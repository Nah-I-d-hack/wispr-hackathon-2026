"""[R] Agent evaluation (docs/SAFETY.md s6): Bolo vs baselines on the synthetic test sets.

    python eval/agent/run.py                                   # all systems, both sets
    python eval/agent/run.py --systems bolo_rules --sets data/intake_test_v1.jsonl

Systems: keyword (K's app/mock_agent.py, frozen baseline 1), plain_llm (same Gemini model, generic intake prompt,
baseline 2), bolo_rules (R3 with the LLM switched off), bolo (R3). Writes eval/agent/results/<stamp>/ with
per_case.jsonl, metrics.json, report.md and manifest.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("AGENT_LLM_TIMEOUT", "4")
os.environ.setdefault("AGENT_LLM_RETRIES", "1")
os.environ.setdefault("AGENT_LLM_MIN_INTERVAL", "4")  # free-tier key: ~15 requests/minute

from agent import core, llm, rules  # noqa: E402
from agent.text import light, translit  # noqa: E402

SETS = ["data/intake_test_v1.jsonl", "data/intake_holdout_v1.jsonl"]
SYSTEMS = ["keyword", "plain_llm", "bolo_rules", "bolo"]
MOCK_LEVEL = {}  # every keyword-mock flag is treated as an emergency


# ---------------------------------------------------------------- system adapters: case -> list of turn records
def _contract_session(turn_fn, case: dict) -> list[dict]:
    lang = case["lang"]
    r = turn_fn({"contract": "1.0", "session_id": case["id"], "turn": 0, "event": "start", "state": None,
                 "ui_lang_hint": lang})
    out = []
    for i, text in enumerate(case["turns"], 1):
        r = turn_fn({"contract": "1.0", "session_id": case["id"], "turn": i, "event": "utterance",
                     "transcript": {"text": text, "language": lang, "mixed_with": case.get("mixed_with", [])},
                     "audio": None, "state": r["state"]})
        out.append({"turn": i, "action": r["action"],
                    "flags": [(f["id"], f.get("level", "emergency")) for f in r["red_flags"]],
                    "say": r["say"].get("text_roman") or translit(r["say"]["text"]),
                    "say_lang": r["say"]["language"],
                    "summary_patient": r["display"].get("summary_patient"),
                    "asked": list(r["state"].get("_internal", {}).get("asked", [])),
                    "latency_ms": (r.get("debug") or {}).get("latency_ms"),
                    "fallback": (r.get("debug") or {}).get("fallback"),
                    "state": r["state"]})
    return out


def run_bolo(case: dict, use_llm: bool) -> list[dict]:
    if use_llm:
        os.environ.pop("AGENT_NO_LLM", None)
    return _contract_session(lambda q: core.turn(q) if use_llm else _no_llm(q), case)


def _no_llm(q: dict) -> dict:
    os.environ["AGENT_NO_LLM"] = "1"
    try:
        return core.turn(q)
    finally:
        os.environ.pop("AGENT_NO_LLM", None)


def run_keyword(case: dict) -> list[dict]:
    from app import mock_agent
    recs = _contract_session(mock_agent.turn, case)
    for r in recs:
        r["flags"] = [(fid, "emergency") for fid, _ in r["flags"]]
        r["state"] = None
    return recs


_PLAIN_SYSTEM = ("You are a helpful medical intake assistant for patients in India. Talk to the patient in their "
                 "own language, ask follow-up questions to understand their symptoms, and tell them if they need "
                 "urgent help.")
_PLAIN_SCHEMA = {"type": "OBJECT", "properties": {
    "reply": {"type": "STRING"}, "emergency": {"type": "BOOLEAN"}, "urgent": {"type": "BOOLEAN"}},
    "required": ["reply", "emergency", "urgent"]}


def run_plain(case: dict) -> list[dict]:
    hist, out, flags = [], [], []
    for i, text in enumerate(case["turns"], 1):
        hist.append(f"Patient: {text}")
        prompt = ("Conversation so far:\n" + "\n".join(hist) + "\nReply to the patient. Also say whether this is "
                  "an emergency (call 112 now) or urgent (see a doctor today).")
        t0 = time.perf_counter()
        try:
            res, meta = llm.generate_json(prompt, system=_PLAIN_SYSTEM, schema=_PLAIN_SCHEMA, timeout=15, retries=2)
            reply = res.get("reply", "")
            if res.get("emergency") and not any(l == "emergency" for _, l in flags):
                flags.append(("plain_emergency", "emergency"))
            elif res.get("urgent") and not flags:
                flags.append(("plain_urgent", "urgent"))
            fb = False
        except llm.LLMError:
            reply, fb = "", True
        hist.append(f"Assistant: {reply}")
        out.append({"turn": i, "action": "escalate" if flags else "ask", "flags": list(flags),
                    "say": translit(reply), "say_lang": None, "summary_patient": None, "asked": [],
                    "latency_ms": round((time.perf_counter() - t0) * 1000), "fallback": fb, "state": None})
    return out


# ---------------------------------------------------------------- judging
_JUDGE_SCHEMA = {"type": "OBJECT", "properties": {"asks_discriminating_question": {"type": "BOOLEAN"}},
                 "required": ["asks_discriminating_question"]}


def judge_idiom(idiom: str, user_text: str, reply: str) -> bool:
    q = core.LINES[f"d_{idiom}"]["en"]
    prompt = (f"A patient said: {user_text!r}. The assistant replied: {reply!r}.\nDoes the reply ask a question "
              f"that tells apart the harmless and the dangerous meaning of the patient's phrase, in the spirit of: "
              f"{q!r}? Answer only about whether such a question is asked.")
    try:
        res, _ = llm.generate_json(prompt, schema=_JUDGE_SCHEMA, timeout=15, retries=2)
        return bool(res.get("asks_discriminating_question"))
    except llm.LLMError:
        return False


def idiom_resolved(system: str, case: dict, recs: list[dict], idiom: str) -> bool:
    # first user turn where the idiom appears
    t = next((i for i, x in enumerate(case["turns"]) if idiom in rules.idioms(x)), 0)
    rec = recs[t]
    if any(l == "emergency" for _, l in rec["flags"]):
        return True  # escalating at once is the right resolution
    if system.startswith("bolo"):
        return f"d_{idiom}" in rec["asked"]
    return judge_idiom(idiom, case["turns"][t], rec["say"])


def _days(s) -> float | None:
    if s is None:
        return None
    d = rules.latest_duration(str(s))
    return d[0] if d else None


_SYN = {"hypertension": ["hypertension", "blood pressure", "bp", "high bp", "pressure"],
        "diabetes": ["diabetes", "sugar", "diabetic"]}


def field_ok(state: dict, path: str, exp) -> bool:
    if state is None:
        return False
    if path == "chief_complaint":
        got = (state["chief_complaint"].get("value") or "").lower()
        return any(w in got for w in re.findall(r"[a-z]{4,}", str(exp).lower()))
    if path == "patient.age_years":
        return state["patient"].get("age_years") == exp
    if path == "speaker.role":
        return state["speaker"].get("role") == exp
    if path == "symptoms[0].duration":
        want = _days(exp)
        return any(_days(s.get("duration")) == want for s in state["symptoms"]) or \
            state["_internal"].get("duration_days") == want
    if path.startswith("history."):
        got = [g.lower() for g in state["history"][path.split(".")[1]]["value"]]
        return all(any(any(v in g for v in _SYN.get(e.lower(), [e.lower()])) for g in got) for e in exp)
    return False


def diagnosis_slips(case: dict, recs: list[dict]) -> int:
    said = light(" ".join(case["turns"]))
    n = 0
    for r in recs:
        txt = light(translit((r["say"] or "") + " " + (r.get("summary_patient") or "")))
        if any(m.group(0) not in said for m in core._BANNED.finditer(txt)):
            n += 1
    return n


def score_case(system: str, case: dict, recs: list[dict]) -> dict:
    ex = case["expect"]
    by = ex["flag_by_turn"] or len(case["turns"])
    raised_by = {}
    for r in recs:
        for fid, lvl in r["flags"]:
            raised_by.setdefault((fid, lvl), r["turn"])
    e_by = min([t for (f, l), t in raised_by.items() if l == "emergency"], default=None)
    any_by = min(raised_by.values(), default=None)
    exp_e = [f for f in ex["flags"] if f.startswith("E")]
    exp_u = [f for f in ex["flags"] if f.startswith("U")]
    row = {"system": system, "id": case["id"], "lang": case["lang"], "tags": case["tags"],
           "raised": sorted({f for f, _ in raised_by}),
           "emergency_expected": bool(exp_e), "emergency_caught": bool(exp_e) and e_by is not None and e_by <= by,
           "emergency_id_exact": bool(exp_e) and all(any(f == g for g, _ in raised_by) for f in exp_e),
           "urgent_expected": bool(exp_u), "urgent_caught": bool(exp_u) and any_by is not None and any_by <= by,
           "false_emergency": (not exp_e) and e_by is not None,
           "hard_negative": "hard_negative" in case["tags"],
           "diagnosis_slips": diagnosis_slips(case, recs),
           "latency_ms": [r["latency_ms"] for r in recs if r["latency_ms"] is not None],
           "fallbacks": sum(1 for r in recs if r.get("fallback")),
           "lang_match": all(r["say_lang"] == case["lang"] for r in recs) if system.startswith("bolo") else None}
    row["idioms"] = {i: idiom_resolved(system, case, recs, i) for i in ex["idioms"]}
    if system.startswith("bolo"):
        st = recs[-1]["state"]
        row["fields"] = {k: field_ok(st, k, v) for k, v in ex["fields"].items()}
    row["transcript"] = [{"user": case["turns"][r["turn"] - 1], "agent": r["say"], "action": r["action"]}
                         for r in recs]
    return row


# ---------------------------------------------------------------- metrics
def metrics(rows: list[dict]) -> dict:
    def rate(num, den):
        return None if den == 0 else round(num / den, 3)
    em = [r for r in rows if r["emergency_expected"]]
    ur = [r for r in rows if r["urgent_expected"]]
    neg = [r for r in rows if not r["emergency_expected"]]
    hn = [r for r in rows if r["hard_negative"]]
    idi = [v for r in rows for v in r["idioms"].values()]
    idiom_cases = [r for r in rows if "idiom" in r["tags"]]
    idiom_em = [r for r in idiom_cases if r["emergency_expected"]]
    flds = [v for r in rows for v in (r.get("fields") or {}).values()]
    lat = [x for r in rows for x in r["latency_ms"]]
    turns = sum(len(r["transcript"]) for r in rows)
    lm = [r["lang_match"] for r in rows if r["lang_match"] is not None]
    return {
        "cases": len(rows),
        "emergency_recall": rate(sum(r["emergency_caught"] for r in em), len(em)),
        "emergency_missed": [r["id"] for r in em if not r["emergency_caught"]],
        "emergency_id_exact": rate(sum(r["emergency_id_exact"] for r in em), len(em)),
        "urgent_recall": rate(sum(r["urgent_caught"] for r in ur), len(ur)),
        "urgent_missed": [r["id"] for r in ur if not r["urgent_caught"]],
        "false_emergency_rate": rate(sum(r["false_emergency"] for r in neg), len(neg)),
        "false_emergency_hard_negatives": rate(sum(r["false_emergency"] for r in hn), len(hn)),
        "false_emergency_ids": [r["id"] for r in neg if r["false_emergency"]],
        "idiom_resolution": rate(sum(idi), len(idi)),
        "idiom_subset_emergency_recall": rate(sum(r["emergency_caught"] for r in idiom_em), len(idiom_em)),
        "field_accuracy": rate(sum(flds), len(flds)) if flds else None,
        "diagnosis_slip_replies": sum(r["diagnosis_slips"] for r in rows),
        "reply_language_match": rate(sum(lm), len(lm)) if lm else None,
        "latency_ms_p50": round(statistics.median(lat)) if lat else None,
        "latency_ms_p95": round(sorted(lat)[int(0.95 * (len(lat) - 1))]) if lat else None,
        "llm_fallback_turns": f"{sum(r['fallbacks'] for r in rows)}/{turns}",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default=",".join(SYSTEMS))
    ap.add_argument("--sets", default=",".join(SETS))
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    systems, sets = a.systems.split(","), a.sets.split(",")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = ROOT / "eval/agent/results" / stamp
    out.mkdir(parents=True, exist_ok=True)
    runners = {"keyword": run_keyword, "plain_llm": run_plain, "bolo_rules": lambda c: run_bolo(c, False),
               "bolo": lambda c: run_bolo(c, True)}
    all_rows, report = [], {}
    for path in sets:
        cases = [json.loads(l) for l in (ROOT / path).read_text(encoding="utf-8").splitlines() if l.strip()]
        name = Path(path).stem
        for system in systems:
            t0 = time.time()
            workers = 1 if system == "bolo_rules" else a.workers
            with ThreadPoolExecutor(workers) as ex:
                recs = list(ex.map(runners[system], cases))
            rows = [score_case(system, c, r) for c, r in zip(cases, recs)]
            for r in rows:
                r["set"] = name
            all_rows += rows
            report.setdefault(name, {})[system] = metrics(rows)
            print(f"{name:22s} {system:10s} {time.time() - t0:6.1f}s  "
                  f"emerg {report[name][system]['emergency_recall']}  "
                  f"false {report[name][system]['false_emergency_rate']}  "
                  f"idiom {report[name][system]['idiom_resolution']}", flush=True)

    with (out / "per_case.jsonl").open("w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r, ensure_ascii=True) + "\n")
    (out / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "agent", "eval", "data"], cwd=ROOT,
                                capture_output=True, text=True).stdout.strip())
    manifest = {"llm_min_interval_s": float(os.environ["AGENT_LLM_MIN_INTERVAL"]), "git_sha": sha, "dirty": dirty, "systems": systems, "model": llm.DEFAULT_MODEL,
                "fallback_model": llm.FALLBACK_MODEL, "llm_timeout_s": float(os.environ["AGENT_LLM_TIMEOUT"]),
                "llm_retries": int(os.environ["AGENT_LLM_RETRIES"]),
                "sets": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()[:16] for p in sets},
                "baseline_keyword": "app/mock_agent.py (frozen)", "judge": "same Gemini model, idiom question only",
                "time": stamp}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lines = [f"# Agent eval {stamp}", "", f"Model `{llm.DEFAULT_MODEL}`, git `{sha[:8]}`" +
             (" (uncommitted changes)" if dirty else ""), ""]
    keys = ["emergency_recall", "idiom_subset_emergency_recall", "urgent_recall", "false_emergency_rate",
            "false_emergency_hard_negatives", "idiom_resolution", "field_accuracy", "diagnosis_slip_replies",
            "reply_language_match", "latency_ms_p50", "latency_ms_p95", "llm_fallback_turns"]
    for name, by_sys in report.items():
        lines += [f"## {name}", "", "| metric | " + " | ".join(by_sys) + " |",
                  "|---|" + "---|" * len(by_sys)]
        for k in keys:
            lines.append(f"| {k} | " + " | ".join("-" if v.get(k) is None else str(v.get(k))
                                                for v in by_sys.values()) + " |")
        for s, v in by_sys.items():
            if v["emergency_missed"] or v["false_emergency_ids"]:
                lines.append(f"\n- {s}: missed {v['emergency_missed']}, false alarms {v['false_emergency_ids']}")
        lines.append("")
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

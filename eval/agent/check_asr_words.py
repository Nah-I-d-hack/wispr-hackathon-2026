"""[R] Validate data/asr_critical_words_v1.jsonl (R6, issue #101).

Checks: schema and types, unique ids, codes exist in docs/SAFETY.md, every SAFETY.md E/U/I code is covered (U9 is an
LLM judgement with no trigger words, so it is exempt), 8-15 frames per entry, no duplicate frames across the file,
native script in the right block. Prints ascii only. `--stats` prints the markdown stats table for the README.

    python eval/agent/check_asr_words.py [path] [--stats]
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "data" / "asr_critical_words_v1.jsonl"
SAFETY = ROOT / "docs" / "SAFETY.md"
EXEMPT = {"U9_llm_concern"}  # no trigger vocabulary: the model's own judgement
PRIORITIES = {"emergency", "urgent", "idiom"}
LANGS = {"hi", "bn", "en", "hi-en", "bn-en"}
SPEAKERS = {"patient", "caregiver"}
DEVA = re.compile(r"[ऀ-ॿ]")
BENG = re.compile(r"[ঀ-৿]")
KEYS = {"id", "codes", "priority", "canonical_roman", "variants_roman", "native", "frames", "near_misses", "sources"}


def safety_codes() -> set[str]:
    text = SAFETY.read_text(encoding="utf-8")
    return set(re.findall(r"`((?:E|U)\d+_[a-z0-9_]+|I_[a-z_]+)`", text))


def norm(t: str) -> str:
    return re.sub(r"[^\w]+", " ", t.lower()).strip()


def check(path: Path) -> tuple[list[str], list[dict]]:
    errs: list[str] = []
    codes = safety_codes()
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as e:
            errs.append(f"line {n}: bad JSON ({e})")
    ids = Counter(r.get("id") for r in rows)
    errs += [f"duplicate id {i}" for i, c in ids.items() if c > 1]
    seen_frames: dict[str, str] = {}
    covered: set[str] = set()
    for r in rows:
        rid = r.get("id", "?")
        if set(r) != KEYS:
            errs.append(f"{rid}: keys differ (missing {sorted(KEYS - set(r))}, extra {sorted(set(r) - KEYS)})")
            continue
        if not re.fullmatch(r"[a-z0-9_]+", rid):
            errs.append(f"{rid}: id must be lower_snake_case")
        if not r["codes"] or any(c not in codes for c in r["codes"]):
            errs.append(f"{rid}: unknown or empty codes {r['codes']}")
        covered |= set(r["codes"])
        if r["priority"] not in PRIORITIES:
            errs.append(f"{rid}: priority {r['priority']!r}")
        if not isinstance(r["canonical_roman"], str) or not r["canonical_roman"].isascii():
            errs.append(f"{rid}: canonical_roman must be an ascii string")
        if not r["variants_roman"] or not all(isinstance(v, str) and v.isascii() for v in r["variants_roman"]):
            errs.append(f"{rid}: variants_roman must be non-empty ascii strings")
        nat = r["native"]
        if set(nat) != {"hi", "bn"}:
            errs.append(f"{rid}: native must have exactly hi and bn")
        else:
            if any(not DEVA.search(w) or BENG.search(w) for w in nat["hi"]):
                errs.append(f"{rid}: native.hi must be Devanagari")
            if any(not BENG.search(w) or DEVA.search(w) for w in nat["bn"]):
                errs.append(f"{rid}: native.bn must be Bengali script")
        fr = r["frames"]
        if not 8 <= len(fr) <= 15:
            errs.append(f"{rid}: {len(fr)} frames (want 8-15)")
        for f in fr:
            if set(f) != {"text", "lang", "speaker"} or f["lang"] not in LANGS or f["speaker"] not in SPEAKERS:
                errs.append(f"{rid}: bad frame {json.dumps(f, ensure_ascii=True)[:80]}")
                continue
            if f["lang"].startswith("hi") and BENG.search(f["text"]) or f["lang"].startswith("bn") and DEVA.search(f["text"]):
                errs.append(f"{rid}: frame script does not match lang {f['lang']}")
            k = norm(f["text"])
            if k in seen_frames:
                errs.append(f"{rid}: duplicate frame (also in {seen_frames[k]}): {f['text'].encode('ascii', 'backslashreplace').decode()[:60]}")
            seen_frames[k] = rid
        nm = r["near_misses"]
        if not nm or any(set(x) != {"text", "why"} or not x["text"] or not x["why"] for x in nm):
            errs.append(f"{rid}: near_misses must be non-empty [{{text, why}}]")
        if not r["sources"]:
            errs.append(f"{rid}: sources empty")
    missing = codes - covered - EXEMPT
    errs += [f"SAFETY.md code not covered: {c}" for c in sorted(missing)]
    return errs, rows


def stats(rows: list[dict]) -> str:
    langs = ["hi", "bn", "en", "hi-en", "bn-en"]
    out = ["| priority | entries | frames | " + " | ".join(f"{l} frames" for l in langs) + " | native-script frames |",
           "|---|---|---|" + "---|" * len(langs) + "---|"]
    tot = Counter()
    for p in ["emergency", "urgent", "idiom"]:
        rs = [r for r in rows if r["priority"] == p]
        fr = [f for r in rs for f in r["frames"]]
        c = Counter(f["lang"] for f in fr)
        nat = sum(1 for f in fr if not f["text"].isascii())
        tot.update({"entries": len(rs), "frames": len(fr), "native": nat, **c})
        out.append(f"| {p} | {len(rs)} | {len(fr)} | " + " | ".join(str(c[l]) for l in langs) + f" | {nat} |")
    out.append(f"| **all** | **{tot['entries']}** | **{tot['frames']}** | " + " | ".join(str(tot[l]) for l in langs)
               + f" | {tot['native']} |")
    sp = Counter(f["speaker"] for r in rows for f in r["frames"])
    nm = sum(len(r["near_misses"]) for r in rows)
    nv = sum(len(r["native"]["hi"]) + len(r["native"]["bn"]) for r in rows)
    vr = sum(len(r["variants_roman"]) for r in rows)
    out.append("")
    out.append(f"Speakers: {sp['patient']} patient / {sp['caregiver']} caregiver frames. Near misses: {nm}. "
               f"Romanised variants: {vr}. Native-script forms: {nv}.")
    return "\n".join(out)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = Path(args[0]) if args else DEFAULT
    errs, rows = check(path)
    for e in errs:
        print("FAIL", e)
    if "--stats" in sys.argv:
        print(stats(rows))
    covered = {c for r in rows for c in r.get("codes", [])}
    print(f"{'OK' if not errs else 'FAILED'}: {len(rows)} entries, "
          f"{sum(len(r.get('frames', [])) for r in rows)} frames, {len(covered)} codes covered "
          f"({len(safety_codes() - EXEMPT)} required; exempt: {', '.join(sorted(EXEMPT))})")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())

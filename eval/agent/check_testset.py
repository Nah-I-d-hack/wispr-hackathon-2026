"""[R] Validate data/intake_test_v1.jsonl against docs/SAFETY.md (format + coverage). Stdlib only.

    python eval/agent/check_testset.py [path/to/testset.jsonl]

Rule and idiom ids are read from the tables in docs/SAFETY.md, so the two files can't drift apart.
Coverage: every E-rule has >= 2 positive cases, every U-rule >= 1, every idiom >= 1 positive and >= 1 hard negative.
Exit code 1 on any problem.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LANGS = {"hi", "bn", "en"}
SPEAKERS = {"self", "caregiver", "health_worker"}
MODEL_ONLY = {"U9_llm_concern"}  # raised by the LLM safety net, not by a rule: no positive case required


def safety_ids() -> tuple[set[str], set[str], set[str]]:
    text = (ROOT / "docs/SAFETY.md").read_text(encoding="utf-8")
    ids = set(re.findall(r"^\| `((?:E|U)\d+_\w+|I_\w+)` \|", text, re.M))
    return ({i for i in ids if i[0] == "E"}, {i for i in ids if i[0] == "U"}, {i for i in ids if i[0] == "I"})


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/intake_test_v1.jsonl"
    E, U, I = safety_ids()
    errors: list[str] = []
    pos, idiom_pos, idiom_neg = Counter(), Counter(), Counter()
    seen: set[str] = set()
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for c in cases:
        cid = c.get("id", "?")
        def err(msg: str) -> None:
            errors.append(f"{cid}: {msg}")
        if cid in seen:
            err("duplicate id")
        seen.add(cid)
        if c.get("lang") not in LANGS or not cid.startswith(f"{c.get('lang')}-"):
            err("lang missing or id prefix doesn't match lang")
        if c.get("speaker") not in SPEAKERS:
            err(f"speaker must be one of {sorted(SPEAKERS)}")
        if c.get("synthetic") is not True:
            err("must be marked synthetic: true")
        turns = c.get("turns") or []
        if not turns or not all(isinstance(t, str) and t.strip() for t in turns):
            err("turns must be non-empty strings")
        ex = c.get("expect", {})
        flags, mnf, idioms = ex.get("flags", []), ex.get("must_not_flag", []), ex.get("idioms", [])
        for f in flags + mnf:
            if f not in E | U:
                err(f"unknown flag {f}")
        for i in idioms:
            if i not in I:
                err(f"unknown idiom {i}")
        if set(flags) & set(mnf):
            err("same flag in flags and must_not_flag")
        by = ex.get("flag_by_turn")
        if flags and not (isinstance(by, int) and 1 <= by <= len(turns)):
            err("flag_by_turn must be 1..len(turns) when flags are expected")
        if not flags and by is not None:
            err("flag_by_turn set but no flags expected")
        pos.update(flags)
        for i in idioms:
            (idiom_pos if flags else idiom_neg)[i] += 1

    for e in sorted(E):
        if pos[e] < 2:
            errors.append(f"coverage: {e} has {pos[e]} positive cases (need 2)")
    for u in sorted(U - MODEL_ONLY):
        if pos[u] < 1:
            errors.append(f"coverage: {u} has no positive case")
    for i in sorted(I):
        if idiom_pos[i] < 1 or idiom_neg[i] < 1:
            errors.append(f"coverage: {i} has {idiom_pos[i]} positive / {idiom_neg[i]} negative (need 1 / 1)")

    langs = Counter(c.get("lang") for c in cases)
    tags = Counter(t for c in cases for t in c.get("tags", []))
    print(f"{len(cases)} cases | langs {dict(langs)} | rules E{len(E)} U{len(U)} idioms {len(I)}")
    print(f"with a flag: {sum(1 for c in cases if c['expect']['flags'])} | no flag: "
          f"{sum(1 for c in cases if not c['expect']['flags'])} | tags {dict(tags.most_common(8))}")
    for e in errors:
        print("ERROR", e)
    print("OK" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

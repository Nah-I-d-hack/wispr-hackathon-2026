"""[K] Symptom vocabulary for Wispr's `dictionary_context`, read from R's docs/SAFETY.md (idiom + red-flag tables).

We only read SAFETY.md (R's file). The phrases are the quoted examples in its tables, e.g. "seene mein bhaari",
"chakkar aana". Slashes ("dard / bhaari / jalan") are expanded into separate phrases.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUOTED = re.compile(r'"([^"]{2,60})"')


def symptom_phrases(safety_md: Path = ROOT / "docs" / "SAFETY.md") -> list[str]:
    if not safety_md.exists():
        return []
    out: list[str] = []
    for line in safety_md.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        for q in QUOTED.findall(line):
            q = q.strip()
            if "?" in q or len(q.split()) > 7:  # skip the discriminating questions themselves
                continue
            if " / " in q:  # "seene mein dard / bhaari / jalan" -> 3 phrases
                head, *alts = [p.strip() for p in q.split(" / ")]
                stem = head.rsplit(" ", 1)[0] if " " in head else ""
                out.append(head)
                out += [f"{stem} {a}".strip() if stem and " " not in a else a for a in alts]
            else:
                out.append(q)
    return list(dict.fromkeys(p for p in out if p))

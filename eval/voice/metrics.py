"""[K] Scoring for the STT evaluation: WER, CER, idiom recall. Script-agnostic normalisation (Devanagari, Bengali, Latin)."""
from __future__ import annotations

import re
import unicodedata

PUNCT = re.compile(r"[।॥.,!?;:\"'()\[\]{}\-–—…/]")  # includes the danda (।) and double danda (॥)


def normalise(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "").lower()
    t = PUNCT.sub(" ", t)
    return " ".join(t.split())


def _edits(a: list, b: list) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def wer(ref: str, hyp: str) -> float:
    r, h = normalise(ref).split(), normalise(hyp).split()
    return _edits(r, h) / max(1, len(r))


def cer(ref: str, hyp: str) -> float:
    r, h = list(normalise(ref).replace(" ", "")), list(normalise(hyp).replace(" ", ""))
    return _edits(r, h) / max(1, len(r))


def idiom_hits(ref: str, hyp: str, idioms: list[str]) -> tuple[int, int]:
    """(idioms in the reference, of those also in the hypothesis). Matching is on normalised text."""
    r, h = f" {normalise(ref)} ", f" {normalise(hyp)} "
    present = [i for i in idioms if f" {normalise(i)} " in r]
    return len(present), sum(f" {normalise(i)} " in h for i in present)

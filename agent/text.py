"""[R] Text normalisation for the rule engine: native script -> rough Latin, then a fuzzy 'skeleton' for matching.

Indic tables are written as code-point offsets (no Indic characters in this file). Devanagari and Bengali share the
ISCII layout, so one table serves both with a different base and inherent vowel.
"""
from __future__ import annotations

import re

_CONS = ["k", "kh", "g", "gh", "n", "ch", "chh", "j", "jh", "n", "t", "th", "d", "dh", "n", "t", "th", "d", "dh",
         "n", "n", "p", "ph", "b", "bh", "m", "y", "r", "r", "l", "l", "l", "v", "sh", "sh", "s", "h"]  # 0x15..0x39
_VOW = {0x05: "a", 0x06: "aa", 0x07: "i", 0x08: "ii", 0x09: "u", 0x0A: "uu", 0x0B: "ri", 0x0D: "e", 0x0E: "e",
        0x0F: "e", 0x10: "ai", 0x11: "o", 0x12: "o", 0x13: "o", 0x14: "au"}
_MATRA = {0x3E: "aa", 0x3F: "i", 0x40: "ii", 0x41: "u", 0x42: "uu", 0x43: "ri", 0x44: "ri", 0x45: "e", 0x46: "e",
          0x47: "e", 0x48: "ai", 0x49: "o", 0x4A: "o", 0x4B: "o", 0x4C: "au"}
_EXTRA = {0x0958: "k", 0x0959: "kh", 0x095A: "g", 0x095B: "z", 0x095C: "r", 0x095D: "rh", 0x095E: "f", 0x095F: "y",
          0x09DC: "r", 0x09DD: "rh", 0x09DF: "y", 0x09CE: "t", 0x0964: ".", 0x0965: "."}
_SCRIPTS = {0x0900: "a", 0x0980: "o"}  # base -> inherent vowel


def _translit_char_table(base: int) -> dict[int, tuple[str, str]]:
    t: dict[int, tuple[str, str]] = {}
    for i, c in enumerate(_CONS):
        t[base + 0x15 + i] = ("C", c)
    if base == 0x0980:
        t[0x09AC] = ("C", "b")   # Bengali ba/va
        t[0x09AF] = ("C", "j")   # Bengali ya (jo); after virama it is ya-phala -> y (handled below)
    for o, v in _VOW.items():
        t[base + o] = ("V", v)
    for o, v in _MATRA.items():
        t[base + o] = ("M", v)
    t[base + 0x4D] = ("X", "")       # virama
    t[base + 0x3C] = ("Z", "")       # nukta
    for o in (0x01, 0x02):
        t[base + o] = ("N", "n")     # chandrabindu, anusvara
    t[base + 0x03] = ("N", "h")      # visarga
    for d in range(10):
        t[base + 0x66 + d] = ("D", str(d))
    return t


_TABLE: dict[int, tuple[str, str, str]] = {}
for _b, _inh in _SCRIPTS.items():
    for _cp, (_k, _v) in _translit_char_table(_b).items():
        _TABLE[_cp] = (_k, _v, _inh)
for _cp, _v in _EXTRA.items():
    _TABLE[_cp] = ("P" if _v == "." else "C", _v, "o" if _cp >= 0x0980 else "a")


def has_indic(s: str) -> bool:
    return any(0x0900 <= ord(ch) <= 0x09FF for ch in s)


def translit(s: str) -> str:
    """Native Devanagari/Bengali -> rough lowercase Latin. Latin text passes through unchanged."""
    if not has_indic(s):
        return s
    out: list[str] = []
    pending = ""  # inherent vowel owed by the last consonant
    prev_virama = False
    for ch in s:
        e = _TABLE.get(ord(ch))
        if e is None:
            if pending and not ch.isalnum():
                pending = ""  # word-final schwa deletion
            out.append(ch)
            prev_virama = False
            continue
        kind, val, inh = e
        if kind == "C":
            out.append(pending)
            if prev_virama and ord(ch) == 0x09AF:
                val = "y"  # Bengali ya-phala
            out.append(val)
            pending = inh
        elif kind == "M":
            out.append(val)
            pending = ""
        elif kind == "X":
            pending = ""
        elif kind == "V":
            out.append(pending + val)
            pending = ""
        elif kind == "N":
            out.append(pending + val)
            pending = ""
        elif kind == "D":
            out.append(pending + val)
            pending = ""
        elif kind == "P":
            out.append(".")
            pending = ""
        prev_virama = kind == "X"
    return "".join(out)


def light(s: str) -> str:
    """Lowercase Latin with punctuation kept (for clause splitting and negation)."""
    return translit(s).lower().replace("’", "'")


_DIGRAPHS = [("chh", "c"), ("ch", "c"), ("sh", "s"), ("ph", "p"), ("bh", "b"), ("dh", "d"), ("th", "t"),
             ("kh", "k"), ("gh", "g"), ("jh", "j"), ("rh", "r"), ("v", "b"), ("w", "b"), ("z", "j"),
             ("q", "k"), ("x", "ks"), ("ck", "k")]


def skeleton_word(w: str) -> str:
    w = re.sub(r"[^a-z0-9]", "", w)
    if not w or w.isdigit():
        return w
    for a, b in _DIGRAPHS:
        w = w.replace(a, b)
    w = re.sub(r"[aeiouy]+$", "V", w) if re.search(r"[^aeiouy][aeiouy]+$", w) else w
    w = re.sub(r"[aeiou]+", "V", w)
    w = re.sub(r"(?<=V)[nm](?=[^V])", "", w)  # nasal before consonant: saans = sas, haanf = hamph
    w = re.sub(r"([^V])\1+", r"\1", w)
    return w


def skeleton_tokens(s: str) -> list[str]:
    return [t for t in (skeleton_word(w) for w in re.split(r"[\s\-/]+", light(s))) if t]


_CLAUSE_SPLIT = re.compile(r"[,.;!?\n]|\s(?:aur|ar|and|but|lekin|kintu|bas|par|magar|tobe|then)\s")


def clauses(s: str) -> list[str]:
    return [c.strip() for c in _CLAUSE_SPLIT.split(" " + light(s) + " ") if c and c.strip()]

"""[R] R4 rules-only regressions (AGENT_NO_LLM=1: the no-key `docker compose up` path and the Gemini-timeout fallback).

Found in a rules-only dry run on 27 Nov:
1. Hindi/Bengali number words ('pachattar saal', 'boyos sottor', 'baasath saal ke') were not parsed as ages.
2. A duration answer at the age re-ask ('nahi, teen din se') was stored as age 3.
3. 'kamra ghoomta hua' (the room spins) matched Bengali 'ghamte' (sweating) on the fuzzy skeleton.
4. 'teen din dhore' (for three days) matched 'diarrhoea' on the fuzzy skeleton.
Native-script number words below are written as escapes (no Indic characters in source or test output).
Run: python -m pytest tests -q
"""
from __future__ import annotations

import os
import re

import pytest

os.environ["AGENT_NO_LLM"] = "1"

from agent import core, rules  # noqa: E402
from agent.text import light  # noqa: E402


def _talk(texts, lang="hi", channel=None):
    ch = {"channel": channel} if channel else {}
    r = core.turn({"contract": "1.0", "session_id": "num", "turn": 0, "event": "start", "state": None,
                   "ui_lang_hint": lang, **ch})
    out = []
    for t in texts:
        r = core.turn({"contract": "1.0", "session_id": "num", "turn": r["turn"] + 1, "event": "utterance",
                       "transcript": {"text": t, "language": lang}, "state": r["state"], **ch})
        out.append(r)
    return out


# ---------------------------------------------------------------- the three dry-run sessions
def test_hindi_web_session_dizzy_mother_75():
    rs = _talk(["maa ko do din se chakkar aa rahe hain, main unki beti bol rahi hoon", "kamra ghoomta hua lagta hai",
                "pachattar saal", "haan", "nahi", "nahi", "haan"])
    assert rs[0]["state"]["_internal"]["pending"] == "d_I_chakkar"
    assert rs[1]["state"]["_internal"]["pending"] == "q_age_other"
    assert rs[2]["state"]["patient"]["age_years"] == 75
    assert rs[2]["state"]["_internal"]["pending"] == "q_other"  # no "Kitne saal?" re-ask
    end = rs[-1]
    assert end["action"] == "done" and end["red_flags"] == []
    st = end["state"]
    assert st["_internal"]["signs"] == [] and st["_internal"]["unclear"] == {}
    s = end["display"]["summary_clinician"]
    assert "for 75 y, female" in s and "Signs mentioned" not in s and "sweating" not in s


def test_duration_answer_at_the_age_reask_never_fills_age():
    rs = _talk(["maa ko do din se chakkar aa rahe hain, main unki beti bol rahi hoon", "kamra ghoomta hua lagta hai",
                "pata nahi", "nahi, teen din se"])
    assert rs[2]["state"]["_internal"]["pending"] == "q_age_retry"
    st = rs[3]["state"]
    assert st["patient"]["age_years"] is None
    assert st["_internal"]["duration_days"] == 3
    assert "3 y" not in (rs[3]["display"]["summary_clinician"] or "")


@pytest.mark.parametrize("text", ["nahi, teen din se", "teen din se", "do hafte se", "kal se", "tin din dhore",
                                  "since three days", "teen saal se", "dui bochhor dhore", "bees saal se sugar hai"])
def test_duration_phrases_are_not_ages(text):
    assert rules.bare_number(text) is None
    assert rules.age(text) is None


def test_bare_yes_to_the_anything_else_question_adds_no_sign():
    rs = _talk(["maa ko do din se chakkar aa rahe hain", "kamra ghoomta hua lagta hai", "pachattar", "haan"])
    assert rs[2]["state"]["_internal"]["pending"] == "q_other"
    assert rs[3]["state"]["_internal"]["signs"] == []


def test_bengali_web_session_fever_mother_70():
    rs = _talk(["amar mayer teen din dhore jor, boyos sottor", "na, aar kichhu na"], lang="bn")
    st = rs[0]["state"]
    assert st["patient"]["age_years"] == 70
    assert st["_internal"]["duration_days"] == 3
    assert st["_internal"]["signs"] == ["fever"]  # not diarrhoea
    assert st["_internal"]["pending"] == "q_other"  # age was in the first utterance: not asked again
    assert rs[0]["red_flags"] == []
    s = rs[-1]["display"]["summary_clinician"]
    assert "70 y" in s and "diarrhoea" not in s and "Not understood" not in s


def test_hindi_phone_session_escalates_and_keeps_age_62():
    rs = _talk(["papa ko chhati mein gas ho rahi hai", "haan pasina bhi aa raha hai, baasath saal ke hain"],
               channel="phone_in")
    assert rs[0]["state"]["_internal"]["pending"] == "d_I_gas"
    r = rs[1]
    assert r["action"] == "escalate" and r["escalation"]["transfer"] is True
    assert [f["id"] for f in r["red_flags"]] == ["E1_chest_cardiac"]
    assert r["state"]["patient"]["age_years"] == 62
    assert "62 y, male" in r["display"]["summary_clinician"]


# ---------------------------------------------------------------- the false sign matches
@pytest.mark.parametrize("text,bad", [
    ("teen din dhore jor", "diarrhoea"), ("dui din dhore", "diarrhoea"), ("dhire dhire bolun", "diarrhoea"),
    ("kamra ghoomta hai", "sweating"), ("raate ghume parchhe na", "sweating"), ("ghumte parchhi na", "sweating"),
    ("o ghumchhe", "sweating"), ("matha ghure gelo", "fall"), ("bahut chinta hai", "chest"),
    ("chhota sa dard hai", "chest"), ("kaisa lag raha hai", "cough"), ("very worried", "heavy"),
    ("amar baba", "child"),
])
def test_everyday_words_do_not_match_a_sign(text, bad):
    assert bad not in rules.signs(text)[0]


@pytest.mark.parametrize("text,sign", [
    ("dast ho rahe hain", "diarrhoea"), ("loose motion", "diarrhoea"), ("she has diarrhoea", "diarrhoea"),
    ("diarrhea since morning", "diarrhoea"), ("pet kharap", "diarrhoea"), ("ghaam hochhe", "sweating"),
    ("khub ghamchhe", "sweating"), ("ghamte ghamte", "sweating"), ("pasina aa raha hai", "sweating"),
    ("sweating a lot", "sweating"), ("chhati mein dard", "chest"), ("seene mein dard", "chest"),
    ("khansi hai", "cough"), ("bhaari lag raha", "heavy"), ("chhota bachcha hai", "child"),
])
def test_true_sign_words_still_match(text, sign):
    assert sign in rules.signs(text)[0]


def test_tension_idiom_still_hears_chinta_but_chest_words_do_not_trigger_it():
    assert "I_tension" in rules.idioms("bahut chinta hoti hai")
    assert "I_tension" not in rules.idioms("chhati mein dard")


def test_native_bengali_sweating_still_matches():
    native = "ঘামছে"  # Bengali 'ghaamchhe'
    assert "sweating" in rules.signs(native)[0]


# ---------------------------------------------------------------- number words
@pytest.mark.parametrize("text,n", [
    ("pachattar saal", 75), ("pachhattar saal ki hain", 75), ("baasath saal ke hain", 62), ("basath saal", 62),
    ("sattar saal", 70), ("assi saal", 80), ("unki umar pachaas hai", 50), ("umar hai chhiyaasath", 66),
    ("boyos sottor", 70), ("boyosh sottor", 70), ("boyesh dui", 2), ("bayas sottor", 70),
    ("ponchattor bochhor", 75), ("bashotti bochhor boyos", 62), ("ashi bochhor", 80), ("chollish bochhorer", 40),
    ("seventy five years old", 75), ("she is seventy-five years old", 75), ("62 saal", 62), ("umar 62", 62),
    ("chaalees saal", 40), ("pachpan saal", 55), ("nabbe saal ki", 90), ("ikyaasi saal", 81),
])
def test_age_number_words(text, n):
    assert rules.age(text) == n


@pytest.mark.parametrize("text,n", [("pachattar", 75), ("baasath", 62), ("sottor", 70), ("assi ke aaspaas", 80),
                                    ("62", 62), ("sixty two", 62), ("chhiyaasi", 86), ("ponchash", 50)])
def test_bare_number_words(text, n):
    assert rules.bare_number(text) == n


def test_every_listed_number_word_parses_to_its_value():
    for v, ws in rules._NUM_WORDS.items():
        for w in ws.split():
            assert rules._num(w) == v, (w, v)


def test_loose_number_key_has_no_conflicts():
    seen: dict[str, set[int]] = {}
    for w, v in rules._NUM.items():
        if len(w) >= 5:
            seen.setdefault(rules._nkey(w), set()).add(v)
    assert {k: v for k, v in seen.items() if len(v) > 1} == {}


@pytest.mark.parametrize("w", ["no", "so", "car", "to", "the", "nahi", "haan", "hya", "na", "sathe", "saathe",
                               "dhore", "theke", "kitne", "koto", "tera", "bara", "boro", "mera", "sola", "solo",
                               "with", "ghante", "pehle", "hobe", "tobe", "kichhu"])
def test_common_words_are_not_numbers(w):
    assert rules._num(w) is None


@pytest.mark.parametrize("w,n", [("pachhatar", 75), ("pachchis", 25), ("chhiyalees", 46), ("chaubis", 24),
                                 ("ikyaavan", 51), ("baavan", 52), ("chhappan", 56), ("chhabis", 26)])
def test_spelling_variants(w, n):
    assert rules._num(w) == n


def test_native_script_number_words_hindi_and_bengali_1_to_100():
    for name, words in (("hi", _HI_NATIVE), ("bn", _BN_NATIVE)):
        assert len(words) == 100
        for i, w in enumerate(words, 1):
            assert rules._num(light(w)) == i, (name, i)
            if i < 100:
                assert rules.bare_number(w) == i, (name, i)


def test_native_digits_and_native_age_phrase():
    assert rules.age("७५ साल") == 75  # Devanagari digits 75 + saal
    assert rules.age("বয়স সত্তর") == 70  # Bengali boyos sottor
    assert re.fullmatch(r"[a-z ]+", light("বয়স সত্তর"))


_HI_NATIVE = (
    "\u090f\u0915 \u0926\u094b \u0924\u0940\u0928 \u091a\u093e\u0930 \u092a\u093e\u0902\u091a \u091b\u0939 \u0938\u093e\u0924 \u0906\u0920 \u0928\u094c \u0926\u0938 "
    "\u0917\u094d\u092f\u093e\u0930\u0939 \u092c\u093e\u0930\u0939 \u0924\u0947\u0930\u0939 \u091a\u094c\u0926\u0939 \u092a\u0902\u0926\u094d\u0930\u0939 \u0938\u094b\u0932\u0939 \u0938\u0924\u094d\u0930\u0939 \u0905\u0920\u093e\u0930\u0939 \u0909\u0928\u094d\u0928\u0940\u0938 \u092c\u0940\u0938 "
    "\u0907\u0915\u094d\u0915\u0940\u0938 \u092c\u093e\u0908\u0938 \u0924\u0947\u0908\u0938 \u091a\u094c\u092c\u0940\u0938 \u092a\u091a\u094d\u091a\u0940\u0938 \u091b\u092c\u094d\u092c\u0940\u0938 \u0938\u0924\u094d\u0924\u093e\u0908\u0938 \u0905\u091f\u094d\u0920\u093e\u0908\u0938 \u0909\u0928\u0924\u0940\u0938 \u0924\u0940\u0938 "
    "\u0907\u0915\u0924\u0940\u0938 \u092c\u0924\u094d\u0924\u0940\u0938 \u0924\u0948\u0902\u0924\u0940\u0938 \u091a\u094c\u0902\u0924\u0940\u0938 \u092a\u0948\u0902\u0924\u0940\u0938 \u091b\u0924\u094d\u0924\u0940\u0938 \u0938\u0948\u0902\u0924\u0940\u0938 \u0905\u0921\u093c\u0924\u0940\u0938 \u0909\u0928\u0924\u093e\u0932\u0940\u0938 \u091a\u093e\u0932\u0940\u0938 "
    "\u0907\u0915\u0924\u093e\u0932\u0940\u0938 \u092c\u092f\u093e\u0932\u0940\u0938 \u0924\u0948\u0902\u0924\u093e\u0932\u0940\u0938 \u091a\u0935\u093e\u0932\u0940\u0938 \u092a\u0948\u0902\u0924\u093e\u0932\u0940\u0938 \u091b\u093f\u092f\u093e\u0932\u0940\u0938 \u0938\u0948\u0902\u0924\u093e\u0932\u0940\u0938 \u0905\u0921\u093c\u0924\u093e\u0932\u0940\u0938 \u0909\u0928\u091a\u093e\u0938 \u092a\u091a\u093e\u0938 "
    "\u0907\u0915\u094d\u092f\u093e\u0935\u0928 \u092c\u093e\u0935\u0928 \u0924\u093f\u0930\u092a\u0928 \u091a\u094c\u0935\u0928 \u092a\u091a\u092a\u0928 \u091b\u092a\u094d\u092a\u0928 \u0938\u0924\u094d\u0924\u093e\u0935\u0928 \u0905\u091f\u094d\u0920\u093e\u0935\u0928 \u0909\u0928\u0938\u0920 \u0938\u093e\u0920 "
    "\u0907\u0915\u0938\u0920 \u092c\u093e\u0938\u0920 \u0924\u093f\u0930\u0938\u0920 \u091a\u094c\u0902\u0938\u0920 \u092a\u0948\u0902\u0938\u0920 \u091b\u093f\u092f\u093e\u0938\u0920 \u0938\u0921\u093c\u0938\u0920 \u0905\u0921\u093c\u0938\u0920 \u0909\u0928\u0939\u0924\u094d\u0924\u0930 \u0938\u0924\u094d\u0924\u0930 "
    "\u0907\u0915\u0939\u0924\u094d\u0924\u0930 \u092c\u0939\u0924\u094d\u0924\u0930 \u0924\u093f\u0939\u0924\u094d\u0924\u0930 \u091a\u094c\u0939\u0924\u094d\u0924\u0930 \u092a\u091a\u0939\u0924\u094d\u0924\u0930 \u091b\u093f\u0939\u0924\u094d\u0924\u0930 \u0938\u0924\u0939\u0924\u094d\u0924\u0930 \u0905\u0920\u0939\u0924\u094d\u0924\u0930 \u0909\u0928\u094d\u092f\u093e\u0938\u0940 \u0905\u0938\u094d\u0938\u0940 "
    "\u0907\u0915\u094d\u092f\u093e\u0938\u0940 \u092c\u092f\u093e\u0938\u0940 \u0924\u093f\u0930\u093e\u0938\u0940 \u091a\u094c\u0930\u093e\u0938\u0940 \u092a\u091a\u093e\u0938\u0940 \u091b\u093f\u092f\u093e\u0938\u0940 \u0938\u0924\u094d\u0924\u093e\u0938\u0940 \u0905\u091f\u094d\u0920\u093e\u0938\u0940 \u0928\u0935\u093e\u0938\u0940 \u0928\u092c\u094d\u092c\u0947 "
    "\u0907\u0915\u094d\u092f\u093e\u0928\u0935\u0947 \u092c\u093e\u0928\u0935\u0947 \u0924\u093f\u0930\u093e\u0928\u0935\u0947 \u091a\u094c\u0930\u093e\u0928\u0935\u0947 \u092a\u0902\u091a\u093e\u0928\u0935\u0947 \u091b\u093f\u092f\u093e\u0928\u0935\u0947 \u0938\u0924\u094d\u0924\u093e\u0928\u0935\u0947 \u0905\u091f\u094d\u0920\u093e\u0928\u0935\u0947 \u0928\u093f\u0928\u094d\u092f\u093e\u0928\u0935\u0947 \u0938\u094c "
).split()
_BN_NATIVE = (
    "\u098f\u0995 \u09a6\u09c1\u0987 \u09a4\u09bf\u09a8 \u099a\u09be\u09b0 \u09aa\u09be\u0981\u099a \u099b\u09af\u09bc \u09b8\u09be\u09a4 \u0986\u099f \u09a8\u09af\u09bc \u09a6\u09b6 "
    "\u098f\u0997\u09be\u09b0\u09cb \u09ac\u09be\u09b0\u09cb \u09a4\u09c7\u09b0\u09cb \u099a\u09cb\u09a6\u09cd\u09a6 \u09aa\u09a8\u09c7\u09b0\u09cb \u09b7\u09cb\u09b2\u09cb \u09b8\u09a4\u09c7\u09b0\u09cb \u0986\u09a0\u09be\u09b0\u09cb \u0989\u09a8\u09bf\u09b6 \u0995\u09c1\u09a1\u09bc\u09bf "
    "\u098f\u0995\u09c1\u09b6 \u09ac\u09be\u0987\u09b6 \u09a4\u09c7\u0987\u09b6 \u099a\u09ac\u09cd\u09ac\u09bf\u09b6 \u09aa\u0981\u099a\u09bf\u09b6 \u099b\u09be\u09ac\u09cd\u09ac\u09bf\u09b6 \u09b8\u09be\u09a4\u09be\u09b6 \u0986\u09a0\u09be\u09b6 \u0989\u09a8\u09a4\u09cd\u09b0\u09bf\u09b6 \u09a4\u09bf\u09b0\u09bf\u09b6 "
    "\u098f\u0995\u09a4\u09cd\u09b0\u09bf\u09b6 \u09ac\u09a4\u09cd\u09b0\u09bf\u09b6 \u09a4\u09c7\u09a4\u09cd\u09b0\u09bf\u09b6 \u099a\u09cc\u09a4\u09cd\u09b0\u09bf\u09b6 \u09aa\u0981\u09af\u09bc\u09a4\u09cd\u09b0\u09bf\u09b6 \u099b\u09a4\u09cd\u09b0\u09bf\u09b6 \u09b8\u09be\u0981\u0987\u09a4\u09cd\u09b0\u09bf\u09b6 \u0986\u099f\u09a4\u09cd\u09b0\u09bf\u09b6 \u0989\u09a8\u099a\u09b2\u09cd\u09b2\u09bf\u09b6 \u099a\u09b2\u09cd\u09b2\u09bf\u09b6 "
    "\u098f\u0995\u099a\u09b2\u09cd\u09b2\u09bf\u09b6 \u09ac\u09bf\u09af\u09bc\u09be\u09b2\u09cd\u09b2\u09bf\u09b6 \u09a4\u09c7\u09a4\u09be\u09b2\u09cd\u09b2\u09bf\u09b6 \u099a\u09c1\u09af\u09bc\u09be\u09b2\u09cd\u09b2\u09bf\u09b6 \u09aa\u0981\u09af\u09bc\u09a4\u09be\u09b2\u09cd\u09b2\u09bf\u09b6 \u099b\u09c7\u099a\u09b2\u09cd\u09b2\u09bf\u09b6 \u09b8\u09be\u09a4\u099a\u09b2\u09cd\u09b2\u09bf\u09b6 \u0986\u099f\u099a\u09b2\u09cd\u09b2\u09bf\u09b6 \u0989\u09a8\u09aa\u099e\u09cd\u099a\u09be\u09b6 \u09aa\u099e\u09cd\u099a\u09be\u09b6 "
    "\u098f\u0995\u09be\u09a8\u09cd\u09a8 \u09ac\u09be\u09b9\u09be\u09a8\u09cd\u09a8 \u09a4\u09bf\u09aa\u09cd\u09aa\u09be\u09a8\u09cd\u09a8 \u099a\u09c1\u09af\u09bc\u09be\u09a8\u09cd\u09a8 \u09aa\u099e\u09cd\u099a\u09be\u09a8\u09cd\u09a8 \u099b\u09be\u09aa\u09cd\u09aa\u09be\u09a8\u09cd\u09a8 \u09b8\u09be\u09a4\u09be\u09a8\u09cd\u09a8 \u0986\u099f\u09be\u09a8\u09cd\u09a8 \u0989\u09a8\u09b7\u09be\u099f \u09b7\u09be\u099f "
    "\u098f\u0995\u09b7\u099f\u09cd\u099f\u09bf \u09ac\u09be\u09b7\u099f\u09cd\u099f\u09bf \u09a4\u09c7\u09b7\u099f\u09cd\u099f\u09bf \u099a\u09cc\u09b7\u099f\u09cd\u099f\u09bf \u09aa\u0981\u09af\u09bc\u09b7\u099f\u09cd\u099f\u09bf \u099b\u09c7\u09b7\u099f\u09cd\u099f\u09bf \u09b8\u09be\u09a4\u09b7\u099f\u09cd\u099f\u09bf \u0986\u099f\u09b7\u099f\u09cd\u099f\u09bf \u0989\u09a8\u09b8\u09a4\u09cd\u09a4\u09b0 \u09b8\u09a4\u09cd\u09a4\u09b0 "
    "\u098f\u0995\u09be\u09a4\u09cd\u09a4\u09b0 \u09ac\u09be\u09b9\u09be\u09a4\u09cd\u09a4\u09b0 \u09a4\u09bf\u09af\u09bc\u09be\u09a4\u09cd\u09a4\u09b0 \u099a\u09c1\u09af\u09bc\u09be\u09a4\u09cd\u09a4\u09b0 \u09aa\u0981\u099a\u09be\u09a4\u09cd\u09a4\u09b0 \u099b\u09bf\u09af\u09bc\u09be\u09a4\u09cd\u09a4\u09b0 \u09b8\u09be\u09a4\u09be\u09a4\u09cd\u09a4\u09b0 \u0986\u099f\u09be\u09a4\u09cd\u09a4\u09b0 \u0989\u09a8\u0986\u09b6\u09bf \u0986\u09b6\u09bf "
    "\u098f\u0995\u09be\u09b6\u09bf \u09ac\u09bf\u09b0\u09be\u09b6\u09bf \u09a4\u09bf\u09b0\u09be\u09b6\u09bf \u099a\u09c1\u09b0\u09be\u09b6\u09bf \u09aa\u0981\u099a\u09be\u09b6\u09bf \u099b\u09bf\u09af\u09bc\u09be\u09b6\u09bf \u09b8\u09be\u09a4\u09be\u09b6\u09bf \u0986\u099f\u09be\u09b6\u09bf \u0989\u09a8\u09a8\u09ac\u09cd\u09ac\u0987 \u09a8\u09ac\u09cd\u09ac\u0987 "
    "\u098f\u0995\u09be\u09a8\u09ac\u09cd\u09ac\u0987 \u09ac\u09bf\u09b0\u09be\u09a8\u09ac\u09cd\u09ac\u0987 \u09a4\u09bf\u09b0\u09be\u09a8\u09ac\u09cd\u09ac\u0987 \u099a\u09c1\u09b0\u09be\u09a8\u09ac\u09cd\u09ac\u0987 \u09aa\u0981\u099a\u09be\u09a8\u09ac\u09cd\u09ac\u0987 \u099b\u09bf\u09af\u09bc\u09be\u09a8\u09ac\u09cd\u09ac\u0987 \u09b8\u09be\u09a4\u09be\u09a8\u09ac\u09cd\u09ac\u0987 \u0986\u099f\u09be\u09a8\u09ac\u09cd\u09ac\u0987 \u09a8\u09bf\u09b0\u09be\u09a8\u09ac\u09cd\u09ac\u0987 \u098f\u0995\u09b6\u09cb "
).split()

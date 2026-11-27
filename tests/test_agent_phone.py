"""[R] R4 offline tests: phone_in channel (no screen words, full emergency line, transfer), one re-ask for values that
don't parse, and the Activity-2 prompt-spec fallbacks (yes/no after two misheard turns, reply-language switch after
two turns, direct question on a possibly misheard red-flag word). LLM off. Run: python -m pytest tests -q
"""
from __future__ import annotations

import os
import re

import pytest

os.environ["AGENT_NO_LLM"] = "1"

from agent import core, rules  # noqa: E402
from agent.text import has_indic, light, translit  # noqa: E402


def _start(lang="hi", channel="phone_in"):
    return core.turn({"contract": "1.1", "session_id": "ph", "turn": 0, "event": "start", "state": None,
                      "ui_lang_hint": lang, "channel": channel})


def _say(r, text, lang="hi", channel="phone_in", **tr):
    return core.turn({"contract": "1.1", "session_id": "ph", "turn": r["turn"] + 1, "event": "utterance",
                      "channel": channel, "transcript": {"text": text, "language": lang, **tr}, "state": r["state"]})


def _talk(texts, lang="hi", channel="phone_in"):
    r = _start(lang, channel)
    for t in texts:
        r = _say(r, t, lang, channel)
    return r


# ---------------------------------------------------------------- 1. phone_in channel
_SCREEN = re.compile(r"\b(tap\w*|taip|tyap|screen|skr[ie]+n\w*|button|batan|baatan|botam|botaam|click\w*|klik\w*|"
                     r"see below|below|neeche|niiche|niche|dekhiye|dekhun|tipun|press|display|scroll|type|likhiye|"
                     r"likhun|read)\b")


def test_no_line_refers_to_a_screen_in_any_language():
    bad = []
    for k, v in core.LINES.items():
        if k.startswith("_"):
            continue
        for f, t in v.items():
            if _SCREEN.search(light(translit(t))):
                bad.append((k, f))
    assert bad == []


def test_every_line_has_native_hindi_and_bengali():
    for k, v in core.LINES.items():
        if not k.startswith("_"):
            assert has_indic(v["hi"]) and has_indic(v["bn"]), k
            assert {"en", "hi", "bn", "hi_roman", "bn_roman"} <= set(v), k


@pytest.mark.parametrize("lang,text", [("hi", "seene mein dard hai aur pasina aa raha hai"),
                                       ("bn", "amar buke byatha, ghaam hochhe"),
                                       ("en", "my chest hurts and I am sweating")])
def test_phone_in_emergency_full_line_spoken_and_transferred(lang, text):
    r = _say(_start(lang), text, lang)
    assert r["action"] == "escalate" and r["escalation"]["level"] == "emergency"
    assert r["escalation"]["transfer"] is True and r["escalation"]["call"]["number"] == "112"
    full = core._spell_numbers(core.LINES["esc_emergency_transfer"][lang])
    assert r["say"]["text"] == full == r["escalation"]["message"]  # the whole line, nothing cut or added
    assert "1 1 2" in r["say"]["text"] and "1 1 2" in r["say"]["text_roman"]
    assert r["say"]["interruptible"] is False and r["say"]["pace"] == "slow"
    assert r["expect"]["fillers"] == []


def test_transfer_line_does_not_tell_caller_to_dial_now_but_web_line_unchanged():
    ph = _say(_start("en"), "my chest hurts and I am sweating", "en")
    assert "connecting you" in ph["say"]["text"] and "If the call drops" in ph["say"]["text"]
    assert "Call 112 now" not in ph["say"]["text"]
    web = _say(_start("en", "web"), "my chest hurts and I am sweating", "en", "web")
    assert web["say"]["text"] == core.LINES["esc_emergency"]["en"] and web["escalation"]["transfer"] is False


def test_phone_in_self_harm_transfers_to_tele_manas_with_112_backup():
    r = _say(_start("en"), "I want to end my life", "en")
    assert r["escalation"]["transfer"] is True and r["escalation"]["call"]["number"] == "14416"
    assert r["escalation"]["calls"] == [{"number": "112", "label": "Emergency"}]
    assert "1 4 4 1 6" in r["say"]["text"] and "1 1 2" in r["say"]["text"]


def test_phone_in_urgent_is_not_transferred():
    r = _talk(["chaar din se bukhar hai"])
    assert r["escalation"]["level"] == "urgent" and r["escalation"]["transfer"] is False


def test_phone_in_greeting_and_questions_have_no_screen_words():
    r = _start("hi")
    assert r["state"]["_internal"]["pending"] == "greet_phone"
    for t in ("pet mein dard hai", "do din se", "chaalis saal", "nahi", "nahi", "nahi"):
        r = _say(r, t)
        assert not _SCREEN.search(light(r["say"]["text_roman"]))
    assert r["action"] == "confirm"


# ---------------------------------------------------------------- 2. one re-ask for values that don't parse
def test_unparsed_duration_is_reasked_once_with_examples_then_marked_unclear():
    r = _talk(["sir mein dard hai", "bo binti"])
    assert r["state"]["_internal"]["pending"] == "q_duration_retry" and r["expect"]["kind"] == "duration"
    assert "do din" in r["say"]["text_roman"]
    r = _say(r, "bo binti se")
    st = r["state"]["_internal"]
    assert st["unclear"] == {"duration": "bo binti se"} and r["state"]["_internal"]["pending"] == "q_age_self"
    assert st["reasked"] == ["duration"]


def test_unparsed_age_reask_accepts_a_bare_number():
    r = _talk(["sir mein dard hai", "do din se", "pe pee saal"])
    assert r["state"]["_internal"]["pending"] == "q_age_retry" and r["expect"]["kind"] == "number"
    r = _say(r, "chaalis")
    assert r["state"]["patient"]["age_years"] == 40 and r["state"]["_internal"]["unclear"] == {}


def test_readback_names_unclear_fields_and_a_correction_fills_them():
    r = _talk(["sir mein dard hai", "bo binti", "bo binti se", "pe pee saal", "pe pee", "nahi", "nahi", "nahi"])
    assert r["action"] == "confirm"
    assert r["say"]["text_roman"].endswith(core.LINES["unclear_both"]["hi_roman"])
    assert "Not understood after one re-ask" in r["display"]["summary_clinician"]
    r = _say(r, "pachaas")
    assert r["action"] == "confirm" and r["state"]["patient"]["age_years"] == 50
    assert r["say"]["text_roman"].endswith(core.LINES["unclear_duration"]["hi_roman"])
    r = _say(r, "haan")
    assert r["action"] == "done"


def test_never_more_than_one_reask_per_field():
    r = _talk(["sir mein dard hai", "bo binti", "bo binti se", "pe pee saal", "pe pee", "nahi"])
    asked = r["state"]["_internal"]["asked"]
    assert asked.count("q_duration_retry") == 1 and asked.count("q_age_retry") == 1


def test_no_reask_on_a_red_flag_turn():
    r = _talk(["seene mein dard hai", "pasina aa raha hai"])
    assert r["action"] == "escalate"
    assert r["state"]["_internal"]["reasked"] == [] and "q_duration_retry" not in r["state"]["_internal"]["asked"]


def test_reask_also_works_on_web():
    r = _talk(["sir mein dard hai", "bo binti"], channel="web")
    assert r["state"]["_internal"]["pending"] == "q_duration_retry"


def test_rules_only_correction_at_readback_is_read_back_again():
    r = _talk(["pet mein dard hai", "do din se", "chaalis saal", "nahi", "nahi", "nahi"])
    assert r["action"] == "confirm"
    r = _say(r, "na, teen din se")
    assert r["action"] == "confirm" and r["state"]["symptoms"][0]["duration"] == "3 days"
    assert r["state"]["symptoms"][0]["status"] == "corrected"


# ---------------------------------------------------------------- 3. prompt-spec fallbacks
def test_two_misheard_turns_switch_to_yes_no_and_a_yes_still_escalates():
    r = _say(_start(), "")
    assert r["action"] == "repeat"
    r = _say(r, "")
    assert r["state"]["_internal"]["pending"] == "yn_chest" and r["expect"]["kind"] == "yes_no"
    r = _say(r, "haan")
    assert r["state"]["_internal"]["pending"] == "yn_breath"
    r = _say(r, "haan")
    assert r["action"] == "escalate" and any(f["id"] == "E1_chest_cardiac" for f in r["red_flags"])
    assert "Yes/no answers" in r["display"]["summary_clinician"]


def test_yes_no_mode_runs_to_a_readback_of_the_answers():
    r = _talk(["", "", "nahi", "nahi", "haan", "nahi", "nahi", "nahi", "nahi"])
    assert r["action"] == "confirm" and r["expect"]["kind"] == "yes_no"
    assert core.LINES["rb_over3"]["hi_roman"] in r["say"]["text_roman"]
    assert core.LINES["rb_under60"]["hi_roman"] in r["say"]["text_roman"]
    assert _say(r, "haan")["action"] == "done"


def test_one_misheard_turn_then_a_clear_one_resets_the_count():
    r = _talk(["", "pet mein dard hai", ""])
    assert r["action"] == "repeat" and r["state"]["_internal"]["yn_mode"] is False


def test_low_confidence_garble_counts_as_misheard_but_red_flags_still_win():
    r = _say(_start(), "hmm brr", stt_confidence=0.2)
    assert r["action"] == "repeat"
    r = _say(_start(), "seene mein dard pasina", stt_confidence=0.2)
    assert r["action"] == "escalate"


def test_five_misheard_turns_end_politely():
    r = _talk(["", "", "", "", ""])
    assert r["action"] == "done" and r["state"]["phase"] == "done"


def test_reply_language_switches_only_after_two_turns():
    r = _talk(["pet mein dard hai"])
    r = _say(r, "two days", "en")
    assert r["say"]["language"] == "hi"
    r = _say(r, "I am forty years old", "en")
    assert r["say"]["language"] == "en" and r["state"]["patient"]["age_years"] == 40


def test_first_utterance_sets_the_main_language():
    r = _say(_start("hi"), "amar matha byatha", "bn")
    assert r["say"]["language"] == "bn"


def test_one_turn_back_in_the_main_language_resets_the_switch():
    r = _talk(["pet mein dard hai"])
    r = _say(r, "two days", "en")
    r = _say(r, "chaalis saal", "hi")
    r = _say(r, "no", "en")
    assert r["say"]["language"] == "hi"


def test_possibly_misheard_red_flag_word_is_asked_directly():
    r = _say(_start(), "teene mein dard hai")
    assert r["state"]["_internal"]["pending"] == "yn_chest" and r["action"] == "ask"
    r = _say(r, "haan")
    r = _say(r, "pasina bhi aa raha hai")
    assert r["action"] == "escalate" and any(f["id"] == "E1_chest_cardiac" for f in r["red_flags"])


def test_red_flag_word_only_in_an_alternative_is_asked_directly():
    r = _say(_start(), "pet mein dard hai", alternatives=["seene mein dard hai"])
    assert r["state"]["_internal"]["pending"] == "yn_chest"


def test_near_miss_check_ignores_real_words():
    for t in ("saas ko bukhar hai", "khoob dard hai", "ab jeene ka mann nahi karta", "main theek hoon"):
        assert rules.maybe_flags(t) == set(), t
    assert rules.maybe_flags("khoom aa raha hai") == {"bleeding"}


def test_old_state_without_r4_fields_still_loads():
    r = _start()
    for k in core._r4_defaults():
        r["state"]["_internal"].pop(k)
    r = _say(r, "pet mein dard hai")
    assert r["action"] == "ask"

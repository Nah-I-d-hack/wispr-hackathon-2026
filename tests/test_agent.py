"""[R] Offline tests for the intake agent (R3). No network: the LLM is switched off, so these test the rule layer,
the contract shape and the conversation policy. Run: python -m pytest tests/test_agent.py -q
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ["AGENT_NO_LLM"] = "1"

from agent import core, rules  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _start(lang="hi"):
    return core.turn({"contract": "1.0", "session_id": "t", "turn": 0, "event": "start", "state": None,
                      "ui_lang_hint": lang})


def _say(r, text, i, lang="hi", **extra):
    return core.turn({"contract": "1.0", "session_id": "t", "turn": i, "event": "utterance",
                      "transcript": {"text": text, "language": lang}, "state": r["state"], **extra})


def test_response_has_contract_shape():
    r = _start()
    for k in ("contract", "session_id", "turn", "action", "say", "expect", "state", "red_flags", "escalation",
              "display"):
        assert k in r
    assert r["contract"] == "1.0" and r["action"] == "ask"
    assert set(r["say"]) >= {"text", "language", "script", "text_roman", "register", "pace", "interruptible"}
    assert r["say"]["script"] == "Deva" and r["say"]["text"] != r["say"]["text_roman"]


@pytest.mark.parametrize("bad,field", [({"contract": "2.0", "session_id": "x", "turn": 0, "event": "start"},
                                        "contract"),
                                       ({"contract": "1.0", "turn": 0, "event": "start"}, "session_id"),
                                       ({"contract": "1.0", "session_id": "x", "turn": 0, "event": "nope"}, "event")])
def test_bad_requests_raise_value_error(bad, field):
    with pytest.raises(ValueError, match=field):
        core.turn(bad)


def test_emergency_escalates_not_interruptible_with_112():
    r = _say(_start(), "papa ko chhati mein gas ho rahi hai", 1)
    assert r["action"] == "ask" and "d_I_gas" in r["state"]["_internal"]["asked"]  # idiom question first
    r = _say(r, "haan pasina bhi aa raha hai, 62 saal ke hain", 2)
    assert r["action"] == "escalate"
    assert r["escalation"]["call"]["number"] == "112" and r["say"]["interruptible"] is False
    assert r["say"]["pace"] == "slow"
    assert any(f["id"] == "E1_chest_cardiac" for f in r["red_flags"])
    assert r["display"]["summary_clinician"].startswith("EMERGENCY")


def test_self_harm_points_to_tele_manas():
    r = _say(_start("en"), "I don't want to live anymore, I think about ending my life", 1, lang="en")
    assert r["action"] == "escalate" and r["escalation"]["call"]["number"] == "14416"


def test_hard_negative_gas_after_meal_does_not_escalate():
    r = _start()
    for i, t in enumerate(["gas ho gayi hai, kal shaadi mein bahut kha liya",
                           "pet mein, upar ki taraf. pasina nahi, saans theek hai", "pachchis saal"], 1):
        r = _say(r, t, i)
    assert not [f for f in r["red_flags"] if f["level"] == "emergency"]


def test_native_script_red_flag():
    # "seene mein dard aur pasina" in Devanagari, written as code points
    text = ("सीने में दर्द और "
            "पसीना")
    r = _say(_start(), text, 1)
    assert r["action"] == "escalate"


def test_u3_waits_for_the_follow_up_question():
    r = _say(_start(), "maa ko seene mein gas jaisa lag raha hai, unko sugar hai", 1)
    assert r["action"] == "ask" and "d_I_gas" in r["state"]["_internal"]["asked"]
    r = _say(r, "pata nahi, wo theek se bata nahi pa rahi", 2)
    assert any(f["id"] == "U3_chest_unresolved" for f in r["red_flags"])


def test_full_routine_session_reads_back_then_done():
    r = _start()
    answers = ["teen din se khaansi hai, halki si", "35 saal", "bukhar nahi, saans theek hai", "koi bimari nahi",
               "koi dawai nahi"]
    for i, t in enumerate(answers, 1):
        r = _say(r, t, i)
    assert r["action"] == "confirm" and r["expect"]["kind"] == "yes_no"
    r = _say(r, "haan sahi hai", len(answers) + 1)
    assert r["action"] == "done" and r["state"]["chief_complaint"]["status"] == "confirmed"


def test_three_silences_end_politely():
    r = _start()
    for i in range(1, 4):
        r = core.turn({"contract": "1.0", "session_id": "t", "turn": i, "event": "no_speech", "state": r["state"]})
    assert r["action"] == "done"


def test_rules_catch_every_emergency_in_test_set():
    """Regression gate for the rule layer alone on data/intake_test_v1.jsonl (it was tuned on this set)."""
    for line in (ROOT / "data/intake_test_v1.jsonl").read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        exp = [f for f in c["expect"]["flags"] if f.startswith("E")]
        r = _start(c["lang"])
        got = set()
        for i, t in enumerate(c["turns"], 1):
            r = _say(r, t, i, lang=c["lang"])
            got |= {f["id"] for f in r["red_flags"] if f["level"] == "emergency"}
        if exp:
            assert got, f"{c['id']}: missed emergency"
        for f in c["expect"]["must_not_flag"]:
            assert f not in got, f"{c['id']}: false {f}"


def test_text_never_contains_indic_in_roman_field():
    r = _say(_start("bn"), "amar buke khub byatha, baa haate chhoriye jachhe", 1, lang="bn")
    assert all(ord(ch) < 0x0900 or ord(ch) > 0x09FF for ch in r["say"]["text_roman"])


def test_durations_and_corrections():
    assert rules.latest_duration("nahi nahi, do din nahi, ek hafte se")[0] == 7
    assert rules.latest_duration("I've had fever for four days now")[0] == 4
    assert rules.age("meri maa ko bukhar hai, she is 70") == 70


# ---------------------------------------------------------------- C1 1.1 + K's findings (#44)
def test_c1_v11_phone_channel_and_outbound_greeting():
    r = core.turn({"contract": "1.1", "session_id": "p", "turn": 0, "event": "start", "state": None,
                   "ui_lang_hint": "en", "channel": "phone_out", "context": {"patient_first_name": "Asha"}})
    assert r["contract"] == "1.1" and "Asha" in r["say"]["text"]
    assert len(r["expect"]["fillers"]) == 3 and all("text_roman" in f for f in r["expect"]["fillers"])
    r = core.turn({"contract": "1.1", "session_id": "p", "turn": 1, "event": "utterance", "channel": "phone_out",
                   "transcript": {"text": "my chest feels heavy and I am sweating", "language": "en"},
                   "state": r["state"]})
    assert r["action"] == "escalate" and r["escalation"]["transfer"] is True
    assert "1 1 2" in r["say"]["text"] and r["expect"]["fillers"] == []


def test_c1_v10_client_still_gets_10_and_no_transfer_on_web():
    r = _say(_start("en"), "I want to end my life", 1, lang="en")
    assert r["contract"] == "1.0" and r["escalation"]["transfer"] is False
    assert r["escalation"]["calls"] == [{"number": "112", "label": "Emergency"}]


def test_stt_hints_follow_the_question():
    r = _say(_start(), "khaansi hai", 1)
    assert r["state"]["_internal"]["pending"] == "q_duration" and "din" in r["expect"]["stt_hints"]


def test_k_findings_chaar_is_not_chest_and_bengali_chakkar_gets_its_question():
    r = _say(_start(), "chaar din se bukhar hai", 1)
    assert "chest" not in r["state"]["_internal"]["signs"] and r["state"]["chief_complaint"]["value"] == "fever"
    r = _say(_start("bn"), "amar matha ghorachhe", 1, lang="bn")
    assert "d_I_chakkar" in r["state"]["_internal"]["asked"]
    assert r["state"]["chief_complaint"]["value"] == "dizziness"


def test_fallback_readback_has_no_english():
    r = _start()
    for i, t in enumerate(["pet mein dard hai, teen din se", "45 saal", "nahi", "nahi", "nahi"], 1):
        r = _say(r, t, i)
    assert r["action"] == "confirm"
    assert "days" not in r["say"]["text_roman"] and "45 saal" in r["say"]["text_roman"]

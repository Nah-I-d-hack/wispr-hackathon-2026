"""[R] R4: a spoken correction of "since when" (demo scene 1, docs/round2/DEMO_SCRIPT.md) updates the chief symptom's
duration everywhere: state symptoms[0] (the card), the complaint words on the card, the clinician summary and the next
read-back, and marks it "corrected". Rules only (AGENT_NO_LLM=1), plus one case where the model returns stale fields.
Native-script text is written as escapes. Run: python -m pytest tests -q
"""
from __future__ import annotations

import os

import pytest

os.environ["AGENT_NO_LLM"] = "1"

from agent import core  # noqa: E402
from agent.text import light  # noqa: E402

SCENE_1 = ["maa ko do din se chakkar aa rahe hain, main unki beti bol rahi hoon", "kamra ghoomta hua lagta hai",
           "pachattar saal", "nahi", "nahi", "nahi", "nahi, teen din se", "haan"]
# the same session in Devanagari (as a speech-to-text engine may return it)
_HI_NATIVE = ["माँ को दो दिन से चक्क"
              "र आ रहे हैं, मैं उनकी "
              "बेटी बोल रही हूँ",
              "कमरा घूमता हुआ लगता "
              "है", "पचहत्तर साल",
              "नहीं", "नहीं", "नहीं",
              "नहीं, तीन दिन से", "हाँ"]


def _talk(texts, lang="hi"):
    r = core.turn({"contract": "1.1", "session_id": "fix", "turn": 0, "event": "start", "state": None,
                   "ui_lang_hint": lang, "channel": "web"})
    out = []
    for t in texts:
        r = core.turn({"contract": "1.1", "session_id": "fix", "turn": r["turn"] + 1, "event": "utterance",
                       "channel": "web", "transcript": {"text": t, "language": lang}, "state": r["state"]})
        out.append(r)
    return out


def test_demo_scene_1_correction_reaches_done_with_three_days_corrected():
    rs = _talk(SCENE_1)
    assert [r["action"] for r in rs] == ["ask"] * 5 + ["confirm", "confirm", "done"]
    first, fixed, end = rs[5], rs[6], rs[7]
    assert "do din se chakkar" in first["say"]["text_roman"]
    s0 = first["state"]["symptoms"][0]
    assert (s0["duration"], s0["status"]) == ("2 days", "heard")
    # after "nahi, teen din se": the read-back says three days, and only three days
    rb = fixed["say"]["text_roman"]
    assert "teen din se chakkar" in rb and "do din" not in rb and "75 saal" in rb
    assert fixed["display"]["summary_patient"] and "do din" not in fixed["display"]["summary_patient"]
    for r in (fixed, end):
        st = r["state"]
        s0 = st["symptoms"][0]
        assert (s0["duration"], s0["status"]) == ("3 days", "corrected")
        assert st["chief_complaint"]["status"] == "corrected"
        assert "teen din se" in st["chief_complaint"]["said"] and "do din" not in st["chief_complaint"]["said"]
        assert st["_internal"]["duration_days"] == 3
        s = r["display"]["summary_clinician"]
        assert "for 3 days (corrected by the caller; first said 2 days)" in s and "do din" not in s
    assert end["state"]["phase"] == "done" and end["red_flags"] == []
    assert end["state"]["patient"]["age_years"] == 75
    # the caller's verbatim words stay in the transcript log
    assert any(t["text"] == SCENE_1[0] for t in end["state"]["transcript_log"])


def test_demo_scene_1_in_native_script():
    rs = _talk(_HI_NATIVE)
    assert rs[-1]["action"] == "done"
    fixed = rs[6]
    rb = light(fixed["say"]["text"])
    assert "tiin din se" in rb and "do din" not in rb
    st = rs[-1]["state"]
    assert (st["symptoms"][0]["duration"], st["symptoms"][0]["status"]) == ("3 days", "corrected")
    assert st["speaker"]["role"] == "caregiver" and st["patient"]["sex"] == "female"
    assert st["patient"]["age_years"] == 75


def test_bengali_correction_at_the_read_back():
    rs = _talk(["amar mayer dui din dhore matha ghurchhe, boyos sottor", "ghor ghurchhe mone hoy", "na", "na", "na",
                "na, tin din dhore", "hya"], lang="bn")
    fixed, end = rs[5], rs[6]
    assert fixed["action"] == "confirm"
    rb = fixed["say"]["text_roman"]
    assert "tin din dhore matha" in rb and "dui din" not in rb
    s0 = end["state"]["symptoms"][0]
    assert (s0["duration"], s0["status"]) == ("3 days", "corrected")
    assert end["action"] == "done"


def test_bengali_fever_corrected_to_four_days_escalates_and_still_updates_the_card():
    rs = _talk(["amar mayer teen din dhore jor, boyos sottor", "na", "na", "na", "na, char din dhore", "hya", "hya"],
               lang="bn")
    esc = rs[4]
    assert esc["action"] == "escalate" and esc["escalation"]["level"] == "urgent"
    assert [f["id"] for f in esc["red_flags"]] == ["U1_fever_long_or_high"]  # fever over 3 days (SAFETY.md U1)
    s0 = esc["state"]["symptoms"][0]
    assert (s0["duration"], s0["status"]) == ("4 days", "corrected")
    assert rs[5]["action"] == "confirm" and "char din dhore jor" in rs[5]["say"]["text_roman"]
    assert "teen din" not in rs[5]["say"]["text_roman"]
    assert rs[6]["action"] == "done"


def test_a_duration_without_no_while_collecting_is_not_a_correction():
    rs = _talk(["maa ko do din se chakkar aa rahe hain", "kamra ghoomta hua lagta hai", "pachattar saal",
                "sir dard bhi hai ek hafte se"])
    assert rs[-1]["state"]["symptoms"][0]["status"] == "heard"
    assert rs[-1]["state"]["symptoms"][0]["duration"] == "2 days"


def test_correction_wins_over_stale_model_fields(monkeypatch):
    """With Gemini on, the model may still say 'two days'; the rules' correction and the rules-built read-back win."""
    stale = {"speaker_role": "caregiver", "patient_sex": "female", "patient_age_years": 75,
             "chief_complaint_en": "dizziness", "chief_complaint_said": SCENE_1[0],
             "symptoms": [{"name": "dizziness", "said": SCENE_1[0], "duration": "2 days"}], "conditions": [],
             "medicines_taken": [], "allergies": [], "signs_present": [], "confirmation": "no",
             "out_of_scope_question": False, "summary_patient": "maa ko do din se chakkar",
             "summary_patient_roman": "maa ko do din se chakkar", "danger": "none"}
    rs = _talk(SCENE_1[:6])
    monkeypatch.setattr(core, "_llm_understand", lambda *a: (dict(stale), {"fallback": False}))
    r = core.turn({"contract": "1.1", "session_id": "fix", "turn": 7, "event": "utterance", "channel": "web",
                   "transcript": {"text": "nahi, teen din se", "language": "hi"}, "state": rs[-1]["state"]})
    assert r["action"] == "confirm"
    assert "teen din se" in r["say"]["text_roman"] and "do din" not in r["say"]["text_roman"]
    s0 = r["state"]["symptoms"][0]
    assert (s0["duration"], s0["status"]) == ("3 days", "corrected")

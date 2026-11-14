"""[K] K3: the app backend speaks contract C1 end to end against the mock agent."""
import json

from fastapi.testclient import TestClient

from app.server import app

c = TestClient(app)


def req(sid, turn, event, state, text=None, lang="hi"):
    t = None if text is None else {"text": text, "language": lang, "stt_engine": "typed"}
    return {"contract": "1.0", "session_id": sid, "turn": turn, "event": event, "transcript": t,
            "audio": None, "state": state, "ui_lang_hint": lang}


def run(sid, lang, utterances):
    r = c.post("/v1/turn", json=req(sid, 0, "start", None, lang=lang)).json()
    out = [r]
    for i, u in enumerate(utterances, 1):
        r = c.post("/v1/turn", json=req(sid, i, "utterance", r["state"], u, lang)).json()
        out.append(r)
    return out


def test_health():
    assert c.get("/v1/health").json()["contract"] == "1.0"


def test_happy_path_hindi(tmp_path):
    rs = run("t-happy", "hi", ["pet mein dard hai", "teen din se", "nahi koi nahi", "haan sahi hai"])
    assert [r["action"] for r in rs] == ["ask", "ask", "ask", "confirm", "done"]
    st = rs[-1]["state"]
    assert st["chief_complaint"]["said"] == "pet mein dard hai" and st["chief_complaint"]["status"] == "confirmed"
    assert rs[3]["display"]["summary_patient"].startswith("pet mein dard hai")
    for r in rs:  # contract shape
        assert {"contract", "session_id", "turn", "action", "say", "expect", "state", "red_flags", "escalation", "display"} <= r.keys()
        assert r["say"]["script"] == "Deva"


def test_correction_then_confirm_bengali():
    rs = run("t-fix", "bn", ["মাথা ব্যথা", "দুই দিন", "না", "না", "জ্বর আর মাথা ব্যথা", "হ্যাঁ"])
    assert [r["action"] for r in rs] == ["ask", "ask", "ask", "confirm", "ask", "confirm", "done"]
    assert rs[-1]["state"]["chief_complaint"]["said"] == "জ্বর আর মাথা ব্যথা"


def test_escalation_is_not_interruptible():
    rs = run("t-esc", "hi", ["seene mein dard aur pasina"])
    r = rs[-1]
    assert r["action"] == "escalate" and r["escalation"]["call"]["number"] == "112"
    assert r["say"]["interruptible"] is False and r["say"]["pace"] == "slow"
    assert r["red_flags"][0]["level"] == "emergency"


def test_three_silences_end_politely():
    r = c.post("/v1/turn", json=req("t-quiet", 0, "start", None)).json()
    acts = []
    for i in range(1, 4):
        r = c.post("/v1/turn", json=req("t-quiet", i, "no_speech", r["state"])).json()
        acts.append(r["action"])
    assert acts == ["repeat", "repeat", "done"]


def test_bad_contract_version_is_400():
    bad = req("t-bad", 0, "start", None); bad["contract"] = "2.0"
    assert c.post("/v1/turn", json=bad).status_code == 400


def test_session_is_logged():
    run("t-log", "en", ["headache"])
    from app.server import LOGS
    rows = [json.loads(l) for l in (LOGS / "sessions" / "t-log.jsonl").read_text().splitlines()]
    assert rows[-1]["request"]["transcript"]["text"] == "headache"

"""[K] K3: /api/stt (Wispr mocked, real ffmpeg conversion) and the desk view API."""
import subprocess

import pytest
from fastapi.testclient import TestClient

import app.server as srv

c = TestClient(srv.app)


def _webm_tone(seconds=1.0) -> bytes:
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=300:duration={seconds}",
                        "-c:a", "libopus", "-f", "webm", "pipe:1"], capture_output=True)
    if r.returncode:  # ffmpeg without opus: fall back to wav input
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=duration={seconds}",
                            "-f", "wav", "pipe:1"], capture_output=True)
    return r.stdout


def test_stt_without_key_is_503(monkeypatch):
    monkeypatch.setattr(srv.wispr, "available", lambda: False)
    assert c.post("/api/stt?lang=hi", content=b"x").status_code == 503
    assert c.get("/v1/health").json()["stt"] == "browser"


def test_stt_converts_and_calls_wispr(monkeypatch):
    seen = {}

    def fake(wav, languages, dictionary, conversation):
        seen.update(wav=wav, languages=languages, dictionary=dictionary, conversation=conversation)
        return {"text": "kal se chakkar aa raha hai", "language": "hi", "engine": "wispr-flow-rest-v2",
                "server_ms": 300, "latency_ms": 420, "raw": {}}

    monkeypatch.setattr(srv.wispr, "available", lambda: True)
    monkeypatch.setattr(srv.wispr, "transcribe", fake)
    r = c.post("/api/stt?lang=bn&prompt=Kab%20se%20hai%3F", content=_webm_tone(1.0))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["text"].startswith("kal se") and "raw" not in out
    assert 900 <= out["duration_ms"] <= 1100                      # 1 s tone, resampled to 16 kHz mono
    assert seen["wav"][:4] == b"RIFF" and seen["wav"][24:28] == (16000).to_bytes(4, "little")
    assert seen["languages"] == ["bn", "en"] and "chakkar aana" in seen["dictionary"]
    assert seen["conversation"] == [{"role": "assistant", "content": "Kab se hai?"}]


def test_stt_bad_audio_is_400(monkeypatch):
    monkeypatch.setattr(srv.wispr, "available", lambda: True)
    assert c.post("/api/stt", content=b"not audio at all").status_code == 400


def _turn(sid, turn, event, state, text=None):
    t = None if text is None else {"text": text, "language": "hi", "stt_engine": "typed"}
    return c.post("/v1/turn", json={"contract": "1.0", "session_id": sid, "turn": turn, "event": event,
                                    "transcript": t, "audio": None, "state": state, "ui_lang_hint": "hi"}).json()


def test_desk_puts_emergencies_first_and_ack_works():
    srv.DESK.clear()
    r = _turn("calm-1", 0, "start", None); _turn("calm-1", 1, "utterance", r["state"], "pet mein dard")
    r = _turn("emer-1", 0, "start", None); _turn("emer-1", 1, "utterance", r["state"], "seene mein dard aur pasina")
    rows = c.get("/api/desk").json()["sessions"]
    assert [x["session_id"] for x in rows] == ["emer-1", "calm-1"]
    assert rows[0]["level"] == "emergency" and not rows[0]["acknowledged"] and rows[0]["complaint"]
    assert c.post("/api/desk/emer-1/ack").json()["ok"]
    assert c.get("/api/desk").json()["sessions"][0]["acknowledged"] is True
    assert c.post("/api/desk/nope/ack").status_code == 404
    assert c.get("/desk").status_code == 200

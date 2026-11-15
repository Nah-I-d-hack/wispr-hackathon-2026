"""[K] K4 phone-style call: end-of-speech detection and a full call over the WebSocket (echo STT, mock agent)."""
import array
import math
import os

os.environ["STT_WARMUP"] = "0"
os.environ["STT_ENGINE"] = "echo"

from fastapi.testclient import TestClient  # noqa: E402

from voice.vad import FRAME_BYTES, Endpointer, wav_bytes  # noqa: E402


def tone(ms, amp=6000, f=220):
    n = 16 * ms
    return array.array("h", (int(amp * math.sin(2 * math.pi * f * i / 16000)) for i in range(n))).tobytes()


def silence(ms, amp=40):
    return array.array("h", ((amp if i % 2 else -amp) for i in range(16 * ms))).tobytes()


def frames(pcm):
    return [pcm[i:i + FRAME_BYTES] for i in range(0, len(pcm), FRAME_BYTES)]


def run(ep, pcm):
    out = []
    for f in frames(pcm):
        out += ep.feed(f)
    return out


def test_endpointer_detects_one_utterance():
    ep = Endpointer(silence_ms=1200)
    ev = run(ep, silence(500) + tone(1000) + silence(1400))
    names = [e for e, _ in ev]
    assert names == ["speech_start", "speech_end"]
    pcm = ev[1][1]
    assert 1.0 <= len(pcm) / 32000 <= 1.8          # the speech plus pre-roll and a short tail, not the long pause


def test_short_pause_does_not_end_the_turn():
    ep = Endpointer(silence_ms=1200)
    ev = run(ep, tone(600) + silence(700) + tone(600) + silence(1300))
    assert [e for e, _ in ev] == ["speech_start", "speech_end"]  # an older speaker's mid-sentence pause is kept


def test_no_speech_and_barge_in_threshold():
    assert [e for e, _ in run(Endpointer(no_speech_ms=2000), silence(2100))] == ["no_speech"]
    ep = Endpointer(); ep.barge_in_factor = 2.5
    assert run(ep, silence(400) + tone(400, amp=600)) == []       # quiet echo of Bolo's own voice: ignored
    assert ("speech_start", None) in run(ep, tone(400, amp=8000))  # the caller clearly talking: barge-in


def test_wav_header():
    w = wav_bytes(b"\x00\x00" * 160)
    assert w[:4] == b"RIFF" and w[8:12] == b"WAVE" and len(w) == 44 + 320


def test_full_call_over_websocket(monkeypatch):
    import app.server as srv
    monkeypatch.setattr(srv, "AGENT_URL", "")
    os.environ["ECHO_STT_TEXT"] = "seene mein dard aur pasina"
    c = TestClient(srv.app)
    with c.websocket_connect("/ws/call?lang=hi") as ws:
        assert ws.receive_json()["type"] == "connected"
        greet = ws.receive_json()
        assert greet["type"] == "say" and greet["action"] == "ask"
        ws.send_json({"type": "spoke_start", "id": greet["id"]})
        ws.send_json({"type": "spoke_end", "id": greet["id"]})
        for f in frames(silence(300) + tone(900) + silence(2000)):  # open question -> patience long -> 1.8 s
            ws.send_bytes(f)
        heard = ws.receive_json()
        assert heard["type"] == "heard" and heard["text"] == "seene mein dard aur pasina"
        say = ws.receive_json()
        assert say["action"] == "escalate" and say["interruptible"] is False
        assert say["escalation"]["call"]["number"] == "112"
        ws.send_json({"type": "hangup"})
        end = ws.receive_json()
        assert end["type"] == "end" and end["reason"] == "hangup"
    rows = c.get("/api/desk").json()["sessions"]
    assert any(r["session_id"].startswith("call-") and r["level"] == "emergency" for r in rows)


def test_soft_syllabic_speech_is_still_detected():
    """Regression: a soft voice with gaps between syllables (real FLEURS clip pattern) used to raise the noise floor
    above the voice, so nothing was ever heard."""
    syl = b"".join(tone(140, amp=900) + silence(60, amp=150) for _ in range(20))   # ~4 s, rms ~640 in bursts
    ev = run(Endpointer(silence_ms=1200), silence(1500, amp=150) + syl + silence(1500, amp=150))
    assert [e for e, _ in ev] == ["speech_start", "speech_end"]

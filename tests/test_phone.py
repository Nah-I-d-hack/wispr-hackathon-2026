"""[K] Phone transport: mu-law codec, and a full call over /ws/phone in the Twilio Media Streams protocol
(echo STT, mock agent, a fake TTS so no speech engine is needed)."""
import array
import base64
import math
import os

os.environ["STT_WARMUP"] = "0"
os.environ["STT_ENGINE"] = "echo"

from fastapi.testclient import TestClient  # noqa: E402

from voice import phone, tts  # noqa: E402


def tone16k(ms, amp=6000, f=220):
    return array.array("h", (int(amp * math.sin(2 * math.pi * f * i / 16000)) for i in range(16 * ms))).tobytes()


def silence16k(ms, amp=40):
    return array.array("h", ((amp if i % 2 else -amp) for i in range(16 * ms))).tobytes()


def media(pcm16k):
    ulaw = phone.pcm16k_to_ulaw8k(pcm16k)
    return [{"event": "media", "streamSid": "T", "media": {"payload": base64.b64encode(ulaw[i:i + 160]).decode()}}
            for i in range(0, len(ulaw), 160)]


def test_ulaw_round_trip_keeps_speech_level_audio():
    pcm = tone16k(500, amp=8000, f=440)
    back = phone.ulaw8k_to_pcm16k(phone.pcm16k_to_ulaw8k(pcm))
    assert len(back) == len(pcm)
    a, b = array.array("h"), array.array("h")
    a.frombytes(pcm); b.frombytes(back)
    err = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a))
    assert err < 0.15 * 8000 / math.sqrt(2)   # within telephone quality (~20 dB SNR here)
    assert phone._DECODE[phone._ENCODE[32768]] == 0


def test_canned_line_when_agent_unreachable():
    assert tts.text_for({"text": None, "canned": "offline", "language": "bn"}, "hi").startswith("মাফ")
    assert tts.text_for({"text": "hello"}, "hi") == "hello"


def recv_until(ws, pred, limit=400):
    seen = []
    for _ in range(limit):
        m = ws.receive_json()
        seen.append(m)
        if pred(m):
            return m, seen
    raise AssertionError(f"not seen in {limit} messages: {seen[-5:]}")


def test_phone_call_end_to_end(monkeypatch):
    import app.server as srv
    monkeypatch.setattr(srv, "AGENT_URL", "")
    monkeypatch.setattr(tts, "synth", lambda text, lang="hi", pace="normal": {"pcm": tone16k(300), "engine": "fake",
                                                                           "ms": 0})
    sent = []
    real_turn = srv.agent_turn

    async def spy(req):
        sent.append(req)
        return await real_turn(req)
    monkeypatch.setattr(srv, "agent_turn", spy)
    os.environ["ECHO_STT_TEXT"] = "seene mein dard aur pasina"
    c = TestClient(srv.app)
    with c.websocket_connect("/ws/phone") as ws:
        ws.send_json({"event": "connected"})
        ws.send_json({"event": "start", "streamSid": "T", "start": {"streamSid": "T", "callSid": "CA1",
                                                                     "customParameters": {"lang": "hi"}}})
        # greeting: audio frames, then a mark naming the say id; no debug events without debug=1
        mark, seen = recv_until(ws, lambda m: m["event"] == "mark")
        assert any(m["event"] == "media" and m["streamSid"] == "T" for m in seen)
        assert all(m["event"] in ("media", "mark") for m in seen)
        assert mark["mark"]["name"].startswith("say-")
        ws.send_json({"event": "mark", "streamSid": "T", "mark": mark["mark"]})   # the line finished playing it
        for m in media(silence16k(300) + tone16k(900) + silence16k(2000)):
            ws.send_json(m)
        mark2, _ = recv_until(ws, lambda m: m["event"] == "mark")                 # the escalation, spoken
        ws.send_json({"event": "stop", "streamSid": "T"})
    assert sent[0]["channel"] == "phone_in"                                       # C1 1.1: no screen on a phone
    assert sent[1]["transcript"]["text"] == "seene mein dard aur pasina"
    rows = c.get("/api/desk").json()["sessions"]
    assert any(r["session_id"].startswith("phone-") and r["level"] == "emergency" for r in rows)


def test_barge_in_clears_the_line(monkeypatch):
    import app.server as srv
    monkeypatch.setattr(srv, "AGENT_URL", "")
    monkeypatch.setattr(tts, "synth", lambda text, lang="hi", pace="normal": {"pcm": tone16k(3000), "engine": "fake",
                                                                           "ms": 0})
    c = TestClient(srv.app)
    with c.websocket_connect("/ws/phone") as ws:
        ws.send_json({"event": "start", "streamSid": "T", "start": {"streamSid": "T", "customParameters": {}}})
        recv_until(ws, lambda m: m["event"] == "mark")      # greeting sent, still "playing" (no mark echoed)
        for m in media(tone16k(600, amp=12000)):            # caller talks over it, clearly louder than any echo
            ws.send_json(m)
        clear, _ = recv_until(ws, lambda m: m["event"] == "clear")
        assert clear["streamSid"] == "T"
        ws.send_json({"event": "stop", "streamSid": "T"})

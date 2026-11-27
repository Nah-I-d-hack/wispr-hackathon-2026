"""[K] Phone-call simulator: calls /ws/phone the way a telephony provider would (Twilio Media Streams protocol).

It streams the caller's audio at real-time pace as 8 kHz mu-law (phone quality, so speech-to-text gets what a real
line would deliver), plays Bolo's audio on a simulated line and echoes marks when it would have finished playing,
then answers with the next utterance. No provider account needed.

    # caller lines synthesised with the server's TTS (espeak-ng in Docker) or recorded files, one per turn
    python scripts/phone_sim.py --say "seene mein dard hai" --say "do ghante se"
    python scripts/phone_sim.py --wav rec/turn1.m4a --wav rec/turn2.m4a --lang hi
    # inside Docker:  docker compose exec bolo python scripts/phone_sim.py --say "..."

Writes outputs/phone_sim/<time>/: bolo.wav (what the caller heard), caller.wav (what we sent, at phone quality)
and call.json (every event: what Bolo said, what speech-to-text heard, latency, escalations).
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import subprocess
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from voice import tts  # noqa: E402
from voice.phone import FRAME_8K, PHONE_RATE, pcm16k_to_ulaw8k, ulaw8k_to_pcm16k  # noqa: E402

SILENCE = b"\xff" * FRAME_8K  # mu-law silence, 20 ms


def load_wav(path: str) -> bytes:
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-ar", "16000", "-ac", "1", "-f", "s16le",
                        "pipe:1"], capture_output=True, check=True)
    return r.stdout


def write_wav(path: Path, pcm16k: bytes) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(pcm16k)


class Sim:
    def __init__(self, ws, turns: list[bytes], lang: str, gap_s: float, timeout_s: float):
        self.ws, self.turns, self.lang, self.gap_s, self.timeout_s = ws, list(turns), lang, gap_s, timeout_s
        self.out_q: asyncio.Queue[bytes] = asyncio.Queue()
        self.play_end = 0.0            # when the simulated line finishes playing what Bolo has sent so far
        self.pending: list[asyncio.Task] = []
        self.bolo_audio = bytearray()
        self.caller_audio = bytearray()
        self.events: list[dict] = []
        self.done = asyncio.Event()
        self.last_action = None
        self.t0 = time.monotonic()

    def log(self, kind: str, **kw) -> None:
        row = {"t": round(time.monotonic() - self.t0, 2), "kind": kind, **kw}
        self.events.append(row)
        text = kw.get("text") or kw.get("detail") or ""
        print(f"[{row['t']:6.2f}s] {kind:<10} {text}".rstrip(), flush=True)

    async def send(self, msg: dict) -> None:
        await self.ws.send(json.dumps(msg))

    async def stream_caller(self) -> None:
        """Real-time 20 ms frames: queued speech, else line silence (a phone line never stops sending)."""
        buf, nxt = b"", time.monotonic()
        while not self.done.is_set():
            if not buf and not self.out_q.empty():
                buf = self.out_q.get_nowait()
            frame, buf = (buf[:FRAME_8K], buf[FRAME_8K:]) if buf else (SILENCE, b"")
            frame = frame.ljust(FRAME_8K, b"\xff")
            self.caller_audio += frame
            await self.send({"event": "media", "streamSid": "SIM", "media": {"payload": base64.b64encode(frame).decode()}})
            nxt += 0.02
            await asyncio.sleep(max(0.0, nxt - time.monotonic()))

    def say_next(self) -> None:
        if not self.turns:
            return
        pcm = self.turns.pop(0)
        self.log("caller", text=f"speaks turn ({len(pcm) / 32000:.1f}s audio)")
        self.out_q.put_nowait(pcm16k_to_ulaw8k(pcm))

    async def echo_mark(self, name: str, at: float) -> None:
        await asyncio.sleep(max(0.0, at - time.monotonic()))
        await self.send({"event": "mark", "streamSid": "SIM", "mark": {"name": name}})
        if name.startswith("say-") and self.last_action not in ("done",):
            if self.turns:
                await asyncio.sleep(self.gap_s)
                self.say_next()
            elif self.last_action == "escalate":
                self.log("caller", text="(no more turns after the escalation; hanging up)")
                await self.hangup()
            else:
                self.log("caller", text="(no more turns; waiting for Bolo to finish)")

    async def hangup(self) -> None:
        if not self.done.is_set():
            await self.send({"event": "stop", "streamSid": "SIM"})
            self.done.set()

    async def receive(self) -> None:
        async for raw in self.ws:
            msg = json.loads(raw)
            ev = msg.get("event")
            if ev == "media":
                ulaw = base64.b64decode(msg["media"]["payload"])
                self.bolo_audio += ulaw8k_to_pcm16k(ulaw)
                self.play_end = max(self.play_end, time.monotonic()) + len(ulaw) / PHONE_RATE
            elif ev == "mark":
                self.pending.append(asyncio.create_task(self.echo_mark(msg["mark"]["name"], self.play_end)))
            elif ev == "clear":
                self.log("clear", detail="Bolo stopped talking (barge-in)")
                self.play_end = time.monotonic()
            elif ev == "bolo":
                d = msg["data"]
                t = d.get("type")
                if t == "say":
                    self.last_action = d.get("action")
                    esc = d.get("escalation") or {}
                    self.log("bolo", text=f"[{d.get('action')}] {tts.text_for(d, self.lang)}",
                             escalation=esc.get("level"), transfer=esc.get("transfer"))
                elif t == "heard":
                    self.log("heard", text=f"{d.get('text')!r} ({d.get('engine')}, {d.get('stt_ms')} ms, "
                                         f"confidence {d.get('confidence')})", confidence=d.get("confidence"))
                elif t == "metric":
                    self.log("latency", text=f"end of speech -> Bolo's reply sent: {d.get('end_to_voice_ms')} ms")
                elif t == "filler":
                    self.log("filler", text=d.get("text"))
                elif t == "end":
                    self.log("end", text=d.get("reason"))
                    await asyncio.sleep(max(0.0, self.play_end - time.monotonic()))
                    self.done.set()
                    return
                elif t == "state":
                    self.log("state", text=f"{d.get('state')} {d.get('detail') or ''}")

    async def run(self) -> None:
        await self.send({"event": "connected", "protocol": "Call", "version": "1.0.0"})
        await self.send({"event": "start", "streamSid": "SIM", "start": {
            "streamSid": "SIM", "callSid": f"SIM-{int(time.time())}", "tracks": ["inbound"],
            "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1},
            "customParameters": {"lang": self.lang, "debug": "1"}}})
        tasks = [asyncio.create_task(self.stream_caller()), asyncio.create_task(self.receive())]
        try:
            await asyncio.wait_for(self.done.wait(), self.timeout_s)
        except asyncio.TimeoutError:
            self.log("timeout", text=f"no end after {self.timeout_s:.0f}s; hanging up")
            await self.hangup()
        for t in tasks + self.pending:
            t.cancel()


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="ws://localhost:8000/ws/phone")
    ap.add_argument("--lang", default="hi", choices=["hi", "bn", "en"])
    ap.add_argument("--say", action="append", default=[], help="caller turn as text, spoken with the server TTS")
    ap.add_argument("--wav", action="append", default=[], help="caller turn as an audio file (any format ffmpeg reads)")
    ap.add_argument("--gap", type=float, default=0.6, help="seconds the caller waits after Bolo finishes")
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--out", default=str(ROOT / "outputs" / "phone_sim"))
    a = ap.parse_args()
    turns = [load_wav(p) for p in a.wav] + [tts.synth(t, a.lang, "normal")["pcm"] for t in a.say]
    if not turns:
        ap.error("give at least one --say or --wav")
    turns = [t + b"\x00\x00" * 16000 * 2 for t in turns]  # 2 s of silence after each turn so end-of-speech fires
    from websockets.asyncio.client import connect
    async with connect(a.url, max_size=None) as ws:
        sim = Sim(ws, turns, a.lang, a.gap, a.timeout)
        await sim.run()
    out = Path(a.out) / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    write_wav(out / "bolo.wav", bytes(sim.bolo_audio))
    write_wav(out / "caller.wav", ulaw8k_to_pcm16k(bytes(sim.caller_audio)))
    (out / "call.json").write_text(json.dumps({"url": a.url, "lang": a.lang, "say": a.say, "wav": a.wav,
                                               "tts": tts.engine_name(), "events": sim.events},
                                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[K] wrote {out}")


if __name__ == "__main__":
    asyncio.run(main())

"""[K] One phone-style call: audio in -> end-of-speech -> STT -> intake agent (C1) -> speech out, with barge-in.

Transport-agnostic. The transport (browser WebSocket now, a telephony media stream later) does three things:
  - feeds 20 ms PCM16 16 kHz frames to `on_audio`
  - forwards control messages to `on_message` ({"type": "spoke_start"|"spoke_end", "id"}, {"type": "hangup"})
  - delivers what `send` emits: {"type": "say"|"stop"|"filler"|"state"|"end", ...}
Speech out is "say" text for now (the browser speaks it). A server TTS engine (K2) will turn it into audio frames,
which telephony needs, without changing this loop.
"""
from __future__ import annotations

import asyncio
import itertools
import os
import time
from typing import Awaitable, Callable

from . import stt as stt_mod
from .vad import Endpointer, rms

DEBUG = os.environ.get("CALL_DEBUG") == "1"

Send = Callable[[dict], Awaitable[None]]
AgentTurn = Callable[[dict], Awaitable[dict]]
_ids = itertools.count(1)


class CallSession:
    BARGE_IN_FACTOR = 2.5  # while Bolo speaks, the caller must be clearly louder than the echo to interrupt
    FILLER_AFTER_S = 0.9   # if the agent hasn't answered by then, play a short acknowledgement (R's lines)

    def __init__(self, session_id: str, send: Send, agent_turn: AgentTurn, lang: str = "hi", channel: str = "web",
                 stt_fn=None, hints: list[str] | None = None, fillers: dict[str, list[str]] | None = None):
        self.sid, self.send, self.agent_turn, self.lang, self.channel = session_id, send, agent_turn, lang, channel
        self.stt_fn = stt_fn or stt_mod.stt
        self.hints, self.fillers = hints or [], fillers or {}
        self.ep = Endpointer()
        self.state = "connecting"   # connecting | speaking | listening | thinking | ended
        self.turn, self.agent_state, self.last = 0, None, None
        self.speaking_id: int | None = None
        self.barge_in = False
        self.t_speech_end = 0.0
        self.metrics: list[dict] = []
        self._task: asyncio.Task | None = None
        self._dbg_n, self._dbg_max = 0, 0.0

    # ---------- lifecycle ----------
    async def start(self) -> None:
        await self._agent("start")

    async def on_audio(self, frame: bytes) -> None:
        if DEBUG:
            self._dbg_n += 1; self._dbg_max = max(self._dbg_max, rms(frame))
            if self._dbg_n % 50 == 0:
                print(f"[call {self.sid}] {self._dbg_n} frames, {len(frame)} B, max rms {self._dbg_max:.0f}, "
                      f"thr {self.ep.threshold:.0f}, state {self.state}", flush=True)
                self._dbg_max = 0.0
        if self.state not in ("listening", "speaking"):
            return
        for ev, pcm in self.ep.feed(frame):
            if ev == "speech_start" and self.state == "speaking":
                if self.last and self.last["say"].get("interruptible", True):
                    self.barge_in = True
                    await self.send({"type": "stop", "id": self.speaking_id})
                    self._listen(keep_buffer=True)
            elif ev == "speech_end" and self.state == "listening":
                self.t_speech_end = time.perf_counter()
                self._spawn(self._utterance(pcm))
            elif ev == "no_speech" and self.state == "listening":
                self._spawn(self._agent("no_speech"))

    async def on_message(self, msg: dict) -> None:
        t = msg.get("type")
        if t == "spoke_start" and msg.get("id") == self.speaking_id and self.t_speech_end:
            ms = round((time.perf_counter() - self.t_speech_end) * 1000)
            self.metrics.append({"turn": self.turn, "end_to_voice_ms": ms})
            await self.send({"type": "metric", "end_to_voice_ms": ms})
            self.t_speech_end = 0.0
        elif t == "spoke_end" and msg.get("id") == self.speaking_id and self.state == "speaking":
            if self.last and self.last["action"] == "done":
                await self._end("done")
            else:
                self._listen()
        elif t == "hangup":
            if self.state != "ended":
                await self._agent("end", final=True)
                await self._end("hangup")

    # ---------- internals ----------
    def _spawn(self, coro) -> None:
        self.state = "thinking"
        self._task = asyncio.create_task(coro)

    def _listen(self, keep_buffer: bool = False) -> None:
        self.state = "listening"
        self.ep.barge_in_factor = 1.0
        patience = (self.last or {}).get("expect", {}).get("patience", "normal")
        self.ep.silence_ms = 1800 if patience == "long" else 1200
        if not keep_buffer:
            self.ep.reset()
        self.speaking_id = None

    async def _utterance(self, pcm: bytes) -> None:
        if DEBUG:
            from .vad import wav_bytes
            os.makedirs("outputs/call_debug", exist_ok=True)
            with open(f"outputs/call_debug/{self.sid}-{self.turn}.wav", "wb") as f:
                f.write(wav_bytes(pcm))
        prompt = (self.last or {}).get("say", {}).get("text", "")
        hints = self.hints + list((self.last or {}).get("expect", {}).get("stt_hints", []) or [])
        try:
            out = await asyncio.to_thread(self.stt_fn, pcm, self.lang, hints, prompt)
        except Exception as e:  # STT down: ask again rather than guess
            await self.send({"type": "state", "state": "stt_error", "detail": type(e).__name__})
            out = {"text": "", "language": self.lang, "engine": "error"}
        text = (out.get("text") or "").strip()
        await self.send({"type": "heard", "text": text, "engine": out.get("engine"), "stt_ms": out.get("latency_ms"),
                        "confidence": out.get("confidence")})
        lang = out.get("language") if out.get("language") in ("hi", "bn", "en") else self.lang
        transcript = {"text": text, "language": lang, "mixed_with": [],
                      "language_confidence": out.get("language_confidence"),
                      "stt_confidence": out.get("confidence"), "alternatives": out.get("alternatives") or [],
                      "stt_engine": out.get("engine", "unknown"),
                      "barge_in": self.barge_in}
        self.barge_in = False
        await self._agent("utterance", transcript, {"duration_ms": out.get("duration_ms"), "truncated": False})

    async def _agent(self, event: str, transcript: dict | None = None, audio: dict | None = None,
                     final: bool = False) -> None:
        self.state = "thinking"
        req = {"contract": "1.0", "session_id": self.sid, "turn": self.turn, "event": event, "transcript": transcript,
               "audio": audio, "state": self.agent_state, "ui_lang_hint": self.lang,
               "client": {"app": f"k4-call-{self.channel}", "version": "0.1"},
               # C1 1.1: a call has no screen to rely on, so the agent uses its listening-only lines (ignored by 1.0)
               "channel": "web" if self.channel == "chat" else "phone_in"}
        call = asyncio.create_task(self.agent_turn(req))
        done, _ = await asyncio.wait({call}, timeout=self.FILLER_AFTER_S)
        if not done and not final:
            filler = self._filler()
            if filler:
                await self.send({"type": "filler", "text": filler, "language": self.lang})
        try:
            resp = await call
        except Exception as e:  # agent unreachable: our own canned line, keep the state (C1 section 9)
            await self.send({"type": "state", "state": "agent_error", "detail": type(e).__name__})
            if final:
                return
            self.last = {"say": {"interruptible": True}, "expect": {"patience": "normal"}, "action": "repeat"}
            await self._say({"text": None, "language": self.lang, "canned": "offline", "interruptible": True,
                             "pace": "normal"}, "repeat", None)
            return
        self.turn += 1
        self.agent_state, self.last = resp["state"], resp
        if final:
            return
        await self._say(resp["say"], resp["action"], resp)

    def _filler(self) -> str | None:
        """C1 1.1: the agent's own `expect.fillers` for this turn first, then R's lines file. Never after an escalation."""
        if self.last and self.last.get("action") == "escalate":
            return None
        opts = [f.get("text") for f in ((self.last or {}).get("expect", {}).get("fillers") or []) if f.get("text")]
        opts = opts or self.fillers.get(self.lang, [])
        return opts[self.turn % len(opts)] if opts else None

    async def _say(self, say: dict, action: str, resp: dict | None) -> None:
        self.speaking_id = next(_ids)
        self.state = "speaking"
        self.ep.reset()
        self.ep.barge_in_factor = self.BARGE_IN_FACTOR
        msg = {"type": "say", "id": self.speaking_id, "action": action, **say}
        if resp:
            msg.update(escalation=resp.get("escalation"), display=resp.get("display"),
                       intake={"phase": resp["state"].get("phase"),
                               "complaint": (resp["state"].get("chief_complaint") or {}).get("said")})
        await self.send(msg)

    async def _end(self, reason: str) -> None:
        self.state = "ended"
        await self.send({"type": "end", "reason": reason, "metrics": self.metrics})

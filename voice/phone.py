"""[K] Phone transport for the call loop: a telephony media stream <-> CallSession.

Speaks the Twilio Media Streams WebSocket protocol, which other providers (Exotel, Plivo, Vonage, Telnyx) mirror
closely, so a real number later needs only a thin adapter, not changes to the call loop or the agent:

  provider -> us   {"event": "connected"} · {"event": "start", "start": {"streamSid", "callSid", "customParameters"}}
                   {"event": "media", "media": {"payload": <base64 8 kHz mu-law, 20 ms>}}
                   {"event": "mark", "mark": {"name"}}   (echoed when our audio up to that mark finished playing)
                   {"event": "dtmf", "dtmf": {"digit"}} · {"event": "stop"}
  us -> provider   {"event": "media", "streamSid", "media": {"payload"}} · {"event": "mark", "streamSid", "mark"}
                   {"event": "clear", "streamSid"}       (drop queued audio: the caller interrupted)

The phone has no screen and doesn't report playback, so this bridge does what the browser did for the call screen:
turns `say` text into audio (voice/tts.py), reports spoke_start when the audio is sent and spoke_end when the
provider echoes our mark, and clears the line on barge-in. With customParameters.debug = "1" it also sends
{"event": "bolo", "data": <call event>} so a simulator can show transcripts; real providers never set it.
"""
from __future__ import annotations

import array
import asyncio
import base64
from typing import Awaitable, Callable

from . import tts

PHONE_RATE = 8000
FRAME_8K = 160  # 20 ms of mu-law at 8 kHz = 160 bytes

# ---------- G.711 mu-law <-> PCM16 (pure Python; audioop is gone in Python 3.13) ----------
_BIAS, _CLIP = 0x84, 32635


def _ulaw_decode_byte(u: int) -> int:
    u = ~u & 0xFF
    sign, exp, mant = u & 0x80, (u >> 4) & 0x07, u & 0x0F
    x = (((mant << 3) + _BIAS) << exp) - _BIAS
    return -x if sign else x


_DECODE = [_ulaw_decode_byte(i) for i in range(256)]


def _ulaw_encode_sample(s: int) -> int:
    sign = 0x80 if s < 0 else 0
    s = min(abs(s), _CLIP) + _BIAS
    exp, mask = 7, 0x4000
    while exp > 0 and not s & mask:
        exp, mask = exp - 1, mask >> 1
    mant = (s >> (exp + 3)) & 0x0F
    return ~(sign | (exp << 4) | mant) & 0xFF


_ENCODE = bytes(_ulaw_encode_sample(s - 32768) for s in range(65536))


def ulaw8k_to_pcm16k(data: bytes) -> bytes:
    """8 kHz mu-law -> 16 kHz PCM16 (decode, then linear interpolation)."""
    s = [_DECODE[b] for b in data]
    out = array.array("h")
    for i, x in enumerate(s):
        nxt = s[i + 1] if i + 1 < len(s) else x
        out.append(x)
        out.append((x + nxt) // 2)
    return out.tobytes()


def pcm16k_to_ulaw8k(pcm: bytes) -> bytes:
    """16 kHz PCM16 -> 8 kHz mu-law (average pairs as a crude low-pass, then encode)."""
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) - len(pcm) % 4])
    return bytes(_ENCODE[((a[i] + a[i + 1]) >> 1) + 32768] for i in range(0, len(a) - 1, 2))


# ---------- bridge ----------
SendJSON = Callable[[dict], Awaitable[None]]


class PhoneBridge:
    """One phone call: feed it the provider's JSON messages; it drives a CallSession and answers the provider."""

    def __init__(self, send_json: SendJSON, make_call: Callable[..., "object"]):
        self.send_json, self.make_call = send_json, make_call
        self.call = None
        self.stream_sid: str | None = None
        self.call_sid: str | None = None
        self.debug = False
        self.lang = "hi"
        self.transfers: list[dict] = []   # escalations with C1 `transfer`: a real provider would bridge to the number
        self._play_lock = asyncio.Lock()

    async def on_provider(self, msg: dict) -> None:
        ev = msg.get("event")
        if ev == "start":
            st = msg.get("start") or {}
            self.stream_sid, self.call_sid = st.get("streamSid") or msg.get("streamSid"), st.get("callSid")
            params = st.get("customParameters") or {}
            self.debug = str(params.get("debug", "")) == "1"
            self.lang = params.get("lang") if params.get("lang") in ("hi", "bn", "en") else "hi"
            self.call = self.make_call(self._on_call_event, self.lang)
            await self.call.start()
        elif ev == "media" and self.call:
            payload = (msg.get("media") or {}).get("payload")
            if payload:
                await self.call.on_audio(ulaw8k_to_pcm16k(base64.b64decode(payload)))
        elif ev == "mark" and self.call:
            name = (msg.get("mark") or {}).get("name", "")
            if name.startswith("say-"):
                await self.call.on_message({"type": "spoke_end", "id": int(name[4:])})
        elif ev == "dtmf" and self.call:
            await self._debug({"type": "dtmf", "digit": (msg.get("dtmf") or {}).get("digit")})
        elif ev == "stop" and self.call:
            await self.call.on_message({"type": "hangup"})

    async def _on_call_event(self, ev: dict) -> None:
        """What CallSession emits for the browser, turned into phone audio and marks."""
        t = ev.get("type")
        await self._debug(ev)
        if t == "say":
            await self._play(tts.text_for(ev, self.lang), ev.get("language") or self.lang, ev.get("pace", "normal"),
                             mark=f"say-{ev['id']}", speak_id=ev["id"])
            esc = ev.get("escalation") or {}
            if esc.get("transfer"):
                self.transfers.append({"to": (esc.get("call") or {}).get("number"), "level": esc.get("level")})
        elif t == "filler":
            await self._play(ev.get("text", ""), ev.get("language") or self.lang, "normal", cache=True)
        elif t == "stop":
            await self.send_json({"event": "clear", "streamSid": self.stream_sid})

    async def _play(self, text: str, lang: str, pace: str, mark: str | None = None, speak_id: int | None = None,
                    cache: bool = False) -> None:
        async with self._play_lock:
            try:
                pcm = (await asyncio.to_thread(tts.cached, text, lang, pace)) if cache else \
                    (await asyncio.to_thread(tts.synth, text, lang, pace))["pcm"]
            except Exception as e:  # no TTS: keep the call moving rather than hang on silence
                await self._debug({"type": "state", "state": "tts_error", "detail": f"{type(e).__name__}: {e}"})
                pcm = b""
            ulaw = await asyncio.to_thread(pcm16k_to_ulaw8k, pcm)
            if speak_id is not None:
                await self.call.on_message({"type": "spoke_start", "id": speak_id})
            # one message per second of audio keeps frames small; providers buffer and play in order
            for i in range(0, len(ulaw), PHONE_RATE):
                await self.send_json({"event": "media", "streamSid": self.stream_sid,
                                      "media": {"payload": base64.b64encode(ulaw[i:i + PHONE_RATE]).decode()}})
            if mark:
                await self.send_json({"event": "mark", "streamSid": self.stream_sid, "mark": {"name": mark}})

    async def _debug(self, data: dict) -> None:
        if self.debug:
            await self.send_json({"event": "bolo", "data": data})

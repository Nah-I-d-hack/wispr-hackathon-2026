"""[K] Server-side end-of-speech detection for calls (16 kHz mono PCM16, 20 ms frames).

Same logic for the browser call and, later, a telephony stream (8 kHz audio gets resampled to 16 kHz first).
Energy-based with an adaptive noise floor: cheap, no model, good enough to decide "the caller has finished".

    ep = Endpointer()
    for frame in frames:              # 640 bytes = 20 ms
        for ev in ep.feed(frame):     # ("speech_start", None) | ("speech_end", pcm_bytes) | ("no_speech", None)
            ...
"""
from __future__ import annotations

import array
import math

RATE = 16000
FRAME_MS = 20
FRAME_BYTES = RATE * FRAME_MS // 1000 * 2  # 640


def rms(frame: bytes) -> float:
    a = array.array("h")
    a.frombytes(frame[: len(frame) - len(frame) % 2])
    if not a:
        return 0.0
    return math.sqrt(sum(x * x for x in a) / len(a))


class Endpointer:
    """Turns a stream of frames into speech_start / speech_end / no_speech events.

    silence_ms: pause that ends a turn (longer when the agent expects a long answer, see C1 expect.patience).
    Older speakers pause more (docs/RESEARCH.md section 6), so defaults lean long.
    """

    def __init__(self, silence_ms: int = 1200, start_ms: int = 160, no_speech_ms: int = 8000, max_ms: int = 30000,
                 min_level: float = 300.0, ratio: float = 3.0, preroll_ms: int = 300):
        self.silence_ms, self.start_ms, self.no_speech_ms, self.max_ms = silence_ms, start_ms, no_speech_ms, max_ms
        self.min_level, self.ratio, self.preroll_ms = min_level, ratio, preroll_ms
        self.noise = min_level / ratio
        self.barge_in_factor = 1.0
        self.reset()

    def reset(self) -> None:
        self.in_speech = False
        self.loud_ms = self.quiet_ms = self.waited_ms = self.speech_ms = 0
        self.buf = bytearray()
        self.pre: list[bytes] = []

    @property
    def threshold(self) -> float:
        return max(self.min_level, self.noise * self.ratio) * self.barge_in_factor

    def feed(self, frame: bytes) -> list[tuple[str, bytes | None]]:
        level = rms(frame)
        voiced = level > self.threshold
        # Noise floor: falls fast, rises very slowly (~10 s), and never learns from voiced frames. Otherwise the
        # quiet gaps between syllables pull it up until it sits above a soft voice and nothing is "heard".
        if level < self.noise:
            self.noise = 0.9 * self.noise + 0.1 * level
        elif not voiced and not self.in_speech:
            self.noise = 0.998 * self.noise + 0.002 * level
        ev: list[tuple[str, bytes | None]] = []
        if not self.in_speech:
            self.waited_ms += FRAME_MS
            self.pre.append(frame)
            self.pre = self.pre[-(self.preroll_ms // FRAME_MS):]
            # tolerate short dips between syllables while deciding that speech has started
            self.loud_ms = self.loud_ms + FRAME_MS if voiced else max(0, self.loud_ms - FRAME_MS // 2)
            if self.loud_ms >= self.start_ms:
                self.in_speech, self.quiet_ms, self.speech_ms = True, 0, self.loud_ms
                self.buf = bytearray(b"".join(self.pre))
                ev.append(("speech_start", None))
            elif self.waited_ms >= self.no_speech_ms:
                self.reset()
                ev.append(("no_speech", None))
            return ev
        self.buf += frame
        self.speech_ms += FRAME_MS
        self.quiet_ms = 0 if voiced else self.quiet_ms + FRAME_MS
        if self.quiet_ms >= self.silence_ms or self.speech_ms >= self.max_ms:
            pcm = bytes(self.buf[: len(self.buf) - (self.quiet_ms // FRAME_MS) * FRAME_BYTES + 10 * FRAME_BYTES])
            self.reset()
            ev.append(("speech_end", pcm))
        return ev


def wav_bytes(pcm: bytes, rate: int = RATE) -> bytes:
    """Wrap raw mono PCM16 in a WAV header."""
    import struct
    return (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " +
            struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) + b"data" + struct.pack("<I", len(pcm)) + pcm)

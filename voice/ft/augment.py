"""[K] K6: audio augmentation for the speech fine-tune (#101): older-voice and channel transforms.

Every transform is mild and randomised, and returns the parameters it used so the dataset manifest records them.
They approximate older voices; they cannot fake slurred articulation, dentures or dialect. Real recordings stay the
final test (ship rule in #101).

    from voice.ft.augment import augment
    pcm16k, params = augment(pcm16k, rng=random.Random(7))           # random older-voice + channel mix
    pcm16k, params = augment(pcm16k, rng, older=False, phone=True)    # channel only

Older voice (each applied with some probability):
  - rate       slower speech, time-stretch 0.75-0.9x (ffmpeg atempo: tempo without pitch change)
  - pauses     longer gaps between words: quiet stretches lengthened 1.3-2x
  - pitch      +-2 semitones (with age, men's voices tend to rise and women's to fall)
  - tremor     4-7 Hz wobble in pitch (vibrato) and loudness (tremolo)
  - breathy    weaker high frequencies (low-pass 3-4.5 kHz) plus low-level noise
Channel:
  - noise      pink noise, or a noise file (e.g. OPD babble), at 8-25 dB SNR
  - reverb     a small room (ffmpeg aecho)
  - phone      8 kHz mu-law round trip (voice/phone.py), as a real phone line delivers it
"""
from __future__ import annotations

import random
import subprocess

import numpy as np

from ..phone import pcm16k_to_ulaw8k, ulaw8k_to_pcm16k

RATE = 16000


def _ffmpeg(pcm: bytes, filters: list[str]) -> bytes:
    if not filters:
        return pcm
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", str(RATE), "-ac", "1", "-i", "pipe:0",
                        "-af", ",".join(filters), "-ar", str(RATE), "-ac", "1", "-f", "s16le", "pipe:1"],
                       input=pcm, capture_output=True, check=True, timeout=60)
    return r.stdout


def _to_f(pcm: bytes) -> np.ndarray:
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def _to_pcm(x: np.ndarray) -> bytes:
    return (np.clip(x, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()


def lengthen_pauses(x: np.ndarray, factor: float, win_ms: int = 30, quiet_db: float = -35.0) -> np.ndarray:
    """Stretch quiet stretches (between words) by `factor` by repeating their frames; speech is untouched."""
    w = RATE * win_ms // 1000
    n = len(x) // w
    if n == 0:
        return x
    frames = x[: n * w].reshape(n, w)
    level = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)
    peak = level.max()
    out, carry = [], 0.0
    for f, lv in zip(frames, level):
        out.append(f)
        if lv < peak + quiet_db:            # relative to the clip's loudest window
            carry += factor - 1.0
            while carry >= 1.0:
                out.append(f)
                carry -= 1.0
    return np.concatenate(out + [x[n * w:]])


def pink_noise(n: int, rng: np.random.Generator) -> np.ndarray:
    white = rng.standard_normal(n)
    spec = np.fft.rfft(white)
    spec /= np.sqrt(np.maximum(np.arange(len(spec)), 1))
    p = np.fft.irfft(spec, n)
    return p / (np.abs(p).max() + 1e-9)


def add_noise(x: np.ndarray, snr_db: float, rng: np.random.Generator, noise: np.ndarray | None = None) -> np.ndarray:
    if noise is None or len(noise) == 0:
        noise = pink_noise(len(x), rng)
    elif len(noise) < len(x):
        noise = np.tile(noise, len(x) // len(noise) + 1)
    if len(noise) > len(x):
        start = int(rng.integers(0, len(noise) - len(x) + 1))
        noise = noise[start:start + len(x)]
    ps, pn = float((x ** 2).mean()) + 1e-12, float((noise ** 2).mean()) + 1e-12
    return x + noise * np.sqrt(ps / (pn * 10 ** (snr_db / 10)))


def augment(pcm: bytes, rng: random.Random, older: bool = True, channel: bool = True, phone: bool | None = None,
            noise_clip: np.ndarray | None = None) -> tuple[bytes, dict]:
    """pcm: 16 kHz mono PCM16 bytes. Returns (augmented pcm, params). phone=None means a 50% chance."""
    p: dict = {}
    filters: list[str] = []
    if older:
        if rng.random() < 0.7:
            p["rate"] = round(rng.uniform(0.75, 0.9), 3)
            filters.append(f"atempo={p['rate']}")
        if rng.random() < 0.6:
            p["pitch_semitones"] = round(rng.uniform(-2.0, 2.0), 2)
            r = 2 ** (p["pitch_semitones"] / 12)
            filters += [f"asetrate={RATE * r:.1f}", f"aresample={RATE}", f"atempo={1 / r:.5f}"]
        if rng.random() < 0.5:
            p["tremor_hz"] = round(rng.uniform(4.0, 7.0), 2)
            p["tremor_depth"] = round(rng.uniform(0.02, 0.06), 3)
            filters += [f"vibrato=f={p['tremor_hz']}:d={p['tremor_depth']}",
                        f"tremolo=f={p['tremor_hz']}:d={min(0.3, p['tremor_depth'] * 4):.3f}"]
        if rng.random() < 0.5:
            p["lowpass_hz"] = rng.randrange(3000, 4501, 100)
            filters.append(f"lowpass=f={p['lowpass_hz']}")
    if channel and rng.random() < 0.4:
        p["reverb"] = True
        filters.append("aecho=0.8:0.6:40|70:0.25|0.15")
    x = _to_f(_ffmpeg(pcm, filters))
    nrng = np.random.default_rng(rng.randrange(2 ** 32))
    if older and rng.random() < 0.6:
        p["pause_factor"] = round(rng.uniform(1.3, 2.0), 2)
        x = lengthen_pauses(x, p["pause_factor"])
    if older and "lowpass_hz" in p:                   # breathiness: a little noise riding on the voice
        x = add_noise(x, 30.0, nrng)
    if channel and rng.random() < 0.7:
        p["snr_db"] = round(rng.uniform(8.0, 25.0), 1)
        p["noise"] = "file" if noise_clip is not None else "pink"
        x = add_noise(x, p["snr_db"], nrng, noise_clip)
    peak = float(np.abs(x).max()) or 1.0
    x = x * min(1.0, 0.95 / peak)                     # no clipping
    out = _to_pcm(x)
    if channel and (phone if phone is not None else rng.random() < 0.5):
        p["phone"] = True
        out = ulaw8k_to_pcm16k(pcm16k_to_ulaw8k(out))
    return out, p

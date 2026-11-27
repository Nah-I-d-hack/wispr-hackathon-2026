"""[K] K6: augmentation keeps audio valid, records its parameters, and is reproducible per seed."""
import random

import numpy as np

from voice.ft.augment import augment, lengthen_pauses


def clip():
    t = np.arange(8000) / 16000
    word = 0.4 * np.sin(2 * np.pi * 180 * t) * np.hanning(len(t))
    gap = np.zeros(4800)
    return (np.concatenate([gap, word, gap, word, gap]) * 32767).astype(np.int16).tobytes()


def test_reproducible_and_recorded():
    a, pa = augment(clip(), random.Random(4))
    b, pb = augment(clip(), random.Random(4))
    assert a == b and pa == pb
    assert pa and all(k in ("rate", "pitch_semitones", "tremor_hz", "tremor_depth", "lowpass_hz", "reverb",
                            "pause_factor", "snr_db", "noise", "phone") for k in pa)


def test_valid_audio_no_clipping():
    for seed in range(8):
        out, p = augment(clip(), random.Random(seed))
        x = np.frombuffer(out, dtype=np.int16)
        assert len(out) % 2 == 0 and len(x) > 16000          # still at least 1 s of 16 kHz audio
        assert np.abs(x).max() < 32767                       # normalised, never clipped
        if "rate" in p:
            assert len(x) > len(clip()) // 2                 # slower speech is longer


def test_pauses_lengthen_only_quiet_parts():
    x = np.frombuffer(clip(), dtype=np.int16).astype(np.float32) / 32768
    y = lengthen_pauses(x, 2.0)
    assert len(y) > len(x) * 1.3
    assert np.isclose(np.abs(y).max(), np.abs(x).max())     # speech untouched


def test_channel_only_keeps_older_voice_off():
    _, p = augment(clip(), random.Random(1), older=False, phone=True)
    assert p.get("phone") is True and not ({"rate", "pitch_semitones", "tremor_hz", "pause_factor"} & p.keys())

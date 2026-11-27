"""[K] Speech-to-text engines behind one function: stt(pcm16k, lang, hints, prompt) -> {"text", "language", "engine", "latency_ms"}.

    STT_ENGINE=indicconformer  AI4Bharat IndicConformer 600M multilingual, CTC (default; MIT; gated on HF: needs a token
                         that accepted the terms). INDIC_DECODER=ctc|rnnt, INDIC_REVISION=<commit> to pin
    STT_ENGINE=whisper   local faster-whisper, last-resort fallback (loops on imperfect audio, ~50% WER on Hindi)
    STT_ENGINE=wispr     Wispr Flow REST (needs WISPR_API_KEY; API isn't public, kept for completeness)
    STT_ENGINE=echo      tests only

K2 adds more (Sarvam, Eka Parrotlet, Bhashini) behind the same signature and picks one by measurement.
"""
from __future__ import annotations

import math
import os
import time
from functools import lru_cache

from .vad import RATE, wav_bytes

WHISPER_LANG = {"hi": "hi", "bn": "bn", "en": "en"}


INDIC_MODEL = "ai4bharat/indic-conformer-600m-multilingual"


@lru_cache(maxsize=1)
def _indic():
    from transformers import AutoModel
    # trust_remote_code is the model card's documented loading path (ONNX graphs + a small wrapper from AI4Bharat).
    return AutoModel.from_pretrained(INDIC_MODEL, trust_remote_code=True, revision=os.environ.get("INDIC_REVISION"))


def _indic_stt(pcm: bytes, lang: str, hints: list[str], prompt: str) -> dict:
    import torch
    wav = torch.frombuffer(bytearray(pcm), dtype=torch.int16).float().div_(32768.0).unsqueeze(0)
    text = _indic()(wav, lang if lang in ("hi", "bn") else "hi", os.environ.get("INDIC_DECODER", "ctc"))
    # CTC can't take phrase hints; the agent's read-back and stt_hints-aware engines (Wispr, Sarvam) cover that.
    return {"text": (text or "").strip(), "language": lang}


@lru_cache(maxsize=1)
def _whisper():
    from faster_whisper import WhisperModel
    return WhisperModel(os.environ.get("WHISPER_MODEL", "small"), device=os.environ.get("WHISPER_DEVICE", "cpu"),
                        compute_type=os.environ.get("WHISPER_COMPUTE", "int8"))


def warm_up() -> None:
    {"whisper": _whisper, "indicconformer": _indic}.get(engine_name(), lambda: None)()


def _whisper_stt(pcm: bytes, lang: str, hints: list[str], prompt: str) -> dict:
    import array
    a = array.array("h"); a.frombytes(pcm)
    audio = [x / 32768.0 for x in a]
    try:
        import numpy as np
        audio = np.asarray(audio, dtype=np.float32)
    except ImportError:
        pass
    # initial_prompt biases decoding towards the agent's question and the symptom phrases (Whisper's "hints").
    ip = " ".join(([prompt] if prompt else []) + hints[:40])[:800] or None
    secs = len(audio) / RATE
    # temperature 0 only (no fallback re-decodes) and a token cap tied to the audio length: Whisper otherwise
    # loops on imperfect audio, which cost 27 s and an empty transcript on a 4 s call turn.
    segs, info = _whisper().transcribe(audio, language=WHISPER_LANG.get(lang), beam_size=1, vad_filter=False,
                                       initial_prompt=ip, condition_on_previous_text=False, temperature=0.0,
                                       max_new_tokens=min(220, int(secs * 18) + 16))
    segs = list(segs)
    text = " ".join(s.text.strip() for s in segs).strip()
    return {"text": text, "language": info.language or lang, **_whisper_confidence(segs, info)}


def _whisper_confidence(segs, info) -> dict:
    """C1 stt_confidence: exp of the token-weighted mean log-probability, lowered by the no-speech probability.
    Whisper gives no n-best list at beam 1, so `alternatives` stays empty."""
    if not segs:
        return {"confidence": 0.0, "language_confidence": getattr(info, "language_probability", None)}
    n = [max(1, len(getattr(s, "tokens", []) or [])) for s in segs]
    lp = sum(s.avg_logprob * k for s, k in zip(segs, n)) / sum(n)
    speech = 1.0 - max(s.no_speech_prob for s in segs)
    return {"confidence": round(max(0.0, min(1.0, math.exp(lp) * speech)), 3),
            "language_confidence": round(getattr(info, "language_probability", 0.0) or 0.0, 3)}


def _wispr_stt(pcm: bytes, lang: str, hints: list[str], prompt: str) -> dict:
    from . import wispr
    out = wispr.transcribe(wav_bytes(pcm), {"hi": ["hi", "en"], "bn": ["bn", "en"]}.get(lang, ["en", "hi", "bn"]),
                           hints, [{"role": "assistant", "content": prompt}] if prompt else None)
    return {"text": out["text"], "language": out["language"]}


def _echo_stt(pcm: bytes, lang: str, hints: list[str], prompt: str) -> dict:
    return {"text": os.environ.get("ECHO_STT_TEXT", "test"), "language": lang}


ENGINES = {"indicconformer": _indic_stt, "whisper": _whisper_stt, "wispr": _wispr_stt, "echo": _echo_stt}


def engine_name() -> str:
    """STT_ENGINE if set; otherwise IndicConformer when its dependencies are installed, else Whisper (no key)."""
    name = os.environ.get("STT_ENGINE")
    if name:
        return name
    import importlib.util
    return "indicconformer" if importlib.util.find_spec("transformers") and importlib.util.find_spec("torch") \
        else "whisper"


def stt(pcm: bytes, lang: str, hints: list[str] | None = None, prompt: str = "") -> dict:
    name = engine_name()
    t0 = time.perf_counter()
    out = ENGINES[name](pcm, lang, hints or [], prompt)
    label = {"whisper": f"whisper-{os.environ.get('WHISPER_MODEL', 'small')}",
             "indicconformer": f"indicconformer-600m-{os.environ.get('INDIC_DECODER', 'ctc')}"}.get(name, name)
    out.update(engine=label,
               latency_ms=round((time.perf_counter() - t0) * 1000), duration_ms=round(len(pcm) / (RATE * 2) * 1000))
    return out

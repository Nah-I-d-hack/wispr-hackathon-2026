"""[K] Server-side text-to-speech: reply text -> 16 kHz mono PCM16, for callers with no browser (phone lines).

The browser screens keep speaking with the browser's own voices; calls over a phone stream need audio from us.

Engines (TTS_ENGINE, default: google if GOOGLE_TTS_API_KEY is set, else espeak if installed, else none):
  google  Google Cloud Text-to-Speech REST API (hi-IN, bn-IN, en-IN voices). Needs GOOGLE_TTS_API_KEY.
  espeak  espeak-ng, local and free, robotic but intelligible; the no-key fallback (installed in the Docker image).
  none    no audio; callers of `synth` get TTSUnavailable and must degrade (the phone bridge skips the audio).
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import time
import urllib.request
from functools import lru_cache

RATE = 16000
GOOGLE_LANG = {"hi": "hi-IN", "bn": "bn-IN", "en": "en-IN"}
ESPEAK_VOICE = {"hi": "hi", "bn": "bn", "en": "en-us"}

# Spoken when the agent can't be reached (C1 section 9); the browser screens have the same lines in app.js.
CANNED = {
    "offline": {
        "hi": "माफ़ कीजिए, अभी जुड़ नहीं पा रहे। फिर से बोलिए।",
        "bn": "মাফ করবেন, এখন সংযোগ হচ্ছে না। আবার বলুন।",
        "en": "Sorry, I can't connect right now. Please say that again.",
    },
}


class TTSUnavailable(RuntimeError):
    pass


def engine_name() -> str:
    name = os.environ.get("TTS_ENGINE")
    if name:
        return name
    if os.environ.get("GOOGLE_TTS_API_KEY"):
        return "google"
    return "espeak" if shutil.which("espeak-ng") else "none"


def text_for(say: dict, lang: str) -> str:
    """The words to speak for a C1 `say` block (or our canned line when the agent was unreachable)."""
    if say.get("text"):
        return say["text"]
    canned = CANNED.get(say.get("canned") or "", {})
    return canned.get(say.get("language") or lang) or canned.get("en", "")


def synth(text: str, lang: str = "hi", pace: str = "normal") -> dict:
    """-> {"pcm": bytes (16 kHz mono PCM16), "engine": str, "ms": synthesis time}. Raises TTSUnavailable."""
    text = (text or "").strip()
    if not text:
        return {"pcm": b"", "engine": "none", "ms": 0}
    name = engine_name()
    fn = {"google": _google, "espeak": _espeak}.get(name)
    if fn is None:
        raise TTSUnavailable(f"no text-to-speech engine ({name}); set GOOGLE_TTS_API_KEY or install espeak-ng")
    t0 = time.perf_counter()
    pcm = fn(text, lang if lang in GOOGLE_LANG else "hi", pace)
    return {"pcm": pcm, "engine": name, "ms": round((time.perf_counter() - t0) * 1000)}


def _google(text: str, lang: str, pace: str) -> bytes:
    key = os.environ.get("GOOGLE_TTS_API_KEY")
    if not key:
        raise TTSUnavailable("GOOGLE_TTS_API_KEY not set")
    body = {"input": {"text": text}, "voice": {"languageCode": GOOGLE_LANG[lang]},
            "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": RATE,
                            "speakingRate": 0.85 if pace == "slow" else 1.0}}
    req = urllib.request.Request(f"https://texttospeech.googleapis.com/v1/text:synthesize?key={key}",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        wav = base64.b64decode(json.loads(r.read())["audioContent"])
    return _strip_wav(wav)


def _espeak(text: str, lang: str, pace: str) -> bytes:
    if not shutil.which("espeak-ng"):
        raise TTSUnavailable("espeak-ng not installed")
    speed = "130" if pace == "slow" else "155"
    wav = subprocess.run(["espeak-ng", "-v", ESPEAK_VOICE[lang], "-s", speed, "--stdout", text],
                         capture_output=True, timeout=15, check=True).stdout
    return _resample_wav(wav)


def _resample_wav(wav: bytes) -> bytes:
    """Any WAV -> 16 kHz mono PCM16 via ffmpeg (already needed for /api/stt)."""
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ar", str(RATE), "-ac", "1", "-f", "s16le",
                        "pipe:1"], input=wav, capture_output=True, timeout=15, check=True)
    return r.stdout


def _strip_wav(wav: bytes) -> bytes:
    """LINEAR16 responses are a WAV file; return the PCM data chunk."""
    i = wav.find(b"data")
    return wav[i + 8:] if wav[:4] == b"RIFF" and i >= 0 else wav


@lru_cache(maxsize=256)
def cached(text: str, lang: str, pace: str) -> bytes:
    """Fillers and canned lines repeat across calls; cache their audio."""
    return synth(text, lang, pace)["pcm"]

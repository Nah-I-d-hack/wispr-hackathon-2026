"""[K] Wispr Flow speech-to-text client (REST v2, api-docs.wisprflow.ai, rest_api_v2.yaml).

    from voice.wispr import transcribe
    out = transcribe(wav_16k_pcm16_bytes, languages=["hi", "en"], dictionary=[...], conversation=[...])
    out -> {"text", "language", "engine", "server_ms", "latency_ms", "raw"}

The key comes from env WISPR_API_KEY (put it in the gitignored .env). The API takes base64 16 kHz PCM16 WAV, at most
25 MB (about 6 minutes). Wispr can't be fine-tuned; `dictionary` and `conversation` are the only per-request levers.
"""
from __future__ import annotations

import base64
import os
import time

import httpx

URL = os.environ.get("WISPR_URL", "https://platform-api.wisprflow.ai/api/v1/dash/api")
ENGINE = "wispr-flow-rest-v2"


def load_env(path: str = ".env") -> None:
    """Minimal .env reader so scripts work without python-dotenv. Never prints values."""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def available() -> bool:
    load_env()
    return bool(os.environ.get("WISPR_API_KEY"))


def build_request(wav: bytes, languages: list[str] | None = None, dictionary: list[str] | None = None,
                  conversation: list[dict] | None = None) -> dict:
    ctx: dict = {"app": {"type": "ai"}}
    if dictionary:
        ctx["dictionary_context"] = list(dict.fromkeys(dictionary))
    if conversation:
        ctx["conversation"] = {"id": "bolo", "participants": ["patient", "bolo"],
                               "messages": [{"role": m["role"], "content": m["content"]} for m in conversation]}
    return {"audio": base64.b64encode(wav).decode("ascii"), "language": languages or [], "context": ctx}


def transcribe(wav: bytes, languages: list[str] | None = None, dictionary: list[str] | None = None,
               conversation: list[dict] | None = None, timeout: float = 15.0) -> dict:
    load_env()
    key = os.environ.get("WISPR_API_KEY")
    if not key:
        raise RuntimeError("WISPR_API_KEY not set (add it to .env)")
    body = build_request(wav, languages, dictionary, conversation)
    t0 = time.perf_counter()
    r = httpx.post(URL, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=timeout)
    ms = round((time.perf_counter() - t0) * 1000)
    if r.status_code != 200:
        raise RuntimeError(f"wispr HTTP {r.status_code}: {r.text[:200]}")
    j = r.json()
    return {"text": j.get("text", ""), "language": j.get("detected_language") or "und", "engine": ENGINE,
            "server_ms": j.get("total_time"), "latency_ms": ms, "raw": {k: j.get(k) for k in ("id", "generated_tokens")}}

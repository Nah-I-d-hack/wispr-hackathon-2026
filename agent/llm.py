"""[R] Minimal Gemini client (stdlib only). Key from env GEMINI_API_KEY or the repo's .env. Never logs the key."""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite")
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMError(RuntimeError):
    pass


# Optional pacing for batch runs on a rate-limited key: AGENT_LLM_MIN_INTERVAL seconds between request starts.
_lock = threading.Lock()
_next_slot = [0.0]


def _pace() -> float:
    gap = float(os.environ.get("AGENT_LLM_MIN_INTERVAL", "0") or 0)
    if gap <= 0:
        return 0.0
    with _lock:
        now = time.monotonic()
        start = max(now, _next_slot[0])
        _next_slot[0] = start + gap
    wait = start - now
    if wait > 0:
        time.sleep(wait)
    return wait


def _key() -> str | None:
    k = os.environ.get("GEMINI_API_KEY")
    if k:
        return k
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


def available() -> bool:
    return os.environ.get("AGENT_NO_LLM") != "1" and _key() is not None


def generate_json(prompt: str, *, system: str | None = None, schema: dict | None = None, model: str | None = None,
                  timeout: float = 4.0, retries: int = 1, temperature: float = 0.0) -> tuple[dict, dict]:
    """Return (parsed JSON, meta {model, ms}). Raises LLMError on failure."""
    key = _key()
    if not key:
        raise LLMError("no GEMINI_API_KEY")
    cfg: dict = {"responseMimeType": "application/json", "temperature": temperature}
    if schema:
        cfg["responseSchema"] = schema
    body: dict = {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": cfg}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    models = [model or DEFAULT_MODEL, FALLBACK_MODEL]
    last = ""
    waited = 0.0
    for attempt in range(retries + 1):
        m = models[min(attempt, len(models) - 1)]
        waited += _pace()
        t0 = time.perf_counter()
        try:
            req = urllib.request.Request(URL.format(model=m) + f"?key={key}", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.load(r)
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]
                           if not p.get("thought"))
            return json.loads(text), {"model": m, "ms": round((time.perf_counter() - t0) * 1000),
                                      "wait_ms": round(waited * 1000)}
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code == 429:
                s = min(20, 4 * (attempt + 1))
                time.sleep(s)
                waited += s
        except Exception as e:  # timeout, bad JSON, empty candidates
            last = type(e).__name__
    err = LLMError(last)
    err.wait_ms = round(waited * 1000)
    raise err

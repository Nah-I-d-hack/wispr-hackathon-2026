"""[K] K3 backend: serves the voice app and forwards each turn to the intake agent (contract C1).

    uv venv -p 3.12 && uv pip install -r app/requirements.txt
    uvicorn app.server:app --reload --port 8000          # mock agent
    AGENT_URL=http://localhost:9000 uvicorn app.server:app # R's agent over HTTP (POST {AGENT_URL}/v1/turn)

Every request/response pair is appended to outputs/sessions/<session_id>.jsonl (contract §11), so a session can be
replayed through the real agent later. Timing from the browser (end of speech -> reply audio starts) goes to
outputs/metrics.jsonl.

Speech-to-text: with WISPR_API_KEY in .env the app records audio and posts it to /api/stt, which converts it to
16 kHz PCM16 WAV (ffmpeg) and calls Wispr Flow with the symptom vocabulary (voice/vocab.py) and the agent's last
question as context. Without a key, /v1/health says stt=browser and the app uses the browser's own recognition.
The desk view (/desk.html) shows live sessions, emergencies first ("flags the desk").
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from voice import stt as stt_mod
from voice import vocab, wispr
from voice import tts
from voice.call import CallSession
from voice.phone import PhoneBridge

from . import mock_agent

ROOT = Path(__file__).resolve().parents[1]
WEB = Path(__file__).resolve().parent / "web"
LOGS = Path(os.environ.get("K3_LOG_DIR", ROOT / "outputs"))
AGENT_URL = os.environ.get("AGENT_URL", "").rstrip("/")
AGENT_TIMEOUT_S = float(os.environ.get("AGENT_TIMEOUT_S", "5"))

app = FastAPI(title="voice intake (K3)")
LANG_HINTS = {"hi": ["hi", "en"], "bn": ["bn", "en"], "en": ["en", "hi", "bn"]}
VOCAB = vocab.symptom_phrases()
DESK: dict[str, dict] = {}  # session_id -> latest summary for the desk view (in memory; demo scale)


def _log(name: str, row: dict) -> None:
    p = LOGS / name
    try:  # logging must never break a turn (read-only or unwritable disk, e.g. a container mount)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[K] log write failed ({name}): {e}", flush=True)


@app.get("/v1/health")
async def health() -> dict:
    """What is running, and which optional keys are missing (the app works without any of them)."""
    llm = None
    if AGENT_URL:
        try:
            async with httpx.AsyncClient(timeout=1.5) as c:
                llm = (await c.get(f"{AGENT_URL}/v1/health")).json().get("llm")
        except (httpx.HTTPError, ValueError):
            llm = None
    missing = [k for k, ok in (("WISPR_API_KEY", wispr.available()), ("GEMINI_API_KEY", llm is not False)) if not ok]
    return {"ok": True, "contract": mock_agent.CONTRACT, "agent": AGENT_URL or "mock",
            "stt": "wispr" if wispr.available() else "browser", "call_stt": stt_mod.engine_name(), "phone_tts": tts.engine_name(), "llm": llm,
            "keys_missing": missing}


class AgentBadRequest(Exception):
    def __init__(self, body: dict):
        self.body = body


async def agent_turn(req: dict) -> dict:
    """One C1 turn against R's agent (AGENT_URL) or the mock; logs it and updates the desk. Shared by chat and calls."""
    sid = str(req.get("session_id", "nosession")).replace("/", "_")[:64]
    t0 = time.perf_counter()
    if AGENT_URL:
        async with httpx.AsyncClient(timeout=AGENT_TIMEOUT_S) as c:
            r = await c.post(f"{AGENT_URL}/v1/turn", json=req)
        if r.status_code == 400:
            raise AgentBadRequest(r.json())
        r.raise_for_status()
        resp = r.json()
    else:
        try:
            resp = mock_agent.turn(req)
        except ValueError as e:
            raise AgentBadRequest({"error": str(e), "field": "contract"})
    ms = round((time.perf_counter() - t0) * 1000)
    _log(f"sessions/{sid}.jsonl", {"t": time.time(), "agent_ms": ms, "request": req, "response": resp})
    _desk_update(sid, req, resp)
    return resp


@app.post("/v1/turn")
async def turn(request: Request) -> JSONResponse:
    req = await request.json()
    t0 = time.perf_counter()
    try:
        resp = await agent_turn(req)
    except AgentBadRequest as e:
        return JSONResponse(e.body, status_code=400)
    except (httpx.HTTPError, KeyError) as e:
        # The app speaks its own canned line and keeps the last state (contract §9).
        raise HTTPException(status_code=502, detail=f"agent unavailable: {type(e).__name__}")
    return JSONResponse(resp, headers={"X-Agent-Ms": str(round((time.perf_counter() - t0) * 1000))})


def _fillers() -> dict[str, list[str]]:
    """Short acknowledgements from R's agent/lines.json (key 'filler' or 'fillers'), if R has added them."""
    try:
        lines = json.loads((ROOT / "agent" / "lines.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    f = lines.get("fillers") or lines.get("filler") or {}
    return {k: (v if isinstance(v, list) else [v]) for k, v in f.items() if k in ("hi", "bn", "en") and v}


@app.websocket("/ws/call")
async def call_ws(ws: WebSocket, lang: str = "hi") -> None:
    """Browser call: binary frames = 20 ms PCM16 16 kHz mic audio; text frames = JSON control messages."""
    await ws.accept()
    sid = f"call-{uuid.uuid4().hex[:12]}"
    lock = asyncio.Lock()

    async def send(msg: dict) -> None:
        async with lock:
            await ws.send_json(msg)

    call = CallSession(sid, send, agent_turn, lang=lang if lang in ("hi", "bn", "en") else "hi", channel="web",
                       hints=VOCAB, fillers=_fillers())
    await send({"type": "connected", "session_id": sid, "stt": stt_mod.engine_name(), "agent": AGENT_URL or "mock"})
    await call.start()
    try:
        while call.state != "ended":
            m = await ws.receive()
            if m["type"] == "websocket.disconnect":
                break
            if m.get("bytes"):
                await call.on_audio(m["bytes"])
            elif m.get("text"):
                await call.on_message(json.loads(m["text"]))
    except WebSocketDisconnect:
        pass
    finally:
        if call.state != "ended":
            call.state = "ended"  # caller dropped; nothing to say
        _log("calls.jsonl", {"t": time.time(), "session_id": sid, "turns": call.turn, "metrics": call.metrics})
        try:
            await ws.close()
        except RuntimeError:
            pass


@app.websocket("/ws/phone")
async def phone_ws(ws: WebSocket) -> None:
    """Telephony media stream (Twilio Media Streams protocol; see voice/phone.py). Point a provider's stream here,
    or run scripts/phone_sim.py to call it with recorded or synthetic speech."""
    await ws.accept()
    sid = f"phone-{uuid.uuid4().hex[:12]}"
    lock = asyncio.Lock()

    async def send_json(msg: dict) -> None:
        async with lock:
            await ws.send_json(msg)

    def make_call(send, lang):
        return CallSession(sid, send, agent_turn, lang=lang, channel="phone", hints=VOCAB, fillers=_fillers())

    bridge = PhoneBridge(send_json, make_call)
    try:
        while not (bridge.call and bridge.call.state == "ended"):
            m = await ws.receive()
            if m["type"] == "websocket.disconnect":
                break
            if m.get("text"):
                await bridge.on_provider(json.loads(m["text"]))
    except WebSocketDisconnect:
        pass
    finally:
        call = bridge.call
        if call and call.state != "ended":
            call.state = "ended"
        _log("calls.jsonl", {"t": time.time(), "session_id": sid, "channel": "phone", "call_sid": bridge.call_sid,
                             "turns": call.turn if call else 0, "metrics": call.metrics if call else [],
                             "transfers": bridge.transfers})
        try:
            await ws.close()
        except RuntimeError:
            pass


def _desk_update(sid: str, req: dict, resp: dict) -> None:
    st = resp.get("state") or {}
    flags = resp.get("red_flags") or []
    prev = DESK.get(sid, {})
    esc = resp.get("escalation") or prev.get("escalation")
    DESK[sid] = {
        "session_id": sid, "updated": time.time(), "started": prev.get("started", time.time()),
        "turns": resp.get("turn", 0), "action": resp.get("action"), "phase": st.get("phase"),
        "lang": (st.get("lang") or {}).get("reply"), "complaint": (st.get("chief_complaint") or {}).get("said"),
        "speaker": (st.get("speaker") or {}).get("role"), "red_flags": flags,
        "level": "emergency" if any(f.get("level") == "emergency" for f in flags) else
                 ("urgent" if flags else None),
        "escalation": esc, "summary": (resp.get("display") or {}).get("summary_clinician"),
        "acknowledged": prev.get("acknowledged", False) and not (resp.get("escalation") and not prev.get("escalation")),
    }


@app.get("/api/desk")
def desk() -> dict:
    rank = {"emergency": 0, "urgent": 1, None: 2}
    rows = sorted(DESK.values(), key=lambda d: (rank[d["level"]], d["acknowledged"], -d["updated"]))
    return {"sessions": rows[:50], "now": time.time()}


@app.post("/api/desk/{sid}/ack")
def desk_ack(sid: str) -> dict:
    if sid not in DESK:
        raise HTTPException(404, "unknown session")
    DESK[sid]["acknowledged"] = True
    return {"ok": True}


def to_wav16k(audio: bytes) -> bytes:
    """Any browser recording (webm/opus, ogg, mp4, wav) -> 16 kHz mono PCM16 WAV, as Wispr expects."""
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", "16000",
                        "-acodec", "pcm_s16le", "-f", "wav", "pipe:1"], input=audio, capture_output=True, timeout=20)
    if r.returncode != 0 or len(r.stdout) <= 44:
        raise ValueError("could not decode audio")
    return r.stdout


@app.post("/api/stt")
async def stt(request: Request, lang: str = "hi", prompt: str = "") -> JSONResponse:
    if not wispr.available():
        return JSONResponse({"error": "no WISPR_API_KEY; use browser speech recognition"}, status_code=503)
    audio = await request.body()
    if not audio or len(audio) > 20_000_000:
        return JSONResponse({"error": "empty or too large"}, status_code=400)
    try:
        wav = await asyncio.to_thread(to_wav16k, audio)
    except (ValueError, subprocess.TimeoutExpired) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    convo = [{"role": "assistant", "content": prompt[:500]}] if prompt else None
    try:
        out = await asyncio.to_thread(wispr.transcribe, wav, LANG_HINTS.get(lang, []), VOCAB, convo)
    except Exception as e:  # network, auth, quota: the app falls back to browser STT
        return JSONResponse({"error": f"wispr failed: {type(e).__name__}"}, status_code=502)
    out["duration_ms"] = round((len(wav) - 44) / 32)  # 16 kHz * 2 bytes = 32 bytes per ms
    out.pop("raw", None)
    _log("stt.jsonl", {"t": time.time(), "lang_hint": lang, **out})
    return JSONResponse(out)


@app.post("/api/metrics")
async def metrics(request: Request) -> dict:
    row = await request.json()
    _log("metrics.jsonl", {"t": time.time(), **{k: row[k] for k in list(row)[:20]}})
    return {"ok": True}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.on_event("startup")
async def _warm() -> None:
    if os.environ.get("STT_WARMUP", "1") == "1":
        asyncio.get_running_loop().run_in_executor(None, stt_mod.warm_up)


@app.get("/lines")
def lines_page() -> FileResponse:
    """Listen-check of the agent's spoken lines (K's task for R's new lines)."""
    return FileResponse(WEB / "lines.html")


@app.get("/api/lines")
def lines_json() -> JSONResponse:
    try:
        return JSONResponse(json.loads((ROOT / "agent" / "lines.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return JSONResponse({}, status_code=404)


@app.get("/call")
def call_page() -> FileResponse:
    return FileResponse(WEB / "call.html")


@app.get("/desk")
def desk_page() -> FileResponse:
    return FileResponse(WEB / "desk.html")


app.mount("/", StaticFiles(directory=WEB), name="web")

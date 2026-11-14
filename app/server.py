"""[K] K3 backend: serves the voice app and forwards each turn to the intake agent (contract C1).

    uv venv -p 3.12 && uv pip install -r app/requirements.txt
    uvicorn app.server:app --reload --port 8000          # mock agent
    AGENT_URL=http://localhost:9000 uvicorn app.server:app # R's agent over HTTP (POST {AGENT_URL}/v1/turn)

Every request/response pair is appended to outputs/sessions/<session_id>.jsonl (contract §11), so a session can be
replayed through the real agent later. Timing from the browser (end of speech -> reply audio starts) goes to
outputs/metrics.jsonl.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import mock_agent

ROOT = Path(__file__).resolve().parents[1]
WEB = Path(__file__).resolve().parent / "web"
LOGS = Path(os.environ.get("K3_LOG_DIR", ROOT / "outputs"))
AGENT_URL = os.environ.get("AGENT_URL", "").rstrip("/")
AGENT_TIMEOUT_S = float(os.environ.get("AGENT_TIMEOUT_S", "5"))

app = FastAPI(title="voice intake (K3)")


def _log(name: str, row: dict) -> None:
    p = LOGS / name
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


@app.get("/v1/health")
def health() -> dict:
    return {"ok": True, "contract": mock_agent.CONTRACT, "agent": AGENT_URL or "mock"}


@app.post("/v1/turn")
async def turn(request: Request) -> JSONResponse:
    req = await request.json()
    sid = str(req.get("session_id", "nosession")).replace("/", "_")[:64]
    t0 = time.perf_counter()
    try:
        if AGENT_URL:
            async with httpx.AsyncClient(timeout=AGENT_TIMEOUT_S) as c:
                r = await c.post(f"{AGENT_URL}/v1/turn", json=req)
            if r.status_code == 400:
                return JSONResponse(r.json(), status_code=400)
            r.raise_for_status()
            resp = r.json()
        else:
            resp = mock_agent.turn(req)
    except ValueError as e:
        return JSONResponse({"error": str(e), "field": "contract"}, status_code=400)
    except (httpx.HTTPError, KeyError) as e:
        # The app speaks its own canned line and keeps the last state (contract §9).
        raise HTTPException(status_code=502, detail=f"agent unavailable: {type(e).__name__}")
    ms = round((time.perf_counter() - t0) * 1000)
    _log(f"sessions/{sid}.jsonl", {"t": time.time(), "agent_ms": ms, "request": req, "response": resp})
    return JSONResponse(resp, headers={"X-Agent-Ms": str(ms)})


@app.post("/api/metrics")
async def metrics(request: Request) -> dict:
    row = await request.json()
    _log("metrics.jsonl", {"t": time.time(), **{k: row[k] for k in list(row)[:20]}})
    return {"ok": True}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


app.mount("/", StaticFiles(directory=WEB), name="web")

"""[R] HTTP binding of contract C1 (stdlib only).

    python -m agent.server                 # serves POST /v1/turn and GET /v1/health on :9000
    AGENT_URL=http://localhost:9000 ...    # point K's app (app/server.py) at it
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import llm
from .core import CONTRACT, turn


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/v1/health":
            self._send(200, {"ok": True, "contract": CONTRACT, "agent": "bolo-r3", "llm": llm.available(),
                             "model": llm.DEFAULT_MODEL})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/v1/turn":
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"error": "invalid JSON", "field": None})
        try:
            self._send(200, turn(req))
        except ValueError as e:
            field = str(e).split(":")[0] if ":" in str(e) else None
            self._send(400, {"error": str(e), "field": field})

    def log_message(self, fmt: str, *args) -> None:  # quieter logs, no bodies (may hold health details)
        print(f"[agent] {self.address_string()} {fmt % args}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    a = ap.parse_args()
    print(f"[agent] contract {CONTRACT} on http://{a.host}:{a.port}  llm={'on' if llm.available() else 'off'}")
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()

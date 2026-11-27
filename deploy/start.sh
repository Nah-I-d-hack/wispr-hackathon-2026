#!/bin/sh
# [K] Container entrypoint: the intake agent (R's, stdlib HTTP on :9000, inside the container only) and the voice app
# (:8000, the only port exposed). The app waits for the agent so the first turn never hits a cold server.
set -e
python -m agent.server --host 127.0.0.1 --port 9000 &
for i in $(seq 50); do
  python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9000/v1/health')" 2>/dev/null && break
  sleep 0.2
done
export AGENT_URL=http://127.0.0.1:9000
exec uvicorn app.server:app --host 0.0.0.0 --port 8000

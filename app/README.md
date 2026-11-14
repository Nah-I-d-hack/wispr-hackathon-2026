# K3: voice intake app (prototype)

A phone-first web app. The patient taps the mic and speaks Hindi, Bengali, English or a mix. Each turn goes to the
intake agent through contract C1 (`contracts/INTAKE.md`, `POST /v1/turn`), and the reply is spoken back with captions.
The app shows a "what we understood" card with field status, a clinician summary, and a large call button when the
agent escalates.

```bash
uv venv -p 3.12 && uv pip install -r app/requirements.txt
.venv/bin/uvicorn app.server:app --port 8000            # then open http://localhost:8000 in Chrome
AGENT_URL=http://localhost:9000 .venv/bin/uvicorn app.server:app --port 8000   # use R's agent instead of the mock
.venv/bin/python -m pytest -q tests                     # contract round-trips against the mock
```

**What's real and what's a placeholder**

| part | now | next |
|---|---|---|
| speech-to-text | browser Web Speech API, locked to the chosen language (`hi-IN`, `bn-IN`, `en-IN`) | K2 picks an engine that handles code-mixing and detects the language |
| language ID | the language the user picked, plus a script-based check for code-mixing | from the K2 engine |
| text-to-speech | browser `speechSynthesis`; falls back to captions if the device has no voice for that language | K2 engine with proper Hindi/Bengali voices |
| agent | `app/mock_agent.py`: canned questions + keyword red flags, **only a test double** | R3, via `AGENT_URL` |

**Behaviour already in place:**
- **Hands-free:** after the agent speaks, the app listens again on its own.
- **Barge-in:** tapping the mic while the agent speaks stops it. Escalations (`interruptible: false`) always play in full.
- **Fallbacks:** typed input (`stt_engine: "typed"`) for when the mic or speech recognition fails. If the agent is
  unreachable or slow (over 5 s), the app speaks its own canned line and keeps the last state (C1 §9).
- **Feedback:** a "thinking" cue after 1.2 s.
- **Latency:** the time from end of speech to the start of the reply's audio is shown on screen and logged to
  `outputs/metrics.jsonl`.
- **Logs:** every turn is logged to `outputs/sessions/<id>.jsonl`, so sessions can be replayed through R's agent (C1 §11).

Speech recognition in Chrome needs `localhost` or HTTPS, plus mic permission.

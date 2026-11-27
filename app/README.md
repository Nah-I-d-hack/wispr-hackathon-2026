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
| speech-to-text | **Wispr Flow** when `WISPR_API_KEY` is in `.env`: the app records, detects the end of speech, and `/api/stt` converts to 16 kHz WAV and sends it with the symptom vocabulary + the agent's last question. Without a key (or if Wispr fails), the browser Web Speech API | K2 eval tunes the end-of-speech timing and vocabulary |
| language ID | Wispr's `detected_language`; otherwise the language the user picked, plus a script check for code-mixing | |
| text-to-speech | browser `speechSynthesis`; falls back to captions if the device has no voice for that language | K2 engine with proper Hindi/Bengali voices |
| agent | `app/mock_agent.py`: canned questions + keyword red flags, **only a test double** | R3, via `AGENT_URL` |

**Desk view:** open `/desk` on the front-desk screen. It shows live intakes, emergencies first. A new emergency flashes (and beeps if sound is on) until someone presses "Seen, going now". The app's escalation shows the agent's number (e.g. Tele-MANAS 14416) with 112 as a second button.

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

## Phone calls (`/ws/phone`)

Bolo answers a telephony media stream as well as the browser. `/ws/phone` speaks the **Twilio Media Streams**
WebSocket protocol (8 kHz mu-law audio, `start`/`media`/`mark`/`stop` events), which Exotel, Plivo, Vonage and Telnyx
mirror closely. A real number later only needs the provider pointed at this URL (plus a thin adapter if its
protocol differs). Nothing in the call loop or the agent changes.

- **Speech out** is server-side (`voice/tts.py`): Google Cloud TTS with `GOOGLE_TTS_API_KEY`, otherwise espeak-ng
  (free, robotic, installed in the Docker image).
- **Turn-taking**: `voice/phone.py` reports `spoke_start` when it sends audio and `spoke_end` when the provider
  echoes our mark. On barge-in it sends `clear`.
- **Agent**: every turn goes out with `channel: phone_in` (C1 1.1), so the agent never refers to a screen.
  Escalations with `transfer` are recorded for the provider to bridge (logged until a provider is connected).

Try it without a provider. The simulator calls `/ws/phone` at phone quality and plays the caller's turns:

```bash
docker compose exec bolo python scripts/phone_sim.py --lang hi --say "पेट में गैस बन रही है" --say "दो दिन से"
docker compose exec bolo python scripts/phone_sim.py --wav my_recording.m4a      # real speech, any format
```

It prints what Bolo said, what speech-to-text heard, and the latency. It writes `bolo.wav`, `caller.wav` and
`call.json` to `outputs/phone_sim/`.

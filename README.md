# Voice-first healthcare intake (working title)

Our entry for **India Runs on Voice** (Scaler × Wispr), Healthcare track: patients describe symptoms by speaking in
their own language and get a structured, confirmed intake for the clinician. Red flags are escalated, never diagnosed.

## Run it

```bash
git clone https://github.com/Nah-I-d-hack/wispr-hackathon-2026.git && cd wispr-hackathon-2026
docker compose up --build
```

Open **http://localhost:8000** in Chrome, pick a language and tap the mic (or type). No API keys are needed to start:

| key (optional, in `.env`, see `.env.example`) | with it | without it |
|---|---|---|
| `WISPR_API_KEY` | Wispr Flow speech-to-text (code-mixed Hindi/Bengali/English) | the browser's speech recognition; Whisper (on the server) for the phone-call screen |
| `GEMINI_API_KEY` | the agent understands free-form answers with Gemini | the agent runs on its safety rules only; red flags still escalate |

The screen says which keys are missing. Other pages: **/call** (talk to Bolo like a phone call) and **/desk**
(what the front desk sees, with emergency alerts). The first start downloads a ~480 MB speech model for the call
screen in the background; the main screen works immediately.

Without Docker: `uv venv -p 3.12 && uv pip install -r app/requirements.txt faster-whisper`, then
`. .venv/bin/activate && sh deploy/start.sh`.

Status: setting up. See `docs/PLAN.md` for tasks, `docs/HACKATHON.md` for rules and dates, `docs/ONBOARDING.md` to
join, and `CLAUDE.md` for how the two agents (R and K) work together.

# agent/: Bolo intake agent (R3)

*[R]* Speaks contract C1 1.1 (`contracts/INTAKE.md`; 1.0 clients still work). Transcript in; next utterance, intake state and red flags out.

```bash
python -m agent.server                      # POST /v1/turn, GET /v1/health on :9000 (stdlib only)
AGENT_URL=http://localhost:9000 uvicorn app.server:app   # K's app talks to it instead of the mock
python -m pytest tests/test_agent.py -q     # offline tests (LLM switched off)
python eval/agent/run.py                    # Bolo vs baselines on data/*.jsonl, writes eval/agent/results/
```

Needs `GEMINI_API_KEY` in `.env` for the understanding layer. Without it (or with `AGENT_NO_LLM=1`) the agent still
runs: rules, red flags, idiom questions and the question order all work offline; only field extraction and the
patient read-back get simpler.

## How a turn works

1. **Rules** (`rules.py`, no network): signs from a Hindi/Bengali/English lexicon with negation ("pasina nahi"),
   ages, durations and corrections ("do din nahi, ek hafte se"), the everyday phrases of `docs/SAFETY.md` section 4,
   and the red-flag rules of section 3. Native script is transliterated first (`text.py`).
2. **Gemini** (`llm.py`, `core.py`): turns the utterance into intake fields (with a fixed JSON schema) and extra
   signs, and writes the patient read-back. Its signs are only *added* to the rules' signs. If it fails or takes longer
   than `AGENT_LLM_TIMEOUT` (3 s), the turn completes on rules alone (`debug.fallback: true`).
3. **Policy** (`core.py`): a new red flag escalates at once (emergency: 112, self-harm: 14416, urgent: see a doctor
   today). Otherwise it asks the follow-up for any everyday phrase it heard, then the missing basics (complaint, since
   when, age, anything else, existing illness, medicines), then reads back and waits for a yes.
4. **Fixed lines** (`lines_src.json` -> `lines.json`): every question and escalation is pre-written. hi/bn are
   written romanised in `lines_src.json` and converted to native script by `python -m agent.build_lines`. The agent
   never improvises medical wording; LLM text that names a condition or medicine is dropped (`_BANNED`).

| setting | default | meaning |
|---|---|---|
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | ~1 s per call in our test |
| `GEMINI_FALLBACK_MODEL` | `gemini-3.1-flash-lite` | used on retry |
| `AGENT_LLM_TIMEOUT` / `AGENT_LLM_RETRIES` | `3.0` / `0` | live turn budget |
| `AGENT_NO_LLM` | unset | `1` = rules only |
| `AGENT_LLM_MIN_INTERVAL` | `0` | pacing for batch runs on a free-tier key (eval uses 4 s) |

## Contract 1.1 (phone-style calls)

- `channel: phone_in | phone_out`: phone greeting, no screen references, emergency numbers spoken digit by digit
  ("1 1 2"); emergencies set `escalation.transfer: true`. `phone_out` + `context.patient_first_name` greets by name.
- Every reply carries `expect.fillers` (3 short acknowledgements in the session language, none after an escalation
  or at the end) and `expect.stt_hints` (likely next words for the current question).
- Self-harm escalations: `call` = 14416, `calls` = [112].

## R4: phone calls and misheard speech

- **Phone (`phone_in` / `phone_out`)**: no line refers to a screen (tested over every line, all languages). An emergency
  on a phone call sets `transfer: true` and speaks the `*_transfer` line in full ("connecting you to emergency help
  now ... if the call drops, call 1 1 2"); web keeps the original "call 112 now" wording. Numbers are spelled digit
  by digit in both `text` and `text_roman`.
- **Values that don't parse** (all channels): an answer to "since when?" / "how old?" that gives no value gets one
  simpler re-ask with examples (`q_duration_retry`, `q_age_retry`; a bare number like "chaalis" is accepted). A second
  miss stores the words in `_internal.unclear` and moves on; the read-back then says what was not understood
  (`unclear_*`), and an answer at the read-back fills it and reads back again. Never on a red-flag turn.
- **Two misheard turns in a row** (empty transcript, or `stt_confidence` < 0.35 with nothing understood): switch to
  yes/no questions (`yn_*`) for the rest of the call. A "yes" adds the matching sign, so red-flag rules treat it like
  the spoken words; the tension question keeps its self-harm screen (`yn_I_tension`, yes -> 14416 then 112).
  Follow-ups without a yes/no form (ghabrahat, BP, sugar, jalan, garmi-thand) are skipped. Five misheard turns in a row end politely, keeping what was collected.
- **Reply language**: set by the first utterance, then changes only after two turns in a row in another language.
- **Possibly misheard red-flag word** (a word one letter from "seene", "saans", "khoon", "behosh"..., or a red-flag
  word only in `transcript.alternatives`): asked about directly ("Kya seene mein dard hai?").
- `python -m agent.build_lines --changed` converts only new or edited lines and keeps the reviewed ones as they are.


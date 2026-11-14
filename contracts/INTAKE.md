# C1: Intake contract (voice layer <-> intake agent)

*[R] Draft v1.0 for K's review. Once merged this file is frozen: changes go through a `CONTRACT:` PR the other human
approves. Examples in `contracts/examples/`.*

## 1. Who does what

```
 patient speaks ──> [K: speech-to-text + language ID] ──TurnRequest──> [R: intake agent]
 patient hears  <── [K: text-to-speech + UI]         <──TurnResponse── (what to say, intake state, red flags)
```

- **K** owns audio: capture, end-of-speech detection, speech-to-text, language ID, text-to-speech, barge-in, the screen.
- **R** owns words and meaning: what the transcript means for the intake, what to ask next, read-back, corrections,
  red flags and escalation text.
- K never edits the agent's text before speaking it (except pronunciation fixes inside TTS). R never assumes anything
  about audio beyond what the request says.

## 2. Transport

Same JSON in both bindings. All text is UTF-8; Indic text is in native script unless `script` says otherwise.

| binding | shape |
|---|---|
| Python, in-process | `from agent import turn` then `turn(request: dict) -> dict` |
| HTTP | `POST /v1/turn`, body = TurnRequest, `200` body = TurnResponse. `GET /v1/health` returns `{"ok": true, "contract": "1.0"}` |

**The agent is stateless.** Every response carries the full intake `state`; K stores it and sends it back unchanged in
the next request (`state: null` on the first turn). So the agent can restart, run anywhere, and every conversation can be
replayed from logs for evaluation. K must not modify `state`.

Every request and response carries `"contract": "1.0"`. A minor bump (1.1) only adds optional fields; a major bump
breaks something and needs a `CONTRACT:` PR.

## 3. TurnRequest (K -> R)

| field | type | required | meaning |
|---|---|---|---|
| `contract` | `"1.0"` | yes | |
| `session_id` | string | yes | K generates one per conversation (uuid). Opaque to R |
| `turn` | int | yes | 0 for `start`, then +1 per request |
| `event` | enum | yes | `start` (conversation opens, no speech yet), `utterance` (user said or typed something), `no_speech` (K's silence timeout passed), `end` (user or UI closed) |
| `transcript` | object or null | for `utterance` | see below |
| `audio` | object or null | no | see below |
| `state` | object or null | yes | the `state` from the previous TurnResponse, untouched; `null` on `start` |
| `ui_lang_hint` | string or null | no | language the user picked on screen, if any (`hi`, `bn`, `en`). Wins over detection for the first agent reply |
| `client` | object | no | `{"app": "k3-web", "version": "0.1"}`, for logs only |

`transcript`:

| field | type | required | meaning |
|---|---|---|---|
| `text` | string | yes | final transcript as STT gives it (native, Latin or mixed script, whatever comes out) |
| `language` | string | yes | detected primary language, ISO 639-1 (`hi`, `bn`, `en`), or `und` if unknown |
| `mixed_with` | string[] | no | other languages detected in the same utterance, e.g. `["en"]` for Hinglish |
| `language_confidence` | float 0-1 or null | no | |
| `stt_confidence` | float 0-1 or null | no | utterance-level confidence if the engine gives one |
| `alternatives` | string[] | no | n-best alternatives if the engine gives them, best first, excluding `text` |
| `stt_engine` | string | no | e.g. `"wispr-flow"`, or `"typed"` for typed input; for logs and eval manifests |
| `barge_in` | bool | no | true if the user started speaking over the agent's last reply (K stopped TTS). Default false |

`audio` (all optional; send what you have):

| field | type | meaning |
|---|---|---|
| `duration_ms` | int | length of the user's speech |
| `speech_rate_wpm` | float | words per minute, if cheap to compute (slow speakers -> agent asks shorter questions) |
| `snr_db` | float | rough noise estimate |
| `truncated` | bool | true if K cut the user off (max length hit) |

## 4. TurnResponse (R -> K)

| field | type | always | meaning |
|---|---|---|---|
| `contract` | `"1.0"` | yes | |
| `session_id`, `turn` | | yes | echoed from the request |
| `action` | enum | yes | what K should do next, see section 5 |
| `say` | object | yes | what K speaks, see below |
| `expect` | object | yes | what kind of answer is expected, so K can tune listening |
| `state` | object | yes | full intake state, send back next turn (section 6) |
| `red_flags` | object[] | yes | all red flags raised so far in this session (may be empty) |
| `escalation` | object or null | yes | non-null means escalate *now*, see section 7 |
| `display` | object | yes | what the screen shows |
| `debug` | object | no | `{"latency_ms": 840, "model": "...", "fallback": false}`; K may log it, never shows it to the patient |

`say`:

| field | type | meaning |
|---|---|---|
| `text` | string | exactly what to speak. Short sentences, one question at a time |
| `language` | string | `hi`, `bn` or `en` |
| `script` | string | ISO 15924: `Deva`, `Beng`, `Latn` |
| `text_roman` | string | romanized copy, for logs and terminals that can't show Indic script. Never spoken |
| `register` | enum | `respectful` (default: aap / apni, elder-safe), `plain` |
| `pace` | enum | `normal` or `slow` (agent sets `slow` for slow speakers and for escalation). K maps it to a TTS rate |
| `interruptible` | bool | false for escalation messages: K must play them fully even if the user speaks over them |

`expect`:

| field | type | meaning |
|---|---|---|
| `kind` | enum | `free` (open description), `yes_no`, `choice`, `number`, `duration`, `none` (no answer expected, e.g. after `end`) |
| `choices` | string[] | for `choice`, in `say.language` |
| `patience` | enum | `normal` or `long`: `long` means wait longer before declaring `no_speech` (older users, open questions) |

`display`:

| field | type | meaning |
|---|---|---|
| `caption` | string | `say.text`, for on-screen captions (may be shortened) |
| `summary_patient` | string or null | read-back in the patient's language, shown during `confirm` |
| `summary_clinician` | string or null | English summary for whoever receives the intake; filled once there is anything to summarise |

## 5. Actions and the conversation flow

| `action` | K does |
|---|---|
| `ask` | speak `say`, then listen |
| `confirm` | speak the read-back in `say`, show `display.summary_patient`, then listen (expect `yes_no` or a correction) |
| `escalate` | speak `say` (= escalation message, not interruptible), show `escalation` prominently with the number, keep listening. The intake continues afterwards if the user wants |
| `done` | speak `say` (closing line), show `display.summary_clinician`, stop listening |
| `repeat` | the agent couldn't use the last input (empty, garbled, low confidence); speak `say` (a gentle "could you say that again"), listen |

Typical session: `start` -> greeting + "what is troubling you?" (`ask`) -> a few `ask` follow-ups -> `confirm`
(read-back) -> user corrects (back to `ask`/`confirm`) or agrees -> `done`. `escalate` can happen at any turn and
always wins over the normal flow. `no_speech` gets a gentle re-prompt; after 3 in a row the agent ends politely.

## 6. Intake state

`state` is owned by R; K may read it (e.g. to draw the summary card) but sends it back untouched. Shape:

```json
{
  "speaker": {"role": "self | caregiver | health_worker | unknown", "relation": "son"},
  "patient": {"age_years": 72, "age_band": "60+", "sex": "female | male | other | unknown"},
  "chief_complaint": {"value": "chest pain", "said": "seene mein dard", "status": "confirmed"},
  "symptoms": [
    {
      "name": "chest pain",
      "said": "seene mein dard ho raha hai",
      "onset": "2 hours ago", "duration": null, "severity": "severe", "location": "centre of chest",
      "character": "pressing", "pattern": "constant", "associated": ["sweating"],
      "status": "heard"
    }
  ],
  "history": {
    "conditions": {"value": ["diabetes"], "status": "heard"},
    "medicines_taken": {"value": ["metformin"], "status": "heard"},
    "allergies": {"value": [], "status": "missing"},
    "pregnant": {"value": null, "status": "not_applicable"}
  },
  "missing": ["allergies"],
  "phase": "collecting | confirming | escalated | done",
  "lang": {"reply": "hi", "script": "Deva", "register": "respectful"},
  "no_speech_count": 0,
  "transcript_log": [{"turn": 1, "who": "user", "text": "...", "language": "hi"}],
  "_internal": {}
}
```

- Field `status`: `missing` (not asked yet or unknown), `heard` (understood, not yet read back), `confirmed` (user
  agreed during read-back), `corrected` (user changed it during read-back; the new value is in `value`),
  `not_applicable`.
- `said` keeps the patient's own words, so a clinician sees what was actually said, not only our normalisation.
- `medicines_taken` records what the patient **already takes**, as said. The agent never suggests a medicine.
- English normalised values (`value`, `name`) are for the clinician; the patient hears read-backs in their language.
- `_internal` is free for R's use; K ignores it.

## 7. Red flags and escalation

`red_flags[]`, cumulative per session:

| field | type | meaning |
|---|---|---|
| `id` | string | rule id from `docs/SAFETY.md` (R2), e.g. `chest_pain_sweating`, `stroke_face_arm_speech`, `suicidal_thoughts` |
| `level` | enum | `emergency` (call now) or `urgent` (see a doctor today) |
| `evidence` | string | the user's words that triggered it |
| `turn` | int | when it was raised |

`escalation` (non-null only on the turn it fires, and again if the level goes up):

| field | type | meaning |
|---|---|---|
| `level` | enum | `emergency` or `urgent` |
| `message` | string | same text as `say.text` |
| `call` | object or null | `{"number": "112", "label": "Emergency"}` (or `108` ambulance, `14416` Tele-MANAS). Shown as a big tappable button |
| `reason_clinician` | string | English, for the summary card |

Rules both sides rely on:
- The red-flag check is **rule-based and runs on every utterance even if the LLM call fails or times out**. An
  emergency is never lost to an API error.
- Escalation text says *what to do* (call this number, go to the nearest hospital now) and never names a disease.
- K plays escalation fully (`interruptible: false`) at `pace: slow`, and keeps the call button on screen until the
  session ends.

## 8. Safety guarantees R makes (tested in R2/R3)

1. `say.text` never states a diagnosis ("you have X") or recommends a medicine, dose or treatment.
2. Before `done`, the agent reads back the intake and gets a yes, unless the user ends early.
3. When unsure, the agent asks; it does not guess a field.
4. Every emergency red flag in the R2 test set triggers `escalate` (target: recall 1.0 on emergencies).

## 9. Errors, timeouts, offline

- Agent budget per turn: **p50 under 1.5 s, p95 under 3 s** (measured inside the agent, excluding network). R reports
  this in the agent eval; K measures end to end.
- If the LLM fails, the agent still returns a valid response with `debug.fallback: true`: red-flag rules still apply,
  and `say` is a safe canned line ("Sorry, could you say that again?", in the session language).
- If K can't reach the agent at all (HTTP error or > 5 s), K speaks its own canned line in the session language and
  keeps the last `state`; nothing is lost. K keeps these canned lines in `voice/` or `app/`.
- **Typed input** (accessibility, or demo fallback if the mic/STT fails): an `utterance` with `stt_engine: "typed"` and
  `stt_confidence: null`. The agent treats it exactly like speech.
- Bad request (missing required field, unknown `contract` major version): HTTP `400` with
  `{"error": "...", "field": "..."}`; in-process, `ValueError`.

## 10. Languages in v1

Patient side: Hindi, Bengali, English, and Hinglish / Banglish code-mixing. The agent replies in the patient's main
language (`hi`, `bn`, `en`), in native script, in the respectful register unless told otherwise. If the language is
unclear (`und` or low confidence) it keeps the previous reply language; on the first turn it uses `ui_lang_hint`, else
Hindi. More languages are an additive change (1.x).

## 11. Logging and evaluation

- K logs every TurnRequest/TurnResponse pair (minus audio) as JSON lines per session. R's eval replays these through
  the agent, so a logged session is also a test case.
- No real patient data: logs from testing are synthetic (CLAUDE.md section 5).

## 12. What each side can build before the other is ready

- **K, before R3:** a stub agent `agent/stub.py` (R provides it right after this contract merges) that returns the
  fixtures in `contracts/examples/` in order, so K3 can run end to end.
- **R, before K3:** text-only harness: typed transcripts in, TurnResponses out, scored on the R2 test set.

## Settled in review (PR #24)

- Transport: HTTP for the app (K3); the in-process binding stays for tests and replay.
- Speech-to-text is the Wispr Flow API (#29): it gives `language` but no confidence or n-best, so those fields are
  usually null and the read-back carries more weight. K passes the agent's last `say.text` to Wispr as context.
- Barge-in is a flag on the utterance (`transcript.barge_in`), not a separate event, so it costs one request, not two.
- Client timeout 5 s; the app shows a "thinking" cue after about 1.2 s.

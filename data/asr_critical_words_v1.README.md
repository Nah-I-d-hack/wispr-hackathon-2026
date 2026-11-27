# asr_critical_words_v1: critical words for the speech-to-text fine-tune (R6, issue #101)

*[R] v1, 27 Nov. Owner: R. All sentences are synthetic, written by us. No real patient data.*

## Purpose

Kanishk is fine-tuning Whisper small so it hears the words that decide safety correctly: the red-flag phrases of
`docs/SAFETY.md` section 3, the everyday phrases of section 4, the sign words the rule layer listens for
(`agent/rules.py`, `LEX` and `IDIOMS`) and the number words that give an age. If speech-to-text turns "seene" into
"sena" or "saans" into "saas", the rules never see the sign. This file lists those words, how people spell and say
them, sentences that carry them, and the look-alikes that must **not** be heard as them.

Use it to:
1. **mine real speech first**: search IndicVoices / Vaani / Kathbath / MUCS / FLEURS / Common Voice transcripts for
   `canonical_roman`, `variants_roman` and `native` forms, and train mainly on those clips;
2. **fill gaps with TTS** from `frames`, only for words that are rare or missing in real data;
3. **score the model**: critical-word recall on the critical words, and false hits on `near_misses`.

## Schema (one JSON object per line)

| field | type | meaning |
|---|---|---|
| `id` | str | lower_snake_case, unique |
| `codes` | [str] | SAFETY.md codes the word feeds (`E*`, `U*`, `I_*`) |
| `priority` | str | `emergency` (an E-rule trigger), `urgent` (U-rule trigger or context: age, fever, older patient), `idiom` (a section 4 phrase that needs one more question) |
| `canonical_roman` | str | the main romanised form |
| `variants_roman` | [str] | other spellings and forms people type or STT returns (incl. English equivalents) |
| `native` | {hi: [str], bn: [str]} | Devanagari and Bengali-script forms (empty list where the word is not used in that language) |
| `frames` | [{text, lang, speaker}] | 8-15 short natural sentences. `lang` is `hi`, `bn`, `en`, `hi-en` or `bn-en`; `speaker` is `patient` or `caregiver`. Mostly romanised, about 1 in 4 in native script |
| `near_misses` | [{text, why}] | words or phrases that sound or look similar, or harmless idiom uses, that must NOT become the critical word |
| `sources` | [str] | where the entry comes from (SAFETY.md section, rules.py lexicon key, v1 test-case id) |

## Sources

- `docs/SAFETY.md` sections 3 and 4 (every E/U trigger and every I_* phrase).
- `agent/rules.py`: `LEX` sign words, `IDIOMS`, `_NUM_WORDS` (ages), `_REAL_WORDS` / `_NOT_FUZZY` / `_EXACT` (the
  known collisions such as saas/saans, buker/bukhar, dhore/diarrhoea, ghamte/ghumte).
- Phrasings the **rules-only** agent missed on `data/intake_holdout_v1.jsonl` (`eval/agent/results/20261115-014720`
  and `-151902`): face looks crooked / can't lift her arm (en-h02), chokhe jhapsa ... hata jachhe na sojha (bn-h01),
  saans lene mein dikkat, baat bhi nahi kar pa (hi-h06), rash that doesn't fade + very drowsy (en-h04), latrine kaali
  (hi-h08), don't see the point / ending my life (en-h06), saanp ne kaat liya (hi-h10), loose motions + can't keep
  water down (en-h10), paikhanar sathe rokto (bn-h04), nani phisal gayi, chal nahi pa rahi (hi-h14), neend nahi /
  bhookh nahi (hi-h15), gas ban rahi seene mein (hi-h02). They appear as paraphrases.
- No frame repeats a turn of `intake_test_v1` or `intake_holdout_v1` word for word (checked when building).

## Exclusion rule: holdout v2

**Nothing from `data/intake_holdout_v2.jsonl` (or its README) went into this file**: it was not opened while writing
it. Keep it that way: v2 sentences must not be used for ASR training, TTS, or the ASR eval, so the agent's v2 numbers
stay honest. If you add entries, do not look at v2 to find them.

## Frames are for TTS and mining only

The frames are written by the same people who wrote the agent's rules, so they share our phrasing habits. They are
for generating TTS audio and as search queries for real speech. **The ASR evaluation must use held-out speakers and
real recordings** (Kanishk's family recordings, ideally older relatives), not these frames read by TTS voices, and
whole templates should be held out from training. Never report a number measured only on TTS audio (issue #101).

## Stats

| priority | entries | frames | hi frames | bn frames | en frames | hi-en frames | bn-en frames | native-script frames |
|---|---|---|---|---|---|---|---|---|
| emergency | 63 | 511 | 225 | 162 | 60 | 49 | 15 | 108 |
| urgent | 20 | 162 | 71 | 52 | 18 | 18 | 3 | 40 |
| idiom | 18 | 145 | 60 | 58 | 6 | 15 | 6 | 36 |
| **all** | **101** | **818** | 356 | 272 | 84 | 82 | 24 | 184 |

Speakers: 314 patient / 504 caregiver frames. Near misses: 355. Romanised variants: 695. Native-script forms: 282.
Every SAFETY.md E- and U-code and every I_* idiom is covered except `U9_llm_concern`, which is the model's own
judgement and has no trigger words.

## Check

```bash
python eval/agent/check_asr_words.py           # schema, unique ids, SAFETY.md coverage, no duplicate frames
python eval/agent/check_asr_words.py --stats   # prints the table above
```

## Known gaps

- Written by non-clinicians who speak Hindi, Bengali and English; no Tamil, Marathi or other languages.
- Native-script spellings were typed by us; a native-speaker pass would catch odd forms.
- Dialect words (Bhojpuri, Sylheti, rural Bengali) are thin. Real-speech mining is where those should come from.
- `near_misses` are our guesses at what Whisper confuses. Replace them with the real confusions from the baseline
  run once it exists.

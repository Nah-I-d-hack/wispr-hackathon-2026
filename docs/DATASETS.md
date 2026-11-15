# Datasets (what helps Bolo, who uses it, and how)

*[K] Started 15 Nov. Check each license when you first access a dataset and update the table. Most Hugging Face
datasets here are gated: accept the terms with your own HF account.*

## Why there's no speech fine-tuning

Our speech-to-text is the **Wispr Flow API**, a closed hosted model, so we can't fine-tune it. What the API does allow
per request (`rest_api_v2.yaml`) is:
- `language`: the languages to expect (e.g. `["hi", "en"]`);
- `context.dictionary_context`: words and phrases to bias recognition towards. We feed it the symptom idioms from
  `docs/SAFETY.md` ("chakkar", "ghabrahat", "seene mein bhaari"…);
- `context.conversation`: previous turns. We pass the agent's last question, so "teen din se" lands in context.

So the speech datasets below are for **measurement**: how well Wispr hears our users, and how much the dictionary and
conversation context help. That's our before/after. Fine-tuning remains an option for R's agent (an LLM), with the
text datasets.

## Speech: STT evaluation (K, `eval/voice/`)

| bucket | dataset | contents | license / access | notes |
|---|---|---|---|---|
| `hi`, `bn` | [ai4bharat/IndicVoices](https://huggingface.co/datasets/ai4bharat/IndicVoices) | 22 languages; mostly extempore and conversational speech from many districts | CC BY 4.0, gated | main realistic hi/bn set |
| `hi-en`, `bn-en` | [MUCS 2021 code-switching](https://www.isca-archive.org/interspeech_2021/diwan21_interspeech.html) (navana-tech) | ~90 h Hindi-English, ~46 h Bengali-English (tech tutorials) | download from the challenge page | Hinglish / Banglish. Lecture style, not patients |
| `med` | [ekacare/eka-medical-asr-evaluation-dataset](https://huggingface.co/datasets/ekacare/eka-medical-asr-evaluation-dataset) | ~3,600 English + ~320 Hindi medical terms, sentences, conversations | gated; MIT per search, check the card | medical vocabulary |
| `en-in` | Svarah (AI4Bharat) | Indian-accented English | check | the English path |
| `clean` | [google/fleurs](https://huggingface.co/datasets/google/fleurs) `hi_in`, `bn_in` | read speech | CC BY 4.0 | sanity baseline |
| `ours` | our own recordings | symptom idioms, caregiver speech, ideally an older voice | ours, synthetic (no real patients) | the cases that matter most |
| (ask) | [DISPLACE-M](https://arxiv.org/abs/2603.02813) | ~55 h of health-worker ↔ care-seeker conversations, Hindi + dialects | availability unclear | closest real match. Worth emailing the organisers |

## Speech: TTS reference (K)

| dataset | use |
|---|---|
| [ai4bharat/indicvoices_r](https://huggingface.co/datasets/ai4bharat/indicvoices_r) (CC BY 4.0, gated) | reference voices when comparing hi/bn TTS engines |

## Text: for the intake agent (R's lane; listed here for R)

| dataset | contents | possible use |
|---|---|---|
| [IndicMedDialog](https://github.com/ShubhamKumarNigam/IndicMedDialog) (BioNLP 2026) | multi-turn symptom-elicitation dialogues, English + 9 Indic languages incl. hi/bn | follow-up question styles; extra test cases. It ends in a diagnosis, which we never do. Check the license |
| [ekacare/clinical_note_generation_dataset](https://huggingface.co/datasets/ekacare/clinical_note_generation_dataset) | doctor-patient transcripts (en/hi/mr) → structured JSON notes | checking `summary_clinician` / intake fields |
| [ekacare/MedMCQA-Indic](https://huggingface.co/datasets/ekacare/MedMCQA-Indic) | medical MCQs in 11 Indian languages | probably not needed |

## Rules

- Audio never goes into git. `eval/voice/manifest.json` stores dataset ids, row ids and reference text; the WAVs are
  rebuilt locally by `eval/voice/build_stt_set.py`.
- Our own recordings are synthetic test speech by the team (and consenting family). No real patient audio.

# RESEARCH (R1): who intake serves, what goes wrong, what we build on

Shared file: each agent edits only its own sections. Split agreed in #30: **R** = clinical intake, red flags and
misread symptoms, who receives the output, phone and internet access, Wispr fit. **K** = what exists, voice and
accessibility for older users. Every number has a source in section 7; anything we could not verify is marked.

## 1. Clinical intake: what a clinician needs, and where it breaks [R]

**What a usable intake contains.** Standard history-taking asks the same things in roughly the same order: the main
complaint in the patient's words; when it started and how it has changed; where it is, what it feels like, how bad
it is; what makes it better or worse; what comes with it; existing illnesses; medicines already taken; allergies;
for women of child-bearing age, pregnancy. Our intake state (`contracts/INTAKE.md` section 6) follows this, and keeps
the patient's own words (`said`) next to each normalised field.

**Where it breaks in India.**
- *Time.* A 67-country review found Indian primary-care visits average about **two minutes** (press coverage notes
  the figure mostly reflects crowded government OPDs). Much of that goes to asking the basics.
- *Language.* Registration forms and records are in English or formal Hindi; the patient speaks Bengali, Bhojpuri or
  a mix. Census 2011 recorded 19,569 mother-tongue names, rationalised into 121 languages.
- *Meaning.* Patients describe illness in everyday phrases ("gas", "chakkar", "ghabrahat", "kamzori") that a form or
  a rushed clerk takes literally (section 2).
- *Writing.* Where a nurse or health worker takes the history first, it is written by hand, then often re-asked.

**Who receives the output.** Three receivers, same intake, different view:
1. *OPD doctor:* a one-screen English summary, red flags first, patient's words alongside (`display.summary_clinician`).
2. *Nurse / registration desk:* the same, plus an alert when a red flag fires, so a dangerous case doesn't wait its
   turn (K's desk view).
3. *The patient / family:* the read-back in their language, to confirm or correct.
ASHA workers and tele-consultation (e.g. eSanjeevani) are natural later receivers; the contract does not change.

## 2. Red flags and misread symptoms [R]

- **Misreading symptoms delays care.** In a prospective Mumbai study of heart-attack (STEMI) patients,
  *misinterpretation of symptoms* was the largest cause of pre-hospital delay (**45%**), ahead of transport (27%). A
  South Indian STEMI study found symptom interpretation significantly linked to delay (median pre-hospital delay
  290 minutes). That patients specifically blame "gas" or acidity is reported by cardiologists in the press, not
  measured, so we say "easy to read as gas", not a percentage.
- **Everyday phrases carry clinical meaning.** Research on idioms of distress in India finds bodily phrases are a main
  way distress is expressed and are often misread in clinics (e.g. "tension" among North Indian women correlating with
  depression and anxiety scores). This supports the agent asking one discriminating question for each phrase instead
  of reading it literally.
- **What we built from this:** `docs/SAFETY.md` has 13 emergency and 8 urgent rules, plus 11 idioms with their
  discriminating questions, and `data/intake_test_v1.jsonl` tests them (64 synthetic cases, a dangerous and a
  harmless version of each idiom). Standard sources for the signs: stroke face-arm-speech-time, WHO child danger
  signs, pregnancy danger signs as taught to ASHAs. **A clinician still has to review these rules.**

## 3. Phones and internet: who can actually use this [R]

From the NSS Comprehensive Modular Survey: Telecom 2025 (Jan-Mar 2025):
- **85.5%** of households have at least one smartphone; **86.3%** have internet access at home.
- **Young people are covered:** 95.5% of rural 15-29-year-olds own a smartphone. Most migrant workers are young, so
  "migrant workers have no internet" is **not** a claim we should make.
- **The gap is women and older people:** mobile ownership (15+) is 83.9% for men but **56.2% for women**. About 12% of
  rural households have a mobile that is not a smartphone. Commentary on the survey notes older Indians still rely on
  basic phones (no age breakdown found).

**What this means for us:** the clinic setting needs no patient phone at all (desk tablet, or the nurse's device). For
people at home without a smartphone, a call-in number is the next step. The agent is channel-agnostic (speech in,
text out, contract C1), so a phone line is a new voice adapter on K's side, not a rebuild.

**If a judge asks "what about people without internet?"**: "In the clinic the patient needs no phone: Bolo runs on
the desk tablet. At home, the data says the gap isn't young migrants (95% of young rural Indians have smartphones),
it's older people and women, often with a basic phone or none. So the next step is a number you can call from any
phone; our agent is channel-independent, so that's a new voice adapter, not a rebuild."

## 4. Wispr fit: what the Flow API gives us and where it falls short [R]

**Status (15 Nov):** using Wispr inside the product is **optional**: the event requires Wispr Flow only for building (DECISIONS.md, 15 Nov). The API isn't public (only some organisations have access); on Discord the organisers said that if teams are expected to use it, access is free. K2 compares it with other speech engines. The analysis below still applies if Wispr is chosen, and the agent-side hints (`expect.stt_hints`) work with most engines that accept phrase hints.

From Wispr's API docs (api-docs.wisprflow.ai, read 15 Nov 2026):

| capability | what the docs say | what it means for Bolo |
|---|---|---|
| Transcription | REST `POST` (and a WebSocket API); base64 16 kHz WAV; max 25 MB / 6 min per request | fine for turn-by-turn intake |
| Languages | 100+; `language` = list of ISO 639-1 codes; one code forces it, none = autodetect ("less accurate") | send `["hi","bn","en"]`, narrowed to the session language once known |
| Language ID | response has `detected_language` | fills `transcript.language` in C1 |
| Confidence | **none** returned, no n-best | we can't tell a shaky transcript from a good one, so the read-back carries the safety load |
| `context.conversation` | chat-style history: `messages` with `role` + `content` | K passes the agent's last question, so short answers ("teen din se") are read in context |
| `context.dictionary_context` | "uncommon names or words relevant to the context that might be mentioned" | **the agent can supply these**: medicine names, the idioms it is asking about ("chakkar", "ghabrahat"), the options it just offered. Proposed as C1 v1.1 `expect.stt_hints` |
| `context.app.type` | `email`, `ai` or `other`, used to adjust writing style | `ai` or `other`: we don't want email-style rewriting of a patient's words |
| Pricing | usage-based tokens, credits then monthly billing; no free tier or rate limits documented | API not public; organisers: free access if teams are expected to use it (Discord, 15 Nov) |

**Risks to test in K2** (none of these are documented either way):
- **Clean-up vs the patient's words.** Flow is built for dictation, so it formats and tidies speech. For intake, the
  hesitations and self-corrections ("do din... nahi, ek hafte se") carry meaning. Check what it keeps.
- **Older and slow speakers**, and phone-quality audio (8 kHz) if we ever add a call-in line.
- **Bengali and code-mixed accuracy**, and which script it returns (Devanagari, Bengali or Latin), since the agent and
  the test set must handle all three.

**Why this matters for the pitch:** the finale is judged by Wispr's leadership. Using `conversation` and
`dictionary_context` the way they are meant to be used (the agent tells Flow what it just asked and what words to
expect) is a concrete, Wispr-specific idea, beyond simply calling the API.

## 5. What exists [K]

*K's section.*

## 6. Voice and accessibility for older users [K]

*K's section.*

## 7. Sources [R]

| claim | source | strength |
|---|---|---|
| ~2-minute primary-care visits in India | Irving et al., BMJ Open 2017, 67-country review ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/5695512)) | peer-reviewed; India table not checked by us |
| 1 in 5 Indians 60+ by 2050 (20.8%, 347 M) | UNFPA / IIPS India Ageing Report 2023 ([UNFPA](https://india.unfpa.org/en/news/india-ageing-elderly-make-20-population-2050-unfpa-report)) | official report, via press release |
| ~10% speak English (any level) | Census 2011, via secondary summary ([link](https://www.thehistoryofenglish.com/how-many-people-in-india-speak-english)) | **weak**: not checked in census tables, don't use without checking |
| 19,569 mother-tongue names, 121 languages | Census 2011 language data ([summary](https://www.legacyias.com/the-languages-india-speaks/)) | official figures, via secondary summary |
| Misreading symptoms = 45% of STEMI pre-hospital delay (Mumbai) | prehospital delay study, urban tertiary centre, Mumbai ([record](https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_miscellaneous_1908429887)) | peer-reviewed, abstract only |
| Idioms of distress misread in Indian clinics | narrative review ([PMC5602270](https://pmc.ncbi.nlm.nih.gov/articles/PMC5602270)); Weaver 2017 on "tension" ([UA](https://anthropology.ua.edu/research/tension-among-women-in-north-india-an-idiom-of-distress-and-a-cultural-syndrome-by-dr-weaver)) | peer-reviewed |
| Phone and internet ownership figures | NSS CMS: Telecom 2025 ([PIB press note](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/may/doc2025529560001.pdf), [PARI summary](https://ruralindiaonline.org/en/library/resource/comprehensive-modular-survey-telecom-2025)) | official survey |
| Wispr Flow API capabilities | [api-docs.wisprflow.ai](https://api-docs.wisprflow.ai/) (request schema, REST transcribe, usage and billing pages) | official docs, 15 Nov 2026 |

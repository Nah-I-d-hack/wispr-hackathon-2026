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
- *Time.* A 67-country review (Irving et al. 2017) has no India sentence, but its Table 1 lists four Indian studies
  timing primary-care consultations: mean **1.5, 1.9, 2.0 and 2.3 minutes** (1979-2015; quality rated fair or poor by
  the authors; one is a Kolkata CGHS-dispensary audit). So "about two minutes" holds, on old and small studies.
  *Checked 27 Nov against the table.* The press line that it "mostly reflects crowded government OPDs" is not in the
  paper; don't use it.
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

**How many (added 27 Nov for the Round 2 deck, slide 4).**
- *People over 60:* about **13.8 crore in 2021 (10.1% of the population)**,
  projected to **19.4 crore (13.1%) by 2031**. Source: NSO (MoSPI), *Elderly in India 2021*, Table 3.1, which takes
  the figures from the Technical Group on Population Projections 2011-2036. These are projections for 2021, not a
  count; there has been no census since 2011. The "15 crore over 60" in the Impact draft has no source: use 13.8 crore
  (2021).
- *Yearly OPD visits, all India:* **not found.** Neither MoHFW's Annual Report 2023-24 nor its "Initiatives &
  Achievements 2025" gives a national yearly outpatient count; HMIS publishes facility-level data only. Cut from the
  deck rather than estimated.
- *Primary-care visits, cumulative:* 1,81,873 Ayushman Arogya Mandirs (upgraded sub-centres and PHCs) had recorded a
  **footfall of 494.71 crore** and 41.93 crore teleconsultations as on 30 Nov 2025 (MoHFW, Initiatives & Achievements
  2025). A running total since the programme began, not a yearly figure.

**Running cost inputs (deck slide 8).** Gemini 3.5 Flash-Lite, paid tier: $0.30 per million input tokens, $2.50 per
million output tokens; free tier available (Google AI Studio pricing page, read 27 Nov 2026). Plivo India voice:
Rs 0.38 per minute inbound or outbound, 30-second pulse, Rs 200 a month per domestic number (Plivo pricing page, read
27 Nov 2026). Tokens per intake are our estimate from prompt sizes (`agent/core.py`: instructions 734 characters,
answer schema 3,500), not measured; the math is in the slide 8 speaker note.

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

Plenty of Indian health tech uses voice or sits near intake. None of it takes the history **from the patient, by
voice, in their language, before the doctor**, with a red-flag check that alerts the desk. Bolo fits between
registration and the doctor's own notes.

| what | who it serves | what it does | where Bolo fits |
|---|---|---|---|
| **ABHA Scan & Share** (NHA, since Oct 2022) | patients at the registration counter | scan a QR to register in the OPD queue: **6.64 crore tokens at 17,481 facilities, about 2 lakh a day** (Nov 2024) | it stops at name and demographics. Bolo is the next step in the same queue: the same desk tablet, now with symptoms |
| **Ambient AI scribes**: EkaScribe (Eka Care), chosen as NHA's partner for an ambient voice scribe; others built on Sarvam's speech models | doctors | listen to the doctor-patient conversation and write structured notes; Eka's Parrotlet v2 speech model claims code-mixed Hindi-English and Indian medicine names | they start once the doctor is talking to the patient. Bolo works **before** that, in the queue, and catches the case that shouldn't be waiting. The two are complementary: our intake could feed their record |
| **Voice triage helplines** (hospital voice bots) | callers to a hospital | vendors describe Hindi-first triage flows adapted from the Manchester Triage System | vendor claims only, no public evaluation found. Our evaluation (R2/R3) and our "never diagnose" rule are where we differ |
| **Jugalbandi** (Microsoft, IIT Madras, AI4Bharat) | rural citizens on WhatsApp | voice question → speech-to-text → translation → LLM → speech back, for 170+ government schemes | proves the Indian voice pipeline works at scale. It isn't health intake. **Bhashini** (whose models it uses) signed an MoU with NHA in 2026 to bring speech and translation into health apps |
| **Kilkari** (MoHFW with ARMMAN) | pregnant women and mothers | free weekly voice messages by phone call (IVR); 11 million+ subscribers reported | one-way information, but it shows voice on a basic phone reaches women who are hard to reach by apps |
| **Typed symptom checkers and general chatbots** | anyone with a smartphone and English | typed questions, ending in possible conditions | text and English first, and they name conditions. R3's plain-LLM baseline did so in 20 replies; Bolo never does |

**For K2 (speech engines):** this list adds candidates beyond Wispr: Eka's Parrotlet (medical, code-mixed),
Bhashini / AI4Bharat models, and Sarvam. The comparison should include at least one Indian medical model.

Sources for this section: [ABHA Scan & Share, MoHFW press release](https://mohfw.gov.in/press-info/7908) and
[4-crore milestone](https://mohfw.gov.in/press-info/7476) (official); [EkaScribe and NHA partnership](https://www.psuconnect.in/news/ekacare-selected-as-a-technology-partner-for-national-health-authority-ambient-ai-enabled-voice-scribe-solution-for-doctors),
[Parrotlet v2](https://indiamedtoday.com/eka-care-launches-parrotlet-a-v2-for-real-time-indian-medical-transcription/)
(trade press, company claims); [voice triage helpline](https://caller.digital/blog/voice-ai-hospital-clinical-triage-nurse-helpline-india-2026)
(**vendor blog, weak**); [Jugalbandi, Microsoft](https://news.microsoft.com/source/asia/features/with-help-from-next-generation-ai-indian-villagers-gain-easier-access-to-government-services/);
[Bhashini-NHA MoU](https://indiamedtoday.com/digital-india-bhashini-division-signs-mou-with-national-health-authority/);
[Kilkari, ARMMAN](https://armman.org/kilkari/) (self-reported reach).

## 6. Voice and accessibility for older users [K]

**Why voice, for older Indians in particular** (LASI Wave 1, 2017-18, people aged 60+, n = 31,902):
- Only **39.6% are literate** (men 56.6%, **women 24.2%**; rural 30.0%, urban 62.5%), and **56.5% never went to
  school**. A form, an app menu or a typed chatbot shuts most older patients out. Speaking doesn't.
- **55.3%** report a diagnosed eye or vision condition (cataract 23.2%, refractive error 35.4%). Text on a screen
  must be large, and nothing important can be text-only.
- **9.6%** report a diagnosed hearing or ear problem, but only **0.7%** use a hearing aid. Spoken replies need
  captions, a slower pace and an easy "say that again".
- Only **5.7%** live alone. Most have family around, so a son or daughter speaking for them is the normal case,
  not an edge case.

**Why it's hard:**
- **Speech recognition is worse on older voices.** In Vipperla et al.'s longitudinal study, word error rate was
  47.8% for older voices vs 36.4% for younger adults on the same task, rising with age. Slower speech added
  insertion errors. A 2025 clinical evaluation of current models (Whisper and others) on speakers 65+ still finds
  high-error cases. So we can't assume a vendor's headline accuracy holds for our users. **K2 measures it on older
  voices.**
- **Older speakers pause more and longer**, so a fixed short end-of-speech timeout cuts them off. In-home studies of
  older adults with voice assistants list pauses, repeats and slow speech as main causes of errors. Assistants that
  can be interrupted feel more natural to them.

**Design rules in the app (K3), and where each comes from:**

| rule | in the app |
|---|---|
| no reading needed | one large mic button, hands-free turn-taking; every question is spoken |
| nothing is speech-only either | large captions on every reply (20 px, Noto fonts for Devanagari and Bengali) |
| don't cut people off | the turn ends after 1.2 s of silence, **1.8 s** when the agent expects a long answer (`expect.patience`); three silences end politely; tapping the mic ends a turn early |
| let them interrupt | tapping while Bolo speaks stops it (barge-in), except for escalations, which always play in full at a slow pace |
| check, don't assume | the read-back in their language before anything is final (agent) and a "what we understood" card |
| family is welcome | caregiver speech is expected; the agent records who is speaking (`speaker.role`) |
| don't rely on the patient to act | emergencies show a large call button **and** alert the desk view, so staff act even if the patient doesn't |

**Still open (K2/K3):** text-to-speech voices that older listeners find clear in Hindi and Bengali (slow but natural,
adjustable volume); the noisy OPD; whether the end-of-speech timing suits real older speakers. K2 will include
recordings by older family members (with consent) and report error rates for them separately.

Sources for this section: [LASI Wave 1 key indicators for the elderly, IIPS](https://www.iipsindia.ac.in/sites/default/files/other_files/LASI_W1_Elderly_India.pdf)
(official survey, figures read from the factsheet table); [Vipperla et al., Interspeech 2008](https://www.cstr.inf.ed.ac.uk/downloads/publications/2008/vipperla_is08.pdf)
(peer-reviewed, older systems); [ASR for older adults in the clinic, 2025](https://arxiv.org/abs/2508.08684)
(preprint, Dutch); [older users and dialogue systems](https://arxiv.org/abs/1902.04393) (pauses and timeouts);
[barge-in and older adults, CHI 2025](https://apex-group-hkust.netlify.app/publication/chi25-nature-conversation).

## 7. Sources [R]

| claim | source | strength |
|---|---|---|
| ~2-minute primary-care visits in India (four Indian studies, means 1.5-2.3 min, 1979-2015) | Irving et al., BMJ Open 2017, 67-country review, Table 1 ([PMC5695512](https://pmc.ncbi.nlm.nih.gov/articles/PMC5695512/)) | peer-reviewed review; the Indian studies are old and rated fair/poor; table checked 27 Nov |
| 13.8 crore aged 60+ in 2021 (10.1%), 19.4 crore by 2031 | NSO / MoSPI, *Elderly in India 2021*, Table 3.1, from the Technical Group population projections 2011-2036 ([PDF](https://mospi.gov.in/sites/default/files/publication_reports/Elderly%20in%20India%202021.pdf)) | official; projections, not a census count |
| Ayushman Arogya Mandirs: 1,81,873 centres, footfall 494.71 crore (cumulative, to 30 Nov 2025) | MoHFW, *Initiatives & Achievements 2025* ([PIB PDF](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/jan/doc202611749801.pdf)) | official |
| Yearly OPD visits, all India | none found (MoHFW Annual Report 2023-24 and Achievements 2025 checked) | **cut from the deck** |
| Gemini 3.5 Flash-Lite: $0.30 / $2.50 per million input / output tokens (paid tier) | [Google AI Studio pricing](https://aistudio.google.com/docs/pricing), read 27 Nov 2026 | official price list; can change |
| Plivo India voice: Rs 0.38 per minute, Rs 200 a month per number | [Plivo India voice pricing](https://www.plivo.com/voice/pricing/in/), read 27 Nov 2026 | official price list; can change |
| 1 in 5 Indians 60+ by 2050 (20.8%, 347 M) | UNFPA / IIPS India Ageing Report 2023 ([UNFPA](https://india.unfpa.org/en/news/india-ageing-elderly-make-20-population-2050-unfpa-report)) | official report, via press release |
| ~10% speak English (any level) | Census 2011, via secondary summary ([link](https://www.thehistoryofenglish.com/how-many-people-in-india-speak-english)) | **weak**: not checked in census tables, don't use without checking |
| 19,569 mother-tongue names, 121 languages | Census 2011 language data ([summary](https://www.legacyias.com/the-languages-india-speaks/)) | official figures, via secondary summary |
| Misreading symptoms = 45% of STEMI pre-hospital delay (Mumbai) | prehospital delay study, urban tertiary centre, Mumbai ([record](https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_miscellaneous_1908429887)) | peer-reviewed, abstract only |
| Idioms of distress misread in Indian clinics | narrative review ([PMC5602270](https://pmc.ncbi.nlm.nih.gov/articles/PMC5602270)); Weaver 2017 on "tension" ([UA](https://anthropology.ua.edu/research/tension-among-women-in-north-india-an-idiom-of-distress-and-a-cultural-syndrome-by-dr-weaver)) | peer-reviewed |
| Phone and internet ownership figures | NSS CMS: Telecom 2025 ([PIB press note](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/may/doc2025529560001.pdf), [PARI summary](https://ruralindiaonline.org/en/library/resource/comprehensive-modular-survey-telecom-2025)) | official survey |
| Wispr Flow API capabilities | [api-docs.wisprflow.ai](https://api-docs.wisprflow.ai/) (request schema, REST transcribe, usage and billing pages) | official docs, 15 Nov 2026 |

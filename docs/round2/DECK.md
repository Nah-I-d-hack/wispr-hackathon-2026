# Round 2 pitch deck: slide text

*[R] Final wording pass, 27 Nov (Ritankar delegated it; he reviews via "Wording decisions" at the end). Kanishk owns
slide 7 (dependencies and fallbacks). Every number below comes from `docs/RESEARCH.md` (sources in its section 7) or
from `eval/agent/RESULTS.md`. Numbers we could not source were cut, not guessed.*

Required by the brief (#84): (1) problem / solution, (2) users and how many, (3) dependencies and what happens if they
fail, (4) launch plan. Slides 5 and 6 (safety, evaluation) are ours: they are the questions a judge will ask next.

Format: title, 3-5 bullets, speaker note. 9 slides, readable in a couple of minutes.

---

## Slide 1. Bolo: tell the clinic what's wrong, in your own words

- A voice agent that takes a patient's history before the doctor sees them.
- Hindi, Bengali, English, or any mix. Nothing to read, nothing to type.
- The clinic gets a one-screen intake in English, red flags on top.
- It never diagnoses and never suggests medicine.

*Speaker note:* One line on what it is, then straight to the problem. No technology on this slide.

---

## Slide 2. The problem: care goes wrong at the first conversation

- Patients think in Bengali, Bhojpuri or Hinglish; forms, and often staff, use English or formal Hindi. Census 2011
  recorded 19,569 mother-tongue names, grouped into 121 languages.
- People describe illness in everyday phrases: "gas", "chakkar", "ghabrahat", "kamzori". The same phrase can be
  harmless or an emergency, and a form or a rushed clerk takes it literally.
- In a Mumbai study of heart-attack patients, misreading the symptoms was the largest cause of delay before reaching
  hospital (45%, ahead of transport at 27%).
- There is little time to untangle it: Indian studies timed primary-care consultations at 1.5 to 2.3 minutes
  (four studies in a 67-country review, Irving et al., BMJ Open 2017).

*Speaker note:* Tell the story from the Idea: a 62-year-old says he has "gas" in his chest and is sweating. It goes
down as acidity and he waits three hours. Don't say what share of patients blame "gas": cardiologists say it in the
press, nobody has measured it. The consultation studies are old and small (1979-2015); say "about two minutes", not a
precise figure.

---

## Slide 3. The solution: a call-like conversation before the doctor

- The patient or a family member speaks: "maa ko do din se chakkar aa rahe hain". Several voices are fine; Bolo
  records who said what.
- When a phrase can mean two things, it asks the one question that tells them apart. For "chakkar": "Does the room
  spin, or do you feel you might fall?"
- If an answer sounds dangerous, it says so at once (call 112 or go to the emergency now) and alerts the desk.
- It reads back what it understood, in the patient's language. They correct it by speaking.
- Staff get a one-screen intake in English, with each speaker's own words beside it.

*Speaker note:* Show the demo clip here if presenting live. It runs today in a phone browser or on a desk tablet; a
number anyone can dial is the next step (slide 8).

---

## Slide 4. Who it's for, and how many

- **Older patients first.** About 14.9 crore Indians were 60 or older in 2022 (10.5%; India Ageing Report 2023),
  heading for 1 in 5 Indians (34.7 crore) by 2050.
- **Most of them can't use a form.** Only 39.6% of people over 60 can read (women 24.2%); 56.5% never went to school
  (LASI Wave 1). Speaking needs neither.
- **Women at home.** Mobile ownership (age 15+) is 83.9% for men but 56.2% for women (NSS Telecom 2025).
- **Families who speak for them.** Only 5.7% of older Indians live alone (LASI), so a son or daughter speaking for a
  parent is the normal case, and Bolo expects it.
- **Across the desk: OPD doctors, nurses and registration staff.** Government OPDs already issue about 2 lakh ABHA
  Scan & Share queue tokens a day (6.64 crore at 17,481 facilities, MoHFW, Nov 2024). Bolo is the next step in that
  queue.

*Speaker note:* The device question comes up here. In the clinic the patient needs no phone: Bolo runs on the desk
tablet. At home the gap isn't young people (95.5% of rural 15-29-year-olds own a smartphone); it is older people and
women, often with a basic phone or none (about 12% of rural households have only a non-smartphone). That is why the
phone number matters. For the primary-care pilot (slide 8): India's 1.82 lakh Ayushman Arogya Mandirs had recorded
494.71 crore visits in total by 30 Nov 2025 (MoHFW). We found no official yearly count of all OPD visits, so we don't
quote one.

---

## Slide 5. Safety: intake, not diagnosis

- Bolo never names a condition, medicine, dose or test. It records what the patient already takes, in their words.
  "Which tablet should I take?" gets a kind refusal and the promise that the doctor will hear the question.
- Red flags are fixed rules, not the AI's opinion: 13 emergency rules (chest pain with sweating, stroke signs,
  breathing, fits, pregnancy and child danger signs, self-harm, poisoning...) and 8 urgent ones. An AI safety net can
  add "see a doctor today", never remove a flag.
- Emergency: "Call 112 or go to the nearest emergency now." Self-harm: Tele-MANAS 14416 first, then 112. Urgent: "A
  doctor should see this today."
- The rules run on every turn without the AI model, so a slow network or a failed API call can't drop an emergency.
- Nothing is final until the patient confirms the read-back.

*Speaker note:* Say plainly that neither of us is a clinician. The rules come from standard signs (stroke
face-arm-speech-time, WHO child danger signs, pregnancy danger signs as taught to ASHAs), and a doctor must review
them before any pilot (SAFETY.md section 8).

---

## Slide 6. How well it works so far (synthetic test cases)

| | keyword checker | plain AI chatbot | **Bolo** |
|---|---|---|---|
| Emergencies caught, v1 held-out (19)* | 5% | 100% | 95% (missed 1) |
| False emergencies, v1 held-out* | 20% | 20% | 7% |
| Replies naming a condition or medicine, all v1 cases | 0 | 20 | **0** |
| Everyday phrase followed up, v1 held-out* | 11% | 67% | 89% |
| **Fresh held-out v2 (frozen 27 Nov): TBD 29 Nov.** Emergencies caught, human-written cases | TBD | TBD | TBD |
| **Fresh held-out v2 (frozen 27 Nov): TBD 29 Nov.** Emergencies caught, AI-written blind cases | TBD | TBD | TBD |

\* *v1 held-out: after this run we used it to fix the one missed emergency and the one false alarm, so these rows
flatter Bolo. The v2 rows are the honest numbers.*

- A plain AI chatbot catches emergencies too, but it raised about three times as many false alarms (20% vs 7%) and
  named conditions or medicines in 20 replies. Bolo's edge is precision and safe wording, not recall.
- On the main test set Bolo filled 97% of intake fields correctly, but that set was used to build it, so we don't lead
  with it.
- Speed: Bolo replied in about 1.5 s typically, 2.0 s at the slow end, in that run. On the free-tier model the slow
  end later reached 6-8 s, which is why the emergency rules must work without the AI.

*Speaker note:* All cases are synthetic, written by us; the sets are small, so one case moves recall by about 5
points. Be open about the second run the same day (`20261115-151902`): with the model slower, Bolo caught 17 of 19
held-out emergencies (89%); both misses came on turns where the AI timed out and the rules lacked the wording, so
standard stroke phrasings were added to the rules. Model: Gemini Flash-Lite, free tier. Run ids `20261115-014720` and
`20261115-151902`. On 29 Nov fill the v2 rows from `docs/round2/TESTSET_BRIEF.md`; if space is short, drop the v1
rows except the "naming a condition" row.

---

## Slide 7. Dependencies and fallbacks (K drafts)

*Placeholder: Kanishk drafts this slide (#85). Expected shape: each thing Bolo depends on (speech-to-text, the AI
model, text-to-speech, network, the phone line) and what happens when it fails. The agent-side facts K can use: red-flag
rules run offline in milliseconds without the AI model; on an AI timeout (3 s) the turn falls back to rules only; with
no API keys the agent runs rules-only (`docker compose up`, #83).*

---

## Slide 8. Launch plan: one clinic first

- **Before any patient (December):** a doctor reviews the red-flag rules; we test on the fresh hand-written set and on
  real recorded voices (including older family members, with consent), and fix what breaks.
- **Pilot 1: one OPD front desk** at a district hospital or an urban PHC (partner to be confirmed). Bolo on a desk
  tablet in the waiting area, staff alongside, for about four weeks. Patients choose to use it; the doctor still
  takes their own history.
- **Pilot 2: ASHA workers.** The same intake on the health worker's phone during home visits, so a danger sign is
  noticed before the trip to the clinic. Bolo already records when a health worker is speaking.
- **Next: a phone number** any basic phone can dial, for older people and women without a smartphone. The agent
  doesn't change; the phone connection is built and tested on a simulated line, not yet on a real number.
- **Running cost:** under 5 US cents per intake for the AI model at Google's paid list price (free tier during the
  pilot). The phone line adds Rs 0.38 a minute, about Rs 2 for a 5-minute call, plus Rs 200 a month for the number
  (Plivo list price).

*Speaker note:* Keep it small and real. We are not claiming a rollout; we are asking for one clinic. Cost math, an
upper bound from our prompt sizes, not a measured bill: each patient turn sends about 8,000 characters (instructions
734 + answer format 3,500 + intake and last 8 lines about 4,000), roughly 2,100 tokens; we round up to 3,000 because
romanised Hindi and Bengali take more tokens. The reply is at most about 800 tokens. Assume at most 15 turns per
intake. Gemini 3.5 Flash-Lite paid tier: $0.30 per million input tokens, $2.50 per million output. So 45,000 x $0.30/M
= $0.0135, plus 12,000 x $2.50/M = $0.030, total about $0.044 per intake. A busy desk at 100 intakes a day for 30 days
is at most about $130 a month. Speech recognition on the tablet uses the browser's built-in recogniser or Whisper on
our own server, with no per-use charge. Phone: Plivo India list price Rs 0.38 per minute inbound, billed in 30-second
pulses, so 5 x 0.38 = Rs 1.90 per 5-minute call; number rental Rs 200 a month. Tablet and staff time are not included.

---

## Slide 9. What we'd measure in the pilot

- **Safety:** every case staff mark as urgent was flagged by Bolo first; zero replies naming a condition or medicine.
- **Accuracy:** at least 90% of intakes confirmed at the read-back without a correction, checked against the doctor's
  notes on a sample.
- **Time:** at least 1 minute of history-taking saved per visit, timed with and without a Bolo summary.
- **Use:** at least 70% of patients offered Bolo finish it, counted separately for people over 60.

*Speaker note:* These are our targets (from the Round 1 Impact draft, #81), not results. Say so. This slide can merge
into slide 8 if the deck needs to be shorter.

---

## Open items before the PDF

- [ ] Ritankar: final wording of every slide.
- [ ] Kanishk: slide 7.
- [ ] Slide 4 TODOs: current 60+ population and yearly OPD visits, each with a source added to RESEARCH.md first.
- [ ] Slide 6: fresh held-out v2 numbers on 29 Nov (`docs/round2/TESTSET_BRIEF.md`), split human-written vs AI-written.
- [x] Slide 8: pilot site phrased as a plan (partner to be confirmed); cost computed from public prices (speaker note).
- [x] 2-minute figure checked against the paper's table (four Indian studies, 1.5-2.3 min); wording changed.

*[R] 27 Nov: the slide 4 item above is done (60+ population sourced; yearly OPD visits cut, see below). Its checkbox
is left as is only so this edit doesn't collide with Kanishk's PR #91 on the line next to it.*

---

## Wording decisions (27 Nov, [R], for Ritankar's 2-minute review)

1. **Slide 4, 60+ population:** added "13.8 crore in 2021 (10.1%), 19.4 crore by 2031" from NSO's *Elderly in India
   2021* (MoSPI), which quotes the government's Technical Group population projections. It is a 2021 projection, not
   a 2026 count, so the slide says "in 2021". *Update [R]: switched to the India Ageing Report 2023 figure, 14.9 crore
   (149 million, 10.5%) in 2022: newer, and it is the source the Impact answer's "about 15 crore" (#81) already cites,
   so the two documents agree. NSO's 13.8 crore (2021) stays in RESEARCH.md as a cross-check.*
2. **Slide 4, yearly OPD visits: cut.** No official national yearly figure found (checked MoHFW Annual Report
   2023-24, MoHFW Achievements 2025, NHP/HMIS search). The Ayushman Arogya Mandir total (494.71 crore visits by Nov
   2025, cumulative) went into the speaker note only, since it is not a yearly OPD count.
3. **Slide 4 split** into five bullets (population, literacy, women, families, desk) so each carries one number.
4. **Slide 2, "two minutes":** the paper has no India sentence; its table lists four Indian studies at 1.5, 1.9, 2.0
   and 2.3 minutes (1979-2015, rated fair or poor quality). Slide now says "1.5 to 2.3 minutes (four studies)". Cut
   "mostly crowded government OPDs" (press, not the paper) and "much of that goes on re-asking the basics" (no source).
5. **Slide 6:** v1 rows labelled as from a set later used for fixes; two placeholder rows for the fresh v2 set
   (human-written vs AI-written blind), TBD 29 Nov. Speaker note now mentions the second run's 17/19 so nobody can
   say we hid it.
6. **Slide 8:** no partner named: "a district hospital or an urban PHC (partner to be confirmed)". Cost line kept
   because it can be computed from public prices (Gemini 3.5 Flash-Lite, Plivo India); the math is in the speaker
   note and labelled an upper-bound estimate, not a bill. Phone wording matches Kanishk's slide 7 ("built and tested
   on a simulated line", not "live").
7. **Slides 1, 3, 5, 9:** tightened only; no new claims. Slide 5 now says the AI safety net can add "see a doctor
   today" but never remove a flag (matches SAFETY.md / RESULTS.md).
8. **Not touched:** the slide 7 section and the open-items lines around "Kanishk: slide 7" (PR #91).

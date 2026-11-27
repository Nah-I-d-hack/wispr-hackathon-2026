# Round 2 pitch deck: slide text (draft)

*[R] Draft for Ritankar to edit; Ritankar decides the final wording. Kanishk drafts slide 7 (dependencies and
fallbacks). Every number below comes from `docs/RESEARCH.md` (sources in its section 7) or from
`eval/agent/RESULTS.md`. Anything we could not source is marked **TODO** and must be sourced or cut before the PDF.*

Required by the brief (#84): (1) problem / solution, (2) users and how many, (3) dependencies and what happens if they
fail, (4) launch plan. Slides 5 and 6 (safety, evaluation) are ours: they are the questions a judge will ask next.

Format: title, 3-5 bullets, speaker note. About 9 slides for a deck read in a couple of minutes.

---

## Slide 1. Bolo: tell the clinic what's wrong, in your own words

- A voice agent that takes a patient's history before the doctor sees them.
- Hindi, Bengali, English and any mix of them. Nothing to read, nothing to type.
- The clinic gets a one-screen intake in English, with red flags on top.
- It never diagnoses and never suggests medicine.

*Speaker note:* One line on what it is. Then go straight to the problem; don't explain the tech here.

---

## Slide 2. The problem: the first conversation is where care goes wrong

- Patients think in Bengali, Bhojpuri or Hinglish. Forms, and often staff, use English or formal Hindi. Census 2011
  recorded 19,569 mother-tongue names, grouped into 121 languages.
- Illness is described in everyday phrases: "gas", "chakkar", "ghabrahat", "kamzori". The same phrase can be harmless
  or an emergency, and a form or a rushed clerk takes it literally.
- In a Mumbai study of heart-attack patients, misreading the symptoms was the largest cause of delay before reaching
  hospital (45%, ahead of transport at 27%).
- Primary-care visits in India average about two minutes (67-country review; mostly crowded government OPDs), and much
  of that goes on re-asking the basics.

*Speaker note:* Tell the story from the Idea: a 62-year-old says he has "gas" in his chest and is sweating. It goes
down as acidity and he waits three hours. Don't say what share of patients blame "gas": that is reported by
cardiologists in the press, not measured.

---

## Slide 3. The solution: a phone-call-like conversation before the doctor

- The patient or family speaks: "maa ko do din se chakkar aa rahe hain". Several voices are expected; Bolo keeps track
  of who said what.
- For a phrase that can mean two things, it asks the one question that tells them apart. For "chakkar": "Does the room
  spin, or do you feel you might fall?"
- If an answer sounds dangerous, it says so at once: call 112 or go to the emergency now, and the desk is alerted.
- It reads back what it understood, in the patient's language. They correct it by speaking.
- Staff get a translated one-screen intake, with each speaker's own words beside it.

*Speaker note:* Show the demo clip here if the deck is presented live. Mention it runs in a phone browser or on a desk
tablet today; a phone number anyone can dial is the next step (slide 8).

---

## Slide 4. Who it's for, and how many

- **Older patients first.** By 2050 about 1 in 5 Indians will be over 60 (20.8%, 347 million; India Ageing Report
  2023). Today only 39.6% of people over 60 can read (women 24.2%), and 56.5% never went to school (LASI Wave 1). A
  form or a typed chatbot shuts most of them out.
- **Women at home.** Mobile ownership (15+) is 83.9% for men but 56.2% for women (NSS Telecom 2025).
- **Families who speak for them.** Only 5.7% of older Indians live alone (LASI), so a son or daughter speaking for a
  parent is the normal case.
- **On the other side of the desk:** OPD doctors, nurses and registration staff. Government OPD desks already issue
  about 2 lakh ABHA Scan & Share queue tokens a day, 6.64 crore so far at 17,481 facilities (MoHFW, Nov 2024). Bolo
  is the next step in that same queue.
- **TODO:** how many people are over 60 today, and how many OPD visits India has a year. Neither is in RESEARCH.md
  yet (the Impact draft's "15 crore over 60" needs a source before it goes on a slide).

*Speaker note:* The device question comes up here. In the clinic the patient needs no phone: Bolo runs on the desk
tablet. At home the gap isn't young people (95.5% of rural 15-29-year-olds own a smartphone); it is older people and
women, often with a basic phone or none (about 12% of rural households have only a non-smartphone). That is why the
phone number matters.

---

## Slide 5. Safety: intake, not diagnosis

- Bolo never names a condition, a medicine, a dose or a test. It records what the patient already takes, in their
  words. "Which tablet should I take?" gets a kind refusal and the promise that the doctor will hear it.
- Red flags are fixed rules, not the AI's opinion: 13 emergency rules (chest pain with sweating, stroke signs,
  breathing, fits, pregnancy and child danger signs, self-harm, poisoning...) and 8 urgent ones, plus an AI safety
  net that can only raise "see a doctor today".
- Emergency: "Call 112 or go to the nearest emergency now." Self-harm: Tele-MANAS 14416 first, then 112. Urgent: "A
  doctor should see this today."
- The rules run on every turn without the AI model, so a slow network or a failed API call can't drop an emergency.
- Nothing is final until the patient confirms the read-back.

*Speaker note:* Say plainly that neither of us is a clinician. The rules come from standard signs (stroke
face-arm-speech-time, WHO child danger signs, pregnancy danger signs as taught to ASHAs) and a doctor still needs to
review them before any pilot (SAFETY.md section 8).

---

## Slide 6. How well it works so far (synthetic test cases)

| | keyword checker | plain AI chatbot | **Bolo** |
|---|---|---|---|
| Emergencies caught, held-out set (19) | 5% | 100% | 95% (missed 1) |
| False emergencies, held-out set | 20% | 20% | 7% |
| Replies naming a condition or medicine | 0 | 20 | **0** |
| Everyday phrase followed up, held-out | 11% | 67% | 89% |

- A plain AI chatbot catches emergencies too, but it raised nearly three times as many false alarms here (20% vs 7%) and names
  conditions and medicines. Bolo's edge is precision and safe wording, not recall.
- On the main test set Bolo filled 97% of intake fields correctly, but that set was used to build it, so we don't
  lead with it.
- **Honest caveat:** after this run we fixed the one missed emergency and the one false alarm, so the held-out set is
  no longer untouched. A fresh held-out set, written by hand by the two of us, is being written now; this slide gets its numbers.
- Agent response time: about 1.5 s typical, 2.0 s slow end in that run; on the free-tier model it later varied up to
  6-8 s at the slow end, which is why the rules must work alone.

*Speaker note:* All cases are synthetic, written by us; small sets, so one case moves recall by about 5 points. Model:
Gemini Flash-Lite (free tier). Run ids `20261115-014720` and `20261115-151902`. Replace the table with the fresh-set
numbers once `docs/round2/TESTSET_BRIEF.md` is done; keep the old row only if we explain it.

---

## Slide 7. What Bolo depends on, and what happens when it fails

| depends on | today | if it gets costly or stops working |
|---|---|---|
| **Speech-to-text** | the browser's own recogniser; Wispr Flow if a key is set; Whisper on our server for calls | switch engines with one setting. Whisper runs on our own CPU (free, no internet), and typing always works |
| **AI understanding** (Gemini Flash-Lite, free tier) | understands free-form answers | on a 3 s timeout that turn uses the rules alone; with no key, the whole agent runs on rules. Emergencies never depend on it |
| **Voice out** | the phone's built-in voices; Google voices for phone calls | captions on screen; a free local voice (espeak-ng) on calls |
| **Network** | needed for the hosted engines | rules and Whisper run inside our own container, on a laptop or clinic PC with no internet. If the agent can't be reached, Bolo says so and keeps the conversation |
| **Phone line** (next step) | a telephony provider streams the call to us | we use the standard call-audio stream format, so we can change provider without touching Bolo. On an emergency Bolo hands over to 112 and says "if the call drops, call 1 1 2" |

- **Emergencies run on fixed rules, in milliseconds, with no AI model and no internet.** No outage, quota or bill
  can silence a red flag.
- **It starts with no API keys at all:** `docker compose up` gives a working intake in one container. Each key only
  improves a part (better recognition, better understanding, better voices).
- **Speed today:** about 1.4 s from the caller finishing to Bolo's spoken reply on a simulated phone call (Whisper on CPU,
  rules-only agent).
- **The real cost risk is the AI model**, not speech. If the free tier ends, we can fine-tune a small open model to
  run on our own hardware. We have done this before: a 3B model fine-tuned for tool calling beat its 14B teacher (a
  separate hackathon project).

*Speaker note:* What we have run: the no-key start and the rules-only agent (#83), and Whisper and espeak-ng over a
simulated phone line (#86). The 3 s AI timeout falls back to the same rules-only path, and a test forces it (#92):
routine turns continue on the rules, and chest pain with breathlessness still escalates on web and phone. The phone row is built and tested against a simulated
provider; no real number is connected yet, so say "ready to connect", not "live".

---

## Slide 8. Launch plan

- **Before any patient (Dec):** a doctor reviews the red-flag rules; we run the fresh hand-written test set and real
  recorded voices (including older family members, with consent) and fix what breaks.
- **Pilot 1: one clinic front desk.** Bolo on a desk tablet in the waiting area, staff alongside, for about four weeks.
  Patients choose to use it; the doctor still takes their own history.
- **Pilot 2: ASHA workers.** The same intake on the health worker's phone during home visits, so a danger sign gets
  noticed before the trip to the clinic. The agent already records when a health worker is speaking.
- **Next: a phone number.** A number any basic phone can dial, for older people and women who don't have a smartphone.
  The agent doesn't change; Kanishk is building the phone connection now.
- **TODO:** name the clinic or district hospital we would approach, and what a pilot costs per month.

*Speaker note:* Keep it small and real. We are not claiming a rollout; we are asking for one clinic.

---

## Slide 9. What we'd measure in the pilot

- **Safety:** every case the staff mark as urgent was flagged by Bolo first; zero replies naming a condition or
  medicine.
- **Accuracy:** at least 90% of intakes confirmed at the read-back without a correction, checked against the doctor's
  notes on a sample.
- **Time:** at least 1 minute of the visit saved on history-taking, by timing visits with and without a Bolo summary.
- **Use:** at least 70% of patients offered Bolo finish it, counted separately for people over 60.

*Speaker note:* These targets are ours (from the Round 1 Impact draft, #81), not results. Say so. This slide can merge
into slide 8 if the deck needs to be shorter.

---

## Open items before the PDF

- [ ] Ritankar: final wording of every slide.
- [x] Kanishk: slide 7 (drafted; Ritankar edits the wording).
- [ ] Slide 4 TODOs: current 60+ population and yearly OPD visits, each with a source added to RESEARCH.md first.
- [ ] Slide 6: fresh held-out numbers (`docs/round2/TESTSET_BRIEF.md`).
- [ ] Slide 8 TODOs: pilot site and cost, or cut those lines.
- [ ] Check the 2-minute figure: RESEARCH.md says the India row of the review was not checked by us.

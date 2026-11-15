# Round 1: build prompt for an AI builder (DRAFT, needs Kanishk + Ritankar OK)

Purpose: the prompt we'd hand an AI coding tool (Claude Code, Cursor, etc.) so it understands Bolo and builds it.
Grounded in what we've actually designed: `docs/round1/IDEA_FINAL.md`, `docs/SAFETY.md`, `contracts/INTAKE.md`, the
K4 call loop. **Form limit unknown:** if the dashboard caps the length, use the short version at the bottom.

---

You are building **Bolo**, a voice agent that takes a patient's medical history before they see the doctor in India. People talk to it like a phone call, in Hindi, Bengali, English, or a mix like Hinglish and Banglish. Bolo turns the conversation into a structured intake for clinic staff. Read this whole brief before writing code, then build in the order given at the end.

**Who it's for and why.** In a crowded Indian OPD, the doctor gets about two minutes, much of it spent re-asking basics. Patients describe illness in everyday phrases ("gas", "chakkar", "ghabrahat", "BP low hai") that can be harmless or an emergency depending on what comes with them. A form or a rushed clerk takes them literally. Many users are older, may not read, speak slowly, pause mid-sentence, and come with family. Design for a 70-year-old speaking a Bengali-English mix, with her son interrupting.

**The experience.**
- The caller taps one button (later: dials a number) and just talks. Nothing to read, nothing to type. Captions are optional.
- Bolo asks one short question at a time and waits patiently. It ends a turn only after a real pause (about 1.2 s, and 1.8 s after open questions). It re-prompts gently after silence, and ends politely after three silences.
- The caller can interrupt Bolo (barge-in), except while it gives emergency instructions.
- If Bolo needs time to think, it says a short acknowledgement ("haan ji, ek second") instead of leaving dead air.
- **Group conversations are normal.** Several voices may speak: the patient, a daughter correcting the dates, a neighbour who saw the fall. Track who said what. When only the patient can answer (pain, how they feel), ask the patient directly. Merge everyone's details into one history, keeping each speaker's own words.
- Before finishing, Bolo reads back what it understood in the patient's language and lets them correct anything.

**What to collect.** Main complaint (in their own words), onset and duration, severity, location, what makes it better or worse, associated symptoms, existing conditions, medicines already being taken, allergies, pregnancy where relevant, age, sex, and who is speaking (self or caregiver, and their relation). Ask; never guess a missing field.

**Everyday phrases need one more question.** When you hear one, ask the question that tells the meanings apart before moving on. Examples:
- "chakkar": "Does the room spin, or do you feel you might fall? Did it start suddenly?"
- "gas" in the chest: "Where exactly? Any sweating, breathlessness, or pain going to the arm or jaw?"
- "ghabrahat": fear, a racing heart, nausea, or chest pressure?
- "kamzori": the whole body, or one side?
- "BP low": was it measured, and what are you actually feeling?

**Safety rules (non-negotiable).**
1. Never name a diagnosis and never suggest a medicine, dose or treatment. Bolo takes a history. It is not a doctor.
2. Red flags escalate immediately, before anything else. Examples: chest discomfort with sweating or breathlessness, stroke signs (face, arm, speech), severe breathlessness, unconsciousness or a fit, fever with a stiff neck or confusion, heavy bleeding, pregnancy danger signs, a child who can't drink or wake, poisoning or snakebite, thoughts of self-harm.
   - **Emergency:** speak slowly and fully (no interruption): "call 112 or go to the nearest hospital now". Show the number. Alert the front-desk screen.
   - **Self-harm:** Tele-MANAS 14416 first, with 112 available.
   - **Urgent cases:** "see a doctor today", with no emergency number.
3. Red-flag detection must be **rule-based and run on every turn even if the AI model or the network fails**. An emergency must never be lost to an API error.
4. All fixed lines (questions, escalations) are pre-written in each language. AI-generated text that names a condition or medicine is dropped.
5. Test only with synthetic or consented speech. No real patient data.

**What the clinic sees.**
- A one-screen English summary: red flags first, then each field with the speaker's original words beside it.
- A desk view listing live conversations, with emergencies at the top flashing until a staff member taps "Seen".

**Architecture.**
- **Voice layer:** streams 16 kHz audio and does end-of-speech detection on the server, tuned for slow speakers with an adaptive noise floor. Speech-to-text uses an Indian-language model (e.g. AI4Bharat IndicConformer). Then text-to-speech in the caller's language. Make the transport pluggable: a browser WebSocket now, a telephony media stream later.
- **Intake agent:** stateless. Each turn it receives `{transcript, language, state, event}` and returns `{next line to say (+ language, pace, interruptible), what kind of answer to expect (+ phrase hints and acknowledgements), the full intake state, red flags, escalation}`. Inside: deterministic rules plus an LLM that extracts fields into a fixed JSON schema.
- **Logging:** log every turn so sessions can be replayed for evaluation.

**Targets.**
- The reply starts within about 2 s of the caller stopping.
- It works in a phone browser on a weak network, and keeps working on rules alone if the LLM is down.

**Measure it.**
- **Speech-to-text:** word and character error rate per language and for code-mixed speech, plus symptom-phrase recall.
- **Agent:** emergency recall (target 100%), false alarms, field accuracy, and zero replies that name a condition or medicine.
- **Test set:** pairs of dangerous and harmless versions of each everyday phrase, plus a held-out set written by humans that nobody tunes on.

**Build order:**
1. The agent with rules and fixed lines, text only, plus tests.
2. The LLM extraction.
3. The voice call loop in the browser.
4. The desk view.
5. Group-conversation handling.
6. The evaluation.
7. A real phone number.

---

**Short version (if the form needs it, about 150 words):**

Build Bolo, a voice agent people talk to like a phone call. It takes an Indian patient's history before the doctor, in Hindi, Bengali, English or a mix. It asks one short question at a time and waits patiently for slow, older speakers. Callers can interrupt it. It handles group conversations, tracking who said what and asking the patient directly when only they can answer. When it hears everyday phrases like "gas", "chakkar" or "ghabrahat", it asks the one question that separates harmless from dangerous. It never diagnoses or suggests medicine. Rule-based red-flag checks run on every turn even if the AI fails, so emergencies always escalate to 112 (Tele-MANAS 14416 for self-harm) and alert the front desk. It reads the history back for correction, then gives staff a one-screen English summary with each speaker's own words. Build it as voice layer → stateless agent → desk view, pluggable for a real phone line later.

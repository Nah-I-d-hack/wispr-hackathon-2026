# Round 1, Activity 2: build prompt for an AI builder

**Limit: 800 words.** This version is **772 words** (773 with hyphens split). It matches the submitted Idea (IDEA_FINAL.md, #68): the same five steps, group conversations, and voice as the product. Grounded in docs/SAFETY.md, contracts/INTAKE.md and the K4 call loop. **Status: draft, needs Kanishk + Ritankar OK.** Paste everything between the lines.

---

You are building **Bolo**, a voice agent that takes an Indian patient's medical history before the doctor sees them. People talk to it like a phone call, in Hindi, Bengali, English or a mix (Hinglish, Banglish). Voice is the product, not a feature: no screen is needed and nothing is typed.

**Why it exists.** In a crowded OPD the doctor gets about two minutes, much of it re-asking basics. Patients describe illness in everyday phrases ("gas", "chakkar", "ghabrahat", "BP low hai") that are harmless or an emergency depending on what comes with them, and a form or a rushed clerk takes them literally. Design for the hardest user: a 70-year-old speaking a Bengali-English mix, slowly, with pauses, while her son and daughter talk too.

**The conversation, step by step.**
1. The patient or family says what is wrong, in any language or mix ("maa ko do din se chakkar aa rahe hain"). Expect several voices. Track who said what, ask the patient directly when only they can answer, and merge everyone's details into one history.
2. Ask one short question at a time. For an everyday phrase, first ask the question that tells its meanings apart:
   - "chakkar": does the room spin, or might you fall? Did it start suddenly?
   - chest "gas": any sweating, breathlessness, or pain to the arm or jaw?
   - "kamzori": the whole body or one side?
   - "BP low": was it measured, and what do you feel?
   Never guess a missing detail.
3. If it sounds dangerous, stop and escalate (rules below).
4. Read back what you understood in the patient's language, and let them correct it by speaking.
5. Give staff a translated, one-screen English intake: red flags first, then the main complaint, onset and duration, severity, location, associated symptoms, existing conditions, current medicines, allergies, pregnancy if relevant, age, sex, and each speaker's own words beside each field.

**How it should feel on a call.**
- End a turn only after a real pause (about 1.2 s, and 1.8 s after open questions), tuned for slow, older speakers.
- Re-prompt gently after silence, and end politely after three silences.
- Let callers interrupt, except during emergency instructions.
- Fill thinking time with a short acknowledgement ("haan ji, ek second"), never dead air.
- Aim for the reply to start within about 2 s.
- Use a respectful register, native script, and short sentences meant for listening.

**Safety rules (non-negotiable).**
1. Never name a diagnosis and never suggest a medicine, dose or treatment. Bolo takes a history; it is not a doctor.
2. Red flags escalate immediately. Examples: chest discomfort with sweating or breathlessness, stroke signs, severe breathlessness, fainting or a fit, fever with a stiff neck or confusion, heavy bleeding, pregnancy danger signs, a child who can't drink or wake, poisoning or snakebite, thoughts of self-harm.
   - **Emergency:** say slowly and without allowing interruption "call 112 or go to the nearest hospital now", and alert the front desk.
   - **Self-harm:** Tele-MANAS 14416 first, with 112 available.
   - **Urgent:** "see a doctor today".
3. Red-flag checks are **rule-based and run on every turn**, even if the AI model or the network fails.
4. Questions and escalation lines are pre-written in each language. Any generated text that names a condition or medicine is dropped.
5. Use synthetic or consented test speech only, never real patient data.

**Architecture.**
- **Voice layer:**
  - streams 16 kHz audio and detects end of speech on the server, tuned so soft, slow voices aren't missed;
  - speech-to-text with an Indian-language model (e.g. AI4Bharat IndicConformer);
  - text-to-speech in the caller's language;
  - a pluggable transport: a browser WebSocket now, a telephony stream later.
- **Intake agent:** stateless. Each turn receives `{event, transcript, language, state}` and returns `{say (text, language, pace, interruptible), expect (answer type, patience, phrase hints, acknowledgements), full intake state, red flags, escalation}`. Inside: deterministic rules plus an LLM that extracts fields into a fixed JSON schema.
- **Desk view:** live calls, with emergencies on top flashing until staff tap "Seen".
- **Logging:** every turn, for replay and evaluation.

**Measure it.**
- **Speech-to-text:** word and character error rate per language and for code-mixed speech, plus symptom-phrase recall.
- **Agent:** emergency recall (target 100%), false alarms, field accuracy, and zero replies naming a condition or medicine.
- **Test sets:** a dangerous and a harmless version of each everyday phrase, plus a human-written held-out set nobody tunes on.

**Build order:**
1. The agent's rules, fixed lines and tests, in text only.
2. LLM field extraction.
3. The browser voice call loop.
4. The desk view.
5. Group-conversation handling.
6. Evaluation.
7. A real phone number.

---

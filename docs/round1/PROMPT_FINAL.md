# Round 1, Activity 2: Prompt (candidate, needs Kanishk + Ritankar OK)

*[R] Built on Kanishk's draft (#66) and our agent, tuned to the form's rubric (`docs/round1/RUBRIC_PROMPT.md`): the
form's four headings, what people say and what Bolo says back at each step (voice flow is weighted most), a
concrete action for each failure case (weighted second), and an architecture + acceptance line (buildability).*

**777 words** (form: 80-800). Paste everything between the lines.

---

Build Bolo, a voice agent that takes a patient's history before they see a doctor in India. People talk to it like a phone call; clinic staff get a one-screen intake. It never diagnoses or suggests medicine.

**Your users and their languages:** Patients at district hospitals and clinics, and the family members who speak for them. Design for the hardest case: a 70-year-old speaking a slow Bengali-English mix while her son interrupts. Languages: Hindi, Bengali, English and code-mixed Hinglish/Banglish, with regional accents (Bhojpuri-tinged Hindi, East Bengal Bengali). Many users can't read or type. Reply in the patient's main language, respectfully ("aap", "apni").

**The voice flow, step by step:**
1. Caller taps one green button (later: dials a number). Bolo: "Namaste. Bataiye, kya takleef hai? Aaram se boliye." (What is troubling you? Take your time.)
2. Caller describes it in their own words: "maa ko do din se chakkar aa rahe hain". Bolo stores the exact words.
3. If it hears an everyday phrase that can be harmless or dangerous, it first asks the one question that separates them:
   - "chakkar": "Does the room spin, or do you feel you might fall? Did it start suddenly?"
   - chest "gas": "Any sweating, breathlessness, or pain going to the arm or jaw?"
   - "kamzori": "The whole body, or one side?"
4. Then one short question per turn, only for what is still missing: since when, age, anything else (fever, vomiting, breathing), long-standing illness (sugar, BP), current medicines. Never re-ask, never guess.
5. Several voices are normal. If a daughter adds "she hasn't eaten since Tuesday", keep it, tagged with who said it. When only the patient can answer, ask the patient directly.
6. Red flags interrupt any turn. Example: chest "gas" plus sweating at 62. Bolo says slowly, uninterruptibly: "Yeh zaroori hai. Abhi 1-1-2 par phone kijiye, ya turant sabse paas ke aspataal jaiye." Show a big 112 button and alert the front desk. Self-harm: Tele-MANAS 14416 first, plus 112. See-a-doctor-today cases (fever over three days): say so, no emergency number.
7. Read-back: "Maine yeh samjha: do din se chakkar, kamra ghoomta hai, 72 saal. Kya yeh sahi hai?" "Yes" finishes. A correction ("nahi, teen din se") replaces the value; read back again.
8. Close: "Dhanyavaad. Aapki baat doctor tak pahunch jayegi."

Timing: end the caller's turn after 1.2 s of silence, 2.8 s after open questions or for older speakers. If a reply takes over 1 s, say "Haan ji, ek second" instead of dead air. Callers can interrupt Bolo, except during emergency instructions.

**What the product says or shows back:**
- Spoken: only pre-written lines per language (questions, escalations, read-back), so medical wording is never improvised. One question per turn, under 20 words. Emergency numbers digit by digit.
- Caller screen: optional live captions, a big call/hang-up button; nothing needs reading.
- Clinic summary (English, one screen): red flags first, then complaint, duration, severity, associated symptoms, conditions, medicines, allergies, age, sex and who spoke, each with the original words beside it.
- Desk view: live calls, emergencies flashing on top until staff tap "Seen".

**Noise, accents, mixed languages and misheard input:**
- **Noisy OPD:** adaptive noise floor, so soft voices aren't cut off. Empty or garbled transcript: "Maaf kijiye, awaaz saaf nahi aayi. Ek baar phir bataiye?" After two failures, switch to yes/no questions.
- **Accents:** an Indian-trained speech model (e.g. AI4Bharat IndicConformer) with the expected languages as hints, plus phrase hints for the next answer (numbers after "since when"). Never correct the caller's dialect.
- **Mixed languages:** accept any mix mid-sentence; reply in the main language, switching only after two turns in another; store words verbatim.
- **Misheard input:** echo durations, ages and medicine names in the read-back; corrections replace values. If a red-flag word may have been heard, ask directly ("Kya seene mein dard hai?") rather than ignore it.
- **Crosstalk:** "Ek-ek karke boliye" (one at a time).
- **Silence:** gentle re-prompt; after three, end politely and save what was collected.
- **Failures:** red-flag rules are deterministic and run every turn even if the LLM or network fails; on errors, play a canned line and keep the intake state.
- **Out of scope:** "Which tablet should I take?" gets "Only the doctor can answer that; I'll make sure they hear exactly what you said."

Architecture: a browser call screen streams 16 kHz audio to a server that detects end of speech, transcribes, calls a stateless intake agent (rules plus an LLM filling a fixed JSON schema) and speaks the reply. Done when a scripted test set of dangerous and harmless versions of each phrase gives 100% emergency recall and zero replies naming a condition or medicine.

---

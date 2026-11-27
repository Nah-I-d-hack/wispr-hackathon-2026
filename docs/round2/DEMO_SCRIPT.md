# Round 2 demo video: shot list (3:00 max)

*[R] Draft for Kanishk (records and edits) and Ritankar (wording). All patient lines are synthetic and spoken by us.
Romanised here; speak them naturally. Timings are targets; cut Scene 3 first if we run long.*

**Setup before recording**
- `docker compose up` on the recording laptop, with `GEMINI_API_KEY` set (better understanding). Do one dry run with
  no keys too, so we can honestly say "this also works with no keys".
- Chrome, window at phone width for `/`, a second window or tablet on `/desk`.
- Screen recorder with system audio (Bolo's voice) and mic (our voice). Captions on.
- Do a full run-through first: the lines below were checked against the agent, but re-check after the last merge.

---

## 0:00 - 0:15 Hook (voice-over on slide 1 or a black screen with text)

> "A 62-year-old says he has 'gas' in his chest and he's sweating. At a busy desk that goes down as acidity. Bolo is
> a voice agent that takes the history first, in the patient's own words and language."

## 0:15 - 1:05 Scene 1: a daughter calls about her mother (web, Hindi, `/`)

Show: the mic button, captions, and the "what we understood" card filling in.

| who | line | what to point at |
|---|---|---|
| Bolo | greeting | spoken in Hindi, captions in both scripts |
| Daughter | "maa ko do din se chakkar aa rahe hain, main unki beti bol rahi hoon" | card: caregiver, chief complaint "dizziness", 2 days |
| Bolo | "Chakkar kaisa hai? Kamra ghoomta hai, ya lagta hai gir jayenge...?" | **the one question that tells two meanings apart** (on-screen caption: "same word, different urgency") |
| Daughter | "kamra ghoomta hua lagta hai" | |
| Bolo | asks age | |
| Daughter | "pachattar saal" | |
| Bolo | "Iske saath aur kuch ho raha hai?" / "Pehle se koi bimari?" / "Koi dawai?" | three quick questions; Daughter answers "nahi" to each. Speed up 2x in the edit |
| Bolo | **read-back**: "Maine yeh samjha: maa ko do din se chakkar..., 75 saal. Kya yeh sahi hai?" | the read-back is the safety step |
| Daughter | "nahi, teen din se" | **a spoken correction**, card changes 2 days -> 3 days, marked "corrected" |
| Bolo | "Maine yeh samjha: maa ko teen din se chakkar..., 75 saal. Kya yeh sahi hai?" | the new duration, read back |
| Daughter | "haan" | done |

Cut to the clinician summary in English (2 seconds on screen): her own words next to the English.

## 1:05 - 1:35 Scene 2: same app, Bengali (web, `/`) - optional, cut if long

| who | line |
|---|---|
| Caregiver | "amar mayer teen din dhore jor, boyos sottor" |
| Bolo | follow-up in Bengali |
| ... | jump-cut to the Bengali read-back and "hya" |

*Don't correct the duration in this scene: fever above 3 days correctly switches Bolo to the urgent path (U1), which
is a different story. Use "na, aar kichhu na" to the follow-ups.*

Caption: "Hindi, Bengali, English, or a mix. Nothing to read, nothing to type."

## 1:35 - 2:25 Scene 3: a phone call, and an emergency (`/call`, plus `/desk` side by side)

Show: the call screen (no buttons to read), and the desk screen beside it.

| who | line | what to point at |
|---|---|---|
| Bolo | "Namaste, yeh Bolo hai..." | sounds like a phone call |
| Son | "papa ko chhati mein gas ho rahi hai" | the word "gas" again |
| Bolo | "Gas thik kahan mehsoos ho rahi hai, pet mein ya seene mein? Kya pasina, saans phoolna...?" | **asks, doesn't assume** |
| Son | "haan pasina bhi aa raha hai, baasath saal ke hain" | |
| Bolo | "Yeh gambhir lag raha hai. Aapko abhi emergency madad se joda ja raha hai... 1 1 2" | spoken in full, can't be interrupted; caption: "red flags run on fixed rules: no AI, no internet needed" |
| Desk | flashes **EMERGENCY**, beeps; staff taps "Seen, going now" | the front desk knows before the family walks up |

## 2:25 - 2:50 Scene 4: what the clinic gets (`/desk`, clinician summary)

- One screen: emergencies on top, then each intake in English with the patient's own words beside it.
- Caption: "Bolo never diagnoses and never names a medicine. It takes the history and escalates."
- Optional 3-second flash of the eval line from the deck (only once the fresh held-out numbers are in).

## 2:50 - 3:00 Close

> "Bolo starts with one command and no API keys. Next: a phone number anyone can dial."

Show `docker compose up` in a terminal for one second, then the team name.

---

**Checklist before upload**
- [ ] Under 3:00 (check the exported file, not the timeline).
- [ ] Every Bolo line audible and captioned; no real patient data; a "synthetic voices, written by the team" note in
      the description.
- [ ] No claim on screen that we didn't run (no "live phone number", say "ready to connect").
- [ ] Both humans watched it before it goes in the submission.

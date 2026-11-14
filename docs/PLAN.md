# PLAN

**Hackathon:** India Runs on Voice (Scaler × Wispr), **Healthcare track**. Rules and dates: `docs/HACKATHON.md`.
Key deadlines (IST): Round 1 closes **26 Nov** · Round 2 build due **29 Nov** · finale **13 Dec**.

Team: R = Ritankar (GitHub `CyberRik`) · K = (GitHub `ActiveMasquerade`) · 3rd member: *decide before S1, team locks
after the first submission*.

Status of each task is tracked in its GitHub issue (`python scripts/collab.py status`), not in this file.
The table is parsed by `collab.py bootstrap`, so keep the column layout. Add new rows for your own lane freely.
Round 2 tasks get added on 27 Nov, once the problem statement is out.

## Lanes (agreed Nov 14: option A, #16; voice output is K's, #17)

| lane | owns |
|---|---|
| **R**: intake agent | decides *what* to say: structuring the transcript into the intake, follow-ups, read-back, corrections, red flags and escalation; the intake test set and the agent's evaluation (field accuracy, red-flag recall, false alarms); drafts the contract |
| **K**: voice + app | the whole voice layer (speech-to-text, language ID, text-to-speech in the patient's language), app/UI, deployment, demo setup and video; voice evaluation (transcription accuracy per language and code-mixed, end-to-end latency) |
| **S**: shared | R1 research, registration, round submissions (S1-S3), finale pitch, README, decisions both humans must make |

**Contract (C1):** K sends `{transcript, detected language, audio metadata}`; R returns `{next utterance text, its
language and register, intake state, red flags}`; K turns the text into speech.

## Tasks

| id | task | owner | depends on | due (IST) |
|---|---|---|---|---|
| S0 | Humans: register on the dashboard (Wispr Flow email + verified phone), install Wispr Flow, join Discord, fix the team roster | S | - | Nov 16 |
| K1 | Repo + collab setup: collab.py, CLAUDE.md, onboarding, plan, labels and issues | K | - | Nov 14 |
| R1 | Problem research (shared): who does healthcare symptom intake serve (patients, ASHA workers, clinic front desks), which languages, what exists, what must never happen. `docs/RESEARCH.md`, 1 to 2 pages | S | - | Nov 17 |
| C1 | Contract: intake schema + agent I/O in `contracts/INTAKE.md` (R drafts, K approves as a `CONTRACT:` PR) | R | - | Nov 17 |
| S1 | Round 1 "Idea" submission (Healthcare). R's draft is `IDEA.md` (mother-tongue users, older people as the hardest case); settle the open questions, humans submit | S | R1 | Nov 18 |
| K2 | Tech spike: speech-to-text + language ID for Hindi, Bengali and code-mixed speech, and text-to-speech in those languages. Compare latency, cost (free tiers), and quality on 10 recorded test utterances. `docs/SPIKE.md` | K | - | Nov 19 |
| S2 | Round 1 "Prompt" submission (opened Nov 13). Draft in `docs/round1/PROMPT.md` | S | S1 | Nov 21 |
| R2 | Safety + evaluation plan: intake only, never diagnosis; red-flag symptoms trigger an escalation message; a test set of utterances per language with expected fields and flags | R | R1 | Nov 21 |
| R3 | Intake agent v1 behind the C1 contract: transcript in, next utterance + intake state + red flags out; scored on the R2 test set | R | C1, R2 | Nov 25 |
| K3 | Prototype skeleton: speak a complaint, the app calls the agent through C1 and speaks its reply; shows the intake summary + red flags; runnable locally and deployable. The Round 2 build extends this | K | K2, C1 | Nov 25 |
| S3 | Round 1 "Impact" submission (opens Nov 20). Draft in `docs/round1/IMPACT.md` | S | S2, R1 | Nov 25 |
| S4 | Round 2: read the problem statement the moment it drops (Nov 27), split into R/K tasks, add rows here | S | - | Nov 27 |

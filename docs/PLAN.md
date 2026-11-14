# PLAN

**Hackathon:** India Runs on Voice (Scaler × Wispr), **Healthcare track**. Rules and dates: `docs/HACKATHON.md`.
Key deadlines (IST): Round 1 closes **26 Nov** · Round 2 build due **29 Nov** · finale **13 Dec**.

Team: R = Ritankar (GitHub `CyberRik`) · K = (GitHub `ActiveMasquerade`) · 3rd member: *decide before S1, team locks
after the first submission*.

Status of each task is tracked in its GitHub issue (`python scripts/collab.py status`), not in this file.
The table is parsed by `collab.py bootstrap`, so keep the column layout. Add new rows for your own lane freely.
Round 2 tasks get added on 27 Nov, once the problem statement is out.

## Lanes (proposed by K, R to confirm or change in its first PR)

| lane | owns |
|---|---|
| **R**: research, safety, evaluation | user/clinical research, the intake schema, red-flag and escalation rules, test utterances and evaluation, write-ups |
| **K**: build and ship | voice pipeline (speech in, language ID, structuring), app/UI, deployment, demo video |
| **S**: shared | registration, round submissions, decisions both humans must make |

## Tasks

| id | task | owner | depends on | due (IST) |
|---|---|---|---|---|
| S0 | Humans: register on the dashboard (Wispr Flow email + verified phone), install Wispr Flow, join Discord, fix the team roster | S | - | Nov 16 |
| K1 | Repo + collab setup: collab.py, CLAUDE.md, onboarding, plan, labels and issues | K | - | Nov 14 |
| R1 | Problem research: who does healthcare symptom intake serve (patients, ASHA workers, clinic front desks), which languages, what exists, what must never happen. `docs/RESEARCH.md`, 1 to 2 pages | R | - | Nov 17 |
| S1 | Round 1 "Idea" submission (Healthcare). R's draft is `IDEA.md` (mother-tongue users, older people as the hardest case); settle the open questions, humans submit | S | R1 | Nov 18 |
| K2 | Tech spike: speech-to-text + language ID for Hindi, Bengali and code-mixed speech, LLM structuring into an intake form. Compare latency, cost (free tiers), and quality on 10 recorded test utterances. `docs/SPIKE.md` | K | - | Nov 19 |
| S2 | Round 1 "Prompt" submission (opened Nov 13). Draft in `docs/round1/PROMPT.md` | S | S1 | Nov 21 |
| R2 | Safety + evaluation plan: intake only, never diagnosis; red-flag symptoms trigger an escalation message; a test set of utterances per language with expected fields and flags | R | R1 | Nov 21 |
| K3 | Prototype skeleton: speak a complaint, get a structured intake summary + red-flag check, runnable locally and deployable. The Round 2 build extends this | K | K2, R2 | Nov 25 |
| S3 | Round 1 "Impact" submission (opens Nov 20). Draft in `docs/round1/IMPACT.md` | S | S2, R1 | Nov 25 |
| S4 | Round 2: read the problem statement the moment it drops (Nov 27), split into R/K tasks, add rows here | S | - | Nov 27 |

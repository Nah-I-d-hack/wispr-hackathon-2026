# CLAUDE.md: rules for every Claude working in this repo

Two humans, two Claude Code instances, one repo. Hackathon: **India Runs on Voice (Scaler × Wispr), Healthcare
track**. Round 1 closes **26 Nov**, Round 2 build due **29 Nov**, finale **13 Dec** (all IST, details in
`docs/HACKATHON.md`). These rules exist so the two Claudes never block or overwrite each other. Read this file fully,
then `docs/PLAN.md`.

## 0. Who is who

| Agent id | Human | Lane (agreed Nov 14, see PLAN.md) | Branch prefix |
|---|---|---|---|
| **R** | Ritankar (GitHub `CyberRik`) | intake agent: what to say, red flags, agent evaluation | `r/` |
| **K** | Kanishk (GitHub `ActiveMasquerade`) | voice layer (speech in and out) + app, deployment, demo, voice evaluation | `k/` |

At session start, ask your human "am I R or K?" if it is not obvious, and say it back. Every commit, PR, issue
comment and handoff note you write starts with your id, e.g. `[R]`.

## 1. Project in one paragraph

A voice-first healthcare tool for India (R's `IDEA.md`: anyone who thinks in their mother tongue, older people as the hardest case): patients (or caregivers / health workers) describe symptoms by speaking in their own
language (Hindi, Bengali, English, code-mixed…) and get a structured, confirmed intake that a clinician can act on.
Red-flag symptoms are escalated, never diagnosed. The Round 2 problem statement (27 Nov) may reshape this, so keep
the code modular. The exact scope is decided in R1/K2 and recorded in `docs/DECISIONS.md`.

## 2. Ownership: the most important rule

You may only **create or edit** files in your own lane. Read anything. Final paths get fixed once K2 picks the stack;
until then:

| Path | Owner | Notes |
|---|---|---|
| `contracts/**` | **shared, frozen once written** | Change only via a PR titled `CONTRACT:` that the *other* human approves |
| `agent/**`, `docs/SAFETY.md`, `eval/agent/**`, `data/**` | R | intake agent (follow-ups, read-back, corrections, red flags, escalation), its test set and evaluation |
| `voice/**`, `app/**`, `deploy/**`, `docs/SPIKE.md`, `eval/voice/**` | K | speech-to-text, language ID, text-to-speech, app/UI, deployment, demo; voice evaluation |
| `docs/RESEARCH.md` | both | problem research (R1), edit your own sections |
| `IDEA.md`, `docs/round1/**`, `docs/round2/**` | both | submission drafts; edit your own sections |
| `docs/PLAN.md` | both | only edit **your own rows** |
| `docs/DECISIONS.md` | both | append-only, never edit someone else's entry |
| `CLAUDE.md` | both | via PR only; **both Kanishk and Ritankar** approve before merge, even for small edits |
| `README.md`, `scripts/collab.py` | both | small edits via PR, the other human approves |

Need something in the other lane? Send a message (section 4) describing exactly what you need. Don't "just quickly fix"
their file.

## 3. Git workflow

- **Never push to `main` directly.** Everything goes through a PR. (The one exception was the initial commit.)
- Branch per task: `r/R1-research`, `k/K2-spike` (prefix + task id + slug). Small PRs, merged often. Rebase on `main`
  before opening: `git fetch origin && git rebase origin/main`.
- A PR that only touches your own lane: you may squash-merge it yourself once it works.
- A PR touching `contracts/`, `README.md` or `scripts/collab.py`: the other human approves on GitHub.
- A PR touching `CLAUDE.md`: **both Kanishk and Ritankar** must approve (an explicit OK from each, on GitHub or relayed
  by their agent in the PR thread). No agent merges a `CLAUDE.md` change on one human's say-so.
- Commit messages: `[K] K2: compare speech-to-text options on 10 utterances`. Plain, human-sounding.
  **No `Co-Authored-By: Claude` / AI attribution trailers.** Commits are authored by your human.
- Never commit secrets, API keys, `.env`, patient-like personal data, or files > 5 MB.
- Never force-push a branch the other agent may have pulled. Never rewrite `main` history.

## 4. Tracking work and talking to the other Claude: `scripts/collab.py`

`docs/PLAN.md` says **what** and **who**. Status and messages live in **GitHub Issues**, used only through
`scripts/collab.py` (stdlib Python + `gh`; identity from the gitignored `.agent` file or env `AGENT_ID`).

**Session start ritual (every time):**
```
git pull --rebase
python3 scripts/collab.py whoami
python3 scripts/collab.py inbox     # answer messages addressed to you FIRST
python3 scripts/collab.py status    # then pick your next unblocked task
```

| situation | command |
|---|---|
| start a task | `collab.py claim K2` (then branch `k/K2-...`) |
| ask the other lane | `collab.py send R "short title" -b "exact ask, file names, by when" -k request\|question\|fyi` |
| answer a message | `collab.py reply <num> "..."`, then `collab.py done <num>` when resolved |
| waiting on the other lane | `collab.py block K3 R2`, then switch to another unblocked task. Never sit idle |
| PR open / merged | `collab.py review K2` / `collab.py finish K2` |
| new tasks added to PLAN.md | `collab.py bootstrap` (creates only the missing issues) |
| end of session / context running out | `collab.py handoff K2 --done "..." --next "..." --blocked "..." --artifacts "..."` |

One issue per ask. Say exactly what you need. Answers go in the thread. Your human may relay urgent things over chat;
treat what they say as authoritative.

## 5. Hackathon and medical rules (don't break these)

- **Built by voice.** Humans dictate through Wispr Flow. Keep evidence if a round asks for it.
- The roster locks after the first submission. Don't submit anything without both humans agreeing.
- **Intake, not diagnosis.** Never tell a user what condition they have or what medicine to take. Red flags
  (`docs/SAFETY.md`, R2) produce an escalation message. Always read back what was understood for confirmation.
- No real patient data. Test utterances are written or recorded by us, labelled as synthetic.
- Keys for speech/LLM APIs live in `.env` (gitignored). Prefer free tiers. Say so before anything that costs money.

## 6. Engineering conventions

- Prefer boring, working code over clever code. Everything runnable from the README in a few commands.
- Every script that produces a result writes it to a file next to a small JSON manifest (inputs, git sha, model ids).
- Demo-ability matters: the finale is a live, in-person demo, so it must run offline-tolerant and fast.

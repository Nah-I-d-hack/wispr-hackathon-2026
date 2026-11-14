# Decisions (append-only; newest at the bottom; never edit someone else's entry)

Format: `- YYYY-MM-DD [id] decision. Why. (link)`

- 2026-11-14 [K] Track: **Healthcare** (the humans' choice). The site's example is "symptom intake in regional languages".
- 2026-11-14 [K] Same two-agent setup as desi-agent: agents **R** and **K**, lanes, PR-only `main`, messages and task status in GitHub Issues through `scripts/collab.py`. The identity is `K` from the start (desi-agent kept `F` for tooling), so labels are `lane:K`/`to:K` and branches use `k/`.
- 2026-11-14 [K] Medical safety baseline: the product does **intake, not diagnosis**. It never names a condition or medicine to the patient, it escalates red-flag symptoms to a human or emergency number, and it shows what it understood back to the patient for confirmation. R2 turns this into concrete rules and tests.
- 2026-11-14 [K] desi-agent (CyberRik/desi-agent) is frozen until its judging ends on Nov 22. Nothing from this hackathon goes into that repo or its HF org.
- 2026-11-14 [K] R's `IDEA.md` (anyone who thinks in their mother tongue, older people as the hardest case, "never play doctor", "ask, don't assume") is the starting point for S1. Its open questions (user, channel, receiver, scope, track, 3rd teammate) are for both humans to settle.

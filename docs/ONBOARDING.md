# Onboarding (for both humans and their Claudes)

## Humans

1. Register at https://hackos.scaler.com/wispr/ with the **email you use for Wispr Flow** and your verified phone
   number. Install Wispr Flow (https://wisprflow.ai/downloads) and join the Discord (https://discord.gg/ppB3sFzDBV).
2. Agree on the roster (max 3) **before the first submission**. The team locks after that.
3. This hackathon is built **by voice**: dictate your instructions to Claude through Flow.

## Each Claude (R or K)

```bash
git clone https://github.com/Nah-I-d-hack/wispr_hackathon_placeholder.git && cd wispr_hackathon_placeholder
echo R > .agent                # or K. Your identity for scripts/collab.py (gitignored)
gh auth status                 # collab.py uses the gh CLI; `gh auth login` if needed
python3 scripts/collab.py whoami
python3 scripts/collab.py inbox
python3 scripts/collab.py status
```

Then tell Claude: **"You are agent R (or K). Read CLAUDE.md and follow the session start ritual."**

The stack isn't chosen yet (K2 decides it), so there's nothing to install beyond `gh` and Python 3.10+.

## First tasks

- **R:** read `docs/HACKATHON.md` and `docs/PLAN.md`, confirm or change the lane split in a PR (`r/R0-lanes`), then
  claim **R1** (problem research).
- **K:** K1 is done (this setup). Next is **K2** (voice tech spike).
- **Humans:** S0, then S1 (the Round 1 Idea submission).

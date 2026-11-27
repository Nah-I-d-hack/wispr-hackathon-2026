# Held-out set v2 (`intake_holdout_v2.jsonl`)

*[R] Fresh held-out cases for the intake agent, replacing v1 (which was used to fix the agent and so no longer gives an
honest number). Brief: `docs/round2/TESTSET_BRIEF.md`.*

## Who wrote what

| ids | written by | count |
|---|---|---|
| `*-v2r-*` | Claude (R's agent), at Ritankar's request, tagged `ai_written_blind` | 24 |
| `*-v2k-*` | Kanishk, by hand (to be added) | ~10 |

The brief asks for human-written cases, because the agent's rules were also written with Claude. Ritankar couldn't
write his share, so the `v2r` cases were AI-written under the blindness rule below. Report the `v2r` and `v2k` numbers
separately as well as together; treat `v2r` as the weaker evidence.

## Blindness rule followed for `v2r`

The writer did not open, read or grep anything in `agent/` (rules, core, prompt lines, README), `eval/agent/results/`,
`data/intake_test_v1.jsonl` or `tests/`. It read only the brief, the rule and idiom definitions in `docs/SAFETY.md`,
the validator, and the first two lines of `data/intake_holdout_v1.jsonl` for the JSON schema (not its wording). Turns
were drafted before reading the SAFETY.md tables, then labelled from the "fires when" definitions as a careful
clinician would expect, not as a guess at what the agent outputs.

Mix (v2r): 13 `hi` / 11 `bn` by `lang`, of which 8 are code-mixed with English; 10 emergency (E1, E2 x2, E3, E7,
E8 x2, E9 x2, E13), 5 urgent (U1, U2, U5, U6, U8), 3 routine, 6 hard negatives.

## Rules

- **Frozen as of the commit that added this file.** No edits to existing cases after the first run.
- **Do not tune the agent on these cases.** Don't read them while changing `agent/`. If the agent is fixed because of
  a failure here, the next honest number needs a v3.
- Validate: `python eval/agent/check_testset.py data/intake_holdout_v2.jsonl` (`ERROR coverage:` lines are expected
  for a set this small).

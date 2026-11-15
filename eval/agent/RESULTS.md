# Agent eval: results and how to read them (R3 v1)

*[R] Run `20261115-014720` (full numbers in `results/20261115-014720/report.md`). Model `gemini-3.5-flash-lite`,
all cases synthetic. Read the caveats before quoting any number.*

| | keyword (K's mock) | plain Gemini chatbot | Bolo, rules only | **Bolo** |
|---|---|---|---|---|
| Emergency recall, held-out (19 cases) | 5% | **100%** | 63% | 95% (missed 1) |
| Emergency recall, main set (37) | 24% | 92% (missed 3 Bengali) | 100%* | **100%*** |
| False emergencies, held-out / main | 20% / 7% | 20% / 15% | 0% / 0% | **7% / 0%** |
| Replies that name a condition or medicine | 0 | **20** | 0 | **0** |
| Everyday phrase followed up, held-out / main | 11% / 19% | 67% / 92% | 89% / 100% | 89% / 100% |
| Intake field accuracy (main) | - | - | 88% | **97%** |
| Agent latency p50 / p95 | - | (not comparable) | 3 ms | 1.5 s / 2.0 s |

\* tuned on this set, so it doesn't show how well the agent handles new wording.

**What holds up.** Bolo matches a plain LLM on catching emergencies while raising far fewer false alarms, never
names a condition or medicine (the plain chatbot did so in 20 replies), asks the follow-up for everyday phrases, and
produces a structured intake (97% field accuracy). The rule layer alone runs offline in milliseconds, which is what
keeps emergencies working when the network or the API fails.

**What doesn't (yet).**
- **Bolo missed one held-out emergency** (hi-h06: can't breathe, can't talk) and raised one false alarm (hi-h18:
  dizziness on standing was tagged as fainting). Both were fixed after this run (`rules.py`: "can't talk" phrases;
  fainting alone is no longer an emergency, per SAFETY.md), together with an urgent escalation that swallowed the
  ghabrahat/self-harm question. **The held-out set is therefore no longer untouched**: the next honest number needs a
  new held-out set, ideally written by a human, not the agent that wrote the rules.
- The plain chatbot caught **every** held-out emergency; Bolo's edge there is precision and safety of wording, not
  recall. Rules alone generalise poorly (63%): the LLM layer is what carries new phrasings.
- Latency p50 1.5 s sits right at the target; p95 2.0 s is inside 3 s. The plain chatbot's latency column includes
  rate-limit pacing and is not comparable.
- Small sets (19 held-out emergencies): one case moves recall by 5 points.
- The judge for "follow-up asked" (baselines only) is the same Gemini model.

# Round 1, Activity 3: Impact (draft, needs Kanishk + Ritankar OK)

*[R] Written to the form's four headings and rubric (`RUBRIC_IMPACT.md`): who benefits and what changes weigh most,
then the measure, then the risk. Numbers come from `docs/RESEARCH.md` (sources there); our own eval numbers from
`eval/agent/RESULTS.md`. Paste everything between the lines.*

**472 words** (478 if hyphens and slashes split; form: 50-500).

---

Who benefits, and roughly how many: Patients who explain their illness in words a clinic doesn't use, and the families who speak for them. First, older patients: India has about 15 crore people over 60 (India Ageing Report 2023), and only 40% of them can read (LASI), so a form or a typed chatbot shuts most of them out; speaking doesn't. Then women at home (only 56% of women own a mobile phone), migrant workers and farmers speaking Bhojpuri-tinged Hindi or Bengali. On the other side of the desk: OPD doctors and registration staff. Government OPD desks already issue about 2 lakh ABHA queue tokens a day at 17,000+ facilities; Bolo plugs into that same queue, so even one district hospital means hundreds of patients a day.

What changes compared with today: Today a patient says "seene mein gas" to a rushed clerk, it is written down as acidity, and they wait hours. The doctor then spends most of a two-minute visit re-asking basics. With Bolo, the patient talks while waiting, in their own language, with the family joining in. Bolo asks the one question that separates harmless "gas" from a heart attack, and a dangerous answer reaches the front desk at once, not at the end of the queue (misread symptoms were the top cause of delay for heart-attack patients in a Mumbai study, 45%). The doctor starts with a one-screen English summary, in the patient's own words, already confirmed by the patient. Nobody has to read, type or speak English.

How you'd know it worked: In a pilot at one district hospital OPD over four weeks:
- Safety: 100% of red-flag cases flagged on our scripted test set before launch, and in the pilot every case staff mark as urgent was flagged by Bolo first; zero replies naming a condition or medicine.
- Accuracy: at least 90% of intakes confirmed at the read-back without a correction, checked against the doctor's own notes on a sample.
- Time: at least 1 minute of the doctor's visit saved on history-taking, measured by timing visits with and without a Bolo summary.
- Use: at least 70% of patients offered Bolo finish a call, including those over 60.

The main risk: Speech recognition is weakest exactly where we need it: older, slow voices in a noisy OPD (studies find much higher error rates for older speakers). A misheard answer could hide a red flag. We limit this three ways: red-flag rules run on every turn even if the AI model fails; Bolo reads everything back for the patient to correct; and if a danger word may have been heard, it asks directly. Bolo never replaces the desk or the doctor. It is an extra pair of ears. A second limit: it needs a phone or tablet and data today; a dial-in number is next.

---

# Round 1 idea: rough direction (draft, open for changes)

*[R] First pass, written to start the discussion. Nothing here is decided. Edit freely.*

**Hackathon:** India Runs on Voice (Wispr x Scaler), https://hackos.scaler.com/wispr/
**Leaning towards:** Healthcare track, for anyone who thinks in their mother tongue. Older people are our hardest test case, not the only user.

## The gap we keep coming back to

A lot of people can't describe what is wrong with them in the language a clinic form, an app or sometimes even the
doctor uses. They think and speak in their mother tongue and mix languages, and the details get lost before care even
starts. This is true for a migrant worker in a new city as much as for someone in a village.

Older people feel it the most: slower speech, forgotten details, often a family member explaining for them. So we
treat them as the **hardest case to design for**: if it works for a 70-year-old speaking Bengali-English mix, it should
work for everyone.

## Direction (not a design)

Something voice-first that lets a patient (or someone speaking for them) say what they are feeling, in whatever language
or mix comes naturally, and turns it into something useful for whoever helps them next. Roughly in the space of
"symptom intake", but how far it goes is open.

## Principles we'd probably want, whatever we build

- **Speak, don't type.** No forms, no reading required.
- **Their language, their way.** Regional languages and code-mixed speech are normal, not edge cases.
- **Ask, don't assume.** If something important is missing, ask a simple follow-up rather than guess.
- **Never play doctor.** Help describe and hand over, not diagnose. Anything that sounds urgent gets pointed to real help.
- **Patient and forgiving.** Slow speech, repetition, changing their mind mid-sentence: all fine.

## Open questions to decide together

1. **Who do we demo with?** Older patient, caregiver speaking for them, a young migrant worker, or a mix?
2. **Where does it live?** Phone call, WhatsApp-style voice note, an app, a kiosk at a clinic or pharmacy?
3. **Who receives the output?** A doctor, an ASHA / health worker, a family member, the person themselves?
4. **Where does it stop?** Just intake? Reminders and follow-ups? Helping with the next visit?
5. **Track:** Healthcare (the user is anyone; older people are the stress test, so we're not tied to the Everyday access track).
6. **Third teammate?** Teams lock after the first submission, so decide before we submit the Round 1 idea.

## What we can reuse from Desi Agent

Multilingual and code-mixed handling (Hindi, Bengali, Hinglish, Banglish), turning free speech into structured fields,
"ask when something is missing" behaviour, and the habit of measuring before/after. Worth keeping in mind, not a plan.

## Notes from the hackathon page

- Round 1 has three steps (Idea, Prompt, Impact) and closes 26 Nov. Round 2 is one shared problem statement for
  everyone (27 Nov, build due 29 Nov), so the track mostly shapes Round 1.
- Builds are done hands-free with Wispr Flow; we should practise dictating into our tools before Round 2.

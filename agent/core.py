"""[R] Intake agent v1 (R3) behind contract C1 (contracts/INTAKE.md). Entry point: turn(request) -> response.

Layers, in order of authority:
1. rules.py (deterministic): signs, red flags, idioms, question order. Always runs; an LLM failure can't drop a flag.
2. Gemini (llm.py): understands the utterance into intake fields and extra signs, and writes the patient read-back.
   Its signs are only ever *added* to the rule engine's. If it fails or times out, the turn still completes.
3. Fixed lines (lines.json): every question and escalation is pre-written per language, so the agent never
   improvises medical wording.
"""
from __future__ import annotations

import copy
import json
import os
import re
import time
from pathlib import Path

from . import llm, rules
from .text import light, translit

CONTRACT = "1.1"   # accepts any 1.x request; answers with the request's version (1.1 fields are additive)
HERE = Path(__file__).resolve().parent
LINES = json.loads((HERE / "lines.json").read_text(encoding="utf-8"))
SCRIPT = {"hi": "Deva", "bn": "Beng", "en": "Latn"}
LANGS = ("hi", "bn", "en")
EVENTS = ("start", "utterance", "no_speech", "end")
CHANNELS = ("web", "phone_in", "phone_out")
IDIOM_ORDER = ["I_gas", "I_ghabrahat", "I_kamzori", "I_sunn", "I_chakkar", "I_saans_phoolna", "I_sugar", "I_jalan",
               "I_bp", "I_garmi_thand", "I_tension"]
LLM_TIMEOUT = float(os.environ.get("AGENT_LLM_TIMEOUT", "3.0"))
LLM_RETRIES = int(os.environ.get("AGENT_LLM_RETRIES", "0"))

# words that must never reach the patient unless the patient said them first (guard on LLM-written text)
_BANNED = re.compile(r"\b(heart attack|attack|stroke|gastritis|acidity|infection|cancer|tumou?r|migraine|pneumonia|"
                     r"covid|dengue|malaria|typhoid|tablet|dose|mg|paracetamol|antibiotic|diagnos\w*|probably|"
                     r"likely|could be|sounds like)\b")


# ---------------------------------------------------------------- state
def _new_state(lang: str) -> dict:
    missing = lambda: {"value": [], "status": "missing"}  # noqa: E731
    return {
        "speaker": {"role": "unknown", "relation": None},
        "patient": {"age_years": None, "age_band": None, "sex": "unknown"},
        "chief_complaint": {"value": None, "said": None, "status": "missing"},
        "symptoms": [],
        "history": {"conditions": missing(), "medicines_taken": missing(), "allergies": missing(),
                    "pregnant": {"value": None, "status": "missing"}},
        "missing": ["chief_complaint"],
        "phase": "collecting",
        "lang": {"reply": lang, "script": SCRIPT[lang], "register": "respectful"},
        "no_speech_count": 0,
        "transcript_log": [],
        "_internal": {"signs": [], "idioms_seen": [], "asked": [], "raised": [], "pending": None, "temp_f": None,
                      "duration_days": None, "llm_fail": 0, "slow": False, **_r4_defaults()},
    }


def _r4_defaults() -> dict:
    """R4 bookkeeping (phone_in work). Added with setdefault, so states saved by older agent versions still load."""
    return {"reasked": [], "unclear": {}, "queue": [], "stt_fail": 0, "yn_mode": False, "yn": {}, "yn_signs": [],
            "rf_asked": [], "lang_cand": None, "last_q": None, "duration_coarse": None, "age_coarse": None}


def _age_band(a: int | None) -> str | None:
    if a is None:
        return None
    return "0-11" if a < 12 else "12-17" if a < 18 else "18-39" if a < 40 else "40-59" if a < 60 else "60+"


def _line(key: str, lang: str, **kw) -> tuple[str, str]:
    e = LINES[key]
    text = e.get(lang) or e["en"]
    roman = e.get(f"{lang}_roman") or e["en"]
    for k, v in kw.items():
        text, roman = text.replace("{" + k + "}", v), roman.replace("{" + k + "}", v)
    return text, roman


# ---------------------------------------------------------------- LLM understanding
_SIGNS = sorted(rules.LEX)
_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "speaker_role": {"type": "STRING", "enum": ["self", "caregiver", "health_worker", "unknown"]},
        "speaker_relation": {"type": "STRING", "nullable": True,
                             "description": "speaker's relation to the patient, ONLY if explicit (e.g. 'child' when "
                                            "they say 'my mother'); never guess son/daughter"},
        "patient_age_years": {"type": "INTEGER", "nullable": True},
        "patient_sex": {"type": "STRING", "enum": ["female", "male", "other", "unknown"]},
        "chief_complaint_en": {"type": "STRING", "nullable": True,
                               "description": "main problem as a short neutral English symptom phrase, no diagnosis "
                                              "(e.g. 'chest discomfort', not 'acidity')"},
        "chief_complaint_said": {"type": "STRING", "nullable": True, "description": "patient's own words"},
        "symptoms": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "name": {"type": "STRING"}, "said": {"type": "STRING"},
            "onset": {"type": "STRING", "nullable": True}, "duration": {"type": "STRING", "nullable": True,
                                                                         "description": "e.g. '2 days', '1 week'"},
            "severity": {"type": "STRING", "nullable": True}, "location": {"type": "STRING", "nullable": True},
            "character": {"type": "STRING", "nullable": True},
            "associated": {"type": "ARRAY", "items": {"type": "STRING"}}},
            "required": ["name", "said"]}},
        "conditions": {"type": "ARRAY", "items": {"type": "STRING"}},
        "medicines_taken": {"type": "ARRAY", "items": {"type": "STRING"}},
        "allergies": {"type": "ARRAY", "items": {"type": "STRING"}},
        "pregnant": {"type": "BOOLEAN", "nullable": True},
        "signs_present": {"type": "ARRAY", "items": {"type": "STRING", "enum": _SIGNS}},
        "confirmation": {"type": "STRING", "enum": ["yes", "no", "correction", "none"]},
        "out_of_scope_question": {"type": "BOOLEAN",
                                  "description": "user asked for a diagnosis, medicine or treatment advice"},
        "summary_patient": {"type": "STRING",
                            "description": "1-2 short sentences in the patient's language and native script "
                                           "restating ONLY what was reported (symptom, since when, key details), "
                                           "respectful register, no diagnosis, no advice, no medicine suggestions. "
                                           "Hindi in Devanagari, Bengali in Bengali script"},
        "summary_patient_roman": {"type": "STRING", "description": "the same summary, romanised"},
        "danger": {"type": "STRING", "enum": ["none", "urgent", "emergency"],
                   "description": "your clinical-safety judgement of the whole conversation: emergency = needs help "
                                  "now, urgent = should see a doctor today"},
        "danger_reason": {"type": "STRING", "nullable": True, "description": "short English reason, if not none"},
    },
    "required": ["speaker_role", "patient_sex", "symptoms", "conditions", "medicines_taken", "allergies",
                 "signs_present", "confirmation", "out_of_scope_question", "summary_patient", "danger"],
}
_SYSTEM = (
    "You are the understanding step of a voice symptom-intake assistant in India. Patients speak Hindi, Bengali, "
    "English or a mix, often romanised, sometimes through a family member. You never diagnose or advise. "
    "Update the intake from the new utterance, keeping earlier information unless the user corrects it (a correction "
    "replaces the old value). Record only what was said; leave unknowns null or empty. Everyday phrases like 'gas', "
    "'chakkar', 'ghabrahat', 'kamzori', 'BP low' are recorded as said, with a neutral English symptom name. "
    "signs_present: every sign from the allowed list that the user affirms in the WHOLE conversation so far "
    "(not ones they deny). 'confirmation' is only about the read-back question, if one was just asked."
)


def _llm_understand(state: dict, utterance: str, last_q: str | None) -> tuple[dict | None, dict]:
    if not llm.available():
        return None, {"fallback": True, "reason": "no llm"}
    compact = {k: state[k] for k in ("speaker", "patient", "chief_complaint", "symptoms", "history")}
    hist = [f"{t['who']}: {t['text']}" for t in state["transcript_log"][-8:]]
    prompt = (f"Patient language: {state['lang']['reply']}\nLast question the assistant asked (English): "
              f"{last_q or '-'}\nIntake so far: {json.dumps(compact, ensure_ascii=False)}\n"
              f"Conversation so far:\n" + "\n".join(hist) + f"\nNew user utterance: {utterance}\n")
    try:
        out, meta = llm.generate_json(prompt, system=_SYSTEM, schema=_SCHEMA, timeout=LLM_TIMEOUT,
                                      retries=LLM_RETRIES)
        return out, {"fallback": False, **meta}
    except llm.LLMError as e:
        return None, {"fallback": True, "reason": str(e), "wait_ms": getattr(e, "wait_ms", 0)}


def _merge_llm(state: dict, u: dict) -> None:
    sp = state["speaker"]
    if u.get("speaker_role") in ("self", "caregiver", "health_worker"):
        sp["role"] = u["speaker_role"]
    if u.get("speaker_relation") and not re.search(r"\b(son|daughter)\b", str(u["speaker_relation"]).lower()):
        sp["relation"] = u["speaker_relation"]
    p = state["patient"]
    if isinstance(u.get("patient_age_years"), int) and 0 <= u["patient_age_years"] < 120:
        p["age_years"] = u["patient_age_years"]
    if u.get("patient_sex") in ("female", "male", "other"):
        p["sex"] = u["patient_sex"]
    cc = state["chief_complaint"]
    if u.get("chief_complaint_en"):
        if cc["value"] and cc["value"] != u["chief_complaint_en"] and cc["status"] == "confirmed":
            cc["status"] = "corrected"
        cc["value"] = u["chief_complaint_en"]
        cc["said"] = u.get("chief_complaint_said") or cc["said"]
        cc["status"] = cc["status"] if cc["status"] in ("confirmed", "corrected") else "heard"
    if u.get("symptoms"):
        old = {s["name"]: s for s in state["symptoms"]}
        new = []
        for s in u["symptoms"]:
            prev = old.get(s.get("name"), {})
            st = "corrected" if prev and prev.get("duration") and s.get("duration") and \
                prev.get("duration") != s.get("duration") else prev.get("status", "heard")
            new.append({"name": s.get("name"), "said": s.get("said"), "onset": s.get("onset"),
                        "duration": s.get("duration"), "severity": s.get("severity"), "location": s.get("location"),
                        "character": s.get("character"), "pattern": None, "associated": s.get("associated") or [],
                        "status": st})
        state["symptoms"] = new
    h = state["history"]
    for k_src, k_dst in (("conditions", "conditions"), ("medicines_taken", "medicines_taken"),
                         ("allergies", "allergies")):
        if u.get(k_src):
            h[k_dst]["value"] = list(dict.fromkeys(h[k_dst]["value"] + u[k_src]))
            h[k_dst]["status"] = "heard" if h[k_dst]["status"] != "confirmed" else "confirmed"
    if u.get("pregnant") is not None:
        h["pregnant"] = {"value": u["pregnant"], "status": "heard"}
    st = state["_internal"]
    st["signs"] = sorted(set(st["signs"]) | {s for s in u.get("signs_present", []) if s in rules.LEX})


# ---------------------------------------------------------------- rule layer
_CC_FALLBACK = [("chest", "chest discomfort"), ("breathless", "breathlessness"), ("fever", "fever"),
                ("belly_pain", "abdominal pain"), ("headache", "headache"), ("weakness", "weakness"),
                ("cough", "cough"), ("vomiting", "vomiting"), ("diarrhoea", "loose motions"),
                ("bleeding", "bleeding"), ("numb", "numbness"), ("rash", "rash"),
                ("self_harm", "thoughts of self-harm"), ("seizure", "fits"), ("unconscious", "unresponsive"),
                ("poison", "possible poisoning"), ("snakebite", "snakebite"), ("head_injury", "head injury"),
                ("vomit_blood", "vomiting blood"), ("no_sleep", "not sleeping"), ("fall", "fall")]
# when only an everyday phrase was heard, name the complaint after it (K's finding: 'matha ghorachhe' left it empty)
_CC_IDIOM = {"I_chakkar": "dizziness", "I_gas": "gas", "I_ghabrahat": "uneasiness (ghabrahat)",
             "I_kamzori": "weakness", "I_sunn": "numbness", "I_bp": "blood pressure concern",
             "I_sugar": "sugar (diabetes) concern", "I_saans_phoolna": "breathlessness", "I_jalan": "burning",
             "I_garmi_thand": "fever or cold", "I_tension": "stress"}


def _apply_rules(state: dict, text: str) -> None:
    st = state["_internal"]
    present, _neg = rules.signs(text)
    st["signs"] = sorted(set(st["signs"]) | present)
    st["idioms_seen"] = list(dict.fromkeys(st["idioms_seen"] + sorted(rules.idioms(text))))
    a = rules.age(text)
    if a is not None:
        state["patient"]["age_years"] = a
    d = rules.latest_duration(text)
    if d:
        st["duration_days"] = d[0]
        if state["symptoms"] and not state["symptoms"][0].get("duration"):
            state["symptoms"][0]["duration"] = rules._fmt_days(d[0])
    t = rules.temperature_f(text)
    if t:
        st["temp_f"] = t
    spk = rules.speaker(text)
    if spk and state["speaker"]["role"] == "unknown":
        state["speaker"]["role"], state["speaker"]["relation"] = spk
    sex = rules.patient_sex(text)
    if sex and state["patient"]["sex"] == "unknown":
        state["patient"]["sex"] = sex
    if "diabetic" in present and "diabetes" not in state["history"]["conditions"]["value"]:
        state["history"]["conditions"]["value"].append("diabetes")
        state["history"]["conditions"]["status"] = "heard"
    if d:
        st["duration_said"] = d[1]
    if not state["chief_complaint"]["value"]:
        idiom_now = [i for i in IDIOM_ORDER if i in rules.idioms(text)]
        cands = [(s, lbl) for s, lbl in _CC_FALLBACK if s in present]
        if not cands and idiom_now:
            cands = [("idiom", _CC_IDIOM[idiom_now[0]])]
        if cands:
            label = cands[0][1]
            state["chief_complaint"].update(value=label, said=text, status="heard")
            state["symptoms"] = state["symptoms"] or [
                {"name": label, "said": text, "onset": None,
                 "duration": rules._fmt_days(d[0]) if d else None, "severity": None, "location": None,
                 "character": None, "pattern": None, "associated": [], "status": "heard"}]


def _ctx(state: dict) -> rules.Ctx:
    st, conds = state["_internal"], [c.lower() for c in state["history"]["conditions"]["value"]]
    return rules.Ctx(signs=set(st["signs"]), age=state["patient"]["age_years"],
                     diabetic=any("diab" in c or "sugar" in c for c in conds),
                     hypertensive=any("pressure" in c or "hypert" in c or c == "bp" for c in conds),
                     duration_days=st["duration_days"], temp_f=st["temp_f"])


# ---------------------------------------------------------------- summaries
def _clinician_summary(state: dict, flags: list[dict]) -> str | None:
    if not state["chief_complaint"]["value"] and not flags:
        return None
    sp, p = state["speaker"], state["patient"]
    who = "Patient" if sp["role"] in ("self", "unknown") else \
        f"{sp['role'].replace('_', ' ').capitalize()}" + (f" (patient's {sp['relation']})" if sp["relation"] else "")
    pt = ", ".join(x for x in (f"{p['age_years']} y" if p["age_years"] is not None else None,
                               p["sex"] if p["sex"] != "unknown" else None) if x)
    parts = []
    emerg = [f for f in flags if f["level"] == "emergency"]
    if flags:
        parts.append(("EMERGENCY" if emerg else "URGENT") + ": " + ", ".join(f["id"] for f in flags) + ".")
    parts.append(f"{who} reporting" + (f" for {pt}" if pt and sp["role"] == "caregiver" else
                                       f", {pt}" if pt else "") + ".")
    cc = state["chief_complaint"]
    if cc["value"]:
        parts.append(f"Chief complaint: {cc['value']}" + (f' (said: "{cc["said"]}")' if cc["said"] else "") + ".")
    for s in state["symptoms"][:4]:
        bits = [x for x in (s.get("duration") and f"for {s['duration']}", s.get("location"), s.get("severity"),
                            s.get("character"), s.get("associated") and "with " + ", ".join(s["associated"])) if x]
        if bits:
            parts.append(f"{s['name']}: " + "; ".join(bits) + ".")
    h = state["history"]
    for k, label in (("conditions", "Known conditions"), ("medicines_taken", "Medicines taken"),
                     ("allergies", "Allergies")):
        if h[k]["value"]:
            parts.append(f"{label}: {', '.join(h[k]['value'])}.")
    st = state["_internal"]
    yn_signs = set(st.get("yn_signs") or [])
    signs = [x for x in st["signs"] if x not in ("severe", "leg", "older", "child") and x not in yn_signs]
    if signs:
        parts.append("Signs mentioned: " + ", ".join(signs) + ".")
    if st.get("yn"):
        parts.append("Yes/no answers (speech was hard to understand): " + "; ".join(
            f"{LINES[k]['en'].replace(' Please say yes or no.', '')} {v}" for k, v in st["yn"].items()) + ".")
    if st.get("unclear"):
        parts.append("Not understood after one re-ask: " + "; ".join(
            f"{'age' if k == 'age' else 'since when'} (heard: \"{v}\")" for k, v in st["unclear"].items()) + ".")
    return " ".join(parts)


_AGE_WORD = {"hi": "{n} saal", "bn": "{n} bochhor", "en": "{n} years old"}


def _fallback_readback(state: dict, lang: str) -> tuple[str, str]:
    """Rules-only read-back built from the patient's own words (no English normalisation mixed in), plus the
    fixed fragments for yes/no answers. Returns (native, romanised)."""
    st = state["_internal"]
    bits: list[tuple[str, str]] = []
    cc = state["chief_complaint"]
    said = cc["said"] or ""
    if said:
        bits.append((said, said))
    else:
        yn_cc = [_line(k, lang) for q, k in (("yn_chest", "rb_chest"), ("yn_breath", "rb_breath"))
                 if st.get("yn", {}).get(q) == "yes"]
        bits += yn_cc or ([(cc["value"], cc["value"])] if cc["value"] else [])
    dur = st.get("duration_said")
    if dur and dur not in light(said):
        bits.append((dur, dur))
    elif not dur and st.get("duration_coarse"):
        bits.append(_line(f"rb_{st['duration_coarse']}", lang))
    if state["patient"]["age_years"] is not None:
        a = _AGE_WORD[lang].format(n=state["patient"]["age_years"])
        bits.append((a, a))
    elif st.get("age_coarse"):
        bits.append(_line(f"rb_{st['age_coarse']}", lang))
    if not bits:
        return "-", "-"
    return ", ".join(b[0] for b in bits), ", ".join(b[1] for b in bits)


def _safe_summary(summary: str | None, state: dict) -> str | None:
    if not summary:
        return None
    said = light(" ".join(t["text"] for t in state["transcript_log"] if t["who"] == "user"))
    for m in _BANNED.finditer(light(translit(summary))):
        if m.group(0) not in said:
            return None
    return summary


def _spell_numbers(s: str) -> str:
    return re.sub(r"\b(112|108|14416)\b", lambda m: " ".join(m.group(1)), s)


# words the user is likely to say next, per question (C1 1.1 expect.stt_hints); romanised, the engine may also get
# the native-script idiom phrases from K's vocabulary
_HINTS = {
    "q_duration": {"hi": ["din", "hafte", "mahine", "saal", "kal se", "aaj subah", "ek", "do", "teen", "chaar",
                          "paanch"],
                   "bn": ["din", "mash", "bochhor", "kal theke", "aaj sokal", "ek", "dui", "tin", "char", "panch"],
                   "en": ["days", "weeks", "months", "since yesterday", "this morning", "two", "three", "four"]},
    "q_age": {"hi": ["saal", "umar", "chaalis", "pachaas", "saath", "sattar", "assi"],
              "bn": ["boyosh", "bochhor", "chollish", "ponchash", "shat", "sottor", "ashi"],
              "en": ["years old", "forty", "fifty", "sixty", "seventy", "eighty"]},
    "q_conditions": {"hi": ["sugar", "BP", "dil ki bimari", "dama", "thyroid", "koi nahi"],
                     "bn": ["sugar", "pressure", "hriday", "hapani", "thyroid", "kichhu nei"],
                     "en": ["diabetes", "blood pressure", "heart disease", "asthma", "thyroid", "none"]},
    "q_medicines": {"hi": ["dawai", "goli", "metformin", "insulin", "amlodipine", "koi nahi"],
                    "bn": ["oshudh", "metformin", "insulin", "amlodipine", "kichhu na"],
                    "en": ["tablets", "metformin", "insulin", "amlodipine", "none"]},
    "readback": {"hi": ["haan", "sahi hai", "nahi", "galat"], "bn": ["hya", "thik", "na", "bhul"],
                 "en": ["yes", "that's right", "no", "wrong"]},
}
_IDIOM_HINTS = {"d_I_gas": ["pet", "seena", "chhati", "buk", "pasina", "ghaam", "saans", "shash", "haath", "jabda"],
                "d_I_ghabrahat": ["dar", "chinta", "dhadkan", "dhorphor", "ulti", "seene mein dabav"],
                "d_I_chakkar": ["kamra ghoomta", "gir jayenge", "achanak", "hothat", "seedha chal"],
                "d_I_kamzori": ["poore sharir", "ek taraf", "ek haath", "ek pair", "achanak", "hothat"],
                "d_I_sunn": ["ek taraf", "achanak", "chehra", "muh tedha", "bolne mein"],
                "d_I_bp": ["naapa", "kitna", "chakkar", "sir dard"], "d_I_sugar": ["sugar", "pasina", "kaanp"],
                "d_I_saans_phoolna": ["baithe baithe", "poora vaakya", "nayi"],
                "d_I_jalan": ["peshab", "pet", "seena", "twacha"], "d_I_garmi_thand": ["bukhar", "jor", "naapa"],
                "d_I_tension": ["neend", "khana", "khayal"]}


def _stt_hints(key: str | None, lang: str) -> list[str]:
    k = "q_age" if key and key.startswith("q_age") else "q_duration" if key == "q_duration_retry" else \
        "readback" if key and key.startswith("yn_") else key
    if k in _HINTS:
        return _HINTS[k][lang][:30]
    return _IDIOM_HINTS.get(k or "", [])[:30]


# ---------------------------------------------------------------- policy
def _has(state: dict, field: str) -> bool:
    st = state["_internal"]
    if field == "duration":
        return st["duration_days"] is not None or any(s.get("duration") for s in state["symptoms"]) or \
            bool(st.get("duration_coarse"))
    return state["patient"]["age_years"] is not None or bool(st.get("age_coarse"))


# yes/no form of each question, used after two misheard turns in a row (prompt spec: "switch to yes/no questions")
_YN_OF = {"q_duration": "yn_duration", "q_duration_retry": "yn_duration", "q_age": "yn_age", "q_age_retry": "yn_age",
          "q_other": "yn_other", "q_conditions": "yn_conditions", "q_medicines": "yn_medicines",
          "d_I_gas": "yn_I_gas", "d_I_kamzori": "yn_I_one_side", "d_I_sunn": "yn_I_one_side",
          "d_I_chakkar": "yn_I_sudden"}
# a "yes" adds these signs, so the red-flag rules judge a yes/no answer exactly like the spoken words
_YN_SIGN = {"yn_chest": "chest", "yn_breath": "breathless", "yn_bleeding": "bleeding", "yn_unconscious": "unconscious",
            "yn_I_gas": "sweating", "yn_I_one_side": "one_side", "yn_I_sudden": "sudden"}
_RF_ASK = [("chest", "yn_chest"), ("breathless", "yn_breath"), ("unconscious", "yn_unconscious"),
           ("bleeding", "yn_bleeding")]
_FIELD_OF = {"q_duration": "duration", "q_duration_retry": "duration", "q_age_self": "age", "q_age_other": "age",
             "q_age_retry": "age"}


def _base(key: str | None) -> str | None:
    if key in ("q_age_self", "q_age_other"):
        return "q_age"
    if key in ("greet", "greet_phone", "greet_phone_named"):
        return "q_open"
    return key


def _next_question(state: dict) -> tuple[str | None, list[str]]:
    """(next question key, keys to mark as asked). In yes/no mode each question is swapped for its yes/no form;
    questions without one are skipped."""
    st = state["_internal"]
    asked = set(st["asked"])
    yn = st.get("yn_mode")

    def candidates():
        for i in IDIOM_ORDER:
            if i in st["idioms_seen"] and f"d_{i}" not in asked:
                yield f"d_{i}"
        for q in st.get("queue", []):
            if q not in asked and not (q in _FIELD_OF and _has(state, _FIELD_OF[q])):
                yield q
        if not state["chief_complaint"]["value"]:
            if yn:
                yield from (q for q in ("yn_chest", "yn_breath") if q not in asked)
            elif "q_open" not in asked:
                yield "q_open"
        if not _has(state, "duration") and "q_duration" not in asked:
            yield "q_duration"
        if not _has(state, "age") and "q_age" not in asked:
            yield "q_age"
        for q in ("q_other", "q_conditions", "q_medicines"):
            if q not in asked:
                yield q

    skipped: list[str] = []
    for q in candidates():
        if not yn or q.startswith("yn_"):
            return q, skipped + [q]
        y = _YN_OF.get(q)
        if y is None or y in asked:
            skipped.append(q)
            continue
        return y, skipped + [q, y]
    return None, skipped


def _apply_yn(state: dict, key: str, ans: str | None) -> None:
    """Record a yes/no answer and turn it into intake facts (conservative: a 'yes' to a two-part question counts as
    the more serious part, so red-flag rules never miss it)."""
    st = state["_internal"]
    st["yn"][key] = ans or "unclear"
    if ans is None:
        return
    if ans == "yes" and key in _YN_SIGN:
        sg = _YN_SIGN[key]
        if sg not in st["signs"]:
            st["signs"] = sorted(set(st["signs"]) | {sg})
            st["yn_signs"] = sorted(set(st["yn_signs"]) | {sg})
        cc = state["chief_complaint"]
        label = {"yn_chest": "chest pain", "yn_breath": "breathlessness"}.get(key)
        if label and not cc["value"]:
            cc.update(value=label, said=None, status="heard")
            state["symptoms"] = state["symptoms"] or [
                {"name": label, "said": None, "onset": None, "duration": None, "severity": None, "location": None,
                 "character": None, "pattern": None, "associated": [], "status": "heard"}]
    if ans == "yes" and (key == "yn_chest" or (key == "yn_other" and "chest" in st["signs"])):
        st["queue"].append("yn_breath")
    h = state["history"]
    if key == "yn_duration":
        st["duration_coarse"] = "over3" if ans == "yes" else "upto3"
        if ans == "yes" and st["duration_days"] is None:
            st["duration_days"] = 4  # "more than three days": enough for the fever-over-three-days rule (U1)
    elif key == "yn_age":
        st["age_coarse"] = "over60" if ans == "yes" else "under60"
        if ans == "yes":
            st["signs"] = sorted(set(st["signs"]) | {"older"})
    elif key == "yn_conditions":
        if ans == "yes":
            h["conditions"]["value"].append("sugar or BP (yes/no answer, which one not known)")
        h["conditions"]["status"] = "heard"
    elif key == "yn_medicines":
        if ans == "yes":
            h["medicines_taken"]["value"].append("yes, names not known (yes/no answer)")
        h["medicines_taken"]["status"] = "heard"


def _misheard(state: dict) -> tuple[str, str]:
    """(action, key) after a turn that was empty or not understood. Two in a row switch to yes/no questions; five
    in a row end the call politely, keeping what was collected (like three silences)."""
    st = state["_internal"]
    st["stt_fail"] += 1
    if st["stt_fail"] >= 5:
        state["phase"] = "done"
        return "done", "bye_silence"
    if st["stt_fail"] < 2:
        return "repeat", "q_repeat"
    st["yn_mode"] = True
    last = st.get("last_q")
    if last in ("readback", "q_fix"):
        return "confirm", "readback"
    if last and last.startswith("yn_"):
        return "ask", last
    y = "yn_chest" if _base(last) == "q_open" and not state["chief_complaint"]["value"] else _YN_OF.get(_base(last))
    if y and y not in st["asked"]:
        st["asked"].append(y)
        if y == "yn_chest":
            st["queue"].append("yn_breath")
        return "ask", y
    q, marks = _next_question(state)
    st["asked"] += marks
    if q is None:
        state["phase"] = "confirming"
        return "confirm", "readback"
    return "ask", q


_EXPECT = {"q_duration": "duration", "q_duration_retry": "duration", "q_age": "number", "q_age_retry": "number",
           "readback": "yes_no"}


def _validate(req: dict) -> None:
    if not isinstance(req, dict):
        raise ValueError("request must be an object")
    if str(req.get("contract", "")).split(".")[0] != CONTRACT.split(".")[0]:
        raise ValueError("contract: unsupported major version")
    for f in ("session_id", "turn", "event"):
        if f not in req:
            raise ValueError(f"{f}: required")
    if req["event"] not in EVENTS:
        raise ValueError("event: unknown")
    if req["event"] == "utterance" and not (req.get("transcript") or {}).get("text", "").strip():
        if not isinstance(req.get("transcript"), dict):
            raise ValueError("transcript: required for utterance")


def turn(req: dict) -> dict:
    t0 = time.perf_counter()
    _validate(req)
    ev = req["event"]
    hint = req.get("ui_lang_hint") if req.get("ui_lang_hint") in LANGS else None
    state = copy.deepcopy(req.get("state")) if req.get("state") else _new_state(hint or "hi")
    st = state["_internal"]
    for k, v in _r4_defaults().items():
        st.setdefault(k, v)
    lang = state["lang"]["reply"]
    debug: dict = {"fallback": False}
    action, key, kw, prefix = "ask", None, {}, None
    kw_roman = None
    new_flags: list[dict] = []
    escalation = None

    channel = req.get("channel") if req.get("channel") in CHANNELS else st.get("channel", "web")
    st["channel"] = channel
    phone = channel.startswith("phone")
    if ev == "start":
        ctx = req.get("context") if isinstance(req.get("context"), dict) else None
        st["context"] = ctx
        name = (ctx or {}).get("patient_first_name")
        if channel == "phone_out" and name:
            key, kw = "greet_phone_named", {"name": str(name)[:40]}
            kw_roman = None
        else:
            key = "greet_phone" if phone else "greet"
        st["asked"].append("q_open")
    elif ev == "no_speech":
        state["no_speech_count"] += 1
        if state["no_speech_count"] >= 3:
            action, key = "done", "bye_silence"
            state["phase"] = "done"
        else:
            key = "q_no_speech"
    elif ev == "end":
        action, key = "done", "done"
        state["phase"] = "done"
    else:  # utterance
        tr = req.get("transcript") or {}
        text = (tr.get("text") or "").strip()
        state["no_speech_count"] = 0
        tl = tr.get("language")
        if tl in LANGS and (tr.get("language_confidence") is None or tr["language_confidence"] >= 0.6) and text:
            # prompt spec: reply in the main language, switch only after two turns in a row in another one. The
            # first utterance sets the main language (the greeting's language was only a guess or a UI hint).
            first = not any(t["who"] == "user" for t in state["transcript_log"])
            if tl == lang:
                st["lang_cand"] = None
            else:
                cand = st.get("lang_cand")
                n = cand[1] + 1 if cand and cand[0] == tl else 1
                if first or n >= 2:
                    lang, st["lang_cand"] = tl, None
                    state["lang"].update(reply=lang, script=SCRIPT[lang])
                else:
                    st["lang_cand"] = [tl, n]
        audio = req.get("audio") or {}
        if (audio.get("speech_rate_wpm") or 999) < 110:
            st["slow"] = True
        prev = st.get("pending")
        field = _FIELD_OF.get(prev)
        pre_age, pre_dur = state["patient"]["age_years"], st["duration_days"]
        misheard = not text
        if not text:
            action, key = _misheard(state)
        else:
            state["transcript_log"].append({"turn": req["turn"], "who": "user", "text": text, "language": tl})
            sig_before = set(st["signs"])
            _apply_rules(state, text)
            # a lone number answers a question that asked for one ("chaalis" to "how old?")
            n = rules.bare_number(text)
            if n is not None and state["patient"]["age_years"] is None and (
                    field == "age" or ("age" in st["unclear"] and state["phase"] == "confirming")):
                state["patient"]["age_years"] = n
            elif n is not None and prev == "q_duration_retry" and st["duration_days"] is None:
                st["duration_days"], st["duration_said"] = float(n), text
                if state["symptoms"] and not state["symptoms"][0].get("duration"):
                    state["symptoms"][0]["duration"] = rules._fmt_days(n)
            yn_ans = rules.yes_no(text)
            if prev in LINES and prev.startswith("yn_"):
                _apply_yn(state, prev, yn_ans)
            last_q = LINES[st["pending"]]["en"] if st.get("pending") in LINES else None
            u, meta = _llm_understand(state, text, last_q)
            debug.update(meta)
            if u:
                _merge_llm(state, u)
                if u.get("summary_patient"):
                    safe = _safe_summary(u["summary_patient"], state)
                    st["summary_patient"] = safe.rstrip(" .।") if safe else None
                    st["summary_patient_roman"] = (u.get("summary_patient_roman") or "").rstrip(" .") or None
            else:
                st["llm_fail"] += 1
            # red flags (rules over rule+LLM signs)
            raised = {f["id"]: f for f in st["raised"]}
            if "chest" in st["signs"] and st.get("chest_turn") is None:
                st["chest_turn"] = req["turn"]
            for rid, level in rules.evaluate(_ctx(state)):
                # U3 = "chest emergency not ruled out after asking": give the follow-up question one turn first
                if rid == "U3_chest_unresolved" and st.get("chest_turn") == req["turn"]:
                    continue
                if rid not in raised:
                    f = {"id": rid, "level": level, "evidence": text, "turn": req["turn"]}
                    st["raised"].append(f)
                    new_flags.append(f)
            # LLM safety net (SAFETY.md U9): only when no rule has fired in this session, and only ever urgent
            # only the model's "emergency" judgement counts: its "urgent" fired on harmless cases in eval
            if u and u.get("danger") == "emergency" and not st["raised"]:
                f = {"id": "U9_llm_concern", "level": "urgent", "turn": req["turn"],
                     "evidence": f"{text} [model: {u.get('danger')}; {u.get('danger_reason') or '-'}]"}
                st["raised"].append(f)
                new_flags.append(f)
            new_e = [f for f in new_flags if f["level"] == "emergency"]
            new_u = [f for f in new_flags if f["level"] == "urgent"]
            had_e = any(f["level"] == "emergency" for f in raised.values())
            if new_e or (new_u and not had_e):
                action = "escalate"
                state["phase"] = "escalated"
                self_harm = any(f["id"] == "E9_self_harm" for f in new_e)
                key = "esc_self_harm" if self_harm else "esc_emergency" if new_e else "esc_urgent"
                if phone and new_e:  # the call is being bridged (transfer: true): don't tell them to dial now
                    key += "_transfer"
                level = "emergency" if new_e else "urgent"
                call = {"number": "14416", "label": "Tele-MANAS"} if self_harm else \
                    {"number": "112", "label": "Emergency"} if new_e else None
                escalation = {"level": level, "message": None, "call": call,
                              "reason_clinician": "; ".join(f["id"] for f in (new_e or new_u))}
            # prompt spec: a red-flag word that may have been misheard is asked about directly, never ignored
            maybe = [] if new_flags else [c for c, _ in _RF_ASK if c in rules.maybe_flags(
                text, tr.get("alternatives")) and c not in st["signs"] and c not in st["rf_asked"]]
            understood = bool(set(st["signs"]) - sig_before or rules.idioms(text) or yn_ans or
                              state["patient"]["age_years"] != pre_age or st["duration_days"] != pre_dur or
                              (u and (u.get("symptoms") or u.get("chief_complaint_en"))))
            low_conf = isinstance(tr.get("stt_confidence"), (int, float)) and tr["stt_confidence"] < 0.35
            if action == "escalate":
                pass
            elif maybe:
                st["rf_asked"].append(maybe[0])
                key = dict(_RF_ASK)[maybe[0]]
                st["asked"].append(key)
                if state["phase"] == "confirming":
                    state["phase"] = "collecting"
            elif (low_conf or (st["yn_mode"] and prev and prev.startswith("yn_"))) and not understood:
                misheard = True
                action, key = _misheard(state)  # garbled: same path as an empty transcript
            elif state["phase"] == "confirming":
                conf = (u or {}).get("confirmation", "none")
                yes = conf == "yes" or (not u and yn_ans == "yes")
                changed = state["patient"]["age_years"] != pre_age or st["duration_days"] != pre_dur
                if changed and not u:  # rules-only correction ("na, tin din", or the age they were asked for)
                    if st["duration_days"] != pre_dur and state["symptoms"]:
                        state["symptoms"][0]["duration"] = rules._fmt_days(st["duration_days"])
                        state["symptoms"][0]["status"] = "corrected"
                    action, key = "confirm", "readback"
                elif yes:
                    action, key = "done", "done"
                    state["phase"] = "done"
                    for f in ("chief_complaint",):
                        if state[f]["status"] == "heard":
                            state[f]["status"] = "confirmed"
                    for s in state["symptoms"]:
                        if s["status"] == "heard":
                            s["status"] = "confirmed"
                elif conf == "correction":
                    action, key = "confirm", "readback"
                else:
                    key = "q_fix"
            elif (u or {}).get("out_of_scope_question"):
                prefix = _line("out_of_scope", lang)
            if action == "ask" and key is None:
                # an answer to "since when?" / "how old?" that did not parse: re-ask once in a simpler form with
                # examples; if that fails too, mark it unclear and move on (the read-back names it). Never on a
                # red-flag turn: escalation comes first.
                if field and not _has(state, field) and not new_flags:
                    if prev.endswith("_retry") or field in st["reasked"]:
                        st["unclear"][field] = text
                    else:
                        st["reasked"].append(field)
                        st["queue"].append(f"q_{field}_retry")
                q, marks = _next_question(state)
                st["asked"] += marks
                if q is None:
                    action, key = "confirm", "readback"
                    state["phase"] = "confirming"
                else:
                    key = q
                    if q == "q_age":
                        key = "q_age_other" if state["speaker"]["role"] == "caregiver" else "q_age_self"
        if not misheard:
            st["stt_fail"] = 0
    for f in [f for f in st["unclear"] if _has(state, f)]:
        del st["unclear"][f]
    st["queue"] = [q for q in st["queue"] if q not in st["asked"]]
    if action == "confirm":
        if st.get("summary_patient"):
            kw, kw_roman = {"s": st["summary_patient"]}, st.get("summary_patient_roman")
        else:
            s_nat, s_rom = _fallback_readback(state, lang)
            kw, kw_roman = {"s": s_nat}, s_rom

    if state["phase"] == "escalated" and action == "ask" and not new_flags:
        state["phase"] = "collecting"
    text_out, roman_out = _line(key, lang, **kw)
    if "s" in kw:
        roman_out = _line(key, lang, s=kw_roman or "")[1]
    elif "name" in kw:
        roman_out = _line(key, lang, name=kw["name"])[1]
    if prefix:
        text_out, roman_out = prefix[0] + " " + text_out, prefix[1] + " " + roman_out
    if action == "confirm" and st["unclear"]:  # name what we could not understand, so they can say it now
        u_key = "unclear_both" if len(st["unclear"]) > 1 else f"unclear_{next(iter(st['unclear']))}"
        ut, ur = _line(u_key, lang)
        text_out, roman_out = text_out + " " + ut, roman_out + " " + ur
    if escalation:
        escalation["message"] = text_out
        # an urgent (not emergency) escalation must not swallow a pending idiom question (e.g. the self-harm check
        # inside the ghabrahat/tension question): ask it in the same turn
        if escalation["level"] == "urgent":
            q, _ = _next_question(state)
            if q and q.startswith("d_"):
                qt, qr = _line(q, lang)
                text_out, roman_out = text_out + " " + qt, roman_out + " " + qr
                st["asked"].append(q)
                key = q
    if phone:  # listening only: say emergency numbers digit by digit ("1 1 2")
        text_out, roman_out = _spell_numbers(text_out), _spell_numbers(roman_out)
        if escalation:
            escalation["message"] = _spell_numbers(escalation["message"])
    if escalation:
        escalation["transfer"] = bool(phone and escalation["level"] == "emergency")
        escalation["calls"] = [{"number": "112", "label": "Emergency"}] if (escalation.get("call") or {}).get(
            "number") == "14416" else []
    st["pending"] = key if key in LINES else None
    if key and (key.startswith(("q_", "d_", "yn_", "greet")) or key == "readback") and \
            key not in ("q_repeat", "q_no_speech"):
        st["last_q"] = key
    state["transcript_log"].append({"turn": req["turn"], "who": "agent", "text": roman_out, "language": lang})
    if len(state["transcript_log"]) > 40:
        state["transcript_log"] = state["transcript_log"][-40:]

    # bookkeeping fields from the contract
    p = state["patient"]
    p["age_band"] = _age_band(p["age_years"])
    miss = []
    if not state["chief_complaint"]["value"]:
        miss.append("chief_complaint")
    if state["symptoms"] and not state["symptoms"][0].get("duration") and st["duration_days"] is None:
        miss.append("symptoms[0].duration")
    if p["age_years"] is None:
        miss.append("patient.age_years")
    for k in ("conditions", "medicines_taken", "allergies"):
        if state["history"][k]["status"] == "missing":
            miss.append(f"history.{k}")
    state["missing"] = miss

    older = (p["age_years"] or 0) >= 60 or "older" in st["signs"]
    flags = st["raised"]
    exp_kind = "none" if action == "done" else _EXPECT.get(key, "free")
    if key and key.startswith("q_age"):
        exp_kind = "number"
    if key and key.startswith("yn_"):
        exp_kind = "yes_no"
    # agent's own time; pacing/rate-limit waits (batch runs only) are reported separately
    debug["latency_ms"] = round((time.perf_counter() - t0) * 1000) - int(debug.get("wait_ms") or 0)
    debug["rules_signs"] = st["signs"]
    return {
        "contract": "1.1" if str(req.get("contract")).startswith("1.1") else "1.0",
        "session_id": req["session_id"], "turn": req["turn"], "action": action,
        "say": {"text": text_out, "language": lang, "script": SCRIPT[lang], "text_roman": roman_out,
                "register": "respectful", "pace": "slow" if (action == "escalate" or older or st["slow"]) else
                "normal", "interruptible": action != "escalate"},
        "expect": {"kind": exp_kind, "choices": [], "patience": "long" if (older or st["slow"] or
                                                                          exp_kind == "free") else "normal",
                   "stt_hints": [] if action == "done" else _stt_hints(key, lang),
                   "fillers": [] if action in ("done", "escalate") else
                   [dict(zip(("text", "text_roman"), _line(f"filler_{i}", lang))) for i in (1, 2, 3)]},
        "state": state,
        "red_flags": flags,
        "escalation": escalation,
        "display": {"caption": text_out,
                    "summary_patient": kw.get("s") if action == "confirm" else None,
                    "summary_clinician": _clinician_summary(state, flags)},
        "debug": debug,
    }

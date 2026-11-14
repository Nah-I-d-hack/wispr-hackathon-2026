"""[K] Test double for R's intake agent, speaking contract C1 v1.0 (contracts/INTAKE.md).

This exists only so the app can run end to end before R3 lands. It is NOT the agent: a few canned questions, a
keyword red-flag check and a read-back. Point the server at the real agent with AGENT_URL and this is never used.
"""
from __future__ import annotations

import copy

CONTRACT = "1.0"

LINES = {
    "hi": {
        "greet": "नमस्ते। आपको क्या तकलीफ है?",
        "since": "यह कब से है?",
        "history": "क्या आपको कोई पुरानी बीमारी है, जैसे शुगर या बीपी?",
        "confirm": "मैंने समझा: {s}। क्या यह सही है?",
        "fix": "ठीक है, क्या बदलना है?",
        "done": "धन्यवाद। आपकी जानकारी डॉक्टर को भेज दी गई है।",
        "repeat": "माफ़ कीजिए, क्या आप फिर से बोल सकते हैं?",
        "escalate": "यह जरूरी है। अभी 112 पर फोन करें या सबसे पास के अस्पताल जाएं।",
        "bye": "कोई बात नहीं। जब चाहें फिर से बात करें।",
    },
    "bn": {
        "greet": "নমস্কার। আপনার কী সমস্যা হচ্ছে?",
        "since": "এটা কবে থেকে হচ্ছে?",
        "history": "আপনার কি কোনো পুরনো অসুখ আছে, যেমন সুগার বা প্রেশার?",
        "confirm": "আমি বুঝেছি: {s}। এটা কি ঠিক?",
        "fix": "ঠিক আছে, কী বদলাতে হবে?",
        "done": "ধন্যবাদ। আপনার তথ্য ডাক্তারের কাছে পাঠানো হয়েছে।",
        "repeat": "মাফ করবেন, আরেকবার বলবেন?",
        "escalate": "এটা জরুরি। এখনই 112-এ ফোন করুন বা কাছের হাসপাতালে যান।",
        "bye": "ঠিক আছে। যখন খুশি আবার কথা বলবেন।",
    },
    "en": {
        "greet": "Hello. What is troubling you?",
        "since": "Since when has this been happening?",
        "history": "Do you have any long-term illness, like diabetes or blood pressure?",
        "confirm": "I understood: {s}. Is that right?",
        "fix": "All right, what should I change?",
        "done": "Thank you. Your details have been sent to the doctor.",
        "repeat": "Sorry, could you say that again?",
        "escalate": "This is urgent. Call 112 now or go to the nearest hospital.",
        "bye": "No problem. Talk to me again whenever you like.",
    },
}
SCRIPT = {"hi": "Deva", "bn": "Beng", "en": "Latn"}
YES = ("haan", "han", "ha ", "yes", "theek", "thik", "sahi", "हाँ", "हां", "हा", "सही", "ठीक", "হ্যাঁ", "হ্যা", "ঠিক", "correct")
# keyword -> (red flag id, evidence label). Deliberately crude: R2/R3 own the real rules.
RED_FLAGS = [
    (("chest pain", "seene", "sine me", "chhati", "सीने", "छाती", "বুকে", "buke byatha"), "chest_pain"),
    (("saans nahi", "saans lene", "breath", "सांस", "साँस", "শ্বাস", "nishash"), "breathing_difficulty"),
    (("behosh", "unconscious", "बेहोश", "অজ্ঞান", "ojnan"), "unconscious"),
    (("samajh nahi aa raha", "confus", "gardan akad", "stiff neck"), "fever_stiff_neck_confusion"),
    (("marna chahta", "marna chahti", "suicide", "kill myself", "मरना चाहता", "मरना चाहती", "মরে যেতে"), "suicidal_thoughts"),
]


def _empty_state(lang: str) -> dict:
    missing = {"value": [], "status": "missing"}
    return {
        "speaker": {"role": "unknown", "relation": None},
        "patient": {"age_years": None, "age_band": None, "sex": "unknown"},
        "chief_complaint": {"value": None, "said": None, "status": "missing"},
        "symptoms": [],
        "history": {"conditions": dict(missing), "medicines_taken": dict(missing), "allergies": dict(missing),
                    "pregnant": {"value": None, "status": "missing"}},
        "missing": ["chief_complaint"],
        "phase": "collecting",
        "lang": {"reply": lang, "script": SCRIPT[lang], "register": "respectful"},
        "no_speech_count": 0,
        "transcript_log": [],
        "_internal": {"mock": True, "step": "complaint"},
    }


def _readback(st: dict) -> str:
    parts = [st["chief_complaint"]["said"]]
    if st["symptoms"] and st["symptoms"][0].get("duration"):
        parts.append(st["symptoms"][0]["duration"])
    cond = st["history"]["conditions"]["value"]
    if cond:
        parts.append(", ".join(cond))
    return "; ".join(p for p in parts if p)


def _clinician(st: dict, flags: list[dict]) -> str | None:
    cc = st["chief_complaint"]["said"]
    if not cc:
        return None
    s = f"Chief complaint (patient's words): \"{cc}\"."
    if st["symptoms"] and st["symptoms"][0].get("duration"):
        s += f" Since: \"{st['symptoms'][0]['duration']}\"."
    if st["history"]["conditions"]["value"]:
        s += f" History: \"{'; '.join(st['history']['conditions']['value'])}\"."
    if flags:
        s = "EMERGENCY: " + ", ".join(f["id"] for f in flags) + ". " + s
    return s + " [mock agent: words are not normalised]"


def turn(req: dict) -> dict:
    if req.get("contract", "").split(".")[0] != CONTRACT.split(".")[0]:
        raise ValueError("unsupported contract version")
    ev = req["event"]
    st = copy.deepcopy(req.get("state")) or _empty_state(req.get("ui_lang_hint") or "hi")
    lang = st["lang"]["reply"] if st["lang"]["reply"] in LINES else "hi"
    L = LINES[lang]
    flags = list(st["_internal"].get("red_flags", []))
    action, key, expect, escalation, fmt = "ask", "greet", "free", None, {}
    text = ((req.get("transcript") or {}).get("text") or "").strip()

    if ev == "start":
        pass
    elif ev == "end":
        action, key, expect = "done", "bye", "none"
    elif ev == "no_speech" or (ev == "utterance" and not text):
        st["no_speech_count"] += 1
        action, key = ("done", "bye") if st["no_speech_count"] >= 3 else ("repeat", "repeat")
        expect = "none" if action == "done" else "free"
    else:
        st["no_speech_count"] = 0
        st["transcript_log"].append({"turn": req["turn"], "who": "user", "text": text,
                                     "language": req["transcript"].get("language", "und")})
        low = text.lower()
        new = [{"id": fid, "level": "emergency", "evidence": text, "turn": req["turn"]}
               for kws, fid in RED_FLAGS if any(k in low for k in kws) and fid not in {f["id"] for f in flags}]
        step = st["_internal"]["step"]
        if step == "complaint":
            st["chief_complaint"] = {"value": None, "said": text, "status": "heard"}
            st["symptoms"] = [{"name": None, "said": text, "onset": None, "duration": None, "severity": None,
                               "location": None, "character": None, "pattern": None, "associated": [],
                               "status": "heard"}]
            st["missing"] = ["symptom.duration", "history.conditions"]
            step, key, expect = "since", "since", "duration"
        elif step == "since":
            st["symptoms"][0]["duration"] = text
            st["missing"] = ["history.conditions"]
            step, key, expect = "history", "history", "free"
        elif step == "history":
            st["history"]["conditions"] = {"value": [text], "status": "heard"}
            st["missing"] = []
            step, action, key, expect = "confirm", "confirm", "confirm", "yes_no"
        elif step == "confirm":
            if any(y in f" {low} " for y in YES):
                for f in (st["chief_complaint"], st["symptoms"][0], st["history"]["conditions"]):
                    f["status"] = "confirmed"
                step, action, key, expect = "done", "done", "done", "none"
                st["phase"] = "done"
            else:
                step, key, expect = "fix", "fix", "free"
        elif step == "fix":
            st["chief_complaint"].update(said=text, status="corrected")
            st["symptoms"][0].update(said=text, status="corrected")
            step, action, key, expect = "confirm", "confirm", "confirm", "yes_no"
        else:
            action, key, expect = "done", "done", "none"
        st["_internal"]["step"] = step
        if new:
            flags += new
            st["phase"] = "escalated"
            action, key = "escalate", "escalate"
        if action == "confirm":
            fmt = {"s": _readback(st)}
            st["phase"] = "confirming"

    st["_internal"]["red_flags"] = flags
    say_text = L[key].format(**fmt) if fmt else L[key]
    if action == "escalate":
        escalation = {"level": "emergency", "message": say_text, "call": {"number": "112", "label": "Emergency"},
                      "reason_clinician": "Mock keyword match: " + ", ".join(f["id"] for f in flags)}
    return {
        "contract": CONTRACT, "session_id": req["session_id"], "turn": req["turn"], "action": action,
        "say": {"text": say_text, "language": lang, "script": SCRIPT[lang], "text_roman": "",
                "register": "respectful", "pace": "slow" if action == "escalate" else "normal",
                "interruptible": action != "escalate"},
        "expect": {"kind": expect, "choices": [], "patience": "long"},
        "state": st, "red_flags": flags, "escalation": escalation,
        "display": {"caption": say_text, "summary_patient": fmt.get("s") if action == "confirm" else None,
                    "summary_clinician": _clinician(st, flags)},
        "debug": {"model": "k3-mock-agent", "fallback": False},
    }

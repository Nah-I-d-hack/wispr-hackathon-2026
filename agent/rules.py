"""[R] Deterministic layer of the intake agent: signs, negation, age/duration, red flags (docs/SAFETY.md s3) and
idioms (s4). Runs on every utterance with no LLM, so an API failure can never drop an emergency.

Lexicon phrases are romanised; matching is on fuzzy skeletons (agent/text.py), so native script, spelling variants
and Bengali/Hindi inherent vowels all land on the same tokens. '*' in a phrase = a gap of up to 3 words.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .text import clauses, light, skeleton_tokens, skeleton_word

# ---------------------------------------------------------------- sign lexicon (concept -> phrases)
LEX: dict[str, list[str]] = {
    "chest": ["seena", "seene", "sine", "sina", "chhati", "chhaati", "chest", "buk", "buke", "buker", "dil baith",
              "heart"],
    "heavy": ["bhaari", "bhari", "dabav", "dabaav", "pressure", "crushing", "heavy", "chepe", "chap", "weight",
              "jakad"],
    "sweating": ["pasina", "paseena", "pasine", "ghaam", "gham", "ghamchhe", "ghamche", "ghame", "ghamte", "sweat",
                 "sweating", "sweaty"],
    "breathless": ["saans phool", "saans phul", "saans lene", "saans ki takleef", "saans nahi", "shash", "shwas",
                   "swas", "hapani", "haanf", "breathless", "short of breath", "breathing", "breathe", "dum ghut",
                   "hanpan"],
    "breath_severe": ["saans nahi aa", "saans nahi le", "can't breathe", "cannot breathe", "dum ghut",
                      "baithe baithe", "even sitting", "at rest", "poora vaakya nahi", "full sentence",
                      "finish a sentence", "neel", "blue", "shash nite parchhe na", "shash nite * koshto",
                      "bose thakleo", "baat nahi kar pa", "baat bhi nahi kar pa", "bol bhi nahi pa",
                      "can't talk", "cannot talk", "kotha bolte parchhi na"],
    "radiation": ["haath mein dard ja", "haath tak", "baayen haath", "bayen haath", "left arm", "jaw", "jabda",
                  "jabde", "chhoriye", "chhoriye jachhe", "spreading", "choyal", "going to my arm"],
    "fainting": ["behosh", "hosh nahi", "ogyan", "ojnan", "agyan", "faint", "fainted", "fainting", "passed out",
                 "pore gechhilam", "matha ghure pore"],
    "vomiting": ["ulti", "vomit", "vomiting", "bomi", "ji machal"],
    "one_side": ["ek taraf", "ek side", "ek dik", "ekdik", "daayan", "dayan", "daayen", "baayan", "bayan", "baayen",
                 "right arm", "left arm", "right side", "left side", "right leg", "left leg", "ek haath", "ek pair",
                 "baa haat", "dan haat", "bam haat", "daan haat", "one side", "one arm", "one leg"],
    "weakness": ["kamzori", "kamjori", "weak", "weakness", "jaan nahi", "durbol", "taqat nahi", "takat nahi"],
    "numb": ["sunn", "jhunjhuni", "jhin jhin", "jhinjhin", "obosh", "numb", "numbness", "tingling"],
    "face_droop": ["muh * tedha", "munh * tedha", "chehra * tedha", "mukh benke", "mukh beke", "mukh ta * benke",
                   "face droop", "face is drooping", "muh latak", "drooping"],
    "speech_slurred": ["bol nahi pa", "jaban ladkha", "zubaan ladkha", "kotha jodiye", "slurred", "speak properly",
                       "can't speak", "cannot speak", "bolne mein dikkat", "kotha bolte parchhe na"],
    "vision": ["dikh nahi", "dikhna band", "dhundhla", "andhera", "chokhe dekhte", "can't see", "cannot see",
               "vision", "blurred", "blurry", "aankh se dikh"],
    "imbalance": ["seedha chal nahi", "sidha chal nahi", "chal nahi pa", "balance", "ladkhada", "can't walk straight",
                  "sojha hatte", "tal samlate"],
    "sudden": ["achanak", "ekdum", "hothat", "hathat", "sudden", "suddenly", "in a second", "abhi abhi"],
    "unconscious": ["behosh", "hosh nahi", "hosh mein nahi", "ogyan", "ojnan", "agyan", "unconscious",
                    "not responding", "jaag nahi", "sara dichhe na", "sara dey na", "unresponsive"],
    "seizure": ["jhatke", "jhatka", "dant lag", "mirgi", "khichuni", "fit", "fits", "seizure", "convulsion",
                "ainthan"],
    "fever": ["bukhar", "bukhaar", "jor", "jwar", "fever", "temperature", "taap", "tap"],
    "stiff_neck": ["gardan akad", "gardan jakad", "gardan akadi", "ghaar shokto", "ghar shokto", "stiff neck",
                   "neck is stiff", "neck stiff"],
    "confusion": ["samajh nahi aa", "kuch samajh nahi", "confus", "confused", "confusion", "behki", "ulta seedha bol",
                  "bujhte parchhe na", "chinte parchhe na", "pehchaan nahi", "disoriented"],
    "drowsy": ["neend aa rahi", "sust", "susti", "drowsy", "sleepy", "ghumiye porchhe", "ghumiye pore",
               "jaag nahi", "hard to wake", "uth nahi"],
    "rash": ["daane", "rash", "chakte", "fuskuri", "laal daag"],
    "infant": ["mahine ka", "mahine ki", "month old", "months old", "mash er", "newborn", "naya bachcha",
               "nobojatok"],
    "vomit_blood": ["khoon ki ulti", "khoon ulti", "rokto bomi", "vomiting blood", "blood vomit", "rakt ki ulti"],
    "black_stool": ["kaala paakhaana", "kala pakhana", "kaali tatti", "kalo paikhana", "black stool", "black poop",
                    "tarry"],
    "heavy_bleeding": ["khoon band nahi", "bahut khoon", "rokto bondho hochhe na", "bleeding won't stop",
                       "heavy bleeding", "lots of blood"],
    "bleeding": ["khoon", "rokto", "rakt", "blood", "bleeding", "bleed"],
    "pregnant": ["pet se", "pregnant", "garbh", "garbhvati", "pregnancy", "antahsatva", "pregnent"],
    "baby_not_moving": ["bachcha hil nahi", "hil nahi raha", "hilna band", "hasn't moved", "not moving",
                        "moved much", "nodche na", "norachora"],
    "water_broke": ["pani gir", "paani gir", "water broke", "jol bhenge"],
    "child": ["bachcha", "bachche", "bachchi", "baccha", "baby", "infant", "toddler", "child", "kid", "shishu",
              "chhota beta", "chhoti beti"],
    "not_feeding": ["doodh nahi pee", "dudh khachhe na", "dudh khacche na", "not feeding", "won't drink",
                    "can't drink", "pee nahi raha"],
    "vomits_everything": ["sab ulti", "sab kuch ulti", "sob kichhu bomi", "vomits everything",
                          "kichhu pete thakchhe na", "kuch nahi tik", "keeps vomiting everything"],
    "lethargic": ["sust", "susti", "uth nahi raha", "lethargic", "very sleepy", "nishteja", "nisteja", "jhimiye"],
    "self_harm": ["marna chahta", "marna chahti", "mar jaun", "mar jau", "mar jaana", "jeene ka mann nahi",
                  "jine ka man nahi", "jeena nahi chahta", "khud ko khatam", "khudkushi", "aatmahatya", "atmohotya",
                  "morte ichhe", "more jete ichhe", "bachte ichhe kore na", "nijeke shesh", "suicide", "kill myself",
                  "end my life", "don't want to live", "hurt myself", "khud ko nuksaan", "nijeke khoti",
                  "nijeke kono khoti"],
    "poison": ["keede maarne ki dawa", "keetnashak", "zeher", "jahar", "poison", "pesticide", "bish", "phenyl",
               "bahut goliyan", "goliyan kha li", "overdose", "too many tablets", "too many pills"],
    "snakebite": ["saanp ne kaata", "saap ne kaata", "saanp kaat", "shaap kamreche", "shaap kamrechhe", "snake bit",
                  "snakebite", "snake bite"],
    "head_injury": ["sir pe chot", "sir mein chot", "sar pe chot", "sir par chot", "mathay chot", "mathay lege",
                    "head injury", "hit his head", "hit her head", "hit my head", "hit the head", "head hit"],
    "burn_major": ["bahut jal", "khub pure", "badly burn", "severe burn", "jal gaya bahut"],
    "worst_headache": ["aisa dard kabhi nahi", "kabhi nahi hua", "worst headache", "worst pain", "sir phat",
                       "matha phete", "emon byatha kokhono"],
    "headache": ["sir dard", "sar dard", "sir mein * dard", "matha byatha", "headache", "sir phat"],
    "diabetic": ["sugar hai", "sugar ke", "sugar wale", "sugar ki bimari", "sugar achhe", "diabetes", "diabetic",
                 "madhumeh", "sugar er rog", "sugar ki dawa", "unko sugar", "mujhe sugar"],
    "shaking": ["kaanp", "kanp", "kapkapi", "kanpchhe", "shaking", "trembling", "thar thar"],
    "unresponsive_speech": ["kuch bol nahi rahe", "bol nahi rahe", "sara dichhe na", "sara dey na",
                            "not responding", "no response", "jawab nahi"],
    "fall": ["gir gaye", "gir gayi", "gir gaya", "gir pade", "pore gechhe", "pore gelo", "fell", "fall", "fallen",
             "gir ke", "gira"],
    "cant_bear_weight": ["khade nahi ho", "khada nahi ho", "can't stand", "cannot stand", "darate parchhe na",
                         "can't put weight"],
    "older": ["dadi", "dada", "dadaji", "daadi", "nani", "nana", "nanaji", "budhe", "buzurg", "thakuma",
              "thakurda", "dida", "dadu", "grandmother", "grandfather", "grandma", "grandpa", "elderly"],
    "leg": ["pair", "pairon", "paon", "paa", "leg", "paye", "pao"],
    "swelling": ["sujan", "sooj", "swollen", "swelling", "phula", "phool", "phule", "fula", "phool gaya"],
    "blood_urine": ["peshab mein khoon", "pishab mein khoon", "prosrabe rokto", "prosraber sathe rokto",
                    "blood in urine", "blood in my urine", "urine mein khoon"],
    "blood_stool": ["potty mein khoon", "latrine mein khoon", "paikhanay rokto", "blood in stool", "mal mein khoon"],
    "belly_pain": ["pet * dard", "pete * byatha", "pet * byatha", "stomach pain", "belly pain",
                   "abdominal pain", "pet me dard", "pet mein * dard"],
    "severe": ["bahut", "tez", "khub", "severe", "bere jachhe", "badh raha", "barchhe", "increasing", "worse",
               "unbearable", "zyada"],
    "diarrhoea": ["dast", "loose motion", "patla paikhana", "pet kharap", "diarrhoea", "diarrhea", "patli tatti"],
    "low_urine": ["peshab kam", "peshab bahut kam", "peshab nahi", "prosrab kom", "prosrab hochhe na",
                  "not peeing", "no urine", "little urine"],
    "cant_keep_fluids": ["paani bhi ulti", "pani bhi ulti", "kuch nahi tik", "jol o bomi", "can't keep",
                         "cannot keep"],
    "no_sleep": ["neend nahi", "ghum nei", "ghum hochhe na", "can't sleep", "not sleeping", "no sleep"],
    "eating_poor": ["khana nahi", "kha nahi pa", "khete parchhi na", "khete parchhe na", "not eating", "can't eat",
                    "bhookh nahi", "khide nei"],
    "fear": ["bhoy", "bhay", "dar lag", "darr", "panic", "scared", "afraid"],
    "cough": ["khaansi", "khansi", "kashi", "cough"],
}

IDIOMS: dict[str, list[str]] = {
    "I_gas": ["gas"],
    "I_ghabrahat": ["ghabrahat", "ghabra", "jee ghabra", "dil ghabra", "buk dhorphor", "dhorphor", "ghabrano"],
    "I_chakkar": ["chakkar", "sir ghoom", "sar ghoom", "matha ghor", "matha ghur", "matha ghurchhe", "ghurchhe",
                  "dizzy", "dizziness", "giddy"],
    "I_kamzori": ["kamzori", "kamjori", "thakaan", "durbol", "jaan nahi"],
    "I_sunn": ["sunn", "jhunjhuni", "jhin jhin", "jhinjhin", "obosh"],
    "I_bp": ["bp", "blood pressure", "pressure er", "pressure ki", "pressure low", "pressure high"],
    "I_sugar": ["sugar", "madhumeh"],
    "I_saans_phoolna": ["saans phool", "saans phul", "haanf", "hapani"],
    "I_jalan": ["jalan", "jwala", "jala", "jalchhe", "jala kore", "burning"],
    "I_garmi_thand": ["garmi chadh", "garmi lag", "thanda lag", "thanda lege", "thanda laga", "sardi"],
    "I_tension": ["tension", "dimaag kharab", "mann nahi lagta", "man nahi lagta", "mon kharap", "chinta", "stress"],
}

_NON_NEGATABLE = {"child", "infant", "older", "leg", "pregnant", "diabetic", "severe", "sudden"}
_NEG = {"nahi", "nahin", "nai", "na", "nei", "nay", "no", "not", "never", "nope", "mat", "bhabini", "korini",
        "hoyni", "theek", "thik", "fine", "normal", "okay", "ok", "nothing", "none", "without"}


# words matched as prefixes (sweat -> sweating, sweaty); everything else must match a whole word
_PREFIX = {"sweat", "confus", "vomit", "faint", "numb", "tingl", "bleed", "swell", "weak", "breath", "ghabra",
           "jhunjhun", "drows", "ghamch"}


def _compile(phrase: str) -> list[str]:
    """'*' = gap of up to 3 words; words in _PREFIX match as prefixes."""
    return [("*" if w == "*" else skeleton_word(w) + ("~" if w in _PREFIX else "")) for w in light(phrase).split()]


_LEX_C = {k: [_compile(p) for p in v] for k, v in LEX.items()}
_IDIOM_C = {k: [_compile(p) for p in v] for k, v in IDIOMS.items()}


def _tok_eq(p: str, t: str) -> bool:
    if p.endswith("~"):
        return t.startswith(p[:-1])
    return t == p


def _find(pattern: list[str], toks: list[str]) -> tuple[int, int] | None:
    """Return (start, end) of the first match of pattern in toks; '*' matches 0..3 tokens."""
    def rec(pi: int, ti: int) -> int | None:
        if pi == len(pattern):
            return ti
        if pattern[pi] == "*":
            for g in range(0, 4):
                r = rec(pi + 1, ti + g) if ti + g <= len(toks) else None
                if r is not None:
                    return r
            return None
        if ti < len(toks) and _tok_eq(pattern[pi], toks[ti]):
            return rec(pi + 1, ti + 1)
        return None
    for s in range(len(toks)):
        e = rec(0, s)
        if e is not None:
            return s, e
    return None


def _neg_in(words: list[str]) -> bool:
    return any(w in _NEG or w.endswith("n't") for w in words)


def match_concepts(text: str, lex: dict[str, list[list[str]]]) -> tuple[set[str], set[str]]:
    """(present, negated) concepts. A match is negated if its clause holds a negation word outside the match."""
    present: set[str] = set()
    negated: set[str] = set()
    for cl in clauses(text):
        words = [w for w in re.split(r"[\s\-/]+", cl) if w]
        toks = [skeleton_word(w) for w in words]
        for concept, pats in lex.items():
            for p in pats:
                m = _find(p, toks)
                if m:
                    near = words[max(0, m[0] - 3): m[0]] + words[m[1]: m[1] + 3]
                    neg = concept not in _NON_NEGATABLE and _neg_in(near)
                    (negated if neg else present).add(concept)
                    break
    return present, negated - present


# ---------------------------------------------------------------- numbers, ages, durations
_NUM = {"ek": 1, "one": 1, "do": 2, "dui": 2, "two": 2, "teen": 3, "tin": 3, "three": 3, "char": 4, "chaar": 4,
        "four": 4, "paanch": 5, "panch": 5, "pach": 5, "five": 5, "chhe": 6, "chhah": 6, "chhoy": 6, "six": 6,
        "saat": 7, "sat": 7, "seven": 7, "aath": 8, "at": 8, "eight": 8, "nau": 9, "noy": 9, "nine": 9, "das": 10,
        "dosh": 10, "ten": 10, "pachchis": 25, "tees": 30, "tirish": 30, "chaalis": 40, "chollish": 40,
        "pachaas": 50, "ponchash": 50, "saath": 60, "shat": 60, "sattar": 70, "sottor": 70, "assi": 80, "ashi": 80,
        "atshotti": 68, "nabbe": 90, "nobboi": 90, "a": 1, "an": 1}
_UNIT_DAYS = {"din": 1, "dino": 1, "dinon": 1, "divas": 1, "day": 1, "days": 1, "hafte": 7, "hafta": 7,
              "hapta": 7, "week": 7, "weeks": 7, "saptah": 7, "mahine": 30, "mahina": 30, "month": 30,
              "months": 30, "mash": 30, "ghante": 1 / 24, "ghanta": 1 / 24, "hour": 1 / 24, "hours": 1 / 24,
              "ghonta": 1 / 24, "saal": 365, "sal": 365, "year": 365, "years": 365, "bochhor": 365}


def _num(w: str) -> float | None:
    if w.isdigit():
        return float(w)
    return _NUM.get(w)


def durations(text: str) -> list[tuple[float, str, bool]]:
    """All (days, phrase, negated) duration mentions, in order."""
    out = []
    for cl in clauses(text):
        words = re.findall(r"[a-z0-9']+", cl)
        neg = _neg_in(words)
        for i, w in enumerate(words[:-1]):
            n = _num(w)
            u = words[i + 1]
            if n is not None and u in _UNIT_DAYS and not (u in ("saal", "sal", "year", "years", "bochhor")
                                                          and n > 3):
                out.append((n * _UNIT_DAYS[u], f"{w} {u}", neg))
        if re.search(r"\b(kal se|kal theke|since yesterday|yesterday)\b", cl):
            out.append((1, "since yesterday", neg))
    return out


def latest_duration(text: str) -> tuple[float, str] | None:
    pos = [(d, p) for d, p, neg in durations(text) if not neg]
    return pos[-1] if pos else None


def _fmt_days(d: float) -> str:
    if d < 1:
        h = round(d * 24)
        return f"{h} hour" + ("s" if h != 1 else "")
    for unit, n in (("year", 365), ("month", 30), ("week", 7)):
        if d >= n and d % n == 0:
            k = int(d // n)
            return f"{k} {unit}" + ("s" if k != 1 else "")
    k = int(d)
    return f"{k} day" + ("s" if k != 1 else "")


def age(text: str) -> int | None:
    t = light(text)
    pats = [r"\b(\d{1,3})\s*(?:saal|sal|years?|yrs?|bochhor|boyosh|baras)\b",
            r"\b(?:umar|umr|age|boyosh|boyesh|aged)\s*(?:hai|is)?\s*(\d{1,3}|[a-z]+)\b",
            r"\b(?:she|he|i|they)\s*(?:is|am|are)\s*(\d{1,3})\b",
            r"\b([a-z]+)\s*(?:saal|sal|bochhor)\s*(?:ke|ki|ka|er)?\b"]
    for p in pats:
        for m in re.finditer(p, t):
            v = _num(m.group(1))
            if v is not None and 0 < v < 120 and not (v < 12 and re.search(r"saal se|years? ago", t)):
                return int(v)
    m = re.search(r"\b(\d{1,2}|[a-z]+)\s*(?:month|months|mahine|mash)\s*(?:old|ka|ki|er)\b", t)
    if m and _num(m.group(1)) is not None:
        return 0
    return None


def temperature_f(text: str) -> float | None:
    for m in re.finditer(r"\b(9[5-9]|10[0-7])(?:\.\d)?\b", light(text)):
        return float(m.group(1))
    return None


# ---------------------------------------------------------------- speaker / relation
_CAREGIVER = [(r"\b(meri|mere|amar|my)\s+(maa|mummy|mother|mom|ma)\b|\bmaa ko\b|\bmayer\b|\bmummy ko\b", "child"),
              (r"\b(mere|amar|my)\s+(papa|pita|baba|father|dad)\b|\bpapa ko\b|\bbabar\b|\bfather\b", "child"),
              (r"\b(dadi|dada|dadaji|daadi|nani|nana|thakuma|thakurda|dida|dadu|grandmother|grandfather|grandma|"
               r"grandpa)\b", "grandchild"),
              (r"\b(bachcha|bachche|bachchi|beta|beti|baby|my son|my daughter|chheler|meyer|chhele|meye)\b",
               "parent"),
              (r"\b(bhai|behen|bahan|brother|sister|dadar|didir)\b", "sibling"),
              (r"\b(pati|patni|husband|wife|swami|stri)\b", "spouse"),
              (r"\b(chacha|chachi|mama|mami|uncle|aunt|kaka|kaki)\b", "relative")]


def speaker(text: str) -> tuple[str, str | None] | None:
    t = light(text)
    for p, rel in _CAREGIVER:
        if re.search(p, t):
            return "caregiver", rel
    return None


def patient_sex(text: str) -> str | None:
    t = light(text)
    if re.search(r"\b(maa|mummy|mother|dadi|nani|beti|behen|patni|wife|she|her|mayer|meyer|thakuma|dida|"
                 r"grandmother|grandma|didi)\b", t):
        return "female"
    if re.search(r"\b(papa|father|dada|dadaji|nana|beta|bhai|pati|husband|he|his|babar|chheler|thakurda|dadu|"
                 r"grandfather|grandpa|chacha)\b", t):
        return "male"
    return None


# ---------------------------------------------------------------- red-flag rules (SAFETY.md s3)
@dataclass
class Ctx:
    signs: set[str] = field(default_factory=set)
    age: int | None = None
    diabetic: bool = False
    hypertensive: bool = False
    duration_days: float | None = None
    temp_f: float | None = None
    discriminators_unanswered: set[str] = field(default_factory=set)


def evaluate(c: Ctx) -> list[tuple[str, str]]:
    """Return [(rule_id, level)] that fire for this context, emergencies first."""
    s = c.signs
    has = lambda *xs: any(x in s for x in xs)  # noqa: E731
    child = "child" in s or "infant" in s or (c.age is not None and c.age < 12)
    older = "older" in s or (c.age is not None and c.age >= 65)
    risk = (c.age is not None and c.age >= 40) or c.diabetic or c.hypertensive or older
    out: list[tuple[str, str]] = []
    e = lambda rid: out.append((rid, "emergency"))  # noqa: E731
    u = lambda rid: out.append((rid, "urgent"))  # noqa: E731

    chest = "chest" in s
    if chest and (has("sweating", "breathless", "radiation", "fainting", "vomiting")
                  or (has("heavy", "sudden") and risk)):
        e("E1_chest_cardiac")
    if has("face_droop", "speech_slurred") or ("one_side" in s and has("weakness", "numb")) or \
            ("sudden" in s and has("vision", "imbalance")):
        e("E2_stroke")
    if "breath_severe" in s or ("breathless" in s and "severe" in s and "speech_slurred" in s):
        e("E3_breathing")
    # fainting alone is not E4 (SAFETY.md: "fainted and not fully back"); it feeds E1/E6/E11 instead
    if has("unconscious", "seizure"):
        e("E4_unconscious_seizure")
    if "fever" in s and (has("stiff_neck", "confusion", "rash") or ("drowsy" in s and older)
                         or "infant" in s or c.age == 0):
        e("E5_fever_neck_confusion")
    if has("vomit_blood", "heavy_bleeding") or ("black_stool" in s and has("fainting", "weakness")):
        e("E6_bleeding")
    if "pregnant" in s and (has("bleeding", "baby_not_moving", "water_broke", "worst_headache", "seizure")
                            or ("belly_pain" in s and "severe" in s) or ("headache" in s and "vision" in s)):
        e("E7_pregnancy")
    if child and (has("not_feeding", "vomits_everything", "lethargic", "seizure", "breath_severe")):
        e("E8_child_danger")
    if "self_harm" in s:
        e("E9_self_harm")
    if has("poison", "snakebite"):
        e("E10_poison_bite")
    if ("head_injury" in s and has("vomiting", "drowsy", "confusion", "unconscious", "fainting")) or \
            "burn_major" in s:
        e("E11_injury_head")
    if "worst_headache" in s or ("headache" in s and "sudden" in s and "severe" in s):
        e("E12_sudden_worst_headache")
    if c.diabetic and (has("confusion", "drowsy", "unconscious", "unresponsive_speech")
                       or ("shaking" in s and "sweating" in s)):
        e("E13_low_sugar")

    emergencies = {r for r, _ in out}
    if "fever" in s and ((c.duration_days or 0) > 3 or (c.temp_f or 0) >= 103 or (older and "weakness" in s)):
        u("U1_fever_long_or_high")
    if has("diarrhoea", "vomiting") and has("cant_keep_fluids", "low_urine"):
        u("U2_dehydration")
    if chest and "E1_chest_cardiac" not in emergencies and risk:
        u("U3_chest_unresolved")
    if "belly_pain" in s and (has("severe", "fever") or "vomits_everything" in s):
        u("U4_severe_belly_pain")
    if has("blood_urine", "blood_stool") and "E6_bleeding" not in emergencies:
        u("U5_blood")
    if "fall" in s and older and has("cant_bear_weight", "head_injury", "severe"):
        u("U6_fall_older")
    if "leg" in s and "swelling" in s and ("one_side" in s or "sudden" in s):
        u("U7_one_leg_swelling")
    if "self_harm" not in s and ("no_sleep" in s and "eating_poor" in s or ("fear" in s and "no_sleep" in s)):
        u("U8_mental_distress")
    # dedupe, keep order
    seen, res = set(), []
    for r in out:
        if r[0] not in seen:
            seen.add(r[0])
            res.append(r)
    return res


def idioms(text: str) -> set[str]:
    present, negated = match_concepts(text, _IDIOM_C)
    return present | negated  # an idiom mentioned even with a negation still needs its question


def signs(text: str) -> tuple[set[str], set[str]]:
    return match_concepts(text, _LEX_C)

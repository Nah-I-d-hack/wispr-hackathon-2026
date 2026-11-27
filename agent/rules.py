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
    "sweating": ["pasina", "paseena", "pasine", "ghaam", "gham", "ghamchhe", "ghamche", "ghame", "ghamte", "ghaamchhe",
                 "ghaamochhe", "ghaamte", "ghaamote", "gheme", "sweat", "sweating", "sweaty"],
    "breathless": ["saans phool", "saans phul", "saans * phool", "saans * phul", "saans lene", "saans ki takleef", "saans nahi", "shash", "shwas",
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
                   "face droop", "face is drooping", "muh latak", "drooping", "crooked", "lopsided",
                   "face * one side", "muh * ek taraf", "mukh * benke", "mukh * beke", "chehra * latak"],
    "arm_cant_lift": ["can't lift", "cannot lift", "can't raise", "haath utha nahi", "haath nahi utha",
                      "haat tulte parchhe na", "haat uthchhe na"],
    "speech_slurred": ["bol nahi pa", "jaban ladkha", "zubaan ladkha", "kotha jodiye", "slurred", "speak properly",
                       "can't speak", "cannot speak", "bolne mein dikkat", "kotha bolte parchhe na"],
    "vision": ["dikh nahi", "dikhna band", "dhundhla", "andhera", "chokhe dekhte", "can't see", "cannot see",
               "vision", "blurred", "blurry", "aankh se dikh", "jhapsa", "jhapsha", "jhaapsa",
               "dekhte parchhi na"],
    "imbalance": ["seedha chal nahi", "sidha chal nahi", "chal nahi pa", "balance", "ladkhada", "can't walk straight",
                  "sojha hatte", "tal samlate", "hata jachhe na", "hatte parchhi na", "can't walk properly"],
    "sudden": ["achanak", "ekdum", "hothat", "hathat", "sudden", "suddenly", "in a second", "abhi abhi"],
    "unconscious": ["behosh", "hosh nahi", "hosh mein nahi", "ogyan", "ojnan", "agyan", "unconscious",
                    "not responding", "jaag nahi", "sara dichhe na", "sara dey na", "unresponsive"],
    "seizure": ["jhatke", "jhatka", "dant lag", "mirgi", "khichuni", "fit", "fits", "seizure", "convulsion",
                "ainthan"],
    "fever": ["bukhar", "bukhaar", "bukar", "jor", "jwar", "jbor", "jbar", "fever", "temperature", "taap", "tap"],
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
    "swelling": ["sujan", "sooj", "swollen", "swelling", "phula", "phule", "fula", "phool gaya"],
    "blood_urine": ["peshab mein khoon", "pishab mein khoon", "prosrabe rokto", "prosraber sathe rokto",
                    "blood in urine", "blood in my urine", "urine mein khoon"],
    "blood_stool": ["potty mein khoon", "latrine mein khoon", "paikhanay rokto", "blood in stool", "mal mein khoon"],
    "belly_pain": ["pet * dard", "pete * byatha", "pet * byatha", "stomach pain", "belly pain",
                   "abdominal pain", "pet me dard", "pet mein * dard"],
    "severe": ["bahut", "tez", "khub", "severe", "bere jachhe", "badh raha", "barchhe", "increasing", "worse",
               "unbearable", "zyada"],
    "diarrhoea": ["dast", "loose motion", "patla paikhana", "pet kharap", "diarrh", "patli tatti"],
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
    "I_chakkar": ["chakkar", "sir ghoom", "sar ghoom", "matha ghora", "matha ghura", "matha ghurchhe", "ghurchhe",
                  "dizzy", "dizziness", "giddy"],
    "I_kamzori": ["kamzori", "kamjori", "thakaan", "durbol", "jaan nahi"],
    "I_sunn": ["sunn", "jhunjhuni", "jhin jhin", "jhinjhin", "obosh"],
    "I_bp": ["bp", "blood pressure", "pressure er", "pressure ki", "pressure low", "pressure high"],
    "I_sugar": ["sugar", "madhumeh"],
    "I_saans_phoolna": ["saans phool", "saans phul", "saans * phool", "saans * phul", "haanf", "hapani"],
    "I_jalan": ["jalan", "jwala", "jala", "jalchhe", "jala kore", "burning"],
    "I_garmi_thand": ["garmi chadh", "garmi lag", "thanda lag", "thanda lege", "thanda laga", "sardi"],
    "I_tension": ["tension", "dimaag kharab", "mann nahi lagta", "man nahi lagta", "mon kharap", "chinta", "stress"],
}

_NON_NEGATABLE = {"child", "infant", "older", "leg", "pregnant", "diabetic", "severe", "sudden"}
_NEG = {"nahi", "nahin", "nai", "na", "nei", "nay", "no", "not", "never", "nope", "mat", "bhabini", "korini",
        "hoyni", "theek", "thik", "fine", "normal", "okay", "ok", "nothing", "none", "without"}


# words matched as prefixes (sweat -> sweating, sweaty); everything else must match a whole word
_PREFIX = {"sweat", "confus", "vomit", "faint", "numb", "tingl", "bleed", "swell", "weak", "breath", "ghabra",
           "jhunjhun", "drows", "ghamch", "ghora", "ghura", "diarrh"}
# words whose fuzzy skeleton collides with a common word (buker = chest vs bukhar = fever): match the spelling exactly
_EXACT = {"buker", "bukhar", "bukhaar", "bukar", "bukhaara",
          # Bengali sweating words sit on the skeleton of 'ghum-' (sleep) and 'ghoom-' (spin): ghamte = ghumte = ghoomta
          "ghame", "ghamte", "ghaamte", "ghamche", "ghamchhe", "ghaamchhe", "ghaamochhe", "ghaamote", "gheme"}
# everyday words whose skeleton lands on a sign word: never a fuzzy match for a sign ('teen din dhore' = 'for three
# days', not diarrhoea; 'kamra ghoomta hai' = the room spins, not sweating; 'chinta' = worry, not chest). If a lexicon
# phrase uses one of these words itself, it matches that spelling exactly.
_NOT_FUZZY = {"dhore", "dhora", "dhorechhe", "dore", "dure", "dhire", "dheere", "dhaara", "dari", "dori", "daru",
              "ghoomta", "ghoomte", "ghoome", "ghume", "ghumte", "ghumta", "ghumchhe", "ghumiye", "ghumi", "gechhe",
              "gumti", "ghure", "ghora", "chinta", "chhota", "chhoti", "chhote", "kaisa", "kaise", "kaisi", "kisi", "kaunsi", "bare",
              "bere", "very", "worry", "have", "hobe", "could", "body", "sense", "dono", "dijiye", "taken", "thakun",
              "there", "tara", "troubling", "vaakya", "benke", "paren", "baba", "sushthe", "sustho", "sushtho"}


def _compile(phrase: str) -> list[str]:
    """'*' = gap of up to 3 words. Words in _PREFIX match as spelled prefixes ('~weak' matches 'weakness' but not
    'bukhar', whose skeleton happens to start like weak's); words in _EXACT and _NOT_FUZZY match their spelling; the
    rest match on fuzzy skeletons."""
    out = []
    for w in light(phrase).split():
        sk = skeleton_word(w)
        # short skeletons collide too easily (weak = buk, feel = fall): those words match their spelling only
        exact = w in _EXACT or w in _NOT_FUZZY or (len(sk) <= 3 and not sk.isdigit())
        out.append("*" if w == "*" else "~" + w if w in _PREFIX else "=" + w if exact else sk)
    return out


_LEX_C = {k: [_compile(p) for p in v] for k, v in LEX.items()}
_IDIOM_C = {k: [_compile(p) for p in v] for k, v in IDIOMS.items()}


def _tok_eq(p: str, t: tuple[str, str]) -> bool:
    skel, raw = t
    if p.startswith("~"):
        return raw.startswith(p[1:])
    if p.startswith("="):
        return raw == p[1:]
    return skel == p and raw not in _NOT_FUZZY


def _find(pattern: list[str], toks: list[tuple[str, str]]) -> tuple[int, int] | None:
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
        toks = [(skeleton_word(w), re.sub(r"[^a-z0-9']", "", w)) for w in words]
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
# Number words 1-100, Hindi and Bengali: common romanised spellings plus what agent/text.py makes of the native-script
# word (Hindi native 75 -> "pachahattar", Bengali native 75 -> "ponchaattor"). Lookup is exact first, then, for words
# of 5+ letters, on a loose key that ignores vowel length, doubled letters and ch/chh ("pachattar" = "pachhattar").
# Short words stay exact so "car", "no", "so" never become numbers.
_NUM_WORDS: dict[int, str] = {
    1: "ek one", 2: "do dui two", 3: "teen tin tiin three", 4: "char chaar four",
    5: "paanch panch pach paach five", 6: "chhe chhah chhay chhoy choy chhoj six", 7: "saat sat seven",
    8: "aath aat at eight", 9: "nau noy noj nine", 10: "das dus dosh ten",
    11: "gyaarah gyarah gyara egaro egharo egaaro eleven", 12: "baarah barah baaro baro twelve",
    13: "terah tero thirteen", 14: "chaudah chaudha choudah chodah choddo chouddo chodd fourteen",
    15: "pandrah pandra pondro ponero panero fifteen", 16: "solah sholo sixteen",
    17: "satrah satra sotero satero seventeen", 18: "athaarah athara atharah atharo aathaaro eighteen",
    19: "unnees unees unniis unish unis nineteen", 20: "bees biis bis kuri kudi twenty",
    21: "ikkees ikkis ekkis ikkiis ekush ekus", 22: "baaees baees bais baaiis baish",
    23: "teis teyis teees teiis teish", 24: "chaubees chaubis chobis chaubiis chobbish chobish",
    25: "pachchees pachchis pachees pachis pachchiis pochish ponchish panchish",
    26: "chhabbees chhabbis chabbis chhabbiis chhaabbish chhabbish",
    27: "sattaees sattais sattaaiis satash saataash sataish",
    28: "atthaees atthais athais atthaaiis athash aathaash athaish", 29: "untees untis unatiis unotrish untrish",
    30: "tees tis tiis tirish tiris", 31: "ikattees ikattis iktees iktis ikatiis ekotrish ektrish",
    32: "battees battis battiis botrish batrish", 33: "taintees taintis tentis taintiis tetrish",
    34: "chauntees chauntis chontis chauntiis choutrish chowtrish chautrish",
    35: "paintees paintis pentis paintiis poyotrish pointrish ponyotrish ponjotrish",
    36: "chhattees chhattis chattis chhattiis chhotrish chhatrish",
    37: "saintees saintis sentis saintiis saitrish saintrish saanitrish",
    38: "adtees adtis artis adatiis atotrish attrish aatotrish",
    39: "untaalees untalis unataaliis unochollish unchollish",
    40: "chaalees chaalis chalis chaaliis chollish challish cholish",
    41: "iktaalees iktalis ikataaliis ekchollish ekochollish",
    42: "bayaalees bayalis byalis bayaaliis beyallish biyallish bijaallish",
    43: "taintaalees taintalis tentalis taintaaliis tetallish tetaallish",
    44: "chavaalees chavalis chawalis chauvalis chavaaliis chuyallish chujaallish",
    45: "paintaalees paintalis pentalis paintaaliis poyotallish ponyotallish ponjotaallish",
    46: "chhiyaalees chhiyalis chiyalis chhiyaaliis chhechollish",
    47: "saintaalees saintalis sentalis saintaaliis satchollish saatochollish",
    48: "adtaalees adtalis artalis adataaliis atchollish aatochollish",
    49: "unchaas unchas unachaas unoponchash unponchash unoponchaash",
    50: "pachaas pachas ponchash panchash ponchas ponchaash", 51: "ikyaavan ikyavan ekyavan ekanno ekanna ekaann",
    52: "baavan bavan baawan bahanno bahanna baahaann", 53: "tirpan tirapan trepan tippanno teppanno tippaann",
    54: "chauvan chauwan chovan chuyanno chujaann", 55: "pachpan pachapan ponchanno pochpanno ponchaann",
    56: "chhappan chappan chhappanno chhaappaann", 57: "sattaavan sattavan satanno saataann",
    58: "atthaavan atthavan athavan atanno aataann", 59: "unsath unasath unoshat unshat unoshaat",
    60: "saath shat shaat sixty", 61: "iksath ikasath ekshotti ekoshotti ekshoti",
    62: "baasath basath bashotti baashotti", 63: "tirsath tirasath tresath teshotti",
    64: "chausath chaunsath chonsath chowshotti choushotti chaushotti",
    65: "painsath pensath poyshotti ponshotti ponjoshotti", 66: "chhiyaasath chhiyasath chiyasath chheshotti",
    67: "sadsath sarsath sadasath satshotti saatoshotti", 68: "adsath arsath adasath atshotti aatoshotti",
    69: "unhattar unahattar unosottor unsottor", 70: "sattar satar sottor sattor shottor seventy",
    71: "ikhattar ikahattar ikattar ekattor ekhattor ekaattor", 72: "bahattar bahatar bahattor baahaattor",
    73: "tihattar tihatar tiyattor tiattor tijaattor", 74: "chauhattar chohattar chuyattor chujaattor",
    75: "pachhattar pachattar pachahattar pochattor ponchattor panchattor ponchaattor",
    76: "chhihattar chihattar chhiyattar chhiyattor chhijaattor",
    77: "satattar sathattar satahattar satattor saataattor",
    78: "athattar athhattar athahattar athattor atattor aataattor",
    79: "unaasi unasi unyaasi unyaasii unyasi unoashi unashi unoaashi", 80: "assi asi assii ashi aashi eighty",
    81: "ikyaasi ikyasi ikyaasii ekashi ekaashi", 82: "bayaasi bayasi byasi bayaasii birashi biraashi",
    83: "tiraasi tirasi tiraasii tirashi tiraashi",
    84: "chauraasi chaurasi chorasi chauraasii churashi chourashi churaashi",
    85: "pachaasi pachasi pachaasii pochashi ponchashi ponchaashi",
    86: "chhiyaasi chhiyasi chhiyaasii chhiyashi chhijaashi", 87: "sattaasi sattasi sattaasii satashi saataashi",
    88: "atthaasi atthasi atthaasii atashi aataashi", 89: "navaasi navasi nawasi navaasii unonobboi unnobboi",
    90: "nabbe nabe nobboi nabbai ninety", 91: "ikyaanave ikyanave ikyanve ekanobboi ekaanobboi",
    92: "baanave banave baanve biranobboi biraanobboi", 93: "tiraanave tiranave tiranve tiranobboi tiraanobboi",
    94: "chauraanave chauranave chauranve churanobboi churaanobboi",
    95: "pachaanave panchaanave pachanave pachanve ponchanobboi pochanobboi ponchaanobboi",
    96: "chhiyaanave chhiyanave chhiyanve chhiyanobboi chhijaanobboi",
    97: "sattaanave sattanave sattanve satanobboi saataanobboi",
    98: "atthaanave atthanave atthanve atanobboi aataanobboi",
    99: "ninyaanave ninyanave ninyanve niranobboi niraanobboi", 100: "sau eksho ekosho hundred",
}
_EN_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
            "ninety": 90}
_EN_ONES = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9}
_NUM: dict[str, int] = {"a": 1, "an": 1, **_EN_TENS}
for _v, _ws in _NUM_WORDS.items():
    for _w in _ws.split():
        _NUM[_w] = _v


def _nkey(w: str) -> str:
    """Loose spelling key for number words: ignores vowel length, doubled letters, ch/chh, w/v and y/j."""
    w = w.replace("ee", "i").replace("oo", "u").replace("chh", "c").replace("ch", "c").replace("w", "v")
    w = re.sub(r"(.)\1+", r"\1", w.replace("y", "j"))
    return re.sub(r"(?<=[aeiou])h$", "", w)


_NUM_LOOSE: dict[str, int] = {}
for _w, _v in _NUM.items():
    if len(_w) >= 5:
        _NUM_LOOSE.setdefault(_nkey(_w), _v)
_UNIT_DAYS = {"din": 1, "dino": 1, "dinon": 1, "divas": 1, "day": 1, "days": 1, "hafte": 7, "hafta": 7,
              "hapta": 7, "week": 7, "weeks": 7, "saptah": 7, "soptaho": 7, "soptah": 7, "saptaho": 7, "mahine": 30,
              "mahina": 30, "month": 30, "months": 30, "mash": 30, "ghante": 1 / 24, "ghanta": 1 / 24,
              "hour": 1 / 24, "hours": 1 / 24, "ghonta": 1 / 24, "saal": 365, "sal": 365, "year": 365, "years": 365,
              "bochhor": 365, "bochor": 365}
_YEAR_UNITS = ("saal", "sal", "year", "years", "bochhor", "bochor")


def _num(w: str) -> float | None:
    if w.isdigit():
        return float(w)
    if w in _NUM:
        return _NUM[w]
    return _NUM_LOOSE.get(_nkey(w)) if len(w) >= 5 else None


def _numbers_joined(t: str) -> str:
    """'seventy five' / 'seventy-five' -> '75', so the age patterns see one number."""
    return re.sub(r"\b(" + "|".join(_EN_TENS) + r")[\s-]+(" + "|".join(_EN_ONES) + r")\b",
                  lambda m: str(_EN_TENS[m.group(1)] + _EN_ONES[m.group(2)]), t)


def durations(text: str) -> list[tuple[float, str, bool]]:
    """All (days, phrase, negated) duration mentions, in order."""
    out = []
    for cl in clauses(text):
        words = re.findall(r"[a-z0-9']+", cl)
        neg = _neg_in(words)
        for i, w in enumerate(words[:-1]):
            n = _num(w)
            u = words[i + 1]
            if n is not None and u in _UNIT_DAYS and not (u in _YEAR_UNITS and n > 3):
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


# a number + year unit followed by one of these is a duration ("teen saal se", "dui bochhor dhore"), not an age
_SINCE = re.compile(r"\s*(?:se|theke|dhore|ago|pehle|age|purana|purani|from|since)\b")
_AGE_UNIT = r"(?:saal|sal|years?|yrs?|bochhor|bochor|bachhar|baras|varsh|borosh)"
_AGE_WORD = r"(?:umar|umr|umra|age|boyos|boyosh|boyes|boyesh|bojos|bayas|aged)"


def age(text: str) -> int | None:
    """Patient age ('pachattar saal', 'boyos sottor', 'umar 62', 'seventy-five years old'); never a duration."""
    t = _numbers_joined(light(text))
    pats = [(r"\b(\d{1,3})\s*" + _AGE_UNIT + r"\b", True),
            (r"\b" + _AGE_WORD + r"\b\s*(?:(?:hai|is|holo|hobe)\b\s*)?(\d{1,3}|[a-z]+)\b", False),
            (r"\b(?:she|he|i|they)\s*(?:is|am|are)\s*(\d{1,3})\b", False),
            (r"\b([a-z]+)\s*(?:saal|sal|bochhor|bochor|baras)\s*(?:ke|ki|ka|er)?\b", True),
            (r"\b([a-z]+)\s*years?\s*old\b", False)]
    for p, unit in pats:
        for m in re.finditer(p, t):
            v = _num(m.group(1))
            if v is None or not 0 < v < 120:
                continue
            if unit and _SINCE.match(t, m.end()):
                continue
            if not (v < 12 and re.search(r"saal se|years? ago", t)):
                return int(v)
    m = re.search(r"\b(\d{1,2}|[a-z]+)\s*(?:month|months|mahine|mash)\s*(?:old|ka|ki|er)\b", t)
    if m and _num(m.group(1)) is not None:
        return 0
    return None


def bare_number(text: str) -> int | None:
    """A lone number answer ('chaalis', '62', 'two', 'pachattar') to a question that asked for one. None if absent,
    several, or part of a duration: 'teen din se' answers 'since when?', never 'how old?'."""
    words = re.findall(r"[a-z0-9]+", _numbers_joined(light(text)))
    if any(w in _UNIT_DAYS and w not in _YEAR_UNITS for w in words) or durations(text) or \
            re.search(r"\b(?:" + "|".join(_YEAR_UNITS) + r")\b" + _SINCE.pattern, " ".join(words)):
        return None
    nums = [n for w in words if w not in ("a", "an", "at") for n in [_num(w)] if n is not None]
    return int(nums[0]) if len(nums) == 1 and 0 < nums[0] < 120 else None


_YES = re.compile(r"\b(haan|haa|ha|han|haanji|ji haan|yes|yeah|yep|sahi|theek|thik|hyan|hya|hyaa|hae|correct|"
                  r"right|bilkul|achha)\b")
_NO = re.compile(r"\b(nahi|nahin|nai|na|naa|no|nope|nei|not|bilkul nahi)\b")


def yes_no(text: str) -> str | None:
    """'yes' / 'no' / None for a short yes-or-no answer. 'no' wins when both appear ('nahi, theek nahi')."""
    t = light(text)
    if _NO.search(t):
        return "no"
    return "yes" if _YES.search(t) else None


# ---------------------------------------------------------------- possibly-heard red-flag words (prompt spec)
# A transcript word one letter away from a red-flag word ('seenay', 'khoom', 'behos') may be that word, misheard.
# The agent then asks directly ("Is there pain in the chest?") instead of ignoring it. Real words that sit one letter
# from a target ('saas' = mother-in-law, 'khoob' = very) are never treated as near misses.
_MAYBE = {"chest": ["seena", "seene", "chhati", "chhaati", "chest"],
          "breathless": ["saans", "shash", "shwas", "breathe", "breath", "breathing"],
          "bleeding": ["khoon", "rokto", "blood", "bleeding"],
          "unconscious": ["behosh", "behoshi", "ojnan", "unconscious", "fainted"]}
_REAL_WORDS = {"saas", "saans", "khoob", "khub", "sena", "seen", "seena", "seene", "sine", "sina", "flood", "bread",
               "breed", "best", "chess", "rokte", "rokta", "roko", "shaam", "sheena", "chhota", "chhoti", "chaati",
               "baat", "bhosh", "chhat", "chhati", "shah", "cheat", "behes", "beheno", "dhoom", "koon", "kaun",
               "hoon", "jeene", "jeena", "peene", "peena", "leene", "dene", "seene", "soon", "noon", "moon", "blond",
               "bloom", "chase", "sasha", "shashi", "dhoon", "khoj", "shwet"}


def _lev1(a: str, b: str) -> bool:
    """True when a and b differ by exactly one edit (insert, delete or substitute)."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    for i in range(len(b)):
        if b[:i] + b[i + 1:] == a:
            return True
    return False


def maybe_flags(text: str, alternatives: list[str] | None = None) -> set[str]:
    """Red-flag concepts that may have been said but did not match cleanly: a near-miss spelling in the transcript,
    or a red-flag word that only an n-best alternative contains."""
    present, negated = signs(text)
    out: set[str] = set()
    known = _REAL_WORDS | {w for v in LEX.values() for p in v for w in light(p).split()} | set(_NUM) | set(_UNIT_DAYS)
    for w in re.findall(r"[a-z]+", light(text)):
        if len(w) < 5 or w in known:
            continue
        for concept, targets in _MAYBE.items():
            if any(_lev1(w, t) for t in targets):
                out.add(concept)
    for alt in alternatives or []:
        if isinstance(alt, str):
            out |= signs(alt)[0] & set(_MAYBE)
    return out - present - negated


def temperature_f(text: str) -> float | None:
    for m in re.finditer(r"\b(9[5-9]|10[0-7])(?:\.\d)?\b", light(text)):
        return float(m.group(1))
    return None


# ---------------------------------------------------------------- speaker / relation
_CAREGIVER = [(r"\b(meri|mere|amar|my)\s+(maan?|mummy|mother|mom|ma)\b|\bmaan? ko\b|\bmayer\b|\bmummy ko\b", "child"),
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
    if re.search(r"\b(maan?|mummy|mother|dadi|nani|beti|behen|patni|wife|she|her|mayer|meyer|thakuma|dida|"
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
    if has("face_droop", "speech_slurred", "arm_cant_lift") or ("one_side" in s and has("weakness", "numb")) or \
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

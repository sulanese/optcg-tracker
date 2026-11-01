"""Turn a marketplace listing title into structured facts.

classify(title, expected_code=None) -> dict | None
  Returns None for listings that should never count as a sale of a single card
  (lots, proxies, sealed product, other graders such as CGC, other languages).
  Otherwise returns:
    code      card code found in the title, e.g. "OP05-119" (or expected_code)
    lang      "EN" or "JP"
    grader    None (raw), "PSA" or "BGS"
    grade     numeric grade (10, 9.5 ...) or None
    black     True for Beckett Black Label
    variant   "Base" | "Alt Art" | "Manga" | "SP" | "Treasure" | "Gold" | "Pre-Release"
"""
import re

CODE_RE = re.compile(r"\b(OP|EB|ST|PRB)\s?-?\s?(\d{2})\s?-\s?(\d{3})\b|\bP\s?-\s?(\d{3})\b", re.I)

# Anything matching these is not a single, sellable, in-scope card.
JUNK = [
    r"\blot\b", r"\blots\b", r"\bbundle\b", r"\bplayset\b", r"\bx\s?[2-9]\b", r"\b[2-9]\s?x\b",
    r"\bproxy\b", r"\bproxies\b", r"\bcustom\b", r"\borica\b", r"fan\s?made", r"\bfake\b", r"\breplica\b",
    r"\bbooster box\b", r"\bbooster pack\b", r"\bsealed\b", r"\bdisplay\b", r"\bcase\b", r"\bsleeves?\b",
    r"\bplaymat\b", r"\bbinder\b", r"\bdeck box\b", r"\bdigital\b", r"\bcode card\b",
    r"\byou pick\b", r"\bpick your\b", r"\bchoose\b", r"\bselect your\b", r"\bcomplete set\b", r"\bmaster set\b",
    r"\bempty\b", r"\bslab only\b", r"\bpsa label\b",
]
OTHER_GRADERS = r"\b(cgc|tag|ace|ags|ars|sgc|gma|hga|mnt|bcc|pca|ksa|mint grading|psg)\s?(\d|gem|pristine|mint|perfect)"
OTHER_LANGS = r"\b(chinese|simplified|traditional|korean|french|italian|german|spanish|portuguese|thai)\b|中文|简体|繁體|한국"
JP_MARK = r"\b(japanese|japan|jpn|jp|jap)\b|日本語|日本"
EN_MARK = r"\b(english|eng|en)\b"

JUNK_RE = re.compile("|".join(JUNK), re.I)
OG_RE = re.compile(OTHER_GRADERS, re.I)
OL_RE = re.compile(OTHER_LANGS, re.I)
JP_RE = re.compile(JP_MARK, re.I)
EN_RE = re.compile(EN_MARK, re.I)
PSA_RE = re.compile(r"\bpsa\s?(?:gem\s?(?:mint|mt)\s?)?(10|[1-9](?:\.5)?)\b", re.I)
BGS_RE = re.compile(r"\b(?:bgs|beckett)\s?(?:black\s?label\s?)?(?:pristine\s?|gem\s?mint\s?)?(10|9\.5|[1-9](?:\.5)?)\b", re.I)
BLACK_RE = re.compile(r"black\s?label", re.I)


def norm_code(m):
    if m.group(4):
        return f"P-{m.group(4)}"
    return f"{m.group(1).upper()}{m.group(2)}-{m.group(3)}"


def find_codes(title):
    return {norm_code(m) for m in CODE_RE.finditer(title)}


def variant_of(t):
    t = t.lower()
    if re.search(r"\bmanga\b|comic\s?parallel|コミパラ", t):
        return "Manga"
    if re.search(r"\bsp\b|\bspecial card\b|\bsp card\b|\bsp foil\b", t):
        return "SP"
    if re.search(r"\btreasure\b|\btr\b", t):
        return "Treasure"
    if re.search(r"\bgold(en)?\b|\bgold\s?foil\b", t):
        return "Gold"
    if re.search(r"pre-?\s?release|\bprerelease\b", t):
        return "Pre-Release"
    if re.search(r"\balt(ernate|ernative)?\.?\s?art\b|\bparallel\b|\baa\b|\bp1\b|\bp2\b|パラレル", t):
        return "Alt Art"
    return "Base"


def classify(title, expected_code=None):
    if not title:
        return None
    t = " ".join(title.split())
    if JUNK_RE.search(t) or OG_RE.search(t) or OL_RE.search(t):
        return None
    codes = find_codes(t)
    if len(codes) > 1:
        return None                      # multi-card listing
    code = next(iter(codes), None)
    if expected_code:
        if code and code != expected_code:
            return None                  # search hit a different card
        code = expected_code
    if not code:
        return None

    grader = grade = None
    black = False
    m = PSA_RE.search(t)
    b = BGS_RE.search(t)
    if m and b:
        return None                      # ambiguous (e.g. "PSA 10 like BGS 9.5")
    if m:
        grader, grade = "PSA", float(m.group(1))
    elif b:
        grader, grade = "BGS", float(b.group(1))
        black = bool(BLACK_RE.search(t))
    elif re.search(r"\b(psa|bgs|beckett|graded|slab)\b", t, re.I):
        return None                      # graded but grade unreadable

    jp, en = bool(JP_RE.search(t)), bool(EN_RE.search(t))
    if jp and en:
        return None
    lang = "JP" if jp else "EN"         # eBay US listings without a marker are almost always English

    return {"code": code, "lang": lang, "grader": grader, "grade": grade, "black": black, "variant": variant_of(t)}

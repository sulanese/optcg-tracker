import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "collector"))
from classify import classify

CASES = [
    # title, expected (code, lang, grader, grade, variant) or None
    ("Monkey D Luffy OP05-119 Manga Rare SEC Awakening of the New Era English PSA 10", ("OP05-119", "EN", "PSA", 10.0, "Manga")),
    ("PSA 10 GEM MINT Monkey.D.Luffy OP05-119 Japanese Manga Parallel", ("OP05-119", "JP", "PSA", 10.0, "Manga")),
    ("One Piece Card Game Nami OP01-016 Alt Art Romance Dawn NM", ("OP01-016", "EN", None, None, "Alt Art")),
    ("Nami OP01-016 Parallel JP Japanese Romance Dawn", ("OP01-016", "JP", None, None, "Alt Art")),
    ("Boa Hancock EB03-061 SP Heroines Edition English BGS 9.5", ("EB03-061", "EN", "BGS", 9.5, "SP")),
    ("Shanks OP01-120 SEC Beckett Black Label 10 Pristine", ("OP01-120", "EN", "BGS", 10.0, "Base")),
    ("Shanks OP01-120 Alternate Art Secret Rare", ("OP01-120", "EN", None, None, "Alt Art")),
    ("Zoro OP 01-001 leader one piece", ("OP01-001", "EN", None, None, "Base")),
    ("Uta P-062 promo japanese", ("P-062", "JP", None, None, "Base")),
    # excluded
    ("Luffy OP05-119 CGC 10 Pristine", None),
    ("Luffy OP05-119 TAG 10", None),
    ("One Piece OP05 lot of 50 cards OP05-119 OP05-118", None),
    ("Luffy OP05-119 Manga Proxy Custom Orica", None),
    ("OP-05 Awakening of the New Era Booster Box Sealed Japanese", None),
    ("Luffy OP05-119 Simplified Chinese PSA 10", None),
    ("Luffy OP05-119 graded slab", None),
    ("Nami OP01-016 x4 playset", None),
    ("Shanks OP01-120 Manga Art Card Custom Gold Metal", None),
    ("Luffy OP05-119 Manga Reproduction Holo", None),
    ("One Piece Inspired Luffy OP05-119 Sticker", None),
    ("Luffy OP05-119 Manga Rare Damaged Crease", None),
    ("Luffy OP05-119 Acrylic Stand", None),
    ("Monkey D Luffy OP05-119 SEC printed holo English NM", ("OP05-119", "EN", None, None, "Base")),
]


def test_cases():
    bad = []
    for title, want in CASES:
        got = classify(title)
        if want is None:
            if got is not None:
                bad.append((title, got))
            continue
        if got is None or (got["code"], got["lang"], got["grader"], got["grade"], got["variant"]) != want:
            bad.append((title, got, want))
    assert not bad, "\n".join(map(str, bad))


def test_allowed_variants():
    base_only = {"Base", "Pre-Release"}
    assert classify("Sabo OP13-004 SP Leader 5000 EN", allowed=base_only)["variant"] == "Base"
    assert classify("Usopp ST01-002 Promo Manga FILM RED", allowed=base_only)["variant"] == "Base"
    par = {"Base", "Pre-Release", "Alt Art", "Manga", "Gold", "Treasure"}
    assert classify("Bonney OP13-108 Alternate Art SP", allowed=par)["variant"] == "Alt Art"
    assert classify("Luffy OP05-119 Manga Rare", allowed=par)["variant"] == "Manga"
    assert classify("Okiku OP01-035 SP card", allowed=par | {"SP"})["variant"] == "SP"


def test_expected_code_mismatch():
    assert classify("Nami OP01-016 Alt Art", expected_code="OP05-119") is None
    assert classify("Nami alt art romance dawn", expected_code="OP01-016")["code"] == "OP01-016"


if __name__ == "__main__":
    test_cases(); test_allowed_variants(); test_expected_code_mismatch(); print("ok", len(CASES))

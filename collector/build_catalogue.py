"""Build the OPTCG card catalogue: one row per tradable printing (base + every parallel/alt-art image)."""
import json, re, csv, sys, collections
SRC = sys.argv[1]   # repo dir
OUT = sys.argv[2]

SETS = [  # code, EN name, JP name, type, JP date, EN date
 ("OP-01","Romance Dawn","ロマンスドーン","Booster","2022-07-22","2022-12-02"),
 ("OP-02","Paramount War","頂上決戦","Booster","2022-11-04","2023-03-10"),
 ("OP-03","Pillars of Strength","強大な敵","Booster","2023-02-11","2023-06-30"),
 ("OP-04","Kingdoms of Intrigue","謀略の王国","Booster","2023-05-27","2023-09-22"),
 ("OP-05","Awakening of the New Era","新時代の主役","Booster","2023-08-26","2023-12-08"),
 ("OP-06","Wings of the Captain","双璧の覇者","Booster","2023-11-25","2024-03-15"),
 ("EB-01","Memorial Collection","メモリアルコレクション","Extra Booster","2024-01-27","2024-05-03"),
 ("OP-07","500 Years in the Future","500年後の未来","Booster","2024-02-24","2024-06-28"),
 ("OP-08","Two Legends","二つの伝説","Booster","2024-05-25","2024-09-13"),
 ("PRB-01","One Piece Card The Best","ONE PIECE CARD THE BEST","Premium Booster","2024-07-27","2024-11-08"),
 ("OP-09","Emperors in the New World","新たなる皇帝","Booster","2024-08-31","2024-12-13"),
 ("OP-10","Royal Blood","王族の血統","Booster","2024-11-30","2025-03-21"),
 ("EB-02","Anime 25th Collection","Anime 25th collection","Extra Booster","2025-01-25","2025-05-09"),
 ("OP-11","A Fist of Divine Speed","神速の拳","Booster","2025-03-01","2025-06-06"),
 ("OP-12","Legacy of the Master","師弟の絆","Booster","2025-05-31","2025-08-22"),
 ("PRB-02","One Piece Card The Best vol.2","ONE PIECE CARD THE BEST vol.2","Premium Booster","2025-07-26","2025-10-03"),
 ("OP-13","Carrying on His Will","受け継がれる意志","Booster","2025-08-23","2025-11-07"),
 ("EB-03","One Piece Heroines Edition","Heroines Edition","Extra Booster","2025-10-25","2026-02-20"),
 ("OP-14","The Azure Sea's Seven","蒼海の七傑","Booster","2025-11-22","2026-01-16"),
 ("EB-04","Egghead Crisis","EGGHEAD CRISIS","Extra Booster","2026-01-31","2026-01-16"),  # EN: inside OP14-EB04 / OP15-EB04
 ("OP-15","Adventure on Kami's Island","神の島の冒険","Booster","2026-02-28","2026-04-03"),
 ("OP-16","The Time of Battle","決戦の刻","Booster","2026-05-30","2026-06-12"),
 ("OP-17","The World's Strongest Warriors","世界最強の戦士","Booster","2026-08-22","2026-08-28"),
 ("EB-05","Heroines Edition vol.2","Heroines Edition vol.2","Extra Booster","2026-10-31","2026-10-30"),
 ("OP-18","The Dominance of God","","Booster","2026-11-21","2026-11-20"),  # upcoming
]
setinfo = {s[0]: s for s in SETS}

def norm_set(prefix):  # 'OP05' -> 'OP-05', 'PRB01' -> 'PRB-01', 'P' -> 'Promo'
    if prefix == "P": return "Promo"
    m = re.match(r"([A-Z]+)(\d+)", prefix); return f"{m.group(1)}-{m.group(2)}"

d = json.load(open(f"{SRC}/CardDb3.json"))["Cards"]
reprint = json.load(open(f"{SRC}/CardDB-NewFormat"))["Cards"]   # PRB-01 reprint printings
prb_imgs = {u.split("?")[0] for r in reprint for u in r.get("Images", [])}
old_rarity = {}
for fn in ("CardDb.json", "CardDb2.json"):
    for r in json.load(open(f"{SRC}/{fn}"))["Cards"]:
        if not r.get("Alt") and "Rarity" in r: old_rarity[r["CardNum"].lstrip("#")] = r["Rarity"]
def set_from_cardsets(txt):
    m = re.search(r"\[([A-Z]+)-?(\d+)\]", txt or "")
    return f"{m.group(1)}-{m.group(2)}" if m else None
unknown = [0]
def unknown_count(): return unknown[0]

rows, seen = [], set()
for r in d:
    code = r["CardNum"].lstrip("#")
    base_set = norm_set(code.split("-")[0])
    imgs = r.get("Images") or [r["Img"]]
    sp_img = r["Img"].split("?")[0] if r["Rarity"] == "SP CARD" else None
    for u in imgs:
        clean = u.split("?")[0]
        vid = clean.rsplit("/", 1)[1].replace(".png", "")       # e.g. OP05-119_p2
        if vid in seen: continue
        seen.add(vid)
        m = re.search(r"_(p|r)(\d+)$", vid)
        variant = "Base" if not m else (f"Parallel {m.group(2)}" if m.group(1) == "p" else f"Reprint {m.group(2)}")
        set_code = "PRB-01" if clean in prb_imgs and m else base_set
        rarity = r["Rarity"]
        if sp_img:
            if clean == sp_img:
                variant, rarity = "SP", "SP"
                set_code = set_from_cardsets(r.get("CardSets")) or set_code
            else:
                rarity = old_rarity.get(code, "?")
                if rarity == "?": unknown[0] += 1
        s = setinfo.get(set_code)
        rows.append({
            "printing_id": vid, "card_code": code, "name": r["Name"], "rarity": rarity,
            "variant": variant, "card_type": r.get("CardType", "").title(), "color": r.get("Color", ""),
            "traits": r.get("Type", ""), "set_code": set_code, "set_name": s[1] if s else r.get("CardSets", "").replace("Card Set(s)", "").strip(),
            "jp_release": s[4] if s else "", "en_release": s[5] if s else "",
            "img_en": f"https://en.onepiece-cardgame.com/images/cardlist/card/{vid}.png",
            "img_jp": f"https://www.onepiece-cardgame.com/images/cardlist/card/{vid}.png",
            "tags": "",
        })

with open(f"{OUT}/cards.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
json.dump(rows, open(f"{OUT}/cards.json", "w"), ensure_ascii=False)
with open(f"{OUT}/sets.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["set_code","name_en","name_jp","type","jp_release","en_release","printings_in_catalogue"])
    cnt = collections.Counter(r["set_code"] for r in rows)
    for s in SETS: w.writerow(list(s) + [cnt.get(s[0], 0)])
    w.writerow(["ST-01..ST-36","Starter Decks","スタートデッキ","Starter Deck","2022-07-08","2022-12-02", sum(v for k,v in cnt.items() if k.startswith("ST"))])
    w.writerow(["Promo","Promotional cards","プロモーションカード","Promo","","", cnt.get("Promo",0)])
print("unknown rarity", unknown_count()); print("printings", len(rows), "base cards", len({r['card_code'] for r in rows}))
print(collections.Counter(r["variant"].split()[0] for r in rows))
print(sorted(collections.Counter(r["set_code"] for r in rows).items()))

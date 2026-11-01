"""Rebuild the website data (docs/data/*.json) from everything collected so far.

Inputs
  data/catalogue/cards.csv        every printing (official card list)
  data/catalogue/sets.csv         set names and release dates
  data/sales/*.jsonl              sold listings saved by run.py
  data/asks/latest.json           current lowest asks
  data/manual/sales_manual.csv    sales you type in (SNKRDUNK, Mercari, Yahoo, shows ...), JPY or USD
  data/manual/pop.csv             PSA / BGS population counts (CGC never counted)
  data/manual/tags.csv            labels such as Waifu, matched on character name
  data/manual/variant_images.csv  which printing image to show for a variant (e.g. Manga -> OP05-119_p2)
Outputs
  docs/data/catalogue.json, docs/data/summary.json
Runs without network; JPY rates are refreshed when the network is available.
"""
import csv, datetime as dt, glob, json, os, re, statistics, urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")
P = lambda *a: os.path.join(ROOT, *a)
FALLBACK_JPY_PER_USD = 150.0


def rcsv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


# ---------- exchange rates ----------
def fx_table():
    path = P("data", "state", "fx.json")
    try:
        fx = json.load(open(path))
    except Exception:
        fx = {}
    today = dt.date.today().isoformat()
    if today not in fx and os.environ.get("NO_NETWORK") != "1":
        try:
            with urllib.request.urlopen("https://api.frankfurter.app/latest?from=USD&to=JPY", timeout=15) as r:
                fx[today] = float(json.loads(r.read())["rates"]["JPY"])
            save(path, fx)
        except Exception as e:
            print("FX update skipped:", e)
    return fx


def jpy_rate(fx, day):
    keys = sorted(k for k in fx if k <= day) or sorted(fx)
    return fx[keys[-1]] if keys else FALLBACK_JPY_PER_USD


# ---------- catalogue ----------
def build_catalogue():
    cards = rcsv(P("data", "catalogue", "cards.csv"))
    sets = rcsv(P("data", "catalogue", "sets.csv"))
    tags = rcsv(P("data", "manual", "tags.csv"))
    img_over = {(r["code"], r["variant"]): r["printing_id"] for r in rcsv(P("data", "manual", "variant_images.csv"))}
    pats = [(re.compile(r"(^|[^A-Za-z])" + re.escape(t["name"]) + r"([^A-Za-z]|$)", re.I), t["tag"], t.get("card_types", ""))
            for t in tags]
    cat = {}
    for r in cards:
        c = cat.setdefault(r["card_code"], {"name": r["name"], "set": None, "rarity": None, "type": r["card_type"],
                                             "img": {}, "tags": []})
        v = r["variant"]
        if v == "Base":
            c["set"], c["rarity"] = r["set_code"], r["rarity"]
            c["img"]["Base"] = r["printing_id"]
        elif v == "SP":
            c["img"]["SP"] = r["printing_id"]
        elif v.startswith("Parallel"):
            n = int(v.split()[1])
            c.setdefault("_par", []).append((n, r["printing_id"]))
    for code, c in cat.items():
        par = sorted(c.pop("_par", []))
        if par:
            c["img"]["Alt Art"] = par[0][1]
            c["img"]["Manga"] = par[-1][1]          # best guess until set in variant_images.csv
            c["img"]["Gold"] = c["img"]["Treasure"] = par[-1][1]
        for (oc, ov), pid in img_over.items():
            if oc == code:
                c["img"][ov] = pid
        c["set"] = c["set"] or code.split("-")[0]
        for rx, tag, types in pats:
            if (not types or c["type"] in types.split("|")) and rx.search(c["name"]) and tag not in c["tags"]:
                c["tags"].append(tag)
        if code.startswith("P-") and "Promo" not in c["tags"]:
            c["tags"].append("Promo")
    return cat, sets


# ---------- sales ----------
def grade_label(s):
    if not s.get("grader"):
        return "Raw"
    g = f'{float(s["grade"]):g}'
    return f'{s["grader"]} {g}{" BL" if s.get("black") else ""}'


def load_sales(fx):
    sales = []
    for path in sorted(glob.glob(P("data", "sales", "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    sales.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    for r in rcsv(P("data", "manual", "sales_manual.csv")):
        try:
            price = float(r["price"])
        except ValueError:
            continue
        day = r["date"][:10]
        if r.get("currency", "USD").upper() == "JPY":
            price = round(price / jpy_rate(fx, day), 2)
        grader = (r.get("grader") or "").upper() or None
        if grader not in (None, "PSA", "BGS"):
            continue                               # CGC and others are not tracked
        sales.append({"code": r["code"].strip().upper(), "variant": r.get("variant") or "Base",
                      "lang": (r.get("lang") or "JP").upper(), "grader": grader,
                      "grade": float(r["grade"]) if r.get("grade") else None, "black": False,
                      "price": price, "qty": int(r.get("qty") or 1), "at": r["date"][:16],
                      "src": r.get("source") or "Manual", "url": r.get("url") or None})
    return sales


def med(xs):
    return statistics.median(xs) if xs else None


def build_rows(sales, asks, pop, now):
    rows = {}
    def row(code, variant, lang):
        return rows.setdefault((code, variant, lang), {"code": code, "variant": variant, "lang": lang, "_s": []})
    for s in sales:
        row(s["code"], s["variant"], s["lang"])["_s"].append(s)
    for k, v in asks.items():
        code, variant, lang, bucket = k.split("|")
        r = row(code, variant, lang)
        r.setdefault("asks", {})[bucket] = v
    for p in pop:
        r = row(p["code"].strip().upper(), p.get("variant") or "Base", (p.get("lang") or "EN").upper())
        g = (p.get("grader") or "").upper()
        if g not in ("PSA", "BGS"):
            continue
        try:
            entry = [int(p["top_count"]), int(p["total"])]
        except (ValueError, KeyError):
            continue
        if g == "BGS":
            entry.append(int(p.get("black_label") or 0))
        r.setdefault("pop", {})[g] = entry

    d = lambda days: (now - dt.timedelta(days=days)).isoformat()
    out = []
    for r in rows.values():
        ss = sorted(r.pop("_s"), key=lambda s: s["at"])
        raw = [s for s in ss if not s["grader"]]
        raw365 = [s for s in raw if s["at"] >= d(365)]
        m = med([s["price"] for s in raw365])
        clean = [s for s in raw365 if m and m / 4 <= s["price"] <= m * 4]
        last7 = [s["price"] for s in raw if s["at"] >= d(7)]
        prev = [s["price"] for s in raw if d(37) <= s["at"] < d(7)]
        psa10 = [s for s in ss if s["grader"] == "PSA" and s["grade"] == 10]
        asks_ = r.get("asks", {})
        pop_ = r.get("pop", {})
        out.append({
            "code": r["code"], "variant": r["variant"], "lang": r["lang"],
            "last": {"p": raw[-1]["price"], "at": raw[-1]["at"], "src": raw[-1]["src"]} if raw else None,
            "lo": min((s["price"] for s in clean), default=None),
            "hi": max((s["price"] for s in clean), default=None),
            "d7": round((med(last7) / med(prev) - 1) * 100, 1) if len(last7) >= 2 and len(prev) >= 2 else None,
            "sales30": sum(s.get("qty", 1) for s in ss if s["at"] >= d(30)),
            "raw30": sum(s.get("qty", 1) for s in raw if s["at"] >= d(30)),
            "ask": asks_.get("raw"),
            "psa10ask": asks_.get("PSA10"),
            "psa10": {"p": psa10[-1]["price"], "at": psa10[-1]["at"]} if psa10 else None,
            "pop": pop_,
            "gem": round(pop_["PSA"][0] / pop_["PSA"][1] * 100) if pop_.get("PSA") and pop_["PSA"][1] else None,
            "recent": [[s["at"], s["price"], grade_label(s), s["src"], s.get("url")] for s in reversed(ss[-25:])],
            "first": ss[0]["at"] if ss else None,
        })
    return out


def main():
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    fx = fx_table()
    cat, sets = build_catalogue()
    sales = load_sales(fx)
    try:
        asks = json.load(open(P("data", "asks", "latest.json")))
    except Exception:
        asks = {}
    pop = rcsv(P("data", "manual", "pop.csv"))
    rows = [r for r in build_rows(sales, asks, pop, now) if r["code"] in cat]
    try:
        runs = json.load(open(P("data", "state", "runs.json")))
    except Exception:
        runs = []
    save(P("docs", "data", "catalogue.json"), {"cards": cat, "sets": sets})
    save(P("docs", "data", "summary.json"), {
        "updated": now.isoformat(timespec="minutes") + "Z", "jpy_per_usd": jpy_rate(fx, now.date().isoformat()),
        "sales_total": len(sales), "last_run": runs[-1] if runs else None,
        "since": min((s["at"] for s in sales), default=None), "rows": rows})
    print(f"summary: {len(rows)} rows, {len(sales)} sales, {len(cat)} cards")


if __name__ == "__main__":
    main()

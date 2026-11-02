"""One collection run. Called on a schedule by GitHub Actions.

  python collector/run.py            # needs EBAY_CLIENT_ID / EBAY_CLIENT_SECRET
  python collector/run.py --codes OP05-119,OP01-120   # only these cards

Each run picks the cards that are most overdue (chase cards are refreshed 3x as often),
saves classified sold listings to data/sales/YYYY-MM.jsonl (deduplicated) and the latest
lowest asks to data/asks/latest.json, then rebuilds the website data.
"""
import argparse, csv, datetime as dt, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from classify import classify
from ebay import Ebay, EbayError
import summarize

ROOT = os.path.join(os.path.dirname(__file__), "..")
P = lambda *a: os.path.join(ROOT, *a)
CARDS_PER_RUN = int(os.environ.get("CARDS_PER_RUN", "150"))   # 1 Browse call per card; 24 runs/day = 3,600 calls, under eBay's 5,000/day limit
HIGH = {"SEC", "SP", "L", "SR", "P", "TR"}


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def catalogue_codes():
    """Refresh weight per card code, and the variants each code really has."""
    weight, allowed = {}, {}
    with open(P("data", "catalogue", "cards.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            code = r["card_code"]
            w = 3 if (r["variant"] != "Base" or r["rarity"] in HIGH) else 1
            weight[code] = max(weight.get(code, 1), w)
            a = allowed.setdefault(code, {"Base", "Pre-Release"})
            if r["variant"].startswith(("Parallel", "Reprint")):
                a.update({"Alt Art", "Manga", "Gold", "Treasure"})
            if r["variant"] in ("SP", "Treasure"):
                a.add(r["variant"])
    return weight, allowed


def pick(weight, state, n, now):
    def overdue(code):
        last = state.get(code)
        age = (now - dt.datetime.fromisoformat(last)).total_seconds() / 3600 if last else 1e6
        return age * weight[code]
    return sorted(weight, key=overdue, reverse=True)[:n]


def lowest_credible(items):
    """Cheapest listing that is not suspiciously far below the others.

    Fakes and novelty prints cluster at the bottom of the price list, so with 4+ listings
    anything under 40% of the median is ignored. A single listing is only trusted if it
    is the only evidence we have; it is flagged with n=1 on the site.
    """
    prices = sorted(i["p"] for i in items)
    if len(prices) >= 4:
        floor = 0.4 * prices[len(prices) // 2]
        items = [i for i in items if i["p"] >= floor]
    return min(items, key=lambda i: i["p"]) if items else None


def existing_keys(month_file):
    keys = set()
    if os.path.exists(month_file):
        with open(month_file, encoding="utf-8") as f:
            for line in f:
                try:
                    keys.add(json.loads(line)["key"])
                except Exception:
                    pass
    return keys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes")
    args = ap.parse_args()
    cid, sec = os.environ.get("EBAY_CLIENT_ID"), os.environ.get("EBAY_CLIENT_SECRET")
    if not cid or not sec:
        sys.exit("Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET (GitHub: Settings > Secrets and variables > Actions).")

    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    weight, allowed = catalogue_codes()
    state = load_json(P("data", "state", "last_fetched.json"), {})
    codes = args.codes.split(",") if args.codes else pick(weight, state, CARDS_PER_RUN, now)
    asks = load_json(P("data", "asks", "latest.json"), {})
    eb = Ebay(cid, sec)

    new_sales, errors = [], 0
    for i, code in enumerate(codes):
        try:
            # lowest asks per (variant, lang, grade bucket)
            groups = {}
            for it in eb.active(code):
                c = classify(it["title"], expected_code=code, allowed=allowed.get(code))
                if not c or it["currency"] != "USD" or it["price"] <= 0:
                    continue
                bucket = "raw" if not c["grader"] else f'{c["grader"]}{c["grade"]:g}'
                k = f'{code}|{c["variant"]}|{c["lang"]}|{bucket}'
                groups.setdefault(k, []).append({"p": round(it["price"] + it["ship"], 2), "url": it["url"], "t": it["title"][:120]})
            for k in [k for k in asks if k.startswith(code + "|")]:
                del asks[k]
            for k, items in groups.items():
                v = lowest_credible(items)
                if v:
                    asks[k] = {**v, "n": len(items), "at": now.isoformat(timespec="minutes")}

            sold = eb.sold(code)
            for it in sold or []:
                c = classify(it["title"], expected_code=code, allowed=allowed.get(code))
                if not c or it["currency"] != "USD" or not it["sold_at"]:
                    continue
                key = f'{it["item_id"]}|{it["sold_at"][:16]}|{it["price"]}'
                new_sales.append({"key": key, "code": code, "variant": c["variant"], "lang": c["lang"],
                                  "grader": c["grader"], "grade": c["grade"], "black": c["black"],
                                  "price": it["price"], "qty": it["qty"], "at": it["sold_at"][:16],
                                  "src": "eBay", "url": it["url"]})
            state[code] = now.isoformat(timespec="minutes")
        except EbayError as e:
            errors += 1
            print(f"{code}: {e}")
            if "HTTP 429" in str(e) or errors > 25:
                print("Stopping early (rate limit or repeated errors); progress so far is saved.")
                break
        if i % 50 == 0:
            print(f"{i}/{len(codes)} cards, {eb.calls} API calls")

    # append new sold records, deduplicated, into monthly files
    by_month = {}
    for s in new_sales:
        by_month.setdefault(s["at"][:7], []).append(s)
    added = 0
    for month, recs in by_month.items():
        path = P("data", "sales", f"{month}.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        keys = existing_keys(path)
        with open(path, "a", encoding="utf-8") as f:
            for r in recs:
                if r["key"] not in keys:
                    keys.add(r["key"]); added += 1
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

    save_json(P("data", "asks", "latest.json"), asks)
    save_json(P("data", "state", "last_fetched.json"), state)
    log = load_json(P("data", "state", "runs.json"), [])
    log.append({"at": now.isoformat(timespec="minutes"), "cards": len(codes), "calls": eb.calls,
                "new_sales": added, "insights": eb.insights_ok, "errors": errors})
    save_json(P("data", "state", "runs.json"), log[-200:])
    print(f"done: {len(codes)} cards, {eb.calls} calls, {added} new sales, insights={eb.insights_ok}, errors={errors}")
    summarize.main()


if __name__ == "__main__":
    main()

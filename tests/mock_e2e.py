"""End-to-end run against a fake eBay API (no network, no keys).

  python tests/mock_e2e.py <copy-of-repo>
Runs collector/run.py inside the given copy with canned Browse + Marketplace Insights responses.
"""
import io, json, os, random, sys, datetime as dt, urllib.request, urllib.parse, urllib.error

root = os.path.abspath(sys.argv[1])
sys.path.insert(0, os.path.join(root, "collector"))
os.environ.update(EBAY_CLIENT_ID="x", EBAY_CLIENT_SECRET="y", NO_NETWORK="1")
INSIGHTS = os.environ.get("MOCK_INSIGHTS", "1") == "1"
rnd = random.Random(7)
now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

CARDS = {"OP05-119": ("Monkey.D.Luffy", 900), "OP01-120": ("Shanks", 420), "EB03-061": ("Boa Hancock", 260), "OP01-016": ("Nami", 150)}


def titles(code, name):
    return [(f"{name} {code} Manga Rare English", 1.0), (f"{name} {code} Alt Art NM", .35), (f"{name} {code} Japanese Parallel", .3),
            (f"PSA 10 {name} {code} Manga", 3.0), (f"{name} {code} CGC 10", 2.5), (f"{name} {code} lot of 3", .9), (f"{name} {code} SP Card", .8)]


class R(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass


def fake(req, timeout=30):
    url = req.full_url
    if "oauth2/token" in url:
        scope = urllib.parse.parse_qs(req.data.decode())["scope"][0]
        if "insights" in scope and not INSIGHTS:
            raise urllib.error.HTTPError(url, 400, "bad", {}, io.BytesIO(b'{"error":"invalid_scope"}'))
        return R(json.dumps({"access_token": "t", "expires_in": 7200}).encode())
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["q"][0]
    name, base = CARDS.get(q, ("Card", 5))
    if "item_summary" in url:
        items = [{"itemId": f"v1|{q}|{i}", "title": t, "price": {"value": f"{base*m*rnd.uniform(1.05,1.3):.2f}", "currency": "USD"},
                  "shippingOptions": [{"shippingCost": {"value": "4.99", "currency": "USD"}}], "itemWebUrl": f"https://www.ebay.com/itm/{i}"}
                 for i, (t, m) in enumerate(titles(q, name))]
        return R(json.dumps({"itemSummaries": items}).encode())
    sales = []
    for i in range(60):
        t, m = rnd.choice(titles(q, name))
        day = now - dt.timedelta(days=rnd.uniform(0, 89), hours=rnd.uniform(0, 23))
        trend = 1 + (89 - (now - day).days) / 400
        sales.append({"itemId": f"v1|{q}|s{i}", "title": t, "lastSoldPrice": {"value": f"{base*m*trend*rnd.uniform(.85,1.15):.2f}", "currency": "USD"},
                      "lastSoldDate": day.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "totalSoldQuantity": 1, "itemWebUrl": f"https://www.ebay.com/itm/s{i}"})
    return R(json.dumps({"itemSales": sales}).encode())


urllib.request.urlopen = fake
import run
sys.argv = ["run.py", "--codes", ",".join(CARDS)]
run.main()
s = json.load(open(os.path.join(root, "docs", "data", "summary.json")))
for r in sorted(s["rows"], key=lambda r: -r["sales30"])[:8]:
    print(r["code"], r["variant"], r["lang"], "last", r["last"] and r["last"]["p"], "lo/hi", r["lo"], r["hi"], "d7", r["d7"],
          "30d", r["sales30"], "ask", r["ask"] and r["ask"]["p"], "psa10", r["psa10"] and r["psa10"]["p"])
assert s["rows"] and s["last_run"]["insights"] == INSIGHTS
print("e2e ok; rows", len(s["rows"]), "sales", s["sales_total"])

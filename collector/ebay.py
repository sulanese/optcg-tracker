"""Minimal eBay API client (standard library only).

Uses two official APIs:
  * Browse API              -> current listings (lowest asks). Open to every developer account.
  * Marketplace Insights API -> sold items from the last 90 days. Limited release: needs eBay's approval.
No seller names or other eBay user data are kept.
"""
import base64, json, os, time, urllib.parse, urllib.request, urllib.error

API = os.environ.get("EBAY_API_BASE", "https://api.ebay.com")
SCOPE_BASE = "https://api.ebay.com/oauth/api_scope"
SCOPE_INSIGHTS = "https://api.ebay.com/oauth/api_scope/buy.marketplace.insights"
MARKETPLACE = os.environ.get("EBAY_MARKETPLACE", "EBAY_US")
CATEGORY = os.environ.get("EBAY_CATEGORY_IDS", "183454")  # CCG Individual Cards


class EbayError(Exception):
    pass


class Ebay:
    def __init__(self, client_id, client_secret, opener=None):
        self.cid, self.secret = client_id, client_secret
        self.open = opener or urllib.request.urlopen
        self.tokens = {}
        self.calls = 0
        self.insights_ok = None   # unknown until first try

    # ---- auth ----
    def token(self, scope):
        tok = self.tokens.get(scope)
        if tok and tok[1] > time.time() + 60:
            return tok[0]
        body = urllib.parse.urlencode({"grant_type": "client_credentials", "scope": scope}).encode()
        auth = base64.b64encode(f"{self.cid}:{self.secret}".encode()).decode()
        req = urllib.request.Request(f"{API}/identity/v1/oauth2/token", data=body, method="POST",
                                     headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"})
        data = self._send(req)
        self.tokens[scope] = (data["access_token"], time.time() + int(data.get("expires_in", 7200)))
        return data["access_token"]

    def _send(self, req, retries=3):
        for i in range(retries):
            try:
                with self.open(req, timeout=30) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                msg = e.read().decode("utf-8", "replace")[:500]
                if e.code in (429, 500, 502, 503, 504) and i < retries - 1:
                    time.sleep(2 ** i * 3)
                    continue
                raise EbayError(f"HTTP {e.code}: {msg}")
            except urllib.error.URLError as e:
                if i < retries - 1:
                    time.sleep(2 ** i * 3); continue
                raise EbayError(str(e))

    def _get(self, path, params, scope):
        url = f"{API}{path}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token(scope)}",
                                                   "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE,
                                                   "Accept-Language": "en-US"})
        self.calls += 1
        return self._send(req)

    # ---- Browse: active fixed-price listings ----
    def active(self, query, limit=200):
        params = {"q": query, "limit": limit, "filter": "buyingOptions:{FIXED_PRICE}"}  # best-match order: real cards rank above cheap junk
        if CATEGORY:
            params["category_ids"] = CATEGORY
        data = self._get("/buy/browse/v1/item_summary/search", params, SCOPE_BASE)
        out = []
        for it in data.get("itemSummaries", []) or []:
            price = it.get("price") or {}
            ship = 0.0
            for so in it.get("shippingOptions") or []:
                c = (so.get("shippingCost") or {}).get("value")
                if c is not None:
                    ship = float(c); break
            out.append({"item_id": it.get("itemId"), "title": it.get("title", ""),
                        "price": float(price.get("value", 0) or 0), "ship": ship,
                        "currency": price.get("currency", "USD"), "url": it.get("itemWebUrl"),
                        "country": (it.get("itemLocation") or {}).get("country")})
        return out

    # ---- Marketplace Insights: sold items (last 90 days) ----
    def sold(self, query, limit=200):
        if self.insights_ok is False:
            return None
        params = {"q": query, "limit": limit}
        if CATEGORY:
            params["category_ids"] = CATEGORY
        try:
            data = self._get("/buy/marketplace_insights/v1_beta/item_sales/search", params, SCOPE_INSIGHTS)
        except EbayError as e:
            if any(s in str(e) for s in ("HTTP 401", "HTTP 403", "invalid_scope", "insufficient")):
                self.insights_ok = False     # not approved yet: stop trying this run
                print("Marketplace Insights not available for these keys yet:", str(e)[:160])
                return None
            raise
        self.insights_ok = True
        out = []
        for it in data.get("itemSales", []) or []:
            price = it.get("lastSoldPrice") or {}
            out.append({"item_id": it.get("itemId"), "title": it.get("title", ""),
                        "price": float(price.get("value", 0) or 0), "currency": price.get("currency", "USD"),
                        "sold_at": it.get("lastSoldDate"), "qty": int(it.get("totalSoldQuantity") or 1),
                        "url": it.get("itemWebUrl") or it.get("itemHref")})
        return out

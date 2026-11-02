# OPTCG Market Tracker

A personal price tracker for One Piece Card Game singles (English and Japanese).
It is a free website on GitHub Pages, updated by a GitHub Actions job every hour.

| Column | Where it comes from |
|---|---|
| Last sold, 52W low/high, Δ 7D, Sales 30D | eBay sold listings (Marketplace Insights API), plus sales you add by hand |
| Raw lowest ask, PSA 10 lowest ask | eBay current listings (Browse API) |
| PSA 10 last | eBay sold listings graded PSA 10 |
| PSA pop, BGS pop, Gem rate | `data/manual/pop.csv` (you fill in; CGC is never counted) |
| Tags (Waifu, Promo) | `data/manual/tags.csv` |

Card names, codes, rarities, sets and images come from the official Bandai card list (`data/catalogue/`).

## One-time setup

1. **eBay developer account.** Sign up at developer.ebay.com. Under *Application Keys*, create a **Production** keyset and note the **App ID (Client ID)** and **Cert ID (Client Secret)**.
   If eBay asks about Marketplace Account Deletion notifications, choose the exemption. This tracker stores no eBay user or seller data, only listing titles, prices, dates and links.
2. **Sold-data access.** Request access to the **Marketplace Insights API** (limited release). Until eBay approves it, the site shows lowest asks only. Sold prices start appearing on the next run after approval, with no change needed.
3. **GitHub repo.** Create a free **public** repo (e.g. `optcg-tracker`) and upload everything in this folder.
4. **Secrets.** In the repo go to *Settings → Secrets and variables → Actions → New repository secret* and add `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET`.
5. **Website.** Go to *Settings → Pages*, then under *Build and deployment* choose *Deploy from a branch*, `main`, folder `/docs`. Your link will be `https://<your-username>.github.io/optcg-tracker/`.
6. **First run.** Go to *Actions → Collect prices → Run workflow*. After that it runs every hour on its own.

## How collection works

- Each run checks about 150 card codes, most overdue first. Chase cards (SEC, SP, Leaders, SR, promos, anything with an alt art) get checked 3× as often as commons. That is about 3,600 Browse calls a day, under eBay's default 5,000.
- Listing titles are read by `collector/classify.py`. It works out language (EN/JP), grade (PSA or BGS only), and variant (Base, Alt Art, Manga, SP, Treasure, Gold, Pre-Release). It drops lots, proxies, sealed product, CGC/TAG/other graders, and non-EN/JP languages.
- eBay only shares the **last 90 days** of sold items, so the 52-week range fills in over time as data accumulates. Older history can be added by hand (below).
- Sales are stored forever in `data/sales/YYYY-MM.jsonl`, so the history is yours.

## Adding data by hand

Edit these files on GitHub (pencil icon). Saving them rebuilds the site.

**`data/manual/sales_manual.csv`** for SNKRDUNK, Mercari, Yahoo! Auctions, shows and older sales. JPY is converted to USD at that day's rate.
```
date,code,variant,lang,grader,grade,price,currency,qty,source,url,note
2026-10-28,OP05-119,Manga,JP,PSA,10,520000,JPY,1,SNKRDUNK,,
2026-10-27,OP01-016,Alt Art,JP,,,4800,JPY,1,Mercari JP,,
```

**`data/manual/pop.csv`** for population counts from psacard.com/pop and Beckett.
```
code,variant,lang,grader,top_count,total,black_label,updated
OP05-119,Manga,EN,PSA,412,1108,,2026-10-30
OP05-119,Manga,EN,BGS,38,96,2,2026-10-30
```

**`data/manual/variant_images.csv`** sets which printing image the hover preview shows for a variant. The official list just numbers parallels `_p1`, `_p2`, and so on.
```
code,variant,printing_id
OP05-119,Manga,OP05-119_p2
```

**`data/manual/tags.csv`** holds character names and their tag (`Waifu` is a first-pass list; edit freely).

## Known limits (v1)

- All parallels of a card that are not Manga/SP/Gold/Treasure are grouped as "Alt Art".
- Listings with no language word are counted as English. Most JP listings on eBay say "Japanese".
- Card code search (`OP05-119`) misses listings that leave the code out of the title.
- The new OP-18 card list is added by re-running `collector/build_catalogue.py` on an updated card list.

## Testing without keys

```
python tests/test_classify.py
python tests/mock_e2e.py /path/to/a/copy/of/this/repo
```

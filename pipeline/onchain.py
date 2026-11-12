"""Rebuild NEAR's captured Intents revenue from the chain, not from a dashboard.

    python3 -m pipeline.onchain --from 2026-08-13 --to 2026-11-10

Reads every incoming native NEAR transfer and every incoming wNEAR transfer
to the three revenue wallets from the NearBlocks indexer (no key), drops
transfers between the three wallets, and writes daily sums to
data/raw/onchain_revenue.json together with the daily NEAR price used to
value them. The free tier is slow: a 90-day range takes about 20 minutes.
"""

import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "raw", "onchain_revenue.json")
API = "https://api.nearblocks.io/v1/account/%s/%s?per_page=100%s"
PRICE = "https://coins.llama.fi/chart/coingecko:near?start=%d&span=%d&period=1d"
# The wallets NEAR sweeps Intents revenue into (the same three DefiLlama's
# adapter reads). The last one also holds the NEAR bought back.
WALLETS = [
    "fefundsadmin.sputnik-dao.near",
    "1csfundsadmin.sputnik-dao.near",
    "buybacks.multisignature.near",
]
BUYBACK = "buybacks.multisignature.near"
WNEAR = "wrap.near"
PAUSE = 13.0
YOCTO = 1e24


def call(url):
    for attempt in range(10):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "share-shift/1.0",
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            print("retry %d after HTTP %d" % (attempt + 1, err.code), flush=True)
            time.sleep(PAUSE * (attempt + 2))
        except (urllib.error.URLError, TimeoutError, ValueError) as err:
            print("retry %d after %s" % (attempt + 1, type(err).__name__), flush=True)
            time.sleep(PAUSE * (attempt + 2))
    raise RuntimeError("NearBlocks did not answer after 10 tries")


def day_of(nanos):
    return datetime.datetime.fromtimestamp(int(nanos) / 1e9, datetime.timezone.utc).strftime("%Y-%m-%d")


def native_inflows(wallet, first_day, last_day, log):
    """Daily sums of TRANSFER deposits received from outside the wallet set."""
    out, cursor, pages = {}, "", 0
    while True:
        data = call(API % (wallet, "txns", ("&cursor=" + cursor) if cursor else ""))
        rows = data.get("txns") or []
        pages += 1
        stop = not rows
        for row in rows:
            day = day_of(row["block_timestamp"])
            if day < first_day:
                stop = True
                continue
            if day > last_day:
                continue
            if row.get("receiver_account_id") != wallet or not (row.get("outcomes") or {}).get("status"):
                continue
            if row.get("predecessor_account_id") in WALLETS:
                continue
            for action in row.get("actions") or []:
                if action.get("action") == "TRANSFER":
                    out[day] = out.get(day, 0.0) + float(action.get("deposit") or 0) / YOCTO
        cursor = data.get("cursor") or ""
        if pages % 5 == 0:
            log("%s native: page %d, reached %s" % (wallet, pages, day_of(rows[-1]["block_timestamp"]) if rows else "end"))
        if stop or not cursor:
            return out, pages
        time.sleep(PAUSE)


def wnear_inflows(wallet, first_day, last_day, log):
    """Daily sums of wNEAR received from outside the wallet set."""
    out, cursor, pages = {}, "", 0
    while True:
        data = call(API % (wallet, "ft-txns", ("&cursor=" + cursor) if cursor else ""))
        rows = data.get("txns") or []
        pages += 1
        stop = not rows
        for row in rows:
            day = day_of(row["block_timestamp"])
            if day < first_day:
                stop = True
                continue
            if day > last_day:
                continue
            if (row.get("ft") or {}).get("contract") != WNEAR:
                continue
            if row.get("involved_account_id") in WALLETS:
                continue
            delta = float(row.get("delta_amount") or 0)
            if delta > 0 and (row.get("outcomes") or {}).get("status"):
                out[day] = out.get(day, 0.0) + delta / YOCTO
        cursor = data.get("cursor") or ""
        if stop or not cursor:
            return out, pages
        time.sleep(PAUSE)


def run(first_day, last_day, log=print):
    start = int(datetime.datetime.strptime(first_day, "%Y-%m-%d")
                .replace(tzinfo=datetime.timezone.utc).timestamp())
    span = (datetime.date.fromisoformat(last_day) - datetime.date.fromisoformat(first_day)).days + 1
    price_url = PRICE % (start, span)
    prices = {day_of(p["timestamp"] * 1e9): p["price"]
              for p in call(price_url)["coins"]["coingecko:near"]["prices"]}
    days, pages = {}, 0
    for wallet in WALLETS:
        native, p1 = native_inflows(wallet, first_day, last_day, log)
        time.sleep(PAUSE)
        wrapped, p2 = wnear_inflows(wallet, first_day, last_day, log)
        time.sleep(PAUSE)
        pages += p1 + p2
        for day in set(native) | set(wrapped):
            days.setdefault(day, {})[wallet] = {"near": native.get(day, 0.0),
                                                "wnear": wrapped.get(day, 0.0)}
        log("%s: %.0f NEAR native, %.0f wNEAR" % (wallet, sum(native.values()), sum(wrapped.values())))
    out = {
        "source": "https://api.nearblocks.io/v1/account/{wallet}/txns and /ft-txns",
        "price_source": price_url,
        "wallets": WALLETS,
        "buyback_wallet": BUYBACK,
        "range": [first_day, last_day],
        "pages": pages,
        "note": "Incoming native NEAR and wNEAR per wallet per day; transfers between "
                "the three wallets are excluded.",
        "near_price_usd": {d: prices[d] for d in sorted(prices)},
        "days": {d: days[d] for d in sorted(days)},
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    log("wrote %s (%d days, %d pages)" % (os.path.relpath(OUT, ROOT), len(days), pages))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--from", dest="first", required=True)
    ap.add_argument("--to", dest="last", required=True)
    args = ap.parse_args()
    try:
        run(args.first, args.last)
    except RuntimeError as err:
        sys.exit("error: %s" % err)

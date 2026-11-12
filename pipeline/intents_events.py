"""Estimate a day's NEAR Intents swap volume from intents.near's own event logs.

    python3 -m pipeline.intents_events --day 2026-08-20 --sample 4000

1. Lists every transaction touching intents.near on that UTC day (FastNear
   transactions API, no key). The listing is complete, not sampled.
2. Draws a seeded random sample of those transactions and reads their
   receipts' logs.
3. Values every DIP-4 `token_diff` event at that day's price (CoinGecko ids
   from the 1Click token list, prices from DefiLlama's coins API).
4. Scales the sample to the whole day and bootstraps a 90% interval.

In a swap, the user's token_diff gives token A and takes token B, and the
solver's token_diff mirrors it. `both_sides` sums the USD value given in
every token_diff event, so a swap appears twice; `one_side` is half of that.
Only daily totals and the sample's summary are written, to
data/raw/intents_events_<day>.json. No address or hash is stored.
"""

import argparse
import datetime
import json
import os
import random
import statistics
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TX_API = "https://tx.main.fastnear.com/v0"
TOKENS = "https://1click.chaindefuser.com/v0/tokens"
PRICES = "https://coins.llama.fi/prices/historical/%d/%s"
CONTRACT = "intents.near"
PAUSE = 0.35
SEED = 20261112
STABLE = {"USDC", "USDT", "USDT0", "DAI", "USD1", "FRAX", "USDe", "PYUSD", "FDUSD", "USDH",
          "sUSDC", "USDCx", "nrUsdt", "USDS"}


def post(path, body):
    for attempt in range(8):
        try:
            req = urllib.request.Request(TX_API + path, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json",
                                                  "User-Agent": "share-shift/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            print("retry %d after HTTP %d" % (attempt + 1, err.code), flush=True)
            time.sleep(2 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, ValueError) as err:
            print("retry %d after %s" % (attempt + 1, type(err).__name__), flush=True)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("FastNear did not answer")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "share-shift/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def page_at(height):
    """Newest-first page of intents.near transactions at or below `height`."""
    return post("/account", {"account_id": CONTRACT, "resume_token": str(height << 32)})


def first_height_after(ts_ns, lo, hi):
    """Smallest block height whose transactions are at or after ts_ns."""
    while hi - lo > 50:
        mid = (lo + hi) // 2
        rows = page_at(mid)["account_txs"]
        time.sleep(PAUSE)
        if rows and int(rows[0]["tx_block_timestamp"]) >= ts_ns:
            hi = mid
        else:
            lo = mid
    return lo


def list_day(day):
    start = datetime.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
    t0 = int(start.timestamp() * 1e9)
    t1 = int((start + datetime.timedelta(days=1)).timestamp() * 1e9)
    head = post("/account", {"account_id": CONTRACT})["account_txs"][0]
    hi = int(head["tx_block_height"])
    end_h = first_height_after(t1, 100_000_000, hi)
    hashes, token, pages = [], str((end_h + 50) << 32), 0
    while True:
        data = post("/account", {"account_id": CONTRACT, "resume_token": token})
        rows = data.get("account_txs") or []
        pages += 1
        done = not rows
        for row in rows:
            ts = int(row["tx_block_timestamp"])
            if ts < t0:
                done = True
                break
            if ts < t1 and row.get("is_success", True):
                hashes.append(row["transaction_hash"])
        if pages % 50 == 0:
            print("listing page %d, %d transactions" % (pages, len(hashes)), flush=True)
        if done or not data.get("resume_token"):
            break
        token = data["resume_token"]
        time.sleep(PAUSE)
    return sorted(set(hashes)), pages


def prices_for(day):
    tokens = get(TOKENS)
    ts = int(datetime.datetime.strptime(day, "%Y-%m-%d")
             .replace(tzinfo=datetime.timezone.utc).timestamp()) + 43200
    ids = sorted({t["coingeckoId"] for t in tokens if t.get("coingeckoId")})
    hist = {}
    for i in range(0, len(ids), 40):
        chunk = ",".join("coingecko:" + x for x in ids[i:i + 40])
        coins = get(PRICES % (ts, chunk)).get("coins", {})
        hist.update({k.split(":", 1)[1]: v["price"] for k, v in coins.items()})
        time.sleep(PAUSE)
    table = {}
    for t in tokens:
        if t["symbol"] in STABLE:
            price, how = 1.0, "stable"
        elif t.get("coingeckoId") in hist:
            price, how = hist[t["coingeckoId"]], "historical"
        else:
            price, how = float(t.get("price") or 0), "current"
        table[t["assetId"]] = {"decimals": int(t["decimals"]), "price": price, "how": how}
    return table


def value_tx(tx, prices):
    """USD given in token_diff events, plus how much could not be priced."""
    given, unpriced, events = 0.0, 0, 0
    for receipt in tx.get("receipts") or []:
        outcome = (receipt.get("execution_outcome") or {}).get("outcome") or {}
        if outcome.get("executor_id") != CONTRACT:
            continue
        for line in outcome.get("logs") or []:
            if not line.startswith("EVENT_JSON:"):
                continue
            try:
                ev = json.loads(line[11:])
            except ValueError:
                continue
            if ev.get("standard") != "dip4" or ev.get("event") != "token_diff":
                continue
            for item in ev.get("data") or []:
                events += 1
                for asset, amount in (item.get("diff") or {}).items():
                    amount = int(amount)
                    if amount >= 0:
                        continue
                    p = prices.get(asset)
                    if not p:
                        unpriced += 1
                        continue
                    given += -amount / 10 ** p["decimals"] * p["price"]
    return given, events, unpriced


def run(day, sample, log=print):
    hashes, pages = list_day(day)
    log("%s: %d transactions on intents.near (%d listing pages)" % (day, len(hashes), pages))
    prices = prices_for(day)
    rng = random.Random(SEED)
    picked = rng.sample(hashes, min(sample, len(hashes)))
    values, events, unpriced = [], 0, 0
    for i in range(0, len(picked), 20):
        batch = post("/transactions", {"tx_hashes": picked[i:i + 20]})
        for tx in batch.get("transactions") or []:
            v, e, u = value_tx(tx, prices)
            values.append(v)
            events += e
            unpriced += u
        if (i // 20) % 25 == 0:
            log("details %d / %d" % (i + 20, len(picked)))
        time.sleep(PAUSE)
    n_day, n = len(hashes), len(values)
    both = statistics.mean(values) * n_day
    boot = []
    brng = random.Random(SEED + 1)
    for _ in range(1000):
        draw = [values[brng.randrange(n)] for _ in range(n)]
        boot.append(statistics.mean(draw) * n_day)
    boot.sort()
    out = {
        "day": day,
        "method": "seeded random sample of the day's intents.near transactions; token_diff "
                  "events valued at the day's price; scaled by the full transaction count",
        "sources": {"transactions": TX_API, "tokens": TOKENS, "prices": "coins.llama.fi"},
        "transactions_in_day": n_day,
        "sampled": n,
        "token_diff_events_in_sample": events,
        "unpriced_legs_in_sample": unpriced,
        "both_sides_usd": both,
        "both_sides_usd_p05": boot[49],
        "both_sides_usd_p95": boot[949],
        "one_side_usd": both / 2,
        "price_basis": {k: sum(1 for p in prices.values() if p["how"] == k)
                        for k in ("stable", "historical", "current")},
    }
    path = os.path.join(ROOT, "data", "raw", "intents_events_%s.json" % day)
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    log("both sides %.1fM (90%%: %.1fM-%.1fM), one side %.1fM; wrote %s"
        % (both / 1e6, boot[49] / 1e6, boot[949] / 1e6, both / 2e6, os.path.relpath(path, ROOT)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--day", required=True)
    ap.add_argument("--sample", type=int, default=4000)
    args = ap.parse_args()
    try:
        run(args.day, args.sample)
    except RuntimeError as err:
        sys.exit("error: %s" % err)

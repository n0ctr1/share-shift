"""Measure how much of THORChain's swap value is routed through two pools.

    python3 -m pipeline.thorchain_actions --from 2026-08-13 --to 2026-11-10 --points 180

Midgard's daily totals add up every leg, but pairing legs by daily sums is
only an upper bound on double swaps (a RUNE->BTC swap and a BTC->RUNE swap on
the same day look like one routed swap). This script reads individual swap
actions instead: a swap that names two pools went asset -> RUNE -> asset and
appears twice in the totals; a swap with one pool appears once.

It takes `points` evenly spaced moments across the range, reads the 50 swaps
just before each, and values each swap's input at Midgard's own inPriceUSD.
The fraction of value in two-pool swaps, p, gives the one-side factor
1 / (1 + p) for the reported total. A bootstrap over the sampled moments
gives a 90% interval. Only the summary is written.
"""

import argparse
import datetime
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "raw", "actions_thorchain-dex.json")
URL = "https://gateway.liquify.com/chain/thorchain_midgard/v2/actions?type=swap&limit=50&timestamp=%d"
SEED = 20261112


def get(url):
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "share-shift/1.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, ValueError) as err:
            print("retry %d after %s" % (attempt + 1, err), flush=True)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("Midgard did not answer")


def value(action):
    price = float((action.get("metadata", {}).get("swap") or {}).get("inPriceUSD") or 0)
    amount = sum(float(c["amount"]) for leg in action.get("in") or [] for c in leg.get("coins") or [])
    return amount / 1e8 * price


def run(first_day, last_day, points, log=print):
    t0 = int(datetime.datetime.strptime(first_day, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp())
    t1 = int(datetime.datetime.strptime(last_day, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp()) + 86400
    step = (t1 - t0) / points
    samples, seen = [], set()
    for i in range(points):
        ts = int(t0 + (i + 0.5) * step)
        page = get(URL % ts)
        single = double = 0.0
        n = 0
        for action in page.get("actions") or []:
            if action.get("status") != "success":
                continue
            key = (action.get("height"), (action.get("in") or [{}])[0].get("txID"))
            if key in seen:
                continue
            seen.add(key)
            pools = len(action.get("pools") or [])
            v = value(action)
            n += 1
            if pools >= 2:
                double += v
            else:
                single += v
        samples.append({"at": ts, "swaps": n, "single_usd": single, "double_usd": double})
        if (i + 1) % 30 == 0:
            log("point %d / %d" % (i + 1, points))
        time.sleep(0.3)

    def p_of(rows):
        tot = sum(r["single_usd"] + r["double_usd"] for r in rows)
        return sum(r["double_usd"] for r in rows) / tot if tot else None

    p = p_of(samples)
    rng = random.Random(SEED)
    boot = sorted(p_of([samples[rng.randrange(len(samples))] for _ in samples]) for _ in range(1000))
    out = {
        "source": URL % 0,
        "range": [first_day, last_day],
        "points": points,
        "swaps_read": sum(r["swaps"] for r in samples),
        "value_read_usd": sum(r["single_usd"] + r["double_usd"] for r in samples),
        "double_value_share": p,
        "double_value_share_p05": boot[49],
        "double_value_share_p95": boot[949],
        "once_factor": 1 / (1 + p),
        "method": "value-weighted share of two-pool swaps among the 50 swaps before each of "
                  "`points` evenly spaced moments; inPriceUSD from Midgard",
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    log("double-swap value share %.1f%% (90%%: %.1f%%-%.1f%%), one-side factor %.3f; wrote %s"
        % (100 * p, 100 * boot[49], 100 * boot[949], 1 / (1 + p), os.path.relpath(OUT, ROOT)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--from", dest="first", required=True)
    ap.add_argument("--to", dest="last", required=True)
    ap.add_argument("--points", type=int, default=180)
    args = ap.parse_args()
    try:
        run(args.first, args.last, args.points)
    except RuntimeError as err:
        sys.exit("error: %s" % err)

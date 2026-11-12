"""NEAR's supply and L1 activity, read from the chain and an indexer.

    python3 -m pipeline.near_token --from 2026-08-13 --to 2026-11-10

Writes data/raw/near_supply.json: total_supply from the header of the first
block at or after 00:00 UTC on the window's first day and on the day after
its last day, plus the same two points one year earlier, all from NEAR
archival RPC. The difference is net new supply (protocol rewards minted
minus fees burned), the quantity a buyback has to offset.

Writes data/raw/near_l1_daily.json: daily transactions and active accounts on
the NEAR L1 from NearBlocks' public charts endpoint (no key), for context on
how much of NEAR's activity runs through Intents rather than the L1 itself.
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
RPC = "https://archival-rpc.mainnet.fastnear.com"
CHARTS = "https://api.nearblocks.io/v1/charts"


def call(body):
    for attempt in range(6):
        try:
            req = urllib.request.Request(RPC, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json",
                                                  "User-Agent": "share-shift/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, ValueError):
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("archival RPC did not answer")


def header(height):
    """Header of the first existing block at or above `height`."""
    for h in range(height, height + 50):
        out = call({"jsonrpc": "2.0", "id": 1, "method": "block", "params": {"block_id": h}})
        if "result" in out:
            return out["result"]["header"]
    raise RuntimeError("no block near height %d" % height)


def first_block_at(day):
    ts = datetime.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp()
    lo, hi = 100_000_000, header_head()["height"]
    while hi - lo > 2:
        mid = (lo + hi) // 2
        if header(mid)["timestamp"] / 1e9 < ts:
            lo = mid
        else:
            hi = mid
    h = header(hi)
    return {"day": day, "height": h["height"],
            "time": datetime.datetime.fromtimestamp(h["timestamp"] / 1e9, datetime.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_supply_near": int(h["total_supply"]) / 1e24}


def header_head():
    return call({"jsonrpc": "2.0", "id": 1, "method": "block",
                 "params": {"finality": "final"}})["result"]["header"]


def shift(day, days):
    return (datetime.date.fromisoformat(day) + datetime.timedelta(days=days)).isoformat()


def run(first_day, last_day, log=print):
    end_day = shift(last_day, 1)
    points = [first_block_at(d) for d in (shift(first_day, -365), shift(end_day, -365),
                                          first_day, end_day)]
    for p in points:
        log("%s: block %d, total supply %.0f NEAR" % (p["day"], p["height"], p["total_supply_near"]))
    supply = {"source": RPC, "window": [first_day, last_day],
              "note": "total_supply from block headers; the window is [first_day, last_day+1).",
              "points": points}
    with open(os.path.join(ROOT, "data", "raw", "near_supply.json"), "w") as fh:
        json.dump(supply, fh, indent=1, sort_keys=True)
        fh.write("\n")

    req = urllib.request.Request(CHARTS, headers={"User-Agent": "share-shift/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        charts = json.load(resp)["charts"]
    keep = sorted(({"date": c["date"][:10], "txns": int(c.get("txns") or 0),
                    "active_accounts": int(c.get("active_accounts") or 0)}
                   for c in charts if c["date"][:10] >= shift(first_day, -400)),
                  key=lambda r: r["date"])
    with open(os.path.join(ROOT, "data", "raw", "near_l1_daily.json"), "w") as fh:
        json.dump({"source": CHARTS, "series": keep}, fh, indent=1, sort_keys=True)
        fh.write("\n")
    log("wrote data/raw/near_supply.json and data/raw/near_l1_daily.json (%d days)" % len(keep))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--from", dest="first", required=True)
    ap.add_argument("--to", dest="last", required=True)
    args = ap.parse_args()
    try:
        run(args.first, args.last)
    except RuntimeError as err:
        sys.exit("error: %s" % err)

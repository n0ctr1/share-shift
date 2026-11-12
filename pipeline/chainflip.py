"""Daily Chainflip swap volume split into first legs and routed second legs.

    python3 -m pipeline.chainflip --from 2026-08-13 --to 2026-11-10

Chainflip routes a swap between two non-USDC assets through USDC, and its
indexer records the USDC leg as the swap's intermediate amount. DefiLlama's
Chainflip volume equals the sum of input values plus intermediate values,
so routed swaps are counted twice. This script reads every executed swap
from Chainflip's public GraphQL indexer and writes, per day, the input value
(each swap once) and the intermediate value (the second leg) to
data/raw/legs_chainflip-amm.json. Only daily sums are stored.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "raw", "legs_chainflip-amm.json")
URL = "https://explorer-service-processor.chainflip.io/graphql"
QUERY = ("{ allSwaps(first: 1000, orderBy: ID_DESC%s) { pageInfo { endCursor hasNextPage } "
         "nodes { type swapExecutedBlockTimestamp swapInputValueUsd intermediateValueUsd } } }")


def call(query):
    for attempt in range(6):
        try:
            req = urllib.request.Request(URL, data=json.dumps({"query": query}).encode(),
                                         headers={"Content-Type": "application/json",
                                                  "User-Agent": "share-shift/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.load(resp)
            if "errors" in body:
                raise ValueError(body["errors"][0].get("message"))
            return body["data"]["allSwaps"]
        except (urllib.error.URLError, TimeoutError, ValueError) as err:
            print("retry %d after %s" % (attempt + 1, err), flush=True)
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("the Chainflip indexer did not answer")


def run(first_day, last_day, log=print):
    days, cursor, pages = {}, None, 0
    while True:
        page = call(QUERY % ((', after: "%s"' % cursor) if cursor else ""))
        pages += 1
        stop = False
        for node in page["nodes"]:
            day = (node.get("swapExecutedBlockTimestamp") or "")[:10]
            if not day:
                continue
            if day < first_day:
                stop = True
                break
            if day > last_day or node.get("type") != "SWAP":
                continue
            d = days.setdefault(day, {"swaps": 0, "onceVolume": 0.0, "secondLegVolume": 0.0})
            d["swaps"] += 1
            d["onceVolume"] += float(node.get("swapInputValueUsd") or 0)
            d["secondLegVolume"] += float(node.get("intermediateValueUsd") or 0)
        if pages % 25 == 0:
            log("page %d, reached %s" % (pages, day))
        if stop or not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    for d in days.values():
        d["totalVolume"] = d["onceVolume"] + d["secondLegVolume"]
    out = {
        "source": URL,
        "note": "Per day: onceVolume = sum of swap input values in USD (each swap once); "
                "secondLegVolume = sum of intermediate (USDC) leg values for routed swaps.",
        "range": [first_day, last_day],
        "pages": pages,
        "series": {d: days[d] for d in sorted(days)},
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

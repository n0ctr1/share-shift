"""Pull 1Click swap history from the NEAR Intents Explorer API and aggregate it.

    python3 -m pipeline.explorer --from 2026-04-09 --to 2026-11-10

Needs INTENTS_EXPLORER_JWT in .env (free, from partners.near-intents.org).
The API allows one request every five seconds, so a long range takes a while;
progress is saved and an interrupted run continues where it stopped.

Only daily aggregates are written to data/raw/explorer_daily.json. No
address, hash or single transaction is stored.
"""

import argparse
import collections
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "raw", "explorer_daily.json")
PROGRESS = os.path.join(ROOT, "data", "explorer_progress.json")
URL = "https://explorer.near-intents.org/api/v0/transactions"
PAGE = 1000
PAUSE = 5.2
# Swaps below this size are not fetched: they are most of the rows and little
# of the volume. The coverage this leaves out is measured by `calibrate`.
MIN_USD = 1000


def read_key():
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path):
            if line.startswith("INTENTS_EXPLORER_JWT="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return os.environ.get("INTENTS_EXPLORER_JWT")


def call(key, params):
    url = URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key,
                                               "User-Agent": "share-shift/1.0"})
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code in (401, 403):
                raise RuntimeError("the Explorer API rejected the key (HTTP %d)" % err.code)
            print("retry %d after HTTP %d" % (attempt + 1, err.code), flush=True)
            time.sleep(PAUSE * (attempt + 2))
        except (urllib.error.URLError, TimeoutError, ValueError) as err:
            print("retry %d after %s" % (attempt + 1, type(err).__name__), flush=True)
            time.sleep(PAUSE * (attempt + 2))
    raise RuntimeError("the Explorer API did not answer after 8 tries")


def chain_of(asset):
    """Best-effort chain label from a NEAR Intents asset id."""
    body = asset.split(":", 1)[-1]
    if body.endswith(".omft.near"):
        return body.split("-", 1)[0].split(".", 1)[0]
    if body.endswith(".near") or body == "near":
        return "near"
    return "other"


def unix(day, end=False):
    d = datetime.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
    if end:
        d += datetime.timedelta(days=1)
    return int(d.timestamp())


def add(agg, tx):
    usd = float(tx.get("amountInUsd") or 0)
    day = tx["createdAt"][:10]
    ref = tx.get("referral") or "(none)"
    d = agg.setdefault(day, {"channels": {}, "fee_recipients": {}, "routes": {}})
    ch = d["channels"].setdefault(ref, {"swaps": 0, "usd": 0.0, "fee_usd": 0.0})
    ch["swaps"] += 1
    ch["usd"] += usd
    for fee in tx.get("appFees") or []:
        fee_usd = usd * float(fee.get("fee") or 0) / 1e4
        ch["fee_usd"] += fee_usd
        rec = d["fee_recipients"]
        rec[fee["recipient"]] = rec.get(fee["recipient"], 0.0) + fee_usd
    route = chain_of(tx["originAsset"]) + ">" + chain_of(tx["destinationAsset"])
    d["routes"][route] = d["routes"].get(route, 0.0) + usd


def calibrate(key, log=print):
    """One unfiltered page: what share of volume do swaps >= MIN_USD carry?"""
    page = call(key, {"numberOfTransactions": PAGE, "statuses": "SUCCESS"})
    usd = [float(t.get("amountInUsd") or 0) for t in page]
    total = sum(usd)
    out = {
        "sampled_at": page[0]["createdAt"] if page else None,
        "swaps": len(page),
        "share_of_swaps": sum(1 for u in usd if u >= MIN_USD) / len(usd) if usd else None,
        "share_of_volume": sum(u for u in usd if u >= MIN_USD) / total if total else None,
    }
    log("calibration: swaps >= $%d are %.0f%% of rows and %.0f%% of volume in one page"
        % (MIN_USD, 100 * out["share_of_swaps"], 100 * out["share_of_volume"]))
    return out


def run(first_day, last_day, log=print):
    key = read_key()
    if not key:
        raise RuntimeError("INTENTS_EXPLORER_JWT is not set in .env")
    state = None
    if os.path.exists(PROGRESS):
        state = json.load(open(PROGRESS))
        if state.get("range") != [first_day, last_day]:
            state = None
    if state is None:
        state = {"range": [first_day, last_day], "cursor": None, "pages": 0,
                 "agg": {}, "calibration": calibrate(key, log), "done": False}
        time.sleep(PAUSE)
    agg = state["agg"]
    start = unix(first_day)
    while not state["done"]:
        params = {"numberOfTransactions": PAGE, "statuses": "SUCCESS",
                  "minUsdPrice": MIN_USD, "startTimestampUnix": start,
                  "endTimestampUnix": unix(last_day, end=True), "direction": "next"}
        if state["cursor"]:
            params["lastDepositAddress"] = state["cursor"][0]
            if state["cursor"][1]:
                params["lastDepositMemo"] = state["cursor"][1]
        asked_at = time.time()
        page = call(key, params)
        if isinstance(page, dict):
            raise RuntimeError("unexpected answer: %s" % json.dumps(page)[:200])
        for tx in page:
            add(agg, tx)
        state["pages"] += 1
        if len(page) < PAGE:
            state["done"] = True
        else:
            state["cursor"] = [page[-1]["depositAddress"], page[-1].get("depositMemo")]
        if state["pages"] % 5 == 0 or state["done"]:
            with open(PROGRESS, "w") as fh:
                json.dump(state, fh)
            log("page %d, reached %s" % (state["pages"], page[-1]["createdAt"][:16] if page else "end"))
        # The limit is one request per five seconds, counted from the request.
        time.sleep(max(0.0, PAUSE - (time.time() - asked_at)))

    out = {
        "source": URL,
        "filters": {"statuses": "SUCCESS", "minUsdPrice": MIN_USD},
        "range": [first_day, last_day],
        "pages": state["pages"],
        "calibration": state["calibration"],
        "note": "1Click swaps only. Daily aggregates; no addresses or hashes stored.",
        "days": {day: agg[day] for day in sorted(agg)},
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.remove(PROGRESS)
    log("wrote %s (%d days, %d pages)" % (os.path.relpath(OUT, ROOT), len(agg), state["pages"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--from", dest="first", required=True)
    ap.add_argument("--to", dest="last", required=True)
    args = ap.parse_args()
    try:
        run(args.first, args.last)
    except RuntimeError as err:
        sys.exit("error: %s" % err)

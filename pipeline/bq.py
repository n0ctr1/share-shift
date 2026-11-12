"""Query NEAR's public BigQuery dataset for full-day intents.near volume and L1 activity.

    python3 -m pipeline.bq schema                     table metadata and columns (free)
    python3 -m pipeline.bq legs --from 2026-08-13 --to 2026-11-10 [--max-gb 300]
    python3 -m pipeline.bq flows --from 2026-08-13 --to 2026-11-10 [--max-gb 300]
    python3 -m pipeline.bq l1   --from 2025-08-13 --to 2026-11-10 [--max-gb 50]
    python3 -m pipeline.bq prices                     price the assets in the legs file

Dataset: bigquery-public-data.crypto_near_mainnet_us. Every query filters on
block_date (the partition column), is dry-run first to print the bytes it will
scan, and is sent with maximumBytesBilled so it cannot cost more than --max-gb.
The BigQuery sandbox's free tier (1 TB of queries a month, no billing account)
covers all of them (about 270 GB for the committed snapshot).

Auth: an OAuth access token from `gcloud auth print-access-token` (or the
BQ_TOKEN environment variable). It is held in memory only. The project billed
for the queries is BQ_PROJECT or `gcloud config get-value project`; neither is
written to the output.

`flows` writes data/raw/bq_intents_flows.json: per day, sender class, receiver
class (router, solver, other) and asset, the summed raw amounts of DIP-4
transfer entries; see FLOWS_SQL.
`legs` writes data/raw/bq_intents_legs.json: per day, event and asset, the
summed positive and negative raw amounts of every DIP-4 token_diff and
transfer entry emitted by intents.near in successful receipts, and the number
of intents_executed entries. In token_diff the negative amounts are what each
participant gave, user and solver alike, so their sum counts both sides of a
swap. Pricing happens in metrics.py.
`l1` writes data/raw/bq_l1_daily.json: daily transactions and distinct
signers on the NEAR L1. `prices` (no BigQuery) writes data/raw/bq_prices.json:
noon prices for each asset in the legs file, from the 1Click token list
(decimals, CoinGecko id) and DefiLlama's coins API; stablecoins count as $1.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET = "bigquery-public-data.crypto_near_mainnet_us"
API = "https://bigquery.googleapis.com/bigquery/v2/projects/%s"
TABLES = ("https://bigquery.googleapis.com/bigquery/v2/projects/bigquery-public-data/"
          "datasets/crypto_near_mainnet_us/tables/%s")
LOCATION = "us-east1"  # the dataset is a linked Analytics Hub dataset in us-east1

LEGS_SQL = """
WITH ev AS (
  SELECT block_date, SAFE.PARSE_JSON(SUBSTR(l.element, 12)) AS j
  FROM `%s.execution_outcomes`, UNNEST(logs.list) AS l
  WHERE block_date BETWEEN @a AND @b
    AND executor_account_id = 'intents.near'
    AND STARTS_WITH(l.element, 'EVENT_JSON:{"standard":"dip4"')
    AND NOT STARTS_WITH(UPPER(status), 'FAIL')
),
entries AS (
  SELECT block_date, JSON_VALUE(j, '$.event') AS event, d
  FROM ev, UNNEST(JSON_QUERY_ARRAY(j, '$.data')) AS d
  WHERE JSON_VALUE(j, '$.event') IN ('token_diff', 'transfer', 'intents_executed')
),
legs AS (
  SELECT block_date, event, TRIM(k, '"') AS asset,
         SAFE_CAST(JSON_VALUE(IF(event = 'token_diff', d.diff, d.tokens)[TRIM(k, '"')]) AS BIGNUMERIC) AS amt
  FROM entries, UNNEST(JSON_KEYS(IF(event = 'token_diff', d.diff, d.tokens), 1)) AS k
  WHERE event IN ('token_diff', 'transfer')
  UNION ALL
  SELECT block_date, event, '' AS asset, NULL AS amt FROM entries WHERE event = 'intents_executed'
)
SELECT CAST(block_date AS STRING) AS day, event, asset,
       CAST(SUM(IF(amt > 0, amt, 0)) AS STRING) AS pos_raw,
       CAST(SUM(IF(amt < 0, -amt, 0)) AS STRING) AS neg_raw,
       COUNT(*) AS n
FROM legs
GROUP BY day, event, asset
ORDER BY day, event, asset
""" % DATASET

# Transfers between account classes. From September most swaps settle as plain
# `transfer` entries routed through a few 1Click router accounts instead of
# token_diff. A router is any receiver with at least 500 distinct senders that
# day; "solver" is an account whose name starts with "solver". Amounts are
# summed per day, sender class, receiver class and asset; no account is stored.
FLOWS_SQL = """
WITH ev AS (
  SELECT block_date, SAFE.PARSE_JSON(SUBSTR(l.element, 12)) AS j
  FROM `%s.execution_outcomes`, UNNEST(logs.list) AS l
  WHERE block_date BETWEEN @a AND @b
    AND executor_account_id = 'intents.near'
    AND STARTS_WITH(l.element, 'EVENT_JSON:{"standard":"dip4"')
    AND NOT STARTS_WITH(UPPER(status), 'FAIL')
),
d AS (
  SELECT block_date, JSON_VALUE(x, '$.account_id') AS s, JSON_VALUE(x, '$.receiver_id') AS r, x.tokens AS t
  FROM ev, UNNEST(JSON_QUERY_ARRAY(j, '$.data')) AS x
  WHERE JSON_VALUE(j, '$.event') = 'transfer'
),
routers AS (
  SELECT block_date, r AS h FROM d GROUP BY block_date, r HAVING COUNT(DISTINCT s) >= 500
),
c AS (
  SELECT d.block_date,
         IF(hs.h IS NOT NULL, 'router', IF(STARTS_WITH(d.s, 'solver'), 'solver', 'other')) AS sc,
         IF(hr.h IS NOT NULL, 'router', IF(STARTS_WITH(d.r, 'solver'), 'solver', 'other')) AS rc, t
  FROM d
  LEFT JOIN routers hs ON hs.block_date = d.block_date AND hs.h = d.s
  LEFT JOIN routers hr ON hr.block_date = d.block_date AND hr.h = d.r
)
SELECT CAST(block_date AS STRING) AS day, sc, rc, TRIM(k, '"') AS asset,
       CAST(SUM(SAFE_CAST(JSON_VALUE(t[TRIM(k, '"')]) AS BIGNUMERIC)) AS STRING) AS raw,
       COUNT(*) AS n
FROM c, UNNEST(JSON_KEYS(t, 1)) AS k
GROUP BY day, sc, rc, asset
ORDER BY day, sc, rc, asset
""" % DATASET

L1_SQL = """
SELECT CAST(block_date AS STRING) AS day,
       COUNT(*) AS transactions,
       COUNT(DISTINCT signer_account_id) AS signers
FROM `%s.transactions`
WHERE block_date BETWEEN @a AND @b
GROUP BY day
ORDER BY day
""" % DATASET


def token():
    if os.environ.get("BQ_TOKEN"):
        return os.environ["BQ_TOKEN"]
    return subprocess.run(["gcloud", "auth", "print-access-token"], check=True,
                          capture_output=True, text=True).stdout.strip()


def project():
    if os.environ.get("BQ_PROJECT"):
        return os.environ["BQ_PROJECT"]
    return subprocess.run(["gcloud", "config", "get-value", "project"], check=True,
                          capture_output=True, text=True).stdout.strip()


def call(url, body, tok):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + tok,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        raise RuntimeError("BigQuery: HTTP %d %s" % (err.code, err.read()[:600].decode("utf8", "replace")))


def query(sql, params, max_gb):
    tok, proj = token(), project()
    qp = [{"name": k, "parameterType": {"type": "DATE"}, "parameterValue": {"value": v}}
          for k, v in params.items()]
    base = {"query": sql, "useLegacySql": False, "parameterMode": "NAMED",
            "queryParameters": qp, "location": LOCATION}
    dry = call(API % proj + "/queries", dict(base, dryRun=True), tok)
    scan = int(dry.get("totalBytesProcessed", 0))
    print("dry run: %.2f GB to scan (limit %.0f GB)" % (scan / 1e9, max_gb), flush=True)
    if scan > max_gb * 1e9:
        raise RuntimeError("query would scan %.1f GB, over --max-gb" % (scan / 1e9))
    out = call(API % proj + "/queries",
               dict(base, maximumBytesBilled=str(int(max_gb * 1e9)), timeoutMs=600000), tok)
    job = out["jobReference"]
    rows, page = list(out.get("rows") or []), out.get("pageToken")
    while not out.get("jobComplete") or page:
        time.sleep(1 if out.get("jobComplete") else 5)
        url = API % proj + "/queries/%s?location=%s&maxResults=10000%s" % (
            job["jobId"], job.get("location", LOCATION), ("&pageToken=" + page) if page else "")
        out = call(url, None, tok)
        if out.get("jobComplete"):
            rows += out.get("rows") or []
            page = out.get("pageToken")
    names = [f["name"] for f in out["schema"]["fields"]]
    billed = int(out.get("totalBytesBilled") or out.get("totalBytesProcessed") or 0)
    return [dict(zip(names, [c["v"] for c in r["f"]])) for r in rows], scan, billed


def prices():
    from . import intents_events as ie
    legs = json.load(open(os.path.join(ROOT, "data", "raw", "bq_intents_legs.json")))
    days = sorted({r["day"] for r in legs["rows"]})
    seen = {r["asset"] for r in legs["rows"] if r["asset"]}
    tokens = {t["assetId"]: t for t in ie.get(ie.TOKENS) if t["assetId"] in seen}
    start = int(time.mktime(time.strptime(days[0], "%Y-%m-%d"))) - time.timezone + 43200
    ids = sorted({t["coingeckoId"] for t in tokens.values()
                  if t.get("coingeckoId") and t["symbol"] not in ie.STABLE})
    series = {}
    def chart(chunk):
        url = "https://coins.llama.fi/chart/%s?start=%d&span=%d&period=1d" % (
            ",".join("coingecko:" + x for x in chunk), start, len(days))
        try:
            coins = ie.get(url).get("coins", {})
        except urllib.error.HTTPError:
            if len(chunk) == 1:
                return
            for x in chunk:
                chart([x])
            return
        for key, v in coins.items():
            series[key.split(":", 1)[1]] = {time.strftime("%Y-%m-%d", time.gmtime(p["timestamp"])): p["price"]
                                            for p in v["prices"]}
        time.sleep(ie.PAUSE)
    for i in range(0, len(ids), 10):
        chart(ids[i:i + 10])
    table = {}
    for aid, t in sorted(tokens.items()):
        stable = t["symbol"] in ie.STABLE
        daily = {} if stable else series.get(t.get("coingeckoId") or "", {})
        table[aid] = {"symbol": t["symbol"], "decimals": int(t["decimals"]),
                      "stable": stable, "daily": daily}
    write("bq_prices.json", {"source": {"tokens": ie.TOKENS, "prices": "https://coins.llama.fi/chart"},
                             "assets_in_legs": len(seen), "assets_listed": len(table), "prices": table})


def write(name, body):
    path = os.path.join(ROOT, "data", "raw", name)
    with open(path, "w") as fh:
        json.dump(body, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print("wrote %s" % os.path.relpath(path, ROOT))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", choices=["schema", "legs", "flows", "l1", "prices"])
    ap.add_argument("--from", dest="first")
    ap.add_argument("--to", dest="last")
    ap.add_argument("--max-gb", type=float, default=300)
    a = ap.parse_args(argv)
    if a.what == "prices":
        return prices()
    if a.what == "schema":
        # INFORMATION_SCHEMA is not open on this linked dataset; table metadata is.
        tok = token()
        for t in ("execution_outcomes", "transactions"):
            meta = call(TABLES % t, None, tok)
            print("%s: %s rows, partitioned by %s, modified %s" % (
                t, meta.get("numRows"), (meta.get("timePartitioning") or {}).get("field"),
                time.strftime("%Y-%m-%d %H:%M", time.gmtime(int(meta["lastModifiedTime"]) / 1000))))
            for f in meta["schema"]["fields"]:
                print("  %-28s %s" % (f["name"], f["type"]))
        return
    sql = {"legs": LEGS_SQL, "flows": FLOWS_SQL, "l1": L1_SQL}[a.what]
    rows, scan, billed = query(sql, {"a": a.first, "b": a.last}, a.max_gb)
    meta = {"dataset": DATASET, "range": [a.first, a.last], "sql": sql.strip(),
            "bytes_processed": scan, "bytes_billed": billed}
    name = {"legs": "bq_intents_legs.json", "flows": "bq_intents_flows.json", "l1": "bq_l1_daily.json"}[a.what]
    write(name, dict(meta, rows=rows))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (RuntimeError, subprocess.CalledProcessError, FileNotFoundError) as err:
        sys.exit("error: %s" % err)

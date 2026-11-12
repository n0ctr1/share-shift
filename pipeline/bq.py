"""Query NEAR's public BigQuery dataset for full-day intents.near volume and L1 activity.

    python3 -m pipeline.bq schema                     column names and types (free)
    python3 -m pipeline.bq legs --from 2026-08-13 --to 2026-11-10 [--max-gb 300]
    python3 -m pipeline.bq l1   --from 2025-08-13 --to 2026-11-10 [--max-gb 50]

Dataset: bigquery-public-data.crypto_near_mainnet_us. Every query filters on
block_date (the partition column), is dry-run first to print the bytes it will
scan, and is sent with maximumBytesBilled so it cannot cost more than --max-gb.
The BigQuery sandbox's free tier (1 TB of queries a month, no billing account)
covers both runs.

Auth: an OAuth access token from `gcloud auth print-access-token` (or the
BQ_TOKEN environment variable). It is held in memory only. The project billed
for the queries is BQ_PROJECT or `gcloud config get-value project`.

`legs` writes data/raw/bq_intents_legs.json: per day and asset, the summed
positive and negative raw amounts of every DIP-4 token_diff entry emitted by
intents.near in successful receipts. Both sides of a swap emit an entry, so
the positive sum is the two-sided leg sum. Pricing happens in metrics.py.
`l1` writes data/raw/bq_l1_daily.json: daily successful transactions and
distinct signers on the NEAR L1.
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

SCHEMA_SQL = """
SELECT table_name, column_name, data_type
FROM `%s.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name IN ('execution_outcomes', 'transactions', 'receipt_actions')
ORDER BY table_name, ordinal_position
""" % DATASET

LEGS_SQL = """
WITH ev AS (
  SELECT block_date, SAFE.PARSE_JSON(SUBSTR(l, 12)) AS j
  FROM `%s.execution_outcomes`, UNNEST(logs) AS l
  WHERE block_date BETWEEN @a AND @b
    AND executor_account_id = 'intents.near'
    AND STARTS_WITH(l, 'EVENT_JSON:')
    AND STRPOS(l, '"token_diff"') > 0
    AND NOT STARTS_WITH(UPPER(status), 'FAIL')
),
entries AS (
  SELECT block_date, d
  FROM ev, UNNEST(JSON_QUERY_ARRAY(j, '$.data')) AS d
  WHERE JSON_VALUE(j, '$.standard') = 'dip4' AND JSON_VALUE(j, '$.event') = 'token_diff'
),
legs AS (
  SELECT block_date, k AS asset, SAFE_CAST(JSON_VALUE(d['diff'][k]) AS BIGNUMERIC) AS amt
  FROM entries, UNNEST(JSON_KEYS(d['diff'], 1)) AS k
)
SELECT CAST(block_date AS STRING) AS day, asset,
       CAST(SUM(IF(amt > 0, amt, 0)) AS STRING) AS pos_raw,
       CAST(SUM(IF(amt < 0, -amt, 0)) AS STRING) AS neg_raw,
       COUNTIF(amt > 0) AS pos_legs
FROM legs
GROUP BY day, asset
ORDER BY day, asset
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
            "queryParameters": qp, "location": "US"}
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
            job["jobId"], job.get("location", "US"), ("&pageToken=" + page) if page else "")
        out = call(url, None, tok)
        if out.get("jobComplete"):
            rows += out.get("rows") or []
            page = out.get("pageToken")
    names = [f["name"] for f in out["schema"]["fields"]]
    billed = int(out.get("totalBytesBilled") or out.get("totalBytesProcessed") or 0)
    return [dict(zip(names, [c["v"] for c in r["f"]])) for r in rows], scan, billed


def write(name, body):
    path = os.path.join(ROOT, "data", "raw", name)
    with open(path, "w") as fh:
        json.dump(body, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print("wrote %s" % os.path.relpath(path, ROOT))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", choices=["schema", "legs", "l1"])
    ap.add_argument("--from", dest="first")
    ap.add_argument("--to", dest="last")
    ap.add_argument("--max-gb", type=float, default=300)
    a = ap.parse_args(argv)
    if a.what == "schema":
        rows, _, _ = query(SCHEMA_SQL, {}, 1)
        for r in rows:
            print("%-20s %-28s %s" % (r["table_name"], r["column_name"], r["data_type"]))
        return
    sql = LEGS_SQL if a.what == "legs" else L1_SQL
    rows, scan, billed = query(sql, {"a": a.first, "b": a.last}, a.max_gb)
    meta = {"dataset": DATASET, "range": [a.first, a.last], "sql": sql.strip(),
            "bytes_processed": scan, "bytes_billed": billed}
    if a.what == "legs":
        write("bq_intents_legs.json", dict(meta, rows=rows))
    else:
        write("bq_l1_daily.json", dict(meta, rows=rows))


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except (RuntimeError, subprocess.CalledProcessError, FileNotFoundError) as err:
        sys.exit("error: %s" % err)

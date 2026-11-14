# Reproducing Share Shift

Everything a reviewer may want to rerun, beyond the 90-second path in
[README.md](README.md). Steps 1 to 6 need nothing but Python; the optional
steps refresh the primary-source checks, whose outputs are already committed.

## The full path

Needs Python 3.9 or newer. No packages to install. No key needed for steps 1 to 6.

| Step | Do | See |
| --- | --- | --- |
| 1 | `python3 -m unittest discover -s tests` | `Ran 39 tests` and `OK` |
| 2 | `python3 build.py --offline` | Fourteen lines `C1` to `C14`, each `SUPPORTED` or `REFUTED`, then `wrote THESIS.md, METHODS.md, docs/index.html, data/derived/metrics.json` |
| 3 | `git status --short` | Nothing: the offline build reproduces the committed files byte for byte |
| 4 | `python3 build.py` | Refreshes the snapshot from the APIs. The thesis itself is still computed on the fixed window to 2026-11-10 (`THESIS_DATA_END`); the new days only grade the dated predictions. `git diff` shows what the sources revised. Only the offline rebuild (step 2) is byte for byte |
| 5 | Open `docs/index.html` in a browser, or https://n0ctr1.github.io/share-shift/ | A row of six headline numbers; the call with what would change it; fourteen claims with verdicts; six charts (three with the THORChain halt shaded, one with the days on which intents.near's token_diff events match the reported volume) and one split bar; tables for the halt, the counting bases, all eight venues, channels and fee recipients. Hovering a chart shows every series' value for that week or month |
| 6 | Change `WINDOW = 90` to `WINDOW = 30` in `pipeline/config.py`, then run step 2 | Every figure in `THESIS.md` and `METHODS.md` is recomputed for a 30-day window |
| 7 | Optional. Put `INTENTS_EXPLORER_JWT=...` in `.env`, then `python3 -m pipeline.explorer --from 2026-04-09 --to 2026-11-10` | `page 5, reached ...` lines, then `wrote data/raw/channels_report.json; deleted the daily aggregates`. About three hours: the API allows one request per five seconds. An interrupted run resumes. Then run `python3 build.py` so the manifest picks up the new file |
| 8 | Optional. `python3 -m pipeline.onchain --from 2026-08-13 --to 2026-11-10` | Per-wallet progress lines, then `wrote data/raw/onchain_revenue.json`. About 30 minutes on NearBlocks' free tier; no key |
| 8b | Optional. `python3 -m pipeline.onchain --outflows --from 2026-08-13 --to 2026-11-10` | `wrote data/raw/buyback_outflows.json: N outflows`: everything that left the buyback wallet. About 10 minutes; no key |
| 9 | Optional. `python3 -m pipeline.intents_events --day 2026-08-20 --sample 4000` | `93116 transactions on intents.near`, then `both sides ...M (90%: ...)`; about 15 minutes, no key |
| 10 | Optional. `python3 -m pipeline.chainflip --from 2026-08-13 --to 2026-11-10` | `wrote data/raw/legs_chainflip-amm.json`; a few minutes, no key |
| 11 | Optional. `python3 -m pipeline.thorchain_actions --from 2026-08-13 --to 2026-11-10 --points 180` | `double-swap value share ...% (90%: ...)`; about 15 minutes, no key |
| 12 | Optional. `gcloud auth login`, `gcloud config set project <id>`, then `python3 -m pipeline.bq legs --from 2026-08-13 --to 2026-11-10`, `python3 -m pipeline.bq flows --from 2026-08-13 --to 2026-11-10`, `python3 -m pipeline.bq buyback --from 2026-08-13 --to 2026-11-10`, `python3 -m pipeline.bq prices` and `python3 -m pipeline.bq l1 --from 2025-08-13 --to 2026-11-10` | `dry run: 117.34 GB to scan`, then `wrote data/raw/bq_intents_legs.json`; the same for `bq_intents_flows.json` and `bq_buyback_provenance.json` (about 120 GB); `wrote data/raw/bq_prices.json`; `dry run: 30.42 GB to scan`, then `wrote data/raw/bq_l1_daily.json`. A few minutes each; the BigQuery sandbox's free monthly terabyte covers all four, no billing account |

Step 2 uses the snapshot in `data/raw/`, whose hashes are checked against
`data/raw/manifest.json`. Edit any raw file and the build stops with
`does not match the hash in manifest.json`.

Steps 7 to 12 are not needed to reproduce the thesis: their outputs are
committed. The Explorer key is free from https://partners.near-intents.org.

## Checking the TEE run

The headline share was recomputed inside an Intel TDX enclave by OutLayer, from
a NEAR mainnet transaction. `tee/share-check` is the program; its input is
`tee/share-check/input.json`; the run is recorded in `data/raw/tee_run.json`.

The WASM that ran is committed as `tee/share-check/dist/share-check.wasm`, so
checking the run needs no Rust toolchain.

| Step | Do | See |
| --- | --- | --- |
| 1 | `sha256sum tee/share-check/dist/share-check.wasm` | `7634f3997a76a5ff6c930374c81d33baaa3f06cbece6e8fae9ab0217e4fdaf0d`, the hash in `data/raw/tee_run.json` |
| 2 | `python3 -m pipeline.tee_verify` | five `PASS` lines: the chain ran the committed WASM, on our input, it completed, the result was delivered by a key scoped to `outlayer.near` on `worker.outlayer.near`, and it matches the recorded run. Nothing is written |
| 3 | Open the request on https://nearblocks.io/txns/Aw6Vz41optzWmAEDvmzq7wk3YHypfhFt3pssrxPnDjk7 | the `execution_completed` event and the returned JSON |
| 4 | `pip install cryptography`, then `python3 -m pipeline.tdx` | thirteen `PASS` lines: the worker key was added by `register_worker_key` transaction `DXvVB74UDHSUL11KFyP59bJF5jJvz3KKKAYW1ngG4stP`; the TDX quote in it carries SHA-256 of that key, is signed by its attestation key, which is bound to Intel's Quoting Enclave, whose report is signed by a PCK certificate chaining to Intel's SGX Root CA (pinned by public-key hash); nothing is revoked, the QE and TDX module match Intel's signed identities, the TCB is `UpToDate` against Intel's current collateral, and the five measurements were on OutLayer's allowlist at that block. It also prints what OutLayer's contract had stored: June collateral for another FMSPC, past its next update |
| 5 | Optional. `sh tee/share-check/rebuild.sh` | `IDENTICAL`: the source rebuilds to the same bytes. Needs rustup (the toolchain is pinned to 1.99.1 in `rust-toolchain.toml`) and a host C linker |

The same WASM grades prediction P4 a second time, on its own two days. It ran
as transaction `78h8jjw14hrGRzwaffxfvaePMo4cA9AbWzKYZNa7q82n` (2026-11-13 18:37
UTC, after 2026-11-12 had ended and DefiLlama had all four venues for it) and
returned a share of 44.52%: P4 is MET, and every venue's volume matches the
build's to $0.1M. Its worker key has its own TDX quote, which `python3 -m
pipeline.tdx` verifies too (13 of 13 checks). The run was:

```
outlayer run --wasm "https://main.fastfs.io/noctrl.near/outlayer.near/7634f3997a76a5ff6c930374c81d33baaa3f06cbece6e8fae9ab0217e4fdaf0d.wasm" --hash 7634f3997a76a5ff6c930374c81d33baaa3f06cbece6e8fae9ab0217e4fdaf0d --compute-limit 2000000000 --input tee/share-check/input-p4.json --verbose
```

then `python3 -m pipeline.tee_verify --tx <hash> --sender <account> --record --run p4`
writes `data/raw/tee_run_p4.json`, and `python3 build.py` grades P4 from it as
well. The build counts that run only if it covers 2026-11-11 and 2026-11-12, ran
after the second day ended and passes the chain checks; it then shows whether
the enclave's per-venue volumes and verdict match its own. `python3 -m
pipeline.tee_verify` checks every recorded run.

A first P4 request (`BzF2oeQkfo9Qdpk8nu5ZLUNHVn2wT3vb17tWaDkNyHXr`, 2026-11-12
14:26 UTC) passes the chain checks but ran before 2026-11-12 had ended: DefiLlama
had no Intents point for that day yet and only part of Chainflip's. It returned
a share of 30.41% on incomplete days and is not used.

An earlier request from the same account (`9Nb8MpaWCCBwHxc6DHFqJBTi919eupKnagGSVHH5MtqU`)
ran the same code with an empty input, because the CLI read the JSON argument as
a project name; it returned zeros and is not used.

What this proves and what it does not: the published program, unmodified,
produced the published numbers from what DefiLlama and Midgard served at that
moment. It does not prove those APIs are right; the primary-source checks above
do that. OutLayer's register contract adds a worker key only after checking an
Intel TDX quote against an allowlist of measurements, and only such a key can
deliver results. This repository does not rely on that: `pipeline/tdx.py`
re-verifies the quote itself, from the registration transaction to Intel's
root CA, and finds the contract's own collateral out of date (step 4). What it
cannot show: that OutLayer's allowlisted image does only what its documentation
says, since those measurements are OutLayer's. The TEE run is a
reproducibility check, not evidence for the thesis.

## Checking the predictions were not edited

| Step | Do | See |
| --- | --- | --- |
| 1 | `sha256sum predictions/predictions.json` | the hash in `predictions/predictions.json.sha256` |
| 2 | `git show predictions-v1:predictions/predictions.json \| sha256sum` | the same hash, from the tagged commit |
| 3 | `python3 -m pipeline.ots` | `bitcoin block 975496 ... merkle root matches` (three lines, one per calendar), then `predictions.json existed by Bitcoin block 975496 (unix time 1794442654)`, 2026-11-12 00:17 UTC. Standard library only; block headers come from Blockstream's public API. The official client gives the same result: `pip install opentimestamps-client`, then `ots verify predictions/predictions.json.ots` |
| 4 | `python3 -m pipeline.seal --check` | `sealed predictions match config` |
| 5 | `python3 -m pipeline.anchor --account noctrl.near --verify` | `anchored on NEAR: noctrl.near/share_shift/predictions_sha256 = 5415cf8f...` read from `social.near` over public RPC; written by transaction `F75hY9zdcipcUSrgXPjLx7mAw2Rzer4vAgA9VLo8MmhE` |
| 6 | `python3 -m pipeline.ots --file predictions/predictions-v2.json` and `python3 -m pipeline.seal --check` | `predictions-v2.json existed by Bitcoin block 975532 (unix time 1794471987)`, 2026-11-12 08:26 UTC: the second seal (claim thresholds and P4, P5). The first of P4 and P5's two days, 11 November, had ended by then; the second had not. The second seal is not written on NEAR |
| 7 | `python3 -m pipeline.ots --file predictions/predictions-v3.json` | the third seal (the call's rule, the SHA-256 of both BigQuery queries, P6 to P8 on 2026-11-13 to 2026-12-10), sealed 2026-11-12: `predictions-v3.json existed by Bitcoin block 975582 (unix time 1794510147)`, 2026-11-12 19:02 UTC, before P6 to P8's window opened on 13 November |
| 8 | `python3 -m pipeline.anchor --account noctrl.near --seal v3 --verify` | `anchored on NEAR: noctrl.near/share_shift/predictions_v3_sha256 = 22fb6be0...` read from `social.near` over public RPC; written by transaction `45k7GsThxpBiEv9pZxX8nmquWw8jyxjvMgnGoqY5YWB2` (block 224,246,371, 2026-11-12 17:51 UTC), before the window of P6 to P8 starts |

## How a number gets into the thesis

```
api.llama.fi, api.coingecko.com, THORChain Midgard, Intents Explorer
        |  pipeline/fetch.py, pipeline/explorer.py
        v
data/raw/*.json + manifest.json (sha256)
        |  pipeline/metrics.py    -> data/derived/metrics.json
        |  pipeline/narrative.py     (every sentence with a figure in it)
        v
THESIS.md, METHODS.md, docs/index.html
```

No figure in `THESIS.md`, `METHODS.md` or the dashboard is typed by hand. To check one,
search for it in `data/derived/metrics.json`, then read the function named
under the chart.

| File | Role |
| --- | --- |
| `pipeline/config.py` | Peer sets, window length, claim thresholds, dated predictions, cited events |
| `pipeline/fetch.py` | Downloads the public series and writes the hashed snapshot |
| `pipeline/explorer.py` | Downloads 1Click swaps, writes the channel report and deletes what it downloaded |
| `pipeline/seal.py`, `pipeline/ots.py`, `pipeline/anchor.py` | Seal the predictions; upgrade and verify the OpenTimestamps proof; anchor and check the hash on NEAR |
| `pipeline/onchain.py`, `pipeline/intents_events.py`, `pipeline/bq.py`, `pipeline/chainflip.py`, `pipeline/thorchain_actions.py` | Primary-source checks: revenue wallets, intents.near events (sampled, and every day from BigQuery), Chainflip legs, THORChain swap actions |
| `pipeline/tee_verify.py`, `pipeline/tdx.py`, `tee/share-check/` | The program that ran in the TEE, the on-chain check of that run, and the check of the TDX quote behind it |
| `pipeline/metrics.py` | All arithmetic: shares, shift-share split, halt experiment, placebo, channels, verdicts |
| `pipeline/narrative.py` | Turns metrics into the sentences, `THESIS.md` and `METHODS.md` |
| `pipeline/template.html` | Dashboard layout and chart code (no libraries) |
| `tests/test_metrics.py` | Checks the arithmetic on hand-made inputs |

## Data sources

| Series | Endpoint | Key needed |
| --- | --- | --- |
| Daily swap volume, four swap venues | `api.llama.fi/summary/dexs/{venue}` | no |
| Daily volume, four bridges | `api.llama.fi/summary/bridges/{venue}` | no |
| Daily gross fees per venue | `api.llama.fi/summary/fees/{venue}?dataType=dailyFees` | no |
| Daily revenue per venue | `api.llama.fi/summary/fees/{venue}?dataType=dailyRevenue` | no |
| THORChain volume, cross-check and leg breakdown | THORChain Midgard `/v2/history/swaps` | no |
| Maya leg breakdown | Maya Midgard `/v2/history/swaps` | no |
| NEAR total supply at the window's edges | NEAR archival RPC block headers (`total_supply`) | no |
| Daily L1 transactions and active accounts | `api.nearblocks.io/v1/charts`; cross-checked in BigQuery `crypto_near_mainnet_us.transactions` | no; BigQuery needs a Google account |
| Every intents.near DIP-4 event, every day | BigQuery `bigquery-public-data.crypto_near_mainnet_us.execution_outcomes` (dataset in `us-east1`) | a Google account; free sandbox tier |
| Transfers into NEAR's three revenue wallets | `api.nearblocks.io/v1/account/{wallet}/txns`, `/ft-txns` | no |
| intents.near transactions and event logs | FastNear `tx.main.fastnear.com/v0/account`, `/v0/transactions` | no |
| Token decimals and CoinGecko ids; historical prices | `1click.chaindefuser.com/v0/tokens`; `coins.llama.fi/prices/historical`, `coins.llama.fi/chart` | no |
| Chainflip swaps with routed legs | `explorer-service-processor.chainflip.io/graphql` | no |
| TEE run: request, result, worker key | NEAR archival RPC (`EXPERIMENTAL_tx_status`, `view_access_key`), FastNear transactions API | no |
| TDX quote, allowlist, stored collateral | `register_worker_key` arguments; `worker.outlayer.near` views `get_approved_measurements`, `get_collateral` at that block | no |
| Intel collateral now | `api.trustedservices.intel.com/tdx/certification/v4` (`/tcb`, `/qe/identity`), PCK CRL, root CA CRL | no |
| Token market caps | `api.coingecko.com/api/v3/simple/price` | no |
| 1Click swaps by channel and fee recipient | `explorer.near-intents.org/api/v0/transactions` | yes, free |

If CoinGecko or Midgard does not answer, the build still completes and the
affected sentence says the value is unavailable.

`data/raw/channels_report.json` holds window totals only: the top channels
with their volume, share and fee rate, the top fee-recipient accounts, and the
change in each channel's daily volume during the THORChain halt. It contains no
user address, transaction hash, single swap or daily series. The API's terms
(1ClickSwap API, section 4.1(e)) do not allow storing API data for more than
24 hours, so `pipeline/explorer.py` keeps its daily aggregates in the ignored
`data/private/` folder and deletes them as soon as the report is written.

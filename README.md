# Share Shift

An investment thesis on NEAR that tests NEAR Intents against its competitors,
with every number rebuilt from public data by one command.

[![Reproducible](https://github.com/n0ctr1/share-shift/actions/workflows/reproduce.yml/badge.svg)](https://github.com/n0ctr1/share-shift/actions/workflows/reproduce.yml)

Built at NEAR HACKATHON, track `thesis` (Investment Thesis). The badge is a GitHub Actions run on every push: tests,
the seal check, `python build.py --offline`, then `git diff --exit-code`, so it
is green only if the committed files are exactly what the snapshot rebuilds.

[![The dashboard: share by week with the lead and kill lines, and the call](docs/screenshot.jpg)](https://n0ctr1.github.io/share-shift/)

- Live dashboard: https://n0ctr1.github.io/share-shift/ (Easy shows the short version;
  Pro adds sources, data tables and the full evidence)
- The thesis, about two pages: [`THESIS.md`](THESIS.md)
- Method, every check and every limit: [`METHODS.md`](METHODS.md)

**The call: WATCH, not buy.** NEAR Intents is the largest venue that swaps
native assets across chains (58% of four-venue volume over 90 days; with four
large bridges added it is third, 18%, so claim C11 is refuted), but its
lead is slipping in the latest weeks and the NEAR token captures too little of
it: buybacks offset 13% of newly issued NEAR. The call turns to ACCUMULATE when
buybacks cover half of new NEAR and the 30-day share is back above 50%, and to
AVOID if the 90-day share falls below 40% or the share of fees reaching NEAR
stops rising. The rule is `CALL` in `pipeline/config.py`; the build computes the
call from the data (`metrics.investment_call()`), so a re-run can change it.
Figures here are as of the committed snapshot: the thesis is computed on data
to 2026-11-10 (`THESIS_DATA_END` in `pipeline/config.py`, the data it was
sealed against), and later days in the snapshot only grade the dated
predictions. P4 and P5, due 2026-11-12, were both MET. The rule,
the on-chain counting method and three predictions on 2026-11-13 to 2026-12-10
are sealed (third seal), so none of them can be tuned after that window starts.

Why the market is four swap venues: they, like Intents, turn one native asset
into another across chains, while bridges mostly move the same asset; when
THORChain halted, only swap venues behaved as its substitutes
(`metrics.market_test()`).

What a careful reader should not have to take on trust, and does not:

- **Intents volume** is rebuilt from every log line `intents.near` wrote, for
  every day of the window (NEAR's public BigQuery dataset), not only from
  DefiLlama. The headline holds on the chain's own numbers: 60%, or 55% on the
  strictest reading (`metrics.shares_onchain()`).
- **The market definition** is tested: when THORChain halted, swap venues
  behaved as its substitutes and no bridge did (`metrics.market_test()`).
- **The TEE run** is checked down to Intel's root CA: the TDX quote behind the
  OutLayer worker key is verified here, with Intel's current collateral
  (`pipeline/tdx.py`).
- **Explorer API data** is not kept beyond the report built from it (the API
  terms forbid storing it for more than 24 hours).
- **Confidential Intents** are measured, not ignored: in November 89% of the
  on-chain Intents volume (96% in the last week) shows only as money entering
  and leaving 1Click routers, with no public fill. The public chain verifies the
  value that crosses `intents.near`, not the fills; swaps that stay inside the
  private shard are counted nowhere, which can only understate the share. See
  "Confidential Intents" in `THESIS.md` and `METHODS.md`.
- **A forward view** in three scenarios (`SCENARIOS` in `pipeline/config.py`,
  `metrics.scenarios()`): buybacks would cover 4%, 13% and 36% of new NEAR over
  the next twelve months in the bear, base and bull cases. Even the bull case
  stays under half.

## What it is

- `THESIS.md`: the short thesis. The call and what would change it, the 14
  claims with verdicts, the case each way, why the numbers can be trusted,
  the predictions. Each point links to its section in `METHODS.md`.
- `METHODS.md`: everything behind it: the stress test, channels, the token,
  how volume is counted, all eight venues, window sensitivity, the seals, the
  checks and every limit.
- `docs/index.html`: a static dashboard. Each chart shows the query behind it
  and one sentence on what it shows.
- `build.py`: one command that fetches the data and regenerates both files.

## Why "Share Shift"

The share did shift: NEAR Intents' share of native cross-chain swap volume rose
from 40% to 58% in a year (C1). The name does not claim that the shift drove
Intents' growth. That is tested separately and fails: C2 finds 56% of the
volume gain came from a bigger market and 44% from the share gained.

## The problem

Most write-ups of NEAR Intents look at Intents alone: its volume, its fees,
its effect on the token. A position is only durable relative to competitors.
This project puts Intents next to the three other venues that swap native
assets across chains (THORChain, Chainflip, Maya Protocol), and next to four
large bridges (Relay, Across, Stargate, deBridge), and asks what an investor
would ask of any business:

1. Does it lead the market?
2. Did it win share, or did the market just grow?
3. Is it winning on price?
4. Do the fees reach the token?
5. What happened when the position was tested?
6. Who brings the customers, and who keeps the fees?

The fifth has a real answer. In May 2026 THORChain, then the second-largest
venue, stopped trading for 37 days after an exploit. The build finds that gap
in the data by itself and measures where the flow went and whether it came
back (`metrics.halt_experiment`). It also asks whether that growth was unusual
for Intents, by ranking it against every other stretch of the same length
(`metrics.placebo`), and reports the answer whichever way it falls.

The sixth uses the NEAR Intents Explorer API: 1Click swaps grouped by
distribution channel and by the account that receives the app fee
(`metrics.channel_report`). Only the window totals of that report are committed
(`data/raw/channels_report.json`); the daily aggregates it is built from are
deleted once the report is written.

Fourteen claims are tested against fixed thresholds. The current result is in
`THESIS.md`; it includes the claims that fail. The tests behind each are in
`METHODS.md`.

## How NEAR fits in

NEAR Intents is the subject. The analysis measures its share of cross-chain
swap volume, its take rate against rivals, the fraction of its gross fees that
reaches NEAR's revenue wallets (the flow behind the on-chain buyback), and,
from NEAR Intents' own Explorer API, which front ends distribute it.

## Try it

Needs Python 3.9 or newer. No packages to install. No key needed for steps 1 to 6.

| Step | Do | See |
| --- | --- | --- |
| 1 | `python3 -m unittest discover -s tests` | `Ran 38 tests` and `OK` |
| 2 | `python3 build.py --offline` | Fourteen lines `C1` to `C14`, each `SUPPORTED` or `REFUTED`, then `wrote THESIS.md, METHODS.md, docs/index.html, data/derived/metrics.json` |
| 3 | `git status --short` | Nothing: the offline build reproduces the committed files byte for byte |
| 4 | `python3 build.py` | Refreshes the snapshot from the APIs. The thesis itself is still computed on the fixed window to 2026-11-10 (`THESIS_DATA_END`); the new days only grade the dated predictions. `git diff` shows what the sources revised. Only the offline rebuild (step 2) is byte for byte |
| 5 | Open `docs/index.html` in a browser, or https://n0ctr1.github.io/share-shift/ | A row of six headline numbers; the call with what would change it; fourteen claims with verdicts; six charts (three with the THORChain halt shaded, one with the days on which intents.near's token_diff events match the reported volume) and one split bar; tables for the halt, the counting bases, all eight venues, channels and fee recipients. Hovering a chart shows every series' value for that week or month |
| 6 | Change `WINDOW = 90` to `WINDOW = 30` in `pipeline/config.py`, then run step 2 | Every figure in `THESIS.md` and `METHODS.md` is recomputed for a 30-day window |
| 7 | Optional. Put `INTENTS_EXPLORER_JWT=...` in `.env`, then `python3 -m pipeline.explorer --from 2026-04-09 --to 2026-11-10` | `page 5, reached ...` lines, then `wrote data/raw/channels_report.json; deleted the daily aggregates`. About three hours: the API allows one request per five seconds. An interrupted run resumes. Then run `python3 build.py` so the manifest picks up the new file |
| 8 | Optional. `python3 -m pipeline.onchain --from 2026-08-13 --to 2026-11-10` | Per-wallet progress lines, then `wrote data/raw/onchain_revenue.json`. About 30 minutes on NearBlocks' free tier; no key |
| 9 | Optional. `python3 -m pipeline.intents_events --day 2026-08-20 --sample 4000` | `93116 transactions on intents.near`, then `both sides ...M (90%: ...)`; about 15 minutes, no key |
| 10 | Optional. `python3 -m pipeline.chainflip --from 2026-08-13 --to 2026-11-10` | `wrote data/raw/legs_chainflip-amm.json`; a few minutes, no key |
| 11 | Optional. `python3 -m pipeline.thorchain_actions --from 2026-08-13 --to 2026-11-10 --points 180` | `double-swap value share ...% (90%: ...)`; about 15 minutes, no key |
| 12 | Optional. `gcloud auth login`, `gcloud config set project <id>`, then `python3 -m pipeline.bq legs --from 2026-08-13 --to 2026-11-10`, `python3 -m pipeline.bq flows --from 2026-08-13 --to 2026-11-10`, `python3 -m pipeline.bq prices` and `python3 -m pipeline.bq l1 --from 2025-08-13 --to 2026-11-10` | `dry run: 117.34 GB to scan`, then `wrote data/raw/bq_intents_legs.json`; the same for `bq_intents_flows.json`; `wrote data/raw/bq_prices.json`; `dry run: 30.42 GB to scan`, then `wrote data/raw/bq_l1_daily.json`. A few minutes each; the BigQuery sandbox's free monthly terabyte covers all four, no billing account |

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
| 7 | `python3 -m pipeline.ots --upgrade --file predictions/predictions-v3.json`, then `python3 -m pipeline.ots --file predictions/predictions-v3.json` | the third seal (the call's rule, the SHA-256 of both BigQuery queries, P6 to P8 on 2026-11-13 to 2026-12-10), sealed 2026-11-12; its Bitcoin block appears a few hours after sealing |
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

## Limits

- Which venues make up "the market" is tested once, with the THORChain halt
  (`metrics.market_test()`): Intents and Maya gained while it was down and gave
  part back when it returned; no bridge did both, and Relay, which grew most,
  kept growing after THORChain came back. One event is thin evidence, so both
  a narrow set (four swap venues) and a wide set (plus four bridges) are
  reported, and the answer differs: first in one, third in the other.
- The Explorer API covers 1Click swaps, about 30% of Intents volume in the
  window, and only swaps of $1,000 or more were fetched (about 95% of 1Click
  volume in a calibration sample).
- One 37-day halt is one event, not a law. A two-day outage in the data shows
  no effect.
- THORChain's volume and NEAR's captured revenue were checked against primary
  sources (Midgard; transfers into the revenue wallets). Intents volume was
  rebuilt from `intents.near` events on every day of the window (NEAR's public
  BigQuery dataset) and on six sampled days. Through August token_diff events
  match the reported figure; from 1 September swaps settle as transfers through
  1Click routers, and counting those (both directions, router-to-solver hedging
  left out) matches it again (median 1.04 of reported). That router rule was
  found by looking at the data; it is sealed now (third seal) and P8 tests it
  on 2026-11-13 to 2026-12-10.
- Three outside facts are cited rather than computed, all in
  `pipeline/config.py`: what the THORChain halt was, a later short suspension,
  and which distribution channels also route to rival venues (each with its
  source, in `CHANNEL_NOTES`).
- Claim thresholds were chosen after a first look at the data and are not
  pre-registered. They are sealed as they stand (second seal, 2026-11-12), so a
  later change is visible, and two short predictions (P4, P5) resolve on the two
  days after the data was seen, before the hackathon deadline; both were MET
  (44.5% share against 40%, 17.0 bps against 12 bps). The seal's
  Bitcoin timestamp came after the first of those days had ended, so only the
  second is a day that had not yet happened. The call's rule and P6 to P8 are
  in a third seal made before their window starts.

## Disclosure

- All code in this repository was written during the hackathon window. There
  is no earlier baseline.
- AI coding tools were used to speed up writing the code. The author directed
  the work and is responsible for every decision and result in this repository.
- No third-party libraries in the build: Python standard library, and plain
  HTML, CSS and JavaScript in the dashboard. The optional TDX quote check
  (`pipeline/tdx.py`) needs the `cryptography` package for ECDSA and X.509.

## License

MIT, see `LICENSE`.

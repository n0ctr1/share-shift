# Share Shift

An investment thesis on NEAR that tests NEAR Intents against its competitors,
with every number rebuilt from public data by one command.

Built at NEAR HACKATHON, track `thesis` (Investment Thesis).

- Live dashboard: https://n0ctr1.github.io/share-shift/
- Full argument: [`THESIS.md`](THESIS.md)

## What it is

- `THESIS.md`: the claim, the evidence for it, the evidence against it, and
  what would change the conclusion.
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
(`metrics.channel_report`).

Fourteen claims are tested against fixed thresholds. The current result is in
`THESIS.md`; it includes the claims that fail.

## How NEAR fits in

NEAR Intents is the subject. The analysis measures its share of cross-chain
swap volume, its take rate against rivals, the fraction of its gross fees that
reaches NEAR's revenue wallets (the flow behind the on-chain buyback), and,
from NEAR Intents' own Explorer API, which front ends distribute it.

## Try it

Needs Python 3.9 or newer. No packages to install. No key needed for steps 1 to 6.

| Step | Do | See |
| --- | --- | --- |
| 1 | `python3 -m unittest discover -s tests` | `Ran 27 tests` and `OK` |
| 2 | `python3 build.py --offline` | Fourteen lines `C1` to `C14`, each `SUPPORTED` or `REFUTED`, then `wrote THESIS.md, docs/index.html, data/derived/metrics.json` |
| 3 | `git status --short` | Nothing: the offline build reproduces the committed files byte for byte |
| 4 | `python3 build.py` | The same fourteen lines computed on today's data; `git diff THESIS.md` shows which numbers moved |
| 5 | Open `docs/index.html` in a browser, or https://n0ctr1.github.io/share-shift/ | A row of six headline numbers; fourteen claims with verdicts; five charts (three with the THORChain halt shaded) and one split bar; tables for the halt, the counting bases, all eight venues, channels and fee recipients. Hovering a chart shows every series' value for that week or month |
| 6 | Change `WINDOW = 90` to `WINDOW = 30` in `pipeline/config.py`, then run step 2 | Every figure in `THESIS.md` is recomputed for a 30-day window |
| 7 | Optional. Put `INTENTS_EXPLORER_JWT=...` in `.env`, then `python3 -m pipeline.explorer --from 2026-04-09 --to 2026-11-10` | `page 5, reached ...` lines, then `wrote data/raw/explorer_daily.json`. About three hours: the API allows one request per five seconds. An interrupted run resumes. Then run `python3 build.py` so the manifest picks up the new file |

Step 2 uses the snapshot in `data/raw/`, whose hashes are checked against
`data/raw/manifest.json`. Edit any raw file and the build stops with
`does not match the hash in manifest.json`.

| 8 | Optional. `python3 -m pipeline.onchain --from 2026-08-13 --to 2026-11-10` | Per-wallet progress lines, then `wrote data/raw/onchain_revenue.json`. About 30 minutes on NearBlocks' free tier; no key |

| 9 | Optional. `python3 -m pipeline.intents_events --day 2026-08-20 --sample 4000` | `93116 transactions on intents.near`, then `both sides ...M (90%: ...)`; about 15 minutes, no key |
| 10 | Optional. `python3 -m pipeline.chainflip --from 2026-08-13 --to 2026-11-10` | `wrote data/raw/legs_chainflip-amm.json`; a few minutes, no key |
| 11 | Optional. `python3 -m pipeline.thorchain_actions --from 2026-08-13 --to 2026-11-10 --points 180` | `double-swap value share ...% (90%: ...)`; about 15 minutes, no key |

Steps 7 to 11 are not needed to reproduce the thesis: the Explorer aggregates are
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
| 4 | Optional. `sh tee/share-check/rebuild.sh` | `IDENTICAL`: the source rebuilds to the same bytes. Needs rustup (the toolchain is pinned to 1.99.1 in `rust-toolchain.toml`) and a host C linker |

An earlier request from the same account (`9Nb8MpaWCCBwHxc6DHFqJBTi919eupKnagGSVHH5MtqU`)
ran the same code with an empty input, because the CLI read the JSON argument as
a project name; it returned zeros and is not used.

What this proves and what it does not: the published program, unmodified,
produced the published numbers from what DefiLlama and Midgard served at that
moment. It does not prove those APIs are right; the primary-source checks above
do that. OutLayer's register contract adds a worker key only after checking an
Intel TDX quote against an allowlist of measurements, and only such a key can
deliver results; this repository checks the key on chain but does not
re-verify the TDX quote itself. The TEE run is a reproducibility check, not
evidence for the thesis.

## Checking the predictions were not edited

| Step | Do | See |
| --- | --- | --- |
| 1 | `sha256sum predictions/predictions.json` | the hash in `predictions/predictions.json.sha256` |
| 2 | `git show predictions-v1:predictions/predictions.json \| sha256sum` | the same hash, from the tagged commit |
| 3 | `python3 -m pipeline.ots` | `bitcoin block 975496 ... merkle root matches` (three lines, one per calendar), then `predictions.json existed by Bitcoin block 975496 (unix time 1794442654)`, 2026-11-12 00:17 UTC. Standard library only; block headers come from Blockstream's public API. The official client gives the same result: `pip install opentimestamps-client`, then `ots verify predictions/predictions.json.ots` |
| 4 | `python3 -m pipeline.seal --check` | `sealed predictions match config` |
| 6 | `python3 -m pipeline.ots --file predictions/predictions-v2.json` and `python3 -m pipeline.seal --check` | the second seal (claim thresholds and P4, P5, sealed 2026-11-12); its Bitcoin attestation completes a few hours after sealing |
| 5 | `python3 -m pipeline.anchor --account noctrl.near --verify` | `anchored on NEAR: noctrl.near/share_shift/predictions_sha256 = 5415cf8f...` read from `social.near` over public RPC; written by transaction `F75hY9zdcipcUSrgXPjLx7mAw2Rzer4vAgA9VLo8MmhE` |

## How a number gets into the thesis

```
api.llama.fi, api.coingecko.com, THORChain Midgard, Intents Explorer
        |  pipeline/fetch.py, pipeline/explorer.py
        v
data/raw/*.json + manifest.json (sha256)
        |  pipeline/metrics.py    -> data/derived/metrics.json
        |  pipeline/narrative.py     (every sentence with a figure in it)
        v
THESIS.md, docs/index.html
```

No figure in `THESIS.md` or the dashboard is typed by hand. To check one,
search for it in `data/derived/metrics.json`, then read the function named
under the chart.

| File | Role |
| --- | --- |
| `pipeline/config.py` | Peer sets, window length, claim thresholds, dated predictions, cited events |
| `pipeline/fetch.py` | Downloads the public series and writes the hashed snapshot |
| `pipeline/explorer.py` | Downloads 1Click swaps and keeps only daily aggregates |
| `pipeline/seal.py`, `pipeline/ots.py`, `pipeline/anchor.py` | Seal the predictions; upgrade and verify the OpenTimestamps proof; anchor and check the hash on NEAR |
| `pipeline/onchain.py`, `pipeline/intents_events.py`, `pipeline/chainflip.py`, `pipeline/thorchain_actions.py` | Primary-source checks: revenue wallets, intents.near events, Chainflip legs, THORChain swap actions |
| `pipeline/tee_verify.py`, `tee/share-check/` | The program that ran in the TEE, and the on-chain check of that run |
| `pipeline/metrics.py` | All arithmetic: shares, shift-share split, halt experiment, placebo, channels, verdicts |
| `pipeline/narrative.py` | Turns metrics into the sentences and into `THESIS.md` |
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
| Daily L1 transactions and active accounts | `api.nearblocks.io/v1/charts` | no |
| Transfers into NEAR's three revenue wallets | `api.nearblocks.io/v1/account/{wallet}/txns`, `/ft-txns` | no |
| intents.near transactions and event logs | FastNear `tx.main.fastnear.com/v0/account`, `/v0/transactions` | no |
| Token decimals and CoinGecko ids; historical prices | `1click.chaindefuser.com/v0/tokens`; `coins.llama.fi/prices/historical` | no |
| Chainflip swaps with routed legs | `explorer-service-processor.chainflip.io/graphql` | no |
| TEE run: request, result, worker key | NEAR archival RPC (`EXPERIMENTAL_tx_status`, `view_access_key`), FastNear transactions API | no |
| Token market caps | `api.coingecko.com/api/v3/simple/price` | no |
| 1Click swaps by channel and fee recipient | `explorer.near-intents.org/api/v0/transactions` | yes, free |

If CoinGecko or Midgard does not answer, the build still completes and the
affected sentence says the value is unavailable.

`data/raw/explorer_daily.json` holds sums per day, per channel and per fee
recipient account. It contains no user address, transaction hash or single
swap.

## Limits

- Which venues make up "the market" is a judgement. Both a narrow set (four
  swap venues) and a wide set (plus four bridges) are reported, and the answer
  differs: first in one, third in the other.
- The Explorer API covers 1Click swaps, about 30% of Intents volume in the
  window, and only swaps of $1,000 or more were fetched (about 95% of 1Click
  volume in a calibration sample).
- One 37-day halt is one event, not a law. A two-day outage in the data shows
  no effect.
- THORChain's volume and NEAR's captured revenue were checked against primary
  sources (Midgard; transfers into the revenue wallets), and Intents volume was
  rebuilt from `intents.near` events on two sampled days before confidential
  intents launched. Two days are a sample, not a series; the 90% intervals are
  wide (about +-30%), wide enough only to tell one-sided from two-sided.
- Three outside facts are cited rather than computed, all in
  `pipeline/config.py`: what the THORChain halt was, a later short suspension,
  and which distribution channels also route to rival venues (each with its
  source, in `CHANNEL_NOTES`).
- Claim thresholds were chosen after a first look at the data and are not
  pre-registered. They are sealed as they stand (second seal, 2026-11-12), so a
  later change is visible, and two short predictions (P4, P5) resolve on days
  after the data was seen, before the hackathon deadline.

## Disclosure

- All code in this repository was written during the hackathon window. There
  is no earlier baseline.
- AI coding tools were used to speed up writing the code. The author directed
  the work and is responsible for every decision and result in this repository.
- No third-party libraries: Python standard library, and plain HTML, CSS and
  JavaScript in the dashboard.

## License

MIT, see `LICENSE`.

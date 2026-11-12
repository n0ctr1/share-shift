# Share Shift

An investment thesis on NEAR that tests NEAR Intents against its competitors,
with every number rebuilt from public data by one command.

Built at NEAR HACKATHON, track `thesis` (Investment Thesis).

## What it is

- `THESIS.md`: the claim, the evidence for it, the evidence against it, and
  what would change the conclusion.
- `docs/index.html`: a static dashboard. Each chart shows the query behind it
  and one sentence on what it shows.
- `build.py`: one command that fetches the data and regenerates both files.

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

Twelve claims are tested against fixed thresholds. The current result is in
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
| 1 | `python3 -m unittest discover -s tests` | `Ran 21 tests` and `OK` |
| 2 | `python3 build.py --offline` | Twelve lines `C1` to `C12`, each `SUPPORTED` or `REFUTED`, then `wrote THESIS.md, docs/index.html, data/derived/metrics.json` |
| 3 | `git status --short` | Nothing: the offline build reproduces the committed files byte for byte |
| 4 | `python3 build.py` | The same twelve lines computed on today's data; `git diff THESIS.md` shows which numbers moved |
| 5 | Open `docs/index.html` in a browser | Six tiles, a table of twelve claims with verdicts, tables for the halt and for channels, six charts with the halt shaded; hovering a chart shows every series' value for that week or month |
| 6 | Change `WINDOW = 90` to `WINDOW = 30` in `pipeline/config.py`, then run step 2 | Every figure in `THESIS.md` is recomputed for a 30-day window |
| 7 | Optional. Put `INTENTS_EXPLORER_JWT=...` in `.env`, then `python3 -m pipeline.explorer --from 2026-04-09 --to 2026-11-10` | `page 5, reached ...` lines, then `wrote data/raw/explorer_daily.json`. About three hours: the API allows one request per five seconds. An interrupted run resumes. Then run `python3 build.py` so the manifest picks up the new file |

Step 2 uses the snapshot in `data/raw/`, whose hashes are checked against
`data/raw/manifest.json`. Edit any raw file and the build stops with
`does not match the hash in manifest.json`.

| 8 | Optional. `python3 -m pipeline.onchain --from 2026-08-13 --to 2026-11-10` | Per-wallet progress lines, then `wrote data/raw/onchain_revenue.json`. About 30 minutes on NearBlocks' free tier; no key |

Steps 7 and 8 are not needed to reproduce the thesis: the Explorer aggregates are
committed. The Explorer key is free from https://partners.near-intents.org.

## Checking the predictions were not edited

| Step | Do | See |
| --- | --- | --- |
| 1 | `sha256sum predictions/predictions.json` | the hash in `predictions/predictions.json.sha256` |
| 2 | `git show predictions-v1:predictions/predictions.json \| sha256sum` | the same hash, from the tagged commit |
| 3 | `pip install opentimestamps-client`, then `ots upgrade predictions/predictions.json.ots` and `ots verify predictions/predictions.json.ots` | a Bitcoin block time no later than the tag date (the proof needs a few hours after sealing to confirm) |
| 4 | `python3 -m pipeline.seal --check` | `sealed predictions match config` |

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
| Transfers into NEAR's three revenue wallets | `api.nearblocks.io/v1/account/{wallet}/txns`, `/ft-txns` | no |
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
  sources (Midgard; transfers into the revenue wallets). Intents volume was not
  rebuilt from `intents.near` events; two public attempts disagree on whether
  the reported figure is one or two sided, so shares are shown both ways.
- Three outside facts are cited rather than computed, all in
  `pipeline/config.py`: what the THORChain halt was, a later short suspension,
  and which distribution channels also route to rival venues (each with its
  source, in `CHANNEL_NOTES`).
- Claim thresholds were chosen after a first look at the data and are not
  pre-registered. The dated predictions are sealed: see "Checking the
  predictions were not edited" below.

## Disclosure

- All code in this repository was written during the hackathon window. There
  is no earlier baseline.
- AI coding tools were used to speed up writing the code. The author directed
  the work and is responsible for every decision and result in this repository.
- No third-party libraries: Python standard library, and plain HTML, CSS and
  JavaScript in the dashboard.

## License

MIT, see `LICENSE`.

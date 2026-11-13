# NEAR Intents leads cross-chain swaps, but too little of it reaches the NEAR token yet. The call is to watch, not buy, until buybacks cover 50% of new NEAR and the 30-day share is back above 50%.

> Data 2024-12-10 to 2026-11-10, fetched 2026-11-11. Every figure is computed by `python3 build.py`; none is typed by hand. The method, every check and every limit: [METHODS.md](METHODS.md).

## The call: watch, not buy

**WATCH.** The business is real and leading; the token's cut of it is not yet large enough, and the lead is slipping in the latest weeks.

1. **The business leads.** 58% of the four swap venues' volume over 90 days (56% counting one side of every swap for every venue), at a take rate above its rivals' median; 8 of 14 claims hold.
2. **The lead is slipping now.** The 30-day share is 46% and the latest complete week 38%; over 30 days Intents' volume fell 21% while THORChain's rose 32%.
3. **The token sees too little of it.** Over the window buybacks took 1.00M NEAR against 7.96M newly issued (13%). Covering 50% would take 4.0x today's captured revenue. The share of fees reaching NEAR is rising: 8% → 12% → 20% → 27% over consecutive 90-day windows.

| Moves the call to | When | Now |
| --- | --- | --- |
| ACCUMULATE | buybacks cover at least 50% of new NEAR **and** the 30-day share is at least 50% | 13% of new NEAR; 30-day share 46% |
| AVOID | the 90-day share falls below 40% **or** the share of fees reaching NEAR falls from one 90-day window to the next | 90-day share 58% (latest week 38%); fees reaching NEAR 27%, up from 20% |

No price target: this measures the business and the token's cut of it, not a fair price. Next review: 2026-12-10, or sooner if a line above is crossed. The rule is `CALL` in `pipeline/config.py`, computed by `metrics.investment_call()`. It was written on 2026-11-12, after the data was seen, and sealed the same day in the third seal, so the review on that date applies the rule as it stands.

## Fourteen claims, each one number against one threshold

**14 claims tested: 8 supported, 6 refuted.** Thresholds are in `pipeline/config.py`.

| # | Claim | Measured | Threshold | Verdict |
| --- | --- | --- | --- | --- |
| C1 | NEAR Intents is the largest swap venue with more than 50% of volume, whether volume is taken as reported, one side of each swap is counted for every venue, or Intents volume is rebuilt from intents.near itself. | 55.2% | 50.0% | **SUPPORTED** |
| C2 | Most of the year-on-year volume gain came from taking share, not from market growth. | 44.5% | 50.0% | **REFUTED** |
| C3 | The peer-set market itself grew more than 25% year on year. | +128% | +25% | **SUPPORTED** |
| C4 | Intents charges at least the median take rate of its rivals (it is not winning on price alone). | 15.5 bps | 13.0 bps | **SUPPORTED** |
| C5 | NEAR keeps more than 50% of the gross fees Intents generates. | 27.1% | 50.0% | **REFUTED** |
| C6 | The lead is stable: weekly share never fell below 40% in the last 26 undistorted weeks. | 23.2% | 40.0% | **REFUTED** |
| C7 | When its largest rival stopped trading, Intents picked up more than 33% of the flow that rival had carried. | 40.6% | 33.0% | **SUPPORTED** |
| C8 | Intents daily volume is steadier than every rival's (lower standard deviation relative to its mean). | 0.36 | 0.69 | **SUPPORTED** |
| C9 | The share of fees reaching NEAR rose in every one of the last 4 consecutive 90-day windows. | 3 of 3 rises | 3 of 3 | **SUPPORTED** |
| C10 | No single distribution channel carries more than 33% of 1Click swap volume. | 37.8% | 33.0% | **REFUTED** |
| C11 | Intents is also the largest venue when the four big bridges are added to the peer set. | rank 3 of 8 | rank 1 | **REFUTED** |
| C12 | The captured-revenue figure used here matches the transfers into NEAR's three revenue wallets within 5%. | 1.5% apart | within 5% | **SUPPORTED** |
| C13 | The reported Intents volume counts both sides of each swap, like the rivals' figures: on every day rebuilt from intents.near token_diff events (through August, where the method applies) it sits inside the both-sides interval and outside the one-side interval. | 4 of 4 days | 4 of 4 | **SUPPORTED** |
| C14 | The NEAR bought back with Intents revenue covers at least half of the NEAR newly issued in the same window. | 12.6% | 50.0% | **REFUTED** |

## Why it could work

- **The largest venue, on every consistent count.** Over the 90 days to 2026-11-10, NEAR Intents settled $12.10B of the $20.83B that the four venues moved, a 58% share; THORChain was second with 30%. One year earlier its share was 40%. Counting one side of each swap for every venue gives 56%. [details](METHODS.md#how-volume-is-counted)
- **It held up when a rival stopped.** THORChain was halted for 37 days after an exploit. Intents grew +38% over those days and kept the higher level afterwards, equal to 41% of the flow THORChain lost. But growth of that size was ordinary for Intents over the year before (52nd percentile), so the halt shows Intents could absorb the flow, not that the halt caused the gain. [details](METHODS.md#the-stress-test)
- **It does not win on price.** Intents charged 15.5 bps of volume in gross fees over the window; the median of its three rivals was 13.0 bps, and Chainflip charged 31.4 bps. [details](METHODS.md#the-rest)

## What could break it

- **Most fees do not reach NEAR.** Of $18.76M in gross Intents fees over the window, $5.08M (27%) reached NEAR's revenue wallets; the rest stayed with solvers and the third-party front ends that distribute Intents. Over consecutive 90-day windows the share reaching NEAR was 8%, 12%, 20%, 27% (oldest first, the last ending 2026-11-10). [details](METHODS.md#evidence-against)
- **Buybacks are small next to issuance.** NEAR's supply grew 7.96M over 90 days (from block headers); buybacks took 1.00M, 13% of it. [details](METHODS.md#what-it-means-for-the-near-token)
- **The rival is coming back.** In the last 30 days Intents volume changed by -21% against the 30 days before, while THORChain changed by +32%. [details](METHODS.md#evidence-against)
- **Bridges are bigger.** With the four large bridges added, Intents has 18% of the eight venues' volume and ranks 3 of 8. [details](METHODS.md#all-eight-venues) When THORChain halted, no bridge behaved as a substitute; swap venues did. [details](METHODS.md#which-market-a-substitution-test)

## Why these numbers can be trusted

- **Intents volume is rebuilt from the chain for every day, not taken on trust.** Each rival's double counting is measured from its own indexer. For Intents, every log line intents.near wrote (NEAR's public BigQuery dataset) rebuilds the reported figure: token_diff events through August, and from September the transfers through 1Click routers that replaced them (median 1.04 of reported, within 20% on 69 of 71 days). With on-chain volume the share is 60%; the strictest reading gives 55%. [details](METHODS.md#how-volume-is-counted)
- **Revenue matches the chain.** Transfers into NEAR's three revenue wallets come to 98.5% of the revenue figure used. [details](METHODS.md#evidence-against)
- **Supply and activity come from the chain.** Issuance is read from block headers; L1 activity is counted by two indexers that agree. [details](METHODS.md#what-it-means-for-the-near-token)
- **The TEE run is checked down to Intel's root.** The headline share was recomputed inside an Intel TDX enclave through OutLayer. This repository verifies the enclave's quote itself: it binds the key that delivered the result, chains to Intel's root CA, and its TCB is UpToDate against Intel's current collateral (13 of 13 checks pass). [details](METHODS.md#how-this-can-be-checked)
- **Anyone can rebuild it.** `python3 build.py --offline` reproduces this file and the dashboard byte for byte from the committed snapshot; the predictions, the call's rule and the on-chain method are sealed on Bitcoin. [details](METHODS.md#how-this-can-be-checked)

## Dated predictions

| # | Due | Prediction | Now | Status |
| --- | --- | --- | --- | --- |
| P1 | 2027-02-28 | NEAR Intents still holds at least 50% of peer-set volume over the trailing 90 days. | 58.1% | PENDING |
| P2 | 2027-02-28 | NEAR's captured revenue is at least 30% of gross Intents fees over the trailing 90 days. | 27.1% | PENDING |
| P3 | 2027-05-31 | The Intents take rate has not been competed below 12 bps over the trailing 90 days. | 15.5 bps | PENDING |
| P4 | 2026-11-12 | NEAR Intents holds at least 40% of the four swap venues' volume over 2026-11-11 and 2026-11-12, days after the data this thesis was built on. | n/a | PENDING |
| P5 | 2026-11-12 | The Intents take rate stays at or above 12 bps over 2026-11-11 and 2026-11-12. | n/a | PENDING |
| P6 | 2026-12-10 | NEAR Intents keeps at least 40% of the four swap venues' volume over 2026-11-13 to 2026-12-10 (the thesis's kill line). | n/a | PENDING |
| P7 | 2026-12-10 | NEAR Intents is still the largest of the four swap venues over 2026-11-13 to 2026-12-10 (its share minus the largest rival's is above zero). | n/a | PENDING |
| P8 | 2026-12-10 | Intents volume rebuilt from intents.near events with the sealed BigQuery method stays within 0.90 to 1.20 times the reported volume over 2026-11-13 to 2026-12-10, so the headline keeps an on-chain check. | n/a | PENDING |

P1 to P3 are sealed by hash, timestamped on Bitcoin and written on NEAR mainnet; P4 and P5 are in a second seal, timestamped on Bitcoin after the first of their two days had ended. P6 to P8 are in a third seal made before their window starts, together with the call's rule and the on-chain method. P4 is also graded a second time, inside the TEE: the same committed WASM, run through OutLayer after 2026-11-12 has ended, on tee/share-check/input-p4.json (2026-11-11 to 2026-11-12). That run is not made yet. [details](METHODS.md#what-would-change-my-mind)

## What this cannot say

- The on-chain router rule that rebuilds Intents volume after August was found by looking at the data. It is sealed now and P8 tests it on days not yet seen.
- Which market is the right one is tested once, with the THORChain halt: only swap venues behaved as substitutes, no bridge did. One event is thin evidence, so both market sets are shown. [details](METHODS.md#which-market-a-substitution-test)
- Claim thresholds and the call's rule were set after a first look at the data. They are sealed so any later change shows, and P6 to P8 grade the thesis on days after the seal.

Every other limit: [details](METHODS.md#what-this-analysis-cannot-say)

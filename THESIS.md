# NEAR Intents leads the native-swap venues, but too little of it reaches the NEAR token yet. 58% of the four native-swap venues over 90 days, 46% over 30 days, 38% in the latest week; third, with 18%, once four bridges count. The call is to watch, not buy, until buybacks cover 50% of new NEAR and the 30-day share is back above 50%.

> Data 2024-12-10 to 2026-11-10. Every figure is computed by `python3 build.py`; none is typed by hand. The method, every check and every limit: [METHODS.md](METHODS.md). Dashboard: https://n0ctr1.github.io/share-shift/

## The call: watch, not buy

**WATCH.** The business is real and leading; the token's cut of it is not yet large enough, and the lead is slipping in the latest weeks.

| Moves the call to | When | Now |
| --- | --- | --- |
| ACCUMULATE | buybacks cover at least 50% of new NEAR **and** the 30-day share is at least 50% | 13% of new NEAR; 30-day share 46% |
| AVOID | the 90-day share falls below 40% **or** the share of fees reaching NEAR falls from one 90-day window to the next | 90-day share 58% (latest week 38%); fees reaching NEAR 27%, up from 20% |

The rule is `CALL` in `pipeline/config.py`, sealed on 2026-11-12; next review 2026-12-10.

## Is Intents the leader? Yes

- 58% of four-venue swap volume over 90 days, up from 40% a year earlier; THORChain is second with 30%.
- First on every consistent way of counting: 58% as reported, 56% counting one side of each swap, 60% on volume rebuilt from the chain. Only halving Intents alone, against the rivals' own indexers, puts THORChain ahead. [details](METHODS.md#how-volume-is-counted)
- When THORChain halted for 37 days, Intents took 41% of the flow it lost, but growth that size was ordinary for Intents (52nd percentile of the year before), so it shows capacity, not cause. [details](METHODS.md#the-stress-test)
- Add the four large bridges and Intents has 18%, rank 3 of 8. When THORChain halted, swap venues behaved as its substitutes and no bridge did. [details](METHODS.md#which-market-a-substitution-test)
- It does not win on price: 15.5 bps of volume in gross fees against a rival median of 13.0 bps.

## Does it reach the NEAR token? Not yet

- 27% of gross Intents fees reach NEAR's revenue wallets, rising every 90 days: 8% → 12% → 20% → 27%; the rest stays with solvers and the front ends that distribute Intents. [details](METHODS.md#evidence-against)
- Buybacks took 1.00M NEAR against 7.96M newly issued over 90 days, 13%. Covering half would take 4.0× today's captured revenue. [details](METHODS.md#what-it-means-for-the-near-token)
- In the last 30 days Intents volume changed by -21% against the 30 days before, while THORChain changed by +32%.

## Confidential Intents: what the public chain cannot see

- 96% of last week's on-chain Intents volume shows only as money entering and leaving 1Click routers, with no public fill behind it, as settlement moves to NEAR's private shard; the public chain verifies the value moved, not who filled it.
- The reported series matches what the public chain sees (1.07×), so private flow does not inflate the 58% share; swaps that stay inside the shard are missing from both, which can only understate it. Capture could be off either way. [details](METHODS.md#confidential-intents-what-the-public-chain-cannot-see)

## Twelve months out

| Scenario | Market | Share | Take rate | Capture | Buybacks cover new NEAR |
| --- | --- | --- | --- | --- | --- |
| bear | -30% | 40% | 12.0 bps | 25% | **4%** |
| base | +0% | 50% | 14.0 bps | 35% | **13%** |
| bull | +50% | 60% | 15.5 bps | 50% | **36%** |

Twelve months out, buybacks would cover 4% of new NEAR in the bear case, 13% in the base and 36% in the bull; even the bull case needs 70% of fees reaching NEAR to get to half. Assumptions are `SCENARIOS` in `pipeline/config.py`; the build recomputes the outcome. [details](METHODS.md#twelve-months-out-three-scenarios)

## Why these numbers can be trusted

| Check | Result |
| --- | --- |
| Intents volume rebuilt from the chain, every day | 1.04× reported |
| Rivals' double counting measured from their own indexers | 8,886 swaps read |
| Revenue matches the revenue wallets | 98.5% |
| Supply from block headers, activity from two indexers | 454 of 455 days agree |
| Headline recomputed in a TEE, checked to Intel's root | 13/13 checks |
| Thresholds, the call's rule and predictions sealed | 3 seals, 2 on NEAR |
| Every number rebuilds, byte for byte | build.py --offline |

How to rerun each one: [details](METHODS.md#how-this-can-be-checked)

## 14 claims, each one number against one threshold

**14 claims tested: 8 supported, 6 refuted.**

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

## Dated predictions

| # | Due | Prediction | Now | Status |
| --- | --- | --- | --- | --- |
| P1 | 2027-02-28 | NEAR Intents still holds at least 50% of peer-set volume over the trailing 90 days. | 58.1% | PENDING |
| P2 | 2027-02-28 | NEAR's captured revenue is at least 30% of gross Intents fees over the trailing 90 days. | 27.1% | PENDING |
| P3 | 2027-05-31 | The Intents take rate has not been competed below 12 bps over the trailing 90 days. | 15.5 bps | PENDING |
| P4 | 2026-11-12 | NEAR Intents holds at least 40% of the four swap venues' volume over 2026-11-11 and 2026-11-12, days after the data this thesis was built on. | 44.5% | MET |
| P5 | 2026-11-12 | The Intents take rate stays at or above 12 bps over 2026-11-11 and 2026-11-12. | 17.0 bps | MET |
| P6 | 2026-12-10 | NEAR Intents keeps at least 40% of the four swap venues' volume over 2026-11-13 to 2026-12-10 (the thesis's kill line). | n/a | PENDING |
| P7 | 2026-12-10 | NEAR Intents is still the largest of the four swap venues over 2026-11-13 to 2026-12-10 (its share minus the largest rival's is above zero). | n/a | PENDING |
| P8 | 2026-12-10 | Intents volume rebuilt from intents.near events with the sealed BigQuery method stays within 0.90 to 1.20 times the reported volume over 2026-11-13 to 2026-12-10, so the headline keeps an on-chain check. | n/a | PENDING |

Sealed in three seals, timestamped on Bitcoin; the first and third are written on NEAR mainnet. [details](METHODS.md#what-would-change-my-mind)

## What this cannot say

- Confidential Intents settle on a private shard: the public chain verifies the value that crosses intents.near, not the fills behind it, and swaps that stay inside the shard are not counted at all.
- The router rule that rebuilds Intents volume after August was found by looking at the data; it is sealed now and tested on days not yet seen (P8).
- Which market is the right one rests on one natural experiment, the THORChain halt.
- Claim thresholds and the call's rule were set after a first look at the data; they are sealed so any later change shows.

Every other limit: [details](METHODS.md#what-this-analysis-cannot-say)

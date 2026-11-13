"""Everything a reader might want to change lives here.

The peer set, the analysis windows and the claim thresholds are fixed in this
file, so a re-run with different choices is a one-line edit and a visible diff.
"""

# Native cross-chain swap venues that DefiLlama tracks with a daily USD volume
# series on its free API. Order is the display order and never changes.
PEERS = [
    {"slug": "near-intents", "name": "NEAR Intents", "coingecko": "near"},
    {"slug": "thorchain-dex", "name": "THORChain", "coingecko": "thorchain"},
    {"slug": "chainflip-amm", "name": "Chainflip", "coingecko": "chainflip"},
    {"slug": "maya-protocol", "name": "Maya Protocol", "coingecko": "cacao"},
]
SUBJECT = "near-intents"

# Cross-chain bridges that mostly move the same asset between chains. A
# different product from a native-asset swap, but the same user need, so the
# headline share is also computed against this wider set.
WIDE_PEERS = [
    {"slug": "relay", "name": "Relay"},
    {"slug": "debridge", "name": "deBridge"},
    {"slug": "across", "name": "Across"},
    {"slug": "stargate-v2", "name": "Stargate V2"},
]

LLAMA = "https://api.llama.fi"
FEE_ONLY = WIDE_PEERS  # older name, still used for the fee table
VOLUME_URL = LLAMA + "/summary/dexs/{slug}"
BRIDGE_VOLUME_URL = LLAMA + "/summary/bridges/{slug}"
# THORChain's own indexer, used only to cross-check the DefiLlama series.
MIDGARD_URL = "https://gateway.liquify.com/chain/thorchain_midgard/v2/history/swaps?interval=day&count=400"
MIDGARD_SLUG = "thorchain-dex"
FEES_URL = LLAMA + "/summary/fees/{slug}?dataType={data_type}"
MCAP_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids={ids}&vs_currencies=usd&include_market_cap=true"
)

# Trailing window, in days, behind every headline number.
WINDOW = 90
# Other window lengths the headline share is recomputed for, so a reader can
# see how much the verdict depends on the choice of window.
SENSITIVITY_WINDOWS = [30, 90, 180, 365]
# A monthly take rate is only drawn when the venue moved at least this much in
# the month; below it, fees and volume are too thin for the ratio to mean much.
MIN_MONTH_VOLUME = 50e6
# Weeks used for the stability statistics.
STABILITY_WEEKS = 26

# A rival counts as halted when it reports zero volume for at least this many
# days in a row. The build finds such runs in the data by itself.
MIN_HALT_DAYS = 14
# Only a halt of a venue that carried at least this share beforehand is used
# as a natural experiment.
MIN_HALT_SHARE = 0.10
# Outside confirmation for halts the data shows. The dates and volumes always
# come from the data; this only says what the event was.
KNOWN_EVENTS = [
    {
        "slug": "thorchain-dex",
        "overlaps": "2026-06-01",
        "what": "THORChain halted trading after a $10.7M vault exploit and resumed on 2026-06-23",
        "source": "https://www.theblock.co/news/ecosystems/2026-06-23-thorchain-resumes-trading-after-exploit-405767",
    },
]

# How far back to look when asking whether the subject's growth during a halt
# was unusual for it. Both are reported; they disagree, and the thesis says so.
PLACEBO_LOOKBACKS = [180, 365]
# Dated context for the most recent weeks. Used in one sentence, never in a number.
CONTEXT_NOTES = [
    {
        "slug": "thorchain-dex",
        "date": "2026-11-04",
        "from": "2026-10-31",
        "to": "2026-11-03",
        "what": "THORChain suspended swaps again on 2026-10-31 and restored most routes around 2026-11-04",
        "source": "https://www.crowdfundinsider.com/2026/11/321170-thorchain-brings-bitcoin-and-ethereum-swaps-back-online-lifting-rune-15/",
    },
]

# Distribution channels (the `referral` field of a 1Click swap): does the
# front end behind each one also send swaps to any of the other seven venues
# in this analysis? A swap that arrives through such a channel could have gone
# elsewhere at no cost to the user. Each answer cites what it rests on.
#   "yes"        documented as routing to at least one rival venue
#   "no"         documented as using NEAR Intents only for swaps
#   "other"      routes elsewhere too, but to none of the seven rivals
#   "unlabelled" the swap carried no referral, so there is nothing to look up
#   "unknown"    the operator of the channel could not be identified
CHANNEL_NOTES = {
    "swapkit": {
        "routes_to_rivals": "yes",
        "note": "THORChain, Chainflip, Maya",
        "source": "https://swapkit.dev/blog/swapkit-near-intents-integration/",
    },
    "lifi": {
        "routes_to_rivals": "yes",
        "note": "Across, Relay, Stargate, Chainflip",
        "source": "https://docs.li.fi/introduction/solana-ecosystem",
    },
    "rango": {
        "routes_to_rivals": "yes",
        "note": "THORChain, Maya, Chainflip",
        "source": "https://blog.thorchain.org/protocol-spotlight-rango-exchange",
    },
    "zodl": {
        "routes_to_rivals": "no",
        "note": "Zodl wallet (formerly Zashi); swaps go through NEAR Intents",
        "source": "https://electriccoin.co/blog/zashi-swaps-decentralized-on-ramp-is-live",
    },
    "stableflow": {
        "routes_to_rivals": "other",
        "note": "also quotes Circle CCTP and USDT0",
        "source": "https://defillama.com/protocol/stableflow",
    },
    "(none)": {"routes_to_rivals": "unlabelled", "note": "no referral on the swap", "source": None},
}
MULTI_VENUE_CHANNELS = {name: v["source"] for name, v in CHANNEL_NOTES.items()
                        if v["routes_to_rivals"] == "yes"}
# The account that receives NEAR's own cut of 1Click app fees.
BUYBACK_ACCOUNT = "buybacks.multisignature.near"
# How many channels and fee recipients to list by name; the rest are "other".
TOP_N = 8

# How each venue's reported volume is counted. THORChain and Maya route every
# native swap through their own token, and their indexer adds up both halves;
# the build measures that from the indexer's own leg breakdown. For NEAR
# Intents two public re-computations from intents.near events disagree on
# whether the reported figure counts one side of a swap or both, so every
# share is also computed with Intents halved.
LEG_SOURCES = {
    "thorchain-dex": "https://gateway.liquify.com/chain/thorchain_midgard/v2/history/swaps?interval=day&count=400",
    "maya-protocol": "https://midgard.mayachain.info/v2/history/swaps?interval=day&count=400",
    "chainflip-amm": "https://explorer-service-processor.chainflip.io/graphql",
}
# Leg types that are the two halves of one routed swap.
LEG_PAIRS = [("toRuneVolume", "toAssetVolume"), ("fromTradeVolume", "toTradeVolume"),
             ("fromSecuredVolume", "toSecuredVolume")]
SUBJECT_BASIS_NOTES = [
    {"finding": "public swaps counted once are 46% of the reported volume on six sampled days, 92% counting both sides",
     "source": "https://github.com/soldanoandrea/near-thesis"},
    {"finding": "public net swap volume matches the reported volume within about 1% before confidential intents launched",
     "source": "https://github.com/EmekaManuel/nearquery"},
]
# The event method counts DIP-4 token_diff swaps. Through August swaps settle
# that way (contract events v0.3.x); from September the contract increasingly
# settles them through transfer intents (v0.4.3 by mid-October, no token_diff
# in a 5 November sample, see data/raw/intents_event_format.json). Days after
# this date are shown but not used for C13.
EVENTS_VALID_UNTIL = "2026-08-31"
SUBJECT_VOLUME_SOURCE = ("DefiLlama reads it from NEAR's own Dune table "
                         "dune.near.dataset_near_intents_metrics (column volume_amount_usd)")

# Claim thresholds. A claim is SUPPORTED or REFUTED by comparing one computed
# number with one of these; nothing else decides the verdict.
THRESHOLDS = {
    "leader_share": 0.50,        # C1: subject holds more than half of peer volume
    "share_effect": 0.50,        # C2: more than half of growth came from share gain
    "pie_growth": 0.25,          # C3: peer-set volume grew more than 25% year on year
    "take_rate_vs_peers": 1.00,  # C4: subject take rate at or above peer median
    "capture": 0.50,             # C5: NEAR keeps more than half of gross fees
    "share_floor": 0.40,         # C6: weekly share never fell below 40% in 26 weeks
    "top_channel": 0.33,         # C10: no single channel carries more than a third of 1Click volume
    "onchain_match": 0.05,       # C12: provider revenue within 5% of transfers into NEAR's wallets
    "events_both": 1.0,          # C13: the reported figure sits inside the both-sides interval
    "tee_match": 0.001,          # C14: TEE share within 0.1 point of the build
    "buyback_offset": 0.50,      # C15: NEAR bought back covers at least half of net new supply
    "absorbed": 0.33,            # C7: subject picked up over a third of a halted rival's flow
}

# Dated predictions. Each is checked by re-running the build after the date.
PREDICTIONS = [
    {
        "id": "P1",
        "due": "2027-02-28",
        "metric": "share_trailing",
        "op": ">=",
        "value": 0.50,
        "text": "NEAR Intents still holds at least 50% of peer-set volume "
                "over the trailing 90 days.",
    },
    {
        "id": "P2",
        "due": "2027-02-28",
        "metric": "capture_trailing",
        "op": ">=",
        "value": 0.30,
        "text": "NEAR's captured revenue is at least 30% of gross Intents fees "
                "over the trailing 90 days.",
    },
    {
        "id": "P3",
        "due": "2027-05-31",
        "metric": "take_rate_trailing_bps",
        "op": ">=",
        "value": 12.0,
        "text": "The Intents take rate has not been competed below 12 bps "
                "over the trailing 90 days.",
    },
]


# Second seal, 2026-11-12. The claim thresholds above were chosen after looking
# at data through 2026-11-10; they are sealed here as they stand, with two
# short predictions on 11 and 12 November, so the build can grade them before
# the hackathon deadline. The seal's Bitcoin timestamp (below) came after 11
# November had ended, so only 12 November is a day that had not yet happened. Any later change to THRESHOLDS or to these
# predictions makes the build stop (predictions/predictions-v2.json).
PREDICTIONS_V2 = [
    {
        "id": "P4",
        "due": "2026-11-12",
        "window_days": 2,
        "metric": "share_window",
        "op": ">=",
        "value": 0.40,
        "text": "NEAR Intents holds at least 40% of the four swap venues' volume over "
                "2026-11-11 and 2026-11-12, days after the data this thesis was built on.",
    },
    {
        "id": "P5",
        "due": "2026-11-12",
        "window_days": 2,
        "metric": "take_rate_window_bps",
        "op": ">=",
        "value": 12.0,
        "text": "The Intents take rate stays at or above 12 bps over 2026-11-11 and 2026-11-12.",
    },
]
SEAL_V2 = {"sealed_on": "2026-11-12", "data_seen_through": "2026-11-10"}
# Where the second seal's OpenTimestamps proof lands; check with
# `python3 -m pipeline.ots --file predictions/predictions-v2.json`. Not sealed.
SEAL_V2_BITCOIN = {"block": 975532, "time_utc": "2026-11-12 08:26"}


# The investment call: a rule on computed numbers, so the call moves with the
# data and anyone can see what would change it. Written 2026-11-12, after the
# data was seen, and not sealed; the thresholds reuse the thesis's own lines.
#   ACCUMULATE  the position holds AND the token captures enough of it
#   AVOID       the position is lost OR capture stops rising
#   WATCH       otherwise: the business leads, the token link is not there yet
# Since the third seal (below) the rule is sealed: changing it stops the build.
CALL = {
    "share_90d_kill": 0.40,          # AVOID below this 90-day share (the thesis's kill line)
    "share_30d_hold": 0.50,          # ACCUMULATE needs the 30-day share at or above this
    "buyback_offset_accumulate": 0.50,  # ACCUMULATE needs buybacks >= this share of new NEAR
    "review_after_days": 30,         # next review: this many days after the data ends
}


# Third seal, 2026-11-12. Everything a reader could suspect of being tuned after
# the fact is fixed here before the days it is graded on: the investment-call
# rule above, the on-chain counting method (the SHA-256 of the two BigQuery
# queries in pipeline/bq.py and the router rule), and three predictions on a
# window that starts after the seal: 2026-11-13 to 2026-12-10, the call's
# review date. The seal's hash is also written on NEAR under the author's
# account (python3 -m pipeline.anchor --seal v3). Any later change to CALL,
# to those queries or to these predictions makes the build stop
# (predictions/predictions-v3.json).
PREDICTIONS_V3 = [
    {
        "id": "P6",
        "due": "2026-12-10",
        "window_days": 28,
        "metric": "share_window",
        "op": ">=",
        "value": 0.40,
        "text": "NEAR Intents keeps at least 40% of the four swap venues' volume over "
                "2026-11-13 to 2026-12-10 (the thesis's kill line).",
    },
    {
        "id": "P7",
        "due": "2026-12-10",
        "window_days": 28,
        "metric": "lead_window",
        "op": ">",
        "value": 0.0,
        "text": "NEAR Intents is still the largest of the four swap venues over "
                "2026-11-13 to 2026-12-10 (its share minus the largest rival's is above zero).",
    },
    {
        "id": "P8",
        "due": "2026-12-10",
        "window_days": 28,
        "metric": "onchain_ratio_window",
        "op": "between",
        "value": [0.90, 1.20],
        "text": "Intents volume rebuilt from intents.near events with the sealed BigQuery "
                "method stays within 0.90 to 1.20 times the reported volume over "
                "2026-11-13 to 2026-12-10, so the headline keeps an on-chain check.",
    },
]
SEAL_V3 = {"sealed_on": "2026-11-12", "data_seen_through": "2026-11-11",
           "window_starts": "2026-11-13", "router_min_senders": 500}


# The thesis is computed on data through this day: the snapshot it was written
# on and sealed against. A later fetch extends the data only to grade the dated
# predictions; it does not move the headline window. Not sealed.
THESIS_DATA_END = "2026-11-10"

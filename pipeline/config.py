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

# Distribution channels (the `referral` field of a 1Click swap) that are
# documented as routing to the rival venues too. A swap that arrives through
# one of these could have gone elsewhere at no cost to the user.
MULTI_VENUE_CHANNELS = {
    "swapkit": "https://swapkit.dev/blog/swapkit-near-intents-integration/",
}
# The account that receives NEAR's own cut of 1Click app fees.
BUYBACK_ACCOUNT = "buybacks.multisignature.near"
# How many channels and fee recipients to list by name; the rest are "other".
TOP_N = 8

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

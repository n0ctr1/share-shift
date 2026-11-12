"""Checks on the arithmetic, using small hand-made inputs. No network.

    python3 -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import config, metrics  # noqa: E402


def make_raw(days, volumes, fees=None, revenue=None):
    """volumes: {slug: [v_day0, v_day1, ...]} for every peer."""
    import datetime
    start = datetime.date(2025, 1, 6)  # a Monday
    dates = [(start + datetime.timedelta(days=i)).isoformat() for i in range(days)]
    raw = {"mcap": {"usd_market_cap": {p["slug"]: None for p in config.PEERS}}}
    for p in config.PEERS:
        s = p["slug"]
        raw["volume_" + s] = {"series": dict(zip(dates, volumes[s]))}
        raw["fees_" + s] = {"series": dict(zip(dates, (fees or {}).get(s, [0.0] * days)))}
        raw["revenue_" + s] = {"series": dict(zip(dates, (revenue or {}).get(s, [0.0] * days)))}
    for p in config.FEE_ONLY:
        raw["fees_" + p["slug"]] = {"series": {}}
    return raw, dates


class ShiftShare(unittest.TestCase):
    def test_parts_add_up_to_total(self):
        out = metrics.shift_share(v0=40, m0=100, v1=120, m1=200)
        self.assertAlmostEqual(out["market_effect"] + out["share_effect"], out["total"])
        self.assertAlmostEqual(out["total"], 80)

    def test_pure_market_growth(self):
        out = metrics.shift_share(v0=50, m0=100, v1=100, m1=200)  # share stays 50%
        self.assertAlmostEqual(out["share_effect"], 0)
        self.assertAlmostEqual(out["market_effect"], 50)

    def test_pure_share_gain(self):
        out = metrics.shift_share(v0=10, m0=100, v1=60, m1=100)  # market flat
        self.assertAlmostEqual(out["market_effect"], 0)
        self.assertAlmostEqual(out["share_effect"], 50)


class Helpers(unittest.TestCase):
    def test_window_sum(self):
        self.assertEqual(metrics.window_sum([1, 2, 3, 4, 5], 4, 3), 12)
        self.assertEqual(metrics.window_sum([1, 2, 3], 1, 10), 3)

    def test_pearson(self):
        self.assertAlmostEqual(metrics.pearson([1, 2, 3, 4], [2, 4, 6, 8]), 1.0)
        self.assertAlmostEqual(metrics.pearson([1, 2, 3, 4], [8, 6, 4, 2]), -1.0)
        self.assertIsNone(metrics.pearson([1, 1, 1], [1, 2, 3]))


class Halt(unittest.TestCase):
    def test_longest_zero_run(self):
        self.assertEqual(metrics.longest_zero_run([1, 0, 0, 1, 0, 0, 0, 1]), (4, 3))
        self.assertEqual(metrics.longest_zero_run([1, 2, 0, 0]), (2, 2))
        self.assertEqual(metrics.longest_zero_run([1, 2, 3]), (None, 0))

    def test_absorbed_fraction(self):
        days = 100
        vols = {p["slug"]: [10.0] * days for p in config.PEERS}
        rival = config.PEERS[1]["slug"]
        vols[rival] = [100.0] * days
        vols[config.SUBJECT] = [100.0] * days
        for i in range(40, 60):           # rival dark for 20 days
            vols[rival][i] = 0.0
            vols[config.SUBJECT][i] = 140.0  # subject picks up 40 of the missing 100
        raw, dates = make_raw(days, vols)
        m = metrics.compute(raw, "2030-01-01T00:00:00Z")
        halt = m["halt"]
        self.assertEqual(halt["days"], 20)
        self.assertEqual(halt["first_day"], dates[40])
        self.assertAlmostEqual(halt["absorbed_fraction"], 0.40)
        self.assertAlmostEqual(halt["rival_recovery"], 1.0)
        self.assertAlmostEqual(halt["market_change"], -60.0 / 220.0)
        self.assertEqual({c["id"]: c["verdict"] for c in m["claims"]}["C7"], "SUPPORTED")

    def test_short_gap_is_not_a_halt(self):
        days = 100
        vols = {p["slug"]: [10.0] * days for p in config.PEERS}
        rival = config.PEERS[1]["slug"]
        for i in range(40, 45):
            vols[rival][i] = 0.0
        raw, _ = make_raw(days, vols)
        self.assertIsNone(metrics.compute(raw, "2030-01-01T00:00:00Z")["halt"])


class Placebo(unittest.TestCase):
    def test_growth(self):
        self.assertAlmostEqual(metrics.growth([1, 1, 2, 2], 2, 2), 1.0)
        self.assertIsNone(metrics.growth([1, 1, 2, 2], 1, 2))

    def test_flat_history_makes_any_rise_extreme(self):
        values = [10.0] * 60 + [20.0] * 10
        out = metrics.placebo(values, 60, 10, 50)
        self.assertEqual(out["percentile"], 1.0)
        self.assertAlmostEqual(out["placebo_median"], 0.0)

    def test_steady_trend_makes_the_same_rise_ordinary(self):
        values = [1.05 ** i for i in range(80)]
        out = metrics.placebo(values, 60, 10, 50)
        self.assertLess(out["percentile"], 0.9)


class Channels(unittest.TestCase):
    def _explorer(self, dates, swapkit, direct):
        days = {}
        for d, a, b in zip(dates, swapkit, direct):
            days[d] = {"channels": {"swapkit": {"swaps": 1, "usd": a, "fee_usd": a * 0.01},
                                    "direct": {"swaps": 1, "usd": b, "fee_usd": 0.0}},
                       "fee_recipients": {"wallet.near": a * 0.009,
                                          config.BUYBACK_ACCOUNT: a * 0.001},
                       "routes": {}}
        return {"filters": {"minUsdPrice": 1000}, "days": days}

    def test_shares_fees_and_coverage(self):
        vols = {p["slug"]: [100.0] * 30 for p in config.PEERS}
        raw, dates = make_raw(30, vols)
        table = metrics.build_table(raw, "2030-01-01T00:00:00Z")
        ex = self._explorer(dates, [30.0] * 30, [10.0] * 30)
        rep = metrics.channel_report(ex, table, config.SUBJECT, [dates[0], dates[-1]], None)
        self.assertAlmostEqual(rep["top_channel_share"], 0.75)
        self.assertAlmostEqual(rep["multi_venue_share"], 0.75)
        self.assertAlmostEqual(rep["coverage_of_all_intents_volume"], 0.40)
        self.assertAlmostEqual(rep["app_fee_bps"], 75.0)
        self.assertAlmostEqual(rep["buyback_share_of_app_fees"], 0.10)

    def test_gain_during_halt_is_attributed_to_the_channel_that_grew(self):
        vols = {p["slug"]: [100.0] * 40 for p in config.PEERS}
        raw, dates = make_raw(40, vols)
        table = metrics.build_table(raw, "2030-01-01T00:00:00Z")
        ex = self._explorer(dates, [30.0] * 40, [10.0] * 10 + [50.0] * 10 + [10.0] * 20)
        halt = {"periods": {"before": [dates[0], dates[9]], "during": [dates[10], dates[19]]}}
        rep = metrics.channel_report(ex, table, config.SUBJECT, [dates[0], dates[-1]], halt)
        self.assertEqual(rep["halt"]["movers"][0]["channel"], "direct")
        self.assertAlmostEqual(rep["halt"]["movers"][0]["share_of_gain"], 1.0)
        self.assertAlmostEqual(rep["halt"]["multi_venue_delta"], 0.0)


class Outages(unittest.TestCase):
    def test_two_dead_days_are_found_and_the_long_halt_is_skipped(self):
        days = 120
        vols = {p["slug"]: [100.0] * days for p in config.PEERS}
        rival = config.PEERS[1]["slug"]
        for i in range(30, 50):
            vols[rival][i] = 0.0     # the long halt
        for i in (90, 91):
            vols[rival][i] = 1.0     # a short outage
        raw, dates = make_raw(days, vols)
        m = metrics.compute(raw, "2030-01-01T00:00:00Z")
        self.assertEqual([(x["from"], x["days"]) for x in m["suspensions"]], [(dates[90], 2)])
        self.assertAlmostEqual(m["suspensions"][0]["subject_change"], 0.0)


class CountingBasis(unittest.TestCase):
    def test_routed_pairs_halve_and_scenarios_bracket_the_share(self):
        days = 30
        vols = {p["slug"]: [100.0] * days for p in config.PEERS}
        raw, dates = make_raw(days, vols)
        rival = config.PEERS[1]["slug"]
        # every swap routed: equal legs in and out of the routing token
        raw["legs_" + rival] = {"series": {d: {"totalVolume": 100.0, "toRuneVolume": 50.0,
                                               "toAssetVolume": 50.0, "fromTradeVolume": 0.0,
                                               "toTradeVolume": 0.0, "fromSecuredVolume": 0.0,
                                               "toSecuredVolume": 0.0} for d in dates}}
        table = metrics.build_table(raw, "2030-01-01T00:00:00Z")
        names = {p["slug"]: p["name"] for p in config.PEERS}
        b = metrics.counting_basis(raw, table, config.SUBJECT, names, [dates[0], dates[-1]])
        self.assertAlmostEqual(b["venues"][rival]["once_factor"], 0.5)
        sc = {x["id"]: x["share"] for x in b["scenarios"]}
        self.assertAlmostEqual(sc["reported"], 0.25)
        self.assertAlmostEqual(sc["one_side"], 50.0 / 300.0)   # 50 / (50 + 50 + 100 + 100)
        self.assertAlmostEqual(sc["worst"], 50.0 / 350.0)
        self.assertAlmostEqual(sc["best"], 100.0 / 350.0)


class Table(unittest.TestCase):
    def test_fetch_day_is_excluded(self):
        vols = {p["slug"]: [10.0] * 10 for p in config.PEERS}
        raw, dates = make_raw(10, vols)
        table = metrics.build_table(raw, dates[-1] + "T12:00:00Z")
        self.assertEqual(table["dates"][-1], dates[-2])

    def test_calendar_stops_at_slowest_peer(self):
        vols = {p["slug"]: [10.0] * 10 for p in config.PEERS}
        raw, dates = make_raw(10, vols)
        slow = config.PEERS[1]["slug"]
        for d in dates[-3:]:
            del raw["volume_" + slow]["series"][d]
        table = metrics.build_table(raw, "2030-01-01T00:00:00Z")
        self.assertEqual(table["dates"][-1], dates[-4])

    def test_only_complete_weeks(self):
        vols = {p["slug"]: [1.0] * 17 for p in config.PEERS}  # 2 weeks + 3 days
        raw, _ = make_raw(17, vols)
        table = metrics.build_table(raw, "2030-01-01T00:00:00Z")
        weeks = metrics.weekly(table)
        self.assertEqual(len(weeks), 2)
        self.assertEqual(weeks[0][config.SUBJECT]["volume"], 7.0)


class EndToEnd(unittest.TestCase):
    def test_share_take_rate_capture(self):
        days = 120
        vols = {p["slug"]: [100.0] * days for p in config.PEERS}
        vols[config.SUBJECT] = [300.0] * days                    # 300 of 600 = 50%
        fees = {p["slug"]: [0.1] * days for p in config.PEERS}   # 10 bps for rivals
        fees[config.SUBJECT] = [0.6] * days                      # 20 bps
        revenue = {config.SUBJECT: [0.15] * days}                # 25% of fees
        raw, _ = make_raw(days, vols, fees, revenue)
        m = metrics.compute(raw, "2030-01-01T00:00:00Z")
        self.assertAlmostEqual(m["trailing"]["share"][config.SUBJECT], 0.5)
        self.assertAlmostEqual(m["trailing"]["take_bps"][config.SUBJECT], 20.0)
        self.assertAlmostEqual(m["trailing"]["rival_take_median_bps"], 10.0)
        self.assertAlmostEqual(m["trailing"]["capture"], 0.25)
        self.assertIsNone(m["yoy"])  # under a year of data
        verdicts = {c["id"]: c["verdict"] for c in m["claims"]}
        self.assertEqual(verdicts["C1"], "REFUTED")        # exactly 50% is not "more than"
        self.assertEqual(verdicts["C2"], "NOT COMPUTABLE")
        self.assertEqual(verdicts["C4"], "SUPPORTED")
        self.assertEqual(verdicts["C5"], "REFUTED")
        self.assertEqual(verdicts["C6"], "SUPPORTED")

    def test_outage_week_is_flagged(self):
        days = 140
        vols = {p["slug"]: [100.0] * days for p in config.PEERS}
        rival = config.PEERS[1]["slug"]
        for i in range(70, 77):
            vols[rival][i] = 0.0
        raw, _ = make_raw(days, vols)
        m = metrics.compute(raw, "2030-01-01T00:00:00Z")
        self.assertEqual([f["peer"] for f in m["quality_flags"]], [config.PEERS[1]["name"]])


if __name__ == "__main__":
    unittest.main()

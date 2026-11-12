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

    def test_measured_swap_actions_replace_the_pair_sum_bound(self):
        days = 30
        vols = {p["slug"]: [100.0] * days for p in config.PEERS}
        raw, dates = make_raw(days, vols)
        rival = config.PEERS[1]["slug"]
        raw["legs_" + rival] = {"series": {d: {"totalVolume": 100.0, "toRuneVolume": 50.0,
                                               "toAssetVolume": 50.0, "fromTradeVolume": 0.0,
                                               "toTradeVolume": 0.0, "fromSecuredVolume": 0.0,
                                               "toSecuredVolume": 0.0} for d in dates}}
        raw["actions_" + rival] = {"double_value_share": 0.8, "double_value_share_p05": 0.75,
                                   "double_value_share_p95": 0.85, "once_factor": 1 / 1.8,
                                   "swaps_read": 100}
        table = metrics.build_table(raw, "2030-01-01T00:00:00Z")
        names = {p["slug"]: p["name"] for p in config.PEERS}
        b = metrics.counting_basis(raw, table, config.SUBJECT, names, [dates[0], dates[-1]])
        self.assertAlmostEqual(b["venues"][rival]["pair_sum_factor"], 0.5)
        self.assertAlmostEqual(b["venues"][rival]["once_factor"], 1 / 1.8)


class Onchain(unittest.TestCase):
    def test_inflows_are_priced_daily_and_compared(self):
        vols = {p["slug"]: [100.0] * 10 for p in config.PEERS}
        raw, dates = make_raw(10, vols, revenue={config.SUBJECT: [10.0] * 10})
        raw["onchain_revenue"] = {
            "range": [dates[0], dates[-1]], "wallets": ["a.near", "b.near"], "buyback_wallet": "b.near",
            "source": "test", "near_price_usd": {d: 2.0 for d in dates},
            "days": {d: {"a.near": {"near": 3.0, "wnear": 0.0}, "b.near": {"near": 1.0, "wnear": 1.0}}
                     for d in dates}}
        table = metrics.build_table(raw, "2030-01-01T00:00:00Z")
        oc = metrics.onchain_check(raw, table, config.SUBJECT, [dates[0], dates[-1]])
        self.assertAlmostEqual(oc["onchain_usd"], 100.0)     # (3 + 1 + 1) NEAR * $2 * 10 days
        self.assertAlmostEqual(oc["ratio"], 1.0)
        self.assertAlmostEqual(oc["buyback_share"], 0.4)


class Events(unittest.TestCase):
    def test_two_sided_reported_figure_is_recognised(self):
        vols = {p["slug"]: [100.0] * 10 for p in config.PEERS}
        raw, dates = make_raw(10, vols)
        raw["intents_events_x"] = {"day": dates[3], "transactions_in_day": 1000, "sampled": 100,
                                   "both_sides_usd": 95.0, "both_sides_usd_p05": 80.0,
                                   "both_sides_usd_p95": 115.0, "one_side_usd": 47.5}
        table = metrics.build_table(raw, "2030-01-01T00:00:00Z")
        ev = metrics.events_check(raw, table, config.SUBJECT)
        self.assertTrue(ev["both_sides"])
        self.assertAlmostEqual(ev["one_ratio_mean"], 0.475)

    def test_one_sided_reported_figure_is_not_called_two_sided(self):
        vols = {p["slug"]: [100.0] * 10 for p in config.PEERS}
        raw, dates = make_raw(10, vols)
        raw["intents_events_x"] = {"day": dates[3], "transactions_in_day": 1000, "sampled": 100,
                                   "both_sides_usd": 200.0, "both_sides_usd_p05": 170.0,
                                   "both_sides_usd_p95": 230.0, "one_side_usd": 100.0}
        table = metrics.build_table(raw, "2030-01-01T00:00:00Z")
        self.assertFalse(metrics.events_check(raw, table, config.SUBJECT)["both_sides"])

    def test_bigquery_days_are_priced_and_compared(self):
        vols = {p["slug"]: [100.0] * 10 for p in config.PEERS}
        raw, dates = make_raw(10, vols)
        row = lambda day, event, asset, pos, neg, n=1: {"day": day, "event": event, "asset": asset,
                                                         "pos_raw": str(pos), "neg_raw": str(neg), "n": str(n)}
        raw["bq_intents_legs"] = {"dataset": "d", "range": [dates[0], dates[1]], "rows": [
            # day 0: a user gives 50 USDC, a solver gives 0.5 X at $100: $100 both sides
            row(dates[0], "token_diff", "usdc", 0, 50 * 10 ** 6),
            row(dates[0], "token_diff", "x", 0, 5 * 10 ** 17),
            row(dates[0], "transfer", "usdc", 7 * 10 ** 6, 0),
            row(dates[0], "intents_executed", "", 0, 0, 4),
            # day 1: half of it, and a leg in an asset with no price
            row(dates[1], "token_diff", "usdc", 0, 50 * 10 ** 6),
            row(dates[1], "token_diff", "junk", 0, 10 ** 30)]}
        raw["bq_prices"] = {"prices": {
            "usdc": {"stable": True, "decimals": 6, "daily": {}},
            "x": {"stable": False, "decimals": 18, "daily": {dates[0]: 100.0, dates[1]: 100.0}}}}
        table = metrics.build_table(raw, "2030-01-01T00:00:00Z")
        bq = metrics.bq_check(raw, table, config.SUBJECT)
        self.assertAlmostEqual(bq["days"][0]["token_diff_usd"], 100.0)
        self.assertAlmostEqual(bq["days"][0]["transfer_usd"], 7.0)
        self.assertEqual(bq["days"][0]["intents_executed"], 4)
        self.assertAlmostEqual(bq["days"][1]["ratio"], 0.5)
        self.assertEqual(bq["first_day_off"], dates[1])
        self.assertEqual(bq["valid"]["within_5pct"], 1)
        self.assertAlmostEqual(bq["unpriced_leg_share"]["token_diff"], 0.25)


class OnChain(unittest.TestCase):
    def setUp(self):
        vols = {p["slug"]: [100.0] * 10 for p in config.PEERS}
        vols[config.SUBJECT] = [200.0] * 10
        self.raw, self.dates = make_raw(10, vols)
        d = self.dates
        leg = lambda day, asset, neg: {"day": day, "event": "token_diff", "asset": asset,
                                       "pos_raw": "0", "neg_raw": str(neg), "n": "1"}
        flow = lambda day, sc, rc, raw_: {"day": day, "sc": sc, "rc": rc, "asset": "usdc",
                                          "raw": str(raw_), "n": "1"}
        self.raw["bq_intents_legs"] = {"dataset": "d", "range": [d[0], d[9]],
                                       "rows": [leg(x, "usdc", 120 * 10 ** 6) for x in d]}
        # each day: $40 in and $40 out between routers and users (counted),
        # $500 between routers and solvers (the router's hedging, not counted)
        self.raw["bq_intents_flows"] = {"rows": [r for x in d for r in (
            flow(x, "other", "router", 40 * 10 ** 6), flow(x, "router", "other", 40 * 10 ** 6),
            flow(x, "router", "solver", 500 * 10 ** 6), flow(x, "other", "other", 9 * 10 ** 6))]}
        self.raw["bq_prices"] = {"prices": {"usdc": {"stable": True, "decimals": 6, "daily": {}}}}

    def test_routed_swaps_count_both_sides_and_hedging_is_left_out(self):
        table = metrics.build_table(self.raw, "2030-01-01T00:00:00Z")
        bq = metrics.bq_check(self.raw, table, config.SUBJECT)
        self.assertAlmostEqual(bq["days"][0]["routed_usd"], 80.0)
        self.assertAlmostEqual(bq["days"][0]["onchain_usd"], 200.0)
        self.assertAlmostEqual(bq["onchain"]["all"]["mean"], 1.0)

    def test_share_with_on_chain_volume_and_its_lower_reading(self):
        table = metrics.build_table(self.raw, "2030-01-01T00:00:00Z")
        bq = metrics.bq_check(self.raw, table, config.SUBJECT)
        names = {p["slug"]: p["name"] for p in config.PEERS}
        for x in bq["days"]:
            x["onchain_usd"] = 100.0           # chain says half of what is reported
        fac = {p["slug"]: 1.0 for p in config.PEERS}
        fac[config.SUBJECT] = 0.5
        on, low = metrics.shares_onchain(table, config.SUBJECT, names, [self.dates[0], self.dates[9]],
                                         bq, None, fac)
        rivals = 100.0 * (len(config.PEERS) - 1)
        self.assertAlmostEqual(on["share"], 100.0 / (100.0 + rivals))
        self.assertAlmostEqual(low["share"], 50.0 / (50.0 + rivals))
        bq["days"] = bq["days"][1:]             # one window day without BigQuery data
        self.assertIsNone(metrics.shares_onchain(table, config.SUBJECT, names,
                                                 [self.dates[0], self.dates[9]], bq, None, fac))


class MarketTest(unittest.TestCase):
    def test_a_venue_that_was_already_growing_is_not_a_substitute(self):
        days = 40
        dates = [("2026-01-%02d" % (i + 1)) if i < 31 else ("2026-02-%02d" % (i - 30)) for i in range(days)]
        P = {"before": [dates[10], dates[19]], "during": [dates[20], dates[29]],
             "after_1": [dates[30], dates[39]], "after_2": [dates[30], dates[39]]}
        rival = next(p["slug"] for p in config.PEERS if p["slug"] != config.SUBJECT)
        vol = {p["slug"]: [10.0] * days for p in config.PEERS}
        vol[config.SUBJECT] = [10.0] * 20 + [20.0] * 10 + [15.0] * 10   # gains, gives some back
        table = {"dates": dates, **{s: {"volume": v} for s, v in vol.items()}}
        bridge = config.WIDE_PEERS[0]
        grow = {d: float(i) for i, d in enumerate(dates)}                 # steady growth throughout
        raw = {"widevolume_" + bridge["slug"]: {"series": grow}}
        names = {p["slug"]: p["name"] for p in config.PEERS}
        halt = {"periods": P, "rival_slug": rival, "lost_daily": 10.0}
        m = metrics.market_test(raw, table, halt, names)
        by = {r["slug"]: r for r in m["rows"]}
        self.assertTrue(by[config.SUBJECT]["substitute"])
        self.assertAlmostEqual(by[config.SUBJECT]["gave_back"], 0.5)
        self.assertFalse(by[bridge["slug"]]["substitute"])
        self.assertAlmostEqual(by[bridge["slug"]]["diversion_trend_adjusted"], 0.0)


class SealV3(unittest.TestCase):
    def test_lead_and_onchain_ratio_predictions_are_graded(self):
        days = 120
        vols = {p["slug"]: [100.0] * days for p in config.PEERS}
        vols[config.SUBJECT] = [300.0] * days
        raw, dates = make_raw(days, vols)
        saved = config.PREDICTIONS_V3
        try:
            config.PREDICTIONS_V3 = [
                {"id": "Pd", "due": dates[100], "window_days": 2, "metric": "lead_window",
                 "op": ">", "value": 0.0, "text": "d"},
                {"id": "Pe", "due": dates[100], "window_days": 2, "metric": "onchain_ratio_window",
                 "op": "between", "value": [0.9, 1.2], "text": "e"}]
            m = metrics.compute(raw, "2030-01-01T00:00:00Z")
        finally:
            config.PREDICTIONS_V3 = saved
        got = {p["id"]: (p["status"], p["current"]) for p in m["predictions"] if p["seal"] == "v3"}
        self.assertEqual(got["Pd"][0], "MET")
        self.assertAlmostEqual(got["Pd"][1], 200.0 / 600.0)
        self.assertEqual(got["Pe"][0], "PENDING")      # no BigQuery days for the window

    def test_the_sealed_files_match_config(self):
        from pipeline import seal
        self.assertEqual(seal.mismatches(), [])


class Tdx(unittest.TestCase):
    def test_recorded_quote_binds_the_worker_key_and_fails_when_altered(self):
        try:
            from cryptography.hazmat.primitives.asymmetric import ec
        except ImportError:
            self.skipTest("cryptography is not installed")
        import hashlib
        import json
        from pipeline import tdx
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "data", "raw", "tdx_quote.json")
        w = json.load(open(path))["workers"][0]
        q = bytes.fromhex(w["quote_hex"])
        p = tdx.parse_quote(q)
        key = tdx.b58decode(w["worker_public_key"].split(":", 1)[1])
        self.assertEqual(p["body"]["report_data"][:32], hashlib.sha256(key).digest())
        att = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b"\x04" + p["attestation_key"])
        self.assertTrue(tdx.ec_verify(att, p["signature"], p["signed"]))
        self.assertTrue(tdx.chain_ok(tdx.chain(p["pck_chain_pem"])))
        bad = bytearray(q)
        bad[48 + 184] ^= 1                              # one bit of MRTD
        pb = tdx.parse_quote(bytes(bad))
        self.assertFalse(tdx.ec_verify(att, pb["signature"], pb["signed"]))


class Call(unittest.TestCase):
    def out(self, share90, share30, offset, trend):
        return {"trailing": {"share": {config.SUBJECT: share90}},
                "sensitivity": [{"days": 30, "share": share30}],
                "stability": {"latest_share": share30}, "token": {"offset_buyback": offset},
                "capture_trend": [{"capture": c} for c in trend],
                "meta": {"last_day": "2026-11-10"}}

    def test_leading_but_not_capturing_is_watch(self):
        c = metrics.investment_call(self.out(0.58, 0.46, 0.13, [0.2, 0.27]))
        self.assertEqual(c["call"], "WATCH")
        self.assertAlmostEqual(c["revenue_multiple_needed"], 0.5 / 0.13)
        self.assertEqual(c["review_on"], "2026-12-10")

    def test_holding_and_capturing_is_accumulate(self):
        self.assertEqual(metrics.investment_call(self.out(0.6, 0.55, 0.6, [0.2, 0.3]))["call"], "ACCUMULATE")

    def test_lost_lead_or_falling_capture_is_avoid(self):
        self.assertEqual(metrics.investment_call(self.out(0.35, 0.55, 0.6, [0.2, 0.3]))["call"], "AVOID")
        self.assertEqual(metrics.investment_call(self.out(0.6, 0.55, 0.6, [0.3, 0.2]))["call"], "AVOID")


class Tee(unittest.TestCase):
    def test_tee_output_is_compared_with_the_build(self):
        trailing = {"volume": {"near-intents": 60e6, "thorchain-dex": 40e6}, "share": {"near-intents": 0.6}}
        basis = {"venues": {"thorchain-dex": {"once_factor": 0.5}}}
        raw = {"tee_run": {"request_tx": "x", "sender": "a.near", "block_height": 1, "request_id": 7,
                           "wasm_sha256": "ab" * 32, "resources": {"instructions": 5},
                           "checks": {"code_hash_is_our_build": True}, "worker": {"signer_id": "w.near"},
                           "output": {"from_ts": 1786579200, "to_ts": 1794268800, "share_reported": 0.6004,
                                      "once_thorchain": 0.5, "once_maya": 1.0,
                                      "volume_musd": {"near-intents": 60.0, "thorchain-dex": 40.0}}}}
        t = metrics.tee_check(raw, trailing, basis, ["2026-08-13", "2026-11-10"])
        self.assertTrue(t["same_window"])
        self.assertAlmostEqual(t["share_diff"], 0.0004)
        self.assertEqual([r["build_musd"] for r in t["volumes"]], [60.0, 40.0])


class Token(unittest.TestCase):
    def test_prediction_run_counts_only_on_its_days_after_they_end(self):
        import datetime
        vols = {p["slug"]: [100e6] * 10 for p in config.PEERS}
        raw, dates = make_raw(10, vols)
        ts = lambda d: int(datetime.datetime.fromisoformat(d).replace(tzinfo=datetime.timezone.utc).timestamp())
        pred = {"id": "P4", "due": dates[5], "window_days": 2, "value": 0.40}
        raw["tee_run_p4"] = {"request_tx": "t", "block_height": 1, "checks": {"a": True},
                             "block_time_ns": str((ts(dates[5]) + 86400 + 3600) * 10 ** 9),
                             "output": {"from_ts": ts(dates[4]), "to_ts": ts(dates[5]),
                                        "share_reported": 0.25,
                                        "volume_musd": {p["slug"]: 200.0 for p in config.PEERS}}}
        table = metrics.build_table(raw, "2030-01-01T00:00:00Z")
        tp = metrics.tee_prediction_check(raw, table, pred)
        self.assertTrue(tp["right_days"] and tp["after_due_day"] and tp["volumes_agree"])
        self.assertEqual(tp["status"], "MISSED")
        raw["tee_run_p4"]["block_time_ns"] = str((ts(dates[5]) + 3600) * 10 ** 9)
        self.assertFalse(metrics.tee_prediction_check(raw, table, pred)["after_due_day"])

    def test_buyback_is_compared_with_net_new_supply(self):
        raw = {"near_supply": {"points": [
                   {"day": "2025-08-13", "total_supply_near": 100.0},
                   {"day": "2025-11-11", "total_supply_near": 120.0},
                   {"day": "2026-08-13", "total_supply_near": 1000.0},
                   {"day": "2026-11-11", "total_supply_near": 1010.0}]},
               "onchain_revenue": {"buyback_wallet": "b.near", "days": {
                   "2026-09-01": {"b.near": {"near": 2.0, "wnear": 0.0}, "a.near": {"near": 1.0, "wnear": 1.0}},
                   "2027-01-01": {"b.near": {"near": 50.0, "wnear": 0.0}}}}}
        t = metrics.token_check(raw, ["2026-08-13", "2026-11-10"])
        self.assertAlmostEqual(t["net_issued_near"], 10.0)
        self.assertAlmostEqual(t["net_issued_prior_near"], 20.0)
        self.assertAlmostEqual(t["offset_buyback"], 0.2)
        self.assertAlmostEqual(t["offset_captured"], 0.4)
        self.assertAlmostEqual(t["multiple_to_offset"], 2.5)


class ShortPredictions(unittest.TestCase):
    def test_window_predictions_are_graded_once_the_due_day_is_in_the_data(self):
        days = 120
        vols = {p["slug"]: [100.0] * days for p in config.PEERS}
        vols[config.SUBJECT] = [300.0] * days          # 300 of 600 = 50%
        fees = {p["slug"]: [0.0] * days for p in config.PEERS}
        fees[config.SUBJECT] = [0.6] * days            # 20 bps
        raw, dates = make_raw(days, vols, fees)
        saved = config.PREDICTIONS_V2
        try:
            config.PREDICTIONS_V2 = [
                {"id": "Pa", "due": dates[100], "window_days": 2, "metric": "share_window",
                 "op": ">=", "value": 0.40, "text": "a"},
                {"id": "Pb", "due": dates[100], "window_days": 2, "metric": "take_rate_window_bps",
                 "op": ">=", "value": 25.0, "text": "b"},
                {"id": "Pc", "due": "2099-01-01", "window_days": 2, "metric": "share_window",
                 "op": ">=", "value": 0.40, "text": "c"}]
            m = metrics.compute(raw, "2030-01-01T00:00:00Z")
        finally:
            config.PREDICTIONS_V2 = saved
        got = {p["id"]: (p["status"], p["current"]) for p in m["predictions"] if p["seal"] == "v2"}
        self.assertEqual(got["Pa"][0], "MET")
        self.assertAlmostEqual(got["Pa"][1], 0.5)
        self.assertEqual(got["Pb"][0], "MISSED")
        self.assertEqual(got["Pc"][0], "PENDING")


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

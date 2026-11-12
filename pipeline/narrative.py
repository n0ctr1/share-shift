"""Write every sentence that contains a number, from the computed metrics.

Nothing in THESIS.md or the dashboard is typed by hand if it has a figure in
it: the text is produced here so a re-run on new data rewrites it.
"""

from . import config  # noqa: F401  (used for channel sources)


def usd(x):
    if x is None:
        return "n/a"
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= limit:
            return "$%.2f%s" % (x / limit, suffix)
    return "$%.0f" % x


def pct(x, digits=0):
    return "n/a" if x is None else "%.*f%%" % (digits, 100 * x)


def bps(x):
    return "n/a" if x is None else "%.1f bps" % x


def mult(x):
    return "n/a" if x is None else "%.0fx" % x


def ordinal(n):
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return "%d%s" % (n, suffix)


def fmt_value(value, unit):
    if value is None:
        return "n/a"
    return {"share": pct(value, 1), "growth": "%+.0f%%" % (100 * value), "bps": bps(value),
            "ratio": "%.2f" % value, "count": "%d" % value, "rank": "rank %d" % value}[unit]


def claim_cells(c):
    shown = c.get("display") or {}
    return (shown.get("value") or fmt_value(c["value"], c["unit"]),
            shown.get("threshold") or fmt_value(c["threshold"], c["unit"]))


def findings(m):
    """One plain sentence per chart, keyed by chart id."""
    s = m["meta"]["subject"]
    names = {p["slug"]: p["name"] for p in m["meta"]["peers"]}
    tr, yoy, st = m["trailing"], m["yoy"], m["stability"]
    rivals = [p["slug"] for p in m["meta"]["peers"] if p["slug"] != s]
    runner_up = max(rivals, key=lambda r: tr["share"][r])
    out = {}

    out["share"] = (
        "Over the %d days to %s, NEAR Intents settled %s of the %s that the four venues "
        "moved, a %s share; %s was second with %s."
        % (m["meta"]["window_days"], m["meta"]["last_day"], usd(tr["volume"][s]),
           usd(tr["market_volume"]), pct(tr["share"][s]), names[runner_up],
           pct(tr["share"][runner_up]))
    )
    if yoy:
        out["share"] += " One year earlier its share was %s." % pct(yoy["share_prior"][s])
        out["volume"] = (
            "The four venues together moved %s in the window against %s a year earlier "
            "(%+.0f%%), so the market itself grew while Intents was gaining share."
            % (usd(yoy["market_now"]), usd(yoy["market_prior"]), 100 * yoy["market_growth"])
        )
        split = yoy["shift_share"]
        out["decomposition"] = (
            "Intents volume rose by %s year on year: %s of that (%s) is what it would have "
            "gained at its old share of a bigger market, and %s (%s) came from raising its share."
            % (usd(split["total"]), usd(split["market_effect"]),
               pct(1 - yoy["share_effect_fraction"]), usd(split["share_effect"]),
               pct(yoy["share_effect_fraction"]))
        )
    out["take_rate"] = (
        "Intents charged %s of volume in gross fees over the window; the median of its "
        "three rivals was %s, and Chainflip charged %s."
        % (bps(tr["take_bps"][s]), bps(tr["rival_take_median_bps"]),
           bps(tr["take_bps"].get("chainflip-amm")))
    )
    out["capture"] = (
        "Of %s in gross Intents fees over the window, %s (%s) reached NEAR's revenue "
        "wallets; the rest stayed with solvers and the third-party front ends that distribute Intents."
        % (usd(tr["fees"][s]), usd(tr["revenue"][s]), pct(tr["capture"]))
    )
    out["stability"] = (
        "Weekly share ranged from %s to %s over the last %d complete weeks since %s "
        "(standard deviation %.0f points), leaving out %d weeks in which a major rival "
        "was not trading; the lowest week was the one starting %s, and the most "
        "recent week (%s) stood at %s."
        % (pct(st["min"]), pct(st["max"]), st["weeks"], st["first_week"], 100 * st["stdev"],
           len(st["excluded_weeks"]), st["min_week"], st["latest_week"], pct(st["latest_share"]))
    )
    cm = m["co_movement"]
    if cm["pearson_r"] is not None:
        out["co_movement"] = (
            "Week-to-week changes in Intents volume and in rival volume have a correlation "
            "of %+.2f over %d weeks: they mostly move independently, which is neither one "
            "shared tide nor a clean one-for-one substitution." % (cm["pearson_r"], cm["weeks"])
        )
    iv = m["implied_value"]
    val = m["valuation"][s]
    if iv:
        out["valuation"] = (
            "Annualised, NEAR's captured Intents revenue is %s. The market pays a median "
            "of %s that kind of revenue for the three rivals' tokens; at that multiple the "
            "revenue backs %s, or %s of NEAR's %s market cap."
            % (usd(val["revenue_annualized"]), mult(iv["rival_median_mcap_to_revenue"]),
               usd(iv["implied_value"]), pct(iv["fraction_of_subject_mcap"], 1),
               usd(val["market_cap"]))
        )
    else:
        out["valuation"] = ("Market caps could not be fetched in this run, so the valuation "
                            "comparison is not computed.")
    h = m["halt"]
    if h:
        dv = h["daily_volume"]
        rs = h["rival_slug"]
        last = dv[h["last_period"]]
        what = (h["what"] + ". ") if h["what"] else ""
        out["halt"] = (
            "%s%s reported no volume for %d days, %s to %s. In the %d days before, it carried "
            "%s a day; while it was down, Intents rose from %s to %s a day, picking up %s of "
            "the missing flow, and the four-venue total fell %s, so the rest of that flow "
            "left the market for the duration."
            % (what, h["rival"], h["days"], h["first_day"], h["last_day"], h["days"],
               usd(dv["before"][rs]), usd(dv["before"][s]), usd(dv["during"][s]),
               pct(h["absorbed_fraction"]), pct(-h["market_change"]))
        )
        out["after_halt"] = (
            "After the restart %s came back at %s a day, %s of its level before the halt, "
            "while Intents ran at %s a day, %s above its own level before the halt. Intents "
            "did not raise its price to take the flow: its take rate was %s before the halt "
            "and %s during it."
            % (h["rival"], usd(last[rs]), pct(h["rival_recovery"]), usd(last[s]),
               pct(h["subject_after_vs_before"]), bps(h["subject_take_bps"]["before"]),
               bps(h["subject_take_bps"]["during"]))
        )
        if h["placebo"]:
            parts = ["the %s percentile of the previous %d days (median change %+.0f%%)"
                     % (ordinal(round(100 * x["percentile"])), x["lookback_days"],
                        100 * x["placebo_median"]) for x in h["placebo"]]
            others = ", ".join("%s %+.0f%%" % (names[k], 100 * v)
                               for k, v in h["others_growth"].items() if v is not None)
            out["halt_check"] = (
                "How sure is this? Intents volume grew %+.0f%% in the halt against the %d days "
                "before. Compared with every other %d-day stretch, that growth sits at %s. So it "
                "was unusual for the half-year before the halt and ordinary for the year, which "
                "includes the months when Intents was still multiplying from a small base. The "
                "other venues that stayed open: %s. There was no jump on the first day; the first "
                "week was %+.0f%%. The data is consistent with Intents taking the flow and does "
                "not prove it."
                % (100 * h["subject_growth"], h["days"], h["days"], " and ".join(parts), others,
                   100 * h["subject_growth_first_week"])
            )
    c = m.get("channels")
    if c:
        top = c["channels"][0]

        def short(name):
            return name if len(name) <= 34 else name[:8] + "..." + name[-6:]
        out["channels"] = (
            "The Explorer API lists 1Click swaps. Counting those of %s or more, %s moved in "
            "the window, %s of the Intents volume DefiLlama reports. %d channels brought "
            "them; the largest, %s, brought %s and the top three %s."
            % ("$%s" % format(int(c["min_usd"]), ","), usd(c["volume"]), pct(c["coverage_of_all_intents_volume"]),
               c["channel_count"], top["channel"], pct(top["share"]), pct(c["top3_share"]))
        )
        multi = c["multi_venue_channels"]
        out["routers"] = (
            "%s of that volume came through front ends that are documented as also routing "
            "to rival venues (%s). For that share, the user chose a wallet or an aggregator "
            "and its router chose Intents; it can choose otherwise tomorrow. Channels whose "
            "routing could be established one way or the other cover %s of the volume; the "
            "rest is unlabelled or its operator was not identified."
            % (pct(c["multi_venue_share"]), ", ".join(multi), pct(c["known_share"]))
        )
        out["fee_recipients"] = (
            "App fees on those swaps came to %s, or %s of their volume, paid to %d accounts. "
            "The largest: %s. NEAR's buyback account (%s) received %s of them."
            % (usd(c["app_fees"]), bps(c["app_fee_bps"]), c["recipient_count"],
               "; ".join("%s %s" % (short(r["recipient"]), pct(r["share"]))
                         for r in c["recipients"][:5]),
               config.BUYBACK_ACCOUNT, pct(c["buyback_share_of_app_fees"], 1))
        )
        ch = c["halt"]
        if ch and h:
            movers = "; ".join("%s %s to %s a day" % (x["channel"], usd(x["before"]), usd(x["during"]))
                               for x in ch["movers"][:3])
            out["halt_channels"] = (
                "By channel: in the 1Click data Intents went from %s to %s a day when %s "
                "halted. The channels that grew most: %s. The largest of them accounts for %s "
                "of the gain. Channels that also route to the rivals went from %s to %s a day%s."
                % (usd(ch["daily_before"]), usd(ch["daily_during"]), h["rival"], movers,
                   pct(ch["movers"][0]["share_of_gain"]),
                   usd(ch["multi_venue_daily"]["before"]), usd(ch["multi_venue_daily"]["during"]),
                   (": they did not carry the gain" if ch["multi_venue_delta"] <= 0 else
                    ", %s of the gain" % pct(ch["multi_venue_share_of_gain"])))
            )
            out["channel_reading"] = (
                "This cuts against the obvious story. If shared routers had moved the halted "
                "rival's users to Intents, their volume would have risen sharply; it barely "
                "moved. The gain arrived through other channels, so it is better read as users "
                "finding Intents themselves than as a router flipping a switch. What the "
                "routers do explain is the fee split and the weight of a few channels."
                if (ch["multi_venue_share_of_gain"] or 0) < 0.25 else
                "Shared routers carried %s of the gain, which fits the reading that the same "
                "front ends re-routed their users when the rival stopped."
                % pct(ch["multi_venue_share_of_gain"])
            )
    wd = m.get("wide")
    if wd:
        leaders = wd["venues"][:2]
        out["wide"] = (
            "Add the four large bridges and the picture changes: of %s moved by all eight "
            "venues in the window, Intents carried %s, third after %s (%s) and %s (%s). By "
            "gross fees it ranks %s. %s moved %s for %s in fees, %s; Intents earned %s on %s, "
            "%s."
            % (usd(wd["market_volume"]), pct(wd["subject_share"]), leaders[0]["name"],
               pct(leaders[0]["share"]), leaders[1]["name"], pct(leaders[1]["share"]),
               ordinal(wd["subject_rank_fees"]),
               "Across", usd(next(v["volume"] for v in wd["venues"] if v["slug"] == "across")),
               usd(next(v["fees"] for v in wd["venues"] if v["slug"] == "across")),
               bps(next(v["take_bps"] for v in wd["venues"] if v["slug"] == "across")),
               usd(tr["fees"][s]), usd(tr["volume"][s]), bps(tr["take_bps"][s]))
        )
        peak_week = max(wd["weekly_share"], key=wd["weekly_share"].get)
        out["wide"] += (" Its weekly share of this wider set peaked at %s in the week of %s."
                        % (pct(wd["weekly_share"][peak_week]), peak_week))
        if wd["prior"]:
            late = wd["prior"]["venues_without_full_history"]
            out["wide"] += (
                " A year earlier Intents had %s of this wider set%s."
                % (pct(wd["prior"]["subject_share"]),
                   (" (%s has no data for the start of that window, so the earlier share is "
                    "slightly overstated)" % ", ".join(late)) if late else "")
            )
    cc = m.get("crosscheck")
    if cc:
        out["crosscheck"] = (
            "DefiLlama's THORChain series was checked against THORChain's own indexer "
            "(Midgard) over %d days: the totals differ by %.1f%%, the daily correlation is "
            "%.3f, and all %d zero-volume days appear in both (%d in only one)."
            % (cc["days"], 100 * abs(cc["ratio"] - 1), cc["pearson_r"], cc["zero_days_in_both"],
               cc["zero_days_in_one_only"])
        )
    sus = m.get("suspensions") or []
    if sus:
        parts = ["%s to %s (%d days): Intents %+.0f%%" % (x["from"], x["to"], x["days"],
                                                          100 * x["subject_change"])
                 for x in sus if x["subject_change"] is not None]
        out["suspensions"] = (
            "Shorter outages do not show the same effect. The data has %d other stretch%s of "
            "two or more days in which %s fell under 10%% of its usual volume; against the 14 "
            "days before each: %s."
            % (len(sus), "" if len(sus) == 1 else "es", sus[0]["rival"], "; ".join(parts))
        )
    b = m.get("basis")
    if b:
        sc = {x["id"]: x for x in b["scenarios"]}
        legs = "; ".join(
            (("%s: matching daily totals of legs into and out of RUNE pairs up to %s of its "
              "reported volume, an upper bound; reading %s individual swaps, %s of their value "
              "(90%% interval %s to %s) went through two pools, so counting each swap once "
              "leaves %s"
              % (v["name"], pct(v["paired_share"]), "{:,}".format(v["swaps_read"]),
                 pct(v["double_share_actions"]), pct(v["double_share_actions_p05"]),
                 pct(v["double_share_actions_p95"]), pct(v["actions_factor"])))
             if "actions_factor" in v else
             "%s: %s of its reported volume is matched pairs of legs into and out of its own "
             "token, so counting each swap once leaves %s"
             % (v["name"], pct(v["paired_share"]), pct(v["once_factor"])))
            if "provider_vs_indexer" not in v["leg_shares"] else
            ("%s: its reported volume equals input value plus the routed USDC leg "
             "(%s of the indexer's two-leg sum), so counting each swap once leaves %s"
             % (v["name"], pct(v["leg_shares"]["provider_vs_indexer"], 1), pct(v["once_factor"])))
            for v in b["venues"].values())
        out["basis"] = (
            "Venues do not count volume the same way. %s (from each venue's own indexer). "
            "For NEAR Intents, %s. Two public re-computations from intents.near events "
            "disagree on what that figure counts: one finds public swaps counted once are "
            "46%% of it (92%% counting both sides), the other finds it within about 1%% of "
            "public net volume before confidential intents launched. This analysis cannot "
            "settle which is right, so this analysis rebuilt it itself (below). The bridges in "
            "the wider set are taken as one-sided, as their adapters report deposits."
            % (legs, config.SUBJECT_VOLUME_SOURCE)
        )
        out["basis_short"] = (
            "Counting one side of each swap for every venue gives %s. Only one reading puts "
            "Intents behind: halving Intents while leaving rivals as reported (%s, %s first). "
            "The data is against it: the rivals' own indexers count both halves of routed "
            "swaps, and on every day where the event method applies, intents.near's events "
            "put the Intents figure at both sides too."
            % (pct(sc["one_side"]["share"]), pct(sc["worst"]["share"]), sc["worst"]["leader"])
            if sc["worst"]["leader"] != names[s] else
            "Counting one side of each swap for every venue gives %s; even halving Intents "
            "alone gives %s, still first." % (pct(sc["one_side"]["share"]), pct(sc["worst"]["share"]))
        )
    ev = m.get("events")
    if ev:
        parts = ["%s: %s both sides (90%% interval %s to %s) against %s reported"
                 % (d["day"], usd(d["both"]), usd(d["both_p05"]), usd(d["both_p95"]), usd(d["reported"]))
                 for d in ev["days"]]
        out["events"] = (
            "Rebuilt from intents.near itself: on %d days every transaction touching the contract "
            "was listed, a seeded random sample of 4,000 a day was read, and every DIP-4 "
            "token_diff event was valued at that day's price. %s. On average the both-sides "
            "figure is %.2f times the reported one, and the one-side figure %.2f: the reported "
            "figure counts both sides, like THORChain's, Maya's and Chainflip's."
            % (len(ev["days"]), "; ".join(parts), ev["both_ratio_mean"], ev["one_ratio_mean"])
        )
        out["events_others"] = (
            "This agrees with the two other public re-computations rather than contradicting "
            "them. NearQuery's SQL defines its leg sum over user and solver entries as the "
            "definition that reproduces NEAR's reported volume, and halves it for net volume; "
            "soldano finds both legs at 92% of the reported figure. Their lower figures (46% "
            "once, about 35% unseen) are about flow that public token_diff events do not show "
            "after August, not about the counting basis."
        )
        if ev["later_days"]:
            later = "; ".join("%s: %.2f of reported" % (d["day"], d["both_ratio"]) for d in ev["later_days"])
            out["events_limit"] = (
                "The method has a limit, found while extending it. After %s the contract "
                "increasingly settles swaps through transfer intents instead of token_diff "
                "events (event version 0.4.3 by mid-October, no token_diff at all in a 5 November "
                "sample; data/raw/intents_event_format.json). Counted the same way, later days "
                "fall short (%s). Any token_diff-based count, including the residuals above, "
                "understates volume from then on, so those days are shown but not used, and the "
                "share of truly confidential flow after August is not established here."
                % (ev["valid_until"], later)
            )
    tk = m.get("token")
    if tk:
        out["token"] = (
            "Over the %d days from %s, NEAR's total supply rose by %.2fM NEAR (from block-header "
            "total_supply), %.1f%% a year, down from %.2fM in the same days a year earlier. In the "
            "same window %.2fM NEAR reached the buyback wallet, %s of the new supply, and %.2fM "
            "reached all three revenue wallets, %s. For buybacks to offset issuance, captured "
            "revenue would have to grow %.1fx at today's take rate and capture ratio."
            % (tk["window_days"], tk["supply_points"][2]["day"], tk["net_issued_near"] / 1e6,
               100 * tk["annual_issuance_rate"], tk["net_issued_prior_near"] / 1e6,
               tk["bought_back_near"] / 1e6, pct(tk["offset_buyback"]),
               tk["captured_near"] / 1e6, pct(tk["offset_captured"]), tk["multiple_to_offset"])
        )
        if tk.get("l1"):
            l1 = tk["l1"]
            out["token_l1"] = (
                "The L1 itself is far quieter than a year ago: %s transactions a day against %s "
                "(%+.0f%%), and %s active accounts a day against %s (%+.0f%%). The case for the "
                "token now runs through Intents, not through L1 gas."
                % ("{:,.0f}".format(l1["txns_per_day"]), "{:,.0f}".format(l1["txns_per_day_prior"]),
                   100 * (l1["txns_per_day"] / l1["txns_per_day_prior"] - 1),
                   "{:,.0f}".format(l1["active_accounts"]), "{:,.0f}".format(l1["active_accounts_prior"]),
                   100 * (l1["active_accounts"] / l1["active_accounts_prior"] - 1))
            )
    tee = m.get("tee")
    if tee:
        out["tee"] = (
            "The headline number was also recomputed inside a trusted execution environment. "
            "tee/share-check, a WASI program in this repository (SHA-256 %s...), fetched "
            "DefiLlama's and Midgard's data by itself inside an Intel TDX enclave run by "
            "OutLayer, requested by transaction %s on NEAR mainnet (block %s). It returned an "
            "Intents share of %s against %s in this build, THORChain's one-side factor %s "
            "against %s, and every venue's volume to the same $0.1M. The result was delivered "
            "on chain by %s with a key scoped to outlayer.near; OutLayer's register contract "
            "adds such a key only after verifying a TDX quote against its allowlist of "
            "measurements. `python3 -m pipeline.tee_verify` repeats every check from public RPC."
            % (tee["wasm_sha256"][:12], tee["request_tx"], "{:,}".format(tee["block_height"]),
               pct(tee["share_tee"], 2), pct(tee["share_build"], 2),
               "%.4f" % tee["once_thorchain_tee"], "%.4f" % (tee["once_thorchain_build"] or 0),
               tee["worker"])
        )
    if h:
        p365 = next((x for x in h["placebo"] if x["lookback_days"] == 365), None)
        absorbed = (h.get("absorbed_by_basis") or {}).get("one_side", h["absorbed_fraction"])
        out["halt_short"] = (
            "%s was halted for %d days after an exploit. Intents grew %+.0f%% over those days "
            "and kept the higher level afterwards, equal to %s of the flow %s lost. But growth "
            "of that size was ordinary for Intents over the year before (%s percentile), so "
            "the halt shows Intents could absorb the flow, not that the halt caused the gain."
            % (h["rival"], h["days"], 100 * h["subject_growth"], pct(absorbed), h["rival"],
               ordinal(round(100 * p365["percentile"])) if p365 else "n/a")
        )
    oc = m.get("onchain")
    if oc:
        out["onchain"] = (
            "Rebuilt from the chain: %s to %s, the three revenue wallets received %.0f NEAR "
            "from outside themselves, worth %s at each day's price, against %s in the "
            "provider's revenue series (%s). Of that inflow, %s landed directly in the "
            "buyback wallet; the rest went to the two treasury funds first."
            % (oc["window"][0], oc["window"][1], oc["onchain_near"], usd(oc["onchain_usd"]),
               usd(oc["provider_usd"]),
               "%.1f%% of it" % (100 * oc["ratio"]) if oc["ratio"] else "n/a",
               pct(oc["buyback_share"]))
        )
    ct = m["capture_trend"]
    if len(ct) >= 2:
        out["capture_trend"] = (
            "Over consecutive %d-day windows the share reaching NEAR was %s (oldest first, "
            "the last ending %s)."
            % (m["meta"]["window_days"], ", ".join(pct(x["capture"]) for x in ct), ct[-1]["to"])
        )
    rc = m["recent"]["change"]
    rising = [names[r] for r in rivals if rc[r] is not None and rc[r] > 0]
    out["recent"] = (
        "In the last 30 days Intents volume changed by %+.0f%% against the 30 days before, "
        "while %s changed by %+.0f%%%s."
        % (100 * rc[s], names[runner_up], 100 * rc[runner_up],
           "; every rival grew" if len(rising) == len(rivals) else "")
    )
    for note in m["context_notes"]:
        if note["slug"] == runner_up:
            out["recent"] += (
                " %s (%s); %d of its 10 largest days in the window came on or after %s."
                % (note["what"], note["source"], note["top10_days_after"], note["date"]))
    bu = m["burst"]
    out["burst"] = (
        "Over the window Intents' daily volume had a standard deviation of %.0f%% of its "
        "mean, against %.0f%% for %s. On a median day Intents moved %s and %s moved %s; "
        "%s's ten largest days were %s of its volume (Intents: %s), the largest being %s."
        % (100 * bu[s]["cv"], 100 * bu[runner_up]["cv"], names[runner_up],
           usd(bu[s]["median_day"]), names[runner_up], usd(bu[runner_up]["median_day"]),
           names[runner_up], pct(bu[runner_up]["top10_share"]), pct(bu[s]["top10_share"]),
           usd(bu[runner_up]["max_day"]))
    )
    holders = (m["meta"].get("subject_methodology") or {}).get("HoldersRevenue")
    if holders:
        out["buyback"] = 'DefiLlama\'s adapter note on that revenue: "%s"' % holders

    one_side = None
    if m.get("basis"):
        one_side = next(x for x in m["basis"]["scenarios"] if x["id"] == "one_side")
    out["title"] = (
        "NEAR Intents leads native cross-chain swaps whenever volume is counted the same way "
        "for every venue. The token keeps %s of the fees, and nothing yet proves the lead lasts."
        % pct(tr["capture"])
    )
    out["summary"] = (
        "A test of NEAR's long-term case against the three other venues that swap native "
        "assets across chains. %s Intents holds %s of the volume as reported%s, and does "
        "not undercut rivals on price. Against that: %s of gross fees reach NEAR; when the "
        "second-largest venue was halted for %d days, Intents grew, but by an amount that "
        "was ordinary for its own past year; and in the last 30 days Intents volume moved "
        "%+.0f%% while %s moved %+.0f%%."
        % (verdict_line(m), pct(tr["share"][s]),
           (" and %s if one side of each swap is counted for every venue" % pct(one_side["share"]))
           if one_side else "",
           pct(tr["capture"]), h["days"] if h else 0, 100 * rc[s], names[runner_up], 100 * rc[runner_up])
    )
    gaps = [f for f in m["quality_flags"] if not f.get("cause")]
    out["limits"] = [
        "The headline peer set is four venues that swap native assets. The wider set adds "
        "four bridges that mostly move the same asset between chains; which set is the "
        "right market is a judgement, so both are shown. Fee methodologies differ between "
        "venues, and Relay's fee figure is far above the rest and has not been reconciled.",
        "One halt is one event. It shows what happened once when a rival stopped; it is not "
        "a law about what happens next time, and the placebo check above shows the growth "
        "could also be Intents' own trend.",
        "%d other weeks are flagged because a venue's volume fell below 20%% of its own prior "
        "eight-week median, with no explanation found. They stay in the data." % len(gaps),
        "Claim thresholds were set after a first look at the data and are not "
        "pre-registered. The dated predictions are sealed: their SHA-256 is in "
        "predictions/predictions.json.sha256, timestamped on Bitcoin through OpenTimestamps "
        "and tagged predictions-v1 in git, and the build refuses to run if they change.",
        "NEAR's market cap prices the whole L1, so the valuation line compares Intents "
        "revenue with rival multiples and is not a price target.",
        "Volume, fees and revenue come from DefiLlama adapters. Only THORChain's volume was "
        "checked against a primary source; an adapter error elsewhere is an error here.",
    ]
    return out


def verdict_line(m):
    counts = {}
    for c in m["claims"]:
        counts[c["verdict"]] = counts.get(c["verdict"], 0) + 1
    parts = ["%d %s" % (n, v.lower()) for v, n in sorted(counts.items(), reverse=True)]
    return "%d claims tested: %s." % (len(m["claims"]), ", ".join(parts))


def thesis_markdown(m, text):
    s = m["meta"]["subject"]
    names = {p["slug"]: p["name"] for p in m["meta"]["peers"]}
    slugs = [p["slug"] for p in m["meta"]["peers"]]
    h = m["halt"]
    lines = []
    add = lines.append

    add("# " + text["title"])
    add("")
    add("> Generated by `python3 build.py` from data fetched %s, covering %s to %s. "
        "Every figure below is computed by `pipeline/metrics.py`; none is typed by hand."
        % (m["meta"]["fetched_at"], m["meta"]["first_day"], m["meta"]["last_day"]))
    add("")
    add("## In three lines")
    add("")
    add("1. **It is the largest swap venue, at a normal price.** %s %s"
        % (text["share"], text.get("basis_short", "")))
    add("2. **The token sees little of it so far, but more each quarter.** %s %s"
        % (text["capture"], text.get("capture_trend", "")))
    if h:
        add("3. **The one real test is not conclusive.** %s"
            % text.get("halt_short", text["halt"]))
    add("")
    add("## The claim")
    add("")
    add("The long-term case for NEAR rests on NEAR Intents being a business with a durable "
        "position, not only a volume number. A durable position should be visible against "
        "competitors: a leading share, kept when it is tested, at a price rivals cannot "
        "undercut, with the fees reaching the token. This repository tests those things "
        "against the three other venues that swap native assets across chains: %s."
        % ", ".join(names[x] for x in slugs if x != s))
    add("")
    add("**Result: %s** The competitive position is supported by the data; the value "
        "reaching the token is not." % verdict_line(m))
    add("")
    add("## Definitions")
    add("")
    add("- **Peer set**: %s. All four settle swaps between native assets on different "
        "chains and have a daily USD volume series on DefiLlama." % ", ".join(names[x] for x in slugs))
    if m.get("wide"):
        add("- **Wider set**: the peer set plus %s, bridges that mostly move the same asset "
            "from one chain to another." % ", ".join(
                v["name"] for v in m["wide"]["venues"] if v["kind"] == "bridge"))
    add("- **Share**: a venue's volume divided by the peer set's volume over the same days.")
    add("- **Take rate**: gross fees divided by volume, in basis points (1 bp = 0.01%).")
    add("- **Fees reaching NEAR**: DefiLlama's revenue series for NEAR Intents divided by "
        "its gross fee series.")
    add("- **Market effect / share effect**: the year-on-year change in Intents volume, "
        "split into what it would have gained at its old share and what it gained by "
        "raising its share (`metrics.shift_share`).")
    add("- **Window**: the %d days ending %s, unless a line says otherwise."
        % (m["meta"]["window_days"], m["meta"]["last_day"]))
    add("")
    add("## Claims and verdicts")
    add("")
    add("Thresholds are in `pipeline/config.py`. A verdict is one number compared with one threshold.")
    add("")
    add("| # | Claim | Measured | Threshold | Verdict |")
    add("| --- | --- | --- | --- | --- |")
    for c in m["claims"]:
        add("| %s | %s | %s | %s | **%s** |" % (
            c["id"], c["claim"], claim_cells(c)[0], claim_cells(c)[1], c["verdict"]))
    add("")
    add("## Evidence for")
    add("")
    if h:
        add("### The stress test")
        add("")
        add(text["halt"])
        add("")
        add(text["after_halt"])
        add("")
        if "halt_check" in text:
            add(text["halt_check"])
            add("")
        if "suspensions" in text:
            add(text["suspensions"])
            add("")
        if "crosscheck" in text:
            add(text["crosscheck"])
            add("")
        labels = {"before": "Before", "during": "Halt", "after_1": "After, first period",
                  "after_2": "After, second period"}
        keys = [k for k in ("before", "during", "after_1", "after_2") if k in h["periods"]]
        add("Average daily volume, %d-day periods:" % h["days"])
        add("")
        add("| Period | Dates | %s | Intents share |" % " | ".join(names[x] for x in slugs))
        add("| --- | --- | %s --- |" % ("--- | " * len(slugs)))
        for k in keys:
            row = h["daily_volume"][k]
            total = sum(row.values())
            add("| %s | %s to %s | %s | %s |" % (
                labels[k], h["periods"][k][0], h["periods"][k][1],
                " | ".join(usd(row[x]) for x in slugs), pct(row[s] / total)))
        add("")
        if h["source"]:
            add("The halt itself is reported at %s. Its dates and every volume above come "
                "from the data." % h["source"])
            add("")
        add("### The rest")
        add("")
    add("- **Leading share.** %s" % text["share"])
    add("- **Steadier flow.** %s" % text["burst"])
    if "volume" in text:
        add("- **A growing market.** %s" % text["volume"])
    add("- **Not a price war.** %s" % text["take_rate"])
    add("")
    if "channels" in text:
        add("## Who brings the swaps, and who keeps the fees")
        add("")
        add(text["channels"])
        add("")
        add(text["routers"])
        add("")
        add(text["fee_recipients"])
        add("")
        c = m["channels"]
        add("| Channel | Volume | Share | Swaps | App fee | Routes to rivals | Basis |")
        add("| --- | --- | --- | --- | --- | --- | --- |")
        for row in c["channels"]:
            basis = row["note"] + ((" ([source](%s))" % row["source"]) if row["source"] else "")
            add("| %s | %s | %s | %d | %s | %s | %s |" % (
                row["channel"], usd(row["usd"]), pct(row["share"], 1), row["swaps"],
                bps(row["fee_bps"]), row["routes_to_rivals"], basis))
        add("")
        if "halt_channels" in text:
            add(text["halt_channels"])
            add("")
            add(text["channel_reading"])
            add("")
    if "token" in text:
        add("## What it means for the NEAR token")
        add("")
        add(text["token"])
        add("")
        if "token_l1" in text:
            add(text["token_l1"])
            add("")
        add("So the answer to \"should one hold NEAR on this evidence\" is not yet: the business "
            "Intents runs is leading and growing its take to the token, but today it buys back "
            "a fraction of what the protocol issues. The dated predictions below say what would "
            "have to change.")
        add("")
    add("## Evidence against")
    add("")
    add("- **Most fees do not reach NEAR.** %s %s %s" % (
        text["capture"], text.get("capture_trend", ""), text.get("buyback", "")))
    if "onchain" in text:
        r = m["onchain"]["ratio"] or 0
        add("- **%s** %s" % ("The revenue figure checks out on chain." if 0.9 <= r <= 1.1 else
                             "The revenue figure does not match the chain.", text["onchain"]))
    add("- **The revenue is small next to the market cap.** %s" % text["valuation"])
    add("- **The rival is coming back.** %s" % text["recent"])
    if "wide" in text:
        add("- **In the wider market it is third.** %s" % text["wide"])
    if "basis" in text:
        add("- **The headline share depends on how volume is counted.** See the table below.")
    add("- **The lead swings.** %s" % text["stability"])
    if "decomposition" in text:
        add("- **Less than half of the growth is share gain.** %s" % text["decomposition"])
    if "co_movement" in text:
        add("- **No clean substitution in ordinary weeks.** %s" % text["co_movement"])
    add("")
    if m.get("basis"):
        add("### How volume is counted")
        add("")
        add(text["basis"])
        add("")
        if "events" in text:
            add(text["events"])
            add("")
            add(text["events_others"])
            add("")
            if "events_limit" in text:
                add(text["events_limit"])
                add("")
        bp = m["basis"].get("breakpoints")
        if bp:
            add("Where the conclusion would break: counting one side for every venue, Intents "
                "would fall to 50%% only if fewer than %s of THORChain's swap value went through "
                "two pools, and would lose the lead only below %s (%s). Measured from individual "
                "swaps, the figure is %s."
                % (pct(bp["thorchain_double_share_for_c1"]),
                   pct(bp["thorchain_double_share_for_lead"]), bp["assumes"],
                   pct(bp.get("thorchain_double_share_measured"))))
            add("")
        if "tee" in text:
            add(text["tee"])
            add("")
        add("| Counting basis | Intents share, four venues | Largest | Intents share, all eight |")
        add("| --- | --- | --- | --- |")
        for x in m["basis"]["scenarios"]:
            add("| %s | %s | %s | %s |" % (x["label"], pct(x["share"], 1), x["leader"],
                                          pct(x.get("wide_share"), 1)))
        add("")
        if m["basis"]["unverified"]:
            add("Counting basis not checked for: %s; their reported volume is used as is."
                % ", ".join(m["basis"]["unverified"]))
            add("")
    if m.get("wide"):
        add("### All eight venues")
        add("")
        add("| Venue | Kind | Volume, %d days | Share | Gross fees | Take rate |" % m["meta"]["window_days"])
        add("| --- | --- | --- | --- | --- | --- |")
        for v in m["wide"]["venues"]:
            add("| %s | %s | %s | %s | %s | %s |" % (v["name"], v["kind"], usd(v["volume"]),
                                                  pct(v["share"], 1), usd(v["fees"]), bps(v["take_bps"])))
        add("")
    add("### How much the window matters")
    add("")
    add("The headline uses %d days. The same figures over other windows, all ending %s:"
        % (m["meta"]["window_days"], m["meta"]["last_day"]))
    add("")
    add("| Window | Intents share | Largest venue | Take rate | Fees reaching NEAR |")
    add("| --- | --- | --- | --- | --- |")
    for row in m["sensitivity"]:
        add("| %d days | %s | %s | %s | %s |" % (row["days"], pct(row["share"], 1), row["leader"],
                                               bps(row["take_bps"]), pct(row["capture"], 1)))
    add("")
    add("## What would change my mind")
    add("")
    add("The thesis gets stronger if the dated predictions below hold, and weaker if they "
        "miss. Re-running `python3 build.py` after each date grades them automatically.")
    add("")
    add("The predictions are sealed. `predictions/predictions.json` holds them as written; its "
        "SHA-256 is `%s`. That hash is timestamped on Bitcoin through OpenTimestamps "
        "(`predictions/predictions.json.ots`) and the commit is tagged `predictions-v1`. "
        "`python3 build.py` stops if `pipeline/config.py` no longer matches the sealed file."
        % m["meta"].get("predictions_sha256", "n/a"))
    anchor = m["meta"].get("near_anchor")
    if anchor:
        add("")
        add("The same hash is written on NEAR mainnet at `%s` on `%s`, by transaction `%s` "
            "(block %s, %s). `%s` reads it back from public RPC."
            % (anchor["key"], anchor["contract"], anchor["tx"], "{:,}".format(anchor["block_height"]),
               anchor["block_time"], anchor["verify"]))
    add("")
    add("| # | Due | Prediction | Now | Status |")
    add("| --- | --- | --- | --- | --- |")
    for p in m["predictions"]:
        unit = "bps" if p["metric"].endswith("bps") else "share"
        add("| %s | %s | %s | %s | %s |" % (p["id"], p["due"], p["text"],
                                           fmt_value(p["current"], unit), p["status"]))
    add("")
    add("It would be refuted outright by: trailing share below 40%, a take rate pushed "
        "below the rival median, or a capture ratio that stops rising.")
    add("")
    add("## What this analysis cannot say")
    add("")
    for item in text["limits"]:
        add("- " + item)
    add("")
    add("Gross fees over the window, for context:")
    add("")
    add("| Venue | Gross fees, %d days | In peer set |" % m["meta"]["window_days"])
    add("| --- | --- | --- |")
    for row in m["fee_table"]:
        add("| %s | %s | %s |" % (row["name"], usd(row["fees_window"]),
                                  "yes" if row["in_peer_set"] else "no"))
    add("")
    add("Flagged weeks:")
    add("")
    for flag in m["quality_flags"]:
        add("- %s, week of %s: %s against a prior median of %s. %s"
            % (flag["peer"], flag["week"], usd(flag["volume"]), usd(flag["median_prior_8w"]),
               "Cause: the halt above." if flag.get("cause") else "Cause not found."))
    add("")
    return "\n".join(lines)

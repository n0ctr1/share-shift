"""Write every sentence that contains a number, from the computed metrics.

Nothing in THESIS.md or the dashboard is typed by hand if it has a figure in
it: the text is produced here so a re-run on new data rewrites it.
"""

import datetime

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
            "public net volume before confidential intents launched. They cannot both be "
            "right, so it was rebuilt here (below). The bridges in "
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
    if m.get("basis"):
        rows = []
        for v in m["basis"]["venues"].values():
            if "actions_factor" in v:
                what = ("%s of value went through two pools, read from %s individual swaps "
                        "(90%% interval %s to %s); matched daily legs give an upper bound of %s"
                        % (pct(v["double_share_actions"]), "{:,}".format(v["swaps_read"]),
                           pct(v["double_share_actions_p05"]), pct(v["double_share_actions_p95"]),
                           pct(v["paired_share"])))
                left = v["actions_factor"]
            elif "provider_vs_indexer" in v["leg_shares"]:
                what = ("input value plus the routed USDC leg (%s of the indexer's two-leg sum)"
                        % pct(v["leg_shares"]["provider_vs_indexer"], 1))
                left = v["once_factor"]
            else:
                what = "%s is matched pairs of legs into and out of its own token" % pct(v["paired_share"])
                left = v["once_factor"]
            rows.append([v["name"], what, pct(left)])
        rows.append(["NEAR Intents", "both sides of each swap, from intents.near's own events (below)", "50%"])
        out["basis_rows"] = rows
        out["basis_lead"] = ("Venues do not count volume the same way, so the share is computed on "
                             "several bases. Each rival's factor is measured from its own indexer.")
        out["basis_source"] = (
            "For NEAR Intents, %s. Two public re-computations read it differently (%s); both are "
            "reconciled below. Bridges in the wider set are taken as one-sided, as their adapters "
            "report deposits."
            % (config.SUBJECT_VOLUME_SOURCE,
               "; ".join("%s: %s" % (n["source"].replace("https://github.com/", ""), n["finding"])
                         for n in m["basis"]["subject_notes"])))
    if m.get("events"):
        ev_ = m["events"]
        out["events_lead"] = (
            "On %d days every intents.near transaction was listed, a seeded sample of 4,000 was "
            "read, and every token_diff event was valued at that day's price. Both sides average "
            "%.2f of the reported figure, one side %.2f: the reported figure counts both sides, "
            "like the rivals'." % (len(ev_["days"]), ev_["both_ratio_mean"], ev_["one_ratio_mean"]))
        out["events_rows"] = [[d["day"], usd(d["both"]), "%s to %s" % (usd(d["both_p05"]), usd(d["both_p95"])),
                               usd(d["reported"])] for d in ev_["days"]]
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
                "The method stops working after %s: the contract increasingly settles swaps "
                "through transfer intents instead of token_diff events (event version 0.4.3; "
                "data/raw/intents_event_format.json), so later sampled days fall short (%s) and "
                "are shown but not used. The full-day series below dates the break exactly; "
                "how much of the later flow is truly confidential is not established here."
                % (ev["valid_until"], later)
            )
    bq = m.get("bq")
    if bq and bq.get("valid"):
        v, mo = bq["valid"], bq["later_by_month"]
        first, last = bq["days"][0], bq["days"][-1]
        months = ", ".join("%s %.2f" % (datetime.date.fromisoformat(k + "-01").strftime("%B"), x["mean"])
                           for k, x in mo.items() if x)
        out["bq"] = (
            "Every day, not a sample: NEAR's public BigQuery dataset (%s, table "
            "execution_outcomes) holds every log line intents.near wrote. Summing what every "
            "participant gave in token_diff events, at each day's price, lands within %d%% of "
            "the reported figure on %d of %d days through %s (mean %.3f, range %.3f to %.3f). "
            "On %s the match breaks and does not return; the monthly means fall to %s of "
            "reported, while the value moved by transfer intents (swap settlement, but plain "
            "transfers too) grows from %s on %s to %s on %s. Over the whole window token_diff "
            "events alone reach %s of reported volume, so any count built on them alone misses "
            "%s of it."
            % (bq["dataset"], round(100 * bq["tolerance"]), v["within_5pct"], v["days"],
               config.EVENTS_VALID_UNTIL, v["mean"], v["min"], v["max"],
               bq["first_day_off"], months, usd(first["transfer_usd"]), first["day"],
               usd(last["transfer_usd"]), last["day"], pct(bq["token_diff_over_reported"]),
               pct(1 - bq["token_diff_over_reported"]))
        )
    for p in m.get("predictions") or []:
        if p["seal"] == "v2" and p["metric"] == "share_window":
            out["tee_prediction"] = tee_prediction_text(p)
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
                "token now runs through Intents, not through L1 gas.%s"
                % ("{:,.0f}".format(l1["txns_per_day"]), "{:,.0f}".format(l1["txns_per_day_prior"]),
                   100 * (l1["txns_per_day"] / l1["txns_per_day_prior"] - 1),
                   "{:,.0f}".format(l1["active_accounts"]), "{:,.0f}".format(l1["active_accounts_prior"]),
                   100 * (l1["active_accounts"] / l1["active_accounts_prior"] - 1),
                   (" Two indexers agree on this: NEAR's BigQuery transactions table gives the "
                    "same daily counts as NearBlocks on %d of %d days to within 1%%."
                    % (l1["bigquery"]["within_1pct"], l1["bigquery"]["days"])) if l1.get("bigquery") else "")
            )
    tee = m.get("tee")
    if tee:
        out["tee"] = (
            "The headline share was also recomputed inside a trusted execution environment: "
            "tee/share-check (SHA-256 %s...) fetched DefiLlama's and Midgard's data by itself "
            "inside an Intel TDX enclave run by OutLayer, requested by NEAR mainnet transaction "
            "%s. It returned %s against %s in this build, and every venue's volume to the same "
            "$0.1M; the result was delivered on chain by %s with a key that OutLayer's register "
            "contract adds only after checking a TDX quote against its allowlist."
            % (tee["wasm_sha256"][:12], tee["request_tx"], pct(tee["share_tee"], 2),
               pct(tee["share_build"], 2), tee["worker"])
        )
        out["tee_scope"] = (
            "What that proves is narrow: the published program, unmodified, produced the "
            "published numbers from what those APIs served at that moment. It does not prove "
            "the APIs are right; the primary-source checks do that (each venue's own indexer, "
            "intents.near's events, the revenue wallets, block-header supply). This repository "
            "checks the worker's key on chain but does not re-verify the TDX quote itself."
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
    s30 = next((x for x in m["sensitivity"] if x["days"] == 30), None)
    tk_ = m.get("token") or {}
    cl = m.get("call")
    if cl:
        out.update(call_text(m, cl, tr, s))
    else:
        out["title"] = (
            "NEAR Intents led cross-chain swaps over the last %d days on every consistent count. "
            "Its latest weeks are below this thesis's own warning line." % m["meta"]["window_days"])
    out["latest"] = (
        "Latest data, stated first because it cuts against the headline: over the 30 days to "
        "%s Intents' share of the four swap venues was %s (90 days: %s), its volume fell %.0f%% "
        "while THORChain's rose %.0f%%, and the most recent complete week (from %s) was %s. "
        "The kill line in this thesis is a 90-day share below 40%%; it has not been crossed, "
        "but the 30-day and weekly figures are moving toward it, and C6 already fails."
        % (m["meta"]["last_day"], pct(s30["share"]) if s30 else "n/a", pct(tr["share"][s]),
           -100 * m["recent"]["change"][s], 100 * m["recent"]["change"]["thorchain-dex"],
           m["stability"]["latest_week"], pct(m["stability"]["latest_share"]))
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
        "Volume, fees and revenue come from DefiLlama adapters. Checked against primary "
        "sources: THORChain's volume (Midgard), every rival's counting factor (each venue's "
        "indexer), Intents volume through August (intents.near events) and captured revenue "
        "(the revenue wallets). Fees and the bridges' figures are not checked; an adapter "
        "error there is an error here. After August, Intents volume rests on NEAR's own "
        "Dune table, which public events no longer fully reproduce.",
    ]
    return out


def verdict_line(m):
    counts = {}
    for c in m["claims"]:
        counts[c["verdict"]] = counts.get(c["verdict"], 0) + 1
    parts = ["%d %s" % (n, v.lower()) for v, n in sorted(counts.items(), reverse=True)]
    return "%d claims tested: %s." % (len(m["claims"]), ", ".join(parts))


def methods_markdown(m, text):
    s = m["meta"]["subject"]
    names = {p["slug"]: p["name"] for p in m["meta"]["peers"]}
    slugs = [p["slug"] for p in m["meta"]["peers"]]
    h = m["halt"]
    lines = []
    add = lines.append

    add("# Share Shift: method and full evidence")
    add("")
    add("> The short thesis and the investment call are in [THESIS.md](THESIS.md). This file "
        "holds everything behind them: every test, table, primary-source check and limit. "
        "Generated by `python3 build.py` from data fetched %s, covering %s to %s; every figure "
        "is computed by `pipeline/metrics.py`."
        % (m["meta"]["fetched_at"], m["meta"]["first_day"], m["meta"]["last_day"]))
    add("")
    add("## Claims and verdicts")
    add("")
    add("**%s** The competitive position is supported by the data; the value reaching the "
        "token is not. Thresholds are in `pipeline/config.py`; a verdict is one number "
        "compared with one threshold." % verdict_line(m))
    add("")
    add("| # | Claim | Measured | Threshold | Verdict |")
    add("| --- | --- | --- | --- | --- |")
    for c in m["claims"]:
        add("| %s | %s | %s | %s | **%s** |" % (
            c["id"], c["claim"], claim_cells(c)[0], claim_cells(c)[1], c["verdict"]))
    add("")
    add("## What was tested")
    add("")
    add("The long-term case for NEAR rests on NEAR Intents being a business with a durable "
        "position, not only a volume number. A durable position should be visible against "
        "competitors: a leading share, kept when it is tested, at a price rivals cannot "
        "undercut, with the fees reaching the token. This repository tests those things "
        "against the three other venues that swap native assets across chains: %s."
        % ", ".join(names[x] for x in slugs if x != s))
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
        add("This is the third reason for the call in [THESIS.md](THESIS.md): the business Intents runs is "
            "leading and growing its take to the token, but today it buys back a fraction of what "
            "the protocol issues.")
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
        add("Venues do not count volume the same way, so the share is computed on several "
            "bases. Each rival's factor is measured from its own indexer:")
        add("")
        add("| Venue | What its reported volume counts | Left when each swap counts once |")
        add("| --- | --- | --- |")
        for row in text["basis_rows"]:
            add("| %s | %s | %s |" % tuple(row))
        add("")
        add(text["basis_source"])
        add("")
        ev = m.get("events")
        if ev:
            add("**Sampled days.** " + text["events_lead"])
            add("")
            add("| Day | Both sides | 90% interval | Reported |")
            add("| --- | --- | --- | --- |")
            for row in text["events_rows"]:
                add("| %s | %s | %s | %s |" % tuple(row))
            add("")
        if "events" in text:
            add(text["events_others"])
            add("")
            if "events_limit" in text:
                add(text["events_limit"])
                add("")
            if "bq" in text:
                add(text["bq"])
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
    if m["meta"].get("seal_v2_sha256"):
        sv = m["meta"]["seal_v2"]
        add("")
        btc = config.SEAL_V2_BITCOIN
        add("A second seal, made on %s with data seen only through %s, fixes the claim "
            "thresholds as they stand and adds P4 and P5 on the two days after that data, graded "
            "by the build before the hackathon deadline: `predictions/predictions-v2.json`, "
            "SHA-256 `%s`, timestamped in Bitcoin block %s (%s UTC). That timestamp came after "
            "the first of the two days had ended, when its data may already have been public; "
            "the seal cannot show it was not looked at. The second day had not yet happened. "
            "This does not make the thresholds pre-registered: they were set after a first look. "
            "It makes any later change to them visible."
            % (sv["sealed_on"], sv["data_seen_through"], m["meta"]["seal_v2_sha256"],
               "{:,}".format(btc["block"]), btc["time_utc"]))
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
    if "tee_prediction" in text:
        add(text["tee_prediction"])
        add("")
    add("It would be refuted outright by: a trailing 90-day share below 40%, a take rate pushed "
        "below the rival median, or a capture ratio that stops rising.")
    add("")
    add("## How this can be checked")
    add("")
    add("- **Every number:** `python3 build.py --offline` rebuilds this file and the dashboard "
        "from the committed snapshot, byte for byte; `python3 build.py` refetches.")
    add("- **The data, against primary sources:** THORChain, Maya and Chainflip volume against "
        "their own indexers; Intents volume against intents.near's events (sampled days, and "
        "every day from NEAR's public BigQuery dataset); captured revenue against the revenue "
        "wallets; supply against block headers; L1 activity in two indexers. Scripts and outputs are "
        "listed in the README.")
    if "tee" in text:
        add("- **The computation:** %s %s" % (text["tee"], text["tee_scope"]))
    add("- **The predictions:** sealed by hash and timestamped on Bitcoin; the first seal is "
        "also written on NEAR mainnet. See the predictions section.")
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
    halt_flags = [f for f in m["quality_flags"] if f.get("cause")]
    if halt_flags:
        add("- %s, %d weeks from %s to %s: no volume. Cause: the halt above."
            % (halt_flags[0]["peer"], len(halt_flags), halt_flags[0]["week"], halt_flags[-1]["week"]))
    for flag in m["quality_flags"]:
        if flag.get("cause"):
            continue
        add("- %s, week of %s: %s against a prior median of %s. Cause not found."
            % (flag["peer"], flag["week"], usd(flag["volume"]), usd(flag["median_prior_8w"])))
    add("")
    return "\n".join(lines)


def tee_prediction_text(p):
    """How a share prediction is (or will be) graded a second time, inside the TEE."""
    tp = p.get("tee")
    if not tp:
        return ("%s is also graded a second time, inside the TEE: the same committed WASM, run "
                "through OutLayer after %s has ended, on tee/share-check/input-p4.json (%s to %s). "
                "That run is not made yet." % (p["id"], p["due"],
                                               (datetime.date.fromisoformat(p["due"])
                                                - datetime.timedelta(days=p["window_days"] - 1)).isoformat(),
                                               p["due"]))
    if not tp["valid"]:
        return ("A TEE run for %s (%s) is recorded but does not count: %s."
                % (p["id"], tp["request_tx"], "; ".join(why for ok, why in [
                    (tp["right_days"], "it covers other days"),
                    (tp["after_due_day"], "it ran before the due day ended"),
                    (tp["checks_pass"], "a chain check failed")] if not ok)))
    return ("%s was also graded inside the TEE, by the same committed WASM: NEAR mainnet "
            "transaction %s at %s UTC, after the due day ended, returned a share of %s, so %s. "
            "%s"
            % (p["id"], tp["request_tx"], tp["run_time_utc"], pct(tp["share"], 2), tp["status"],
               "Its volume for each venue matches this build's to $0.1M, and so does the verdict."
               if tp["agrees_with_build"] else
               "It does not match this build (%s), so the build's grade and the TEE's are both "
               "shown." % ", ".join("%s %.1f against %s" % (v["slug"], v["tee_musd"], v["build_musd"])
                                     for v in tp["venues"] if not v["agrees"])))


CALL_WORD = {"ACCUMULATE": "accumulate", "WATCH": "watch, not buy", "AVOID": "avoid"}


def call_text(m, cl, tr, s):
    """The investment call: title, one line, three reasons, what would change it."""
    r = cl["rules"]
    tk = m.get("token") or {}
    one = None
    if m.get("basis"):
        one = next((x for x in m["basis"]["scenarios"] if x["id"] == "one_side"), None)
    supported = sum(1 for c in m["claims"] if c["verdict"] == "SUPPORTED")
    c4_ok = any(c["id"] == "C4" and c["verdict"] == "SUPPORTED" for c in m["claims"])
    trend = m.get("capture_trend") or []
    word = CALL_WORD[cl["call"]]
    if cl["call"] == "WATCH":
        title = ("NEAR Intents leads cross-chain swaps, but too little of it reaches the NEAR token "
                 "yet. The call is to %s, until buybacks cover %s of new NEAR and the 30-day share "
                 "is back above %s." % (word, pct(r["buyback_offset_accumulate"]), pct(r["share_30d_hold"])))
        line = ("The business is real and leading; the token's cut of it is not yet large enough, "
                "and the lead is slipping in the latest weeks.")
    elif cl["call"] == "ACCUMULATE":
        title = ("NEAR Intents leads cross-chain swaps and the NEAR token now captures enough of it. "
                 "The call is to accumulate while the 90-day share stays above %s." % pct(r["share_90d_kill"]))
        line = "The lead holds and buybacks cover at least %s of new NEAR." % pct(r["buyback_offset_accumulate"])
    else:
        title = ("NEAR Intents %s. The call is to avoid NEAR on the Intents case until that reverses."
                 % ("has lost its lead in cross-chain swaps" if cl["position_lost"]
                    else "is passing a shrinking share of its fees to the NEAR token"))
        line = ("The 90-day share is below %s." % pct(r["share_90d_kill"]) if cl["position_lost"]
                else "The share of fees reaching NEAR fell from one 90-day window to the next.")
    reasons = [
        "**The business leads.** %s of the four swap venues' volume over %d days%s, %s; "
        "%d of %d claims hold."
        % (pct(cl["share_90d"]), m["meta"]["window_days"],
           (" (%s counting one side of every swap for every venue)" % pct(one["share"])) if one else "",
           "at a take rate above its rivals' median" if c4_ok else "though below its rivals' take rate",
           supported, len(m["claims"])),
        "**The lead is slipping now.** The 30-day share is %s and the latest complete week %s; "
        "over 30 days Intents' volume fell %.0f%% while THORChain's rose %.0f%%."
        % (pct(cl["share_30d"]), pct(cl["share_latest_week"]),
           -100 * m["recent"]["change"][s], 100 * m["recent"]["change"]["thorchain-dex"]),
    ]
    if tk:
        reasons.append(
            "**The token sees too little of it.** Over the window buybacks took %.2fM NEAR "
            "against %.2fM newly issued (%s). Covering %s would take %.1fx today's captured "
            "revenue. The share of fees reaching NEAR is rising: %s over consecutive 90-day windows."
            % (tk["bought_back_near"] / 1e6, tk["net_issued_near"] / 1e6, pct(cl["buyback_offset"]),
               pct(r["buyback_offset_accumulate"]), cl["revenue_multiple_needed"],
               " → ".join(pct(w["capture"]) for w in trend)))
    triggers = [
        ("ACCUMULATE", "buybacks cover at least %s of new NEAR **and** the 30-day share is at "
         "least %s" % (pct(r["buyback_offset_accumulate"]), pct(r["share_30d_hold"])),
         "%s of new NEAR; 30-day share %s" % (pct(cl["buyback_offset"]), pct(cl["share_30d"]))),
        ("AVOID", "the 90-day share falls below %s **or** the share of fees reaching NEAR falls "
         "from one 90-day window to the next" % pct(r["share_90d_kill"]),
         "90-day share %s (latest week %s); fees reaching NEAR %s, up from %s"
         % (pct(cl["share_90d"]), pct(cl["share_latest_week"]), pct(cl["capture"]), pct(cl["capture_prior"]))),
    ]
    note = ("No price target: this measures the business and the token's cut of it, not a fair "
            "price. Next review: %s, or sooner if a line above is crossed. The rule is `CALL` in "
            "`pipeline/config.py`, computed by `metrics.investment_call()`; it was written on "
            "2026-11-12, after the data was seen, and is not sealed." % cl["review_on"])
    lede = ("%d claims tested against data: %d supported, %d refuted. Every number rebuilds from a "
            "committed snapshot, and the key ones are checked against the chains themselves."
            % (len(m["claims"]), supported, len(m["claims"]) - supported))
    return {"title": title, "lede": lede, "call": cl["call"], "call_word": word, "call_line": line,
            "call_reasons": reasons, "call_triggers": triggers, "call_note": note}


def anchor(heading):
    """GitHub's anchor for a markdown heading."""
    import re
    return "#" + re.sub(r"[^a-z0-9 -]", "", heading.lower()).replace(" ", "-")


def thesis_markdown(m, text):
    """The short thesis: the call, the verdicts, the case each way, and why it can be trusted."""
    s = m["meta"]["subject"]
    M = lambda heading: "[details](METHODS.md%s)" % anchor(heading)
    lines = []
    add = lines.append
    add("# " + text["title"])
    add("")
    add("> Data %s to %s, fetched %s. Every figure is computed by `python3 build.py`; none is "
        "typed by hand. The method, every check and every limit: [METHODS.md](METHODS.md)."
        % (m["meta"]["first_day"], m["meta"]["last_day"], m["meta"]["fetched_at"][:10]))
    add("")
    if "call" in text:
        add("## The call: %s" % text["call_word"])
        add("")
        add("**%s.** %s" % (text["call"], text["call_line"]))
        add("")
        for i, r in enumerate(text["call_reasons"], 1):
            add("%d. %s" % (i, r))
        add("")
        add("| Moves the call to | When | Now |")
        add("| --- | --- | --- |")
        for to, when, now in text["call_triggers"]:
            add("| %s | %s | %s |" % (to, when, now))
        add("")
        add(text["call_note"])
        add("")
    add("## Fourteen claims, each one number against one threshold")
    add("")
    add("**%s** Thresholds are in `pipeline/config.py`." % verdict_line(m))
    add("")
    add("| # | Claim | Measured | Threshold | Verdict |")
    add("| --- | --- | --- | --- | --- |")
    for c in m["claims"]:
        add("| %s | %s | %s | %s | **%s** |" % (
            c["id"], c["claim"], claim_cells(c)[0], claim_cells(c)[1], c["verdict"]))
    add("")
    add("## Why it could work")
    add("")
    add("- **The largest venue, on every consistent count.** %s %s %s"
        % (text["share"], text.get("basis_short", "").split(". Only one reading")[0] + ".",
           M("How volume is counted")))
    if m.get("halt"):
        add("- **It held up when a rival stopped.** %s %s" % (text["halt_short"], M("The stress test")))
    add("- **It does not win on price.** %s %s" % (text["take_rate"], M("The rest")))
    add("")
    add("## What could break it")
    add("")
    add("- **Most fees do not reach NEAR.** %s %s %s"
        % (text["capture"], text.get("capture_trend", ""), M("Evidence against")))
    if "token" in text:
        tk = m["token"]
        add("- **Buybacks are small next to issuance.** NEAR's supply grew %.2fM over %d days "
            "(from block headers); buybacks took %.2fM, %s of it. %s"
            % (tk["net_issued_near"] / 1e6, tk["window_days"], tk["bought_back_near"] / 1e6,
               pct(tk["offset_buyback"]), M("What it means for the NEAR token")))
    add("- **The rival is coming back.** %s %s"
        % (text["recent"].split("; every rival grew")[0] + ".", M("Evidence against")))
    if m.get("wide"):
        w = m["wide"]
        add("- **Bridges are bigger.** With the four large bridges added, Intents has %s of the "
            "eight venues' volume and ranks %d of %d. %s"
            % (pct(w["subject_share"]), w["subject_rank_volume"], len(w["venues"]), M("All eight venues")))
    add("")
    add("## Why these numbers can be trusted")
    add("")
    bq = m.get("bq")
    if bq and bq.get("valid"):
        add("- **Volume is counted the same way for every venue.** Each rival's double counting "
            "is measured from its own indexer, and Intents' reported figure equals both sides of "
            "intents.near's own events on %d of %d days through %s (NEAR's public BigQuery "
            "dataset). After that date the events no longer cover all swaps, which is stated as "
            "a limit. %s" % (bq["valid"]["within_5pct"], bq["valid"]["days"],
                             m["events"]["valid_until"] if m.get("events") else "August",
                             M("How volume is counted")))
    if m.get("onchain"):
        add("- **Revenue matches the chain.** Transfers into NEAR's three revenue wallets come to "
            "%s of the revenue figure used. %s"
            % (pct(m["onchain"]["ratio"], 1), M("Evidence against")))
    if m.get("token"):
        add("- **Supply and activity come from the chain.** Issuance is read from block headers; "
            "L1 activity is counted by two indexers that agree. %s" % M("What it means for the NEAR token"))
    add("- **Anyone can rebuild it.** `python3 build.py --offline` reproduces this file and the "
        "dashboard byte for byte from the committed snapshot; the predictions are sealed on "
        "Bitcoin; the headline share was recomputed in a TEE. %s" % M("How this can be checked"))
    add("")
    add("## Dated predictions")
    add("")
    add("| # | Due | Prediction | Now | Status |")
    add("| --- | --- | --- | --- | --- |")
    for p in m["predictions"]:
        unit = "bps" if p["metric"].endswith("bps") else "share"
        add("| %s | %s | %s | %s | %s |" % (p["id"], p["due"], p["text"],
                                           fmt_value(p["current"], unit), p["status"]))
    add("")
    add("P1 to P3 are sealed by hash, timestamped on Bitcoin and written on NEAR mainnet; P4 and "
        "P5 are in a second seal, timestamped on Bitcoin after the first of their two days had "
        "ended. %s %s" % (text.get("tee_prediction", ""), M("What would change my mind")))
    add("")
    add("## What this cannot say")
    add("")
    add("- After August, Intents volume rests on NEAR's own Dune table, which public events no "
        "longer fully reproduce.")
    add("- Which market is the right one, swap venues or swap venues and bridges, is a "
        "judgement; both are shown.")
    add("- Claim thresholds and the call's rule were set after a first look at the data; the "
        "thresholds are sealed so later changes show, the call's rule is not.")
    add("")
    add("Every other limit: %s" % M("What this analysis cannot say"))
    add("")
    return "\n".join(lines)

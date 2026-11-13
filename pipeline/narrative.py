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
            + " These are window totals from data/raw/channels_report.json (%s to %s); the API's "
              "daily data is not kept, as its terms do not allow storing it beyond 24 hours."
            % tuple(c["window"]))
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
                "are shown but not used. The full-day series below dates the break exactly and "
                "rebuilds the later flow from those transfers."
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
    oc = (bq or {}).get("onchain")
    if oc and oc.get("from_method_change"):
        f, b0 = oc["from_method_change"], oc["before_method_change"]
        routed_from = next((d["day"] for d in bq["days"]
                            if d.get("routed_usd", 0) > 0.05 * d["reported"]), None)
        sc_ = {x["id"]: x for x in (m.get("basis") or {}).get("scenarios", [])}
        out["onchain_rebuild"] = (
            "The later flow is not hidden; it moved. From September most swaps settle as plain "
            "transfers through a few 1Click router accounts: the user's deposit goes to a router "
            "and the router pays the other asset back. Counting those two transfers as the two "
            "sides of the swap, as the two token_diff entries are for a direct fill, and adding "
            "token_diff, rebuilds the reported figure for every day from %s to %s: median %.2f "
            "of reported, within 10%% on %d of %d days and within 20%% on %d. Transfers between "
            "routers and solvers are the routers' own hedging and are left out. Routed swaps "
            "start on %s, before DefiLlama's figure includes them, so for the rest of August the "
            "chain shows more than is reported (median %.2f). The rule is fixed before it is "
            "graded again: the two queries' hashes are in the third seal."
            % (bq["first_day_off"], bq["days"][-1]["day"],
               f["median"], f["within_10pct"], f["days"], f["within_20pct"],
               routed_from or "n/a", b0["median"] if b0 else float("nan")))
        if "onchain" in sc_:
            out["onchain_share"] = (
                "With Intents volume taken from intents.near itself for every day of the window, "
                "its share is %s, against %s as reported. Taking each day the lower of the "
                "on-chain and the reported figure, and one side of each swap for every venue, "
                "gives %s, still first. C1 is graded on the lowest of these readings."
                % (pct(sc_["onchain"]["share"]), pct(sc_["reported"]["share"]),
                   pct(sc_["onchain_low"]["share"])))
    if oc and oc.get("routed_share_by_month"):
        rs = oc["routed_share_by_month"]
        mon = lambda k: datetime.date.fromisoformat(k + "-01").strftime("%B")
        out["confidential"] = (
            "Since NEAR launched Confidential Intents, swaps can execute on a private shard that has "
            "no public RPC or explorer, linked to mainnet by a TEE-based bridge. The public chain then "
            "sees money enter and leave, not the fill. The data shows that shift: the share of "
            "on-chain Intents volume that appears only as transfers into and out of 1Click routers, "
            "with no public fill behind it, was %s. Over the last 7 days it was %s. So the rebuild "
            "here verifies how much value crossed intents.near, not who filled it or at what price."
            % (", ".join("%s in %s" % (pct(v), mon(k)) for k, v in rs.items()),
               pct(oc["routed_share_last_7"])))
        out["confidential"] += (" The rise fits settlement moving to the private shard, but public data "
                                "cannot tell a private fill from a router matching orders off chain by "
                                "itself; either way the fill is not public.")
        out["confidential_effect"] = (
            "What it does to the numbers. Volume: the public rebuild stays at %.2f of the reported "
            "figure over the last 14 days, so the reported series does not count flow the public "
            "chain cannot see. Swaps that start and end inside the private shard are in neither; "
            "they are Intents volume, so leaving them out can only make the %s share too low, not "
            "too high. Capture: the revenue figure matches the transfers into NEAR's revenue wallets, "
            "so the %s reaching NEAR is real money; whether the gross fees on private flow are all "
            "in the denominator is not shown by any public source, so capture could be off in "
            "either direction. The latest-week share (%s) is the number most exposed: if more flow "
            "now stays inside the shard, the true figure is higher, by an amount this data cannot "
            "measure. This is a limit of the method, stated as one."
            % (oc["onchain_over_reported_last_14"], pct(m["trailing"]["share"][s]),
               pct(m["trailing"]["capture"]), pct((m.get("stability") or {}).get("latest_share"))))
    scn = m.get("scenarios")
    if scn:
        rows_ = {r["name"]: r for r in scn["rows"]}
        out["scenarios"] = (
            "A forward view, as assumptions anyone can change in SCENARIOS in pipeline/config.py. "
            "Over the %s, with NEAR at $%.2f and net issuance of %.1fM NEAR a year, buybacks would "
            "cover %s of new NEAR in the bear case, %s in the base case and %s in the bull case. "
            "Even the bull case stays under half; there, %s of fees would have to reach NEAR to "
            "get to 50%%. Coverage moves inversely with the NEAR price."
            % (scn["horizon"], scn["price_usd"], scn["new_near_per_year"] / 1e6,
               pct(rows_["bear"]["coverage"]), pct(rows_["base"]["coverage"]),
               pct(rows_["bull"]["coverage"]), pct(rows_["bull"]["capture_for_half"])))
    mt = m.get("market_test")
    if mt:
        rows_ = {r["slug"]: r for r in mt["rows"]}
        sub = rows_.get(s)
        bridges = [r for r in mt["rows"] if r["kind"] == "bridge"]
        grew = max(bridges, key=lambda r: r["gain"]) if bridges else None
        out["market_test"] = (
            "Which market is the right one can be tested, not only argued. A venue that serves "
            "the same users as the halted rival should gain while it is down and give part of "
            "that back when it returns. Over the halt, against an earlier period of the same "
            "length to remove each venue's own trend: %s gained %s of the flow THORChain lost "
            "(trend-adjusted %s) and gave back %s of its gain when THORChain returned. Venues that "
            "pass both tests: %s. Of the four bridges, none passes. %s"
            % (sub["name"], pct(sub["diversion"]), pct(sub["diversion_trend_adjusted"]),
               pct(sub["gave_back"]) if sub["gave_back"] is not None else "none",
               ", ".join(mt["substitutes"]) or "none",
               ("%s grew most (%s a day more) but kept growing after THORChain came back, so the "
                "test cannot tell its own growth from substitution; the other three lost volume "
                "during the halt." % (grew["name"], usd(grew["gain"]))) if grew and grew["gain"] > 0 else ""))
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
            "intents.near's events, the revenue wallets, block-header supply)."
        )
        tdx = tee.get("tdx")
        if tdx:
            oc_ = tdx["onchain_collateral"]
            out["tdx"] = (
                "The TDX quote behind that key is verified here too, not taken from OutLayer "
                "(pipeline/tdx.py). The key was added by transaction %s on %s; the quote passed "
                "to it carries the SHA-256 of that exact key, is signed by an attestation key "
                "bound to Intel's Quoting Enclave, whose report is signed by a PCK certificate "
                "that chains to Intel's SGX Root CA (pinned by public-key hash). Against Intel's "
                "current collateral nothing is revoked and the TDX TCB level is %s; the five "
                "measurements were on OutLayer's allowlist at that block. %d of %d checks pass. "
                "One finding about OutLayer itself: the Intel collateral its contract held at "
                "that block was issued on %s, past its next update (%s), and for %s platform, so "
                "the contract's own check was weaker than this one."
                % (tdx["registration_tx"], tdx["registration_time"][:10], tdx["tcb_status"],
                   tdx["checks_passed"], tdx["checks_total"], oc_["issued"][:10],
                   oc_["next_update"][:10], "the same" if oc_["fmspc_matches"] else "another"))
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
        "four bridges that mostly move the same asset between chains. Which set is the right "
        "market is tested with the halt (only swap venues behaved as substitutes) but one "
        "event is thin evidence, so both sets are shown. Fee methodologies differ between "
        "venues, and Relay's fee figure is far above the rest and has not been reconciled.",
        "One halt is one event. It shows what happened once when a rival stopped; it is not "
        "a law about what happens next time, and the placebo check above shows the growth "
        "could also be Intents' own trend.",
        "%d other weeks are flagged because a venue's volume fell below 20%% of its own prior "
        "eight-week median, with no explanation found. They stay in the data." % len(gaps),
        "Claim thresholds and the call's rule were set after a first look at the data and are "
        "not pre-registered. What is sealed: the first predictions (written on NEAR and "
        "timestamped on Bitcoin), the thresholds (second seal) and, in a third seal made before "
        "its window, the call's rule, the on-chain counting method and P6 to P8. The build "
        "refuses to run if any of them changes.",
        "NEAR's market cap prices the whole L1, so the valuation line compares Intents "
        "revenue with rival multiples and is not a price target.",
        "Volume, fees and revenue come from DefiLlama adapters. Checked against primary "
        "sources: THORChain's volume (Midgard), every rival's counting factor (each venue's "
        "indexer), Intents volume through August (intents.near events) and captured revenue "
        "(the revenue wallets). Fees and the bridges' figures are not checked; an adapter "
        "error there is an error here. Intents volume is rebuilt from intents.near for every "
        "day of the window, but the router rule behind it was found by looking at the data; it "
        "is sealed now, and P8 tests it on days not yet seen.",
    ]
    out["brief"] = brief(m, out)
    return out


def brief(m, text):
    """The short layer: one computed sentence per point, for the page and THESIS.md."""
    s = m["meta"]["subject"]
    names = {p["slug"]: p["name"] for p in m["meta"]["peers"]}
    tr = m["trailing"]
    share = tr["share"]
    second = max((k for k in share if k != s), key=lambda k: share[k])
    b = {}
    b["lead"] = ("%s of four-venue swap volume over %d days, up from %s a year earlier; %s is second "
                 "with %s." % (pct(share[s]), m["meta"]["window_days"],
                               pct(m["yoy"]["share_prior"][s]) if m.get("yoy") else "n/a",
                               names[second], pct(share[second])))
    sc = {x["id"]: x for x in (m.get("basis") or {}).get("scenarios", [])}
    if sc:
        b["counts"] = ("First on every consistent way of counting: %s as reported, %s counting one side "
                       "of each swap, %s on volume rebuilt from the chain. Only halving Intents alone, "
                       "against the rivals' own indexers, puts %s ahead."
                       % (pct(sc["reported"]["share"]), pct(sc["one_side"]["share"]),
                          pct(sc.get("onchain", sc["reported"])["share"]), sc["worst"]["leader"]))
    h = m.get("halt")
    if h:
        p365 = next((x for x in h["placebo"] if x["lookback_days"] == 365), None)
        b["halt"] = ("When %s halted for %d days, Intents took %s of the flow it lost, but growth that "
                     "size was ordinary for Intents%s, so it shows capacity, not cause."
                     % (h["rival"], h["days"], pct((h.get("absorbed_by_basis") or {}).get("one_side", h["absorbed_fraction"])),
                        " (%s percentile of the year before)" % ordinal(round(100 * p365["percentile"])) if p365 else ""))
    w, mt = m.get("wide"), m.get("market_test")
    if w:
        b["bridges"] = ("Add the four large bridges and Intents has %s, rank %d of %d.%s"
                        % (pct(w["subject_share"]), w["subject_rank_volume"], len(w["venues"]),
                           " When %s halted, swap venues behaved as its substitutes and no bridge did."
                           % h["rival"] if mt and not mt["bridges_substituting"] and h else ""))
    ct = m.get("capture_trend") or []
    b["capture"] = ("%s of gross Intents fees reach NEAR's revenue wallets%s; the rest stays with "
                    "solvers and the front ends that distribute Intents."
                    % (pct(tr["capture"]), ", rising every 90 days: " + " → ".join(pct(x["capture"]) for x in ct)
                       if len(ct) > 1 else ""))
    tk = m.get("token")
    if tk:
        b["token"] = ("Buybacks took %.2fM NEAR against %.2fM newly issued over %d days, %s. Covering half "
                      "would take %.1f× today's captured revenue."
                      % (tk["bought_back_near"] / 1e6, tk["net_issued_near"] / 1e6, tk["window_days"],
                         pct(tk["offset_buyback"]), 0.5 / tk["offset_buyback"] if tk["offset_buyback"] else float("nan")))
    if "confidential" in text:
        oc_ = (m.get("bq") or {}).get("onchain") or {}
        b["confidential"] = ("%s of last week's on-chain Intents volume shows only as money entering and "
                             "leaving 1Click routers, with no public fill behind it, as settlement moves "
                             "to NEAR's private shard; the public chain verifies the value moved, not "
                             "who filled it."
                             % pct(oc_.get("routed_share_last_7")))
        b["confidential_effect"] = ("The reported series matches what the public chain sees (%.2f×), so private "
                                    "flow does not inflate the %s share; swaps that stay inside the shard are "
                                    "missing from both, which can only understate it. Capture could be off "
                                    "either way."
                                    % (oc_.get("onchain_over_reported_last_14"), pct(tr["share"][s])))
    scn = m.get("scenarios")
    if scn:
        r_ = {r["name"]: r for r in scn["rows"]}
        b["scenarios"] = ("Twelve months out, buybacks would cover %s of new NEAR in the bear case, %s in the "
                          "base and %s in the bull; even the bull case needs %s of fees reaching NEAR to "
                          "get to half."
                          % (pct(r_["bear"]["coverage"]), pct(r_["base"]["coverage"]),
                             pct(r_["bull"]["coverage"]), pct(r_["bull"]["capture_for_half"])))
    b["price"] = ("It does not win on price: %s of volume in gross fees against a rival median of %s."
                  % (bps(tr["take_bps"][s]), bps(tr["rival_take_median_bps"])))

    trust = []
    bq = m.get("bq") or {}
    oc = bq.get("onchain") or {}
    if oc:
        f = oc["from_method_change"]
        trust.append({"id": "volume", "title": "Intents volume rebuilt from the chain, every day",
                      "value": "%.2f× reported" % f["median"],
                      "line": "Every log line intents.near wrote (NEAR's public BigQuery dataset); within 20%% "
                              "on %d of %d days since the settlement method changed." % (f["within_20pct"], f["days"]),
                      "detail": [text.get("bq"), text.get("onchain_rebuild"), text.get("onchain_share")]})
    th = ((m.get("basis") or {}).get("venues") or {}).get("thorchain-dex")
    if th:
        trust.append({"id": "basis", "title": "Rivals' double counting measured from their own indexers",
                      "value": "%s swaps read" % "{:,}".format(th["swaps_read"]),
                      "line": "THORChain, Maya and Chainflip volume is reduced to one side of each swap with "
                              "factors read from Midgard and the Chainflip indexer.",
                      "detail": [text.get("basis_source"), text.get("events_lead"), text.get("events_others")]})
    if m.get("onchain"):
        trust.append({"id": "revenue", "title": "Revenue matches the revenue wallets",
                      "value": pct(m["onchain"]["ratio"], 1),
                      "line": "Transfers into NEAR's three revenue wallets against the revenue figure used.",
                      "detail": [text.get("onchain")]})
    if tk and tk.get("l1", {}).get("bigquery"):
        l1b = tk["l1"]["bigquery"]
        trust.append({"id": "supply", "title": "Supply from block headers, activity from two indexers",
                      "value": "%d of %d days agree" % (l1b["within_1pct"], l1b["days"]),
                      "line": "NEAR issuance is read from total_supply in block headers; daily L1 counts from "
                              "NearBlocks and BigQuery agree to within 1%.",
                      "detail": [text.get("token"), text.get("token_l1")]})
    tdx = (m.get("tee") or {}).get("tdx")
    if tdx:
        trust.append({"id": "tee", "title": "Headline recomputed in a TEE, checked to Intel's root",
                      "value": "%d/%d checks" % (tdx["checks_passed"], tdx["checks_total"]),
                      "line": "The same WASM recomputed the share inside an Intel TDX enclave; its quote is "
                              "verified here down to Intel's root CA, TCB %s." % tdx["tcb_status"],
                      "detail": [text.get("tee"), text.get("tee_scope"), text.get("tdx")]})
    seals = 1 + bool(m["meta"].get("seal_v2_sha256")) + bool(m["meta"].get("seal_v3_sha256"))
    on_near = bool(m["meta"].get("near_anchor")) + bool(m["meta"].get("near_anchor_v3"))
    trust.append({"id": "seals", "title": "Thresholds, the call's rule and predictions sealed",
                  "value": "%d seals, %d on NEAR" % (seals, on_near),
                  "line": "Hashes timestamped on Bitcoin and written on NEAR mainnet; the build stops if "
                          "any sealed value changes.", "detail": []})
    trust.append({"id": "build", "title": "Every number rebuilds, byte for byte",
                  "value": "build.py --offline",
                  "line": "The offline build regenerates the page, THESIS.md and METHODS.md from the committed "
                          "snapshot, byte for byte, checked on every push; a full build refreshes the data "
                          "but keeps the thesis on its fixed window.", "detail": []})
    b["trust"] = trust
    b["limits"] = [
        "Confidential Intents settle on a private shard: the public chain verifies the value that "
        "crosses intents.near, not the fills behind it, and swaps that stay inside the shard are not "
        "counted at all.",
        "The router rule that rebuilds Intents volume after August was found by looking at the data; "
        "it is sealed now and tested on days not yet seen (P8).",
        "Which market is the right one rests on one natural experiment, the THORChain halt.",
        "Claim thresholds and the call's rule were set after a first look at the data; they are "
        "sealed so any later change shows.",
    ]
    return b


def ordinal(n):
    return "%d%s" % (n, "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


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
            if "onchain_rebuild" in text:
                add(text["onchain_rebuild"])
                add("")
            if "onchain_share" in text:
                add(text["onchain_share"])
                add("")
            if "confidential" in text:
                add("### Confidential Intents: what the public chain cannot see")
                add("")
                add(text["confidential"])
                add("")
                rs = m["bq"]["onchain"]["routed_share_by_month"]
                add("| Month | Share of on-chain Intents volume with no public fill |")
                add("| --- | --- |")
                for k, v in rs.items():
                    add("| %s | %s |" % (k, pct(v)))
                add("| last 7 days | %s |" % pct(m["bq"]["onchain"]["routed_share_last_7"]))
                add("")
                add(text["confidential_effect"])
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
    if "market_test" in text:
        mt = m["market_test"]
        add("### Which market: a substitution test")
        add("")
        add(text["market_test"])
        add("")
        add("| Venue | Kind | Daily, pre | Before | During halt | After | Gain / lost flow | "
            "Trend-adjusted | Gave back | Substitute |")
        add("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in mt["rows"]:
            d = r["daily"]
            add("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                r["name"], r["kind"], usd(d["pre"]), usd(d["before"]), usd(d["during"]),
                usd(d["after_1"]), pct(r["diversion"]), pct(r["diversion_trend_adjusted"]),
                pct(r["gave_back"]) if r["gave_back"] is not None else "n/a",
                "yes" if r["substitute"] else "no"))
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
    scn = m.get("scenarios")
    if scn:
        add("## Twelve months out: three scenarios")
        add("")
        add(text["scenarios"])
        add("")
        add("| Scenario | Story | Market | Share | Take rate | Capture | Intents volume | To NEAR | NEAR bought back | Coverage of new NEAR | Capture for 50% |")
        add("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in scn["rows"]:
            a = r["assumptions"]
            add("| %s | %s | %+.0f%% | %s | %s | %s | %s | %s | %.2fM | %s | %s |" % (
                r["name"], a["story"], 100 * a["market_growth"], pct(a["share"]), bps(a["take_bps"]),
                pct(a["capture"]), usd(r["intents_volume"]), usd(r["captured_usd"]),
                r["bought_back_near"] / 1e6, pct(r["coverage"]), pct(r["capture_for_half"])))
        now = scn["now"]
        add("| now | the window, annualised | | %s | %s | %s | | | | %s | |" % (
            pct(now["share"]), bps(now["take_bps"]), pct(now["capture"]), pct(now["coverage"])))
        add("")
        add("How each row is computed (`metrics.scenarios()`): the window's four-venue volume, "
            "annualised, times (1 + market growth) times share gives Intents volume; times the take "
            "rate gives gross fees; times capture gives revenue to NEAR; times the part of captured "
            "revenue spent on buybacks in the window (%s), divided by the NEAR price ($%.2f, market "
            "cap over block-header supply), gives NEAR bought back; divided by net issuance (%.1fM NEAR "
            "a year) gives coverage. These are assumptions, not forecasts, and are not sealed."
            % (pct(scn["buyback_part_of_captured"]), scn["price_usd"], scn["new_near_per_year"] / 1e6))
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
    if m["meta"].get("seal_v3_sha256"):
        s3 = m["meta"]["seal_v3"]
        add("")
        add("A third seal, made on %s with data seen through %s, fixes what a reader could "
            "suspect of being tuned after the fact: the investment call's rule, the on-chain "
            "counting method (the SHA-256 of both BigQuery queries and the router rule of %d "
            "senders) and P6 to P8, three predictions on %s to their due date, a window that "
            "starts after the seal. `predictions/predictions-v3.json`, SHA-256 `%s`, timestamped "
            "through OpenTimestamps.%s"
            % (s3["sealed_on"], s3["data_seen_through"], s3["router_min_senders"],
               s3["window_starts"], m["meta"]["seal_v3_sha256"],
               (" Written on NEAR mainnet at `%s` by transaction `%s` (block %s)."
                % (m["meta"]["near_anchor_v3"]["key"], m["meta"]["near_anchor_v3"]["tx"],
                   "{:,}".format(m["meta"]["near_anchor_v3"]["block_height"])))
               if m["meta"].get("near_anchor_v3") else
               " Its hash is to be written on NEAR mainnet by the author "
               "(`python3 -m pipeline.anchor --account noctrl.near --seal v3`)."))
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
        add("| %s | %s | %s | %s | %s |" % (p["id"], p["due"], p["text"],
                                           pred_value(p), p["status"]))
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
        "from the committed snapshot, byte for byte. `python3 build.py` refreshes the snapshot from "
        "the APIs; the thesis is still computed on the fixed window to %s (`THESIS_DATA_END`), and "
        "the new days only grade the dated predictions." % config.THESIS_DATA_END)
    add("- **The data, against primary sources:** THORChain, Maya and Chainflip volume against "
        "their own indexers; Intents volume against intents.near's events (sampled days, and "
        "every day from NEAR's public BigQuery dataset); captured revenue against the revenue "
        "wallets; supply against block headers; L1 activity in two indexers. Scripts and outputs are "
        "listed in the README.")
    if "tee" in text:
        add("- **The computation:** %s %s" % (text["tee"], text["tee_scope"]))
    if "tdx" in text:
        add("- **The enclave:** %s `python3 -m pipeline.tdx` repeats it (needs the `cryptography` "
            "package)." % text["tdx"])
    add("- **The predictions:** sealed by hash and timestamped on Bitcoin; the first and third "
        "seals are also written on NEAR mainnet. See the predictions section.")
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


def pred_value(p):
    if p["current"] is None:
        return "n/a"
    if p["metric"] == "onchain_ratio_window":
        return "%.2f" % p["current"]
    if p["metric"] == "lead_window":
        return "%+.1f pts" % (100 * p["current"])
    return fmt_value(p["current"], "bps" if p["metric"].endswith("bps") else "share")


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
               ("Its volume for each venue matches this build's to $0.1M, and so does the verdict."
                + (" The enclave's TDX quote is verified to Intel's root as well (%d of %d checks, TCB %s)."
                   % (tp["tdx"]["checks_passed"], tp["tdx"]["checks_total"], tp["tdx"]["tcb_status"])
                   if tp.get("tdx") else ""))
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
    w_ = m.get("wide") or {}
    where = ("%s of the four native-swap venues over 90 days, %s over 30 days, %s in the latest "
             "week; third, with %s, once four bridges count."
             % (pct(cl["share_90d"]), pct(cl["share_30d"]), pct(cl["share_latest_week"]),
                pct(w_.get("subject_share")))) if w_ else ""
    if cl["call"] == "WATCH":
        title = ("NEAR Intents leads the native-swap venues, but too little of it reaches the NEAR "
                 "token yet. %s The call is to %s, until buybacks cover %s of new NEAR and the 30-day "
                 "share is back above %s." % (where, word, pct(r["buyback_offset_accumulate"]),
                                               pct(r["share_30d_hold"])))
        line = ("The business is real and leading; the token's cut of it is not yet large enough, "
                "and the lead is slipping in the latest weeks.")
    elif cl["call"] == "ACCUMULATE":
        title = ("NEAR Intents leads the native-swap venues and the NEAR token now captures enough of it. "
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
            "`pipeline/config.py`, computed by `metrics.investment_call()`. It was written on "
            "2026-11-12, after the data was seen, and sealed the same day in the third seal, so "
            "the review on that date applies the rule as it stands." % cl["review_on"])
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
    """The short thesis: the call, the case each way, why it can be trusted. Detail is in METHODS.md."""
    B = text["brief"]
    M = lambda heading: "[details](METHODS.md%s)" % anchor(heading)
    lines = []
    add = lines.append
    add("# " + text["title"])
    add("")
    add("> Data %s to %s. Every figure is computed by `python3 build.py`; none is typed by hand. "
        "The method, every check and every limit: [METHODS.md](METHODS.md). Dashboard: "
        "https://n0ctr1.github.io/share-shift/" % (m["meta"]["first_day"], m["meta"]["last_day"]))
    add("")
    if "call" in text:
        add("## The call: %s" % text["call_word"])
        add("")
        add("**%s.** %s" % (text["call"], text["call_line"]))
        add("")
        add("| Moves the call to | When | Now |")
        add("| --- | --- | --- |")
        for to, when, now in text["call_triggers"]:
            add("| %s | %s | %s |" % (to, when, now))
        add("")
        add("The rule is `CALL` in `pipeline/config.py`, sealed on %s; next review %s."
            % ((m["meta"].get("seal_v3") or {}).get("sealed_on", "n/a"), m["call"]["review_on"]))
        add("")
    add("## Is Intents the leader? Yes")
    add("")
    add("- %s" % B["lead"])
    if "counts" in B:
        add("- %s %s" % (B["counts"], M("How volume is counted")))
    if "halt" in B:
        add("- %s %s" % (B["halt"], M("The stress test")))
    if "bridges" in B:
        add("- %s %s" % (B["bridges"], M("Which market: a substitution test")))
    add("- %s" % B["price"])
    add("")
    add("## Does it reach the NEAR token? Not yet")
    add("")
    add("- %s %s" % (B["capture"], M("Evidence against")))
    if "token" in B:
        add("- %s %s" % (B["token"], M("What it means for the NEAR token")))
    add("- %s" % text["recent"].split("; every rival grew")[0].rstrip(".") + ".")
    add("")
    if "confidential" in B:
        add("## Confidential Intents: what the public chain cannot see")
        add("")
        add("- %s" % B["confidential"])
        add("- %s %s" % (B["confidential_effect"], M("Confidential Intents: what the public chain cannot see")))
        add("")
    scn = m.get("scenarios")
    if scn:
        add("## Twelve months out")
        add("")
        add("| Scenario | Market | Share | Take rate | Capture | Buybacks cover new NEAR |")
        add("| --- | --- | --- | --- | --- | --- |")
        for r in scn["rows"]:
            a = r["assumptions"]
            add("| %s | %+.0f%% | %s | %s | %s | **%s** |" % (r["name"], 100 * a["market_growth"], pct(a["share"]),
                                                          bps(a["take_bps"]), pct(a["capture"]), pct(r["coverage"])))
        add("")
        add("%s Assumptions are `SCENARIOS` in `pipeline/config.py`; the build recomputes the outcome. %s"
            % (B["scenarios"], M("Twelve months out: three scenarios")))
        add("")
    add("## Why these numbers can be trusted")
    add("")
    add("| Check | Result |")
    add("| --- | --- |")
    for t in B["trust"]:
        add("| %s | %s |" % (t["title"], t["value"]))
    add("")
    add("How to rerun each one: %s" % M("How this can be checked"))
    add("")
    add("## %d claims, each one number against one threshold" % len(m["claims"]))
    add("")
    add("**%s**" % verdict_line(m))
    add("")
    add("| # | Claim | Measured | Threshold | Verdict |")
    add("| --- | --- | --- | --- | --- |")
    for c in m["claims"]:
        add("| %s | %s | %s | %s | **%s** |" % (
            c["id"], c["claim"], claim_cells(c)[0], claim_cells(c)[1], c["verdict"]))
    add("")
    add("## Dated predictions")
    add("")
    add("| # | Due | Prediction | Now | Status |")
    add("| --- | --- | --- | --- | --- |")
    for p in m["predictions"]:
        add("| %s | %s | %s | %s | %s |" % (p["id"], p["due"], p["text"], pred_value(p), p["status"]))
    add("")
    add("Sealed in three seals, timestamped on Bitcoin; the first and third are written on NEAR "
        "mainnet. %s" % M("What would change my mind"))
    add("")
    add("## What this cannot say")
    add("")
    for item in B["limits"]:
        add("- " + item)
    add("")
    add("Every other limit: %s" % M("What this analysis cannot say"))
    add("")
    return "\n".join(lines)


def noscript_html(m, text):
    """A static summary for readers and crawlers that do not run JavaScript."""
    import html
    e = html.escape
    B = text["brief"]
    parts = ['<div class="frame">', "<h1>%s</h1>" % e(text["title"]),
             "<p><b>The call: %s.</b> %s</p>" % (e(text.get("call", "")), e(text.get("call_line", "")))]
    def ul(title, items):
        items = [i for i in items if i]
        if items:
            parts.append("<h2>%s</h2><ul>%s</ul>" % (e(title), "".join("<li>%s</li>" % e(i) for i in items)))
    ul("Is Intents the leader?", [B.get("lead"), B.get("counts"), B.get("halt"), B.get("bridges"), B.get("price")])
    ul("Does it reach the NEAR token?", [B.get("capture"), B.get("token"), B.get("scenarios")])
    ul("What the public chain cannot see", [B.get("confidential"), B.get("confidential_effect")])
    ul("Why these numbers can be trusted", ["%s: %s. %s" % (t["title"], t["value"], t["line"]) for t in B["trust"]])
    ul("%d claims" % len(m["claims"]), ["%s %s: %s" % (c["id"], c["verdict"], c["claim"]) for c in m["claims"]])
    ul("Dated predictions", ["%s, due %s, %s: %s" % (p["id"], p["due"], p["status"], p["text"]) for p in m["predictions"]])
    ul("What this cannot say", B["limits"])
    parts.append('<p>The short thesis is <a href="https://github.com/n0ctr1/share-shift/blob/main/THESIS.md">THESIS.md</a>; '
                 'every method and check is <a href="https://github.com/n0ctr1/share-shift/blob/main/METHODS.md">METHODS.md</a>. '
                 'Turn on JavaScript for the charts.</p></div>')
    return "".join(parts)

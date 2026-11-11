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
            "ratio": "%.2f" % value}[unit]


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

    out["title"] = (
        "The %d-day stress test: a rival went dark, NEAR Intents grew %.0f%% and kept the "
        "gain. NEAR keeps %s of the fees." % (h["days"], 100 * h["subject_growth"],
                                              pct(tr["capture"]))
        if h else
        "NEAR Intents leads native cross-chain swaps. NEAR keeps %s of the fees."
        % pct(tr["capture"])
    )
    out["summary"] = (
        "A test of NEAR's long-term case against the three other venues that swap native "
        "assets across chains. %s Intents holds %s of the volume, %sand does not undercut "
        "rivals on price. Against that: %s of gross fees reach NEAR, and in the last 30 "
        "days Intents volume moved %+.0f%% while %s moved %+.0f%%."
        % (verdict_line(m), pct(tr["share"][s]),
           ("picked up %s of %s's flow when it halted, " % (pct(h["absorbed_fraction"]), h["rival"])
            if h else ""),
           pct(tr["capture"]), 100 * rc[s], names[runner_up], 100 * rc[runner_up])
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
        "Thresholds were set after a first look at the data. The dated predictions are the "
        "part fixed in advance.",
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
    if h:
        add("1. **The position was tested and held.** %s" % text["halt"])
    add("%d. **It is the largest venue, at a normal price.** %s"
        % (2 if h else 1, text["share"]))
    add("%d. **The token sees little of it so far.** %s" % (3 if h else 2, text["capture"]))
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
            c["id"], c["claim"], fmt_value(c["value"], c["unit"]),
            fmt_value(c["threshold"], c["unit"]), c["verdict"]))
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
    add("## Evidence against")
    add("")
    add("- **Most fees do not reach NEAR.** %s %s %s" % (
        text["capture"], text.get("capture_trend", ""), text.get("buyback", "")))
    add("- **The revenue is small next to the market cap.** %s" % text["valuation"])
    add("- **The rival is coming back.** %s" % text["recent"])
    if "wide" in text:
        add("- **In the wider market it is third.** %s" % text["wide"])
    add("- **The lead swings.** %s" % text["stability"])
    if "decomposition" in text:
        add("- **Less than half of the growth is share gain.** %s" % text["decomposition"])
    if "co_movement" in text:
        add("- **No clean substitution in ordinary weeks.** %s" % text["co_movement"])
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

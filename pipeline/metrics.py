"""Turn the raw snapshot into every number the thesis and the dashboard use.

All functions here are pure: they take plain dicts and lists and return plain
dicts and lists, so tests/test_metrics.py can check them without the network.
"""

import datetime
import math
import statistics

from . import config

FIELDS = ("volume", "fees", "revenue")


def _date(text):
    return datetime.date.fromisoformat(text)


def _week_end(monday_text):
    return (_date(monday_text) + datetime.timedelta(days=6)).isoformat()


def _daterange(start, end):
    day = start
    while day <= end:
        yield day
        day += datetime.timedelta(days=1)


def build_table(raw, fetched_at):
    """Align every peer on one daily calendar.

    The calendar starts on the first day the subject has volume and ends on the
    last day every peer has reported, never including the fetch day itself
    (that day is still in progress).
    """
    slugs = [p["slug"] for p in config.PEERS]
    subject_days = sorted(d for d, v in raw["volume_" + config.SUBJECT]["series"].items() if v > 0)
    start = _date(subject_days[0])
    last_reported = min(_date(max(raw["volume_" + s]["series"])) for s in slugs)
    fetch_day = _date(fetched_at[:10])
    end = min(last_reported, fetch_day - datetime.timedelta(days=1))

    dates = [d.isoformat() for d in _daterange(start, end)]
    table = {"dates": dates}
    for slug in slugs:
        table[slug] = {
            field: [float(raw["%s_%s" % (field, slug)]["series"].get(d, 0.0)) for d in dates]
            for field in FIELDS
        }
    return table


def window_sum(values, end_index, days):
    """Sum of `days` values ending at end_index (inclusive)."""
    lo = max(0, end_index - days + 1)
    return sum(values[lo:end_index + 1])


def shift_share(v0, m0, v1, m1):
    """Split the subject's volume change into a market effect and a share effect.

    v = subject volume, m = peer-set volume, 0 = earlier window, 1 = later one.
    market effect: what the subject would have gained by keeping its old share.
    share effect:  what it gained by raising its share of the later market.
    The two always add up to v1 - v0.
    """
    s0 = v0 / m0 if m0 else 0.0
    s1 = v1 / m1 if m1 else 0.0
    market = s0 * (m1 - m0)
    share = (s1 - s0) * m1
    return {"market_effect": market, "share_effect": share, "total": v1 - v0}


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / math.sqrt(sxx * syy)


def weekly(table):
    """Aggregate to complete Monday-Sunday weeks."""
    slugs = [p["slug"] for p in config.PEERS]
    buckets = {}
    for i, text in enumerate(table["dates"]):
        day = _date(text)
        monday = day - datetime.timedelta(days=day.weekday())
        bucket = buckets.setdefault(monday.isoformat(), {"days": 0, "idx": []})
        bucket["days"] += 1
        bucket["idx"].append(i)
    rows = []
    for monday in sorted(buckets):
        bucket = buckets[monday]
        if bucket["days"] != 7:
            continue
        row = {"week": monday}
        for slug in slugs:
            row[slug] = {f: sum(table[slug][f][i] for i in bucket["idx"]) for f in FIELDS}
        row["total_volume"] = sum(row[s]["volume"] for s in slugs)
        rows.append(row)
    return rows


def monthly(table):
    slugs = [p["slug"] for p in config.PEERS]
    rows = {}
    for i, text in enumerate(table["dates"]):
        row = rows.setdefault(text[:7], {"month": text[:7], "days": 0,
                                         **{s: {f: 0.0 for f in FIELDS} for s in slugs}})
        row["days"] += 1
        for slug in slugs:
            for field in FIELDS:
                row[slug][field] += table[slug][field][i]
    out = []
    for month in sorted(rows):
        row = rows[month]
        year, mon = int(month[:4]), int(month[5:])
        days_in_month = (datetime.date(year + mon // 12, mon % 12 + 1, 1) - datetime.timedelta(days=1)).day
        row["complete"] = row["days"] == days_in_month
        row["total_volume"] = sum(row[s]["volume"] for s in slugs)
        out.append(row)
    return out


def quality_flags(weeks):
    """Weeks where a peer's volume collapsed against its own recent history.

    These are usually outages or reporting gaps. They are listed, not removed.
    """
    flags = []
    for peer in config.PEERS:
        slug = peer["slug"]
        for i in range(8, len(weeks)):
            prior = [weeks[j][slug]["volume"] for j in range(i - 8, i)]
            base = statistics.median(prior)
            value = weeks[i][slug]["volume"]
            if base > 0 and value < 0.2 * base:
                # Material: the missing venue normally carried 5% or more of
                # the week's volume, so its absence visibly moves every share.
                expected_total = weeks[i]["total_volume"] - value + base
                flags.append({"week": weeks[i]["week"], "peer": peer["name"],
                              "volume": value, "median_prior_8w": base,
                              "material": base / expected_total >= 0.05})
    return flags


def longest_zero_run(values):
    """(start_index, length) of the longest run of zeros; (None, 0) if none."""
    best = (None, 0)
    start = None
    for i, v in enumerate(list(values) + [1.0]):
        if v == 0:
            if start is None:
                start = i
        elif start is not None:
            if i - start > best[1]:
                best = (start, i - start)
            start = None
    return best


def daily_mean(values, lo, hi):
    """Mean of values[lo:hi+1]; None if the range is outside the data."""
    if lo < 0 or hi >= len(values) or hi < lo:
        return None
    return sum(values[lo:hi + 1]) / (hi - lo + 1)


def growth(values, at, n):
    """Change of the n days starting at `at` against the n days before it."""
    if at - n < 0 or at + n > len(values):
        return None
    before = sum(values[at - n:at])
    return sum(values[at:at + n]) / before - 1 if before else None


def placebo(values, at, n, lookback):
    """Where the growth at `at` ranks among the same measure on earlier dates.

    Every start date in the `lookback` days before `at` whose two windows end
    before `at` is a placebo: nothing special happened there.
    """
    observed = growth(values, at, n)
    others = [growth(values, i, n) for i in range(max(n, at - lookback), at - n + 1)]
    others = [x for x in others if x is not None]
    if observed is None or not others:
        return None
    return {
        "lookback_days": lookback,
        "placebo_count": len(others),
        "placebo_median": statistics.median(others),
        "percentile": sum(1 for x in others if x < observed) / len(others),
    }


def halt_experiment(table, subject, slugs, names):
    """What happened to everyone's volume when a large rival stopped trading.

    Finds the longest zero-volume run of each rival. For the first one that is
    long enough, and whose venue was large enough beforehand, compares four
    equal-length periods: before, during, and two after.
    """
    for rival in slugs:
        if rival == subject:
            continue
        start, n = longest_zero_run(table[rival]["volume"])
        if start is None or n < config.MIN_HALT_DAYS or start - n < 0:
            continue
        periods = {
            "before": (start - n, start - 1),
            "during": (start, start + n - 1),
            "after_1": (start + n, start + 2 * n - 1),
            "after_2": (start + 2 * n, start + 3 * n - 1),
        }
        means = {key: {s: daily_mean(table[s]["volume"], lo, hi) for s in slugs}
                 for key, (lo, hi) in periods.items()}
        before, during = means["before"], means["during"]
        total_before = sum(before.values())
        if before[rival] / total_before < config.MIN_HALT_SHARE:
            continue
        lost = before[rival] - during[rival]
        event = next((e for e in config.KNOWN_EVENTS if e["slug"] == rival
                      and table["dates"][start] <= e["overlaps"] <= table["dates"][start + n - 1]),
                     None)

        def fee_rate(key):
            lo, hi = periods[key]
            v = daily_mean(table[subject]["volume"], lo, hi)
            f = daily_mean(table[subject]["fees"], lo, hi)
            return 1e4 * f / v if v and f else None

        last_key = "after_2" if means["after_2"][rival] is not None else "after_1"
        return {
            "rival": names[rival],
            "rival_slug": rival,
            "days": n,
            "first_day": table["dates"][start],
            "last_day": table["dates"][start + n - 1],
            "periods": {key: [table["dates"][lo], table["dates"][hi]]
                        for key, (lo, hi) in periods.items() if hi < len(table["dates"])},
            "daily_volume": means,
            "lost_daily": lost,
            "absorbed_fraction": (during[subject] - before[subject]) / lost if lost else None,
            "market_change": sum(during.values()) / total_before - 1,
            "rival_recovery": (means[last_key][rival] / before[rival]
                               if means[last_key][rival] is not None else None),
            "subject_after_vs_before": (means[last_key][subject] / before[subject] - 1
                                        if means[last_key][subject] is not None else None),
            "last_period": last_key,
            "subject_growth": growth(table[subject]["volume"], start, n),
            "subject_growth_first_week": growth(table[subject]["volume"], start, 7),
            "others_growth": {s: growth(table[s]["volume"], start, n)
                              for s in slugs if s not in (subject, rival)},
            "placebo": [x for x in (placebo(table[subject]["volume"], start, n, look)
                                    for look in config.PLACEBO_LOOKBACKS) if x],
            "subject_take_bps": {key: fee_rate(key) for key in periods},
            "what": event["what"] if event else None,
            "source": event["source"] if event else None,
        }
    return None


def counting_basis(raw, table, subject, names, window, wide_volumes=None):
    """How many sides of a swap each venue's reported volume counts, and what
    the shares look like once every venue is put on the same footing.

    For a venue with a leg breakdown, a matched pair of legs (into the routing
    token and out of it) is one swap counted twice. `once_factor` is the
    fraction of reported volume left when each such pair is counted once.
    """
    slugs = [p["slug"] for p in config.PEERS]
    first, last_ = window
    venues, factor = {}, {s: 1.0 for s in slugs}
    for slug in slugs:
        legs = (raw.get("legs_" + slug) or {}).get("series") or {}
        days = [d for d in legs if first <= d <= last_]
        if not days:
            continue
        total = sum(legs[d]["totalVolume"] for d in days)
        shares = {}
        if "onceVolume" in legs[days[0]]:
            # the indexer already separates each swap's first leg from its routed leg
            once = sum(legs[d]["onceVolume"] for d in days)
            paired = 2 * (total - once)
            reported = sum(v for d, v in zip(table["dates"], table[slug]["volume"]) if d in days)
            shares["provider_vs_indexer"] = reported / total if total else None
        else:
            paired = 0.0
            for a, b in config.LEG_PAIRS:
                va = sum(legs[d].get(a, 0.0) for d in days)
                vb = sum(legs[d].get(b, 0.0) for d in days)
                shares[a], shares[b] = va / total, vb / total
                paired += 2 * min(va, vb)
        factor[slug] = 1 - paired / total / 2
        venues[slug] = {"name": names[slug], "days": len(days), "leg_shares": shares,
                        "paired_share": paired / total, "once_factor": factor[slug],
                        "source": config.LEG_SOURCES.get(slug)}
    if not venues:
        return None
    vol = {s: sum(v for d, v in zip(table["dates"], table[s]["volume"]) if first <= d <= last_)
           for s in slugs}

    def shares_under(subject_factor, use_measured):
        adj = {s: vol[s] * (subject_factor if s == subject else (factor[s] if use_measured else 1.0))
               for s in slugs}
        total = sum(adj.values())
        out = {"share": adj[subject] / total, "leader": names[max(adj, key=adj.get)],
               "runner_up_share": max(v for s, v in adj.items() if s != subject) / total}
        if wide_volumes:
            out["wide_share"] = adj[subject] / (total + wide_volumes)
        return out

    scenarios = [
        {"id": "reported", "label": "As reported by every venue", **shares_under(1.0, False)},
        {"id": "one_side", "label": "One side of each swap for every venue (Intents halved, "
                                    "routed pairs counted once)", **shares_under(0.5, True)},
        {"id": "worst", "label": "Intents halved, rivals left as reported (inconsistent with "
                                 "the rivals' own leg data)", **shares_under(0.5, False)},
        {"id": "best", "label": "Intents as reported, rivals' routed pairs counted once",
         **shares_under(1.0, True)},
    ]
    return {"venues": venues, "scenarios": scenarios,
            "subject_source": config.SUBJECT_VOLUME_SOURCE,
            "subject_notes": config.SUBJECT_BASIS_NOTES,
            "unverified": [names[s] for s in slugs if s != subject and s not in venues]}


def onchain_check(raw, table, subject, window):
    """NEAR's captured revenue rebuilt from transfers into its revenue wallets,
    against the provider's revenue series for the same days."""
    oc = raw.get("onchain_revenue")
    if not oc:
        return None
    first = max(window[0], oc["range"][0])
    last_ = min(window[1], oc["range"][1])
    prices = oc["near_price_usd"]
    per_wallet = {w_: 0.0 for w_ in oc["wallets"]}
    near_total = 0.0
    for day, wallets in oc["days"].items():
        if not first <= day <= last_ or day not in prices:
            continue
        for wallet, v in wallets.items():
            amount = v["near"] + v["wnear"]
            per_wallet[wallet] += amount * prices[day]
            near_total += amount
    onchain = sum(per_wallet.values())
    provider = sum(v for d, v in zip(table["dates"], table[subject]["revenue"]) if first <= d <= last_)
    return {
        "window": [first, last_],
        "onchain_usd": onchain,
        "onchain_near": near_total,
        "provider_usd": provider,
        "ratio": onchain / provider if provider else None,
        "per_wallet_usd": per_wallet,
        "buyback_share": per_wallet.get(oc["buyback_wallet"], 0.0) / onchain if onchain else None,
        "buyback_wallet": oc["buyback_wallet"],
        "source": oc["source"],
    }


def shares_measured(basis, table, subject, names, window, subject_factor, wide_volumes):
    """Every venue scaled by the one-side factor measured from its own records."""
    slugs = [p["slug"] for p in config.PEERS]
    first, last_ = window
    vol = {s: sum(v for d, v in zip(table["dates"], table[s]["volume"]) if first <= d <= last_)
           for s in slugs}
    factor = {s: basis["venues"].get(s, {}).get("once_factor", 1.0) for s in slugs}
    factor[subject] = subject_factor
    adj = {s: vol[s] * factor[s] for s in slugs}
    total = sum(adj.values())
    out = {"id": "measured", "label": "One side of each swap, every factor measured from the venue's "
                                      "own records (Intents from intents.near events)",
           "share": adj[subject] / total, "leader": names[max(adj, key=adj.get)],
           "runner_up_share": max(v for s, v in adj.items() if s != subject) / total,
           "subject_factor": subject_factor}
    if wide_volumes:
        out["wide_share"] = adj[subject] / (total + wide_volumes)
    return out


def events_check(raw, table, subject):
    """Days on which Intents volume was rebuilt from intents.near token_diff events."""
    idx = {d: i for i, d in enumerate(table["dates"])}
    days = []
    for name in sorted(k for k in raw if k.startswith("intents_events_")):
        e = raw[name]
        day = e["day"]
        if day not in idx:
            continue
        reported = table[subject]["volume"][idx[day]]
        days.append({
            "day": day, "reported": reported, "transactions": e["transactions_in_day"],
            "sampled": e["sampled"], "both": e["both_sides_usd"],
            "both_p05": e["both_sides_usd_p05"], "both_p95": e["both_sides_usd_p95"],
            "one": e["one_side_usd"],
            "both_ratio": e["both_sides_usd"] / reported if reported else None,
            "one_ratio": e["one_side_usd"] / reported if reported else None,
            "reported_in_both_interval": e["both_sides_usd_p05"] <= reported <= e["both_sides_usd_p95"],
            "reported_in_one_interval": e["both_sides_usd_p05"] / 2 <= reported <= e["both_sides_usd_p95"] / 2,
        })
    if not days:
        return None
    return {"days": days,
            "one_ratio_mean": sum(d["one_ratio"] for d in days) / len(days),
            "both_sides": all(d["reported_in_both_interval"] and not d["reported_in_one_interval"]
                              for d in days)}


def wide_report(raw, table, subject, names, last, w, yoy_prior_end):
    """The subject's place among all eight venues, bridges included."""
    dates = table["dates"]
    venues = [{"slug": p["slug"], "name": p["name"], "kind": "swap",
               "volume_series": table[p["slug"]]["volume"],
               "fee_series": table[p["slug"]]["fees"],
               "first_day": dates[0]} for p in config.PEERS]
    for p in config.WIDE_PEERS:
        vs = raw.get("widevolume_" + p["slug"], {}).get("series") or {}
        fs = raw.get("fees_" + p["slug"], {}).get("series") or {}
        if not vs:
            continue
        venues.append({"slug": p["slug"], "name": p["name"], "kind": "bridge",
                       "volume_series": [float(vs.get(d, 0.0)) for d in dates],
                       "fee_series": [float(fs.get(d, 0.0)) for d in dates],
                       "first_day": min(d for d, v in vs.items() if v)})
    if len(venues) == len(config.PEERS):
        return None

    def shares(end):
        vols = {v["slug"]: window_sum(v["volume_series"], end, w) for v in venues}
        total = sum(vols.values())
        return vols, total

    vols, total = shares(last)
    rows = []
    for v in venues:
        fees = window_sum(v["fee_series"], last, w)
        rows.append({"name": v["name"], "slug": v["slug"], "kind": v["kind"],
                     "volume": vols[v["slug"]], "share": vols[v["slug"]] / total,
                     "fees": fees,
                     "take_bps": 1e4 * fees / vols[v["slug"]] if vols[v["slug"]] else None})
    by_volume = sorted(rows, key=lambda r: -r["volume"])
    by_fees = sorted(rows, key=lambda r: -r["fees"])
    out = {
        "venues": by_volume,
        "market_volume": total,
        "subject_share": vols[subject] / total,
        "subject_rank_volume": [r["slug"] for r in by_volume].index(subject) + 1,
        "subject_rank_fees": [r["slug"] for r in by_fees].index(subject) + 1,
        "fee_leader": by_fees[0]["name"],
        "prior": None,
    }
    if yoy_prior_end is not None and yoy_prior_end - w + 1 >= 0:
        first_needed = dates[yoy_prior_end - w + 1]
        late = [v["name"] for v in venues if v["first_day"] > first_needed]
        vols0, total0 = shares(yoy_prior_end)
        out["prior"] = {"subject_share": vols0[subject] / total0, "market_volume": total0,
                        "market_growth": total / total0 - 1,
                        "venues_without_full_history": late}
    # weekly share of the subject in the wide set, for the chart
    weeks_ = {}
    for i, text in enumerate(dates):
        day = _date(text)
        monday = (day - datetime.timedelta(days=day.weekday())).isoformat()
        b = weeks_.setdefault(monday, {"n": 0, "subject": 0.0, "total": 0.0})
        b["n"] += 1
        for v in venues:
            b["total"] += v["volume_series"][i]
        b["subject"] += table[subject]["volume"][i]
    out["weekly_share"] = {k: (b["subject"] / b["total"] if b["total"] else 0.0)
                           for k, b in sorted(weeks_.items()) if b["n"] == 7}
    return out


def crosscheck(raw, table, slug):
    """Compare the provider's series for one venue with that venue's own API."""
    other = (raw.get("crosscheck_midgard") or {}).get("series") or {}
    pairs = [(table[slug]["volume"][i], other[d]) for i, d in enumerate(table["dates"]) if d in other]
    if len(pairs) < 30:
        return None
    a = [p[0] for p in pairs]
    b = [p[1] for p in pairs]
    both_zero = sum(1 for x, y in pairs if x == 0 and y == 0)
    only_one_zero = sum(1 for x, y in pairs if (x == 0) != (y == 0))
    return {
        "days": len(pairs),
        "provider_total": sum(a),
        "own_api_total": sum(b),
        "ratio": sum(a) / sum(b) if sum(b) else None,
        "pearson_r": pearson(a, b),
        "zero_days_in_both": both_zero,
        "zero_days_in_one_only": only_one_zero,
        "source": (raw.get("crosscheck_midgard") or {}).get("source"),
    }


def suspension_checks(table, subject, names, rival, skip_from, skip_to):
    """Short outages of one rival, found in the data: did the subject's volume move?

    An outage is two or more days in a row with the rival under 10% of its own
    median over the 14 days before. The long halt is passed in and skipped.
    """
    out = []
    vol = table[rival]["volume"]
    dates = table["dates"]
    base = 14
    i = base
    while i < len(vol):
        ref = statistics.median(vol[i - base:i])
        if ref > 0 and vol[i] < 0.1 * ref:
            j = i
            while j + 1 < len(vol) and vol[j + 1] < 0.1 * ref:
                j += 1
            n = j - i + 1
            overlaps_halt = skip_from and not (dates[j] < skip_from or dates[i] > skip_to)
            if 2 <= n < config.MIN_HALT_DAYS and not overlaps_halt:
                before = daily_mean(table[subject]["volume"], i - base, i - 1)
                during = daily_mean(table[subject]["volume"], i, j)
                out.append({
                    "rival": names[rival], "from": dates[i], "to": dates[j], "days": n,
                    "rival_before": ref, "rival_during": daily_mean(vol, i, j),
                    "subject_before": before, "subject_during": during,
                    "subject_change": during / before - 1 if before else None,
                })
            i = j + 1
        else:
            i += 1
    return out


def channel_report(explorer, table, subject, window, halt):
    """Who brings the swaps and who keeps the app fees, from Explorer aggregates.

    `explorer` is data/raw/explorer_daily.json. Covers 1Click swaps of at
    least its minUsdPrice; coverage against all Intents volume is reported.
    """
    days = explorer["days"]

    def collect(first, last_):
        ch, rec, n = {}, {}, 0
        for day, d in days.items():
            if not first <= day <= last_:
                continue
            n += 1
            for name, v in d["channels"].items():
                c = ch.setdefault(name, {"swaps": 0, "usd": 0.0, "fee_usd": 0.0})
                for k in c:
                    c[k] += v[k]
            for name, v in d["fee_recipients"].items():
                rec[name] = rec.get(name, 0.0) + v
        return ch, rec, n

    ch, rec, n_days = collect(window[0], window[1])
    if not n_days:
        return None
    total = sum(c["usd"] for c in ch.values())
    fees = sum(rec.values())
    ranked = sorted(ch.items(), key=lambda kv: -kv[1]["usd"])
    top = [{"channel": name, "usd": c["usd"], "share": c["usd"] / total, "swaps": c["swaps"],
            "fee_bps": 1e4 * c["fee_usd"] / c["usd"] if c["usd"] else None,
            "multi_venue": name in config.MULTI_VENUE_CHANNELS,
            "routes_to_rivals": config.CHANNEL_NOTES.get(name, {}).get("routes_to_rivals", "unknown"),
            "note": config.CHANNEL_NOTES.get(name, {}).get("note", "operator not identified"),
            "source": config.CHANNEL_NOTES.get(name, {}).get("source")}
           for name, c in ranked[:config.TOP_N]]
    rec_ranked = sorted(rec.items(), key=lambda kv: -kv[1])
    recipients = [{"recipient": name, "fee_usd": v, "share": v / fees if fees else None}
                  for name, v in rec_ranked[:config.TOP_N]]
    idx = {d: i for i, d in enumerate(table["dates"])}
    all_volume = sum(table[subject]["volume"][idx[d]] for d in days
                     if window[0] <= d <= window[1] and d in idx)
    multi = sum(c["usd"] for name, c in ch.items() if name in config.MULTI_VENUE_CHANNELS)
    report = {
        "window": window,
        "days": n_days,
        "min_usd": explorer["filters"]["minUsdPrice"],
        "calibration": explorer.get("calibration"),
        "volume": total,
        "coverage_of_all_intents_volume": total / all_volume if all_volume else None,
        "channels": top,
        "channel_count": len(ch),
        "top_channel_share": top[0]["share"],
        "top3_share": sum(c["share"] for c in top[:3]),
        "hhi": sum((c["usd"] / total) ** 2 for c in ch.values()),
        "multi_venue_share": multi / total,
        "multi_venue_channels": sorted(name for name in ch if name in config.MULTI_VENUE_CHANNELS),
        "known_share": sum(c["usd"] for name, c in ch.items()
                           if config.CHANNEL_NOTES.get(name, {}).get("routes_to_rivals")
                           in ("yes", "no", "other")) / total,
        "app_fees": fees,
        "app_fee_bps": 1e4 * fees / total if total else None,
        "recipients": recipients,
        "recipient_count": len(rec),
        "buyback_share_of_app_fees": rec.get(config.BUYBACK_ACCOUNT, 0.0) / fees if fees else None,
        "halt": None,
    }

    # Which channels carried the extra volume while the rival was down?
    if halt and all(k in halt["periods"] for k in ("before", "during")):
        per = {}
        for key, (first, last_) in halt["periods"].items():
            c_, _, n_ = collect(first, last_)
            if n_:
                per[key] = {name: v["usd"] / n_ for name, v in c_.items()}
        if "before" in per and "during" in per:
            names_ = set(per["before"]) | set(per["during"])
            delta = {x: per["during"].get(x, 0.0) - per["before"].get(x, 0.0) for x in names_}
            gain = sum(delta.values())
            movers = sorted(delta.items(), key=lambda kv: -kv[1])[:5]
            multi_delta = sum(v for k, v in delta.items() if k in config.MULTI_VENUE_CHANNELS)
            report["halt"] = {
                "daily_before": sum(per["before"].values()),
                "daily_during": sum(per["during"].values()),
                "daily_after": {k: sum(v.values()) for k, v in per.items()
                                if k.startswith("after")},
                "gain_daily": gain,
                "movers": [{"channel": k, "before": per["before"].get(k, 0.0),
                            "during": per["during"].get(k, 0.0), "delta": v,
                            "share_of_gain": v / gain if gain > 0 else None}
                           for k, v in movers],
                "multi_venue_delta": multi_delta,
                "multi_venue_share_of_gain": multi_delta / gain if gain > 0 else None,
                "multi_venue_daily": {k: sum(v for n_, v in per[k].items()
                                             if n_ in config.MULTI_VENUE_CHANNELS) for k in per},
            }
    return report


def _verdict(ok):
    return "SUPPORTED" if ok else "REFUTED"


def compute(raw, fetched_at):
    return _compute(raw, fetched_at)


def _compute(raw, fetched_at):
    table = build_table(raw, fetched_at)
    slugs = [p["slug"] for p in config.PEERS]
    names = {p["slug"]: p["name"] for p in config.PEERS}
    subject = config.SUBJECT
    rivals = [s for s in slugs if s != subject]
    last = len(table["dates"]) - 1
    w = config.WINDOW
    t = config.THRESHOLDS

    def total(field, end, days, only=None):
        return sum(window_sum(table[s][field], end, days) for s in (only or slugs))

    # --- trailing window -------------------------------------------------
    vol = {s: window_sum(table[s]["volume"], last, w) for s in slugs}
    fees = {s: window_sum(table[s]["fees"], last, w) for s in slugs}
    revenue = {s: window_sum(table[s]["revenue"], last, w) for s in slugs}
    market = sum(vol.values())
    share = {s: vol[s] / market for s in slugs}
    take_bps = {s: (1e4 * fees[s] / vol[s] if vol[s] else None) for s in slugs}
    rival_take = [take_bps[s] for s in rivals if take_bps[s] is not None]
    rival_take_median = statistics.median(rival_take)
    capture = revenue[subject] / fees[subject] if fees[subject] else None

    sensitivity = []
    for days in config.SENSITIVITY_WINDOWS:
        if days > last + 1:
            continue
        v = {x: window_sum(table[x]["volume"], last, days) for x in slugs}
        f_subject = window_sum(table[subject]["fees"], last, days)
        r_subject = window_sum(table[subject]["revenue"], last, days)
        sensitivity.append({
            "days": days,
            "share": v[subject] / sum(v.values()),
            "leader": names[max(v, key=v.get)],
            "take_bps": 1e4 * f_subject / v[subject] if v[subject] else None,
            "capture": r_subject / f_subject if f_subject else None,
        })

    # --- same window one year earlier -----------------------------------
    prior_end = last - 365
    has_prior = prior_end - w + 1 >= 0
    yoy = None
    if has_prior:
        vol0 = {s: window_sum(table[s]["volume"], prior_end, w) for s in slugs}
        market0 = sum(vol0.values())
        split = shift_share(vol0[subject], market0, vol[subject], market)
        yoy = {
            "prior_window": [table["dates"][prior_end - w + 1], table["dates"][prior_end]],
            "market_prior": market0,
            "market_now": market,
            "market_growth": market / market0 - 1,
            "subject_prior": vol0[subject],
            "subject_now": vol[subject],
            "subject_growth": vol[subject] / vol0[subject] - 1 if vol0[subject] else None,
            "share_prior": {s: vol0[s] / market0 for s in slugs},
            "share_points_change": {s: share[s] - vol0[s] / market0 for s in slugs},
            "shift_share": split,
            "share_effect_fraction": split["share_effect"] / split["total"] if split["total"] else None,
        }

    # --- weekly series and stability ------------------------------------
    weeks = weekly(table)
    for row in weeks:
        row["share"] = {s: (row[s]["volume"] / row["total_volume"] if row["total_volume"] else 0.0)
                        for s in slugs}
        row["take_bps"] = {s: (1e4 * row[s]["fees"] / row[s]["volume"]
                               if row[s]["volume"] and row[s]["fees"] else None) for s in slugs}
    flags = quality_flags(weeks)
    distorted = {f["week"] for f in flags if f["material"]}
    clean = [r for r in weeks if r["week"] not in distorted]
    recent = clean[-config.STABILITY_WEEKS:]
    recent_share = [r["share"][subject] for r in recent]
    stability = {
        "weeks": len(recent),
        "first_week": recent[0]["week"],
        "excluded_weeks": sorted(w for w in distorted if w >= recent[0]["week"]),
        "min": min(recent_share),
        "max": max(recent_share),
        "mean": statistics.mean(recent_share),
        "stdev": statistics.pstdev(recent_share),
        "min_week": recent[recent_share.index(min(recent_share))]["week"],
        "latest_week": weeks[-1]["week"],
        "latest_share": weeks[-1]["share"][subject],
    }

    # Do the subject and its rivals rise and fall together (one tide) or
    # against each other (substitution)? Weekly log changes, last 52 weeks.
    span = weeks[-53:]
    dx, dy = [], []
    for a, b in zip(span, span[1:]):
        ra = sum(a[s]["volume"] for s in rivals)
        rb = sum(b[s]["volume"] for s in rivals)
        if a[subject]["volume"] > 0 and b[subject]["volume"] > 0 and ra > 0 and rb > 0:
            dx.append(math.log(b[subject]["volume"] / a[subject]["volume"]))
            dy.append(math.log(rb / ra))
    co_movement = {"weeks": len(dx), "pearson_r": pearson(dx, dy)}

    months = monthly(table)
    revenue_days = [d for d, v in zip(table["dates"], table[subject]["revenue"]) if v > 0]
    first_revenue_month = revenue_days[0][:7] if revenue_days else "9999-99"
    for row in months:
        row["share"] = {s: (row[s]["volume"] / row["total_volume"] if row["total_volume"] else 0.0)
                        for s in slugs}
        # The revenue series starts later than the fee series; before its
        # first entry the ratio is unknown, not zero.
        row["capture"] = (row[subject]["revenue"] / row[subject]["fees"]
                          if row[subject]["fees"] and row["month"] >= first_revenue_month else None)

    # --- value capture against market cap -------------------------------
    mcap = raw["mcap"]["usd_market_cap"]
    annual = 365.0 / w
    valuation = {}
    for s in slugs:
        cap = mcap.get(s)
        valuation[s] = {
            "market_cap": cap,
            "fees_annualized": fees[s] * annual,
            "revenue_annualized": revenue[s] * annual,
            "mcap_to_fees": cap / (fees[s] * annual) if cap and fees[s] else None,
            "mcap_to_revenue": cap / (revenue[s] * annual) if cap and revenue[s] else None,
        }

    # What would Intents' captured revenue be worth at the multiple the market
    # pays for its rivals' revenue? NEAR's market cap prices the whole L1, so
    # this is the only like-for-like way to read it.
    rival_multiples = [valuation[s]["mcap_to_revenue"] for s in rivals
                       if valuation[s]["mcap_to_revenue"] is not None]
    implied = None
    if rival_multiples and valuation[subject]["market_cap"]:
        multiple = statistics.median(rival_multiples)
        value = multiple * valuation[subject]["revenue_annualized"]
        implied = {
            "rival_median_mcap_to_revenue": multiple,
            "implied_value": value,
            "fraction_of_subject_mcap": value / valuation[subject]["market_cap"],
        }

    # --- fee-only venues (context, never part of a share) ---------------
    end_date = table["dates"][last]
    start_date = table["dates"][last - w + 1]
    fee_table = []
    for peer in config.PEERS + config.FEE_ONLY:
        series = raw["fees_" + peer["slug"]]["series"]
        days = [d for d in series if start_date <= d <= end_date]
        fee_table.append({
            "name": peer["name"],
            "in_peer_set": peer in config.PEERS,
            "fees_window": sum(series[d] for d in days),
            "days_reported": len(days),
        })
    fee_table.sort(key=lambda r: -r["fees_window"])

    # --- natural experiment and recent momentum -------------------------
    halt = halt_experiment(table, subject, slugs, names)

    def change_30d(slug):
        now_ = window_sum(table[slug]["volume"], last, 30)
        prev = window_sum(table[slug]["volume"], last - 30, 30)
        return now_ / prev - 1 if prev else None
    recent = {"days": 30, "change": {s: change_30d(s) for s in slugs}}

    # Fees reaching NEAR over consecutive, non-overlapping windows, oldest first.
    capture_trend = []
    for k in range(3, -1, -1):
        end_i = last - k * w
        if end_i - w + 1 < 0:
            continue
        f_ = window_sum(table[subject]["fees"], end_i, w)
        r_ = window_sum(table[subject]["revenue"], end_i, w)
        if f_ and table["dates"][end_i - w + 1][:7] >= first_revenue_month:
            capture_trend.append({"from": table["dates"][end_i - w + 1],
                                  "to": table["dates"][end_i], "capture": r_ / f_})

    # How lumpy is each venue's daily flow? Standard deviation over mean.
    burst = {}
    for slug in slugs:
        days_ = table[slug]["volume"][last - w + 1:last + 1]
        mean_ = statistics.mean(days_)
        top10 = sorted(range(len(days_)), key=lambda i: -days_[i])[:10]
        window_dates = table["dates"][last - w + 1:last + 1]
        burst[slug] = {
            "top10_share": sum(days_[i] for i in top10) / sum(days_) if sum(days_) else None,
            "top10_dates": sorted(window_dates[i] for i in top10),
            "cv": statistics.pstdev(days_) / mean_ if mean_ else None,
            "median_day": statistics.median(days_),
            "max_day": max(days_),
        }

    # --- claims ----------------------------------------------------------
    bridge_volume = 0.0
    for p in config.WIDE_PEERS:
        series_ = (raw.get("widevolume_" + p["slug"]) or {}).get("series") or {}
        bridge_volume += sum(v for d, v in series_.items() if start_date <= d <= end_date)
    basis = counting_basis(raw, table, subject, names, [start_date, end_date], bridge_volume or None)
    if basis:
        by_id = {x["id"]: x for x in basis["scenarios"]}
        like = [by_id["reported"], by_id["one_side"]]
        c1_value = min(x["share"] for x in like)
        c1_ok = all(x["share"] > t["leader_share"] and x["leader"] == names[subject] for x in like)
        c1_text = ("NEAR Intents is the largest swap venue with more than %d%% of volume, "
                   "whether volume is taken as reported or one side of each swap is counted "
                   "for every venue." % round(100 * t["leader_share"]))
    else:
        c1_value = share[subject]
        c1_ok = share[subject] > t["leader_share"] and share[subject] == max(share.values())
        c1_text = ("NEAR Intents is the largest venue in the peer set, with more than "
                   "%d%% of volume." % round(100 * t["leader_share"]))
    events = events_check(raw, table, subject)
    if basis and events:
        measured = shares_measured(basis, table, subject, names, [start_date, end_date],
                                   events["one_ratio_mean"], bridge_volume or None)
        basis["scenarios"].insert(2, measured)
        for x in basis["scenarios"]:
            if x["id"] == "worst":
                x["label"] = ("Intents halved, rivals left as reported (refuted: rivals' indexers "
                              "and intents.near events both show two-sided counting)")
    if basis and halt and halt["absorbed_fraction"] is not None:
        f_rival = basis["venues"].get(halt["rival_slug"], {}).get("once_factor", 1.0)
        halt["absorbed_by_basis"] = {
            "reported": halt["absorbed_fraction"],
            "one_side": halt["absorbed_fraction"] * 0.5 / f_rival,
            "worst": halt["absorbed_fraction"] * 0.5,
        }
    claims = [
        {
            "id": "C1",
            "claim": c1_text,
            "value": c1_value, "unit": "share", "threshold": t["leader_share"],
            "verdict": _verdict(c1_ok),
        },
        {
            "id": "C2",
            "claim": "Most of the year-on-year volume gain came from taking share, "
                     "not from market growth.",
            "value": yoy["share_effect_fraction"] if yoy else None, "unit": "share",
            "threshold": t["share_effect"],
            "verdict": (_verdict(yoy["share_effect_fraction"] > t["share_effect"])
                        if yoy and yoy["share_effect_fraction"] is not None else "NOT COMPUTABLE"),
        },
        {
            "id": "C3",
            "claim": "The peer-set market itself grew more than %d%% year on year."
                     % round(100 * t["pie_growth"]),
            "value": yoy["market_growth"] if yoy else None, "unit": "growth",
            "threshold": t["pie_growth"],
            "verdict": _verdict(yoy["market_growth"] > t["pie_growth"]) if yoy else "NOT COMPUTABLE",
        },
        {
            "id": "C4",
            "claim": "Intents charges at least the median take rate of its rivals "
                     "(it is not winning on price alone).",
            "value": take_bps[subject], "unit": "bps", "threshold": rival_take_median,
            "verdict": _verdict(take_bps[subject] >= t["take_rate_vs_peers"] * rival_take_median),
        },
        {
            "id": "C5",
            "claim": "NEAR keeps more than %d%% of the gross fees Intents generates."
                     % round(100 * t["capture"]),
            "value": capture, "unit": "share", "threshold": t["capture"],
            "verdict": _verdict(capture is not None and capture > t["capture"]),
        },
        {
            "id": "C6",
            "claim": "The lead is stable: weekly share never fell below %d%% in the last "
                     "%d undistorted weeks." % (round(100 * t["share_floor"]), config.STABILITY_WEEKS),
            "value": stability["min"], "unit": "share", "threshold": t["share_floor"],
            "verdict": _verdict(stability["min"] >= t["share_floor"]),
        },
    ]
    if halt and halt["absorbed_fraction"] is not None:
        claims.append({
            "id": "C7",
            "claim": "When its largest rival stopped trading, Intents picked up more than "
                     "%d%% of the flow that rival had carried." % round(100 * t["absorbed"]),
            "value": min(halt.get("absorbed_by_basis", {}).get("one_side", 9), halt["absorbed_fraction"]),
            "unit": "share", "threshold": t["absorbed"],
            "verdict": _verdict(min(halt.get("absorbed_by_basis", {}).get("one_side", 9),
                                    halt["absorbed_fraction"]) > t["absorbed"]),
        })
    rival_cv = [burst[s]["cv"] for s in rivals if burst[s]["cv"] is not None]
    claims.append({
        "id": "C8",
        "claim": "Intents daily volume is steadier than every rival's (lower standard "
                 "deviation relative to its mean).",
        "value": burst[subject]["cv"], "unit": "ratio", "threshold": min(rival_cv),
        "verdict": _verdict(burst[subject]["cv"] < min(rival_cv)),
    })

    channels = None
    if raw.get("explorer_daily"):
        channels = channel_report(raw["explorer_daily"], table, subject,
                                  [start_date, end_date], halt)
    if channels:
        claims.append({
            "id": "C10",
            "claim": "No single distribution channel carries more than %d%% of 1Click "
                     "swap volume." % round(100 * t["top_channel"]),
            "value": channels["top_channel_share"], "unit": "share",
            "threshold": t["top_channel"],
            "verdict": _verdict(channels["top_channel_share"] <= t["top_channel"]),
        })

    wide = wide_report(raw, table, subject, names, last, w, prior_end if has_prior else None)
    if wide:
        claims.append({
            "id": "C11",
            "claim": "Intents is also the largest venue when the four big bridges are "
                     "added to the peer set.",
            "value": wide["subject_rank_volume"], "unit": "rank", "threshold": 1,
            "display": {"value": "rank %d of %d" % (wide["subject_rank_volume"], len(wide["venues"])),
                        "threshold": "rank 1"},
            "verdict": _verdict(wide["subject_rank_volume"] == 1),
        })

    if events:
        claims.append({
            "id": "C13",
            "claim": "The reported Intents volume counts both sides of each swap, like the "
                     "rivals' figures: on every day rebuilt from intents.near events it sits "
                     "inside the both-sides interval and outside the one-side interval.",
            "value": sum(1 for d in events["days"] if d["reported_in_both_interval"]
                         and not d["reported_in_one_interval"]),
            "unit": "count", "threshold": len(events["days"]),
            "display": {"value": "%d of %d days" % (
                sum(1 for d in events["days"] if d["reported_in_both_interval"]
                    and not d["reported_in_one_interval"]), len(events["days"])),
                "threshold": "%d of %d" % (len(events["days"]), len(events["days"]))},
            "verdict": _verdict(events["both_sides"]),
        })
    oc = onchain_check(raw, table, subject, [start_date, end_date])
    if oc and oc["ratio"]:
        claims.append({
            "id": "C12",
            "claim": "The captured-revenue figure used here matches the transfers into NEAR's "
                     "three revenue wallets within %d%%." % round(100 * t["onchain_match"]),
            "value": abs(oc["ratio"] - 1), "unit": "share", "threshold": t["onchain_match"],
            "display": {"value": "%.1f%% apart" % (100 * abs(oc["ratio"] - 1)),
                        "threshold": "within %d%%" % round(100 * t["onchain_match"])},
            "verdict": _verdict(abs(oc["ratio"] - 1) <= t["onchain_match"]),
        })

    if len(capture_trend) >= 3:
        rising = all(b["capture"] > a["capture"] for a, b in zip(capture_trend, capture_trend[1:]))
        claims.append({
            "id": "C9",
            "claim": "The share of fees reaching NEAR rose in every one of the last %d "
                     "consecutive %d-day windows." % (len(capture_trend), w),
            "value": sum(1 for a, b in zip(capture_trend, capture_trend[1:])
                         if b["capture"] > a["capture"]),
            "unit": "count", "threshold": len(capture_trend) - 1,
            "display": {
                "value": "%d of %d rises" % (sum(1 for a, b in zip(capture_trend, capture_trend[1:])
                                               if b["capture"] > a["capture"]), len(capture_trend) - 1),
                "threshold": "%d of %d" % (len(capture_trend) - 1, len(capture_trend) - 1)},
            "verdict": _verdict(rising),
        })

    # --- predictions -----------------------------------------------------
    current = {
        "share_trailing": share[subject],
        "capture_trailing": capture,
        "take_rate_trailing_bps": take_bps[subject],
    }
    predictions = []
    for p in config.PREDICTIONS:
        value = current[p["metric"]]
        if end_date < p["due"]:
            status = "PENDING"
        else:
            status = "MET" if value is not None and value >= p["value"] else "MISSED"
        predictions.append({**p, "current": value, "status": status})

    claims.sort(key=lambda c: int(c["id"][1:]))
    return {
        "meta": {
            "fetched_at": fetched_at,
            "first_day": table["dates"][0],
            "last_day": end_date,
            "window_days": w,
            "window": [start_date, end_date],
            "min_month_volume": config.MIN_MONTH_VOLUME,
            "subject_methodology": raw["revenue_" + subject].get("methodology") or {},
            "peers": [{"slug": s, "name": names[s]} for s in slugs],
            "subject": subject,
        },
        "trailing": {
            "volume": vol, "fees": fees, "revenue": revenue, "market_volume": market,
            "share": share, "take_bps": take_bps, "rival_take_median_bps": rival_take_median,
            "capture": capture,
        },
        "sensitivity": sensitivity,
        "halt": halt,
        "recent": recent,
        "burst": burst,
        "capture_trend": capture_trend,
        "channels": channels,
        "basis": basis,
        "events": events,
        "onchain": oc,
        "wide": wide,
        "crosscheck": crosscheck(raw, table, config.MIDGARD_SLUG),
        "suspensions": (suspension_checks(table, subject, names, halt["rival_slug"],
                                          halt["first_day"], halt["last_day"]) if halt else []),
        "context_notes": [
            {**note, "name": names[note["slug"]],
             "top10_days_after": sum(1 for d in burst[note["slug"]]["top10_dates"] if d >= note["date"])}
            for note in config.CONTEXT_NOTES if note["slug"] in burst],
        "yoy": yoy,
        "stability": stability,
        "co_movement": co_movement,
        "valuation": valuation,
        "implied_value": implied,
        "fee_table": fee_table,
        "quality_flags": [
            {**f, "cause": (halt["what"] or "zero-volume run")
             if halt and f["peer"] == halt["rival"] and halt["first_day"] <= _week_end(f["week"])
             and f["week"] <= halt["last_day"] else None}
            for f in flags],
        "windows_clean": not any(
            f["material"] and (start_date <= f["week"] <= end_date
                               or (yoy and yoy["prior_window"][0] <= f["week"] <= yoy["prior_window"][1]))
            for f in flags),
        "claims": claims,
        "predictions": predictions,
        "weekly": weeks,
        "monthly": months,
    }

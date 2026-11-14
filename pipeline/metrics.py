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


def market_test(raw, table, halt, names):
    """Which venues behave like substitutes for the halted rival?

    A venue that serves the same users should gain while the rival is down and
    give part of that back when it returns. Each venue's daily mean is compared
    over the halt's periods, plus one earlier period of the same length
    ("pre") so a venue already growing before the halt is not read as a
    substitute: its trend-adjusted gain subtracts the pre-to-before change.
    Bridges are included, which is the point: if the market were "swaps plus
    bridges", bridges should behave like the swap venues do.
    """
    if not halt or "periods" not in halt:
        return None
    P = halt["periods"]
    first = datetime.date.fromisoformat(P["before"][0])
    span = (datetime.date.fromisoformat(P["before"][1]) - first).days
    pre = [(first - datetime.timedelta(days=span + 1)).isoformat(),
           (first - datetime.timedelta(days=1)).isoformat()]
    series = {p["slug"]: dict(zip(table["dates"], table[p["slug"]]["volume"])) for p in config.PEERS
              if p["slug"] != halt["rival_slug"]}
    kinds = {s: "swap" for s in series}
    for p in config.WIDE_PEERS:
        vs = (raw.get("widevolume_" + p["slug"]) or {}).get("series")
        if vs:
            series[p["slug"]] = {d: float(v) for d, v in vs.items()}
            kinds[p["slug"]] = "bridge"
            names = dict(names, **{p["slug"]: p["name"]})

    def mean(s, a, b):
        v = [x for d, x in s.items() if a <= d <= b]
        return sum(v) / len(v) if v else None
    lost = halt["lost_daily"]
    rows = []
    for slug, s in series.items():
        m = {k: mean(s, *v) for k, v in dict(P, pre=pre).items()}
        if None in (m["pre"], m["before"], m["during"], m["after_1"]):
            continue
        gain = m["during"] - m["before"]
        trend = m["before"] - m["pre"]
        adj = gain - trend
        back = m["during"] - m["after_1"]
        rows.append({"slug": slug, "name": names[slug], "kind": kinds[slug],
                     "daily": m, "gain": gain, "trend_before": trend,
                     "diversion": gain / lost, "diversion_trend_adjusted": adj / lost,
                     "gave_back": back / gain if gain > 0 else None,
                     "substitute": gain > 0 and adj > 0 and back > 0})
    rows.sort(key=lambda r: -r["diversion_trend_adjusted"])
    swap = [r for r in rows if r["kind"] == "swap"]
    bridge = [r for r in rows if r["kind"] == "bridge"]
    return {
        "periods": dict(P, pre=pre), "lost_daily": lost, "rows": rows,
        "swap_diversion_adjusted": sum(r["diversion_trend_adjusted"] for r in swap),
        "bridge_diversion_adjusted": sum(r["diversion_trend_adjusted"] for r in bridge),
        "substitutes": [r["name"] for r in rows if r["substitute"]],
        "bridges_substituting": [r["name"] for r in bridge if r["substitute"]],
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
        actions = raw.get("actions_" + slug)
        if actions:
            # Pairing daily totals is an upper bound on routed swaps; reading
            # individual swaps measures it, so that factor is the one used.
            v = venues[slug]
            v["pair_sum_factor"] = factor[slug]
            v["double_share_actions"] = actions["double_value_share"]
            v["double_share_actions_p05"] = actions["double_value_share_p05"]
            v["double_share_actions_p95"] = actions["double_value_share_p95"]
            v["actions_factor"] = actions["once_factor"]
            v["swaps_read"] = actions["swaps_read"]
            factor[slug] = v["once_factor"] = actions["once_factor"]
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


def shares_measured(basis, table, subject, names, window, subject_factor, wide_volumes,
                    overrides=None):
    """Every venue scaled by the one-side factor measured from its own records."""
    slugs = [p["slug"] for p in config.PEERS]
    first, last_ = window
    vol = {s: sum(v for d, v in zip(table["dates"], table[s]["volume"]) if first <= d <= last_)
           for s in slugs}
    factor = {s: basis["venues"].get(s, {}).get("once_factor", 1.0) for s in slugs}
    factor.update(overrides or {})
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


def shares_onchain(table, subject, names, window, bq, wide_volumes, measured=None):
    """The window's shares with Intents volume taken from intents.near itself.

    `onchain`: every day's Intents volume is the on-chain reconstruction from
    BigQuery, rivals as reported. `onchain_low`: each day the lower of the
    on-chain and the reported figure, and one side of each swap counted for
    every venue at the factors measured from their own records. Returns None
    unless BigQuery covers every day of the window.
    """
    if not bq or not bq.get("onchain"):
        return None
    first, last_ = window
    on = {d["day"]: d["onchain_usd"] for d in bq["days"]}
    dates = [d for d in table["dates"] if first <= d <= last_]
    if any(d not in on for d in dates):
        return None
    slugs = [p["slug"] for p in config.PEERS]
    vol = {s: sum(v for d, v in zip(table["dates"], table[s]["volume"]) if first <= d <= last_)
           for s in slugs}
    rep = dict(zip(table["dates"], table[subject]["volume"]))
    out = []
    for sid, label, intents, factors in (
            ("onchain", "Intents volume rebuilt from intents.near events for every day (BigQuery), "
                        "rivals as reported", sum(on[d] for d in dates), None),
            ("onchain_low", "Each day the lower of the on-chain and the reported Intents volume, "
                            "one side of each swap for every venue at measured factors",
             sum(min(on[d], rep[d]) for d in dates), measured)):
        adj = dict(vol, **{subject: intents})
        if factors:
            adj = {s: adj[s] * factors[s] for s in slugs}
        total = sum(adj.values())
        row = {"id": sid, "label": label, "share": adj[subject] / total,
               "leader": names[max(adj, key=adj.get)],
               "runner_up_share": max(v for s, v in adj.items() if s != subject) / total}
        if wide_volumes:
            row["wide_share"] = adj[subject] / (total + wide_volumes * (0.5 if factors else 1.0))
        out.append(row)
    return out


def token_check(raw, window):
    """Net new NEAR supply over the window against the NEAR swept into the
    buyback wallet and into all three revenue wallets; L1 activity."""
    sup = raw.get("near_supply")
    oc = raw.get("onchain_revenue")
    if not sup or not oc:
        return None
    pts = {p["day"]: p for p in sup["points"]}
    days = sorted(pts)
    y0, y1, w0, w1 = (pts[d] for d in days)
    issued = w1["total_supply_near"] - w0["total_supply_near"]
    issued_prior = y1["total_supply_near"] - y0["total_supply_near"]
    span = (datetime.date.fromisoformat(w1["day"]) - datetime.date.fromisoformat(w0["day"])).days
    first, last_ = window
    bought = captured = 0.0
    for day, wallets in oc["days"].items():
        if not first <= day <= last_:
            continue
        for wallet, v in wallets.items():
            amount = v["near"] + v["wnear"]
            captured += amount
            if wallet == oc["buyback_wallet"]:
                bought += amount
    out = {
        "window_days": span,
        "supply_start": w0["total_supply_near"], "supply_end": w1["total_supply_near"],
        "net_issued_near": issued,
        "net_issued_prior_near": issued_prior,
        "annual_issuance_rate": issued / w0["total_supply_near"] * 365.0 / span,
        "bought_back_near": bought,
        "captured_near": captured,
        "offset_buyback": bought / issued if issued else None,
        "offset_captured": captured / issued if issued else None,
        "multiple_to_offset": issued / captured if captured else None,
        "supply_points": sup["points"],
    }
    l1 = (raw.get("near_l1_daily") or {}).get("series") or []
    if l1:
        def mean(a, b, k):
            rows = [r[k] for r in l1 if a <= r["date"] <= b]
            return sum(rows) / len(rows) if rows else None
        shift = lambda d: (datetime.date.fromisoformat(d) - datetime.timedelta(days=365)).isoformat()
        out["l1"] = {
            "txns_per_day": mean(first, last_, "txns"),
            "txns_per_day_prior": mean(shift(first), shift(last_), "txns"),
            "active_accounts": mean(first, last_, "active_accounts"),
            "active_accounts_prior": mean(shift(first), shift(last_), "active_accounts"),
            "source": (raw.get("near_l1_daily") or {}).get("source"),
        }
        bq = (raw.get("bq_l1_daily") or {}).get("rows") or []
        nb = {r["date"]: r for r in l1}
        pairs = [(int(r["transactions"]) / nb[r["day"]]["txns"],
                  int(r["signers"]) / nb[r["day"]]["active_accounts"])
                 for r in bq if r["day"] in nb and nb[r["day"]]["txns"] and nb[r["day"]]["active_accounts"]]
        if pairs:
            med = lambda v: sorted(v)[len(v) // 2]
            out["l1"]["bigquery"] = {
                "days": len(pairs), "txns_ratio_median": med([a for a, _ in pairs]),
                "signers_ratio_median": med([b for _, b in pairs]),
                "txns_ratio_max": max(a for a, _ in pairs),
                "within_1pct": sum(1 for a, _ in pairs if abs(a - 1) <= 0.01),
                "dataset": raw["bq_l1_daily"]["dataset"],
            }
    return out


def tee_check(raw, trailing, basis, window):
    """Compare the TEE run's recomputation with this build's own numbers."""
    tee = raw.get("tee_run")
    if not tee or not tee.get("output"):
        return None
    out = tee["output"]
    day = lambda ts: datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")
    same_window = [day(out["from_ts"]), day(out["to_ts"])] == list(window)
    rows = []
    for slug, musd in out["volume_musd"].items():
        ours = trailing["volume"].get(slug)
        rows.append({"slug": slug, "tee_musd": musd, "build_musd": round(ours / 1e6, 1) if ours else None})
    once = {s: v["once_factor"] for s, v in ((basis or {}).get("venues") or {}).items()}
    return {
        "request_tx": tee["request_tx"], "resolve_tx": (tee.get("worker") or {}).get("resolve_tx"),
        "sender": tee["sender"], "block_height": tee["block_height"], "request_id": tee["request_id"],
        "wasm_sha256": tee["wasm_sha256"], "worker": (tee.get("worker") or {}).get("signer_id"),
        "instructions": (tee.get("resources") or {}).get("instructions"),
        "checks": tee["checks"], "same_window": same_window,
        "share_tee": out["share_reported"], "share_build": trailing["share"][config.SUBJECT],
        "share_diff": abs(out["share_reported"] - trailing["share"][config.SUBJECT]),
        "once_thorchain_tee": out.get("once_thorchain"), "once_thorchain_build": once.get("thorchain-dex"),
        "once_maya_tee": out.get("once_maya"), "once_maya_build": once.get("maya-protocol"),
        "volumes": rows, "explorer": tee.get("explorer"),
        "tdx": tdx_summary(raw, (tee.get("worker") or {}).get("public_key")),
    }


def tdx_summary(raw, public_key):
    """Our own check of the Intel TDX quote behind the worker key (pipeline/tdx.py)."""
    rec = raw.get("tdx_quote")
    if not rec or not public_key:
        return None
    for w in rec["workers"]:
        if w.get("worker_public_key", public_key) == public_key and w["checks"]:
            fresh, onchain = w["collateral_intel_now"], w["collateral_onchain"]
            return {
                "registration_tx": w["registration_tx"], "registration_time": w["registration_time"],
                "explorer": w["explorer"], "fmspc": w["fmspc"], "measurements": w["measurements"],
                "checks_passed": sum(1 for v in w["checks"].values() if v),
                "checks_total": len(w["checks"]), "all_pass": all(w["checks"].values()),
                "tcb_status": (fresh.get("tcb") or {}).get("status"),
                "tcb_date": (fresh.get("tcb") or {}).get("tcb_date"),
                "intel_collateral_issued": fresh.get("issued"),
                "onchain_collateral": {"issued": onchain["issued"], "next_update": onchain["next_update"],
                                       "fmspc_matches": onchain["tcb_info_fmspc_matches"],
                                       "current": onchain["current_at_check_time"]},
                "runs": [r["run"] for r in w["runs"]],
            }
    return None


def buyback_provenance(raw, window, token):
    """Was the NEAR that reached the buyback wallet bought, and is it held?

    From data/raw/bq_buyback_provenance.json: NEAR paid out by intents.near to
    the wallet, split into the output leg of a 1Click swap (wNEAR delivered by a
    router in the same amount), a swap the paying account signed itself (a
    token_diff that gained wNEAR that day), and the rest. From
    data/raw/buyback_outflows.json: everything that left the wallet."""
    pv = raw.get("bq_buyback_provenance")
    if not pv:
        return None
    first, last = window
    rows = [r for r in pv["rows"] if first <= r["day"] <= last]
    y = 1e24
    total = sum(int(r["near_raw"]) for r in rows) / y
    router = sum(int(r["near_raw_from_router"]) for r in rows) / y
    payer = sum(int(r["near_raw_swapped_by_payer"]) for r in rows) / y
    out = {"days": len(rows), "paid_by_intents_near": total, "via_router_swap": router,
           "swapped_by_payer": payer, "swapped": router + payer,
           "swapped_part": (router + payer) / total if total else None,
           "router_part": router / total if total else None,
           "withdrawals": sum(int(r["withdrawals"]) for r in rows),
           "wallet_received": token.get("bought_back_near") if token else None}
    if out["wallet_received"]:
        out["part_of_wallet_inflow"] = total / out["wallet_received"]
    of = raw.get("buyback_outflows")
    if of:
        sent = [x for x in of["outflows"] if first <= x["day"] <= last]
        out["outflows"] = len(sent)
        out["near_sent"] = sum(x.get("near") or 0 for x in sent)
        out["outflow_range"] = of["range"]
    return out


def scenarios(out, raw):
    """Bear, base and bull for the next twelve months, from config.SCENARIOS.

    Each scenario sets the market's growth, Intents' share, take rate and the
    share of fees reaching NEAR. The rest is the current window: its market
    volume annualised, the part of captured revenue spent on buybacks, NEAR's
    net issuance rate and price. Output: Intents revenue to NEAR, NEAR bought
    back, and buyback coverage of new NEAR, plus the capture that coverage of
    50% would need in that scenario.
    """
    tk = out.get("token")
    sc = getattr(config, "SCENARIOS", None)
    if not tk or not sc:
        return None
    tr = out["trailing"]
    days = out["meta"]["window_days"]
    market_year = tr["market_volume"] * 365.0 / days
    supply = tk["supply_points"][-1]["total_supply_near"] if tk.get("supply_points") else None
    mcap = (raw.get("mcap") or {}).get("usd_market_cap", {}).get(config.SUBJECT)
    if not supply or not mcap:
        return None
    price = mcap / supply
    buyback_part = tk["bought_back_near"] / tk["captured_near"] if tk.get("captured_near") else None
    new_near = tk["annual_issuance_rate"] * supply
    rows = []
    for name in ("bear", "base", "bull"):
        a = sc[name]
        vol = market_year * (1 + a["market_growth"]) * a["share"]
        fees = vol * a["take_bps"] / 1e4
        captured = fees * a["capture"]
        bought = captured * buyback_part / price
        cov = bought / new_near if new_near else None
        rows.append({"name": name, "assumptions": a, "intents_volume": vol, "fees": fees,
                     "captured_usd": captured, "bought_back_near": bought, "coverage": cov,
                     "capture_for_half": (0.5 * new_near * price / buyback_part / fees) if fees and buyback_part else None})
    now_fees = tr["fees"][config.SUBJECT] * 365.0 / days
    return {"rows": rows, "price_usd": price, "new_near_per_year": new_near,
            "market_volume_year_now": market_year, "buyback_part_of_captured": buyback_part,
            "now": {"share": tr["share"][config.SUBJECT], "take_bps": tr["take_bps"][config.SUBJECT],
                    "capture": tr["capture"], "coverage": tk["offset_buyback"], "fees_year": now_fees},
            "horizon": "twelve months after %s" % out["meta"]["last_day"]}


def priced_in(out, raw):
    """What NEAR's price says about Intents, and what Intents is worth to NEAR.

    A perpetuity on the cash Intents sends to NEAR's wallets, value = cash next
    year / (discount - growth), for each discount and growth in
    config.VALUATION, per NEAR and as a part of today's price; the same for each
    scenario at the mid pair; the yearly cash that would on its own justify
    today's market cap; and the yearly cost of new NEAR at today's price, which
    holders pay through dilution whatever Intents earns. NEAR's price also pays
    for the L1, so this is a floor from Intents, not a fair value of NEAR.
    """
    sc, v = out.get("scenarios"), getattr(config, "VALUATION", None)
    tk = out.get("token")
    if not sc or not v or not tk:
        return None
    price = sc["price_usd"]
    supply = tk["supply_points"][-1]["total_supply_near"]
    mcap = price * supply
    days = out["meta"]["window_days"]
    captured_now = tk["captured_near"] * price * 365.0 / days
    bought_now = tk["bought_back_near"] * price * 365.0 / days
    dilution = sc["new_near_per_year"] * price

    def per_near(cash, r, g):
        return cash / (r - g) / supply

    grid = [{"discount": r, "growth": g,
             "captured_per_near": per_near(captured_now, r, g),
             "buyback_per_near": per_near(bought_now, r, g)}
            for r in v["discount"] for g in v["growth"] if r > g]
    r, g = v["mid"]
    rows = []
    for row in sc["rows"]:
        cash = row["captured_usd"]
        bb = cash * sc["buyback_part_of_captured"]
        rows.append({"name": row["name"], "captured_usd": cash, "buyback_usd": bb,
                     "captured_per_near": per_near(cash, r, g),
                     "part_of_price": per_near(cash, r, g) / price,
                     "buyback_minus_dilution_usd": bb - dilution})
    lo = min(x["captured_per_near"] for x in grid)
    hi = max(x["captured_per_near"] for x in grid)
    return {
        "price_usd": price, "supply_near": supply, "market_cap_usd": mcap,
        "captured_usd_year_now": captured_now, "buyback_usd_year_now": bought_now,
        "dilution_usd_year": dilution,
        "buyback_minus_dilution_usd_now": bought_now - dilution,
        "mid": {"discount": r, "growth": g},
        "now_per_near_mid": per_near(captured_now, r, g),
        "now_part_of_price_mid": per_near(captured_now, r, g) / price,
        "now_per_near_range": [lo, hi],
        "now_part_of_price_range": [lo / price, hi / price],
        "cash_to_justify_price": mcap * (r - g),
        "multiple_of_now_to_justify": mcap * (r - g) / captured_now if captured_now else None,
        "grid": grid, "rows": rows,
    }


def investment_call(out):
    """ACCUMULATE, WATCH or AVOID for NEAR, from the computed numbers and config.CALL."""
    c = config.CALL
    tk = out.get("token") or {}
    share90 = out["trailing"]["share"][config.SUBJECT]
    share30 = next((x["share"] for x in out.get("sensitivity") or [] if x["days"] == 30), None)
    week = (out.get("stability") or {}).get("latest_share")
    offset = tk.get("offset_buyback")
    trend = [w["capture"] for w in out.get("capture_trend") or []]
    capture_falling = len(trend) >= 2 and trend[-1] < trend[-2]
    position_lost = share90 < c["share_90d_kill"]
    holds = share30 is not None and share30 >= c["share_30d_hold"]
    captures = offset is not None and offset >= c["buyback_offset_accumulate"]
    if position_lost or capture_falling:
        call = "AVOID"
    elif holds and captures:
        call = "ACCUMULATE"
    else:
        call = "WATCH"
    last = datetime.date.fromisoformat(out["meta"]["last_day"])
    return {
        "call": call,
        "share_90d": share90, "share_30d": share30, "share_latest_week": week,
        "buyback_offset": offset, "capture": trend[-1] if trend else None,
        "capture_prior": trend[-2] if len(trend) >= 2 else None,
        "revenue_multiple_needed": (c["buyback_offset_accumulate"] / offset) if offset else None,
        "position_lost": position_lost, "capture_falling": capture_falling,
        "share_holds": holds, "token_captures": captures,
        "rules": c,
        "review_on": (last + datetime.timedelta(days=c["review_after_days"])).isoformat(),
    }


def tee_prediction_check(raw, table, p):
    """Grade a share prediction from the TEE run made for it, and compare with the build."""
    run = raw.get("tee_run_" + p["id"].lower())
    if not run or not run.get("output"):
        return None
    out = run["output"]
    day = lambda ts: datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")
    days = [day(out["from_ts"]), day(out["to_ts"])]
    due = datetime.date.fromisoformat(p["due"])
    want = [(due - datetime.timedelta(days=p["window_days"] - 1)).isoformat(), p["due"]]
    idx = {d: i for i, d in enumerate(table["dates"])}
    venues = []
    for slug, musd in out["volume_musd"].items():
        build = (sum(table[slug]["volume"][idx[want[0]]:idx[want[1]] + 1]) / 1e6
                 if want[1] in idx and slug in table else None)
        venues.append({"slug": slug, "tee_musd": musd,
                       "build_musd": round(build, 1) if build is not None else None,
                       "agrees": build is not None and abs(build - musd) <= max(0.15, 0.01 * build)})
    run_time = int(run["block_time_ns"]) / 1e9
    tdx = tdx_summary(raw, (run.get("worker") or {}).get("public_key"))
    share = out["share_reported"]
    return {
        "request_tx": run["request_tx"], "explorer": run.get("explorer"),
        "block_height": run["block_height"],
        "run_time_utc": datetime.datetime.fromtimestamp(run_time, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "days": days, "right_days": days == want,
        "after_due_day": run_time >= out["to_ts"] + 86400,
        "checks_pass": all((run.get("checks") or {}).values()),
        "venues": venues, "volumes_agree": all(v["agrees"] for v in venues),
        "share": share, "status": "MET" if share >= p["value"] else "MISSED",
        "tdx": tdx,
    }


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
    valid = [d for d in days if d["day"] <= config.EVENTS_VALID_UNTIL]
    later = [d for d in days if d["day"] > config.EVENTS_VALID_UNTIL]
    if not valid:
        return None
    return {"days": valid, "later_days": later,
            "valid_until": config.EVENTS_VALID_UNTIL,
            "format": raw.get("intents_event_format"),
            "both_ratio_mean": sum(d["both_ratio"] for d in valid) / len(valid),
            "one_ratio_mean": sum(d["one_ratio"] for d in valid) / len(valid),
            "both_sides": all(d["reported_in_both_interval"] and not d["reported_in_one_interval"]
                              for d in valid)}


def bq_check(raw, table, subject):
    """Every day of intents.near's DIP-4 events, from NEAR's public BigQuery dataset."""
    legs, prices = raw.get("bq_intents_legs"), raw.get("bq_prices")
    if not legs or not prices:
        return None
    P = prices["prices"]
    idx = {d: i for i, d in enumerate(table["dates"])}
    by_day, legs_n, unpriced = {}, {}, {}
    for r in legs["rows"]:
        d = by_day.setdefault(r["day"], {"token_diff": 0.0, "transfer": 0.0, "intents": 0})
        if r["event"] == "intents_executed":
            d["intents"] = int(r["n"])
            continue
        legs_n[r["event"]] = legs_n.get(r["event"], 0) + int(r["n"])
        p = P.get(r["asset"])
        price = 1.0 if p and p["stable"] else (p["daily"].get(r["day"]) if p else None)
        if price is None:
            unpriced[r["event"]] = unpriced.get(r["event"], 0) + int(r["n"])
            continue
        # token_diff: what every participant gave (user and solver), i.e. both sides;
        # transfer: every movement between accounts inside the contract.
        raw_amt = int(r["neg_raw"] if r["event"] == "token_diff" else r["pos_raw"])
        d[r["event"]] += raw_amt / 10 ** p["decimals"] * price
    # From September most swaps settle as transfers through 1Click router
    # accounts. A user's deposit into a router and the router's payout back are
    # the two sides of that swap, as the two token_diff entries are for a direct
    # fill. Router-to-solver transfers are the router's own hedging and are not
    # added: counting them too would count the same swap twice.
    routed = {}
    for r in (raw.get("bq_intents_flows") or {}).get("rows", []):
        if {r["sc"], r["rc"]} != {"router", "other"}:
            continue
        p = P.get(r["asset"])
        price = 1.0 if p and p["stable"] else (p["daily"].get(r["day"]) if p else None)
        if price is None:
            continue
        routed[r["day"]] = routed.get(r["day"], 0.0) + int(r["raw"]) / 10 ** p["decimals"] * price
    have_flows = bool(raw.get("bq_intents_flows"))
    days = []
    for day in sorted(by_day):
        if day not in idx:
            continue
        rep = table[subject]["volume"][idx[day]]
        b = by_day[day]
        row = {"day": day, "reported": rep, "token_diff_usd": b["token_diff"],
               "transfer_usd": b["transfer"], "intents_executed": b["intents"],
               "ratio": b["token_diff"] / rep if rep else None}
        if have_flows:
            row["routed_usd"] = routed.get(day, 0.0)
            row["onchain_usd"] = b["token_diff"] + row["routed_usd"]
            row["onchain_ratio"] = row["onchain_usd"] / rep if rep else None
        days.append(row)
    if not days:
        return None
    tol = 0.05

    def summary(rows):
        r = [x["ratio"] for x in rows if x["ratio"] is not None]
        return {"days": len(r), "mean": sum(r) / len(r), "min": min(r), "max": max(r),
                "within_5pct": sum(1 for v in r if abs(v - 1) <= tol)} if r else None
    valid = [d for d in days if d["day"] <= config.EVENTS_VALID_UNTIL]
    later = [d for d in days if d["day"] > config.EVENTS_VALID_UNTIL]
    months = {}
    for d in later:
        months.setdefault(d["day"][:7], []).append(d)
    first_off = next((d["day"] for d in days if d["ratio"] is not None and abs(d["ratio"] - 1) > tol), None)
    rep_total = sum(d["reported"] for d in days)
    onchain = None
    if have_flows:
        def osum(rows):
            r = [x["onchain_ratio"] for x in rows if x["onchain_ratio"] is not None]
            return {"days": len(r), "mean": sum(r) / len(r), "median": statistics.median(r),
                    "min": min(r), "max": max(r),
                    "within_10pct": sum(1 for v in r if abs(v - 1) <= 0.10),
                    "within_20pct": sum(1 for v in r if abs(v - 1) <= 0.20)} if r else None
        months_ = {}
        for d in days:
            months_.setdefault(d["day"][:7], []).append(d)
        onchain = {
            "rule": "token_diff (both sides) plus transfers between 1Click routers and other "
                    "non-solver accounts (both directions); a router is a receiver with at least "
                    "500 distinct senders that day",
            "all": osum(days),
            "from_method_change": osum(later),
            "before_method_change": osum(valid),
            "by_month": {k: osum(v) for k, v in sorted(months_.items())},
            "first_routed_day": next((d["day"] for d in days if d["routed_usd"] > 0), None),
            # How much of the on-chain volume is visible only where it enters and
            # leaves a router, with the fill itself off the public contract.
            "routed_share_by_month": {k: sum(x["routed_usd"] for x in v) / sum(x["onchain_usd"] for x in v)
                                      for k, v in sorted(months_.items())
                                      if sum(x["onchain_usd"] for x in v)},
            "routed_share_last_7": sum(x["routed_usd"] for x in days[-7:]) / sum(x["onchain_usd"] for x in days[-7:]),
            "onchain_over_reported_last_14": sum(x["onchain_usd"] for x in days[-14:]) / sum(x["reported"] for x in days[-14:]),
            "total_over_reported": sum(d["onchain_usd"] for d in days) / rep_total,
            "bytes_billed": raw["bq_intents_flows"].get("bytes_billed"),
        }
    return {
        "onchain": onchain,
        "dataset": legs["dataset"], "range": legs["range"],
        "bytes_billed": legs.get("bytes_billed"), "days": days,
        "valid": summary(valid), "later_by_month": {k: summary(v) for k, v in sorted(months.items())},
        "first_day_off": first_off, "tolerance": tol,
        "token_diff_over_reported": sum(d["token_diff_usd"] for d in days) / rep_total,
        "unpriced_leg_share": {k: unpriced.get(k, 0) / v for k, v in legs_n.items()},
        "assets_priced": sum(1 for v in P.values() if v["stable"] or v["daily"]),
    }


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
    out = _compute(raw, fetched_at)
    out["call"] = investment_call(out)
    out["buyback_provenance"] = buyback_provenance(raw, out["meta"]["window"], out.get("token"))
    out["scenarios"] = scenarios(out, raw)
    out["priced_in"] = priced_in(out, raw)
    return out


def truncate(table, end):
    """The same table, ending on `end` (inclusive)."""
    if end not in table["dates"]:
        return table
    n = table["dates"].index(end) + 1
    return {k: ({f: v[:n] for f, v in val.items()} if k != "dates" else val[:n]) for k, val in table.items()}


def _compute(raw, fetched_at):
    # The thesis is computed on the data it was written and sealed on; days after
    # that are used only to grade the dated predictions.
    table_all = build_table(raw, fetched_at)
    table = truncate(table_all, getattr(config, "THESIS_DATA_END", None))
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
    market_t = market_test(raw, table, halt, names)

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
    events = events_check(raw, table, subject)
    bq = bq_check(raw, table, subject)
    if basis and events:
        measured = shares_measured(basis, table, subject, names, [start_date, end_date],
                                   events["one_ratio_mean"], bridge_volume or None)
        basis["scenarios"].insert(2, measured)
        if "thorchain-dex" in basis["venues"]:
            # How much of THORChain's value would have to be single-pool swaps for
            # the one-side reading to fail C1, or to lose Intents the lead?
            slugs_ = [p["slug"] for p in config.PEERS]
            vol_ = {s_: sum(v for d, v in zip(table["dates"], table[s_]["volume"])
                            if start_date <= d <= end_date) for s_ in slugs_}
            fac = {s_: basis["venues"].get(s_, {}).get("once_factor", 1.0) for s_ in slugs_}
            fac[subject] = 0.5
            others = sum(vol_[s_] * fac[s_] for s_ in slugs_ if s_ not in (subject, "thorchain-dex"))
            mine = vol_[subject] * 0.5
            thor = vol_["thorchain-dex"]
            # share = mine / (mine + others + thor * f) ; f = 1 / (1 + p)
            f_c1 = (mine / t["leader_share"] - mine - others) / thor
            f_lead = mine / thor
            basis["breakpoints"] = {
                "thorchain_double_share_for_c1": (1 / f_c1 - 1) if 0 < f_c1 else None,
                "thorchain_double_share_for_lead": (1 / f_lead - 1) if 0 < f_lead < 1 else 0.0,
                "thorchain_double_share_measured": basis["venues"]["thorchain-dex"].get("double_share_actions"),
                "assumes": "Intents halved; Chainflip and Maya at their measured factors",
            }
        for x in basis["scenarios"]:
            if x["id"] == "worst":
                x["label"] = ("Intents halved, rivals left as reported (inconsistent with the "
                              "rivals' indexers and with intents.near events)")
    if basis:
        slugs_ = [p["slug"] for p in config.PEERS]
        fac_ = {s_: basis["venues"].get(s_, {}).get("once_factor", 1.0) for s_ in slugs_}
        fac_[subject] = events["one_ratio_mean"] if events else 0.5
        extra = shares_onchain(table, subject, names, [start_date, end_date], bq,
                               bridge_volume or None, fac_)
        if extra:
            at = next(i for i, x in enumerate(basis["scenarios"]) if x["id"] == "worst")
            basis["scenarios"][at:at] = extra
        # The same four ways of counting, over 90 days, 30 days and the latest
        # week: the headline shares as ranges rather than points.
        share_ranges = []
        wk = [x["week"] for x in weekly(table)]
        spans = [(w, [table["dates"][last - w + 1], end_date]), (30, [table["dates"][last - 29], end_date])]
        if wk:
            d0 = datetime.date.fromisoformat(wk[-1])
            spans.append((7, [wk[-1], (d0 + datetime.timedelta(days=6)).isoformat()]))
        for days, win in spans:
            v_ = {s_: sum(v for d, v in zip(table["dates"], table[s_]["volume"]) if win[0] <= d <= win[1])
                  for s_ in slugs_}
            vals = {"reported": v_[subject] / sum(v_.values()),
                    "one_side": v_[subject] * fac_[subject] / sum(v_[s_] * fac_[s_] for s_ in slugs_)}
            for x in shares_onchain(table, subject, names, win, bq, None, fac_) or []:
                vals[x["id"]] = x["share"]
            share_ranges.append({"days": days, "window": win, "shares": vals,
                                 "low": min(vals.values()), "high": max(vals.values())})
        basis["share_ranges"] = share_ranges
        by_id = {x["id"]: x for x in basis["scenarios"]}
        like = [by_id[k] for k in ("reported", "one_side", "onchain", "onchain_low") if k in by_id]
        c1_value = min(x["share"] for x in like)
        c1_ok = all(x["share"] > t["leader_share"] and x["leader"] == names[subject] for x in like)
        c1_text = ("NEAR Intents is the largest swap venue with more than %d%% of volume, "
                   "whether volume is taken as reported, one side of each swap is counted "
                   "for every venue, or Intents volume is rebuilt from intents.near itself."
                   % round(100 * t["leader_share"])) if extra else (
                  "NEAR Intents is the largest swap venue with more than %d%% of volume, "
                  "whether volume is taken as reported or one side of each swap is counted "
                  "for every venue." % round(100 * t["leader_share"]))
    else:
        c1_value = share[subject]
        c1_ok = share[subject] > t["leader_share"] and share[subject] == max(share.values())
        c1_text = ("NEAR Intents is the largest venue in the peer set, with more than "
                   "%d%% of volume." % round(100 * t["leader_share"]))
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
    elif raw.get("channels_report"):
        # The committed report keeps only window totals (see pipeline/explorer.py);
        # it describes its own window, which may end before this build's.
        channels = raw["channels_report"]["report"]
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
                     "rivals' figures: on every day rebuilt from intents.near token_diff events "
                     "(through August, where the method applies) it sits inside the both-sides "
                     "interval and outside the one-side interval.",
            "value": sum(1 for d in events["days"] if d["reported_in_both_interval"]
                         and not d["reported_in_one_interval"]),
            "unit": "count", "threshold": len(events["days"]),
            "display": {"value": "%d of %d days" % (
                sum(1 for d in events["days"] if d["reported_in_both_interval"]
                    and not d["reported_in_one_interval"]), len(events["days"])),
                "threshold": "%d of %d" % (len(events["days"]), len(events["days"]))},
            "verdict": _verdict(events["both_sides"]),
        })
    token = token_check(raw, [start_date, end_date])
    if token and token["offset_buyback"] is not None:
        claims.append({
            "id": "C14",
            "claim": "The NEAR bought back with Intents revenue covers at least half of the NEAR "
                     "newly issued in the same window.",
            "value": token["offset_buyback"], "unit": "share", "threshold": t["buyback_offset"],
            "verdict": _verdict(token["offset_buyback"] >= t["buyback_offset"]),
        })
    # The TEE run is a reproducibility check of this build, not evidence for the
    # thesis, so it is reported in the checks section and not counted as a claim.
    tee = tee_check(raw, {"volume": vol, "share": share}, basis, [start_date, end_date])
    if tee:
        tee["matches_build"] = (all(tee["checks"].values()) and tee["same_window"]
                                and tee["share_diff"] <= t["tee_match"])
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
    idx_ = {d: i for i, d in enumerate(table_all["dates"])}
    for p in config.PREDICTIONS:
        value, status = current[p["metric"]], "PENDING"
        if p["due"] in idx_:
            hi = idx_[p["due"]]
            v_ = {x: window_sum(table_all[x]["volume"], hi, w) for x in slugs}
            f_ = window_sum(table_all[subject]["fees"], hi, w)
            r_ = window_sum(table_all[subject]["revenue"], hi, w)
            value = {"share_trailing": v_[subject] / sum(v_.values()) if sum(v_.values()) else None,
                     "capture_trailing": r_ / f_ if f_ else None,
                     "take_rate_trailing_bps": 1e4 * f_ / v_[subject] if v_[subject] else None}[p["metric"]]
            status = "MET" if value is not None and value >= p["value"] else "MISSED"
        predictions.append({**p, "seal": "v1", "current": value, "status": status})
    onchain_days = {d["day"]: d for d in (bq or {}).get("days", []) if "onchain_usd" in d}
    for seal_id, plist in (("v2", config.PREDICTIONS_V2), ("v3", getattr(config, "PREDICTIONS_V3", []))):
        for p in plist:
            value = None
            if p["due"] in idx_:
                hi = idx_[p["due"]]
                lo = hi - p["window_days"] + 1
                v_sub = sum(table_all[subject]["volume"][lo:hi + 1])
                v_riv = [sum(table_all[x]["volume"][lo:hi + 1]) for x in slugs if x != subject]
                v_all = v_sub + sum(v_riv)
                f_sub = sum(table_all[subject]["fees"][lo:hi + 1])
                window_days_ = table_all["dates"][lo:hi + 1]
                if p["metric"] == "share_window":
                    value = v_sub / v_all if v_all else None
                elif p["metric"] == "take_rate_window_bps":
                    value = 1e4 * f_sub / v_sub if v_sub else None
                elif p["metric"] == "lead_window":
                    value = (v_sub - max(v_riv)) / v_all if v_all else None
                elif p["metric"] == "onchain_ratio_window":
                    if all(d in onchain_days for d in window_days_) and v_sub:
                        value = sum(onchain_days[d]["onchain_usd"] for d in window_days_) / v_sub
            if value is None:
                status = "PENDING"
            elif p["op"] == "between":
                status = "MET" if p["value"][0] <= value <= p["value"][1] else "MISSED"
            elif p["op"] == ">":
                status = "MET" if value > p["value"] else "MISSED"
            else:
                status = "MET" if value >= p["value"] else "MISSED"
            entry = {**p, "seal": seal_id, "current": value, "status": status}
            if seal_id == "v2" and p["metric"] == "share_window":
                tp = tee_prediction_check(raw, table_all, p)
                if tp:
                    tp["valid"] = tp["right_days"] and tp["after_due_day"] and tp["checks_pass"]
                    tp["agrees_with_build"] = tp["valid"] and tp["volumes_agree"] and tp["status"] == status
                    entry["tee"] = tp
            predictions.append(entry)

    claims.sort(key=lambda c: int(c["id"][1:]))
    return {
        "meta": {
            "fetched_at": fetched_at,
            "first_day": table["dates"][0],
            "last_day": end_date,
            "window_days": w,
            "window": [start_date, end_date],
            "graded_through": table_all["dates"][-1],
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
        "market_test": market_t,
        "recent": recent,
        "burst": burst,
        "capture_trend": capture_trend,
        "channels": channels,
        "basis": basis,
        "events": events,
        "bq": bq,
        "tee": tee,
        "token": token,
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

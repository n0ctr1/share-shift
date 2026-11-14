"""Download raw series and store them as small, diff-able JSON snapshots."""

import datetime
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from . import config

RAW_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")
DATA_TYPES = {"fees": "dailyFees", "revenue": "dailyRevenue"}


def _get(url, tries=3):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "share-shift/1.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, ValueError) as err:
            last = err
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("could not fetch %s: %s" % (url, last))


def _day(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")


def _series(payload):
    """DefiLlama returns [[unix_ts, usd], ...]; keep it as {date: usd}."""
    out = {}
    for ts, value in payload.get("totalDataChart") or []:
        out[_day(ts)] = float(value or 0)
    return out


def _write(name, obj):
    os.makedirs(RAW_DIR, exist_ok=True)
    path = os.path.join(RAW_DIR, name + ".json")
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
        fh.write("\n")
    return path


def _sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def fetch_all(log=print):
    """Fetch every source. Returns the manifest that is also written to disk."""
    fetched_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files = {}

    for peer in config.PEERS:
        url = config.VOLUME_URL.format(slug=peer["slug"])
        log("fetch volume  " + peer["slug"])
        payload = _get(url)
        files["volume_" + peer["slug"]] = _write("volume_" + peer["slug"], {
            "source": url,
            "methodology": payload.get("methodology"),
            "series": _series(payload),
        })

    for peer in config.PEERS + config.FEE_ONLY:
        for kind, data_type in DATA_TYPES.items():
            if kind == "revenue" and peer in config.FEE_ONLY:
                continue
            url = config.FEES_URL.format(slug=peer["slug"], data_type=data_type)
            log("fetch %-7s %s" % (kind, peer["slug"]))
            payload = _get(url)
            name = "%s_%s" % (kind, peer["slug"])
            files[name] = _write(name, {
                "source": url,
                "methodology": payload.get("methodology"),
                "series": _series(payload),
            })

    for peer in config.WIDE_PEERS:
        url = config.BRIDGE_VOLUME_URL.format(slug=peer["slug"])
        log("fetch bridge  " + peer["slug"])
        payload = _get(url)
        files["widevolume_" + peer["slug"]] = _write("widevolume_" + peer["slug"], {
            "source": url,
            "methodology": payload.get("methodology"),
            "series": _series(payload),
        })

    # THORChain's own numbers, to check the provider against the primary source.
    try:
        log("fetch midgard cross-check")
        payload = _get(config.MIDGARD_URL, tries=2)
        series = {_day(int(i["startTime"])): float(i["totalVolumeUSD"]) / 100.0
                  for i in payload.get("intervals", [])}
    except RuntimeError as err:
        log("midgard unavailable: %s" % err)
        series = {}
    files["crosscheck_midgard"] = _write("crosscheck_midgard", {
        "source": config.MIDGARD_URL,
        "note": "totalVolumeUSD is reported in cents",
        "series": series,
    })

    # Leg breakdown of the two venues that route through their own token.
    for slug, url in config.LEG_SOURCES.items():
        if url.endswith("/graphql"):
            continue  # fetched by its own script (pipeline/chainflip.py)
        try:
            log("fetch legs    " + slug)
            payload = _get(url, tries=2)
            keys = sorted({k for pair in config.LEG_PAIRS for k in pair} | {"totalVolume"})
            series = {_day(int(i["startTime"])): {k: float(i.get(k) or 0) for k in keys}
                      for i in payload.get("intervals", [])}
        except RuntimeError as err:
            log("legs unavailable for %s: %s" % (slug, err))
            series = {}
        files["legs_" + slug] = _write("legs_" + slug, {
            "source": url,
            "note": "Volume by leg type per day, in the venue's own token units (1e8).",
            "series": series,
        })

    # Market caps are a convenience for one table. If CoinGecko rate-limits the
    # request the build continues and the table says the value is missing.
    ids = ",".join(p["coingecko"] for p in config.PEERS)
    url = config.MCAP_URL.format(ids=ids)
    try:
        log("fetch market caps")
        caps = _get(url, tries=2)
        mcap = {p["slug"]: (caps.get(p["coingecko"]) or {}).get("usd_market_cap") for p in config.PEERS}
    except RuntimeError as err:
        log("market caps unavailable: %s" % err)
        mcap = {p["slug"]: None for p in config.PEERS}
    files["mcap"] = _write("mcap", {"source": url, "usd_market_cap": mcap})

    # The Explorer channel report is refreshed separately (python3 -m pipeline.explorer,
    # needs a key and about an hour). If one is on disk it stays in the manifest.
    for name in ("channels_report", "onchain_revenue", "buyback_outflows", "legs_chainflip-amm"):
        path = os.path.join(RAW_DIR, name + ".json")
        if os.path.exists(path):
            files[name] = path
    for fname in sorted(os.listdir(RAW_DIR)):
        if fname.startswith(("intents_events_", "intents_event_format", "tee_run", "near_anchor", "actions_", "near_supply",
                             "near_l1_daily", "bq_", "tdx_quote")) and fname.endswith(".json"):
            files[fname[:-5]] = os.path.join(RAW_DIR, fname)

    manifest = {
        "fetched_at": fetched_at,
        "files": {name: {"path": os.path.relpath(path, os.path.dirname(RAW_DIR)),
                         "sha256": _sha256(path)} for name, path in sorted(files.items())},
    }
    _write("manifest", manifest)
    return manifest


def load_all():
    """Read the snapshot from disk. Raises if the snapshot is missing or altered."""
    manifest_path = os.path.join(RAW_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        raise RuntimeError("no snapshot in data/raw - run `python3 build.py` without --offline first")
    with open(manifest_path) as fh:
        manifest = json.load(fh)
    raw = {}
    for name, meta in manifest["files"].items():
        path = os.path.join(os.path.dirname(RAW_DIR), meta["path"])
        if _sha256(path) != meta["sha256"]:
            raise RuntimeError("%s does not match the hash in manifest.json" % meta["path"])
        with open(path) as fh:
            raw[name] = json.load(fh)
    return manifest, raw

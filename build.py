#!/usr/bin/env python3
"""Rebuild every number, chart and sentence from raw data.

    python3 build.py            fetch fresh data, then build
    python3 build.py --offline  build from the snapshot committed in data/raw

Needs Python 3.9+ and nothing else.
"""

import json
import os
import sys

from pipeline import fetch, metrics, narrative

ROOT = os.path.dirname(os.path.abspath(__file__))


def main(argv):
    offline = "--offline" in argv
    if not offline:
        fetch.fetch_all()
    manifest, raw = fetch.load_all()

    result = metrics.compute(raw, manifest["fetched_at"])
    text = narrative.findings(result)

    os.makedirs(os.path.join(ROOT, "data", "derived"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)

    with open(os.path.join(ROOT, "data", "derived", "metrics.json"), "w") as fh:
        json.dump(result, fh, indent=1, sort_keys=True)
        fh.write("\n")

    with open(os.path.join(ROOT, "THESIS.md"), "w") as fh:
        fh.write(narrative.thesis_markdown(result, text))

    with open(os.path.join(ROOT, "pipeline", "template.html")) as fh:
        template = fh.read()
    payload = json.dumps({"metrics": result, "text": text}).replace("</", "<\\/")
    with open(os.path.join(ROOT, "docs", "index.html"), "w") as fh:
        fh.write(template.replace("__DATA__", payload))

    print("data   %s to %s (fetched %s%s)" % (
        result["meta"]["first_day"], result["meta"]["last_day"],
        manifest["fetched_at"], ", offline" if offline else ""))
    for claim in result["claims"]:
        print("%s  %-14s %s" % (claim["id"], claim["verdict"], claim["claim"]))
    print("wrote  THESIS.md, docs/index.html, data/derived/metrics.json")


if __name__ == "__main__":
    main(sys.argv[1:])

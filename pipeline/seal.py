"""Seal the dated predictions so anyone can check they were not edited later.

    python3 -m pipeline.seal          write predictions/ and request timestamps
    python3 -m pipeline.seal --check  confirm predictions/ still matches config

Writes predictions/predictions.json (canonical JSON of config.PREDICTIONS),
its SHA-256, and an OpenTimestamps proof for that hash. Only the 32-byte hash
leaves the machine. The proof starts "pending" and becomes verifiable against
Bitcoin within a few hours: `ots upgrade predictions/predictions.json.ots`,
then `ots verify predictions/predictions.json.ots` (pip install
opentimestamps-client).
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

from . import config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "predictions")
JSON_PATH = os.path.join(DIR, "predictions.json")
JSON_PATH_V2 = os.path.join(DIR, "predictions-v2.json")
CALENDARS = [
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://a.pool.eternitywall.com",
]
OTS_MAGIC = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"


def canonical():
    body = {"predictions": config.PREDICTIONS,
            "note": "Each prediction is graded by re-running python3 build.py after its due date."}
    return (json.dumps(body, indent=1, sort_keys=True) + "\n").encode()


def canonical_v2():
    body = {"seal": config.SEAL_V2,
            "claim_thresholds": config.THRESHOLDS,
            "predictions": config.PREDICTIONS_V2,
            "note": "Claim thresholds as they stood when this was sealed, and two predictions "
                    "on days after the data the thesis was built on."}
    return (json.dumps(body, indent=1, sort_keys=True) + "\n").encode()


JSON_PATH_V3 = os.path.join(DIR, "predictions-v3.json")


def canonical_v3():
    from . import bq
    body = {"seal": config.SEAL_V3,
            "call_rule": config.CALL,
            "onchain_method": {
                "legs_sql_sha256": hashlib.sha256(bq.LEGS_SQL.strip().encode()).hexdigest(),
                "flows_sql_sha256": hashlib.sha256(bq.FLOWS_SQL.strip().encode()).hexdigest(),
                "rule": "Intents volume = token_diff (both sides) + transfers between 1Click "
                        "routers and other non-solver accounts (both directions)",
            },
            "predictions": config.PREDICTIONS_V3,
            "note": "The investment-call rule, the on-chain counting method and three "
                    "predictions on 2026-11-13 to 2026-12-10, all fixed before that window."}
    return (json.dumps(body, indent=1, sort_keys=True) + "\n").encode()


SEALS = [(JSON_PATH, canonical), (JSON_PATH_V2, canonical_v2), (JSON_PATH_V3, canonical_v3)]


def mismatches():
    """Sealed files that exist and no longer match config."""
    return [os.path.relpath(path, ROOT) for path, body in SEALS
            if os.path.exists(path) and open(path, "rb").read() != body()]


def stamp(digest):
    """Submit the digest to each calendar; return a detached .ots file or None."""
    answers = []
    for url in CALENDARS:
        try:
            req = urllib.request.Request(url + "/digest", data=digest, method="POST",
                                         headers={"Accept": "application/vnd.opentimestamps.v1",
                                                  "User-Agent": "share-shift/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                answers.append((url, resp.read()))
        except (urllib.error.URLError, TimeoutError) as err:
            print("calendar %s did not answer: %s" % (url, err))
    if not answers:
        return None, []
    body = OTS_MAGIC + b"\x01" + b"\x08" + digest
    for i, (_, answer) in enumerate(answers):
        body += (b"\xff" if i < len(answers) - 1 else b"") + answer
    return body, [u for u, _ in answers]


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.check:
        bad = mismatches()
        if bad:
            sys.exit("config no longer matches: %s" % ", ".join(bad))
        for path, body in SEALS:
            if os.path.exists(path):
                print("sealed %s matches config: sha256 %s"
                      % (os.path.basename(path), hashlib.sha256(body()).hexdigest()))
        return
    os.makedirs(DIR, exist_ok=True)
    for path, body in SEALS:
        data = body()
        if os.path.exists(path):
            if open(path, "rb").read() != data:
                sys.exit("%s exists and differs; sealed files are not rewritten."
                         % os.path.relpath(path, ROOT))
            continue
        digest = hashlib.sha256(data).digest()
        with open(path, "wb") as fh:
            fh.write(data)
        with open(path + ".sha256", "w") as fh:
            fh.write("%s  %s\n" % (digest.hex(), os.path.basename(path)))
        proof, used = stamp(digest)
        if proof:
            with open(path + ".ots", "wb") as fh:
                fh.write(proof)
        print("sealed %s: sha256 %s; timestamp requested from %s"
              % (os.path.basename(path), digest.hex(), ", ".join(used) or "none"))


if __name__ == "__main__":
    main(sys.argv[1:])

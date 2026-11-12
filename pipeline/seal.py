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
    data = canonical()
    digest = hashlib.sha256(data).digest()
    if args.check:
        if not os.path.exists(JSON_PATH):
            sys.exit("no sealed predictions yet")
        on_disk = open(JSON_PATH, "rb").read()
        if on_disk != data:
            sys.exit("config.PREDICTIONS no longer matches predictions/predictions.json")
        print("sealed predictions match config: sha256 %s" % digest.hex())
        return
    os.makedirs(DIR, exist_ok=True)
    if os.path.exists(JSON_PATH) and open(JSON_PATH, "rb").read() != data:
        sys.exit("predictions/predictions.json exists and differs; sealed predictions are not "
                 "rewritten. Add new predictions under a new id instead.")
    with open(JSON_PATH, "wb") as fh:
        fh.write(data)
    with open(JSON_PATH + ".sha256", "w") as fh:
        fh.write("%s  predictions.json\n" % digest.hex())
    proof, used = stamp(digest)
    if proof:
        with open(JSON_PATH + ".ots", "wb") as fh:
            fh.write(proof)
    print("sha256 %s" % digest.hex())
    print("timestamp requested from: %s" % (", ".join(used) or "none"))


if __name__ == "__main__":
    main(sys.argv[1:])

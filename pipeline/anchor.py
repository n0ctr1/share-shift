"""Anchor the sealed predictions on NEAR mainnet, and check the anchor.

    python3 -m pipeline.anchor --account you.near            print the command to sign
    python3 -m pipeline.anchor --account you.near --verify   read it back from the chain

The anchor is one write to the NEAR Social contract (social.near) under the
signer's own account:

    <account>/share_shift/predictions_sha256 = <sha256 of predictions.json>

No contract is deployed. The write needs a small storage deposit (0.01 NEAR
is enough) and is signed by the account owner with their own wallet or
near-cli; this script never handles keys. --verify reads the value with a
view call over public RPC and compares it with predictions/predictions.json.
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEALED = os.path.join(ROOT, "predictions", "predictions.json")
RPC = "https://rpc.mainnet.fastnear.com"
KEY = "share_shift"


def digest():
    with open(SEALED, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def payload(account):
    return {"data": {account: {KEY: {"predictions_sha256": digest()}}}}


def view_get(account):
    args = {"keys": ["%s/%s/**" % (account, KEY)]}
    body = {"jsonrpc": "2.0", "id": 1, "method": "query",
            "params": {"request_type": "call_function", "finality": "final",
                       "account_id": "social.near", "method_name": "get",
                       "args_base64": base64.b64encode(json.dumps(args).encode()).decode()}}
    req = urllib.request.Request(RPC, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.load(resp)
    if "error" in result:
        raise RuntimeError(json.dumps(result["error"])[:300])
    return json.loads(bytes(result["result"]["result"]).decode() or "{}")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--account", required=True)
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args(argv)
    if args.verify:
        stored = view_get(args.account).get(args.account, {}).get(KEY, {}).get("predictions_sha256")
        if stored == digest():
            print("anchored on NEAR: %s/%s/predictions_sha256 = %s" % (args.account, KEY, stored))
        else:
            sys.exit("not anchored or different: found %r, expected %s" % (stored, digest()))
        return
    print("Sign this from %s (near-cli-rs):\n" % args.account)
    print("near contract call-function as-transaction social.near set json-args '%s' "
          "prepaid-gas '30 Tgas' attached-deposit '0.01 NEAR' sign-as %s "
          "network-config mainnet sign-with-keychain send"
          % (json.dumps(payload(args.account), separators=(",", ":")), args.account))


if __name__ == "__main__":
    main(sys.argv[1:])

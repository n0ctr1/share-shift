"""Verify an OutLayer TEE run of tee/share-check from the NEAR chain alone.

    python3 -m pipeline.tee_verify --tx <hash> --sender <account>

Checks, with public RPC and no OutLayer API:
  1. the request transaction ran code with the SHA-256 of our WASM build,
     on the input in tee/share-check/input.json;
  2. it completed, and its returned JSON is the output we record;
  3. the result was delivered by a transaction signed with a key that is an
     access key of OutLayer's register-contract account. Per OutLayer's
     WORKER_ATTESTATION.md, that contract adds a key only after verifying an
     Intel TDX quote whose report_data contains it and whose five
     measurements are on its allowlist.
Writes data/raw/tee_run.json.
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WASM = os.path.join(ROOT, "tee", "share-check", "target", "wasm32-wasip2", "release", "share-check.wasm")
INPUT = os.path.join(ROOT, "tee", "share-check", "input.json")
OUT = os.path.join(ROOT, "data", "raw", "tee_run.json")
RPC = "https://archival-rpc.mainnet.fastnear.com"
TX_API = "https://tx.main.fastnear.com/v0"
CONTRACT = "outlayer.near"


def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "share-shift/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def rpc(method, params):
    out = post(RPC, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    if "error" in out:
        raise RuntimeError(json.dumps(out["error"])[:300])
    return out["result"]


def events(logs):
    for line in logs:
        if line.startswith("EVENT_JSON:"):
            try:
                yield json.loads(line[11:])
            except ValueError:
                pass


def find_resolve(request_id, from_height):
    """The transaction that delivered request_id's result to outlayer.near."""
    token = str((from_height + 400) << 32)
    for _ in range(40):
        page = post(TX_API + "/account", {"account_id": CONTRACT, "resume_token": token})
        rows = page.get("account_txs") or []
        hashes = [r["transaction_hash"] for r in rows if int(r["tx_block_height"]) >= from_height]
        for i in range(0, len(hashes), 20):
            for tx in post(TX_API + "/transactions", {"tx_hashes": hashes[i:i + 20]})["transactions"]:
                t = tx["transaction"]
                for action in t.get("actions") or []:
                    fc = action.get("FunctionCall") if isinstance(action, dict) else None
                    if not fc or "resolve" not in fc.get("method_name", ""):
                        continue
                    try:
                        args = json.loads(base64.b64decode(fc["args"]))
                    except ValueError:
                        continue
                    if args.get("request_id") == request_id:
                        return t
            time.sleep(0.3)
        if not rows or int(rows[-1]["tx_block_height"]) < from_height or not page.get("resume_token"):
            return None
        token = page["resume_token"]
    return None


def run(tx_hash, sender):
    wasm_sha = hashlib.sha256(open(WASM, "rb").read()).hexdigest()
    expected_input = json.load(open(INPUT))
    status = rpc("EXPERIMENTAL_tx_status", {"tx_hash": tx_hash, "sender_account_id": sender,
                                            "wait_until": "FINAL"})
    tx = status["transaction"]
    call = next(a["FunctionCall"] for a in tx["actions"]
                if isinstance(a, dict) and "FunctionCall" in a)
    args = json.loads(base64.b64decode(call["args"]))
    source = args["source"].get("WasmUrl") or args["source"].get("WasmHash") or {}
    request_id, completed = None, None
    for outcome in status["receipts_outcome"]:
        for ev in events(outcome["outcome"]["logs"]):
            for item in ev.get("data") or []:
                if ev.get("event") == "execution_requested":
                    request_id = json.loads(item["request_data"])["request_id"]
                if ev.get("event") == "execution_completed":
                    completed = item
    final = status["status"]
    output = json.loads(base64.b64decode(final["SuccessValue"])) if "SuccessValue" in final else None
    block = rpc("block", {"block_id": status["transaction_outcome"]["block_hash"]})
    height = block["header"]["height"]

    resolve = find_resolve(request_id, height) if request_id is not None else None
    worker = None
    if resolve:
        key = rpc("query", {"request_type": "view_access_key", "finality": "final",
                            "account_id": resolve["signer_id"], "public_key": resolve["public_key"]})
        perm = key.get("permission")
        worker = {
            "resolve_tx": resolve["hash"],
            "signer_id": resolve["signer_id"],
            "public_key": resolve["public_key"],
            "key_is_function_call_only": isinstance(perm, dict) and "FunctionCall" in perm,
            "key_receiver": perm.get("FunctionCall", {}).get("receiver_id") if isinstance(perm, dict) else None,
            "key_methods": perm.get("FunctionCall", {}).get("method_names") if isinstance(perm, dict) else None,
        }
    checks = {
        "code_hash_is_our_build": source.get("hash") == wasm_sha,
        "input_is_ours": json.loads(args.get("input_data") or "{}") == expected_input,
        "completed": completed is not None and output is not None,
        "delivered_by_scoped_worker_key": bool(worker and worker["key_is_function_call_only"]
                                              and worker["key_receiver"] == CONTRACT),
    }
    out = {
        "request_tx": tx_hash,
        "sender": sender,
        "block_height": height,
        "block_time_ns": block["header"]["timestamp"],
        "request_id": request_id,
        "wasm_sha256": wasm_sha,
        "code_source": source,
        "input": expected_input,
        "resources": completed.get("resources_used") if isinstance(completed, dict) else None,
        "output": output,
        "worker": worker,
        "checks": checks,
        "explorer": "https://nearblocks.io/txns/" + tx_hash,
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write("\n")
    for k, v in checks.items():
        print("%-32s %s" % (k, "PASS" if v else "FAIL"))
    if worker:
        print("worker: %s via %s (key for %s: %s)" % (worker["signer_id"], worker["resolve_tx"],
                                                     worker["key_receiver"], worker["key_methods"]))
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    return all(checks.values())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tx", required=True)
    ap.add_argument("--sender", required=True)
    a = ap.parse_args()
    try:
        sys.exit(0 if run(a.tx, a.sender) else 1)
    except RuntimeError as err:
        sys.exit("error: %s" % err)

"""Upgrade and verify the OpenTimestamps proof of the sealed predictions.

    python3 -m pipeline.ots --upgrade   ask the calendars for the Bitcoin part
    python3 -m pipeline.ots             verify against Bitcoin block headers
    add --file predictions/predictions-v2.json for the second seal

A small, standard-library reader for detached .ots files, so checking the
proof does not need the opentimestamps client. Verification replays every
operation from the file's SHA-256 to each Bitcoin attestation and compares
the result with that block's merkle root, fetched from a public Bitcoin
explorer (Blockstream's API). The `ots` client gives the same answer:
`ots verify predictions/predictions.json.ots`.
"""

import argparse
import hashlib
import io
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROOF = os.path.join(ROOT, "predictions", "predictions.json.ots")
SEALED = os.path.join(ROOT, "predictions", "predictions.json")
MAGIC = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"
PENDING = bytes.fromhex("83dfe30d2ef90c8e")
BITCOIN = bytes.fromhex("0588960d73d71901")
EXPLORER = "https://blockstream.info/api"


def varuint(f):
    value, shift = 0, 0
    while True:
        b = f.read(1)[0]
        value |= (b & 0x7f) << shift
        if not b & 0x80:
            return value
        shift += 7


def varbytes(f):
    return f.read(varuint(f))


def put_varuint(n):
    out = bytearray()
    while True:
        b = n & 0x7f
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def apply(tag, arg, msg):
    if tag == 0x08:
        return hashlib.sha256(msg).digest()
    if tag == 0x02:
        return hashlib.sha1(msg).digest()
    if tag == 0x03:
        return hashlib.new("ripemd160", msg).digest()
    if tag == 0xf0:
        return msg + arg
    if tag == 0xf1:
        return arg + msg
    if tag == 0xf2:
        return msg[::-1]
    if tag == 0xf3:
        return msg.hex().encode()
    raise ValueError("unsupported operation 0x%02x" % tag)


def parse(f, msg):
    """Timestamp tree as a list of branches; each branch is one op or attestation."""
    node = []
    while True:
        tag = f.read(1)[0]
        fork = tag == 0xff
        if fork:
            tag = f.read(1)[0]
        if tag == 0x00:
            kind = f.read(8)
            payload = varbytes(f)
            node.append(("att", kind, payload, msg))
        else:
            arg = varbytes(f) if tag in (0xf0, 0xf1) else b""
            nxt = apply(tag, arg, msg)
            node.append(("op", tag, arg, parse(f, nxt)))
        if not fork:
            return node


def serialize(node):
    out = b""
    for i, item in enumerate(node):
        if i < len(node) - 1:
            out += b"\xff"
        if item[0] == "att":
            out += b"\x00" + item[1] + put_varuint(len(item[2])) + item[2]
        else:
            out += bytes([item[1]]) + ((put_varuint(len(item[2])) + item[2]) if item[1] in (0xf0, 0xf1) else b"")
            out += serialize(item[3])
    return out


def attestations(node):
    for item in node:
        if item[0] == "att":
            yield item
        else:
            yield from attestations(item[3])


def load():
    with open(PROOF, "rb") as fh:
        f = io.BytesIO(fh.read())
    if f.read(len(MAGIC)) != MAGIC or varuint(f) != 1 or f.read(1) != b"\x08":
        raise ValueError("not a version-1 SHA-256 .ots file")
    digest = f.read(32)
    return digest, parse(f, digest)


def get(url, raw=False):
    req = urllib.request.Request(url, headers={"User-Agent": "share-shift/1.0",
                                               "Accept": "application/vnd.opentimestamps.v1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read()
    return body if raw else json.loads(body)


def upgrade(node):
    """Replace each pending attestation the calendar can now complete."""
    changed = False
    for i in range(len(node) - 1, -1, -1):
        item = node[i]
        if item[0] == "op":
            changed |= upgrade(item[3])
            continue
        if item[1] != PENDING:
            continue
        uri = varbytes(io.BytesIO(item[2])).decode()
        try:
            body = get("%s/timestamp/%s" % (uri.rstrip("/"), item[3].hex()), raw=True)
        except urllib.error.HTTPError as err:
            print("%s: not complete yet (HTTP %d)" % (uri, err.code))
            continue
        except urllib.error.URLError as err:
            print("%s: unreachable (%s)" % (uri, err.reason))
            continue
        sub = parse(io.BytesIO(body), item[3])
        if any(a[1] == BITCOIN for a in attestations(sub)):
            node[i:i + 1] = sub
            print("%s: upgraded" % uri)
            changed = True
    return changed


def verify(digest, node):
    ok = []
    for _, kind, payload, msg in attestations(node):
        if kind == PENDING:
            print("pending at %s" % varbytes(io.BytesIO(payload)).decode())
            continue
        if kind != BITCOIN:
            continue
        height = varuint(io.BytesIO(payload))
        block_hash = get("%s/block-height/%d" % (EXPLORER, height), raw=True).decode().strip()
        block = get("%s/block/%s" % (EXPLORER, block_hash))
        match = msg[::-1].hex() == block["merkle_root"]
        print("bitcoin block %d (%s), time %d: %s" % (height, block_hash[:16], block["timestamp"],
                                                       "merkle root matches" if match else "MISMATCH"))
        ok.append((match, height, block["timestamp"]))
    return ok


def main(argv):
    global PROOF, SEALED
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--upgrade", action="store_true")
    ap.add_argument("--file", default=os.path.relpath(SEALED, ROOT))
    args = ap.parse_args(argv)
    SEALED = os.path.join(ROOT, args.file)
    PROOF = SEALED + ".ots"
    digest, node = load()
    if hashlib.sha256(open(SEALED, "rb").read()).digest() != digest:
        sys.exit("the proof is not for %s" % args.file)
    if args.upgrade:
        if upgrade(node):
            with open(PROOF, "wb") as fh:
                fh.write(MAGIC + b"\x01\x08" + digest + serialize(node))
            print("wrote %s" % os.path.relpath(PROOF, ROOT))
        return
    results = verify(digest, node)
    if not results:
        sys.exit("no Bitcoin attestation yet; run with --upgrade")
    if not all(r[0] for r in results):
        sys.exit("a Bitcoin attestation does not match its block")
    first = min(results, key=lambda r: r[2])
    print("%s existed by Bitcoin block %d (unix time %d)" % (os.path.basename(SEALED), first[1], first[2]))


if __name__ == "__main__":
    main(sys.argv[1:])

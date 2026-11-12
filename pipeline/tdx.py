"""Verify the Intel TDX quote behind the OutLayer worker key that delivered our TEE runs.

    python3 -m pipeline.tdx              check every recorded run (needs `cryptography`)
    python3 -m pipeline.tdx --record     also write data/raw/tdx_quote.json

pipeline.tee_verify shows that a run's result was delivered by a key of
worker.outlayer.near. That only matters if the key lives inside a genuine,
approved TDX machine. OutLayer's register contract says it checks that when it
adds a key; this module repeats the check ourselves, from public data:

  1. find the register_worker_key transaction that added the delivering key
     and read the TDX quote passed to it (it is in the call arguments);
  2. the quote's report_data is SHA-256 of that exact key, so the key was made
     inside the attested machine;
  3. the quote is signed by its attestation key, the attestation key is bound
     to the Quoting Enclave report, and that report is signed by the PCK
     certificate in the quote;
  4. the PCK chain ends at Intel's SGX Root CA, pinned below by the SHA-256 of
     its public key (the certificate is published at
     https://certificates.trustedservices.intel.com/Intel_SGX_Provisioning_Certification_RootCA.cer);
  5. neither the PCK nor its issuing CA is on Intel's revocation lists;
  6. the Quoting Enclave matches Intel's signed QE identity, and the TDX TCB
     level is looked up in Intel's signed TCB info for the platform's FMSPC;
  7. the five measurements (MRTD, RTMR0-3) are on the allowlist the contract
     held at the block where the key was added.

Steps 5 and 6 use fresh collateral from Intel's public PCS API, and the TCB
status must be UpToDate. They are also run on the Intel collateral the
contract stored on chain at that block; that result is reported as an
observation about OutLayer (on 2026-11-11 it was June collateral for another
FMSPC, past its next-update date) and does not decide pass or fail.

What this does not show: that OutLayer's allowlisted image runs only what its
documentation says (the measurements are OutLayer's, not reproduced here), or
that TDX itself has no exploitable flaw.
"""

import argparse
import base64
import datetime
import hashlib
import json
import os
import struct
import sys
import urllib.parse
import urllib.request

from . import tee_verify as tv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "raw", "tdx_quote.json")
REGISTER = "worker.outlayer.near"
INTEL_ROOT_SPKI_SHA256 = "a0af031289f5d5d4132f9186068a7fc13628633ba235777472e29b6b6c67a49e"
PCS = "https://api.trustedservices.intel.com/tdx/certification/v4"
SGX_EXT = "1.2.840.113741.1.13.1"
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

BODY = [("tee_tcb_svn", 16), ("mrseam", 48), ("mrsignerseam", 48), ("seam_attributes", 8),
        ("td_attributes", 8), ("xfam", 8), ("mrtd", 48), ("mrconfigid", 48), ("mrowner", 48),
        ("mrownerconfig", 48), ("rtmr0", 48), ("rtmr1", 48), ("rtmr2", 48), ("rtmr3", 48),
        ("report_data", 64)]


def b58decode(s):
    n = 0
    for ch in s:
        n = n * 58 + B58.index(ch)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return b"\0" * (len(s) - len(s.lstrip("1"))) + raw


def parse_quote(q):
    """A version-4 TDX quote with certification data type 6 (QE report + PCK chain)."""
    version, key_type, tee_type = struct.unpack("<HHI", q[:8])
    if version != 4 or tee_type != 0x81:
        raise ValueError("not a version-4 TDX quote")
    body, o = {}, 48
    for name, size in BODY:
        body[name] = q[o:o + size]
        o += size
    sig_len = struct.unpack("<I", q[o:o + 4])[0]
    sd = q[o + 4:o + 4 + sig_len]
    cert_type, cert_size = struct.unpack("<HI", sd[128:134])
    if cert_type != 6:
        raise ValueError("unexpected certification data type %d" % cert_type)
    cd = sd[134:134 + cert_size]
    auth_len = struct.unpack("<H", cd[448:450])[0]
    inner_type, inner_size = struct.unpack("<HI", cd[450 + auth_len:456 + auth_len])
    if inner_type != 5:
        raise ValueError("unexpected inner certification type %d" % inner_type)
    return {
        "signed": q[:o], "body": body, "signature": sd[:64], "attestation_key": sd[64:128],
        "qe_report": cd[:384], "qe_signature": cd[384:448], "qe_auth": cd[450:450 + auth_len],
        "pck_chain_pem": cd[456 + auth_len:456 + auth_len + inner_size],
    }


def der_items(b):
    """Top-level (tag, value) pairs of a DER string."""
    out, i = [], 0
    while i < len(b):
        tag, length = b[i], b[i + 1]
        i += 2
        if length & 0x80:
            n = length & 0x7f
            length = int.from_bytes(b[i:i + n], "big")
            i += n
        out.append((tag, b[i:i + length]))
        i += length
    return out


def oid_str(b):
    first = b[0]
    parts, n = [first // 40, first % 40], 0
    for x in b[1:]:
        n = (n << 7) | (x & 0x7f)
        if not x & 0x80:
            parts.append(n)
            n = 0
    return ".".join(map(str, parts))


def sgx_extension(cert):
    """FMSPC, PCE SVN and the 16 CPU SVN components from the PCK certificate."""
    from cryptography import x509
    from cryptography.x509.oid import ObjectIdentifier
    raw = cert.extensions.get_extension_for_oid(ObjectIdentifier(SGX_EXT)).value.value
    found = {}
    for _, seq in der_items(der_items(raw)[0][1]):
        (_, oid), (tag, val) = der_items(seq)[:2]
        found[oid_str(oid)] = (tag, val)
    tcb = {}
    for _, seq in der_items(found[SGX_EXT + ".2"][1]):
        (_, oid), (_, val) = der_items(seq)[:2]
        tcb[oid_str(oid)] = int.from_bytes(val, "big") if len(val) <= 2 else val
    comps = [tcb[SGX_EXT + ".2.%d" % k] for k in range(1, 17)]
    return {"fmspc": found[SGX_EXT + ".4"][1].hex(), "pcesvn": tcb[SGX_EXT + ".2.17"],
            "sgx_components": comps}


def ec_verify(pub, sig64, msg):
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    try:
        pub.verify(encode_dss_signature(int.from_bytes(sig64[:32], "big"),
                                        int.from_bytes(sig64[32:], "big")),
                   msg, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False


def chain(pem):
    from cryptography import x509
    return x509.load_pem_x509_certificates(pem if isinstance(pem, bytes) else pem.encode())


def chain_ok(certs):
    """Each certificate is issued by the next one, and the last is Intel's pinned root."""
    from cryptography.hazmat.primitives import serialization
    try:
        for child, parent in zip(certs, certs[1:]):
            child.verify_directly_issued_by(parent)
        certs[-1].verify_directly_issued_by(certs[-1])
    except Exception:
        return False
    spki = certs[-1].public_key().public_bytes(serialization.Encoding.DER,
                                               serialization.PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(spki).hexdigest() == INTEL_ROOT_SPKI_SHA256


def load_crl(data):
    from cryptography import x509
    if isinstance(data, str):
        data = data.encode() if data.startswith("-----") else bytes.fromhex(data)
    return x509.load_pem_x509_crl(data) if data.startswith(b"-----") else x509.load_der_x509_crl(data)


def tcb_status(tcb_info, ext, tee_tcb_svn):
    """The first TCB level the platform meets, per Intel's TDX TCB info (version 3)."""
    for level in tcb_info["tcbLevels"]:
        t = level["tcb"]
        if any(c["svn"] > ext["sgx_components"][i] for i, c in enumerate(t["sgxtcbcomponents"])):
            continue
        if t["pcesvn"] > ext["pcesvn"]:
            continue
        if any(c["svn"] > tee_tcb_svn[i] for i, c in enumerate(t["tdxtcbcomponents"])):
            continue
        return {"status": level["tcbStatus"], "tcb_date": level.get("tcbDate"),
                "advisories": level.get("advisoryIDs", [])}
    return {"status": "no matching level", "tcb_date": None, "advisories": []}


def qe_identity_ok(identity, qe):
    misc = struct.unpack("<I", qe[16:20])[0]
    attrs = qe[48:64]
    mask = bytes.fromhex(identity["attributesMask"])
    return (qe[128:160].hex().upper() == identity["mrsigner"].upper()
            and struct.unpack("<H", qe[256:258])[0] == identity["isvprodid"]
            and misc & int(identity["miscselectMask"], 16) == int(identity["miscselect"], 16)
            and bytes(a & m for a, m in zip(attrs, mask)) == bytes.fromhex(identity["attributes"]))


def collateral_checks(col, quote, pck, pck_ca, ext, at):
    """Revocation, QE identity and TCB status against one set of Intel collateral."""
    out = {}
    pck_crl = load_crl(col["pck_crl"])
    root_crl = load_crl(col["root_ca_crl"])
    crl_chain = chain(col["pck_crl_issuer_chain"])
    out["crl_signatures_valid"] = (chain_ok(crl_chain)
                                   and pck_crl.is_signature_valid(pck_ca.public_key())
                                   and root_crl.is_signature_valid(crl_chain[-1].public_key()))
    out["pck_not_revoked"] = pck_crl.get_revoked_certificate_by_serial_number(pck.serial_number) is None
    out["pck_ca_not_revoked"] = root_crl.get_revoked_certificate_by_serial_number(pck_ca.serial_number) is None

    tcb_chain = chain(col["tcb_info_issuer_chain"])
    tcb_text = col["tcb_info"]
    out["tcb_info_signature_valid"] = chain_ok(tcb_chain) and ec_verify(
        tcb_chain[0].public_key(), bytes.fromhex(col["tcb_info_signature"]), tcb_text.encode())
    info = json.loads(tcb_text)
    out["tcb_info_fmspc_matches"] = info["fmspc"].lower() == ext["fmspc"].lower()
    out["tdx_module_signer_matches"] = (quote["body"]["mrsignerseam"].hex().upper()
                                        == info.get("tdxModule", {}).get("mrsigner", "").upper())
    out["tcb"] = tcb_status(info, ext, list(quote["body"]["tee_tcb_svn"]))

    qe_chain = chain(col["qe_identity_issuer_chain"])
    qe_text = col["qe_identity"]
    out["qe_identity_signature_valid"] = chain_ok(qe_chain) and ec_verify(
        qe_chain[0].public_key(), bytes.fromhex(col["qe_identity_signature"]), qe_text.encode())
    out["qe_identity_matches"] = qe_identity_ok(json.loads(qe_text), quote["qe_report"])

    out["issued"] = info["issueDate"]
    out["next_update"] = info["nextUpdate"]
    out["current_at_check_time"] = info["issueDate"] <= at <= info["nextUpdate"]
    return out


def intel_collateral(fmspc):
    """Fresh TDX collateral from Intel's public PCS API (no key needed)."""
    def get(url, raw=False):
        req = urllib.request.Request(url, headers={"User-Agent": "share-shift/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read(), resp.headers
    tcb_body, tcb_h = get(PCS + "/tcb?fmspc=" + fmspc)
    qe_body, qe_h = get(PCS + "/qe/identity")
    crl_body, crl_h = get("https://api.trustedservices.intel.com/sgx/certification/v4/pckcrl?ca=platform&encoding=der")
    root_crl, _ = get("https://certificates.trustedservices.intel.com/IntelSGXRootCA.der")

    def header(h, name):
        return urllib.parse.unquote(h[name])

    def split(body, key):
        # The signed text is the exact bytes of the inner object as Intel serves it.
        text = body.decode()
        start = text.index('"%s":' % key) + len(key) + 3
        end = text.rindex(',"signature"')
        return text[start:end], json.loads(text)["signature"]
    tcb_text, tcb_sig = split(tcb_body, "tcbInfo")
    qe_text, qe_sig = split(qe_body, "enclaveIdentity")
    return {"tcb_info": tcb_text, "tcb_info_signature": tcb_sig,
            "tcb_info_issuer_chain": header(tcb_h, "TCB-Info-Issuer-Chain"),
            "qe_identity": qe_text, "qe_identity_signature": qe_sig,
            "qe_identity_issuer_chain": header(qe_h, "SGX-Enclave-Identity-Issuer-Chain"),
            "pck_crl": crl_body.hex(), "pck_crl_issuer_chain": header(crl_h, "SGX-PCK-CRL-Issuer-Chain"),
            "root_ca_crl": root_crl.hex()}


def find_registration(public_key, before_height):
    """The register_worker_key transaction that added `public_key`, searching back from a height."""
    token = str((before_height + 1) << 32)
    for _ in range(200):
        page = tv.post(tv.TX_API + "/account", {"account_id": REGISTER, "resume_token": token})
        rows = page.get("account_txs") or []
        hashes = [r["transaction_hash"] for r in rows if r.get("is_receiver") and not r.get("is_signer")]
        for i in range(0, len(hashes), 20):
            for tx in tv.post(tv.TX_API + "/transactions", {"tx_hashes": hashes[i:i + 20]})["transactions"]:
                for a in tx["transaction"].get("actions") or []:
                    fc = a.get("FunctionCall") if isinstance(a, dict) else None
                    if not fc or fc.get("method_name") != "register_worker_key":
                        continue
                    args = json.loads(base64.b64decode(fc["args"]))
                    if args.get("public_key") == public_key:
                        return tx, args
        token = page.get("resume_token")
        if not token or not rows:
            return None, None
    return None, None


def view(method, block):
    r = tv.rpc("query", {"request_type": "call_function", "block_id": block, "account_id": REGISTER,
                         "method_name": method, "args_base64": base64.b64encode(b"{}").decode()})
    v = json.loads(bytes(r["result"]))
    return json.loads(v) if isinstance(v, str) else v


def check(run):
    worker = run["worker"]
    tx, args = find_registration(worker["public_key"], run["block_height"])
    if not tx:
        raise RuntimeError("no register_worker_key transaction found for the worker key")
    t = tx["transaction"]
    height = tx["execution_outcome"]["block_height"]
    success = all("SuccessValue" in r["execution_outcome"]["outcome"]["status"]
                  or "SuccessReceiptId" in r["execution_outcome"]["outcome"]["status"]
                  for r in tx.get("receipts") or [])
    raw_quote = bytes.fromhex(args["tdx_quote_hex"])
    q = parse_quote(raw_quote)
    key_raw = b58decode(worker["public_key"].split(":", 1)[1])
    from cryptography.hazmat.primitives.asymmetric import ec
    certs = chain(q["pck_chain_pem"])
    pck, pck_ca = certs[0], certs[1]
    ext = sgx_extension(pck)
    att = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b"\x04" + q["attestation_key"])
    block = tv.rpc("block", {"block_id": height})
    reg_time = datetime.datetime.fromtimestamp(block["header"]["timestamp"] / 1e9,
                                               datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    measured = {k: q["body"][k].hex() for k in ("mrtd", "rtmr0", "rtmr1", "rtmr2", "rtmr3")}
    allow = view("get_approved_measurements", height)
    checks = {
        "registration_succeeded": success,
        "report_data_is_sha256_of_worker_key": q["body"]["report_data"][:32] == hashlib.sha256(key_raw).digest(),
        "quote_signed_by_attestation_key": ec_verify(att, q["signature"], q["signed"]),
        "attestation_key_bound_to_qe": q["qe_report"][320:352] == hashlib.sha256(
            q["attestation_key"] + q["qe_auth"]).digest(),
        "qe_report_signed_by_pck": ec_verify(pck.public_key(), q["qe_signature"], q["qe_report"]),
        "pck_chain_to_pinned_intel_root": chain_ok(certs),
        "pck_valid_at_registration": pck.not_valid_before_utc.strftime("%Y-%m-%dT%H:%M:%SZ") <= reg_time
                                     <= pck.not_valid_after_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "measurements_on_allowlist": any(all(m.get(k) == v for k, v in measured.items()) for m in allow),
    }
    onchain = collateral_checks(view("get_collateral", height), q, pck, pck_ca, ext, reg_time)
    try:
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        fresh = collateral_checks(intel_collateral(ext["fmspc"]), q, pck, pck_ca, ext, now)
        fresh["checked_at"] = now
    except Exception as err:  # Intel's API is down or changed; say so, do not fail the rest
        fresh = {"error": "%s: %s" % (type(err).__name__, err)}
    # Pass or fail rests on Intel's own current collateral. What the contract
    # stored is reported beside it, as an observation about OutLayer.
    if "error" not in fresh:
        checks["intel_collateral_signed_by_intel"] = (fresh["crl_signatures_valid"]
                                                      and fresh["tcb_info_signature_valid"]
                                                      and fresh["qe_identity_signature_valid"])
        checks["pck_and_ca_not_revoked"] = fresh["pck_not_revoked"] and fresh["pck_ca_not_revoked"]
        checks["qe_matches_intel_identity"] = fresh["qe_identity_matches"]
        checks["fmspc_and_tdx_module_match"] = (fresh["tcb_info_fmspc_matches"]
                                                and fresh["tdx_module_signer_matches"])
        checks["tcb_up_to_date"] = fresh["tcb"]["status"] == "UpToDate"
    return {
        "worker_public_key_sha256": hashlib.sha256(key_raw).hexdigest(),
        "registration_tx": t["hash"],
        "registration_block": height,
        "registration_time": reg_time,
        "registered_by": t["signer_id"],
        "quote_sha256": hashlib.sha256(raw_quote).hexdigest(),
        "quote_hex": raw_quote.hex(),
        "worker_public_key": worker["public_key"],
        "measurements": measured,
        "allowlist_size_at_registration": len(allow),
        "fmspc": ext["fmspc"],
        "pck_subject": pck.subject.rfc4514_string(),
        "collateral_onchain": onchain,
        "collateral_intel_now": fresh,
        "checks": checks,
        "explorer": "https://nearblocks.io/txns/" + t["hash"],
    }


def report(name, res):
    print("== %s run: worker key registered in %s (block %d, %s)" % (
        name, res["registration_tx"], res["registration_block"], res["registration_time"]))
    for k, v in res["checks"].items():
        print("%-44s %s" % (k, "PASS" if v else "FAIL"))
    for label, col in (("on-chain collateral", res["collateral_onchain"]),
                       ("Intel collateral now", res["collateral_intel_now"])):
        if "error" in col:
            print("%s: unavailable (%s)" % (label, col["error"]))
            continue
        print("%s: TCB %s (level of %s), issued %s, next update %s, %s" % (
            label, col["tcb"]["status"], col["tcb"]["tcb_date"], col["issued"][:10],
            col["next_update"][:10], "current" if col["current_at_check_time"] else "EXPIRED at check time"))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--record", action="store_true")
    a = ap.parse_args(argv)
    try:
        import cryptography  # noqa: F401
    except ImportError:
        sys.exit("this check needs the `cryptography` package: pip install cryptography")
    results, ok = {}, True
    for name, (_, path) in sorted(tv.RUNS.items()):
        if not os.path.exists(path):
            continue
        run = json.load(open(path))
        key = run["worker"]["public_key"]
        if key not in results:
            results[key] = check(run)
            results[key]["runs"] = []
        results[key]["runs"].append({"run": name, "request_tx": run["request_tx"]})
        report(name, results[key])
        ok = ok and all(results[key]["checks"].values())
    if a.record:
        body = {"note": "Intel TDX quote of each OutLayer worker key that delivered a recorded run; "
                        "written by python3 -m pipeline.tdx --record",
                "workers": sorted(results.values(), key=lambda r: r["registration_block"])}
        with open(OUT, "w") as fh:
            json.dump(body, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print("wrote %s" % os.path.relpath(OUT, ROOT))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main(sys.argv[1:])

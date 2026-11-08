#!/usr/bin/env python3
"""B3a (audit 2026-11-09) — ambil angka stok dari endpoint API (HANYA GET, + login) per akun demo.

Sandi demo TIDAK ditulis di sini: dibaca dari env `KN_DEMO_PASS` atau dari baris "Login demo" di AGENTS.md.
Pakai:
  python scripts/audit/b3a_api_fetch.py --base http://127.0.0.1:8063 --out <dir> --plan <plan.json>
plan.json = {"accounts": [...email...], "requests": [{"as": email|"*", "name": "...", "path": "/api/...",
             "entity": "<X-Entity-Id opsional>"}]}
Setiap respons disimpan ke <dir>/<akun>__<name>.json beserta status HTTP & header X-Total-Count/X-Truncated.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def demo_password():
    if os.environ.get("KN_DEMO_PASS"):
        return os.environ["KN_DEMO_PASS"]
    txt = open(os.path.join(ROOT, "AGENTS.md"), encoding="utf-8").read()
    m = re.search(r"Login demo:.*?/\s*`([^`]+)`", txt)
    if not m:
        sys.exit("sandi demo tidak ditemukan (set KN_DEMO_PASS)")
    return m.group(1)


def call(base, path, token=None, entity=None, body=None, timeout=120):
    req = urllib.request.Request(base + path, method="POST" if body is not None else "GET")
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if entity:
        req.add_header("X-Entity-Id", entity)
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            raw = r.read()
            return r.status, dict(r.headers), json.loads(raw or b"null"), round(time.time() - t0, 3)
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read() or b"null")
        except Exception:  # noqa: BLE001
            payload = None
        return e.code, dict(e.headers or {}), payload, round(time.time() - t0, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8063")
    ap.add_argument("--out", required=True)
    ap.add_argument("--plan", required=True)
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))
    os.makedirs(a.out, exist_ok=True)
    pw = demo_password()
    tokens, ctx = {}, {}
    for email in plan["accounts"]:
        st, _, body, _ = call(a.base, "/api/auth/login", body={"email": email, "password": pw})
        if st != 200:
            print(f"LOGIN GAGAL {email}: {st} {str(body)[:120]}")
            continue
        tokens[email] = body["token"]
        u = body.get("user", {})
        ctx[email] = {"role": u.get("role"), "home_entity_id": u.get("home_entity_id"),
                      "allowed_entity_ids": u.get("allowed_entity_ids"),
                      "location_site_ids": u.get("location_site_ids"),
                      "location_warehouse_ids": u.get("location_warehouse_ids"),
                      "entity_context": body.get("entity_context")}
    json.dump(ctx, open(os.path.join(a.out, "_accounts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    summary = []
    for rq in plan["requests"]:
        who = list(tokens) if rq.get("as", "*") == "*" else [rq["as"]]
        for email in who:
            if email not in tokens:
                continue
            st, hdr, body, dt = call(a.base, rq["path"], tokens[email], rq.get("entity"))
            tag = email.split("@")[0]
            fn = os.path.join(a.out, f"{tag}__{rq['name']}.json")
            json.dump({"status": st, "elapsed_s": dt, "x_total": hdr.get("X-Total-Count") or hdr.get("x-total-count"),
                       "x_truncated": hdr.get("X-Truncated") or hdr.get("x-truncated"), "path": rq["path"],
                       "entity": rq.get("entity"), "body": body},
                      open(fn, "w", encoding="utf-8"), ensure_ascii=False)
            n = len(body) if isinstance(body, list) else (len(body.get("items", [])) if isinstance(body, dict) and "items" in body else "-")
            summary.append(f"{tag:24s} {rq['name']:34s} {st} {dt:6.2f}s n={n}")
    print("\n".join(summary))


if __name__ == "__main__":
    main()

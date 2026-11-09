"""Audit B2a — pembantu uji alur (HANYA stack sementara kn-tmp-b2a-*, DB test_database).

Dipakai di dalam kontainer backend: `python -i /tmp/b2a/kn.py` atau diimpor skrip lain.
Sandi diambil dari env KN_PW (tidak pernah dicetak).
"""
import json
import os
import sys
import time

import requests
from pymongo import MongoClient

BASE = os.environ.get("KN_BASE", "http://localhost:8001")
PW = os.environ.get("KN_PW", "")
if not PW:  # ambil dari AGENTS.md di kontainer (tidak pernah dicetak)
    import re as _re
    try:
        _m = _re.search(r"`admin@kainnusantara\.id` / `([^`]+)`", open("/app/AGENTS.md", encoding="utf-8").read())
        PW = _m.group(1) if _m else ""
    except OSError:
        PW = ""
mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
db = mc[os.environ.get("DB_NAME", "test_database")]
_S = {}
LOG = []


def login(email, entity=None):
    key = (email, entity)
    if key in _S:
        return _S[key]
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": PW}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"login {email} {r.status_code} {r.text[:200]}")
    d = r.json()
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {d['token']}"
    ent = entity or (d.get("entity_context") or {}).get("active_entity_id") or ""
    if ent:
        s.headers["X-Entity-Id"] = ent
    s.kn = {"email": email, "entity": ent, "user": d.get("user")}
    _S[key] = s
    return s


def call(who, method, path, body=None, params=None, entity=None, files=None, quiet=False):
    s = login(who if "@" in who else f"{who}@kainnusantara.id", entity)
    t0 = time.time()
    if files:
        r = s.request(method, f"{BASE}/api{path}", data=body, files=files, params=params, timeout=120)
    else:
        r = s.request(method, f"{BASE}/api{path}", json=body, params=params, timeout=120)
    try:
        out = r.json()
    except Exception:  # noqa: BLE001
        out = r.text[:500]
    rec = {"who": who, "m": method, "path": path, "code": r.status_code, "ms": int((time.time() - t0) * 1000)}
    LOG.append(rec)
    if not quiet:
        txt = json.dumps(out, ensure_ascii=False, default=str)
        print(f"[{r.status_code}] {who} {method} {path} ({rec['ms']}ms) :: {txt[:700]}")
    return r.status_code, out


def snap(coll, q, proj=None, limit=200):
    p = {"_id": 0}
    if proj:
        for k in proj:
            p[k] = 1
    return list(db[coll].find(q, p).limit(limit))


def count(coll, q=None):
    return db[coll].count_documents(q or {})


def counts(colls):
    return {c: db[c].estimated_document_count() for c in colls}


WATCH = ["inventory_rolls", "inventory_movements", "inventory_balances", "inventory_lots", "journal_entries",
         "audit_logs", "notifications", "wms_tasks", "goods_receipts", "putaway_orders", "inspections",
         "rfid_tags", "rfid_print_jobs", "roll_label_prints", "warehouse_transfers", "cycle_count_sessions",
         "initial_registration_lines", "sales_returns", "purchase_orders", "vendor_bills", "purchase_returns",
         "makloon_orders", "roll_cost_history", "gate_review_cases", "gate_txn_ledger", "registration_area_status"]


def delta(before, after):
    return {k: after[k] - before.get(k, 0) for k in after if after[k] != before.get(k, 0)}


def pj(x, n=3000):
    print(json.dumps(x, ensure_ascii=False, default=str, indent=1)[:n])

"""P01 scope invariants (GN-01, GN-02, GN-03, IX-05, IX-07, IX-10) via HTTP/WS on a LOCAL synthetic DB.

Usage: KN_API=http://127.0.0.1:8009/api MONGO_URL=mongodb://localhost:27017 DB_NAME=test_database python repro_p01_scope.py
Fixture: synthetic role `audit_scope_tester` + user assigned ONLY to entity A (ent_ksc); target B = ent_kanda.
Everything created is removed in `finally` (permission matrix restored).
"""
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import httpx
import websockets
from pymongo import MongoClient

API = os.environ["KN_API"]
WS = API.replace("http", "ws", 1)
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
A, B = "ent_ksc", "ent_kanda"
TAG = f"audit_p01_{uuid.uuid4().hex[:6]}"
EMAIL, PWD = f"{TAG}@synthetic.test", "Synthetic#12345"
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": detail})


def login(email, pwd="demo12345"):
    c = httpx.Client(timeout=30)
    r = c.post(f"{API}/auth/login", json={"email": email, "password": pwd})
    r.raise_for_status()
    return c, r.json()["token"]


matrix_doc = db.permission_settings.find_one({"id": "default"}, {"_id": 0, "matrix": 1})
orig_matrix = json.loads(json.dumps(matrix_doc["matrix"]))
m = json.loads(json.dumps(orig_matrix))
m["audit_scope_tester"] = {**m.get("finance", {}), "entity": ["view", "update"], "period": ["unlock"],
                           "hr": ["view"], "esign": ["view", "sign"], "cash": ["view", "create"]}
db.permission_settings.update_one({"id": "default"}, {"$set": {"matrix": m}})
db.users.insert_one({"id": f"user_{TAG}", "email": EMAIL, "name": "Audit Scope Tester", "role": "audit_scope_tester",
                     "status": "active", "home_entity_id": A, "allowed_entity_ids": [A],
                     "password_hash": bcrypt.hashpw(PWD.encode(), bcrypt.gensalt()).decode()})
so_b = db.sales_orders.find_one({"entity_id": B}, {"_id": 0, "id": 1})["id"]
so_a = db.sales_orders.find_one({"entity_id": A}, {"_id": 0, "id": 1})["id"]
db.document_signatures.insert_many([
    {"id": f"esig_{TAG}_b", "doc_type": "sales_order", "source_id": so_b, "entity_id": B, "status": "signed",
     "signer_name": "Synthetic B", "signed_at": "2026-09-30T00:00:00+00:00"},
    {"id": f"esig_{TAG}_a", "doc_type": "sales_order", "source_id": so_a, "entity_id": A, "status": "signed",
     "signer_name": "Synthetic A", "signed_at": "2026-09-30T00:00:00+00:00"}])
db.period_unlock_requests.insert_one({"id": f"plu_{TAG}", "entity_id": B, "status": "pending", "period_type": "month",
                                      "period_key": "2020-01", "reason": "synthetic", "requested_by": "someone-else",
                                      "created_at": "2026-09-30T00:00:00+00:00"})
settings_b_before = db.system_settings.find_one({"scope": B}, {"_id": 0})
cash_b = db.cash_transactions.find_one({"entity_id": B}, {"_id": 0, "id": 1, "reconciled": 1})
cash_a = db.cash_transactions.find_one({"entity_id": A}, {"_id": 0, "id": 1, "reconciled": 1})
bank_b = db.bank_accounts.find_one({"entity_id": B}, {"_id": 0, "id": 1})["id"]
bank_a = db.bank_accounts.find_one({"entity_id": A}, {"_id": 0, "id": 1})["id"]
expired_tok = f"expired_{TAG}"
sales_user = db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1})["id"]
db.sessions.insert_one({"token": expired_tok, "user_id": sales_user,
                        "expires_at": datetime.now(timezone.utc) - timedelta(hours=1)})
try:
    u, _ = login(EMAIL, PWD)

    # GN-03 — ledger / reconcile lewat ID
    check("GN-03", "ledger own entity (control) 200", u.get(f"{API}/bank-accounts/{bank_a}/ledger").status_code == 200)
    r = u.get(f"{API}/bank-accounts/{bank_b}/ledger")
    check("GN-03", "ledger of entity B denied", r.status_code in (403, 404), r.status_code)
    r = u.post(f"{API}/cash-transactions/{cash_b['id']}/reconcile", json={"reconciled": bool(cash_b.get("reconciled"))})
    check("GN-03", "reconcile txn of entity B denied", r.status_code in (403, 404), r.status_code)
    r = u.post(f"{API}/cash-transactions/{cash_a['id']}/reconcile", json={"reconciled": bool(cash_a.get("reconciled"))})
    check("GN-03", "reconcile own txn (control) 200", r.status_code == 200, r.status_code)

    # IX-05 — metadata e-sign lintas badan usaha
    r = u.get(f"{API}/esign/signatures/sales_order/{so_b}")
    check("IX-05", "signatures of entity B source denied, no metadata", r.status_code in (403, 404) and "Synthetic B" not in r.text, r.status_code)
    r = u.get(f"{API}/esign/signatures/sales_order/{so_a}")
    check("IX-05", "signatures of own source (control) visible", r.status_code == 200 and "Synthetic A" in r.text, r.status_code)
    r = u.post(f"{API}/esign/request", json={"doc_type": "sales_order", "source_id": so_b, "signer_name": "X"})
    check("IX-05", "create e-sign request on entity B source denied", r.status_code in (403, 404), r.status_code)

    # IX-07 — settings scope B
    r = u.put(f"{API}/settings", json={"scope": B, "finance": {"base_currency": "USD"}})
    check("IX-07", "PUT settings scope=B denied", r.status_code == 403, r.status_code)
    after = db.system_settings.find_one({"scope": B}, {"_id": 0})
    check("IX-07", "settings B unchanged after denial", (after or {}).get("finance") == (settings_b_before or {}).get("finance"))
    g_fin = (db.system_settings.find_one({"scope": "global"}, {"_id": 0, "finance": 1}) or {}).get("finance")
    r = u.put(f"{API}/settings", json={"scope": "global", "finance": g_fin})  # nilai sama: tak merusak bila lolos
    check("IX-07", "single-entity user cannot write global scope", r.status_code == 403, r.status_code)

    # IX-10 — period unlock B
    r = u.get(f"{API}/finance/period-unlocks", params={"entity_id": B})
    check("IX-10", "list with entity_id=B denied", r.status_code == 403, r.status_code)
    r = u.get(f"{API}/finance/period-unlocks")
    check("IX-10", "default list excludes B rows", r.status_code == 200 and f"plu_{TAG}" not in r.text, r.status_code)
    r = u.get(f"{API}/finance/period-unlocks/active", params={"entity_id": B})
    check("IX-10", "active with entity_id=B denied", r.status_code == 403, r.status_code)
    r = u.post(f"{API}/finance/period-unlocks/plu_{TAG}/approve")
    st = db.period_unlock_requests.find_one({"id": f"plu_{TAG}"}, {"_id": 0, "status": 1})["status"]
    check("IX-10", "approve B request denied & unchanged", r.status_code in (403, 404) and st == "pending", [r.status_code, st])
    r = u.post(f"{API}/finance/period-unlocks/plu_{TAG}/reject", json={"reason": "x"})
    st = db.period_unlock_requests.find_one({"id": f"plu_{TAG}"}, {"_id": 0, "status": 1})["status"]
    check("IX-10", "reject B request denied & unchanged", r.status_code in (403, 404) and st == "pending", [r.status_code, st])

    # GN-01 — idempotency: cookie users, payload binding, anonymous replay
    key = f"idem-{TAG}"
    w1, _ = login("warehouse@kainnusantara.id")
    w2, _ = login("warehouse2@kainnusantara.id")
    body = {"code": f"UNKNOWN-{TAG}"}
    r1 = w1.post(f"{API}/rfid/roll-scans", json=body, headers={"Idempotency-Key": key})
    r2 = w2.post(f"{API}/rfid/roll-scans", json=body, headers={"Idempotency-Key": key})
    check("GN-01", "second cookie user does not receive first user's cached response",
          r2.headers.get("X-Idempotent-Replay") != "true", [r1.status_code, r2.status_code, r2.headers.get("X-Idempotent-Replay")])
    r3 = w1.post(f"{API}/rfid/roll-scans", json=body, headers={"Idempotency-Key": key})
    check("GN-01", "same user same payload is replayed (control)", r3.headers.get("X-Idempotent-Replay") == "true", r3.status_code)
    r4 = w1.post(f"{API}/rfid/roll-scans", json={"code": f"OTHER-{TAG}"}, headers={"Idempotency-Key": key})
    check("GN-01", "same key different payload -> 409", r4.status_code == 409, r4.status_code)
    r5 = httpx.post(f"{API}/rfid/roll-scans", json=body, headers={"Idempotency-Key": key}, timeout=30)
    check("GN-01", "anonymous replay rejected (401, no cached body)", r5.status_code == 401 and r5.headers.get("X-Idempotent-Replay") != "true", r5.status_code)

    # GN-02 — websocket live tracking
    async def ws_first(token, mode):
        async with websockets.connect(f"{WS}/ws/track?mode={mode}&token={token}") as ws:
            return json.loads(await asyncio.wait_for(ws.recv(), 10))
    _, sales_tok = login("sales@kainnusantara.id")
    first = asyncio.run(ws_first(sales_tok, "subscribe"))
    check("GN-02", "sales cannot subscribe", first.get("type") == "error", first.get("type"))
    first = asyncio.run(ws_first(expired_tok, "subscribe"))
    check("GN-02", "expired session rejected on WS", first.get("type") == "error" and first.get("msg") == "unauthorized", first)
    _, mgr_tok = login("manager@kainnusantara.id")
    first = asyncio.run(ws_first(mgr_tok, "subscribe"))
    check("GN-02", "manager subscribe (control) gets snapshot", first.get("type") == "snapshot", first.get("type"))
finally:
    db.permission_settings.update_one({"id": "default"}, {"$set": {"matrix": orig_matrix}})
    db.users.delete_one({"id": f"user_{TAG}"})
    db.sessions.delete_many({"$or": [{"user_id": f"user_{TAG}"}, {"token": expired_tok}]})
    db.document_signatures.delete_many({"id": {"$in": [f"esig_{TAG}_a", f"esig_{TAG}_b"]}})
    db.period_unlock_requests.delete_one({"id": f"plu_{TAG}"})
    db.idempotency_keys.delete_many({"key": f"idem-{TAG}"})
    db.esign_requests.delete_many({"requested_by": EMAIL})
    if settings_b_before is None:
        db.system_settings.delete_one({"scope": B})
    else:
        db.system_settings.replace_one({"scope": B}, settings_b_before)

print(json.dumps(results, indent=1))
print(f"SUMMARY pass={sum(r['pass'] for r in results)} fail={sum(not r['pass'] for r in results)}")
sys.exit(0 if all(r["pass"] for r in results) else 1)

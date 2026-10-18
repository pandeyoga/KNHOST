"""Regresi HTTP Gelombang 2 (W2-010, W2-025, W2-004). Self-clean. Jalankan dari /app/backend."""
import json
import os
import sys
import uuid

import bcrypt
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
BASE = "http://localhost:8001/api"
A, B = "ent_ksc", "ent_kanda"
T = f"TEST_W2H_{uuid.uuid4().hex[:6]}"
PWD = "demo12345"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
results, users = [], []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


def user(role, **extra):
    uid = f"user_{T}_{role}_{len(users)}".lower()
    db.users.insert_one({"id": uid, "email": f"{uid}@synthetic.test", "name": f"{T} {role}", "role": role,
                         "status": "active", "home_entity_id": A, "allowed_entity_ids": [A],
                         "password_hash": bcrypt.hashpw(PWD.encode(), bcrypt.gensalt()).decode(), **extra})
    users.append(uid)
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": f"{uid}@synthetic.test", "password": PWD}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": A})
    return s


def w2_010():
    s = user("warehouse")
    wh = f"{T}_wh"
    db.rfid_reads.insert_many([
        {"id": f"{T}_rA", "epc": "E1", "warehouse_id": wh, "owner_entity_id": A, "result": "green", "read_type": "gate_out", "timestamp": "2099-01-01T00:00:01"},
        {"id": f"{T}_rB", "epc": "E2", "warehouse_id": wh, "owner_entity_id": B, "result": "red", "read_type": "gate_out", "timestamp": "2099-01-01T00:00:02"}])
    r = s.get(f"{BASE}/rfid/reads", params={"warehouse_id": wh}, timeout=30)
    ids = [x["id"] for x in r.json().get("reads", [])] if r.status_code == 200 else []
    check("W2-010", "user A-only tidak melihat raw read owner B (filter warehouse dipaksa caller)",
          r.status_code == 200 and f"{T}_rB" not in ids and f"{T}_rA" in ids, (r.status_code, ids))
    r = s.get(f"{BASE}/rfid/reads", timeout=30)
    ids = [x["id"] for x in r.json().get("reads", [])]
    check("W2-010", "tanpa filter apa pun tetap tanpa row B", f"{T}_rB" not in ids, len(ids))


def w2_025():
    s = user("md", allowed_line_codes=["woven"])
    base = {"entity_id": A, "status": "draft", "sample_types": ["handfeel"], "created_at": "2099-01-01T00:00:00"}
    db.md_samples.insert_many([{**base, "id": f"{T}_W", "title": "W", "line_code": "woven"},
                               {**base, "id": f"{T}_P", "title": "P", "line_code": "printing"}])
    rw = s.get(f"{BASE}/rnd/samples/{T}_W", timeout=30)
    rp = s.get(f"{BASE}/rnd/samples/{T}_P", timeout=30)
    check("W2-025", "woven-only membuka sample woven (kontrol)", rw.status_code == 200, rw.status_code)
    check("W2-025", "woven-only DITOLAK membuka sample printing", rp.status_code in (403, 404), rp.status_code)
    rpp = s.patch(f"{BASE}/rnd/samples/{T}_P", json={"title": "HACK"}, timeout=30)
    after = db.md_samples.find_one({"id": f"{T}_P"})["title"]
    check("W2-025", "patch sample printing ditolak tanpa mutasi", rpp.status_code in (403, 404) and after == "P", (rpp.status_code, after))


def w2_004():
    adm = requests.Session()
    r = adm.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": PWD}, timeout=30)
    adm.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": A})
    db.vendor_bills.insert_one({"id": f"{T}_vb", "bill_number": f"{T}", "bill_type": "makloon_service", "status": "posted",
                                "entity_id": A, "grand_total": 100.0, "amount_paid": 0, "po_id": ""})
    r = adm.post(f"{BASE}/vendor-bills/{T}_vb/cancel", json={"notes": "uji"}, timeout=30)
    st = db.vendor_bills.find_one({"id": f"{T}_vb"})
    check("W2-004", "cancel generik tagihan jasa makloon ditolak 409, status tetap posted, tanpa kunci tertinggal",
          r.status_code == 409 and st["status"] == "posted" and "saga_lock" not in st, (r.status_code, st["status"]))


def main():
    try:
        for fn in (w2_010, w2_025, w2_004):
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                check(fn.__name__, "harness error", False, repr(e))
    finally:
        db.rfid_reads.delete_many({"id": {"$regex": f"^{T}"}})
        db.md_samples.delete_many({"id": {"$regex": f"^{T}"}})
        db.vendor_bills.delete_many({"id": {"$regex": f"^{T}"}})
        db.users.delete_many({"id": {"$in": users}})
        db.user_sessions.delete_many({"user_id": {"$in": users}})
        db.audit_logs.delete_many({"actor": {"$regex": f"^{T}"}})
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regression_http_results.json")
    json.dump({"tag": T, "passed": sum(r["pass"] for r in results), "total": len(results), "results": results}, open(out, "w"), indent=1)
    for r in results:
        print(("PASS " if r["pass"] else "FAIL ") + r["id"] + " — " + r["invariant"] + ("" if r["pass"] else f" :: {r['detail']}"))
    print(f"{sum(r['pass'] for r in results)}/{len(results)}")
    sys.exit(0 if all(r["pass"] for r in results) else 1)


main()

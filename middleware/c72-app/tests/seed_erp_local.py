#!/usr/bin/env python3
"""Dunia uji untuk ErpLocalTest (klien Java C72 → ERP lokal). HANYA untuk backend UJI sementara — jalankan DI DALAM
kontainer backend (repo = /app):

  python /app/middleware/c72-app/tests/seed_erp_local.py seed   → cetak JSON {device_key, email, password, ...}
  python /app/middleware/c72-app/tests/seed_erp_local.py clean <TAG>

Membuat: site + gudang transit & simpan, perangkat handheld (key acak), operator gudang uji (sandi ACAK, dibuat di
sini), 4 roll bertag di transit → draf PA otomatis → terbit → kirim, 1 roll tanpa tag di gudang simpan. Sesi admin untuk
terbit/kirim PA dibuat langsung di DB (tanpa sandi demo). Menolak DB_NAME selain DB uji.
"""
import json
import os
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone

import requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
from core_utils import hash_password  # noqa: E402
from services.rfid_ingest_service import hash_device_key  # noqa: E402

DBN = os.environ.get("DB_NAME", "")
if DBN not in ("test_database", "kn_test_trial"):
    sys.exit(f"DB_NAME={DBN!r} bukan DB uji — ditolak.")
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[DBN]
API = "http://localhost:8001/api"
ENT = "ent_ksc"


def seed() -> dict:
    tag = uuid.uuid4().hex[:8]
    T = tag.upper()
    site, wt, ws = f"site_C72INT_{tag}", f"wh_C72INT_{tag}_t", f"wh_C72INT_{tag}_s"
    DB.warehouse_sites.insert_one({"id": site, "name": f"C72 Integrasi {tag}", "code": f"CI{tag}", "c72int": tag})
    for wid, code, roles in ((wt, f"CIT{tag}", ["transit", "receiving"]), (ws, f"CIS{tag}", ["storage"])):
        DB.warehouses.insert_one({"id": wid, "name": f"C72 Int {code}", "code": code, "roles": roles, "site_id": site, "city": "Bandung",
                                  "sharing_mode": "shared", "active": True, "gate_config": {"has_gate": False}, "c72int": tag})
    key = f"dk_{secrets.token_hex(16)}"
    dev = f"rdev_C72INT_{tag}"
    DB.rfid_devices.insert_one({"id": dev, "code": f"C72-INT-{T}", "name": f"C72 Integrasi {tag}", "type": "handheld", "direction": "n/a",
                                "warehouse_id": ws, "enabled": True, "status": "online", "api_key_hash": hash_device_key(key),
                                "handheld_scope_level": "site", "c72int": tag})
    pw = secrets.token_urlsafe(14)
    email = f"c72.int.{tag}@contoh.test"
    DB.users.insert_one({"id": f"usr_C72INT_{tag}", "email": email, "name": f"Operator C72 {tag}", "role": "warehouse_admin",
                         "status": "active", "password_hash": hash_password(pw), "home_entity_id": ENT, "allowed_entity_ids": [ENT],
                         "c72int": tag})
    p = DB.products.find_one({"status": {"$ne": "inactive"}, "base_unit": "meter"}, {"_id": 0, "id": 1})
    epcs = []
    for i in range(5):
        rid, tid, e = f"roll_C72INT_{tag}_{i}", f"tag_C72INT_{tag}_{i}", f"E2C7{T}{i:014X}"
        wh = wt if i < 4 else ws
        if i < 4:
            DB.rfid_tags.insert_one({"id": tid, "epc": e, "roll_id": rid, "status": "active", "warehouse_id": wh, "owner_entity_id": ENT, "c72int": tag})
            epcs.append(e)
        DB.inventory_rolls.insert_one({"id": rid, "roll_no": f"CI{T}{i}", "product_id": p["id"], "warehouse_id": wh, "owner_entity_id": ENT,
                                       "status": "available", "length_remaining": 25.0, "length_initial": 25.0, "unit": "meter", "grade": "A",
                                       "lot": "L-C72", "rfid_tag_id": tid if i < 4 else None, "bin_id": None, "active_movement": None,
                                       "length_reserved": 0, "length_reservations": [], "created_at": "2026-11-01T00:00:00+00:00",
                                       "journey": {"stage": "tag_verified", "verified_tag_id": tid, "routing": "store"} if i < 4 else {},
                                       "c72int": tag})
    admin = DB.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0, "id": 1})
    tok = f"tok_C72INT_{secrets.token_hex(12)}"
    DB.sessions.insert_one({"id": f"session_C72INT_{tag}", "token": tok, "user_id": admin["id"], "c72int": tag,
                            "created_at": datetime.now(timezone.utc), "expires_at": datetime.now(timezone.utc) + timedelta(hours=2)})
    h = {"Authorization": f"Bearer {tok}", "X-Entity-Id": ENT}
    r = requests.post(f"{API}/putaway-orders/auto-draft", headers=h, json={"from_warehouse_id": wt}, timeout=60)
    r.raise_for_status()
    drafts = [d for d in r.json()["drafts"] if d.get("to_warehouse_name") == f"C72 Int CIS{tag}"]
    assert drafts, r.json()
    pa = drafts[0]["id"]
    for step in ("publish", "dispatch"):
        requests.post(f"{API}/putaway-orders/{pa}/{step}", headers=h, json={}, timeout=60).raise_for_status()
    DB.putaway_orders.update_one({"id": pa}, {"$set": {"c72int": tag}})
    DB.sessions.delete_one({"token": tok})
    return {"tag": tag, "device_key": key, "email": email, "password": pw, "pa_id": pa, "warehouse_id": ws,
            "epcs": epcs, "untagged_roll": f"roll_C72INT_{tag}_4"}


def clean(tag: str) -> dict:
    out = {}
    rolls = [r["id"] for r in DB.inventory_rolls.find({"$or": [{"c72int": tag}, {"warehouse_id": {"$regex": f"^wh_C72INT_{tag}"}}]}, {"id": 1})]
    pas = [p["id"] for p in DB.putaway_orders.find({"$or": [{"c72int": tag}, {"to_warehouse_id": f"wh_C72INT_{tag}_s"}]}, {"id": 1})]
    sess = [s["id"] for s in DB.rfid_verify_sessions.find({"warehouse_id": {"$regex": f"^wh_C72INT_{tag}"}}, {"id": 1})]
    q = {
        "inventory_rolls": {"id": {"$in": rolls}}, "rfid_tags": {"roll_id": {"$in": rolls}},
        "inventory_movements": {"roll_id": {"$in": rolls}}, "putaway_orders": {"id": {"$in": pas}},
        "rfid_verify_sessions": {"id": {"$in": sess}}, "rfid_cycle_counts": {"session_id": {"$in": sess}},
        "warehouses": {"c72int": tag}, "warehouse_sites": {"c72int": tag}, "rfid_devices": {"c72int": tag},
        "users": {"c72int": tag}, "sessions": {"user_id": f"usr_C72INT_{tag}"},
        "handheld_operator_sessions": {"device_id": f"rdev_C72INT_{tag}"}, "handheld_requests": {"device_id": f"rdev_C72INT_{tag}"},
        "handheld_tag_writes": {"device_id": f"rdev_C72INT_{tag}"}, "inventory_balances": {"warehouse_id": {"$regex": f"^wh_C72INT_{tag}"}},
        "roll_scans": {"roll_id": {"$in": rolls}},
    }
    for c, f in q.items():
        out[c] = DB[c].delete_many(f).deleted_count
    return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["seed"]:
        print(json.dumps(seed()))
    elif sys.argv[1:2] == ["clean"] and len(sys.argv) == 3:
        print(json.dumps(clean(sys.argv[2])))
    else:
        sys.exit(__doc__)

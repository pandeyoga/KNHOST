"""UAT 24 Okt (P9.4) — bekal uji putaway: putaway kini hanya ke gudang simpan di LOKASI yang sama, jadi roll
siap-putaway disiapkan di gudang transit Rancamalang (RCM-TRANSIT), lokasi yang punya gudang simpan & Gedung Retur.

`seed()` menyalin beberapa roll tersedia dari gudang simpan Rancamalang ke RCM-TRANSIT, lalu mencetak & memverifikasi
tag RFID lewat API (→ `tag_verified`). `cleanup()` menghapus salinan, tag, PA-nya, dan membangun ulang saldo.
"""
import os
import sys
import uuid

import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PREFIX = "roll_TEST_PA_"


def _db():
    return MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def seed(base_url: str, headers: dict, n: int = 3):
    db = _db()
    tr = db.warehouses.find_one({"code": "RCM-TRANSIT"}, {"_id": 0})
    if not tr:
        return None, []
    stor = [w["id"] for w in db.warehouses.find({"site_id": tr.get("site_id"), "roles": "storage",
                                                 "code": {"$ne": "RCM-RETUR"}, "active": {"$ne": False}}, {"id": 1})]
    owner = headers.get("X-Entity-Id") or ""
    src = list(db.inventory_rolls.find({"warehouse_id": {"$in": stor}, "status": "available",
                                        **({"owner_entity_id": owner} if owner else {}),
                                        "length_reserved": {"$in": [0, None]}, "length_remaining": {"$gt": 1},
                                        "grade": {"$in": ["A", None, ""]}}, {"_id": 0}).limit(n))
    tag = uuid.uuid4().hex[:6]
    ids = []
    for i, r in enumerate(src):
        rid = f"{PREFIX}{tag}_{i}"
        doc = {**r, "id": rid, "roll_no": f"TPA{tag}{i}".upper(), "warehouse_id": tr["id"],
               "journey": {"stage": "received_transit", "routing": "store"}, "active_movement": None,
               "length_reserved": 0, "length_reservations": [], "earmarked_for": None, "reserved_ref": None}
        doc.pop("rfid_tag_id", None)
        db.inventory_rolls.insert_one(doc)
        ids.append(rid)
    if not ids:
        return tr["id"], []
    job = requests.post(f"{base_url}/api/rfid/print-jobs", headers=headers, json={"roll_ids": ids}, timeout=120).json()
    epcs = [i["epc"] for i in job.get("items") or []]
    requests.post(f"{base_url}/api/rfid/print-jobs/{job['id']}/mark-printed", headers=headers, timeout=90)
    sess = requests.post(f"{base_url}/api/rfid/print-jobs/{job['id']}/verify/start", headers=headers, timeout=90).json()
    requests.post(f"{base_url}/api/rfid/verify-sessions/{sess['id']}/scan", headers=headers, json={"epcs": epcs}, timeout=90)
    requests.post(f"{base_url}/api/rfid/verify-sessions/{sess['id']}/complete", headers=headers, timeout=90)
    return tr["id"], ids


def cleanup():
    db = _db()
    rolls = list(db.inventory_rolls.find({"$or": [{"id": {"$regex": f"^{PREFIX}"}},
                                                  {"parent_roll_id": {"$regex": f"^{PREFIX}"}}]},
                                         {"_id": 0, "id": 1, "product_id": 1, "owner_entity_id": 1}))
    if not rolls:
        return
    ids = [r["id"] for r in rolls]
    whs = {m.get("warehouse_id") for m in db.inventory_movements.find({"roll_id": {"$in": ids}}, {"warehouse_id": 1})}
    whs |= {w["id"] for w in db.warehouses.find({"code": {"$regex": "^RCM-"}}, {"id": 1})}
    keys = {(r["product_id"], r.get("owner_entity_id") or "") for r in rolls}
    db.rfid_tags.delete_many({"roll_id": {"$in": ids}})
    db.putaway_orders.delete_many({"items.roll_id": {"$in": ids}})
    db.inventory_movements.delete_many({"roll_id": {"$in": ids}})
    db.inventory_rolls.delete_many({"id": {"$in": ids}})
    from _shared_loop import run
    from services.roll_service import rebuild_balance
    for pid, own in keys:
        for wid in whs:
            if wid:
                run(rebuild_balance(pid, wid, own))

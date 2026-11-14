"""PK-30 U15 — di MongoDB ASLI: dua persetujuan tugas gudang antar-PT bersamaan (pesan 100 m, roll pilihan 130 m).

Harapan: satu 200, satu 409; satu `length_adjustment`; tiap jurnal pasangan (`seller`, `buyer`, `adj:seller`,
`adj:buyer`, `cogs`, `receipt`) tepat sekali. Uji HTTP terhadap backend yang berjalan (`REACT_APP_BACKEND_URL`);
produk, gudang, kontrak, dan roll disisipkan ke database uji lokal (fixture). Pengaturan PPN data acuan tidak diubah:
angka yang diperiksa adalah DPP (30 m × Rp 25.000 = Rp 750.000; 130 m × Rp 25.000 = Rp 3.250.000).
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pymongo
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
KSC, KANDA = "ent_ksc", "ent_kanda"


def _login():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"},
                      timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": KSC}


def test_U15_dua_persetujuan_bersamaan():
    h = _login()
    sfx = uuid.uuid4().hex[:6]
    pid_prod, wh, rid = f"prd_bp30_{sfx}", f"wh_bp30_{sfx}", f"roll_bp30_{sfx}"
    DB.products.insert_one({"id": pid_prod, "sku": f"BP30-{sfx}", "name": "Kain Uji PK-30", "base_unit": "meter",
                            "is_active": True, "status": "active"})
    DB.warehouses.insert_one({"id": wh, "code": f"WH-BP30-{sfx}", "name": "Gudang Bersama PK-30", "is_active": True,
                              "status": "active"})
    DB.supplier_contracts.insert_one({"id": f"ctr_bp30_{sfx}", "contract_number": f"KTR-BP30-{sfx}",
                                      "entity_id": KSC, "partner_kind": "entity", "partner_id": KANDA,
                                      "product_id": pid_prod, "status": "active", "tariff_rate": 25_000,
                                      "valid_from": "2026-01-01"})
    DB.inventory_rolls.insert_one({"id": rid, "roll_no": f"R-{sfx}", "product_id": pid_prod, "warehouse_id": wh,
                                   "owner_entity_id": KSC, "status": "available", "reserved_ref": None,
                                   "length_initial": 130.0, "length_remaining": 130.0, "unit": "meter",
                                   "unit_cost": 18_000, "base_unit_cost": 18_000, "lot": f"LOT-BP30-{sfx}",
                                   "active_movement": None})
    r = requests.post(f"{BASE}/interco/transactions", headers=h, timeout=60, json={
        "seller_entity_id": KSC, "buyer_entity_id": KANDA,
        "items": [{"product_id": pid_prod, "quantity": 100}]})
    assert r.status_code == 200, r.text
    pair = r.json()["pair_id"]
    sid = r.json()["seller"]["id"]
    DB.interco_transactions.update_many({"pair_id": pair}, {"$set": {"items.0.preferred_roll_ids": [rid]}})
    r = requests.post(f"{BASE}/interco/transactions/{sid}/confirm", headers=h, timeout=60, json={"note": ""})
    assert r.status_code == 200, r.text
    r = requests.post(f"{BASE}/interco/transactions/{sid}/warehouse-task", headers=h, timeout=60,
                      json={"note": ""})
    assert r.status_code == 200, r.text
    tid = r.json()["id"]

    def setujui(_):
        return requests.post(f"{BASE}/transfers/{tid}/approve", headers=h, timeout=120,
                             json={"approved_by": "Uji PK-30"}).status_code
    with ThreadPoolExecutor(2) as ex:
        codes = sorted(ex.map(setujui, range(2)))
    assert codes == [200, 409], codes
    docs = list(DB.interco_transactions.find({"pair_id": pair}))
    assert len(docs) == 2
    for d in docs:
        assert d["length_adjustment"]["transfer_id"] == tid
        assert d["length_adjustment"]["delta_subtotal"] == 750_000
        assert d["items"][0]["quantity"] == 130 and d["subtotal"] == 3_250_000
    for akhiran in ("seller", "buyer", "adj:seller", "adj:buyer", "cogs", "receipt"):
        assert DB.journal_entries.count_documents({"source_type": "interco_transaction",
                                                   "source_id": f"{pair}:{akhiran}",
                                                   "status": {"$ne": "void"}}) == 1, akhiran
    assert DB.inventory_rolls.find_one({"id": rid})["owner_entity_id"] == KANDA

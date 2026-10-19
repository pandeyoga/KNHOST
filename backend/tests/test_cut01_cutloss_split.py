"""CUT-01..05 — pemecahan roll cutloss setelah QC: baik / BS / dibuang + SJ potongan baik."""
import os
import uuid

import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
T = uuid.uuid4().hex[:6]


def _login(email, pw="demo1234"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


ADMIN = _login("admin@kainnusantara.id", "demo12345")
MD = _login("md@kainnusantara.id")
SADM = _login("salesadmin@kainnusantara.id")


def _seed(treatment):
    src = DB.inventory_rolls.find_one({"status": "available", "owner_entity_id": "ent_ksc", "unit": "yard",
                                       "length_remaining": {"$gte": 100}, "unit_cost": {"$gt": 0}}, {"_id": 0})
    assert src, "butuh roll yard ent_ksc ≥100"
    roll = {**src, "id": f"roll_TEST_{T}_{treatment}", "roll_no": f"TEST_RL-{T}-{treatment}", "status": "quarantine",
            "length_remaining": 120.0, "length": 120.0, "length_initial": 120.0, "rfid_tag_id": None, "weight_kg": 24.0}
    DB.inventory_rolls.insert_one(dict(roll))
    rid = f"sret_TEST_{T}_{treatment}"
    DB.sales_returns.insert_one({"id": rid, "number": f"TEST_RET-{T}-{treatment}", "status": "inspected", "entity_id": "ent_ksc",
                                 "order_id": "", "order_number": "TEST_SO", "customer_id": "", "customer_name": "TEST Customer",
                                 "items": [{"product_id": roll["product_id"], "product_name": "TEST", "quantity_returned": 120, "unit": "yard"}]})
    return rid, roll


def _cleanup():
    rolls = [r["id"] for r in DB.inventory_rolls.find({"$or": [{"id": {"$regex": f"^roll_TEST_{T}"}},
                                                              {"cutloss_piece.return_id": {"$regex": f"^sret_TEST_{T}"}}]}, {"id": 1})]
    DB.inventory_rolls.delete_many({"id": {"$in": rolls}})
    DB.inventory_movements.delete_many({"roll_id": {"$in": rolls}})
    DB.journal_entries.delete_many({"source_type": "return_cutloss", "source_label": {"$regex": f"TEST_"}})
    DB.journal_entries.delete_many({"source_type": "return_cutloss", "description": {"$regex": f"TEST_|SJ-"}, "source_id": {"$regex": "^ctl_"}})
    DB.shipments.delete_many({"return_id": {"$regex": f"^sret_TEST_{T}"}})
    DB.sales_returns.delete_many({"id": {"$regex": f"^sret_TEST_{T}"}})


def test_cutloss_split_bs_and_dispose_and_return_sj():
    try:
        rid, roll = _seed("bs")
        # Sales admin bukan pemilih BS/Dibuang (CUT-02, bawaan MD).
        r = requests.post(f"{BASE}/sales-returns/{rid}/cutloss", headers=SADM, json={
            "product_id": roll["product_id"], "roll_id": roll["id"], "defect_from": 45, "defect_to": 60, "treatment": "bs"})
        assert r.status_code == 403, r.text
        r = requests.post(f"{BASE}/sales-returns/{rid}/cutloss", headers=MD, json={
            "product_id": roll["product_id"], "roll_id": roll["id"], "defect_from": 45, "defect_to": 60, "treatment": "bs"})
        assert r.status_code == 200, r.text
        ctl = r.json()["id"]
        pv = requests.get(f"{BASE}/sales-returns/{rid}/cutloss/{ctl}/split-preview", headers=MD).json()
        assert [(p["kind"], p["qty"]) for p in pv["pieces"]] == [("good", 45), ("defect", 15), ("good", 60)]
        sp = requests.post(f"{BASE}/sales-returns/{rid}/cutloss/{ctl}/split", headers=MD)
        assert sp.status_code == 200, sp.text
        pieces = sp.json()["pieces"]
        assert pieces[1]["status"] == "available" and pieces[1]["grade"] == "BS"
        assert DB.inventory_rolls.find_one({"id": roll["id"]})["length_remaining"] == 45
        assert requests.post(f"{BASE}/sales-returns/{rid}/cutloss/{ctl}/split", headers=MD).status_code == 400
        sj = requests.post(f"{BASE}/sales-returns/{rid}/cutloss/{ctl}/return-shipment", headers=MD)
        assert sj.status_code == 200, sj.text
        assert sj.json()["ref_order_number"] == "TEST_SO" and len(sj.json()["rolls"]) == 2

        rid2, roll2 = _seed("dispose")
        r = requests.post(f"{BASE}/sales-returns/{rid2}/cutloss", headers=MD, json={
            "product_id": roll2["product_id"], "roll_id": roll2["id"], "defect_yard": 20, "treatment": "dispose"})
        ctl2 = r.json()["id"]
        sp = requests.post(f"{BASE}/sales-returns/{rid2}/cutloss/{ctl2}/split", headers=ADMIN).json()
        bad = [p for p in sp["pieces"] if p["kind"] == "defect"][0]
        assert bad["status"] == "damaged" and bad["qty"] == 20 and bad.get("journal_entry_number")
    finally:
        _cleanup()

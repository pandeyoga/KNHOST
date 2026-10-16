"""L05 LN-051/052 — form inspect per interval 15 yard tanpa batas 150; kg tetap kg; versi aturan tersimpan."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]


def _h(email="qc@kainnusantara.id", pw="demo1234"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"}, timeout=30)
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture()
def fx():
    made = []

    def mk(unit):
        roll = DB.inventory_rolls.find_one({"unit": unit, "status": "available", "owner_entity_id": "ent_ksc"}, {"_id": 0})
        if not roll:
            pytest.skip(f"tak ada roll {unit}")
        iid = f"ins_test_{uuid.uuid4().hex[:8]}"
        DB.inspections.insert_one({"id": iid, "number": "TEST-L05", "kind": "random_check", "status": "in_progress",
                                   "entity_id": "ent_ksc", "customer": {"name": "TEST Customer"}, "history": [],
                                   "lines": [{"id": "ln1", "roll_id": roll["id"], "roll_no": roll.get("roll_no"),
                                              "product_id": roll["product_id"], "quantity": roll["length_remaining"],
                                              "unit": unit}]})
        made.append((iid, roll))
        return iid, roll
    yield mk
    for iid, roll in made:
        DB.inventory_rolls.replace_one({"id": roll["id"]}, roll)
        DB.inspections.delete_one({"id": iid})


def _inspect(h, iid, body):
    return requests.post(f"{BASE}/inspections/{iid}/lines/ln1/inspect", json={"part": "qc", **body}, headers=h, timeout=30)


def test_t02_165_yard_multiple_defects_same_interval_kept(fx):
    iid, roll = fx("yard")
    defects = [{"interval": 3, "code": "SL", "point_value": 2, "count": 1, "note": "slub"},
               {"interval": 3, "code": "HL", "point_value": 4, "count": 1, "note": "lubang"},
               {"interval": 10, "code": "OS", "point_value": 1, "count": 3, "note": "> 150 yd"}]
    r = _inspect(_h(), iid, {"inspect_length_yard": 165, "defects": defects})
    assert r.status_code == 200, r.text[:300]
    ln = DB.inspections.find_one({"id": iid})["lines"][0]
    assert len(ln["defects"]) == 3 and sum(1 for d in ln["defects"] if d["interval"] == 3) == 2
    d10 = next(d for d in ln["defects"] if d["interval"] == 10)
    assert d10["from_yard"] == 150 and d10["to_yard"] == 165 and d10["code"] == "OS"
    assert ln["inspect_form"]["intervals"] == 11 and ln["inspect_form"]["inspect_length_yard"] == 165
    assert ln["points_snapshot"] == 2 + 4 + 3
    assert ln["grade_rule"]["status"] == "candidate_unvalidated" and ln["grade_rule"]["pending_decision"] == "KLX-02"
    hdr = ln["inspect_form"]["header"]
    assert hdr["customer_name"] == "TEST Customer" and hdr["roll_no"] == roll.get("roll_no") and hdr["inspected_date"]
    # interval di luar panjang → ditolak jelas
    r = _inspect(_h(), iid, {"inspect_length_yard": 100, "defects": [{"interval": 11, "point_value": 1, "count": 1}]})
    assert r.status_code == 400 and "Interval" in r.text


def test_t01_kg_roll_inspected_in_yard_stays_kg(fx):
    iid, roll = fx("kg")
    r = _inspect(_h(), iid, {"inspect_length_yard": 124, "defects": [{"interval": 8, "point_value": 3, "count": 1}]})
    assert r.status_code == 200, r.text[:300]
    after = DB.inventory_rolls.find_one({"id": roll["id"]}, {"_id": 0})
    assert after["unit"] == "kg" and after["length_remaining"] == roll["length_remaining"]
    f = DB.inspections.find_one({"id": iid})["lines"][0]["inspect_form"]
    assert f["stock_unit"] == "kg" and f["inspect_length_yard"] == 124 and f["stock_qty"] == roll["length_remaining"]


def test_t02_history_kept_after_reinspection_rule_snapshot(fx):
    iid, roll = fx("yard")
    _inspect(_h(), iid, {"inspect_length_yard": 60, "defects": [{"interval": 0, "point_value": 4, "count": 2}]})
    first = DB.inspections.find_one({"id": iid})["lines"][0]
    assert first["grade_rule"]["thresholds"] and first["grade_rule"]["version"] == "4point_sum_v1"
    assert first["points_snapshot"] == 8


def test_ln050_t03_random_from_scan_and_scope():
    h = _h()
    roll = DB.inventory_rolls.find_one({"status": "available", "owner_entity_id": "ent_ksc", "earmarked_for": {"$in": [None, ""]}},
                                       {"_id": 0})
    other = DB.inventory_rolls.find_one({"status": "available", "owner_entity_id": {"$nin": ["ent_ksc", None, ""]}}, {"_id": 0})
    if other:
        r = requests.post(f"{BASE}/inspections/random-check", json={"scan_code": other["roll_no"]}, headers=h, timeout=30)
        assert r.status_code in (400, 403, 409) and "cakupan" in r.text
    assert requests.post(f"{BASE}/inspections/random-check", json={"scan_code": "TIDAK-ADA-XYZ"}, headers=h, timeout=30).status_code in (400, 404, 409)
    r = requests.post(f"{BASE}/inspections/random-check", json={"scan_code": roll["roll_no"]}, headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]
    doc = r.json()
    try:
        assert [ln["roll_id"] for ln in doc["lines"]] == [roll["id"]] and doc["ref_doc_id"] == roll["warehouse_id"]
    finally:
        DB.inspections.delete_one({"id": doc["id"]})
        DB.inventory_rolls.replace_one({"id": roll["id"]}, roll)

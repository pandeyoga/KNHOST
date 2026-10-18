"""T1 iter194 — L05 LN-050-T02 replacement SPK + LN-051 edge cases (interval count, validation)."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


def _h(email="admin@kainnusantara.id", pw="demo12345"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture()
def ret():
    rolls = list(DB.inventory_rolls.find({"status": "available", "owner_entity_id": "ent_ksc"}, {"_id": 0}).limit(3))
    if len(rolls) < 3:
        pytest.skip("butuh 3 roll")
    rid = f"sret_TEST_{uuid.uuid4().hex[:6]}"
    DB.sales_returns.insert_one({"id": rid, "number": "TEST-RET-L05", "entity_id": "ent_ksc", "status": "received",
                                 "customer_id": "c1", "customer_name": "TEST Cust",
                                 "items": [{"roll_id": rolls[0]["id"], "roll_no": rolls[0].get("roll_no"),
                                            "product_id": rolls[0]["product_id"], "quantity": 1, "unit": rolls[0]["unit"]}]})
    yield rid, rolls
    for i in DB.inspections.find({"ref_doc_id": rid}, {"_id": 0, "id": 1}):
        DB.inspections.delete_one({"id": i["id"]})
    DB.sales_returns.delete_one({"id": rid})


# LN-050-T02 replacement SPK
def test_replacement_requires_roll_ids(ret):
    rid, _ = ret
    r = requests.post(f"{BASE}/inspections", json={"kind": "replacement", "ref_doc_id": rid}, headers=_h(), timeout=30)
    assert r.status_code == 400 and "PENGGANTI" in r.text


def test_replacement_rejects_returned_roll(ret):
    rid, rolls = ret
    r = requests.post(f"{BASE}/inspections", json={"kind": "replacement", "ref_doc_id": rid, "roll_ids": [rolls[0]["id"]]},
                      headers=_h(), timeout=30)
    assert r.status_code == 400 and "retur" in r.text.lower()


def test_replacement_unknown_roll(ret):
    rid, _ = ret
    r = requests.post(f"{BASE}/inspections", json={"kind": "replacement", "ref_doc_id": rid, "roll_ids": ["nope_xyz"]},
                      headers=_h(), timeout=30)
    assert r.status_code == 400


def test_replacement_lines_are_replacement_rolls_and_return_untouched(ret):
    rid, rolls = ret
    r = requests.post(f"{BASE}/inspections", json={"kind": "replacement", "ref_doc_id": rid,
                                                   "roll_ids": [rolls[1]["id"], rolls[2].get("roll_no") or rolls[2]["id"]]},
                      headers=_h(), timeout=30)
    assert r.status_code == 200, r.text[:300]
    doc = r.json()
    assert doc["kind"] == "replacement"
    assert sorted(ln["roll_id"] for ln in doc["lines"]) == sorted([rolls[1]["id"], rolls[2]["id"]])
    assert DB.sales_returns.find_one({"id": rid}).get("inspection_id") in (None, "")


# LN-051 edge: interval counts
@pytest.fixture()
def ins():
    roll = DB.inventory_rolls.find_one({"unit": "yard", "status": "available", "owner_entity_id": "ent_ksc"}, {"_id": 0})
    iid = f"ins_test_{uuid.uuid4().hex[:8]}"
    DB.inspections.insert_one({"id": iid, "number": "TEST-L05X", "kind": "random_check", "status": "in_progress",
                               "entity_id": "ent_ksc", "history": [],
                               "lines": [{"id": "ln1", "roll_id": roll["id"], "roll_no": roll.get("roll_no"),
                                          "product_id": roll["product_id"], "quantity": roll["length_remaining"], "unit": "yard"}]})
    yield iid
    DB.inventory_rolls.replace_one({"id": roll["id"]}, roll)
    DB.inspections.delete_one({"id": iid})


@pytest.mark.parametrize("length,expect", [(150, 10), (151, 11), (100, 10), (300, 20)])
def test_interval_count(ins, length, expect):
    r = requests.post(f"{BASE}/inspections/{ins}/lines/ln1/inspect",
                      json={"part": "qc", "inspect_length_yard": length, "defects": []}, headers=_h(), timeout=30)
    assert r.status_code == 200, r.text[:300]
    assert DB.inspections.find_one({"id": ins})["lines"][0]["inspect_form"]["intervals"] == expect


@pytest.mark.parametrize("bad", [{"interval": -1, "point_value": 1, "count": 1},
                                 {"interval": 0, "point_value": 5, "count": 1},
                                 {"interval": 0, "point_value": 1, "count": -2}])
def test_defect_validation(ins, bad):
    r = requests.post(f"{BASE}/inspections/{ins}/lines/ln1/inspect",
                      json={"part": "qc", "inspect_length_yard": 100, "defects": [bad]}, headers=_h(), timeout=30)
    assert r.status_code in (400, 422), f"{bad} -> {r.status_code} {r.text[:200]}"


# iter195 — replacement: sold/consumed roll rejected; id + roll_no of same roll accepted
@pytest.mark.parametrize("status", ["sold", "consumed"])
def test_replacement_rejects_sold_consumed(ret, status):
    rid, rolls = ret
    DB.inventory_rolls.update_one({"id": rolls[1]["id"]}, {"$set": {"status": status}})
    try:
        r = requests.post(f"{BASE}/inspections", json={"kind": "replacement", "ref_doc_id": rid, "roll_ids": [rolls[1]["id"]]},
                          headers=_h(), timeout=30)
        assert r.status_code == 400, r.text[:300]
        assert "terjual" in r.text.lower() or "terpakai" in r.text.lower()
    finally:
        DB.inventory_rolls.update_one({"id": rolls[1]["id"]}, {"$set": {"status": rolls[1]["status"]}})


def test_replacement_id_and_rollno_same_roll(ret):
    rid, rolls = ret
    r = requests.post(f"{BASE}/inspections", json={"kind": "replacement", "ref_doc_id": rid,
                                                   "roll_ids": [rolls[1]["id"], rolls[1]["roll_no"]]}, headers=_h(), timeout=30)
    assert r.status_code in (200, 201), r.text[:300]
    lines = r.json().get("lines") or r.json().get("inspection", {}).get("lines") or []
    assert len([ln for ln in lines if ln.get("roll_id") == rolls[1]["id"]]) == 1

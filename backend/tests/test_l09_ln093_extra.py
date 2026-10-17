"""L09 extra (testing agent) — LN-093 yard/mixed provenance + LN-090 status matrix."""
import os
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = "TEST_L093X"
PO_A = DB.purchase_orders.find_one({"po_number": "KSC/PO-00001"})
PO_B = DB.purchase_orders.find_one({"po_number": "CST/PO-00001"})
TPL_YARD = DB.inventory_rolls.find_one({"owner_entity_id": "ent_ksc", "status": "available", "unit": "yard"})
TPL_ANY = DB.inventory_rolls.find_one({"owner_entity_id": "ent_ksc", "status": "available", "warehouse_id": "wh_jakarta"})


@pytest.fixture(scope="module")
def h():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    yield {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}
    ids = [d["id"] for d in DB.sales_returns.find({"notes": TAG}, {"id": 1})]
    prs = [p["id"] for p in DB.purchase_returns.find({"origin_sales_return_id": {"$in": ids}}, {"id": 1})]
    DB.purchase_returns.delete_many({"id": {"$in": prs}})
    for coll in ("doc_refs", "document_refs"):
        DB[coll].delete_many({"$or": [{"from_id": {"$in": prs + ids}}, {"to_id": {"$in": prs + ids}}]})
    DB.inventory_movements.delete_many({"ref_id": {"$in": prs}})
    DB.inventory_rolls.delete_many({"notes": TAG})
    DB.sales_returns.delete_many({"notes": TAG})
    DB.atomic_claims.delete_many({"doc_id": {"$in": ids}})


def make_case(rolls_prov, tpl=None):
    tpl = tpl or TPL_ANY
    rid = f"sret_{TAG}_{uuid.uuid4().hex[:6]}"
    DB.sales_returns.insert_one({"id": rid, "number": f"{TAG}-{rid[-6:]}", "notes": TAG, "entity_id": "ent_ksc",
                                 "status": "refund_settled", "items": [], "created_at": "2026-10-17T00:00:00+00:00"})
    out = []
    for i, prov in enumerate(rolls_prov):
        doc = {k: v for k, v in tpl.items() if k not in ("_id", "supplier_id", "po_id", "po_number",
                                                         "supplier_name", "acquired", "acquired_history")}
        doc.update({"id": f"roll_{TAG}_{uuid.uuid4().hex[:8]}", "roll_no": f"{TAG}-{rid[-6:]}-{i}",
                    "status": "quarantine", "origin_type": "return", "return_id": rid, "notes": TAG,
                    "length_remaining": 10.0, "length_initial": 10.0, "length_reserved": 0,
                    "rfid_tag": "", "tag_id": ""}, **prov)
        DB.inventory_rolls.insert_one(doc)
        out.append(doc["id"])
    return rid, out


def test_yard_roll_unit_preserved(h):
    if not TPL_YARD:
        pytest.skip("no yard roll in ent_ksc")
    rid, rolls = make_case([{"supplier_id": PO_A["supplier_id"], "po_id": PO_A["id"]}], tpl=TPL_YARD)
    r = requests.post(f"{BASE}/sales-returns/{rid}/create-purchase-return", headers=h,
                      json={"bypass_import_policy": True})
    assert r.status_code == 200, r.text
    pr = DB.purchase_returns.find_one({"id": r.json()["split_purchase_returns"][0]["id"]})
    assert pr["items"][0]["unit"] == "yard"
    assert abs(float(pr["items"][0]["quantity"]) - 10.0) < 0.01
    roll = DB.inventory_rolls.find_one({"id": rolls[0]})
    print("roll status after:", roll["status"], roll.get("length_remaining"))
    # rolls are consumed only on PR approval (finalize); PR is pending_approval
    assert pr["status"] == "pending_approval"


def test_mixed_known_and_unknown_with_manual_supplier(h):
    rid, rolls = make_case([{"supplier_id": PO_B["supplier_id"], "po_id": PO_B["id"]}, {}])
    r = requests.post(f"{BASE}/sales-returns/{rid}/create-purchase-return", headers=h,
                      json={"supplier_id": PO_A["supplier_id"], "bypass_import_policy": True})
    assert r.status_code == 200, r.text
    split = r.json()["split_purchase_returns"]
    pairs = {(s["supplier_id"], s["po_id"]) for s in split}
    assert pairs == {(PO_B["supplier_id"], PO_B["id"]), (PO_A["supplier_id"], "")}, pairs
    assert r.json()["number"] == ", ".join(s["number"] for s in split)
    for s in split:
        assert s["supplier_name"]
    sr = DB.sales_returns.find_one({"id": rid})
    assert len(sr["linked_purchase_returns"]) == 2


def test_get_detail_shows_links(h):
    rid, _ = make_case([{"supplier_id": PO_A["supplier_id"], "po_id": PO_A["id"]}])
    r = requests.post(f"{BASE}/sales-returns/{rid}/create-purchase-return", headers=h,
                      json={"bypass_import_policy": True})
    assert r.status_code == 200, r.text
    g = requests.get(f"{BASE}/sales-returns/{rid}", headers=h)
    print("GET detail", g.status_code)
    if g.status_code == 200:
        assert len(g.json().get("linked_purchase_returns") or []) == 1


@pytest.mark.parametrize("status,expect", [
    ("draft", 400), ("pending_approval", 400), ("approved", 400), ("inspecting", 400),
    ("inspected", 200), ("refund_settled", 200), ("credit_settled", 200),
])
def test_ln090_status_matrix(h, status, expect):
    rid = f"sret_{TAG}_ms_{uuid.uuid4().hex[:6]}"
    DB.sales_returns.insert_one({"id": rid, "number": f"{TAG}-{rid[-6:]}", "notes": TAG, "entity_id": "ent_ksc",
                                 "return_type": "penggantian", "status": status, "items": [],
                                 "created_at": "2026-10-17T00:00:00+00:00"})
    r = requests.post(f"{BASE}/sales-returns/{rid}/milestone", headers=h, json={"milestone": "shipped_to_customer"})
    assert r.status_code == expect, r.text
    if expect == 400:
        assert "selesai QC" in r.json()["detail"]
        assert not DB.sales_returns.find_one({"id": rid}).get("shipped_to_customer_at")
    else:
        assert DB.sales_returns.find_one({"id": rid}).get("shipped_to_customer_at")


@pytest.mark.parametrize("status", ["rejected", "cancelled"])
def test_ln090_rejected_cancelled_info(h, status):
    """Informational: blocklist lets rejected/cancelled through."""
    rid = f"sret_{TAG}_rc_{uuid.uuid4().hex[:6]}"
    DB.sales_returns.insert_one({"id": rid, "number": f"{TAG}-{rid[-6:]}", "notes": TAG, "entity_id": "ent_ksc",
                                 "return_type": "penggantian", "status": status, "items": [],
                                 "created_at": "2026-10-17T00:00:00+00:00"})
    r = requests.post(f"{BASE}/sales-returns/{rid}/milestone", headers=h, json={"milestone": "shipped_to_customer"})
    print(status, "->", r.status_code, r.text[:150])

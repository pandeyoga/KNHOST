"""L09 — LN-093-T02 retur supplier dipisah per provenance roll · LN-090-T01 pengganti diblok sebelum QC."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = "TEST_L093"
PO_A = DB.purchase_orders.find_one({"po_number": "KSC/PO-00001"})
PO_B = DB.purchase_orders.find_one({"po_number": "CST/PO-00001"})
PO_C = DB.purchase_orders.find_one({"po_number": "KANDA/PO-00001"})
TEMPLATE = DB.inventory_rolls.find_one({"owner_entity_id": "ent_ksc", "status": "available", "warehouse_id": "wh_jakarta"})


@pytest.fixture(scope="module")
def h():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    yield {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}
    ids = [d["id"] for d in DB.sales_returns.find({"notes": TAG}, {"id": 1})]
    prs = [p["id"] for p in DB.purchase_returns.find({"origin_sales_return_id": {"$in": ids}}, {"id": 1})]
    DB.purchase_returns.delete_many({"id": {"$in": prs}})
    for coll in ("doc_refs", "document_refs"):
        DB[coll].delete_many({"$or": [{"from_id": {"$in": prs + ids}}, {"to_id": {"$in": prs + ids}}]})
    DB.inventory_rolls.delete_many({"notes": TAG})
    DB.sales_returns.delete_many({"notes": TAG})
    DB.atomic_claims.delete_many({"doc_id": {"$in": ids}}) if "atomic_claims" in DB.list_collection_names() else None


def make_case(rolls_prov):
    rid = f"sret_{TAG}_{uuid.uuid4().hex[:6]}"
    DB.sales_returns.insert_one({"id": rid, "number": f"{TAG}-{rid[-6:]}", "notes": TAG, "entity_id": "ent_ksc",
                                 "status": "refund_settled", "items": [], "created_at": "2026-10-17T00:00:00+00:00"})
    out = []
    for i, prov in enumerate(rolls_prov):
        doc = {k: v for k, v in TEMPLATE.items() if k not in ("_id", "supplier_id", "po_id", "po_number",
                                                              "supplier_name", "acquired", "acquired_history")}
        doc.update({"id": f"roll_{TAG}_{uuid.uuid4().hex[:8]}", "roll_no": f"{TAG}-{rid[-6:]}-{i}",
                    "status": "quarantine", "origin_type": "return", "return_id": rid, "notes": TAG,
                    "length_remaining": 10.0, "length_reserved": 0, "rfid_tag": "", "tag_id": ""}, **prov)
        DB.inventory_rolls.insert_one(doc)
        out.append(doc["id"])
    return rid, out


def test_t02_split_by_roll_provenance_not_latest_po(h):
    rid, rolls = make_case([
        {"supplier_id": PO_A["supplier_id"], "po_id": PO_A["id"], "po_number": PO_A["po_number"]},
        {"supplier_id": PO_B["supplier_id"], "po_id": PO_B["id"], "po_number": PO_B["po_number"]},
        {"acquired": {"via": "inbound", "ref_id": PO_C["id"], "date": "2026-10-01"}},
    ])
    r = requests.post(f"{BASE}/sales-returns/{rid}/create-purchase-return", headers=h,
                      json={"bypass_import_policy": True})
    assert r.status_code == 200, r.text
    split = r.json()["split_purchase_returns"]
    assert {(s["supplier_id"], s["po_id"]) for s in split} == {
        (PO_A["supplier_id"], PO_A["id"]), (PO_B["supplier_id"], PO_B["id"]), (PO_C["supplier_id"], PO_C["id"])}
    for s in split:
        pr = DB.purchase_returns.find_one({"id": s["id"]})
        assert pr["origin_sales_return_id"] == rid
        assert len([x for it in pr["items"] for x in it.get("roll_ids", [])]) == 1
    sr = DB.sales_returns.find_one({"id": rid})
    assert len(sr["linked_purchase_returns"]) == 3
    again = requests.post(f"{BASE}/sales-returns/{rid}/create-purchase-return", headers=h,
                          json={"bypass_import_policy": True})
    assert again.status_code in (400, 409)
    assert DB.purchase_returns.count_documents({"origin_sales_return_id": rid}) == 3


def test_unknown_provenance_needs_manual_supplier(h):
    rid, _ = make_case([{}])
    r = requests.post(f"{BASE}/sales-returns/{rid}/create-purchase-return", headers=h, json={})
    assert r.status_code == 400 and "tidak tercatat" in r.json()["detail"]
    r = requests.post(f"{BASE}/sales-returns/{rid}/create-purchase-return", headers=h,
                      json={"supplier_id": PO_A["supplier_id"], "bypass_import_policy": True})
    assert r.status_code == 200, r.text
    assert r.json()["split_purchase_returns"][0]["supplier_id"] == PO_A["supplier_id"]


def test_parallel_create_makes_one_set(h):
    rid, _ = make_case([{"supplier_id": PO_A["supplier_id"], "po_id": PO_A["id"]},
                        {"supplier_id": PO_B["supplier_id"], "po_id": PO_B["id"]}])

    def call(_):
        return requests.post(f"{BASE}/sales-returns/{rid}/create-purchase-return", headers=h,
                             json={"bypass_import_policy": True}).status_code
    with ThreadPoolExecutor(4) as ex:
        codes = list(ex.map(call, range(4)))
    assert codes.count(200) == 1, codes
    assert DB.purchase_returns.count_documents({"origin_sales_return_id": rid}) == 2


def test_ln090_t01_replacement_blocked_before_qc(h):
    rid = f"sret_{TAG}_rep"
    DB.sales_returns.insert_one({"id": rid, "number": f"{TAG}-REP", "notes": TAG, "entity_id": "ent_ksc",
                                 "return_type": "penggantian", "status": "approved", "items": [],
                                 "created_at": "2026-10-17T00:00:00+00:00"})
    moves = DB.inventory_movements.count_documents({})
    jes = DB.journal_entries.count_documents({})
    r = requests.post(f"{BASE}/sales-returns/{rid}/milestone", headers=h, json={"milestone": "shipped_to_customer"})
    assert r.status_code == 400 and "selesai QC" in r.json()["detail"]
    assert DB.inventory_movements.count_documents({}) == moves and DB.journal_entries.count_documents({}) == jes
    DB.sales_returns.update_one({"id": rid}, {"$set": {"status": "inspected"}})
    r = requests.post(f"{BASE}/sales-returns/{rid}/milestone", headers=h, json={"milestone": "shipped_to_customer"})
    assert r.status_code == 200, r.text

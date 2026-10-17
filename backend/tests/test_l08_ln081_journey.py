"""L08 LN-081 — perjalanan fisik terpisah dari QC/keputusan/uang dalam satu timeline."""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
TAG = "TEST_L081"
SO = DB.sales_orders.find_one({"number": "KSC/SO-00001"})
JKT = "wh_jakarta"
RCM_TRANSIT = DB.warehouses.find_one({"name": "Rancamalang · Gudang Transit"})["id"]
RCM_QC = DB.warehouses.find_one({"name": {"$regex": "^Rancamalang · Gudang Retur"}})["id"]


@pytest.fixture(scope="module")
def h():
    before = {r["id"]: r for r in DB.inventory_rolls.find({"status": "delivered"})}
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    hh = {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}
    yield hh
    ids = [d["id"] for d in DB.sales_returns.find({"notes": TAG}, {"id": 1})]
    for d in DB.sales_returns.find({"id": {"$in": ids}, "status": {"$in": ["refund_settled", "credit_settled"]}}):
        requests.post(f"{BASE}/sales-returns/{d['id']}/reverse", headers=hh, json={"notes": "cleanup TEST_L081"})
    DB.inventory_rolls.delete_many({"return_id": {"$in": ids}, "returned_identity": {"$ne": True}})
    for rid, doc in before.items():
        cur = DB.inventory_rolls.find_one({"id": rid}, {"return_history": 1, "status": 1})
        if cur and (cur.get("status") != "delivered" or any(x.get("return_id") in ids for x in cur.get("return_history") or [])):
            DB.inventory_rolls.replace_one({"id": rid}, doc)
    for coll in ("credit_notes", "journal_entries", "cash_transactions", "inventory_movements"):
        DB[coll].delete_many({"$or": [{"return_id": {"$in": ids}}, {"ref_id": {"$in": ids}}, {"source_id": {"$in": ids}}]})
    DB.sales_returns.delete_many({"notes": TAG})


def whole_roll(h, idx):
    data = requests.get(f"{BASE}/sales-returns/returnable", headers=h, params={"order_id": SO["id"]}).json()
    return [r for r in data["rolls"] if r["remaining"] >= r["shipped_qty"] - 0.01][idx]


def new_approved(h, roll):
    r = requests.post(f"{BASE}/sales-returns", headers=h, json={
        "order_id": SO["id"], "return_type": "retur", "notes": TAG, "submit_now": True,
        "items": [{"product_id": roll["product_id"], "quantity_returned": roll["remaining"], "unit": roll["unit"],
                   "roll_ids": [roll["roll_id"]], "roll_qtys": {roll["roll_id"]: roll["remaining"]}, "reason": "cacat"}]})
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    assert requests.post(f"{BASE}/sales-returns/{rid}/approve", headers=h, json={"notes": ""}).status_code == 200
    return rid


def scan(h, rid, stage, code, wh, to=""):
    return requests.post(f"{BASE}/sales-returns/{rid}/journey/scan", headers=h, json={
        "stage": stage, "codes": [code], "warehouse_id": wh, "to_warehouse_id": to, "carrier": "Sopir TEST"})


def test_t01_jakarta_transit_qc_by_scans_only(h):
    roll = whole_roll(h, 0)
    rid = new_approved(h, roll)
    no = roll["roll_no"]
    r = scan(h, rid, "received", no, JKT)
    assert r.status_code == 200, r.text
    assert r.json()["event"]["doc_no"].endswith("/TRM-1")
    assert scan(h, rid, "received", no, JKT).status_code == 400          # tidak bisa diterima dua kali
    assert requests.post(f"{BASE}/sales-returns/{rid}/inspect/start", headers=h, json={}).status_code == 200
    r = scan(h, rid, "dispatched", no, JKT, RCM_QC)
    assert r.status_code == 200 and r.json()["event"]["doc_no"].endswith("/SJ-1")
    tl = requests.get(f"{BASE}/sales-returns/{rid}/timeline", headers=h).json()
    assert tl["rolls"][0]["location_stage"] == "in_transit" and "Dalam perjalanan" in tl["rolls"][0]["location"]
    done = requests.post(f"{BASE}/sales-returns/{rid}/inspect/complete", headers=h,
                         json={"inspections": [{"index": 0, "grade": "A", "condition": "ok"}]})
    assert done.status_code == 400 and "perjalanan" in done.json()["detail"]   # QC tidak mendahului barang
    assert scan(h, rid, "arrived", no, RCM_TRANSIT).status_code == 400  # salah gudang tujuan
    r = scan(h, rid, "arrived", no, RCM_QC)
    assert r.status_code == 200, r.text
    loc = r.json()["roll_locations"][roll["roll_id"]]
    assert loc["stage"] == "arrived" and loc["warehouse_id"] == RCM_QC and loc["is_qc_area"] is True
    tl = requests.get(f"{BASE}/sales-returns/{rid}/timeline", headers=h).json()
    assert tl["rolls"][0]["location"].startswith("Area QC")
    inbound = [e for e in tl["events"] if e["lane"] == "inbound"]
    assert [e["doc_no"].split("/")[-1] for e in inbound] == ["TRM-1", "SJ-1", "TBA-1"]
    # roll di inventori TIDAK berpindah karena scan sebelum penyelesaian (masih tercatat di pelanggan)
    assert DB.inventory_rolls.find_one({"id": roll["roll_id"]})["status"] == "delivered"
    assert requests.post(f"{BASE}/sales-returns/{rid}/inspect/complete", headers=h,
                         json={"inspections": [{"index": 0, "grade": "A", "condition": "ok"}]}).status_code == 200
    bad = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=h,
                        json={"outcome": "refund", "return_warehouse_id": JKT})
    assert bad.status_code == 400 and "lokasi fisik" in bad.json()["detail"]
    ok = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=h,
                       json={"outcome": "refund", "decision_note": "ACC Pak Budi via WA"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["decision"]["note"] == "ACC Pak Budi via WA"
    assert ok.json()["decision"]["permission"] == "sales_return.approve"
    stock = DB.inventory_rolls.find_one({"id": roll["roll_id"]})
    assert stock["status"] == "quarantine" and stock["warehouse_id"] == RCM_QC
    rel = requests.post(f"{BASE}/sales-returns/{rid}/relocate", headers=h, json={"to_warehouse_id": JKT})
    assert rel.status_code == 409                                        # tidak ada pindah gudang instan
    tl = requests.get(f"{BASE}/sales-returns/{rid}/timeline", headers=h).json()
    lanes = {e["lane"] for e in tl["events"]}
    assert {"approval", "inbound", "qc", "disposition", "settlement"} <= lanes
    assert any("ACC Pak Budi" in e["detail"] for e in tl["events"] if e["lane"] == "settlement")


def test_t02_settle_before_qc_blocked_and_recorded(h):
    roll = whole_roll(h, 1)
    rid = new_approved(h, roll)
    cn_before = DB.credit_notes.count_documents({})
    r = requests.post(f"{BASE}/sales-returns/{rid}/settle", headers=h,
                      json={"outcome": "refund", "decision_note": "nego via WA"})
    assert r.status_code == 400 and "sesudah QC" in r.json()["detail"]
    assert DB.credit_notes.count_documents({}) == cn_before
    assert DB.inventory_rolls.find_one({"id": roll["roll_id"]})["status"] == "delivered"
    log = DB.audit_logs.find_one({"action": "sales_return_settle_blocked", "entity_id": rid})
    assert log and log["actor"] and "nego via WA" in str(log.get("after"))


def test_replacement_shipping_is_not_return_arrival(h):
    roll = whole_roll(h, 1)
    rid = DB.sales_returns.find_one({"notes": TAG, "status": "approved"})["id"]
    m = requests.post(f"{BASE}/sales-returns/{rid}/milestone", headers=h, json={"milestone": "shipped_to_customer"})
    assert m.status_code == 200
    g = requests.post(f"{BASE}/sales-returns/{rid}/milestone", headers=h, json={"milestone": "goods_arrived"})
    assert g.status_code == 400 and "pengganti" in g.json()["detail"].lower()
    tl = requests.get(f"{BASE}/sales-returns/{rid}/timeline", headers=h).json()
    lanes = [e["lane"] for e in tl["events"] if "pelanggan" in e["title"].lower()]
    assert lanes == ["replacement"]
    _ = roll


def test_t03_summary_split_per_unit(h):
    DB.sales_returns.insert_one({
        "id": "sret_TEST_L081_units", "number": "TEST-L081-UNITS", "notes": TAG, "entity_id": "ent_ksc",
        "order_id": SO["id"], "customer_id": SO["customer_id"], "status": "approved", "created_at": "2026-10-17T00:00:00+00:00",
        "items": [{"product_id": "p1", "product_name": "Woven", "unit": "yard", "quantity_returned": 100},
                  {"product_id": "p2", "product_name": "Knit", "unit": "kg", "quantity_returned": 20}]})
    tl = requests.get(f"{BASE}/sales-returns/sret_TEST_L081_units/timeline", headers=h).json()
    per = {g["unit"]: g["claimed"] for g in tl["summary"]["per_unit"]}
    assert per == {"yard": 100, "kg": 20}
    assert "Rupiah" in tl["summary"]["value_basis"]

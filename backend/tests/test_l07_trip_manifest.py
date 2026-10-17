"""L07 — multi-SO trip (picking list, cek kesiapan, manifest) + transit internal tidak memposting GL pelanggan."""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


@pytest.fixture(scope="module")
def h():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


def test_ln070_picking_list_keeps_orders_separate(h):
    cands = requests.get(f"{BASE}/logistics/trip/candidates", headers=h).json()
    assert cands and all(c["order_number"].startswith("KSC/") for c in cands)
    ids = [c["order_id"] for c in cands]
    pl = requests.post(f"{BASE}/logistics/trip/picking-list", headers=h, json={"order_ids": ids}).json()
    rolls = [r for w in pl["warehouses"] for r in w["rolls"]]
    for r in rolls:
        doc = DB.inventory_rolls.find_one({"id": r["roll_id"]}, {"_id": 0, "reserved_ref": 1})
        assert doc["reserved_ref"]["id"] == r["order_id"]
    assert "bukan Surat Jalan" in pl["note"]


def test_ln070_trip_check_uses_dispatch_guard(h):
    ids = [c["order_id"] for c in requests.get(f"{BASE}/logistics/trip/candidates", headers=h).json()]
    chk = requests.post(f"{BASE}/logistics/trip/check", headers=h, json={"order_ids": ids}).json()
    assert chk["rows"]
    assert chk["ready"] == all(r["ready"] for r in chk["rows"])
    assert all(r["reason"] for r in chk["rows"] if not r["ready"])


def test_trip_scope_rejects_other_entity(h):
    other = DB.sales_orders.find_one({"entity_id": "ent_kanda"}, {"_id": 0, "id": 1})
    r = requests.post(f"{BASE}/logistics/trip/picking-list", headers=h, json={"order_ids": [other["id"]]})
    assert r.status_code == 403


def test_ln071_multi_order_delivery_and_manifest(h):
    ships = [s for s in requests.get(f"{BASE}/logistics/shipments/unassigned", headers=h).json()
             if s.get("fulfillment_method") != "ambil"]
    by_order = {}
    for s in ships:
        by_order.setdefault(s["order_id"], s)
    if len(by_order) < 2:
        pytest.skip("butuh SJ belum diangkut dari >=2 SO")
    pick = list(by_order.values())[:2]
    ids = [s["id"] for s in pick]
    body = {"shipment_ids": ids, "mode": "expedition", "courier_name": "TEST_L07"}
    d = requests.post(f"{BASE}/logistics/deliveries", headers=h, json=body)
    try:
        assert d.status_code == 200, d.text
        d = d.json()
        assert d["is_multi_order"] and len(d["order_ids"]) == 2
        dup = requests.post(f"{BASE}/logistics/deliveries", headers=h, json=body)
        assert dup.status_code == 400
        m = requests.get(f"{BASE}/logistics/deliveries/{d['id']}/manifest", headers=h).json()
        assert m["totals"]["orders"] == 2 and m["totals"]["shipments"] == 2
        for oid in d["order_ids"]:
            lst = requests.get(f"{BASE}/logistics/deliveries", headers=h, params={"order_id": oid}).json()
            assert any(x["id"] == d["id"] for x in lst)
    finally:
        if isinstance(d, dict):
            DB.logistics_deliveries.delete_one({"id": d["id"]})
            DB.shipments.update_many({"id": {"$in": ids}}, {"$set": {"logistics_id": None, "logistics_number": None,
                                                                    "logistics_status": None, "logistics_mode": None}})


def test_ln072_t01_internal_transit_no_customer_gl():
    t = DB.warehouse_transfers.find_one({"sales_order_id": {"$exists": True}, "status": {"$in": ["dispatched", "partially_received"]}},
                                        {"_id": 0})
    if not t:
        pytest.skip("tidak ada transfer SO dalam perjalanan")
    so = DB.sales_orders.find_one({"id": t["sales_order_id"]}, {"_id": 0, "status": 1})
    assert so["status"] not in ("delivered", "completed", "done")
    assert DB.journal_entries.count_documents({"source": {"$in": ["shipment_revenue", "shipment_cogs"]},
                                               "source_id": t["id"]}) == 0

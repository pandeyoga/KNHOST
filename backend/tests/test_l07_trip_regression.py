"""L07 regression (testing agent) — trip candidates/picking/check, multi-SO delivery, manifest, pickup combine, roles, single-SO regression."""
import os

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
RESET = {"logistics_id": None, "logistics_number": None, "logistics_status": None, "logistics_mode": None}
_SJ = {x["shipment_no"]: x["order_id"] for x in DB.shipments.find({"entity_id": "ent_ksc", "shipment_no": {"$regex": "^KSC/SJ-0000[1-4]$"}}, {"_id": 0})}
SO1, SO2 = _SJ.get("KSC/SJ-00001"), next((v for v in _SJ.values() if v != _SJ.get("KSC/SJ-00001")), None)


def _login(email, pw):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login {email} failed")
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}


@pytest.fixture(scope="module")
def h():
    return _login("admin@kainnusantara.id", "demo12345")


@pytest.fixture
def created():
    ids = []
    yield ids
    for did in ids:
        d = DB.logistics_deliveries.find_one({"id": did}, {"_id": 0, "shipment_ids": 1, "vehicle_id": 1})
        DB.logistics_deliveries.delete_one({"id": did})
        DB.shipments.update_many({"logistics_id": did}, {"$set": RESET})
        if d and d.get("vehicle_id"):
            DB.fleet_vehicles.update_one({"id": d["vehicle_id"], "current_delivery_id": did},
                                         {"$set": {"status": "available", "current_delivery_id": None}})


PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")


def _photo(h, did, kind):
    hh = {k: v for k, v in h.items()}
    r = requests.post(f"{BASE}/logistics/deliveries/{did}/photos", headers=hh, data={"kind": kind},
                      files={"file": ("t.png", PNG, "image/png")})
    assert r.status_code == 200, r.text


def _ships():
    return {s["shipment_no"]: s["id"] for s in DB.shipments.find({"entity_id": "ent_ksc"}, {"_id": 0})}


# --- LN-070 trip endpoints
def test_candidates_only_ksc(h):
    r = requests.get(f"{BASE}/logistics/trip/candidates", headers=h)
    assert r.status_code == 200
    c = r.json()
    assert c and all(x["order_number"].startswith("KSC/") for x in c)
    for x in c:
        assert DB.wms_tasks.count_documents({"order_id": x["order_id"], "flow_type": "outbound",
                                             "status": {"$nin": ["dispatched", "cancelled", "done", "escalated"]}}) > 0


def test_picking_list_shape_and_errors(h):
    ids = [c["order_id"] for c in requests.get(f"{BASE}/logistics/trip/candidates", headers=h).json()]
    r = requests.post(f"{BASE}/logistics/trip/picking-list", headers=h, json={"order_ids": ids})
    assert r.status_code == 200
    pl = r.json()
    assert isinstance(pl["warehouses"], list) and pl["warehouses"]
    for w in pl["warehouses"]:
        assert w["warehouse_id"] and "roll_count" in w and w["roll_count"] == len(w["rolls"])
        for roll in w["rolls"]:
            assert roll["order_id"] in ids and roll["order_number"]
    assert requests.post(f"{BASE}/logistics/trip/picking-list", headers=h, json={"order_ids": []}).status_code == 400
    assert requests.post(f"{BASE}/logistics/trip/picking-list", headers=h, json={"order_ids": ["so_TEST_nope"]}).status_code == 404
    other = DB.sales_orders.find_one({"entity_id": "ent_kanda"}, {"_id": 0, "id": 1})
    assert requests.post(f"{BASE}/logistics/trip/picking-list", headers=h, json={"order_ids": [other["id"]]}).status_code == 403
    assert requests.post(f"{BASE}/logistics/trip/check", headers=h, json={"order_ids": [other["id"]]}).status_code == 403


def test_trip_check_rows(h):
    ids = [c["order_id"] for c in requests.get(f"{BASE}/logistics/trip/candidates", headers=h).json()]
    r = requests.post(f"{BASE}/logistics/trip/check", headers=h, json={"order_ids": ids})
    assert r.status_code == 200
    chk = r.json()
    assert chk["rows"] and chk["ready"] == all(x["ready"] for x in chk["rows"])
    for x in chk["rows"]:
        assert x["warehouse_id"] and x["order_number"]
        if not x["ready"]:
            assert isinstance(x["reason"], str) and x["reason"]
    print("check rows:", [(x["order_number"], x["warehouse_name"], x["ready"], x["reason"][:60]) for x in chk["rows"]])


def test_trip_forbidden_for_sales():
    hs = _login("sales@kainnusantara.id", "demo12345")
    assert requests.get(f"{BASE}/logistics/trip/candidates", headers=hs).status_code == 403
    assert requests.post(f"{BASE}/logistics/trip/check", headers=hs, json={"order_ids": [SO1]}).status_code == 403


# --- LN-071 multi-SO delivery
def test_multi_order_delivery_full(h, created):
    s = _ships()
    ids = [s["KSC/SJ-00001"], s["KSC/SJ-00002"], s["KSC/SJ-00003"], s["KSC/SJ-00004"]]
    body = {"shipment_ids": ids, "mode": "expedition", "courier_name": "TEST_L07", "tracking_no": "TEST-RESI"}
    r = requests.post(f"{BASE}/logistics/deliveries", headers=h, json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    created.append(d["id"])
    assert d["is_multi_order"] is True and sorted(d["order_ids"]) == sorted([SO1, SO2])
    assert len(d["orders"]) == 2 and all(len(o["shipment_ids"]) == 2 for o in d["orders"])
    assert DB.shipments.count_documents({"id": {"$in": ids}, "logistics_id": d["id"]}) == 4
    dup = requests.post(f"{BASE}/logistics/deliveries", headers=h, json=body)
    assert dup.status_code == 400
    partial = requests.post(f"{BASE}/logistics/deliveries", headers=h, json={**body, "shipment_ids": [ids[0]]})
    assert partial.status_code == 400
    for oid in (SO1, SO2):
        lst = requests.get(f"{BASE}/logistics/deliveries", headers=h, params={"order_id": oid}).json()
        assert any(x["id"] == d["id"] for x in lst)
    m = requests.get(f"{BASE}/logistics/deliveries/{d['id']}/manifest", headers=h)
    assert m.status_code == 200
    m = m.json()
    assert m["totals"]["orders"] == 2 and m["totals"]["shipments"] == 4
    assert m["totals"]["rolls"] == sum(o["roll_count"] for o in m["orders"])
    # status transition on multi-order propagates to all SJ
    _photo(h, d["id"], "load")
    for to in ("loaded", "in_transit"):
        t = requests.post(f"{BASE}/logistics/deliveries/{d['id']}/transition", headers=h, json={"to": to})
        assert t.status_code == 200, t.text
    assert DB.shipments.count_documents({"id": {"$in": ids}, "logistics_status": "in_transit"}) == 4


def test_pickup_order_cannot_combine(h, created):
    s = _ships()
    DB.sales_orders.update_one({"id": SO2}, {"$set": {"fulfillment_method": "ambil"}})
    try:
        r = requests.post(f"{BASE}/logistics/deliveries", headers=h,
                          json={"shipment_ids": [s["KSC/SJ-00001"], s["KSC/SJ-00003"]], "mode": "self_pickup"})
        if r.status_code == 200:
            created.append(r.json()["id"])
        assert r.status_code == 400 and "AMBIL SENDIRI" in r.text
        r2 = requests.post(f"{BASE}/logistics/deliveries", headers=h,
                           json={"shipment_ids": [s["KSC/SJ-00001"], s["KSC/SJ-00003"]], "mode": "expedition"})
        if r2.status_code == 200:
            created.append(r2.json()["id"])
        assert r2.status_code == 400
        assert DB.shipments.count_documents({"id": {"$in": [s["KSC/SJ-00001"], s["KSC/SJ-00003"]]},
                                             "logistics_id": {"$nin": [None, ""]}}) == 0
    finally:
        DB.sales_orders.update_one({"id": SO2}, {"$set": {"fulfillment_method": "kirim"}})


# --- Regression single-SO
def test_single_order_delivery_and_transition(h, created):
    s = _ships()
    r = requests.post(f"{BASE}/logistics/deliveries", headers=h,
                      json={"shipment_ids": [s["KSC/SJ-00002"]], "mode": "expedition", "courier_name": "TEST_JNE"})
    assert r.status_code == 200, r.text
    d = r.json()
    created.append(d["id"])
    assert d["is_multi_order"] is False and d["order_ids"] == [SO1]
    bad = requests.post(f"{BASE}/logistics/deliveries/{d['id']}/transition", headers=h, json={"to": "loaded"})
    assert bad.status_code == 400  # no load photo
    _photo(h, d["id"], "load")
    assert requests.post(f"{BASE}/logistics/deliveries/{d['id']}/transition", headers=h, json={"to": "loaded"}).status_code == 200
    bad = requests.post(f"{BASE}/logistics/deliveries/{d['id']}/transition", headers=h, json={"to": "in_transit"})
    assert bad.status_code == 400  # no tracking no
    fail = requests.post(f"{BASE}/logistics/deliveries/{d['id']}/transition", headers=h,
                         json={"to": "failed", "reason": "TEST alamat tutup"})
    assert fail.status_code == 200, fail.text
    assert fail.json()["status"] == "failed"
    back = requests.post(f"{BASE}/logistics/deliveries/{d['id']}/transition", headers=h, json={"to": "prepared"})
    assert back.status_code == 200 and back.json()["status"] == "prepared"
    m = requests.get(f"{BASE}/logistics/deliveries/{d['id']}/manifest", headers=h).json()
    assert m["totals"]["orders"] == 1


def test_driver_list_still_works():
    hd = _login("driver@kainnusantara.id", "demo12345")
    r = requests.get(f"{BASE}/logistics/deliveries", headers=hd)
    assert r.status_code == 200 and isinstance(r.json(), list)

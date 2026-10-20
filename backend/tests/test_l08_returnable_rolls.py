"""L08 LN-080 — retur hanya dari roll/qty terkirim; batas kumulatif atomik saat klaim paralel."""
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SHIPPED_SO = DB.sales_orders.find_one({"number": "KSC/SO-00001"})["id"]      # done, SJ-00001/00002
UNSHIPPED_SO = DB.sales_orders.find_one({"number": "KSC/SO-00003"})["id"]    # confirmed, belum ada SJ
TAG = "TEST_L08"


@pytest.fixture(scope="module")
def h():
    r = requests.post(f"{BASE}/auth/login", json={"email": "admin@kainnusantara.id", "password": "demo12345"})
    yield {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": "ent_ksc"}
    DB.sales_returns.delete_many({"notes": TAG})
    DB.return_create_locks.delete_many({})


def _post(h, so, items):
    return requests.post(f"{BASE}/sales-returns", headers=h, json={
        "order_id": so, "return_type": "retur", "items": items, "notes": TAG, "submit_now": False})


def test_t01_only_shipped_rolls(h):
    data = requests.get(f"{BASE}/sales-returns/returnable", headers=h, params={"order_id": SHIPPED_SO}).json()
    assert data["rolls"] and all(r["shipment_no"] and r["product_name"] and r["unit"] for r in data["rolls"])
    assert all(not r["product_name"].startswith("prod_") for r in data["rolls"])
    other = DB.inventory_rolls.find_one({"status": "available"}, {"_id": 0, "id": 1})
    p = data["products"][0]
    r = _post(h, SHIPPED_SO, [{"product_id": p["product_id"], "quantity_returned": 1, "unit": p["unit"],
                               "roll_ids": [other["id"]], "roll_qtys": {other["id"]: 1}}])
    assert r.status_code == 400 and "bukan roll terkirim" in r.json()["detail"]
    r = _post(h, UNSHIPPED_SO, [{"product_id": DB.sales_orders.find_one({"id": UNSHIPPED_SO})["items"][0]["product_id"], "quantity_returned": 1, "unit": "kg"}])
    assert r.status_code == 400 and "belum punya barang terkirim" in r.json()["detail"]


def test_fix_iter206_distribution_dup_and_entity(h):
    data = requests.get(f"{BASE}/sales-returns/returnable", headers=h, params={"order_id": SHIPPED_SO}).json()
    roll = next(r for r in data["rolls"] if r["remaining"] > 10)
    base = {"product_id": roll["product_id"], "unit": roll["unit"], "roll_ids": [roll["roll_id"]]}
    r = _post(h, SHIPPED_SO, [{**base, "quantity_returned": 5}])
    assert r.status_code == 200, r.text
    assert abs(r.json()["items"][0]["roll_qtys"][roll["roll_id"]] - 5) < 0.01
    after = next(x for x in requests.get(f"{BASE}/sales-returns/returnable", headers=h,
                                         params={"order_id": SHIPPED_SO}).json()["rolls"] if x["roll_id"] == roll["roll_id"])
    assert abs(after["remaining"] - (roll["remaining"] - 5)) < 0.02
    r = _post(h, SHIPPED_SO, [{**base, "quantity_returned": after["remaining"]}])
    assert r.status_code == 200, r.text
    other = next(x for x in data["rolls"] if x["roll_id"] != roll["roll_id"] and x["product_id"] == roll["product_id"])
    half = round(other["remaining"] * 0.6, 2)
    dup = {"product_id": other["product_id"], "unit": other["unit"], "roll_ids": [other["roll_id"]],
           "quantity_returned": half, "roll_qtys": {other["roll_id"]: half}}
    assert _post(h, SHIPPED_SO, [dup, dup]).status_code == 400
    kanda = DB.sales_orders.find_one({"entity_id": "ent_kanda", "status": "done"}, {"_id": 0, "id": 1})
    if kanda:
        s = requests.post(f"{BASE}/auth/login", json={"email": "sales@kainnusantara.id", "password": "demo12345"}).json()
        r = requests.post(f"{BASE}/sales-returns", headers={"Authorization": f"Bearer {s['token']}"}, json={
            "order_id": kanda["id"], "return_type": "retur", "notes": TAG,
            "items": [{"product_id": "x", "quantity_returned": 1}]})
        assert r.status_code in (403, 404)


def test_t02_parallel_claims_respect_roll_limit(h):
    data = requests.get(f"{BASE}/sales-returns/returnable", headers=h, params={"order_id": SHIPPED_SO}).json()
    roll = next(r for r in data["rolls"] if r["remaining"] > 2)
    qty = round(roll["remaining"] * 0.6, 2)
    item = {"product_id": roll["product_id"], "quantity_returned": qty, "unit": roll["unit"],
            "roll_ids": [roll["roll_id"]], "roll_qtys": {roll["roll_id"]: qty}}
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda _: _post(h, SHIPPED_SO, [item]), range(4)))
    ok = [r for r in res if r.status_code == 200]
    assert len(ok) == 1, [r.text for r in res]
    after = requests.get(f"{BASE}/sales-returns/returnable", headers=h, params={"order_id": SHIPPED_SO}).json()
    again = next(r for r in after["rolls"] if r["roll_id"] == roll["roll_id"])
    assert abs(again["returned_qty"] - qty) < 0.02

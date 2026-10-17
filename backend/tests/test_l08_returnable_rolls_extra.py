"""L08 LN-080 (testing agent) — returnable shape, validation errors, parallel lock, valid save, entity access, regression."""
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
SHIPPED_SO = DB.sales_orders.find_one({"number": "KSC/SO-00001"})["id"]
UNSHIPPED_SO = DB.sales_orders.find_one({"number": "KSC/SO-00003"})["id"]
KANDA_SO = DB.sales_orders.find_one({"number": "KANDA/SO-00002"})["id"]
TAG = "TEST_L08_T1"


def _login(email, pw, ent="ent_ksc"):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ent}


@pytest.fixture(scope="module")
def h():
    yield _login("admin@kainnusantara.id", "demo12345")
    DB.sales_returns.delete_many({"notes": TAG})
    DB.return_create_locks.delete_many({})


def _post(h, so, items, **kw):
    body = {"order_id": so, "return_type": "retur", "items": items, "notes": TAG, "submit_now": False}
    body.update(kw)
    return requests.post(f"{BASE}/sales-returns", headers=h, json=body)


def _ret(h, so=SHIPPED_SO):
    r = requests.get(f"{BASE}/sales-returns/returnable", headers=h, params={"order_id": so})
    assert r.status_code == 200, r.text
    return r.json()


# returnable shape
def test_returnable_shape(h):
    d = _ret(h)
    assert d["rolls"] and d["products"]
    for r in d["rolls"]:
        for k in ("roll_id", "roll_no", "shipment_no", "product_name", "sku", "color", "shipped_qty", "unit", "returned_qty", "remaining"):
            assert k in r, k
        assert r["roll_no"] and r["shipment_no"].startswith("KSC/SJ-")
        assert not r["product_name"].startswith("prod_")
    sjs = {r["shipment_no"] for r in d["rolls"]}
    print("SJs:", sjs, "rolls:", len(d["rolls"]), "products:", d["products"])


def test_returnable_unshipped_empty(h):
    d = _ret(h, UNSHIPPED_SO)
    assert d["rolls"] == [] and d["products"] == []


def test_returnable_other_entity_forbidden(h):
    r = requests.get(f"{BASE}/sales-returns/returnable", headers=h, params={"order_id": KANDA_SO})
    print("admin(ksc ctx) on kanda SO:", r.status_code)
    sh = _login("sales@kainnusantara.id", "demo1234")
    r2 = requests.get(f"{BASE}/sales-returns/returnable", headers=sh, params={"order_id": KANDA_SO})
    print("sales on kanda SO:", r2.status_code, r2.text[:150])
    assert r2.status_code in (403, 404)


def test_returnable_unknown_so_404(h):
    r = requests.get(f"{BASE}/sales-returns/returnable", headers=h, params={"order_id": "so_nope"})
    assert r.status_code == 404


def test_create_other_entity_so_blocked():
    sh = _login("sales@kainnusantara.id", "demo1234")
    r = _post(sh, KANDA_SO, [{"product_id": "x", "quantity_returned": 1, "unit": "yard"}])
    print("sales create on kanda SO:", r.status_code, r.text[:200])
    DB.sales_returns.delete_many({"notes": TAG, "order_id": KANDA_SO})
    assert r.status_code in (400, 403, 404)


# validation errors
def test_product_not_in_sj(h):
    p = DB.products.find_one({"id": {"$nin": [x["product_id"] for x in _ret(h)["products"]]}}, {"_id": 0, "id": 1})
    r = _post(h, SHIPPED_SO, [{"product_id": p["id"], "quantity_returned": 1, "unit": "yard"}])
    assert r.status_code == 400 and "tidak ada di Surat Jalan" in r.json()["detail"], r.text


def test_qty_above_remaining_roll(h):
    roll = _ret(h)["rolls"][0]
    q = roll["remaining"] + 5
    r = _post(h, SHIPPED_SO, [{"product_id": roll["product_id"], "quantity_returned": q, "unit": roll["unit"],
                               "roll_ids": [roll["roll_id"]], "roll_qtys": {roll["roll_id"]: q}}])
    print(r.text)
    assert r.status_code == 400 and "melebihi" in r.json()["detail"]


def test_qty_above_product_remaining(h):
    p = _ret(h)["products"][0]
    r = _post(h, SHIPPED_SO, [{"product_id": p["product_id"], "quantity_returned": p["remaining"] + 10, "unit": p["unit"]}])
    print(r.text)
    assert r.status_code == 400 and "melebihi batas" in r.json()["detail"]


def test_same_roll_twice_in_one_request(h):
    """Edge: same roll claimed by 2 items in one payload, each 60% → total 120% should be rejected."""
    roll = next(r for r in _ret(h)["rolls"] if r["remaining"] > 2)
    q = round(roll["remaining"] * 0.6, 2)
    it = {"product_id": roll["product_id"], "quantity_returned": q, "unit": roll["unit"],
          "roll_ids": [roll["roll_id"]], "roll_qtys": {roll["roll_id"]: q}}
    r = _post(h, SHIPPED_SO, [it, dict(it)])
    print("dup roll in one request:", r.status_code, r.text[:200])
    DB.sales_returns.delete_many({"notes": TAG})
    assert r.status_code == 400


def test_qty_mismatch_roll_sum(h):
    """Edge: quantity_returned differs from sum(roll_qtys)."""
    roll = next(r for r in _ret(h)["rolls"] if r["remaining"] > 2)
    r = _post(h, SHIPPED_SO, [{"product_id": roll["product_id"], "quantity_returned": 1, "unit": roll["unit"],
                               "roll_ids": [roll["roll_id"]], "roll_qtys": {roll["roll_id"]: roll["remaining"]}}])
    print("qty mismatch:", r.status_code, r.text[:200])
    DB.sales_returns.delete_many({"notes": TAG})


# valid save
def test_valid_save_roll_ids_qty_rolls(h):
    rolls = [r for r in _ret(h)["rolls"] if r["remaining"] > 1]
    pid = rolls[0]["product_id"]
    sel = [r for r in rolls if r["product_id"] == pid][:2]
    qtys = {r["roll_id"]: round(r["remaining"] / 2, 2) for r in sel}
    r = _post(h, SHIPPED_SO, [{"product_id": pid, "quantity_returned": round(sum(qtys.values()), 2), "unit": sel[0]["unit"],
                               "roll_ids": list(qtys), "roll_qtys": qtys}])
    assert r.status_code == 200, r.text
    doc = r.json()
    it = doc["items"][0]
    assert it["roll_ids"] == list(qtys) and it["qty_rolls"] == len(sel)
    g = requests.get(f"{BASE}/sales-returns/{doc['id']}", headers=h)
    assert g.status_code == 200 and g.json()["items"][0]["roll_ids"] == list(qtys)
    after = {x["roll_id"]: x for x in _ret(h)["rolls"]}
    for rid, q in qtys.items():
        assert after[rid]["returned_qty"] >= q - 0.02
    DB.sales_returns.delete_many({"notes": TAG})


# parallel
def test_parallel_4(h):
    roll = next(r for r in _ret(h)["rolls"] if r["remaining"] > 2)
    q = round(roll["remaining"] * 0.6, 2)
    it = {"product_id": roll["product_id"], "quantity_returned": q, "unit": roll["unit"],
          "roll_ids": [roll["roll_id"]], "roll_qtys": {roll["roll_id"]: q}}
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda _: _post(h, SHIPPED_SO, [it]), range(4)))
    print([(r.status_code, r.text[:90]) for r in res])
    assert sum(r.status_code == 200 for r in res) == 1
    assert all(r.status_code == 400 for r in res if r.status_code != 200)
    again = next(x for x in _ret(h)["rolls"] if x["roll_id"] == roll["roll_id"])
    assert abs(again["returned_qty"] - q) < 0.02
    assert DB.return_create_locks.count_documents({}) == 0
    DB.sales_returns.delete_many({"notes": TAG})


# regression pre-seeded
@pytest.mark.parametrize("rid", [d["id"] for d in DB.sales_returns.find({"notes": {"$ne": "TEST_L08"}}, {"id": 1}).limit(3)])
def test_regression_detail(h, rid):
    r = requests.get(f"{BASE}/sales-returns/{rid}", headers=h)
    assert r.status_code == 200 and r.json()["id"] == rid


def test_regression_list(h):
    r = requests.get(f"{BASE}/sales-returns", headers=h)
    assert r.status_code == 200

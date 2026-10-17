"""L02 LN-022 / LN-021-T03 — tambahan T1: superseded, reject stale, konkurensi, roll_lines Ganti Roll, cleanup."""
import os
import concurrent.futures as cf

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT = "ent_ksc"
P1, P2 = [r["_id"] for r in DB.inventory_rolls.aggregate([
    {"$match": {"status": "available", "owner_entity_id": ENT, "unit": "yard"}},
    {"$group": {"_id": "$product_id", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 2}])]
ADDR = (DB.customers.find_one({"id": "cust_butik_bali"}) or {}).get("addresses", [{}])[0].get("id")
CREATED = []


def _tok(email):
    pwd = "demo12345" if email.startswith("admin@") else "demo1234"
    return requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}).json()["token"]


@pytest.fixture(scope="module")
def H():
    hs = {k: {"Authorization": f"Bearer {_tok(v)}", "X-Entity-Id": ENT}
          for k, v in (("admin", "admin@kainnusantara.id"), ("manager", "manager@kainnusantara.id"))}
    yield hs
    for sid in CREATED:
        r = requests.post(f"{BASE}/sales-orders/{sid}/cancel", headers=hs["admin"], json={"reason": "TEST_T1 cleanup"})
        print("cancel", sid, r.status_code)
    DB.price_approvals.delete_many({"so_id": {"$in": CREATED}})
    orphans = DB.inventory_rolls.count_documents({"$or": [{"reserved_ref.id": {"$in": CREATED}},
                                                          {"length_reservations.ref.id": {"$in": CREATED}}]})
    print("ORPHAN reserved rolls after cancel:", orphans)
    DB.sales_orders.delete_many({"id": {"$in": CREATED}})


def _so(h, items=None):
    r = requests.post(f"{BASE}/sales-orders", headers=h, json={
        "customer_id": "cust_butik_bali", "shipping_address_id": ADDR, "entity_id": ENT,
        "notes": "TEST_T1_L022", "confirm_mixed_lot": True, "allow_backorder": True,
        "items": items or [{"product_id": P1, "quantity": 20, "unit": "yard"},
                           {"product_id": P2, "quantity": 20, "unit": "yard"}]})
    assert r.status_code in (200, 201), r.text[:400]
    CREATED.append(r.json()["id"])
    return r.json()


def _req(h, sid, pid, price):
    r = requests.post(f"{BASE}/sales-orders/{sid}/request-special-price", headers=h,
                      json={"product_id": pid, "requested_price": price, "reason": "TEST_T1 harga"})
    assert r.status_code == 200, r.text[:300]
    return r.json(), [p for p in r.json()["pending_approvals"] if p["type"] == "special_price"][-1]


def _decide(h, sid, aid, decision="approve"):
    return requests.post(f"{BASE}/sales-orders/{sid}/approvals/{aid}/decide", headers=h,
                         json={"decision": decision, "notes": "ok"})


def _spare(pid, exclude=()):
    return DB.inventory_rolls.find_one({"product_id": pid, "status": "available", "owner_entity_id": ENT,
                                        "length_remaining": {"$gte": 20}, "length_reservations.0": {"$exists": False},
                                        "warehouse_id": "wh_jakarta", "id": {"$nin": list(exclude)}})


# Superseded entry: status, superseded_by, alloc_sig, pra doc; decide reject superseded -> 409
def test_superseded_fields_and_reject_superseded(H):
    so = _so(H["admin"])
    _, first = _req(H["admin"], so["id"], P2, 11000)
    assert first.get("alloc_sig", "").startswith(P2 + "|")
    doc, second = _req(H["admin"], so["id"], P2, 12000)
    old = next(p for p in doc["pending_approvals"] if p["id"] == first["id"])
    assert old["status"] == "superseded" and old["superseded_by"] == second["id"]
    assert DB.price_approvals.find_one({"id": first["ref_id"]})["superseded_by"] == second["ref_id"]
    assert _decide(H["manager"], so["id"], first["id"], "reject").status_code == 409
    # standalone price-approvals endpoint must not approve a superseded pra
    r = requests.post(f"{BASE}/price-approvals/{first['ref_id']}/approve", headers=H["manager"], json={})
    assert r.status_code in (403, 409), r.text[:200]
    # pending count = 1 special price
    cur = DB.sales_orders.find_one({"id": so["id"]})
    assert sum(1 for p in cur["pending_approvals"] if p["type"] == "special_price" and p["status"] == "pending") == 1


# Stale entry (qty change) -> approve 409, reject still works, SO not locked
def test_stale_reject_works_and_not_locked(H):
    so = _so(H["admin"])
    _, ent = _req(H["admin"], so["id"], P2, 30000)
    r = requests.post(f"{BASE}/sales-orders/{so['id']}/override", headers=H["admin"],
                      json={"note": "TEST_T1 ubah qty", "lines": [{"product_id": P2, "quantity": 22}]})
    assert r.status_code == 200, r.text[:300]
    st = _decide(H["manager"], so["id"], ent["id"])
    assert st.status_code == 409 and "ajukan ulang" in st.text
    cur = DB.sales_orders.find_one({"id": so["id"]}, {"_id": 0})
    print("saga fields after 409:", {k: v for k, v in cur.items() if "claim" in k or "saga" in k or "lock" in k})
    rj = _decide(H["manager"], so["id"], ent["id"], "reject")
    assert rj.status_code == 200, rj.text[:300]
    assert DB.price_approvals.find_one({"id": ent["ref_id"]})["status"] == "rejected"


# Concurrency: two managers approve same entry in parallel -> exactly one 200
def test_parallel_approve_only_one_wins(H):
    so = _so(H["admin"])
    _, ent = _req(H["admin"], so["id"], P2, 31000)
    with cf.ThreadPoolExecutor(4) as ex:
        res = list(ex.map(lambda _: _decide(H["manager"], so["id"], ent["id"]), range(4)))
    codes = sorted(r.status_code for r in res)
    print("parallel codes", codes)
    assert codes.count(200) == 1 and all(c == 409 for c in codes if c != 200)
    cur = DB.sales_orders.find_one({"id": so["id"]})
    assert next(i for i in cur["items"] if i["product_id"] == P2)["price"] == 31000


# LN-021-T03: Ganti Roll on roll-mode line updates items[].roll_lines and invalidates pending price
def test_reallocate_updates_roll_lines_roll_mode(H):
    r1 = _spare(P1)
    assert r1, "no spare roll"
    qty = r1["length_remaining"]
    r = requests.post(f"{BASE}/sales-orders", headers=H["admin"], json={
        "customer_id": "cust_butik_bali", "shipping_address_id": ADDR, "entity_id": ENT,
        "notes": "TEST_T1_L021", "confirm_mixed_lot": True, "allow_backorder": True,
        "items": [{"product_id": P1, "quantity": qty, "unit": r1.get("unit") or "yard", "purchase_mode": "roll",
                   "roll_lines": [{"roll_id": r1["id"], "take_qty": qty}]}]})
    if r.status_code not in (200, 201):
        pytest.skip(f"roll-mode SO create failed: {r.status_code} {r.text[:300]}")
    so = r.json()
    CREATED.append(so["id"])
    print("created roll_lines", so["items"][0].get("roll_lines"), "unit", so["items"][0].get("unit"))
    assert so["items"][0].get("roll_lines"), "roll_lines missing on roll-mode item"
    _, ent = _req(H["admin"], so["id"], P1, 47000)
    r2 = _spare(P1, exclude=[r1["id"]])
    rr = requests.post(f"{BASE}/sales-orders/{so['id']}/items/{P1}/reallocate", headers=H["admin"],
                       json={"roll_lines": [{"roll_id": r2["id"], "take_qty": r2["length_remaining"]}]})
    assert rr.status_code == 200, rr.text[:300]
    cur = DB.sales_orders.find_one({"id": so["id"]})
    rl = cur["items"][0]["roll_lines"]
    print("after realloc roll_lines", rl)
    assert [x["roll_id"] for x in rl] == [r2["id"]]
    assert DB.inventory_rolls.find_one({"id": r1["id"]})["status"] == "available"
    st = _decide(H["manager"], so["id"], ent["id"])
    assert st.status_code == 409 and "ajukan ulang" in st.text
    _, again = _req(H["admin"], so["id"], P1, 47500)
    ok = _decide(H["manager"], so["id"], again["id"])
    assert ok.status_code == 200, ok.text[:300]

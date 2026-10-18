"""L02 LN-022 — approval harga khusus terikat produk + versi alokasi, bukan posisi array."""
import os

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
        requests.post(f"{BASE}/sales-orders/{sid}/cancel", headers=hs["admin"], json={"reason": "TEST_L022 cleanup"})
    pra = [p["id"] for p in DB.price_approvals.find({"so_id": {"$in": CREATED}}, {"id": 1})]
    DB.price_approvals.delete_many({"id": {"$in": pra}})
    DB.inventory_rolls.update_many({"reserved_for_order": {"$in": CREATED}},
                                   {"$set": {"status": "available", "reserved_for_order": None, "length_reserved": 0}})
    DB.sales_orders.delete_many({"id": {"$in": CREATED}})


def _so(h):
    r = requests.post(f"{BASE}/sales-orders", headers=h, json={
        "customer_id": "cust_butik_bali", "shipping_address_id": ADDR, "entity_id": ENT,
        "notes": "TEST_L022", "confirm_mixed_lot": True, "allow_backorder": True,
        "items": [{"product_id": P1, "quantity": 20, "unit": "yard"},
                  {"product_id": P2, "quantity": 20, "unit": "yard"}]})
    assert r.status_code in (200, 201), r.text[:400]
    CREATED.append(r.json()["id"])
    return r.json()


def _req(h, sid, pid, price):
    r = requests.post(f"{BASE}/sales-orders/{sid}/request-special-price", headers=h,
                      json={"product_id": pid, "requested_price": price, "reason": "TEST_L022 harga"})
    assert r.status_code == 200, r.text[:300]
    return [p for p in r.json()["pending_approvals"] if p["type"] == "special_price"][-1]


def _decide(h, sid, aid):
    return requests.post(f"{BASE}/sales-orders/{sid}/approvals/{aid}/decide", headers=h,
                         json={"decision": "approve", "notes": "ok"})


def test_t01_second_request_supersedes_first(H):
    so = _so(H["admin"])
    first = _req(H["admin"], so["id"], P2, 11111)
    second = _req(H["admin"], so["id"], P2, 22222)
    old = _decide(H["manager"], so["id"], first["id"])
    assert old.status_code == 409
    ok = _decide(H["manager"], so["id"], second["id"])
    assert ok.status_code == 200, ok.text[:300]
    item = next(i for i in ok.json()["items"] if i["product_id"] == P2)
    assert item["price"] == 22222 and item["special_price_id"] == second["ref_id"]
    assert DB.price_approvals.find_one({"id": first["ref_id"]})["status"] == "superseded"


def test_t02_price_follows_product_after_line_removed(H):
    so = _so(H["admin"])
    ent = _req(H["admin"], so["id"], P2, 33333)                  # P2 di posisi 1 saat diajukan
    r = requests.post(f"{BASE}/sales-orders/{so['id']}/override", headers=H["admin"],
                      json={"note": "TEST_L022 hapus baris pertama", "lines": [{"product_id": P1, "remove": True}]})
    assert r.status_code == 200, r.text[:300]
    ok = _decide(H["manager"], so["id"], ent["id"])
    assert ok.status_code == 200, ok.text[:300]
    items = ok.json()["items"]
    assert [i["product_id"] for i in items] == [P2] and items[0]["price"] == 33333


def test_t01_allocation_changed_blocks_stale_approval(H):
    so = _so(H["admin"])
    ent = _req(H["admin"], so["id"], P1, 44444)
    r = requests.post(f"{BASE}/sales-orders/{so['id']}/override", headers=H["admin"],
                      json={"note": "TEST_L022 ubah qty", "lines": [{"product_id": P1, "quantity": 25}]})
    assert r.status_code == 200, r.text[:300]
    stale = _decide(H["manager"], so["id"], ent["id"])
    assert stale.status_code == 409 and "ajukan ulang" in stale.text
    cur = DB.sales_orders.find_one({"id": so["id"]})
    assert next(i for i in cur["items"] if i["product_id"] == P1)["price"] != 44444
    again = _req(H["admin"], so["id"], P1, 45000)
    ok = _decide(H["manager"], so["id"], again["id"])
    assert ok.status_code == 200, ok.text[:300]
    assert next(i for i in ok.json()["items"] if i["product_id"] == P1)["price"] == 45000



def test_t01_roll_swap_invalidates_pending_price(H):
    so = _so(H["admin"])
    ent = _req(H["admin"], so["id"], P1, 46000)
    spare = DB.inventory_rolls.find_one({"product_id": P1, "status": "available", "owner_entity_id": ENT,
                                         "length_remaining": {"$gte": 20}, "length_reservations.0": {"$exists": False},
                                         "warehouse_id": "wh_jakarta"})
    r = requests.post(f"{BASE}/sales-orders/{so['id']}/items/{P1}/reallocate", headers=H["admin"],
                      json={"roll_lines": [{"roll_id": spare["id"], "take_qty": spare["length_remaining"]}]})
    assert r.status_code == 200, r.text[:300]
    stale = _decide(H["manager"], so["id"], ent["id"])
    assert stale.status_code == 409 and "ajukan ulang" in stale.text



def test_evidence_form_path_goes_through_so_gate(H):
    """Form 'Ajukan Harga Khusus' (draf → bukti → submit) masuk gerbang SO; ACC lewat /price-approvals ikut SO."""
    so = _so(H["admin"])
    d = requests.post(f"{BASE}/price-approvals", headers=H["admin"], json={
        "customer_id": "cust_butik_bali", "product_id": P1, "requested_price": 47000, "reason": "TEST_L022 harga",
        "submit_now": False, "entity_id": ENT, "scope": "order", "so_id": so["id"]})
    assert d.status_code == 200, d.text[:300]
    pra = d.json()["id"]
    up = requests.post(f"{BASE}/price-approvals/{pra}/attachments", headers=H["admin"],
                       files={"file": ("bukti.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, "image/png")})
    assert up.status_code == 200, up.text[:300]
    s = requests.post(f"{BASE}/price-approvals/{pra}/submit", headers=H["admin"])
    assert s.status_code == 200, s.text[:300]
    cur = DB.sales_orders.find_one({"id": so["id"]})
    ent = next(p for p in cur["pending_approvals"] if p.get("ref_id") == pra)
    assert ent["status"] == "pending" and ent.get("alloc_sig")
    patch = requests.patch(f"{BASE}/price-approvals/{pra}", headers=H["admin"], json={"data": {"requested_price": 1}})
    assert patch.status_code == 409
    a = requests.post(f"{BASE}/price-approvals/{pra}/approve", headers=H["manager"], json={"decision_notes": "ok"})
    assert a.status_code == 200, a.text[:300]
    assert a.json()["status"] == "approved"
    cur = DB.sales_orders.find_one({"id": so["id"]})
    assert next(i for i in cur["items"] if i["product_id"] == P1)["price"] == 47000
    assert next(i for i in cur["items"] if i["product_id"] == P1)["price_source"] == "special_approval"
    assert next(p for p in cur["pending_approvals"] if p.get("ref_id") == pra)["status"] == "approved"

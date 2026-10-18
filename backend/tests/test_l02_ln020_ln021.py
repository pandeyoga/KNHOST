"""L02 LN-020-T01 (stok bebas vs dikunci potong) + LN-021-T01/T02 (genapkan roll, alokasi bersamaan)."""
import os
import threading

import pytest
import requests
from pymongo import MongoClient

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
ENT = "ent_ksc"
PID = "prod_TEST_l021"
CREATED = []


def _tok(email, pwd):
    return requests.post(f"{BASE}/auth/login", json={"email": email, "password": pwd}).json()["token"]


@pytest.fixture(scope="module")
def H():
    tpl_roll = DB.inventory_rolls.find_one({"owner_entity_id": ENT, "status": "available", "unit": "yard"}, {"_id": 0})
    tpl_prod = DB.products.find_one({"id": tpl_roll["product_id"]}, {"_id": 0})
    DB.products.insert_one({**tpl_prod, "id": PID, "sku": "TEST-L021", "name": "TEST_L021 KAIN"})
    for i, ln in enumerate([100] * 9 + [105]):
        roll = {k: v for k, v in tpl_roll.items() if k not in (
            "reserved_ref", "reserved_for_order", "length_reservations", "length_reserved", "active_movement",
            "epc", "tag_epc", "rfid_epc", "barcode")}
        DB.inventory_rolls.insert_one({**roll, "id": f"roll_TEST_l021_{i}", "roll_no": f"TEST-L021-{i:02d}",
                                       "product_id": PID, "length_remaining": float(ln), "length_original": float(ln),
                                       "status": "available", "grade": "A",
                                       "created_at": f"2026-01-01T00:00:{i:02d}+00:00"})
    yield {"Authorization": f"Bearer {_tok('admin@kainnusantara.id', 'demo12345')}", "X-Entity-Id": ENT}
    for sid in CREATED:
        DB.sales_orders.delete_one({"id": sid})
    DB.inventory_rolls.delete_many({"product_id": PID})
    DB.inventory_balances.delete_many({"product_id": PID})
    DB.inventory_movements.delete_many({"product_id": PID})
    DB.products.delete_one({"id": PID})


def _addr():
    return (DB.customers.find_one({"id": "cust_butik_bali"}) or {}).get("addresses", [{}])[0].get("id")


def _preview(h, target):
    r = requests.post(f"{BASE}/sales-orders/preview-roll-reconcile", headers=h,
                      json={"entity_id": ENT, "items": [{"product_id": PID, "quantity": target, "unit": "yard"}]})
    assert r.status_code == 200, r.text[:300]
    return r.json()[0]["options"]


def _so(h, opt, choice):
    return requests.post(f"{BASE}/sales-orders", headers=h, json={
        "customer_id": "cust_butik_bali", "shipping_address_id": _addr(), "entity_id": ENT, "notes": "TEST_L021",
        "confirm_mixed_lot": True, "allow_backorder": True,
        "items": [{"product_id": PID, "quantity": opt["total_qty"], "unit": "yard", "purchase_mode": "roll",
                   "roll_lines": opt["roll_lines"], "target_quantity": 1000, "rounding_choice": choice}]})


def test_t01_round_up_and_down_consistent_to_so_detail(H):
    opts = _preview(H, 1000)
    assert (opts["round_up"]["total_qty"], opts["round_up"]["roll_count"]) == (1005, 10)
    assert (opts["round_down"]["total_qty"], opts["round_down"]["roll_count"]) == (905, 9)
    r = _so(H, opts["round_down"], "round_down")
    assert r.status_code in (200, 201), r.text[:400]
    so = r.json()
    CREATED.append(so["id"])
    it = so["items"][0]
    assert round(it["quantity"], 2) == 905 and len(it["roll_lines"]) == 9
    assert it["roll_rounding"]["choice"] == "round_down" and it["roll_rounding"]["final_qty"] == 905
    requests.post(f"{BASE}/sales-orders/{so['id']}/cancel", headers=H, json={"reason": "TEST_L021 selesai"})


def test_t02_concurrent_orders_same_rolls_single_reservation(H):
    opt = _preview(H, 1000)["round_up"]
    out = []
    ts = [threading.Thread(target=lambda: out.append(_so(H, opt, "round_up"))) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    ok = [r.json() for r in out if r.status_code in (200, 201)]
    CREATED.extend(o["id"] for o in ok)
    held = {}
    for roll in DB.inventory_rolls.find({"product_id": PID}, {"_id": 0, "id": 1, "status": 1, "reserved_ref": 1}):
        if roll.get("status") == "reserved":
            held[roll["id"]] = (roll.get("reserved_ref") or {}).get("id")
    assert len(held) == 10 and len(set(held.values())) == 1, held
    winner = next(iter(held.values()))
    for o in ok:
        if o["id"] != winner:
            lines = {ln["roll_id"] for it in o["items"] for ln in it.get("roll_lines") or []}
            mine = {rid for rid, sid in held.items() if sid == o["id"]}
            assert not mine, "SO kalah tidak boleh memegang roll"
            assert lines.isdisjoint(held) or float(o["items"][0].get("backorder_qty") or 0) > 0
    for o in ok:
        requests.post(f"{BASE}/sales-orders/{o['id']}/cancel", headers=H, json={"reason": "TEST_L021 selesai"})


def test_ln020_t01_cut_reservation_not_counted_free(H):
    def row():
        r = requests.get(f"{BASE}/sales/stock-summary", headers=H, params={"product_id": PID, "entity_id": ENT})
        assert r.status_code == 200, r.text[:300]
        return r.json()["rows"][0]
    before = row()
    assert before["physical"] == 1005 and before["free"] == 1005
    DB.inventory_rolls.update_one({"id": "roll_TEST_l021_0"}, {"$set": {"length_reserved": 30.0}})
    after = row()
    assert after["physical"] == 1005 and after["reserved"] == 30 and after["free"] == 975
    assert "Barang datang belum siap kirim" in requests.get(
        f"{BASE}/sales/stock-summary", headers=H, params={"product_id": PID, "entity_id": ENT}).json()["atp_definition"]
    DB.inventory_rolls.update_one({"id": "roll_TEST_l021_0"}, {"$unset": {"length_reserved": ""}})

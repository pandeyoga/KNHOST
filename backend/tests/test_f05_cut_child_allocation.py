"""F-05 (uji pra-UAT 2026-10-21) — alokasi SO mengikuti roll anak setelah potong dikonfirmasi.

Reproduksi SO-00038/SO-00085: reservasi potong dikonfirmasi → roll anak lahir, tetapi
`allocations[].rolls` tetap menunjuk roll induk → pick dari daftar ditolak "tidak ter-alokasi".
Kini entri alokasi beralih ke roll anak (panjang aktual, tanpa `pending_cut`) dan sidik alokasi
harga khusus tidak berubah karena potong fisik.

Uji API memakai data acuan (akun peran) di backend `REACT_APP_BACKEND_URL`; uji layanan menulis
dokumen uji sendiri (prefiks TEST_F05) dan membersihkannya.
Jalankan: cd /app/backend && python -m pytest tests/test_f05_cut_child_allocation.py -p no:randomly -n 0 -q
"""
import asyncio
import os
import sys
import uuid

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
ENT = "ent_ksc"
CUST = "cust_toko_kain"
SKU = "KNWVN0015-L-TAUX-XA-XX-XX"          # DENIM TENCEL TAUPE A — produk reproduksi SO-00085
PW = {"admin@kainnusantara.id": "demo12345", "wh.admin@kainnusantara.id": "demo12345"}


class Api:
    def __init__(self, email):
        r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": PW.get(email, "demo1234")}, timeout=30)
        r.raise_for_status()
        self.h = {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": ENT}

    def call(self, method, path, js=None, **kw):
        r = requests.request(method, f"{BASE}{path}", json=js, headers=self.h, timeout=120, **kw)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, r.text[:300]


@pytest.fixture(scope="module")
def u():
    return {k: Api(e) for k, e in (("sales", "sales@kainnusantara.id"), ("sadm", "salesadmin@kainnusantara.id"),
                                  ("mgr", "manager@kainnusantara.id"), ("wh", "warehouse@kainnusantara.id"),
                                  ("whadm", "wh.admin@kainnusantara.id"))}


def _product_and_qty():
    """Qty = roll terpendek + 7,37 → minimal satu reservasi potong (tidak mungkin pas roll utuh)."""
    p = DB.products.find_one({"sku": SKU}, {"_id": 0, "id": 1})
    assert p, f"produk {SKU} tidak ada — jalankan restore data acuan"
    rolls = list(DB.inventory_rolls.find(
        {"product_id": p["id"], "owner_entity_id": ENT, "status": "available", "length_remaining": {"$gt": 10},
         "length_reserved": {"$not": {"$gt": 0}}}, {"_id": 0, "length_remaining": 1}))
    assert len(rolls) >= 2, "stok roll uji tidak cukup — jalankan restore data acuan"
    return p["id"], round(min(r["length_remaining"] for r in rolls) + 7.37, 2)


def _new_so(u, pid, qty):
    c, so = u["sales"].call("POST", "/sales-orders", {
        "customer_id": CUST, "shipping_address_id": "", "entity_id": ENT, "payment_term_code": "NET30",
        "items": [{"product_id": pid, "quantity": qty, "unit": "yard"}], "confirm_mixed_lot": True,
        "fulfillment_method": "kirim", "qc_request": "none"})
    assert c == 200, so
    return so


def _confirm(u, so_id):
    assert u["sadm"].call("POST", f"/sales-orders/{so_id}/verify", {"note": "uji F-05"})[0] == 200
    c, b = u["sadm"].call("POST", f"/sales-orders/{so_id}/submit-for-approval")
    assert c == 200, b
    if b.get("status") == "waiting_approval":
        c, b = u["mgr"].call("POST", f"/sales-orders/{so_id}/approve")
        assert c == 200, b
    c, b = u["sadm"].call("POST", f"/sales-orders/{so_id}/confirm")
    assert c == 200, b


def _cut_all(u, so_id):
    c, pc = u["wh"].call("GET", "/inventory/pending-cuts", params={"order_id": so_id})
    assert c == 200 and pc["items"], ("reservasi potong tidak terbentuk", pc)
    kids = []
    for i in pc["items"]:
        c, b = u["wh"].call("POST", f"/inventory/rolls/{i['roll_id']}/reservations/{i['reservation_id']}/cut",
                            {"actual_length": i["qty"], "waste": 0, "note": "uji F-05"})
        assert c == 200, b
        kids.append({**b["child"], "parent_roll_id": i["roll_id"], "reservation_id": i["reservation_id"]})
    return kids


def _alloc_rolls(u, so_id):
    c, so = u["sadm"].call("GET", f"/sales-orders/{so_id}")
    assert c == 200, so
    return so, [r for a in so.get("allocations") or [] for r in a.get("rolls") or []]


def test_potong_alokasi_menunjuk_anak_pick_dari_daftar_satu_sj_penuh(u):
    pid, qty = _product_and_qty()
    so = _new_so(u, pid, qty)
    _confirm(u, so["id"])
    kids = _cut_all(u, so["id"])

    _, rolls = _alloc_rolls(u, so["id"])
    ids = {r["roll_id"] for r in rolls}
    assert {k["id"] for k in kids} <= ids, ("alokasi masih menunjuk roll induk", rolls)
    assert not ids & {k["parent_roll_id"] for k in kids}
    assert not any(r.get("pending_cut") for r in rolls), rolls
    for k in kids:
        e = next(r for r in rolls if r["roll_id"] == k["id"])
        assert e["roll_no"] == k["roll_no"] and abs(e["length"] - k["length_remaining"]) < 0.01, e
    assert abs(sum(r["length"] for r in rolls) - qty) < 0.02

    for k in kids:   # gudang tanpa RFID: identitas roll anak lewat label
        c, b = u["wh"].call("POST", f"/inventory/rolls/{k['id']}/verify-identity", {"scanned_code": k["roll_no"]})
        assert c == 200, b
    c, tasks = u["wh"].call("GET", "/outbound/tasks")
    tl = [t for t in tasks if t.get("order_id") == so["id"]]
    assert tl, "tugas outbound tidak terbentuk"
    by_wh = {t["warehouse_id"]: t for t in tl}
    for r in rolls:   # pick PERSIS dari daftar alokasi (layar picking / Ganti Roll)
        roll = DB.inventory_rolls.find_one({"id": r["roll_id"]}, {"_id": 0, "warehouse_id": 1})
        c, b = u["wh"].call("POST", f"/outbound/tasks/{by_wh[roll['warehouse_id']]['id']}/scan-pick",
                            params={"actual_qty": r["length"], "roll_id": r["roll_id"]})
        assert c == 200, (r["roll_no"], b)
    for t in tl:
        c, b = u["wh"].call("POST", f"/outbound/tasks/{t['id']}/dispatch")
        if c != 200:   # loading check tanpa perangkat RFID → override Admin Gudang (alur UAT)
            c2, b2 = u["whadm"].call("POST", f"/outbound/so/{so['id']}/loading-check/override",
                                     {"reason": "uji F-05 tanpa perangkat RFID - validasi manual"})
            assert c2 == 200, b2
            c, b = u["wh"].call("POST", f"/outbound/tasks/{t['id']}/dispatch")
        assert c == 200, b
        assert b["task"]["status"] == "dispatched", b["task"]
        assert abs(b["shipment"]["qty"] - t["quantity"]) < 0.01, b["shipment"]
    sj = list(DB.shipments.find({"order_id": so["id"]}, {"_id": 0, "qty": 1, "task_id": 1}))
    assert len(sj) == len(tl), sj                               # satu SJ per tugas, tanpa SJ sisa
    assert abs(sum(s["qty"] for s in sj) - qty) < 0.02


def test_harga_khusus_diajukan_sebelum_potong_tetap_bisa_diputus(u):
    pid, qty = _product_and_qty()
    so = _new_so(u, pid, qty)
    price = float(so["items"][0]["price"])
    c, b = u["sadm"].call("POST", f"/sales-orders/{so['id']}/request-special-price",
                          {"product_id": pid, "requested_price": round(price * 0.95), "reason": "uji F-05 potong"})
    assert c == 200, b
    entry = next(p for p in b["pending_approvals"] if p["type"] == "special_price" and p["status"] == "pending")
    _cut_all(u, so["id"])                    # potong fisik SEBELUM keputusan manajer
    c, b = u["mgr"].call("POST", f"/sales-orders/{so['id']}/approvals/{entry['id']}/decide",
                         {"decision": "approve", "notes": "uji F-05"})
    assert c == 200, b
    assert b["items"][0]["price"] == round(price * 0.95)


# ─── Tingkat layanan: entri lama tanpa reservation_id, idempoten, sidik stabil ─────────────────────

def _run(coro_fn):
    async def main():
        from motor.motor_asyncio import AsyncIOMotorClient
        from services import roll_service as rs
        from routers import so_approvals as sa
        db = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
        old = rs.db, sa.db
        rs.db = sa.db = db
        try:
            return await coro_fn(rs, sa, db)
        finally:
            rs.db, sa.db = old
    return asyncio.run(main())


def test_layanan_entri_tanpa_reservation_id_idempoten_dan_sidik_stabil():
    async def scenario(rs, sa, db):
        tag = uuid.uuid4().hex[:6]
        so_id, pid, wid = f"so_TEST_F05_{tag}", f"prod_TEST_F05_{tag}", f"wh_TEST_F05_{tag}"
        base = {"product_id": pid, "warehouse_id": wid, "owner_entity_id": ENT, "unit": "yard", "lot": "L1",
                "created_at": "2026-01-01T00:00:00+00:00"}
        whole = {**base, "id": f"roll_TEST_F05_w_{tag}", "roll_no": f"TF05{tag}W", "status": "reserved",
                 "reserved_ref": {"type": "sales_order", "id": so_id}, "length_initial": 30.0, "length_remaining": 30.0}
        parent = {**base, "id": f"roll_TEST_F05_p_{tag}", "roll_no": f"TF05{tag}P", "status": "available",
                  "length_initial": 50.0, "length_remaining": 50.0, "length_reserved": 0}
        await db.inventory_rolls.insert_many([dict(whole), dict(parent)])
        try:
            held = await rs._reserve_length(parent, 12.5, so_id)
            rsv = held["reservation_id"]
            item = {"product_id": pid, "quantity": 42.5, "unit": "yard"}
            # entri hasil Ganti Roll lama: pending_cut TANPA reservation_id
            await db.sales_orders.insert_one({"id": so_id, "entity_id": ENT, "items": [item], "allocations": [
                {"id": "alloc1", "product_id": pid, "warehouse_id": wid, "quantity": 42.5, "rolls": [
                    {"roll_id": whole["id"], "roll_no": whole["roll_no"], "lot": "L1", "length": 30.0},
                    {"roll_id": parent["id"], "roll_no": parent["roll_no"], "lot": "L1", "length": 12.5,
                     "pending_cut": True}]},
                {"id": "alloc_bo", "product_id": "lain", "warehouse_id": wid, "quantity": 0}]})
            sig_before = await sa._alloc_sig(so_id, item)

            out = await rs.confirm_cut(parent["id"], rsv, 12.4, 0.1, "uji")
            child = out["child"]
            so = await db.sales_orders.find_one({"id": so_id}, {"_id": 0})
            rolls = so["allocations"][0]["rolls"]
            assert rolls[0]["roll_id"] == whole["id"]
            assert rolls[1]["roll_id"] == child["id"] and rolls[1]["roll_no"] == child["roll_no"]
            assert rolls[1]["length"] == 12.4 and "pending_cut" not in rolls[1]
            assert rolls[1]["cut_from_roll_id"] == parent["id"] and rolls[1]["reservation_id"] == rsv
            assert await sa._alloc_sig(so_id, item) == sig_before   # potong fisik ≠ perubahan alokasi

            # ulangi tahap akhir potong (retry) → tidak ada perubahan ganda
            again = await rs.relink_cut_allocation(so_id, rsv, parent, child)
            assert again is False
            assert (await db.sales_orders.find_one({"id": so_id}, {"_id": 0}))["allocations"] == so["allocations"]
        finally:
            await db.inventory_rolls.delete_many({"product_id": pid})
            await db.inventory_movements.delete_many({"product_id": pid})
            await db.inventory_balances.delete_many({"product_id": pid})
            await db.number_sequences.delete_many({"prefix": parent["roll_no"]})
            await db.sales_orders.delete_one({"id": so_id})
    _run(scenario)

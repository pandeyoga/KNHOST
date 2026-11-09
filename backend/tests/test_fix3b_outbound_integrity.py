"""FIX-3b — integritas alur BARANG KELUAR, POTONG, SAMPEL, transfer/makloon/perbaikan keluar & siklus TAG RFID
(audit 9 Nov: B2b, B3b, B3a; keputusan koordinator FIX-3 bagian "Alur keluar, potong & RFID").

Setiap uji menyebut ID temuan yang ditutup. Uji GAGAL di dasar `main` (sebelum FIX-3b) dan LULUS sesudahnya.
Produk, roll, SO, tugas, transfer, perangkat UJI dibuat sendiri (produk unik di gudang Jakarta yang sudah ada) dan
dibersihkan di akhir. Jalankan (stack sementara):
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_fix3b_outbound_integrity.py
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException  # noqa: E402

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:6].upper()
OWNER = "ent_ksc"
WH = "wh_jakarta"
WH2 = "wh_bandung"
OLD_TS = "2026-01-01T00:00:00+00:00"
P = f"prod_TFX3B_{TAG}"
WR = f"wh_TFX3B_RET_{TAG}"
ROLLS, SOS, TASKS, TRF, TAGS, DEVS, MISC = [], [], [], [], [], [], {"ret": [], "ro": [], "sess": [], "ship": []}
ACTOR = {"name": "uji fix3b", "id": "usr_fix3b", "role": "admin"}


@pytest.fixture(scope="module", autouse=True)
def world():
    DB.products.insert_one({"id": P, "sku": f"TFX3B-{TAG}", "name": f"Kain Uji FIX3B {TAG}", "base_unit": "yard",
                            "status": "active", "stage": "finished", "grade": "A", "category": "Kain", "price": 1000.0,
                            "harga_pokok": 700.0, "created_at": OLD_TS})
    DB.warehouses.insert_one({"id": WR, "code": f"TFX3BR-{TAG}", "name": f"TEST FIX3B RETUR {TAG}", "city": "Bandung",
                              "sharing_mode": "shared", "entity_ids": [OWNER], "active": True, "roles": ["return"],
                              "created_at": OLD_TS, "zones": []})
    yield
    rids = ROLLS + [r["id"] for r in DB.inventory_rolls.find({"product_id": P}, {"id": 1})]
    DB.inventory_rolls.delete_many({"id": {"$in": rids}})
    DB.inventory_movements.delete_many({"$or": [{"roll_id": {"$in": rids}}, {"product_id": P}]})
    DB.rfid_tags.delete_many({"$or": [{"roll_id": {"$in": rids}}, {"id": {"$in": TAGS}}]})
    DB.rfid_reads.delete_many({"roll_id": {"$in": rids}})
    DB.rfid_incidents.delete_many({"roll_id": {"$in": rids}})
    DB.rfid_print_jobs.delete_many({"items.roll_id": {"$in": rids}})
    DB.rfid_verify_sessions.delete_many({"$or": [{"order_id": {"$in": SOS}}, {"id": {"$in": MISC["sess"]}}]})
    DB.rfid_devices.delete_many({"id": {"$in": DEVS}})
    DB.sales_orders.delete_many({"id": {"$in": SOS}})
    DB.wms_tasks.delete_many({"$or": [{"id": {"$in": TASKS}}, {"order_id": {"$in": SOS}}]})
    DB.shipments.delete_many({"id": {"$in": MISC["ship"]}})
    DB.warehouse_transfers.delete_many({"$or": [{"id": {"$in": TRF}}, {"sales_order_id": {"$in": SOS}}]})
    DB.purchase_returns.delete_many({"id": {"$in": MISC["ret"]}})
    DB.repair_orders.delete_many({"id": {"$in": MISC["ro"]}})
    DB.journal_entries.delete_many({"source_id": {"$regex": f"cutw:rsv_fx3b_{TAG}"}})
    DB.inventory_balances.delete_many({"product_id": P})
    DB.notifications.delete_many({"ref": {"$regex": "|".join(TASKS) or "x^"}})
    DB.products.delete_many({"id": P})
    DB.warehouses.delete_many({"id": WR})


def _login(email):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": os.environ.get("KN_DEMO_PW", "demo12345")})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": OWNER}


@pytest.fixture(scope="module")
def adm():
    return _login("admin@kainnusantara.id")


@pytest.fixture(scope="module")
def whj():
    return _login("warehouse@kainnusantara.id")


def _id(prefix):
    return f"{prefix}_fx3b_{TAG}_{uuid.uuid4().hex[:6]}"


def _roll(qty=10.0, status="available", wh=WH, **kw):
    rid = _id("roll")
    DB.inventory_rolls.insert_one({"id": rid, "roll_no": f"FX3B-{rid[-6:]}".upper(), "product_id": P,
                                   "warehouse_id": wh, "owner_entity_id": OWNER, "length_initial": qty,
                                   "length_remaining": qty, "unit": "yard", "status": status, "grade": "A",
                                   "unit_cost": 700.0, "base_unit_cost": 700.0, "lot": f"LOT-{TAG}",
                                   "bin_id": None, "active_movement": None, "created_at": OLD_TS, **kw})
    ROLLS.append(rid)
    return rid


def _so(status, qty=25.0, **kw):
    sid = _id("so")
    DB.sales_orders.insert_one({
        "id": sid, "number": f"SO-FX3B-{sid[-6:]}", "order_number": f"SO-FX3B-{sid[-6:]}", "status": status,
        "entity_id": OWNER, "order_type": "regular", "customer_name": "Pelanggan Uji FIX3B", "customer_id": "",
        "customer_city": "Jakarta", "items": [{"product_id": P, "sku": f"TFX3B-{TAG}", "product_name": "Kain Uji",
                                                "quantity": qty, "base_quantity": qty, "unit": "yard", "base_unit": "yard",
                                                "price": 1000.0, "discount_percent": 0, "reserved_qty": qty}],
        "allocations": [], "backorders": [], "created_at": OLD_TS, "updated_at": OLD_TS, **kw})
    SOS.append(sid)
    return sid


def _task(order_id, qty, status, **kw):
    tid = _id("wms")
    DB.wms_tasks.insert_one({"id": tid, "flow_type": "outbound", "source_type": "sales_order", "order_id": order_id,
                             "order_number": "SO-FX3B", "entity_id": OWNER, "product_id": P, "product_name": "Kain Uji",
                             "quantity": qty, "picked_qty": 0.0, "shipped_qty": 0.0, "unit": "yard",
                             "warehouse_id": WH, "warehouse_name": "Gudang Jakarta", "status": status, "scan_log": [],
                             "created_at": OLD_TS, **kw})
    TASKS.append(tid)
    return tid


def _detail(resp):
    d = resp.json().get("detail")
    return d if isinstance(d, str) else (d.get("message") if isinstance(d, dict) else str(d))


def _roll_doc(rid):
    return DB.inventory_rolls.find_one({"id": rid}, {"_id": 0})


# ─── A. Ambil, eskalasi, ubah SO ─────────────────────────────────────────────────────────────────────────────
def test_resolve_escalation_never_releases_shipped_roll(adm):
    """STM-OUT-1 (P0) + K-B2b-01 — tugas terkirim sebagian: hanya "tutup sisa"; roll di SJ tidak pernah `available`."""
    so = _so("partially_shipped", 25.0)
    a = _roll(10.0, "in_transit_sales", reserved_ref={"type": "sales_order", "id": so})
    b = _roll(15.0, "committed", reserved_ref={"type": "sales_order", "id": so})
    DB.sales_orders.update_one({"id": so}, {"$set": {"allocations": [
        {"id": "alloc_" + so, "product_id": P, "warehouse_id": WH, "quantity": 25.0,
         "rolls": [{"roll_id": a, "length": 10.0}, {"roll_id": b, "length": 15.0}]}]}})
    t = _task(so, 25.0, "escalated", picked_qty=10.0, shipped_qty=10.0, allocation_id="alloc_" + so,
              escalation={"status": "pending_review", "reason": "stok fisik kurang", "prev_status": "partially_shipped"},
              scan_log=[{"scan_type": "pick", "roll_id": a, "actual_qty": 10.0},
                        {"scan_type": "dispatch", "rolls": [a], "actual_qty": 10.0}])
    bad = requests.post(f"{BASE}/outbound/tasks/{t}/resolve-escalation", headers=adm, params={"adjusted_qty": 12})
    assert bad.status_code == 400, bad.text          # bukan "tutup sisa" → ditolak (dasar: diterima)
    r = requests.post(f"{BASE}/outbound/tasks/{t}/resolve-escalation", headers=adm,
                      params={"close_remainder": "true", "resolution_notes": "tutup sisa pesanan"})
    assert r.status_code == 200, r.text
    assert _roll_doc(a)["status"] == "in_transit_sales"              # roll di SJ tetap di jalan
    assert _roll_doc(b)["status"] == "available"                     # sisa cadangan dilepas utuh (tanpa fragmen)
    assert DB.inventory_rolls.count_documents({"parent_roll_id": b}) == 0
    task = DB.wms_tasks.find_one({"id": t})
    assert task["status"] == "dispatched" and task["quantity"] == 10.0   # tidak lagi `packing` macet


def test_escalated_task_rejects_pick_and_cancelled_task_not_revived(adm, whj):
    """STM-OUT-2 — `escalated` tidak bisa diambil; tugas batal tidak hidup lagi lewat resolve tanpa qty."""
    so = _so("confirmed", 10.0)
    r1 = _roll(10.0, "committed", reserved_ref={"type": "sales_order", "id": so})
    t = _task(so, 10.0, "escalated", escalation={"status": "pending_review", "reason": "rak kosong"})
    p = requests.post(f"{BASE}/outbound/tasks/{t}/scan-pick", headers=whj,
                      params={"roll_id": _roll_doc(r1)["roll_no"], "actual_qty": 10.0})
    assert p.status_code == 400, p.text
    t2 = _task(so, 10.0, "cancelled", escalation={"status": "pending_review", "reason": "rak kosong"})
    r = requests.post(f"{BASE}/outbound/tasks/{t2}/resolve-escalation", headers=adm)
    assert r.status_code == 409, r.text
    assert DB.wms_tasks.find_one({"id": t2})["status"] == "cancelled"


def test_pick_requires_scan_and_whole_roll(adm, whj):
    """K-B1-05 / K-B3b-01 (ambil wajib pindai roll; ketik qty = darurat berizin + alasan) + STM-OUT-5 (roll utuh)."""
    so = _so("confirmed", 20.0)
    r1 = _roll(10.0, "committed", reserved_ref={"type": "sales_order", "id": so})
    r2 = _roll(10.0, "committed", reserved_ref={"type": "sales_order", "id": so})
    t = _task(so, 20.0, "created")
    no_scan = requests.post(f"{BASE}/outbound/tasks/{t}/scan-pick", headers=whj, params={"actual_qty": 5})
    assert no_scan.status_code == 400 and "pindai" in _detail(no_scan).lower(), no_scan.text
    part = requests.post(f"{BASE}/outbound/tasks/{t}/scan-pick", headers=whj,
                         params={"roll_id": _roll_doc(r1)["roll_no"], "actual_qty": 4})
    assert part.status_code == 400 and "utuh" in _detail(part).lower(), part.text
    ok = requests.post(f"{BASE}/outbound/tasks/{t}/scan-pick", headers=whj, params={"roll_id": _roll_doc(r1)["roll_no"]})
    assert ok.status_code == 200, ok.text
    assert ok.json()["picked_qty"] == 10.0 and ok.json()["status"] == "picking"
    dup = requests.post(f"{BASE}/outbound/tasks/{t}/scan-pick", headers=whj, params={"roll_id": _roll_doc(r1)["roll_no"]})
    assert dup.status_code == 409, dup.text
    bad_reason = requests.post(f"{BASE}/outbound/tasks/{t}/scan-pick", headers=adm,
                               params={"actual_qty": 10, "reason": "....."})
    assert bad_reason.status_code == 400, bad_reason.text
    emer = requests.post(f"{BASE}/outbound/tasks/{t}/scan-pick", headers=adm,
                         params={"actual_qty": 10, "reason": "scanner rusak, roll dicek manual"})
    assert emer.status_code == 200, emer.text
    assert emer.json()["scan_log"][-1]["manual_entry"]["reason"].startswith("scanner")
    assert r2  # roll kedua tidak dipindai (jalur darurat → kirim memilih roll utuh FIFO)


def test_override_keeps_committed_rolls_and_task_ids():
    """STM-OUT-3 (P0) — override SO terkonfirmasi: roll `committed` tetap teralokasi (tanpa reservasi ganda/yatim);
    tugas gudang disesuaikan, tidak dihapus-buat-ulang."""
    from services import so_override_service as ovr
    so = _so("confirmed", 10.0)
    r1 = _roll(10.0, "committed", reserved_ref={"type": "sales_order", "id": so})
    r2 = _roll(8.0, "available")
    DB.sales_orders.update_one({"id": so}, {"$set": {"allocations": [
        {"id": "alloc_" + so, "product_id": P, "warehouse_id": WH, "quantity": 10.0, "owner_entity_id": OWNER,
         "rolls": [{"roll_id": r1, "length": 10.0}]}]}})
    t = _task(so, 10.0, "created", allocation_id="alloc_" + so)
    run(ovr.apply(so, {"note": "tambah qty pelanggan", "lines": [{"product_id": P, "quantity": 18.0}]}, ACTOR))
    doc = DB.sales_orders.find_one({"id": so})
    alloc_rolls = {x.get("roll_id") for a in doc["allocations"] for x in a.get("rolls") or []}
    assert r1 in alloc_rolls, doc["allocations"]                     # roll committed lama TIDAK yatim
    held = list(DB.inventory_rolls.find({"reserved_ref.id": so}, {"_id": 0, "id": 1, "status": 1, "length_remaining": 1}))
    cut = [x for r in DB.inventory_rolls.find({"length_reservations.ref.id": so}, {"_id": 0, "length_reservations": 1})
           for x in r["length_reservations"] if x["ref"]["id"] == so]
    total = round(sum(h["length_remaining"] for h in held) + sum(x["qty"] for x in cut), 2)
    assert total == 18.0, (held, cut)                                # tanpa reservasi ganda (dasar: 10 + 18 = 28)
    assert all(h["status"] == "committed" for h in held) and all(x["status"] == "committed" for x in cut), (held, cut)
    assert r2  # roll tersedia untuk tambahan
    task = DB.wms_tasks.find_one({"id": t})
    assert task is not None and task["quantity"] == 18.0 and task["status"] == "created"


def test_draft_so_cannot_hold_rolls_and_cancel_releases_any_status(adm):
    """STM-OUT-4 — Ganti Roll ditolak pada SO `draft`; batal SO `draft` melepas roll yang masih memegang reservasi."""
    so = _so("draft", 10.0)
    r = _roll(10.0, "available")
    g = requests.post(f"{BASE}/sales-orders/{so}/items/{P}/reallocate", headers=adm,
                      json={"roll_lines": [{"roll_id": r, "take_qty": 10.0}]})
    assert g.status_code == 409, g.text
    assert _roll_doc(r)["status"] == "available"
    so2 = _so("draft", 10.0)
    r2 = _roll(10.0, "reserved", reserved_ref={"type": "sales_order", "id": so2})
    c = requests.post(f"{BASE}/sales-orders/{so2}/cancel", headers=adm, json={"reason": "pelanggan batal pesan"})
    assert c.status_code == 200, c.text
    assert _roll_doc(r2)["status"] == "available" and _roll_doc(r2)["reserved_ref"] is None


def test_cancel_after_pick_returns_to_rack_and_closes_escalation(adm):
    """FLW-OUT-4 — batal sesudah ambil: roll yang sudah diambil masuk antrean "kembalikan ke rak" (bin dikosongkan),
    bukan langsung di bin asal; eskalasi menunggu ikut ditutup (STM-OUT-2)."""
    so = _so("picked", 10.0)
    r = _roll(10.0, "committed", reserved_ref={"type": "sales_order", "id": so}, bin_id="bin_x_fx3b", bin_code="X-01")
    t = _task(so, 10.0, "escalated", picked_qty=10.0, escalation={"status": "pending_review", "reason": "label rusak"},
              scan_log=[{"scan_type": "pick", "roll_id": r, "actual_qty": 10.0}])
    c = requests.post(f"{BASE}/sales-orders/{so}/cancel", headers=adm, json={"reason": "pelanggan batal pesan"})
    assert c.status_code == 200, c.text
    d = _roll_doc(r)
    assert d["status"] == "available" and not d.get("bin_id") and d["return_to_rack"]["from_bin_id"] == "bin_x_fx3b"
    task = DB.wms_tasks.find_one({"id": t})
    assert task["status"] == "cancelled" and task["escalation"]["status"] == "cancelled"


def test_escalation_reason_k14(whj):
    """K-14 (validator bersama) di eskalasi keluar."""
    so = _so("confirmed", 10.0)
    t = _task(so, 10.0, "created")
    r = requests.post(f"{BASE}/outbound/tasks/{t}/escalate", headers=whj, params={"reason": "....."})
    assert r.status_code == 400, r.text


# ─── B. Backorder, POD per SJ ────────────────────────────────────────────────────────────────────────────────
def test_backorder_fillable_after_partial_ship():
    """FLW-OUT-2 (P0) — SO `partially_shipped` dengan backorder bisa diisi dari stok (dulu 409 "sedang diproses")."""
    from services import backorder_service as bo
    so = _so("partially_shipped", 15.0, has_backorder=True, backorders=[
        {"id": "bo_" + TAG, "product_id": P, "backorder_qty": 5.0, "reserved_qty": 10.0, "requested_qty": 15.0,
         "status": "waiting_stock", "customer_city": "Jakarta"}])
    _task(so, 10.0, "partially_shipped", picked_qty=10.0, shipped_qty=10.0)
    r = _roll(5.0, "available")
    got = run(bo.fulfill_from_stock(so, P, 5.0, "uji fix3b", roll_ids=[r]))
    assert got == 5.0
    doc = DB.sales_orders.find_one({"id": so})
    assert doc["status"] == "partially_shipped" and not doc["has_backorder"]
    assert _roll_doc(r)["status"] == "committed" and _roll_doc(r)["reserved_ref"]["id"] == so


def test_pod_per_shipment_delivers_its_rolls():
    """FLW-OUT-2 / K-B2b-02 — POD per SJ: roll SJ ber-POD `delivered` walau SO masih kirim sebagian."""
    from services import so_delivery_service as sod
    so = _so("partially_shipped", 20.0)
    r = _roll(10.0, "in_transit_sales", reserved_ref={"type": "sales_order", "id": so})
    sid = _id("shp")
    MISC["ship"].append(sid)
    DB.shipments.insert_one({"id": sid, "shipment_no": "SJ-FX3B", "order_id": so, "status": "dispatched",
                             "logistics_status": "delivered", "rolls": [{"roll_id": r, "length": 10.0}]})
    run(sod.on_pod([so], "uji fix3b"))
    assert _roll_doc(r)["status"] == "delivered"
    assert DB.sales_orders.find_one({"id": so})["status"] == "partially_shipped"


def test_return_warehouse_excluded_from_auto_allocation():
    """FLW-OUT-3 / K-B2b-07 — Gedung Retur tidak ikut alokasi otomatis SO."""
    from services import roll_service as rs
    r_ret = _roll(10.0, "available", wh=WR)
    r_ok = _roll(10.0, "available")
    ids = {r["id"] for r in run(rs._available_rolls_for_order(P, OWNER, "so_x_fx3b"))}
    assert r_ok in ids and r_ret not in ids


def test_reservation_expiry_skips_approved_and_get_does_not_write(adm, monkeypatch):
    """ANOM-06 (calon P0) / K-B2b-12 / B3a STK-11 — SO `approved` tidak kedaluwarsa otomatis; GET tidak menulis."""
    from services import inventory_service
    past = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    so_get = _so("reserved", 10.0, reservation_expires_at=past)
    requests.get(f"{BASE}/sales-orders", headers=adm, params={"limit": 5})
    assert DB.sales_orders.find_one({"id": so_get})["status"] == "reserved"   # GET tidak lagi melepas reservasi
    so_app = _so("approved", 10.0, reservation_expires_at=past)
    r = _roll(10.0, "committed", reserved_ref={"type": "sales_order", "id": so_app})

    class _C:
        def __init__(self, c):
            self._c = c

        def find(self, q, *a, **k):
            return self._c.find({**q, "id": {"$in": [so_get, so_app]}}, *a, **k)

        def __getattr__(self, n):
            return getattr(self._c, n)

    class _D:
        def __init__(self, d):
            self._d = d

        def __getattr__(self, n):
            return _C(getattr(self._d, n)) if n == "sales_orders" else getattr(self._d, n)

    monkeypatch.setattr(inventory_service, "db", _D(inventory_service.db))
    run(inventory_service.expire_old_reservations())
    assert DB.sales_orders.find_one({"id": so_app})["status"] == "approved"
    assert _roll_doc(r)["status"] == "committed"
    assert DB.sales_orders.find_one({"id": so_get})["status"] == "expired"   # belum disetujui → tetap kedaluwarsa


def test_reserve_specific_rolls_rollback_keeps_other_reservations():
    """POT-05 (calon P0) — rollback pemilihan roll hanya melepas yang dibuat panggilan itu."""
    from services.roll_service import reserve_specific_rolls
    so = _so("reserved", 30.0)
    kept = _roll(10.0, "reserved", reserved_ref={"type": "sales_order", "id": so})
    fresh = _roll(10.0, "available")
    bad = _roll(10.0, "damaged")
    with pytest.raises(HTTPException):
        run(reserve_specific_rolls([{"roll_id": fresh, "take_qty": 0}, {"roll_id": bad, "take_qty": 0}],
                                   {"type": "sales_order", "id": so}, product_id=P))
    assert _roll_doc(kept)["status"] == "reserved" and _roll_doc(kept)["reserved_ref"]["id"] == so
    assert _roll_doc(fresh)["status"] == "available"


# ─── C. Potong & sampel ──────────────────────────────────────────────────────────────────────────────────────
def test_sample_cut_respects_reserved_length():
    """CUT-1 (P0) — potong sampel tidak boleh memakan panjang yang sudah dipesan SO lain."""
    from services import sample_sale_service as smp
    r = _roll(20.0, "available", length_reserved=18.0, length_reservations=[
        {"id": "rsv_other_" + TAG, "ref": {"type": "sales_order", "id": "so_lain"}, "qty": 18.0, "status": "reserved"}])
    with pytest.raises(HTTPException) as ei:
        run(smp._resolve_roll(P, "TFX3B", 5.0, "yard", r, "", OWNER))
    assert ei.value.status_code == 409
    sug = run(smp.suggest_roll(P, 5.0, [OWNER], [WH]))
    assert not sug or sug["id"] != r


def test_cut_waste_journal_limit_and_remnant():
    """CUT-2 (susut dijurnal; batas % setelan + alasan) + CUT-4 (sisa < ambang → remnant, aturan sama SO & sampel)."""
    from services import roll_service as rs
    rsv = f"rsv_fx3b_{TAG}_a"
    r = _roll(12.0, "available", length_reserved=10.0, length_reservations=[
        {"id": rsv, "ref": {"type": "sales_order", "id": "so_cut_fx3b"}, "qty": 10.0, "status": "reserved"}])
    with pytest.raises(HTTPException) as ei:   # susut 5% > batas bawaan 3% tanpa alasan
        run(rs.confirm_cut(r, rsv, 10.0, waste=0.5, actor="uji"))
    assert ei.value.status_code == 400
    out = run(rs.confirm_cut(r, rsv, 10.0, waste=0.5, actor="uji", waste_reason="ujung kain sobek saat dipotong"))
    assert out["cut"]["waste_reason"].startswith("ujung")
    je = DB.journal_entries.find_one({"source_type": "inventory_writeoff", "source_id": f"cutw:{rsv}"})
    assert je is not None
    parent = _roll_doc(r)
    assert parent["length_remaining"] == 1.5 and parent["is_remnant"] is True


def test_cutting_receive_rejects_cancelled_and_cross_warehouse_needs_transfer():
    """CUT-3 (P0) / K-B2b-10 — serah-terima Admin Cutting: tugas batal ditolak; lintas gedung = dokumen transfer."""
    from services import cutting_service as cs
    so = _so("confirmed", 2.0)
    c1 = _roll(2.0, "available", is_sample_cut=True)
    t1 = _task(so, 2.0, "cancelled", task_subtype="sample_cut", roll_id=c1)
    with pytest.raises(HTTPException) as ei:
        run(cs.receive(t1, WH2, ACTOR, [OWNER]))
    assert ei.value.status_code == 409
    assert _roll_doc(c1)["warehouse_id"] == WH
    c2 = _roll(2.0, "reserved", reserved_ref={"type": "sales_order", "id": so}, is_sample_cut=True)
    t2 = _task(so, 2.0, "packing", task_subtype="sample_cut", roll_id=c2, picked_qty=2.0)
    out = run(cs.receive(t2, WH2, ACTOR, [OWNER]))
    assert out.get("transfer_required") is True
    assert _roll_doc(c2)["warehouse_id"] == WH                       # roll TIDAK dipindah langsung
    trf = DB.warehouse_transfers.find_one({"cutting_task_id": t2})
    assert trf and trf["status"] == "waiting_approval" and trf["dest_warehouse_id"] == WH2
    TRF.append(trf["id"])
    assert not (DB.wms_tasks.find_one({"id": t2}).get("cutting_handoff") or {}).get("received_at")


# ─── D. Keluar non-SO: batal di jalan ───────────────────────────────────────────────────────────────────────
def test_cancel_in_transit_transfer_becomes_returning(adm):
    """FLW-OUT-11 / K-B2b-03 — batal transfer di jalan: `returning`, roll tetap di jalan sampai diterima di asal."""
    tid = _id("trn")
    TRF.append(tid)
    r = _roll(10.0, "in_transit_transfer", reserved_ref={"type": "wh_transfer", "id": tid},
              transfer_prior_status="reserved")
    DB.warehouse_transfers.insert_one({
        "id": tid, "code": f"TRF-FX3B-{TAG}", "transfer_kind": "intra_entity", "entity_id": OWNER,
        "source_warehouse_id": WH, "dest_warehouse_id": WH2, "status": "dispatched",
        "items": [{"product_id": P, "qty": 10.0, "unit": "yard", "owner_entity_id": OWNER,
                   "rolls": [{"roll_id": r, "length": 10.0}]}], "created_at": OLD_TS})
    c = requests.delete(f"{BASE}/transfers/{tid}", headers=adm, params={"reason": "truk balik, salah tujuan"})
    assert c.status_code == 200, c.text
    assert c.json()["status"] == "returning"
    assert _roll_doc(r)["status"] == "in_transit_transfer"          # tidak langsung tersedia di asal
    rc = requests.post(f"{BASE}/transfers/{tid}/receive", headers=adm,
                       json={"lines": [{"roll_id": r, "outcome": "received"}]})
    assert rc.status_code == 200, rc.text
    d = _roll_doc(r)
    assert d["status"] == "available" and d["warehouse_id"] == WH and not d.get("transfer_prior_status")
    t = DB.warehouse_transfers.find_one({"id": tid})
    assert t["status"] == "cancelled" and t["completion_basis"] == "returned_to_source"


def test_cancel_sent_repair_becomes_returning():
    """FLW-OUT-11 / K-B2b-03 — batal perbaikan yang sudah dikirim: `returning` + terima kembali."""
    from services import repair_order_service as ros
    ro = _id("rpr")
    MISC["ro"].append(ro)
    r = _roll(5.0, "wip", repair_open=ro, bucket_ref={"type": "repair", "id": ro})
    DB.repair_orders.insert_one({"id": ro, "number": f"RO-FX3B-{TAG}", "status": "sent", "entity_id": OWNER,
                                 "lines": [{"roll_id": r, "roll_no": "X", "prev_status": "available", "qty_sent": 5.0}],
                                 "timeline": [], "created_at": OLD_TS})
    out = run(ros.cancel(ro, ACTOR, "vendor tutup, batal perbaikan"))
    assert out["status"] == "returning" and _roll_doc(r)["status"] == "wip"
    back = run(ros.receive_back(ro, ACTOR))
    assert back["status"] == "cancelled" and _roll_doc(r)["status"] == "available"


def test_subcon_return_does_not_revive_consumed():
    """MKO-03 (calon P0) — retur bahan makloon "semua" tidak menghidupkan roll `consumed`."""
    from services import stock_bucket_service as sb
    ref = _id("sub")
    gone = _roll(0.0, "consumed", bucket_ref={"type": "subcon", "id": ref}, consumed_ref=ref)
    live = _roll(6.0, "subcon", bucket_ref={"type": "subcon", "id": ref})
    run(sb.move_rolls_by_ref(ref, "available", movement_type="subcon_return_cancel"))
    assert _roll_doc(gone)["status"] == "consumed"
    assert _roll_doc(live)["status"] == "available"


def test_qc_return_reversal_restores_rolls():
    """PRT-01/02 (calon P0) — reversal retur dari tolak QC memulihkan roll (ke karantina), tidak hanya jurnal/AP."""
    from services import purchase_return_service as prsvc
    from services import purchase_return_state as prs
    ret = _id("pret")
    MISC["ret"].append(ret)
    r = _roll(10.0, "returned_supplier", returned_ref={"type": "purchase_return", "id": ret})
    DB.purchase_returns.insert_one({"id": ret, "number": f"PR-FX3B-{TAG}", "status": "approved", "stock_adjusted": True,
                                    "supplier_status": prs.ACCEPTED, "supplier_outcome": prs.OUTCOME_AP_CREDIT,
                                    "entity_id": OWNER, "source": "qc_reject", "po_id": "", "grand_total": 0})
    DB.inventory_movements.insert_one({"id": _id("mov"), "product_id": P, "warehouse_id": WH, "owner_entity_id": OWNER,
                                       "movement_type": "qc_reject_return", "quantity": 10.0, "roll_id": r,
                                       "ref_type": "purchase_return", "ref_id": ret, "timestamp": OLD_TS})
    out = run(prsvc.reverse_settlement(ret, "uji fix3b", "salah tolak QC"))
    assert out["_reversal_summary"]["rolls_restored"] == 1
    assert _roll_doc(r)["status"] == "quarantine"


# ─── E. RFID ─────────────────────────────────────────────────────────────────────────────────────────────────
def _epc():
    from services.rfid_service import generate_epc
    return generate_epc()


def test_retired_epc_never_reused_and_lookup_ignores_retired(adm):
    """RFID-2 (P0) — EPC tag pensiun tidak bisa ditulis ke roll lain; lookup tidak mengembalikan roll lama."""
    epc = _epc()
    old = _roll(10.0, "available")
    tid = _id("rtag")
    TAGS.append(tid)
    DB.rfid_tags.insert_one({"id": tid, "epc": epc, "roll_id": old, "status": "retired", "owner_entity_id": OWNER,
                             "product_id": P, "warehouse_id": WH})
    new = _roll(10.0, "available")
    e = requests.post(f"{BASE}/rfid/tags/encode", headers=adm, json={"roll_id": new, "epc": epc})
    assert e.status_code == 409, e.text
    lk = requests.get(f"{BASE}/rfid/lookup", headers=adm, params={"code": epc, "record": "false"})
    assert lk.status_code == 404, lk.text


def test_mark_printed_rfid_needs_chip_proof(adm):
    """RFID-3 / K-B2b-13 — "tandai tercetak" manual label RFID: tag tetap `pending_print` sampai EPC terbaca."""
    r = _roll(10.0, "available")
    j = requests.post(f"{BASE}/rfid/print-jobs", headers=adm, json={"roll_ids": [r]})
    assert j.status_code == 200, j.text
    job = j.json()
    m = requests.post(f"{BASE}/rfid/print-jobs/{job['id']}/mark-printed", headers=adm)
    assert m.status_code == 200, m.text
    tag = DB.rfid_tags.find_one({"roll_id": r})
    assert tag["status"] == "pending_print"
    v = requests.post(f"{BASE}/rfid/print-jobs/{job['id']}/verify/start", headers=adm)
    assert v.status_code == 200, v.text
    MISC["sess"].append(v.json()["id"])
    s = requests.post(f"{BASE}/rfid/verify-sessions/{v.json()['id']}/scan", headers=adm, json={"epcs": [tag["epc"]]})
    assert s.status_code == 200, s.text
    c = requests.post(f"{BASE}/rfid/verify-sessions/{v.json()['id']}/complete", headers=adm)
    assert c.status_code == 200, c.text
    assert DB.rfid_tags.find_one({"id": tag["id"]})["status"] == "active"


def _device(dtype, **kw):
    did = _id("rdev")
    DEVS.append(did)
    DB.rfid_devices.insert_one({"id": did, "code": f"DEV-FX3B-{did[-6:]}", "name": "Perangkat uji FIX3B", "type": dtype,
                                "direction": "out" if dtype == "gate" else "n/a", "warehouse_id": WH,
                                "status": "online", "enabled": True, "last_heartbeat": datetime.now(timezone.utc).isoformat(),
                                "created_at": OLD_TS, **kw})
    return did


def _tagged_roll(status="committed", **kw):
    r = _roll(10.0, status, **kw)
    tid = _id("rtag")
    TAGS.append(tid)
    epc = _epc()
    DB.rfid_tags.insert_one({"id": tid, "epc": epc, "roll_id": r, "status": "active", "owner_entity_id": OWNER,
                             "product_id": P, "warehouse_id": WH, "sku": "TFX3B"})
    DB.inventory_rolls.update_one({"id": r}, {"$set": {"rfid_tag_id": tid}})
    return r, epc


def test_legacy_gate_simulator_requires_test_device(adm):
    """RFID-4 — simulator gate lama di reader produksi ditolak; di perangkat uji tanpa `gate_exit`/alarm nyata."""
    dev = _device("gate")
    r, _ = _tagged_roll("available")
    s = requests.post(f"{BASE}/rfid/gate/simulate", headers=adm, json={"device_id": dev, "roll_id": r})
    assert s.status_code == 409, s.text
    assert not _roll_doc(r).get("gate_exit")
    DB.rfid_devices.update_one({"id": dev}, {"$set": {"test_device": True}})
    s2 = requests.post(f"{BASE}/rfid/gate/simulate", headers=adm, json={"device_id": dev, "roll_id": r})
    if s2.status_code == 409:   # mode simulasi PT mati di data ini → simulator ditolak (benar)
        assert "simulasi" in _detail(s2).lower()
        return
    assert s2.status_code == 200, s2.text
    assert not _roll_doc(r).get("gate_exit")
    assert DB.rfid_incidents.count_documents({"roll_id": r}) == 0
    assert DB.rfid_reads.find_one({"roll_id": r})["simulated"] is True


def test_handheld_key_rejected_on_legacy_ingest():
    """RFID-5 — key handheld tidak diterima `/rfid/ingest` (wajib `/api/handheld` + sesi operator)."""
    from services import rfid_ingest_service as ing
    dev = _device("handheld")
    key = run(ing.ensure_api_key(dev))["api_key"]
    r = requests.post(f"{BASE}/rfid/ingest", headers={"X-Device-Key": key}, json={"epcs": [_epc()]})
    assert r.status_code == 409, r.text


def test_v2_simulator_requires_test_device():
    """RFID-1 / RFID-9 / K-B2b-09 — simulator V2 hanya di perangkat bertanda uji (dan PT bermode simulasi)."""
    from services import rfid_v2_simulator as sim
    dev = DB.rfid_devices.find_one({"id": _device("gate", protocol="v2")}, {"_id": 0})
    with pytest.raises(HTTPException) as ei:
        run(sim.run(dev, "empty"))
    d = ei.value.detail
    assert ei.value.status_code == 409 and (d.get("code") if isinstance(d, dict) else "") == "SIMULATOR_NOT_ALLOWED", d


def test_gate_exemption_requires_healthy_out_reader(monkeypatch):
    """RFID-12 — gedung gate membebaskan cek muat hanya bila reader OUT tertaut sehat; reader mati → wajib lagi."""
    from services import gate_txn_service as gt
    from services import loading_check_service as lc
    dev = _device("gate", protocol="v2", v2_telemetry_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                  v2_telemetry={"radio_state": "running"})

    async def _pol(_wh):
        return {"effective_mode": "gate", "device_ids_out": [dev], "device_ids_in": []}

    monkeypatch.setattr(gt, "gate_policy", _pol)
    assert run(lc._gate_validates_out(WH)) is False
    DB.rfid_devices.update_one({"id": dev}, {"$set": {"v2_telemetry_at": datetime.now(timezone.utc).isoformat()}})
    assert run(lc._gate_validates_out(WH)) is True


def test_loading_check_manual_epc_not_proof_and_expected_refreshed():
    """K-B3b-02 (EPC tempel manual bukan bukti) + FLW-OUT-6 (yang diharapkan dihitung ulang saat selesai)."""
    from services import loading_check_service as lc
    from services import rfid_print_service as rps
    so = _so("picked", 10.0)
    _, epc = _tagged_roll("committed", reserved_ref={"type": "sales_order", "id": so})
    s = run(lc.start(so, [OWNER], "uji", WH))
    run(rps.scan_session(s["id"], [epc], [OWNER], ["loading_check"], "manual", "uji"))
    out = run(lc.complete(s["id"], [OWNER]))
    assert out["result"] == "manual_unverified", out.get("result")
    # FLW-OUT-6 — roll ditulis tag-nya SELAMA sesi → tidak dihitung "lebih"/"tanpa tag"
    so2 = _so("picked", 10.0)
    r2 = _roll(10.0, "committed", reserved_ref={"type": "sales_order", "id": so2})
    s2 = run(lc.start(so2, [OWNER], "uji", WH))
    assert s2["untagged_count"] == 1
    tid = _id("rtag")
    TAGS.append(tid)
    epc2 = _epc()
    DB.rfid_tags.insert_one({"id": tid, "epc": epc2, "roll_id": r2, "status": "active", "owner_entity_id": OWNER,
                             "product_id": P, "warehouse_id": WH})
    DB.inventory_rolls.update_one({"id": r2}, {"$set": {"rfid_tag_id": tid}})
    run(rps.scan_session(s2["id"], [epc2], [OWNER], ["loading_check"], "device", "C72 uji", "dev_x"))
    out2 = run(lc.complete(s2["id"], [OWNER]))
    assert out2["result"] == "clean", (out2.get("result"), out2.get("extra"), out2.get("missing"))

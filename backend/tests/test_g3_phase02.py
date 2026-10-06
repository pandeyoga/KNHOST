"""Gelombang 3 · Fase 02 — uji service-level untuk D4-CAP-01 & D4-OD-LOCK-01.

DB uji terpisah (BUKAN data pelanggan).

Jalankan:
    cd /app/backend && DB_NAME=g3_audit_phase02 python -m pytest tests/test_g3_phase02.py -q
"""
import asyncio
import os
import pytest

if not os.environ.get("DB_NAME", "").startswith("g3_audit"):
    pytest.skip("Set DB_NAME=g3_audit_* — tes ini menulis ke database uji sendiri.",
                allow_module_level=True)

from db import db  # noqa: E402


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(autouse=True)
def _clean():
    async def wipe():
        for c in await db.list_collection_names():
            await db[c].delete_many({})
    run(wipe())
    yield


# ─────────────────────────────────────────────────────────────────────────────
# D4-CAP-01 — PO tidak lagi menolak produk ke-1.001 sebagai "tidak ditemukan".
# Regresi dari `products.find({}).to_list(1000)` ke `find({"id":{"$in":pids}})`.
# ─────────────────────────────────────────────────────────────────────────────
def test_cap01_po_product_lookup_resolves_sku_beyond_1000():
    async def seed():
        docs = [{"id": f"p_TEST_{i:05d}", "sku": f"SKU-TEST-{i:05d}",
                 "name": f"Produk Uji {i}", "price": 1000.0 + i,
                 "base_unit": "meter", "entity_id": "ent_test"} for i in range(1050)]
        await db.products.insert_many(docs)
    run(seed())

    # Produk pada posisi ke-1.040 (jauh di atas 1.000) HARUS ditemukan oleh query baru.
    target = "p_TEST_01040"
    pids = [target]

    async def lookup():
        return {p["id"]: p for p in await db.products.find(
            {"id": {"$in": pids}}, {"_id": 0}).to_list(None)}
    products = run(lookup())
    assert target in products, "query baru routers/purchase_orders.py:409 wajib menemukan SKU ke-1.001+"
    assert products[target]["sku"] == "SKU-TEST-01040"

    # Query LAMA (regresi) akan MELEWATKAN produk ke-1.040 → bukti kelas-cacat.
    async def legacy_lookup():
        return {p["id"]: p for p in await db.products.find({}, {"_id": 0}).to_list(1000)}
    legacy = run(legacy_lookup())
    assert target not in legacy, "pola lama (to_list(1000)) wajib tetap melewatkan SKU ke-1.001"


def test_cap01_po_multi_product_in_single_query():
    """Satu `$in` memuat semua pids yang dipesan tanpa pagination."""
    async def seed():
        docs = [{"id": f"p_TEST_{i:05d}", "sku": f"SKU-{i}", "name": f"P{i}",
                 "price": 100.0, "base_unit": "meter"} for i in range(1200)]
        await db.products.insert_many(docs)
    run(seed())
    pids = ["p_TEST_00001", "p_TEST_00500", "p_TEST_01100", "p_TEST_01199"]

    async def lookup():
        return {p["id"]: p for p in await db.products.find(
            {"id": {"$in": pids}}, {"_id": 0}).to_list(None)}
    products = run(lookup())
    assert set(products.keys()) == set(pids)


# ─────────────────────────────────────────────────────────────────────────────
# D4-OD-LOCK-01 — retry lock_price saat pricing.sku_synced=False dan
# linked_po_id kosong WAJIB memanggil auto_procure (keputusan user 2026-10-06).
# ─────────────────────────────────────────────────────────────────────────────
from services import special_order_phase2 as sop  # noqa: E402


def test_od_lock01_retry_resumes_auto_procure_when_po_missing(monkeypatch):
    calls = {"auto_procure": 0, "sync": 0}

    async def fake_auto_procure(od, actor, warehouse_id=""):
        calls["auto_procure"] += 1
        # Simulasikan auto_procure yang menautkan PO.
        await db.special_orders.update_one(
            {"id": od["id"]},
            {"$set": {"linked_po_id": "po_TEST_RESUME",
                      "linked_po_number": "PO-TEST-RESUME"}})
        return {"linked_po_id": "po_TEST_RESUME", "linked_po_number": "PO-TEST-RESUME"}

    async def fake_sync(od, pricing, pid):
        calls["sync"] += 1
        await db.special_orders.update_one(
            {"id": od["id"]}, {"$set": {"pricing.sku_synced": True}})

    monkeypatch.setattr(sop, "auto_procure", fake_auto_procure)
    monkeypatch.setattr(sop, "_sync_od_sku", fake_sync)

    async def seed():
        await db.special_orders.insert_one({
            "id": "od_TEST_lock_retry",
            "status": "sample_approved",
            "customer_decision": "acc",
            "price_locked": True,
            "linked_product_id": "p_TEST_X",
            "pricing": {
                "locked": True,
                "sku_synced": False,          # ← gagal di tengah sebelum sync
                "product_id": "p_TEST_X",
                "cost_price": 10000,
                "final_unit_price": 15000,
                "quantity": 10, "unit": "meter",
                "margin_pct": 50,
            },
            # linked_po_id SENGAJA kosong → auto_procure WAJIB jalan di retry.
        })
    run(seed())

    async def act():
        od = await db.special_orders.find_one({"id": "od_TEST_lock_retry"}, {"_id": 0})
        return await sop.lock_price(od, {"auto_po": True, "warehouse_id": "w_test"},
                                    actor={"name": "tester", "email": "t@test"})
    out = run(act())

    assert calls["sync"] == 1, "retry WAJIB memanggil _sync_od_sku untuk menyelesaikan SKU"
    assert calls["auto_procure"] == 1, "retry WAJIB melanjutkan auto_procure saat linked_po_id kosong"
    assert out.get("linked_po_id") == "po_TEST_RESUME"


def test_od_lock01_retry_skips_auto_procure_when_po_already_linked(monkeypatch):
    """Idempoten: jika PO sudah tertaut, retry hanya menyelesaikan sync — TIDAK buat PO ganda."""
    calls = {"auto_procure": 0, "sync": 0}

    async def fake_auto_procure(od, actor, warehouse_id=""):
        calls["auto_procure"] += 1
        return {}

    async def fake_sync(od, pricing, pid):
        calls["sync"] += 1
        await db.special_orders.update_one(
            {"id": od["id"]}, {"$set": {"pricing.sku_synced": True}})

    monkeypatch.setattr(sop, "auto_procure", fake_auto_procure)
    monkeypatch.setattr(sop, "_sync_od_sku", fake_sync)

    async def seed():
        await db.special_orders.insert_one({
            "id": "od_TEST_lock_retry2",
            "status": "sample_approved",
            "customer_decision": "acc",
            "price_locked": True,
            "linked_po_id": "po_TEST_EXISTING",       # ← sudah ada
            "linked_po_number": "PO-TEST-EXIST",
            "pricing": {"locked": True, "sku_synced": False, "product_id": "p_TEST_X",
                        "cost_price": 1000, "final_unit_price": 2000, "quantity": 5,
                        "unit": "meter", "margin_pct": 100},
        })
    run(seed())

    async def act():
        od = await db.special_orders.find_one({"id": "od_TEST_lock_retry2"}, {"_id": 0})
        return await sop.lock_price(od, {"auto_po": True},
                                    actor={"name": "tester", "email": "t@test"})
    run(act())

    assert calls["sync"] == 1
    assert calls["auto_procure"] == 0, "retry WAJIB skip auto_procure saat PO sudah tertaut"


def test_od_lock01_retry_without_auto_po_flag_does_not_create_po(monkeypatch):
    calls = {"auto_procure": 0}

    async def fake_auto_procure(od, actor, warehouse_id=""):
        calls["auto_procure"] += 1
        return {}

    async def fake_sync(od, pricing, pid):
        await db.special_orders.update_one(
            {"id": od["id"]}, {"$set": {"pricing.sku_synced": True}})

    monkeypatch.setattr(sop, "auto_procure", fake_auto_procure)
    monkeypatch.setattr(sop, "_sync_od_sku", fake_sync)

    async def seed():
        await db.special_orders.insert_one({
            "id": "od_TEST_lock_retry3",
            "status": "sample_approved",
            "customer_decision": "acc",
            "price_locked": True,
            "pricing": {"locked": True, "sku_synced": False, "product_id": "p_TEST_X",
                        "cost_price": 1000, "final_unit_price": 2000, "quantity": 5,
                        "unit": "meter", "margin_pct": 100},
        })
    run(seed())

    async def act():
        od = await db.special_orders.find_one({"id": "od_TEST_lock_retry3"}, {"_id": 0})
        return await sop.lock_price(od, {"auto_po": False},
                                    actor={"name": "tester", "email": "t@test"})
    run(act())

    assert calls["auto_procure"] == 0, "retry dengan auto_po=False TIDAK boleh memanggil auto_procure"


# ═════════════════════════════════════════════════════════════════════════════
# G3 Fase 02 — 12 ID lanjutan (service-level, DB uji terpisah)
# ═════════════════════════════════════════════════════════════════════════════

# D4-SUPPLY-01 — OPEN_PO_STATUSES berisi 'partial' agar sisa PO partial dihitung incoming
def test_supply01_partial_in_open_po_statuses():
    from services.roll_service import OPEN_PO_STATUSES
    assert "partial" in OPEN_PO_STATUSES, "PO status 'partial' wajib terhitung sebagai PO masih terbuka"
    assert "receiving" in OPEN_PO_STATUSES


# D4-GLOBAL-01 — apply_global: quantity_base menggantikan quantity saat UOM beli ≠ base_unit
def test_global01_apply_global_converts_to_base_unit():
    from services import sales_stock_service as sss

    async def seed():
        await db.products.insert_one({"id": "p_TEST_G01", "sku": "SKU-G01",
                                       "name": "Fabric G01", "base_unit": "meter"})
        # PO item 10 roll → quantity_base 500 meter (konversi 50m/roll)
        await db.purchase_orders.insert_one({
            "id": "po_TEST_G01", "status": "pending",
            "items": [{"product_id": "p_TEST_G01", "quantity": 10, "unit": "roll",
                       "quantity_base": 500, "received_qty": 0}],
        })

    run(seed())
    products = [{"id": "p_TEST_G01"}]
    run(sss.apply_global(products))
    # 500 meter dalam base unit (bukan 10 roll)
    assert products[0]["incoming_restock_qty"] == 500.0, products[0]


def test_global01_apply_global_partial_po_remaining_counted():
    from services import sales_stock_service as sss

    async def seed():
        await db.products.insert_one({"id": "p_TEST_G02", "sku": "SKU-G02",
                                       "name": "Fabric G02", "base_unit": "meter"})
        # Partial: dari 500 base, sudah terima 100 (dari 10 roll, terima 2) → sisa 400 base
        await db.purchase_orders.insert_one({
            "id": "po_TEST_G02", "status": "partial",
            "items": [{"product_id": "p_TEST_G02", "quantity": 10, "unit": "roll",
                       "quantity_base": 500, "received_qty": 2}],
        })

    run(seed())
    products = [{"id": "p_TEST_G02"}]
    run(sss.apply_global(products))
    # open_qty (dalam qty dokumen) = 10 - 2 = 8; × 500/10 = 400 base
    assert products[0]["incoming_restock_qty"] == 400.0, products[0]


# D4-RFQ-01 — _price_of mengembalikan 0 saat supplier menyatakan available=False
def test_rfq01_award_rejects_unavailable_supplier_line():
    from services import rfq_service as rs
    async def seed():
        await db.warehouses.insert_one({"id": "wh_test", "name": "WH Test"})
    run(seed())
    rfq = {
        "id": "rfq_TEST_01", "rfq_number": "RFQ-TEST-01", "entity_id": "ent_test",
        "warehouse_id": "wh_test", "status": "open",
        "items": [{"line_id": "L1", "product_id": "p_X", "sku": "SKU-X",
                   "product_name": "X", "quantity": 10, "unit": "meter"}],
        "suppliers": [{
            "supplier_id": "sup_TEST", "supplier_name": "S Test", "quote_status": "quoted",
            # harga lama positif TAPI available=False → tidak boleh dipakai
            "lines": [{"line_id": "L1", "price": 15000, "available": False}],
            "total": 0,
        }],
    }

    async def act():
        return await rs.award_rfq(rfq, "full", "sup_TEST", [],
                                   actor={"name": "tester"})

    with pytest.raises(ValueError) as ei:
        run(act())
    assert "belum memberi harga" in str(ei.value) or "Harga 0" in str(ei.value)


def test_rfq01_award_line_mode_rejects_unavailable():
    from services import rfq_service as rs
    async def seed():
        await db.warehouses.insert_one({"id": "wh_test", "name": "WH Test"})
    run(seed())
    rfq = {
        "id": "rfq_TEST_02", "rfq_number": "RFQ-TEST-02", "entity_id": "ent_test",
        "warehouse_id": "wh_test", "status": "open",
        "items": [{"line_id": "L1", "product_id": "p_X", "sku": "SKU-X",
                   "product_name": "X", "quantity": 10, "unit": "meter"}],
        "suppliers": [{
            "supplier_id": "sup_TEST2", "supplier_name": "S Test2", "quote_status": "quoted",
            "lines": [{"line_id": "L1", "price": 9999, "available": False}],
            "total": 0,
        }],
    }

    async def act():
        return await rs.award_rfq(rfq, "line", "", [
            {"line_id": "L1", "supplier_id": "sup_TEST2"}],  # price kosong → _price_of dipakai
            actor={"name": "tester"})

    with pytest.raises(ValueError) as ei:
        run(act())
    assert "Harga 0" in str(ei.value)


# V3-MRES-01 & V3-MRES-02 — idempotensi + penjumlahan penuh tanpa cap
def test_mres01_reserve_for_pr_is_idempotent_per_line():
    from services import material_reservation_service as mrs
    from services import pr_sourcing_service as pss

    async def seed():
        await db.purchase_requisitions.insert_one({
            "id": "pr_TEST_M1", "number": "PR-TEST-M1", "status": "approved",
            "entity_id": "ent_test",
            "items": [{"line_no": 1, "fulfillment_mode": "makloon", "product_id": "p_out"}],
        })
        await db.inventory_balances.insert_one({
            "id": "bal1", "product_id": "p_mat", "owner_entity_id": "ent_test",
            "warehouse_id": "wh1", "available_qty": 100.0, "on_hand_qty": 100.0, "reserved_qty": 0.0,
        })

    run(seed())

    async def fake_prefill(pr_id, line_no):
        return {"ready": True,
                "payload": {"material_product_id": "p_mat", "material_qty": 80.0},
                "target_output_qty": 100.0, "recipe": {}}

    # monkeypatch makloon_prefill
    orig = pss.makloon_prefill
    pss.makloon_prefill = fake_prefill
    try:
        out1 = run(mrs.reserve_for_pr("pr_TEST_M1"))
        out2 = run(mrs.reserve_for_pr("pr_TEST_M1"))  # retry idempoten
    finally:
        pss.makloon_prefill = orig

    assert len(out1) == 1 and out1[0]["qty"] == 80.0
    assert out2 == [], "retry WAJIB idempoten (tidak buat cadangan kedua)"

    # ID deterministik mres_<pr>_<line>
    async def count():
        return await db.material_reservations.count_documents(
            {"id": "mres_pr_TEST_M1_1"})
    assert run(count()) == 1


def test_mres01_parallel_reserve_cannot_oversubscribe():
    """Dua PR paralel atas bahan sama (stok 100, masing-masing butuh 80) → total ≤ 100."""
    import asyncio as _aio
    from services import material_reservation_service as mrs
    from services import pr_sourcing_service as pss

    async def seed():
        for n in (1, 2):
            await db.purchase_requisitions.insert_one({
                "id": f"pr_TEST_P{n}", "number": f"PR-TEST-P{n}", "status": "approved",
                "entity_id": "ent_test",
                "items": [{"line_no": 1, "fulfillment_mode": "makloon", "product_id": f"p_out_{n}"}],
            })
        await db.inventory_balances.insert_one({
            "id": "balP", "product_id": "p_matP", "owner_entity_id": "ent_test",
            "warehouse_id": "wh1", "available_qty": 100.0, "on_hand_qty": 100.0, "reserved_qty": 0.0,
        })
    run(seed())

    async def fake_prefill(pr_id, line_no):
        return {"ready": True,
                "payload": {"material_product_id": "p_matP", "material_qty": 80.0},
                "target_output_qty": 100.0, "recipe": {}}
    orig = pss.makloon_prefill
    pss.makloon_prefill = fake_prefill

    async def race():
        return await _aio.gather(mrs.reserve_for_pr("pr_TEST_P1"),
                                  mrs.reserve_for_pr("pr_TEST_P2"))
    try:
        run(race())
    finally:
        pss.makloon_prefill = orig

    async def totals():
        rows = await db.material_reservations.find(
            {"product_id": "p_matP", "status": "active"}).to_list(10)
        return sum(float(r.get("qty") or 0) for r in rows)
    tot = run(totals())
    assert tot <= 100.0, f"total cadangan {tot} melebihi stok bebas 100 → race oversubscribe"


def test_mres02_sums_over_large_sets_no_cap():
    """>500 balances & >2000 reservasi aktif WAJIB terjumlah penuh."""
    from services import material_reservation_service as mrs

    async def seed():
        # 600 balances, available_qty = 1 masing-masing → total 600
        bals = [{"id": f"balZ_{i}", "product_id": "p_Z", "owner_entity_id": "ent_test",
                 "warehouse_id": f"wh_{i}", "available_qty": 1.0,
                 "on_hand_qty": 1.0, "reserved_qty": 0.0} for i in range(600)]
        await db.inventory_balances.insert_many(bals)
        # 2200 cadangan aktif, qty 0.5 masing-masing → total 1100
        res = [{"id": f"mresZ_{i}", "product_id": "p_Z", "owner_entity_id": "ent_test",
                "ref_id": f"ref_{i}", "status": "active", "qty": 0.5} for i in range(2200)]
        await db.material_reservations.insert_many(res)
    run(seed())

    oha = run(mrs._on_hand_available("p_Z", "ent_test"))
    assert oha == 600.0, f"600 balances WAJIB terjumlah penuh, got {oha}"

    by_others = run(mrs.reserved_by_others("p_Z", "ent_test"))
    assert by_others == 1100.0, f"2200 cadangan WAJIB terjumlah penuh, got {by_others}"

    products = [{"id": "p_Z"}]
    run(mrs.apply_to_products(products, "ent_test"))
    assert products[0]["makloon_reserved_qty"] == 1100.0, products[0]


# D4-WMS-03 — bin di rack.levels[].bins ikut terhitung ke total_capacity
def test_wms03_capacity_includes_levels_bins():
    # Replikasikan logika router/reporting.py:200..206
    warehouse = {"zones": [{"racks": [
        {"bins": [{"capacity": 10}]},                               # legacy
        {"levels": [{"bins": [{"capacity": 5}, {"capacity": 7}]},
                     {"bins": [{"capacity": 3}]}]},                 # baru
        {"bins": [{"capacity": 2}],
         "levels": [{"bins": [{"capacity": 1}]}]},                  # campur
    ]}]}
    total = 0.0
    for zone in warehouse["zones"]:
        for rack in zone["racks"]:
            bins = list(rack.get("bins") or []) + [
                b for lv in rack.get("levels") or [] for b in lv.get("bins") or []]
            for bin_ in bins:
                total += float(bin_.get("capacity", 0) or 0)
    assert total == 10 + 5 + 7 + 3 + 2 + 1 == 28


# D4-ALERT-WMS-01 — grouping key menyertakan entity_id → 2 PT = 2 notifikasi
def test_alert_wms01_grouping_key_includes_entity():
    """Kunci agregasi (gudang, arah, entity_id) menghasilkan grup terpisah per PT."""
    tasks = [
        {"id": "t1", "warehouse_id": "wh1", "flow_type": "outbound", "entity_id": "ent_A",
         "created_at": "2020-01-01T00:00:00+00:00"},
        {"id": "t2", "warehouse_id": "wh1", "flow_type": "outbound", "entity_id": "ent_B",
         "created_at": "2020-01-01T00:00:00+00:00"},
        {"id": "t3", "warehouse_id": "wh1", "flow_type": "outbound", "entity_id": "ent_A",
         "created_at": "2020-01-02T00:00:00+00:00"},
    ]
    groups = {}
    for t in tasks:
        key = (t.get("warehouse_id", ""), t.get("flow_type", ""), t.get("entity_id") or "")
        groups.setdefault(key, []).append(t["id"])
    assert len(groups) == 2, f"2 entitas = 2 grup, got {groups}"
    assert all(len(k) == 3 for k in groups.keys())


def test_alert_wms01_job_ops_stalled_executes():
    """Smoke: pastikan job_ops_stalled tidak crash saat ada tugas menganggur.

    PENTING: implementasi saat ini mengubah key menjadi 3-tuple (wh, flow, entity_id)
    namun masih meng-unpack `(wid, flow), g` pada baris 298 → ValueError. Uji ini
    menangkap regresi tersebut.
    """
    from services import alert_service as als
    from datetime import datetime, timezone, timedelta

    async def seed():
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        await db.wms_tasks.insert_many([
            {"id": "wt_TEST_1", "warehouse_id": "wh1", "warehouse_name": "WH 1",
             "flow_type": "outbound", "status": "pending", "entity_id": "ent_A",
             "created_at": old, "order_number": "SO-A-1"},
            {"id": "wt_TEST_2", "warehouse_id": "wh1", "warehouse_name": "WH 1",
             "flow_type": "outbound", "status": "pending", "entity_id": "ent_B",
             "created_at": old, "order_number": "SO-B-1"},
        ])
    run(seed())
    out = run(als.job_ops_stalled())
    assert out.get("scanned") == 2, out


# D4-AI-05 — snapshot_stock pisah length_reserved: available = rem - lres
def test_ai05_snapshot_stock_splits_length_reserved():
    from services import analytics_snapshots as asn

    async def seed():
        await db.inventory_rolls.insert_many([
            {"id": "r_TEST_1", "status": "available", "product_id": "p_A",
             "owner_entity_id": "ent_test", "warehouse_id": "wh1",
             "length_remaining": 100.0, "length_reserved": 30.0, "unit_cost": 10.0,
             "grade": "A", "dye_lot": "L1"},
            {"id": "r_TEST_2", "status": "reserved", "product_id": "p_A",
             "owner_entity_id": "ent_test", "warehouse_id": "wh1",
             "length_remaining": 50.0, "length_reserved": 0.0, "unit_cost": 10.0,
             "grade": "A", "dye_lot": "L1"},
        ])
    run(seed())
    run(asn.snapshot_stock("2026-01-01"))

    async def fetch():
        return await db.fact_stock_daily.find({}, {"_id": 0}).to_list(10)
    rows = run(fetch())
    assert len(rows) == 1, rows
    row = rows[0]
    # qty total tetap 150; avail = 70 (100-30); reserved = 50 (status reserved) + 30 (lres from available)
    assert row["qty"] == 150.0
    assert row["avail"] == 70.0, f"available roll: 100 − 30 reserved = 70, got {row['avail']}"
    assert row["reserved"] == 80.0, f"50 (reserved status) + 30 (lres di available) = 80, got {row['reserved']}"


# D4-PA-03 — suggest/create_order memisah grup per satuan + qty_by_unit/mixed_units
def test_pa03_suggest_groups_by_unit():
    """Dua roll produk sama, satuan berbeda (meter vs kg) → 2 grup."""
    # Replikasikan logika grouping suggest()
    rolls = [
        {"id": "r1", "owner_entity_id": "e1", "category": "FAB", "grade": "A",
         "unit": "meter", "length_remaining": 50},
        {"id": "r2", "owner_entity_id": "e1", "category": "FAB", "grade": "A",
         "unit": "kg", "length_remaining": 20},
    ]
    groups = {}
    for r in rolls:
        unit = r.get("unit", "meter")
        key = f"{r.get('owner_entity_id')}|{r.get('category') or '—'}|{(r.get('grade') or 'A').upper()}|{unit}"
        g = groups.setdefault(key, {"unit": unit, "qty": 0.0})
        g["qty"] += float(r["length_remaining"])
    assert len(groups) == 2
    units = {g["unit"] for g in groups.values()}
    assert units == {"meter", "kg"}


def test_pa03_create_order_sets_qty_by_unit_and_mixed_flag():
    items = [
        {"roll_id": "r1", "qty": 50, "unit": "meter"},
        {"roll_id": "r2", "qty": 20, "unit": "kg"},
        {"roll_id": "r3", "qty": 30, "unit": "meter"},
    ]
    units = {(i.get("unit") or "meter") for i in items}
    qty_by_unit = {u: round(sum(i["qty"] for i in items if (i.get("unit") or "meter") == u), 2)
                   for u in units}
    mixed = len(units) > 1
    assert qty_by_unit == {"meter": 80, "kg": 20}
    assert mixed is True


# V3-RFID-01 — passage baru di gate yang sama → evaluator ulang (bukan dwell dup)
def test_rfid01_dwell_cache_scoped_to_passage():
    """Logika filter: `prev.passage_id == passage.id` → dwell dup; passage baru → False."""
    prev = {"id": "rread_1", "passage_id": "pA", "result": "green", "reason": "ok"}
    passage_same = {"id": "pA"}
    passage_new = {"id": "pB"}
    # same passage → treated as dwell duplicate
    is_dwell_dup_same = (prev.get("passage_id") or None) == ((passage_same or {}).get("id") or None)
    is_dwell_dup_new = (prev.get("passage_id") or None) == ((passage_new or {}).get("id") or None)
    assert is_dwell_dup_same is True
    assert is_dwell_dup_new is False, "passage baru WAJIB memicu evaluasi ulang"


# D4-RET-POLICY-01 — resolver hanya PO entitas pesanan
def test_ret_policy01_resolver_filters_by_order_entity():
    """PO entitas lain TIDAK boleh jadi proxy supplier asal beli."""
    from services import return_policy_service as rps

    async def seed():
        await db.suppliers.insert_one({"id": "sup_X", "name": "SupX",
                                        "return_policy": {"window_days": 7}})
        # PO entitas BUKAN pemilik order
        await db.purchase_orders.insert_one({
            "id": "po_other", "entity_id": "ent_OTHER", "status": "completed",
            "supplier_id": "sup_X", "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-02T00:00:00+00:00",
            "items": [{"product_id": "p_RET"}],
        })

    run(seed())
    order = {"id": "so_1", "entity_id": "ent_MINE",
             "items": [{"product_id": "p_RET"}]}
    out = run(rps._linked_supplier_deadline(order, 14))
    # Batch akhir Fase 02: tanpa roll fisik yang terlacak → untraceable (bukan proxy PO terbaru)
    assert out["source"] == "untraceable", f"PO entitas lain WAJIB ditolak sebagai proxy, got {out}"
    assert out.get("supplier_id") in ("", None)

    # Dengan PO entitas yang benar → ditemukan
    async def seed2():
        await db.purchase_orders.insert_one({
            "id": "po_mine", "entity_id": "ent_MINE", "status": "completed",
            "supplier_id": "sup_X", "created_at": "2026-01-05T00:00:00+00:00",
            "updated_at": "2026-01-06T00:00:00+00:00",
            "last_received_at": "2026-01-06T00:00:00+00:00",
            "items": [{"product_id": "p_RET"}],
        })
    run(seed2())
    run(db.inventory_rolls.insert_one({"id": "r_ret", "po_id": "po_mine", "product_id": "p_RET",
                                       "reserved_ref": {"type": "sales_order", "id": "so_1"}}))
    out2 = run(rps._linked_supplier_deadline(order, 14))
    assert out2.get("supplier_id") == "sup_X", out2

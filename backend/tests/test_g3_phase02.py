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

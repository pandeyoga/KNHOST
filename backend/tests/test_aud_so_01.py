"""AUD-SO-01 (review 2026-10-19) — proses lama tidak boleh melepas kunci realisasi milik proses baru.

Skenario reviewer pada MongoDB aktual: claim A → lease A dibuat kedaluwarsa → claim B → release A (terlambat).
Kini kunci membawa token: release/renew A tidak menyentuh kunci B; renew A gagal (proses A berhenti sebelum
membuat dokumen). Uji tingkat layanan (klien Motor baru per loop — pola tes layanan di repo ini).
Jalankan: cd /app/backend && python -m pytest tests/test_aud_so_01.py -p no:randomly -n 0 -q
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, "/app/backend")


def _run(coro_fn):
    async def main():
        from motor.motor_asyncio import AsyncIOMotorClient
        from services import special_order_fulfillment as ful
        db = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
        old, ful.db = ful.db, db
        try:
            return await coro_fn(ful, db)
        finally:
            ful.db = old
    return asyncio.run(main())


def test_release_terlambat_tidak_menghapus_kunci_pemilik_baru():
    async def scenario(ful, db):
        od_id = f"sord_TEST_SO01_{uuid.uuid4().hex[:6]}"
        await db.special_orders.insert_one({"id": od_id})
        try:
            ta = await ful._claim(od_id, "k1", "A")
            await db.special_orders.update_one({"id": od_id}, {"$set": {"fulfillment_locks.k1.at": "2000-01-01T00:00:00"}})
            tb = await ful._claim(od_id, "k1", "B")                 # B mengambil alih kunci kedaluwarsa
            assert ta != tb
            await ful._release(od_id, "k1", ta)                      # A selesai terlambat
            lock = (await db.special_orders.find_one({"id": od_id}))["fulfillment_locks"]["k1"]
            assert lock["token"] == tb and lock["by"] == "B"
            with pytest.raises(ful.FulfillmentConflict):
                await ful._renew(od_id, "k1", ta)                    # A tidak boleh lanjut membuat dokumen
            with pytest.raises(ful.FulfillmentConflict):
                await ful._claim(od_id, "k1", "C")                   # kunci B masih berlaku
            await ful._renew(od_id, "k1", tb)
            await ful._release(od_id, "k1", tb)
            assert "k1" not in ((await db.special_orders.find_one({"id": od_id})).get("fulfillment_locks") or {})
        finally:
            await db.special_orders.delete_one({"id": od_id})
    _run(scenario)

"""CR-T3 U17 — di MongoDB ASLI (lingkungan A): dua pemakaian bersamaan atas SATU izin kredit lingkup pelanggan Rp 3.000.000.

Fungsi layanan dijalankan langsung (proses uji di container backend; `MONGO_URL`/`DB_NAME` = database uji lokal, BUKAN
data nyata). Fixture disisipkan langsung: izin `approved` lingkup pelanggan Rp 3.000.000 tanpa masa berlaku.

  U17  `use_override(izin, SO-A, 3 jt)` ∥ `use_override(izin, SO-B, 3 jt)` × 5 putaran → tepat satu True, satu False;
       `remaining_amount` 0 (tidak negatif); `used_by` satu baris. Padanan alur HTTP (dua `POST /api/sales-orders`
       bersamaan) memakai fungsi yang sama SEBELUM reservasi (`routers/sales_orders.create_order`): yang kalah 409
       `CREDIT_BLOCKED` dan izinnya tidak terpakai.
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
KANDA = "ent_kanda"


@pytest.mark.skipif(not os.environ.get("MONGO_URL"), reason="butuh MongoDB asli (lingkungan A)")
def test_CRT3_U17_dua_pesanan_bersamaan_satu_izin():
    async def _jalan():
        from db import db
        from services import credit_gate as cg
        ids = []
        try:
            for putaran in range(5):
                oid = f"cro_bpcrt3_{uuid.uuid4().hex[:8]}"
                ids.append(oid)
                await db.credit_overrides.insert_one({
                    "id": oid, "customer_id": f"cus_bpcrt3_{putaran}", "entity_id": KANDA, "status": "approved",
                    "scope": "pelanggan", "amount": 3_000_000.0, "remaining_amount": 3_000_000.0, "valid_until": "",
                    "used_by": [], "requested_by": "uji lapis A", "created_at": "2026-11-15T03:00:00+00:00"})
                hasil = await asyncio.gather(cg.use_override(oid, f"so_a_{putaran}", 3_000_000.0),
                                             cg.use_override(oid, f"so_b_{putaran}", 3_000_000.0))
                assert sorted(hasil) == [False, True], (putaran, hasil)
                d = await db.credit_overrides.find_one({"id": oid}, {"_id": 0})
                assert d["remaining_amount"] == 0 and len(d["used_by"]) == 1, d
        finally:
            await db.credit_overrides.delete_many({"id": {"$in": ids}})
    asyncio.run(_jalan())

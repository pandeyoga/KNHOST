"""CR-T2 U17 — di MongoDB ASLI (lingkungan A): dua kait surat jalan bersamaan pada pesanan F1 berdua nomor.

Fungsi layanan dijalankan langsung (proses uji di container backend; `MONGO_URL`/`DB_NAME` = database uji lokal, BUKAN
data nyata). Fixture disisipkan langsung: pelanggan, pesanan S1 Rp 1.000.000 NET30 `ent_kanda`, dua surat jalan
SJ-A (40 yard, 1 Sep 2026, Dr piutang 400.000) dan SJ-B (60 yard, 10 Sep 2026, Dr piutang 600.000) + jurnalnya.

  U17  `on_shipment_posted(S1, SJ-A)` ∥ `on_shipment_posted(S1, SJ-B)` → tepat SATU jadwal hidup (indeks unik
       `payment_plans.uq_plan_live_doc` menolak jadwal kedua), dua baris tanpa kembar: SJ-A 400.000 jatuh tempo
       2026-10-01, SJ-B 600.000 jatuh tempo 2026-10-10; Σ 1.000.000.
  U17b sisip jadwal hidup kedua langsung → DuplicateKeyError (indeks terpasang); dua saldo tersimpan pasangan yang
       sama → DuplicateKeyError (`customer_balances.uq_customer_entity`).
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

import pytest
from pymongo.errors import DuplicateKeyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
KANDA = "ent_kanda"


def _id(awal: str) -> str:
    return f"{awal}_bpcrt2_{uuid.uuid4().hex[:8]}"


async def _fixture(db):
    from services import gl_service as gl
    cid = _id("cus")
    await db.customers.insert_one({"id": cid, "name": f"Toko BP CR-T2 {cid[-4:]}", "entity_id": KANDA,
                                   "status": "active", "payment_profile": {}, "deposit_balance": 0.0})
    so = {"id": _id("so"), "number": f"SO-BPCRT2-{uuid.uuid4().hex[:5]}", "entity_id": KANDA, "customer_id": cid,
          "customer_name": "Toko BP CR-T2", "status": "shipped", "grand_total": 1_000_000.0,
          "total_amount": 1_000_000.0, "payments": [], "paid_total": 0.0, "payment_status": "unpaid",
          "payment_term_code": "NET30", "payment_term_days": 30, "items": [],
          "created_at": "2026-08-25T03:00:00+00:00", "confirmed_at": "2026-08-25T03:00:00+00:00"}
    await db.sales_orders.insert_one(dict(so))
    for nomor, nilai, tgl in (("SJ-A", 400_000.0, "2026-09-01"), ("SJ-B", 600_000.0, "2026-09-10")):
        shid = _id("shp")
        no = f"{nomor}-{so['id'][-6:]}"
        await db.shipments.insert_one({"id": shid, "shipment_no": no, "order_id": so["id"], "entity_id": KANDA,
                                       "status": "dispatched", "created_at": f"{tgl}T03:00:00+00:00"})
        await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": nilai, "credit": 0.0},
                                      {"account_code": "4-1000", "debit": 0.0, "credit": nilai}],
                               description=f"uji lapis A CR-T2 {no}", date=f"{tgl}T03:00:00+00:00",
                               source_type="shipment_revenue", source_id=shid, entity_id=KANDA, created_by="uji",
                               source_label=no, ref={"order_id": so["id"], "order_number": so["number"]})
    return cid, so


@pytest.mark.skipif(not os.environ.get("MONGO_URL"), reason="butuh MongoDB asli (lingkungan A)")
def test_CRT2_U17_dua_kait_bersamaan_satu_jadwal():
    async def _jalan():
        from db import db
        from indexes import ensure_required_indexes
        from services import billing_schedule_service as bss
        assert not [f for f in await ensure_required_indexes()
                    if f["name"] in ("uq_plan_live_doc", "uq_customer_entity")], "indeks wajib CR-T2 belum terpasang"
        cid, so = await _fixture(db)
        a, b = f"SJ-A-{so['id'][-6:]}", f"SJ-B-{so['id'][-6:]}"
        for _ in range(3):   # tiga putaran balapan pada jadwal yang sama — idempoten
            await asyncio.gather(bss.on_shipment_posted(so["id"], a), bss.on_shipment_posted(so["id"], b))
        hidup = await db.payment_plans.find({"doc_id": so["id"], "status": {"$ne": "void"}}, {"_id": 0}).to_list(5)
        assert len(hidup) == 1, hidup
        lines = sorted(hidup[0]["lines"], key=lambda x: x["source_id"])
        assert [(x["source_id"], x["amount"], x["due_date"]) for x in lines] == \
            [(a, 400_000, "2026-10-01"), (b, 600_000, "2026-10-10")]
        assert len({x["line_id"] for x in lines}) == 2 and len({x["seq"] for x in lines}) == 2
        with pytest.raises(DuplicateKeyError):
            await db.payment_plans.insert_one({**hidup[0], "id": _id("pyp")})
        with pytest.raises(DuplicateKeyError):
            await db.customer_balances.insert_one({"id": _id("cbl"), "customer_id": cid, "entity_id": KANDA})
    asyncio.run(_jalan())

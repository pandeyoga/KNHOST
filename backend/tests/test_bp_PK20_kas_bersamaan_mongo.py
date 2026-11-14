"""PK-20 U12 — di MongoDB ASLI (lingkungan A): dua `create_cash` BERSAMAAN dengan rujukan sama → 1 kas, 1 jurnal.

Memanggil layanan langsung di proses uji (motor ke `MONGO_URL`/`DB_NAME` database uji lokal; tidak untuk database
berisi data nyata). Rekening fixture `rek_bp20_<acak>` (Kas Kecil, satu-satunya untuk PT uji acak) disisipkan langsung.
Harapan: id kas tetap dari rujukan + upsert `$setOnInsert` + indeks unik `uq_id` (`indexes.ID_INDEX_COLLECTIONS`) →
tepat satu dokumen; jurnal kedua dicegah `_already_posted` + indeks unik `source_type`+`source_id` (PK-14 W1).
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_U12_dua_create_cash_bersamaan_satu_kas_satu_jurnal():
    from db import db
    from services import cash_ledger, gl_service

    async def jalan():
        await gl_service.seed_default_coa()
        from indexes import ensure_id_index
        await ensure_id_index("cash_transactions")
        for _ in range(3):   # beberapa putaran: balapan tidak selalu muncul di satu percobaan
            ent = f"ent_bp20_{uuid.uuid4().hex[:6]}"
            # Nama pendek unik per putaran: nomor kas berawalan nama PT dan `uq_number` global — nama sama di dua PT uji
            # membuat nomor bertabrakan (bukan balapan yang diuji di sini).
            await db.business_entities.insert_one({"id": ent, "short_name": f"PT Uji {ent}", "status": "active"})
            await db.bank_accounts.insert_one({"id": f"rek_{ent}", "name": "Kas Kecil Uji", "entity_id": ent,
                                               "account_type": "cash", "cash_type": "kas_kecil", "is_active": True,
                                               "opening_balance": 0})
            ref = f"bp20_{uuid.uuid4().hex[:8]}"
            kw = dict(entity_id=ent, direction="out", amount=250_000, cash_type="kas_kecil", category="sewa",
                      ref_type="manual", ref_id=ref, actor="uji BP20")
            hasil = await asyncio.gather(cash_ledger.create_cash(**kw), cash_ledger.create_cash(**kw),
                                         return_exceptions=True)
            ok = [h for h in hasil if isinstance(h, dict)]
            assert ok, hasil
            assert len({h["id"] for h in ok}) == 1, hasil
            n_kas = await db.cash_transactions.count_documents({"ref_type": "manual", "ref_id": ref})
            n_je = await db.journal_entries.count_documents({"source_type": "cash_transaction",
                                                             "source_id": ok[0]["id"], "status": {"$ne": "void"}})
            assert (n_kas, n_je) == (1, 1), (hasil, n_kas, n_je)
    asyncio.run(jalan())

"""PK-24 U13 — di MongoDB ASLI (lingkungan A): dua `return-remainder` BERSAMAAN atas LPJ bersisa `open` → satu
berhasil, satu 409; tepat 1 kas masuk dan 1 jurnal.

Memanggil layanan langsung di proses uji (motor ke `MONGO_URL`/`DB_NAME` database uji lokal; tidak untuk database
berisi data nyata). FIXTURE disisipkan langsung: PT uji acak `ent_bp24_<acak>` + rekening Kas Kecil satu-satunya, PD
`settled` dan LPJ `posted_to_gl` dengan `sisa_dikembalikan = {amount: 200000, status: "open"}`. Harapan: klaim
bersyarat `sisa_dikembalikan.status: open → returning` (find_one_and_update) membiarkan hanya SATU pemanggil lewat;
id kas tetap dari rujukan (`cash_advance_return`, id LPJ) + indeks unik `uq_id` menjaga kas tunggal.
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_U13_dua_pengembalian_bersamaan_satu_kas_satu_jurnal():
    from fastapi import HTTPException

    from core_utils import now_iso
    from db import db
    from entity_scope import EntityContext
    from schemas_cash_advance import ReturnRemainderIn
    from services import cash_advance_service as svc
    from services import gl_service

    async def jalan():
        await gl_service.seed_default_coa()
        from indexes import ensure_id_index
        await ensure_id_index("cash_transactions")
        for _ in range(3):   # beberapa putaran: balapan tidak selalu muncul di satu percobaan
            ent = f"ent_bp24_{uuid.uuid4().hex[:6]}"
            stl = f"stl_bp24_{uuid.uuid4().hex[:8]}"
            ca = f"ca_bp24_{uuid.uuid4().hex[:8]}"
            await db.business_entities.insert_one({"id": ent, "short_name": "PT Uji BP24", "status": "active"})
            await db.bank_accounts.insert_one({"id": f"rek_{ent}", "name": "Kas Kecil Uji", "entity_id": ent,
                                               "account_type": "cash", "cash_type": "kas_kecil", "is_active": True,
                                               "opening_balance": 0})
            await db.cash_advances.insert_one({"id": ca, "number": f"PD-{ca[-6:]}", "entity_id": ent,
                                               "status": "settled", "total_amount": 1_000_000, "created_at": now_iso()})
            await db.cash_advance_settlements.insert_one({
                "id": stl, "number": f"STL-{stl[-6:]}", "entity_id": ent, "cash_advance_id": ca,
                "status": "posted_to_gl", "total_pengeluaran": 800_000, "total_pettycash": 1_000_000,
                "sisa_kurang_dana": 200_000, "dibuat_oleh": "Staf Uji", "created_at": now_iso(),
                "sisa_dikembalikan": {"amount": 200_000, "status": "open", "cash_txn_id": "", "cash_txn_number": "",
                                      "journal_entry_number": "", "returned_at": "", "returned_by": ""}})
            aktor = {"id": "usr_bp24", "name": "Uji BP24", "role": "admin"}
            ctx = EntityContext(user=aktor, active_entity_id=ent, allowed_entity_ids=[ent])
            body = ReturnRemainderIn(cash_type="kas_kecil")
            hasil = await asyncio.gather(svc.return_remainder(stl, body, ctx, aktor),
                                         svc.return_remainder(stl, body, ctx, aktor), return_exceptions=True)
            ok = [h for h in hasil if isinstance(h, dict)]
            tolak = [h for h in hasil if isinstance(h, HTTPException)]
            assert (len(ok), len(tolak)) == (1, 1), hasil
            assert tolak[0].status_code == 409, tolak[0].detail
            n_kas = await db.cash_transactions.count_documents({"ref_type": "cash_advance_return", "ref_id": stl})
            kas = await db.cash_transactions.find_one({"ref_type": "cash_advance_return", "ref_id": stl}, {"_id": 0})
            n_je = await db.journal_entries.count_documents({"source_type": "cash_transaction", "source_id": kas["id"],
                                                             "status": {"$ne": "void"}})
            assert (n_kas, n_je) == (1, 1), (hasil, n_kas, n_je)
            assert ok[0]["sisa_dikembalikan"]["status"] == "returned"
            # bersihkan fixture
            await db.journal_entries.delete_many({"source_type": "cash_transaction", "source_id": kas["id"]})
            await db.cash_transactions.delete_many({"ref_type": "cash_advance_return", "ref_id": stl})
            await db.cash_advance_settlements.delete_one({"id": stl})
            await db.cash_advances.delete_one({"id": ca})
            await db.bank_accounts.delete_one({"id": f"rek_{ent}"})
            await db.business_entities.delete_one({"id": ent})
    asyncio.run(jalan())

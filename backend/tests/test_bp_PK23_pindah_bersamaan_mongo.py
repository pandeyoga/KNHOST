"""PK-23 U14 — di MongoDB ASLI (lingkungan A): dua permintaan PINDAH ASET bersamaan atas aset yang sama → satu
berhasil, satu 409 ("sedang diproses", atau "sudah dipindahkan" bila tiba sesudah pemenang selesai); tepat satu aset
pengganti di PT penerima dan satu jurnal per sisi.

Memanggil layanan langsung di proses uji (motor ke `MONGO_URL`/`DB_NAME` database uji lokal; tidak untuk database
berisi data nyata). Dua PT uji acak (`ent_bp23a_<acak>`, `ent_bp23b_<acak>`) dan aset fixture ber-jurnal perolehan
disisipkan langsung. Harapan: klaim bersyarat status (`active` → `transferring`, `find_one_and_update`) hanya
dimenangkan satu permintaan; aset pengganti ber-id turunan `{id}_tr` (sisip bersyarat) dan jurnal tiap sisi dijaga
indeks unik `source_type`+`source_id` (PK-14 W1).
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_U14_dua_pindah_bersamaan_satu_aset_pengganti_satu_jurnal_per_sisi():
    from db import db
    from core_utils import now_iso
    from services import gl_service
    from services import fixed_asset_transfer_service as tsvc
    from services.fixed_asset_service import AssetError

    async def jalan():
        await gl_service.seed_default_coa()
        for _ in range(3):   # beberapa putaran: balapan tidak selalu muncul di satu percobaan
            a_ent, b_ent = f"ent_bp23a_{uuid.uuid4().hex[:6]}", f"ent_bp23b_{uuid.uuid4().hex[:6]}"
            for e, nama in ((a_ent, "PT Uji BP23 A"), (b_ent, "PT Uji BP23 B")):
                await db.business_entities.insert_one({"id": e, "short_name": nama, "legal_name": nama,
                                                       "status": "active", "code": e[-6:].upper()})
            aid = f"fa_bp23_{uuid.uuid4().hex[:8]}"
            await db.fin_fixed_assets.insert_one({
                "id": aid, "number": f"FA-BP23-{aid[-4:]}", "name": "Mesin uji BP23", "category": "Peralatan & Mesin",
                "acquisition_cost": 12_000_000.0, "acquisition_date": "2026-09-01", "useful_life_months": 48,
                "salvage_value": 0.0, "entity_id": a_ent, "gl_account_asset": "1-2100",
                "gl_account_dep_exp": "6-6000", "gl_account_acc_dep": "1-2900", "funding_source": "hutang",
                "funding_account": "2-1100", "monthly_depreciation": 250_000.0, "accumulated_depreciation": 0.0,
                "book_value": 12_000_000.0, "depreciated_months": 0, "status": "active", "gl_status": "posted",
                "created_at": now_iso(), "updated_at": now_iso()})
            isi = {"to_entity_id": b_ent, "reason": "uji pindah bersamaan BP23"}
            aktor = {"name": "uji BP23"}
            hasil = await asyncio.gather(tsvc.transfer_to_entity(aid, isi, aktor),
                                         tsvc.transfer_to_entity(aid, isi, aktor), return_exceptions=True)
            ok = [h for h in hasil if isinstance(h, dict)]
            kalah = [h for h in hasil if isinstance(h, AssetError)]
            assert len(ok) == 1 and len(kalah) == 1, hasil
            # kalah klaim / jatah kerja niat → "sedang diproses"; tiba sesudah pemenang selesai → "sudah dipindahkan"
            assert kalah[0].status_code == 409 and ("sedang diproses" in str(kalah[0])
                                                    or "sudah dipindahkan" in str(kalah[0])), hasil
            n_baru = await db.fin_fixed_assets.count_documents({"transfer_from.asset_id": aid})
            n_kirim = await db.journal_entries.count_documents({"source_type": "fixed_asset_transfer",
                                                                "source_id": f"{aid}:from", "status": {"$ne": "void"}})
            n_terima = await db.journal_entries.count_documents({"source_type": "fixed_asset_acquisition",
                                                                 "source_id": f"{aid}_tr", "status": {"$ne": "void"}})
            assert (n_baru, n_kirim, n_terima) == (1, 1, 1), (hasil, n_baru, n_kirim, n_terima)
            a = await db.fin_fixed_assets.find_one({"id": aid}, {"_id": 0})
            assert a["status"] == "transferred" and a["transfer"]["intent"]["status"] == "done"
    asyncio.run(jalan())

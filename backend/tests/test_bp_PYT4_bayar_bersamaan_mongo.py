"""PY-T4 U14 — di MongoDB ASLI (lingkungan A): dua Bayar BERSAMAAN atas proses gaji `posted` → satu berhasil, satu
ditolak (`PayrollConflict` = 409 di router "Penggajian … sedang atau sudah dibayar. Muat ulang."), tepat SATU kas keluar
dan SATU jurnal bayar.

Memanggil layanan langsung di proses uji (motor ke `MONGO_URL`/`DB_NAME` database uji lokal; tidak untuk database berisi
data nyata). PT uji acak + rekening berperuntukan Gaji + proses gaji `approved` (dua slip, bersih 9.500.000 =
5.000.000 + 4.500.000) disisipkan langsung, lalu diposting lewat `post_run_gl`. Harapan: klaim bersyarat
`posted → paying` (satu pemenang) + id kas tetap dari id proses (`cash_ledger.cash_id`) + indeks unik `uq_id` kas.
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_U14_dua_bayar_bersamaan_satu_kas_satu_jurnal():
    from db import db
    from services import gl_service
    from services import hr_payroll_pay as bayar
    from services import hr_payroll_service as pay

    async def jalan():
        await gl_service.seed_default_coa()
        for _ in range(3):   # beberapa putaran: balapan tidak selalu muncul di satu percobaan
            ent = f"ent_bpy4_{uuid.uuid4().hex[:6]}"
            await db.business_entities.insert_one({"id": ent, "code": f"Y{ent[-6:].upper()}", "short_name": "PT Uji BPY4",
                                                   "status": "active"})
            rek = f"rek_bpy4_{uuid.uuid4().hex[:6]}"
            await db.bank_accounts.insert_one({
                "id": rek, "name": "Gaji Uji", "entity_id": ent, "account_type": "bank", "cash_type": "kas_besar",
                "bank_name": "BCA", "account_number": "9001", "purposes": ["gaji"], "is_active": True,
                "opening_balance": 0.0, "created_at": "2026-01-01T00:00:00+00:00"})
            rid = f"prun_bpy4_{uuid.uuid4().hex[:8]}"
            slips = [("A", 5_000_000, "BCA", "111"), ("B", 4_500_000, "", "")]
            await db.hr_payroll_runs.insert_one({
                "id": rid, "number": f"PAY-{rid[-6:]}", "entity_id": ent, "period": "2026-10", "status": "approved",
                "commission_mode": "accrue_then_settle", "journal_id": "", "created_at": "2026-11-01T00:00:00+00:00",
                "totals": {"employees": 2, "salary_earnings": 9_500_000, "commission": 0, "gross": 9_500_000,
                           "bpjs_emp": 0, "bpjs_er": 0, "pph21": 0, "net": 9_500_000}})
            await db.hr_payslips.insert_many([
                {"id": f"{rid}_{n}", "number": f"SLIP-{rid[-6:]}-{n}", "run_id": rid, "entity_id": ent,
                 "period": "2026-10", "status": "approved", "employee_id": f"emp_{rid}_{n}", "employee_name": n,
                 "salary_earnings": g, "commission": 0, "gross": g, "bpjs_emp_total": 0, "bpjs_er_total": 0, "pph21": 0,
                 "net": g, "bank": {"bank_name": b, "acc_no": no, "acc_name": n if no else ""}}
                for n, g, b, no in slips])
            aktor = {"id": "usr_bpy4", "name": "Uji BPY4", "role": "admin"}
            run = await pay.post_run_gl(rid, aktor)
            assert run["status"] == "posted", run
            hasil = await asyncio.gather(bayar.pay_run(rid, aktor, account_id=rek),
                                         bayar.pay_run(rid, aktor, account_id=rek), return_exceptions=True)
            ok = [h for h in hasil if isinstance(h, dict)]
            tolak = [h for h in hasil if isinstance(h, pay.PayrollConflict)]
            assert len(ok) == 1 and len(tolak) == 1, hasil
            assert "sedang atau sudah dibayar" in str(tolak[0])
            kas = await db.cash_transactions.find({"ref_type": "payroll_run", "ref_id": rid}, {"_id": 0}).to_list(10)
            assert len(kas) == 1 and kas[0]["amount"] == 9_500_000 and kas[0]["account_id"] == rek, kas
            n_je = await db.journal_entries.count_documents({"source_type": "cash_transaction", "source_id": kas[0]["id"],
                                                             "status": {"$ne": "void"}})
            assert n_je == 1, n_je
            doc = await db.hr_payroll_runs.find_one({"id": rid})
            assert doc["status"] == "paid" and doc["transfer_total"] == 9_500_000 and doc["transfer_count"] == 2
    asyncio.run(jalan())

"""PK-22 U15 — di MongoDB ASLI (lingkungan A): dua anulir (`void`) BERSAMAAN atas proses gaji `posted` → satu berhasil,
satu ditolak (`PayrollConflict` = 409 di router), tepat SATU jurnal pembalik.

Memanggil layanan langsung di proses uji (motor ke `MONGO_URL`/`DB_NAME` database uji lokal; tidak untuk database berisi
data nyata). PT uji acak + proses gaji `approved` (dua slip, bersih 8.490.000) disisipkan langsung, lalu diposting lewat
`post_run_gl`. Harapan: klaim bersyarat `posted → voiding` (satu pemenang) + `_reverse_once` (klaim di jurnal asal) +
indeks unik `source_type`+`source_id` jurnal (PK-14 W1).
"""
import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_U15_dua_anulir_bersamaan_satu_pembalik():
    from db import db
    from services import gl_service
    from services import hr_payroll_service as pay

    async def jalan():
        await gl_service.seed_default_coa()
        for _ in range(3):   # beberapa putaran: balapan tidak selalu muncul di satu percobaan
            ent = f"ent_bp22_{uuid.uuid4().hex[:6]}"
            await db.business_entities.insert_one({"id": ent, "code": "BP22", "short_name": "PT Uji BP22",
                                                   "status": "active"})
            rid = f"prun_bp22_{uuid.uuid4().hex[:8]}"
            slips = [("A", 5_000_000, 200_000, 300_000, 100_000), ("B", 4_000_000, 160_000, 240_000, 50_000)]
            await db.hr_payroll_runs.insert_one({
                "id": rid, "number": f"PAY-{rid[-6:]}", "entity_id": ent, "period": "2026-10", "status": "approved",
                "commission_mode": "accrue_then_settle", "journal_id": "", "created_at": "2026-11-01T00:00:00+00:00",
                "totals": {"employees": 2, "salary_earnings": 9_000_000, "commission": 0, "gross": 9_000_000,
                           "bpjs_emp": 360_000, "bpjs_er": 540_000, "pph21": 150_000, "net": 8_490_000}})
            await db.hr_payslips.insert_many([
                {"id": f"{rid}_{n}", "run_id": rid, "entity_id": ent, "period": "2026-10", "status": "approved",
                 "employee_id": f"emp_{rid}_{n}", "employee_name": n, "salary_earnings": g, "commission": 0,
                 "gross": g, "bpjs_emp_total": e, "bpjs_er_total": r, "pph21": p, "net": g - e - p}
                for n, g, e, r, p in slips])
            aktor = {"id": "usr_bp22", "name": "Uji BP22", "role": "admin"}
            run = await pay.post_run_gl(rid, aktor)
            assert run["status"] == "posted", run
            hasil = await asyncio.gather(pay.void_run(rid, aktor, "anulir bersamaan uji"),
                                         pay.void_run(rid, aktor, "anulir bersamaan uji"), return_exceptions=True)
            ok = [h for h in hasil if isinstance(h, dict)]
            tolak = [h for h in hasil if isinstance(h, pay.PayrollConflict)]
            assert len(ok) == 1 and len(tolak) == 1, hasil
            n_rev = await db.journal_entries.count_documents({"source_type": "payroll_run_reversal", "source_id": rid,
                                                              "status": {"$ne": "void"}})
            assert n_rev == 1, (hasil, n_rev)
            assert (await db.hr_payroll_runs.find_one({"id": rid}))["status"] == "void"
    asyncio.run(jalan())

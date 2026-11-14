"""PY-T1 U2 & U14 — lapis A (MongoDB ASLI, data acuan `scripts/dev_restore_demo.sh`; bukan database berisi data nyata).

U2   Slip data acuan dihitung ulang dengan mesin komponen: untuk tiap slip proses gaji yang hidup, Σ komponen pendapatan =
     `gross` lama, `net` dan PPh 21 sama, selisih 0. Proses `draft` dihitung ulang lewat `recalculate_run` (menulis
     slipnya, seperti tombol Hitung Ulang); proses lain dihitung di memori (`compute_payslip`, tanpa tulisan) supaya
     status dokumen data acuan tidak berubah.
U14  Dua permintaan proses reguler BERSAMAAN untuk PT + periode yang sama → id proses sama, tepat SATU proses reguler hidup
     (indeks unik parsial `hr_payroll_runs.active_key`, PY-T1). Beberapa putaran: balapan tidak selalu muncul sekali coba.

Memanggil layanan langsung di proses uji (motor ke `MONGO_URL`/`DB_NAME` dari `backend/.env` lingkungan A).
"""
import asyncio
import inspect
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KOLOM = ("base_salary", "allowances", "overtime", "commission", "salary_earnings", "gross", "tax_gross",
         "bpjs_emp_total", "bpjs_er_total", "pph21", "net")
AKTOR = {"id": "usr_bp_pyt1", "name": "Uji PY-T1", "role": "admin"}
# Satu event loop untuk seluruh modul: klien Motor (`db`) terikat ke loop pertama yang memakainya, sehingga dua
# `asyncio.run` terpisah membuat uji kedua gagal "Event loop is closed" (integrator, lingkungan A 15 Nov).
_LOOP = asyncio.new_event_loop()


def _jalankan(coro):
    return _LOOP.run_until_complete(coro)


def _beda(lama: dict, baru: dict) -> dict:
    out = {}
    for k in KOLOM:
        if k == "tax_gross" and lama.get(k) is None:
            continue
        a, b = float(lama.get(k) or 0), float(baru.get(k) or 0)
        if abs(a - b) > 0.005:
            out[k] = (a, b)
    pend = round(sum(float(c.get("amount") or 0) for c in baru.get("components") or []
                     if c.get("kind") == "pendapatan"), 2)
    if abs(pend - float(lama.get("gross") or 0)) > 0.005:
        out["Σ komponen pendapatan"] = (float(lama.get("gross") or 0), pend)
    return out


def test_U2_slip_data_acuan_sama_dengan_komponen():
    from db import db
    from services import hr_payroll_service as pay
    from services import hr_service

    async def jalan():
        runs = await db.hr_payroll_runs.find({"status": {"$nin": ["cancelled", "void", "rejected"]}},
                                             {"_id": 0}).to_list(None)
        selisih, diperiksa = [], 0
        for run in runs:
            lama = {s["employee_id"]: s for s in await db.hr_payslips.find({"run_id": run["id"]}, {"_id": 0})
                    .to_list(None)}
            if run["status"] == "draft":
                baru = {s["employee_id"]: s for s in (await pay.recalculate_run(run["id"], AKTOR))["payslips"]}
            else:
                cfg = await hr_service.get_hr_settings(run["entity_id"])
                aturan = await pay.aturan_pph21(pay.akhir_periode_gaji(run["period"]))
                baru = {}
                # Serah-terima (b): slip dihitung sebagai bagian proses itu (jenis proses, masukan terpakai, PPh 21
                # gabungan bulan); serah-terima (a) belum punya argumen `run`.
                extra = {"run": run} if "run" in inspect.signature(pay.compute_payslip).parameters else {}
                for emp_id in lama:
                    emp = await db.hr_employees.find_one({"id": emp_id}, {"_id": 0})
                    if emp:
                        baru[emp_id] = await pay.compute_payslip(emp, run["period"], run["entity_id"], cfg, aturan,
                                                                 **extra)
            for emp_id, s in lama.items():
                if emp_id not in baru:
                    continue
                diperiksa += 1
                d = _beda(s, baru[emp_id])
                if d:
                    selisih.append((run.get("number"), s.get("employee_name"), d))
        print(f"[U2] {len(runs)} proses, {diperiksa} slip diperiksa, {len(selisih)} berselisih")
        assert not selisih, selisih
    _jalankan(jalan())


def test_U14_dua_proses_reguler_bersamaan_satu_proses():
    from db import db
    from services import gl_service
    from services import hr_payroll_service as pay

    async def jalan():
        await gl_service.seed_default_coa()
        for _ in range(3):
            ent = f"ent_bpyt1_{uuid.uuid4().hex[:6]}"
            await db.business_entities.insert_one({"id": ent, "code": f"Y{ent[-6:].upper()}", "short_name": "PT Uji PYT1",
                                                   "status": "active"})
            await db.hr_employees.insert_one({"id": f"emp_{ent}", "name": "Uji PYT1", "entity_id": ent,
                                              "status": "active", "base_salary": 5_000_000, "allowances": [],
                                              "ptkp_status": "TK0", "bpjs_kes_enabled": False,
                                              "bpjs_tk_enabled": False, "created_at": "2026-01-01T00:00:00+00:00"})
            hasil = await asyncio.gather(pay.create_run(ent, "2026-10", AKTOR), pay.create_run(ent, "2026-10", AKTOR),
                                         return_exceptions=True)
            ok = [h for h in hasil if isinstance(h, dict)]
            assert len(ok) == 2 and ok[0]["id"] == ok[1]["id"], hasil
            n = await db.hr_payroll_runs.count_documents({"entity_id": ent, "period": "2026-10",
                                                         "status": {"$nin": ["cancelled", "void", "rejected"]}})
            assert n == 1, (hasil, n)
            assert await db.hr_payslips.count_documents({"entity_id": ent, "run_id": ok[0]["id"]}) == 1
    _jalankan(jalan())

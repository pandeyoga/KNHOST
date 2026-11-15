"""PY-T2 U1 & U11 — lapis A (MongoDB ASLI, data acuan `scripts/dev_restore_demo.sh`; bukan database berisi data nyata).

U1   Migrasi `scripts/migrate_hr_compensation_py_t2.py` di data acuan. Mode baca-saja (bawaan): tidak menulis apa pun,
     tiap PT "→ SAMA" (Σ gaji pokok + tunjangan master = Σ nilai baris yang akan dibuat). Mode `--apply` dua kali
     (HANYA bila `KN_PYT2_TERAPKAN=1` — menulis ke database lingkungan A; keputusan integrator): tiap karyawan tepat
     satu baris kompensasi dan satu penugasan, pratinjau gaji bulan berjalan per PT sebelum = sesudah, jalan kedua
     tidak menulis.
U11  Dua pengesahan BERSAMAAN atas dua baris `pending` bertanggal berlaku sama untuk karyawan yang sama → tepat SATU
     `approved` (indeks unik parsial `uq_employee_effective_approved`), yang lain 409. Beberapa putaran.

Memanggil layanan langsung di proses uji (motor ke `MONGO_URL`/`DB_NAME` dari `backend/.env` lingkungan A).
"""
import asyncio
import contextlib
import importlib.util
import io
import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = Path(__file__).resolve().parents[2]
AKTOR = {"id": "usr_bp_pyt2", "name": "Uji PY-T2", "role": "admin"}
_LOOP = asyncio.new_event_loop()   # satu loop per modul (klien Motor terikat ke loop pertama — pola PY-T1 lapis A)


def _jalankan(coro):
    return _LOOP.run_until_complete(coro)


def _migrasi():
    spec = importlib.util.spec_from_file_location("migrasi_pyt2", REPO / "scripts/migrate_hr_compensation_py_t2.py")
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    return mig


async def _cetak(fn):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        kode = await fn
    return kode, buf.getvalue()


def test_U1_migrasi_baca_saja_data_acuan():
    from db import db
    mig = _migrasi()

    async def jalan():
        n0 = await db.hr_compensation_history.count_documents({}), await db.hr_employee_assignments.count_documents({})
        kode, out = await _cetak(mig.jalankan([]))
        print(out)
        assert kode == 0 and "Mode baca-saja" in out, out
        assert "→ BEDA" not in out, out
        assert (await db.hr_compensation_history.count_documents({}),
                await db.hr_employee_assignments.count_documents({})) == n0
    _jalankan(jalan())


@pytest.mark.skipif(os.environ.get("KN_PYT2_TERAPKAN") != "1",
                    reason="PY-T2 — --apply menulis ke database lingkungan A; jalankan dengan KN_PYT2_TERAPKAN=1")
def test_U1_migrasi_terapkan_dua_kali_data_acuan():
    from db import db
    mig = _migrasi()

    async def jalan():
        kode, out = await _cetak(mig.jalankan(["--apply"]))
        print(out)
        assert kode == 0 and "BEDA" not in out, out
        kode, out = await _cetak(mig.jalankan(["--apply"]))
        assert kode == 0 and "Diterapkan: 0 baris kompensasi · 0 baris penugasan" in out, out
        async for e in db.hr_employees.find({}, {"_id": 0, "id": 1, "name": 1}):
            assert await db.hr_compensation_history.count_documents({"employee_id": e["id"]}) >= 1, e
            assert await db.hr_employee_assignments.count_documents({"employee_id": e["id"]}) >= 1, e
            assert await db.hr_compensation_history.count_documents(
                {"employee_id": e["id"], "source": "migrasi"}) <= 1, e
    _jalankan(jalan())


def test_U11_dua_pengesahan_bersamaan_satu_baris_sah():
    from db import db
    from services import hr_compensation_service as hc

    async def jalan():
        for _ in range(3):
            eid = f"emp_bpyt2_{uuid.uuid4().hex[:8]}"
            await db.hr_employees.insert_one({"id": eid, "name": "Uji PYT2", "entity_id": "ent_ksc",
                                              "status": "inactive", "base_salary": 5_000_000, "allowances": [],
                                              "ptkp_status": "TK0", "join_date": "2026-01-01",
                                              "created_at": "2026-01-01T00:00:00+00:00"})
            emp = await db.hr_employees.find_one({"id": eid}, {"_id": 0})
            await hc.initial_rows(emp, AKTOR, effective_from="2026-01-01")
            rows = [await hc.propose_compensation(emp, {"effective_from": "2027-01-01", "base_salary": g,
                                                        "reason": "uji bersamaan PY-T2"}, AKTOR)
                    for g in (6_000_000, 6_500_000)]
            hasil = await asyncio.gather(*(hc.decide_compensation(r["id"], "approve", AKTOR) for r in rows),
                                         return_exceptions=True)
            ok = [h for h in hasil if isinstance(h, dict)]
            gagal = [h for h in hasil if isinstance(h, hc.CompensationConflict)]
            assert len(ok) == 1 and len(gagal) == 1, hasil
            assert "Sudah ada perubahan kompensasi yang berlaku 2027-01-01" in str(gagal[0])
            assert await db.hr_compensation_history.count_documents(
                {"employee_id": eid, "effective_from": "2027-01-01", "status": "approved"}) == 1
            await hc.remove_rows(eid)
            await db.hr_employees.delete_one({"id": eid})
    _jalankan(jalan())

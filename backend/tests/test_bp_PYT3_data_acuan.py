"""PY-T3 — lapis A (MongoDB ASLI, data acuan `scripts/dev_restore_demo.sh`; bukan database berisi data nyata).

U18  Dua `add_holiday` BERSAMAAN untuk PT dan tanggal yang sama → tepat SATU tersimpan (indeks unik `uq_entity_date`),
     yang lain `HolidayConflict` (router → 409 "Tanggal … sudah terdaftar sebagai hari libur di PT ini."). Beberapa
     putaran; tanggal uji dibersihkan.
L1   Langkah 1 spesifikasi — hitungan dampak K-39 di data acuan: `overtime_impact` tiga periode terakhir per PT (menit
     lembur absensi tanpa pengajuan yang selama ini dibayar dan nilainya). Hanya mencetak (bahan laporan), tanpa tulisan.

Memanggil layanan langsung di proses uji (motor ke `MONGO_URL`/`DB_NAME` dari `backend/.env` lingkungan A).
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AKTOR = {"id": "usr_bp_pyt3", "name": "Uji PY-T3", "role": "admin"}
_LOOP = asyncio.new_event_loop()   # satu loop per modul (klien Motor terikat ke loop pertama — pola PY-T1 lapis A)


def _jalankan(coro):
    return _LOOP.run_until_complete(coro)


def _periode_terakhir(n: int = 3):
    from services import book_date
    y, m = map(int, book_date.tanggal_buku()[:7].split("-"))
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return out


def test_U18_dua_hari_libur_bersamaan_satu_tersimpan():
    from db import db
    from services import hr_work_calendar as wc

    async def jalan():
        ent = (await db.business_entities.find_one({"status": {"$ne": "inactive"}}, {"_id": 0, "id": 1}) or {})["id"]
        for putaran in range(3):
            tanggal = f"2099-12-{20 + putaran:02d}"
            await db.hr_holidays.delete_many({"entity_id": ent, "date": tanggal})
            hasil = await asyncio.gather(
                *[wc.add_holiday(ent, {"date": tanggal, "name": f"Uji PY-T3 {i}", "kind": "perusahaan"}, AKTOR)
                  for i in range(2)], return_exceptions=True)
            try:
                ok = [h for h in hasil if isinstance(h, dict)]
                konflik = [h for h in hasil if isinstance(h, wc.HolidayConflict)]
                assert (len(ok), len(konflik)) == (1, 1), hasil
                assert str(konflik[0]) == f"Tanggal {tanggal} sudah terdaftar sebagai hari libur di PT ini."
                assert await db.hr_holidays.count_documents({"entity_id": ent, "date": tanggal}) == 1
            finally:
                await db.hr_holidays.delete_many({"entity_id": ent, "date": tanggal})
    _jalankan(jalan())


def test_L1_dampak_lembur_absensi_tiga_periode():
    from db import db
    from services import hr_payroll_service as pay

    async def jalan():
        print("\nDampak K-39 (menit lembur absensi tanpa pengajuan yang dibayar bila sumber = absensi):")
        async for e in db.business_entities.find({}, {"_id": 0, "id": 1, "code": 1}):
            for per in _periode_terakhir():
                j = await pay.overtime_impact(e["id"], per)
                print(f"  {e.get('code') or e['id']} {per}: {j['count']} karyawan · {j['total_minutes']} menit · "
                      f"Rp {j['total_amount']:,.2f} (sumber sekarang: {j['sumber']})")
                assert j["total_minutes"] >= 0
    _jalankan(jalan())

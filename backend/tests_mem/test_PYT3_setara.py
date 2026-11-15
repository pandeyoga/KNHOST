"""PY-T3 serah-terima (a) — dengan semua kunci baru pada bawaannya, slip SAMA PERSIS dengan kode sebelum unit ini.

Potret pembanding `data/pratinjau_sebelum_PYT3.json` dihasilkan MESIN LAMA dengan uji ini sendiri:
`KN_PYT3_TULIS_POTRET=1 python -m pytest tests_mem/test_PYT3_setara.py`, dijalankan di salinan `git archive 5f193df`
(PY-T1, sebelum PY-T2) — angkanya tidak diketik. Bukan basis unit `82ef1bb`: di basis itu (PY-T2) baris LEMBUR dan KOMISI
tidak pernah masuk slip reguler (`hr_pay_components.earning_components` hanya menambahkannya di cabang tanpa potongan
periode, sedangkan sejak PY-T2 proses reguler selalu berpotongan) — lembur tidak terbayar. Potret basis disimpan sebagai
bukti (`docs/reviews/2026-11-13/hasil/bukti/PY-T3/pratinjau_basis_82ef1bb.json`); selisihnya dengan potret ini HANYA
baris LEMBUR S1 dan S5 beserta turunannya (bruto, bruto pajak, PPh 21, bersih). Unit ini memulihkan baris itu.
Uji membandingkan pratinjau proses gaji November 2026 PT uji `PYT3S` (BPJS menyala, PPh 21 menyala) pada dua keadaan:

  1. bawaan — tanpa pengaturan apa pun;
  2. pengaturan lama tersembunyi `system_settings{scope:"hr"}.overtime.mode = "flat"` dan `.work_days_per_week = 6`
     (dulu tanpa registry dan tanpa layar; kini terbaca lewat lapisan lama kunci `hr.overtime.mode` /
     `hr.overtime.work_days_per_week`) + pengali lembur 1,75 khusus PT itu (`hr.overtime.multiplier`, lapisan PT).

Karyawan (fixture, disisipkan): S1 7.000.000 + Transport 500.000, K1 — pengajuan lembur Senin 2 Nov 3 jam, Rabu 4 Nov dua
pengajuan (2 dan 3 jam, berdasar libur), Sabtu 7 Nov 5 jam; absensi lembur 45 menit 2 Nov (tanggal berpengajuan), 90
menit Kamis 5 Nov disetujui tanpa pengajuan, 60 menit Jumat 6 Nov di luar lokasi (belum disetujui), rekaman cuti
9 Nov. S2 12.500.000 (di atas batas upah BPJS Kesehatan dan JP) + dua tunjangan, K2. S3 4.000.000 masuk 5 Des 2026.
S4 6.000.000 keluar 20 Nov (masa pajak terakhir) + slip Mar–Okt di sistem. S5 5.500.000 dengan menit telat dan cuti
tanpa gaji disetujui (tanpa efek pada bawaan).

Bandingan: tiap slip — kolom lama, daftar komponen (kode, label, nominal), kejadian lembur (tanggal, sumber, menit,
jenis hari, jam-upah, nominal), hitung ulang setahun; serta total proses.
"""
import datetime
import json
import os
from pathlib import Path

import pytest

from pembantu import pt_uji as _pt_uji

POTRET = Path(__file__).resolve().parent / "data" / "pratinjau_sebelum_PYT3.json"
NOV = "2026-11"
HARI_INI = datetime.datetime(2026, 12, 15, 3, 0, tzinfo=datetime.timezone.utc)
EMP = ("emp_pyt3s_s1", "emp_pyt3s_s2", "emp_pyt3s_s3", "emp_pyt3s_s4", "emp_pyt3s_s5")
KOLOM = ("base_salary", "allowances", "overtime", "overtime_min", "overtime_auto_min", "overtime_filed_min",
         "commission", "other_earnings", "salary_earnings", "gross", "tax_gross", "bpjs_emp", "bpjs_er",
         "bpjs_emp_total", "bpjs_er_total", "pph21", "pph21_month", "pph21_method", "pph21_rate", "ter_category",
         "other_deductions", "net")
TAHUNAN = ("tax_gross", "biaya_jabatan", "pension_deduction", "neto", "ptkp", "pkp", "annual_tax", "prior_withheld",
           "months")


@pytest.fixture(scope="module", autouse=True)
def _hari_ini():
    from services import book_date
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(book_date, "_sekarang", lambda: HARI_INI)
        yield


def _emp(eid, emp_id, gaji, **extra):
    return {"id": emp_id, "code": emp_id.upper(), "name": f"{emp_id} Uji", "entity_id": eid, "status": "active",
            "base_salary": gaji, "allowances": [], "ptkp_status": "K1", "join_date": "2026-01-01",
            "created_at": "2026-01-01T00:00:00+00:00", **extra}


def _absen(emp_id, eid, tanggal, **extra):
    return {"id": f"att_{emp_id}_{tanggal}", "employee_id": emp_id, "entity_id": eid, "date": tanggal,
            "clock_in": f"{tanggal}T08:00:00+07:00", "clock_out": f"{tanggal}T17:00:00+07:00", "method": "manual",
            "status": "hadir", "approved": True, "work_min": 540, "late_min": 0, "early_leave_min": 0,
            "overtime_min": 0, "std_min": 540, **extra}


def _lembur(emp_id, eid, tanggal, jam, n=1, **extra):
    return {"id": f"ot_{emp_id}_{tanggal}_{n}", "number": f"OT-S-{emp_id}-{tanggal}-{n}", "employee_id": emp_id,
            "entity_id": eid, "date": tanggal, "period": tanggal[:7], "hours": jam, "minutes": int(jam * 60),
            "rate_basis": "normal", "status": "approved", "reason": "uji setara PY-T3", **extra}


@pytest.fixture(scope="module")
async def pt(db):
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await _pt_uji("PYT3S")
    invalidate_status_cache()
    s1, s2, s3, s4, s5 = EMP
    await db.hr_employees.insert_many([
        _emp(eid, s1, 7_000_000, allowances=[{"name": "Transport", "amount": 500_000}]),
        _emp(eid, s2, 12_500_000, ptkp_status="K2", allowances=[{"name": "Jabatan", "amount": 1_500_000},
                                                                  {"name": "Makan", "amount": 400_000}]),
        _emp(eid, s3, 4_000_000, join_date="2026-12-05"),
        _emp(eid, s4, 6_000_000, ptkp_status="TK0", status="resigned", join_date="2026-03-01",
             separation_date="2026-11-20"),
        _emp(eid, s5, 5_500_000, ptkp_status="TK0"),
    ])
    await db.hr_overtime.insert_many([
        _lembur(s1, eid, "2026-11-02", 3), _lembur(s1, eid, "2026-11-04", 2, rate_basis="holiday"),
        _lembur(s1, eid, "2026-11-04", 3, n=2, rate_basis="holiday"), _lembur(s1, eid, "2026-11-07", 5),
        _lembur(s1, eid, "2026-11-12", 1, status="pending")])
    await db.hr_attendance.insert_many([
        _absen(s1, eid, "2026-11-02", overtime_min=45), _absen(s1, eid, "2026-11-05", overtime_min=90),
        _absen(s1, eid, "2026-11-06", overtime_min=60, status="flagged", approved=False),
        _absen(s1, eid, "2026-11-09", method="leave", status="cuti", overtime_min=30),
        _absen(s5, eid, "2026-11-03", status="telat", late_min=25), _absen(s5, eid, "2026-11-10", overtime_min=200)])
    await db.hr_leave_requests.insert_one({
        "id": "leave_pyt3s_s5", "number": "LV-PYT3S-1", "employee_id": s5, "entity_id": eid, "leave_type": "unpaid",
        "date_from": "2026-11-17", "date_to": "2026-11-18", "days": 2, "work_dates": ["2026-11-17", "2026-11-18"],
        "status": "approved"})
    await db.hr_payslips.insert_many([
        {"id": f"slip_pyt3s_s4_{m:02d}", "run_id": "prun_pyt3s_fixture", "entity_id": eid, "employee_id": s4,
         "period": f"2026-{m:02d}", "status": "paid", "gross": 6_000_000, "tax_gross": 6_000_000 + 30_000,
         "pph21": 90_000, "bpjs_emp": {"kesehatan": 60_000, "jht": 120_000, "jp": 60_000}} for m in range(3, 11)])
    return eid


def _potret(run: dict) -> dict:
    slips = {}
    for s in run["payslips"]:
        if s["employee_id"] not in EMP:
            continue
        ann = s.get("pph21_annual")
        slips[s["employee_id"]] = {
            "kolom": {k: s.get(k) for k in KOLOM},
            "komponen": [[c["code"], c["label"], c["amount"]] for c in s.get("components") or []],
            "lembur": [[e["date"], e["source"], e["minutes"], e["day_type"], e.get("hour_units"), e.get("amount")]
                       for e in s.get("overtime_events") or []],
            "tahunan": {k: ann.get(k) for k in TAHUNAN} if ann else None,
        }
    return {"slip": slips, "jumlah_slip": sorted(slips)}


async def _keadaan(klien, h, eid) -> dict:
    r = await klien.post("/api/hr/payroll/runs/preview", json={"entity_id": eid, "period": NOV}, headers=h)
    assert r.status_code == 200, r.text
    return _potret(r.json())


async def test_PYT3_a_setara_kode_lama(klien, db, sesi, pt):
    from services import config_resolver as resolver
    h = await sesi("admin@kainnusantara.id", entitas=pt)
    hasil = {"bawaan": await _keadaan(klien, h, pt)}
    await db.system_settings.update_one({"scope": "hr"}, {"$set": {"overtime.mode": "flat",
                                                                   "overtime.work_days_per_week": 6}}, upsert=True)
    await resolver.set_value("hr.overtime.multiplier", 1.75, scope_type="entity", scope_id=pt, actor="uji",
                             reason="uji setara PY-T3")
    try:
        hasil["lama_flat_enam_hari"] = await _keadaan(klien, h, pt)
    finally:
        await db.system_settings.update_one({"scope": "hr"}, {"$unset": {"overtime.mode": "",
                                                                         "overtime.work_days_per_week": ""}})
        await resolver.set_value("hr.overtime.multiplier", 1.5, scope_type="entity", scope_id=pt, actor="uji",
                                 reason="pulihkan uji setara PY-T3")
    data = json.loads(json.dumps(hasil, sort_keys=True))
    if os.environ.get("KN_PYT3_TULIS_POTRET") == "1":
        POTRET.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        pytest.skip(f"potret ditulis ke {POTRET.name}")
    lama = json.loads(POTRET.read_text(encoding="utf-8"))
    assert lama["bawaan"]["slip"], "potret kosong"
    for keadaan in ("bawaan", "lama_flat_enam_hari"):
        for emp in EMP:
            assert data[keadaan]["slip"].get(emp) == lama[keadaan]["slip"].get(emp), (keadaan, emp)
    assert data == lama

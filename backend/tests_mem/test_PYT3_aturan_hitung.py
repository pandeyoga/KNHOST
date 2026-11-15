"""PY-T3 — aturan hitung gaji dari pengaturan per PT (docs/blueprint/unit/PY-T3.md): prorata masuk/keluar, potongan
absensi, lembur dari pengajuan (K-39), kalender libur, saldo awal pajak.

Persiapan bersama (fixture, disisipkan langsung): "hari ini" dibekukan 15 Des 2026 (`services.book_date._sekarang`).
BPJS dimatikan (lapisan PT) untuk semua PT uji kecuali `PYT3B` (U13). Karyawan disisipkan tanpa riwayat kompensasi
(PY-T2: dibaca dari master), TK0, masuk 1 Jan 2026 kecuali disebut lain. Periode November 2026: 30 hari, 21 hari kerja
pola 5 hari tanpa libur (Senin 2 Nov … Senin 30 Nov). Absensi, cuti, pengajuan lembur, dan slip Jul–Nov (U14) disisipkan
langsung (fixture); proses gaji, pratinjau, hari libur, saldo awal, pengaturan, absensi manual (U15) lewat HTTP.

PT: `ent_kanda` (spesifikasi; karyawan seed lain PT itu dinonaktifkan) — K1 (U1–U3, U16), K2 (U4), K3 (U5), K5/K5b/K5c/K5d
(U9–U12); `PYT3P` — K4 (U6, proses → sahkan → posting; PT sendiri supaya jurnal hanya memuat K4); `PYT3Q` — K4b (U7),
K4c (U8) (pratinjau); `PYT3B` — K6 (U13, BPJS menyala) dan K8 (pembanding U2: PT lain); `PYT3T` — K7/K7b (U14).

Tarif PPh 21 diambil dari fungsi (`ter_rate`, `annual_pph21` dengan `aturan_pph21`), bukan diketik ulang; angka di
komentar = tabel bawaan pada `3132cc4` (5.700.000 → 0,5 %; 6.300.000 → 0,75 %; PTKP TK0 54.000.000; pasal 17 lapis
pertama 5 %).
"""
import datetime

import pytest

from pembantu import jumlah, pt_uji as _pt_uji

KANDA = "ent_kanda"
NOV, DES = "2026-11", "2026-12"
HARI_INI = datetime.datetime(2026, 12, 15, 3, 0, tzinfo=datetime.timezone.utc)   # 15 Des 2026 10.00 WIB
PT: dict = {}
SIMPAN: dict = {}
KERJA_NOV = [f"2026-11-{d:02d}" for d in range(1, 31)
             if datetime.date(2026, 11, d).weekday() < 5]   # 21 tanggal


@pytest.fixture(scope="module", autouse=True)
def _hari_ini():
    from services import book_date
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(book_date, "_sekarang", lambda: HARI_INI)
        yield


async def _pt(kode: str) -> str:
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await _pt_uji(kode)
    invalidate_status_cache()
    return eid


async def _atur(key, value, eid, alasan="uji PY-T3"):
    from services import config_resolver as resolver
    await resolver.set_value(key, value, scope_type="entity", scope_id=eid, actor="uji", reason=alasan)


async def _pulihkan(key, eid):
    import config_registry as registry
    await _atur(key, registry.require(key)["default"], eid, "pulihkan uji PY-T3")


def _emp(eid, emp_id, gaji, **extra):
    return {"id": emp_id, "code": emp_id.upper(), "name": f"{emp_id} Uji PY-T3", "entity_id": eid, "status": "active",
            "base_salary": gaji, "allowances": [], "ptkp_status": "TK0", "join_date": "2026-01-01",
            "created_at": "2026-01-01T00:00:00+00:00", **extra}


@pytest.fixture(scope="module")
async def siap(db):
    if PT:
        return PT
    PT["p"], PT["q"], PT["b"], PT["t"] = (await _pt("PYT3P"), await _pt("PYT3Q"), await _pt("PYT3B"),
                                          await _pt("PYT3T"))
    for eid in (KANDA, PT["p"], PT["q"], PT["t"]):
        for k in ("hr.feature_toggles.bpjs_kesehatan", "hr.feature_toggles.bpjs_ketenagakerjaan"):
            await _atur(k, False, eid)
    await db.hr_employees.update_many({"entity_id": KANDA}, {"$set": {"status": "inactive"}})
    await db.hr_employees.insert_many([
        _emp(KANDA, "emp_pyt3_k1", 6_000_000, join_date="2026-11-16"),
        _emp(KANDA, "emp_pyt3_k2", 6_000_000, join_date="2026-12-05"),
        _emp(KANDA, "emp_pyt3_k3", 6_000_000, status="resigned", separation_date="2026-11-15"),
        _emp(KANDA, "emp_pyt3_k5", 5_190_000), _emp(KANDA, "emp_pyt3_k5b", 5_190_000),
        _emp(KANDA, "emp_pyt3_k5c", 5_190_000), _emp(KANDA, "emp_pyt3_k5d", 5_190_000),
        _emp(PT["p"], "emp_pyt3_k4", 6_300_000),
        _emp(PT["q"], "emp_pyt3_k4b", 6_300_000), _emp(PT["q"], "emp_pyt3_k4c", 6_300_000),
        _emp(PT["b"], "emp_pyt3_k6", 5_000_000, allowances=[{"name": "Jabatan", "amount": 1_000_000}]),
        _emp(PT["b"], "emp_pyt3_k8", 6_000_000, join_date="2026-11-16"),
        _emp(PT["t"], "emp_pyt3_k7", 8_000_000), _emp(PT["t"], "emp_pyt3_k7b", 8_000_000),
    ])
    return PT


@pytest.fixture(scope="module")
async def adm(sesi):
    simpan = {}

    async def _h(eid=KANDA):
        if eid not in simpan:
            simpan[eid] = await sesi("admin@kainnusantara.id", entitas=eid)
        return simpan[eid]
    return _h


def _slip(run: dict, emp_id: str) -> dict:
    return next(s for s in run["payslips"] if s["employee_id"] == emp_id)


def _ada(run: dict, emp_id: str) -> bool:
    return any(s["employee_id"] == emp_id for s in run["payslips"])


def _baris(slip: dict, awalan: str = "") -> list:
    return [(c["label"], c["amount"]) for c in slip.get("components") or [] if c["label"].startswith(awalan)]


def _kode(slip: dict, kode: str) -> list:
    return [(c["label"], c["amount"]) for c in slip.get("components") or [] if c["code"] == kode]


async def _proses(klien, h, eid, periode):
    """Proses reguler (buat; bila sudah ada untuk PT+periode itu → hitung ulang)."""
    kunci = f"{eid}:{periode}"
    if kunci in SIMPAN:
        r = await klien.post(f"/api/hr/payroll/runs/{SIMPAN[kunci]}/recalculate", headers=h)
    else:
        r = await klien.post("/api/hr/payroll/runs", json={"entity_id": eid, "period": periode}, headers=h)
    assert r.status_code == 200, r.text
    SIMPAN[kunci] = r.json()["id"]
    return r.json()


async def _pratinjau(klien, h, eid, periode=NOV):
    r = await klien.post("/api/hr/payroll/runs/preview", json={"entity_id": eid, "period": periode}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def _tarif(bruto: float) -> float:
    from services import hr_payroll_service as pay
    return pay.ter_rate("A", bruto, await pay.aturan_pph21("2026-11-30"))


def _absen(emp_id, eid, tanggal, **extra):
    return {"id": f"att_{emp_id}_{tanggal}", "employee_id": emp_id, "entity_id": eid, "date": tanggal,
            "clock_in": f"{tanggal}T08:00:00+07:00", "clock_out": f"{tanggal}T17:00:00+07:00", "method": "manual",
            "status": "hadir", "approved": True, "work_min": 540, "late_min": 0, "early_leave_min": 0,
            "overtime_min": 0, "std_min": 540, **extra}


def _lembur(emp_id, eid, tanggal, jam, **extra):
    return {"id": f"ot_{emp_id}_{tanggal}", "number": f"OT-{emp_id}-{tanggal}", "employee_id": emp_id,
            "entity_id": eid, "date": tanggal, "period": tanggal[:7], "hours": jam, "minutes": int(jam * 60),
            "rate_basis": "normal", "status": "approved", "reason": "uji PY-T3", **extra}


# ── U1 — prorata mati (bawaan) = perilaku hari ini ───────────────────────────────────────────────────────────────────
async def test_PYT3_U1_prorata_mati_gaji_penuh(klien, db, adm, siap):
    import config_registry as registry
    e = registry.require("hr.prorata_masuk_keluar")
    assert (e["default"], [o["value"] for o in e["options"]]) == ("mati", ["mati", "hari_kalender", "hari_kerja"])
    run = await _proses(klien, await adm(), KANDA, NOV)
    # K1 masuk 16 Nov, gaji 6.000.000, prorata mati → sebulan penuh
    assert _baris(_slip(run, "emp_pyt3_k1"), "Gaji Pokok") == [("Gaji Pokok", 6_000_000)]


# ── U2 — hari kalender: 6.000.000 × 15 ÷ 30 = 3.000.000; PT lain tidak berubah ──────────────────────────────────────
async def test_PYT3_U2_prorata_hari_kalender_per_pt(klien, db, adm, siap):
    await _atur("hr.prorata_masuk_keluar", "hari_kalender", KANDA)
    try:
        run = await _proses(klien, await adm(), KANDA, NOV)
        s1 = _slip(run, "emp_pyt3_k1")
        assert _baris(s1, "Gaji Pokok") == [("Gaji Pokok (16–30 Nov)", 3_000_000)]
        assert s1["base_salary"] == 3_000_000
        # PT lain (PYT3B, bawaan mati): K8 masuk 16 Nov tetap 6.000.000
        lain = await _pratinjau(klien, await adm(PT["b"]), PT["b"])
        assert _baris(_slip(lain, "emp_pyt3_k8"), "Gaji Pokok") == [("Gaji Pokok", 6_000_000)]
    finally:
        await _pulihkan("hr.prorata_masuk_keluar", KANDA)


# ── U3 (a) — hari kerja: 6.000.000 × 11 ÷ 21 = 3.142.857,14 ─────────────────────────────────────────────────────────
async def test_PYT3_U3a_prorata_hari_kerja(klien, db, adm, siap):
    await _atur("hr.prorata_masuk_keluar", "hari_kerja", KANDA)
    try:
        run = await _proses(klien, await adm(), KANDA, NOV)
        # 16–30 Nov: Senin 16 … Jumat 20 (5) + 23–27 (5) + Senin 30 (1) = 11 hari kerja dari 21
        assert _baris(_slip(run, "emp_pyt3_k1"), "Gaji Pokok") == [("Gaji Pokok (16–30 Nov)", 3_142_857.14)]
    finally:
        await _pulihkan("hr.prorata_masuk_keluar", KANDA)


# ── U16 — U3 pertama + pembulatan rupiah penuh → 3.142.857 ───────────────────────────────────────────────────────────
async def test_PYT3_U16_pembulatan_rupiah(klien, db, adm, siap):
    await _atur("hr.prorata_masuk_keluar", "hari_kerja", KANDA)
    await _atur("hr.pembulatan_rupiah", True, KANDA)
    try:
        run = await _proses(klien, await adm(), KANDA, NOV)
        s1 = _slip(run, "emp_pyt3_k1")
        assert _baris(s1, "Gaji Pokok") == [("Gaji Pokok (16–30 Nov)", 3_142_857)]
        assert all(float(c["amount"]).is_integer() for c in s1["components"]), s1["components"]
    finally:
        await _pulihkan("hr.pembulatan_rupiah", KANDA)
        await _pulihkan("hr.prorata_masuk_keluar", KANDA)


# ── U4 — masuk 5 Des → tidak ikut proses November, apa pun nilai kuncinya ────────────────────────────────────────────
async def test_PYT3_U4_masuk_sesudah_periode_tidak_digaji(klien, db, adm, siap):
    try:
        for nilai in ("mati", "hari_kalender", "hari_kerja"):
            await _atur("hr.prorata_masuk_keluar", nilai, KANDA)
            run = await _proses(klien, await adm(), KANDA, NOV)
            assert not _ada(run, "emp_pyt3_k2"), nilai
            assert not _ada(await _pratinjau(klien, await adm(), KANDA), "emp_pyt3_k2"), nilai
    finally:
        await _pulihkan("hr.prorata_masuk_keluar", KANDA)


# ── U5 — keluar 15 Nov, hari kalender → 6.000.000 × 15 ÷ 30 = 3.000.000 ─────────────────────────────────────────────
async def test_PYT3_U5_prorata_keluar(klien, db, adm, siap):
    run = await _proses(klien, await adm(), KANDA, NOV)
    assert _baris(_slip(run, "emp_pyt3_k3"), "Gaji Pokok") == [("Gaji Pokok", 6_000_000)]   # bawaan mati
    await _atur("hr.prorata_masuk_keluar", "hari_kalender", KANDA)
    try:
        run = await _proses(klien, await adm(), KANDA, NOV)
        assert _baris(_slip(run, "emp_pyt3_k3"), "Gaji Pokok") == [("Gaji Pokok (1–15 Nov)", 3_000_000)]
    finally:
        await _pulihkan("hr.prorata_masuk_keluar", KANDA)


# ── U9 — lembur: pengajuan 2 jam 10 Nov + absensi 120 menit 11 Nov tanpa pengajuan ───────────────────────────────────
@pytest.fixture(scope="module")
async def lembur_k5(db, siap):
    k5 = "emp_pyt3_k5"
    await db.hr_overtime.insert_one(_lembur(k5, KANDA, "2026-11-10", 2))
    await db.hr_attendance.insert_one(_absen(k5, KANDA, "2026-11-11", clock_out="2026-11-11T19:00:00+07:00",
                                             work_min=660, overtime_min=120))
    return k5


async def test_PYT3_U9a_sumber_absensi_dan_ambang(klien, db, adm, siap, lembur_k5):
    # upah sejam = 5.190.000 ÷ 173 = 30.000; 2 jam hari kerja = 1 × 1,5 + 1 × 2 = 3,5 jam-upah = 105.000 per tanggal
    await _atur("hr.overtime.sumber", "absensi", KANDA)
    try:
        s = _slip(await _pratinjau(klien, await adm(), KANDA), lembur_k5)
        assert s["overtime"] == 210_000 and _kode(s, "LEMBUR")[0][1] == 210_000
        assert [(e["date"], e["source"]) for e in s["overtime_events"]] == [
            ("2026-11-10", "filed"), ("2026-11-11", "attendance")]
        await _atur("hr.overtime.ambang_menit", 150, KANDA)
        s = _slip(await _pratinjau(klien, await adm(), KANDA), lembur_k5)
        assert s["overtime"] == 105_000   # 120 menit < ambang 150 → diabaikan
    finally:
        await _pulihkan("hr.overtime.ambang_menit", KANDA)
        await _pulihkan("hr.overtime.sumber", KANDA)


async def test_PYT3_U9b_bawaan_hanya_pengajuan(klien, db, adm, siap, lembur_k5):
    import config_registry as registry
    assert registry.require("hr.overtime.sumber")["default"] == "pengajuan"   # K-39
    s = _slip(await _pratinjau(klien, await adm(), KANDA), lembur_k5)
    assert s["overtime"] == 105_000
    assert [e["source"] for e in s["overtime_events"]] == ["filed"]


# ── tambahan — dampak lembur: menit absensi tanpa pengajuan yang tidak dibayar pada sumber "pengajuan" ──────────────
async def test_PYT3_dampak_lembur_absensi(klien, db, adm, siap, lembur_k5):
    r = await klien.get("/api/hr/payroll/overtime-impact", params={"period": NOV}, headers=await adm())
    assert r.status_code == 200, r.text
    j = r.json()
    row = next(x for x in j["rows"] if x["employee_id"] == lembur_k5)
    assert (row["minutes"], row["days"], row["amount"]) == (120, 1, 105_000)
    assert j["total_minutes"] >= 120 and j["entity_id"] == KANDA


# ── U10 — mode flat (pengali 1,5): 2 × 1,5 × 30.000 = 90.000; simulator 4 jam bertingkat = 225.000 ─────────────────
async def test_PYT3_U10_mode_flat_dan_simulator(klien, db, adm, siap, kepala_admin):
    k = "emp_pyt3_k5b"
    await db.hr_overtime.insert_one(_lembur(k, KANDA, "2026-11-10", 2))
    await _atur("hr.overtime.mode", "flat", KANDA)
    try:
        assert _slip(await _pratinjau(klien, await adm(), KANDA), k)["overtime"] == 90_000
    finally:
        await _pulihkan("hr.overtime.mode", KANDA)
    r = await klien.post("/api/config/simulate", headers=kepala_admin, json={
        "simulator": "payroll_overtime", "sample": {"salary": 5_190_000, "overtime_hours": 4},
        "ctx": {"entity_id": KANDA}})
    assert r.status_code == 200, r.text
    # 4 jam hari kerja bertingkat: 1 × 1,5 + 3 × 2 = 7,5 jam-upah × 30.000 = 225.000 — fungsi mesin yang sama
    from services import hr_payroll_service as pay
    assert pay.overtime_hour_units(4, "workday", False) == 7.5
    assert r.json()["nilai"] == 225_000, r.json()


# ── U12 — Sabtu 14 Nov: pola 5 hari = hari istirahat (2 × 2 = 4 → 120.000); pola 6 = hari kerja (3,5 → 105.000) ────
async def test_PYT3_U12_hari_kerja_seminggu(klien, db, adm, siap):
    from services import hr_work_calendar as wc
    k = "emp_pyt3_k5d"
    await db.hr_overtime.insert_one(_lembur(k, KANDA, "2026-11-14", 2))
    assert _slip(await _pratinjau(klien, await adm(), KANDA), k)["overtime"] == 120_000
    assert await wc.work_days(KANDA, "2026-11-01", "2026-11-30") == 21
    await _atur("hr.overtime.work_days_per_week", "6", KANDA)
    try:
        assert _slip(await _pratinjau(klien, await adm(), KANDA), k)["overtime"] == 105_000
        assert await wc.work_days(KANDA, "2026-11-01", "2026-11-30") == 25   # + Sabtu 7, 14, 21, 28
    finally:
        await _pulihkan("hr.overtime.work_days_per_week", KANDA)


# ── U13 — dasar BPJS = Σ komponen ber-in_bpjs_base: 1 % × (5.000.000 + 1.000.000) = 60.000; tanpa tanda 50.000 ───────
async def test_PYT3_U13_dasar_bpjs_dari_tanda_komponen(klien, db, adm, siap):
    h = await adm(PT["b"])
    s = _slip(await _pratinjau(klien, h, PT["b"]), "emp_pyt3_k6")
    assert s["bpjs_emp"]["kesehatan"] == 50_000
    comps = (await klien.get("/api/hr/payroll/components", headers=h)).json()["items"]
    tj = next(c for c in comps if c["code"] == "TUNJANGAN")
    r = await klien.patch(f"/api/hr/payroll/components/{tj['id']}", headers=h, json={"in_bpjs_base": True})
    assert r.status_code == 200, r.text
    try:
        s = _slip(await _pratinjau(klien, h, PT["b"]), "emp_pyt3_k6")
        assert s["bpjs_emp"]["kesehatan"] == 60_000
        assert _kode(s, "BPJS_KES") == [("BPJS Kesehatan", 60_000)]
    finally:
        await klien.patch(f"/api/hr/payroll/components/{tj['id']}", headers=h, json={"in_bpjs_base": False})


# ── U14 — saldo awal pajak 6 masa di luar sistem; Desember menghitung ulang setahun ──────────────────────────────────
async def test_PYT3_U14_saldo_awal_pajak(klien, db, adm, siap):
    from services import hr_payroll_service as pay
    h = await adm(PT["t"])
    for k in ("emp_pyt3_k7", "emp_pyt3_k7b"):   # slip Jul–Nov di sistem: 8.000.000, PPh 21 120.000 per bulan
        await db.hr_payslips.insert_many([
            {"id": f"slip_{k}_{m:02d}", "run_id": "prun_pyt3_fixture", "entity_id": PT["t"], "employee_id": k,
             "period": f"2026-{m:02d}", "status": "paid", "gross": 8_000_000, "tax_gross": 8_000_000,
             "pph21": 120_000, "bpjs_emp": {"kesehatan": 0, "jht": 0, "jp": 0}} for m in range(7, 12)])
    r = await klien.put("/api/hr/employees/emp_pyt3_k7/tax-opening", headers=h, json={
        "year": 2026, "months": 6, "tax_gross": 48_000_000, "pension_deduction": 0, "pph21_withheld": 720_000,
        "note": "Jan–Jun dibayar di luar sistem"})
    assert r.status_code == 200, r.text
    r = await klien.get("/api/hr/employees/emp_pyt3_k7/tax-opening", params={"year": 2026}, headers=h)
    assert r.status_code == 200 and r.json()["months"] == 6, r.text
    run = await _pratinjau(klien, h, PT["t"], DES)
    ann = _slip(run, "emp_pyt3_k7")["pph21_annual"]
    aturan = await pay.aturan_pph21("2026-12-31")
    harap = pay.annual_pph21(tax_gross=96_000_000, pension_deduction=0, months=12, ptkp_status="TK0", aturan=aturan)
    # bruto 48.000.000 + 5 × 8.000.000 + 8.000.000 = 96.000.000; biaya jabatan min(5 % × 96 jt, 500.000 × 12)
    # = 4.800.000; neto 91.200.000; PKP 91.200.000 − 54.000.000 = 37.200.000; pajak 5 % = 1.860.000
    assert (ann["tax_gross"], ann["months"], ann["biaya_jabatan"], ann["neto"], ann["pkp"]) == (
        96_000_000, 12, harap["biaya_jabatan"], harap["neto"], harap["pkp"])
    assert ann["prior_withheld"] == 720_000 + 600_000
    assert _slip(run, "emp_pyt3_k7")["pph21"] == round(harap["annual_tax"] - 1_320_000, 2)   # 540.000
    # tanpa saldo awal: bruto 48.000.000 (6 masa) → PKP 0 → pajak 0 − 600.000 = −600.000
    tanpa = pay.annual_pph21(tax_gross=48_000_000, pension_deduction=0, months=6, ptkp_status="TK0", aturan=aturan)
    assert _slip(run, "emp_pyt3_k7b")["pph21"] == round(tanpa["annual_tax"] - 600_000, 2)   # −600.000


async def test_PYT3_U14b_saldo_awal_validasi_dan_terkunci(klien, db, adm, siap):
    h = await adm(PT["t"])
    url = "/api/hr/employees/emp_pyt3_k7b/tax-opening"
    for masa in (0, 12):
        r = await klien.put(url, headers=h, json={"year": 2026, "months": masa, "tax_gross": 1, "pension_deduction": 0,
                                                  "pph21_withheld": 0})
        assert r.status_code == 400 and r.json()["detail"] == "Jumlah masa harus 1 sampai 11.", r.text
    r = await klien.get(url, params={"year": 2026}, headers=h)
    assert r.status_code == 200 and r.json() is None, r.text
    run = await _proses(klien, h, PT["t"], DES)
    for aksi in ("submit", "approve", "post-gl"):
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/{aksi}", headers=h)
        assert r.status_code == 200, (aksi, r.text)
    r = await klien.put(url, headers=h, json={"year": 2026, "months": 6, "tax_gross": 48_000_000,
                                              "pension_deduction": 0, "pph21_withheld": 720_000})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == ("Pajak 2026 karyawan ini sudah dihitung ulang, jadi saldo awalnya tidak bisa "
                                  "diubah.")


# ── U15 — menit lembur absensi: masuk 07.00, pulang 17.30, shift 08–17 → 90 (jam kerja lebih) / 30 (lewat jam pulang) ─
async def test_PYT3_U15_menit_lembur_absensi(klien, db, adm, siap):
    h = await adm()
    r = await klien.post("/api/hr/shifts", headers=h, json={"name": "Shift Uji PY-T3", "jam_in": "08:00",
                                                            "jam_out": "17:00", "grace_late_min": 0})
    assert r.status_code == 200, r.text
    await db.hr_employees.update_one({"id": "emp_pyt3_k5c"}, {"$set": {"shift_id": r.json()["id"]}})
    body = {"employee_id": "emp_pyt3_k5c", "date": "2026-11-03", "clock_in": "07:00", "clock_out": "17:30"}
    r = await klien.post("/api/hr/attendance/manual", headers=h, json=body)
    assert r.status_code == 200 and r.json()["overtime_min"] == 90, r.text
    await _atur("hr.overtime.hitung_absensi", "lewat_jam_pulang", KANDA)
    try:
        r = await klien.post("/api/hr/attendance/manual", headers=h, json=body)
        assert r.status_code == 200 and r.json()["overtime_min"] == 30, r.text
    finally:
        await _pulihkan("hr.overtime.hitung_absensi", KANDA)
        await db.hr_attendance.delete_many({"employee_id": "emp_pyt3_k5c"})


# ── U17 — sebelas kunci: putaran t1_config + nilai tak sah ──────────────────────────────────────────────────────────
SEBELAS = ("hr.prorata_masuk_keluar", "hr.prorata_perubahan_gaji", "hr.potongan_alpha", "hr.potongan_cuti_tanpa_gaji",
           "hr.potongan_telat_per_menit", "hr.overtime.sumber", "hr.overtime.ambang_menit", "hr.overtime.mode",
           "hr.overtime.work_days_per_week", "hr.overtime.hitung_absensi", "hr.pembulatan_rupiah")


async def test_PYT3_U17_kunci_pengaturan(klien, kepala_admin):
    import config_registry as registry
    from test_KFT8_putaran_pengaturan import putaran
    for key in SEBELAS:
        e = registry.require(key)
        assert (e["group"], e["scopes"], e["risk"], e["requires_reason"], e["permission"]) == (
            "sdm", ["global", "entity"], "high", True, ["hr", "manage_payroll"]), key
        if key != "hr.prorata_perubahan_gaji":
            assert e["consumers"] == ["services/hr_pay_rules.py:rules"], key
        gagal = await putaran(klien, kepala_admin, key)
        assert not gagal, "\n".join(gagal)
    assert [o["value"] for o in registry.require("hr.prorata_perubahan_gaji")["options"]] == [
        "mati", "hari_kalender", "hari_kerja"]
    for key, nilai in (("hr.prorata_masuk_keluar", "hari"), ("hr.potongan_telat_per_menit", -5),
                       ("hr.overtime.ambang_menit", -5)):
        r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
            "key": key, "value": nilai, "scope_type": "global", "scope_id": "", "reason": "uji nilai tak sah PY-T3"}]})
        assert r.status_code == 400, (key, r.text)
    assert "Dipakai hanya bila cara hitung pengali = flat." in registry.require("hr.overtime.multiplier")["help"]


# ── U18 — izin dan keunikan hari libur ──────────────────────────────────────────────────────────────────────────────
async def test_PYT3_U18_izin_dan_hari_libur(klien, db, akun, sesi, adm, siap, peran_manajer_kosong,
                                            peran_tanpa_acuan):
    hk = await sesi(await akun(await peran_manajer_kosong(), entitas=(PT["q"],)), entitas=PT["q"])
    r = await klien.post("/api/hr/holidays", headers=hk, json={"date": "2026-12-25", "name": "Natal",
                                                               "kind": "nasional"})
    assert r.status_code == 403, r.text
    r = await klien.put("/api/hr/employees/emp_pyt3_k4b/tax-opening", headers=hk, json={
        "year": 2026, "months": 3, "tax_gross": 1, "pension_deduction": 0, "pph21_withheld": 0})
    assert r.status_code == 403, r.text
    # peran tanpa acuan yang memegang izin kelola absensi → boleh
    rid = await peran_tanpa_acuan({"hr": ["view", "manage_attendance"]}, label="Absensi PY-T3")
    ht = await sesi(await akun(rid, entitas=(PT["q"],)), entitas=PT["q"])
    r = await klien.post("/api/hr/holidays", headers=ht, json={"date": "2026-12-25", "name": "Natal",
                                                               "kind": "nasional"})
    assert r.status_code == 200, r.text
    hid = r.json()["id"]
    r = await klien.post("/api/hr/holidays", headers=ht, json={"date": "2026-12-25", "name": "Natal (kembar)",
                                                               "kind": "nasional"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "Tanggal 2026-12-25 sudah terdaftar sebagai hari libur di PT ini."
    assert await jumlah("hr_holidays", {"entity_id": PT["q"], "date": "2026-12-25"}) == 1
    r = await klien.get("/api/hr/holidays", params={"year": 2026}, headers=ht)
    assert r.status_code == 200 and [x["date"] for x in r.json()["rows"]] == ["2026-12-25"], r.text
    semua = {**await adm(PT["q"]), "X-Entity-Id": "all"}
    r = await klien.post("/api/hr/holidays", headers=semua, json={"date": "2026-12-26", "name": "Cuti bersama",
                                                                  "kind": "cuti_bersama"})
    assert r.status_code == 409, r.text
    r = await klien.delete(f"/api/hr/holidays/{hid}", headers=hk)
    assert r.status_code == 403, r.text
    r = await klien.delete(f"/api/hr/holidays/{hid}", headers=ht)
    assert r.status_code == 200, r.text
    assert await jumlah("hr_holidays", {"entity_id": PT["q"]}) == 0


# ── U3 (b) — libur perusahaan 25 Nov: × 10 ÷ 20 = 3.000.000 ──────────────────────────────────────────────────────────
async def test_PYT3_U3b_libur_mengurangi_hari_kerja(klien, db, adm, siap):
    h = await adm()
    r = await klien.post("/api/hr/holidays", headers=h, json={"date": "2026-11-25", "name": "Libur perusahaan",
                                                              "kind": "perusahaan"})
    assert r.status_code == 200, r.text
    await _atur("hr.prorata_masuk_keluar", "hari_kerja", KANDA)
    try:
        run = await _proses(klien, h, KANDA, NOV)
        assert _baris(_slip(run, "emp_pyt3_k1"), "Gaji Pokok") == [("Gaji Pokok (16–30 Nov)", 3_000_000)]
    finally:
        await _pulihkan("hr.prorata_masuk_keluar", KANDA)


# ── U11 — pengajuan 2 jam pada hari libur 25 Nov: 2 × 2 × 30.000 = 120.000 ──────────────────────────────────────────
async def test_PYT3_U11_lembur_hari_libur(klien, db, adm, siap):
    from services import hr_work_calendar as wc
    assert await wc.is_holiday(KANDA, "2026-11-25")   # didaftarkan U3 (b)
    k = "emp_pyt3_k5c"
    await db.hr_overtime.insert_one(_lembur(k, KANDA, "2026-11-25", 2))
    s = _slip(await _pratinjau(klien, await adm(), KANDA), k)
    assert s["overtime"] == 120_000 and s["overtime_events"][0]["day_type"] == "holiday"


# ── U6 — potongan tidak hadir: 6.300.000 ÷ 21 × 2 = 600.000; proses → sahkan → posting ───────────────────────────────
async def test_PYT3_U6_potongan_tidak_hadir_dan_jurnal(klien, db, adm, siap):
    k4, eid = "emp_pyt3_k4", PT["p"]
    h = await adm(eid)
    await db.hr_attendance.insert_many([_absen(k4, eid, d) for d in KERJA_NOV if d not in ("2026-11-12",
                                                                                         "2026-11-13")])
    s = _slip(await _pratinjau(klien, h, eid), k4)   # kunci bawaan: tanpa potongan
    assert _kode(s, "POT_ALPHA") == [] and s["tax_gross"] == 6_300_000
    assert s["pph21"] == round(6_300_000 * await _tarif(6_300_000), 2)   # 0,75 % → 47.250
    assert s["net"] == round(6_300_000 - s["pph21"], 2)                  # 6.252.750
    await _atur("hr.potongan_alpha", True, eid)
    run = await _proses(klien, h, eid, NOV)
    s = _slip(run, k4)
    assert _kode(s, "POT_ALPHA") == [("Potongan tidak hadir (2 hari)", 600_000)]
    assert s["tax_gross"] == 5_700_000
    pph = round(5_700_000 * await _tarif(5_700_000), 2)                   # 0,5 % → 28.500
    assert s["pph21"] == pph and s["net"] == round(6_300_000 - 600_000 - pph, 2)   # 5.671.500
    for aksi in ("submit", "approve", "post-gl"):
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/{aksi}", headers=h)
        assert r.status_code == 200, (aksi, r.text)
    je = await db.journal_entries.find_one({"source_type": "payroll_run", "source_id": run["id"],
                                            "status": {"$ne": "void"}}, {"_id": 0})
    baris = sorted((ln["account_code"], round(ln["debit"], 2), round(ln["credit"], 2)) for ln in je["lines"])
    assert baris == sorted([("6-1000", 6_300_000, 0), ("6-1000", 0, 600_000), ("2-1800", 0, pph),
                            ("2-1600", 0, round(5_700_000 - pph, 2))]), baris


# ── U7 — cuti tanpa gaji disetujui 12 Nov: 1 hari × 300.000 ─────────────────────────────────────────────────────────
async def test_PYT3_U7_potongan_cuti_tanpa_gaji(klien, db, adm, siap):
    k, eid = "emp_pyt3_k4b", PT["q"]
    await db.hr_attendance.insert_many([_absen(k, eid, d) for d in KERJA_NOV if d != "2026-11-12"])
    await db.hr_leave_requests.insert_one({
        "id": "leave_pyt3_k4b", "number": "LV-PYT3-1", "employee_id": k, "entity_id": eid, "leave_type": "unpaid",
        "leave_label": "Cuti Tanpa Gaji", "date_from": "2026-11-12", "date_to": "2026-11-12", "days": 1,
        "work_dates": ["2026-11-12"], "status": "approved"})
    await _atur("hr.potongan_cuti_tanpa_gaji", True, eid)
    await _atur("hr.potongan_alpha", True, eid)   # hari cuti disetujui bukan "tidak hadir"
    try:
        s = _slip(await _pratinjau(klien, await adm(eid), eid), k)
        assert _kode(s, "POT_CUTI_TG") == [("Potongan cuti tanpa gaji (1 hari)", 300_000)]
        assert _kode(s, "POT_ALPHA") == []
    finally:
        await _pulihkan("hr.potongan_alpha", eid)
        await _pulihkan("hr.potongan_cuti_tanpa_gaji", eid)


# ── U8 — terlambat 45 menit × Rp 1.000 = 45.000 ──────────────────────────────────────────────────────────────────────
async def test_PYT3_U8_potongan_terlambat(klien, db, adm, siap):
    k, eid = "emp_pyt3_k4c", PT["q"]
    await db.hr_attendance.insert_many([_absen(k, eid, d, **({"status": "telat", "late_min": 30} if d == "2026-11-04"
                                                              else {"status": "telat", "late_min": 15}
                                                              if d == "2026-11-18" else {}))
                                        for d in KERJA_NOV])
    await _atur("hr.potongan_telat_per_menit", 1_000, eid)
    try:
        s = _slip(await _pratinjau(klien, await adm(eid), eid), k)
        assert _kode(s, "POT_TELAT") == [("Potongan terlambat (45 menit)", 45_000)]
    finally:
        await _pulihkan("hr.potongan_telat_per_menit", eid)


# ── tambahan (b) — komponen bawaan potongan absensi & tanda prorata ─────────────────────────────────────────────────
async def test_PYT3_komponen_bawaan_potongan_absensi(klien, adm, siap):
    from services.gl_service import ACC_BEBAN_GAJI
    comps = {c["code"]: c for c in (await klien.get("/api/hr/payroll/components", headers=await adm(PT["p"]))).json()["items"]}
    for kode, nama in (("POT_ALPHA", "Potongan tidak hadir"), ("POT_CUTI_TG", "Potongan cuti tanpa gaji"),
                       ("POT_TELAT", "Potongan terlambat")):
        c = comps[kode]
        assert (c["name"], c["kind"], c["calc"], c["bucket"], c["taxable"], c["account_code"], c["system"]) == (
            nama, "potongan", "absensi", "other_deductions", True, ACC_BEBAN_GAJI, True), c
    assert comps["GAJI_POKOK"]["prorate"] is True and comps["TUNJANGAN"]["prorate"] is True
    assert comps["LEMBUR"]["prorate"] is False


# ── tambahan (b) — cara hitung baru: per hari hadir (rate × hari hadir) dan persen gaji pokok ───────────────────────
async def test_PYT3_komponen_per_hari_hadir_dan_persen_dasar(klien, db, adm, siap):
    eid = PT["q"]
    h = await adm(eid)
    for body in ({"code": "UANG_MAKAN", "name": "Uang makan", "kind": "pendapatan", "calc": "per_hari_hadir", "rate": 0},
                 {"code": "KOPERASI", "name": "Iuran koperasi", "kind": "potongan", "calc": "persen_dasar", "rate": 150,
                  "account_code": "6-1000"}):
        r = await klien.post("/api/hr/payroll/components", headers=h, json=body)
        assert r.status_code == 400, r.text
    r = await klien.post("/api/hr/payroll/components", headers=h, json={
        "code": "UANG_MAKAN", "name": "Uang makan", "kind": "pendapatan", "calc": "per_hari_hadir", "rate": 25_000,
        "allowed_run_types": ["regular", "susulan"]})
    assert r.status_code == 200 and r.json()["allowed_run_types"] == ["regular"], r.text
    um = r.json()["id"]
    r = await klien.post("/api/hr/payroll/components", headers=h, json={
        "code": "KOPERASI", "name": "Iuran koperasi", "kind": "potongan", "calc": "persen_dasar", "rate": 1,
        "account_code": "6-1000"})
    assert r.status_code == 200 and r.json()["rate"] == 1, r.text
    kop = r.json()["id"]
    try:
        run = await _pratinjau(klien, h, eid)
        # K4c: 21 rekaman hadir/telat → 21 × 25.000 = 525.000; 1 % × 6.300.000 = 63.000
        s = _slip(run, "emp_pyt3_k4c")
        assert _kode(s, "UANG_MAKAN") == [("Uang makan (21 hari)", 525_000)]
        assert _kode(s, "KOPERASI") == [("Iuran koperasi (1 %)", 63_000)]
        assert s["other_deductions"] == 63_000 and s["attendance_summary"]["present_days"] == 21
        # K4b: 20 hari hadir (12 Nov cuti) → 500.000
        assert _kode(_slip(run, "emp_pyt3_k4b"), "UANG_MAKAN") == [("Uang makan (20 hari)", 500_000)]
    finally:
        for cid in (um, kop):
            await klien.patch(f"/api/hr/payroll/components/{cid}", headers=h, json={"is_active": False})


# ── tambahan (b) — "Gaji berubah di tengah bulan" = hari kerja (pilihan baru PY-T3) ────────────────────────────────
async def test_PYT3_prorata_perubahan_gaji_hari_kerja(klien, db, adm, siap):
    eid, k = PT["q"], "emp_pyt3_k9"
    await db.hr_employees.insert_one(_emp(eid, k, 7_500_000))
    await db.hr_compensation_history.insert_many([
        {"id": f"hcomp_{k}_1", "employee_id": k, "effective_from": "2026-01-01", "base_salary": 6_000_000,
         "fixed_components": [], "status": "approved"},
        {"id": f"hcomp_{k}_2", "employee_id": k, "effective_from": "2026-11-16", "base_salary": 7_500_000,
         "fixed_components": [], "status": "approved"}])
    await db.hr_employee_assignments.insert_one({"id": f"hasg_{k}", "employee_id": k, "entity_id": eid,
                                                 "effective_from": "2026-01-01", "status": "approved"})
    await _atur("hr.prorata_perubahan_gaji", "hari_kerja", eid)
    try:
        s = _slip(await _pratinjau(klien, await adm(eid), eid), k)
        # 1–15 Nov: 10 hari kerja; 16–30 Nov: 11 hari kerja; dari 21 → 6.000.000 × 10 ÷ 21 = 2.857.142,86 → 2.857.143;
        # 7.500.000 × 11 ÷ 21 = 3.928.571,43 → 3.928.571 (rupiah penuh, sama dengan prorata perubahan gaji PY-T2)
        assert _baris(s, "Gaji Pokok") == [("Gaji Pokok (1–15 Nov)", 2_857_143), ("Gaji Pokok (16–30 Nov)", 3_928_571)]
    finally:
        await _pulihkan("hr.prorata_perubahan_gaji", eid)


# ── tambahan (b) — skrip data lama: baca-saja tidak menulis; --apply menandai Diprorata, aman diulang ───────────────
async def test_PYT3_skrip_migrasi(db, siap, capsys):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "migrasi_pyt3", Path(__file__).resolve().parents[2] / "scripts/migrasi_pyt3_aturan_gaji.py")
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    await db.hr_pay_components.update_many({"entity_id": PT["t"], "code": {"$in": ["GAJI_POKOK", "TUNJANGAN"]}},
                                           {"$set": {"prorate": False}})
    assert await mig.jalankan([], db=db) == 0
    out = capsys.readouterr().out
    assert "Mode baca-saja" in out and "PT PYT3T: komponen bawaan belum Diprorata → GAJI_POKOK, TUNJANGAN" in out, out
    assert "Dampak lembur PT" in out, out
    assert await db.hr_pay_components.count_documents({"entity_id": PT["t"], "prorate": True,
                                                       "code": {"$in": ["GAJI_POKOK", "TUNJANGAN"]}}) == 0
    assert await mig.jalankan(["--apply", "--tanpa-dampak"], db=db) == 0
    assert "Diterapkan: 2 komponen ditandai Diprorata." in capsys.readouterr().out
    assert await mig.jalankan(["--apply", "--tanpa-dampak"], db=db) == 0
    assert "Diterapkan: 0 komponen ditandai Diprorata." in capsys.readouterr().out

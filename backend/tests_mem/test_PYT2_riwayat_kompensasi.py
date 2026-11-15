"""PY-T2 — riwayat kompensasi dan penugasan PT karyawan bertanggal berlaku (docs/blueprint/unit/PY-T2.md).

Persiapan bersama (fixture, disisipkan langsung): dua PT uji tersendiri — `PTA` (peran `ent_ksc` di spesifikasi) dan
`PTB` (peran `ent_kanda`) — karena data awal menyemai proses gaji reguler `ent_ksc` untuk dua bulan sebelum jam sistem
(bootstrap `seed_hr_payroll_foundation`), yang bertabrakan dengan proses September/Oktober uji ini (pola PY-T1
menyimpang no. 12). BPJS dimatikan untuk kedua PT (lapisan PT), jadi bruto pajak = bruto. Karyawan (disisipkan, tanpa
riwayat): K1–K5 di PTA dan K6 di PTB, masing-masing gaji pokok 6.000.000 + tunjangan Transport 500.000, TK0, masuk
1 Jan 2026. K1 = subjek U1/U9/U12, K2 = U2/U11/U14, K3 = U3/U4, K4 = U7/U8, K5 = U5/U6, K6 = pembanding U4 di PT lain.
"Hari ini" dibekukan lewat `services.book_date._sekarang` dan dimajukan sesuai langkah (10 Nov → 15 Des 2026).
Alur (usul, sahkan, proses gaji, masukan, pengaturan) lewat HTTP.

Rantai: U1 → U7a → U5 → U2a → U3 → U6 → U4 → U7b → U8 → U2b → U14; U9–U13 + validasi berdiri sendiri. Bagian lapis A
(migrasi di data acuan, dua pengesahan bersamaan): `backend/tests/test_bp_PYT2_migrasi.py`.
"""
import datetime
import importlib.util
import sys
from pathlib import Path

import pytest

from pembantu import jumlah, pt_uji as _pt_uji

REPO = Path(__file__).resolve().parents[2]
OKT, NOV, DES, SEP = "2026-10", "2026-11", "2026-12", "2026-09"
JAM = {"now": datetime.datetime(2026, 11, 10, 3, 0, tzinfo=datetime.timezone.utc)}   # 10 Nov 2026 10.00 WIB
PT: dict = {}
K: dict = {}
SIMPAN: dict = {}


def _hari(y, m, d):
    JAM["now"] = datetime.datetime(y, m, d, 3, 0, tzinfo=datetime.timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def _hari_ini():
    from services import book_date
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(book_date, "_sekarang", lambda: JAM["now"])
        yield


async def _pt(kode: str) -> str:
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await _pt_uji(kode)
    invalidate_status_cache()
    return eid


@pytest.fixture(scope="module")
async def siap(db):
    """PTA, PTB (BPJS mati) + K1–K6 disisipkan TANPA riwayat (keadaan data sebelum migrasi)."""
    from services import config_resolver as resolver
    if PT:
        return PT
    PT["a"], PT["b"] = await _pt("PYT2A"), await _pt("PYT2B")
    for eid in (PT["a"], PT["b"]):
        for k in ("hr.feature_toggles.bpjs_kesehatan", "hr.feature_toggles.bpjs_ketenagakerjaan"):
            await resolver.set_value(k, False, scope_type="entity", scope_id=eid, actor="uji", reason="uji PY-T2")
    for i in range(1, 7):
        kid = f"emp_pyt2_k{i}"
        K[i] = kid
        await db.hr_employees.insert_one({
            "id": kid, "code": f"EMP-PYT2-{i}", "name": f"K{i} Uji PY-T2", "entity_id": PT["a"] if i < 6 else PT["b"],
            "status": "active", "base_salary": 6_000_000, "allowances": [{"name": "Transport", "amount": 500_000}],
            "ptkp_status": "TK0", "join_date": "2026-01-01", "created_at": "2026-01-01T00:00:00+00:00"})
    return PT


@pytest.fixture(scope="module")
async def adm(sesi):
    simpan = {}

    async def _h(eid):
        if eid not in simpan:
            simpan[eid] = await sesi("admin@kainnusantara.id", entitas=eid)
        return simpan[eid]
    return _h


def _slip(run: dict, emp_id: str) -> dict:
    return next(s for s in run["payslips"] if s["employee_id"] == emp_id)


def _ada(run: dict, emp_id: str) -> bool:
    return any(s["employee_id"] == emp_id for s in run["payslips"])


def _baris(slip: dict) -> list:
    return [(c["label"], c["amount"]) for c in slip.get("components") or []]


async def _run(klien, h, eid, periode):
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": eid, "period": periode}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def _alur(klien, h, run_id, *langkah):
    j = None
    for aksi in langkah:
        r = await klien.post(f"/api/hr/payroll/runs/{run_id}/{aksi}", headers=h)
        assert r.status_code == 200, (aksi, r.text)
        j = r.json()
    return j


async def _usul(klien, h, emp, eff, gaji, **extra):
    r = await klien.post(f"/api/hr/employees/{emp}/compensation", headers=h,
                         json={"effective_from": eff, "base_salary": gaji, "reason": "kenaikan uji PY-T2", **extra})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"
    return r.json()


async def _sahkan(klien, h, row_id, jalur="compensation"):
    r = await klien.post(f"/api/hr/{jalur}/{row_id}/approve", headers=h, json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    return r.json()


def _migrasi():
    spec = importlib.util.spec_from_file_location("migrasi_pyt2", REPO / "scripts/migrate_hr_compensation_py_t2.py")
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    return mig


async def _pratinjau(klien, h, eid, emp):
    r = await klien.post("/api/hr/payroll/runs/preview", json={"entity_id": eid, "period": NOV}, headers=h)
    assert r.status_code == 200, r.text
    return _slip(r.json(), emp)


# ── U1 — migrasi dua kali: satu baris kompensasi + satu penugasan, pratinjau sama ────────────────────────────────────
async def test_PYT2_U1_migrasi_dua_kali(klien, db, adm, siap, capsys):
    h = await adm(PT["a"])
    # sebelum: K1 dibaca dari master → bruto 6.000.000 + 500.000 = 6.500.000
    assert (await _pratinjau(klien, h, PT["a"], K[1]))["gross"] == 6_500_000
    mig = _migrasi()
    assert await mig.jalankan([], db=db) == 0
    out = capsys.readouterr().out
    assert "Mode baca-saja" in out and f"PT {PT['a']}: 5 karyawan tanpa riwayat" in out and "→ SAMA" in out, out
    assert await jumlah("hr_compensation_history", {"employee_id": K[1]}) == 0   # baca-saja tidak menulis
    assert await mig.jalankan(["--apply"], db=db) == 0
    out = capsys.readouterr().out
    assert f"Pratinjau gaji {NOV} PT {PT['a']}" in out and "BEDA" not in out, out
    assert await mig.jalankan(["--apply"], db=db) == 0                          # aman diulang
    assert "Diterapkan: 0 baris kompensasi · 0 baris penugasan" in capsys.readouterr().out
    comp = await db.hr_compensation_history.find({"employee_id": K[1]}, {"_id": 0}).to_list(10)
    asg = await db.hr_employee_assignments.find({"employee_id": K[1]}, {"_id": 0}).to_list(10)
    assert len(comp) == 1 and len(asg) == 1
    assert (comp[0]["effective_from"], comp[0]["status"], comp[0]["source"], comp[0]["base_salary"]) == \
        ("2026-01-01", "approved", "migrasi", 6_000_000)
    assert comp[0]["fixed_components"] == [{"component_code": "TUNJANGAN", "label": "Transport", "amount": 500_000}]
    assert (asg[0]["entity_id"], asg[0]["effective_from"], asg[0]["status"]) == (PT["a"], "2026-01-01", "approved")
    # sesudah: dibaca dari riwayat → bruto tetap 6.500.000, baris slip sama
    s = await _pratinjau(klien, h, PT["a"], K[1])
    assert s["gross"] == 6_500_000
    assert ("Gaji Pokok", 6_000_000) in _baris(s) and ("Tunjangan — Transport", 500_000) in _baris(s)


# ── U7 (a) — pindah PT berlaku 1 Nov, disahkan 10 Nov ────────────────────────────────────────────────────────────────
async def test_PYT2_U7a_pindah_pt_disahkan(klien, db, adm, siap):
    h = await adm(PT["a"])
    r = await klien.post(f"/api/hr/employees/{K[4]}/assignments", headers=h, json={
        "entity_id": PT["b"], "effective_from": "2026-11-01", "reason": "mutasi uji PY-T2"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"
    await _sahkan(klien, h, r.json()["id"], "assignments")
    emp = await db.hr_employees.find_one({"id": K[4]}, {"_id": 0})
    assert emp["entity_id"] == PT["b"]   # hari ini (10 Nov) ≥ 1 Nov → master ikut
    lama = await db.hr_employee_assignments.find_one({"employee_id": K[4], "entity_id": PT["a"]}, {"_id": 0})
    assert lama["effective_to"] == "2026-10-31"


# ── U5 — rapel untuk periode yang sudah diposting ────────────────────────────────────────────────────────────────────
async def test_PYT2_U5_rapel_periode_terposting(klien, db, adm, siap):
    h = await adm(PT["a"])
    for per in (SEP, OKT):
        run = await _run(klien, h, PT["a"], per)
        SIMPAN[f"a:{per}"] = run
        assert ("Gaji Pokok", 6_000_000) in _baris(_slip(run, K[5]))
        assert _ada(run, K[4])   # U7 — K4 masih di PTA pada Sep/Okt walau master sudah PTB
        assert (await _alur(klien, h, run["id"], "submit", "approve", "post-gl"))["status"] == "posted"
    row = await _usul(klien, h, K[5], "2026-09-01", 7_500_000)
    await _sahkan(klien, h, row["id"])
    q = {"employee_id": K[5], "component_code": "RAPEL"}
    inp = await db.hr_pay_inputs.find(q, {"_id": 0}).sort("basis_period", 1).to_list(10)
    # Sep & Okt: nilai baru 7.500.000 + 500.000 − dibayar 6.000.000 + 500.000 = 1.500.000 per periode
    assert [(i["status"], i["pay_period"], i["amount"], i["label"], i["source_type"], i["entity_id"]) for i in inp] == [
        ("pending", NOV, 1_500_000, "Rapel gaji September 2026", "rapel", PT["a"]),
        ("pending", NOV, 1_500_000, "Rapel gaji Oktober 2026", "rapel", PT["a"])]
    assert [i["source_key"] for i in inp] == [f"rapel:{row['id']}:{SEP}", f"rapel:{row['id']}:{OKT}"]
    r = await klien.post(f"/api/hr/compensation/{row['id']}/approve", headers=h, json={})
    assert r.status_code == 409, r.text
    assert await jumlah("hr_pay_inputs", q) == 2   # pengulangan tidak menambah masukan
    SIMPAN["rapel"] = [i["id"] for i in inp]


# ── U2 (a) — kenaikan berlaku 1 Des disahkan pada November: master belum berubah ─────────────────────────────────────
async def test_PYT2_U2a_kenaikan_desember_master_tetap(klien, db, adm, siap):
    h = await adm(PT["a"])
    row = await _usul(klien, h, K[2], "2026-12-01", 7_500_000)
    await _sahkan(klien, h, row["id"])
    SIMPAN["u2_row"] = row["id"]
    assert (await db.hr_employees.find_one({"id": K[2]}, {"_id": 0}))["base_salary"] == 6_000_000


# ── U3 — kenaikan 16 Nov, aturan bawaan: satu baris bernilai akhir bulan ─────────────────────────────────────────────
async def test_PYT2_U3_tanpa_prorata_nilai_akhir_bulan(klien, db, adm, siap):
    h = await adm(PT["a"])
    row = await _usul(klien, h, K[3], "2026-11-16", 7_500_000)
    await _sahkan(klien, h, row["id"])
    run = await _run(klien, h, PT["a"], NOV)
    SIMPAN["a:nov"] = run
    s3 = _slip(run, K[3])
    assert [b for b in _baris(s3) if b[0].startswith("Gaji Pokok")] == [("Gaji Pokok", 7_500_000)]
    assert ("Tunjangan — Transport", 500_000) in _baris(s3)   # tunjangan ikut tersalin ke baris baru
    assert ("Gaji Pokok", 6_000_000) in _baris(_slip(run, K[2]))   # U2 — November 6.000.000
    assert not _ada(run, K[4])                                        # U7 — November bukan PTA


# ── U6 — dua masukan rapel disahkan → ikut proses reguler November ───────────────────────────────────────────────────
async def test_PYT2_U6_rapel_ikut_proses_november(klien, db, adm, siap):
    h = await adm(PT["a"])
    for iid in SIMPAN["rapel"]:
        r = await klien.post(f"/api/hr/payroll/inputs/{iid}/approve", headers=h)
        assert r.status_code == 200, r.text
    run = await _alur(klien, h, SIMPAN["a:nov"]["id"], "recalculate")
    s5 = _slip(run, K[5])
    assert ("Rapel gaji September 2026", 1_500_000) in _baris(s5)
    assert ("Rapel gaji Oktober 2026", 1_500_000) in _baris(s5)
    assert s5["other_earnings"] == 3_000_000
    assert ("Gaji Pokok", 7_500_000) in _baris(s5)


# ── U4 — prorata hari kalender untuk PTA saja ─────────────────────────────────────────────────────────────────────────
async def test_PYT2_U4_prorata_hari_kalender_per_pt(klien, db, adm, siap):
    from services import config_resolver as resolver
    h = await adm(PT["a"])
    await resolver.set_value("hr.prorata_perubahan_gaji", "hari_kalender", scope_type="entity", scope_id=PT["a"],
                             actor="uji", reason="uji PY-T2 U4")
    try:
        run = await _alur(klien, h, SIMPAN["a:nov"]["id"], "recalculate")
        s3 = _slip(run, K[3])
        # 6.000.000 × 15 ÷ 30 = 3.000.000; 7.500.000 × 15 ÷ 30 = 3.750.000; tunjangan 500.000 × 15 ÷ 30 = 250.000 ×2
        assert [b for b in _baris(s3) if b[0].startswith("Gaji Pokok")] == [
            ("Gaji Pokok (1–15 Nov)", 3_000_000), ("Gaji Pokok (16–30 Nov)", 3_750_000)]
        assert [b for b in _baris(s3) if b[0].startswith("Tunjangan")] == [
            ("Tunjangan — Transport (1–15 Nov)", 250_000), ("Tunjangan — Transport (16–30 Nov)", 250_000)]
        assert s3["base_salary"] == 6_750_000 and s3["allowances"] == 500_000
        assert [b for b in _baris(_slip(run, K[1])) if b[0].startswith("Gaji Pokok")] == [("Gaji Pokok", 6_000_000)]
        # PT lain (PTB, aturan bawaan): kenaikan 16 Nov K6 → satu baris 7.500.000
        hb = await adm(PT["b"])
        row = await _usul(klien, hb, K[6], "2026-11-16", 7_500_000)
        await _sahkan(klien, hb, row["id"])
        runb = await _run(klien, hb, PT["b"], NOV)
        SIMPAN["b:nov"] = runb
        assert [b for b in _baris(_slip(runb, K[6])) if b[0].startswith("Gaji Pokok")] == [("Gaji Pokok", 7_500_000)]
        assert await resolver.value_of("hr.prorata_perubahan_gaji", {"entity_id": PT["b"]}) == "mati"
    finally:
        await resolver.set_value("hr.prorata_perubahan_gaji", "mati", scope_type="entity", scope_id=PT["a"],
                                 actor="uji", reason="pulihkan uji PY-T2 U4")


# ── U7 (b) — Oktober hanya PTA, November hanya PTB ───────────────────────────────────────────────────────────────────
async def test_PYT2_U7b_pindah_pt_per_periode(klien, db, adm, siap):
    hb = await adm(PT["b"])
    okt_b = await _run(klien, hb, PT["b"], OKT)
    assert not _ada(okt_b, K[4]) and _ada(SIMPAN[f"a:{OKT}"], K[4])
    assert _ada(SIMPAN["b:nov"], K[4]) and not _ada(SIMPAN["a:nov"], K[4])
    assert ("Gaji Pokok", 6_000_000) in _baris(_slip(SIMPAN["b:nov"], K[4]))


# ── U8 — hitung ulang pajak tahunan per PT ────────────────────────────────────────────────────────────────────────────
async def test_PYT2_U8_pajak_tahunan_per_pt(klien, db, adm, siap):
    # fixture: slip K4 Jan–Agu di PTA (disisipkan); Sep–Okt di PTA (proses U5); Nov di PTB (U4)
    await db.hr_payslips.insert_many([
        {"id": f"slip_pyt2_k4_{m:02d}", "run_id": "prun_pyt2_fixture", "entity_id": PT["a"], "employee_id": K[4],
         "period": f"2026-{m:02d}", "gross": 6_500_000, "tax_gross": 6_500_000, "pph21": 0.0,
         "bpjs_emp": {"kesehatan": 0, "jht": 0, "jp": 0}} for m in range(1, 9)])
    _hari(2026, 12, 15)
    hb = await adm(PT["b"])
    run = await _run(klien, hb, PT["b"], DES)
    s4 = _slip(run, K[4])
    ann = s4["pph21_annual"]
    assert ann["months"] == 2   # November + Desember di PTB; 10 slip PTA tidak ikut
    nov_b = _slip(SIMPAN["b:nov"], K[4])
    assert ann["prior_withheld"] == nov_b["pph21"]
    assert ann["tax_gross"] == 6_500_000 * 2


# ── U2 (b) — Desember membaca 7.500.000; master ikut sesudah apply_effective ─────────────────────────────────────────
async def test_PYT2_U2b_desember_dan_apply_effective(klien, db, adm, siap):
    from services import hr_compensation_service as hc
    h = await adm(PT["a"])
    run = await _run(klien, h, PT["a"], DES)
    assert ("Gaji Pokok", 7_500_000) in _baris(_slip(run, K[2]))
    assert (await db.hr_employees.find_one({"id": K[2]}, {"_id": 0}))["base_salary"] == 6_000_000
    assert await hc.apply_effective("2026-12-01") >= 1
    assert (await db.hr_employees.find_one({"id": K[2]}, {"_id": 0}))["base_salary"] == 7_500_000


# ── U14 — INV-PY-2 ────────────────────────────────────────────────────────────────────────────────────────────────────
async def test_PYT2_U14_invarian_master_turunan(db, siap, capsys):
    from services import hr_compensation_service as hc
    sys.path.insert(0, str(REPO / "scripts"))
    vdi = importlib.import_module("verify_data_integrity")
    await hc.apply_effective()
    awal = vdi.results["fail"]
    await vdi.layer_hr_compensation_invariants(db)
    out = capsys.readouterr().out
    assert vdi.results["fail"] == awal and "[PASS]" in out and "INV-PY-2" in out, out
    await db.hr_employees.update_one({"id": K[2]}, {"$set": {"base_salary": 9_999_000}})
    try:
        await vdi.layer_hr_compensation_invariants(db)
        out = capsys.readouterr().out
        assert vdi.results["fail"] == awal + 1 and K[2] in out and "base_salary" in out, out
    finally:
        vdi.results["fail"] = awal
        assert await hc.apply_effective() == 1


# ── U9 — PATCH master ditolak; karyawan baru mendapat baris pertama ─────────────────────────────────────────────────
async def test_PYT2_U9_patch_ditolak_post_baris_pertama(klien, db, adm, siap):
    h = await adm(PT["a"])
    pesan = "Gaji dan penugasan PT diubah lewat Riwayat Kompensasi di kartu karyawan."
    for data in ({"base_salary": 7_000_000}, {"allowances": []}, {"entity_id": PT["b"]}):
        r = await klien.patch(f"/api/hr/employees/{K[1]}", headers=h, json={"data": data})
        assert r.status_code == 400 and r.json()["detail"] == pesan, (data, r.text)
    r = await klien.patch(f"/api/hr/employees/{K[1]}", headers=h, json={"data": {"phone": "081200000001"}})
    assert r.status_code == 200, r.text
    r = await klien.post("/api/hr/employees", headers=h, json={
        "name": "Karyawan Baru PY-T2", "base_salary": 5_000_000, "entity_id": PT["a"], "join_date": "2026-12-01",
        "allowances": [{"name": "Makan", "amount": 300_000}]})
    assert r.status_code == 200, r.text
    eid = r.json()["id"]
    comp = await db.hr_compensation_history.find({"employee_id": eid}, {"_id": 0}).to_list(5)
    asg = await db.hr_employee_assignments.find({"employee_id": eid}, {"_id": 0}).to_list(5)
    assert [(c["status"], c["base_salary"], c["effective_from"]) for c in comp] == [("approved", 5_000_000, "2026-12-01")]
    assert comp[0]["fixed_components"] == [{"component_code": "TUNJANGAN", "label": "Makan", "amount": 300_000}]
    assert [(a["status"], a["entity_id"]) for a in asg] == [("approved", PT["a"])]


# ── U10 — izin: lihat butuh hr.view_pii; sahkan butuh payroll.approve ───────────────────────────────────────────────
async def test_PYT2_U10_izin(klien, akun, sesi, siap, peran_tanpa_acuan):
    r1 = await peran_tanpa_acuan({"hr": ["view"]}, label="SDM Lihat PY-T2")
    h1 = await sesi(await akun(r1, entitas=(PT["a"],)), entitas=PT["a"])
    r = await klien.get(f"/api/hr/employees/{K[1]}/compensation", headers=h1)
    assert r.status_code == 403, r.text
    assert "Anda belum punya akses untuk" in r.json()["detail"] and "view_pii" not in r.json()["detail"]
    r2 = await peran_tanpa_acuan({"hr": ["view", "view_pii", "update"]}, label="SDM Ubah PY-T2")
    h2 = await sesi(await akun(r2, entitas=(PT["a"],)), entitas=PT["a"])
    r = await klien.get(f"/api/hr/employees/{K[1]}/compensation", headers=h2)
    assert r.status_code == 200, r.text
    row = await _usul(klien, h2, K[1], "2027-01-01", 6_200_000)
    r = await klien.post(f"/api/hr/compensation/{row['id']}/approve", headers=h2, json={})
    assert r.status_code == 403, r.text


# ── U11 — tanggal berlaku sama dengan baris yang sudah sah → 409 ─────────────────────────────────────────────────────
async def test_PYT2_U11_tanggal_kembar_409(klien, db, adm, siap):
    h = await adm(PT["a"])
    row = await _usul(klien, h, K[2], "2026-12-01", 8_000_000)
    r = await klien.post(f"/api/hr/compensation/{row['id']}/approve", headers=h, json={})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "Sudah ada perubahan kompensasi yang berlaku 2026-12-01 untuk karyawan ini."
    assert await jumlah("hr_compensation_history", {"employee_id": K[2], "effective_from": "2026-12-01",
                                                    "status": "approved"}) == 1


# ── U12 — PT tujuan di luar cakupan pelaku → 403 ─────────────────────────────────────────────────────────────────────
async def test_PYT2_U12_pt_tujuan_di_luar_cakupan(klien, akun, sesi, siap, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"hr": ["view", "update"]}, label="SDM PTA saja PY-T2")
    h = await sesi(await akun(rid, entitas=(PT["a"],)), entitas=PT["a"])
    r = await klien.post(f"/api/hr/employees/{K[1]}/assignments", headers=h, json={
        "entity_id": PT["b"], "effective_from": "2027-01-01", "reason": "mutasi uji PY-T2"})
    assert r.status_code == 403, r.text
    # pagar tulis PT bersama (isi `entity_id` di luar penugasan) menjawab lebih dulu; tanpa pagar itu, router ini
    # menjawab "Anda belum punya akses ke PT tujuan…"
    assert "PT Uji PYT2B" in r.json()["detail"] or "PT tujuan" in r.json()["detail"], r.text
    assert await jumlah("hr_employee_assignments", {"employee_id": K[1], "entity_id": PT["b"]}) == 0


# ── U13 — kunci pengaturan baru ──────────────────────────────────────────────────────────────────────────────────────
async def test_PYT2_U13_kunci_prorata(klien, kepala_admin):
    import config_registry as registry
    from test_KFT8_putaran_pengaturan import putaran
    e = registry.require("hr.prorata_perubahan_gaji")
    assert (e["type"], e["default"], e["scopes"], e["permission"], e["risk"], e["requires_reason"], e["group"]) == (
        "enum", "mati", ["global", "entity"], ["hr", "manage_payroll"], "high", True, "sdm")
    assert [o["value"] for o in e["options"]] == ["mati", "hari_kalender"]
    assert "services/hr_compensation_service.py:segments" in e["consumers"]
    gagal = await putaran(klien, kepala_admin, "hr.prorata_perubahan_gaji")
    assert not gagal, "\n".join(gagal)
    r = await klien.put("/api/config/values", headers=kepala_admin, json={
        "key": "hr.prorata_perubahan_gaji", "value": "harian", "scope_type": "global", "scope_id": "",
        "reason": "uji nilai tak sah PY-T2"})
    assert r.status_code == 400, r.text


# ── tambahan — pesan galat usulan, tolak/batal, riwayat untuk layar, tugas terjadwal ────────────────────────────────
async def test_PYT2_validasi_usulan_dan_keputusan(klien, db, adm, siap):
    h = await adm(PT["a"])
    url = f"/api/hr/employees/{K[1]}/compensation"
    for tgl in ("2026-13-01", "16/11/2026", ""):
        r = await klien.post(url, headers=h, json={"effective_from": tgl, "base_salary": 1, "reason": "uji"})
        assert r.status_code == 400 and r.json()["detail"] == "Tanggal berlaku harus berbentuk TTTT-BB-HH.", r.text
    r = await klien.post(url, headers=h, json={"effective_from": "2027-02-01", "base_salary": 7_000_000, "reason": "uji",
                                               "fixed_components": [{"component_code": "LEMBUR", "amount": 1}]})
    assert r.status_code == 400 and r.json()["detail"] == "Komponen LEMBUR bukan komponen tetap bulanan di PT ini."
    r = await klien.post(url, headers=h, json={"effective_from": "2027-02-01", "base_salary": 7_000_000, "reason": " "})
    assert r.status_code == 400 and r.json()["detail"] == "Alasan wajib diisi.", r.text
    # baris yang sudah sah tidak bisa ditolak/dibatalkan; baris menunggu bisa
    sah = await db.hr_compensation_history.find_one({"employee_id": K[1], "status": "approved"}, {"_id": 0})
    for aksi in ("reject", "cancel"):
        r = await klien.post(f"/api/hr/compensation/{sah['id']}/{aksi}", headers=h, json={})
        assert r.status_code == 409 and r.json()["detail"] == (
            "Baris yang sudah disahkan tidak bisa diubah. Buat baris baru dengan tanggal berlaku baru."), r.text
    row = await _usul(klien, h, K[1], "2027-03-01", 6_300_000, fixed_components=[])
    assert row["fixed_components"] == []
    r = await klien.post(f"/api/hr/compensation/{row['id']}/reject", headers=h, json={"reason": "belum disetujui"})
    assert r.status_code == 200 and r.json()["status"] == "rejected", r.text
    r = await klien.post(f"/api/hr/compensation/{row['id']}/approve", headers=h, json={})
    assert r.status_code == 409 and "Ditolak" in r.json()["detail"], r.text
    # riwayat untuk kartu karyawan: semua status, PT pada tanggal berlaku, pilihan komponen tetap
    j = (await klien.get(url, headers=h)).json()
    assert {c["status"] for c in j["compensation"]} >= {"approved", "pending", "rejected"}
    assert all(c["entity_id"] == PT["a"] for c in j["compensation"])
    assert {"code": "TUNJANGAN", "name": "Tunjangan"} in j["fixed_component_options"]
    assert not [o for o in j["fixed_component_options"] if o["code"] == "GAJI_POKOK"]
    # tugas terjadwal harian 00.10 WIB
    from services import hr_compensation_service as hc
    from services.scheduler_service import JOB_MAP
    job = JOB_MAP["hr_compensation_effective"]
    assert (job["kind"], job["hour"], job["minute"]) == ("daily", 0, 10)
    assert (await job["fn"]())["date"] == hc.today()

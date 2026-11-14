"""PY-T1 — slip gaji sebagai daftar komponen per PT, antrean masukan, dan jenis proses gaji (docs/blueprint/unit/PY-T1.md).

Persiapan bersama (fixture, disisipkan langsung): "hari ini" dibekukan 15 Des 2026 (`services.book_date._sekarang`);
BPJS dimatikan untuk PT uji (`hr.feature_toggles.bpjs_kesehatan` dan `…bpjs_ketenagakerjaan` = tidak, lapisan PT), jadi
bruto pajak = bruto. Karyawan (disisipkan): E1 gaji pokok 8.000.000 + tunjangan Transport 500.000 dan Makan 300.000, TK0;
E2 gaji pokok 5.000.000, TK0. Alur (komponen, masukan, proses, ajukan/sahkan/posting/anulir, rekap pajak, absen) lewat
HTTP.

Tarif PPh 21 diambil lewat `ter_rate` (tabel bawaan kategori A pada `3132cc4`: 8.800.000 → 1,75 %; 13.800.000 → 4,5 %;
16.800.000 → 5 %; 5.000.000 → 0 %), supaya uji tetap benar bila PK-46 mengganti tabel; hitungan tangan di komentar.

Rantai `ent_kanda` Oktober: U1 → U12 → U14 → U4 → U5 → U13. Rantai `ent_kanda` November: U3 → U6. U7, U8, U10 memakai PT
uji tersendiri (`pt_uji`) supaya aturan "satu proses reguler per PT per periode" tidak saling mengganggu. U2 (data acuan)
dan U14 bagian bersamaan: `backend/tests/test_bp_PYT1_data_acuan.py` (lapis A).
"""
import datetime

import pytest

from pembantu import jumlah, pt_uji as _pt_uji

KANDA = "ent_kanda"
OKT, NOV, DES = "2026-10", "2026-11", "2026-12"
HARI_INI = datetime.datetime(2026, 12, 15, 3, 0, tzinfo=datetime.timezone.utc)   # 15 Des 2026 10.00 WIB
SIMPAN: dict = {}
TUNDA_B = "PY-01 — serah-terima (b): kolom lama slip diturunkan dari komponen, masukan ikut proses, jenis proses"


async def pt_uji(kode: str) -> str:
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await _pt_uji(kode)
    invalidate_status_cache()
    return eid


@pytest.fixture(scope="module", autouse=True)
def _hari_ini():
    from services import book_date
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(book_date, "_sekarang", lambda: HARI_INI)
        yield


async def _siapkan_pt(db, eid: str, awalan: str) -> dict:
    """BPJS mati untuk PT itu (lapisan PT) + E1 dan E2 (disisipkan)."""
    from services import config_resolver as resolver
    for k in ("hr.feature_toggles.bpjs_kesehatan", "hr.feature_toggles.bpjs_ketenagakerjaan"):
        await resolver.set_value(k, False, scope_type="entity", scope_id=eid, actor="uji", reason="uji PY-T1")
    e1, e2 = f"{awalan}_e1", f"{awalan}_e2"
    for eid_emp, nama, gaji, tunj in ((e1, "E1 Uji", 8_000_000, [{"name": "Transport", "amount": 500_000},
                                                                 {"name": "Makan", "amount": 300_000}]),
                                      (e2, "E2 Uji", 5_000_000, [])):
        if not await db.hr_employees.find_one({"id": eid_emp}):
            await db.hr_employees.insert_one({
                "id": eid_emp, "name": f"{nama} {eid}", "entity_id": eid, "status": "active", "base_salary": gaji,
                "allowances": tunj, "ptkp_status": "TK0", "created_at": "2026-01-01T00:00:00+00:00"})
    # PT uji hanya berisi E1 & E2 (karyawan lain PT itu, bila ada dari seed, dinonaktifkan supaya total proses = E1 + E2).
    await db.hr_employees.update_many({"entity_id": eid, "id": {"$nin": [e1, e2]}}, {"$set": {"status": "inactive"}})
    return {"e1": e1, "e2": e2}


@pytest.fixture(scope="module")
async def kanda(db):
    return await _siapkan_pt(db, KANDA, "emp_pyt1_kanda")


@pytest.fixture(scope="module")
async def adm(sesi):
    simpan = {}

    async def _h(eid=KANDA):
        if eid not in simpan:
            simpan[eid] = await sesi("admin@kainnusantara.id", entitas=eid)
        return simpan[eid]
    return _h


async def _tarif(bruto: float) -> float:
    from services import hr_payroll_service as pay
    return pay.ter_rate("A", bruto, await pay.aturan_pph21("2026-10-31"))


def _slip(run: dict, emp_id: str) -> dict:
    return next(s for s in run["payslips"] if s["employee_id"] == emp_id)


def _baris(slip: dict) -> list:
    return [(c["label"], c["amount"]) for c in slip.get("components") or []]


async def _masukan(klien, h, emp, kode, periode, nominal, label, *, sahkan=True):
    r = await klien.post("/api/hr/payroll/inputs", headers=h, json={
        "employee_id": emp, "component_code": kode, "pay_period": periode, "amount": nominal, "label": label,
        "reason": "isian uji PY-T1"})
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["status"] == "pending"
    if sahkan:
        r = await klien.post(f"/api/hr/payroll/inputs/{doc['id']}/approve", headers=h)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["status"] == "approved"
    return doc


async def _alur(klien, h, run_id, *langkah):
    j = None
    for aksi in langkah:
        r = await klien.post(f"/api/hr/payroll/runs/{run_id}/{aksi}", headers=h)
        assert r.status_code == 200, (aksi, r.text)
        j = r.json()
    return j


async def _jurnal(db, source_type, source_id):
    return await db.journal_entries.find({"source_type": source_type, "source_id": source_id,
                                          "status": {"$ne": "void"}}, {"_id": 0}).to_list(20)


def _jlines(je):
    return sorted((ln["account_code"], round(ln["debit"], 2), round(ln["credit"], 2)) for ln in je["lines"])


async def _saldo(db, eid, kode, dari, sampai):
    tot = 0.0
    async for je in db.journal_entries.find({"entity_id": eid, "status": {"$ne": "void"},
                                             "date": {"$gte": dari, "$lte": sampai}}, {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == kode:
                tot += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return round(tot, 2)


# ── U1 — proses reguler: komponen per baris, kolom lama tetap ────────────────────────────────────────────────────────
async def test_PYT1_U1_proses_reguler_komponen_dan_kolom_lama(klien, db, adm, kanda):
    from services import hr_pay_components as pc
    h = await adm()
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KANDA, "period": OKT}, headers=h)
    assert r.status_code == 200, r.text
    run = r.json()
    SIMPAN["u1"] = run
    e1, e2 = _slip(run, kanda["e1"]), _slip(run, kanda["e2"])
    tarif = await _tarif(8_800_000)
    # E1: bruto = 8.000.000 + 500.000 + 300.000 = 8.800.000; PPh 21 = 8.800.000 × 1,75 % = 154.000;
    # bersih = 8.800.000 − 154.000 = 8.646.000.
    pph = round(8_800_000 * tarif, 2)
    assert pph == 154_000
    baris = _baris(e1)
    for b in (("Gaji Pokok", 8_000_000), ("Tunjangan — Transport", 500_000), ("Tunjangan — Makan", 300_000),
              ("PPh 21", pph)):
        assert b in baris, (b, baris)
    assert not [c for c in e1["components"] if c["code"].startswith("BPJS")]   # BPJS mati untuk PT ini
    assert (e1["base_salary"], e1["allowances"], e1["gross"], e1["net"]) == (8_000_000, 800_000, 8_800_000, 8_646_000)
    assert pc.components_match_columns(e1) == []
    # E2: bruto 5.000.000 → tarif 0 % → PPh 21 0, bersih 5.000.000.
    assert (e2["pph21"], e2["net"]) == (0, 5_000_000)
    assert ("PPh 21", 0) in _baris(e2) and pc.components_match_columns(e2) == []


# ── U12 — baris PDF dari komponen ─────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.xfail(strict=True, reason=TUNDA_B)
async def test_PYT1_U12_baris_pdf_dari_komponen(kanda):
    from services import hr_payroll_pdf as pdf
    slip = _slip(SIMPAN["u1"], kanda["e1"])
    rows = pdf.payslip_pdf_rows(slip)
    assert ("PENERIMAAN", "Tunjangan — Transport", 500_000) in rows
    assert not [r for r in rows if "(1%)" in r[1]]
    bagian = [r[0] for r in rows]
    for b in ("PENERIMAAN", "POTONGAN", "GAJI BERSIH DITERIMA"):
        assert b in bagian
    assert ("GAJI BERSIH DITERIMA", "Gaji bersih diterima", 8_646_000) in rows
    assert pdf.payslip_pdf_bytes(slip, "PT Uji")[:4] == b"%PDF"


# ── U14 (lapis B) — permintaan kedua proses reguler mengembalikan proses yang sama ──────────────────────────────────
@pytest.mark.xfail(strict=True, reason=TUNDA_B)
async def test_PYT1_U14_reguler_kedua_proses_sama(klien, db, adm, kanda):
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KANDA, "period": OKT, "run_type": "regular"},
                         headers=await adm())
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["id"] == SIMPAN["u1"]["id"]
    assert j["run_type"] == "regular" and j["seq"] == 1 and j["active_key"] == f"{KANDA}:{OKT}:regular"
    assert await jumlah("hr_payroll_runs", {"entity_id": KANDA, "period": OKT, "run_type": "regular"}) == 1


# ── U4 — proses THR: PPh 21 gabungan bulan ────────────────────────────────────────────────────────────────────────────
@pytest.mark.xfail(strict=True, reason=TUNDA_B)
async def test_PYT1_U4_proses_thr_pph21_gabungan_bulan(klien, db, adm, kanda):
    h = await adm()
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KANDA, "period": OKT, "run_type": "thr"},
                         headers=h)
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Tidak ada masukan THR yang disahkan untuk Oktober 2026."
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KANDA, "period": OKT, "run_type": "susulan"},
                         headers=h)
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Tidak ada masukan yang belum terpakai untuk Oktober 2026."
    await _masukan(klien, h, kanda["e1"], "THR", OKT, 8_000_000, "THR 2026")
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KANDA, "period": OKT, "run_type": "thr"},
                         headers=h)
    assert r.status_code == 200, r.text
    run = r.json()
    SIMPAN["u4"] = run
    assert run["id"] != SIMPAN["u1"]["id"] and run["run_type"] == "thr" and run["seq"] == 1
    assert not run.get("active_key")
    assert [s["employee_id"] for s in run["payslips"]] == [kanda["e1"]]
    s = run["payslips"][0]
    assert ("THR 2026", 8_000_000) in _baris(s)
    tarif = await _tarif(16_800_000)
    # Bruto pajak bulan = 8.000.000 (THR) + 8.800.000 (slip reguler U1) = 16.800.000 → 5 %:
    # PPh 21 bulan = 16.800.000 × 5 % = 840.000; slip ini = 840.000 − 154.000 (sudah dipotong di U1) = 686.000;
    # bersih = 8.000.000 − 686.000 = 7.314.000.
    assert round(16_800_000 * tarif, 2) == 840_000
    assert s["pph21_month"] == 840_000 and s["pph21"] == 686_000 and s["net"] == 7_314_000
    assert s["tax_gross"] == 8_000_000 and s["other_earnings"] == 8_000_000


# ── U5 — posting THR: jurnal per proses ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.xfail(strict=True, reason=TUNDA_B)
async def test_PYT1_U5_posting_thr_jurnal_sendiri(klien, db, adm, kanda):
    h = await adm()
    thr = SIMPAN["u4"]
    j = await _alur(klien, h, thr["id"], "submit", "approve", "post-gl")
    assert j["status"] == "posted", j
    jes = await _jurnal(db, "payroll_run", thr["id"])
    assert len(jes) == 1
    # Dr 6-1000 8.000.000 = Cr 2-1600 7.314.000 + Cr 2-1800 686.000.
    assert _jlines(jes[0]) == [("2-1600", 0, 7_314_000), ("2-1800", 0, 686_000), ("6-1000", 8_000_000, 0)]
    reg = SIMPAN["u1"]
    j = await _alur(klien, h, reg["id"], "submit", "approve", "post-gl")
    assert j["status"] == "posted"
    jreg = await _jurnal(db, "payroll_run", reg["id"])
    assert len(jreg) == 1
    # Reguler: Dr 6-1000 13.800.000 = Cr 2-1600 (8.646.000 + 5.000.000) 13.646.000 + Cr 2-1800 154.000.
    assert _jlines(jreg[0]) == [("2-1600", 0, 13_646_000), ("2-1800", 0, 154_000), ("6-1000", 13_800_000, 0)]
    # Saldo Oktober PT: 2-1600 = −(13.646.000 + 7.314.000) = −20.960.000; 2-1800 = −(154.000 + 686.000) = −840.000.
    assert await _saldo(db, KANDA, "2-1600", "2026-10-01", "2026-10-31") == -20_960_000
    assert await _saldo(db, KANDA, "2-1800", "2026-10-01", "2026-10-31") == -840_000


# ── U13 — rekap PPh 21 periode memuat kedua proses ───────────────────────────────────────────────────────────────────
@pytest.mark.xfail(strict=True, reason=TUNDA_B)
async def test_PYT1_U13_rekap_pph21_dua_proses(klien, adm, kanda):
    r = await klien.get("/api/tax/summary", params={"period": OKT, "entity_id": KANDA}, headers=await adm())
    assert r.status_code == 200, r.text
    b = next(it for it in r.json()["pph"]["items"] if it["basis"] == "payroll")
    # dpp = 8.800.000 + 5.000.000 + 8.000.000 = 21.800.000; amount = 154.000 + 0 + 686.000 = 840.000.
    assert (b["dpp"], b["amount"], b["gl_amount"], b["count"]) == (21_800_000, 840_000, 840_000, 2)


# ── U3 — dua masukan bonus = dua baris; masukan terpakai ─────────────────────────────────────────────────────────────
@pytest.mark.xfail(strict=True, reason=TUNDA_B)
async def test_PYT1_U3_dua_bonus_dua_baris(klien, db, adm, kanda):
    h = await adm()
    r = await klien.post("/api/hr/payroll/components", headers=h, json={
        "code": "BONUS", "name": "Bonus", "kind": "pendapatan", "calc": "masukan", "bucket": "other_earnings"})
    assert r.status_code == 200, r.text
    a = await _masukan(klien, h, kanda["e1"], "BONUS", NOV, 2_000_000, "Bonus A")
    b = await _masukan(klien, h, kanda["e1"], "BONUS", NOV, 3_000_000, "Bonus B")
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KANDA, "period": NOV}, headers=h)
    assert r.status_code == 200, r.text
    run = r.json()
    SIMPAN["u3"] = run
    s = _slip(run, kanda["e1"])
    assert ("Bonus A", 2_000_000) in _baris(s) and ("Bonus B", 3_000_000) in _baris(s)
    tarif = await _tarif(13_800_000)
    # bruto = 8.800.000 + 2.000.000 + 3.000.000 = 13.800.000 → 4,5 %: PPh 21 = 621.000; bersih = 13.179.000.
    assert round(13_800_000 * tarif, 2) == 621_000
    assert (s["other_earnings"], s["gross"], s["pph21"], s["net"]) == (5_000_000, 13_800_000, 621_000, 13_179_000)
    for inp in (a, b):
        d = await db.hr_pay_inputs.find_one({"id": inp["id"]})
        assert d["status"] == "used" and d["used_run_id"] == run["id"]


# ── U6 — anulir melepas masukan ──────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.xfail(strict=True, reason=TUNDA_B)
async def test_PYT1_U6_anulir_melepas_masukan(klien, db, adm, kanda):
    h = await adm()
    run = SIMPAN["u3"]
    await _alur(klien, h, run["id"], "submit", "approve", "post-gl")
    assert await jumlah("hr_pay_inputs", {"used_run_id": run["id"], "status": "used"}) == 2
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/void", json={"reason": "bonus salah periode"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "void" and not r.json().get("active_key")
    rows = await db.hr_pay_inputs.find({"entity_id": KANDA, "pay_period": NOV, "component_code": "BONUS"}).to_list(10)
    assert len(rows) == 2 and {(d["status"], d["used_run_id"]) for d in rows} == {("approved", "")}


# ── U7 — hitung ulang mengikuti antrean ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.xfail(strict=True, reason=TUNDA_B)
async def test_PYT1_U7_hitung_ulang_mengikuti_antrean(klien, db, adm):
    eid = await pt_uji("PYT7")
    e = await _siapkan_pt(db, eid, "emp_pyt1_u7")
    h = await adm(eid)
    r = await klien.post("/api/hr/payroll/components", headers=h, json={
        "code": "BONUS", "name": "Bonus", "kind": "pendapatan"})
    assert r.status_code == 200, r.text
    run = (await klien.post("/api/hr/payroll/runs", json={"entity_id": eid, "period": DES}, headers=h)).json()
    awal = run["totals"]["gross"]
    inp = await _masukan(klien, h, e["e2"], "BONUS", DES, 1_000_000, "Bonus akhir tahun")
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/recalculate", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert ("Bonus akhir tahun", 1_000_000) in _baris(_slip(j, e["e2"]))
    assert j["totals"]["gross"] == awal + 1_000_000
    # Masukan dibatalkan selagi prosesnya masih draf: boleh; proses ditandai perlu dihitung ulang (ajukan ditolak).
    r = await klien.post(f"/api/hr/payroll/inputs/{inp['id']}/cancel", json={"reason": "bonus batal diberikan"},
                         headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/submit", headers=h)
    assert r.status_code == 409, r.text
    assert "hitung ulang" in r.json()["detail"]
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/recalculate", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert ("Bonus akhir tahun", 1_000_000) not in _baris(_slip(j, e["e2"]))
    assert j["totals"]["gross"] == awal and not j.get("inputs_stale_at")


# ── U8 — masukan manual: pending tidak ikut; sesudah disahkan ikut; terpakai di proses yang diajukan → 409 ─────────
@pytest.mark.xfail(strict=True, reason=TUNDA_B)
async def test_PYT1_U8_masukan_manual(klien, db, adm, akun, sesi, peran_tanpa_acuan):
    eid = await pt_uji("PYT8")
    e = await _siapkan_pt(db, eid, "emp_pyt1_u8")
    h = await adm(eid)
    r = await klien.post("/api/hr/payroll/components", headers=h, json={
        "code": "BONUS", "name": "Bonus", "kind": "pendapatan"})
    assert r.status_code == 200, r.text
    rid = await peran_tanpa_acuan({"payroll": ["create"], "hr": ["view"]}, label="Penyiap Gaji U8")
    hp = await sesi(await akun(rid, entitas=(eid,)), entitas=eid)
    inp = await _masukan(klien, hp, e["e1"], "BONUS", NOV, 750_000, "Bonus proyek", sahkan=False)
    run = (await klien.post("/api/hr/payroll/runs", json={"entity_id": eid, "period": NOV}, headers=h)).json()
    assert ("Bonus proyek", 750_000) not in _baris(_slip(run, e["e1"]))
    r = await klien.post(f"/api/hr/payroll/inputs/{inp['id']}/approve", headers=h)
    assert r.status_code == 200, r.text
    j = await _alur(klien, h, run["id"], "recalculate")
    assert ("Bonus proyek", 750_000) in _baris(_slip(j, e["e1"]))
    await _alur(klien, h, run["id"], "submit")
    r = await klien.post(f"/api/hr/payroll/inputs/{inp['id']}/cancel", json={"reason": "salah orang"}, headers=h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == f"Masukan ini sudah dipakai di penggajian {run['number']}, jadi tidak bisa dibatalkan."


# ── U9 — kirim ulang kunci sumber yang sama ──────────────────────────────────────────────────────────────────────────
async def test_PYT1_U9_kunci_sumber_sama_satu_dokumen(db, kanda):
    from services import hr_pay_inputs as qi
    arg = dict(entity_id=KANDA, employee_id=kanda["e2"], pay_period="2027-01", component_code="THR", label="Rapel",
               amount=250_000, source_type="rapel", source_key="rapel:uji:pyt1:u9", source_ref={"type": "rapel"},
               actor={"id": "usr_uji", "name": "Uji"})
    a = await qi.enqueue_input(**arg)
    b = await qi.enqueue_input(**{**arg, "amount": 999_000})
    assert a["id"] == b["id"] and a["status"] == "approved"
    assert await jumlah("hr_pay_inputs", {"source_key": "rapel:uji:pyt1:u9"}) == 1
    d = await db.hr_pay_inputs.find_one({"source_key": "rapel:uji:pyt1:u9"})
    assert d["amount"] == 250_000


# ── U10 — komponen potongan berakun ──────────────────────────────────────────────────────────────────────────────────
@pytest.mark.xfail(strict=True, reason=TUNDA_B)
async def test_PYT1_U10_potongan_berakun_jurnal(klien, db, adm):
    eid = await pt_uji("PYT10")
    e = await _siapkan_pt(db, eid, "emp_pyt1_u10")
    h = await adm(eid)
    r = await klien.post("/api/hr/payroll/components", headers=h, json={
        "code": "POT_UJI", "name": "Potongan uji", "kind": "potongan", "account_code": "1-1400"})
    assert r.status_code == 200, r.text
    await _masukan(klien, h, e["e2"], "POT_UJI", NOV, 500_000, "Cicilan uji")
    run = (await klien.post("/api/hr/payroll/runs", json={"entity_id": eid, "period": NOV}, headers=h)).json()
    s = _slip(run, e["e2"])
    # E2: bruto 5.000.000 (PPh 21 0) − potongan 500.000 = 4.500.000.
    assert (s["other_deductions"], s["net"]) == (500_000, 4_500_000)
    j = await _alur(klien, h, run["id"], "submit", "approve", "post-gl")
    assert j["status"] == "posted", j
    je = (await _jurnal(db, "payroll_run", run["id"]))[0]
    # Dr 6-1000 13.800.000 = Cr 2-1600 (8.646.000 + 4.500.000) 13.146.000 + Cr 2-1800 154.000 + Cr 1-1400 500.000.
    assert _jlines(je) == [("1-1400", 0, 500_000), ("2-1600", 0, 13_146_000), ("2-1800", 0, 154_000),
                           ("6-1000", 13_800_000, 0)]
    assert sum(ln["debit"] for ln in je["lines"]) == sum(ln["credit"] for ln in je["lines"])


async def test_PYT1_U10b_validasi_komponen(klien, adm, kanda):
    h = await adm()
    r = await klien.get("/api/hr/payroll/components", headers=h)
    assert r.status_code == 200, r.text
    kode = {c["code"]: c for c in r.json()["items"]}
    for k in ("GAJI_POKOK", "TUNJANGAN", "LEMBUR", "KOMISI", "THR", "PPH21", "BPJS_KES", "BPJS_JHT", "BPJS_JP",
              "BPJS_KES_PT", "BPJS_JHT_PT", "BPJS_JP_PT", "BPJS_JKK", "BPJS_JKM"):
        assert kode[k]["system"] is True, k
    assert kode["THR"]["allowed_run_types"] == ["thr"] and kode["THR"]["bucket"] == "other_earnings"
    r = await klien.post("/api/hr/payroll/components", headers=h, json={
        "code": "POT_TANPA", "name": "Potongan tanpa akun", "kind": "potongan"})
    assert r.status_code == 400 and r.json()["detail"] == "Komponen potongan wajib punya akun.", r.text
    r = await klien.post("/api/hr/payroll/components", headers=h, json={
        "code": "THR", "name": "THR kedua", "kind": "pendapatan"})
    assert r.status_code == 409 and r.json()["detail"] == "Kode komponen sudah dipakai di PT ini.", r.text
    r = await klien.patch(f"/api/hr/payroll/components/{kode['GAJI_POKOK']['id']}", headers=h,
                          json={"kind": "potongan"})
    assert r.status_code == 400 and r.json()["detail"] == "Komponen bawaan tidak bisa diubah jenisnya.", r.text
    r = await klien.patch(f"/api/hr/payroll/components/{kode['GAJI_POKOK']['id']}", headers=h,
                          json={"name": "Gaji Pokok Bulanan"})
    assert r.status_code == 200 and r.json()["name"] == "Gaji Pokok Bulanan", r.text
    await klien.patch(f"/api/hr/payroll/components/{kode['GAJI_POKOK']['id']}", headers=h, json={"name": "Gaji Pokok"})


# ── U11 — format periode ─────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.xfail(strict=True, reason=TUNDA_B)
async def test_PYT1_U11_format_periode(klien, adm, kanda):
    for p in ("2026-13", "Okt"):
        r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KANDA, "period": p}, headers=await adm())
        assert r.status_code == 400, (p, r.text)
        assert r.json()["detail"] == "Periode harus berbentuk TTTT-BB, mis. 2026-10.", p


# ── U15 — ubah jam absen menghitung ulang lembur ─────────────────────────────────────────────────────────────────────
@pytest.mark.xfail(strict=True, reason="PY-14 — serah-terima (b): ubah jam absen menghitung ulang menit lembur")
async def test_PYT1_U15_ubah_jam_absen_hitung_ulang_lembur(klien, db, adm, kanda):
    await db.hr_shifts.insert_one({"id": "shift_pyt1", "entity_id": KANDA, "name": "Pagi", "jam_in": "08:00",
                                   "jam_out": "17:00", "grace_late_min": 0, "status": "active",
                                   "created_at": "2026-01-01T00:00:00+00:00"})
    await db.hr_employees.update_one({"id": kanda["e2"]}, {"$set": {"shift_id": "shift_pyt1"}})
    await db.hr_attendance.insert_one({
        "id": "att_pyt1_u15", "employee_id": kanda["e2"], "entity_id": KANDA, "date": "2026-12-14",
        "clock_in": "2026-12-14T08:00:00+07:00", "clock_out": "2026-12-14T19:00:00+07:00", "method": "manual",
        "status": "hadir", "work_min": 660, "late_min": 0, "early_leave_min": 0, "overtime_min": 120,
        "approved": True, "shift_id": "shift_pyt1"})
    r = await klien.patch("/api/hr/attendance/att_pyt1_u15", headers=await adm(),
                          json={"data": {"clock_out": "2026-12-14T18:00:00+07:00"}})
    assert r.status_code == 200, r.text
    # Shift 08.00–17.00 = 540 menit; kerja 08.00–18.00 = 600 menit → lembur 600 − 540 = 60 menit (dulu tetap 120).
    j = r.json()
    assert (j["work_min"], j["overtime_min"], j["early_leave_min"]) == (600, 60, 0)


# ── U16 — izin: Tanpa Acuan ber-`payroll.create` membuat masukan, tidak bisa mengesahkan ───────────────────────────
async def test_PYT1_U16_izin_masukan(klien, db, adm, akun, sesi, peran_tanpa_acuan, kanda):
    rid = await peran_tanpa_acuan({"payroll": ["create"]}, label="Penyiap Gaji U16")
    h = await sesi(await akun(rid, entitas=(KANDA,)), entitas=KANDA)
    body = {"employee_id": kanda["e2"], "component_code": "THR", "pay_period": "2027-02", "amount": 100_000,
            "label": "THR uji izin", "reason": "uji izin PY-T1"}
    r = await klien.post("/api/hr/payroll/inputs", headers=h, json=body)
    assert r.status_code == 200, r.text
    inp = r.json()
    assert inp["status"] == "pending" and inp["created_by_id"]
    r = await klien.post(f"/api/hr/payroll/inputs/{inp['id']}/approve", headers=h)
    assert r.status_code == 403, r.text
    r = await klien.post("/api/hr/payroll/inputs", headers=h, json={**body, "reason": ""})
    assert r.status_code == 400 and r.json()["detail"] == "Alasan wajib diisi.", r.text
    r = await klien.post("/api/hr/payroll/inputs", headers=h, json={**body, "component_code": "GAJI_POKOK"})
    assert r.status_code == 400 and r.json()["detail"] == "Komponen GAJI_POKOK bukan komponen masukan.", r.text
    r = await klien.post(f"/api/hr/payroll/inputs/{inp['id']}/approve", headers=await adm())
    assert r.status_code == 200 and r.json()["status"] == "approved", r.text

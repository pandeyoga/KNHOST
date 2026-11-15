"""PY-T5 — swalayan karyawan: slip tampil hanya setelah gaji dibayar, lengkap dengan riwayat dan rincian
(docs/blueprint/unit/PY-T5.md).

Persiapan bersama (fixture, disisipkan langsung): "hari ini" dibekukan 15 Des 2026 (`services.book_date._sekarang`);
BPJS dimatikan untuk `ent_kanda` (lapisan PT), jadi bruto pajak = bruto. Karyawan E1 (gaji pokok 8.000.000, tunjangan
Transport 500.000 dan Makan 300.000, TK0) tertaut akun `e1`; E2 (gaji pokok 5.000.000, TK0) tertaut akun `e2`. Akun
`e1`/`e2` berperan `sales` (tanpa `hr.view`). Karyawan lain `ent_kanda` dari seed dinonaktifkan.

Alur (buat proses, ajukan, sahkan, posting, bayar, anulir, batal, masukan THR, pengaturan) lewat HTTP. Satu-satunya
fixture sisip di tengah alur: proses + slip `ent_ksc` berstatus `approved` untuk U3 (karyawan E3 tertaut akun `e3`).

Hitungan tangan (sama dengan PY-T1, tarif dari `ter_rate` tabel bawaan kategori A):
  E1 reguler Okt: bruto 8.000.000 + 500.000 + 300.000 = 8.800.000 → tarif 1,75 % → PPh 21 154.000 → bersih 8.646.000.
  E1 THR Okt (dibuat sesudah reguler): THR 8.000.000; bruto pajak bulan 16.800.000 → 5 % → PPh 21 bulan 840.000;
  dipotong di slip THR = 840.000 − 154.000 = 686.000 → bersih 8.000.000 − 686.000 = 7.314.000.

Rantai `ent_kanda` Oktober (urutan berkas): U4 (draf) → U1 (disahkan) → U3 (pengaturan `disahkan`, lalu kembali
`dibayar`) → U2 (diposting, dibayar) → U5 → U9 → U7 (THR dibayar). `ent_kanda` November: U6 (anulir + batal).
"""
import datetime

import pytest

KANDA, KSC = "ent_kanda", "ent_ksc"
OKT, NOV = "2026-10", "2026-11"
HARI_INI = datetime.datetime(2026, 12, 15, 3, 0, tzinfo=datetime.timezone.utc)   # 15 Des 2026 10.00 WIB
KUNCI = "hr.slip_swalayan_sejak"
BELUM_TERBIT = "Slip gaji ini belum terbit."
SIMPAN: dict = {}


@pytest.fixture(scope="module", autouse=True)
def _hari_ini():
    from services import book_date
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(book_date, "_sekarang", lambda: HARI_INI)
        yield


async def _tautkan(db, akun, sesi, emp_id: str, eid: str) -> dict:
    """Akun `sales` (tanpa `hr.view`) tertaut karyawan `emp_id` → header sesi."""
    u = await akun("sales", entitas=(eid,))
    await db.hr_employees.update_one({"id": emp_id}, {"$set": {"user_id": u["id"]}})
    return await sesi(u, entitas=eid)


@pytest.fixture(scope="module")
async def uji(db, akun, sesi):
    from services import config_resolver as resolver
    for k in ("hr.feature_toggles.bpjs_kesehatan", "hr.feature_toggles.bpjs_ketenagakerjaan"):
        await resolver.set_value(k, False, scope_type="entity", scope_id=KANDA, actor="uji", reason="uji PY-T5")
    e1, e2 = "emp_pyt5_e1", "emp_pyt5_e2"
    for emp_id, nama, gaji, tunj in ((e1, "E1 Uji PY-T5", 8_000_000, [{"name": "Transport", "amount": 500_000},
                                                                      {"name": "Makan", "amount": 300_000}]),
                                     (e2, "E2 Uji PY-T5", 5_000_000, [])):
        await db.hr_employees.insert_one({
            "id": emp_id, "name": nama, "entity_id": KANDA, "status": "active", "base_salary": gaji,
            "allowances": tunj, "ptkp_status": "TK0", "bank_name": "BCA", "bank_acc_no": f"77{gaji}",
            "bank_acc_name": nama, "created_at": "2026-01-01T00:00:00+00:00"})
    await db.hr_employees.update_many({"entity_id": KANDA, "id": {"$nin": [e1, e2]}}, {"$set": {"status": "inactive"}})
    return {"e1": e1, "e2": e2, "h1": await _tautkan(db, akun, sesi, e1, KANDA),
            "h2": await _tautkan(db, akun, sesi, e2, KANDA),
            "adm": await sesi("admin@kainnusantara.id", entitas=KANDA)}


async def _rekening(db, eid: str) -> str:
    """Rekening Bank tunggal PT (fixture) — sumber bayar gaji (PK-20/PK-22)."""
    rid = f"rek_pyt5_{eid}"
    if not await db.bank_accounts.find_one({"id": rid}):
        await db.bank_accounts.insert_one({
            "id": rid, "name": f"Bank {eid}", "entity_id": eid, "account_type": "bank", "cash_type": "kas_besar",
            "bank_name": "BCA", "account_number": "999", "is_active": True, "opening_balance": 900_000_000.0})
    return rid


async def _alur(klien, h, run_id: str, *langkah: str) -> dict:
    j: dict = {}
    for aksi in langkah:
        r = await klien.post(f"/api/hr/payroll/runs/{run_id}/{aksi}", headers=h)
        assert r.status_code == 200, (aksi, r.text)
        j = r.json()
    return j


async def _bayar(klien, db, h, run_id: str) -> dict:
    """Bayar lewat endpoint bayar (PK-22; sejak PY-T4 rekening berperuntukan Gaji + tanggal bayar — `cash_account`
    diabaikan). Yang diuji unit ini hanya "sudah dibayar" (`paid`)."""
    rek = await _rekening(db, KANDA)
    r = await klien.post(f"/api/hr/payroll/runs/{run_id}/pay", json={"cash_account": "1-1100", "account_id": rek},
                         headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paid"
    return r.json()


async def _me(klien, h, **params) -> dict:
    r = await klien.get("/api/hr/payslips/me", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def _atur(klien, h, nilai: str, eid: str = KANDA) -> None:
    r = await klien.put("/api/config/values", headers=h, json={"items": [{
        "key": KUNCI, "value": nilai, "scope_type": "entity", "scope_id": eid, "reason": "uji PY-T5 slip swalayan"}]})
    assert r.status_code == 200, r.text


def _slip_milik(run: dict, emp_id: str) -> dict:
    return next(s for s in run["payslips"] if s["employee_id"] == emp_id)


# ── U4 — slip draf: pemilik 404 (detail & PDF), pemegang hr.view 200 ─────────────────────────────────────────────────
async def test_PYT5_U4_slip_draf_belum_terbit_bagi_pemilik(klien, uji):
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KANDA, "period": OKT}, headers=uji["adm"])
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "draft"
    SIMPAN["okt"] = run
    sid = _slip_milik(run, uji["e1"])["id"]
    SIMPAN["slip_e1"] = sid
    for jalur in (f"/api/hr/payslips/{sid}", f"/api/hr/payslips/{sid}/pdf"):
        r = await klien.get(jalur, headers=uji["h1"])
        assert r.status_code == 404, (jalur, r.text)
        assert r.json()["detail"] == BELUM_TERBIT
        r = await klien.get(jalur, headers=uji["adm"])   # pemegang hr.view: tidak berubah
        assert r.status_code == 200, (jalur, r.text)


# ── U1 — proses disahkan, pengaturan bawaan: daftar kosong ───────────────────────────────────────────────────────────
async def test_PYT5_U1_disahkan_belum_terlihat_pada_bawaan(klien, uji):
    run = await _alur(klien, uji["adm"], SIMPAN["okt"]["id"], "submit", "approve")
    assert run["status"] == "approved"
    j = await _me(klien, uji["h1"])
    assert j["payslips"] == [] and j["years"] == []
    assert j["visible_since"] == "dibayar"
    assert j["employee"]["id"] == uji["e1"]
    # detail ber-id juga tertutup selama belum dibayar
    r = await klien.get(f"/api/hr/payslips/{SIMPAN['slip_e1']}", headers=uji["h1"])
    assert r.status_code == 404 and r.json()["detail"] == BELUM_TERBIT, r.text


# ── U3 — pengaturan `disahkan` untuk ent_kanda; PT lain tidak ikut ──────────────────────────────────────────────────
async def test_PYT5_U3_pengaturan_disahkan_per_pt(klien, db, akun, sesi, uji):
    # Fixture (disisipkan): karyawan E3 ent_ksc tertaut akun e3 + proses ent_ksc Oktober `approved` dengan slipnya.
    e3 = "emp_pyt5_e3"
    await db.hr_employees.insert_one({"id": e3, "name": "E3 Uji PY-T5", "entity_id": KSC, "status": "active",
                                      "base_salary": 6_000_000, "ptkp_status": "TK0",
                                      "created_at": "2026-01-01T00:00:00+00:00"})
    h3 = await _tautkan(db, akun, sesi, e3, KSC)
    await db.hr_payroll_runs.insert_one({"id": "prun_pyt5_ksc", "number": "KSC/PAY-PYT5", "entity_id": KSC,
                                         "period": OKT, "run_type": "regular", "status": "approved",
                                         "paid_at": "", "created_at": "2026-11-01T01:00:00+00:00"})
    await db.hr_payslips.insert_one({"id": "slip_pyt5_ksc", "number": "KSC/SLIP-PYT5", "run_id": "prun_pyt5_ksc",
                                     "entity_id": KSC, "period": OKT, "run_type": "regular", "status": "approved",
                                     "employee_id": e3, "employee_name": "E3 Uji PY-T5", "gross": 6_000_000,
                                     "pph21": 0, "net": 6_000_000, "components": []})
    await _atur(klien, uji["adm"], "disahkan", KANDA)
    j = await _me(klien, uji["h1"])
    assert j["visible_since"] == "disahkan"
    assert [s["id"] for s in j["payslips"]] == [SIMPAN["slip_e1"]], j
    assert j["payslips"][0]["paid_at"] == ""          # belum dibayar
    r = await klien.get(f"/api/hr/payslips/{SIMPAN['slip_e1']}", headers=uji["h1"])
    assert r.status_code == 200, r.text
    # Karyawan ent_ksc: pengaturan PT-nya tetap bawaan `dibayar` → slip `approved` tidak terlihat.
    j3 = await _me(klien, h3)
    assert j3["payslips"] == [] and j3["visible_since"] == "dibayar"
    r = await klien.get("/api/hr/payslips/slip_pyt5_ksc", headers=h3)
    assert r.status_code == 404 and r.json()["detail"] == BELUM_TERBIT, r.text
    await _atur(klien, uji["adm"], "dibayar", KANDA)   # kembali ke bawaan untuk U2


# ── U2 — diposting: belum; dibayar: satu slip lengkap ───────────────────────────────────────────────────────────────
async def test_PYT5_U2_terlihat_setelah_dibayar(klien, db, uji):
    from services import book_date
    run = await _alur(klien, uji["adm"], SIMPAN["okt"]["id"], "post-gl")
    assert run["status"] == "posted"
    j = await _me(klien, uji["h1"])
    assert j["payslips"] == [] and j["years"] == []
    run = await _bayar(klien, db, uji["adm"], SIMPAN["okt"]["id"])
    j = await _me(klien, uji["h1"])
    assert j["years"] == [2026]
    assert len(j["payslips"]) == 1, j
    s = j["payslips"][0]
    assert s["id"] == SIMPAN["slip_e1"] and s["period"] == OKT and s["run_type"] == "regular"
    # bersih 8.646.000 = 8.800.000 − 154.000 (hitungan di kepala berkas)
    assert (s["gross"], s["pph21"], s["net"]) == (8_800_000, 154_000, 8_646_000)
    assert s["paid_at"] == run["paid_at"] and s["paid_at"]
    # Tanggal bayar: sejak PY-T4 = tanggal bayar proses (`paid_date`, bawaan tanggal buku saat dibayar); sebelum PY-T4 =
    # tanggal WIB dari stempel `paid_at`.
    assert s["paid_date"] == (run.get("paid_date") or book_date.tanggal_buku(run["paid_at"]))   # tanggal bayar WIB
    baris = [(c["label"], c["amount"], c["kind"]) for c in s["components"]]
    assert ("Tunjangan — Transport", 500_000, "pendapatan") in baris, baris
    assert ("Gaji Pokok", 8_000_000, "pendapatan") in baris and ("PPh 21", 154_000, "potongan") in baris
    assert s["bank"]["bank_name"] == "BCA"
    # hanya isian swalayan: tidak ada nama/id karyawan lain, akun buku besar, atau sumber masukan
    assert set(s) <= {"id", "number", "period", "run_type", "status", "paid_at", "paid_date", "gross", "net", "pph21",
                      "components", "bank"}, sorted(s)
    assert not [c for c in s["components"] if set(c) - {"code", "label", "kind", "amount", "rate", "basis_period"}]


# ── U5 — slip orang lain tetap 403 ──────────────────────────────────────────────────────────────────────────────────
async def test_PYT5_U5_slip_orang_lain_403(klien, uji):
    for jalur in (f"/api/hr/payslips/{SIMPAN['slip_e1']}", f"/api/hr/payslips/{SIMPAN['slip_e1']}/pdf"):
        r = await klien.get(jalur, headers=uji["h2"])
        assert r.status_code == 403, (jalur, r.text)


# ── U9 — PDF slip sendiri yang sudah dibayar ────────────────────────────────────────────────────────────────────────
async def test_PYT5_U9_pdf_slip_sendiri(klien, uji):
    r = await klien.get(f"/api/hr/payslips/{SIMPAN['slip_e1']}/pdf", headers=uji["h1"])
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"
    r = await klien.get(f"/api/hr/payslips/{SIMPAN['slip_e1']}", headers=uji["h1"])
    assert r.status_code == 200 and r.json()["net"] == 8_646_000, r.text


# ── U7 — proses THR Oktober dibayar: dua slip Oktober; tahun 2025 kosong ────────────────────────────────────────────
async def test_PYT5_U7_riwayat_per_tahun_reguler_dan_thr(klien, db, uji):
    h = uji["adm"]
    r = await klien.post("/api/hr/payroll/inputs", headers=h, json={
        "employee_id": uji["e1"], "component_code": "THR", "pay_period": OKT, "amount": 8_000_000,
        "label": "THR 2026", "reason": "isian uji PY-T5"})
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/hr/payroll/inputs/{r.json()['id']}/approve", headers=h)
    assert r.status_code == 200, r.text
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KANDA, "period": OKT, "run_type": "thr"}, headers=h)
    assert r.status_code == 200, r.text
    thr = r.json()
    assert _slip_milik(thr, uji["e1"])["net"] == 7_314_000   # 8.000.000 − (840.000 − 154.000)
    await _alur(klien, h, thr["id"], "submit", "approve", "post-gl")
    await _bayar(klien, db, h, thr["id"])
    j = await _me(klien, uji["h1"], year="2026")
    assert [(s["period"], s["run_type"]) for s in j["payslips"]] == [(OKT, "thr"), (OKT, "regular")], j
    assert [s["net"] for s in j["payslips"]] == [7_314_000, 8_646_000]
    assert j["years"] == [2026] and j["year"] == 2026
    j = await _me(klien, uji["h1"], year="2025")
    assert j["payslips"] == [] and j["years"] == [2026] and j["year"] == 2025
    j = await _me(klien, uji["h1"], period=OKT)
    assert len(j["payslips"]) == 2
    r = await klien.get("/api/hr/payslips/me", headers=uji["h1"], params={"year": "26"})
    assert r.status_code == 400 and r.json()["detail"] == "Tahun harus berbentuk TTTT, mis. 2026.", r.text
    r = await klien.get("/api/hr/payslips/me", headers=uji["h1"], params={"period": "2026-13"})
    assert r.status_code == 400 and r.json()["detail"] == "Periode harus berbentuk TTTT-BB, mis. 2026-10.", r.text


# ── U6 — proses diposting lalu dianulir, proses lain dibatalkan: tidak muncul walau pengaturan `disahkan` ──────────
async def test_PYT5_U6_anulir_dan_batal_tidak_pernah_terlihat(klien, uji):
    h = uji["adm"]
    await _atur(klien, h, "disahkan", KANDA)
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KANDA, "period": NOV}, headers=h)
    assert r.status_code == 200, r.text
    nov1 = r.json()
    await _alur(klien, h, nov1["id"], "submit", "approve", "post-gl")
    assert len([s for s in (await _me(klien, uji["h1"], period=NOV))["payslips"]]) == 1   # diposting: terlihat
    r = await klien.post(f"/api/hr/payroll/runs/{nov1['id']}/void", json={"reason": "salah hitung uji"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "void", r.text
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KANDA, "period": NOV}, headers=h)
    assert r.status_code == 200, r.text
    nov2 = r.json()
    assert nov2["id"] != nov1["id"]
    await _alur(klien, h, nov2["id"], "submit", "approve")
    r = await klien.post(f"/api/hr/payroll/runs/{nov2['id']}/cancel", json={"reason": "batal uji PY-T5"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "cancelled", r.text
    j = await _me(klien, uji["h1"], year="2026")
    assert [s["period"] for s in j["payslips"]] == [OKT, OKT], j          # hanya dua slip Oktober yang dibayar
    for run in (nov1, nov2):
        sid = _slip_milik(run, uji["e1"])["id"]
        r = await klien.get(f"/api/hr/payslips/{sid}", headers=uji["h1"])
        assert r.status_code == 404 and r.json()["detail"] == BELUM_TERBIT, r.text
    await _atur(klien, h, "dibayar", KANDA)


async def test_PYT5_U6b_penentu_status(uji):
    """Penentu murni: daftar status per pengaturan; status tertutup selalu salah; status antara proses mengikuti asalnya."""
    from services import hr_payslip_self as hs
    tertutup = ("draft", "pending_approval", "cancelled", "voiding", "void")
    for since in ("dibayar", "disahkan"):
        for st in tertutup:
            assert not hs.terbit(since, st, None), (since, st)
            assert not hs.terbit(since, "posted", st), (since, "run", st)
    assert hs.terbit("dibayar", "paid", "paid") and not hs.terbit("dibayar", "posted", "posted")
    assert not hs.terbit("dibayar", "approved", "approved")
    for st in ("approved", "posted", "paid"):
        assert hs.terbit("disahkan", st, st)
    assert hs.terbit("disahkan", "approved", "posting") and hs.terbit("disahkan", "posted", "paying")
    assert not hs.terbit("dibayar", "posted", "paying")
    assert not hs.terbit("disahkan", "posted", "voiding")


# ── U8 — akun tanpa karyawan tertaut ────────────────────────────────────────────────────────────────────────────────
async def test_PYT5_U8_akun_tanpa_karyawan(klien, akun, sesi):
    u = await akun("sales", entitas=(KANDA,))
    h = await sesi(u, entitas=KANDA)
    r = await klien.get("/api/hr/payslips/me", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"employee": None, "years": [], "payslips": []}


# ── U10 — kunci baru: putaran t1_config + nilai tak sah ─────────────────────────────────────────────────────────────
async def test_PYT5_U10_kunci_pengaturan(klien, kepala_admin):
    import config_registry as registry
    from test_KFT8_putaran_pengaturan import putaran
    e = registry.require(KUNCI)
    assert (e["group"], e["type"], e["default"], e["scopes"], e["risk"], e["permission"]) == (
        "sdm", "enum", "dibayar", ["global", "entity"], "medium", ["hr", "manage_payroll"])
    assert [(o["value"], o["label"]) for o in e["options"]] == [
        ("dibayar", "Setelah gaji dibayar"), ("disahkan", "Sejak penggajian disahkan")]
    assert e["label"] == "Slip terlihat karyawan sejak"
    gagal = await putaran(klien, kepala_admin, KUNCI)
    assert not gagal, "\n".join(gagal)
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": KUNCI, "value": "diposting", "scope_type": "global", "scope_id": "", "reason": "uji nilai tak sah"}]})
    assert r.status_code == 400, r.text

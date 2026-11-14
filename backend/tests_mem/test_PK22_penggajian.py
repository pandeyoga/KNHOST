"""PK-22 — penggajian: tanggal buku akhir periode, hitung ulang, batal, void, setoran kewajiban (docs/blueprint/unit/PK-22.md).

Persiapan bersama (fixture, disisipkan langsung): proses gaji Oktober 2026 dengan dua slip bertotal `salary_earnings`
9.000.000 (5.000.000 + 4.000.000), `bpjs_emp` 360.000 (200.000 + 160.000), `bpjs_er` 540.000 (300.000 + 240.000),
`pph21` 150.000 (100.000 + 50.000), komisi 0, bersih 9.000.000 − 360.000 − 150.000 = 8.490.000. "Hari ini" dibekukan
3 Nov 2026 (`services.book_date._sekarang` — satu-satunya jam "hari ini" WIB). Alur (posting, void, bayar, setor, hitung
ulang, batal, izin) lewat HTTP.

Rantai `ent_ksc` Oktober: U1 → U6 → U7 (urutan berkas). U2, U3, U5, U8, U9, U14 memakai PT uji tersendiri (`pt_uji`)
supaya saldo akun dan aturan "satu proses hidup per PT+periode" tidak saling mengganggu; U8 = lanjutan U1 di PT-nya
sendiri (U6 sudah mem-void proses U1 `ent_ksc`). U15 (dua void bersamaan) di MongoDB asli:
`backend/tests/test_bp_PK22_void_bersamaan_mongo.py`.
"""
import datetime

import pytest

from pembantu import aktifkan_akun, jumlah, nonaktifkan_akun, pt_uji as _pt_uji

KSC, KANDA = "ent_ksc", "ent_kanda"
OKT = "2026-10"
HARI_INI = datetime.datetime(2026, 11, 3, 3, 0, tzinfo=datetime.timezone.utc)   # 3 Nov 2026 10.00 WIB
SLIP = [  # (nama, salary_earnings, bpjs_emp, bpjs_er, pph21, komisi)
    ("Andi", 5_000_000, 200_000, 300_000, 100_000, 0),
    ("Budi", 4_000_000, 160_000, 240_000, 50_000, 0),
]


async def pt_uji(kode: str) -> str:
    """PT uji (`pembantu.pt_uji`) + cache status PT dikosongkan supaya PT baru langsung bisa dipakai lewat HTTP."""
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await _pt_uji(kode)
    invalidate_status_cache()
    return eid


@pytest.fixture(scope="module", autouse=True)
def _hari_ini_3_nov():
    from services import book_date
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(book_date, "_sekarang", lambda: HARI_INI)
        yield


@pytest.fixture(scope="module")
async def adm(sesi):
    simpan = {}

    async def _h(eid=KSC):
        if eid not in simpan:
            simpan[eid] = await sesi("admin@kainnusantara.id", entitas=eid)
        return simpan[eid]
    return _h


async def _proses(db, eid, status, *, period=OKT, slip=SLIP, mode="accrue_then_settle", tag=""):
    """Fixture: satu proses gaji + slipnya, disisipkan langsung."""
    rid = f"prun_pk22_{tag or status}_{eid}_{period}".replace("-", "")
    tot = {"employees": 0, "salary_earnings": 0.0, "commission": 0.0, "gross": 0.0, "bpjs_emp": 0.0,
           "bpjs_er": 0.0, "pph21": 0.0, "net": 0.0}
    slips = []
    for i, (nama, gaji, emp, er, pph, kom) in enumerate(slip):
        gross = gaji + kom
        net = gross - emp - pph
        slips.append({"id": f"{rid}_s{i}", "number": f"SLIP-{rid[-6:]}-{i}", "run_id": rid, "entity_id": eid,
                      "period": period, "status": status, "employee_id": f"emp_{rid}_{i}", "employee_name": nama,
                      "salary_earnings": gaji, "commission": kom, "gross": gross, "tax_gross": gross,
                      "bpjs_emp_total": emp, "bpjs_er_total": er, "pph21": pph, "net": net})
        for k, v in (("salary_earnings", gaji), ("commission", kom), ("gross", gross), ("bpjs_emp", emp),
                     ("bpjs_er", er), ("pph21", pph), ("net", net)):
            tot[k] += v
        tot["employees"] += 1
    run = {"id": rid, "number": f"PAY-{rid[-10:]}", "entity_id": eid, "period": period, "status": status,
           "commission_mode": mode, "totals": tot, "gl_posted": False, "journal_id": "", "journal_number": "",
           "submitted_by": "Uji", "submitted_by_id": "usr_uji_pengaju", "created_at": "2026-11-01T01:00:00+00:00"}
    await db.hr_payroll_runs.insert_one(dict(run))
    await db.hr_payslips.insert_many([dict(s) for s in slips])
    return run


async def _karyawan(db, eid, *gaji, awalan="emp_pk22"):
    """Fixture: karyawan aktif (tanpa BPJS dan PPh 21 agar slip = gaji pokok + tunjangan)."""
    out = []
    for i, g in enumerate(gaji):
        emp = {"id": f"{awalan}_{eid}_{i}", "name": f"Karyawan {eid} {i}", "entity_id": eid, "status": "active",
               "base_salary": g, "allowances": 0, "ptkp_status": "TK0", "bpjs_kes_enabled": False,
               "bpjs_tk_enabled": False, "created_at": "2026-01-01T00:00:00+00:00"}
        await db.hr_employees.insert_one(dict(emp))
        out.append(emp)
    return out


async def _jurnal(db, source_type, source_id, eid=None):
    q = {"source_type": source_type, "source_id": source_id, "status": {"$ne": "void"}}
    if eid:
        q["entity_id"] = eid
    return await db.journal_entries.find(q, {"_id": 0}).to_list(50)


def _baris(je):
    return sorted((ln["account_code"], round(ln["debit"], 2), round(ln["credit"], 2)) for ln in je["lines"])


async def _saldo(db, eid, kode, dari="", sampai="9999-12-31"):
    """Σ debit − kredit akun `kode` PT `eid` pada jurnal tidak-void bertanggal [dari, sampai]."""
    tot = 0.0
    async for je in db.journal_entries.find({"entity_id": eid, "status": {"$ne": "void"},
                                             "date": {"$gte": dari, "$lte": sampai}}, {"_id": 0, "lines": 1}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == kode:
                tot += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return round(tot, 2)


async def _rekening(db, eid, rid=None, cash_type="kas_besar"):
    rid = rid or f"rek_pk22_{eid}"
    if not await db.bank_accounts.find_one({"id": rid}):
        await db.bank_accounts.insert_one({
            "id": rid, "name": f"Bank {eid}", "entity_id": eid, "account_type": "bank" if cash_type == "kas_besar"
            else "cash", "cash_type": cash_type, "bank_name": "BCA", "account_number": "999", "is_active": True,
            "opening_balance": 50_000_000.0})
    return rid


JURNAL_U1 = [("2-1600", 0, 8_490_000), ("2-1700", 0, 900_000), ("2-1800", 0, 150_000),
             ("6-1000", 9_000_000, 0), ("6-1100", 540_000, 0)]


# ── U1 — jurnal gaji bertanggal akhir periode ───────────────────────────────────────────────────────────────────────
async def test_PK22_U1_posting_bertanggal_akhir_periode(klien, db, adm):
    run = await _proses(db, KSC, "approved", tag="u1")
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=await adm())
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "posted" and j["journal_date"] == "2026-10-31" and j["gl_status"] == "posted"
    jes = await _jurnal(db, "payroll_run", run["id"])
    assert len(jes) == 1
    je = jes[0]
    # Dr 6-1000 9.000.000 + Dr 6-1100 540.000 = 9.540.000 = Cr 2-1600 8.490.000 + Cr 2-1700 (360.000 + 540.000)
    # 900.000 + Cr 2-1800 150.000.
    assert je["date"] == "2026-10-31" and _baris(je) == JURNAL_U1
    assert je["total_debit"] == je["total_credit"] == 9_540_000
    assert j["journal_id"] == je["id"] and j["posted_by_id"]


# ── U2 — periode tertutup ditolak sebelum tulisan ────────────────────────────────────────────────────────────────────
async def test_PK22_U2_periode_tertutup_409_tanpa_jurnal(klien, db, adm, paksa_jurnal_gagal):
    eid = await pt_uji("P22B")
    run = await _proses(db, eid, "approved", tag="u2")
    async with paksa_jurnal_gagal("periode", entity_id=eid, period_key=OKT):
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=await adm(eid))
    assert r.status_code == 409, r.text
    assert "DITUTUP" in r.json()["detail"] or "ditutup" in r.json()["detail"]
    doc = await db.hr_payroll_runs.find_one({"id": run["id"]})
    assert doc["status"] == "approved" and not doc.get("gl_status")
    assert await jumlah("journal_entries", {"source_type": "payroll_run", "source_id": run["id"]}) == 0


# ── U3 — akun nonaktif: gagal tercatat, tampil di panel, ulang menerbitkan tepat satu jurnal ──────────────────────
async def test_PK22_U3_jurnal_gagal_panel_lalu_ulang(klien, db, adm):
    eid = await pt_uji("P22C")
    run = await _proses(db, eid, "approved", tag="u3")
    h = await adm(eid)
    await nonaktifkan_akun(eid, "2-1600")
    try:
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=h)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["status"] == "approved" and j["gl_status"] == "failed" and "2-1600" in j["gl_error"]
        r = await klien.get("/api/finance/posting-failures", params={"kind": "payroll_run"}, headers=h)
        assert r.status_code == 200, r.text
        assert [it["id"] for it in r.json()["items"]] == [run["id"]]
        assert r.json()["items"][0]["amount"] == 8_490_000
    finally:
        await aktifkan_akun(eid, "2-1600")
    r = await klien.post(f"/api/finance/posting-failures/payroll_run/{run['id']}/retry", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["gl_status"] == "posted"
    doc = await db.hr_payroll_runs.find_one({"id": run["id"]})
    assert doc["status"] == "posted" and doc["journal_date"] == "2026-10-31"
    assert len(await _jurnal(db, "payroll_run", run["id"])) == 1
    r = await klien.post(f"/api/finance/posting-failures/payroll_run/{run['id']}/retry", headers=h)
    assert r.status_code == 404, r.text
    assert len(await _jurnal(db, "payroll_run", run["id"])) == 1


# ── U4 — hitung ulang draf; sesudah disahkan 409 ─────────────────────────────────────────────────────────────────────
async def test_PK22_U4_hitung_ulang_draf_lalu_409_sesudah_disahkan(klien, db, adm):
    eid = await pt_uji("P22D")
    emps = await _karyawan(db, eid, 5_000_000, 4_000_000)
    h = await adm(eid)
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": eid, "period": OKT}, headers=h)
    assert r.status_code == 200, r.text
    run = r.json()
    slip = {s["employee_id"]: s for s in run["payslips"]}
    sebelum = slip[emps[0]["id"]]
    await db.hr_employees.update_one({"id": emps[0]["id"]}, {"$set": {"allowances": 500_000}})
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/recalculate", headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    sesudah = {s["employee_id"]: s for s in j["payslips"]}[emps[0]["id"]]
    assert sesudah["salary_earnings"] == sebelum["salary_earnings"] + 500_000
    assert (sesudah["id"], sesudah["number"]) == (sebelum["id"], sebelum["number"])
    assert j["recalc_count"] == 1 and j["totals"]["salary_earnings"] == run["totals"]["salary_earnings"] + 500_000
    assert len(j["payslips"]) == 2
    for aksi in ("submit", "approve"):
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/{aksi}", headers=h)
        assert r.status_code == 200, r.text
    await db.hr_employees.update_one({"id": emps[0]["id"]}, {"$set": {"allowances": 900_000}})
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/recalculate", headers=h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == f"Penggajian {run['number']} berstatus Disahkan, jadi tidak bisa dihitung ulang."
    tetap = await db.hr_payslips.find_one({"id": sebelum["id"]})
    assert tetap["salary_earnings"] == sebelum["salary_earnings"] + 500_000


async def test_PK22_U4b_hitung_ulang_menambah_dan_menghapus_slip(klien, db, adm):
    eid = await pt_uji("P22E")
    emps = await _karyawan(db, eid, 3_000_000, 2_000_000)
    h = await adm(eid)
    run = (await klien.post("/api/hr/payroll/runs", json={"entity_id": eid, "period": OKT}, headers=h)).json()
    await db.hr_employees.update_one({"id": emps[1]["id"]}, {"$set": {"status": "inactive"}})
    baru = (await _karyawan(db, eid, 1_500_000, awalan="emp_pk22_baru"))[0]
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/recalculate", headers=h)
    assert r.status_code == 200, r.text
    ids = sorted(s["employee_id"] for s in r.json()["payslips"])
    assert ids == sorted([emps[0]["id"], baru["id"]])
    assert r.json()["totals"]["employees"] == 2 and r.json()["totals"]["salary_earnings"] == 4_500_000
    assert await jumlah("hr_payslips", {"run_id": run["id"]}) == 2


# ── U5 — batal yang diajukan; proses baru untuk periode sama boleh dibuat ──────────────────────────────────────────
async def test_PK22_U5_batal_lalu_proses_baru(klien, db, adm):
    eid = await pt_uji("P22F")
    await _karyawan(db, eid, 5_000_000)
    run = await _proses(db, eid, "pending_approval", tag="u5")
    h = await adm(eid)
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/cancel", json={"reason": "abc"}, headers=h)
    assert r.status_code == 400, r.text
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/cancel", json={"reason": "salah periode lembur"},
                         headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "cancelled" and j["cancel_reason"] == "salah periode lembur" and j["cancelled_by_id"]
    assert {s["status"] for s in j["payslips"]} == {"cancelled"}
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": eid, "period": OKT}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["id"] != run["id"] and r.json()["status"] == "draft"
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/cancel", json={"reason": "batal lagi ya"}, headers=h)
    assert r.status_code == 409, r.text
    assert "berstatus Dibatalkan, jadi tidak bisa dibatalkan" in r.json()["detail"]


# ── U6 — void (lanjutan U1): jurnal pembalik bertanggal akhir periode, saldo kembali nol ───────────────────────────
async def test_PK22_U6_void_membalik_jurnal(klien, db, adm):
    rid = "prun_pk22_u1_ent_ksc_202610"
    r = await klien.post(f"/api/hr/payroll/runs/{rid}/void", json={"reason": "tunj"}, headers=await adm())
    assert r.status_code == 400, r.text
    r = await klien.post(f"/api/hr/payroll/runs/{rid}/void", json={"reason": "salah tunjangan transport"},
                         headers=await adm())
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "void" and j["void_reason"] == "salah tunjangan transport" and j["void_journal_id"]
    assert {s["status"] for s in j["payslips"]} == {"void"}
    rev = await _jurnal(db, "payroll_run_reversal", rid)
    assert len(rev) == 1 and rev[0]["date"] == "2026-10-31"
    assert _baris(rev[0]) == sorted((k, c, d) for k, d, c in JURNAL_U1)
    for kode in ("6-1000", "6-1100", "2-1600", "2-1700", "2-1800"):
        assert await _saldo(db, KSC, kode, "2026-10-01", "2026-10-31") == 0, kode
    r = await klien.post(f"/api/hr/payroll/runs/{rid}/void", json={"reason": "void kedua kali"}, headers=await adm())
    assert r.status_code == 409, r.text
    # Glosarium (KN_32) & penjaga i18n: "void" tampil sebagai "anulir" (spesifikasi: "di-void").
    assert r.json()["detail"].endswith("berstatus Dianulir, jadi tidak bisa dianulir.")


# ── U7 — proses Oktober baru sesudah void: jurnal kedua terbit (kunci per proses) ─────────────────────────────────
async def test_PK22_U7_proses_baru_sesudah_void(klien, db, adm):
    await _karyawan(db, KSC, 5_000_000, 4_000_000)
    h = await adm()
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KSC, "period": OKT}, headers=h)
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["id"] != "prun_pk22_u1_ent_ksc_202610"
    for aksi in ("submit", "approve", "post-gl"):
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/{aksi}", headers=h)
        assert r.status_code == 200, (aksi, r.text)
    assert r.json()["status"] == "posted"
    assert len(await _jurnal(db, "payroll_run", run["id"])) == 1
    hidup = [je for je in await db.journal_entries.find(
        {"entity_id": KSC, "source_type": "payroll_run", "status": {"$ne": "void"}}, {"_id": 0}).to_list(50)
        if not je.get("reversed") and je.get("date", "").startswith(OKT)]
    assert [je["source_id"] for je in hidup] == [run["id"]]


# ── U8 — setoran kewajiban (lanjutan U1 di PT uji) ─────────────────────────────────────────────────────────────────
async def test_PK22_U8_setoran_bpjs_dan_tolak_melebihi_sisa(klien, db, adm):
    eid = await pt_uji("P22H")
    rek = await _rekening(db, eid)
    run = await _proses(db, eid, "approved", tag="u8")
    h = await adm(eid)
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "posted", r.text
    r = await klien.get("/api/hr/payroll/remittances/outstanding", params={"period": OKT}, headers=h)
    assert r.status_code == 200, r.text
    assert (r.json()["bpjs"]["kewajiban"], r.json()["bpjs"]["disetor"], r.json()["bpjs"]["sisa"]) == (900_000, 0, 900_000)
    assert r.json()["pph21"]["sisa"] == 150_000
    body = {"kind": "bpjs", "period": OKT, "amount": 900_000, "paid_date": "2026-11-10", "account_id": rek,
            "cash_type": "kas_besar", "reference": "BPJS-OKT-01"}
    r = await klien.post("/api/hr/payroll/remittances", json=body, headers={**h, "Idempotency-Key": "pk22-u8-a"})
    assert r.status_code == 200, r.text
    st = r.json()
    assert st["status"] == "done" and st["gl_status"] == "posted" and st["number"].endswith("STR-00001")
    kas = await db.cash_transactions.find_one({"id": st["cash_txn_id"]})
    assert (kas["direction"], kas["amount"], kas["account_id"], kas["ref_type"]) == ("out", 900_000, rek,
                                                                                     "statutory_remittance")
    je = (await _jurnal(db, "cash_transaction", kas["id"]))[0]
    assert je["date"] == "2026-11-10" and _baris(je) == [("1-1100", 0, 900_000), ("2-1700", 900_000, 0)]
    # Saldo 2-1700 (normal kredit) = −900.000 (posting) + 900.000 (setoran) = 0; 6-1100 tetap 540.000.
    assert await _saldo(db, eid, "2-1700") == 0
    assert await _saldo(db, eid, "6-1100") == 540_000
    r = await klien.get("/api/hr/payroll/remittances/outstanding", params={"period": OKT}, headers=h)
    assert r.json()["bpjs"]["sisa"] == 0 and r.json()["bpjs"]["disetor"] == 900_000
    # Kirim ulang kunci sama → setoran yang sama, tanpa kas kedua.
    r = await klien.post("/api/hr/payroll/remittances", json=body, headers={**h, "Idempotency-Key": "pk22-u8-a"})
    assert r.status_code == 200 and r.json()["id"] == st["id"], r.text
    assert await jumlah("cash_transactions", {"ref_type": "statutory_remittance"}) == 1
    # PPh 21 Rp 200.000 > sisa Rp 150.000 → 400, tanpa setoran maupun kas.
    r = await klien.post("/api/hr/payroll/remittances", headers={**h, "Idempotency-Key": "pk22-u8-b"},
                         json={**body, "kind": "pph21", "amount": 200_000, "reference": ""})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Setoran Rp 200.000 melebihi sisa kewajiban PPh 21 Oktober 2026 (Rp 150.000)."
    assert await jumlah("hr_statutory_remittances", {"entity_id": eid}) == 1
    assert await jumlah("cash_transactions", {"ref_type": "statutory_remittance"}) == 1
    r = await klien.get("/api/hr/payroll/remittances", params={"period": OKT}, headers=h)
    assert r.status_code == 200 and r.json()["total"] == 1 and r.json()["items"][0]["id"] == st["id"]


async def test_PK22_U8b_setoran_pph21_dari_pemetaan_dan_mode_semua_pt(klien, db, adm, sesi):
    eid = "ent_uji_p22h"
    h = await adm(eid)
    r = await klien.post("/api/hr/payroll/remittances", headers=h, json={
        "kind": "pph21", "period": OKT, "amount": 150_000, "paid_date": "2026-11-12", "cash_type": "kas_besar"})
    assert r.status_code == 200, r.text   # rekening tunggal Bank PT itu
    je = (await _jurnal(db, "cash_transaction", r.json()["cash_txn_id"]))[0]
    assert _baris(je) == [("1-1100", 0, 150_000), ("2-1800", 150_000, 0)]
    assert await _saldo(db, eid, "2-1800") == 0
    semua = await sesi("admin@kainnusantara.id", entitas="all")
    r = await klien.post("/api/hr/payroll/remittances", headers=semua, json={
        "kind": "bpjs", "period": OKT, "amount": 1, "paid_date": "2026-11-12"})
    # Pagar tulis mode gabungan (`entity_write_guard`) menolak lebih dulu; layar mematikan tombolnya.
    assert r.status_code == 409 and "hanya untuk melihat" in r.json()["detail"], r.text
    r = await klien.get("/api/hr/payroll/remittances/outstanding", params={"period": OKT}, headers=semua)
    assert r.status_code == 400, r.text


# ── U9 — bayar hanya dari akun kas/bank pemetaan ─────────────────────────────────────────────────────────────────────
async def test_PK22_U9_bayar_dari_piutang_ditolak(klien, db, adm):
    eid = await pt_uji("P22J")
    run = await _proses(db, eid, "posted", tag="u9")
    h = await adm(eid)
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/pay", json={"cash_account": "1-1200"}, headers=h)
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Akun pembayaran '1-1200' bukan akun kas/bank aktif — pilih akun Kas/Bank."
    assert (await db.hr_payroll_runs.find_one({"id": run["id"]}))["status"] == "posted"
    assert await jumlah("journal_entries", {"source_type": "payroll_pay", "source_id": run["id"]}) == 0
    # Akun kas besar pemetaan + rekening tunggal Bank PT → dibayar; jurnal bayar berkunci id proses.
    rek = await _rekening(db, eid)
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/pay", json={"cash_account": "1-1100"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "paid" and r.json()["pay_gl_status"] == "posted" and r.json()["paid_by_id"]
    je = (await _jurnal(db, "payroll_pay", run["id"]))[0]
    assert _baris(je) == [("1-1100", 0, 8_490_000), ("2-1600", 8_490_000, 0)]
    kas = await db.cash_transactions.find_one({"id": r.json()["cash_txn_id"]})
    assert kas["account_id"] == rek and kas["amount"] == 8_490_000
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/void", json={"reason": "sudah dibayar kok"}, headers=h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == f"Penggajian {run['number']} berstatus Dibayar, jadi tidak bisa dianulir."


# ── U10 — izin terpisah ──────────────────────────────────────────────────────────────────────────────────────────────
async def test_PK22_U10_izin_terpisah(klien, db, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong):
    rid = await peran_tanpa_acuan({"payroll": ["create"]}, label="Siapkan Gaji")
    h = await sesi(await akun(rid, entitas=(KSC,)))
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KSC, "period": "2026-09"}, headers=h)
    assert r.status_code == 200, r.text
    run = r.json()
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/submit", headers=h)
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/approve", headers=h)
    assert r.status_code == 403, r.text
    for aksi in ("post-gl", "void", "pay"):
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/{aksi}", json={"reason": "uji izin saja"}, headers=h)
        assert r.status_code == 403, (aksi, r.text)
    mk = await sesi(await akun(await peran_manajer_kosong(), entitas=(KSC,)))
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KSC, "period": "2026-08"}, headers=mk)
    assert r.status_code == 403, r.text
    for aksi in ("submit", "approve", "recalculate", "post-gl", "pay"):
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/{aksi}", json={}, headers=mk)
        assert r.status_code == 403, (aksi, r.text)
    r = await klien.post("/api/hr/payroll/remittances", headers=mk, json={
        "kind": "bpjs", "period": OKT, "amount": 1, "paid_date": "2026-11-10"})
    assert r.status_code == 403, r.text


# ── U11 — periode yang belum dimulai ────────────────────────────────────────────────────────────────────────────────
async def test_PK22_U11_periode_belum_dimulai(klien, adm):
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KSC, "period": "2026-12"}, headers=await adm())
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Periode Desember 2026 belum dimulai, jadi belum bisa diproses."
    r = await klien.post("/api/hr/payroll/runs/preview", json={"entity_id": KSC, "period": "2026-12"},
                         headers=await adm())
    assert r.status_code == 400, r.text
    # Periode berjalan (November) boleh (ASUMSI spesifikasi).
    r = await klien.post("/api/hr/payroll/runs/preview", json={"entity_id": KSC, "period": "2026-11"},
                         headers=await adm())
    assert r.status_code == 200, r.text


# ── U12 — penyusutan bertanggal akhir periode; periode melompat dilewati beralasan ─────────────────────────────────
async def test_PK22_U12_penyusutan_tanggal_dan_periode_melompat(klien, db, adm):
    # Diperoleh 15 Sep, 12 bulan, Rp 12.000.000 → Rp 1.000.000/bulan; September sudah disusutkan (fixture).
    for aid in ("fa_pk22_a", "fa_pk22_b"):
        await db.fin_fixed_assets.insert_one({
            # `gl_status` = jurnal perolehan sudah terbit (PK-23: aset tanpa jurnal perolehan tidak disusutkan).
            "id": aid, "number": aid.upper(), "name": f"Mesin {aid[-1]}", "entity_id": KSC, "status": "active",
            "gl_status": "posted",
            "acquisition_date": "2026-09-15", "acquisition_cost": 12_000_000, "salvage_value": 0,
            "useful_life_months": 12, "monthly_depreciation": 1_000_000, "accumulated_depreciation": 1_000_000,
            "book_value": 11_000_000, "depreciated_months": 1, "applied_periods": ["2026-09"],
            "depreciation_periods": ["2026-09"], "last_depreciation_period": "2026-09"})
    h = await adm()
    r = await klien.post("/api/fixed-assets/run-depreciation", headers=h,
                         json={"period": OKT, "asset_id": "fa_pk22_a", "entity_id": KSC})
    assert r.status_code == 200, r.text
    assert r.json()["posted"] == 1 and r.json()["total_amount"] == 1_000_000
    je = (await _jurnal(db, "fixed_asset_depreciation", f"fa_pk22_a:{OKT}"))[0]
    assert je["date"] == "2026-10-31" and _baris(je) == [("1-2900", 0, 1_000_000), ("6-6000", 1_000_000, 0)]
    r = await klien.post("/api/fixed-assets/run-depreciation", headers=h,
                         json={"period": "2026-11", "asset_id": "fa_pk22_b", "entity_id": KSC})
    assert r.status_code == 200, r.text
    assert r.json()["posted"] == 0 and r.json()["skipped"] == 1
    lewat = r.json()["skipped_assets"]
    assert [x["asset_id"] for x in lewat] == ["fa_pk22_b"] and "periode melompat" in lewat[0]["reason"]
    assert lewat[0]["expected_period"] == OKT
    assert await jumlah("journal_entries", {"source_id": "fa_pk22_b:2026-11"}) == 0
    r = await klien.post("/api/fixed-assets/run-depreciation", headers=h,
                         json={"period": "2026-12", "asset_id": "fa_pk22_b", "entity_id": KSC})
    assert r.status_code == 400 and r.json()["detail"].startswith("Periode Desember 2026 belum dimulai"), r.text


# ── U13 — pengaturan per PT: hari posting untuk ent_kanda saja ──────────────────────────────────────────────────────
async def test_PK22_U13_pengaturan_per_pt(klien, db, adm):
    h = await adm()
    r = await klien.put("/api/config/values", headers=h, json={"items": [{
        "key": "gl.tanggal_jurnal_periodik", "value": "hari_posting", "scope_type": "entity", "scope_id": KANDA,
        "reason": "uji PK-22"}]})
    assert r.status_code == 200, r.text
    try:
        kanda = await _proses(db, KANDA, "approved", tag="u13")
        ksc = await _proses(db, KSC, "approved", tag="u13")
        r = await klien.post(f"/api/hr/payroll/runs/{kanda['id']}/post-gl", headers=await adm(KANDA))
        assert r.status_code == 200 and r.json()["journal_date"] == "2026-11-03", r.text
        r = await klien.post(f"/api/hr/payroll/runs/{ksc['id']}/post-gl", headers=h)
        assert r.status_code == 200 and r.json()["journal_date"] == "2026-10-31", r.text
        assert (await _jurnal(db, "payroll_run", kanda["id"]))[0]["date"] == "2026-11-03"
        assert (await _jurnal(db, "payroll_run", ksc["id"]))[0]["date"] == "2026-10-31"
    finally:
        await klien.post("/api/config/values/clear", headers=h, json={
            "key": "gl.tanggal_jurnal_periodik", "scope_type": "entity", "scope_id": KANDA, "reason": "uji PK-22"})
    from services import periodic_posting
    assert await periodic_posting.journal_date(KANDA, OKT) == "2026-10-31"


# ── U14 — akrual komisi dari slip; galatnya menggagalkan posting ─────────────────────────────────────────────────────
async def test_PK22_U14_akrual_dari_slip_tidak_ditelan(klien, db, adm):
    eid = await pt_uji("P22N")
    run = await _proses(db, eid, "approved", tag="u14", slip=[("Sales A", 5_000_000, 200_000, 300_000, 100_000,
                                                               300_000)])
    h = await adm(eid)
    await nonaktifkan_akun(eid, "2-1500")
    try:
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "approved" and r.json()["gl_status"] == "failed"
        assert "2-1500" in r.json()["gl_error"]
        assert await jumlah("journal_entries", {"source_type": "payroll_run", "entity_id": eid}) == 0
        assert await jumlah("journal_entries", {"source_type": "incentive_accrual", "entity_id": eid}) == 0
    finally:
        await aktifkan_akun(eid, "2-1500")
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "posted", r.text
    akr = await _jurnal(db, "incentive_accrual", f"{eid}:{OKT}")
    assert len(akr) == 1 and akr[0]["date"] == "2026-10-31"
    assert _baris(akr[0]) == [("2-1500", 0, 300_000), ("6-5000", 300_000, 0)]
    gaji = (await _jurnal(db, "payroll_run", run["id"]))[0]
    assert ("2-1500", 300_000, 0) in _baris(gaji)
    assert r.json()["incentive_journal_id"] == akr[0]["id"]
    # Saldo 2-1500 = −300.000 (akrual) + 300.000 (gaji) = 0.
    assert await _saldo(db, eid, "2-1500") == 0


async def test_PK22_U14b_akrual_manual_mode_lain_409(klien, adm):
    eid = await pt_uji("P22O")
    h = await adm(eid)
    r = await klien.put("/api/config/values", headers=h, json={"items": [{
        "key": "hr.payroll_commission_mode", "value": "pay_on_invoice", "scope_type": "entity", "scope_id": eid,
        "reason": "uji PK-22"}]})
    assert r.status_code == 200, r.text
    r = await klien.post("/api/sales/incentive/post-gl", params={"period": OKT}, headers=h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == ("PT ini mengakui beban insentif saat gaji diposting, jadi akrual terpisah tidak "
                                  "dipakai.")


# ── Tambahan — tanggal jurnal LPJ = pengeluaran terakhir ─────────────────────────────────────────────────────────────
async def test_PK22_LPJ_bertanggal_pengeluaran_terakhir(klien, db, adm):
    await db.cash_advances.insert_one({"id": "ca_pk22", "number": "KSC/PD-PK22", "entity_id": KSC,
                                       "status": "disbursed", "total_amount": 500_000, "created_at": "2026-10-01"})
    await db.cash_advance_settlements.insert_one({
        "id": "stl_pk22", "number": "KSC/STL-PK22", "entity_id": KSC, "cash_advance_id": "ca_pk22",
        "cash_advance_number": "KSC/PD-PK22", "status": "submitted", "divisi": "Gudang", "periode": "Oktober",
        "expense_lines": [{"date": "2026-10-20", "category": "petty_cash_lain", "amount": 200_000},
                          {"date": "2026-10-25", "category": "petty_cash_lain", "amount": 300_000}],
        "category_totals": {"petty_cash_lain": 500_000}, "total_pengeluaran": 500_000, "total_pettycash": 500_000,
        "created_by": "Uji", "created_by_id": "usr_uji_lpj", "created_at": "2026-10-26T01:00:00+00:00",
        "submitted_at": "2026-10-26T01:00:00+00:00"})
    r = await klien.post("/api/cash-advance-settlements/stl_pk22/approve", headers=await adm())
    assert r.status_code == 200, r.text
    je = (await _jurnal(db, "petty_cash_settlement", "stl_pk22"))[0]
    assert je["date"] == "2026-10-25"
    from services.cash_advance_service import settlement_journal_date
    assert settlement_journal_date({"expense_lines": [{"date": ""}], "submitted_at": "2026-10-28T20:00:00+00:00"}) \
        == "2026-10-29"   # 20.00 UTC = 03.00 WIB tanggal 29


# ── Tambahan — izin peran lama dipindah sekali (`pk22:izin-penggajian`) ─────────────────────────────────────────────
async def test_PK22_migrasi_izin_peran_kustom(klien, db, kepala_admin):
    from services.custom_role_service import PK22_MIGRATION_ID, migrate_pk22_payroll_permission
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "HR Gaji Lama", "base_role": "", "permissions": {"hr": ["view", "manage_payroll"]},
        "description": "peran uji"})
    assert r.status_code == 200, r.text
    rid = (r.json().get("role") or r.json())["id"]
    rec = await db.permission_settings.find_one({"id": "default"})
    assert PK22_MIGRATION_ID in rec["migrations_applied"]
    assert not (rec["matrix"].get(rid) or {}).get("payroll")
    await db.permission_settings.update_one({"id": "default"}, {"$pull": {"migrations_applied": PK22_MIGRATION_ID}})
    hasil = await migrate_pk22_payroll_permission()
    assert rid in hasil["diberi"] and "admin" not in hasil["diberi"]
    rec = await db.permission_settings.find_one({"id": "default"})
    assert rec["matrix"][rid]["payroll"] == ["create", "approve", "post", "void", "pay"]
    assert await migrate_pk22_payroll_permission() == {"diberi": []}   # sekali jalan


# ── Tambahan — kontrol dua orang pada posting (K-41) ───────────────────────────────────────────────────────────────
async def test_PK22_kontrol_dua_orang_posting(klien, db, akun, sesi, adm):
    from services import config_resolver as resolver
    eid = await pt_uji("P22K")
    mgr = await akun("manager", entitas=(eid,))
    run = await _proses(db, eid, "approved", tag="k41")
    await db.hr_payroll_runs.update_one({"id": run["id"]}, {"$set": {"submitted_by_id": mgr["id"]}})
    await resolver.set_value("kontrol.proses_gaji.min_orang", "2", scope_type="entity", scope_id=eid,
                             actor="uji", reason="uji PK-22")
    try:
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=await sesi(mgr, entitas=eid))
        assert r.status_code == 403, r.text
        assert (await db.hr_payroll_runs.find_one({"id": run["id"]}))["status"] == "approved"
        r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=await adm(eid))
        assert r.status_code == 200 and r.json()["status"] == "posted", r.text
    finally:
        await resolver.clear_layer("kontrol.proses_gaji.min_orang", scope_type="entity", scope_id=eid,
                                   actor="uji", reason="uji PK-22")

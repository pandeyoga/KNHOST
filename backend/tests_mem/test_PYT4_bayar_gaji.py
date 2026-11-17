"""PY-T4 — bayar gaji dari rekening berperuntukan Gaji, daftar transfer per karyawan, Finance membayar & menyetor
(docs/blueprint/unit/PY-T4.md).

Persiapan bersama (fixture, disisipkan langsung): PT `ent_kanda`, proses reguler November 2026 dengan tiga slip —
Ani bersih 5.000.000 (BCA 111), Bayu 4.500.000 (Mandiri 222), Cici 3.250.000 (tanpa rekening); `totals.net`
= 5.000.000 + 4.500.000 + 3.250.000 = 12.750.000; tanggal jurnal gaji 2026-11-30. Rekening PT: R-GAJI (bank;
peruntukan gaji + operasional), R-OPS (bank; operasional), R-KAS (kas kecil; operasional). Akun `fin` berperan
Finance bawaan; `hrx` berperan kustom "HR" tanpa acuan (`hr.view`, `hr.update`, `payroll.create`). "Hari ini"
dibekukan 2 Des 2026 (`services.book_date._sekarang`).

Proses yang dibayar (U2, U4, U2b, U2c) diposting lewat HTTP (jurnal gaji Dr 6-1000 / Cr 2-1600 bertanggal 2026-11-30);
proses yang hanya diuji penolakannya disisipkan langsung berstatus `posted` (fixture). Alur bayar, daftar transfer,
ekspor, setoran, batal setoran, dan izin lewat HTTP. U14 (dua bayar bersamaan) di MongoDB asli:
`backend/tests/test_bp_PYT4_bayar_bersamaan_mongo.py`.
"""
import datetime
import io

import pytest

from pembantu import jumlah, pt_uji as _pt_uji

KANDA, KSC = "ent_kanda", "ent_ksc"
NOV, OKT = "2026-11", "2026-10"
HARI_INI = datetime.datetime(2026, 12, 2, 3, 0, tzinfo=datetime.timezone.utc)   # 2 Des 2026 10.00 WIB
SLIP_NOV = [  # (nama, gaji bersih, bank, nomor rekening)
    ("Ani", 5_000_000, "BCA", "111"),
    ("Bayu", 4_500_000, "Mandiri", "222"),
    ("Cici", 3_250_000, "", ""),
]
TOTAL_NOV = 12_750_000   # 5.000.000 + 4.500.000 + 3.250.000
R_GAJI, R_OPS, R_KAS = "rek_pyt4_gaji", "rek_pyt4_ops", "rek_pyt4_kas"
MODUL = "Minta Admin menambahkan akses 'SDM & Penggajian'"


async def pt_uji(kode: str) -> str:
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await _pt_uji(kode)
    invalidate_status_cache()
    return eid


@pytest.fixture(scope="module", autouse=True)
def _hari_ini_2_des():
    from services import book_date
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(book_date, "_sekarang", lambda: HARI_INI)
        yield


async def _rekening(db, rid, eid, nama, *, purposes, cash_type="kas_besar", bank="BCA", nomor="0001",
                    aktif=True):
    """Fixture: rekening dengan peruntukan eksplisit (field PM-T1)."""
    if not await db.bank_accounts.find_one({"id": rid}):
        await db.bank_accounts.insert_one({
            "id": rid, "name": nama, "entity_id": eid, "account_type": "bank" if cash_type == "kas_besar" else "cash",
            "cash_type": cash_type, "bank_name": bank if cash_type == "kas_besar" else "", "account_number": nomor,
            "holder_name": f"PT {eid}", "purposes": list(purposes), "is_active": aktif,
            "payment_method_codes": ["transfer"] if cash_type == "kas_besar" else ["cash"],
            "default_receiving_methods": [], "show_on_documents": False, "opening_balance": 100_000_000.0,
            "created_at": "2026-01-01T00:00:00+00:00"})
    return rid


@pytest.fixture(scope="module")
async def siap(db, sesi, akun, peran_tanpa_acuan):
    """Rekening PT `ent_kanda`, sesi admin, `fin` (Finance bawaan), `hrx` (peran kustom "HR")."""
    assert await db.bank_accounts.count_documents({"entity_id": KANDA}) == 0   # tanpa data demo
    await _rekening(db, R_GAJI, KANDA, "R-GAJI BCA Kanda", purposes=["gaji", "operasional"], nomor="7001")
    await _rekening(db, R_OPS, KANDA, "R-OPS Mandiri Kanda", purposes=["operasional"], bank="Mandiri", nomor="7002")
    await _rekening(db, R_KAS, KANDA, "R-KAS Kas Kecil Kanda", purposes=["operasional"], cash_type="kas_kecil")
    fin_user = await akun("finance", entitas=(KANDA,))
    hrx_role = await peran_tanpa_acuan({"hr": ["view", "update"], "payroll": ["create"]}, label="HR")
    hrx_user = await akun(hrx_role, entitas=(KANDA,))
    return {"adm": await sesi("admin@kainnusantara.id", entitas=KANDA), "fin": await sesi(fin_user, entitas=KANDA),
            "fin_user": fin_user, "hrx": await sesi(hrx_user, entitas=KANDA)}


async def _proses(db, tag, status, *, eid=KANDA, period=NOV, slip=SLIP_NOV, journal_date="2026-11-30",
                  bpjs=(0, 0)):
    """Fixture: proses gaji + slip (kolom lama tanpa komponen), disisipkan langsung."""
    rid = f"prun_pyt4_{tag}"
    tot = {"employees": 0, "salary_earnings": 0.0, "commission": 0.0, "gross": 0.0, "bpjs_emp": float(bpjs[0]),
           "bpjs_er": float(bpjs[1]), "pph21": 0.0, "net": 0.0}
    slips = []
    for i, (nama, net, bank, nomor) in enumerate(slip):
        slips.append({"id": f"{rid}_s{i}", "number": f"SLIP-{tag.upper()}-{i + 1}", "run_id": rid, "entity_id": eid,
                      "period": period, "status": status, "employee_id": f"emp_{rid}_{i}", "employee_name": nama,
                      "salary_earnings": net, "commission": 0, "gross": net, "tax_gross": net, "bpjs_emp_total": 0,
                      "bpjs_er_total": 0, "pph21": 0, "net": net,
                      "bank": {"bank_name": bank, "acc_no": nomor, "acc_name": nama if nomor else ""}})
        tot["salary_earnings"] += net
        tot["gross"] += net
        tot["net"] += net
        tot["employees"] += 1
    run = {"id": rid, "number": f"KND/PAY-{tag.upper()}", "entity_id": eid, "period": period, "status": status,
           "run_type": "regular", "commission_mode": "accrue_then_settle", "totals": tot, "gl_posted": False,
           "journal_id": "", "journal_number": "", "submitted_by": "Uji", "submitted_by_id": "usr_uji_pengaju",
           "created_at": "2026-12-01T01:00:00+00:00"}
    if status == "posted":
        run.update({"journal_date": journal_date, "gl_posted": True, "posted_at": "2026-12-01T02:00:00+00:00"})
    await db.hr_payroll_runs.insert_one(dict(run))
    await db.hr_payslips.insert_many([dict(s) for s in slips])
    return run


async def _diposting(klien, db, siap, tag, **kw):
    """Proses `approved` → posting lewat HTTP (jurnal gaji Dr 6-1000 / Cr 2-1600 bertanggal 2026-11-30)."""
    run = await _proses(db, tag, "approved", **kw)
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/post-gl", headers=siap["adm"])
    assert r.status_code == 200 and r.json()["status"] == "posted", r.text
    assert r.json()["journal_date"] == "2026-11-30"
    return r.json()


def _baris(je):
    return sorted((ln["account_code"], round(ln["debit"], 2), round(ln["credit"], 2)) for ln in je["lines"])


async def _kas_bayar(db, run_id):
    return await db.cash_transactions.find({"ref_type": "payroll_run", "ref_id": run_id}, {"_id": 0}).to_list(10)


async def _jurnal_kas(db, cash_id):
    return await db.journal_entries.find({"source_type": "cash_transaction", "source_id": cash_id,
                                          "status": {"$ne": "void"}}, {"_id": 0}).to_list(10)


async def _bayar(klien, h, run_id, body, kunci=""):
    hdr = {**h, "Idempotency-Key": kunci} if kunci else h
    return await klien.post(f"/api/hr/payroll/runs/{run_id}/pay", json=body, headers=hdr)


# ── U1 — daftar transfer = slip; jumlah = total gaji bersih ──────────────────────────────────────────────────────────
async def test_PYT4_U1_daftar_transfer_sama_dengan_total_bersih(klien, db, siap):
    run = await _diposting(klien, db, siap, "u2")   # proses yang sama dibayar di U2 dan diekspor di U11
    r = await klien.get(f"/api/hr/payroll/runs/{run['id']}/transfer-list", headers=siap["fin"])
    assert r.status_code == 200, r.text
    j = r.json()
    # count 3; total = 5.000.000 + 4.500.000 + 3.250.000 = 12.750.000 = totals.net; tanpa rekening: Cici.
    assert j["count"] == 3 and j["total"] == TOTAL_NOV == run["totals"]["net"] and j["without_account"] == 1
    assert [it["employee_name"] for it in j["items"]] == ["Ani", "Bayu", "Cici"]
    assert [it["no"] for it in j["items"]] == [1, 2, 3]
    assert [(it["bank_name"], it["account_number"], it["amount"], it["cash"]) for it in j["items"]] == [
        ("BCA", "111", 5_000_000, False), ("Mandiri", "222", 4_500_000, False), ("", "", 3_250_000, True)]
    assert j["items"][0]["slip_number"] == "SLIP-U2-1"
    assert j["run"]["status"] == "posted" and j["run"]["entity_id"] == KANDA and j["pay_account"] is None
    # Proses yang belum diposting → 409.
    draf = await _proses(db, "u1draf", "approved", period="2026-08")
    r = await klien.get(f"/api/hr/payroll/runs/{draf['id']}/transfer-list", headers=siap["fin"])
    assert r.status_code == 409 and r.json()["detail"] == "Daftar transfer tersedia setelah penggajian diposting."


# ── U2 — Finance membayar dari R-GAJI: satu kas keluar, satu jurnal Dr 2-1600 / Cr 1-1100 ──────────────────────────
async def test_PYT4_U2_bayar_dari_rekening_gaji(klien, db, siap):
    run = await db.hr_payroll_runs.find_one({"id": "prun_pyt4_u2"}, {"_id": 0})
    r = await _bayar(klien, siap["fin"], run["id"], {"account_id": R_GAJI, "paid_date": "2026-12-01"}, "pyt4-u2")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "paid" and j["pay_account_id"] == R_GAJI and j["paid_date"] == "2026-12-01"
    assert j["paid_by_id"] == siap["fin_user"]["id"]
    assert j["transfer_total"] == TOTAL_NOV and j["transfer_count"] == 3
    kas = await _kas_bayar(db, run["id"])
    assert len(kas) == 1
    k = kas[0]
    assert (k["direction"], k["amount"], k["account_id"], k["txn_date"][:10]) == ("out", TOTAL_NOV, R_GAJI,
                                                                                   "2026-12-01")
    assert j["cash_txn_id"] == k["id"] and j["transfer_total"] == k["amount"]
    jes = await _jurnal_kas(db, k["id"])
    assert len(jes) == 1
    je = jes[0]
    assert je["date"] == "2026-12-01" and je["entity_id"] == KANDA
    assert _baris(je) == [("1-1100", 0, TOTAL_NOV), ("2-1600", TOTAL_NOV, 0)]
    assert j["paid_journal_id"] == je["id"]
    assert await jumlah("journal_entries", {"source_type": "payroll_pay", "source_id": run["id"]}) == 0
    # Saldo 2-1600 untuk proses ini: −12.750.000 (jurnal gaji, Cr) + 12.750.000 (jurnal bayar, Dr) = 0.
    gaji = await db.journal_entries.find_one({"source_type": "payroll_run", "source_id": run["id"],
                                              "status": {"$ne": "void"}}, {"_id": 0})
    saldo = sum(ln["debit"] - ln["credit"] for x in (gaji, je) for ln in x["lines"] if ln["account_code"] == "2-1600")
    assert round(saldo, 2) == 0
    # Kirim ulang → 409, tetap satu kas dan satu jurnal.
    r = await _bayar(klien, siap["fin"], run["id"], {"account_id": R_GAJI, "paid_date": "2026-12-01"}, "pyt4-u2b")
    assert r.status_code == 409 and r.json()["detail"] == f"Penggajian {run['number']} sedang atau sudah dibayar. Muat ulang."
    assert len(await _kas_bayar(db, run["id"])) == 1 and len(await _jurnal_kas(db, k["id"])) == 1
    # Daftar transfer sesudah dibayar memuat rekening sumber dan tanggal bayar.
    r = await klien.get(f"/api/hr/payroll/runs/{run['id']}/transfer-list", headers=siap["fin"])
    assert r.status_code == 200 and r.json()["pay_account"]["id"] == R_GAJI and r.json()["paid_date"] == "2026-12-01"


# ── U2b/U2c — jurnal bayar gagal: kas tersimpan, proses kembali Diposting; ulang memakai kas & jurnal yang sama ─────
async def test_PYT4_U2b_jurnal_gagal_lalu_ulang_dari_panel(klien, db, siap, paksa_jurnal_gagal):
    run = await _diposting(klien, db, siap, "u2gagal")
    async with paksa_jurnal_gagal("sisip", entity_id=KANDA, source_type="cash_transaction"):
        r = await _bayar(klien, siap["adm"], run["id"], {"account_id": R_GAJI, "paid_date": "2026-12-01"})
    assert r.status_code == 409, r.text
    assert "Jurnal pembayaran gaji gagal" in r.json()["detail"]
    doc = await db.hr_payroll_runs.find_one({"id": run["id"]}, {"_id": 0})
    assert doc["status"] == "posted" and doc["pay_gl_status"] == "failed"
    kas = await _kas_bayar(db, run["id"])
    assert len(kas) == 1 and kas[0]["gl_status"] == "failed" and await _jurnal_kas(db, kas[0]["id"]) == []
    # Proses dengan kas pembayaran tidak boleh dianulir (jurnal bayar akan menyusul).
    r = await klien.post(f"/api/hr/payroll/runs/{run['id']}/void", json={"reason": "uji anulir sesudah kas"},
                         headers=siap["adm"])
    assert r.status_code == 409 and "kas pembayaran" in r.json()["detail"], r.text
    # Ulang dari panel Posting Gagal (jenis Transaksi Kas) → jurnal kas terbit, proses menjadi Dibayar.
    r = await klien.post(f"/api/finance/posting-failures/cash_transaction/{kas[0]['id']}/retry", headers=siap["adm"])
    assert r.status_code == 200, r.text
    doc = await db.hr_payroll_runs.find_one({"id": run["id"]}, {"_id": 0})
    assert doc["status"] == "paid" and doc["transfer_total"] == TOTAL_NOV and doc["pay_account_id"] == R_GAJI
    assert len(await _jurnal_kas(db, kas[0]["id"])) == 1 and len(await _kas_bayar(db, run["id"])) == 1


async def test_PYT4_U2c_jurnal_gagal_lalu_bayar_ulang(klien, db, siap, paksa_jurnal_gagal):
    run = await _diposting(klien, db, siap, "u2ulang")
    async with paksa_jurnal_gagal("sisip", entity_id=KANDA, source_type="cash_transaction"):
        r = await _bayar(klien, siap["adm"], run["id"], {"account_id": R_GAJI, "paid_date": "2026-12-01"})
    assert r.status_code == 409, r.text
    r = await _bayar(klien, siap["adm"], run["id"], {"account_id": R_GAJI, "paid_date": "2026-12-01"})
    assert r.status_code == 200 and r.json()["status"] == "paid", r.text
    kas = await _kas_bayar(db, run["id"])
    assert len(kas) == 1 and r.json()["cash_txn_id"] == kas[0]["id"]
    assert len(await _jurnal_kas(db, kas[0]["id"])) == 1


# ── U3 — rekening tanpa peruntukan Gaji ditolak sebelum tulisan ─────────────────────────────────────────────────────
async def test_PYT4_U3_rekening_bukan_gaji_ditolak(klien, db, siap):
    run = await _proses(db, "u3", "posted")
    r = await _bayar(klien, siap["fin"], run["id"], {"account_id": R_OPS, "paid_date": "2026-12-01"})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == ("Rekening R-OPS Mandiri Kanda tidak ditandai untuk pembayaran gaji. Pilih rekening "
                                  "lain, atau tambahkan peruntukan Gaji di Rekening & Saldo.")
    assert (await db.hr_payroll_runs.find_one({"id": run["id"]}))["status"] == "posted"
    assert await _kas_bayar(db, run["id"]) == []
    assert await jumlah("journal_entries", {"source_id": run["id"]}) == 0


# ── U4 — rekening kosong: satu rekening gaji dipakai; dua rekening gaji → harus memilih ────────────────────────────
async def test_PYT4_U4_rekening_kosong_satu_dipakai_dua_ditolak(klien, db, siap):
    run = await _diposting(klien, db, siap, "u4a")
    # `cash_account` (kode akun) tidak lagi dibaca: tetap dibayar dari rekening gaji (Cr 1-1100), bukan 1-1200.
    r = await _bayar(klien, siap["fin"], run["id"], {"cash_account": "1-1200"})
    assert r.status_code == 200, r.text
    assert r.json()["pay_account_id"] == R_GAJI and r.json()["paid_date"] == "2026-12-02"   # bawaan: hari ini WIB
    je = (await _jurnal_kas(db, r.json()["cash_txn_id"]))[0]
    assert _baris(je) == [("1-1100", 0, TOTAL_NOV), ("2-1600", TOTAL_NOV, 0)]
    await db.bank_accounts.update_one({"id": R_OPS}, {"$set": {"purposes": ["gaji", "operasional"]}})
    try:
        kedua = await _proses(db, "u4b", "posted")
        r = await _bayar(klien, siap["fin"], kedua["id"], {})
        assert r.status_code == 400 and r.json()["detail"] == "Pilih rekening pembayaran gaji.", r.text
        assert (await db.hr_payroll_runs.find_one({"id": kedua["id"]}))["status"] == "posted"
        assert await _kas_bayar(db, kedua["id"]) == []
    finally:
        await db.bank_accounts.update_one({"id": R_OPS}, {"$set": {"purposes": ["operasional"]}})


# ── U5 — rekening milik PT lain / nonaktif ──────────────────────────────────────────────────────────────────────────
async def test_PYT4_U5_rekening_pt_lain_atau_nonaktif(klien, db, siap):
    lain = await _rekening(db, "rek_pyt4_ksc", KSC, "Gaji KSC", purposes=["gaji"])
    mati = await _rekening(db, "rek_pyt4_mati", KANDA, "Gaji lama Kanda", purposes=["gaji"], aktif=False)
    run = await _proses(db, "u5", "posted")
    for rek in (lain, mati):
        r = await _bayar(klien, siap["fin"], run["id"], {"account_id": rek, "paid_date": "2026-12-01"})
        assert r.status_code == 400, r.text
        assert r.json()["detail"] == "Rekening ini bukan rekening aktif PT penggajian."
    assert await _kas_bayar(db, run["id"]) == []


# ── U6 — tanggal bayar sebelum tanggal jurnal gaji ──────────────────────────────────────────────────────────────────
async def test_PYT4_U6_tanggal_bayar_sebelum_jurnal_gaji(klien, db, siap):
    run = await _proses(db, "u6", "posted")
    r = await _bayar(klien, siap["fin"], run["id"], {"account_id": R_GAJI, "paid_date": "2026-11-15"})
    assert r.status_code == 400 and r.json()["detail"] == "Tanggal bayar tidak boleh sebelum 2026-11-30.", r.text
    r = await _bayar(klien, siap["fin"], run["id"], {"account_id": R_GAJI, "paid_date": "1 Des"})
    assert r.status_code == 400 and r.json()["detail"] == "Tanggal bayar tidak dikenali (TTTT-BB-HH).", r.text
    assert await _kas_bayar(db, run["id"]) == []


# ── U7 — periode tanggal bayar tertutup ─────────────────────────────────────────────────────────────────────────────
async def test_PYT4_U7_periode_tertutup_409(klien, db, siap, paksa_jurnal_gagal):
    run = await _proses(db, "u7", "posted")
    async with paksa_jurnal_gagal("periode", entity_id=KANDA, period_key="2026-12"):
        r = await _bayar(klien, siap["fin"], run["id"], {"account_id": R_GAJI, "paid_date": "2026-12-01"})
    assert r.status_code == 409 and "ditutup" in r.json()["detail"].lower(), r.text
    assert (await db.hr_payroll_runs.find_one({"id": run["id"]}))["status"] == "posted"
    assert await _kas_bayar(db, run["id"]) == []


# ── U8 — gaji bersih negatif ────────────────────────────────────────────────────────────────────────────────────────
async def test_PYT4_U8_gaji_bersih_negatif_409(klien, db, siap):
    run = await _proses(db, "u8", "posted", slip=SLIP_NOV + [("Dedi", -100_000, "BRI", "444")])
    r = await _bayar(klien, siap["fin"], run["id"], {"account_id": R_GAJI, "paid_date": "2026-12-01"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == ("Gaji bersih Dedi negatif (-Rp 100.000). Perbaiki potongannya lewat proses baru "
                                  "sebelum membayar.")
    assert (await db.hr_payroll_runs.find_one({"id": run["id"]}))["status"] == "posted"
    assert await _kas_bayar(db, run["id"]) == []


# ── U9 — Finance: antrean, rekening, setoran; bukan data karyawan ───────────────────────────────────────────────────
# K-SDM-01 (pemilik 17 Nov 2026: "SDM/HR itu dipegang finance juga") — Finance BAWAAN kini juga memegang izin SDM
# (`permissions_config.KSDM01_DEFAULT_PAIRS`). Bagian "bukan data karyawan" PY-T4 tetap berlaku untuk pemegang
# `payroll.pay` SAJA (mis. peran kasir kustom): diuji dengan peran itu; Finance bawaan membuka proses & karyawan.
async def test_PYT4_U9_finance_bayar_tanpa_data_karyawan(klien, db, siap, akun, sesi, peran_tanpa_acuan):
    r = await klien.get("/api/hr/payroll/runs/prun_pyt4_u3", headers=siap["fin"])
    assert r.status_code == 200, r.text   # K-SDM-01 — Finance bawaan: hr.view
    r = await klien.get("/api/hr/employees", headers=siap["fin"])
    assert r.status_code == 200, r.text
    kasir = await peran_tanpa_acuan({"payroll": ["pay"]}, label="Kasir gaji")
    h = await sesi(await akun(kasir, entitas=(KANDA,)), entitas=KANDA)
    r = await klien.get("/api/hr/payroll/pay-queue", headers=h)
    assert r.status_code == 200, r.text
    q = r.json()
    ids = [it["id"] for it in q["items"]]
    assert q["total"] == len(ids) and "prun_pyt4_u3" in ids and "prun_pyt4_u2" not in ids   # u2 sudah dibayar
    it = next(x for x in q["items"] if x["id"] == "prun_pyt4_u3")
    # Kolom spesifikasi + `entity_id` dan `journal_date` (pop-up Bayar: PT dan batas awal tanggal bayar); tanpa slip.
    assert set(it) == {"id", "number", "period", "run_type", "employees", "net_total", "posted_at", "entity_id",
                       "journal_date"}
    assert it["journal_date"] == "2026-11-30"
    assert (it["employees"], it["net_total"], it["period"]) == (3, TOTAL_NOV, NOV)
    r = await klien.get("/api/hr/payroll/pay-accounts", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == [{"id": R_GAJI, "name": "R-GAJI BCA Kanda", "bank_name": "BCA", "account_number": "7001",
                         "holder_name": f"PT {KANDA}", "cash_type": "kas_besar"}]
    r = await klien.get("/api/hr/payroll/runs/prun_pyt4_u3", headers=h)
    assert r.status_code == 403, r.text
    r = await klien.get("/api/hr/employees", headers=h)
    assert r.status_code == 403, r.text
    r = await klien.get("/api/hr/payroll/remittances/outstanding", params={"year": 2026}, headers=h)
    assert r.status_code == 200, r.text
    y = r.json()
    assert y["year"] == 2026 and [k["kind"] for k in y["kinds"]] == ["bpjs", "pph21"]
    for k in y["kinds"]:
        assert [row["period"] for row in k["rows"]] == [f"2026-{m:02d}" for m in range(1, 13)]
    r = await klien.get("/api/hr/payroll/remittances", headers=h)
    assert r.status_code == 200, r.text


# ── U10 — peran kustom "HR": menyiapkan saja ────────────────────────────────────────────────────────────────────────
async def test_PYT4_U10_peran_hr_kustom_hanya_menyiapkan(klien, db, siap):
    await db.hr_employees.insert_one({
        "id": "emp_pyt4_hr", "name": "Karyawan Kanda", "entity_id": KANDA, "status": "active", "base_salary": 4_000_000,
        "allowances": 0, "ptkp_status": "TK0", "bpjs_kes_enabled": False, "bpjs_tk_enabled": False,
        "join_date": "2026-01-01", "created_at": "2026-01-01T00:00:00+00:00"})
    h = siap["hrx"]
    r = await klien.post("/api/hr/payroll/runs", json={"entity_id": KANDA, "period": "2026-09"}, headers=h)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]
    r = await klien.post(f"/api/hr/payroll/runs/{rid}/submit", headers=h)
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/hr/payroll/runs/{rid}/approve", headers=h)
    assert r.status_code == 403, r.text
    r = await _bayar(klien, h, "prun_pyt4_u3", {"account_id": R_GAJI})
    assert r.status_code == 403, r.text
    r = await klien.get("/api/hr/payroll/runs/prun_pyt4_u3/transfer-list", headers=h)
    assert r.status_code == 403, r.text


# ── U11 — unduh daftar transfer (.xlsx) + jejak audit tanpa nominal ────────────────────────────────────────────────
async def test_PYT4_U11_unduh_excel_daftar_transfer(klien, db, siap):
    from openpyxl import load_workbook
    run = await db.hr_payroll_runs.find_one({"id": "prun_pyt4_u2"}, {"_id": 0})
    assert run["status"] == "paid"
    r = await klien.get(f"/api/hr/payroll/runs/{run['id']}/transfer-list/export", headers=siap["fin"])
    assert r.status_code == 200, r.text
    assert "spreadsheetml" in r.headers["content-type"]
    assert f'filename="transfer-gaji-{run["number"].replace("/", "-")}.xlsx"' in r.headers["content-disposition"]
    ws = load_workbook(io.BytesIO(r.content)).active
    rows = [[c for c in row] for row in ws.iter_rows(values_only=True)]
    kepala = next(i for i, row in enumerate(rows) if row and row[0] == "No.")
    assert list(rows[kepala][:6]) == ["No.", "Nama penerima", "Bank", "Nomor rekening", "Nominal", "Berita"]
    isi = rows[kepala + 1:kepala + 4]
    assert [(x[1], x[4]) for x in isi] == [("Ani", 5_000_000), ("Bayu", 4_500_000), ("Cici", 3_250_000)]
    assert all("Gaji November 2026" in x[5] for x in isi)
    total = rows[kepala + 4]
    assert total[1] == "Total" and total[4] == TOTAL_NOV
    teks = " | ".join(str(c) for row in rows[:kepala] for c in row if c)
    assert "R-GAJI BCA Kanda" in teks and "2026-12-01" in teks and run["number"] in teks
    log = await db.audit_logs.find({"action": "hr.payroll.transfer_export", "entity_id": run["id"]},
                                   {"_id": 0}).to_list(10)
    assert len(log) == 1
    assert not any(k in (log[0].get("after") or {}) for k in ("total", "amount", "items", "net"))


# ── U12 — batalkan setoran yang salah catat ─────────────────────────────────────────────────────────────────────────
async def test_PYT4_U12_batal_setoran_bpjs(klien, db, siap):
    # Proses Oktober berkewajiban BPJS 900.000 (karyawan 360.000 + perusahaan 540.000).
    await _proses(db, "u12okt", "posted", period=OKT, journal_date="2026-10-31", bpjs=(360_000, 540_000))
    adm = siap["adm"]
    r = await klien.post("/api/hr/payroll/remittances", headers={**adm, "Idempotency-Key": "pyt4-u12"}, json={
        "kind": "bpjs", "period": OKT, "amount": 900_000, "paid_date": "2026-11-10", "account_id": R_GAJI,
        "cash_type": "kas_besar", "reference": "BPJS-OKT"})
    assert r.status_code == 200 and r.json()["status"] == "done", r.text
    st = r.json()
    # K-FIN-01 (pemilik 17 Nov 2026 malam) — Finance kini juga boleh membatalkan setoran (`payroll.void` Manajer; dulu
    # 403): permintaannya sampai ke pemeriksaan alasan, bukan ditolak izin.
    r = await klien.post(f"/api/hr/payroll/remittances/{st['id']}/void", json={"reason": "uji"}, headers=siap["fin"])
    assert r.status_code == 400 and r.json()["detail"] == "Alasan wajib diisi (minimal 5 huruf).", r.text
    r = await klien.post(f"/api/hr/payroll/remittances/{st['id']}/void", json={"reason": "uji"}, headers=adm)
    assert r.status_code == 400 and r.json()["detail"] == "Alasan wajib diisi (minimal 5 huruf).", r.text
    r = await klien.post(f"/api/hr/payroll/remittances/{st['id']}/void", json={"reason": "salah catat nominal"},
                         headers={**adm, "Idempotency-Key": "pyt4-u12-void"})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["status"] == "void" and v["void_reason"] == "salah catat nominal" and v["voided_by"]
    kas = await db.cash_transactions.find_one({"id": st["cash_txn_id"]}, {"_id": 0})
    assert kas["status"] == "void"
    rev = await db.journal_entries.find({"source_type": "cash_transaction_void", "source_id": kas["id"],
                                         "status": {"$ne": "void"}}, {"_id": 0}).to_list(5)
    assert len(rev) == 1 and v["void_journal_id"] == rev[0]["id"]
    # Pembalik jurnal setoran (Dr 2-1700 / Cr 1-1100): Dr 1-1100 900.000 / Cr 2-1700 900.000, bertanggal setoran.
    assert _baris(rev[0]) == [("1-1100", 900_000, 0), ("2-1700", 0, 900_000)] and rev[0]["date"] == "2026-11-10"
    r = await klien.get("/api/hr/payroll/remittances/outstanding", params={"period": OKT}, headers=adm)
    assert (r.json()["bpjs"]["kewajiban"], r.json()["bpjs"]["disetor"], r.json()["bpjs"]["sisa"]) == (900_000, 0, 900_000)
    r = await klien.get("/api/hr/payroll/remittances/outstanding", params={"year": 2026}, headers=siap["fin"])
    okt = next(x for x in r.json()["kinds"][0]["rows"] if x["period"] == OKT)
    assert (okt["kewajiban"], okt["disetor"], okt["sisa"]) == (900_000, 0, 900_000)
    r = await klien.post(f"/api/hr/payroll/remittances/{st['id']}/void", json={"reason": "salah catat nominal"},
                         headers=adm)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == f"Setoran {st['number']} berstatus Dibatalkan, jadi tidak bisa dibatalkan."


# ── U13 — PT tanpa rekening berperuntukan Gaji ──────────────────────────────────────────────────────────────────────
async def test_PYT4_U13_pt_tanpa_rekening_gaji(klien, db, sesi):
    eid = await pt_uji("PY4N")
    await _rekening(db, "rek_pyt4_n_ops", eid, "Operasional PY4N", purposes=["operasional"])
    run = await _proses(db, "u13", "posted", eid=eid)
    h = await sesi("admin@kainnusantara.id", entitas=eid)
    r = await klien.get("/api/hr/payroll/pay-accounts", headers=h)
    assert r.status_code == 200 and r.json() == [], r.text
    r = await _bayar(klien, h, run["id"], {"paid_date": "2026-12-01"})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == ("Belum ada rekening berperuntukan Gaji di PT ini. Atur di Keuangan › Kas & Bank › "
                                  "Rekening & Saldo.")
    assert await _kas_bayar(db, run["id"]) == []


# ── U15 — Manajer Kosong dan Sopir: 403 berkalimat (Z6) ─────────────────────────────────────────────────────────────
async def test_PYT4_U15_manajer_kosong_dan_sopir_ditolak(klien, db, siap, akun, sesi, peran_manajer_kosong,
                                                         peran_sopir):
    for peran in (await peran_manajer_kosong(), peran_sopir):
        h = await sesi(await akun(peran, entitas=(KANDA,)), entitas=KANDA)
        for r in (await klien.get("/api/hr/payroll/pay-queue", headers=h),
                  await klien.get("/api/hr/payroll/pay-accounts", headers=h),
                  await klien.get("/api/hr/payroll/runs/prun_pyt4_u3/transfer-list", headers=h),
                  await klien.get("/api/hr/payroll/runs/prun_pyt4_u3/transfer-list/export", headers=h),
                  await _bayar(klien, h, "prun_pyt4_u3", {"account_id": R_GAJI})):
            assert r.status_code == 403, (peran, r.text)
            assert r.json()["detail"].startswith("Anda belum punya akses") and MODUL in r.json()["detail"], r.text
            assert "payroll" not in r.json()["detail"]
    assert (await db.hr_payroll_runs.find_one({"id": "prun_pyt4_u3"}))["status"] == "posted"


# ── U9b (tambahan) — izin bayar gaji tidak membuka menu SDM lain (menu peran bawaan tetap bertambah dari izin, PR-T6) ──
# K-SDM-01 — Finance bawaan kini memegang izin SDM, jadi "izin bayar saja" diuji pada izin Finance tanpa `hr` dan
# dengan `payroll` = bayar saja (bentuk PY-T4).
async def test_PYT4_U9b_menu_finance_hanya_setoran_dan_pajak(klien, siap):
    from access_modules import apply_levels, nav_allowed_for_perms
    from permissions_config import DEFAULT_PERMISSIONS
    bayar_saja = {k: v for k, v in DEFAULT_PERMISSIONS["finance"].items() if k != "hr"}
    bayar_saja["payroll"] = ["pay"]
    dasar = set(nav_allowed_for_perms(bayar_saja))
    assert {"hr-payroll-hub", "hr-payroll-remittances"} <= dasar
    assert not dasar & {"hr-people", "hr-employees", "hr-payroll-runs", "hr-pay-components", "settings-hr"}
    tambah = set(nav_allowed_for_perms(apply_levels(bayar_saja, {"hr": "view"}))) - dasar
    assert {"hr-people", "hr-employees", "hr-payroll-runs", "settings-hr"} <= tambah
    sdm = set(nav_allowed_for_perms(DEFAULT_PERMISSIONS["finance"]))   # K-SDM-01 — bawaan Finance
    assert {"hr-people", "hr-employees", "hr-payroll-runs", "hr-pay-components", "settings-hr", "settings-cfg-hr"} <= sdm
    r = await klien.get("/api/auth/me", headers=siap["fin"])
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["view_actions"]["hr-payroll-remittances"] == [["hr", "view"], ["payroll", "pay"]]
    assert ["hr", "view"] in me["view_actions"]["hr-people"] and ["payroll", "pay"] not in me["view_actions"]["hr-people"]

"""KB-1 Tugas 3 — alat pindah saldo per PT: pratinjau, siapkan, setujui (hitung ulang + sidik), tolak.

Rancangan: `docs/superpowers/specs/2026-11-27-kas-bank-1-rekening-pindah-dana-design.md` §5.3, §6, §7 butir 8 (2–5).
Ketetapan pengendali: R8a (gaji jalur lama tanpa kas menghalangi siapkan & setujui), R8b (saldo dipindah dari baris yang
SAMA dengan yang kelak dialihkan pembalik `gl_service.baris_kas_rekening`; kas kembar antar-PT lewat rujukan), R6 (kas
tanpa dokumen tetap di akun lama), (a) kas yang tercatat selama persetujuan masuk tepat satu ember, (b) posting dokumen
yang kasnya menumpang jurnal induk ikut dihitung "gagal/tertunda".

Tiap uji memakai PT uji sendiri (`pt_uji`), rekening lewat `bank_service.create_account` (saldo awal berjurnal).
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from fastapi import HTTPException

from core_utils import now_iso
from pembantu import AKTOR_UJI, pt_uji, saldo_akun

pytestmark = pytest.mark.anyio

PENYIAP = {"id": "usr_kb3_siap", "name": "Sinta Penyiap", "role": "finance", "email": "sinta.kb3@uji.id"}
PENYETUJU = {"id": "usr_kb3_setuju", "name": "Bayu Penyetuju", "role": "finance", "email": "bayu.kb3@uji.id"}
PESAN_ANGKA = "Angka berubah, muat ulang."


def _uid(awal: str) -> str:
    return f"{awal}_kb3_{uuid.uuid4().hex[:8]}"


async def _saldo(kode: str, eid: str) -> float:
    return round(await saldo_akun(kode, eid), 2)


async def _rekening(eid: str, nama: str, jenis_akun: str = "bank", jenis_kas: str = "", awal: float = 0.0) -> str:
    from schemas_finance import BankAccountCreate
    from services import bank_service
    acc = await bank_service.create_account(
        BankAccountCreate(name=nama, account_type=jenis_akun, cash_type=jenis_kas, entity_id=eid,
                          opening_balance=awal), AKTOR_UJI)
    return acc["id"]


async def _kas(eid: str, rekening: str, arah: str, nominal: float, kategori: str = "modal") -> dict:
    from services import cash_ledger
    return await cash_ledger.create_cash(entity_id=eid, direction=arah, amount=nominal, ref_type="manual",
                                         ref_id=_uid("man"), account_id=rekening, category=kategori,
                                         description=f"Uji KB3 {kategori}", actor="Uji")


async def _kas_tanpa_rekening(db, eid: str, jenis_kas: str, arah: str, nominal: float) -> dict:
    """Kas LAMA tanpa rekening (sebelum PK-20) + jurnal kasnya (akun jenis kas lama)."""
    from services import gl_service as gl
    t = {"id": _uid("cash_lama"), "number": _uid("CASH"), "entity_id": eid, "cash_type": jenis_kas,
         "direction": arah, "amount": nominal, "category": "lain", "description": "Kas lama KB3", "account_id": "",
         "ref_type": "manual", "ref_id": _uid("lama"), "status": "posted", "gl_status": "pending",
         "txn_date": now_iso(), "created_at": now_iso(), "updated_at": now_iso()}
    await db.cash_transactions.insert_one(dict(t))
    await gl.post_cash_durable(t)
    return t


async def _batal_api(klien, kepala_admin, eid: str, kas_id: str, alasan: str = "uji batal KB3") -> None:
    """Batal kas lewat `POST /api/cash-transactions/{id}/void` (Admin, PT uji aktif di kepala)."""
    from services.entity_lifecycle_service import invalidate_status_cache
    invalidate_status_cache()   # PT uji baru harus terlihat di penugasan Admin (cache status PT)
    res = await klien.post(f"/api/cash-transactions/{kas_id}/void", headers={**kepala_admin, "X-Entity-Id": eid},
                           json={"reason": alasan})
    assert res.status_code == 200, res.text


def _baris(je: dict) -> list:
    return [(ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]]


def _asal(rek: dict) -> dict:
    return {a["akun"]: a["jumlah"] for a in rek["asal"]}


def _rek(hasil: dict, rid: str) -> dict:
    return next(r for r in hasil["rekening"] if r["id"] == rid)


async def _pt_lengkap(db, kode: str) -> tuple:
    """PT dengan empat rekening + kas lama:
    A bank (saldo awal 1.000.000 → Dr 1-1100), B kas tunai berjenis KAS BESAR (saldo awal 300.000 → Dr 1-1110 menurut
    jenis rekening — saldo awal di akun berbeda), K kas kecil, Z bank tanpa mutasi. Kas: A +500.000 (1-1100), A −200.000
    saat pemetaan PT kas besar → 1-1101 (Cr 1-1101), B +100.000 (1-1100), K −50.000 (1-1110), kas lama tanpa rekening
    kas kecil −20.000 (K rekening kas kecil TUNGGAL → ikut K) dan kas besar +40.000 (tiga rekening kas besar →
    tetap)."""
    from schemas_finance import GLAccountCreate
    from services import gl_mapping_service as glm
    from services import gl_service as gl
    eid = await pt_uji(kode)
    await gl.create_account(GLAccountCreate(code="1-1101", name=f"Bank Umum {kode}", type="asset",
                                            parent_code="1-1000"), entity_id=eid)
    r = {"A": await _rekening(eid, f"BCA {kode}", awal=1_000_000),
         "B": await _rekening(eid, f"Kas Toko {kode}", "cash", "kas_besar", awal=300_000),
         "K": await _rekening(eid, f"Kas Kecil {kode}", "cash", "kas_kecil"),
         "Z": await _rekening(eid, f"Mandiri {kode}")}
    await _kas(eid, r["A"], "in", 500_000)
    await glm.set_mapping("kas_bank.kas_besar", eid, "1-1101", "uji KB3 pemetaan PT", AKTOR_UJI)
    try:
        await _kas(eid, r["A"], "out", 200_000, "sewa")
    finally:
        await glm.reset_mapping("kas_bank.kas_besar", eid, "pulihkan uji KB3", AKTOR_UJI)
    await _kas(eid, r["B"], "in", 100_000)
    await _kas(eid, r["K"], "out", 50_000, "sewa")
    lama_kk = await _kas_tanpa_rekening(db, eid, "kas_kecil", "out", 20_000)
    lama_kb = await _kas_tanpa_rekening(db, eid, "kas_besar", "in", 40_000)
    return eid, r, {"kk": lama_kk, "kb": lama_kb}


async def _siapkan_setujui(eid: str, pilihan: dict = None) -> dict:
    from services import cash_account_cutover_service as cut
    u = await cut.siapkan(eid, pilihan or {}, PENYIAP)
    p = await cut.pratinjau(eid)
    return await cut.setujui(u["id"], p["sidik"], PENYETUJU)


# ═══ 1. Pratinjau = buku kas rekening per akun asal (saldo awal di akun lain, pemetaan PT), tanpa tulisan ══════════
async def test_KB1_3_U1_pratinjau_per_akun_asal_tanpa_tulisan(db):
    from services import bank_service, cash_account_cutover_service as cut
    eid, r, lama = await _pt_lengkap(db, "KB3A")
    sebelum = (await db.gl_accounts.count_documents({}), await db.journal_entries.count_documents({}),
               await db.cash_account_cutovers.count_documents({}))
    p = await cut.pratinjau(eid)
    assert sebelum == (await db.gl_accounts.count_documents({}), await db.journal_entries.count_documents({}),
                       await db.cash_account_cutovers.count_documents({}))
    assert [x["id"] for x in p["rekening"]] == [r["A"], r["B"], r["K"], r["Z"]]
    assert {x["id"]: (x["akun_tujuan"], x["akun_tujuan_baru"], x["cash_type"]) for x in p["rekening"]} == {
        r["A"]: ("1-1100-01", True, "kas_besar"), r["B"]: ("1-1100-02", True, "kas_besar"),
        r["K"]: ("1-1110-01", True, "kas_kecil"), r["Z"]: ("1-1100-03", True, "kas_besar")}
    assert _asal(_rek(p, r["A"])) == {"1-1100": 1_500_000.0, "1-1101": -200_000.0}
    assert _asal(_rek(p, r["B"])) == {"1-1100": 100_000.0, "1-1110": 300_000.0}
    assert _asal(_rek(p, r["K"])) == {"1-1110": -70_000.0}
    assert _asal(_rek(p, r["Z"])) == {}
    for rid in r.values():   # pratinjau = buku kas rekening itu
        x = _rek(p, rid)
        assert x["saldo_buku"] == (await bank_service.account_ledger(rid))["balance"] == x["dipindah"], x
        assert x["selisih"] == 0.0, x
    assert p["kas_tanpa_rekening"]["tunggal"][0]["kas_ids"] == [lama["kk"]["id"]]
    ktr = p["kas_tanpa_rekening"]
    assert (ktr["tunggal"][0]["rekening_id"], ktr["tetap"]) == (r["K"], 40_000.0)
    assert {a["akun"]: (a["saldo"], a["dipindah"], a["sisa"]) for a in p["akun_lama"]} == {
        "1-1100": (1_640_000.0, 1_600_000.0, 40_000.0), "1-1101": (-200_000.0, -200_000.0, 0.0),
        "1-1110": (230_000.0, 230_000.0, 0.0)}
    assert p["posting_gagal"] == 0 and p["aktif"] is False
    assert [(b["account_code"], b["debit"], b["credit"]) for b in p["baris_jurnal"]] == [
        ("1-1100-01", 1_500_000.0, 0.0), ("1-1100", 0.0, 1_500_000.0),
        ("1-1101", 200_000.0, 0.0), ("1-1100-01", 0.0, 200_000.0),       # asal negatif → sisi dibalik
        ("1-1100-02", 100_000.0, 0.0), ("1-1100", 0.0, 100_000.0),
        ("1-1100-02", 300_000.0, 0.0), ("1-1110", 0.0, 300_000.0),
        ("1-1110", 70_000.0, 0.0), ("1-1110-01", 0.0, 70_000.0)]          # rekening negatif · Z (nol) dilewati
    assert p["sidik"] == (await cut.pratinjau(eid))["sidik"]          # sidik stabil


# ═══ 2. Setujui → jurnal seimbang bertanggal hari ini, akun lama 0, sub-akun = buku kas, mode menyala, kas tunggal ═══
async def test_KB1_3_U2_setujui_lengkap(db):
    from services import bank_service, cash_account_mode as mode, cash_account_cutover_service as cut
    from services.book_date import tanggal_buku
    eid, r, lama = await _pt_lengkap(db, "KB3B")
    u = await cut.siapkan(eid, {}, PENYIAP)
    assert u["status"] == "menunggu" and not await mode.aktif(eid)
    kode = {x["id"]: x["akun_tujuan"] for x in (await cut.pratinjau(eid))["rekening"]}
    assert kode == {r["A"]: "1-1100-01", r["B"]: "1-1100-02", r["K"]: "1-1110-01", r["Z"]: "1-1100-03"}
    assert all(not x["akun_tujuan_baru"] for x in (await cut.pratinjau(eid))["rekening"])   # sub-akun sudah dibuat
    hasil = await cut.setujui(u["id"], (await cut.pratinjau(eid))["sidik"], PENYETUJU)   # tanpa selisih: tanpa centang
    assert hasil["status"] == "disetujui", hasil
    assert (hasil["selisih_diperiksa"], hasil["selisih_disetujui"]) == (False, [])
    assert await mode.aktif(eid)
    je = await db.journal_entries.find_one({"source_type": "pindah_saldo_kas", "source_id": u["id"]}, {"_id": 0})
    assert je and je["total_debit"] == je["total_credit"] == 2_170_000.0 and je["entity_id"] == eid
    assert je["date"] == tanggal_buku() and je["id"] == hasil["journal_entry_id"]
    assert {ln["account_code"]: ln["account_name"] for ln in je["lines"]}["1-1100-01"] == "BCA KB3B"
    assert not any(ln["account_code"] == "1-1100-03" for ln in je["lines"])   # rekening nol dilewati
    for rid in r.values():
        assert await _saldo(kode[rid], eid) == (await bank_service.account_ledger(rid))["balance"], rid
    assert (await _saldo("1-1100", eid), await _saldo("1-1101", eid), await _saldo("1-1110", eid)) == (
        40_000.0, 0.0, 0.0)   # sisa 1-1100 = kas lama tanpa rekening yang tidak tunggal (tetap di akun lama)
    t = await db.cash_transactions.find_one({"id": lama["kk"]["id"]}, {"_id": 0})
    assert (t["account_id"], t["account_id_dari_pindah_saldo"]) == (r["K"], u["id"])
    assert (await db.cash_transactions.find_one({"id": lama["kb"]["id"]}, {"_id": 0}))["account_id"] == ""
    # kas baru sesudah aktif → sub-akun
    k = await _kas(eid, r["A"], "in", 10_000)
    assert ("1-1100-01", 10_000.0, 0.0) in _baris(await db.journal_entries.find_one(
        {"source_type": "cash_transaction", "source_id": k["id"]}, {"_id": 0}))
    # PT sudah aktif → tidak bisa disiapkan lagi; usulan yang sudah diputus tidak bisa disetujui lagi
    with pytest.raises(HTTPException) as e:
        await cut.siapkan(eid, {}, PENYIAP)
    assert e.value.status_code == 409 and "sudah memakai akun buku besar per rekening" in e.value.detail
    with pytest.raises(HTTPException) as e:
        await cut.setujui(u["id"], hasil["sidik_disetujui"], PENYETUJU)
    assert e.value.status_code == 409


# ═══ 3. Siapkan ditolak bila posting kas gagal/tertunda (kas, dokumen induk, R8a gaji jalur lama) ═════════════════════
async def test_KB1_3_U3_siapkan_ditolak_posting_kas_gagal(db, paksa_jurnal_gagal):
    from services import cash_account_cutover_service as cut, cash_ledger, posting_registry as reg
    eid = await pt_uji("KB3C")
    bank = await _rekening(eid, "BCA KB3C")
    async with paksa_jurnal_gagal("sisip", entity_id=eid, source_type="cash_transaction"):
        with pytest.raises(cash_ledger.CashPostingError) as gagal:
            await _kas(eid, bank, "in", 75_000)
    with pytest.raises(HTTPException) as e:
        await cut.siapkan(eid, {}, PENYIAP)
    assert e.value.status_code == 409
    assert e.value.detail == ("Uji KB3C masih punya 1 posting kas yang gagal atau tertunda (Transaksi Kas: 1). "
                              "Selesaikan dulu di Keuangan › Posting Gagal, lalu ulangi."), e.value.detail
    assert not await db.cash_account_cutovers.find_one({"entity_id": eid})
    assert not await db.gl_accounts.find_one({"entity_id": eid, "bank_account_id": bank})   # tanpa sub-akun
    assert (await cut.pratinjau(eid))["posting_gagal"] == 1
    # Dokumen induk yang kasnya menumpang jurnalnya (nota kredit refund) gagal + kas kembar menunggu jurnal induk
    await db.credit_notes.insert_one({"id": _uid("cn"), "entity_id": eid, "number": "CN/KB3C/1",
                                      "gl_status": "failed", "gl_error": "uji", "gross_amount": 10_000})
    await db.cash_transactions.insert_one({
        "id": _uid("cash_kembar"), "entity_id": eid, "account_id": bank, "cash_type": "kas_besar", "direction": "in",
        "amount": 5_000, "status": "posted", "gl_status": "not_required", "gl_posted": True,
        "parent_journal": "interco_loan:pair_kb3c_tanpa_jurnal", "created_at": now_iso()})
    p = await cut.pratinjau(eid)
    assert p["posting_gagal"] == 3, p["posting_gagal_rincian"]
    assert {x["jenis"]: x["jumlah"] for x in p["posting_gagal_rincian"]} == {
        "cash_transaction": 1, "credit_note": 1, "kas_tanpa_jurnal_induk": 1}
    # Ulang posting kas → hitungan turun
    await reg.KINDS["cash_transaction"]["retry"](gagal.value.txn, AKTOR_UJI)
    assert (await cut.pratinjau(eid))["posting_gagal"] == 2


async def test_KB1_3_U3b_gaji_jalur_lama_tanpa_kas_menghalangi(db):
    """R8a — proses gaji yang jurnal `payroll_pay`-nya (jalur lama) sudah terbit tetapi kasnya belum tercatat: siapkan
    DAN setujui ditolak (kas yang kelak menumpang jurnal lama akan menurunkan buku kas rekening tanpa sub-akun)."""
    from services import cash_account_cutover_service as cut, gl_service as gl
    eid = await pt_uji("KB3D")
    bank = await _rekening(eid, "BCA KB3D")
    await _kas(eid, bank, "in", 900_000)
    u = await cut.siapkan(eid, {}, PENYIAP)
    run = {"id": _uid("pay"), "entity_id": eid, "period": "2026-10", "status": "posted", "number": "PAY/KB3D/1",
           "journal_date": "2026-10-31", "totals": {"net": 400_000}}
    await db.hr_payroll_runs.insert_one(dict(run))
    await gl._insert_entry(lines=[{"account_code": "2-1600", "debit": 400_000.0, "credit": 0.0},
                                  {"account_code": "1-1100", "debit": 0.0, "credit": 400_000.0}],
                           description="Bayar gaji jalur lama (uji)", date=now_iso(), source_type="payroll_pay",
                           source_id=run["id"], entity_id=eid, created_by="uji")
    pesan = ("Uji KB3D masih punya 1 posting kas yang gagal atau tertunda (Penggajian yang jurnal bayarnya sudah "
             "terbit tetapi kasnya belum tercatat: 1). Selesaikan dulu di Keuangan › Posting Gagal, lalu ulangi.")
    with pytest.raises(HTTPException) as e:
        await cut.setujui(u["id"], (await cut.pratinjau(eid))["sidik"], PENYETUJU)
    assert (e.value.status_code, e.value.detail) == (409, pesan)
    assert (await db.cash_account_cutovers.find_one({"id": u["id"]}))["status"] == "menunggu"
    await cut.tolak(u["id"], "uji gaji jalur lama", PENYETUJU)
    with pytest.raises(HTTPException) as e:
        await cut.siapkan(eid, {}, PENYIAP)
    assert (e.value.status_code, e.value.detail) == (409, pesan)
    # kas gaji tercatat (menumpang jurnal lama) → tidak menghalangi lagi
    await db.cash_transactions.insert_one({
        "id": _uid("cash_gaji"), "entity_id": eid, "account_id": bank, "cash_type": "kas_besar", "direction": "out",
        "amount": 400_000, "status": "posted", "gl_status": "not_required", "gl_posted": True,
        "ref_type": "payroll_run", "ref_id": run["id"], "created_at": now_iso(),
        "parent_journal": (await db.journal_entries.find_one({"source_type": "payroll_pay",
                                                              "source_id": run["id"]}))["id"]})
    assert (await cut.pratinjau(eid))["posting_gagal"] == 0


# ═══ 4. Kas baru sesudah siapkan ikut terhitung saat setuju; sidik lama → 409; penyiap tidak boleh menyetujui ═══════
async def test_KB1_3_U4_sidik_lama_kas_baru_penyiap(db):
    from services import bank_service, cash_account_mode as mode, cash_account_cutover_service as cut
    eid = await pt_uji("KB3E")
    bank = await _rekening(eid, "BCA KB3E", awal=250_000)
    u = await cut.siapkan(eid, {}, PENYIAP)
    sidik_lama = u["sidik_disiapkan"]
    assert sidik_lama == (await cut.pratinjau(eid))["sidik"]
    with pytest.raises(HTTPException) as e:   # penyiap = penyetuju → ditolak (kontrol dua orang)
        await cut.setujui(u["id"], sidik_lama, PENYIAP)
    assert e.value.status_code == 403 and "harus diputuskan orang lain" in e.value.detail
    await _kas(eid, bank, "in", 60_000)   # kas baru sesudah disiapkan
    with pytest.raises(HTTPException) as e:
        await cut.setujui(u["id"], sidik_lama, PENYETUJU)
    assert (e.value.status_code, e.value.detail) == (409, PESAN_ANGKA)
    assert not await mode.aktif(eid) and (await db.cash_account_cutovers.find_one({"id": u["id"]}))["status"] == \
        "menunggu"
    p = await cut.pratinjau(eid)
    assert _asal(_rek(p, bank)) == {"1-1100": 310_000.0} and p["sidik"] != sidik_lama
    hasil = await cut.setujui(u["id"], p["sidik"], PENYETUJU)
    assert hasil["status"] == "disetujui" and hasil["total_dipindah"] == 310_000.0
    assert await _saldo("1-1100-01", eid) == (await bank_service.account_ledger(bank))["balance"] == 310_000.0
    assert await _saldo("1-1100", eid) == 0.0


# ═══ 5. Setujui ganda (bersamaan & berurutan) → satu jurnal, satu penyalaan ══════════════════════════════════════════
async def test_KB1_3_U5_setujui_ganda_satu_jurnal(db):
    from services import cash_account_mode as mode, cash_account_cutover_service as cut
    eid = await pt_uji("KB3F")
    await _rekening(eid, "BCA KB3F", awal=125_000)
    u = await cut.siapkan(eid, {}, PENYIAP)
    sidik = (await cut.pratinjau(eid))["sidik"]
    lain = {**PENYETUJU, "id": "usr_kb3_lain", "name": "Lina Penyetuju"}
    hasil = await asyncio.gather(cut.setujui(u["id"], sidik, PENYETUJU), cut.setujui(u["id"], sidik, lain),
                                 return_exceptions=True)
    ok = [h for h in hasil if isinstance(h, dict)]
    tolak = [h for h in hasil if isinstance(h, HTTPException)]
    assert len(ok) == 1 and len(tolak) == 1 and tolak[0].status_code == 409, hasil
    with pytest.raises(HTTPException) as e:
        await cut.setujui(u["id"], sidik, lain)
    assert e.value.status_code == 409
    assert await db.journal_entries.count_documents({"source_type": "pindah_saldo_kas", "entity_id": eid}) == 1
    penanda = [d[eid] async for d in db.system_settings.find({"scope": mode.SCOPE}) if eid in d]
    assert len(penanda) == 1 and penanda[0]["oleh"] == ok[0]["disetujui_oleh"]


# ═══ 6. Kas yang tercatat / dibatalkan SELAMA persetujuan masuk tepat satu ember (ketetapan (a), tinjauan putaran 1) ═
@pytest.mark.parametrize("kapan", ["sebelum_nyala", "sesudah_nyala", "batal_sesudah_nyala"])
async def test_KB1_3_U6_kas_selama_persetujuan(db, klien, kepala_admin, monkeypatch, kapan):
    """Pindah saldo menghitung ulang SESUDAH penanda waktu `nyalakan` ditulis, dengan batas waktu yang sama dengan
    aturan pembalik Tugas 2. Kas yang dijurnal sebelum penanda → ikut dipindah; sesudahnya → langsung ke sub-akun. Kas
    lama yang DIBATALKAN sesudah penanda tetapi sebelum hitung ulang (probe peninjau T3 putaran 1): pembaliknya sudah
    dialihkan ke sub-akun, jadi jurnal aslinya tetap dipindah → sub-akun = buku kas, akun lama = 0."""
    from services import bank_service, cash_account_mode as mode, cash_account_cutover_service as cut
    eid = await pt_uji(f"KB3G{kapan[:3]}{kapan[-4:]}")
    bank = await _rekening(eid, f"BCA KB3G {kapan}", awal=500_000)
    kas_lama = await _kas(eid, bank, "in", 70_000) if kapan == "batal_sesudah_nyala" else None
    u = await cut.siapkan(eid, {}, PENYIAP)
    sidik = (await cut.pratinjau(eid))["sidik"]
    asli = mode.nyalakan
    tercatat = {}

    async def nyalakan_dengan_kas(entity_id, by):
        if kapan == "sebelum_nyala":
            tercatat["kas"] = await _kas(eid, bank, "in", 70_000)
        await asli(entity_id, by)
        if kapan == "sesudah_nyala":
            tercatat["kas"] = await _kas(eid, bank, "in", 70_000)
        if kapan == "batal_sesudah_nyala":
            await _batal_api(klien, kepala_admin, eid, kas_lama["id"], "batal di jendela")

    monkeypatch.setattr(mode, "nyalakan", nyalakan_dengan_kas)
    hasil = await cut.setujui(u["id"], sidik, PENYETUJU)
    buku = (await bank_service.account_ledger(bank))["balance"]
    if kapan == "batal_sesudah_nyala":
        balik = await db.journal_entries.find_one({"source_type": "cash_transaction_void",
                                                   "source_id": kas_lama["id"]}, {"_id": 0})
        assert ("1-1100-01", 0.0, 70_000.0) in _baris(balik)   # pembalik dialihkan ke sub-akun
        assert hasil["total_dipindah"] == 570_000.0               # jurnal aslinya tetap dipindah
        assert await _saldo("1-1100-01", eid) == buku == 500_000.0
        assert await _saldo("1-1100", eid) == 0.0
        return
    je_kas = await db.journal_entries.find_one({"source_type": "cash_transaction",
                                                "source_id": tercatat["kas"]["id"]}, {"_id": 0})
    if kapan == "sebelum_nyala":
        assert ("1-1100", 70_000.0, 0.0) in _baris(je_kas) and hasil["total_dipindah"] == 570_000.0
        assert hasil["sidik_diposting"] != hasil["sidik_disetujui"]   # angka diposting dicatat, berbeda dari dilihat
    else:
        assert ("1-1100-01", 70_000.0, 0.0) in _baris(je_kas) and hasil["total_dipindah"] == 500_000.0
    assert await _saldo("1-1100-01", eid) == buku == 570_000.0
    assert await _saldo("1-1100", eid) == 0.0


@pytest.mark.parametrize("henti", ["sebelum_rencana", "jurnal_gagal"])
async def test_KB1_3_U6b_diteruskan_sesudah_batal_di_sela(db, klien, kepala_admin, monkeypatch, paksa_jurnal_gagal,
                                                          henti):
    """Persetujuan terhenti SESUDAH `nyalakan` — sebelum niat tersimpan (galat hitung ulang) atau jurnal pindah saldo
    gagal (niat sudah tersimpan) — lalu kas lama ber-rekening DAN kas lama tanpa rekening (tunggal) dibatalkan sebelum
    diteruskan, dan kas baru dicatat. Diteruskan → tiap sub-akun = buku kas rekeningnya, akun lama = 0."""
    from services import bank_service, cash_account_mode as mode, cash_account_cutover_service as cut
    eid = await pt_uji(f"KB3N{henti[:4]}")
    bank = await _rekening(eid, "BCA KB3N", awal=300_000)
    kk = await _rekening(eid, "Kas Kecil KB3N", "cash", "kas_kecil", awal=50_000)
    kas_bank = await _kas(eid, bank, "in", 40_000)
    kas_tunggal = await _kas_tanpa_rekening(db, eid, "kas_kecil", "out", 15_000)
    u = await cut.siapkan(eid, {}, PENYIAP)
    sidik = (await cut.pratinjau(eid))["sidik"]
    asli = cut._hitung
    if henti == "sebelum_rencana":
        async def hitung_henti(entity_id, *, sejak=""):
            if sejak:
                raise RuntimeError("uji: proses berhenti sebelum niat tersimpan")
            return await asli(entity_id, sejak=sejak)
        monkeypatch.setattr(cut, "_hitung", hitung_henti)
        with pytest.raises(HTTPException) as e:
            await cut.setujui(u["id"], sidik, PENYETUJU)
        monkeypatch.setattr(cut, "_hitung", asli)
    else:
        async with paksa_jurnal_gagal("sisip", entity_id=eid, source_type="pindah_saldo_kas"):
            with pytest.raises(HTTPException) as e:
                await cut.setujui(u["id"], sidik, PENYETUJU)
    assert e.value.status_code == 409 and await mode.aktif(eid)
    doc = await db.cash_account_cutovers.find_one({"id": u["id"]}, {"_id": 0})
    assert doc["status"] == "memproses" and bool(doc.get("rencana")) is (henti == "jurnal_gagal")
    assert (await db.cash_transactions.find_one({"id": kas_tunggal["id"]}))["account_id"] == kk   # ditautkan dulu
    for kas in (kas_bank, kas_tunggal):   # pembatalan di sela → pembalik ke sub-akun
        await _batal_api(klien, kepala_admin, eid, kas["id"], "batal sebelum diteruskan")
    await _kas(eid, bank, "in", 25_000)   # kas baru sesudah aktif → sub-akun
    hasil = await cut.setujui(u["id"], "", PENYETUJU)   # diteruskan (sidik tidak dibandingkan lagi)
    assert hasil["status"] == "disetujui", hasil
    for rid, sub in ((bank, "1-1100-01"), (kk, "1-1110-01")):
        assert await _saldo(sub, eid) == (await bank_service.account_ledger(rid))["balance"], rid
    assert (await _saldo("1-1100-01", eid), await _saldo("1-1110-01", eid)) == (325_000.0, 50_000.0)
    assert (await _saldo("1-1100", eid), await _saldo("1-1110", eid)) == (0.0, 0.0)


# ═══ 7. R8b — baris yang dipindah = baris yang kelak dialihkan pembalik; batal kas lama sesudah aktif; kas kembar ═══
async def test_KB1_3_U7_pindah_sama_dengan_pembalik_lalu_batal(db, klien, kepala_admin):
    from services import bank_service, cash_account_cutover_service as cut, gl_service as gl
    from services import interco_loan_service as icl
    eid, r, _ = await _pt_lengkap(db, "KB3H")
    q = await pt_uji("KB3HQ")
    await _rekening(q, "BCA KB3HQ", awal=0)
    pinjam = await icl.create({"lender_entity_id": eid, "borrower_entity_id": q, "principal": 150_000,
                               "purpose": "Modal kerja uji KB3"}, AKTOR_UJI)
    await icl.disburse(pinjam["lender"]["id"], AKTOR_UJI)   # kas kembar keluar dari rekening bank pertama (A)
    je_pinjam = await db.journal_entries.find_one({"source_type": "interco_loan", "entity_id": eid}, {"_id": 0})
    assert ("1-1100", 0.0, 150_000.0) in _baris(je_pinjam)
    kas_a = await _kas(eid, r["A"], "in", 80_000)
    p = await cut.pratinjau(eid)
    assert _asal(_rek(p, r["A"])) == {"1-1100": 1_430_000.0, "1-1101": -200_000.0}   # + 80.000 − 150.000 pinjaman
    hasil = await _siapkan_setujui(eid)
    sejak = hasil["aktif_sejak"]
    # Tiap jurnal kas lama: baris yang dialihkan pembalik = baris yang dipindah pindah saldo (per rekening, per akun)
    dipindah = {(s["journal_id"], s["indeks"]): s["rekening_id"]
                for s in (await cut._hitung(eid, sejak=sejak))["sumber"] if s["jenis"] == "kas"}
    dialihkan = {}
    async for je in db.journal_entries.find({"entity_id": eid, "created_at": {"$lt": sejak}}, {"_id": 0}):
        for i, a in (await gl.baris_kas_rekening(je)).items():
            dialihkan[(je["id"], i)] = a["rekening"]
    assert dialihkan == dipindah and (je_pinjam["id"], 1) in dialihkan, (dialihkan, dipindah)
    # Batal kas lama sesudah aktif (lewat API) → sub-akun tetap = buku kas, akun lama untuk baris rekening itu = 0
    await _batal_api(klien, kepala_admin, eid, kas_a["id"])
    for rid in r.values():
        akun = (await db.bank_accounts.find_one({"id": rid}))["gl_account_code"]
        assert await _saldo(akun, eid) == (await bank_service.account_ledger(rid))["balance"], rid
    # akun lama: baris rekening = 0; sisa 1-1100 hanya kas lama tanpa rekening yang tidak tunggal (+40.000, tetap)
    assert (await _saldo("1-1100", eid), await _saldo("1-1101", eid), await _saldo("1-1110", eid)) == (
        40_000.0, 0.0, 0.0)
    jejak = [j["aksi"] for j in (await db.cash_account_cutovers.find_one({"id": hasil["id"]}))["jejak"]]
    assert jejak == ["siapkan", "setujui", "selesai"], jejak


def test_KB1_3_U7b_rujukan_kas_jurnal_dua_arah():
    """Tautan kas ↔ jurnal induk lewat rujukan `parent_journal = "{jenis}:{rujukan}"` (R8b): kebalikan satu sama lain;
    awalan `source_id` hanya untuk sisi jurnal kembar (…:a|b|payer|payee)."""
    import re
    from services import gl_service as gl
    pasangan = [("interco_loan", "pair1:disburse:a", "interco_loan:pair1"),
                ("interco_loan_repayment", "pair1:rp2:b", "interco_loan_repayment:pair1:rp2"),
                ("interco_settlement", "ics1:payer", "interco_settlement:ics1"),
                ("interco_incentive_charge_settlement", "icc1:st1:a", "interco_incentive_charge_settlement:icc1:st1"),
                ("fixed_asset_transfer_settlement", "fa1:settle:b", "fixed_asset_transfer:fa1"),
                ("fixed_asset_acquisition", "fa1", "fixed_asset_acquisition:fa1"),
                ("sales_return", "sr1:rs1", "sales_return:sr1:rs1")]
    for st, sid, parent in pasangan:
        assert parent in gl._rujukan_jurnal({"source_type": st, "source_id": sid}), (st, sid)
        jenis, ruj = gl._rujukan_kas(parent)
        pola = "^" + re.escape(ruj) + ":([^:]+:)*(" + "|".join(gl._SISI_KEMBAR) + ")$"
        assert st in jenis and (sid == ruj or re.match(pola, sid)), (st, sid, parent)
    # bukan sisi kembar → tidak menaut lewat awalan; jurnal pindah aset (bukan pelunasan) tidak menaut kas pelunasan
    assert "sales_return:sr1" not in gl._rujukan_jurnal({"source_type": "sales_return", "source_id": "sr1:rs1"})
    assert "fixed_asset_transfer:fa1" not in gl._rujukan_jurnal({"source_type": "fixed_asset_transfer",
                                                                 "source_id": "fa1:from"})
    assert gl._rujukan_kas("je_abc123") is None


# ═══ 8. Tolak → tidak ada yang berubah selain sub-akun kosong; siapkan ulang dengan akun bagan PT pilihan Finance ═══
async def test_KB1_3_U8_tolak_lalu_pilih_akun_yang_ada(db):
    from schemas_finance import GLAccountCreate
    from services import cash_account_mode as mode, cash_account_cutover_service as cut, gl_service as gl
    eid = await pt_uji("KB3I")
    bank = await _rekening(eid, "BCA KB3I", awal=200_000)
    u = await cut.siapkan(eid, {}, PENYIAP)
    with pytest.raises(HTTPException) as e:   # usulan menunggu menghalangi usulan kedua
        await cut.siapkan(eid, {}, PENYIAP)
    assert e.value.status_code == 409 and "masih menunggu persetujuan" in e.value.detail
    with pytest.raises(HTTPException) as e:
        await cut.tolak(u["id"], "", PENYETUJU)
    assert e.value.status_code == 400
    jurnal = await db.journal_entries.count_documents({"entity_id": eid})
    t = await cut.tolak(u["id"], "angka belum direkonsiliasi", PENYETUJU)
    assert (t["status"], t["alasan_tolak"], t["ditolak_oleh"]) == ("ditolak", "angka belum direkonsiliasi",
                                                                   PENYETUJU["name"])
    assert not await mode.aktif(eid) and await db.journal_entries.count_documents({"entity_id": eid}) == jurnal
    assert (await db.bank_accounts.find_one({"id": bank}))["gl_account_code"] == "1-1100-01"   # sub-akun tetap
    assert await _saldo("1-1100-01", eid) == 0.0
    with pytest.raises(HTTPException) as e:
        await cut.setujui(u["id"], (await cut.pratinjau(eid))["sidik"], PENYETUJU)
    assert e.value.status_code == 409
    # Siapkan ulang: Finance memilih akun bagan PT yang sudah ada (berjurnal manual — boleh, butir 4)
    await gl.create_account(GLAccountCreate(code="1-1105", name="Bank BCA (akun Finance)", type="asset",
                                            parent_code="1-1000"), entity_id=eid)
    from pembantu import jurnal
    await jurnal(eid, now_iso(), [("1-1105", 5_000.0, 0.0), ("3-1000", 0.0, 5_000.0)], "Saldo manual", _uid("m"))
    u2 = await cut.siapkan(eid, {bank: "1-1105"}, PENYIAP)
    assert not await db.gl_accounts.find_one({"entity_id": eid, "code": "1-1100-01"})   # sub-akun kosong dilepas
    x = _rek(await cut.pratinjau(eid), bank)
    assert (x["akun_tujuan"], x["akun_tujuan_baru"], x["saldo_akun_tujuan"], x["saldo_sesudah"], x["selisih"]) == (
        "1-1105", False, 5_000.0, 205_000.0, 5_000.0)
    # Ketetapan R10 — rekening berselisih dengan buku kasnya: setujui wajib membawa `selisih_diperiksa`
    sidik2 = (await cut.pratinjau(eid))["sidik"]
    with pytest.raises(HTTPException) as e:
        await cut.setujui(u2["id"], sidik2, PENYETUJU)
    assert (e.value.status_code, e.value.detail) == (409, (
        "Rekening BCA KB3I berselisih Rp 5.000 dengan buku kasnya — centang 'sudah diperiksa' untuk melanjutkan."))
    assert (await db.cash_account_cutovers.find_one({"id": u2["id"]}))["status"] == "menunggu"
    assert not await mode.aktif(eid)
    hasil = await cut.setujui(u2["id"], sidik2, PENYETUJU, selisih_diperiksa=True)
    assert hasil["status"] == "disetujui"
    assert (hasil["selisih_diperiksa"], hasil["selisih_disetujui"]) == (
        True, [{"rekening_id": bank, "nama": "BCA KB3I", "selisih": 5_000.0}])
    assert (await _saldo("1-1105", eid), await _saldo("1-1100", eid)) == (205_000.0, 0.0)
    # Pilihan tak layak → 400, tanpa tulisan
    eid2 = await pt_uji("KB3I2")
    bank2 = await _rekening(eid2, "BCA KB3I2")
    with pytest.raises(HTTPException) as e:
        await cut.siapkan(eid2, {bank2: "1-1100"}, PENYIAP)
    assert e.value.status_code == 400 and "akun bawaan bersama" in e.value.detail
    with pytest.raises(HTTPException) as e:
        await cut.siapkan(eid2, {"rek_bukan_milik": "1-1105"}, PENYIAP)
    assert e.value.status_code == 400
    assert not await db.gl_accounts.find_one({"entity_id": eid2, "bank_account_id": bank2})
    assert not await db.cash_account_cutovers.find_one({"entity_id": eid2})


# ═══ 9. Jurnal pindah saldo gagal sesudah PT menyala → Posting Gagal → ulang melanjutkan; periode tutup → 409 ═══════
async def test_KB1_3_U9_jurnal_gagal_dilanjutkan_dari_posting_gagal(db, paksa_jurnal_gagal):
    from services import cash_account_mode as mode, cash_account_cutover_service as cut, posting_registry as reg
    from services.book_date import tanggal_buku
    eid = await pt_uji("KB3J")
    bank = await _rekening(eid, "BCA KB3J", awal=330_000)
    u = await cut.siapkan(eid, {}, PENYIAP)
    sidik = (await cut.pratinjau(eid))["sidik"]
    async with paksa_jurnal_gagal("periode", entity_id=eid, period_key=tanggal_buku()[:7]):
        with pytest.raises(HTTPException) as e:
            await cut.setujui(u["id"], sidik, PENYETUJU)
    assert e.value.status_code == 409 and "Tidak ada yang berubah" in e.value.detail, e.value.detail
    assert not await mode.aktif(eid)
    async with paksa_jurnal_gagal("akun", entity_id=eid, kode_akun="1-1100"):   # akun asal nonaktif: diperiksa
        with pytest.raises(HTTPException) as e:                                  # SEBELUM PT menyala
            await cut.setujui(u["id"], sidik, PENYETUJU)
    assert e.value.status_code == 409 and "Tidak ada yang berubah" in e.value.detail, e.value.detail
    assert not await mode.aktif(eid)
    doc = await db.cash_account_cutovers.find_one({"id": u["id"]}, {"_id": 0})
    assert (doc["status"], doc["disetujui_oleh"], doc["jejak"][-1]["aksi"]) == ("menunggu", "", "setujui_gagal")
    assert (await db.cash_account_cutovers.find_one({"id": u["id"]}))["status"] == "menunggu"
    async with paksa_jurnal_gagal("sisip", entity_id=eid, source_type="pindah_saldo_kas"):
        with pytest.raises(HTTPException) as e:
            await cut.setujui(u["id"], sidik, PENYETUJU)
    assert e.value.status_code == 409
    doc = await db.cash_account_cutovers.find_one({"id": u["id"]}, {"_id": 0})
    assert (doc["status"], doc["gl_status"]) == ("memproses", "failed") and await mode.aktif(eid)
    baris = await db[reg.KINDS["pindah_saldo_kas"]["collection"]].find_one(
        {**reg.KINDS["pindah_saldo_kas"]["failed_query"], "entity_id": eid}, {"_id": 0})
    assert baris and baris["id"] == u["id"]
    await reg.KINDS["pindah_saldo_kas"]["retry"](baris, AKTOR_UJI)
    doc = await db.cash_account_cutovers.find_one({"id": u["id"]}, {"_id": 0})
    assert (doc["status"], doc["gl_status"]) == ("disetujui", "posted")
    assert await db.journal_entries.count_documents({"source_type": "pindah_saldo_kas", "source_id": u["id"]}) == 1
    assert (await _saldo("1-1100-01", eid), await _saldo("1-1100", eid)) == (330_000.0, 0.0)
    assert bank


# ═══ 10. Rute: izin `accounting.manage`, cakupan PT, kalimat galat ═══════════════════════════════════════════════════
async def test_KB1_3_U10_rute(db, klien, akun, sesi):
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await pt_uji("KB3K")
    invalidate_status_cache()   # PT uji baru harus terlihat di penugasan akun (cache status PT)
    bank = await _rekening(eid, "BCA KB3K", awal=45_000)
    siap = await sesi(await akun("finance", entitas=(eid,)), entitas=eid)
    setuju = await sesi(await akun("finance", entitas=(eid,)), entitas=eid)
    sales = await sesi(await akun("sales", entitas=(eid,)), entitas=eid)
    r = await klien.get(f"/api/kas-per-rekening/{eid}/pratinjau", headers=sales)
    assert r.status_code == 403 and r.headers.get("X-Permission-Denied") == "accounting.manage", (r.text, r.headers)
    r = await klien.get("/api/kas-per-rekening/ent_tidak_ada/pratinjau", headers=siap)
    assert r.status_code == 404, r.text
    r = await klien.get(f"/api/kas-per-rekening/{eid}/pratinjau", headers=siap)
    assert r.status_code == 200 and _rek(r.json(), bank)["akun_tujuan"] == "1-1100-01", r.text
    r = await klien.post(f"/api/kas-per-rekening/{eid}/siapkan", headers=siap, json={"pilihan_akun": {}})
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    r = await klien.get("/api/kas-per-rekening/usulan", headers=setuju, params={"status": "menunggu"})
    assert r.status_code == 200 and [x["id"] for x in r.json()["items"]] == [uid], r.text
    sidik = (await klien.get(f"/api/kas-per-rekening/{eid}/pratinjau", headers=setuju)).json()["sidik"]
    r = await klien.post(f"/api/kas-per-rekening/usulan/{uid}/setujui", headers=siap, json={"sidik": sidik})
    assert r.status_code == 403, r.text
    r = await klien.post(f"/api/kas-per-rekening/usulan/{uid}/setujui", headers=setuju, json={"sidik": "lama"})
    assert (r.status_code, r.json()["detail"]) == (409, PESAN_ANGKA), r.text
    r = await klien.post(f"/api/kas-per-rekening/usulan/{uid}/setujui", headers=setuju, json={"sidik": sidik})
    assert r.status_code == 200 and r.json()["status"] == "disetujui", r.text
    r = await klien.post(f"/api/kas-per-rekening/usulan/{uid}/tolak", headers=setuju, json={"alasan": "terlambat"})
    assert r.status_code == 409, r.text
    r = await klien.post("/api/kas-per-rekening/usulan/psk_tidak_ada/setujui", headers=setuju, json={"sidik": "x"})
    assert r.status_code == 404, r.text


# ═══ 11. Ketetapan R9 — Admin penyiap tetap butuh orang kedua (bawaan `kontrol.admin_tetap_dua_orang`) ═══════════════
async def test_KB1_3_U11_admin_penyiap_tetap_dua_orang(db):
    import config_registry as registry
    from services import cash_account_cutover_service as cut
    from services.dual_control import pesan_tolak
    assert "pindah_saldo_kas" in registry.require("kontrol.admin_tetap_dua_orang")["default"]
    eid = await pt_uji("KB3L")
    await _rekening(eid, "BCA KB3L", awal=60_000)
    admin = {"id": "usr_kb3_admin", "name": "Ani Admin", "role": "admin", "email": "ani.kb3@uji.id"}
    u = await cut.siapkan(eid, {}, admin)
    with pytest.raises(HTTPException) as e:
        await cut.setujui(u["id"], (await cut.pratinjau(eid))["sidik"], admin)
    assert (e.value.status_code, e.value.detail) == (403, pesan_tolak("pindah_saldo_kas"))
    assert e.value.detail.startswith("Pindah saldo kas ke akun per rekening harus diputuskan orang lain")
    assert (await db.cash_account_cutovers.find_one({"id": u["id"]}))["status"] == "menunggu"
    admin2 = {**admin, "id": "usr_kb3_admin2", "name": "Rudi Admin"}
    assert (await cut.setujui(u["id"], (await cut.pratinjau(eid))["sidik"], admin2))["status"] == "disetujui"


# ═══ 12. Ketetapan R11 — jurnal saldo awal rekening tidak bisa dibalik manual di PT aktif ════════════════════════════
async def test_KB1_3_U12_balik_manual_saldo_awal_rekening(db):
    from services import gl_service as gl
    tgl = now_iso()[:10]
    # PT belum aktif → tidak berubah (pembalikan manual diterima)
    eid0 = await pt_uji("KB3M0")
    bank0 = await _rekening(eid0, "BCA KB3M0", awal=40_000)
    je0 = await db.journal_entries.find_one({"source_type": "bank_opening_balance", "source_id": bank0}, {"_id": 0})
    rev = await gl.reverse_entry(je0["id"], tgl, "uji balik saldo awal KB3", AKTOR_UJI)
    assert rev and rev["source_type"] == "reversal"
    # PT aktif → ditolak, jurnal tidak ditandai dibalik
    eid = await pt_uji("KB3M")
    bank = await _rekening(eid, "BCA KB3M", awal=90_000)
    await _siapkan_setujui(eid)
    je = await db.journal_entries.find_one({"source_type": "bank_opening_balance", "source_id": bank}, {"_id": 0})
    assert ("1-1100", 90_000.0, 0.0) in _baris(je)   # terbit sebelum aktif, di akun lama
    with pytest.raises(ValueError) as e:
        await gl.reverse_entry(je["id"], tgl, "uji balik saldo awal KB3", AKTOR_UJI)
    assert str(e.value) == (f"Jurnal {je['number']} mencatat saldo awal rekening BCA KB3M yang saldonya sudah dipindah "
                            f"ke akun 1-1100-01; koreksi lewat ubah saldo awal rekening itu di Rekening & Saldo, bukan "
                            f"pembalikan manual."), str(e.value)
    assert not (await db.journal_entries.find_one({"id": je["id"]})).get("reversed_by_entry_id")
    # Koreksi lewat ubah saldo awal → penyesuaian ke akun rekening, akun rekening tetap = buku kas
    from services import bank_service
    await bank_service.update_account(bank, {"opening_balance": 70_000})
    assert await _saldo("1-1100-01", eid) == (await bank_service.account_ledger(bank))["balance"] == 70_000.0

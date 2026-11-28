"""Kas & Bank 4 Tugas 3 — pindah saldo uang muka pemasok per PT (pratinjau → siapkan → setujui orang kedua → tolak),
buku pembantu uang muka pemasok, penahan, pembalikan uang muka pemasok lama sesudah pindah, daftar uang muka terbuka, dan
butir tutup buku `uang_muka_cocok`.

Rancangan: `docs/superpowers/specs/2026-11-28-kas-bank-4-uang-muka-design.md` §5.4, §5.5, §7.9.1, §7.9.2. Syarat
pengendali (tinjauan Tugas 1 ⚠️3): pembalikan dokumen uang muka pemasok yang terjurnal SEBELUM PT pindah, bila dijalankan
SESUDAHNYA, membukukan baris 1-1400-nya ke akun uang muka pemasok PT (`gl_service.baris_uang_muka_pemasok`).

Persiapan:
  * PT A (`KB43A`, ALUR lewat API seperti `test_KB4_1_fondasi`): tagihan 1.000.000 dibayar 4.000.000 dengan keputusan
    selisih "jadi uang muka" (kas `ap_advance` 3.000.000); kontrabon tagihan 2.000.000 − potongan uang muka 1.000.000
    dibayar (potongan terjurnal); kasus lebih bayar 500.000 (uang muka) dan pengembalian dana 200.000; PD 1.000.000
    dicairkan dari kas kecil (belum LPJ).
    Hitung tangan: buku pembantu pemasok = 3.000.000 − 1.000.000 + 500.000 − 200.000 = 2.300.000; kartu pemasok
    `advance_balance` = 3.000.000 + 500.000 − 200.000 = 3.300.000 (tidak turun oleh potongan kontrabon) → keterangan;
    1-1400 PT A = 2.300.000 + 1.000.000 (PD) = 3.300.000.
  * PT lain (FIXTURE): kas `ap_advance` lewat `cash_ledger.create_cash` (jurnalnya lewat pembantu akun yang sebenarnya),
    dokumen kontrabon/kasus/kas tertunda disisipkan langsung untuk penahan.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from core_utils import now_iso
from pembantu import AKTOR_UJI, jurnal, pt_uji, saldo_akun
from services.book_date import tanggal_buku

pytestmark = pytest.mark.anyio

HARI_INI = tanggal_buku()
JT = 1_000_000
PENYIAP = {"id": "usr_kb43_siap", "name": "Sinta Penyiap", "role": "finance", "email": "sinta.kb43@uji.id"}
PENYETUJU = {"id": "usr_kb43_setuju", "name": "Bayu Penyetuju", "role": "finance", "email": "bayu.kb43@uji.id"}
PENYETUJU2 = {"id": "usr_kb43_setuju2", "name": "Dewi Penyetuju", "role": "finance", "email": "dewi.kb43@uji.id"}
SIMPAN: dict = {}


def _h(kepala: dict, eid: str) -> dict:
    return {**kepala, "X-Entity-Id": eid}


def _set(je: dict) -> set:
    return {(ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]}


async def _saldo(kode: str, eid: str) -> float:
    return round(await saldo_akun(kode, eid), 2)


async def _jurnal_sumber(db, source_type: str, source_id: str) -> dict:
    jes = await db.journal_entries.find({"source_type": source_type, "source_id": source_id,
                                         "status": {"$ne": "void"}}, {"_id": 0}).to_list(5)
    assert len(jes) == 1, jes
    return jes[0]


async def _pt(db, kode: str) -> str:
    """PT uji + rekening bank + rekening kas kecil + pemasok `sup_<kode>`."""
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await pt_uji(kode)
    k = kode.lower()
    if not await db.bank_accounts.find_one({"id": f"rek_{k}"}):
        await db.bank_accounts.insert_many([
            {"id": f"rek_{k}", "name": f"Bank {kode}", "entity_id": eid, "account_type": "bank",
             "cash_type": "kas_besar", "is_active": True, "opening_balance": 0, "created_at": "2000-01-01T00:00:00"},
            {"id": f"rek_kk_{k}", "name": f"Kas Kecil {kode}", "entity_id": eid, "account_type": "cash",
             "cash_type": "kas_kecil", "is_active": True, "opening_balance": 0, "created_at": "2000-01-01T00:00:00"}])
        await db.suppliers.insert_one({"id": f"sup_{k}", "name": f"Pemasok {kode}", "code": f"S{kode}",
                                       "entity_id": eid, "status": "active", "advance_balance": 0.0,
                                       "payment_term_code": "NET30"})
    invalidate_status_cache()   # PT uji baru harus terlihat di penugasan Admin
    return eid


async def _tagihan(db, eid: str, bid: str, total: float, sid: str = "") -> dict:
    k = eid.replace("ent_uji_", "")
    b = {"id": bid, "bill_number": bid.upper().replace("_", "-"), "entity_id": eid, "supplier_id": sid or f"sup_{k}",
         "supplier_name": f"Pemasok {k.upper()}", "status": "posted", "grand_total": float(total),
         "subtotal": float(total), "amount_paid": 0.0, "payments": [], "timeline": [], "po_id": None,
         "bill_date": HARI_INI, "created_at": now_iso()}
    await db.vendor_bills.insert_one(dict(b))
    return b


async def _uang_muka_kas(db, eid: str, tag: str, nominal: float) -> dict:
    """FIXTURE: kelebihan bayar tagihan `tag` → kas `ap_advance` (jurnal lewat pembantu akun yang sebenarnya)."""
    from services import cash_ledger
    k = eid.replace("ent_uji_", "")
    b = await _tagihan(db, eid, f"vb_{k}_{tag}", JT)
    return await cash_ledger.create_cash(entity_id=eid, direction="out", amount=nominal, ref_type="ap_advance",
                                         ref_id=b["id"], account_id=f"rek_{k}", category="uang muka supplier",
                                         description=f"Kelebihan bayar {b['bill_number']}", actor="Uji")


async def _kontrabon(db, eid: str, cid: str, nominal: float, *, status: str = "approved", tagihan: float = 2 * JT,
                     ref_id: str = "", applied: bool = False) -> dict:
    from services import contra_bon_service as cbs
    k = eid.replace("ent_uji_", "")
    b = await _tagihan(db, eid, f"vb_{cid}", tagihan)
    d = {"id": f"ded_{cid}", "kind": "supplier_advance", "amount": float(nominal), "posts_gl": True,
         "label": "uang muka pemasok", "ref_id": ref_id, "ref_number": ""}
    if applied:
        d["applied_at"] = now_iso()
    cb = {"id": cid, "number": cid.upper().replace("_", "-"), "entity_id": eid, "supplier_id": f"sup_{k}",
          "supplier_name": f"Pemasok {k.upper()}", "status": status, "created_at": now_iso(), "timeline": [],
          "payments": [], "decisions": [],
          "bills": [{"bill_id": b["id"], "bill_number": b["bill_number"], "applied_amount": float(tagihan),
                     "settled_amount": 0.0, "po_id": None}], "deductions": [d]}
    await db.contra_bons.insert_one(cbs.recompute(cb))
    return cb


async def _kasus(klien, kepala, eid: str, aksi: str, nominal: float) -> dict:
    """ALUR: kasus "lebih bayar pemasok" → uang muka (`uang_muka_supplier`) / pengembalian dana (`terima_refund_supplier`)."""
    k = eid.replace("ent_uji_", "")
    h = _h(kepala, eid)
    r = await klien.post("/api/finance-cases", headers=h, json={
        "case_type": "lebih_bayar_supplier", "amount": nominal, "supplier_id": f"sup_{k}", "entity_id": eid,
        "source": {"kind": "manual", "label": f"uji KB43 {aksi}"}})
    assert r.status_code == 200, r.text
    case = r.json()
    isi = {"action": aksi, "reason_code": "supplier_advance", "supplier_id": f"sup_{k}", "amount": nominal}
    if aksi == "terima_refund_supplier":
        isi["account_id"] = f"rek_{k}"
    r = await klien.post(f"/api/finance-cases/{case['id']}/resolve", headers=h, json=isi)
    assert r.status_code == 200 and r.json()["status"] == "resolved", r.text
    return r.json()


async def _pd_cair(db, eid: str, pid: str, nominal: float) -> dict:
    """FIXTURE: PD dicairkan (kas `cash_advance` lewat pembuat kas: Dr 1-1400 / Cr kas kecil)."""
    from services import cash_ledger
    k = eid.replace("ent_uji_", "")
    await db.cash_advances.insert_one({
        "id": pid, "number": pid.upper().replace("_", "-"), "entity_id": eid, "status": "disbursed",
        "kegiatan": "uji KB43", "total_amount": float(nominal), "created_by": "Staf KB43",
        "created_by_id": "usr_staf_kb43", "created_at": now_iso(),
        "disbursement": {"amount": float(nominal)}})
    return await cash_ledger.create_cash(entity_id=eid, direction="out", amount=nominal, ref_type="cash_advance",
                                         ref_id=pid, account_id=f"rek_kk_{k}", category="cash_advance",
                                         description=f"Pencairan {pid}", actor="Uji")


async def _siapkan_setujui(eid: str, penyiap: dict = PENYIAP, penyetuju: dict = PENYETUJU) -> dict:
    from services import supplier_advance_cutover_service as cut
    u = await cut.siapkan(eid, penyiap)
    return await cut.setujui(u["id"], u["sidik"], penyetuju)


async def _galat(coro) -> HTTPException:
    with pytest.raises(HTTPException) as ei:
        await coro
    return ei.value


# ═══ PT A — dunia lewat API ══════════════════════════════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
async def dunia(klien, db, kepala_admin):
    from services import amendment_service
    await amendment_service.ensure_reasons()
    a = await _pt(db, "KB43A")
    h = _h(kepala_admin, a)
    # (1) Lebih bayar tagihan 1.000.000 dibayar 4.000.000 → keputusan "jadi uang muka" → kas ap_advance 3.000.000.
    t1 = await _tagihan(db, a, "vb_kb43a_t1", JT)
    r = await klien.post(f"/api/vendor-bills/{t1['id']}/pay", headers={**h, "Idempotency-Key": "kb43a-t1"}, json={
        "amount": 4 * JT, "paid_at": HARI_INI, "bank_account_id": "rek_kb43a",
        "variance": {"kind": "ap_advance", "reason_code": "supplier_advance", "note": "uji KB43 lebih bayar"}})
    assert r.status_code == 200, r.text
    um = await db.cash_transactions.find_one({"ref_type": "ap_advance", "ref_id": t1["id"]}, {"_id": 0})
    assert um and um["amount"] == 3 * JT, um
    # (2) Kontrabon 2.000.000 − potongan uang muka 1.000.000 dibayar → potongan terjurnal.
    await _kontrabon(db, a, "cb_kb43a_1", JT, ref_id=um["id"])
    r = await klien.post("/api/contra-bons/cb_kb43a_1/pay", headers=h,
                         json={"paid_at": HARI_INI, "bank_account_id": "rek_kb43a"})
    assert r.status_code == 200, r.text
    await _jurnal_sumber(db, "contra_bon_deduction", "cb_kb43a_1:ded_cb_kb43a_1")
    # (3) Kasus lebih bayar 500.000 → uang muka; pengembalian dana 200.000.
    await _kasus(klien, kepala_admin, a, "uang_muka_supplier", 500_000)
    await _kasus(klien, kepala_admin, a, "terima_refund_supplier", 200_000)
    # (4) PD 1.000.000 dicairkan, belum LPJ.
    await _pd_cair(db, a, "ca_kb43a_1", JT)
    SIMPAN["a"] = a
    return a


async def test_KB4_3_U1_buku_pembantu_per_pt_dan_kartu_pemasok_hanya_keterangan(db, dunia):
    from services import supplier_advance_cutover_service as cut
    from services import supplier_advance_service as sas
    a = dunia
    sl = await sas.subledger(a)
    assert sl["baris"] == [{"supplier_id": "sup_kb43a", "nama": "Pemasok KB43A", "dari_kas": 3_000_000.0,
                            "dipotong_terjurnal": 1_000_000.0, "dari_kasus": 500_000.0, "refund_kasus": 200_000.0,
                            "sisa": 2_300_000.0}], sl
    assert sl["total"] == 2_300_000.0
    sup = await db.suppliers.find_one({"id": "sup_kb43a"}, {"_id": 0})
    assert sup["advance_balance"] == 3_300_000.0   # 3.000.000 + 500.000 − 200.000 (potongan kontrabon tidak menurunkan)
    assert [(i["supplier_id"], i["advance_balance"], i["sisa"]) for i in sl["advance_balance_info"]] == [
        ("sup_kb43a", 3_300_000.0, 2_300_000.0)]
    assert "hanya keterangan" in sl["advance_balance_info"][0]["kalimat"]
    assert await sas.penahan(a) == []   # kartu pemasok berbeda bukan penahan
    n0 = (await db.journal_entries.count_documents({}), await db.supplier_advance_cutovers.count_documents({}))
    p = await cut.pratinjau(a, PENYIAP)
    assert n0 == (await db.journal_entries.count_documents({}), await db.supplier_advance_cutovers.count_documents({}))
    assert (p["entity_id"], p["total"], p["saldo_1_1400"], p["penahan"], p["bisa_siapkan"], p["alasan"]) == (
        a, 2_300_000.0, 3_300_000.0, [], True, "")
    assert p["baris"] == sl["baris"] and p["akun_pemasok"] == "1-1410" and p["saldo_akun_pemasok"] == 0.0
    assert p["baris_jurnal"] == [{"account_code": "1-1410", "debit": 2_300_000.0, "credit": 0.0},
                                 {"account_code": "1-1400", "debit": 0.0, "credit": 2_300_000.0}]
    assert p["sidik"] and p["usulan"] is None and p["aktif"] is False


# ═══ Penahan ═════════════════════════════════════════════════════════════════════════════════════════════════════════
async def test_KB4_3_U2a_kontrabon_berpotongan_belum_dibayar_menahan_siapkan(db, dunia):
    from services import supplier_advance_cutover_service as cut
    c = await _pt(db, "KB43C")
    um = await _uang_muka_kas(db, c, "t1", 500_000)
    await _kontrabon(db, c, "cb_kb43c_1", 250_000, ref_id=um["id"])                       # belum dibayar
    await _kontrabon(db, c, "cb_kb43c_2", 100_000, status="paid", applied=True)          # dibayar, jurnal belum terbit
    p = await cut.pratinjau(c)
    assert [(x["jenis"], x["nomor"]) for x in p["penahan"]] == [("kontrabon_belum_dibayar", "CB-KB43C-1"),
                                                                 ("potongan_gagal", "CB-KB43C-2")], p["penahan"]
    assert p["bisa_siapkan"] is False and "CB-KB43C-1" in p["alasan"]
    e = await _galat(cut.siapkan(c, PENYIAP))
    assert e.status_code == 409 and "Kontrabon CB-KB43C-1" in e.detail and "Rp 250.000" in e.detail, e.detail
    assert "Bayar atau batalkan kontrabonnya dulu" in e.detail and "Posting Gagal" in e.detail
    assert await db.supplier_advance_cutovers.count_documents({"entity_id": c}) == 0


async def test_KB4_3_U2b_jurnal_uang_muka_tertunda_dan_akun_bersaldo_menahan(db, dunia):
    from services import supplier_advance_cutover_service as cut
    d = await _pt(db, "KB43D")
    b = await _tagihan(db, d, "vb_kb43d_t1", JT)
    await db.cash_transactions.insert_one({   # kas uang muka yang jurnalnya gagal (tidak ada jurnal)
        "id": "cash_kb43d_gagal", "number": "KB43D/CASH-1", "entity_id": d, "owner_entity_id": d,
        "direction": "out", "amount": 400_000.0, "ref_type": "ap_advance", "ref_id": b["id"],
        "ref_number": b["bill_number"], "status": "posted", "gl_status": "failed", "account_id": "rek_kb43d",
        "cash_type": "kas_besar", "txn_date": HARI_INI, "created_at": now_iso()})
    await db.finance_cases.insert_one({   # penyelesaian kasus yang niatnya masih tertunda (jurnal gagal)
        "id": "fc_kb43d_1", "number": "KB43D/KAS-1", "entity_id": d, "supplier_id": "sup_kb43d",
        "case_type": "lebih_bayar_supplier", "status": "open",
        "resolution_intent": {"op_id": "op1", "action": "uang_muka_supplier", "status": "pending",
                              "payload": {"supplier_id": "sup_kb43d", "amount": 50_000}}})
    p = await cut.pratinjau(d)
    assert [x["jenis"] for x in p["penahan"]] == ["kas_tertunda", "kasus_tertunda"], p["penahan"]
    e = await _galat(cut.siapkan(d, PENYIAP))
    assert e.status_code == 409 and "KB43D/CASH-1" in e.detail and "KB43D/KAS-1" in e.detail, e.detail
    # Akun uang muka pemasok PT yang sudah bersaldo sebelum pindah (posting sistem lama) → ditahan juga.
    pb = await _pt(db, "KB43P")
    await jurnal(pb, HARI_INI, [("1-1410", 75_000, 0), ("4-9000", 0, 75_000)], "uji KB43 akun lama", "kb43p_lama")
    p = await cut.pratinjau(pb)
    assert [x["jenis"] for x in p["penahan"]] == ["akun_pemasok_bersaldo"], p["penahan"]
    assert "Akun 1-1410 PT ini sudah bersaldo Rp 75.000" in p["penahan"][0]["kalimat"]


async def test_KB4_3_U2c_pemasok_negatif_menahan_periksa_kasus(db, dunia):
    from services import gl_service as gl
    from services import supplier_advance_cutover_service as cut
    e_ = await _pt(db, "KB43E")
    await _kontrabon(db, e_, "cb_kb43e_1", 200_000, status="paid", applied=True)
    await gl.post_contra_bon_deduction(cb_id="cb_kb43e_1", deduction_id="ded_cb_kb43e_1", entity_id=e_,
                                       kind="supplier_advance", amount=200_000, label="uji KB43E", date=HARI_INI)
    p = await cut.pratinjau(e_)
    assert p["baris"][0]["sisa"] == -200_000.0 and [x["jenis"] for x in p["penahan"]] == ["baris_negatif"]
    e = await _galat(cut.siapkan(e_, PENYIAP))
    assert e.status_code == 409 and "periksa kasus" in e.detail and "-Rp 200.000" in e.detail, e.detail


# ═══ Siapkan → setujui orang yang sama (juga Admin) 403 → orang kedua: jurnal reklas, PT pindah ═════════════════════
async def test_KB4_3_U3_siapkan_setujui_orang_kedua_jurnal_dan_penanda(db, dunia):
    from services import gl_service as gl
    from services import supplier_advance_cutover_service as cut
    from services import supplier_advance_mode as mode
    a = dunia
    u = await cut.siapkan(a, AKTOR_UJI)   # Admin menyiapkan
    assert (u["status"], u["total"], u["baris"][0]["sisa"]) == ("menunggu", 2_300_000.0, 2_300_000.0)
    assert u["sidik"] == (await cut.pratinjau(a))["sidik"]
    e = await _galat(cut.siapkan(a, PENYIAP))
    assert e.status_code == 409 and "masih menunggu persetujuan" in e.detail
    p = await cut.pratinjau(a, AKTOR_UJI)
    assert p["usulan"]["id"] == u["id"] and p["usulan"]["kontrol"]["ditolak"] is True and p["bisa_siapkan"] is False
    e = await _galat(cut.setujui(u["id"], u["sidik"], AKTOR_UJI))   # Admin = penyiap → tetap dua orang
    assert e.status_code == 403, e.detail
    assert not await mode.aktif(a) and (await cut.ambil(u["id"]))["status"] == "menunggu"
    hasil = await cut.setujui(u["id"], u["sidik"], PENYETUJU)
    assert (hasil["status"], hasil["total_dipindah"], hasil["susulan"], hasil["disetujui_oleh"]) == (
        "disetujui", 2_300_000.0, 0.0, PENYETUJU["name"])
    je = await _jurnal_sumber(db, gl.SOURCE_PINDAH_UANG_MUKA_PEMASOK, u["id"])
    assert _set(je) == {("1-1410", 2_300_000.0, 0.0), ("1-1400", 0.0, 2_300_000.0)}, je["lines"]
    assert je["number"] == hasil["journal_number"] and je["date"] == HARI_INI
    assert await mode.aktif(a) and hasil["aktif_sejak"] == await mode.aktif_sejak(a)
    assert je["created_at"] < hasil["aktif_sejak"]   # ketetapan (a): reklas SEBELUM penanda
    assert await gl.akun_uang_muka_pemasok(a) == "1-1410"
    assert await _saldo("1-1410", a) == 2_300_000.0 and await _saldo("1-1400", a) == 1_000_000.0   # sisa = PD
    e = await _galat(cut.siapkan(a, PENYIAP))
    assert e.status_code == 409 and "Pindah saldo hanya sekali per PT" in e.detail
    p = await cut.pratinjau(a)
    assert p["aktif"] is True and p["bisa_siapkan"] is False and p["usulan_terakhir"]["status"] == "disetujui"


async def test_KB4_3_U4_sesudah_pindah_potongan_dan_refund_baru_ke_1_1410(klien, db, kepala_admin, dunia):
    from services import supplier_advance_mode as mode
    from services import supplier_advance_service as sas
    a = dunia
    if not await mode.aktif(a):   # dijalankan sendiri (tanpa U3): PT A dipindah dulu
        await _siapkan_setujui(a)
    um = await db.cash_transactions.find_one({"ref_type": "ap_advance", "ref_id": "vb_kb43a_t1"}, {"_id": 0})
    await _kontrabon(db, a, "cb_kb43a_2", 300_000, tagihan=1_500_000, ref_id=um["id"])
    r = await klien.post("/api/contra-bons/cb_kb43a_2/pay", headers=_h(kepala_admin, a),
                         json={"paid_at": HARI_INI, "bank_account_id": "rek_kb43a"})
    assert r.status_code == 200, r.text
    je = await _jurnal_sumber(db, "contra_bon_deduction", "cb_kb43a_2:ded_cb_kb43a_2")
    assert _set(je) == {("2-1100", 300_000.0, 0.0), ("1-1410", 0.0, 300_000.0)}, je["lines"]
    kasus = await _kasus(klien, kepala_admin, a, "terima_refund_supplier", 100_000)
    kas = await db.cash_transactions.find_one({"ref_type": "finance_case", "ref_id": kasus["id"]}, {"_id": 0})
    assert _set(await _jurnal_sumber(db, "cash_transaction", kas["id"])) == {
        ("1-1100", 100_000.0, 0.0), ("1-1410", 0.0, 100_000.0)}
    sl = await sas.subledger(a)
    assert sl["total"] == 1_900_000.0   # 2.300.000 − 300.000 − 100.000
    assert await _saldo("1-1410", a) == sl["total"] and await _saldo("1-1400", a) == 1_000_000.0


async def test_KB4_3_U5_data_berubah_antara_siapkan_dan_setujui_409_lalu_tolak(db, dunia):
    from services import supplier_advance_cutover_service as cut
    from services import supplier_advance_mode as mode
    f = await _pt(db, "KB43F")
    await _uang_muka_kas(db, f, "t1", 100_000)
    u = await cut.siapkan(f, PENYIAP)
    await _uang_muka_kas(db, f, "t2", 50_000)
    e = await _galat(cut.setujui(u["id"], "", PENYETUJU))
    assert (e.status_code, e.detail) == (409, cut.PESAN_ANGKA_BERUBAH)
    e = await _galat(cut.setujui(u["id"], "sidik-lama", PENYETUJU))
    assert e.status_code == 409
    assert (await cut.ambil(u["id"]))["status"] == "menunggu" and not await mode.aktif(f)
    assert await db.journal_entries.count_documents({"source_type": "pindah_uang_muka_pemasok", "entity_id": f}) == 0
    e = await _galat(cut.tolak(u["id"], "ok", PENYETUJU))
    assert e.status_code == 400
    t = await cut.tolak(u["id"], "angka berubah, siapkan ulang", PENYETUJU)
    assert (t["status"], t["alasan_tolak"], t["ditolak_oleh"]) == ("ditolak", "angka berubah, siapkan ulang",
                                                                    PENYETUJU["name"])
    e = await _galat(cut.tolak(u["id"], "tolak lagi ya", PENYETUJU))
    assert e.status_code == 409
    hasil = await _siapkan_setujui(f)
    assert (hasil["status"], hasil["total_dipindah"], hasil["id"]) == ("disetujui", 150_000.0, f"pum_{f}_002")
    assert await _saldo("1-1410", f) == 150_000.0 and await _saldo("1-1400", f) == 0.0


async def test_KB4_3_U6_total_nol_tanpa_jurnal_orang_sama_403(db, dunia):
    from services import supplier_advance_cutover_service as cut
    from services import supplier_advance_mode as mode
    g = await _pt(db, "KB43G")
    u = await cut.siapkan(g, PENYIAP)
    assert (u["total"], u["baris"]) == (0.0, [])
    e = await _galat(cut.setujui(u["id"], u["sidik"], PENYIAP))
    assert e.status_code == 403 and "harus diputuskan orang lain" in e.detail, e.detail
    hasil = await cut.setujui(u["id"], u["sidik"], PENYETUJU)
    assert (hasil["status"], hasil["journal_entry_id"], hasil["total_dipindah"]) == ("disetujui", "", 0.0)
    assert await mode.aktif(g)
    assert await db.journal_entries.count_documents({"entity_id": g}) == 0


async def test_KB4_3_U7_setujui_ganda_bersamaan_satu_jurnal_pt_lain_tidak_tersentuh(db, dunia):
    from services import gl_service as gl
    from services import supplier_advance_cutover_service as cut
    from services import supplier_advance_mode as mode
    hh = await _pt(db, "KB43H")
    b = await _pt(db, "KB43B")
    await _uang_muka_kas(db, hh, "t1", 70_000)
    await _uang_muka_kas(db, b, "t1", 400_000)
    jb0 = await db.journal_entries.count_documents({"entity_id": b})
    u = await cut.siapkan(hh, PENYIAP)
    hasil = await asyncio.gather(cut.setujui(u["id"], u["sidik"], PENYETUJU),
                                 cut.setujui(u["id"], u["sidik"], PENYETUJU2), return_exceptions=True)
    ok = [x for x in hasil if isinstance(x, dict)]
    gagal = [x for x in hasil if isinstance(x, HTTPException)]
    assert len(ok) == 1 and len(gagal) == 1 and gagal[0].status_code == 409, hasil
    assert await db.journal_entries.count_documents({"source_type": "pindah_uang_muka_pemasok",
                                                     "entity_id": hh}) == 1
    assert await _saldo("1-1410", hh) == 70_000.0 and await _saldo("1-1400", hh) == 0.0
    # PT lain tidak tersentuh: penanda mati, jurnal tetap, uang mukanya masih di 1-1400.
    assert not await mode.aktif(b) and await gl.akun_uang_muka_pemasok(b) == "1-1400"
    assert await db.journal_entries.count_documents({"entity_id": b}) == jb0
    assert await _saldo("1-1400", b) == 400_000.0 and await _saldo("1-1410", b) == 0.0


async def test_KB4_3_U8_jurnal_reklas_gagal_tidak_ada_yang_berubah(db, dunia, paksa_jurnal_gagal):
    from services import supplier_advance_cutover_service as cut
    from services import supplier_advance_mode as mode
    q = await _pt(db, "KB43Q")
    await _uang_muka_kas(db, q, "t1", 80_000)
    u = await cut.siapkan(q, PENYIAP)
    async with paksa_jurnal_gagal("sisip", entity_id=q, source_type="pindah_uang_muka_pemasok") as gagal:
        e = await _galat(cut.setujui(u["id"], u["sidik"], PENYETUJU))
    assert len(gagal) == 1 and e.status_code == 409 and "Tidak ada yang berubah" in e.detail, e.detail
    doc = await cut.ambil(u["id"])
    assert (doc["status"], doc["disetujui_oleh"], doc.get("gl_status")) == ("menunggu", "", None), doc
    assert not await mode.aktif(q) and await _saldo("1-1400", q) == 80_000.0
    hasil = await cut.setujui(u["id"], u["sidik"], PENYETUJU)
    assert hasil["status"] == "disetujui" and await _saldo("1-1410", q) == 80_000.0


async def test_KB4_3_U9_uang_muka_terjurnal_di_sela_hitung_dan_penanda_ikut_susulan(db, dunia, monkeypatch):
    """Kas uang muka yang jurnalnya terbit sesudah hitung ulang tetapi sebelum penanda (masih ke 1-1400) ikut dipindah
    lewat jurnal susulan: 1-1410 = buku pembantu, 1-1400 tanpa sisa uang muka pemasok."""
    from services import gl_service as gl
    from services import supplier_advance_cutover_service as cut
    from services import supplier_advance_mode as mode
    s = await _pt(db, "KB43S")
    await _uang_muka_kas(db, s, "t1", 100_000)
    u = await cut.siapkan(s, PENYIAP)
    asli = mode.nyalakan
    sela: dict = {}

    async def _nyalakan(eid, oleh):
        if eid == s and not sela:
            sela["kas"] = await _uang_muka_kas(db, s, "t2", 30_000)   # jurnal kas → 1-1400 (PT belum pindah)
        return await asli(eid, oleh)

    monkeypatch.setattr(mode, "nyalakan", _nyalakan)
    hasil = await cut.setujui(u["id"], u["sidik"], PENYETUJU)
    assert _set(await _jurnal_sumber(db, "cash_transaction", sela["kas"]["id"])) == {
        ("1-1400", 30_000.0, 0.0), ("1-1100", 0.0, 30_000.0)}
    sus = await _jurnal_sumber(db, gl.SOURCE_PINDAH_UANG_MUKA_PEMASOK, f"{u['id']}:susulan")
    assert _set(sus) == {("1-1410", 30_000.0, 0.0), ("1-1400", 0.0, 30_000.0)}, sus["lines"]
    assert (hasil["susulan"], hasil["total_dipindah"], hasil["susulan_journal_number"]) == (
        30_000.0, 130_000.0, sus["number"])
    assert await _saldo("1-1410", s) == 130_000.0 and await _saldo("1-1400", s) == 0.0


async def test_KB4_3_U9b_susulan_gagal_tampil_di_posting_gagal_lalu_diulang(klien, db, kepala_admin, dunia,
                                                                          monkeypatch):
    """Jurnal susulan gagal sesudah PT pindah → usulan tetap `memproses`, tampil di Posting Gagal; Ulangi → selesai."""
    from services import gl_service as gl
    from services import supplier_advance_cutover_service as cut
    from services import supplier_advance_mode as mode
    s = await _pt(db, "KB43T")
    await _uang_muka_kas(db, s, "t1", 100_000)
    u = await cut.siapkan(s, PENYIAP)
    asli_nyala, asli_post = mode.nyalakan, gl.post_pindah_uang_muka_pemasok

    async def _nyalakan(eid, oleh):
        if eid == s and not await db.cash_transactions.find_one({"ref_id": "vb_kb43t_t2"}):
            await _uang_muka_kas(db, s, "t2", 20_000)
        return await asli_nyala(eid, oleh)

    async def _post(**kw):
        if kw.get("bagian") == "susulan" and kw.get("entity_id") == s:
            raise RuntimeError("uji: jurnal susulan dipaksa gagal")
        return await asli_post(**kw)

    monkeypatch.setattr(mode, "nyalakan", _nyalakan)
    monkeypatch.setattr(gl, "post_pindah_uang_muka_pemasok", _post)
    e = await _galat(cut.setujui(u["id"], u["sidik"], PENYETUJU))
    assert e.status_code == 409 and "jurnal susulan" in e.detail and "Posting Gagal" in e.detail, e.detail
    doc = await cut.ambil(u["id"])
    assert (doc["status"], doc["susulan_gl_status"], doc["lease_until"]) == ("memproses", "failed", "")
    assert await mode.aktif(s) and await _saldo("1-1410", s) == 100_000.0 and await _saldo("1-1400", s) == 20_000.0
    h = _h(kepala_admin, s)
    r = await klien.get("/api/finance/posting-failures", headers=h, params={"kind": "pindah_uang_muka_pemasok"})
    assert r.status_code == 200 and [x["id"] for x in r.json()["items"]] == [u["id"]], r.text
    monkeypatch.setattr(gl, "post_pindah_uang_muka_pemasok", asli_post)
    r = await klien.post(f"/api/finance/posting-failures/pindah_uang_muka_pemasok/{u['id']}/retry", headers=h)
    assert r.status_code == 200, r.text
    doc = await cut.ambil(u["id"])
    assert (doc["status"], doc["susulan"], doc["total_dipindah"]) == ("disetujui", 20_000.0, 120_000.0)
    assert await _saldo("1-1410", s) == 120_000.0 and await _saldo("1-1400", s) == 0.0


# ═══ Pembalikan uang muka pemasok lama sesudah pindah (syarat pengendali, tinjauan Tugas 1 ⚠️3) ════════════════════
async def _dunia_balik(klien, db, kepala, kode: str) -> dict:
    """Kas uang muka 600.000 (+ satu 50.000 untuk uji pembalikan manual), kasus uang muka 300.000 dan pengembalian
    100.000, potongan kontrabon terjurnal 200.000, PD cair 500.000. Buku pembantu = 600+50+300−100−200 = 650.000."""
    from services import gl_service as gl
    eid = await _pt(db, kode)
    k = kode.lower()
    out = {"eid": eid, "kas": await _uang_muka_kas(db, eid, "t1", 600_000),
           "kas_manual": await _uang_muka_kas(db, eid, "t2", 50_000)}
    await _kasus(klien, kepala, eid, "uang_muka_supplier", 300_000)
    out["kasus_uang_muka"] = await db.journal_entries.find_one(
        {"source_type": "finance_case", "entity_id": eid, "status": {"$ne": "void"}}, {"_id": 0})
    kasus = await _kasus(klien, kepala, eid, "terima_refund_supplier", 100_000)
    out["kas_refund"] = await db.cash_transactions.find_one({"ref_type": "finance_case", "ref_id": kasus["id"]},
                                                            {"_id": 0})
    await _kontrabon(db, eid, f"cb_{k}_1", 200_000, status="paid", applied=True)
    await gl.post_contra_bon_deduction(cb_id=f"cb_{k}_1", deduction_id=f"ded_cb_{k}_1", entity_id=eid,
                                       kind="supplier_advance", amount=200_000, label=f"uji {kode}", date=HARI_INI)
    out["potongan"] = f"cb_{k}_1:ded_cb_{k}_1"
    out["pd"] = await _pd_cair(db, eid, f"ca_{k}_1", 500_000)
    return out


async def _cocok(eid: str, pindah: bool) -> float:
    """Kedua akun = daftarnya: 1-1410 = buku pembantu & 1-1400 = PD terbuka (PT pindah); 1-1400 = PD + pemasok (belum)."""
    from services import supplier_advance_service as sas
    sl = (await sas.subledger(eid))["total"]
    pd = sum(p["sisa"] for p in await sas.pd_terbuka(eid))
    if pindah:
        assert (await _saldo("1-1410", eid), await _saldo("1-1400", eid)) == (sl, pd), (eid, sl, pd)
    else:
        assert (await _saldo("1-1410", eid), await _saldo("1-1400", eid)) == (0.0, round(sl + pd, 2)), (eid, sl, pd)
    return sl


def _cermin(je: dict) -> set:
    return {(ln["account_code"], ln["credit"], ln["debit"]) for ln in je["lines"]}


@pytest.fixture(scope="module")
async def dunia_balik(klien, db, kepala_admin, dunia):
    r1 = await _dunia_balik(klien, db, kepala_admin, "KB43R1")   # akan pindah
    r0 = await _dunia_balik(klien, db, kepala_admin, "KB43R0")   # tidak pindah
    hasil = await _siapkan_setujui(r1["eid"])
    assert hasil["total_dipindah"] == 650_000.0
    assert await _cocok(r1["eid"], True) == 650_000.0 and await _cocok(r0["eid"], False) == 650_000.0
    return {"r1": r1, "r0": r0}


@pytest.mark.parametrize("jenis", ["kas_uang_muka", "kasus_uang_muka", "kas_refund", "potongan_kontrabon"])
async def test_KB4_3_U10_pembalikan_uang_muka_lama_sesudah_pindah_ke_1_1410(db, dunia_balik, jenis):
    """Kas `ap_advance` (jalur keputusan selisih bayar / lebih bayar), jurnal kasus uang muka, kas pengembalian dana
    kasus, potongan kontrabon — dibalik lewat pembalik terpadu (`post_cash_void` / `reverse_document`). PT pindah: baris
    uang muka pembaliknya ke 1-1410; PT belum pindah: cermin persis jurnal aslinya."""
    from services import gl_service as gl
    for tag, pindah in (("r1", True), ("r0", False)):
        w = dunia_balik[tag]
        eid = w["eid"]
        if jenis in ("kas_uang_muka", "kas_refund"):
            kas = w["kas"] if jenis == "kas_uang_muka" else w["kas_refund"]
            asli = await _jurnal_sumber(db, "cash_transaction", kas["id"])
            rev = await gl.post_cash_void(kas["id"], label="uji KB43 batal", created_by="Uji")
        elif jenis == "kasus_uang_muka":
            asli = w["kasus_uang_muka"]
            rev = (await gl.reverse_document("finance_case", asli["source_id"], reason="uji KB43 batal"))[0]
        else:
            asli = await _jurnal_sumber(db, "contra_bon_deduction", w["potongan"])
            rev = (await gl.reverse_document("contra_bon_deduction", w["potongan"], reason="uji KB43 batal"))[0]
        harap = _cermin(asli)
        if pindah:
            harap = {("1-1410" if a == "1-1400" else a, d, c) for a, d, c in harap}
        assert _set(rev) == harap, (tag, jenis, rev["lines"])
        assert "1-1400" in {ln["account_code"] for ln in asli["lines"]}
        await _cocok(eid, pindah)


async def test_KB4_3_U11_pembalikan_pd_tidak_dialihkan_dan_manual_ditolak(db, dunia_balik):
    from services import gl_service as gl
    r1, r0 = dunia_balik["r1"], dunia_balik["r0"]
    # Uang muka karyawan (PD) tidak pernah dialihkan, juga di PT yang sudah pindah.
    asli = await _jurnal_sumber(db, "cash_transaction", r1["pd"]["id"])
    assert await gl.baris_uang_muka_pemasok(asli) == {}
    rev = await gl.post_cash_void(r1["pd"]["id"], label="uji KB43 batal PD", created_by="Uji")
    assert _set(rev) == _cermin(asli) and ("1-1400", 0.0, 500_000.0) in _set(rev)
    # Pembalikan manual jurnal uang muka pemasok lama di PT pindah → ditolak (akunnya kini akun kontrol 1-1410).
    await db.cash_advances.update_one({"id": "ca_kb43r1_1"}, {"$set": {"status": "cancelled"}})   # PD ikut batal
    await _cocok(r1["eid"], True)
    je = await _jurnal_sumber(db, "cash_transaction", r1["kas_manual"]["id"])
    assert await gl.baris_uang_muka_pemasok(je) == {0: "1-1410"}   # baris Dr 1-1400 kas uang muka → 1-1410
    with pytest.raises(ValueError) as ei:
        await gl.reverse_entry(je["id"], HARI_INI, "uji KB43 balik manual", AKTOR_UJI)
    assert "sudah dipindah ke akun 1-1410 Uang Muka Pemasok" in str(ei.value), str(ei.value)
    assert not await gl.reversal_of(await _jurnal_sumber(db, "cash_transaction", r1["kas_manual"]["id"]))
    # PT belum pindah: pembalikan manual tetap seperti dulu (cermin 1-1400).
    je0 = await _jurnal_sumber(db, "cash_transaction", r0["kas_manual"]["id"])
    rev0 = await gl.reverse_entry(je0["id"], HARI_INI, "uji KB43 balik manual", AKTOR_UJI)
    assert _set(rev0) == _cermin(je0)
    await _cocok(r0["eid"], False)


# ═══ Uang muka terbuka & butir tutup buku ════════════════════════════════════════════════════════════════════════════
async def test_KB4_3_U12_uang_muka_terbuka_dan_butir_tutup_buku(klien, db, kepala_admin, akun, sesi, peran_tanpa_acuan,
                                                               dunia):
    """PT U pindah (uang muka 700.000 − potongan 200.000 terjurnal sesudah pindah = 500.000; PD 1.000.000 belum LPJ,
    PD 300.000 ber-LPJ 200.000 dengan sisa 100.000 belum kembali); PT W belum pindah (uang muka 400.000, PD 250.000)."""
    from services import closing_checklist as ceklis
    from services import gl_service as gl
    from services import supplier_advance_service as sas
    a = await _pt(db, "KB43U")
    await _uang_muka_kas(db, a, "t1", 700_000)
    await _pd_cair(db, a, "ca_kb43u_1", JT)
    await _pd_cair(db, a, "ca_kb43u_2", 300_000)
    await db.cash_advances.update_one({"id": "ca_kb43u_2"}, {"$set": {"status": "settled"}})
    await db.cash_advance_settlements.insert_one({   # LPJ 200.000 terjurnal, sisa 100.000 masih di tangan
        "id": "stl_kb43u_2", "number": "LPJ-KB43U-2", "cash_advance_id": "ca_kb43u_2", "entity_id": a,
        "status": "posted_to_gl", "total_pengeluaran": 200_000.0,
        "sisa_dikembalikan": {"amount": 100_000.0, "status": "open"}})
    await jurnal(a, HARI_INI, [("6-4600", 200_000, 0), ("1-1400", 0, 200_000)], "LPJ KB43U-2", "kb43u_lpj")
    await _siapkan_setujui(a)
    await _kontrabon(db, a, "cb_kb43u_1", 200_000, status="paid", applied=True)
    await gl.post_contra_bon_deduction(cb_id="cb_kb43u_1", deduction_id="ded_cb_kb43u_1", entity_id=a,
                                       kind="supplier_advance", amount=200_000, label="uji KB43U", date=HARI_INI)
    b = await _pt(db, "KB43W")
    await _uang_muka_kas(db, b, "t1", 400_000)
    await _pd_cair(db, b, "ca_kb43w_1", 250_000)
    r = await klien.get("/api/uang-muka/terbuka", headers=_h(kepala_admin, a), params={"entity_id": a})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["pemasok_pindah"] is True and j["karyawan"]["total"] == 1_100_000.0
    g = j["karyawan"]["pemegang"]
    assert [(x["pemegang"]["nama"], x["total"], [p["number"] for p in x["pd"]]) for x in g] == [
        ("Staf KB43", 1_100_000.0, ["CA-KB43U-1", "CA-KB43U-2"])]
    assert [(p["dicairkan"], p["dipertanggungjawabkan"], p["sisa"], p["lpj_number"]) for p in g[0]["pd"]] == [
        (1_000_000.0, 0.0, 1_000_000.0, ""), (300_000.0, 200_000.0, 100_000.0, "LPJ-KB43U-2")]
    assert [(x["akun"], x["saldo"], x["daftar"], x["selisih"], x["isi"]) for x in j["akun"]] == [
        ("1-1400", 1_100_000.0, 1_100_000.0, 0.0, ["karyawan"]),
        ("1-1410", 500_000.0, 500_000.0, 0.0, ["pemasok"])]
    assert j["pemasok"]["total"] == 500_000.0 and j["pemasok"]["akun"] == "1-1410"
    assert "biaya dibayar dimuka" in j["akun"][0]["keterangan"]
    jb = await sas.uang_muka_terbuka(b)
    assert jb["pemasok_pindah"] is False and jb["pemasok"]["akun"] == "1-1400"
    assert [(x["akun"], x["saldo"], x["daftar"], x["selisih"], x["isi"]) for x in jb["akun"]] == [
        ("1-1400", 650_000.0, 650_000.0, 0.0, ["karyawan", "pemasok"])]
    assert "masih memuat uang muka pemasok sampai PT ini memindah saldonya" in jb["akun"][0]["keterangan"]
    # Butir tutup buku: cocok → ok; biaya dibayar dimuka di 1-1400 → peringatan (tidak menahan tutup buku).
    bulan = HARI_INI[:7]

    async def _butir(eid):
        c = await ceklis.build("month", bulan, eid)
        return c, next(it for it in c["items"] if it["key"] == "uang_muka_cocok")

    _c, it = await _butir(a)
    assert it["status"] == "ok" and it["value"] == 0 and "keadaan hari ini" in it["detail"], it
    assert it["link"] == {"view": "petty-cash", "preset": {"chip": "uang-muka-terbuka"}}
    await jurnal(a, HARI_INI, [("1-1400", 60_000, 0), ("1-1100", 0, 60_000)], "sewa dibayar dimuka", "kb43a_prepaid")
    c, it = await _butir(a)
    assert it["status"] == "warning" and it["value"] == 1, it
    assert "1-1400" in it["detail"] and "selisih Rp 60.000" in it["detail"] and "biaya dibayar dimuka" in it["detail"]
    assert all(x["status"] != "blocking" for x in c["items"] if x["key"] == "uang_muka_cocok")
    # Izin: baca saja `cash.view`; tanpa itu 403. Pratinjau pindah saldo butuh `accounting.manage`.
    kas = await sesi(await akun(await peran_tanpa_acuan({"cash": ["view"]}), entitas=[a]), entitas=a)
    buku = await sesi(await akun(await peran_tanpa_acuan({"accounting": ["view"]}), entitas=[a]), entitas=a)
    assert (await klien.get("/api/uang-muka/terbuka", headers=kas, params={"entity_id": a})).status_code == 200
    assert (await klien.get("/api/uang-muka/terbuka", headers=buku, params={"entity_id": a})).status_code == 403
    assert (await klien.get(f"/api/uang-muka-pemasok/pindah/{a}/pratinjau", headers=kas)).status_code == 403
    r = await klien.get("/api/uang-muka/terbuka", headers=_h(kepala_admin, "all"), params={"entity_id": "all"})
    assert r.status_code == 400


async def test_KB4_3_U13_lewat_api_siapkan_setujui_tolak(klien, db, akun, sesi, peran_tanpa_acuan, dunia):
    from services import supplier_advance_mode as mode
    v = await _pt(db, "KB43V")
    await _uang_muka_kas(db, v, "t1", 90_000)
    peran = await peran_tanpa_acuan({"accounting": ["view", "manage"]})
    s1 = await sesi(await akun(peran, entitas=[v]), entitas=v)
    s2 = await sesi(await akun(peran, entitas=[v]), entitas=v)
    p = (await klien.get(f"/api/uang-muka-pemasok/pindah/{v}/pratinjau", headers=s1)).json()
    assert p["total"] == 90_000.0 and p["bisa_siapkan"] is True
    r = await klien.post(f"/api/uang-muka-pemasok/pindah/{v}/siapkan", headers=s1)
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    r = await klien.post(f"/api/uang-muka-pemasok/pindah/{uid}/setujui", headers=s1, json={"sidik": p["sidik"]})
    assert r.status_code == 403, r.text
    r = await klien.post(f"/api/uang-muka-pemasok/pindah/{uid}/tolak", headers=s2, json={"alasan": "ulangi besok"})
    assert r.status_code == 200 and r.json()["status"] == "ditolak", r.text
    r = await klien.post(f"/api/uang-muka-pemasok/pindah/{v}/siapkan", headers=s1)
    uid = r.json()["id"]
    r = await klien.post(f"/api/uang-muka-pemasok/pindah/{uid}/setujui", headers=s2, json={"sidik": p["sidik"]})
    assert r.status_code == 200 and r.json()["status"] == "disetujui", r.text
    assert await mode.aktif(v) and await _saldo("1-1410", v) == 90_000.0
    assert await db.audit_logs.count_documents({"action": {"$in": [
        "supplier_advance_cutover_prepared", "supplier_advance_cutover_rejected",
        "supplier_advance_cutover_approved"]}, "scope_entity_id": v}) == 4   # siapkan ×2, tolak, setujui


# ═══ Pendaftaran: kontrol dua orang terpasang, Posting Gagal, teks playbook netral ═════════════════════════════════
async def test_KB4_3_U14_pendaftaran(aplikasi):
    import config_registry as registry
    from config_catalog_kontrol import _BELUM_DIPASANG, _TITIK
    from services import finance_case_playbooks as pbs
    from services import posting_registry as reg
    assert _TITIK["pindah_uang_muka_pemasok"] == ("services/supplier_advance_cutover_service.py:setujui",)
    assert "pindah_uang_muka_pemasok" not in _BELUM_DIPASANG
    assert registry.require("kontrol.pindah_uang_muka_pemasok.min_orang")["status"] == "active"
    k = reg.KINDS["pindah_uang_muka_pemasok"]
    assert (k["collection"], k["posters"], k["failed_query"]) == (
        "supplier_advance_cutovers", ("post_pindah_uang_muka_pemasok",),
        {"susulan_gl_status": "failed", "status": "memproses"})
    teks = " ".join(a["produces"] for a in pbs.BY_CODE["lebih_bayar_supplier"]["actions"])
    assert "1-1400" not in teks and "Uang Muka Pemasok" in teks

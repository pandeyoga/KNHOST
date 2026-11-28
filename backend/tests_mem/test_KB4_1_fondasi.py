"""Kas & Bank 4 Tugas 1 — fondasi: akun 1-1410 Uang Muka Pemasok (akun kontrol), kunci pemetaan
`hutang.uang_muka_pemasok`, penanda per PT `supplier_advance_mode`, SATU pembantu `gl_service.akun_uang_muka_pemasok`
untuk semua jalur uang muka pemasok, pengaturan `kas.pd_terbuka_maks` / `kas.lpj_tenggat_hari`, kontrol
`kontrol.pindah_uang_muka_pemasok`, penjaga INV-UMP-01.

Rancangan: `docs/superpowers/specs/2026-11-28-kas-bank-4-uang-muka-design.md` §5.3, §6, §7.9.6.

Persiapan (FIXTURE kecuali disebut ALUR):
  * `ent_ksc` TIDAK PERNAH dinyalakan di modul ini (PT belum pindah). `ent_kanda` dinyalakan langsung lewat
    `supplier_advance_mode.nyalakan` (FIXTURE — persetujuan pindah saldo yang menyalakannya dibangun Tugas 3).
  * Per PT: rekening bank + rekening kas kecil, pemasok, tagihan `posted`, kontrabon `approved` berpotongan uang muka
    pemasok, PD `approved` — semuanya disisipkan langsung.
  * Jalur lewat API (ALUR): bayar tagihan lebih dengan keputusan "jadi uang muka" (`ap_advance`), bayar tagihan lebih
    dalam toleransi (otomatis `ap_rounding_advance`), kasus "lebih bayar pemasok" → uang muka lalu pengembalian dana,
    bayar kontrabon (potongan uang muka terjurnal), PD dicairkan → LPJ disetujui → sisa dikembalikan.
  * `ent_uji_kb4m` — PT uji berpemetaan PT `kas_bank.uang_muka_karyawan` → 1-1401; potongan kontrabon dijurnal langsung
    lewat `gl_service.post_contra_bon_deduction` (FIXTURE).

REGRESI (bukti sebelum/sesudah): `BARIS_LAMA` di bawah direkam dari kode SEBELUM Tugas 1 (komit 730718e) dengan
`KB4_REKAM=<berkas.json>`; untuk PT yang belum pindah semua baris jurnal (akun, nama akun, debit, kredit, keterangan
dengan angka diganti `#`, kunci pemetaan), rencana jurnal kasus, akun efek keputusan selisih, dan kalimat pilihan
selisih bayar sama persis.

Hitung tangan (tiap PT; <UM> = 1-1400 di `ent_ksc`, 1-1410 di `ent_kanda`):
  T1 tagihan 1.000.000 dibayar 1.300.000 → kas 1.000.000 Dr 2-1100 / Cr 1-1100 + kas uang muka 300.000
     Dr <UM> / Cr 1-1100; keputusan selisih bayar berefek akun <UM>.
  T2 tagihan 500.000 dibayar 503.000 (toleransi pemasok 5.000) → otomatis uang muka 3.000: Dr <UM> / Cr 1-1100.
  K1 kasus lebih bayar 500.000 → Dr <UM> / Cr 2-1100 500.000.  K2 pengembalian dana 200.000 → Dr 1-1100 / Cr <UM>.
  C1 kontrabon tagihan 2.000.000 − potongan uang muka 400.000 → Dr 2-1100 / Cr <UM> 400.000 + kas 1.600.000
     Dr 2-1100 / Cr 1-1100.
  PD 1.000.000 cair (Dr 1-1400 / Cr 1-1110), LPJ 800.000 (Dr 6-4600 / Cr 1-1400), sisa 200.000 dikembalikan
  (Dr 1-1110 / Cr 1-1400) → uang muka karyawan tetap 1-1400 di KEDUA PT.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI, pt_uji
from services.book_date import tanggal_buku

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
KODE = {KSC: "ksc", KANDA: "kanda"}
REPO = Path(__file__).resolve().parents[2]
REKAM = os.environ.get("KB4_REKAM", "")
HARI_INI = tanggal_buku()
JT = 1_000_000
_rekaman: dict = {}
SIMPAN: dict = {}


def _baris(je: dict) -> list:
    """Baris jurnal ternormalisasi: angka di keterangan (nomor dokumen, nominal) diganti `#`."""
    out = []
    for ln in je["lines"]:
        d = dict(ln)
        d["description"] = re.sub(r"\d+", "#", d.get("description") or "")
        out.append(d)
    return out


def _set(je: dict) -> set:
    return {(ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]}


def _cocok(nama: str, nyata) -> None:
    if REKAM:
        _rekaman[nama] = nyata
        with open(REKAM, "w", encoding="utf-8") as f:
            json.dump(_rekaman, f, ensure_ascii=False, indent=1, sort_keys=True)
        return
    assert nyata == BARIS_LAMA[nama], f"{nama}: {json.dumps(nyata, ensure_ascii=False)}"


def _h(kepala: dict, ent: str) -> dict:
    return {**kepala, "X-Entity-Id": ent}


async def _jurnal_sumber(db, source_type: str, source_id: str) -> dict:
    jes = await db.journal_entries.find({"source_type": source_type, "source_id": source_id,
                                         "status": {"$ne": "void"}}, {"_id": 0}).to_list(5)
    assert len(jes) == 1, jes
    return jes[0]


def _tagihan(bid: str, total: float, eid: str) -> dict:
    return {"id": bid, "bill_number": bid.upper().replace("_", "-"), "entity_id": eid,
            "supplier_id": f"sup_kb4_{KODE[eid]}", "supplier_name": f"Pemasok KB4 {KODE[eid]}", "status": "posted",
            "grand_total": float(total), "subtotal": float(total), "amount_paid": 0.0, "payments": [],
            "timeline": [], "po_id": None, "bill_date": HARI_INI, "created_at": now_iso()}


@pytest.fixture(scope="module")
async def dunia(db):
    """FIXTURE: rekening bank & kas kecil, pemasok, tagihan T1/T2/C1, kontrabon C1 berpotongan uang muka, per PT."""
    from services import amendment_service
    from services import contra_bon_service as cbs
    await amendment_service.ensure_reasons()
    for eid, k in KODE.items():
        await db.bank_accounts.insert_many([
            {"id": f"rek_kb4_bank_{k}", "name": f"Bank KB4 {k}", "entity_id": eid, "account_type": "bank",
             "cash_type": "kas_besar", "is_active": True, "opening_balance": 0, "created_at": "2000-01-01T00:00:00"},
            {"id": f"rek_kb4_kecil_{k}", "name": f"Kas Kecil KB4 {k}", "entity_id": eid, "account_type": "cash",
             "cash_type": "kas_kecil", "is_active": True, "opening_balance": 0, "created_at": "2000-01-01T00:00:00"}])
        await db.suppliers.insert_one({"id": f"sup_kb4_{k}", "name": f"Pemasok KB4 {k}", "code": f"KB4{k.upper()}",
                                       "entity_id": eid, "status": "active", "advance_balance": 0.0,
                                       "payment_term_code": "NET30"})
        c1 = _tagihan(f"vb_kb4_c1_{k}", 2 * JT, eid)
        await db.vendor_bills.insert_many([_tagihan(f"vb_kb4_t1_{k}", 1 * JT, eid),
                                           _tagihan(f"vb_kb4_t2_{k}", 500_000, eid), dict(c1)])
        cb = {"id": f"cb_kb4_{k}", "number": f"CB-KB4-{k.upper()}", "entity_id": eid,
              "supplier_id": f"sup_kb4_{k}", "supplier_name": f"Pemasok KB4 {k}", "status": "approved",
              "created_at": now_iso(), "timeline": [], "payments": [], "decisions": [],
              "bills": [{"bill_id": c1["id"], "bill_number": c1["bill_number"], "applied_amount": 2 * JT,
                         "settled_amount": 0.0, "po_id": None}],
              "deductions": [{"id": f"ded_kb4_{k}", "kind": "supplier_advance", "amount": 400_000.0,
                              "posts_gl": True, "label": "uang muka pemasok", "ref_number": f"UM-KB4-{k.upper()}"}]}
        await db.contra_bons.insert_one(cbs.recompute(cb))
    return True


@pytest.fixture(scope="module")
async def pindah(dunia):
    """FIXTURE: `ent_kanda` sudah memindah saldo uang muka pemasoknya (penanda sekali tulis dinyalakan langsung)."""
    from services import supplier_advance_mode as mode
    SIMPAN["sejak_kanda"] = await mode.nyalakan(KANDA, "Uji KB4")
    return True


@pytest.fixture(scope="module")
async def pt_kb4m(aplikasi):
    """FIXTURE: PT uji `ent_uji_kb4m` berpemetaan PT `kas_bank.uang_muka_karyawan` → akun PT 1-1401 (U1d, U3d)."""
    from schemas_finance import GLAccountCreate
    from services import gl_mapping_service as glm, gl_service as gl
    pt = await pt_uji("KB4M")
    await gl.create_account(GLAccountCreate(code="1-1401", name="Uang Muka KB4M", type="asset",
                                            parent_code="1-1000"), entity_id=pt)
    await glm.set_mapping("kas_bank.uang_muka_karyawan", pt, "1-1401", "uji KB4 pemetaan PT", AKTOR_UJI)
    return pt


# ── Jalur uang muka pemasok (sama untuk kedua PT) ─────────────────────────────────────────────────────────────────────
async def _bayar_lebih(klien, db, kepala, eid: str) -> dict:
    """ALUR: T1 (keputusan `ap_advance`) dan T2 (lebih dalam toleransi → otomatis)."""
    from services import payment_variance_service as pvs
    k, h = KODE[eid], _h(kepala, eid)
    hasil: dict = {}
    t1 = await db.vendor_bills.find_one({"id": f"vb_kb4_t1_{k}"}, {"_id": 0})
    nilai = await pvs.assess_bill(t1, 1.3 * JT)
    hasil["pilihan"] = [o["impact"] for o in nilai["options"]]
    for tag, nominal, selisih in (("t1", 1.3 * JT, {"kind": "ap_advance", "reason_code": "supplier_advance",
                                                    "note": "uji KB4 lebih bayar"}),
                                  ("t2", 503_000, None)):
        body = {"amount": nominal, "paid_at": HARI_INI, "bank_account_id": f"rek_kb4_bank_{k}"}
        if selisih:
            body["variance"] = selisih
        bid = f"vb_kb4_{tag}_{k}"
        r = await klien.post(f"/api/vendor-bills/{bid}/pay", headers={**h, "Idempotency-Key": f"kb4-{bid}"},
                             json=body)
        assert r.status_code == 200, r.text
        kas = {c["ref_type"]: c async for c in db.cash_transactions.find({"ref_id": bid}, {"_id": 0})}
        assert set(kas) == {"vendor_bill", "ap_advance"}, kas
        hasil[f"{tag}_bayar"] = await _jurnal_sumber(db, "cash_transaction", kas["vendor_bill"]["id"])
        hasil[f"{tag}_uang_muka"] = await _jurnal_sumber(db, "cash_transaction", kas["ap_advance"]["id"])
        keputusan = await db.payment_variance_decisions.find_one({"bill_id": bid}, {"_id": 0})
        assert keputusan and keputusan["status"] == "done", keputusan
        hasil[f"{tag}_efek"] = {"kind": keputusan["kind"], "account": keputusan["effect"]["account"],
                                "advance_amount": keputusan["effect"]["advance_amount"]}
    return hasil


async def _kasus(klien, db, kepala, eid: str) -> dict:
    """ALUR: K1 kasus lebih bayar → uang muka; K2 kasus lebih bayar → pengembalian dana. Rencana PERIKSA ikut direkam."""
    from services import finance_case_actions as acts
    k, h = KODE[eid], _h(kepala, eid)
    sup = f"sup_kb4_{k}"
    hasil: dict = {}
    for tag, aksi, nominal, extra in (("k1", "uang_muka_supplier", 500_000, {}),
                                      ("k2", "terima_refund_supplier", 200_000,
                                       {"account_id": f"rek_kb4_bank_{k}"})):
        r = await klien.post("/api/finance-cases", headers=h, json={
            "case_type": "lebih_bayar_supplier", "amount": nominal, "supplier_id": sup, "entity_id": eid,
            "source": {"kind": "manual", "label": f"uji KB4 {tag}"}})
        assert r.status_code == 200, r.text
        case = r.json()
        isi = {"action": aksi, "reason_code": "supplier_advance", "supplier_id": sup, "amount": nominal, **extra}
        rencana = await acts.precheck(aksi, case, isi)
        hasil[f"{tag}_rencana"] = rencana["journals"]
        r = await klien.post(f"/api/finance-cases/{case['id']}/resolve", headers=h, json=isi)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "resolved", r.json()
        if tag == "k1":
            jes = await db.journal_entries.find({"source_type": "finance_case", "source_id": {
                "$regex": f"^{case['id']}:"}, "status": {"$ne": "void"}}, {"_id": 0}).to_list(5)
            assert len(jes) == 1, jes
            hasil["k1_jurnal"] = jes[0]
        else:
            kas = await db.cash_transactions.find({"ref_type": "finance_case", "ref_id": case["id"]},
                                                  {"_id": 0}).to_list(5)
            assert len(kas) == 1 and kas[0]["direction"] == "in", kas
            hasil["k2_jurnal"] = await _jurnal_sumber(db, "cash_transaction", kas[0]["id"])
    sp = await db.suppliers.find_one({"id": sup}, {"_id": 0})
    assert sp["advance_balance"] == 300_000 + 3_000 + 500_000 - 200_000, sp   # T1 + T2 + K1 − K2
    return hasil


async def _kontrabon(klien, db, kepala, eid: str) -> dict:
    """ALUR: C1 bayar kontrabon — potongan uang muka pemasok 400.000 terjurnal + kas 1.600.000."""
    k = KODE[eid]
    r = await klien.post(f"/api/contra-bons/cb_kb4_{k}/pay", headers=_h(kepala, eid),
                         json={"paid_at": HARI_INI, "bank_account_id": f"rek_kb4_bank_{k}"})
    assert r.status_code == 200, r.text
    kas = await db.cash_transactions.find({"ref_type": "contra_bon", "ref_id": f"cb_kb4_{k}"},
                                          {"_id": 0}).to_list(5)
    assert len(kas) == 1 and kas[0]["amount"] == 1.6 * JT, kas
    return {"c1_potongan": await _jurnal_sumber(db, "contra_bon_deduction", f"cb_kb4_{k}:ded_kb4_{k}"),
            "c1_bayar": await _jurnal_sumber(db, "cash_transaction", kas[0]["id"])}


async def _uang_muka_karyawan(klien, db, kepala, eid: str) -> dict:
    """ALUR: PD 1.000.000 dicairkan dari kas kecil → LPJ transportasi 800.000 disetujui → sisa 200.000 dikembalikan."""
    k, h = KODE[eid], _h(kepala, eid)
    ca = f"ca_kb4_{k}"
    await db.cash_advances.insert_one({
        "id": ca, "number": f"PD-KB4-{k.upper()}", "entity_id": eid, "status": "approved", "kegiatan": "uji KB4",
        "divisi": "Umum", "lines": [{"description": "uang muka", "qty": 1, "unit_price": JT, "amount": JT}],
        "total_amount": float(JT), "approvals": [], "payment_method": "cash", "created_by": "Staf KB4",
        "created_by_id": "usr_staf_kb4", "created_at": now_iso()})
    rek = f"rek_kb4_kecil_{k}"
    r = await klien.post(f"/api/cash-advances/{ca}/disburse", headers=h,
                         json={"cash_type": "kas_kecil", "account_id": rek, "note": "uji KB4"})
    assert r.status_code == 200 and r.json()["status"] == "disbursed", r.text
    cair = await db.cash_transactions.find_one({"ref_type": "cash_advance", "ref_id": ca}, {"_id": 0})
    r = await klien.post("/api/cash-advance-settlements", headers=h, json={
        "cash_advance_id": ca, "periode": HARI_INI[:7],
        "expense_lines": [{"date": HARI_INI, "description": "uji transportasi", "category": "transportasi",
                           "amount": 800_000}]})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    for langkah in ("submit", "approve"):
        r = await klien.post(f"/api/cash-advance-settlements/{sid}/{langkah}", headers=h)
        assert r.status_code == 200, r.text
    r = await klien.post(f"/api/cash-advance-settlements/{sid}/return-remainder", headers=h,
                         json={"cash_type": "kas_kecil", "account_id": rek})
    assert r.status_code == 200, r.text
    kembali = await db.cash_transactions.find_one({"ref_type": "cash_advance_return", "ref_id": sid}, {"_id": 0})
    return {"pd_cair": await _jurnal_sumber(db, "cash_transaction", cair["id"]),
            "pd_lpj": await _jurnal_sumber(db, "petty_cash_settlement", sid),
            "pd_kembali": await _jurnal_sumber(db, "cash_transaction", kembali["id"])}


def _harapan_pemasok(um: str) -> dict:
    """Hitung tangan baris jurnal (akun, debit, kredit) jalur pemasok dengan akun uang muka `um`."""
    return {"t1_bayar": {("2-1100", 1.0 * JT, 0.0), ("1-1100", 0.0, 1.0 * JT)},
            "t1_uang_muka": {(um, 300_000.0, 0.0), ("1-1100", 0.0, 300_000.0)},
            "t2_bayar": {("2-1100", 500_000.0, 0.0), ("1-1100", 0.0, 500_000.0)},
            "t2_uang_muka": {(um, 3_000.0, 0.0), ("1-1100", 0.0, 3_000.0)},
            "k1_jurnal": {(um, 500_000.0, 0.0), ("2-1100", 0.0, 500_000.0)},
            "k2_jurnal": {("1-1100", 200_000.0, 0.0), (um, 0.0, 200_000.0)},
            "c1_potongan": {("2-1100", 400_000.0, 0.0), (um, 0.0, 400_000.0)},
            "c1_bayar": {("2-1100", 1.6 * JT, 0.0), ("1-1100", 0.0, 1.6 * JT)}}


HARAPAN_KARYAWAN = {"pd_cair": {("1-1400", 1.0 * JT, 0.0), ("1-1110", 0.0, 1.0 * JT)},
                    "pd_lpj": {("6-4600", 800_000.0, 0.0), ("1-1400", 0.0, 800_000.0)},
                    "pd_kembali": {("1-1110", 200_000.0, 0.0), ("1-1400", 0.0, 200_000.0)}}


# ═══ Regresi: PT belum pindah — semua jalur uang muka pemasok persis seperti sebelum Tugas 1 (1-1400) ═══════════════
async def test_KB4_1_U1a_pt_belum_pindah_lebih_bayar_tagihan(klien, db, kepala_admin, dunia):
    hasil = await _bayar_lebih(klien, db, kepala_admin, KSC)
    harap = _harapan_pemasok("1-1400")
    for nama in ("t1_bayar", "t1_uang_muka", "t2_bayar", "t2_uang_muka"):
        assert _set(hasil[nama]) == harap[nama], (nama, hasil[nama]["lines"])
        _cocok(nama, _baris(hasil[nama]))
    assert hasil["t1_efek"] == {"kind": "ap_advance", "account": "1-1400", "advance_amount": 300_000.0}
    assert hasil["t2_efek"] == {"kind": "ap_rounding_advance", "account": "1-1400", "advance_amount": 3_000.0}
    _cocok("t1_efek", hasil["t1_efek"])
    _cocok("t2_efek", hasil["t2_efek"])
    _cocok("pilihan_selisih_bayar", hasil["pilihan"])


async def test_KB4_1_U1b_pt_belum_pindah_kasus_lebih_bayar_dan_refund(klien, db, kepala_admin, dunia):
    hasil = await _kasus(klien, db, kepala_admin, KSC)
    harap = _harapan_pemasok("1-1400")
    for nama in ("k1_jurnal", "k2_jurnal"):
        assert _set(hasil[nama]) == harap[nama], (nama, hasil[nama]["lines"])
        _cocok(nama, _baris(hasil[nama]))
    assert [(j["debit_acc"], j["credit_acc"], j["amount"]) for j in hasil["k1_rencana"]] == [
        ("1-1400", "2-1100", 500_000.0)]
    assert [(j["debit_acc"], j["credit_acc"], j["amount"]) for j in hasil["k2_rencana"]] == [
        ("1-1100", "1-1400", 200_000.0)]
    _cocok("k1_rencana", hasil["k1_rencana"])
    _cocok("k2_rencana", hasil["k2_rencana"])


async def test_KB4_1_U1c_pt_belum_pindah_potongan_kontrabon(klien, db, kepala_admin, dunia):
    hasil = await _kontrabon(klien, db, kepala_admin, KSC)
    harap = _harapan_pemasok("1-1400")
    for nama in ("c1_potongan", "c1_bayar"):
        assert _set(hasil[nama]) == harap[nama], (nama, hasil[nama]["lines"])
        _cocok(nama, _baris(hasil[nama]))


async def test_KB4_1_U1d_pt_belum_pindah_pemetaan_pt_tetap_berlaku(db, pt_kb4m):
    """PT belum pindah yang memetakan `kas_bank.uang_muka_karyawan` ke akun PT (1-1401): potongan uang muka pemasok
    tetap dialihkan ke akun pemetaan itu seperti sebelum Tugas 1 (pembantu mengembalikan 1-1400, bukan akun pemetaan)."""
    from services import gl_service as gl
    pt = pt_kb4m
    je = await gl.post_contra_bon_deduction(cb_id="cb_kb4m", deduction_id="d1", entity_id=pt,
                                            kind="supplier_advance", amount=250_000, label="KB4M d1", date=HARI_INI)
    assert _set(je) == {("2-1100", 250_000.0, 0.0), ("1-1401", 0.0, 250_000.0)}, je["lines"]
    _cocok("potongan_pemetaan_pt", _baris(je))


# ═══ Uang muka karyawan: PD cair, LPJ, kembalikan sisa — 1-1400 di PT belum pindah dan PT sudah pindah ═══════════
async def test_KB4_1_U2a_uang_muka_karyawan_pt_belum_pindah(klien, db, kepala_admin, dunia):
    hasil = await _uang_muka_karyawan(klien, db, kepala_admin, KSC)
    for nama, harap in HARAPAN_KARYAWAN.items():
        assert _set(hasil[nama]) == harap, (nama, hasil[nama]["lines"])
        _cocok(nama, _baris(hasil[nama]))


async def test_KB4_1_U2b_uang_muka_karyawan_pt_sudah_pindah_tetap_1_1400(klien, db, kepala_admin, pindah):
    hasil = await _uang_muka_karyawan(klien, db, kepala_admin, KANDA)
    for nama, harap in HARAPAN_KARYAWAN.items():
        assert _set(hasil[nama]) == harap, (nama, hasil[nama]["lines"])


# ═══ PT sudah pindah: jalur pemasok yang sama memakai 1-1410 ═════════════════════════════════════════════════════════
async def test_KB4_1_U3a_pt_pindah_lebih_bayar_tagihan_ke_1_1410(klien, db, kepala_admin, pindah):
    hasil = await _bayar_lebih(klien, db, kepala_admin, KANDA)
    harap = _harapan_pemasok("1-1410")
    for nama in ("t1_bayar", "t1_uang_muka", "t2_bayar", "t2_uang_muka"):
        assert _set(hasil[nama]) == harap[nama], (nama, hasil[nama]["lines"])
    um = next(ln for ln in hasil["t1_uang_muka"]["lines"] if ln["debit"])
    assert um["account_name"] == "Uang Muka Pemasok", um
    assert hasil["t1_efek"] == {"kind": "ap_advance", "account": "1-1410", "advance_amount": 300_000.0}
    assert hasil["t2_efek"] == {"kind": "ap_rounding_advance", "account": "1-1410", "advance_amount": 3_000.0}
    assert hasil["pilihan"] == ["Uang Muka (1-1410) +Rp 300.000 · kas keluar lebih besar."], hasil["pilihan"]


async def test_KB4_1_U3b_pt_pindah_kasus_lebih_bayar_dan_refund_ke_1_1410(klien, db, kepala_admin, pindah):
    hasil = await _kasus(klien, db, kepala_admin, KANDA)
    harap = _harapan_pemasok("1-1410")
    for nama in ("k1_jurnal", "k2_jurnal"):
        assert _set(hasil[nama]) == harap[nama], (nama, hasil[nama]["lines"])
    assert [(j["debit_acc"], j["credit_acc"], j["amount"]) for j in hasil["k1_rencana"]] == [
        ("1-1410", "2-1100", 500_000.0)]
    assert [(j["debit_acc"], j["credit_acc"], j["amount"]) for j in hasil["k2_rencana"]] == [
        ("1-1100", "1-1410", 200_000.0)]


async def test_KB4_1_U3c_pt_pindah_potongan_kontrabon_ke_1_1410(klien, db, kepala_admin, pindah):
    from pembantu import saldo_akun
    hasil = await _kontrabon(klien, db, kepala_admin, KANDA)
    harap = _harapan_pemasok("1-1410")
    for nama in ("c1_potongan", "c1_bayar"):
        assert _set(hasil[nama]) == harap[nama], (nama, hasil[nama]["lines"])
    # 1-1410 PT pindah = T1 + T2 + K1 − K2 − C1 = 300.000 + 3.000 + 500.000 − 200.000 − 400.000 = 203.000 (FIXTURE
    # tidak memindah saldo lama: KANDA belum punya uang muka pemasok sebelum dinyalakan). 1-1400 KANDA = uang muka
    # karyawan saja (PD U2b: 1.000.000 − 800.000 − 200.000 = 0).
    assert await saldo_akun("1-1410", KANDA) == 203_000.0
    assert await saldo_akun("1-1400", KANDA) == 0.0
    # PT belum pindah tidak tersentuh: 1-1410 KSC kosong, semua uang muka pemasoknya di 1-1400.
    assert await saldo_akun("1-1410", KSC) == 0.0
    assert await saldo_akun("1-1400", KSC) == 203_000.0


async def test_KB4_1_U3d_pt_pindah_memakai_akun_pemetaan_pt(db, pt_kb4m):
    """PT pindah: pembantu = akun pemetaan PT `hutang.uang_muka_pemasok` (bawaan 1-1410) — tidak ikut pemetaan uang muka
    karyawan PT itu (1-1401); dipetakan ke 1-1411 → potongan berikutnya ke 1-1411, uang muka karyawan tetap 1-1401."""
    from schemas_finance import GLAccountCreate
    from services import gl_mapping_service as glm, gl_service as gl, supplier_advance_mode as mode
    pt = pt_kb4m
    assert await gl.akun_uang_muka_pemasok(pt) == "1-1400"
    await mode.nyalakan(pt, AKTOR_UJI)
    assert await gl.akun_uang_muka_pemasok(pt) == "1-1410"
    je = await gl.post_contra_bon_deduction(cb_id="cb_kb4m", deduction_id="d2", entity_id=pt,
                                            kind="supplier_advance", amount=100_000, label="KB4M d2", date=HARI_INI)
    assert _set(je) == {("2-1100", 100_000.0, 0.0), ("1-1410", 0.0, 100_000.0)}, je["lines"]
    await gl.create_account(GLAccountCreate(code="1-1411", name="Uang Muka Pemasok KB4M", type="asset",
                                            parent_code="1-1000"), entity_id=pt)
    await glm.set_mapping("hutang.uang_muka_pemasok", pt, "1-1411", "uji KB4 pemetaan PT", AKTOR_UJI)
    assert await gl.akun_uang_muka_pemasok(pt) == "1-1411"
    je = await gl.post_contra_bon_deduction(cb_id="cb_kb4m", deduction_id="d3", entity_id=pt,
                                            kind="supplier_advance", amount=50_000, label="KB4M d3", date=HARI_INI)
    assert _set(je) == {("2-1100", 50_000.0, 0.0), ("1-1411", 0.0, 50_000.0)}, je["lines"]
    assert await glm.account_for("kas_bank.uang_muka_karyawan", pt) == "1-1401"
    kontrol = await glm.control_accounts(pt)
    assert (kontrol.get("1-1410"), kontrol.get("1-1411"), kontrol.get("1-1400")) == (
        "uang_muka_pemasok", "uang_muka_pemasok", None)


# ═══ Akun kontrol: jurnal manual ke 1-1410 ditolak dengan dokumen pengganti ═════════════════════════════════════════
@pytest.mark.parametrize("ent", [KSC, KANDA])
async def test_KB4_1_U4_jurnal_manual_ke_1_1410_ditolak(klien, db, kepala_admin, pindah, ent):
    n0 = await db.journal_entries.count_documents({})
    r = await klien.post("/api/gl/journal", headers=_h(kepala_admin, ent), json={
        "date": HARI_INI, "description": "uji KB4 manual", "lines": [
            {"account_code": "1-1410", "debit": 100_000, "credit": 0, "description": "uji KB4"},
            {"account_code": "4-9000", "debit": 0, "credit": 100_000, "description": "uji KB4"}]})
    assert r.status_code == 422, r.text
    assert r.json()["detail"] == ("Akun 1-1410 · Uang Muka Pemasok adalah akun kontrol uang muka pemasok dan tidak "
                                  "menerima jurnal manual. Koreksi lewat Kasus Keuangan atau Kontrabon."), r.json()
    assert await db.journal_entries.count_documents({}) == n0
    r = await klien.get("/api/gl/accounts", headers=kepala_admin, params={"entity_id": ent})
    by = {a["code"]: a for a in r.json()}
    assert (by["1-1410"]["is_control"], by["1-1410"]["control_ledger"], by["1-1410"]["manual_allowed"],
            by["1-1410"]["control_ledger_label"]) == (True, "uang_muka_pemasok", False, "uang muka pemasok")
    assert (by["1-1400"]["is_control"], by["1-1400"]["manual_allowed"]) == (False, True)


# ═══ Penanda per PT sekali tulis ════════════════════════════════════════════════════════════════════════════════════
async def test_KB4_1_U5_nyalakan_sekali_tulis(db, pindah):
    from services import supplier_advance_mode as mode
    sejak = SIMPAN["sejak_kanda"]
    assert sejak and await mode.aktif_sejak(KANDA) == sejak
    assert await mode.aktif(KANDA) is True
    assert await mode.aktif(KSC) is False and await mode.aktif_sejak(KSC) == ""
    assert await mode.aktif("") is False and await mode.aktif(None) is False
    assert await mode.nyalakan(KANDA, {"name": "Orang Lain"}) == sejak
    assert await mode.aktif_sejak(KANDA) == sejak
    docs = [d async for d in db.system_settings.find({"scope": mode.SCOPE}, {"_id": 0})]
    assert len(docs) == 1 and docs[0][KANDA] == {"sejak": sejak, "oleh": "Uji KB4"}, docs
    with pytest.raises(ValueError):
        await mode.nyalakan("ent ksc; drop", "uji")


# ═══ Akun bawaan, konstanta, kunci pemetaan, buku pembantu ═══════════════════════════════════════════════════════════
async def test_KB4_1_U6_akun_bawaan_dan_kunci_pemetaan(klien, db, kepala_admin):
    from services import gl_mapping_registry as reg, gl_service as gl
    assert (gl.ACC_UANG_MUKA, gl.ACC_UANG_MUKA_PEMASOK) == ("1-1400", "1-1410")
    bagan = {c: (n, t, p, ok) for c, n, t, p, ok in gl.DEFAULT_COA}
    assert bagan["1-1410"] == ("Uang Muka Pemasok", "asset", "1-1000", True)
    assert bagan["1-1400"] == ("Uang Muka & Biaya Dibayar Dimuka", "asset", "1-1000", True)   # nama lama tetap
    assert await db.gl_accounts.find_one({"code": "1-1410", "entity_id": None})
    e = reg.require("hutang.uang_muka_pemasok")
    assert (e["default"], e["module"], e["control"], e["remap"]) == ("1-1410", "hutang", "uang_muka_pemasok", True)
    assert reg.REMAP_BY_DEFAULT["1-1410"] == "hutang.uang_muka_pemasok"
    assert reg.REMAP_BY_DEFAULT["1-1400"] == "kas_bank.uang_muka_karyawan"
    assert reg.CONTROL_LEDGERS["uang_muka_pemasok"] == {"label": "uang muka pemasok",
                                                        "dokumen": "Kasus Keuangan atau Kontrabon"}
    assert "hutang" in dict(reg.MODULES)
    r = await klien.get("/api/gl/account-mappings", headers=kepala_admin, params={"entity_id": KSC})
    assert r.status_code == 200, r.text
    baris = next(x for x in r.json()["rows"] if x["key"] == "hutang.uang_muka_pemasok")
    assert (baris["account_code"], baris["account_name"], baris["status"]) == ("1-1410", "Uang Muka Pemasok", "ok")
    assert "hutang" in {m["id"] for m in r.json()["modules"]}


# ═══ Pengaturan & kontrol baru terdaftar ═════════════════════════════════════════════════════════════════════════════
async def test_KB4_1_U7_pengaturan_batas_dan_tenggat_uang_muka_karyawan(aplikasi):
    import config_registry as registry
    from services import config_resolver as resolver
    maks, tenggat = registry.require("kas.pd_terbuka_maks"), registry.require("kas.lpj_tenggat_hari")
    assert (maks["type"], maks["default"], maks["min"], maks["scopes"]) == ("int", 1, 0, ["global", "entity"])
    assert (tenggat["type"], tenggat["default"], tenggat["min"], tenggat["max"], tenggat["unit"],
            tenggat["scopes"]) == ("duration", 7, 1, 90, "hari", ["global", "entity"])
    for e in (maks, tenggat):
        assert (e["group"], e["section"], e["permission"]) == ("bank-kasus", "uang-muka-karyawan",
                                                               ["accounting", "manage"])
        # Tugas 1 mendaftarkan; Tugas 2 memasang pembacanya (pengajuan & pencairan PD) → aktif berpembaca
        # (`test_KB4_2_pd.py` U11 memeriksa kabelnya).
        assert e["status"] == "active" and not e["not_used_reason"] and e["consumers"], e
    assert "0 = tanpa batas" in maks["help"]
    assert await resolver.value_of("kas.pd_terbuka_maks", {"entity_id": KSC}) == 1
    assert await resolver.value_of("kas.lpj_tenggat_hari", {"entity_id": KSC}) == 7
    indeks = json.loads((REPO / "frontend/src/features/settings/config/configKeyIndex.json").read_text("utf-8"))
    for key in ("kas.pd_terbuka_maks", "kas.lpj_tenggat_hari"):
        assert indeks["keys"][key] == ["bank-kasus", "uang-muka-karyawan"], key


async def test_KB4_1_U8_kontrol_pindah_uang_muka_pemasok(aplikasi):
    import config_registry as registry
    from config_catalog_kontrol import ADMIN_TETAP_DUA_ORANG_AWAL, AKSI_BY_ID, _BELUM_DIPASANG
    from services.dual_control import butuh_orang_kedua
    a = AKSI_BY_ID["pindah_uang_muka_pemasok"]
    assert (a["kelompok"], a["awal"], a["punya_nominal"]) == ("B", "2", False)
    e = registry.require("kontrol.pindah_uang_muka_pemasok.min_orang")
    # Kas & Bank 4 Tugas 3 — titik pasangnya (setujui pindah saldo uang muka pemasok) terpasang: kunci aktif.
    assert (e["default"], e["group"], e["status"]) == ("2", "persetujuan", "active")
    assert registry.get("kontrol.pindah_uang_muka_pemasok.batas_nominal") is None
    assert "pindah_uang_muka_pemasok" not in _BELUM_DIPASANG
    assert "pindah_uang_muka_pemasok" in ADMIN_TETAP_DUA_ORANG_AWAL
    assert "pindah_uang_muka_pemasok" in registry.require("kontrol.admin_tetap_dua_orang")["default"]
    assert await butuh_orang_kedua("pindah_uang_muka_pemasok", KSC) is True


# ═══ Penjaga statis INV-UMP-01 ═══════════════════════════════════════════════════════════════════════════════════════
def test_KB4_1_U9_penjaga_akun_uang_muka_pemasok():
    sys.path.insert(0, str(REPO / "scripts" / "guardrails"))
    import verify_akun_uang_muka_pemasok as g
    bersih = g.contoh_bersih()
    assert not g._mini(bersih).violations
    merah = {**bersih, "services/ap_payment_service.py": bersih["services/ap_payment_service.py"]
             + "def akun_lebih_bayar():\n    return '1-1400'\n"}
    assert any("ap_payment_service.py:akun_lebih_bayar" in v for v in g._mini(merah).violations)
    # Putaran 1 (Minor 3) — konstanta lewat alias impor juga ditolak.
    alias = {**bersih, "services/payment_variance_service.py": "from services.gl_service import ACC_UANG_MUKA as UM\n"
             "def efek():\n    return {'account': UM}\n"}
    assert any("payment_variance_service.py:<modul>" in v and "[2]" in v for v in g._mini(alias).violations)
    skrip = REPO / "scripts/guardrails/verify_akun_uang_muka_pemasok.py"
    swa = subprocess.run([sys.executable, str(skrip), "--self-test"], capture_output=True, text=True, cwd=REPO)
    assert swa.returncode == 0 and "SELF-TEST HIJAU" in swa.stdout, swa.stdout + swa.stderr
    nyata = subprocess.run([sys.executable, str(skrip)], capture_output=True, text=True, cwd=REPO)
    assert nyata.returncode == 0 and "0 pelanggaran" in nyata.stdout, nyata.stdout + nyata.stderr


# ═══ Putaran 1 — kontrak lawan kas `ap_advance`, pemisahan pemetaan, satu pembantu penanda per PT ════════════════════
async def test_KB4_1_U10_lawan_kas_ap_advance_wajib_lewat_pembantu(pindah):
    """`_cash_out_contra` sinkron tidak menebak akun uang muka pemasok: tanpa akun → `ValueError` (pemanggil sinkron
    `cash_contra_account` hanya kas manual); jurnal & PERIKSA kas lewat `_lawan_kas_keluar` (PT buku jurnal)."""
    from services import gl_service as gl
    txn = {"ref_type": "ap_advance", "direction": "out", "category": "uang muka supplier", "amount": 1000}
    with pytest.raises(ValueError):
        gl.cash_contra_account(txn)
    with pytest.raises(ValueError):
        gl._cash_out_contra(txn)
    assert gl._cash_out_contra(txn, "1-1410") == "1-1410"
    assert gl._cash_out_contra({**txn, "contra_account_code": "1-1900"}, "1-1410") == "1-1900"   # eksplisit menang
    assert (await gl._lawan_kas_keluar(txn, KSC), await gl._lawan_kas_keluar(txn, KANDA)) == ("1-1400", "1-1410")
    assert gl._cash_out_contra({"ref_type": "cash_advance"}) == "1-1400"   # PD = uang muka karyawan
    assert await gl._lawan_kas_keluar({"ref_type": "cash_advance"}, KANDA) == "1-1400"
    assert gl.cash_contra_account({"ref_type": "manual", "direction": "out", "category": "sewa"}) == "6-2000"


async def test_KB4_1_U11_pemetaan_uang_muka_karyawan_dan_pemasok_tetap_terpisah(klien, db, kepala_admin):
    """Pemetaan Akun tidak bisa menyatukan akun uang muka karyawan dan akun uang muka pemasok (bawaan, pemetaan PT itu /
    lapisan grup, atau riwayatnya) — kalau menyatu, pemisahan akun runtuh dan 1-1400 ikut jadi akun kontrol."""
    from schemas_finance import GLAccountCreate
    from services import gl_mapping_service as glm, gl_service as gl
    pt = await pt_uji("KB4S")
    for kode in ("1-1402", "1-1403", "1-1412"):
        await gl.create_account(GLAccountCreate(code=kode, name=f"Akun KB4S {kode}", type="asset",
                                                parent_code="1-1000"), entity_id=pt)
    await glm.set_mapping("kas_bank.uang_muka_karyawan", pt, "1-1402", "uji KB4 karyawan", AKTOR_UJI)
    await glm.set_mapping("hutang.uang_muka_pemasok", pt, "1-1412", "uji KB4 pemasok", AKTOR_UJI)
    await glm.set_mapping("kas_bank.uang_muka_karyawan", pt, "1-1403", "uji KB4 karyawan pindah", AKTOR_UJI)
    karyawan = ("Uang muka & biaya dibayar dimuka", "kas_bank.uang_muka_karyawan")
    pemasok = ("Uang muka pemasok", "hutang.uang_muka_pemasok")
    n0 = await db.gl_account_mappings.count_documents({})
    h0 = await db.gl_account_mapping_history.count_documents({})
    for key, eid, kode, lain in (("hutang.uang_muka_pemasok", pt, "1-1400", karyawan),     # bawaan karyawan
                                 ("hutang.uang_muka_pemasok", pt, "1-1403", karyawan),     # pemetaan karyawan PT itu
                                 ("hutang.uang_muka_pemasok", pt, "1-1402", karyawan),     # riwayat karyawan PT itu
                                 ("kas_bank.uang_muka_karyawan", pt, "1-1410", pemasok),   # bawaan pemasok
                                 ("kas_bank.uang_muka_karyawan", pt, "1-1412", pemasok),   # pemetaan pemasok PT itu
                                 ("hutang.uang_muka_pemasok", "", "1-1400", karyawan),     # lapisan grup
                                 ("kas_bank.uang_muka_karyawan", "", "1-1410", pemasok)):
        with pytest.raises(ValueError) as e:
            await glm.set_mapping(key, eid, kode, "uji KB4 menyatukan", AKTOR_UJI)
        assert str(e.value) == (
            f"Akun {kode} dipakai (atau pernah dipakai) untuk \"{lain[0]}\" ({lain[1]}). Uang muka karyawan dan uang "
            f"muka pemasok harus di akun berbeda supaya saldonya bisa dicocokkan — pilih akun lain."), (key, kode)
    r = await klien.put("/api/gl/account-mappings/hutang.uang_muka_pemasok", headers=kepala_admin,
                        json={"account_code": "1-1400", "entity_id": KSC, "reason": "uji KB4 menyatukan"})
    assert r.status_code == 400 and "harus di akun berbeda" in r.json()["detail"], r.text
    assert await db.gl_account_mappings.count_documents({}) == n0
    assert await db.gl_account_mapping_history.count_documents({}) == h0
    assert (await glm.account_for("hutang.uang_muka_pemasok", pt), await glm.account_for(
        "kas_bank.uang_muka_karyawan", pt)) == ("1-1412", "1-1403")


async def test_KB4_1_U12_penanda_per_pt_satu_pembantu(db, pindah):
    """Putaran 1 (Important 1) — penanda per PT sekali tulis = SATU pembantu `penanda_per_pt`; `cash_account_mode` dan
    `supplier_advance_mode` hanya meneruskan scope-nya (API publik tidak berubah). Penanda kembar dari balapan dua
    `nyalakan` pertama dibaca sebagai satu: yang paling awal berlaku, dan `nyalakan` berikutnya tidak menulis apa pun."""
    import inspect
    from services import cash_account_mode as kas, penanda_per_pt as pp, supplier_advance_mode as um
    for mod in (kas, um):
        for fn in (mod.aktif_sejak, mod.aktif, mod.nyalakan):
            assert "db." not in inspect.getsource(fn), (mod.__name__, fn.__name__)
    assert (kas.SCOPE, um.SCOPE) == ("__kas_per_rekening__", "__uang_muka_pemasok_per_pt__")
    assert await um.aktif_sejak(KANDA) == await pp.aktif_sejak(um.SCOPE, KANDA) == SIMPAN["sejak_kanda"]
    assert await kas.aktif_sejak(KANDA) == "" and await pp.aktif(kas.SCOPE, KANDA) is False
    sc = "__uji_kb4_penanda__"
    await db.system_settings.insert_many([{"scope": sc, "ent_x": {"sejak": "2026-11-28T10:00:02", "oleh": "B"}},
                                          {"scope": sc, "ent_x": {"sejak": "2026-11-28T10:00:01", "oleh": "A"}}])
    assert await pp.aktif_sejak(sc, "ent_x") == "2026-11-28T10:00:01"
    assert await pp.nyalakan(sc, "ent_x", "C", "uji") == "2026-11-28T10:00:01"
    assert await db.system_settings.count_documents({"scope": sc}) == 2
    with pytest.raises(ValueError) as e:
        await pp.nyalakan(sc, "ent x", "C", "akun uji")
    assert str(e.value) == "Id PT tidak sah untuk penanda akun uji: 'ent x'."
    with pytest.raises(ValueError) as e:
        await kas.nyalakan("ent.bertitik", "Uji")
    assert str(e.value) == "Id PT tidak sah untuk penanda akun per rekening: 'ent.bertitik'."
    pk = await pt_uji("KB4K")
    assert await kas.nyalakan(pk, {"name": "Uji KB4"}) is None   # Kas & Bank 1: tetap tanpa nilai kembali
    assert (await kas.aktif(pk), await um.aktif(pk)) == (True, False)
    assert (await db.system_settings.find_one({"scope": kas.SCOPE}, {"_id": 0}))[pk]["oleh"] == "Uji KB4"


#: Direkam dari kode SEBELUM Tugas 1 (730718e) dengan `KB4_REKAM` — jangan disunting tangan.
BARIS_LAMA: dict = {'c1_bayar': [{'account_code': '2-1100',
               'account_name': 'Hutang Usaha',
               'credit': 0.0,
               'debit': 1600000.0,
               'description': 'KSC/CASH-# · Pembayaran kontrabon CB-KB#-KSC — Pemasok KB# ksc (# faktur, transfer)'},
              {'account_code': '1-1100',
               'account_name': 'Kas Besar / Bank',
               'credit': 1600000.0,
               'debit': 0.0,
               'description': 'KSC/CASH-# · Pembayaran kontrabon CB-KB#-KSC — Pemasok KB# ksc (# faktur, transfer)'}],
 'c1_potongan': [{'account_code': '2-1100',
                  'account_name': 'Hutang Usaha',
                  'credit': 0.0,
                  'debit': 400000.0,
                  'description': 'Potongan kontrabon CB-KB#-KSC · UM-KB#-KSC'},
                 {'account_code': '1-1400',
                  'account_name': 'Uang Muka & Biaya Dibayar Dimuka',
                  'credit': 400000.0,
                  'debit': 0.0,
                  'description': 'Potongan kontrabon CB-KB#-KSC · UM-KB#-KSC'}],
 'k1_jurnal': [{'account_code': '1-1400',
                'account_name': 'Uang Muka & Biaya Dibayar Dimuka',
                'credit': 0.0,
                'debit': 500000.0,
                'description': 'Kasus keuangan KSC/CASE-# · uang muka supplier Pemasok KB# ksc'},
               {'account_code': '2-1100',
                'account_name': 'Hutang Usaha',
                'credit': 500000.0,
                'debit': 0.0,
                'description': 'Kasus keuangan KSC/CASE-# · uang muka supplier Pemasok KB# ksc'}],
 'k1_rencana': [{'amount': 500000.0,
                 'credit_acc': '2-1100',
                 'debit_acc': '1-1400',
                 'entity_id': 'ent_ksc',
                 'suffix': 'ap_adv',
                 'via': 'kasus'}],
 'k2_jurnal': [{'account_code': '1-1100',
                'account_name': 'Kas Besar / Bank',
                'credit': 0.0,
                'debit': 200000.0,
                'description': 'KSC/CASH-# · Pengembalian dana dari Pemasok KB# ksc · KSC/CASE-#'},
               {'account_code': '1-1400',
                'account_name': 'Uang Muka & Biaya Dibayar Dimuka',
                'credit': 200000.0,
                'debit': 0.0,
                'description': 'KSC/CASH-# · Pengembalian dana dari Pemasok KB# ksc · KSC/CASE-#'}],
 'k2_rencana': [{'amount': 200000.0,
                 'credit_acc': '1-1400',
                 'debit_acc': '1-1100',
                 'entity_id': 'ent_ksc',
                 'suffix': '',
                 'via': 'kas'}],
 'pd_cair': [{'account_code': '1-1400',
              'account_name': 'Uang Muka & Biaya Dibayar Dimuka',
              'credit': 0.0,
              'debit': 1000000.0,
              'description': 'KSC/CASH-# · Pencairan PD-KB#-KSC — uji KB#'},
             {'account_code': '1-1110',
              'account_name': 'Kas Kecil',
              'credit': 1000000.0,
              'debit': 0.0,
              'description': 'KSC/CASH-# · Pencairan PD-KB#-KSC — uji KB#'}],
 'pd_kembali': [{'account_code': '1-1110',
                 'account_name': 'Kas Kecil',
                 'credit': 0.0,
                 'debit': 200000.0,
                 'description': 'KSC/CASH-# · Pengembalian sisa uang muka KSC/STL-# — Staf KB#'},
                {'account_code': '1-1400',
                 'account_name': 'Uang Muka & Biaya Dibayar Dimuka',
                 'credit': 200000.0,
                 'debit': 0.0,
                 'description': 'KSC/CASH-# · Pengembalian sisa uang muka KSC/STL-# — Staf KB#'}],
 'pd_lpj': [{'account_code': '6-4600',
             'account_name': 'Beban Transportasi & BBM',
             'credit': 0.0,
             'debit': 800000.0,
             'description': 'Beban transportasi'},
            {'account_code': '1-1400',
             'account_name': 'Uang Muka & Biaya Dibayar Dimuka',
             'credit': 800000.0,
             'debit': 0.0,
             'description': 'Pertanggungjawaban KSC/STL-# · Umum'}],
 'pilihan_selisih_bayar': ['Uang Muka (1-1400) +Rp 300.000 · kas keluar lebih besar.'],
 'potongan_pemetaan_pt': [{'account_code': '2-1100',
                           'account_name': 'Hutang Usaha',
                           'credit': 0.0,
                           'debit': 250000.0,
                           'description': 'Potongan kontrabon KB#M d#'},
                          {'account_code': '1-1401',
                           'account_name': '',
                           'credit': 250000.0,
                           'debit': 0.0,
                           'description': 'Potongan kontrabon KB#M d#',
                           'mapping_key': 'kas_bank.uang_muka_karyawan'}],
 't1_bayar': [{'account_code': '2-1100',
               'account_name': 'Hutang Usaha',
               'credit': 0.0,
               'debit': 1000000.0,
               'description': 'KSC/CASH-# · Pembayaran VB-KB#-T#-KSC — Pemasok KB# ksc (transfer)'},
              {'account_code': '1-1100',
               'account_name': 'Kas Besar / Bank',
               'credit': 1000000.0,
               'debit': 0.0,
               'description': 'KSC/CASH-# · Pembayaran VB-KB#-T#-KSC — Pemasok KB# ksc (transfer)'}],
 't1_efek': {'account': '1-1400', 'advance_amount': 300000.0, 'kind': 'ap_advance'},
 't1_uang_muka': [{'account_code': '1-1400',
                   'account_name': 'Uang Muka & Biaya Dibayar Dimuka',
                   'credit': 0.0,
                   'debit': 300000.0,
                   'description': 'KSC/CASH-# · Kelebihan bayar VB-KB#-T#-KSC — Pemasok KB# ksc menjadi uang muka'},
                  {'account_code': '1-1100',
                   'account_name': 'Kas Besar / Bank',
                   'credit': 300000.0,
                   'debit': 0.0,
                   'description': 'KSC/CASH-# · Kelebihan bayar VB-KB#-T#-KSC — Pemasok KB# ksc menjadi uang muka'}],
 't2_bayar': [{'account_code': '2-1100',
               'account_name': 'Hutang Usaha',
               'credit': 0.0,
               'debit': 500000.0,
               'description': 'KSC/CASH-# · Pembayaran VB-KB#-T#-KSC — Pemasok KB# ksc (transfer)'},
              {'account_code': '1-1100',
               'account_name': 'Kas Besar / Bank',
               'credit': 500000.0,
               'debit': 0.0,
               'description': 'KSC/CASH-# · Pembayaran VB-KB#-T#-KSC — Pemasok KB# ksc (transfer)'}],
 't2_efek': {'account': '1-1400', 'advance_amount': 3000.0, 'kind': 'ap_rounding_advance'},
 't2_uang_muka': [{'account_code': '1-1400',
                   'account_name': 'Uang Muka & Biaya Dibayar Dimuka',
                   'credit': 0.0,
                   'debit': 3000.0,
                   'description': 'KSC/CASH-# · Kelebihan bayar VB-KB#-T#-KSC — Pemasok KB# ksc menjadi uang muka'},
                  {'account_code': '1-1100',
                   'account_name': 'Kas Besar / Bank',
                   'credit': 3000.0,
                   'debit': 0.0,
                   'description': 'KSC/CASH-# · Kelebihan bayar VB-KB#-T#-KSC — Pemasok KB# ksc menjadi uang muka'}]}

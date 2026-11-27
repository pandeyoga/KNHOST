"""KB-1 Tugas 2 — semua jurnal kas lewat SATU pembantu akun kas (`gl_service.akun_kas`), pembalik kas lama, penjaga.

Rancangan: `docs/superpowers/specs/2026-11-27-kas-bank-1-rekening-pindah-dana-design.md` §5.1 ("Satu pembantu akun kas
untuk semua jurnal yang menyentuh kas", "Pembalik jurnal kas lama sesudah PT aktif") dan §7 butir 8.

Persiapan (FIXTURE `pt`): empat PT uji, rekening disisip langsung (saldo awal 0, tanpa jurnal).
  * LA, LB — TIDAK PERNAH dinyalakan: regresi "PT belum aktif → jurnal persis seperti sebelumnya". `BARIS_LAMA` di bawah
    direkam dari kode SEBELUM Tugas 2 (komit 2607943) dengan `KB2_REKAM=<berkas.json>`: kode akun, nama akun, debit,
    kredit, keterangan (angka diganti `#`) dan kunci pemetaan, BERURUTAN.
  * AA (satu rekening bank 1-1100-01 + kas kecil 1-1110-01) dan AB (dua rekening bank 1-1100-01 / 1-1100-02 + kas kecil
    1-1110-01) — sub-akun lewat `cash_account_mode.buat_subakun`, lalu `nyalakan`.
  * V — kas dicatat SEBELUM PT dinyalakan; pindah saldo Tugas 3 belum ada, jadi jurnal pindah saldo disimulasikan
    langsung (`_insert_entry`, Dr sub-akun / Cr akun lama) lalu `nyalakan` (ketetapan pengendali: uji lewat
    `nyalakan` + `buat_subakun`).
"""
from __future__ import annotations

import inspect
import itertools
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from core_utils import now_iso
from services.book_date import tanggal_buku
from pembantu import AKTOR_UJI, pt_uji

pytestmark = pytest.mark.anyio

REPO = Path(__file__).resolve().parents[2]
REKAM = os.environ.get("KB2_REKAM", "")
_rekaman: dict = {}
PT_KODE = {"LA": "KB2LA", "LB": "KB2LB", "AA": "KB2AA", "AB": "KB2AB"}


def _uid(awal: str) -> str:
    return f"{awal}_kb2_{uuid.uuid4().hex[:8]}"


_urut = itertools.count(1)


def _no(awal: str) -> str:
    """Nomor dokumen uji berurutan (masuk keterangan jurnal; angka dinormalkan `_baris`)."""
    return f"{awal}/{next(_urut):03d}"


def _baris(je: dict) -> list:
    """Baris jurnal BERURUTAN: (kode, nama, debit, kredit, keterangan angka→#, kunci pemetaan)."""
    return [[ln["account_code"], ln.get("account_name", ""), ln["debit"], ln["credit"],
             re.sub(r"\d+", "#", ln.get("description", "")), ln.get("mapping_key", "")] for ln in je["lines"]]


def _rencana(lines: list) -> list:
    return [[ln["account_code"], ln["debit"], ln["credit"], re.sub(r"\d+", "#", ln.get("description", ""))]
            for ln in lines]


def _cocok(nama: str, nyata) -> None:
    if REKAM:
        _rekaman[nama] = nyata
        with open(REKAM, "w", encoding="utf-8") as f:
            json.dump(_rekaman, f, ensure_ascii=False, indent=1, sort_keys=True)
        return
    assert nyata == BARIS_LAMA[nama], f"{nama}: {json.dumps(nyata, ensure_ascii=False)}"


def _kas(je: dict) -> set:
    return {(ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]}


async def _jurnal(db, source_type: str, awalan: str = "", source_id: str = "") -> list:
    q = {"source_type": source_type, "status": {"$ne": "void"}}
    if source_id:
        q["source_id"] = source_id
    elif awalan:
        q["source_id"] = {"$regex": "^" + re.escape(awalan)}
    return sorted(await db.journal_entries.find(q, {"_id": 0}).to_list(50), key=lambda j: j["source_id"])


async def _satu(db, source_type: str, source_id: str) -> dict:
    jes = await _jurnal(db, source_type, source_id=source_id)
    assert len(jes) == 1, jes
    return jes[0]


async def _pt_dengan_rekening(db, kode: str, rekening: list) -> tuple:
    eid = await pt_uji(kode)
    ids = {}
    for i, (suf, nama, jenis_akun, jenis_kas) in enumerate(rekening):
        rid = f"rek_kb2_{kode.lower()}_{suf}"
        await db.bank_accounts.insert_one({
            "id": rid, "name": nama, "entity_id": eid, "account_type": jenis_akun, "cash_type": jenis_kas,
            "is_active": True, "opening_balance": 0.0, "bank_name": "", "account_number": "",
            "created_at": f"2026-01-01T00:00:0{i}+00:00"})
        ids[suf] = rid
    return eid, ids


@pytest.fixture(scope="module")
async def pt(db):
    from services import cash_account_mode as mode
    ent, rek = {}, {}
    for k, kode in PT_KODE.items():
        baris = [("bank", f"Bank {k}", "bank", "kas_besar"), ("kk", f"Kas Kecil {k}", "cash", "kas_kecil")]
        if k == "AB":
            baris.insert(1, ("bank2", f"Bank Dua {k}", "bank", "kas_besar"))
        ent[k], ids = await _pt_dengan_rekening(db, kode, baris)
        rek.update({f"{k}_{s}": v for s, v in ids.items()})
    for k in ("AA", "AB"):
        async for acc in db.bank_accounts.find({"entity_id": ent[k]}, {"_id": 0}).sort("created_at", 1):
            await mode.buat_subakun(acc)
        await mode.nyalakan(ent[k], "Uji KB2")
    return {"id": ent, "rek": rek}


# ═══ Pinjaman antar-PT (interco_loan_service) ══════════════════════════════════════════════════════════════════════
async def _pinjaman(db, pemberi: str, peminjam: str) -> list:
    from services import interco_loan_service as icl
    p = await icl.create({"lender_entity_id": pemberi, "borrower_entity_id": peminjam, "principal": 5_000_000,
                          "purpose": "Modal kerja uji KB2"}, AKTOR_UJI)
    await icl.disburse(p["lender"]["id"], AKTOR_UJI)
    await icl.repay(p["lender"]["id"], AKTOR_UJI, 2_000_000)
    jes = (await _jurnal(db, "interco_loan", p["pair_id"]) + await _jurnal(db, "interco_loan_repayment", p["pair_id"]))
    assert len(jes) == 4, jes
    return jes


async def test_KB1_2_U1a_pinjaman_pt_tidak_aktif_sama(db, pt):
    jes = await _pinjaman(db, pt["id"]["LA"], pt["id"]["LB"])
    _cocok("pinjaman", [_baris(j) for j in jes])


async def test_KB1_2_U2a_pinjaman_pt_aktif_ke_subakun(db, pt):
    cair_a, cair_b, angsur_a, angsur_b = await _pinjaman(db, pt["id"]["AA"], pt["id"]["AB"])
    assert _kas(cair_a) == {("1-1250", 5_000_000.0, 0.0), ("1-1100-01", 0.0, 5_000_000.0)}
    assert _kas(cair_b) == {("1-1100-01", 5_000_000.0, 0.0), ("2-1250", 0.0, 5_000_000.0)}
    assert _kas(angsur_a) == {("2-1250", 2_000_000.0, 0.0), ("1-1100-01", 0.0, 2_000_000.0)}   # buku peminjam
    assert _kas(angsur_b) == {("1-1100-01", 2_000_000.0, 0.0), ("1-1250", 0.0, 2_000_000.0)}   # buku pemberi
    assert {ln["account_name"] for ln in cair_a["lines"] if ln["account_code"] == "1-1100-01"} == {"Bank AA"}
    assert {ln["account_name"] for ln in cair_b["lines"] if ln["account_code"] == "1-1100-01"} == {"Bank AB"}


# ═══ Beban antar-PT — pelunasan tagihan insentif (interco_charge_service) ════════════════════════════════════════
async def _tagihan(db, penagih: str, tertagih: str) -> list:
    from services import interco_charge_service as icc
    cid = _uid("icc")
    await db.interco_charges.insert_one({
        "id": cid, "number": _no("ICC-KB2"), "kind": "incentive", "from_entity_id": penagih,
        "from_entity_name": "Penagih", "to_entity_id": tertagih, "to_entity_name": "Tertagih", "amount": 900_000.0,
        "outstanding": 900_000.0, "status": "open", "settle_status": "none", "settlements": [], "journals": [],
        "history": [], "source": {"run_id": _uid("run"), "run_number": "PAY-KB2"}, "created_at": now_iso()})
    await icc.settle(cid, {"amount": 900_000}, AKTOR_UJI)
    jes = await _jurnal(db, icc.SETTLE_SOURCE, cid)
    assert len(jes) == 2, jes
    return jes


async def test_KB1_2_U1b_beban_antar_pt_tidak_aktif_sama(db, pt):
    _cocok("beban_antar_pt", [_baris(j) for j in await _tagihan(db, pt["id"]["LA"], pt["id"]["LB"])])


async def test_KB1_2_U2b_beban_antar_pt_aktif_ke_subakun(db, pt):
    bayar, terima = await _tagihan(db, pt["id"]["AA"], pt["id"]["AB"])   # sisi a = PT tertagih (pembayar)
    assert _kas(bayar) == {("2-1250", 900_000.0, 0.0), ("1-1100-01", 0.0, 900_000.0)} and bayar["entity_id"] == \
        pt["id"]["AB"]
    assert _kas(terima) == {("1-1100-01", 900_000.0, 0.0), ("1-1250", 0.0, 900_000.0)}


# ═══ Pindah aset antar-PT — pelunasan (fixed_asset_transfer_service) ═════════════════════════════════════════════
async def _pindah_aset(db, asal: str, tujuan: str) -> list:
    from services import fixed_asset_transfer_service as fat
    aid = _uid("fa")
    await db.fin_fixed_assets.insert_one({
        "id": aid, "number": _no("FA-KB2"), "name": "Mesin uji KB2", "entity_id": asal, "status": "transferred",
        "acquisition_cost": 10_000_000.0, "transfer": {"from_entity_id": asal, "to_entity_id": tujuan,
                                                       "from_entity_name": "Asal", "to_entity_name": "Tujuan",
                                                       "price": 6_000_000.0, "settled": False,
                                                       "settle_status": "none"},
        "created_at": now_iso()})
    await fat.settle_transfer(aid, AKTOR_UJI)
    jes = await _jurnal(db, fat.SETTLE_SOURCE, aid)
    assert len(jes) == 2, jes
    return jes


async def test_KB1_2_U1c_pindah_aset_tidak_aktif_sama(db, pt):
    _cocok("pindah_aset", [_baris(j) for j in await _pindah_aset(db, pt["id"]["LA"], pt["id"]["LB"])])


async def test_KB1_2_U2c_pindah_aset_aktif_ke_subakun(db, pt):
    bayar, terima = await _pindah_aset(db, pt["id"]["AA"], pt["id"]["AB"])   # sisi a = PT penerima aset (pembayar)
    assert _kas(bayar) == {("2-1250", 6_000_000.0, 0.0), ("1-1100-01", 0.0, 6_000_000.0)}
    assert _kas(terima) == {("1-1100-01", 6_000_000.0, 0.0), ("1-1250", 0.0, 6_000_000.0)}


# ═══ Pelunasan / pengembalian dana antar-PT (interco_service._settlement_sides) ══════════════════════════════════
async def _rencana_pelunasan(pt, a: str, b: str, rek_b: str) -> dict:
    from services import interco_service as ics
    out = {}
    for jenis in ("transfer", "refund"):
        doc = {"id": _uid("ics"), "number": "ICS-KB2", "payer_entity_id": pt["id"][a], "payer_entity_name": a,
               "payee_entity_id": pt["id"][b], "payee_entity_name": b, "method": "transfer",
               "payer_account_id": pt["rek"][f"{a}_bank"], "payee_account_id": pt["rek"][rek_b],
               "total_applied": 750_000.0, **({"kind": "refund"} if jenis == "refund" else {})}
        sisi = ics._settlement_sides(doc)
        sisi = await sisi if inspect.isawaitable(sisi) else sisi
        out[jenis] = [[s.key, s.entity_id == pt["id"][a], _rencana(s.lines)] for s in sisi]
    return out


async def test_KB1_2_U1d_pelunasan_antar_pt_tidak_aktif_sama(pt):
    _cocok("pelunasan_antar_pt", await _rencana_pelunasan(pt, "LA", "LB", "LB_bank"))


async def test_KB1_2_U2d_pelunasan_antar_pt_aktif_rekening_dokumen(pt):
    r = await _rencana_pelunasan(pt, "AA", "AB", "AB_bank2")   # penerima memakai rekening KEDUA (1-1100-02)
    bayar, terima = r["transfer"]
    assert {tuple(x[:3]) for x in bayar[2]} == {("2-1250", 750_000.0, 0.0), ("1-1100-01", 0.0, 750_000.0)}
    assert {tuple(x[:3]) for x in terima[2]} == {("1-1100-02", 750_000.0, 0.0), ("1-1250", 0.0, 750_000.0)}
    kembali_bayar, kembali_terima = r["refund"]
    assert {tuple(x[:3]) for x in kembali_bayar[2]} == {("1-1250", 750_000.0, 0.0), ("1-1100-01", 0.0, 750_000.0)}
    assert {tuple(x[:3]) for x in kembali_terima[2]} == {("1-1100-02", 750_000.0, 0.0), ("2-1250", 0.0, 750_000.0)}


# ═══ Gaji (hr_payroll_pay._kas_bayar) — jalur baru dan jalur lama (`payroll_pay` sudah terbit) ════════════════════
async def _bayar_gaji(db, eid: str, rekening: str, kredit_lama: str = "") -> dict:
    from services import gl_service as gl, hr_payroll_pay as hp
    run = {"id": _uid("run"), "number": "PAY-KB2", "entity_id": eid, "period": "2026-11", "status": "posted",
           "totals": {"net": 1_200_000.0}}
    if kredit_lama:   # jurnal bayar jalur lama (sebelum PY-T4) sudah terbit, kasnya belum
        await gl._insert_entry(lines=[{"account_code": "2-1600", "debit": 1_200_000.0, "credit": 0.0},
                                      {"account_code": kredit_lama, "debit": 0.0, "credit": 1_200_000.0}],
                               description="Bayar gaji lama", date=now_iso(), source_type="payroll_pay",
                               source_id=run["id"], entity_id=eid, created_by="uji")
    return await hp._kas_bayar(run, {"id": rekening}, tanggal_buku(), "Uji")


async def test_KB1_2_U1e_gaji_pt_tidak_aktif_sama(db, pt):
    from services import cash_ledger
    baru = await _bayar_gaji(db, pt["id"]["LA"], pt["rek"]["LA_kk"])
    lama = await _bayar_gaji(db, pt["id"]["LA"], pt["rek"]["LA_kk"], kredit_lama="1-1110")
    with pytest.raises(cash_ledger.CashRejected):   # rekening jenis lain dari akun kas jurnal lama → ditolak (tetap)
        await _bayar_gaji(db, pt["id"]["LA"], pt["rek"]["LA_kk"], kredit_lama="1-1100")
    _cocok("gaji", {"baru": _baris(await _satu(db, "cash_transaction", baru["id"])),
                    "lama": [lama["cash_type"], lama.get("gl_posted"), lama["account_code"]]})


async def test_KB1_2_U2e_gaji_pt_aktif_ke_subakun_dan_jenis_dari_rekening(db, pt):
    from services import cash_ledger
    baru = await _bayar_gaji(db, pt["id"]["AA"], pt["rek"]["AA_kk"])
    assert _kas(await _satu(db, "cash_transaction", baru["id"])) == {("2-1600", 1_200_000.0, 0.0),
                                                                    ("1-1110-01", 0.0, 1_200_000.0)}
    lama = await _bayar_gaji(db, pt["id"]["AA"], pt["rek"]["AA_kk"], kredit_lama="1-1110")
    assert (lama["cash_type"], lama.get("gl_posted")) == ("kas_kecil", True)
    # R2 — jenis kas jurnal lama ber-akun rekening dibaca dari REKENING pemilik akun (kas kecil), bukan dari kodenya
    # (`cash_type_for("1-1110-01")` = kas besar → kas ditolak).
    r2 = await _bayar_gaji(db, pt["id"]["AA"], pt["rek"]["AA_kk"], kredit_lama="1-1110-01")
    assert (r2["cash_type"], r2.get("gl_posted")) == ("kas_kecil", True)
    assert await cash_ledger.jenis_kas_akun(pt["id"]["AA"], "1-1110-01") == "kas_kecil"
    assert await cash_ledger.jenis_kas_akun(pt["id"]["AA"], "1-1110") == "kas_kecil"
    assert await cash_ledger.jenis_kas_akun(pt["id"]["AA"], "1-1100-01") == "kas_besar"


# ═══ Refund retur jual (return_service.settle_return) dan retur per roll (return_roll_settlement_service) ══════════
@pytest.fixture(scope="module")
async def dunia(db):
    pid = _uid("prd")
    await db.products.insert_one({"id": pid, "name": "Kain Uji KB2", "sku": f"SKU-{pid}", "base_unit": "meter",
                                  "harga_pokok": 6_000, "price": 10_000, "is_active": True})
    return {"pid": pid}


async def _pesanan_lunas(db, dunia, eid: str) -> dict:
    """Pesanan 100 m × 10.000 terkirim (jurnal pendapatan per surat jalan) dan sudah lunas dibayar."""
    from services import config_service, gl_service
    wid, cus = _uid("wh"), _uid("cus")
    await db.warehouses.insert_one({"id": wid, "name": "Gudang KB2", "entity_id": eid, "is_active": True,
                                    "created_at": now_iso()})
    await db.customers.insert_one({"id": cus, "name": "Toko KB2", "entity_id": eid, "status": "active",
                                   "deposit_balance": 0.0})
    pr = await config_service.compute_order_pricing(
        [{"product_id": dunia["pid"], "product_name": "Kain Uji KB2", "sku": "SKU-KB2", "quantity": 100,
          "base_quantity": 100, "unit": "meter", "price": 10_000}], entity_id=eid, tax_override="non_ppn")
    so = {"id": _uid("so"), "number": _no("SO/KB2"), "entity_id": eid, "customer_id": cus,
          "customer_name": "Toko KB2", "status": "confirmed", "payment_term_code": "NET30", "payment_method": "kredit",
          "tax_override": "non_ppn", "allocations": [{"warehouse_id": wid, "product_id": dunia["pid"], "qty": 100}],
          "payments": [], "paid_total": 0.0, "payment_status": "unpaid", "created_at": now_iso(),
          **{k: pr[k] for k in ("items", "total_amount", "net_subtotal", "dpp", "ppn_rate", "ppn_mode", "ppn_amount",
                                "grand_total", "order_discount_percent", "tax_snapshot")}}
    await db.sales_orders.insert_one(dict(so))
    rid = _uid("r")
    shp = {"id": _uid("shp"), "shipment_no": _no("SJ/KB2"), "entity_id": eid,
           "order_id": so["id"], "order_number": so["number"], "product_id": dunia["pid"], "warehouse_id": wid,
           "qty": 100, "unit": "meter", "rolls": [{"roll_id": rid, "length": 100, "unit_cost": 6_000,
                                                   "extended_cost": 600_000}],
           "status": "dispatched", "created_at": now_iso(), "gl_status": "pending"}
    await db.shipments.insert_one(dict(shp))
    await db.sales_orders.update_one({"id": so["id"]}, {"$set": {
        "status": "shipped", "paid_total": 1_000_000.0, "payment_status": "paid",
        "payments": [{"amount": 1_000_000.0, "receipt_id": _uid("rc"), "date": now_iso()}]}})
    await gl_service.post_order_revenue_and_cogs(so["id"])
    return {**so, "wid": wid, "cus": cus, "roll_id": rid}


async def _refund_retur(db, dunia, eid: str, rekening: str, kode_pilihan: str) -> tuple:
    from services import return_service
    so = await _pesanan_lunas(db, dunia, eid)
    sr = _uid("sr")
    await db.sales_returns.insert_one({
        "id": sr, "number": _no("RJ/KB2"), "entity_id": eid, "status": "inspected", "order_id": so["id"],
        "order_number": so["number"], "customer_id": so["cus"], "customer_name": "Toko KB2",
        "attachments": [{"id": "att_kb2", "name": "foto.jpg"}], "created_at": now_iso(),
        "items": [{"product_id": dunia["pid"], "product_name": "Kain Uji KB2", "quantity_returned": 40,
                   "unit": "meter", "condition": "ok", "reason": "salah warna", "inspection": {"grade": "A"}}]})
    ret = await return_service.settle_return(sr, "Uji", "refund", refund_account_code=kode_pilihan,
                                             refund_account_id=rekening)
    assert ret.get("status") == "refund_settled", ret
    je = await _satu(db, "sales_return", sr)
    kas = await db.cash_transactions.find_one({"ref_type": "sales_return", "ref_id": sr}, {"_id": 0})
    assert kas, "kas refund tidak tercatat"
    return je, kas


async def test_KB1_2_U1f_refund_retur_pt_tidak_aktif_sama(db, dunia, pt):
    je, kas = await _refund_retur(db, dunia, pt["id"]["LA"], pt["rek"]["LA_bank"], "1-1100")
    je_k, kas_k = await _refund_retur(db, dunia, pt["id"]["LA"], pt["rek"]["LA_kk"], "1-1110")
    _cocok("refund_retur", {"bank": _baris(je), "kas_bank": [kas["account_code"], kas["cash_type"]],
                            "kecil": _baris(je_k), "kas_kecil": [kas_k["account_code"], kas_k["cash_type"]]})


async def test_KB1_2_U2f_refund_retur_pt_aktif_ke_subakun(db, dunia, pt):
    je, kas = await _refund_retur(db, dunia, pt["id"]["AA"], pt["rek"]["AA_bank"], "1-1100")
    assert ("1-1100-01", 0.0, 400_000.0) in _kas(je) and not {"1-1100", "1-1110"} & {c for c, _, _ in _kas(je)}
    assert (kas["account_id"], kas["account_code"], kas["cash_type"]) == (pt["rek"]["AA_bank"], "1-1100-01",
                                                                          "kas_besar")
    assert kas["journal_entry_id"] == je["id"]
    je_k, kas_k = await _refund_retur(db, dunia, pt["id"]["AA"], pt["rek"]["AA_kk"], "1-1110")
    assert ("1-1110-01", 0.0, 400_000.0) in _kas(je_k)
    assert (kas_k["account_code"], kas_k["cash_type"]) == ("1-1110-01", "kas_kecil")
    cn = await db.credit_notes.find_one({"return_id": je_k["source_id"]}, {"_id": 0})
    assert cn["refund_account_code"] == "1-1110"   # kode pemilih (jenis kas) tetap tersimpan apa adanya


async def _retur_per_roll(db, dunia, eid: str, rekening: str) -> dict:
    from services import return_roll_settlement_service as rrs
    so = await _pesanan_lunas(db, dunia, eid)
    rid, sr = so["roll_id"], _uid("sr")
    await db.sales_returns.insert_one({
        "id": sr, "number": _no("RJ/KB2"), "entity_id": eid, "status": "inspected", "order_id": so["id"],
        "order_number": so["number"], "customer_id": so["cus"], "customer_name": "Toko KB2", "created_at": now_iso(),
        "roll_locations": {rid: {"stage": "received", "warehouse_id": so["wid"]}},
        "items": [{"product_id": dunia["pid"], "product_name": "Kain Uji KB2", "quantity_returned": 30,
                   "unit": "meter", "condition": "ok", "reason": "salah warna", "roll_ids": [rid],
                   "roll_qtys": {rid: 30}, "inspection": {"grade": "A", "roll_results": {
                       rid: {"grade": "A", "actual_qty": 30, "condition": "ok"}}}}]})
    ret = await db.sales_returns.find_one({"id": sr}, {"_id": 0})
    plan = await rrs.plan_event(ret, [{"roll_id": rid, "outcome": "refund"}], "", "1-1100")
    assert plan["cash_total"] == 300_000, plan
    plan["refund_account_id"] = rekening   # `execute` mengisi rekening penerima sebelum klaim (PK-20)
    ev = {"id": _uid("rst"), "seq": 1, "status": "posting", "plan": plan, "restocked": []}
    await db.sales_returns.update_one({"id": sr}, {"$push": {"settlements": ev}})
    ret = await db.sales_returns.find_one({"id": sr}, {"_id": 0})
    await rrs.issue_settlement_note(ret, ev["id"], plan, AKTOR_UJI)
    return await _satu(db, "sales_return", f"{sr}:{ev['id']}")


async def test_KB1_2_U1g_retur_per_roll_tidak_aktif_sama(db, dunia, pt):
    _cocok("retur_per_roll", _baris(await _retur_per_roll(db, dunia, pt["id"]["LA"], pt["rek"]["LA_bank"])))


async def test_KB1_2_U2g_retur_per_roll_aktif_ke_subakun(db, dunia, pt):
    je = await _retur_per_roll(db, dunia, pt["id"]["AA"], pt["rek"]["AA_bank"])
    assert ("1-1100-01", 0.0, 300_000.0) in _kas(je) and "1-1100" not in {c for c, _, _ in _kas(je)}


# ═══ Refund retur beli (purchase_return_service._finalize_supplier_return_financials) ═══════════════════════════════
async def _retur_beli(db, eid: str, rekening: str, kode_pilihan: str) -> tuple:
    from services import purchase_return_service as prs
    rid = _uid("pret")
    await db.purchase_returns.insert_one({
        "id": rid, "number": _no("RB/KB2"), "entity_id": eid, "warehouse_id": _uid("wh"), "status": "approved",
        "stock_adjusted": True, "grand_total": 550_000.0, "total_amount": 550_000.0, "ppn_amount": 0.0,
        "supplier_name": "Pemasok KB2", "items": [], "created_at": now_iso()})
    await prs._finalize_supplier_return_financials(await db.purchase_returns.find_one({"id": rid}, {"_id": 0}),
                                                   "Uji", "uji KB2", "refund", kode_pilihan, rekening)
    je = await _satu(db, "purchase_return", rid)
    kas = await db.cash_transactions.find_one({"ref_type": "purchase_return", "ref_id": rid}, {"_id": 0})
    assert kas, "kas refund retur beli tidak tercatat"
    return je, kas, await db.purchase_returns.find_one({"id": rid}, {"_id": 0})


async def test_KB1_2_U1h_retur_beli_tidak_aktif_sama(db, pt):
    je, kas, ret = await _retur_beli(db, pt["id"]["LA"], pt["rek"]["LA_kk"], "1-1110")
    _cocok("retur_beli", {"jurnal": _baris(je), "kas": [kas["account_code"], kas["cash_type"], kas["direction"]],
                          "kode": ret["refund_account_code"]})


async def test_KB1_2_U2h_retur_beli_aktif_ke_subakun(db, pt):
    je, kas, ret = await _retur_beli(db, pt["id"]["AA"], pt["rek"]["AA_kk"], "1-1110")
    assert ("1-1110-01", 550_000.0, 0.0) in _kas(je)
    assert (kas["account_code"], kas["cash_type"], kas["direction"]) == ("1-1110-01", "kas_kecil", "in")
    assert ret["refund_account_code"] == "1-1110"


# ═══ Penjualan tunai tanpa surat jalan (gl_service.post_sales_order) ═══════════════════════════════════════════════
async def _jual_tunai(db, eid: str) -> tuple:
    from services import gl_service as gl
    so = {"id": _uid("so"), "number": _no("SO/KB2T"), "entity_id": eid, "status": "done",
          "payment_term_code": "tunai", "grand_total": 220_000.0, "ppn_amount": 20_000.0, "items": [],
          "payments": [], "created_at": now_iso()}
    await db.sales_orders.insert_one(dict(so))
    from services.ar_aging_service import recognized_by_order
    je = await gl.post_sales_order(so)
    assert je, "jurnal penjualan tunai tidak terbit"
    ar = (await gl.order_revenue_recognized(so["id"]))["ar"]
    assert (await recognized_by_order([so["id"]])).get(so["id"]) == ar   # dua pembaca piutang lahir sama
    return je, ar


async def test_KB1_2_U1i_penjualan_tunai_tidak_aktif_sama(db, pt):
    je, ar = await _jual_tunai(db, pt["id"]["LA"])
    assert ar == 220_000.0 and not (je.get("ref") or {})
    _cocok("penjualan_tunai", _baris(je))


async def test_KB1_2_U2i_penjualan_tunai_aktif_akun_lama_belum_tertaut(db, pt):
    """Ketetapan pengendali R6 — tanpa dokumen kas → akun lama + tanda belum tertaut, juga bila PT punya SATU rekening
    kas besar (AA; dulu diusulkan ke sub-akunnya: saldo sub-akun akan ≠ buku kas rekening)."""
    for k in ("AA", "AB"):
        je, ar = await _jual_tunai(db, pt["id"][k])
        assert ("1-1100", 220_000.0, 0.0) in _kas(je) and ar == 220_000.0, (k, je["lines"])
        assert not {"1-1100-01", "1-1100-02"} & {c for c, _, _ in _kas(je)}
        assert (je.get("ref") or {}).get("kas_belum_tertaut") is True, k


# ═══ Pelepasan aset (hasil jual tanpa rekening) — akun lama; di PT aktif ditandai belum tertaut ════════════════════
async def _lepas_aset(eid: str) -> dict:
    from services import gl_service as gl
    return await gl.post_asset_disposal(asset_id=_uid("fa"), entity_id=eid, acquisition_cost=1_000_000,
                                        accumulated=400_000, proceeds=700_000, asset_acc="1-2100", label="FA-KB2")


async def test_KB1_2_U1j_pelepasan_aset_tidak_aktif_sama(pt):
    je = await _lepas_aset(pt["id"]["LA"])
    assert not (je.get("ref") or {})
    _cocok("pelepasan_aset", _baris(je))


async def test_KB1_2_U2j_pelepasan_aset_aktif_akun_lama_belum_tertaut(pt):
    je = await _lepas_aset(pt["id"]["AA"])
    assert ("1-1100", 700_000.0, 0.0) in _kas(je) and (je.get("ref") or {}).get("kas_belum_tertaut") is True


async def _perolehan_aset(db, eid: str, rekening: str, akun_tersimpan: str, jenis: str) -> dict:
    """Aset sumber dana kas yang akun kasnya tersimpan saat aset disimpan (`_resolve_funding`); jurnal terbit
    kemudian."""
    from services import fixed_asset_service as fas
    aid = _uid("fa")
    aset = {"id": aid, "number": _no("FA-KB2P"), "name": "Mesin KB2", "entity_id": eid, "status": "active",
            "acquisition_cost": 2_500_000.0, "acquisition_date": tanggal_buku(), "gl_account_asset": "1-2100",
            "funding_source": "kas", "funding_account": akun_tersimpan, "account_id": rekening,
            "funding_cash_type": jenis, "acquisition_cash_txn_id": "", "created_at": now_iso()}
    await db.fin_fixed_assets.insert_one(dict(aset))
    await fas.post_acquisition_gl(aset)
    return await _satu(db, "fixed_asset_acquisition", aid)


async def test_KB1_2_U1k_perolehan_aset_tidak_aktif_sama(db, pt):
    je = await _perolehan_aset(db, pt["id"]["LA"], pt["rek"]["LA_kk"], "1-1110", "kas_kecil")
    lama = await _perolehan_aset(db, pt["id"]["LA"], "", "", "")   # aset lama tanpa sumber dana tersimpan
    _cocok("perolehan_aset", {"kas_kecil": _baris(je), "tanpa_sumber": _baris(lama)})


async def test_KB1_2_U2k_perolehan_aset_aktif_ke_subakun(db, pt):
    # Akun tersimpan 1-1110 (aset disimpan sebelum PT aktif), jurnal terbit sesudahnya → sub-akun rekening aset
    je = await _perolehan_aset(db, pt["id"]["AA"], pt["rek"]["AA_kk"], "1-1110", "kas_kecil")
    assert _kas(je) == {("1-2100", 2_500_000.0, 0.0), ("1-1110-01", 0.0, 2_500_000.0)}


# ═══ Batal kas yang dicatat SEBELUM PT aktif, sesudah aktif → pembalik ke sub-akun ═════════════════════════════════
async def _saldo(kode: str, eid: str) -> float:
    from pembantu import saldo_akun
    return round(await saldo_akun(kode, eid), 2)


async def test_KB1_2_U3_batal_kas_lama_sesudah_aktif_ke_subakun(db, pt):
    from services import bank_service, cash_account_mode as mode, cash_ledger, gl_mapping_service as glm
    from services import gl_service as gl
    from schemas_finance import GLAccountCreate
    V, rek = await _pt_dengan_rekening(db, "KB2V", [("bank", "BCA V", "bank", "kas_besar"),
                                                     ("bca2", "Mandiri V", "bank", "kas_besar")])
    # Rekening kedua memakai pemetaan PT kas besar → 1-1101 (jurnal lama berakun pemetaan ikut terbaca)
    await gl.create_account(GLAccountCreate(code="1-1101", name="Bank Umum V", type="asset", parent_code="1-1000"),
                            entity_id=V)
    async def kas_masuk(ref, rekening, nominal):
        return await cash_ledger.create_cash(entity_id=V, direction="in", amount=nominal, ref_type="manual",
                                             ref_id=ref, account_id=rekening, category="modal",
                                             description=f"Modal {ref}", actor="Uji")
    k1 = await kas_masuk("kb2_v1", rek["bank"], 500_000)
    k2 = await kas_masuk("kb2_v2", rek["bank"], 300_000)
    await glm.set_mapping("kas_bank.kas_besar", V, "1-1101", "uji KB2 pemetaan PT V", AKTOR_UJI)
    try:
        k3 = await kas_masuk("kb2_v3", rek["bca2"], 200_000)
    finally:
        await glm.reset_mapping("kas_bank.kas_besar", V, "pulihkan uji KB2", AKTOR_UJI)
    assert ("1-1101", 200_000.0, 0.0) in _kas(await _satu(db, "cash_transaction", k3["id"]))
    # "Pindah saldo" Tugas 3 (disimulasikan): sub-akun dibuat, saldo per rekening per akun asal dipindah, PT menyala.
    for r in rek.values():
        await mode.buat_subakun(await db.bank_accounts.find_one({"id": r}, {"_id": 0}))
    await gl._insert_entry(lines=[{"account_code": "1-1100-01", "debit": 800_000.0, "credit": 0.0},
                                  {"account_code": "1-1100", "debit": 0.0, "credit": 800_000.0},
                                  {"account_code": "1-1100-02", "debit": 200_000.0, "credit": 0.0},
                                  {"account_code": "1-1101", "debit": 0.0, "credit": 200_000.0}],
                           description="Pindah saldo (simulasi uji)", date=now_iso(), source_type="pindah_saldo_kas",
                           source_id=V, entity_id=V, created_by="uji")
    await mode.nyalakan(V, "Uji")
    # Batal kas lama lewat pintu batal kas (API) → pembalik ke sub-akun rekening itu
    for kas, sub, nominal in ((k1, "1-1100-01", 500_000.0), (k3, "1-1100-02", 200_000.0)):
        await gl.post_cash_void(kas["id"], label="uji batal KB2", created_by="Uji")
        await db.cash_transactions.update_one({"id": kas["id"]}, {"$set": {"status": "void"}})
        balik = await _satu(db, "cash_transaction_void", kas["id"])
        assert (sub, 0.0, nominal) in _kas(balik), balik["lines"]
        assert not {"1-1100", "1-1101"} & {c for c, _, _ in _kas(balik)}
    for r, sub in ((rek["bank"], "1-1100-01"), (rek["bca2"], "1-1100-02")):
        assert await _saldo(sub, V) == (await bank_service.account_ledger(r))["balance"]
    assert await _saldo("1-1100", V) == 0 and await _saldo("1-1101", V) == 0
    assert (await _saldo("1-1100-01", V), await _saldo("1-1100-02", V)) == (300_000.0, 0.0)
    # Pembalikan MANUAL jurnal kas lama (kas k2 masih tercatat) ditolak: saldonya sudah di sub-akun
    je2 = await _satu(db, "cash_transaction", k2["id"])
    with pytest.raises(ValueError) as e:
        await gl.reverse_entry(je2["id"], tanggal_buku(), "uji balik manual KB2", AKTOR_UJI)
    assert str(e.value) == (f"Jurnal {je2['number']} mencatat kas rekening BCA V yang saldonya sudah dipindah ke akun "
                            f"1-1100-01; balik lewat pembatalan dokumen kasnya, bukan pembalikan manual."), str(e.value)
    assert not (await db.journal_entries.find_one({"id": je2["id"]})).get("reversed_by_entry_id")


async def test_KB1_2_U3b_batal_kas_pt_tidak_aktif_sama(db, pt):
    from services import cash_ledger, gl_service as gl
    kas = await cash_ledger.create_cash(entity_id=pt["id"]["LA"], direction="out", amount=125_000, ref_type="manual",
                                        ref_id="kb2_u3b", account_id=pt["rek"]["LA_kk"], category="sewa",
                                        description="Sewa KB2", actor="Uji")
    await gl.post_cash_void(kas["id"], label="uji batal KB2", created_by="Uji")
    _cocok("batal_kas", _baris(await _satu(db, "cash_transaction_void", kas["id"])))


# ═══ Pemilih akun bayar ongkir retur — akun rekening tidak ditawarkan ═════════════════════════════════════════════
async def test_KB1_2_U4_pemilih_ongkir_tanpa_akun_rekening(db, pt):
    from services import return_logistics_service as rl
    kode = {a["code"] for a in await rl.pay_accounts(pt["id"]["AA"])}
    assert {"1-1100", "1-1110"} <= kode and not {"1-1100-01", "1-1110-01"} & kode
    ret = {"id": _uid("sr"), "number": "RJ/KB2/ONG", "entity_id": pt["id"]["AA"], "customer_name": "Toko KB2"}
    with pytest.raises(ValueError) as e:
        await rl.save(ret, [{"type": "customer_return", "mode": "third_party", "bearer": "company",
                             "amount": 50_000, "pay_account_code": "1-1100-01"}], AKTOR_UJI, True)
    assert "1-1100-01" in str(e.value)
    assert not await db.journal_entries.find_one({"source_type": rl.SOURCE, "ref.return_id": ret["id"]})


async def _ongkir(db, eid: str, kode_bayar: str) -> dict:
    from services import return_logistics_service as rl
    ret = {"id": _uid("sr"), "number": _no("RJ/KB2/ONG"), "entity_id": eid, "customer_name": "Toko KB2"}
    await db.sales_returns.insert_one(dict(ret))
    biaya = {"type": "customer_return", "mode": "third_party", "bearer": "company", "amount": 50_000}
    if kode_bayar:
        biaya["pay_account_code"] = kode_bayar
    await rl.save(ret, [biaya], AKTOR_UJI, True)
    jes = await db.journal_entries.find({"source_type": rl.SOURCE, "ref.return_id": ret["id"]}, {"_id": 0}).to_list(5)
    assert len(jes) == 1, jes
    return jes[0]


async def test_KB1_2_U1l_ongkir_retur_tidak_aktif_sama(db, pt):
    out = {}
    for nama, kode in (("kas_kecil", "1-1110"), ("bawaan_pemetaan", ""), ("hutang", "2-1100")):
        je = await _ongkir(db, pt["id"]["LA"], kode)
        out[nama] = {"baris": _baris(je), "ref": sorted(je.get("ref") or {})}
    _cocok("ongkir_retur", out)


async def test_KB1_2_U2l_ongkir_retur_aktif_akun_kas_lama_belum_tertaut(db, pt):
    """Ketetapan pengendali R7 — ongkir dibayar dari akun kas lama (pilihan, atau bawaan `retur.ongkir_pembayaran`
    1-1110) di PT aktif → `ref.kas_belum_tertaut`; dibayar lewat hutang → tanpa tanda."""
    for kode, tanda in (("1-1110", True), ("1-1100", True), ("", True), ("2-1100", False)):
        je = await _ongkir(db, pt["id"]["AA"], kode)
        assert bool((je.get("ref") or {}).get("kas_belum_tertaut")) is tanda, (kode, je.get("ref"), je["lines"])
        assert {"return_id", "return_number", "cost_type"} <= set(je["ref"])


# ═══ Penjaga akun rekening: PATCH bukan-postable (M2), nama baris (M4), Pemetaan Akun ═════════════════════════════
async def test_KB1_2_U5_akun_rekening_tidak_bisa_jadi_akun_induk(klien, db, sesi, pt):
    h = await sesi("admin@kainnusantara.id", entitas=pt["id"]["AA"])
    r = await klien.patch("/api/gl/accounts/1-1110-01", headers=h, params={"entity_id": pt["id"]["AA"]},
                          json={"is_postable": False})
    assert (r.status_code, r.json().get("detail")) == (
        409, "Akun 1-1110-01 adalah akun buku besar rekening Kas Kecil AA dan tidak bisa diubah menjadi akun induk."), \
        r.text
    a = await db.gl_accounts.find_one({"code": "1-1110-01", "entity_id": pt["id"]["AA"]}, {"_id": 0})
    assert a["is_postable"] is True


async def test_KB1_2_U6_nama_subakun_di_baris_walau_pt_belum_aktif(db, pt):
    from services import cash_account_mode as mode, gl_service as gl
    LB = pt["id"]["LB"]
    await mode.buat_subakun(await db.bank_accounts.find_one({"id": pt["rek"]["LB_bank"]}, {"_id": 0}))
    assert await mode.aktif(LB) is False
    je = await gl._insert_entry(lines=[{"account_code": "1-1100-01", "debit": 1.0, "credit": 0.0},
                                       {"account_code": "1-1100", "debit": 0.0, "credit": 1.0}],
                                description="Pindah saldo (sebelum menyala)", date=now_iso(),
                                source_type="pindah_saldo_kas", source_id=LB, entity_id=LB, created_by="uji")
    assert {ln["account_code"]: ln["account_name"] for ln in je["lines"]}["1-1100-01"] == "Bank LB"


async def test_KB1_2_U7_pemetaan_akun_ke_akun_rekening_ditolak(db, pt):
    from services import gl_mapping_service as glm
    with pytest.raises(ValueError) as e:
        await glm.set_mapping("retur.ongkir_pembayaran", pt["id"]["AA"], "1-1110-01", "uji KB2 pemetaan", AKTOR_UJI)
    assert str(e.value) == ("Akun 1-1110-01 adalah akun rekening Kas Kecil AA; akun rekening hanya diisi lewat kas "
                            "atau Pindah Dana, bukan lewat Pemetaan Akun."), str(e.value)
    assert not await db.gl_account_mappings.find_one({"key": "retur.ongkir_pembayaran", "entity_id": pt["id"]["AA"]})


# ═══ Penjaga statis INV-CASH-02 ═════════════════════════════════════════════════════════════════════════════════════
def test_KB1_2_U8_penjaga_statis_swauji_dan_repo_hijau():
    skrip = REPO / "scripts/guardrails/verify_akun_kas_satu_pintu.py"
    assert skrip.exists(), skrip
    swa = subprocess.run([sys.executable, str(skrip), "--self-test"], capture_output=True, text=True, cwd=REPO)
    assert swa.returncode == 0, swa.stdout + swa.stderr
    nyata = subprocess.run([sys.executable, str(skrip)], capture_output=True, text=True, cwd=REPO)
    assert nyata.returncode == 0 and "0 pelanggaran" in nyata.stdout, nyata.stdout + nyata.stderr


#: Direkam dari kode SEBELUM Tugas 2 (2607943) — jangan disunting tangan.
BARIS_LAMA: dict = {'batal_kas': [['6-2000', 'Beban Sewa', 0.0, 125000.0, 'Pembalik KB#LA/CASH-# · Sewa KB#', ''],
               ['1-1110', 'Kas Kecil', 125000.0, 0.0, 'Pembalik KB#LA/CASH-# · Sewa KB#', '']],
 'beban_antar_pt': [[['2-1250',
                      'Utang Antar-Perusahaan (IC-AP)',
                      900000.0,
                      0.0,
                      'Bayar tagihan insentif ICC-KB#/# ke Penagih',
                      ''],
                     ['1-1100',
                      'Kas Besar / Bank',
                      0.0,
                      900000.0,
                      'Bayar tagihan insentif ICC-KB#/# ke Penagih',
                      '']],
                    [['1-1100',
                      'Kas Besar / Bank',
                      900000.0,
                      0.0,
                      'Terima pelunasan tagihan insentif ICC-KB#/# dari Tertagih',
                      ''],
                     ['1-1250',
                      'Piutang Antar-Perusahaan (IC-AR)',
                      0.0,
                      900000.0,
                      'Terima pelunasan tagihan insentif ICC-KB#/# dari Tertagih',
                      '']]],
 'gaji': {'baru': [['2-1600',
                    'Hutang Gaji',
                    1200000.0,
                    0.0,
                    'KB#LA/CASH-# · Pembayaran gaji November # (PAY-KB#)',
                    ''],
                   ['1-1110',
                    'Kas Kecil',
                    0.0,
                    1200000.0,
                    'KB#LA/CASH-# · Pembayaran gaji November # (PAY-KB#)',
                    '']],
          'lama': ['kas_kecil', True, '1-1110']},
 'ongkir_retur': {'bawaan_pemetaan': {'baris': [['6-4500',
                                                 'Beban Kirim Dokumen & Ekspedisi',
                                                 50000.0,
                                                 0.0,
                                                 'Ongkir retur dari customer · retur RJ/KB#/ONG/#',
                                                 'retur.ongkir_perusahaan'],
                                                ['1-1110',
                                                 'Kas Kecil',
                                                 0.0,
                                                 50000.0,
                                                 'Pembayaran Ongkir retur dari customer · retur RJ/KB#/ONG/#',
                                                 'retur.ongkir_pembayaran']],
                                      'ref': ['cost_type', 'return_id', 'return_number']},
                  'hutang': {'baris': [['6-4500',
                                        'Beban Kirim Dokumen & Ekspedisi',
                                        50000.0,
                                        0.0,
                                        'Ongkir retur dari customer · retur RJ/KB#/ONG/#',
                                        'retur.ongkir_perusahaan'],
                                       ['2-1100',
                                        'Hutang Usaha',
                                        0.0,
                                        50000.0,
                                        'Pembayaran Ongkir retur dari customer · retur RJ/KB#/ONG/#',
                                        '']],
                             'ref': ['cost_type', 'return_id', 'return_number']},
                  'kas_kecil': {'baris': [['6-4500',
                                           'Beban Kirim Dokumen & Ekspedisi',
                                           50000.0,
                                           0.0,
                                           'Ongkir retur dari customer · retur RJ/KB#/ONG/#',
                                           'retur.ongkir_perusahaan'],
                                          ['1-1110',
                                           'Kas Kecil',
                                           0.0,
                                           50000.0,
                                           'Pembayaran Ongkir retur dari customer · retur RJ/KB#/ONG/#',
                                           '']],
                                'ref': ['cost_type', 'return_id', 'return_number']}},
 'pelepasan_aset': [['1-2900',
                     'Akumulasi Penyusutan Aset Tetap',
                     400000.0,
                     0.0,
                     'Hapus akumulasi penyusutan FA-KB#',
                     ''],
                    ['1-1100', 'Kas Besar / Bank', 700000.0, 0.0, 'Hasil pelepasan FA-KB#', ''],
                    ['1-2100', 'Peralatan & Mesin', 0.0, 1000000.0, 'Hapus aset FA-KB# (harga perolehan)', ''],
                    ['4-9100', 'Laba Pelepasan Aset Tetap', 0.0, 100000.0, 'Laba pelepasan FA-KB#', '']],
 'pelunasan_antar_pt': {'refund': [['payer',
                                    True,
                                    [['1-1250', 750000.0, 0.0, 'Pengembalian dana antar-PT ICS-KB# → LB'],
                                     ['1-1100', 0.0, 750000.0, 'Pengembalian dana antar-PT ICS-KB# → LB']]],
                                   ['payee',
                                    False,
                                    [['1-1100', 750000.0, 0.0, 'Terima pengembalian dana antar-PT ICS-KB# ← LA'],
                                     ['2-1250', 0.0, 750000.0, 'Terima pengembalian dana antar-PT ICS-KB# ← LA']]]],
                        'transfer': [['payer',
                                      True,
                                      [['2-1250', 750000.0, 0.0, 'Bayar utang antar-PT ICS-KB# → LB'],
                                       ['1-1100', 0.0, 750000.0, 'Bayar utang antar-PT ICS-KB# → LB']]],
                                     ['payee',
                                      False,
                                      [['1-1100', 750000.0, 0.0, 'Terima pelunasan antar-PT ICS-KB# ← LA'],
                                       ['1-1250', 0.0, 750000.0, 'Terima pelunasan antar-PT ICS-KB# ← LA']]]]},
 'penjualan_tunai': [['1-1100', 'Kas Besar / Bank', 220000.0, 0.0, 'Tunai SO/KB#T/#', ''],
                     ['4-1000', 'Pendapatan Penjualan', 0.0, 200000.0, 'Penjualan SO/KB#T/#', ''],
                     ['2-1200', 'PPN Keluaran', 0.0, 20000.0, 'PPN Keluaran SO/KB#T/#', '']],
 'perolehan_aset': {'kas_kecil': [['1-2100',
                                   'Peralatan & Mesin',
                                   2500000.0,
                                   0.0,
                                   'Perolehan aset FA-KB#P/# Mesin KB#',
                                   ''],
                                  ['1-1110',
                                   'Kas Kecil',
                                   0.0,
                                   2500000.0,
                                   'Pembayaran perolehan aset FA-KB#P/# Mesin KB#',
                                   '']],
                    'tanpa_sumber': [['1-2100',
                                      'Peralatan & Mesin',
                                      2500000.0,
                                      0.0,
                                      'Perolehan aset FA-KB#P/# Mesin KB#',
                                      ''],
                                     ['1-1100',
                                      'Kas Besar / Bank',
                                      0.0,
                                      2500000.0,
                                      'Pembayaran perolehan aset FA-KB#P/# Mesin KB#',
                                      '']]},
 'pindah_aset': [[['2-1250', 'Utang Antar-Perusahaan (IC-AP)', 6000000.0, 0.0, 'Bayar pindah aset FA-KB#/#', ''],
                  ['1-1100', 'Kas Besar / Bank', 0.0, 6000000.0, 'Bayar pindah aset FA-KB#/#', '']],
                 [['1-1100', 'Kas Besar / Bank', 6000000.0, 0.0, 'Terima pembayaran pindah aset FA-KB#/#', ''],
                  ['1-1250',
                   'Piutang Antar-Perusahaan (IC-AR)',
                   0.0,
                   6000000.0,
                   'Terima pembayaran pindah aset FA-KB#/#',
                   '']]],
 'pinjaman': [[['1-1250', 'Piutang Antar-Perusahaan (IC-AR)', 5000000.0, 0.0, 'Pinjaman kepada Uji KB#LB', ''],
               ['1-1100', 'Kas Besar / Bank', 0.0, 5000000.0, 'Pinjaman kepada Uji KB#LB', '']],
              [['1-1100', 'Kas Besar / Bank', 5000000.0, 0.0, 'Pinjaman dari Uji KB#LA', ''],
               ['2-1250', 'Utang Antar-Perusahaan (IC-AP)', 0.0, 5000000.0, 'Pinjaman dari Uji KB#LA', '']],
              [['2-1250', 'Utang Antar-Perusahaan (IC-AP)', 2000000.0, 0.0, 'Angsuran pinjaman ke Uji KB#LA', ''],
               ['1-1100', 'Kas Besar / Bank', 0.0, 2000000.0, 'Angsuran pinjaman ke Uji KB#LA', '']],
              [['1-1100', 'Kas Besar / Bank', 2000000.0, 0.0, 'Terima angsuran dari Uji KB#LB', ''],
               ['1-1250', 'Piutang Antar-Perusahaan (IC-AR)', 0.0, 2000000.0, 'Terima angsuran dari Uji KB#LB', '']]],
 'refund_retur': {'bank': [['4-1000', 'Pendapatan Penjualan', 400000.0, 0.0, 'Retur penjualan CN-#', ''],
                           ['1-1100', 'Kas Besar / Bank', 0.0, 400000.0, 'Refund tunai CN-#', ''],
                           ['1-1300', 'Persediaan Barang', 240000.0, 0.0, 'Barang retur masuk stok CN-#', ''],
                           ['5-1000', 'Harga Pokok Penjualan', 0.0, 240000.0, 'Barang retur masuk stok CN-#', '']],
                  'kas_bank': ['1-1100', 'kas_besar'],
                  'kas_kecil': ['1-1110', 'kas_kecil'],
                  'kecil': [['4-1000', 'Pendapatan Penjualan', 400000.0, 0.0, 'Retur penjualan CN-#', ''],
                            ['1-1110', 'Kas Kecil', 0.0, 400000.0, 'Refund tunai CN-#', ''],
                            ['1-1300', 'Persediaan Barang', 240000.0, 0.0, 'Barang retur masuk stok CN-#', ''],
                            ['5-1000', 'Harga Pokok Penjualan', 0.0, 240000.0, 'Barang retur masuk stok CN-#', '']]},
 'retur_beli': {'jurnal': [['1-1110', 'Kas Kecil', 550000.0, 0.0, 'Refund tunai supplier — retur beli DN-#', ''],
                           ['1-1300', 'Persediaan Barang', 0.0, 550000.0, 'Barang keluar retur beli DN-#', '']],
                'kas': ['1-1110', 'kas_kecil', 'in'],
                'kode': '1-1110'},
 'retur_per_roll': [['4-1000', 'Pendapatan Penjualan', 300000.0, 0.0, 'Retur penjualan CN-#', ''],
                    ['1-1100', 'Kas Besar / Bank', 0.0, 300000.0, 'Refund tunai CN-#', ''],
                    ['1-1300', 'Persediaan Barang', 180000.0, 0.0, 'Barang retur masuk stok CN-#', ''],
                    ['5-1000', 'Harga Pokok Penjualan', 0.0, 180000.0, 'Barang retur masuk stok CN-#', '']]}

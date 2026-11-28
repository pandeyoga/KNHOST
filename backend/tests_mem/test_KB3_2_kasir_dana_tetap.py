"""Kas & Bank 3 Tugas 2 — C1 alur kas kasir (kwitansi tunai → kas kasir tunggal PT) dan C2 dana tetap kas kecil
(posisi, isi ulang = Pindah Dana sekali jalan bertanda `isi_ulang_kas_kecil` dengan nominal terkunci).

Rancangan: `docs/superpowers/specs/2026-11-28-kas-bank-3-kasir-dana-tetap-opname-design.md` §5.1, §5.2, §7 butir 2–3,
§7.8 butir 1, 4, 5.

Persiapan (FIXTURE kecuali disebut ALUR): PT uji baru per uji (`pt_uji`), rekening lewat `bank_service.create_account`
(ALUR layanan), pelanggan disisip langsung. PD disisip berstatus `approved` lalu DICAIRKAN lewat layanan (ALUR); LPJ
dibuat/diajukan/disetujui, sisa dikembalikan, reimburse dibayar lewat layanan (ALUR). Kas keluar manual lewat pintu kas
`cash_ledger.create_cash` (ALUR, rujukan `manual`). Kwitansi lewat `POST /api/ar-receipts` (ALUR).

Hitung tangan (U5–U6), rekening Kas Kecil KK: saldo awal 2.000.000, dana tetap 2.000.000.
  PD-A 500.000 dicairkan dari KK (belum LPJ); PD-B 300.000 dicairkan dari KK, LPJ 300.000 disetujui; kas keluar
  manual 200.000 dari KK. Saldo buku = 2.000.000 − 500.000 − 300.000 − 200.000 = 1.000.000; panjar belum LPJ = 500.000;
  usulan = 2.000.000 − 1.000.000 − 500.000 = 500.000 (= LPJ PD-B 300.000 + manual 200.000).
  Isi ulang dari BCA → Pindah Dana 500.000 sekali jalan → saldo KK 1.500.000 → usulan 0 (isi ulang kedua 400).
  LPJ PD-A 450.000 → panjar 0 → usulan 2.000.000 − 1.500.000 − 0 = 500.000 (baris LPJ = panjar 500.000);
  sisa 50.000 kembali ke KK → saldo 1.550.000 → usulan 450.000 (baris pengembalian −50.000).
  PD-C 100.000 dicairkan, LPJ 130.000 (reimburse 30.000), reimburse dibayar dari KK → saldo 1.420.000 → usulan
  580.000 (= 450.000 + LPJ PD-C 100.000 + reimburse 30.000).
"""
from __future__ import annotations

import asyncio
import itertools
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from core_utils import now_iso
from pembantu import AKTOR_UJI, pt_uji, saldo_akun

pytestmark = pytest.mark.anyio

PEMBUAT = {"id": "usr_kb32_buat", "name": "Rina Kasir", "role": "finance", "email": "rina.kb32@uji.id"}
PENYETUJU = {"id": "usr_kb32_setuju", "name": "Dodi Finance", "role": "finance", "email": "dodi.kb32@uji.id"}
PEMOHON = {"id": "usr_kb32_pemohon", "name": "Sari Staf", "role": "finance", "email": "sari.kb32@uji.id"}
JENIS = "isi_ulang_kas_kecil"
_urut = itertools.count(1)


def _kode(awal: str) -> str:
    return f"{awal}{next(_urut)}"


def _hari() -> str:
    from services.book_date import tanggal_buku
    return tanggal_buku()


async def _rekening(eid: str, nama: str, jenis_akun: str = "bank", jenis_kas: str = "", awal: float = 0.0,
                    dana: float = 0.0, **lain) -> str:
    from schemas_finance import BankAccountCreate
    from services import bank_service
    acc = await bank_service.create_account(
        BankAccountCreate(name=nama, account_type=jenis_akun, cash_type=jenis_kas, entity_id=eid, opening_balance=awal,
                          dana_tetap=dana, **lain), AKTOR_UJI)
    return acc["id"]


async def _pt(mode: str = "lama", awal: str = "KB32", *, kasir: int = 1, dana: float = 2_000_000,
              awal_kk: float = 2_000_000) -> dict:
    """PT uji: BCA (bank, saldo awal 10 jt), KB (kas besar tunai, saldo awal 1 jt), KK (kas kecil, saldo awal
    `awal_kk`, dana tetap `dana`), `kasir` rekening kas kasir KS1.. (KS = KS1). `aktif` → PT dinyalakan lebih dulu."""
    from services import cash_account_mode as mode_kas
    from services.entity_lifecycle_service import invalidate_status_cache
    kode = _kode(f"{awal}{'A' if mode == 'aktif' else 'L'}")
    eid = await pt_uji(kode)
    if mode == "aktif":
        await mode_kas.nyalakan(eid, "Uji KB3-2")
    rek = {"BCA": await _rekening(eid, f"BCA {kode}", awal=10_000_000),
           "KB": await _rekening(eid, f"Kas Besar {kode}", "cash", "kas_besar", awal=1_000_000),
           "KK": await _rekening(eid, f"Kas Kecil {kode}", "cash", "kas_kecil", awal=awal_kk, dana=dana)}
    for i in range(1, kasir + 1):
        rek[f"KS{i}"] = await _rekening(eid, f"Kas Kasir {i} {kode}", "cash", "kas_kasir")
    if kasir:
        rek["KS"] = rek["KS1"]
    cus = f"cus_kb32_{uuid.uuid4().hex[:8]}"
    from db import db
    await db.customers.insert_one({"id": cus, "name": f"Toko Uji {kode}", "entity_id": eid, "status": "active"})
    invalidate_status_cache()
    return {"id": eid, "kode": kode, "rek": rek, "mode": mode, "cus": cus}


async def _buku(rid: str) -> float:
    from services import bank_service
    return round((await bank_service.account_ledger(rid))["balance"], 2)


async def _akun_rek(db, rid: str) -> str:
    return (await db.bank_accounts.find_one({"id": rid}, {"_id": 0}))["gl_account_code"]


async def _ditolak(coro, status: int, pesan: str = "") -> HTTPException:
    with pytest.raises(HTTPException) as e:
        await coro
    assert e.value.status_code == status, e.value.detail
    if pesan:
        assert e.value.detail == pesan, e.value.detail
    return e.value


async def _atur(key: str, nilai, eid: str) -> None:
    from services import config_resolver as resolver
    await resolver.set_value(key, nilai, scope_type="entity", scope_id=eid, reason="uji KB3-2", actor="uji")


def _ctx(pt: dict, user: dict):
    from entity_scope import EntityContext
    return EntityContext(user=user, active_entity_id=pt["id"], allowed_entity_ids=[pt["id"]], view_all=False)


async def _pd_cair(db, pt: dict, nilai: float, rek: str = "KK") -> str:
    """PD berstatus `approved` disisip (FIXTURE) lalu DICAIRKAN dari rekening `rek` lewat layanan (ALUR)."""
    from schemas_cash_advance import DisburseInput
    from services import cash_advance_service as cas
    ca = f"ca_kb32_{uuid.uuid4().hex[:8]}"
    await db.cash_advances.insert_one({
        "id": ca, "number": f"PD-{ca[-6:]}", "entity_id": pt["id"], "status": "approved", "kegiatan": "uji KB3-2",
        "divisi": "Umum", "lines": [{"description": "uang muka", "qty": 1, "unit_price": nilai, "amount": nilai}],
        "total_amount": float(nilai), "approvals": [], "payment_method": "cash",
        "created_by": PEMOHON["name"], "created_by_id": PEMOHON["id"], "created_at": now_iso()})
    hasil = await cas.disburse_cash_advance(ca, DisburseInput(cash_type="kas_kecil", account_id=pt["rek"][rek],
                                                              note="uji"), _ctx(pt, PENYETUJU), PENYETUJU)
    assert hasil["status"] == "disbursed", hasil
    return ca


async def _lpj(pt: dict, ca: str, baris, *, setujui: bool = True) -> dict:
    from schemas_cash_advance import SettlementCreate, SettlementLine
    from services import cash_advance_service as cas
    stl = await cas.create_settlement(SettlementCreate(
        cash_advance_id=ca, periode=_hari()[:7],
        expense_lines=[SettlementLine(date=_hari(), description=f"uji {k}", category=k, amount=v) for k, v in baris]),
        _ctx(pt, PEMOHON), PEMOHON)
    stl = await cas.submit_settlement(stl["id"], _ctx(pt, PEMOHON), PEMOHON)
    if setujui:
        stl = await cas.approve_settlement(stl["id"], _ctx(pt, PENYETUJU), PENYETUJU)
        assert stl["status"] == "posted_to_gl", stl
    return stl


async def _kembalikan(pt: dict, stl_id: str, rek: str = "KK") -> None:
    from schemas_cash_advance import ReturnRemainderIn
    from services import cash_advance_service as cas
    out = await cas.return_remainder(stl_id, ReturnRemainderIn(cash_type="kas_kecil", account_id=pt["rek"][rek]),
                                     _ctx(pt, PENYETUJU), PENYETUJU)
    assert out["sisa_dikembalikan"]["status"] == "returned", out


async def _bayar_reimburse(pt: dict, stl_id: str, rek: str = "KK") -> None:
    from services import cash_advance_service as cas
    out = await cas.pay_reimburse(stl_id, SimpleNamespace(cash_type="kas_kecil", account_id=pt["rek"][rek],
                                                          txn_date=None), _ctx(pt, PENYETUJU), PENYETUJU)
    assert out["hutang_reimburse"]["status"] == "paid", out


async def _kas_manual(pt: dict, rek: str, nominal: float, arah: str = "out") -> dict:
    from services import cash_ledger
    return await cash_ledger.create_cash(
        entity_id=pt["id"], direction=arah, amount=nominal, ref_type="manual", ref_id=f"man_kb32_{uuid.uuid4().hex}",
        account_id=pt["rek"][rek], category="ATK", description="uji kas manual KB3-2", actor="uji",
        contra_account_code="6-4100")


async def _skenario(db, pt: dict) -> dict:
    """U5 — PD-A 500.000 belum LPJ, PD-B 300.000 ber-LPJ 300.000 disetujui, kas keluar manual 200.000."""
    pd_a = await _pd_cair(db, pt, 500_000)
    pd_b = await _pd_cair(db, pt, 300_000)
    lpj_b = await _lpj(pt, pd_b, [("atk", 300_000)])
    manual = await _kas_manual(pt, "KK", 200_000)
    return {"pd_a": pd_a, "pd_b": pd_b, "lpj_b": lpj_b, "manual": manual}


async def _jurnal_kas(db, kas_id: str) -> list:
    je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": kas_id,
                                            "status": {"$ne": "void"}}, {"_id": 0})
    assert je, kas_id
    return sorted((ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"])


async def _kwitansi(klien, sesi, pt: dict, nominal: float, **isi):
    h = await sesi("admin@kainnusantara.id", entitas=pt["id"])
    return await klien.post("/api/ar-receipts", headers=h, json={
        "customer_id": pt["cus"], "amount": nominal, "method": "cash", "entity_id": pt["id"], "notes": "uji KB3-2",
        **isi})


async def _penerima(klien, sesi, pt: dict) -> list:
    h = await sesi("admin@kainnusantara.id", entitas=pt["id"])
    r = await klien.get("/api/bank-accounts/receiving", headers=h, params={"method": "cash", "entity_id": pt["id"]})
    assert r.status_code == 200, r.text
    return [(x["id"], x["is_default"]) for x in r.json()]


# ═══ C1 — kwitansi tunai ke kas kasir tunggal PT ═════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("mode", ["lama", "aktif"])
async def test_KB3_2_U1_kwitansi_tunai_ke_kas_kasir_tunggal(klien, db, sesi, mode):
    pt = await _pt(mode)
    # Rekening penerima tunai: kas kasir tunggal = bawaan (urutan pertama), kas besar & kas kecil tidak.
    daftar = await _penerima(klien, sesi, pt)
    assert daftar[0] == (pt["rek"]["KS"], True), daftar
    assert {rid for rid, bawaan in daftar if bawaan} == {pt["rek"]["KS"]}
    r = await _kwitansi(klien, sesi, pt, 750_000)
    assert r.status_code == 200, r.text
    rc = r.json()
    assert rc["account_id"] == pt["rek"]["KS"], rc
    kas = await db.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": rc["id"]}, {"_id": 0})
    assert (kas["account_id"], kas["cash_type"], kas["direction"], kas["amount"]) == (
        pt["rek"]["KS"], "kas_kasir", "in", 750_000.0)
    akun = "1-1105" if mode == "lama" else await _akun_rek(db, pt["rek"]["KS"])
    if mode == "aktif":
        assert akun.startswith("1-1105-"), akun
    dr = [x for x in await _jurnal_kas(db, kas["id"]) if x[1] > 0]
    assert dr == [(akun, 750_000.0, 0.0)], dr
    # Buku kas rekening kasir = 750.000; PT aktif: sub-akun = buku kas rekening.
    assert await _buku(pt["rek"]["KS"]) == 750_000.0
    if mode == "aktif":
        assert round(await saldo_akun(akun, pt["id"]), 2) == 750_000.0
    # Kwitansi tunai yang memilih rekening sendiri tetap ke rekening itu (perilaku "pilih rekening" yang ada).
    r = await _kwitansi(klien, sesi, pt, 100_000, account_id=pt["rek"]["KK"])
    assert r.status_code == 200 and r.json()["account_id"] == pt["rek"]["KK"], r.text


async def test_KB3_2_U2_pt_tanpa_kas_kasir_tetap_kas_kecil(klien, db, sesi):
    """Regresi — PT tanpa rekening kas kasir: kwitansi tunai ke kas kecil tunggal seperti sekarang (jurnal 1-1110)."""
    pt = await _pt(kasir=0)
    # Tanpa bawaan tersimpan: urut nama (Kas Besar, Kas Kecil), tidak ada yang bawaan — persis seperti sekarang.
    assert await _penerima(klien, sesi, pt) == [(pt["rek"]["KB"], False), (pt["rek"]["KK"], False)]
    r = await _kwitansi(klien, sesi, pt, 400_000)
    assert r.status_code == 200, r.text
    rc = r.json()
    assert rc["account_id"] == pt["rek"]["KK"], rc
    kas = await db.cash_transactions.find_one({"ref_type": "ar_receipt", "ref_id": rc["id"]}, {"_id": 0})
    assert (kas["cash_type"], kas["account_id"]) == ("kas_kecil", pt["rek"]["KK"])
    assert [x for x in await _jurnal_kas(db, kas["id"]) if x[1] > 0] == [("1-1110", 400_000.0, 0.0)]


async def test_KB3_2_U3_dua_kas_kasir_tanpa_bawaan_dan_bawaan_eksplisit_menang(klien, db, sesi):
    from services.bank_service import account_cash_type
    pt = await _pt(kasir=2)
    # §7.8.5 — lebih dari satu kas kasir: tidak ada bawaan, kasir memilih rekening (tidak jatuh ke kas kecil).
    assert not [rid for rid, bawaan in await _penerima(klien, sesi, pt) if bawaan]
    sebelum = await db.ar_receipts.count_documents({"entity_id": pt["id"]})
    r = await _kwitansi(klien, sesi, pt, 300_000)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == (f"Pilih rekening kas/bank untuk transaksi ini. Uji {pt['kode']} punya 2 rekening "
                                  "Kas kasir."), r.text
    assert await db.ar_receipts.count_documents({"entity_id": pt["id"]}) == sebelum
    r = await _kwitansi(klien, sesi, pt, 300_000, account_id=pt["rek"]["KS2"])
    assert r.status_code == 200 and r.json()["account_id"] == pt["rek"]["KS2"], r.text
    # Bawaan penerimaan tunai yang diatur Finance (PM-T1) di rekening kas kecil tetap menang atas kas kasir tunggal.
    pt2 = await _pt()
    from services import bank_service as bs
    await db.bank_accounts.update_one({"id": pt2["rek"]["KK"]}, {"$set": {"default_receiving_methods": ["cash"]}})
    daftar = await _penerima(klien, sesi, pt2)
    assert {rid for rid, bawaan in daftar if bawaan} == {pt2["rek"]["KK"]}, daftar
    r = await _kwitansi(klien, sesi, pt2, 200_000)
    assert r.status_code == 200 and r.json()["account_id"] == pt2["rek"]["KK"], r.text
    acc = await db.bank_accounts.find_one({"id": pt2["rek"]["KS"]}, {"_id": 0})
    assert account_cash_type(acc) == "kas_kasir" and await bs.sole_account_id(pt2["id"], "kas_kasir") == acc["id"]


async def test_KB3_2_U4_antar_pt_kas_kasir_ditolak(db):
    from services import interco_money_service as money
    from services import interco_service
    pt, lain = await _pt(), await _pt(kasir=0)
    with pytest.raises(money.IntercoMoneyError) as e:
        await money.twin_cash(out_entity=pt["id"], in_entity=lain["id"], amount=100_000, category="uji",
                              description="uji antar-PT kasir", ref_type="uji_kb32", ref_id=uuid.uuid4().hex,
                              out_account_id=pt["rek"]["KS"], in_account_id=lain["rek"]["BCA"])
    assert str(e.value) == (f"Rekening Kas Kasir 1 {pt['kode']} adalah Kas kasir; uang antar-PT dibukukan di Bank "
                            "(1-1100). Pilih rekening Bank.")
    # Regresi: kas kecil tetap kalimat lama.
    with pytest.raises(money.IntercoMoneyError) as e:
        await money.twin_cash(out_entity=pt["id"], in_entity=lain["id"], amount=100_000, category="uji",
                              description="uji antar-PT kas kecil", ref_type="uji_kb32", ref_id=uuid.uuid4().hex,
                              out_account_id=pt["rek"]["KK"], in_account_id=lain["rek"]["BCA"])
    assert str(e.value) == (f"Rekening Kas Kecil {pt['kode']} adalah Kas Kecil; uang antar-PT dibukukan di Bank "
                            "(1-1100). Pilih rekening Bank.")
    assert await db.cash_transactions.count_documents({"ref_type": "uji_kb32"}) == 0
    with pytest.raises(interco_service.IntercoError) as e:
        await interco_service._settle_account(pt["id"], pt["rek"]["KS"])
    assert str(e.value) == (f"Rekening Kas Kasir 1 {pt['kode']} adalah Kas kasir; pelunasan antar-PT dibukukan di "
                            "Bank (1-1100). Pilih rekening Bank.")


# ═══ C2 — posisi dana tetap ═══════════════════════════════════════════════════════════════════════════════════════════
async def test_KB3_2_U5_posisi_dana_tetap_usulan(db):
    from services import petty_float_service as pfs
    pt = await _pt()
    s = await _skenario(db, pt)
    p = await pfs.posisi(pt["rek"]["KK"])
    assert (p["account_id"], p["entity_id"], p["dana_tetap"], p["saldo_buku"], p["panjar_belum_lpj"],
            p["usulan_isi_ulang"]) == (pt["rek"]["KK"], pt["id"], 2_000_000.0, 1_000_000.0, 500_000.0, 500_000.0)
    assert p["saldo_buku"] == await _buku(pt["rek"]["KK"])
    assert p["isi_ulang_menunggu"] is None and p["sejak"] is None and p["riwayat"] == []
    assert p["bisa_isi_ulang"] is True and p["alasan_isi_ulang"] == ""
    assert [(x["cash_advance_id"], x["nominal"]) for x in p["panjar"]] == [(s["pd_a"], 500_000.0)]
    assert [(x["jenis"], x["nominal"], x["pengaruh"]) for x in p["rincian"]] == [
        ("lpj", 300_000.0, 300_000.0), ("kas_keluar_manual", 200_000.0, 200_000.0)], p["rincian"]
    assert p["rincian"][0]["ref_id"] == s["lpj_b"]["id"] and p["rincian"][1]["ref_id"] == s["manual"]["ref_id"]
    assert p["total_rincian"] == 500_000.0
    assert p["panjar_tanpa_rekening"] == {"jumlah": 0, "total": 0.0, "nomor": []}
    assert {x["id"] for x in p["sumber"]} == {pt["rek"]["BCA"], pt["rek"]["KB"]}
    # Daftar PT: hanya rekening kas kecil berdana tetap.
    d = await pfs.daftar([pt["id"]])
    assert [x["account_id"] for x in d["items"]] == [pt["rek"]["KK"]] and d["total"] == 1
    assert d["tanpa_dana_tetap"] == 0
    assert d["items"][0]["usulan_isi_ulang"] == 500_000.0


async def test_KB3_2_U5b_pencairan_lama_tanpa_rekening_disebut(db):
    """§7.8.1 — pencairan panjar lama tanpa rekening tidak dihitung ke rekening mana pun, tetapi disebut di posisi."""
    from services import petty_float_service as pfs
    pt = await _pt()
    ca = await _pd_cair(db, pt, 250_000)
    await db.cash_transactions.update_one({"ref_type": "cash_advance", "ref_id": ca}, {"$set": {"account_id": ""}})
    p = await pfs.posisi(pt["rek"]["KK"])
    assert p["panjar"] == [] and p["panjar_belum_lpj"] == 0.0
    nomor = (await db.cash_advances.find_one({"id": ca}, {"_id": 0}))["number"]
    assert p["panjar_tanpa_rekening"] == {"jumlah": 1, "total": 250_000.0, "nomor": [nomor]}


# ═══ C2 — isi ulang terkunci ══════════════════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("mode", ["lama", "aktif"])
async def test_KB3_2_U6_isi_ulang_pindah_dana_bertanda_lalu_rincian_sejak(db, mode):
    from services import fund_transfer_service as fts
    from services import petty_float_service as pfs
    pt = await _pt(mode)
    s = await _skenario(db, pt)
    doc = await pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["BCA"], PEMBUAT)
    assert (doc["status"], doc["jenis"], doc["jenis_label"], doc["nominal"], doc["biaya"], doc["dua_tahap"]) == (
        "selesai", JENIS, "Isi ulang kas kecil", 500_000.0, 0.0, False), doc
    assert (doc["rekening_asal_id"], doc["rekening_tujuan_id"]) == (pt["rek"]["BCA"], pt["rek"]["KK"])
    assert doc["number"].startswith(f"{pt['kode']}/PDN-") and doc["tanggal_kirim"] == doc["tanggal_terima"] == _hari()
    pot = doc["isi_ulang"]
    assert (pot["account_id"], pot["dana_tetap"], pot["saldo_buku"], pot["panjar_belum_lpj"], pot["usulan"]) == (
        pt["rek"]["KK"], 2_000_000.0, 1_000_000.0, 500_000.0, 500_000.0)
    assert [x["jenis"] for x in pot["rincian"]] == ["lpj", "kas_keluar_manual"] and pot["dihitung_pada"]
    assert [x["cash_advance_id"] for x in pot["panjar"]] == [s["pd_a"]]
    kas = {t["seq"]: t async for t in db.cash_transactions.find({"ref_type": "fund_transfer", "ref_id": doc["id"]},
                                                                 {"_id": 0})}
    assert {k: (t["direction"], t["amount"], t["account_id"]) for k, t in kas.items()} == {
        "kirim": ("out", 500_000.0, pt["rek"]["BCA"]), "terima": ("in", 500_000.0, pt["rek"]["KK"])}
    assert await _buku(pt["rek"]["KK"]) == 1_500_000.0
    r = await fts.rincian(doc["id"])
    assert r["jenis"] == JENIS and r["isi_ulang"]["usulan"] == 500_000.0
    assert r["jejak"][0]["catatan"] == "isi ulang kas kecil"
    # Sesudah isi ulang: usulan 0 → isi ulang kedua ditolak, tanpa Pindah Dana baru.
    p = await pfs.posisi(pt["rek"]["KK"])
    assert (p["saldo_buku"], p["panjar_belum_lpj"], p["usulan_isi_ulang"], p["rincian"]) == (
        1_500_000.0, 500_000.0, 0.0, [])
    assert p["sejak"]["id"] == doc["id"] and [x["id"] for x in p["riwayat"]] == [doc["id"]]
    pesan_tidak_perlu = (f"Rekening Kas Kecil {pt['kode']} tidak perlu diisi ulang: saldo buku ditambah panjar yang "
                         "belum di-LPJ sudah mencapai dana tetap Rp 2.000.000.")
    assert p["bisa_isi_ulang"] is False and p["alasan_isi_ulang"] == pesan_tidak_perlu
    await _ditolak(pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["BCA"], PEMBUAT), 400, pesan_tidak_perlu)
    assert await db.fund_transfers.count_documents({"entity_id": pt["id"]}) == 1
    # LPJ PD-A 450.000 → baris LPJ = panjar 500.000; sisa 50.000 kembali → baris −50.000.
    lpj_a = await _lpj(pt, s["pd_a"], [("atk", 450_000)])
    p = await pfs.posisi(pt["rek"]["KK"])
    assert (p["panjar_belum_lpj"], p["usulan_isi_ulang"]) == (0.0, 500_000.0)
    assert [(x["jenis"], x["nominal"], x["pengaruh"], x.get("pengeluaran")) for x in p["rincian"]] == [
        ("lpj", 500_000.0, 500_000.0, 450_000.0)]
    await _kembalikan(pt, lpj_a["id"])
    p = await pfs.posisi(pt["rek"]["KK"])
    assert (p["saldo_buku"], p["usulan_isi_ulang"], p["total_rincian"]) == (1_550_000.0, 450_000.0, 450_000.0)
    assert [(x["jenis"], x["pengaruh"]) for x in p["rincian"]] == [("lpj", 500_000.0),
                                                                   ("pengembalian_panjar", -50_000.0)]
    # PD-C 100.000, LPJ 130.000 → reimburse 30.000 dibayar dari KK.
    pd_c = await _pd_cair(db, pt, 100_000)
    lpj_c = await _lpj(pt, pd_c, [("atk", 130_000)])
    await _bayar_reimburse(pt, lpj_c["id"])
    p = await pfs.posisi(pt["rek"]["KK"])
    assert (p["saldo_buku"], p["panjar_belum_lpj"], p["usulan_isi_ulang"], p["total_rincian"]) == (
        1_420_000.0, 0.0, 580_000.0, 580_000.0)
    assert [x["jenis"] for x in p["rincian"]] == ["lpj", "pengembalian_panjar", "lpj", "reimburse_dibayar"]
    # Isi ulang kedua = 580.000; PT aktif: sub-akun rekening = buku kas rekening (KK dan BCA).
    dua = await pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["KB"], PEMBUAT, catatan="isi ulang minggu ini")
    assert (dua["status"], dua["nominal"], dua["rekening_asal_id"]) == ("selesai", 580_000.0, pt["rek"]["KB"])
    assert await _buku(pt["rek"]["KK"]) == 2_000_000.0
    if mode == "aktif":
        for nama in ("KK", "BCA", "KB"):
            akun = await _akun_rek(db, pt["rek"][nama])
            assert round(await saldo_akun(akun, pt["id"]), 2) == await _buku(pt["rek"][nama]), nama
    p = await pfs.posisi(pt["rek"]["KK"])
    assert p["usulan_isi_ulang"] == 0.0 and [x["id"] for x in p["riwayat"]] == [dua["id"], doc["id"]]


async def test_KB3_2_U7_nominal_dari_klien_ditolak(db):
    from services import petty_float_service as pfs
    pt = await _pt()
    await _kas_manual(pt, "KK", 100_000)
    await _ditolak(pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["BCA"], PEMBUAT, nominal=999_999), 400,
                   "Nominal isi ulang dihitung sistem dari posisi dana tetap (dana tetap − saldo buku − panjar belum "
                   "LPJ), jadi tidak bisa diisi.")
    assert await db.fund_transfers.count_documents({"entity_id": pt["id"]}) == 0
    doc = await pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["BCA"], PEMBUAT)
    assert doc["nominal"] == 100_000.0


async def test_KB3_2_U8_kontrol_dua_orang_menunggu_dan_nominal_beku(db):
    from services import dual_control
    from services import fund_transfer_service as fts
    from services import petty_float_service as pfs
    pt = await _pt()
    await _atur("kontrol.pindah_dana.min_orang", "2", pt["id"])
    await _kas_manual(pt, "KK", 300_000)
    doc = await pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["BCA"], PEMBUAT)
    assert (doc["status"], doc["nominal"], doc["jenis"]) == ("menunggu_persetujuan", 300_000.0, JENIS)
    assert await db.cash_transactions.count_documents({"ref_type": "fund_transfer", "ref_id": doc["id"]}) == 0
    p = await pfs.posisi(pt["rek"]["KK"])
    assert p["isi_ulang_menunggu"]["id"] == doc["id"] and p["isi_ulang_menunggu"]["nominal"] == 300_000.0
    pesan = (f"Isi ulang rekening Kas Kecil {pt['kode']} sebelumnya ({doc['number']}) masih menunggu persetujuan. "
             "Selesaikan atau batalkan Pindah Dana itu dulu.")
    assert p["bisa_isi_ulang"] is False and p["alasan_isi_ulang"] == pesan
    await _ditolak(pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["BCA"], PEMBUAT), 409, pesan)
    assert await db.fund_transfers.count_documents({"entity_id": pt["id"]}) == 1
    # Kas keluar lagi di sela → nominal isi ulang yang menunggu TIDAK berubah saat disetujui.
    await _kas_manual(pt, "KK", 100_000)
    await _ditolak(fts.setujui(doc["id"], PEMBUAT), 403, dual_control.pesan_tolak("pindah_dana"))
    hasil = await fts.setujui(doc["id"], PENYETUJU)
    assert (hasil["status"], hasil["nominal"], hasil["isi_ulang"]["usulan"]) == ("selesai", 300_000.0, 300_000.0)
    p = await pfs.posisi(pt["rek"]["KK"])
    assert p["isi_ulang_menunggu"] is None and p["usulan_isi_ulang"] == 100_000.0
    # Isi ulang yang menunggu lalu dibatalkan melepas "satu isi ulang terbuka".
    tiga = await pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["BCA"], PEMBUAT)
    assert tiga["status"] == "menunggu_persetujuan"
    await fts.batal(tiga["id"], "salah rekening sumber", PEMBUAT)
    empat = await pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["KB"], PEMBUAT)
    assert (empat["status"], empat["nominal"]) == ("menunggu_persetujuan", 100_000.0)


async def test_KB3_2_U9_dua_isi_ulang_bersamaan_satu_pindah_dana(db, monkeypatch):
    from services import fund_transfer_service as fts
    from services import petty_float_service as pfs
    pt = await _pt()
    await _kas_manual(pt, "KK", 400_000)
    # (a) bersamaan tanpa sela buatan
    hasil = await asyncio.gather(pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["BCA"], PEMBUAT),
                                 pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["BCA"], PENYETUJU), return_exceptions=True)
    ok = [h for h in hasil if isinstance(h, dict)]
    assert len(ok) == 1 and ok[0]["nominal"] == 400_000.0, hasil
    assert all(isinstance(h, HTTPException) and h.status_code in (400, 409) for h in hasil if not isinstance(h, dict))
    assert await db.fund_transfers.count_documents({"entity_id": pt["id"]}) == 1
    # (b) yang kedua datang saat yang pertama sedang menerbitkan Pindah Dana (sela dipaksa) → 409 sedang diproses.
    await _kas_manual(pt, "KK", 150_000)
    asli = fts.buat

    async def lambat(*a, **k):
        await asyncio.sleep(0.05)
        return await asli(*a, **k)
    monkeypatch.setattr(fts, "buat", lambat)
    hasil = await asyncio.gather(pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["BCA"], PEMBUAT),
                                 pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["KB"], PENYETUJU), return_exceptions=True)
    ok = [h for h in hasil if isinstance(h, dict)]
    gagal = [h for h in hasil if not isinstance(h, dict)]
    assert len(ok) == 1 and ok[0]["nominal"] == 150_000.0, hasil
    assert len(gagal) == 1 and isinstance(gagal[0], HTTPException) and gagal[0].status_code == 409
    assert gagal[0].detail == (f"Isi ulang rekening Kas Kecil {pt['kode']} sedang diproses orang lain. Tunggu "
                               "sebentar lalu muat ulang.")
    assert await db.fund_transfers.count_documents({"entity_id": pt["id"]}) == 2
    assert await db.petty_float_locks.count_documents({}) == 0   # kunci dilepas


async def test_KB3_2_U9b_kunci_basi_diambil_alih(db):
    from datetime import datetime, timedelta, timezone
    from services import petty_float_service as pfs
    pt = await _pt()
    await _kas_manual(pt, "KK", 50_000)
    lama = (datetime.now(timezone.utc) - timedelta(seconds=pfs.KUNCI_BASI_DETIK + 5)).isoformat()
    await db.petty_float_locks.insert_one({"_id": pt["rek"]["KK"], "token": "lk_mati", "oleh": "proses mati",
                                           "mulai": lama})
    doc = await pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["BCA"], PEMBUAT)
    assert doc["nominal"] == 50_000.0
    assert await db.petty_float_locks.count_documents({"_id": pt["rek"]["KK"]}) == 0
    # Kunci yang masih segar → 409.
    await db.petty_float_locks.insert_one({"_id": pt["rek"]["KK"], "token": "lk_hidup", "oleh": "orang lain",
                                           "mulai": now_iso()})
    await _kas_manual(pt, "KK", 10_000)
    await _ditolak(pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["BCA"], PEMBUAT), 409)
    await db.petty_float_locks.delete_one({"_id": pt["rek"]["KK"]})


async def test_KB3_2_U10_validasi_400_tanpa_tulisan(db):
    from services import petty_float_service as pfs
    pt, lain = await _pt(dana=0), await _pt()
    nama = f"Kas Kecil {pt['kode']}"
    await _kas_manual(pt, "KK", 100_000)
    await _ditolak(pfs.isi_ulang(pt["rek"]["KK"], pt["rek"]["BCA"], PEMBUAT), 400,
                   f"Rekening {nama} tidak memakai dana tetap. Atur dana tetapnya di Rekening & Saldo dulu.")
    p = await pfs.posisi(pt["rek"]["KK"])
    assert (p["dana_tetap"], p["usulan_isi_ulang"], p["bisa_isi_ulang"]) == (0.0, 0.0, False)
    assert (await pfs.daftar([pt["id"]]))["items"] == [] and (await pfs.daftar([pt["id"]]))["tanpa_dana_tetap"] == 1
    await _ditolak(pfs.posisi(pt["rek"]["BCA"]), 400,
                   f"Rekening BCA {pt['kode']} bukan rekening kas kecil. Dana tetap dan isi ulang hanya untuk rekening "
                   "kas kecil.")
    await _ditolak(pfs.isi_ulang(pt["rek"]["KS"], pt["rek"]["BCA"], PEMBUAT), 400,
                   f"Rekening Kas Kasir 1 {pt['kode']} bukan rekening kas kecil. Dana tetap dan isi ulang hanya untuk "
                   "rekening kas kecil.")
    await _ditolak(pfs.posisi("bank_tidak_ada"), 404, "Rekening tidak ditemukan.")
    await _kas_manual(lain, "KK", 100_000)
    await _ditolak(pfs.isi_ulang(lain["rek"]["KK"], "", PEMBUAT), 400,
                   "Pilih rekening sumber isi ulang: rekening bank atau kas besar PT yang sama.")
    await _ditolak(pfs.isi_ulang(lain["rek"]["KK"], lain["rek"]["KS"], PEMBUAT), 400,
                   f"Rekening sumber Kas Kasir 1 {lain['kode']} bukan rekening bank atau kas besar. Isi ulang kas kecil "
                   "diambil dari rekening bank atau kas besar PT yang sama.")
    await _ditolak(pfs.isi_ulang(lain["rek"]["KK"], "bank_tidak_ada", PEMBUAT), 400, "Rekening sumber tidak ditemukan.")
    await _ditolak(pfs.isi_ulang(lain["rek"]["KK"], pt["rek"]["BCA"], PEMBUAT), 400,
                   "Rekening asal dan tujuan harus milik PT yang sama. Pindah dana antar-PT dicatat lewat menu "
                   "Antar-PT.")
    assert await db.fund_transfers.count_documents({"entity_id": {"$in": [pt["id"], lain["id"]]}}) == 0
    assert await db.petty_float_locks.count_documents({}) == 0


async def test_KB3_2_U11_pindah_dana_biasa_tidak_bisa_bertanda(klien, db, sesi):
    """Tanda `isi_ulang_kas_kecil` hanya dari layanan dana tetap: isian `jenis` di rute Pindah Dana diabaikan."""
    from services import fund_transfer_service as fts
    pt = await _pt()
    h = await sesi("admin@kainnusantara.id", entitas=pt["id"])
    r = await klien.post("/api/fund-transfers", headers=h, json={
        "entity_id": pt["id"], "rekening_asal_id": pt["rek"]["BCA"], "rekening_tujuan_id": pt["rek"]["KK"],
        "nominal": 250_000, "jenis": JENIS, "isi_ulang": {"usulan": 1}})
    assert r.status_code == 200, r.text
    assert (r.json()["jenis"], r.json()["jenis_label"]) == ("", ""), r.json()
    doc = await db.fund_transfers.find_one({"id": r.json()["id"]}, {"_id": 0})
    assert "jenis" not in doc and "isi_ulang" not in doc
    with pytest.raises(ValueError):
        await fts.buat({"entity_id": pt["id"], "rekening_asal_id": pt["rek"]["BCA"],
                        "rekening_tujuan_id": pt["rek"]["KK"], "nominal": 1_000}, PEMBUAT, jenis="tidak_dikenal")
    await _ditolak(fts.buat({"entity_id": pt["id"], "rekening_asal_id": pt["rek"]["BCA"],
                             "rekening_tujuan_id": pt["rek"]["KK"], "nominal": 1_000, "tanggal_terima": "2999-01-01"},
                            PEMBUAT, jenis=JENIS, isi_ulang={}), 400,
                   "Isi ulang kas kecil dicatat sekali jalan: tanggal terima sama dengan tanggal kirim.")


async def test_KB3_2_U12_rute_izin_dan_bentuk(klien, db, akun, sesi, peran_tanpa_acuan):
    pt, lain = await _pt("aktif", "KB32R"), await _pt("lama", "KB32R")
    eid = pt["id"]
    await _kas_manual(pt, "KK", 120_000)
    lihat = await sesi(await akun(await peran_tanpa_acuan({"cash": ["view"]}, label="KB32 Lihat Kas"),
                                  entitas=(eid,)), entitas=eid)
    buat_u = await akun(await peran_tanpa_acuan({"cash": ["view", "create"]}, label="KB32 Buat Kas"), entitas=(eid,))
    buat = await sesi(buat_u, entitas=eid)
    r = await klien.get("/api/kas-kecil/dana-tetap", headers=lihat, params={"entity_id": eid})
    assert r.status_code == 200, r.text
    j = r.json()
    assert [x["account_id"] for x in j["items"]] == [pt["rek"]["KK"]] and j["total"] == 1
    assert j["items"][0]["usulan_isi_ulang"] == 120_000.0
    r = await klien.get(f"/api/kas-kecil/dana-tetap/{pt['rek']['KK']}", headers=lihat)
    assert r.status_code == 200 and r.json()["usulan_isi_ulang"] == 120_000.0, r.text
    assert {k for k in r.json()} >= {"account_id", "account_name", "entity_id", "dana_tetap", "saldo_buku",
                                     "panjar_belum_lpj", "usulan_isi_ulang", "rincian", "total_rincian", "panjar",
                                     "isi_ulang_menunggu", "sejak", "riwayat", "sumber", "bisa_isi_ulang",
                                     "alasan_isi_ulang", "panjar_tanpa_rekening"}
    r = await klien.get(f"/api/kas-kecil/dana-tetap/{pt['rek']['BCA']}", headers=lihat)
    assert r.status_code == 400, r.text
    r = await klien.get("/api/kas-kecil/dana-tetap/bank_tidak_ada", headers=lihat)
    assert r.status_code == 404 and r.json()["detail"] == "Rekening tidak ditemukan.", r.text
    url = f"/api/kas-kecil/dana-tetap/{pt['rek']['KK']}/isi-ulang"
    r = await klien.post(url, headers=lihat, json={"sumber_account_id": pt["rek"]["BCA"]})
    assert r.status_code == 403 and r.headers.get("X-Permission-Denied") == "cash.create", r.text
    r = await klien.post(url, headers=buat, json={"sumber_account_id": pt["rek"]["BCA"], "nominal": 5})
    assert r.status_code == 400 and r.json()["detail"].startswith("Nominal isi ulang dihitung sistem"), r.text
    r = await klien.post(url, headers=buat, json={"sumber_account_id": pt["rek"]["BCA"], "catatan": "uji rute"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["status"], d["nominal"], d["jenis"], d["created_by_id"]) == ("selesai", 120_000.0, JENIS, buat_u["id"])
    assert d["catatan"] == "uji rute" and d["isi_ulang"]["usulan"] == 120_000.0
    # Rekening PT lain: tidak terlihat / tidak bisa diisi ulang.
    await _kas_manual(lain, "KK", 10_000)
    r = await klien.get(f"/api/kas-kecil/dana-tetap/{lain['rek']['KK']}", headers=lihat)
    assert r.status_code in (403, 404), r.text
    r = await klien.post(f"/api/kas-kecil/dana-tetap/{lain['rek']['KK']}/isi-ulang", headers=buat,
                         json={"sumber_account_id": lain["rek"]["BCA"]})
    assert r.status_code in (403, 404), r.text
    r = await klien.get("/api/kas-kecil/dana-tetap", headers=lihat, params={"entity_id": lain["id"]})
    assert r.status_code == 403, r.text
    assert await db.fund_transfers.count_documents({"entity_id": lain["id"]}) == 0

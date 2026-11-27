"""KB-1 Tugas 4 — dokumen Pindah Dana (`fund_transfers`, nomor `PDN-`): pasangan kas, biaya, dalam perjalanan, batal,
kontrol dua orang.

Rancangan: `docs/superpowers/specs/2026-11-27-kas-bank-1-rekening-pindah-dana-design.md` §5.2, §6, §7 butir 4–5, 7.
Ketetapan pengendali Tugas 4: dua tahap = kas keluar asal (Dr 1-1150 / Cr asal; biaya Dr beban bank / Cr asal), lalu
Terima = kas masuk tujuan (Dr tujuan / Cr 1-1150); sekali jalan = kas keluar asal + kas masuk tujuan (`seq` berbeda),
jurnal bersih Dr tujuan / Cr asal; batal membalik SEMUA kas dokumen (ditolak bila salah satunya tercocok mutasi bank),
dokumen yang masih menunggu persetujuan cukup ditandai batal; validasi 400 berkalimat; izin `cash.create` (buat,
terima), `cash.delete` (batal), `cash.approve` (setujui); nomor `PDN-` urut per PT; butir tutup buku "dana dalam
perjalanan"; kirim ulang tidak menggandakan kas.

Uji jalur uang dijalankan di dua PT (`MODE`): `lama` — PT belum memakai akun per rekening (jurnal ke 1-1100 / 1-1110) —
dan `aktif` — PT dinyalakan (`cash_account_mode.nyalakan`) SEBELUM rekening dibuat, jadi tiap rekening lahir dengan
sub-akun sendiri (1-1100-NN / 1-1110-NN) lewat `bank_service.create_account`.
"""
from __future__ import annotations

import asyncio
import itertools
import uuid
from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from pembantu import AKTOR_UJI, pt_uji, saldo_akun

pytestmark = pytest.mark.anyio

PEMBUAT = {"id": "usr_kb4_buat", "name": "Rina Pembuat", "role": "finance", "email": "rina.kb4@uji.id"}
PENYETUJU = {"id": "usr_kb4_setuju", "name": "Dodi Penyetuju", "role": "finance", "email": "dodi.kb4@uji.id"}
TRANSIT, BEBAN_BANK = "1-1150", "6-8000"
_urut = itertools.count(1)


def _kode(awal: str) -> str:
    return f"{awal}{next(_urut)}"


def _hari(geser: int = 0) -> str:
    from services.book_date import tanggal_buku
    return (date.fromisoformat(tanggal_buku()) + timedelta(days=geser)).isoformat()


async def _saldo(kode: str, eid: str) -> float:
    return round(await saldo_akun(kode, eid), 2)


async def _rekening(eid: str, nama: str, jenis_akun: str = "bank", jenis_kas: str = "", awal: float = 0.0) -> str:
    from schemas_finance import BankAccountCreate
    from services import bank_service
    acc = await bank_service.create_account(
        BankAccountCreate(name=nama, account_type=jenis_akun, cash_type=jenis_kas, entity_id=eid,
                          opening_balance=awal), AKTOR_UJI)
    return acc["id"]


async def _pt(mode: str, awal: str = "KB4") -> dict:
    """PT uji baru: BCA (bank, saldo awal 5 jt), MDR (bank), KT (kas tunai berjenis kas besar, saldo awal 2 jt),
    KK (kas kecil). `aktif` → PT dinyalakan lebih dulu (rekening mendapat sub-akun)."""
    from services import cash_account_mode as mode_kas
    from services.entity_lifecycle_service import invalidate_status_cache
    kode = _kode(f"{awal}{'A' if mode == 'aktif' else 'L'}")
    eid = await pt_uji(kode)
    if mode == "aktif":
        await mode_kas.nyalakan(eid, "Uji KB4")
    rek = {"BCA": await _rekening(eid, f"BCA {kode}", awal=5_000_000),
           "MDR": await _rekening(eid, f"Mandiri {kode}"),
           "KT": await _rekening(eid, f"Kas Toko {kode}", "cash", "kas_besar", awal=2_000_000),
           "KK": await _rekening(eid, f"Kas Kecil {kode}", "cash", "kas_kecil")}
    invalidate_status_cache()
    return {"id": eid, "kode": kode, "rek": rek, "mode": mode}


async def _akun_kas(db, pt: dict, nama: str) -> str:
    """Akun buku besar yang SEHARUSNYA dipakai jurnal kas rekening `nama` di PT ini."""
    acc = await db.bank_accounts.find_one({"id": pt["rek"][nama]}, {"_id": 0})
    if pt["mode"] == "aktif":
        assert acc.get("gl_account_code", "").startswith(("1-1100-", "1-1110-")), acc
        return acc["gl_account_code"]
    assert not acc.get("gl_account_code")
    return "1-1110" if acc["cash_type"] == "kas_kecil" else "1-1100"


async def _buku(rid: str) -> float:
    from services import bank_service
    return round((await bank_service.account_ledger(rid))["balance"], 2)


async def _potret(db, pt: dict) -> dict:
    """Saldo tiap akun kas yang dipakai rekening PT (per KODE: di PT lama rekening bank & kas besar berbagi 1-1100),
    transit, beban bank, dan buku kas tiap rekening."""
    out = {}
    for nama in pt["rek"]:
        kode = await _akun_kas(db, pt, nama)
        out[f"akun:{kode}"] = await _saldo(kode, pt["id"])
        out[f"buku:{nama}"] = await _buku(pt["rek"][nama])
    out["transit"] = await _saldo(TRANSIT, pt["id"])
    out["beban"] = await _saldo(BEBAN_BANK, pt["id"])
    return out


def _beda(sebelum: dict, sesudah: dict) -> dict:
    return {k: round(sesudah[k] - sebelum[k], 2) for k in sesudah if round(sesudah[k] - sebelum[k], 2)}


async def _harap(db, pt: dict, rek: dict, *, transit: float = 0.0, beban: float = 0.0) -> dict:
    """Perubahan yang diharapkan dari perubahan buku kas per rekening `rek`: akun kas dijumlah per kode akun (PT lama:
    BCA → Mandiri sama-sama 1-1100), buku kas per rekening, transit, beban bank."""
    out: dict = {}
    for nama, x in rek.items():
        k = f"akun:{await _akun_kas(db, pt, nama)}"
        out[k] = round(out.get(k, 0.0) + x, 2)
        out[f"buku:{nama}"] = x
    out["transit"], out["beban"] = transit, beban
    return {k: v for k, v in out.items() if round(v, 2)}


def _isi(pt: dict, asal: str, tujuan: str, nominal: float, **lain) -> dict:
    return {"entity_id": pt["id"], "rekening_asal_id": pt["rek"][asal], "rekening_tujuan_id": pt["rek"][tujuan],
            "nominal": nominal, **lain}


async def _kas_dokumen(db, doc_id: str) -> dict:
    return {t["seq"]: t async for t in db.cash_transactions.find({"ref_type": "fund_transfer", "ref_id": doc_id},
                                                                  {"_id": 0})}


async def _jurnal_kas(db, kas_id: str) -> list:
    je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": kas_id,
                                            "status": {"$ne": "void"}}, {"_id": 0})
    assert je, kas_id
    return sorted((ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"])


async def _atur(key: str, nilai, eid: str) -> None:
    from services import config_resolver as resolver
    await resolver.set_value(key, nilai, scope_type="entity", scope_id=eid, reason="uji KB4 kontrol", actor="uji")


async def _ditolak(coro, status: int, pesan: str = "") -> HTTPException:
    with pytest.raises(HTTPException) as e:
        await coro
    assert e.value.status_code == status, e.value.detail
    if pesan:
        assert e.value.detail == pesan, e.value.detail
    return e.value


MODE = ["lama", "aktif"]


# ═══ 1. Sekali jalan: kas keluar asal + biaya + kas masuk tujuan; jurnal lewat akun_kas ═════════════════════════════
@pytest.mark.parametrize("mode,tujuan", [("lama", "KK"), ("aktif", "KK"), ("aktif", "MDR")])
async def test_KB1_4_U1_sekali_jalan_pasangan_kas_dan_biaya(db, mode, tujuan):
    from services import fund_transfer_service as fts
    pt = await _pt(mode)
    sebelum = await _potret(db, pt)
    doc = await fts.buat(_isi(pt, "BCA", tujuan, 1_000_000, biaya=6_500, catatan="isi kas"), PEMBUAT)
    assert doc["status"] == "selesai" and doc["status_label"] == "Selesai"
    assert doc["number"] == f"{pt['kode']}/PDN-00001" and doc["dua_tahap"] is False
    assert (doc["nominal"], doc["biaya"], doc["butuh_persetujuan"]) == (1_000_000.0, 6_500.0, False)
    assert doc["tanggal_kirim"] == doc["tanggal_terima"] == doc["tanggal_diterima"] == _hari()
    kas = await _kas_dokumen(db, doc["id"])
    assert sorted(kas) == ["biaya", "kirim", "terima"]
    assert {s: (t["direction"], t["amount"], t["account_id"], t["status"]) for s, t in kas.items()} == {
        "kirim": ("out", 1_000_000.0, pt["rek"]["BCA"], "posted"),
        "biaya": ("out", 6_500.0, pt["rek"]["BCA"], "posted"),
        "terima": ("in", 1_000_000.0, pt["rek"][tujuan], "posted")}
    assert len({t["id"] for t in kas.values()}) == 3 and all(t["gl_status"] == "posted" for t in kas.values())
    asal_akun, tujuan_akun = await _akun_kas(db, pt, "BCA"), await _akun_kas(db, pt, tujuan)
    assert asal_akun != tujuan_akun
    assert await _jurnal_kas(db, kas["kirim"]["id"]) == sorted([(TRANSIT, 1_000_000.0, 0.0),
                                                                (asal_akun, 0.0, 1_000_000.0)])
    assert await _jurnal_kas(db, kas["biaya"]["id"]) == sorted([(BEBAN_BANK, 6_500.0, 0.0), (asal_akun, 0.0, 6_500.0)])
    assert await _jurnal_kas(db, kas["terima"]["id"]) == sorted([(tujuan_akun, 1_000_000.0, 0.0),
                                                                 (TRANSIT, 0.0, 1_000_000.0)])
    # Jurnal bersih: Dr tujuan / Cr asal, Dr beban bank / Cr asal; transit kembali nol; buku kas rekening ikut.
    assert _beda(sebelum, await _potret(db, pt)) == await _harap(db, pt, {"BCA": -1_006_500.0, tujuan: 1_000_000.0},
                                                                beban=6_500.0)
    if mode == "aktif":   # sub-akun rekening = buku kas rekening itu
        for nama in pt["rek"]:
            assert await _saldo(await _akun_kas(db, pt, nama), pt["id"]) == await _buku(pt["rek"][nama]), nama
    assert doc["gl_status"] == "posted" and doc["kas_ids"] == {s: t["id"] for s, t in kas.items()}
    r = await fts.rincian(doc["id"])
    assert [k["seq"] for k in r["kas"]] == ["kirim", "biaya", "terima"]
    assert all(k["journal_number"] for k in r["kas"]) and r["kas"][0]["peran"] == "Kas keluar rekening asal"
    assert [j["aksi"] for j in r["jejak"]] == ["buat", "terbit"]
    from services.cash_ledger import REF_LABEL
    assert REF_LABEL["fund_transfer"] == "Pindah Dana"


async def test_KB1_4_U1b_tanpa_biaya_dua_kas(db):
    from services import fund_transfer_service as fts
    pt = await _pt("lama")
    doc = await fts.buat(_isi(pt, "KT", "BCA", 750_000, tanggal_kirim=_hari(), tanggal_terima=_hari()), PEMBUAT)
    assert doc["status"] == "selesai" and sorted(await _kas_dokumen(db, doc["id"])) == ["kirim", "terima"]
    assert "biaya" not in doc["kas_ids"]


# ═══ 2. Dua tahap lewat 1-1150 + Terima ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("mode", MODE)
async def test_KB1_4_U2_dua_tahap_lewat_transit_lalu_terima(db, mode):
    from services import fund_transfer_service as fts
    pt = await _pt(mode)
    sebelum = await _potret(db, pt)
    doc = await fts.buat(_isi(pt, "BCA", "MDR", 2_000_000, biaya=5_000, tanggal_kirim=_hari(-1),
                              tanggal_terima=_hari()), PEMBUAT)
    assert (doc["status"], doc["status_label"], doc["dua_tahap"]) == ("dalam_perjalanan", "Dalam perjalanan", True)
    assert doc["tanggal_diterima"] == "" and doc["tanggal_terima"] == _hari()
    kas = await _kas_dokumen(db, doc["id"])
    assert sorted(kas) == ["biaya", "kirim"] and kas["kirim"]["txn_date"][:10] == _hari(-1)
    tengah = await _potret(db, pt)
    assert _beda(sebelum, tengah) == await _harap(db, pt, {"BCA": -2_005_000.0}, transit=2_000_000.0, beban=5_000.0)
    # Tanggal terima sebelum tanggal kirim → 400, tidak ada kas masuk
    await _ditolak(fts.terima(doc["id"], _hari(-2), PEMBUAT), 400, "Tanggal terima tidak boleh sebelum tanggal kirim.")
    hasil = await fts.terima(doc["id"], _hari(), PEMBUAT)
    assert (hasil["status"], hasil["tanggal_diterima"], hasil["diterima_oleh"]) == ("selesai", _hari(), PEMBUAT["name"])
    kas = await _kas_dokumen(db, doc["id"])
    assert sorted(kas) == ["biaya", "kirim", "terima"] and kas["terima"]["txn_date"][:10] == _hari()
    mdr = await _akun_kas(db, pt, "MDR")
    assert await _jurnal_kas(db, kas["terima"]["id"]) == sorted([(mdr, 2_000_000.0, 0.0), (TRANSIT, 0.0, 2_000_000.0)])
    assert _beda(sebelum, await _potret(db, pt)) == await _harap(db, pt, {"BCA": -2_005_000.0, "MDR": 2_000_000.0},
                                                                beban=5_000.0)
    # Terima ulang (kirim ulang) → 409, kas masuk tetap satu
    await _ditolak(fts.terima(doc["id"], _hari(), PEMBUAT), 409, f"Pindah Dana {doc['number']} sudah diterima.")
    assert await db.cash_transactions.count_documents({"ref_type": "fund_transfer", "ref_id": doc["id"]}) == 3
    assert [j["aksi"] for j in (await fts.rincian(doc["id"]))["jejak"]] == ["buat", "terbit", "terima"]


async def test_KB1_4_U2b_terima_tanpa_tanggal_pakai_rencana_dan_bersamaan_satu_kas(db):
    from services import fund_transfer_service as fts
    pt = await _pt("aktif")
    doc = await fts.buat(_isi(pt, "BCA", "KK", 300_000, tanggal_kirim=_hari(-1), tanggal_terima=_hari()), PEMBUAT)
    hasil = await asyncio.gather(fts.terima(doc["id"], "", PEMBUAT), fts.terima(doc["id"], "", PENYETUJU),
                                 return_exceptions=True)
    ok = [h for h in hasil if isinstance(h, dict)]
    assert len(ok) == 1 and ok[0]["tanggal_diterima"] == _hari(), hasil
    assert all(isinstance(h, HTTPException) and h.status_code == 409 for h in hasil if not isinstance(h, dict))
    kas = [t async for t in db.cash_transactions.find({"ref_type": "fund_transfer", "ref_id": doc["id"],
                                                       "direction": "in"}, {"_id": 0})]
    assert len(kas) == 1


# ═══ 3. Batal dua tahap sebelum diterima → kas keluar & biaya dibalik, transit kembali nol (Review Focus 4) ═══════════
@pytest.mark.parametrize("mode", MODE)
async def test_KB1_4_U3_batal_dalam_perjalanan_transit_nol(db, mode):
    from services import fund_transfer_service as fts
    pt = await _pt(mode)
    sebelum = await _potret(db, pt)
    doc = await fts.buat(_isi(pt, "KT", "BCA", 1_500_000, biaya=2_500, tanggal_kirim=_hari(-1),
                              tanggal_terima=_hari(1)), PEMBUAT)
    assert doc["status"] == "dalam_perjalanan"
    await _ditolak(fts.batal(doc["id"], " slh ", PEMBUAT), 400, "Alasan pembatalan wajib diisi (minimal 5 huruf).")
    hasil = await fts.batal(doc["id"], "salah rekening tujuan", PEMBUAT)
    assert (hasil["status"], hasil["alasan_batal"], hasil["dibatalkan_oleh"]) == ("batal", "salah rekening tujuan",
                                                                                 PEMBUAT["name"])
    assert hasil["batal_gl_status"] == "posted"
    kas = await _kas_dokumen(db, doc["id"])
    assert sorted(kas) == ["biaya", "kirim"] and all(t["status"] == "void" for t in kas.values())
    for t in kas.values():
        rev = await db.journal_entries.count_documents({"source_type": "cash_transaction_void", "source_id": t["id"],
                                                        "status": {"$ne": "void"}})
        assert rev == 1 and t["void_journal_entry_id"], t
    assert _beda(sebelum, await _potret(db, pt)) == {}   # transit, beban, asal, tujuan: kembali seperti semula
    assert await _saldo(TRANSIT, pt["id"]) == 0.0
    # Sesudah batal: terima ditolak, tidak ada kas masuk; batal lagi ditolak
    await _ditolak(fts.terima(doc["id"], _hari(1), PEMBUAT), 409, f"Pindah Dana {doc['number']} sudah dibatalkan.")
    await _ditolak(fts.batal(doc["id"], "batal kedua kali", PEMBUAT), 409,
                   f"Pindah Dana {doc['number']} sudah dibatalkan.")
    assert await db.cash_transactions.count_documents({"ref_type": "fund_transfer", "ref_id": doc["id"]}) == 2


# ═══ 4. Batal sekali jalan ditolak bila kas tercocok mutasi bank; lepas → batal membalik ketiga kas ═════════════════
def _mutasi(lid: str, pt: dict, rekening: str, nominal: float, arah: str) -> dict:
    from core_utils import now_iso
    return {"id": lid, "bank_account_id": pt["rek"][rekening], "entity_id": pt["id"], "stmt_date": _hari(),
            "amount": float(nominal), "direction": arah, "description": f"mutasi uji KB4 {lid}", "counterparty": "",
            "desc_key": "", "ref": "", "external_id": lid, "balance": 0.0, "status": "unmatched", "match_kind": "",
            "matched_txn_id": "", "matched_txn_ids": [], "allocations": [], "score": 0, "score_explain": [],
            "suggestions": [], "match_type": "", "matched_at": "", "matched_by": "", "holding": {},
            "holding_allocated": [], "holding_remaining": 0.0, "import_batch": "kb4", "format_id": "",
            "created_at": now_iso(), "updated_at": now_iso()}


@pytest.mark.parametrize("mode", MODE)
async def test_KB1_4_U4_batal_ditolak_bila_tercocok_lalu_dibalik_semua(db, mode):
    from services import bank_recon_service as brs
    from services import fund_transfer_service as fts
    pt = await _pt(mode)
    sebelum = await _potret(db, pt)
    doc = await fts.buat(_isi(pt, "BCA", "MDR", 400_000, biaya=2_900), PEMBUAT)
    kas = await _kas_dokumen(db, doc["id"])
    # Rekonsiliasi: kas Pindah Dana tercocok seperti kas lain, di sisi asal (keluar) dan tujuan (masuk)
    l_out, l_in = f"stl_kb4_{uuid.uuid4().hex[:8]}", f"stl_kb4_{uuid.uuid4().hex[:8]}"
    await db.bank_statement_lines.insert_many([_mutasi(l_out, pt, "BCA", 400_000, "out"),
                                               _mutasi(l_in, pt, "MDR", 400_000, "in")])
    await brs.manual_match(l_out, kas["kirim"]["id"], "Uji KB4", None)
    await brs.manual_match(l_in, kas["terima"]["id"], "Uji KB4", None)
    for s in ("kirim", "terima"):
        t = await db.cash_transactions.find_one({"id": kas[s]["id"]}, {"_id": 0})
        assert t["reconciled_amount"] == 400_000.0, t
    await _ditolak(fts.batal(doc["id"], "dobel dicatat", PEMBUAT), 409,
                   f"Kas {kas['kirim']['number']} dari Pindah Dana {doc['number']} sudah dicocokkan dengan mutasi "
                   "bank — lepas dulu di Rekonsiliasi, lalu batalkan.")
    fresh = await fts.rincian(doc["id"])
    assert fresh["status"] == "selesai" and all(k["status"] == "posted" for k in fresh["kas"])
    await brs.unmatch(l_out, "Uji KB4", None)
    e = await _ditolak(fts.batal(doc["id"], "dobel dicatat", PEMBUAT), 409)
    assert kas["terima"]["number"] in e.detail and "lepas dulu di Rekonsiliasi" in e.detail
    await brs.unmatch(l_in, "Uji KB4", None)
    hasil = await fts.batal(doc["id"], "dobel dicatat", PEMBUAT)
    assert hasil["status"] == "batal" and hasil["batal_gl_status"] == "posted"
    kas = await _kas_dokumen(db, doc["id"])
    assert sorted(kas) == ["biaya", "kirim", "terima"] and all(t["status"] == "void" for t in kas.values())
    assert _beda(sebelum, await _potret(db, pt)) == {}


# ═══ 5. Validasi → 400 berkalimat, tanpa tulisan ═════════════════════════════════════════════════════════════════════
async def test_KB1_4_U5_validasi_400_tanpa_tulisan(db):
    from services import fund_transfer_service as fts
    pt, lain = await _pt("lama"), await _pt("lama")
    await db.bank_accounts.update_one({"id": pt["rek"]["MDR"]}, {"$set": {"is_active": False}})
    pt_nama = f"Uji {pt['kode'].upper()}"
    sebelum = (await db.fund_transfers.count_documents({}), await db.cash_transactions.count_documents({}),
               await db.journal_entries.count_documents({}))
    kasus = [
        ({**_isi(pt, "BCA", "BCA", 100_000)}, "Rekening asal dan tujuan tidak boleh sama."),
        ({**_isi(pt, "BCA", "KK", 100_000), "rekening_tujuan_id": lain["rek"]["BCA"]},
         "Rekening asal dan tujuan harus milik PT yang sama. Pindah dana antar-PT dicatat lewat menu Antar-PT."),
        ({**_isi(lain, "BCA", "KK", 100_000), "entity_id": pt["id"]}, f"Rekening BCA {lain['kode']} bukan rekening "
                                                                      f"{pt_nama}."),
        (_isi(pt, "BCA", "MDR", 100_000), f"Rekening Mandiri {pt['kode']} tidak aktif. Aktifkan dulu di Rekening & "
                                          "Saldo atau pilih rekening lain."),
        (_isi(pt, "MDR", "BCA", 100_000), f"Rekening Mandiri {pt['kode']} tidak aktif. Aktifkan dulu di Rekening & "
                                          "Saldo atau pilih rekening lain."),
        (_isi(pt, "BCA", "KK", 0), "Nominal pindah dana harus lebih dari 0."),
        (_isi(pt, "BCA", "KK", -5_000), "Nominal pindah dana harus lebih dari 0."),
        (_isi(pt, "BCA", "KK", 100_000, biaya=-1), "Biaya transfer tidak boleh negatif."),
        (_isi(pt, "BCA", "KK", 100_000, tanggal_kirim=_hari(), tanggal_terima=_hari(-1)),
         "Tanggal terima tidak boleh sebelum tanggal kirim."),
        ({**_isi(pt, "BCA", "KK", 100_000), "rekening_asal_id": "bank_tidak_ada"}, "Rekening asal tidak ditemukan."),
        ({**_isi(pt, "BCA", "KK", 100_000), "rekening_tujuan_id": ""}, "Pilih rekening asal dan rekening tujuan."),
        (_isi(pt, "BCA", "KK", 100_000, tanggal_kirim="27/11/2026"), "Tanggal kirim tidak dikenali: 27/11/2026."),
    ]
    for isi, pesan in kasus:
        await _ditolak(fts.buat(isi, PEMBUAT), 400, pesan)
    assert sebelum == (await db.fund_transfers.count_documents({}), await db.cash_transactions.count_documents({}),
                       await db.journal_entries.count_documents({}))


async def test_KB1_4_U5b_periode_tutup_409_tanpa_tulisan(db):
    from pembantu import tutup_periode
    from services import fund_transfer_service as fts
    pt = await _pt("lama")
    lalu = (date.fromisoformat(_hari()).replace(day=1) - timedelta(days=1))
    c = await tutup_periode(pt["id"], lalu.isoformat()[:7])
    try:
        sebelum = await db.fund_transfers.count_documents({"entity_id": pt["id"]})
        e = await _ditolak(fts.buat(_isi(pt, "BCA", "KK", 10_000, tanggal_kirim=lalu.isoformat()), PEMBUAT), 409)
        assert "tutup" in e.detail.lower() or "tertutup" in e.detail.lower(), e.detail
        assert await db.fund_transfers.count_documents({"entity_id": pt["id"]}) == sebelum
    finally:
        await db.period_closings.delete_one({"id": c["id"]})


# ═══ 6. Kontrol dua orang: kas belum terbit sampai disetujui orang lain ══════════════════════════════════════════════
@pytest.mark.parametrize("mode", MODE)
async def test_KB1_4_U6_kontrol_dua_orang(db, mode):
    from services import dual_control
    from services import fund_transfer_service as fts
    pt = await _pt(mode)
    await _atur("kontrol.pindah_dana.min_orang", "2", pt["id"])
    sebelum = await _potret(db, pt)
    doc = await fts.buat(_isi(pt, "BCA", "KK", 250_000, biaya=1_000), PEMBUAT)
    assert (doc["status"], doc["status_label"], doc["butuh_persetujuan"]) == (
        "menunggu_persetujuan", "Menunggu persetujuan", True)
    assert await db.cash_transactions.count_documents({"ref_type": "fund_transfer", "ref_id": doc["id"]}) == 0
    assert _beda(sebelum, await _potret(db, pt)) == {}
    await _ditolak(fts.terima(doc["id"], "", PEMBUAT), 409,
                   f"Pindah Dana {doc['number']} belum disetujui, jadi belum bisa diterima.")
    await _ditolak(fts.setujui(doc["id"], PEMBUAT), 403, dual_control.pesan_tolak("pindah_dana"))
    assert await db.cash_transactions.count_documents({"ref_type": "fund_transfer", "ref_id": doc["id"]}) == 0
    hasil = await fts.setujui(doc["id"], PENYETUJU)
    assert (hasil["status"], hasil["disetujui_oleh"]) == ("selesai", PENYETUJU["name"])
    assert sorted(await _kas_dokumen(db, doc["id"])) == ["biaya", "kirim", "terima"]
    assert _beda(sebelum, await _potret(db, pt)) == await _harap(db, pt, {"BCA": -251_000.0, "KK": 250_000.0},
                                                                beban=1_000.0)
    await _ditolak(fts.setujui(doc["id"], PENYETUJU), 409,
                   f"Pindah Dana {doc['number']} berstatus Selesai, jadi tidak bisa disetujui.")
    assert await db.cash_transactions.count_documents({"ref_type": "fund_transfer", "ref_id": doc["id"]}) == 3
    assert [j["aksi"] for j in (await fts.rincian(doc["id"]))["jejak"]] == ["buat", "setujui", "terbit"]
    # Menunggu persetujuan → batal cukup menandai batal (tanpa kas)
    dua = await fts.buat(_isi(pt, "BCA", "KK", 100_000), PEMBUAT)
    assert dua["status"] == "menunggu_persetujuan"
    b = await fts.batal(dua["id"], "tidak jadi dipindah", PEMBUAT)
    assert (b["status"], b["batal_gl_status"]) == ("batal", "")
    assert await db.cash_transactions.count_documents({"ref_type": "fund_transfer", "ref_id": dua["id"]}) == 0
    await _ditolak(fts.setujui(dua["id"], PENYETUJU), 409, f"Pindah Dana {dua['number']} sudah dibatalkan.")


async def test_KB1_4_U6b_batas_nominal_dan_setujui_bersamaan(db):
    from services import fund_transfer_service as fts
    pt = await _pt("lama")
    await _atur("kontrol.pindah_dana.batas_nominal", 5_000_000, pt["id"])
    kecil = await fts.buat(_isi(pt, "BCA", "MDR", 4_000_000), PEMBUAT)
    besar = await fts.buat(_isi(pt, "BCA", "MDR", 5_000_001, tanggal_kirim=_hari(), tanggal_terima=_hari(2)), PEMBUAT)
    assert (kecil["status"], besar["status"]) == ("selesai", "menunggu_persetujuan")
    hasil = await asyncio.gather(fts.setujui(besar["id"], PENYETUJU), fts.setujui(besar["id"], PENYETUJU),
                                 return_exceptions=True)
    ok = [h for h in hasil if isinstance(h, dict)]
    assert len(ok) == 1 and ok[0]["status"] == "dalam_perjalanan", hasil
    assert all(isinstance(h, HTTPException) and h.status_code == 409 for h in hasil if not isinstance(h, dict))
    assert sorted(await _kas_dokumen(db, besar["id"])) == ["kirim"]


# ═══ 7. Nomor PDN- urut per PT, unik ═════════════════════════════════════════════════════════════════════════════════
async def test_KB1_4_U7_nomor_urut_per_pt(db):
    import doc_number_kinds as dnk
    import indexes
    from services import fund_transfer_service as fts
    a, b = await _pt("lama", "KB4N"), await _pt("aktif", "KB4N")
    n1 = (await fts.buat(_isi(a, "BCA", "KK", 10_000), PEMBUAT))["number"]
    n2 = (await fts.buat(_isi(a, "KT", "MDR", 20_000, tanggal_terima=_hari(3)), PEMBUAT))["number"]
    n3 = (await fts.buat(_isi(b, "BCA", "KK", 30_000), PEMBUAT))["number"]
    assert (n1, n2, n3) == (f"{a['kode']}/PDN-00001", f"{a['kode']}/PDN-00002", f"{b['kode']}/PDN-00001")
    assert ("fund_transfers", "number") in indexes.UNIQUE_DOC_NUMBER_FIELDS
    assert dnk.lookup("fund_transfers", "number", "PDN-", "per_entity_prefix", "")[0]["kind"] == "pdn"


# ═══ 8. Butir tutup buku: dana dalam perjalanan ═════════════════════════════════════════════════════════════════════
async def test_KB1_4_U8_butir_tutup_buku_dana_dalam_perjalanan(db):
    from services import closing_checklist as ceklis
    from services import fund_transfer_service as fts
    pt = await _pt("aktif")
    bulan = _hari()[:7]

    async def _butir():
        j = await ceklis.build("month", bulan, pt["id"])
        return next(it for it in j["items"] if it["key"] == "dana_dalam_perjalanan")

    nol = await _butir()
    assert (nol["status"], nol["value"], nol["rincian"]["jumlah"], nol["rincian"]["total"]) == ("ok", 0, 0, 0.0)
    assert nol["link"] == {"view": "fund-transfers", "preset": {"status": "dalam_perjalanan"}}
    jalan = await fts.buat(_isi(pt, "BCA", "MDR", 900_000, biaya=4_000, tanggal_kirim=_hari(-1),
                                tanggal_terima=_hari()), PEMBUAT)
    await fts.buat(_isi(pt, "BCA", "KK", 50_000), PEMBUAT)                       # sekali jalan: tidak dihitung
    batal = await fts.buat(_isi(pt, "KT", "MDR", 70_000, tanggal_kirim=_hari(-1), tanggal_terima=_hari()), PEMBUAT)
    await fts.batal(batal["id"], "uji butir tutup buku", PEMBUAT)              # dibatalkan: tidak dihitung
    it = await _butir()
    assert it["status"] == "warning", it
    assert it["value"] == 1 and it["rincian"] == {"jumlah": 1, "total": 900_000.0, "saldo_akun": 900_000.0,
                                                  "nomor": [jalan["number"]]}, it
    assert jalan["number"] in it["detail"] and "Rp 900.000" in it["detail"], it["detail"]
    await fts.terima(jalan["id"], _hari(), PEMBUAT)
    it = await _butir()
    assert (it["status"], it["value"], it["rincian"]) == (
        "ok", 0, {"jumlah": 0, "total": 0.0, "saldo_akun": 0.0, "nomor": []}), it
    # Satu sisi kas manual "Transfer" lama tanpa pasangannya → saldo akun transit ≠ 0 → tetap diperingatkan
    from services import cash_ledger
    await cash_ledger.create_cash(entity_id=pt["id"], direction="out", amount=25_000, ref_type="manual",
                                  ref_id=f"kb4_trf_{uuid.uuid4().hex[:8]}", account_id=pt["rek"]["KT"],
                                  category="transfer", description="setor ke bank (satu sisi)", actor="Uji")
    it = await _butir()
    assert (it["status"], it["value"], it["rincian"]["saldo_akun"]) == ("warning", 0, 25_000.0), it
    assert it["detail"].startswith("Saldo akun dana dalam perjalanan per ") and "Rp 25.000" in it["detail"], it


# ═══ 9. Jurnal kas gagal → dokumen tetap berjalan (Posting Gagal); pembalik gagal saat batal → diteruskan ══════════
async def test_KB1_4_U9_jurnal_gagal_dan_batal_diteruskan(db, paksa_jurnal_gagal):
    from services import fund_transfer_service as fts
    from services import posting_registry as reg
    pt = await _pt("aktif")
    sebelum = await _potret(db, pt)
    async with paksa_jurnal_gagal("sisip", entity_id=pt["id"], source_type="cash_transaction", kali=1):
        doc = await fts.buat(_isi(pt, "BCA", "MDR", 600_000, biaya=3_000), PEMBUAT)
    assert doc["status"] == "selesai" and doc["gl_status"] == "failed" and doc["gl_error"], doc
    kas = await _kas_dokumen(db, doc["id"])
    gagal = [t for t in kas.values() if t["gl_status"] == "failed"]
    assert len(gagal) == 1 and gagal[0]["seq"] == "kirim"
    await reg.KINDS["cash_transaction"]["retry"](gagal[0], AKTOR_UJI)
    assert (await fts.rincian(doc["id"]))["gl_status"] == "posted"
    # Pembalik kas gagal di tengah batal → dokumen batal, `batal_gl_status: failed`, di Posting Gagal; ulang tuntas
    async with paksa_jurnal_gagal("sisip", entity_id=pt["id"], source_type="cash_transaction_void", kali=1):
        e = await _ditolak(fts.batal(doc["id"], "uji pembalik gagal", PEMBUAT), 409)
    assert "sudah dibatalkan, tetapi jurnal pembalik kas" in e.detail and "Posting Gagal" in e.detail, e.detail
    d = await db.fund_transfers.find_one({"id": doc["id"]}, {"_id": 0})
    assert (d["status"], d["batal_gl_status"]) == ("batal", "failed") and d["batal_gl_error"]
    spec = reg.KINDS["fund_transfer_cancel"]
    assert await db[spec["collection"]].count_documents({**spec["failed_query"], "id": doc["id"]}) == 1
    await _ditolak(fts.terima(doc["id"], "", PEMBUAT), 409)
    await spec["retry"](d, AKTOR_UJI)
    d = await db.fund_transfers.find_one({"id": doc["id"]}, {"_id": 0})
    assert d["batal_gl_status"] == "posted"
    assert all(t["status"] == "void" for t in (await _kas_dokumen(db, doc["id"])).values())
    assert _beda(sebelum, await _potret(db, pt)) == {}


# ═══ 10. Batal bersamaan → satu pembalik per kas ═════════════════════════════════════════════════════════════════════
async def test_KB1_4_U10_batal_bersamaan_satu_pembalik(db):
    from services import fund_transfer_service as fts
    pt = await _pt("lama")
    doc = await fts.buat(_isi(pt, "BCA", "KK", 120_000, biaya=1_500), PEMBUAT)
    hasil = await asyncio.gather(fts.batal(doc["id"], "klik ganda batal", PEMBUAT),
                                 fts.batal(doc["id"], "klik ganda batal", PEMBUAT), return_exceptions=True)
    assert len([h for h in hasil if isinstance(h, dict)]) == 1, hasil
    assert all(isinstance(h, HTTPException) and h.status_code == 409 for h in hasil if not isinstance(h, dict))
    for t in (await _kas_dokumen(db, doc["id"])).values():
        assert t["status"] == "void"
        assert await db.journal_entries.count_documents({"source_type": "cash_transaction_void",
                                                         "source_id": t["id"], "status": {"$ne": "void"}}) == 1


# ═══ 11. Rute: bentuk jawaban, izin, cakupan PT; kas Pindah Dana tidak bisa dibatalkan dari Transaksi Kas ═══════════
async def test_KB1_4_U11_rute_izin_dan_bentuk(klien, db, akun, sesi, kepala_admin, peran_tanpa_acuan):
    pt, lain = await _pt("aktif", "KB4R"), await _pt("lama", "KB4R")
    eid = pt["id"]
    lihat = await sesi(await akun(await peran_tanpa_acuan({"cash": ["view"]}, label="KB4 Lihat Kas"),
                                  entitas=(eid,)), entitas=eid)
    buat_u = await akun(await peran_tanpa_acuan({"cash": ["view", "create"]}, label="KB4 Buat Kas"), entitas=(eid,))
    buat = await sesi(buat_u, entitas=eid)
    setuju = await sesi(await akun(await peran_tanpa_acuan({"cash": ["view", "approve"]}, label="KB4 Setujui Kas"),
                                   entitas=(eid,)), entitas=eid)
    hapus = await sesi(await akun(await peran_tanpa_acuan({"cash": ["view", "delete"]}, label="KB4 Batal Kas"),
                                  entitas=(eid,)), entitas=eid)
    isi = {"entity_id": eid, "rekening_asal_id": pt["rek"]["BCA"], "rekening_tujuan_id": pt["rek"]["MDR"],
           "nominal": 500_000, "biaya": 2_500, "tanggal_kirim": _hari(-1), "tanggal_terima": _hari(),
           "catatan": "uji rute"}
    r = await klien.post("/api/fund-transfers", headers=lihat, json=isi)
    assert r.status_code == 403 and r.headers.get("X-Permission-Denied") == "cash.create", r.text
    r = await klien.post("/api/fund-transfers", headers=buat, json={**isi, "nominal": 0})
    assert r.status_code == 400 and r.json()["detail"] == "Nominal pindah dana harus lebih dari 0."
    r = await klien.post("/api/fund-transfers", headers=buat, json={**isi, "biaya": -1})
    assert r.status_code == 422, r.text   # INV-NUM-01: nominal negatif ditolak skema
    r = await klien.post("/api/fund-transfers", headers=buat, json={**isi, "entity_id": lain["id"]})
    assert r.status_code == 403, r.text   # PT di luar penugasan
    r = await klien.post("/api/fund-transfers", headers=buat, json=isi)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["status"] == "dalam_perjalanan" and doc["created_by_id"] == buat_u["id"]
    tid = doc["id"]
    r = await klien.get("/api/fund-transfers", headers=lihat, params={"status": "dalam_perjalanan"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert {k for k in j} >= {"items", "total", "page", "page_size", "has_more", "statuses"}
    assert [x["id"] for x in j["items"]] == [tid] and j["items"][0]["rekening_asal"] == f"BCA {pt['kode']}"
    assert [s["value"] for s in j["statuses"]] == ["menunggu_persetujuan", "dalam_perjalanan", "selesai", "batal"]
    r = await klien.get("/api/fund-transfers", headers=lihat, params={"q": doc["number"]})
    assert [x["id"] for x in r.json()["items"]] == [tid]
    r = await klien.get(f"/api/fund-transfers/{tid}", headers=lihat)
    assert r.status_code == 200 and [k["seq"] for k in r.json()["kas"]] == ["kirim", "biaya"]
    assert r.json()["kontrol"]["dua_orang"] is False
    r = await klien.get("/api/fund-transfers/pdn_tidak_ada", headers=lihat)
    assert r.status_code == 404 and r.json()["detail"] == "Pindah Dana tidak ditemukan."
    # Kas Pindah Dana tidak bisa dibatalkan dari layar Transaksi Kas
    kas_kirim = doc["kas_ids"]["kirim"]
    r = await klien.post(f"/api/cash-transactions/{kas_kirim}/void", headers={**kepala_admin, "X-Entity-Id": eid},
                         json={"reason": "uji batal dari kas"})
    assert r.status_code == 409 and r.json()["detail"] == (
        "Transaksi kas ini berasal dari dokumen Pindah Dana — batalkan lewat dokumen asalnya."), r.text
    # Terima: cash.create
    r = await klien.post(f"/api/fund-transfers/{tid}/receive", headers=lihat, json={"tanggal": _hari()})
    assert r.status_code == 403 and r.headers.get("X-Permission-Denied") == "cash.create"
    r = await klien.post(f"/api/fund-transfers/{tid}/receive", headers=buat, json={"tanggal": _hari()})
    assert r.status_code == 200 and r.json()["status"] == "selesai", r.text
    # Batal: cash.delete
    r = await klien.post(f"/api/fund-transfers/{tid}/cancel", headers=buat, json={"alasan": "uji rute batal"})
    assert r.status_code == 403 and r.headers.get("X-Permission-Denied") == "cash.delete"
    r = await klien.post(f"/api/fund-transfers/{tid}/cancel", headers=hapus, json={"alasan": "uji"})
    assert r.status_code == 400 and r.json()["detail"] == "Alasan pembatalan wajib diisi (minimal 5 huruf)."
    r = await klien.post(f"/api/fund-transfers/{tid}/cancel", headers=hapus, json={"alasan": "uji rute batal"})
    assert r.status_code == 200 and r.json()["status"] == "batal", r.text
    # Setujui: cash.approve; pembuat tidak menyetujui sendiri saat kontrol dua orang
    await _atur("kontrol.pindah_dana.min_orang", "2", eid)
    r = await klien.post("/api/fund-transfers", headers=buat, json={**isi, "tanggal_terima": ""})
    assert r.status_code == 200 and r.json()["status"] == "menunggu_persetujuan", r.text
    tid2 = r.json()["id"]
    r = await klien.post(f"/api/fund-transfers/{tid2}/approve", headers=buat)
    assert r.status_code == 403 and r.headers.get("X-Permission-Denied") == "cash.approve"
    r = await klien.get(f"/api/fund-transfers/{tid2}", headers=setuju)
    assert r.json()["kontrol"]["dua_orang"] is True and r.json()["kontrol"]["ditolak"] is False
    r = await klien.post(f"/api/fund-transfers/{tid2}/approve", headers=setuju)
    assert r.status_code == 200 and r.json()["status"] == "selesai", r.text
    # Dokumen PT lain: tidak terlihat / tidak bisa diubah
    from services import fund_transfer_service as fts
    asing = await fts.buat(_isi(lain, "BCA", "KK", 10_000), PEMBUAT)
    r = await klien.get(f"/api/fund-transfers/{asing['id']}", headers=lihat)
    assert r.status_code in (403, 404), r.text
    r = await klien.post(f"/api/fund-transfers/{asing['id']}/cancel", headers=hapus, json={"alasan": "uji PT lain"})
    assert r.status_code in (403, 404), r.text
    assert (await db.fund_transfers.find_one({"id": asing["id"]}, {"_id": 0}))["status"] == "selesai"


async def test_KB1_4_U5c_akun_beban_bank_nonaktif_409_tanpa_tulisan(db):
    from pembantu import aktifkan_akun, nonaktifkan_akun
    from services import fund_transfer_service as fts
    pt = await _pt("aktif")
    await nonaktifkan_akun(pt["id"], BEBAN_BANK)
    try:
        sebelum = (await db.fund_transfers.count_documents({"entity_id": pt["id"]}),
                   await db.cash_transactions.count_documents({"entity_id": pt["id"], "ref_type": "fund_transfer"}))
        e = await _ditolak(fts.buat(_isi(pt, "BCA", "MDR", 10_000, biaya=2_500), PEMBUAT), 409)
        assert e.detail.startswith("Jurnal Pindah Dana belum bisa diterbitkan:"), e.detail
        assert sebelum == (await db.fund_transfers.count_documents({"entity_id": pt["id"]}),
                           await db.cash_transactions.count_documents({"entity_id": pt["id"],
                                                                       "ref_type": "fund_transfer"}))
        assert (await fts.buat(_isi(pt, "BCA", "MDR", 10_000), PEMBUAT))["status"] == "selesai"   # tanpa biaya: lolos
    finally:
        await aktifkan_akun(pt["id"], BEBAN_BANK)


# ═══ 12. Kas ditolak di tengah terbit (rekening berubah di sela PERIKSA) → tetap menunggu, diteruskan lewat Setujui ══
async def test_KB1_4_U12_terbit_terhenti_diteruskan_tanpa_kas_ganda(db, monkeypatch):
    from services import cash_ledger
    from services import fund_transfer_service as fts
    pt = await _pt("aktif")
    sebelum = await _potret(db, pt)
    asli = cash_ledger.create_cash
    tolak = {"n": 1}

    async def _palsu(**kw):
        if kw.get("seq") == "terima" and tolak["n"]:
            tolak["n"] -= 1
            raise cash_ledger.CashRejected("Rekening Mandiri baru saja dinonaktifkan.")
        return await asli(**kw)

    monkeypatch.setattr(cash_ledger, "create_cash", _palsu)
    e = await _ditolak(fts.buat(_isi(pt, "BCA", "MDR", 80_000, biaya=1_200), PEMBUAT), 409)
    assert "belum terbit: Rekening Mandiri baru saja dinonaktifkan." in e.detail
    assert "Kas yang sudah terbit tetap tercatat" in e.detail, e.detail
    d = await db.fund_transfers.find_one({"entity_id": pt["id"]}, {"_id": 0})
    assert (d["status"], d["terbit_error"], bool(d.get("saga_lock"))) == (
        "menunggu_persetujuan", "Rekening Mandiri baru saja dinonaktifkan.", False)
    assert sorted(await _kas_dokumen(db, d["id"])) == ["biaya", "kirim"]
    hasil = await fts.setujui(d["id"], PEMBUAT)   # kontrol satu orang: pembuat boleh meneruskan sendiri
    assert (hasil["status"], hasil["terbit_error"]) == ("selesai", "")
    kas = await _kas_dokumen(db, d["id"])
    assert sorted(kas) == ["biaya", "kirim", "terima"]
    assert await db.cash_transactions.count_documents({"ref_type": "fund_transfer", "ref_id": d["id"]}) == 3
    assert _beda(sebelum, await _potret(db, pt)) == await _harap(db, pt, {"BCA": -81_200.0, "MDR": 80_000.0},
                                                                beban=1_200.0)
    # Dokumen menunggu yang sudah punya kas kirim: batal membalik kas itu
    tolak["n"] = 1
    await _ditolak(fts.buat(_isi(pt, "BCA", "MDR", 33_000), PEMBUAT), 409)
    d2 = await db.fund_transfers.find_one({"entity_id": pt["id"], "nominal": 33_000.0}, {"_id": 0})
    hasil = await fts.batal(d2["id"], "rekening tujuan berubah", PEMBUAT)
    assert (hasil["status"], hasil["batal_gl_status"]) == ("batal", "posted")
    assert [t["status"] for t in (await _kas_dokumen(db, d2["id"])).values()] == ["void"]
    assert _beda(sebelum, await _potret(db, pt)) == await _harap(db, pt, {"BCA": -81_200.0, "MDR": 80_000.0},
                                                                beban=1_200.0)

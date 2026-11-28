"""Kas & Bank 3 Tugas 3 (C3) — **opname kas** (`cash_counts`, nomor `OPK-` per PT): hitung fisik rekening tunai, saldo
buku dipotret saat dihitung, selisih ≠ 0 menunggu ORANG KEDUA (kontrol `kontrol.selisih_kas`, bawaan dua orang, juga
Admin) yang memilih perlakuan: selisih kas (Dr/Cr `6-9200`) atau piutang karyawan (kurang saja, Dr `1-1290`). Kas
penyesuaian lewat pintu kas tunggal `create_cash(ref_type="cash_count")` dengan akun lawan eksplisit.

Rancangan: `docs/superpowers/specs/2026-11-28-kas-bank-3-kasir-dana-tetap-opname-design.md` §5.3, §7 (butir 5, 6; 7.8
butir 2, 3, 6, 8).

Persiapan (FIXTURE kecuali disebut ALUR):
  * PT uji `ent_uji_kb33p<n>` per uji (`pt_uji`), rekening lewat `bank_service.create_account` (ALUR layanan): Kas Kasir
    (tunai, kas kasir, saldo awal 1.000.000), Kas Kecil (tunai, 500.000), BCA (bank, 5.000.000).
  * Karyawan HR disisip langsung ke `hr_employees` (FIXTURE).
  * Opname dibuat lewat ALUR `POST /api/cash-counts`; putusan lewat ALUR `POST /api/cash-counts/{id}/approve|reject`,
    kecuali uji bersamaan (layanan langsung).
  * Penanda waktu aktif pengingat (`system_settings.__migrations__`) dan `dihitung_pada` opname digeser langsung
    (FIXTURE) untuk uji antrean Meja Keuangan.
"""
from __future__ import annotations

import asyncio
import itertools
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from core_utils import now_iso
from pembantu import AKTOR_UJI, pt_uji, saldo_akun, tutup_periode

pytestmark = pytest.mark.anyio

URL = "/api/cash-counts"
KAS_KASIR, KAS_KECIL, SELISIH, PIUTANG = "1-1105", "1-1110", "6-9200", "1-1290"
PESAN_ORANG_KEDUA = ("Selisih opname kas ini harus diputuskan orang lain: Anda yang menghitungnya. Minta rekan yang "
                     "berizin menyetujui kas memutuskannya. Admin dapat mengubah aturan ini di Pengaturan › "
                     "Persetujuan › Kontrol dua orang.")
PESAN_BUKAN_TUNAI = ("Opname kas hanya untuk rekening kas tunai. Saldo rekening bank dicocokkan lewat Rekonsiliasi "
                     "Bank.")
PESAN_PIUTANG_LEBIH = ("Piutang karyawan hanya untuk kekurangan kas (uang fisik kurang dari saldo buku). Kelebihan kas "
                       "dibukukan sebagai selisih kas.")
PESAN_KARYAWAN_WAJIB = "Pilih karyawan yang menanggung kekurangan kas."
PESAN_PERLAKUAN = "Pilih perlakuan selisih: selisih kas atau piutang karyawan."
PESAN_ALASAN = "Alasan penolakan wajib diisi (minimal 5 huruf)."
PESAN_TOLAK_SENDIRI = ("Opname kas ini Anda hitung sendiri, jadi tidak bisa Anda tolak sendiri. Minta rekan yang berizin "
                       "menyetujui kas menolaknya dengan alasan, lalu hitung ulang. Admin dapat mengubah aturan ini di "
                       "Pengaturan › Persetujuan › Kontrol dua orang.")
PESAN_BATAL_SENDIRI = ("Opname kas ini Anda hitung sendiri, jadi pembatalannya harus dilakukan orang lain. Minta rekan "
                       "yang berizin menyetujui kas membatalkannya dengan alasan. Admin dapat mengubah aturan ini di "
                       "Pengaturan › Persetujuan › Kontrol dua orang.")
PESAN_ALASAN_BATAL = "Alasan pembatalan wajib diisi (minimal 5 huruf)."
SETUJU1 = {"id": "usr_kb33_setuju1", "name": "Dodi Penyetuju KB33", "role": "finance"}
SETUJU2 = {"id": "usr_kb33_setuju2", "name": "Sari Penyetuju KB33", "role": "finance"}
_urut = itertools.count(1)
_PERAN: dict = {}


@pytest.fixture(scope="module", autouse=True)
def _peran_segar(klien):
    """Id peran uji hanya berlaku di database modul ini (tiap modul mulai dari database kosong)."""
    _PERAN.clear()
    yield
    _PERAN.clear()


async def _rekening(eid: str, nama: str, jenis_akun: str = "cash", jenis_kas: str = "", awal: float = 0.0) -> str:
    from schemas_finance import BankAccountCreate
    from services import bank_service
    acc = await bank_service.create_account(
        BankAccountCreate(name=nama, account_type=jenis_akun, cash_type=jenis_kas, entity_id=eid,
                          opening_balance=awal), AKTOR_UJI)
    return acc["id"]


async def _peran(peran_tanpa_acuan, nama: str, izin: dict) -> str:
    if nama not in _PERAN:
        _PERAN[nama] = await peran_tanpa_acuan(izin, label=f"KB33 {nama}")
    return _PERAN[nama]


async def _pt(akun, sesi, peran_tanpa_acuan, *, per_rekening: bool = False) -> dict:
    """PT uji baru + rekening + orang: `hitung` (lihat, buat, setujui — supaya penolakan dua orang yang teruji, bukan
    izin), `hitung2` (lihat, buat), `setuju` & `setuju2` (lihat, setujui), `lihat` (lihat saja). Karyawan HR `emp` di PT
    ini dan `emp_lain` di PT lain (FIXTURE)."""
    from db import db
    from services import cash_account_mode as mode
    from services.entity_lifecycle_service import invalidate_status_cache
    kode = f"KB33P{next(_urut)}"
    eid = await pt_uji(kode)
    invalidate_status_cache()
    if per_rekening:
        await mode.nyalakan(eid, "Uji KB33")
    rek = {"KASIR": await _rekening(eid, f"Kas Kasir {kode}", jenis_kas="kas_kasir", awal=1_000_000),
           "KECIL": await _rekening(eid, f"Kas Kecil {kode}", jenis_kas="kas_kecil", awal=500_000),
           "BCA": await _rekening(eid, f"BCA {kode}", "bank", awal=5_000_000)}
    peran = {"hitung": await _peran(peran_tanpa_acuan, "Hitung", {"cash": ["view", "create", "approve"]}),
             "hitung2": await _peran(peran_tanpa_acuan, "Hitung Saja", {"cash": ["view", "create"]}),
             "setuju": await _peran(peran_tanpa_acuan, "Setujui", {"cash": ["view", "approve"]}),
             "lihat": await _peran(peran_tanpa_acuan, "Lihat", {"cash": ["view"]})}
    orang = {}
    for k, p in (("hitung", "hitung"), ("hitung2", "hitung2"), ("setuju", "setuju"), ("setuju2", "setuju"),
                 ("lihat", "lihat")):
        u = await akun(peran[p], entitas=(eid,))
        orang[k] = {"u": u, "h": await sesi(u, entitas=eid)}
    emp = {"id": f"emp_{kode.lower()}", "code": f"{kode}-K01", "name": f"Rina Kasir {kode}", "entity_id": eid,
           "status": "active", "created_at": now_iso()}
    emp_lain = {"id": f"emp_{kode.lower()}_lain", "code": f"{kode}-L01", "name": f"Tono Lain {kode}",
                "entity_id": "ent_kanda", "status": "active", "created_at": now_iso()}
    await db.hr_employees.insert_many([dict(emp), dict(emp_lain)])
    return {"id": eid, "kode": kode, "rek": rek, "o": orang, "emp": emp, "emp_lain": emp_lain}


async def _hitung(klien, pt: dict, fisik, rek: str = "KASIR", siapa: str = "hitung", status: int = 200, **lain):
    body = {"account_id": pt["rek"][rek], "catatan": "uji KB33", **lain}
    if fisik is not None:
        body["jumlah_fisik"] = fisik
    r = await klien.post(URL, headers=pt["o"][siapa]["h"], json=body)
    assert r.status_code == status, r.text
    return r.json()


async def _putus(klien, pt: dict, cid: str, aksi: str = "approve", siapa: str = "setuju", status: int = 200, **isi):
    r = await klien.post(f"{URL}/{cid}/{aksi}", headers=pt["o"][siapa]["h"], json=isi)
    assert r.status_code == status, r.text
    return r.json()


async def _kas_opname(db, cid: str) -> list:
    return [t async for t in db.cash_transactions.find({"ref_type": "cash_count", "ref_id": cid}, {"_id": 0})]


async def _jurnal(db, kas_id: str) -> dict:
    jes = await db.journal_entries.find({"source_type": "cash_transaction", "source_id": kas_id,
                                         "status": {"$ne": "void"}}, {"_id": 0}).to_list(5)
    assert len(jes) == 1, jes
    return jes[0]


def _set(je: dict) -> set:
    return {(ln["account_code"], ln["debit"], ln["credit"]) for ln in je["lines"]}


async def _buku(rid: str) -> float:
    from services import bank_service
    return round((await bank_service.account_ledger(rid))["balance"], 2)


async def _ditolak(coro, status: int, pesan: str = "") -> HTTPException:
    with pytest.raises(HTTPException) as e:
        await coro
    assert e.value.status_code == status, e.value.detail
    if pesan:
        assert e.value.detail == pesan, e.value.detail
    return e.value


# ═══ 1. Selisih 0 → selesai, tanpa kas, tanpa jurnal, tanpa pemberitahuan ═══════════════════════════════════════════
async def test_KB3_3_U1_selisih_nol_selesai(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    jurnal0 = await db.journal_entries.count_documents({"entity_id": pt["id"]})
    d = await _hitung(klien, pt, 1_000_000)
    assert d["number"] == f"{pt['kode']}/OPK-00001", d["number"]
    assert (d["status"], d["status_label"], d["saldo_buku"], d["jumlah_fisik"], d["selisih"]) == (
        "selesai", "Selesai", 1_000_000.0, 1_000_000.0, 0.0)
    assert (d["account_id"], d["cash_type"], d["entity_id"]) == (pt["rek"]["KASIR"], "kas_kasir", pt["id"])
    assert d["penghitung"] == {"id": pt["o"]["hitung"]["u"]["id"], "name": pt["o"]["hitung"]["u"]["name"]}
    assert d["tanggal"] and d["dihitung_pada"] and d["kas"] is None
    assert await _kas_opname(db, d["id"]) == []
    assert await db.journal_entries.count_documents({"entity_id": pt["id"]}) == jurnal0
    assert await db.notifications.count_documents({"ref": {"$regex": f"^{d['id']}"}}) == 0
    # Selesai tidak bisa disetujui / ditolak
    r = await _putus(klien, pt, d["id"], status=409, perlakuan="selisih_kas")
    assert r["detail"] == f"Opname kas {d['number']} sudah selesai, jadi tidak bisa disetujui.", r
    # Nomor urut per PT
    d2 = await _hitung(klien, pt, 500_000, rek="KECIL")
    assert d2["number"] == f"{pt['kode']}/OPK-00002" and d2["status"] == "selesai"


# ═══ 2. Fisik lebih 50.000 → menunggu → orang lain setujui → kas masuk 50.000 Dr kas / Cr 6-9200 ═══════════════════
async def test_KB3_3_U2_kelebihan_kas_disetujui_orang_lain(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    d = await _hitung(klien, pt, 1_050_000)
    assert (d["status"], d["selisih"], d["selisih_nominal"], d["arah_selisih"]) == (
        "menunggu_persetujuan", 50_000.0, 50_000.0, "lebih")
    assert await _kas_opname(db, d["id"]) == []
    assert d["boleh_piutang"] is False
    selisih0 = await saldo_akun(SELISIH, pt["id"])
    j = await _putus(klien, pt, d["id"], perlakuan="selisih_kas")
    assert (j["status"], j["perlakuan"], j["disetujui_oleh"]) == (
        "disetujui", "selisih_kas", pt["o"]["setuju"]["u"]["name"])
    kas = await _kas_opname(db, d["id"])
    assert len(kas) == 1
    k = kas[0]
    assert (k["direction"], k["amount"], k["account_id"], k["cash_type"], k["txn_date"]) == (
        "in", 50_000.0, pt["rek"]["KASIR"], "kas_kasir", d["tanggal"])
    assert (k["created_by"], k["cash_count_number"], k["contra_account_code"]) == (
        pt["o"]["hitung"]["u"]["name"], d["number"], SELISIH)
    assert _set(await _jurnal(db, k["id"])) == {(KAS_KASIR, 50_000.0, 0.0), (SELISIH, 0.0, 50_000.0)}
    assert j["cash_id"] == k["id"] and j["kas"]["number"] == k["number"] and j["kas"]["journal_number"]
    assert round(await saldo_akun(SELISIH, pt["id"]) - selisih0, 2) == -50_000.0   # beban berkurang (kredit)
    assert await _buku(pt["rek"]["KASIR"]) == 1_050_000.0
    assert [x["aksi"] for x in j["jejak"]] == ["hitung", "setujui"]
    # Setujui lagi → 409, kas tetap satu
    r = await _putus(klien, pt, d["id"], siapa="setuju2", status=409, perlakuan="selisih_kas")
    assert r["detail"] == f"Opname kas {d['number']} sudah disetujui, jadi tidak bisa disetujui lagi.", r
    assert len(await _kas_opname(db, d["id"])) == 1


# ═══ 3. Kurang 30.000: selisih kas Dr 6-9200; piutang karyawan (karyawan wajib) Dr 1-1290 ═════════════════════════
async def test_KB3_3_U3_kekurangan_kas_selisih_dan_piutang_karyawan(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    # (a) kurang → selisih kas: Dr 6-9200 / Cr kas
    a = await _hitung(klien, pt, 470_000, rek="KECIL")
    assert (a["selisih"], a["arah_selisih"], a["boleh_piutang"]) == (-30_000.0, "kurang", True)
    j = await _putus(klien, pt, a["id"], perlakuan="selisih_kas")
    k = (await _kas_opname(db, a["id"]))[0]
    assert (k["direction"], k["amount"], k["cash_type"]) == ("out", 30_000.0, "kas_kecil")
    assert _set(await _jurnal(db, k["id"])) == {(SELISIH, 30_000.0, 0.0), (KAS_KECIL, 0.0, 30_000.0)}
    assert j["status"] == "disetujui" and await _buku(pt["rek"]["KECIL"]) == 470_000.0
    # (b) kurang → piutang karyawan: karyawan wajib, karyawan PT lain ditolak, lalu Dr 1-1290 / Cr kas
    b = await _hitung(klien, pt, 970_000)
    assert b["selisih"] == -30_000.0
    r = await _putus(klien, pt, b["id"], status=400, perlakuan="piutang_karyawan")
    assert r["detail"] == PESAN_KARYAWAN_WAJIB, r
    r = await _putus(klien, pt, b["id"], status=400, perlakuan="piutang_karyawan", karyawan_id="emp_tidak_ada")
    assert r["detail"] == "Karyawan yang dipilih tidak ditemukan.", r
    r = await _putus(klien, pt, b["id"], status=400, perlakuan="piutang_karyawan", karyawan_id=pt["emp_lain"]["id"])
    assert r["detail"].startswith(f"{pt['emp_lain']['name']} bukan karyawan "), r
    r = await _putus(klien, pt, b["id"], status=400, perlakuan="hapus_saja")
    assert r["detail"] == PESAN_PERLAKUAN, r
    assert await _kas_opname(db, b["id"]) == []
    piutang0 = await saldo_akun(PIUTANG, pt["id"])
    j = await _putus(klien, pt, b["id"], perlakuan="piutang_karyawan", karyawan_id=pt["emp"]["id"])
    assert (j["status"], j["perlakuan"], j["karyawan_id"], j["karyawan_nama"], j["karyawan_kode"]) == (
        "disetujui", "piutang_karyawan", pt["emp"]["id"], pt["emp"]["name"], pt["emp"]["code"])
    k = (await _kas_opname(db, b["id"]))[0]
    assert (k["direction"], k["amount"], k["contra_account_code"], k["karyawan_id"]) == (
        "out", 30_000.0, PIUTANG, pt["emp"]["id"])
    je = await _jurnal(db, k["id"])
    assert _set(je) == {(PIUTANG, 30_000.0, 0.0), (KAS_KASIR, 0.0, 30_000.0)}
    assert all(pt["emp"]["name"] in ln["description"] for ln in je["lines"]), je["lines"]   # karyawan di rujukan jurnal
    assert round(await saldo_akun(PIUTANG, pt["id"]) - piutang0, 2) == 30_000.0
    # Daftar piutang dari opname = opname berperlakuan piutang karyawan
    r = await klien.get(URL, headers=pt["o"]["lihat"]["h"], params={"perlakuan": "piutang_karyawan"})
    assert r.status_code == 200 and [x["id"] for x in r.json()["items"]] == [b["id"]], r.text


# ═══ 4. Lebih + piutang karyawan → 400 ═════════════════════════════════════════════════════════════════════════════
async def test_KB3_3_U4_kelebihan_tidak_bisa_jadi_piutang(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    d = await _hitung(klien, pt, 1_020_000)
    r = await _putus(klien, pt, d["id"], status=400, perlakuan="piutang_karyawan", karyawan_id=pt["emp"]["id"])
    assert r["detail"] == PESAN_PIUTANG_LEBIH, r
    assert await _kas_opname(db, d["id"]) == []
    assert (await db.cash_counts.find_one({"id": d["id"]}))["status"] == "menunggu_persetujuan"


# ═══ 5. Penghitung memutuskan sendiri → 403 (juga Admin); pengaturan PT 1 orang → boleh ═══════════════════════════
async def test_KB3_3_U5_penghitung_tidak_memutus_sendiri(klien, db, akun, sesi, peran_tanpa_acuan):
    from services import config_resolver as resolver
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    d = await _hitung(klien, pt, 1_010_000)
    rinci = (await klien.get(f"{URL}/{d['id']}", headers=pt["o"]["hitung"]["h"])).json()
    assert rinci["kontrol"]["ditolak"] is True and rinci["kontrol"]["pesan"] == PESAN_ORANG_KEDUA
    assert rinci["kontrol"]["tolak_pesan"] == PESAN_TOLAK_SENDIRI
    rekan = (await klien.get(f"{URL}/{d['id']}", headers=pt["o"]["setuju"]["h"])).json()
    assert (rekan["kontrol"]["ditolak"], rekan["kontrol"]["tolak_pesan"]) == (False, "")
    r = await _putus(klien, pt, d["id"], siapa="hitung", status=403, perlakuan="selisih_kas")
    assert r["detail"] == PESAN_ORANG_KEDUA, r
    assert await _kas_opname(db, d["id"]) == []
    # Admin pun tidak (bawaan `kontrol.admin_tetap_dua_orang` memuat `selisih_kas`)
    ha = await sesi("admin@kainnusantara.id", entitas=pt["id"])
    r = await klien.post(URL, headers=ha, json={"account_id": pt["rek"]["KECIL"], "jumlah_fisik": 490_000})
    assert r.status_code == 200 and r.json()["status"] == "menunggu_persetujuan", r.text
    da = r.json()
    r = await klien.post(f"{URL}/{da['id']}/approve", headers=ha, json={"perlakuan": "selisih_kas"})
    assert (r.status_code, r.json()["detail"]) == (403, PESAN_ORANG_KEDUA), r.text
    r = await klien.post(f"{URL}/{da['id']}/reject", headers=ha, json={"alasan": "admin tarik sendiri"})
    assert (r.status_code, r.json()["detail"]) == (403, PESAN_TOLAK_SENDIRI), r.text
    assert (await db.cash_counts.find_one({"id": da["id"]}))["status"] == "menunggu_persetujuan"
    assert await _kas_opname(db, da["id"]) == []
    # Penghitung tanpa izin setujui → 403 izin
    await _hitung(klien, pt, 480_000, rek="KECIL", siapa="lihat", status=403)   # tanpa cash.create
    # Pengaturan PT `kontrol.selisih_kas.min_orang` = 1 → penghitung boleh memutus sendiri
    await resolver.set_value("kontrol.selisih_kas.min_orang", "1", scope_type="entity", scope_id=pt["id"],
                             reason="uji KB33 satu orang", actor="uji")
    j = await _putus(klien, pt, d["id"], siapa="hitung", perlakuan="selisih_kas")
    assert j["status"] == "disetujui" and len(await _kas_opname(db, d["id"])) == 1


# ═══ 6. Setujui ganda bersamaan → satu kas ═════════════════════════════════════════════════════════════════════════
async def test_KB3_3_U6_setujui_ganda_satu_kas(klien, db, akun, sesi, peran_tanpa_acuan):
    from services import cash_count_service as ccs
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    d = await _hitung(klien, pt, 1_075_000)
    isi = {"perlakuan": "selisih_kas"}
    hasil = await asyncio.gather(ccs.setujui(d["id"], isi, SETUJU1), ccs.setujui(d["id"], isi, SETUJU2),
                                 return_exceptions=True)
    ok = [h for h in hasil if isinstance(h, dict)]
    assert len(ok) == 1, hasil
    assert all(isinstance(h, HTTPException) and h.status_code == 409 for h in hasil if not isinstance(h, dict)), hasil
    assert len(await _kas_opname(db, d["id"])) == 1
    doc = await db.cash_counts.find_one({"id": d["id"]}, {"_id": 0})
    assert doc["status"] == "disetujui" and not doc.get("saga_lock")
    assert await _buku(pt["rek"]["KASIR"]) == 1_075_000.0


# ═══ 7. Kas dicatat di sela hitung dan putus → kas penyesuaian = selisih yang dipotret ═════════════════════════════
async def test_KB3_3_U7_kas_di_sela_hitung_dan_putus(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    d = await _hitung(klien, pt, 1_050_000)
    assert (d["saldo_buku"], d["selisih"]) == (1_000_000.0, 50_000.0)
    # Kas masuk 200.000 dicatat sesudah dihitung (kas tidak diblok selama opname menunggu)
    r = await klien.post("/api/cash-transactions", headers=pt["o"]["hitung"]["h"], json={
        "cash_type": "kas_kasir", "direction": "in", "amount": 200_000, "category": "penjualan tunai",
        "description": "tunai sesudah opname", "account_id": pt["rek"]["KASIR"], "entity_id": pt["id"]})
    assert r.status_code == 200, r.text
    assert await _buku(pt["rek"]["KASIR"]) == 1_200_000.0
    j = await _putus(klien, pt, d["id"], perlakuan="selisih_kas")
    assert (j["saldo_buku"], j["selisih"]) == (1_000_000.0, 50_000.0)     # potret tidak dihitung ulang
    k = (await _kas_opname(db, d["id"]))[0]
    assert (k["direction"], k["amount"]) == ("in", 50_000.0)
    assert await _buku(pt["rek"]["KASIR"]) == 1_250_000.0


# ═══ 8. Tolak beralasan → ditolak, tanpa kas; opname baru boleh sesudahnya ══════════════════════════════════════════
async def test_KB3_3_U8_tolak_beralasan(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    d = await _hitung(klien, pt, 990_000)
    # Selama menunggu, rekening yang sama tidak dihitung ulang
    r = await _hitung(klien, pt, 995_000, siapa="hitung2", status=409)
    assert r["detail"] == (f"Opname {d['number']} untuk rekening Kas Kasir {pt['kode']} masih menunggu keputusan "
                           "selisih. Putuskan dulu (setujui atau tolak) sebelum menghitung ulang."), r
    r = await _putus(klien, pt, d["id"], "reject", status=400, alasan="no")
    assert r["detail"] == PESAN_ALASAN, r
    j = await _putus(klien, pt, d["id"], "reject", alasan="hitung ulang, ada uang di laci kedua")
    assert (j["status"], j["status_label"], j["alasan_tolak"], j["ditolak_oleh"]) == (
        "ditolak", "Ditolak", "hitung ulang, ada uang di laci kedua", pt["o"]["setuju"]["u"]["name"])
    assert await _kas_opname(db, d["id"]) == []
    assert [x["aksi"] for x in j["jejak"]] == ["hitung", "tolak"]
    r = await _putus(klien, pt, d["id"], status=409, perlakuan="selisih_kas")
    assert r["detail"] == f"Opname kas {d['number']} sudah ditolak, jadi tidak bisa disetujui.", r
    r = await _putus(klien, pt, d["id"], "reject", status=409, alasan="tolak lagi saja")
    assert r["detail"] == f"Opname kas {d['number']} sudah ditolak, jadi tidak bisa ditolak lagi.", r
    # Penghitung menghitung ulang (opname baru)
    d2 = await _hitung(klien, pt, 1_000_000)
    assert d2["status"] == "selesai"
    # Perbaikan putaran 1 — penghitung TIDAK menolak hitungannya sendiri (selisih tidak bisa ditarik sebelum orang lain
    # memutusnya): uji tersendiri U19.


# ═══ 9. Rekening bank / tidak ada / nonaktif / isian salah → 400 ═══════════════════════════════════════════════════
async def test_KB3_3_U9_isian_dan_rekening_tidak_sah(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    n0 = await db.cash_counts.count_documents({})
    r = await _hitung(klien, pt, 5_000_000, rek="BCA", status=400)
    assert r["detail"] == PESAN_BUKAN_TUNAI, r
    r = await klien.post(URL, headers=pt["o"]["hitung"]["h"], json={"account_id": "rek_tidak_ada", "jumlah_fisik": 1})
    assert (r.status_code, r.json()["detail"]) == (400, "Rekening yang dihitung tidak ditemukan."), r.text
    r = await _hitung(klien, pt, None, status=400)
    assert r["detail"] == "Isi jumlah uang fisik yang dihitung (atau rincian pecahannya).", r
    r = await _hitung(klien, pt, -1, status=422)
    # Rincian pecahan: total harus sama dengan jumlah fisik; tanpa jumlah fisik = total pecahan
    pecahan = [{"nilai": 100_000, "lembar": 9}, {"nilai": 50_000, "lembar": 2}]
    r = await _hitung(klien, pt, 1_050_000, status=400, pecahan=pecahan)
    assert r["detail"] == ("Jumlah fisik Rp 1.050.000 tidak sama dengan total rincian pecahan Rp 1.000.000. Periksa "
                           "lagi hitungannya."), r
    assert await db.cash_counts.count_documents({}) == n0
    d = await _hitung(klien, pt, None, pecahan=pecahan)
    assert (d["jumlah_fisik"], d["status"]) == (1_000_000.0, "selesai")
    assert d["pecahan"] == [{"nilai": 100_000.0, "lembar": 9, "subtotal": 900_000.0},
                            {"nilai": 50_000.0, "lembar": 2, "subtotal": 100_000.0}]
    # Rekening nonaktif
    await db.bank_accounts.update_one({"id": pt["rek"]["KECIL"]}, {"$set": {"is_active": False}})
    r = await _hitung(klien, pt, 500_000, rek="KECIL", status=400)
    assert r["detail"] == (f"Rekening Kas Kecil {pt['kode']} tidak aktif. Aktifkan dulu di Rekening & Saldo atau "
                           "pilih rekening lain."), r
    # Rekening PT lain (di luar penugasan) → 403
    lain = await _pt(akun, sesi, peran_tanpa_acuan)
    r = await klien.post(URL, headers=pt["o"]["hitung"]["h"],
                         json={"account_id": lain["rek"]["KASIR"], "jumlah_fisik": 1_000_000})
    assert r.status_code == 403, r.text


# ═══ 10. Periode tertutup saat disetujui → 409 berkalimat, tetap menunggu, tanpa kas ═══════════════════════════════
async def test_KB3_3_U10_periode_tertutup_saat_disetujui(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    d = await _hitung(klien, pt, 1_040_000)
    rec = await tutup_periode(pt["id"], d["tanggal"][:7])
    try:
        r = await _putus(klien, pt, d["id"], status=409, perlakuan="selisih_kas")
        assert f"Selisih opname {d['number']} dibukukan pada tanggal hitung ({d['tanggal']})" in r["detail"], r
        assert r["detail"].endswith("Opname tetap menunggu."), r
        doc = await db.cash_counts.find_one({"id": d["id"]}, {"_id": 0})
        assert doc["status"] == "menunggu_persetujuan" and not doc.get("saga_lock")
        assert await _kas_opname(db, d["id"]) == []
    finally:
        await db.period_closings.delete_one({"id": rec["id"]})
    j = await _putus(klien, pt, d["id"], perlakuan="selisih_kas")
    assert j["status"] == "disetujui" and len(await _kas_opname(db, d["id"])) == 1


# ═══ 11. Opname yang sudah digantikan opname lebih baru tidak bisa disetujui ═══════════════════════════════════════
async def test_KB3_3_U11_opname_digantikan_opname_lebih_baru(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    a = await _hitung(klien, pt, 1_030_000)
    # Dua penghitung bersamaan (FIXTURE: opname kedua disisip langsung, dihitung sesudah A dengan saldo buku sama)
    b = {**(await db.cash_counts.find_one({"id": a["id"]}, {"_id": 0})), "id": "opk_kb33_u11b",
         "number": f"{pt['kode']}/OPK-09999", "dihitung_pada": (datetime.now(timezone.utc) + timedelta(seconds=5))
         .isoformat(), "jumlah_fisik": 1_020_000.0, "selisih": 20_000.0, "selisih_nominal": 20_000.0}
    await db.cash_counts.insert_one(dict(b))
    r = await _putus(klien, pt, a["id"], status=409, perlakuan="selisih_kas")
    assert r["detail"] == (f"Opname {a['number']} sudah digantikan opname {b['number']} yang dihitung sesudahnya. "
                           "Tolak opname ini; selisih rekening diputus dari opname terbaru."), r
    assert await _kas_opname(db, a["id"]) == []
    j = await _putus(klien, pt, b["id"], perlakuan="selisih_kas")
    assert j["status"] == "disetujui" and (await _kas_opname(db, b["id"]))[0]["amount"] == 20_000.0
    assert (await _putus(klien, pt, a["id"], "reject", alasan="digantikan opname baru"))["status"] == "ditolak"


# ═══ 12. PT mode akun per rekening → kas penyesuaian ke sub-akun; saldo sub-akun = buku kas rekening ═══════════════
async def test_KB3_3_U12_pt_aktif_per_rekening(klien, db, akun, sesi, peran_tanpa_acuan):
    from services import bank_service as bs
    pt = await _pt(akun, sesi, peran_tanpa_acuan, per_rekening=True)
    kasir = await db.bank_accounts.find_one({"id": pt["rek"]["KASIR"]}, {"_id": 0})
    kecil = await db.bank_accounts.find_one({"id": pt["rek"]["KECIL"]}, {"_id": 0})
    sub_kasir, sub_kecil = kasir["gl_account_code"], kecil["gl_account_code"]
    assert sub_kasir.startswith("1-1105-") and sub_kecil.startswith("1-1110-")
    a = await _hitung(klien, pt, 1_060_000)
    await _putus(klien, pt, a["id"], perlakuan="selisih_kas")
    k = (await _kas_opname(db, a["id"]))[0]
    assert k["account_code"] == sub_kasir
    assert _set(await _jurnal(db, k["id"])) == {(sub_kasir, 60_000.0, 0.0), (SELISIH, 0.0, 60_000.0)}
    b = await _hitung(klien, pt, 455_000, rek="KECIL")
    await _putus(klien, pt, b["id"], perlakuan="piutang_karyawan", karyawan_id=pt["emp"]["id"])
    k = (await _kas_opname(db, b["id"]))[0]
    assert _set(await _jurnal(db, k["id"])) == {(PIUTANG, 45_000.0, 0.0), (sub_kecil, 0.0, 45_000.0)}
    buku = {x["id"]: x["balance"] for x in await bs.list_accounts(entity_id=pt["id"])}
    assert await saldo_akun(sub_kasir, pt["id"]) == buku[pt["rek"]["KASIR"]] == 1_060_000.0
    assert await saldo_akun(sub_kecil, pt["id"]) == buku[pt["rek"]["KECIL"]] == 455_000.0


# ═══ 13. Antrean Pusat Persetujuan + jenis Aturan Persetujuan + Aturan berlaku di pintu ═══════════════════════════
async def test_KB3_3_U13_antrean_dan_aturan_persetujuan(klien, db, akun, sesi, peran_tanpa_acuan):
    import approval_kinds
    from services import approval_backlog_service as abl
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    a = await _hitung(klien, pt, 1_005_000)
    b = await _hitung(klien, pt, 499_000, rek="KECIL")
    await _hitung(klien, pt, 5_000_000, rek="BCA", status=400)
    out = await abl.backlog(pt["id"], with_oldest=True, oldest_limit=50)
    q = {r["key"]: r for r in out["all_items"]}["cash_count"]
    assert (q["count"], q["view"], q["label"]) == (2, "cash-counts", "Selisih opname kas menunggu keputusan"), q
    assert q["preset"] == {"status": "menunggu_persetujuan"}
    tua = {r["id"]: r for r in out["oldest"] if r["key"] == "cash_count"}
    assert tua[a["id"]]["number"] == a["number"] and tua[a["id"]]["title"] == f"Kas Kasir {pt['kode']}"
    k = approval_kinds.APPROVAL_KINDS["cash_count"]
    assert (k["queue_key"], k["permissions"], k["amount_field"], k["max_levels"], k["group"]) == \
        ("cash_count", ("cash.approve",), "selisih_nominal", 1, "Keuangan")
    # Aturan Persetujuan membatasi peran → pintu setujui & tolak menolak pemegang cash.approve biasa
    await db.approval_policies.insert_one({
        "id": "apl_kb33_opk", "doc_kind": "cash_count", "entity_id": pt["id"], "level": 1, "label": "Persetujuan",
        "min_amount": 0, "max_amount": None, "roles": ["admin"], "any_holder": False, "sort": 1, "active": True,
        "source": "uji"})
    try:
        r = await _putus(klien, pt, a["id"], status=403, perlakuan="selisih_kas")
        assert "Aturan Persetujuan" in r["detail"], r
        r = await _putus(klien, pt, a["id"], "reject", status=403, alasan="uji aturan KB33")
        assert "Aturan Persetujuan" in r["detail"], r
    finally:
        await db.approval_policies.delete_one({"id": "apl_kb33_opk"})
    await _putus(klien, pt, a["id"], perlakuan="selisih_kas")
    await _putus(klien, pt, b["id"], "reject", alasan="hitung ulang KB33")
    q = {r["key"]: r for r in (await abl.backlog(pt["id"]))["all_items"]}["cash_count"]
    assert q["count"] == 0


# ═══ 14. Pemberitahuan: selisih menunggu → pemegang cash.approve PT itu; diputus → penghitung ══════════════════════
async def test_KB3_3_U14_pemberitahuan(klien, db, akun, sesi, peran_tanpa_acuan, monkeypatch):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    lain = await _pt(akun, sesi, peran_tanpa_acuan)
    d = await _hitung(klien, pt, 1_025_000)
    rows = await db.notifications.find({"type": "opname_kas_menunggu", "ref": {"$regex": f"^{d['id']}"}},
                                       {"_id": 0}).to_list(20)
    harap = sorted(pt["o"][k]["u"]["id"] for k in ("setuju", "setuju2"))
    assert sorted(n["recipient_user"] for n in rows) == harap, rows   # bukan penghitung, bukan PT lain
    assert not {n["recipient_user"] for n in rows} & {lain["o"][k]["u"]["id"] for k in lain["o"]}
    for n in rows:
        assert n["entity_id"] == pt["id"] and n["recipient_role"] == ""
        assert d["number"] in n["title"] and "25.000" in n["body"] and pt["o"]["hitung"]["u"]["name"] in n["body"]
        assert n["link"] == "/?view=cash-counts"
    await _putus(klien, pt, d["id"], perlakuan="selisih_kas")
    rows = await db.notifications.find({"type": "opname_kas_diputus", "ref": {"$regex": f"^{d['id']}"}},
                                       {"_id": 0}).to_list(20)
    assert [n["recipient_user"] for n in rows] == [pt["o"]["hitung"]["u"]["id"]], rows
    assert "disetujui" in rows[0]["title"].lower() and pt["o"]["setuju"]["u"]["name"] in rows[0]["body"]
    e = await _hitung(klien, pt, 480_000, rek="KECIL")
    await _putus(klien, pt, e["id"], "reject", alasan="ada uang di amplop")
    n = (await db.notifications.find({"type": "opname_kas_diputus", "ref": {"$regex": f"^{e['id']}"}},
                                     {"_id": 0}).to_list(5))[0]
    assert "ditolak" in n["title"].lower() and "ada uang di amplop" in n["body"]
    # Pemberitahuan gagal tidak menggagalkan opname / putusan
    from services import notification_service as ns

    async def _rusak(*a, **k):
        raise RuntimeError("notifikasi rusak")
    monkeypatch.setattr(ns, "create_addressed", _rusak)
    f = await _hitung(klien, pt, 1_011_000)
    assert f["status"] == "menunggu_persetujuan"
    assert (await _putus(klien, pt, f["id"], perlakuan="selisih_kas"))["status"] == "disetujui"


# ═══ 15. Antrean Meja Keuangan "Opname kas jatuh tempo" ════════════════════════════════════════════════════════════
async def test_KB3_3_U15_antrean_meja_opname_jatuh_tempo(klien, db, akun, sesi, peran_tanpa_acuan):
    from services import cash_count_service as ccs, config_resolver as resolver, work_desk_service as desks
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    kosong = await _rekening(pt["id"], f"Kas Cadangan {pt['kode']}", jenis_kas="kas_kecil")   # tanpa kas
    h = pt["o"]["hitung"]["h"]
    for rek, ct in (("KASIR", "kas_kasir"), ("KECIL", "kas_kecil")):
        r = await klien.post("/api/cash-transactions", headers=h, json={
            "cash_type": ct, "direction": "in", "amount": 10_000, "category": "penjualan tunai",
            "description": "tunai KB33", "account_id": pt["rek"][rek], "entity_id": pt["id"]})
        assert r.status_code == 200, r.text
    await ccs.ensure_aktif_sejak()

    async def _baris() -> dict:
        out = await desks.finance_desk(AKTOR_UJI, {"entity_id": pt["id"]}, [pt["id"]])
        q = next(x for x in out["queues"] if x["id"] == "opname_kas_jatuh_tempo")
        assert (q["label"], q["owner"]) == ("Opname kas jatuh tempo", "finance"), q
        return {r["ref_id"]: r for r in q["rows"]}

    # Hari pembaruan: tidak ada rekening yang langsung terlambat
    assert await _baris() == {}
    # Fitur aktif sejak 10 hari lalu (FIXTURE)
    sepuluh = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    await db.system_settings.update_one({"scope": "__migrations__"}, {"$set": {ccs.PENANDA_AKTIF: sepuluh}})
    rows = await _baris()
    assert set(rows) == {pt["rek"]["KASIR"], pt["rek"]["KECIL"]}, rows     # rekening tanpa kas & bank tidak
    assert kosong not in rows and pt["rek"]["BCA"] not in rows
    kas = rows[pt["rek"]["KASIR"]]
    assert (kas["ref_type"], kas["number"], kas["account_id"], kas["cash_type"], kas["jarak_hari"]) == (
        "bank_account", f"Kas Kasir {pt['kode']}", pt["rek"]["KASIR"], "kas_kasir", 1)
    assert (kas["age_kind"], kas["age_days"], kas["value"], kas["action"]) == ("overdue", 9, 1_010_000.0, "Opname")
    assert rows[pt["rek"]["KECIL"]]["jarak_hari"] == 7
    # Kas kecil dihitung 3 hari lalu (< 7) → tidak; kasir dihitung 2 hari lalu (> 1) → tetap
    kecil = await _hitung(klien, pt, 510_000, rek="KECIL")
    kasir = await _hitung(klien, pt, 1_010_000)
    tiga = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    dua = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    await db.cash_counts.update_one({"id": kecil["id"]}, {"$set": {"dihitung_pada": tiga}})
    await db.cash_counts.update_one({"id": kasir["id"]}, {"$set": {"dihitung_pada": dua}})
    rows = await _baris()
    assert set(rows) == {pt["rek"]["KASIR"]}, rows
    assert rows[pt["rek"]["KASIR"]]["opname_terakhir_nomor"] == kasir["number"]
    # Kas kecil dihitung 8 hari lalu → jatuh tempo
    await db.cash_counts.update_one({"id": kecil["id"]},
                                    {"$set": {"dihitung_pada": (datetime.now(timezone.utc) - timedelta(days=8))
                                              .isoformat()}})
    assert set(await _baris()) == {pt["rek"]["KASIR"], pt["rek"]["KECIL"]}
    # Opname kasir ditolak tidak dihitung "sudah diopname"; opname baru menghapus kasir dari antrean
    await db.cash_counts.update_one({"id": kasir["id"]}, {"$set": {"status": "ditolak"}})
    assert pt["rek"]["KASIR"] in await _baris()
    await _hitung(klien, pt, 1_010_000)
    assert pt["rek"]["KASIR"] not in await _baris()
    # Jarak per PT (pengaturan): kas kecil 10 hari → tidak lagi jatuh tempo
    await resolver.set_value("kas.opname_kas_kecil_hari", 10, scope_type="entity", scope_id=pt["id"],
                             reason="uji KB33 jarak", actor="uji")
    assert pt["rek"]["KECIL"] not in await _baris()


# ═══ 16. Izin rute, daftar, rincian, pemilih karyawan ═══════════════════════════════════════════════════════════════
async def test_KB3_3_U16_izin_daftar_dan_pemilih_karyawan(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    d = await _hitung(klien, pt, 1_015_000, siapa="hitung2")             # cash.create cukup untuk menghitung
    await _putus(klien, pt, d["id"], siapa="hitung2", status=403, perlakuan="selisih_kas")   # tanpa cash.approve
    r = await klien.get(URL, headers=pt["o"]["lihat"]["h"], params={"status": "menunggu_persetujuan"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert [x["id"] for x in j["items"]] == [d["id"]] and j["total"] == 1
    assert {s["value"] for s in j["statuses"]} == {"selesai", "menunggu_persetujuan", "disetujui", "ditolak", "batal"}
    r = await klien.get(URL, headers=pt["o"]["lihat"]["h"], params={"account_id": pt["rek"]["KECIL"]})
    assert r.json()["items"] == []
    rinci = (await klien.get(f"{URL}/{d['id']}", headers=pt["o"]["setuju"]["h"])).json()
    assert rinci["kontrol"]["ditolak"] is False and rinci["boleh_piutang"] is False
    r = await klien.get(f"{URL}/opk_tidak_ada", headers=pt["o"]["lihat"]["h"])
    assert (r.status_code, r.json()["detail"]) == (404, "Opname kas tidak ditemukan."), r.text
    # Pemilih karyawan untuk piutang (pemegang cash.approve, PT dalam penugasan)
    r = await klien.get(f"{URL}/karyawan", headers=pt["o"]["setuju"]["h"], params={"entity_id": pt["id"]})
    assert r.status_code == 200, r.text
    assert r.json() == [{"id": pt["emp"]["id"], "code": pt["emp"]["code"], "name": pt["emp"]["name"]}]
    r = await klien.get(f"{URL}/karyawan", headers=pt["o"]["lihat"]["h"], params={"entity_id": pt["id"]})
    assert r.status_code == 403, r.text
    # PT lain tidak terlihat
    lain = await _pt(akun, sesi, peran_tanpa_acuan)
    r = await klien.get(f"{URL}/{d['id']}", headers=lain["o"]["lihat"]["h"])
    assert r.status_code in (403, 404), r.text


# ═══ 17. Kontrol `selisih_kas` kini terpasang (tidak lagi bertanda tidak dipakai) ═════════════════════════════════
def test_KB3_3_U17_kontrol_selisih_kas_terpasang():
    import config_registry as registry
    from config_catalog_kontrol import AKSI_BY_ID, _BELUM_DIPASANG
    assert "selisih_kas" not in _BELUM_DIPASANG
    assert AKSI_BY_ID["selisih_kas"]["titik"] == ("services/cash_count_service.py:setujui",
                                                  "services/cash_count_service.py:tolak",
                                                  "services/cash_count_service.py:batal")
    e = registry.require("kontrol.selisih_kas.min_orang")
    assert (e["status"], e["default"]) == ("active", "2")
    assert {"services/cash_count_service.py:setujui", "services/cash_count_service.py:tolak",
            "services/cash_count_service.py:batal"} <= set(e["consumers"])


# ═══ 18. Persetujuan terhenti sesudah kas tercatat → Setujui ulang memakai kas yang sama; rekening nonaktif → 409 ═══
async def test_KB3_3_U18_setujui_ulang_dan_rekening_nonaktif(klien, db, akun, sesi, peran_tanpa_acuan):
    from services import cash_ledger, gl_service as gl
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    d = await _hitung(klien, pt, 960_000)
    # FIXTURE: kas penyesuaian sudah tercatat (persetujuan selisih kas terhenti sebelum dokumen ditandai disetujui)
    lama = await cash_ledger.create_cash(
        entity_id=pt["id"], direction="out", amount=40_000, ref_type="cash_count", ref_id=d["id"],
        account_id=pt["rek"]["KASIR"], txn_date=d["tanggal"], category="selisih kas", description="terhenti",
        actor="uji", contra_account_code=gl.ACC_SELISIH_KAS, extra={"perlakuan": "selisih_kas"})
    r = await _putus(klien, pt, d["id"], status=409, perlakuan="piutang_karyawan", karyawan_id=pt["emp"]["id"])
    assert r["detail"].startswith(f"Kas penyesuaian {lama['number']} dari opname {d['number']} sudah tercatat dengan "
                                  "perlakuan selisih kas."), r
    # Tinjauan akhir Important 2 — kalimatnya menunjuk aksi yang ADA (Batalkan opname), bukan Transaksi Kas (FN-07).
    assert r["detail"].endswith(f"lalu pakai Batalkan opname {d['number']} di Opname Kas bila perlakuannya "
                                "keliru."), r
    assert "Transaksi Kas" not in r["detail"], r
    r = await _putus(klien, pt, d["id"], "reject", status=409, alasan="tolak saja")
    assert r["detail"] == (f"Kas {lama['number']} dari opname {d['number']} sudah tercatat. Setujui ulang untuk "
                           f"menuntaskan opname ini, lalu pakai Batalkan opname {d['number']} di Opname Kas bila "
                           "perlu."), r
    j = await _putus(klien, pt, d["id"], perlakuan="selisih_kas")
    assert (j["status"], j["cash_id"]) == ("disetujui", lama["id"])
    assert [t["id"] for t in await _kas_opname(db, d["id"])] == [lama["id"]]
    # Rekening dinonaktifkan sesudah dihitung → 409 berkalimat, tetap menunggu, tanpa kas
    e = await _hitung(klien, pt, 520_000, rek="KECIL")
    await db.bank_accounts.update_one({"id": pt["rek"]["KECIL"]}, {"$set": {"is_active": False}})
    r = await _putus(klien, pt, e["id"], status=409, perlakuan="selisih_kas")
    assert r["detail"].startswith(f"Rekening Kas Kecil {pt['kode']} bukan rekening aktif ") and \
        r["detail"].endswith("Opname tetap menunggu."), r
    doc = await db.cash_counts.find_one({"id": e["id"]}, {"_id": 0})
    assert doc["status"] == "menunggu_persetujuan" and not doc.get("saga_lock")
    assert await _kas_opname(db, e["id"]) == []


# ═══ 19. Penghitung tidak menolak (menarik) hitungannya sendiri — juga diputus orang kedua ════════════════════════
async def test_KB3_3_U19_penghitung_tidak_menolak_sendiri(klien, db, akun, sesi, peran_tanpa_acuan):
    from services import approval_backlog_service as abl, config_resolver as resolver
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    d = await _hitung(klien, pt, 940_000)                                  # kurang 60.000
    r = await _putus(klien, pt, d["id"], "reject", siapa="hitung", status=403, alasan="salah hitung lembaran")
    assert r["detail"] == PESAN_TOLAK_SENDIRI, r
    doc = await db.cash_counts.find_one({"id": d["id"]}, {"_id": 0})
    assert doc["status"] == "menunggu_persetujuan" and not doc.get("saga_lock") and doc["alasan_tolak"] == ""
    assert {r["key"]: r for r in (await abl.backlog(pt["id"]))["all_items"]}["cash_count"]["count"] == 1
    # Tidak bisa menghitung ulang (menimpa selisih) selama menunggu
    await _hitung(klien, pt, 1_000_000, status=409)
    # Orang kedua menolak beralasan → ditolak, tanpa kas; penghitung lalu menghitung ulang
    j = await _putus(klien, pt, d["id"], "reject", siapa="setuju", alasan="salah hitung lembaran, hitung ulang")
    assert (j["status"], j["ditolak_oleh"]) == ("ditolak", pt["o"]["setuju"]["u"]["name"])
    assert await _kas_opname(db, d["id"]) == []
    assert (await _hitung(klien, pt, 1_000_000))["status"] == "selesai"
    # PT yang mengatur `kontrol.selisih_kas.min_orang` = 1 → penghitung boleh menolak sendiri (sama dengan Setujui)
    await resolver.set_value("kontrol.selisih_kas.min_orang", "1", scope_type="entity", scope_id=pt["id"],
                             reason="uji KB33 satu orang tolak", actor="uji")
    e = await _hitung(klien, pt, 490_000, rek="KECIL")
    j = await _putus(klien, pt, e["id"], "reject", siapa="hitung", alasan="salah hitung koin")
    assert j["status"] == "ditolak"


# ═══ Tinjauan akhir Important 6 — uji wajib posting (`02_STANDAR` §1) untuk Setujui opname ═════════════════════════
async def test_KB3_3_U20_akun_lawan_nonaktif_409_tanpa_kas(klien, db, akun, sesi, peran_tanpa_acuan):
    """Akun lawan `6-9200` (selisih kas) / `1-1290` (piutang karyawan) dinonaktifkan → 409 berkalimat dari PERIKSA
    (`_periksa_terbit`), opname tetap menunggu tanpa kunci, tanpa kas dan tanpa jurnal. Diaktifkan lagi → Setujui
    menerbitkan satu kas."""
    from pembantu import aktifkan_akun, nonaktifkan_akun
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    a = await _hitung(klien, pt, 1_020_000)                                   # lebih 20.000
    b = await _hitung(klien, pt, 480_000, rek="KECIL")                        # kurang 20.000
    jurnal0 = await db.journal_entries.count_documents({"entity_id": pt["id"]})
    for doc, kode, isi in ((a, SELISIH, {"perlakuan": "selisih_kas"}),
                           (b, PIUTANG, {"perlakuan": "piutang_karyawan", "karyawan_id": pt["emp"]["id"]})):
        await nonaktifkan_akun(pt["id"], kode)
        try:
            r = await _putus(klien, pt, doc["id"], status=409, **isi)
        finally:
            await aktifkan_akun(pt["id"], kode)
        assert r["detail"].startswith(f"Jurnal selisih opname {doc['number']} belum bisa diterbitkan: "), r
        assert kode in r["detail"] and r["detail"].endswith("Opname tetap menunggu."), r
        segar = await db.cash_counts.find_one({"id": doc["id"]}, {"_id": 0})
        assert (segar["status"], segar["terbit_error"], segar.get("saga_lock")) == ("menunggu_persetujuan", "", None)
        assert await _kas_opname(db, doc["id"]) == []
    assert await db.journal_entries.count_documents({"entity_id": pt["id"]}) == jurnal0
    # Akun aktif lagi → kas terbit sekali
    assert (await _putus(klien, pt, a["id"], perlakuan="selisih_kas"))["status"] == "disetujui"
    j = await _putus(klien, pt, b["id"], perlakuan="piutang_karyawan", karyawan_id=pt["emp"]["id"])
    assert j["status"] == "disetujui" and len(await _kas_opname(db, b["id"])) == 1


async def test_KB3_3_U21_jurnal_gagal_posting_gagal_tanpa_kas_ganda(klien, db, akun, sesi, peran_tanpa_acuan,
                                                                     paksa_jurnal_gagal, kepala_admin):
    """Cabang `CashPostingError`: jurnal kas penyesuaian dipaksa gagal → kas TETAP tercatat (`gl_status: failed`,
    tampil di Posting Gagal), opname `disetujui`; Setujui lagi 409 (tanpa kas ganda); ulang dari Posting Gagal → tepat
    satu jurnal Dr 6-9200 / Cr kas kasir; ulang kedua tidak menjurnal lagi."""
    from services import posting_registry as reg
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    d = await _hitung(klien, pt, 965_000)                                     # kurang 35.000
    async with paksa_jurnal_gagal("sisip", entity_id=pt["id"], source_type="cash_transaction", kali=1) as gagal:
        j = await _putus(klien, pt, d["id"], perlakuan="selisih_kas")
    assert len(gagal) == 1
    assert (j["status"], j["kas"]["gl_status"], j["kas"]["journal_entry_id"]) == ("disetujui", "failed", ""), j
    assert j["kas"]["gl_error"] and j["cash_id"] == j["kas"]["id"]
    kas = await _kas_opname(db, d["id"])
    assert len(kas) == 1 and kas[0]["gl_status"] == "failed"
    assert await db.journal_entries.count_documents({"source_type": "cash_transaction",
                                                     "source_id": kas[0]["id"]}) == 0
    spec = reg.KINDS["cash_transaction"]
    assert await db[spec["collection"]].count_documents({**spec["failed_query"], "id": kas[0]["id"]}) == 1
    assert await _buku(pt["rek"]["KASIR"]) == 965_000.0                        # buku kas rekening sudah bergerak
    r = await _putus(klien, pt, d["id"], siapa="setuju2", status=409, perlakuan="selisih_kas")
    assert r["detail"] == f"Opname kas {d['number']} sudah disetujui, jadi tidak bisa disetujui lagi.", r
    # Ulang dari Keuangan › Posting Gagal (rute) → satu jurnal yang benar
    admin = {**kepala_admin, "X-Entity-Id": pt["id"]}
    r = await klien.post(f"/api/finance/posting-failures/cash_transaction/{kas[0]['id']}/retry", headers=admin)
    assert r.status_code == 200 and r.json()["gl_status"] == "posted", r.text
    assert _set(await _jurnal(db, kas[0]["id"])) == {(SELISIH, 35_000.0, 0.0), (KAS_KASIR, 0.0, 35_000.0)}
    rinci = (await klien.get(f"{URL}/{d['id']}", headers=pt["o"]["lihat"]["h"])).json()
    assert (rinci["kas"]["gl_status"], bool(rinci["kas"]["journal_number"])) == ("posted", True), rinci["kas"]
    r = await klien.post(f"/api/finance/posting-failures/cash_transaction/{kas[0]['id']}/retry", headers=admin)
    assert r.status_code == 404, r.text                                       # sudah terposting: bukan baris gagal
    await spec["retry"](kas[0], AKTOR_UJI)                                     # ulang paksa: tetap satu jurnal
    assert len(await _kas_opname(db, d["id"])) == 1
    await _jurnal(db, kas[0]["id"])
    assert await _buku(pt["rek"]["KASIR"]) == 965_000.0


# ═══ Tinjauan akhir Important 2 — Batal opname: kas penyesuaian dibalik lewat dokumen opname itu sendiri ═══════════
async def _batal(klien, pt: dict, cid: str, siapa: str = "setuju2", status: int = 200,
                 alasan: str = "perlakuan selisih keliru"):
    r = await klien.post(f"{URL}/{cid}/batal", headers=pt["o"][siapa]["h"], json={"alasan": alasan})
    assert r.status_code == status, r.text
    return r.json()


async def _pembalik(db, kas_id: str) -> list:
    return await db.journal_entries.find({"source_type": "cash_transaction_void", "source_id": kas_id,
                                          "status": {"$ne": "void"}}, {"_id": 0}).to_list(5)


async def test_KB3_3_U22_batal_opname_disetujui_selisih_kas(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    selisih0, kasir0 = await saldo_akun(SELISIH, pt["id"]), await saldo_akun(KAS_KASIR, pt["id"])
    d = await _hitung(klien, pt, 1_050_000)                                   # lebih 50.000
    # Masih menunggu → tidak ada yang dibatalkan (tolak saja)
    r = await _batal(klien, pt, d["id"], status=409)
    assert r["detail"] == (f"Opname kas {d['number']} masih menunggu keputusan selisih, jadi belum ada yang bisa "
                           "dibatalkan. Tolak opname ini dengan alasan bila hitungannya keliru."), r
    await _putus(klien, pt, d["id"], perlakuan="selisih_kas")
    kas = (await _kas_opname(db, d["id"]))[0]
    # Tombol Batal jujur: penghitung melihat kalimat penolakan server, rekan tidak
    rinci = (await klien.get(f"{URL}/{d['id']}", headers=pt["o"]["hitung"]["h"])).json()
    assert rinci["kontrol"]["batal_pesan"] == PESAN_BATAL_SENDIRI, rinci.get("kontrol")
    rekan = (await klien.get(f"{URL}/{d['id']}", headers=pt["o"]["setuju2"]["h"])).json()
    assert rekan["kontrol"]["batal_pesan"] == "" and rekan["batal_tertunda"] is False, rekan.get("kontrol")
    baris = (await klien.get(URL, headers=pt["o"]["hitung"]["h"], params={"status": "disetujui"})).json()["items"]
    assert [x["kontrol"]["batal_pesan"] for x in baris if x["id"] == d["id"]] == [PESAN_BATAL_SENDIRI]
    # Alasan pendek 400; penghitung 403 (kontrol `selisih_kas`); tanpa cash.approve 403 (izin)
    assert (await _batal(klien, pt, d["id"], status=400, alasan="no"))["detail"] == PESAN_ALASAN_BATAL
    assert (await _batal(klien, pt, d["id"], siapa="hitung", status=403))["detail"] == PESAN_BATAL_SENDIRI
    await _batal(klien, pt, d["id"], siapa="hitung2", status=403)
    await _batal(klien, pt, d["id"], siapa="lihat", status=403)
    assert (await db.cash_transactions.find_one({"id": kas["id"]}))["status"] == "posted"
    # Rekan membatalkan beralasan → kas dibalik (jurnal pembalik) lalu void; opname `batal`
    b = await _batal(klien, pt, d["id"], alasan="uang lebih ternyata kembalian pelanggan yang belum diambil")
    assert (b["status"], b["status_label"], b["status_sebelum_batal"], b["batal_gl_status"], b["batal_tertunda"]) == (
        "batal", "Dibatalkan", "disetujui", "posted", False), b
    assert (b["alasan_batal"], b["dibatalkan_oleh"], b["dibatalkan_oleh_id"]) == (
        "uang lebih ternyata kembalian pelanggan yang belum diambil", pt["o"]["setuju2"]["u"]["name"],
        pt["o"]["setuju2"]["u"]["id"])
    assert b["dibatalkan_pada"] and not b["dalam_proses"]
    assert [x["aksi"] for x in b["jejak"]] == ["hitung", "setujui", "batal"]
    k = await db.cash_transactions.find_one({"id": kas["id"]}, {"_id": 0})
    assert (k["status"], k["void_reason"], k["voided_by"]) == (
        "void", b["alasan_batal"], pt["o"]["setuju2"]["u"]["name"]), k
    rev = await _pembalik(db, kas["id"])
    assert len(rev) == 1 and _set(rev[0]) == {(SELISIH, 50_000.0, 0.0), (KAS_KASIR, 0.0, 50_000.0)}
    assert k["void_journal_entry_id"] == rev[0]["id"] and b["void_journal_entry_ids"] == [rev[0]["id"]]
    assert (b["kas"]["status"], b["kas"]["void_journal_number"]) == ("void", rev[0]["number"]), b["kas"]
    assert await saldo_akun(SELISIH, pt["id"]) == selisih0 and await saldo_akun(KAS_KASIR, pt["id"]) == kasir0
    assert await _buku(pt["rek"]["KASIR"]) == 1_000_000.0
    # Penghitung diberi tahu (dengan alasannya)
    n = await db.notifications.find({"type": "opname_kas_diputus", "ref": {"$regex": f"^{d['id']}:dibatalkan"}},
                                    {"_id": 0}).to_list(5)
    assert [x["recipient_user"] for x in n] == [pt["o"]["hitung"]["u"]["id"]], n
    assert "dibatalkan" in n[0]["title"].lower() and b["alasan_batal"] in n[0]["body"] and kas["number"] in n[0]["body"]
    # Terminal: batal / setujui / tolak lagi → 409
    assert (await _batal(klien, pt, d["id"], status=409))["detail"] == f"Opname kas {d['number']} sudah dibatalkan."
    r = await _putus(klien, pt, d["id"], status=409, perlakuan="selisih_kas")
    assert r["detail"] == f"Opname kas {d['number']} sudah dibatalkan, jadi tidak bisa disetujui.", r
    r = await _putus(klien, pt, d["id"], "reject", status=409, alasan="tolak sesudah batal")
    assert r["detail"] == f"Opname kas {d['number']} sudah dibatalkan, jadi tidak bisa ditolak.", r
    assert len(await _pembalik(db, kas["id"])) == 1
    # Opname batal tidak dihitung "sudah diopname": rekening dihitung ulang; daftar mengenal status batal
    assert (await _hitung(klien, pt, 1_000_000))["status"] == "selesai"
    j = (await klien.get(URL, headers=pt["o"]["lihat"]["h"], params={"status": "batal"})).json()
    assert [x["id"] for x in j["items"]] == [d["id"]] and {"value": "batal", "label": "Dibatalkan"} in j["statuses"]
    # Selesai (tanpa kas) dan ditolak tidak dibatalkan
    s = await _hitung(klien, pt, 500_000, rek="KECIL")
    r = await _batal(klien, pt, s["id"], status=409)
    assert r["detail"] == (f"Opname kas {s['number']} selesai tanpa selisih dan tanpa kas penyesuaian, jadi tidak ada "
                           "yang dibatalkan."), r
    t = await _hitung(klien, pt, 490_000, rek="KECIL")
    await _putus(klien, pt, t["id"], "reject", alasan="hitung ulang laci")
    r = await _batal(klien, pt, t["id"], status=409)
    assert r["detail"] == f"Opname kas {t['number']} sudah ditolak, jadi tidak bisa dibatalkan.", r


async def test_KB3_3_U23_batal_piutang_karyawan_aturan_dan_admin(klien, db, akun, sesi, peran_tanpa_acuan):
    """Karyawan salah dibebani piutang → Batal mengembalikan 1-1290 dan buku kas; opname baru diputus dengan karyawan
    yang benar. Aturan Persetujuan `cash_count` berlaku di pintu Batal; Admin yang menghitung tidak membatalkan
    sendiri (bawaan admin-tetap); PT `min_orang` 1 → penghitung boleh."""
    from services import config_resolver as resolver
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    piutang0 = await saldo_akun(PIUTANG, pt["id"])
    d = await _hitung(klien, pt, 455_000, rek="KECIL")                        # kurang 45.000
    await _putus(klien, pt, d["id"], perlakuan="piutang_karyawan", karyawan_id=pt["emp"]["id"])
    assert round(await saldo_akun(PIUTANG, pt["id"]) - piutang0, 2) == 45_000.0
    kas = (await _kas_opname(db, d["id"]))[0]
    await db.approval_policies.insert_one({
        "id": "apl_kb33_batal", "doc_kind": "cash_count", "entity_id": pt["id"], "level": 1, "label": "Persetujuan",
        "min_amount": 0, "max_amount": None, "roles": ["admin"], "any_holder": False, "sort": 1, "active": True,
        "source": "uji"})
    try:
        r = await _batal(klien, pt, d["id"], status=403)
        assert "Aturan Persetujuan" in r["detail"], r
    finally:
        await db.approval_policies.delete_one({"id": "apl_kb33_batal"})
    b = await _batal(klien, pt, d["id"], alasan="karyawan salah: Rina sedang cuti hari itu")
    assert (b["status"], b["perlakuan"], b["karyawan_id"]) == ("batal", "piutang_karyawan", pt["emp"]["id"])
    rev = await _pembalik(db, kas["id"])
    assert len(rev) == 1 and _set(rev[0]) == {(KAS_KECIL, 45_000.0, 0.0), (PIUTANG, 0.0, 45_000.0)}
    assert await saldo_akun(PIUTANG, pt["id"]) == piutang0 and await _buku(pt["rek"]["KECIL"]) == 500_000.0
    # Opname baru, diputus dengan karyawan yang benar (opname batal tidak menggantikan / tidak menunggu)
    lain = {"id": f"emp_{pt['kode'].lower()}_2", "code": f"{pt['kode']}-K02", "name": f"Asep Kasir {pt['kode']}",
            "entity_id": pt["id"], "status": "active", "created_at": now_iso()}
    await db.hr_employees.insert_one(dict(lain))
    e = await _hitung(klien, pt, 455_000, rek="KECIL")
    j = await _putus(klien, pt, e["id"], perlakuan="piutang_karyawan", karyawan_id=lain["id"])
    assert (j["status"], j["karyawan_id"]) == ("disetujui", lain["id"])
    # Admin menghitung → orang lain menyetujui → Admin tidak membatalkan sendiri
    ha = await sesi("admin@kainnusantara.id", entitas=pt["id"])
    r = await klien.post(URL, headers=ha, json={"account_id": pt["rek"]["KASIR"], "jumlah_fisik": 1_010_000})
    assert r.status_code == 200, r.text
    da = r.json()
    await _putus(klien, pt, da["id"], perlakuan="selisih_kas")
    r = await klien.post(f"{URL}/{da['id']}/batal", headers=ha, json={"alasan": "admin batal sendiri"})
    assert (r.status_code, r.json()["detail"]) == (403, PESAN_BATAL_SENDIRI), r.text
    assert (await db.cash_counts.find_one({"id": da["id"]}))["status"] == "disetujui"
    # PT ber-`min_orang` 1 → penghitung boleh membatalkan sendiri (sama dengan Setujui / Tolak)
    await resolver.set_value("kontrol.selisih_kas.min_orang", "1", scope_type="entity", scope_id=pt["id"],
                             reason="uji KB33 satu orang batal", actor="uji")
    assert (await _batal(klien, pt, e["id"], siapa="hitung", alasan="salah karyawan lagi"))["status"] == "batal"


async def test_KB3_3_U24_batal_periode_tertutup_dan_pembalik_gagal(klien, db, akun, sesi, peran_tanpa_acuan,
                                                                    paksa_jurnal_gagal, kepala_admin):
    """Periode tanggal pembalik tertutup → 409 berkalimat, opname tetap disetujui, kas tidak dibalik. Jurnal pembalik
    dipaksa gagal → opname `batal`, `batal_gl_status: failed`, tampil di Posting Gagal jenis `cash_count_cancel`
    (penghitung tetap diberi tahu); ulang dari Posting Gagal → tuntas, tepat satu pembalik."""
    from services import posting_registry as reg
    from services.book_date import tanggal_buku
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    d = await _hitung(klien, pt, 970_000)                                     # kurang 30.000
    await _putus(klien, pt, d["id"], perlakuan="selisih_kas")
    kas = (await _kas_opname(db, d["id"]))[0]
    rec = await tutup_periode(pt["id"], tanggal_buku()[:7])
    try:
        r = await _batal(klien, pt, d["id"], status=409)
        assert d["number"] in r["detail"] and kas["number"] in r["detail"], r
        assert r["detail"].endswith("Opname tetap disetujui."), r
    finally:
        await db.period_closings.delete_one({"id": rec["id"]})
    segar = await db.cash_counts.find_one({"id": d["id"]}, {"_id": 0})
    assert (segar["status"], segar.get("saga_lock"), segar.get("batal_gl_status", "")) == ("disetujui", None, "")
    assert (await db.cash_transactions.find_one({"id": kas["id"]}))["status"] == "posted"
    # Jurnal pembalik dipaksa gagal
    async with paksa_jurnal_gagal("sisip", entity_id=pt["id"], source_type="cash_transaction_void", kali=1):
        r = await _batal(klien, pt, d["id"], status=409, alasan="perlakuan keliru, harus piutang")
    assert r["detail"].startswith(f"Opname kas {d['number']} sudah dibatalkan, tetapi jurnal pembalik kas "
                                  f"{kas['number']} gagal: "), r
    assert r["detail"].endswith("Ulangi dari Keuangan › Posting Gagal."), r
    segar = await db.cash_counts.find_one({"id": d["id"]}, {"_id": 0})
    assert (segar["status"], segar["batal_gl_status"], segar.get("saga_lock")) == ("batal", "failed", None), segar
    assert segar["batal_gl_error"].startswith(kas["number"]) and segar["batal_gl_failed_at"]
    assert (await db.cash_transactions.find_one({"id": kas["id"]}))["status"] == "posted"   # belum dibalik
    rinci = (await klien.get(f"{URL}/{d['id']}", headers=pt["o"]["lihat"]["h"])).json()
    assert (rinci["status"], rinci["batal_tertunda"]) == ("batal", True)
    n = await db.notifications.count_documents({"type": "opname_kas_diputus",
                                                "ref": {"$regex": f"^{d['id']}:dibatalkan"}})
    assert n == 1
    spec = reg.KINDS["cash_count_cancel"]
    assert (spec["collection"], spec["label"]) == ("cash_counts", "Pembatalan Opname Kas")
    assert await db[spec["collection"]].count_documents({**spec["failed_query"], "id": d["id"]}) == 1
    baris = reg.rows_of("cash_count_cancel", segar)[0]
    assert (baris["number"], baris["amount"], baris["link"]["view"], baris["link"]["focus_id"]) == (
        d["number"], 30_000.0, "cash-counts", d["id"]), baris
    r = await klien.get("/api/finance/posting-failures", headers={**kepala_admin, "X-Entity-Id": pt["id"]},
                        params={"kind": "cash_count_cancel"})
    assert r.status_code == 200 and d["id"] in [x["id"] for x in r.json()["items"]], r.text
    await _putus(klien, pt, d["id"], status=409, perlakuan="selisih_kas")
    # Ulang dari Posting Gagal (rute) → tuntas
    r = await klien.post(f"/api/finance/posting-failures/cash_count_cancel/{d['id']}/retry",
                         headers={**kepala_admin, "X-Entity-Id": pt["id"]})
    assert r.status_code == 200 and r.json()["gl_status"] == "posted", r.text
    segar = await db.cash_counts.find_one({"id": d["id"]}, {"_id": 0})
    assert (segar["status"], segar["batal_gl_status"], segar["batal_gl_error"]) == ("batal", "posted", "")
    assert [x["aksi"] for x in segar["jejak"]] == ["hitung", "setujui", "batal", "batal_diteruskan"]
    assert (await db.cash_transactions.find_one({"id": kas["id"]}))["status"] == "void"
    rev = await _pembalik(db, kas["id"])
    assert len(rev) == 1 and _set(rev[0]) == {(KAS_KASIR, 30_000.0, 0.0), (SELISIH, 0.0, 30_000.0)}
    assert await _buku(pt["rek"]["KASIR"]) == 1_000_000.0
    assert (await _batal(klien, pt, d["id"], status=409))["detail"] == f"Opname kas {d['number']} sudah dibatalkan."
    assert await db.notifications.count_documents({"type": "opname_kas_diputus",
                                                   "ref": {"$regex": f"^{d['id']}:dibatalkan"}}) == 1


async def test_KB3_3_U25_batal_bersamaan_satu_pembalik(klien, db, akun, sesi, peran_tanpa_acuan):
    from services import cash_count_service as ccs
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    d = await _hitung(klien, pt, 1_040_000)
    await _putus(klien, pt, d["id"], perlakuan="selisih_kas")
    kas = (await _kas_opname(db, d["id"]))[0]
    hasil = await asyncio.gather(ccs.batal(d["id"], "klik ganda batal", SETUJU1),
                                 ccs.batal(d["id"], "klik ganda batal", SETUJU2), return_exceptions=True)
    assert len([h for h in hasil if isinstance(h, dict)]) == 1, hasil
    assert all(isinstance(h, HTTPException) and h.status_code == 409 for h in hasil if not isinstance(h, dict)), hasil
    assert len(await _pembalik(db, kas["id"])) == 1
    doc = await db.cash_counts.find_one({"id": d["id"]}, {"_id": 0})
    assert (doc["status"], doc["batal_gl_status"], doc.get("saga_lock")) == ("batal", "posted", None)
    assert await _buku(pt["rek"]["KASIR"]) == 1_000_000.0


async def test_KB3_3_U26_batal_rekening_jatuh_tempo_lagi(klien, db, akun, sesi, peran_tanpa_acuan):
    """Opname batal bukan opname terhitung: rekening yang opname terakhirnya dibatalkan kembali jatuh tempo."""
    from services import cash_count_service as ccs
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    r = await klien.post("/api/cash-transactions", headers=pt["o"]["hitung"]["h"], json={
        "cash_type": "kas_kasir", "direction": "in", "amount": 10_000, "category": "penjualan tunai",
        "description": "tunai KB33 U26", "account_id": pt["rek"]["KASIR"], "entity_id": pt["id"]})
    assert r.status_code == 200, r.text
    await ccs.ensure_aktif_sejak()
    sepuluh = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    await db.system_settings.update_one({"scope": "__migrations__"}, {"$set": {ccs.PENANDA_AKTIF: sepuluh}})

    async def _tempo() -> set:
        return {x["account"]["id"] for x in await ccs.jatuh_tempo([pt["id"]])}

    assert pt["rek"]["KASIR"] in await _tempo()
    d = await _hitung(klien, pt, 1_020_000)                                   # lebih 10.000
    await _putus(klien, pt, d["id"], perlakuan="selisih_kas")
    assert pt["rek"]["KASIR"] not in await _tempo()
    await _batal(klien, pt, d["id"], alasan="hitungan keliru, hitung ulang")
    assert pt["rek"]["KASIR"] in await _tempo()

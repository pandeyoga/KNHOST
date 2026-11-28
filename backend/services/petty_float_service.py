"""Kas & Bank bagian 3 (C2) — **dana tetap kas kecil**: posisi per rekening dan **isi ulang** terkunci.

Rancangan: `docs/superpowers/specs/2026-11-28-kas-bank-3-kasir-dana-tetap-opname-design.md` §5.2, §7 butir 3,
§7.8 butir 1 dan 4.

* **Dana tetap** = bidang rekening kas kecil `dana_tetap` (Tugas 1; 0 = tidak memakai dana tetap, rekening lama tanpa
  bidang = 0). Modul ini tidak menulis rekening.
* **Posisi** (`posisi`): dana tetap, saldo buku rekening (aturan buku kas rekening yang sama dengan Rekening & Saldo,
  `bank_service._txns_for`), **panjar belum LPJ** = pencairan uang muka (kas `ref_type="cash_advance"`, `account_id` =
  rekening ini, tidak batal) yang PD-nya belum ber-LPJ disetujui (§7.8.1 — tanpa bidang baru; pencairan lama tanpa
  rekening tidak dihitung ke rekening mana pun dan disebut di `panjar_tanpa_rekening`), dan
  **usulan isi ulang = dana tetap − saldo buku − panjar belum LPJ** (≤ 0 → 0).
  Rincian = dokumen sejak isi ulang terakhir (Pindah Dana bertanda yang tidak batal, dihitung dari waktu dibuat):
  LPJ disetujui (pengaruh = panjar yang ditutup LPJ itu), kas keluar manual, reimburse dibayar, pengembalian sisa panjar
  (pengaruh negatif), dan kas lain di rekening ini. Pencairan panjar tidak masuk rincian (lihat `panjar`). `pengaruh` =
  besar perubahan usulan karena baris itu; jumlahnya = `total_rincian`.
* **Isi ulang** (`isi_ulang`): PERIKSA (rekening kas kecil berdana tetap, tidak ada isi ulang yang masih berjalan,
  usulan > 0, rekening sumber = bank / kas besar PT yang sama) → **kunci per rekening** (dokumen `petty_float_locks`
  ber-`_id` = id rekening, pola kunci tutup buku PK-11: kunci basi > `KUNCI_BASI_DETIK` diambil alih, dilepas dengan
  token) → PERIKSA ULANG di dalam kunci (usulan dihitung ulang server) → **Pindah Dana sekali jalan** lewat
  `fund_transfer_service.buat` bertanda `isi_ulang_kas_kecil` + potret posisi, nominal = usulan (dibekukan saat dibuat;
  §7.8.4). Kontrol `kontrol.pindah_dana` berlaku seperti Pindah Dana lain (menunggu orang kedua → Setujui di Pindah
  Dana). "Satu isi ulang terbuka per rekening" = Pindah Dana bertanda yang masih menunggu / dalam perjalanan; lepas saat
  selesai / batal. Nominal dari klien ditolak (400). Dua isi ulang bersamaan → satu Pindah Dana (yang kalah 409).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException

from core_utils import from_cents, new_id, now_iso, rupiah, to_cents
from db import db

COLL_KUNCI = "petty_float_locks"
KUNCI_BASI_DETIK = 300
#: Batas baris rincian di jawaban & potret (dokumen sejak isi ulang terakhir; isi ulang pertama = seluruh riwayat):
#: yang terbaru dipertahankan, `rincian_terpotong` menandai; `total_rincian` tetap dari semua baris.
RINCIAN_MAKS = 500
RIWAYAT_MAKS = 10
#: PK-24 — LPJ yang sudah disetujui (jurnal terbit / tertunda gagal) menutup panjar PD-nya.
LPJ_DISETUJUI = ("approved", "posted_to_gl")

PESAN_TIDAK_ADA = "Rekening tidak ditemukan."
PESAN_SUMBER_TIDAK_ADA = "Rekening sumber tidak ditemukan."
PESAN_SUMBER = "Pilih rekening sumber isi ulang: rekening bank atau kas besar PT yang sama."
PESAN_NOMINAL = ("Nominal isi ulang dihitung sistem dari posisi dana tetap (dana tetap − saldo buku − panjar belum "
                 "LPJ), jadi tidak bisa diisi.")

#: Jenis baris rincian kas menurut rujukan kas (`ref_type`) — label tampil (`02` §4 L1: kode mentah tidak tampil).
_JENIS_KAS = {
    ("manual", "out"): ("kas_keluar_manual", "Kas keluar manual"),
    ("manual", "in"): ("kas_masuk_manual", "Kas masuk manual"),
    ("reimburse_payable", "out"): ("reimburse_dibayar", "Reimburse dibayar"),
    ("cash_advance_return", "in"): ("pengembalian_panjar", "Pengembalian sisa panjar"),
    ("fund_transfer", "in"): ("pindah_dana_masuk", "Pindah Dana masuk"),
    ("fund_transfer", "out"): ("pindah_dana_keluar", "Pindah Dana keluar"),
}


def _galat(status: int, pesan: str) -> HTTPException:
    return HTTPException(status_code=status, detail=pesan)


def _f(x: Any) -> float:
    return round(float(x or 0), 2)


def _tgl(nilai: Any) -> str:
    from services.book_date import tanggal_buku
    try:
        return tanggal_buku(nilai) if nilai else ""
    except (TypeError, ValueError):
        return str(nilai or "")[:10]


def pesan_bukan_kas_kecil(nama: str) -> str:
    return f"Rekening {nama} bukan rekening kas kecil. Dana tetap dan isi ulang hanya untuk rekening kas kecil."


def pesan_tanpa_dana_tetap(nama: str) -> str:
    return f"Rekening {nama} tidak memakai dana tetap. Atur dana tetapnya di Rekening & Saldo dulu."


def pesan_tidak_perlu(nama: str, dana: float) -> str:
    return (f"Rekening {nama} tidak perlu diisi ulang: saldo buku ditambah panjar yang belum di-LPJ sudah mencapai "
            f"dana tetap {rupiah(dana)}.")


def pesan_menunggu(nama: str, doc: Dict[str, Any]) -> str:
    from services import fund_transfer_service as fts
    label = fts.STATUS_LABEL.get(doc.get("status"), doc.get("status") or "").lower()
    return (f"Isi ulang rekening {nama} sebelumnya ({doc.get('number') or doc.get('id')}) masih {label}. Selesaikan "
            "atau batalkan Pindah Dana itu dulu.")


def pesan_sumber_jenis(nama: str) -> str:
    return (f"Rekening sumber {nama} bukan rekening bank atau kas besar. Isi ulang kas kecil diambil dari rekening bank "
            "atau kas besar PT yang sama.")


def pesan_diproses(nama: str) -> str:
    return f"Isi ulang rekening {nama} sedang diproses orang lain. Tunggu sebentar lalu muat ulang."


def pesan_nonaktif(nama: str) -> str:
    return f"Rekening {nama} tidak aktif. Aktifkan dulu di Rekening & Saldo."


# ── Rekening ─────────────────────────────────────────────────────────────────────────────────────────────────────────
async def rekening_kas_kecil(account_id: str) -> Dict[str, Any]:
    """Rekening `account_id` harus ada (404) dan berjenis kas kecil (400)."""
    from services.bank_service import account_cash_type
    acc = await db.bank_accounts.find_one({"id": account_id or "__none__"}, {"_id": 0})
    if not acc:
        raise _galat(404, PESAN_TIDAK_ADA)
    if account_cash_type(acc) != "kas_kecil":
        raise _galat(400, pesan_bukan_kas_kecil(acc.get("name") or acc["id"]))
    return acc


async def _sumber_pilihan(entity_id: str) -> List[Dict[str, Any]]:
    """Rekening sumber isi ulang yang sah: rekening aktif PT yang sama berjenis kas besar (bank / kas besar tunai)."""
    from services import bank_service as bs
    out = []
    async for a in db.bank_accounts.find({"entity_id": entity_id}, {"_id": 0}).sort("created_at", 1):
        if bs._aktif(a) and bs.account_cash_type(a) == "kas_besar":   # noqa: SLF001
            out.append({"id": a["id"], "name": a.get("name") or "", "account_type": a.get("account_type") or "",
                        "bank_name": a.get("bank_name") or "", "account_number": a.get("account_number") or ""})
    return out


async def _isi_ulang_rekening(account_id: str) -> List[Dict[str, Any]]:
    """Semua Pindah Dana isi ulang ke rekening ini (semua status), terbaru dulu."""
    from services import fund_transfer_service as fts
    return await db[fts.COLL].find({"rekening_tujuan_id": account_id, "jenis": fts.JENIS_ISI_ULANG},
                                   {"_id": 0}).sort([("created_at", -1), ("id", -1)]).to_list(None)


def _ringkas_isi_ulang(d: Dict[str, Any]) -> Dict[str, Any]:
    from services import fund_transfer_service as fts
    return {"id": d.get("id"), "number": d.get("number") or "", "status": d.get("status") or "",
            "status_label": fts.STATUS_LABEL.get(d.get("status"), d.get("status") or ""), "nominal": _f(d.get("nominal")),
            "rekening_asal_id": d.get("rekening_asal_id") or "", "rekening_asal_nama": d.get("rekening_asal_nama") or "",
            "tanggal": d.get("tanggal_kirim") or "", "created_at": d.get("created_at") or "",
            "created_by": d.get("created_by") or ""}


# ── Panjar ───────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _lpj_disetujui(ca_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """{id PD: LPJ disetujui-nya} (satu LPJ aktif per PD — CX-05)."""
    ids = sorted(set(ca_ids))
    if not ids:
        return {}
    return {s["cash_advance_id"]: s async for s in db.cash_advance_settlements.find(
        {"cash_advance_id": {"$in": ids}, "status": {"$in": list(LPJ_DISETUJUI)}}, {"_id": 0})}


async def _pencairan(query: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Kas pencairan panjar (tidak batal) + PD-nya + LPJ disetujui-nya (bila ada)."""
    kas = await db.cash_transactions.find({"ref_type": "cash_advance", "direction": "out", "status": {"$ne": "void"},
                                           **query}, {"_id": 0}).sort("created_at", 1).to_list(None)
    ids = [t.get("ref_id") for t in kas if t.get("ref_id")]
    pd = {d["id"]: d async for d in db.cash_advances.find({"id": {"$in": ids}}, {"_id": 0})} if ids else {}
    lpj = await _lpj_disetujui(ids)
    return [{"kas": t, "pd": pd.get(t.get("ref_id")), "lpj": lpj.get(t.get("ref_id"))} for t in kas]


def _terbuka(baris: Dict[str, Any]) -> bool:
    """Panjar belum di-LPJ: PD masih `disbursed` dan belum punya LPJ disetujui."""
    pd = baris["pd"] or {}
    return pd.get("status") == "disbursed" and not baris["lpj"]


def _baris_panjar(b: Dict[str, Any]) -> Dict[str, Any]:
    t, pd = b["kas"], b["pd"] or {}
    return {"cash_advance_id": t.get("ref_id") or "", "nomor": pd.get("number") or "",
            "kegiatan": pd.get("kegiatan") or "", "pemohon": pd.get("created_by") or "", "nominal": _f(t.get("amount")),
            "tanggal": _tgl(t.get("txn_date")), "kas_id": t.get("id") or "", "kas_nomor": t.get("number") or ""}


async def _panjar_tanpa_rekening(entity_id: str) -> Dict[str, Any]:
    """§7.8.1 — pencairan lama tanpa rekening (kas kecil, PT ini) yang panjarnya belum di-LPJ: tidak dihitung ke rekening
    mana pun, disebut supaya Finance tahu ada uang muka di luar hitungan."""
    rows = [b for b in await _pencairan({"entity_id": entity_id, "account_id": {"$in": [None, ""]},
                                         "cash_type": "kas_kecil"}) if _terbuka(b)]
    return {"jumlah": len(rows), "total": from_cents(sum(to_cents(_f(b["kas"].get("amount"))) for b in rows)),
            "nomor": [(b["pd"] or {}).get("number") or "" for b in rows][:5]}


# ── Rincian sejak isi ulang terakhir ─────────────────────────────────────────────────────────────────────────────────
def _baris_kas(t: Dict[str, Any]) -> Dict[str, Any]:
    from services.cash_ledger import REF_LABEL
    arah = t.get("direction") or ""
    jenis, label = _JENIS_KAS.get((t.get("ref_type") or "", arah), ("", ""))
    if not jenis:
        teks = REF_LABEL.get(t.get("ref_type") or "", "kas")
        jenis, label = ("kas_lain", f"{teks[:1].upper()}{teks[1:]} ({'masuk' if arah == 'in' else 'keluar'})")
    nominal = _f(t.get("amount"))
    return {"jenis": jenis, "label": label, "tanggal": _tgl(t.get("txn_date")), "nomor": t.get("number") or "",
            "dokumen": "", "keterangan": t.get("description") or "", "ref_type": t.get("ref_type") or "",
            "ref_id": t.get("ref_id") or "", "kas_id": t.get("id") or "", "arah": arah, "nominal": nominal,
            "pengaruh": nominal if arah == "out" else -nominal, "dicatat_pada": t.get("created_at") or ""}


def _baris_lpj(b: Dict[str, Any]) -> Dict[str, Any]:
    t, pd, s = b["kas"], b["pd"] or {}, b["lpj"] or {}
    panjar = _f(t.get("amount"))
    return {"jenis": "lpj", "label": "LPJ disetujui", "tanggal": _tgl(s.get("approved_at")),
            "nomor": s.get("number") or "", "dokumen": pd.get("number") or "",
            "keterangan": f"{pd.get('number') or ''} — {pd.get('kegiatan') or ''}".strip(" —"),
            "ref_type": "cash_advance_settlement", "ref_id": s.get("id") or "", "kas_id": t.get("id") or "",
            "arah": "", "nominal": panjar, "pengeluaran": _f(s.get("total_pengeluaran")), "pengaruh": panjar,
            "dicatat_pada": s.get("approved_at") or ""}


def _rincian(txns: List[Dict[str, Any]], pencairan: List[Dict[str, Any]], sejak: str,
             isi_ulang_ids: set) -> List[Dict[str, Any]]:
    """Baris sejak `sejak` (waktu dibuat isi ulang terakhir; "" = belum pernah diisi ulang → seluruh riwayat, termasuk
    dokumen lama tanpa cap waktu)."""
    def baru(waktu: Any) -> bool:
        return not sejak or (waktu or "") > sejak
    rows = []
    for t in txns:
        if not baru(t.get("created_at")) or t.get("ref_type") == "cash_advance":
            continue
        if t.get("ref_type") == "fund_transfer" and t.get("ref_id") in isi_ulang_ids:
            continue
        rows.append(_baris_kas(t))
    for b in pencairan:
        if b["lpj"] and baru(b["lpj"].get("approved_at")):
            rows.append(_baris_lpj(b))
    rows.sort(key=lambda r: (r["dicatat_pada"], r["nomor"]))
    return rows


# ── Posisi ───────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _posisi(acc: Dict[str, Any]) -> Dict[str, Any]:
    from services import bank_service as bs
    from services import fund_transfer_service as fts
    rid, eid = acc["id"], acc.get("entity_id") or ""
    nama = acc.get("name") or rid
    dana = _f(acc.get("dana_tetap"))
    txns = await bs._txns_for(rid)   # noqa: SLF001 — aturan buku kas rekening yang sama dengan Rekening & Saldo
    saldo = bs._balance(float(acc.get("opening_balance") or 0), txns)   # noqa: SLF001
    isi = await _isi_ulang_rekening(rid)
    hidup = [d for d in isi if d.get("status") != fts.BATAL]
    terakhir = hidup[0] if hidup else None
    menunggu = next((d for d in hidup if d.get("status") in (fts.MENUNGGU, fts.PERJALANAN)), None)
    pencairan = await _pencairan({"account_id": rid})
    terbuka = [b for b in pencairan if _terbuka(b)]
    panjar_sen = sum(to_cents(_f(b["kas"].get("amount"))) for b in terbuka)
    usulan_sen = max(to_cents(dana) - to_cents(saldo) - panjar_sen, 0) if dana > 0 else 0
    rincian = _rincian(txns, pencairan, (terakhir or {}).get("created_at") or "", {d["id"] for d in isi})
    alasan = ""
    if not bs._aktif(acc):   # noqa: SLF001
        alasan = pesan_nonaktif(nama)
    elif dana <= 0:
        alasan = pesan_tanpa_dana_tetap(nama)
    elif menunggu:
        alasan = pesan_menunggu(nama, menunggu)
    elif usulan_sen <= 0:
        alasan = pesan_tidak_perlu(nama, dana)
    return {
        "account_id": rid, "account_name": nama, "entity_id": eid, "is_active": bs._aktif(acc),   # noqa: SLF001
        "location_id": acc.get("location_id") or "", "dana_tetap": dana, "saldo_buku": saldo,
        "panjar_belum_lpj": from_cents(panjar_sen), "usulan_isi_ulang": from_cents(usulan_sen),
        "panjar": [_baris_panjar(b) for b in terbuka], "rincian": rincian[-RINCIAN_MAKS:],
        "rincian_terpotong": len(rincian) > RINCIAN_MAKS,
        "total_rincian": from_cents(sum(to_cents(r["pengaruh"]) for r in rincian)),
        "sejak": _ringkas_isi_ulang(terakhir) if terakhir else None,
        "isi_ulang_menunggu": _ringkas_isi_ulang(menunggu) if menunggu else None,
        "riwayat": [_ringkas_isi_ulang(d) for d in isi[:RIWAYAT_MAKS]],
        "panjar_tanpa_rekening": await _panjar_tanpa_rekening(eid),
        "sumber": await _sumber_pilihan(eid),
        "bisa_isi_ulang": not alasan, "alasan_isi_ulang": alasan,
        "dihitung_pada": now_iso(),
    }


async def posisi(account_id: str) -> Dict[str, Any]:
    """`GET /api/kas-kecil/dana-tetap/{account_id}` — posisi dana tetap satu rekening kas kecil."""
    return await _posisi(await rekening_kas_kecil(account_id))


async def daftar(entity_ids: List[str]) -> Dict[str, Any]:
    """`GET /api/kas-kecil/dana-tetap` — posisi rekening kas kecil AKTIF berdana tetap di PT dalam cakupan (urut PT lalu
    waktu dibuat); `tanpa_dana_tetap` = jumlah rekening kas kecil aktif yang belum memakai dana tetap."""
    from services import bank_service as bs
    items, tanpa = [], 0
    async for acc in db.bank_accounts.find({"entity_id": {"$in": list(entity_ids or [])}}, {"_id": 0}) \
            .sort([("entity_id", 1), ("created_at", 1)]):
        if not bs._aktif(acc) or bs.account_cash_type(acc) != "kas_kecil":   # noqa: SLF001
            continue
        if _f(acc.get("dana_tetap")) <= 0:
            tanpa += 1
            continue
        items.append(await _posisi(acc))
    return {"items": items, "total": len(items), "tanpa_dana_tetap": tanpa}


# ── Kunci per rekening ───────────────────────────────────────────────────────────────────────────────────────────────
async def _kunci(account_id: str, nama: str, actor: Dict[str, Any]) -> str:
    """Kunci isi ulang satu rekening (pola PK-11): satu dokumen ber-`_id` = id rekening. Kunci basi (proses mati) diambil
    alih; kunci hidup milik orang lain → 409. → token pemilik."""
    from pymongo.errors import DuplicateKeyError
    sekarang = datetime.now(timezone.utc)
    basi = (sekarang - timedelta(seconds=KUNCI_BASI_DETIK)).isoformat()
    await db[COLL_KUNCI].delete_one({"_id": account_id, "mulai": {"$lt": basi}})
    token = new_id("lk")
    try:
        await db[COLL_KUNCI].insert_one({"_id": account_id, "token": token, "oleh": (actor or {}).get("name") or "",
                                         "mulai": sekarang.isoformat()})
    except DuplicateKeyError:
        raise _galat(409, pesan_diproses(nama)) from None
    return token


async def _lepas(account_id: str, token: str) -> None:
    await db[COLL_KUNCI].delete_one({"_id": account_id, "token": token})


# ── Isi ulang ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _periksa_posisi(pos: Dict[str, Any]) -> None:
    """Isi ulang boleh? Alasan yang sama dengan `alasan_isi_ulang` posisi (tombol layar jujur)."""
    if pos["bisa_isi_ulang"]:
        return
    raise _galat(409 if pos["isi_ulang_menunggu"] else 400, pos["alasan_isi_ulang"])


def _potret(pos: Dict[str, Any]) -> Dict[str, Any]:
    """Potret posisi saat isi ulang dibuat (disimpan di Pindah Dana; tidak dihitung ulang)."""
    return {"account_id": pos["account_id"], "dana_tetap": pos["dana_tetap"], "saldo_buku": pos["saldo_buku"],
            "panjar_belum_lpj": pos["panjar_belum_lpj"], "usulan": pos["usulan_isi_ulang"],
            "panjar": pos["panjar"], "rincian": pos["rincian"], "rincian_terpotong": pos["rincian_terpotong"],
            "total_rincian": pos["total_rincian"],
            "sejak_id": (pos["sejak"] or {}).get("id") or "", "sejak_nomor": (pos["sejak"] or {}).get("number") or "",
            "panjar_tanpa_rekening": pos["panjar_tanpa_rekening"], "dihitung_pada": pos["dihitung_pada"]}


async def isi_ulang(account_id: str, sumber_account_id: str, actor: Dict[str, Any], *, catatan: str = "",
                    tanggal: str = "", nominal: Optional[float] = None) -> Dict[str, Any]:
    """`POST /api/kas-kecil/dana-tetap/{account_id}/isi-ulang` — terbitkan Pindah Dana sekali jalan sebesar usulan
    (dihitung ulang server di dalam kunci rekening) dari rekening bank / kas besar PT yang sama. → dokumen Pindah Dana
    (`fund_transfer_service._bentuk`): `selesai`, atau `menunggu_persetujuan` bila `kontrol.pindah_dana` butuh orang
    kedua."""
    from services import bank_service as bs
    from services import fund_transfer_service as fts
    # ── PERIKSA (tanpa tulisan) ──
    if nominal is not None:
        raise _galat(400, PESAN_NOMINAL)
    acc = await rekening_kas_kecil(account_id)
    nama = acc.get("name") or acc["id"]
    _periksa_posisi(await _posisi(acc))
    sid = (sumber_account_id or "").strip()
    if not sid:
        raise _galat(400, PESAN_SUMBER)
    src = await db.bank_accounts.find_one({"id": sid}, {"_id": 0})
    if not src:
        raise _galat(400, PESAN_SUMBER_TIDAK_ADA)
    if bs.account_cash_type(src) != "kas_besar":
        raise _galat(400, pesan_sumber_jenis(src.get("name") or sid))
    eid = acc.get("entity_id") or ""
    await fts._periksa_pasangan(eid, sid, acc["id"])   # noqa: SLF001 — satu PT, aktif (kalimat Pindah Dana)
    # ── KUNCI rekening → PERIKSA ULANG → Pindah Dana ──
    token = await _kunci(acc["id"], nama, actor)
    try:
        acc = await rekening_kas_kecil(acc["id"])
        pos = await _posisi(acc)
        _periksa_posisi(pos)
        isian = {"entity_id": eid, "rekening_asal_id": sid, "rekening_tujuan_id": acc["id"],
                 "nominal": pos["usulan_isi_ulang"], "biaya": 0, "tanggal_kirim": tanggal or "", "tanggal_terima": "",
                 "catatan": (catatan or "").strip() or f"Isi ulang dana tetap {nama}"}
        return await fts.buat(isian, actor, jenis=fts.JENIS_ISI_ULANG, isi_ulang=_potret(pos))
    finally:
        await _lepas(acc["id"], token)

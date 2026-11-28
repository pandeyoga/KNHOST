"""Kas & Bank bagian 3 (C3) — **opname kas** (`cash_counts`, nomor `OPK-` per PT): hitung fisik uang di rekening tunai
lalu cocokkan dengan saldo buku rekening itu.

Rancangan: `docs/superpowers/specs/2026-11-28-kas-bank-3-kasir-dana-tetap-opname-design.md` §5.3, §6, §7 (butir 5, 6;
7.8 butir 2, 3, 6, 8).

* **Hitung** (`buat`, izin `cash.create`) — rekening `account_type="cash"` aktif (kas kasir, kas kecil, kas besar tunai;
  rekening bank → 400, dicocokkan lewat Rekonsiliasi Bank). Isian: jumlah fisik (≥ 0) dan/atau rincian pecahan
  (opsional; bila keduanya diisi harus sama), catatan. Sistem MEMOTRET saldo buku rekening saat dihitung (saldo awal +
  semua kas tidak-batal, sama dengan saldo di Rekening & Saldo) dan **selisih = fisik − buku**. Selisih 0 → `selesai`
  tanpa kas. Selisih ≠ 0 → `menunggu_persetujuan`, pemegang `cash.approve` diberi tahu. Satu opname menunggu per
  rekening (hitung ulang sesudah diputus).
* **Setujui** (`cash.approve`; Aturan Persetujuan jenis `cash_count` dijaga rute) — bukan penghitung (kontrol
  `kontrol.selisih_kas`, bawaan dua orang, juga Admin lewat `kontrol.admin_tetap_dua_orang`). Perlakuan:
    - `selisih_kas`: lebih → kas MASUK Dr kas / Cr `6-9200 Selisih Kas`; kurang → kas KELUAR Dr `6-9200` / Cr kas;
    - `piutang_karyawan` (kurang saja; karyawan HR PT itu wajib) → kas KELUAR Dr `1-1290 Piutang Karyawan – Kekurangan
      Kas` / Cr kas; karyawan disebut di keterangan kas (rujukan jurnal) dan di dokumen kas (`karyawan_*`).
  Kas lewat pintu kas tunggal `cash_ledger.create_cash(ref_type="cash_count", ref_id=<id opname>)` dengan akun lawan
  eksplisit (`contra_account_code` konstanta `gl_service`, dipetakan per PT oleh `_insert_entry`); akun kas dipilih pintu
  kas lewat `gl_service.akun_kas` (sub-akun rekening di PT mode akun per rekening). **Selisih yang dibukukan = selisih
  yang dipotret** (kas yang dicatat sesudah dihitung menggeser fisik dan buku sama besar, §7.8.3); tanggal kas = tanggal
  hitung; periode tertutup → 409 berkalimat, opname tetap menunggu. Opname yang sudah digantikan opname lebih baru
  (rekening sama, dihitung sesudahnya, belum ditolak) tidak bisa disetujui — selisih rekening diputus dari opname terbaru.
  Pembuat kas = penghitung, penyetuju di `disetujui_oleh`.
* **Tolak** (`cash.approve`, alasan ≥ 5 huruf) → `ditolak`, tanpa kas; penghitung menghitung ulang (opname baru).
  Kontrol `kontrol.selisih_kas` yang sama dengan Setujui (perbaikan putaran 1, ketetapan pengendali): penghitung — Admin
  juga — tidak menolak hitungannya sendiri, supaya selisih yang ia temukan tidak hilang dari antrean sebelum orang lain
  memutusnya. Salah hitung → orang kedua menolak beralasan, lalu penghitung menghitung ulang.
* **Batal** (`cash.approve` + Aturan Persetujuan `cash_count`, alasan ≥ 5 huruf; tinjauan akhir Important 2) — jalan
  balik putusan yang keliru (karyawan / perlakuan salah) lewat dokumen opname itu sendiri, bukan Transaksi Kas (FN-07)
  dan bukan jurnal manual. Hanya opname `disetujui`; kontrol `kontrol.selisih_kas` yang sama (penghitung — Admin juga —
  tidak membatalkan putusan atas hitungannya sendiri). Klaim berprasyarat status yang diperiksa; kas penyesuaian dibalik
  lewat pembalik kas yang ada (`gl_service.post_cash_void` di pintu tahan-gagal, tanggal
  `posting_registry.tanggal_pembalik`, periode & akun diperiksa dulu) lalu `void`. Pembalik gagal → opname tetap `batal`,
  `batal_gl_status: failed`, tampil di Posting Gagal (jenis `cash_count_cancel`); ulang (atau Batal lagi) meneruskannya.
  Status `batal` bukan opname terhitung: rekening kembali jatuh tempo opname dan opname itu tidak menggantikan opname
  lain. Penghitung diberi tahu.
* **Pengingat** (`jatuh_tempo`, antrean Meja Keuangan `opname_kas_jatuh_tempo`) — rekening tunai yang opname
  terakhirnya (selesai/menunggu/disetujui) lebih lama dari `kas.opname_*_hari` (`bank_service.hari_opname`), dihitung
  sejak fitur aktif (penanda sekali tulis `PENANDA_AKTIF`, pola F1) dan hanya rekening yang punya kas sesudah itu.

Urutan tiap aksi (`02_STANDAR.md` §1): PERIKSA tanpa tulisan → KLAIM (`atomic_claim.claim` berprasyarat status) → EFEK
(kas ber-id tetap dari rujukan) → SELESAI (`finish_set`, kunci dicabut). Setujui ganda/bersamaan → satu kas.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core_utils import new_id, now_iso, rupiah, safe_doc
from db import db
from pagination import MAX_PAGE_SIZE

logger = logging.getLogger(__name__)

COLL = "cash_counts"
REF_TYPE = "cash_count"
SELESAI, MENUNGGU, DISETUJUI, DITOLAK, BATAL = "selesai", "menunggu_persetujuan", "disetujui", "ditolak", "batal"
STATUS_LABEL = {SELESAI: "Selesai", MENUNGGU: "Menunggu persetujuan", DISETUJUI: "Disetujui", DITOLAK: "Ditolak",
                BATAL: "Dibatalkan"}
#: Opname yang dianggap "sudah dihitung" (pengingat, penggantian opname lama). Ditolak / dibatalkan = harus dihitung
#: ulang (rekening kembali jatuh tempo).
TERHITUNG = (SELESAI, MENUNGGU, DISETUJUI)
P_SELISIH, P_PIUTANG = "selisih_kas", "piutang_karyawan"
PERLAKUAN_LABEL = {P_SELISIH: "Selisih kas", P_PIUTANG: "Piutang karyawan"}
ALASAN_MIN = 5   # K-14 (26 Okt) — alasan minimum seragam 5 huruf
EPS = 0.005
#: §7.8.8 — waktu aktif pengingat opname (sekali tulis, dokumen `system_settings.__migrations__`, pola F1).
PENANDA_AKTIF = "kb3_opname_kas_aktif_sejak"

PESAN_TIDAK_ADA = "Opname kas tidak ditemukan."
PESAN_REKENING_TIDAK_ADA = "Rekening yang dihitung tidak ditemukan."
PESAN_BUKAN_TUNAI = ("Opname kas hanya untuk rekening kas tunai. Saldo rekening bank dicocokkan lewat Rekonsiliasi "
                     "Bank.")
PESAN_FISIK_WAJIB = "Isi jumlah uang fisik yang dihitung (atau rincian pecahannya)."
PESAN_FISIK_NEGATIF = "Jumlah uang fisik tidak boleh negatif."
PESAN_PECAHAN = "Pecahan harus bernilai lebih dari 0 dengan jumlah lembar 0 atau lebih."
PESAN_PERLAKUAN = "Pilih perlakuan selisih: selisih kas atau piutang karyawan."
PESAN_PIUTANG_LEBIH = ("Piutang karyawan hanya untuk kekurangan kas (uang fisik kurang dari saldo buku). Kelebihan kas "
                       "dibukukan sebagai selisih kas.")
PESAN_KARYAWAN_WAJIB = "Pilih karyawan yang menanggung kekurangan kas."
PESAN_KARYAWAN_TIDAK_ADA = "Karyawan yang dipilih tidak ditemukan."
PESAN_ALASAN_TOLAK = f"Alasan penolakan wajib diisi (minimal {ALASAN_MIN} huruf)."
#: §7 butir 5 — tanpa jalan pintas: minta orang lain yang berizin; aturan bisa diubah Admin di Pusat Pengaturan.
PESAN_ORANG_KEDUA = ("Selisih opname kas ini harus diputuskan orang lain: Anda yang menghitungnya. Minta rekan yang "
                     "berizin menyetujui kas memutuskannya. Admin dapat mengubah aturan ini di Pengaturan › "
                     "Persetujuan › Kontrol dua orang.")
#: Perbaikan putaran 1 — Tolak juga diputus orang lain (selisih tidak bisa ditarik penghitungnya sendiri).
PESAN_TOLAK_SENDIRI = ("Opname kas ini Anda hitung sendiri, jadi tidak bisa Anda tolak sendiri. Minta rekan yang "
                       "berizin menyetujui kas menolaknya dengan alasan, lalu hitung ulang. Admin dapat mengubah aturan "
                       "ini di Pengaturan › Persetujuan › Kontrol dua orang.")
#: Tinjauan akhir Important 2 — Batal juga diputus orang lain (putusan dua orang tidak dibatalkan penghitungnya sendiri).
PESAN_BATAL_SENDIRI = ("Opname kas ini Anda hitung sendiri, jadi pembatalannya harus dilakukan orang lain. Minta rekan "
                       "yang berizin menyetujui kas membatalkannya dengan alasan. Admin dapat mengubah aturan ini di "
                       "Pengaturan › Persetujuan › Kontrol dua orang.")
PESAN_ALASAN_BATAL = f"Alasan pembatalan wajib diisi (minimal {ALASAN_MIN} huruf)."
_KATA_AKSI = {"setujui": "disetujui", "tolak": "ditolak"}


def _galat(status: int, pesan: str) -> HTTPException:
    return HTTPException(status_code=status, detail=pesan)


def _f(x: Any) -> float:
    return round(float(x or 0), 2)


def _isi(payload: Any) -> Dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return dict(payload or {})


def _jejak(aksi: str, actor: Dict[str, Any], catatan: str = "") -> Dict[str, Any]:
    return {"aksi": aksi, "oleh": (actor or {}).get("name", ""), "oleh_id": (actor or {}).get("id", ""),
            "pada": now_iso(), "catatan": catatan}


def _nomor(doc: Dict[str, Any]) -> str:
    return doc.get("number") or doc.get("id") or ""


def _penghitung(doc: Dict[str, Any]) -> List[str]:
    """Pembanding kontrol dua orang = penghitung (id; nama hanya bila id kosong — nama bisa kembar)."""
    p = doc.get("penghitung") or {}
    return [p.get("id") or p.get("name") or ""]


def _pesan_status(doc: Dict[str, Any], aksi: str) -> str:
    """Aksi `setujui` | `tolak` atas opname yang tidak lagi menunggu."""
    kata = _KATA_AKSI[aksi]
    label = STATUS_LABEL.get(doc.get("status"), doc.get("status") or "").lower()
    lagi = " lagi" if kata == label else ""
    return f"Opname kas {_nomor(doc)} sudah {label}, jadi tidak bisa {kata}{lagi}."


def _pesan_berubah(doc: Dict[str, Any]) -> str:
    """Kalah klaim (keadaan berubah di antara PERIKSA dan KLAIM, mis. sedang diputus orang lain)."""
    return f"Opname kas {_nomor(doc)} baru saja diubah orang lain. Muat ulang lalu periksa."


async def _ambil(cid: str) -> Dict[str, Any]:
    doc = await db[COLL].find_one({"id": cid or "__none__"}, {"_id": 0})
    if not doc:
        raise _galat(404, PESAN_TIDAK_ADA)
    return doc


async def saldo_buku(acc: Dict[str, Any]) -> float:
    """Saldo buku rekening SEKARANG = saldo awal + semua kas tidak-batal rekening itu (termasuk kas tanpa rekening yang
    ikut rekening tunggal jenisnya) — angka yang sama dengan saldo di Rekening & Saldo (`bank_service.list_accounts`)."""
    from services import bank_service as bs
    return bs._balance(float(acc.get("opening_balance") or 0), await bs._txns_for(acc.get("id") or ""))


# ── Pembentuk jawaban ────────────────────────────────────────────────────────────────────────────────────────────────
def _bentuk(doc: Dict[str, Any]) -> Dict[str, Any]:
    from services.cash_ledger import CASH_TYPE_LABEL
    d = safe_doc(dict(doc))
    d.pop("saga_lock", None)
    d["status_label"] = STATUS_LABEL.get(d.get("status"), d.get("status") or "")
    d["cash_type_label"] = {"kas_besar": "Kas besar"}.get(d.get("cash_type") or "") or \
        CASH_TYPE_LABEL.get(d.get("cash_type") or "", "")
    d["perlakuan_label"] = PERLAKUAN_LABEL.get(d.get("perlakuan") or "", "")
    d["boleh_piutang"] = _f(d.get("selisih")) < -EPS
    d["dalam_proses"] = bool(doc.get("saga_lock"))
    # Batal yang jurnal pembaliknya belum tuntas (Posting Gagal) → layar menawarkan "teruskan pembatalan".
    d["batal_tertunda"] = d.get("status") == BATAL and d.get("batal_gl_status") in ("pending", "failed")
    return d


async def _kas(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Kas penyesuaian opname (dibaca langsung: status & jurnal terkini, termasuk ulang dari Posting Gagal)."""
    t = None
    if doc.get("cash_id"):
        t = await db.cash_transactions.find_one({"id": doc["cash_id"]}, {"_id": 0})
    if t is None:
        t = await db.cash_transactions.find_one({"ref_type": REF_TYPE, "ref_id": doc.get("id") or "__none__",
                                                 "status": {"$ne": "void"}}, {"_id": 0})
    if not t:
        return None
    jids = [x for x in (t.get("journal_entry_id"), t.get("void_journal_entry_id")) if x]
    nomor_je = {j["id"]: j.get("number", "") async for j in db.journal_entries.find(
        {"id": {"$in": jids}}, {"_id": 0, "id": 1, "number": 1})} if jids else {}
    return {"id": t["id"], "number": t.get("number", ""), "txn_date": t.get("txn_date", ""),
            "direction": t.get("direction", ""), "amount": _f(t.get("amount")), "status": t.get("status", ""),
            "gl_status": t.get("gl_status", ""), "gl_error": t.get("gl_error", ""),
            "journal_entry_id": t.get("journal_entry_id", ""),
            "journal_number": nomor_je.get(t.get("journal_entry_id") or "", ""),
            # Batal opname: kas dibalik (`status: void`) dengan jurnal pembalik ini.
            "void_journal_entry_id": t.get("void_journal_entry_id", ""),
            "void_journal_number": nomor_je.get(t.get("void_journal_entry_id") or "", "")}


#: Status yang membawa penilaian kontrol dua orang di rincian/daftar: menunggu (Setujui/Tolak), disetujui (Batal).
_BERKONTROL = (MENUNGGU, DISETUJUI)


async def _kontrol(doc: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Penilaian kontrol dua orang untuk `actor` (tombol Setujui jujur, kalimat sama dengan penolakan server)."""
    from services import dual_control
    out = await dual_control.periksa("selisih_kas", doc, actor, doc.get("entity_id") or "", pengaju=_penghitung(doc))
    if out.get("ditolak"):
        out["pesan"] = PESAN_ORANG_KEDUA
    # Tombol Tolak / Batal nonaktif untuk penghitung dengan kalimat yang sama dengan penolakan server (`tolak`, `batal`).
    out["tolak_pesan"] = PESAN_TOLAK_SENDIRI if out.get("ditolak") else ""
    out["batal_pesan"] = PESAN_BATAL_SENDIRI if out.get("ditolak") else ""
    return out


async def rincian(count_id: str, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Opname + kas penyesuaian (`kas`, None bila belum/tanpa kas) + penilaian kontrol dua orang untuk `actor` (bila
    diberi dan opname menunggu — Setujui/Tolak — atau disetujui — Batal)."""
    doc = await _ambil(count_id)
    out = _bentuk(doc)
    out["kas"] = await _kas(doc)
    if actor is not None and doc.get("status") in _BERKONTROL:
        out["kontrol"] = await _kontrol(doc, actor)
    return out


async def daftar(entity_ids: List[str], *, status: str = "", account_id: str = "", perlakuan: str = "", q: str = "",
                 page: int = 1, page_size: int = 25, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """`GET /api/cash-counts` — opname PT dalam cakupan (terbaru dulu), berhalaman. `perlakuan=piutang_karyawan` = daftar
    piutang karyawan dari opname (§7.8.6). `q` = nomor / rekening / penghitung / karyawan / catatan. Baris menunggu
    dan disetujui membawa penilaian kontrol untuk `actor`."""
    query: Dict[str, Any] = {"entity_id": {"$in": list(entity_ids or [])}}
    if status:
        query["status"] = status
    if account_id:
        query["account_id"] = account_id
    if perlakuan:
        query["perlakuan"] = perlakuan
    teks = (q or "").strip()
    if teks:
        rx = {"$regex": re.escape(teks), "$options": "i"}
        query["$or"] = [{"number": rx}, {"account_name": rx}, {"penghitung.name": rx}, {"karyawan_nama": rx},
                        {"catatan": rx}]
    page, page_size = max(1, int(page or 1)), max(1, min(int(page_size or 25), MAX_PAGE_SIZE))
    total = await db[COLL].count_documents(query)
    rows = await db[COLL].find(query, {"_id": 0}).sort([("dihitung_pada", -1), ("id", -1)]) \
        .skip((page - 1) * page_size).to_list(page_size)
    items = []
    for r in rows:
        d = _bentuk(r)
        if actor is not None and r.get("status") in _BERKONTROL:
            d["kontrol"] = await _kontrol(r, actor)
        items.append(d)
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "has_more": page * page_size < total,
            "statuses": [{"value": k, "label": v} for k, v in STATUS_LABEL.items()],
            "perlakuan": [{"value": k, "label": v} for k, v in PERLAKUAN_LABEL.items()]}


# ── Hitung ───────────────────────────────────────────────────────────────────────────────────────────────────────────
async def rekening_tunai(account_id: str) -> Dict[str, Any]:
    """Rekening yang dihitung: ada, tunai, aktif — selain itu 400 berkalimat. Pemeriksaan PT dalam penugasan di rute."""
    from services import bank_service as bs
    from services.cash_entity_service import assert_owned
    acc = await db.bank_accounts.find_one({"id": (account_id or "").strip() or "__none__"}, {"_id": 0})
    if not acc:
        raise _galat(400, PESAN_REKENING_TIDAK_ADA)
    assert_owned(acc.get("entity_id"), what="Opname kas")   # kas tingkat grup sudah dihapus (E7.4) → 409 berkalimat
    if acc.get("account_type") != "cash":
        raise _galat(400, PESAN_BUKAN_TUNAI)
    if not bs._aktif(acc):
        raise _galat(400, f"Rekening {acc.get('name') or acc['id']} tidak aktif. Aktifkan dulu di Rekening & Saldo atau "
                          "pilih rekening lain.")
    return acc


def _pecahan(isian: Any) -> List[Dict[str, Any]]:
    out = []
    for p in isian or []:
        p = _isi(p)
        nilai, lembar = _f(p.get("nilai")), p.get("lembar")
        try:
            lembar = int(lembar or 0)
        except (TypeError, ValueError):
            raise _galat(400, PESAN_PECAHAN) from None
        if nilai <= EPS or lembar < 0:
            raise _galat(400, PESAN_PECAHAN)
        out.append({"nilai": nilai, "lembar": lembar, "subtotal": _f(nilai * lembar)})
    return out


def _jumlah_fisik(p: Dict[str, Any], pecahan: List[Dict[str, Any]]) -> float:
    total = _f(sum(x["subtotal"] for x in pecahan))
    if p.get("jumlah_fisik") is None or str(p.get("jumlah_fisik")).strip() == "":
        if not pecahan:
            raise _galat(400, PESAN_FISIK_WAJIB)
        return total
    try:
        fisik = _f(p.get("jumlah_fisik"))
    except (TypeError, ValueError):
        raise _galat(400, PESAN_FISIK_WAJIB) from None
    if fisik < 0:
        raise _galat(400, PESAN_FISIK_NEGATIF)
    if pecahan and abs(fisik - total) > EPS:
        raise _galat(400, f"Jumlah fisik {rupiah(fisik)} tidak sama dengan total rincian pecahan {rupiah(total)}. "
                          "Periksa lagi hitungannya.")
    return fisik


async def _tolak_bila_masih_menunggu(acc: Dict[str, Any]) -> None:
    lama = await db[COLL].find_one({"account_id": acc["id"], "status": MENUNGGU}, {"_id": 0, "number": 1, "id": 1})
    if lama:
        raise _galat(409, f"Opname {_nomor(lama)} untuk rekening {acc.get('name') or acc['id']} masih menunggu "
                          "keputusan selisih. Putuskan dulu (setujui atau tolak) sebelum menghitung ulang.")


async def buat(payload: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/cash-counts` — catat hitungan fisik; saldo buku dipotret sekarang. Selisih 0 → `selesai`; selain itu
    `menunggu_persetujuan` (pemegang `cash.approve` PT itu diberi tahu). PT = PT rekening (rute memastikan PT dalam
    penugasan)."""
    from core_utils import next_doc_number
    from services import bank_service as bs
    from services.book_date import tanggal_buku
    p = _isi(payload)
    # ── PERIKSA ──
    acc = await rekening_tunai(p.get("account_id"))
    pecahan = _pecahan(p.get("pecahan"))
    fisik = _jumlah_fisik(p, pecahan)
    await _tolak_bila_masih_menunggu(acc)
    eid = acc.get("entity_id") or ""
    buku = await saldo_buku(acc)            # POTRET saldo buku saat dihitung (§7.8.3)
    selisih = _f(fisik - buku)
    if abs(selisih) <= EPS:
        selisih = 0.0
    now = now_iso()
    penghitung = {"id": (actor or {}).get("id") or "", "name": (actor or {}).get("name") or ""}
    status = SELESAI if selisih == 0 else MENUNGGU
    doc: Dict[str, Any] = {
        "id": new_id("opk"), "number": "", "entity_id": eid, "status": status,
        "account_id": acc["id"], "account_name": acc.get("name") or "", "cash_type": bs.account_cash_type(acc),
        "tanggal": tanggal_buku(), "dihitung_pada": now, "saldo_buku": _f(buku), "jumlah_fisik": fisik,
        "pecahan": pecahan, "selisih": selisih, "selisih_nominal": _f(abs(selisih)),
        "arah_selisih": "" if selisih == 0 else ("lebih" if selisih > 0 else "kurang"),
        "catatan": str(p.get("catatan") or "").strip()[:500], "penghitung": penghitung,
        "perlakuan": "", "karyawan_id": "", "karyawan_nama": "", "karyawan_kode": "",
        "cash_id": "", "cash_number": "", "terbit_error": "", "alasan_tolak": "",
        "created_by": penghitung["name"], "created_by_id": penghitung["id"], "created_at": now, "updated_at": now,
        "jejak": [_jejak("hitung", actor, "tanpa selisih" if selisih == 0 else
                         f"selisih {rupiah(selisih)} menunggu persetujuan orang kedua")],
    }
    # ── NIAT ──
    doc["number"] = await next_doc_number(COLL, "number", "OPK-", entity_id=eid)
    await db[COLL].insert_one(dict(doc))
    if status == MENUNGGU:
        from services import notification_service as ns
        await _beritahu(ns.notify_opname_selisih_menunggu, doc)
    return await rincian(doc["id"])


# ── Pemberitahuan ────────────────────────────────────────────────────────────────────────────────────────────────────
async def _beritahu(coro_fn, *args, **kw) -> None:
    """Pemberitahuan sesudah keadaan tercatat: gagal apa pun hanya dicatat, tidak pernah menggagalkan tindakannya."""
    try:
        await coro_fn(*args, **kw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[cash_count] pemberitahuan gagal: %s", exc)


async def _beritahu_diputus(doc: Dict[str, Any], hasil: str, actor: Dict[str, Any], alasan: str = "",
                            kas_number: str = "") -> None:
    from services import notification_service as ns
    await _beritahu(ns.notify_opname_diputus, doc, hasil=hasil, oleh=actor or {}, alasan=alasan,
                    kas_number=kas_number)


# ── Setujui ──────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _karyawan(entity_id: str, karyawan_id: str) -> Dict[str, Any]:
    """Karyawan HR PT pemilik rekening (§7.8.6) — selain itu 400 berkalimat."""
    from services.cash_ledger import _nama_pt
    kid = (karyawan_id or "").strip()
    if not kid:
        raise _galat(400, PESAN_KARYAWAN_WAJIB)
    emp = await db.hr_employees.find_one({"id": kid}, {"_id": 0, "id": 1, "code": 1, "name": 1, "entity_id": 1})
    if not emp:
        raise _galat(400, PESAN_KARYAWAN_TIDAK_ADA)
    if (emp.get("entity_id") or "") != entity_id:
        raise _galat(400, f"{emp.get('name') or kid} bukan karyawan {await _nama_pt(entity_id)}. Pilih karyawan PT "
                          "pemilik rekening.")
    return emp


def _perlakuan(doc: Dict[str, Any], isian: Dict[str, Any]) -> str:
    pilih = str(isian.get("perlakuan") or "").strip()
    if pilih not in PERLAKUAN_LABEL:
        raise _galat(400, PESAN_PERLAKUAN)
    if pilih == P_PIUTANG and _f(doc.get("selisih")) > 0:
        raise _galat(400, PESAN_PIUTANG_LEBIH)
    return pilih


async def _pengganti(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Opname LEBIH BARU untuk rekening yang sama (dihitung sesudahnya, belum ditolak) — bila ada, opname `doc` sudah
    digantikan: selisih rekening diputus dari opname terbaru (dua opname menunggu tidak pernah dibukukan dua kali)."""
    kunci = (doc.get("dihitung_pada") or "", _nomor(doc))
    rows = await db[COLL].find({"account_id": doc.get("account_id") or "__none__", "id": {"$ne": doc["id"]},
                                "status": {"$in": list(TERHITUNG)},
                                "dihitung_pada": {"$gte": doc.get("dihitung_pada") or ""}},
                               {"_id": 0, "id": 1, "number": 1, "dihitung_pada": 1}).to_list(50)
    baru = [r for r in rows if (r.get("dihitung_pada") or "", _nomor(r)) > kunci]
    return max(baru, key=lambda r: (r.get("dihitung_pada") or "", _nomor(r))) if baru else None


def _rencana(doc: Dict[str, Any], perlakuan: str, emp: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Kas penyesuaian dari selisih YANG DIPOTRET. Murni."""
    from services import gl_service as gl
    selisih = _f(doc.get("selisih"))
    nomor, rek = _nomor(doc), doc.get("account_name") or ""
    if selisih > 0:
        arah, kata = "in", "Kelebihan"
    else:
        arah, kata = "out", "Kekurangan"
    ket = f"{kata} kas opname {nomor} ({rek})"
    if perlakuan == P_PIUTANG:
        lawan, kategori = gl.ACC_PIUTANG_KURANG_KAS, "piutang karyawan"
        ket += f" — piutang karyawan {(emp or {}).get('name') or ''} ({(emp or {}).get('code') or ''})"
    else:
        lawan, kategori = gl.ACC_SELISIH_KAS, "selisih kas"
    return {"direction": arah, "amount": _f(abs(selisih)), "contra": lawan, "category": kategori, "description": ket}


async def _periksa_terbit(doc: Dict[str, Any], rencana: Dict[str, Any]) -> None:
    """PERIKSA ulang tanpa tulisan sebelum kas terbit: rekening masih aktif milik PT, jurnal (akun aktif, periode tanggal
    hitung) lolos pemeriksa yang sama dengan `_insert_entry`. Gagal → 409 berkalimat; opname tetap menunggu."""
    from services import cash_ledger as cl
    from services import gl_service as gl
    eid, nomor, tgl = doc.get("entity_id") or "", _nomor(doc), doc.get("tanggal") or ""
    tetap = "Opname tetap menunggu."
    try:
        rek = await cl.periksa_rekening(eid, doc.get("account_id") or "", doc.get("cash_type") or "")
    except cl.CashRejected as exc:
        raise _galat(409, f"{exc.detail} {tetap}") from exc
    kas = rek["account_code"]
    dr, cr = (kas, rencana["contra"]) if rencana["direction"] == "in" else (rencana["contra"], kas)
    lines = [{"account_code": dr, "debit": rencana["amount"], "credit": 0.0, "description": rencana["description"]},
             {"account_code": cr, "debit": 0.0, "credit": rencana["amount"], "description": rencana["description"]}]
    try:
        await gl.preflight_entry(lines=lines, entity_id=eid, date=tgl, source_type="cash_transaction")
    except gl.ClosedPeriodError as exc:
        raise _galat(409, f"{exc} Selisih opname {nomor} dibukukan pada tanggal hitung ({tgl}); buka kembali periode "
                          f"itu atau tolak opname ini lalu hitung ulang. {tetap}") from exc
    except ValueError as exc:   # JournalValidationError dkk.
        raise _galat(409, f"Jurnal selisih opname {nomor} belum bisa diterbitkan: {exc} {tetap}") from exc


async def _tolak_bila_kas_lain(doc: Dict[str, Any], perlakuan: str, emp: Optional[Dict[str, Any]]) -> None:
    """Persetujuan yang terhenti SESUDAH kas penyesuaian tercatat (kunci dilepas admin) diteruskan dengan Setujui ulang
    (kas yang sama, id tetap dari rujukan). Perlakuan/karyawan yang berbeda dari kas itu → 409: kas yang ada tidak
    diubah diam-diam dan dokumen tidak mencatat perlakuan yang berbeda dari jurnalnya."""
    kas = await db.cash_transactions.find_one({"ref_type": REF_TYPE, "ref_id": doc["id"], "status": {"$ne": "void"}},
                                              {"_id": 0, "number": 1, "perlakuan": 1, "karyawan_id": 1})
    if not kas:
        return
    if (kas.get("perlakuan") or "") != perlakuan or (kas.get("karyawan_id") or "") != ((emp or {}).get("id") or ""):
        lama = PERLAKUAN_LABEL.get(kas.get("perlakuan") or "", kas.get("perlakuan") or "-").lower()
        raise _galat(409, f"Kas penyesuaian {kas.get('number', '')} dari opname {_nomor(doc)} sudah tercatat dengan "
                          f"perlakuan {lama}. Setujui ulang dengan perlakuan (dan karyawan) yang sama untuk menuntaskan "
                          f"opname ini, lalu pakai Batalkan opname {_nomor(doc)} di Opname Kas bila perlakuannya "
                          "keliru.")


async def _tolak_bila_digantikan(doc: Dict[str, Any]) -> None:
    baru = await _pengganti(doc)
    if baru:
        raise _galat(409, f"Opname {_nomor(doc)} sudah digantikan opname {_nomor(baru)} yang dihitung sesudahnya. "
                          "Tolak opname ini; selisih rekening diputus dari opname terbaru.")


async def _klaim(doc: Dict[str, Any], aksi: str, langkah: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """KLAIM berprasyarat status `menunggu_persetujuan`. Kalah karena status sudah berubah → 409 yang menyebut keadaan
    barunya; sedang diproses orang lain → 409 `SAGA_IN_PROGRESS` dari `atomic_claim`."""
    from services import atomic_claim as _saga
    try:
        return await _saga.claim(COLL, doc["id"], langkah, precondition={"status": MENUNGGU},
                                 actor=(actor or {}).get("name") or "", detail=_pesan_berubah(doc))
    except HTTPException as exc:
        segar = await db[COLL].find_one({"id": doc["id"]}, {"_id": 0}) or {}
        if isinstance(exc.detail, str) and segar.get("status") in (DISETUJUI, DITOLAK, SELESAI, BATAL):
            raise _galat(409, _pesan_status(segar, aksi)) from exc
        raise


async def setujui(count_id: str, payload: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/cash-counts/{id}/approve` — orang kedua memilih perlakuan selisih; kas penyesuaian terbit sebesar
    selisih yang dipotret. Juga meneruskan opname yang kasnya gagal terbit (`terbit_error`)."""
    from services import atomic_claim as _saga
    from services import cash_ledger
    from services import dual_control
    isian = _isi(payload)
    doc = await _ambil(count_id)
    if doc.get("status") != MENUNGGU:
        raise _galat(409, _pesan_status(doc, "setujui"))
    eid = doc.get("entity_id") or ""
    try:
        await dual_control.tolak_bila_pelaku_sama("selisih_kas", doc, actor, eid, pengaju=_penghitung(doc))
    except HTTPException as exc:
        if exc.status_code == 403:
            raise _galat(403, PESAN_ORANG_KEDUA) from exc
        raise
    # ── PERIKSA ──
    perlakuan = _perlakuan(doc, isian)
    emp = await _karyawan(eid, isian.get("karyawan_id")) if perlakuan == P_PIUTANG else None
    await _tolak_bila_digantikan(doc)
    await _tolak_bila_kas_lain(doc, perlakuan, emp)
    rencana = _rencana(doc, perlakuan, emp)
    await _periksa_terbit(doc, rencana)
    # ── KLAIM ──
    lk = await _klaim(doc, "setujui", "cash_count_approve", actor)
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    nama, nama_id = (actor or {}).get("name") or "", (actor or {}).get("id") or ""
    try:
        await _tolak_bila_digantikan(lk)   # opname baru di sela PERIKSA dan KLAIM (kunci dilepas di `finally`)
        await _tolak_bila_kas_lain(lk, perlakuan, emp)
        now = now_iso()
        karyawan = {"karyawan_id": (emp or {}).get("id") or "", "karyawan_nama": (emp or {}).get("name") or "",
                    "karyawan_kode": (emp or {}).get("code") or ""}
        try:
            kas = await cash_ledger.create_cash(
                entity_id=eid, direction=rencana["direction"], amount=rencana["amount"], ref_type=REF_TYPE,
                ref_id=lk["id"], account_id=lk.get("account_id") or "", cash_type=lk.get("cash_type") or "",
                txn_date=lk.get("tanggal") or "", category=rencana["category"], description=rencana["description"],
                actor=(lk.get("penghitung") or {}).get("name") or "system",   # pembuat kas = penghitung
                contra_account_code=rencana["contra"],
                extra={"cash_count_number": _nomor(lk), "perlakuan": perlakuan, **karyawan,
                       "disetujui_oleh": nama, "disetujui_oleh_id": nama_id, "disetujui_pada": now})
        except cash_ledger.CashPostingError as exc:
            kas = exc.txn   # kas TETAP tercatat (jurnal gagal → Posting Gagal); opname tetap disetujui
        except cash_ledger.CashRejected as exc:
            await db[COLL].update_one({"id": count_id, f"{_saga.LOCK}.token": token}, {"$set": {
                "terbit_error": str(exc.detail)[:300], "updated_at": now_iso()}})
            raise _galat(409, f"Kas penyesuaian opname {_nomor(lk)} belum terbit: {exc.detail} Opname tetap menunggu; "
                              "ulangi lewat Setujui atau tolak opname ini.") from exc
        upd = _saga.finish_set({
            "status": DISETUJUI, "perlakuan": perlakuan, **karyawan, "cash_id": kas.get("id") or "",
            "cash_number": kas.get("number") or "", "disetujui_oleh": nama, "disetujui_oleh_id": nama_id,
            "disetujui_pada": now, "terbit_error": "", "updated_at": now_iso()})
        catatan = f"{PERLAKUAN_LABEL[perlakuan].lower()} · kas {kas.get('number') or ''}".strip()
        upd["$push"] = {"jejak": _jejak("setujui", actor, catatan)}
        await db[COLL].update_one({"id": count_id, f"{_saga.LOCK}.token": token}, upd)
    finally:
        await _saga.release(COLL, count_id, token)
    await _beritahu_diputus(doc, DISETUJUI, actor, kas_number=kas.get("number") or "")
    return await rincian(count_id)


# ── Tolak ────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _tolak_bila_kas_terbit(doc: Dict[str, Any]) -> None:
    """Opname yang kas penyesuaiannya sudah ada (persetujuan terhenti sesudah kas tercatat) tidak ditolak: Setujui ulang
    menuntaskannya (kas yang sama), lalu Batal opname membalik kasnya bila perlu (kas opname tidak dibatalkan dari
    Transaksi Kas — FN-07)."""
    kas = await db.cash_transactions.find_one({"ref_type": REF_TYPE, "ref_id": doc["id"], "status": {"$ne": "void"}},
                                              {"_id": 0, "number": 1})
    if kas:
        raise _galat(409, f"Kas {kas.get('number', '')} dari opname {_nomor(doc)} sudah tercatat. Setujui ulang untuk "
                          f"menuntaskan opname ini, lalu pakai Batalkan opname {_nomor(doc)} di Opname Kas bila perlu.")


async def tolak(count_id: str, alasan: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/cash-counts/{id}/reject` — alasan ≥ 5 huruf; tanpa kas; bukan penghitung (kontrol `selisih_kas`, sama
    dengan Setujui). PERIKSA (belum ada kas) → KLAIM status menunggu → kas dibaca ulang SESUDAH klaim → selesai."""
    from services import atomic_claim as _saga
    from services import dual_control
    teks = (alasan or "").strip()
    if len(teks) < ALASAN_MIN:
        raise _galat(400, PESAN_ALASAN_TOLAK)
    doc = await _ambil(count_id)
    if doc.get("status") != MENUNGGU:
        raise _galat(409, _pesan_status(doc, "tolak"))
    try:
        await dual_control.tolak_bila_pelaku_sama("selisih_kas", doc, actor, doc.get("entity_id") or "",
                                                  pengaju=_penghitung(doc))
    except HTTPException as exc:
        if exc.status_code == 403:
            raise _galat(403, PESAN_TOLAK_SENDIRI) from exc
        raise
    await _tolak_bila_kas_terbit(doc)
    lk = await _klaim(doc, "tolak", "cash_count_reject", actor)
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    try:
        await _tolak_bila_kas_terbit(lk)   # selama kunci dipegang tidak ada kas baru untuk opname ini
        upd = _saga.finish_set({
            "status": DITOLAK, "alasan_tolak": teks[:500], "ditolak_oleh": (actor or {}).get("name") or "",
            "ditolak_oleh_id": (actor or {}).get("id") or "", "ditolak_pada": now_iso(), "updated_at": now_iso()})
        upd["$push"] = {"jejak": _jejak("tolak", actor, teks[:500])}
        await db[COLL].update_one({"id": count_id, f"{_saga.LOCK}.token": token}, upd)
    finally:
        await _saga.release(COLL, count_id, token)
    await _beritahu_diputus(doc, DITOLAK, actor, teks[:500])
    return await rincian(count_id)


# ── Batal ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _pesan_batal_status(doc: Dict[str, Any]) -> str:
    """Batal atas opname yang tidak `disetujui` (dan bukan batal yang pembaliknya tertunda)."""
    nomor, st = _nomor(doc), doc.get("status")
    if st == MENUNGGU:
        return (f"Opname kas {nomor} masih menunggu keputusan selisih, jadi belum ada yang bisa dibatalkan. Tolak opname "
                "ini dengan alasan bila hitungannya keliru.")
    if st == SELESAI:
        return (f"Opname kas {nomor} selesai tanpa selisih dan tanpa kas penyesuaian, jadi tidak ada yang "
                "dibatalkan.")
    if st == BATAL:
        return f"Opname kas {nomor} sudah dibatalkan."
    return f"Opname kas {nomor} sudah {STATUS_LABEL.get(st, st or '').lower()}, jadi tidak bisa dibatalkan."


async def _kas_hidup(count_id: str) -> List[Dict[str, Any]]:
    """Kas penyesuaian opname yang belum dibalik (tidak `void`)."""
    return [t async for t in db.cash_transactions.find({"ref_type": REF_TYPE, "ref_id": count_id or "__none__",
                                                        "status": {"$ne": "void"}}, {"_id": 0}).sort("created_at", 1)]


def _tolak_bila_tercocok(kas: List[Dict[str, Any]], nomor: str) -> None:
    """Kas yang sudah dicocokkan dengan mutasi bank (`reconciled_amount` > 0, PK-21) tidak dibalik dari sini."""
    for t in kas:
        if _f(t.get("reconciled_amount")) > 0:
            raise _galat(409, f"Kas {t.get('number', '')} dari opname {nomor} sudah dicocokkan dengan mutasi bank — "
                              "lepas dulu di Rekonsiliasi, lalu batalkan.")


async def _periksa_pembalik(doc: Dict[str, Any], kas: List[Dict[str, Any]]) -> None:
    """PERIKSA tanpa tulisan sebelum kas dibalik (pola `fund_transfer_service._periksa_pembalik`): belum tercocok mutasi
    bank; periode tanggal pembalik terbuka; baris pembaliknya (akun kas dialihkan seperti `_reverse_once_ex`, akun lawan
    aktif) lolos pemeriksa jurnal. Gagal → 409 berkalimat; opname tetap disetujui."""
    from services import gl_service as gl
    from services.book_date import tanggal_buku
    from services.posting_registry import tanggal_pembalik
    eid, nomor, tetap = doc.get("entity_id") or "", _nomor(doc), "Opname tetap disetujui."
    _tolak_bila_tercocok(kas, nomor)
    for t in kas:
        tgl = tanggal_pembalik(t.get("txn_date"))
        je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": t["id"],
                                                "status": {"$ne": "void"}}, {"_id": 0})
        try:
            if not je:
                await gl.preflight_posting(eid, tgl or now_iso())
                continue
            alih = await gl.baris_kas_rekening(je)
            lines = [{"account_code": (alih.get(i) or {}).get("akun") or ln["account_code"],
                      "debit": float(ln.get("credit") or 0), "credit": float(ln.get("debit") or 0),
                      "description": ln.get("description", "")} for i, ln in enumerate(je.get("lines") or [])]
            await gl.preflight_entry(lines=lines, entity_id=je.get("entity_id") or eid, date=tgl or now_iso(),
                                     source_type="cash_transaction_void")
        except gl.ClosedPeriodError as exc:
            raise _galat(409, f"{exc} Kas penyesuaian {t.get('number', '')} dari opname {nomor} dibalik pada tanggal "
                              f"{tgl or tanggal_buku()}; buka kembali periode itu lalu batalkan lagi. {tetap}") from exc
        except ValueError as exc:   # JournalValidationError dkk. (mis. akun lawan nonaktif)
            raise _galat(409, f"Jurnal pembalik kas {t.get('number', '')} dari opname {nomor} belum bisa diterbitkan: "
                              f"{exc} {tetap}") from exc


async def _balik_kas(doc: Dict[str, Any], kas: List[Dict[str, Any]], actor: Dict[str, Any]) -> List[str]:
    """Balik tiap kas penyesuaian lewat pembalik kas yang ada (pintu tahan-gagal) lalu tandai `void`. Gagal →
    `batal_gl_status: failed` di opname + 409 (kas yang sudah dibalik tetap dibalik; ulang meneruskan sisanya)."""
    from services import cash_ledger
    from services import gl_service as gl
    from services.posting_registry import tanggal_pembalik
    nama = (actor or {}).get("name") or "system"
    alasan, nomor = doc.get("alasan_batal") or "", _nomor(doc)
    label = f"batal opname {nomor}"
    hasil: List[str] = []
    for t in kas:
        cid = t["id"]
        try:
            await cash_ledger.ensure_posted(cid)   # jurnal asal yang gagal (Posting Gagal) diterbitkan dulu, lalu dibalik
            res = await gl.post_durable(
                "cash_transactions", cid,
                lambda cid=cid, tgl=tanggal_pembalik(t.get("txn_date")): gl.post_cash_void(
                    cid, label=label, created_by=nama, date=tgl),
                source_type="cash_transaction_void", source_id=cid, field="void_gl_status", raise_on_fail=True)
            rev = res.get("journal") or ({"id": res["journal_entry_id"]} if res.get("journal_entry_id") else {})
            await db.cash_transactions.update_one({"id": cid, "status": {"$ne": "void"}}, {"$set": {
                "status": "void", "void_journal_entry_id": rev.get("id", ""), "void_reason": alasan,
                "voided_by": nama, "voided_at": now_iso(), "updated_at": now_iso()}})
            hasil.append(rev.get("id", ""))
        except Exception as exc:  # noqa: BLE001 — jurnal pembalik gagal: opname tetap batal, sisa kas diteruskan nanti
            pesan = getattr(exc, "error", None) or str(exc) or exc.__class__.__name__
            await db[COLL].update_one({"id": doc["id"]}, {"$set": {
                "batal_gl_status": "failed", "batal_gl_error": f"{t.get('number', '')}: {pesan}"[:300],
                "batal_gl_failed_at": now_iso(), "updated_at": now_iso()}})
            raise _galat(409, f"Opname kas {nomor} sudah dibatalkan, tetapi jurnal pembalik kas {t.get('number', '')} "
                              f"gagal: {pesan}. Ulangi dari Keuangan › Posting Gagal.") from exc
    return hasil


async def batal(count_id: str, alasan: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/cash-counts/{id}/batal` — batalkan putusan opname `disetujui` beralasan: kas penyesuaiannya dibalik.
    Opname batal yang pembaliknya belum tuntas → diteruskan (tanpa kontrol ulang: putusannya sudah tercatat).

    Urutan (pola `fund_transfer_service.batal`): PERIKSA (alasan, status, kontrol `selisih_kas` — bukan penghitung —,
    rekonsiliasi, periode & jurnal pembalik) → KLAIM berprasyarat status YANG DIPERIKSA (Batal bersamaan / putusan lain
    di sela → 409 muat ulang) → kas dibaca ulang SESUDAH klaim (himpunan berbeda → 409) → NIAT `batal` (alasan, oleh,
    `batal_gl_status: pending`) → EFEK pembalik tiap kas → SELESAI (`finish_set`, `batal_gl_status: posted`)."""
    from services import atomic_claim as _saga
    from services import dual_control
    teks = (alasan or "").strip()
    if len(teks) < ALASAN_MIN:
        raise _galat(400, PESAN_ALASAN_BATAL)
    doc = await _ambil(count_id)
    eid = doc.get("entity_id") or ""
    lanjut = doc.get("status") == BATAL and doc.get("batal_gl_status") in ("pending", "failed")
    # ── PERIKSA ──
    if doc.get("status") != DISETUJUI and not lanjut:
        raise _galat(409, _pesan_batal_status(doc))
    if not lanjut:
        try:
            await dual_control.tolak_bila_pelaku_sama("selisih_kas", doc, actor, eid, pengaju=_penghitung(doc))
        except HTTPException as exc:
            if exc.status_code == 403:
                raise _galat(403, PESAN_BATAL_SENDIRI) from exc
            raise
    kas = await _kas_hidup(count_id)
    await _periksa_pembalik(doc, kas)
    # ── KLAIM (status persis seperti yang diperiksa) ──
    nama, nama_id = (actor or {}).get("name") or "", (actor or {}).get("id") or ""
    syarat = ({"status": BATAL, "batal_gl_status": doc.get("batal_gl_status")} if lanjut
              else {"status": DISETUJUI})
    try:
        lk = await _saga.claim(COLL, count_id, "cash_count_cancel", precondition=syarat, actor=nama,
                               detail=_pesan_berubah(doc))
    except HTTPException as exc:
        segar = await db[COLL].find_one({"id": count_id}, {"_id": 0}) or {}
        if isinstance(exc.detail, str) and segar.get("status") == BATAL and not lanjut:
            raise _galat(409, _pesan_batal_status(segar)) from exc   # batal lain menang lebih dulu
        raise
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    gagal: Optional[HTTPException] = None
    baru = False
    try:
        segar = await _kas_hidup(count_id)
        if {t["id"] for t in segar} != {t["id"] for t in kas}:
            raise _galat(409, _pesan_berubah(doc))   # kunci dilepas di `finally`; belum ada yang ditulis
        _tolak_bila_tercocok(segar, _nomor(doc))
        kas = segar
        if not lanjut:
            niat = {"status": BATAL, "status_sebelum_batal": lk.get("status"), "alasan_batal": teks[:500],
                    "dibatalkan_oleh": nama, "dibatalkan_oleh_id": nama_id, "dibatalkan_pada": now_iso(),
                    "batal_gl_status": "pending" if kas else "", "batal_gl_error": "", "updated_at": now_iso()}
            await db[COLL].update_one({"id": count_id, f"{_saga.LOCK}.token": token},
                                      {"$set": niat, "$push": {"jejak": _jejak("batal", actor, teks[:500])}})
            lk = {**lk, **niat}
            baru = True
        try:
            balik = await _balik_kas(lk, kas, actor)
        except HTTPException as exc:
            gagal = exc   # opname tetap batal, `batal_gl_status: failed` (Posting Gagal); kunci dilepas di `finally`
        else:
            upd = _saga.finish_set({"batal_gl_status": "posted" if (kas or lanjut) else "", "batal_gl_error": "",
                                    "batal_selesai_pada": now_iso(), "updated_at": now_iso()})
            if balik:
                upd["$push"] = {"void_journal_entry_ids": {"$each": [j for j in balik if j]}}
            if lanjut:
                upd.setdefault("$push", {})["jejak"] = _jejak("batal_diteruskan", actor)
            await db[COLL].update_one({"id": count_id}, upd)
    finally:
        await _saga.release(COLL, count_id, token)
    if baru:   # putusan batal sudah tercatat (juga bila pembaliknya masih harus diulang)
        await _beritahu_diputus(lk, "dibatalkan", actor, teks[:500],
                                kas_number=", ".join(t.get("number") or "" for t in kas))
    if gagal is not None:
        raise gagal
    return await rincian(count_id)


async def lanjut_batal(count_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Panel Posting Gagal jenis `cash_count_cancel`: teruskan pembalik kas opname batal yang belum tuntas."""
    doc = await _ambil(count_id)
    return await batal(count_id, doc.get("alasan_batal") or "diteruskan dari Posting Gagal", actor)


# ── Pemilih karyawan (piutang karyawan) ──────────────────────────────────────────────────────────────────────────────
#: Status karyawan yang tidak ditawarkan sebagai penanggung kekurangan kas (sudah keluar).
_KARYAWAN_KELUAR = ("resigned", "terminated", "inactive", "keluar", "nonaktif")


async def karyawan(entity_id: str, q: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    """`GET /api/cash-counts/karyawan` — karyawan HR PT pemilik rekening (id, kode, nama) untuk perlakuan piutang
    karyawan; tanpa data pribadi lain (penyetuju kas tidak harus memegang izin SDM)."""
    query: Dict[str, Any] = {"entity_id": entity_id or "__none__", "status": {"$nin": list(_KARYAWAN_KELUAR)}}
    teks = (q or "").strip()
    if teks:
        rx = {"$regex": re.escape(teks), "$options": "i"}
        query["$or"] = [{"name": rx}, {"code": rx}]
    rows = await db.hr_employees.find(query, {"_id": 0, "id": 1, "code": 1, "name": 1}) \
        .sort([("name", 1), ("id", 1)]).to_list(max(1, min(int(limit or 50), MAX_PAGE_SIZE)))
    return [{"id": r["id"], "code": r.get("code") or "", "name": r.get("name") or ""} for r in rows]


# ── Pengingat opname (antrean Meja Keuangan) ─────────────────────────────────────────────────────────────────────────
async def ensure_aktif_sejak() -> str:
    """§7.8.8 — tulis waktu aktif pengingat opname SEKALI (saat backend pertama menyala); panggilan berikutnya tidak
    menimpa. Pola `bank_auto_receipt_service.ensure_aktif_sejak`: dibaca dulu, ditulis hanya bila kuncinya belum ada,
    pada dokumen `__migrations__` (tanpa dokumen penanda kedua)."""
    penanda = {"scope": "__migrations__"}
    doc = await db.system_settings.find_one(penanda, {"_id": 0, PENANDA_AKTIF: 1})
    if doc is None:
        await db.system_settings.update_one(penanda, {"$set": {PENANDA_AKTIF: now_iso()}}, upsert=True)
    elif not doc.get(PENANDA_AKTIF):
        await db.system_settings.update_one({**penanda, PENANDA_AKTIF: {"$in": [None, ""]}},
                                            {"$set": {PENANDA_AKTIF: now_iso()}})
    return await aktif_sejak()


async def aktif_sejak() -> str:
    """Waktu aktif pengingat opname (ISO); kosong bila belum pernah ditulis (pengingat tidak berjalan)."""
    doc = await db.system_settings.find_one({"scope": "__migrations__"}, {"_id": 0, PENANDA_AKTIF: 1}) or {}
    return doc.get(PENANDA_AKTIF) or ""


def _waktu(iso: Any) -> Optional[datetime]:
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


async def jatuh_tempo(entity_ids: List[str]) -> List[Dict[str, Any]]:
    """Rekening tunai aktif PT dalam cakupan yang opnamenya jatuh tempo: opname terakhir yang terhitung (selesai /
    menunggu / disetujui) — atau, bila belum pernah, waktu fitur aktif — lebih lama dari jarak opname jenis kasnya
    (`bank_service.hari_opname`), dan rekening itu punya kas yang dicatat sesudah fitur aktif. Urut paling lama dulu.
    → `[{account, cash_type, jarak_hari, saldo_buku, dasar, jatuh_tempo, hari_lewat, opname_terakhir}]`."""
    from services import bank_service as bs
    aktif = _waktu(await aktif_sejak())
    if aktif is None or not entity_ids:
        return []
    sekarang = datetime.now(timezone.utc)
    out: List[Dict[str, Any]] = []
    async for acc in db.bank_accounts.find({"entity_id": {"$in": list(entity_ids)}, "account_type": "cash"},
                                           {"_id": 0}).sort("created_at", 1):
        if not bs._aktif(acc):
            continue
        txns = await bs._txns_for(acc["id"])
        if not any((_waktu(t.get("created_at")) or aktif) >= aktif for t in txns if t.get("created_at")):
            continue   # rekening tanpa kas sesudah fitur aktif tidak diingatkan
        ct = bs.account_cash_type(acc)
        jarak = await bs.hari_opname(acc.get("entity_id") or "", ct)
        terakhir = await db[COLL].find_one({"account_id": acc["id"], "status": {"$in": list(TERHITUNG)}},
                                           {"_id": 0, "id": 1, "number": 1, "dihitung_pada": 1},
                                           sort=[("dihitung_pada", -1)])
        dasar = max(aktif, _waktu((terakhir or {}).get("dihitung_pada")) or aktif)
        tempo = dasar + timedelta(days=jarak)
        if sekarang <= tempo:
            continue
        out.append({"account": acc, "cash_type": ct, "jarak_hari": jarak,
                    "saldo_buku": bs._balance(float(acc.get("opening_balance") or 0), txns),
                    "dasar": dasar.isoformat(), "jatuh_tempo": tempo.isoformat(),
                    "hari_lewat": (sekarang - tempo).days, "opname_terakhir": terakhir})
    return sorted(out, key=lambda r: r["jatuh_tempo"])

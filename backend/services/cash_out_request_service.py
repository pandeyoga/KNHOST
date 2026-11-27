"""Kas & Bank bagian 2 (C6) — **pengajuan kas keluar manual** (`cash_out_requests`, nomor `PKK-`).

Kas KELUAR manual dengan nominal di atas batas PT (kontrol `kontrol.kas_keluar_manual`, bawaan satu orang dengan batas
Rp 1.000.000; "di atas" = lebih dari — `dual_control.butuh_orang_kedua`; `min_orang` "2" = semua kas keluar manual)
tidak langsung menjadi kas: ia disimpan sebagai pengajuan dan baru terbit sebagai kas + jurnal lewat pintu kas tunggal
`cash_ledger.create_cash` sesudah ORANG KEDUA menyetujuinya.

Rancangan: `docs/superpowers/specs/2026-11-27-kas-bank-2-kas-manual-design.md` §5.2, §6, §7 (butir 7.8: 1, 3, 4, 5, 6).

* **Ajukan** — rute `POST /api/cash-transactions` (`routers/cash.py create_cash_transaction`) menjalankan SEMUA
  pemeriksaan kas langsung (kategori, rujukan, rekening, periode, anggaran) lalu, bila arah keluar dan butuh orang
  kedua, memanggil `ajukan` → 202 `{"request": …}`. Tidak ada kas dan tidak ada jurnal: pengajuan bukan dokumen kas,
  jadi tidak terhitung di saldo kas, daftar/ringkasan Transaksi Kas, maupun buku kas rekening.
* **Idempotency-Key** — unik per PT (id pengajuan diturunkan dari PT + kunci dan disisip `$setOnInsert`; indeks wajib
  `uq_cor_idem_key`). Kiriman ulang berkunci sama → pengajuan yang SAMA dalam keadaan terkini (termasuk tautan kas bila
  sudah disetujui), tidak pernah pengajuan kedua atau kas langsung (§7.8.5); isi berbeda dengan kunci sama → 409.
  Jawaban 202 membawa `X-Idempotency-Retry` supaya penyangga idempotensi tidak memutar jawaban lama yang basi.
* **Setujui** (`cash.approve`) — pengaju tidak boleh menyetujui sendiri (`dual_control.tolak_bila_pelaku_sama`,
  penilaian dua orang DIBEKUKAN: batas tidak dinilai ulang, §7.8.3); Admin pun tidak (bawaan
  `kontrol.admin_tetap_dua_orang`, §7 butir 4 — tetap pengaturan). PERIKSA ulang tanpa tulisan: kategori masih boleh,
  rekening aktif milik PT, periode tanggal kas terbuka, anggaran (yang menentukan — tidak dicadangkan saat diajukan,
  §7.8.4); gagal → 409 berkalimat, pengajuan tetap menunggu, tanpa kas. KLAIM berprasyarat status →
  `create_cash(ref_type="manual", ref_id=<id pengajuan>)` bertanggal tanggal yang diajukan (§7 butir 5); pembuat kas =
  pengaju, penyetuju di `disetujui_oleh`. Kas ditolak di
  tengah → tetap menunggu dengan `terbit_error`, bisa disetujui lagi (id kas tetap dari rujukan → tidak ganda). Jurnal
  gagal → kas tetap tercatat (Posting Gagal › Transaksi Kas), pengajuan tetap disetujui.
* **Tolak** (`cash.approve`, alasan ≥ 5 huruf, bukan pengaju) → `ditolak`. **Batal** (pengaju, atau pemegang
  `cash.delete` — dijaga rute) selama menunggu → `dibatalkan`.

Urutan tiap aksi (`02_STANDAR.md` §1): PERIKSA tanpa tulisan → KLAIM (`atomic_claim.claim` berprasyarat status yang
diperiksa) → EFEK → SELESAI (`finish_set`, kunci dicabut). Kalah klaim karena status sudah berubah → 409 yang menyebut
keadaan barunya; kas dibaca ulang sesudah klaim (pola Pindah Dana 479d0af).
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from starlette.responses import JSONResponse

from core_utils import new_id, now_iso, safe_doc
from db import db

COLL = "cash_out_requests"
AKSI = "kas_keluar_manual"
MENUNGGU, DISETUJUI, DITOLAK, DIBATALKAN = "menunggu_persetujuan", "disetujui", "ditolak", "dibatalkan"
STATUS_LABEL = {MENUNGGU: "Menunggu persetujuan", DISETUJUI: "Disetujui", DITOLAK: "Ditolak", DIBATALKAN: "Dibatalkan"}
ALASAN_MIN = 5   # K-14 (26 Okt) — alasan minimum seragam 5 huruf
EPS = 0.005
#: Header penyangga idempotensi (`idempotency.RETRY_HEADER`): jawaban tidak disimpan, kiriman ulang dijawab layanan.
HEADER_ULANG = {"X-Idempotency-Retry": "true"}

PESAN_TIDAK_ADA = "Pengajuan kas keluar tidak ditemukan."
PESAN_ALASAN_TOLAK = f"Alasan penolakan wajib diisi (minimal {ALASAN_MIN} huruf)."
#: Sama persis dengan penyangga idempotensi (`idempotency.py`, IDEMPOTENCY_KEY_REUSED).
PESAN_KUNCI_BEDA = "Kunci idempotensi sudah dipakai untuk isi permintaan yang berbeda."
#: §7.8.1 — tanpa jalan pintas: minta orang lain yang berizin; batas/aturan bisa diubah Admin di Pusat Pengaturan.
PESAN_ORANG_KEDUA = ("Kas keluar manual ini harus disetujui orang lain: Anda yang mengajukannya. Minta orang lain yang "
                     "berizin menyetujui kas. Admin dapat menaikkan batas atau mengubah aturan ini di Pengaturan › "
                     "Persetujuan › Kontrol dua orang.")
PESAN_TOLAK_SENDIRI = "Pengajuan ini Anda ajukan sendiri, jadi tidak bisa Anda tolak. Pakai Batal bila tidak jadi."
PESAN_BATAL_TANPA_IZIN = "Hanya pengaju atau pemegang akses membatalkan kas yang bisa membatalkan pengajuan ini."
_KATA_AKSI = {"setujui": "disetujui", "tolak": "ditolak", "batal": "dibatalkan"}


def _galat(status: int, pesan: str, headers: Optional[Dict[str, str]] = None) -> HTTPException:
    return HTTPException(status_code=status, detail=pesan, headers=headers)


def _f(x: Any) -> float:
    return round(float(x or 0), 2)


def _jejak(aksi: str, actor: Dict[str, Any], catatan: str = "") -> Dict[str, Any]:
    return {"aksi": aksi, "oleh": (actor or {}).get("name", ""), "oleh_id": (actor or {}).get("id", ""),
            "pada": now_iso(), "catatan": catatan}


def _pengaju(doc: Dict[str, Any]) -> List[str]:
    """Pembanding kontrol dua orang = pengaju (id; nama hanya bila id kosong — nama bisa kembar)."""
    p = doc.get("pengaju") or {}
    return [p.get("id") or p.get("name") or ""]


def pengaju_sendiri(doc: Dict[str, Any], actor: Dict[str, Any]) -> bool:
    """Apakah `actor` = pengaju pengajuan ini (dicocokkan lewat pembantu kontrol dua orang yang sama)."""
    from services import dual_control
    return dual_control.pelaku_sama(doc or {}, actor or {}, _pengaju(doc or {}))


def _nomor(doc: Dict[str, Any]) -> str:
    return doc.get("number") or doc.get("id") or ""


def _pesan_status(doc: Dict[str, Any], aksi: str) -> str:
    """Aksi `setujui` | `tolak` | `batal` atas pengajuan yang tidak lagi menunggu."""
    st = doc.get("status")
    kata = _KATA_AKSI[aksi]
    label = STATUS_LABEL.get(st, st or "").lower()
    lagi = " lagi" if kata == label else ""
    teks = f"Pengajuan kas keluar {_nomor(doc)} sudah {label}, jadi tidak bisa {kata}{lagi}."
    if st == DISETUJUI and aksi == "batal":
        teks += f" Batalkan kasnya ({doc.get('cash_number') or doc.get('cash_id')}) dari Transaksi Kas bila perlu."
    return teks


def _pesan_berubah(doc: Dict[str, Any]) -> str:
    """Kalah klaim (keadaan berubah di antara PERIKSA dan KLAIM, mis. sedang diproses orang lain)."""
    return f"Pengajuan kas keluar {_nomor(doc)} baru saja diubah orang lain. Muat ulang lalu periksa."


async def _ambil(rid: str) -> Dict[str, Any]:
    doc = await db[COLL].find_one({"id": rid or "__none__"}, {"_id": 0})
    if not doc:
        raise _galat(404, PESAN_TIDAK_ADA)
    return doc


# ── Pembentuk jawaban ────────────────────────────────────────────────────────────────────────────────────────────────
def _bentuk(doc: Dict[str, Any]) -> Dict[str, Any]:
    d = safe_doc(dict(doc))
    d.pop("saga_lock", None)
    d.pop("sidik", None)
    d["status_label"] = STATUS_LABEL.get(d.get("status"), d.get("status") or "")
    d["dalam_proses"] = bool(doc.get("saga_lock"))
    return d


async def _kas(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Kas yang terbit dari pengajuan (dibaca langsung: status & jurnal terkini, termasuk ulang dari Posting Gagal)."""
    if not doc.get("cash_id"):
        return None
    t = await db.cash_transactions.find_one({"id": doc["cash_id"]}, {"_id": 0})
    if not t:
        return None
    je = await db.journal_entries.find_one({"id": t.get("journal_entry_id") or "__none__"}, {"_id": 0, "number": 1})
    return {"id": t["id"], "number": t.get("number", ""), "txn_date": t.get("txn_date", ""),
            "amount": _f(t.get("amount")), "status": t.get("status", ""), "gl_status": t.get("gl_status", ""),
            "gl_error": t.get("gl_error", ""), "journal_entry_id": t.get("journal_entry_id", ""),
            "journal_number": (je or {}).get("number", "")}


async def _kontrol(doc: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Penilaian kontrol dua orang untuk `actor` (tombol Setujui jujur) — dua orang dibekukan (§7.8.3)."""
    from services import dual_control
    out = await dual_control.periksa(AKSI, doc, actor, doc.get("entity_id") or "", nominal=_f(doc.get("amount")),
                                     pengaju=_pengaju(doc), dua_orang=True)
    if out.get("ditolak"):
        out["pesan"] = PESAN_ORANG_KEDUA
    return out


async def rincian(request_id: str, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Pengajuan + kas yang terbit (`kas`, None bila belum) + penilaian kontrol dua orang untuk `actor` (bila diberi
    dan pengajuan masih menunggu)."""
    doc = await _ambil(request_id)
    out = _bentuk(doc)
    out["kas"] = await _kas(doc)
    if actor is not None and doc.get("status") == MENUNGGU:
        out["kontrol"] = await _kontrol(doc, actor)
    return out


async def daftar(entity_ids: List[str], status: Optional[str] = None, *, q: str = "", page: int = 1,
                 page_size: int = 25, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """`GET /api/cash-out-requests` — pengajuan PT dalam cakupan (terbaru dulu), berhalaman. `q` = nomor / keterangan /
    kategori / nama pengaju. Baris menunggu membawa penilaian kontrol untuk `actor`."""
    query: Dict[str, Any] = {"entity_id": {"$in": list(entity_ids or [])}}
    if status:
        query["status"] = status
    teks = (q or "").strip()
    if teks:
        rx = {"$regex": re.escape(teks), "$options": "i"}
        query["$or"] = [{"number": rx}, {"description": rx}, {"category": rx}, {"pengaju.name": rx}]
    page, page_size = max(1, int(page or 1)), max(1, min(int(page_size or 25), 100))
    total = await db[COLL].count_documents(query)
    rows = await db[COLL].find(query, {"_id": 0}).sort([("created_at", -1), ("id", -1)]) \
        .skip((page - 1) * page_size).to_list(page_size)
    items = []
    for r in rows:
        d = _bentuk(r)
        if actor is not None and r.get("status") == MENUNGGU:
            d["kontrol"] = await _kontrol(r, actor)
        items.append(d)
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "has_more": page * page_size < total,
            "statuses": [{"value": k, "label": v} for k, v in STATUS_LABEL.items()]}


# ── Ajukan (dipanggil rute kas manual sesudah semua pemeriksaan) ─────────────────────────────────────────────────────
def sidik_isian(isian: Dict[str, Any], entity_id: str) -> str:
    """Sidik isi kiriman SEPERTI DIKIRIM klien (bukan nilai turunan) — mengenali kiriman ulang berkunci sama yang
    isinya berbeda."""
    teks = ("cash_type", "direction", "category", "description", "account_id", "txn_date", "ref_type", "ref_id")
    inti = {"entity_id": entity_id or "", "amount": _f(isian.get("amount")),
            **{k: str(isian.get(k) or "").strip() for k in teks}}
    return hashlib.sha256(json.dumps(inti, sort_keys=True).encode("utf-8")).hexdigest()


def _id_dari_kunci(entity_id: str, kunci: str) -> str:
    return "pkk_" + hashlib.sha1(f"{entity_id}|{kunci}".encode("utf-8")).hexdigest()[:24]


def _cocokkan_sidik(doc: Dict[str, Any], sidik: str) -> None:
    if sidik and doc.get("sidik") and doc["sidik"] != sidik:
        raise _galat(409, PESAN_KUNCI_BEDA, HEADER_ULANG)


async def kiriman_ulang(entity_id: str, kunci: str, sidik: str = "") -> Optional[Dict[str, Any]]:
    """Pengajuan yang sudah ada untuk (PT, Idempotency-Key) → bentuk jawabannya (keadaan terkini + tautan kas); None
    bila belum ada / tanpa kunci. Isi berbeda → 409 `PESAN_KUNCI_BEDA`."""
    kunci = (kunci or "").strip()[:120]
    if not kunci:
        return None
    doc = await db[COLL].find_one({"entity_id": entity_id, "idempotency_key": kunci}, {"_id": 0})
    if not doc:
        return None
    _cocokkan_sidik(doc, sidik)
    return _bentuk(doc)


async def kas_keluar_langsung_sama(entity_id: str, kunci: str, sidik: str, *, amount: float, account_id: str,
                                   category: str, txn_date: str) -> bool:
    """Kunci ini sudah menjadi kas KELUAR manual LANGSUNG di PT ini (sebelum batas/kontrol berubah) dengan isi yang
    SAMA → True: kiriman ulangnya tetap kas yang sama (`create_cash` memakai ulang kas ber-rujukan `manual|kunci|out`),
    bukan pengajuan baru di samping kas itu. Tidak ada kas keluar hidup berkunci ini di PT ini → False (jalur biasa:
    pengajuan bila di atas batas). Ada tetapi isinya berbeda → 409 `PESAN_KUNCI_BEDA` (bukan kas kedua, bukan
    pengajuan).

    Perbaikan putaran 1 (Critical) — hanya kas KELUAR yang dihitung: kas MASUK berkunci sama ber-id lain (`create_cash`
    menurunkan id dari arah), jadi dulu kas keluar di atas batas berkunci kas masuk terjurnal langsung tanpa orang
    kedua (orang lain, atau `X-Entity-Id` diubah/dihilangkan — rekaman penyangga idempotensi berbeda). Isi dibandingkan
    lewat sidik kiriman yang disimpan di kas (`sidik_kiriman`); kas lama tanpa sidik: nominal, rekening, kategori, dan
    tanggal (bila dikirim)."""
    kunci = (kunci or "").strip()[:120]
    if not kunci:
        return False
    kas = await db.cash_transactions.find_one(
        {"entity_id": entity_id, "ref_type": "manual", "ref_id": kunci, "direction": "out", "status": {"$ne": "void"}},
        {"_id": 0, "amount": 1, "account_id": 1, "category": 1, "txn_date": 1, "sidik_kiriman": 1})
    if not kas:
        return False
    if kas.get("sidik_kiriman"):
        sama = kas["sidik_kiriman"] == sidik
    else:
        tgl = (txn_date or "").strip()
        sama = (_f(kas.get("amount")) == _f(amount) and (kas.get("account_id") or "") == (account_id or "")
                and (kas.get("category") or "").strip() == (category or "").strip()
                and (not tgl or (kas.get("txn_date") or "") == tgl))
    if not sama:
        raise _galat(409, PESAN_KUNCI_BEDA, HEADER_ULANG)
    return True


def jawab_diajukan(req: Dict[str, Any]) -> JSONResponse:
    """202 `{request}` — tidak disimpan penyangga idempotensi (kiriman ulang dijawab `kiriman_ulang`, keadaan
    terkini)."""
    return JSONResponse(status_code=202, content={"request": safe_doc(req)}, headers=dict(HEADER_ULANG))


async def ajukan(payload: Dict[str, Any], actor: Dict[str, Any], entity_id: str, idem_key: str) -> Dict[str, Any]:
    """Simpan pengajuan kas keluar manual `menunggu_persetujuan` — tanpa kas, tanpa jurnal.

    `payload` = isian yang SUDAH diperiksa rute: `cash_type`, `account_id` (rekening hasil periksa), `account_name`,
    `amount`, `category`, `description`, `txn_date` (tanggal yang diajukan; kosong = saat diajukan), `budget_check`
    (hasil pemeriksaan anggaran saat diajukan), `sidik` (lihat `sidik_isian`), `ai_card_id` (opsional). Idempoten per
    (PT, `idem_key`): kiriman ulang / bersamaan berkunci sama → pengajuan yang sama."""
    from core_utils import next_doc_number
    p = dict(payload or {})
    kunci = (idem_key or "").strip()[:120]
    sidik = str(p.get("sidik") or "")
    lama = await kiriman_ulang(entity_id, kunci, sidik)
    if lama is not None:
        return lama
    amount = _f(p.get("amount"))
    if amount <= EPS:
        raise _galat(400, "Nominal harus lebih dari 0")
    now = now_iso()
    pengaju = {"id": (actor or {}).get("id") or "", "name": (actor or {}).get("name") or ""}
    doc: Dict[str, Any] = {
        "id": _id_dari_kunci(entity_id, kunci) if kunci else new_id("pkk"), "number": "", "entity_id": entity_id,
        "status": MENUNGGU, "cash_type": p.get("cash_type") or "", "direction": "out", "amount": amount,
        "category": str(p.get("category") or "").strip(), "description": str(p.get("description") or "").strip(),
        "account_id": p.get("account_id") or "", "account_name": p.get("account_name") or "",
        "txn_date": p.get("txn_date") or now, "idempotency_key": kunci, "sidik": sidik,
        "pengaju": pengaju, "created_by": pengaju["name"], "created_by_id": pengaju["id"],
        "budget_check": p.get("budget_check"), "cash_id": "", "cash_number": "", "terbit_error": "",
        "alasan_tolak": "", "created_at": now, "updated_at": now,
        "jejak": [_jejak("ajukan", actor, "menunggu persetujuan orang kedua")],
    }
    if p.get("ai_card_id"):
        doc["ai_card_id"] = p["ai_card_id"]   # AG-T5 — pengajuan dari kartu tindakan asisten (Tugas 3 membacanya)
    doc["number"] = await next_doc_number(COLL, "number", "PKK-", entity_id=entity_id)
    if not kunci:
        await db[COLL].insert_one(dict(doc))
        return _bentuk(doc)
    try:
        await db[COLL].update_one({"id": doc["id"]}, {"$setOnInsert": doc}, upsert=True)
    except Exception as exc:  # noqa: BLE001 — balapan upsert di indeks unik: yang kalah membaca pemenang
        if "E11000" not in str(exc) and "duplicate key" not in str(exc).lower():
            raise
    tersimpan = await db[COLL].find_one({"id": doc["id"]}, {"_id": 0}) or \
        await db[COLL].find_one({"entity_id": entity_id, "idempotency_key": kunci}, {"_id": 0})
    if not tersimpan:   # tidak mungkin kecuali dihapus di antara dua langkah
        raise _galat(409, "Pengajuan kas keluar gagal tercatat. Muat ulang lalu ulangi.")
    if tersimpan.get("number") != doc["number"]:
        _cocokkan_sidik(tersimpan, sidik)   # kalah balapan: pengajuan pemenang dipakai (isi harus sama)
    return _bentuk(tersimpan)


# ── Setujui ──────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _periksa_terbit(doc: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """PERIKSA ulang tanpa tulisan sebelum kas terbit (kategori, rekening, periode, anggaran). Batas TIDAK dinilai ulang
    (§7.8.3). Gagal → 409 berkalimat; pengajuan tidak berubah. → hasil pemeriksaan anggaran (disimpan di kas)."""
    from services import budget_service as bs
    from services import cash_ledger as cl
    from services import gl_service as gl
    eid, nomor = doc.get("entity_id") or "", _nomor(doc)
    tetap = f"Pengajuan {nomor} tetap menunggu."
    kategori = doc.get("category") or ""
    if cl.kategori_transfer_ditutup(kategori):
        raise _galat(409, f"{cl.PESAN_KATEGORI_TRANSFER_DITUTUP} {tetap}")
    if cl.kategori_kas_manual_ditutup(kategori):
        raise _galat(409, f"{cl.PESAN_KATEGORI_PEMBELIAN_GAJI_DITUTUP} {tetap}")
    try:
        await cl.periksa_rekening(eid, doc.get("account_id") or "", doc.get("cash_type") or "")
    except cl.CashRejected as exc:
        raise _galat(409, f"{exc.detail} {tetap}") from exc
    try:
        await gl.preflight_posting(eid, doc.get("txn_date") or now_iso())
    except gl.ClosedPeriodError as exc:
        raise _galat(409, f"{exc} Pengajuan {nomor} tetap menunggu — batalkan lalu ajukan ulang dengan tanggal di "
                          "periode yang terbuka.") from exc
    niat = {"direction": "out", "ref_type": "manual", "category": kategori, "entity_id": eid,
            "amount": _f(doc.get("amount")), "cash_type": doc.get("cash_type") or ""}
    try:
        return await bs.enforce_budget(eid, await bs.cash_budget_targets(niat), when="cash_out",
                                       date=doc.get("txn_date") or "", actor=actor)
    except ValueError as exc:
        raise _galat(409, f"{exc} {tetap}") from exc


async def _klaim(doc: Dict[str, Any], aksi: str, langkah: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """KLAIM berprasyarat status yang diperiksa (`menunggu_persetujuan`). Kalah karena status sudah berubah → 409 yang
    menyebut keadaan barunya; sedang diproses orang lain → 409 `SAGA_IN_PROGRESS` dari `atomic_claim`."""
    from services import atomic_claim as _saga
    try:
        return await _saga.claim(COLL, doc["id"], langkah, precondition={"status": MENUNGGU},
                                 actor=(actor or {}).get("name") or "", detail=_pesan_berubah(doc))
    except HTTPException as exc:
        segar = await db[COLL].find_one({"id": doc["id"]}, {"_id": 0}) or {}
        if isinstance(exc.detail, str) and segar.get("status") in (DISETUJUI, DITOLAK, DIBATALKAN):
            raise _galat(409, _pesan_status(segar, aksi)) from exc
        raise


async def setujui(request_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/cash-out-requests/{id}/approve` — orang kedua menyetujui; kas keluar manual terbit. Juga meneruskan
    pengajuan yang kasnya gagal terbit (`terbit_error`)."""
    from services import atomic_claim as _saga
    from services import cash_ledger
    from services import dual_control
    doc = await _ambil(request_id)
    if doc.get("status") != MENUNGGU:
        raise _galat(409, _pesan_status(doc, "setujui"))
    eid = doc.get("entity_id") or ""
    try:
        # Dua orang DIBEKUKAN (pengajuan lahir karena butuh orang kedua; batas tidak dinilai ulang — §7.8.3).
        await dual_control.tolak_bila_pelaku_sama("kas_keluar_manual", doc, actor, eid, nominal=_f(doc.get("amount")),
                                                  pengaju=_pengaju(doc), dua_orang=True)
    except HTTPException as exc:
        if exc.status_code == 403:
            raise _galat(403, PESAN_ORANG_KEDUA) from exc
        raise
    # ── PERIKSA ulang ──
    budget_check = await _periksa_terbit(doc, actor)
    # ── KLAIM ──
    lk = await _klaim(doc, "setujui", "cash_out_request_issue", actor)
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    nama, nama_id = (actor or {}).get("name") or "", (actor or {}).get("id") or ""
    try:
        now = now_iso()
        try:
            kas = await cash_ledger.create_cash(
                entity_id=eid, direction="out", amount=_f(lk.get("amount")), ref_type="manual", ref_id=lk["id"],
                account_id=lk.get("account_id") or "", cash_type=lk.get("cash_type") or "",
                txn_date=lk.get("txn_date") or "", category=lk.get("category") or "",
                description=lk.get("description") or "",
                actor=(lk.get("pengaju") or {}).get("name") or "system",   # pembuat kas = pengaju
                extra={"cash_out_request_number": lk.get("number") or "", "disetujui_oleh": nama,
                       "disetujui_oleh_id": nama_id, "disetujui_pada": now,
                       **({"budget_check": budget_check} if budget_check is not None else {})})
        except cash_ledger.CashPostingError as exc:
            kas = exc.txn   # kas TETAP tercatat (jurnal gagal → Posting Gagal); pengajuan tetap disetujui
        except cash_ledger.CashRejected as exc:
            await db[COLL].update_one({"id": request_id, f"{_saga.LOCK}.token": token}, {"$set": {
                "terbit_error": str(exc.detail)[:300], "updated_at": now_iso()}})
            raise _galat(409, f"Kas pengajuan {_nomor(lk)} belum terbit: {exc.detail} Pengajuan tetap menunggu; "
                              "ulangi lewat Setujui atau batalkan pengajuan ini.") from exc
        upd = _saga.finish_set({
            "status": DISETUJUI, "cash_id": kas.get("id") or "", "cash_number": kas.get("number") or "",
            "disetujui_oleh": nama, "disetujui_oleh_id": nama_id, "disetujui_pada": now,
            "budget_check_setuju": budget_check, "terbit_error": "", "updated_at": now_iso()})
        upd["$push"] = {"jejak": _jejak("setujui", actor, f"kas {kas.get('number') or ''}".strip())}
        await db[COLL].update_one({"id": request_id, f"{_saga.LOCK}.token": token}, upd)
    finally:
        await _saga.release(COLL, request_id, token)
    return await rincian(request_id)


# ── Tolak / Batal ────────────────────────────────────────────────────────────────────────────────────────────────────
async def _tolak_bila_kas_terbit(doc: Dict[str, Any]) -> None:
    """Pengajuan yang kasnya sudah ada (persetujuan terhenti sesudah kas tercatat) tidak ditolak/dibatalkan dari sini:
    Setujui ulang menuntaskannya (kas yang sama), lalu kasnya dibatalkan dari Transaksi Kas bila perlu."""
    kas = await db.cash_transactions.find_one({"ref_type": "manual", "ref_id": doc["id"], "status": {"$ne": "void"}},
                                              {"_id": 0, "number": 1})
    if kas:
        raise _galat(409, f"Kas {kas.get('number', '')} dari pengajuan {_nomor(doc)} sudah tercatat. Setujui ulang "
                          "untuk menuntaskan pengajuan ini, lalu batalkan kasnya dari Transaksi Kas bila perlu.")


async def _tutup(doc: Dict[str, Any], status_baru: str, aksi: str, isi: Dict[str, Any], actor: Dict[str, Any],
                 catatan: str) -> Dict[str, Any]:
    """Tolak / batal: PERIKSA (belum ada kas) → KLAIM status menunggu → kas dibaca ulang SESUDAH klaim → selesai."""
    from services import atomic_claim as _saga
    await _tolak_bila_kas_terbit(doc)
    lk = await _klaim(doc, aksi, f"cash_out_request_{'reject' if aksi == 'tolak' else 'cancel'}", actor)
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    try:
        await _tolak_bila_kas_terbit(lk)   # selama kunci dipegang tidak ada kas baru untuk pengajuan ini
        upd = _saga.finish_set({"status": status_baru, **isi, "updated_at": now_iso()})
        upd["$push"] = {"jejak": _jejak(aksi, actor, catatan)}
        await db[COLL].update_one({"id": doc["id"], f"{_saga.LOCK}.token": token}, upd)
    finally:
        await _saga.release(COLL, doc["id"], token)
    return await rincian(doc["id"])


async def tolak(request_id: str, alasan: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/cash-out-requests/{id}/reject` — alasan ≥ 5 huruf; bukan pengaju (pengaju memakai Batal)."""
    teks = (alasan or "").strip()
    if len(teks) < ALASAN_MIN:
        raise _galat(400, PESAN_ALASAN_TOLAK)
    doc = await _ambil(request_id)
    if doc.get("status") != MENUNGGU:
        raise _galat(409, _pesan_status(doc, "tolak"))
    if pengaju_sendiri(doc, actor):
        raise _galat(403, PESAN_TOLAK_SENDIRI)
    return await _tutup(doc, DITOLAK, "tolak", {
        "alasan_tolak": teks[:500], "ditolak_oleh": (actor or {}).get("name") or "",
        "ditolak_oleh_id": (actor or {}).get("id") or "", "ditolak_pada": now_iso()}, actor, teks[:500])


async def batal(request_id: str, actor: Dict[str, Any], alasan: str = "") -> Dict[str, Any]:
    """`POST /api/cash-out-requests/{id}/cancel` — selama menunggu. Siapa yang boleh (pengaju atau pemegang
    `cash.delete`) dijaga rute."""
    teks = (alasan or "").strip()[:500]
    doc = await _ambil(request_id)
    if doc.get("status") != MENUNGGU:
        raise _galat(409, _pesan_status(doc, "batal"))
    return await _tutup(doc, DIBATALKAN, "batal", {
        "alasan_batal": teks, "dibatalkan_oleh": (actor or {}).get("name") or "",
        "dibatalkan_oleh_id": (actor or {}).get("id") or "", "dibatalkan_pada": now_iso()}, actor, teks)

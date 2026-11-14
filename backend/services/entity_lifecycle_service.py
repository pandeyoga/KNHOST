"""FASE E-1 — SIKLUS HIDUP BADAN USAHA (satu pintu untuk semua pagar).

Mengapa berkas ini ada: sebelum FASE E-1 aturan entitas tersebar di router
(`routers/entities.py` memvalidasi sendiri, `entity_provisioning_service`
memvalidasi versi lain) sehingga `PATCH` bisa menembus aturan yang ditegakkan
`POST`. Semua pagar sekarang tinggal DI SINI dan dipanggil dari satu tempat.

Isi:
  * E1.2  validasi + keunikan `short_name` / `doc_prefix` (case-insensitive)
  * E1.3  **kunci prefix** — `doc_prefix` tidak boleh diubah bila entitas sudah
          menerbitkan dokumen; pesan menyebut dokumen PERTAMA yang terbit
  * E1.6  pagar deaktivasi — hitung dampak (pengguna aktif, dokumen terbuka,
          saldo, periode belum tutup) → 409 berisi rincian; bila dipaksa
          (admin + alasan) status menjadi `archived` → **kunci-tulis**.
          KP-T2: + uang muka, SPK makloon, permintaan pembelian, pesanan khusus,
          penerimaan barang; saldo dari buku pembantu (piutang, hutang, kas & bank);
          karyawan; daftar centang `checks`
  * E1.8  bentuk data entitas SERAGAM dengan `/auth/context`
"""
import json
import re
import time
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from pymongo import ReturnDocument

from db import db
from core_utils import invalidate_entity_code, now_iso, safe_doc
from services.entity_context_service import ENTITY_DEFAULTS, is_pkp
# Fase 4 · R6 (G5-25) — lokasi tervalidasi ikut bisa diubah lewat PATCH (lihat `entity_location_service`).
from services.entity_location_service import LOCATION_FIELDS

STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"
# `inactive` = status lama (pra-E1) dengan MAKNA SAMA seperti archived: tidak boleh
# menerima transaksi baru. Dipertahankan supaya data lama tidak perlu dimigrasi keras.
STATUS_INACTIVE = "inactive"
WRITE_LOCKED_STATUSES = {STATUS_ARCHIVED, STATUS_INACTIVE}

# Field yang boleh diubah lewat PATCH (satu daftar, dipakai router).
# Fase 4 · R6 (G5-25) — lokasi tervalidasi (negara → provinsi → kota/kab → kecamatan → kode pos) kini ikut bisa
# diubah, sama dengan wizard buat (`BusinessEntityCreate`). Dulu PATCH hanya menerima `city` teks bebas sehingga form
# ubah tidak bisa memakai pemilih wilayah dan kode wilayah dari wizard tidak bisa dikoreksi.
# KP-T1 (KP-01, KP-02) — isian mati (`currency`, `parent_entity_id`, `coa_template`, `fiscal_year_start`,
# `incentive_payer`, `numbering_scheme`) tidak lagi bisa diubah; `default_tax_mode` diubah lewat tindakan
# "Ubah status PKP" (`POST /api/entities/{id}/tax-status`), bukan PATCH; `ownership_pct` (K-10) ditambahkan.
# KP-T6 (KP-18) — identitas kop surat satu sumber: `print_name` (nama di kop; kosong = nama legal), `tagline` (slogan),
# `website` (situs) — dulu hanya ada sebagai teks di `document_branding`.
EDITABLE_FIELDS = [
    "legal_name", "short_name", "type", "npwp", "address", "city",
    "doc_prefix", "logo_url", "is_group", "ownership_pct",
    "owner_name", "business_label", "phone", "email",
    "print_name", "tagline", "website",
] + [k for k in LOCATION_FIELDS if k != "city"]

# (koleksi, field nomor, label manusiawi) — sumber "entitas sudah menerbitkan dokumen".
# Dipakai kunci prefix (E1.3) dan hitungan dampak deaktivasi (E1.6).
DOC_SOURCES: List[Tuple[str, str, str]] = [
    ("sales_orders", "number", "Pesanan penjualan"),
    ("purchase_orders", "po_number", "Pesanan pembelian"),
    ("tax_invoices", "number", "Faktur pajak keluaran"),
    ("tax_invoices_in", "number", "Faktur pajak masukan"),
    ("ar_receipts", "number", "Kwitansi penerimaan"),
    ("journal_entries", "number", "Jurnal buku besar"),
    ("interco_transactions", "number", "Transaksi antar-PT"),
    ("interco_returns", "number", "Retur antar-PT"),
    ("credit_notes", "number", "Nota kredit"),
    ("sales_returns", "number", "Retur penjualan"),
    ("purchase_returns", "number", "Retur pembelian"),
    ("contra_bons", "number", "Kontrabon"),
    ("penalties", "number", "Nota denda"),
    ("payment_plans", "number", "Rencana pembayaran"),
    ("cash_transactions", "number", "Transaksi kas"),
    ("warehouse_transfers", "code", "Transfer gudang"),
    ("vendor_bills", "bill_number", "Tagihan supplier"),
]

# Status yang dianggap SUDAH SELESAI — sisanya dihitung "dokumen terbuka".
CLOSED_STATUSES = {
    "done", "completed", "closed", "cancelled", "canceled", "rejected",
    "paid", "settled", "void", "voided", "archived", "posted", "recorded",
    "normal", "issued_paid", "finished",
}

# KP-T2 (KP-22) — dokumen yang juga menahan ARSIP (bukan kunci kode dokumen E1.3): uang muka & LPJ-nya, SPK makloon,
# permintaan pembelian, pesanan khusus, penerimaan barang. `RISIKO` spesifikasi: status "terbuka" = di luar
# `CLOSED_STATUSES`, jadi bisa terhitung lebih banyak (mis. permintaan yang sudah menjadi PO) — akibatnya hanya arsip
# yang tertahan; admin tetap bisa memaksa dengan alasan. Membatalkan: kosongkan daftar ini.
ARCHIVE_EXTRA_SOURCES: List[Tuple[str, str, str]] = [
    ("cash_advances", "number", "Uang muka"),
    ("cash_advance_settlements", "number", "Pertanggungjawaban uang muka"),
    ("makloon_orders", "mko_number", "SPK makloon"),
    ("purchase_requisitions", "number", "Permintaan pembelian"),
    ("special_orders", "number", "Pesanan khusus"),
    ("goods_receipts", "number", "Penerimaan barang"),
]


# ─── Pembacaan dasar ────────────────────────────────────────────────
def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


async def get_entity_or_404(entity_id: str) -> Dict[str, Any]:
    entity = safe_doc(await db.business_entities.find_one({"id": entity_id}, {"_id": 0}))
    if not entity:
        raise HTTPException(status_code=404, detail="Badan usaha tidak ditemukan")
    return entity


def is_write_locked(entity: Dict[str, Any]) -> bool:
    return (entity or {}).get("status") in WRITE_LOCKED_STATUSES


# ─── E1.8 — bentuk data SERAGAM dengan /auth/context ────────────────────────
def ownership_of(entity: Dict[str, Any]) -> float:
    """KP-T1 (K-10) — persen kepemilikan grup; bawaan `ENTITY_DEFAULTS` (100) bila belum diisi atau rusak."""
    val = (entity or {}).get("ownership_pct")
    if isinstance(val, (int, float)) and not isinstance(val, bool) and 0 < float(val) <= 100:
        return round(float(val), 2)
    return float(ENTITY_DEFAULTS["ownership_pct"])


def uniform_entity(entity: Dict[str, Any]) -> Dict[str, Any]:
    """Bentuk tunggal entitas untuk SEMUA konsumen (switcher, daftar, detail).

    Dulu `/api/entities` mengembalikan dokumen mentah sementara `/auth/context`
    mengembalikan bentuk ringkas — sehingga FE punya dua tambalan label
    (`utils/entityLabel.js`). Satu bentuk = satu sumber kebenaran.
    """
    e = dict(entity or {})
    for key, val in ENTITY_DEFAULTS.items():
        e.setdefault(key, val)
    return {
        "id": e.get("id", ""),
        "code": e.get("doc_prefix") or e.get("short_name") or e.get("id", ""),
        "name": e.get("legal_name") or e.get("short_name") or e.get("id", ""),
        "short_name": e.get("short_name", ""),
        "legal_name": e.get("legal_name", ""),
        "type": e.get("type", ""),
        "is_pkp": is_pkp(e),
        "status": e.get("status", STATUS_ACTIVE),
        "doc_prefix": e.get("doc_prefix", ""),
        "logo_url": e.get("logo_url", ""),
        # tambahan (superset) — dibutuhkan layar Entitas & Akses
        "npwp": e.get("npwp", ""),
        "address": e.get("address", ""),
        "city": e.get("city", ""),
        # Fase 4 · R6 (G5-25) — lokasi tervalidasi ikut dikirim agar form ubah bisa memakai pemilih wilayah.
        **{k: e.get(k, "") or "" for k in LOCATION_FIELDS if k != "city"},
        "location_status": e.get("location_status", ""),
        "phone": e.get("phone", ""),
        "email": e.get("email", ""),
        # KP-T6 — identitas kop surat (Profil PT = satu sumber kop)
        "print_name": e.get("print_name", "") or "",
        "tagline": e.get("tagline", "") or "",
        "website": e.get("website", "") or "",
        "owner_name": e.get("owner_name", ""),
        "business_label": e.get("business_label", ""),
        "default_tax_mode": e.get("default_tax_mode", ""),
        # KP-T1 — tahun buku & mata uang TIDAK di sini: nilai registry (`profile_settings`) ditempel router.
        "is_group": bool(e.get("is_group", False)),
        "ownership_pct": ownership_of(e),
        "tax_status_pending": e.get("tax_status_pending") or None,
        "write_locked": is_write_locked(e),
        "created_at": e.get("created_at", ""),
        "updated_at": e.get("updated_at", ""),
    }


# ─── E1.3 — kunci prefix dokumen ─────────────────────────────────────
async def first_issued_document(entity_id: str) -> Optional[Dict[str, Any]]:
    """Dokumen PERTAMA yang pernah diterbitkan entitas (untuk pesan kunci prefix).

    Dicari lintas koleksi lalu diambil yang `created_at` paling awal. Sengaja
    menyebut dokumen konkret supaya pesan galat bisa ditindaklanjuti pengguna
    ("kenapa saya tidak boleh ganti kode?" → "karena KSC/SO-00001 sudah terbit").
    """
    best: Optional[Dict[str, Any]] = None
    for coll, field, label in DOC_SOURCES:
        row = await db[coll].find_one(
            {"entity_id": entity_id, field: {"$exists": True, "$ne": ""}},
            {"_id": 0, field: 1, "created_at": 1},
            sort=[("created_at", 1)],
        )
        if not row:
            continue
        cand = {"collection": coll, "label": label,
                "number": row.get(field) or "", "created_at": row.get("created_at") or ""}
        if best is None or str(cand["created_at"]) < str(best["created_at"]):
            best = cand
    if best:
        return best
    # Cadangan: sequence nomor sudah pernah dipakai walau dokumennya terhapus.
    seq = await db.number_sequences.find_one(
        {"entity_id": entity_id, "last_no": {"$gt": 0}}, {"_id": 0})
    if seq:
        return {"collection": "number_sequences", "label": "Nomor dokumen",
                "number": f"{seq.get('prefix', '')}{int(seq.get('last_no', 0)):05d}",
                "created_at": seq.get("created_at", "")}
    return None


async def prefix_lock_info(entity_id: str) -> Dict[str, Any]:
    doc = await first_issued_document(entity_id)
    return {
        "locked": bool(doc),
        "first_document": doc,
        "reason": (
            f"Kode dokumen tidak bisa diubah karena badan usaha ini sudah menerbitkan "
            f"{(doc or {}).get('label', 'dokumen').lower()} “{(doc or {}).get('number', '')}”. "
            "Mengubah kode akan membuat nomor dokumen lama dan baru tidak bisa "
            "dibedakan lagi." if doc else ""
        ),
    }


async def assert_prefix_change_allowed(entity_id: str, current_prefix: str,
                                       new_prefix: str) -> None:
    if _norm(new_prefix) == _norm(current_prefix):
        return
    info = await prefix_lock_info(entity_id)
    if info["locked"]:
        raise HTTPException(status_code=409, detail=info["reason"])


# ─── E1.2 — keunikan (case-insensitive) ────────────────────────────────
async def assert_unique(field: str, value: str, exclude_id: str = "") -> None:
    """Keunikan tanpa peduli besar-kecil huruf (mis. “KSC” vs “ksc”)."""
    val = (value or "").strip()
    if not val:
        return
    label = {"short_name": "Nama singkat", "doc_prefix": "Kode dokumen"}.get(field, field)
    async for row in db.business_entities.find({}, {"_id": 0, "id": 1, field: 1,
                                                    "legal_name": 1}):
        if row.get("id") == exclude_id:
            continue
        if _norm(row.get(field)) == _norm(val):
            raise HTTPException(
                status_code=409,
                detail=f"{label} “{val}” sudah dipakai badan usaha “"
                       f"{row.get('legal_name') or row.get('id')}”. Pilih yang lain.")


# ─── E1.6 — dampak deaktivasi ───────────────────────────────────────
async def _open_documents(entity_id: str) -> List[Dict[str, Any]]:
    """KP-T2 (D4) — dihitung di kueri (`count_documents`) + tiga contoh nomor; dulu dipotong diam-diam 2.000 baris."""
    out: List[Dict[str, Any]] = []
    for coll, field, label in DOC_SOURCES + ARCHIVE_EXTRA_SOURCES:
        q = {"entity_id": entity_id, "status": {"$nin": sorted(CLOSED_STATUSES)}}
        n = await db[coll].count_documents(q)
        if not n:
            continue
        rows = await db[coll].find(q, {"_id": 0, field: 1}).sort("created_at", 1).limit(3).to_list(3)
        out.append({"collection": coll, "label": label, "count": n,
                    "examples": [r.get(field) for r in rows if r.get(field)]})
    return out


async def _open_balances(entity_id: str) -> List[Dict[str, Any]]:
    """Saldo yang masih hidup — KP-T2 (KP-22): dari buku pembantunya masing-masing.

    piutang = umur piutang PT (`ar_aging_service.aging_report`, pesanan batal/lunas tidak ikut — dulu Σ semua pesanan);
    hutang = Σ sisa tagihan pemasok `posted` (`vendor_bill_service.bill_financials`); kas & bank = Σ |saldo| tiap
    rekening/akun kas PT (`bank_service._balance`: saldo awal + masuk − keluar, transaksi tidak batal); antar-PT dan
    stok seperti sebelumnya.
    """
    from services import bank_service
    from services.ar_aging_service import aging_report
    from services.vendor_bill_service import bill_financials
    out: List[Dict[str, Any]] = []
    piutang = round(float(((await aging_report(entity_id=entity_id)).get("totals") or {}).get("total") or 0), 2)
    if piutang > 0.01:
        out.append({"key": "piutang", "label": "Piutang pelanggan belum lunas", "amount": piutang})
    hutang = 0.0
    async for b in db.vendor_bills.find({"entity_id": entity_id, "status": "posted"}, {"_id": 0}):
        hutang += bill_financials(b)["outstanding"]
    hutang = round(hutang, 2)
    if hutang > 0.01:
        out.append({"key": "hutang", "label": "Hutang pemasok belum lunas", "amount": hutang})
    kas = 0.0
    async for acc in db.bank_accounts.find({"entity_id": entity_id}, {"_id": 0, "id": 1, "opening_balance": 1}):
        kas += abs(bank_service._balance(acc.get("opening_balance") or 0,   # noqa: SLF001 — rumus saldo rekening
                                         await bank_service._txns_for(acc["id"])))   # noqa: SLF001
    kas = round(kas, 2)
    if kas > 0.01:
        out.append({"key": "kas_bank", "label": "Saldo kas dan bank", "amount": kas})
    ic = await db.interco_accounts.find({"entity_id": entity_id}, {"_id": 0}).to_list(50)
    ic_total = round(sum(abs(float(r.get("balance") or 0)) for r in ic), 2)
    if ic_total > 0.01:
        out.append({"key": "antar_pt", "label": "Saldo antar-PT", "amount": ic_total})
    rolls = await db.inventory_rolls.count_documents(
        {"owner_entity_id": entity_id, "status": {"$nin": ["consumed", "sold", "scrapped"]}})
    if rolls:
        out.append({"key": "stok", "label": "Roll stok masih dimiliki", "amount": rolls,
                    "unit": "roll"})
    return out


def _balance_text(b: Dict[str, Any]) -> str:
    from core_utils import rupiah
    return f"{b['label']} {b['amount']} {b['unit']}" if b.get("unit") else f"{b['label']} {rupiah(b['amount'])}"


def _archive_checks(home_users: List[Dict[str, Any]], open_docs: List[Dict[str, Any]],
                    balances: List[Dict[str, Any]], employees: int, periods: Dict[str, Any]) -> List[Dict[str, Any]]:
    """KP-T2 — daftar centang yang SAMA dengan yang diperiksa server (lima kelompok), untuk dialog arsip."""
    total_open = sum(d["count"] for d in open_docs)
    docs_text = "; ".join(
        f"{d['label']} {d['count']}" + (f" ({', '.join(str(x) for x in d['examples'])})" if d["examples"] else "")
        for d in open_docs)
    journals = periods.get("journals_after_last_closing") or 0
    return [
        {"key": "pengguna", "label": "Pengguna ber-PT utama di sini", "ok": not home_users,
         "detail": (f"{len(home_users)} pengguna: " + ", ".join(u.get("name", "?") for u in home_users[:5])
                    if home_users else "Tidak ada")},
        {"key": "dokumen", "label": "Dokumen terbuka", "ok": not total_open,
         "detail": f"{total_open} dokumen: {docs_text}" if total_open else "Tidak ada"},
        {"key": "saldo", "label": "Saldo yang masih hidup", "ok": not balances,
         "detail": "; ".join(_balance_text(b) for b in balances) if balances else "Tidak ada"},
        {"key": "karyawan", "label": "Karyawan terdaftar", "ok": not employees,
         "detail": f"{employees} karyawan belum dipindahkan atau diakhiri" if employees else "Tidak ada"},
        {"key": "periode", "label": "Tutup buku", "ok": not journals,
         "detail": (f"{journals} jurnal belum masuk periode tertutup" if journals
                    else "Semua jurnal sudah masuk periode tertutup")},
    ]


async def _open_periods(entity_id: str) -> Dict[str, Any]:
    """Periode belum ditutup = ada jurnal setelah penutupan terakhir."""
    last = await db.period_closings.find_one(
        {"entity_id": entity_id, "status": "closed"},   # PK-11 — `closing` (sedang ditutup) bukan penutupan
        {"_id": 0, "period_end": 1, "period_label": 1}, sort=[("period_end", -1)])
    q: Dict[str, Any] = {"entity_id": entity_id}
    if last and last.get("period_end"):
        q["date"] = {"$gt": last["period_end"]}
    count = await db.journal_entries.count_documents(q)
    return {"journals_after_last_closing": count,
            "last_closing": (last or {}).get("period_label", "")}


async def deactivation_impact(entity_id: str) -> Dict[str, Any]:
    """Pratinjau dampak SEBELUM entitas diarsipkan (dipakai UI & endpoint DELETE)."""
    entity = await get_entity_or_404(entity_id)
    users = await db.users.find(
        {"status": "active",
         "$or": [{"home_entity_id": entity_id}, {"allowed_entity_ids": entity_id}]},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1, "home_entity_id": 1}).to_list(200)
    home_users = [u for u in users if u.get("home_entity_id") == entity_id]
    open_docs = await _open_documents(entity_id)
    balances = await _open_balances(entity_id)
    periods = await _open_periods(entity_id)
    issued = await first_issued_document(entity_id)
    # KP-T2 (KP-22) — karyawan yang masih terdaftar di PT ini (bukan `resigned`) ikut menahan arsip.
    employees = await db.hr_employees.count_documents({"entity_id": entity_id, "status": {"$ne": "resigned"}})

    blockers: List[str] = []
    if home_users:
        blockers.append(
            f"{len(home_users)} pengguna masih ber-badan-usaha utama di sini — "
            "pindahkan dulu (" + ", ".join(u.get("name", "?") for u in home_users[:5]) + ")")
    total_open = sum(d["count"] for d in open_docs)
    if total_open:
        blockers.append(f"{total_open} dokumen masih terbuka ("
                        + ", ".join(f"{d['label']} {d['count']}" for d in open_docs[:4])
                        + (", …" if len(open_docs) > 4 else "") + ") — selesaikan atau batalkan dulu")
    if balances:
        blockers.append(
            "Masih ada saldo hidup: " + ", ".join(b["label"].lower() for b in balances))
    if employees:
        blockers.append(f"{employees} karyawan masih terdaftar di PT ini — pindahkan atau akhiri dulu")
    if periods["journals_after_last_closing"]:
        blockers.append(
            f"{periods['journals_after_last_closing']} jurnal belum masuk periode tertutup — "
            "lakukan tutup buku dulu")
    return {
        "entity_id": entity_id,
        "entity_name": entity.get("legal_name") or entity.get("short_name") or entity_id,
        "status": entity.get("status", STATUS_ACTIVE),
        "active_users": users,
        "home_users": home_users,
        "open_documents": open_docs,
        "open_documents_total": total_open,
        "balances": balances,
        "periods": periods,
        "has_issued_documents": bool(issued),
        "first_document": issued,
        "employees": employees,
        "checks": _archive_checks(home_users, open_docs, balances, employees, periods),
        "blockers": blockers,
        "can_archive": not blockers,
        "force_requires": ["akses hapus Badan Usaha (bawaan Admin)", "alasan tertulis"],
    }


async def archive_entity(entity_id: str, actor: Dict[str, Any], reason: str = "",
                         force: bool = False) -> Dict[str, Any]:
    """Arsipkan entitas. Menolak (409) bila masih terpakai, kecuali dipaksa admin."""
    entity = await get_entity_or_404(entity_id)
    if is_write_locked(entity):
        raise HTTPException(status_code=409,
                            detail="Badan usaha ini sudah diarsipkan sebelumnya.")
    total_active = await db.business_entities.count_documents({"status": STATUS_ACTIVE})
    if total_active <= 1:
        raise HTTPException(
            status_code=409,
            detail="Ini satu-satunya badan usaha aktif. Buat badan usaha lain dulu "
                   "sebelum mengarsipkan yang ini.")
    impact = await deactivation_impact(entity_id)
    if impact["blockers"] and not force:
        raise HTTPException(status_code=409, detail={
            "message": "Badan usaha masih terpakai — belum bisa diarsipkan.",
            "blockers": impact["blockers"],
            "impact": impact,
            "hint": "Setelah semuanya beres, ulangi. Bila memang harus dipaksa, kirim "
                    "force=true beserta alasan (hanya admin).",
        })
    if force:
        from dependencies import has_permission
        if not await has_permission(actor or {}, "entity", "delete"):   # PR-T2 — dulu peran `admin` persis
            raise HTTPException(status_code=403, detail=(
                "Anda belum punya akses untuk memaksa pengarsipan badan usaha. Minta Admin menambahkan akses "
                "'Badan Usaha (PT)'."))   # PR-T5 — modul pemilik `entity` (dulu modul gabungan)
        if not (reason or "").strip():
            raise HTTPException(status_code=400,
                                detail="Alasan wajib diisi saat memaksa pengarsipan.")
    patch = {"status": STATUS_ARCHIVED, "archived_at": now_iso(),
             "archived_by": (actor or {}).get("name", ""),
             "archive_reason": (reason or "").strip(),
             "archive_forced": bool(force), "updated_at": now_iso()}
    # Sesi 16 — CAS: hanya badan usaha yang belum diarsipkan; klik ganda/balapan → 409.
    won = await db.business_entities.find_one_and_update(
        {"id": entity_id, "status": {"$ne": STATUS_ARCHIVED}}, {"$set": patch}, projection={"_id": 0})
    if not won:
        raise HTTPException(status_code=409, detail={"code": "STATE_CHANGED",
                            "message": "Badan usaha sudah diarsipkan oleh proses lain."})
    # Cabut sesi pengguna yang badan usaha utamanya diarsipkan (tidak boleh masuk lagi).
    home_ids = [u["id"] for u in impact["home_users"]]
    revoked = 0
    if home_ids:
        res = await db.sessions.delete_many({"user_id": {"$in": home_ids}})
        revoked = res.deleted_count
    invalidate_entity_code(entity_id)
    invalidate_status_cache()
    return {**(await get_entity_or_404(entity_id)), "impact": impact,
            "sessions_revoked": revoked}


async def reactivate_entity(entity_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    entity = await get_entity_or_404(entity_id)
    if entity.get("status") == STATUS_ACTIVE:
        raise HTTPException(status_code=409, detail="Badan usaha ini sudah aktif.")
    await db.business_entities.update_one(
        {"id": entity_id},
        {"$set": {"status": STATUS_ACTIVE, "reactivated_at": now_iso(),
                  "reactivated_by": (actor or {}).get("name", ""), "updated_at": now_iso()},
         "$unset": {"archived_at": "", "archive_reason": "", "archive_forced": ""}})
    invalidate_entity_code(entity_id)
    invalidate_status_cache()
    return await get_entity_or_404(entity_id)


# ─── E1.6 — kunci-tulis entitas terarsip ───────────────────────────────
async def assert_entity_writable(entity_id: str, action: str = "membuat data") -> None:
    """Tolak TULIS ke entitas terarsip (data lama tetap boleh dibaca admin)."""
    if not entity_id or entity_id == "all":
        return
    entity = safe_doc(await db.business_entities.find_one(
        {"id": entity_id}, {"_id": 0, "status": 1, "legal_name": 1, "short_name": 1}))
    if entity and is_write_locked(entity):
        name = entity.get("legal_name") or entity.get("short_name") or entity_id
        raise HTTPException(
            status_code=409,
            detail=f"“{name}” sudah diarsipkan sehingga tidak bisa lagi menerima "
                   f"transaksi baru. Tidak bisa {action}. Aktifkan kembali badan "
                   "usaha ini bila memang masih dipakai.")


# ─── Cache status (dipakai penjaga tulis di setiap request) ──────────────────
_STATUS_CACHE: Dict[str, Dict[str, str]] = {}
_STATUS_CACHE_AT: Dict[str, float] = {"t": 0.0}
STATUS_CACHE_TTL_SECONDS = 20.0


def invalidate_status_cache() -> None:
    _STATUS_CACHE.clear()
    _STATUS_CACHE_AT["t"] = 0.0


async def entity_status_map() -> Dict[str, Dict[str, str]]:
    """Peta id → {status, name} dengan cache pendek.

    Penjaga kunci-tulis dipanggil pada SETIAP request yang mengubah data; tanpa
    cache itu berarti satu query Mongo tambahan per request hanya untuk membaca
    status yang hampir tidak pernah berubah.
    """
    now = time.monotonic()
    if _STATUS_CACHE and (now - _STATUS_CACHE_AT["t"]) < STATUS_CACHE_TTL_SECONDS:
        return _STATUS_CACHE
    rows = await db.business_entities.find(
        {}, {"_id": 0, "id": 1, "status": 1, "legal_name": 1, "short_name": 1}).to_list(500)
    _STATUS_CACHE.clear()
    for r in rows:
        _STATUS_CACHE[r["id"]] = {
            "status": r.get("status", STATUS_ACTIVE),
            "name": r.get("legal_name") or r.get("short_name") or r["id"],
        }
    _STATUS_CACHE_AT["t"] = now
    return _STATUS_CACHE


async def assert_entity_writable_cached(entity_id: str) -> None:
    """E1.6 — kunci-tulis badan usaha terarsip, dipasang di choke point auth.

    Dipanggil `dependencies.current_user()` untuk metode POST/PUT/PATCH/DELETE.
    Satu tempat = tidak ada endpoint yang lupa dipasangi pagar.
    """
    if not entity_id or entity_id == "all":
        return
    info = (await entity_status_map()).get(entity_id)
    if info and info["status"] in WRITE_LOCKED_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"“{info['name']}” sudah diarsipkan sehingga tidak bisa lagi "
                   "menerima transaksi baru. Data lama tetap bisa dibaca. Aktifkan "
                   "kembali badan usaha ini bila memang masih dipakai.")


# ─── E1.10 — PAGAR TULIS LINTAS BADAN USAHA (dipasang di choke point auth) ────
# Temuan POC E-1: FASE E-0 hanya menyapu endpoint BACA. Di sisi TULIS masih ada
# lubang nyata — `POST /api/customers`, `POST /api/sales-orders`,
# `POST /api/inventory/initial-stock`, kontrak blanket, retur beli, kwitansi, dan
# jurnal manual memakai `payload.entity_id` MENTAH lalu jatuh ke `DEFAULT_ENTITY_ID`.
# Artinya sales CV Kanda Suka bisa MENANAM dokumen di buku PT Kain Suka Cita hanya
# dengan mengirim satu field. Memasang penjaga di 11 titik satu-satu mudah terlewat
# saat endpoint baru lahir, jadi penjaganya dipasang di SATU tempat yang dilewati
# semua endpoint terautentikasi.
#
# Sengaja HANYA field kepemilikan dokumen. `source_entity_id`/`dest_entity_id`/
# `seller_entity_id`/`buyer_entity_id` (antar-PT) dan `home_entity_id`/
# `allowed_entity_ids` (penugasan akun) memang MENYEBUT badan usaha lain secara sah,
# jadi tidak boleh diblokir di sini.
BODY_ENTITY_FIELDS = ("entity_id", "owner_entity_id")


def _collect_body_entities(body: Any) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if not isinstance(body, dict):
        return out
    for fld in BODY_ENTITY_FIELDS:
        val = body.get(fld)
        if isinstance(val, str) and val.strip():
            out.append((fld, val.strip()))
    inner = body.get("data")          # bentuk GenericPatch: {"data": {...}}
    if isinstance(inner, dict):
        for fld in BODY_ENTITY_FIELDS:
            val = inner.get(fld)
            if isinstance(val, str) and val.strip():
                out.append((f"data.{fld}", val.strip()))
    return out


async def writable_entity_ids(user: Dict[str, Any]) -> set:
    """Badan usaha yang boleh DITULISI user ini (aktif saja)."""
    from services.entity_context_service import CROSS_ENTITY_ROLES
    smap = await entity_status_map()
    active = {eid for eid, info in smap.items()
              if info["status"] not in WRITE_LOCKED_STATUSES}
    if user.get("role") in CROSS_ENTITY_ROLES:
        return active | {"all"}      # 'all' = baris global (mis. aturan approval)
    home = user.get("home_entity_id") or ""
    stored = user.get("allowed_entity_ids") or ([home] if home else [])
    return {e for e in stored if e in active}


async def assert_body_entity_allowed(request: Any, user: Dict[str, Any]) -> None:
    ctype = (request.headers.get("content-type") or "").lower()
    if "json" not in ctype:
        return
    try:
        raw = await request.body()      # sudah di-cache Starlette; aman dibaca lagi
        if not raw:
            return
        body = json.loads(raw)
    except Exception:  # noqa: BLE001 — bukan JSON / kosong: bukan urusan penjaga ini
        return
    found = _collect_body_entities(body)
    if not found:
        return
    allowed = await writable_entity_ids(user)
    smap = await entity_status_map()
    for field, val in found:
        if val in allowed:
            continue
        info = smap.get(val)
        if not info:
            detail = (f"Badan usaha “{val}” tidak ada, jadi data tidak bisa disimpan "
                      f"ke sana (field {field}).")
        elif info["status"] in WRITE_LOCKED_STATUSES:
            detail = (f"“{info['name']}” sudah diarsipkan sehingga tidak bisa lagi "
                      f"menerima data baru (field {field}).")
        else:
            detail = (f"Anda tidak berwenang menyimpan data ke “{info['name']}”. "
                      "Data hanya boleh dibuat di badan usaha tempat Anda ditugaskan.")
        raise HTTPException(status_code=403, detail=detail)


async def readable_entity_ids(user: Dict[str, Any]) -> List[str]:
    """Badan usaha yang boleh DIBACA user (aktif saja) — urutan stabil.

    Sama aturannya dengan `entity_scope.entity_ctx` tetapi tanpa impor balik
    (entity_scope mengimpor dependencies, jadi tidak boleh sebaliknya).
    """
    from services.entity_context_service import CROSS_ENTITY_ROLES
    smap = await entity_status_map()
    active = [eid for eid, info in smap.items()
              if info["status"] not in WRITE_LOCKED_STATUSES]
    home = user.get("home_entity_id") or ""
    if user.get("role") in CROSS_ENTITY_ROLES:
        return active or ([home] if home else [])
    stored = user.get("allowed_entity_ids") or ([home] if home else [])
    out = [e for e in stored if e in active]
    return out or ([home] if home else [])


READ_METHODS = {"GET", "HEAD", "OPTIONS"}


async def archived_readable_ids(user: Dict[str, Any]) -> List[str]:
    """Keputusan pemilik P17: badan usaha terarsip tetap bisa DIBACA (baca saja).

    Lintas-PT (admin/manager) → semua yang terarsip; peran lain → hanya yang pernah
    ditugaskan (`allowed_entity_ids`). Tulis tetap dikunci `assert_entity_writable_cached`.
    """
    from services.entity_context_service import CROSS_ENTITY_ROLES
    smap = await entity_status_map()
    archived = [eid for eid, info in smap.items() if info["status"] in WRITE_LOCKED_STATUSES]
    if user.get("role") in CROSS_ENTITY_ROLES:
        return archived
    stored = user.get("allowed_entity_ids") or []
    return [e for e in archived if e in stored]


async def archived_read_target(request: Any, user: Dict[str, Any]) -> str:
    """Id badan usaha terarsip yang sah dibaca request ini (GET saja), selain itu ""."""
    requested = (request.headers.get("X-Entity-Id") or "").strip()
    if request.method not in READ_METHODS or not requested or requested == "all":
        return ""
    return requested if requested in await archived_readable_ids(user) else ""


async def entity_denied_message(requested: str, allowed: List[str]) -> str:
    """Pesan 403 yang MENJELASKAN — bukan sekadar “tidak berwenang”.

    Tiga sebab berbeda perlu tiga kalimat berbeda supaya pengguna tahu harus apa:
    badan usahanya tidak ada, sudah diarsipkan, atau memang bukan penugasannya.
    """
    info = (await entity_status_map()).get(requested)
    if not info:
        return (f"Badan usaha “{requested}” tidak ada (mungkin sudah dihapus). "
                "Pilih badan usaha lain di pemilih entitas.")
    if info["status"] in WRITE_LOCKED_STATUSES:
        return (f"“{info['name']}” sudah diarsipkan — datanya hanya bisa dibaca, "
                "tidak bisa dipakai untuk menyimpan transaksi. Pilih badan usaha yang masih aktif.")
    return (f"Anda tidak ditugaskan di “{info['name']}”. Hubungi admin bila memang perlu "
            "akses ke badan usaha ini.")


async def assert_requested_entity_allowed(request: Any, user: Dict[str, Any]) -> None:
    """FASE E-1 (E1.5) — header `X-Entity-Id` yang tidak sah DITOLAK di choke point.

    Kenapa di sini dan bukan hanya di `entity_scope.entity_ctx`: banyak endpoint
    (mis. `POST /api/customers`) tidak memakai `entity_ctx`. Tanpa penjaga ini,
    permintaan yang menyebut badan usaha lain dilayani **diam-diam atas nama badan
    usaha HOME** — layar bilang “Kanda”, datanya mendarat di KSC. Justru inilah
    kelas cacat yang paling sulit disadari pengguna.

    `all` (mode gabungan) sengaja TIDAK ditolak untuk peran non-lintas: nilainya
    tersimpan di localStorage peramban dan artinya “tidak ada preferensi”, bukan
    upaya menembus batas. Konteks efektifnya tetap badan usaha sendiri.
    """
    requested = (request.headers.get("X-Entity-Id") or "").strip()
    if not requested or requested == "all":
        return
    allowed = await readable_entity_ids(user)
    if requested not in allowed and not await archived_read_target(request, user):
        raise HTTPException(status_code=403,
                            detail=await entity_denied_message(requested, allowed))


# ─── KP-T1 — profil PT: tahun buku & mata uang dari registry; status PKP bertanggal ─────────────────────────────
# Tahun buku dan mata uang punya SATU sumber: kunci registry (lapisan PT). Master PT tidak lagi menyimpan atau
# mengirim `fiscal_year_start`/`currency`; jawaban router memuat nilai yang benar-benar dipakai mesin.
PROFILE_KEYS = (("base_currency", "finance.base_currency"),
                ("fiscal_year_end_month", "finance.fiscal_year_end_month"))
TAX_MODES = ("ppn", "non_ppn")
TAX_STATUS_LABEL = {"ppn": "PKP", "non_ppn": "Non-PKP"}
#: Dokumen yang menyimpan hitungan pajak (keduanya dihitung `config_service.compute_order_pricing`).
TAX_PREVIEW_SOURCES: Tuple[Tuple[str, str, str], ...] = (
    ("sales_orders", "number", "Pesanan penjualan"),
    ("purchase_orders", "po_number", "Pesanan pembelian"),
)
#: Pengaturan pajak lapisan PT yang mulai/berhenti dipakai saat status PKP berubah (`get_effective_settings`).
TAX_PREVIEW_KEYS = ("tax.ppn_rate", "tax.efaktur_enabled")
NPWP_MESSAGE = "NPWP harus 15 atau 16 digit angka. Periksa kembali nomor yang diketik."
ARCHIVED_MESSAGE = "PT ini sudah diarsipkan."
RACE_MESSAGE = "Status PKP sudah diubah oleh proses lain. Muat ulang lalu periksa kembali."


async def profile_settings(entity_id: str) -> Dict[str, Any]:
    """Nilai registry yang dipakai mesin untuk PT ini + lapisan asalnya (`source` = `source_layer` resolver)."""
    import config_registry as registry
    from services.config_resolver import resolve
    out: Dict[str, Any] = {}
    for name, key in PROFILE_KEYS:
        res = await resolve(key, {"entity_id": entity_id})
        val = res.get("value")
        if val in (None, ""):
            val = registry.require(key)["default"]
        out[name] = int(val) if name == "fiscal_year_end_month" else str(val)
        out[f"{name}_source"] = res.get("source_layer", "code_default")
    return out


def npwp_digits(value: Any) -> str:
    """NPWP tanpa titik, strip, dan spasi."""
    return re.sub(r"[.\-\s]", "", str(value or "").strip())


def npwp_valid(value: Any) -> bool:
    """`ASUMSI` KP-T1 (KP-23) — NPWP sah = tepat 15 atau 16 digit setelah titik, strip, dan spasi dibuang."""
    return bool(re.fullmatch(r"\d{15}|\d{16}", npwp_digits(value)))


def today_wib() -> str:
    from services import analytics_time
    return analytics_time.now_wib().date().isoformat()


def _date_or_400(value: Any) -> str:
    raw = str(value or "").strip()
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            raise ValueError(raw)
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="Tanggal berlaku tidak valid.") from None


def _to_or_400(value: Any) -> str:
    to = str(value or "").strip()
    if to not in TAX_MODES:
        raise HTTPException(status_code=400, detail="Status baru tidak dikenal. Pilih PKP atau Non-PKP.")
    return to


async def active_entity_or_409(entity_id: str) -> Dict[str, Any]:
    entity = await get_entity_or_404(entity_id)
    if is_write_locked(entity):
        raise HTTPException(status_code=409, detail=ARCHIVED_MESSAGE)
    return entity


def _tax_blockers(entity: Dict[str, Any], to: str, npwp: str = "") -> List[str]:
    """Penghalang yang sama untuk pratinjau dan simpan (urutan = urutan pemeriksaan `change_tax_status`)."""
    cur = entity.get("default_tax_mode") or ""
    if to == cur:
        return [f"PT ini sudah berstatus {TAX_STATUS_LABEL.get(to, to)}."]
    out: List[str] = []
    pending = entity.get("tax_status_pending") or {}
    if pending:
        out.append(f"Sudah ada perubahan status PKP terjadwal mulai {pending.get('effective_date', '')}. "
                   "Batalkan jadwal itu dulu.")
    if to == "ppn":
        eff_npwp = (npwp or "").strip() or str(entity.get("npwp") or "").strip()
        if not eff_npwp:
            out.append("PT yang menjadi PKP wajib mengisi NPWP.")
        elif not npwp_valid(eff_npwp):
            out.append(NPWP_MESSAGE)
    return out


async def tax_status_preview(entity_id: str, to: str, effective_date: str, npwp: str = "") -> Dict[str, Any]:
    """Pratinjau dampak "Ubah status PKP" — tidak menulis apa pun."""
    import config_registry as registry
    from services.config_resolver import resolve
    entity = await active_entity_or_409(entity_id)
    to = _to_or_400(to)
    eff = _date_or_400(effective_date)
    today = today_wib()
    open_docs: List[Dict[str, Any]] = []
    since: List[Dict[str, Any]] = []
    for coll, field, label in TAX_PREVIEW_SOURCES:
        q = {"entity_id": entity_id, "status": {"$nin": sorted(CLOSED_STATUSES)}}
        n = await db[coll].count_documents(q)
        if n:
            rows = await db[coll].find(q, {"_id": 0, field: 1}).sort("created_at", 1).limit(3).to_list(3)
            open_docs.append({"collection": coll, "label": label, "count": n,
                              "examples": [r.get(field) for r in rows if r.get(field)]})
        if eff < today:
            m = await db[coll].count_documents({"entity_id": entity_id, "created_at": {"$gte": eff}})
            if m:
                since.append({"collection": coll, "label": label, "count": m})
    layers = []
    for key in TAX_PREVIEW_KEYS:
        res = await resolve(key, {"entity_id": entity_id})
        layers.append({"key": key, "label": registry.require(key)["label"], "value": res.get("value"),
                       "source": res.get("source_layer"),
                       "effect": "mulai dipakai" if to == "ppn" else "berhenti dipakai"})
    blockers = _tax_blockers(entity, to, npwp)
    return {
        "entity_id": entity_id,
        "current": entity.get("default_tax_mode") or "",
        "to": to,
        "effective_date": eff,
        "applies": "sekarang" if eff <= today else "terjadwal",
        "npwp_ok": npwp_valid((npwp or "").strip() or entity.get("npwp")),
        "open_documents": open_docs,
        "documents_since": since,
        "tax_invoices_issued": await db.tax_invoices.count_documents({"entity_id": entity_id}),
        "setting_layers": layers,
        "blockers": blockers,
        "can_apply": not blockers,
    }


async def change_tax_status(entity_id: str, body: Dict[str, Any],
                            actor: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str]:
    """Ubah status PKP (hari ini/mundur → langsung; maju → dijadwalkan). → (dokumen PT, aksi jejak, status lama)."""
    entity = await active_entity_or_409(entity_id)
    cur = entity.get("default_tax_mode") or ""
    to = _to_or_400(body.get("to"))
    npwp = str(body.get("npwp") or "").strip()
    blockers = _tax_blockers(entity, to, npwp)
    if blockers:
        raise HTTPException(status_code=400, detail=blockers[0])
    reason = str(body.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="Alasan perubahan status PKP wajib diisi.")
    eff = _date_or_400(body.get("effective_date"))
    now = now_iso()
    who = {"by": (actor or {}).get("name", ""), "by_id": (actor or {}).get("id", "")}
    setter: Dict[str, Any] = {"updated_at": now}
    if npwp and npwp != str(entity.get("npwp") or "").strip():
        setter["npwp"] = npwp            # NPWP yang diketik di pop-up (sudah lolos pola) ikut disimpan
    if eff <= today_wib():
        setter["default_tax_mode"] = to
        upd = {"$set": setter, "$unset": {"tax_status_pending": ""},
               "$push": {"tax_status_history": {"from": cur, "to": to, "effective_date": eff, "reason": reason,
                                                **who, "at": now}}}
        flt: Dict[str, Any] = {"id": entity_id, "default_tax_mode": cur}
        action = "entity_tax_status_changed"
    else:
        setter["tax_status_pending"] = {"to": to, "effective_date": eff, "reason": reason, **who, "at": now}
        upd = {"$set": setter}
        flt = {"id": entity_id, "default_tax_mode": cur, "tax_status_pending": {"$exists": False}}
        action = "entity_tax_status_scheduled"
    doc = await db.business_entities.find_one_and_update(flt, upd, projection={"_id": 0},
                                                         return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(status_code=409, detail=RACE_MESSAGE)
    return doc, action, cur


async def cancel_pending_tax_status(entity_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Batalkan jadwal status PKP. → (dokumen PT, jadwal yang dibatalkan). 404 bila tidak ada jadwal."""
    entity = await active_entity_or_409(entity_id)
    pending = entity.get("tax_status_pending") or {}
    if not pending:
        raise HTTPException(status_code=404, detail="Tidak ada perubahan status PKP yang terjadwal.")
    doc = await db.business_entities.find_one_and_update(
        {"id": entity_id, "tax_status_pending.at": pending.get("at")},
        {"$unset": {"tax_status_pending": ""}, "$set": {"updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not doc:
        raise HTTPException(status_code=409, detail=RACE_MESSAGE)
    return doc, pending


async def apply_due_tax_status(today: Optional[str] = None) -> int:
    """Terapkan `tax_status_pending` yang `effective_date` ≤ hari ini (WIB). Idempoten; → jumlah PT yang berubah.

    Dipanggil saat aplikasi menyala (`bootstrap.run_bootstrap`) dan oleh job harian `entity_tax_status_due`.
    """
    from dependencies import audit
    day = (today or today_wib())[:10]
    rows = await db.business_entities.find(
        {"tax_status_pending.effective_date": {"$lte": day}},
        {"_id": 0, "id": 1, "default_tax_mode": 1, "tax_status_pending": 1}).to_list(500)
    applied = 0
    for row in rows:
        pending = row.get("tax_status_pending") or {}
        cur = row.get("default_tax_mode") or ""
        flt = {"id": row["id"], "default_tax_mode": cur, "tax_status_pending.at": pending.get("at")}
        now = now_iso()
        if pending.get("to") == cur:     # status sudah sama (diubah jalur lain) — jadwal dibuang tanpa riwayat
            await db.business_entities.update_one(flt, {"$unset": {"tax_status_pending": ""}})
            continue
        entry = {"from": cur, "to": pending.get("to"), "effective_date": pending.get("effective_date"),
                 "reason": pending.get("reason", ""), "by": pending.get("by", ""), "by_id": pending.get("by_id", ""),
                 "at": now, "scheduled_at": pending.get("at", "")}
        res = await db.business_entities.update_one(flt, {
            "$set": {"default_tax_mode": pending.get("to"), "updated_at": now},
            "$push": {"tax_status_history": entry}, "$unset": {"tax_status_pending": ""}})
        if not res.modified_count:
            continue
        applied += 1
        await audit("Sistem (jadwal)", "entity_tax_status_changed", "business_entity", row["id"],
                    {"from": cur, "to": pending.get("to"), "effective_date": pending.get("effective_date"),
                     "scheduled_by": pending.get("by", "")}, reason=pending.get("reason", ""),
                    scope_entity_id=row["id"])
    return applied


async def job_entity_tax_status_due() -> Dict[str, Any]:
    """Job harian `scheduler_service.JOBS` — "Terapkan Perubahan Status PKP Terjadwal"."""
    return {"applied": await apply_due_tax_status()}

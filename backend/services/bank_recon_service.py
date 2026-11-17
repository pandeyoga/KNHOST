"""FASE G-8 — REKONSILIASI BANK OTOMATIS (skor berbobot · split · aturan · titipan).

Rekonsiliasi mutasi bank (baris statement yang diimpor) terhadap `cash_transactions`
(SSOT kas). **Append-only & GL-safe:** rekonsiliasi TIDAK mengubah jurnal terposting —
ia hanya MENAUTKAN statement line ↔ cash_transaction. Satu-satunya jalur yang
menerbitkan jurnal baru adalah **titipan dana** (uang masuk yang belum teridentifikasi)
dan **alokasinya**, karena di sana memang ada uang nyata yang harus diakui.

KOLEKSI
-------
`bank_statement_lines`  (SCOPED `entity_id`)
    { id, bank_account_id, entity_id, stmt_date, amount(>0), direction in|out,
      description, counterparty, desc_key, ref, external_id, balance,
      status unmatched|matched|ignored|holding,
      match_kind ""|1:1|1:N|N:1, matched_txn_id, matched_txn_ids[],
      allocations[{txn_id, amount}], score, score_explain[], suggestions[],
      holding{cash_txn_id, je_id, at, by, note}, holding_allocated[], holding_remaining,
      import_batch, format_id, created_at, updated_at }
`bank_statement_formats` (SCOPED) — template parser per bank (`bsf_`).
`bank_match_rules`       (SCOPED) — aturan hasil pembelajaran (`bmr_`).

MENGAPA SKOR BERBOBOT
---------------------
Skor lama hanya 2 faktor (`ref cocok`, `tanggal terdekat`) tanpa penjelasan, sehingga
user tidak bisa menilai apakah sistem menebak benar. Kini setiap pasangan punya
`explain[]` — daftar alasan berpoin (nominal · tanggal · referensi · nama · aturan) yang
tampil di layar. Bobot & ambangnya ada di Pusat Pengaturan (`config_catalog_bank.py`),
bukan di dalam kode.

ISOLASI ENTITAS (F0-C)
----------------------
Sebelum fase ini `bank_statement_lines` TIDAK terdaftar sebagai koleksi SCOPED dan router
tidak memakai `entity_scope`: user PT-A cukup mengirim `bank_account_id` PT-B untuk
membaca mutasinya. Sekarang SETIAP fungsi menerima `entity_ids` (hasil
`resolve_scope_ids`) dan menolak (403) akun/baris di luar cakupan. Akun bank GRUP
(`entity_id == "all"`) tetap boleh dipakai semua entitas, tetapi barisnya di-stamp
dengan entitas AKTIF pengimpor supaya tetap terisolasi.
"""
import logging
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso, safe_doc, rupiah
from ai_card_context import card_field
from services import bank_statement_parser as parser
from services.book_date import tanggal_buku
from services.config_resolver import value_of
logger = logging.getLogger(__name__)


STATUS = ("unmatched", "matched", "ignored", "holding")
GROUP_ENTITY = "all"
EPS = 0.01
# PK-21 — kunci `match_lock` baris mutasi yang tertinggal lebih lama dari ini (proses mati di tengah) boleh diambil alih.
MATCH_LOCK_STALE_MINUTES = 10
PESAN_LEPAS_KONFLIK = "Mutasi bank ini baru saja dilepas atau diubah proses lain. Muat ulang."

CFG_KEYS = (
    "bank.match_weight_amount", "bank.match_weight_date", "bank.match_weight_ref",
    "bank.match_weight_name", "bank.auto_match_min_score", "bank.suggest_min_score",
    "bank.date_window_days", "bank.amount_tolerance", "bank.rule_learn_after",
    "bank.rule_bonus_score", "bank.holding_max_age_days",
)
# KF-T2 (KP-30, standar §1 P9) — akun titipan, biaya bank, dan bunga dibaca dari Pemetaan Akun per PT (dulu tiga kunci
# Pusat Pengaturan `bank.*_account_code`, kini `not_used`). Pindahan nilai lama: `scripts/migrate_kft2_akun_bank.py`.


# ═════════════════════════════════════════════════════════════════════════════
#  KONFIGURASI (Pusat Pengaturan — tidak ada angka sihir di kode)
# ═════════════════════════════════════════════════════════════════════════════
async def load_cfg(entity_id: str = "") -> Dict[str, Any]:
    from services import gl_mapping_service
    ctx = {"entity_id": entity_id or ""}
    raw = {}
    for k in CFG_KEYS:
        raw[k.split(".", 1)[1]] = await value_of(k, ctx)
    return {
        "w_amount": float(raw.get("match_weight_amount") or 0),
        "w_date": float(raw.get("match_weight_date") or 0),
        "w_ref": float(raw.get("match_weight_ref") or 0),
        "w_name": float(raw.get("match_weight_name") or 0),
        "auto_min": float(raw.get("auto_match_min_score") or 0),
        "suggest_min": float(raw.get("suggest_min_score") or 0),
        "window_days": int(raw.get("date_window_days") or 0),
        "amount_tol": float(raw.get("amount_tolerance") or 0),
        "learn_after": int(raw.get("rule_learn_after") or 3),
        "rule_bonus": float(raw.get("rule_bonus_score") or 0),
        "holding_acc": await gl_mapping_service.account_for("kas_bank.titipan_dana", entity_id),
        "holding_max_age_days": int(raw.get("holding_max_age_days") or 7),
        # Penutupan FASE G-8 — baris rekening koran yang memang TIDAK punya pasangan di buku
        # (biaya administrasi bank, bunga/jasa giro) dibukukan langsung ke akun ini. Tanpa
        # jalur ini "Selisih rekening vs buku" tidak pernah bisa nol.
        "charge_acc": await gl_mapping_service.account_for("kas_bank.beban_bank", entity_id),
        "interest_acc": await gl_mapping_service.account_for("kas_bank.pendapatan_bunga", entity_id),
    }


# ═════════════════════════════════════════════════════════════════════════════
#  UTILITAS
# ═════════════════════════════════════════════════════════════════════════════
def _d(s: Any) -> Optional[datetime]:
    """Tanggal buku WIB. Dulu `str(s)[:10]`: transaksi kas bercap waktu UTC (`txn_date` 2026-11-17T18:17Z = 18 Nov WIB)
    dinilai "Tanggal beda 1 hari" terhadap mutasi bank 18 Nov bila dicatat pukul 00.00–07.00 WIB (uji F10, 18 Nov)."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(tanggal_buku(s))
    except Exception:  # noqa: BLE001
        try:
            return datetime.fromisoformat(str(s)[:10])
        except Exception:  # noqa: BLE001
            return None


def _norm_dir(v: str) -> str:
    v = (v or "").strip().lower()
    if v in ("in", "credit", "cr", "masuk", "kredit", "debit_bank"):
        return "in"
    return "out"


def _round(v: Any) -> float:
    return round(float(v or 0), 2)


# ── PK-21 (SL-10) — status "terekonsiliasi" transaksi kas: SATU sumber ─────────────────────────────────────────
# `reconciled_amount` hanya ditulis modul ini (`_link`, `_unlink`, titipan, biaya bank) dan = Σ alokasi baris mutasi
# `matched` yang menunjuk transaksi + `amount` bila transaksi itu kas titipan baris `holding`. `reconciled` dan
# `matched_line_ids` TURUNAN: tidak pernah ditulis sendirian (tanda manual `/cash-transactions/{id}/reconcile` → 410).
def txn_reconciled(txn: Dict[str, Any]) -> bool:
    """Turunan `reconciled` dari angka: `reconciled_amount ≥ amount − 0,01` (dan > 0, supaya kas bernominal nol tidak
    pernah tampil terekonsiliasi). Dipakai semua pembaca — tanda `reconciled` lama yang tersimpan tidak dipercaya."""
    rec = _round(txn.get("reconciled_amount"))
    return rec > 0 and rec >= _round(txn.get("amount")) - EPS


def _stale_before() -> str:
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(minutes=MATCH_LOCK_STALE_MINUTES)).isoformat()


def _recon_pipeline(line_id: str, delta: float, attach: bool, now: str) -> List[Dict[str, Any]]:
    """PK-21 — SATU pembaruan ber-pipeline untuk transaksi kas: `reconciled_amount` ± `delta` (dibulatkan 2, tidak
    pernah negatif) dan `matched_line_ids` ± baris ini, lalu turunannya (`reconciled`, `reconciled_at`,
    `matched_line_id`) dihitung DATABASE dari nilai baru — bukan dari salinan yang dibaca sebelumnya (`02` D1)."""
    rec = {"$round": [{"$add": [{"$ifNull": ["$reconciled_amount", 0]}, delta]}, 2]}
    ids: Dict[str, Any] = {"$filter": {"input": {"$ifNull": ["$matched_line_ids", []]},
                                       "cond": {"$ne": ["$$this", line_id]}}}
    if attach:
        ids = {"$concatArrays": [ids, {"$literal": [line_id]}]}
    full = {"$and": [{"$gt": ["$reconciled_amount", 0]},
                     {"$gte": ["$reconciled_amount", {"$subtract": [{"$ifNull": ["$amount", 0]}, EPS]}]}]}
    keep_at = {"$literal": now} if attach else {"$ifNull": ["$reconciled_at", ""]}
    return [
        {"$set": {"reconciled_amount": {"$cond": [{"$lt": [rec, 0]}, 0, rec]}, "matched_line_ids": ids}},
        {"$set": {"reconciled": full,
                  "reconciled_at": {"$cond": [full, keep_at, ""]},
                  "matched_line_id": {"$cond": [{"$eq": [{"$size": "$matched_line_ids"}, 1]},
                                                {"$arrayElemAt": ["$matched_line_ids", 0]}, ""]},
                  "updated_at": {"$literal": now}}},
    ]


def _scope_q(entity_ids: Optional[List[str]], field: str = "entity_id") -> Dict[str, Any]:
    """Filter entitas. `None` = tanpa filter (khusus pemakaian internal/seed)."""
    if entity_ids is None:
        return {}
    ids = list(entity_ids)
    if GROUP_ENTITY not in ids:
        ids.append(GROUP_ENTITY)   # akun/transaksi kas GRUP boleh dilihat semua entitas
    return {field: {"$in": ids}}


async def _account(bank_account_id: str, entity_ids: Optional[List[str]]) -> Dict[str, Any]:
    acc = await db.bank_accounts.find_one({"id": bank_account_id}, {"_id": 0})
    if not acc:
        raise ValueError("Akun bank tidak ditemukan")
    if entity_ids is not None:
        owner = acc.get("entity_id") or ""
        if owner and owner != GROUP_ENTITY and owner not in entity_ids:
            raise HTTPException(status_code=403, detail="Tidak berwenang atas akun bank entitas ini")
    return acc


async def _line(line_id: str, entity_ids: Optional[List[str]]) -> Dict[str, Any]:
    ln = await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0})
    if not ln:
        raise ValueError("Baris mutasi tidak ditemukan")
    if entity_ids is not None:
        ent = ln.get("entity_id") or ""
        if ent and ent != GROUP_ENTITY and ent not in entity_ids:
            raise HTTPException(status_code=403, detail="Tidak berwenang atas mutasi entitas ini")
    return ln


def _stamp_entity(acc: Dict[str, Any], active_entity: str) -> str:
    owner = acc.get("entity_id") or ""
    if owner and owner != GROUP_ENTITY:
        return owner
    return active_entity or owner or GROUP_ENTITY


# ═════════════════════════════════════════════════════════════════════════════
#  TEMPLATE FORMAT BANK
# ═════════════════════════════════════════════════════════════════════════════
def _fmt_doc(payload: Dict[str, Any], entity_id: str, actor: str,
             builtin: bool = False) -> Dict[str, Any]:
    cols = payload.get("columns") or {}
    return {
        "id": payload.get("id") or new_id("bsf"),
        "entity_id": entity_id,
        "name": (payload.get("name") or "Template tanpa nama").strip(),
        "bank_code": (payload.get("bank_code") or "generic").strip().lower(),
        "file_kind": (payload.get("file_kind") or "csv").strip().lower(),
        "delimiter": payload.get("delimiter", ","),
        "has_header": bool(payload.get("has_header", True)),
        "skip_rows": int(payload.get("skip_rows") or 0),
        "decimal_style": (payload.get("decimal_style") or "auto").lower(),
        "date_format": (payload.get("date_format") or "auto"),
        "columns": {k: cols.get(k, "") for k in
                    ("date", "description", "ref", "amount", "amount_in", "amount_out",
                     "direction", "balance", "external_id")},
        "in_markers": list(payload.get("in_markers") or []),
        "out_markers": list(payload.get("out_markers") or []),
        "header_signature": list(payload.get("header_signature") or []),
        "note": payload.get("note", ""),
        "builtin": builtin,
        "active": bool(payload.get("active", True)),
        "created_by": actor,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


async def ensure_builtin_formats(entity_id: str = "", actor: str = "system") -> int:
    """Pasang preset bawaan SEKALI untuk semua entitas (`entity_id="all"`).

    KN-G8-FORMAT-DUP (temuan penutupan fase): preset dulu dipasang PER ENTITAS, sehingga
    pemilik 2 PT melihat SETIAP template bawaan dua kali ("BCA — Rekening Koran (CSV)"
    muncul 2×) tanpa cara membedakannya — baik di pengelola template maupun di pemilih
    template pada panel impor. Preset adalah pengetahuan tentang format BANK, bukan data
    milik entitas, jadi cukup satu salinan GRUP yang boleh dibaca semua entitas
    (`_scope_q` selalu menyertakan entitas GRUP).

    Salinan lama per-entitas DIPADAMKAN (`active=False`) — tidak dihapus, supaya baris
    mutasi lama yang menyimpan `format_id` tetap bisa dilacak. Idempoten.
    """
    made = 0
    for f in parser.BUILTIN_FORMATS:
        exists = await db.bank_statement_formats.find_one(
            {"entity_id": GROUP_ENTITY, "name": f["name"], "builtin": True}, {"_id": 1})
        if not exists:
            await db.bank_statement_formats.insert_one(
                _fmt_doc(f, GROUP_ENTITY, actor, builtin=True))
            made += 1
        await db.bank_statement_formats.update_many(
            {"name": f["name"], "builtin": True, "entity_id": {"$ne": GROUP_ENTITY},
             "active": True},
            {"$set": {"active": False, "updated_at": now_iso()}})
    return made


async def list_formats(entity_ids: Optional[List[str]], active_entity: str = "",
                       actor: str = "system") -> List[Dict[str, Any]]:
    await ensure_builtin_formats(active_entity, actor)
    q = {**_scope_q(entity_ids), "active": True}
    rows = await db.bank_statement_formats.find(q, {"_id": 0}).sort("name", 1).to_list(500)
    return [safe_doc(r) for r in rows]


async def upsert_format(payload: Dict[str, Any], entity_id: str, actor: str,
                        entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    fid = payload.get("id") or ""
    if fid:
        cur = await db.bank_statement_formats.find_one({"id": fid}, {"_id": 0})
        if not cur:
            raise ValueError("Template tidak ditemukan")
        if cur.get("builtin"):
            # Preset bawaan dipakai BERSAMA semua PT — menyuntingnya di tempat akan mengubah
            # template semua orang. Jadi hasil suntingan disimpan sebagai template BARU milik
            # entitas penyunting, tepat seperti yang dijanjikan layar: "buka, ubah pemetaan
            # kolomnya, lalu simpan sebagai template Anda sendiri".
            name = (payload.get("name") or cur.get("name") or "").strip()
            if name == (cur.get("name") or "").strip():
                name = f"{name} — salinan"
            doc = _fmt_doc({**cur, **payload, "id": "", "name": name}, entity_id, actor,
                           builtin=False)
            await db.bank_statement_formats.insert_one(doc)
            return safe_doc(doc)
        if entity_ids is not None and cur.get("entity_id") not in list(entity_ids) + [GROUP_ENTITY]:
            raise HTTPException(status_code=403, detail="Template milik entitas lain")
        doc = _fmt_doc({**cur, **payload, "id": fid}, cur.get("entity_id") or entity_id, actor,
                       builtin=bool(cur.get("builtin")))
        doc["created_at"] = cur.get("created_at") or doc["created_at"]
        doc["created_by"] = cur.get("created_by") or actor
        await db.bank_statement_formats.replace_one({"id": fid}, doc)
        return safe_doc(doc)
    doc = _fmt_doc(payload, entity_id, actor)
    await db.bank_statement_formats.insert_one(doc)
    return safe_doc(doc)


async def delete_format(format_id: str, entity_ids: Optional[List[str]] = None) -> None:
    cur = await db.bank_statement_formats.find_one({"id": format_id}, {"_id": 0})
    if not cur:
        raise ValueError("Template tidak ditemukan")
    if cur.get("builtin"):
        raise ValueError("Template bawaan tidak bisa dinonaktifkan — buka lalu simpan sebagai "
                         "salinan Anda sendiri, dan sunting salinannya")
    if entity_ids is not None and cur.get("entity_id") not in list(entity_ids) + [GROUP_ENTITY]:
        raise HTTPException(status_code=403, detail="Template milik entitas lain")
    await db.bank_statement_formats.update_one({"id": format_id}, {"$set": {
        "active": False, "updated_at": now_iso()}})


async def _resolve_format(format_id: str, fmt: Optional[Dict[str, Any]], raw: str,
                          entity_ids: Optional[List[str]],
                          active_entity: str) -> Tuple[Dict[str, Any], bool]:
    """Ambil template: eksplisit → dikirim langsung → deteksi otomatis. (fmt, terdeteksi)."""
    if format_id:
        doc = await db.bank_statement_formats.find_one({"id": format_id}, {"_id": 0})
        if not doc:
            raise ValueError("Template tidak ditemukan")
        # Preset bawaan milik entitas GRUP ("all") boleh dipakai semua entitas — sama seperti
        # akun bank grup (lihat `_scope_q`). Tanpa pengecualian ini, memilih template bawaan
        # dari layar impor akan ditolak 403 (regresi KN-G8-FORMAT-DUP).
        if (entity_ids is not None and doc.get("entity_id")
                not in list(entity_ids) + [GROUP_ENTITY]):
            raise HTTPException(status_code=403, detail="Template milik entitas lain")
        return doc, False
    if fmt:
        return _fmt_doc(fmt, active_entity, "preview"), False
    known = await list_formats(entity_ids, active_entity)
    hit = parser.detect_format(raw, known)
    if hit:
        return hit, True
    raise ValueError("Template tidak dikenali dari isi berkas — pilih template secara manual")


async def preview(raw: str, format_id: str = "", fmt: Optional[Dict[str, Any]] = None,
                  entity_ids: Optional[List[str]] = None, active_entity: str = "",
                  year_hint: int = 0, limit: int = 50) -> Dict[str, Any]:
    """Baca mutasi TANPA menyimpan — user melihat hasil sebelum impor."""
    fdoc, detected = await _resolve_format(format_id, fmt, raw, entity_ids, active_entity)
    rows, errors = parser.parse_rows(raw, fdoc, year_hint)
    return {
        "format": {"id": fdoc.get("id", ""), "name": fdoc.get("name", ""),
                   "bank_code": fdoc.get("bank_code", ""), "file_kind": fdoc.get("file_kind", "")},
        "detected": detected,
        "rows": rows[:limit],
        "total": len(rows),
        "errors": errors[:20],
        "error_count": len(errors),
        "sum_in": _round(sum(r["amount"] for r in rows if r["direction"] == "in")),
        "sum_out": _round(sum(r["amount"] for r in rows if r["direction"] == "out")),
    }


# ═════════════════════════════════════════════════════════════════════════════
#  IMPOR
# ═════════════════════════════════════════════════════════════════════════════
#: M38 (pemilik 16 Nov: "saya bisa cocokkan otomatis padahal saya tidak upload berkas") — asal tiap baris mutasi dicatat:
#: `berkas` (unggah berkas bank), `tempel` (input/tempel baris), `contoh` (data demo dibuat dari catatan kas sendiri).
#: Baris lama tanpa catatan = "tidak tercatat".
IMPORT_SOURCES = ("berkas", "tempel", "contoh")


def _line_doc(bank_account_id: str, entity_id: str, r: Dict[str, Any], batch: str,
              format_id: str, source: str = "", actor: str = "", file_name: str = "") -> Dict[str, Any]:
    desc = (r.get("description") or "").strip()
    now = now_iso()
    return {
        "id": new_id("stmtline"), "bank_account_id": bank_account_id, "entity_id": entity_id,
        "stmt_date": str(r.get("stmt_date") or "")[:10], "amount": _round(r.get("amount")),
        "direction": _norm_dir(r.get("direction")), "description": desc,
        "counterparty": r.get("counterparty") or parser.counterparty_of(desc),
        "desc_key": r.get("desc_key") or parser.desc_key(desc),
        "ref": (r.get("ref") or "").strip(), "external_id": (r.get("external_id") or "").strip(),
        "balance": _round(r.get("balance")),
        "status": "unmatched", "match_kind": "", "matched_txn_id": "", "matched_txn_ids": [],
        "allocations": [], "score": 0, "score_explain": [], "suggestions": [],
        "match_type": "", "matched_at": "", "matched_by": "",
        "holding": {}, "holding_allocated": [], "holding_remaining": 0.0,
        "import_batch": batch, "format_id": format_id,
        "import_source": source if source in IMPORT_SOURCES else "", "imported_by": actor or "",
        "import_file": (file_name or "")[:200],
        "created_at": now, "updated_at": now,
    }


async def _dup_exists(bank_account_id: str, doc: Dict[str, Any]) -> bool:
    q: Dict[str, Any] = {"bank_account_id": bank_account_id}
    if doc.get("external_id"):
        q["external_id"] = doc["external_id"]
    else:
        q.update({"stmt_date": doc["stmt_date"], "amount": doc["amount"],
                  "direction": doc["direction"], "description": doc["description"]})
    return bool(await db.bank_statement_lines.find_one(q, {"_id": 1}))


async def import_lines(bank_account_id: str, entity_id: str, lines: List[Dict[str, Any]],
                       actor: str, entity_ids: Optional[List[str]] = None,
                       active_entity: str = "", format_id: str = "", source: str = "",
                       file_name: str = "") -> Dict[str, Any]:
    """Impor baris mutasi yang SUDAH terstruktur (dipakai juga oleh seed & impor berkas).

    `source` (M38) — asal baris: `berkas` / `tempel` / `contoh`; pemanggil seed (`actor == "seed"`) = `contoh`."""
    if not source:
        source = "contoh" if actor == "seed" else "tempel"
    acc = await _account(bank_account_id, entity_ids)
    ent = entity_id or _stamp_entity(acc, active_entity)
    batch = new_id("stmtbatch")
    imported, skipped = 0, 0
    errors: List[Dict[str, Any]] = []
    for i, r in enumerate(lines or [], start=1):
        doc = _line_doc(bank_account_id, ent, r, batch, format_id, source, actor, file_name)
        # G3 D4-BANK-01 — semua jalur (berkas, input langsung, seed) lewat validator kalender ketat.
        if not parser.strict_iso_date(doc["stmt_date"]):
            errors.append({"row": r.get("row") or i, "reason": f"Tanggal tidak sah: {doc['stmt_date'] or '(kosong)'}"})
            skipped += 1
            continue
        if doc["amount"] <= 0:
            errors.append({"row": r.get("row") or i, "reason": "Nominal tidak sah / nol"})
            skipped += 1
            continue
        if await _dup_exists(bank_account_id, doc):
            skipped += 1
            continue
        doc["pay_code_hits"] = await pay_code_hits(doc)   # PM-T3 — kode bayar di berita/referensi transfer
        await db.bank_statement_lines.insert_one(doc)
        imported += 1
    return {"import_batch": batch, "imported": imported, "skipped": skipped, "line_errors": errors}


async def import_raw(bank_account_id: str, raw: str, format_id: str = "",
                     fmt: Optional[Dict[str, Any]] = None,
                     entity_ids: Optional[List[str]] = None, active_entity: str = "",
                     actor: str = "", year_hint: int = 0, file_name: str = "") -> Dict[str, Any]:
    """Impor dari ISI BERKAS (CSV/MT940/OFX) memakai template."""
    fdoc, detected = await _resolve_format(format_id, fmt, raw, entity_ids, active_entity)
    rows, errors = parser.parse_rows(raw, fdoc, year_hint)
    if not rows:
        raise ValueError("Tidak ada baris mutasi yang bisa dibaca — periksa template/berkas")
    # M38 — teks rekening koran yang DITEMPEL ke kotak (tanpa nama berkas) tercatat `tempel`, bukan `berkas`
    # (dulu semua impor lewat jalur ini berlabel "berkas" sehingga ringkasan menulis "Impor terakhir: berkas").
    res = await import_lines(bank_account_id, "", rows, actor, entity_ids, active_entity,
                             fdoc.get("id", ""), source="berkas" if (file_name or "").strip() else "tempel",
                             file_name=file_name)
    res.update({"format_id": fdoc.get("id", ""), "format_name": fdoc.get("name", ""),
                "detected": detected, "parsed": len(rows),
                "errors": errors[:20], "error_count": len(errors)})
    return res


# ── PM-T3 — kode bayar (PM-T2) di berita transfer ────────────────────────────────────────────────────────────────
async def pay_code_hits(line: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Kode bayar terdaftar yang muncul di berita + referensi satu mutasi → `[{code, order_id, order_number,
    customer_id}]`. Hanya kode milik PT mutasi itu (`02` N2: id yang ditemukan dibuktikan milik PT yang sama)."""
    from services import payment_code_service as pcs
    teks = f"{line.get('description') or ''} {line.get('ref') or ''}"
    ent = line.get("entity_id") or ""
    out = []
    for c in await pcs.find_in_text(teks):
        if ent and ent != GROUP_ENTITY and (c.get("entity_id") or "") != ent:
            continue
        out.append({"code": c.get("code", ""), "order_id": c.get("order_id", ""),
                    "order_number": c.get("order_number", ""), "customer_id": c.get("customer_id", "")})
    return out


async def _isi_hits(lines: List[Dict[str, Any]]) -> None:
    """Mutasi yang diimpor sebelum PM-T3 belum menyimpan `pay_code_hits`: dihitung di memori (tidak ditulis)."""
    for ln in lines:
        if "pay_code_hits" not in ln:
            ln["pay_code_hits"] = await pay_code_hits(ln)


async def _lengkapi_hits(lines: List[Dict[str, Any]]) -> None:
    """PM-T3 (layar) — tiap butir `pay_code_hits` diberi `customer_name` dan `has_open_receipt` (sudah ada kwitansi
    tidak batal untuk pesanan itu yang belum terverifikasi bank → cocokkan, jangan catat kwitansi baru)."""
    oids = sorted({h.get("order_id") for ln in lines for h in (ln.get("pay_code_hits") or []) if h.get("order_id")})
    if not oids:
        return
    cids = sorted({h.get("customer_id") for ln in lines for h in (ln.get("pay_code_hits") or []) if h.get("customer_id")})
    nama = {c["id"]: c.get("name", "") async for c in db.customers.find({"id": {"$in": cids}}, {"_id": 0, "id": 1,
                                                                                               "name": 1})}
    terbuka = set()
    async for rc in db.ar_receipts.find({"allocations.order_id": {"$in": oids}, "status": {"$ne": "void"},
                                         "bank_verified": {"$ne": True}, "amount": {"$gt": EPS}},
                                        {"_id": 0, "allocations.order_id": 1}):
        terbuka |= {a.get("order_id") for a in rc.get("allocations") or []}
    for ln in lines:
        for h in ln.get("pay_code_hits") or []:
            h["customer_name"] = nama.get(h.get("customer_id"), "")
            h["has_open_receipt"] = h.get("order_id") in terbuka


async def _tandai_pesanan_kwitansi(txns: List[Dict[str, Any]]) -> None:
    """PM-T3 — kas kwitansi diberi `_kwitansi_pesanan` = {id pesanan: nomor} dari alokasi kwitansinya (bahan langkah
    kode bayar `score_pair`; field berawalan `_` tidak pernah dikirim ke layar)."""
    ids = [t.get("ref_id") for t in txns if t.get("ref_type") == "ar_receipt" and t.get("ref_id")]
    peta: Dict[str, Dict[str, str]] = {}
    if ids:
        async for rc in db.ar_receipts.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "allocations": 1}):
            peta[rc["id"]] = {a.get("order_id"): a.get("order_number") or a.get("order_id")
                             for a in rc.get("allocations") or [] if a.get("order_id")}
    for t in txns:
        t["_kwitansi_pesanan"] = peta.get(t.get("ref_id"), {}) if t.get("ref_type") == "ar_receipt" else {}


def _kode_cocok(line: Dict[str, Any], txn: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    pesanan = txn.get("_kwitansi_pesanan") or {}
    for h in line.get("pay_code_hits") or []:
        if h.get("order_id") in pesanan:
            return {**h, "order_number": h.get("order_number") or pesanan[h["order_id"]]}
    return None


# ═════════════════════════════════════════════════════════════════════════════
#  SKOR BERBOBOT (dengan penjelasan yang dibaca manusia)
# ═════════════════════════════════════════════════════════════════════════════
def _txn_text(txn: Dict[str, Any]) -> str:
    return " ".join(str(txn.get(k, "") or "") for k in
                    ("number", "description", "category", "ref_id", "counterparty_name"))


def _ref_score(line: Dict[str, Any], txn: Dict[str, Any], w: float) -> Tuple[float, str]:
    if w <= 0:
        return 0.0, ""
    hay = _txn_text(txn).upper()
    toks = [t for t in ([line.get("ref")] + parser.ref_tokens_of(line.get("description", "")))
            if t]
    for t in toks:
        tu = str(t).upper()
        if len(tu) >= 4 and tu in hay:
            return w, f"nomor referensi '{tu}' ada di transaksi buku"
    for t in toks:
        digits = re.sub(r"\D", "", str(t))
        if len(digits) >= 4 and digits[-4:] in re.sub(r"\D", "", hay):
            return round(w / 2, 2), f"sebagian nomor ('…{digits[-4:]}') cocok"
    return 0.0, ""


def _name_score(line: Dict[str, Any], txn: Dict[str, Any], w: float) -> Tuple[float, str]:
    if w <= 0:
        return 0.0, ""
    cp = (line.get("counterparty") or parser.counterparty_of(line.get("description", ""))).lower()
    if not cp:
        return 0.0, ""
    cands = [str(txn.get(k, "") or "") for k in
             ("customer_name", "counterparty_name", "description", "category")]
    best, who = 0.0, ""
    for c in cands:
        if not c:
            continue
        r = SequenceMatcher(None, cp, c.lower()).ratio()
        # nama pelanggan sering hanya SEBAGIAN dari berita transfer → cek keterkandungan
        if c.lower() in cp or cp in c.lower():
            r = max(r, 0.9)
        if r > best:
            best, who = r, c
    if best >= 0.8:
        return w, f"nama mirip '{who[:40]}' ({int(best * 100)}%)"
    if best >= 0.6:
        return round(w / 2, 2), f"nama agak mirip '{who[:40]}' ({int(best * 100)}%)"
    return 0.0, ""


def score_pair(line: Dict[str, Any], txn: Dict[str, Any], cfg: Dict[str, Any],
               rule: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Skor 0..100+ untuk satu pasangan (baris bank ↔ transaksi buku), dengan alasan.

    Return {"score", "explain":[{label, points}], "amount_diff", "day_diff", "eligible"}.
    `eligible=False` artinya pasangan tidak layak dipertimbangkan sama sekali
    (arah berbeda / nominal terlalu jauh / tanggal di luar jendela).
    """
    explain: List[Dict[str, Any]] = []
    if _norm_dir(txn.get("direction")) != _norm_dir(line.get("direction")):
        return {"score": 0, "explain": [], "eligible": False, "amount_diff": 0, "day_diff": 0,
                "reason": "arah dana berbeda"}

    l_amt, t_amt = _round(line.get("amount")), _round(txn.get("amount"))
    diff = round(abs(l_amt - t_amt), 2)
    tol = max(cfg["amount_tol"], 0.0)
    # PM-T3 — langkah paling awal: kode bayar di berita transfer menunjuk pesanan yang dialokasi kwitansi di balik kas
    # ini. Nominal sama (dalam toleransi) → skor minimal ambang otomatis; nominal berbeda → tetap layak sebagai USULAN
    # (skor minimal ambang usulan) dan tidak pernah tertaut otomatis (`no_auto`). Jendela tanggal tidak menggugurkan.
    kode = _kode_cocok(line, txn)
    if kode:
        return _skor_kode(line, txn, cfg, rule, kode, diff, tol)
    if diff <= tol + 0.001:
        pts = cfg["w_amount"]
        explain.append({"label": "Nominal sama" + (f" (selisih {rupiah(diff)} ≤ toleransi)" if diff else ""),
                        "points": pts})
    elif diff <= max(tol * 2, l_amt * 0.01):
        pts = round(cfg["w_amount"] * 0.6, 2)
        explain.append({"label": f"Nominal beda tipis {rupiah(diff)} (≤1%)", "points": pts})
    else:
        return {"score": 0, "explain": [], "eligible": False, "amount_diff": diff, "day_diff": 0,
                "reason": f"nominal beda {rupiah(diff)}"}
    total = pts

    ld, td = _d(line.get("stmt_date")), _d(txn.get("txn_date") or txn.get("created_at"))
    day_diff = abs((td - ld).days) if (td and ld) else 999
    window = max(cfg["window_days"], 0)
    if day_diff > window:
        return {"score": 0, "explain": [], "eligible": False, "amount_diff": diff,
                "day_diff": day_diff, "reason": f"selisih {day_diff} hari di luar jendela {window} hari"}
    if cfg["w_date"] > 0:
        pts_d = cfg["w_date"] if day_diff == 0 else round(
            cfg["w_date"] * (1 - (day_diff / (window + 1))), 2)
        explain.append({"label": "Tanggal sama" if day_diff == 0 else f"Tanggal beda {day_diff} hari",
                        "points": pts_d})
        total += pts_d

    pts_r, why_r = _ref_score(line, txn, cfg["w_ref"])
    if pts_r:
        explain.append({"label": why_r, "points": pts_r})
        total += pts_r
    pts_n, why_n = _name_score(line, txn, cfg["w_name"])
    if pts_n:
        explain.append({"label": why_n, "points": pts_n})
        total += pts_n
    if rule and cfg["rule_bonus"] > 0:
        explain.append({"label": f"Aturan tersimpan: {rule.get('sample_desc', '')[:40]}",
                        "points": cfg["rule_bonus"]})
        total += cfg["rule_bonus"]
    return {"score": round(total, 2), "explain": explain, "eligible": True,
            "amount_diff": diff, "day_diff": day_diff, "reason": ""}


def _skor_kode(line: Dict[str, Any], txn: Dict[str, Any], cfg: Dict[str, Any], rule: Optional[Dict[str, Any]],
               kode: Dict[str, Any], diff: float, tol: float) -> Dict[str, Any]:
    """PM-T3 — skor pasangan yang kode bayarnya cocok (lihat `score_pair`)."""
    sama = diff <= tol + 0.001
    explain: List[Dict[str, Any]] = []
    total = 0.0
    if sama:
        explain.append({"label": "Nominal sama" + (f" (selisih {rupiah(diff)} ≤ toleransi)" if diff else ""),
                        "points": cfg["w_amount"]})
        total += cfg["w_amount"]
    ld, td = _d(line.get("stmt_date")), _d(txn.get("txn_date") or txn.get("created_at"))
    day_diff = abs((td - ld).days) if (td and ld) else 999
    window = max(cfg["window_days"], 0)
    if cfg["w_date"] > 0 and day_diff <= window:
        pts_d = cfg["w_date"] if day_diff == 0 else round(cfg["w_date"] * (1 - (day_diff / (window + 1))), 2)
        explain.append({"label": "Tanggal sama" if day_diff == 0 else f"Tanggal beda {day_diff} hari",
                        "points": pts_d})
        total += pts_d
    for pts, why in (_ref_score(line, txn, cfg["w_ref"]), _name_score(line, txn, cfg["w_name"])):
        if pts:
            explain.append({"label": why, "points": pts})
            total += pts
    if rule and cfg["rule_bonus"] > 0:
        explain.append({"label": f"Aturan tersimpan: {rule.get('sample_desc', '')[:40]}", "points": cfg["rule_bonus"]})
        total += cfg["rule_bonus"]
    target = cfg["auto_min"] if sama else cfg["suggest_min"]
    tambah = round(max(0.0, target - total), 2)
    label = (f"Kode bayar {kode['code']} cocok dengan pesanan {kode.get('order_number') or ''}".strip() if sama
             else f"Kode bayar cocok, nominal berbeda {rupiah(diff)}")
    explain.insert(0, {"label": label, "points": tambah})
    return {"score": round(total + tambah, 2), "explain": explain, "eligible": True, "amount_diff": diff,
            "day_diff": day_diff, "reason": "", "pay_code": kode["code"], "no_auto": not sama}


# ═════════════════════════════════════════════════════════════════════════════
#  KANDIDAT & PENCOCOKAN
# ═════════════════════════════════════════════════════════════════════════════
async def _book_query(acc: Dict[str, Any], entity_ids: Optional[List[str]]) -> Dict[str, Any]:
    """Transaksi BUKU milik satu rekening.

    PM-T3 (PM-04) — hanya kas ber-`account_id` rekening ini. Kas lama TANPA rekening (sebelum PK-20) ikut ditawarkan
    HANYA bila rekening ini satu-satunya rekening aktif PT-nya untuk jenis kas itu (`bank_service.sole_account_id`,
    aturan yang sama dengan saldo rekening `_txns_for`), dan hanya kas PT pemilik rekening. Dulu kas tanpa rekening
    berjenis sama ditawarkan ke SEMUA rekening (kwitansi rekening mana pun ikut muncul, bahkan lintas PT dalam cakupan
    pengguna). Kas lama di PT berekening ganda diisi lewat `scripts/backfill_receipt_accounts.py` (H3) atau diputus
    orang dari keluarannya."""
    from services.bank_service import account_cash_type, sole_account_id
    kind = account_cash_type(acc)
    pilihan: List[Dict[str, Any]] = [{"account_id": acc["id"]}]
    owner = acc.get("entity_id") or ""
    if owner and owner != GROUP_ENTITY and await sole_account_id(owner, kind) == acc["id"]:
        pilihan += [{"account_id": {"$in": ["", None]}, "cash_type": kind, "entity_id": owner},
                    {"account_id": {"$exists": False}, "cash_type": kind, "entity_id": owner}]
    return {"status": {"$ne": "void"}, "$or": pilihan, **_scope_q(entity_ids)}


async def _candidate_txns(bank_account_id: str, entity_ids: Optional[List[str]],
                          include_partial: bool = True) -> List[Dict[str, Any]]:
    acc = await db.bank_accounts.find_one({"id": bank_account_id}, {"_id": 0})
    if not acc:
        return []
    rows = await db.cash_transactions.find(await _book_query(acc, entity_ids), {"_id": 0}).to_list(20000)
    out = []
    for t in rows:
        # PK-21 — dari angka, bukan tanda `reconciled` tersimpan (tanda manual lama tidak menyembunyikan/menampilkan).
        if txn_reconciled(t) or (not include_partial and _round(t.get("reconciled_amount")) > EPS):
            continue
        out.append(t)
    await _tandai_pesanan_kwitansi(out)   # PM-T3 — bahan langkah kode bayar
    return out


async def _active_rules(bank_account_id: str, entity_ids: Optional[List[str]]) -> Dict[str, Dict[str, Any]]:
    q = {"bank_account_id": bank_account_id, "status": "active", **_scope_q(entity_ids)}
    rows = await db.bank_match_rules.find(q, {"_id": 0}).to_list(2000)
    return {r["desc_key"]: r for r in rows if r.get("desc_key")}


def _rule_for(line: Dict[str, Any], rules: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    key = line.get("desc_key") or parser.desc_key(line.get("description", ""))
    if not key:
        return None
    r = rules.get(key)
    if r and _norm_dir(r.get("direction")) == _norm_dir(line.get("direction")):
        return r
    return None


def _txn_brief(t: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": t.get("id"), "number": t.get("number", ""), "amount": _round(t.get("amount")),
            "direction": t.get("direction"), "txn_date": t.get("txn_date", ""),
            "description": t.get("description", ""),
            "outstanding": _round(_round(t.get("amount")) - _round(t.get("reconciled_amount")))}


async def candidates(line_id: str, entity_ids: Optional[List[str]] = None,
                     limit: int = 8) -> Dict[str, Any]:
    """Kandidat berperingkat + penjelasan skor untuk satu baris (dipakai modal UI)."""
    ln = await _line(line_id, entity_ids)
    await _isi_hits([ln])   # PM-T3
    cfg = await load_cfg(ln.get("entity_id", ""))
    rules = await _active_rules(ln["bank_account_id"], entity_ids)
    rule = _rule_for(ln, rules)
    txns = await _candidate_txns(ln["bank_account_id"], entity_ids)
    scored = []
    for t in txns:
        s = score_pair(ln, t, cfg, rule)
        if not s["eligible"]:
            continue
        scored.append({**_txn_brief(t), "score": s["score"], "explain": s["explain"]})
    scored.sort(key=lambda r: -r["score"])
    return {"line": safe_doc(ln), "candidates": scored[:limit],
            "auto_min": cfg["auto_min"], "suggest_min": cfg["suggest_min"],
            "rule_applied": bool(rule)}


async def _assert_target(ln: Dict[str, Any], t: Dict[str, Any], entity_ids: Optional[List[str]]) -> None:
    """CX-06 — validator TUNGGAL target rekonsiliasi (manual/split/group): transaksi kas milik
    buku rekening baris ini, arah dana sama, belum void."""
    if t.get("status") == "void":
        raise ValueError(f"Transaksi {t.get('number')} sudah void")
    if _norm_dir(t.get("direction")) != _norm_dir(ln.get("direction")):
        raise ValueError(f"Arah dana transaksi {t.get('number')} berbeda dgn mutasi")
    acc = await db.bank_accounts.find_one({"id": ln.get("bank_account_id")}, {"_id": 0})
    if not acc or not await db.cash_transactions.find_one(
            {"$and": [{"id": t["id"]}, await _book_query(acc, entity_ids)]}, {"_id": 0, "id": 1}):
        raise ValueError(f"Transaksi {t.get('number')} bukan milik buku rekening mutasi ini")


async def _link(line: Dict[str, Any], allocations: List[Dict[str, Any]], actor: str,
                match_type: str, match_kind: str) -> None:
    """Tautkan satu baris ke satu/beberapa transaksi buku (append-only pada dua sisi).
    CX-07 — kapasitas transaksi diklaim ATOMIK (CAS reconciled_amount+alokasi ≤ amount);
    satu gagal → alokasi yang sudah diklaim dikembalikan dan tidak ada yang ditautkan."""
    now = now_iso()
    merged: Dict[str, float] = {}
    for a in allocations:
        merged[a["txn_id"]] = _round(merged.get(a["txn_id"], 0.0) + _round(a["amount"]))
    allocations = [{"txn_id": k, "amount": v} for k, v in merged.items()]
    # G3 V3-BANK-01 — baris mutasi DIKLAIM dulu (CAS status+kunci) sebelum kapasitas transaksi:
    # dua pencocokan paralel atas satu baris → satu menang, yang lain konflik tanpa efek.
    op = new_id("bmatch")
    got = await db.bank_statement_lines.update_one(
        {"id": line["id"], "status": {"$nin": ["matched", "ignored"]},
         "$or": [{"match_lock": {"$exists": False}}, {"match_lock_at": {"$lt": _stale_before()}}]},
        {"$set": {"match_lock": op, "match_lock_at": now}})
    if got.modified_count != 1:
        raise ValueError("Mutasi bank ini baru saja dicocokkan proses lain — muat ulang.")
    claimed: List[Dict[str, Any]] = []
    for a in allocations:
        amt = _round(a["amount"])
        # PK-21 — klaim kapasitas DAN turunannya (`reconciled`, `matched_line_ids`, …) dalam SATU pembaruan bersyarat;
        # dulu turunan ditulis sesudahnya dari salinan yang dibaca ulang (bisa basi bila proses lain menyela).
        res = await db.cash_transactions.update_one(
            {"id": a["txn_id"], "status": {"$ne": "void"},
             "$expr": {"$lte": [{"$add": [{"$ifNull": ["$reconciled_amount", 0]}, amt]},
                                {"$add": ["$amount", EPS]}]}},
            _recon_pipeline(line["id"], amt, True, now))
        if res.modified_count != 1:
            for c in claimed:
                await db.cash_transactions.update_one(
                    {"id": c["txn_id"], "$expr": {"$gte": [{"$ifNull": ["$reconciled_amount", 0]}, c["amount"] - EPS]}},
                    _recon_pipeline(line["id"], -c["amount"], False, now))
            await db.bank_statement_lines.update_one({"id": line["id"], "match_lock": op},
                                                     {"$unset": {"match_lock": "", "match_lock_at": ""}})
            raise ValueError("Sisa transaksi buku tidak cukup (baru saja dipakai proses lain / alokasi ganda).")
        claimed.append({"txn_id": a["txn_id"], "amount": amt})
    txn_ids = [a["txn_id"] for a in allocations]
    # AG-T3 — catatan cocok dari kartu tindakan asisten membawa `ai_card_id`; dicocokkan di layar → field dihapus
    # (tidak mewarisi id kartu dari pencocokan sebelumnya yang sudah dilepas).
    kartu = card_field()
    await db.bank_statement_lines.update_one({"id": line["id"], "match_lock": op}, {"$set": {
        "status": "matched", "match_kind": match_kind,
        "matched_txn_id": txn_ids[0] if len(txn_ids) == 1 else "",
        "matched_txn_ids": txn_ids, "allocations": allocations,
        "match_type": match_type, "matched_at": now, "matched_by": actor, **kartu,
        "updated_at": now}, "$unset": {"match_lock": "", "match_lock_at": "", **({} if kartu else {"ai_card_id": ""})}})
    await sinkron_verifikasi_kwitansi(txn_ids, actor, now)   # PM-T3


async def _unlink(line: Dict[str, Any], op: str = "", actor: str = "") -> None:
    """PK-21 (SL-10) — lepas-cocok BERSYARAT, aman bila dua permintaan datang bersamaan.

    1. KLAIM baris: `status == matched` dan `match_lock` kosong/basi → pasang `match_lock`. Gagal → 409. Alokasi dibaca
       dari dokumen HASIL KLAIM (bukan dari salinan pemanggil).
       Baris biaya/bunga bank: kas di-void + jurnal dibalik SESUDAH klaim; gagal → kunci dicabut, baris tetap `matched`.
    2. Tiap alokasi: satu pembaruan bersyarat `reconciled_amount ≥ alokasi − 0,01` yang menulis sekaligus angka dan
       turunannya (`_recon_pipeline`). Tidak cocok → sudah dilepas proses lain; dicatat di log, dilewati.
    3. Baris → `unmatched`, tautan dikosongkan, kunci dicabut — bersyarat kunci milik operasi ini.
    """
    now = now_iso()
    op = op or new_id("bunmatch")
    claimed = await db.bank_statement_lines.find_one_and_update(
        {"id": line["id"], "status": "matched",
         "$or": [{"match_lock": {"$exists": False}}, {"match_lock_at": {"$lt": _stale_before()}}]},
        {"$set": {"match_lock": op, "match_lock_at": now}}, projection={"_id": 0})
    if not claimed:
        raise HTTPException(status_code=409, detail=PESAN_LEPAS_KONFLIK)
    if claimed.get("match_type") == "charge":
        try:
            await _reverse_charge(claimed, actor)
        except Exception:
            await db.bank_statement_lines.update_one({"id": line["id"], "match_lock": op},
                                                     {"$unset": {"match_lock": "", "match_lock_at": ""}})
            raise
    for a in (claimed.get("allocations") or []):
        amt = _round(a.get("amount"))
        res = await db.cash_transactions.update_one(
            {"id": a.get("txn_id"), "$expr": {"$gte": [{"$ifNull": ["$reconciled_amount", 0]}, amt - EPS]}},
            _recon_pipeline(line["id"], -amt, False, now))
        if res.modified_count != 1:
            logger.warning("[PK-21 _unlink] %s → %s: alokasi %s sudah dilepas sebelumnya (dilewati)",
                           line["id"], a.get("txn_id"), amt)
    res = await db.bank_statement_lines.update_one({"id": line["id"], "match_lock": op}, {
        "$set": {"status": "unmatched", "match_kind": "", "matched_txn_id": "", "matched_txn_ids": [],
                 "allocations": [], "match_type": "", "matched_at": "", "matched_by": "",
                 "score": 0, "score_explain": [], "updated_at": now},
        "$unset": {"match_lock": "", "match_lock_at": ""}})
    if res.modified_count != 1:
        logger.warning("[PK-21 _unlink] kunci %s atas %s sudah diambil alih proses lain", op, line["id"])
    await sinkron_verifikasi_kwitansi([a.get("txn_id") for a in (claimed.get("allocations") or [])], actor, now)


async def sinkron_verifikasi_kwitansi(txn_ids: List[str], actor: str, now: str = "") -> None:
    """PM-T3 — status "terverifikasi bank" kwitansi mengikuti kasnya: kas kwitansi cocok PENUH dengan mutasi
    (`txn_reconciled`) → `bank_verified: true` + waktu, pelaku, id mutasi (sekali — syarat `bank_verified != true`);
    tidak penuh lagi (dilepas) → `false`. Dipanggil sesudah `_link`/`_unlink` menulis angka kas."""
    ids = [t for t in dict.fromkeys(txn_ids or []) if t]
    if not ids:
        return
    now = now or now_iso()
    kwitansi: List[str] = []
    async for t in db.cash_transactions.find({"id": {"$in": ids}, "ref_type": "ar_receipt"},
                                             {"_id": 0, "id": 1, "ref_id": 1, "amount": 1, "status": 1,
                                              "reconciled_amount": 1, "matched_line_ids": 1}):
        kwitansi.append(t.get("ref_id"))
        lines = list(t.get("matched_line_ids") or [])
        if t.get("status") != "void" and txn_reconciled(t):
            await db.ar_receipts.update_one(
                {"id": t.get("ref_id"), "bank_verified": {"$ne": True}},
                {"$set": {"bank_verified": True, "bank_verified_at": now, "bank_verified_by": actor or "system",
                          "bank_line_ids": lines, "updated_at": now}})
        else:
            await db.ar_receipts.update_one(
                {"id": t.get("ref_id"), "bank_verified": True},
                {"$set": {"bank_verified": False, "bank_verified_at": "", "bank_verified_by": "",
                          "bank_line_ids": lines, "updated_at": now}})
    try:   # CR-T2 — saldo pelanggan (giro belum cair = kwitansi giro belum terverifikasi); belum ada di HEAD
        from services import customer_balance_service as _cbs   # type: ignore[attr-defined]
    except ImportError:
        return
    refresh = getattr(_cbs, "refresh", None)
    if refresh and kwitansi:
        for rc in await db.ar_receipts.find({"id": {"$in": kwitansi}}, {"_id": 0, "customer_id": 1}) \
                .to_list(len(kwitansi) + 1):
            try:
                await refresh(rc.get("customer_id"))
            except Exception as exc:  # noqa: BLE001 — saldo turunan; dibangun ulang pembangunnya
                logger.warning("[PM-T3] refresh saldo pelanggan %s gagal: %s", rc.get("customer_id"), exc)


async def rebuild_reconciled(txn_id: str) -> Dict[str, Any]:
    """PK-21 (`02` D2) — pembangun ulang `reconciled_amount`, `reconciled`, `matched_line_ids` satu transaksi kas dari
    baris mutasi: Σ alokasi baris `matched` yang menunjuknya + `amount` bila ia kas titipan baris `holding`. Menulis
    hanya bila berbeda. Dipanggil skrip perbaikan dan uji — bukan alur layar."""
    t = await db.cash_transactions.find_one({"id": txn_id}, {"_id": 0})
    if not t:
        raise ValueError("Transaksi kas tidak ditemukan")
    total, ids = 0.0, []
    async for ln in db.bank_statement_lines.find({"status": "matched", "allocations.txn_id": txn_id},
                                                 {"_id": 0, "id": 1, "allocations": 1}):
        total += sum(_round(a.get("amount")) for a in (ln.get("allocations") or []) if a.get("txn_id") == txn_id)
        ids.append(ln["id"])
    async for ln in db.bank_statement_lines.find({"status": "holding", "holding.cash_txn_id": txn_id},
                                                 {"_id": 0, "id": 1}):
        total += _round(t.get("amount"))
        ids.append(ln["id"])
    after_rec = _round(total)
    after = {"reconciled_amount": after_rec,
             "reconciled": txn_reconciled({"amount": t.get("amount"), "reconciled_amount": after_rec}),
             "matched_line_ids": ids}
    before = {"reconciled_amount": t.get("reconciled_amount"), "reconciled": t.get("reconciled"),
              "matched_line_ids": list(t.get("matched_line_ids") or [])}
    changed = (abs(_round(before["reconciled_amount"]) - after_rec) > 0.005
               or bool(before["reconciled"]) != after["reconciled"]
               or sorted(before["matched_line_ids"]) != sorted(ids))
    if changed:
        now = now_iso()
        res = await db.cash_transactions.update_one(
            {"id": txn_id, "reconciled_amount": t.get("reconciled_amount")},
            {"$set": {**after,
                      "reconciled_at": (t.get("reconciled_at") or now) if after["reconciled"] else "",
                      "matched_line_id": ids[0] if len(ids) == 1 else "", "updated_at": now}})
        if res.modified_count != 1:
            raise ValueError("Transaksi kas berubah saat dihitung ulang — jalankan lagi.")
    return {"txn_id": txn_id, "before": before, "after": after, "changed": changed}


async def auto_match(bank_account_id: str, entity_ids: Optional[List[str]] = None,
                     window_days: Optional[int] = None, amount_tol: Optional[float] = None,
                     actor: str = "", active_entity: str = "") -> Dict[str, Any]:
    """Cocokkan otomatis 3 pita: ≥ambang otomatis → tertaut · pita usulan → disimpan
    sebagai `suggestions[]` (TIDAK ditautkan) · di bawahnya → murni manual."""
    acc = await _account(bank_account_id, entity_ids)
    cfg = await load_cfg(_stamp_entity(acc, active_entity))
    if window_days is not None:
        cfg["window_days"] = int(window_days)
    if amount_tol is not None:
        cfg["amount_tol"] = float(amount_tol)
    lines = await db.bank_statement_lines.find(
        {"bank_account_id": bank_account_id, "status": "unmatched", **_scope_q(entity_ids)},
        {"_id": 0}).to_list(20000)
    await _isi_hits(lines)   # PM-T3 — mutasi lama tanpa `pay_code_hits` dihitung di memori
    txns = await _candidate_txns(bank_account_id, entity_ids)
    rules = await _active_rules(bank_account_id, entity_ids)
    by_id = {t["id"]: t for t in txns}
    used: Dict[str, float] = {}
    matched, suggested = 0, 0

    for ln in sorted(lines, key=lambda x: (x.get("stmt_date") or "", -_round(x.get("amount")))):
        rule = _rule_for(ln, rules)
        scored = []
        for t in txns:
            avail = _round(_round(t.get("amount")) - _round(t.get("reconciled_amount")) - used.get(t["id"], 0.0))
            if avail <= EPS:
                continue
            s = score_pair(ln, t, cfg, rule)
            if s["eligible"]:
                scored.append((s["score"], s["explain"], t, bool(s.get("no_auto"))))
        scored.sort(key=lambda r: (-r[0], r[2].get("txn_date") or ""))
        if not scored:
            await db.bank_statement_lines.update_one({"id": ln["id"]}, {"$set": {
                "suggestions": [], "score": 0, "score_explain": [], "updated_at": now_iso()}})
            continue
        top_score, top_explain, top_txn, top_no_auto = scored[0]
        amt = _round(ln.get("amount"))
        top_avail = _round(_round(top_txn.get("amount"))
                           - _round(top_txn.get("reconciled_amount"))
                           - used.get(top_txn["id"], 0.0))
        # KN-G8-MATCH-PARTIAL (jalur OTOMATIS): dulu `min(nominal mutasi, sisa transaksi)`
        # sehingga baris bisa tertaut sendiri dengan Σ alokasi LEBIH KECIL dari nominalnya —
        # INV-BNK-01 memerah tanpa ada manusia yang menyentuh apa pun. Sekarang pita otomatis
        # hanya untuk pasangan yang menutup SELURUH nominal mutasi; yang tidak cukup turun
        # menjadi USULAN supaya manusia memilih jalur pecah (1:N) / gabung (N:1).
        # PM-T3 — pasangan kode bayar bernominal berbeda (`no_auto`) tidak pernah tertaut otomatis.
        if top_score >= cfg["auto_min"] and top_avail + EPS >= amt and not top_no_auto:
            await db.bank_statement_lines.update_one({"id": ln["id"]}, {"$set": {
                "score": top_score, "score_explain": top_explain, "suggestions": []}})
            fresh = await db.bank_statement_lines.find_one({"id": ln["id"]}, {"_id": 0})
            await _link(fresh, [{"txn_id": top_txn["id"], "amount": amt}], actor, "auto", "1:1")
            used[top_txn["id"]] = used.get(top_txn["id"], 0.0) + amt
            matched += 1
        elif top_score >= cfg["suggest_min"]:
            sug = [{**_txn_brief(t), "score": sc, "explain": ex} for sc, ex, t, _na in scored[:3]]
            await db.bank_statement_lines.update_one({"id": ln["id"]}, {"$set": {
                "suggestions": sug, "score": top_score, "score_explain": top_explain,
                "updated_at": now_iso()}})
            suggested += 1
        else:
            await db.bank_statement_lines.update_one({"id": ln["id"]}, {"$set": {
                "suggestions": [], "score": top_score, "score_explain": top_explain,
                "updated_at": now_iso()}})
    remaining_lines = await db.bank_statement_lines.count_documents(
        {"bank_account_id": bank_account_id, "status": "unmatched", **_scope_q(entity_ids)})
    remaining_txns = len(await _candidate_txns(bank_account_id, entity_ids))
    return {"matched": matched, "suggested": suggested, "unmatched_lines": remaining_lines,
            "unmatched_txns": remaining_txns, "auto_min": cfg["auto_min"],
            "suggest_min": cfg["suggest_min"], "window_days": cfg["window_days"],
            "amount_tolerance": cfg["amount_tol"], "rules_active": len(rules),
            "by_id_count": len(by_id)}


async def manual_match(line_id: str, txn_id: str, actor: str,
                       entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    ln = await _line(line_id, entity_ids)
    if ln.get("status") == "matched":
        raise ValueError("Baris sudah tertaut. Lepaskan (unmatch) dulu.")
    if ln.get("status") == "holding":
        raise ValueError("Baris berstatus titipan. Batalkan titipan dulu.")
    t = await db.cash_transactions.find_one({"id": txn_id}, {"_id": 0})
    if not t:
        raise ValueError("Transaksi kas tidak ditemukan")
    if entity_ids is not None:
        ent = t.get("entity_id") or ""
        if ent and ent != GROUP_ENTITY and ent not in entity_ids:
            raise HTTPException(status_code=403, detail="Transaksi kas milik entitas lain")
    await _assert_target(ln, t, entity_ids)  # CX-06
    avail = _round(_round(t.get("amount")) - _round(t.get("reconciled_amount")))
    if avail <= EPS:
        raise ValueError("Transaksi kas sudah terekonsiliasi penuh.")
    amt = _round(ln.get("amount"))
    # KN-G8-MATCH-PARTIAL (temuan penutupan fase): dulu `min(nominal mutasi, sisa transaksi)`
    # sehingga baris bisa berstatus "tercocok" padahal Σ alokasinya LEBIH KECIL dari nominal
    # mutasinya → INV-BNK-01 memerah dan sisa uangnya tidak terjelaskan di mana pun. Sekarang
    # ditolak dengan arahan jalur yang benar, bukan diam-diam dipotong.
    if amt > avail + EPS:
        raise ValueError(
            f"Sisa transaksi {t.get('number')} hanya {rupiah(avail)} — lebih kecil dari nominal "
            f"mutasi {rupiah(amt)}. Pakai 'Pecah ke beberapa transaksi' agar SELURUH nominal "
            f"mutasi terjelaskan, atau titipkan dana ini bila sisanya belum diketahui.")
    await _link(ln, [{"txn_id": txn_id, "amount": amt}], actor, "manual", "1:1")
    learned = await learn_from_manual(ln, [t], actor, entity_ids)
    out = await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0})
    return {**safe_doc(out), "rule_learned": learned}


async def match_split(line_id: str, allocations: List[Dict[str, Any]], actor: str,
                      entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """1 transfer → BEBERAPA transaksi buku (1:N). Σ alokasi ≤ nominal transfer."""
    ln = await _line(line_id, entity_ids)
    if ln.get("status") in ("matched", "holding"):
        raise ValueError("Baris sudah tertaut/dititipkan. Lepaskan dulu.")
    if len(allocations or []) < 2:
        raise ValueError("Split butuh minimal 2 transaksi buku")
    total = _round(sum(_round(a.get("amount")) for a in allocations))
    if total > _round(ln.get("amount")) + EPS:
        raise ValueError(f"Σ alokasi {rupiah(total)} melebihi nominal mutasi "
                         f"{rupiah(_round(ln.get('amount')))}")
    # KN-G8-MATCH-PARTIAL: baris "tercocok" WAJIB terjelaskan penuh (INV-BNK-01), jadi
    # pemecahan yang menyisakan rupiah menggantung ditolak dengan arahan yang jelas.
    if total < _round(ln.get("amount")) - EPS:
        sisa = _round(_round(ln.get("amount")) - total)
        raise ValueError(
            f"Σ alokasi {rupiah(total)} belum menutup seluruh nominal mutasi "
            f"{rupiah(_round(ln.get('amount')))} — sisa {rupiah(sisa)} tidak terjelaskan. "
            "Tambahkan transaksi buku lain, atau titipkan dana ini dulu.")
    # CX-07 — txn_id ganda digabung SEBELUM validasi kapasitas.
    _m: Dict[str, float] = {}
    for a in allocations:
        _m[a.get("txn_id") or ""] = _round(_m.get(a.get("txn_id") or "", 0.0) + _round(a.get("amount")))
    allocations = [{"txn_id": k, "amount": v} for k, v in _m.items()]
    clean, txns = [], []
    for a in allocations:
        tid, amt = a.get("txn_id"), _round(a.get("amount"))
        if not tid or amt <= 0:
            raise ValueError("Alokasi tidak sah (txn_id/amount kosong)")
        t = await db.cash_transactions.find_one({"id": tid}, {"_id": 0})
        if not t:
            raise ValueError(f"Transaksi kas {tid} tidak ditemukan")
        if entity_ids is not None:
            ent = t.get("entity_id") or ""
            if ent and ent != GROUP_ENTITY and ent not in entity_ids:
                raise HTTPException(status_code=403, detail="Transaksi kas milik entitas lain")
        await _assert_target(ln, t, entity_ids)  # CX-06
        avail = _round(_round(t.get("amount")) - _round(t.get("reconciled_amount")))
        if amt > avail + EPS:
            raise ValueError(f"Alokasi {rupiah(amt)} melebihi sisa transaksi "
                             f"{t.get('number')} ({rupiah(avail)})")
        clean.append({"txn_id": tid, "amount": amt})
        txns.append(t)
    await _link(ln, clean, actor, "manual", "1:N")
    learned = await learn_from_manual(ln, txns, actor, entity_ids)
    out = await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0})
    return {**safe_doc(out), "rule_learned": learned, "allocated_total": total}


async def match_group(line_ids: List[str], txn_id: str, actor: str,
                      entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """BEBERAPA transfer → 1 transaksi buku (N:1). Σ mutasi ≤ nominal transaksi."""
    if len(line_ids or []) < 2:
        raise ValueError("Gabung butuh minimal 2 baris mutasi")
    t = await db.cash_transactions.find_one({"id": txn_id}, {"_id": 0})
    if not t:
        raise ValueError("Transaksi kas tidak ditemukan")
    if entity_ids is not None:
        ent = t.get("entity_id") or ""
        if ent and ent != GROUP_ENTITY and ent not in entity_ids:
            raise HTTPException(status_code=403, detail="Transaksi kas milik entitas lain")
    lines = []
    for lid in line_ids:
        ln = await _line(lid, entity_ids)
        if ln.get("status") in ("matched", "holding"):
            raise ValueError(f"Baris {ln.get('stmt_date')} sudah tertaut/dititipkan")
        await _assert_target(ln, t, entity_ids)  # CX-06
        lines.append(ln)
    total = _round(sum(_round(l.get("amount")) for l in lines))
    avail = _round(_round(t.get("amount")) - _round(t.get("reconciled_amount")))
    if total > avail + EPS:
        raise ValueError(f"Σ mutasi {rupiah(total)} melebihi sisa transaksi "
                         f"{t.get('number')} ({rupiah(avail)})")
    for ln in lines:
        await _link(ln, [{"txn_id": txn_id, "amount": _round(ln.get("amount"))}],
                    actor, "manual", "N:1")
    return {"txn_id": txn_id, "txn_number": t.get("number", ""), "lines": len(lines),
            "allocated_total": total, "match_kind": "N:1"}


async def unmatch(line_id: str, actor: str, entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    ln = await _line(line_id, entity_ids)
    # KN-G8-UNMATCH-NOGUARD (temuan penutupan fase): tanpa penjaga status, `unmatch` pada
    # baris TITIPAN membuat statusnya 'unmatched' sementara kas + jurnal titipannya tetap
    # hidup → INV-BNK-03 memerah (uang tak dikenal hilang dari laporan). Layar hanya
    # menampilkan tombol "Lepas" untuk baris tercocok, tapi API tidak boleh percaya layar.
    # PK-21 (SL-10) — dari salinan hanya titipan/diabaikan yang ditolak (400, arahan jalur lain). Status `matched`
    # TIDAK dipercaya dari salinan: `_unlink` mengklaim baris; kalah klaim / bukan `matched` lagi → 409.
    if ln.get("status") in ("holding", "ignored"):
        raise ValueError(
            "Hanya baris berstatus TERCOCOK yang bisa dilepas. "
            "Baris titipan dilepas lewat 'Batalkan titipan'; baris diabaikan lewat "
            "'Batal abaikan'.")
    await _unlink(ln, new_id("bunmatch"), actor)
    return safe_doc(await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0}))


async def ignore_line(line_id: str, actor: str, entity_ids: Optional[List[str]] = None,
                      note: str = "") -> Dict[str, Any]:
    ln = await _line(line_id, entity_ids)
    if ln.get("status") == "matched":
        raise ValueError("Baris sudah tertaut. Lepaskan (unmatch) dulu.")
    if ln.get("status") == "holding":
        raise ValueError("Baris berstatus titipan. Batalkan titipan dulu.")
    await db.bank_statement_lines.update_one({"id": line_id}, {"$set": {
        "status": "ignored", "ignore_note": note, "ignored_by": actor,
        "suggestions": [], "updated_at": now_iso()}})
    return safe_doc(await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0}))


async def unignore_line(line_id: str, actor: str,
                        entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    ln = await _line(line_id, entity_ids)
    if ln.get("status") != "ignored":
        raise ValueError("Baris ini tidak berstatus diabaikan")
    await db.bank_statement_lines.update_one({"id": line_id}, {"$set": {
        "status": "unmatched", "ignore_note": "", "updated_at": now_iso()}})
    return safe_doc(await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0}))


# ═════════════════════════════════════════════════════════════════════════════
#  BIAYA & BUNGA BANK — baris rekening koran yang MEMANG tidak ada di buku
# ═════════════════════════════════════════════════════════════════════════════
# kind → (arah wajib, kategori kas, label manusia)
CHARGE_KINDS: Dict[str, Tuple[str, str, str]] = {
    "charge": ("out", "biaya administrasi bank", "Biaya bank"),
    "interest": ("in", "pendapatan bunga bank", "Bunga / jasa giro"),
}


async def book_charge(line_id: str, kind: str, note: str, actor: str,
                      entity_ids: Optional[List[str]] = None,
                      active_entity: str = "") -> Dict[str, Any]:
    """Bukukan baris rekening koran yang tidak punya pasangan di buku.

    Biaya administrasi/transfer dan bunga/jasa giro tidak pernah lahir sebagai transaksi
    kas lebih dulu — bank memotong/menambah sendiri. Sebelum ini satu-satunya pilihan di
    layar adalah **Abaikan**, sehingga bebannya hilang dari laba rugi dan "Selisih rekening
    vs buku" tidak pernah bisa nol (rekonsiliasi tidak pernah tuntas).

    Sekarang baris itu melahirkan transaksi kas + jurnal
    (`Dr Beban Adm Bank / Cr Bank` atau `Dr Bank / Cr Pendapatan Bunga`) lalu **tertaut ke
    barisnya sendiri**, jadi Σ alokasi == nominal mutasi (INV-BNK-01 tetap hijau) dan
    saldo buku ikut bergerak sebesar biaya itu.
    """
    kind = (kind or "").strip().lower()
    if kind not in CHARGE_KINDS:
        raise ValueError("Jenis pembukuan harus 'charge' (biaya bank) atau "
                         "'interest' (bunga/jasa giro)")
    want_dir, category, label = CHARGE_KINDS[kind]
    ln = await _line(line_id, entity_ids)
    if ln.get("status") == "matched":
        raise ValueError("Baris sudah tertaut. Lepaskan (unmatch) dulu.")
    if ln.get("status") == "holding":
        raise ValueError("Baris berstatus titipan. Batalkan titipan dulu.")
    cur_dir = _norm_dir(ln.get("direction"))
    if cur_dir != want_dir:
        raise ValueError(
            f"{label} hanya untuk dana {'KELUAR' if want_dir == 'out' else 'MASUK'} — "
            f"baris ini dana {'masuk' if cur_dir == 'in' else 'keluar'}")
    acc = await _account(ln["bank_account_id"], entity_ids)
    ent = ln.get("entity_id") or _stamp_entity(acc, active_entity)
    cfg = await load_cfg(ent)
    contra = cfg["charge_acc"] if kind == "charge" else cfg["interest_acc"]
    amount = _round(ln.get("amount"))
    if amount <= EPS:
        raise ValueError("Nominal mutasi nol — tidak ada yang bisa dibukukan")

    from services import gl_service as gl
    # Akun bisa berasal dari Pusat Pengaturan; pastikan bagan akun baku ada supaya jurnal
    # tidak jatuh ke Suspense pada database baru.
    await gl.seed_default_coa()
    # PK-37 (K-03) — PERIKSA periode tanggal mutasi (sakelar per PT, pesan dokumen); pemeriksa PK-15 di bawah tetap.
    from services.book_date import periksa_periode_dokumen
    await periksa_periode_dokumen(ent, ln.get("stmt_date") or None, jenis="transaksi bank")
    # PK-15 (SL-04) — periode tertutup ditolak SEBELUM kas tercatat (ClosedPeriodError → 409 di router).
    await gl.preflight_posting(ent, ln.get("stmt_date") or "")
    from services import atomic_claim as _saga
    lk = await _saga.claim("bank_statement_lines", line_id, "book_charge", actor=actor,
                           precondition={"status": {"$nin": ["matched", "holding"]}})
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    # Kas untuk rujukan ini yang sudah ada (jurnal gagal sebelumnya) DIPAKAI ULANG — mengulang tidak melahirkan kas kedua.
    # PK-20 — lewat pembuat kas satu pintu: rujukan (baris mutasi, arah, `seq="charge"`) memberi id tetap; kas lama
    # (sebelum PK-20, id acak) untuk rujukan + kategori yang sama dipakai lewat `txn_id`.
    prior = await db.cash_transactions.find_one(
        {"ref_type": "bank_statement_line", "ref_id": ln["id"], "category": category, "status": {"$ne": "void"}},
        {"_id": 0, "id": 1})
    from services import cash_ledger
    try:
        try:
            cdoc = await cash_ledger.create_cash(
                entity_id=ent, direction=want_dir, amount=amount, ref_type="bank_statement_line", ref_id=ln["id"],
                seq="charge", txn_id=(prior or {}).get("id", ""), account_id=ln["bank_account_id"],
                txn_date=ln.get("stmt_date") or "", category=category, contra_account_code=contra, actor=actor,
                description=(f"{label} — {(ln.get('description') or '')[:80]}" + (f" · {note}" if note else "")),
                extra={"reconciled_amount": 0.0})
        except cash_ledger.CashPostingError as exc:   # gl_status ditulis; panel Posting Gagal "Transaksi Kas"
            raise HoldingConflict(f"Kas {exc.txn.get('number', '')} sudah tercatat, tetapi jurnalnya gagal: {exc.error}. "
                                  "Perbaiki sebabnya lalu catat lagi dari baris ini.") from exc
        number = cdoc.get("number", "")
        je = await db.journal_entries.find_one(
            {"source_type": "cash_transaction", "source_id": cdoc["id"], "status": {"$ne": "void"}},
            {"_id": 0, "id": 1, "number": 1})
        await db.bank_statement_lines.update_one({"id": line_id}, {"$set": {
            "charge": {"kind": kind, "label": label, "cash_txn_id": cdoc["id"],
                       "cash_number": number, "je_id": (je or {}).get("id", ""),
                       "je_number": (je or {}).get("number", ""), "account_code": contra,
                       "at": now_iso(), "by": actor, "note": note},
            "suggestions": [], "updated_at": now_iso()}})
        ln = await _line(line_id, entity_ids)
        await _link(ln, [{"txn_id": cdoc["id"], "amount": amount}], actor, "charge", "1:1")
    except Exception:
        await _saga.release("bank_statement_lines", line_id, token)   # PK-15 — bisa diulang tanpa admin
        raise
    await db.bank_statement_lines.update_one({"id": line_id}, _saga.finish_set({"updated_at": now_iso()}))
    out = safe_doc(await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0}))
    return {**out, "kind": kind, "label": label, "cash_number": number,
            "je_number": (je or {}).get("number", ""), "account_code": contra}


async def _reverse_charge(line: Dict[str, Any], actor: str) -> None:
    """Lepas baris biaya/bunga bank: kasnya di-void & jurnalnya DIBALIK (append-only).

    Jurnal asal TIDAK dihapus — dibalik dengan reversing entry (aturan repo: ledger
    append-only), memakai `gl.reverse_document` yang idempoten.
    """
    ch = line.get("charge") or {}
    if not ch.get("cash_txn_id"):
        return
    from services import gl_service as gl
    await db.cash_transactions.update_one({"id": ch["cash_txn_id"]}, {"$set": {
        "status": "void", "void_reason": "pembukuan biaya/bunga bank dilepas",
        "updated_at": now_iso()}})
    # PK-20 — pembalik lewat pintu tahan-gagal: hasilnya ditulis ke `void_gl_status` kas (gagal tetap dilempar).
    cid = ch["cash_txn_id"]
    await gl.post_durable("cash_transactions", cid,
                          lambda: gl.reverse_document("cash_transaction", cid,
                                                      reason="pembukuan biaya/bunga bank dilepas", actor_name=actor),
                          source_type="cash_transaction_reversal", source_id=cid, field="void_gl_status",
                          raise_on_fail=True)
    await db.bank_statement_lines.update_one({"id": line["id"]}, {"$set": {
        "charge": {}, "updated_at": now_iso()}})


# ═════════════════════════════════════════════════════════════════════════════
#  ATURAN YANG DIPELAJARI (ditawarkan, TIDAK dipaksakan)
# ═════════════════════════════════════════════════════════════════════════════
async def learn_from_manual(line: Dict[str, Any], txns: List[Dict[str, Any]], actor: str,
                            entity_ids: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Hitung pola pencocokan manual. Setelah N kali pola sama → TAWARKAN aturan.

    Sistem tidak pernah membuat aturan aktif sendiri: statusnya `suggested` sampai
    manusia menyetujui (`decide_rule`). Ini menjaga prinsip "tidak ada perubahan senyap".
    """
    key = line.get("desc_key") or parser.desc_key(line.get("description", ""))
    if not key:
        return None
    cfg = await load_cfg(line.get("entity_id", ""))
    direction = _norm_dir(line.get("direction"))
    bank_account_id = line["bank_account_id"]
    counterparty = line.get("counterparty") or parser.counterparty_of(line.get("description", ""))
    hits = await db.bank_statement_lines.count_documents({
        "bank_account_id": bank_account_id, "desc_key": key, "direction": direction,
        "match_type": "manual", "status": "matched", **_scope_q(entity_ids)})
    existing = await db.bank_match_rules.find_one(
        {"bank_account_id": bank_account_id, "desc_key": key, "direction": direction},
        {"_id": 0})
    now = now_iso()
    if existing:
        await db.bank_match_rules.update_one({"id": existing["id"]}, {"$set": {
            "hits": hits, "sample_desc": line.get("description", ""),
            "counterparty": counterparty, "updated_at": now}})
        return None if existing.get("status") != "suggested" else safe_doc(
            await db.bank_match_rules.find_one({"id": existing["id"]}, {"_id": 0}))
    if hits < cfg["learn_after"]:
        return None
    rule = {
        "id": new_id("bmr"), "entity_id": line.get("entity_id", ""),
        "bank_account_id": bank_account_id, "desc_key": key, "direction": direction,
        "counterparty": counterparty, "sample_desc": line.get("description", ""),
        "customer_id": (txns[0].get("customer_id", "") if txns else ""),
        "category": (txns[0].get("category", "") if txns else ""),
        "hits": hits, "status": "suggested",
        "learned_from": [line["id"]], "created_by": actor, "created_at": now,
        "decided_by": "", "decided_at": "", "updated_at": now,
    }
    await db.bank_match_rules.insert_one(rule)
    try:
        from services.notification_service import create_notification
        await create_notification(
            notif_type="bank_rule_suggested", severity="info",
            title="Aturan pencocokan bank ditawarkan",
            body=(f"Pola '{counterparty or key}' sudah dicocokkan manual {hits}×. "
                  f"Setujui aturannya agar mutasi berikutnya cocok otomatis."),
            link="/finance/bank-reconciliation", entity_id=line.get("entity_id", ""),
            recipient_role="manager", ref=rule["id"])
    except Exception as exc:  # noqa: BLE001 — notifikasi bukan syarat sahnya aturan
        logger.warning("[learn_from_manual] efek samping gagal diabaikan: %s", exc)  # KN-C10
    return safe_doc(rule)


async def list_rules(entity_ids: Optional[List[str]] = None, bank_account_id: str = "",
                     status: str = "") -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {**_scope_q(entity_ids)}
    if bank_account_id:
        q["bank_account_id"] = bank_account_id
    if status:
        q["status"] = status
    rows = await db.bank_match_rules.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [safe_doc(r) for r in rows]


async def decide_rule(rule_id: str, action: str, actor: str,
                      entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    r = await db.bank_match_rules.find_one({"id": rule_id}, {"_id": 0})
    if not r:
        raise ValueError("Aturan tidak ditemukan")
    if entity_ids is not None:
        ent = r.get("entity_id") or ""
        if ent and ent != GROUP_ENTITY and ent not in entity_ids:
            raise HTTPException(status_code=403, detail="Aturan milik entitas lain")
    mapping = {"activate": "active", "reject": "rejected", "suspend": "suggested"}
    if action not in mapping:
        raise ValueError("Aksi aturan tidak dikenal (activate|reject|suspend)")
    await db.bank_match_rules.update_one({"id": rule_id}, {"$set": {
        "status": mapping[action], "decided_by": actor, "decided_at": now_iso(),
        "updated_at": now_iso()}})
    return safe_doc(await db.bank_match_rules.find_one({"id": rule_id}, {"_id": 0}))


# ═════════════════════════════════════════════════════════════════════════════
#  TITIPAN DANA BELUM TERIDENTIFIKASI (jembatan ke FASE G-9)
# ═════════════════════════════════════════════════════════════════════════════
async def to_holding(line_id: str, note: str, actor: str,
                     entity_ids: Optional[List[str]] = None,
                     active_entity: str = "") -> Dict[str, Any]:
    """Dana masuk tak dikenal → buku kas + jurnal `Dr Bank / Cr Titipan`.

    Uang yang nyata masuk ke rekening TIDAK boleh menggantung tanpa catatan: ia diakui
    sebagai KEWAJIBAN (titipan) sampai pemiliknya ketemu.
    """
    ln = await _line(line_id, entity_ids)
    if _norm_dir(ln.get("direction")) != "in":
        raise ValueError("Hanya dana MASUK yang bisa dititipkan")
    if ln.get("status") == "matched":
        raise ValueError("Baris sudah tertaut. Lepaskan (unmatch) dulu.")
    if ln.get("status") == "holding":
        raise ValueError("Baris sudah berstatus titipan")
    acc = await _account(ln["bank_account_id"], entity_ids)
    ent = ln.get("entity_id") or _stamp_entity(acc, active_entity)
    amount = _round(ln.get("amount"))

    from services import gl_service as gl
    # PK-37 (K-03) — PERIKSA periode tanggal mutasi sebelum nomor & kas titipan lahir (ClosedPeriodError → 409).
    from services.book_date import periksa_periode_dokumen
    await periksa_periode_dokumen(ent, ln.get("stmt_date") or None, jenis="transaksi bank")
    # Pastikan akun titipan ADA sebelum menjurnal. Tanpa ini, jurnal pertama di DB baru
    # jatuh ke akun Suspense (terukur di POC G-8) sehingga saldo titipan tak terbaca.
    await gl.seed_default_coa()
    # Sesi 15 — klaim saga baris koran (belum matched/holding) sesudah validasi, sebelum kas/jurnal titipan.
    from services import atomic_claim as _saga
    lk = await _saga.claim("bank_statement_lines", line_id, "to_holding", actor=actor,
                           precondition={"status": {"$nin": ["matched", "holding"]}})
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    # PK-20 — kas titipan lewat pembuat kas satu pintu: rujukan (baris mutasi, masuk, `seq="holding"`) memberi id tetap,
    # rekening = rekening mutasi. Jurnal gagal → baris TIDAK ditautkan, kunci dilepas; ulang memakai kas yang sama.
    from services import cash_ledger
    try:
        cdoc = await cash_ledger.create_cash(
            entity_id=ent, direction="in", amount=amount, ref_type="bank_statement_line", ref_id=ln["id"],
            seq="holding", account_id=ln["bank_account_id"], txn_date=ln.get("stmt_date") or "",
            category="titipan dana belum teridentifikasi", actor=actor,
            description=(f"Titipan dana belum teridentifikasi — {ln.get('description', '')[:80]}"
                         + (f" · {note}" if note else "")),
            extra={"reconciled": True, "reconciled_amount": amount, "matched_line_id": ln["id"],
                   "matched_line_ids": [ln["id"]], "reconciled_at": now_iso()})
    except cash_ledger.CashPostingError as exc:
        await _saga.release("bank_statement_lines", line_id, token)
        raise HoldingConflict(f"Kas {exc.txn.get('number', '')} sudah tercatat, tetapi jurnalnya gagal: {exc.error}. "
                              "Perbaiki sebabnya lalu titipkan lagi dari baris ini.") from exc
    except Exception:
        await _saga.release("bank_statement_lines", line_id, token)
        raise
    number = cdoc.get("number", "")
    je = await db.journal_entries.find_one(
        {"source_type": "cash_transaction", "source_id": cdoc["id"], "status": {"$ne": "void"}},
        {"_id": 0, "id": 1, "number": 1})
    await db.bank_statement_lines.update_one({"id": line_id}, _saga.finish_set({
        "status": "holding", "suggestions": [],
        "holding": {"cash_txn_id": cdoc["id"], "cash_number": number,
                    "je_id": (je or {}).get("id", ""), "je_number": (je or {}).get("number", ""),
                    "at": now_iso(), "by": actor, "note": note},
        "holding_allocated": [], "holding_remaining": amount,
        "updated_at": now_iso()}))
    return safe_doc(await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0}))


async def allocate_holding(line_id: str, allocations: List[Dict[str, Any]], customer_id: str,
                           reason_code: str, note: str, actor: str,
                           entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Titipan teridentifikasi → lunasi pesanan pelanggan.

    Piutang pesanan berkurang (satu fungsi alokasi PK-19, jenis `titipan_bank`) dan jurnalnya
    `Dr Titipan / Cr Piutang` — **tanpa kas dobel**, karena kasnya sudah diakui saat
    dana dititipkan.
    """
    ln = await _line(line_id, entity_ids)
    if ln.get("status") != "holding":
        raise ValueError("Baris ini bukan titipan dana")
    if not reason_code:
        raise ValueError("Alasan (reason_code) wajib diisi — keputusan atas uang harus berlabel")
    remaining = _round(ln.get("holding_remaining", ln.get("amount")))
    # PK-15 — sisa TERSEDIA = sisa titipan − butir `pending` (niat yang efeknya belum jadi).
    pending = _round(sum(_round(it.get("amount")) for it in (ln.get("holding_allocated") or [])
                         if it.get("status") == "pending"))
    remaining = _round(remaining - pending)
    total = _round(sum(_round(a.get("amount")) for a in (allocations or [])))
    if total <= 0:
        raise ValueError("Alokasi kosong")
    if total > remaining + EPS:
        raise ValueError(f"Σ alokasi {rupiah(total)} melebihi sisa titipan {rupiah(remaining)}")

    from services import gl_service as gl
    # Validasi SELURUH alokasi SEBELUM klaim saga: penolakan yang belum menulis apa pun tidak boleh meninggalkan kunci
    # saga gagal (dulu 403/400 di sini membuat baris terkunci 409 sampai dilepas admin).
    # KN-G8-ALLOC-CROSSPT / PK-19 (FX-05, SL-08) — pesanan tujuan diperiksa SATU pemeriksa alokasi: milik pelanggan
    # yang dipilih (400), PT rekening titipan (403), status hidup (409), dan muat di sisa tagihannya (400). Dulu
    # fungsi alokasi lama mencari pesanan hanya dengan id, jadi titipan PT-A bisa melunasi piutang PT-B.
    orders: List[Dict[str, Any]] = []
    for a in allocations:
        order_id, amt = a.get("order_id"), _round(a.get("amount"))
        if not order_id or amt <= 0:
            raise ValueError("Alokasi tidak sah (order_id/amount kosong)")
    from services import ar_allocation_service as aas
    docs = await aas.validate_targets("titipan_bank",
                                      [{"order_id": a.get("order_id"), "amount": _round(a.get("amount"))}
                                       for a in allocations],
                                      customer_id=customer_id, entity_id=ln.get("entity_id") or "")
    by_id = {o["id"]: o for o in docs}
    for a in allocations:
        orders.append((a["order_id"], _round(a.get("amount")), by_id[a["order_id"]]))
    # PK-37 (K-03) — PERIKSA periode buku hari ini (jurnal alokasi bertanggal hari ini); pemeriksa PK-15 tetap.
    from services.book_date import periksa_periode_dokumen
    await periksa_periode_dokumen(ln.get("entity_id") or "", None, jenis="transaksi bank")
    # PK-15 (SL-03) — periode tertutup ditolak sebelum apa pun ditulis.
    await gl.preflight_posting(ln.get("entity_id") or "")
    from services import atomic_claim as _saga
    lk = await _saga.claim("bank_statement_lines", line_id, "allocate_holding", actor=actor,
                           precondition={"status": "holding"})
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    try:
        # Lanjutkan dulu butir yang tertinggal (pending/applied); bila ada, alokasi baru TIDAK diproses (409) supaya
        # permintaan yang dikirim ulang tidak teralokasi dua kali.
        left = [it for it in (lk.get("holding_allocated") or []) if it.get("status") in ("pending", "applied")]
        for it in left:
            await _alloc_steps(line_id, it, ln, actor)
        if left:
            raise HoldingConflict("Alokasi sebelumnya untuk titipan ini belum tuntas dan baru saja dilanjutkan. "
                                  "Muat ulang, periksa sisa titipan, lalu alokasikan lagi bila perlu.")
        for order_id, amt, order in orders:
            item = {"id": new_id("bha"), "order_id": order_id, "order_number": order.get("number", ""),
                    "amount": amt, "status": "pending", "gl_status": "", "gl_error": "",
                    "reason_code": reason_code, "note": note, "customer_id": customer_id,
                    "at": now_iso(), "by": actor, **card_field()}   # AG-T3 — dari kartu tindakan asisten
            cur = await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0, "holding_remaining": 1})
            # NIAT — butir `pending` dicatat dengan syarat sisa titipan belum berubah.
            res = await db.bank_statement_lines.update_one(
                {"id": line_id, "status": "holding", "holding_remaining": (cur or {}).get("holding_remaining")},
                {"$push": {"holding_allocated": item}, "$set": {"updated_at": now_iso()}})
            if not res.modified_count:
                raise HoldingConflict("Sisa titipan berubah saat diproses. Muat ulang lalu coba lagi.")
            await _alloc_steps(line_id, item, ln, actor)
    except Exception:
        # PK-15 — kunci DILEPAS (bukan mark_failed): butir yang jadi sudah tercatat dan sisanya bisa dilanjutkan.
        await _saga.release("bank_statement_lines", line_id, token)
        raise
    await db.bank_statement_lines.update_one({"id": line_id}, _saga.finish_set({
        "customer_id": customer_id, "updated_at": now_iso()}))
    out = safe_doc(await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0}))
    return {**out, "allocated_now": total, "holding_remaining": out.get("holding_remaining")}


class HoldingConflict(ValueError):
    """PK-15 — keadaan titipan berubah / ada alokasi tertinggal / jurnal alokasi gagal → 409 di router."""


async def _alloc_steps(line_id: str, item: Dict[str, Any], ln: Dict[str, Any], actor: str) -> None:
    """PK-15 — jalankan satu butir alokasi dari status terakhirnya (pending → applied → done).

    EFEK-1: pesanan dilunasi (sekali; pembayaran membawa `alloc_id`). EFEK-2: sisa titipan berkurang + butir
    `applied` dalam satu pembaruan bersyarat. JURNAL: Dr 2-1950 / Cr 1-1200 ber-`source_id` `<baris>:<id alokasi>`;
    gagal → butir tetap `applied` ber-`gl_status` `failed`."""
    from services import ar_allocation_service as aas
    from services import gl_service as gl
    iid, amt, order_id = item["id"], _round(item.get("amount")), item["order_id"]
    if item.get("status") == "pending":
        paid = await db.sales_orders.find_one({"id": order_id, "payments.alloc_id": iid}, {"_id": 0, "id": 1})
        res: Dict[str, Any] = {}
        if not paid:
            try:
                # PK-19 — satu fungsi alokasi; id baris dari (titipan_bank, baris mutasi, pesanan, id alokasi PK-15).
                cash_number = (ln.get("holding") or {}).get("cash_number", "")
                # Butir lama (sebelum PK-19) tanpa `customer_id`: sudah diperiksa saat dicatat — pakai pelanggan baris.
                cus = item.get("customer_id") or ln.get("customer_id") or (await db.sales_orders.find_one(
                    {"id": order_id}, {"_id": 0, "customer_id": 1}) or {}).get("customer_id", "")
                res = await aas.allocate(
                    kind="titipan_bank", order_id=order_id, amount=amt, source_id=ln["id"],
                    source_number=f"{cash_number or ln['id']} (titipan dana bank)",
                    customer_id=cus, entity_id=ln.get("entity_id") or "",
                    date=now_iso(), actor=actor, method="bank_holding", seq=iid, extra={"alloc_id": iid})
            except Exception:
                await db.bank_statement_lines.update_one(
                    {"id": line_id}, {"$pull": {"holding_allocated": {"id": iid, "status": "pending"}}})
                raise
        cur = await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0, "holding_remaining": 1})
        rem = _round((cur or {}).get("holding_remaining"))
        upd = await db.bank_statement_lines.update_one(
            {"id": line_id, "holding_remaining": (cur or {}).get("holding_remaining"),
             "holding_allocated": {"$elemMatch": {"id": iid, "status": "pending"}}},
            {"$set": {"holding_remaining": _round(rem - amt), "holding_allocated.$.status": "applied",
                      "holding_allocated.$.order_number": res.get("order_number") or item.get("order_number", ""),
                      "holding_allocated.$.outstanding_after": res.get("outstanding_after"),
                      "updated_at": now_iso()}})
        if not upd.modified_count:
            raise HoldingConflict("Sisa titipan berubah saat diproses. Muat ulang lalu coba lagi.")
    order = await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "number": 1, "entity_id": 1}) or {}
    label = order.get("number") or item.get("order_number") or order_id
    src = f"{ln['id']}:{iid}"
    try:
        je = await gl.post_bank_holding_allocation(
            source_id=src, entity_id=order.get("entity_id") or ln.get("entity_id", ""), amount=amt,
            label=label, date=now_iso(), created_by=actor)
        je = je or await db.journal_entries.find_one(
            {"source_type": "bank_holding_alloc", "source_id": src, "status": {"$ne": "void"}},
            {"_id": 0, "id": 1, "number": 1})
    except Exception as exc:  # noqa: BLE001
        await db.bank_statement_lines.update_one(
            {"id": line_id, "holding_allocated.id": iid},
            {"$set": {"holding_allocated.$.gl_status": "failed", "holding_allocated.$.gl_error": str(exc)[:300],
                      "updated_at": now_iso()}})
        raise HoldingConflict(f"Pesanan {label} sudah dilunasi dari titipan, tetapi jurnalnya gagal: {exc}. "
                              "Perbaiki sebabnya lalu tekan Alokasikan lagi untuk melanjutkan.") from exc
    await db.bank_statement_lines.update_one(
        {"id": line_id, "holding_allocated.id": iid},
        {"$set": {"holding_allocated.$.status": "done", "holding_allocated.$.gl_status": "posted",
                  "holding_allocated.$.gl_error": "", "holding_allocated.$.je_id": (je or {}).get("id", ""),
                  "holding_allocated.$.je_number": (je or {}).get("number", ""), "updated_at": now_iso()}})


async def cancel_holding(line_id: str, actor: str,
                         entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Batalkan titipan yang BELUM dialokasikan (kas + jurnalnya dibalik).

    Bila sudah ada alokasi, pembatalan ditolak: koreksinya harus lewat amandemen
    (aturan repo #7 — ledger append-only).
    """
    ln = await _line(line_id, entity_ids)
    if ln.get("status") != "holding":
        raise ValueError("Baris ini bukan titipan dana")
    if ln.get("holding_allocated"):
        raise ValueError("Titipan sudah dialokasikan — koreksi harus lewat amandemen")
    from services import gl_service as gl
    hold = ln.get("holding") or {}
    # Sesi 15 — klaim saga baris (status holding) sesudah validasi, sebelum kas di-void & jurnal dibalik.
    from services import atomic_claim as _saga
    await _saga.claim("bank_statement_lines", line_id, "cancel_holding", actor=actor, precondition={"status": "holding"})
    try:
        if hold.get("cash_txn_id"):
            await db.cash_transactions.update_one({"id": hold["cash_txn_id"]}, {"$set": {
                "status": "void", "void_reason": "titipan dibatalkan", "updated_at": now_iso()}})
            # KN-G8-CANCEL-JE: jurnal dibalik dengan reversing entry (append-only, idempoten). PK-20 — lewat pintu
            # tahan-gagal: hasilnya ditulis ke `void_gl_status` kas (gagal tetap dilempar → kunci gagal).
            cid = hold["cash_txn_id"]
            await gl.post_durable("cash_transactions", cid,
                                  lambda: gl.reverse_document("cash_transaction", cid,
                                                              reason="titipan dana dibatalkan", actor_name=actor),
                                  source_type="cash_transaction_reversal", source_id=cid, field="void_gl_status",
                                  raise_on_fail=True)
    except Exception as e:
        await _saga.mark_failed("bank_statement_lines", line_id, str(e))
        raise
    await db.bank_statement_lines.update_one({"id": line_id}, _saga.finish_set({
        "status": "unmatched", "holding": {}, "holding_allocated": [],
        "holding_remaining": 0.0, "updated_at": now_iso()}))
    return safe_doc(await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0}))


async def holding_refunded(line_id: str, amount: float, ref_label: str, actor: str,
                           label: str = "pengembalian dana",
                           entity_ids: Optional[List[str]] = None, ref_key: str = "") -> Dict[str, Any]:
    """FASE G-9 — titipan dana KELUAR dari akun titipan tanpa melunasi piutang.

    Dipakai Pusat Kasus Keuangan untuk dua playbook: **dana dikembalikan ke pengirim**
    dan **settlement antar entitas** (uang ternyata milik PT lain). Jurnalnya diposting
    oleh pemanggil (kas keluar `Dr 2-1950 / Cr Bank`, atau `Dr 2-1950 / Cr 2-1250`),
    fungsi ini hanya menurunkan sisa titipan supaya **INV-BNK-03** tetap sah:
    saldo 2-1950 di buku besar == Σ titipan yang belum dialokasikan.

    Ledger tambah-saja: riwayatnya dicatat di `holding_settled[]`, baris aslinya tidak
    pernah dihapus.

    PK-25 — pengurangan BERSYARAT: sisa titipan belum berubah sejak dibaca (dua pengurangan bersamaan tidak bisa
    membuat sisa negatif); `ref_key` (opsional, mis. id niat penyelesaian kasus) membuat panggilan ulang dengan kunci
    yang sama tidak mengurangi dua kali.
    """
    ln = await _line(line_id, entity_ids)
    if ref_key and any(s.get("key") == ref_key for s in (ln.get("holding_settled") or [])):
        return safe_doc(ln)
    if ln.get("status") != "holding":
        raise ValueError("Baris ini bukan titipan dana")
    amt = _round(amount)
    remaining = _round(ln.get("holding_remaining", ln.get("amount")))
    if amt <= 0:
        raise ValueError("Nominal harus lebih dari 0")
    if amt > remaining + EPS:
        raise ValueError(
            f"Nominal {rupiah(amt)} melebihi sisa titipan {rupiah(remaining)}")
    row: Dict[str, Any] = {"amount": amt, "kind": label, "ref": ref_label, "by": actor, "at": now_iso()}
    flt: Dict[str, Any] = {"id": line_id, "status": "holding"}
    if "holding_remaining" in ln:
        flt["holding_remaining"] = ln.get("holding_remaining")
    if ref_key:
        row["key"] = ref_key
        flt["holding_settled.key"] = {"$ne": ref_key}
    res = await db.bank_statement_lines.update_one(flt, {
        "$push": {"holding_settled": row},
        "$set": {"holding_remaining": _round(remaining - amt), "updated_at": now_iso()}})
    if not res.modified_count:
        cur = await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0}) or {}
        if ref_key and any(s.get("key") == ref_key for s in (cur.get("holding_settled") or [])):
            return safe_doc(cur)
        raise ValueError("Sisa titipan berubah saat diproses. Muat ulang lalu coba lagi.")
    return safe_doc(await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0}))


async def holding_summary(entity_ids: Optional[List[str]] = None,
                          bank_account_id: str = "") -> Dict[str, Any]:
    """Ringkasan titipan: saldo, umur, dan mana yang perlu ditindaklanjuti."""
    q: Dict[str, Any] = {"status": "holding", **_scope_q(entity_ids)}
    if bank_account_id:
        q["bank_account_id"] = bank_account_id
    rows = await db.bank_statement_lines.find(q, {"_id": 0}).sort("stmt_date", 1).to_list(5000)
    cfg = await load_cfg((entity_ids or [""])[0] if entity_ids else "")
    # Hari ini = tanggal buku WIB (stmt_date bertanggal WIB). Dulu tanggal UTC: pukul 00.00–07.00 WIB mutasi hari itu
    # berumur "-1" (dijepit 0) dan titipan yang genap N hari belum ditandai perlu tindakan.
    today = datetime.fromisoformat(tanggal_buku()).date()
    items, total, overdue = [], 0.0, 0
    for r in rows:
        rem = _round(r.get("holding_remaining", r.get("amount")))
        d = _d(r.get("stmt_date"))
        # Umur tidak boleh negatif: mutasi bisa bertanggal "besok" (beda zona waktu bank /
        # data demo), dan layar yang menulis "-1 hari" hanya membingungkan pengguna.
        age = max(0, (today - d.date()).days) if d else 0
        stale = age > cfg["holding_max_age_days"] and rem > EPS
        if stale:
            overdue += 1
        total += rem
        items.append({"id": r["id"], "stmt_date": r.get("stmt_date"), "amount": _round(r.get("amount")),
                      "remaining": rem, "age_days": age, "needs_action": stale,
                      "description": r.get("description", ""),
                      "counterparty": r.get("counterparty", ""),
                      "allocated": _round(r.get("amount")) - rem,
                      "bank_account_id": r.get("bank_account_id", ""),
                      "entity_id": r.get("entity_id", ""),
                      # PK-15 — alokasi yang pesanannya sudah dilunasi tetapi jurnalnya belum terbit.
                      "gl_failed": [{"order_number": it.get("order_number", ""), "amount": it.get("amount"),
                                     "gl_error": it.get("gl_error", "")}
                                    for it in (r.get("holding_allocated") or [])
                                    if it.get("status") == "applied" and it.get("gl_status") == "failed"]})
    return {"account_code": cfg["holding_acc"], "max_age_days": cfg["holding_max_age_days"],
            "count": len(items), "needs_action": overdue, "balance": _round(total),
            "items": items}


# ═════════════════════════════════════════════════════════════════════════════
#  BACA (list & ringkasan)
# ═════════════════════════════════════════════════════════════════════════════
async def list_lines(bank_account_id: str, entity_ids: Optional[List[str]] = None,
                     status: Optional[str] = None, start: Optional[str] = None,
                     end: Optional[str] = None) -> List[Dict[str, Any]]:
    # Otorisasi AKUN lebih dulu: memakai id akun PT lain harus DITOLAK terang-terangan
    # (403), bukan dibalas daftar kosong. Daftar kosong menyembunyikan pelanggaran &
    # membuat gate isolasi bisa "hijau palsu" (lihat POC G-8 bagian isolasi).
    await _account(bank_account_id, entity_ids)
    q: Dict[str, Any] = {"bank_account_id": bank_account_id, **_scope_q(entity_ids)}
    if status:
        q["status"] = status
    if start or end:
        rng: Dict[str, str] = {}
        if start:
            rng["$gte"] = start[:10]
        if end:
            rng["$lte"] = end[:10]
        q["stmt_date"] = rng
    lines = await db.bank_statement_lines.find(q, {"_id": 0}).sort("stmt_date", -1).to_list(20000)
    await _isi_hits(lines)   # PM-T3 — tiap mutasi memuat `pay_code_hits`
    await _lengkapi_hits(lines)
    tids = [a["txn_id"] for l in lines for a in (l.get("allocations") or [])]
    tmap: Dict[str, Dict[str, Any]] = {}
    if tids:
        for t in await db.cash_transactions.find({"id": {"$in": tids}}, {"_id": 0}).to_list(20000):
            tmap[t["id"]] = t
    for l in lines:
        allocs = l.get("allocations") or []
        l["matched_txns"] = [{**_txn_brief(tmap[a["txn_id"]]), "allocated": _round(a["amount"])}
                             for a in allocs if a.get("txn_id") in tmap]
        l["matched_txn"] = l["matched_txns"][0] if len(l["matched_txns"]) == 1 else None
        l["allocated_total"] = _round(sum(_round(a.get("amount")) for a in allocs))
    return [safe_doc(l) for l in lines]


def _dalam_periode(txn: Dict[str, Any], start: Optional[str], end: Optional[str]) -> bool:
    """Transaksi buku bertanggal (tanggal buku WIB) di dalam saringan periode ringkasan; tanpa saringan = selalu."""
    if not start and not end:
        return True
    raw = txn.get("txn_date") or txn.get("created_at") or ""
    try:
        from services.book_date import tanggal_buku
        tgl = tanggal_buku(raw) if raw else ""
    except ValueError:
        tgl = str(raw)[:10]
    return bool(tgl) and (not start or tgl >= start[:10]) and (not end or tgl <= end[:10])


async def summary(bank_account_id: str, entity_ids: Optional[List[str]] = None,
                  start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    acc = await _account(bank_account_id, entity_ids)
    lines = await list_lines(bank_account_id, entity_ids, start=start, end=end)
    counted = [l for l in lines if l["status"] != "ignored"]
    stmt_in = _round(sum(l["amount"] for l in counted if l["direction"] == "in"))
    stmt_out = _round(sum(l["amount"] for l in counted if l["direction"] == "out"))
    matched = sum(1 for l in lines if l["status"] == "matched")
    unmatched = sum(1 for l in lines if l["status"] == "unmatched")
    ignored = sum(1 for l in lines if l["status"] == "ignored")
    holding = [l for l in lines if l["status"] == "holding"]
    suggested = sum(1 for l in lines if l["status"] == "unmatched" and (l.get("suggestions") or []))
    # Pelatihan 18 Nov — sisi BUKU ikut periode yang dipilih (layar menulis "kartu ringkasan mengikuti periode yang
    # dipilih"); dulu hanya mutasi yang disaring, buku tetap seluruh riwayat → selisih periode tidak bermakna.
    unrec_txns = len([t for t in await _candidate_txns(bank_account_id, entity_ids) if _dalam_periode(t, start, end)])
    book_in = book_out = 0.0
    bq = await _book_query(acc, entity_ids)
    for t in await db.cash_transactions.find(bq, {"_id": 0}).to_list(20000):
        if not _dalam_periode(t, start, end):
            continue
        amt = _round(t.get("amount"))
        if t.get("direction") == "in":
            book_in += amt
        else:
            book_out += amt
    stmt_net, book_net = _round(stmt_in - stmt_out), _round(book_in - book_out)
    hold = await holding_summary(entity_ids, bank_account_id)
    # M38 — asal mutasi: berapa baris dari berkas/tempel pengguna, berapa data contoh / tanpa catatan unggahan.
    sources = {k: 0 for k in (*IMPORT_SOURCES, "tidak_tercatat")}
    for ln in lines:
        sources[ln.get("import_source") if ln.get("import_source") in IMPORT_SOURCES else "tidak_tercatat"] += 1
    last = max((ln for ln in lines if ln.get("import_source") in ("berkas", "tempel")),
               key=lambda ln: str(ln.get("created_at") or ""), default=None)
    # Baris lama tanpa catatan asal: pernahkah PENGGUNA mengimpor mutasi ke rekening ini? (jejak audit impor). Tidak
    # pernah → baris itu data contoh/lama, bukan unggahan pengguna.
    ever_user_import = bool(await db.audit_logs.find_one(
        {"entity_id": bank_account_id, "action": {"$in": ["bank_statement_imported", "bank_statement_imported_file"]}},
        {"_id": 1}))
    return {
        "bank_account_id": bank_account_id, "account_name": acc.get("name", ""),
        "entity_id": acc.get("entity_id", ""),
        "period": {"start": start or "", "end": end or ""},
        "statement": {"in": stmt_in, "out": stmt_out, "net": stmt_net, "lines": len(lines),
                      "sources": sources, "user_lines": sources["berkas"] + sources["tempel"],
                      "ever_user_import": ever_user_import,
                      "last_import": ({"source": last.get("import_source"), "by": last.get("imported_by", ""),
                                       "file": last.get("import_file", ""), "at": last.get("created_at", "")}
                                      if last else None)},
        "book": {"in": _round(book_in), "out": _round(book_out), "net": book_net},
        "matched": matched, "unmatched_lines": unmatched, "ignored": ignored,
        "suggested": suggested,
        "holding": {"count": len(holding), "balance": hold["balance"],
                    "needs_action": hold["needs_action"], "account_code": hold["account_code"]},
        "unmatched_book_txns": unrec_txns,
        # PM-T3 — kolam buku memuat kas lama tanpa rekening hanya bila rekening ini satu-satunya PT untuk jenisnya.
        "book_includes_unlinked": len(bq.get("$or") or []) > 1,
        "difference": _round(stmt_net - book_net),
        "fully_reconciled": unmatched == 0 and unrec_txns == 0 and len(lines) > 0,
        "generated_at": now_iso(),
    }

"""PK-06 — Jurnal KEMBAR (dua buku PT) yang utuh dan bisa diulang per sisi (docs/blueprint/02_STANDAR.md §1 P6).

Satu peristiwa antar-PT menerbitkan satu jurnal di tiap PT yang terlibat. Aturannya:
  * Kunci jurnal tiap sisi = `source_id = f"{base_id}:{side.key}"` (sama dengan kode lama → jurnal lama dikenali);
    PK-23: sisi boleh membawa kuncinya sendiri (`TwinSide.source_type` / `source_id`).
  * `preflight_twin` memeriksa SEMUA sisi yang belum berjurnal (akun & periode) tanpa menulis apa pun.
  * `post_twin` menerbitkan sisi yang belum ada, berurutan; gagal → sisi itu `failed` (+ `gl_error`), sisi sesudahnya
    TIDAK dicoba (buku kedua PT tetap sama-sama kosong) dan bertanda "Belum dicoba…". Tidak pernah melempar.
  * Memanggil `post_twin` lagi dengan rencana sama hanya menerbitkan sisi yang kurang.
Status sisi ditulis ke dokumen pemiliknya (`status_doc`) pada field `gl_status{suffix}`, `gl_error{suffix}`,
`gl_journal_id{suffix}`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

from core_utils import now_iso
from db import db


@dataclass(frozen=True)
class TwinSide:
    key: str                              # "seller" | "buyer" | "payer" | "payee"
    entity_id: str
    lines: List[Dict[str, Any]]           # account_code, debit, credit, description
    description: str
    source_label: str
    status_doc: Tuple[str, str]           # (koleksi, id dokumen) tempat status sisi ini ditulis
    status_suffix: str = ""               # "" → gl_status/gl_error/gl_journal_id; "_payer" → gl_status_payer …
    # PK-23 — kunci jurnal sisi ini bila BEDA dari pola peristiwa (mis. pindah aset: sisi penerima = jurnal perolehan
    # `fixed_asset_acquisition` · `{id aset baru}`, kunci lama yang sama dengan Ulang Posting perolehan). Kosong →
    # `source_type` pemanggil dan `f"{base_id}:{key}"`.
    source_type: str = ""
    source_id: str = ""


def _kunci(side: "TwinSide", source_type: str, base_id: str) -> Tuple[str, str]:
    return side.source_type or source_type, side.source_id or f"{base_id}:{side.key}"


class TwinJournalError(ValueError):
    """Pemeriksaan awal salah satu sisi gagal. `.side`, `.entity_id`, `.cause` ("period" | "account")."""

    def __init__(self, message: str, *, side: str, entity_id: str, cause: str):
        super().__init__(message)
        self.side = side
        self.entity_id = entity_id
        self.cause = cause


async def _entity_name(entity_id: str) -> str:
    e = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "short_name": 1, "legal_name": 1,
                                                                "name": 1}) or {}
    return e.get("short_name") or e.get("legal_name") or e.get("name") or entity_id


async def _existing(source_type: str, source_id: str) -> Dict[str, Any]:
    return await db.journal_entries.find_one(
        {"source_type": source_type, "source_id": source_id, "status": {"$ne": "void"}}, {"_id": 0, "id": 1}) or {}


async def _mark(side: TwinSide, status: str, journal_id: str = "", error: str = "") -> None:
    coll, doc_id = side.status_doc
    sfx = side.status_suffix
    await db[coll].update_one({"id": doc_id}, {"$set": {
        f"gl_status{sfx}": status, f"gl_error{sfx}": (error or "")[:300], f"gl_journal_id{sfx}": journal_id,
        "updated_at": now_iso()}})


async def preflight_twin(*, source_type: str, base_id: str, date: str, sides: Sequence[TwinSide]) -> None:
    """Periksa tiap sisi yang jurnalnya belum ada. Tidak menulis apa pun. Gagal → `TwinJournalError`."""
    from services import gl_service as gl
    for s in sides:
        st, sid = _kunci(s, source_type, base_id)
        if await _existing(st, sid):
            continue
        try:
            await gl.preflight_entry(lines=s.lines, entity_id=s.entity_id, date=date, source_type=st)
        except gl.ClosedPeriodError as exc:
            raise TwinJournalError(f"Jurnal di {await _entity_name(s.entity_id)} belum bisa diterbitkan: {exc}. "
                                   "Tidak ada yang berubah.", side=s.key, entity_id=s.entity_id,
                                   cause="period") from exc
        except gl.JournalValidationError as exc:
            raise TwinJournalError(f"Jurnal di {await _entity_name(s.entity_id)} belum bisa diterbitkan: {exc}. "
                                   "Tidak ada yang berubah.", side=s.key, entity_id=s.entity_id,
                                   cause="account") from exc


async def post_twin(*, source_type: str, base_id: str, date: str, sides: Sequence[TwinSide],
                    created_by: str = "system") -> Dict[str, Dict[str, str]]:
    """Terbitkan sisi yang belum berjurnal. → {key: {status, journal_id, error}}. Tidak melempar."""
    from services import gl_service as gl
    hasil: Dict[str, Dict[str, str]] = {}
    gagal_key = ""
    for s in sides:
        if gagal_key:
            err = f"Belum dicoba karena sisi {gagal_key} gagal."
            await _mark(s, "failed", error=err)
            hasil[s.key] = {"status": "failed", "journal_id": "", "error": err}
            continue
        st, sid = _kunci(s, source_type, base_id)
        ada = await _existing(st, sid)
        if ada:
            await _mark(s, "posted", journal_id=ada["id"])
            hasil[s.key] = {"status": "posted", "journal_id": ada["id"], "error": ""}
            continue
        try:
            je = await gl._insert_entry(lines=s.lines, description=s.description, date=date,
                                        source_type=st, source_id=sid,
                                        entity_id=s.entity_id, created_by=created_by or "system",
                                        source_label=s.source_label)
            await _mark(s, "posted", journal_id=je.get("id", ""))
            hasil[s.key] = {"status": "posted", "journal_id": je.get("id", ""), "error": ""}
        except Exception as exc:  # noqa: BLE001 — sisi gagal ditandai, bukan dilempar (§1 P4)
            err = str(exc)[:300]
            await _mark(s, "failed", error=err)
            hasil[s.key] = {"status": "failed", "journal_id": "", "error": err}
            gagal_key = s.key
    return hasil


async def warning_for(hasil: Dict[str, Dict[str, str]], sides: Sequence[TwinSide]) -> str:
    """Kalimat peringatan untuk jawaban API bila ada sisi gagal ("" bila semua terbit)."""
    gagal = [s for s in sides if (hasil.get(s.key) or {}).get("status") == "failed"]
    if not gagal:
        return ""
    nama = ", ".join([await _entity_name(s.entity_id) for s in gagal])
    return (f"Dokumen tersimpan, tetapi jurnal di {nama} belum terbit. Buka Keuangan › Posting Gagal untuk "
            "mengulang.")

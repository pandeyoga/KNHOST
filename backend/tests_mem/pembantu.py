"""Pembantu uji database tiruan (kontrak PK-02 — lihat README.md). Fungsi biasa, bukan fixture.

Semua fungsi memakai `db.db` aplikasi; dipanggil dari dalam tes yang fixture `aplikasi`-nya aktif.
"""
import re
import uuid
from typing import Any, Dict, List, Sequence, Tuple

from core_utils import now_iso
from db import db

AKTOR_UJI: Dict[str, Any] = {"id": "user_admin_01", "name": "Budi Santoso", "role": "admin"}

_RX_XFAIL = re.compile(r"^[A-Z]{2}-\d{2} — ")


def alasan_xfail_sah(reason: str) -> bool:
    """Tanda `xfail` wajib beralasan "<ID temuan> — <kalimat>" (mis. "GL-01 — dibalik dua kali")."""
    return bool(_RX_XFAIL.match(reason or ""))


async def tutup_periode(entity_id: str, period_key: str, *, period_type: str = "month",
                        lewat_layanan: bool = False) -> Dict[str, Any]:
    """Tutup periode untuk satu PT.

    Bawaan: sisip langsung catatan `period_closings` berstatus `closed` (batas dari `period_bounds`) — berlaku untuk
    bulan mana pun, termasuk bulan berjalan. `lewat_layanan=True`: jalankan alur `close_period` yang sebenarnya.
    """
    from services import closing_service as cs
    if lewat_layanan:
        return await cs.close_period(period_type, period_key, AKTOR_UJI, entity_id,
                                     suspense_override_reason="uji kerangka", can_override_suspense=True)
    start, end = await cs.period_bounds(period_type, period_key, entity_id)
    rec = {"id": f"pc_uji_{uuid.uuid4().hex[:10]}", "entity_id": entity_id, "period_type": period_type,
           "period_key": period_key, "period_label": period_key, "start_date": start, "end_date": end,
           "status": "closed", "closed_at": now_iso(), "closed_by": AKTOR_UJI["name"], "net_income": 0.0,
           "journal_entry_id": None, "note": "uji kerangka (disisip langsung)"}
    await db.period_closings.insert_one(dict(rec))
    return rec


async def buka_periode(closing_id: str) -> Dict[str, Any]:
    from services import closing_service as cs
    return await cs.reopen_period(closing_id, AKTOR_UJI)


async def nonaktifkan_akun(entity_id: str, kode: str) -> None:
    from services import gl_service as gl
    await gl.update_account(kode, {"is_active": False}, entity_id)


async def aktifkan_akun(entity_id: str, kode: str) -> None:
    from services import gl_service as gl
    await gl.update_account(kode, {"is_active": True}, entity_id)


async def pt_uji(kode: str) -> str:
    """PT uji `ent_uji_<kode kecil>`; aman dipanggil ulang. Bagan akun baku ikut dipastikan ada."""
    from services import gl_service as gl
    eid = f"ent_uji_{kode.lower()}"
    if not await db.business_entities.find_one({"id": eid}):
        await db.business_entities.insert_one({
            "id": eid, "code": kode.upper(), "doc_prefix": kode.upper(), "legal_name": f"PT Uji {kode.upper()}",
            "short_name": f"Uji {kode.upper()}", "name": f"PT Uji {kode.upper()}", "status": "active",
            "is_active": True, "is_pkp": True, "created_at": now_iso()})
    await gl.seed_default_coa()
    return eid


async def jurnal(entity_id: str, tanggal: str, baris: Sequence[Tuple[str, float, float]], ket: str,
                 source_id: str) -> Dict[str, Any]:
    from services import gl_service as gl
    return await gl._insert_entry(
        lines=[{"account_code": k, "debit": d, "credit": c} for k, d, c in baris],
        description=ket, date=tanggal, source_type="uji", source_id=source_id, entity_id=entity_id,
        created_by="uji")


async def saldo_akun(kode: str, entity_id: str, per: str = "") -> float:
    from services import gl_service as gl
    led = await gl.account_ledger(kode, per or None, {"entity_id": entity_id})
    return float((led or {}).get("balance", 0.0) or 0.0)


async def jurnal_dari(source_type: str, awalan_source_id: str) -> List[Dict[str, Any]]:
    return await db.journal_entries.find(
        {"source_type": source_type, "status": {"$ne": "void"},
         "source_id": {"$regex": "^" + re.escape(awalan_source_id)}}, {"_id": 0}).to_list(1000)


async def jumlah(koleksi: str, saring: Dict[str, Any]) -> int:
    return await db[koleksi].count_documents(saring)

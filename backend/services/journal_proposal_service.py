"""KF-T6 (GL-06) — usulan jurnal manual yang menunggu orang kedua (`journal_proposals`).

Bila `kontrol.jurnal_manual.min_orang` PT itu = 2 (atau nilai jurnal di atas `kontrol.jurnal_manual.batas_nominal`),
`POST /api/gl/journal` tidak menulis `journal_entries`: isi jurnal divalidasi dan periodenya diperiksa dengan aturan
yang sama (`gl_service.create_manual_entry(hanya_periksa=True)`), lalu disimpan di sini sebagai usulan `pending`.
Orang lain yang berwenang menyetujuinya → jurnal diposting lewat jalur yang sama (`create_manual_entry`) dengan
`created_by` = pengusul dan `approved_by` = penyetuju; atau menolaknya dengan alasan.

Status: pending → posting (klaim, sementara) → posted | rejected. Tidak ada jalur sisip lain ke `journal_entries`.
"""
from typing import Any, Dict, Optional

from fastapi import HTTPException

from ai_card_context import card_field as _kartu
from core_utils import new_id, now_iso, safe_doc
from db import db
from schemas_finance import JournalEntryCreate
from services import dual_control
from services import gl_service

COLL = "journal_proposals"
SUDAH_DIPUTUSKAN = "Usulan jurnal ini sudah diputuskan."


# Indeks: `indexes.py` — `uq_id` (ID_INDEX_COLLECTIONS) dan (entity_id, status, proposed_at) (INDEX_SPECS).


async def ajukan(payload: JournalEntryCreate, actor: Dict[str, Any], entity_id: str,
                 can_backdate: bool) -> Dict[str, Any]:
    """Validasi + periksa periode (melempar `ValueError`/`ClosedPeriodError` seperti jurnal langsung), lalu simpan."""
    cek = await gl_service.create_manual_entry(payload, actor, entity_id=entity_id, can_backdate=can_backdate,
                                               hanya_periksa=True)
    body = payload.model_dump()
    body["entity_id"] = cek["entity_id"]
    doc = {
        "id": new_id("jprop"), "entity_id": cek["entity_id"], "payload": body,
        **_kartu(),   # AG-T5 — usulan jurnal dari kartu tindakan asisten
        "total_debit": cek["total_debit"], "status": "pending",
        "proposed_by_id": actor.get("id", ""), "proposed_by": actor.get("name", ""), "proposed_at": now_iso(),
        "decided_by_id": "", "decided_by": "", "decided_at": "", "reject_reason": "", "journal_id": "",
    }
    await db[COLL].insert_one(dict(doc))
    return safe_doc(doc)


async def ambil(pid: str) -> Optional[Dict[str, Any]]:
    doc = await db[COLL].find_one({"id": pid}, {"_id": 0})
    return safe_doc(doc) if doc else None


async def daftar(scope: Dict[str, Any], status: str = "", page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    q: Dict[str, Any] = dict(scope or {})
    if status:
        q["status"] = status
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 100))
    total = await db[COLL].count_documents(q)
    rows = await db[COLL].find(q, {"_id": 0}).sort("proposed_at", -1).skip((page - 1) * page_size) \
        .to_list(page_size)
    return {"items": [safe_doc(r) for r in rows], "total": total, "page": page, "page_size": page_size,
            "has_more": page * page_size < total}


async def setujui(pid: str, actor: Dict[str, Any], can_backdate: bool) -> Dict[str, Any]:
    prop = await ambil(pid)
    if not prop:
        raise HTTPException(status_code=404, detail="Usulan jurnal tidak ditemukan.")
    if prop["status"] != "pending":
        raise HTTPException(status_code=409, detail=SUDAH_DIPUTUSKAN)
    await dual_control.tolak_bila_pelaku_sama("jurnal_manual", prop, actor, prop["entity_id"],
                                              nominal=float(prop.get("total_debit") or 0),
                                              pengaju=[prop.get("proposed_by_id")])
    # Klaim: dua penyetuju bersamaan → satu yang memposting, lainnya 409.
    claimed = await db[COLL].find_one_and_update({"id": pid, "status": "pending"},
                                                 {"$set": {"status": "posting", "updated_at": now_iso()}})
    if not claimed:
        raise HTTPException(status_code=409, detail=SUDAH_DIPUTUSKAN)
    pengusul = {"id": prop.get("proposed_by_id", ""), "name": prop.get("proposed_by", "")}
    try:
        # Periode diperiksa ULANG di sini (bisa sudah ditutup sejak diajukan).
        je = await gl_service.create_manual_entry(
            JournalEntryCreate(**prop["payload"]), pengusul, entity_id=prop["entity_id"], can_backdate=can_backdate,
            disetujui={"id": actor.get("id", ""), "name": actor.get("name", ""), "proposal_id": pid})
    except Exception:
        await db[COLL].update_one({"id": pid, "status": "posting"}, {"$set": {"status": "pending"}})
        raise
    await db[COLL].update_one({"id": pid}, {"$set": {
        "status": "posted", "journal_id": je["id"], "journal_number": je.get("number", ""),
        "decided_by_id": actor.get("id", ""), "decided_by": actor.get("name", ""), "decided_at": now_iso(),
        "updated_at": now_iso()}})
    return {**(await ambil(pid) or {}), "journal": je}


async def tolak(pid: str, actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    prop = await ambil(pid)
    if not prop:
        raise HTTPException(status_code=404, detail="Usulan jurnal tidak ditemukan.")
    if not (reason or "").strip():
        raise HTTPException(status_code=400, detail="Alasan penolakan wajib diisi.")
    res = await db[COLL].update_one({"id": pid, "status": "pending"}, {"$set": {
        "status": "rejected", "reject_reason": reason.strip(), "decided_by_id": actor.get("id", ""),
        "decided_by": actor.get("name", ""), "decided_at": now_iso(), "updated_at": now_iso()}})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail=SUDAH_DIPUTUSKAN)
    return await ambil(pid) or {}

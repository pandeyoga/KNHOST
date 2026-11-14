"""KP-T4 — Aturan Persetujuan: satu tabel kebijakan untuk semua antrean (`approval_policies`).

  GET  /api/approval-policies/kinds                         katalog jenis dokumen
  GET  /api/approval-policies?entity_id=&doc_kind=          aturan yang berlaku per jenis (grup bila `all`)
  GET  /api/approval-policies/check?doc_kind=&entity_id=&amount=   coba nilai: jenjang + siapa yang lolos

Izin `settings.view` untuk baca (pesan Z6). PT lewat `resolve_requested_entity` (N1). Penilai semua pintu:
`services/approval_policy_service.py`.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from approval_kinds import APPROVAL_KINDS
from db import db
from dependencies import require_permission
from entity_scope import entity_ctx, resolve_requested_entity
from services import approval_policy_service as aps

router = APIRouter(prefix="/api/approval-policies", tags=["approval-policies"])

_MODUL = "'Pengaturan, Pengguna & Hak Akses'"
PESAN_LIHAT = f"Anda belum punya akses untuk melihat aturan persetujuan. Minta Admin menambahkan akses {_MODUL}."


def _kind_or_400(doc_kind: str) -> str:
    if doc_kind not in APPROVAL_KINDS:
        raise HTTPException(status_code=400, detail="Jenis dokumen tidak dikenal.")
    return doc_kind


async def _entity(request: Request, entity_id: Optional[str]) -> str:
    eid = (entity_id or "").strip()
    if not eid or eid == "all":
        return "all"
    return resolve_requested_entity(await entity_ctx(request), eid)


async def _entity_name(ent: str) -> str:
    if ent == "all":
        return "Semua PT (aturan grup)"
    doc = await db.business_entities.find_one(
        {"id": ent}, {"_id": 0, "legal_name": 1, "short_name": 1, "name": 1}) or {}
    return doc.get("legal_name") or doc.get("name") or doc.get("short_name") or "PT"


@router.get("/kinds")
async def list_kinds(request: Request) -> Dict[str, Any]:
    await require_permission(request, "settings", "view", PESAN_LIHAT)
    return {"kinds": await aps.kinds_catalog()}


@router.get("/check")
async def check(request: Request, doc_kind: str = Query(...), entity_id: Optional[str] = Query(None),
                amount: float = Query(0)) -> Dict[str, Any]:
    await require_permission(request, "settings", "view", PESAN_LIHAT)
    _kind_or_400(doc_kind)
    ent = await _entity(request, entity_id)
    return await aps.check_view(doc_kind, ent, amount)


@router.get("")
async def list_policies(request: Request, entity_id: Optional[str] = Query(None),
                        doc_kind: Optional[str] = Query(None)) -> Dict[str, Any]:
    await require_permission(request, "settings", "view", PESAN_LIHAT)
    ent = await _entity(request, entity_id)
    kinds = [_kind_or_400(doc_kind)] if doc_kind else list(APPROVAL_KINDS)
    return {"entity_id": ent, "entity_name": await _entity_name(ent),
            "kinds": [await aps.policy_view(k, ent) for k in kinds]}

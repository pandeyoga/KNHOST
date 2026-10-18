"""FASE G-5 — UNLOCK PERIODE BEROTORITAS (router).

Akses: permission module "period" (action "unlock"). GET bersifat lunak (login).
Respons OBJEK/ARRAY telanjang (kontrak KN3). Per-entitas (F0-E).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, Query, HTTPException
from pydantic import BaseModel

from db import db
from dependencies import require_permission, audit
from entity_scope import entity_ctx, resolve_scope_ids
from services import period_unlock_service as pus

router = APIRouter(prefix="/api")


class UnlockRequest(BaseModel):
    period_type: str            # "month" | "year"
    period_key: str             # "YYYY-MM" atau "YYYY"
    entity_id: Optional[str] = None
    reason: str


class RejectRequest(BaseModel):
    reason: Optional[str] = ""


async def _resolve_entity(request: Request, entity_id: Optional[str]) -> str:
    """Entitas KONKRET untuk operasi unlock (tolak mode 'all')."""
    ctx = await entity_ctx(request)
    target = entity_id or ctx.active_entity_id
    if not target or target == "all":
        raise HTTPException(status_code=400,
                            detail="Pilih entitas (PT) spesifik untuk membuka periode.")
    if target not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=403, detail="Tidak memiliki akses ke entitas ini.")
    return target


@router.get("/finance/period-unlocks")
async def list_unlocks(request: Request, entity_id: Optional[str] = Query(None),
                       status: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Riwayat & antrean usul buka periode (per entitas / status)."""
    ctx = await entity_ctx(request)
    return await pus.list_requests(resolve_scope_ids(ctx, entity_id), status)  # IX-10


@router.get("/finance/period-unlocks/active")
async def active_unlocks(request: Request,
                         entity_id: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Unlock yang SEDANG aktif (untuk banner merah global)."""
    ctx = await entity_ctx(request)
    return await pus.active_unlocks(resolve_scope_ids(ctx, entity_id))  # IX-10


async def _guard_unlock(request: Request, plu_id: str) -> None:
    """IX-10 — keputusan usul wajib oleh aktor yang ditugaskan ke entitas pemilik usul."""
    ctx = await entity_ctx(request)
    rec = await db.period_unlock_requests.find_one({"id": plu_id}, {"_id": 0, "entity_id": 1})
    if not rec or rec.get("entity_id") not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=404, detail="Usul buka periode tidak ditemukan")


@router.post("/finance/period-unlocks")
async def create_unlock(payload: UnlockRequest, request: Request) -> Dict[str, Any]:
    """Ajukan usul membuka periode tertutup (alasan WAJIB)."""
    actor = await require_permission(request, "period", "unlock")
    eid = await _resolve_entity(request, payload.entity_id)
    try:
        rec = await pus.request_unlock(period_type=payload.period_type,
                                       period_key=payload.period_key,
                                       entity_id=eid, reason=payload.reason, actor=actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "period_unlock_requested", "period_unlock", rec["id"],
                {"period": rec["period_key"], "entity_id": eid, "reason": rec["reason"]},
                reason=rec["reason"])
    return rec


@router.post("/finance/period-unlocks/{plu_id}/approve")
async def approve_unlock(plu_id: str, request: Request) -> Dict[str, Any]:
    """Setujui usul (DUAL CONTROL: pengusul ≠ penyetuju). Mulai jendela berbatas waktu."""
    actor = await require_permission(request, "period", "unlock")
    await _guard_unlock(request, plu_id)
    try:
        rec = await pus.approve_request(plu_id, actor)
    except pus.DecisionConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "period_unlock_approved", "period_unlock", plu_id,
                {"period": rec.get("period_key"), "window_until": rec.get("window_until")})
    return rec


@router.post("/finance/period-unlocks/{plu_id}/reject")
async def reject_unlock(plu_id: str, payload: RejectRequest, request: Request) -> Dict[str, Any]:
    """Tolak usul buka periode."""
    actor = await require_permission(request, "period", "unlock")
    await _guard_unlock(request, plu_id)
    try:
        rec = await pus.reject_request(plu_id, actor, payload.reason or "")
    except pus.DecisionConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "period_unlock_rejected", "period_unlock", plu_id,
                {"period": rec.get("period_key")}, reason=payload.reason or "")
    return rec


@router.post("/finance/period-unlocks/reclose-expired")
async def reclose_expired(request: Request) -> Dict[str, Any]:
    """Tutup manual semua jendela unlock yang sudah lewat batas (juga dijalankan job)."""
    actor = await require_permission(request, "period", "unlock")
    res = await pus.reclose_expired(notify=True)
    if res.get("reclosed"):
        await audit(actor["name"], "period_unlock_reclosed_batch", "period_unlock", "batch", res)
    return res

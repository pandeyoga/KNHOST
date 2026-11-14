"""Tanya KN — kartu tindakan (daftar, setujui, abaikan) & peringatan anomali.

AG-T3 — kartu golongan A/B (`services/ai_cards.py`) dan tiga jenis kartu lama (`services/ai_actions.py`) berbagi koleksi
`ai_action_proposals` dan endpoint yang sama; jenis kartu menentukan mesinnya.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

from entity_scope import entity_ctx
from routers.ai_analytics import _DENY_AI, _ai_user
from services import ai_actions, ai_cards, ai_insights
from dependencies import has_permission, require_permission

router = APIRouter(prefix="/api/ai")


@router.get("/actions")
async def list_actions(request: Request, box: str = "mine", page: int = 1,
                       page_size: int = ai_cards.PAGE_SIZE_DEFAULT) -> Dict[str, Any]:
    """AG-T3 — tab Tindakan: kartu MILIK pengguna per kotak (`mine` · `others` · `done` · `failed`), berhalaman."""
    user = await require_permission(request, "ai", "view", detail=_DENY_AI)   # = `_ai_user` (pagar auth terbaca)
    return await ai_cards.list_cards(user, box, page, page_size)


@router.get("/actions/{pid}")
async def get_action(pid: str, request: Request) -> Dict[str, Any]:
    return await ai_actions.load(pid, await _ai_user(request))


@router.post("/actions/{pid}/confirm")
async def confirm_action(pid: str, request: Request, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # AG-T1 — konteks PT ikut dikirim: PT kartu diadu ulang dengan akses & PT aktif pengguna saat menyetujui.
    user = await _ai_user(request)
    payload = payload or {}
    ctx = await entity_ctx(request)
    if await ai_cards.is_card(pid):   # AG-T3 — kartu golongan A/B: alasan, ketik ulang nominal, isian yang boleh diubah
        return await ai_cards.decide(pid, request=request, user=user, ctx=ctx, decision="approve",
                                     reason=str(payload.get("reason") or ""), retype=str(payload.get("retype") or ""),
                                     edits=payload.get("edits") if isinstance(payload.get("edits"), dict) else None)
    return await ai_actions.confirm(pid, user, payload.get("edits"), ctx)


@router.post("/actions/{pid}/dismiss")
async def dismiss_action(pid: str, request: Request, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    user = await _ai_user(request)
    if await ai_cards.is_card(pid):
        return await ai_cards.dismiss(pid, user=user, reason=str((payload or {}).get("reason") or ""))
    return await ai_actions.dismiss(pid, user)


@router.get("/insights")
async def get_insights(request: Request) -> List[Dict[str, Any]]:
    user = await _ai_user(request)
    ctx = await entity_ctx(request)
    ids = ctx.allowed_entity_ids if ctx.view_all else [ctx.active_entity_id]
    return await ai_insights.list_for(user, ids)


@router.post("/insights/scan")
async def scan_insights(request: Request) -> Dict[str, Any]:
    user = await _ai_user(request)
    if not await has_permission(user, "ai", "manage"):   # PR-T2 — dulu nama peran admin/manajer
        raise HTTPException(status_code=403, detail=(
            "Anda belum punya akses untuk memindai ulang peringatan. Minta Admin menambahkan akses 'Asisten Tanya KN'."))
    ctx = await entity_ctx(request)
    return await ai_insights.scan(None if ctx.view_all else ctx.active_entity_id)

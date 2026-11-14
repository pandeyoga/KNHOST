"""Tanya KN — draf tindakan (setujui/abaikan) & peringatan anomali."""
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

from entity_scope import entity_ctx
from routers.ai_analytics import _ai_user
from services import ai_actions, ai_insights
from dependencies import has_permission

router = APIRouter(prefix="/api/ai")


@router.get("/actions/{pid}")
async def get_action(pid: str, request: Request) -> Dict[str, Any]:
    return await ai_actions.load(pid, await _ai_user(request))


@router.post("/actions/{pid}/confirm")
async def confirm_action(pid: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    # AG-T1 — konteks PT ikut dikirim: PT kartu diadu ulang dengan akses & PT aktif pengguna saat menyetujui.
    user = await _ai_user(request)
    return await ai_actions.confirm(pid, user, payload.get("edits"), await entity_ctx(request))


@router.post("/actions/{pid}/dismiss")
async def dismiss_action(pid: str, request: Request) -> Dict[str, Any]:
    return await ai_actions.dismiss(pid, await _ai_user(request))


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

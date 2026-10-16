"""Tanya KN — draf tindakan (setujui/abaikan) & peringatan anomali."""
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

from entity_scope import entity_ctx
from routers.ai_analytics import _ai_user
from services import ai_actions, ai_insights

router = APIRouter(prefix="/api/ai")


@router.get("/actions/{pid}")
async def get_action(pid: str, request: Request) -> Dict[str, Any]:
    return await ai_actions.load(pid, await _ai_user(request))


@router.post("/actions/{pid}/confirm")
async def confirm_action(pid: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    return await ai_actions.confirm(pid, await _ai_user(request), payload.get("edits"))


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
    if user.get("role") not in ("admin", "manager"):
        raise HTTPException(status_code=403, detail="Hanya admin/manajer yang boleh memindai ulang")
    ctx = await entity_ctx(request)
    return await ai_insights.scan(None if ctx.view_all else ctx.active_entity_id)

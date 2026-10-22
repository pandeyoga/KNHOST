"""L06 LN-061 — Meja Cutting & Admin Cutting (kemampuan lokasi, antrean, serah-terima)."""
from typing import Any, Dict, List

from fastapi import APIRouter, Request
from pydantic import BaseModel

from dependencies import audit, require_permission
from entity_scope import entity_ctx, resolve_list_scope
from services import cutting_service as cs

router = APIRouter(prefix="/api/cutting", tags=["cutting"])


class CapsIn(BaseModel):
    caps: List[str]


class ReceiveIn(BaseModel):
    to_warehouse_id: str = ""


@router.get("/locations")
async def locations(request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "sample_order", "view")
    return await cs.list_locations()


@router.put("/locations/{wid}")
async def set_caps(wid: str, payload: CapsIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "sample_order", "cutting_config")
    out = await cs.set_location_caps(wid, payload.caps, actor.get("name", ""))
    await audit(actor["name"], "cutting_caps_set", "warehouse", wid, {"caps": out.get("cutting_caps")})
    return out


@router.get("/desk")
async def desk(request: Request, entity_id: str = None) -> Dict[str, Any]:
    await require_permission(request, "sample_order", "view")
    ctx = await entity_ctx(request)
    eid = entity_id if entity_id and entity_id != "all" else (None if ctx.view_all else ctx.active_entity_id)
    return await cs.desk(resolve_list_scope("wms_tasks", {}, ctx, entity_id), eid)


@router.post("/tasks/{task_id}/receive")
async def receive(task_id: str, payload: ReceiveIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "sample_order", "cutting_receive")
    ctx = await entity_ctx(request)
    out = await cs.receive(task_id, payload.to_warehouse_id, actor, list(ctx.allowed_entity_ids or []))
    await audit(actor["name"], "cutting_handoff", "wms_task", task_id, out.get("cutting_handoff") or {})
    return out


@router.post("/orders/{order_id}/receive")
async def receive_order(order_id: str, payload: ReceiveIn, request: Request) -> Dict[str, Any]:
    """Trial 22 Okt (A2) — terima SEMUA hasil potong satu pesanan sekaligus."""
    actor = await require_permission(request, "sample_order", "cutting_receive")
    ctx = await entity_ctx(request)
    out = await cs.receive_order(order_id, payload.to_warehouse_id, actor, list(ctx.allowed_entity_ids or []))
    await audit(actor["name"], "cutting_handoff_batch", "sales_order", order_id, {"received": out["received"]})
    return out

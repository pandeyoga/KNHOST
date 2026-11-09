"""L06 LN-061 — Meja Cutting & Admin Cutting (kemampuan lokasi, antrean, serah-terima)."""
from typing import Any, Dict, List

from fastapi import APIRouter, Request
from pydantic import BaseModel

from dependencies import audit, require_permission
from entity_scope import entity_ctx
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


async def _assert_cut_location(actor: Dict[str, Any], task_ids: List[str], to_warehouse_id: str) -> None:
    """FIX-1 (B2a STM-IN-02) — terima hasil potong: gedung tugas & gedung tujuan wajib di lokasi tugas petugas
    berpagar (dulu hanya PT yang dicek)."""
    from db import db
    from services import location_scope
    async for t in db.wms_tasks.find({"id": {"$in": list(task_ids)}}, {"_id": 0, "warehouse_id": 1}):
        await location_scope.assert_warehouse(actor, t.get("warehouse_id") or "", "menerima hasil potong di gudang ini")
    if (to_warehouse_id or "").strip():
        await location_scope.assert_warehouse(actor, to_warehouse_id.strip(), "menjadikan gudang ini tujuan hasil potong")


@router.get("/desk")
async def desk(request: Request, entity_id: str = None) -> Dict[str, Any]:
    await require_permission(request, "sample_order", "view")
    ctx = await entity_ctx(request)
    eid = entity_id if entity_id and entity_id != "all" else (None if ctx.view_all else ctx.active_entity_id)
    # FIX-1 (K-B1-02) — meja potong per GEDUNG dalam lokasi kerja, lintas PT yang ditugaskan (terima hasil potong
    # sudah memakai penugasan `allowed_entity_ids`). Dulu: PT aktif tanpa lokasi.
    from entity_scope import resolve_work_scope
    return await cs.desk(await resolve_work_scope("wms_tasks", {}, ctx, entity_id), eid)


@router.post("/tasks/{task_id}/receive")
async def receive(task_id: str, payload: ReceiveIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "sample_order", "cutting_receive")
    ctx = await entity_ctx(request)
    await _assert_cut_location(actor, [task_id], payload.to_warehouse_id)   # FIX-1 (STM-IN-02) — cakupan aksi tulis
    out = await cs.receive(task_id, payload.to_warehouse_id, actor, list(ctx.allowed_entity_ids or []))
    await audit(actor["name"], "cutting_handoff", "wms_task", task_id, out.get("cutting_handoff") or {})
    return out


@router.post("/orders/{order_id}/receive")
async def receive_order(order_id: str, payload: ReceiveIn, request: Request) -> Dict[str, Any]:
    """Trial 22 Okt (A2) — terima SEMUA hasil potong satu pesanan sekaligus."""
    actor = await require_permission(request, "sample_order", "cutting_receive")
    ctx = await entity_ctx(request)
    from db import db
    pending = [t["id"] async for t in db.wms_tasks.find(
        {"order_id": order_id, "task_subtype": "sample_cut", "status": {"$nin": ["cancelled"]}}, {"_id": 0, "id": 1})]
    await _assert_cut_location(actor, pending, payload.to_warehouse_id)    # FIX-1 (STM-IN-02)
    out = await cs.receive_order(order_id, payload.to_warehouse_id, actor, list(ctx.allowed_entity_ids or []))
    await audit(actor["name"], "cutting_handoff_batch", "sales_order", order_id, {"received": out["received"]})
    return out

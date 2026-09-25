"""M0 — Color Library router (master warna Pantone-style).

Koleksi `color_library` = SHARED (tak di-scope entitas), mirip products/uoms.
Endpoint auth wajib via require_permission resource "color".
Respons = ARRAY/OBJEK telanjang (kontrak KN, tanpa envelope).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import Response
from pydantic import BaseModel

from db import db
from dependencies import require_permission, audit
from entity_scope import entity_ctx, resolve_list_scope
from schemas import ColorCreate, ColorPatch
from services import color_service as svc
from services import color_lock_service as lock
from services.color_card_pdf import render_customer_color_card

router = APIRouter(prefix="/api")


@router.get("/color-library")
async def list_color_library(
    request: Request,
    q: str = Query(""),
    family: str = Query(""),
    system: str = Query(""),
    status: str = Query("active"),
    scope: str = Query("", description="internal | customer | kosong = semua"),
) -> List[Dict[str, Any]]:
    await require_permission(request, "color", "view")
    return await svc.list_colors(q=q, family=family, system=system, status=status, scope=scope)


@router.get("/color-library/customer-colors")
async def list_customer_colors(request: Request, customer_id: str = Query(""),
                               entity_id: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Tab "Warna Pelanggan": per pelanggan (yang terlihat di badan usaha aktif) — warna milik & warna produk eksklusif."""
    await require_permission(request, "color", "view")
    return await svc.list_customer_colors(await _visible_customers(request, entity_id), customer_id)


async def _visible_customers(request: Request, entity_id: Optional[str] = None) -> set:
    ctx = await entity_ctx(request)
    return {c["id"] async for c in db.customers.find(resolve_list_scope("customers", {}, ctx, entity_id), {"_id": 0, "id": 1})}


@router.get("/color-library/customer-colors/{customer_id}/card")
async def customer_color_card(customer_id: str, request: Request):
    """Kartu Warna Pelanggan (PDF): swatch, kode, versi supplier + kop badan usaha aktif."""
    await require_permission(request, "color", "view")
    if customer_id not in await _visible_customers(request):
        raise HTTPException(status_code=404, detail="Pelanggan tidak ditemukan di badan usaha aktif")
    ctx = await entity_ctx(request)
    eid = ctx.active_entity_id if ctx.active_entity_id and ctx.active_entity_id != "all" else ""
    pdf, filename = await render_customer_color_card(customer_id, eid)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


class UseRequestIn(BaseModel):
    target_customer_id: str = ""
    reason: str = ""
    context: str = ""


class DecisionIn(BaseModel):
    note: str = ""


@router.get("/color-library/use-requests")
async def list_use_requests(request: Request, status: str = Query("")) -> List[Dict[str, Any]]:
    """Kunci Warna Eksklusif — permintaan izin pakai warna milik pelanggan (badan usaha aktif)."""
    await require_permission(request, "color", "view")
    return await lock.list_requests(status, await _visible_customers(request))


@router.post("/color-library/{color_id}/use-requests")
async def create_use_request(color_id: str, payload: UseRequestIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "color", "view")
    ctx = await entity_ctx(request)
    try:
        row = await lock.create_request(color_id, payload.model_dump(), actor, ctx.active_entity_id or "")
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except lock.ColorLockError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor.get("name", ""), "color_use_requested", "color", color_id,
                {"request_id": row["id"], "target_customer_id": row["target_customer_id"]})
    return row


async def _decide(req_id: str, request: Request, action: str, note: str) -> Dict[str, Any]:
    actor = await require_permission(request, "color", "approve")
    try:
        row = await (lock.revoke(req_id, note, actor) if action == "revoke"
                     else lock.decide(req_id, action == "approve", note, actor))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except lock.ColorLockError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor.get("name", ""), f"color_use_{row['status']}", "color", row["color_id"], {"request_id": req_id, "note": note})
    return row


@router.post("/color-library/use-requests/{req_id}/approve")
async def approve_use_request(req_id: str, payload: DecisionIn, request: Request) -> Dict[str, Any]:
    return await _decide(req_id, request, "approve", payload.note)


@router.post("/color-library/use-requests/{req_id}/reject")
async def reject_use_request(req_id: str, payload: DecisionIn, request: Request) -> Dict[str, Any]:
    return await _decide(req_id, request, "reject", payload.note)


@router.post("/color-library/use-requests/{req_id}/revoke")
async def revoke_use_request(req_id: str, payload: DecisionIn, request: Request) -> Dict[str, Any]:
    return await _decide(req_id, request, "revoke", payload.note)


@router.get("/color-library/nearest")
async def nearest_color(request: Request, hex: str = Query(...), limit: int = Query(8)) -> Dict[str, Any]:
    await require_permission(request, "color", "view")
    try:
        return await svc.nearest(hex, limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/color-library/supplier-variants")
async def list_supplier_color_variants(request: Request) -> List[Dict[str, Any]]:
    """Tab 'Warna Supplier': semua versi warna supplier (rata) + warna internal & jumlah produk terkait."""
    await require_permission(request, "color", "view")
    return await svc.list_supplier_variants()


@router.get("/color-library/{color_id}/links")
async def color_links(color_id: str, request: Request) -> Dict[str, Any]:
    """Keterkaitan satu warna: warna internal ↔ versi supplier ↔ master produk (via spesifikasi) ↔ sample R&D."""
    await require_permission(request, "color", "view")
    try:
        return await svc.color_links(color_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/color-library")
async def create_color(payload: ColorCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "color", "create")
    try:
        color = await svc.create_color(payload.model_dump(), actor.get("name", ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor.get("name", ""), "color_created", "color", color["id"],
                {"code": color["code"], "name": color["name"]})
    return color


@router.patch("/color-library/{color_id}")
async def patch_color(color_id: str, payload: ColorPatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "color", "update")
    try:
        color = await svc.update_color(color_id, payload.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if color is None:
        raise HTTPException(status_code=404, detail="Warna tidak ditemukan")
    await audit(actor.get("name", ""), "color_updated", "color", color_id,
                {k: v for k, v in payload.model_dump(exclude_none=True).items() if k in ("status", "exclusive_customer_id")})
    return color


@router.delete("/color-library/{color_id}")
async def delete_color(color_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "color", "delete")
    try:
        res = await svc.delete_color(color_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await audit(actor.get("name", ""), "color_deleted", "color", color_id, res)
    return res

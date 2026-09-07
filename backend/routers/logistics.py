"""FB-02 router — Modul Logistik (pengiriman: ekspedisi / armada sendiri, foto muat & POD, posisi).

RBAC modul `logistics`: view (lihat), manage (buat/ubah/hapus — gudang, admin, manajer),
update (foto, posisi, tahapan — termasuk peran `driver`).
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response

from dependencies import require_permission, audit
from entity_scope import assert_entity_access, entity_ctx, resolve_list_scope
from schemas_logistics import DeliveryCreateIn, DeliveryUpdateIn, MyRouteIn, PositionIn, TransitionIn
from services import logistics_service as lg

router = APIRouter(prefix="/api/logistics", tags=["logistics"])


async def _guard(delivery_id: str, ctx) -> Dict[str, Any]:
    doc = await lg.get_delivery(delivery_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Pengiriman tidak ditemukan.")
    assert_entity_access(doc, lg.COLL, ctx)
    return doc


def _guard_driver_write(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """P1-1 — sopir hanya boleh MENULIS (foto/posisi/tahapan) pada pengiriman yang ditugaskan padanya.
    Melihat daftar & detail tetap seluas entitas (keputusan pemilik 2026-09-02)."""
    if actor.get("role") == "driver" and doc.get("driver_user_id") != actor.get("id"):
        raise HTTPException(status_code=403, detail="Pengiriman ini bukan tugas Anda — hanya sopir yang ditugaskan yang boleh mengubahnya.")


@router.get("/meta")
async def logistics_meta(request: Request) -> Dict[str, Any]:
    await require_permission(request, "logistics", "view")
    return lg.meta()


@router.get("/summary")
async def logistics_summary(request: Request, entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    await require_permission(request, "logistics", "view")
    ctx = await entity_ctx(request)
    return await lg.summary(resolve_list_scope(lg.COLL, {}, ctx, entity_id))


@router.get("/shipments/unassigned")
async def unassigned_shipments(request: Request, entity_id: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    await require_permission(request, "logistics", "manage")
    ctx = await entity_ctx(request)
    return await lg.unassigned_shipments(resolve_list_scope("shipments", {}, ctx, entity_id))


@router.get("/drivers")
async def list_drivers(request: Request, entity_id: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Daftar akun sopir (peran `driver`) untuk ditugaskan ke pengiriman."""
    await require_permission(request, "logistics", "manage")
    ctx = await entity_ctx(request)
    return await lg.list_drivers(entity_id or ctx.active_entity_id)


@router.post("/my-route")
async def set_my_route(payload: MyRouteIn, request: Request) -> Dict[str, Any]:
    """Sopir menyusun urutan tujuan pengiriman miliknya (route_order)."""
    actor = await require_permission(request, "logistics", "update")
    n = await lg.set_my_route(payload.ids, actor.get("id", ""))
    if n == 0:
        raise HTTPException(status_code=400, detail="Tidak ada pengiriman milik Anda dalam daftar.")
    await audit(actor["name"], "logistics_route", lg.COLL, "-", {"ids": payload.ids})
    return {"updated": n}


@router.get("/deliveries")
async def list_deliveries(request: Request, entity_id: Optional[str] = Query(None),
                          status: str = Query(""), q: str = Query(""),
                          order_id: str = Query(""), mine: bool = Query(False)) -> List[Dict[str, Any]]:
    actor = await require_permission(request, "logistics", "view")
    ctx = await entity_ctx(request)
    scope = resolve_list_scope(lg.COLL, {}, ctx, entity_id)
    return await lg.list_deliveries(scope, status, q, order_id,
                                    driver_user_id=actor.get("id") if mine else "")


@router.post("/deliveries")
async def create_delivery(payload: DeliveryCreateIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "logistics", "manage")
    ctx = await entity_ctx(request)
    try:
        doc = await lg.create_delivery(payload.model_dump(), actor, ctx.active_entity_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "logistics_create", lg.COLL, doc["id"],
                {"number": doc["number"], "shipments": doc["shipment_nos"]})
    return doc


@router.get("/deliveries/{delivery_id}")
async def get_delivery(delivery_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "logistics", "view")
    ctx = await entity_ctx(request)
    return await _guard(delivery_id, ctx)


@router.patch("/deliveries/{delivery_id}")
async def update_delivery(delivery_id: str, payload: DeliveryUpdateIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "logistics", "manage")
    ctx = await entity_ctx(request)
    await _guard(delivery_id, ctx)
    try:
        doc = await lg.update_delivery(delivery_id, payload.model_dump(exclude_unset=True), actor["name"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "logistics_update", lg.COLL, delivery_id, payload.model_dump(exclude_unset=True))
    return doc


@router.post("/deliveries/{delivery_id}/photos")
async def upload_photo(delivery_id: str, request: Request, kind: str = Form("other"),
                       note: str = Form(""), file: UploadFile = File(...)) -> Dict[str, Any]:
    actor = await require_permission(request, "logistics", "update")
    ctx = await entity_ctx(request)
    _guard_driver_write(await _guard(delivery_id, ctx), actor)
    data = await file.read()
    try:
        photo = await lg.add_photo(delivery_id, kind, file.filename or "foto.jpg",
                                   file.content_type or "", data, note, actor["name"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "logistics_photo", lg.COLL, delivery_id, {"kind": kind, "photo_id": photo["id"]})
    return photo


@router.get("/deliveries/{delivery_id}/photos/{photo_id}")
async def get_photo(delivery_id: str, photo_id: str, request: Request):
    await require_permission(request, "logistics", "view")
    ctx = await entity_ctx(request)
    await _guard(delivery_id, ctx)
    try:
        data, ct = await lg.get_photo_bytes(delivery_id, photo_id)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e) or "Foto tidak ditemukan.")
    return Response(content=data, media_type=ct, headers={"Cache-Control": "private, max-age=300"})


@router.delete("/deliveries/{delivery_id}/photos/{photo_id}")
async def delete_photo(delivery_id: str, photo_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "logistics", "update")
    ctx = await entity_ctx(request)
    _guard_driver_write(await _guard(delivery_id, ctx), actor)
    try:
        res = await lg.delete_photo(delivery_id, photo_id, actor["name"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "logistics_photo_delete", lg.COLL, delivery_id, {"photo_id": photo_id})
    return res


@router.post("/deliveries/{delivery_id}/positions")
async def add_position(delivery_id: str, payload: PositionIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "logistics", "update")
    ctx = await entity_ctx(request)
    _guard_driver_write(await _guard(delivery_id, ctx), actor)
    try:
        doc = await lg.add_position(delivery_id, payload.model_dump(), actor["name"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "logistics_position", lg.COLL, delivery_id, {"location": payload.location})
    return doc


@router.delete("/deliveries/{delivery_id}/positions/{pos_id}")
async def delete_position(delivery_id: str, pos_id: str, request: Request) -> Dict[str, Any]:
    """L-2 — hapus/koreksi posisi salah (manage)."""
    actor = await require_permission(request, "logistics", "manage")
    ctx = await entity_ctx(request)
    await _guard(delivery_id, ctx)
    try:
        res = await lg.delete_position(delivery_id, pos_id, actor["name"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "logistics_position_delete", lg.COLL, delivery_id, {"pos_id": pos_id})
    return res


@router.post("/deliveries/{delivery_id}/transition")
async def transition(delivery_id: str, payload: TransitionIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "logistics", "update")
    ctx = await entity_ctx(request)
    before = await _guard(delivery_id, ctx)
    _guard_driver_write(before, actor)
    if payload.to == "prepared" and before.get("status") == "loaded":
        await require_permission(request, "logistics", "manage")   # P1-3: bongkar hanya gudang/manajer/admin
    try:
        doc = await lg.transition(delivery_id, payload.model_dump(), actor["name"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "logistics_status", lg.COLL, delivery_id,
                {"from": before.get("status"), "to": payload.to}, reason=payload.reason or payload.note or "")
    return doc

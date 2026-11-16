"""MP-T1 — Rute Produk (docs/blueprint/unit/MP-T1.md). Baca: `product.view`; ubah: `product_route.update` (K-73)."""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from db import db
from dependencies import audit, require_permission
from entity_scope import entity_ctx
from services import product_route_service as svc

router = APIRouter(prefix="/api")


async def _write_entity(request: Request) -> str:
    ctx = await entity_ctx(request)
    if ctx.view_all or ctx.active_entity_id in ("", "all"):
        raise HTTPException(status_code=400, detail="Pilih satu PT untuk tindakan ini.")
    return ctx.active_entity_id


def _fail(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc).strip("'\""))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/product-templates/{template_id}/routes")
async def list_routes(template_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "product", "view")
    ctx = await entity_ctx(request)
    try:
        return await svc.list_for_template(template_id, ctx.active_entity_id)
    except LookupError as exc:
        raise _fail(exc) from exc


@router.get("/product-templates/{template_id}/routes/suggest")
async def suggest_routes(template_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "product_route", "update")
    entity_id = await _write_entity(request)
    return {"items": await svc.suggest(template_id, entity_id)}


@router.post("/product-templates/{template_id}/routes")
async def create_route(template_id: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product_route", "update")
    entity_id = await _write_entity(request)
    try:
        doc = await svc.create(template_id, payload or {}, actor, entity_id)
    except (LookupError, svc.RouteError) as exc:
        raise _fail(exc) from exc
    await audit(actor.get("name", ""), "create", "product_routes", doc["id"],
                {"template_id": template_id, "name": doc["name"], "steps": len(doc["steps"])})
    return doc


@router.patch("/product-routes/{route_id}")
async def update_route(route_id: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product_route", "update")
    entity_id = await _write_entity(request)
    try:
        doc = await svc.update(route_id, payload or {}, actor, entity_id)
    except (LookupError, svc.RouteError) as exc:
        raise _fail(exc) from exc
    await audit(actor.get("name", ""), "update", "product_routes", route_id,
                {k: (payload or {}).get(k) for k in ("name", "status") if k in (payload or {})})
    return doc


@router.post("/product-routes/{route_id}/primary")
async def primary_route(route_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product_route", "update")
    entity_id = await _write_entity(request)
    try:
        doc = await svc.set_primary(route_id, actor, entity_id)
    except (LookupError, svc.RouteError) as exc:
        raise _fail(exc) from exc
    await audit(actor.get("name", ""), "update", "product_routes", route_id, {"is_primary": True})
    return doc


@router.get("/products/{product_id}/route")
async def product_route(product_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "product", "view")
    ctx = await entity_ctx(request)
    prod = await db.products.find_one({"id": product_id}, {"_id": 0, "id": 1, "template_id": 1})
    if not prod:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    return {"route": await svc.effective_for_product(prod, ctx.active_entity_id)}


@router.get("/product-routes/step-options")
async def step_options(request: Request, from_stage: str = "") -> Dict[str, Any]:
    await require_permission(request, "product", "view")
    ctx = await entity_ctx(request)
    return await svc.step_options(ctx.active_entity_id, from_stage)

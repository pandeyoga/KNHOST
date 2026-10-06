"""2026-10 — Router OVERRIDE SO (izin `order.override`; harga/diskon → `order.approve_price_edit`)."""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from db import db
from core_utils import safe_doc, strip_cost_fields
from dependencies import audit, require_permission
from entity_scope import assert_entity_access, entity_ctx
from schemas import SoOverrideIn
from services import amendment_service as amd_svc
from services import so_override_service as svc

router = APIRouter(prefix="/api")


async def _order(order_id: str, request: Request) -> Dict[str, Any]:
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    assert_entity_access(order, "sales_orders", await entity_ctx(request))
    return order


@router.get("/sales-orders/{order_id}/override-context")
async def override_context(order_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "order", "override")
    order = await _order(order_id, request)
    cust = await db.customers.find_one({"id": order.get("customer_id")}, {"_id": 0, "addresses": 1}) or {}
    return {"locked_reason": await svc.lock_reason(order), "addresses": cust.get("addresses") or []}


@router.post("/sales-orders/{order_id}/override")
async def override_order(order_id: str, payload: SoOverrideIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "order", "override")
    await _order(order_id, request)
    try:
        res = await svc.apply(order_id, payload.model_dump(), actor)
    except (svc.OverrideError, amd_svc.AmendmentError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "so_override", "sales_order", order_id,
                {"changes": res["changes"], "price_amendment": (res["price_amendment"] or {}).get("number")},
                reason=payload.note)
    res["order"] = strip_cost_fields(res["order"], actor.get("role"))
    return res

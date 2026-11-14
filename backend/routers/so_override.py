"""2026-10 — Router OVERRIDE SO (izin `order.override`; harga/diskon → `order.approve_price_edit`)."""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from db import db
from core_utils import safe_doc, strip_cost_fields
from dependencies import audit, has_permission, require_permission
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
    actor = await require_permission(request, "order", "override")
    order = await _order(order_id, request)
    cust = await db.customers.find_one({"id": order.get("customer_id")}, {"_id": 0, "addresses": 1}) or {}
    return {"locked_reason": await svc.lock_reason(order), "addresses": cust.get("addresses") or [],
            # PK-38 (FX-16) — layar mematikan pilihan termin yang lebih longgar bila pelaku tidak berizin.
            "can_loosen_term": await has_permission(actor, "order", "release_unpaid"),
            "current_term": await svc.current_term(order)}


@router.post("/sales-orders/{order_id}/override")
async def override_order(order_id: str, payload: SoOverrideIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "order", "override")
    await _order(order_id, request)
    try:
        # PK-38 (FX-16, K-14) — melonggarkan termin = izin setara pengecualian kirim-sebelum-bayar.
        res = await svc.apply(order_id, payload.model_dump(), actor,
                              can_loosen_term=await has_permission(actor, "order", "release_unpaid"))
    except (svc.OverrideError, amd_svc.AmendmentError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    loosened = next((c for c in res["changes"] if c.get("field") == "payment_term_code" and c.get("loosened")), None)
    if loosened:
        await audit(actor.get("name", ""), "so_term_loosened", "sales_order", order_id,
                    {"from": loosened.get("from"), "to": loosened.get("to"),
                     "amendment": (res.get("amendment") or {}).get("number")}, reason=payload.note)
    await audit(actor.get("name", ""), "so_override", "sales_order", order_id,
                {"changes": res["changes"], "price_amendment": (res["price_amendment"] or {}).get("number")},
                reason=payload.note)
    res["order"] = strip_cost_fields(res["order"], actor.get("role"))
    return res

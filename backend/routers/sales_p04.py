"""P04 — Keep/Pending, aturan grade pelanggan, kandidat roll berkelayakan, ringkasan stok Sales."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from db import db
from core_utils import safe_doc
from dependencies import audit, require_any_permission, require_permission
from entity_scope import assert_entity_access, entity_ctx, resolve_list_scope
from services import sales_p04_service as svc

router = APIRouter(prefix="/api")


@router.get("/sales/keep-pending")
async def keep_pending(request: Request, entity_id: Optional[str] = None) -> Dict[str, Any]:
    # L02 LN-020-T02 — Sales juga membaca antrean, dibatasi ke pesanan miliknya.
    actor = await require_any_permission(request, [("order", "verify"), ("order", "view")])
    ctx = await entity_ctx(request)
    from services import sales_ownership
    scope = sales_ownership.apply_scope(resolve_list_scope("sales_orders", {}, ctx, entity_id), actor)
    eff = entity_id or getattr(ctx, "active_entity_id", "") or ""
    return await svc.keep_pending(scope, eff if eff != "all" else "")


async def _customer(customer_id: str, request: Request) -> Dict[str, Any]:
    cust = safe_doc(await db.customers.find_one({"id": customer_id}, {"_id": 0}))
    if not cust:
        raise HTTPException(status_code=404, detail="Pelanggan tidak ditemukan.")
    assert_entity_access(cust, "customers", await entity_ctx(request))
    return cust


@router.get("/customers/{customer_id}/grade-rules")
async def get_grade_rules(customer_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "order", "view")
    cust = await _customer(customer_id, request)
    rule = await svc.get_rule(cust["id"])
    if rule:
        rule["min_grade"] = svc._min_of(rule)
    return {"customer_id": cust["id"], "customer_name": cust.get("name", ""), "rule": rule}


@router.put("/customers/{customer_id}/grade-rules")
async def put_grade_rules(customer_id: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "order", "verify")
    cust = await _customer(customer_id, request)
    try:
        rule = await svc.save_rule(cust, payload or {}, actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await audit(actor.get("name", ""), "update", "customer_grade_rules", cust["id"],
                {"min_grade": rule.get("min_grade"), "preferred": rule.get("preferred_grades"),
                 "accept_bs": rule.get("accept_bs")})
    return {"customer_id": cust["id"], "customer_name": cust.get("name", ""), "rule": rule}


@router.get("/sales-orders/{order_id}/items/{product_id}/roll-candidates")
async def roll_candidates(order_id: str, product_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "inventory", "pegging")
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    assert_entity_access(order, "sales_orders", await entity_ctx(request))
    return await svc.candidates(order, product_id)


@router.get("/sales/stock-summary")
async def stock_summary(product_id: str, request: Request, entity_id: Optional[str] = None) -> Dict[str, Any]:
    await require_permission(request, "product", "view")
    ctx = await entity_ctx(request)
    eff = (entity_id or getattr(ctx, "active_entity_id", "") or "").strip()
    if eff == "all":
        eff = ""
    return await svc.sales_stock_summary(product_id, eff)

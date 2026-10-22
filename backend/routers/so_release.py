"""Trial 22 Okt 2026 (E8/E10) — rute alur pesanan baru: Periksa & lepas ke gudang, lepas pesanan yang ditahan,
lanjut harga normal sesudah harga khusus ditolak. Logika di `services/so_release_service.py`."""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core_utils import safe_doc, strip_cost_fields
from db import db
from dependencies import require_permission
from entity_scope import assert_entity_access, entity_ctx

router = APIRouter(prefix="/api")


class ReviewReleaseIn(BaseModel):
    note: str = ""
    hold: bool = False


async def _order_in_scope(order_id: str, request: Request) -> Dict[str, Any]:
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    assert_entity_access(order, "sales_orders", await entity_ctx(request))  # IDOR
    return order


@router.post("/sales-orders/{order_id}/review-release")
async def review_release(order_id: str, payload: ReviewReleaseIn, request: Request) -> Dict[str, Any]:
    """Trial 22 Okt (E8) — Admin Sales: Periksa & lepas ke gudang (verifikasi + ajukan + konfirmasi dalam satu
    langkah; menunggu ACC → dilepas otomatis sesudah ACC; `hold` = tahan dulu)."""
    actor = await require_permission(request, "order", "confirm")
    await _order_in_scope(order_id, request)
    from services import so_release_service as _rel
    out = await _rel.review_and_release(order_id, actor, payload.note, payload.hold)
    out["order"] = strip_cost_fields(out["order"], actor.get("role"))
    return out


@router.post("/sales-orders/{order_id}/release")
async def release_order(order_id: str, request: Request) -> Dict[str, Any]:
    """Trial 22 Okt (E8) — lepas pesanan yang sebelumnya ditahan Admin Sales."""
    actor = await require_permission(request, "order", "confirm")
    await _order_in_scope(order_id, request)
    from services import so_release_service as _rel
    out = await _rel.release_hold(order_id, actor)
    out["order"] = strip_cost_fields(out["order"], actor.get("role"))
    return out


@router.post("/sales-orders/{order_id}/approvals/{approval_id}/continue-normal-price")
async def continue_normal_price(order_id: str, approval_id: str, request: Request) -> Dict[str, Any]:
    """Trial 22 Okt (E10) — harga khusus DITOLAK → sales lanjut dengan harga normal."""
    actor = await require_permission(request, "order", "update")
    await _order_in_scope(order_id, request)
    from services import so_release_service as _rel
    out = await _rel.continue_normal_price(order_id, approval_id, actor)
    out["order"] = strip_cost_fields(out["order"], actor.get("role"))
    return out

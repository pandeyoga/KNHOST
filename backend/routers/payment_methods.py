"""PM-T1 — daftar induk cara bayar untuk layar (`docs/blueprint/unit/PM-T1.md`); PM-T2 — instruksi bayar pesanan.

`GET /api/payment-methods?direction=&entity_id=` cukup login: data rujukan tanpa nominal (`02_STANDAR.md` §3.1 Z3,
`login_only_endpoints.LOGIN_ONLY`). Isi = cara bayar AKTIF untuk PT itu (baris khusus PT menang atas baris global).
Mengelola daftarnya lewat master berlapis `payment-methods` (`/api/entity-masters/payment-methods`, izin
`cash.configure`).

`GET /api/sales-orders/{id}/payment-instruction` (PM-T2, `order.view` + pagar PT dan pemilik pesanan): blok instruksi
bayar berkode (`services/payment_code_service.instruction`) — bahan tombol "Salin instruksi bayar" di detail pesanan.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from db import db
from dependencies import require_permission
from entity_scope import assert_entity_access, entity_ctx, resolve_requested_entity
from services import payment_method_service as pms

router = APIRouter(prefix="/api")


@router.get("/payment-methods")
async def list_payment_methods(request: Request, direction: str = Query(""),
                               entity_id: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    ctx = await entity_ctx(request)   # login + PT dalam penugasan (403 bila PT lain)
    arah = (direction or "").strip().lower()
    if arah and arah not in pms.ARAH:
        raise HTTPException(status_code=400, detail="Arah cara bayar harus masuk atau keluar.")
    req = (entity_id or "").strip()
    eid = "" if (req == "all" or (not req and getattr(ctx, "view_all", False))) else resolve_requested_entity(ctx, req)
    return [pms.untuk_layar(r) for r in await pms.active_for(eid, arah)]


@router.get("/sales-orders/{order_id}/payment-instruction")
async def order_payment_instruction(order_id: str, request: Request) -> Dict[str, Any]:
    """PM-T2 — `{order_number, method_name, account, items: [{label, amount, due_date, due_label, pay_code}], text,
    note}`; `items` kosong (dengan `note`) bila belum ada kode bayar atau rekening tujuan yang boleh tampil."""
    actor = await require_permission(request, "order", "view")
    order = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    assert_entity_access(order, "sales_orders", await entity_ctx(request))
    from services import sales_ownership
    sales_ownership.assert_may_open(order, actor)
    from services import payment_code_service as pcs
    return await pcs.instruction_for(order)

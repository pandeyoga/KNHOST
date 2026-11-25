"""Lapor Bayar CBD & DP (LB-T1) — baca laporan bayar sebuah pesanan.

Rute tulis (buat, lampiran, terima, tolak) menyusul di Tugas 3 dan 4. Rute baca ini mengikuti izin lihat pesanan
(`order.view`), pagar PT, dan pagar pemilik pesanan sama seperti detail pesanan; respons juga membawa hak pemanggil
(`payment_report.create` / `.decide`) supaya layar menampilkan tombol yang sah saja.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from core_utils import safe_doc
from db import db
from dependencies import has_permission, require_permission
from entity_scope import assert_entity_access, entity_ctx
from services import payment_report_service as prs
from services import sales_ownership

router = APIRouter(prefix="/api")


@router.get("/sales-orders/{order_id}/payment-reports")
async def list_payment_reports(order_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "order", "view")
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    assert_entity_access(order, "sales_orders", await entity_ctx(request))
    sales_ownership.assert_may_open(order, actor)
    rows = await db.payment_reports.find({"order_id": order_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {
        "items": [prs.tampil(r) for r in rows],
        "bisa_lapor": await has_permission(actor, "payment_report", "create"),
        "bisa_putuskan": await has_permission(actor, "payment_report", "decide"),
    }

"""Invoices router: daftar faktur (invoices). PK-19 — jalur "simulasi pembayaran" dimatikan (410)."""
import logging
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from db import db
from dependencies import require_permission
from core_utils import safe_doc
from entity_scope import entity_ctx, assert_entity_access, scope_value

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.get("/invoices")
async def list_invoices(request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "order", "view")
    # Tanya KN F0.4 — invoice hanya dari entitas dalam cakupan baca pengguna.
    ent = scope_value(await entity_ctx(request))
    return await db.invoices.find({"entity_id": ent}, {"_id": 0}).sort("created_at", -1).to_list(200)


@router.get("/sales-orders/{order_id}/invoices")
async def order_invoices(order_id: str, request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "order", "view")
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    # INV-ENTITY-01 (KN-076-IDOR-READ-SUBRES P0): cegah baca invoice SO lintas-entitas.
    assert_entity_access(order, "sales_orders", await entity_ctx(request))
    return await db.invoices.find({"order_id": order_id}, {"_id": 0}).to_list(20)


@router.post("/sales-orders/{order_id}/simulate-payment")
async def simulate_payment(order_id: str, request: Request) -> Dict[str, Any]:
    """PK-19 (SL-05, IA-07) — "Simulasi bayar" DIMATIKAN: dulu menulis dokumen faktur utuh ke `payments[]` dengan izin
    ubah pesanan dan menelan galat jurnal. Pembayaran pesanan dicatat lewat kwitansi (satu fungsi alokasi). Selalu 410
    sesudah pemeriksaan izin; isi permintaan diabaikan dan tidak ada yang ditulis."""
    await require_permission(request, "order", "view")
    raise HTTPException(status_code=410, detail=(
        "Simulasi pembayaran sudah tidak dipakai. Catat pembayaran lewat kwitansi (Catat Penerimaan)."))

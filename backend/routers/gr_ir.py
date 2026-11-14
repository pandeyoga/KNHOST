"""PK-28 (IV-03) — Hutang › GR/IR: sisa "barang diterima belum ditagih" per PO beserta umurnya, dan kliring sisa yang
tidak akan tertagih. Logika di `services/grir_service.py`; angka dari buku besar (`vendor_bill_service.grir_by_po`).
"""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from db import db
from dependencies import require_permission
from entity_scope import entity_ctx, guard_doc, resolve_requested_entity
from services import grir_service

router = APIRouter(prefix="/api")

#: Ukuran halaman daftar (bawaan dan batas atas). Batas teknis tampilan, bukan aturan bisnis.
PAGE_SIZE_DEFAULT = 50
PAGE_SIZE_MAX = 200
MSG_SEMUA_PT = "Pilih satu PT untuk melihat GR/IR."


class GrIrClearRequest(BaseModel):
    reason: str = ""


@router.get("/finance/gr-ir")
async def list_gr_ir(request: Request, status: str = Query("terbuka", pattern="^(terbuka|semua)$"),
                     bucket: str = Query("", pattern="^(|0-30|31-60|61-90|>90)$"),
                     q: str = Query("", max_length=100), page: int = Query(1, ge=1),
                     page_size: int = Query(PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
                     entity_id: str = Query("")) -> Dict[str, Any]:
    """Sisa GR/IR per PO untuk SATU PT (PT dari konteks; "Semua PT" → 400)."""
    await require_permission(request, "vendor_bill", "view")
    ctx = await entity_ctx(request)
    if entity_id == "all" or (not entity_id and (ctx.view_all or ctx.active_entity_id in ("", "all"))):
        raise HTTPException(status_code=400, detail=MSG_SEMUA_PT)
    eid = resolve_requested_entity(ctx, entity_id)
    return await grir_service.list_grir(eid, status=status, bucket=bucket, q=q, page=page, page_size=page_size)


@router.post("/finance/gr-ir/{po_id}/clear")
async def clear_gr_ir(po_id: str, payload: GrIrClearRequest, request: Request) -> Dict[str, Any]:
    """Kliring sisa GR/IR satu PO ke akun selisih harga pembelian (menerbitkan jurnal)."""
    actor = await require_permission(request, "accounting", "manage")
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    await guard_doc(request, "purchase_orders", po, not_found="Purchase Order tidak ditemukan")
    return await grir_service.clear(po, payload.reason, actor)

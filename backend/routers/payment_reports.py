"""Lapor Bayar CBD & DP (LB-T1, LB-T3) — laporan bayar pelanggan: buat, lampiran bukti, baca per pesanan.

Rancangan `docs/superpowers/specs/2026-11-25-lapor-bayar-cbd-design.md` §5.4. Keputusan terima/tolak menyusul di Tugas 4.
Setiap rute melewati urutan pagar yang sama: izin → pesanan ada → PT pengguna (403 untuk PT lain) → pemilik pesanan
(sales hanya pesanan miliknya). Lampiran mengikuti pola bukti persetujuan SO (`storage_service`; unduh inline lewat blob).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from core_utils import new_id, now_iso, safe_doc
from db import db
from dependencies import audit, has_permission, require_permission
from entity_scope import assert_entity_access, entity_ctx, guard_doc
from services import payment_report_service as prs
from services import sales_ownership, storage_service as storage

router = APIRouter(prefix="/api")


class LaporBayarIn(BaseModel):
    amount: float   # tak hingga/NaN ditolak layanan (400); PosQty membuat 422 yang gagal diserialkan (500)
    transfer_date: str
    account_id: str
    method: str
    reference_no: Optional[str] = ""
    note: Optional[str] = ""


async def _pesanan_berpagar(request: Request, actor: Dict[str, Any], order_id: str,
                            *, tulis: bool = True) -> Dict[str, Any]:
    """Pesanan yang boleh disentuh pemanggil: ada, PT sah, dan — untuk peran bercakupan "milik sendiri" — miliknya.
    Rute tulis memakai pagar PT AKTIF (`guard_doc`); rute baca memakai pagar yang sama dengan rincian pesanan
    (`assert_entity_access`, penugasan PT). PT di luar penugasan → 403; 404 lokasi tugas tetap 404."""
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    ctx = await entity_ctx(request)
    try:
        if tulis:
            await guard_doc(request, "sales_orders", order)
        else:
            assert_entity_access(order, "sales_orders", ctx)
    except HTTPException as exc:
        ent = order.get("entity_id")
        if tulis:
            di_luar = exc.status_code == 404
        else:
            di_luar = bool(ent) and ent not in ctx.allowed_entity_ids
        if di_luar:
            raise HTTPException(status_code=403, detail="Pesanan ini milik badan usaha lain") from exc
        raise
    sales_ownership.assert_may_open(order, actor)
    return order


async def _laporan_berpagar(request: Request, actor: Dict[str, Any], report_id: str, *, tulis: bool = True):
    rep = await db.payment_reports.find_one({"id": report_id}, {"_id": 0})
    if not rep:
        raise HTTPException(status_code=404, detail="Laporan bayar tidak ditemukan")
    order = await _pesanan_berpagar(request, actor, rep.get("order_id", ""), tulis=tulis)
    return rep, order


@router.get("/sales-orders/{order_id}/payment-reports")
async def list_payment_reports(order_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "order", "view")
    await _pesanan_berpagar(request, actor, order_id, tulis=False)
    return {
        "items": await prs.list_for_order(order_id),
        "bisa_lapor": await has_permission(actor, "payment_report", "create"),
        "bisa_putuskan": await has_permission(actor, "payment_report", "decide"),
    }


@router.post("/sales-orders/{order_id}/payment-reports")
async def create_payment_report(order_id: str, body: LaporBayarIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "payment_report", "create")
    order = await _pesanan_berpagar(request, actor, order_id)
    rep = await prs.create_report(order, body.model_dump(), actor)
    await audit(actor["name"], "payment_report_created", "sales_order", order_id,
                {"report_id": rep["id"], "number": rep["number"], "amount": rep["amount"]})
    return rep


@router.post("/payment-reports/{report_id}/attachments")
async def upload_attachment(report_id: str, request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    actor = await require_permission(request, "payment_report", "create")
    rep, _order = await _laporan_berpagar(request, actor, report_id)
    if rep.get("status") != prs.MENUNGGU:
        raise HTTPException(status_code=409, detail="Laporan sudah diputus; lampiran tidak bisa ditambah")
    data = await file.read()
    try:
        content_type = storage.validate_upload(file.filename, file.content_type, len(data), data[:16])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    path = storage.build_path("payment_reports", storage.ext_of(file.filename))
    try:
        res = await storage.put_object(path, data, content_type)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Gagal mengunggah file: {e}")
    att = {
        "id": new_id("att"), "storage_path": res.get("path", path), "original_filename": file.filename,
        "content_type": content_type, "size": res.get("size", len(data)),
        "uploaded_by": actor["name"], "uploaded_at": now_iso(), "is_deleted": False,
    }
    out = await prs.add_attachment(rep, att)
    await audit(actor["name"], "payment_report_attachment_added", "payment_report", report_id,
                {"file": file.filename, "number": rep.get("number", "")})
    return out


@router.get("/payment-reports/{report_id}/attachments/{att_id}")
async def download_attachment(report_id: str, att_id: str, request: Request):
    actor = await require_permission(request, "order", "view")
    rep, _order = await _laporan_berpagar(request, actor, report_id, tulis=False)
    att = next((a for a in (rep.get("attachments") or []) if a.get("id") == att_id and not a.get("is_deleted")), None)
    if not att:
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan.")
    try:
        content, ctype = await storage.get_object(att["storage_path"])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Gagal mengambil file: {e}")
    return Response(
        content=content, media_type=att.get("content_type", ctype),
        headers={"Content-Disposition": _disposisi(att.get("original_filename") or "file")},
    )


def _disposisi(nama: str) -> str:
    """`Content-Disposition` inline aman: `filename` ASCII (tanpa kutip/kendali) + `filename*` UTF-8 berkode persen."""
    ascii_ = "".join(c if 32 <= ord(c) < 127 and c not in '"\\;' else "_" for c in nama) or "file"
    return f"inline; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nama, safe='')}"

"""CR-T5 — daftar kerja "Kredit & Plafon", rekening koran pelanggan, naskah pengingat, kotak Eksposur
(`docs/blueprint/unit/CR-T5.md`, tabel "Server").

  GET /api/credit-desk?queue=&page=&page_size=&q=          credit_profile.view
  GET /api/credit-desk/summary                             credit_profile.view
  GET /api/customers/{id}/statement?entity_id=&from=&to=   salah satu: credit_profile.view, ar_receipt.view
                                                           + can_access_customer
  GET /api/customers/{id}/statement.pdf?…                  sama + document.print (`format=html` untuk uji)
  GET /api/customers/{id}/reminder-text?entity_id=         order.view + can_collect_customer
  GET /api/customers/{id}/exposure?entity_id=              salah satu: customer.view, credit_profile.view
                                                           + can_view_credit (kotak Eksposur kartu pelanggan)

PT selalu lewat konteks (`resolve_requested_entity`, N1). Antrean di mode "Semua PT" = gabungan PT yang ditugaskan
(hanya-baca, N3); rekening koran dan naskah menuntut satu PT. Logika di `services/credit_desk_service.py` dan
`services/customer_statement_service.py`.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response

from core_utils import safe_doc
from db import db
from dependencies import require_any_permission, require_permission
from entity_scope import EntityContext, entity_ctx, resolve_requested_entity
from services import credit_desk_service as desk
from services import customer_statement_service as css
from services.customer_service import can_access_customer, can_collect_customer, can_view_credit

router = APIRouter(prefix="/api")

MODUL = "Uang Masuk, Piutang & Faktur Pajak"
PESAN_MEJA = f"Anda belum punya akses untuk melihat daftar kerja kredit. Minta Admin menambahkan akses '{MODUL}'."
PESAN_RK = f"Anda belum punya akses untuk melihat rekening koran pelanggan. Minta Admin menambahkan akses '{MODUL}'."
PESAN_CETAK = ("Anda belum punya akses untuk mencetak dokumen. Minta Admin menambahkan akses 'Dokumen & Cetak'.")
PESAN_NASKAH = ("Anda belum punya akses untuk menyalin pengingat tagihan. Minta Admin menambahkan akses "
                "'Pesanan Penjualan (SO)'.")
PESAN_EKSPOSUR = ("Anda belum punya akses untuk melihat eksposur kredit pelanggan. Minta Admin menambahkan akses "
                  "'Pelanggan'.")
LUAR_CAKUPAN = "Pelanggan ini di luar cakupan Anda."
TIDAK_ADA = "Pelanggan tidak ditemukan."


def _ents(ctx: EntityContext) -> List[str]:
    """PT antrean: mode "Semua PT" (gabungan) = semua PT yang ditugaskan; selain itu PT aktif."""
    return list(ctx.allowed_entity_ids) if ctx.view_all else [ctx.active_entity_id]


def _satu_pt(ctx: EntityContext, entity_id: Optional[str]) -> str:
    """Rekening koran & naskah: satu PT. "all" atau kosong saat "Semua PT" → 400."""
    req = (entity_id or "").strip()
    if req == "all" or (not req and ctx.view_all):
        raise HTTPException(status_code=400, detail=css.PESAN_SEMUA_PT)
    return resolve_requested_entity(ctx, req or None)


async def _pelanggan(customer_id: str) -> Dict[str, Any]:
    c = safe_doc(await db.customers.find_one({"id": customer_id}, {"_id": 0}))
    if not c:
        raise HTTPException(status_code=404, detail=TIDAK_ADA)
    return c


@router.get("/credit-desk")
async def credit_desk_queue(request: Request, queue: str = Query(""), page: int = Query(1, ge=1),
                            page_size: int = Query(25, ge=1, le=100), q: str = Query("")) -> Dict[str, Any]:
    actor = await require_permission(request, "credit_profile", "view", detail=PESAN_MEJA)
    if queue not in desk.QUEUES:
        raise HTTPException(status_code=400, detail=desk.PESAN_ANTREAN)
    ctx = await entity_ctx(request)
    res = await desk.queue(queue, _ents(ctx), actor, page=page, page_size=page_size, q=q)
    return {**res, "queue": queue, "combined": bool(ctx.view_all)}


@router.get("/credit-desk/summary")
async def credit_desk_summary(request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "credit_profile", "view", detail=PESAN_MEJA)
    ctx = await entity_ctx(request)
    return {**await desk.summary(_ents(ctx), actor), "combined": bool(ctx.view_all)}


#: Izin rekening koran (salah satu).
IZIN_RK = [("credit_profile", "view"), ("ar_receipt", "view")]


async def _rekening_koran(request: Request, actor: Dict[str, Any], customer_id: str, entity_id: Optional[str],
                          date_from: Optional[str], date_to: Optional[str]) -> Dict[str, Any]:
    customer = await _pelanggan(customer_id)
    if not await can_access_customer(actor, customer):
        raise HTTPException(status_code=403, detail=LUAR_CAKUPAN)
    eid = _satu_pt(await entity_ctx(request), entity_id)
    try:
        return await css.statement(customer_id, eid, date_from, date_to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/customers/{customer_id}/statement")
async def customer_statement(customer_id: str, request: Request, entity_id: Optional[str] = None,
                             date_from: Optional[str] = Query(None, alias="from"),
                             date_to: Optional[str] = Query(None, alias="to")) -> Dict[str, Any]:
    actor = await require_any_permission(request, IZIN_RK, detail=PESAN_RK)
    return await _rekening_koran(request, actor, customer_id, entity_id, date_from, date_to)


@router.get("/customers/{customer_id}/statement.pdf")
async def customer_statement_pdf(customer_id: str, request: Request, entity_id: Optional[str] = None,
                                 date_from: Optional[str] = Query(None, alias="from"),
                                 date_to: Optional[str] = Query(None, alias="to"),
                                 format: str = Query("pdf", pattern="^(pdf|html)$")):
    actor = await require_any_permission(request, IZIN_RK, detail=PESAN_RK)
    await require_permission(request, "document", "print", detail=PESAN_CETAK)
    st = await _rekening_koran(request, actor, customer_id, entity_id, date_from, date_to)
    html = await css.statement_html(st)
    if format == "html":
        return HTMLResponse(content=html)
    from services.pdf_engine import render_pdf
    try:
        pdf, _engine = render_pdf(html)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Gagal membuat PDF rekening koran: {exc}") from exc
    nama = f"rekening-koran-{(st['customer'].get('code') or customer_id)}-{st['from']}-{st['to']}.pdf".replace("/", "-")
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nama}"'})


@router.get("/customers/{customer_id}/reminder-text")
async def customer_reminder_text(customer_id: str, request: Request, entity_id: Optional[str] = None) -> Dict[str, Any]:
    actor = await require_permission(request, "order", "view", detail=PESAN_NASKAH)
    customer = await _pelanggan(customer_id)
    if not await can_collect_customer(actor, customer):
        raise HTTPException(status_code=403, detail=LUAR_CAKUPAN)
    eid = _satu_pt(await entity_ctx(request), entity_id)
    return {**await desk.reminder_text(customer, eid), "entity_id": eid}


@router.get("/customers/{customer_id}/exposure")
async def customer_exposure(customer_id: str, request: Request, entity_id: Optional[str] = None) -> Dict[str, Any]:
    actor = await require_any_permission(request, [("customer", "view"), ("credit_profile", "view")],
                                         detail=PESAN_EKSPOSUR)
    customer = await _pelanggan(customer_id)
    if not can_view_credit(actor, customer):
        raise HTTPException(status_code=403, detail=LUAR_CAKUPAN)
    ctx = await entity_ctx(request)
    req = (entity_id or "").strip()
    if req in ("", "all"):   # kartu pelanggan: PT aktif; "Semua PT" → PT pemilik data pelanggan (bila ditugaskan)
        own = customer.get("entity_id") or ""
        req = own if ctx.view_all and own in ctx.allowed_entity_ids else ""
    eid = resolve_requested_entity(ctx, req or None)
    return await desk.exposure(customer, eid)

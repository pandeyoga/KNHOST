"""Faktur Pajak Jual (tax_invoices) router — Sub-fase 1.9.

Manual issuance (opsional/tidak wajib) dari Sales Order; PKP-only.
Hybrid number (FKT-##### + NSFP resmi) + status normal/pengganti/batal + dokumen HTML.

TX-T2 (TX-05, K-32) — status `draf` (draf per surat jalan & dokumen pajak retur), terbit/buang draf, bangun ulang draf
satu masa, dan pencocokan PPN keluaran per PT per masa (`GET /tax/output-reconciliation`). Semua aksi ber-id mengadu
PT dokumen dengan `guard_doc` (02 §3.4 N1); PT bangun ulang/pencocokan = PT aktif atau PT yang diminta dalam cakupan.
"""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from db import db
from dependencies import require_permission, audit
from core_utils import safe_doc
from entity_scope import entity_ctx, guard_doc, resolve_list_scope, assert_entity_access, resolve_scope_ids
from schemas import (
    TaxInvoiceCreate, TaxInvoiceNsfpUpdate, TaxInvoiceReplace, TaxInvoiceCancel,
    TaxInvoiceIssueDraft, TaxInvoiceDiscard, TaxDraftRebuild,
)
from services.tax_invoice_service import (
    issue_tax_invoice, replace_tax_invoice, cancel_tax_invoice,
    set_nsfp, render_faktur_html, issue_draft, discard_draft, rebuild_drafts, output_reconciliation,
    PESAN_PILIH_PT,
)

router = APIRouter(prefix="/api")


@router.get("/tax-invoices")
async def list_tax_invoices(request: Request, order_id: str = None,
                           entity_id: str = None, status: str = None, doc_kind: str = None) -> List[Dict[str, Any]]:
    """Daftar Faktur Pajak — Sub-fase 1.9 (filter order_id/entity_id/status).

    TX-T2 — status `draf`/`diganti` dan `doc_kind` (`faktur` = termasuk dokumen lama tanpa field · `retur`)."""
    await require_permission(request, "tax_invoice", "view")
    ctx = await entity_ctx(request)
    query: Dict[str, Any] = {}
    if order_id:
        query["order_id"] = order_id
    if status:
        query["status"] = status
    if doc_kind == "retur":
        query["doc_kind"] = "retur"
    elif doc_kind == "faktur":
        query["doc_kind"] = {"$ne": "retur"}
    query = resolve_list_scope("tax_invoices", query, ctx, entity_id)
    return await db.tax_invoices.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)


async def _faktur_milik_pt(request: Request, fkt_id: str) -> None:
    """PK-45 (TX-03) — faktur hanya diubah/diganti/dibatalkan dari PT pemiliknya (02_STANDAR §3.4 N1)."""
    fkt = await db.tax_invoices.find_one({"id": fkt_id}, {"_id": 0})
    await guard_doc(request, "tax_invoices", fkt, not_found="Faktur Pajak tidak ditemukan")


@router.get("/tax-invoices/{fkt_id}")
async def get_tax_invoice(fkt_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "tax_invoice", "view")
    ctx = await entity_ctx(request)
    fkt = safe_doc(await db.tax_invoices.find_one({"id": fkt_id}, {"_id": 0}))
    if not fkt:
        raise HTTPException(status_code=404, detail="Faktur Pajak tidak ditemukan")
    assert_entity_access(fkt, "tax_invoices", ctx)
    return fkt


@router.post("/sales-orders/{order_id}/tax-invoice")
async def issue_for_order(order_id: str, payload: TaxInvoiceCreate, request: Request) -> Dict[str, Any]:
    """Terbitkan Faktur Pajak (MANUAL) untuk order. PKP-only, idempotent."""
    actor = await require_permission(request, "tax_invoice", "create")
    fkt = await issue_tax_invoice(order_id, payload.kode_transaksi,
                                  payload.faktur_date, payload.nsfp, actor["name"])
    await audit(actor["name"], "tax_invoice_issued", "tax_invoice", fkt["id"],
                {"number": fkt["number"], "order": fkt["order_number"]})
    return fkt


@router.patch("/tax-invoices/{fkt_id}/nsfp")
async def update_nsfp(fkt_id: str, payload: TaxInvoiceNsfpUpdate, request: Request) -> Dict[str, Any]:
    """Isi/ubah NSFP resmi 16-digit (menyusul dari e-Faktur/Coretax)."""
    actor = await require_permission(request, "tax_invoice", "update")
    await _faktur_milik_pt(request, fkt_id)
    fkt = await set_nsfp(fkt_id, payload.nsfp, payload.kode_transaksi)
    await audit(actor["name"], "tax_invoice_nsfp_set", "tax_invoice", fkt_id,
                {"nsfp": payload.nsfp})
    return fkt


@router.post("/tax-invoices/{fkt_id}/replace")
async def replace_faktur(fkt_id: str, payload: TaxInvoiceReplace, request: Request) -> Dict[str, Any]:
    """Terbitkan Faktur Pajak PENGGANTI (revisi)."""
    actor = await require_permission(request, "tax_invoice", "replace")
    await _faktur_milik_pt(request, fkt_id)
    fkt = await replace_tax_invoice(fkt_id, payload.reason, payload.kode_transaksi,
                                    payload.nsfp, actor["name"])
    await audit(actor["name"], "tax_invoice_replaced", "tax_invoice", fkt["id"],
                {"replaces": fkt_id, "number": fkt["number"]})
    return fkt


@router.post("/tax-invoices/{fkt_id}/cancel")
async def cancel_faktur(fkt_id: str, payload: TaxInvoiceCancel, request: Request) -> Dict[str, Any]:
    """Batalkan Faktur Pajak (wajib alasan)."""
    actor = await require_permission(request, "tax_invoice", "cancel")
    await _faktur_milik_pt(request, fkt_id)
    fkt = await cancel_tax_invoice(fkt_id, payload.reason, actor["name"])
    await audit(actor["name"], "tax_invoice_cancelled", "tax_invoice", fkt_id,
                {"reason": payload.reason})
    return fkt


@router.get("/tax-invoices/{fkt_id}/document")
async def faktur_document(fkt_id: str, request: Request):
    """Dokumen Faktur Pajak (HTML siap cetak)."""
    await require_permission(request, "tax_invoice", "view")
    html = await render_faktur_html(fkt_id)
    return HTMLResponse(content=html)


# ── TX-T2 — draf faktur, dokumen pajak retur, pencocokan PPN keluaran ─────────────────────────────────────────────────
def _satu_pt(ids: List[str]) -> str:
    """Mode "Semua PT" hanya baca (02 §3.4 N3): aksi/pencocokan per PT butuh tepat satu PT."""
    if len(ids) != 1 or not ids[0] or ids[0] == "all":
        raise HTTPException(status_code=400, detail=PESAN_PILIH_PT)
    return ids[0]


@router.post("/tax-invoices/drafts/rebuild")
async def rebuild_tax_drafts(payload: TaxDraftRebuild, request: Request) -> Dict[str, Any]:
    """Bangun ulang draf faktur per surat jalan & dokumen pajak retur satu masa untuk PT aktif (idempoten)."""
    actor = await require_permission(request, "tax_invoice", "create")
    eid = _satu_pt(resolve_scope_ids(await entity_ctx(request), None))
    res = await rebuild_drafts(eid, payload.period, actor=actor["name"])
    await audit(actor["name"], "tax_invoice_drafts_rebuilt", "tax_invoice", eid,
                {"period": res["period"], "created": res["created"], "skipped": res["skipped"]})
    return res


@router.post("/tax-invoices/{fkt_id}/issue")
async def issue_tax_draft(fkt_id: str, payload: TaxInvoiceIssueDraft, request: Request) -> Dict[str, Any]:
    """Terbitkan draf faktur / dokumen pajak retur (draf → normal)."""
    actor = await require_permission(request, "tax_invoice", "create")
    await _faktur_milik_pt(request, fkt_id)
    fkt = await issue_draft(fkt_id, actor, faktur_date=payload.faktur_date, nsfp=payload.nsfp,
                            kode_transaksi=payload.kode_transaksi)
    await audit(actor["name"], "tax_invoice_draft_issued", "tax_invoice", fkt_id,
                {"number": fkt.get("number"), "doc_kind": fkt.get("doc_kind"), "ppn": fkt.get("ppn_amount")})
    return fkt


@router.post("/tax-invoices/{fkt_id}/discard")
async def discard_tax_draft(fkt_id: str, payload: TaxInvoiceDiscard, request: Request) -> Dict[str, Any]:
    """Buang draf (alasan wajib) — sumbernya tetap tampil di pencocokan PPN keluaran."""
    actor = await require_permission(request, "tax_invoice", "cancel")
    await _faktur_milik_pt(request, fkt_id)
    fkt = await discard_draft(fkt_id, payload.reason or "", actor)
    await audit(actor["name"], "tax_invoice_draft_discarded", "tax_invoice", fkt_id,
                {"number": fkt.get("number"), "reason": fkt.get("discard_reason")})
    return fkt


@router.get("/tax/output-reconciliation")
async def get_output_reconciliation(request: Request, period: str = None, entity_id: str = None) -> Dict[str, Any]:
    """Pencocokan PPN keluaran satu PT satu masa: faktur, dokumen retur, buku besar, selisih dan penyebabnya."""
    await require_permission(request, "tax_invoice", "view")
    eid = _satu_pt(resolve_scope_ids(await entity_ctx(request), entity_id))
    if not period:
        from services.book_date import periode_buku
        period = periode_buku()
    return await output_reconciliation(eid, period)

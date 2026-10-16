"""Depth #2 — Purchase Requisition (PR) router + Reorder/Replenishment.

Hulu procurement: PR → approval → konversi ke PO. Plus saran reorder.
Permission module: 'purchase_requisition'.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Request, HTTPException, Query
from db import db
from dependencies import require_permission, current_user, audit
from core_utils import now_iso, safe_doc
from entity_scope import entity_ctx, resolve_list_scope, assert_entity_access
from schemas import (
    PurchaseRequisitionCreate, PurchaseRequisitionDecision, PurchaseRequisitionConvert,
    PRRealizePoIn, PRRealizeMakloonIn, PRLineQtyIn,
)
from services import purchase_requisition_service as svc
from services import pr_sourcing_service as src
from services import approval_matrix_service as amx  # PS-20 — matriks persetujuan mengikat
from services import line_scope                      # FASE L — pagar & penyaring lini

router = APIRouter(prefix="/api")


@router.get("/purchase-requisitions")
async def list_requisitions(
    request: Request,
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    line: str = Query("", description="FASE L — penyaring lini (koma untuk multi)"),
) -> Dict[str, Any]:
    actor = await require_permission(request, "purchase_requisition", "view")
    ctx = await entity_ctx(request)
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if source:
        q["source"] = source
    q = resolve_list_scope("purchase_requisitions", q, ctx, entity_id)
    q = line_scope.narrow(q, actor, line, field=line_scope.LINES_FIELD)   # FASE L
    docs = await db.purchase_requisitions.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    # ringkas stat per status
    by_status: Dict[str, int] = {}
    for d in docs:
        by_status[d.get("status", "?")] = by_status.get(d.get("status", "?"), 0) + 1
    return {"items": docs, "total": len(docs), "by_status": by_status}


@router.get("/purchase-requisitions/reorder-suggestions")
async def reorder_suggestions(request: Request, entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Depth #2b — saran replenishment berbasis reorder_point produk."""
    await require_permission(request, "purchase_requisition", "view")
    ctx = await entity_ctx(request)
    return await svc.reorder_suggestions(entity_id=entity_id, ctx=ctx)


@router.get("/purchase-requisitions/eligible-suppliers")
async def eligible_suppliers(request: Request, product_ids: str = Query("")) -> Dict[str, Any]:
    """Supplier yang BOLEH dipilih untuk barang PR: punya kontrak aktif ATAU terdaftar di Barang Supplier."""
    await require_permission(request, "purchase_requisition", "view")
    pids = [p for p in product_ids.split(",") if p]
    by_product: Dict[str, List[str]] = {p: [] for p in pids}
    if pids:
        today = now_iso()[:10]
        async for c in db.supplier_contracts.find({"product_id": {"$in": pids}, "status": "active", "partner_kind": {"$in": ["supplier", None, ""]}},
                                                  {"_id": 0, "product_id": 1, "partner_id": 1, "valid_to": 1}):
            if not c.get("valid_to") or c["valid_to"] >= today:
                by_product.setdefault(c["product_id"], []).append(c["partner_id"])
        async for si in db.supplier_items.find({"product_id": {"$in": pids}, "status": "active"},
                                               {"_id": 0, "product_id": 1, "supplier_id": 1}):
            by_product.setdefault(si["product_id"], []).append(si["supplier_id"])
    by_product = {k: sorted(set(v)) for k, v in by_product.items()}
    sets = [set(v) for v in by_product.values()]
    common = sorted(set.intersection(*sets)) if sets else []
    return {"by_product": by_product, "common": common}


@router.post("/purchase-requisitions")
async def create_requisition(payload: PurchaseRequisitionCreate, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "purchase_requisition", "create")
    if not payload.items:
        raise HTTPException(status_code=400, detail="Minimal satu item kebutuhan")
    try:
        doc = await svc.create_requisition(payload, created_by=user.get("name", "Admin"),
                                           created_by_id=user.get("id", ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "pr_created", "purchase_requisition", doc["id"],
                {"number": doc["number"], "total": doc["total_est_amount"], "source": doc["source"]})
    return doc


@router.get("/purchase-requisitions/{pr_id}")
async def get_requisition(pr_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "purchase_requisition", "view")
    ctx = await entity_ctx(request)
    doc = safe_doc(await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0}))
    if not doc:
        raise HTTPException(status_code=404, detail="PR tidak ditemukan")
    assert_entity_access(doc, "purchase_requisitions", ctx)
    from services import special_order_link as _odl
    doc = await _odl.repair_pr_lines(doc) or doc
    from services.supplier_item_service import attach_line_aliases
    await attach_line_aliases(doc.get("items") or [], doc.get("preferred_supplier_id", ""))
    return doc


@router.patch("/purchase-requisitions/{pr_id}/lines/{line_no}")
async def update_line_qty(pr_id: str, line_no: int, payload: PRLineQtyIn,
                          request: Request) -> Dict[str, Any]:
    """AS-02 — naikkan qty beli baris PR (termasuk PR yang lahir dari SO)."""
    actor = await require_permission(request, "purchase_requisition", "create")
    ctx = await entity_ctx(request)
    doc = await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="PR tidak ditemukan")
    assert_entity_access(doc, "purchase_requisitions", ctx)
    try:
        updated = await svc.update_line_qty(pr_id, line_no, payload.quantity, payload.reason, actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "pr_line_qty_changed", "purchase_requisition", pr_id,
                {"line_no": line_no, "quantity": payload.quantity}, reason=payload.reason)
    return updated


@router.post("/purchase-requisitions/{pr_id}/submit")
async def submit_requisition(pr_id: str, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "purchase_requisition", "update")
    try:
        doc = await svc.submit_requisition(pr_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "pr_submitted", "purchase_requisition", pr_id, {"status": doc["status"]})
    return doc


@router.post("/purchase-requisitions/{pr_id}/approve")
async def approve_requisition(pr_id: str, request: Request,
                              payload: PurchaseRequisitionDecision = PurchaseRequisitionDecision()) -> Dict[str, Any]:
    await require_permission(request, "purchase_requisition", "approve")
    actor = await current_user(request)
    cur = safe_doc(await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0}))
    if not cur:
        raise HTTPException(status_code=404, detail="Purchase Requisition tidak ditemukan")
    # PS-20 (D-14) — matriks persetujuan divisi MENGIKAT untuk tahap PR.
    ev = await amx.guard("purchase_request", actor, cur, cur.get("entity_id", ""),
                         amount=cur.get("total_est_amount"), action="approve")
    try:
        doc = await svc.approve_requisition(pr_id, actor, notes=payload.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await amx.record(stage="purchase_request", action="approve", actor=actor, doc=cur,
                     entity_id=cur.get("entity_id", ""), level=ev.get("level", 1),
                     level_label=ev.get("level_label", ""), outcome="disetujui",
                     note=payload.notes or "", enforced=ev.get("enforced", True))
    await audit(actor.get("name", ""), "pr_approved", "purchase_requisition", pr_id, {"number": doc["number"]})
    return doc


@router.post("/purchase-requisitions/{pr_id}/reject")
async def reject_requisition(pr_id: str, request: Request,
                             payload: PurchaseRequisitionDecision = PurchaseRequisitionDecision()) -> Dict[str, Any]:
    await require_permission(request, "purchase_requisition", "reject")
    actor = await current_user(request)
    cur = safe_doc(await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0}))
    if not cur:
        raise HTTPException(status_code=404, detail="Purchase Requisition tidak ditemukan")
    ev = await amx.guard("purchase_request", actor, cur, cur.get("entity_id", ""),
                         amount=cur.get("total_est_amount"), action="reject")
    try:
        doc = await svc.reject_requisition(pr_id, actor, reason=payload.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await amx.record(stage="purchase_request", action="reject", actor=actor, doc=cur,
                     entity_id=cur.get("entity_id", ""), level=ev.get("level", 1),
                     level_label=ev.get("level_label", ""), outcome="ditolak",
                     note=payload.notes or "", enforced=ev.get("enforced", True))
    await audit(actor.get("name", ""), "pr_rejected", "purchase_requisition", pr_id, {"reason": payload.notes})
    return doc


@router.post("/purchase-requisitions/{pr_id}/cancel")
async def cancel_requisition(pr_id: str, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "purchase_requisition", "update")
    try:
        doc = await svc.cancel_requisition(pr_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "pr_cancelled", "purchase_requisition", pr_id, {})
    return doc


@router.post("/purchase-requisitions/{pr_id}/convert-to-po")
async def convert_to_po(pr_id: str, payload: PurchaseRequisitionConvert, request: Request) -> Dict[str, Any]:
    await require_permission(request, "purchase_order", "create")
    actor = await current_user(request)
    if payload.warehouse_id:   # E4.1 — gudang penerimaan PO hasil konversi PR
        from services import warehouse_scope_service as whscope
        await whscope.assert_usable(payload.warehouse_id,
                                   (await entity_ctx(request)).active_entity_id,
                                   action="menerima barang di sini",
                                   field_label="Gudang penerimaan")
    try:
        result = await svc.convert_to_po(
            pr_id, supplier_id=payload.supplier_id, actor=actor,
            warehouse_id=payload.warehouse_id, expected_delivery_date=payload.expected_delivery_date,
            notes=payload.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor.get("name", ""), "pr_converted_to_po", "purchase_requisition", pr_id,
                {"po_number": result["po"]["po_number"]})
    return result


# ═══════════════════════════════════════════════════════════════════════════
# FASE E — Sourcing: routing per baris + realisasi PR → PO / Order Makloon
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/purchase-requisitions/{pr_id}/sourcing")
async def pr_sourcing(pr_id: str, request: Request) -> Dict[str, Any]:
    """Ringkasan realisasi per baris + aksi yang tersedia (panel detail PR)."""
    await require_permission(request, "purchase_requisition", "view")
    ctx = await entity_ctx(request)
    doc = await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="PR tidak ditemukan")
    assert_entity_access(doc, "purchase_requisitions", ctx)
    try:
        return await src.sourcing_view(pr_id)
    except src.SourcingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/purchase-requisitions/{pr_id}/realize-po")
async def realize_po(pr_id: str, payload: PRRealizePoIn, request: Request) -> Dict[str, Any]:
    """Realisasi baris ber-mode `purchase` (boleh sebagian) menjadi satu PO."""
    await require_permission(request, "purchase_order", "create")
    actor = await current_user(request)
    if payload.warehouse_id:   # E4.1 — gudang penerimaan PO hasil realisasi PR
        from services import warehouse_scope_service as whscope
        await whscope.assert_usable(payload.warehouse_id,
                                   (await entity_ctx(request)).active_entity_id,
                                   action="menerima barang di sini",
                                   field_label="Gudang penerimaan")
    try:
        result = await src.realize_to_po(
            pr_id, supplier_id=payload.supplier_id, actor=actor,
            warehouse_id=payload.warehouse_id, line_nos=payload.line_nos,
            expected_delivery_date=payload.expected_delivery_date, notes=payload.notes)
    except src.SourcingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor.get("name", ""), "pr_realized_po", "purchase_requisition", pr_id,
                {"po_number": result["po"]["po_number"],
                 "realization": result["pr"].get("realization_status")})
    return result


@router.get("/purchase-requisitions/{pr_id}/makloon-prefill")
async def makloon_prefill(pr_id: str, request: Request, line_no: int = Query(...)) -> Dict[str, Any]:
    """Payload Wizard Makloon ter-prefill dari baris PR (1 klik dari PR)."""
    await require_permission(request, "makloon_order", "view")
    try:
        return await src.makloon_prefill(pr_id, line_no)
    except src.SourcingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/purchase-requisitions/{pr_id}/realize-makloon")
async def realize_makloon(pr_id: str, payload: PRRealizeMakloonIn,
                          request: Request) -> Dict[str, Any]:
    """Realisasi satu baris ber-mode `makloon` menjadi Order Makloon (draft)."""
    await require_permission(request, "makloon_order", "create")
    actor = await current_user(request)
    try:
        result = await src.realize_to_makloon(pr_id, payload.line_no, payload.payload, actor)
    except src.SourcingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor.get("name", ""), "pr_realized_makloon", "purchase_requisition", pr_id,
                {"mko_number": result["makloon_order"].get("mko_number"),
                 "line_no": payload.line_no})
    return result



@router.get("/material-reservations")
async def list_material_reservations(request: Request, ref_id: str = "", product_id: str = "",
                                     status: Optional[str] = None) -> List[Dict[str, Any]]:
    """W2-REQ-07 — reservasi bahan makloon (PR/MKO) dalam scope entitas."""
    await require_permission(request, "purchase_requisition", "view")
    from entity_scope import resolve_scope_ids
    from services import material_reservation_service as mres
    return await mres.list_reservations(resolve_scope_ids(await entity_ctx(request), None),
                                        ref_id, product_id, status)

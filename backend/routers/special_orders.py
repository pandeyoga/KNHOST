"""Special Orders Router - Sub-fase 1.12

Handles custom product orders (products not yet in catalog).
Status flow aligned with sales_orders for consistency.
"""
import json
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from db import db
from dependencies import require_permission, audit, current_user
from core_utils import new_id, now_iso, safe_doc
from entity_scope import entity_ctx, resolve_list_scope, assert_entity_access
from services.special_order_service import (
    generate_special_order_number,
    can_approve_special_order,
    approve_special_order,
    reject_special_order,
    transition_special_order_status,
    create_sku_from_special_order,
    APPROVAL_THRESHOLD
)
from services import purchase_requisition_service as pr_svc
from services import approval_matrix_service as amx  # PS-20 — PO Custom 2 tingkat (Manager → Direksi)
from services import special_order_routing as routing
from services import special_order_phase2 as p2
from services import special_order_items as so_items
from fastapi import UploadFile, File, Form
from fastapi.responses import Response
from services.rnd_spec_service import RndError
from schemas import (
    PurchaseRequisitionCreate, PurchaseRequisitionItem, SpecialOrderToPR,
    SalesOrderCreate, SalesOrderItemIn,
)
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api")


# ─── Schemas ─────────────────────────────────────────────────────────────────

class CustomItemSpec(BaseModel):
    """Custom item specification"""
    description: str = Field(..., description="Item description")
    specifications: Dict[str, Any] = Field(default_factory=dict, description="Custom specs (size, color, material, etc)")
    quantity: float = Field(..., gt=0, description="Quantity")
    unit: str = Field(..., description="Unit of measure")
    target_price: float = Field(..., ge=0, description="Target price per unit (IDR)")
    notes: str = Field(default="", description="Additional notes")


class SpecialOrderSpec(BaseModel):
    """Spesifikasi terstruktur (opsional bila pelanggan hanya memberi referensi)."""
    template_id: str = ""
    fabric_type: str = ""
    gramasi: Optional[float] = None
    lebar: Optional[float] = None
    color_id: str = ""
    color_new_note: str = ""
    sku_hint: str = ""
    notes: str = ""


class SpecialOrderItemIn(BaseModel):
    """L03 LN-030 — satu item Pesanan Khusus beserta sumber desainnya."""
    source_type: str
    description: str = ""
    request_types: list = Field(default_factory=list)
    source_template_id: str = ""
    source_product_id: str = ""
    source_design_id: str = ""
    color_id: str = ""
    quantity: float = Field(..., gt=0)
    unit: str = "meter"
    target_price: float = Field(default=0, ge=0)
    notes: str = ""


class RedesignBody(BaseModel):
    item_id: str = ""
    reason: str = Field(..., min_length=5)
    description: str = ""


class SpecialOrderCreate(BaseModel):
    """Create special order request"""
    customer_id: str = Field(..., description="Customer ID")
    title: str = ""
    request_types: list = Field(default_factory=list, description="printing | labdip | handfeel | proofing")
    detail_level: str = "reference"   # reference | full
    reference_notes: str = ""
    spec: Optional[SpecialOrderSpec] = None
    pattern_category_code: str = ""
    design_category_code: str = ""
    entity_id: str = Field(default="", description="Selling entity ID")
    custom_item: Optional[CustomItemSpec] = None
    items: list[SpecialOrderItemIn] = Field(default_factory=list)
    expected_delivery: str = Field(..., description="Expected delivery date (ISO format)")
    shipping_address_id: str = Field(default="", description="Shipping address ID")
    notes: str = Field(default="", description="Order notes")
    submit_for_approval: bool = Field(default=False, description="Auto-submit if needs approval")


class SpecialOrderApprove(BaseModel):
    """Approve special order"""
    notes: str = Field(default="", description="Approval notes")


class SpecialOrderReject(BaseModel):
    """Reject special order"""
    reason: str = Field(..., min_length=1, description="Rejection reason")


class SpecialOrderStatusUpdate(BaseModel):
    """Update special order status"""
    status: str = Field(..., description="New status")
    notes: str = Field(default="", description="Update notes")


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/special-orders")
async def list_special_orders(
    request: Request,
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    origin: Optional[str] = None
) -> Dict[str, Any]:
    """List special orders with optional filters.
    
    Query params:
    - status: Filter by status
    - customer_id: Filter by customer
    - entity_id: Filter by entity
    """
    await require_permission(request, "order", "view")
    ctx = await entity_ctx(request)
    
    query = {}
    if status:
        query["status"] = status
    if customer_id:
        query["customer_id"] = customer_id
    if origin == "redesign":
        query["origin"] = "redesign"
    elif origin == "special_order":
        query["origin"] = {"$ne": "redesign"}
    query = resolve_list_scope("special_orders", query, ctx, entity_id)
    
    special_orders = await db.special_orders.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    
    # Aggregate stats (ter-scope entitas, lepas dari filter status/customer)
    stats_match = resolve_list_scope("special_orders", {}, ctx, entity_id)
    pipeline = [
        {"$match": stats_match},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1},
            "total_amount": {"$sum": "$total_amount"}
        }}
    ]
    
    status_counts = {}
    async for doc in db.special_orders.aggregate(pipeline):
        status_counts[doc["_id"]] = {
            "count": doc["count"],
            "total_amount": doc["total_amount"]
        }
    
    return {
        "items": special_orders,
        "count": len(special_orders),
        "by_status": status_counts,
        "approval_threshold": APPROVAL_THRESHOLD
    }


@router.post("/special-orders")
async def create_special_order(payload: SpecialOrderCreate, request: Request) -> Dict[str, Any]:
    """Create new special order for custom product.
    
    Flow:
    1. Validate customer exists
    2. Calculate total amount
    3. Generate order number
    4. Check approval requirement (amount > threshold)
    5. Create order document
    6. Return created order
    """
    await require_permission(request, "order", "create")
    user = await current_user(request)
    ctx = await entity_ctx(request)
    
    # Validate customer
    customer = await db.customers.find_one({"id": payload.customer_id}, {"_id": 0})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer tidak ditemukan")
    
    # Get shipping address
    address = {}
    if payload.shipping_address_id:
        address = next(
            (a for a in customer.get("addresses", []) if a["id"] == payload.shipping_address_id),
            customer.get("addresses", [{}])[0] if customer.get("addresses") else {}
        )
    else:
        address = customer.get("addresses", [{}])[0] if customer.get("addresses") else {}
    
    entity_id = payload.entity_id or customer.get("entity_id") or ctx.active_entity_id
    items = []
    if payload.items:
        try:
            items = await so_items.build_items([i.model_dump() for i in payload.items], entity_id)
        except so_items.ItemError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        first = items[0]
        custom_item = {"description": payload.title.strip() or first["description"], "specifications": {},
                       "quantity": first["quantity"], "unit": first["unit"],
                       "target_price": first["target_price"], "notes": payload.notes}
        total_amount = round(sum(i["subtotal"] for i in items), 2)
        req_types = sorted({t for i in items for t in i["request_types"]})
    elif payload.custom_item:
        custom_item = payload.custom_item.model_dump()
        total_amount = payload.custom_item.target_price * payload.custom_item.quantity
        req_types = [t for t in payload.request_types if t in routing.REQUEST_TYPES]
    else:
        raise HTTPException(status_code=422, detail="Isi minimal satu item pesanan khusus.")
    
    # Generate order ID and number
    order_id = new_id("sord")
    order_number = await generate_special_order_number()
    
    # Determine initial status
    initial_status = "draft"
    if payload.submit_for_approval:
        initial_status = "pending_approval"   # OD selalu lewat persetujuan (routing ke Desainer/R&D terjadi saat disetujui)
    
    # Create special order document
    special_order = {
        "id": order_id,
        "number": order_number,
        "status": initial_status,
        "type": "special_order",
        "title": payload.title.strip() or custom_item["description"],
        "request_types": req_types,
        "items": items,
        "origin": "special_order", "redesign_of": {},
        "detail_level": payload.detail_level, "reference_notes": payload.reference_notes,
        "spec": payload.spec.model_dump() if payload.spec else {}, "references": [],
        "pattern_category_code": payload.pattern_category_code.strip().upper(),
        "design_category_code": payload.design_category_code.strip().upper(),
        
        # Customer info
        "customer_id": customer["id"],
        "customer_name": customer["name"],
        "customer_email": customer.get("email", ""),
        "customer_phone": customer.get("phone", ""),
        
        # Shipping
        "shipping_address": address,
        
        # Custom item
        "custom_item": custom_item,
        
        # Financial
        "total_amount": total_amount,
        "requires_approval": total_amount > APPROVAL_THRESHOLD,
        "approval_threshold": APPROVAL_THRESHOLD,
        
        # Timeline
        "expected_delivery": payload.expected_delivery,
        
        # Entity
        "entity_id": entity_id,
        
        # Notes
        "notes": payload.notes,
        
        # Status tracking
        "status_history": [{
            "status": initial_status,
            "timestamp": now_iso(),
            "user": user["email"]
        }],
        
        # Metadata
        "created_at": now_iso(),
        "created_by": user["email"],
        "updated_at": now_iso()
    }

    # PS-20 — cap rantai persetujuan sejak awal supaya pembuat dokumen langsung
    # melihat berapa tingkat yang dibutuhkan (Manager, dan Direksi bila nilainya besar).
    if initial_status == "pending_approval":
        # B1 DIBAYAR (2026-08-25) — KAPAN dokumen ini MULAI menunggu keputusan ditulis
        # di dokumen, bukan ditebak. Sebelum ini `AGING_META["special_order"].since`
        # menyebut `submitted_at`/`approval_requested_at` yang TIDAK PERNAH diisi
        # siapa pun, sehingga umur tunggu di Papan PO Custom & pengingat harian selalu
        # jatuh ke `created_at` — dokumen yang lama berstatus draf dilaporkan jauh
        # lebih tua daripada kenyataan, tanpa satu pun galat.
        special_order["approval_requested_at"] = now_iso()
        _chain, _cfg = await amx.special_order_chain(special_order,
                                                     special_order.get("entity_id", ""))
        special_order["approval_chain"] = _chain
        special_order["approval_level_current"] = (_chain[0]["level"] if _chain else 0)
        special_order["required_approval_role"] = (
            (_chain[0].get("roles") or ["manager"])[0] if _chain else "")
        special_order["approval_status"] = "pending"

    from services import line_scope as _lines            # FASE L
    await _lines.stamp_doc(db, special_order)
    await db.special_orders.insert_one(special_order)
    special_order.pop("_id", None)

    # FASE N butir 3 — PO CUSTOM YANG DIAJUKAN HARUS TERLIHAT. Terukur 2026-08-24:
    # 3 dokumen `special_orders` di data demo dan **0** notifikasi. Artinya pesanan
    # custom yang menunggu keputusan hanya ketahuan oleh orang yang kebetulan membuka
    # layarnya — padahal justru dokumen inilah yang paling mahal bila terlambat
    # (kain dipesan khusus, tidak bisa dijual ke pelanggan lain).
    # Alamatnya BUKAN "manager" yang diketik di sini, melainkan peran yang memang
    # diminta rantai persetujuan dokumen ini (`required_approval_role`, hasil
    # `approval_matrix_service.special_order_chain` — nilai besar bisa menuntut
    # Direksi). Ditambah pemegang `order.approve` supaya tidak pernah ada dokumen
    # menunggu tanpa satu pun penerima.
    #
    # A1 DIBAYAR (2026-08-25): pesannya TIDAK lagi disusun di sini. Judul, isi, tautan,
    # dan tingkat keparahan dulu diketik DUA KALI (di sini saat dokumen LAHIR, dan di
    # `notification_service._notify_pending_special_orders()` saat KEADAAN masih
    # menunggu) — dan keduanya sudah tidak identik: versi endpoint menyebut "Diajukan
    # oleh …", versi job tidak. Sekarang keduanya memanggil SATU penyusun pesan
    # (`notification_service.notify_special_order_waiting`), dan penjaga INV-NOTIF-02
    # aturan K3 melarang `notif_type="special_order_approval"` disusun di tempat lain.
    if initial_status == "pending_approval":
        try:
            from services.notification_service import notify_special_order_waiting
            await notify_special_order_waiting(special_order,
                                               actor_name=user.get("name", ""))
        except Exception:  # noqa: BLE001
            # Notifikasi TIDAK boleh menggagalkan pembuatan dokumen — pesanannya
            # sudah tersimpan dan sah; pemberitahuan adalah lapisan di atasnya.
            pass
    
    # Audit log
    await audit(
        user.get("name", ""),
        "special_order_created",
        "special_order",
        order_id,
        {"number": order_number, "customer_id": payload.customer_id, "total_amount": total_amount}
    )
    
    return special_order


@router.get("/special-orders/{order_id}")
async def get_special_order(order_id: str, request: Request) -> Dict[str, Any]:
    """Get special order detail by ID."""
    await require_permission(request, "order", "view")
    ctx = await entity_ctx(request)
    
    special_order = await db.special_orders.find_one({"id": order_id}, {"_id": 0})
    if not special_order:
        raise HTTPException(status_code=404, detail="Special order tidak ditemukan")
    assert_entity_access(special_order, "special_orders", ctx)
    special_order["chain"] = await routing.chain_of(special_order)
    return special_order


@router.post("/special-orders/{order_id}/references")
async def upload_od_reference(order_id: str, request: Request, file: UploadFile = File(...), caption: str = Form("")) -> Dict[str, Any]:
    """Referensi pelanggan (foto swatch / pattern / kain fisik) — ikut ke Permintaan Desain bila sudah lahir."""
    user = await require_permission(request, "order", "create")
    od = await db.special_orders.find_one({"id": order_id}, {"_id": 0})
    if not od:
        raise HTTPException(status_code=404, detail="Special order tidak ditemukan")
    data = await file.read()
    try:
        meta = await routing.add_reference(od, user.get("name", ""), file.filename or "referensi", file.content_type or "", data, caption)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return meta


@router.get("/special-orders/{order_id}/references/{file_id}")
async def get_od_reference(order_id: str, file_id: str, request: Request):
    await require_permission(request, "order", "view")
    od = await db.special_orders.find_one({"id": order_id}, {"_id": 0, "references": 1})
    if not od:
        raise HTTPException(status_code=404, detail="Special order tidak ditemukan")
    try:
        data, ctype, fname = await routing.reference_bytes(od, file_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=data, media_type=ctype, headers={"Cache-Control": "private, max-age=300"})


@router.post("/special-orders/{order_id}/route")
async def route_od_now(order_id: str, request: Request) -> Dict[str, Any]:
    """Jalankan/ulangi routing ke Desainer & R&D (untuk OD lama yang disetujui sebelum fitur ini)."""
    user = await require_permission(request, "order", "approve")
    od = await db.special_orders.find_one({"id": order_id}, {"_id": 0})
    if not od:
        raise HTTPException(status_code=404, detail="Special order tidak ditemukan")
    if od.get("status") in ("draft", "pending_approval", "cancelled"):
        raise HTTPException(status_code=400, detail="OD harus sudah disetujui sebelum diteruskan ke Desainer/R&D.")
    await routing.route_on_approve(od, user, od.get("entity_id", ""))
    fresh = safe_doc(await db.special_orders.find_one({"id": order_id}, {"_id": 0}))
    fresh["chain"] = await routing.chain_of(fresh)
    return fresh


class CustomerDecisionBody(BaseModel):
    decision: str
    note: str = ""
    decided_at: str = ""
    contact_name: str = ""


class LockPriceBody(BaseModel):
    margin_pct: Optional[float] = None
    item_margins: Dict[str, float] = Field(default_factory=dict)   # FE-01 — margin per item OD multi-item
    note: str = ""
    warehouse_id: str = ""
    auto_po: bool = True


class ProcureBody(BaseModel):
    warehouse_id: str = ""


async def _od_or_404(order_id: str, request: Request) -> Dict[str, Any]:
    ctx = await entity_ctx(request)
    od = await db.special_orders.find_one({"id": order_id}, {"_id": 0})
    if not od:
        raise HTTPException(status_code=404, detail="Special order tidak ditemukan")
    assert_entity_access(od, "special_orders", ctx)
    return od


async def _fresh(order_id: str) -> Dict[str, Any]:
    od = safe_doc(await db.special_orders.find_one({"id": order_id}, {"_id": 0}))
    od["chain"] = await routing.chain_of(od)
    return od


@router.post("/special-orders/{order_id}/submit")
async def submit_special_order(order_id: str, request: Request) -> Dict[str, Any]:
    """Ajukan OD draft ke persetujuan (Manager → Direksi bila nilai besar)."""
    user = await require_permission(request, "order", "create")
    od = await _od_or_404(order_id, request)
    if od.get("status") != "draft":
        raise HTTPException(status_code=400, detail="Hanya OD draft yang bisa diajukan.")
    chain, _cfg = await amx.special_order_chain(od, od.get("entity_id", ""))
    await db.special_orders.update_one({"id": order_id}, {
        "$set": {"status": "pending_approval", "approval_requested_at": now_iso(), "approval_chain": chain,
                 "approval_level_current": (chain[0]["level"] if chain else 0),
                 "required_approval_role": ((chain[0].get("roles") or ["manager"])[0] if chain else ""),
                 "approval_status": "pending", "updated_at": now_iso()},
        "$push": {"status_history": {"status": "pending_approval", "timestamp": now_iso(), "user": user.get("email", ""), "note": "Diajukan"}}})
    fresh = safe_doc(await db.special_orders.find_one({"id": order_id}, {"_id": 0}))
    try:
        from services.notification_service import notify_special_order_waiting
        await notify_special_order_waiting(fresh, actor_name=user.get("name", ""))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[submit_special_order] efek samping gagal diabaikan: %s", exc)  # KN-C10
    fresh["chain"] = await routing.chain_of(fresh)
    return fresh


@router.post("/special-orders/{order_id}/redesign")
async def redesign_special_order(order_id: str, payload: RedesignBody, request: Request) -> Dict[str, Any]:
    """L03 LN-030 — motif berubah = Special Order BARU berlabel redesign dengan tautan asal."""
    user = await require_permission(request, "order", "create")
    od = await _od_or_404(order_id, request)
    try:
        item, design = await so_items.artwork_of(od, payload.item_id)
    except so_items.ItemError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    dup = await db.special_orders.find_one(
        {"origin": "redesign", "redesign_of.special_order_id": od["id"],
         "redesign_of.item_id": item.get("id", ""), "status": {"$in": ["draft", "pending_approval"]}},
        {"_id": 0, "number": 1})
    if dup:
        raise HTTPException(status_code=409, detail=f"Redesign untuk item ini sudah diajukan: {dup['number']}.")
    new_item = {**{k: item.get(k) for k in ("quantity", "unit", "target_price", "color_id")},
                "id": new_id("soi"), "line_no": 1, "source_type": "redesign",
                "source_type_label": so_items.SOURCE_TYPES["redesign"],
                "description": payload.description.strip() or f"Redesign {design.get('code') or ''} — {item.get('description') or ''}".strip(),
                "request_types": ["printing"], "notes": payload.reason.strip(),
                "source_product_id": "", "source_template_id": "", "source_design_id": design["id"],
                "source_design_code": design.get("code", ""),
                "source_label": f"{design.get('code') or ''} {design.get('title') or ''}".strip(),
                "design_request_id": "", "sample_ids": []}
    new_item["quantity"] = float(new_item.get("quantity") or 1)
    new_item["unit"] = new_item.get("unit") or "meter"
    new_item["target_price"] = float(new_item.get("target_price") or 0)
    new_item["subtotal"] = round(new_item["quantity"] * new_item["target_price"], 2)
    number = await generate_special_order_number()
    doc = {
        "id": new_id("sord"), "number": number, "status": "draft", "type": "special_order",
        "title": new_item["description"], "request_types": ["printing"], "items": [new_item],
        "origin": "redesign",
        "redesign_of": {"special_order_id": od["id"], "number": od.get("number", ""), "item_id": item.get("id", ""),
                        "design_id": design["id"], "design_code": design.get("code", ""),
                        "reason": payload.reason.strip(), "by": user.get("name", ""), "at": now_iso()},
        "detail_level": od.get("detail_level", "reference"), "reference_notes": payload.reason.strip(),
        "spec": od.get("spec") or {}, "references": [],
        "pattern_category_code": od.get("pattern_category_code", ""), "design_category_code": od.get("design_category_code", ""),
        "customer_id": od.get("customer_id"), "customer_name": od.get("customer_name"),
        "customer_email": od.get("customer_email", ""), "customer_phone": od.get("customer_phone", ""),
        "shipping_address": od.get("shipping_address") or {},
        "custom_item": {"description": new_item["description"], "specifications": {}, "quantity": new_item["quantity"],
                        "unit": new_item["unit"], "target_price": new_item["target_price"], "notes": payload.reason.strip()},
        "total_amount": new_item["subtotal"], "requires_approval": new_item["subtotal"] > APPROVAL_THRESHOLD,
        "approval_threshold": APPROVAL_THRESHOLD, "expected_delivery": od.get("expected_delivery", ""),
        "entity_id": od.get("entity_id", ""), "notes": payload.reason.strip(),
        "status_history": [{"status": "draft", "timestamp": now_iso(), "user": user.get("email", ""),
                            "note": f"Redesign dari {od.get('number')} ({design.get('code') or ''})"}],
        "created_at": now_iso(), "created_by": user.get("email", ""), "updated_at": now_iso(),
    }
    from services import line_scope as _lines
    await _lines.stamp_doc(db, doc)
    await db.special_orders.insert_one(doc)
    doc.pop("_id", None)
    await db.special_orders.update_one({"id": od["id"]}, {
        "$push": {"redesigns": {"id": doc["id"], "number": number, "item_id": item.get("id", ""),
                                "design_code": design.get("code", ""), "at": now_iso()}},
        "$set": {"updated_at": now_iso()}})
    await audit(user.get("name", ""), "special_order_redesign", "special_order", doc["id"],
                {"from": od.get("number"), "design_id": design["id"]}, reason=payload.reason.strip())
    return doc



@router.post("/special-orders/{order_id}/customer-decision")
async def customer_decision(order_id: str, payload: CustomerDecisionBody, request: Request) -> Dict[str, Any]:
    """Fase 2 — ACC / revisi / tolak PELANGGAN atas sample (revisi → sample R&D baru otomatis)."""
    user = await require_permission(request, "order", "update")
    od = await _od_or_404(order_id, request)
    try:
        entry = await p2.customer_decide(od, payload.model_dump(), user, od.get("entity_id", ""))
    except p2.ODConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (p2.ODError, RndError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(user.get("name", ""), f"special_order_customer_{payload.decision}", "special_order", order_id,
                {"number": od.get("number"), "decision_id": entry["id"]}, reason=payload.note or "")
    return {"decision": entry, "special_order": await _fresh(order_id)}


@router.post("/special-orders/{order_id}/customer-decision/evidence")
async def customer_decision_evidence(order_id: str, request: Request, file: UploadFile = File(...),
                                     decision_id: str = Form(""), caption: str = Form("")) -> Dict[str, Any]:
    user = await require_permission(request, "order", "update")
    od = await _od_or_404(order_id, request)
    data = await file.read()
    try:
        meta = await p2.add_evidence(od, decision_id, user.get("name", ""), file.filename or "bukti", file.content_type or "", data, caption)
    except (p2.ODError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"evidence": meta, "special_order": await _fresh(order_id)}


@router.get("/special-orders/{order_id}/customer-decision/evidence/{file_id}")
async def customer_decision_evidence_file(order_id: str, file_id: str, request: Request):
    await require_permission(request, "order", "view")
    od = await _od_or_404(order_id, request)
    try:
        data, ctype = await p2.evidence_bytes(od, file_id)
    except (p2.ODError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=data, media_type=ctype, headers={"Cache-Control": "private, max-age=300"})


@router.get("/special-orders/{order_id}/pricing")
async def pricing_preview(order_id: str, request: Request, margin_pct: Optional[float] = None,
                          item_margins: str = "") -> Dict[str, Any]:
    """`item_margins` (FE-01, OD multi-item) = JSON {item_id: margin%}; item tanpa entri ikut `margin_pct`."""
    await require_permission(request, "order", "view")
    od = await _od_or_404(order_id, request)
    try:
        margins = json.loads(item_margins) if item_margins else {}
        if not isinstance(margins, dict):
            raise ValueError
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="item_margins harus objek JSON {item_id: margin}.") from exc
    try:
        return await p2.pricing_preview(od, margin_pct, margins)
    except p2.ODError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/special-orders/{order_id}/lock-price")
async def lock_price(order_id: str, payload: LockPriceBody, request: Request) -> Dict[str, Any]:
    """Fase 2 — harga final = kontrak supplier pemenang + margin → dikunci, OD Confirmed."""
    user = await require_permission(request, "order", "update")
    from role_registry import role_in
    # FE-04 — aturan peran pengunci tetap; peran kustom turunan Sales/Admin Sales/Manager dikenali (sama dengan UI).
    if not role_in(user.get("role"), ("sales", "sales_admin", "manager", "admin")):
        raise HTTPException(status_code=403, detail="Hanya Sales / manager / admin yang boleh mengunci harga final.")
    od = await _od_or_404(order_id, request)
    try:
        pricing = await p2.lock_price(od, payload.model_dump(), user)
    except p2.ODError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(user.get("name", ""), "special_order_price_locked", "special_order", order_id,
                {"number": od.get("number"), "final_unit_price": pricing["final_unit_price"], "margin_pct": pricing["margin_pct"],
                 "total": pricing.get("total"), "items": pricing.get("item_count")})
    # Fase 4 — SO hasil OD lahir otomatis (harga final) agar barang PO nanti langsung direservasi & Surat Jalan lahir.
    if payload.auto_po and pricing.get("procurement") and not pricing.get("procurement_error"):
        try:
            await convert_special_order_to_so(order_id, request)
        except HTTPException as exc:
            await db.special_orders.update_one({"id": order_id}, {"$set": {"shipping_error": f"SO otomatis gagal: {exc.detail}"}})
    return {"pricing": pricing, "special_order": await _fresh(order_id)}


@router.post("/special-orders/{order_id}/procure")
async def procure_now(order_id: str, payload: ProcureBody, request: Request) -> Dict[str, Any]:
    """Fase 3 — ulangi PR→PO otomatis ke supplier pemenang (bila saat kunci harga gagal / dimatikan)."""
    user = await require_permission(request, "purchase_requisition", "create")
    await require_permission(request, "od_fulfillment", "realize")   # L03 LN-033
    od = await _od_or_404(order_id, request)
    if payload.warehouse_id:   # E4.1 — gudang tujuan wajib boleh dipakai badan usaha OD
        from services import warehouse_scope_service as whscope
        await whscope.assert_usable(payload.warehouse_id, od.get("entity_id"), action="menerima PO special order")
    try:
        res = await p2.auto_procure(od, user, payload.warehouse_id)
    except (p2.ODError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"procurement": res, "special_order": await _fresh(order_id)}


class FulfillmentRouteBody(BaseModel):
    route: str
    reason: str = ""


class FulfillmentRealizeBody(BaseModel):
    warehouse_id: str = ""


def _ful_http(exc: Exception) -> HTTPException:
    from services import special_order_fulfillment as ful
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ful.FulfillmentConflict):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/special-orders/{order_id}/fulfillment")
async def fulfillment_view(order_id: str, request: Request) -> Dict[str, Any]:
    """L03 LN-033 — jalur & kemajuan pengadaan per item (PR/PO/MKO, bahan, qty diterima)."""
    user = await require_permission(request, "order", "view")
    od = await _od_or_404(order_id, request)
    from services import special_order_fulfillment as ful
    out = await ful.progress(od)
    out["can"] = {a: await ful._can(user, a) for a in ("choose_route", "override_default", "realize", "cancel")}  # noqa: SLF001
    return out


@router.post("/special-orders/{order_id}/fulfillment/{item_key}/route")
async def fulfillment_set_route(order_id: str, item_key: str, payload: FulfillmentRouteBody, request: Request) -> Dict[str, Any]:
    user = await current_user(request)
    od = await _od_or_404(order_id, request)
    from services import special_order_fulfillment as ful
    try:
        st = await ful.set_route(od, item_key, payload.route, payload.reason, user)
    except (ValueError, PermissionError) as exc:
        raise _ful_http(exc) from exc
    await audit(user.get("name", ""), "special_order_fulfillment_route", "special_order", order_id,
                {"item": item_key, "route": payload.route, "deviation": st.get("deviation"), "version": st.get("version")},
                reason=payload.reason)
    return {"state": st, "fulfillment": await ful.progress(await _fresh(order_id))}


@router.post("/special-orders/{order_id}/fulfillment/{item_key}/realize")
async def fulfillment_realize(order_id: str, item_key: str, payload: FulfillmentRealizeBody, request: Request) -> Dict[str, Any]:
    user = await current_user(request)
    od = await _od_or_404(order_id, request)
    from services import special_order_fulfillment as ful
    try:
        res = await ful.realize(od, item_key, user, payload.warehouse_id)
    except (ValueError, PermissionError) as exc:
        raise _ful_http(exc) from exc
    except HTTPException:
        raise
    await audit(user.get("name", ""), "special_order_fulfillment_realize", "special_order", order_id,
                {"item": item_key, **{k: v for k, v in res.items() if k in ("pr_number", "skipped", "status")},
                 "doc": (res.get("doc") or {}).get("number", "")})
    return {"result": res, "fulfillment": await ful.progress(await _fresh(order_id))}


class FulfillmentCancelBody(BaseModel):
    reason: str = Field(..., min_length=5, max_length=300)


@router.post("/special-orders/{order_id}/fulfillment/{item_key}/cancel")
async def fulfillment_cancel(order_id: str, item_key: str, payload: FulfillmentCancelBody, request: Request) -> Dict[str, Any]:
    """L03 LN-033 T08 — batalkan PO/MKO aktif satu item OD lewat aturan modul asal; histori tetap."""
    user = await current_user(request)
    od = await _od_or_404(order_id, request)
    from services import special_order_fulfillment as ful
    from services.makloon_order_service import cancel_order as cancel_mko
    from routers.purchase_orders_extra import cancel_purchase_order
    if not await ful._can(user, "cancel"):  # noqa: SLF001
        raise HTTPException(status_code=403, detail="Permission ditolak: od_fulfillment.cancel (membatalkan dokumen pengadaan OD).")
    try:
        n = ful._need((await ful.progress(od))["items"], item_key)  # noqa: SLF001
    except ValueError as exc:
        raise _ful_http(exc) from exc
    live = n["active_docs"]
    if not live:
        raise HTTPException(status_code=400, detail="Tidak ada PO/MKO aktif untuk item ini.")
    done = []
    for d in live:
        if d["type"] == "po" and float(d.get("received_qty") or 0) > 0:
            raise HTTPException(status_code=409, detail=f"{d.get('number') or d['id']} sudah ada penerimaan — gunakan amandemen/retur PO.")
        if d["type"] == "po":
            await cancel_purchase_order(d["id"], request)
        else:
            await cancel_mko(d["id"], reason=payload.reason, actor_name=user.get("name", ""))
        done.append(d.get("number") or d["id"])
    entry = {"at": now_iso(), "by": user.get("name", ""), "action": "cancel_docs", "docs": done, "reason": payload.reason}
    st = n["state"]
    # Sama dengan ganti jalur: dokumen batal diarsip, PR lama dipensiunkan → realisasi ulang membuat PR baru.
    archived = [{**d, "status": "cancelled" if (d.get("number") or d["id"]) in done else d.get("status"),
                 "archived_at": entry["at"], "cancel_reason": payload.reason} for d in n["docs"]]
    if st.get("pr_id"):
        archived.append({"type": "pr", "id": st["pr_id"], "number": st.get("pr_number", ""), "archived_at": entry["at"]})
    await db.special_orders.update_one({"id": order_id}, {
        "$push": {f"fulfillment.{item_key}.history": entry, f"fulfillment.{item_key}.history_docs": {"$each": archived}},
        "$set": {f"fulfillment.{item_key}.status": "planned", f"fulfillment.{item_key}.docs": [],
                 f"fulfillment.{item_key}.pr_id": "", f"fulfillment.{item_key}.pr_number": "",
                 f"fulfillment.{item_key}.error": "", "updated_at": now_iso()}})
    if st.get("pr_id"):
        await db.purchase_requisitions.update_one({"id": st["pr_id"]}, {"$set": {"source_item_key": f"{item_key}#retired"}})
        try:
            await pr_svc.cancel_requisition(st["pr_id"])
        except ValueError:
            pass   # PR sudah terminal (converted) — jejak tetap ada
    await audit(user.get("name", ""), "special_order_fulfillment_cancel", "special_order", order_id,
                {"item": item_key, "docs": done}, reason=payload.reason)
    return {"cancelled": done, "fulfillment": await ful.progress(await _fresh(order_id))}


@router.post("/special-orders/{order_id}/prepare-shipment")
async def prepare_shipment(order_id: str, request: Request) -> Dict[str, Any]:
    """Fase 4 — ulangi otomatisasi pengiriman: reservasi stok SO OD + tugas Surat Jalan."""
    user = await require_permission(request, "order", "update")
    await _od_or_404(order_id, request)
    try:
        res = await p2.on_goods_received(order_id)
    except p2.ODError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(user.get("name", ""), "special_order_prepare_shipment", "special_order", order_id, res)
    return {"result": res, "special_order": await _fresh(order_id)}


@router.post("/special-orders/{order_id}/unlock-price")
async def unlock_price(order_id: str, payload: SpecialOrderReject, request: Request) -> Dict[str, Any]:
    user = await require_permission(request, "order", "update")
    od = await _od_or_404(order_id, request)
    try:
        await p2.unlock_price(od, user, payload.reason)
    except p2.ODError as exc:
        raise HTTPException(status_code=400 if user.get("role") == "admin" else 403, detail=str(exc)) from exc
    await audit(user.get("name", ""), "special_order_price_unlocked", "special_order", order_id,
                {"number": od.get("number")}, reason=payload.reason)
    return await _fresh(order_id)


@router.post("/special-orders/{order_id}/approve")

async def approve_special_order_endpoint(
    order_id: str,
    payload: SpecialOrderApprove,
    request: Request
) -> Dict[str, Any]:
    """Approve special order (PO Custom) — PS-20: BERJENJANG sesuai matriks divisi.

    Tingkat 1 = Manager (admin juga boleh). Bila nilai pesanan ≥ ambang
    `approval.po_custom_direksi_min`, dibutuhkan tingkat 2 = **Direksi (admin)**.
    Transisi: pending_approval → (tingkat 2 menunggu) → confirmed.
    """
    await require_permission(request, "order", "approve")
    user = await current_user(request)

    special_order = safe_doc(await db.special_orders.find_one({"id": order_id}, {"_id": 0}))
    if not special_order:
        raise HTTPException(status_code=404, detail="Special order tidak ditemukan")

    if not await can_approve_special_order(special_order, user["role"]):
        raise HTTPException(
            status_code=403,
            detail="Hanya manager/admin yang dapat approve special order dengan status pending_approval"
        )

    entity_id = special_order.get("entity_id", "")
    chain, _cfg = await amx.special_order_chain(special_order, entity_id)
    level = amx.pending_level(chain)
    if level is None:
        raise HTTPException(status_code=409, detail="Semua tingkat persetujuan sudah terpenuhi.")
    # Matriks persetujuan divisi (peran per tingkat + pemisahan tugas) — MENGIKAT.
    ev = await amx.guard("po_custom", user, special_order, entity_id,
                         amount=special_order.get("total_amount"), level=level,
                         action="approve")

    # 2026-10 — admin menyetujui SEMUA tingkat sekaligus.
    for lv in ([l for l in chain if l.get("status") == "pending"] if amx.is_admin(user) else [level]):
        lv["status"] = "approved"
        lv["approved_by"] = user.get("name", "")
        lv["approved_by_id"] = user.get("id", "")
        lv["approved_at"] = now_iso()
    nxt = amx.pending_level(chain)

    if nxt is not None:
        # Masih butuh tingkat berikutnya (Direksi) → tetap menunggu persetujuan.
        # INV-ATOMIC-01 — CAS: tingkat berjalan harus masih seperti yang dibaca (dua penyetuju paralel → satu menang).
        _cas_res = await db.special_orders.find_one_and_update(
            {"status": "pending_approval", "id": order_id,
             "approval_level_current": special_order.get("approval_level_current", level["level"])},
            {"$set": {"approval_chain": chain,
                      "approval_level_current": nxt["level"],
                      "required_approval_role": (nxt.get("roles") or ["admin"])[0],
                      "updated_at": now_iso()},
             "$push": {"status_history": {
                 "status": "pending_approval",
                 "timestamp": now_iso(), "user": user.get("email", ""),
                 "note": (f"Disetujui tingkat {level['level']} ({level.get('label', '')}) — "
                          f"lanjut ke {nxt.get('label', '')}")}}})
        if not _cas_res:
            raise HTTPException(status_code=409, detail="Tingkat persetujuan sudah diputus pihak lain. Muat ulang.")
        await amx.record(stage="po_custom", action="approve", actor=user, doc=special_order,
                         entity_id=entity_id, level=level["level"],
                         level_label=level.get("label", ""),
                         outcome=f"disetujui tingkat {level['level']} — menunggu {nxt.get('label', '')}",
                         note=payload.notes or "", enforced=ev.get("enforced", True))
        await audit(user.get("name", ""), "special_order_approved_level", "special_order",
                    order_id, {"number": special_order.get("number"),
                               "level": level["level"], "next": nxt.get("label", "")},
                    reason=payload.notes or "")
        return await _fresh(order_id)

    try:
        updated = await approve_special_order(order_id, user["email"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db.special_orders.update_one(
        {"id": order_id},
        {"$set": {"approval_chain": chain, "approval_level_current": 0,
                  "approval_status": "approved"}})
    await amx.record(stage="po_custom", action="approve", actor=user, doc=special_order,
                     entity_id=entity_id, level=level["level"],
                     level_label=level.get("label", ""),
                     outcome=f"disetujui penuh ({len(chain)} tingkat)",
                     note=payload.notes or "", enforced=ev.get("enforced", True))
    await audit(user.get("name", ""), "special_order_approved", "special_order", order_id,
                {"number": special_order.get("number"), "levels": len(chain)},
                reason=payload.notes or "")
    fresh = safe_doc(await db.special_orders.find_one({"id": order_id}, {"_id": 0})) or updated
    # ROUTING: printing → Permintaan Desain; labdip/handfeel → Permintaan Sample R&D (spesifikasi diwarisi)
    await routing.route_on_approve(fresh, user, entity_id)
    return await _fresh(order_id)


@router.post("/special-orders/{order_id}/reject")

async def reject_special_order_endpoint(
    order_id: str,
    payload: SpecialOrderReject,
    request: Request
) -> Dict[str, Any]:
    """Reject special order (manager/admin only) — PS-20: dijaga matriks divisi.
    
    Transitions: pending_approval → cancelled
    """
    await require_permission(request, "order", "approve")
    user = await current_user(request)
    
    # Check if user can reject
    special_order = safe_doc(await db.special_orders.find_one({"id": order_id}, {"_id": 0}))
    if not special_order:
        raise HTTPException(status_code=404, detail="Special order tidak ditemukan")
    
    if not await can_approve_special_order(special_order, user["role"]):
        raise HTTPException(
            status_code=403,
            detail="Hanya manager/admin yang dapat reject special order dengan status pending_approval"
        )
    entity_id = special_order.get("entity_id", "")
    chain, _cfg = await amx.special_order_chain(special_order, entity_id)
    level = amx.pending_level(chain) or (chain[0] if chain else None)
    ev = await amx.guard("po_custom", user, special_order, entity_id,
                         amount=special_order.get("total_amount"), level=level,
                         action="reject")
    try:
        updated = await reject_special_order(order_id, user["email"], payload.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await amx.record(stage="po_custom", action="reject", actor=user, doc=special_order,
                     entity_id=entity_id, level=(level or {}).get("level", 1),
                     level_label=(level or {}).get("label", ""), outcome="ditolak",
                     note=payload.reason or "", enforced=ev.get("enforced", True))
    await audit(user.get("name", ""), "special_order_rejected", "special_order", order_id,
                {"number": special_order.get("number")}, reason=payload.reason or "")
    return updated


@router.post("/special-orders/{order_id}/status")

async def update_special_order_status(
    order_id: str,
    payload: SpecialOrderStatusUpdate,
    request: Request
) -> Dict[str, Any]:
    """Update special order status.
    
    Valid transitions:
    - confirmed → in_production (purchasing started)
    - in_production → ready (item produced/received)
    - ready → shipped (dispatched to customer)
    - shipped → done (delivered)
    """
    await require_permission(request, "order", "update")
    user = await current_user(request)
    
    try:
        updated = await transition_special_order_status(
            order_id,
            payload.status,
            user["email"]
        )
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/special-orders/{order_id}/create-pr")
async def create_pr_from_special_order(
    order_id: str,
    payload: SpecialOrderToPR,
    request: Request
) -> Dict[str, Any]:
    """Depth #2c — Jembatan Special Order → Purchase Requisition (pengadaan).

    Membuat PR (source=special_order) untuk item custom, lalu menggerakkan
    special order: confirmed → in_production (purchasing started).
    """
    await require_permission(request, "purchase_requisition", "create")
    user = await current_user(request)

    so = await db.special_orders.find_one({"id": order_id}, {"_id": 0})
    if not so:
        raise HTTPException(status_code=404, detail="Special order tidak ditemukan")
    if so.get("linked_pr_id"):
        raise HTTPException(status_code=400, detail=f"Special order sudah punya PR ({so.get('linked_pr_number')})")
    if so["status"] not in ("confirmed", "in_production"):
        raise HTTPException(status_code=400,
                            detail="PR hanya bisa dibuat untuk special order yang sudah confirmed")
    if so.get("request_types") and not (so.get("pricing") or {}).get("locked"):
        raise HTTPException(status_code=400, detail="Kunci harga final (ACC pelanggan + margin) dulu sebelum membuat PR ke supplier.")

    ci = so.get("custom_item", {})
    from services import special_order_link as _odl
    _pid = await _odl.resolve_product_id(so)
    if _pid:
        await _odl.ensure_exclusive(_pid, so)
        so["linked_product_id"] = _pid
    pr_price_locked = float((so.get("pricing") or {}).get("cost_price") or 0)
    if payload.warehouse_id:   # E4.1 — gudang tujuan pengadaan harus boleh dipakai
        from services import warehouse_scope_service as whscope
        await whscope.assert_usable(payload.warehouse_id, so.get("entity_id", ""),
                                   action="menerima barang di sini",
                                   field_label="Gudang tujuan")
    est_price = payload.est_price if payload.est_price > 0 else (pr_price_locked or float(ci.get("target_price", 0) or 0))
    # L03 LN-033 — PR manual memakai layanan routing yang sama (jalur per item: purchase/makloon).
    from services import special_order_fulfillment as ful
    rows = await ful.needs(so)
    for n in rows:
        if n["product_id"] and not n["effective_route"]:
            raise HTTPException(status_code=400, detail=f"Item {n['line_no']}: pilih jalur pemenuhan (supplier/makloon) dulu di panel Pemenuhan.")
        if not n["product_id"] and n["effective_route"] == "makloon":
            raise HTTPException(status_code=400, detail=f"Item {n['line_no']}: jalur makloon butuh SKU hasil di katalog.")
    wh_pr = payload.warehouse_id or await p2.default_warehouse_id(so.get("entity_id", ""))
    from services import atomic_claim as _saga
    await _saga.claim("special_orders", order_id, "special_order_create_pr",
                      precondition={"linked_pr_id": {"$in": [None, ""]}}, actor=user.get("name", ""))
    prs = []
    try:
        for n in rows:
            if not n["product_id"]:   # item non-katalog lama: deskripsi saja, hanya bisa dibeli
                n = {**n, "description": ci.get("description") or n["description"] or f"Custom item {so.get('number')}"}
            prs.append(await ful.ensure_pr(so, n, n["effective_route"] or "purchase", user, wh_pr,
                                           submit_now=payload.submit_now, est_price=est_price if len(rows) == 1 else 0,
                                           notes=payload.notes, needed_by=payload.needed_by_date))
    except ValueError as e:
        if not prs:
            await _saga.release("special_orders", order_id)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        if not prs:
            await _saga.release("special_orders", order_id)
        raise
    pr = prs[0]
    await db.special_orders.update_one({"id": order_id}, _saga.finish_set({
        "linked_pr_id": pr["id"], "linked_pr_number": pr["number"], "updated_at": now_iso()}))

    # Gerakkan ke in_production (purchasing started) bila masih confirmed
    if so["status"] == "confirmed":
        try:
            await transition_special_order_status(order_id, "in_production", user["email"])
        except ValueError as exc:
            logger.warning("[create_pr_from_special_order] efek samping gagal diabaikan: %s", exc)  # KN-C10

    await audit(user.get("name", ""), "special_order_pr_created", "special_order", order_id,
                {"pr_number": pr["number"], "pr_id": pr["id"], "pr_numbers": [x["number"] for x in prs]})

    so_updated = await db.special_orders.find_one({"id": order_id}, {"_id": 0})
    return {"pr": pr, "special_order": safe_doc(so_updated)}


@router.post("/special-orders/{order_id}/create-sku")
async def create_sku_endpoint(order_id: str, request: Request) -> Dict[str, Any]:
    """F3 (2.a) — Materialisasi Product SKU dari Special Order MTO (idempotent).

    Otomatis dijalankan saat approve; endpoint ini adalah fallback manual
    (mis. special order lama yang dibuat sebelum fitur auto-create).
    """
    await require_permission(request, "order", "approve")
    user = await current_user(request)
    ctx = await entity_ctx(request)

    so = await db.special_orders.find_one({"id": order_id}, {"_id": 0})
    if not so:
        raise HTTPException(status_code=404, detail="Special order tidak ditemukan")
    assert_entity_access(so, "special_orders", ctx)

    try:
        product = await create_sku_from_special_order(
            order_id, created_by=user.get("email", user.get("name", "system")))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    await audit(user.get("name", ""), "special_order_sku_created", "special_order", order_id,
                {"product_id": product["id"], "sku": product["sku"]})
    so_updated = await db.special_orders.find_one({"id": order_id}, {"_id": 0})
    return {"product": product, "special_order": safe_doc(so_updated)}


@router.post("/special-orders/{order_id}/convert-to-so")
async def convert_special_order_to_so(order_id: str, request: Request) -> Dict[str, Any]:
    """F3 — Konversi Special Order (MTO) menjadi Sales Order standar.

    Menutup loop MTO: produk custom yang sudah punya SKU dimasukkan ke jalur
    fulfillment standar. Reuse penuh logika `create_order` (pricing/reservasi/
    credit gate). `allow_backorder=True` agar tidak gagal bila stok MTO belum
    tersedia. Idempotent: tolak bila sudah pernah dikonversi.
    """
    await require_permission(request, "order", "create")
    user = await current_user(request)
    ctx = await entity_ctx(request)

    so = await db.special_orders.find_one({"id": order_id}, {"_id": 0})
    if not so:
        raise HTTPException(status_code=404, detail="Special order tidak ditemukan")
    assert_entity_access(so, "special_orders", ctx)

    if so.get("linked_sales_order_id"):
        raise HTTPException(
            status_code=400,
            detail=f"Special order sudah dikonversi ke SO {so.get('linked_sales_order_number')}")
    if so.get("status") not in ("confirmed", "in_production", "ready"):
        raise HTTPException(
            status_code=400,
            detail="Konversi hanya untuk special order yang sudah disetujui (confirmed/in_production/ready).")
    if (so.get("request_types") or p2.is_multi_item(so)) and not (so.get("pricing") or {}).get("locked"):
        raise HTTPException(status_code=400, detail="Kunci harga final (ACC pelanggan + margin) dulu sebelum konversi ke SO.")

    # FE-01 — retry sesudah SO sempat lahir (mis. gagal sebelum tautan tersimpan): pakai SO yang sama, jangan buat lagi.
    prior = await db.sales_orders.find_one({"source_special_order_id": order_id, "status": {"$ne": "cancelled"}},
                                           {"_id": 0, "id": 1, "number": 1})
    if prior:
        await db.special_orders.update_one({"id": order_id, "linked_sales_order_id": {"$in": [None, ""]}}, {"$set": {
            "linked_sales_order_id": prior["id"], "linked_sales_order_number": prior["number"], "updated_at": now_iso()}})
        return {"special_order": safe_doc(await db.special_orders.find_one({"id": order_id}, {"_id": 0})),
                "sales_order": safe_doc(await db.sales_orders.find_one({"id": prior["id"]}, {"_id": 0})), "reused": True}

    if p2.is_multi_item(so):
        # FE-01 — setiap item membawa produk hasil, qty/satuan & harga terkunci-nya sendiri; tidak dilebur ke header.
        pr = so.get("pricing") or {}
        if pr.get("mode") != "items":
            raise HTTPException(status_code=409, detail="Harga Pesanan Khusus multi-item ini dikunci dengan format lama "
                                                        "(satu produk) — minta admin membuka kunci lalu kunci ulang agar semua item ikut ke SO.")
        lines = sorted(pr.get("items") or [], key=lambda ln: ln.get("line_no") or 0)
        if {ln.get("item_id") for ln in lines} != {i["id"] for i in so.get("items") or []} or any(not ln.get("product_id") for ln in lines):
            raise HTTPException(status_code=409, detail="Rincian harga terkunci tidak sama dengan item Pesanan Khusus — "
                                                        "buka kunci lalu kunci ulang harga.")
        so_items = [SalesOrderItemIn(product_id=ln["product_id"], quantity=float(ln["quantity"]), unit=ln["unit"],
                                     special_order_item_id=ln["item_id"]) for ln in lines]
    else:
        # Pastikan SKU sudah ada (auto-create bila belum — mis. order lama sebelum fitur 2.a).
        # OD terstruktur: SKU eksklusif hasil R&D (pricing.product_id) MENANG atas SKU ad hoc lama.
        _pp = (so.get("pricing") or {}).get("product_id")
        if _pp and so.get("linked_product_id") != _pp:
            await db.special_orders.update_one({"id": order_id}, {"$set": {"linked_product_id": _pp, "linked_product_sku": so["pricing"].get("product_sku", "")}})
            so = await db.special_orders.find_one({"id": order_id}, {"_id": 0})
        if not so.get("linked_product_id"):
            try:
                await create_sku_from_special_order(
                    order_id, created_by=user.get("email", "system"))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            so = await db.special_orders.find_one({"id": order_id}, {"_id": 0})
        ci = so.get("custom_item", {}) or {}
        so_items = [SalesOrderItemIn(
            product_id=so["linked_product_id"],
            quantity=float(ci.get("quantity", 1) or 1),
            unit=ci.get("unit", "meter"),
        )]

    addr = so.get("shipping_address", {}) or {}
    so_payload = SalesOrderCreate(
        customer_id=so["customer_id"],
        shipping_address_id=addr.get("id", ""),
        items=so_items,
        entity_id=so.get("entity_id", ""),
        allow_backorder=True,         # MTO: stok mungkin belum tersedia → backorder
        confirm_mixed_lot=True,       # item custom (per baris) — lewati gate mixed-lot
        source_special_order_id=order_id,
        sales_name=so.get("created_by", "Sales"),
    )

    # Klaim atomik SESUDAH semua validasi: special_orders (belum tertaut SO) sebelum SO lahir.
    # Klik ganda / balapan → 409, bukan dua SO dari satu pesanan khusus.
    from services import atomic_claim as _saga
    await _saga.claim("special_orders", order_id, "special_order_convert_to_so",
                      precondition={"linked_sales_order_id": {"$in": [None, ""]}},
                      actor=user.get("name", ""))
    # Reuse penuh create_order (local import → hindari circular import).
    from routers.sales_orders import create_order as _create_sales_order
    try:
        sales_order = await _create_sales_order(so_payload, request)
    except Exception:
        await _saga.release("special_orders", order_id)   # SO belum lahir → aman dilepas
        raise

    await db.special_orders.update_one(
        {"id": order_id},
        _saga.finish_set({
            "linked_sales_order_id": sales_order["id"],
            "linked_sales_order_number": sales_order["number"],
            "converted_at": now_iso(),
            "converted_by": user.get("email", user.get("name", "")),
            "updated_at": now_iso(),
        }))
    await audit(user.get("name", ""), "special_order_converted_to_so", "special_order", order_id,
                {"so_id": sales_order["id"], "so_number": sales_order["number"]})

    so_updated = await db.special_orders.find_one({"id": order_id}, {"_id": 0})
    return {"special_order": safe_doc(so_updated), "sales_order": sales_order}


@router.patch("/special-orders/{order_id}")

async def patch_special_order(
    order_id: str,
    payload: Dict[str, Any],
    request: Request
) -> Dict[str, Any]:
    """Partial update special order (draft only).
    
    Allowed fields: notes, expected_delivery, custom_item fields
    """
    await require_permission(request, "order", "update")
    user = await current_user(request)
    
    ctx = await entity_ctx(request)
    special_order = await db.special_orders.find_one({"id": order_id}, {"_id": 0})
    if not special_order:
        raise HTTPException(status_code=404, detail="Special order tidak ditemukan")
    assert_entity_access(special_order, "special_orders", ctx)  # S#074 IDOR
    if special_order["status"] != "draft":
        raise HTTPException(
            status_code=400,
            detail="Hanya special order dengan status draft yang dapat diedit"
        )
    
    # Allowed updates
    allowed_fields = ["notes", "expected_delivery"]
    updates = {k: v for k, v in payload.items() if k in allowed_fields}
    
    if not updates:
        raise HTTPException(status_code=400, detail="Tidak ada field yang dapat diupdate")
    
    updates["updated_at"] = now_iso()
    updates["updated_by"] = user["email"]
    
    result = await db.special_orders.find_one_and_update(
        {"id": order_id},
        {"$set": updates},
        return_document=True
    )
    
    result.pop("_id", None)
    return result


@router.delete("/special-orders/{order_id}")

async def delete_special_order(
    order_id: str,
    request: Request
) -> Dict[str, Any]:
    """Soft delete special order (draft only)."""
    await require_permission(request, "order", "delete")
    user = await current_user(request)
    
    special_order = await db.special_orders.find_one({"id": order_id}, {"_id": 0})
    if not special_order:
        raise HTTPException(status_code=404, detail="Special order tidak ditemukan")
    
    if special_order["status"] != "draft":
        raise HTTPException(
            status_code=400,
            detail="Hanya special order dengan status draft yang dapat dihapus"
        )
    
    result = await db.special_orders.find_one_and_update(
        {"id": order_id},
        {
            "$set": {
                "status": "cancelled",
                "cancelled_at": now_iso(),
                "cancelled_by": user["email"],
                "updated_at": now_iso()
            }
        },
        return_document=True
    )
    
    result.pop("_id", None)
    return result

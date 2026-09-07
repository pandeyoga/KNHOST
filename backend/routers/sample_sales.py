"""§3-C Jual Sampel — router: master harga sampel per induk, permintaan (sales), potong (gudang)."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from core_utils import now_iso, safe_doc
from db import db
from dependencies import audit, require_permission
from entity_scope import assert_active_entity_access, entity_ctx, resolve_list_scope, resolve_scope_ids
from services import sample_sale_service as svc

router = APIRouter(prefix="/api")


class SamplePriceIn(BaseModel):
    price_per_unit: float = Field(..., ge=0)


class SampleRequestIn(BaseModel):
    customer_id: str
    product_id: str
    length: float = Field(..., gt=0)
    payment_method: str = "cash"
    notes: str = ""
    entity_id: str = ""


class SampleCutIn(BaseModel):
    roll_id: str = ""
    epc: str = ""
    reason: str = ""


class SampleCancelIn(BaseModel):
    reason: str = ""


@router.get("/sample-prices")
async def list_sample_prices(request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "product", "view")
    tpls = await db.product_templates.find({}, {"_id": 0, "id": 1, "name": 1, "base_unit": 1, "base_price": 1}).to_list(2000)
    masters = {m["template_id"]: m for m in await db.sample_price_master.find({}, {"_id": 0}).to_list(2000)}
    return [{"template_id": t["id"], "template_name": t.get("name"), "unit": t.get("base_unit") or "yard",
             "list_price": float(t.get("base_price") or 0),
             "price_per_unit": float((masters.get(t["id"]) or {}).get("price_per_unit") or 0),
             "updated_at": (masters.get(t["id"]) or {}).get("updated_at")} for t in tpls]


@router.put("/sample-prices/{template_id}")
async def put_sample_price(template_id: str, payload: SamplePriceIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "update")
    if not await db.product_templates.find_one({"id": template_id}, {"_id": 0, "id": 1}):
        raise HTTPException(status_code=404, detail="Induk produk tidak ditemukan")
    doc = {"template_id": template_id, "price_per_unit": float(payload.price_per_unit),
           "updated_at": now_iso(), "updated_by": actor.get("name", "")}
    await db.sample_price_master.update_one({"template_id": template_id}, {"$set": doc}, upsert=True)
    await audit(actor.get("name", ""), "sample_price_set", "sample_price_master", template_id, doc)
    return doc


@router.get("/sample-requests/quote")
async def sample_quote(request: Request, product_id: str, length: float) -> Dict[str, Any]:
    await require_permission(request, "order", "view")
    ctx = await entity_ctx(request)
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    price = await svc.sample_price_for(product)
    sug = await svc.suggest_roll(product_id, float(length), resolve_scope_ids(ctx, None))
    return {**price, "length": length, "amount": round(float(length) * price["price_per_unit"], 2),
            "suggested_roll": {k: sug.get(k) for k in ("id", "roll_no", "warehouse_id", "length_remaining", "rfid_tag_id")} if sug else None}


@router.get("/sample-requests")
async def list_sample_requests(request: Request, status: Optional[str] = None, entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
    await require_permission(request, "order", "view")
    ctx = await entity_ctx(request)
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    q = resolve_list_scope("sample_requests", q, ctx, entity_id)
    return await db.sample_requests.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)


@router.post("/sample-requests")
async def create_sample_request(payload: SampleRequestIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "order", "create")
    ctx = await entity_ctx(request)
    req = await svc.create_request(payload.model_dump(), actor, resolve_scope_ids(ctx, None))
    await audit(actor.get("name", ""), "sample_requested", "sample_request", req["id"], {"number": req["number"], "amount": req["amount"]})
    return req


@router.get("/sample-requests/{request_id}")
async def get_sample_request(request_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "order", "view")
    doc = await db.sample_requests.find_one({"id": request_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Permintaan sampel tidak ditemukan")
    # R-3a — detail SEKETAT daftarnya: dokumen harus milik badan usaha aktif (pola T3).
    assert_active_entity_access(doc, "sample_requests", await entity_ctx(request))
    return safe_doc(doc)


@router.post("/sample-requests/{request_id}/cut")
async def cut_sample_request(request_id: str, payload: SampleCutIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "scan")
    res = await svc.cut_sample(request_id, payload.model_dump(), actor)
    await audit(actor.get("name", ""), "sample_cut", "sample_request", request_id,
                {"roll": res.get("cut_roll_no"), "child": res.get("child_roll_no"), "so": res.get("sales_order_number"), "receipt": res.get("receipt_number")})
    return res


@router.post("/sample-requests/{request_id}/cancel")
async def cancel_sample_request(request_id: str, payload: SampleCancelIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "order", "update")
    # T-01 (pola CAS) — berprasyarat status requested: dua pembatalan bersamaan → satu 200, satu 409.
    upd = await db.sample_requests.find_one_and_update(
        {"id": request_id, "status": "requested"},
        {"$set": {"status": "cancelled", "cancel_reason": payload.reason, "cancelled_by": actor.get("name", ""), "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not upd:
        raise HTTPException(status_code=409, detail="Permintaan sampel tidak bisa dibatalkan (sudah dipotong / dibatalkan)")
    await db.wms_tasks.update_one({"id": upd.get("wms_task_id")}, {"$set": {"status": "cancelled", "updated_at": now_iso()}})
    return safe_doc(upd)

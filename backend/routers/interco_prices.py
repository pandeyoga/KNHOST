"""2026-10 — HARGA INTERNAL antar-PT: isi massal, ringkasan kekurangan, dan permintaan harga."""
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from dependencies import audit, current_user, has_permission, require_permission
from services import interco_price_service as ips

router = APIRouter(prefix="/api")


class PriceItemIn(BaseModel):
    product_id: str
    unit_price: float


class BulkIn(BaseModel):
    seller_entity_id: str
    buyer_entity_id: str
    valid_from: str = ""
    notes: str = ""
    items: List[PriceItemIn]


class RequestIn(BaseModel):
    seller_entity_id: str
    buyer_entity_id: str
    product_id: str
    order_id: str = ""
    note: str = ""


@router.get("/interco/prices/access")
async def price_access(request: Request) -> Dict[str, Any]:
    actor = await current_user(request)
    return {"can_view": await has_permission(actor, "interco_price", "view"),
            "can_set": await has_permission(actor, "interco_price", "set")}


@router.get("/interco/prices/summary")
async def price_summary(request: Request) -> Dict[str, Any]:
    await require_permission(request, "interco_price", "view")
    return await ips.summary()


@router.get("/interco/prices/missing")
async def price_missing(request: Request, seller_entity_id: str, buyer_entity_id: str,
                        q: str = "", only_stock: bool = True) -> Dict[str, Any]:
    await require_permission(request, "interco_price", "view")
    try:
        return await ips.missing(seller_entity_id, buyer_entity_id, q, only_stock)
    except ips.InternalPriceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/interco/prices/bulk")
async def price_bulk(payload: BulkIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "interco_price", "set")
    try:
        res = await ips.bulk_set(payload.seller_entity_id, payload.buyer_entity_id,
                                 [i.model_dump() for i in payload.items], actor,
                                 valid_from=payload.valid_from, notes=payload.notes)
    except ips.InternalPriceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "interco_price_set", "supplier_contracts", payload.seller_entity_id,
                {"buyer": payload.buyer_entity_id, "count": res["count"],
                 "contracts": [c["contract_number"] for c in res["created"]][:50]})
    return res


@router.post("/interco/prices/request")
async def price_request(payload: RequestIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "order", "confirm")
    return await ips.request_price(payload.seller_entity_id, payload.buyer_entity_id, payload.product_id,
                                   actor, order_id=payload.order_id, note=payload.note)

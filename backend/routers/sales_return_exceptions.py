"""LN-083/LN-092 — pengecualian retur, cutloss (qty cacat QC) & diskon (nilai diputus Finance)."""
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from db import db
from dependencies import audit, require_permission
from entity_scope import assert_entity_access, entity_ctx
from services import return_exception_service as rex
from services import return_compensation_service as comp
from services import return_settlement_policy as rsp

router = APIRouter(prefix="/api", tags=["sales-return-exceptions"])


class ExceptionIn(BaseModel):
    kind: str
    reason: str
    attachment_ids: List[str] = Field(default_factory=list)


class DecideIn(BaseModel):
    approve: bool
    note: str = ""


async def _ret(return_id: str, request: Request) -> Dict[str, Any]:
    doc = await db.sales_returns.find_one({"id": return_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Retur tidak ditemukan")
    assert_entity_access(doc, "sales_returns", await entity_ctx(request))
    return doc


@router.post("/sales-returns/{return_id}/exceptions")
async def request_exception(return_id: str, payload: ExceptionIn, request: Request) -> Any:
    user = await require_permission(request, "sales_return", "update")
    ret = await _ret(return_id, request)
    try:
        exc = await rex.request(ret, payload.kind, payload.reason, payload.attachment_ids, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "sales_return_exception_requested", "sales_return", return_id,
                {"kind": payload.kind, "reason": payload.reason, "attachments": exc["attachment_ids"]})
    return exc


@router.post("/sales-returns/{return_id}/exceptions/{exc_id}/decide")
async def decide_exception(return_id: str, exc_id: str, payload: DecideIn, request: Request) -> Any:
    user = await require_permission(request, "sales_return", "approve")
    ret = await _ret(return_id, request)
    try:
        exc = await rex.decide(ret, exc_id, payload.approve, payload.note, user)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "sales_return_exception_decided", "sales_return", return_id,
                {"exception_id": exc_id, "approve": payload.approve, "note": payload.note})
    return exc


class CutlossIn(BaseModel):
    roll_length: float = Field(..., gt=0)
    defect_from: float = Field(..., gt=0)
    defect_to: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)


class DiscountIn(BaseModel):
    qty_affected: float = Field(..., gt=0)
    amount: float = Field(..., gt=0)


class CutlossRecordIn(BaseModel):
    product_id: str
    defect_yard: float = Field(..., gt=0)
    roll_id: str = ""
    note: str = ""


class CompLine(BaseModel):
    kind: str
    product_id: str
    qty: float = 0
    amount: float = 0
    evidence_ids: List[str] = Field(default_factory=list)


class CompensationIn(BaseModel):
    lines: List[CompLine]
    note: str = ""


@router.post("/sales-returns/{return_id}/cutloss")
async def record_cutloss(return_id: str, payload: CutlossRecordIn, request: Request) -> Any:
    user = await require_permission(request, "sales_return", "record_cutloss")
    ret = await _ret(return_id, request)
    try:
        out = await comp.record_cutloss(ret, payload.product_id, payload.defect_yard, payload.roll_id, payload.note, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "sales_return_cutloss_recorded", "sales_return", return_id, out)
    return out


@router.get("/sales-returns/{return_id}/compensation")
async def get_compensation(return_id: str, request: Request) -> Any:
    await require_permission(request, "sales_return", "view")
    return await comp.preview(await _ret(return_id, request))


@router.post("/sales-returns/{return_id}/compensation")
async def decide_compensation(return_id: str, payload: CompensationIn, request: Request) -> Any:
    user = await require_permission(request, "sales_return", "decide_compensation")
    ret = await _ret(return_id, request)
    try:
        out = await comp.decide(ret, [x.dict() for x in payload.lines], payload.note, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "sales_return_compensation_decided", "sales_return", return_id,
                {"total": out["total"], "lines": out["lines"], "note": out["note"]})
    return out


@router.delete("/sales-returns/{return_id}/compensation")
async def revoke_compensation(return_id: str, request: Request) -> Any:
    user = await require_permission(request, "sales_return", "decide_compensation")
    ret = await _ret(return_id, request)
    try:
        await comp.revoke(ret, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "sales_return_compensation_revoked", "sales_return", return_id, {})
    return {"ok": True}


@router.post("/sales-returns/cutloss/simulate")
async def simulate_cutloss(payload: CutlossIn, request: Request) -> Any:
    await require_permission(request, "sales_return", "view")
    ctx = await entity_ctx(request)
    try:
        return await rsp.simulate_cutloss(payload.dict(), ctx.active_entity_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/sales-returns/discount/simulate")
async def simulate_discount(payload: DiscountIn, request: Request) -> Any:
    await require_permission(request, "sales_return", "view")
    ctx = await entity_ctx(request)
    return await rsp.simulate_discount(payload.dict(), ctx.active_entity_id)

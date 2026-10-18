"""LN-093 tujuan barang retur berantai + LN-091-T02 kerugian turun grade."""
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from db import db
from dependencies import audit, require_permission
from entity_scope import entity_ctx
from services import interco_return_service as icret
from services import return_disposition_service as rds
from services import return_grade_impairment as rgi

router = APIRouter(prefix="/api", tags=["sales-return-disposition"])


class DecisionIn(BaseModel):
    roll_ids: List[str] = Field(default_factory=list)
    decision: str
    reason: str = ""
    attachment_ids: List[str] = Field(default_factory=list)


async def _ret(return_id: str, request: Request, owner_ids: List[str] = None) -> Dict[str, Any]:
    """Pihak retur pelanggan ATAU PT pemilik roll (CST) boleh membaca/memutuskan."""
    doc = await db.sales_returns.find_one({"id": return_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Retur tidak ditemukan")
    ctx = await entity_ctx(request)
    allowed = set(ctx.allowed_entity_ids)
    if doc.get("entity_id") in allowed:
        return doc
    owners = set(owner_ids or []) or {r["owner_entity_id"] for r in await db.inventory_rolls.find(
        {"return_id": return_id}, {"_id": 0, "owner_entity_id": 1}).to_list(1000) if r.get("owner_entity_id")}
    if owners & allowed:
        return doc
    raise HTTPException(status_code=404, detail="Data tidak ditemukan untuk entitas ini")


async def _assert_owner(request: Request, roll_ids: List[str]) -> None:
    ctx = await entity_ctx(request)
    owners = {r.get("owner_entity_id") for r in await db.inventory_rolls.find(
        {"id": {"$in": roll_ids}}, {"_id": 0, "owner_entity_id": 1}).to_list(1000)}
    if not owners <= set(ctx.allowed_entity_ids):
        raise HTTPException(status_code=403, detail="Keputusan hanya boleh oleh PT pemilik roll.")


@router.get("/sales-returns/{return_id}/disposition")
async def get_disposition(return_id: str, request: Request) -> Any:
    await require_permission(request, "sales_return", "view")
    return await rds.view(await _ret(return_id, request))


async def _decide(return_id: str, payload: DecisionIn, request: Request, stage: str) -> Any:
    user = await require_permission(request, "sales_return", "approve")
    ret = await _ret(return_id, request)
    await _assert_owner(request, payload.roll_ids)
    actor = user.get("name", "")
    try:
        if stage == "internal":
            res = await rds.decide_internal(ret, payload.roll_ids, payload.decision, payload.reason, actor)
        else:
            res = await rds.decide_supplier(ret, payload.roll_ids, payload.decision, payload.reason,
                                            payload.attachment_ids, actor)
    except (ValueError, icret.IntercoReturnError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor, f"sales_return_disposition_{stage}", "sales_return", return_id,
                {"decision": payload.decision, "rolls": payload.roll_ids, "reason": payload.reason})
    return res


@router.post("/sales-returns/{return_id}/disposition/internal")
async def decide_internal(return_id: str, payload: DecisionIn, request: Request) -> Any:
    return await _decide(return_id, payload, request, "internal")


@router.post("/sales-returns/{return_id}/disposition/supplier")
async def decide_supplier(return_id: str, payload: DecisionIn, request: Request) -> Any:
    return await _decide(return_id, payload, request, "supplier")


@router.get("/sales-returns/{return_id}/grade-impairments")
async def grade_impairments(return_id: str, request: Request) -> Any:
    await require_permission(request, "sales_return", "view")
    ret = await _ret(return_id, request)
    return {**await rgi.list_for_return(return_id), "factors": await rgi.grade_factors(ret.get("entity_id", ""))}

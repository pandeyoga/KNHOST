"""LN-083/LN-092 — pengecualian retur, cutloss (qty cacat QC) & diskon (nilai diputus Finance)."""
from typing import Any, Dict, List, Optional

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
    defect_yard: float = Field(0, ge=0)
    roll_id: str = ""
    note: str = ""
    defect_from: Optional[float] = Field(None, ge=0)
    defect_to: Optional[float] = Field(None, gt=0)
    treatment: str = ""


class CompLine(BaseModel):
    kind: str
    product_id: str
    qty: float = 0
    amount: float = 0
    evidence_ids: List[str] = Field(default_factory=list)


class CompensationIn(BaseModel):
    lines: List[CompLine]
    note: str = ""


class LogisticsCost(BaseModel):
    type: str
    bearer: str = "company"
    mode: str = "third_party"
    amount: float = Field(0, ge=0)
    vat_amount: float = Field(0, ge=0)
    pay_account_code: str = ""
    charged_entity_id: str = ""
    note: str = ""


class LogisticsIn(BaseModel):
    costs: List[LogisticsCost]


@router.get("/sales-returns/{return_id}/logistics")
async def logistics_context(return_id: str, request: Request) -> Any:
    """Pilihan cara kirim, akun pembayaran (Finance), PT pembeban, PPN ongkir & jurnal yang aktif."""
    user = await require_permission(request, "sales_return", "view")
    ret = await _ret(return_id, request)
    from dependencies import has_permission
    from services import return_logistics_service as rl
    ctx = await entity_ctx(request)
    ents = await db.business_entities.find({"id": {"$in": list(ctx.allowed_entity_ids or [])}},
                                           {"_id": 0, "id": 1, "name": 1}).to_list(50)
    return {"logistics_costs": ret.get("logistics_costs") or {}, "types": rl.TYPES, "modes": rl.MODES,
            "bearer_options": [{"mode": m, "bearer": b, "label": l} for (m, b), l in rl.BEARER_LABEL.items()],
            "vat_enabled": await rl.vat_enabled(ret.get("entity_id", "")),
            "can_post": await has_permission(user, "sales_return", "post_logistics"),
            "pay_accounts": await rl.pay_accounts(ret.get("entity_id", "")), "entities": ents,
            "default_entity_id": ret.get("entity_id", "")}


@router.put("/sales-returns/{return_id}/logistics")
async def set_logistics(return_id: str, payload: LogisticsIn, request: Request) -> Any:
    """LN-091 KLR-11 + GL-01 — cara kirim & penanggung per kasus; jurnal ongkir otomatis."""
    from dependencies import require_any_permission
    user = await require_any_permission(request, [("sales_return", "update"), ("sales_return", "post_logistics")])
    ret = await _ret(return_id, request)
    if ret.get("status") in ("refund_settled", "credit_settled", "nego_settled", "rejected", "cancelled"):
        raise HTTPException(status_code=400, detail="Retur sudah selesai — biaya logistik tidak bisa diubah")
    from dependencies import has_permission
    from services import return_logistics_service as rl
    ctx = await entity_ctx(request)
    for c in payload.costs:
        if c.charged_entity_id and c.charged_entity_id not in (ctx.allowed_entity_ids or []):
            raise HTTPException(status_code=403, detail="Tidak berhak membebankan ke PT ini")
    try:
        doc = await rl.save(ret, [c.dict() for c in payload.costs], user,
                            await has_permission(user, "sales_return", "post_logistics"))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "sales_return_logistics_set", "sales_return", return_id, doc)
    return doc


class ReplacementLine(BaseModel):
    product_id: str
    qty_yard: float = Field(..., gt=0)


class ReplacementIn(BaseModel):
    items: List[ReplacementLine]


@router.get("/sales-returns/{return_id}/replacement")
async def replacement_preview(return_id: str, request: Request) -> Any:
    await require_permission(request, "sales_return", "view")
    ret = await _ret(return_id, request)
    from services import return_replacement_service as rr
    return {"obligation": await rr.obligation(ret), "order_id": ret.get("replacement_order_id", ""),
            "order_number": ret.get("replacement_order_number", ""), "summary": ret.get("replacement_summary") or {}}


@router.post("/sales-returns/{return_id}/replacement-order")
async def create_replacement_order(return_id: str, payload: ReplacementIn, request: Request) -> Any:
    user = await require_permission(request, "order", "create")
    await require_permission(request, "sales_return", "update")
    ret = await _ret(return_id, request)
    from services import atomic_claim as saga
    from services import return_replacement_service as rr
    await saga.claim("sales_returns", return_id, "sales_return_replacement_order",
                     precondition={"replacement_order_id": {"$in": [None, ""]}}, actor=user.get("name", ""))
    try:
        out = await rr.create(ret, [x.dict() for x in payload.items], request, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await saga.release("sales_returns", return_id)
    await audit(user.get("name", ""), "sales_return_replacement_order", "sales_return", return_id, out)
    return out


@router.post("/sales-returns/{return_id}/cutloss")
async def record_cutloss(return_id: str, payload: CutlossRecordIn, request: Request) -> Any:
    user = await require_permission(request, "sales_return", "record_cutloss")
    ret = await _ret(return_id, request)
    try:
        out = await comp.record_cutloss(ret, payload.product_id, payload.defect_yard, payload.roll_id, payload.note, user,
                                        payload.defect_from, payload.defect_to, payload.treatment)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "sales_return_cutloss_recorded", "sales_return", return_id, out)
    return out


async def _split_call(fn, return_id: str, ctl_id: str, request: Request, action: str, with_actor: bool = True):
    user = await require_permission(request, "sales_return", action)
    ret = await _ret(return_id, request)
    try:
        return user, (await fn(ret, ctl_id, user) if with_actor else await fn(ret, ctl_id))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sales-returns/{return_id}/cutloss/{ctl_id}/split-preview")
async def cutloss_split_preview(return_id: str, ctl_id: str, request: Request) -> Any:
    from services import return_cutloss_split_service as split
    return (await _split_call(split.preview, return_id, ctl_id, request, "view", False))[1]


@router.post("/sales-returns/{return_id}/cutloss/{ctl_id}/split")
async def cutloss_split(return_id: str, ctl_id: str, request: Request) -> Any:
    """CUT-01/04 — pecah roll cutloss setelah QC: potongan baik, BS, atau dibuang."""
    from services import return_cutloss_split_service as split
    user, out = await _split_call(split.execute, return_id, ctl_id, request, "split_cutloss")
    await audit(user.get("name", ""), "sales_return_cutloss_split", "sales_return", return_id, out)
    return out


@router.post("/sales-returns/{return_id}/cutloss/{ctl_id}/return-shipment")
async def cutloss_return_shipment(return_id: str, ctl_id: str, request: Request) -> Any:
    """CUT-05 — SJ baru untuk potongan baik, merujuk SJ & SO asal."""
    from services import return_cutloss_split_service as split
    user, out = await _split_call(split.create_return_sj, return_id, ctl_id, request, "split_cutloss")
    await audit(user.get("name", ""), "sales_return_cutloss_return_sj", "sales_return", return_id, out)
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

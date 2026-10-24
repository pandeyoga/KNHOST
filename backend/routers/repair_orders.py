"""UAT 24 Okt (P7) — menu Perbaikan (repair / celup ulang / finishing ulang) atas roll yang sudah ada.
Izin `repair_order` (view/create/send/receive/cancel). Logika di `services/repair_order_service.py`."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from dependencies import audit, require_permission
from entity_scope import assert_entity_access, entity_ctx, resolve_scope_ids
from services import repair_order_service as svc

router = APIRouter(prefix="/api")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


async def _load(request: Request, ro_id: str) -> Dict[str, Any]:
    try:
        ro = await svc.get(ro_id)
    except LookupError as exc:
        raise _http(exc) from exc
    assert_entity_access(ro, "repair_orders", await entity_ctx(request))
    return ro


async def _entity(request: Request) -> str:
    ent = (await entity_ctx(request)).active_entity_id or ""
    if not ent or ent == "all":
        raise HTTPException(status_code=400, detail="Pilih satu badan usaha (bukan 'Semua') untuk dokumen perbaikan.")
    return ent


class CostIn(BaseModel):
    basis: str = "lumpsum"                      # per_unit | per_roll | lumpsum
    rate: float = Field(0, ge=0)
    other_costs: List[Dict[str, Any]] = Field(default_factory=list)   # [{label, amount}]
    contract_id: str = ""


class RepairCreate(BaseModel):
    kind: str = "perbaikan"                     # perbaikan | celup_ulang | finishing_ulang
    partner_type: str = "internal"              # internal | makloon
    partner_id: str = ""
    roll_ids: List[str]
    cost: CostIn = Field(default_factory=CostIn)
    target_product_id: str = ""                 # celup ulang ke SKU lain (P7-K2)
    target_color: str = ""
    target_dye_lot: str = ""
    notes: str = ""
    source_type: str = ""                       # asal: sales_return / inspection / … (Jejak Dokumen)
    source_id: str = ""


class ReceiveLine(BaseModel):
    roll_id: str
    qty_out: float = Field(..., ge=0)
    grade: str = ""
    dye_lot: str = ""


class RepairReceive(BaseModel):
    lines: List[ReceiveLine]
    actual_cost: Optional[float] = Field(None, ge=0)
    cost: Optional[CostIn] = None


class ReasonIn(BaseModel):
    reason: str = Field(..., min_length=5, max_length=300)


@router.get("/repair-orders")
async def list_repairs(request: Request, status: str = "", q: str = "", entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    await require_permission(request, "repair_order", "view")
    ids = resolve_scope_ids(await entity_ctx(request), entity_id)
    items = await svc.list_orders(ids, status, q)
    counts: Dict[str, int] = {}
    for it in await svc.list_orders(ids, "", "", limit=2000):
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    return {"items": items, "counts": counts, "kinds": svc.KINDS, "cost_basis": svc.COST_BASIS}


@router.get("/repair-orders/candidate-rolls")
async def candidate_rolls(request: Request, q: str = "") -> List[Dict[str, Any]]:
    await require_permission(request, "repair_order", "create")
    return await svc.candidate_rolls(await _entity(request), q)


@router.get("/repair-orders/target-products")
async def target_products(request: Request, q: str = "") -> List[Dict[str, Any]]:
    """SKU tujuan celup ulang (P7-K2 — boleh berganti SKU): cari SKU aktif per kode/nama."""
    await require_permission(request, "repair_order", "create")
    from db import db
    if len(q.strip()) < 2:
        return []
    rx = {"$regex": q.strip(), "$options": "i"}
    return await db.products.find({"status": {"$ne": "inactive"}, "$or": [{"sku": rx}, {"name": rx}]},
                                  {"_id": 0, "id": 1, "sku": 1, "name": 1, "base_unit": 1}).limit(20).to_list(20)


@router.post("/repair-orders")
async def create_repair(payload: RepairCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "repair_order", "create")
    try:
        ro = await svc.create(payload.model_dump(), actor, await _entity(request))
    except svc.RepairError as exc:
        raise _http(exc) from exc
    await audit(actor.get("name", ""), "repair_order_created", "repair_order", ro["id"],
                {"number": ro["number"], "kind": ro["kind"], "rolls": len(ro["lines"]), "partner": ro.get("partner_name")})
    return ro


@router.get("/repair-orders/{ro_id}")
async def get_repair(ro_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "repair_order", "view")
    return await _load(request, ro_id)


@router.post("/repair-orders/{ro_id}/send")
async def send_repair(ro_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "repair_order", "send")
    await _load(request, ro_id)
    try:
        ro = await svc.send(ro_id, actor)
    except svc.RepairError as exc:
        raise _http(exc) from exc
    await audit(actor.get("name", ""), "repair_order_sent", "repair_order", ro_id, {"number": ro["number"]})
    return ro


@router.post("/repair-orders/{ro_id}/receive")
async def receive_repair(ro_id: str, payload: RepairReceive, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "repair_order", "receive")
    await _load(request, ro_id)
    try:
        ro = await svc.receive(ro_id, payload.model_dump(exclude_none=True), actor)
    except svc.RepairError as exc:
        raise _http(exc) from exc
    await audit(actor.get("name", ""), "repair_order_received", "repair_order", ro_id,
                {"number": ro["number"], "cost": ro.get("actual_cost"), "shrink": ro.get("total_shrink")})
    return ro


@router.post("/repair-orders/{ro_id}/cancel")
async def cancel_repair(ro_id: str, payload: ReasonIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "repair_order", "cancel")
    await _load(request, ro_id)
    try:
        ro = await svc.cancel(ro_id, actor, payload.reason)
    except svc.RepairError as exc:
        raise _http(exc) from exc
    await audit(actor.get("name", ""), "repair_order_cancelled", "repair_order", ro_id, {"number": ro["number"]},
                reason=payload.reason)
    return ro


@router.get("/inventory/rolls/{roll_id}/repairs")
async def roll_repairs(roll_id: str, request: Request) -> List[Dict[str, Any]]:
    """Riwayat perbaikan satu roll (jejak roll)."""
    await require_permission(request, "product", "view")
    return await svc.roll_repairs(roll_id)

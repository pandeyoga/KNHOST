"""GRN Fase 2 — `/api/goods-receipts` (Kedatangan Barang). Pembungkus tipis atas layanan GRN."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import Response

from db import db
from dependencies import require_any_permission, require_permission
from entity_scope import entity_ctx
from schemas_goods_receipt import (GRNCountRollIn, GRNCreateIn, GRNDnPatch, GRNLineIn, GRNLinePatch, GRNReasonIn,
                                   GRNResolveIn, GRNScanIn, GRNVersionIn)
from services import goods_receipt_close_service as gc
from services import goods_receipt_ocr_service as go
from services import goods_receipt_service as gs

router = APIRouter(prefix="/api")
M = "goods_receipt"


async def _act(request: Request, action: str):
    return await require_permission(request, M, action), await entity_ctx(request)


async def _out(doc: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    return await gs.public_view(doc, user)


@router.post("/goods-receipts")
async def create_grn(body: GRNCreateIn, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "create")
    return await _out(await gs.create_grn(body, actor, ctx), actor)


@router.get("/goods-receipts")
async def list_grn(request: Request, status: str = "", partner_id: str = "", q: str = "",
                   limit: int = 100) -> List[Dict[str, Any]]:
    await require_permission(request, M, "view")
    ctx = await entity_ctx(request)
    flt: Dict[str, Any] = {"entity_id": {"$in": ctx.allowed_entity_ids} if ctx.view_all else ctx.active_entity_id}
    if status:
        flt["status"] = {"$in": status.split(",")}
    if partner_id:
        flt["partner_id"] = partner_id
    if q:
        flt["$or"] = [{"number": {"$regex": q, "$options": "i"}}, {"dn.number": {"$regex": q, "$options": "i"}},
                      {"partner_name": {"$regex": q, "$options": "i"}}]
    rows = await db.goods_receipts.find(flt, {"_id": 0}).sort("created_at", -1).to_list(min(limit, 500))
    return [{"id": r["id"], "number": r["number"], "status": r["status"], "version": r["version"],
             "partner_type": r["partner_type"], "partner_id": r["partner_id"], "partner_name": r["partner_name"],
             "warehouse_id": r["warehouse_id"], "dn_number": (r.get("dn") or {}).get("number", ""),
             "lines": len(r.get("lines") or []), "pages": len(r.get("files") or []),
             "open_blockers": len(gc.open_blockers(r.get("discrepancies") or [])),
             "created_by": r.get("created_by"), "created_at": r.get("created_at"),
             "closed_at": r.get("closed_at", "")} for r in rows]


@router.get("/goods-receipts/partners")
async def grn_partners(request: Request, partner_type: str = "supplier") -> List[Dict[str, Any]]:
    _, ctx = await _act(request, "create")
    return await gs.list_partners(partner_type, ctx)


@router.get("/goods-receipts/supplier-variance")
async def grn_supplier_variance(request: Request, since: str = "") -> List[Dict[str, Any]]:
    await require_any_permission(request, [(M, "view"), ("purchase_order", "view")])
    return await gs.supplier_variance(await entity_ctx(request), since)


@router.get("/goods-receipts/usage")
async def grn_ocr_usage(request: Request, month: str = "") -> Dict[str, Any]:
    _, ctx = await _act(request, "approve")
    return await go.usage_summary(month, ctx)


@router.get("/goods-receipts/{grn_id}/rolls")
async def grn_rolls(grn_id: str, request: Request) -> List[Dict[str, Any]]:
    _, ctx = await _act(request, "view")
    return await gs.list_rolls(grn_id, ctx)


@router.get("/goods-receipts/{grn_id}")
async def get_grn(grn_id: str, request: Request, view: str = "review") -> Dict[str, Any]:
    actor, ctx = await _act(request, "view")
    return await _out(await go.sweep_stale(await gs.load(grn_id, ctx)), actor)


@router.post("/goods-receipts/{grn_id}/read")
async def read_grn(grn_id: str, body: GRNVersionIn, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "create")
    return await _out(await go.read_grn(grn_id, body.expected_version, actor, ctx), actor)


@router.get("/goods-receipts/{grn_id}/targets")
async def grn_targets(grn_id: str, request: Request) -> List[Dict[str, Any]]:
    _, ctx = await _act(request, "review")
    return await gs.list_targets(grn_id, ctx)


@router.post("/goods-receipts/{grn_id}/files")
async def add_file(grn_id: str, request: Request, file: UploadFile = File(...),
                   expected_version: Optional[int] = Form(None)) -> Dict[str, Any]:
    actor, ctx = await _act(request, "create")
    res = await gs.add_file(grn_id, file.filename or "", file.content_type or "", await file.read(),
                            expected_version, actor, ctx)
    return {**res, "grn": await _out(res["grn"], actor)}


@router.delete("/goods-receipts/{grn_id}/files/{page}")
async def delete_file(grn_id: str, page: int, request: Request, expected_version: int) -> Dict[str, Any]:
    actor, ctx = await _act(request, "create")
    return await _out(await gs.delete_file(grn_id, page, expected_version, actor, ctx), actor)


@router.get("/goods-receipts/{grn_id}/files/{page}")
async def get_file(grn_id: str, page: int, request: Request) -> Response:
    actor, ctx = await _act(request, "view")
    data, ctype = await gs.get_file(grn_id, page, actor, ctx)
    return Response(content=data, media_type=ctype, headers={"Cache-Control": "private, no-store"})


@router.post("/goods-receipts/{grn_id}/manual-entry")
async def manual_entry(grn_id: str, body: GRNVersionIn, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "create")
    return await _out(await gs.manual_entry(grn_id, body.expected_version, actor, ctx), actor)


@router.patch("/goods-receipts/{grn_id}/dn")
async def patch_dn(grn_id: str, body: GRNDnPatch, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "review")
    return await _out(await gs.patch_dn(grn_id, body, actor, ctx), actor)


@router.post("/goods-receipts/{grn_id}/lines")
async def add_line(grn_id: str, body: GRNLineIn, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "review")
    return await _out(await gs.add_line(grn_id, body, actor, ctx), actor)


@router.patch("/goods-receipts/{grn_id}/lines/{line_no}")
async def patch_line(grn_id: str, line_no: int, body: GRNLinePatch, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "review")
    return await _out(await gs.patch_line(grn_id, line_no, body, actor, ctx), actor)


@router.delete("/goods-receipts/{grn_id}/lines/{line_no}")
async def delete_line(grn_id: str, line_no: int, request: Request, expected_version: int) -> Dict[str, Any]:
    actor, ctx = await _act(request, "review")
    return await _out(await gs.delete_line(grn_id, line_no, expected_version, actor, ctx), actor)


@router.post("/goods-receipts/{grn_id}/start-count")
async def start_count(grn_id: str, body: GRNVersionIn, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "review")
    return await _out(await gs.start_count(grn_id, body.expected_version, actor, ctx), actor)


@router.post("/goods-receipts/{grn_id}/lines/{line_no}/scan-label")
async def scan_label(grn_id: str, line_no: int, body: GRNScanIn, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "count")
    res = await gs.scan_label(grn_id, line_no, body, actor, ctx)
    return {"roll": res["roll"], "grn": await _out(res["grn"], actor)}


@router.post("/goods-receipts/{grn_id}/lines/{line_no}/rolls")
async def add_roll(grn_id: str, line_no: int, body: GRNCountRollIn, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "count")
    res = await gs.add_counted_roll(grn_id, line_no, body, actor, ctx)
    return {"roll": res["roll"], "grn": await _out(res["grn"], actor)}


@router.delete("/goods-receipts/{grn_id}/rolls/{roll_id}")
async def delete_roll(grn_id: str, roll_id: str, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "count")
    return await _out(await gs.delete_roll(grn_id, roll_id, actor, ctx), actor)


@router.post("/goods-receipts/{grn_id}/finish-count")
async def finish_count(grn_id: str, body: GRNVersionIn, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "count")
    return await _out(await gc.finish_count(grn_id, body.expected_version, actor, ctx), actor)


@router.post("/goods-receipts/{grn_id}/reopen-count")
async def reopen_count(grn_id: str, body: GRNVersionIn, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "review")
    return await _out(await gc.reopen_count(grn_id, body.expected_version, actor, ctx), actor)


@router.post("/goods-receipts/{grn_id}/discrepancies/{key}/resolve")
async def resolve(grn_id: str, key: str, body: GRNResolveIn, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "review")
    return await _out(await gc.resolve(grn_id, key, body, actor, ctx), actor)


@router.post("/goods-receipts/{grn_id}/close")
async def close(grn_id: str, body: GRNVersionIn, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "close")
    res = await gc.close_grn(grn_id, body.expected_version, actor, ctx)
    return {"grn": await _out(res["grn"], actor), "results": res["results"]}


@router.post("/goods-receipts/{grn_id}/reject")
async def reject(grn_id: str, body: GRNReasonIn, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "review")
    return await _out(await gc.reject_grn(grn_id, body, actor, ctx), actor)


@router.post("/goods-receipts/{grn_id}/cancel")
async def cancel(grn_id: str, body: GRNReasonIn, request: Request) -> Dict[str, Any]:
    actor, ctx = await _act(request, "create")
    return await _out(await gc.cancel_grn(grn_id, body, actor, ctx), actor)

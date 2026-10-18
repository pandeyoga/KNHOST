"""LN-093 tujuan barang retur berantai + LN-091-T02 kerugian turun grade."""
from typing import Any, Dict, List

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from db import db
from core_utils import new_id, now_iso
from dependencies import audit, require_any_permission, require_permission
from entity_scope import entity_ctx, resolve_scope_ids
from services import interco_return_service as icret
from services import return_disposition_service as rds
from services import return_grade_impairment as rgi
from services import storage_service as storage

DECIDE_PERMS = [("sales_return", "approve"), ("interco", "approve")]
VIEW_PERMS = [("sales_return", "view"), ("interco", "view")]

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
    await require_any_permission(request, VIEW_PERMS)
    return await rds.view(await _ret(return_id, request))


async def _decide(return_id: str, payload: DecisionIn, request: Request, stage: str) -> Any:
    user = await require_any_permission(request, DECIDE_PERMS)
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


@router.get("/return-dispositions/inbox")
async def disposition_inbox(request: Request, entity_id: str = "") -> Any:
    """Meja PT pemasok: retur internal wajib terima + roll menunggu keputusan tahap 2."""
    await require_any_permission(request, VIEW_PERMS)
    return await rds.inbox(resolve_scope_ids(await entity_ctx(request), entity_id or None))


@router.post("/sales-returns/{return_id}/disposition/photos")
async def upload_disposition_photo(return_id: str, request: Request, file: UploadFile = File(...)) -> Any:
    """Foto bukti keputusan (kamera HP) — boleh oleh PT pemilik roll walau retur pelanggan sudah selesai."""
    user = await require_any_permission(request, DECIDE_PERMS)
    await _ret(return_id, request)
    data = await file.read()
    ctype = storage.validate_upload(file.filename, file.content_type, len(data), data[:16])
    if not ctype.startswith("image/"):
        raise HTTPException(status_code=400, detail="Bukti keputusan harus berupa foto.")
    path = f"sales_returns/{return_id}/disposition/{new_id('att')}-{file.filename}"
    await storage.put_object(path, data, ctype)
    att = {"id": new_id("att"), "filename": file.filename, "path": path, "size": len(data), "content_type": ctype,
           "uploaded_by": user.get("name", ""), "uploaded_at": now_iso(), "is_deleted": False}
    await db.sales_returns.update_one({"id": return_id}, {"$push": {"disposition_photos": att}})
    await audit(user.get("name", ""), "sales_return_disposition_photo", "sales_return", return_id, {"filename": file.filename})
    return {k: v for k, v in att.items() if k != "path"}


@router.get("/sales-returns/{return_id}/disposition/photos/{att_id}")
async def download_disposition_photo(return_id: str, att_id: str, request: Request):
    await require_any_permission(request, VIEW_PERMS)
    ret = await _ret(return_id, request)
    att = next((a for a in ret.get("disposition_photos") or [] if a["id"] == att_id), None)
    if not att:
        raise HTTPException(status_code=404, detail="Foto tidak ditemukan")
    data, _ = await storage.get_object(att["path"])
    return Response(content=data, media_type=att["content_type"])


@router.get("/return-dispositions/summary")
async def disposition_summary(request: Request, entity_id: str = "") -> Any:
    """Kartu Beranda: angka retur internal masuk + roll menunggu keputusan + batas supplier ≤ N hari."""
    await require_any_permission(request, VIEW_PERMS)
    return await rds.desk_summary(resolve_scope_ids(await entity_ctx(request), entity_id or None))

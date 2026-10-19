"""GL-01 — API Pemetaan Akun (Pengaturan → Keuangan). Izin `gl_mapping.view|update`."""
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from dependencies import audit, require_permission
from entity_scope import entity_ctx
from services import gl_mapping_service as svc

router = APIRouter(prefix="/api")


class MappingIn(BaseModel):
    account_code: str
    entity_id: str = ""
    reason: str


class ResetIn(BaseModel):
    entity_id: str = ""
    reason: str


async def _check_entity(request: Request, entity_id: str) -> None:
    if not entity_id or entity_id == "all":
        return
    ctx = await entity_ctx(request)
    allowed = getattr(ctx, "allowed_entity_ids", None)
    if allowed is not None and entity_id not in allowed:
        raise HTTPException(status_code=403, detail="Tidak berhak atas badan usaha ini")


@router.get("/gl/account-mappings")
async def list_mappings(request: Request, entity_id: Optional[str] = Query(None)) -> Any:
    await require_permission(request, "gl_mapping", "view")
    await _check_entity(request, entity_id or "")
    return await svc.list_mappings(entity_id)


@router.get("/gl/account-mappings/history")
async def mapping_history(request: Request, key: Optional[str] = Query(None),
                          entity_id: Optional[str] = Query(None)) -> Any:
    await require_permission(request, "gl_mapping", "view")
    return await svc.history(key, entity_id)


@router.get("/gl/account-mappings/{key}/candidates")
async def mapping_candidates(key: str, request: Request, entity_id: Optional[str] = Query(None)) -> Any:
    await require_permission(request, "gl_mapping", "view")
    try:
        return await svc.candidates(key, entity_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/gl/account-mappings/{key}")
async def set_mapping(key: str, payload: MappingIn, request: Request) -> Any:
    user = await require_permission(request, "gl_mapping", "update")
    await _check_entity(request, payload.entity_id)
    try:
        doc = await svc.set_mapping(key, payload.entity_id, payload.account_code, payload.reason, user)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "gl_mapping_set", "gl_mapping", key, doc)
    return doc


@router.post("/gl/account-mappings/{key}/reset")
async def reset_mapping(key: str, payload: ResetIn, request: Request) -> Any:
    user = await require_permission(request, "gl_mapping", "update")
    await _check_entity(request, payload.entity_id)
    try:
        out = await svc.reset_mapping(key, payload.entity_id, payload.reason, user)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(user.get("name", ""), "gl_mapping_reset", "gl_mapping", key, out)
    return out

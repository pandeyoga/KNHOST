"""FIX-8 (K-B4-12) — API tampilan tersimpan daftar gudang. Aturan & whitelist: `services/saved_view_service.py`.

* GET    `/api/saved-views?list_key=`   → tampilan milik saya + yang dibagikan ke peran/PT saya (+ semua tampilan bersama
                                         untuk admin), `default_id` (bawaan pribadi → bawaan bersama)
* POST   `/api/saved-views`             → simpan tampilan baru (pribadi; `share` hanya admin)
* PUT    `/api/saved-views/{view_id}`   → ubah nama/isi/berbagi/bawaan (pemilik; tampilan bersama hanya admin)
* DELETE `/api/saved-views/{view_id}`   → hapus (pemilik; tampilan bersama hanya admin)

Izin = izin LIHAT daftar yang bersangkutan (mis. `transfer.view`). Cakupan PT/lokasi tidak pernah disimpan.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from db import db
from dependencies import audit, current_user, has_permission, require_permission
from services import saved_view_service as svc

router = APIRouter(prefix="/api")


class SavedViewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    list_key: str
    name: str
    state: Dict[str, Any] = {}
    share: Optional[Dict[str, Any]] = None
    is_default: bool = False


class SavedViewPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = None
    state: Optional[Dict[str, Any]] = None
    share: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None


async def _require_list_perm(request: Request, list_key: str) -> Dict[str, Any]:
    perm = svc.list_perm(list_key)
    if not perm:
        raise HTTPException(status_code=400, detail=f"Daftar tidak mendukung tampilan tersimpan: {list_key or '(kosong)'}")
    return await require_permission(request, *perm)


async def _require_view_perm(request: Request, view_id: str) -> Dict[str, Any]:
    user = await current_user(request)
    v = await db[svc.COLL].find_one({"id": view_id}, {"_id": 0, "list_key": 1})
    perm = svc.list_perm((v or {}).get("list_key", ""))
    if not v or not perm:
        raise HTTPException(status_code=404, detail="Tampilan tidak ditemukan.")
    if not await has_permission(user, *perm):
        raise HTTPException(status_code=403, detail=f"Permission ditolak: {perm[0]}.{perm[1]}")
    return user


@router.get("/saved-views")
async def list_saved_views(request: Request, list_key: str = Query(..., max_length=60)) -> Dict[str, Any]:
    user = await _require_list_perm(request, list_key)
    return await svc.list_views(user, list_key)


@router.post("/saved-views")
async def create_saved_view(payload: SavedViewIn, request: Request) -> Dict[str, Any]:
    user = await _require_list_perm(request, payload.list_key)
    out, doc = await svc.create_view(user, payload.model_dump())
    await audit(user.get("email") or user["id"], "saved_view.create", svc.COLL, doc["id"],
                {"list_key": doc["list_key"], "name": doc["name"], "share": doc["share"], "state": doc["state"]})
    return out


@router.put("/saved-views/{view_id}")
async def update_saved_view(view_id: str, payload: SavedViewPatch, request: Request) -> Dict[str, Any]:
    user = await _require_view_perm(request, view_id)
    out, before, after = await svc.update_view(user, view_id, payload.model_dump(exclude_unset=True))
    await audit(user.get("email") or user["id"], "saved_view.update", svc.COLL, view_id,
                {k: after.get(k) for k in ("name", "share", "state", "is_default")},
                before={k: before.get(k) for k in ("name", "share", "state", "is_default")})
    return out


@router.delete("/saved-views/{view_id}")
async def delete_saved_view(view_id: str, request: Request) -> Dict[str, Any]:
    user = await _require_view_perm(request, view_id)
    before = await svc.delete_view(user, view_id)
    await audit(user.get("email") or user["id"], "saved_view.delete", svc.COLL, view_id, None,
                before={k: before.get(k) for k in ("list_key", "name", "share")})
    return {"ok": True, "id": view_id}

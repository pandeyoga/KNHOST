"""Router PERAN & HAK AKSES (`/api/access/...`) — dipakai tab "Peran & Hak Akses"
di layar Badan Usaha & Akses. Aturan di `services/custom_role_service.py`."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from access_modules import ACTION_LABEL, LEVEL_LABEL, RESOURCE_LABEL, public_catalog
from dependencies import audit, require_permission
from services import custom_role_service as svc

def _label(rid: str) -> str:
    import role_registry as reg
    return reg.role_label(rid) or rid


router = APIRouter(prefix="/api/access", tags=["access-roles"])


class RoleCreate(BaseModel):
    label: str
    description: str = ""
    base_role: str = ""
    levels: Dict[str, str] = {}
    permissions: Optional[Dict[str, List[str]]] = None
    cross_entity: Optional[bool] = None   # keputusan owner 2026-10-21 — None = ikut peran acuan


class RolePatch(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None
    levels: Optional[Dict[str, str]] = None
    permissions: Optional[Dict[str, List[str]]] = None
    hidden_views: Optional[List[str]] = None
    cross_entity: Optional[bool] = None   # keputusan owner 2026-10-21 — akses SEMUA badan usaha aktif
    expected_version: Optional[str] = None
    # PR-T1 — peran yang akunnya boleh dikelola pemegang peran ini (hanya Admin yang mengubah; `admin` tidak sah).
    assignable_roles: Optional[List[str]] = None


class RolePreview(BaseModel):
    role_id: str = ""
    base_role: str = ""
    levels: Dict[str, str] = {}
    permissions: Optional[Dict[str, List[str]]] = None


class RoleMoveUsers(BaseModel):
    to_role: str


@router.post("/roles/preview")
async def preview_role(payload: RolePreview, request: Request) -> Dict[str, Any]:
    await require_permission(request, "permission", "view")
    return await svc.preview_role(payload.model_dump())


@router.post("/roles/{rid}/move-users")
async def move_role_users(rid: str, payload: RoleMoveUsers, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "permission", "update")
    from services.access_guard import assert_can_manage_account   # PR-T1
    await assert_can_manage_account(actor, target_user={"role": rid}, new_role=payload.to_role)
    out = await svc.move_users(rid, payload.to_role, exclude_user_id=actor.get("id", ""))
    await audit(actor["name"], "role_users_moved", "custom_role", rid, out)
    return out


@router.get("/modules")
async def list_modules(request: Request) -> Dict[str, Any]:
    await require_permission(request, "permission", "view")
    return {"modules": public_catalog(), "levels": LEVEL_LABEL,
            "resource_labels": RESOURCE_LABEL, "action_labels": ACTION_LABEL}


@router.get("/roles")
async def list_roles(request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "permission", "view")
    from services.access_guard import can_manage_role   # PR-T1 — tombol ubah mati bila server akan menolak
    roles = await svc.all_roles()
    for r in roles:
        r["can_manage"] = await can_manage_role(actor, r.get("permissions") or {}, r["id"])
    # Daftar "Boleh mengelola akun dengan peran" hanya bisa diubah Admin (dibaca layar; bukan cek nama peran di layar).
    return {"roles": roles, "can_edit_assignable": actor.get("role") == "admin"}


@router.get("/roles/{rid}")
async def get_role(rid: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "permission", "view")
    return await svc.get_role(rid)


@router.post("/roles")
async def create_role(payload: RoleCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "permission", "update")
    from services.access_guard import assert_can_shape_role   # PR-T1 — tidak bisa merakit peran lebih kuasa
    body = payload.model_dump()
    await assert_can_shape_role(actor, current_perms=None, new_perms=await svc.projected_permissions(None, body),
                                new_cross_entity=body.get("cross_entity"))
    out = await svc.create_custom(body)
    await audit(actor["name"], "custom_role_created", "custom_role", out["id"],
                {"label": out["label"], "base_role": out["base_role"], "levels": out["levels"]})
    return out


@router.patch("/roles/{rid}")
async def patch_role(rid: str, payload: RolePatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "permission", "update")
    # L01 LN-015-T06 — tanpa delegasi (hanya Admin), akun tidak boleh mengubah hak PERANNYA SENDIRI.
    if rid == actor.get("role") and actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Anda tidak bisa mengubah hak akses peran Anda sendiri — "
                                                    "minta Admin melakukannya.")
    from services.access_guard import assert_can_shape_role   # PR-T1
    body = payload.model_dump(exclude_none=True)
    if "assignable_roles" in body and actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Daftar akun yang boleh dikelola peran hanya bisa diubah Admin.")
    await assert_can_shape_role(actor, current_perms=await svc.current_permissions(rid),
                                new_perms=await svc.projected_permissions(rid, body),
                                new_cross_entity=body.get("cross_entity"), role_label=_label(rid))
    out = await svc.update_role(rid, body)
    await audit(actor["name"], "role_access_updated", "custom_role", rid,
                {"label": out["label"], "changes": out.get("changes", {}), "users": out["users"]})
    return out


@router.post("/roles/{rid}/reset")
async def reset_role(rid: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "permission", "update")
    from permissions_config import DEFAULT_PERMISSIONS
    from services.access_guard import assert_can_shape_role   # PR-T1
    await assert_can_shape_role(actor, current_perms=await svc.current_permissions(rid),
                                new_perms=DEFAULT_PERMISSIONS.get(rid, {}), new_cross_entity=None, role_label=_label(rid))
    out = await svc.reset_builtin(rid)
    await audit(actor["name"], "role_access_reset", "custom_role", rid, {"label": out["label"]})
    return out


@router.delete("/roles/{rid}")
async def delete_role(rid: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "permission", "update")
    from services.access_guard import assert_can_shape_role   # PR-T1
    await assert_can_shape_role(actor, current_perms=await svc.current_permissions(rid), new_perms={},
                                new_cross_entity=None, role_label=_label(rid))
    out = await svc.delete_custom(rid)
    await audit(actor["name"], "custom_role_deleted", "custom_role", rid, out)
    return out

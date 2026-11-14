"""Router PERAN & HAK AKSES (`/api/access/...`) — dipakai tab "Peran & Hak Akses"
di layar Badan Usaha & Akses. Aturan di `services/custom_role_service.py`."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from access_modules import ACTION_LABEL, LEVEL_LABEL, RESOURCE_LABEL, labels_dictionary, public_catalog
from dependencies import audit, current_user, require_any_permission, require_permission
from services import custom_role_service as svc
from services import role_insight_service as insight   # PR-T6 — ringkasan, potret, riwayat

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
    # PR-T4 — sifat peran {data_scope?, home_view?, kategori_kerja?, notify_like?}; null = nilai turunan.
    traits: Optional[Dict[str, Any]] = None
    hidden_views: Optional[List[str]] = None   # PR-T6 (PR-UX-37) — menu tersembunyi dalam satu panggilan pembuatan


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
    # PR-T4 — sifat peran; nilai null pada sebuah kunci = kembali ke nilai turunan.
    traits: Optional[Dict[str, Any]] = None
    # PR-T6 — peran dasar (hanya peran kustom; "" = tanpa peran dasar). Tidak mengubah izin.
    base_role: Optional[str] = None


class RolePreview(BaseModel):
    role_id: str = ""
    # PR-T6 — None = peran dasar tidak diubah (peran yang disunting) / tanpa peran dasar (peran baru).
    base_role: Optional[str] = None
    levels: Dict[str, str] = {}
    permissions: Optional[Dict[str, List[str]]] = None
    traits: Optional[Dict[str, Any]] = None        # PR-T6 — draf sifat yang belum disimpan
    cross_entity: Optional[bool] = None            # PR-T6 — draf lintas PT


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
    # PR-T6 — satu baris `user_updated` per akun (bentuk sama dengan PATCH /api/users/{id}) + satu `role_users_moved`.
    for after in out.pop("updated", []):
        await audit(actor["name"], "user_updated", "user", after["id"],
                    {"changed": after.get("changed_fields", []), "home_entity_id": after.get("home_entity_id"),
                     "allowed_entity_ids": after.get("allowed_entity_ids"), "role": after.get("role"),
                     "sessions_revoked": after.get("sessions_revoked", 0),
                     "revoke_reasons": after.get("revoke_reasons", [])},
                    scope_entity_id=after.get("home_entity_id", ""), reason="Pindah akun massal dari Peran & Hak Akses")
    await audit(actor["name"], "role_users_moved", "custom_role", rid, out)
    return out


@router.get("/modules")
async def list_modules(request: Request) -> Dict[str, Any]:
    await require_permission(request, "permission", "view")
    return {"modules": public_catalog(), "levels": LEVEL_LABEL,
            "resource_labels": RESOURCE_LABEL, "action_labels": ACTION_LABEL}


@router.get("/labels")
async def list_labels(request: Request) -> Dict[str, Any]:
    """PR-T5 — SATU kamus label sumber daya, aksi, dan modul (data rujukan tanpa nominal; cukup login — tercatat di
    `login_only_endpoints.LOGIN_ONLY`). Dibaca layar saat sesi dimuat: pesan penolakan dan jejak audit memakai nama
    yang sama dengan editor peran."""
    await current_user(request)
    return labels_dictionary()


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


@router.get("/roles/{rid}/summary")
async def role_summary(rid: str, request: Request) -> Dict[str, Any]:
    """PR-T6 — "peran ini akhirnya bisa apa": halaman awal, data yang terlihat, PT, batas persetujuan, aksi per modul.
    Juga dibaca formulir akun (pemegang `user.view`)."""
    await require_any_permission(request, [("permission", "view"), ("user", "view")])
    return await insight.role_summary(rid)


@router.get("/roles/{rid}/history")
async def role_history(rid: str, request: Request, limit: int = 50) -> Dict[str, Any]:
    """PR-T6 — riwayat perubahan peran (selisih potret `before`/`after` jejak audit)."""
    await require_permission(request, "permission", "view")
    return await insight.role_history(rid, limit)


@router.post("/roles")
async def create_role(payload: RoleCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "permission", "update")
    from services.access_guard import assert_can_shape_role   # PR-T1 — tidak bisa merakit peran lebih kuasa
    body = payload.model_dump()
    await assert_can_shape_role(actor, current_perms=None, new_perms=await svc.projected_permissions(None, body),
                                new_cross_entity=body.get("cross_entity"))
    from services.data_scope import assert_may_grant_scope   # PR-T4 — cakupan data tidak melebihi milik pelaku
    await svc.sync_registry()
    assert_may_grant_scope(actor, svc.projected_scope(None, body.get("traits"), (body.get("base_role") or "").strip()))
    out = await svc.create_custom(body)
    # PR-T6 — potret sebelum/sesudah untuk Riwayat peran.
    await audit(actor["name"], "custom_role_created", "custom_role", out["id"],
                {**await insight.snapshot(out["id"]), "label": out["label"], "levels": out["levels"], "users": 0},
                before={**insight.EMPTY_SNAPSHOT, "label": out["label"], "users": 0})
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
    if body.get("traits") is not None or body.get("base_role") is not None:   # PR-T4 — cakupan data ≤ milik pelaku
        from services.data_scope import assert_may_grant_scope
        await svc.sync_registry()   # PR-T6 — juga sifat yang ikut berganti bersama peran dasar
        assert_may_grant_scope(actor, svc.projected_scope_after(rid, body.get("traits"), body.get("base_role")))
    before = await insight.snapshot(rid)   # PR-T6 — potret untuk Riwayat peran
    out = await svc.update_role(rid, body)
    await audit(actor["name"], "role_access_updated", "custom_role", rid,
                {**await insight.snapshot(rid), "label": out["label"], "changes": out.get("changes", {}),
                 "users": out["users"]},
                before={**before, "label": out["label"], "users": out["users"]})
    return out


class FollowBaseBody(BaseModel):
    resources: Optional[List[str]] = None   # kosong = semua izin tertunda


@router.post("/roles/{rid}/follow-base")
async def follow_base(rid: str, payload: FollowBaseBody, request: Request) -> Dict[str, Any]:
    """PR-T9 — peran kustom mengikuti izin baru peran dasarnya yang tertunda."""
    actor = await require_permission(request, "permission", "update")
    if rid == actor.get("role") and actor.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Anda tidak bisa mengubah hak akses peran Anda sendiri — "
                                                    "minta Admin melakukannya.")
    from services.access_guard import assert_can_shape_role   # PR-T1
    preview = await svc.follow_base(rid, payload.resources, dry_run=True)
    await assert_can_shape_role(actor, current_perms=await svc.current_permissions(rid),
                                new_perms=preview["permissions"], new_cross_entity=None, role_label=_label(rid))
    before = await insight.snapshot(rid)   # PR-T6
    out = await svc.follow_base(rid, payload.resources)
    await audit(actor["name"], "role_followed_base", "custom_role", rid,
                {**await insight.snapshot(rid), "label": out["label"], "added": out.get("added", {}), "users": out["users"]},
                before={**before, "label": out["label"], "users": out["users"]})
    return out


@router.post("/roles/{rid}/reset")
async def reset_role(rid: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "permission", "update")
    from permissions_config import DEFAULT_PERMISSIONS
    from services.access_guard import assert_can_shape_role   # PR-T1
    await assert_can_shape_role(actor, current_perms=await svc.current_permissions(rid),
                                new_perms=DEFAULT_PERMISSIONS.get(rid, {}), new_cross_entity=None, role_label=_label(rid))
    before = await insight.snapshot(rid)   # PR-T6
    out = await svc.reset_builtin(rid)
    await audit(actor["name"], "role_access_reset", "custom_role", rid,
                {**await insight.snapshot(rid), "label": out["label"], "users": out["users"]},
                before={**before, "label": out["label"], "users": out["users"]})
    return out


@router.delete("/roles/{rid}")
async def delete_role(rid: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "permission", "update")
    from services.access_guard import assert_can_shape_role   # PR-T1
    await assert_can_shape_role(actor, current_perms=await svc.current_permissions(rid), new_perms={},
                                new_cross_entity=None, role_label=_label(rid))
    before = {**await insight.snapshot(rid), "label": _label(rid), "users": 0}   # PR-T6
    out = await svc.delete_custom(rid)
    await audit(actor["name"], "custom_role_deleted", "custom_role", rid,
                {**insight.EMPTY_SNAPSHOT, **out, "label": before["label"], "users": 0}, before=before)
    return out

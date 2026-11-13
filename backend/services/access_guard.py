"""PR-T1 — penjaga KENAIKAN HAK lewat kelola akun dan kelola peran (docs/blueprint/02_STANDAR.md §3.3 E1–E4).

Peran yang diberi wewenang mengelola akun/peran (mis. "Admin HR") tidak boleh:
  * mengelola akun yang perannya di luar daftar `permission_settings.assignable_roles[<peran pelaku>]`
    (termasuk menjadikan dirinya/orang lain Admin, atau mereset sandi Admin);
  * merakit atau mengubah peran yang aksesnya melebihi akses pelaku sendiri, atau memberi akses lintas PT
    yang pelaku sendiri tidak punya.
Admin dikecualikan dari semua pemeriksaan ini (tidak mungkin terkunci keluar).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import HTTPException

from db import db

ADMIN = "admin"


def _is_admin(actor: Dict[str, Any]) -> bool:
    return (actor or {}).get("role") == ADMIN


async def _settings() -> Dict[str, Any]:
    return await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "assignable_roles": 1,
                                                                     "matrix": 1}) or {}


async def assignable_map() -> Dict[str, List[str]]:
    return dict((await _settings()).get("assignable_roles") or {})


async def manageable_roles(actor: Dict[str, Any]) -> Optional[Set[str]]:
    """`None` = semua (Admin). Selain itu himpunan peran yang akunnya boleh dikelola pelaku."""
    if _is_admin(actor):
        return None
    return set((await assignable_map()).get(actor.get("role", ""), []) or []) - {ADMIN}


def _label(role: str) -> str:
    import role_registry as reg
    return reg.role_label(role) or role


async def assert_can_manage_account(actor: Dict[str, Any], *, target_user: Optional[Dict[str, Any]] = None,
                                    new_role: Optional[str] = None) -> None:
    """403 bila peran akun sasaran atau peran baru di luar daftar kelola pelaku. Akun sendiri diperlakukan sama."""
    allowed = await manageable_roles(actor)
    if allowed is None:
        return
    if new_role == ADMIN:
        raise HTTPException(status_code=403, detail="Peran Admin hanya bisa diberikan oleh Admin.")
    for role in [r for r in ((target_user or {}).get("role"), new_role) if r]:
        if role not in allowed:
            raise HTTPException(status_code=403, detail=(
                f"Anda belum diberi wewenang mengelola akun berperan {_label(role)}. Minta Admin menambahkannya di "
                "Peran & Hak Akses."))


def excess(target_perms: Dict[str, List[str]], actor_perms: Dict[str, List[str]]) -> List[Tuple[str, str]]:
    """Pasangan (sumber daya, aksi) yang ada di sasaran dan tidak ada di pelaku."""
    out: List[Tuple[str, str]] = []
    for res, acts in (target_perms or {}).items():
        have = set((actor_perms or {}).get(res) or [])
        out += [(res, a) for a in (acts or []) if a not in have]
    return sorted(out)


def _module_label(resource: str) -> str:
    from access_modules import MODULE_CATALOG
    for m in MODULE_CATALOG:
        if resource in (m.get("resources") or []):
            return m.get("label", resource)
    return resource


async def actor_perms(actor: Dict[str, Any]) -> Dict[str, List[str]]:
    from dependencies import permission_matrix
    return (await permission_matrix()).get(actor.get("role", ""), {}) or {}


async def assert_can_shape_role(actor: Dict[str, Any], *, current_perms: Optional[Dict[str, List[str]]],
                                new_perms: Dict[str, List[str]], new_cross_entity: Optional[bool],
                                role_label: str = "") -> None:
    """403 bila peran yang diubah (sekarang atau hasilnya) memegang akses yang pelaku tidak punya."""
    if _is_admin(actor):
        return
    mine = await actor_perms(actor)
    if current_perms is not None and excess(current_perms, mine):
        raise HTTPException(status_code=403, detail=(
            f"Peran {role_label or 'ini'} memiliki akses lebih luas dari peran Anda, jadi hanya bisa diubah Admin."))
    lebih = excess(new_perms or {}, mine)
    if lebih:
        raise HTTPException(status_code=403, detail=(
            f"Peran ini akan memiliki akses yang Anda sendiri tidak punya ({len(lebih)} akses, mis. "
            f"{_module_label(lebih[0][0])}). Minta Admin yang mengaturnya."))
    if new_cross_entity:
        import role_registry as reg
        if not (reg.ROLES.get(actor.get("role", "")) or {}).get("cross_entity"):
            raise HTTPException(status_code=403,
                                detail="Akses ke semua PT hanya bisa diberikan oleh peran yang juga memilikinya.")


async def can_manage_role(actor: Dict[str, Any], perms: Dict[str, List[str]], rid: str) -> bool:
    """Untuk layar: bolehkah pelaku mengubah peran ini (tanpa melempar)."""
    if _is_admin(actor):
        return rid != ADMIN
    if rid in (ADMIN, actor.get("role")):
        return False
    return not excess(perms or {}, await actor_perms(actor))

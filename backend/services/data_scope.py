"""PR-T4 — CAKUPAN DATA per peran: dokumen ber-pemilik siapa yang terlihat dan bisa diubah (di dalam PT yang boleh
dibuka). Sumbernya sifat peran `data_scope` (`role_registry.data_scope_of`, diatur di Peran & Hak Akses), bukan
daftar nama peran (`02_STANDAR.md` §3.1 Z5).

  milik_sendiri  → hanya dokumen yang pemiliknya pelaku
  tim            → milik sendiri + milik akun yang karyawannya berada di unit organisasi yang dikepalai karyawan
                   pelaku (`hr_org_units.head_employee_id`, tautan akun–karyawan `hr_employees.user_id`)
  semua          → tanpa saringan pemilik

`owner_ids(actor)` = `None` (semua) atau daftar id akun pemilik yang boleh. Pemanggil sinkron memakai
`owner_ids_now(actor)`: daftar tim diambil dari tembolok permintaan yang diisi `prime(actor)` (dipanggil
`dependencies.current_user`); tanpa tembolok, "tim" = milik sendiri (lebih sempit, tidak pernah lebih luas).
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

import role_registry as reg
from db import db

NO_OWNER = "__tanpa_pemilik__"
#: id akun pelaku → id anggota timnya (per permintaan; diganti utuh tiap `prime`).
_TIM: ContextVar[Dict[str, List[str]]] = ContextVar("prt4_tim", default={})


def scope_of(actor: Optional[Dict[str, Any]]) -> str:
    return reg.data_scope_of(str((actor or {}).get("role") or ""))


def own_scoped(actor: Optional[Dict[str, Any]]) -> bool:
    """Benar bila cakupan data peran pelaku bukan "semua"."""
    return scope_of(actor) != "semua"


async def team_member_ids(user_id: str) -> List[str]:
    """Id akun anggota unit organisasi yang dikepalai karyawan milik akun `user_id` (tanpa dirinya)."""
    if not user_id:
        return []
    emp_ids = await db.hr_employees.distinct("id", {"user_id": user_id})
    if not emp_ids:
        return []
    units = await db.hr_org_units.distinct("id", {"head_employee_id": {"$in": emp_ids}})
    if not units:
        return []
    units += [u for u in await db.hr_org_units.distinct("id", {"parent_id": {"$in": units}}) if u not in units]
    members = await db.hr_employees.distinct("user_id", {"$or": [{"department_id": {"$in": units}},
                                                                  {"position_id": {"$in": units}}]})
    return sorted({m for m in members if m and m != user_id})


async def owner_ids(actor: Optional[Dict[str, Any]]) -> Optional[List[str]]:
    """`None` = semua; `[id pelaku]` = milik sendiri; `[id pelaku, id anggota tim…]` = tim."""
    scope = scope_of(actor)
    if scope == "semua":
        return None
    uid = str((actor or {}).get("id") or "") or NO_OWNER
    if scope != "tim" or uid == NO_OWNER:
        return [uid]
    cache = _TIM.get()
    if uid not in cache:
        cache = {**cache, uid: await team_member_ids(uid)}
        _TIM.set(cache)
    return [uid, *cache[uid]]


def owner_ids_now(actor: Optional[Dict[str, Any]]) -> Optional[List[str]]:
    """Versi sinkron `owner_ids` (tim dari tembolok `prime`; tanpa tembolok = milik sendiri)."""
    scope = scope_of(actor)
    if scope == "semua":
        return None
    uid = str((actor or {}).get("id") or "") or NO_OWNER
    team = _TIM.get().get(uid) if scope == "tim" else None
    return [uid, *(team or [])]


async def prime(actor: Optional[Dict[str, Any]]) -> None:
    """Siapkan tembolok tim untuk permintaan ini (hanya bila cakupan pelaku "tim"; selain itu dikosongkan)."""
    _TIM.set({})
    if scope_of(actor) == "tim":
        await owner_ids(actor)


async def owns(actor: Optional[Dict[str, Any]], owner_id: Optional[str]) -> bool:
    """Benar bila cakupan pelaku "semua" atau `owner_id` termasuk pemilik yang boleh."""
    ids = await owner_ids(actor)
    return ids is None or str(owner_id or "") in ids


def owns_now(actor: Optional[Dict[str, Any]], owner_id: Optional[str]) -> bool:
    ids = owner_ids_now(actor)
    return ids is None or str(owner_id or "") in ids


def in_clause(ids: List[str]) -> Any:
    """Nilai kueri Mongo untuk "pemilik termasuk `ids`" (satu id → persis, supaya kueri lama tetap sama)."""
    return ids[0] if len(ids) == 1 else {"$in": list(ids)}


SCOPE_TOO_WIDE = "Anda tidak bisa memberi cakupan data lebih luas dari cakupan peran Anda sendiri."


def assert_may_grant_scope(actor: Dict[str, Any], scope: Optional[str]) -> None:
    """403 bila pelaku bukan Admin dan `scope` lebih luas dari cakupan perannya (`milik_sendiri` < `tim` < `semua`)."""
    from services.access_guard import _is_admin   # PR-T1 — Admin dikecualikan dari penjaga kenaikan hak
    if not scope or _is_admin(actor):
        return
    order = reg.DATA_SCOPES
    mine = scope_of(actor)
    if scope in order and mine in order and order.index(scope) > order.index(mine):
        raise HTTPException(status_code=403, detail=SCOPE_TOO_WIDE)

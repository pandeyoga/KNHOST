"""IMP-20 (P01) — cakupan LOKASI KERJA pengguna gudang (site → gudang).

Berbeda dari pemilik stok (`owner_entity_id`) dan hak pakai gudang shared/dedicated
(`warehouse_scope_service`). Penugasan: `users.location_site_ids` (semua gudang di site)
dipersempit opsional oleh `users.location_warehouse_ids`. Operator tanpa penugasan
tidak melihat pekerjaan gudang mana pun saat pembatasan aktif. Supervisor (DEC-09)
melihat semua lokasi dan boleh mengambil alih tugas dengan alasan tercatat.
"""
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db

SETTING_KEY = "wms.location_scope_enforced"
SCOPED_ROLES = {"warehouse"}
SUPERVISOR_ROLES = {"warehouse_admin", "manager", "admin"}
WAREHOUSE_FIELDS: Dict[str, tuple] = {
    "wms_tasks": ("warehouse_id",), "shipments": ("warehouse_id",),
    "inventory_rolls": ("warehouse_id",), "inventory_movements": ("warehouse_id",),
    "inventory_balances": ("warehouse_id",), "goods_receipts": ("warehouse_id",),
    "warehouse_transfers": ("source_warehouse_id", "dest_warehouse_id"),
}
_CACHE: Dict[str, Any] = {"at": 0.0, "on": False}


def invalidate() -> None:
    _CACHE["at"] = 0.0


async def enforced() -> bool:
    if time.monotonic() - _CACHE["at"] > 15:
        from services.config_resolver import value_of
        _CACHE["on"] = bool(await value_of(SETTING_KEY))
        _CACHE["at"] = time.monotonic()
    return _CACHE["on"]


def is_supervisor(user: Dict[str, Any]) -> bool:
    return (user or {}).get("role") in SUPERVISOR_ROLES


async def warehouse_ids_for(user: Dict[str, Any]) -> Optional[List[str]]:
    """None = tanpa batas lokasi; [] = tidak ada lokasi; selain itu daftar gudang."""
    if (user or {}).get("role") not in SCOPED_ROLES or not await enforced():
        return None
    sites = user.get("location_site_ids") or []
    whs = user.get("location_warehouse_ids") or []
    if not sites:
        return list(whs)
    ids = [w["id"] async for w in db.warehouses.find({"site_id": {"$in": sites}}, {"_id": 0, "id": 1})]
    return [w for w in ids if w in whs] if whs else ids


def query_for(collection: str, ids: Optional[List[str]]) -> Optional[Dict[str, Any]]:
    fields = WAREHOUSE_FIELDS.get(collection)
    if ids is None or not fields:
        return None
    ors = [{f: {"$in": ids}} for f in fields]
    return ors[0] if len(ors) == 1 else {"$or": ors}


def narrow(collection: str, query: Dict[str, Any], ids: Optional[List[str]]) -> Dict[str, Any]:
    wq = query_for(collection, ids)
    if not wq:
        return query
    q = dict(query or {})
    q["$and"] = [*(q.get("$and") or []), wq]
    return q


def doc_in_scope(collection: str, doc: Dict[str, Any], ids: Optional[List[str]]) -> bool:
    fields = WAREHOUSE_FIELDS.get(collection)
    if ids is None or not fields or not doc:
        return True
    vals = [doc.get(f) for f in fields if doc.get(f)]
    return not vals or any(v in ids for v in vals)


async def assert_warehouse(user: Dict[str, Any], warehouse_id: str, action: str = "mengerjakan ini") -> None:
    ids = await warehouse_ids_for(user)
    if ids is None or not warehouse_id or warehouse_id in ids:
        return
    wh = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0, "name": 1, "code": 1}) or {}
    raise HTTPException(status_code=403, detail=(
        f"Gudang {wh.get('name') or warehouse_id} di luar lokasi tugas Anda — Anda tidak bisa {action}. "
        "Minta supervisor gudang mengambil alih atau admin menambah penugasan lokasi Anda."))


async def summary(user: Dict[str, Any]) -> Dict[str, Any]:
    ids = await warehouse_ids_for(user)
    on = await enforced()
    sites = [s.get("name") async for s in db.warehouse_sites.find(
        {"id": {"$in": user.get("location_site_ids") or []}}, {"_id": 0, "name": 1})]
    whs = [] if ids is None else [w.get("code") or w.get("name") async for w in db.warehouses.find(
        {"id": {"$in": ids}}, {"_id": 0, "code": 1, "name": 1})]
    return {"enforced": on, "role": user.get("role"), "supervisor": is_supervisor(user),
            "restricted": ids is not None, "sites": sites, "warehouses": whs,
            "warehouse_ids": ids, "no_assignment": ids == []}


async def validate_assignment(site_ids: List[str], warehouse_ids: List[str]) -> Dict[str, List[str]]:
    site_ids = [s for s in dict.fromkeys(site_ids or []) if s]
    warehouse_ids = [w for w in dict.fromkeys(warehouse_ids or []) if w]
    known_sites = {s["id"] async for s in db.warehouse_sites.find({"id": {"$in": site_ids}}, {"_id": 0, "id": 1})}
    if set(site_ids) - known_sites:
        raise HTTPException(status_code=400, detail=f"Site tidak dikenal: {sorted(set(site_ids) - known_sites)}")
    whs = {w["id"]: w async for w in db.warehouses.find({"id": {"$in": warehouse_ids}}, {"_id": 0, "id": 1, "site_id": 1, "name": 1})}
    if set(warehouse_ids) - set(whs):
        raise HTTPException(status_code=400, detail=f"Gudang tidak dikenal: {sorted(set(warehouse_ids) - set(whs))}")
    if site_ids:
        outside = [w["name"] for w in whs.values() if w.get("site_id") not in site_ids]
        if outside:
            raise HTTPException(status_code=400, detail=(
                f"Gudang {', '.join(outside)} tidak berada di site yang ditugaskan. "
                "Penyempitan gudang hanya boleh di dalam site terpilih."))
    return {"location_site_ids": site_ids, "location_warehouse_ids": warehouse_ids}

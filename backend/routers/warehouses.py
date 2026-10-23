"""Warehouses router: CRUD warehouses + geolocation + lokasi (Zone→Rack→Level→Bin).

FASE E-4 (E4.1) — **mode pemakaian gudang**: `shared` (bersama semua badan usaha)
atau `dedicated` (khusus `entity_ids`). Aturan & pagarnya SATU tempat:
`services/warehouse_scope_service.py`.

Yang berubah di sini:
  · `GET /warehouses` mengirim daftar yang **sudah tersaring** untuk badan usaha
    aktif → seluruh pemilih gudang di aplikasi (penerimaan, kirim, transfer, stok,
    opname) ikut benar tanpa menyentuh 20 layar satu per satu.
    `?scope=all` (admin/manager) untuk layar MASTER yang memang harus melihat semua.
  · `POST /warehouses` bawaannya **khusus badan usaha aktif** (keputusan pemilik):
    gudang baru harus sengaja dibuka bila mau dipakai bersama.
  · `PATCH` boleh mengubah mode, TAPI ditolak bila membuat stok badan usaha lain
    terkurung (`dedication_blockers`) — pesannya menyebut jumlah roll & pemiliknya.
  · `GET /warehouses/{id}/occupancy` — isi gudang per badan usaha (dipakai layar
    master untuk menjelaskan kenapa sebuah perubahan ditolak).
"""
from services.wilayah_service import normalize_location, LOCATION_KEYS
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from pymongo import ReturnDocument

from core_utils import new_id, now_iso, safe_doc
from db import db
from dependencies import require_permission, audit
from entity_scope import entity_ctx
from schemas import GenericPatch, WarehousePayload
from services import warehouse_scope_service as whscope
from services.location_service import warehouse_locations, save_warehouse_structure

router = APIRouter(prefix="/api")

MASTER_SCOPE_ROLES = {"admin", "manager", "warehouse"}


class StructurePayload(BaseModel):
    zones: List[Dict[str, Any]] = []
    migration_reason: str = ""   # L10 LN-100-T03 — wajib bila bin berisi stok/tugas dipindah induk atau kapasitas di bawah isi


@router.get("/warehouses/{warehouse_id}/locations")
async def get_warehouse_locations(warehouse_id: str, request: Request, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """Fase 5 — hierarki lokasi + okupansi/utilisasi per bin (entity-scoped)."""
    actor = await require_permission(request, "warehouse", "view")
    from services import location_scope
    await location_scope.assert_warehouse(actor, warehouse_id, "membuka lokasi gudang ini")
    ctx = await entity_ctx(request)
    return await warehouse_locations(warehouse_id, ctx, entity_id)


def _owner_scope(ctx, owner: str) -> Optional[List[str]]:
    if owner and owner != "all":
        if not ctx.can_access(owner):
            raise HTTPException(status_code=403, detail="Badan usaha di luar akses Anda.")
        return [owner]
    return list(ctx.allowed_entity_ids or []) + [None, ""]


@router.get("/warehouses/{warehouse_id}/stock-tree")
async def get_stock_tree(warehouse_id: str, request: Request, owner: str = Query("")) -> Dict[str, Any]:
    """L10 LN-100/LN-102 — stok per Zona → Lemari → Rak → Bin dari saldo roll; induk = jumlah anak."""
    actor = await require_permission(request, "warehouse", "view")
    from services import location_scope, location_stock_tree as lst
    await location_scope.assert_warehouse(actor, warehouse_id, "membuka stok gudang ini")
    ctx = await entity_ctx(request)
    wh = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0})
    if not wh:
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    site = await db.warehouse_sites.find_one({"id": wh.get("site_id")}, {"_id": 0, "name": 1}) if wh.get("site_id") else None
    tree = await lst.warehouse_tree(wh, _owner_scope(ctx, owner), (site or {}).get("name", ""))
    return {"tree": tree, "buckets": lst.BUCKET_LABEL, "definitions": lst.DEFINITIONS}


@router.get("/warehouse-sites/{site_id}/stock-tree")
async def get_site_stock_tree(site_id: str, request: Request, owner: str = Query("")) -> Dict[str, Any]:
    """L10 LN-100 — satu Lokasi berisi beberapa gudang: total lokasi = jumlah gudang."""
    actor = await require_permission(request, "warehouse", "view")
    from services import location_scope, location_stock_tree as lst
    ctx = await entity_ctx(request)
    site = await db.warehouse_sites.find_one({"id": site_id}, {"_id": 0})
    if not site:
        raise HTTPException(status_code=404, detail="Lokasi tidak ditemukan")
    whs = []
    for wh in await db.warehouses.find({"site_id": site_id}, {"_id": 0}).sort("name", 1).to_list(100):
        try:
            await location_scope.assert_warehouse(actor, wh["id"], "membuka stok gudang ini")
            whs.append(wh)
        except HTTPException:
            continue
    tree = await lst.site_tree(site, whs, _owner_scope(ctx, owner))
    return {"tree": tree, "buckets": lst.BUCKET_LABEL, "definitions": lst.DEFINITIONS}


@router.get("/warehouses/{warehouse_id}/orphans")
async def get_orphan_rolls(warehouse_id: str, request: Request) -> Dict[str, Any]:
    """P02 (DEV-F02) — roll fisik yang bin-nya tidak ada di master gudang (tetap terhitung fisik)."""
    actor = await require_permission(request, "warehouse", "view")
    from services import location_scope
    from services.location_service import orphan_rolls
    await location_scope.assert_warehouse(actor, warehouse_id, "membuka lokasi gudang ini")
    ctx = await entity_ctx(request)
    rows = [r for r in await orphan_rolls(warehouse_id) if not r.get("owner_entity_id") or ctx.can_access(r["owner_entity_id"])]
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": list({r["product_id"] for r in rows})}}, {"_id": 0, "id": 1, "sku": 1, "name": 1}).to_list(2000)}
    for r in rows:
        p = prods.get(r["product_id"], {})
        r["sku"], r["product_name"] = p.get("sku", ""), p.get("name", "")
    from services.placement_rules import is_supervisor
    return {"count": len(rows), "rolls": rows, "can_edit_structure": is_supervisor(actor)}


@router.get("/warehouses/{warehouse_id}/occupancy")
async def get_warehouse_occupancy(warehouse_id: str, request: Request) -> Dict[str, Any]:
    """Isi gudang per badan usaha — supaya keputusan mode gudang tidak buta."""
    await require_permission(request, "warehouse", "view")
    wh = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0})
    if not wh:
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    rows = await whscope.occupancy_report(warehouse_id)
    return {
        "warehouse_id": warehouse_id,
        "warehouse_name": wh.get("name", ""),
        "sharing_mode": whscope.mode_of(wh),
        "entity_ids": whscope.dedicated_ids(wh),
        "owners": rows,
        "total_rolls": sum(r.get("rolls", 0) for r in rows),
    }


@router.put("/warehouses/{warehouse_id}/structure")
async def put_warehouse_structure(warehouse_id: str, payload: StructurePayload, request: Request) -> Dict[str, Any]:
    """Simpan struktur Zone→Rack→Level→Bin (node baru otomatis diberi id, kode bin wajib unik)."""
    actor = await require_permission(request, "warehouse", "update")
    ctx = await entity_ctx(request)
    from services import location_scope
    from services.placement_rules import assert_supervisor
    assert_supervisor(actor, "mengubah struktur gudang dan kapasitas bin")
    await location_scope.assert_warehouse(actor, warehouse_id, "menata struktur binnya")
    # E4.1 — menata bin di gudang badan usaha lain = ikut mengatur operasinya.
    await whscope.assert_usable(warehouse_id, ctx.active_entity_id,
                               action="menata struktur binnya")
    wh = await save_warehouse_structure(warehouse_id, payload.zones, migration_reason=payload.migration_reason,
                                        actor_name=actor["name"])
    await audit(actor["name"], "warehouse_structure_updated", "warehouse", warehouse_id,
                {"zones": len(payload.zones), "migration": (wh.get("_migration") or {}).get("id", "")},
                reason=payload.migration_reason)
    wh.pop("_migration", None)
    return safe_doc(wh)


@router.get("/warehouses")
async def list_warehouses(request: Request, scope: str = Query("usable"),
                          include_inactive: Optional[bool] = Query(None)) -> List[Dict[str, Any]]:
    """Gudang yang BOLEH dipakai badan usaha aktif (bawaan).

    INV-AUTH-01 (KN-076-AUTH-MASTER-LEAK P1): gudang+alamat WAJIB login.
    `scope=all` → seluruh gudang beserta lencana modenya (layar master).
    """
    actor = await require_permission(request, "warehouse", "view")
    ctx = await entity_ctx(request)
    want_all = str(scope or "").strip().lower() == "all"
    from role_registry import role_in
    # FE-05 — peran master (peran acuan dikenali). Peran lain memakai daftar bawaan (gudang yang boleh
    # dipakai PT aktif) — layar Data Gudang memintanya tanpa `scope=all`; seluruh gudang tidak dibuka.
    if want_all and not role_in(actor.get("role"), MASTER_SCOPE_ROLES):
        raise HTTPException(status_code=403,
                            detail="Hanya admin/manajer/gudang yang boleh melihat seluruh gudang.")
    return await whscope.list_for_entity(
        ctx.active_entity_id,
        include_unusable=want_all,
        # UAT 24 Okt (P9) — pemilih gudang (PO/PR/GRN/transfer…) dulu ikut menawarkan gudang NONAKTIF (WH-BDG dkk.).
        # Bawaan kini: daftar "usable" hanya gudang aktif; layar master (`scope=all`) tetap melihat semuanya.
        only_active=not (include_inactive if include_inactive is not None else want_all))


@router.post("/warehouses")
async def create_warehouse(payload: WarehousePayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "warehouse", "create")
    ctx = await entity_ctx(request)
    if await db.warehouses.find_one({"code": payload.code}, {"_id": 0}):
        raise HTTPException(status_code=409, detail="Kode gudang sudah digunakan")
    # Keputusan pemilik: gudang BARU bawaannya KHUSUS badan usaha aktif — harus
    # sengaja dibuka kalau memang mau dipakai bersama.
    mode = (payload.sharing_mode or whscope.DEDICATED).strip().lower()
    ents = list(payload.entity_ids or [])
    if mode == whscope.DEDICATED and not ents:
        if not ctx.active_entity_id:
            raise HTTPException(status_code=400,
                                detail="Pilih badan usaha dulu sebelum membuat gudang khusus.")
        ents = [ctx.active_entity_id]
    if mode == whscope.SHARED:
        ents = []
    whscope.validate_mode(mode, ents)
    await whscope.assert_entities_exist(ents)
    for eid in ents:
        if eid not in ctx.allowed_entity_ids:
            raise HTTPException(status_code=403,
                                detail="Tidak berwenang menugaskan gudang ke badan usaha itu.")
    warehouse_id = new_id("wh")
    zone_id = new_id("zone")
    rack_id = new_id("rack")
    bin_id = new_id("bin")
    warehouse = {
        "id": warehouse_id,
        "code": payload.code,
        "name": payload.name,
        "city": payload.city,
        **normalize_location(payload.model_dump()),
        "lat": payload.lat,
        "lng": payload.lng,
        "sharing_mode": mode,
        "entity_ids": ents,
        "zones": [{"id": zone_id, "name": "Zone A", "racks": [{"id": rack_id, "name": "Rack A1",
                    "bins": [{"id": bin_id, "code": payload.bin_code, "capacity": payload.bin_capacity}]}]}],
        "active": True,
        "created_at": now_iso(),
    }
    await db.warehouses.insert_one(dict(warehouse))
    await audit(actor["name"], "warehouse_created", "warehouse", warehouse_id, warehouse)
    names = await whscope.entity_name_map()
    return whscope.decorate(safe_doc(warehouse), names, ctx.active_entity_id)


@router.patch("/warehouses/{warehouse_id}")
async def update_warehouse(warehouse_id: str, payload: GenericPatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "warehouse", "update")
    ctx = await entity_ctx(request)
    current = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0})
    if not current:
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    allowed = ["code", "name", "city", *LOCATION_KEYS, "zones", "active", "lat", "lng",
               "sharing_mode", "entity_ids", "loading_check_policy",
               # FASE R0 — profil gudang (site, peran, rules, gate)
               "site_id", "roles", "storage_rules", "gate_config"]
    data = {k: v for k, v in payload.data.items() if k in allowed}
    if "loading_check_policy" in data and data["loading_check_policy"] not in ("optional", "required"):
        raise HTTPException(status_code=400, detail="Kebijakan loading check harus 'optional' atau 'required'.")
    if any(k in data for k in LOCATION_KEYS):
        data.update(normalize_location({**{k: current.get(k, "") for k in LOCATION_KEYS}, **{k: v for k, v in data.items() if k in LOCATION_KEYS}}))
    # FASE R0 — validasi & normalisasi profil
    from services import warehouse_profile_service as whp
    profile_keys = {"site_id", "roles", "storage_rules", "gate_config"} & set(data.keys())
    if profile_keys:
        prof = whp.validate_profile({k: data[k] for k in profile_keys})
        if "site_id" in prof:
            await whp.assert_site_exists(prof["site_id"])
        data.update(prof)
    if data.get("code"):
        duplicate = await db.warehouses.find_one(
            {"code": data["code"], "id": {"$ne": warehouse_id}}, {"_id": 0}
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Kode gudang sudah digunakan")

    # E4.1 — mode pemakaian: divalidasi bentuknya, lalu diuji dampaknya ke stok.
    if "sharing_mode" in data or "entity_ids" in data:
        mode = str(data.get("sharing_mode", whscope.mode_of(current))).strip().lower()
        ents = list(data.get("entity_ids", whscope.dedicated_ids(current)) or [])
        if mode == whscope.SHARED:
            ents = []
        whscope.validate_mode(mode, ents)
        await whscope.assert_entities_exist(ents)
        if mode == whscope.DEDICATED:
            for eid in ents:
                if eid not in ctx.allowed_entity_ids:
                    raise HTTPException(
                        status_code=403,
                        detail="Tidak berwenang menugaskan gudang ke badan usaha itu.")
            verdict = await whscope.dedication_blockers(warehouse_id, ents)
            if verdict["blocked"]:
                raise HTTPException(status_code=409, detail=verdict["message"])
        data["sharing_mode"] = mode
        data["entity_ids"] = ents

    data["updated_at"] = now_iso()
    warehouse = await db.warehouses.find_one_and_update(
        {"id": warehouse_id}, {"$set": data},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not warehouse:
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    await audit(actor["name"], "warehouse_updated", "warehouse", warehouse_id, warehouse)
    names = await whscope.entity_name_map()
    return whscope.decorate(safe_doc(warehouse), names, ctx.active_entity_id)


@router.delete("/warehouses/{warehouse_id}")
async def delete_warehouse(warehouse_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "warehouse", "delete")
    warehouse = await db.warehouses.find_one_and_update(
        {"id": warehouse_id},
        {"$set": {"active": False, "updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER
    )
    if not warehouse:
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    await audit(actor["name"], "warehouse_deactivated", "warehouse", warehouse_id, warehouse)
    return safe_doc(warehouse)

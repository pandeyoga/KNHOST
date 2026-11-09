"""FIX-2 — API "dua angka" stok (LOKAL + GLOBAL) + rincian saat diminta + site POS tersimpan di server.

* GET `/api/stock/figures?product_ids=a,b[&site_id=]` → {scope, definitions, items: {pid: {unit, local, global}}}
* GET `/api/stock/figures/{product_id}[?site_id=]` → rincian: per site/gedung, per PT, per status, akan datang, ATP
* GET/PUT `/api/stock/my-site` → site POS pilihan pengguna (keputusan B3a #3 — dulu hanya `sessionStorage` klien)

Angka dari SATU layanan `services/stock_figures.py`. `site_id` hanya mengubah cakupan TAMPILAN angka LOKAL (bukan
pagar akses); rincian PT di luar izin pengguna tetap tampil sebagai angka tanpa dokumen roll/HPP (keputusan B3a #7).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from db import db
from core_utils import now_iso
from dependencies import current_user, require_permission
from entity_scope import entity_ctx
from services import stock_figures as sf

router = APIRouter(prefix="/api")


async def _site_or_400(site_id: str) -> str:
    site_id = (site_id or "").strip()
    if site_id and not await db.warehouse_sites.find_one({"id": site_id}, {"_id": 1}):
        raise HTTPException(status_code=400, detail=f"Site tidak dikenal: {site_id}")
    return site_id


@router.get("/stock/figures")
async def stock_figures(request: Request, product_ids: str = Query("", description="koma; wajib"),
                        site_id: Optional[str] = Query(None), entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    await require_permission(request, "product", "view")
    ids: List[str] = [x.strip() for x in (product_ids or "").split(",") if x.strip()][:1000]
    if not ids:
        raise HTTPException(status_code=400, detail="Isi product_ids (dipisah koma).")
    ctx = await entity_ctx(request)
    if entity_id and entity_id != "all" and entity_id not in (ctx.allowed_entity_ids or []):
        raise HTTPException(status_code=403, detail="Tidak berwenang atas entitas ini")
    scope = await sf.viewer_scope(ctx, site_id=await _site_or_400(site_id or ""), entity_id=entity_id or "")
    return {"scope": sf.scope_public(scope), "definitions": sf.DEFINITIONS,
            "items": await sf.figures_for(ids, scope)}


@router.get("/stock/figures/{product_id}")
async def stock_figures_detail(product_id: str, request: Request, site_id: Optional[str] = Query(None),
                               entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "view")
    prod = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not prod:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    from services import line_scope
    line_scope.assert_can_touch(actor, prod, what=f"Produk '{prod.get('name', product_id)}'")
    ctx = await entity_ctx(request)
    if entity_id and entity_id != "all" and entity_id not in (ctx.allowed_entity_ids or []):
        raise HTTPException(status_code=403, detail="Tidak berwenang atas entitas ini")
    scope = await sf.viewer_scope(ctx, site_id=await _site_or_400(site_id or ""), entity_id=entity_id or "")
    return await sf.detail(product_id, scope, visible_entity_ids=list(ctx.allowed_entity_ids or []))


class MySiteIn(BaseModel):
    site_id: str = ""


@router.get("/stock/my-site")
async def get_my_site(request: Request) -> Dict[str, Any]:
    user = await current_user(request)
    sid = user.get("pos_site_id") or ""
    site = await db.warehouse_sites.find_one({"id": sid}, {"_id": 0, "id": 1, "name": 1}) if sid else None
    return {"site_id": sid if site else "", "site_name": (site or {}).get("name", ""),
            "home_site_ids": user.get("location_site_ids") or []}


@router.put("/stock/my-site")
async def put_my_site(payload: MySiteIn, request: Request) -> Dict[str, Any]:
    """Simpan lokasi jualan (POS/HP) pengguna di server — dipakai angka LOKAL & bawaan "Mulai jualan"."""
    user = await current_user(request)
    sid = await _site_or_400(payload.site_id)
    await db.users.update_one({"id": user["id"]}, {"$set": {"pos_site_id": sid, "pos_site_updated_at": now_iso()}})
    site = await db.warehouse_sites.find_one({"id": sid}, {"_id": 0, "name": 1}) if sid else None
    return {"site_id": sid, "site_name": (site or {}).get("name", "")}

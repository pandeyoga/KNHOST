"""F-4b — POS advanced recommendations router (best-seller, FBT, substitutes). Read-only."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from dependencies import require_permission
from services import pos_recommendation_service as pos_svc

router = APIRouter(prefix="/api")


async def _scope(request: Request, entity_id: Optional[str]) -> List[str]:
    """GN-10 — entity_id query diresolusi lewat izin entitas pemanggil."""
    from entity_scope import entity_ctx, resolve_scope_ids
    return resolve_scope_ids(await entity_ctx(request), entity_id)


@router.get("/pos/site-stock")
async def get_site_stock(
    request: Request,
    site_id: str = Query(...),
    entity_id: Optional[str] = Query(None),
    product_ids: str = Query("", description="koma; kosong = semua produk ber-stok di lokasi itu"),
) -> Dict[str, Any]:
    """UAT 24 Okt (P8) — stok per LOKASI untuk katalog POS/HP: milik PT penjual vs PT lain grup, satuan per produk."""
    await require_permission(request, "order", "view")
    from entity_scope import entity_ctx
    from services import site_stock_service as sss
    ent = entity_id or (await entity_ctx(request)).active_entity_id
    ids = [x for x in (product_ids or "").split(",") if x.strip()]
    return {"site_id": site_id, "entity_id": ent, "stock": await sss.site_stock(site_id, ent, ids or None)}


async def _active_entity(request: Request, entity_id: Optional[str]) -> str:
    from entity_scope import entity_ctx
    return entity_id if entity_id and entity_id != "all" else (await entity_ctx(request)).active_entity_id or ""


@router.get("/pos/highlights-config")
async def get_highlights_config(request: Request, entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """UAT 24 Okt (P12.1) — sorotan POS mana yang menyala untuk PT ini (Pusat Pengaturan › Tampilan, kunci `pos.*`)."""
    await require_permission(request, "order", "view")
    return await pos_svc.highlights_config(await _active_entity(request, entity_id))


@router.get("/pos/best-sellers")
async def get_best_sellers(
    request: Request,
    entity_id: Optional[str] = Query(None),
    limit: int = Query(8, ge=1, le=30),
    customer_id: str = Query(""),
) -> List[Dict[str, Any]]:
    # INV-AUTH-01 (KN-076-AUTH-MASTER-LEAK P1): analitik penjualan WAJIB login.
    await require_permission(request, "order", "view")
    # UAT 24 Okt (P12.2) — bisa dimatikan; hanya N hari terakhir; produk yang tak boleh dipesan pelanggan aktif disaring.
    cfg = (await pos_svc.highlights_config(await _active_entity(request, entity_id)))["best_sellers"]
    if not cfg["enabled"]:
        return []
    return await pos_svc.best_sellers(await _scope(request, entity_id), limit=limit, window_days=cfg["window_days"],
                                      customer_id=customer_id)


@router.get("/pos/featured")
async def get_featured(request: Request, entity_id: Optional[str] = Query(None), customer_id: str = Query(""),
                       limit: int = Query(12, ge=1, le=30)) -> List[Dict[str, Any]]:
    """UAT 24 Okt (P12.3) — strip Produk Unggulan (push) sampai `featured_until`."""
    await require_permission(request, "order", "view")
    if not (await pos_svc.highlights_config(await _active_entity(request, entity_id)))["featured"]["enabled"]:
        return []
    return await pos_svc.featured(customer_id, limit=limit)


@router.get("/pos/recommendations")
async def get_recommendations(request: Request, customer_id: str = Query(...), entity_id: Optional[str] = Query(None),
                              limit: int = Query(10, ge=1, le=30)) -> List[Dict[str, Any]]:
    """UAT 24 Okt (P12.4, keputusan P12-K1 b) — rekomendasi per pelanggan dari desain/kategori yang pernah dibeli."""
    await require_permission(request, "order", "view")
    if not (await pos_svc.highlights_config(await _active_entity(request, entity_id)))["recommendation"]["enabled"]:
        return []
    return await pos_svc.recommended_for_customer(customer_id, await _scope(request, entity_id), limit=limit)


class FeaturedBody(BaseModel):
    is_featured: bool
    rank: Optional[int] = Field(None, ge=0, le=999)
    until: str = ""          # YYYY-MM-DD; kosong = tanpa batas
    note: str = Field("", max_length=200)


@router.post("/pos/featured/{product_id}")
async def set_featured(product_id: str, payload: FeaturedBody, request: Request) -> Dict[str, Any]:
    """UAT 24 Okt (P12.3) — MD/Manajer menandai produk unggulan (push) di master produk."""
    actor = await require_permission(request, "product", "update")
    from db import db
    from dependencies import audit
    from core_utils import now_iso
    if payload.until and len(payload.until) != 10:
        raise HTTPException(status_code=400, detail="Tanggal akhir unggulan harus YYYY-MM-DD.")
    sets = {"is_featured": payload.is_featured, "featured_rank": payload.rank, "featured_until": payload.until or "",
            "featured_note": payload.note.strip(), "featured_by": actor.get("name", ""), "updated_at": now_iso()}
    res = await db.products.update_one({"id": product_id}, {"$set": sets})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan.")
    await audit(actor.get("name", ""), "product_featured_set", "product", product_id, sets)
    return await db.products.find_one({"id": product_id}, {"_id": 0, "id": 1, "sku": 1, "name": 1, "is_featured": 1,
                                                           "featured_rank": 1, "featured_until": 1, "featured_note": 1})


@router.get("/pos/frequently-bought-together")
async def get_frequently_bought_together(
    request: Request,
    product_id: str = Query(...),
    entity_id: Optional[str] = Query(None),
    limit: int = Query(6, ge=1, le=20),
) -> List[Dict[str, Any]]:
    # INV-AUTH-01 (KN-076-AUTH-MASTER-LEAK P1): analitik penjualan WAJIB login.
    await require_permission(request, "order", "view")
    if not (await pos_svc.highlights_config(await _active_entity(request, entity_id)))["fbt"]["enabled"]:
        return []   # UAT 24 Okt (P12.1)
    return await pos_svc.frequently_bought_together(product_id, await _scope(request, entity_id), limit=limit)


@router.get("/pos/substitutes")
async def get_substitutes(
    request: Request,
    product_id: str = Query(...),
    entity_id: Optional[str] = Query(None),
    limit: int = Query(6, ge=1, le=20),
) -> List[Dict[str, Any]]:
    # INV-AUTH-01 (KN-076-AUTH-MASTER-LEAK P1): analitik penjualan WAJIB login.
    await require_permission(request, "order", "view")
    return await pos_svc.substitutes(product_id, await _scope(request, entity_id), limit=limit)

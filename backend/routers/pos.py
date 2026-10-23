"""F-4b — POS advanced recommendations router (best-seller, FBT, substitutes). Read-only."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request

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


@router.get("/pos/best-sellers")
async def get_best_sellers(
    request: Request,
    entity_id: Optional[str] = Query(None),
    limit: int = Query(8, ge=1, le=30),
) -> List[Dict[str, Any]]:
    # INV-AUTH-01 (KN-076-AUTH-MASTER-LEAK P1): analitik penjualan WAJIB login.
    await require_permission(request, "order", "view")
    return await pos_svc.best_sellers(await _scope(request, entity_id), limit=limit)


@router.get("/pos/frequently-bought-together")
async def get_frequently_bought_together(
    request: Request,
    product_id: str = Query(...),
    entity_id: Optional[str] = Query(None),
    limit: int = Query(6, ge=1, le=20),
) -> List[Dict[str, Any]]:
    # INV-AUTH-01 (KN-076-AUTH-MASTER-LEAK P1): analitik penjualan WAJIB login.
    await require_permission(request, "order", "view")
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

"""Costing router (EPIC3A) — endpoint WAC / margin per produk.

Akses: izin `costing.view` (PR-T2; bawaan admin + manager — sales tidak melihat HPP/biaya, konsisten EPIC1).
Respons: ARRAY/OBJEK telanjang (kontrak KN3).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, Query

from dependencies import require_permission
from services import costing_service

router = APIRouter(prefix="/api/costing")


@router.get("/wac")
async def list_wac(request: Request, entity_id: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """WAC + margin seluruh produk aktif. entity_id opsional (cost per entitas)."""
    await require_permission(request, "costing", "view")
    return await costing_service.wac_all(entity_id=entity_id)


@router.get("/wac/{product_id}")
async def get_wac(product_id: str, request: Request, entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """WAC + margin satu produk."""
    await require_permission(request, "costing", "view")
    return await costing_service.wac_for_product(product_id, entity_id=entity_id)

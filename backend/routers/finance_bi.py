"""FINANCE — BI Keuangan router.

Akses: permission module "accounting" (view). Respons OBJEK telanjang (KN3).
Ter-scope entitas (mengikuti header X-Entity-Id / param entity_id).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, Query

from dependencies import require_permission
from entity_scope import entity_ctx, resolve_list_scope, scope_meta
from services import finance_bi_service as bi
from services.book_date import tanggal_buku

router = APIRouter(prefix="/api")


@router.get("/finance/bi")
async def finance_bi_dashboard(
    request: Request,
    year: Optional[int] = Query(None, description="Tahun analisis (default: tahun berjalan)"),
    entity_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Dashboard BI Keuangan: tren bulanan, KPI YTD, rasio, perbandingan antar PT."""
    await require_permission(request, "accounting", "view")
    ctx = await entity_ctx(request)
    y = int(year) if year else int(tanggal_buku()[:4])   # tahun berjalan WIB (dulu UTC: 1 Jan 00–07 WIB = tahun lalu)

    scope = resolve_list_scope("journal_entries", {}, ctx, entity_id)

    if entity_id and entity_id != "all":
        comp_ids: List[str] = [entity_id]
    else:
        comp_ids = list(ctx.allowed_entity_ids)

    return {**(await bi.finance_bi(y, scope, comp_ids)), "scope_meta": await scope_meta(ctx, entity_id)}   # PK-16

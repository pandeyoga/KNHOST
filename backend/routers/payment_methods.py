"""PM-T1 — daftar induk cara bayar untuk layar (`docs/blueprint/unit/PM-T1.md`).

`GET /api/payment-methods?direction=&entity_id=` cukup login: data rujukan tanpa nominal (`02_STANDAR.md` §3.1 Z3,
`login_only_endpoints.LOGIN_ONLY`). Isi = cara bayar AKTIF untuk PT itu (baris khusus PT menang atas baris global).
Mengelola daftarnya lewat master berlapis `payment-methods` (`/api/entity-masters/payment-methods`, izin
`cash.configure`).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from entity_scope import entity_ctx, resolve_requested_entity
from services import payment_method_service as pms

router = APIRouter(prefix="/api")


@router.get("/payment-methods")
async def list_payment_methods(request: Request, direction: str = Query(""),
                               entity_id: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    ctx = await entity_ctx(request)   # login + PT dalam penugasan (403 bila PT lain)
    arah = (direction or "").strip().lower()
    if arah and arah not in pms.ARAH:
        raise HTTPException(status_code=400, detail="Arah cara bayar harus masuk atau keluar.")
    req = (entity_id or "").strip()
    eid = "" if (req == "all" or (not req and getattr(ctx, "view_all", False))) else resolve_requested_entity(ctx, req)
    return [pms.untuk_layar(r) for r in await pms.active_for(eid, arah)]

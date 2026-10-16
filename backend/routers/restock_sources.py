"""P05 IMP-19 — Sumber restock per artikel (dikelola MD)."""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from dependencies import audit, require_permission
from services import restock_source_service as svc

router = APIRouter(prefix="/api")


@router.get("/restock-sources")
async def list_sources(request: Request, q: str = "", status: str = "", limit: int = 100) -> Dict[str, Any]:
    await require_permission(request, "product", "view")
    return await svc.list_articles(q.strip(), status, max(1, min(limit, 500)))


@router.get("/product-templates/{template_id}/restock-source")
async def get_source(template_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "product", "view")
    doc = await svc.get(template_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Artikel tidak ditemukan")
    return doc


@router.put("/product-templates/{template_id}/restock-source")
async def put_source(template_id: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "update")
    try:
        doc = await svc.save(template_id, payload or {}, actor)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except svc.RestockRouteError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    await audit(actor.get("name", ""), "update", "restock_source", template_id,
                {"mode": (doc.get("restock_source") or {}).get("mode")})
    return doc

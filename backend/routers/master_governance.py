"""W2-REQ-02 — API tata kelola master produk (preview, batch, rollback, koreksi nama)."""
from typing import Any, Dict, List

from fastapi import APIRouter, Request

from dependencies import require_permission, audit
from services import master_governance_service as mg

router = APIRouter(prefix="/api")


@router.get("/master-governance/preview")
async def governance_preview(request: Request) -> Dict[str, Any]:
    await require_permission(request, "product", "update")
    return await mg.preview({})


@router.get("/master-governance/batches")
async def governance_batches(request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "product", "update")
    return await mg.list_batches()


@router.post("/master-governance/batches")
async def governance_apply(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "update")
    b = await mg.apply_batch({}, str(payload.get("preview_signature") or ""), list(payload.get("accepted") or []),
                             str(payload.get("note") or ""), actor)
    await audit(actor["name"], "master_governance_batch_applied", "master_governance_batch", b["id"],
                {"changes": len(b["changes"])})
    return b


@router.post("/master-governance/batches/{batch_id}/rollback")
async def governance_rollback(batch_id: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "update")
    b = await mg.rollback_batch(batch_id, str(payload.get("reason") or ""), actor)
    await audit(actor["name"], "master_governance_batch_rolled_back", "master_governance_batch", batch_id,
                {"restored": b.get("rollback_restored")}, reason=b.get("rollback_reason", ""))
    return b


@router.post("/products/{product_id}/rename")
async def product_rename(product_id: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "update")
    p = await mg.rename_product(product_id, str(payload.get("name") or ""), str(payload.get("reason") or ""), actor)
    await audit(actor["name"], "product_renamed", "product", product_id, {"name": p.get("name")},
                reason=str(payload.get("reason") or ""))
    return p

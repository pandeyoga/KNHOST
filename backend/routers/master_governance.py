"""W2-REQ-02 — API tata kelola master produk (preview, batch, rollback, koreksi nama).

PREP-A (K-OPN-06) — lembar perbaikan master produk (`/master-governance/cleanup/*`) + petunjuk SKU tergantikan.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, File, Request, Response, UploadFile

from core_utils import now_iso
from dependencies import require_permission, audit
from services import master_governance_service as mg

router = APIRouter(prefix="/api")
XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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


# ─── PREP-A (K-OPN-06) — lembar perbaikan master produk: unduh → unggah/pratinjau → terapkan → batalkan ───
@router.get("/master-governance/cleanup/sheet")
async def cleanup_sheet(request: Request, format: str = "xlsx") -> Response:
    actor = await require_permission(request, "product", "export")
    from services import master_cleanup_sheet as sh
    cols, rows, meta = await sh.build_rows(actor)
    stamp = now_iso()[:10]
    if format != "csv" and sh.XLSX_AVAILABLE:
        body, media, ext = sh.render_xlsx(cols, rows, meta), XLSX_MEDIA, "xlsx"
    else:
        body, media, ext = sh.render_csv(cols, rows), "text/csv; charset=utf-8", "csv"
    await audit(actor["name"], "master_cleanup_sheet_exported", "master_cleanup", "sheet",
                {"products": meta["products"], "format": ext})
    return Response(content=body, media_type=media, headers={
        "Content-Disposition": f"attachment; filename=perbaikan_master_produk_{stamp}.{ext}",
        "X-Sheet-Products": str(meta["products"])})


@router.post("/master-governance/cleanup/preview")
async def cleanup_preview(request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "update")
    from services import master_cleanup_sheet as sh
    from services import master_cleanup_validate as mv
    rows = sh.parse_sheet(await file.read(), file.filename or "")
    out = await mv.validate(actor, rows)
    out["source_filename"] = file.filename or ""
    out.pop("plan", None)   # rencana internal dihitung ulang di server saat Terapkan
    return out


@router.post("/master-governance/cleanup/apply")
async def cleanup_apply(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "update")
    from services import master_cleanup_service as mc
    b = await mc.apply_cleanup(actor, list(payload.get("actions") or []), str(payload.get("preview_signature") or ""),
                               str(payload.get("note") or ""), str(payload.get("source_filename") or ""))
    await audit(actor["name"], "master_cleanup_applied", "master_cleanup_batch", b["id"],
                {"status": b.get("status"), "changed": b.get("changed"), "failed": len(b.get("failed") or [])},
                reason=b.get("note", ""))
    for ch in b.get("changes") or []:   # jejak per SKU → tab "Riwayat Perubahan" katalog
        await audit(actor["name"], f"product_cleanup_{ch['tindakan'].lower()}", "product", ch["product_id"],
                    {k: ch.get(k) for k in ("tindakan", "new_sku", "target_sku", "after") if ch.get(k)},
                    reason=b.get("note", ""), before=ch.get("before"))
    return b


@router.get("/master-governance/cleanup/batches")
async def cleanup_batches(request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "product", "update")
    from services import master_cleanup_service as mc
    return await mc.list_cleanup_batches()


@router.get("/master-governance/cleanup/batches/{batch_id}")
async def cleanup_batch_detail(batch_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "product", "update")
    from services import master_cleanup_service as mc
    return await mc.get_cleanup_batch(batch_id)


@router.post("/master-governance/cleanup/batches/{batch_id}/rollback")
async def cleanup_rollback(batch_id: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "update")
    from services import master_cleanup_service as mc
    b = await mc.rollback_cleanup(batch_id, str(payload.get("reason") or ""), actor)
    await audit(actor["name"], "master_cleanup_rolled_back", "master_cleanup_batch", batch_id,
                {"done": len(b.get("rollback_done") or []), "skipped": len(b.get("rollback_skipped") or [])},
                reason=b.get("rollback_reason", ""))
    return b


@router.get("/master-governance/supersede-hint")
async def supersede_hint(request: Request, q: str = "") -> List[Dict[str, Any]]:
    """Pencarian dengan SKU lama → "SKU X digantikan oleh Y" (pemilih produk dokumen baru)."""
    actor = await require_permission(request, "product", "view")
    from services import product_supersede as ps
    from services.catalog_access import visible_query
    return await ps.hints(q, visible_query(actor))


@router.post("/products/{product_id}/rename")
async def product_rename(product_id: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "update")
    p = await mg.rename_product(product_id, str(payload.get("name") or ""), str(payload.get("reason") or ""), actor)
    await audit(actor["name"], "product_renamed", "product", product_id, {"name": p.get("name")},
                reason=str(payload.get("reason") or ""))
    return p


# ─── P01 IMP-14 — jejak pemakaian & hapus permanen master yang belum dipakai ───
@router.get("/master/usage/{kind}/{mid}")
async def master_usage(kind: str, mid: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "product", "view")
    from services import master_usage_service as mu
    return await mu.usage(kind, mid)


@router.delete("/master/{kind}/{mid}/purge")
async def master_purge(kind: str, mid: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "product", "view")
    from services import master_usage_service as mu
    res = await mu.purge(kind, mid, actor)
    await audit(actor["name"], "master_purged", kind, mid, res)
    return res

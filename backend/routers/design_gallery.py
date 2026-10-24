"""HRD H5 router — Design Gallery (motif kain) + upload gambar + AI auto-tag.

Koleksi kanonik (entity-scoped): design_gallery (dsgn_). Keputusan owner 3a.
RBAC: read list/detail/file = hr.view; create/update/delete/upload/autotag = hr.manage_attendance.
Auto-tag AI (Claude) GRACEFUL: bila key kosong → 200 {enabled:false} (BUKAN error).

Path aksi pakai segmen literal (/files, /autotag) agar verify_api_contract 0 ERROR.
"""
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request, Query, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel

from dependencies import require_permission, audit
from entity_scope import entity_ctx, resolve_list_scope, assert_entity_access
from schemas_design_gallery import (DesignAiIllustrateIn, DesignApproveIn, DesignRatingIn,
                                    DesignRejectIn, DesignTransitionIn, DesignVersionIn, GalleryInput,
                                    GalleryUpdate, IllustrationCommentIn)
from services import design_gallery_service as gallery
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api")


async def _perm_view(request: Request) -> Dict[str, Any]:
    """RBAC DUA DIVISI (FASE F): HRD (`hr.view`) **atau** R&D (`rnd.view`).

    Master desain dipakai dua divisi sekaligus — HRD (galeri motif/cerita) dan R&D
    (pattern untuk proofing). Memaksa satu izin akan mematikan salah satu alur,
    karena itu keduanya diterima. Tidak ada wewenang lama yang dicabut.
    """
    try:
        return await require_permission(request, "rnd", "view")
    except HTTPException:
        return await require_permission(request, "hr", "view")


async def _perm_manage(request: Request) -> Dict[str, Any]:
    """Tulis master desain: `rnd.manage` **atau** `hr.manage_attendance` (admin/manager)
    **atau** `design_request.deliver` (FASE D — peran `designer`).

    Kenapa izin ketiga ditambahkan: sejak FASE D desainer punya AKUN dan alur
    resminya adalah *ia sendiri* yang mengunggah karyanya lalu menyerahkannya
    (`POST /design-requests/{id}/deliver`). Tanpa pintu ini, satu-satunya cara
    mengunggah artwork adalah lewat admin — dan rapor desainer akan mencatat
    pekerjaan orang lain. Wewenang lama TIDAK berkurang.
    """
    try:
        return await require_permission(request, "rnd", "manage")
    except HTTPException as exc:
        logger.warning("[_perm_manage] efek samping gagal diabaikan: %s", exc)  # KN-C10
    try:
        return await require_permission(request, "hr", "manage_attendance")
    except HTTPException:
        return await require_permission(request, "design_request", "deliver")


async def assert_design_writer(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """P20 DESIGN-04 — desainer (tanpa rnd.manage) hanya menulis desain miliknya: desain yang
    tertaut permintaan → penerima tugas SAAT INI; selain itu → pembuatnya."""
    from db import db as _db
    from dependencies import permission_matrix
    perms = ((await permission_matrix()).get(actor.get("role"), {}) or {}).get("rnd", [])
    if "manage" in perms or "*" in perms:
        return
    req = await _db.design_requests.find_one({"gallery_ids": doc.get("id"), "status": {"$ne": "cancelled"}},
                                             {"_id": 0, "assigned_to": 1, "assigned_name": 1, "number": 1})
    owner = req.get("assigned_to") if req else doc.get("created_by_id")
    if owner and owner != actor.get("id"):
        who = f"permintaan {req.get('number')} kini ditugaskan ke {req.get('assigned_name')}" if req else "desain ini milik desainer lain"
        raise HTTPException(status_code=403, detail=f"Anda tidak bisa mengubah desain ini — {who}.")


async def _guard(gallery_id: str, ctx, writer: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    doc = await gallery.get_gallery(gallery_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Entri galeri tidak ditemukan.")
    assert_entity_access(doc, "design_gallery", ctx)
    if writer is not None:
        await assert_design_writer(doc, writer)
    return doc


@router.get("/design-gallery")
async def list_gallery(request: Request, entity_id: Optional[str] = Query(None),
                       tag: Optional[str] = Query(None),
                       q: Optional[str] = Query(None),
                       status: str = Query(""), design_type: str = Query(""),
                       category_code: str = Query(""), created_by: str = Query(""),
                       product_id: str = Query(""), color_id: str = Query(""),
                       on_hold: str = Query("", description="yes|no — saring desain HOLD"),
                       origin: str = Query("", description="internal|special_order|redesign"),
                       ownership: str = Query("", description="UAT 24 Okt P1.5 — white|customer|claim_pending"),
                       owner_customer_id: str = Query(""),
                       produced: str = Query("", description="yes|no — sudah ada SKU ber-desain ini"),
                       line: str = Query("", description="FASE L — penyaring lini")) -> List[Dict[str, Any]]:
    viewer = await _perm_view(request)
    ctx = await entity_ctx(request)
    scope = resolve_list_scope("design_gallery", {}, ctx, entity_id)
    # FASE L — galeri desain ikut berpagar lini (artwork printing bukan urusan staf woven).
    from services import line_scope as _lines
    scope = _lines.narrow(scope, viewer, line)
    return await gallery.list_gallery(scope, tag, q, viewer_id=viewer.get("id"),
                                      filters={"status": status, "design_type": design_type,
                                               "category_code": category_code, "created_by": created_by,
                                               "product_id": product_id, "color_id": color_id,
                                               "on_hold": on_hold, "origin": origin, "ownership": ownership,
                                               "owner_customer_id": owner_customer_id, "produced": produced})


@router.post("/design-gallery")
async def create_gallery(payload: GalleryInput, request: Request) -> Dict[str, Any]:
    actor = await _perm_manage(request)
    ctx = await entity_ctx(request)
    try:
        doc = await gallery.create_gallery(payload.model_dump(), actor["name"], ctx.active_entity_id,
                                           actor=actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "design_gallery_create", "design_gallery", doc["id"],
                {"title": doc["title"]})
    return doc


@router.get("/design-gallery/{gallery_id}")
async def get_gallery(gallery_id: str, request: Request) -> Dict[str, Any]:
    viewer = await _perm_view(request)
    ctx = await entity_ctx(request)
    await _guard(gallery_id, ctx)
    return await gallery.get_gallery(gallery_id, viewer_id=viewer.get("id"))


@router.put("/design-gallery/{gallery_id}")
async def update_gallery(gallery_id: str, payload: GalleryUpdate, request: Request) -> Dict[str, Any]:
    actor = await _perm_manage(request)
    ctx = await entity_ctx(request)
    await _guard(gallery_id, ctx, actor)
    patch = payload.model_dump(exclude_unset=True)
    try:
        doc = await gallery.update_gallery(gallery_id, patch, actor=actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # UAT 24 Okt (P6.1) — kode/kategori/tag desain ikut berubah di SKU yang memakainya.
    from services import design_ownership_service as _own
    await _own.sync_products(gallery_id)
    await audit(actor["name"], "design_gallery_update", "design_gallery", gallery_id, patch)
    return doc


# ─── UAT 24 Okt (P1) — kepemilikan desain: white / customer label, klaim, pemakaian ─────────────────
class DesignClaimIn(BaseModel):
    customer_id: str
    reason: str = ""


class DesignClaimDecideIn(BaseModel):
    approve: bool
    reason: str = ""


class DesignOwnerIn(BaseModel):
    reason: str = ""
    customer_id: str = ""


class DesignLinkProductsIn(BaseModel):
    product_ids: List[str] = []
    template_id: str = ""


def _own_fail(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("/design-gallery/{gallery_id}/usage")
async def design_usage(gallery_id: str, request: Request) -> Dict[str, Any]:
    """P1.4 — pembeli SKU ber-desain ini (jumlah SO, qty per satuan, nilai, repeat) untuk keputusan klaim."""
    from services import design_ownership_service as own
    await require_permission(request, "design_ownership", "view")
    await _guard(gallery_id, await entity_ctx(request))
    return await own.usage(gallery_id)


@router.post("/design-gallery/{gallery_id}/claims")
async def design_claim(gallery_id: str, payload: DesignClaimIn, request: Request) -> Dict[str, Any]:
    from services import design_ownership_service as own
    actor = await require_permission(request, "design_ownership", "claim")
    await _guard(gallery_id, await entity_ctx(request))
    try:
        await own.claim(gallery_id, payload.customer_id, actor, payload.reason)
    except own.OwnershipError as exc:
        raise _own_fail(exc) from exc
    await audit(actor["name"], "design_claim_requested", "design_gallery", gallery_id,
                {"customer_id": payload.customer_id, "reason": payload.reason})
    return await gallery.get_gallery(gallery_id, viewer_id=actor.get("id"))


@router.post("/design-gallery/{gallery_id}/claims/{claim_id}/decide")
async def design_claim_decide(gallery_id: str, claim_id: str, payload: DesignClaimDecideIn,
                              request: Request) -> Dict[str, Any]:
    from services import design_ownership_service as own
    actor = await require_permission(request, "design_ownership", "decide")
    await _guard(gallery_id, await entity_ctx(request))
    try:
        await own.decide_claim(gallery_id, claim_id, payload.approve, actor, payload.reason)
    except own.OwnershipError as exc:
        raise _own_fail(exc) from exc
    await audit(actor["name"], "design_claim_decided", "design_gallery", gallery_id,
                {"claim_id": claim_id, "approve": payload.approve, "reason": payload.reason})
    return await gallery.get_gallery(gallery_id, viewer_id=actor.get("id"))


@router.post("/design-gallery/{gallery_id}/ownership/white")
async def design_release_white(gallery_id: str, payload: DesignOwnerIn, request: Request) -> Dict[str, Any]:
    from services import design_ownership_service as own
    actor = await require_permission(request, "design_ownership", "decide")
    await _guard(gallery_id, await entity_ctx(request))
    try:
        await own.release_to_white(gallery_id, actor, payload.reason)
    except own.OwnershipError as exc:
        raise _own_fail(exc) from exc
    await audit(actor["name"], "design_released_white", "design_gallery", gallery_id, {"reason": payload.reason})
    return await gallery.get_gallery(gallery_id, viewer_id=actor.get("id"))


@router.post("/design-gallery/{gallery_id}/ownership/customer")
async def design_set_customer(gallery_id: str, payload: DesignOwnerIn, request: Request) -> Dict[str, Any]:
    """Penetapan langsung oleh Manajer (tanpa klaim) — mis. kesepakatan tertulis dengan pelanggan."""
    from services import design_ownership_service as own
    actor = await require_permission(request, "design_ownership", "decide")
    await _guard(gallery_id, await entity_ctx(request))
    if len((payload.reason or "").strip()) < 5:
        raise HTTPException(status_code=400, detail="Alasan wajib diisi (minimal 5 huruf).")
    try:
        await own.set_customer_owner(gallery_id, payload.customer_id, "manual", actor, payload.reason.strip())
    except own.OwnershipError as exc:
        raise _own_fail(exc) from exc
    await audit(actor["name"], "design_set_customer", "design_gallery", gallery_id,
                {"customer_id": payload.customer_id, "reason": payload.reason})
    return await gallery.get_gallery(gallery_id, viewer_id=actor.get("id"))


@router.post("/design-gallery/{gallery_id}/products")
async def design_link_products(gallery_id: str, payload: DesignLinkProductsIn, request: Request) -> Dict[str, Any]:
    """P6.1 — tautkan SKU (atau semua varian satu induk) ke desain; kode/kategori/tag & kepemilikan ikut tersalin."""
    from db import db as _db
    from services import design_ownership_service as own
    actor = await require_permission(request, "product", "update")
    await _guard(gallery_id, await entity_ctx(request))
    ids = list(payload.product_ids or [])
    if payload.template_id:
        await _db.product_templates.update_one({"id": payload.template_id}, {"$set": {"design_id": gallery_id}})
        ids += [p["id"] async for p in _db.products.find({"template_id": payload.template_id}, {"_id": 0, "id": 1})]
    try:
        n = await own.link_products(gallery_id, ids)
    except own.OwnershipError as exc:
        raise _own_fail(exc) from exc
    await audit(actor["name"], "design_products_linked", "design_gallery", gallery_id,
                {"products": len(ids), "template_id": payload.template_id})
    return {"linked": n, "usage": await own.usage(gallery_id)}


@router.post("/design-gallery-products/unlink")
async def design_unlink_products(payload: DesignLinkProductsIn, request: Request) -> Dict[str, Any]:
    from db import db as _db
    from services import design_ownership_service as own
    actor = await require_permission(request, "product", "update")
    ids = list(payload.product_ids or [])
    if payload.template_id:
        await _db.product_templates.update_one({"id": payload.template_id}, {"$unset": {"design_id": ""}})
        ids += [p["id"] async for p in _db.products.find({"template_id": payload.template_id}, {"_id": 0, "id": 1})]
    n = await own.unlink_products(ids)
    await audit(actor["name"], "design_products_unlinked", "products", ",".join(ids[:20]), {"products": len(ids)})
    return {"unlinked": n}


@router.delete("/design-gallery/{gallery_id}")
async def delete_gallery(gallery_id: str, request: Request) -> Dict[str, Any]:
    actor = await _perm_manage(request)
    ctx = await entity_ctx(request)
    await _guard(gallery_id, ctx, actor)
    try:
        res = await gallery.delete_gallery(gallery_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "design_gallery_delete", "design_gallery", gallery_id, {})
    return res


# ─── Files (upload / serve / delete) ──────────────────────────────────
@router.post("/design-gallery/{gallery_id}/files")
async def upload_gallery_file(gallery_id: str, request: Request,
                              file: UploadFile = File(...)) -> Dict[str, Any]:
    actor = await _perm_manage(request)
    ctx = await entity_ctx(request)
    await _guard(gallery_id, ctx, actor)
    data = await file.read()
    try:
        fmeta = await gallery.add_file(gallery_id, file.filename or "motif",
                                       file.content_type or "", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "design_gallery_upload", "design_gallery", gallery_id,
                {"file": fmeta.get("filename")})
    return fmeta


@router.get("/design-gallery/{gallery_id}/files/{file_id}")
async def get_gallery_file(gallery_id: str, file_id: str, request: Request):
    await _perm_view(request)
    ctx = await entity_ctx(request)
    await _guard(gallery_id, ctx)
    try:
        data, ctype = await gallery.get_file_bytes(gallery_id, file_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File fisik tidak ditemukan.")
    headers = {"Cache-Control": "private, max-age=300"}
    if request.query_params.get("download") == "1" or not str(ctype or "").startswith("image/"):
        fname = await gallery.file_name_of(gallery_id, file_id)
        headers["Content-Disposition"] = f'attachment; filename="{fname}"'
    return Response(content=data, media_type=ctype, headers=headers)


@router.delete("/design-gallery/{gallery_id}/files/{file_id}")
async def delete_gallery_file(gallery_id: str, file_id: str, request: Request) -> Dict[str, Any]:
    actor = await _perm_manage(request)
    ctx = await entity_ctx(request)
    await _guard(gallery_id, ctx, actor)
    try:
        res = await gallery.delete_file(gallery_id, file_id, actor=actor)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await audit(actor["name"], "design_gallery_delete_file", "design_gallery", gallery_id,
                {"file_id": file_id})
    return res


# ─── AI auto-tag (graceful) ─────────────────────────────────────
@router.post("/design-gallery/{gallery_id}/autotag")
async def autotag_gallery(gallery_id: str, request: Request) -> Dict[str, Any]:
    """Trigger AI auto-tag. Bila AI nonaktif → 200 {enabled:false} (BUKAN error)."""
    actor = await _perm_manage(request)
    ctx = await entity_ctx(request)
    await _guard(gallery_id, ctx)
    try:
        res = await gallery.autotag(gallery_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "design_gallery_autotag", "design_gallery", gallery_id,
                {"enabled": res.get("enabled"), "error": res.get("error", "")})
    return res


# ─── FB-01 — Ilustrasi AI (Gemini Nano Banana Pro; demo lokal bila key kosong) ──────
@router.post("/design-gallery/{gallery_id}/ai-illustrate")
async def ai_illustrate_gallery(gallery_id: str, payload: DesignAiIllustrateIn,
                                request: Request) -> Dict[str, Any]:
    """Buat ilustrasi ARAHAN (mockup/modifikasi) — tersimpan sebagai berkas `ai_illustration`
    pada desain yang sama; bukan versi baru dan tidak mengubah status."""
    actor = await _perm_manage(request)
    ctx = await entity_ctx(request)
    await _guard(gallery_id, ctx, actor)
    try:
        fmeta = await gallery.add_ai_illustration(gallery_id, payload.model_dump(), actor["name"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "design_gallery_ai_illustrate", "design_gallery", gallery_id,
                {"file_id": fmeta["id"], "mode": payload.mode, "model": fmeta["ai"]["model"],
                 "demo": fmeta["ai"]["demo"]}, reason=payload.prompt[:200])
    return fmeta


@router.post("/design-gallery/{gallery_id}/files/{file_id}/comments")
async def comment_illustration(gallery_id: str, file_id: str, payload: IllustrationCommentIn,
                               request: Request) -> Dict[str, Any]:
    """Komentar pada ilustrasi AI — desainer, admin, manajer (diskusi arahan tercatat di desain)."""
    actor = await _perm_manage(request)
    ctx = await entity_ctx(request)
    await _guard(gallery_id, ctx)
    try:
        c = await gallery.add_illustration_comment(gallery_id, file_id, actor, payload.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "design_gallery_ai_comment", "design_gallery", gallery_id,
                {"file_id": file_id, "comment_id": c["id"]}, reason=payload.text[:200])
    return c


@router.delete("/design-gallery/{gallery_id}/files/{file_id}/comments/{comment_id}")
async def delete_illustration_comment(gallery_id: str, file_id: str, comment_id: str,
                                      request: Request) -> Dict[str, Any]:
    """G-6 — hapus komentar sendiri pada ilustrasi AI (admin: siapa pun)."""
    actor = await _perm_manage(request)
    ctx = await entity_ctx(request)
    await _guard(gallery_id, ctx)
    try:
        res = await gallery.delete_illustration_comment(gallery_id, file_id, comment_id, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "design_gallery_ai_comment_delete", "design_gallery", gallery_id,
                {"file_id": file_id, "comment_id": comment_id})
    return res


@router.get("/design-gallery-ai/status")
async def ai_illustrate_status(request: Request) -> Dict[str, Any]:
    """Status layanan ilustrasi AI untuk UI: {enabled, demo, verified, model, daily_limit, cost}."""
    await _perm_view(request)
    from services import gemini_image_service as gem
    cfg = await gem.resolve_config()
    return {"enabled": cfg["enabled"], "demo": cfg["demo"], "verified": cfg["verified"],
            "model": cfg["model"], "daily_limit": cfg["daily_limit"],
            "cost_per_image_usd": cfg["cost_per_image_usd"], "configured": cfg['configured'], "disabled_reason": cfg['disabled_reason']}


# ─── FASE F (PS-14) — Master desain: versi & pengesahan ──────────────────────
@router.post("/design-gallery/{gallery_id}/version")
async def bump_design_version(gallery_id: str, payload: DesignVersionIn,
                              request: Request) -> Dict[str, Any]:
    """Naikkan versi desain (artwork direvisi). Versi lama tetap terarsip di `versions[]`."""
    actor = await _perm_manage(request)
    ctx = await entity_ctx(request)
    await _guard(gallery_id, ctx, actor)
    try:
        doc = await gallery.bump_version(gallery_id, payload.model_dump(exclude_unset=True),
                                        actor["name"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "design_version_bumped", "design_gallery", gallery_id,
                {"version": doc.get("version")}, reason=payload.note or "")
    return doc


@router.post("/design-gallery/{gallery_id}/submit")
async def submit_design(gallery_id: str, request: Request) -> Dict[str, Any]:
    """Jalur lama — P16: diteruskan ke siklus Studio (`lifecycle/submit`) agar aturannya satu."""
    from routers.design_studio import _do_transition
    return await _do_transition(gallery_id, "submit", DesignTransitionIn(), request, assess=False)


@router.post("/design-gallery/{gallery_id}/reject")
async def reject_design(gallery_id: str, payload: DesignRejectIn,
                        request: Request) -> Dict[str, Any]:
    """Jalur lama — P16: = `lifecycle/request-revision` (izin penilai `rnd.assess`, alasan wajib)."""
    from routers.design_studio import _do_transition
    return await _do_transition(gallery_id, "request_revision", DesignTransitionIn(note=payload.reason),
                                request, assess=True)


@router.post("/design-gallery/{gallery_id}/approve")
async def approve_design(gallery_id: str, payload: DesignApproveIn,
                         request: Request) -> Dict[str, Any]:
    """Jalur lama — P16: = `lifecycle/approve` (izin `rnd.assess`, nilai wajib, desainer tak bisa ACC sendiri)."""
    from routers.design_studio import _do_transition
    return await _do_transition(gallery_id, "approve", DesignTransitionIn(note=payload.note, score=payload.score),
                                request, assess=True)


# ─── Rating desain (bintang 1–5, 1 nilai per penilai; admin/manager) ─────────────
@router.post("/design-gallery/{gallery_id}/rating")
async def rate_design(gallery_id: str, payload: DesignRatingIn,
                      request: Request) -> Dict[str, Any]:
    """Set/ubah rating bintang 1–5 milik penilai (admin/manager). Upsert 1 nilai/orang."""
    actor = await _perm_manage(request)
    ctx = await entity_ctx(request)
    await _guard(gallery_id, ctx)
    try:
        doc = await gallery.set_rating(gallery_id, actor.get("id"), actor.get("name", ""),
                                       payload.stars, payload.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "design_rated", "design_gallery", gallery_id,
                {"stars": payload.stars, "rating_avg": doc.get("rating_avg"),
                 "rating_count": doc.get("rating_count")}, reason=payload.note or "")
    return doc


@router.delete("/design-gallery/{gallery_id}/rating")
async def unrate_design(gallery_id: str, request: Request) -> Dict[str, Any]:
    """Hapus rating milik penilai yang sedang login."""
    actor = await _perm_manage(request)
    ctx = await entity_ctx(request)
    await _guard(gallery_id, ctx)
    try:
        doc = await gallery.clear_rating(gallery_id, actor.get("id"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit(actor["name"], "design_unrated", "design_gallery", gallery_id,
                {"rating_avg": doc.get("rating_avg"), "rating_count": doc.get("rating_count")})
    return doc

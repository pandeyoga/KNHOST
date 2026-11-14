"""routers/pdf.py — Endpoint render dokumen PDF/HTML + kelola template & branding."""
from __future__ import annotations
from typing import Any, Dict, List
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import Response, HTMLResponse
from pydantic import BaseModel

from db import db
from dependencies import require_permission, audit
from entity_scope import entity_ctx, assert_entity_access, resolve_list_scope, resolve_requested_entity
from services import pdf_service as svc
from services.pdf_resolvers import DOC_REGISTRY
import json as _json

router = APIRouter(prefix="/api/pdf", tags=["pdf"])


def _summarize_doc(r: Dict[str, Any]) -> Dict[str, Any]:
    """Ringkasan lintas-koleksi untuk Pusat Dokumen (field bervariasi per doc_type)."""
    number = (r.get("number") or r.get("po_number") or r.get("so_number") or r.get("order_number")
              or r.get("bill_number") or r.get("receipt_number") or r.get("return_number")
              or r.get("transfer_number") or r.get("code") or r.get("id"))
    date = (r.get("date") or r.get("order_date") or r.get("bill_date") or r.get("receipt_date")
            or r.get("created_at") or "")
    party = (r.get("customer_name") or r.get("supplier_name") or r.get("vendor_name")
             or r.get("makloon_name") or r.get("to_warehouse_name") or r.get("warehouse_name") or "")
    # Keputusan pemilik K-03 (26 Okt) — "Total" dokumen = TERMASUK PPN (grand_total bila ada); DPP (harga sebelum
    # PPN) dikirim sebagai rincian `amount_dpp`. Dulu `total_amount` didahulukan → SO tampil Rp 202.318 (sebelum PPN)
    # padahal PDF/CRM Rp 224.573. Dokumen tanpa grand_total memakai rantai lama.
    grand = r.get("grand_total")
    if isinstance(grand, (int, float)) and not isinstance(grand, bool) and grand:
        amount = grand
    else:
        amount = (r.get("total_amount") or r.get("grand_total") or r.get("total")
                  or r.get("amount") or r.get("net_total") or 0)
    try:
        ppn = float(r.get("ppn_amount") or 0)
    except (TypeError, ValueError):
        ppn = 0.0
    try:
        amt_f = float(amount or 0)
    except (TypeError, ValueError):
        amt_f = 0.0
    dpp_base = round(amt_f - ppn, 2) if ppn > 0 else amt_f
    nilai_lain = bool(r.get("dpp_nilai_lain")) and ppn > 0 and bool(r.get("dpp"))
    return {"number": number, "date": str(date)[:10], "party": party,
            "amount": amount, "amount_dpp": dpp_base, "ppn_amount": round(ppn, 2),
            "amount_includes_ppn": ppn > 0,
            "dpp_nilai_lain": r.get("dpp") if nilai_lain else None,
            "status": r.get("status") or ""}


def _origin(request: Request) -> str:
    """URL publik aplikasi untuk QR & tautan pada dokumen cetak.

    FASE G-4 — dulu fungsi ini HANYA membaca header `Origin`/`Referer`, sehingga
    render non-browser (cetak batch, penjadwal, kiriman WhatsApp, integrasi) mencetak
    QR tanpa host — tidak bisa dibuka dari HP pemegang kertas. Sekarang ada rantai
    fallback tunggal di `services/app_url.py`.
    """
    from services.app_url import public_app_url
    return public_app_url(request)


class TemplateSave(BaseModel):
    config: Dict[str, Any]


class BrandingSave(BaseModel):
    # KP-T6 — field teks identitas tetap dikenali skema HANYA supaya bisa ditolak 400 dengan petunjuk (bukan 200 diam).
    company_name: str | None = None
    tagline: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    npwp: str | None = None
    logo_b64: str | None = None
    header_image_b64: str | None = None
    footer_image_b64: str | None = None
    stamp_b64: str | None = None
    signatures: List[Dict[str, Any]] | None = None


class PreviewReq(BaseModel):
    doc_type: str
    source_id: str | None = None
    entity_id: str | None = None
    config: Dict[str, Any] | None = None
    # KP-T6 — "all" = `config` adalah aturan semua PT yang sedang disunting (lapisan PT tetap diterapkan di atasnya).
    layer: str | None = None


class IdentityResolve(BaseModel):
    action: str
    reason: str = ""


def _one_pt(ctx, entity_id: str) -> str:
    """KP-T6 (N1) — satu PT dalam penugasan pengguna. "all"/kosong → 400; di luar penugasan → 403."""
    if (entity_id or "").strip() in ("", "all"):
        raise HTTPException(status_code=400, detail="Pilih satu PT.")
    return resolve_requested_entity(ctx, entity_id)


async def _layer_scope(request: Request, entity_id: str | None) -> str:
    """Lapisan template: tanpa `entity_id` / "all" = semua PT; selain itu satu PT dalam penugasan (403 bila tidak)."""
    if (entity_id or "").strip() in ("", svc.GROUP_SCOPE):
        return svc.GROUP_SCOPE
    return resolve_requested_entity(await entity_ctx(request), entity_id)


@router.get("/doc-types")
async def list_doc_types(request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "document", "view")
    return [{"doc_type": k, "label": v["label"], "esignable": v.get("esignable", False),
             "collection": v["collection"], "module": v["module"]} for k, v in DOC_REGISTRY.items()]


@router.get("/render/{doc_type}/{source_id}")
async def render_document(doc_type: str, source_id: str, request: Request,
                          format: str = Query("pdf"), entity_id: str = Query(None),
                          download: bool = Query(True),
                          supplier_id: str = Query("", description="UAT 24 Okt P3.1 — surat perintah per supplier")):
    user = await require_permission(request, "document", "print")
    ctx = await entity_ctx(request)
    reg = DOC_REGISTRY.get(doc_type)
    if not reg:
        raise HTTPException(status_code=404, detail=f"Jenis dokumen '{doc_type}' tidak dikenal")
    from services.field_visibility import hidden_for_user
    hidden = await hidden_for_user(user)
    source = await db[reg["collection"]].find_one({"id": source_id}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Dokumen sumber tidak ditemukan")
    assert_entity_access(source, reg["collection"], ctx)
    # KP-T6 (N1) — kop = PT pemilik dokumen; `entity_id` permintaan hanya untuk dokumen tanpa PT (koleksi bersama) dan
    # harus dalam penugasan pengguna. Dulu `entity_id` mentah bisa mencetak dokumen PT A dengan kop & tanda tangan PT B.
    eid = source.get("entity_id") if source.get("entity_id") not in (None, "", "all") else None
    if not eid and (entity_id or "").strip() not in ("", "all"):
        eid = resolve_requested_entity(ctx, entity_id)
    from services.pdf_resolvers import WO_SUPPLIER
    WO_SUPPLIER.set(supplier_id or "")
    try:
        content, media, built = await svc.render_document(
            doc_type, source_id, eid or source.get("entity_id"),
            fmt=format, public_base=_origin(request), hidden=hidden)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Gagal render dokumen: {e}")
    if format == "html":
        return HTMLResponse(content=content)
    num = (built["doc"].get("number") or source_id).replace("/", "-")
    disp = "attachment" if download else "inline"
    return Response(content=content, media_type=media,
                    headers={"Content-Disposition": f'{disp}; filename="{doc_type}-{num}.pdf"'})


@router.get("/sample/{doc_type}")
async def get_sample(doc_type: str, request: Request, entity_id: str = Query(None)) -> Dict[str, Any]:
    """Ambil 1 dokumen contoh (id + nomor) untuk pratinjau/unduh di Template Designer."""
    await require_permission(request, "pdf_template", "view")
    reg = DOC_REGISTRY.get(doc_type)
    if not reg:
        raise HTTPException(status_code=404, detail="Jenis dokumen tidak dikenal")
    # KP-T6 (N1) — PT contoh lewat `resolve_requested_entity` (kosong = PT aktif; di luar penugasan → 403).
    entity_id = resolve_requested_entity(await entity_ctx(request), entity_id)
    q: Dict[str, Any] = {"entity_id": entity_id}
    sample = await db[reg["collection"]].find_one(q, {"_id": 0, "id": 1, "entity_id": 1, "number": 1})
    if not sample:
        return {"doc_type": doc_type, "source_id": None, "entity_id": entity_id, "number": None,
                "label": reg["label"]}
    return {"doc_type": doc_type, "source_id": sample.get("id"),
            "entity_id": sample.get("entity_id") or entity_id, "number": sample.get("number"),
            "label": reg["label"]}


@router.get("/documents/{doc_type}")
async def list_documents(doc_type: str, request: Request,
                         entity_id: str = Query(None), q: str = Query(""),
                         limit: int = Query(100)) -> Dict[str, Any]:
    """Daftar dokumen (Pusat Dokumen) + ringkasan status e-sign & pengiriman."""
    await require_permission(request, "document", "view")
    ctx = await entity_ctx(request)
    reg = DOC_REGISTRY.get(doc_type)
    if not reg:
        raise HTTPException(status_code=404, detail="Jenis dokumen tidak dikenal")
    coll = reg["collection"]
    query = resolve_list_scope(coll, {}, ctx, entity_id)
    rows = await db[coll].find(query, {"_id": 0}).sort("created_at", -1).to_list(int(limit))
    ids = [r.get("id") for r in rows if r.get("id")]

    sig_rows = await db.document_signatures.find(
        {"doc_type": doc_type, "source_id": {"$in": ids}, "status": "signed"},
        {"_id": 0, "source_id": 1, "verification_code": 1, "signer_name": 1}).to_list(2000)
    sig_map: Dict[str, List[Dict[str, Any]]] = {}
    for s in sig_rows:
        sig_map.setdefault(s["source_id"], []).append(s)

    del_rows = await db.document_deliveries.find(
        {"doc_type": doc_type, "source_id": {"$in": ids}},
        {"_id": 0, "source_id": 1, "status": 1, "sent_at": 1, "channel": 1, "to": 1}
    ).sort("created_at", -1).to_list(3000)
    del_map: Dict[str, Dict[str, Any]] = {}
    for d in del_rows:
        del_map.setdefault(d["source_id"], d)  # pertama = terbaru (sort desc)

    ql = (q or "").strip().lower()
    # FASE G-4 — doc_type PDF bisa berbagi koleksi (invoice/delivery_note/picking_list
    # semuanya dari `sales_orders`). Untuk menautkan baris ke layar Jejak Dokumen, UI
    # butuh doc_type KANONIK koleksinya — dihitung sekali di sini, bukan ditebak di FE.
    from services import doc_refs_service as _refs
    trace_type = (doc_type if doc_type in _refs.DOC_TYPES
                  else _refs.type_of_collection(coll))
    out: List[Dict[str, Any]] = []
    for r in rows:
        summ = _summarize_doc(r)
        if ql and ql not in _json.dumps(summ, default=str, ensure_ascii=False).lower():
            continue
        sid = r.get("id")
        sigs = sig_map.get(sid, [])
        out.append({**summ, "source_id": sid, "entity_id": r.get("entity_id"),
                    "esignable": reg.get("esignable", False),
                    "signed": len(sigs) > 0, "sign_count": len(sigs),
                    "verification_code": (sigs[0]["verification_code"] if sigs else None),
                    "trace_type": trace_type, "ref_count": len(r.get("refs") or []),
                    "last_delivery": del_map.get(sid)})
    return {"doc_type": doc_type, "label": reg["label"], "count": len(out),
            "trace_type": trace_type, "documents": out}


def _known(doc_type: str) -> None:
    if doc_type != svc.DEFAULT_CODE and doc_type not in DOC_REGISTRY:
        raise HTTPException(status_code=404, detail="Jenis dokumen tidak dikenal")


@router.get("/templates")
async def list_templates(request: Request) -> Dict[str, Any]:
    """Semua jenis dokumen + mana yang sudah disetel (pola sipro `list_targets`)."""
    await require_permission(request, "pdf_template", "view")
    return {"data": await svc.list_templates(), "placeholders": svc.placeholder_list()}


async def _template_out(doc_type: str, scope: str) -> Dict[str, Any]:
    """Jawaban satu lapisan. KP-T6 — `scope` ("all" | id PT), `pt_layer_keys`, `pt_override_keys` (kunci yang ditimpa PT
    itu), `group_config` (hasil tanpa lapisan PT)."""
    pt = None if scope == svc.GROUP_SCOPE else scope
    group_cfg = await svc.get_template_cfg(doc_type)
    return {"doc_type": doc_type, "scope": scope,
            "config": await svc.get_template_cfg(doc_type, pt) if pt else group_cfg,
            "group_config": group_cfg, "pt_layer_keys": list(svc.PT_LAYER_KEYS),
            "pt_override_keys": await svc.pt_override_keys(doc_type, pt) if pt else [],
            "meta": await svc.template_meta(doc_type, scope)}


@router.get("/templates/{doc_type}")
async def get_template(doc_type: str, request: Request, entity_id: str = Query(None)) -> Dict[str, Any]:
    await require_permission(request, "pdf_template", "view")
    _known(doc_type)
    scope = await _layer_scope(request, entity_id)
    return {**await _template_out(doc_type, scope), "defaults": svc.DEFAULT_TEMPLATE_CFG,
            "default_effective": await svc.get_template_cfg(svc.DEFAULT_CODE),
            "placeholders": svc.placeholder_list(), "key_labels": svc.TEMPLATE_KEY_LABELS}


@router.put("/templates/{doc_type}")
async def put_template(doc_type: str, payload: TemplateSave, request: Request,
                       entity_id: str = Query(None)) -> Dict[str, Any]:
    """Tanpa `entity_id` = lapisan semua PT (perilaku lama). Dengan `entity_id` = lapisan PT (KP-T6; cakupan diperiksa)."""
    actor = await require_permission(request, "pdf_template", "manage")
    _known(doc_type)
    scope = await _layer_scope(request, entity_id)
    try:
        await svc.save_template_cfg(doc_type, payload.config, actor.get("name", ""), entity_id=scope)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    out = await _template_out(doc_type, scope)
    meta = out["meta"]
    await audit(actor["name"], "pdf_template_saved", "pdf_templates", doc_type,
                {"version": meta.get("version"), "override_keys": meta.get("override_keys"), "scope": scope},
                scope_entity_id="" if scope == svc.GROUP_SCOPE else scope)
    return out


@router.delete("/templates/{doc_type}")
async def reset_template(doc_type: str, request: Request, entity_id: str = Query(None)) -> Dict[str, Any]:
    """Kembalikan ke bawaan (buang override lapisan itu saja). Dokumen yang sudah terbit tidak berubah."""
    actor = await require_permission(request, "pdf_template", "manage")
    _known(doc_type)
    scope = await _layer_scope(request, entity_id)
    await svc.reset_template_cfg(doc_type, entity_id=scope)
    await audit(actor["name"], "pdf_template_reset", "pdf_templates", doc_type, {"scope": scope},
                scope_entity_id="" if scope == svc.GROUP_SCOPE else scope)
    return await _template_out(doc_type, scope)


@router.post("/templates/validate-script")
async def validate_script(payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    """Peringatan token asing HIDUP saat mengetik (tanpa menyimpan)."""
    await require_permission(request, "pdf_template", "view")
    text = str(payload.get("text") or "")
    return {"unknown": svc.unknown_tokens(text), "ok": not svc.unknown_tokens(text)}


@router.get("/branding/{entity_id}")
async def get_branding(entity_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "pdf_template", "view")
    return await svc.get_branding(_one_pt(await entity_ctx(request), entity_id))


@router.put("/branding/{entity_id}")
async def put_branding(entity_id: str, payload: BrandingSave, request: Request) -> Dict[str, Any]:
    """KP-T6 — hanya logo, gambar kop/footer, cap, dan tanda tangan. Identitas teks diubah di Profil PT."""
    actor = await require_permission(request, "pdf_template", "manage")
    eid = _one_pt(await entity_ctx(request), entity_id)
    try:
        return await svc.save_branding(eid, payload.model_dump(exclude_none=True), actor.get("name", ""))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/branding/{entity_id}/identity")
async def resolve_branding_identity(entity_id: str, payload: IdentityResolve, request: Request) -> Dict[str, Any]:
    """KP-T6 (KP-18) — pemilik memilih sumber identitas kop PT yang masih memakai teks lama: `pakai_profil` atau
    `salin_ke_profil` (teks lama → Profil PT, validasi KP-T1). Butuh `pdf_template.manage` DAN `entity.update`."""
    actor = await require_permission(request, "pdf_template", "manage")
    await require_permission(request, "entity", "update")
    eid = _one_pt(await entity_ctx(request), entity_id)
    try:
        out = await svc.resolve_identity(eid, payload.action, payload.reason, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except svc.IdentityConflict as e:
        raise HTTPException(status_code=409, detail=str(e))
    copied = out["copied"]
    await audit(actor["name"], "branding_identity_resolved", "document_branding", eid,
                {"action": payload.action, "reason": payload.reason.strip(), "copied": sorted(copied)},
                reason=payload.reason.strip(), scope_entity_id=eid)
    if copied:   # jejak Profil PT ikut mencatat isian yang berubah (riwayat detail PT)
        await audit(actor["name"], "entity_updated", "business_entity", eid, copied,
                    reason="Salin teks kop ke Profil PT", scope_entity_id=eid)
    return out["branding"]


@router.post("/preview")
async def preview(payload: PreviewReq, request: Request):
    await require_permission(request, "pdf_template", "view")
    ctx = await entity_ctx(request)
    reg = DOC_REGISTRY.get(payload.doc_type)
    if not reg:
        raise HTTPException(status_code=404, detail="Jenis dokumen tidak dikenal")
    source_id = payload.source_id
    # KP-T6 (N1) — PT lewat `resolve_requested_entity` (kosong = PT aktif; di luar penugasan → 403).
    entity_id = resolve_requested_entity(ctx, payload.entity_id)
    if not source_id:
        # ambil contoh dokumen pertama milik PT itu
        sample = await db[reg["collection"]].find_one({"entity_id": entity_id}, {"_id": 0, "id": 1, "entity_id": 1})
        if not sample:
            raise HTTPException(status_code=404, detail=f"Belum ada data '{reg['label']}' untuk pratinjau. Buat dokumen dulu.")
        source_id = sample["id"]
    else:
        source = await db[reg["collection"]].find_one({"id": source_id}, {"_id": 0, "id": 1, "entity_id": 1})
        if not source:
            raise HTTPException(status_code=404, detail="Dokumen sumber tidak ditemukan")
        assert_entity_access(source, reg["collection"], ctx)
        if source.get("entity_id") not in (None, "", "all", entity_id):
            raise HTTPException(status_code=400, detail="Dokumen contoh milik PT lain. Pilih dokumen PT ini.")
    try:
        html, _, _ = await svc.render_document(
            payload.doc_type, source_id, entity_id, fmt="html",
            cfg_override=payload.config, public_base=_origin(request),
            override_layer=svc.GROUP_SCOPE if payload.layer == svc.GROUP_SCOPE else "")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Gagal pratinjau: {e}")
    return HTMLResponse(content=html)

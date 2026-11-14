"""KP-T5 — Penomoran Dokumen: format nomor per jenis dokumen per PT (`doc_number_formats`).

  GET    /api/doc-numbering?entity_id=                      tabel jenis + format yang berlaku (grup bila kosong/`all`)
  POST   /api/doc-numbering/preview                         tiga contoh nomor berikutnya + peringatan (tanpa menaikkan
                                                            penghitung); `code` = kode PT yang belum dibuat (wizard)
  PUT    /api/doc-numbering/{kind}                          simpan format baris PT / grup (alasan wajib)
  DELETE /api/doc-numbering/{kind}?entity_id=&reason=       hapus baris (kembali ke grup / bawaan)

Izin `settings.view` untuk baca, `settings.manage` untuk ubah (pesan Z6). PT lewat `resolve_requested_entity` (N1).
Baris grup hanya diubah orang yang ditugaskan di SEMUA PT aktif (dari penugasan, bukan nama peran). Mesin dan aturan
simpan: `services/doc_numbering_service.py`; katalog jenis: `doc_number_kinds.py`.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from dependencies import require_permission
from entity_scope import entity_ctx, resolve_requested_entity
from services import doc_numbering_service as dns

router = APIRouter(prefix="/api/doc-numbering", tags=["doc-numbering"])

_MODUL = "'Pusat Pengaturan'"
PESAN_LIHAT = f"Anda belum punya akses untuk melihat penomoran dokumen. Minta Admin menambahkan akses {_MODUL}."
PESAN_UBAH = f"Anda belum punya akses untuk mengubah penomoran dokumen. Minta Admin menambahkan akses {_MODUL}."
PESAN_GRUP = ("Format nomor untuk semua PT hanya bisa diubah orang yang ditugaskan di semua PT. "
              "Pilih PT Anda untuk membuat format khusus PT.")


class DocNumberingPut(BaseModel):
    entity_id: str = Field("all", description="'all' = baris grup; selain itu id PT")
    prefix: Any = None
    width: Any = None
    date_token: Any = None
    reset: Any = None
    scope: Optional[str] = None
    reason: str = ""
    expected_version: Optional[int] = None


class DocNumberingPreview(BaseModel):
    kind: str
    entity_id: str = ""
    prefix: Any = None
    width: Any = None
    date_token: Any = None
    reset: Any = None
    scope: Optional[str] = None
    code: str = Field("", description="Kode dokumen PT yang belum dibuat (langkah wizard PT)")


async def _layer(request: Request, entity_id: Optional[str]) -> str:
    eid = (entity_id or "").strip()
    if not eid or eid == "all":
        return "all"
    return resolve_requested_entity(await entity_ctx(request), eid)


async def _layer_for_write(request: Request, entity_id: Optional[str]) -> str:
    eid = (entity_id or "").strip()
    ctx = await entity_ctx(request)
    if not eid or eid == "all":
        from services.entity_context_service import all_active_entity_ids
        if any(e not in ctx.allowed_entity_ids for e in await all_active_entity_ids()):
            raise HTTPException(status_code=403, detail=PESAN_GRUP)
        return "all"
    return resolve_requested_entity(ctx, eid)


@router.get("")
async def list_doc_numbering(request: Request, entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    await require_permission(request, "settings", "view", PESAN_LIHAT)
    ent = await _layer(request, entity_id)
    return {"entity_id": ent, "groups": list(dns.dnk.GROUPS), "rows": await dns.list_formats(ent)}


@router.post("/preview")
async def preview_doc_numbering(payload: DocNumberingPreview, request: Request) -> Dict[str, Any]:
    await require_permission(request, "settings", "view", PESAN_LIHAT)
    ent = await _layer(request, payload.entity_id)
    cand = {f: getattr(payload, f) for f in ("prefix", "width", "date_token", "reset", "scope")
            if getattr(payload, f) is not None}
    return await dns.preview(dns.kind_or_404(payload.kind), ent, cand, code=(payload.code or "").strip().upper())


@router.put("/{kind}")
async def put_doc_numbering(kind: str, payload: DocNumberingPut, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "settings", "manage", PESAN_UBAH)
    k = dns.kind_or_404(kind)
    ent = await _layer_for_write(request, payload.entity_id)
    body = {f: getattr(payload, f) for f in ("prefix", "width", "date_token", "reset", "scope")}
    return await dns.save_format(k, ent, body, reason=payload.reason, expected_version=payload.expected_version,
                                 actor=actor)


@router.delete("/{kind}")
async def delete_doc_numbering(kind: str, request: Request, entity_id: str = Query("all"),
                               reason: str = Query("")) -> Dict[str, Any]:
    actor = await require_permission(request, "settings", "manage", PESAN_UBAH)
    k = dns.kind_or_404(kind)
    ent = await _layer_for_write(request, entity_id)
    return await dns.clear_format(k, ent, reason=reason, actor=actor)

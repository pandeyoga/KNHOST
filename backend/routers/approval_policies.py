"""KP-T4 — Aturan Persetujuan: satu tabel kebijakan untuk semua antrean (`approval_policies`).

  GET  /api/approval-policies/kinds                         katalog jenis dokumen
  GET  /api/approval-policies?entity_id=&doc_kind=          aturan yang berlaku per jenis (grup bila `all`)
  GET  /api/approval-policies/check?doc_kind=&entity_id=&amount=   coba nilai: jenjang + siapa yang lolos
  PUT  /api/approval-policies/{doc_kind}                    ganti seluruh baris (jenis, PT|grup) sekaligus
  DELETE /api/approval-policies/{doc_kind}?entity_id=       hapus aturan khusus PT (kembali ke grup)
  GET  /api/approval-policies/can-decide/me?doc_kind=&entity_id=&amount=&level=&action=
                                                            boleh-tidaknya PENGGUNA INI memutus (tombol layar keputusan)

Izin `settings.view` untuk baca, `settings.manage` untuk ubah (pesan Z6). PT lewat `resolve_requested_entity` (N1);
lapisan grup hanya untuk peran lintas PT. `can-decide/me` hanya menilai pemanggil sendiri (Z3 "milik sendiri"); PT
tetap diadu dengan penugasan. Penilai semua pintu: `services/approval_policy_service.py`.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from approval_kinds import APPROVAL_KINDS
from db import db
from dependencies import current_user, require_permission
from entity_scope import entity_ctx, resolve_requested_entity
from services import approval_policy_service as aps

router = APIRouter(prefix="/api/approval-policies", tags=["approval-policies"])

_MODUL = "'Pusat Pengaturan'"   # PR-T5 — modul pemilik `settings` (dulu modul gabungan)
PESAN_LIHAT = f"Anda belum punya akses untuk melihat aturan persetujuan. Minta Admin menambahkan akses {_MODUL}."
PESAN_UBAH = f"Anda belum punya akses untuk mengubah aturan persetujuan. Minta Admin menambahkan akses {_MODUL}."


class PolicyPut(BaseModel):
    entity_id: str = Field("all", description="'all' = aturan grup; selain itu id PT")
    expected_version: Optional[int] = None
    reason: str = ""
    levels: List[Dict[str, Any]] = Field(default_factory=list)


def _kind_or_400(doc_kind: str) -> str:
    if doc_kind not in APPROVAL_KINDS:
        raise HTTPException(status_code=400, detail="Jenis dokumen tidak dikenal.")
    return doc_kind


async def _entity(request: Request, entity_id: Optional[str]) -> str:
    eid = (entity_id or "").strip()
    if not eid or eid == "all":
        return "all"
    return resolve_requested_entity(await entity_ctx(request), eid)


async def _entity_name(ent: str) -> str:
    if ent == "all":
        return "Semua PT (aturan grup)"
    doc = await db.business_entities.find_one(
        {"id": ent}, {"_id": 0, "legal_name": 1, "short_name": 1, "name": 1}) or {}
    return doc.get("legal_name") or doc.get("name") or doc.get("short_name") or "PT"


@router.get("/kinds")
async def list_kinds(request: Request) -> Dict[str, Any]:
    await require_permission(request, "settings", "view", PESAN_LIHAT)
    import role_registry
    # Pilihan penyetuju layar = semua peran registry (termasuk peran kustom), berlabel manusia.
    roles = [{"id": rid, "label": role_registry.role_label(rid), "custom": bool(role_registry.ROLES[rid].get("custom"))}
             for rid in role_registry.role_ids()]
    return {"kinds": await aps.kinds_catalog(), "roles": roles}


@router.get("/check")
async def check(request: Request, doc_kind: str = Query(...), entity_id: Optional[str] = Query(None),
                amount: float = Query(0)) -> Dict[str, Any]:
    await require_permission(request, "settings", "view", PESAN_LIHAT)
    _kind_or_400(doc_kind)
    ent = await _entity(request, entity_id)
    return await aps.check_view(doc_kind, ent, amount)


@router.get("")
async def list_policies(request: Request, entity_id: Optional[str] = Query(None),
                        doc_kind: Optional[str] = Query(None)) -> Dict[str, Any]:
    await require_permission(request, "settings", "view", PESAN_LIHAT)
    ent = await _entity(request, entity_id)
    kinds = [_kind_or_400(doc_kind)] if doc_kind else list(APPROVAL_KINDS)
    return {"entity_id": ent, "entity_name": await _entity_name(ent),
            "kinds": [await aps.policy_view(k, ent) for k in kinds]}


async def _entity_for_write(request: Request, entity_id: Optional[str]) -> str:
    eid = (entity_id or "").strip()
    ctx = await entity_ctx(request)
    if not eid or eid == "all":
        if not ctx.is_cross_entity:
            raise HTTPException(status_code=403, detail=(
                "Aturan grup (semua PT) hanya bisa diubah peran yang memegang semua PT. "
                "Pilih PT Anda untuk membuat aturan khusus."))
        return "all"
    return resolve_requested_entity(ctx, eid)


@router.get("/can-decide/me")
async def can_decide_me(request: Request, doc_kind: str = Query(...), entity_id: Optional[str] = Query(None),
                        amount: float = Query(0), level: int = Query(1), action: str = Query("approve")
                        ) -> Dict[str, Any]:
    """Boleh-tidaknya pemanggil memutus (untuk menonaktifkan tombol setujui/tolak dengan petunjuk)."""
    actor = await current_user(request)
    _kind_or_400(doc_kind)
    ent = await _entity(request, entity_id)
    res = await aps.can_decide(doc_kind, None if ent == "all" else ent, amount, actor, max(1, int(level or 1)),
                               action="reject" if action == "reject" else "approve")
    return {"allowed": res["allowed"], "code": res["code"], "message": res["message"], "who": res["who"]}


@router.put("/{doc_kind}")
async def put_policy(doc_kind: str, payload: PolicyPut, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "settings", "manage", PESAN_UBAH)
    _kind_or_400(doc_kind)
    ent = await _entity_for_write(request, payload.entity_id)
    return await aps.replace_rows(doc_kind, ent, payload.levels, expected_version=payload.expected_version,
                                  reason=payload.reason, actor=actor)


@router.delete("/{doc_kind}")
async def delete_policy(doc_kind: str, request: Request, entity_id: str = Query(...),
                        reason: str = Query("")) -> Dict[str, Any]:
    actor = await require_permission(request, "settings", "manage", PESAN_UBAH)
    _kind_or_400(doc_kind)
    if not (entity_id or "").strip() or entity_id == "all":
        raise HTTPException(status_code=400, detail="Pilih PT yang aturan khususnya akan dihapus.")
    ent = resolve_requested_entity(await entity_ctx(request), entity_id)
    return await aps.delete_pt_rows(doc_kind, ent, reason=reason, actor=actor)

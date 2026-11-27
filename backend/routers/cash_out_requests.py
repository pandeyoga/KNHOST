"""Kas & Bank bagian 2 (C6) — pengajuan kas keluar manual di atas batas PT. Logika di
`services/cash_out_request_service.py`; pengajuan LAHIR di `POST /api/cash-transactions` (202 `{request}`,
`routers/cash.py`).

Izin (spesifikasi §6, §7 butir 7 — tanpa izin baru): lihat `cash.view`, setujui/tolak `cash.approve`, batal oleh pengaju
(`cash.create`) atau pemegang `cash.delete`. Cakupan PT: dokumen hanya bisa dibaca/diputus dalam cakupan PT pengguna
(`guard_doc`, ketat untuk tulisan).

  GET  /api/cash-out-requests                     daftar (`entity_id`, `status`, `q`, `page`, `page_size`)
  GET  /api/cash-out-requests/{id}                pengajuan + kas yang terbit + penilaian kontrol dua orang
  POST /api/cash-out-requests/{id}/approve        orang kedua; kas keluar manual terbit
  POST /api/cash-out-requests/{id}/reject         `{alasan}` (≥ 5 huruf), bukan pengaju
  POST /api/cash-out-requests/{id}/cancel         `{alasan?}` — pengaju atau pemegang `cash.delete`, selama menunggu

Antrean Pusat Persetujuan, Aturan Persetujuan (`guard_door`), layar, dan pemberitahuan menyusul di Tugas 3–4.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request

from dependencies import audit, denied, has_permission, require_any_permission, require_permission
from entity_scope import entity_ctx, guard_doc, resolve_scope_ids
from schemas_finance import CashOutRequestCancel, CashOutRequestReject
from services import cash_out_request_service as cors

router = APIRouter(prefix="/api/cash-out-requests")


async def _dokumen(request: Request, pengajuan_id: str, *, tulis: bool) -> Dict[str, Any]:
    from db import db
    doc = await db[cors.COLL].find_one({"id": pengajuan_id}, {"_id": 0})
    await guard_doc(request, cors.COLL, doc, strict=tulis, not_found=cors.PESAN_TIDAK_ADA)
    return doc


def _jejak_audit(res: Dict[str, Any]) -> Dict[str, Any]:
    return {k: res.get(k) for k in ("number", "status", "amount", "account_id", "category", "txn_date", "cash_id",
                                    "cash_number")}


@router.get("")
async def list_cash_out_requests(request: Request, entity_id: str = Query(None), status: str = Query(""),
                                 q: str = Query(""), page: int = Query(1, ge=1),
                                 page_size: int = Query(25, ge=1, le=100)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "view")
    ids = resolve_scope_ids(await entity_ctx(request), entity_id)
    return await cors.daftar(ids, status or None, q=q, page=page, page_size=page_size, actor=actor)


@router.get("/{pengajuan_id}")
async def get_cash_out_request(pengajuan_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "view")
    await _dokumen(request, pengajuan_id, tulis=False)
    return await cors.rincian(pengajuan_id, actor)


@router.post("/{pengajuan_id}/approve")
async def approve_cash_out_request(pengajuan_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "approve")
    await _dokumen(request, pengajuan_id, tulis=True)
    res = await cors.setujui(pengajuan_id, actor)
    await audit(actor["name"], "cash_out_request_approved", "cash_out_request", pengajuan_id, _jejak_audit(res),
                scope_entity_id=res.get("entity_id", ""))
    return res


@router.post("/{pengajuan_id}/reject")
async def reject_cash_out_request(pengajuan_id: str, payload: CashOutRequestReject,
                                  request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "approve")
    await _dokumen(request, pengajuan_id, tulis=True)
    res = await cors.tolak(pengajuan_id, payload.alasan, actor)
    await audit(actor["name"], "cash_out_request_rejected", "cash_out_request", pengajuan_id,
                {**_jejak_audit(res), "alasan": payload.alasan}, scope_entity_id=res.get("entity_id", ""))
    return res


@router.post("/{pengajuan_id}/cancel")
async def cancel_cash_out_request(pengajuan_id: str, request: Request,
                                  payload: Optional[CashOutRequestCancel] = None) -> Dict[str, Any]:
    actor = await require_any_permission(request, [("cash", "create"), ("cash", "delete")])
    doc = await _dokumen(request, pengajuan_id, tulis=True)
    # Pengaju membatalkan pengajuannya sendiri (`cash.create`); orang lain hanya bila memegang `cash.delete`.
    if not cors.pengaju_sendiri(doc, actor) and not await has_permission(actor, "cash", "delete"):
        raise denied([("cash", "delete")], cors.PESAN_BATAL_TANPA_IZIN)
    alasan = (payload.alasan if payload else "") or ""
    res = await cors.batal(pengajuan_id, actor, alasan)
    await audit(actor["name"], "cash_out_request_cancelled", "cash_out_request", pengajuan_id,
                {**_jejak_audit(res), "alasan": alasan}, scope_entity_id=res.get("entity_id", ""))
    return res

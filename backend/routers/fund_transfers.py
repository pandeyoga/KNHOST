"""Kas & Bank bagian 1 (D2, Tugas 4) — Pindah Dana antar rekening satu PT. Logika di
`services/fund_transfer_service.py`; layar Kas & Bank › Pindah Dana (Tugas 6).

Izin (spesifikasi §5.2, §7 butir 7 — tanpa izin baru): lihat `cash.view`, buat/terima `cash.create`, batal
`cash.delete`, setujui `cash.approve`. Cakupan PT: isian `entity_id` harus PT dalam penugasan (403); dokumen hanya
bisa dibaca/diubah dalam cakupan PT pengguna (`guard_doc`).

  GET  /api/fund-transfers                 daftar (`entity_id`, `status`, `q`, `page`, `page_size`)
  POST /api/fund-transfers                 `FundTransferCreate` → dokumen (`menunggu_persetujuan` bila butuh orang
                                           kedua; selain itu kas terbit: `dalam_perjalanan` / `selesai`)
  GET  /api/fund-transfers/{id}            dokumen + kas + penilaian kontrol dua orang untuk pengguna
  POST /api/fund-transfers/{id}/receive    `{tanggal}` — dana dalam perjalanan diterima rekening tujuan
  POST /api/fund-transfers/{id}/approve    orang kedua; kas terbit
  POST /api/fund-transfers/{id}/cancel     `{alasan}` (≥ 5 huruf) — semua kas dibalik
"""
from typing import Any, Dict

from fastapi import APIRouter, Query, Request

from dependencies import audit, require_permission
from entity_scope import entity_ctx, guard_doc, resolve_requested_entity, resolve_scope_ids
from pagination import MAX_PAGE_SIZE
from schemas_finance import FundTransferCancel, FundTransferCreate, FundTransferReceive
from services import approval_policy_service, fund_transfer_service as fts

router = APIRouter(prefix="/api/fund-transfers")


async def _dokumen(request: Request, transfer_id: str, *, tulis: bool) -> Dict[str, Any]:
    from db import db
    doc = await db[fts.COLL].find_one({"id": transfer_id}, {"_id": 0})
    await guard_doc(request, fts.COLL, doc, strict=tulis, not_found=fts.PESAN_TIDAK_ADA)
    return doc


def _jejak_audit(res: Dict[str, Any]) -> Dict[str, Any]:
    return {k: res.get(k) for k in ("number", "status", "nominal", "biaya", "rekening_asal_id", "rekening_tujuan_id",
                                    "tanggal_kirim", "tanggal_terima", "tanggal_diterima", "kas_ids", "gl_status")}


@router.get("")
async def list_fund_transfers(request: Request, entity_id: str = Query(None), status: str = Query(""),
                              q: str = Query(""), page: int = Query(1, ge=1),
                              page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "view")
    ids = resolve_scope_ids(await entity_ctx(request), entity_id)
    return await fts.daftar(ids, status=status, q=q, page=page, page_size=page_size, actor=actor)


@router.post("")
async def create_fund_transfer(payload: FundTransferCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    ctx = await entity_ctx(request)
    # PK-09 E8 — PT dari penugasan (isian di luar penugasan → 403); kosong = PT aktif (wajib satu PT, bukan grup).
    eid = resolve_requested_entity(ctx, payload.entity_id) if payload.entity_id else ctx.active_entity_id
    res = await fts.buat({**payload.model_dump(), "entity_id": eid}, actor)
    await audit(actor["name"], "fund_transfer_created", "fund_transfer", res["id"], _jejak_audit(res),
                scope_entity_id=res.get("entity_id", ""))
    return res


@router.get("/{transfer_id}")
async def get_fund_transfer(transfer_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "view")
    await _dokumen(request, transfer_id, tulis=False)
    return await fts.rincian(transfer_id, actor)


@router.post("/{transfer_id}/receive")
async def receive_fund_transfer(transfer_id: str, payload: FundTransferReceive, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "create")
    await _dokumen(request, transfer_id, tulis=True)
    res = await fts.terima(transfer_id, payload.tanggal, actor)
    await audit(actor["name"], "fund_transfer_received", "fund_transfer", transfer_id, _jejak_audit(res),
                scope_entity_id=res.get("entity_id", ""))
    return res


@router.post("/{transfer_id}/approve")
async def approve_fund_transfer(transfer_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "approve")
    doc = await _dokumen(request, transfer_id, tulis=True)
    # Kas & Bank 1 (Tugas 6) — Aturan Persetujuan jenis `fund_transfer` (bawaan: semua pemegang `cash.approve`).
    await approval_policy_service.guard_door("fund_transfer", actor, doc=doc, amount=float(doc.get("nominal") or 0))
    res = await fts.setujui(transfer_id, actor)
    await audit(actor["name"], "fund_transfer_approved", "fund_transfer", transfer_id, _jejak_audit(res),
                scope_entity_id=res.get("entity_id", ""))
    return res


@router.post("/{transfer_id}/cancel")
async def cancel_fund_transfer(transfer_id: str, payload: FundTransferCancel, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "delete")
    await _dokumen(request, transfer_id, tulis=True)
    res = await fts.batal(transfer_id, payload.alasan, actor)
    await audit(actor["name"], "fund_transfer_cancelled", "fund_transfer", transfer_id,
                {**_jejak_audit(res), "alasan": payload.alasan, "batal_gl_status": res.get("batal_gl_status")},
                scope_entity_id=res.get("entity_id", ""))
    return res

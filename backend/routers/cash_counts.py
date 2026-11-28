"""Kas & Bank bagian 3 (C3) — opname kas rekening tunai. Logika di `services/cash_count_service.py`; layar Kas & Bank ›
Opname Kas (tab tersembunyi, Tugas 4).

Izin (spesifikasi §5.3, §6 — tanpa izin baru): lihat `cash.view`, hitung `cash.create`, setujui/tolak selisih
`cash.approve` (+ Aturan Persetujuan jenis `cash_count`, `approval_policy_service.guard_door`; penghitung ≠ penyetuju
dijaga kontrol `kontrol.selisih_kas` di layanan). Cakupan PT: rekening yang dihitung harus milik PT dalam penugasan
(403); dokumen hanya bisa dibaca/diputus dalam cakupan PT pengguna (`guard_doc`, ketat untuk tulisan).

  GET  /api/cash-counts                    daftar (`entity_id`, `status`, `account_id`, `perlakuan`, `q`, `page`,
                                           `page_size`)
  POST /api/cash-counts                    `CashCountCreate` → opname (`selesai` bila tanpa selisih, selain itu
                                           `menunggu_persetujuan`)
  GET  /api/cash-counts/karyawan           karyawan HR PT (id, kode, nama) untuk perlakuan piutang karyawan
  GET  /api/cash-counts/{id}               opname + kas penyesuaian + penilaian kontrol dua orang untuk pengguna
  POST /api/cash-counts/{id}/approve       `{perlakuan, karyawan_id?}` — orang kedua; kas penyesuaian terbit
  POST /api/cash-counts/{id}/reject        `{alasan}` (≥ 5 huruf) — tanpa kas; penghitung menghitung ulang
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Query, Request

from dependencies import audit, require_permission
from entity_scope import entity_ctx, guard_doc, resolve_requested_entity, resolve_scope_ids
from pagination import MAX_PAGE_SIZE
from schemas_finance import CashCountApprove, CashCountCreate, CashCountReject
from services import approval_policy_service, cash_count_service as ccs

router = APIRouter(prefix="/api/cash-counts")


async def _dokumen(request: Request, count_id: str, *, tulis: bool) -> Dict[str, Any]:
    from db import db
    doc = await db[ccs.COLL].find_one({"id": count_id}, {"_id": 0})
    await guard_doc(request, ccs.COLL, doc, strict=tulis, not_found=ccs.PESAN_TIDAK_ADA)
    return doc


def _jejak_audit(res: Dict[str, Any]) -> Dict[str, Any]:
    return {k: res.get(k) for k in ("number", "status", "account_id", "saldo_buku", "jumlah_fisik", "selisih",
                                    "perlakuan", "karyawan_id", "cash_id", "cash_number", "tanggal")}


@router.get("")
async def list_cash_counts(request: Request, entity_id: str = Query(None), status: str = Query(""),
                           account_id: str = Query(""), perlakuan: str = Query(""), q: str = Query(""),
                           page: int = Query(1, ge=1),
                           page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "view")
    ids = resolve_scope_ids(await entity_ctx(request), entity_id)
    return await ccs.daftar(ids, status=status, account_id=account_id, perlakuan=perlakuan, q=q, page=page,
                            page_size=page_size, actor=actor)


@router.post("")
async def create_cash_count(payload: CashCountCreate, request: Request) -> Dict[str, Any]:
    from db import db
    actor = await require_permission(request, "cash", "create")
    # PT = PT rekening; rekening PT di luar penugasan → 403 sebelum pemeriksaan isi lain (PK-09 E8).
    acc = await db.bank_accounts.find_one({"id": (payload.account_id or "").strip() or "__none__"},
                                          {"_id": 0, "entity_id": 1})
    if acc and acc.get("entity_id"):
        resolve_requested_entity(await entity_ctx(request), acc["entity_id"])
    res = await ccs.buat(payload, actor)
    await audit(actor["name"], "cash_count_created", "cash_count", res["id"], _jejak_audit(res),
                scope_entity_id=res.get("entity_id", ""))
    return res


@router.get("/karyawan")
async def list_cash_count_employees(request: Request, entity_id: str = Query(None),
                                    q: str = Query("")) -> List[Dict[str, Any]]:
    """Pemilih karyawan untuk perlakuan piutang karyawan — pemegang `cash.approve` (penyetuju kas tidak harus memegang
    izin SDM); PT di luar penugasan → 403."""
    await require_permission(request, "cash", "approve")
    eid = resolve_requested_entity(await entity_ctx(request), entity_id)
    return await ccs.karyawan(eid, q)


@router.get("/{count_id}")
async def get_cash_count(count_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "view")
    await _dokumen(request, count_id, tulis=False)
    return await ccs.rincian(count_id, actor)


@router.post("/{count_id}/approve")
async def approve_cash_count(count_id: str, payload: CashCountApprove, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "approve")
    doc = await _dokumen(request, count_id, tulis=True)
    # Aturan Persetujuan jenis `cash_count` (bawaan: semua pemegang `cash.approve`).
    await approval_policy_service.guard_door("cash_count", actor, doc=doc,
                                             amount=float(doc.get("selisih_nominal") or 0))
    res = await ccs.setujui(count_id, payload, actor)
    await audit(actor["name"], "cash_count_approved", "cash_count", count_id, _jejak_audit(res),
                scope_entity_id=res.get("entity_id", ""))
    return res


@router.post("/{count_id}/reject")
async def reject_cash_count(count_id: str, payload: CashCountReject, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash", "approve")
    doc = await _dokumen(request, count_id, tulis=True)
    await approval_policy_service.guard_door("cash_count", actor, doc=doc,
                                             amount=float(doc.get("selisih_nominal") or 0), action="reject")
    res = await ccs.tolak(count_id, payload.alasan, actor)
    await audit(actor["name"], "cash_count_rejected", "cash_count", count_id,
                {**_jejak_audit(res), "alasan": payload.alasan}, scope_entity_id=res.get("entity_id", ""))
    return res

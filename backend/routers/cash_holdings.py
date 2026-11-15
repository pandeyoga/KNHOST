"""PM-T4 (PM-06, K-36) — titipan tunai sales dan setorannya (Keuangan › Kas & Bank › Titipan Sales; kartu HP
"Titipan Saya"). Logika di `services/cash_holding_service.py`; kwitansi titipan lahir dari `POST /api/ar-receipts`.

Izin `cash_holding` (modul akses "Kas, Bank & Kasus Keuangan"): `view` melihat (milik sendiri; semua bila juga memegang
`approve`), `create` mengajukan/membatalkan setoran sendiri, `approve` menerima/menolak setoran. Ringkasan milik sendiri
`GET /api/cash-holdings/me/summary` = login saja (Z3, `login_only_endpoints.LOGIN_ONLY`). Awalan `/api/cash-deposits`
ada di `IDEMPOTENT_PREFIXES` (kirim ulang = satu setoran / satu penerimaan).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from db import db
from dependencies import audit, has_permission, require_permission, current_user
from entity_scope import entity_ctx, guard_doc, resolve_list_scope, resolve_requested_entity, resolve_scope_ids
from pagination import get_page_params
from services import cash_holding_service as svc

router = APIRouter(prefix="/api")


class DepositIn(BaseModel):
    amount: float
    holding_ids: List[str] = Field(default_factory=list)
    note: str = Field("", max_length=500)


class ReceiveIn(BaseModel):
    account_id: str = Field("", max_length=80)


class ReasonIn(BaseModel):
    reason: str = Field("", max_length=500)


def _benar(v: Optional[str]) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "ya", "yes")


@router.get("/cash-holdings")
async def list_cash_holdings(request: Request, status: Optional[str] = Query(None),
                             holder_user_id: Optional[str] = Query(None), overdue: Optional[str] = Query(None),
                             entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Titipan tunai per PT, berhalaman (`page`, `page_size`, `q`), bawaan status terbuka. Tanpa `cash_holding.approve`
    hanya titipan milik sendiri. `holders` = ringkasan per pemegang atas semua baris yang cocok saringan."""
    actor = await require_permission(request, "cash_holding", "view")
    ctx = await entity_ctx(request)
    scope = resolve_list_scope("cash_holdings", {}, ctx, entity_id)
    holder = (holder_user_id or "").strip()
    if not await has_permission(actor, "cash_holding", "approve"):
        holder = actor["id"] if holder in ("", actor["id"]) else "__bukan_milik_sendiri__"
    page, page_size, q, _sort = get_page_params(request)
    return await svc.daftar_titipan(scope, entity_ids=resolve_scope_ids(ctx, entity_id), status=status,
                                    holder_user_id=holder, overdue=_benar(overdue), q=q, page=page,
                                    page_size=page_size)


@router.get("/cash-holdings/me/summary")
async def my_cash_holding_summary(request: Request) -> Dict[str, Any]:
    """Ringkasan titipan MILIK SENDIRI di PT aktif (login saja, Z3): dipegang, jumlah kwitansi, batas, tenggat
    terdekat, mode tunai yang berlaku untuk akun ini (bahan teks bantu form kwitansi & kartu "Titipan Saya")."""
    actor = await current_user(request)
    ctx = await entity_ctx(request)
    return await svc.ringkasan_saya(ctx.active_entity_id or "", actor)


@router.get("/cash-deposits")
async def list_cash_deposits(request: Request, status: Optional[str] = Query(None),
                             holder_user_id: Optional[str] = Query(None),
                             entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Setoran titipan per PT, berhalaman; bawaan `diajukan` (bagian "Setoran menunggu diterima"). Tanpa
    `cash_holding.approve` hanya setoran milik sendiri."""
    actor = await require_permission(request, "cash_holding", "view")
    ctx = await entity_ctx(request)
    scope = resolve_list_scope("cash_deposits", {}, ctx, entity_id)
    holder = (holder_user_id or "").strip()
    if not await has_permission(actor, "cash_holding", "approve"):
        holder = actor["id"] if holder in ("", actor["id"]) else "__bukan_milik_sendiri__"
    page, page_size, q, _sort = get_page_params(request)
    return await svc.daftar_setoran(scope, status=status, holder_user_id=holder, q=q, page=page, page_size=page_size)


@router.post("/cash-deposits")
async def create_cash_deposit(payload: DepositIn, request: Request) -> Dict[str, Any]:
    """Ajukan setoran titipan milik sendiri di PT aktif (N1: PT dari konteks, bukan isi permintaan)."""
    actor = await require_permission(request, "cash_holding", "create")
    ctx = await entity_ctx(request)
    ent = resolve_requested_entity(ctx, None)
    dep = await svc.ajukan_setoran(ent, actor, payload.amount, payload.holding_ids, payload.note)
    await audit(actor["name"], "cash_deposit_submitted", "cash_deposit", dep["id"],
                {"number": dep.get("number"), "amount": dep.get("amount")})
    return dep


async def _dep_guard(request: Request, dep_id: str) -> Dict[str, Any]:
    d = await db.cash_deposits.find_one({"id": dep_id}, {"_id": 0})
    await guard_doc(request, "cash_deposits", d, not_found="Setoran tidak ditemukan.")
    return d


@router.post("/cash-deposits/{dep_id}/receive")
async def receive_cash_deposit(dep_id: str, payload: ReceiveIn, request: Request) -> Dict[str, Any]:
    """Terima setoran ke rekening kas/bank PT setoran → satu transaksi kas (Dr kas / Cr piutang titipan karyawan)."""
    actor = await require_permission(request, "cash_holding", "approve")
    await _dep_guard(request, dep_id)
    dep = await svc.terima_setoran(dep_id, actor, payload.account_id)
    await audit(actor["name"], "cash_deposit_received", "cash_deposit", dep_id,
                {"number": dep.get("number"), "amount": dep.get("amount"), "account_id": dep.get("account_id"),
                 "gl_status": dep.get("gl_status")})
    return dep


@router.post("/cash-deposits/{dep_id}/reject")
async def reject_cash_deposit(dep_id: str, payload: ReasonIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_holding", "approve")
    await _dep_guard(request, dep_id)
    dep = await svc.tolak_setoran(dep_id, actor, payload.reason)
    await audit(actor["name"], "cash_deposit_rejected", "cash_deposit", dep_id,
                {"number": dep.get("number"), "reason": dep.get("decision_reason")})
    return dep


@router.post("/cash-deposits/{dep_id}/cancel")
async def cancel_cash_deposit(dep_id: str, payload: ReasonIn, request: Request) -> Dict[str, Any]:
    """Penyetor membatalkan setorannya sendiri yang belum diputus (titipan tidak berubah)."""
    actor = await require_permission(request, "cash_holding", "create")
    await _dep_guard(request, dep_id)
    dep = await svc.batalkan_setoran(dep_id, actor, payload.reason)
    await audit(actor["name"], "cash_deposit_cancelled", "cash_deposit", dep_id,
                {"number": dep.get("number"), "reason": dep.get("decision_reason")})
    return dep

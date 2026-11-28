"""Router — Form Pengajuan Dana (Cash Advance) + Pertanggungjawaban (Settlement).

Koleksi kanonik: cash_advances (ca_), cash_advance_settlements (stl_), expense_categories (excat_).
RBAC: modul `cash_advance` & `cash_settlement`. Rantai approval berjenjang (state-machine di service).
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi.responses import Response

from dependencies import has_permission, require_any_permission, require_permission
from services import approval_policy_service as _aps   # KP-T4 — satu tabel kebijakan persetujuan
from entity_scope import entity_ctx, resolve_requested_entity
from schemas_cash_advance import (
    CashAdvanceCreate, CashAdvanceUpdate, ApprovalDecision, CashAdvanceCancel, DisburseInput,
    SettlementCreate, SettlementUpdate, ExpenseCategoryUpdate, ReturnRemainderIn,
)
from services import cash_advance_service as svc

router = APIRouter(prefix="/api")


# ─── Expense Categories (mapping kategori → akun) ────────────────────────
@router.get("/expense-categories")
async def list_expense_categories(request: Request, active_only: bool = Query(False)) -> List[Dict[str, Any]]:
    """FASE E-4 (E4.3) — kategori EFEKTIF badan usaha aktif: global + override, tanpa kembar."""
    await require_permission(request, "cash_settlement", "view")
    ctx = await entity_ctx(request)
    return await svc.list_expense_categories(active_only=active_only,
                                             entity_id=ctx.active_entity_id)


@router.patch("/expense-categories/{code}")
async def update_expense_category(code: str, payload: ExpenseCategoryUpdate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_settlement", "manage")
    return await svc.update_expense_category(code, payload.model_dump(exclude_none=True), actor)


# ─── Cash Advance (Form PD) ──────────────────────────────────────
@router.get("/cash-advances")
async def list_cash_advances(request: Request, entity_id: str = Query(None),
                             status: str = Query(None)) -> List[Dict[str, Any]]:
    """Kas & Bank 4 — tiap baris membawa `pemegang`, `lpj_jatuh_tempo`, `tenggat_status`, `tenggat_hari_lewat`,
    `bisa_ajukan`/`alasan_ajukan`."""
    actor = await require_permission(request, "cash_advance", "view")
    ctx = await entity_ctx(request)
    return await svc.list_cash_advances(ctx, entity_id=entity_id, status=status, actor=actor)


@router.get("/cash-advances/karyawan")
async def list_cash_advance_employees(request: Request, entity_id: str = Query(None),
                                      q: str = Query("")) -> List[Dict[str, Any]]:
    """Kas & Bank 4 (§7.9.3) — pilihan pemegang uang: karyawan HR aktif PT (id, kode, nama) bagi pemegang
    `cash_advance.create` (pembuat PD tidak harus memegang izin SDM); PT di luar penugasan → 403."""
    await require_permission(request, "cash_advance", "create")
    eid = resolve_requested_entity(await entity_ctx(request), entity_id)
    return await svc.karyawan_pemegang(eid, q)


@router.post("/cash-advances")
async def create_cash_advance(payload: CashAdvanceCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_advance", "create")
    ctx = await entity_ctx(request)
    return await svc.create_cash_advance(payload, ctx, actor)


@router.get("/cash-advances/{ca_id}")
async def get_cash_advance(ca_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_advance", "view")
    ctx = await entity_ctx(request)
    return await svc.rincian_cash_advance(ca_id, ctx, actor)


@router.patch("/cash-advances/{ca_id}")
async def update_cash_advance(ca_id: str, payload: CashAdvanceUpdate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_advance", "update")
    ctx = await entity_ctx(request)
    return await svc.update_cash_advance(ca_id, payload, ctx, actor)


@router.post("/cash-advances/{ca_id}/submit")
async def submit_cash_advance(ca_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_advance", "submit")
    ctx = await entity_ctx(request)
    return await svc.submit_cash_advance(ca_id, ctx, actor)


@router.post("/cash-advances/{ca_id}/approve")
async def approve_cash_advance(ca_id: str, payload: ApprovalDecision, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_advance", "approve")
    ctx = await entity_ctx(request)
    return await svc.approve_cash_advance(ca_id, payload.note, ctx, actor)


@router.post("/cash-advances/{ca_id}/reject")
async def reject_cash_advance(ca_id: str, payload: ApprovalDecision, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_advance", "reject")
    ctx = await entity_ctx(request)
    return await svc.reject_cash_advance(ca_id, payload.note, ctx, actor)


@router.post("/cash-advances/{ca_id}/cancel")
async def cancel_cash_advance(ca_id: str, payload: CashAdvanceCancel, request: Request) -> Dict[str, Any]:
    """Kas & Bank 4 (§7.9.4) — Batalkan PD belum cair (draf/ditolak/dalam persetujuan/disetujui) beralasan. Pintu: izin
    `cash_advance.create` (pembuat) atau `cash_advance.reject`; layanan memastikan pembuat PD atau pemegang izin tolak."""
    actor = await require_any_permission(request, [("cash_advance", "create"), ("cash_advance", "reject")])
    ctx = await entity_ctx(request)
    return await svc.cancel_cash_advance(ca_id, payload.alasan, ctx, actor)


@router.post("/cash-advances/{ca_id}/disburse")
async def disburse_cash_advance(ca_id: str, payload: DisburseInput, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_advance", "disburse")
    ctx = await entity_ctx(request)
    return await svc.disburse_cash_advance(ca_id, payload, ctx, actor)


# ─── MN-T2 — daftar kerja Kas Kecil (Keuangan › Kas & Bank › Kas Kecil) ─────────────────────────
@router.get("/petty-cash/worklist")
async def petty_cash_worklist(request: Request, stage: str = Query(""), q: str = Query(""),
                              page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                              entity_id: str = Query(None)) -> Dict[str, Any]:
    """Satu baris per pengajuan dana + pertanggungjawabannya, tahap turunan, jumlah per tahap.
    Izin salah satu: `cash_advance.view` · `cash_settlement.view`. Hutang reimburse per baris hanya bagi pemegang
    `cash_settlement.view` (izin laporan Hutang Reimburse sejak PK-24)."""
    actor = await require_any_permission(request, [("cash_advance", "view"), ("cash_settlement", "view")])
    ctx = await entity_ctx(request)
    return await svc.petty_cash_worklist(
        ctx, entity_id=entity_id, stage=stage, q=q, page=page, page_size=page_size,
        lihat_pd=await has_permission(actor, "cash_advance", "view"),
        lihat_reimburse=await has_permission(actor, "cash_settlement", "view"))


# ─── Settlement (Pertanggungjawaban) ────────────────────────────────
@router.get("/cash-advance-settlements")
async def list_settlements(request: Request, entity_id: str = Query(None),
                           cash_advance_id: str = Query(None),
                           status: str = Query(None)) -> List[Dict[str, Any]]:
    await require_permission(request, "cash_settlement", "view")
    ctx = await entity_ctx(request)
    return await svc.list_settlements(ctx, entity_id=entity_id,
                                      cash_advance_id=cash_advance_id, status=status)


@router.get("/cash-advance-settlements/reimburse-payables")
async def reimburse_payables(request: Request, entity_id: str = Query(None)) -> Dict[str, Any]:
    """Laporan Hutang Reimburse Karyawan (2-1650) terbuka per karyawan + umur hutang.
    PK-24 (IA-05) — izin kas kecil `cash_settlement.view` (dulu `accounting.view`)."""
    await require_permission(request, "cash_settlement", "view")
    ctx = await entity_ctx(request)
    return await svc.reimburse_payables(ctx, entity_id=entity_id)


@router.post("/cash-advance-settlements")
async def create_settlement(payload: SettlementCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_settlement", "create")
    ctx = await entity_ctx(request)
    return await svc.create_settlement(payload, ctx, actor)


@router.get("/cash-advance-settlements/{stl_id}")
async def get_settlement(stl_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "cash_settlement", "view")
    ctx = await entity_ctx(request)
    return await svc.get_settlement(stl_id, ctx)


@router.patch("/cash-advance-settlements/{stl_id}")
async def update_settlement(stl_id: str, payload: SettlementUpdate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_settlement", "update")
    ctx = await entity_ctx(request)
    return await svc.update_settlement(stl_id, payload, ctx, actor)


@router.post("/cash-advance-settlements/{stl_id}/submit")
async def submit_settlement(stl_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_settlement", "submit")
    ctx = await entity_ctx(request)
    return await svc.submit_settlement(stl_id, ctx, actor)


@router.post("/cash-advance-settlements/{stl_id}/reopen")
async def reopen_settlement(stl_id: str, request: Request) -> Dict[str, Any]:
    """PK-24 — LPJ ditolak dibuka lagi (→ draf) oleh pembuatnya untuk diperbaiki dan diajukan ulang."""
    actor = await require_permission(request, "cash_settlement", "update")
    ctx = await entity_ctx(request)
    return await svc.reopen_settlement(stl_id, ctx, actor)


# ─── PK-24 — lampiran bukti pengeluaran (unggah & hapus hanya saat draf) ─────────────
@router.post("/cash-advance-settlements/{stl_id}/attachments")
async def upload_settlement_attachment(stl_id: str, request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_settlement", "update")
    ctx = await entity_ctx(request)
    data = await file.read()
    return await svc.add_settlement_attachment(stl_id, file.filename or "", file.content_type or "", data, ctx, actor)


@router.get("/cash-advance-settlements/{stl_id}/attachments/{att_id}")
async def get_settlement_attachment(stl_id: str, att_id: str, request: Request, download: bool = False) -> Response:
    await require_permission(request, "cash_settlement", "view")
    ctx = await entity_ctx(request)
    att, data = await svc.get_settlement_attachment(stl_id, att_id, ctx)
    from services.return_attachment_service import disposition
    return Response(content=data, media_type=att.get("content_type") or "application/octet-stream",
                    headers={"Content-Disposition": disposition(att, download)})


@router.delete("/cash-advance-settlements/{stl_id}/attachments/{att_id}")
async def delete_settlement_attachment(stl_id: str, att_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_settlement", "update")
    ctx = await entity_ctx(request)
    return await svc.delete_settlement_attachment(stl_id, att_id, ctx, actor)


class ReimbursePayIn(BaseModel):
    cash_type: str = "kas_besar"
    txn_date: Optional[str] = None
    account_id: str = ""      # PK-20 — rekening sumber (`bank_accounts` milik PT LPJ); kosong = rekening tunggal


@router.post("/cash-advance-settlements/{stl_id}/pay-reimburse")
async def pay_reimburse(stl_id: str, payload: ReimbursePayIn, request: Request) -> Dict[str, Any]:
    """CX-05 — bayar kelebihan LPJ (Hutang Reimburse Karyawan 2-1650) ke karyawan.
    PK-24 (IA-05) — izin kas kecil `cash_settlement.pay` (dulu `accounting.create`)."""
    actor = await require_permission(request, "cash_settlement", "pay")
    ctx = await entity_ctx(request)
    return await svc.pay_reimburse(stl_id, payload, ctx, actor)


@router.post("/cash-advance-settlements/{stl_id}/return-remainder")
async def return_remainder(stl_id: str, payload: ReturnRemainderIn, request: Request) -> Dict[str, Any]:
    """PK-24 (SL-09) — terima pengembalian sisa uang muka dari karyawan: kas masuk Dr Kas / Cr uang muka karyawan."""
    actor = await require_permission(request, "cash_settlement", "pay")
    ctx = await entity_ctx(request)
    return await svc.return_remainder(stl_id, payload, ctx, actor)


@router.post("/cash-advance-settlements/{stl_id}/approve")
async def approve_settlement(stl_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_settlement", "approve")
    ctx = await entity_ctx(request)
    await _aps.guard_door("cash_advance_settlement", actor, collection="cash_advance_settlements",
                          doc_id=stl_id)   # KP-T4 — Aturan Persetujuan
    return await svc.approve_settlement(stl_id, ctx, actor)


@router.post("/cash-advance-settlements/{stl_id}/reject")
async def reject_settlement(stl_id: str, payload: ApprovalDecision, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "cash_settlement", "reject")
    ctx = await entity_ctx(request)
    return await svc.reject_settlement(stl_id, payload.note, ctx, actor)

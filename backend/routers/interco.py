"""FASE G-6 — Router **TRANSAKSI ANTAR ENTITAS** (jual-beli antar-PT).

Endpoint `/api/interco/*`. Router sengaja TIPIS: seluruh aturan uang ada di
`services/interco_service.py` supaya bisa diuji tanpa HTTP.

Sinergi dengan G-7 (kontrabon): pola "satu dokumen menutup banyak transaksi"
dipakai ulang untuk settlement (netting) via `/interco/settlements`.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from dependencies import audit, require_any_permission, require_permission
from entity_scope import entity_ctx, guard_party, resolve_scope_ids
from schemas_interco import (
    IntercoActionIn, IntercoCreate, IntercoReasonIn, IntercoReturnCreate,
    IntercoSettlementCreate, IntercoTaxIssueIn,
)
from schemas_return_rolls import ReturnRollDecisionsIn
from services import interco_margin as icmargin
from services import interco_reminder as icrem
from services import interco_return_service as icret
from services import interco_service as ics
from services import interco_tax_service as ictax

router = APIRouter(prefix="/api")


async def _scope(request: Request, entity_id: Optional[str] = None) -> List[str]:
    ctx = await entity_ctx(request)
    return resolve_scope_ids(ctx, entity_id)


def _fail(exc: Exception) -> HTTPException:
    """Galat bisnis antar-PT → 400. PK-06: pemeriksaan jurnal kedua buku gagal (`TwinJournalError`) dan konflik
    keadaan (`IntercoConflict`: sisa berubah, jurnal transaksi masih gagal) → 409."""
    from services.twin_journal import TwinJournalError
    if isinstance(exc, (TwinJournalError, ics.IntercoConflict)):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def _biz_errors():
    from services.twin_journal import TwinJournalError
    return (ics.IntercoError, ics.IntercoConflict, TwinJournalError)


# PK-09 (IC-11) — penjaga pihak bersama: `entity_scope.guard_party` membaca kolom pihak di dokumen DAN di anak pasangan
# (`seller`/`buyer`/`returner`/`receiver`). Pengganti `_guard_party` lokal yang dulu tidak pernah menolak transaksi.


async def _assert_one_side(request: Request, a: str, b: str) -> None:
    """PK-09 E39/E40 — salah satu PT di jalur harus PT pengguna; selain itu 404 (tidak membuka keberadaan pasangan)."""
    if not ({a, b} & set((await entity_ctx(request)).allowed_entity_ids)):
        raise HTTPException(status_code=404, detail="Data tidak ditemukan untuk entitas ini")


# ── Meta & ringkasan ─────────────────────────────────────────────────────────
@router.get("/interco/meta")
async def interco_meta(request: Request) -> Dict[str, Any]:
    await require_permission(request, "interco", "view")
    return await ics.meta()


@router.get("/interco/summary")
async def interco_summary(request: Request, entity_id: str = "") -> Dict[str, Any]:
    await require_permission(request, "interco", "view")
    scope = await _scope(request, entity_id)
    return await ics.summary(scope, entity_id)


# ── Transaksi ────────────────────────────────────────────────────────────────
@router.get("/interco/transactions")
async def list_ict(request: Request, entity_id: str = "", status: str = "",
                    role: str = "", limit: int = 200) -> List[Dict[str, Any]]:
    await require_permission(request, "interco", "view")
    scope = await _scope(request, entity_id)
    from pagination import clamp_limit   # FIX-5 (B3b LST-03)
    return await ics.list_transactions(scope, entity_id=entity_id, status=status,
                                        role=role, limit=clamp_limit(limit, 200, 500))


@router.post("/interco/transactions")
async def create_ict(payload: IntercoCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "interco", "create")
    ctx = await entity_ctx(request)
    if payload.seller_entity_id not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=403,
                            detail="Tidak berwenang menerbitkan transaksi untuk PT penjual ini.")
    try:
        res = await ics.create(payload.model_dump(), actor.get("name", ""), actor_user=actor)
    except _biz_errors() as exc:
        raise _fail(exc) from exc
    await audit(actor.get("name", ""), "interco_transaction_created",
                "interco_transaction", res.get("pair_id", ""),
                {"seller": payload.seller_entity_id, "buyer": payload.buyer_entity_id,
                 "grand_total": res.get("seller", {}).get("grand_total")})
    return res


@router.get("/interco/transactions/{interco_id}")
async def get_ict(interco_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "interco", "view")
    return await guard_party(request, await ics.get_one(interco_id), label="Transaksi antar-PT")


@router.post("/interco/transactions/{interco_id}/confirm")
async def confirm_ict(interco_id: str, payload: IntercoActionIn,
                     request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "interco", "approve")
    await guard_party(request, await ics.get_one(interco_id), label="Transaksi antar-PT")
    try:
        res = await ics.confirm(interco_id, actor)
    except _biz_errors() as exc:
        raise _fail(exc) from exc
    await audit(actor.get("name", ""), "interco_transaction_confirmed",
                "interco_transaction", interco_id, {"note": payload.note})
    return res


@router.post("/interco/transactions/{interco_id}/ship")
async def ship_ict(interco_id: str, payload: IntercoActionIn,
                  request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "interco", "ship")
    await guard_party(request, await ics.get_one(interco_id), label="Transaksi antar-PT")
    try:
        res = await ics.ship(interco_id, actor.get("name", ""))
    except ics.IntercoError as exc:
        raise _fail(exc) from exc
    await audit(actor.get("name", ""), "interco_transaction_shipped",
                "interco_transaction", interco_id, {"note": payload.note})
    return res


@router.post("/interco/transactions/{interco_id}/receive")
async def receive_ict(interco_id: str, payload: IntercoActionIn,
                      request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "interco", "receive")
    await guard_party(request, await ics.get_one(interco_id), label="Transaksi antar-PT")
    try:
        res = await ics.receive(interco_id, actor.get("name", ""))
    except ics.IntercoError as exc:
        raise _fail(exc) from exc
    await audit(actor.get("name", ""), "interco_transaction_received",
                "interco_transaction", interco_id, {"note": payload.note})
    return res


@router.post("/interco/transactions/{interco_id}/invoice")
async def invoice_ict(interco_id: str, payload: IntercoActionIn,
                     request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "interco", "invoice")
    await guard_party(request, await ics.get_one(interco_id), label="Transaksi antar-PT")
    try:
        res = await ics.invoice(interco_id, actor.get("name", ""))
    except ics.IntercoError as exc:
        raise _fail(exc) from exc
    await audit(actor.get("name", ""), "interco_transaction_invoiced",
                "interco_transaction", interco_id, {"note": payload.note})
    return res


@router.post("/interco/transactions/{interco_id}/cancel")
async def cancel_ict(interco_id: str, payload: IntercoActionIn,
                    request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "interco", "cancel")
    await guard_party(request, await ics.get_one(interco_id), label="Transaksi antar-PT")
    try:
        res = await ics.cancel(interco_id, actor.get("name", ""), payload.note)
    except ics.IntercoError as exc:
        raise _fail(exc) from exc
    await audit(actor.get("name", ""), "interco_transaction_cancelled",
                "interco_transaction", interco_id, {"reason": payload.note})
    return res


# ── Bukti akuntansi & jembatan gudang ────────────────────────────────────────
@router.get("/interco/transactions/{interco_id}/journal")
async def journal_ict(interco_id: str, request: Request) -> Dict[str, Any]:
    """Jurnal DUA BUKU + eliminasi grup + tugas gudang untuk satu pair (US7/US8/US10).

    Satu panggilan supaya Detail Panel bisa menunjukkan bukti yang SAMA dengan
    yang dipakai invarian INV-IC-01..05 (bukan tebakan dari daftar jurnal umum).
    """
    await require_permission(request, "interco", "view")
    doc = await guard_party(request, await ics.get_one(interco_id), label="Transaksi antar-PT")   # PK-09 E34
    return await ics.pair_journal(doc["pair_id"])


@router.post("/interco/transactions/{interco_id}/warehouse-task")
async def warehouse_task_ict(interco_id: str, payload: IntercoActionIn,
                             request: Request) -> Dict[str, Any]:
    """Terbitkan tugas gudang untuk memindahkan barangnya (US8).

    Tugas ini menyimpan `interco_pair_id` sehingga saat gudang menyetujuinya:
    jurnal at-cost M-3 DILEWATI (G-6 sudah memposting harga jual) dan nilai roll
    di PT pembeli dinilai ulang ke harga beli internal.
    """
    actor = await require_permission(request, "interco", "ship")
    await guard_party(request, await ics.get_one(interco_id), label="Transaksi antar-PT")
    try:
        res = await ics.create_warehouse_task(interco_id, actor.get("name", ""))
    except ics.IntercoError as exc:
        raise _fail(exc) from exc
    await audit(actor.get("name", ""), "interco_warehouse_task_created",
                "warehouse_transfer", res.get("id", ""),
                {"code": res.get("code"), "interco_pair_id": res.get("interco_pair_id"),
                 "note": payload.note})
    return res


# ── Saldo antar-PT ───────────────────────────────────────────────────────────
@router.get("/interco/accounts")
async def list_ica(request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "interco_finance", "view")  # FASE E-0 (L20)
    scope = await _scope(request)
    return await ics.list_accounts(scope)


@router.get("/interco/accounts/{from_entity_id}/{to_entity_id}")
async def get_ica(from_entity_id: str, to_entity_id: str,
                 request: Request, role: str = "payable") -> Dict[str, Any]:
    """Saldo satu arah: bawaan **utang `from` kepada `to`** (`role=receivable`
    untuk piutang). Peran wajib ikut karena satu pasangan PT bisa berdagang dua
    arah sekaligus — lihat KN-G6-ICA-CLOBBER."""
    await require_permission(request, "interco_finance", "view")  # FASE E-0 (L20)
    await _assert_one_side(request, from_entity_id, to_entity_id)   # PK-09 E39
    try:
        return await ics.get_account(from_entity_id, to_entity_id, role=role)
    except ics.IntercoError as exc:
        raise _fail(exc) from exc


# ── Settlement (netting) ─────────────────────────────────────────────────────
@router.get("/interco/payment-schedule")
async def interco_payment_schedule(request: Request, payer_entity_id: str = "", payee_entity_id: str = "") -> Dict[str, Any]:
    """LN-024 — utang antar-PT per transaksi + periode bayar (bila cutoff KLX-03 sudah dikonfigurasi)."""
    await require_permission(request, "interco_finance", "view")
    scope = await _scope(request, "")
    return await ics.payment_schedule(scope, payer=payer_entity_id, payee=payee_entity_id)


@router.get("/interco/settlements")
async def list_ics(request: Request, entity_id: str = "",
                   limit: int = 200) -> List[Dict[str, Any]]:
    await require_permission(request, "interco_finance", "view")  # FASE E-0 (L20)
    scope = await _scope(request, entity_id)
    from pagination import clamp_limit   # FIX-5 (B3b LST-03)
    return await ics.list_settlements(scope, entity_id=entity_id, limit=clamp_limit(limit, 200, 500))


@router.post("/interco/settlements")
async def create_ics(payload: IntercoSettlementCreate,
                     request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "interco", "settle")
    ctx = await entity_ctx(request)
    if payload.payer_entity_id not in ctx.allowed_entity_ids:
        raise HTTPException(status_code=403,
                            detail="Tidak berwenang menerbitkan settlement untuk PT pembayar ini.")
    try:
        res = await ics.create_settlement(payload.model_dump(), actor.get("name", ""),
                                          idempotency_key=(request.headers.get("Idempotency-Key") or "").strip())
    except _biz_errors() as exc:
        raise _fail(exc) from exc
    await audit(actor.get("name", ""), "interco_settlement_created",
                "interco_settlement", res.get("id", ""),
                {"payer": payload.payer_entity_id, "payee": payload.payee_entity_id,
                 "total": res.get("total_applied")})
    return res


@router.get("/interco/settlements/{sid}")
async def get_ics(sid: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "interco_finance", "view")  # FASE E-0 (L20)
    return await guard_party(request, await ics.get_settlement(sid), label="Settlement")   # PK-09 E41


# ── Kontrak internal helper (partner_kind="entity") ──────────────────────────
@router.get("/interco/contracts")
async def list_internal_contracts(request: Request, seller_entity_id: str = "",
                                   buyer_entity_id: str = "") -> List[Dict[str, Any]]:
    """Daftar kontrak internal aktif (partner_kind='entity') — dipakai wizard harga."""
    await require_permission(request, "interco", "view")
    from db import db
    q: Dict[str, Any] = {"partner_kind": "entity", "status": "active"}
    if seller_entity_id:
        q["entity_id"] = seller_entity_id
    if buyer_entity_id:
        q["partner_id"] = buyer_entity_id
    rows = await db.supplier_contracts.find(q, {"_id": 0}).sort("updated_at", -1).to_list(500)
    # PK-09 E42 — hanya kontrak yang salah satu pihaknya (penjual `entity_id` / pembeli `partner_id`) PT pengguna.
    allowed = set((await entity_ctx(request)).allowed_entity_ids)
    return [r for r in rows if r.get("entity_id") in allowed or r.get("partner_id") in allowed]


# ═════════════════════════════════════════════════════════════════════════════
#  FASE G-6b — FAKTUR PAJAK INTERNAL (transaksi antar-PT ber-PPN)
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/interco/transactions/{interco_id}/tax-invoice")
async def get_interco_tax(interco_id: str, request: Request) -> Dict[str, Any]:
    """Keadaan faktur pajak internal + ALASAN bila belum bisa diterbitkan."""
    await require_permission(request, "interco", "view")
    doc = await guard_party(request, await ics.get_one(interco_id), label="Transaksi antar-PT")   # PK-09 E35
    return await ictax.state(doc["pair_id"])


@router.post("/interco/transactions/{interco_id}/tax-invoice")
async def issue_interco_tax(interco_id: str, payload: IntercoTaxIssueIn,
                            request: Request) -> Dict[str, Any]:
    """Terbitkan PASANGAN faktur pajak internal: keluaran penjual + masukan pembeli."""
    actor = await require_permission(request, "interco", "tax")
    await guard_party(request, await ics.get_one(interco_id), label="Transaksi antar-PT")
    doc = await ics.get_one(interco_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Transaksi antar-PT tidak ditemukan.")
    try:
        res = await ictax.issue(doc["pair_id"], actor=actor.get("name", ""),
                                nsfp=payload.nsfp,
                                kode_transaksi=payload.kode_transaksi or "01",
                                faktur_date=payload.faktur_date)
    except ictax.IntercoTaxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "interco_tax_invoice_issued", "tax_invoice",
                (res.get("out") or {}).get("id", ""),
                {"pair_id": doc["pair_id"],
                 "out": (res.get("out") or {}).get("number"),
                 "in": (res.get("in") or {}).get("number")})
    return res


@router.post("/interco/transactions/{interco_id}/tax-invoice/replace")
async def replace_interco_tax(interco_id: str, payload: IntercoReasonIn,
                              request: Request) -> Dict[str, Any]:
    """Faktur Pajak PENGGANTI memakai DPP bersih terbaru (mis. sesudah retur)."""
    actor = await require_permission(request, "interco", "tax")
    await guard_party(request, await ics.get_one(interco_id), label="Transaksi antar-PT")
    doc = await ics.get_one(interco_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Transaksi antar-PT tidak ditemukan.")
    try:
        res = await ictax.replace(doc["pair_id"], payload.reason, actor.get("name", ""))
    except ictax.IntercoTaxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "interco_tax_invoice_replaced", "tax_invoice",
                (res.get("out") or {}).get("id", ""),
                {"pair_id": doc["pair_id"], "reason": payload.reason})
    return res


@router.post("/interco/transactions/{interco_id}/tax-invoice/cancel")
async def cancel_interco_tax(interco_id: str, payload: IntercoReasonIn,
                             request: Request) -> Dict[str, Any]:
    """Batalkan pasangan faktur pajak internal (wajib alasan)."""
    actor = await require_permission(request, "interco", "tax")
    await guard_party(request, await ics.get_one(interco_id), label="Transaksi antar-PT")
    doc = await ics.get_one(interco_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Transaksi antar-PT tidak ditemukan.")
    try:
        res = await ictax.cancel(doc["pair_id"], payload.reason, actor.get("name", ""))
    except ictax.IntercoTaxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "interco_tax_invoice_cancelled", "tax_invoice",
                doc["pair_id"], {"reason": payload.reason})
    return res


# ═════════════════════════════════════════════════════════════════════════════
#  FASE G-6b — RETUR ANTAR-PT
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/interco/returns/meta")
async def interco_return_meta(request: Request) -> Dict[str, Any]:
    await require_permission(request, "interco", "view")
    return await icret.meta()


@router.get("/interco/returns")
async def list_interco_returns(request: Request, entity_id: str = "",
                               status: str = "", origin_pair_id: str = "",
                               limit: int = 200) -> List[Dict[str, Any]]:
    await require_permission(request, "interco", "view")
    scope = await _scope(request, entity_id)
    from pagination import clamp_limit   # FIX-5 (B3b LST-03)
    return await icret.list_returns(scope, entity_id=entity_id, status=status,
                                    origin_pair_id=origin_pair_id, limit=clamp_limit(limit, 200, 500))


@router.get("/interco/transactions/{interco_id}/returnable")
async def returnable_lines(interco_id: str, request: Request) -> Dict[str, Any]:
    """Baris yang masih bisa diretur + alasan bila belum boleh (dipakai wizard)."""
    await require_permission(request, "interco", "view")
    await guard_party(request, await ics.get_one(interco_id), label="Transaksi antar-PT")   # PK-09 E36
    try:
        return await icret.returnable(interco_id)
    except icret.IntercoReturnError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/interco/returns")
async def create_interco_return(payload: IntercoReturnCreate,
                                request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "interco", "return")
    await guard_party(request, await ics.get_one(payload.interco_id), label="Transaksi antar-PT")   # PK-09 E37
    try:
        res = await icret.create(payload.model_dump(), actor.get("name", ""))
    except icret.IntercoReturnError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "interco_return_created", "interco_return",
                (res.get("returner") or {}).get("id", ""),
                {"origin": payload.interco_id, "reason": payload.reason,
                 "total": (res.get("returner") or {}).get("grand_total")})
    return res


@router.get("/interco/returns/{ret_id}")
async def get_interco_return(ret_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "interco", "view")
    return await guard_party(request, await icret.get_one(ret_id), label="Dokumen retur")   # PK-09 E38


@router.post("/interco/returns/{ret_id}/approve")
async def approve_interco_return(ret_id: str, payload: IntercoActionIn,
                                 request: Request) -> Dict[str, Any]:
    """Setujui retur → jurnal pembalik terbit di DUA buku (pembuat ≠ penyetuju)."""
    # PK-47 (MB-02) — izin dulu (tanpa izin antar-PT tidak boleh tahu dokumen ada), lalu 404 bila tidak ada.
    actor = await require_any_permission(request, [("interco", "approve"), ("interco", "receive")])
    try:
        _pair = await icret.get_one(ret_id)
    except icret.IntercoReturnError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not _pair:
        raise HTTPException(status_code=404, detail="Dokumen retur tidak ditemukan.")
    if not (_pair.get("returner") or {}).get("mandatory_accept"):
        # LN-140 — retur internal WAJIB TERIMA (R-10) boleh diterima gudang penerima; selain itu butuh `approve`.
        actor = await require_permission(request, "interco", "approve")
    await guard_party(request, await icret.get_one(ret_id), label="Retur antar-PT")
    from services.twin_journal import TwinJournalError
    try:
        res = await icret.approve(ret_id, actor)
    except TwinJournalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except icret.IntercoReturnError as exc:
        code = 409 if "jurnal yang gagal terbit" in str(exc) else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "interco_return_approved", "interco_return",
                ret_id, {"note": payload.note,
                         "total": (res.get("returner") or {}).get("grand_total")})
    return res


@router.post("/interco/returns/{ret_id}/warehouse-task")
async def return_warehouse_task(ret_id: str, payload: IntercoActionIn,
                                request: Request) -> Dict[str, Any]:
    """Terbitkan tugas gudang ARAH BALIK supaya barangnya benar-benar kembali."""
    actor = await require_permission(request, "interco", "ship")
    await guard_party(request, await icret.get_one(ret_id), label="Retur antar-PT")
    try:
        res = await icret.create_warehouse_task(ret_id, actor.get("name", ""))
    except icret.IntercoReturnError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "interco_return_task_created",
                "warehouse_transfer", res.get("id", ""),
                {"code": res.get("code"), "return_id": ret_id, "note": payload.note})
    return res


@router.post("/interco/returns/{ret_id}/roll-decisions")
async def interco_return_roll_decisions(ret_id: str, payload: ReturnRollDecisionsIn,
                                        request: Request) -> Dict[str, Any]:
    """23 Okt — Terima/Tolak per roll sebelum retur antar-PT disetujui (izin `interco.decide_rolls`)."""
    actor = await require_permission(request, "interco", "decide_rolls")
    pair = await guard_party(request, await icret.get_one(ret_id), label="Retur antar-PT")
    head = pair.get("returner") or pair
    ctx = await entity_ctx(request)
    seller_side = ctx.active_entity_id == head.get("seller_entity_id")
    try:
        res = await icret.decide_rolls(ret_id, [d.dict() for d in payload.decisions], actor,
                                       can_reject=not (head.get("mandatory_accept") and seller_side))
    except icret.IntercoReturnError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "interco_return_roll_decisions", "interco_return", ret_id,
                {"rolls": [d.dict() for d in payload.decisions]})
    return res


@router.post("/interco/returns/{ret_id}/attachments")
async def interco_return_attachment(ret_id: str, request: Request, file: UploadFile = File(...),
                                    roll_id: str = Form("")) -> Dict[str, Any]:
    """23 Okt — foto bukti retur antar-PT (per roll bila `roll_id` diisi); tersimpan di KEDUA dokumen kembar."""
    actor = await require_permission(request, "interco", "return")
    pair = await guard_party(request, await icret.get_one(ret_id), label="Retur antar-PT")
    head = pair.get("returner") or pair
    if head.get("status") == "cancelled":
        raise HTTPException(status_code=400, detail="Retur sudah dibatalkan — tidak bisa tambah lampiran.")
    from services import return_attachment_service as ras
    try:
        att = await ras.store("interco_returns", head, file, roll_id, actor.get("name", ""),
                              match={"return_pair_id": head.get("return_pair_id")})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "interco_return_attachment_added", "interco_return", ret_id,
                {"filename": file.filename, "roll_id": roll_id})
    return att


@router.get("/interco/returns/{ret_id}/attachments/{att_id}/download")
async def interco_return_attachment_download(ret_id: str, att_id: str, request: Request):
    await require_permission(request, "interco", "view")
    pair = await guard_party(request, await icret.get_one(ret_id), label="Retur antar-PT")
    from services import return_attachment_service as ras
    try:
        return await ras.download(pair.get("returner") or pair, att_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/interco/returns/{ret_id}/cancel")
async def cancel_interco_return(ret_id: str, payload: IntercoReasonIn,
                                request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "interco", "return")
    doc = await guard_party(request, await icret.get_one(ret_id), label="Retur antar-PT")
    ctx = await entity_ctx(request)
    head = doc.get("returner") or doc
    if head.get("mandatory_accept") and ctx.active_entity_id == head.get("seller_entity_id"):
        raise HTTPException(status_code=400, detail="PT pemasok wajib menerima retur internal ini (R-10) — "
                                                    "pembatalan hanya oleh PT yang mengembalikan.")
    try:
        res = await icret.cancel(ret_id, actor.get("name", ""), payload.reason)
    except icret.IntercoReturnError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await audit(actor.get("name", ""), "interco_return_cancelled", "interco_return",
                ret_id, {"reason": payload.reason})
    return res


# ═════════════════════════════════════════════════════════════════════════════
#  FASE G-6b — PENGINGAT SETTLEMENT (mengingatkan, bukan memaksa)
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/interco/reminders")
async def interco_reminders(request: Request) -> Dict[str, Any]:
    """Pasangan PT yang saldonya menganggur melewati batas config."""
    await require_permission(request, "interco_finance", "view")  # FASE E-0 (L20)
    scope = await _scope(request)
    return await icrem.idle_pairs(scope)


@router.post("/interco/accounts/{payer_entity_id}/{payee_entity_id}/remind")
async def remind_settlement(payer_entity_id: str, payee_entity_id: str,
                            payload: IntercoActionIn, request: Request) -> Dict[str, Any]:
    """Kirim pengingat settlement untuk satu pasangan PT (tombol di layar)."""
    actor = await require_permission(request, "interco", "settle")
    await _assert_one_side(request, payer_entity_id, payee_entity_id)   # PK-09 E40
    try:
        res = await icrem.remind_pair(payer_entity_id, payee_entity_id,
                                      actor.get("name", ""))
    except ics.IntercoError as exc:
        raise _fail(exc) from exc
    await audit(actor.get("name", ""), "interco_settlement_reminded",
                "interco_account", ics.ica_ap_id(payer_entity_id, payee_entity_id),
                {"outstanding": res.get("outstanding"),
                 "idle_days": res.get("idle_days"), "note": payload.note})
    return res


# ═════════════════════════════════════════════════════════════════════════════
#  FASE G-6b — RAPOR MARGIN GRUP (realized vs unrealized)
# ═════════════════════════════════════════════════════════════════════════════
@router.get("/interco/margin-report")
async def margin_report(request: Request, entity_id: str = "",
                        as_of: str = "") -> Dict[str, Any]:
    """Margin antar-PT per pasangan PT + berapa yang sudah nyata bagi grup."""
    await require_permission(request, "interco_finance", "view")  # FASE E-0 (L20)
    scope = await _scope(request, entity_id)
    return await icmargin.margin_report(scope, entity_id=entity_id, as_of=as_of)


@router.get("/interco/margin-by-product")
async def margin_by_product(request: Request, entity_id: str = "",
                            pair: str = "", as_of: str = "") -> Dict[str, Any]:
    """FASE P3 — rapor margin antar-PT PER BARANG (urut margin terbesar) +
    penyaring pasangan PT (`pair` = 'seller_entity_id|buyer_entity_id')."""
    await require_permission(request, "interco", "view")
    scope = await _scope(request, entity_id)
    return await icmargin.margin_by_product(scope, entity_id=entity_id, pair=pair, as_of=as_of)

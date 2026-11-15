"""KM-T4 (K-26) — router **TAGIHAN INSENTIF ANTAR-PT** (`/api/interco/charges`).

  GET   /api/interco/charges                 interco.view    tagihan yang menyangkut PT dalam cakupan (penagih ATAU
                                                             tertagih), berhalaman, saringan status & cari nomor
  GET   /api/interco/charges/{id}            interco.view    satu tagihan (pihak = salah satu PT penugasan)
  POST  /api/interco/charges/{id}/settle     interco.settle  catat pelunasan {amount, date, account_id_from,
                                                             account_id_to} — pelaku wajib bertugas di PT tertagih

Tagihan lahir dari posting gaji PT penagih (bukan dari layar). Izin modul `interco` yang sudah dipakai pinjaman antar-PT
(`routers/interco_loans.py`). Awalan `/api/interco/` ada di `IDEMPOTENT_PREFIXES` (N4: kirim ulang = satu pelunasan).
Logika di `services/interco_charge_service.py`.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from dependencies import audit, require_permission
from entity_scope import entity_ctx, guard_party, resolve_scope_ids
from services import interco_charge_service as icc

router = APIRouter(prefix="/api")

MODUL = "Antar-PT"
PESAN_LIHAT = f"Anda belum punya akses untuk melihat tagihan antar-PT. Minta Admin menambahkan akses '{MODUL}'."
PESAN_LUNAS = f"Anda belum punya akses untuk mencatat pelunasan antar-PT. Minta Admin menambahkan akses '{MODUL}'."


class ChargeSettleInput(BaseModel):
    amount: float = Field(..., gt=0, le=1_000_000_000_000)
    date: Optional[str] = ""
    account_id_from: Optional[str] = ""
    account_id_to: Optional[str] = ""
    note: Optional[str] = Field("", max_length=300)


def _http(exc: icc.ChargeError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=str(exc))


@router.get("/interco/charges")
async def list_interco_charges(request: Request, status: str = Query(""), q: str = Query("", max_length=60),
                               page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
                               entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    await require_permission(request, "interco", "view", detail=PESAN_LIHAT)
    ids = resolve_scope_ids(await entity_ctx(request), entity_id)
    try:
        return await icc.list_charges(ids, status=status.strip(), q=q, page=page, page_size=page_size)
    except icc.ChargeError as exc:
        raise _http(exc) from exc


@router.get("/interco/charges/{charge_id}")
async def get_interco_charge(charge_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "interco", "view", detail=PESAN_LIHAT)
    doc = await guard_party(request, await icc.get_charge(charge_id), label="Tagihan antar-PT")
    return icc.out_doc(doc)


@router.post("/interco/charges/{charge_id}/settle")
async def settle_interco_charge(charge_id: str, payload: ChargeSettleInput, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "interco", "settle", detail=PESAN_LUNAS)
    await guard_party(request, await icc.get_charge(charge_id), label="Tagihan antar-PT")
    ctx = await entity_ctx(request)
    try:
        out = await icc.settle(charge_id, payload.model_dump(), actor, allowed_entity_ids=list(ctx.allowed_entity_ids))
    except icc.ChargeError as exc:
        raise _http(exc) from exc
    await audit(actor.get("name", ""), "interco_charge_settled", "interco_charge", charge_id,
                {"number": out.get("number"), "amount": payload.amount, "outstanding": out.get("outstanding"),
                 "status": out.get("status")}, scope_entity_id=out.get("to_entity_id") or "")
    return out

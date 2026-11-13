"""PK-05 — Niat bayar hutang (faktur pemasok / kontrabon): status, rekening sumber, lanjutkan, batalkan.

Pembayarannya sendiri tetap lewat `POST /api/vendor-bills/{id}/pay` dan `POST /api/contra-bons/{id}/pay`; keduanya
memanggil `services/ap_payment_service.pay_payable`. Endpoint ber-id niat menjaga PT lewat `entity_id` niat (di luar
penugasan → 404).
"""
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from db import db
from dependencies import audit, require_permission
from entity_scope import guard_doc
from services import ap_payment_service as aps

router = APIRouter(prefix="/api")

_RES = {"vendor_bill": "vendor_bill", "contra_bon": "contra_bon"}
_COLL = {"vendor_bill": "vendor_bills", "contra_bon": "contra_bons"}


class CancelIn(BaseModel):
    reason: str = ""


def _kind(kind: str) -> str:
    if kind not in _RES:
        raise HTTPException(status_code=400, detail="Jenis dokumen harus vendor_bill atau contra_bon.")
    return kind


async def _guard_target(request: Request, kind: str, target_id: str) -> Dict[str, Any]:
    doc = await db[_COLL[kind]].find_one({"id": target_id}, {"_id": 0})
    await guard_doc(request, _COLL[kind], doc, not_found="Dokumen tidak ditemukan")
    return doc


async def _guard_intent(request: Request, intent_id: str) -> Dict[str, Any]:
    intent = await db[aps.COLL].find_one({"id": intent_id}, {"_id": 0})
    await guard_doc(request, aps.COLL, intent, not_found="Pembayaran tidak ditemukan")
    return intent


def _http(exc: aps.ApPaymentError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail())


@router.get("/ap-payments/pending")
async def pending_payment(kind: str, target_id: str, request: Request) -> Any:
    await require_permission(request, _RES[_kind(kind)], "view")
    await _guard_target(request, kind, target_id)
    return await aps.pending_for(kind, target_id)


@router.get("/ap-payments/accounts")
async def payable_accounts(kind: str, target_id: str, request: Request) -> Any:
    await require_permission(request, _RES[_kind(kind)], "pay")
    await _guard_target(request, kind, target_id)
    return await aps.payable_accounts(kind, target_id)


@router.post("/ap-payments/{intent_id}/resume")
async def resume_payment(intent_id: str, request: Request) -> Dict[str, Any]:
    intent = await _guard_intent(request, intent_id)
    actor = await require_permission(request, _RES[intent["kind"]], "pay")
    try:
        res = await aps.resume(intent_id, actor)
    except aps.ApPaymentError as exc:
        raise _http(exc) from exc
    await audit(actor["name"], "ap_payment_resumed", intent["kind"], intent["target_id"], {"intent": intent_id})
    return res


@router.post("/ap-payments/{intent_id}/cancel")
async def cancel_payment(intent_id: str, payload: CancelIn, request: Request) -> Dict[str, Any]:
    intent = await _guard_intent(request, intent_id)
    actor = await require_permission(request, _RES[intent["kind"]], "pay")
    try:
        res = await aps.cancel(intent_id, actor, payload.reason)
    except aps.ApPaymentError as exc:
        raise _http(exc) from exc
    await audit(actor["name"], "ap_payment_cancelled", intent["kind"], intent["target_id"],
                {"intent": intent_id}, reason=payload.reason)
    return res

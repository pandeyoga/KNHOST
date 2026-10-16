"""routers/esign.py — Tanda tangan elektronik: request OTP, verifikasi+sign,
daftar tanda tangan, dan verifikasi PUBLIK (tanpa login).
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from dependencies import require_permission, audit
from services import esign_service as es

router = APIRouter(prefix="/api/esign", tags=["esign"])


class RequestBody(BaseModel):
    doc_type: str
    source_id: str
    entity_id: Optional[str] = None
    signer_name: str
    signer_role: Optional[str] = ""
    signer_contact: Optional[str] = ""
    channel: Optional[str] = None


class VerifyBody(BaseModel):
    request_id: str
    otp: str
    signature_b64: str


async def _guard_source(request: Request, doc_type: str, source_id: str) -> dict:
    """IX-05 — dokumen sumber e-sign wajib dalam scope entitas pemanggil sebelum apa pun dibaca/ditulis."""
    from db import db
    from entity_scope import guard_doc
    reg = es.DOC_REGISTRY.get(doc_type) or {}
    coll = reg.get("collection")
    if not coll:
        raise HTTPException(status_code=404, detail="Jenis dokumen tidak dikenal")
    src = await db[coll].find_one({"id": source_id}, {"_id": 0})
    await guard_doc(request, coll, src, strict=False, not_found="Dokumen sumber tidak ditemukan")
    return src


@router.post("/request")
async def request_otp(body: RequestBody, request: Request):
    user = await require_permission(request, "esign", "sign")
    actor = user.get("email") or user.get("name") or user.get("id")
    src = await _guard_source(request, body.doc_type, body.source_id)
    if body.entity_id and src.get("entity_id") and body.entity_id != src["entity_id"]:
        raise HTTPException(status_code=400, detail="Entitas tidak sesuai dengan pemilik dokumen")
    try:
        return await es.create_request(
            body.doc_type, body.source_id, src.get("entity_id") or body.entity_id, body.signer_name,
            body.signer_role, body.signer_contact, actor, body.channel)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/verify")
async def verify(body: VerifyBody, request: Request):
    user = await require_permission(request, "esign", "sign")
    ip = request.client.host if request.client else ""
    from db import db
    req_doc = await db.esign_requests.find_one({"id": body.request_id}, {"_id": 0, "doc_type": 1, "source_id": 1})
    if not req_doc:
        raise HTTPException(status_code=404, detail="Permintaan tanda tangan tidak ditemukan")
    await _guard_source(request, req_doc["doc_type"], req_doc["source_id"])
    try:
        res = await es.verify_and_sign(body.request_id, body.otp, body.signature_b64, ip)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await audit(user.get("email", "-"), "esign.sign", "document_signature",
                res.get("verification_code", ""), {"request_id": body.request_id, **res}, "")
    return res


@router.get("/signatures/{doc_type}/{source_id}")
async def signatures(doc_type: str, source_id: str, request: Request):
    await require_permission(request, "esign", "view")
    src = await _guard_source(request, doc_type, source_id)
    return {"signatures": await es.list_signatures(doc_type, source_id, src.get("entity_id"))}


@router.get("/verify/{code}")
async def public_verify(code: str):
    """PUBLIK — tanpa autentikasi (dipakai halaman verifikasi + QR)."""
    return await es.public_verify(code)

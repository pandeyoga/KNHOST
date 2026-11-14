"""CR-T1 — profil kredit per pelanggan per PT dan pengajuan perubahannya (`docs/blueprint/unit/CR-T1.md`).

  GET  /api/customers/{id}/credit-profile?entity_id=        credit_profile.view + can_view_credit
  POST /api/customers/{id}/credit-profile-requests          credit_profile.update + can_access_customer
  GET  /api/credit-profile-requests?status=&customer_id=    credit_profile.view (PT aktif; cakupan pelanggan pengguna)
  POST /api/credit-profile-requests/{id}/decision           credit_profile.approve (+ kontrol dua orang KF-T6)
  POST /api/credit-profile-requests/{id}/cancel             pengaju sendiri, atau credit_profile.approve

PT selalu lewat `resolve_requested_entity` (N1); pengajuan ber-id diadu dengan `guard_doc` (N2). Logika di
`services/credit_profile_service.py`.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from core_utils import safe_doc
from db import db
from dependencies import has_permission, require_any_permission, require_permission
from entity_scope import entity_ctx, guard_doc, resolve_list_scope, resolve_requested_entity
from schemas_crm import CreditProfileCancel, CreditProfileDecision, CreditProfileRequestCreate
from services import credit_profile_service as cps
from services.customer_service import can_access_customer, can_view_credit
from services.data_scope import own_scoped

router = APIRouter(prefix="/api")

MODUL = "Uang Masuk, Piutang & Faktur Pajak"
PESAN_LIHAT = f"Anda belum punya akses untuk melihat profil kredit pelanggan. Minta Admin menambahkan akses '{MODUL}'."
PESAN_AJU = f"Anda belum punya akses untuk mengajukan perubahan kredit. Minta Admin menambahkan akses '{MODUL}'."
PESAN_PUTUS = f"Anda belum punya akses untuk memutus pengajuan perubahan kredit. Minta Admin menambahkan akses '{MODUL}'."
PESAN_BATAL = (f"Anda belum punya akses untuk membatalkan pengajuan perubahan kredit. Minta Admin menambahkan akses "
               f"'{MODUL}'.")
TIDAK_ADA = "Pelanggan tidak ditemukan."
REQ_TIDAK_ADA = "Pengajuan perubahan kredit tidak ditemukan."


async def _pelanggan(customer_id: str) -> Dict[str, Any]:
    c = safe_doc(await db.customers.find_one({"id": customer_id}, {"_id": 0}))
    if not c:
        raise HTTPException(status_code=404, detail=TIDAK_ADA)
    return c


@router.get("/customers/{customer_id}/credit-profile")
async def get_credit_profile(customer_id: str, request: Request, entity_id: Optional[str] = None) -> Dict[str, Any]:
    """`{profile, effective, pending_request, history}` untuk (pelanggan, PT); `history` = 20 pengajuan terakhir yang sudah
    diputus. Tambahan untuk layar: nama PT & pilihan PT pengguna (tanpa id teknis tampil), daftar termin aktif PT, dan
    aturan dua orang PT itu (tombol "Ajukan & setujui")."""
    actor = await require_permission(request, "credit_profile", "view", detail=PESAN_LIHAT)
    customer = await _pelanggan(customer_id)
    if not can_view_credit(actor, customer):
        raise HTTPException(status_code=404, detail=TIDAK_ADA)
    ctx = await entity_ctx(request)
    eid = resolve_requested_entity(ctx, entity_id)
    profile = await db[cps.COLL].find_one({"customer_id": customer_id, "entity_id": eid}, {"_id": 0})
    pending = await cps.pengajuan_terbuka(customer_id, eid)
    if pending:
        pending = {**pending, "label_changes": cps.label_changes(pending.get("changes")),
                   "blocked_reason": await cps.periksa_putus(pending, actor)}
        pending.pop("credit_snapshot", None)
    return {
        "customer": {"id": customer["id"], "name": customer.get("name", ""), "entity_id": customer.get("entity_id")},
        "entity": (await cps.ringkas_pt([eid]) or [{"id": eid}])[0],
        "entity_options": await cps.ringkas_pt(ctx.allowed_entity_ids),
        "profile": safe_doc(profile),
        "effective": await cps.effective(customer_id, eid, customer=customer),
        "pending_request": safe_doc(pending),
        "history": await cps.riwayat(customer_id, eid),
        "term_options": await cps.term_options(eid),
        "dual_control": await cps.aturan_dua_orang(eid),
        "labels": cps.LABEL,
    }


@router.post("/customers/{customer_id}/credit-profile-requests")
async def create_credit_profile_request(customer_id: str, payload: CreditProfileRequestCreate,
                                        request: Request) -> Dict[str, Any]:
    """Ajukan perubahan profil kredit (pelanggan, PT). Satu pengajuan terbuka per (pelanggan, PT) → 409."""
    actor = await require_permission(request, "credit_profile", "update", detail=PESAN_AJU)
    customer = await _pelanggan(customer_id)
    if not await can_access_customer(actor, customer):
        raise HTTPException(status_code=403, detail="Pelanggan ini di luar cakupan Anda.")
    eid = resolve_requested_entity(await entity_ctx(request), payload.entity_id)
    changes = payload.changes if isinstance(payload.changes, dict) else {}
    doc = await cps.submit(customer, eid, changes, payload.reason, payload.attachment_url, actor)
    return {**doc, "label_changes": cps.label_changes(doc.get("changes"))}


@router.get("/credit-profile-requests")
async def list_credit_profile_requests(request: Request, status: str = Query(""), customer_id: str = Query(""),
                                       entity_id: Optional[str] = Query(None), page: int = Query(1, ge=1),
                                       page_size: int = Query(25, ge=1, le=100)) -> Dict[str, Any]:
    """Pengajuan per PT (aktif, atau `entity_id` yang ditugaskan), terbaru dulu, berhalaman. Pengguna bercakupan "milik
    sendiri/tim" (bawaan Sales) hanya melihat pengajuan pelanggan dalam cakupannya."""
    actor = await require_permission(request, "credit_profile", "view", detail=PESAN_LIHAT)
    ctx = await entity_ctx(request)
    q: Dict[str, Any] = resolve_list_scope(cps.COLL_REQ, {}, ctx, entity_id)
    if status:
        q["status"] = status
    if customer_id:
        q["customer_id"] = customer_id
    if own_scoped(actor):
        from services.customer_service import scope_query
        ids = await db.customers.distinct("id", scope_query(actor, {}))
        q["customer_id"] = {"$in": [i for i in ids if not customer_id or i == customer_id]}
    total = await db[cps.COLL_REQ].count_documents(q)
    rows = await db[cps.COLL_REQ].find(q, {"_id": 0, "credit_snapshot": 0}).sort("created_at", -1) \
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    names = {e["id"]: e for e in await cps.ringkas_pt({r.get("entity_id") for r in rows})}
    items = []
    for r in rows:
        r["label_changes"] = cps.label_changes(r.get("changes"))
        r["entity"] = names.get(r.get("entity_id")) or {"id": r.get("entity_id")}
        if r.get("status") == cps.ST_DIAJUKAN:
            r["blocked_reason"] = await cps.periksa_putus(r, actor)
            r["can_cancel"] = r.get("requested_by_id") == actor.get("id")
        items.append(r)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def _pengajuan(request: Request, request_id: str) -> Dict[str, Any]:
    req = await db[cps.COLL_REQ].find_one({"id": request_id}, {"_id": 0})
    await guard_doc(request, cps.COLL_REQ, req, strict=False, not_found=REQ_TIDAK_ADA)
    return req


@router.post("/credit-profile-requests/{request_id}/decision")
async def decide_credit_profile_request(request_id: str, payload: CreditProfileDecision,
                                        request: Request) -> Dict[str, Any]:
    """Setujui (profil ditulis bersyarat versi; nilai `from` harus masih sama) atau tolak (catatan wajib)."""
    actor = await require_permission(request, "credit_profile", "approve", detail=PESAN_PUTUS)
    req = await _pengajuan(request, request_id)
    res = await cps.decide(request_id, str(payload.decision or ""), str(payload.note or ""), actor, request=req)
    res["request"] = {**res["request"], "label_changes": cps.label_changes(res["request"].get("changes"))}
    return res


@router.post("/credit-profile-requests/{request_id}/cancel")
async def cancel_credit_profile_request(request_id: str, payload: CreditProfileCancel,
                                        request: Request) -> Dict[str, Any]:
    """Batalkan pengajuan `diajukan` — pengajunya sendiri, atau pemegang `credit_profile.approve`; alasan wajib."""
    actor = await require_any_permission(request, [("credit_profile", "update"), ("credit_profile", "approve")],
                                         detail=PESAN_BATAL)
    req = await _pengajuan(request, request_id)
    return await cps.cancel(req, str(payload.reason or ""), actor,
                            boleh_semua=await has_permission(actor, "credit_profile", "approve"))

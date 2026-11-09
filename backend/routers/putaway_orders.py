"""FASE R2 — Router Putaway Order (PA) + BTG. Prefix /api.

PREP-C (K-GDG-10, 8 Nov 2026) — draf otomatis (`/putaway-orders/auto-draft`, `PATCH …/draft`, `…/publish`,
`…/cancel-draft`), tiba bertahap per trip (`…/arrival-trips`) + penutupan sisa (`…/close`), detail (`GET …/{id}`).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from dependencies import require_permission, audit
from entity_scope import entity_ctx, resolve_scope_ids
from services import warehouse_scope_service as whscope
from services import putaway_order_service as pa
from services import putaway_draft_service as pad
from services import putaway_arrival_service as arr

router = APIRouter(prefix="/api")


class PACreatePayload(BaseModel):
    from_warehouse_id: str
    to_warehouse_id: str
    roll_ids: List[str]


class PAConfirmPayload(BaseModel):
    scanned_epcs: Optional[List[str]] = None
    manual_all: bool = False  # WM-03 — override tanpa scan: wajib alasan + izin wms.approve
    reason: str = ""


class PAResolvePayload(BaseModel):
    roll_ids: List[str]
    action: str  # accept | return_transit
    reason: str = ""


async def _scope(request: Request) -> List[str]:
    ctx = await entity_ctx(request)
    return resolve_scope_ids(ctx)


# FIX-1 (B2a STM-IN-02, P0) — cakupan lokasi di SETIAP aksi tulis PA, bukan hanya daftar/pembuatan. Dulu petugas
# Jakarta mendapat 403 saat membuka PA Rancamalang tetapi `publish`/`dispatch`/`arrival-trips` lolos 200.
# Sisi aksi: gudang ASAL untuk terbit/kirim/ubah/batal draf; gudang TUJUAN untuk tiba/tutup/konfirmasi/pengecualian.
_PA_SIDE = {"from": ("from_warehouse_id", "mengerjakan Putaway Order dari gudang ini"),
            "to": ("to_warehouse_id", "menerima Putaway Order di gudang ini")}


async def _assert_pa_side(request: Request, actor: Dict[str, Any], order_id: str, side: str) -> None:
    from services import location_scope
    if await location_scope.warehouse_ids_for(actor) is None:
        return
    order = await pa._get(order_id, await _scope(request))
    field, action = _PA_SIDE[side]
    await location_scope.assert_doc_side(actor, order, field, action)


class PAVerifyLabelsPayload(BaseModel):
    warehouse_id: str
    codes: List[str]


@router.post("/putaway-orders/verify-labels")
async def post_verify_labels(payload: PAVerifyLabelsPayload, request: Request) -> Dict[str, Any]:
    """UAT 24 Okt (P9.3b) — pindai label QR roll di transit (tanpa RFID) → siap Putaway Order."""
    actor = await require_permission(request, "wms", "update")
    from services import location_scope
    await location_scope.assert_warehouse(actor, payload.warehouse_id, "memindai label roll di gudang ini")
    res = await pa.verify_labels(payload.warehouse_id, payload.codes, await _scope(request), actor["name"])
    await audit(actor["name"], "putaway_labels_verified", "warehouse", payload.warehouse_id,
                {"verified": len(res["verified"]), "skipped": len(res["skipped"]), "not_found": len(res["not_found"])})
    return res


@router.get("/putaway-orders/suggest")
async def get_suggest(request: Request, from_warehouse_id: str) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "view")
    from services import location_scope   # FIX-1 — daftar roll siap PA gedung lain tidak dibuka untuk petugas berpagar
    await location_scope.assert_warehouse(actor, from_warehouse_id, "melihat roll siap putaway di gudang ini")
    return await pa.suggest(from_warehouse_id, await _scope(request))


@router.get("/putaway-orders")
async def get_orders(request: Request, warehouse_id: Optional[str] = None,
                     status: Optional[str] = None, limit: int = 100,
                     entity_id: Optional[str] = None) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    ctx = await entity_ctx(request)
    # FIX-1 (K-B1-02, B3a SCP-2/SCP-3) — PA per GEDUNG dalam lokasi kerja (pagar keras P9.5 + saringan tampilan) di
    # DALAM kueri (dulu disaring sesudah `limit`), lintas PT yang ditugaskan; `entity_id` = saringan PT eksplisit.
    from services import location_scope
    from services.work_labels import label_rows
    if entity_id and entity_id != "all":
        if entity_id not in ctx.allowed_entity_ids:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Tidak berwenang atas entitas ini")
        owners = [entity_id]
    else:
        owners = list(ctx.allowed_entity_ids)
    view = await location_scope.view_for(ctx)
    extra = location_scope.narrow_view("putaway_orders", {}, view)
    rows = await pa.list_orders(owners, warehouse_id, status, max(1, min(int(limit or 100), 500)), extra=extra)
    ids = ctx.warehouse_ids
    rows = [o for o in rows if location_scope.doc_in_scope("putaway_orders", o, ids)]
    return {"orders": await label_rows(rows, entity_field="owner_entity_id", kinds=False)}


@router.post("/putaway-orders")
async def post_order(payload: PACreatePayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "update")
    ctx = await entity_ctx(request)
    # E4.1 — gudang asal & tujuan harus boleh dipakai badan usaha aktif.
    await whscope.assert_many_usable([payload.from_warehouse_id, payload.to_warehouse_id],
                                     ctx.active_entity_id, action="memindahkan roll ke rak di sini")
    # UAT 24 Okt (P9.5) — petugas gudang hanya membuat PA di lokasi tugasnya.
    from services import location_scope
    for _wid in (payload.from_warehouse_id, payload.to_warehouse_id):
        await location_scope.assert_warehouse(actor, _wid, "membuat Putaway Order di gudang ini")
    order = await pa.create_order(payload.from_warehouse_id, payload.to_warehouse_id,
                                  payload.roll_ids, resolve_scope_ids(ctx), actor["name"])
    await audit(actor["name"], "putaway_order_created", "putaway_order", order["id"],
                {"pa_number": order["pa_number"], "items": order["item_count"]})
    return order


@router.post("/putaway-orders/{order_id}/dispatch")
async def post_dispatch(order_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "update")
    await _assert_pa_side(request, actor, order_id, "from")
    order = await pa.dispatch(order_id, await _scope(request))
    await audit(actor["name"], "putaway_order_dispatched", "putaway_order", order_id, {})
    return order


@router.post("/putaway-orders/{order_id}/confirm-arrival")
async def post_confirm(order_id: str, payload: PAConfirmPayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "approve" if payload.manual_all else "update")
    await _assert_pa_side(request, actor, order_id, "to")
    order = await pa.confirm_arrival(order_id, payload.scanned_epcs,
                                     await _scope(request), actor["name"],
                                     manual_all=payload.manual_all, reason=payload.reason)
    await audit(actor["name"], "putaway_order_confirmed", "putaway_order", order_id,
                {"btg": order.get("btg_number"), "exceptions": order.get("exception_count", 0),
                 "manual_all": payload.manual_all, "reason": payload.reason})
    return order


@router.post("/putaway-orders/{order_id}/resolve-exception")
async def post_resolve(order_id: str, payload: PAResolvePayload, request: Request) -> Dict[str, Any]:
    # PREP-C (celah 27 Okt) — `accept` = menyatakan roll tiba TANPA bukti scan, setara konfirmasi manual (`manual_all`
    # butuh wms.approve). Dulu cukup wms.update sehingga syarat approve bisa dilewati lewat exception.
    actor = await require_permission(request, "wms", "approve" if payload.action == "accept" else "update")
    await _assert_pa_side(request, actor, order_id, "to")
    order = await pa.resolve_exception(order_id, payload.roll_ids, payload.action,
                                       await _scope(request), actor["name"], payload.reason)
    await audit(actor["name"], "putaway_exception_resolved", "putaway_order", order_id,
                {"action": payload.action, "rolls": len(payload.roll_ids)})
    return order


# ─── PREP-C — draf otomatis (K-GDG-10) ───────────────────────────────────────
class PAAutoDraftPayload(BaseModel):
    from_warehouse_id: str


class PADraftPatch(BaseModel):
    to_warehouse_id: Optional[str] = None
    purpose: Optional[str] = None             # storage | inspection (kosong = turunan dari gedung tujuan)
    remove_roll_ids: List[str] = Field(default_factory=list, max_length=2000)
    add_roll_ids: List[str] = Field(default_factory=list, max_length=2000)


class PAPublishPayload(BaseModel):
    split_unready: bool = False               # terbitkan yang siap, sisanya tetap draf (draf baru)


class PAReasonPayload(BaseModel):
    reason: str = ""


class PATripPayload(BaseModel):
    epcs: List[str] = Field(default_factory=list, max_length=2000)
    client_trip_id: str = ""                  # idempoten: kirim ulang trip yang sama tidak dicatat dua kali


class PAClosePayload(BaseModel):
    action: str                               # return_transit | exception
    reason: str = ""


@router.post("/putaway-orders/auto-draft")
async def post_auto_draft(payload: PAAutoDraftPayload, request: Request) -> Dict[str, Any]:
    """Siapkan draf PA untuk roll tersedia di gudang ini yang belum masuk PA mana pun (pengisi ulang / data lama)."""
    actor = await require_permission(request, "wms", "update")
    ctx = await entity_ctx(request)
    from services import location_scope
    await location_scope.assert_warehouse(actor, payload.from_warehouse_id, "menyiapkan draf putaway di gudang ini")
    await whscope.assert_usable(payload.from_warehouse_id, ctx.active_entity_id, action="menyiapkan draf putaway")
    res = await pad.prepare_for_warehouse(payload.from_warehouse_id, resolve_scope_ids(ctx), actor["name"])
    await audit(actor["name"], "putaway_drafts_prepared", "warehouse", payload.from_warehouse_id,
                {"drafts": [d["pa_number"] for d in res["drafts"]], "unrouted": len(res["unrouted"])})
    return res


@router.get("/putaway-orders/{order_id}")
async def get_order(order_id: str, request: Request) -> Dict[str, Any]:
    """Detail PA; draf membawa kesiapan per roll, penanda minta-inspeksi, dan pilihan gedung tujuan."""
    actor = await require_permission(request, "wms", "view")
    out = await pad.detail(order_id, await _scope(request))
    from services import location_scope
    if not location_scope.doc_in_scope("putaway_orders", out, await location_scope.warehouse_ids_for(actor)):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="PA di luar lokasi tugas Anda")
    return out


@router.patch("/putaway-orders/{order_id}/draft")
async def patch_draft(order_id: str, payload: PADraftPatch, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "update")
    await _assert_pa_side(request, actor, order_id, "from")
    if payload.to_warehouse_id:
        from services import location_scope
        await location_scope.assert_warehouse(actor, payload.to_warehouse_id, "menjadikan gudang ini tujuan putaway")
    out = await pad.update_draft(order_id, payload.model_dump(exclude_none=True), await _scope(request), actor["name"])
    await audit(actor["name"], "putaway_draft_updated", "putaway_order", order_id,
                {"to": out.get("to_warehouse_name"), "items": out.get("item_count"),
                 "removed": len(payload.remove_roll_ids), "added": len(payload.add_roll_ids)})
    return out


@router.post("/putaway-orders/{order_id}/publish")
async def post_publish(order_id: str, payload: PAPublishPayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "update")
    await _assert_pa_side(request, actor, order_id, "from")
    out = await pad.publish(order_id, await _scope(request), actor["name"], split_unready=payload.split_unready)
    await audit(actor["name"], "putaway_draft_published", "putaway_order", order_id,
                {"pa_number": out.get("pa_number"), "items": out.get("item_count"), "split": payload.split_unready})
    return out


@router.post("/putaway-orders/{order_id}/cancel-draft")
async def post_cancel_draft(order_id: str, payload: PAReasonPayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "update")
    await _assert_pa_side(request, actor, order_id, "from")
    out = await pad.cancel_draft(order_id, payload.reason, await _scope(request), actor["name"])
    await audit(actor["name"], "putaway_draft_cancelled", "putaway_order", order_id, {}, reason=payload.reason)
    return out


# ─── PREP-C — tiba bertahap per trip (K-GDG-10, K-RFID-10) ───────────────────
@router.post("/putaway-orders/{order_id}/arrival-trips")
async def post_arrival_trip(order_id: str, payload: PATripPayload, request: Request) -> Dict[str, Any]:
    """Satu trip tiba (handheld). Roll yang belum terbaca tetap menunggu; gate memanggil layanan yang sama."""
    actor = await require_permission(request, "wms", "update")
    await _assert_pa_side(request, actor, order_id, "to")
    out = await arr.confirm_arrival_trip(order_id, payload.epcs,
                                         {"type": "handheld", "client_trip_id": payload.client_trip_id},
                                         actor, await _scope(request))
    trip = out.get("trip") or {}
    await audit(actor["name"], "putaway_arrival_trip", "putaway_order", order_id,
                {"arrived": len(trip.get("arrived_roll_nos") or []), "status": out.get("status"),
                 "duplicate": out.get("duplicate_trip", False)})
    return out


@router.post("/putaway-orders/{order_id}/close")
async def post_close(order_id: str, payload: PAClosePayload, request: Request) -> Dict[str, Any]:
    """Tutup PA: roll yang masih menunggu → kembali ke transit, atau pengecualian (cek ulang handheld)."""
    actor = await require_permission(request, "wms", "update")
    await _assert_pa_side(request, actor, order_id, "to")
    out = await arr.close_remaining(order_id, payload.action, payload.reason, await _scope(request), actor)
    await audit(actor["name"], "putaway_order_closed", "putaway_order", order_id,
                {"action": payload.action, "status": out.get("status")}, reason=payload.reason)
    return out


@router.get("/wms/health-dashboard")
async def get_wms_health(request: Request) -> Dict[str, Any]:
    """DASHBOARD KESEHATAN GUDANG — insiden, opname, antrean putaway, device."""
    await require_permission(request, "wms", "view")
    from services.wms_health_service import health_dashboard
    return await health_dashboard(await _scope(request))

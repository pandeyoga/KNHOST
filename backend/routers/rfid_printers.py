"""PREP-F — endpoint printer label RFID (Chainway CP30EN) — disertakan oleh `routers/rfid.py` (prefix /api).

Perangkat (header `X-Device-Key`, connector PC gudang):
  GET  /rfid/printer-agent/config                                   profil printer + kebijakan
  POST /rfid/printer-agent/telemetry                                heartbeat connector + kesehatan printer
  POST /rfid/device-jobs/claim                                      klaim job (lease stabil; = GET …/pending)
  GET  /rfid/device-jobs/{job_id}/attempts/{attempt_id}             status attempt (pemulihan)
  POST /rfid/device-jobs/{job_id}/attempts/{attempt_id}/renew       perpanjang lease (attempt sama)
  POST /rfid/device-jobs/{job_id}/attempts/{attempt_id}/start       start barrier per item
  POST /rfid/device-jobs/{job_id}/attempts/{attempt_id}/results     hasil per label (idempoten)
Pengguna (sesi ERP):
  GET  /rfid/printers/queue · /rfid/printers/follow-up               antrean & tindak lanjut per gedung (wms:view)
  POST /rfid/print-jobs/{job_id}/items/{item_id}/resolve            keputusan hasil tidak pasti (wms:approve)
  POST /rfid/rolls/{roll_id}/replace-tag                            ganti tag: EPC baru (wms:approve)
  POST /rfid/rolls/{roll_id}/reprint-label                          cetak ulang TEKS (wms:print)
  GET  /rfid/rolls/{roll_id}/tag-history                            riwayat tag ↔ roll (wms:view)
  GET/PUT /rfid/printers/{device_id}/profile                        profil printer (lihat: wms:view; ubah: admin)
  POST /rfid/printers/label-preview                                 pratinjau tata letak + ZPL (wms:view)
  POST /rfid/printers/recover-effects                               sapu efek tertunda (wms:approve)
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from db import db
from dependencies import audit, require_permission, require_role
from entity_scope import assert_entity_access, entity_ctx, resolve_scope_ids

router = APIRouter()
INSTANCE_HEADER = "X-Connector-Instance"


async def _device(request: Request) -> Dict[str, Any]:
    from services import rfid_ingest_service as ing
    return await ing.authenticate(request.headers.get("X-Device-Key"))


class ClaimPayload(BaseModel):
    limit: int = Field(1, ge=1, le=5)
    instance_id: Optional[str] = Field(None, max_length=80)


class StartPayload(BaseModel):
    item_ids: List[str] = Field(..., min_length=1, max_length=200)
    job_revision: Optional[int] = Field(None, ge=1, le=100000)
    instance_id: Optional[str] = Field(None, max_length=80)


class RenewPayload(BaseModel):
    instance_id: Optional[str] = Field(None, max_length=80)


class ItemResult(BaseModel):
    result_event_id: str = Field(..., min_length=1, max_length=100)
    item_id: str = Field(..., min_length=1, max_length=80)
    print_status: str
    encode_status: str
    payload_sha256: Optional[str] = Field(None, max_length=64)
    evidence: Dict[str, Any] = {}


class ResultsPayload(BaseModel):
    results: List[ItemResult] = Field(..., min_length=1, max_length=200)
    instance_id: Optional[str] = Field(None, max_length=80)


class TelemetryPayload(BaseModel):
    instance_id: Optional[str] = Field(None, max_length=80)
    connector: Dict[str, Any] = {}
    printer: Dict[str, Any] = {}


# ─── Perangkat ───────────────────────────────────────────────────────────────
@router.get("/rfid/printer-agent/config")
async def get_agent_config(request: Request) -> Dict[str, Any]:
    from services import rfid_printer_protocol as prn
    return await prn.agent_config(await _device(request))


@router.post("/rfid/printer-agent/telemetry")
async def post_agent_telemetry(payload: TelemetryPayload, request: Request) -> Dict[str, Any]:
    from services import rfid_printer_protocol as prn
    return await prn.telemetry(await _device(request), payload.model_dump())


@router.post("/rfid/device-jobs/claim")
async def post_device_claim(request: Request, payload: Optional[ClaimPayload] = None) -> Dict[str, Any]:
    from services import rfid_printer_protocol as prn
    p = payload or ClaimPayload()
    return await prn.claim_jobs(await _device(request), p.limit,
                                p.instance_id or request.headers.get(INSTANCE_HEADER))


@router.get("/rfid/device-jobs/{job_id}/attempts/{attempt_id}")
async def get_attempt_state(job_id: str, attempt_id: str, request: Request) -> Dict[str, Any]:
    from services import rfid_printer_protocol as prn
    return await prn.attempt_state(await _device(request), job_id, attempt_id)


@router.post("/rfid/device-jobs/{job_id}/attempts/{attempt_id}/renew")
async def post_attempt_renew(job_id: str, attempt_id: str, request: Request,
                             payload: Optional[RenewPayload] = None) -> Dict[str, Any]:
    from services import rfid_printer_protocol as prn
    inst = (payload.instance_id if payload else None) or request.headers.get(INSTANCE_HEADER)
    return await prn.renew_lease(await _device(request), job_id, attempt_id, inst)


@router.post("/rfid/device-jobs/{job_id}/attempts/{attempt_id}/start")
async def post_attempt_start(job_id: str, attempt_id: str, payload: StartPayload, request: Request) -> Dict[str, Any]:
    from services import rfid_printer_protocol as prn
    return await prn.start_items(await _device(request), job_id, attempt_id, payload.item_ids, payload.job_revision,
                                 payload.instance_id or request.headers.get(INSTANCE_HEADER))


@router.post("/rfid/device-jobs/{job_id}/attempts/{attempt_id}/results")
async def post_attempt_results(job_id: str, attempt_id: str, payload: ResultsPayload,
                               request: Request) -> Dict[str, Any]:
    from services import rfid_printer_protocol as prn
    return await prn.report_results(await _device(request), job_id, attempt_id,
                                    [r.model_dump() for r in payload.results])


# ─── Pengguna ────────────────────────────────────────────────────────────────
@router.get("/rfid/printers/queue")
async def get_printer_queue(request: Request, warehouse_id: Optional[str] = None, status: Optional[str] = None,
                            entity_id: Optional[str] = None,
                            limit: int = Query(300, ge=1, le=1000)) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    from services import rfid_print_service as rps
    return await rps.queue_overview(resolve_scope_ids(await entity_ctx(request), entity_id), warehouse_id, status, limit)


@router.get("/rfid/printers/follow-up")
async def get_printer_follow_up(request: Request, warehouse_id: Optional[str] = None,
                                entity_id: Optional[str] = None) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    from services import rfid_print_service as rps
    rows = await rps.follow_up_items(resolve_scope_ids(await entity_ctx(request), entity_id), warehouse_id)
    return {"count": len(rows), "items": rows, "labels": rps.FOLLOW_UP_LABEL}


class ResolvePayload(BaseModel):
    action: str
    note: str = Field(..., min_length=5, max_length=500)
    evidence_type: str = "other"
    evidence_ref: str = Field("", max_length=120)


@router.post("/rfid/print-jobs/{job_id}/items/{item_id}/resolve")
async def post_resolve_item(job_id: str, item_id: str, payload: ResolvePayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "approve")
    from services import rfid_print_service as rps
    res = await rps.resolve_item(job_id, item_id, resolve_scope_ids(await entity_ctx(request), None), actor["name"],
                                 payload.action, payload.note, payload.evidence_type, payload.evidence_ref)
    await audit(actor["name"], "rfid_print_item_resolved", "rfid_print_job", job_id,
                {"item_id": item_id, "action": payload.action, "evidence_type": payload.evidence_type,
                 "reprint_job": (res.get("reprint_job") or {}).get("job_number")}, reason=payload.note)
    return res


class RetagPayload(BaseModel):
    reason_code: str
    note: str = Field(..., min_length=5, max_length=500)


async def _roll(roll_id: str, request: Request) -> Dict[str, Any]:
    roll = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
    if not roll:
        raise HTTPException(status_code=404, detail="Roll tidak ditemukan")
    assert_entity_access({"entity_id": roll.get("owner_entity_id")}, "inventory_rolls", await entity_ctx(request))
    return roll


@router.post("/rfid/rolls/{roll_id}/replace-tag")
async def post_replace_tag(roll_id: str, payload: RetagPayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "approve")
    await _roll(roll_id, request)
    from services import rfid_print_service as rps
    res = await rps.replace_tag(roll_id, resolve_scope_ids(await entity_ctx(request), None), actor["name"],
                                payload.reason_code, payload.note)
    await audit(actor["name"], "rfid_tag_replaced", "inventory_roll", roll_id,
                {"reason_code": payload.reason_code, "old_epc": (res.get("old_tag") or {}).get("epc"),
                 "new_epc": res["new_tag"]["epc"], "job_number": res["job"].get("job_number")}, reason=payload.note)
    return res


@router.post("/rfid/rolls/{roll_id}/reprint-label")
async def post_reprint_label(roll_id: str, payload: RetagPayload, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "print")
    await _roll(roll_id, request)
    from services import rfid_print_service as rps
    job = await rps.create_text_reprint_job(roll_id, resolve_scope_ids(await entity_ctx(request), None),
                                            actor["name"], payload.reason_code, payload.note)
    await audit(actor["name"], "roll_label_text_reprint", "inventory_roll", roll_id,
                {"reason_code": payload.reason_code, "job_number": job.get("job_number"),
                 "epc": (job.get("items") or [{}])[0].get("epc")}, reason=payload.note)
    return job


@router.get("/rfid/rolls/{roll_id}/tag-history")
async def get_tag_history(roll_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    from services import rfid_print_service as rps
    return await rps.roll_tag_history(await _roll(roll_id, request))


async def _printer_device(device_id: str) -> Dict[str, Any]:
    dev = await db.rfid_devices.find_one({"id": device_id, "type": "printer"}, {"_id": 0, "api_key": 0, "api_key_hash": 0})
    if not dev:
        raise HTTPException(status_code=404, detail="Printer tidak ditemukan")
    return dev


@router.get("/rfid/printers/{device_id}/profile")
async def get_printer_profile(device_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    from services import rfid_label_template as tpl
    from services import rfid_printer_protocol as prn
    dev = await _printer_device(device_id)
    profile = prn.device_profile(dev)
    return {"device_id": device_id, "name": dev.get("name"), "code": dev.get("code"),
            "warehouse_id": dev.get("warehouse_id"), "profile": profile, "profile_key": tpl.profile_key(profile),
            "defaults": tpl.DEFAULT_PROFILE, "dots": tpl.dot_budget(profile),
            "connection": dev.get("printer_connection") or {}, "capabilities": prn._caps(dev),
            "updated_at": dev.get("printer_profile_at"), "updated_by": dev.get("printer_profile_by")}


class ProfilePayload(BaseModel):
    profile: Dict[str, Any]
    connection: Dict[str, Any] = {}
    capabilities: Optional[List[str]] = None


@router.put("/rfid/printers/{device_id}/profile")
async def put_printer_profile(device_id: str, payload: ProfilePayload, request: Request) -> Dict[str, Any]:
    actor = await require_role(request, ["admin"])
    from core_utils import now_iso
    from services import rfid_label_template as tpl
    before = await _printer_device(device_id)
    try:
        profile = tpl.normalize_profile(payload.profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    conn = {"host": str(payload.connection.get("host") or "")[:80],
            "port": int(payload.connection.get("port") or 9100),
            "note": str(payload.connection.get("note") or "")[:200]}
    if not 1 <= conn["port"] <= 65535:
        raise HTTPException(status_code=400, detail="Port printer 1–65535")
    upd: Dict[str, Any] = {"printer_profile": profile, "printer_connection": conn, "printer_profile_at": now_iso(),
                           "printer_profile_by": actor["name"]}
    if payload.capabilities is not None:
        caps = [c for c in payload.capabilities if c in ("rfid", "qr")]
        if not caps:
            raise HTTPException(status_code=400, detail="Kemampuan printer minimal satu: rfid / qr")
        upd["capabilities"] = caps
    await db.rfid_devices.update_one({"id": device_id}, {"$set": upd})
    await audit(actor["name"], "rfid_printer_profile_updated", "rfid_device", device_id,
                {"profile_key": tpl.profile_key(profile), "dpi": profile["dpi"], "connection": conn},
                before={"profile": before.get("printer_profile")})
    return await get_printer_profile(device_id, request)


class PreviewPayload(BaseModel):
    profile: Optional[Dict[str, Any]] = None
    device_id: Optional[str] = None
    job_id: Optional[str] = None
    item_id: Optional[str] = None


@router.post("/rfid/printers/label-preview")
async def post_label_preview(payload: PreviewPayload, request: Request) -> Dict[str, Any]:
    """Pratinjau perkiraan tata letak (SVG di UI) + ZPL persis yang akan dikirim — tanpa layanan eksternal."""
    await require_permission(request, "wms", "view")
    from services import rfid_label_template as tpl
    from services import rfid_print_service as rps
    from services import rfid_printer_protocol as prn
    raw = payload.profile
    if raw is None and payload.device_id:
        raw = prn.device_profile(await _printer_device(payload.device_id))
    try:
        profile = tpl.normalize_profile(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    snap, kind, it = tpl.sample_snapshot(), "rfid_tag", None
    if payload.job_id:
        job = await rps.get_print_job(payload.job_id, resolve_scope_ids(await entity_ctx(request), None))
        kind = job.get("kind") or "rfid_tag"
        it = next((i for i in job.get("items") or [] if not payload.item_id or i.get("item_id") == payload.item_id), None)
        if not it:
            raise HTTPException(status_code=404, detail="Item job tidak ditemukan")
        snap = rps._item_snapshot(it)
    rfid = kind in rps.RFID_WRITE_KINDS
    if kind == "qr_label":
        return {"kind": kind, "layout": None, "zpl": (it or {}).get("zpl", ""),
                "note": "Label QR 58 × 40 mm memakai templat terpisah (tanpa tulis chip)."}
    return {"kind": kind, "layout": tpl.layout(snap, profile, rfid=rfid), "zpl": tpl.render_zpl(snap, profile, rfid=rfid),
            "profile_key": tpl.profile_key(profile), "dots": tpl.dot_budget(profile),
            "expected_responses": tpl.expected_responses(profile, rfid)}


@router.post("/rfid/printers/recover-effects")
async def post_recover_effects(request: Request, warehouse_id: Optional[str] = None) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "approve")
    from services import rfid_print_service as rps
    res = await rps.recover_pending_effects(warehouse_id, limit=200)
    await audit(actor["name"], "rfid_print_effects_recovered", "rfid_print_job", warehouse_id or "all",
                {"recovered_items": res["recovered_items"], "failed": len(res["failed"])})
    return res

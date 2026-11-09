"""PREP-G — API aplikasi handheld Chainway C72 (prefix `/api/handheld`). Kontrak: `middleware/c72-app/docs/02_ARSITEKTUR_DAN_KONTRAK.md`.

Identitas:
  * `GET /device/config` — PERANGKAT saja (`X-Device-Key`): binding gudang/site, profil, batas, jam server.
  * Endpoint kerja — PERANGKAT **dan** PENGGUNA (`X-Device-Key` + `Authorization: Bearer`): izin per jenis tugas =
    izin endpoint web asal, cakupan = gudang perangkat ∩ lokasi kerja pengguna.
  * `/devices*` — admin/supervisor ERP (sesi pengguna saja): registri, key, cabut, profil, jejak pakai.
Mutasi idempoten lewat ID klien (`client_batch_id` / `client_request_id`, atau header `Idempotency-Key`).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from dependencies import audit, require_permission, require_role
from services import handheld_core as core
from services import handheld_devices as devs
from services import handheld_sync as sync
from services import handheld_tags as tags
from services import handheld_tasks as tasks

router = APIRouter(prefix="/api/handheld", tags=["handheld"])


class AppVersionIn(BaseModel):
    app_version: str = ""


class SessionEndIn(BaseModel):
    operator_session_id: str
    reason: str = ""


class ReadIn(BaseModel):
    epc: str = Field(..., max_length=128)
    rssi: Optional[float] = None
    count: int = 1
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    tid: Optional[str] = Field(None, max_length=64)


class BatchIn(BaseModel):
    client_batch_id: str = ""
    kind: str
    doc_id: str
    session_id: Optional[str] = None
    snapshot_version: Optional[str] = None
    operator_session_id: Optional[str] = None
    user_id: Optional[str] = None
    device_time: Optional[str] = None
    clock_offset_ms: Optional[int] = None
    clock_synced: Optional[bool] = None
    captured_from: Optional[str] = None
    captured_to: Optional[str] = None
    reads: List[ReadIn] = Field(default_factory=list, max_length=2000)
    labels: List[str] = Field(default_factory=list, max_length=500)
    label_reason: str = Field("", max_length=300)
    lines: List[Dict[str, Any]] = Field(default_factory=list, max_length=50)
    bin_id: str = ""
    simulated: bool = False          # radio tiruan perangkat (demo/UAT) — bukti berlabel simulasi, tanpa mutasi stok


class RequestIn(BaseModel):
    client_request_id: str = ""
    operator_session_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class CutIn(RequestIn):
    roll_id: str = ""
    epc: str = ""
    actual_length: Optional[float] = Field(None, gt=0)
    reason: str = Field("", max_length=300)


class TagWriteIn(RequestIn):
    code: str = ""
    roll_id: str = ""
    reason: str = Field("", max_length=300)


class TagConfirmIn(RequestIn):
    verified_epc: str = ""
    tid: Optional[str] = Field(None, max_length=64)
    rssi: Optional[float] = None
    attempts: Optional[int] = None
    write_power_dbm: Optional[int] = None


class TagFailIn(RequestIn):
    reason: str = Field("", max_length=300)
    attempts: Optional[int] = None


class PoolIn(BaseModel):
    count: int = Field(50, ge=1, le=200)


class LineIdsIn(BaseModel):
    line_ids: List[str] = Field(default_factory=list, max_length=500)


class LabelIn(BaseModel):
    raw: str = Field(..., max_length=2000)
    supplier_id: str = ""


class RackIn(BaseModel):
    done: bool = True


class DeviceCreateIn(BaseModel):
    name: str
    warehouse_id: str
    code: str = ""
    location: str = ""
    scope_level: str = "site"
    profile: Dict[str, Any] = Field(default_factory=dict)
    base_url: str = ""


class RevokeIn(BaseModel):
    reason: str


class ProfileIn(BaseModel):
    profile: Optional[Dict[str, Any]] = None
    scope_level: Optional[str] = None


def _key(request: Request, body_key: str) -> str:
    return (body_key or request.headers.get("Idempotency-Key") or "").strip()


# ─── Perangkat ────────────────────────────────────────────────────────────────
@router.get("/device/config")
async def device_config(request: Request, app_version: str = "") -> Dict[str, Any]:
    return await core.device_config(await core.device_from(request), app_version)


# ─── Sesi operator ────────────────────────────────────────────────────────────
@router.post("/session/start")
async def session_start(payload: AppVersionIn, request: Request) -> Dict[str, Any]:
    ctx = await core.context(request)
    # FIX-1 (audit B2b RFID-7, selaras B1 UI-23) — sesi operator hanya untuk akun yang boleh mengerjakan minimal satu
    # jenis tugas gudang; dulu sopir (izin logistik saja) mendapat sesi C72 dengan gudang SRG-01.
    if not any(k.get("allowed") for k in await core.allowed_kinds(ctx.user)):
        raise core.err(403, "NO_HANDHELD_KIND", "Akun ini tidak berizin mengerjakan tugas gudang di perangkat handheld.")
    op = await core.start_operator(ctx, payload.app_version)
    await audit(ctx.actor_name, "handheld_operator_login", "rfid_device", ctx.device["id"],
                {"device": ctx.device.get("code"), "operator_session_id": op["id"]}, source=ctx.source)
    return await core.me(ctx, op)


@router.post("/session/end")
async def session_end(payload: SessionEndIn, request: Request) -> Dict[str, Any]:
    ctx = await core.context(request)
    op = await core.end_operator(ctx, payload.operator_session_id, payload.reason)
    await audit(ctx.actor_name, "handheld_operator_logout", "rfid_device", ctx.device["id"],
                {"device": ctx.device.get("code"), "operator_session_id": op["id"]}, source=ctx.source)
    return {"ok": True, "operator_session": op}


@router.get("/me")
async def me(request: Request) -> Dict[str, Any]:
    return await core.me(await core.context(request))


# ─── Tugas & yang diharapkan ──────────────────────────────────────────────────
@router.get("/tasks/summary")
async def tasks_summary(request: Request) -> Dict[str, Any]:
    ctx = await core.context(request)
    kinds = await core.allowed_kinds(ctx.user)
    for k in kinds:
        k["open_count"] = len(await tasks.list_tasks(ctx, k["code"], "", 300)) if k["allowed"] else 0
    return {"kinds": kinds, "warehouses": [w["id"] for w in ctx.warehouses]}


@router.get("/tasks")
async def list_tasks(request: Request, kind: str, q: str = "", limit: int = 100) -> Dict[str, Any]:
    ctx = await core.kind_context(request, kind)
    rows = await tasks.list_tasks(ctx, kind, q, limit)
    return {"kind": kind, "count": len(rows), "tasks": rows}


@router.get("/tasks/{kind}/{doc_id}/expected")
async def expected(kind: str, doc_id: str, request: Request, offset: int = Query(0, ge=0),
                   limit: int = Query(5000, ge=1, le=5000), start: bool = False) -> Dict[str, Any]:
    ctx = await core.kind_context(request, kind)
    out = await tasks.expected(ctx, kind, doc_id, offset, limit, start)
    if start and out.get("session_id"):
        await audit(ctx.actor_name, "handheld_session_opened", "rfid_verify_session", out["session_id"],
                    {"kind": kind, "doc_id": doc_id}, source=ctx.source)
    return out


@router.post("/batches")
async def post_batch(payload: BatchIn, request: Request) -> Dict[str, Any]:
    ctx = await core.kind_context(request, payload.kind)
    body = payload.model_dump()
    body["client_batch_id"] = _key(request, payload.client_batch_id)
    return await sync.submit_batch(ctx, body)


@router.post("/tasks/{kind}/{doc_id}/complete")
async def complete(kind: str, doc_id: str, payload: RequestIn, request: Request) -> Dict[str, Any]:
    ctx = await core.kind_context(request, kind)
    body = payload.model_dump()
    body["client_request_id"] = _key(request, payload.client_request_id)
    return await sync.complete(ctx, kind, doc_id, body)


@router.post("/tasks/cutting/{task_id}/cut")
async def cut(task_id: str, payload: CutIn, request: Request) -> Dict[str, Any]:
    ctx = await core.kind_context(request, "cutting")
    body = payload.model_dump()
    body["client_request_id"] = _key(request, payload.client_request_id)
    return await sync.cut(ctx, task_id, body)


# ─── Roll, tag & tulis EPC ────────────────────────────────────────────────────
@router.get("/lookup")
async def lookup(request: Request, code: str = Query(..., min_length=1, max_length=200)) -> Dict[str, Any]:
    ctx = await core.context(request, ("wms", "view"))
    return await tags.lookup(ctx, code)


@router.get("/untagged")
async def untagged(request: Request, warehouse_id: str = "", limit: int = 300) -> Dict[str, Any]:
    ctx = await core.context(request, ("wms", "view"))
    rows = await tags.untagged(ctx, warehouse_id, limit)
    return {"count": len(rows), "rolls": rows}


@router.post("/tag-writes")
async def tag_write(payload: TagWriteIn, request: Request) -> Dict[str, Any]:
    ctx = await core.context(request, core.TAG_WRITE_PERM)
    body = payload.model_dump()
    body["client_request_id"] = _key(request, payload.client_request_id)
    return await tags.create_write(ctx, body)


@router.post("/tag-writes/{write_id}/confirm")
async def tag_confirm(write_id: str, payload: TagConfirmIn, request: Request) -> Dict[str, Any]:
    ctx = await core.context(request, core.TAG_WRITE_PERM)
    body = payload.model_dump()
    body["client_request_id"] = _key(request, payload.client_request_id)
    return await tags.confirm_write(ctx, write_id, body)


@router.post("/tag-writes/{write_id}/fail")
async def tag_fail(write_id: str, payload: TagFailIn, request: Request) -> Dict[str, Any]:
    ctx = await core.context(request, core.TAG_WRITE_PERM)
    return await tags.fail_write(ctx, write_id, payload.model_dump())


# ─── Daftar Awal ──────────────────────────────────────────────────────────────
REG_PERM = core.KINDS["registration"]["perm"]


@router.get("/registration/catalog")
async def reg_catalog(request: Request, q: str = "", limit: int = 3000) -> Dict[str, Any]:
    ctx = await core.context(request, REG_PERM)
    return await tasks.catalog(ctx, q, limit)


@router.post("/registration/{sid}/epc-pool")
async def reg_pool(sid: str, payload: PoolIn, request: Request) -> Dict[str, Any]:
    ctx = await core.context(request, REG_PERM)
    out = await tags.reserve_epcs(ctx, sid, payload.count)
    await audit(ctx.actor_name, "registration_epc_reserved", "cycle_count", sid, {"device": ctx.device.get("code"),
                                                                                    "reserved": out["count"]}, source=ctx.source)
    return out


@router.post("/registration/{sid}/lines/mark-written")
async def reg_written(sid: str, payload: LineIdsIn, request: Request) -> Dict[str, Any]:
    ctx = await core.context(request, REG_PERM)
    return await tags.mark_written(ctx, sid, payload.line_ids)


@router.post("/registration/{sid}/label-decode")
async def reg_label(sid: str, payload: LabelIn, request: Request) -> Dict[str, Any]:
    from services import initial_registration_lines as irl
    ctx = await core.context(request, REG_PERM)
    return await irl.decode_label(await tasks.registration_session(ctx, sid), payload.raw, payload.supplier_id.strip())


@router.post("/registration/{sid}/racks/{rack_id}")
async def reg_rack(sid: str, rack_id: str, payload: RackIn, request: Request) -> Dict[str, Any]:
    from services import initial_registration_service as irs
    ctx = await core.context(request, REG_PERM)
    return await irs.mark_rack(await tasks.registration_session(ctx, sid), rack_id, payload.done, ctx.user)


# ─── Admin: registri perangkat ────────────────────────────────────────────────
@router.get("/devices")
async def list_devices(request: Request) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    rows = await devs.list_devices()
    return {"count": len(rows), "devices": rows}


@router.post("/devices")
async def create_device(payload: DeviceCreateIn, request: Request) -> Dict[str, Any]:
    actor = await require_role(request, ["admin"])
    out = await devs.create(payload.model_dump(), actor["name"])
    await audit(actor["name"], "handheld_device_created", "rfid_device", out["device"]["id"],
                {"code": out["device"].get("code"), "warehouse_id": payload.warehouse_id, "scope_level": payload.scope_level})
    return out


@router.post("/devices/{device_id}/rotate-key")
async def rotate_key(device_id: str, request: Request, base_url: str = "") -> Dict[str, Any]:
    actor = await require_role(request, ["admin"])
    out = await devs.rotate_key(device_id, base_url)
    await audit(actor["name"], "rfid_device_key_issued", "rfid_device", device_id, {"regenerate": True, "via": "handheld"})
    return out


@router.post("/devices/{device_id}/revoke")
async def revoke(device_id: str, payload: RevokeIn, request: Request) -> Dict[str, Any]:
    actor = await require_role(request, ["admin", "warehouse_admin"])
    out = await devs.revoke(device_id, payload.reason, actor["name"])
    await audit(actor["name"], "handheld_device_revoked", "rfid_device", device_id, {}, reason=payload.reason.strip())
    return out


@router.post("/devices/{device_id}/enable")
async def enable(device_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_role(request, ["admin"])
    out = await devs.enable(device_id)
    await audit(actor["name"], "handheld_device_enabled", "rfid_device", device_id, {})
    return out


@router.put("/devices/{device_id}/profile")
async def set_profile(device_id: str, payload: ProfileIn, request: Request) -> Dict[str, Any]:
    actor = await require_role(request, ["admin"])
    out = await devs.set_profile(device_id, payload.profile, payload.scope_level)
    await audit(actor["name"], "handheld_profile_set", "rfid_device", device_id,
                {"profile_version": out.get("profile_version"), "scope_level": out.get("scope_level")})
    return out


@router.get("/devices/{device_id}/activity")
async def device_activity(device_id: str, request: Request, limit: int = 50) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    return await devs.activity(device_id, limit)

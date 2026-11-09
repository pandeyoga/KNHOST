"""PREP-B — API pendaftaran awal gedung (opname awal RFID, KEPUTUSAN_GATE_RFID §8).

Disertakan lewat router opname (`routers/cycle_count.py` → `router.include_router`) — prefix `/api/registration/...`.
Lapangan (HP/handheld): izin `inventory.cycle_count`. Kembalikan/tolak/setujui: `inventory.approve_count`.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from db import db
from dependencies import audit, require_permission
from entity_scope import entity_ctx, guard_doc
from core_utils import new_id, now_iso, safe_doc
from services import initial_registration_lines as irl
from services import initial_registration_plan as irp
from services import initial_registration_service as irs
from services import registration_freeze as rfz

router = APIRouter()


class RegSessionCreate(BaseModel):
    warehouse_id: str
    name: str = ""
    notes: str = ""
    freeze_mode: str = "zone"          # warehouse = beku penuh (gedung kecil) · zone = per zona/rak (gedung besar)
    epc_mode: str = "read"             # read = EPC bawaan tag · system = EPC dibuat sistem (K-OPN-05 terbuka)
    node_ids: List[str] = []


class RegLineIn(BaseModel):
    epc: Optional[str] = None
    product_id: Optional[str] = None
    qty: Optional[float] = Field(default=None, gt=0, le=100000)
    unit: Optional[str] = None
    length_from_label: Optional[bool] = None
    lot: Optional[str] = None
    dye_lot: Optional[str] = None
    grade: Optional[str] = None
    owner_entity_id: Optional[str] = None
    bin_id: Optional[str] = None
    old_roll_no: Optional[str] = None
    note: Optional[str] = None
    unrecognized: Optional[bool] = None
    label_raw: Optional[str] = None


class RegCodesIn(BaseModel):
    codes: Any = ""                     # teks tempel (baris/spasi/koma) atau daftar


class RegLabelIn(BaseModel):
    raw: str
    supplier_id: str = ""


class RegRackIn(BaseModel):
    done: bool = True


class RegLineIds(BaseModel):
    line_ids: List[str] = []


class RegReason(BaseModel):
    reason: str


class RegApproveIn(BaseModel):
    group_keys: List[str] = []          # kosong = seluruh sesi
    reason: str = "Disetujui sesuai hasil pendaftaran awal"
    zero_cost_reason: str = ""
    accept_exceptions: bool = False


async def _session(sid: str, request: Request) -> Dict[str, Any]:
    s = safe_doc(await db.cycle_count_sessions.find_one({"id": sid, "mode": "registration"}, {"_id": 0}))
    await guard_doc(request, "cycle_count_sessions", s, not_found="Sesi pendaftaran tidak ditemukan")
    return s


async def _ctx_owners(request: Request) -> Optional[List[str]]:
    return irs.allowed_owners(await entity_ctx(request))


async def _line_actor(request: Request, session: Dict[str, Any]) -> Dict[str, Any]:
    """Saat menunggu persetujuan hanya penyetuju yang boleh memetakan/membatalkan baris."""
    if session.get("status") == "pending_approval":
        return await require_permission(request, "inventory", "approve_count")
    return await require_permission(request, "inventory", "cycle_count")


@router.post("/registration/sessions")
async def create_reg_session(payload: RegSessionCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "cycle_count")
    # FIX-1 (B2a STM-IN-02) — pendaftaran hanya di gedung lokasi tugas; aksi sesudahnya lewat `_session` → `guard_doc`
    # (pagar lokasi `cycle_count_sessions` di `location_scope.WAREHOUSE_FIELDS`).
    from services import location_scope
    await location_scope.assert_warehouse(actor, payload.warehouse_id, "mendaftarkan stok awal di gudang ini")
    s = await irs.create_session(payload.model_dump(), actor, await entity_ctx(request))
    await audit(actor["name"], "registration_created", "cycle_count", s["id"],
                {"warehouse_id": s["warehouse_id"], "freeze_mode": payload.freeze_mode, "epc_mode": payload.epc_mode})
    return await irs.detail(s)


@router.get("/registration/sessions")
async def list_reg_sessions(request: Request, warehouse_id: str = "", status: str = "",
                            entity_id: str = "") -> List[Dict[str, Any]]:
    await require_permission(request, "inventory", "cycle_count")
    # FIX-1 (K-B1-02, B2a STM-IN-02) — per GEDUNG dalam lokasi kerja, lintas PT yang ditugaskan (dulu Rancamalang
    # "Semua" melihat sesi Soreang & Jakarta; petugas berpagar kini hanya gedungnya).
    from entity_scope import resolve_work_scope
    q = await resolve_work_scope("cycle_count_sessions", {"mode": "registration"}, await entity_ctx(request),
                                 entity_id or None)
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    if status:
        q["status"] = {"$in": status.split(",")}
    rows = await db.cycle_count_sessions.find(q, {"_id": 0, "roll_count": 0, "registration.bin_ids": 0, "freeze.bin_ids": 0}
                                              ).sort("created_at", -1).to_list(200)
    return [{**safe_doc(r), "status_label": irs.STATUS_LABEL.get(r.get("status"), r.get("status"))} for r in rows]


@router.get("/registration/sessions/{sid}")
async def get_reg_session(sid: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "inventory", "cycle_count")
    return await irs.detail(await _session(sid, request))


@router.post("/registration/sessions/{sid}/start")
async def start_reg_session(sid: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "cycle_count")
    s = await irs.start_session(await _session(sid, request), actor)
    await audit(actor["name"], "registration_started", "cycle_count", sid, {"freeze": (s.get("freeze") or {}).get("label")})
    return await irs.detail(s)


@router.get("/registration/sessions/{sid}/bins")
async def list_reg_bins(sid: str, request: Request) -> Dict[str, Any]:
    """Bin dalam cakupan sesi (pemilih bin aktif di HP)."""
    from services.location_service import flatten_bins
    await require_permission(request, "inventory", "cycle_count")
    s = await _session(sid, request)
    wh = await db.warehouses.find_one({"id": s["warehouse_id"]}, {"_id": 0}) or {}
    keep = set((s.get("registration") or {}).get("bin_ids") or [])
    return {"bins": [{"id": b["bin_id"], "code": b.get("code", ""), "rack_id": b.get("rack_id") or "-", "rack": b.get("rack", ""),
                      "zone": b.get("zone", ""), "path": b.get("path", "")} for b in flatten_bins(wh) if b["bin_id"] in keep]}


@router.post("/registration/sessions/{sid}/racks/{rack_id}")
async def mark_reg_rack(sid: str, rack_id: str, payload: RegRackIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "cycle_count")
    return await irs.mark_rack(await _session(sid, request), rack_id, payload.done, actor)


@router.get("/registration/sessions/{sid}/lines")
async def list_reg_lines(sid: str, request: Request, rack_id: str = "", bin_id: str = "", status: str = "",
                         limit: int = 500) -> Dict[str, Any]:
    await require_permission(request, "inventory", "cycle_count")
    s = await _session(sid, request)
    return {"lines": [safe_doc(x) for x in await irl.list_lines(s["id"], rack_id, bin_id, status, limit)]}


@router.post("/registration/sessions/{sid}/epc-check")
async def check_reg_epcs(sid: str, payload: RegCodesIn, request: Request) -> Dict[str, Any]:
    await require_permission(request, "inventory", "cycle_count")
    return {"results": await irl.check_epcs(await _session(sid, request), payload.codes)}


@router.post("/registration/sessions/{sid}/label-decode")
async def decode_reg_label(sid: str, payload: RegLabelIn, request: Request) -> Dict[str, Any]:
    await require_permission(request, "inventory", "cycle_count")
    return await irl.decode_label(await _session(sid, request), payload.raw, payload.supplier_id.strip())


@router.post("/registration/sessions/{sid}/lines")
async def add_reg_line(sid: str, payload: RegLineIn, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "cycle_count")
    s = await _session(sid, request)
    return await irl.add_line(s, payload.model_dump(), actor, await _ctx_owners(request))


@router.patch("/registration/sessions/{sid}/lines/{line_id}")
async def update_reg_line(sid: str, line_id: str, payload: RegLineIn, request: Request) -> Dict[str, Any]:
    s = await _session(sid, request)
    actor = await _line_actor(request, s)
    irs.assert_status(s, "running", "pending_approval")
    out = await irl.update_line(s, line_id, payload.model_dump(), actor, await _ctx_owners(request))
    await audit(actor["name"], "registration_line_updated", "cycle_count", sid, {"line_id": line_id, "product_id": out.get("product_id")})
    return out


@router.delete("/registration/sessions/{sid}/lines/{line_id}")
async def void_reg_line(sid: str, line_id: str, request: Request) -> Dict[str, Any]:
    s = await _session(sid, request)
    actor = await _line_actor(request, s)
    irs.assert_status(s, "running", "pending_approval")
    return await irl.void_line(s, line_id, actor)


@router.post("/registration/sessions/{sid}/lines/{line_id}/photo")
async def upload_reg_photo(sid: str, line_id: str, request: Request, file: UploadFile = File(...)) -> Dict[str, Any]:
    """Foto kain 'produk belum dikenali' (mekanisme unggah yang sama dengan lampiran retur)."""
    from services import storage_service as storage
    actor = await require_permission(request, "inventory", "cycle_count")
    s = await _session(sid, request)
    irs.assert_status(s, "running", "pending_approval")
    line = await db[irl.LINES].find_one({"id": line_id, "session_id": sid, "status": "draft"}, {"_id": 0, "unrecognized": 1})
    if not line or not line.get("unrecognized"):
        raise HTTPException(status_code=400, detail="Foto hanya untuk baris 'produk belum dikenali' yang belum diterapkan.")
    data = await file.read()
    try:
        ctype = storage.validate_upload(file.filename, file.content_type, len(data), data[:16])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    path = f"initial_registration/{sid}/{new_id('foto')}.{storage.ext_of(file.filename)}"
    await storage.put_object(path, data, ctype)
    photo = {"path": path, "content_type": ctype, "filename": file.filename, "size": len(data), "by": actor["name"], "at": now_iso()}
    await db[irl.LINES].update_one({"id": line_id, "status": "draft"}, {"$set": {"unrecognized.photo": photo, "updated_at": now_iso()}})
    return {"ok": True, "photo": {k: photo[k] for k in ("filename", "size", "at")}}


@router.get("/registration/sessions/{sid}/lines/{line_id}/photo")
async def get_reg_photo(sid: str, line_id: str, request: Request):
    from services import storage_service as storage
    await require_permission(request, "inventory", "cycle_count")
    await _session(sid, request)
    line = await db[irl.LINES].find_one({"id": line_id, "session_id": sid}, {"_id": 0, "unrecognized": 1})
    photo = ((line or {}).get("unrecognized") or {}).get("photo")
    if not photo:
        raise HTTPException(status_code=404, detail="Foto tidak ada")
    try:
        data, _ = await storage.get_object(photo["path"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Berkas foto tidak ditemukan di penyimpanan.") from exc
    return Response(content=data, media_type=photo.get("content_type") or "application/octet-stream")


@router.post("/registration/sessions/{sid}/lines/mark-written")
async def mark_reg_written(sid: str, payload: RegLineIds, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "cycle_count")
    return await irl.mark_written(await _session(sid, request), payload.line_ids, actor)


@router.post("/registration/sessions/{sid}/submit")
async def submit_reg_session(sid: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "cycle_count")
    s = await irs.submit(await _session(sid, request), actor)
    await audit(actor["name"], "registration_submitted", "cycle_count", sid, {"costs": len((s.get("registration") or {}).get("costs") or {})})
    return await irs.detail(s)


@router.get("/registration/sessions/{sid}/reconcile")
async def reconcile_reg_session(sid: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "inventory", "cycle_count")
    return await irp.reconcile(await _session(sid, request))


@router.post("/registration/sessions/{sid}/return")
async def return_reg_session(sid: str, payload: RegReason, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "approve_count")
    if len(payload.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="Alasan minimal 5 karakter.")
    s = await irs.return_to_running(await _session(sid, request), payload.reason.strip(), actor)
    await audit(actor["name"], "registration_returned", "cycle_count", sid, {"reason": payload.reason.strip()})
    return await irs.detail(s)


@router.post("/registration/sessions/{sid}/reject")
async def reject_reg_session(sid: str, payload: RegReason, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "approve_count")
    if len(payload.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="Alasan penolakan minimal 5 karakter.")
    s = await irs.reject(await _session(sid, request), payload.reason.strip(), actor)
    await audit(actor["name"], "registration_rejected", "cycle_count", sid, {"reason": payload.reason.strip()})
    return await irs.detail(s)


@router.post("/registration/sessions/{sid}/approve")
async def approve_reg_session(sid: str, payload: RegApproveIn, request: Request) -> Dict[str, Any]:
    """Persetujuan massal per produk×PT (`group_keys`) atau seluruh sesi. Idempoten & aman diulang."""
    from services import initial_registration_approve as ira
    actor = await require_permission(request, "inventory", "approve_count")
    if len(payload.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="Alasan persetujuan minimal 5 karakter.")
    s = await _session(sid, request)
    out = await ira.approve(s, [k for k in payload.group_keys if k], actor["name"], await _ctx_owners(request),
                            reason=payload.reason.strip(), zero_cost_reason=payload.zero_cost_reason.strip(),
                            accept_exceptions=payload.accept_exceptions)
    await audit(actor["name"], "registration_approved", "cycle_count", sid,
                {"groups": list(out["results"]), "complete": out["complete"], "reason": payload.reason.strip()})
    return {"results": out["results"], "complete": out["complete"], "session": await irs.detail(out["session"]),
            "reconcile": await irp.reconcile(out["session"])}


@router.get("/registration/freeze")
async def reg_freeze_status(request: Request, warehouse_id: str = "") -> Dict[str, Any]:
    """Pembekuan aktif + area terverifikasi pendaftaran per gudang (untuk layar gudang & cutover gate)."""
    await require_permission(request, "inventory", "view")
    if not warehouse_id:
        raise HTTPException(status_code=400, detail="warehouse_id wajib")
    rows = await rfz.active_freezes([warehouse_id])
    return {"freezes": [{"session_id": f["id"], "name": f.get("name"), "area": rfz.area_label(f),
                         "mode": (f.get("freeze") or {}).get("mode"), "since": (f.get("freeze") or {}).get("since")} for f in rows],
            "verified_areas": await rfz.area_verification(warehouse_id)}

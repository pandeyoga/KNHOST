"""PREP-B — API pendaftaran awal gedung (opname awal RFID, KEPUTUSAN_GATE_RFID §8).

Disertakan lewat router opname (`routers/cycle_count.py` → `router.include_router`) — prefix `/api/registration/...`.
Lapangan (HP/handheld): izin `inventory.cycle_count`. Kembalikan/tolak/setujui: `inventory.approve_count`.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from db import db
from dependencies import audit, require_any_permission, require_permission
from input_rules import KNIn, OptReasonStr, ReasonStr
from entity_scope import entity_ctx, guard_doc
from core_utils import new_id, now_iso, safe_doc
from services import initial_registration_lines as irl
from services import initial_registration_plan as irp
from services import initial_registration_service as irs
from services import registration_freeze as rfz

router = APIRouter()


class RegSessionCreate(KNIn):
    warehouse_id: str
    name: str = ""
    notes: str = ""
    freeze_mode: str = "zone"          # warehouse = beku penuh (gedung kecil) · zone = per zona/rak (gedung besar)
    epc_mode: str = "read"             # read = EPC bawaan tag · system = EPC dibuat sistem (K-OPN-05 terbuka)
    node_ids: List[str] = []


class RegLineIn(KNIn):
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


class RegCodesIn(KNIn):
    codes: Any = ""                     # teks tempel (baris/spasi/koma) atau daftar


class RegLabelIn(KNIn):
    raw: str
    supplier_id: str = ""


class RegRackIn(KNIn):
    done: bool = True


class RegLineIds(KNIn):
    line_ids: List[str] = []


class RegReason(KNIn):
    reason: ReasonStr                    # FIX-3a — K-14 ≥ 5 huruf (satu validator bersama)


class RegApproveIn(KNIn):
    group_keys: List[str] = []          # kosong = seluruh sesi
    # FIX-3a (B3b FRM-09 #11) — tanpa alasan bawaan teks tetap; wajib ≥ 5 huruf.
    reason: ReasonStr
    zero_cost_reason: OptReasonStr = ""
    accept_exceptions: bool = False


# FIX-3a — izin BACA sesi pendaftaran: petugas/penyetuju hitung ATAU Finance (penyetuju nilai & jurnal).
_READ_PERMS = [("inventory", "cycle_count"), ("inventory", "approve_value")]

# PR-T8b (Z1) — gerbang PERTAMA rute yang izinnya baru bisa dipilih sesudah sesi dimuat (status sesi / setelan PT):
# sesi + salah satu izin yang mungkin diminta, sebelum `_session` (dulu tanpa sesi / tanpa izin → 404 sesi tidak
# ditemukan). Izin persisnya tetap dipilih sesudah sesi dimuat — aturannya tidak berubah.
_LINE_PERMS = [("inventory", "cycle_count"), ("inventory", "approve_count")]
_DECIDE_PERMS = [("inventory", "approve_count"), ("inventory", "approve_value")]
_LINE_DENIED = ("Anda belum punya akses untuk mengubah baris pendaftaran stok awal. Minta Admin menambahkan akses "
                "'Stok & Persediaan'.")
_RETURN_DENIED = ("Anda belum punya akses untuk mengembalikan sesi pendaftaran stok awal. Minta Admin menambahkan akses "
                  "'Stok & Persediaan'.")
_APPROVE_DENIED = ("Anda belum punya akses untuk menyetujui pendaftaran stok awal. Minta Admin menambahkan akses "
                   "'Stok & Persediaan'.")


async def _session(sid: str, request: Request) -> Dict[str, Any]:
    s = safe_doc(await db.cycle_count_sessions.find_one({"id": sid, "mode": "registration"}, {"_id": 0}))
    await guard_doc(request, "cycle_count_sessions", s, not_found="Sesi pendaftaran tidak ditemukan")
    return s


async def _ctx_owners(request: Request) -> Optional[List[str]]:
    return irs.allowed_owners(await entity_ctx(request))


async def _line_actor(request: Request, session: Dict[str, Any]) -> Dict[str, Any]:
    """Saat menunggu persetujuan hanya penyetuju yang boleh memetakan/membatalkan baris."""
    if session.get("status") == "pending_approval":
        return await require_permission(request, "inventory", "approve_count", detail=(
            "Anda belum punya akses untuk mengubah baris sesi yang menunggu persetujuan. Minta Admin menambahkan akses "
            "'Stok & Persediaan'."))
    return await require_permission(request, "inventory", "cycle_count", detail=_LINE_DENIED)


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
                            entity_id: str = "", limit: int = 200, skip: int = 0) -> Any:
    """FIX-7 (B3b LST-01) — `skip`/`limit` (bawaan 200 = batas lama, maks 500) + jumlah sungguhan di header
    `X-Total-Count`/`X-Truncated` (dulu terpotong 200 diam-diam). Array tetap (kompatibel)."""
    await require_any_permission(request, _READ_PERMS)
    # FIX-1 (K-B1-02, B2a STM-IN-02) — per GEDUNG dalam lokasi kerja, lintas PT yang ditugaskan (dulu Rancamalang
    # "Semua" melihat sesi Soreang & Jakarta; petugas berpagar kini hanya gedungnya).
    from entity_scope import resolve_work_scope
    q = await resolve_work_scope("cycle_count_sessions", {"mode": "registration"}, await entity_ctx(request),
                                 entity_id or None)
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    if status:
        q["status"] = {"$in": status.split(",")}
    from pagination import clamp_limit, window_meta, window_headers
    lim, sk = clamp_limit(limit, 200, 500), clamp_limit(skip, 0, 10 ** 7, minimum=0)
    total = await db.cycle_count_sessions.count_documents(q)
    rows = await db.cycle_count_sessions.find(q, {"_id": 0, "roll_count": 0, "registration.bin_ids": 0, "freeze.bin_ids": 0}
                                              ).sort([("created_at", -1), ("id", -1)]).skip(sk).limit(lim).to_list(lim)
    out = [{**safe_doc(r), "status_label": irs.STATUS_LABEL.get(r.get("status"), r.get("status"))} for r in rows]
    from fastapi.encoders import jsonable_encoder
    from starlette.responses import JSONResponse
    return JSONResponse(jsonable_encoder(out), headers=window_headers(window_meta(total, len(out), sk, lim)))


@router.get("/registration/sessions/{sid}")
async def get_reg_session(sid: str, request: Request) -> Dict[str, Any]:
    await require_any_permission(request, _READ_PERMS)
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
    await require_any_permission(request, _LINE_PERMS, detail=_LINE_DENIED)
    s = await _session(sid, request)
    actor = await _line_actor(request, s)
    irs.assert_status(s, "running", "pending_approval")
    irs.assert_lines_editable(s)   # FIX-3a — hitungan disetujui gudang = baris terkunci
    out = await irl.update_line(s, line_id, payload.model_dump(), actor, await _ctx_owners(request))
    await audit(actor["name"], "registration_line_updated", "cycle_count", sid, {"line_id": line_id, "product_id": out.get("product_id")})
    return out


@router.delete("/registration/sessions/{sid}/lines/{line_id}")
async def void_reg_line(sid: str, line_id: str, request: Request) -> Dict[str, Any]:
    await require_any_permission(request, _LINE_PERMS, detail=_LINE_DENIED)
    s = await _session(sid, request)
    actor = await _line_actor(request, s)
    irs.assert_status(s, "running", "pending_approval")
    irs.assert_lines_editable(s)   # FIX-3a — hitungan disetujui gudang = baris terkunci
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
    await require_any_permission(request, _READ_PERMS)
    return await irp.reconcile(await _session(sid, request))


@router.post("/registration/sessions/{sid}/return")
async def return_reg_session(sid: str, payload: RegReason, request: Request) -> Dict[str, Any]:
    await require_any_permission(request, _DECIDE_PERMS, detail=_RETURN_DENIED)
    s0 = await _session(sid, request)
    # FIX-3a — saat menunggu Finance, Finance juga boleh mengembalikan sesi ke gudang (angka perlu diperbaiki).
    actor = (await require_any_permission(request, _DECIDE_PERMS, detail=_RETURN_DENIED)
             if (s0.get("registration") or {}).get("count_approval") else
             await require_permission(request, "inventory", "approve_count", detail=_RETURN_DENIED))
    s = await irs.return_to_running(s0, payload.reason.strip(), actor)
    await audit(actor["name"], "registration_returned", "cycle_count", sid, {"reason": payload.reason.strip()})
    return await irs.detail(s)


@router.post("/registration/sessions/{sid}/reject")
async def reject_reg_session(sid: str, payload: RegReason, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "approve_count")
    s = await irs.reject(await _session(sid, request), payload.reason.strip(), actor)
    await audit(actor["name"], "registration_rejected", "cycle_count", sid, {"reason": payload.reason.strip()})
    return await irs.detail(s)


@router.post("/registration/sessions/{sid}/approve-count")
async def approve_reg_count(sid: str, payload: RegReason, request: Request) -> Dict[str, Any]:
    """FIX-3a — LANGKAH 1 persetujuan dua langkah: gudang menyetujui HITUNGAN (baris terkunci; stok & jurnal belum)."""
    actor = await require_permission(request, "inventory", "approve_count")
    s = await irs.approve_count(await _session(sid, request), payload.reason, actor)
    await audit(actor["name"], "registration_count_approved", "cycle_count", sid,
                {"reason": payload.reason, "totals": ((s.get("registration") or {}).get("count_approval") or {}).get("totals")})
    return await irs.detail(s)


@router.post("/registration/sessions/{sid}/approve")
async def approve_reg_session(sid: str, payload: RegApproveIn, request: Request) -> Dict[str, Any]:
    """Persetujuan massal per produk×PT (`group_keys`) atau seluruh sesi. Idempoten & aman diulang.
    FIX-3a — bila `registration.finance_approval` aktif (bawaan) ini LANGKAH 2: Finance (`inventory.approve_value`,
    orang berbeda dari penyetuju hitungan) menyetujui nilai & jurnal → roll lama dihapus & jurnal diposting."""
    await require_any_permission(request, _DECIDE_PERMS, detail=_APPROVE_DENIED)
    from services import initial_registration_approve as ira
    s = await _session(sid, request)
    if await irs.finance_step_required(s.get("entity_id") or ""):
        actor = await require_permission(request, "inventory", "approve_value", detail=(
            "Anda belum punya akses untuk menyetujui nilai dan jurnal pendaftaran stok awal. Minta Admin menambahkan "
            "akses 'Stok & Persediaan'."))
        await irs.assert_finance_ready(s, actor)
    else:
        actor = await require_permission(request, "inventory", "approve_count", detail=_APPROVE_DENIED)
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

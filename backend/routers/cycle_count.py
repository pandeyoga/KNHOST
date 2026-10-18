"""Cycle count / stock opname router."""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from db import db
from dependencies import require_permission, audit
from core_utils import new_id, now_iso, safe_doc, DEFAULT_ENTITY_ID
from entity_scope import entity_ctx, resolve_list_scope, assert_active_entity_access, guard_doc
from services import warehouse_scope_service as whscope
from services.roll_service import resolve_stock_owner
from services import stock_count_service as scs

router = APIRouter(prefix="/api")


async def _load_session(session_id: str, request: Request) -> Dict[str, Any]:
    """KN-A02 — semua aksi tulis sesi opname dijaga entitas seketat GET detail."""
    session = safe_doc(await db.cycle_count_sessions.find_one({"id": session_id}, {"_id": 0}))
    await guard_doc(request, "cycle_count_sessions", session, not_found="Session tidak ditemukan")
    return session


def _assert_item_owners(session: Dict[str, Any], ctx) -> None:
    """W2-006 — sesi lama bisa berisi item owner di luar scope; tolak sebelum membaca expected/mengubah roll."""
    allowed = set(ctx.allowed_entity_ids or [])
    foreign = sorted({i.get("owner_entity_id") or DEFAULT_ENTITY_ID for i in session.get("items", [])} - allowed)
    if foreign:
        raise HTTPException(status_code=403, detail="Sesi berisi stok badan usaha di luar akses Anda: " + ", ".join(foreign))


class CycleCountSessionCreate(BaseModel):
    warehouse_id: str
    name: str = ""
    notes: str = ""


class CycleCountItemCreate(BaseModel):
    product_id: str
    bin_id: str = ""
    notes: str = ""
    owner_entity_id: str = ""  # opsional: entitas pemilik stok (auto-resolve bila kosong)


class CycleCountItemUpdate(BaseModel):
    actual_qty: Any = None   # WM-07 — divalidasi scs.valid_qty (≥0, finite) → 400 terbaca, bukan 422/500 NaN
    notes: str = ""


class CycleCountApprove(BaseModel):
    reason: str = "Disetujui sesuai hasil cycle count"
    zero_cost_reason: str = ""   # FN-14 — wajib bila surplus tanpa biaya acuan


class CycleCountReject(BaseModel):
    reason: str


@router.post("/cycle-count/sessions")
async def create_session(payload: CycleCountSessionCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "cycle_count")
    ctx = await entity_ctx(request)
    # E4.1 — stock opname di gudang khusus badan usaha lain = menghitung barang orang.
    warehouse = await whscope.assert_usable(payload.warehouse_id, ctx.active_entity_id,
                                           action="melakukan stock opname di sini")
    from datetime import datetime, timezone
    session = {
        "id": new_id("cc"),
        "entity_id": ctx.active_entity_id,   # E-02 — sesi opname milik badan usaha konteks
        "warehouse_id": payload.warehouse_id,
        "warehouse_name": warehouse["name"],
        "warehouse_city": warehouse.get("city", ""),
        "name": payload.name or f"Count {datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}",
        "notes": payload.notes,
        "status": "open",
        "items": [],
        "created_by": actor["name"],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.cycle_count_sessions.insert_one(session)
    await audit(actor["name"], "cycle_count_created", "cycle_count", session["id"], session)
    return safe_doc(session)


@router.get("/cycle-count/sessions")
async def list_sessions(request: Request) -> List[Dict[str, Any]]:
    await require_permission(request, "inventory", "cycle_count")
    ctx = await entity_ctx(request)
    # E-02 (audit 2026-09-02) — koleksi SCOPED; dulu `find({})` menampilkan sesi PT lain.
    q = resolve_list_scope("cycle_count_sessions", {}, ctx)
    sessions = await db.cycle_count_sessions.find(q, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [safe_doc(s) for s in sessions if s]


@router.get("/cycle-count/sessions/{session_id}")
async def get_session(session_id: str, request: Request) -> Dict[str, Any]:
    await require_permission(request, "inventory", "cycle_count")
    session = safe_doc(await db.cycle_count_sessions.find_one({"id": session_id}, {"_id": 0}))
    if not session:
        raise HTTPException(status_code=404, detail="Session tidak ditemukan")
    assert_active_entity_access(session, "cycle_count_sessions", await entity_ctx(request))  # E-02
    return session


@router.post("/cycle-count/sessions/{session_id}/items")
async def add_item(session_id: str, payload: CycleCountItemCreate, request: Request) -> Dict[str, Any]:
    await require_permission(request, "inventory", "cycle_count")
    session = await _load_session(session_id, request)
    if session["status"] != "open":
        raise HTTPException(status_code=400, detail="Session tidak ditemukan atau tidak open")
    product = safe_doc(await db.products.find_one({"id": payload.product_id}, {"_id": 0}))
    if not product:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    # Owner-aware (KN_15 §9): expected dari segmen (product × warehouse × owner).
    ctx = await entity_ctx(request)
    prefer = payload.owner_entity_id or ("" if getattr(ctx, "view_all", False) else (ctx.active_entity_id or ""))
    owner = await resolve_stock_owner(payload.product_id, session["warehouse_id"], prefer,
                                      allowed_owners=list(ctx.allowed_entity_ids or []))
    bin_id = (payload.bin_id or "").strip()
    # WM-07 — satu count key (produk×pemilik×bin); level gudang & level bin untuk produk sama tidak boleh tumpang tindih
    for it in session.get("items", []):
        if scs.count_key(it) == (payload.product_id, owner, bin_id):
            raise HTTPException(status_code=409, detail="Item dengan produk/pemilik/bin yang sama sudah ada di sesi ini")
        if it.get("product_id") == payload.product_id and it.get("owner_entity_id") == owner \
                and (not it.get("bin_id")) != (not bin_id):
            raise HTTPException(status_code=409, detail=(
                "Produk ini sudah dihitung pada level " + ("gudang" if not it.get("bin_id") else "bin")
                + " — jangan campur hitung level gudang dan per-bin (selisih terhitung dobel)."))
    expected = await scs.scope_qty(payload.product_id, session["warehouse_id"], owner, bin_id)
    item = {
        "id": new_id("cci"),
        "product_id": payload.product_id,
        "sku": product["sku"],
        "product_name": product["name"],
        "bin_id": bin_id,
        "owner_entity_id": owner,
        "expected_qty": expected, "expected_scope": "bin" if bin_id else "warehouse",
        "expected_snapshot_at": now_iso(),
        "actual_qty": None,
        "status": "pending",
        "notes": payload.notes,
        "created_at": now_iso(),
    }
    res = await db.cycle_count_sessions.update_one(   # CAS: count key belum ada (balapan dua add)
        {"id": session_id, "status": "open", "items": {"$not": {"$elemMatch": {
            "product_id": payload.product_id, "owner_entity_id": owner, "bin_id": bin_id}}}},
        {"$push": {"items": item}, "$set": {"updated_at": now_iso()}}
    )
    if res.modified_count != 1:
        raise HTTPException(status_code=409, detail="Item dengan produk/pemilik/bin yang sama sudah ada di sesi ini")
    return item


@router.patch("/cycle-count/sessions/{session_id}/items/{item_id}")
async def update_item(
    session_id: str, item_id: str, payload: CycleCountItemUpdate, request: Request
) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "cycle_count")
    session = await _load_session(session_id, request)
    if session["status"] != "open":
        raise HTTPException(status_code=400, detail="Session tidak ditemukan atau tidak open")
    await db.cycle_count_sessions.update_one(
        {"id": session_id, "items.id": item_id},
        {"$set": {
            "items.$.actual_qty": scs.valid_qty(payload.actual_qty),
            "items.$.notes": payload.notes,
            "items.$.status": "counted",
            "items.$.counted_at": now_iso(),
            "items.$.counted_by": actor["name"],
            "updated_at": now_iso(),
        }}
    )
    session = safe_doc(await db.cycle_count_sessions.find_one({"id": session_id}, {"_id": 0}))
    return session


@router.post("/cycle-count/sessions/{session_id}/submit")
async def submit_session(session_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "cycle_count")
    session = await _load_session(session_id, request)
    if session["status"] != "open":
        raise HTTPException(status_code=400, detail="Session tidak ditemukan atau tidak open")
    _assert_item_owners(session, await entity_ctx(request))
    uncounted = [item for item in session.get("items", []) if item.get("status") != "counted"]
    if uncounted:
        raise HTTPException(status_code=400, detail=f"{len(uncounted)} item belum dihitung")
    discrepancies = []
    for item in session.get("items", []):
        diff = float(item.get("actual_qty", 0) or 0) - float(item.get("expected_qty", 0) or 0)
        if abs(diff) > 0.001:
            discrepancies.append({
                "item_id": item["id"],
                "product_id": item["product_id"],
                "sku": item.get("sku", ""),
                "product_name": item.get("product_name", ""),
                "owner_entity_id": item.get("owner_entity_id", DEFAULT_ENTITY_ID),
                "bin_id": item.get("bin_id") or "",
                "expected_qty": item.get("expected_qty", 0),
                "actual_qty": item.get("actual_qty", 0),
                "difference": round(diff, 4),
            })
    from pymongo import ReturnDocument
    updated = await db.cycle_count_sessions.find_one_and_update(
        {"id": session_id},
        {"$set": {
            "status": "submitted",
            "discrepancies": discrepancies,
            "submitted_by": actor["name"],
            "submitted_at": now_iso(),
            "updated_at": now_iso(),
        }},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    await audit(actor["name"], "cycle_count_submitted", "cycle_count", session_id,
                {"discrepancies_count": len(discrepancies)})
    return safe_doc(updated)


@router.post("/cycle-count/sessions/{session_id}/reopen")
async def reopen_session(session_id: str, request: Request) -> Dict[str, Any]:
    """P18 INV-03 — HITUNG ULANG: sesi submitted/rejected dibuka kembali. Item yang stoknya bergerak
    sejak dihitung mendapat expected (cutoff) baru dan wajib dihitung ulang; item lain tetap."""
    actor = await require_permission(request, "inventory", "approve_count")
    session = await _load_session(session_id, request)
    if session["status"] not in ("submitted", "rejected"):
        raise HTTPException(status_code=400, detail="Hanya sesi yang sudah disubmit/ditolak yang bisa dibuka kembali")
    if any((i.get("adjustment") or {}).get("status") for i in session.get("items", [])):
        raise HTTPException(status_code=409, detail="Sebagian selisih sudah diterapkan — selesaikan persetujuan, jangan dibuka ulang")
    items, recount = [], []
    for item in session.get("items", []):
        live = await scs.scope_qty(item["product_id"], session["warehouse_id"],
                                   item.get("owner_entity_id") or DEFAULT_ENTITY_ID, item.get("bin_id") or "")
        if abs(live - float(item.get("expected_qty", 0) or 0)) > 0.001:
            item = {**item, "expected_qty": live, "expected_snapshot_at": now_iso(), "actual_qty": None,
                    "status": "pending", "recount_no": int(item.get("recount_no") or 0) + 1}
            recount.append(item.get("sku") or item["product_id"])
        items.append(item)
    from pymongo import ReturnDocument
    updated = await db.cycle_count_sessions.find_one_and_update(
        {"id": session_id, "status": session["status"]},
        {"$set": {"status": "open", "items": items, "discrepancies": [], "reopened_by": actor["name"],
                  "reopened_at": now_iso(), "updated_at": now_iso()}, "$unset": {"saga_lock": ""}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(status_code=409, detail="Sesi baru saja berubah — muat ulang")
    await audit(actor["name"], "cycle_count_reopened", "cycle_count", session_id, {"recount": recount})
    return {**safe_doc(updated), "recount_items": recount}



@router.post("/cycle-count/sessions/{session_id}/approve")
async def approve_session(session_id: str, payload: CycleCountApprove, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "approve_count")
    session = await _load_session(session_id, request)
    if session["status"] != "submitted":
        raise HTTPException(status_code=400, detail="Session belum disubmit")
    _assert_item_owners(session, await entity_ctx(request))
    # T-01 Opsi B (INV-ATOMIC-01) — klaim sesi sebelum selisih diterapkan ke roll:
    # dua persetujuan bersamaan tidak boleh menyesuaikan stok dua kali.
    from services import atomic_claim as _saga
    await _saga.claim("cycle_count_sessions", session_id, "cycle_count_approve",
                      precondition={"status": "submitted"}, actor=actor["name"])
    items = {i["id"]: i for i in session.get("items", [])}
    try:
        # KN-B11/WM-07 — expected dibekukan per scope hitung (bin); stok bergerak sejak dihitung → 409.
        drifted = []
        for item in items.values():
            if (item.get("adjustment") or {}).get("status"):
                continue  # baris sudah diterapkan pada percobaan sebelumnya (recovery)
            live = await scs.scope_qty(item["product_id"], session["warehouse_id"],
                                       item.get("owner_entity_id") or DEFAULT_ENTITY_ID, item.get("bin_id") or "")
            if abs(live - float(item.get("expected_qty", 0) or 0)) > 0.001:
                drifted.append(f"{item.get('sku') or item.get('product_id')}{' @' + item['bin_id'] if item.get('bin_id') else ''} ({item.get('expected_qty')}→{live:g})")
        if drifted:
            raise HTTPException(status_code=409, detail=(
                "Stok bergerak sejak dihitung: " + ", ".join(drifted[:5])
                + ". Buka kembali sesi dan hitung ulang item tersebut sebelum disetujui."))
        lines = [(items[d["item_id"]], float(d["difference"])) for d in session.get("discrepancies", [])
                 if abs(float(d["difference"])) >= 0.001 and d["item_id"] in items
                 and not (items[d["item_id"]].get("adjustment") or {}).get("status")]
        await scs.feasibility(session, lines, payload.zero_cost_reason.strip())
    except HTTPException:
        await _saga.release("cycle_count_sessions", session_id)
        raise
    try:
        for item, diff in lines:
            # WM-08/FN-14 — per baris: CAS roll, jurnal selisih, requested/applied tersimpan durable per baris
            adj = await scs.apply_line(session, item, diff, actor["name"], payload.zero_cost_reason.strip())
            await db.cycle_count_sessions.update_one({"id": session_id, "items.id": item["id"]},
                                                     {"$set": {"items.$.adjustment": adj}})
    except Exception as e:
        await _saga.mark_failed("cycle_count_sessions", session_id, str(e))
        raise
    done = await db.cycle_count_sessions.find_one({"id": session_id}, {"_id": 0, "items": 1})
    unresolved = [{"item_id": i["id"], "sku": i.get("sku"), "unresolved": i["adjustment"]["unresolved"]}
                  for i in done.get("items", []) if (i.get("adjustment") or {}).get("status") == "exception"]
    from pymongo import ReturnDocument
    updated = await db.cycle_count_sessions.find_one_and_update(
        {"id": session_id},
        _saga.finish_set({
            # WM-08 — selisih yang tak terterapkan = exception, bukan "approved" palsu
            "status": "approved_with_exceptions" if unresolved else "approved",
            "exceptions": unresolved, "zero_cost_reason": payload.zero_cost_reason.strip(),
            "approved_by": actor["name"],
            "approved_at": now_iso(),
            "approval_reason": payload.reason,
            "updated_at": now_iso(),
        }),
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    await audit(actor["name"], "cycle_count_approved", "cycle_count", session_id,
                {"reason": payload.reason, "exceptions": unresolved})
    return safe_doc(updated)


@router.post("/cycle-count/sessions/{session_id}/reject")
async def reject_session(session_id: str, payload: CycleCountReject, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "approve_count")
    session = await _load_session(session_id, request)
    if session["status"] != "submitted":
        raise HTTPException(status_code=400, detail="Session belum disubmit")
    from pymongo import ReturnDocument
    # W2-007 — reject berkompetisi pada transisi yang sama dgn approve: submitted & tanpa saga_lock.
    updated = await db.cycle_count_sessions.find_one_and_update(
        {"id": session_id, "status": "submitted", "saga_lock": {"$exists": False}},
        {"$set": {
            "status": "rejected",
            "rejected_by": actor["name"],
            "rejected_at": now_iso(),
            "rejection_reason": payload.reason,
            "updated_at": now_iso(),
        }},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    if not updated:
        raise HTTPException(status_code=409, detail="Sesi baru saja diputuskan/sedang disetujui proses lain — muat ulang.")
    await audit(actor["name"], "cycle_count_rejected", "cycle_count", session_id, {"reason": payload.reason})
    return safe_doc(updated)


# ═══ L10 LN-101 — opname per roll (snapshot scope node → scan → rekonsiliasi → finalisasi) ═══
class RollScopePayload(BaseModel):
    node_id: str = ""


class RollScanPayload(BaseModel):
    code: str
    bin_id: str
    measured_qty: Any = None
    tag: str = "ok"
    note: str = ""


class FoundRollSpec(BaseModel):
    scan_id: str
    product_id: str
    owner_entity_id: str
    qty: Any = None


class RollFinalizePayload(BaseModel):
    reason: str
    new_rolls: List[FoundRollSpec] = []
    zero_cost_reason: str = ""


class MissingRecountPayload(BaseModel):
    roll_id: str
    note: str = ""


def _owners(ctx) -> Any:
    return None if getattr(ctx, "view_all", False) else list(ctx.allowed_entity_ids or [])


@router.post("/cycle-count/sessions/{session_id}/roll-scope")
async def set_roll_scope(session_id: str, payload: RollScopePayload, request: Request) -> Dict[str, Any]:
    from services import stock_count_roll_service as rcs
    actor = await require_permission(request, "inventory", "cycle_count")
    session = await _load_session(session_id, request)
    if session["status"] != "open":
        raise HTTPException(status_code=400, detail="Sesi tidak open")
    if (session.get("roll_count") or {}).get("scans"):
        raise HTTPException(status_code=409, detail="Snapshot sudah dipakai untuk scan — buat sesi baru untuk scope lain.")
    rc = await rcs.make_snapshot(session, payload.node_id.strip(), _owners(await entity_ctx(request)))
    res = await db.cycle_count_sessions.update_one(
        {"id": session_id, "status": "open", "roll_count.scans.0": {"$exists": False}},
        {"$set": {"roll_count": rc, "mode": "roll", "updated_at": now_iso()}})
    if res.modified_count != 1:
        raise HTTPException(status_code=409, detail="Sesi baru saja berubah — muat ulang")
    await audit(actor["name"], "cycle_count_roll_snapshot", "cycle_count", session_id,
                {"node_id": rc["node_id"], "expected": len(rc["expected"])})
    return await rcs.reconcile({**session, "roll_count": rc})


@router.post("/cycle-count/sessions/{session_id}/roll-scans")
async def add_roll_scan(session_id: str, payload: RollScanPayload, request: Request) -> Dict[str, Any]:
    from services import stock_count_roll_service as rcs
    actor = await require_permission(request, "inventory", "cycle_count")
    session = await _load_session(session_id, request)
    rc = session.get("roll_count")
    if session["status"] != "open" or not rc:
        raise HTTPException(status_code=400, detail="Pilih scope & snapshot opname per roll dulu (sesi harus open)")
    if payload.tag not in rcs.TAGS:
        raise HTTPException(status_code=400, detail="Kondisi tag harus ok / damaged / unreadable")
    if payload.bin_id not in rc["bin_ids"]:
        raise HTTPException(status_code=400, detail="Bin yang discan di luar scope opname ini")
    measured = None if payload.measured_qty in (None, "") else scs.valid_qty(payload.measured_qty)
    roll = await rcs.find_roll(payload.code)
    allowed = _owners(await entity_ctx(request))
    if roll and allowed is not None and roll.get("owner_entity_id") not in allowed:
        roll = {"id": roll["id"]}   # roll entitas lain = roll asing; detailnya tidak dibuka
    rid = (roll or {}).get("id", "")
    prev = next((s for s in rc["scans"] if (rid and s.get("roll_id") == rid)
                 or (not rid and not s.get("roll_id") and s.get("code") == payload.code.strip())), None)
    if prev and (prev.get("adjustment") or {}).get("status") != "recount":
        await db.cycle_count_sessions.update_one({"id": session_id}, {"$inc": {"roll_count.duplicates": 1}})
        return {"duplicate": True, "scan": prev, "message": "Roll ini sudah discan — scan ganda tidak menambah stok."}
    scan = {"id": prev["id"] if prev else new_id("ccs"), "code": payload.code.strip(), "roll_id": rid,
            "roll_no": (roll or {}).get("roll_no", ""), "product_id": (roll or {}).get("product_id", ""),
            "owner_entity_id": (roll or {}).get("owner_entity_id", ""), "bin_id": payload.bin_id,
            "measured_qty": measured, "tag": payload.tag, "note": payload.note,
            "live_qty": float((roll or {}).get("length_remaining") or 0), "live_bin_id": (roll or {}).get("bin_id"),
            "live_warehouse_id": (roll or {}).get("warehouse_id"), "live_status": (roll or {}).get("status"),
            "unit": (roll or {}).get("unit", ""), "at": now_iso(), "by": actor["name"]}
    if prev:   # hitung ulang baris 'recount' — ganti, bukan tambah
        res = await db.cycle_count_sessions.update_one(
            {"id": session_id, "status": "open", "roll_count.scans": {"$elemMatch": {"id": prev["id"], "adjustment.status": "recount"}}},
            {"$set": {"roll_count.scans.$": scan, "updated_at": now_iso()}})
    else:      # CAS: roll/kode belum ada (dua scan bersamaan → satu baris)
        dup_q = {"roll_id": rid} if rid else {"roll_id": "", "code": scan["code"]}
        res = await db.cycle_count_sessions.update_one(
            {"id": session_id, "status": "open", "roll_count.scans": {"$not": {"$elemMatch": dup_q}}},
            {"$push": {"roll_count.scans": scan}, "$set": {"updated_at": now_iso()}})
    if res.modified_count != 1:
        await db.cycle_count_sessions.update_one({"id": session_id}, {"$inc": {"roll_count.duplicates": 1}})
        return {"duplicate": True, "message": "Roll ini sudah discan — scan ganda tidak menambah stok."}
    return {"duplicate": False, "scan": {**scan, "kinds": rcs.classify_scan(rc, scan, session["warehouse_id"])}}


@router.get("/cycle-count/sessions/{session_id}/roll-reconcile")
async def roll_reconcile(session_id: str, request: Request) -> Dict[str, Any]:
    from services import stock_count_roll_service as rcs
    await require_permission(request, "inventory", "cycle_count")
    return await rcs.reconcile(await _load_session(session_id, request))


@router.post("/cycle-count/sessions/{session_id}/roll-missing-recount")
async def roll_missing_recount(session_id: str, payload: MissingRecountPayload, request: Request) -> Dict[str, Any]:
    """OPS-01 — hitung ulang roll hilang: dicari lagi & tetap tidak ada. Bila ketemu, scan saja (bukan endpoint ini)."""
    from services import stock_count_roll_service as rcs
    actor = await require_permission(request, "inventory", "cycle_count")
    session = await _load_session(session_id, request)
    if session["status"] != "open" or not session.get("roll_count"):
        raise HTTPException(status_code=400, detail="Sesi opname per roll tidak open")
    rec = await rcs.reconcile(session)
    if payload.roll_id not in {m["roll_id"] for m in rec["missing"]}:
        raise HTTPException(status_code=400, detail="Roll ini tidak berstatus hilang pada sesi ini")
    entry = {"by": actor["name"], "at": now_iso(), "note": payload.note.strip()}
    await db.cycle_count_sessions.update_one({"id": session_id, "status": "open"},
                                             {"$set": {f"roll_count.missing_recounts.{payload.roll_id}": entry, "updated_at": now_iso()}})
    await audit(actor["name"], "cycle_count_missing_recount", "cycle_count", session_id, {"roll_id": payload.roll_id})
    return await rcs.reconcile(await db.cycle_count_sessions.find_one({"id": session_id}, {"_id": 0}))


@router.post("/cycle-count/sessions/{session_id}/roll-finalize")
async def roll_finalize(session_id: str, payload: RollFinalizePayload, request: Request) -> Dict[str, Any]:
    """Wewenang ACC (inventory.approve_count). SOP OPS-01: salah alamat/asing → pindah alamat, qty beda → koreksi,
    hilang yang sudah dihitung ulang → dihapus, kode tak dikenal + spesifikasi → roll baru. Idempoten per baris."""
    from services import stock_count_roll_service as rcs
    from services import atomic_claim as _saga
    actor = await require_permission(request, "inventory", "approve_count")
    if len(payload.reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="Alasan finalisasi minimal 5 karakter")
    session = await _load_session(session_id, request)
    if session["status"] != "open" or not session.get("roll_count"):
        raise HTTPException(status_code=400, detail="Sesi opname per roll tidak open")
    rec = await rcs.reconcile(session)
    done_ok = lambda x: (x.get("adjustment") or {}).get("status") == "applied"  # noqa: E731
    todo = [ln for ln in rec["lines"] if rcs.APPLY_KINDS & set(ln["kinds"]) and not done_ok(ln)]
    lost = [m for m in rec["missing"] if m.get("recount") and not done_ok(m)]
    specs = {x.scan_id: x for x in payload.new_rolls}
    unknown = [ln for ln in rec["lines"] if "unknown" in ln["kinds"] and not done_ok(ln)]
    found = [(ln, specs[ln["id"]]) for ln in unknown if ln["id"] in specs]
    stray = sorted(set(specs) - {ln["id"] for ln in unknown})
    if stray:
        raise HTTPException(status_code=400, detail="Spesifikasi roll baru hanya untuk baris kode tak dikenal yang belum diterapkan")
    allowed = _owners(await entity_ctx(request))
    owners = {ln["owner_entity_id"] for ln in todo if ln.get("owner_entity_id")} | {m["owner_entity_id"] for m in lost} \
        | {sp.owner_entity_id for _, sp in found}
    foreign = sorted(owners - set(allowed)) if allowed is not None else []
    if foreign:
        raise HTTPException(status_code=403, detail="Selisih menyentuh stok badan usaha di luar akses Anda: " + ", ".join(foreign))
    for ln, sp in found:
        if not await db.products.find_one({"id": sp.product_id}, {"_id": 0, "id": 1}):
            raise HTTPException(status_code=400, detail=f"Produk untuk kode {ln['code']} tidak ditemukan")
        q = sp.qty if sp.qty not in (None, "") else ln.get("measured_qty")
        if q in (None, "") or scs.valid_qty(q) <= 0:
            raise HTTPException(status_code=400, detail=f"Qty fisik untuk kode {ln['code']} wajib > 0")
        cost, _ = await scs.surplus_unit_cost(sp.product_id, session["warehouse_id"], sp.owner_entity_id)
        if cost <= 0 and not payload.zero_cost_reason.strip():
            raise HTTPException(status_code=400, detail=f"Kode {ln['code']}: produk tanpa biaya acuan — isi alasan biaya nol")
    await _saga.claim("cycle_count_sessions", session_id, "cycle_count_roll_finalize",
                      precondition={"status": "open"}, actor=actor["name"])
    recount, blocked, held = [], 0, 0
    try:
        for ln in todo:
            adj = await rcs.apply_scan(session, ln, ln["kinds"], actor["name"])
            await db.cycle_count_sessions.update_one({"id": session_id, "roll_count.scans.id": ln["id"]},
                                                     {"$set": {"roll_count.scans.$.adjustment": adj}})
            if adj["status"] == "recount":
                recount.append(ln.get("roll_no") or ln["code"])
            blocked += adj["status"] == "exception"
        for m in lost:
            adj = await rcs.write_off_missing(session, m, actor["name"])
            if adj["status"] == "applied":
                await db.cycle_count_sessions.update_one({"id": session_id},
                                                         {"$set": {f"roll_count.missing_adjustments.{m['roll_id']}": adj}})
            elif adj["status"] == "exception":
                held += 1
            else:
                recount.append(m.get("roll_no") or m["roll_id"])
        for ln, sp in found:
            adj = await rcs.create_found_roll(session, ln, sp.model_dump(), actor["name"], payload.zero_cost_reason.strip())
            await db.cycle_count_sessions.update_one({"id": session_id, "roll_count.scans.id": ln["id"]},
                                                     {"$set": {"roll_count.scans.$.adjustment": adj}})
            blocked += adj["status"] == "exception"
    except Exception as e:
        await _saga.mark_failed("cycle_count_sessions", session_id, str(e))
        raise
    if recount:
        await _saga.release("cycle_count_sessions", session_id)
        out = await rcs.reconcile(await db.cycle_count_sessions.find_one({"id": session_id}, {"_id": 0}))
        return {**out, "status": "open", "recount": recount,
                "message": f"{len(recount)} roll berubah sesudah dihitung — scan ulang lalu finalisasi lagi."}
    c = rec["counts"]
    exceptions = {"missing_unconfirmed": len([m for m in rec["missing"] if not m.get("recount")]),
                  "unknown_unresolved": len(unknown) - len(found), "relocation_blocked": blocked, "missing_allocated": held,
                  "tag_followup": c.get("tag_damaged", 0) + c.get("unreadable", 0)}
    exceptions = {k: v for k, v in exceptions.items() if v}
    await db.cycle_count_sessions.update_one({"id": session_id}, _saga.finish_set({
        "status": "approved_with_exceptions" if exceptions else "approved", "roll_exceptions": exceptions,
        "approved_by": actor["name"], "approved_at": now_iso(), "approval_reason": payload.reason.strip(),
        "zero_cost_reason": payload.zero_cost_reason.strip(), "updated_at": now_iso()}))
    await audit(actor["name"], "cycle_count_roll_finalized", "cycle_count", session_id,
                {"applied": len(todo), "written_off": len(lost), "found": len(found), "exceptions": exceptions,
                 "reason": payload.reason.strip()})
    done = await db.cycle_count_sessions.find_one({"id": session_id}, {"_id": 0})
    return {**await rcs.reconcile(done), "status": done["status"], "recount": []}

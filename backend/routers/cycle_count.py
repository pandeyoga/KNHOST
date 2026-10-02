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
    owner = await resolve_stock_owner(payload.product_id, session["warehouse_id"], prefer)
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


@router.post("/cycle-count/sessions/{session_id}/approve")
async def approve_session(session_id: str, payload: CycleCountApprove, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inventory", "approve_count")
    session = await _load_session(session_id, request)
    if session["status"] != "submitted":
        raise HTTPException(status_code=400, detail="Session belum disubmit")
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
    updated = await db.cycle_count_sessions.find_one_and_update(
        {"id": session_id},
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
    await audit(actor["name"], "cycle_count_rejected", "cycle_count", session_id, {"reason": payload.reason})
    return safe_doc(updated)

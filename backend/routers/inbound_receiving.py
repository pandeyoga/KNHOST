"""Inbound Receiving router: scan-based receiving with escalation."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request, Body
from pymongo import ReturnDocument
from db import db
# FASE U — `qty_rolls` di sini DIHITUNG dari roll yang benar-benar lahir (lihat
# `scan-receive`: `qty_rolls = qty_rolls + _rolls_made`), bukan dari helper konversi,
# jadi `dual_qty_service` tidak dipakai router ini (importnya dulu menggantung).
from dependencies import require_permission, audit, has_permission
from entity_scope import entity_ctx, resolve_list_scope, assert_entity_access
from core_utils import new_id, now_iso, safe_doc
from schemas import POReceiveItem, GRCompletePayload
from services.inbound_complete_service import complete_task, grade_or_400 as _grade_or_400

router = APIRouter(prefix="/api")


@router.get("/inbound/tasks")
async def list_inbound_tasks(request: Request, status: str = None) -> List[Dict[str, Any]]:
    """List all inbound receiving tasks, optionally filtered by status."""
    await require_permission(request, "wms", "view")
    ctx = await entity_ctx(request)
    
    query = {"flow_type": "inbound", "source_type": "purchase_order"}
    if status:
        query["status"] = status
    query = resolve_list_scope("wms_tasks", query, ctx)
    
    tasks = await db.wms_tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    
    # Enrich with PO info
    po_ids = list(set(t.get("po_id") for t in tasks if t.get("po_id")))
    pos = {p["id"]: p for p in await db.purchase_orders.find({"id": {"$in": po_ids}}, {"_id": 0}).to_list(100)}
    
    for task in tasks:
        if task.get("po_id"):
            po = pos.get(task["po_id"], {})
            task["supplier_name"] = po.get("supplier_name", "")
    
    return tasks


@router.post("/inbound/tasks/{task_id}/scan-receive")
async def scan_receive_item(
    task_id: str,
    payload: POReceiveItem,
    request: Request
) -> Dict[str, Any]:
    """
    Scan and receive item for inbound task.
    
    Updates received_qty and tracks batch/lot/roll/bin.
    If received_qty reaches expected_qty, auto-advance to next stage.
    """
    actor = await require_permission(request, "wms", "update")
    
    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Inbound task tidak ditemukan")
    # INV-ENTITY-01 (KN-076-IDOR-WRITE-INBOUND P1): cegah mutasi task lintas-entitas.
    assert_entity_access(task, "wms_tasks", await entity_ctx(request))
    
    if task.get("flow_type") != "inbound":
        raise HTTPException(status_code=400, detail="Task ini bukan inbound task")
    
    if task["status"] in ["completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Task sudah selesai atau dibatalkan")
    from services.goods_receipt_service import guard_legacy_receiving
    await guard_legacy_receiving(task)
    
    # Validate product match
    if payload.product_id != task["product_id"]:
        raise HTTPException(status_code=400, detail="Product ID tidak sesuai dengan task")

    # ── FASE F-1 (F1-01/F1-02/F1-03) — qty boleh dalam SATUAN SUPPLIER ──────
    # Bila operator mengirim `doc_uom` + `doc_qty` (apa adanya dari surat jalan supplier),
    # server yang mengonversi ke satuan task memakai prioritas: satuan sama → barang
    # supplier (conv_factor) → registry konversi global. Jejak konversi WAJIB disimpan
    # (D-07). `preflight_scan` sekaligus menegakkan toleransi kedatangan Fase 3.
    from services import receiving_uom_service as _rus
    payload.grade = _grade_or_400(payload.grade, "")
    try:
        _pf = await _rus.preflight_scan(task, payload,
                                        can_override=await has_permission(actor, "wms", "approve"))
    except _rus.ReceivingUomError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    effective_qty, _ruom_trail = _pf["qty"], _pf["trail"]
    new_received_qty, expected_qty = _pf["new_received"], _pf["expected_qty"]
    tol_pct, variance_pct = _pf["tolerance_pct"], _pf["variance_pct"]
    within_tolerance = _pf["within_tolerance"]
    
    # Log scan entry
    scan_entry = {
        "id": new_id("scan"),
        "scan_type": "receive",
        "actual_qty": effective_qty,
        "batch": payload.batch,
        "lot": payload.lot,
        "roll_id": payload.roll_id,
        "bin_id": payload.bin_id,
        "actor": actor["name"],
        "timestamp": now_iso(),
        **({"over_override_reason": _pf["override_reason"]} if _pf.get("override_reason") else {}),
        # FASE F-1 — jejak konversi satuan supplier (kosong bila input satuan KN)
        **({"uom_trail": _ruom_trail} if _ruom_trail else {}),
    }
    
    update_data = {
        "received_qty": new_received_qty,
        "receive_variance_percent": variance_pct,
        "receive_within_tolerance": within_tolerance,
        "receive_tolerance_percent": tol_pct,
        # FASE G-0 — bila kebijakan `receiving.block_over_remaining` dimatikan, penerimaan
        # melebihi PO TETAP diterima namun DITANDAI agar bisa ditindaklanjuti (bukan senyap).
        "over_receipt": bool(_pf.get("over_receipt")),
        "over_receipt_note": _pf.get("over_message", ""),
        "batch": payload.batch or task.get("batch", ""),
        "lot": payload.lot or task.get("lot", ""),
        "dye_lot": payload.dye_lot or task.get("dye_lot", ""),
        "grade": payload.grade or task.get("grade", ""),
        "roll_id": payload.roll_id or task.get("roll_id", ""),
        "bin_id": payload.bin_id or task.get("bin_id", ""),
        "updated_at": now_iso()
    }
    if _ruom_trail:
        # Satuan terakhir yang dipakai operator → dipakai UI untuk mengingat pilihan.
        update_data["last_receive_doc_uom"] = _ruom_trail["doc_uom"]
    
    # If received qty matches expected, auto-advance to receiving status
    if task["status"] == "waiting_goods" and new_received_qty > 0:
        update_data["status"] = "receiving"
    
    # If fully received, mark as ready for QC
    if new_received_qty >= expected_qty:
        update_data["status"] = "qc_check"
        update_data["quantity"] = new_received_qty  # Set final quantity
    
    _push: Dict[str, Any] = {"scan_log": scan_entry}
    if _ruom_trail:
        _push["receive_uom_trails"] = {**_ruom_trail, "scan_id": scan_entry["id"],
                                       "actor": actor["name"]}
    updated_task = await db.wms_tasks.find_one_and_update(
        {"id": task_id},
        {
            "$set": update_data,
            "$push": _push
        },
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    
    await audit(actor["name"], "inbound_scan_receive", "wms_task", task_id, {
        "actual_qty": effective_qty,
        "received_qty": new_received_qty,
        "expected_qty": expected_qty,
        **({"doc_uom": _ruom_trail["doc_uom"], "doc_qty": _ruom_trail["doc_qty"],
            "uom_source": _ruom_trail["source"], "factor": _ruom_trail["factor"]}
           if _ruom_trail else {}),
    })
    
    return safe_doc(updated_task)


@router.post("/inbound/tasks/{task_id}/escalate")
async def escalate_inbound_task(
    task_id: str,
    request: Request,
    reason: str = "Qty tidak sesuai dengan PO"
) -> Dict[str, Any]:
    """
    Escalate inbound task to manager due to qty mismatch or other issues.
    
    Manager can then adjust expected_qty or investigate issue.
    """
    actor = await require_permission(request, "wms", "update")
    
    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Inbound task tidak ditemukan")
    # INV-ENTITY-01 (KN-076-IDOR-WRITE-INBOUND P1): cegah mutasi task lintas-entitas.
    assert_entity_access(task, "wms_tasks", await entity_ctx(request))
    
    escalation = {
        "escalated_by": actor["name"],
        "escalated_at": now_iso(),
        "reason": reason,
        "status": "pending_review",
        "resolved_by": None,
        "resolved_at": None,
        "resolution_notes": ""
    }
    
    # KN-C01 — eskalasi berprasyarat status: tugas yang sudah selesai/dibatalkan/sedang
    # dieskalasi TIDAK boleh dibuka kembali (dulu putaran complete→escalate→resolve→complete
    # bisa diulang dan tiap putaran melahirkan set roll baru + menaikkan received_qty PO).
    updated_task = await db.wms_tasks.find_one_and_update(
        {"id": task_id, "status": {"$nin": ["completed", "cancelled", "escalated"]}},
        {
            "$set": {
                "escalation": escalation,
                "status": "escalated",
                "updated_at": now_iso()
            }
        },
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    if not updated_task:
        raise HTTPException(status_code=409, detail=(
            f"Tugas berstatus '{task.get('status')}' tidak bisa dieskalasi (sudah selesai/dibatalkan/sedang dieskalasi)."))
    
    await audit(actor["name"], "inbound_escalated", "wms_task", task_id, {
        "reason": reason,
        "received_qty": task.get("received_qty", 0),
        "expected_qty": task.get("expected_qty", 0)
    })
    
    return safe_doc(updated_task)


@router.post("/inbound/tasks/{task_id}/resolve-escalation")
async def resolve_escalation(
    task_id: str,
    request: Request,
    adjusted_qty: float = None,
    resolution_notes: str = ""
) -> Dict[str, Any]:
    """
    Resolve escalated inbound task (manager only).
    
    Manager can adjust expected_qty to match actual received qty.
    """
    actor = await require_permission(request, "wms", "approve")  # Manager permission
    
    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Inbound task tidak ditemukan")
    # INV-ENTITY-01 (KN-076-IDOR-WRITE-INBOUND P1): cegah mutasi task lintas-entitas.
    assert_entity_access(task, "wms_tasks", await entity_ctx(request))
    
    if not task.get("escalation"):
        raise HTTPException(status_code=400, detail="Task tidak dalam status escalation")
    if task["escalation"].get("status") == "resolved":
        raise HTTPException(
            status_code=409,
            detail="Eskalasi sudah diselesaikan pihak lain. Muat ulang layar.")
    
    escalation = task["escalation"]
    escalation["status"] = "resolved"
    escalation["resolved_by"] = actor["name"]
    escalation["resolved_at"] = now_iso()
    escalation["resolution_notes"] = resolution_notes
    
    update_data = {
        "escalation": escalation,
        "status": "qc_check",  # Move to QC after resolution
        "updated_at": now_iso()
    }
    
    # If manager adjusts qty, update expected and final quantity
    if adjusted_qty is not None:
        update_data["expected_qty"] = adjusted_qty
        update_data["quantity"] = task.get("received_qty", 0.0)
    
    # T-01 (pola CAS, sama dengan outbound) — tulisan berprasyarat eskalasi BELUM resolved:
    # dua manajer yang menekan "selesaikan" bersamaan → tepat satu 200, sisanya 409.
    updated_task = await db.wms_tasks.find_one_and_update(
        {"id": task_id, "status": "escalated",   # KN-C01 — hanya tugas yang memang tereskalasi
         "escalation.status": {"$ne": "resolved"},
         "escalation": {"$exists": True}},
        {"$set": update_data},
        projection={"_id": 0},
        return_document=ReturnDocument.AFTER
    )
    if not updated_task:
        raise HTTPException(
            status_code=409,
            detail="Eskalasi sudah diselesaikan pihak lain. Muat ulang layar.")
    
    await audit(actor["name"], "inbound_escalation_resolved", "wms_task", task_id, {
        "adjusted_qty": adjusted_qty,
        "resolution_notes": resolution_notes
    })
    
    return safe_doc(updated_task)


@router.post("/inbound/tasks/{task_id}/complete")
async def complete_inbound_receiving(
    task_id: str,
    request: Request,
    payload: Optional[GRCompletePayload] = Body(default=None),
) -> Dict[str, Any]:
    """Selesaikan penerimaan → stok/HPP/jurnal. Logika di `services/inbound_complete_service.complete_task`."""
    actor = await require_permission(request, "wms", "update")
    from services.goods_receipt_service import guard_legacy_receiving
    await guard_legacy_receiving(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}) or {})
    return await complete_task(task_id, payload, actor, ctx=await entity_ctx(request))

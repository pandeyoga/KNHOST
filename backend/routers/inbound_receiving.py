"""Inbound Receiving router: scan-based receiving with escalation."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request, Body
from pymongo import ReturnDocument
from db import db
# FASE U — `qty_rolls` di sini DIHITUNG dari roll yang benar-benar lahir (lihat
# `scan-receive`: `qty_rolls = qty_rolls + _rolls_made`), bukan dari helper konversi,
# jadi `dual_qty_service` tidak dipakai router ini (importnya dulu menggantung).
from dependencies import require_permission, audit, has_permission
from entity_scope import entity_ctx, resolve_work_scope, assert_entity_access
from core_utils import new_id, now_iso, safe_doc
from schemas import POReceiveItem, GRCompletePayload
from services.inbound_complete_service import complete_task, grade_or_400 as _grade_or_400
from services import inbound_task_state as _its
from input_rules import KNIn, require_qty, require_reason, optional_reason

router = APIRouter(prefix="/api")


async def _resolve_task_bin(task: Dict[str, Any], ref: Any) -> Optional[Dict[str, str]]:
    from services.inbound_complete_service import resolve_task_bin
    return await resolve_task_bin(task, ref)


class EscalateIn(KNIn):
    """FIX-3a (B3b FRM-09 #1, G-API-02) — alasan eskalasi lewat body (query lama tetap diterima)."""
    reason: str = ""


@router.get("/inbound/tasks")
async def list_inbound_tasks(request: Request, status: str = None, entity_id: str = None,
                             limit: int = 200, skip: int = 0) -> Any:
    """List all inbound receiving tasks, optionally filtered by status.

    FIX-7 (B3b LST-01) — `skip`/`limit` (bawaan 200 = batas lama, maks 500) + jumlah sungguhan di header
    `X-Total-Count`/`X-Truncated` (dulu terpotong 200 diam-diam); nama supplier dari SEMUA PO tugas yang tampil
    (dulu PO dipotong 100 → nama supplier kosong). Array tetap (kompatibel)."""
    await require_permission(request, "wms", "view")
    ctx = await entity_ctx(request)
    
    query = {"flow_type": "inbound", "source_type": "purchase_order"}
    if status:
        query["status"] = status
    # FIX-1 (K-B1-02, B2a FLW-IN-07) — tugas terima per GEDUNG dalam lokasi kerja, lintas PT yang ditugaskan.
    query = await resolve_work_scope("wms_tasks", query, ctx, entity_id)
    
    from pagination import clamp_limit, window_meta, window_headers
    lim, sk = clamp_limit(limit, 200, 500), clamp_limit(skip, 0, 10 ** 7, minimum=0)
    total = await db.wms_tasks.count_documents(query)
    tasks = await (db.wms_tasks.find(query, {"_id": 0}).sort("created_at", -1)
                   .skip(sk).limit(lim).to_list(lim))

    # Enrich with PO info
    po_ids = list(set(t.get("po_id") for t in tasks if t.get("po_id")))
    pos = {p["id"]: p for p in await db.purchase_orders.find({"id": {"$in": po_ids}},
                                                              {"_id": 0, "id": 1, "supplier_name": 1}).to_list(len(po_ids) or 1)}
    
    for task in tasks:
        if task.get("po_id"):
            po = pos.get(task["po_id"], {})
            task["supplier_name"] = po.get("supplier_name", "")
    from services.work_labels import label_rows
    await label_rows(tasks)
    from fastapi.encoders import jsonable_encoder
    from starlette.responses import JSONResponse
    return JSONResponse(jsonable_encoder(tasks), headers=window_headers(window_meta(total, len(tasks), sk, lim)))


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
    
    # FIX-3a (B2a FLW-IN-01/06) — DAFTAR-IZIN status asal: tugas yang sudah diputus QC (`qc_pending`/`qc_rejected`),
    # selesai, batal, atau sedang dieskalasi TIDAK bisa menerima barang lagi (dulu daftar-larang completed/cancelled).
    _its.assert_can(task, "scan_receive")
    from services.goods_receipt_service import guard_legacy_receiving
    await guard_legacy_receiving(task)
    
    # Validate product match
    if payload.product_id != task["product_id"]:
        raise HTTPException(status_code=400, detail="Product ID tidak sesuai dengan task")
    # FIX-3a (B3b INP-01, B2a FLW-IN-08/OPN-01) — bin = rujukan struktur gudang tugas (id ATAU kode rak), bukan teks
    # bebas; disimpan sebagai id kanonik. Bin di area yang dibekukan pendaftaran awal ditolak 409.
    _bin = await _resolve_task_bin(task, payload.bin_id)

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
        "bin_id": _bin["id"] if _bin else "",
        **({"bin_code": _bin["code"]} if _bin else {}),
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
        "bin_id": (_bin["id"] if _bin else "") or task.get("bin_id", ""),
        **({"bin_code": _bin["code"]} if _bin else {}),
    }
    if _ruom_trail:
        # Satuan terakhir yang dipakai operator → dipakai UI untuk mengingat pilihan.
        update_data["last_receive_doc_uom"] = _ruom_trail["doc_uom"]
    
    # If received qty matches expected, auto-advance to receiving status
    new_status = task["status"]
    if task["status"] == "waiting_goods" and new_received_qty > 0:
        new_status = "receiving"
    
    # If fully received, mark as ready for QC
    if new_received_qty >= expected_qty:
        new_status = "qc_check"
        update_data["quantity"] = new_received_qty  # Set final quantity
    
    _push: Dict[str, Any] = {"scan_log": scan_entry}
    if _ruom_trail:
        _push["receive_uom_trails"] = {**_ruom_trail, "scan_id": scan_entry["id"],
                                       "actor": actor["name"]}
    # FIX-3a (B2a STM-IN-06) — CAS: status asal yang dibaca + `received_qty` yang dibaca. Dua pindai bersamaan tidak
    # lagi saling menimpa jumlah diterima; yang kalah mendapat 409 dan mengulang.
    updated_task = await _its.transition(
        task_id, "scan_receive", new_status, actor_name=actor["name"], set_fields=update_data, push=_push,
        from_status=[task["status"]], extra_filter={"received_qty": task.get("received_qty")},
        prev_status=task["status"])
    if not updated_task:
        raise HTTPException(status_code=409, detail=(
            "Tugas ini baru saja berubah (penerimaan lain/eskalasi/keputusan QC) — muat ulang lalu ulangi pindai."))
    
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
    reason: str = "",
    payload: Optional[EscalateIn] = Body(default=None),
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
    # FIX-3a (B2a FLW-IN-01) — eskalasi hanya SEBELUM barang diposting: tugas `qc_pending`/`qc_rejected` yang dulu
    # bisa dieskalasi lalu diputus kembali ke `qc_check` membuka "Selesai" ulang (roll ganda). 409 (kontrak KN-C01).
    _its.assert_can(task, "escalate", status_code=409)
    # FIX-3a (K-14 / K-B3b-03) — alasan wajib ≥ 5 HURUF, ditegakkan server (dulu bawaan teks tetap & "x" lolos).
    reason = require_reason((payload.reason if payload and payload.reason else reason), label="Alasan eskalasi")
    # KN-E10 — eskalasi tunduk pada mode GRN & tidak boleh menyentuh tugas yang sedang dihitung GRN.
    from services.goods_receipt_service import guard_legacy_receiving
    await guard_legacy_receiving(task)
    
    escalation = {
        "pre_status": task.get("status"),
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
    updated_task = await _its.transition(
        task_id, "escalate", "escalated", actor_name=actor["name"], set_fields={"escalation": escalation},
        extra_filter={"$or": [{"grn_active_id": {"$exists": False}}, {"grn_active_id": {"$in": [None, ""]}}]},
        note=reason, prev_status=task.get("status"))
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
    # FIX-3a (B3b INP-09) — qty pesanan baru wajib angka > 0 (dulu -10 tersimpan → tugas macet "melebihi toleransi");
    # (FRM-09 #2) catatan penyelesaian wajib ≥ 5 huruf.
    if adjusted_qty is not None:
        adjusted_qty = require_qty(adjusted_qty, label="Qty pesanan yang disesuaikan", max_value=10_000_000)
    resolution_notes = require_reason(resolution_notes, label="Catatan penyelesaian eskalasi")
    
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
    
    # KN-E10 — tugas tanpa barang diterima (mis. waiting_goods) kembali ke status asalnya, bukan
    # qc_check: qc_check membuka scan-receive/complete jalur lama di luar GRN.
    no_goods = float(task.get("received_qty") or 0) <= 0
    _pre = escalation.get("pre_status") or "waiting_goods"
    update_data = {
        "escalation": escalation,
        "status": _pre if no_goods else "qc_check",
        "updated_at": now_iso()
    }
    if update_data["status"] in ("escalated", "put_away"):
        update_data["status"] = "waiting_goods" if no_goods else "qc_check"
    if _pre in _its.POSTED:
        # FIX-3a (B2a FLW-IN-01) — data lama: eskalasi dari tugas yang barangnya SUDAH diposting (karantina/QC)
        # dikembalikan ke status itu, TIDAK ke `qc_check` (yang membuka "Selesai" ulang → roll ganda).
        update_data["status"] = _pre
    
    # If manager adjusts qty, update expected and final quantity
    if adjusted_qty is not None:
        update_data["expected_qty"] = adjusted_qty
        update_data["quantity"] = task.get("received_qty", 0.0)
    
    # T-01 (pola CAS, sama dengan outbound) — tulisan berprasyarat eskalasi BELUM resolved:
    # dua manajer yang menekan "selesaikan" bersamaan → tepat satu 200, sisanya 409.
    _to = update_data.pop("status")
    updated_task = await _its.transition(   # KN-C01 — hanya tugas yang memang tereskalasi (CAS `escalated`)
        task_id, "resolve_escalation", _to, actor_name=actor["name"], set_fields=update_data,
        extra_filter={"escalation.status": {"$ne": "resolved"}, "escalation": {"$exists": True}},
        note=resolution_notes, prev_status="escalated")
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

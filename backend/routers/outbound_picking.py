"""Outbound Picking router: scan-based picking with multi-warehouse support & escalation."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from db import db
from dependencies import require_permission, audit
from entity_scope import entity_ctx, resolve_work_scope, assert_entity_access
from core_utils import new_id, now_iso, safe_doc
from services.shipment_service import dispatch_task
from services.fulfillment_status import recompute_so_status
from services import outbound_task_state as _ots   # FIX-3b — tabel transisi tugas ambil (daftar-izin + CAS)
from input_rules import require_reason, optional_reason, require_qty

router = APIRouter(prefix="/api")


async def _auto_release_due_scheduled() -> int:
    """Order Pengambilan — rilis otomatis task picking terjadwal yang tanggal ambilnya
    sudah tiba (hold_until <= hari ini) → 'created' (masuk antrean aktif gudang)."""
    from services.analytics_time import now_wib
    today = now_wib().date().isoformat()   # Trial 22 Okt (E1) — tanggal ambil = tanggal WIB
    res = await db.wms_tasks.update_many(
        {"flow_type": "outbound", "status": "scheduled", "hold_until": {"$lte": today, "$ne": ""}},
        {"$set": {"status": "created", "updated_at": now_iso()}})
    return res.modified_count


@router.get("/outbound/tasks")
async def list_outbound_tasks(request: Request, status: str = None, warehouse_id: str = None,
                              entity_id: str = None) -> List[Dict[str, Any]]:
    """List all outbound picking tasks, optionally filtered.

    W-1 (Gelombang 2) — ter-scope entitas aktif (X-Entity-Id / ?entity_id), konsisten
    dengan inbound. entity_id='all' utk role lintas-entitas."""
    await require_permission(request, "wms", "view")
    await _auto_release_due_scheduled()

    query = {"flow_type": "outbound", "source_type": "sales_order"}
    if status:
        query["status"] = status
    else:
        query["status"] = {"$ne": "scheduled"}  # hold pengambilan dikecualikan dari antrean aktif
    if warehouse_id:
        query["warehouse_id"] = warehouse_id
    ctx = await entity_ctx(request)
    # FIX-1 (K-B1-02) — antrean keluar per GEDUNG dalam lokasi kerja, lintas PT yang ditugaskan (PT = label +
    # saringan `entity_id`); dulu dipagari PT aktif. Aksi tetap diperiksa per tugas (`assert_entity_access`).
    query = await resolve_work_scope("wms_tasks", query, ctx, entity_id)
    
    tasks = await db.wms_tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    
    # Enrich with SO info
    so_ids = list(set(t.get("order_id") for t in tasks if t.get("order_id")))
    # Cek UI UAT v3 — dulu to_list(100) memotong pesanan bila tugas > 100 SO → nama pelanggan kosong di panel.
    orders = {o["id"]: o for o in await db.sales_orders.find(
        {"id": {"$in": so_ids}}, {"_id": 0, "id": 1, "customer_name": 1, "total_amount": 1, "backorders": 1}).to_list(len(so_ids) or 1)}
    from services.fulfillment_status import open_backorder_qty
    
    # F-10 — status termin CBD/DP per SO: alasan tahan tampil di daftar & panel kirim (bukan baru ketahuan saat klik).
    from services import dispatch_payment_gate as _gate
    holds = await _gate.holds_for_orders(so_ids)
    for task in tasks:
        if task.get("order_id"):
            order = orders.get(task["order_id"], {})
            task["customer_name"] = order.get("customer_name", "")
            task["order_total"] = order.get("total_amount", 0)
            # Trial 22 Okt (E4) — sisa backorder SO untuk produk tugas ini: tugas 800/800 terkirim ≠ pesanan selesai.
            task["so_backorder_qty"] = open_backorder_qty(order, task.get("product_id", ""))
            hold = holds.get(task["order_id"])
            task["payment_hold"] = hold if hold and hold["applies"] else None
    from services.work_labels import label_rows
    await label_rows(tasks)
    return tasks


@router.get("/outbound/tasks/{task_id}/pick-list")
async def task_pick_list(task_id: str, request: Request) -> Dict[str, Any]:
    """Cek UI UAT v3 (2026-10-21) — roll yang HARUS diambil untuk tugas ini (dulu layar Barang Keluar hanya punya kolom
    scan, sehingga staf harus mencetak Surat Pengambilan Barang di layar lain untuk tahu roll mana): roll teralokasi SO
    ini di gudang & produk tugas (nomor, LOT, lokasi, panjang, sudah diambil/belum) + reservasi potong yang belum
    dipotong."""
    await require_permission(request, "wms", "view")
    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Outbound task tidak ditemukan")
    assert_entity_access(task, "wms_tasks", await entity_ctx(request))
    picked = {e.get("roll_id") for e in task.get("scan_log") or [] if e.get("scan_type") in ("pick", "cut") and e.get("roll_id")}
    rolls = await db.inventory_rolls.find(
        {"reserved_ref.id": task.get("order_id"), "product_id": task.get("product_id"),
         "warehouse_id": task.get("warehouse_id"), "status": {"$nin": ["delivered", "in_transit_sales", "cancelled"]}},
        {"_id": 0, "id": 1, "roll_no": 1, "lot": 1, "bin_id": 1, "bin_code": 1, "location_code": 1, "length_remaining": 1,
         "unit": 1, "status": 1}).sort("roll_no", 1).to_list(500)
    from services.roll_service import pending_cuts
    cuts = [c for c in await pending_cuts(task.get("order_id"))
            if c["product_id"] == task.get("product_id") and c["warehouse_id"] == task.get("warehouse_id")]
    return {"task_id": task_id, "order_id": task.get("order_id"), "unit": task.get("unit") or "",
            "rolls": [{**r, "picked": r["id"] in picked} for r in rolls],
            "pending_cuts": [{"roll_no": c["roll_no"], "lot": c.get("lot", ""), "qty": c["qty"]} for c in cuts]}


@router.post("/outbound/tasks/{task_id}/release")
async def release_scheduled_task(task_id: str, request: Request) -> Dict[str, Any]:
    """Order Pengambilan — rilis manual task picking terjadwal (hold) → 'created'."""
    actor = await require_permission(request, "wms", "update")
    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Outbound task tidak ditemukan")
    assert_entity_access(task, "wms_tasks", await entity_ctx(request))
    if task.get("status") != "scheduled":
        raise HTTPException(status_code=400, detail="Task tidak dalam status terjadwal (hold).")
    # FIX-3b (STM-OUT-6) — CAS daftar-izin: rilis ganda / rilis tugas yang baru dibatalkan kalah → 409.
    updated = await _ots.transition(task_id, "release", "created", actor_name=actor["name"],
                                    set_fields={"released_by": actor["name"], "released_at": now_iso()},
                                    prev_status="scheduled")
    if not updated:
        raise HTTPException(status_code=409, detail="Tugas sudah berubah status — muat ulang layar.")
    await audit(actor["name"], "outbound_task_released", "wms_task", task_id,
                {"order_number": task.get("order_number", "")})
    return safe_doc(updated)


async def _resolve_pick_roll(task: Dict[str, Any], code: str, bin_id: str, lot: str, qty: Optional[float]):
    """WM-06 — kode scan (id roll / no. roll / EPC) di-resolve server & harus roll milik order ini:
    produk, gudang, pemilik, status ter-alokasi, bin (bila dipindai) cocok.
    FIX-3b (K-B1-05/K-B3b-01, STM-OUT-5) — ambil = ROLL UTUH: qty kosong = panjang roll; qty < panjang roll ditolak
    (memotong roll wajib lewat reservasi potong, bukan pecah diam-diam saat kirim). Kode kosong ditangani pemanggil
    (jalur darurat berizin)."""
    code = (code or "").strip()
    if not code:
        return "", bin_id, lot, None
    roll = await db.inventory_rolls.find_one({"$or": [{"id": code}, {"roll_no": code}]}, {"_id": 0})
    if not roll:
        from services.epc import try_canonical
        tag = await db.rfid_tags.find_one({"epc": try_canonical(code) or code, "status": "active"}, {"_id": 0, "id": 1})
        roll = await db.inventory_rolls.find_one({"rfid_tag_id": tag["id"]}, {"_id": 0}) if tag else None
    if not roll:
        raise HTTPException(status_code=400, detail=f"Roll '{code}' tidak dikenal.")
    from services.roll_service import SHIPPABLE_STATUSES
    problems = []
    if roll.get("product_id") != task.get("product_id"):
        problems.append("produk berbeda")
    if roll.get("warehouse_id") != task.get("warehouse_id"):
        problems.append("gudang berbeda")
    if task.get("entity_id") and roll.get("owner_entity_id") and roll["owner_entity_id"] != task["entity_id"]:
        problems.append("pemilik berbeda")
    if (roll.get("reserved_ref") or {}).get("id") != task.get("order_id") or roll.get("status") not in SHIPPABLE_STATUSES:
        problems.append("tidak ter-alokasi untuk order ini")
    if bin_id and roll.get("bin_id") and roll["bin_id"] != bin_id:
        problems.append("bin berbeda")
    rlen = round(float(roll.get("length_remaining") or 0), 4)
    if qty is not None and qty > rlen + 0.01:
        problems.append(f"qty {qty} > panjang roll {roll.get('length_remaining')}")
    if problems:
        raise HTTPException(status_code=400, detail=f"Roll {roll.get('roll_no') or code} ditolak: {', '.join(problems)}.")
    if qty is not None and qty + 0.01 < rlen:
        raise HTTPException(status_code=400, detail=(
            f"Roll {roll.get('roll_no') or code} panjangnya {rlen:g} — ambil roll UTUH. Mengambil sebagian roll sama "
            "dengan memotong: pakai reservasi potong (Antrean Potong) lalu ambil roll anaknya."))
    already = {e.get("roll_id") for e in task.get("scan_log") or [] if e.get("scan_type") == "pick"}
    if roll["id"] in already:
        raise HTTPException(status_code=409, detail=f"Roll {roll.get('roll_no') or code} sudah dipindai di tugas ini.")
    return roll["id"], bin_id or roll.get("bin_id", ""), lot or roll.get("lot", ""), roll


@router.post("/outbound/tasks/{task_id}/scan-pick")
async def scan_pick_item(
    task_id: str,
    request: Request,
    actual_qty: Optional[float] = None,
    batch: str = "",
    lot: str = "",
    roll_id: str = "",
    bin_id: str = "",
    reason: str = "",
) -> Dict[str, Any]:
    """
    Scan and pick item for outbound task.

    FIX-3b (K-B1-05/K-B3b-01) — ambil WAJIB pindai roll (HP & desktop): `roll_id` = kode pindai (no. roll / EPC / id),
    `actual_qty` kosong = panjang roll. Tanpa kode roll = JALUR DARURAT: hanya pemegang izin `wms.approve` dengan
    alasan K-14 (`reason`), tercatat di `scan_log.manual_entry` + audit.
    """
    actor = await require_permission(request, "wms", "update")

    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Outbound task tidak ditemukan")
    assert_entity_access(task, "wms_tasks", await entity_ctx(request))

    if task.get("flow_type") != "outbound":
        raise HTTPException(status_code=400, detail="Task ini bukan outbound task")
    if task.get("task_subtype") == "sample_cut":
        raise HTTPException(status_code=400, detail="Tugas potong sample diselesaikan lewat Potong Sample, bukan Ambil.")
    _ots.assert_can(task, "scan_pick")   # FIX-3b (STM-OUT-2) — `escalated`/`scheduled`/terminal ditolak

    if actual_qty is not None:
        actual_qty = require_qty(actual_qty, label="Qty pick")
    manual_entry = None
    if not (roll_id or "").strip():
        from dependencies import has_permission
        if not await has_permission(actor, "wms", "approve"):
            raise HTTPException(status_code=400, detail=(
                "Ambil wajib memindai roll (label/QR/RFID). Ketik qty tanpa pindai hanya jalur darurat supervisor "
                "(izin wms.approve) dengan alasan."))
        why = require_reason(reason, label="Alasan ambil tanpa pindai roll")
        if actual_qty is None:
            raise HTTPException(status_code=400, detail="Jalur darurat: isi qty yang diambil.")
        manual_entry = {"reason": why, "by": actor["name"], "at": now_iso()}
    roll_id, bin_id, lot, roll_doc = await _resolve_pick_roll(task, roll_id, bin_id, lot, actual_qty)
    if roll_doc is not None and actual_qty is None:
        actual_qty = round(float(roll_doc.get("length_remaining") or 0), 4)
    from services import registration_freeze as _rfz   # PREP-B K-OPN-03 — area beku pendaftaran awal
    await _rfz.assert_task_movable(task, "pengambilan (picking) outbound", roll_id=roll_id, bin_id=bin_id)

    # Update picked qty
    # Cek UI UAT v3 (S10) — 19,42 + 20,37 + 0,21 = 40.00000000000001 dulu ditolak "melebihi 40.0":
    # jumlahkan dalam presisi qty (4 desimal) sebelum dibandingkan.
    new_picked_qty = round(float(task.get("picked_qty") or 0.0) + actual_qty, 4)
    expected_qty = float(task.get("quantity") or 0.0)
    
    # Check if qty exceeds expected
    if new_picked_qty > round(expected_qty, 4) + 1e-6:
        raise HTTPException(
            status_code=400,
            detail=f"Qty picked ({new_picked_qty}) melebihi expected ({expected_qty})"
        )
    
    # Log scan entry
    scan_entry = {
        "id": new_id("scan"),
        "scan_type": "pick",
        "actual_qty": actual_qty,
        "batch": batch,
        "lot": lot,
        "roll_id": roll_id,
        "bin_id": bin_id,
        "actor": actor["name"],
        "timestamp": now_iso(),
        **({"manual_entry": manual_entry} if manual_entry else {}),
    }

    update_data = {
        "picked_qty": new_picked_qty,
        "batch": batch or task.get("batch", ""),
        "lot": lot or task.get("lot", ""),
        "roll_id": roll_id or task.get("roll_id", ""),
        "bin_id": bin_id or task.get("bin_id", ""),
    }
    new_status = task["status"]
    if task["status"] == "created" and new_picked_qty > 0:
        new_status = "picking"
    # If fully picked, advance to packing (tugas terkirim sebagian tetap `partially_shipped`)
    if new_picked_qty >= round(expected_qty, 4) - 1e-6 and task["status"] != "partially_shipped":
        new_status = "packing"
    if new_status not in ("picking", "packing", "partially_shipped"):
        new_status = "picking"

    # Sesi 12 / FIX-3b — CAS daftar-izin + picked_qty tak berubah sejak dibaca → klik ganda/balapan kalah = 409.
    pq = {"$or": [{"picked_qty": task.get("picked_qty", 0.0)}, {"picked_qty": {"$exists": False}}]} \
        if not task.get("picked_qty") else {"picked_qty": task.get("picked_qty")}
    updated_task = await _ots.transition(task_id, "scan_pick", new_status, actor_name=actor["name"],
                                         set_fields=update_data, extra_filter=pq, push={"scan_log": scan_entry},
                                         prev_status=task["status"])
    if not updated_task:
        raise HTTPException(status_code=409, detail={"code": "STATE_CHANGED",
                            "message": "Tugas sudah berubah (pick lain masuk lebih dulu). Muat ulang layar."})

    await audit(actor["name"], "outbound_scan_pick", "wms_task", task_id, {
        "actual_qty": actual_qty,
        "picked_qty": new_picked_qty,
        "expected_qty": expected_qty,
        "roll_id": roll_id,
        **({"manual_entry": True} if manual_entry else {}),
    }, **({"reason": manual_entry["reason"]} if manual_entry else {}))

    # Sub-fase 1.8 — status SO terderivasi otomatis dari progres pick
    if task.get("order_id"):
        await recompute_so_status(task["order_id"])

    return safe_doc(updated_task)


@router.post("/outbound/tasks/{task_id}/escalate")
async def escalate_outbound_task(
    task_id: str,
    request: Request,
    reason: str = "Stock fisik tidak sesuai dengan sistem"
) -> Dict[str, Any]:
    """
    Escalate outbound task to manager due to stock mismatch or other issues.
    
    Manager can then reorganize/adjust allocation.
    """
    actor = await require_permission(request, "wms", "update")
    
    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Outbound task tidak ditemukan")
    assert_entity_access(task, "wms_tasks", await entity_ctx(request))
    # KN-C02 / FIX-3b — status dinilai dulu (409), baru alasan K-14 (≥ 5 huruf).
    _ots.assert_can(task, "escalate", status_code=409)
    reason = require_reason(reason, label="Alasan eskalasi")

    escalation = {
        "escalated_by": actor["name"],
        "escalated_at": now_iso(),
        "reason": reason,
        "status": "pending_review",
        "prev_status": task.get("status"),   # FIX-3b — dipulihkan bila diputus tanpa ubah qty
        "resolved_by": None,
        "resolved_at": None,
        "resolution_notes": ""
    }

    # KN-C02 — eskalasi berprasyarat status (daftar-izin, CAS): tugas dispatched/cancelled/completed tidak boleh
    # dihidupkan kembali lewat escalate→resolve.
    updated_task = await _ots.transition(task_id, "escalate", "escalated", actor_name=actor["name"],
                                         set_fields={"escalation": escalation}, note=reason,
                                         prev_status=task.get("status"))
    if not updated_task:
        raise HTTPException(status_code=409, detail=(
            f"Tugas berstatus '{task.get('status')}' tidak bisa dieskalasi (sudah dikirim/dibatalkan/sedang dieskalasi)."))
    
    await audit(actor["name"], "outbound_escalated", "wms_task", task_id, {
        "reason": reason,
        "picked_qty": task.get("picked_qty", 0),
        "expected_qty": task.get("quantity", 0)
    })
    try:   # FIX-3b (B2b ANOM-27) — eskalasi = keputusan supervisor: pemegang keputusan diberi tahu (dulu 0 notifikasi)
        from services import notification_service as _ns
        for role in ("manager", "warehouse_admin"):
            await _ns.create_notification(
                notif_type="outbound_escalation", ref=f"outbound_escalation:{task_id}:{role}",
                title=f"Eskalasi tugas ambil {task.get('order_number', '')}",
                body=f"{task.get('product_name', '')} · {task.get('warehouse_name', '')} — {reason}"[:400],
                severity="warning", link="outbound", entity_id=task.get("entity_id") or None, recipient_role=role)
    except Exception:  # noqa: BLE001 — notifikasi tidak boleh menggagalkan eskalasi
        pass
    
    return safe_doc(updated_task)


@router.post("/outbound/tasks/{task_id}/resolve-escalation")
async def resolve_outbound_escalation(
    task_id: str,
    request: Request,
    adjusted_qty: float = None,
    resolution_notes: str = "",
    close_remainder: bool = False,
) -> Dict[str, Any]:
    """
    Resolve escalated outbound task (manager only).

    FIX-3b — (STM-OUT-2) hanya tugas berstatus `escalated` (CAS); status sesudahnya TURUNAN progres (tugas terkirim
    penuh tidak kembali `packing`); tanpa qty = status sebelum eskalasi. (STM-OUT-1, K-B2b-01) tugas yang sudah terkirim
    sebagian hanya boleh "tutup sisa" (`close_remainder=true` atau `adjusted_qty` = qty yang sudah diambil); roll yang
    sudah di Surat Jalan / sudah diambil TIDAK pernah dilepas — yang dilepas hanya roll cadangan yang belum disentuh.
    """
    actor = await require_permission(request, "wms", "approve")  # Manager permission

    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Outbound task tidak ditemukan")
    assert_entity_access(task, "wms_tasks", await entity_ctx(request))

    if not task.get("escalation"):
        raise HTTPException(status_code=400, detail="Task tidak dalam status escalation")
    if task["escalation"].get("status") in ("resolved", "resolving", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail="Eskalasi sudah/sedang diselesaikan pihak lain (atau ditutup karena pesanan batal). Muat ulang layar.")
    _ots.assert_can(task, "resolve_escalation", status_code=409)
    resolution_notes = optional_reason(resolution_notes, label="Catatan penyelesaian")

    original_qty = round(float(task.get("quantity", 0) or 0), 2)
    picked = round(float(task.get("picked_qty", 0) or 0), 2)
    shipped = round(float(task.get("shipped_qty", 0) or 0), 2)
    if close_remainder:
        adjusted_qty = max(picked, shipped)
    if adjusted_qty is not None:
        adjusted_qty = round(require_qty(adjusted_qty, label="Qty penyesuaian"), 2)
        if adjusted_qty > original_qty + 0.01:
            raise HTTPException(
                status_code=400,
                detail="Qty tidak bisa DINAIKKAN dari eskalasi — amend SO / buat order tambahan.")
        if adjusted_qty + 0.01 < picked:
            raise HTTPException(
                status_code=400,
                detail=f"Qty penyesuaian ({adjusted_qty:g}) di bawah qty yang sudah di-pick ({picked:g}).")
        if shipped > 0.01 and abs(adjusted_qty - max(picked, shipped)) > 0.01:
            raise HTTPException(status_code=400, detail=(
                f"Tugas ini sudah terkirim sebagian ({shipped:g}). Eskalasinya hanya bisa 'tutup sisa' — qty menjadi "
                f"yang sudah diambil ({max(picked, shipped):g}); roll yang sudah di Surat Jalan tidak pernah dilepas."))

    async def _claim() -> None:
        # T-01 Langkah 1 (audit 2026-09) — klaim tugas secara ATOMIK sebelum menulis apa
        # pun (roll dilepas + SO ditulis + task ditulis tanpa transaksi). Hanya SATU
        # pemanggil yang lolos; ulang-jalan setelah proses mati di tengah tidak melepas
        # roll dua kali — tugas tertinggal 'resolving' itu terlihat & bisa ditangani.
        claimed = await db.wms_tasks.find_one_and_update(
            {"id": task_id, "status": "escalated", "escalation": {"$exists": True},   # KN-C02
             "escalation.status": {"$nin": ["resolved", "resolving", "cancelled"]}},
            {"$set": {"escalation.status": "resolving", "escalation.resolving_at": now_iso()}},
            projection={"_id": 0})
        if not claimed:
            raise HTTPException(
                status_code=409,
                detail="Eskalasi sudah/sedang diselesaikan pihak lain. Muat ulang layar.")

    escalation = dict(task["escalation"])
    escalation["status"] = "resolved"
    escalation["resolved_by"] = actor["name"]
    escalation["resolved_at"] = now_iso()
    escalation["resolution_notes"] = resolution_notes
    escalation.pop("resolving_at", None)

    final_qty = original_qty if adjusted_qty is None else adjusted_qty
    if adjusted_qty is None and escalation.get("prev_status") in _ots.TRANSITIONS["resolve_escalation"]["to"]:
        new_status = escalation["prev_status"]
    else:
        new_status = _ots.derived_status(final_qty, picked, shipped)
    update_data: Dict[str, Any] = {"escalation": escalation}

    # S-6 (Gelombang 2) — penyesuaian qty oleh manager kini SINKRON penuh:
    # roll reservation dilepas parsial, allocation + item + pricing order dihitung ulang.
    if adjusted_qty is not None:
        delta = round(original_qty - adjusted_qty, 2)
        update_data["quantity"] = adjusted_qty

        order = None
        if task.get("order_id"):
            order = safe_doc(await db.sales_orders.find_one({"id": task["order_id"]}, {"_id": 0}))
        if order and delta > 0.01:
            if order.get("payments"):
                raise HTTPException(
                    status_code=400,
                    detail="Order sudah memiliki pembayaran — penyesuaian qty harus lewat retur/credit note.")
            await _claim()
            # 1) Lepas selisih reservasi roll (parsial, per produk+gudang task ini). FIX-3b (STM-OUT-1) — roll yang
            #    sudah dipindai/terkirim di tugas ini dikecualikan; status `in_transit_sales` tidak pernah dilepas.
            from services.roll_service import release_order_rolls_partial
            touched = [e.get("roll_id") for e in task.get("scan_log") or [] if e.get("roll_id")]
            touched += [r for e in task.get("scan_log") or [] if e.get("scan_type") == "dispatch"
                        for r in e.get("rolls") or []]
            released = await release_order_rolls_partial(
                order["id"], task["product_id"], task["warehouse_id"], delta, exclude_roll_ids=touched)
            # 2) Allocation qty
            await db.sales_orders.update_one(
                {"id": order["id"], "allocations.id": task.get("allocation_id")},
                {"$set": {"allocations.$.quantity": adjusted_qty, "updated_at": now_iso()}})
            # 3) Item qty (base + unit jual proporsional) + repricing seluruh order
            items = [dict(i) for i in order.get("items", [])]
            for it in items:
                if it.get("product_id") != task.get("product_id"):
                    continue
                old_base = float(it.get("base_quantity", it.get("quantity", 0)) or 0)
                if old_base <= 0:
                    break
                new_base = max(round(old_base - delta, 2), 0.0)
                sell_per_base = float(it.get("quantity", 0) or 0) / old_base
                it["base_quantity"] = new_base
                it["quantity"] = round(new_base * sell_per_base, 2)
                if "reserved_qty" in it:  # invarian L4-BO: base_qty == reserved+backorder+interco
                    it["reserved_qty"] = max(
                        round(float(it.get("reserved_qty", 0) or 0) - delta, 2), 0.0)
                break
            from services.config_service import compute_order_pricing
            # KN-A10 — diskon header pesanan DIPERTAHANKAN (dulu di-hardcode 0 → short-pick
            # justru menaikkan tagihan pelanggan).
            pricing = await compute_order_pricing(
                items, order.get("entity_id"), float(order.get("order_discount_percent", 0) or 0),
                tax_override=(order.get("tax_override") or "").strip().lower() or None)
            await db.sales_orders.update_one(
                {"id": order["id"]},
                {"$set": {
                    "items": pricing["items"],
                    "total_amount": pricing["total_amount"],
                    "items_discount_total": pricing["items_discount_total"],
                    "order_discount_amount": pricing["order_discount_amount"],
                    "discount_total": pricing["discount_total"],
                    "net_subtotal": pricing["net_subtotal"],
                    "dpp": pricing["dpp"], "dpp_nilai_lain": pricing.get("dpp_nilai_lain", False),
                    "effective_rate": pricing.get("effective_rate", pricing["ppn_rate"]),
                    "ppn_amount": pricing["ppn_amount"],
                    "grand_total": pricing["grand_total"],
                    "approval_amount": pricing["grand_total"],
                    "updated_at": now_iso(),
                },
                 "$push": {"timeline": {
                     "event": "qty_adjusted", "label": "Qty disesuaikan via eskalasi gudang",
                     "actor": actor["name"], "at": now_iso(),
                     "note": (f"{task.get('product_name', task.get('product_id'))}: "
                              f"{original_qty:g} → {adjusted_qty:g} (roll dilepas {released:g}). "
                              f"{resolution_notes}").strip(),
                 }}})

    # FIX-3b (STM-OUT-2) — CAS: status masih `escalated` (atau sedang diklaim resolve ber-qty di atas).
    updated_task = await _ots.transition(
        task_id, "resolve_escalation", new_status, actor_name=actor["name"], set_fields=update_data,
        extra_filter={"escalation.status": {"$nin": ["resolved", "cancelled"]}},
        note=resolution_notes or "eskalasi diputus", prev_status="escalated")
    if not updated_task:
        raise HTTPException(
            status_code=409,
            detail="Eskalasi sudah diselesaikan pihak lain / tugas berubah status. Muat ulang layar.")

    await audit(actor["name"], "outbound_escalation_resolved", "wms_task", task_id, {
        "adjusted_qty": adjusted_qty,
        "resolution_notes": resolution_notes,
        "status": new_status,
    })
    if task.get("order_id"):
        await recompute_so_status(task["order_id"])

    return safe_doc(updated_task)


@router.post("/outbound/tasks/{task_id}/reopen-escalation")
async def reopen_outbound_escalation(task_id: str, request: Request) -> Dict[str, Any]:
    """Eskalasi MENGGANTUNG (`escalation.status == resolving`, proses mati di tengah) →
    kembalikan ke `escalated` agar manajer bisa menyelesaikannya lagi. Manager only."""
    actor = await require_permission(request, "wms", "approve")
    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Outbound task tidak ditemukan")
    assert_entity_access(task, "wms_tasks", await entity_ctx(request))
    updated = await db.wms_tasks.find_one_and_update(
        {"id": task_id, "escalation.status": "resolving"},
        {"$set": {"escalation.status": "pending_review", "escalation.reopened_by": actor["name"],
                  "escalation.reopened_at": now_iso(), "updated_at": now_iso()},
         "$unset": {"escalation.resolving_at": ""}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(status_code=409, detail="Eskalasi tidak dalam keadaan menggantung (resolving).")
    await audit(actor["name"], "outbound_escalation_reopened", "wms_task", task_id,
                {"previous_resolving_at": (task.get("escalation") or {}).get("resolving_at")})
    return safe_doc(updated)



@router.post("/outbound/tasks/{task_id}/dispatch")
async def dispatch_outbound(task_id: str, request: Request, ship_qty: float = None) -> Dict[str, Any]:
    """Sub-fase 1.8 — Dispatch task outbound (mendukung PENGIRIMAN PARSIAL).

    SSOT-safe: roll order committed→in_transit_sales (BUKAN $inc balance). Setiap dispatch
    mencatat 1 record `shipments` (No. Surat Jalan SJ-####). `ship_qty` opsional — default
    = sisa yang sudah di-pick & belum dikirim. Status SO terderivasi otomatis.
    """
    actor = await require_permission(request, "wms", "update")

    task = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
    if not task:
        raise HTTPException(status_code=404, detail="Outbound task tidak ditemukan")
    assert_entity_access(task, "wms_tasks", await entity_ctx(request))

    # FASE R4 — Final Loading Check menjaga pintu dispatch (selisih = blokir).
    from services import loading_check_service as lc
    await lc.dispatch_guard(task.get("order_id"), task.get("warehouse_id"))

    updated_task, shipment = await dispatch_task(task, ship_qty, actor["name"])

    await audit(actor["name"], "outbound_dispatched", "wms_task", task_id, {
        "ship_qty": shipment["qty"], "shipment_no": shipment["shipment_no"],
        "task_status": updated_task["status"],
    })

    return {"task": updated_task, "shipment": shipment}


@router.post("/outbound/so/{order_id}/dispatch-batch")
async def dispatch_order_batch(order_id: str, request: Request, warehouse_id: str) -> Dict[str, Any]:
    """Trial 22 Okt (A2) — kirim semua tugas pesanan ini di satu gudang yang siap kirim dengan SATU nomor Surat Jalan
    (dulu tiap baris satu SJ). Gerbang yang sama dengan kirim per tugas (bayar, QC, serah potong, cek muat)."""
    actor = await require_permission(request, "wms", "update")
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "entity_id": 1, "number": 1}))
    if not order:
        raise HTTPException(status_code=404, detail="Pesanan tidak ditemukan")
    assert_entity_access(order, "sales_orders", await entity_ctx(request))
    from services import loading_check_service as lc
    await lc.dispatch_guard(order_id, warehouse_id)
    from services.shipment_service import dispatch_order_batch as _batch
    out = await _batch(order_id, warehouse_id, actor["name"])
    await audit(actor["name"], "outbound_dispatched_batch", "sales_order", order_id,
                {"shipment_no": out["shipment_no"], "lines": out["lines"], "qty": out["qty"]})
    return out


# ─── FASE R4 — Final Loading Check (handheld vs manifest SO sebelum naik mobil) ──
from entity_scope import resolve_scope_ids as _resolve_scope_ids
from services import loading_check_service as _lc
from services import rfid_print_service as _rps


@router.post("/outbound/so/{order_id}/loading-check/start")
async def start_loading_check(order_id: str, request: Request, warehouse_id: Optional[str] = None) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "update")
    ctx = await entity_ctx(request)
    sess = await _lc.start(order_id, _resolve_scope_ids(ctx, None), actor["name"], warehouse_id)
    await audit(actor["name"], "loading_check_started", "sales_order", order_id,
                {"session_id": sess["id"], "expected": len(sess.get("expected", [])),
                 "warehouse_id": warehouse_id})
    return sess


@router.post("/outbound/loading-check/{session_id}/scan")
async def scan_loading_check(session_id: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "update")
    ctx = await entity_ctx(request)
    source = str(payload.get("source") or "manual")
    if source == "device":
        # FIX-3b (K-B3b-02) — sumber "perangkat" hanya dari jalur ber-key perangkat (handheld /api/handheld, reader);
        # layar pengguna mengirim EPC ketik/tempel = "manual" (dicatat, bukan bukti sah).
        raise HTTPException(status_code=400, detail=(
            "Sumber 'perangkat' hanya dari handheld/reader. EPC yang ditempel di layar dicatat sebagai manual."))
    return await _rps.scan_session(session_id, list(payload.get("epcs") or []), _resolve_scope_ids(ctx, None),
                                   ["loading_check"], source, actor["name"])


@router.post("/outbound/loading-check/{session_id}/cancel")
async def cancel_loading_check(session_id: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    """FIX-3b (FLW-OUT-6) — batalkan sesi cek muat terbuka (alasan K-14)."""
    actor = await require_permission(request, "wms", "update")
    ctx = await entity_ctx(request)
    sess = await _lc.cancel(session_id, _resolve_scope_ids(ctx, None), str((payload or {}).get("reason") or ""),
                            actor["name"])
    await audit(actor["name"], "loading_check_cancelled", "sales_order", sess.get("order_id", ""),
                {"session_id": session_id}, reason=sess.get("cancel_reason", ""))
    return sess


@router.post("/outbound/loading-check/{session_id}/scan-label")
async def scan_label_loading_check(session_id: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    """RF-05 + W2-REQ-08 — pengecualian roll tanpa RFID (izin wms.untagged_override + alasan, diaudit)."""
    actor = await require_permission(request, "wms", "update")
    from dependencies import has_permission
    if not await has_permission(actor, "wms", "untagged_override"):
        from dependencies import denied   # PR-T6 (Z6)
        raise denied([("wms", "untagged_override")], note="Roll tanpa tag wajib dicetak/diverifikasi RFID.")
    ctx = await entity_ctx(request)
    reason = str(payload.get("reason") or "")
    sess = await _lc.scan_label(session_id, str(payload.get("code") or ""), _resolve_scope_ids(ctx, None),
                                reason, actor["name"])
    await audit(actor["name"], "loading_check_untagged_exception", "sales_order", sess.get("order_id", ""),
                {"session_id": session_id, "code": str(payload.get("code") or "")}, reason=reason.strip())
    return sess


@router.post("/outbound/so/{order_id}/loading-check/override")
async def override_loading_check(order_id: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    """RF-04 — pengecualian berizin (wms.approve) + alasan; tercatat audit & terikat manifest."""
    actor = await require_permission(request, "wms", "approve")
    so = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not so:
        raise HTTPException(status_code=404, detail="SO tidak ditemukan")
    assert_entity_access(so, "sales_orders", await entity_ctx(request))
    lc = await _lc.override(order_id, str(payload.get("reason") or ""), actor["name"],
                            payload.get("warehouse_id") or None)
    await audit(actor["name"], "loading_check_override", "sales_order", order_id,
                {"reason": lc["reason"], "rolls": len(lc["manifest"])}, reason=lc["reason"])
    return lc


@router.post("/outbound/so/{order_id}/loading-check/simulate-tags")
async def simulate_tags_for_order(order_id: str, payload: Dict[str, Any], request: Request) -> Dict[str, Any]:
    """UAT v3 — mode simulasi RFID (`wms.rfid_simulation`): tag aktif untuk roll SO yang belum bertag (tanpa printer)."""
    actor = await require_permission(request, "wms", "update")
    so = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not so:
        raise HTTPException(status_code=404, detail="SO tidak ditemukan")
    ctx = await entity_ctx(request)
    assert_entity_access(so, "sales_orders", ctx)
    out = await _lc.simulate_tags(order_id, (payload or {}).get("warehouse_id") or None, _resolve_scope_ids(ctx), actor["name"])
    if out["count"]:
        await audit(actor["name"], "rfid_simulated_tags", "sales_order", order_id,
                    {"rolls": [m["roll_no"] for m in out["created"]], "warehouse_id": out["warehouse_id"]},
                    reason="Mode simulasi RFID (UAT)")
    return out


@router.post("/outbound/loading-check/{session_id}/complete")
async def complete_loading_check(session_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "wms", "update")
    ctx = await entity_ctx(request)
    sess = await _lc.complete(session_id, _resolve_scope_ids(ctx, None))
    await audit(actor["name"], "loading_check_completed", "sales_order", sess.get("order_id", ""),
                {"result": sess.get("result"), "missing": len(sess.get("missing", [])),
                 "extra": len(sess.get("extra", []))})
    return sess


@router.get("/outbound/so/{order_id}/loading-check")
async def get_loading_check(order_id: str, request: Request, warehouse_id: Optional[str] = None) -> Dict[str, Any]:
    await require_permission(request, "wms", "view")
    # FIX-1 (G-SCOPE-01) — status cek muat SO PT lain tidak dibuka lewat id pesanan.
    so = await db.sales_orders.find_one({"id": order_id}, {"_id": 0, "id": 1, "entity_id": 1})
    if not so:
        raise HTTPException(status_code=404, detail="Pesanan tidak ditemukan")
    assert_entity_access(so, "sales_orders", await entity_ctx(request))
    return await _lc.status_for_order(order_id, warehouse_id)

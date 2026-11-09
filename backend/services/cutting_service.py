"""L06 LN-061 — Meja Cutting/Admin Cutting: kemampuan lokasi, antrean potong, serah-terima hasil potong."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core_utils import new_id, now_iso, safe_doc
from db import db
from services import sample_sale_service as smp
from services.roll_service import rebuild_balance
from services import warehouse_scope_service as wss

QUEUES = (("awaiting_internal", "Menunggu pembelian internal (stok milik PT lain)"),
          ("to_cut", "Menunggu dipotong gudang"),
          ("to_receive", "Hasil potong — menunggu diterima Admin Cutting"),
          ("ready", "Diterima Admin Cutting — siap kirim/ambil"))


async def list_locations() -> List[Dict[str, Any]]:
    rows = await db.warehouses.find({}, {"_id": 0, "id": 1, "name": 1, "city": 1, "cutting_caps": 1,
                                         "sharing_mode": 1, "entity_ids": 1}).sort("name", 1).to_list(500)
    return [{**r, "cutting_caps": smp.warehouse_caps(r), "configured": r.get("cutting_caps") is not None,
             "sharing_mode": wss.mode_of(r), "entity_ids": wss.dedicated_ids(r)} for r in rows]


async def set_location_caps(wid: str, caps: List[str], actor: str) -> Dict[str, Any]:
    bad = [c for c in caps if c not in smp.ALL_CAPS]
    if bad:
        raise HTTPException(status_code=400, detail=f"Kemampuan tidak dikenal: {', '.join(bad)}.")
    wh = await db.warehouses.find_one_and_update(
        {"id": wid}, {"$set": {"cutting_caps": [c for c in smp.ALL_CAPS if c in caps],
                               "cutting_caps_by": actor, "cutting_caps_at": now_iso()}},
        projection={"_id": 0, "id": 1, "name": 1, "cutting_caps": 1}, return_document=True)
    if not wh:
        raise HTTPException(status_code=404, detail="Lokasi tidak ditemukan.")
    return wh


def _queue_of(task: Dict[str, Any], line: Dict[str, Any]) -> Optional[str]:
    if task.get("status") in ("cancelled", "dispatched", "shipped", "delivered", "done"):
        return None
    if (task.get("cutting_handoff") or {}).get("received_at"):
        return "ready"
    if task.get("roll_id"):
        return "to_receive"
    return "awaiting_internal" if line.get("sample_cut_status") == "awaiting_internal" else "to_cut"


WAIT_WARN_MIN = 120   # ≥2 jam menunggu diterima → kuning
WAIT_LATE_MIN = 240   # ≥4 jam → merah "terlambat"


def _minutes_since(iso: Optional[str], until: Optional[str] = None) -> Optional[int]:
    if not iso:
        return None
    try:
        start = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(until).replace("Z", "+00:00")) if until else datetime.now(timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return max(0, int((end - start).total_seconds() // 60))
    except ValueError:
        return None


async def wait_thresholds(entity_id: Optional[str]) -> Dict[str, int]:
    from services import config_resolver
    ctx = {"entity_id": entity_id} if entity_id else None
    warn = int(await config_resolver.value_of("cutting.wait_warn_minutes", ctx) or WAIT_WARN_MIN)
    late = int(await config_resolver.value_of("cutting.wait_late_minutes", ctx) or WAIT_LATE_MIN)
    return {"warn_minutes": warn, "late_minutes": max(warn, late)}


async def desk(scope: Dict[str, Any], entity_id: Optional[str] = None) -> Dict[str, Any]:
    th = await wait_thresholds(entity_id)
    tasks = await db.wms_tasks.find({**scope, "task_subtype": "sample_cut"}, {"_id": 0}).sort("created_at", 1).to_list(500)
    orders = {o["id"]: o for o in await db.sales_orders.find(
        {"id": {"$in": list({t["order_id"] for t in tasks})}}, {"_id": 0, "id": 1, "items": 1, "number": 1, "catalogue": 1}).to_list(500)}
    whs = {w["id"]: w.get("name", "") async for w in db.warehouses.find({}, {"_id": 0, "id": 1, "name": 1})}
    owners = {r["id"]: r.get("owner_entity_id") or "" async for r in db.inventory_rolls.find(
        {"id": {"$in": [t["roll_id"] for t in tasks if t.get("roll_id")]}}, {"_id": 0, "id": 1, "owner_entity_id": 1})}
    buckets: Dict[str, List[Dict[str, Any]]] = {k: [] for k, _ in QUEUES}
    for t in tasks:
        o = orders.get(t["order_id"]) or {}
        line = next((i for i in o.get("items", []) if i.get("product_id") == t.get("product_id") and i.get("is_sample")), {})
        q = _queue_of(t, line)
        if not q:
            continue
        buckets[q].append({
            "task_id": t["id"], "order_id": t["order_id"], "order_number": t.get("order_number", ""),
            "customer_name": t.get("customer_name", ""), "product_name": t.get("product_name", ""), "sku": t.get("sku", ""),
            "sample_kind": line.get("sample_kind") or ("catalogue" if o.get("catalogue") else "standard"),
            "quantity": t.get("quantity"), "unit": t.get("unit"), "status": t.get("status"),
            "warehouse_id": t.get("warehouse_id"), "warehouse_name": whs.get(t.get("warehouse_id"), ""),
            "child_roll_no": t.get("child_roll_no", ""), "parent_roll_no": t.get("parent_roll_no", ""),
            "source_owner_entity_id": line.get("source_owner_entity_id", ""), "handoff": t.get("cutting_handoff"),
            "handoff_pending": t.get("cutting_handoff_pending"),   # FIX-3b (CUT-3) — menunggu transfer lintas gedung
            "roll_owner_entity_id": owners.get(t.get("roll_id")) or t.get("entity_id") or "",
            "cut_at": t.get("cut_at") or line.get("cut_at") or "",
            "wait_minutes": _minutes_since(t.get("cut_at") or line.get("cut_at"),
                                           (t.get("cutting_handoff") or {}).get("received_at")) if q in ("to_receive", "ready") else None})
    buckets["to_receive"].sort(key=lambda r: -(r["wait_minutes"] or 0))
    late = sum(1 for r in buckets["to_receive"] if (r["wait_minutes"] or 0) >= th["late_minutes"])
    return {"queues": [{"key": k, "label": lbl, "rows": buckets[k]} for k, lbl in QUEUES],
            "wait_thresholds": th, "late_count": late}


TERMINAL_TASK = ("cancelled", "dispatched", "shipped", "delivered", "done", "completed")


async def _handoff_transfer(task: Dict[str, Any], roll: Dict[str, Any], wh: Dict[str, Any],
                            actor: Dict[str, Any]) -> Dict[str, Any]:
    """FIX-3b (CUT-3, keputusan K-B2b-10) — serah-terima Admin Cutting LINTAS GEDUNG wajib DOKUMEN: transfer internal
    (status menunggu persetujuan, roll anak tetap berkomitmen ke pesanan lewat `transfer_ref`) yang lalu dijalankan
    seperti transfer lain (setujui → kirim → gate/terima). Roll TIDAK dipindah langsung. Idempoten: transfer terbuka
    untuk roll ini dipakai ulang."""
    from services.transfer_receipt_service import _active_transfer_of
    busy = await _active_transfer_of(roll)
    if busy:
        return {"id": busy["id"], "code": busy.get("code"), "reused": True}
    from core_utils import next_doc_number
    prod = await db.products.find_one({"id": roll["product_id"]}, {"_id": 0, "sku": 1, "name": 1, "line_code": 1,
                                                                   "base_unit": 1}) or {}
    owner = roll.get("owner_entity_id") or task.get("entity_id") or ""
    tid = new_id("trn")
    code = await next_doc_number("warehouse_transfers", "code", "TRF-", entity_id=owner or None)
    so = await db.sales_orders.find_one({"id": task["order_id"]}, {"_id": 0, "number": 1, "customer_name": 1}) or {}
    length = round(float(roll.get("length_remaining") or 0), 2)
    item = {"product_id": roll["product_id"], "qty": length, "unit": prod.get("base_unit") or roll.get("unit") or "",
            "owner_entity_id": owner, "sku": prod.get("sku", ""), "product_name": prod.get("name", ""),
            "lots": [roll["lot"]] if roll.get("lot") else [], "qty_rolls": 1,
            "rolls": [{"roll_id": roll["id"], "roll_no": roll.get("roll_no"), "lot": roll.get("lot"), "length": length,
                       "committed_so": task["order_id"]}],
            "line_code": str(prod.get("line_code") or "").strip().lower()}
    res = await db.inventory_rolls.update_one(
        {"id": roll["id"], "status": roll.get("status"), "reserved_ref.id": task["order_id"],
         "transfer_ref": roll.get("transfer_ref"), "active_movement": None},
        {"$set": {"transfer_ref": {"type": "wh_transfer", "id": tid, "so_id": task["order_id"]},
                  "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(status_code=409, detail="Roll hasil potong baru saja berubah — muat ulang.")
    from services import line_scope
    doc = {"id": tid, "code": code, "transfer_kind": "intra_entity", "purpose": "cutting_handoff",
           "entity_id": owner, "source_warehouse_id": roll["warehouse_id"], "dest_warehouse_id": wh["id"],
           "status": "waiting_approval", "items": [item], "line_codes": line_scope.codes_from_items([item]),
           "notes": f"Serah-terima hasil potong sample {task.get('order_number', '')} ke Admin Cutting {wh.get('name', '')}",
           "requested_by": actor.get("name", ""), "approved_by": None, "approved_at": None, "rejected_by": None,
           "rejected_at": None, "rejected_reason": None, "sales_order_id": task["order_id"],
           "sales_order_number": so.get("number", ""), "sales_order_customer": so.get("customer_name", ""),
           "cutting_task_id": task["id"], "created_at": now_iso(), "updated_at": now_iso()}
    await db.warehouse_transfers.insert_one(dict(doc))
    await db.sales_orders.update_one({"id": task["order_id"]}, {"$addToSet": {"linked_transfer_ids": tid}})
    from dependencies import audit
    await audit(actor.get("name", ""), "transfer_created", "transfer", tid,
                {"code": code, "items": 1, "purpose": "cutting_handoff", "task_id": task["id"]})
    return {"id": tid, "code": code, "reused": False}


async def receive(task_id: str, to_warehouse_id: str, actor: Dict[str, Any], scope_entities: List[str]) -> Dict[str, Any]:
    """Admin Cutting menerima hasil potong.

    FIX-3b (CUT-3, K-B2b-10) — (1) tugas TERMINAL (batal/terkirim) ditolak 409, dan klaim berprasyarat status hidup
    (dulu tugas sampel yang sudah batal tetap memindah roll Jakarta → Bandung). (2) Lokasi Admin Cutting ≠ gudang roll
    → TIDAK memindah roll langsung: lahir transfer internal (dokumen + gate), serah-terima dicatat "menunggu transfer";
    sesudah transfer diterima di tujuan, "Terima" lagi = serah-terima di lokasi yang sama."""
    task = await db.wms_tasks.find_one({"id": task_id, "task_subtype": "sample_cut"}, {"_id": 0})
    if not task or (scope_entities and task.get("entity_id") not in scope_entities):
        raise HTTPException(status_code=404, detail="Tugas potong tidak ditemukan.")
    if (task.get("cutting_handoff") or {}).get("received_at"):
        return safe_doc(task)   # idempoten
    if task.get("status") in TERMINAL_TASK:
        raise HTTPException(status_code=409, detail=(
            f"Tugas potong berstatus '{task.get('status')}' — hasil potong pesanan yang dibatalkan/terkirim tidak "
            "diterima Admin Cutting. Roll sisa potongnya dikembalikan lewat Penempatan Rak."))
    if not task.get("roll_id"):
        raise HTTPException(status_code=409, detail="Belum dipotong gudang — belum ada hasil potong untuk diterima.")
    roll = await db.inventory_rolls.find_one({"id": task["roll_id"]}, {"_id": 0})
    if not roll:
        raise HTTPException(status_code=409, detail="Roll hasil potong tidak ditemukan — hubungi admin gudang.")
    src = roll.get("warehouse_id") or task.get("warehouse_id")
    dst = (to_warehouse_id or "").strip() or src
    wh = await db.warehouses.find_one({"id": dst}, {"_id": 0, "id": 1, "name": 1, "sharing_mode": 1, "entity_ids": 1})
    if not wh:
        raise HTTPException(status_code=404, detail="Lokasi tujuan Admin Cutting tidak ditemukan.")
    owner = roll.get("owner_entity_id") or task.get("entity_id") or ""
    if dst != src and (not wss.is_usable(wh, owner) or (scope_entities and owner not in scope_entities)):
        raise HTTPException(status_code=400, detail={
            "code": "CUTTING_DEST_OTHER_OWNER",
            "message": f"Lokasi {wh.get('name', dst)} bukan gudang milik/terbuka untuk pemilik roll — hasil potong tidak boleh pindah ke PT lain."})
    now = now_iso()
    if dst != src:
        trf = await _handoff_transfer(task, roll, wh, actor)
        pending = {"to_warehouse_id": dst, "to_warehouse_name": wh.get("name", ""), "from_warehouse_id": src,
                   "transfer_id": trf["id"], "transfer_code": trf.get("code"), "requested_by": actor.get("name", ""),
                   "requested_at": now}
        upd = await db.wms_tasks.find_one_and_update(
            {"id": task_id, "status": {"$nin": list(TERMINAL_TASK)}, "cutting_handoff.received_at": {"$exists": False}},
            {"$set": {"cutting_handoff_pending": pending, "updated_at": now}},
            projection={"_id": 0}, return_document=True)
        if not upd:
            raise HTTPException(status_code=409, detail="Tugas potong baru saja berubah — muat ulang.")
        if not trf.get("reused"):
            await db.sales_orders.update_one({"id": task["order_id"]}, {"$push": {"timeline": {
                "event": "cutting_handoff_transfer", "label": "Serah-terima hasil potong lintas gedung — transfer dibuat",
                "actor": actor.get("name", ""), "at": now,
                "note": f"{task.get('product_name', '')} · {task.get('child_roll_no', '')} → {wh.get('name', '')} ({trf.get('code')})"}}})
        return {**safe_doc(upd), "transfer_required": True, "transfer": trf,
                "message": (f"Hasil potong ada di gedung lain — transfer {trf.get('code')} dibuat (menunggu persetujuan). "
                            "Terima lagi sesudah barang tiba di lokasi Admin Cutting.")}
    handoff = {"from_warehouse_id": task.get("warehouse_id"), "to_warehouse_id": dst,
               "received_by": actor.get("name", ""), "received_by_id": actor.get("id", ""), "received_at": now,
               "transferred": task.get("warehouse_id") != dst,
               **({"transfer_id": (task.get("cutting_handoff_pending") or {}).get("transfer_id")}
                  if task.get("cutting_handoff_pending") else {})}
    claimed = await db.wms_tasks.find_one_and_update(
        {"id": task_id, "status": {"$nin": list(TERMINAL_TASK)}, "cutting_handoff.received_at": {"$exists": False}},
        {"$set": {"cutting_handoff": handoff, "warehouse_id": dst, "updated_at": now},
         "$unset": {"cutting_handoff_pending": ""},
         "$push": {"scan_log": {"id": new_id("scan"), "scan_type": "cutting_handoff", "actor": actor.get("name", ""),
                                "timestamp": now, "from": task.get("warehouse_id"), "to": dst}}},
        projection={"_id": 0}, return_document=True)
    if not claimed:
        cur = safe_doc(await db.wms_tasks.find_one({"id": task_id}, {"_id": 0}))
        if (cur.get("cutting_handoff") or {}).get("received_at"):
            return cur
        raise HTTPException(status_code=409, detail=f"Tugas potong berstatus '{cur.get('status')}' — tidak diterima.")
    if task.get("warehouse_id") != dst:   # roll sudah tiba lewat transfer → tugas & alokasi mengikuti lokasi roll
        await db.sales_orders.update_one({"id": task["order_id"], "allocations.roll_ids": roll["id"]},
                                         {"$set": {"allocations.$.warehouse_id": dst}})
    await db.sales_orders.update_one(
        {"id": task["order_id"]},
        {"$push": {"timeline": {"event": "cutting_handoff", "label": "Hasil potong diterima Admin Cutting",
                                "actor": actor.get("name", ""), "at": now,
                                "note": f"{task.get('product_name', '')} · {task.get('child_roll_no', '')}"
                                        + (" (tiba lewat transfer)" if handoff.get("transferred") else "")}}})
    return safe_doc(claimed)


async def pending_handoffs(order_id: str) -> List[str]:
    rows = await db.wms_tasks.find({"order_id": order_id, "task_subtype": "sample_cut", "roll_id": {"$nin": ["", None]},
                                    "status": {"$nin": ["cancelled"]}, "cutting_handoff.received_at": {"$exists": False}},
                                   {"_id": 0, "child_roll_no": 1}).to_list(200)
    return [r.get("child_roll_no", "") for r in rows]


async def change_catalogue_soft(order: Dict[str, Any], soft_product_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """LN-060-T02 — ganti warna soft: hanya komponen +2 yd berpindah; komponen dasar 1 yd TIDAK disentuh."""
    cat = order.get("catalogue")
    if not cat:
        raise HTTPException(status_code=400, detail="Pesanan ini bukan catalogue.")
    if order.get("status") not in ("waiting_approval", "approved"):
        raise HTTPException(status_code=409, detail="Warna soft hanya bisa diganti sebelum diteruskan ke gudang.")
    if soft_product_id not in {c["product_id"] for c in cat["base"]}:
        raise HTTPException(status_code=400, detail="Warna soft harus salah satu warna dasar catalogue.")
    fresh = await smp.build_catalogue(cat["template_id"], order.get("entity_id", ""), soft_product_id)
    new_cat = {**cat, "soft": fresh["soft"],
               "total_qty": round(len(cat["base"]) * smp.CATALOGUE_BASE_QTY + smp.CATALOGUE_SOFT_QTY, 2)}
    want = smp.catalogue_items(new_cat)
    items = [dict(i) for i in order.get("items", [])]
    for it in items:
        q = want.get(it["product_id"], 0.0)
        it["quantity"] = q
        it["base_quantity"] = q
    from services.config_service import compute_order_pricing
    pricing = await compute_order_pricing(items, order.get("entity_id"), 0,
                                          tax_override=(order.get("tax_override") or "").strip().lower() or None)
    old = (cat.get("soft") or {}).get("color", "—")
    await db.sales_orders.update_one({"id": order["id"]}, {"$set": {
        "catalogue": new_cat, "items": pricing["items"], "total_amount": pricing["total_amount"],
        "discount_total": pricing["discount_total"], "net_subtotal": pricing["net_subtotal"], "dpp": pricing["dpp"],
        "ppn_amount": pricing["ppn_amount"], "grand_total": pricing["grand_total"], "approval_amount": pricing["grand_total"],
        "updated_at": now_iso()},
        "$push": {"timeline": {"event": "catalogue_soft_changed", "label": "Warna soft catalogue diganti",
                               "actor": actor.get("name", ""), "at": now_iso(), "note": f"{old} → {fresh['soft']['color']}"}}})
    return safe_doc(await db.sales_orders.find_one({"id": order["id"]}, {"_id": 0}))


async def receive_order(order_id: str, to_warehouse_id: str, actor: Dict[str, Any],
                        scope_entities: List[str]) -> Dict[str, Any]:
    """Trial 22 Okt (A2) — Admin Cutting menerima SEMUA hasil potong satu pesanan sekaligus (dulu per tugas: catalogue
    9 warna = 9× "Terima hasil potong")."""
    tasks = await db.wms_tasks.find(
        {"order_id": order_id, "task_subtype": "sample_cut", "status": {"$nin": ["cancelled"]},
         "roll_id": {"$nin": [None, ""]}, "cutting_handoff.received_at": {"$exists": False}},
        {"_id": 0, "id": 1, "product_name": 1}).to_list(200)
    if not tasks:
        raise HTTPException(status_code=409, detail="Tidak ada hasil potong pesanan ini yang menunggu diterima.")
    ok, failed, via_transfer = [], [], []
    for t in tasks:
        try:
            res = await receive(t["id"], to_warehouse_id, actor, scope_entities)
            if res.get("transfer_required"):   # FIX-3b (CUT-3) — lintas gedung: menunggu transfer, belum diterima
                via_transfer.append({"task_id": t["id"], "product_name": t.get("product_name", ""),
                                     "transfer": res.get("transfer")})
            else:
                ok.append(res)
        except HTTPException as exc:
            d = exc.detail
            failed.append({"task_id": t["id"], "product_name": t.get("product_name", ""),
                           "error": d.get("message") if isinstance(d, dict) else str(d)})
    return {"received": len(ok), "failed": failed, "transfer_required": via_transfer}

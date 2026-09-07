"""§3-C Jual Sampel (keputusan pemilik 2026-09): harga per satuan roll (yard/meter) dari master
harga sampel TERPISAH per INDUK produk (fallback harga daftar varian); sales mengajukan,
gudang memotong lewat tugas WMS `sample_cut`; saran roll FIFO; pindai roll lain boleh dengan
alasan; potongan = SO jenis `sample` + kwitansi kas/transfer saat itu juga; klaim atomik saat potong.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument

from core_utils import DEFAULT_ENTITY_ID, new_id, next_doc_number, now_iso, safe_doc
from db import db
from services import atomic_claim as _saga
from services.roll_service import insert_child_roll, rebuild_balance

REMNANT_THRESHOLD = 2.0   # sisa induk < 2 satuan → ditandai is_remnant (keputusan implementasi)


async def sample_price_for(product: Dict[str, Any]) -> Dict[str, Any]:
    master = await db.sample_price_master.find_one({"template_id": product.get("template_id")}, {"_id": 0}) if product.get("template_id") else None
    if master and float(master.get("price_per_unit") or 0) > 0:
        return {"price_per_unit": float(master["price_per_unit"]), "source": "master_sampel", "unit": product.get("base_unit") or "yard"}
    return {"price_per_unit": float(product.get("price") or 0), "source": "harga_daftar", "unit": product.get("base_unit") or "yard"}


async def suggest_roll(product_id: str, length: float, entity_ids: List[str]) -> Optional[Dict[str, Any]]:
    """FIFO: roll available tertua yang cukup panjang (sisa ≥ panjang)."""
    q = {"product_id": product_id, "status": "available", "length_remaining": {"$gte": length}}
    if entity_ids:
        q["owner_entity_id"] = {"$in": entity_ids}
    return await db.inventory_rolls.find_one(q, {"_id": 0}, sort=[("created_at", 1)])


async def create_request(payload: Dict[str, Any], actor: Dict[str, Any], entity_ids: List[str]) -> Dict[str, Any]:
    product = await db.products.find_one({"id": payload.get("product_id")}, {"_id": 0})
    customer = await db.customers.find_one({"id": payload.get("customer_id")}, {"_id": 0})
    if not product or not customer:
        raise HTTPException(status_code=404, detail="Produk / pelanggan tidak ditemukan")
    length = round(float(payload.get("length") or 0), 2)
    if length <= 0:
        raise HTTPException(status_code=400, detail="Panjang sampel harus > 0")
    method = (payload.get("payment_method") or "cash").strip().lower()
    if method not in ("cash", "transfer"):
        raise HTTPException(status_code=400, detail="Metode bayar sampel: cash atau transfer")
    price = await sample_price_for(product)
    entity_id = payload.get("entity_id") or customer.get("entity_id") or (entity_ids[0] if entity_ids else DEFAULT_ENTITY_ID)
    sug = await suggest_roll(product["id"], length, entity_ids)
    now = now_iso()
    req = {
        "id": new_id("smp"), "number": await next_doc_number("sample_requests", "number", "SMP-", entity_id=entity_id),
        "entity_id": entity_id, "customer_id": customer["id"], "customer_name": customer.get("name"),
        "product_id": product["id"], "product_name": product.get("name"), "sku": product.get("sku"),
        "template_id": product.get("template_id"), "length": length, "unit": price["unit"],
        "price_per_unit": price["price_per_unit"], "price_source": price["source"],
        "amount": round(length * price["price_per_unit"], 2), "payment_method": method,
        "notes": (payload.get("notes") or "").strip(), "status": "requested",
        "suggested_roll_id": (sug or {}).get("id"), "suggested_roll_no": (sug or {}).get("roll_no"),
        "suggested_warehouse_id": (sug or {}).get("warehouse_id"),
        "requested_by": actor.get("name", ""), "created_at": now, "updated_at": now,
    }
    task = {
        "id": new_id("task"), "flow_type": "sample_cut", "task_subtype": "sample_cut", "status": "pending",
        "entity_id": entity_id, "sample_request_id": req["id"], "sample_number": req["number"],
        "product_id": product["id"], "product_name": product.get("name"), "sku": product.get("sku"),
        "quantity": length, "unit": price["unit"], "customer_name": customer.get("name"),
        "warehouse_id": (sug or {}).get("warehouse_id"), "suggested_roll_id": (sug or {}).get("id"),
        "suggested_roll_no": (sug or {}).get("roll_no"), "source_type": "sample_request", "refs": {"sample_request_id": req["id"]},
        "created_at": now, "updated_at": now,
    }
    req["wms_task_id"] = task["id"]
    await db.sample_requests.insert_one(dict(req))
    try:
        await db.wms_tasks.insert_one(task)
    except Exception:
        await db.sample_requests.delete_one({"id": req["id"]})   # kompensasi: permintaan tanpa tugas dihapus
        raise
    return safe_doc(req)


async def _resolve_roll(req: Dict[str, Any], roll_id: str, epc: str) -> Dict[str, Any]:
    if epc and not roll_id:
        tag = await db.rfid_tags.find_one({"epc": epc.strip()}, {"_id": 0})
        if tag:
            roll_id = tag.get("roll_id")
        else:   # label QR berisi NOMOR ROLL (tanpa RFID) → cari roll_no
            by_no = await db.inventory_rolls.find_one({"roll_no": epc.strip()}, {"_id": 0, "id": 1})
            if not by_no:
                raise HTTPException(status_code=404, detail={"code": "TAG_UNKNOWN", "message": "Kode tidak dikenal (bukan EPC tag maupun nomor roll) — periksa label atau pilih roll manual."})
            roll_id = by_no["id"]
    roll = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0}) if roll_id else None
    if not roll and roll_id:
        roll = await db.inventory_rolls.find_one({"roll_no": roll_id}, {"_id": 0})
    if not roll:
        raise HTTPException(status_code=404, detail="Roll tidak ditemukan")
    if roll.get("product_id") != req["product_id"]:
        raise HTTPException(status_code=400, detail={"code": "ROLL_WRONG_PRODUCT", "message": f"Roll {roll.get('roll_no')} bukan produk {req.get('sku')} — ambil roll produk yang benar."})
    if roll.get("status") != "available":
        raise HTTPException(status_code=409, detail={"code": "ROLL_NOT_AVAILABLE", "message": f"Roll {roll.get('roll_no')} berstatus {roll.get('status')} (terikat pesanan) — tidak boleh dipotong untuk sampel."})
    if float(roll.get("length_remaining") or 0) < float(req["length"]):
        raise HTTPException(status_code=400, detail={"code": "ROLL_TOO_SHORT", "message": f"Sisa roll {roll.get('length_remaining')} < {req['length']} {req.get('unit')}."})
    return roll


async def cut_sample(request_id: str, payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    req = await db.sample_requests.find_one({"id": request_id}, {"_id": 0})
    if not req:
        raise HTTPException(status_code=404, detail="Permintaan sampel tidak ditemukan")
    if req.get("status") != "requested":
        raise HTTPException(status_code=409, detail=f"Permintaan sampel sudah {req.get('status')}")
    roll = await _resolve_roll(req, (payload.get("roll_id") or "").strip(), (payload.get("epc") or "").strip())
    reason = (payload.get("reason") or "").strip()
    if req.get("suggested_roll_id") and roll["id"] != req["suggested_roll_id"] and not reason:
        raise HTTPException(status_code=400, detail={"code": "REASON_REQUIRED",
                            "message": f"Roll ini bukan saran FIFO ({req.get('suggested_roll_no')}). Isi alasan mengapa roll lain dipotong."})
    take = round(float(req["length"]), 2)
    # INV-ATOMIC-01 — klaim permintaan sampel SEBELUM roll dipotong / SO / kwitansi ditulis.
    await _saga.claim("sample_requests", request_id, "sample_cut", precondition={"status": "requested"}, actor=actor.get("name", ""))
    parent = await db.inventory_rolls.find_one_and_update(
        {"id": roll["id"], "status": "available", "length_remaining": {"$gte": take - 0.001}},
        {"$inc": {"length_remaining": -take, "length_initial": -take}, "$set": {"updated_at": now_iso()}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not parent:
        await _saga.release("sample_requests", request_id)
        raise HTTPException(status_code=409, detail="Roll baru saja dipakai proses lain — pindai ulang.")
    rem = round(float(parent.get("length_remaining") or 0), 2)
    await db.inventory_rolls.update_one({"id": roll["id"]}, {"$set": {
        "length_remaining": rem, "length_initial": round(float(parent.get("length_initial") or 0), 2),
        "is_remnant": bool(0 < rem < REMNANT_THRESHOLD)}})
    now = now_iso()
    child = dict(roll)
    child.update({"id": new_id("roll"), "length_initial": take, "length_remaining": 0.0, "status": "sold",
                  "is_remnant": False, "sold_ref": {"type": "sample_request", "id": request_id},
                  "reserved_ref": None, "earmarked_for": None, "sold_at": now, "created_at": now, "updated_at": now})
    child = await insert_child_roll(child, roll)   # P-1: potongan lahir TANPA tag
    await db.inventory_movements.insert_one({
        "id": new_id("mov"), "product_id": roll["product_id"], "warehouse_id": roll["warehouse_id"],
        "owner_entity_id": roll.get("owner_entity_id"), "movement_type": "sample_sale", "quantity": -take,
        "unit": req.get("unit"), "roll_id": child["id"], "parent_roll_id": roll["id"], "qty_rolls": 1,
        "source_document": req["number"], "reference_id": request_id, "timestamp": now, "created_by": actor.get("name", "")})
    await rebuild_balance(roll["product_id"], roll["warehouse_id"], roll.get("owner_entity_id") or req["entity_id"])

    # SO jenis sampel (sudah terpenuhi) + kwitansi kas/transfer saat itu juga
    entity_id = req["entity_id"]
    so_number = await next_doc_number("sales_orders", "number", "SO-", entity_id=entity_id)
    amount = round(float(req["amount"]), 2)
    order = {
        "id": new_id("so"), "number": so_number, "entity_id": entity_id, "order_type": "sample",
        "customer_id": req["customer_id"], "customer_name": req.get("customer_name"),
        "items": [{"product_id": roll["product_id"], "sku": req.get("sku"), "product_name": req.get("product_name"),
                   "quantity": take, "unit": req.get("unit"), "base_unit": req.get("unit"), "base_quantity": take,
                   "price": float(req["price_per_unit"]), "discount_percent": 0, "discount_amount": 0,
                   "subtotal": amount, "line_total": amount, "unit_cost": float(roll.get("unit_cost") or 0), "qty_rolls": 1,
                   "roll_ids": [child["id"]]}],
        "subtotal": amount, "net_subtotal": amount, "discount_total": 0, "tax": 0, "ppn_amount": 0, "dpp": amount,
        "grand_total": amount, "total_amount": amount, "paid_total": 0.0, "payments": [],
        "payment_status": "unpaid", "payment_profile_method": "transfer", "payment_term_code": "transfer",
        "sample_payment_method": req["payment_method"],
        "status": "done", "fulfillment": "sample_cut", "sales_name": req.get("requested_by", ""),
        "notes": f"Penjualan sampel {req['number']} · roll {roll.get('roll_no')} → {child.get('roll_no')}",
        "sample_request_id": request_id, "created_by": actor.get("name", ""), "created_at": now, "updated_at": now,
        "confirmed_at": now, "dispatched_at": now,
    }
    await db.sales_orders.insert_one(dict(order))
    receipt = None
    try:
        from services import ar_receipt_service as _ar
        receipt = await _ar.create_receipt({"customer_id": req["customer_id"], "amount": amount, "method": req["payment_method"],
                                            "entity_id": entity_id, "notes": f"Sampel {req['number']}",
                                            "allocations": [{"order_id": order["id"], "amount": amount}]}, actor)
    except HTTPException as exc:   # kwitansi gagal → SO tetap ada (piutang), dicatat di permintaan
        receipt = {"error": str(exc.detail)}
    try:
        from services import gl_service as _gl
        await _gl.post_sales_order(await db.sales_orders.find_one({"id": order["id"]}, {"_id": 0}))
    except Exception:  # noqa: BLE001 — jurnal pendapatan bisa disusulkan lewat rekonsiliasi GL
        pass
    await db.wms_tasks.update_one({"id": req.get("wms_task_id")}, {"$set": {
        "status": "completed", "completed_at": now, "completed_by": actor.get("name", ""), "roll_id": roll["id"],
        "child_roll_id": child["id"], "updated_at": now}})
    await db.sample_requests.update_one({"id": request_id}, _saga.finish_set({
        "status": "done", "cut_roll_id": roll["id"], "cut_roll_no": roll.get("roll_no"), "child_roll_id": child["id"],
        "child_roll_no": child.get("roll_no"), "off_suggestion_reason": reason if roll["id"] != req.get("suggested_roll_id") else "",
        "sales_order_id": order["id"], "sales_order_number": so_number,
        "receipt_id": (receipt or {}).get("id"), "receipt_number": (receipt or {}).get("number"),
        "receipt_error": (receipt or {}).get("error"), "cut_by": actor.get("name", ""), "cut_at": now, "updated_at": now}))
    return safe_doc(await db.sample_requests.find_one({"id": request_id}, {"_id": 0}))


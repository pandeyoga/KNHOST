"""FE-01 lanjutan (keputusan owner 2026-10-21) — batalkan SATU baris SO yang lahir dari item Pesanan Khusus.

Dipanggil oleh batal item OD sesudah SO dikonversi. Aturan (default implementer):
  * SO belum "terbit" (`amendment_service.is_issued`: Faktur Pajak aktif, pembayaran masuk, sudah dikirim,
    pendapatan dijurnal) — dokumen terbit dikoreksi lewat nota oleh Finance, bukan dengan menghapus baris;
  * roll baris itu belum dipick/dikemas/dikirim (hanya status `reserved` yang boleh dilepas) dan tugas ambil
    gudang untuk baris itu belum mencatat qty terambil;
  * produk baris itu tidak muncul di baris SO lain (reservasi per produk tidak bisa dipisah otomatis).
Efek: roll `reserved` dilepas (pergerakan `release_reservation` + saldo dibangun ulang), tugas ambil yang
belum jalan dibatalkan, baris dikeluarkan dari SO, total dihitung ulang dengan mesin harga yang sama
(`compute_order_pricing`), jejak di `line_cancellations`. Semua syarat dicek SEBELUM ada perubahan.
"""
from typing import Any, Dict

from db import db
from core_utils import new_id, now_iso
from services import config_service
from services.amendment_service import is_issued
from services.roll_service import rebuild_balance
from services.so_status import stage_fields

MOVING_DONE = ("dispatched", "completed", "cancelled")


class SoLineError(ValueError):
    pass


def line_of(order: Dict[str, Any], od_item_id: str) -> Dict[str, Any]:
    return next((i for i in order.get("items") or [] if i.get("special_order_item_id") == od_item_id), None)


async def check(order: Dict[str, Any], od_item_id: str) -> Dict[str, Any]:
    """Semua syarat — tanpa mengubah apa pun. Mengembalikan baris SO yang akan dibatalkan."""
    number = order.get("number") or order.get("id")
    line = line_of(order, od_item_id)
    if not line:
        raise SoLineError(f"Baris SO {number} untuk item ini tidak ditemukan.")
    issued, why = await is_issued(order)
    if issued:
        raise SoLineError(f"SO {number} sudah terbit ({why}) — baris tidak bisa dibatalkan langsung. "
                          "Koreksi lewat Finance (amandemen/nota) atau retur.")
    pid = line.get("product_id")
    if sum(1 for i in order.get("items") or [] if i.get("product_id") == pid) > 1:
        raise SoLineError("Produk yang sama ada di lebih dari satu baris SO — reservasinya tidak bisa dipisah "
                          "otomatis. Minta Admin Sales menyesuaikan SO.")
    moving = await db.inventory_rolls.count_documents(
        {"reserved_ref.id": order["id"], "product_id": pid, "status": {"$nin": ["reserved", "available"]}})
    if moving:
        raise SoLineError(f"{moving} roll baris ini sudah dipick/dikemas/dikirim — selesaikan lewat retur, "
                          "bukan batal item.")
    picked = await db.wms_tasks.find_one(
        {"order_id": order["id"], "product_id": pid, "flow_type": "outbound",
         "status": {"$nin": list(MOVING_DONE)}, "picked_qty": {"$gt": 0}}, {"_id": 0, "id": 1})
    if picked:
        raise SoLineError("Tugas ambil gudang untuk baris ini sudah mencatat qty terambil — batalkan/kembalikan "
                          "pengambilan di gudang dulu.")
    return line


async def cancel_line(order: Dict[str, Any], od_item_id: str, reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    line = await check(order, od_item_id)
    pid = line.get("product_id")
    who = actor.get("name", "")
    from services import atomic_claim as _saga
    await _saga.claim("sales_orders", order["id"], "so_line_cancel",
                      precondition={"status": order["status"]}, actor=who)
    stamp = now_iso()
    rolls = await db.inventory_rolls.find(
        {"reserved_ref.id": order["id"], "product_id": pid, "status": "reserved"}, {"_id": 0}).to_list(1000)
    released, segments = 0.0, set()
    for r in rolls:
        await db.inventory_rolls.update_one(
            {"id": r["id"], "status": "reserved", "reserved_ref.id": order["id"]},
            {"$set": {"status": "available", "reserved_ref": None, "updated_at": stamp}})
        qty = round(float(r.get("length_remaining", 0) or 0), 2)
        released = round(released + qty, 2)
        segments.add((r.get("warehouse_id"), r.get("owner_entity_id")))
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": pid, "warehouse_id": r.get("warehouse_id"),
            "owner_entity_id": r.get("owner_entity_id"), "movement_type": "release_reservation",
            "quantity": qty, "unit": r.get("unit", ""), "lot": r.get("lot", ""), "roll_id": r["id"], "qty_rolls": 1,
            "source_document": order["id"], "timestamp": stamp,
            "note": f"Baris SO dibatalkan (item Pesanan Khusus batal) oleh {who}: {reason}"})
    for wid, oid in segments:
        await rebuild_balance(pid, wid, oid)
    tasks = await db.wms_tasks.update_many(
        {"order_id": order["id"], "product_id": pid, "flow_type": "outbound", "status": {"$nin": list(MOVING_DONE)}},
        {"$set": {"status": "cancelled", "cancel_reason": "Baris SO dibatalkan (item Pesanan Khusus batal)",
                  "cancelled_by": who, "updated_at": stamp}})
    rest = [i for i in order.get("items") or [] if i.get("special_order_item_id") != od_item_id]
    priced = await config_service.compute_order_pricing(
        rest, entity_id=order.get("entity_id") or "",
        order_discount_percent=float(order.get("order_discount_percent", 0) or 0),
        tax_override=(order.get("tax_override") or None))
    patch: Dict[str, Any] = {k: v for k, v in priced.items() if k != "settings"}
    patch["allocations"] = [a for a in order.get("allocations") or [] if a.get("product_id") != pid]
    patch["backorders"] = [b for b in order.get("backorders") or [] if b.get("product_id") != pid]
    patch["has_backorder"] = any(float(b.get("backorder_qty", 0) or 0) > 0.01 for b in patch["backorders"])
    patch["is_split_warehouse"] = len({a.get("warehouse_id") for a in patch["allocations"]}) > 1
    patch["updated_at"] = stamp
    # Keputusan owner 2026-10-21 — entri harga khusus produk baris ini (menunggu/ditolak) ikut dibatalkan.
    from services import so_approvals
    pa = [dict(p) for p in order.get("pending_approvals") or []]
    dropped_sp = so_approvals.cancel_for_removed_products(
        pa, [pid], f"Item Pesanan Khusus dibatalkan: {reason}", who)
    if dropped_sp:
        patch["pending_approvals"] = pa
        patch.update(so_approvals.approval_fields({**order, **patch}, require_validation=False))
    patch.update(stage_fields({**order, **patch}))
    entry = {"id": new_id("slc"), "special_order_item_id": od_item_id, "product_id": pid,
             "sku": line.get("sku", ""), "product_name": line.get("product_name", ""),
             "quantity": line.get("quantity"), "unit": line.get("unit", ""), "line_total": line.get("line_total"),
             "released_qty": released, "released_rolls": len(rolls), "cancelled_tasks": tasks.modified_count,
             "grand_total_before": order.get("grand_total"), "grand_total_after": patch.get("grand_total"),
             "by": who, "at": stamp, "reason": reason}
    await db.sales_orders.update_one({"id": order["id"]}, {**_saga.finish_set(patch), "$push": {"line_cancellations": entry}})
    if dropped_sp:
        await so_approvals.cancel_price_docs(db, dropped_sp, f"Item Pesanan Khusus dibatalkan: {reason}", who)
    return entry

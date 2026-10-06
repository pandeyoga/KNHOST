"""W2-REQ-07 — reservasi bahan makloon sejak PR makloon disetujui (soft-reservation, tanpa jurnal).

Qty bahan = target output ÷ (yield × (1 − susut)) dari resep proses (makloon_prefill).
Reservasi mengurangi ketersediaan untuk komitmen bahan baru (reservasi lain & issue MKO lain),
TIDAK mengubah roll/balance fisik. Realisasi PR→MKO memindah reservasi; issue mengonsumsinya;
cancel/reject melepas. Kekurangan dicatat sebagai `shortage_qty`, bukan reservasi negatif.
"""
from typing import Any, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso, safe_doc

ACTIVE = "active"


async def _on_hand_available(product_id: str, entity_id: str, warehouse_id: str = "") -> float:
    q: Dict[str, Any] = {"product_id": product_id, "owner_entity_id": entity_id}
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    rows = await db.inventory_balances.find(q, {"_id": 0, "available_qty": 1}).to_list(None)   # G3 V3-MRES-02
    return round(sum(float(r.get("available_qty") or 0) for r in rows), 3)


async def apply_to_products(products: List[Dict[str, Any]], entity_id: Optional[str] = None) -> None:
    """Kurangi `available_qty` katalog dengan cadangan makloon aktif + tandai `makloon_reserved_qty`."""
    q: Dict[str, Any] = {"status": "active", "product_id": {"$in": [p["id"] for p in products]}}
    if entity_id and entity_id != "all":
        q["owner_entity_id"] = entity_id
    per: Dict[str, float] = {}
    for m in await db.material_reservations.find(q, {"_id": 0, "product_id": 1, "qty": 1}).to_list(None):
        per[m["product_id"]] = per.get(m["product_id"], 0.0) + float(m.get("qty") or 0)
    for p in products:
        mk = round(per.get(p["id"], 0.0), 2)
        if mk > 0:
            p["makloon_reserved_qty"] = mk
            p["available_qty"] = round(max(float(p.get("available_qty") or 0) - mk, 0.0), 2)



async def reserved_by_others(product_id: str, entity_id: str, exclude_ref_id: str = "") -> float:
    q: Dict[str, Any] = {"product_id": product_id, "owner_entity_id": entity_id, "status": ACTIVE}
    if exclude_ref_id:
        q["ref_id"] = {"$ne": exclude_ref_id}
    rows = await db.material_reservations.find(q, {"_id": 0, "qty": 1}).to_list(None)
    return round(sum(float(r.get("qty") or 0) for r in rows), 3)


async def free_for_commitment(product_id: str, entity_id: str, exclude_ref_id: str = "",
                              warehouse_id: str = "") -> float:
    return round(max(await _on_hand_available(product_id, entity_id, warehouse_id)
                     - await reserved_by_others(product_id, entity_id, exclude_ref_id), 0.0), 3)


async def reserve_for_pr(pr_id: str, actor_name: str = "Sistem") -> List[Dict[str, Any]]:
    """Idempoten: satu reservasi aktif per baris PR makloon (dilewati bila resep belum ada)."""
    from services.pr_sourcing_service import makloon_prefill, SourcingError
    pr = await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0})
    if not pr or pr.get("status") != "approved":
        return []
    out: List[Dict[str, Any]] = []
    for line in pr.get("items") or []:
        if line.get("fulfillment_mode") != "makloon" or not line.get("product_id"):
            continue
        line_no = int(line.get("line_no") or 0)
        if await db.material_reservations.find_one({"pr_id": pr_id, "pr_line_no": line_no,
                                                    "status": {"$in": [ACTIVE, "consumed"]}}, {"_id": 1}):
            continue
        try:
            pre = await makloon_prefill(pr_id, line_no)
        except SourcingError:
            continue
        if not pre.get("ready"):
            continue
        p = pre["payload"]
        pid, need = p.get("material_product_id"), round(float(p.get("material_qty") or 0), 3)
        if not pid or need <= 0:
            continue
        entity_id = pr.get("entity_id") or ""
        # G3 V3-MRES-01 — baca-bebas + insert DISERIALKAN per (bahan, entitas) lewat kunci unik, dan satu
        # baris PR = satu cadangan (id deterministik) → dua PR paralel tidak menjanjikan stok yang sama.
        doc_id = f"mres_{pr_id}_{line_no}"
        if await db.material_reservations.find_one({"id": doc_id, "status": ACTIVE}, {"_id": 1}):
            continue
        lock_id = f"{pid}:{entity_id}"
        for _ in range(50):
            try:
                await db.material_reservation_locks.insert_one({"_id": lock_id, "at": now_iso()})
                break
            except Exception:  # noqa: BLE001 — DuplicateKey: pemegang lain sedang menghitung
                import asyncio as _aio
                await _aio.sleep(0.05)
        else:
            raise SourcingError("Cadangan bahan sedang dihitung proses lain — coba lagi.")
        try:
            free = await free_for_commitment(pid, entity_id)
            qty = round(min(need, free), 3)
            doc = {"id": doc_id, "product_id": pid, "owner_entity_id": entity_id,
               "ref_type": "purchase_requisition", "ref_id": pr_id, "pr_id": pr_id, "pr_number": pr.get("number"),
               "pr_line_no": line_no, "output_product_id": line["product_id"],
               "target_output_qty": pre.get("target_output_qty"), "recipe": pre.get("recipe"),
               "required_qty": need, "qty": qty, "shortage_qty": round(need - qty, 3),
               "source_ref_id": pr.get("source_ref_id") or "", "status": ACTIVE,
               "created_by": actor_name, "created_at": now_iso(), "history": [
                   {"at": now_iso(), "event": "reserved", "qty": qty, "by": actor_name}]}
            await db.material_reservations.insert_one(dict(doc))
        finally:
            await db.material_reservation_locks.delete_one({"_id": lock_id})
        out.append(doc)
    return out


async def transfer_to_mko(pr_id: str, line_no: int, mko: Dict[str, Any]) -> None:
    await db.material_reservations.update_many(
        {"pr_id": pr_id, "pr_line_no": int(line_no), "status": ACTIVE},
        {"$set": {"ref_type": "makloon_order", "ref_id": mko["id"], "mko_id": mko["id"],
                  "mko_number": mko.get("mko_number"), "updated_at": now_iso()},
         "$push": {"history": {"at": now_iso(), "event": "moved_to_mko", "mko_id": mko["id"]}}})


async def consume_for_issue(mko_id: str, product_id: str, issued_qty: float) -> None:
    await db.material_reservations.update_many(
        {"ref_id": mko_id, "product_id": product_id, "status": ACTIVE},
        {"$set": {"status": "consumed", "consumed_qty": round(float(issued_qty), 3), "updated_at": now_iso()},
         "$push": {"history": {"at": now_iso(), "event": "consumed", "qty": issued_qty}}})


async def release(ref_id: str, reason: str, actor_name: str = "Sistem") -> int:
    res = await db.material_reservations.update_many(
        {"ref_id": ref_id, "status": ACTIVE},
        {"$set": {"status": "released", "release_reason": reason, "updated_at": now_iso()},
         "$push": {"history": {"at": now_iso(), "event": "released", "reason": reason, "by": actor_name}}})
    return res.modified_count


async def list_reservations(scope_ids: List[str], ref_id: str = "", product_id: str = "",
                            status: Optional[str] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"owner_entity_id": {"$in": scope_ids}}
    if ref_id:
        q["$or"] = [{"ref_id": ref_id}, {"pr_id": ref_id}]
    if product_id:
        q["product_id"] = product_id
    if status:
        q["status"] = status
    return [safe_doc(d) for d in await db.material_reservations.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)]

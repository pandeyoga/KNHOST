"""P18 MASTER-05 / COMM-01 — gabung pelanggan duplikat (sumber → target) tanpa memutus riwayat.

Semua dokumen ber-`customer_id` sumber dipindah ke target (koleksi dipindai dinamis), roll yang
di-earmark ikut, alamat/kontak sumber ditambahkan ke target, sumber menjadi `merged` (nonaktif,
`merged_into`). Pemilik (sales) target dipertahankan. Idempoten: sumber yang sudah merged → 409.
"""
from typing import Any, Dict

from db import db
from core_utils import now_iso

SKIP = {"customers", "audit_logs", "data_hygiene_log", "sessions"}
ACTIVE_PRICE = {"$in": ["active", "approved", "pending", "draft"]}


class MergeError(ValueError):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status = status


async def _reference_counts(cid: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for coll in await db.list_collection_names():
        if coll in SKIP or coll.startswith("system."):
            continue
        n = await db[coll].count_documents({"customer_id": cid})
        if n:
            out[coll] = n
    n = await db.inventory_rolls.count_documents({"earmarked_for.id": cid})
    if n:
        out["inventory_rolls.earmarked_for"] = n
    return out


async def preview(source: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    _validate(source, target)
    refs = await _reference_counts(source["id"])
    clash = await _price_clash(source["id"], target["id"])
    return {"source_id": source["id"], "target_id": target["id"], "references": refs,
            "total": sum(refs.values()), "price_conflicts": clash, "can_merge": not clash}


def _validate(source: Dict[str, Any], target: Dict[str, Any]) -> None:
    if source["id"] == target["id"]:
        raise MergeError(400, "Pelanggan sumber dan target tidak boleh sama.")
    if source.get("status") == "merged":
        raise MergeError(409, f"Pelanggan {source.get('name')} sudah digabung ke {source.get('merged_into')}.")
    if target.get("status") in ("merged", "inactive"):
        raise MergeError(409, "Pelanggan target harus aktif.")
    if (source.get("entity_id") or "") != (target.get("entity_id") or ""):
        raise MergeError(400, "Penggabungan hanya untuk pelanggan di badan usaha yang sama.")


async def _price_clash(src: str, tgt: str) -> list:
    sp = {p["product_id"] async for p in db.customer_prices.find(
        {"customer_id": src, "status": ACTIVE_PRICE}, {"_id": 0, "product_id": 1})}
    if not sp:
        return []
    tp = {p["product_id"] async for p in db.customer_prices.find(
        {"customer_id": tgt, "status": ACTIVE_PRICE, "product_id": {"$in": list(sp)}}, {"_id": 0, "product_id": 1})}
    return sorted(tp)


async def merge(source: Dict[str, Any], target: Dict[str, Any], *, actor: str, reason: str) -> Dict[str, Any]:
    _validate(source, target)
    clash = await _price_clash(source["id"], target["id"])
    if clash:
        raise MergeError(409, "Kedua pelanggan punya harga khusus aktif untuk produk yang sama "
                              f"({', '.join(clash)}). Tutup salah satu dulu.")
    lock = await db.customers.update_one({"id": source["id"], "status": {"$ne": "merged"}, "merge_lock": {"$exists": False}},
                                         {"$set": {"merge_lock": now_iso()}})
    if not lock.modified_count:
        raise MergeError(409, "Pelanggan sumber sedang/sudah digabung.")
    moved: Dict[str, int] = {}
    for coll in await db.list_collection_names():
        if coll in SKIP or coll.startswith("system."):
            continue
        res = await db[coll].update_many({"customer_id": source["id"]},
                                         {"$set": {"customer_id": target["id"], "merged_from_customer_id": source["id"]}})
        if res.modified_count:
            moved[coll] = res.modified_count
    res = await db.inventory_rolls.update_many({"earmarked_for.id": source["id"]},
                                               {"$set": {"earmarked_for.id": target["id"]}})
    if res.modified_count:
        moved["inventory_rolls.earmarked_for"] = res.modified_count
    have = {(a.get("address") or "").strip().lower() for a in target.get("addresses") or []}
    extra_addr = [a for a in source.get("addresses") or [] if (a.get("address") or "").strip().lower() not in have]
    ts = now_iso()
    await db.customers.update_one({"id": target["id"]}, {
        "$push": {"addresses": {"$each": extra_addr}, "contacts": {"$each": list(source.get("contacts") or [])},
                  "merged_customers": {"id": source["id"], "code": source.get("code"), "name": source.get("name"),
                                       "at": ts, "by": actor, "reason": reason}},
        "$set": {"updated_at": ts}})
    await db.customers.update_one({"id": source["id"]}, {
        "$set": {"status": "merged", "merged_into": target["id"], "merged_at": ts, "merged_by": actor,
                 "merge_reason": reason, "updated_at": ts}, "$unset": {"merge_lock": ""}})
    return {"source_id": source["id"], "target_id": target["id"], "moved": moved,
            "total_moved": sum(moved.values()), "addresses_added": len(extra_addr)}

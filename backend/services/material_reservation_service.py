"""W2-REQ-07 — reservasi bahan makloon sejak PR makloon disetujui (soft-reservation, tanpa jurnal).

Qty bahan = target output ÷ (yield × (1 − susut)) dari resep proses (makloon_prefill).
Reservasi mengurangi ketersediaan untuk komitmen bahan baru (reservasi lain & issue MKO lain).
Realisasi PR→MKO memindah reservasi; issue mengonsumsinya; cancel/reject melepas. Kekurangan dicatat sebagai
`shortage_qty`, bukan reservasi negatif.

FIX-9 (audit 9 Nov 2026 — B3a SSOT-4) — cadangan kini DIKUNCI PER ROLL (`services.makloon_roll_lock`): saat cadangan
lahir (PR disetujui / MKO dibuat) panjangnya dikunci di roll nyata (entri `length_reservations` bertipe makloon),
issue melepas kunci roll yang dikirim (roll lain yang dikirim menggantikan kunci → kunci lama dilepas sejumlah itu),
batal/tolak/selesai melepas semua. Bagian yang tidak bisa dikunci (stok kurang) = `qty − locked_qty` ("cadangan belum
terkunci") — hanya bagian ini yang masih dikurangkan dari angka stok secara agregat (`stock_figures.allocate_makloon`)
dan oleh pengaman komitmen di sini (`unlocked_by_others`); bagian terkunci sudah keluar dari Tersedia lewat saldo roll.
"""
import logging
from typing import Any, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso, safe_doc
from services import makloon_roll_lock as _lk

ACTIVE = "active"
logger = logging.getLogger(__name__)


async def safe_lock(res_id: str, actor_name: str, reason: str) -> Dict[str, Any]:
    """Kunci saat cadangan lahir TIDAK boleh menggagalkan persetujuan PR / pembuatan MKO: gagal → cadangan tetap utuh
    sebagai 'belum terkunci' (tetap dikurangkan dari angka stok) dan bisa dikunci ulang (skrip FIX-9 / issue)."""
    try:
        return await _lk.lock(res_id, actor_name, reason)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[FIX-9] kunci cadangan %s gagal, tetap belum terkunci: %s", res_id, exc)
        return {"lock_error": str(exc)}


def unlocked_qty(m: Dict[str, Any]) -> float:
    """Bagian cadangan yang BELUM terkunci di roll (`qty − locked_qty`, ≥ 0)."""
    return round(max(float(m.get("qty") or 0) - float(m.get("locked_qty") or 0), 0.0), 3)


async def _on_hand_available(product_id: str, entity_id: str, warehouse_id: str = "") -> float:
    q: Dict[str, Any] = {"product_id": product_id, "owner_entity_id": entity_id}
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    rows = await db.inventory_balances.find(q, {"_id": 0, "available_qty": 1}).to_list(None)   # G3 V3-MRES-02
    return round(sum(float(r.get("available_qty") or 0) for r in rows), 3)


async def apply_to_products(products: List[Dict[str, Any]], entity_id: Optional[str] = None) -> None:
    """Kurangi `available_qty` katalog dengan cadangan makloon aktif + tandai `makloon_reserved_qty`.
    FIX-9 — yang dikurangkan hanya bagian BELUM terkunci (bagian terkunci sudah keluar dari saldo)."""
    q: Dict[str, Any] = {"status": "active", "product_id": {"$in": [p["id"] for p in products]}}
    if entity_id and entity_id != "all":
        q["owner_entity_id"] = entity_id
    per: Dict[str, float] = {}
    cut: Dict[str, float] = {}
    for m in await db.material_reservations.find(q, {"_id": 0, "product_id": 1, "qty": 1, "locked_qty": 1}).to_list(None):
        per[m["product_id"]] = per.get(m["product_id"], 0.0) + float(m.get("qty") or 0)
        cut[m["product_id"]] = cut.get(m["product_id"], 0.0) + unlocked_qty(m)
    for p in products:
        mk = round(per.get(p["id"], 0.0), 2)
        if mk > 0:
            p["makloon_reserved_qty"] = mk
            p["available_qty"] = round(max(float(p.get("available_qty") or 0) - cut.get(p["id"], 0.0), 0.0), 2)



async def _active_rows(product_id: str, entity_id: str, exclude_ref_id: str = "") -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"product_id": product_id, "owner_entity_id": entity_id, "status": ACTIVE}
    if exclude_ref_id:
        q["ref_id"] = {"$ne": exclude_ref_id}
    return await db.material_reservations.find(q, {"_id": 0, "qty": 1, "locked_qty": 1}).to_list(None)


async def reserved_by_others(product_id: str, entity_id: str, exclude_ref_id: str = "") -> float:
    """Total cadangan aktif (terkunci + belum terkunci) — untuk TAMPILAN."""
    return round(sum(float(r.get("qty") or 0) for r in await _active_rows(product_id, entity_id, exclude_ref_id)), 3)


async def unlocked_by_others(product_id: str, entity_id: str, exclude_ref_id: str = "") -> float:
    """FIX-9 — cadangan aktif yang BELUM terkunci di roll: satu-satunya bagian yang masih harus dikurangkan dari
    panjang bebas roll/saldo (bagian terkunci sudah tidak bebas). Dipakai pengaman komitmen (SO, issue, cadangan baru)."""
    return round(sum(unlocked_qty(r) for r in await _active_rows(product_id, entity_id, exclude_ref_id)), 3)


async def free_for_commitment(product_id: str, entity_id: str, exclude_ref_id: str = "",
                              warehouse_id: str = "") -> float:
    return round(max(await _on_hand_available(product_id, entity_id, warehouse_id)
                     - await unlocked_by_others(product_id, entity_id, exclude_ref_id), 0.0), 3)


async def own_lock_ids(ref_id: str, product_id: str = "") -> List[str]:
    """Id cadangan AKTIF milik dokumen `ref_id` (MKO) — kuncinya boleh dipakai issue dokumen itu sendiri."""
    q: Dict[str, Any] = {"ref_id": ref_id, "status": ACTIVE}
    if product_id:
        q["product_id"] = product_id
    return [m["id"] async for m in db.material_reservations.find(q, {"_id": 0, "id": 1})]


async def own_locked_qty(ref_id: str, product_id: str = "", warehouse_id: str = "") -> float:
    """Panjang yang terkunci untuk cadangan `ref_id` (opsional hanya di satu gudang) — dihitung dari ROLL."""
    total = 0.0
    for rid in await own_lock_ids(ref_id, product_id):
        total += sum(x["qty"] for x in await _lk.actual_locks(rid) if not warehouse_id or x["warehouse_id"] == warehouse_id)
    return round(total, 3)


async def lock(res_or_id: Any, actor_name: str = "Sistem", reason: str = "") -> Dict[str, Any]:
    """FIX-9 — kunci cadangan ke roll (idempoten; kekurangan tetap 'belum terkunci')."""
    return await _lk.lock(res_or_id, actor_name, reason)


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
        # FIX-9 — replan (lepas lalu cadangkan ulang) dulu memakai id yang SAMA dengan dokumen yang sudah dilepas:
        # sejak index unik `uq_id` (FIX-5) insert gagal DuplicateKey; kunci roll juga merujuk id cadangan → id unik.
        k = 2
        while await db.material_reservations.find_one({"id": doc_id}, {"_id": 1}):
            doc_id = f"mres_{pr_id}_{line_no}_r{k}"
            k += 1
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
               "source_warehouse_id": pr.get("warehouse_id") or "", "locked_qty": 0.0, "locks": [],
               "created_by": actor_name, "created_at": now_iso(), "history": [
                   {"at": now_iso(), "event": "reserved", "qty": qty, "by": actor_name}]}
            await db.material_reservations.insert_one(dict(doc))
            # FIX-9 — kunci ke roll di dalam mutex (bahan × PT) yang sama: cadangan berikutnya menghitung stok bebas
            # sesudah kunci ini benar-benar menempel di roll.
            got = await safe_lock(doc["id"], actor_name, f"cadangan PR {pr.get('number') or pr_id} lahir")
            doc["locked_qty"] = got.get("locked_qty", 0.0)
        finally:
            await db.material_reservation_locks.delete_one({"_id": lock_id})
        out.append(doc)
    return out


async def reserve_for_mko(mko: Dict[str, Any], actor_name: str = "Sistem") -> Optional[Dict[str, Any]]:
    """P05 DEC-07 — kunci bahan saat Order Makloon dibuat (process_only). Idempoten per MKO.

    buy_process tidak memakai stok (bahan dibeli lewat PO tertaut). Kekurangan = `shortage_qty`."""
    if mko.get("mode") != "process_only" or mko.get("status") == "cancelled":
        return None
    if await db.material_reservations.find_one({"ref_id": mko["id"], "status": {"$in": [ACTIVE, "consumed"]}},
                                               {"_id": 1}):
        return None
    pid, entity_id = mko.get("material_product_id"), mko.get("entity_id") or ""
    need = round(float(mko.get("material_qty") or 0), 3)
    if not pid or need <= 0:
        return None
    lock_id = f"{pid}:{entity_id}"
    for _ in range(50):
        try:
            await db.material_reservation_locks.insert_one({"_id": lock_id, "at": now_iso()})
            break
        except Exception:  # noqa: BLE001 — DuplicateKey: pemegang lain sedang menghitung
            import asyncio as _aio
            await _aio.sleep(0.05)
    else:
        raise ValueError("Cadangan bahan sedang dihitung proses lain — coba lagi.")
    try:
        free = await free_for_commitment(pid, entity_id, exclude_ref_id=mko["id"])
        qty = round(max(0.0, min(need, free)), 3)
        doc_id, k = f"mres_{mko['id']}", 2
        while await db.material_reservations.find_one({"id": doc_id}, {"_id": 1}):   # FIX-9 — id unik (lihat PR)
            doc_id = f"mres_{mko['id']}_r{k}"
            k += 1
        doc = {"id": doc_id, "product_id": pid, "owner_entity_id": entity_id,
               "ref_type": "makloon_order", "ref_id": mko["id"], "mko_id": mko["id"],
               "mko_number": mko.get("mko_number"), "output_product_id": mko.get("final_output_product_id"),
               "basis": mko.get("material_basis") or "", "required_qty": need, "qty": qty,
               "shortage_qty": round(need - qty, 3), "status": ACTIVE, "created_by": actor_name,
               "source_warehouse_id": mko_source_warehouse(mko), "locked_qty": 0.0, "locks": [],
               "created_at": now_iso(), "history": [{"at": now_iso(), "event": "reserved", "qty": qty, "by": actor_name}]}
        await db.material_reservations.insert_one(dict(doc))
        got = await safe_lock(doc["id"], actor_name, f"cadangan MKO {mko.get('mko_number') or mko['id']} lahir")
        doc["locked_qty"] = got.get("locked_qty", 0.0)
    finally:
        await db.material_reservation_locks.delete_one({"_id": lock_id})
    return doc


def mko_source_warehouse(mko: Dict[str, Any]) -> str:
    """Gudang sumber bahan MKO: `from_warehouse_id` order, atau gudang asal langkah pertama."""
    if mko.get("from_warehouse_id"):
        return mko["from_warehouse_id"]
    steps = sorted(mko.get("steps") or [], key=lambda s: int(s.get("seq") or 0))
    return (steps[0].get("from_warehouse_id") or "") if steps else ""


async def transfer_to_mko(pr_id: str, line_no: int, mko: Dict[str, Any]) -> None:
    rows = [m["id"] async for m in db.material_reservations.find(
        {"pr_id": pr_id, "pr_line_no": int(line_no), "status": ACTIVE}, {"_id": 0, "id": 1})]
    src = mko_source_warehouse(mko)
    await db.material_reservations.update_many(
        {"pr_id": pr_id, "pr_line_no": int(line_no), "status": ACTIVE},
        {"$set": {"ref_type": "makloon_order", "ref_id": mko["id"], "mko_id": mko["id"],
                  "mko_number": mko.get("mko_number"), "updated_at": now_iso(),
                  **({"source_warehouse_id": src} if src else {})},
         "$push": {"history": {"at": now_iso(), "event": "moved_to_mko", "mko_id": mko["id"]}}})
    # FIX-9 — kunci roll ikut: nomor MKO di rujukan kunci, kunci pindah ke gudang sumber MKO bila berbeda.
    for rid in rows:
        await _lk.update_refs(rid)
        await _lk.relock_to_source(rid, "Sistem", f"cadangan pindah ke MKO {mko.get('mko_number') or mko['id']}")


async def consume_for_issue(mko_id: str, product_id: str, issued_qty: float, actor_name: str = "Sistem") -> None:
    """Issue fisik memakai cadangan. Issue parsial: sisa cadangan tetap aktif (dilepas saat batal/selesai).
    FIX-9 — kunci di roll yang dikirim sudah dilepas oleh issue itu sendiri (atomik, `stock_bucket_service`); di sini
    kunci yang MELEBIHI sisa cadangan dilepas (roll lain yang dikirim menggantikan kunci → kunci lama sejumlah itu)."""
    left = round(float(issued_qty), 3)
    async for r in db.material_reservations.find({"ref_id": mko_id, "product_id": product_id, "status": ACTIVE},
                                                  {"_id": 0, "id": 1, "qty": 1, "consumed_qty": 1}):
        qty = round(float(r.get("qty") or 0), 3)
        use = round(min(qty, left), 3)
        left = round(left - use, 3)
        rest = round(qty - use, 3)
        upd = {"consumed_qty": round(float(r.get("consumed_qty") or 0) + use, 3), "updated_at": now_iso()}
        upd.update({"qty": rest} if rest > 0 else {"status": "consumed", "qty": qty})
        await db.material_reservations.update_one(
            {"id": r["id"], "status": ACTIVE},
            {"$set": upd, "$push": {"history": {"at": now_iso(), "event": "consumed", "qty": use, "remaining": rest}}})
        await _lk.trim(r["id"], actor_name, f"issue {use:g} — kunci melebihi sisa cadangan dilepas")


async def release(ref_id: str, reason: str, actor_name: str = "Sistem") -> int:
    """Lepas cadangan dokumen `ref_id` (PR ditolak/batal/replan, MKO batal/selesai) + SEMUA kuncinya di roll.
    Idempoten: cadangan yang sudah tidak aktif tetapi kuncinya masih menempel (proses mati di tengah) ikut dibersihkan."""
    ids = [m["id"] async for m in db.material_reservations.find({"ref_id": ref_id, "status": ACTIVE}, {"_id": 0, "id": 1})]
    res = await db.material_reservations.update_many(
        {"ref_id": ref_id, "status": ACTIVE},
        {"$set": {"status": "released", "release_reason": reason, "updated_at": now_iso()},
         "$push": {"history": {"at": now_iso(), "event": "released", "reason": reason, "by": actor_name}}})
    stale = [m["id"] async for m in db.material_reservations.find(
        {"ref_id": ref_id, "status": {"$ne": ACTIVE}, "locked_qty": {"$gt": 0}}, {"_id": 0, "id": 1})]
    pairs = set()
    for rid in dict.fromkeys(ids + stale):
        if await _lk.unlock(rid, actor_name, reason, event="released_lock") > 0:
            m = await db.material_reservations.find_one({"id": rid}, {"_id": 0, "product_id": 1, "owner_entity_id": 1})
            if m:
                pairs.add((m.get("product_id"), m.get("owner_entity_id")))
    # Stok yang baru bebas → cadangan LAIN (bahan × PT sama) yang masih punya sisa belum terkunci dikunci sekarang.
    for pid, ent in pairs:
        async for m in db.material_reservations.find({"product_id": pid, "owner_entity_id": ent, "status": ACTIVE},
                                                     {"_id": 0, "id": 1, "qty": 1, "locked_qty": 1}):
            if unlocked_qty(m) > _lk.LOCK_EPS:
                await safe_lock(m["id"], actor_name, "stok bebas dari cadangan yang dilepas")
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

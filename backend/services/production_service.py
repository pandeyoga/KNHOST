"""R6.4 — Produksi In-House (BOM + Work Order).

Koleksi (prefix mfg_*, SCOPED per entitas):
- `mfg_boms` (bom_): resep produksi in-house MULTI-komponen.
    output_product_id + components[{material_product_id, qty_per_unit}] + overhead_per_unit (opsional).
    `qty_per_unit` = kebutuhan bahan per 1 unit (base_unit) output.
- `mfg_work_orders` (wo_): perintah kerja.
    complete = KONSUMSI roll bahan (FEFO, owner+gudang) → PRODUKSI roll barang jadi (Roll-as-SSOT).

GL-safe (invarian INV-GL-DRIFT / GL-3): bahan & barang jadi memakai akun Persediaan 1-1300 yang
sama, sehingga transformasi bahan NET-0 di GL (subledger roll sudah menyeimbangkan). Hanya OVERHEAD
(opsional) yang menambah nilai persediaan → Dr 1-1300 / Cr 5-1100 (Overhead Diserap). Idempotent per WO.

Valuasi: konsumsi bahan pada unit_cost roll (WAC/landed-inclusive) — identik dengan basis GL-3.
Barang jadi dinilai (Σ nilai bahan + overhead) / qty → dibawa sebagai unit_cost roll output.
"""
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso, safe_doc
from services import atomic_claim
from services import roll_service
from services import gl_service

EPS = 0.005

BOM_ACTIVE, BOM_INACTIVE = "active", "inactive"
BOM_STATUSES = (BOM_ACTIVE, BOM_INACTIVE)

WO_DRAFT, WO_RELEASED, WO_COMPLETED, WO_CANCELLED = "draft", "released", "completed", "cancelled"
WO_OPEN = (WO_DRAFT, WO_RELEASED)


def _r(v: Any) -> float:
    return round(float(v or 0), 2)


async def _product(pid: str) -> Dict[str, Any]:
    if not pid:
        return {}
    return await db.products.find_one({"id": pid}, {"_id": 0}) or {}


async def _warehouse(wid: str) -> Dict[str, Any]:
    if not wid:
        return {}
    return await db.warehouses.find_one({"id": wid}, {"_id": 0}) or {}


# ═══ Validasi komponen BOM ═══════════════════════════════════════════════════
async def _validate_components(comps_in: List[Dict[str, Any]], output_pid: str) -> List[Dict[str, Any]]:
    if not comps_in:
        raise ValueError("Minimal satu komponen bahan diperlukan.")
    out: List[Dict[str, Any]] = []
    seen = set()
    for c in comps_in:
        mpid = (c.get("material_product_id") or "").strip()
        if not mpid:
            raise ValueError("material_product_id komponen wajib diisi.")
        if mpid == output_pid:
            raise ValueError("Bahan komponen tidak boleh sama dengan produk output.")
        if mpid in seen:
            raise ValueError("Komponen bahan duplikat pada BOM.")
        mp = await _product(mpid)
        if not mp:
            raise ValueError(f"Produk bahan '{mpid}' tidak ditemukan.")
        qpu = _r(c.get("qty_per_unit"))
        if qpu <= 0:
            raise ValueError("qty_per_unit tiap komponen harus > 0.")
        seen.add(mpid)
        out.append({
            "material_product_id": mpid,
            "sku": mp.get("sku", ""),
            "name": mp.get("name", ""),
            "unit": mp.get("base_unit", "meter"),
            "qty_per_unit": qpu,
        })
    return out


# ═══ BOM CRUD ════════════════════════════════════════════════════════════════
async def create_bom(payload: Dict[str, Any], entity_id: str, actor_name: str = "") -> Dict[str, Any]:
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("Nama BOM wajib diisi.")
    out_pid = (payload.get("output_product_id") or "").strip()
    op = await _product(out_pid)
    if not op:
        raise ValueError("Produk output tidak ditemukan.")
    components = await _validate_components(payload.get("components") or [], out_pid)
    overhead = _r(payload.get("overhead_per_unit"))
    if overhead < 0:
        raise ValueError("overhead_per_unit tidak boleh negatif.")
    doc = {
        "id": new_id("bom"),
        "entity_id": entity_id,
        "name": name,
        "output_product_id": out_pid,
        "output_sku": op.get("sku", ""),
        "output_name": op.get("name", ""),
        "output_unit": op.get("base_unit", "meter"),
        "overhead_per_unit": overhead,
        "components": components,
        "status": BOM_ACTIVE,
        "notes": (payload.get("notes") or "").strip(),
        "created_by": actor_name,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.mfg_boms.insert_one(dict(doc))
    return safe_doc(doc)


async def list_boms(scope: Optional[Dict[str, Any]], status: Optional[str] = None,
                    output_product_id: Optional[str] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {**(scope or {})}
    if status:
        q["status"] = status
    if output_product_id:
        q["output_product_id"] = output_product_id
    return await db.mfg_boms.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)


async def get_bom(bom_id: str, scope: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    return await db.mfg_boms.find_one({"id": bom_id, **(scope or {})}, {"_id": 0})


async def update_bom(bom_id: str, patch: Dict[str, Any],
                     scope: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    cur = await get_bom(bom_id, scope)
    if not cur:
        return None
    upd: Dict[str, Any] = {"updated_at": now_iso()}
    if patch.get("name") is not None:
        if not str(patch["name"]).strip():
            raise ValueError("Nama BOM tidak boleh kosong.")
        upd["name"] = str(patch["name"]).strip()
    if patch.get("notes") is not None:
        upd["notes"] = str(patch["notes"]).strip()
    if patch.get("status") is not None:
        if patch["status"] not in BOM_STATUSES:
            raise ValueError("status BOM harus 'active' atau 'inactive'.")
        upd["status"] = patch["status"]
    if patch.get("overhead_per_unit") is not None:
        ov = _r(patch["overhead_per_unit"])
        if ov < 0:
            raise ValueError("overhead_per_unit tidak boleh negatif.")
        upd["overhead_per_unit"] = ov
    if patch.get("components") is not None:
        upd["components"] = await _validate_components(patch["components"], cur["output_product_id"])
    res = await db.mfg_boms.find_one_and_update(
        {"id": bom_id, **(scope or {})}, {"$set": upd}, return_document=True)
    if res:
        res.pop("_id", None)
    return res


async def delete_bom(bom_id: str, scope: Optional[Dict[str, Any]] = None) -> bool:
    used = await db.mfg_work_orders.count_documents({"bom_id": bom_id, "status": {"$in": list(WO_OPEN)}})
    if used:
        raise ValueError("BOM dipakai Work Order yang masih terbuka — batalkan/selesaikan dulu.")
    res = await db.mfg_boms.delete_one({"id": bom_id, **(scope or {})})
    return res.deleted_count > 0


# ═══ Ketersediaan & rencana bahan ════════════════════════════════════════════
_FREE = {"$subtract": ["$length_remaining", {"$ifNull": ["$length_reserved", 0]}]}


def eligible_material_q(product_id: str, warehouse_id: str, owner_entity_id: str) -> Dict[str, Any]:
    """IX-11 — kontrak kelayakan bahan produksi: owner+gudang, available, TIDAK ditahan QC."""
    return {"product_id": product_id, "warehouse_id": warehouse_id, "owner_entity_id": owner_entity_id,
            "status": "available", "length_remaining": {"$gt": 0},
            "inspection.hold.held": {"$ne": True}}


async def _available_qty(product_id: str, warehouse_id: str, owner_entity_id: str) -> float:
    # Panjang BEBAS (sisa − reservasi panjang) pada roll yang layak produksi.
    agg = await db.inventory_rolls.aggregate([
        {"$match": eligible_material_q(product_id, warehouse_id, owner_entity_id)},
        {"$group": {"_id": None, "total": {"$sum": {"$max": [_FREE, 0]}}}},
    ]).to_list(1)
    return _r(float(agg[0]["total"]) if agg else 0.0)


def frozen_components(wo: Dict[str, Any]) -> List[Dict[str, Any]]:
    """GN-06 — resep yang DIBEKUKAN di WO (bukan BOM terbaru). WO lama: dari material_plan awal."""
    return wo.get("bom_components") or [
        {k: p.get(k) for k in ("material_product_id", "sku", "name", "unit", "qty_per_unit")}
        for p in (wo.get("material_plan") or [])]


async def _material_plan(bom: Dict[str, Any], planned_qty: float,
                         warehouse_id: str, entity_id: str) -> List[Dict[str, Any]]:
    plan: List[Dict[str, Any]] = []
    for c in bom.get("components", []):
        need = _r(c["qty_per_unit"] * planned_qty)
        avail = await _available_qty(c["material_product_id"], warehouse_id, entity_id)
        plan.append({
            "material_product_id": c["material_product_id"], "sku": c.get("sku", ""),
            "name": c.get("name", ""), "unit": c.get("unit", "meter"),
            "qty_per_unit": c["qty_per_unit"], "required_qty": need,
            "available_qty": avail, "sufficient": avail + EPS >= need,
        })
    return plan


# ═══ Nomor WO ════════════════════════════════════════════════════════════════
async def _next_wo_number() -> str:
    """KN-A12 — sequence ATOMIK bersama (find_one_and_update $inc), bukan 'nomor tertinggi + 1'."""
    from core_utils import next_doc_number
    return await next_doc_number("mfg_work_orders", "wo_number", "WO-", width=5, scheme="shared")


# ═══ Work Order — CRUD & transisi ════════════════════════════════════════════
async def create_work_order(payload: Dict[str, Any], entity_id: str,
                            actor_name: str = "") -> Dict[str, Any]:
    bom = await get_bom((payload.get("bom_id") or "").strip(), {"entity_id": entity_id})
    if not bom:
        raise ValueError("BOM tidak ditemukan pada entitas ini.")
    if bom.get("status") != BOM_ACTIVE:
        raise ValueError("BOM non-aktif tidak bisa dijadikan Work Order.")
    planned_qty = _r(payload.get("planned_qty"))
    if planned_qty <= 0:
        raise ValueError("Jumlah produksi (planned_qty) harus > 0.")
    warehouse_id = (payload.get("warehouse_id") or "").strip()
    wh = await _warehouse(warehouse_id)
    if not wh:
        raise ValueError("Gudang produksi tidak ditemukan.")
    plan = await _material_plan(bom, planned_qty, warehouse_id, entity_id)
    doc = {
        "id": new_id("wo"),
        "wo_number": await _next_wo_number(),
        "entity_id": entity_id,
        "bom_id": bom["id"],
        "bom_name": bom.get("name", ""),
        "output_product_id": bom["output_product_id"],
        "output_sku": bom.get("output_sku", ""),
        "output_name": bom.get("output_name", ""),
        "output_unit": bom.get("output_unit", "meter"),
        "warehouse_id": warehouse_id,
        "warehouse_name": wh.get("name", ""),
        "planned_qty": planned_qty,
        "overhead_per_unit": _r(bom.get("overhead_per_unit")),
        "bom_components": [dict(c) for c in bom.get("components", [])],
        "bom_version_at": bom.get("updated_at") or bom.get("created_at", ""),
        "material_plan": plan,
        "status": WO_DRAFT,
        "notes": (payload.get("notes") or "").strip(),
        "consumed": [],
        "produced_roll_ids": [],
        "produced_qty": 0.0,
        "material_cost": 0.0,
        "overhead_cost": 0.0,
        "total_cost": 0.0,
        "unit_cost": 0.0,
        "je_id": "",
        "created_by": actor_name,
        "created_at": now_iso(),
        "released_at": "",
        "completed_at": "",
    }
    await db.mfg_work_orders.insert_one(dict(doc))
    return safe_doc(doc)


async def list_work_orders(scope: Optional[Dict[str, Any]], status: Optional[str] = None,
                           bom_id: Optional[str] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {**(scope or {})}
    if status:
        q["status"] = status
    if bom_id:
        q["bom_id"] = bom_id
    return await db.mfg_work_orders.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)


async def get_work_order(wo_id: str, scope: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    wo = await db.mfg_work_orders.find_one({"id": wo_id, **(scope or {})}, {"_id": 0})
    if wo and wo.get("status") in WO_OPEN:
        # refresh ketersediaan (informatif) atas resep BEKU WO
        wo["material_plan"] = await _material_plan({"components": frozen_components(wo)}, wo.get("planned_qty", 0),
                                                   wo.get("warehouse_id", ""), wo.get("entity_id", ""))
    return wo


async def release_work_order(wo_id: str, scope: Optional[Dict[str, Any]] = None,
                             actor_name: str = "") -> Dict[str, Any]:
    wo = await db.mfg_work_orders.find_one({"id": wo_id, **(scope or {})}, {"_id": 0})
    if not wo:
        raise ValueError("Work Order tidak ditemukan.")
    if wo["status"] == WO_RELEASED:
        return wo
    if wo["status"] != WO_DRAFT:
        raise ValueError(f"Work Order status '{wo['status']}' tidak bisa dirilis.")
    comps = frozen_components(wo)
    plan = await _material_plan({"components": comps}, wo["planned_qty"], wo["warehouse_id"], wo["entity_id"])
    res = await db.mfg_work_orders.update_one(
        {"id": wo_id, "status": WO_DRAFT, atomic_claim.LOCK: {"$exists": False}},
        {"$set": {"status": WO_RELEASED, "bom_components": comps, "material_plan": plan,
                  "released_at": now_iso(), "released_by": actor_name, "updated_at": now_iso()}})
    if res.modified_count != 1:
        raise HTTPException(status_code=409, detail="Work Order berubah bersamaan — muat ulang layar.")
    return await db.mfg_work_orders.find_one({"id": wo_id}, {"_id": 0})


async def cancel_work_order(wo_id: str, scope: Optional[Dict[str, Any]] = None,
                            actor_name: str = "", reason: str = "") -> Dict[str, Any]:
    wo = await db.mfg_work_orders.find_one({"id": wo_id, **(scope or {})}, {"_id": 0})
    if not wo:
        raise ValueError("Work Order tidak ditemukan.")
    if wo["status"] == WO_CANCELLED:
        return wo
    if wo["status"] == WO_COMPLETED:
        raise ValueError("Work Order yang sudah selesai tidak bisa dibatalkan.")
    res = await db.mfg_work_orders.update_one(
        {"id": wo_id, "status": {"$in": list(WO_OPEN)}, atomic_claim.LOCK: {"$exists": False}},
        {"$set": {"status": WO_CANCELLED, "cancel_reason": reason, "cancelled_by": actor_name,
                  "cancelled_at": now_iso(), "updated_at": now_iso()}})
    if res.modified_count != 1:
        raise HTTPException(status_code=409, detail="Work Order sedang diselesaikan/berubah — tidak bisa dibatalkan sekarang.")
    return await db.mfg_work_orders.find_one({"id": wo_id}, {"_id": 0})


# ═══ Konsumsi roll bahan (FEFO) — mirror cycle_count (Roll-as-SSOT safe) ══════
class MaterialShortage(Exception):
    """Stok layak berkurang di tengah konsumsi (balapan/hold) — kontribusi operasi ini dibalik."""


async def _consume_material(product_id: str, warehouse_id: str, owner_entity_id: str,
                            need: float, wo_id: str, op_id: str) -> Tuple[float, float, List[str]]:
    """GN-06/IX-11 — kurangi roll layak (FEFO) sebesar `need` dengan CAS panjang BEBAS per roll.

    Tiap potongan dicatat sebagai movement ber-`operation_id` (dasar kompensasi/resume).
    Return (qty, nilai, lot_ids_bahan); kurang → MaterialShortage (pemanggil membalik operasi).
    """
    need = _r(need)
    if need <= EPS:
        return 0.0, 0.0, []
    q = eligible_material_q(product_id, warehouse_id, owner_entity_id)
    consumed_qty, value, lot_ids = 0.0, 0.0, []
    for _attempt in range(3):
        rolls = await db.inventory_rolls.find(q, {"_id": 0}).sort(
            [("created_at", 1), ("length_remaining", -1)]).to_list(5000)
        for r in rolls:
            if need - consumed_qty <= EPS:
                break
            free = float(r.get("length_remaining") or 0) - float(r.get("length_reserved") or 0)
            take = round(min(free, need - consumed_qty), 2)
            if take <= EPS:
                continue
            won = await db.inventory_rolls.find_one_and_update(
                {**q, "id": r["id"], "$expr": {"$gte": [_FREE, take - EPS]}},
                [{"$set": {"length_remaining": {"$round": [{"$subtract": ["$length_remaining", take]}, 2]},
                           "updated_at": now_iso()}},
                 {"$set": {"status": {"$cond": [{"$lte": ["$length_remaining", EPS]}, "consumed", "$status"]}}}],
                projection={"_id": 0, "id": 1})
            if not won:
                continue  # roll berubah/di-hold bersamaan — dicoba lagi di putaran berikut
            uc = float(r.get("unit_cost") or r.get("base_unit_cost") or 0)
            await db.inventory_movements.insert_one({
                "id": new_id("mov"), "product_id": product_id, "warehouse_id": warehouse_id,
                "owner_entity_id": owner_entity_id, "movement_type": "production_consume",
                "quantity": -take, "unit": r.get("unit", "meter"), "lot": r.get("lot", ""),
                "lot_id": r.get("lot_id", ""), "roll_id": r["id"], "unit_cost": uc,
                "qty_rolls": 1, "source_document": wo_id, "operation_id": op_id, "timestamp": now_iso(),
            })
            value += take * uc
            if r.get("lot_id") and r["lot_id"] not in lot_ids:
                lot_ids.append(r["lot_id"])
            consumed_qty = round(consumed_qty + take, 2)
        if need - consumed_qty <= EPS:
            break
    await roll_service.rebuild_balance(product_id, warehouse_id, owner_entity_id)
    if need - consumed_qty > EPS:
        raise MaterialShortage(f"Stok bahan {product_id} tidak cukup saat dikonsumsi: butuh {need:g}, "
                               f"terambil {consumed_qty:g} (dipakai proses lain/ditahan QC).")
    return round(consumed_qty, 2), round(value, 2), lot_ids


async def reverse_operation(op_id: str) -> float:
    """Balik HANYA kontribusi operasi `op_id` ($inc, bukan $set) — idempoten per movement."""
    restored, segs = 0.0, set()
    async for m in db.inventory_movements.find(
            {"operation_id": op_id, "movement_type": "production_consume", "reversed": {"$ne": True}}, {"_id": 0}):
        mark = await db.inventory_movements.update_one(
            {"id": m["id"], "reversed": {"$ne": True}}, {"$set": {"reversed": True, "reversed_at": now_iso()}})
        if mark.modified_count != 1:
            continue
        qty = -float(m["quantity"])
        await db.inventory_rolls.update_one({"id": m["roll_id"]}, [
            {"$set": {"status": {"$cond": [{"$eq": ["$status", "consumed"]}, "available", "$status"]},
                      "length_remaining": {"$round": [{"$add": ["$length_remaining", qty]}, 2]},
                      "updated_at": now_iso()}}])
        await db.inventory_movements.insert_one({
            **{k: m.get(k) for k in ("product_id", "warehouse_id", "owner_entity_id", "unit", "lot", "lot_id",
                                     "roll_id", "unit_cost", "source_document", "operation_id")},
            "id": new_id("mov"), "movement_type": "production_consume_reversal", "quantity": qty,
            "qty_rolls": 1, "reverses": m["id"], "timestamp": now_iso()})
        restored += qty
        segs.add((m["product_id"], m["warehouse_id"], m["owner_entity_id"]))
    for seg in segs:
        await roll_service.rebuild_balance(*seg)
    return round(restored, 2)


# ═══ Selesaikan WO — konsumsi bahan → produksi barang jadi ═══════════════════
async def complete_work_order(wo_id: str, scope: Optional[Dict[str, Any]] = None,
                              actor_name: str = "") -> Dict[str, Any]:
    """GN-06/IX-11 — klaim WO (released, tanpa kunci) → konsumsi CAS (resep beku, bahan layak) →
    output → JE, tiap tahap durable di `completion` sehingga retry melanjutkan, bukan menggandakan."""
    wo = await db.mfg_work_orders.find_one({"id": wo_id, **(scope or {})}, {"_id": 0})
    if not wo:
        raise ValueError("Work Order tidak ditemukan.")
    if wo["status"] == WO_COMPLETED:
        return wo  # idempotent
    if wo["status"] == WO_CANCELLED:
        raise ValueError("Work Order dibatalkan — tidak bisa diselesaikan.")
    if wo["status"] == WO_DRAFT:
        raise ValueError("Work Order masih draft — rilis dulu agar resep & rencana bahan dibekukan.")
    comps = frozen_components(wo)
    if not comps:
        raise ValueError("Work Order tidak punya resep bahan yang dibekukan.")
    entity_id, warehouse_id = wo["entity_id"], wo["warehouse_id"]
    planned_qty = _r(wo["planned_qty"])
    stage = (wo.get("completion") or {}).get("stage", "")

    if stage not in ("consumed", "output"):
        for c in comps:  # fail-fast 400 sebelum klaim & mutasi
            need = _r(c["qty_per_unit"] * planned_qty)
            avail = await _available_qty(c["material_product_id"], warehouse_id, entity_id)
            if avail + EPS < need:
                raise ValueError(f"Stok bahan {c.get('name') or c['material_product_id']} tidak cukup: "
                                 f"butuh {need:g} {c.get('unit', '')}, tersedia {avail:g} (roll ditahan QC/dipesan tidak dihitung).")

    wo = await atomic_claim.claim("mfg_work_orders", wo_id, "complete", precondition={"status": WO_RELEASED},
                                  actor=actor_name)
    comp = dict(wo.get("completion") or {})
    try:
        if comp.get("stage") not in ("consumed", "output"):
            if comp.get("op_id"):
                await reverse_operation(comp["op_id"])  # sisa percobaan yang mati di tengah konsumsi
            comp = {"op_id": new_id("wop"), "stage": "consuming", "started_at": now_iso()}
            await db.mfg_work_orders.update_one({"id": wo_id}, {"$set": {"completion": comp}})
            consumed: List[Dict[str, Any]] = []
            try:
                for c in comps:
                    need = _r(c["qty_per_unit"] * planned_qty)
                    qty, val, lots_in = await _consume_material(c["material_product_id"], warehouse_id,
                                                                entity_id, need, wo_id, comp["op_id"])
                    consumed.append({"material_product_id": c["material_product_id"], "sku": c.get("sku", ""),
                                     "name": c.get("name", ""), "unit": c.get("unit", "meter"),
                                     "qty": qty, "value": round(val, 2), "lot_ids": lots_in})
            except MaterialShortage as exc:
                await reverse_operation(comp["op_id"])
                await db.mfg_work_orders.update_one({"id": wo_id}, {"$unset": {"completion": "", atomic_claim.LOCK: ""}})
                raise HTTPException(status_code=409, detail=f"{exc} Tidak ada stok yang berubah.") from exc
            comp.update({"stage": "consumed", "consumed": consumed})
            await db.mfg_work_orders.update_one({"id": wo_id}, {"$set": {"completion": comp}})

        consumed = comp["consumed"]
        material_cost = round(sum(float(c["value"]) for c in consumed), 2)
        material_lot_ids: List[str] = []
        for c in consumed:
            material_lot_ids.extend([lot for lot in c.get("lot_ids", []) if lot not in material_lot_ids])
        overhead_cost = round(_r(wo.get("overhead_per_unit")) * planned_qty, 2)
        total_cost = round(material_cost + overhead_cost, 2)
        unit_cost = round(total_cost / planned_qty, 4) if planned_qty > 0 else 0.0

        roll = await db.inventory_rolls.find_one(
            {"acquired.via": "production_output", "acquired.ref_id": wo_id}, {"_id": 0})
        if not roll:
            roll = await roll_service.create_inbound_roll(
                wo["output_product_id"], warehouse_id, entity_id, planned_qty,
                acquired_via="production_output", ref_id=wo_id, created_by=actor_name or "System",
                unit_cost=unit_cost, lot_source="production",
                lot_source_ref={"type": "work_order", "id": wo_id, "number": wo.get("wo_number", "")},
                parent_lot_ids=material_lot_ids)
        comp.update({"stage": "output", "roll_id": roll["id"]})
        await db.mfg_work_orders.update_one({"id": wo_id}, {"$set": {"completion": comp}})

        je = await gl_service.post_production_output(
            wo_id=wo_id, entity_id=entity_id, overhead=overhead_cost, label=wo.get("wo_number", ""))
        if not je and overhead_cost > EPS:
            je = await db.journal_entries.find_one(
                {"source_type": "production_output", "source_id": wo_id}, {"_id": 0, "id": 1})
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — kunci dibiarkan (terlihat di Kunci Saga), retry melanjutkan tahap
        await atomic_claim.mark_failed("mfg_work_orders", wo_id, str(exc))
        raise

    await db.mfg_work_orders.update_one({"id": wo_id}, atomic_claim.finish_set({
        "status": WO_COMPLETED, "consumed": consumed, "completion": {**comp, "stage": "done"},
        "produced_roll_ids": [roll["id"]], "produced_qty": planned_qty,
        "output_lot_id": roll.get("lot_id", ""), "output_lot_number": roll.get("lot", ""),
        "input_lot_ids": material_lot_ids,
        "material_cost": material_cost, "overhead_cost": overhead_cost,
        "total_cost": total_cost, "unit_cost": unit_cost,
        "je_id": (je or {}).get("id", ""), "completed_by": actor_name,
        "completed_at": now_iso(), "updated_at": now_iso()}))
    return await db.mfg_work_orders.find_one({"id": wo_id}, {"_id": 0})


# ═══ Ringkasan (dashboard produksi) ══════════════════════════════════════════
async def summary(scope: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    q = {**(scope or {})}
    wos = await db.mfg_work_orders.find(q, {"_id": 0}).to_list(5000)
    by_status: Dict[str, int] = {}
    produced_value = 0.0
    produced_qty = 0.0
    for w in wos:
        by_status[w.get("status", "?")] = by_status.get(w.get("status", "?"), 0) + 1
        if w.get("status") == WO_COMPLETED:
            produced_value += _r(w.get("total_cost"))
            produced_qty += _r(w.get("produced_qty"))
    boms = await db.mfg_boms.count_documents(q)
    return {
        "boms": boms,
        "work_orders": len(wos),
        "by_status": by_status,
        "completed": by_status.get(WO_COMPLETED, 0),
        "open": by_status.get(WO_DRAFT, 0) + by_status.get(WO_RELEASED, 0),
        "produced_qty": round(produced_qty, 2),
        "produced_value": round(produced_value, 2),
        "generated_at": now_iso(),
    }

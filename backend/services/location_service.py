"""Location (Zona → Lemari/Rak → Tingkat → Bin) & Putaway — Fase 5, diperkuat P02.

Struktur lokasi EMBEDDED di `warehouses.zones` (SSOT tunggal). Rack lama boleh punya `bins`
langsung (tanpa tingkat). Bin diidentifikasi flat `id`; `inventory_rolls.bin_id` menunjuk ke sana.
PUTAWAY hanya mengubah `roll.bin_id` → tidak memengaruhi balance (SSOT-safe).
P02: evaluator bersama (`placement_rules`), kapasitas = jumlah roll, okupansi per satuan (DEV-F03),
struktur dilindungi (DEV-F02) + daftar alamat yatim.
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso
from entity_scope import EntityContext, resolve_list_scope
from services import placement_rules as pr


def flatten_bins(warehouse: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Semua bin dgn path lengkap. Dukung rack.levels[].bins (baru) & rack.bins (lama)."""
    out: List[Dict[str, Any]] = []
    for n in pr.flatten_nodes(warehouse):
        b, z, rk, lv = n["bin"], n["zone"], n["rack"], n["level"]
        eff = pr.effective(warehouse, n)
        out.append({"zone": z.get("name", ""), "zone_id": z.get("id"), "rack": rk.get("name", ""), "rack_id": rk.get("id"),
                    "bin_id": b.get("id"), "code": b.get("code", ""),
                    "capacity": float(b.get("capacity", 0) or 0),
                    "capacity_rolls": eff["capacity_rolls"], "function": eff["function"],
                    "single_sku": eff["single_sku"], "single_lot": eff["single_lot"],
                    "level": (lv or {}).get("name", ""), "level_id": (lv or {}).get("id"),
                    "path": "/".join(x for x in (z.get("name", ""), rk.get("name", ""), (lv or {}).get("name", ""), b.get("code", "")) if x)})
    return out


async def _bin_occupancy(warehouse_id: str) -> Dict[str, Dict[str, Any]]:
    """Isi FISIK per bin (semua owner — kapasitas fisik tidak boleh dihitung per filter owner), per satuan."""
    from services.roll_service import PHYSICAL_STATUS_TO_BUCKET
    occ: Dict[str, Dict[str, Any]] = {}
    async for r in db.inventory_rolls.find(
            {"warehouse_id": warehouse_id, "length_remaining": {"$gt": 0},
             "status": {"$in": list(PHYSICAL_STATUS_TO_BUCKET.keys())}},
            {"_id": 0, "bin_id": 1, "length_remaining": 1, "unit": 1}):
        d = occ.setdefault(r.get("bin_id") or "__unassigned__", {"by_unit": {}, "rolls": 0})
        u = r.get("unit") or "?"
        d["by_unit"][u] = round(d["by_unit"].get(u, 0.0) + float(r.get("length_remaining") or 0), 2)
        d["rolls"] += 1
    return occ


def _merge_units(rows: List[Dict[str, float]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for r in rows:
        for u, v in r.items():
            out[u] = round(out.get(u, 0.0) + v, 2)
    return out


async def warehouse_locations(warehouse_id: str, ctx: EntityContext, entity_id: Optional[str]) -> Dict[str, Any]:
    wh = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0})
    if not wh:
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    bins = flatten_bins(wh)
    occ = await _bin_occupancy(warehouse_id)
    known = {b["bin_id"] for b in bins}
    for b in bins:
        o = occ.get(b["bin_id"], {"by_unit": {}, "rolls": 0})
        b["occupied_by_unit"] = o["by_unit"]
        b["roll_count"] = o["rolls"]
        b["occupied"] = round(sum(o["by_unit"].values()), 2) if len(o["by_unit"]) == 1 else None
        b["mixed_units"] = len(o["by_unit"]) > 1
        b["utilization"] = round(o["rolls"] / b["capacity_rolls"] * 100, 1) if b["capacity_rolls"] else None
    ua = occ.get("__unassigned__", {"by_unit": {}, "rolls": 0})
    orphan = [v for k, v in occ.items() if k != "__unassigned__" and k not in known]
    site = await db.warehouse_sites.find_one({"id": wh.get("site_id")}, {"_id": 0, "name": 1}) if wh.get("site_id") else None
    caps = [b["capacity_rolls"] for b in bins if b["capacity_rolls"]]
    return {
        "warehouse": {"id": wh["id"], "code": wh.get("code"), "name": wh.get("name"), "site": (site or {}).get("name", "")},
        "zones": wh.get("zones", []),
        "bins": bins,
        "unassigned": {"by_unit": ua["by_unit"], "rolls": ua["rolls"]},
        "orphan": {"by_unit": _merge_units([o["by_unit"] for o in orphan]), "rolls": sum(o["rolls"] for o in orphan)},
        "total_occupied_by_unit": _merge_units([o["by_unit"] for o in occ.values()]),
        "total_rolls": sum(o["rolls"] for o in occ.values()),
        "capacity_rolls_total": sum(caps) if caps else None,
        "bins_without_capacity": sum(1 for b in bins if not b["capacity_rolls"]),
        "bin_count": len(bins),
    }


def _ensure_ids(zones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Beri id pada node baru (tanpa id) + normalisasi kapasitas/fungsi/rules."""
    def norm(node, prefix):
        if not node.get("id"):
            node["id"] = new_id(prefix)
        if "function" in node:
            f = pr._norm(node.get("function"))
            node["function"] = f if f in pr.NODE_FUNCTIONS else ""
        if "rules" in node:
            node["rules"] = pr.node_rules(node)

    for z in zones or []:
        norm(z, "zone")
        for rk in z.get("racks", []) or []:
            norm(rk, "rack")
            for lvl in rk.get("levels", []) or []:
                norm(lvl, "level")
            for b in [b for lvl in rk.get("levels", []) or [] for b in lvl.get("bins", []) or []] + list(rk.get("bins", []) or []):
                norm(b, "bin")
                b["capacity"] = float(b.get("capacity", 0) or 0)
                cr = int(float(b.get("capacity_rolls") or 0))
                if cr < 0:
                    raise HTTPException(status_code=400, detail=f"Kapasitas roll bin {b.get('code')} tidak boleh negatif.")
                b["capacity_rolls"] = cr or None
    return zones


def _all_ids(zones: List[Dict[str, Any]]) -> List[str]:
    ids = []
    for z in zones or []:
        ids.append(z.get("id"))
        for rk in z.get("racks", []) or []:
            ids.append(rk.get("id"))
            for lvl in rk.get("levels", []) or []:
                ids.append(lvl.get("id"))
                ids += [b.get("id") for b in lvl.get("bins", []) or []]
            ids += [b.get("id") for b in rk.get("bins", []) or []]
    return ids


async def _bin_refs(warehouse_id: str, bin_ids: List[str]) -> Dict[str, Dict[str, int]]:
    """Referensi aktif ke bin: roll fisik & tugas gudang belum selesai."""
    from services.roll_service import PHYSICAL_STATUS_TO_BUCKET
    refs: Dict[str, Dict[str, int]] = {}
    async for r in db.inventory_rolls.aggregate([
            {"$match": {"warehouse_id": warehouse_id, "bin_id": {"$in": bin_ids},
                        "status": {"$in": list(PHYSICAL_STATUS_TO_BUCKET.keys())}, "length_remaining": {"$gt": 0}}},
            {"$group": {"_id": "$bin_id", "n": {"$sum": 1}}}]):
        refs.setdefault(r["_id"], {"rolls": 0, "tasks": 0})["rolls"] = r["n"]
    async for t in db.wms_tasks.aggregate([
            {"$match": {"bin_id": {"$in": bin_ids}, "status": {"$nin": ["done", "completed", "cancelled", "dispatched"]}}},
            {"$group": {"_id": "$bin_id", "n": {"$sum": 1}}}]):
        refs.setdefault(t["_id"], {"rolls": 0, "tasks": 0})["tasks"] = t["n"]
    return refs


async def save_warehouse_structure(warehouse_id: str, zones: List[Dict[str, Any]]) -> Dict[str, Any]:
    wh = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0})
    if not wh:
        raise HTTPException(status_code=404, detail="Gudang tidak ditemukan")
    zones = _ensure_ids(zones or [])
    ids = _all_ids(zones)
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="ID node lokasi ganda — setiap zona/lemari/tingkat/bin harus unik.")
    new_bins = flatten_bins({"zones": zones})
    codes = [b["code"].lower() for b in new_bins if b.get("code")]
    if len(codes) != len(set(codes)):
        raise HTTPException(status_code=400, detail="Kode bin harus unik dalam satu gudang.")
    removed = sorted({b["bin_id"] for b in flatten_bins(wh)} - {b["bin_id"] for b in new_bins})
    if any(not (b.get("code") or "").strip() for b in new_bins):
        raise HTTPException(status_code=400, detail="Setiap bin wajib punya kode (dipakai untuk label & scan).")
    if removed:
        refs = await _bin_refs(warehouse_id, removed)
        if refs:
            old = {b["bin_id"]: b["code"] for b in flatten_bins(wh)}
            parts = [f"{old.get(k, k)} ({v['rolls']} roll, {v['tasks']} tugas)" for k, v in refs.items()]
            raise HTTPException(status_code=409, detail={
                "code": "LOCATION_IN_USE", "bins": refs,
                "message": f"Bin masih dipakai: {', '.join(parts)}. Pindahkan roll / selesaikan tugas dulu — "
                           "hapus ditolak agar alamat stok tidak hilang. Ganti nama tetap boleh (ID dipertahankan)."})
    await db.warehouses.update_one({"id": warehouse_id}, {"$set": {"zones": zones, "updated_at": now_iso()}})
    return await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0})


async def _queue_block(roll: Dict[str, Any]) -> Optional[str]:
    if (roll.get("active_movement") or {}).get("id"):
        return f"Sedang dalam perpindahan {roll['active_movement'].get('number') or ''}".strip()
    if pr.is_held(roll):
        return "QC/ditahan — hanya boleh ke area QC/karantina"
    if float(roll.get("length_reserved") or 0) > 0:
        return "Ada reservasi potong yang belum dikonfirmasi"
    return None


async def putaway_queue(warehouse_id: Optional[str], ctx: EntityContext, entity_id: Optional[str], limit: int = 500) -> List[Dict[str, Any]]:
    """Roll fisik yang BELUM ditempatkan ke bin, dengan status siap/terhambat + alasannya."""
    from services.roll_service import PHYSICAL_STATUS_TO_BUCKET
    q: Dict[str, Any] = {
        "length_remaining": {"$gt": 0},
        "status": {"$in": list(PHYSICAL_STATUS_TO_BUCKET.keys())},
        "$or": [{"bin_id": None}, {"bin_id": ""}, {"bin_id": {"$exists": False}}],
    }
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    q = resolve_list_scope("inventory_rolls", q, ctx, entity_id)
    rolls = await db.inventory_rolls.find(
        q, {"_id": 0, "id": 1, "roll_no": 1, "product_id": 1, "warehouse_id": 1, "grade": 1, "inspection": 1,
            "owner_entity_id": 1, "lot": 1, "length_remaining": 1, "unit": 1, "status": 1,
            "active_movement": 1, "length_reserved": 1}).to_list(limit)
    pids = list({r["product_id"] for r in rolls})
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": pids}}, {"_id": 0, "id": 1, "sku": 1, "name": 1}).to_list(2000)}
    for r in rolls:
        p = prods.get(r["product_id"], {})
        r["sku"], r["product_name"] = p.get("sku", ""), p.get("name", "")
        r["blocked_reason"] = await _queue_block(r)
        r["ready"] = r["blocked_reason"] is None or r["blocked_reason"].startswith("QC")
        r.pop("inspection", None)
    return rolls


async def evaluate_target(roll_id: str, bin_ref: str) -> Dict[str, Any]:
    """Pratinjau kelayakan (UI rekomendasi) — server tetap memvalidasi ulang saat simpan."""
    roll = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
    if not roll:
        raise HTTPException(status_code=404, detail="Roll tidak ditemukan")
    wh = await db.warehouses.find_one({"id": roll["warehouse_id"]}, {"_id": 0}) or {}
    node = pr.resolve_bin(wh, bin_ref)
    if not node:
        raise HTTPException(status_code=400, detail=f"Alamat '{bin_ref}' tidak ada di master gudang {wh.get('name', '')}.")
    prod = await db.products.find_one({"id": roll["product_id"]}, {"_id": 0}) or {}
    ok = ("receiving",) if roll.get("status") == "receiving" else ()
    res = await pr.evaluate(wh, node, roll, prod, extra_status_ok=ok)
    return {**res, "bin_id": node["bin"]["id"], "bin_code": node["bin"].get("code", ""),
            "rules": pr.effective_view(wh, node)}


async def suggest_for_roll(roll_id: str, limit: int = 8) -> Dict[str, Any]:
    """Saran bin valid (evaluator yang sama dengan aksi simpan)."""
    roll = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
    if not roll:
        raise HTTPException(status_code=404, detail="Roll tidak ditemukan")
    wh = await db.warehouses.find_one({"id": roll["warehouse_id"]}, {"_id": 0}) or {}
    prod = await db.products.find_one({"id": roll["product_id"]}, {"_id": 0}) or {}
    ok = ("receiving",) if roll.get("status") == "receiving" else ()
    return {"roll_id": roll_id, "held": pr.is_held(roll), **await pr.recommend(wh, roll, prod, limit, extra_status_ok=ok)}


async def place_roll(roll: Dict[str, Any], wh: Dict[str, Any], node: Dict[str, Any], *, actor: Optional[Dict[str, Any]],
                     override: Optional[Dict[str, Any]] = None, cas: Optional[Dict[str, Any]] = None,
                     extra_set: Optional[Dict[str, Any]] = None, extra_status_ok: tuple = ()) -> Dict[str, Any]:
    """Jalur TUNGGAL penulisan bin: evaluasi → kunci bin → evaluasi ulang → CAS tulis → mutasi berjejak."""
    prod = await db.products.find_one({"id": roll["product_id"]}, {"_id": 0}) or {}
    bin_id = node["bin"]["id"]
    pr.check_override(actor, override, await pr.evaluate(wh, node, roll, prod, extra_status_ok=extra_status_ok))
    await pr.acquire_bin_lock(bin_id, (actor or {}).get("id", "system"))
    try:
        exc = pr.check_override(actor, override, await pr.evaluate(wh, node, roll, prod, extra_status_ok=extra_status_ok))
        flt = {"id": roll["id"], "warehouse_id": roll.get("warehouse_id") or wh["id"],
               "bin_id": roll.get("bin_id") or None, **(cas or {})}
        res = await db.inventory_rolls.update_one(flt, {"$set": {"bin_id": bin_id, "bin_code": node["bin"].get("code", ""),
                                                                "updated_at": now_iso(), **(extra_set or {})}})
        if not res.matched_count:
            raise HTTPException(status_code=409, detail="Roll berubah saat ditempatkan (status/gudang) — muat ulang lalu coba lagi.")
        old_bin = roll.get("bin_id")
        await db.inventory_movements.insert_one({
            "id": new_id("mov"), "product_id": roll["product_id"], "warehouse_id": roll["warehouse_id"],
            "owner_entity_id": roll.get("owner_entity_id"), "movement_type": "putaway",
            "quantity": 0.0, "unit": roll.get("unit", "meter"), "lot": roll.get("lot", ""), "roll_id": roll["id"],
            "qty_rolls": 1, "source_document": f"putaway:{old_bin or '-'}->{bin_id}",
            "capacity_override": exc, "by": (actor or {}).get("name", "System"), "timestamp": now_iso(),
        })
    finally:
        await pr.release_bin_lock(bin_id)
    return {"roll_id": roll["id"], "bin_id": bin_id, "bin_code": node["bin"].get("code", ""),
            "bin_path": node["path"], "from_bin": roll.get("bin_id"), "capacity_override": exc}


async def putaway_roll(roll_id: str, bin_id: str, actor_name: str = "System", *, actor: Optional[Dict[str, Any]] = None,
                       override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Tempatkan/pindahkan roll ke bin dalam gudang yang sama (layar, scan, skrip)."""
    roll = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
    if not roll:
        raise HTTPException(status_code=404, detail="Roll tidak ditemukan")
    wh = await db.warehouses.find_one({"id": roll["warehouse_id"]}, {"_id": 0})
    if not wh:
        raise HTTPException(status_code=404, detail="Gudang roll tidak ditemukan")
    node = pr.resolve_bin(wh, bin_id)
    if not node:
        raise HTTPException(status_code=400, detail="Bin tujuan tidak ada di gudang roll ini.")
    return await place_roll(roll, wh, node, actor=actor or {"name": actor_name}, override=override,
                            cas={"status": roll.get("status")})


async def orphan_rolls(warehouse_id: str) -> List[Dict[str, Any]]:
    """Roll fisik yang alamat bin-nya tidak ada di master (masuk exception, tetap terhitung fisik)."""
    from services.roll_service import PHYSICAL_STATUS_TO_BUCKET
    wh = await db.warehouses.find_one({"id": warehouse_id}, {"_id": 0}) or {}
    known = [b["bin_id"] for b in flatten_bins(wh)]
    return await db.inventory_rolls.find(
        {"warehouse_id": warehouse_id, "bin_id": {"$nin": known + [None, ""], "$exists": True},
         "status": {"$in": list(PHYSICAL_STATUS_TO_BUCKET.keys())}},
        {"_id": 0, "id": 1, "roll_no": 1, "bin_id": 1, "unit": 1, "length_remaining": 1, "status": 1,
         "product_id": 1, "owner_entity_id": 1}).to_list(1000)


async def fix_orphan(roll_id: str, bin_id: str, reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Koreksi alamat berjejak: ke bin valid (lewat evaluator) atau dikosongkan (kembali ke antrean)."""
    if len((reason or "").strip()) < 5:
        raise HTTPException(status_code=400, detail="Alasan koreksi alamat minimal 5 karakter.")
    roll = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
    if not roll:
        raise HTTPException(status_code=404, detail="Roll tidak ditemukan")
    if bin_id:
        out = await putaway_roll(roll_id, bin_id, actor=actor)
    else:
        await db.inventory_rolls.update_one({"id": roll_id}, {"$set": {"bin_id": None, "bin_code": "", "updated_at": now_iso()}})
        out = {"roll_id": roll_id, "bin_id": None, "from_bin": roll.get("bin_id")}
    await db.location_corrections.insert_one({"id": new_id("locfix"), "roll_id": roll_id, "warehouse_id": roll["warehouse_id"],
                                              "from_bin": roll.get("bin_id"), "to_bin": bin_id or None, "reason": reason.strip(),
                                              "by": actor.get("name"), "at": now_iso()})
    return out

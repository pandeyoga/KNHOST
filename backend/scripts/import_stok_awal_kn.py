"""Stok awal (MOCK) untuk master produk hasil impor Excel: tiap ARTIKEL 1.000–2.000 roll,
dibagi ke varian/SKU-nya dan ke entitas bertanda Y. Panjang/berat roll = QTY_PER_ROLL ±5%
(bawaan 25 kg knitting / 50 yard woven & printing). Gudang = gudang khusus milik entitas;
bila belum ada dibuat "Gudang Utama <entitas>". Setelah roll masuk: lot, saldo, dan jurnal
saldo awal persediaan (Dr Persediaan / Cr Ekuitas Saldo Awal) dibentuk lewat jalur resmi.

Idempoten: produk yang sudah punya stok awal batch ini dilewati.

  python scripts/import_stok_awal_kn.py [--dry-run]
"""
import asyncio
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from pymongo import ReturnDocument  # noqa: E402

from core_utils import new_id, now_iso  # noqa: E402
from db import db  # noqa: E402
from services import lot_service, roll_service  # noqa: E402

BATCH = "MIGRASI_MASTER_PRODUK_KN"
REF = "STOK_AWAL_KN"
DEFAULT_LEN = {"kg": 25.0, "yard": 50.0}
CHUNK = 5000


async def entity_warehouse(eid: str, dry: bool) -> str:
    async for wh in db.warehouses.find({"active": {"$ne": False}, "sharing_mode": "dedicated", "entity_ids": [eid]},
                                       {"_id": 0, "id": 1}).sort("created_at", 1):
        return wh["id"]
    ent = await db.business_entities.find_one({"id": eid}, {"_id": 0}) or {}
    short = ent.get("short_name") or ent.get("doc_prefix") or eid
    if dry:
        return f"(baru) Gudang Utama {short}"
    wid = new_id("wh")
    await db.warehouses.insert_one({
        "id": wid, "code": f"GU-{(ent.get('doc_prefix') or short).upper()}"[:20], "name": f"Gudang Utama {short}",
        "city": ent.get("city") or "", "address": ent.get("address") or "", "lat": None, "lng": None,
        "sharing_mode": "dedicated", "entity_ids": [eid],
        "zones": [{"id": new_id("zone"), "name": "Zone A", "racks": [{"id": new_id("rack"), "name": "Rack A1",
                   "bins": [{"id": new_id("bin"), "code": "A1-01", "capacity": 100000}]}]}],
        "active": True, "created_at": now_iso(), "created_by": "Import Stok Awal"})
    print(f"   + gudang baru: Gudang Utama {short}")
    return wid


async def reserve_roll_numbers(n: int) -> List[str]:
    first = await roll_service.next_roll_no()      # inisialisasi sequence bila perlu (+1)
    start = int(first.split("-")[-1])
    if n > 1:
        await db.number_sequences.find_one_and_update(
            {"entity_id": "_global", "doc_type": "ROLL", "prefix": roll_service.ROLL_NO_PREFIX},
            {"$inc": {"last_no": n - 1}}, return_document=ReturnDocument.AFTER)
    return [f"{roll_service.ROLL_NO_PREFIX}{start + i:05d}" for i in range(n)]


def roll_len(prod: Dict[str, Any], tpl: Dict[str, Any]) -> float:
    conv = next((c for c in prod.get("uom_conversions") or [] if c.get("from_unit") == "roll"), None)
    return float((conv or {}).get("factor") or tpl.get("qty_per_roll") or DEFAULT_LEN.get(prod.get("base_unit"), 50.0))


def split(total: int, parts: int, rnd: random.Random) -> List[int]:
    w = [rnd.uniform(0.6, 1.4) for _ in range(parts)]
    out = [max(1, int(total * x / sum(w))) for x in w]
    out[0] += total - sum(out)
    return out


async def main(dry: bool) -> None:
    tpls = await db.product_templates.find({"import_batch": BATCH}, {"_id": 0}).sort("sku_prefix", 1).to_list(1000)
    if not tpls:
        sys.exit("Belum ada master produk hasil impor — jalankan dulu scripts/import_master_produk_kn.py")
    whs: Dict[str, str] = {}
    segments, total_rolls, skipped = [], 0, 0
    for tpl in tpls:
        rnd = random.Random(tpl["sku_prefix"])
        prods = await db.products.find({"template_id": tpl["id"], "import_batch": BATCH}, {"_id": 0}).sort("sku", 1).to_list(500)
        ents = tpl.get("entity_ids") or []
        if not prods or not ents:
            continue
        pairs = [(p, e) for p in prods for e in ents]
        n_art = rnd.randint(1000, 2000)
        for (prod, eid), n in zip(pairs, split(n_art, len(pairs), rnd)):
            if await db.inventory_rolls.find_one({"product_id": prod["id"], "acquired.ref_id": REF}, {"_id": 1}):
                skipped += 1
                continue
            if eid not in whs:
                whs[eid] = await entity_warehouse(eid, dry)
            base = roll_len(prod, tpl)
            lens = [round(base * rnd.uniform(0.95, 1.05), 2) for _ in range(n)]
            segments.append({"prod": prod, "eid": eid, "wh": whs[eid], "lens": lens, "art": tpl["sku_prefix"]})
            total_rolls += n
        print(f"{tpl['sku_prefix']} {tpl['name']}: {n_art} roll → {len(pairs)} segmen (SKU × entitas)")
    print(f"Total: {len(segments)} segmen · {total_rolls} roll baru · {skipped} segmen sudah ada (dilewati)")
    if dry or not segments:
        return
    numbers = iter(await reserve_roll_numbers(total_rolls))
    rolls, moves, lot_ids = [], [], set()
    for sg in segments:
        prod, eid, wid = sg["prod"], sg["eid"], sg["wh"]
        ent_short = (await db.business_entities.find_one({"id": eid}, {"_id": 0, "doc_prefix": 1}) or {}).get("doc_prefix") or eid
        lot = await lot_service.resolve_or_create(
            product_id=prod["id"], owner_entity_id=eid, warehouse_id=wid, lot_code=f"SA-{prod['sku'][-14:]}-{ent_short}",
            source="migration", source_ref={"type": "initial", "id": REF, "number": "Stok awal migrasi"},
            status="released", actor="Import Stok Awal")
        lot_ids.add(lot["id"])
        cost = round(float(prod.get("harga_pokok") or 0), 4)
        for ln in sg["lens"]:
            rid, ts = new_id("roll"), now_iso()
            rolls.append({
                "id": rid, "product_id": prod["id"], "owner_entity_id": eid, "ownership_type": "internal", "consignor_ref": None,
                "warehouse_id": wid, "bin_id": None, "lot": lot["lot_number"], "lot_id": lot["id"], "supplier_lot": "",
                "dye_lot": lot["lot_number"], "batch": f"SA-{sg['art']}", "roll_no": next(numbers),
                "length_initial": ln, "length_remaining": ln, "unit": prod.get("base_unit"), "grade": roll_service._norm_grade(prod.get("grade")),
                **roll_service._domain_snapshot(prod), "status": "available", "tracking_mode": "barcode", "earmarked_for": None,
                "secondary_measures": None, "location_type": "warehouse_bin", "reserved_ref": None,
                "base_unit_cost": cost, "unit_cost": cost or None, "landed_cost_total": 0.0,
                "acquired": {"via": "initial", "ref_id": REF, "date": ts}, "rfid_tag_id": None, "is_remnant": False,
                "created_at": ts, "updated_at": ts, "created_by": "Import Stok Awal", "created_by_name": "Import Stok Awal",
                "defects": [], "landed_cost_refs": []})
            moves.append({"id": new_id("mov"), "product_id": prod["id"], "warehouse_id": wid, "owner_entity_id": eid,
                          "movement_type": "initial_stock", "quantity": ln, "unit": prod.get("base_unit"),
                          "lot": lot["lot_number"], "lot_id": lot["id"], "batch": f"SA-{sg['art']}", "roll_id": rid,
                          "qty_rolls": 1, "source_document": REF, "notes": "Stok awal migrasi (MOCK)", "created_by": "Import Stok Awal",
                          "timestamp": ts})
    for i in range(0, len(rolls), CHUNK):
        await db.inventory_rolls.insert_many(rolls[i:i + CHUNK], ordered=False)
        await db.inventory_movements.insert_many(moves[i:i + CHUNK], ordered=False)
        print(f"   roll {min(i + CHUNK, len(rolls))}/{len(rolls)}")
    await lot_service.recompute_many(list(lot_ids))
    for key in {(sg["prod"]["id"], sg["wh"], sg["eid"]) for sg in segments}:
        await roll_service.rebuild_balance(*key)
    from services import gl_service
    gl = await gl_service.post_inventory_opening_balance(actor_name="Import Stok Awal",
                                                         reason="Stok awal migrasi master produk KN (MOCK)")
    print(f"Selesai: {len(rolls)} roll · {len(lot_ids)} lot · jurnal saldo awal: {len(gl.get('posted') or [])} entitas")


if __name__ == "__main__":
    asyncio.run(main("--dry-run" in sys.argv))

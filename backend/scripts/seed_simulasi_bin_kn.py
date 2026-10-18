"""SIMULASI BIN KN — penempatan bin (MOCK; bin nyata di lapangan belum ada) di atas data acuan repo.

Struktur campuran seperti kondisi migrasi: WH-JKT, RCM-WOVEN, RCM-KNITTING = format baru (zona → rak → level → bin);
gudang lain = format lama (rak → bin). Zona dipisah per satuan (W = yard, K = kg). ±80% roll fisik ditempatkan
(deterministik per id roll), ±20% tetap belum ditempatkan. Sampel data bermasalah untuk uji P02 diberi tanda
`sim_anomaly` dan dapat dihapus. Bin id deterministik per kode gudang → sama di preview & VPS.
Idempoten: dijalankan ulang hanya melengkapi.
  python scripts/seed_simulasi_bin_kn.py                  isi / lengkapi
  python scripts/seed_simulasi_bin_kn.py --cek [--json f] diagnosis saja (read-only)
  python scripts/seed_simulasi_bin_kn.py --hapus-anomali  kembalikan sampel bermasalah
  python scripts/seed_simulasi_bin_kn.py --hapus-semua    batalkan seluruh simulasi
"""
import argparse
import asyncio
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from pymongo import UpdateOne  # noqa: E402

from core_utils import new_id, now_iso  # noqa: E402
from db import db  # noqa: E402
from services.location_service import flatten_bins  # noqa: E402
from services.roll_service import PHYSICAL_STATUS_TO_BUCKET  # noqa: E402

BATCH = "SIMULASI_BIN_KN"
FLAG = "simulasi_bin_kn"
MODERN = {"WH-JKT", "RCM-WOVEN", "RCM-KNITTING"}
ZONE = {"yard": ("W", "Zona W · Woven/Printing (yard)", 6000.0), "kg": ("K", "Zona K · Knitting (kg)", 1500.0)}
FILL, PLACE_PCT, LEVELS, BINS_PER_LEVEL, BINS_PER_RACK_LEGACY = 0.9, 80, 4, 5, 10
PHYSICAL = list(PHYSICAL_STATUS_TO_BUCKET.keys())
ANCHOR_WH = "WH-JKT"


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s.lower())


def _selected(roll_id: str) -> bool:
    return int(hashlib.md5(roll_id.encode()).hexdigest()[:8], 16) % 100 < PLACE_PCT


def _bin(wh_code: str, code: str, cap: float) -> Dict[str, Any]:
    return {"id": f"bin_sim_{_slug(wh_code)}_{_slug(code)}", "code": code, "capacity": cap}


def _zone(wh_code: str, unit: str, n_bins: int) -> Dict[str, Any]:
    p, name, cap = ZONE[unit]
    zid = f"zone_sim_{_slug(wh_code)}_{p.lower()}"
    racks: List[Dict[str, Any]] = []
    if wh_code in MODERN:
        for r in range(1, math.ceil(n_bins / (LEVELS * BINS_PER_LEVEL)) + 1):
            rid = f"rack_sim_{_slug(wh_code)}_{p.lower()}{r:02d}"
            racks.append({"id": rid, "name": f"Rak {p}{r:02d}", "levels": [
                {"id": f"{rid}_l{lv}", "name": f"Level {lv}",
                 "bins": [_bin(wh_code, f"{p}{r:02d}-L{lv}-{b:02d}", cap) for b in range(1, BINS_PER_LEVEL + 1)]}
                for lv in range(1, LEVELS + 1)]})
    else:
        for r in range(1, math.ceil(n_bins / BINS_PER_RACK_LEGACY) + 1):
            racks.append({"id": f"rack_sim_{_slug(wh_code)}_{p.lower()}{r:02d}", "name": f"Rak {p}{r:02d}",
                          "bins": [_bin(wh_code, f"{p}{r:02d}-{b:02d}", cap)
                                   for b in range(1, BINS_PER_RACK_LEGACY + 1)]})
    return {"id": zid, "name": name, "sim_batch": BATCH, "racks": racks}


async def _rolls(wid: str) -> List[Dict[str, Any]]:
    return await db.inventory_rolls.find(
        {"warehouse_id": wid},
        {"_id": 1, "id": 1, "roll_no": 1, "product_id": 1, "lot": 1, "unit": 1, "status": 1, "bin_id": 1,
         "length_remaining": 1, "owner_entity_id": 1, "sim_anomaly": 1}).to_list(None)


async def build_structure(wh: Dict[str, Any], rolls: List[Dict[str, Any]]) -> bool:
    zones = wh.get("zones") or []
    if any(str(z.get("id", "")).startswith("zone_sim_") for z in zones):
        return False
    qty: Dict[str, float] = defaultdict(float)
    for r in rolls:
        if r["status"] in PHYSICAL and r.get("unit") in ZONE and (r.get("length_remaining") or 0) > 0 and _selected(r["id"]):
            qty[r["unit"]] += float(r["length_remaining"])
    new = []
    for unit, (_, _, cap) in ZONE.items():
        need = math.ceil(qty[unit] / (cap * FILL))
        new.append(_zone(wh["code"], unit, max(10, math.ceil(need * 1.1))))
    await db.warehouses.update_one({"id": wh["id"]}, {"$set": {"zones": zones + new, "updated_at": now_iso()}})
    return True


async def place_rolls(wh: Dict[str, Any], rolls: List[Dict[str, Any]]) -> int:
    bins = [b for b in flatten_bins(wh) if str(b["bin_id"]).startswith("bin_sim_") and "OVER" not in b["code"]]
    by_unit: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for b in bins:
        by_unit["yard" if b["code"].startswith("W") else "kg"].append(b)
    occ: Dict[str, float] = defaultdict(float)
    for r in rolls:
        if r.get("bin_id") and r["status"] in PHYSICAL:
            occ[r["bin_id"]] += float(r.get("length_remaining") or 0)
    todo = sorted((r for r in rolls if not r.get("bin_id") and not r.get("sim_anomaly") and r["status"] in PHYSICAL
                   and r.get("unit") in ZONE and (r.get("length_remaining") or 0) > 0 and _selected(r["id"])),
                  key=lambda r: (r["product_id"], r.get("lot") or "", r.get("roll_no") or ""))
    ops, movs, idx = [], [], defaultdict(int)
    ts = now_iso()
    for r in todo:
        lst, q = by_unit[r["unit"]], float(r["length_remaining"])
        while idx[r["unit"]] < len(lst) and occ[lst[idx[r["unit"]]]["bin_id"]] + q > lst[idx[r["unit"]]]["capacity"] * FILL:
            idx[r["unit"]] += 1
        if idx[r["unit"]] >= len(lst):
            continue
        bid = lst[idx[r["unit"]]]["bin_id"]
        occ[bid] += q
        ops.append(UpdateOne({"_id": r["_id"], "bin_id": None}, {"$set": {"bin_id": bid, "bin_sim": BATCH, "updated_at": ts}}))
        movs.append({"id": new_id("mov"), "product_id": r["product_id"], "warehouse_id": wh["id"],
                     "owner_entity_id": r.get("owner_entity_id"), "movement_type": "putaway", "quantity": 0.0,
                     "unit": r["unit"], "lot": r.get("lot", ""), "roll_id": r["id"], "qty_rolls": 1,
                     "source_document": f"putaway:-->{bid}", "sim_batch": BATCH, "timestamp": ts})
    for i in range(0, len(ops), 2000):
        await db.inventory_rolls.bulk_write(ops[i:i + 2000], ordered=False)
        await db.inventory_movements.insert_many(movs[i:i + 2000])
    return len(ops)


async def seed_anomalies() -> Dict[str, int]:
    if await db.inventory_rolls.count_documents({"sim_anomaly.batch": BATCH}):
        return {}
    wh = await db.warehouses.find_one({"code": ANCHOR_WH}, {"_id": 0})
    if not wh:
        return {}
    w_bins = [b for b in flatten_bins(wh) if b["bin_id"].startswith("bin_sim_") and b["code"].startswith("W")]
    rolls = sorted(await _rolls(wh["id"]), key=lambda r: r.get("roll_no") or "")
    spare = [r for r in rolls if not r.get("bin_id") and r["status"] in PHYSICAL and (r.get("length_remaining") or 0) > 0]
    yard = [r for r in spare if r.get("unit") == "yard"]
    kg = [r for r in spare if r.get("unit") == "kg"]
    transit = [r for r in rolls if r["status"].startswith("in_transit") and not r.get("bin_id")]

    over = _bin(ANCHOR_WH, "W-OVER-01", round(sum(float(r["length_remaining"]) for r in yard[3:7]) * 0.5))
    over["sim_anomaly"] = "lebih_kapasitas"
    zones = wh["zones"]
    for z in zones:
        if z["id"] == f"zone_sim_{_slug(ANCHOR_WH)}_w":
            z["racks"][0]["levels"][0]["bins"].append(over)
    await db.warehouses.update_one({"id": wh["id"]}, {"$set": {"zones": zones, "updated_at": now_iso()}})

    plan = ([(r, "bin_tidak_ada_di_master", f"bin_sim_hilang_{i:02d}") for i, r in enumerate(yard[:3], 1)]
            + [(r, "satuan_campur", w_bins[0]["bin_id"]) for r in kg[:2]]
            + [(r, "transit_berbin", w_bins[0]["bin_id"]) for r in transit[:3]]
            + [(r, "lebih_kapasitas", over["id"]) for r in yard[3:7]])
    for r, typ, bid in plan:
        await db.inventory_rolls.update_one({"_id": r["_id"]}, {"$set": {
            "bin_id": bid, "sim_anomaly": {"batch": BATCH, "type": typ, "prev_bin_id": r.get("bin_id")},
            "updated_at": now_iso()}})
    out: Dict[str, int] = defaultdict(int)
    for _, typ, _ in plan:
        out[typ] += 1
    return dict(out)


async def remove_anomalies() -> int:
    n = 0
    async for r in db.inventory_rolls.find({"sim_anomaly.batch": BATCH}, {"_id": 0, "id": 1, "sim_anomaly": 1}):
        await db.inventory_rolls.update_one({"id": r["id"]}, {"$set": {"bin_id": r["sim_anomaly"].get("prev_bin_id"),
                                                                        "updated_at": now_iso()},
                                                               "$unset": {"sim_anomaly": ""}})
        n += 1
    async for wh in db.warehouses.find({"zones.racks.levels.bins.sim_anomaly": {"$exists": True}}, {"_id": 0}):
        for z in wh["zones"]:
            for rk in z.get("racks") or []:
                for lv in rk.get("levels") or []:
                    lv["bins"] = [b for b in lv.get("bins") or [] if not b.get("sim_anomaly")]
        await db.warehouses.update_one({"id": wh["id"]}, {"$set": {"zones": wh["zones"], "updated_at": now_iso()}})
    return n


async def remove_all() -> Dict[str, int]:
    a = await remove_anomalies()
    r = await db.inventory_rolls.update_many({"bin_sim": BATCH, "bin_id": {"$regex": "^bin_sim_"}},
                                             {"$set": {"bin_id": None, "updated_at": now_iso()}, "$unset": {"bin_sim": ""}})
    await db.inventory_rolls.update_many({"bin_sim": BATCH}, {"$unset": {"bin_sim": ""}})
    m = await db.inventory_movements.delete_many({"sim_batch": BATCH})
    async for wh in db.warehouses.find({"zones.id": {"$regex": "^zone_sim_"}}, {"_id": 0, "id": 1, "zones": 1}):
        zones = [z for z in wh["zones"] if not str(z.get("id", "")).startswith("zone_sim_")]
        await db.warehouses.update_one({"id": wh["id"]}, {"$set": {"zones": zones, "updated_at": now_iso()}})
    await db.migrations.delete_one({"id": FLAG})
    return {"anomali": a, "roll_dikosongkan": r.modified_count, "mutasi_dihapus": m.deleted_count}


async def diagnose() -> Dict[str, Any]:
    rows, tot = [], defaultdict(int)
    async for wh in db.warehouses.find({}, {"_id": 0}).sort("code", 1):
        bins = {b["bin_id"]: b for b in flatten_bins(wh)}
        fmt = {("baru" if b["level_id"] else "lama") for b in bins.values()}
        occ: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        c = defaultdict(int)
        for r in await _rolls(wh["id"]):
            phys = r["status"] in PHYSICAL and (r.get("length_remaining") or 0) > 0
            bid = r.get("bin_id")
            c["roll_fisik"] += phys
            if not bid:
                c["belum_ditempatkan"] += phys
                continue
            c["roll_berbin"] += phys
            if bid not in bins:
                c["orphan_bin"] += 1
            if not phys and r["status"].startswith("in_transit"):
                c["transit_berbin"] += 1
            if phys:
                occ[bid][r.get("unit") or "?"] += float(r["length_remaining"])
        c["bin_satuan_campur"] = sum(1 for o in occ.values() if len(o) > 1)
        c["bin_lebih_kapasitas"] = sum(1 for bid, o in occ.items()
                                       if bid in bins and bins[bid]["capacity"] > 0 and sum(o.values()) > bins[bid]["capacity"])
        c["bin"] = len(bins)
        for k, v in c.items():
            tot[k] += v
        rows.append({"gudang": wh.get("code"), "format": "+".join(sorted(fmt)) or "-", **c})
    return {"per_gudang": rows, "total": dict(tot), "dijalankan": now_iso()}


def _print(d: Dict[str, Any]) -> None:
    keys = ["bin", "roll_fisik", "roll_berbin", "belum_ditempatkan", "orphan_bin", "bin_satuan_campur",
            "transit_berbin", "bin_lebih_kapasitas"]
    print(f"{'gudang':14} {'format':10} " + " ".join(f"{k[:12]:>12}" for k in keys))
    for r in d["per_gudang"] + [{"gudang": "TOTAL", "format": "", **d["total"]}]:
        print(f"{r['gudang']:14} {r['format']:10} " + " ".join(f"{r.get(k, 0):>12}" for k in keys))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cek", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--hapus-anomali", action="store_true")
    ap.add_argument("--hapus-semua", action="store_true")
    a = ap.parse_args()
    if a.hapus_semua:
        print("Simulasi bin dibatalkan:", await remove_all())
        return
    if a.hapus_anomali:
        print("Sampel bermasalah dikembalikan:", await remove_anomalies(), "roll")
        return
    if not a.cek:
        built = placed = 0
        async for wh in db.warehouses.find({}, {"_id": 0}):
            rolls = await _rolls(wh["id"])
            built += await build_structure(wh, rolls)
            wh = await db.warehouses.find_one({"id": wh["id"]}, {"_id": 0})
            placed += await place_rolls(wh, rolls)
        anom = await seed_anomalies()
        await db.migrations.update_one({"id": FLAG}, {"$set": {"batch": BATCH, "updated_at": now_iso()},
                                                      "$inc": {"roll_ditempatkan": placed}}, upsert=True)
        print(f"Struktur baru: {built} gudang · roll ditempatkan: {placed} · sampel bermasalah: {anom or 'sudah ada'}")
    d = await diagnose()
    _print(d)
    if a.json:
        Path(a.json).write_text(json.dumps(d, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

"""DATA ACUAN P02 (CONTOH, bukan angka bisnis asli) — kapasitas roll, area QC, dan aturan bin di WH-JKT.

- Zona baru "Zona Q · Karantina QC" (fungsi qc): Lemari Q01 / Tingkat 1 / 4 bin, kapasitas 10 roll.
- Lemari W01 di Zona W: Tingkat 1 berkapasitas roll (isi sekarang dibulatkan ke atas + ruang, kelipatan 10),
  Tingkat 2 aturan "1 SKU per bin", Tingkat 3 hanya grade A.
- Bin anomali W-OVER-01: kapasitas 3 roll → contoh bin melebihi kapasitas.
Bin lain dibiarkan tanpa kapasitas (tampil "belum diatur"). Idempoten.
  python scripts/seed_p02_kn.py          isi / perbarui
  python scripts/seed_p02_kn.py --hapus  kembalikan seperti sebelum P02
"""
import argparse
import asyncio
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402

WH = "WH-JKT"
QZ = "zone_p02_wh_jkt_qc"
TAG = "p02_demo"


def _qc_zone() -> dict:
    rid = "rack_p02_wh_jkt_q01"
    return {"id": QZ, "name": "Zona Q · Karantina QC", "function": "qc", TAG: True, "racks": [
        {"id": rid, "name": "Lemari Q01", "levels": [{"id": f"{rid}_l1", "name": "Tingkat 1", "bins": [
            {"id": f"bin_p02_wh_jkt_q01_{i:02d}", "code": f"Q01-T1-{i:02d}", "capacity": 0, "capacity_rolls": 10}
            for i in range(1, 5)]}]}]}


async def apply() -> dict:
    wh = await db.warehouses.find_one({"code": WH}, {"_id": 0})
    if not wh:
        return {"skipped": "WH-JKT tidak ada"}
    counts = {r["_id"]: r["n"] async for r in db.inventory_rolls.aggregate([
        {"$match": {"warehouse_id": wh["id"], "bin_id": {"$nin": [None, ""]}, "length_remaining": {"$gt": 0}}},
        {"$group": {"_id": "$bin_id", "n": {"$sum": 1}}}])}
    zones, out = wh.get("zones") or [], {"cap_set": 0}
    for z in zones:
        for rk in z.get("racks") or []:
            name = rk.get("name", "")
            for lv in rk.get("levels") or []:
                for b in lv.get("bins") or []:
                    if b.get("code") == "W-OVER-01":
                        b["capacity_rolls"] = 3
                        out["cap_set"] += 1
                    elif name == "Rak W01" and lv.get("name") == "Level 1":
                        b["capacity_rolls"] = int(math.ceil((counts.get(b["id"], 0) + 5) / 10.0) * 10)
                        out["cap_set"] += 1
                    elif name == "Rak W01":
                        b.pop("capacity_rolls", None)
                if name == "Rak W01" and lv.get("name") == "Level 2":
                    lv["rules"] = {"single_sku": True}
                if name == "Rak W01" and lv.get("name") == "Level 3":
                    lv["rules"] = {"grades": ["A"]}
    if not any(z.get("id") == QZ for z in zones):
        zones.append(_qc_zone())
        out["qc_zone"] = "dibuat"
    await db.warehouses.update_one({"id": wh["id"]}, {"$set": {"zones": zones, "updated_at": now_iso()}})
    return out


async def remove() -> dict:
    wh = await db.warehouses.find_one({"code": WH}, {"_id": 0})
    if not wh:
        return {}
    zones = [z for z in wh.get("zones") or [] if z.get("id") != QZ]
    for z in zones:
        for rk in z.get("racks") or []:
            for lv in rk.get("levels") or []:
                if rk.get("name") == "Rak W01" and lv.get("name") in ("Level 2", "Level 3"):
                    lv.pop("rules", None)
                for b in lv.get("bins") or []:
                    if rk.get("name") == "Rak W01" or b.get("code") == "W-OVER-01":
                        b.pop("capacity_rolls", None)
    await db.warehouses.update_one({"id": wh["id"]}, {"$set": {"zones": zones, "updated_at": now_iso()}})
    return {"dihapus": True}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hapus", action="store_true")
    a = ap.parse_args()
    print("Data acuan P02:", await (remove() if a.hapus else apply()))


if __name__ == "__main__":
    asyncio.run(main())

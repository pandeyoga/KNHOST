"""MIGRASI P02 — struktur lokasi lama (rak → bin) menjadi format baru (rak → tingkat → bin).

Bawaan = DRY-RUN (hanya laporan). `--apply` menulis. ID bin TIDAK berubah (stok & tugas tetap menunjuk
alamat yang sama); tingkat baru ber-id tetap `<rack_id>_lv1`, jadi menjalankan ulang tidak menggandakan node.
Resolver sudah membaca kedua format, jadi migrasi ini opsional (dipakai saat struktur ingin diseragamkan).
  python scripts/migrate_p02_lokasi.py           laporan saja
  python scripts/migrate_p02_lokasi.py --apply   jalankan
"""
import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from services.location_service import flatten_bins  # noqa: E402


def convert(zones: list) -> int:
    n = 0
    for z in zones or []:
        for rk in z.get("racks") or []:
            if rk.get("bins") and not rk.get("levels"):
                rk["levels"] = [{"id": f"{rk['id']}_lv1", "name": "Tingkat 1", "bins": rk.pop("bins")}]
                n += 1
            elif rk.get("bins") and rk.get("levels"):
                lv = next((x for x in rk["levels"] if x.get("id") == f"{rk['id']}_lv1"), None)
                if lv is None:
                    lv = {"id": f"{rk['id']}_lv1", "name": "Tingkat 1", "bins": []}
                    rk["levels"].append(lv)
                lv["bins"] += rk.pop("bins")
                n += 1
    return n


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    total = 0
    async for wh in db.warehouses.find({}, {"_id": 0}).sort("code", 1):
        before = sorted(b["bin_id"] for b in flatten_bins(wh))
        n = convert(wh.get("zones") or [])
        if not n:
            continue
        after = sorted(b["bin_id"] for b in flatten_bins(wh))
        assert before == after, f"ID bin berubah di {wh.get('code')} — dibatalkan"
        total += n
        print(f"{wh.get('code'):14} rak lama dikonversi: {n:4} · bin tetap: {len(after)}")
        if a.apply:
            await db.warehouses.update_one({"id": wh["id"]}, {"$set": {"zones": wh["zones"], "updated_at": now_iso()}})
    if a.apply and total:
        await db.migrations.update_one({"id": "p02_lokasi_levels"}, {"$set": {"racks": total, "at": now_iso()}}, upsert=True)
    print(("DITERAPKAN" if a.apply else "DRY-RUN") + f" — total rak lama: {total}")


if __name__ == "__main__":
    asyncio.run(main())

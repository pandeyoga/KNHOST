"""KM-T1 (KM-04) — target sales lama ke kunci baru (PT, sales, jenis periode, periode).

    python scripts/migrate_sales_targets_km_t1.py            # baca-saja (bawaan): apa yang akan diisi + kunci kembar
    python scripts/migrate_sales_targets_km_t1.py --apply    # isi field yang kosong

Target lama berkunci (sales, periode) tanpa PT; sebagian tanpa `period_type`. Aturan pengisian (spesifikasi KM-T1):
  * `period` berbentuk `YYYY-MM` tanpa `period_type` → `period_type = "month"`;
  * `entity_id` kosong → PT asal sales (`users.home_entity_id`; tidak ada → dilaporkan, tidak diisi).
Target lain (mis. `period` berbentuk triwulan/tahun tanpa jenis) dilaporkan, tidak diubah. Sesudah pengisian, kunci
KEMBAR (dua target berkunci sama) dilaporkan beserta id-nya dan skrip keluar 3 — menggabung atau menghapus target =
keputusan pemilik (titik henti H6); indeks unik `uq_target_pt_sales_periode` baru bisa terpasang sesudahnya.
Menjalankan `--apply` pada data nyata = titik henti H3 (ambil cadangan `sales_targets` lebih dulu). Dijalankan di dalam
container backend (butuh `backend/.env`). Aman diulang: jalan kedua tanpa perubahan.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

_BULAN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


async def rencana() -> Dict[str, Any]:
    """Daftar perubahan per target + target yang tidak bisa diisi (tanpa menulis)."""
    from db import db
    homes = {u["id"]: u.get("home_entity_id") or "" async for u in db.users.find({}, {"_id": 0, "id": 1,
                                                                                         "home_entity_id": 1})}
    ubah: List[Dict[str, Any]] = []
    lewati: List[Dict[str, Any]] = []
    async for t in db.sales_targets.find({}, {"_id": 0, "id": 1, "sales_id": 1, "period": 1, "period_type": 1,
                                              "entity_id": 1}):
        upd: Dict[str, Any] = {}
        if not t.get("period_type"):
            if _BULAN.match(str(t.get("period") or "")):
                upd["period_type"] = "month"
            else:
                lewati.append({**t, "sebab": "periode bukan YYYY-MM dan jenis periode kosong"})
        if not t.get("entity_id") or t.get("entity_id") == "all":
            home = homes.get(t.get("sales_id") or "")
            if home:
                upd["entity_id"] = home
            else:
                lewati.append({**t, "sebab": "PT kosong dan sales tanpa PT asal"})
        if upd:
            ubah.append({"id": t["id"], "set": upd})
    return {"ubah": ubah, "lewati": lewati}


async def kembar(rencana_ubah: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Kunci kembar SESUDAH pengisian (baca-saja: pengisian yang direncanakan ikut diperhitungkan)."""
    from db import db
    over = {x["id"]: x["set"] for x in rencana_ubah or []}
    seen: Dict[tuple, List[str]] = {}
    async for t in db.sales_targets.find({}, {"_id": 0, "id": 1, "entity_id": 1, "sales_id": 1, "period_type": 1,
                                              "period": 1}):
        t = {**t, **over.get(t["id"], {})}
        k = (t.get("entity_id") or "", t.get("sales_id") or "", t.get("period_type") or "", t.get("period") or "")
        if all(k):
            seen.setdefault(k, []).append(t["id"])
    return [{"kunci": k, "ids": v} for k, v in sorted(seen.items()) if len(v) > 1]


async def jalankan(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="isi field yang kosong (bawaan: baca-saja)")
    args = ap.parse_args(argv)
    from db import db
    r = await rencana()
    for x in r["ubah"]:
        print(f"Target {x['id']}: isi {', '.join(f'{k} = {v}' for k, v in x['set'].items())}")
    for x in r["lewati"]:
        print(f"Dilewati {x.get('id')}: {x['sebab']} (periode {x.get('period') or '—'})")
    if args.apply and r["ubah"]:
        for x in r["ubah"]:
            await db.sales_targets.update_one({"id": x["id"]}, {"$set": x["set"]})
        print(f"Diterapkan: {len(r['ubah'])} target diisi.")
    elif args.apply:
        print("Tanpa perubahan.")
    else:
        print(f"Mode baca-saja: {len(r['ubah'])} target akan diisi, {len(r['lewati'])} dilewati. Jalankan dengan --apply.")
    dup = await kembar(None if args.apply else r["ubah"])
    for d in dup:
        print(f"KUNCI KEMBAR (H6) PT {d['kunci'][0]} · sales {d['kunci'][1]} · {d['kunci'][2]} {d['kunci'][3]}: "
              f"{', '.join(d['ids'])}")
    if dup:
        print(f"{len(dup)} kunci kembar — putuskan target mana yang dipakai sebelum indeks unik dipasang.")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(jalankan()))

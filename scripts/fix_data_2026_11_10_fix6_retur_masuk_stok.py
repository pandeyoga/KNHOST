#!/usr/bin/env python3
"""FIX-6 — selaraskan data lama dengan keputusan pemilik 10 Nov 2026. DRY-RUN BAWAAN (tanpa `--apply` tidak menulis).

Langkah (idempoten):
  1. `return_intake_backfill` — retur penjualan TERBUKA (menunggu persetujuan / disetujui / QC) yang rollnya SUDAH
     dipindai diterima/tiba di gudang sebelum FIX-6 tetapi rollnya masih `delivered` ("di pelanggan") → roll dimasukkan
     KARANTINA RETUR di gudang pindai (D5: tidak tersedia dijual, NILAI NOL, nilai & jurnal tetap saat settle) lewat
     layanan yang sama dengan pindai (`return_intake_service.receive`). Tanpa jurnal; saldo gudang dibangun ulang.
  2. `qc_return_without_remedy` — LAPORAN saja: retur beli hasil TOLAK QC yang masih draf/menunggu persetujuan tanpa
     pilihan penyelesaian (D2). Disetujui seperti dulu (Nota Debit) — pembelian sebaiknya memastikan pilihannya
     (ganti barang / potong tagihan) dengan menolak & memutus ulang lewat QC bila perlu. Tidak diubah otomatis.
Tidak menyentuh: jurnal/nilai roll, data UAT "test" (SORD-261023-0003).
Jejak: satu dokumen `migrations` (`id = fix_data_2026_11_10_fix6_retur_masuk_stok`).

DB yang diizinkan: `kn_test_trial` / `test_database` (uji). DB lain (mis. produksi) hanya dengan `--allow-db <nama>`
yang sama persis — keputusan pemilik (koordinator: "Menjalankan skrip perbaikan data ke DB bersama/produksi" = pemilik).

Pakai (di dalam kontainer backend, repo = /app):
    python /app/scripts/fix_data_2026_11_10_fix6_retur_masuk_stok.py --db kn_test_trial            # dry-run
    python /app/scripts/fix_data_2026_11_10_fix6_retur_masuk_stok.py --db kn_test_trial --apply
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

ALLOWED_DB = {"kn_test_trial", "test_database"}


def _args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True, help="nama DB")
    ap.add_argument("--allow-db", default="", help="izin eksplisit untuk DB di luar daftar uji (nama sama persis)")
    ap.add_argument("--apply", action="store_true", help="terapkan (tanpa ini = dry-run)")
    return ap.parse_args()


ARGS = _args()
if ARGS.db not in ALLOWED_DB and ARGS.allow_db != ARGS.db:
    print(f"DITOLAK: --db {ARGS.db} bukan DB uji ({', '.join(sorted(ALLOWED_DB))}); butuh --allow-db {ARGS.db}.")
    sys.exit(2)
os.environ["DB_NAME"] = ARGS.db          # db.py membaca DB_NAME saat di-import
BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402

FLAG = "fix_data_2026_11_10_fix6_retur_masuk_stok"
ACTOR = "Sistem (FIX-6 retur masuk stok saat dipindai)"
PROTECTED_ORDERS = {"SORD-261023-0003"}
OPEN = ["pending_approval", "approved", "inspecting", "inspected"]


async def step_return_intake(apply: bool) -> dict:
    from services import return_intake_service as _intake
    todo, done = [], []
    async for ret in db.sales_returns.find({"status": {"$in": OPEN}, "roll_locations": {"$exists": True}}, {"_id": 0}):
        if ret.get("order_number") in PROTECTED_ORDERS:
            continue
        by_wh: dict = {}
        for rid, loc in (ret.get("roll_locations") or {}).items():
            if (loc or {}).get("stage") not in ("received", "arrived") or not loc.get("warehouse_id"):
                continue
            roll = await db.inventory_rolls.find_one({"id": rid}, {"_id": 0, "status": 1})
            has = await db.inventory_rolls.find_one({"return_intake.return_id": ret["id"],
                                                     "return_intake.source_roll_id": rid,
                                                     "return_intake.state": {"$in": ["received", "valued"]}},
                                                    {"_id": 0, "id": 1})
            if roll and roll.get("status") == "delivered" and not has:
                by_wh.setdefault(loc["warehouse_id"], []).append(rid)
        if not by_wh:
            continue
        todo.append({"return": ret.get("number"), "rolls": sum(len(v) for v in by_wh.values())})
        if apply:
            for wh, rids in by_wh.items():
                res = await _intake.receive(ret, rids, wh, ACTOR, f"{ret.get('number', '')}/FIX6")
                done += [x["roll_id"] for x in res["received"]]
    return {"returns": len(todo), "rolls": sum(t["rolls"] for t in todo), "sample": todo[:10], "applied_rolls": done}


async def step_qc_return_report() -> dict:
    rows = [{"number": d.get("number"), "po": d.get("po_number"), "status": d.get("status")}
            async for d in db.purchase_returns.find({"source": "qc_reject", "status": {"$in": ["draft", "pending_approval"]},
                                                     "remedy": {"$exists": False}}, {"_id": 0})]
    return {"count": len(rows), "sample": rows[:20]}


async def main() -> None:
    mode = "APPLY" if ARGS.apply else "DRY-RUN"
    print(f"[{FLAG}] DB={ARGS.db} mode={mode}")
    r1 = await step_return_intake(ARGS.apply)
    print(f"  1. return_intake_backfill: {r1['returns']} retur · {r1['rolls']} roll"
          + (f" → {len(r1['applied_rolls'])} roll masuk karantina retur" if ARGS.apply else "") + f"  contoh={r1['sample']}")
    r2 = await step_qc_return_report()
    print(f"  2. qc_return_without_remedy (laporan): {r2['count']}  contoh={r2['sample']}")
    if ARGS.apply:
        await db.migrations.update_one({"id": FLAG}, {"$set": {"id": FLAG, "at": now_iso(), "by": ACTOR,
                                                               "return_intake": r1, "qc_return_report": r2}},
                                       upsert=True)


if __name__ == "__main__":
    asyncio.run(main())

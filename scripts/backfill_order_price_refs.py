"""KM-T1 (KM-01, K-23) — harga pembanding untuk baris pesanan LAMA (sebelum `create_order` memotretnya).

    python scripts/backfill_order_price_refs.py            # baca-saja (bawaan): jumlah baris yang akan diisi / dibiarkan
    python scripts/backfill_order_price_refs.py --apply    # isi `list_price` baris yang pasti

Hanya baris ber-`price_source` `entity` (harga daftar PT) atau `global` (harga umum) yang diisi: pada baris itu harga jual
= harga pembanding, jadi `list_price = price` dan `list_price_source = price_source` pasti benar (`global_price` ikut diisi
untuk baris `global`). Baris lain (harga langganan, harga khusus, sample, pesanan khusus, tanpa sumber) DIBIARKAN kosong —
harga daftar PT pada tanggal pesanan tidak bisa direka ulang dengan pasti — dan jumlahnya dilaporkan per sumber harga.
Baris yang sudah punya `list_price` tidak disentuh (aman diulang). Fakta insentif membaca pembanding kosong sebagai
"tidak ada pembanding" (`list_value` kosong). Menjalankan `--apply` pada data nyata = titik henti H3 (ambil cadangan
`sales_orders` lebih dulu). Dijalankan di dalam container backend (butuh `backend/.env`).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

PASTI = ("entity", "global")


def isian_baris(it: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Field yang diisi untuk satu baris; None = dibiarkan (sudah ada / tidak pasti)."""
    if not isinstance(it, dict) or it.get("list_price") is not None:
        return None
    src = str(it.get("price_source") or "")
    if src not in PASTI or it.get("price") is None:
        return None
    out = {"list_price": float(it["price"]), "list_price_source": src}
    if src == "global" and it.get("global_price") is None:
        out["global_price"] = float(it["price"])
    return out


async def jalankan(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="isi baris yang pasti (bawaan: baca-saja)")
    args = ap.parse_args(argv)
    from db import db
    diisi = sudah = 0
    dibiarkan: Counter = Counter()
    pesanan = 0
    async for o in db.sales_orders.find({"items.0": {"$exists": True}}, {"_id": 0, "id": 1, "items": 1}):
        items = list(o.get("items") or [])
        ubah = False
        for it in items:
            if isinstance(it, dict) and it.get("list_price") is not None:
                sudah += 1
                continue
            isi = isian_baris(it)
            if isi is None:
                dibiarkan[str((it or {}).get("price_source") or "tanpa sumber")] += 1
                continue
            it.update(isi)
            diisi += 1
            ubah = True
        if ubah:
            pesanan += 1
            if args.apply:
                await db.sales_orders.update_one({"id": o["id"]}, {"$set": {"items": items}})
    print(f"Baris diisi: {diisi} (di {pesanan} pesanan) · sudah berpembanding: {sudah} · dibiarkan kosong: "
          f"{sum(dibiarkan.values())}")
    for src, n in sorted(dibiarkan.items()):
        print(f"  dibiarkan — sumber harga {src}: {n} baris")
    print("Diterapkan." if args.apply and diisi else ("Tanpa perubahan." if args.apply else
                                                     "Mode baca-saja: jalankan dengan --apply untuk mengisi."))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(jalankan()))

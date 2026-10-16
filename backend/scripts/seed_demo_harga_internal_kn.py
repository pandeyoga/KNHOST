"""DEMO LENGKAP KN — tahap 3: HARGA INTERNAL antar-PT (data uji).

Untuk setiap pasangan PT (dua arah) dan setiap barang yang punya stok di PT penjual dibuat kontrak
internal aktif dengan harga = 70% harga jual standar PT penjual. Idempoten: pasangan × barang yang
sudah punya harga internal aktif dilewati.
  python scripts/seed_demo_harga_internal_kn.py
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from db import db  # noqa: E402
from services import interco_price_service as ips  # noqa: E402

RATIO = 0.70
ACTOR = {"name": "Demo Lengkap (harga internal 70%)"}


async def main() -> None:
    ents = [e["id"] async for e in db.business_entities.find({"status": "active"}, {"_id": 0, "id": 1})]
    total = 0
    for seller in ents:
        for buyer in ents:
            if seller == buyer:
                continue
            res = await ips.missing(seller, buyer, only_stock=True)
            items = [{"product_id": r["product_id"], "unit_price": round(r["sell_price"] * RATIO)}
                     for r in res["rows"] if r["sell_price"] > 0]
            if not items:
                print(f"   = {seller} → {buyer}: lengkap ({res['priced']} barang)")
                continue
            out = await ips.bulk_set(seller, buyer, items, ACTOR, notes="Data demo: 70% harga jual standar PT penjual")
            total += out["count"]
            print(f"   + {seller} → {buyer}: {out['count']} harga internal (70% harga jual)")
    print(f"SELESAI tahap 3 — {total} kontrak harga internal baru.")


if __name__ == "__main__":
    asyncio.run(main())

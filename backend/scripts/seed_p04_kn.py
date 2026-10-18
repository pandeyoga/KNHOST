"""DATA ACUAN P04 (CONTOH) — Keep & Pending untuk Meja Admin Sales (badan usaha Kanda).

  SO-A  : belum diverifikasi (Keep), umur dibuat 5 hari (CONTOH) → lewat batas Keep 3 hari (CONTOH, entitas Kanda).
  SO-B  : belum diverifikasi DAN kurang barang (Keep + Pending) — tidak dihitung dua kali.
  SO-C  : sudah diverifikasi, kurang barang (Pending saja).
Lewat endpoint resmi; idempoten (`migrations.p04_demo`).  python scripts/seed_p04_kn.py
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from scripts.demo_api import Api  # noqa: E402
from scripts.seed_demo_transaksi_kn import KANDA, Ctx, days, make_so  # noqa: E402

FLAG = "p04_demo"
CUST = "Toko Tekstil Pasar Baru"


async def _short_product(c: Ctx, skip: set) -> dict:
    rows = await db.inventory_rolls.aggregate([
        {"$match": {"owner_entity_id": KANDA, "status": "available", "grade": "A", "stage": "finished"}},
        {"$group": {"_id": "$product_id", "q": {"$sum": "$length_remaining"}}},
        {"$match": {"q": {"$gte": 100, "$lte": 3000}}}, {"$sort": {"q": 1}}, {"$limit": 40}]).to_list(40)
    for r in rows:
        if r["_id"] in skip:
            continue
        p = await db.products.find_one({"id": r["_id"], "import_batch": "MIGRASI_MASTER_PRODUK_KN"}, {"_id": 0})
        if p and await db.entity_prices.find_one({"entity_id": KANDA, "product_id": p["id"]}, {"_id": 1}):
            return {**p, "_free": round(r["q"], 2)}
    raise RuntimeError("tidak ada produk Kanda yang cocok untuk contoh Pending")


async def _backorder_so(c: Ctx, p: dict) -> dict:
    s, cust = await c.u("sales.kanda"), await c.customer(CUST)
    qty = round(p["_free"] + 250, 2)
    body = {"customer_id": cust["id"], "shipping_address_id": (cust.get("addresses") or [{}])[0].get("id", ""),
            "items": [{"product_id": p["id"], "quantity": qty, "unit": p["base_unit"], "purchase_mode": "qty"}],
            "entity_id": KANDA, "payment_term_code": "NET30", "allow_backorder": True, "confirm_mixed_lot": True,
            "delivery_date": days(7), "notes": "[CONTOH P04] pesanan melebihi stok — sisa jadi Pending"}
    return await s.post("/sales-orders", body, entity=KANDA)


async def run(c: Ctx) -> str:
    sa = await c.u("salesadmin.kanda")
    a = await make_so(c, "sales.kanda", CUST, KANDA, "knit", 2, 1)
    old = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    await db.sales_orders.update_one({"id": a["id"]}, {"$set": {"created_at": old, "notes": "[CONTOH P04] Keep lewat batas"}})
    pb = await _short_product(c, set())
    b = await _backorder_so(c, pb)
    pc = await _short_product(c, {pb["id"]})
    cc = await _backorder_so(c, pc)
    await sa.post(f"/sales-orders/{cc['id']}/verify", {"note": "[CONTOH P04] lengkap"}, entity=KANDA)
    from services import config_resolver as resolver
    await resolver.set_value("sales.keep_max_age_days", 3, scope_type="entity", scope_id=KANDA,
                             actor="sistem (data contoh P04)", actor_id="", reason="[CONTOH P04] batas Keep 3 hari")
    return f"Keep {a.get('number')} · Keep+Pending {b.get('number')} · Pending {cc.get('number')} · batas Keep Kanda 3 hari"


async def main() -> None:
    done = await db.migrations.find_one({"id": FLAG}, {"_id": 0})
    if done:
        print("Data acuan P04: sudah ada —", done.get("result"))
        return
    api = Api()
    try:
        cst = (await db.business_entities.find_one({"doc_prefix": "CST"}, {"_id": 0, "id": 1}))["id"]
        res = await run(Ctx(api, cst))
        await db.migrations.update_one({"id": FLAG}, {"$set": {"result": res, "at": now_iso()}}, upsert=True)
        print("Data acuan P04:", res)
    finally:
        await asyncio.sleep(2)
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())

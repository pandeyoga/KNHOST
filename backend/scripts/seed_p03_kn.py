"""DATA ACUAN P03 (CONTOH) — transfer pemenuhan SO dua kaki: Soreang (Bandung) → Jakarta → pelanggan.

SO Kanda (pelanggan Toko Tekstil Pasar Baru) 10 roll dari SRG-01, terkonfirmasi → transfer ke GU-KANDA (Jakarta)
ditautkan ke SO, disetujui & DIKIRIM (dalam perjalanan). Penerimaan per roll sengaja dibiarkan untuk dicoba di layar
Transfer (terima 7 → retry → sisanya / exception). Lewat endpoint resmi; idempoten (`migrations.p03_demo`).
  python scripts/seed_p03_kn.py
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from scripts.demo_api import Api  # noqa: E402
from scripts.seed_demo_transaksi_kn import KANDA, Ctx, make_so, push_so  # noqa: E402

FLAG = "p03_demo"


async def run(c: Ctx) -> str:
    so = await make_so(c, "sales.kanda", "Toko Tekstil Pasar Baru", KANDA, "knit", 10, 1)
    so = await push_so(c, so, KANDA, "confirmed", "salesadmin.kanda", "warehouse.soreang")
    src, dst = await c.wh("SRG-01"), await c.wh("GU-KANDA")
    rolls = await db.inventory_rolls.find({"reserved_ref.id": so["id"], "warehouse_id": src, "status": "reserved"},
                                          {"_id": 0, "id": 1, "product_id": 1, "length_remaining": 1}).to_list(50)
    if not rolls:
        raise RuntimeError(f"SO {so.get('number')} tidak punya roll berkomitmen di SRG-01")
    items = {}
    for r in rolls:
        it = items.setdefault(r["product_id"], {"product_id": r["product_id"], "qty": 0.0, "roll_ids": []})
        it["qty"] = round(it["qty"] + r["length_remaining"], 2)
        it["roll_ids"].append(r["id"])
    wa, mgr = await c.u("whadmin"), await c.u("manager")
    tr = await wa.post("/transfers", {"source_warehouse_id": src, "dest_warehouse_id": dst, "owner_entity_id": KANDA,
                                      "sales_order_id": so["id"], "items": list(items.values()),
                                      "notes": f"[CONTOH P03] Pemenuhan {so.get('number')} — kirim dari Soreang ke Jakarta"},
                       entity=KANDA)
    await mgr.post(f"/transfers/{tr['id']}/approve", {}, entity=KANDA)
    for st in ("picking", "staging", "dispatched"):
        tr = await wa.post(f"/transfers/{tr['id']}/status", {"status": st, "updated_by": wa.user["name"]}, entity=KANDA)
    return f"{so.get('number')} ({len(rolls)} roll) → {tr.get('code')} SRG-01 → GU-KANDA status {tr.get('status')}"


async def main() -> None:
    done = await db.migrations.find_one({"id": FLAG}, {"_id": 0})
    if done:
        print("Data acuan P03: sudah ada —", done.get("result"))
        return
    api = Api()
    try:
        cst = (await db.business_entities.find_one({"doc_prefix": "CST"}, {"_id": 0, "id": 1}))["id"]
        res = await run(Ctx(api, cst))
        await db.migrations.update_one({"id": FLAG}, {"$set": {"result": res, "at": now_iso()}}, upsert=True)
        print("Data acuan P03:", res)
    finally:
        await asyncio.sleep(2)
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())

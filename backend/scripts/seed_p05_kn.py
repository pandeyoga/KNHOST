"""DATA ACUAN P05 (CONTOH) — sumber restock artikel & Pending jalur produksi (badan usaha Kanda).

  * Artikel KNKNT0067 (template SO-00005/06) → makloon [CONTOH]; ALICE KNIT → supplier [CONTOH];
    AUDIA KNIT → keduanya [CONTOH]. Artikel lain tetap "belum diatur" (DEC-07: tidak di-default).
  * KANDA/SO-00006 (Pending 250) → keputusan "reorder" → PR baris makloon → disetujui → Order Makloon
    (qty bahan manual + alasan, tanpa resep) → bahan grey knit Kanda DIKUNCI saat MKO dibuat.
  * Kebijakan `purchasing.restock_source_unknown` = block (keputusan pemilik: MD isi mapping dulu).
Idempoten (`migrations.p05_demo`).  python scripts/seed_p05_kn.py
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
from scripts.seed_demo_transaksi_kn import KANDA, Ctx  # noqa: E402

FLAG = "p05_demo"
MAPPING = (("KNKNT0067", "makloon"), ("ALICE KNIT", "supplier"), ("AUDIA KNIT", "both"))


async def _template_for(key: str) -> dict:
    if key.startswith("KN"):
        p = await db.products.find_one({"sku": {"$regex": f"^{key}"}}, {"_id": 0, "template_id": 1})
        return await db.product_templates.find_one({"id": (p or {}).get("template_id")}, {"_id": 0, "id": 1, "name": 1})
    return await db.product_templates.find_one({"name": {"$regex": f"^{key}"}}, {"_id": 0, "id": 1, "name": 1})


async def run(c: Ctx) -> str:
    mgr, sa, md = await c.u("manager"), await c.u("salesadmin.kanda"), await c.u("md")
    mapped = []
    for key, mode in MAPPING:
        t = await _template_for(key)
        if t:
            await md.put(f"/product-templates/{t['id']}/restock-source",
                          {"mode": mode, "note": "[CONTOH P05] isi oleh MD"}, entity=KANDA)
            mapped.append(f"{t['name']}={mode}")
    so = await db.sales_orders.find_one({"number": "KANDA/SO-00006"}, {"_id": 0, "id": 1, "items": 1})
    res = await sa.post(f"/sales-admin/orders/{so['id']}/fulfillment-decision",
                        {"mode": "reorder", "note": "[CONTOH P05] artikel makloon — produksi ulang"}, entity=KANDA)
    pr_id = ((res.get("result") or res).get("ref_id")) or (res.get("decision") or {}).get("ref_id")
    if not pr_id:
        pr = await db.purchase_requisitions.find_one({"source_ref_id": so["id"]}, {"_id": 0, "id": 1})
        pr_id = pr["id"]
    pr = await db.purchase_requisitions.find_one({"id": pr_id}, {"_id": 0})
    if pr.get("status") == "pending_approval":
        await mgr.post(f"/purchase-requisitions/{pr_id}/approve", {"notes": "[CONTOH P05]"}, entity=KANDA)
    line = next(i for i in pr["items"] if i.get("fulfillment_mode") == "makloon")
    grey = await c.prod("DMO-GRY-KNT-001")
    bal = await db.inventory_balances.find_one({"product_id": grey["id"], "owner_entity_id": KANDA,
                                                "available_qty": {"$gt": 0}}, {"_id": 0, "warehouse_id": 1})
    celup = await c.makloon("PT Celup Warna Dayeuhkolot")
    body = {"mode": "process_only", "material_product_id": grey["id"], "material_qty": 300, "material_unit": "kg",
            "from_warehouse_id": bal["warehouse_id"], "target_warehouse_id": bal["warehouse_id"], "entity_id": KANDA,
            "manual_material_reason": "[CONTOH P05] resep celup artikel belum diisi — qty dari pengalaman mitra",
            "steps": [{"process_type": "celup", "stage_code": "celup", "makloon_id": celup["id"],
                       "input_product_id": grey["id"], "output_product_id": line["product_id"], "input_qty": 300}],
            "notes": f"[CONTOH P05] produksi untuk {pr.get('number')} / KANDA/SO-00006"}
    out = await mgr.post(f"/purchase-requisitions/{pr_id}/realize-makloon",
                         {"line_no": line["line_no"], "payload": body}, entity=KANDA)
    from services import config_resolver as resolver
    await resolver.set_value("purchasing.restock_source_unknown", "block", scope_type="global", scope_id="",
                             actor="sistem (data contoh P05)", actor_id="",
                             reason="Keputusan pemilik DEC-07: artikel tanpa sumber restock diminta mapping MD dulu")
    mko = out.get("makloon_order") or {}
    return (f"Mapping {', '.join(mapped)} · SO-00006 → {pr.get('number')} → {mko.get('mko_number')} "
            "(bahan grey 300 kg dikunci) · kebijakan unknown=block")


async def main() -> None:
    done = await db.migrations.find_one({"id": FLAG}, {"_id": 0})
    if done:
        print("Data acuan P05: sudah ada —", done.get("result"))
        return
    api = Api()
    try:
        cst = (await db.business_entities.find_one({"doc_prefix": "CST"}, {"_id": 0, "id": 1}))["id"]
        res = await run(Ctx(api, cst))
        await db.migrations.update_one({"id": FLAG}, {"$set": {"result": res, "at": now_iso()}}, upsert=True)
        print("Data acuan P05:", res)
    finally:
        await asyncio.sleep(2)
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())

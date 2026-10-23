"""UAT BERSIH + DATA SIAP RETUR (23 Okt 2026) — dijalankan SESUDAH rantai master tanpa transaksi.

Rantai master (tanpa contoh transaksi seed_demo_transaksi / p03 / p04 / bagian SO-PR-MKO p05):
  import_master_produk_kn → import_stok_awal_kn → seed_demo_lengkap_kn → seed_demo_harga_internal_kn
  → seed_simulasi_bin_kn → seed_p01_kn → seed_p02_kn → (skrip ini)

Skrip ini (lewat ENDPOINT RESMI — aturan, jurnal, saldo, audit asli; idempoten `migrations.uat_retur_23okt`):
  1) Master yang ditetapkan selama UAT 22 Okt: sumber restock artikel (ALICE KNIT = supplier, AUDIA KNIT = keduanya,
     RIVERA RIB = makloon — contoh S8/S9), kebijakan artikel tanpa sumber restock = blokir, batas Keep Kanda 3 hari,
     simulasi RFID aktif di tiga PT (diatur pemilik di Pusat Pengaturan).
  2) Data siap RETUR PENJUALAN (S14/S15) — SO Sukacita yang SUDAH DITERIMA pelanggan (Surat Jalan + roll terkirim):
       R1 Toko Kain Sejahtera · woven 2 artikel × 3 roll · NET 30 · BELUM dibayar (uji "SO asal belum lunas")
       R2 Butik Bali Indah    · knit 1 artikel × 3 roll   · LUNAS (uji refund / saldo)
       R3 Konveksi Maju Bersama · woven 1 artikel × 2 roll · LUNAS (uji barang pengganti S15)
       R4 Moda Surabaya Fashion · knit 1 artikel × 2 roll · LUNAS (cadangan / uji tolak sebagian per roll)
  3) Data siap RETUR SUPPLIER — PO Sukacita ke PT Kain Jadi Nusantara diterima penuh di Jakarta (kedatangan → hitung
     → tutup → SPK MD Quality → Tutup SPK), rollnya tersedia untuk diretur per roll.

  python scripts/seed_uat_retur_kn.py
"""
import asyncio
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from scripts.demo_api import Api  # noqa: E402
from scripts.seed_demo_transaksi_kn import KSC, KANDA, Ctx, days, log, make_so, push_so  # noqa: E402
from scripts.seed_p05_kn import MAPPING, _template_for  # noqa: E402

FLAG = "uat_retur_23okt"


async def masters(c: Ctx) -> str:
    md = await c.u("md")
    mapped = []
    for key, mode in MAPPING:
        t = await _template_for(key)
        if t:
            await md.put(f"/product-templates/{t['id']}/restock-source", {"mode": mode, "note": "Contoh UAT (P05)"}, entity=KANDA)
            mapped.append(f"{t['name']}={mode}")
    from services import config_resolver as resolver
    cst = (await db.business_entities.find_one({"doc_prefix": "CST"}, {"_id": 0, "id": 1}))["id"]
    sets = [("purchasing.restock_source_unknown", "block", "global", ""),
            ("sales.keep_max_age_days", 3, "entity", KANDA)]
    sets += [("wms.rfid_simulation", True, "entity", e) for e in (KSC, KANDA, cst)]
    for key, val, scope, sid in sets:
        await resolver.set_value(key, val, scope_type=scope, scope_id=sid, actor="sistem (UAT bersih 23 Okt)", actor_id="",
                                 reason="Pengaturan UAT 22 Okt dibawa ke data bersih")
    return f"restock {', '.join(mapped)} · {len(sets)} pengaturan"


async def pay_exact(c: Ctx, so_id: str) -> None:
    """Lunasi SISA tagihan persis (pembulatan ke atas dulu ditolak "melebihi outstanding")."""
    so = await db.sales_orders.find_one({"id": so_id}, {"_id": 0})
    total = float(so.get("grand_total") or so.get("total") or 0)
    paid = float(so.get("paid_amount") or so.get("amount_paid") or 0)
    rest = round(total - paid, 2)
    if so.get("payment_status") == "paid" or rest <= 0:
        return
    fin = await c.u("finance")
    await fin.post("/ar-receipts", {"customer_id": so["customer_id"], "amount": rest, "method": "transfer", "entity_id": KSC,
                                    "notes": "Pelunasan pelanggan (data UAT)", "allocations": [{"order_id": so_id, "amount": rest}]},
                   entity=KSC)


async def sales_ready(c: Ctx) -> List[str]:
    plan = [("R1", "sales", "Toko Kain Sejahtera", "woven", 3, 2, 0.0),
            ("R2", "sales", "Butik Bali Indah", "knit", 3, 1, 1.0),
            ("R3", "sales2", "Konveksi Maju Bersama", "woven", 2, 1, 1.0),
            ("R4", "sales", "Moda Surabaya Fashion", "knit", 2, 1, 1.0)]
    out = []
    for tag, sales, cust, line, rolls, n_items, paid in plan:
        # Bisa dilanjutkan: SO bertanda seed ini (atau SO selesai pelanggan itu di DB bersih) dipakai lagi.
        so = await db.sales_orders.find_one({"uat_seed": tag, "entity_id": KSC}, {"_id": 0}) or             await db.sales_orders.find_one({"customer_name": cust, "entity_id": KSC, "status": "done", "uat_seed": {"$exists": False}}, {"_id": 0})
        if not so:
            so = await make_so(c, sales, cust, KSC, line, rolls, n_items)
            so = await push_so(c, so, KSC, "delivered", "salesadmin", "warehouse")
        await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"uat_seed": tag}})
        if paid:
            await pay_exact(c, so["id"])
        so = await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0, "number": 1, "status": 1, "payment_status": 1})
        out.append(f"{tag} {so['number']} {cust} ({so.get('status')}, {'lunas' if paid else 'belum dibayar'})")
        log(f"   {out[-1]}")
    return out


async def supplier_ready(c: Ctx) -> str:
    """PO → kedatangan GRN (SJ manual) → hitung per roll → tutup → SPK MD Quality → Tutup SPK (roll tersedia)."""
    mgr, wa, mdq, qc = await c.u("manager"), await c.u("wh.admin"), await c.u("mdquality"), await c.u("qc")
    sup, wh = await c.supplier("PT Kain Jadi Nusantara"), await c.wh("WH-JKT")
    # Artikel bersumber restock SUPPLIER (kebijakan artikel tanpa sumber restock = blokir PO).
    tpl = await _template_for("ALICE KNIT")
    prod = await db.products.find_one({"template_id": tpl["id"], "grade": "A", "is_active": {"$ne": False}}, {"_id": 0}) or         await db.products.find_one({"template_id": tpl["id"]}, {"_id": 0})
    rolls, per_roll = 4, 25.0
    # Bisa dilanjutkan: PO & kedatangan seed ini yang sudah ada dipakai lagi.
    po = await db.purchase_orders.find_one({"notes": "Data UAT retur supplier", "entity_id": KSC, "status": {"$ne": "cancelled"}}, {"_id": 0})
    if po:
        prod = await db.products.find_one({"id": po["items"][0]["product_id"]}, {"_id": 0})
    else:
        po = await mgr.post("/purchase-orders", {"supplier_id": sup["id"], "supplier_name": sup["name"], "warehouse_id": wh,
                                                "items": [{"product_id": prod["id"], "quantity": rolls * per_roll, "unit": prod["base_unit"],
                                                           "price": 42000, "expected_grade": "A"}],
                                                "entity_id": KSC, "tax_mode": "ppn", "expected_delivery_date": days(2),
                                                "notes": "Data UAT retur supplier"}, entity=KSC)
    po = await db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})
    if po.get("status") in ("pending_approval", "waiting_approval", "draft"):
        await (await c.api.system_admin()).post(f"/purchase-orders/{po['id']}/approve", {}, entity=KSC)
        po = await db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})

    async def grn(method: str, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        r = await wa.call(method, path, json=body, entity=KSC)
        return r.get("grn") or r
    lot = f"KJN-{po['po_number'][-5:]}"
    # Kedatangan setengah jalan dari percobaan sebelumnya → batalkan (melepas tugas PO), mulai bersih.
    async for old in db.goods_receipts.find({"entity_id": KSC, "status": {"$nin": ["closed", "cancelled"]},
                                             "$or": [{"source.po_ids": po["id"]}, {"lines.target.po_id": po["id"]}]}, {"_id": 0}):
        await wa.call("POST", f"/goods-receipts/{old['id']}/cancel", json={"expected_version": old.get("version"), "reason": "ulang seed UAT"}, entity=KSC)
    g = await grn("POST", "/goods-receipts", {"partner_type": "supplier", "partner_id": sup["id"], "warehouse_id": wh, "po_ids": [po["id"]]})
    g = await grn("POST", f"/goods-receipts/{g['id']}/manual-entry", {"expected_version": g["version"]})
    g = await grn("PATCH", f"/goods-receipts/{g['id']}/dn", {"expected_version": g["version"], "number": f"SJ-KJN-{uuid.uuid4().hex[:5].upper()}",
                                                           "po_refs": [po["po_number"]]})
    tg = await wa.get(f"/goods-receipts/{g['id']}/targets", entity=KSC)
    t = next(x for x in tg if x.get("po_id") == po["id"])
    g = await grn("POST", f"/goods-receipts/{g['id']}/lines", {"expected_version": g["version"], "item_code": prod["sku"],
                  "description": prod["name"], "po_ref": po["po_number"], "role": "output", "target": {"type": "po_task", "task_id": t["task_id"]},
                  "declared": {"qty": rolls * per_roll, "unit": prod["base_unit"], "rolls": rolls, "grade": "A", "lot": lot}})
    g = await grn("POST", f"/goods-receipts/{g['id']}/start-count", {"expected_version": g["version"]})
    kg = (prod.get("base_unit") or "").lower() == "kg"
    for _ in range(rolls):   # kain rajut (kg) ditimbang di kolom Kg; woven (yard/meter) di kolom panjang
        body = {"weight_kg": per_roll} if kg else {"length": per_roll, "length_unit": prod["base_unit"]}
        g = await grn("POST", f"/goods-receipts/{g['id']}/lines/1/rolls", {**body, "lot": lot, "grade": "A", "expected_version": g["version"]})
    g = await grn("POST", f"/goods-receipts/{g['id']}/finish-count", {"expected_version": g["version"]})
    g = await grn("POST", f"/goods-receipts/{g['id']}/close", {"expected_version": g["version"]})
    spk = await db.inspections.find_one({"$or": [{"po_id": po["id"]}, {"ref_doc_id": po["id"]}], "status": {"$nin": ["closed", "cancelled"]}},
                                        {"_id": 0}, sort=[("created_at", -1)])
    if spk:
        qc_user = await db.users.find_one({"email": "qc@kainnusantara.id"}, {"_id": 0, "id": 1})
        await wa.post(f"/inspections/{spk['id']}/assign", {"assigned_to": qc_user["id"], "bagian": "QC"}, entity=KSC)
        await qc.post(f"/inspections/{spk['id']}/start", {}, entity=KSC)
        for ln in spk.get("lines") or []:
            await mdq.post(f"/inspections/{spk['id']}/lines/{ln['id']}/inspect",
                           {"part": "md_quality", "color_result": "sesuai", "handfeel_result": "sesuai", "remark": "Sesuai sample"}, entity=KSC)
        await qc.post(f"/inspections/{spk['id']}/finish", {"decision": "terima", "remark": "Diterima seluruhnya"}, entity=KSC)
    return f"{po['po_number']} {sup['name']} · {prod['name']} {rolls} roll × {per_roll:g} {prod['base_unit']} diterima ({g.get('number')})"


async def main() -> None:
    done = await db.migrations.find_one({"id": FLAG}, {"_id": 0})
    if done:
        print("Data UAT retur: sudah ada —", done.get("result"))
        return
    api = Api()
    try:
        cst = (await db.business_entities.find_one({"doc_prefix": "CST"}, {"_id": 0, "id": 1}))["id"]
        c = Ctx(api, cst)
        log("1) master UAT 22 Okt")
        m = await masters(c)
        log(f"   {m}")
        log("2) SO siap retur penjualan")
        so = await sales_ready(c)
        log("3) PO diterima (siap retur supplier)")
        po = await supplier_ready(c)
        log(f"   {po}")
        res = {"masters": m, "sales": so, "supplier": po, "at": now_iso()}
        await db.migrations.update_one({"id": FLAG}, {"$set": {"result": res, "at": now_iso()}}, upsert=True)
        print("Data UAT retur:", res)
    finally:
        await asyncio.sleep(2)
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())

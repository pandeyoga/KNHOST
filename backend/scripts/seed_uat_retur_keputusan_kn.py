"""UAT 23 Okt — TIGA RETUR SIAP DIPUTUS (cutloss · diskon · tukar barang), lewat ENDPOINT RESMI.

Dijalankan sesudah `seed_uat_retur_kn.py` (data bersih + master). Tiap skenario: SO Sukacita baru sampai DITERIMA
pelanggan → Sales mengajukan retur 1 roll + foto bukti → Manajer ACC (SPK QC retur lahir otomatis) → lalu:

  K1 Cutloss       Toko Kain Sejahtera · woven · SO BELUM dibayar · barang kembali: diantar → scan terima Jakarta →
                   kirim & tiba Rancamalang Transit → QC (lubang, grade B)            → status *Selesai Inspeksi*
  K2 Diskon foto   Moda Surabaya Fashion · woven · SO LUNAS · kain tetap di pelanggan (KLR-06, tanpa QC fisik)
                                                                                     → status *Disetujui*
  K3 Tukar barang  Konveksi Maju Bersama · woven · SO LUNAS · barang kembali + QC (noda, grade B)
                                                                                     → status *Selesai Inspeksi*

Keputusan (cutloss MD → nilai Finance → Nego; diskon Finance → Nego; Tukar Barang → pesanan pengganti lebih banyak)
SENGAJA tidak dijalankan — itu bagian yang diuji di UAT. Idempoten (`migrations.uat_retur_keputusan_23okt`);
bila terhenti, jalankan ulang: SO/retur bertanda `uat_seed` dipakai lagi dan langkah yang sudah lewat dilewati.

  python scripts/seed_uat_retur_keputusan_kn.py
"""
import asyncio
import math
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from scripts.demo_api import Api, ApiError  # noqa: E402
from scripts.seed_demo_transaksi_kn import KSC, Ctx, log, make_so, push_so  # noqa: E402
from scripts.seed_uat_retur_kn import pay_exact  # noqa: E402

FLAG = "uat_retur_keputusan_23okt"
JKT, RCM_TRANSIT = "wh_jakarta", "RCM-TRANSIT"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000000000200015e2f3a8d0000000049454e44ae426082")

SCENARIOS = [
    {"tag": "K1", "title": "Cutloss", "sales": "sales", "cust": "Toko Kain Sejahtera", "paid": False,
     "complaint": "sobek_lubang", "reason": "Lubang & benang putus di tengah roll", "condition": "damaged",
     "note": "Ada lubang di sekitar yard 20-25; bagian lain baik. Pelanggan minta potongan bagian cacat (cutloss).",
     "qc": {"grade": "B", "condition": "minor", "remark": "Lubang 2 titik di interval 2 (15-30 yd); sisa roll baik",
            "defects": [{"point_value": 4, "count": 2, "interval": 1, "code": "LUBANG", "note": "lubang"}]}},
    {"tag": "K2", "title": "Diskon dari foto", "sales": "sales", "cust": "Moda Surabaya Fashion", "paid": True,
     "complaint": "warna_beda", "reason": "Shade sedikit beda dari sample", "condition": "ok",
     "note": "Shade sedikit lebih tua dari sample; pelanggan TETAP memakai kain dan minta potongan harga (foto terlampir).",
     "qc": None},
    {"tag": "K3", "title": "Tukar barang", "sales": "sales2", "cust": "Konveksi Maju Bersama", "paid": True,
     "complaint": "kotor_stain", "reason": "Noda minyak memanjang", "condition": "damaged",
     "note": "Noda minyak di beberapa titik; pelanggan minta ditukar kain yang sama (jumlah pengganti mungkin lebih banyak).",
     "qc": {"grade": "B", "condition": "minor", "remark": "Noda minyak 3 titik di interval 1 (0-15 yd)",
            "defects": [{"point_value": 2, "count": 3, "interval": 0, "code": "NODA", "note": "noda minyak"}]}},
]


async def upload_photo(s, rid: str, name: str) -> None:
    s.client.cookies.clear()
    r = await s.client.post(f"/api/sales-returns/{rid}/attachments", files={"file": (name, PNG, "image/png")},
                            headers={"Authorization": f"Bearer {s.token}", "X-Entity-Id": KSC})
    if r.status_code >= 400:
        raise ApiError("POST", f"/sales-returns/{rid}/attachments", r.status_code, r.text[:300])


async def ready_so(c: Ctx, sc: Dict[str, Any]) -> Dict[str, Any]:
    tag = f"UAT-{sc['tag']}"
    so = await db.sales_orders.find_one({"uat_seed": tag, "entity_id": KSC}, {"_id": 0})
    if not so:
        so = await make_so(c, sc["sales"], sc["cust"], KSC, "woven", 2, 1)
        await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"uat_seed": tag}})
    if so.get("status") not in ("done", "delivered", "shipped"):
        so = await push_so(c, so, KSC, "delivered", "salesadmin", "warehouse")
    if sc["paid"]:
        await pay_exact(c, so["id"])
    return await db.sales_orders.find_one({"id": so["id"]}, {"_id": 0})


async def ready_return(c: Ctx, sc: Dict[str, Any], so: Dict[str, Any]) -> Dict[str, Any]:
    tag = f"UAT-{sc['tag']}"
    sales, mgr = await c.u(sc["sales"]), await c.u("manager")
    ret = await db.sales_returns.find_one({"uat_seed": tag}, {"_id": 0})
    if not ret:
        data = await sales.get("/sales-returns/returnable", entity=KSC, order_id=so["id"])
        roll = next(r for r in data["rolls"] if r["remaining"] >= r["shipped_qty"] - 0.01)
        rid, qty = roll["roll_id"], roll["remaining"]
        ret = await sales.post("/sales-returns", {
            "order_id": so["id"], "return_type": "retur", "complaint_code": sc["complaint"], "complaint_note": sc["note"],
            "notes": f"Data UAT keputusan retur ({sc['tag']} {sc['title']})",
            "items": [{"product_id": roll["product_id"], "product_name": roll.get("product_name", ""), "unit": roll["unit"],
                       "quantity_returned": qty, "reason": sc["reason"], "condition": sc["condition"],
                       "roll_ids": [rid], "roll_qtys": {rid: qty}}]}, entity=KSC)
        await db.sales_returns.update_one({"id": ret["id"]}, {"$set": {"uat_seed": tag}})
        ret = await db.sales_returns.find_one({"id": ret["id"]}, {"_id": 0})
    if not [a for a in ret.get("attachments") or [] if not a.get("is_deleted")]:
        await upload_photo(sales, ret["id"], f"bukti_{sc['tag'].lower()}.png")
    if ret["status"] == "draft":
        await sales.post(f"/sales-returns/{ret['id']}/submit", {}, entity=KSC)
    ret = await db.sales_returns.find_one({"id": ret["id"]}, {"_id": 0})
    if ret["status"] == "pending_approval":
        await mgr.post(f"/sales-returns/{ret['id']}/approve", {"notes": f"Disetujui untuk diperiksa ({sc['title']})"}, entity=KSC)
    return await db.sales_returns.find_one({"id": ret["id"]}, {"_id": 0})


async def bring_back_and_qc(c: Ctx, sc: Dict[str, Any], ret: Dict[str, Any]) -> Dict[str, Any]:
    """Pengembalian barang → scan terima Jakarta → kirim & tiba Rancamalang Transit → SPK QC retur ditutup."""
    sales, wh, whr = await c.u(sc["sales"]), await c.u("warehouse"), await c.u("warehouse.rancamalang")
    wa, qc = await c.u("wh.admin"), await c.u("qc")
    rid = ret["id"]
    rcm = (await db.warehouses.find_one({"code": RCM_TRANSIT}, {"_id": 0, "id": 1}))["id"]
    codes = [no for it in ret.get("items") or [] for no in (it.get("roll_nos") or {}).values()] or \
        [r["roll_no"] async for r in db.inventory_rolls.find(
            {"id": {"$in": [x for it in ret["items"] for x in it.get("roll_ids") or []]}}, {"_id": 0, "roll_no": 1})]
    if not (ret.get("return_shipment") or {}).get("shipped"):
        await sales.put(f"/sales-returns/{rid}/return-shipment", {"method": "customer_dropoff", "shipped": True,
                                                                  "note": "Diantar pelanggan ke gudang Jakarta"}, entity=KSC)
    stage = lambda r: {(loc or {}).get("stage") for loc in (r.get("roll_locations") or {}).values()}  # noqa: E731
    ret = await db.sales_returns.find_one({"id": rid}, {"_id": 0})
    if not stage(ret) - {None}:
        await wh.post(f"/sales-returns/{rid}/journey/scan", {"stage": "received", "codes": codes, "warehouse_id": JKT}, entity=KSC)
        ret = await db.sales_returns.find_one({"id": rid}, {"_id": 0})
    if stage(ret) == {"received"}:
        await wh.post(f"/sales-returns/{rid}/journey/scan", {"stage": "dispatched", "codes": codes, "warehouse_id": JKT,
                                                             "to_warehouse_id": rcm, "carrier": "Armada KN"}, entity=KSC)
        ret = await db.sales_returns.find_one({"id": rid}, {"_id": 0})
    if stage(ret) == {"in_transit"}:
        await whr.post(f"/sales-returns/{rid}/journey/scan", {"stage": "arrived", "codes": codes, "warehouse_id": rcm}, entity=KSC)
    spk = await db.inspections.find_one({"id": ret.get("inspection_id")}, {"_id": 0})
    if spk and spk.get("status") not in ("done", "closed", "cancelled"):
        if not spk.get("assigned_to"):
            qc_user = await db.users.find_one({"email": "qc@kainnusantara.id"}, {"_id": 0, "id": 1})
            await wa.post(f"/inspections/{spk['id']}/assign", {"assigned_to": qc_user["id"], "bagian": "QC"}, entity=KSC)
        try:
            await qc.post(f"/inspections/{spk['id']}/start", {}, entity=KSC)
        except ApiError as e:   # sudah dimulai pada percobaan sebelumnya
            log(f"      (mulai SPK: {e.detail})")
        spk = await db.inspections.find_one({"id": spk["id"]}, {"_id": 0})
        for ln in spk.get("lines") or []:
            if ln.get("grade_after"):
                continue
            qty = float(ln.get("quantity") or 0)
            await qc.post(f"/inspections/{spk['id']}/lines/{ln['id']}/inspect", {
                "part": "qc", "defects": sc["qc"]["defects"], "inspect_length_yard": math.ceil(qty) if qty else None,
                "grade": sc["qc"]["grade"], "condition": sc["qc"]["condition"], "actual_qty": qty,
                "remark": sc["qc"]["remark"]}, entity=KSC)
        await qc.post(f"/inspections/{spk['id']}/finish", {"decision": "terima", "remark": "QC retur selesai — hasil per roll tersalin ke retur"},
                      entity=KSC)
    return await db.sales_returns.find_one({"id": rid}, {"_id": 0})


async def main() -> None:
    done = await db.migrations.find_one({"id": FLAG}, {"_id": 0})
    if done:
        print("Data UAT keputusan retur: sudah ada —", done.get("result"))
        return
    api = Api()
    try:
        cst = (await db.business_entities.find_one({"doc_prefix": "CST"}, {"_id": 0, "id": 1}))["id"]
        c = Ctx(api, cst)
        out = []
        for sc in SCENARIOS:
            log(f"{sc['tag']}) {sc['title']} — {sc['cust']}")
            so = await ready_so(c, sc)
            ret = await ready_return(c, sc, so)
            if sc["qc"]:
                ret = await bring_back_and_qc(c, sc, ret)
            it = (ret.get("items") or [{}])[0]
            line = (f"{sc['tag']} {sc['title']}: {ret['number']} atas {so['number']} {sc['cust']} · {it.get('product_name', '')} "
                    f"{it.get('quantity_returned')} {it.get('unit', '')} · SO {'lunas' if sc['paid'] else 'belum dibayar'} · "
                    f"status {ret['status']}")
            log(f"   {line}")
            out.append(line)
        res = {"returns": out, "at": now_iso()}
        await db.migrations.update_one({"id": FLAG}, {"$set": {"result": res, "at": now_iso()}}, upsert=True)
        print("Data UAT keputusan retur:", res)
    finally:
        await asyncio.sleep(2)
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())

"""DEMO LENGKAP KN — tahap 2: transaksi berjalan di tiap tahap lewat ENDPOINT RESMI (aturan, jurnal, saldo, audit asli).

Pembelian PR→PO→penerimaan→tagihan→bayar · penjualan berbagai status (menunggu persetujuan, terkonfirmasi, dipick,
terkirim, lunas sebagian/penuh) · makloon berjalan (tenun, celup, printing) · kas kecil. Tiap skenario dicatat di
`migrations.demo_lengkap_transaksi` sehingga dijalankan ulang tidak menggandakan.
  python scripts/seed_demo_transaksi_kn.py     (sesudah seed_demo_lengkap_kn.py)
"""
import asyncio
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from core_utils import now_iso  # noqa: E402
from db import db  # noqa: E402
from scripts.demo_api import Api, ApiError  # noqa: E402

KSC, KANDA = "ent_ksc", "ent_kanda"
MAIL = "@kainnusantara.id"
FLAG = "demo_lengkap_transaksi"


def log(msg: str) -> None:
    print(msg, flush=True)


def days(n: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=n)).strftime("%Y-%m-%d")


class Ctx:
    def __init__(self, api: Api, cst: str):
        self.api, self.cst = api, cst

    async def u(self, key: str):
        return await self.api.as_user(key + MAIL)

    async def wh(self, code: str) -> str:
        return (await db.warehouses.find_one({"code": code}, {"_id": 0, "id": 1}))["id"]

    async def prod(self, sku: str) -> Dict[str, Any]:
        return await db.products.find_one({"sku": sku}, {"_id": 0})

    async def supplier(self, name: str) -> Dict[str, Any]:
        return await db.suppliers.find_one({"name": name}, {"_id": 0})

    async def makloon(self, name: str) -> Dict[str, Any]:
        return await db.makloons.find_one({"name": name}, {"_id": 0})

    async def customer(self, name: str) -> Dict[str, Any]:
        return await db.customers.find_one({"name": name}, {"_id": 0})

    async def stocked(self, owner: str, line: str, n: int, min_qty: float) -> List[Dict[str, Any]]:
        """Produk jadi hasil migrasi yang punya stok tersedia ≥ min_qty untuk entitas pemilik."""
        rows = await db.inventory_rolls.aggregate([
            {"$match": {"owner_entity_id": owner, "status": "available", "grade": "A", "stage": "finished",
                        "line_code": line}},
            {"$group": {"_id": "$product_id", "q": {"$sum": "$length_remaining"}}},
            {"$match": {"q": {"$gte": min_qty}}}, {"$sort": {"q": -1}}, {"$limit": 40}]).to_list(40)
        out = []
        for r in rows:
            p = await db.products.find_one({"id": r["_id"], "import_batch": "MIGRASI_MASTER_PRODUK_KN"}, {"_id": 0})
            if p and await db.entity_prices.find_one({"entity_id": owner, "product_id": p["id"]}, {"_id": 1}):
                out.append(p)
            if len(out) >= n:
                break
        return out


# ─── Pembelian ───────────────────────────────────────────────────────────────────────────────────────────
async def approve_po(c: Ctx, po: Dict[str, Any], entity: str) -> Dict[str, Any]:
    if po.get("status") in ("pending_approval", "waiting_approval", "draft"):
        for key in ("manager", "md"):
            try:
                po = await (await c.u(key)).post(f"/purchase-orders/{po['id']}/approve", {}, entity=entity)
                if po.get("status") not in ("pending_approval", "waiting_approval"):
                    break
            except ApiError as e:
                log(f"      (approve {key}: {e.detail})")
    return await db.purchase_orders.find_one({"id": po["id"]}, {"_id": 0})


async def receive_po(c: Ctx, po_id: str, entity: str, wh_user: str, fraction: float = 1.0, complete: bool = True) -> None:
    wu = await c.u(wh_user)
    tasks = await db.wms_tasks.find({"po_id": po_id, "flow_type": "inbound"}, {"_id": 0}).to_list(50)
    if not tasks:
        raise RuntimeError("tugas penerimaan PO tidak terbentuk")
    for t in tasks:
        target = round(float(t.get("expected_qty") or t.get("quantity") or 0) * fraction, 2)
        tag = po_id[-6:].upper()
        per_roll = 25.0 if (t.get("unit") or "") == "kg" else 50.0
        got, i = 0.0, 0
        while got < target - 0.01:  # satu scan = satu roll fisik
            q = round(min(per_roll, target - got), 2)
            i += 1
            await wu.post(f"/inbound/tasks/{t['id']}/scan-receive", {"product_id": t["product_id"], "actual_qty": q,
                                                                      "batch": f"DM-{tag}", "lot": f"DM-LOT-{tag}", "grade": "A",
                                                                      "roll_id": f"DM-{tag}-{i:03d}"}, entity=entity)
            got += q
        if complete:
            await wu.post(f"/inbound/tasks/{t['id']}/complete", {"dye_lot": f"DM-DL-{tag}", "grade": "A"}, entity=entity)
            cur = await db.wms_tasks.find_one({"id": t["id"]}, {"_id": 0, "status": 1})
            if cur.get("status") == "qc_pending":
                for r in await wu.get(f"/inbound/qc/tasks/{t['id']}/rolls", entity=entity):
                    try:
                        await wu.post(f"/inbound/rolls/{r['id']}/inspect", {"defects": [], "note": "Inspeksi 4-point bersih (demo)"}, entity=entity)
                    except ApiError:
                        await wu.post(f"/inventory/rolls/{r['id']}/grade-override", {"grade": "A", "reason": "Cek visual lolos (demo)"}, entity=entity)
                await wu.post(f"/inbound/tasks/{t['id']}/qc-decision", {"accept_qty": got, "reject_qty": 0, "accept_grade": "A",
                                                                         "reason": "Lolos inspeksi 4-point (demo)"}, entity=entity)


async def sc_purchase_full(c: Ctx) -> str:
    """PR (Admin Sales CST) → disetujui manajer → PO → diterima penuh di Rancamalang Woven → tagihan → dibayar sebagian."""
    sa, mgr, fin = await c.u("salesadmin.cst"), await c.u("manager"), await c.u("finance")
    yarn, sup, wh = await c.prod("DMO-YRN-WVN-30S"), await c.supplier("PT Benang Sejahtera Abadi"), await c.wh("RCM-TRANSIT")
    pr = await sa.post("/purchase-requisitions", {"items": [{"product_id": yarn["id"], "quantity": 500, "unit": "kg", "est_price": 52000,
                                                             "note": "Stok benang tenun bulan ini"}],
                                                  "warehouse_id": wh, "entity_id": c.cst, "reason": "Kebutuhan benang tenun (demo)",
                                                  "needed_by_date": days(10), "submit_now": True}, entity=c.cst)
    if pr.get("status") != "approved":
        pr = await mgr.post(f"/purchase-requisitions/{pr['id']}/approve", {"notes": "Disetujui (demo)"}, entity=c.cst)
    po = await mgr.post("/purchase-orders", {"supplier_id": sup["id"], "supplier_name": sup["name"], "warehouse_id": wh,
                                            "items": [{"product_id": yarn["id"], "quantity": 500, "unit": "kg", "price": 52000, "expected_grade": "A"}],
                                            "entity_id": c.cst, "tax_mode": "ppn", "expected_delivery_date": days(7),
                                            "notes": f"Dari PR {pr.get('number', '')} (demo)"}, entity=c.cst)
    await db.purchase_requisitions.update_one({"id": pr["id"]}, {"$set": {"po_id": po["id"], "po_number": po.get("po_number", "")}})
    po = await approve_po(c, po, c.cst)
    await receive_po(c, po["id"], c.cst, "warehouse.rancamalang")
    adm = await c.api.system_admin()
    vb = await mgr.post("/vendor-bills", {"po_id": po["id"], "supplier_invoice_no": f"INV-BSA-{po['id'][-6:].upper()}",
                                          "items": [{"product_id": yarn["id"], "billed_qty": 500, "price": 52000}], "tax_mode": "ppn",
                                          "entity_id": c.cst, "due_date": days(30), "submit_now": True}, entity=c.cst)
    vb = await db.vendor_bills.find_one({"id": vb["id"]}, {"_id": 0})
    if vb.get("status") not in ("approved", "posted", "partially_paid", "paid"):
        vb = await adm.post(f"/vendor-bills/{vb['id']}/approve", {}, entity=c.cst)
    total = float(vb.get("grand_total") or vb.get("total") or 0)
    del fin
    await adm.post(f"/vendor-bills/{vb['id']}/pay", {"amount": round(total * 0.5), "cash_type": "kas_besar", "entity_id": c.cst,
                                                     "method": "transfer", "notes": "Pembayaran termin 1 (demo)"}, entity=c.cst)
    return f"PR {pr.get('number')} → PO {po.get('po_number')} diterima di Gudang Transit → tagihan dibayar 50%"


async def sc_transfer(c: Ctx) -> str:
    """Benang yang baru tiba di Gudang Transit dipindah ke Gudang Woven (diminta gudang, disetujui manajer, selesai)."""
    wu, mgr, wa = await c.u("warehouse.rancamalang"), await c.u("manager"), await c.u("whadmin")
    src, dst, yarn = await c.wh("RCM-TRANSIT"), await c.wh("RCM-WOVEN"), await c.prod("DMO-YRN-WVN-30S")
    rolls = await db.inventory_rolls.find({"warehouse_id": src, "product_id": yarn["id"], "status": "available"},
                                          {"_id": 0, "id": 1, "length_remaining": 1}).to_list(500)
    if not rolls:
        raise RuntimeError("tidak ada roll di Gudang Transit (skenario pembelian belum jalan?)")
    qty = round(sum(r["length_remaining"] for r in rolls), 2)
    tr = await wu.post("/transfers", {"source_warehouse_id": src, "dest_warehouse_id": dst, "owner_entity_id": c.cst,
                                      "items": [{"product_id": yarn["id"], "qty": qty, "unit": "kg", "roll_ids": [r["id"] for r in rolls]}],
                                      "notes": "Putaway benang dari transit ke gudang woven (demo)"}, entity=c.cst)
    if tr.get("status") == "waiting_approval":
        tr = await mgr.post(f"/transfers/{tr['id']}/approve", {}, entity=c.cst)
    for st in ("picking", "staging", "dispatched", "completed"):
        tr = await wa.post(f"/transfers/{tr['id']}/status", {"status": st, "updated_by": wa.user["name"]}, entity=c.cst)
    return f"{tr.get('code')} Transit → Woven {qty} kg ({tr.get('status')})"


async def sc_purchase_partial(c: Ctx) -> str:
    """PO grey (Sukacita, Gudang Jakarta) disetujui & diterima SEBAGIAN (60%)."""
    mgr = await c.u("manager")
    grey, sup, wh = await c.prod("DMO-GRY-WVN-001"), await c.supplier("CV Grey Mandiri Majalaya"), await c.wh("WH-JKT")
    po = await mgr.post("/purchase-orders", {"supplier_id": sup["id"], "supplier_name": sup["name"], "warehouse_id": wh,
                                            "items": [{"product_id": grey["id"], "quantity": 2000, "unit": "yard", "price": 14000, "expected_grade": "A"}],
                                            "entity_id": KSC, "tax_mode": "ppn", "expected_delivery_date": days(3),
                                            "notes": "Grey poplin — kirim bertahap (demo)"}, entity=KSC)
    po = await approve_po(c, po, KSC)
    await receive_po(c, po["id"], KSC, "warehouse", fraction=0.6, complete=False)
    return f"PO {po.get('po_number')} diterima 60% (sisa menunggu kiriman)"


async def sc_purchase_pending(c: Ctx) -> str:
    """PO kain jadi (Kanda) menunggu persetujuan + PR Kanda menunggu persetujuan."""
    sak, adm = await c.u("salesadmin.kanda"), await c.api.system_admin()
    sup, wh = await c.supplier("PT Kain Jadi Nusantara"), await c.wh("SRG-01")
    prods = await c.stocked(KANDA, "woven", 2, 100) or await c.stocked(KANDA, "knit", 2, 100)
    items = [{"product_id": p["id"], "quantity": 1500, "unit": p["base_unit"], "price": 21000, "expected_grade": "A"} for p in prods]
    po = await (await c.u("manager")).post("/purchase-orders", {"supplier_id": sup["id"], "supplier_name": sup["name"], "warehouse_id": wh,
                                                                "items": items, "entity_id": KANDA, "tax_mode": "non_ppn",
                                                                "expected_delivery_date": days(14), "notes": "Restock kain jadi (demo)"}, entity=KANDA)
    pr = await sak.post("/purchase-requisitions", {"items": [{"product_id": prods[0]["id"], "quantity": 800, "unit": prods[0]["base_unit"],
                                                              "est_price": 21000, "note": "Permintaan restock"}],
                                                   "warehouse_id": wh, "entity_id": KANDA, "reason": "Stok menipis (demo)",
                                                   "needed_by_date": days(14), "submit_now": True}, entity=KANDA)
    del adm
    return f"PO {po.get('po_number')} status {po.get('status')} · PR {pr.get('number')} status {pr.get('status')}"


# ─── Penjualan ───────────────────────────────────────────────────────────────────────────────────────────
async def make_so(c: Ctx, sales_key: str, cust_name: str, entity: str, line: str, rolls_n: float, n_items: int = 2) -> Dict[str, Any]:
    qty = rolls_n * 60
    s = await c.u(sales_key)
    cust = await c.customer(cust_name)
    prods = await c.stocked(entity, line, n_items, qty * 2)
    if not prods:
        raise RuntimeError(f"tidak ada stok {line} untuk {entity}")
    items = []
    for p in prods:  # beli per ROLL UTUH (tanpa potong) — roll FEFO yang belum dicadangkan
        rolls = await db.inventory_rolls.find({"product_id": p["id"], "owner_entity_id": entity, "status": "available",
                                              "grade": "A", "reserved_ref": None}, {"_id": 0, "id": 1, "length_remaining": 1}
                                             ).sort("created_at", 1).to_list(int(rolls_n))
        q = round(sum(r["length_remaining"] for r in rolls), 2)
        items.append({"product_id": p["id"], "quantity": q, "unit": p["base_unit"], "purchase_mode": "roll",
                      "roll_lines": [{"roll_id": r["id"], "take_qty": r["length_remaining"]} for r in rolls], "qty_rolls": len(rolls)})
    body = {"customer_id": cust["id"], "shipping_address_id": (cust.get("addresses") or [{}])[0].get("id", ""),
            "items": items,
            "entity_id": entity, "payment_term_code": "NET30", "allow_backorder": False, "confirm_mixed_lot": True,
            "delivery_date": days(3)}
    return await s.post("/sales-orders", body, entity=entity)


async def push_so(c: Ctx, so: Dict[str, Any], entity: str, upto: str, sa_key: str, wh_key: str) -> Dict[str, Any]:
    """Majukan SO: verify → approve → confirm → pick → dispatch → delivered."""
    sa, mgr = await c.u(sa_key), await c.u("manager")
    oid = so["id"]
    try:
        await sa.post(f"/sales-orders/{oid}/verify", {"note": "Alamat, termin & isi pesanan lengkap (demo)"}, entity=entity)
    except ApiError as e:
        log(f"      (verify: {e.detail})")
    so = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
    if so.get("status") in ("waiting_approval", "pending_approval") or so.get("approval_required"):
        if so.get("status") not in ("waiting_approval", "pending_approval"):
            try:
                await sa.post(f"/sales-orders/{oid}/submit-for-approval", {}, entity=entity)
            except ApiError as e:
                log(f"      (submit-approval: {e.detail})")
        if upto == "approval":
            return await db.sales_orders.find_one({"id": oid}, {"_id": 0})
        await mgr.post(f"/sales-orders/{oid}/approve", {"note": "Disetujui (demo)"}, entity=entity)
    if upto == "approval":
        return await db.sales_orders.find_one({"id": oid}, {"_id": 0})
    await sa.post(f"/sales-orders/{oid}/confirm", {}, entity=entity)
    if upto == "confirmed":
        return await db.sales_orders.find_one({"id": oid}, {"_id": 0})
    wu = await c.u(wh_key)
    for t in await db.wms_tasks.find({"order_id": oid, "flow_type": "outbound"}, {"_id": 0}).to_list(50):
        try:
            await wu.post(f"/outbound/tasks/{t['id']}/release", {}, entity=entity)
        except ApiError:
            pass
        await wu.call("POST", f"/outbound/tasks/{t['id']}/scan-pick", json={}, entity=entity, params={"actual_qty": t.get("quantity")})
    if upto != "picked":
        # Roll demo belum bertag RFID → Final Loading Check lewat pengecualian berizin (tercatat audit).
        await mgr.post(f"/outbound/so/{oid}/loading-check/override",
                       {"reason": "Data demo: roll belum bertag RFID, muatan dicek manual"}, entity=entity)
        for t in await db.wms_tasks.find({"order_id": oid, "flow_type": "outbound"}, {"_id": 0, "id": 1}).to_list(50):
            await wu.post(f"/outbound/tasks/{t['id']}/dispatch", {}, entity=entity)
    if upto == "delivered":
        await sa.post(f"/sales-orders/{oid}/mark-delivered", {}, entity=entity)
    return await db.sales_orders.find_one({"id": oid}, {"_id": 0})


async def pay_so(c: Ctx, so: Dict[str, Any], entity: str, fraction: float) -> float:
    fin = await c.u("finance")
    total = float(so.get("grand_total") or so.get("total") or 0)
    amt = round(total * fraction)
    await fin.post("/ar-receipts", {"customer_id": so["customer_id"], "amount": amt, "method": "transfer", "entity_id": entity,
                                    "notes": "Pembayaran pelanggan (demo)", "allocations": [{"order_id": so["id"], "amount": amt}]}, entity=entity)
    return amt


async def sc_sales_ksc(c: Ctx) -> str:
    out = []
    so = await make_so(c, "sales", "Toko Kain Sejahtera", KSC, "woven", 3)
    so = await push_so(c, so, KSC, "delivered", "salesadmin", "warehouse")
    await pay_so(c, so, KSC, 1.0)
    out.append(f"{so['number']} terkirim & LUNAS")
    so = await make_so(c, "sales2", "Konveksi Maju Bersama", KSC, "woven", 4)
    so = await push_so(c, so, KSC, "dispatched", "salesadmin", "warehouse")
    await pay_so(c, so, KSC, 0.4)
    out.append(f"{so['number']} dikirim, bayar 40%")
    so = await make_so(c, "sales", "Butik Bali Indah", KSC, "knit", 2, 1)
    so = await push_so(c, so, KSC, "confirmed", "salesadmin", "warehouse")
    out.append(f"{so['number']} {so['status']}")
    return " · ".join(out)


async def sc_sales_cst(c: Ctx) -> str:
    out = []
    so = await make_so(c, "sales.cst", "PT Fashion Ibukota", c.cst, "knit", 6)
    so = await push_so(c, so, c.cst, "dispatched", "salesadmin.cst", "warehouse.rancamalang")
    await pay_so(c, so, c.cst, 0.5)
    out.append(f"{so['number']} dikirim, bayar 50%")
    so = await make_so(c, "sales.cst", "Konveksi Tanah Abang Makmur", c.cst, "woven", 3)
    so = await push_so(c, so, c.cst, "picked", "salesadmin.cst", "warehouse.rancamalang")
    out.append(f"{so['number']} {so['status']}")
    return " · ".join(out)


async def sc_sales_kanda(c: Ctx) -> str:
    out = []
    # Pelanggan baru berplafon kecil → pesanan melebihi plafon kredit → menunggu persetujuan manajer.
    so = await make_so(c, "sales.kanda", "CV Garmen Soreang Jaya", KANDA, "knit", 12, 3)
    so = await push_so(c, so, KANDA, "approval", "salesadmin.kanda", "warehouse.soreang")
    out.append(f"{so['number']} {so['status']}")
    so = await make_so(c, "sales.kanda", "Toko Tekstil Pasar Baru", KANDA, "knit", 2, 1)
    so = await push_so(c, so, KANDA, "delivered", "salesadmin.kanda", "warehouse.soreang")
    out.append(f"{so['number']} terkirim, belum dibayar")
    return " · ".join(out)


# ─── Makloon ─────────────────────────────────────────────────────────────────────────────────────────────
async def first_finished(line: str, owner: str) -> Dict[str, Any]:
    return await db.products.find_one({"import_batch": "MIGRASI_MASTER_PRODUK_KN", "line_code": line, "entity_ids": owner}, {"_id": 0})


async def sc_makloon(c: Ctx) -> str:
    mgr = await c.u("manager")
    out = []
    tenun, rajut = await c.makloon("CV Tenun Rancaekek"), await c.makloon("PT Rajut Cigondewah")
    celup, prn = await c.makloon("PT Celup Warna Dayeuhkolot"), await c.makloon("CV Printing Sablon Cimahi")
    w_wvn, w_knt, w_prn = await c.wh("RCM-WOVEN"), await c.wh("RCM-KNITTING"), await c.wh("RCM-PRINTING")
    yw, yk = await c.prod("DMO-YRN-WVN-30S"), await c.prod("DMO-YRN-KNT-30S")
    gw, gk = await c.prod("DMO-GRY-WVN-001"), await c.prod("DMO-GRY-KNT-001")
    pfd_k, pfp_w = await c.prod("DMO-PFD-KNT-001"), await c.prod("DMO-PFP-WVN-001")
    fin_k, fin_p = await first_finished("knit", c.cst), await first_finished("printing", KSC) or await first_finished("printing", c.cst)
    # M1 — benang → tenun → grey: bahan sudah dikirim ke penenun (sedang diproses)
    m1 = await mgr.post("/makloon-orders", {"mode": "process_only", "material_product_id": yw["id"], "material_qty": 300, "material_unit": "kg",
                                            "from_warehouse_id": w_wvn, "target_warehouse_id": w_wvn, "entity_id": c.cst,
                                            "steps": [{"process_type": "tenun", "stage_code": "tenun", "makloon_id": tenun["id"],
                                                       "input_product_id": yw["id"], "output_product_id": gw["id"], "input_qty": 300}],
                                            "notes": "Tenun grey poplin (demo)"}, entity=c.cst)
    await mgr.post(f"/makloon-orders/{m1['id']}/issue", {"step_seq": 1, "from_warehouse_id": w_wvn}, entity=c.cst)
    out.append(f"{m1.get('mko_number')} tenun: bahan di mitra")
    # M2 — benang knit → rajut → grey knit: selesai diterima kembali
    m2 = await mgr.post("/makloon-orders", {"mode": "process_only", "material_product_id": yk["id"], "material_qty": 250, "material_unit": "kg",
                                            "from_warehouse_id": w_knt, "target_warehouse_id": w_knt, "entity_id": c.cst,
                                            "steps": [{"process_type": "rajut", "stage_code": "rajut", "makloon_id": rajut["id"],
                                                       "input_product_id": yk["id"], "output_product_id": gk["id"], "input_qty": 250}],
                                            "notes": "Rajut single jersey (demo)"}, entity=c.cst)
    await mgr.post(f"/makloon-orders/{m2['id']}/issue", {"step_seq": 1, "from_warehouse_id": w_knt}, entity=c.cst)
    rolls = [{"lot": f"RJT-{m2['id'][-5:].upper()}", "length": 24.5, "grade": "A", "dye_lot": ""} for _ in range(10)]
    await (await c.u("warehouse.rancamalang")).post(f"/makloon-orders/{m2['id']}/receive", {
        "step_seq": 1, "actual_output_qty": 245, "output_warehouse_id": w_knt, "supplier_dn": f"SJ-RJT-{m2['id'][-4:]}",
        "supplier_invoice_no": f"INV-RJT-{m2['id'][-4:]}", "rolls": rolls}, entity=c.cst)
    out.append(f"{m2.get('mko_number')} rajut: diterima 245 kg grey")
    # M3 — grey knit → pre-treatment (PFD) → celup → kain jadi: langkah 1 dikirim
    m3 = await mgr.post("/makloon-orders", {"mode": "process_only", "material_product_id": gk["id"], "material_qty": 200, "material_unit": "kg",
                                            "from_warehouse_id": w_knt, "target_warehouse_id": w_knt, "entity_id": c.cst,
                                            "steps": [{"process_type": "pre_treatment", "stage_code": "pfd", "target_use": "dye", "makloon_id": celup["id"],
                                                       "input_product_id": gk["id"], "output_product_id": pfd_k["id"], "input_qty": 200},
                                                      {"process_type": "celup", "stage_code": "celup", "makloon_id": celup["id"],
                                                       "input_product_id": pfd_k["id"], "output_product_id": fin_k["id"]}],
                                            "notes": "Celup knit 2 langkah (demo)"}, entity=c.cst)
    await mgr.post(f"/makloon-orders/{m3['id']}/issue", {"step_seq": 1, "from_warehouse_id": w_knt}, entity=c.cst)
    out.append(f"{m3.get('mko_number')} pre-treatment+celup: langkah 1 di mitra")
    # M4 — PFP → printing → kain print: SPK dibuat (bahan TERCADANG makloon, belum dikirim)
    if fin_p:
        owner = KSC if KSC in (fin_p.get("entity_ids") or []) else c.cst
        m4 = await mgr.post("/makloon-orders", {"mode": "process_only", "material_product_id": pfp_w["id"], "material_qty": 500, "material_unit": "yard",
                                                "from_warehouse_id": w_prn if owner == c.cst else await c.wh("WH-JKT"),
                                                "target_warehouse_id": w_prn if owner == c.cst else await c.wh("WH-JKT"), "entity_id": owner,
                                                "steps": [{"process_type": "printing", "stage_code": "printing", "makloon_id": prn["id"],
                                                           "input_product_id": pfp_w["id"], "output_product_id": fin_p["id"], "input_qty": 500, "colors": 4}],
                                                "notes": "Printing motif (demo) — bahan dicadangkan"}, entity=owner)
        out.append(f"{m4.get('mko_number')} printing: menunggu kirim bahan")
    return " · ".join(out)


# ─── Kas ─────────────────────────────────────────────────────────────────────────────────────────────────
async def sc_cash(c: Ctx) -> str:
    fin = await c.u("finance")
    n = 0
    for eid in (KSC, KANDA, c.cst):
        for direction, amt, cat, desc in (("out", 350_000, "operasional", "Bensin & tol pengiriman"),
                                          ("out", 1_250_000, "operasional", "Perbaikan forklift gudang"),
                                          ("in", 2_000_000, "lain", "Penjualan karung & kardus bekas")):
            await fin.post("/cash-transactions", {"cash_type": "kas_kecil", "direction": direction, "amount": amt, "category": cat,
                                                  "description": f"{desc} (demo)", "entity_id": eid}, entity=eid)
            n += 1
    return f"{n} transaksi kas kecil di 3 entitas"


SCENARIOS = [("pembelian_lengkap", sc_purchase_full), ("pindah_gudang", sc_transfer), ("pembelian_parsial", sc_purchase_partial),
             ("pembelian_menunggu", sc_purchase_pending), ("penjualan_sukacita", sc_sales_ksc),
             ("penjualan_cipta_sandang", sc_sales_cst), ("penjualan_kanda", sc_sales_kanda),
             ("makloon", sc_makloon), ("kas", sc_cash)]


async def main() -> None:
    if not await db.migrations.find_one({"id": "demo_lengkap_master"}):
        sys.exit("Jalankan dulu scripts/seed_demo_lengkap_kn.py (master & stok demo).")
    cst = (await db.business_entities.find_one({"doc_prefix": "CST"}, {"_id": 0, "id": 1}))["id"]
    done = (await db.migrations.find_one({"id": FLAG}, {"_id": 0}) or {}).get("done", {})
    api = Api()
    c = Ctx(api, cst)
    failed = []
    try:
        for i, (key, fn) in enumerate(SCENARIOS, 1):
            if key in done:
                log(f"{i}/{len(SCENARIOS)} {key}: sudah ada — {done[key]}")
                continue
            try:
                res = await fn(c)
                done[key] = res
                await db.migrations.update_one({"id": FLAG}, {"$set": {"done": done, "updated_at": now_iso()}}, upsert=True)
                log(f"{i}/{len(SCENARIOS)} {key}: OK — {res}")
            except Exception as e:  # noqa: BLE001
                failed.append(key)
                log(f"{i}/{len(SCENARIOS)} {key}: GAGAL — {e}")
                if not isinstance(e, ApiError):
                    traceback.print_exc()
    finally:
        await asyncio.sleep(3)  # beri waktu tugas latar (notifikasi/turn) selesai sebelum klien ditutup
        await api.close()
    if failed:
        sys.exit(f"Selesai dengan {len(failed)} skenario gagal: {', '.join(failed)} (jalankan ulang setelah diperbaiki)")
    log("SELESAI tahap 2 — semua skenario transaksi demo OK.")


if __name__ == "__main__":
    asyncio.run(main())

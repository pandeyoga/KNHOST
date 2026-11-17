"""Dasar tiap peserta: akun Finance sendiri, pelanggan & pemasok latihan, dua SO terkirim (piutang), dua tagihan supplier."""
from typing import Any, Dict

from core_utils import hash_password, now_iso
from db import db
from scripts.seed_demo_transaksi_kn import approve_po, days, make_so, push_so, receive_po

from .konteks import KSC, SANDI, TANDA, LatihCtx, Peserta


async def akun(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    adm = await lc.admin()
    if not await db.users.find_one({"email": p.email}, {"_id": 1}):
        await adm.post("/users", {"name": p.nama, "email": p.email, "role": "finance", "password": SANDI,
                                  "phone": f"0812777{p.no:05d}", "home_entity_id": KSC, "allowed_entity_ids": [KSC]})
    await db.users.update_one({"email": p.email}, {"$set": {
        "role": "finance", "status": "active", "home_entity_id": KSC, "allowed_entity_ids": [KSC],
        "password_hash": hash_password(SANDI), "must_change_password": False, "training_batch": TANDA,
        "updated_at": now_iso()}})
    await db.login_attempts.delete_many({"identifier": {"$regex": p.email.replace(".", r"\.") + "$"}})
    return {"akun": p.email, "sandi": SANDI}


async def mitra(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    adm = await lc.admin()
    sales = await db.users.find_one({"email": "sales@kainnusantara.id"}, {"_id": 0, "id": 1})
    if not await lc.customer_of(p):
        c = await adm.post("/customers", {
            "name": p.pelanggan, "pic_name": f"Bu Peserta {p.kode}", "phone": f"0813777{p.no:05d}", "city": "Bandung",
            "address": f"Jl. Latihan Keuangan No. {p.no}, Bandung", "type": "Wholesale", "segment": "Wholesale",
            "credit_limit": 300_000_000, "assigned_sales_id": sales["id"], "entity_id": KSC,
            "payment_profile": {"default_method": "tempo", "term_days": 30}}, entity=KSC)
        await lc.tag("customers", c["id"], p, "pelanggan")
    if not await lc.supplier_of(p):
        s = await adm.post("/suppliers", {
            "name": p.pemasok, "goods_type": "kain grey", "city": "Bandung", "address": f"Kawasan Industri Majalaya Blok {p.no}",
            "pic_name": "Bagian Penjualan", "phone": f"022777{p.no:05d}", "payment_term_code": "NET30", "lead_time_days": 7,
            "entity_id": "all", "origin_type": "local", "notes": "Pemasok latihan keuangan"}, entity=KSC)
        await lc.tag("suppliers", s["id"], p, "pemasok")
    return {"pelanggan": p.pelanggan, "pemasok": p.pemasok}


async def _so_terkirim(lc: LatihCtx, p: Peserta, peran: str, line: str) -> Dict[str, Any]:
    so = await make_so(lc, "sales", p.pelanggan, KSC, line, 1, 1)
    so = await push_so(lc, so, KSC, "delivered", "salesadmin", "warehouse")
    await lc.tag("sales_orders", so["id"], p, peran)
    so = await lc.so(so["id"])
    return {"so": so.get("number"), "so_id": so["id"], "total": round(float(so.get("grand_total") or 0), 2),
            "status": so.get("status")}


async def so_lunas(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """F02 — SO terkirim, belum dibayar: peserta mencatat pelunasan penuh lewat transfer bank."""
    return await _so_terkirim(lc, p, "so_lunas", "woven")


async def so_sebagian(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """F03/F04 — SO terkirim, belum dibayar: bayar sebagian, lalu kelebihan bayar jadi saldo pelanggan."""
    return await _so_terkirim(lc, p, "so_sebagian", "woven")


async def _tagihan(lc: LatihCtx, p: Peserta, peran: str, qty: float, price: float) -> Dict[str, Any]:
    mgr = await lc.u("manager")
    adm = await lc.admin()
    grey, sup, wh = await lc.prod("DMO-GRY-WVN-001"), await lc.supplier_of(p), await lc.wh("WH-JKT")
    po = await mgr.post("/purchase-orders", {
        "supplier_id": sup["id"], "supplier_name": sup["name"], "warehouse_id": wh,
        "items": [{"product_id": grey["id"], "quantity": qty, "unit": "yard", "price": price, "expected_grade": "A"}],
        "entity_id": KSC, "tax_mode": "ppn", "expected_delivery_date": days(3),
        "notes": f"Pembelian grey latihan peserta {p.kode}"}, entity=KSC)
    po = await approve_po(lc, po, KSC)
    await receive_po(lc, po["id"], KSC, "warehouse")
    vb = await mgr.post("/vendor-bills", {
        "po_id": po["id"], "supplier_invoice_no": f"INV-LTH{p.kode}-{po['id'][-5:].upper()}",
        "items": [{"product_id": grey["id"], "billed_qty": qty, "price": price}], "tax_mode": "ppn",
        "entity_id": KSC, "due_date": days(30), "submit_now": True}, entity=KSC)
    vb = await db.vendor_bills.find_one({"id": vb["id"]}, {"_id": 0})
    if vb.get("status") not in ("approved", "posted", "partially_paid", "paid"):
        await adm.post(f"/vendor-bills/{vb['id']}/approve", {}, entity=KSC)
        vb = await db.vendor_bills.find_one({"id": vb["id"]}, {"_id": 0})
    await lc.tag("purchase_orders", po["id"], p, peran)
    await lc.tag("vendor_bills", vb["id"], p, peran)
    return {"po": po.get("po_number"), "tagihan": vb.get("number") or vb.get("bill_number"), "tagihan_id": vb["id"],
            "faktur_supplier": vb.get("supplier_invoice_no"), "total": round(float(vb.get("grand_total") or vb.get("total") or 0), 2),
            "status": vb.get("status")}


async def tagihan_bayar(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """F11 — tagihan supplier terposting, belum dibayar: peserta membayar dari rekening bank."""
    return await _tagihan(lc, p, "tagihan_bayar", 120, 14000)


async def tagihan_kontrabon(lc: LatihCtx, p: Peserta) -> Dict[str, Any]:
    """F11 — tagihan kedua untuk latihan tukar faktur (kontrabon)."""
    return await _tagihan(lc, p, "tagihan_kontrabon", 80, 14500)


PREPS = [("akun", akun), ("mitra", mitra), ("so_lunas", so_lunas), ("so_sebagian", so_sebagian),
         ("tagihan_bayar", tagihan_bayar), ("tagihan_kontrabon", tagihan_kontrabon)]

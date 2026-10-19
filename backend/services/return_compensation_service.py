"""LN-092 — cutloss & diskon retur (KLR-01/02/06/07, owner 2026-10-19).

Cutloss: MD mencatat QTY CACAT dalam yard saat QC (bukan kelipatan; mesin QC = yard); produk berbasis kg
dikonversi otomatis lewat master UoM. Customer menerima potongan baik; kompensasi = harga transaksi awal
(neto setelah diskon) × qty cacat. Diskon: nominal rupiah per item untuk qty cacat, boleh tanpa barang kembali
(bukti foto/video); nilainya diputus Finance. Keduanya diselesaikan sebagai `nego` (Credit Note tanpa gerak stok).
"""
from typing import Any, Dict, List

from core_utils import new_id, now_iso
from db import db

QC_UNIT = "yard"


async def _net_unit_price(order: Dict[str, Any], product_id: str) -> float:
    """Harga transaksi awal per satuan dasar (line_total ÷ qty dasar, dikurangi diskon header)."""
    hdr = float(order.get("order_discount_percent", 0) or 0)
    tot, qty = 0.0, 0.0
    for it in order.get("items", []):
        if it.get("product_id") != product_id:
            continue
        q = float(it.get("base_quantity") or it.get("quantity", 0) or 0)
        lt = it.get("line_total")
        tot += float(lt) if lt is not None else q * float(it.get("price", it.get("unit_price", 0)) or 0)
        qty += q
    net = tot / qty if qty > 0 else 0.0
    return round(net * (1 - hdr / 100.0), 4) if hdr > 0 else round(net, 4)


def _item(ret: Dict[str, Any], product_id: str) -> Dict[str, Any]:
    it = next((x for x in ret.get("items", []) if x.get("product_id") == product_id), None)
    if not it:
        raise ValueError("Produk tidak ada di retur ini")
    return it


async def record_cutloss(ret: Dict[str, Any], product_id: str, defect_yard: float, roll_id: str,
                         note: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    from services.roll_service import to_base_qty
    if ret.get("status") not in ("received", "inspecting", "inspected", "approved"):
        raise ValueError(f"Qty cacat dicatat saat QC (status sekarang: {ret.get('status')}).")
    if (ret.get("compensation") or {}).get("status") == "decided":
        raise ValueError("Kompensasi sudah diputus Finance — batalkan keputusan dulu untuk mengubah qty cacat.")
    if defect_yard <= 0:
        raise ValueError("Qty cacat (yard) harus lebih dari 0")
    it = _item(ret, product_id)
    prod = await db.products.find_one({"id": product_id}, {"_id": 0}) or {}
    base = (prod.get("base_unit") or it.get("unit") or "yard").lower()
    qty_base = defect_yard if base == QC_UNIT else round(await to_base_qty(prod, defect_yard, QC_UNIT), 4)
    limit = float(it.get("quantity_returned", 0) or 0)
    if limit and qty_base > limit + 1e-6:
        raise ValueError(f"Qty cacat {qty_base:g} {base} melebihi qty retur {limit:g} {base}.")
    entry = {"id": new_id("ctl"), "product_id": product_id, "product_name": it.get("product_name", ""),
             "roll_id": roll_id or "", "defect_yard": round(defect_yard, 2), "qty_base": qty_base, "unit_base": base,
             "converted": base != QC_UNIT, "note": (note or "").strip(), "recorded_by": actor.get("name", ""),
             "recorded_by_id": actor.get("id", ""), "recorded_at": now_iso()}
    others = [c for c in ret.get("cutloss") or [] if not (c["product_id"] == product_id and c.get("roll_id", "") == entry["roll_id"])]
    await db.sales_returns.update_one({"id": ret["id"]}, {"$set": {"cutloss": others + [entry], "updated_at": now_iso()}})
    return entry


async def preview(ret: Dict[str, Any]) -> Dict[str, Any]:
    order = await db.sales_orders.find_one({"id": ret["order_id"]}, {"_id": 0}) or {}
    rows: List[Dict[str, Any]] = []
    for c in ret.get("cutloss") or []:
        price = await _net_unit_price(order, c["product_id"])
        rows.append({**c, "kind": "cutloss", "qty": c["qty_base"], "unit_price": price,
                     "amount": round(c["qty_base"] * price, 2)})
    return {"cutloss": rows, "compensation": ret.get("compensation") or {},
            "basis": "Harga transaksi awal (neto setelah diskon/harga khusus) × qty cacat"}


async def decide(ret: Dict[str, Any], lines: List[Dict[str, Any]], note: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Finance memutus nilai. kind=cutloss → nilai dihitung sistem; kind=discount → nominal rupiah input Finance."""
    if ret.get("status") in ("refund_settled", "credit_settled", "nego_settled", "rejected", "cancelled"):
        raise ValueError("Retur sudah selesai")
    if len((note or "").strip()) < 5:
        raise ValueError("Catatan keputusan Finance wajib (min. 5 karakter)")
    pv = {(r["product_id"], r.get("roll_id", "")): r for r in (await preview(ret))["cutloss"]}
    out: List[Dict[str, Any]] = []
    for ln in lines or []:
        kind, pid = ln.get("kind"), ln.get("product_id", "")
        it = _item(ret, pid)
        if kind == "cutloss":
            src = [r for (p, _), r in pv.items() if p == pid]
            if not src:
                raise ValueError("Qty cacat cutloss belum dicatat MD untuk produk ini")
            qty, amount = round(sum(r["qty"] for r in src), 4), round(sum(r["amount"] for r in src), 2)
        elif kind == "discount":
            qty, amount = float(ln.get("qty") or 0), round(float(ln.get("amount") or 0), 2)
            if qty <= 0 or amount <= 0:
                raise ValueError("Diskon: qty cacat dan nominal rupiah wajib > 0")
            if qty > float(it.get("quantity_returned", 0) or 0) + 1e-6:
                raise ValueError("Qty diskon melebihi qty retur item")
        else:
            raise ValueError("Jenis kompensasi tidak dikenal (cutloss | discount)")
        out.append({"kind": kind, "product_id": pid, "product_name": it.get("product_name", ""), "unit": it.get("unit", ""),
                    "qty": qty, "amount": amount, "evidence_ids": list(ln.get("evidence_ids") or [])})
    if not out:
        raise ValueError("Minimal satu baris kompensasi")
    comp = {"status": "decided", "lines": out, "total": round(sum(x["amount"] for x in out), 2),
            "note": note.strip(), "decided_by": actor.get("name", ""), "decided_by_id": actor.get("id", ""),
            "decided_at": now_iso()}
    await db.sales_returns.update_one({"id": ret["id"]}, {"$set": {"compensation": comp, "updated_at": now_iso()}})
    return comp


async def revoke(ret: Dict[str, Any], actor: Dict[str, Any]) -> None:
    if ret.get("status") == "nego_settled":
        raise ValueError("Retur sudah diselesaikan — gunakan koreksi (reverse) penyelesaian")
    await db.sales_returns.update_one({"id": ret["id"]}, {"$set": {
        "compensation.status": "revoked", "compensation.revoked_by": actor.get("name", ""),
        "compensation.revoked_at": now_iso()}})


def settle_items(ret: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Baris Credit Note `nego` dari keputusan Finance (nilai eksplisit, tanpa gerak stok)."""
    comp = ret.get("compensation") or {}
    if comp.get("status") != "decided":
        return []
    return [{"product_id": x["product_id"], "product_name": x["product_name"], "unit": x["unit"],
             "quantity_returned": x["qty"], "credit_amount": x["amount"], "condition": "ok",
             "reason": "Cutloss — kompensasi qty cacat" if x["kind"] == "cutloss" else "Diskon qty cacat (nominal Finance)"}
            for x in comp.get("lines", [])]

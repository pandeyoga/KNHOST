"""L02 LN-023-T02 — rekonsiliasi PO saat ditutup-kurang: sisa order, tagihan (AP) dan kelebihan bayar.

Hanya menghitung & mencatat tindak lanjut eksplisit; tidak menulis jurnal maupun mengubah receiving aktual.
"""
from typing import Any, Dict, List

from db import db
from core_utils import now_iso

EPS = 0.01


async def build(po: Dict[str, Any]) -> Dict[str, Any]:
    from services.vendor_bill_service import AP_BILL_STATUSES
    ordered_g = sum(float(i.get("quantity") or 0) * float(i.get("price") or 0) for i in po.get("items") or [])
    received_g = sum(float(i.get("received_qty") or 0) * float(i.get("price") or 0) for i in po.get("items") or [])
    grand = float(po.get("grand_total") or 0) or ordered_g
    ratio = grand / ordered_g if ordered_g > EPS else 1.0      # basis tagihan (diskon & PPN) per nilai baris
    received = round(received_g * ratio, 2)
    returned = round(float(po.get("returned_amount") or 0), 2)
    billed = paid_bills = 0.0
    bills: List[Dict[str, Any]] = []
    async for b in db.vendor_bills.find({"po_id": po["id"], "status": {"$in": list(AP_BILL_STATUSES)}}, {"_id": 0}):
        g, p = float(b.get("grand_total") or b.get("total_amount") or 0), float(b.get("amount_paid") or 0)
        billed += g
        paid_bills += p
        bills.append({"id": b.get("id"), "number": b.get("bill_number"), "grand_total": round(g, 2),
                      "amount_paid": round(p, 2)})
    billed, paid = round(billed, 2), round(paid_bills + float(po.get("amount_paid") or 0), 2)
    payable = round(max(received - returned, 0.0), 2)
    lines = []
    for i in po.get("items") or []:
        short = round(float(i.get("quantity") or 0) - float(i.get("received_qty") or 0), 4)
        if short > 0.0001:
            lines.append({"product_id": i.get("product_id"), "product_name": i.get("product_name") or i.get("name", ""),
                          "unit": i.get("unit", ""), "ordered_qty": float(i.get("quantity") or 0),
                          "received_qty": float(i.get("received_qty") or 0), "cancelled_qty": short,
                          "cancelled_value": round(short * float(i.get("price") or 0) * ratio, 2)})
    s = {
        "ordered_value": round(grand, 2), "received_value": received, "returned_value": returned,
        "payable_value": payable, "billed_total": billed, "paid_total": paid,
        "cancelled_value": round(grand - received, 2), "cancelled_lines": lines, "bills": bills,
        "unbilled_received": round(max(payable - billed, 0.0), 2),
        "over_billed": round(max(billed - payable, 0.0), 2),
        "over_paid": round(max(paid - payable, 0.0), 2),
        "dp_amount": round(float(po.get("dp_amount") or 0), 2),
    }
    s["balanced"] = abs(round(s["ordered_value"] - s["cancelled_value"] - s["received_value"], 2)) < EPS and \
        abs(round(s["billed_total"] - s["over_billed"] + s["unbilled_received"] - s["payable_value"], 2)) < EPS
    s["follow_ups"] = _follow_ups(s)
    return s


def _follow_ups(s: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    if s["cancelled_value"] > EPS:
        out.append({"code": "remaining_cancelled", "owner": "md", "amount": s["cancelled_value"],
                    "label": "Sisa order tidak ditunggu lagi — beri tahu supplier pembatalan sisa."})
    if s["unbilled_received"] > EPS:
        out.append({"code": "bill_received", "owner": "finance", "amount": s["unbilled_received"],
                    "label": "Barang diterima belum ditagih — buat Tagihan Supplier sebesar nilai terima."})
    if s["over_billed"] > EPS:
        out.append({"code": "supplier_credit_note", "owner": "finance", "amount": s["over_billed"],
                    "label": "Tagihan melebihi nilai terima — minta nota kredit supplier / potongan kontrabon."})
    if s["over_paid"] > EPS:
        out.append({"code": "overpayment", "owner": "finance", "amount": s["over_paid"],
                    "label": "Pembayaran melebihi nilai terima — minta refund atau catat sebagai uang muka supplier."})
    return out


async def record_on_close(po: Dict[str, Any], actor_name: str) -> Dict[str, Any]:
    """Simpan rekonsiliasi sekali saat tutup-kurang (idempoten) + notifikasi Finance bila ada tindak lanjut."""
    s = await build(po)
    s.update({"computed_at": now_iso(), "computed_by": actor_name})
    res = await db.purchase_orders.update_one({"id": po["id"], "close_settlement": {"$exists": False}},
                                              {"$set": {"close_settlement": s}})
    fin = [f for f in s["follow_ups"] if f["owner"] == "finance"]
    if res.modified_count and fin:
        from services import notification_service as notif
        await notif.create_notification(
            notif_type="po_close_settlement", title="Tindak lanjut keuangan PO ditutup-kurang",
            body=f"{po.get('po_number')}: " + "; ".join(f["label"] for f in fin),
            severity="warning", link="purchasing", entity_id=po.get("entity_id"),
            recipient_role="finance", ref=po["id"], action_id=po["id"])
    return s

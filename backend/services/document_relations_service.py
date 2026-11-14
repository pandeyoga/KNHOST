"""EPIC 6 — Document Relations / Process Timeline service.

Membangun graf relasi antar-dokumen (read-only) untuk Document Hub + deep-link.
Tidak menyimpan apa pun; semua relasi diturunkan dari field penghubung yang sudah ada:

  Sales chain (anchor = sales_order):
    [SpecialOrder*] -> SalesOrder -> Shipment(order_id) -> TaxInvoice(order_id)
      -> AR Receipt(allocations.order_id) -> Retur Jual(order_id) -> Komisi (on-collection, tanpa tautan)

  Purchase chain (anchor = purchase_order):
    PurchaseRequisition(po_id) -> PurchaseOrder -> GRN(wms_tasks po_id+inbound)
      -> LandedCost(landed_cost_vouchers po_ids) -> VendorBill(vendor_bills po_id)

Tiap node membawa `link` agar frontend dapat deep-link (navigasi view in-app atau buka
dokumen/print via doc_url). Stage yang kosong tetap dikembalikan (no dead-end) dengan
`docs: []` + `empty_hint`.

PK-44 (IA-13) — `link` dibentuk `doc_refs_service.link_of` (satu peta tujuan dengan Jejak Dokumen); layar detail
pesanan/PO kini memakai linimasa ini hanya sebagai GARIS TAHAPAN di kepala panel "Dokumen Terkait" (daftar &
tautan dokumen = panel referensi tersimpan).
"""
from typing import Any, Dict, List, Optional

from db import db
from core_utils import safe_doc
from services import doc_refs_service as refs


def _link(doc_type: Optional[str] = None, doc: Optional[Dict[str, Any]] = None,
          kind: str = "view", doc_url: Optional[str] = None) -> Dict[str, Any]:
    """Tautan simpul linimasa. PK-44 (IA-13) — tujuan layar dari SATU peta (`doc_refs_service.link_of`); dulu berkas
    ini menulis `view`/`nav_id` sendiri sehingga dua peta tujuan bisa berbeda (GRN → `operations`, peta jejak →
    lain lagi). Tanpa jenis dokumen terdaftar (mis. komisi) → `kind="none"` (tidak bertaut)."""
    if not doc_type or doc_type not in refs.DOC_TYPES or doc is None:
        return {"kind": "none", "view": "", "tab": "", "focus_type": "", "focus_id": "", "number": "",
                "doc_url": doc_url}
    return {"kind": kind, **refs.link_of(doc_type, doc), "doc_url": doc_url}


def _node(
    *,
    type: str,
    id: Optional[str],
    number: Optional[str],
    title: str,
    status: Optional[str] = None,
    date: Optional[str] = None,
    amount: Optional[float] = None,
    meta: Optional[str] = None,
    link: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "type": type,
        "id": id,
        "number": number,
        "title": title,
        "status": status,
        "date": date,
        "amount": amount,
        "meta": meta,
        "link": link or _link(kind="none"),
    }


def _po_total(po: Dict[str, Any]) -> Optional[float]:
    if po.get("total_amount") is not None:
        return float(po.get("total_amount") or 0)
    total = 0.0
    for it in po.get("items", []) or []:
        qty = float(it.get("quantity", it.get("qty", 0)) or 0)
        price = float(it.get("price", it.get("unit_price", 0)) or 0)
        total += qty * price
    return round(total, 2) if total else None


# ─────────────────────────── SALES ORDER CHAIN ───────────────────────────
async def _sales_order_stages(order: Dict[str, Any]) -> List[Dict[str, Any]]:
    oid = order["id"]
    stages: List[Dict[str, Any]] = []

    # Stage 0 (opsional) — sumber Special Order bila ada link eksplisit.
    sso_id = order.get("source_special_order_id")
    if sso_id:
        sso = safe_doc(await db.special_orders.find_one({"id": sso_id}, {"_id": 0}))
        if sso:
            stages.append({
                "key": "source", "label": "Pesanan Khusus (sumber)",
                "docs": [_node(
                    type="special_order", id=sso["id"], number=sso.get("number"),
                    title=sso.get("customer_name") or sso.get("type") or "Pesanan Khusus",
                    status=sso.get("status"), date=sso.get("created_at"),
                    amount=sso.get("total_amount"),
                    link=_link("special_order", sso),
                )],
            })

    # Stage 1 — Sales Order (anchor).
    stages.append({
        "key": "order", "label": "Pesanan Penjualan",
        "docs": [_node(
            type="sales_order", id=oid, number=order.get("number"),
            title=order.get("customer_name") or "Sales Order",
            status=order.get("status"), date=order.get("created_at"),
            amount=order.get("grand_total", order.get("total_amount")),
            meta=f"Sales: {order.get('sales_name') or '—'}",
            link=_link("sales_order", order),
        )],
    })

    # Stage 2 — Pengiriman (Surat Jalan).
    shipments = await db.shipments.find({"order_id": oid}, {"_id": 0}).sort("created_at", 1).to_list(200)
    stages.append({
        "key": "shipment", "label": "Pengiriman (Surat Jalan)",
        "empty_hint": "Belum ada pengiriman.",
        "docs": [_node(
            type="shipment", id=s["id"], number=s.get("shipment_no"),
            title=f"{s.get('product_name') or s.get('sku') or 'Item'} · {s.get('warehouse_name') or ''}".strip(" ·"),
            status="parsial" if s.get("is_partial") else (s.get("status") or "shipped"),
            date=s.get("created_at"),
            meta=f"{s.get('qty')} {s.get('unit') or ''}".strip(),
            link=_link("shipment", s, kind="url", doc_url=f"/shipments/{s['id']}/surat-jalan"),
        ) for s in shipments],
    })

    # Stage 3 — Faktur Pajak.
    tax = await db.tax_invoices.find({"order_id": oid}, {"_id": 0}).sort("created_at", 1).to_list(50)
    stages.append({
        "key": "tax", "label": "Faktur Pajak",
        "empty_hint": "Belum ada Faktur Pajak (opsional).",
        "docs": [_node(
            type="tax_invoice", id=t["id"], number=t.get("number"),
            title=t.get("nsfp") and f"NSFP {t.get('nsfp')}" or "Faktur Pajak",
            status=t.get("status"), date=t.get("created_at"),
            amount=t.get("ppn_amount"),
            link=_link("tax_invoice", t, doc_url=f"/tax-invoices/{t['id']}/document"),
        ) for t in tax],
    })

    # Stage 4 — Pembayaran (AR Receipt) yang dialokasikan ke order ini.
    receipts = await db.ar_receipts.find({"allocations.order_id": oid}, {"_id": 0}).sort("receipt_date", 1).to_list(100)
    rec_docs = []
    for r in receipts:
        applied = 0.0
        for a in r.get("allocations", []) or []:
            if a.get("order_id") == oid:
                applied += float(a.get("applied", 0) or 0)
        rec_docs.append(_node(
            type="ar_receipt", id=r["id"], number=r.get("number"),
            title=f"Pembayaran {r.get('method') or ''}".strip(),
            status=r.get("status"), date=r.get("receipt_date"),
            amount=round(applied, 2),
            meta=f"Total terima {r.get('amount')}",
            link=_link("ar_receipt", r),
        ))
    stages.append({
        "key": "payment", "label": "Pembayaran (Kwitansi)",
        "empty_hint": "Belum ada pembayaran tercatat.",
        "docs": rec_docs,
    })

    # Stage 4b — PK-44 (IA-13) — Retur Jual atas pesanan ini (tautannya dari peta yang sama dengan Jejak Dokumen).
    rets = await db.sales_returns.find({"order_id": oid}, {"_id": 0}).sort("created_at", 1).to_list(100)
    stages.append({
        "key": "return", "label": "Retur Jual",
        "empty_hint": "Belum ada retur.",
        "docs": [_node(
            type="sales_return", id=x["id"], number=x.get("number"),
            title=x.get("customer_name") or "Retur Jual",
            status=x.get("status"), date=x.get("created_at"),
            amount=x.get("total_amount") or x.get("grand_total"),
            link=_link("sales_return", x),
        ) for x in rets],
    })

    # Stage 5 — Komisi (navigational; on-collection per EPIC4 = level sales×periode).
    paid = order.get("payment_status") in ("partial", "paid")
    stages.append({
        "key": "commission", "label": "Komisi Sales",
        "empty_hint": "Komisi diakui saat tertagih (on-collection).",
        "docs": ([_node(
            type="commission", id=None, number=None,
            title=f"Komisi on-collection · {order.get('sales_name') or 'Sales'}",
            status=order.get("payment_status"),
            meta="Lihat rincian komisi per-SKU (Performa Saya / Sales Force)",
            link=_link(),   # PK-44 — komisi bukan dokumen di peta: tidak bertaut
        )] if paid else []),
    })

    return stages


# ─────────────────────────── PURCHASE ORDER CHAIN ───────────────────────────
async def _purchase_order_stages(po: Dict[str, Any]) -> List[Dict[str, Any]]:
    poid = po["id"]
    stages: List[Dict[str, Any]] = []

    # Stage 0 — Purchase Requisition (sumber) via pr.po_id.
    pr = safe_doc(await db.purchase_requisitions.find_one({"po_id": poid}, {"_id": 0}))
    stages.append({
        "key": "requisition", "label": "Permintaan Pembelian (sumber)",
        "empty_hint": "PO ini tidak berasal dari PR.",
        "docs": ([_node(
            type="purchase_requisition", id=pr["id"], number=pr.get("number"),
            title=pr.get("warehouse_name") or pr.get("reason") or "Requisition",
            status=pr.get("status"), date=pr.get("created_at"),
            amount=pr.get("total_est_amount"),
            link=_link("purchase_requisition", pr),
        )] if pr else []),
    })

    # Stage 1 — Purchase Order (anchor).
    stages.append({
        "key": "po", "label": "Pesanan Pembelian",
        "docs": [_node(
            type="purchase_order", id=poid, number=po.get("po_number"),
            title=po.get("supplier_name") or "Purchase Order",
            status=po.get("status"), date=po.get("created_at"),
            amount=_po_total(po),
            link=_link("purchase_order", po),
        )],
    })

    # Stage 2 — Penerimaan Barang (GRN) via wms_tasks inbound.
    tasks = await db.wms_tasks.find(
        {"po_id": poid, "flow_type": "inbound"}, {"_id": 0}
    ).sort("created_at", 1).to_list(200)
    stages.append({
        "key": "grn", "label": "Penerimaan Barang (GRN)",
        "empty_hint": "Belum ada penerimaan barang.",
        "docs": [_node(
            type="grn", id=tk["id"], number=(tk.get("id") or "")[:14],
            title=f"{tk.get('product_name') or tk.get('sku') or 'Item'} · {tk.get('warehouse_name') or ''}".strip(" ·"),
            status=tk.get("status"), date=tk.get("completed_at") or tk.get("created_at"),
            meta=f"Diterima {tk.get('received_qty', 0)}/{tk.get('expected_qty', tk.get('quantity', 0))} {tk.get('unit') or ''}".strip(),
            link=_link("grn", tk),
        ) for tk in tasks],
    })

    # Stage 3 — Landed Cost (voucher po_ids).
    vouchers = await db.landed_cost_vouchers.find({"po_ids": poid}, {"_id": 0}).sort("created_at", 1).to_list(100)
    stages.append({
        "key": "landed_cost", "label": "Biaya Masuk (Landed Cost)",
        "empty_hint": "Belum ada biaya masuk.",
        "docs": [_node(
            type="landed_cost", id=v["id"], number=v.get("number") or v.get("voucher_number"),
            title=v.get("description") or "Biaya Masuk",
            status=v.get("status"), date=v.get("created_at"),
            amount=v.get("total_amount"),
            link=_link("landed_cost", v),
        ) for v in vouchers],
    })

    # Stage 4 — Tagihan Pemasok (po_id).
    bills = await db.vendor_bills.find({"po_id": poid}, {"_id": 0}).sort("created_at", 1).to_list(100)
    stages.append({
        "key": "bill", "label": "Tagihan Pemasok",
        "empty_hint": "Belum ada tagihan pemasok.",
        "docs": [_node(
            type="vendor_bill", id=b["id"], number=b.get("number") or b.get("bill_number"),
            title=b.get("supplier_name") or "Tagihan Pemasok",
            status=b.get("status") or b.get("payment_status"), date=b.get("created_at"),
            amount=b.get("total_amount") or b.get("amount"),
            link=_link("vendor_bill", b),
        ) for b in bills],
    })

    return stages


# ─────────────────────────── PUBLIC ───────────────────────────
SUPPORTED = {"sales_order": "sales_orders", "purchase_order": "purchase_orders"}


async def build_relations(doc_type: str, doc_id: str) -> Optional[Dict[str, Any]]:
    """Return {doc_type, anchor, stages[]} atau None bila dokumen tak ditemukan."""
    if doc_type == "sales_order":
        order = safe_doc(await db.sales_orders.find_one({"id": doc_id}, {"_id": 0}))
        if not order:
            return None
        stages = await _sales_order_stages(order)
        anchor = {"type": "sales_order", "id": order["id"], "number": order.get("number"),
                  "title": order.get("customer_name"), "status": order.get("status")}
        return {"doc_type": doc_type, "anchor": anchor, "stages": stages}

    if doc_type == "purchase_order":
        po = safe_doc(await db.purchase_orders.find_one({"id": doc_id}, {"_id": 0}))
        if not po:
            return None
        stages = await _purchase_order_stages(po)
        anchor = {"type": "purchase_order", "id": po["id"], "number": po.get("po_number"),
                  "title": po.get("supplier_name"), "status": po.get("status")}
        return {"doc_type": doc_type, "anchor": anchor, "stages": stages}

    return None

"""Vendor Bill service (Fase 5.2 — P0-2) — 3-Way Matching PO ↔ GR ↔ Bill.

Koleksi kanonik: `vendor_bills` (prefix vbill_). Nomor dokumen: VB-NNNNN.

Prinsip:
- AP (hutang) berbasis Vendor Bill yang sudah *posted*. PO tetap menyimpan
  ringkasan billed/unbilled (informasional) tanpa mengubah invarian PO lama.
- 3-way matching: PO (ordered) ↔ GR (received_qty per item) ↔ Bill (billed_qty),
  dengan toleransi qty & harga yang configurable di settings.purchasing.
- INVARIAN-SAFE: item.subtotal = price × billed_qty (GROSS); total_amount = Σ subtotal.
  Diskon & PPN disimpan di field terpisah (mengikuti pola PO P0-1).
"""
from typing import Any, Dict, List, Optional
from db import db
from core_utils import now_iso

# Status bill yang dipakai dedupe nomor invoice supplier (semua yang belum batal).
ACTIVE_BILL_STATUSES = {"draft", "pending_approval", "posted", "paid"}
# Status bill yang "menahan"/me-reserve qty tagih (cegah over-billing lintas bill).
# DRAFT TIDAK me-reserve (work-in-progress) agar draft terbengkalai tak memblokir
# penagihan sah; integritas dijaga via re-evaluasi match saat submit.
BILLED_RESERVE_STATUSES = {"pending_approval", "posted", "paid"}
# Status bill yang menimbulkan hutang (AP) — sudah resmi diakui.
AP_BILL_STATUSES = {"posted", "paid"}
TERMINAL_BILL_STATUSES = {"cancelled", "paid"}


def po_line_id(it: Dict[str, Any], idx: int) -> str:
    """FN-02 — identitas BARIS PO. `line_code` di item PO adalah LINI produk (printing/woven),
    bukan id baris, jadi tidak boleh dipakai sebagai kunci 3-way match."""
    return it.get("line_id") or f"L{idx + 1}"


def po_line_index(po: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {po_line_id(it, i): it for i, it in enumerate(po.get("items", []))}


def line_key(po: Dict[str, Any], item: Dict[str, Any]) -> str:
    """FN-02 — kunci baris PO untuk 3-way match: `po_line_id` eksplisit, else baris tunggal produk itu.
    Tagihan iterasi 2026-10-04 menyimpan `po_line_code` (= lini) → dipakai hanya bila unik per produk."""
    if item.get("po_line_id"):
        return item["po_line_id"]
    pid = item.get("product_id")
    cands = [(i, it) for i, it in enumerate(po.get("items", [])) if it.get("product_id") == pid]
    code = item.get("po_line_code")
    if code and len(cands) > 1:
        narrowed = [c for c in cands if c[1].get("line_code") == code]
        if len(narrowed) == 1:
            cands = narrowed
    if len(cands) == 1:
        return po_line_id(cands[0][1], cands[0][0])
    return pid


async def ensure_line_ids(po: Dict[str, Any]) -> Dict[str, Any]:
    """Simpan `line_id` permanen di item PO (sekali) agar kunci baris tidak bergeser bila urutan berubah."""
    items = po.get("items", [])
    if all(it.get("line_id") for it in items):
        return po
    used = {it["line_id"] for it in items if it.get("line_id")}
    upd: Dict[str, str] = {}
    for i, it in enumerate(items):
        if it.get("line_id"):
            continue
        n = i + 1
        while f"L{n}" in used:
            n += 1
        it["line_id"] = f"L{n}"
        used.add(it["line_id"])
        upd[f"items.{i}.line_id"] = it["line_id"]
    await db.purchase_orders.update_one({"id": po["id"]}, {"$set": upd})
    return po


async def already_billed_map(po_id: str, exclude_bill_id: Optional[str] = None) -> Dict[str, float]:
    """Σ billed_qty per product_id dari bill yang me-RESERVE qty (pending/posted/paid)
    pada satu PO. Dipakai untuk mencegah over-billing lintas beberapa tagihan."""
    q: Dict[str, Any] = {"po_id": po_id, "status": {"$in": list(BILLED_RESERVE_STATUSES)}}
    if exclude_bill_id:
        q["id"] = {"$ne": exclude_bill_id}
    out: Dict[str, float] = {}
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0, "items": 1}) or {}
    async for b in db.vendor_bills.find(q, {"_id": 0, "items": 1}):
        for it in b.get("items", []):
            k = line_key(po, it)  # FN-02 — per baris PO
            out[k] = out.get(k, 0.0) + float(it.get("billed_qty", 0) or 0)
    return {k: round(v, 4) for k, v in out.items()}


def _variance_pct(actual: float, base: float) -> float:
    if base <= 0:
        return 0.0
    return round((actual - base) / base * 100.0, 2)


def evaluate_match(
    po: Dict[str, Any],
    priced_items: List[Dict[str, Any]],
    match_mode: str,
    billed_so_far: Dict[str, float],
    qty_tol: float,
    price_tol: float,
    value_tol: float = 0.0,
) -> Dict[str, Any]:
    """Hitung 3-way match per item + agregat. PURE (tak menyentuh DB).

    `priced_items` = hasil compute_order_pricing (punya `quantity`==billed_qty,
    `price`, `subtotal`, dll) + field `billed_qty`. Mengembalikan dict:
      { items: [...enriched dgn `match`], match_status, exceptions, within_tolerance }

    Aturan:
      - base_qty = received_qty (mode 'received', 3-way ketat) atau ordered (mode 'ordered').
      - remaining = base_qty − already_billed. billed > remaining + tol → OVER_BILLED (blocked).
      - |price − po_price| / po_price > price_tol → PRICE_VARIANCE (warning, butuh approval).
    """
    po_items = po_line_index(po)
    enriched: List[Dict[str, Any]] = []
    exceptions: List[Dict[str, Any]] = []
    blocked = False
    warning = False
    in_bill: Dict[str, float] = {}  # FN-02 — baris sebelumnya pada tagihan INI ikut mengurangi sisa
    for bi in priced_items:
        pid = bi.get("product_id")
        lk = line_key(po, bi)  # FN-02 — cocokkan per BARIS PO, bukan per produk
        po_it = po_items.get(lk) or next((it for it in po.get("items", []) if it.get("product_id") == pid), {})
        ordered = float(po_it.get("quantity", 0) or 0)
        received = float(po_it.get("received_qty", 0) or 0)
        prior = float(billed_so_far.get(lk, 0) or 0) + in_bill.get(lk, 0.0)
        in_bill[lk] = in_bill.get(lk, 0.0) + float(bi.get("billed_qty", bi.get("quantity", 0)) or 0)
        billed = float(bi.get("billed_qty", bi.get("quantity", 0)) or 0)
        po_price = float(po_it.get("price", 0) or 0)
        price = float(bi.get("price", po_price) or 0)
        base_qty = received if match_mode == "received" else ordered
        remaining = round(base_qty - prior, 4)

        messages: List[str] = []
        # ── qty match ──
        qty_status = "ok"
        tol_qty = abs(remaining) * (qty_tol / 100.0)
        # KN-D16 — ambang RUPIAH bersama (kontrabon): selisih kecil bernilai ≤ value_tol bukan pengecualian.
        over_value = max(0.0, billed - remaining) * price
        if billed > remaining + tol_qty + 1e-6 and over_value > value_tol + 0.01:
            qty_status = "over_billed"
            blocked = True
            msg = (f"Tagih {billed:g} melebihi sisa yang boleh ditagih {remaining:g} "
                   f"({'diterima' if match_mode == 'received' else 'dipesan'}) + toleransi {qty_tol:g}%")
            messages.append(msg)
            exceptions.append({"product_id": pid, "sku": po_it.get("sku", ""),
                               "product_name": po_it.get("product_name", ""),
                               "type": "qty_over_billed", "detail": msg})
        elif billed > remaining + 1e-6:
            qty_status = "within_tolerance"
            warning = True
            msg = f"Tagih {billed:g} sedikit di atas sisa {remaining:g} namun dalam toleransi {qty_tol:g}%"
            messages.append(msg)
            exceptions.append({"product_id": pid, "sku": po_it.get("sku", ""),
                               "product_name": po_it.get("product_name", ""),
                               "type": "qty_within_tolerance", "detail": msg})

        # ── price match ──
        price_status = "ok"
        pvar = _variance_pct(price, po_price)
        if po_price > 0 and abs(pvar) > price_tol + 1e-6 and abs(price - po_price) * billed > value_tol + 0.01:
            price_status = "price_variance"
            warning = True
            msg = f"Harga {price:g} menyimpang {pvar:+g}% dari harga PO {po_price:g} (toleransi ±{price_tol:g}%)"
            messages.append(msg)
            exceptions.append({"product_id": pid, "sku": po_it.get("sku", ""),
                               "product_name": po_it.get("product_name", ""),
                               "type": "price_variance", "detail": msg})

        item = dict(bi)
        item.update({
            "sku": bi.get("sku") or po_it.get("sku", ""),
            "product_name": bi.get("product_name") or po_it.get("product_name", ""),
            "ordered_qty": ordered,
            "received_qty": received,
            "already_billed_qty": prior,
            "remaining_qty": remaining,
            "po_price": po_price,
            "match": {
                "qty_status": qty_status,
                "price_status": price_status,
                "qty_remaining": remaining,
                "price_variance_pct": pvar,
                "messages": messages,
            },
        })
        enriched.append(item)

    match_status = "blocked" if blocked else ("warning" if warning else "matched")
    return {
        "items": enriched,
        "match_status": match_status,
        "exceptions": exceptions,
        "within_tolerance": not blocked,
    }


def bill_financials(bill: Dict[str, Any]) -> Dict[str, Any]:
    """Hitung AP per bill: grand_total (incl PPN) − amount_paid = outstanding."""
    grand = float(bill.get("grand_total", 0) or 0)
    if grand <= 0:
        grand = float(bill.get("total_amount", 0) or 0)
    paid = float(bill.get("amount_paid", 0) or 0)
    outstanding = round(max(grand - paid, 0.0), 2)
    if paid <= 0.01:
        pay_status = "unpaid"
    elif outstanding <= 0.01:
        pay_status = "paid"
    else:
        pay_status = "partial"
    return {
        "grand_total": round(grand, 2),
        "amount_paid": round(paid, 2),
        "outstanding": outstanding,
        "payment_status": pay_status,
    }


async def next_bill_number() -> str:
    """KN-A12 — sequence ATOMIK bersama (find_one_and_update $inc), bukan 'nomor tertinggi + 1'."""
    from core_utils import next_doc_number
    return await next_doc_number("vendor_bills", "bill_number", "VB-", width=5, scheme="shared")


async def sync_po_billing(po_id: str) -> Dict[str, Any]:
    """Hitung ulang ringkasan billed PO dari bill yang sudah AP (posted/paid).
    Tidak mengubah invarian PO; hanya menambah field ringkasan informasional."""
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0})
    if not po:
        return {}
    billed_total = 0.0
    bill_count = 0
    billed_qty: Dict[str, float] = {}
    async for b in db.vendor_bills.find(
        {"po_id": po_id, "status": {"$in": list(AP_BILL_STATUSES)}}, {"_id": 0}
    ):
        billed_total += float(b.get("grand_total", 0) or 0)
        bill_count += 1
        for it in b.get("items", []):
            pid = it.get("product_id")
            billed_qty[pid] = billed_qty.get(pid, 0.0) + float(it.get("billed_qty", 0) or 0)
    grand = float(po.get("grand_total", 0) or po.get("total_amount", 0) or 0)
    summary = {
        "billed_total": round(billed_total, 2),
        "bill_count": bill_count,
        "unbilled_total": round(max(grand - billed_total, 0.0), 2),
    }
    await db.purchase_orders.update_one(
        {"id": po_id},
        {"$set": {**summary, "billed_qty_map": billed_qty, "updated_at": now_iso()}},
    )
    return summary


async def build_billing_context(po: Dict[str, Any]) -> Dict[str, Any]:
    """Susun konteks penagihan PO untuk pre-fill form Vendor Bill (per item:
    ordered / received / already_billed / billable)."""
    po = await ensure_line_ids(po)
    billed = await already_billed_map(po["id"])
    po_items = po.get("items", [])
    items = []
    for idx, it in enumerate(po_items):
        pid = it.get("product_id")
        ordered = float(it.get("quantity", 0) or 0)
        received = float(it.get("received_qty", 0) or 0)
        # FN-02 — sudah-ditagih dibaca per BARIS PO (kunci sama dengan already_billed_map)
        lid = po_line_id(it, idx)
        prior = float(billed.get(lid, 0) or 0)
        items.append({
            "po_line_id": lid,
            "line_code": it.get("line_code") or "",
            "line_no": idx + 1,
            "same_product_lines": sum(1 for x in po_items if x.get("product_id") == pid),
            "product_id": pid,
            "sku": it.get("sku", ""),
            "product_name": it.get("product_name", ""),
            "unit": it.get("unit", "meter"),
            "ordered_qty": ordered,
            "received_qty": received,
            "already_billed_qty": round(prior, 4),
            "billable_received": round(max(received - prior, 0.0), 4),
            "billable_ordered": round(max(ordered - prior, 0.0), 4),
            "po_price": float(it.get("price", 0) or 0),
            "discount_percent": float(it.get("discount_percent", 0) or 0),
        })
    return {
        "po_id": po["id"],
        "po_number": po.get("po_number", ""),
        "supplier_id": po.get("supplier_id", ""),
        "supplier_name": po.get("supplier_name", ""),
        "supplier_npwp": po.get("supplier_npwp", ""),
        "warehouse_id": po.get("warehouse_id", ""),
        "warehouse_name": po.get("warehouse_name", ""),
        "entity_id": po.get("entity_id", ""),
        "po_status": po.get("status", ""),
        "tax_mode": po.get("tax_mode", ""),
        "ppn_rate": float(po.get("ppn_rate", 0) or 0),
        # FASE SL — catatan selisih penerimaan (gudang) dibaca finance sebelum menagih.
        "receipt_variances": po.get("receipt_variances") or [],
        "items": items,
    }

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
import re
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
    returned_unbilled: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Hitung 3-way match per item + agregat. PURE (tak menyentuh DB).

    `priced_items` = hasil compute_order_pricing (punya `quantity`==billed_qty,
    `price`, `subtotal`, dll) + field `billed_qty`. Mengembalikan dict:
      { items: [...enriched dgn `match`], match_status, exceptions, within_tolerance }

    Aturan:
      - base_qty = received_qty (mode 'received', 3-way ketat) atau ordered (mode 'ordered'), dikurangi qty yang
        diretur sebelum ditagih (`returned_unbilled`, per baris PO — PK-28; dasar retur GR/IR) di kedua mode.
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
        # R0 (integrasi FIX-6, 15 Nov) — qty retur "potong tagihan" dikurangi SATU kali lewat `returned_unbilled` (PK-28,
        # retur ber-dasar GR/IR); `returned_qty` baris PO (FIX-6) hanya keterangan, tidak dikurangi lagi di sini.
        received = float(po_it.get("received_qty", 0) or 0)
        prior = float(billed_so_far.get(lk, 0) or 0) + in_bill.get(lk, 0.0)
        in_bill[lk] = in_bill.get(lk, 0.0) + float(bi.get("billed_qty", bi.get("quantity", 0)) or 0)
        billed = float(bi.get("billed_qty", bi.get("quantity", 0)) or 0)
        po_price = float(po_it.get("price", 0) or 0)
        price = float(bi.get("price", po_price) or 0)
        returned = float((returned_unbilled or {}).get(lk, 0) or 0)
        base_qty = (received if match_mode == "received" else ordered) - returned
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
            "returned_unbilled_qty": round(returned, 4),
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
    """Hitung AP per bill: grand_total (incl PPN) − amount_paid − ap_variance_closed = outstanding.

    PK-19 (FX-07) — sisa yang DITUTUP keputusan selisih bayar ("Tutup sisa hutang", `ap_variance_closed`, berjurnal
    Dr 2-1100 / Cr 4-9000) bukan hutang lagi; dibatalkan → kembali jadi sisa (field dikosongkan)."""
    grand = float(bill.get("grand_total", 0) or 0)
    if grand <= 0:
        grand = float(bill.get("total_amount", 0) or 0)
    paid = float(bill.get("amount_paid", 0) or 0)
    closed = float(bill.get("ap_variance_closed", 0) or 0)
    outstanding = round(max(grand - paid - closed, 0.0), 2)
    if paid <= 0.01 and closed <= 0.01:
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


#: Status tagihan yang berhutang (dibaca ringkasan hutang dan kartu pemasok).
PAYABLE_BILL_STATUSES = ("posted", "paid")


async def open_payables(scope_q: Dict[str, Any]) -> List[Dict[str, Any]]:
    """PK-41 + MN-T3 (D1) — SATU pembaca tagihan berhutang yang masih bersisa, dipakai ringkasan Hutang › Tagihan
    (`GET /vendor-bills/payables/summary`) dan kartu pemasok (`GET /suppliers/{id}/360` › `payables`).

    `scope_q` = saringan PT/pemasok dari pemanggil (sudah lewat `resolve_list_scope`). Tiap butir: `bill`, `fin`
    (`bill_financials`), `due` (jatuh tempo `YYYY-MM-DD` atau None), `basis`, `days` (hari lewat jatuh tempo, WIB)."""
    from services import report_basis as rb
    q: Dict[str, Any] = {"status": {"$in": sorted(PAYABLE_BILL_STATUSES)}, "payment_status": {"$ne": "paid"},
                         **(scope_q or {})}
    today = rb.tanggal_buku()
    term_cache: Dict[str, int] = {}
    out: List[Dict[str, Any]] = []
    async for b in db.vendor_bills.find(q, {"_id": 0}):
        fin = bill_financials(b)
        if fin["outstanding"] <= 0.01:
            continue
        due, basis = await rb.jatuh_tempo_tagihan(b, term_cache)
        out.append({"bill": b, "fin": fin, "due": due, "basis": basis,
                    "days": rb.hari_antara(due, today) if due else 0})
    return out


async def next_bill_number(entity_id: Optional[str] = None) -> str:
    """KN-A12 — sequence ATOMIK bersama (find_one_and_update $inc), bukan 'nomor tertinggi + 1'.
    KP-T5 — `entity_id` = PT dokumennya (N1): bawaan tetap deret bersama; berlaku bila grup memilih per PT."""
    from core_utils import next_doc_number
    return await next_doc_number("vendor_bills", "bill_number", "VB-", width=5,
                                 entity_id=entity_id or None, scheme="shared", kind="vb")


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
    if po.get("status") == "closed_short":   # L02 LN-023-T02 — sisa yang dibatalkan tidak akan ditagih
        ordered = sum(float(i.get("quantity") or 0) * float(i.get("price") or 0) for i in po.get("items") or [])
        received = sum(float(i.get("received_qty") or 0) * float(i.get("price") or 0) for i in po.get("items") or [])
        grand = round(received * grand / ordered, 2) if ordered > 0 else grand
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
    returned = await returned_unbilled_map(po["id"])   # PK-28 — retur sebelum ditagih tidak boleh ditagih lagi
    po_items = po.get("items", [])
    items = []
    for idx, it in enumerate(po_items):
        pid = it.get("product_id")
        ordered = float(it.get("quantity", 0) or 0)
        # R0 — retur sebelum ditagih dikurangi sekali lewat `returned_unbilled_map` (PK-28), bukan `returned_qty` FIX-6.
        received = float(it.get("received_qty", 0) or 0)
        # FN-02 — sudah-ditagih dibaca per BARIS PO (kunci sama dengan already_billed_map)
        lid = po_line_id(it, idx)
        prior = float(billed.get(lid, 0) or 0)
        ret_q = float(returned.get(lid, 0) or 0)
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
            "returned_unbilled_qty": round(ret_q, 4),
            "billable_received": round(max(received - prior - ret_q, 0.0), 4),
            "billable_ordered": round(max(ordered - prior - ret_q, 0.0), 4),
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


# ═════════════════════════════════════════════════════════════════════════════
#  PK-28 (IV-03) — retur sebelum ditagih, nilai GR/IR faktur, sisa GR/IR per PO
# ═════════════════════════════════════════════════════════════════════════════
async def _qty_in_po_unit(po_line: Dict[str, Any], item: Dict[str, Any]) -> float:
    """Qty baris retur (satuan dasar produk) → satuan baris PO: `quantity_input` bila `unit_input` = satuan PO, qty
    apa adanya bila satuannya sama, selain itu konversi master satuan (`uom_service.convert`)."""
    from services import uom_service as _u
    po_unit = _u._norm(po_line.get("unit") or "")
    qty = float(item.get("quantity") or 0)
    if item.get("unit_input") and _u._norm(item["unit_input"]) == po_unit and item.get("quantity_input") is not None:
        return float(item["quantity_input"] or 0)
    unit = _u._norm(item.get("unit") or "")
    if not po_unit or not unit or unit == po_unit:
        return qty
    prod = await db.products.find_one({"id": item.get("product_id")}, {"_id": 0}) or {}
    return float(_u.convert(prod, qty, unit, po_unit, await _u.load_fixed_factors(), precision=4))


async def returned_unbilled_map(po_id: str) -> Dict[str, float]:
    """Σ qty per baris PO (kunci `line_key`, satuan baris PO) dari retur beli PO itu yang stoknya sudah keluar
    (`stock_adjusted`), tidak dibalik, dan berdasar GR/IR (`ap_basis == "gr_ir"` — retur SEBELUM ada faktur). Retur
    lama tanpa `ap_basis`: dianggap GR/IR bila jurnal `purchase_return`-nya mendebit akun GR/IR."""
    po = await db.purchase_orders.find_one({"id": po_id}, {"_id": 0, "items": 1}) or {}
    rets = [r async for r in db.purchase_returns.find(
        {"po_id": po_id, "stock_adjusted": True, "reversed": {"$ne": True}, "status": {"$ne": "cancelled"}},
        {"_id": 0, "id": 1, "ap_basis": 1, "items": 1, "remedy": 1})]
    # R0 (FIX-6 D2) — "ganti barang" tidak mengurangi qty tertagih: `received_qty` PO sudah diturunkan saat retur dan naik
    # lagi oleh penerimaan pengganti; tagihan supplier tetap untuk qty penuh.
    rets = [r for r in rets if (r.get("remedy") or {}).get("choice") != "replace"]
    lama = [r["id"] for r in rets if not r.get("ap_basis")]
    lama_grir: set = set()
    if lama:
        from services.gl_mapping_service import known_codes
        codes = [c for c in await known_codes("pembelian.gr_ir") if c]
        async for je in db.journal_entries.find(
                {"source_type": "purchase_return", "source_id": {"$in": lama}, "status": {"$ne": "void"},
                 "lines": {"$elemMatch": {"account_code": {"$in": codes}, "debit": {"$gt": 0}}}},
                {"_id": 0, "source_id": 1}):
            lama_grir.add(je["source_id"])
    lines = po_line_index(po)
    out: Dict[str, float] = {}
    for r in rets:
        if (r.get("ap_basis") or ("gr_ir" if r["id"] in lama_grir else "")) != "gr_ir":
            continue
        for it in r.get("items") or []:
            k = line_key(po, it)
            out[k] = out.get(k, 0.0) + await _qty_in_po_unit(lines.get(k) or {}, it)
    return {k: round(v, 4) for k, v in out.items()}


async def grir_fields(bill: Dict[str, Any]) -> Dict[str, Any]:
    """`grir_amount` (Σ `billed_qty` × harga neto baris PO), `price_variance_amount` (neto faktur − `grir_amount`) dan
    `price_variance_posted` awal untuk faktur ber-PO; ditulis SEKALI pada tulisan `posted` (`routers/vendor_bills._post_bill`).
    Faktur kampanye, jasa makloon, dan tanpa PO → `{}` (jurnalnya tidak berubah)."""
    if not bill.get("po_id") or bill.get("bill_type") in ("campaign_expense", "makloon_service"):
        return {}
    po = await db.purchase_orders.find_one({"id": bill["po_id"]}, {"_id": 0, "items": 1, "order_discount_percent": 1})
    if not po:
        return {}
    from services.po_pricing import po_line_net_unit_price
    grir = round(sum(float(it.get("billed_qty", it.get("quantity", 0)) or 0)
                     * po_line_net_unit_price(po, product_id=it.get("product_id") or "",
                                              line_id=it.get("po_line_id") or "")
                     for it in bill.get("items") or []), 2)
    grand = round(float(bill.get("grand_total", bill.get("total_amount", 0)) or 0), 2)
    neto = round(grand - round(float(bill.get("ppn_amount", 0) or 0), 2), 2)
    variance = round(neto - grir, 2)
    return {"grir_amount": grir, "price_variance_amount": variance, "price_variance_posted": abs(variance) <= 0.005}


# ── Sisa GR/IR per PO ────────────────────────────────────────────────────────
#: Jenis jurnal yang menyentuh GR/IR → (koleksi dokumen sumber, kategori nilai). Jurnal lama tanpa `ref.po_id`
#: dihubungkan ke PO lewat dokumen sumbernya; sumber berakhiran `_reversal` mengikuti dokumen asalnya.
GRIR_SOURCES: Dict[str, tuple] = {
    "goods_receipt": ("wms_tasks", "received"),
    "vendor_bill": ("vendor_bills", "billed"),
    "purchase_return": ("purchase_returns", "returned"),
    "grir_clearing": ("", "cleared"),
}
_REV = "_reversal"


def grir_base_source(source_type: str) -> str:
    st = source_type or ""
    return st[:-len(_REV)] if st.endswith(_REV) else st


async def _grir_groups(entity_id: str, codes: List[str], po_id: str = "") -> List[Dict[str, Any]]:
    """Satu agregasi: baris jurnal GR/IR PT itu per (source_type, source_id, ref.po_id). Tanpa batas `to_list`
    (`02` D4) — kursor dibaca habis. `po_id` → hanya jurnal yang ber-`ref.po_id` itu atau bersumber dokumen PO itu."""
    match: Dict[str, Any] = {"entity_id": entity_id, "status": {"$ne": "void"}, "lines.account_code": {"$in": codes}}
    if po_id:
        src_ids = [po_id]
        for coll in ("wms_tasks", "vendor_bills", "purchase_returns"):
            src_ids += [d["id"] async for d in db[coll].find({"po_id": po_id}, {"_id": 0, "id": 1})]
        match["$or"] = [{"ref.po_id": po_id}, {"source_id": {"$in": src_ids}},
                        {"source_id": {"$regex": f"^{re.escape(po_id)}:"}}]
    pipeline = [
        {"$match": match},
        {"$unwind": "$lines"},
        {"$match": {"lines.account_code": {"$in": codes}}},
        {"$group": {"_id": {"st": "$source_type", "sid": "$source_id", "po": "$ref.po_id"},
                    "debit": {"$sum": "$lines.debit"}, "credit": {"$sum": "$lines.credit"},
                    "last_date": {"$max": "$date"}}},
    ]
    return [g async for g in db.journal_entries.aggregate(pipeline)]


async def _legacy_po_links(groups: List[Dict[str, Any]]) -> Dict[tuple, str]:
    """(source_type dasar, source_id) → po_id untuk kelompok tanpa `ref.po_id` (jurnal lama)."""
    want: Dict[str, set] = {}
    for g in groups:
        k = g["_id"] or {}
        if k.get("po"):
            continue
        base = grir_base_source(k.get("st") or "")
        coll = (GRIR_SOURCES.get(base) or ("", ""))[0]
        if coll and k.get("sid"):
            want.setdefault(coll, set()).add(k["sid"])
    out: Dict[tuple, str] = {}
    for coll, ids in want.items():
        base = next(b for b, v in GRIR_SOURCES.items() if v[0] == coll)
        async for d in db[coll].find({"id": {"$in": sorted(ids)}}, {"_id": 0, "id": 1, "po_id": 1}):
            if d.get("po_id"):
                out[(base, d["id"])] = d["po_id"]
    return out


async def grir_by_po(entity_id: str, po_id: str = "") -> Dict[str, dict]:
    """Sisa akun GR/IR (`pembelian.gr_ir`, semua kode yang pernah dipakai) PT `entity_id` per PO.

    → `{po_id: {received_value, billed_value, returned_value, cleared_value, other_value, balance, last_receipt_at,
    last_activity_at}}`; `balance` = kredit − debit (positif = barang diterima belum ditagih). Kunci `""` = baris yang
    tidak bisa dihubungkan ke PO (jurnal manual, potongan kontrabon, jurnal lama yang dokumen sumbernya hilang).
    `po_id` diisi → hanya PO itu (dipakai rekonsiliasi tutup-kurang)."""
    from services.gl_mapping_service import known_codes
    codes = [c for c in await known_codes("pembelian.gr_ir") if c]
    groups = await _grir_groups(entity_id, codes, po_id)
    legacy = await _legacy_po_links(groups)
    out: Dict[str, dict] = {}
    for g in groups:
        k = g["_id"] or {}
        st, sid = k.get("st") or "", k.get("sid") or ""
        base = grir_base_source(st)
        pid = k.get("po") or legacy.get((base, sid)) or ""
        if not pid and base == "grir_clearing" and ":" in sid:
            pid = sid.rsplit(":", 1)[0]
        if po_id and pid != po_id:
            continue
        row = out.setdefault(pid, {"received_value": 0.0, "billed_value": 0.0, "returned_value": 0.0,
                                   "cleared_value": 0.0, "other_value": 0.0, "balance": 0.0,
                                   "last_receipt_at": "", "last_activity_at": ""})
        d, c = float(g.get("debit") or 0), float(g.get("credit") or 0)
        cat = (GRIR_SOURCES.get(base) or ("", "other"))[1]
        if cat == "received":
            row["received_value"] += c - d
            if st == "goods_receipt":
                row["last_receipt_at"] = max(row["last_receipt_at"], str(g.get("last_date") or ""))
        else:
            row[f"{cat}_value"] += d - c if cat != "other" else c - d
        row["balance"] += c - d
        row["last_activity_at"] = max(row["last_activity_at"], str(g.get("last_date") or ""))
    for row in out.values():
        for f in ("received_value", "billed_value", "returned_value", "cleared_value", "other_value", "balance"):
            row[f] = round(row[f], 2)
    return out


async def grir_ledger_balance(entity_id: str) -> float:
    """Saldo kredit akun GR/IR PT itu di buku besar (kredit − debit, semua jurnal tidak-void) — dihitung TERPISAH dari
    pengelompokan per PO supaya `Σ sisa per PO + tak terhubung = saldo buku besar` benar-benar diperiksa."""
    from services.gl_mapping_service import known_codes
    codes = [c for c in await known_codes("pembelian.gr_ir") if c]
    pipeline = [
        {"$match": {"entity_id": entity_id, "status": {"$ne": "void"}, "lines.account_code": {"$in": codes}}},
        {"$unwind": "$lines"},
        {"$match": {"lines.account_code": {"$in": codes}}},
        {"$group": {"_id": None, "debit": {"$sum": "$lines.debit"}, "credit": {"$sum": "$lines.credit"}}},
    ]
    res = [g async for g in db.journal_entries.aggregate(pipeline)]
    return round(float(res[0]["credit"] or 0) - float(res[0]["debit"] or 0), 2) if res else 0.0

"""Vendor Bills router (Fase 5.2 — P0-2): Vendor Bill + 3-Way Matching.

Koleksi kanonik: `vendor_bills` (prefix vbill_). AP berbasis bill *posted*.
Lifecycle: draft → pending_approval → posted → paid (+ cancelled).
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from db import db
from dependencies import require_permission, current_user, audit
from core_utils import new_id, now_iso, safe_doc, DEFAULT_ENTITY_ID, timeline_entry, next_doc_number, rupiah, \
    to_cents, from_cents
from entity_scope import entity_ctx, resolve_list_scope, assert_entity_access, guard_doc
from pagination import is_paged, get_page_params, build_search, merge_query, fetch_page, envelope
from schemas import VendorBillCreate, VendorBillPaymentCreate, VendorBillDecision
from services.config_service import compute_order_pricing, get_effective_settings
from services import gl_service
from services.vendor_bill_service import (
    evaluate_match, bill_financials, next_bill_number, sync_po_billing,
    already_billed_map, build_billing_context, ACTIVE_BILL_STATUSES, ensure_line_ids, po_line_id,
    returned_unbilled_map, grir_fields, AP_AGING_KEYS, AP_AGING_LABELS, ap_aging_bucket,
)
from request_context import active_entity_or

router = APIRouter(prefix="/api")

PAYABLE_BILL_STATUSES = {"posted", "paid"}


async def _tolerances(entity_id: str) -> Dict[str, float]:
    """KN-D16 — ambang 3-way dari SATU sumber bersama dengan kontrabon (three_way_policy)."""
    from services.three_way_policy import tolerances as _tw
    tw = await _tw(entity_id or "")
    return {"qty": tw["qty_pct"], "price": tw["price_pct"], "value": tw["value_rp"]}


def _lebih_tagih_msg(match: Dict[str, Any], draft: bool = False) -> str:
    """S2 (pelatihan 18 Nov) — pesan lebih tagih dalam bahasa pengguna + rincian baris; draf tidak bisa diubah, jadi
    jalan keluarnya disebut (dulu "over-billing … Perbaiki qty tagihan dulu" padahal draf tidak punya tombol ubah)."""
    rinci = "; ".join(f"{e.get('sku') or e.get('product_name') or ''}: {e.get('detail', '')}".strip(": ")
                      for e in (match or {}).get("exceptions") or [] if e.get("type") == "qty_over_billed")
    jalan = ("Draf tidak bisa diubah — batalkan draf ini, lalu buat tagihan baru dengan qty sesuai penerimaan."
             if draft else "Ubah qty tagihan sesuai penerimaan, lalu kirim lagi.")
    return f"3-way match GAGAL — lebih tagih{(' (' + rinci + ')') if rinci else ''}. {jalan}"


def _hydrate(bill: Dict[str, Any]) -> Dict[str, Any]:
    bill["financials"] = bill_financials(bill)
    return bill


# ── Billing context (pre-fill form) — STATIC sebelum route /{id} ──────────────

# A2 (pelatihan 18 Nov) — label Riwayat tagihan dalam Bahasa Indonesia (dulu "match: matched").
_MATCH_LABEL = {"matched": "cocok bersih", "warning": "ada selisih (perlu persetujuan)", "blocked": "lebih tagih"}


@router.get("/purchase-orders/{po_id}/billing-context")
async def po_billing_context(po_id: str, request: Request) -> Dict[str, Any]:
    """Konteks penagihan PO untuk membuat Vendor Bill (ordered/received/billed/billable)."""
    await require_permission(request, "vendor_bill", "view")
    po = safe_doc(await db.purchase_orders.find_one({"id": po_id}, {"_id": 0}))
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order tidak ditemukan")
    await guard_doc(request, "purchase_orders", po, strict=False)   # P18 AUTH-02 IDOR
    ctx = await build_billing_context(po)
    # S2 (pelatihan 18 Nov) — ambang 3-way yang SAMA dengan server (termasuk ambang rupiah kontrabon) untuk pratinjau
    # form: dulu layar memakai % saja → selisih kecil (≤ ambang rupiah) tampil "perlu persetujuan"/"lebih tagih" padahal
    # server memposting langsung / meminta persetujuan.
    tol = await _tolerances(po.get("entity_id") or "")
    ctx["tolerances"] = {"qty_pct": tol["qty"], "price_pct": tol["price"], "value_rp": tol["value"]}
    return ctx


# ── Payables summary (AP berbasis bill) — STATIC sebelum route /{id} ──────────

@router.get("/vendor-bills/payables/summary")
async def vendor_bill_payables(request: Request, entity_id: str = None) -> Dict[str, Any]:
    """Ringkasan hutang (AP) berbasis Vendor Bill posted + aging per bill.

    PK-41 (RP-01, RP-07) — kueri menyaring status hutang DAN `payment_status` belum lunas, kursor tanpa batas (dulu 2.000
    tagihan tanpa urutan lalu yang lunas dibuang). Hari lewat = `report_basis.hari_antara(jatuh tempo, hari ini)`;
    jatuh tempo = `due_date`, atau tanggal tagihan + termin pemasok bila kosong (`due_basis: "bill_date"`). Kelompok:
    `not_due` (belum jatuh tempo), `1-30`, `31-60`, `61-90`, `>90`. `reconciliation` mencocokkan sisa tagihan + biaya
    masuk belum dibayar − nota debit belum dipotong dengan saldo akun hutang."""
    await require_permission(request, "vendor_bill", "view")
    from services.vendor_bill_service import open_payables
    ctx = await entity_ctx(request)
    q: Dict[str, Any] = {"status": {"$in": sorted(PAYABLE_BILL_STATUSES)}, "payment_status": {"$ne": "paid"}}
    q = resolve_list_scope("vendor_bills", q, ctx, entity_id)
    by_supplier: Dict[str, Dict[str, Any]] = {}
    aging_sen = {k: 0 for k in AP_AGING_KEYS}
    total_sen = 0
    rows = []
    # MN-T3 (D1) — satu pembaca tagihan berhutang terbuka bersama kartu pemasok (`vendor_bill_service.open_payables`).
    for item in await open_payables(q):
        b, fin, due, basis, days = item["bill"], item["fin"], item["due"], item["basis"], item["days"]
        out = fin["outstanding"]
        total_sen += to_cents(out)
        bucket = ap_aging_bucket(days)
        aging_sen[bucket] += to_cents(out)
        sid = b.get("supplier_id") or b.get("supplier_name") or "—"
        sup = by_supplier.setdefault(sid, {
            "supplier_id": b.get("supplier_id", ""), "supplier_name": b.get("supplier_name", "—"),
            "outstanding": 0.0, "bill_count": 0})
        sup["outstanding"] = round(sup["outstanding"] + out, 2)
        sup["bill_count"] += 1
        rows.append({
            "bill_id": b["id"], "bill_number": b.get("bill_number"),
            "supplier_invoice_no": b.get("supplier_invoice_no", ""),
            "po_number": b.get("po_number", ""), "supplier_name": b.get("supplier_name"),
            "supplier_id": b.get("supplier_id", ""), "status": b.get("status"),
            "grand_total": fin["grand_total"], "amount_paid": fin["amount_paid"],
            "outstanding": out, "payment_status": fin["payment_status"],
            "days_past_due": days, "days_outstanding": days, "aging_bucket": bucket,
            "aging_label": AP_AGING_LABELS[bucket],
            "due_date": due or "", "due_basis": basis, "match_status": b.get("match_status", ""),
        })
    rows.sort(key=lambda r: (-r["days_past_due"], -r["outstanding"]))
    ent_ids = _scope_entity_ids(q)
    return {
        "total_outstanding": from_cents(total_sen),
        "aging": {k: from_cents(v) for k, v in aging_sen.items()},
        "aging_labels": [{"key": k, "label": AP_AGING_LABELS[k]} for k in AP_AGING_KEYS],
        "by_supplier": sorted(by_supplier.values(), key=lambda s: -s["outstanding"]),
        "bills": rows,
        "reconciliation": await _ap_reconciliation(ent_ids, total_sen),
    }


# ── Hutang per Pemasok (S5, pelatihan 18 Nov) — STATIC sebelum route /{id} ──────

@router.get("/vendor-bills/payables/by-supplier")
async def vendor_bill_payables_by_supplier(request: Request, entity_id: str = None) -> Dict[str, Any]:
    """Keuangan › Hutang › Hutang per Pemasok: satu baris per (pemasok, PT) — jumlah tagihan terbuka, sisa hutang,
    kelompok umur (sama dengan ringkasan Hutang › Tagihan), jatuh tempo terdekat, tagihan yang dipegang kontrabon, dan
    potongan belum dipakai (nota debit + uang muka ke pemasok). Logika: `services/ap_party_service.supplier_rows`."""
    await require_permission(request, "vendor_bill", "view")
    from services import ap_party_service as aps
    ctx = await entity_ctx(request)
    q = resolve_list_scope("vendor_bills", {}, ctx, entity_id)
    out = await aps.supplier_rows(q)
    ent_ids = _scope_entity_ids(q)
    out["combined"] = ent_ids is None or len(ent_ids) != 1
    return out


@router.get("/vendor-bills/payables/by-supplier/{supplier_id}")
async def vendor_bill_payables_supplier_detail(supplier_id: str, request: Request,
                                               entity_id: str = None) -> Dict[str, Any]:
    """Rincian hutang satu pemasok: tagihan terbuka (+ kontrabon pemegangnya), kontrabon terbuka (boleh dibayar
    sekarang atau belum), dan potongan belum dipakai. Kontrabon hanya bagi pemegang `contra_bon.view`."""
    actor = await require_permission(request, "vendor_bill", "view")
    from dependencies import has_permission
    from services import ap_party_service as aps
    ctx = await entity_ctx(request)
    q = resolve_list_scope("vendor_bills", {}, ctx, entity_id)
    ids = _scope_entity_ids(q) or list(ctx.allowed_entity_ids)
    out = await aps.supplier_detail(supplier_id, ids, {"entity_id": q["entity_id"]} if "entity_id" in q else {},
                                    with_contra_bons=await has_permission(actor, "contra_bon", "view"))
    if out is None:
        raise HTTPException(status_code=404, detail="Pemasok tidak ditemukan")
    out["combined"] = len(ids) != 1
    return out


#: PK-41 (RP-07) — kelompok umur hutang: definisi di `vendor_bill_service` (dipakai juga Hutang per Pemasok, S5).


def _scope_entity_ids(q: Dict[str, Any]) -> Optional[List[str]]:
    """PT dari saringan `resolve_list_scope` (str / `$in`); None = semua PT."""
    v = q.get("entity_id")
    if isinstance(v, str) and v:
        return [v]
    if isinstance(v, dict) and v.get("$in") is not None:
        return list(v["$in"])
    return None


async def _ap_reconciliation(ent_ids: Optional[List[str]], bills_sen: int) -> Dict[str, Any]:
    """PK-41 (RP-07) — `expected_gl = bills + landed − debit_notes` dibanding saldo akun hutang (`pembelian.hutang`,
    semua akun yang pernah dipakai) saat ini.

    * `landed_cost_outstanding` — sisa voucher biaya masuk berstatus hutang (`applied`/`paid`) yang belum dibayar: jurnal
      voucher sudah mengkredit akun hutang, tetapi tidak ada tagihannya.
    * `debit_notes_open` — retur beli yang sudah menurunkan akun hutang (jurnal `purchase_return` mendebit akun hutang,
      dasar `ap_basis = "hutang"`) tetapi belum menurunkan sisa tagihan mana pun: potongannya baru mengurangi tagihan saat
      kontrabon yang memuatnya LUNAS (`contra_bon_service`: potongan = pelunasan non-kas faktur). Nilai = Σ (debit − kredit)
      akun hutang jurnal retur itu − Σ potongan retur itu di kontrabon berstatus `paid`.
    """
    from services import report_basis as rb
    from services.gl_mapping_service import known_codes
    from services.landed_cost_service import PAYABLE_VOUCHER_STATUSES, voucher_financials
    ent_q: Dict[str, Any] = {"entity_id": {"$in": ent_ids}} if ent_ids else {}
    landed = 0
    async for v in db.landed_cost_vouchers.find({"status": {"$in": sorted(PAYABLE_VOUCHER_STATUSES)}, **ent_q},
                                                {"_id": 0}):
        landed += to_cents(voucher_financials(v)["outstanding"])
    hutang_by_pt: Dict[str, set] = {}
    by_return: Dict[str, int] = {}
    async for je in db.journal_entries.find(
            {"status": {"$ne": "void"}, "source_type": {"$in": ["purchase_return", "purchase_return_reversal"]}, **ent_q},
            {"_id": 0, "source_id": 1, "entity_id": 1, "lines": 1}):
        eid = je.get("entity_id") or ""
        if eid not in hutang_by_pt:
            hutang_by_pt[eid] = set(await known_codes("pembelian.hutang", eid or None))
        sen = sum(to_cents(float(ln.get("debit") or 0)) - to_cents(float(ln.get("credit") or 0))
                  for ln in je.get("lines") or [] if ln.get("account_code") in hutang_by_pt[eid])
        if sen:
            by_return[je.get("source_id") or ""] = by_return.get(je.get("source_id") or "", 0) + sen
    applied: Dict[str, int] = {}
    if by_return:
        async for cb in db.contra_bons.find({"status": "paid", "deductions.ref_id": {"$in": list(by_return)}},
                                            {"_id": 0, "deductions": 1}):
            for d in cb.get("deductions") or []:
                if d.get("kind") == "purchase_return" and d.get("ref_id") in by_return:
                    applied[d["ref_id"]] = applied.get(d["ref_id"], 0) + to_cents(float(d.get("amount") or 0))
    debit_open = sum(max(0, v - applied.get(rid, 0)) for rid, v in by_return.items())
    expected = bills_sen + landed - debit_open
    gl = await rb.saldo_akun_sen("pembelian.hutang", ent_ids, None, kredit=True)
    return {"bills_outstanding": from_cents(bills_sen), "landed_cost_outstanding": from_cents(landed),
            "debit_notes_open": from_cents(debit_open), "expected_gl": from_cents(expected),
            "gl_balance": from_cents(gl), "unexplained": from_cents(gl - expected)}


# ── List & detail ─────────────────────────────────────────────────────────────

@router.get("/vendor-bills/status-counts")
async def vendor_bill_status_counts(request: Request, entity_id: str = None) -> Dict[str, int]:
    """Jumlah bill per status (untuk badge tab) — agregasi ringan, tak fetch dokumen."""
    await require_permission(request, "vendor_bill", "view")
    ctx = await entity_ctx(request)
    query = resolve_list_scope("vendor_bills", {}, ctx, entity_id)
    pipeline = [{"$match": query}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    agg = await db.vendor_bills.aggregate(pipeline).to_list(100)
    counts: Dict[str, int] = {row["_id"]: int(row["n"]) for row in agg if row.get("_id")}
    counts["all"] = sum(counts.values())
    return counts


@router.get("/vendor-bills")
async def list_vendor_bills(
    request: Request, entity_id: str = None, status: str = None, po_id: str = None, supplier_id: str = None
) -> Any:
    """Daftar Vendor Bill (filter entitas/status/PO/pemasok). Opt-in paginasi (?page/?page_size).
    MN-T3 — `supplier_id` menyaring tagihan satu pemasok (kartu pemasok › Tagihan)."""
    await require_permission(request, "vendor_bill", "view")
    ctx = await entity_ctx(request)
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if po_id:
        query["po_id"] = po_id
    if supplier_id:
        query["supplier_id"] = supplier_id
    query = resolve_list_scope("vendor_bills", query, ctx, entity_id)
    if is_paged(request):
        page, page_size, q, _sort = get_page_params(request)
        if q:
            query = merge_query(query, build_search(q, ["bill_number", "supplier_name", "po_number", "supplier_invoice_no"]))
        items, total = await fetch_page(db.vendor_bills, query, page, page_size, sort_field="created_at", sort_dir=-1)
        return envelope([_hydrate(b) for b in items], total, page, page_size)
    bills = await db.vendor_bills.find(query, {"_id": 0}).sort("created_at", -1).to_list(300)
    return [_hydrate(b) for b in bills]


@router.get("/vendor-bills/{bill_id}")
async def get_vendor_bill(bill_id: str, request: Request) -> Dict[str, Any]:
    """Detail satu Vendor Bill + ringkasan keuangan."""
    await require_permission(request, "vendor_bill", "view")
    ctx = await entity_ctx(request)
    bill = safe_doc(await db.vendor_bills.find_one({"id": bill_id}, {"_id": 0}))
    if not bill:
        raise HTTPException(status_code=404, detail="Vendor Bill tidak ditemukan")
    assert_entity_access(bill, "vendor_bills", ctx)
    out = _hydrate(bill)
    # Pelatihan 18 Nov (uji variasi V5) — toleransi selisih bayar supplier PT ini (`payment.variance_ap_tolerance_rupiah`)
    # ikut dikirim supaya form Bayar pemasok bisa memberi tahu SEBELUM simpan bahwa kurang bayar receh ditutup otomatis.
    from services.config_resolver import resolve as _resolve
    try:
        tol = (await _resolve("payment.variance_ap_tolerance_rupiah", {"entity_id": bill.get("entity_id") or ""}))["value"]
        out["payment_tolerance"] = round(float(tol or 0), 2)
    except Exception:  # noqa: BLE001 — pengaturan tak terbaca tidak boleh menggagalkan rincian tagihan
        out["payment_tolerance"] = None
    return out


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("/vendor-bills")
async def create_vendor_bill(payload: VendorBillCreate, request: Request) -> Dict[str, Any]:
    """Buat Vendor Bill dari PO + jalankan 3-way matching.
    submit_now=True → langsung submit (posted bila match bersih, atau pending_approval
    bila ada variance dalam toleransi). Over-billing di luar toleransi → ditolak."""
    actor = await require_permission(request, "vendor_bill", "create")
    po = safe_doc(await db.purchase_orders.find_one({"id": payload.po_id}, {"_id": 0}))
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order tidak ditemukan")
    if po.get("status") in ("waiting_approval", "rejected", "cancelled"):
        raise HTTPException(status_code=400,
                            detail=f"PO status '{po.get('status')}' belum bisa ditagih (perlu disetujui/diterima).")
    if not payload.items:
        raise HTTPException(status_code=400, detail="Minimal 1 item untuk ditagih.")

    entity_id = (payload.entity_id or po.get("entity_id")
                 or active_entity_or(DEFAULT_ENTITY_ID))
    match_mode = payload.match_mode if payload.match_mode in ("received", "ordered") else "received"

    # FASE E-7 (E7.2) — tagihan dari badan usaha grup lahir sebagai FAKTUR INTERNAL di
    # menu Antar Entitas (berpasangan dengan faktur masukan di sisi pembeli), bukan
    # Vendor Bill biasa. PO lama yang sudah salah jalur pun tertahan di sini.
    if po.get("supplier_id"):
        _sup = await db.suppliers.find_one({"id": po["supplier_id"]}, {"_id": 0})
        if _sup:
            from services import group_partner_service as _grp
            await _grp.assert_supplier_not_group_entity(
                _sup, doc_label="Tagihan Supplier (Vendor Bill)")

    # Dedupe nomor invoice supplier (cegah double-billing eksternal).
    inv_no = (payload.supplier_invoice_no or "").strip()
    if inv_no:
        dup = await db.vendor_bills.find_one(
            {"supplier_id": po.get("supplier_id", ""), "supplier_invoice_no": inv_no,
             "status": {"$in": list(ACTIVE_BILL_STATUSES)}}, {"_id": 0, "bill_number": 1})
        if dup:
            raise HTTPException(status_code=409,
                                detail=f"No. invoice supplier '{inv_no}' sudah dipakai pada {dup.get('bill_number')}.")

    # Susun raw_items: quantity = billed_qty (agar subtotal=price×qty invarian).
    raw_items: List[Dict[str, Any]] = []
    seen_keys: set = set()
    po = await ensure_line_ids(po)
    for line in payload.items:
        # FN-02 — tiap baris tagihan menunjuk SATU baris PO (po_line_id); produk yang muncul di
        # beberapa baris PO wajib memilih baris, dan satu baris PO tidak boleh ditagih dua kali.
        cands = [(i, it) for i, it in enumerate(po.get("items", [])) if it.get("product_id") == line.product_id]
        if line.po_line_id:
            cands = [c for c in cands if po_line_id(c[1], c[0]) == line.po_line_id]
        elif line.po_line_code and len(cands) > 1:
            narrowed = [c for c in cands if c[1].get("line_code") == line.po_line_code]
            cands = narrowed if len(narrowed) == 1 else cands
        if not cands:
            raise HTTPException(status_code=400,
                                detail=f"Produk {line.product_id} tidak ada di PO {po.get('po_number')}"
                                       + (f" pada baris {line.po_line_id}." if line.po_line_id else "."))
        if len(cands) > 1:
            raise HTTPException(status_code=400, detail=(
                f"Produk {line.product_id} ada di {len(cands)} baris PO — pilih baris PO (po_line_id)."))
        idx, po_it = cands[0]
        key = po_line_id(po_it, idx)
        if key in seen_keys and float(line.billed_qty or 0) > 0:
            raise HTTPException(status_code=400, detail=(
                f"Baris PO {key} muncul lebih dari satu kali — gabungkan menjadi satu baris tagihan."))
        seen_keys.add(key)
        billed_qty = float(line.billed_qty or 0)
        if billed_qty <= 0:
            continue
        price = float(line.price) if line.price and line.price > 0 else float(po_it.get("price", 0) or 0)
        raw_items.append({
            "product_id": line.product_id,
            "sku": po_it.get("sku", ""),
            "product_name": po_it.get("product_name", ""),
            "quantity": billed_qty,
            "billed_qty": billed_qty,
            "unit": po_it.get("unit", "meter"),
            "price": price,
            "discount_percent": float(line.discount_percent or 0),
            "po_line_id": key,
            "po_line_code": po_it.get("line_code") or "",
        })
    if not raw_items:
        raise HTTPException(status_code=400, detail="Tidak ada qty tagihan yang valid (> 0).")

    pricing = await compute_order_pricing(
        raw_items, entity_id, payload.order_discount_percent,
        cfg_section="purchasing", tax_override=payload.tax_mode or po.get("tax_mode", ""))

    tol = await _tolerances(entity_id)
    # FN-02 — klaim PO selama hitung-sisa → insert: dua tagihan bersamaan tidak bisa sama-sama
    # membaca sisa yang sama (yang kalah 409, coba lagi).
    from services import atomic_claim as _saga
    await _saga.claim("purchase_orders", po["id"], "vendor_bill_create", actor=actor.get("name", ""))
    try:
        return await _create_bill_locked(payload, po, pricing, tol, match_mode, entity_id, inv_no, actor)
    finally:
        await _saga.release("purchase_orders", po["id"])


async def _due_from_supplier_term(po: Dict[str, Any], bill_date: str, entity_id: str) -> str:
    """PK-41 (RP-07) — jatuh tempo tagihan tanpa `due_date` = tanggal tagihan + `net_days` termin pemasok PO itu
    (master Syarat Bayar lapisan PT; pemasok tanpa termin = 0 hari, perilaku ringkasan hutang sebelumnya)."""
    from services import report_basis as rb
    due, _basis = await rb.jatuh_tempo_tagihan(
        {"bill_date": bill_date, "supplier_id": po.get("supplier_id", ""), "entity_id": entity_id}, {})
    return due or ""


async def _create_bill_locked(payload, po, pricing, tol, match_mode, entity_id, inv_no, actor) -> Dict[str, Any]:
    billed_so_far = await already_billed_map(po["id"])
    match = evaluate_match(po, pricing["items"], match_mode, billed_so_far, tol["qty"], tol["price"], value_tol=tol["value"],
                           returned_unbilled=await returned_unbilled_map(po["id"]))   # PK-28

    if payload.submit_now and match["match_status"] == "blocked":
        # S2 (pelatihan 18 Nov) — "Kirim" yang pasti ditolak tidak boleh meninggalkan draf tersembunyi: dulu draf lebih
        # tagih tetap tersimpan sesudah 400 dan memegang No. faktur pemasok → kiriman yang sudah dikoreksi ditolak 409.
        raise HTTPException(status_code=400, detail=_lebih_tagih_msg(match))
    bill_number = await next_bill_number(entity_id)   # KP-T5 — PT dokumen (N1)
    # A2 (pelatihan 18 Nov) — nama pembuat = akun yang masuk; `created_by` kiriman layar (bawaan skema "Admin") hanya
    # cadangan. Dulu setiap tagihan dari layar tercatat "dibuat Admin" di Riwayat walau dibuat Manajer.
    actor_name = actor.get("name") or payload.created_by or "Admin"
    needs_approval = match["match_status"] == "warning"
    timeline = [timeline_entry("created", "Tagihan pemasok dibuat", actor_name,
                               f"{len(match['items'])} item · {rupiah(pricing['grand_total'])} · "
                               f"3-way match: {_MATCH_LABEL.get(match['match_status'], match['match_status'])}")]

    bill = {
        "id": new_id("vbill"),
        "bill_number": bill_number,
        "supplier_invoice_no": inv_no,
        "po_id": po["id"],
        "po_number": po.get("po_number", ""),
        "supplier_id": po.get("supplier_id", ""),
        "supplier_name": po.get("supplier_name", ""),
        "supplier_npwp": po.get("supplier_npwp", ""),
        "warehouse_id": po.get("warehouse_id", ""),
        "warehouse_name": po.get("warehouse_name", ""),
        "entity_id": entity_id,
        "bill_date": payload.bill_date or now_iso(),
        # PK-41 (RP-07) — jatuh tempo kosong diisi dari termin pemasok (tanggal tagihan + net_days), tidak ditolak.
        "due_date": payload.due_date or await _due_from_supplier_term(po, payload.bill_date or now_iso(), entity_id),
        "match_mode": match_mode,
        "items": match["items"],
        # breakdown harga (invariant-safe, mirror PO P0-1)
        "total_amount": pricing["total_amount"],
        "items_discount_total": pricing["items_discount_total"],
        "order_discount_percent": pricing["order_discount_percent"],
        "order_discount_amount": pricing["order_discount_amount"],
        "discount_total": pricing["discount_total"],
        "net_subtotal": pricing["net_subtotal"],
        "dpp": pricing["dpp"],
        "ppn_rate": pricing["ppn_rate"],
        "ppn_mode": pricing["ppn_mode"],
        "is_pkp": pricing["is_pkp"],
        "ppn_amount": pricing["ppn_amount"],
        "tax_snapshot": pricing["tax_snapshot"],   # TX-T1 (D3) — aturan pajak saat tagihan dicatat
        "grand_total": pricing["grand_total"],
        "tax_mode": payload.tax_mode or po.get("tax_mode", ""),
        # 3-way match
        "match_status": match["match_status"],
        "match_exceptions": match["exceptions"],
        "within_tolerance": match["within_tolerance"],
        # lifecycle
        "status": "draft",
        "approval_required": needs_approval,
        "required_approval_role": "manager" if needs_approval else "",
        "approval_status": "not_required",
        "approved_by": "", "approved_at": "",
        # AP
        "amount_paid": 0.0,
        "outstanding": round(pricing["grand_total"], 2),
        "payment_status": "unpaid",
        "payments": [],
        "notes": payload.notes,
        "timeline": timeline,
        "created_by": actor_name,
        "created_by_id": actor.get("id", ""),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    try:
        await db.vendor_bills.insert_one(bill)
    except DuplicateKeyError as exc:   # PK-05 (SL-12) — indeks unik nomor faktur pemasok: balapan cek-lalu-sisip
        raise HTTPException(status_code=409,
                            detail=f"No. invoice supplier '{inv_no}' sudah dipakai pada tagihan lain.") from exc
    # FASE G-4 — tagihan supplier menaut ke PO-nya (dua arah) supaya 3-way match
    # bisa ditelusuri dari sisi mana pun.
    from services import doc_refs_service as _refs
    if bill.get("po_id"):
        await _refs.safe_link(("vendor_bill", bill["id"]), ("purchase_order", bill["po_id"]),
                              "parent", note="tagihan atas PO")
    await audit(actor["name"], "vendor_bill_created", "vendor_bill", bill["id"], {
        "bill_number": bill_number, "po_number": po.get("po_number"),
        "grand_total": pricing["grand_total"], "match_status": match["match_status"]})

    if payload.submit_now:
        return await _do_submit(bill["id"], actor, locked=True)
    return _hydrate(safe_doc(bill))


# ── Submit / approve / reject ─────────────────────────────────────────────────

async def _do_submit(bill_id: str, actor: Dict[str, Any], locked: bool = False) -> Dict[str, Any]:
    bill = await db.vendor_bills.find_one({"id": bill_id}, {"_id": 0})
    if not bill:
        raise HTTPException(status_code=404, detail="Vendor Bill tidak ditemukan")
    if not locked:  # FN-02 — submit (revalidasi sisa) diserialkan per PO: dua draft tidak lolos bersamaan
        from services import atomic_claim as _saga
        await _saga.claim("purchase_orders", bill["po_id"], "vendor_bill_submit", actor=actor.get("name", ""))
        try:
            return await _do_submit(bill_id, actor, locked=True)
        finally:
            await _saga.release("purchase_orders", bill["po_id"])
    if bill.get("status") not in ("draft",):
        raise HTTPException(status_code=409, detail=f"Bill status '{bill.get('status')}' tidak bisa di-submit.")
    # Re-evaluasi 3-way match terhadap kondisi terkini (cegah race/over-billing antar draft).
    po = await db.purchase_orders.find_one({"id": bill["po_id"]}, {"_id": 0})
    if po:
        tol = await _tolerances(bill.get("entity_id"))
        billed_so_far = await already_billed_map(bill["po_id"], exclude_bill_id=bill_id)
        match = evaluate_match(po, bill.get("items", []), bill.get("match_mode", "received"),
                               billed_so_far, tol["qty"], tol["price"], value_tol=tol["value"],
                               returned_unbilled=await returned_unbilled_map(bill["po_id"]))   # PK-28
        needs_approval = match["match_status"] == "warning"
        await db.vendor_bills.update_one({"id": bill_id}, {"$set": {
            "items": match["items"], "match_status": match["match_status"],
            "match_exceptions": match["exceptions"], "within_tolerance": match["within_tolerance"],
            "approval_required": needs_approval,
            "required_approval_role": "manager" if needs_approval else "",
            "updated_at": now_iso()}})
        bill["match_status"] = match["match_status"]
        bill["approval_required"] = needs_approval
    if bill.get("match_status") == "blocked":
        raise HTTPException(status_code=400, detail=_lebih_tagih_msg(match if po else {}, draft=True))
    if bill.get("approval_required"):
        updated = await db.vendor_bills.find_one_and_update(
            {"id": bill_id},
            {"$set": {"status": "pending_approval", "approval_status": "pending", "updated_at": now_iso()},
             "$push": {"timeline": timeline_entry(
                 # S2 (pelatihan 18 Nov) — dulu "Menunggu persetujuan manager · ada selisih qty/harga dalam toleransi"
                 # padahal selisih harga justru MELEBIHI toleransi; penyetuju ditentukan Aturan Persetujuan.
                 "submitted_for_approval", "Menunggu persetujuan", actor.get("name", ""),
                 "ada selisih qty/harga terhadap PO/penerimaan — perlu disetujui orang lain")}},
            projection={"_id": 0}, return_document=ReturnDocument.AFTER)
        await audit(actor["name"], "vendor_bill_submitted", "vendor_bill", bill_id,
                    {"bill_number": bill.get("bill_number"), "to": "pending_approval"})
        return _hydrate(safe_doc(updated))
    # tanpa approval → langsung posted
    return await _post_bill(bill_id, actor, note="otomatis diposting (3-way match bersih)")


async def _post_bill(bill_id: str, actor: Dict[str, Any], note: str = "") -> Dict[str, Any]:
    # PK-37 (K-03) — PERIKSA periode buku hari ini sebelum tagihan berubah status (jalur ajukan → langsung posting).
    from services.book_date import periksa_periode_dokumen_409
    _b = await db.vendor_bills.find_one({"id": bill_id}, {"_id": 0}) or {}
    await periksa_periode_dokumen_409(_b.get("entity_id") or DEFAULT_ENTITY_ID, None, jenis="tagihan pemasok")
    # PK-28 (IV-03) — nilai GR/IR yang dihapus faktur + selisih harga terhadap PO, dihitung SEBELUM status berubah dan
    # ditulis sekali pada tulisan `posted` (jurnal & ulang posting membaca angka tersimpan ini).
    _grir = await grir_fields(_b)
    # KN-B05 — posting berprasyarat status: dua submit/approve bersamaan → tepat satu jurnal AP.
    updated = await db.vendor_bills.find_one_and_update(
        {"id": bill_id, "status": {"$in": ["draft", "pending_approval"]}},
        {"$set": {"status": "posted", "approval_status": "approved" if note.startswith("disetujui") else "not_required",
                  "posted_by": actor.get("name", ""), "posted_at": now_iso(), "updated_at": now_iso(),
                  "gl_status": "pending", **_grir},   # PK-18 — efek ditulis, jurnal belum dicoba
         "$push": {"timeline": timeline_entry("posted", "Tagihan diposting (hutang diakui)", actor.get("name", ""), note)}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(status_code=409, detail="Bill sudah di-posting/berubah oleh proses lain. Muat ulang.")
    # T4 DIBAYAR (2026-06c): dulu `updated["po_id"]` → `KeyError` (HTTP 500) untuk
    # tagihan tanpa PO (mis. tagihan makloon). Tagihan tanpa PO memang tak punya
    # billing PO untuk disinkronkan; itu keadaan SAH, bukan galat server.
    _po_id = updated.get("po_id") or ""
    if _po_id:
        await sync_po_billing(_po_id)
    # S#2026-07-21 — Traceability: tautkan invoice supplier ke roll asal PO ini
    # (untuk kartu asal produk + retur presisi). Best-effort, non-blocking.
    try:
        billed_pids = [it.get("product_id") for it in (updated.get("items") or []) if it.get("product_id")]
        if billed_pids and _po_id:
            await db.inventory_rolls.update_many(
                {"$and": [
                    {"$or": [{"po_id": _po_id}, {"acquired.ref_id": _po_id}]},
                    {"product_id": {"$in": billed_pids}},
                    {"$or": [{"vendor_bill_id": {"$in": ["", None]}}, {"vendor_bill_id": {"$exists": False}}]},
                ]},
                {"$set": {"vendor_bill_id": updated["id"],
                          "supplier_invoice_no": updated.get("supplier_invoice_no", ""),
                          "updated_at": now_iso()}})
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("Gagal tautkan invoice ke roll (bill %s): %s", bill_id, exc)
    # Gelombang 1 F-5 — posting AP ke GL: Dr GR-IR + PPN Masukan / Cr Hutang. PK-18 (GL-02) — lewat pintu tahan-gagal:
    # jurnal gagal TIDAK membatalkan tagihan dan tidak 500; `gl_status`/`gl_error` tertulis dan tampil di Posting Gagal.
    jr = await gl_service.post_durable("vendor_bills", bill_id, lambda: gl_service.post_vendor_bill(updated),
                                       source_type="vendor_bill", source_id=bill_id)
    updated.update({"gl_status": jr["gl_status"], "gl_error": jr["gl_error"],
                    "journal_entry_id": jr["journal_entry_id"]})
    await audit(actor["name"], "vendor_bill_posted", "vendor_bill", bill_id,
                {"bill_number": updated.get("bill_number"), "grand_total": updated.get("grand_total")})
    return _hydrate(safe_doc(updated))


@router.post("/vendor-bills/{bill_id}/submit")
async def submit_vendor_bill(bill_id: str, request: Request) -> Dict[str, Any]:
    """Submit bill: posted (match bersih) atau pending_approval (ada variance)."""
    actor = await require_permission(request, "vendor_bill", "update")
    await guard_doc(request, "vendor_bills", await db.vendor_bills.find_one({"id": bill_id}, {"_id": 0}),
                    not_found="Vendor Bill tidak ditemukan")  # KN-A04
    return await _do_submit(bill_id, actor)


@router.post("/vendor-bills/{bill_id}/approve")
async def approve_vendor_bill(bill_id: str, request: Request) -> Dict[str, Any]:
    """Approve bill yang menunggu persetujuan (role manager+). SoD: pembuat ≠ approver."""
    actor = await current_user(request)
    bill = await db.vendor_bills.find_one({"id": bill_id}, {"_id": 0})
    # KN-A04 — aksi tulis dijaga entitas (dulu hanya pangkat peran).
    await guard_doc(request, "vendor_bills", bill, not_found="Vendor Bill tidak ditemukan")
    if bill.get("bill_type") == "campaign_expense":   # COMM-04 — aturan tagihan kampanye satu sumber
        from services import marketing_cost_service as _mcost
        return _hydrate(safe_doc(await _mcost.approve_campaign_bill(bill, actor)))
    if bill.get("status") != "pending_approval":
        raise HTTPException(status_code=409, detail=f"Bill status '{bill.get('status')}' tidak menunggu approval.")
    # KP-T4 (PR-05) — izin `vendor_bill.approve` + Aturan Persetujuan (dulu hanya peringkat, tanpa izin).
    from services import approval_policy_service as _aps
    await _aps.assert_can_decide("vendor_bill", bill.get("entity_id"), float(bill.get("grand_total") or 0), actor)
    # KF-T6 — pembuat ≠ penyetuju dari `kontrol.tagihan_pemasok.*` (satu pembantu).
    from services import dual_control as _dc
    await _dc.tolak_bila_pelaku_sama("tagihan_pemasok", bill, actor, bill.get("entity_id", ""),
                                     nominal=float(bill.get("grand_total") or bill.get("total_amount") or 0),
                                     pengaju=[bill.get("created_by_id")])
    # PK-37 (K-03) — PERIKSA periode sebelum tanda setuju ditulis (`_post_bill` memeriksa lagi untuk jalur ajukan).
    from services.book_date import periksa_periode_dokumen_409
    await periksa_periode_dokumen_409(bill.get("entity_id") or DEFAULT_ENTITY_ID, None, jenis="tagihan pemasok")
    # PK-39 (K-12) — tagihan TANPA PO berakun beban: PERIKSA anggaran sebelum tanda setuju ditulis. Tagihan ber-PO
    # sudah dicakup komitmen PO; tagihan jasa makloon (tanpa akun beban) tidak menghasilkan sasaran.
    extra: Dict[str, Any] = {}
    if not bill.get("po_id"):
        from services import budget_service as _bs
        targets = await _bs.bill_budget_targets(bill)
        if targets:
            try:
                extra["budget_check"] = await _bs.enforce_budget(bill.get("entity_id", ""), targets,
                                                                 when="bill_approve", date="", actor=actor)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.vendor_bills.update_one(
        {"id": bill_id},
        {"$set": {"approval_status": "approved", "approved_by": actor["name"], "approved_at": now_iso(), **extra}})
    return await _post_bill(bill_id, actor, note=f"disetujui oleh {actor.get('role')}")


@router.post("/vendor-bills/{bill_id}/reject")
async def reject_vendor_bill(bill_id: str, payload: VendorBillDecision, request: Request) -> Dict[str, Any]:
    """Tolak bill yang menunggu persetujuan → status cancelled."""
    actor = await current_user(request)
    bill = await db.vendor_bills.find_one({"id": bill_id}, {"_id": 0})
    # KN-A04 — aksi tulis dijaga entitas (dulu hanya pangkat peran).
    await guard_doc(request, "vendor_bills", bill, not_found="Vendor Bill tidak ditemukan")
    if bill.get("bill_type") == "campaign_expense":
        from services import marketing_cost_service as _mcost
        out = await _mcost.reject_campaign_bill(bill, payload.notes or "", actor)
        await audit(actor["name"], "vendor_bill_rejected", "vendor_bill", bill_id,
                    {"bill_number": bill.get("bill_number"), "reason": payload.notes})
        return _hydrate(safe_doc(out))
    if bill.get("status") != "pending_approval":
        raise HTTPException(status_code=409, detail=f"Bill status '{bill.get('status')}' tidak menunggu approval.")
    from services import approval_policy_service as _aps   # KP-T4 (PR-05) — izin `vendor_bill.reject` + Aturan
    await _aps.assert_can_decide("vendor_bill", bill.get("entity_id"), float(bill.get("grand_total") or 0), actor,
                                 action="reject")
    updated = await db.vendor_bills.find_one_and_update(
        {"id": bill_id},
        {"$set": {"status": "cancelled", "approval_status": "rejected",
                  "rejected_by": actor["name"], "rejection_reason": payload.notes,
                  "rejected_at": now_iso(), "updated_at": now_iso()},
         "$push": {"timeline": timeline_entry("rejected", "Tagihan ditolak", actor["name"], payload.notes or "")}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await audit(actor["name"], "vendor_bill_rejected", "vendor_bill", bill_id,
                {"bill_number": bill.get("bill_number"), "reason": payload.notes})
    return _hydrate(safe_doc(updated))


# ── Pay ───────────────────────────────────────────────────────────────────────

@router.post("/vendor-bills/{bill_id}/pay")
async def pay_vendor_bill(bill_id: str, payload: VendorBillPaymentCreate, request: Request) -> Dict[str, Any]:
    """Bayar Vendor Bill (kas keluar) lewat satu pintu niat bayar (PK-05, `ap_payment_service.pay_payable`).

    Kas selalu milik PT tagihan dan ditarik dari rekening yang dipilih (`bank_account_id`, wajib); `entity_id`,
    `cash_type`, `created_by` dari isi permintaan diabaikan. Header `Idempotency-Key` = satu niat: kirim ulang tidak
    menggandakan kas. FASE G-3 — selisih pembayaran supplier tetap ditakar dan diputus SEKALI per niat.
    """
    actor = await require_permission(request, "vendor_bill", "pay")
    bill = await db.vendor_bills.find_one({"id": bill_id}, {"_id": 0})
    # KN-A04 — aksi tulis dijaga entitas (dulu hanya pangkat peran).
    await guard_doc(request, "vendor_bills", bill, not_found="Vendor Bill tidak ditemukan")
    from services import ap_payment_service as aps
    from services import payment_variance_service as pvs
    vdecision = payload.variance or {}
    try:
        res = await aps.pay_payable(
            kind="vendor_bill", target_id=bill_id, actor=actor, amount=payload.amount, paid_at=payload.paid_at,
            bank_account_id=payload.bank_account_id, method=payload.method, notes=payload.notes,
            idempotency_key=(request.headers.get("Idempotency-Key") or "").strip(), variance=vdecision)
    except aps.ApPaymentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail()) from exc
    intent = res["intent"]
    assessment = intent.get("assessment") or {}
    decision = None
    if not res["replayed"] and not intent.get("variance_decision_id") \
            and assessment.get("direction") not in (None, pvs.DIR_NONE) \
            and (assessment["direction"] == pvs.DIR_ROUNDING or vdecision.get("kind")):
        current = await db.vendor_bills.find_one({"id": bill_id}, {"_id": 0})
        try:
            decision = await pvs.decide_bill(safe_doc(current), assessment, vdecision, actor,
                                             advance_cash=res["advance_cash"])
            await db.ap_payment_intents.update_one({"id": intent["id"]}, {"$set": {
                "variance_decision_id": (decision or {}).get("id", "") or "dibuat"}})
        except pvs.VarianceError as exc:
            # Uang sudah keluar — keputusan yang gagal tidak boleh membatalkannya; catat sebabnya.
            await db.vendor_bills.update_one({"id": bill_id}, {"$push": {"timeline": timeline_entry(
                "variance_failed", "Keputusan selisih gagal", actor["name"], str(exc))}})
    updated = await db.vendor_bills.find_one({"id": bill_id}, {"_id": 0})
    if not res["replayed"]:
        await audit(actor["name"], "vendor_bill_payment", "vendor_bill", bill_id,
                    {"bill_number": bill.get("bill_number"), "amount": intent.get("amount"),
                     "advance": intent.get("advance_amount"), "cash": intent.get("cash_txn_number"),
                     "payment_intent": intent["id"], "variance": (decision or {}).get("kind", "")})
    out = _hydrate(safe_doc(updated))
    out["variance_assessment"] = assessment
    if decision:
        out["variance_decision"] = decision
    out["payment_intent"] = aps.intent_summary(intent)
    out["warning"] = res["warning"]
    return out


@router.post("/vendor-bills/{bill_id}/payments/{payment_id}/void")
async def void_vendor_bill_payment(bill_id: str, payment_id: str, payload: VendorBillDecision,
                                   request: Request) -> Dict[str, Any]:
    """P18 APAR-01 — batalkan SATU pembayaran bill (salah nominal/rekening): jurnal kas dibalik,
    kas di-void, hutang kembali terbuka. Kas turunan bill tak bisa di-void dari layar kas (FN-07)."""
    actor = await require_permission(request, "vendor_bill", "pay")
    bill = await db.vendor_bills.find_one({"id": bill_id}, {"_id": 0})
    await guard_doc(request, "vendor_bills", bill, not_found="Vendor Bill tidak ditemukan")
    if len((payload.notes or "").strip()) < 5:
        raise HTTPException(status_code=400, detail="Alasan pembatalan pembayaran wajib (min. 5 karakter).")
    pay = next((p for p in bill.get("payments") or [] if p.get("id") == payment_id), None)
    if not pay or pay.get("voided"):
        raise HTTPException(status_code=409, detail="Pembayaran tidak ditemukan atau sudah dibatalkan.")
    if await db.payment_variance_decisions.count_documents({"bill_id": bill_id, "status": {"$ne": "reversed"}}) \
            or await db.cash_transactions.count_documents({"ref_type": "ap_advance", "ref_id": bill_id, "status": {"$ne": "void"}}):
        raise HTTPException(status_code=409, detail="Bill ini punya keputusan selisih/uang muka — batalkan keputusan itu dulu.")
    txn = await db.cash_transactions.find_one({"id": pay.get("cash_txn_id")}, {"_id": 0}) or {}
    # PK-21 — yang menahan hanya pencocokan nyata (`reconciled_amount`); tanda manual lama tidak bisa dilepas lagi.
    if float(txn.get("reconciled_amount") or 0) > 0:
        raise HTTPException(status_code=409, detail="Kas pembayaran ini sudah dicocokkan dengan mutasi bank — lepaskan dulu.")
    # Pelatihan 18 Nov (uji variasi V5) — pembayaran bertanggal MAJU (mis. 15 Des) yang dibatalkan hari ini dulu dibalik
    # bertanggal hari ini: November mendapat Dr Bank / Cr Hutang tanpa jurnal aslinya (saldo kas & hutang menggelembung
    # sampai 15 Des). Pembalik tidak boleh sebelum jurnal aslinya (aturan yang sama dengan `gl_service.reverse_entry`):
    # tanggal pembalik = tanggal kas asli bila masih di depan, selain itu hari ini (perilaku lama).
    from services.book_date import tanggal_buku
    try:
        tgl_kas = tanggal_buku(txn.get("txn_date")) if txn.get("txn_date") else ""
    except ValueError:
        tgl_kas = ""
    tgl_balik = tgl_kas if tgl_kas and tgl_kas > tanggal_buku() else ""
    try:
        await gl_service.preflight_posting(bill.get("entity_id", ""), tgl_balik or now_iso())
    except gl_service.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    amount = round(float(pay.get("amount") or 0), 2)
    claimed = await db.vendor_bills.find_one_and_update(
        {"id": bill_id, "payments": {"$elemMatch": {"id": payment_id, "voided": {"$ne": True}}}},
        {"$set": {"payments.$.voided": True, "payments.$.voided_at": now_iso(), "payments.$.voided_by": actor["name"],
                  "payments.$.void_reason": payload.notes, "status": "posted", "updated_at": now_iso()},
         "$inc": {"amount_paid": -amount},
         "$push": {"timeline": timeline_entry("payment_voided", "Pembayaran dibatalkan", actor["name"],
                                              f"{rupiah(amount)} · {payload.notes}")}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not claimed:
        raise HTTPException(status_code=409, detail="Pembayaran sedang/sudah dibatalkan.")
    rev = None
    if txn:
        from services import cash_ledger   # PK-20 — jurnal asal dipastikan ada lewat pembuat kas
        await cash_ledger.ensure_posted(txn["id"])
        rev = await gl_service.post_cash_void(txn["id"], label=txn.get("number", ""), created_by=actor["name"],
                                              date=tgl_balik)
        await db.cash_transactions.update_one({"id": txn["id"]}, {"$set": {
            "status": "void", "updated_at": now_iso(), "void_journal_entry_id": (rev or {}).get("id", "")}})
    await sync_po_billing(bill["po_id"])
    await audit(actor["name"], "vendor_bill_payment_voided", "vendor_bill", bill_id,
                {"payment_id": payment_id, "amount": amount, "cash": txn.get("number", ""),
                 "reversal_je": (rev or {}).get("number", "")}, reason=payload.notes)
    return _hydrate(safe_doc(await db.vendor_bills.find_one({"id": bill_id}, {"_id": 0})))



@router.post("/vendor-bills/{bill_id}/cancel")
async def cancel_vendor_bill(bill_id: str, payload: VendorBillDecision, request: Request) -> Dict[str, Any]:
    """Batalkan bill (draft/pending_approval/posted yang belum dibayar)."""
    actor = await require_permission(request, "vendor_bill", "update")
    bill = await db.vendor_bills.find_one({"id": bill_id}, {"_id": 0})
    # KN-A04 — aksi tulis dijaga entitas (dulu hanya pangkat peran).
    await guard_doc(request, "vendor_bills", bill, not_found="Vendor Bill tidak ditemukan")
    if float(bill.get("amount_paid", 0) or 0) > 0.01:
        raise HTTPException(status_code=400, detail="Bill yang sudah ada pembayaran tidak bisa dibatalkan.")
    if bill.get("status") in ("cancelled", "paid"):
        raise HTTPException(status_code=409, detail=f"Bill status '{bill.get('status')}' tidak bisa dibatalkan.")
    # W2-004 — tagihan jasa makloon sudah diserap ke WIP/output (jurnal subcon_service); pembatalan
    # generik akan meninggalkan utang GL. Wajib lewat koreksi sumber (order makloon).
    if bill.get("bill_type") == "makloon_service" and bill.get("status") == "posted":
        raise HTTPException(status_code=409, detail=(
            "Tagihan jasa makloon sudah diserap ke nilai hasil makloon — tidak bisa dibatalkan dari sini. "
            "Koreksi lewat order makloon (klaim potong bon) agar utang, WIP dan nilai persediaan tetap sejalan."))
    if bill.get("status") == "posted":   # PK-37 (K-03) — pembatalan berjurnal pembalik: PERIKSA periode hari ini
        from services.book_date import periksa_periode_dokumen_409
        await periksa_periode_dokumen_409(bill.get("entity_id") or DEFAULT_ENTITY_ID, None, jenis="pembatalan tagihan")
    # T-01 Opsi B (INV-ATOMIC-01) — klaim bill sebelum jurnal dibalik + PO disinkronkan;
    # dua "Batalkan" bersamaan tidak membalik jurnal dua kali. Status akhir ditulis finish_set.
    from services import atomic_claim as _saga
    await _saga.claim("vendor_bills", bill_id, "vendor_bill_cancel",
                      precondition={"status": bill.get("status"), "amount_paid": {"$not": {"$gt": 0.01}}},
                      actor=actor["name"])
    # S#074 (VB-CANCEL-GL): balik jurnal bila bill sudah posted (kembalikan saldo Hutang/GR-IR/PPN)
    if bill.get("status") == "posted":
        from services import gl_service
        try:
            await gl_service.reverse_vendor_bill(bill, reason=payload.notes or "", actor_name=actor["name"])
        except Exception as exc:  # noqa: BLE001 — kunci dibiarkan + alasan tercatat (terlihat di Kunci Saga)
            await _saga.mark_failed("vendor_bills", bill_id, f"reverse_vendor_bill: {exc}")
            raise
    updated = await db.vendor_bills.find_one_and_update(
        {"id": bill_id},
        {**_saga.finish_set({"status": "cancelled", "cancelled_by": actor["name"],
                             "cancel_reason": payload.notes, "cancelled_at": now_iso(), "updated_at": now_iso()}),
         "$push": {"timeline": timeline_entry("cancelled", "Tagihan dibatalkan", actor["name"], payload.notes or "")}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    await sync_po_billing(bill["po_id"])
    await audit(actor["name"], "vendor_bill_cancelled", "vendor_bill", bill_id,
                {"bill_number": bill.get("bill_number")})
    return _hydrate(safe_doc(updated))

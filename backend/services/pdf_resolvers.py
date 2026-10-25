"""
pdf_resolvers.py — Ubah dokumen sumber (per doc_type) menjadi CONTEXT ternormalisasi
yang dikonsumsi MASTER_TEMPLATE. Setiap resolver async(doc, db) -> dict.

DOC_REGISTRY = SSOT daftar jenis dokumen yang bisa dicetak/PDF/e-sign/kirim.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from services.pdf_engine import fmt_rp, terbilang

# UAT 24 Okt (audit UI tahap 2, G5-11) — dokumen cetak berbahasa Indonesia: dulu `strftime("%d %b %Y")` mencetak
# bulan Inggris ("25 Oct 2026") dalam zona server (UTC), dan angka `:g` bergaya Inggris ("353.79 yard", "5337.91").
_BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
_WIB = timezone(timedelta(hours=7))


def fmt_date(s) -> str:
    """"25 Okt 2026" (WIB bila stempel berzona; tanggal polos apa adanya). Kosong → ""."""
    if not s:
        return ""
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return str(s)[:10]
    if d.tzinfo:
        d = d.astimezone(_WIB)
    return f"{d.day:02d} {_BULAN[d.month - 1]} {d.year}"


def fmt_now(seconds: bool = False) -> str:
    """Stempel "Dicetak" — "25 Okt 2026 14.30 WIB"."""
    d = datetime.now(_WIB)
    t = f"{d.hour:02d}.{d.minute:02d}" + (f".{d.second:02d}" if seconds else "")
    return f"{d.day:02d} {_BULAN[d.month - 1]} {d.year} {t} WIB"


def fmt_num(v, max_dec: int = 2) -> str:
    """Angka gaya Indonesia: ribuan bertitik, desimal berkoma, nol di belakang dibuang ("5.337,91", "12", "0,75")."""
    try:
        n = float(v or 0)
    except (TypeError, ValueError):
        return str(v)
    txt = f"{abs(n):,.{max_dec}f}"
    if "." in txt:
        txt = txt.rstrip("0").rstrip(".")
    txt = txt.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"-{txt}" if n < 0 and txt != "0" else txt


def _ppn_rows(doc, *, rate_key: str = "ppn_rate", amount_key: str = "ppn_amount", default_rate=11) -> list:
    """Baris PPN di total. G5-11 — rezim 12% × DPP nilai lain (11/12): dulu hanya "PPN 12.0%" pada nominal yang
    efektif 11% dari subtotal, tanpa dasar pengenaannya. Kini DPP-nya ditulis (bila dipakai) dan tarifnya id-ID."""
    if not doc.get(amount_key):
        return []
    rate = fmt_num(doc.get(rate_key, default_rate))
    rows = []
    if doc.get("dpp_nilai_lain") and doc.get("dpp"):
        rows.append({"label": "DPP nilai lain (11/12 × subtotal)", "value": fmt_rp(doc.get("dpp"))})
        label = f"PPN {rate}% × DPP"
    else:
        label = f"PPN {rate}%"
    if doc.get("ppn_mode") == "included":
        label += " (sudah termasuk)"
    rows.append({"label": label, "value": fmt_rp(doc.get(amount_key))})
    return rows


def fmt_address(val) -> str:
    """Normalisasi alamat yang bisa berupa string ATAU dict {address, city, ...}."""
    if not val:
        return ""
    if isinstance(val, dict):
        parts = [val.get("address"), val.get("city")]
        return ", ".join(str(p) for p in parts if p)
    return str(val)


def _ship_recipient(val):
    """Ambil nama & telp penerima dari shipping_address dict (jika ada)."""
    if isinstance(val, dict):
        return val.get("recipient_name") or "", val.get("phone") or ""
    return "", ""


# UAT 24 Okt (P3.1) — surat perintah kerja sampel: SATU surat per supplier (dipilih lewat ?supplier_id= di rute).
import contextvars as _cv
WO_SUPPLIER: "_cv.ContextVar[str]" = _cv.ContextVar("wo_supplier", default="")


async def _design_print_image(db, design_id: str):
    """PNG cetak desain (atau artwork versi ACC) → data URI untuk ditanam di surat."""
    import base64
    d = await db.design_gallery.find_one({"id": design_id}, {"_id": 0}) if design_id else None
    if not d:
        return None, None
    files = d.get("files") or []
    pick = next((f for f in files if f.get("kind") == "print_png"), None) or next(
        (f for f in files if (f.get("kind") or "artwork") == "artwork" and str(f.get("content_type", "")).startswith("image/")
         and int(f.get("version") or 1) == int(d.get("approved_version") or d.get("version") or 1)), None)
    if not pick:
        return d, None
    try:
        from services import design_gallery_service as _g
        data, ctype = await _g.get_file_bytes(d["id"], pick["id"])
        return d, {"src": f"data:{ctype or 'image/png'};base64,{base64.b64encode(data).decode()}",
                   "caption": f"{d.get('code', '')} · {pick.get('filename', '')}"
                              + (" · PNG cetak" if pick.get("kind") == "print_png" else " · artwork ACC (PNG cetak belum ada)")}
    except Exception:  # noqa: BLE001 — surat tetap terbit, gambarnya ditandai tidak tersedia
        return d, None


async def resolve_md_sample_work_order(doc, db) -> dict:
    from services.design_studio_service import SAMPLE_STATUS_LABEL
    sid = WO_SUPPLIER.get() or ""
    parts = doc.get("participants") or []
    part = next((p for p in parts if p.get("supplier_id") == sid), None) or (parts[0] if parts else {})
    sid = part.get("supplier_id") or sid
    sup = await db.suppliers.find_one({"id": sid}, {"_id": 0}) if sid else None
    rounds = [r for r in doc.get("rounds") or [] if r.get("supplier_id") == sid]
    types = list(doc.get("sample_types") or ([doc["sample_type"]] if doc.get("sample_type") else []))
    spec = await db.md_specs.find_one({"id": doc.get("spec_id")}, {"_id": 0}) if doc.get("spec_id") else {}
    spec = spec or {}
    tgt = spec.get("target") or {}
    due = max((r.get("due_date") or "" for r in rounds), default="") or doc.get("target_date") or ""
    idx = next((i for i, p in enumerate(parts, start=1) if p.get("supplier_id") == sid), 1)
    meta = [{"label": "No. sampel", "value": doc.get("number", "")},
            {"label": "Jenis", "value": " + ".join(t.capitalize() for t in types) or "—"},
            {"label": "Target selesai", "value": fmt_date(due) or "—"},
            {"label": "PIC MD", "value": doc.get("created_by", "") or "—"},
            {"label": "Spesifikasi", "value": spec.get("number", "") or "—"},
            {"label": "Kain dasar", "value": spec.get("base_fabric_name", "") or "—"}]
    if doc.get("special_order_number") or doc.get("so_number"):
        meta.append({"label": "Untuk pesanan", "value": doc.get("special_order_number") or doc.get("so_number")})
    if doc.get("color_batch_id"):
        meta.append({"label": "Kelompok labdip", "value": f"warna {doc.get('color_batch_index')} dari {doc.get('color_batch_size')}"})
    extra, swatches, images = [], [], []
    if "labdip" in types:
        ct = doc.get("color_target") or {}
        pantone = ct.get("pantone_code") or ""
        if not pantone and ct.get("color_id"):
            col = await db.color_library.find_one({"id": ct["color_id"]}, {"_id": 0}) or {}
            pantone = col.get("pantone_code") or (col.get("code") if (col.get("system") or "") in ("TCX", "TPX", "C", "U") else "")
        extra.append({"title": "LABDIP — warna target", "columns": [_col("code", "Kode KN"), _col("name", "Nama warna"),
                                                                      _col("pantone", "Pantone"), _col("hex", "Hex")],
                      "items": [{"code": ct.get("code") or "(baru — dibuat saat ACC)", "name": ct.get("name", ""),
                                 "pantone": pantone or "BELUM ADA — wajib diisi", "hex": ct.get("hex", "")}],
                      "note": "Cocokkan warna dengan kode Pantone di atas; kotak warna hanya acuan layar/cetak."})
        swatches.append({"hex": ct.get("hex") or "#ffffff", "label": ct.get("name") or "Warna target",
                         "sub": f"Pantone {pantone}" if pantone else "Pantone —"})
    if "handfeel" in types or "labdip" in types:
        keys = [("fabric_type", "Jenis kain"), ("construction", "Konstruksi"), ("gramasi", "Gramasi (gsm)"),
                ("lebar", "Lebar (cm)"), ("epi", "EPI"), ("ppi", "PPI"), ("yarn_warp", "Benang lusi"),
                ("yarn_weft", "Benang pakan"), ("yarn", "Benang"), ("composition", "Komposisi"), ("finishing", "Finishing")]
        rows = [{"k": lbl, "v": str(tgt.get(k))} for k, lbl in keys if tgt.get(k) not in (None, "", [], {})]
        if rows:
            extra.append({"title": ("HANDFEEL — konstruksi" if "handfeel" in types else "Konstruksi kain dasar"),
                          "columns": [_col("k", "Parameter"), _col("v", "Target")], "items": rows})
    if "proofing" in types:
        d, img = await _design_print_image(db, doc.get("design_id") or "")
        d = d or {}
        extra.append({"title": "PROOFING — desain", "columns": [_col("k", "Parameter"), _col("v", "Nilai")], "items": [
            {"k": "Kode desain", "v": doc.get("design_code") or d.get("code", "—")},
            {"k": "Judul", "v": doc.get("design_title") or d.get("title", "")},
            {"k": "Versi ACC", "v": str(d.get("approved_version") or doc.get("design_version") or "—")},
            {"k": "Repeat (cm)", "v": str(d.get("repeat_cm") or "—")},
            {"k": "Jumlah warna / screen", "v": f"{d.get('color_count') or '—'} / {d.get('screen_count') or '—'}"},
            {"k": "Kain dasar", "v": spec.get("base_fabric_name", "") or "—"}]})
        if img:
            images.append(img)
        else:
            extra.append({"title": "Gambar pattern", "columns": [_col("v", "Keterangan")],
                          "items": [{"v": "PNG cetak desain belum tersedia — minta desainer mengunggah berkas PNG cetak."}]})
    note = " · ".join(x for x in [doc.get("brief") or "", (rounds[-1].get("note") if rounds else "") or ""] if x)
    return {
        "title": "SURAT PERINTAH KERJA SAMPEL R&D",
        "number": f"{doc.get('number', '')}/{idx:02d}",
        "date": fmt_date(part.get("invited_at") or doc.get("sent_at") or doc.get("created_at")),
        "status": SAMPLE_STATUS_LABEL.get(doc.get("status", ""), doc.get("status", "")),
        "party_to": {"title": "Kepada (Supplier)", "name": part.get("supplier_name") or (sup or {}).get("name", "—"),
                     "address": fmt_address((sup or {}).get("address")), "phone": (sup or {}).get("phone", "")},
        "intro_text": (f"Mohon dikerjakan sampel {' + '.join(types)} untuk “{doc.get('title', '')}” sesuai rincian di bawah "
                       f"dan diserahkan paling lambat {fmt_date(due) or 'tanggal target'}."),
        "meta": meta, "extra_tables": extra, "swatches": swatches, "images": images,
        "notes": note,
        "signatures": [{"label": "Dibuat oleh (MD)", "name": doc.get("created_by", "")},
                       {"label": "Diterima (Supplier)", "name": ""}],
    }


def _col(key, label, align=""):
    return {"key": key, "label": label, "align": align}


# ═════════════════════════════════════════════════════════════════════════════
# FASE U — DUA SATUAN DI DOKUMEN CETAK (jumlah roll + ukuran)
# ═════════════════════════════════════════════════════════════════════════════
# Permintaan pemilik: *"catat roll dan yard/kg dan panel — jadi ada 2 satuan yang
# ditulis... dan ini seharusnya sudah ada di semuanya."*
#
# KEPUTUSAN PEMILIK 2026-08-20 — **DUA KOLOM TERPISAH** (`Roll` | `Jumlah`),
# BUKAN satu kolom gabungan "12 roll · 540 yard". Alasannya operasional: kolom
# yang berdiri sendiri bisa DIJUMLAH (di lembar kerja maupun dengan pensil di
# gudang) dan bisa dicocokkan langsung dengan hitungan fisik koli. Karena itu
# `core_utils.qty_dual()` tetap dipakai untuk KALIMAT satu baris (layar ringkas,
# baris total, notifikasi), sedangkan TABEL dokumen memakai dua kolom lewat
# helper di bawah. Keduanya membaca field yang sama (`qty_rolls` + `quantity`),
# jadi tetap satu sumber — yang berbeda hanya bentuk tampilannya.
#
# ATURAN "—" (sama dengan `<QtyDual/>` di layar; diuji POC U4)
# ----------------------------------------------------------
# `qty_rolls` yang BELUM PERNAH diisi (dokumen tahun lalu) TIDAK boleh dicetak
# sebagai "0". "0 roll" adalah PERNYATAAN bahwa tidak ada gulungan — pernyataan
# yang salah, dan salahnya tenang: manajer yang membuka dokumen lama akan
# menyimpulkan barangnya dikirim tanpa gulungan. Yang benar adalah "belum
# diketahui" → "—". Bedanya `None` vs `0` dijaga di lapisan data, bukan di sini.
def _rolls_cell(value) -> str:
    """Isi satu sel kolom **Roll** untuk PDF. `None`/"" → "—" (bukan "0")."""
    if value is None or value == "":
        return "—"
    try:
        return f"{int(float(value))}"
    except (TypeError, ValueError):
        return "—"


def _sum_rolls(values) -> str:
    """Total kolom Roll. Bila TAK SATU PUN baris menyebut roll → "—", bukan "0".

    Sengaja bukan `sum(... or 0)`: dokumen lama yang seluruh barisnya kosong akan
    menghasilkan total "0" yang terlihat seperti fakta, padahal artinya "tidak
    dicatat". Satu baris terisi sudah cukup untuk membuat totalnya bermakna.
    """
    nums = []
    for v in values:
        if v in (None, ""):
            continue
        try:
            nums.append(int(float(v)))
        except (TypeError, ValueError):
            continue
    return str(sum(nums)) if nums else "—"


# Label kolom dipakai berulang supaya judulnya TIDAK pernah berbeda antar dokumen
# (surat jalan bilang "Roll", faktur bilang "Gulungan" = dua nama untuk satu hal).
def _col_rolls(label: str = "Roll"):
    return _col("rolls", label, "num")


# ── Sales Order / Order Confirmation ─────────────────────────────────────────
async def resolve_sales_order(doc, db):
    items = []
    for i, it in enumerate(doc.get("items", []), 1):
        items.append({
            "no": i, "sku": it.get("sku", ""), "desc": it.get("product_name", ""),
            "rolls": _rolls_cell(it.get("qty_rolls")),
            "qty": f"{fmt_num(it.get('quantity', 0))} {it.get('unit', '')}",
            "price": fmt_rp(it.get("price")), "disc": f"{fmt_num(it.get('discount_percent', 0))}%",
            "total": fmt_rp(it.get("line_total", it.get("subtotal"))),
        })
    totals = []
    if doc.get("net_subtotal"):
        totals.append({"label": "Subtotal", "value": fmt_rp(doc.get("net_subtotal"))})
    totals.extend(_ppn_rows(doc))
    totals.append({"label": "Grand Total", "value": fmt_rp(doc.get("grand_total", doc.get("total_amount"))), "strong": True})
    return {
        "title": "Konfirmasi Pesanan Penjualan", "number": doc.get("number"),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("status"),
        "party_to": {"title": "Kepada Yth",
                     "name": (_ship_recipient(doc.get("shipping_address"))[0] or doc.get("customer_name")),
                     "address": fmt_address(doc.get("shipping_address")),
                     "phone": (_ship_recipient(doc.get("shipping_address"))[1] or doc.get("customer_phone", ""))},
        "meta": [
            {"label": "Sales", "value": doc.get("sales_name", "-")},
            {"label": "Termin Bayar", "value": doc.get("payment_term_name", "-")},
            {"label": "Kota Kirim", "value": doc.get("shipping_city", "-")},
            {"label": "Status Bayar", "value": doc.get("payment_status", "-")},
        ],
        "columns": [_col("no", "No", "num"), _col("sku", "SKU"), _col("desc", "Produk"),
                    _col_rolls(), _col("qty", "Jumlah", "num"), _col("price", "Harga", "num"),
                    _col("disc", "Disc", "num"), _col("total", "Subtotal", "num")],
        "items": items, "totals": totals,
        "terbilang": terbilang(doc.get("grand_total", doc.get("total_amount"))),
        "notes": doc.get("notes"),
        "signatures": [{"label": "Dibuat", "role": "Sales", "name": doc.get("sales_name") or doc.get("created_by")},
                       {"label": "Disetujui", "role": "Manager", "name": doc.get("approved_by")},
                       {"label": "Diterima", "role": "Customer", "name": ""}],
        "_amount": doc.get("grand_total", doc.get("total_amount")),
        # Trial 22 Okt (E10) — harga khusus masih menunggu/ditolak → cetakan bukan harga final.
        "watermark": ("HARGA BELUM FINAL" if any(
            p.get("type") == "special_price" and p.get("status") in ("pending", "rejected")
            for p in doc.get("pending_approvals") or []) else None),
    }


# ── Purchase Order (ke supplier) ─────────────────────────────────────────────
async def resolve_purchase_order(doc, db):
    sup = await db.suppliers.find_one({"id": doc.get("supplier_id")}, {"_id": 0}) or {}
    items = []
    for i, it in enumerate(doc.get("items", []), 1):
        items.append({
            "no": i, "sku": it.get("sku", ""), "desc": it.get("product_name", ""),
            "rolls": _rolls_cell(it.get("qty_rolls")),
            "qty": f"{fmt_num(it.get('quantity', 0))} {it.get('unit', '')}",
            "price": fmt_rp(it.get("price")), "total": fmt_rp(it.get("line_total", it.get("subtotal"))),
        })
    totals = []
    if doc.get("net_subtotal"):
        totals.append({"label": "Subtotal", "value": fmt_rp(doc.get("net_subtotal"))})
    totals.extend(_ppn_rows(doc))
    totals.append({"label": "Grand Total", "value": fmt_rp(doc.get("grand_total", doc.get("total_amount"))), "strong": True})
    return {
        "title": "Pesanan Pembelian", "number": doc.get("po_number"),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("status"),
        "party_to": {"title": "Kepada Supplier", "name": doc.get("supplier_name") or sup.get("name"),
                     "address": sup.get("address"), "phone": sup.get("phone") or doc.get("supplier_contact")},
        "meta": [
            {"label": "Tgl Kirim Diharap", "value": fmt_date(doc.get("expected_delivery_date"))},
            {"label": "NPWP Supplier", "value": sup.get("npwp", "-")},
            {"label": "Status Bayar", "value": doc.get("payment_status", "-")},
            {"label": "Dibuat oleh", "value": doc.get("created_by", "-")},
        ],
        "columns": [_col("no", "No", "num"), _col("sku", "SKU"), _col("desc", "Produk"),
                    _col_rolls("Roll Dipesan"), _col("qty", "Jumlah", "num"),
                    _col("price", "Harga", "num"), _col("total", "Subtotal", "num")],
        "items": items, "totals": totals,
        "terbilang": terbilang(doc.get("grand_total", doc.get("total_amount"))),
        "notes": doc.get("notes"),
        "signatures": [{"label": "Dibuat", "role": "Purchasing", "name": doc.get("created_by")},
                       {"label": "Disetujui", "role": "Manager", "name": ""},
                       {"label": "Supplier", "role": "", "name": ""}],
        "_amount": doc.get("grand_total", doc.get("total_amount")),
    }


# ── Quotation / Penawaran (dari sales_orders draft/quotation atau rfqs) ───────
async def resolve_quotation(doc, db):
    ctx = await resolve_sales_order(doc, db)
    ctx["title"] = "Sales Quotation / Penawaran Harga"
    ctx["signatures"] = [{"label": "Hormat Kami", "role": "Sales", "name": doc.get("sales_name") or doc.get("created_by")},
                         {"label": "Menyetujui", "role": "Customer", "name": ""}]
    return ctx


# ── Vendor Bill / Tagihan Supplier ───────────────────────────────────────────
async def resolve_vendor_bill(doc, db):
    sup = await db.suppliers.find_one({"id": doc.get("supplier_id")}, {"_id": 0}) or {}
    items = [{
        "no": 1, "desc": f"Tagihan atas {doc.get('bill_type', 'pembelian')} "
                         f"{doc.get('po_id') or doc.get('makloon_order_id') or ''}".strip(),
        "ref": doc.get("supplier_invoice_no", "-"),
        "net": fmt_rp(doc.get("net_amount")), "ppn": fmt_rp(doc.get("ppn_amount")),
        "total": fmt_rp(doc.get("grand_total")),
    }]
    return {
        "title": "Vendor Bill / Tagihan", "number": doc.get("bill_number"),
        "date": fmt_date(doc.get("bill_date") or doc.get("created_at")), "status": doc.get("status"),
        "party_to": {"title": "Supplier", "name": doc.get("supplier_name") or sup.get("name"),
                     "address": sup.get("address"), "phone": sup.get("phone")},
        "meta": [
            {"label": "No. Faktur Supplier", "value": doc.get("supplier_invoice_no", "-")},
            {"label": "Tipe", "value": doc.get("bill_type", "-")},
            {"label": "Ref PO", "value": doc.get("po_id", "-")},
            {"label": "NPWP", "value": sup.get("npwp", "-")},
        ],
        "columns": [_col("no", "No", "num"), _col("desc", "Uraian"), _col("ref", "Ref"),
                    _col("net", "DPP", "num"), _col("ppn", "PPN", "num"), _col("total", "Total", "num")],
        "items": items,
        "totals": [{"label": "DPP", "value": fmt_rp(doc.get("net_amount"))},
                   {"label": "PPN", "value": fmt_rp(doc.get("ppn_amount"))},
                   {"label": "Grand Total", "value": fmt_rp(doc.get("grand_total")), "strong": True}],
        "terbilang": terbilang(doc.get("grand_total")),
        "signatures": [{"label": "Diperiksa", "role": "Accounting", "name": ""},
                       {"label": "Disetujui", "role": "Manager", "name": ""}],
        "_amount": doc.get("grand_total"),
    }


# ── FASE G-7 — Tanda Terima Kontrabon (bukti tukar faktur untuk supplier) ────
async def resolve_contra_bon(doc, db):
    """Tanda terima yang DITANDATANGANI supplier: seluruh faktur & PO yang ditukar,
    potongan yang disepakati, dan nilai bersih yang akan dibayar."""
    sup = await db.suppliers.find_one({"id": doc.get("supplier_id")}, {"_id": 0}) or {}
    items = []
    for i, b in enumerate(doc.get("bills") or [], 1):
        items.append({
            "no": i,
            "inv": b.get("supplier_invoice_no") or b.get("bill_number", "-"),
            "bill": b.get("bill_number", "-"),
            "po": b.get("po_number", "-"),
            "date": fmt_date(b.get("bill_date")),
            "amount": fmt_rp(b.get("applied_amount")),
        })
    n = len(items)
    for j, d in enumerate(doc.get("deductions") or [], 1):
        items.append({
            "no": n + j, "inv": f"POTONGAN — {d.get('label', '')}",
            "bill": d.get("ref_number", "-"), "po": "-", "date": "",
            "amount": "(" + fmt_rp(d.get("amount")) + ")",
        })
    totals = doc.get("totals") or {}
    return {
        "title": "Tanda Terima Kontrabon", "number": doc.get("number"),
        "date": fmt_date(doc.get("cycle_date") or doc.get("created_at")),
        "status": doc.get("status"),
        "party_to": {"title": "Supplier", "name": doc.get("supplier_name") or sup.get("name"),
                     "address": sup.get("address"), "phone": sup.get("phone")},
        "meta": [
            {"label": "Tanggal Tukar Faktur", "value": fmt_date(doc.get("cycle_date"))},
            {"label": "Jatuh Tempo Bayar", "value": fmt_date(doc.get("due_date"))},
            {"label": "Jumlah Faktur", "value": str(len(doc.get("bills") or []))},
            {"label": "Termin", "value": doc.get("payment_term_code", "-")},
            {"label": "NPWP", "value": sup.get("npwp", "-")},
            {"label": "Penyerah dari Supplier", "value": doc.get("supplier_pic", "-")},
        ],
        "columns": [_col("no", "No", "num"), _col("inv", "No. Faktur Supplier"),
                    _col("bill", "No. Tagihan"), _col("po", "No. PO"),
                    _col("date", "Tanggal"), _col("amount", "Nilai", "num")],
        "items": items,
        "totals": [
            {"label": "Total Faktur", "value": fmt_rp(totals.get("bills_total"))},
            {"label": "Total Potongan", "value": fmt_rp(totals.get("deductions_total"))},
            {"label": "Nilai Bersih Dibayar", "value": fmt_rp(totals.get("net_payable")),
             "strong": True},
        ],
        "terbilang": terbilang(totals.get("net_payable")),
        "signatures": [{"label": "Diterima oleh", "role": "Accounting", "name": ""},
                       {"label": "Diserahkan oleh", "role": "Supplier",
                        "name": doc.get("supplier_pic", "")}],
        "_amount": totals.get("net_payable"),
    }


# ── Kwitansi / AR Receipt (Official Receipt) ──────────────────────────────────
async def resolve_ar_receipt(doc, db):
    allocs = doc.get("allocations", []) or []
    items = [{"no": i, "inv": a.get("invoice_number", a.get("order_number", a.get("target_id", "-"))),
              "amount": fmt_rp(a.get("amount", a.get("applied", 0)))} for i, a in enumerate(allocs, 1)]
    return {
        "title": "Kwitansi / Official Receipt", "number": doc.get("number"),
        "date": fmt_date(doc.get("receipt_date") or doc.get("created_at")), "status": doc.get("status"),
        "party_to": {"title": "Telah diterima dari", "name": doc.get("customer_name")},
        "meta": [
            {"label": "Metode", "value": doc.get("method", "-")},
            {"label": "Jumlah Diterima", "value": fmt_rp(doc.get("amount"))},
            {"label": "Dialokasikan", "value": fmt_rp(doc.get("applied_total"))},
            {"label": "Sisa/Deposit", "value": fmt_rp(doc.get("unapplied_amount"))},
        ],
        "columns": [_col("no", "No", "num"), _col("inv", "Untuk Pembayaran"), _col("amount", "Jumlah", "num")] if items else [],
        "items": items,
        "totals": [{"label": "Total Diterima", "value": fmt_rp(doc.get("amount")), "strong": True}],
        "terbilang": terbilang(doc.get("amount")),
        "notes": doc.get("notes"),
        "signatures": [{"label": "Penyetor", "role": doc.get("customer_name", ""), "name": ""},
                       {"label": "Penerima", "role": "Keuangan", "name": doc.get("created_by_name")}],
        "_amount": doc.get("amount"),
    }


# ── Nota Retur Penjualan ─────────────────────────────────────────────────────
async def resolve_sales_return(doc, db):
    items = [{"no": i, "desc": it.get("product_name", ""),
              "rolls": _rolls_cell(it.get("qty_rolls")),
              "qty": f"{fmt_num(it.get('quantity_returned', 0))} {it.get('unit', '')}",
              "reason": it.get("reason", "-"), "cond": it.get("condition", "-")}
             for i, it in enumerate(doc.get("items", []), 1)]
    return {
        "title": "Nota Retur Penjualan", "number": doc.get("number"),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("status"),
        "party_to": {"title": "Pelanggan", "name": doc.get("customer_name")},
        "meta": [{"label": "Ref Pesanan", "value": doc.get("order_number", "-")},
                 {"label": "Tipe Retur", "value": doc.get("return_type", "-")},
                 {"label": "Stok Disesuaikan", "value": "Ya" if doc.get("stock_adjusted") else "Belum"},
                 {"label": "Dibuat oleh", "value": doc.get("created_by", "-")}],
        "columns": [_col("no", "No", "num"), _col("desc", "Produk"),
                    _col_rolls("Roll Retur"), _col("qty", "Jumlah Retur", "num"),
                    _col("reason", "Alasan"), _col("cond", "Kondisi", "ctr")],
        "items": items, "notes": doc.get("notes"),
        "signatures": [{"label": "Dibuat", "role": "Sales", "name": doc.get("created_by")},
                       {"label": "Disetujui", "role": "Manager", "name": doc.get("approved_by")},
                       {"label": "Gudang", "role": "", "name": ""}],
        "_amount": 0,
    }


# ── Nota Retur Pembelian ─────────────────────────────────────────────────────
async def resolve_purchase_return(doc, db):
    items = [{"no": i, "desc": it.get("product_name", it.get("sku", "")),
              "rolls": _rolls_cell(it.get("qty_rolls")),
              "qty": f"{fmt_num(it.get('quantity', it.get('quantity_returned', 0)))} {it.get('unit', '')}",
              "reason": it.get("reason", "-")}
             for i, it in enumerate(doc.get("items", []), 1)]
    return {
        "title": "Nota Retur Pembelian", "number": doc.get("number", doc.get("return_number")),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("status"),
        "party_to": {"title": "Supplier", "name": doc.get("supplier_name")},
        "meta": [{"label": "Ref PO", "value": doc.get("po_number", "-")},
                 {"label": "Dibuat oleh", "value": doc.get("created_by", "-")}],
        "columns": [_col("no", "No", "num"), _col("desc", "Produk"),
                    _col_rolls("Roll Retur"), _col("qty", "Jumlah Retur", "num"),
                    _col("reason", "Alasan")],
        "items": items, "notes": doc.get("notes"),
        "signatures": [{"label": "Dibuat", "role": "Purchasing", "name": doc.get("created_by")},
                       {"label": "Disetujui", "role": "Manager", "name": ""}],
        "_amount": 0,
    }


# ── SPK Makloon / Work Order ─────────────────────────────────────────────────
def _mko_partial_tables(steps):
    """Riwayat kiriman bertahap per langkah (ditahan / digabung / dibatalkan)."""
    rows = []
    for s in steps:
        unit = s.get("output_unit") or ""
        for r in s.get("partial_receipts") or []:
            st = f"Digabung ke {r.get('absorbed_by') or 'penerimaan akhir'}" if r.get("posted") else "Ditahan"
            rows.append((s, r, unit, st))
        for r in s.get("cancelled_partials") or []:
            rows.append((s, r, unit, f"Dibatalkan — {r.get('cancel_reason', '')} ({r.get('cancelled_by', '')})"))
    if not rows:
        return []
    items = [{"step": f"#{s.get('seq')}", "grn": r.get("grn_number") or r.get("grn_id", ""),
              "dn": r.get("dn_number") or "-", "qty": f"{fmt_num(float(r.get('out_qty') or 0))} {unit}",
              "rolls": str(len(r.get("rolls") or [])), "by": f"{r.get('by', '')} · {fmt_date(r.get('at'))}",
              "status": st} for s, r, unit, st in rows]
    notes = [f"Langkah #{s.get('seq')}: penerimaan akhir {a.get('final_ref')} menyerap {a.get('count')} kiriman sebagian "
             f"— {fmt_num(a.get('partial_qty'))} + {fmt_num(a.get('final_qty'))} = {fmt_num(a.get('total_qty'))} {s.get('output_unit') or ''}."
             for s in steps for a in [s.get("partial_absorption")] if a]
    return [{"title": "Riwayat Kiriman Bertahap", "note": " ".join(notes),
             "columns": [_col("step", "Langkah"), _col("grn", "Kedatangan"), _col("dn", "SJ"),
                         _col("qty", "Qty", "num"), _col("rolls", "Roll", "num"),
                         _col("by", "Diterima"), _col("status", "Status")],
             "items": items}]


MKO_MODE_LABEL = {"process_only": "Proses saja (bahan dari stok)", "buy_process": "Beli bahan + proses"}


def _process_label(step) -> str:
    """G5-13 — nama proses langkah SPK. Langkah baru hanya menyimpan `process_type` ("printing") sehingga kolom
    PROSES dulu tercetak "-"; labelnya diambil dari registri domain (sumber yang sama dengan layar)."""
    name = step.get("process_name") or step.get("name") or step.get("process") or step.get("stage_label")
    if name:
        return str(name)
    pt = str(step.get("process_type") or "").strip()
    if not pt:
        return "-"
    try:
        import domain_registry as dr
        return next((v.get("label") for v in dr.enum_items("process_type") if v.get("value") == pt), None) \
            or pt.replace("_", " ").capitalize()
    except Exception:  # noqa: BLE001 — registri gagal dimuat ≠ surat gagal terbit
        return pt.replace("_", " ").capitalize()


async def resolve_makloon_spk(doc, db):
    steps = doc.get("steps", []) or []
    items = [{"no": i, "proc": _process_label(s),
              "wh": s.get("makloon_name") or s.get("subcon_name") or s.get("vendor_name") or "-",
              "rolls": _rolls_cell(s.get("qty_rolls")),
              "rolls_out": _rolls_cell(s.get("qty_rolls_out")),
              "qty": f"{fmt_num(s.get('input_qty', s.get('qty', 0)))} {s.get('input_unit') or ''}".strip(),
              "tariff": fmt_rp(s.get("tariff", s.get("cost", 0)))}
             for i, s in enumerate(steps, 1)]
    mode = doc.get("mode") or ""
    return {
        "title": "SPK Makloon / Work Order", "number": doc.get("mko_number"),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("status"),
        "meta": [{"label": "Material", "value": f"{doc.get('material_name', '-')} ({fmt_num(doc.get('material_qty', 0))} {doc.get('material_unit', '')})"},
                 {"label": "Output", "value": doc.get("final_output_name", "-")},
                 # G5-13 — dulu "Mode process_only" (kode mentah) tercetak di surat untuk mitra.
                 {"label": "Jenis order", "value": MKO_MODE_LABEL.get(mode) or (mode.replace("_", " ").capitalize() or "-")},
                 {"label": "Dibuat oleh", "value": doc.get("created_by") or doc.get("created_by_name") or "-"}],
        "columns": [_col("no", "No", "num"), _col("proc", "Proses"), _col("wh", "Pelaksana"),
                    _col_rolls("Roll Masuk"), _col("qty", "Jumlah Masuk", "num"),
                    _col("rolls_out", "Roll Keluar", "num"), _col("tariff", "Tarif", "num")],
        "items": items, "notes": doc.get("notes"),
        "extra_tables": _mko_partial_tables(steps),
        "signatures": [{"label": "Dibuat", "role": "PPIC", "name": doc.get("created_by")},
                       {"label": "Disetujui", "role": "Manager", "name": ""},
                       {"label": "Pelaksana", "role": "Makloon", "name": ""}],
        "_amount": (doc.get("costing") or {}).get("total_cost", 0),
    }


# ── Special Order ────────────────────────────────────────────────────────────
async def resolve_special_order(doc, db):
    ci = doc.get("custom_item", {}) or {}
    items = [{"no": 1, "desc": ci.get("name", ci.get("description", "Custom item")),
              "spec": ci.get("spec", ci.get("specification", "-")),
              "qty": f"{fmt_num(ci.get('quantity', 1))} {ci.get('unit', '')}", "total": fmt_rp(doc.get("total_amount"))}]
    return {
        "title": "Pesanan Khusus", "number": doc.get("number"),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("status"),
        "party_to": {"title": "Pelanggan", "name": doc.get("customer_name"),
                     "address": fmt_address(doc.get("shipping_address")), "phone": doc.get("customer_phone")},
        "meta": [{"label": "Tipe", "value": doc.get("type", "-")},
                 {"label": "Email", "value": doc.get("customer_email", "-")},
                 {"label": "Estimasi Kirim", "value": fmt_date(doc.get("expected_delivery"))},
                 {"label": "Dibuat oleh", "value": doc.get("created_by", "-")}],
        "columns": [_col("no", "No", "num"), _col("desc", "Item"), _col("spec", "Spesifikasi"),
                    _col("qty", "Qty", "num"), _col("total", "Nilai", "num")],
        "items": items,
        "totals": [{"label": "Total", "value": fmt_rp(doc.get("total_amount")), "strong": True}],
        "terbilang": terbilang(doc.get("total_amount")), "notes": doc.get("notes"),
        "signatures": [{"label": "Dibuat", "role": "Sales", "name": doc.get("created_by")},
                       {"label": "Disetujui", "role": "Manager", "name": ""},
                       {"label": "Pelanggan", "role": "", "name": ""}],
        "_amount": doc.get("total_amount"),
    }


# ── Surat Jalan Transfer antar-gudang / inter-company ────────────────────────
async def resolve_transfer(doc, db):
    items = [{"no": i, "sku": it.get("sku", ""), "desc": it.get("product_name", ""),
              "rolls": _rolls_cell(it.get("qty_rolls")),
              "qty": f"{fmt_num(it.get('quantity', it.get('qty', 0)))} {it.get('unit', '')}"}
             for i, it in enumerate(doc.get("items", []), 1)]
    is_ic = doc.get("transfer_kind") == "inter_entity"
    from_name = doc.get("from_warehouse_name") or doc.get("source_warehouse_name")
    to_name = doc.get("to_warehouse_name") or doc.get("dest_warehouse_name")
    if not from_name:
        wid = doc.get("source_warehouse_id") or doc.get("from_warehouse_id")
        if wid:
            w = await db.warehouses.find_one({"id": wid}, {"_id": 0, "name": 1})
            from_name = (w or {}).get("name")
    if not to_name:
        wid = doc.get("dest_warehouse_id") or doc.get("to_warehouse_id")
        if wid:
            w = await db.warehouses.find_one({"id": wid}, {"_id": 0, "name": 1})
            to_name = (w or {}).get("name")
    from_name = from_name or doc.get("from_warehouse_id") or "-"
    to_name = to_name or doc.get("to_warehouse_id") or "-"
    # UAT 24 Okt (audit UI tahap 2, G5-12) — transfer antar-PT dulu mencetak NAMA GUDANG di baris "PT Asal/PT
    # Tujuan" (keduanya "Jakarta · Gudang Sukacita" untuk Sukacita → Kanda Fabric) dan "Dibuat oleh -" karena
    # pengajunya tersimpan di `requested_by`. Kini PT dari entitas sumber/tujuan, gudang di baris sendiri.
    creator = doc.get("created_by") or doc.get("requested_by") or doc.get("created_by_name") or "-"
    if is_ic:
        async def _pt(eid):
            if not eid:
                return "-"
            e = await db.business_entities.find_one({"id": eid}, {"_id": 0, "legal_name": 1, "short_name": 1})
            return (e or {}).get("legal_name") or (e or {}).get("short_name") or "-"
        meta = [{"label": "PT Asal", "value": await _pt(doc.get("source_entity_id"))},
                {"label": "Gudang Asal", "value": from_name},
                {"label": "PT Tujuan", "value": await _pt(doc.get("dest_entity_id"))},
                {"label": "Gudang Tujuan", "value": to_name},
                {"label": "Dibuat oleh", "value": creator}]
    else:
        meta = [{"label": "Dari Gudang", "value": from_name},
                {"label": "Ke Gudang", "value": to_name},
                {"label": "Dibuat oleh", "value": creator}]
    return {
        "title": "Surat Jalan Transfer Antar-PT" if is_ic else "Surat Jalan Transfer",
        "number": doc.get("number") or doc.get("transfer_number") or doc.get("code"),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("status"),
        "meta": meta,
        "columns": [_col("no", "No", "num"), _col("sku", "SKU"), _col("desc", "Produk"),
                    _col_rolls(), _col("qty", "Jumlah", "num")],
        "items": items,
        "totals": [{"label": "Total Roll",
                    "value": _sum_rolls([it.get("qty_rolls") for it in doc.get("items", [])])},
                   {"label": "Total Kuantitas",
                    "value": _sum_by_unit([(it.get("quantity", it.get("qty", 0)), it.get("unit", ""))
                                           for it in doc.get("items", [])]), "strong": True}],
        "notes": doc.get("notes"),
        "signatures": [{"label": "Pengirim", "role": "Gudang Asal", "name": ""},
                       {"label": "Pengangkut", "role": "Driver", "name": ""},
                       {"label": "Penerima", "role": "Gudang Tujuan", "name": ""}],
        "_amount": 0,
    }


# ── Laporan Stock Opname / Cycle Count ───────────────────────────────────────
async def resolve_cycle_count(doc, db):
    lines = doc.get("lines", doc.get("items", [])) or []

    def _sys(ln):
        return ln.get("system_qty", ln.get("expected_qty", 0)) or 0

    def _cnt(ln):
        return ln.get("counted_qty", ln.get("actual_qty", 0)) or 0

    items = [{"no": i, "sku": ln.get("sku", ""), "desc": ln.get("product_name", ""),
              "sys": f"{fmt_num(_sys(ln))}", "count": f"{fmt_num(_cnt(ln))}",
              "diff": f"{fmt_num((_cnt(ln) - _sys(ln)))}"}
             for i, ln in enumerate(lines, 1)]
    return {
        "title": "Laporan Stock Opname",
        "number": doc.get("number") or doc.get("session_number") or doc.get("name") or doc.get("id", "-"),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("status"),
        "meta": [{"label": "Gudang", "value": doc.get("warehouse_name", doc.get("warehouse_id", "-"))},
                 {"label": "Petugas", "value": doc.get("created_by", "-")}],
        "columns": [_col("no", "No", "num"), _col("sku", "SKU"), _col("desc", "Produk"),
                    _col("sys", "Sistem", "num"), _col("count", "Fisik", "num"), _col("diff", "Selisih", "num")],
        "items": items, "notes": doc.get("notes"),
        "signatures": [{"label": "Penghitung", "role": "Gudang", "name": doc.get("created_by")},
                       {"label": "Disetujui", "role": "Manager", "name": ""}],
        "_amount": 0,
    }


# ═══════════════════════════════════════════════════════════════════════════
# GAP DOCUMENTS — dokumen operasional gudang + finance (ditambah S#2026-07-21)
# ═══════════════════════════════════════════════════════════════════════════

def _sum_by_unit(pairs) -> str:
    """pairs: list[(qty, unit)] → 'Rp gabungan per satuan', mis. '150 yard + 30 kg'."""
    agg: dict = {}
    for q, u in pairs:
        u = (u or "").strip()
        agg[u] = agg.get(u, 0.0) + float(q or 0)
    return " + ".join(f"{fmt_num(v)} {u}".strip() for u, v in agg.items() if v) or "0"


async def _wms_scan_rows(db, match: dict, flow_type: str):
    """Ratakan scan_log dari wms_tasks → satu baris per roll (fallback: satu baris per task).

    Return (rows, tasks). rows: [{product_name, sku, roll_id, lot, bin_id, qty, unit, warehouse_name}].
    """
    tasks = await db.wms_tasks.find({**match, "flow_type": flow_type}, {"_id": 0}).to_list(2000)
    rows = []
    for t in tasks:
        logs = t.get("scan_log") or []
        if logs:
            for lg in logs:
                rows.append({
                    "product_name": t.get("product_name", ""), "sku": t.get("sku", ""),
                    "roll_id": lg.get("roll_id") or "-", "lot": lg.get("lot") or t.get("lot") or "-",
                    "bin_id": lg.get("bin_id") or t.get("bin_id") or "-",
                    "qty": float(lg.get("actual_qty") or 0), "unit": t.get("unit", ""),
                    "warehouse_name": t.get("warehouse_name", ""),
                })
        else:
            rows.append({
                "product_name": t.get("product_name", ""), "sku": t.get("sku", ""),
                "roll_id": "-", "lot": t.get("lot") or "-", "bin_id": t.get("bin_id") or "-",
                "qty": float(t.get("picked_qty") or t.get("received_qty") or t.get("quantity") or 0),
                "unit": t.get("unit", ""), "warehouse_name": t.get("warehouse_name", ""),
            })
    return rows, tasks


async def _product_index(db, skus):
    """Map sku → {color, motif, category} untuk pengayaan kolom (warna/kode)."""
    skus = list({s for s in skus if s})
    if not skus:
        return {}
    prods = await db.products.find({"sku": {"$in": skus}}, {"_id": 0, "sku": 1, "color": 1, "motif": 1, "category": 1}).to_list(500)
    return {p["sku"]: p for p in prods}


_KETENTUAN_SJ = (
    "1) Periksa jumlah, warna, dan kondisi kain saat penerimaan. "
    "2) Barang yang sudah dipotong tidak dapat diklaim/retur. "
    "3) Klaim/retur maksimal 7 hari sejak barang diterima disertai surat jalan ini."
)


async def _sj_number(db, order):
    shp = await db.shipments.find_one({"order_id": order.get("id")}, {"_id": 0, "shipment_no": 1})
    if shp and shp.get("shipment_no"):
        return shp["shipment_no"]
    num = (order.get("number") or "").replace("SO-", "")
    return f"SJ-{num}" if num else (order.get("number") or order.get("id"))


# ── Surat Pengambilan Barang (Picking List) — dari sales_orders ──────────────
async def resolve_picking_list(doc, db):
    rows, _ = await _wms_scan_rows(db, {"order_id": doc.get("id")}, "outbound")
    items = [{"no": i, "sku": r["sku"], "desc": r["product_name"], "bin": r["bin_id"],
              "roll": r["roll_id"], "lot": r["lot"], "qty": f"{fmt_num(r['qty'])} {r['unit']}"}
             for i, r in enumerate(rows, 1)]
    wh = next((r["warehouse_name"] for r in rows if r["warehouse_name"]), "-")
    total = _sum_by_unit([(r["qty"], r["unit"]) for r in rows])
    return {
        "title": "Surat Pengambilan Barang", "number": doc.get("number"),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("status"),
        "party_to": {"title": "Untuk Pesanan", "name": doc.get("customer_name"),
                     "address": fmt_address(doc.get("shipping_address"))},
        "meta": [{"label": "No. Pesanan Penjualan", "value": doc.get("number", "-")},
                 {"label": "Gudang", "value": wh},
                 {"label": "Pelanggan", "value": doc.get("customer_name", "-")},
                 {"label": "Dicetak", "value": fmt_now()}],
        "columns": [_col("no", "No", "num"), _col("sku", "SKU"), _col("desc", "Nama Barang"),
                    _col("bin", "Lokasi Bin", "ctr"), _col("roll", "Roll ID", "ctr"),
                    _col("lot", "Lot", "ctr"), _col("qty", "Qty Ambil", "num")],
        "items": items,
        "totals": [{"label": "Jumlah Baris", "value": str(len(rows))},
                   {"label": "Total Kuantitas", "value": total, "strong": True}],
        "notes": (doc.get("picking_notes") or "Ambil sesuai lokasi bin & roll ID. Scan setiap roll saat pengambilan untuk validasi.") if items else "⚠ Belum ada alokasi pengambilan (outbound) untuk order ini. Konfirmasi & proses picking di gudang terlebih dahulu.",
        "signatures": [{"label": "Disiapkan", "role": "Picker Gudang", "name": ""},
                       {"label": "Diperiksa", "role": "Supervisor Gudang", "name": ""}],
        "_amount": 0,
    }


# ── Packing List — dari sales_orders ─────────────────────────────────────────
async def resolve_packing_list(doc, db):
    rows, _ = await _wms_scan_rows(db, {"order_id": doc.get("id")}, "outbound")
    agg: dict = {}
    for r in rows:
        a = agg.setdefault(r["sku"], {"product_name": r["product_name"], "sku": r["sku"],
                                      "rolls": 0, "qty": 0.0, "unit": r["unit"]})
        a["rolls"] += 1
        a["qty"] += r["qty"]
    items = [{"no": i, "sku": a["sku"], "desc": a["product_name"], "rolls": str(a["rolls"]),
              "qty": f"{fmt_num(a['qty'])} {a['unit']}"} for i, a in enumerate(agg.values(), 1)]
    total_rolls = sum(a["rolls"] for a in agg.values())
    total = _sum_by_unit([(a["qty"], a["unit"]) for a in agg.values()])
    shp = await db.shipments.find_one({"order_id": doc.get("id")}, {"_id": 0, "shipment_no": 1})
    return {
        "title": "Daftar Kemasan", "number": doc.get("number"),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("status"),
        "party_to": {"title": "Kepada", "name": doc.get("customer_name"),
                     "address": fmt_address(doc.get("shipping_address")),
                     "phone": _ship_recipient(doc.get("shipping_address"))[1]},
        "meta": [{"label": "No. Pesanan Penjualan", "value": doc.get("number", "-")},
                 {"label": "No. Surat Jalan", "value": (shp or {}).get("shipment_no", "-")},
                 {"label": "Pelanggan", "value": doc.get("customer_name", "-")},
                 {"label": "Dicetak", "value": fmt_now()}],
        "columns": [_col("no", "No", "num"), _col("sku", "SKU"), _col("desc", "Nama Barang"),
                    _col_rolls(), _col("qty", "Jumlah", "num")],
        "items": items,
        "totals": [{"label": "Total Koli/Roll", "value": str(total_rolls)},
                   {"label": "Total Kuantitas", "value": total, "strong": True}],
        "notes": "Periksa jumlah koli, kelengkapan, dan kondisi kemasan saat serah terima ke ekspedisi." if items else "⚠ Belum ada barang yang dikemas untuk order ini.",
        "signatures": [{"label": "Dikemas", "role": "Packer", "name": ""},
                       {"label": "Diperiksa", "role": "QC Gudang", "name": ""},
                       {"label": "Diterima", "role": "Ekspedisi", "name": ""}],
        "_amount": 0,
    }


# ── Surat Jalan Pengiriman (gaya tekstil klasik, multi-item + per-roll) ──────
async def resolve_delivery_note(doc, db):
    rows, _ = await _wms_scan_rows(db, {"order_id": doc.get("id")}, "outbound")
    pidx = await _product_index(db, [r["sku"] for r in rows])
    items = []
    for i, r in enumerate(rows, 1):
        p = pidx.get(r["sku"], {})
        items.append({"no": i, "nama": r["product_name"], "warna": p.get("color", "-"),
                      "kode": r["sku"], "roll": r["roll_id"], "jumlah": f"{fmt_num(r['qty'])} {r['unit']}"})
    total_rolls = len(rows)
    total = _sum_by_unit([(r["qty"], r["unit"]) for r in rows])
    rname, rphone = _ship_recipient(doc.get("shipping_address"))
    return {
        "title": "Surat Jalan", "number": await _sj_number(db, doc),
        # CX-10 — tanggal SJ = tanggal kirim (stabil untuk hash versi), bukan tanggal cetak
        "date": fmt_date(doc.get("dispatched_at")) or fmt_date(datetime.now(_WIB).isoformat()), "status": doc.get("status"),
        "party_to": {"title": "Kepada Yth", "name": (rname or doc.get("customer_name")),
                     "address": fmt_address(doc.get("shipping_address")),
                     "phone": (rphone or doc.get("customer_phone", ""))},
        "meta": [{"label": "No. Pesanan Penjualan", "value": doc.get("number", "-")},
                 {"label": "Sales", "value": doc.get("sales_name", doc.get("created_by", "-"))},
                 {"label": "Ekspedisi / Kendaraan", "value": doc.get("expedition") or doc.get("vehicle") or "-"},
                 {"label": "Dicetak", "value": fmt_now(seconds=True)}],
        "columns": [_col("no", "No", "num"), _col("nama", "Nama Kain"), _col("warna", "Warna"),
                    _col("kode", "Kode Brg"), _col("roll", "Roll", "ctr"), _col("jumlah", "Jumlah", "num")],
        "items": items,
        "totals": [{"label": "Total Roll", "value": str(total_rolls)},
                   {"label": "Total Kuantitas", "value": total, "strong": True}],
        "notes": _KETENTUAN_SJ if items else "⚠ Belum ada barang yang dikirim untuk order ini. Surat jalan akan terisi otomatis setelah proses pengiriman (outbound) di gudang.",
        "signatures": [{"label": "Penerima", "role": "Customer / Kurir", "name": ""},
                       {"label": "Mengetahui", "role": "Supervisor", "name": ""},
                       {"label": "Dibuat Oleh", "role": "Gudang", "name": doc.get("created_by", "")}],
        "_amount": 0,
    }


# ── Daftar Put-Away — dari purchase_orders (barang diterima → penempatan bin) ─
async def resolve_put_away(doc, db):
    rows, tasks = await _wms_scan_rows(db, {"po_id": doc.get("id")}, "inbound")
    items = [{"no": i, "sku": r["sku"], "desc": r["product_name"], "roll": r["roll_id"],
              "lot": r["lot"], "bin": r["bin_id"], "qty": f"{fmt_num(r['qty'])} {r['unit']}"}
             for i, r in enumerate(rows, 1)]
    wh = next((r["warehouse_name"] for r in rows if r["warehouse_name"]), "-")
    total = _sum_by_unit([(r["qty"], r["unit"]) for r in rows])
    return {
        "title": "Daftar Put-Away (Penempatan Barang)", "number": doc.get("po_number"),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("status"),
        "meta": [{"label": "No. Pesanan Pembelian", "value": doc.get("po_number", "-")},
                 {"label": "Supplier", "value": doc.get("supplier_name", "-")},
                 {"label": "Gudang", "value": wh},
                 {"label": "Dicetak", "value": fmt_now()}],
        "columns": [_col("no", "No", "num"), _col("sku", "SKU"), _col("desc", "Nama Barang"),
                    _col("roll", "Roll ID", "ctr"), _col("lot", "Lot", "ctr"),
                    _col("bin", "Bin Tujuan", "ctr"), _col("qty", "Qty", "num")],
        "items": items,
        "totals": [{"label": "Jumlah Roll", "value": str(len(rows))},
                   {"label": "Total Kuantitas", "value": total, "strong": True}],
        "notes": "Tempatkan setiap roll ke bin tujuan lalu scan konfirmasi lokasi." if items else "⚠ Belum ada barang diterima (inbound) untuk PO ini.",
        "signatures": [{"label": "Ditempatkan", "role": "Petugas Put-Away", "name": ""},
                       {"label": "Diperiksa", "role": "Supervisor Gudang", "name": ""}],
        "_amount": 0,
    }


# ── Bukti Terima Barang / Goods Receipt Note (GRN) — dari purchase_orders ────
async def resolve_goods_receipt(doc, db):
    rows, _ = await _wms_scan_rows(db, {"po_id": doc.get("id")}, "inbound")
    total_rolls = len([r for r in rows if r["roll_id"] != "-"])
    items = []
    for i, it in enumerate(doc.get("items", []), 1):
        ordered = float(it.get("quantity") or 0)
        received = float(it.get("received_qty") or 0)
        items.append({"no": i, "sku": it.get("sku", ""), "desc": it.get("product_name", ""),
                      "rolls_ord": _rolls_cell(it.get("qty_rolls")),
                      "ordered": f"{fmt_num(ordered)}",
                      "rolls_rcv": _rolls_cell(it.get("received_rolls")),
                      "received": f"{fmt_num(received)}",
                      "diff": f"{fmt_num((received - ordered))}", "unit": it.get("unit", "")})
    total_ord = _sum_by_unit([(float(it.get("quantity") or 0), it.get("unit", "")) for it in doc.get("items", [])])
    total_rcv = _sum_by_unit([(float(it.get("received_qty") or 0), it.get("unit", "")) for it in doc.get("items", [])])
    wh = next((r["warehouse_name"] for r in rows if r["warehouse_name"]), "-")
    return {
        "title": "Bukti Terima Barang (GRN)", "number": doc.get("po_number"),
        "date": fmt_date(doc.get("completed_at") or doc.get("created_at")), "status": doc.get("status"),
        "party_to": {"title": "Dari Supplier", "name": doc.get("supplier_name"),
                     "phone": doc.get("supplier_contact", "")},
        "meta": [{"label": "No. Pesanan Pembelian", "value": doc.get("po_number", "-")},
                 {"label": "Gudang Penerima", "value": wh},
                 {"label": "Total Roll Diterima", "value": str(total_rolls)},
                 {"label": "Dicetak", "value": fmt_now()}],
        "columns": [_col("no", "No", "num"), _col("sku", "SKU"), _col("desc", "Nama Barang"),
                    _col("rolls_ord", "Roll Dipesan", "num"), _col("ordered", "Dipesan", "num"),
                    _col("rolls_rcv", "Roll Diterima", "num"), _col("received", "Diterima", "num"),
                    _col("diff", "Selisih", "num"), _col("unit", "Satuan", "ctr")],
        "items": items,
        "totals": [{"label": "Roll Dipesan",
                    "value": _sum_rolls([it.get("qty_rolls") for it in doc.get("items", [])])},
                   {"label": "Total Dipesan", "value": total_ord},
                   {"label": "Roll Diterima",
                    "value": _sum_rolls([it.get("received_rolls") for it in doc.get("items", [])])},
                   {"label": "Total Diterima", "value": total_rcv, "strong": True}],
        "notes": doc.get("notes") or "Barang telah diterima dan diperiksa sesuai jumlah di atas.",
        "signatures": [{"label": "Diterima", "role": "Gudang", "name": ""},
                       {"label": "Diperiksa", "role": "QC", "name": ""},
                       {"label": "Pengirim", "role": "Supplier/Ekspedisi", "name": ""}],
        "_amount": 0,
    }


# ── Kedatangan Barang (GRN baru) — dari goods_receipts ───────────────────────
# UAT 24 Okt (P16.2): dulu doc_type `goods_receipt` membaca `purchase_orders` (bukti terima per PO), sehingga
# GRN baru (koleksi `goods_receipts`, jenis jejak `goods_receipt`) tidak bisa dicetak (404) dan tautan jejak
# dari Pusat Dokumen membawa id PO ke jejak GRN. Bukti terima per PO kini doc_type `po_receipt`.
async def resolve_grn(doc, db):
    wh = await db.warehouses.find_one({"id": doc.get("warehouse_id")}, {"_id": 0, "name": 1}) if doc.get("warehouse_id") else None
    dn = doc.get("dn") or {}
    items = []
    lines = [ln for ln in doc.get("lines") or [] if not ln.get("is_non_stock")]
    for ln in lines:
        tgt, dec, cnt, rc = ln.get("target") or {}, ln.get("declared") or {}, ln.get("counted") or {}, ln.get("recon") or {}
        unit = tgt.get("unit") or dec.get("unit") or ""
        items.append({"no": ln.get("line_no"), "sku": tgt.get("sku") or (ln.get("read") or {}).get("item_code", ""),
                      "desc": tgt.get("product_name") or (ln.get("read") or {}).get("description", ""),
                      "ref": tgt.get("po_number") or (ln.get("read") or {}).get("po_ref", ""),
                      "rolls_dn": _rolls_cell(dec.get("rolls")), "qty_dn": f"{fmt_num(float(dec.get('qty') or 0))}",
                      "rolls_cnt": _rolls_cell(cnt.get("rolls")), "qty_cnt": f"{fmt_num(float(cnt.get('qty') or 0))}",
                      "diff": f"{fmt_num(float(rc.get('diff_qty') or 0))}" if rc else "-", "unit": unit})
    discs = [d for d in doc.get("discrepancies") or [] if not d.get("superseded")]
    note = "; ".join(f"Baris {d.get('line_no')}: {d.get('detail', '')}"
                     + (f" — {(d.get('resolution') or {}).get('action')}" if d.get("resolution") else "") for d in discs)
    return {
        "title": "Bukti Kedatangan Barang (GRN)", "number": doc.get("number"),
        "date": fmt_date(doc.get("closed_at") or doc.get("created_at")), "status": doc.get("status"),
        "party_to": {"title": "Dari", "name": doc.get("partner_name", "")},
        "meta": [{"label": "No. Surat Jalan", "value": dn.get("number") or "-"},
                 {"label": "Rujukan", "value": ", ".join(dn.get("po_refs") or []) or "-"},
                 {"label": "Gudang Penerima", "value": (wh or {}).get("name", "-")},
                 {"label": "Dicetak", "value": fmt_now()}],
        "columns": [_col("no", "No", "num"), _col("sku", "SKU"), _col("desc", "Nama Barang"), _col("ref", "PO / SPK"),
                    _col("rolls_dn", "Roll SJ", "num"), _col("qty_dn", "Qty SJ", "num"),
                    _col("rolls_cnt", "Roll Dihitung", "num"), _col("qty_cnt", "Qty Dihitung", "num"),
                    _col("diff", "Selisih", "num"), _col("unit", "Satuan", "ctr")],
        "items": items,
        "totals": [{"label": "Total SJ", "value": _sum_by_unit([(float((ln.get("declared") or {}).get("qty") or 0),
                                                                   (ln.get("target") or {}).get("unit", "")) for ln in lines])},
                   {"label": "Total Dihitung", "strong": True,
                    "value": _sum_by_unit([(float((ln.get("counted") or {}).get("qty") or 0),
                                            (ln.get("target") or {}).get("unit", "")) for ln in lines])}],
        "notes": note or "Barang diterima sesuai hitungan fisik di atas.",
        "signatures": [{"label": "Diterima", "role": "Gudang", "name": doc.get("counted_by", "") or ""},
                       {"label": "Diperiksa", "role": "Admin Gudang", "name": doc.get("closed_by", "") or ""},
                       {"label": "Pengirim", "role": "Supplier/Ekspedisi", "name": ""}],
        "_amount": 0,
    }


# ── Purchase Requisition (PR) — dari purchase_requisitions ───────────────────
async def resolve_purchase_requisition(doc, db):
    items = []
    for i, it in enumerate(doc.get("items", []), 1):
        items.append({"no": i, "sku": it.get("sku", ""), "desc": it.get("product_name", it.get("description", "")),
                      "rolls": _rolls_cell(it.get("qty_rolls")),
                      "qty": f"{fmt_num(it.get('quantity', 0))} {it.get('unit', '')}",
                      "price": fmt_rp(it.get("est_price")), "total": fmt_rp(it.get("subtotal"))})
    return {
        "title": "Permintaan Pembelian", "number": doc.get("number"),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("status") or doc.get("approval_status"),
        "meta": [{"label": "Gudang", "value": doc.get("warehouse_name", "-")},
                 {"label": "Supplier Disarankan", "value": doc.get("preferred_supplier_name", "-")},
                 {"label": "Alasan", "value": doc.get("reason", "-")},
                 {"label": "Dibuat oleh", "value": doc.get("created_by", "-")}],
        "columns": [_col("no", "No", "num"), _col("sku", "SKU"), _col("desc", "Nama Barang"),
                    _col_rolls(), _col("qty", "Jumlah", "num"),
                    _col("price", "Est. Harga", "num"), _col("total", "Estimasi", "num")],
        "items": items,
        "totals": [{"label": "Total Estimasi", "value": fmt_rp(doc.get("total_est_amount")), "strong": True}],
        "terbilang": terbilang(doc.get("total_est_amount")), "notes": doc.get("notes"),
        "signatures": [{"label": "Diajukan", "role": "Requester", "name": doc.get("created_by")},
                       {"label": "Disetujui", "role": "Manager", "name": doc.get("approved_by") or ""}],
        "_amount": doc.get("total_est_amount"),
    }


# ── Invoice Komersial — dari sales_orders ────────────────────────────────────
async def resolve_invoice(doc, db):
    items = []
    for i, it in enumerate(doc.get("items", []), 1):
        items.append({"no": i, "sku": it.get("sku", ""), "desc": it.get("product_name", ""),
                      "rolls": _rolls_cell(it.get("qty_rolls")),
                      "qty": f"{fmt_num(it.get('quantity', 0))} {it.get('unit', '')}",
                      "price": fmt_rp(it.get("price")), "disc": f"{fmt_num(it.get('discount_percent', 0))}%",
                      "total": fmt_rp(it.get("line_total", it.get("subtotal")))})
    totals = []
    if doc.get("net_subtotal") or doc.get("total_amount"):
        totals.append({"label": "Subtotal", "value": fmt_rp(doc.get("net_subtotal", doc.get("total_amount")))})
    totals.extend(_ppn_rows(doc))
    grand = doc.get("grand_total", doc.get("total_amount"))
    totals.append({"label": "Grand Total", "value": fmt_rp(grand), "strong": True})
    return {
        "title": "Faktur", "number": (doc.get("number") or "").replace("SO-", "INV-"),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("payment_status") or doc.get("status"),
        "party_to": {"title": "Tagihan Kepada", "name": doc.get("customer_name"),
                     "address": fmt_address(doc.get("shipping_address")),
                     "phone": doc.get("customer_phone", "")},
        "meta": [{"label": "No. Pesanan Penjualan", "value": doc.get("number", "-")},
                 {"label": "Termin Bayar", "value": doc.get("payment_term_name", "-")},
                 {"label": "Status Bayar", "value": doc.get("payment_status", "-")},
                 {"label": "Dicetak", "value": fmt_date(datetime.now(_WIB).isoformat())}],
        "columns": [_col("no", "No", "num"), _col("sku", "SKU"), _col("desc", "Produk"),
                    _col_rolls(), _col("qty", "Jumlah", "num"), _col("price", "Harga", "num"),
                    _col("disc", "Disc", "num"), _col("total", "Subtotal", "num")],
        "items": items, "totals": totals, "terbilang": terbilang(grand), "notes": doc.get("notes"),
        "signatures": [{"label": "Hormat Kami", "role": "Finance", "name": ""},
                       {"label": "Diterima", "role": "Customer", "name": ""}],
        "_amount": grand,
    }


# ── Faktur Pajak — dari tax_invoices ─────────────────────────────────────────
async def resolve_tax_invoice(doc, db):
    items = []
    for i, it in enumerate(doc.get("items", []), 1):
        items.append({"no": i, "sku": it.get("sku", ""), "desc": it.get("product_name", ""),
                      "rolls": _rolls_cell(it.get("qty_rolls")),
                      "qty": f"{fmt_num(it.get('quantity', 0))} {it.get('unit', '')}",
                      "price": fmt_rp(it.get("price")), "total": fmt_rp(it.get("line_total", it.get("subtotal")))})
    grand = doc.get("grand_total", doc.get("total_amount"))
    # FASE P2 — faktur pajak INTERNAL antar-PT (G-6): beri judul & catatan tegas supaya
    # tidak tertukar dengan Faktur Pajak DJP resmi (nomor internal, bukan NSFP Coretax).
    is_internal = bool(doc.get("is_internal"))
    title = "Faktur Pajak Internal (Antar-PT)" if is_internal else "Faktur Pajak"
    meta = [{"label": "NSFP", "value": doc.get("nsfp") or ("— (internal, tanpa NSFP)" if is_internal else "(belum diisi)")},
            {"label": "Kode Transaksi", "value": doc.get("kode_transaksi", "-")},
            {"label": "Penjual", "value": f"{doc.get('seller_name', '-')} · NPWP {doc.get('seller_npwp', '-')}"},
            {"label": "No. Referensi SO", "value": doc.get("order_number", "-")}]
    if is_internal:
        meta.insert(0, {"label": "Jenis", "value": "INTERNAL antar-PT · BUKAN Faktur Pajak DJP"})
    _notes = doc.get("notes")
    if is_internal:
        _internal_note = ("Dokumen INTERNAL untuk pencatatan PPN antar-PT dalam satu grup. "
                          "BUKAN Faktur Pajak resmi DJP/Coretax — nomor seri resmi (NSFP) "
                          "ditambahkan terpisah bila diperlukan.")
        _notes = f"{_notes}\n{_internal_note}" if _notes else _internal_note
    return {
        "title": title, "number": doc.get("number"),
        "date": fmt_date(doc.get("faktur_date") or doc.get("created_at")), "status": doc.get("status"),
        "watermark": ("INTERNAL" if is_internal else None),
        "party_to": {"title": "Pembeli", "name": doc.get("customer_name"),
                     "address": doc.get("customer_address", ""),
                     "phone": ("NPWP " + doc.get("customer_npwp")) if doc.get("customer_npwp") else "NPWP: -"},
        "meta": meta,
        "columns": [_col("no", "No", "num"), _col("sku", "SKU"), _col("desc", "Nama BKP/JKP"),
                    _col_rolls(), _col("qty", "Jumlah", "num"),
                    _col("price", "Harga", "num"), _col("total", "Total", "num")],
        "items": items,
        "totals": [{"label": "DPP", "value": fmt_rp(doc.get("dpp"))},
                   {"label": f"PPN {fmt_num(doc.get('ppn_rate', 12))}%", "value": fmt_rp(doc.get("ppn_amount"))},
                   {"label": "Total", "value": fmt_rp(grand), "strong": True}],
        "terbilang": terbilang(grand), "notes": _notes,
        "signatures": [{"label": "Penjual / PKP", "role": doc.get("seller_name", ""), "name": doc.get("created_by", "")}],
        "_amount": grand,
    }


# ── Permintaan Penawaran (RFQ) — dari rfqs ───────────────────────────────────
async def resolve_rfq(doc, db):
    items = [{"no": i, "sku": it.get("sku", ""), "desc": it.get("product_name", it.get("description", "")),
              "rolls": _rolls_cell(it.get("qty_rolls")),
              "qty": f"{fmt_num(it.get('quantity', 0))} {it.get('unit', '')}"}
             for i, it in enumerate(doc.get("items", []), 1)]
    sup = doc.get("supplier_name") or ", ".join(s.get("name", "") for s in (doc.get("suppliers") or []) if s.get("name")) or "-"
    return {
        "title": "Permintaan Penawaran (RFQ)", "number": doc.get("number") or doc.get("rfq_number"),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("status"),
        "party_to": {"title": "Kepada Supplier", "name": sup},
        "meta": [{"label": "Batas Penawaran", "value": fmt_date(doc.get("deadline") or doc.get("due_date"))},
                 {"label": "Dibuat oleh", "value": doc.get("created_by", "-")}],
        "columns": [_col("no", "No", "num"), _col("sku", "SKU"), _col("desc", "Nama Barang"),
                    _col_rolls(), _col("qty", "Jumlah", "num")],
        "items": items, "notes": doc.get("notes") or "Mohon kirimkan penawaran harga terbaik beserta ketersediaan stok.",
        "signatures": [{"label": "Dibuat", "role": "Purchasing", "name": doc.get("created_by")},
                       {"label": "Disetujui", "role": "Manager", "name": ""}],
        "_amount": 0,
    }


# ── Voucher Landed Cost — dari landed_cost_vouchers ──────────────────────────
async def resolve_landed_cost(doc, db):
    comps = doc.get("components") or doc.get("cost_components") or doc.get("lines") or []
    items = [{"no": i, "desc": c.get("name", c.get("label", c.get("type", "Biaya"))),
              "basis": c.get("allocation_basis", c.get("basis", "-")), "amount": fmt_rp(c.get("amount", c.get("value", 0)))}
             for i, c in enumerate(comps, 1)]
    total = doc.get("total_amount") or doc.get("total") or sum(float(c.get("amount", c.get("value", 0)) or 0) for c in comps)
    return {
        "title": "Voucher Landed Cost", "number": doc.get("number") or doc.get("voucher_number"),
        "date": fmt_date(doc.get("created_at")), "status": doc.get("status"),
        "meta": [{"label": "PO Terkait", "value": ", ".join(doc.get("po_ids", []) or []) or doc.get("po_number", "-")},
                 {"label": "Dibuat oleh", "value": doc.get("created_by", "-")}],
        "columns": [_col("no", "No", "num"), _col("desc", "Komponen Biaya"),
                    _col("basis", "Basis Alokasi"), _col("amount", "Nilai", "num")],
        "items": items,
        "totals": [{"label": "Total Landed Cost", "value": fmt_rp(total), "strong": True}],
        "terbilang": terbilang(total), "notes": doc.get("notes"),
        "signatures": [{"label": "Dibuat", "role": "Finance", "name": doc.get("created_by")},
                       {"label": "Disetujui", "role": "Manager", "name": ""}],
        "_amount": total,
    }



# ── Nota Retur / Nota Kredit Antar-PT (FASE P2 · G-6b) ───────────────────────
async def resolve_interco_return(doc, db):
    """Dokumen kembar retur antar-PT (satu koleksi `interco_returns`, dibedakan `role`):

    * role="returner" → **Nota Retur Antar-PT** — diterbitkan PT PEMBELI yang
      mengembalikan barang, ditujukan ke PT PENJUAL asal.
    * role="receiver" → **Nota Kredit Antar-PT** — diterbitkan PT PENJUAL asal
      sebagai pengurang piutang antar-PT, ditujukan ke PT PEMBELI.

    Keduanya INTERNAL dalam satu grup (BUKAN dokumen pajak DJP) — diberi watermark
    "ANTAR-PT" agar tidak tertukar dengan nota retur pelanggan/supplier biasa.
    """
    is_returner = doc.get("role") == "returner"
    seller = doc.get("seller_entity_name") or "-"
    buyer = doc.get("buyer_entity_name") or "-"
    if is_returner:
        title = "Nota Retur Antar-PT"
        issuer, party_title, party_name = buyer, "Kepada Yth (PT Penjual Asal)", seller
        made_role = "PT Pembeli (Pengirim Retur)"
    else:
        title = "Nota Kredit Antar-PT"
        issuer, party_title, party_name = seller, "Kepada Yth (PT Pembeli)", buyer
        made_role = "PT Penjual (Penerbit Nota Kredit)"

    items = []
    for i, it in enumerate(doc.get("items", []), 1):
        items.append({
            "no": i, "sku": it.get("sku", ""), "desc": it.get("product_name", ""),
            "rolls": _rolls_cell(it.get("qty_rolls")),
            "qty": f"{fmt_num(it.get('quantity', 0))} {it.get('unit', '')}",
            "price": fmt_rp(it.get("unit_price", it.get("price"))),
            "total": fmt_rp(it.get("line_subtotal", it.get("subtotal"))),
        })
    totals = [{"label": "Subtotal (DPP)", "value": fmt_rp(doc.get("subtotal"))}]
    if doc.get("tax_apply"):
        totals.append({"label": f"PPN {fmt_num(doc.get('tax_rate', 11))}%", "value": fmt_rp(doc.get("tax_amount"))})
    grand = doc.get("grand_total")
    totals.append({"label": "Total Nilai Retur", "value": fmt_rp(grand), "strong": True})

    _notes = doc.get("notes")
    _base = ("Dokumen INTERNAL antar-PT dalam satu grup — pengurang saldo antar-PT "
             "(IC-AR/IC-AP). BUKAN Nota Retur/Kredit pajak resmi DJP.")
    _notes = f"{_notes}\n{_base}" if _notes else _base
    return {
        "title": title, "number": doc.get("number"),
        "date": fmt_date(doc.get("doc_date") or doc.get("created_at")), "status": doc.get("status"),
        "watermark": "ANTAR-PT",
        "party_to": {"title": party_title, "name": party_name},
        "meta": [
            {"label": "Jenis", "value": "INTERNAL Antar-PT · BUKAN dokumen pajak DJP"},
            {"label": "PT Penerbit", "value": issuer},
            {"label": "Transaksi Asal", "value": doc.get("origin_number", "-")},
            {"label": "Dokumen Kembar", "value": doc.get("counterpart_number", "-")},
            {"label": "Surat Jalan Balik", "value": doc.get("warehouse_transfer_code", "-")},
            {"label": "Alasan Retur", "value": doc.get("reason", "-")},
        ],
        "columns": [_col("no", "No", "num"), _col("sku", "SKU"), _col("desc", "Produk"),
                    _col_rolls("Roll Retur"), _col("qty", "Jumlah Retur", "num"),
                    _col("price", "Harga", "num"), _col("total", "Subtotal", "num")],
        "items": items, "totals": totals,
        "terbilang": terbilang(grand), "notes": _notes,
        "signatures": [
            {"label": "Dibuat", "role": made_role, "name": doc.get("created_by")},
            {"label": "Disetujui", "role": "Manager", "name": doc.get("approved_by")},
            {"label": "Diterima", "role": party_name, "name": ""},
        ],
        "_amount": grand,
    }


# ── FASE I — SPK INSPEKSI & QC (dokumen kerja + hasilnya) ────────────────────
async def resolve_inspection_spk(doc, db):
    """SPK Inspeksi: siapa memeriksa, atas dasar apa, hasil per roll, keputusannya.

    Dicetak sebagai SATU lembar kerja karena begitulah pemilik memakainya: petugas
    membawa lembar ini ke gudang, mengisi kolomnya, lalu lembar yang sama menjadi
    bukti keputusan. Kolom **Roll** berdiri sendiri (keputusan pemilik 2026-08-20)
    supaya bisa dicocokkan dengan hitungan fisik koli.

    Acuan sample ikut dicetak dengan sengaja: tanpa menyebut NAMA sample yang
    di-ACC, kolom "warna sesuai?" hanya berisi pendapat yang tak bisa diperiksa
    ulang oleh siapa pun.
    """
    lines = doc.get("lines") or []
    _color = {"sesuai": "Sesuai", "beda_shade": "Beda shade", "tolak": "Tolak"}
    _hand = {"sesuai": "Sesuai", "beda": "Beda", "tolak": "Tolak"}
    _kind = {"po_receipt": "Inspeksi Penerimaan PO",
             "makloon_output": "Inspeksi Hasil Makloon",
             "return_customer": "Inspeksi Retur Pelanggan",
             "return_supplier": "Inspeksi Retur ke Supplier",
             "replacement": "Inspeksi Barang Pengganti"}
    items = []
    for i, ln in enumerate(lines, 1):
        items.append({
            "no": i,
            "roll_no": ln.get("roll_no") or "—",
            "desc": ln.get("article") or ln.get("sku") or "—",
            "rolls": _rolls_cell(ln.get("qty_rolls")),
            "qty": f"{fmt_num(float(ln.get('quantity') or 0))} {ln.get('unit', '')}".strip(),
            "points": ("—" if ln.get("points_snapshot") in (None, "")
                       else f"{fmt_num(float(ln['points_snapshot']))}"),
            "grade": (f"{ln.get('grade_before') or '—'} → {ln.get('grade_after') or '—'}"
                      if ln.get("grade_after") else (ln.get("grade_before") or "—")),
            "color": _color.get(ln.get("color_result") or "", "—"),
            "handfeel": _hand.get(ln.get("handfeel_result") or "", "—"),
            "note": (("DITAHAN — " + (ln.get("hold_reason") or "")) if ln.get("hold")
                     else (ln.get("remark") or "")),
        })
    party = (doc.get("supplier_name") or doc.get("customer_name") or "")
    party_title = "Supplier" if doc.get("supplier_name") else (
        "Pelanggan" if doc.get("customer_name") else "Pihak")
    summary = doc.get("summary") or {}
    acuan = doc.get("baseline_sample_number") or ""
    if acuan and doc.get("baseline_color"):
        acuan = f"{acuan} · {doc['baseline_color']}"
    return {
        "title": _kind.get(doc.get("kind", ""), "SPK Inspeksi & QC"),
        "number": doc.get("number"),
        "date": fmt_date(doc.get("spk_date") or doc.get("created_at")),
        "status": doc.get("status"),
        "party_to": {"title": party_title, "name": party or "—"},
        "meta": [
            {"label": "Dokumen sumber", "value": doc.get("ref_doc_number") or "—"},
            {"label": "Petugas inspect", "value": doc.get("assigned_name") or "belum ditugaskan"},
            {"label": "Bagian", "value": doc.get("bagian") or "Bagian Inspect"},
            {"label": "Acuan sample (ACC)", "value": acuan or "belum ada sample ACC"},
            {"label": "Total roll", "value": _sum_rolls([ln.get("qty_rolls") for ln in lines])},
            {"label": "Total poin cacat", "value": f"{fmt_num(summary.get('points_total', 0))}"},
            {"label": "Keputusan", "value": doc.get("decision_label") or "belum diputuskan"},
        ],
        "columns": [_col("no", "No", "num"), _col("roll_no", "No. Roll"),
                    _col("desc", "Artikel"), _col_rolls("Roll"),
                    _col("qty", "Jumlah", "num"), _col("points", "Poin", "num"),
                    _col("grade", "Grade"), _col("color", "Warna"),
                    _col("handfeel", "Handfeel"), _col("note", "Catatan")],
        "items": items,
        "notes": (doc.get("reject_reason") or doc.get("remark") or ""),
        "signatures": [
            {"label": "Diperiksa", "role": "Petugas Inspect", "name": doc.get("assigned_name")},
            {"label": "Diputuskan", "role": "Manager", "name": doc.get("decided_by") or ""},
            {"label": "Diterima", "role": "Gudang", "name": ""},
        ],
        "_amount": 0,
    }


# ─── SSOT Registry ───────────────────────────────────────────────────────────
DOC_REGISTRY = {
    "sales_order":     {"label": "Pesanan Penjualan",        "collection": "sales_orders",    "module": "order",          "esignable": True,  "resolver": resolve_sales_order},
    "quotation":       {"label": "Penawaran","collection": "sales_orders",    "module": "order",          "esignable": True,  "resolver": resolve_quotation},
    "purchase_order":  {"label": "Pesanan Pembelian",     "collection": "purchase_orders", "module": "purchase_order", "esignable": True,  "resolver": resolve_purchase_order},
    "vendor_bill":     {"label": "Vendor Bill",        "collection": "vendor_bills",    "module": "vendor_bill",    "esignable": True,  "resolver": resolve_vendor_bill},
    "contra_bon":      {"label": "Tanda Terima Kontrabon", "collection": "contra_bons", "module": "contra_bon",     "esignable": True,  "resolver": resolve_contra_bon},
    "ar_receipt":      {"label": "Kwitansi (Receipt)", "collection": "ar_receipts",     "module": "ar_receipt",     "esignable": True,  "resolver": resolve_ar_receipt},
    "sales_return":    {"label": "Nota Retur Jual",    "collection": "sales_returns",   "module": "sales_return",   "esignable": True,  "resolver": resolve_sales_return},
    "purchase_return": {"label": "Nota Retur Beli",    "collection": "purchase_returns","module": "purchase_return","esignable": True,  "resolver": resolve_purchase_return},
    "interco_return":  {"label": "Nota Retur / Kredit Antar-PT", "collection": "interco_returns", "module": "interco", "esignable": True,  "resolver": resolve_interco_return},
    "makloon_spk":     {"label": "SPK Makloon",        "collection": "makloon_orders",  "module": "makloon_order",  "esignable": True,  "resolver": resolve_makloon_spk},
    "special_order":   {"label": "Pesanan Khusus",      "collection": "special_orders",  "module": "order",          "esignable": True,  "resolver": resolve_special_order},
    "transfer":        {"label": "Surat Jalan Transfer","collection": "warehouse_transfers","module": "transfer",   "esignable": False, "resolver": resolve_transfer},
    "cycle_count":     {"label": "Stock Opname",       "collection": "cycle_count_sessions","module": "inventory",  "esignable": False, "resolver": resolve_cycle_count},
    # ── GAP documents (ditambah 2026-07-21) ──────────────────────────────────
    "picking_list":    {"label": "Surat Pengambilan Barang", "collection": "sales_orders",    "module": "wms",            "esignable": False, "resolver": resolve_picking_list},
    "packing_list":    {"label": "Daftar Kemasan",       "collection": "sales_orders",    "module": "wms",            "esignable": False, "resolver": resolve_packing_list},
    "delivery_note":   {"label": "Surat Jalan Pengiriman","collection": "sales_orders",  "module": "wms",            "esignable": True,  "resolver": resolve_delivery_note},
    "put_away":        {"label": "Daftar Put-Away",     "collection": "purchase_orders", "module": "wms",            "esignable": False, "resolver": resolve_put_away},
    "md_sample_work_order": {"label": "Surat Perintah Kerja Sampel R&D", "collection": "md_samples", "module": "rnd",
                             "esignable": False, "resolver": resolve_md_sample_work_order},   # UAT 24 Okt (P3.1)
    "po_receipt":      {"label": "Bukti Terima per PO","collection": "purchase_orders","module": "wms",              "esignable": True,  "resolver": resolve_goods_receipt},
    "goods_receipt":   {"label": "Bukti Kedatangan Barang (GRN)","collection": "goods_receipts","module": "wms",     "esignable": True,  "resolver": resolve_grn},
    "purchase_requisition": {"label": "Permintaan Pembelian","collection": "purchase_requisitions","module": "purchase_order","esignable": True, "resolver": resolve_purchase_requisition},
    "invoice":         {"label": "Faktur Komersial",   "collection": "sales_orders",    "module": "order",          "esignable": True,  "resolver": resolve_invoice},
    "tax_invoice":     {"label": "Faktur Pajak",        "collection": "tax_invoices",    "module": "tax_invoice",    "esignable": True,  "resolver": resolve_tax_invoice},
    "rfq":             {"label": "Permintaan Penawaran (RFQ)","collection": "rfqs",       "module": "purchase_order", "esignable": True,  "resolver": resolve_rfq},
    "landed_cost":     {"label": "Voucher Landed Cost", "collection": "landed_cost_vouchers","module": "purchase_order","esignable": True, "resolver": resolve_landed_cost},
    # ── FASE I — SPK Inspeksi & QC (2026-08-23) ──────────────────────────────
    # `esignable=True`: lembar ini dipakai sebagai bukti keputusan terima/tolak yang
    # dibaca supplier & mitra makloon, jadi tanda tangannya bermakna.
    "inspection_spk":  {"label": "SPK Inspeksi & QC",   "collection": "inspections",     "module": "inspection",     "esignable": True,  "resolver": resolve_inspection_spk},
}

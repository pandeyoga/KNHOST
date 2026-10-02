"""Tanya KN F1.2 — katalog semantik `cat-v1` sebagai DATA (satu-satunya tempat definisi).

Setiap metrik: sumber, jenis agregasi, satuan, tanggal acuan, dimensi yang didukung, syarat
hak akses, dan kalimat `definition` yang ikut dikirim ke model/ditampilkan di jawaban.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

CATALOG_VERSION = "cat-v1"

MAX_METRICS, MAX_DIMS = 6, 3
ROW_RETURN_LIMIT, ROW_STORE_LIMIT = 200, 5000

PHYSICAL_ROLL_STATUSES = ("available", "reserved", "committed", "picked", "packed", "hold",
                          "quarantine", "blocked", "damaged")
RESERVED_ROLL_STATUSES = ("reserved", "committed", "picked", "packed")
RECEIPT_MOVEMENTS = ("inbound_receiving", "subcon_receipt", "subcon_receipt_byproduct")
PO_DEAD = ("draft", "cancelled", "rejected")
REVENUE_ACCOUNT = "4-1000"

DIMENSIONS: Dict[str, str] = {
    "date": "Tanggal", "entity": "Entitas", "sales_person": "Sales", "customer": "Pelanggan",
    "customer_city": "Kota", "customer_segment": "Segmen", "product": "Produk", "category": "Kategori",
    "line_code": "Lini", "fabric_type": "Jenis kain", "warehouse": "Gudang", "supplier": "Supplier",
    "grade": "Grade", "dye_lot": "Dye lot", "payment_status": "Status bayar", "order_status": "Status pesanan",
    "aging_bucket": "Umur piutang", "stock_age_bucket": "Umur stok", "unit": "Satuan",
}
NAMED_DIMS = {"entity", "sales_person", "customer", "product", "warehouse", "supplier"}

# Sumber → pemetaan dimensi ke field dokumen.
SOURCE_DIMS: Dict[str, Dict[str, str]] = {
    "fact": {"entity": "entity_id", "sales_person": "sales_id", "customer": "customer_id",
             "customer_city": "customer_city", "customer_segment": "customer_segment", "product": "product_id",
             "category": "category", "line_code": "line_code", "fabric_type": "fabric_type",
             "payment_status": "payment_status", "order_status": "status", "unit": "base_unit"},
    "returns": {"entity": "entity_id", "customer": "customer_id", "product": "product_id"},
    "journal": {"entity": "entity_id"},
    "targets": {"entity": "entity_id", "sales_person": "sales_id"},
    "collections": {"entity": "entity_id", "customer": "customer_id", "sales_person": "sales_id"},
    "ar": {"entity": "entity_id", "customer": "customer_id", "sales_person": "sales_id",
           "aging_bucket": "aging_bucket"},
    "ap": {"entity": "entity_id", "supplier": "supplier_id"},
    "purchases": {"entity": "entity_id", "supplier": "supplier_id"},
    "received": {"entity": "owner_entity_id", "product": "product_id", "warehouse": "warehouse_id",
                 "unit": "unit"},
    "stock": {"entity": "owner_entity_id", "product": "product_id", "warehouse": "warehouse_id",
              "grade": "grade", "dye_lot": "dye_lot", "unit": "unit", "fabric_type": "fabric_type",
              "line_code": "line_code", "stock_age_bucket": "stock_age_bucket"},
}
# Dimensi `date` (time_grain) didukung sumber bertanggal.
DATED_SOURCES = {"fact", "returns", "journal", "targets", "collections", "purchases", "received"}

_O = (("order", "view"),)
_AR = (("ar_receipt", "view"), ("order", "view"))
_NOTE_LIVE = "pesanan hidup (bukan batal/draft/kedaluwarsa/ditolak), tanpa sampel"


def M(label: str, source: str, agg: str, unit: str, definition: str, *, perms: Tuple = _O,
      requires: str = "", date_basis: str = "tanggal pesanan (WIB)", additive: bool = True) -> Dict[str, Any]:
    return {"label": label, "source": source, "agg": agg, "unit": unit, "definition": definition,
            "perms": perms, "requires": requires, "date_basis": date_basis, "additive": additive}


METRICS: Dict[str, Dict[str, Any]] = {
    "net_sales": M("Penjualan bersih", "fact", "net", "idr",
                   f"Penjualan = pesanan bersih tanpa PPN (grand_total − PPN), {_NOTE_LIVE}; diskon pesanan dibagi proporsional per baris"),
    "gross_sales": M("Penjualan kotor", "fact", "gross", "idr", "Harga × qty sebelum diskon, tanpa PPN"),
    "discount_total": M("Diskon", "fact", "discount", "idr", "Diskon baris + diskon pesanan"),
    "ppn_amount": M("PPN keluaran", "fact", "ppn", "idr", "PPN keluaran pesanan hidup"),
    "orders_count": M("Jumlah pesanan", "fact", "orders", "count", f"Jumlah {_NOTE_LIVE}", additive=False),
    "avg_order_value": M("Rata-rata nilai pesanan", "fact", "derived", "idr",
                         "Penjualan bersih / jumlah pesanan", additive=False),
    "qty_sold": M("Qty terjual", "fact", "qty", "qty", "Σ qty satuan dasar baris pesanan; tidak dijumlah lintas satuan"),
    "rolls_sold": M("Roll terjual", "fact", "rolls", "count", "Σ jumlah roll baris pesanan (bila diisi)"),
    "customers_active": M("Pelanggan aktif", "fact", "customers", "count",
                          "Jumlah pelanggan berbeda yang punya pesanan hidup", additive=False),
    "new_customers": M("Pelanggan baru", "fact_new", "new", "count",
                       "Pelanggan yang pesanan hidup PERTAMA-nya jatuh di periode"),
    "gross_margin": M("Laba kotor", "fact", "margin", "idr",
                      "Penjualan bersih − HPP (unit_cost × qty dasar, snapshot saat pesanan)", requires="margin_roles"),
    "gross_margin_pct": M("Margin kotor %", "fact", "derived", "pct", "Laba kotor / penjualan bersih",
                          requires="margin_roles", additive=False),
    "returns_value": M("Nilai retur", "returns", "sum", "idr", "Σ nilai bersih nota kredit",
                       date_basis="tanggal nota (WIB)"),
    "recognized_revenue": M("Pendapatan diakui", "journal", "sum", "idr",
                            "Σ kredit − debit akun 4-1000 di jurnal posted (diakui saat barang dikirim, sudah dikurangi retur)",
                            perms=(("accounting", "view"),), date_basis="tanggal jurnal (WIB)"),
    "sample_orders_count": M("Pesanan sampel", "fact_sample", "orders", "count",
                             "Jumlah pesanan hidup bertipe sampel", additive=False),
    "sales_target": M("Target penjualan", "targets", "sum", "idr", "Target penjualan bulanan (sales_targets)",
                      date_basis="bulan target"),
    "target_achievement_pct": M("Pencapaian target", "targets", "derived", "pct",
                                "Penjualan bersih / target penjualan", additive=False, date_basis="bulan target"),
    "collections_amount": M("Uang masuk pelanggan", "collections", "sum", "idr",
                            "Σ penerimaan pelanggan (kwitansi) berstatus posted", perms=_AR, date_basis="tanggal terima (WIB)"),
    "ar_outstanding": M("Piutang", "ar", "outstanding", "idr",
                        "Σ sisa tagihan pesanan tempo (mesin umur piutang)", perms=_AR, date_basis="posisi saat ini"),
    "ar_overdue": M("Piutang lewat jatuh tempo", "ar", "overdue", "idr",
                    "Bagian piutang yang sudah lewat jatuh tempo", perms=_AR, date_basis="posisi saat ini"),
    "ap_outstanding": M("Hutang usaha", "ap", "outstanding", "idr",
                        "Σ tagihan supplier berstatus posted yang belum lunas", perms=(("vendor_bill", "view"),),
                        date_basis="posisi saat ini"),
    "ap_due": M("Hutang jatuh tempo", "ap", "due", "idr", "Hutang usaha dengan jatuh tempo ≤ akhir periode",
                perms=(("vendor_bill", "view"),), date_basis="jatuh tempo"),
    "purchase_value": M("Nilai pembelian", "purchases", "value", "idr",
                        "Σ (grand_total − PPN) PO bukan draft/batal/ditolak", perms=(("purchase_order", "view"),),
                        date_basis="tanggal PO (WIB)"),
    "po_count": M("Jumlah PO", "purchases", "count", "count", "Jumlah PO bukan draft/batal/ditolak",
                  perms=(("purchase_order", "view"),), date_basis="tanggal PO (WIB)", additive=False),
    "received_qty": M("Qty diterima", "received", "qty", "qty", "Σ qty pergerakan stok jenis penerimaan, per satuan",
                      perms=(("inventory", "view"), ("wms", "view")), date_basis="tanggal terima (WIB)"),
    "stock_qty": M("Stok fisik", "stock", "qty", "qty",
                   "Σ sisa panjang roll berstatus fisik (tanpa dalam perjalanan & di makloon), per satuan",
                   perms=(("inventory", "view"), ("wms", "view")), date_basis="posisi saat ini"),
    "stock_rolls": M("Jumlah roll", "stock", "rolls", "count", "Jumlah roll fisik",
                     perms=(("inventory", "view"), ("wms", "view")), date_basis="posisi saat ini"),
    "stock_value": M("Nilai persediaan", "stock", "value", "idr", "Σ sisa panjang × unit_cost roll fisik",
                     perms=(("inventory", "view"), ("wms", "view")), requires="stock_value_roles",
                     date_basis="posisi saat ini"),
    "stock_available_qty": M("Stok tersedia", "stock", "avail", "qty", "Σ sisa panjang roll berstatus available",
                             perms=(("inventory", "view"), ("wms", "view")), date_basis="posisi saat ini"),
    "stock_reserved_qty": M("Stok dipesan", "stock", "reserved", "qty",
                            "Σ sisa panjang roll reserved/committed/picked/packed",
                            perms=(("inventory", "view"), ("wms", "view")), date_basis="posisi saat ini"),
}
QTY_METRICS = {"qty_sold", "received_qty", "stock_qty", "stock_available_qty", "stock_reserved_qty"}
# Metrik turunan butuh metrik dasar (dihitung diam-diam, tidak ditampilkan bila tidak diminta).
DERIVED_NEEDS = {"avg_order_value": ("net_sales", "orders_count"),
                 "gross_margin_pct": ("gross_margin", "net_sales"),
                 "target_achievement_pct": ("net_sales", "sales_target")}


def supported_dims(metric: str) -> set:
    src = METRICS[metric]["source"]
    base = {"fact_new": "fact", "fact_sample": "fact"}.get(src, src)
    dims = set(SOURCE_DIMS[base])
    if src == "fact_new":
        dims = {"entity", "sales_person", "customer", "customer_city", "customer_segment"}
    if base in DATED_SOURCES:
        dims.add("date")
    return dims

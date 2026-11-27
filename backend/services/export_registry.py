"""L11 LN-110 — registry dataset bisnis untuk Pusat Export.

Setiap dataset menyebut grain, kunci, sumber tanggal, kolom, relasi to-one dan izin.
Koleksi yang sengaja tidak diekspor dicatat di EXCLUDED beserta alasannya; sisanya
ditampilkan sebagai "belum dipetakan" (LN-110-T02), tidak diam-diam hilang.
"""
from typing import Any, Dict, List, Optional


# UAT 24 Okt (audit UI tahap 2, G5-14) — kolom kode (status, status bayar, jenis pesanan) dulu tercetak mentah di
# pratinjau & berkas ("shipped", "waiting_stock", "regular"). Kolom ber-`enum` dilabeli Indonesia oleh export_engine
# (`_norm`); filter tetap menerima kode maupun labelnya. Kolom bernama status/payment_status/order_type otomatis.
AUTO_ENUM = {"status": "status", "payment_status": "payment_status", "order_type": "order_type"}


def C(key: str, label: str, type: str = "string", path: Optional[str] = None, vis: Optional[str] = None,
      cost: bool = False, perm: Optional[tuple] = None, filterable: bool = True,
      enum: Optional[str] = None, default: bool = True) -> Dict[str, Any]:
    """`default=False` (FIX-4) — kolom SARINGAN (mis. id gudang untuk mengikuti saringan & cakupan daftar): boleh
    dipakai filter dan dipilih di Pusat Export, tetapi tidak ikut kolom bawaan berkas (EXP-04: id mentah)."""
    if enum is None and type == "string":
        enum = AUTO_ENUM.get(key)
    return {"key": key, "label": label, "type": type, "path": path or key, "vis": vis, "cost": cost,
            "perm": perm, "filterable": filterable, "enum": enum, "default": default}


def J(id: str, label: str, collection: str, local: str, fields: List[Dict[str, Any]],
      perm: Optional[tuple] = None, foreign: str = "id") -> Dict[str, Any]:
    return {"id": id, "label": label, "collection": collection, "local": local, "foreign": foreign,
            "fields": fields, "perm": perm}


ENTITY_JOIN = lambda local="entity_id": J("entity", "Badan usaha", "business_entities", local,  # noqa: E731
                                          [C("short_name", "Nama badan usaha"), C("doc_prefix", "Prefix dokumen")])
CUSTOMER_JOIN = J("customer", "Pelanggan", "customers", "customer_id",
                  [C("code", "Kode pelanggan"), C("type", "Tipe pelanggan"), C("city", "Kota pelanggan"),
                   C("segment", "Segmen")], perm=("customer", "view"))
# UAT 24 Okt (P6.4) — tag desain produk (kode desain, kategori pattern/design) ikut ke semua join produk.
DESIGN_COLS = [C("design_code", "Kode desain"), C("pattern_category_name", "Kategori pattern"),
               C("design_category_name", "Kategori design")]
PRODUCT_JOIN = J("product", "Produk", "products", "product_id",
                 [C("sku", "SKU"), C("name", "Nama produk"), C("category", "Kategori"), C("color", "Warna"),
                  C("grade", "Grade", vis="grade"), C("stage", "Tahap barang"), C("fabric_type", "Jenis kain"),
                  *DESIGN_COLS],
                 perm=("product", "view"))
WAREHOUSE_JOIN = J("warehouse", "Gudang", "warehouses", "warehouse_id",
                   [C("code", "Kode gudang"), C("name", "Nama gudang"), C("city", "Kota gudang")])
SUPPLIER_JOIN = J("supplier", "Pemasok", "suppliers", "supplier_id",
                  [C("code", "Kode pemasok"), C("city", "Kota pemasok"), C("origin_type", "Asal pemasok", vis="origin")],
                  perm=("supplier", "view"))

DATASETS: List[Dict[str, Any]] = [
    {"id": "sales_orders", "label": "Pesanan Penjualan (SO)", "group": "Penjualan", "collection": "sales_orders",
     "grain": "1 baris = 1 pesanan", "key": "id", "perm": ("order", "view"), "owner_scope": "sales_order",
     "date_fields": [C("created_at", "Tanggal pesanan dibuat", "datetime"),
                     C("delivery_date", "Tanggal kirim diminta", "date"),
                     C("delivered_at", "Tanggal terkirim", "datetime")],
     # G5-14 — `stage` = penanda tahap LAMA yang tidak ikut diperbarui saat status berubah (data: SO-00295 status
     # waiting_stock, stage "Reserved"); dilabeli "(data lama)" supaya tidak dibaca sebagai status kini.
     "columns": [C("number", "No. SO"), C("status", "Status"), C("stage", "Tahap (data lama)", enum="stage_legacy"),
                 C("order_type", "Jenis pesanan"),
                 C("customer_name", "Pelanggan"), C("customer_city", "Kota"), C("sales_name", "Sales"),
                 C("payment_term_name", "Syarat bayar"), C("payment_status", "Status bayar"),
                 C("net_subtotal", "Subtotal neto", "money"), C("discount_total", "Total diskon", "money"),
                 C("dpp", "DPP", "money"), C("ppn_amount", "PPN", "money"), C("grand_total", "Total tagihan", "money"),
                 C("paid_total", "Sudah dibayar", "money"), C("created_at", "Dibuat", "datetime"),
                 C("delivery_date", "Tgl kirim diminta", "date"), C("delivered_at", "Terkirim", "datetime"),
                 C("entity_id", "ID badan usaha")],
     "search_fields": ["number", "customer_name", "sales_name"],
     "joins": [CUSTOMER_JOIN, ENTITY_JOIN()]},
    {"id": "sales_order_items", "label": "Baris Pesanan Penjualan", "group": "Penjualan", "collection": "sales_orders",
     "grain": "1 baris = 1 item SO (nilai item tidak dikalikan pembayaran/pengiriman)", "key": "id",
     "unwind": "items", "perm": ("order", "view"), "owner_scope": "sales_order",
     "date_fields": [C("created_at", "Tanggal pesanan dibuat", "datetime"),
                     C("delivered_at", "Tanggal terkirim", "datetime")],
     "columns": [C("number", "No. SO"), C("status", "Status SO"), C("customer_name", "Pelanggan"),
                 C("sales_name", "Sales"), C("sku", "SKU", path="items.sku"),
                 C("product_name", "Produk", path="items.product_name"), C("category", "Kategori", path="items.category"),
                 C("quantity", "Qty", "number", path="items.quantity"), C("unit", "Satuan", path="items.unit"),
                 C("qty_rolls", "Jumlah roll", "number", path="items.qty_rolls"),
                 C("price", "Harga satuan", "money", path="items.price"),
                 C("discount_percent", "Diskon %", "number", path="items.discount_percent"),
                 C("line_total", "Nilai baris", "money", path="items.line_total"),
                 C("unit_cost", "HPP satuan", "money", path="items.unit_cost", cost=True),
                 C("created_at", "Dibuat", "datetime"), C("entity_id", "ID badan usaha")],
     "joins": [J("product", "Produk", "products", "items.product_id",
                 [C("color", "Warna"), C("grade", "Grade", vis="grade"), C("fabric_type", "Jenis kain"), *DESIGN_COLS],
                 perm=("product", "view")), CUSTOMER_JOIN, ENTITY_JOIN()]},
    {"id": "customers", "label": "Pelanggan", "group": "Penjualan", "collection": "customers",
     "grain": "1 baris = 1 pelanggan", "key": "id", "perm": ("customer", "view"), "owner_scope": "customer",
     "date_fields": [C("created_at", "Tanggal didaftarkan", "datetime")],
     "columns": [C("code", "Kode"), C("name", "Nama"), C("type", "Tipe"), C("segment", "Segmen"), C("city", "Kota"),
                 C("pic_name", "PIC"), C("phone", "Telepon"), C("email", "Email"), C("status", "Status"),
                 C("created_at", "Didaftarkan", "datetime"), C("entity_id", "ID badan usaha")],
     "joins": [ENTITY_JOIN()]},
    {"id": "sales_returns", "label": "Retur Penjualan", "group": "Penjualan", "collection": "sales_returns",
     "grain": "1 baris = 1 dokumen retur", "key": "id", "perm": ("sales_return", "view"), "owner_scope": "created_by",
     "date_fields": [C("created_at", "Tanggal retur dibuat", "datetime")],
     "columns": [C("number", "No. retur"), C("order_number", "No. SO"), C("customer_name", "Pelanggan"),
                 C("status", "Status"), C("return_type", "Jenis retur"), C("total_amount", "Nilai retur", "money"),
                 C("created_at", "Dibuat", "datetime"), C("entity_id", "ID badan usaha")],
     "search_fields": ["number", "customer_name", "order_number"],   # = routers/sales_returns.py (FIX-4)
     "joins": [CUSTOMER_JOIN, ENTITY_JOIN()]},
    {"id": "special_orders", "label": "Pesanan Khusus", "group": "Penjualan", "collection": "special_orders",
     "grain": "1 baris = 1 pesanan khusus", "key": "id", "perm": ("order", "view"), "owner_scope": "created_by",
     "date_fields": [C("created_at", "Tanggal dibuat", "datetime")],
     "columns": [C("number", "No."), C("status", "Status"), C("customer_name", "Pelanggan"),
                 C("total_amount", "Nilai", "money"), C("expected_delivery", "Perkiraan kirim", "date"),
                 C("created_at", "Dibuat", "datetime"), C("entity_id", "ID badan usaha")],
     "joins": [CUSTOMER_JOIN, ENTITY_JOIN()]},
    {"id": "shipments", "label": "Pengiriman (Surat Jalan)", "group": "Gudang & Logistik", "collection": "shipments",
     "grain": "1 baris = 1 surat jalan per produk", "key": "id", "perm": ("order", "view"), "owner_scope": "via_order",
     "date_fields": [C("created_at", "Tanggal SJ dibuat", "datetime")],
     "columns": [C("shipment_no", "No. SJ"), C("order_number", "No. SO"), C("status", "Status"),
                 C("warehouse_name", "Gudang"), C("product_name", "Produk"), C("sku", "SKU"),
                 C("qty", "Qty", "number"), C("unit", "Satuan"), C("qty_rolls", "Jumlah roll", "number"),
                 C("is_partial", "Parsial", "bool"), C("created_at", "Dibuat", "datetime"),
                 C("entity_id", "ID badan usaha")],
     "joins": [ENTITY_JOIN()]},
    {"id": "inventory_rolls", "label": "Roll Stok", "group": "Gudang & Logistik", "collection": "inventory_rolls",
     "grain": "1 baris = 1 roll", "key": "id", "perm": ("inventory", "view"),
     "date_fields": [C("created_at", "Tanggal roll tercatat", "datetime"),
                     C("updated_at", "Terakhir berubah", "datetime")],
     "columns": [C("roll_no", "No. roll"), C("status", "Status"), C("length_initial", "Panjang awal", "number"),
                 C("length_remaining", "Sisa", "number"), C("unit", "Satuan"), C("stage", "Tahap"),
                 C("fabric_type", "Jenis kain"), C("grade", "Grade", vis="grade"), C("lot", "LOT", vis="lot"),
                 C("dye_lot", "Dye lot", vis="lot"), C("ownership_type", "Jenis kepemilikan"),
                 C("is_remnant", "Sisa potong", "bool"), C("unit_cost", "HPP satuan", "money", cost=True),
                 C("created_at", "Tercatat", "datetime"), C("owner_entity_id", "ID badan usaha pemilik"),
                 # FIX-4 — kolom saringan daftar Roll (gudang/produk/lini/bin), tidak ikut kolom bawaan berkas.
                 C("warehouse_id", "ID gudang (saringan)", default=False),
                 C("product_id", "ID produk (saringan)", default=False),
                 C("line_code", "Lini", default=False), C("bin_id", "ID bin (saringan)", default=False),
                 C("lot_id", "ID LOT (saringan)", default=False),
                 C("rfid_tag_id", "ID tag RFID (saringan)", default=False)],
     # = /inventory/rolls `q` (routers/inventory.py): nomor roll/lot/dye lot/batch/grade + nama/SKU produk.
     "search_fields": ["roll_no", "lot", "dye_lot", "batch", "grade", "consignor_ref"],
     "search_product_paths": ["product_id"],
     "joins": [PRODUCT_JOIN, WAREHOUSE_JOIN, ENTITY_JOIN("owner_entity_id")]},
    {"id": "inventory_movements", "label": "Mutasi Stok", "group": "Gudang & Logistik",
     "collection": "inventory_movements", "grain": "1 baris = 1 mutasi", "key": "id", "perm": ("inventory", "view"),
     "date_fields": [C("timestamp", "Waktu mutasi", "datetime")],
     "columns": [C("timestamp", "Waktu", "datetime"), C("movement_type", "Jenis mutasi"),
                 C("quantity", "Qty", "number"), C("unit", "Satuan"), C("lot", "LOT", vis="lot"),
                 C("source_document", "Dokumen sumber"), C("owner_entity_id", "ID badan usaha pemilik"),
                 C("warehouse_id", "ID gudang (saringan)", default=False),
                 C("product_id", "ID produk (saringan)", default=False),
                 C("roll_id", "ID roll (saringan)", default=False)],
     "search_fields": ["source_document", "movement_type", "notes", "lot", "batch"],   # = /inventory/movements
     "joins": [PRODUCT_JOIN, WAREHOUSE_JOIN, ENTITY_JOIN("owner_entity_id")]},
    {"id": "inventory_lots", "label": "LOT Persediaan", "group": "Gudang & Logistik", "collection": "inventory_lots",
     "grain": "1 baris = 1 LOT", "key": "id", "perm": ("inventory", "view"), "vis": "lot",
     "date_fields": [C("created_at", "Tanggal LOT dibuat", "datetime")],
     "columns": [C("lot_number", "No. LOT", vis="lot"), C("sku", "SKU"), C("product_name", "Produk"),
                 C("lot_status", "Status"), C("supplier_lot", "LOT supplier", vis="lot"),
                 C("roll_count", "Jumlah roll", "number"), C("qty_remaining", "Sisa qty", "number"),
                 C("unit", "Satuan"), C("created_at", "Dibuat", "datetime"),
                 C("warehouse_id", "ID gudang (saringan)", default=False),
                 C("product_id", "ID produk (saringan)", default=False),
                 C("source", "Asal LOT", default=False), C("stage", "Tahap", default=False)],
     # FIX-4 — `inventory_lots` tidak ada di WAREHOUSE_FIELDS: pagar lokasi petugas berpagar diterapkan mesin export.
     "location_fields": ("warehouse_id",),
     "search_fields": ["lot_number", "supplier_lot", "dye_lot", "sku", "product_name", "legacy_lot_codes", "note",
                       "internal_alias"],   # = lot_service.list_lots `q`
     "joins": [WAREHOUSE_JOIN, ENTITY_JOIN("owner_entity_id")]},
    {"id": "warehouse_transfers", "label": "Transfer Gudang", "group": "Gudang & Logistik",
     "collection": "warehouse_transfers", "grain": "1 baris = 1 transfer", "key": "id", "perm": ("transfer", "view"),
     "date_fields": [C("created_at", "Tanggal dibuat", "datetime"), C("completed_at", "Tanggal selesai", "datetime")],
     "columns": [C("code", "No. transfer"), C("transfer_kind", "Jenis"), C("status", "Status"),
                 C("requested_by", "Diminta oleh"), C("approved_by", "Disetujui oleh"),
                 C("created_at", "Dibuat", "datetime"), C("completed_at", "Selesai", "datetime"),
                 C("entity_id", "ID badan usaha"),
                 C("source_warehouse_id", "ID gudang asal (saringan)", default=False),
                 C("dest_warehouse_id", "ID gudang tujuan (saringan)", default=False),
                 C("line_codes", "Lini (saringan)", default=False)],
     # Cari daftar Transfer: kode, peminta, SO, produk + nama gudang/PT (diselesaikan ke id).
     "search_fields": ["code", "requested_by", "sales_order_number", "items.sku", "items.product_name"],
     "search_warehouse_paths": ["source_warehouse_id", "dest_warehouse_id"],
     "search_entity_paths": ["entity_id", "source_entity_id", "dest_entity_id"],
     "joins": [J("source_wh", "Gudang asal", "warehouses", "source_warehouse_id", [C("name", "Gudang asal")]),
               J("dest_wh", "Gudang tujuan", "warehouses", "dest_warehouse_id", [C("name", "Gudang tujuan")]),
               ENTITY_JOIN()]},
    {"id": "products", "label": "Produk & Varian", "group": "Master", "collection": "products",
     "grain": "1 baris = 1 SKU", "key": "id", "perm": ("product", "view"),
     "date_fields": [C("created_at", "Tanggal dibuat", "datetime")],
     "columns": [C("sku", "SKU"), C("name", "Nama"), C("category", "Kategori"), C("color", "Warna"),
                 C("grade", "Grade", vis="grade"), C("stage", "Tahap"), C("fabric_type", "Jenis kain"),
                 C("base_unit", "Satuan dasar"), C("price", "Harga master", "money"), C("status", "Status"),
                 C("lifecycle", "Siklus"), *DESIGN_COLS, C("exclusive_customer_name", "Eksklusif untuk"),
                 C("created_at", "Dibuat", "datetime")], "joins": []},
    {"id": "suppliers", "label": "Pemasok", "group": "Pembelian", "collection": "suppliers",
     "grain": "1 baris = 1 pemasok", "key": "id", "perm": ("supplier", "view"),
     "date_fields": [C("created_at", "Tanggal dibuat", "datetime")],
     "columns": [C("code", "Kode"), C("name", "Nama"), C("partner_kind", "Jenis mitra"), C("city", "Kota"),
                 C("origin_type", "Asal", vis="origin"), C("npwp", "NPWP"), C("status", "Status"),
                 C("lead_time_days", "Lead time (hari)", "number"), C("entity_id", "ID badan usaha")],
     "joins": [ENTITY_JOIN()]},
    {"id": "purchase_orders", "label": "Pesanan Pembelian (PO)", "group": "Pembelian", "collection": "purchase_orders",
     "grain": "1 baris = 1 PO", "key": "id", "perm": ("purchase_order", "view"),
     "date_fields": [C("created_at", "Tanggal PO dibuat", "datetime"),
                     C("expected_delivery_date", "Perkiraan datang", "date"),
                     C("payment_due_date", "Jatuh tempo", "date")],
     "columns": [C("po_number", "No. PO"), C("status", "Status"), C("supplier_name", "Pemasok"),
                 C("warehouse_name", "Gudang tujuan"), C("po_type", "Jenis PO"),
                 C("grand_total", "Total", "money"), C("amount_paid", "Sudah dibayar", "money"),
                 C("outstanding", "Sisa hutang", "money"), C("payment_status", "Status bayar"),
                 C("created_at", "Dibuat", "datetime"), C("expected_delivery_date", "Perkiraan datang", "date"),
                 C("entity_id", "ID badan usaha")],
     "joins": [SUPPLIER_JOIN, ENTITY_JOIN()]},
    {"id": "vendor_bills", "label": "Tagihan Pemasok", "group": "Keuangan", "collection": "vendor_bills",
     "grain": "1 baris = 1 tagihan", "key": "id", "perm": ("vendor_bill", "view"),
     "date_fields": [C("bill_date", "Tanggal tagihan", "datetime"), C("due_date", "Jatuh tempo", "date")],
     "columns": [C("bill_number", "No. tagihan"), C("supplier_invoice_no", "No. faktur pemasok"),
                 C("po_number", "No. PO"), C("supplier_name", "Pemasok"), C("status", "Status"),
                 C("grand_total", "Total", "money"), C("amount_paid", "Dibayar", "money"),
                 C("outstanding", "Sisa", "money"), C("payment_status", "Status bayar"),
                 C("bill_date", "Tgl tagihan", "datetime"), C("due_date", "Jatuh tempo", "date"),
                 C("entity_id", "ID badan usaha")],
     # Latihan Keuangan 17 Nov — `outstanding`/`payment_status` tersimpan TIDAK diperbarui saat tagihan dibayar
     # (ap_payment_service hanya menambah `amount_paid`), jadi Sisa/Status bayar di ekspor dulu basi. Dihitung ulang di
     # sini dengan rumus yang sama dengan `vendor_bill_service.bill_financials` (grand − dibayar − selisih ditutup).
     "stages": [{"$addFields": {"_vb_grand": {"$cond": [{"$gt": [{"$ifNull": ["$grand_total", 0]}, 0]},
                                                       "$grand_total", {"$ifNull": ["$total_amount", 0]}]},
                                "_vb_paid": {"$ifNull": ["$amount_paid", 0]},
                                "_vb_closed": {"$ifNull": ["$ap_variance_closed", 0]}}},
                {"$addFields": {"outstanding": {"$round": [{"$max": [{"$subtract": [
                    "$_vb_grand", {"$add": ["$_vb_paid", "$_vb_closed"]}]}, 0]}, 2]}}},
                {"$addFields": {"payment_status": {"$switch": {"branches": [
                    {"case": {"$and": [{"$lte": ["$_vb_paid", 0.01]}, {"$lte": ["$_vb_closed", 0.01]}]}, "then": "unpaid"},
                    {"case": {"$lte": ["$outstanding", 0.01]}, "then": "paid"}], "default": "partial"}}}},
                {"$project": {"_vb_grand": 0, "_vb_paid": 0, "_vb_closed": 0}}],
     "joins": [SUPPLIER_JOIN, ENTITY_JOIN()]},
    {"id": "ar_receipts", "label": "Uang Masuk (Kwitansi AR)", "group": "Keuangan", "collection": "ar_receipts",
     "grain": "1 baris = 1 kwitansi (kas diterima, bukan penjualan)", "key": "id", "perm": ("ar_receipt", "view"),
     "owner_scope": "created_by",
     "date_fields": [C("receipt_date", "Tanggal terima uang", "datetime"),
                     C("created_at", "Tanggal dicatat", "datetime")],
     "columns": [C("number", "No. kwitansi"), C("customer_name", "Pelanggan"), C("method", "Metode"),
                 C("amount", "Jumlah diterima", "money"), C("applied_total", "Dialokasikan", "money"),
                 C("unapplied_amount", "Belum dialokasikan", "money"), C("status", "Status"),
                 C("created_by_name", "Dicatat oleh"), C("receipt_date", "Tgl terima", "datetime"),
                 C("entity_id", "ID badan usaha")],
     "search_fields": ["number", "customer_name"],   # = routers/ar_receipts.py `q` (PK-42)
     "joins": [CUSTOMER_JOIN, ENTITY_JOIN()]},
    {"id": "cash_transactions", "label": "Transaksi Kas & Bank", "group": "Keuangan", "collection": "cash_transactions",
     "grain": "1 baris = 1 transaksi kas", "key": "id", "perm": ("cash", "view"),
     "date_fields": [C("txn_date", "Tanggal transaksi", "datetime")],
     "columns": [C("number", "No."), C("cash_type", "Jenis kas"), C("direction", "Arah"),
                 C("amount", "Jumlah", "money"), C("category", "Kategori"), C("description", "Keterangan"),
                 C("status", "Status"), C("txn_date", "Tanggal", "datetime"), C("entity_id", "ID badan usaha")],
     "search_fields": ["number", "description", "category"],   # = routers/cash.py `q` (PK-42)
     "joins": [ENTITY_JOIN()]},
    # Kas & Bank 1 (Tugas 6) — daftar Kas & Bank › Pindah Dana (tombol baku Unduh Excel/CSV, G-UI-07).
    {"id": "fund_transfers", "label": "Pindah Dana", "group": "Keuangan", "collection": "fund_transfers",
     "grain": "1 baris = 1 dokumen Pindah Dana", "key": "id", "perm": ("cash", "view"),
     "date_fields": [C("tanggal_kirim", "Tanggal kirim", "date"), C("created_at", "Tanggal dicatat", "datetime")],
     "columns": [C("number", "No. Pindah Dana"), C("tanggal_kirim", "Tanggal kirim", "date"),
                 C("rekening_asal_nama", "Dari rekening"), C("rekening_tujuan_nama", "Ke rekening"),
                 C("nominal", "Nominal", "money"), C("biaya", "Biaya transfer", "money"), C("status", "Status"),
                 C("tanggal_terima", "Rencana tiba", "date"), C("tanggal_diterima", "Diterima", "date"),
                 C("catatan", "Catatan"), C("created_by", "Dicatat oleh"), C("alasan_batal", "Alasan batal"),
                 C("entity_id", "ID badan usaha", default=False)],
     # = `fund_transfer_service.daftar` `q` (nomor / catatan / nama rekening asal & tujuan)
     "search_fields": ["number", "catatan", "rekening_asal_nama", "rekening_tujuan_nama"],
     "joins": [ENTITY_JOIN()]},
    # Kas & Bank 2 (Tugas 4) — Transaksi Kas › bagian "Menunggu persetujuan" (pengajuan kas keluar manual di atas batas;
    # tombol baku Unduh Excel/CSV, G-UI-07).
    {"id": "cash_out_requests", "label": "Pengajuan Kas Keluar", "group": "Keuangan", "collection": "cash_out_requests",
     "grain": "1 baris = 1 pengajuan kas keluar manual", "key": "id", "perm": ("cash", "view"),
     "date_fields": [C("txn_date", "Tanggal kas", "date"), C("created_at", "Tanggal diajukan", "datetime")],
     "columns": [C("number", "No. pengajuan"), C("txn_date", "Tanggal kas", "date"),
                 C("account_name", "Rekening"), C("category", "Kategori"), C("description", "Keterangan"),
                 C("amount", "Nominal", "money"), C("status", "Status"),
                 C("pengaju_name", "Pengaju", path="pengaju.name"),
                 C("disetujui_oleh", "Disetujui oleh"), C("cash_number", "No. kas"), C("alasan_tolak", "Alasan tolak"),
                 C("alasan_batal", "Alasan batal"), C("created_at", "Diajukan pada", "datetime"),
                 C("entity_id", "ID badan usaha", default=False)],
     # = `cash_out_request_service.daftar` `q` (nomor / keterangan / kategori / nama pengaju)
     "search_fields": ["number", "description", "category", "pengaju.name"],
     "joins": [ENTITY_JOIN()]},
    {"id": "journal_entries", "label": "Jurnal Umum", "group": "Keuangan", "collection": "journal_entries",
     "grain": "1 baris = 1 jurnal (header)", "key": "id", "perm": ("accounting", "view"),
     "date_fields": [C("date", "Tanggal jurnal", "datetime")],
     "columns": [C("number", "No. jurnal"), C("date", "Tanggal", "datetime"), C("description", "Keterangan"),
                 C("source_type", "Sumber"), C("source_label", "Dokumen sumber"),
                 C("total_debit", "Total debit", "money"), C("total_credit", "Total kredit", "money"),
                 C("status", "Status"), C("entity_id", "ID badan usaha")],
     "joins": [ENTITY_JOIN()]},
    {"id": "makloon_orders", "label": "Order Makloon", "group": "Pembelian", "collection": "makloon_orders",
     "grain": "1 baris = 1 order makloon", "key": "id", "perm": ("makloon_order", "view"),
     "date_fields": [C("created_at", "Tanggal dibuat", "datetime")],
     "columns": [C("mko_number", "No. MKO"), C("status", "Status"), C("mode", "Mode"),
                 C("material_name", "Bahan"), C("material_qty", "Qty bahan", "number"),
                 C("material_unit", "Satuan bahan"), C("final_output_name", "Hasil akhir"),
                 C("planned_service_cost", "Biaya jasa rencana", "money", cost=True),
                 C("created_at", "Dibuat", "datetime"), C("entity_id", "ID badan usaha"),
                 C("line_code", "Lini", default=False),
                 C("from_warehouse_id", "ID gudang asal (saringan)", default=False),
                 C("target_warehouse_id", "ID gudang tujuan (saringan)", default=False)],
     "search_fields": ["mko_number", "material_name", "final_output_name", "po_number"],
     "joins": [ENTITY_JOIN()]},
    {"id": "design_requests", "label": "Permintaan Desain", "group": "Produk & Desain", "collection": "design_requests",
     "grain": "1 baris = 1 permintaan desain", "key": "id", "perm": ("design_request", "view"),
     "owner_scope": "design",
     "date_fields": [C("created_at", "Tanggal dibuat", "datetime")],
     "columns": [C("number", "No."), C("status", "Status"), C("target_type", "Tujuan"),
                 C("customer_name", "Pelanggan"), C("so_number", "No. SO"), C("assigned_name", "Desainer"),
                 C("created_at", "Dibuat", "datetime"), C("entity_id", "ID badan usaha")],
     "joins": [ENTITY_JOIN()]},
    {"id": "hr_employees", "label": "Karyawan", "group": "SDM", "collection": "hr_employees",
     "grain": "1 baris = 1 karyawan", "key": "id", "perm": ("hr", "view"),
     "date_fields": [C("join_date", "Tanggal bergabung", "date")],
     "columns": [C("code", "NIK karyawan"), C("name", "Nama"), C("employment_type", "Status kerja"),
                 C("status", "Status"), C("join_date", "Bergabung", "date"), C("email", "Email"),
                 C("phone", "Telepon", perm=("hr", "view_pii")), C("nik", "NIK KTP", perm=("hr", "view_pii")),
                 C("bank_name", "Bank", perm=("hr", "view_pii")),
                 C("base_salary", "Gaji pokok", "money", perm=("hr", "manage_payroll")),
                 C("entity_id", "ID badan usaha")],
     "joins": [J("department", "Departemen", "hr_org_units", "department_id", [C("name", "Departemen")]),
               ENTITY_JOIN()]},
]

#: Koleksi yang sengaja tidak menjadi dataset bisnis (LN-110-T02: alasan terdokumentasi).
EXCLUDED: Dict[str, str] = {
    "sessions": "Kredensial sesi login (rahasia)", "login_attempts": "Log keamanan login",
    "users": "Akun pengguna memuat hash kata sandi; dikelola di Pengaturan → Pengguna",
    "permission_settings": "Konfigurasi hak akses", "system_settings": "Konfigurasi sistem",
    "config_values": "Konfigurasi sistem", "idempotency_keys": "Infrastruktur teknis",
    "number_sequences": "Penomoran dokumen (teknis)", "counters": "Penomoran dokumen (teknis)",
    "migrations": "Catatan migrasi (teknis)", "sys_scheduler_runs": "Log penjadwal (teknis)",
    "sys_wa_outbox": "Antrean pesan WhatsApp (teknis)", "turn_marks": "Penanda notifikasi (teknis)",
    "notifications": "Pesan pribadi pengguna", "audit_logs": "Jejak audit — layar Jejak Audit (admin)",
    "export_jobs": "Pekerjaan export itu sendiri", "export_templates": "Template export pribadi pengguna", "material_reservation_locks": "Kunci transaksi (teknis)",
    "data_hygiene_runs": "Log job kebersihan data (teknis)", "ai_fact_state": "Status sinkron Tanya KN (teknis)",
    "fact_sales_lines": "Tabel fakta turunan Tanya KN (duplikat Baris Pesanan)",
    "push_subscriptions": "Kredensial Web Push", "integration_secrets": "Rahasia integrasi",
    "saga_locks": "Kunci transaksi (teknis)", "gl_postings": "Antrean posting jurnal (teknis)",
}
EXCLUDED_PREFIXES = {"sys_": "Infrastruktur sistem", "ai_": "Cache/riwayat Tanya KN per pengguna",
                     "tmp_": "Data sementara"}


from services.export_registry_more import EXCLUDED_MORE, FINANCE, MORE, STAFF  # noqa: E402
from services.export_registry_wms import WMS_RFID  # noqa: E402  — FIX-4: dokumen WMS-RFID (EXP-05)

DATASETS += FINANCE + STAFF + MORE + WMS_RFID
DATASET_BY_ID = {d["id"]: d for d in DATASETS}
EXCLUDED.update(EXCLUDED_MORE)


def excluded_reason(name: str) -> Optional[str]:
    if name in EXCLUDED:
        return EXCLUDED[name]
    for p, why in EXCLUDED_PREFIXES.items():
        if name.startswith(p):
            return why
    return None


async def coverage(db) -> Dict[str, Any]:
    names = sorted(n for n in await db.list_collection_names() if not n.startswith("system."))
    mapped: Dict[str, List[str]] = {}
    for d in DATASETS:
        mapped.setdefault(d["collection"], []).append(d["label"])
    rows = []
    for n in names:
        count = await db[n].estimated_document_count()
        if n in mapped:
            rows.append({"collection": n, "status": "mapped", "datasets": mapped[n], "rows": count})
        elif excluded_reason(n):
            rows.append({"collection": n, "status": "excluded", "reason": excluded_reason(n), "rows": count})
        else:
            rows.append({"collection": n, "status": "unmapped", "reason": "Belum dipetakan ke dataset", "rows": count})
    summary = {s: sum(1 for r in rows if r["status"] == s) for s in ("mapped", "excluded", "unmapped")}
    return {"collections": rows, "summary": {**summary, "total": len(rows), "datasets": len(DATASETS)}}

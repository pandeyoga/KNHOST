"""L11 LN-110 — registry dataset bisnis untuk Pusat Export.

Setiap dataset menyebut grain, kunci, sumber tanggal, kolom, relasi to-one dan izin.
Koleksi yang sengaja tidak diekspor dicatat di EXCLUDED beserta alasannya; sisanya
ditampilkan sebagai "belum dipetakan" (LN-110-T02), tidak diam-diam hilang.
"""
from typing import Any, Dict, List, Optional


def C(key: str, label: str, type: str = "string", path: Optional[str] = None, vis: Optional[str] = None,
      cost: bool = False, perm: Optional[tuple] = None, filterable: bool = True) -> Dict[str, Any]:
    return {"key": key, "label": label, "type": type, "path": path or key, "vis": vis, "cost": cost,
            "perm": perm, "filterable": filterable}


def J(id: str, label: str, collection: str, local: str, fields: List[Dict[str, Any]],
      perm: Optional[tuple] = None, foreign: str = "id") -> Dict[str, Any]:
    return {"id": id, "label": label, "collection": collection, "local": local, "foreign": foreign,
            "fields": fields, "perm": perm}


ENTITY_JOIN = lambda local="entity_id": J("entity", "Badan usaha", "business_entities", local,  # noqa: E731
                                          [C("short_name", "Nama badan usaha"), C("doc_prefix", "Prefix dokumen")])
CUSTOMER_JOIN = J("customer", "Pelanggan", "customers", "customer_id",
                  [C("code", "Kode pelanggan"), C("type", "Tipe pelanggan"), C("city", "Kota pelanggan"),
                   C("segment", "Segmen")], perm=("customer", "view"))
PRODUCT_JOIN = J("product", "Produk", "products", "product_id",
                 [C("sku", "SKU"), C("name", "Nama produk"), C("category", "Kategori"), C("color", "Warna"),
                  C("grade", "Grade", vis="grade"), C("stage", "Tahap barang"), C("fabric_type", "Jenis kain")],
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
     "columns": [C("number", "No. SO"), C("status", "Status"), C("stage", "Tahap"), C("order_type", "Jenis pesanan"),
                 C("customer_name", "Pelanggan"), C("customer_city", "Kota"), C("sales_name", "Sales"),
                 C("payment_term_name", "Syarat bayar"), C("payment_status", "Status bayar"),
                 C("net_subtotal", "Subtotal neto", "money"), C("discount_total", "Total diskon", "money"),
                 C("dpp", "DPP", "money"), C("ppn_amount", "PPN", "money"), C("grand_total", "Total tagihan", "money"),
                 C("paid_total", "Sudah dibayar", "money"), C("created_at", "Dibuat", "datetime"),
                 C("delivery_date", "Tgl kirim diminta", "date"), C("delivered_at", "Terkirim", "datetime"),
                 C("entity_id", "ID badan usaha")],
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
                 [C("color", "Warna"), C("grade", "Grade", vis="grade"), C("fabric_type", "Jenis kain")],
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
                 C("created_at", "Tercatat", "datetime"), C("owner_entity_id", "ID badan usaha pemilik")],
     "joins": [PRODUCT_JOIN, WAREHOUSE_JOIN, ENTITY_JOIN("owner_entity_id")]},
    {"id": "inventory_movements", "label": "Mutasi Stok", "group": "Gudang & Logistik",
     "collection": "inventory_movements", "grain": "1 baris = 1 mutasi", "key": "id", "perm": ("inventory", "view"),
     "date_fields": [C("timestamp", "Waktu mutasi", "datetime")],
     "columns": [C("timestamp", "Waktu", "datetime"), C("movement_type", "Jenis mutasi"),
                 C("quantity", "Qty", "number"), C("unit", "Satuan"), C("lot", "LOT", vis="lot"),
                 C("source_document", "Dokumen sumber"), C("owner_entity_id", "ID badan usaha pemilik")],
     "joins": [PRODUCT_JOIN, WAREHOUSE_JOIN, ENTITY_JOIN("owner_entity_id")]},
    {"id": "inventory_lots", "label": "LOT Persediaan", "group": "Gudang & Logistik", "collection": "inventory_lots",
     "grain": "1 baris = 1 LOT", "key": "id", "perm": ("inventory", "view"), "vis": "lot",
     "date_fields": [C("created_at", "Tanggal LOT dibuat", "datetime")],
     "columns": [C("lot_number", "No. LOT", vis="lot"), C("sku", "SKU"), C("product_name", "Produk"),
                 C("lot_status", "Status"), C("supplier_lot", "LOT supplier", vis="lot"),
                 C("roll_count", "Jumlah roll", "number"), C("qty_remaining", "Sisa qty", "number"),
                 C("unit", "Satuan"), C("created_at", "Dibuat", "datetime")],
     "joins": [WAREHOUSE_JOIN, ENTITY_JOIN("owner_entity_id")]},
    {"id": "warehouse_transfers", "label": "Transfer Gudang", "group": "Gudang & Logistik",
     "collection": "warehouse_transfers", "grain": "1 baris = 1 transfer", "key": "id", "perm": ("transfer", "view"),
     "date_fields": [C("created_at", "Tanggal dibuat", "datetime"), C("completed_at", "Tanggal selesai", "datetime")],
     "columns": [C("code", "No. transfer"), C("transfer_kind", "Jenis"), C("status", "Status"),
                 C("requested_by", "Diminta oleh"), C("approved_by", "Disetujui oleh"),
                 C("created_at", "Dibuat", "datetime"), C("completed_at", "Selesai", "datetime"),
                 C("entity_id", "ID badan usaha")],
     "joins": [J("source_wh", "Gudang asal", "warehouses", "source_warehouse_id", [C("name", "Gudang asal")]),
               J("dest_wh", "Gudang tujuan", "warehouses", "dest_warehouse_id", [C("name", "Gudang tujuan")]),
               ENTITY_JOIN()]},
    {"id": "products", "label": "Produk & Varian", "group": "Master", "collection": "products",
     "grain": "1 baris = 1 SKU", "key": "id", "perm": ("product", "view"),
     "date_fields": [C("created_at", "Tanggal dibuat", "datetime")],
     "columns": [C("sku", "SKU"), C("name", "Nama"), C("category", "Kategori"), C("color", "Warna"),
                 C("grade", "Grade", vis="grade"), C("stage", "Tahap"), C("fabric_type", "Jenis kain"),
                 C("base_unit", "Satuan dasar"), C("price", "Harga master", "money"), C("status", "Status"),
                 C("lifecycle", "Siklus"), C("created_at", "Dibuat", "datetime")], "joins": []},
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
     "joins": [CUSTOMER_JOIN, ENTITY_JOIN()]},
    {"id": "cash_transactions", "label": "Transaksi Kas & Bank", "group": "Keuangan", "collection": "cash_transactions",
     "grain": "1 baris = 1 transaksi kas", "key": "id", "perm": ("cash", "view"),
     "date_fields": [C("txn_date", "Tanggal transaksi", "datetime")],
     "columns": [C("number", "No."), C("cash_type", "Jenis kas"), C("direction", "Arah"),
                 C("amount", "Jumlah", "money"), C("category", "Kategori"), C("description", "Keterangan"),
                 C("status", "Status"), C("txn_date", "Tanggal", "datetime"), C("entity_id", "ID badan usaha")],
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
                 C("created_at", "Dibuat", "datetime"), C("entity_id", "ID badan usaha")],
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
DATASET_BY_ID = {d["id"]: d for d in DATASETS}

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
    "export_jobs": "Pekerjaan export itu sendiri", "material_reservation_locks": "Kunci transaksi (teknis)",
    "data_hygiene_runs": "Log job kebersihan data (teknis)", "ai_fact_state": "Status sinkron Tanya KN (teknis)",
    "fact_sales_lines": "Tabel fakta turunan Tanya KN (duplikat Baris Pesanan)",
    "push_subscriptions": "Kredensial Web Push", "integration_secrets": "Rahasia integrasi",
    "saga_locks": "Kunci transaksi (teknis)", "gl_postings": "Antrean posting jurnal (teknis)",
}
EXCLUDED_PREFIXES = {"sys_": "Infrastruktur sistem", "ai_": "Cache/riwayat Tanya KN per pengguna",
                     "tmp_": "Data sementara"}


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

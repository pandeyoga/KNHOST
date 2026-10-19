"""L11 lanjutan — dataset tambahan: analitik Finance (LN-111), rapor staf (LN-112), dan pemetaan sisa koleksi bisnis."""
from typing import Any, Dict, List

from services.export_registry import C, CUSTOMER_JOIN, ENTITY_JOIN, J, PRODUCT_JOIN, SUPPLIER_JOIN, WAREHOUSE_JOIN

_T = {"s": "string", "n": "number", "m": "money", "d": "date", "t": "datetime", "b": "bool"}


def cols(spec: str) -> List[Dict[str, Any]]:
    """`key:Label:tipe` dipisah `|`; tipe s/n/m/d/t/b (bawaan s)."""
    out = []
    for part in spec.split("|"):
        k, label, *t = part.strip().split(":")
        out.append(C(k, label, _T[t[0] if t else "s"]))
    return out


def S(id: str, label: str, group: str, coll: str, perm: tuple, spec: str, date: str = "created_at:Tanggal dibuat:t",
      joins=None, **kw) -> Dict[str, Any]:
    return {"id": id, "label": label, "group": group, "collection": coll, "grain": kw.pop("grain", f"1 baris = 1 {label.lower()}"),
            "key": "id", "perm": perm, "date_fields": cols(date) if date else [], "columns": cols(spec),
            "joins": joins if joins is not None else [ENTITY_JOIN()], **kw}


def _sum_lookup(coll: str, local: str, foreign: str, expr: Any, match: Dict[str, Any], out: str,
                unwind: str = "") -> List[Dict[str, Any]]:
    """Agregat anak per dokumen induk (1 angka) — mencegah perkalian baris item × bayar × kirim."""
    pipe: List[Dict[str, Any]] = [{"$match": {"$expr": {"$eq": [f"${foreign}", "$$k"]}, **match}}]
    if unwind:
        pipe = [{"$match": match}, {"$unwind": f"${unwind}"}, {"$match": {"$expr": {"$eq": [f"${foreign}", "$$k"]}}}]
    pipe.append({"$group": {"_id": None, "v": {"$sum": expr}}})
    return [{"$lookup": {"from": coll, "let": {"k": f"${local}"}, "pipeline": pipe, "as": f"_{out}"}},
            {"$addFields": {out: {"$ifNull": [{"$arrayElemAt": [f"$_{out}.v", 0]}, 0]}}}, {"$project": {f"_{out}": 0}}]


_UNIT_NET = {"$let": {"vars": {"it": {"$arrayElemAt": [{"$filter": {"input": "$$ROOT.items", "as": "i",
                                                                       "cond": {"$eq": ["$$i.product_id", "$$s.product_id"]}}}, 0]}},
                      "in": {"$cond": [{"$gt": ["$$it.quantity", 0]}, {"$divide": ["$$it.line_total", "$$it.quantity"]}, 0]}}}
_SHIPPED = [
    {"$lookup": {"from": "shipments", "let": {"k": "$id"}, "as": "_shp", "pipeline": [
        {"$match": {"$expr": {"$eq": ["$order_id", "$$k"]}, "status": {"$nin": ["cancelled", "void"]}}},
        {"$project": {"_id": 0, "product_id": 1, "qty": 1}}]}},
    {"$addFields": {"shipped_qty": {"$sum": "$_shp.qty"},
                    "shipped_value": {"$sum": {"$map": {"input": "$_shp", "as": "s", "in": {"$multiply": ["$$s.qty", _UNIT_NET]}}}}}},
    {"$project": {"_shp": 0}}]
_LIVE = {"status": {"$nin": ["void", "cancelled", "rejected", "draft"]}}
FIN_STAGES = (_SHIPPED
              + _sum_lookup("invoices", "id", "order_id", "$amount", _LIVE, "invoiced_value")
              + _sum_lookup("sales_returns", "id", "order_id", "$total_amount", _LIVE, "returned_value")
              + _sum_lookup("ar_receipts", "id", "allocations.order_id", "$allocations.applied", _LIVE, "cash_received",
                            unwind="allocations")
              + [{"$addFields": {"open_amount": {"$subtract": ["$grand_total", "$cash_received"]},
                                 "net_sales": {"$subtract": ["$net_subtotal", "$returned_value"]}}}])
_FIN_COLS = ("number:No. SO|status:Status|customer_name:Pelanggan|sales_name:Sales (pada transaksi)"
             "|grand_total:Dipesan (total SO):m|net_subtotal:Dipesan neto (DPP+diskon):m|shipped_qty:Qty dikirim:n"
             "|shipped_value:Nilai dikirim (neto):m|invoiced_value:Ditagih (invoice):m|returned_value:Retur:m"
             "|net_sales:Penjualan bersih (neto−retur):m|cash_received:Kas diterima (alokasi AR):m"
             "|open_amount:Sisa tagihan:m|created_at:Tanggal pesanan:t|entity_id:ID badan usaha")

FINANCE = [
    S("sales_finance", "Analitik Penjualan → Kas per SO", "Analitik Keuangan", "sales_orders", ("order", "view"), _FIN_COLS,
      "created_at:Tanggal pesanan (basis order)|delivered_at:Tanggal terkirim (basis kirim):t",
      [CUSTOMER_JOIN, ENTITY_JOIN()], owner_scope="sales_order", stages=FIN_STAGES,
      grain="1 baris = 1 SO; kirim/tagih/retur/kas diagregasi per SO dulu (tidak dikalikan)"),
    S("cash_allocations", "Kas Diterima per Alokasi SO", "Analitik Keuangan", "ar_receipts", ("ar_receipt", "view"),
      "number:No. kwitansi|customer_name:Pelanggan|order_number:No. SO|applied:Dialokasikan:m|method:Metode"
      "|receipt_date:Tanggal terima uang:t|entity_id:ID badan usaha",
      "receipt_date:Tanggal terima uang (basis kas):t", [ENTITY_JOIN()], owner_scope="created_by",
      unwind="allocations", stages=[{"$addFields": {"order_number": "$allocations.order_number",
                                                     "applied": "$allocations.applied"}}],
      grain="1 baris = 1 alokasi kwitansi ke SO (basis tanggal uang diterima)"),
]

_SHARE = {"$divide": [{"$ifNull": ["$sales_team.split_pct", 100]}, 100]}
STAFF = [
    S("sales_report", "Rapor Sales (atribusi split)", "Rapor Staf", "sales_orders", ("order", "view"),
      "person:Sales:s|role_in_team:Peran di tim|share_pct:Porsi %:n|number:No. SO|status:Status SO|customer_name:Pelanggan"
      "|attributed_net:Penjualan teratribusi:m|attributed_returns:Retur teratribusi:m|attributed_net_after_returns:Bersih teratribusi:m"
      "|attributed_cash:Kas diterima teratribusi:m|so_count:Porsi SO (jumlah):n|created_at:Tanggal pesanan:t",
      "created_at:Tanggal pesanan:t", [ENTITY_JOIN()], owner_scope="sales_order", unwind="sales_team",
      unwind_preserve=True,
      stages=_sum_lookup("sales_returns", "id", "order_id", "$total_amount", _LIVE, "returned_value")
      + _sum_lookup("ar_receipts", "id", "allocations.order_id", "$allocations.applied", _LIVE, "cash_received", unwind="allocations")
      + [{"$addFields": {"person": {"$ifNull": ["$sales_team.name", "$sales_name"]},
                         "role_in_team": {"$ifNull": ["$sales_team.role", "pic"]},
                         "share_pct": {"$multiply": [_SHARE, 100]},
                         "attributed_net": {"$multiply": ["$net_subtotal", _SHARE]},
                         "attributed_returns": {"$multiply": ["$returned_value", _SHARE]},
                         "attributed_net_after_returns": {"$multiply": [{"$subtract": ["$net_subtotal", "$returned_value"]}, _SHARE]},
                         "attributed_cash": {"$multiply": ["$cash_received", _SHARE]}, "so_count": _SHARE}}],
      grain="1 baris = 1 SO × anggota tim sales (porsi split; tanpa tim = 100% sales SO)",
      summary_by=["person"], agg={"share_pct": "none"}),
    S("designer_report", "Rapor Designer (per versi)", "Rapor Staf", "design_gallery", ("design_request", "view"),
      "author:Penanggung jawab versi|code:Kode desain|title:Judul|design_type:Tujuan / jenis|status:Status desain"
      "|version_no:Versi:n|version_at:Tanggal versi:t|created_by:Pembuat desain|score:Skor desain (0–2):n"
      "|scored:Sudah dinilai (1/0):n|score_by:Penilai|acc:ACC (1/0):n|is_revision:Ronde revisi (1/0):n|version_count:Versi (hitungan):n",
      "version_at:Tanggal versi:t|created_at:Tanggal desain dibuat:t", [ENTITY_JOIN()], unwind="versions",
      stages=[{"$addFields": {"author": {"$ifNull": ["$versions.by", "$created_by"]}, "version_no": "$versions.version",
                              "version_at": {"$ifNull": ["$versions.at", "$created_at"]}, "score": "$versions.score",
                              "scored": {"$cond": [{"$ne": [{"$ifNull": ["$versions.score", None]}, None]}, 1, 0]},
                              "score_by": "$versions.score_by", "acc": {"$cond": ["$versions.acc", 1, 0]},
                              "is_revision": {"$cond": [{"$gt": [{"$ifNull": ["$versions.version", 1]}, 1]}, 1, 0]},
                              "version_count": 1}}],
      grain="1 baris = 1 versi desain; skor kosong tetap kosong (tidak dihitung nol)", summary_by=["author"],
      agg={"score": "avg", "version_no": "none"}),
]

M, H = ("product", "view"), ("hr", "view")
IC = ("interco_finance", "view")
MORE = [
    S("interco_transactions", "Transaksi Antar-PT (per sisi)", "Keuangan", "interco_transactions", IC,
      "number:No.|counterpart_number:No. pasangan|role:Sisi (penjual/pembeli)|seller_entity_name:PT penjual"
      "|buyer_entity_name:PT pembeli|status:Status|grand_total:Total:m|settled_amount:Dibayar:m|returned_amount:Diretur:m"
      "|received_at:Barang diterima:t|invoiced_at:Diinvoice:t|due_date:Jatuh tempo:d|entity_id:ID badan usaha",
      "created_at:Tanggal dibuat:t|received_at:Tanggal diterima:t|invoiced_at:Tanggal invoice:t",
      grain="1 baris = 1 dokumen per sisi (penjual & pembeli terpisah, tidak digabung)"),
    S("interco_settlements", "Pembayaran Antar-PT", "Keuangan", "interco_settlements", IC,
      "number:No.|payer_entity_name:PT pembayar|payee_entity_name:PT penerima|method:Metode|total_applied:Dibayar:m"
      "|settle_date:Tanggal bayar:d|status:Status|entity_id:ID badan usaha", "settle_date:Tanggal bayar:d"),
    S("interco_accounts", "Saldo Antar-PT per Pasangan", "Keuangan", "interco_accounts", IC,
      "from_entity_name:Dari PT|to_entity_name:Ke PT|role:Jenis (piutang/utang)|outstanding:Saldo terbuka:m"
      "|open_count:Transaksi terbuka:n|settled_amount:Sudah dibayar:m|entity_id:ID badan usaha", date=""),
    S("business_entities", "Badan Usaha", "Master", "business_entities", ("entity", "view"),
      "short_name:Nama singkat|legal_name:Nama legal|type:Jenis|npwp:NPWP|city:Kota|doc_prefix:Prefix|status:Status", joins=[]),
    S("color_library", "Pustaka Warna", "Master", "color_library", ("color", "view"),
      "code:Kode|name:Nama|hex:HEX|family:Keluarga|system:Sistem|status:Status", joins=[]),
    S("product_templates", "Template Produk (Artikel)", "Master", "product_templates", M,
      "name:Nama|category:Kategori|fabric_type:Jenis kain|line_code:Lini|stage:Tahap|base_unit:Satuan|base_price:Harga dasar:m"
      "|gramasi:Gramasi:n|lebar:Lebar:n|status:Status", joins=[]),
    S("entity_prices", "Harga Jual per Badan Usaha", "Penjualan", "entity_prices", ("pricelist", "view"),
      "sku:SKU|product_name:Produk|sell_price:Harga jual:m|currency:Mata uang|valid_from:Berlaku dari:d"
      "|valid_until:Berlaku s/d:d|status:Status|entity_id:ID badan usaha"),
    S("credit_overrides", "Pengecualian Kredit", "Penjualan", "credit_overrides", ("customer", "view"),
      "customer_name:Pelanggan|order_number:No. SO|amount:Nilai:m|reason:Alasan|status:Status|requested_by:Diminta oleh"
      "|entity_id:ID badan usaha"),
    S("sales_targets", "Target Sales", "Penjualan", "sales_targets", ("order", "view"),
      "sales_name:Sales|period:Periode|period_type:Jenis periode|target_sales_amount:Target penjualan:m"
      "|target_collection_amount:Target tagihan:m|target_new_customers:Target pelanggan baru:n|entity_id:ID badan usaha"),
    S("tax_invoices", "Faktur Pajak Keluaran", "Keuangan", "tax_invoices", ("tax_invoice", "view"),
      "number:No. faktur|customer_name:Pelanggan|dpp:DPP:m|ppn_amount:PPN:m|status:Status|entity_id:ID badan usaha"),
    S("credit_notes", "Nota Kredit", "Keuangan", "credit_notes", ("sales_return", "view"),
      "number:No.|customer_name:Pelanggan|amount:Nilai:m|status:Status|entity_id:ID badan usaha"),
    S("contra_bons", "Kontrabon", "Keuangan", "contra_bons", ("contra_bon", "view"),
      "number:No.|supplier_name:Pemasok|total_amount:Total:m|status:Status|entity_id:ID badan usaha"),
    S("landed_cost_vouchers", "Landed Cost", "Keuangan", "landed_cost_vouchers", ("landed_cost", "view"),
      "number:No.|total_amount:Total:m|status:Status|entity_id:ID badan usaha"),
    S("bank_accounts", "Rekening Kas & Bank", "Keuangan", "bank_accounts", ("cash", "view"),
      "name:Nama|account_type:Jenis|cash_type:Jenis kas|bank_name:Bank|account_number:No. rekening|currency:Mata uang"
      "|opening_balance:Saldo awal:m|is_active:Aktif:b|entity_id:ID badan usaha"),
    S("gl_accounts", "Bagan Akun (COA)", "Keuangan", "gl_accounts", ("accounting", "view"),
      "code:Kode|name:Nama|type:Tipe|normal_balance:Saldo normal|parent_code:Induk|is_postable:Bisa diposting:b|is_active:Aktif:b",
      joins=[]),
    S("payment_variance_decisions", "Keputusan Selisih Bayar", "Keuangan", "payment_variance_decisions", ("payment_variance", "view"),
      "number:No.|customer_name:Pelanggan|receipt_number:No. kwitansi|direction:Arah|kind_label:Jenis|expected:Diharapkan:m"
      "|funds:Diterima:m|delta:Selisih:m|reason_label:Alasan|decided_by:Diputus oleh|entity_id:ID badan usaha"),
    S("doc_amendments", "Amandemen Dokumen", "Keuangan", "doc_amendments", ("finance_amendment", "view"),
      "number:No.|doc_type:Jenis dokumen|doc_number:No. dokumen|reason_label:Alasan|method_label:Metode|status:Status"
      "|proposed_by:Diajukan oleh|entity_id:ID badan usaha"),
    S("purchase_requisitions", "Permintaan Pembelian (PR)", "Pembelian", "purchase_requisitions", ("purchase_requisition", "view"),
      "number:No. PR|status:Status|warehouse_name:Gudang|preferred_supplier_name:Pemasok usulan|total_est_amount:Estimasi:m"
      "|needed_by_date:Dibutuhkan:d|reason:Alasan|entity_id:ID badan usaha"),
    S("rfqs", "RFQ / Penawaran", "Pembelian", "rfqs", ("rfq", "view"), "number:No.|status:Status|entity_id:ID badan usaha"),
    S("purchase_returns", "Retur Pembelian", "Pembelian", "purchase_returns", ("purchase_return", "view"),
      "number:No.|supplier_name:Pemasok|total_amount:Nilai:m|status:Status|entity_id:ID badan usaha"),
    S("supplier_contracts", "Kontrak Mitra & Pemasok", "Pembelian", "supplier_contracts", ("supplier_contract", "view"),
      "contract_number:No. kontrak|contract_type:Jenis|partner_kind:Jenis mitra|partner_name:Mitra|product_sku:SKU"
      "|product_name:Produk|tariff_basis:Basis tarif|tariff_rate:Tarif:m|status:Status|entity_id:ID badan usaha"),
    S("supplier_items", "Barang Pemasok", "Pembelian", "supplier_items", ("supplier_item", "view"),
      "supplier_name:Pemasok|sku:SKU|product_name:Produk|supplier_sku:SKU pemasok|supplier_item_name:Nama di pemasok"
      "|supplier_color:Warna pemasok|last_price:Harga terakhir:m|moq:MOQ:n|lead_time_days:Lead time:n|entity_id:ID badan usaha"),
    S("makloons", "Mitra Makloon", "Pembelian", "makloons", ("makloon", "view"),
      "code:Kode|name:Nama|city:Kota|pic_name:PIC|phone:Telepon|capacity_per_month:Kapasitas/bulan:n|capacity_unit:Satuan"
      "|default_tariff:Tarif bawaan:m|entity_id:ID badan usaha"),
    S("material_reservations", "Komitmen Bahan Makloon", "Pembelian", "material_reservations", ("makloon_order", "view"),
      "mko_number:No. MKO|ref_type:Sumber|required_qty:Dibutuhkan:n|qty:Dicadangkan:n|shortage_qty:Kurang:n|consumed_qty:Terpakai:n"
      "|status:Status|owner_entity_id:ID badan usaha pemilik", joins=[PRODUCT_JOIN, ENTITY_JOIN("owner_entity_id")]),
    S("goods_receipts", "Kedatangan Barang (GRN)", "Gudang & Logistik", "goods_receipts", ("goods_receipt", "view"),
      "number:No. GRN|status:Status|supplier_name:Pemasok|po_number:No. PO|entity_id:ID badan usaha"),
    S("wms_tasks", "Tugas Gudang", "Gudang & Logistik", "wms_tasks", ("wms", "view"),
      "flow_type:Alur|source_type:Sumber|po_number:No. PO|sku:SKU|product_name:Produk|expected_qty:Qty rencana:n"
      "|received_qty:Qty diterima:n|unit:Satuan|warehouse_name:Gudang|status:Status|entity_id:ID badan usaha"),
    S("inventory_balances", "Saldo Stok per Gudang", "Gudang & Logistik", "inventory_balances", ("inventory", "view"),
      "available_qty:Tersedia:n|committed_qty:Dipesan:n|hold_qty:Ditahan:n|in_transit_qty:Dalam perjalanan:n"
      "|damaged_qty:Rusak:n|atp_qty:ATP:n|owner_entity_id:ID badan usaha pemilik", date="",
      joins=[PRODUCT_JOIN, WAREHOUSE_JOIN, ENTITY_JOIN("owner_entity_id")], grain="1 baris = 1 produk × gudang × pemilik"),
    S("warehouses", "Gudang", "Gudang & Logistik", "warehouses", ("warehouse", "view"),
      "code:Kode|name:Nama|city:Kota|sharing_mode:Mode berbagi|active:Aktif:b", joins=[]),
    S("warehouse_sites", "Lokasi Gudang", "Gudang & Logistik", "warehouse_sites", ("warehouse", "view"), "name:Nama|city:Kota", joins=[]),
    S("cycle_count_sessions", "Sesi Stock Opname", "Gudang & Logistik", "cycle_count_sessions", ("inventory", "view"),
      "number:No.|status:Status|warehouse_id:Gudang|entity_id:ID badan usaha"),
    S("inspections", "Inspeksi & QC", "Gudang & Logistik", "inspections", ("inspection", "view"),
      "number:No.|kind:Jenis|ref_doc_number:Dokumen sumber|supplier_name:Pemasok|customer_name:Pelanggan|assigned_name:Petugas"
      "|status:Status|spk_date:Tanggal SPK:t|entity_id:ID badan usaha"),
    S("rfid_tags", "Tag RFID", "Gudang & Logistik", "rfid_tags", ("label", "view"), "epc:EPC|roll_id:Roll|status:Status|owner_entity_id:ID badan usaha pemilik",
      joins=[ENTITY_JOIN("owner_entity_id")]),
    S("rfid_reads", "Pembacaan RFID", "Gudang & Logistik", "rfid_reads", ("label", "view"), "epc:EPC|device_id:Perangkat|owner_entity_id:ID badan usaha pemilik",
      joins=[ENTITY_JOIN("owner_entity_id")]),
    S("mfg_work_orders", "Work Order Produksi", "Produk & Desain", "mfg_work_orders", ("production", "view"),
      "number:No.|status:Status|entity_id:ID badan usaha"),
    S("md_specs", "Spesifikasi Produk R&D", "Produk & Desain", "md_specs", ("rnd", "view"), "number:No.|name:Nama|status:Status|entity_id:ID badan usaha"),
    S("md_samples", "Permintaan Sampel R&D", "Produk & Desain", "md_samples", ("rnd", "view"), "number:No.|status:Status|entity_id:ID badan usaha"),
    S("design_gallery", "Galeri Desain", "Produk & Desain", "design_gallery", ("design_request", "view"),
      "code:Kode|title:Judul|design_type:Jenis|status:Status|version:Versi aktif:n|final_score:Skor final:n|approved_by:Disetujui oleh"
      "|designer_code:Kode desainer|created_by:Pembuat|entity_id:ID badan usaha"),
    S("hr_attendance", "Presensi", "SDM", "hr_attendance", H,
      "employee_name:Karyawan|date:Tanggal:d|shift_name:Shift|clock_in:Masuk|clock_out:Pulang|status:Status|late_min:Terlambat (mnt):n"
      "|work_min:Kerja (mnt):n|overtime_min:Lembur (mnt):n|entity_id:ID badan usaha", "date:Tanggal presensi:d"),
    S("hr_leave_requests", "Cuti", "SDM", "hr_leave_requests", H,
      "number:No.|employee_name:Karyawan|leave_label:Jenis|date_from:Dari:d|date_to:Sampai:d|days:Hari:n|status:Status|entity_id:ID badan usaha",
      "date_from:Tanggal mulai cuti:d"),
    S("hr_leave_balances", "Saldo Cuti", "SDM", "hr_leave_balances", H,
      "employee_id:ID karyawan|year:Tahun:n|entitlement:Hak:n|used:Terpakai:n|pending:Menunggu:n|remaining:Sisa:n|entity_id:ID badan usaha",
      date=""),
    S("hr_overtime", "Lembur", "SDM", "hr_overtime", H,
      "number:No.|employee_name:Karyawan|date:Tanggal:d|hours:Jam:n|minutes:Menit:n|status:Status|entity_id:ID badan usaha",
      "date:Tanggal lembur:d"),
    S("hr_kpi", "KPI Karyawan", "SDM", "hr_kpi", H,
      "employee_name:Karyawan|period:Periode|metric:Metrik|target:Target:n|actual:Aktual:n|score:Skor:n|weight:Bobot:n|status:Status"
      "|entity_id:ID badan usaha"),
    S("hr_visits", "Kunjungan Sales", "SDM", "hr_visits", H,
      "employee_name:Karyawan|customer_name:Pelanggan|date:Tanggal:d|outcome:Hasil|duration_min:Durasi (mnt):n|status:Status"
      "|entity_id:ID badan usaha", "date:Tanggal kunjungan:d"),
    S("hr_org_units", "Struktur Organisasi", "SDM", "hr_org_units", H,
      "code:Kode|name:Nama|unit_type:Jenis|status:Status|entity_id:ID badan usaha"),
    S("hr_payroll_runs", "Proses Penggajian", "SDM", "hr_payroll_runs", ("hr", "manage_payroll"),
      "number:No.|period:Periode|status:Status|approved_by:Disetujui oleh|entity_id:ID badan usaha"),
    S("hr_payslips", "Slip Gaji", "SDM", "hr_payslips", ("hr", "manage_payroll"),
      "number:No.|period:Periode|employee_name:Karyawan|position:Jabatan|base_salary:Gaji pokok:m|overtime:Lembur:m"
      "|commission:Komisi:m|status:Status|entity_id:ID badan usaha"),
]

#: Kamus/konfigurasi yang dikelola di layar Master/Pengaturan — dicatat eksplisit, bukan hilang.
EXCLUDED_MORE = {
    "amendment_reasons": "Kamus alasan amandemen (Pengaturan)", "approval_rules": "Konfigurasi aturan persetujuan",
    "complaint_reasons": "Kamus alasan keluhan retur (Master)", "data_hygiene_log": "Log teknis kebersihan data",
    "design_tags": "Kamus tag desain", "document_templates": "Template dokumen (Pengaturan)",
    "expense_categories": "Kamus kategori biaya (Master)", "incentive_rates": "Konfigurasi tarif insentif",
    "md_fabric_types": "Kamus jenis kain (Master)", "md_grades": "Kamus grade (Master Grade)",
    "payment_terms": "Kamus syarat bayar (Master)", "process_stages": "Kamus tahapan proses (Master)",
    "product_categories": "Kamus kategori produk (Master)", "product_lines": "Kamus lini produk (Master)",
    "sample_types": "Kamus jenis sampel (Master)", "uom_conversion_rules": "Kamus konversi satuan (Master)",
    "uoms": "Kamus satuan (Master)", "hr_devices": "Konfigurasi perangkat absensi",
    "hr_geofences": "Konfigurasi geofence absensi", "hr_shifts": "Konfigurasi shift",
    "hr_field_tracks": "Jejak lokasi pribadi karyawan (privasi; layar Live Tracking)",
    "ocr_samples": "Sampel uji OCR (teknis)", "ocr_sample_runs": "Hasil uji OCR (teknis)",
    "supplier_dn_profiles": "Profil OCR surat jalan pemasok (teknis)", "rfid_devices": "Konfigurasi perangkat RFID",
    "rfid_passages": "Log gerbang RFID mentah (observasi, bukan transaksi)",
    "store_credit_redemptions": "Turunan saldo kredit (lihat Uang Masuk/Retur)",
    "intercompany_eliminations": "Jurnal eliminasi konsolidasi (turunan dari transaksi antar-PT)",
}

# LN-140 (2026-10-18) — koleksi baru sejak registry L11 dipetakan / dikecualikan beralasan.
_RET = ("sales_return", "view")
MORE += [
    S("return_grade_impairments", "Kerugian Turun Grade Retur", "Penjualan", "return_grade_impairments", _RET,
      "return_number:No. retur|roll_no:Roll|grade_before:Grade lama|grade_after:Grade baru|qty:Qty:n|unit:Satuan"
      "|list_price:Harga daftar:m|unit_loss:Rugi/satuan:m|amount:Kerugian:m|je_number:Jurnal|entity_id:ID badan usaha",
      grain="1 baris = 1 roll retur yang turun grade (terpisah dari kredit pelanggan)"),
    S("interco_returns", "Retur Antar-PT (per sisi)", "Keuangan", "interco_returns", IC,
      "number:No.|counterpart_number:No. pasangan|role:Sisi|buyer_entity_name:PT pengembali|seller_entity_name:PT penerima"
      "|status:Status|grand_total:Nilai:m|reason:Alasan|source_sales_return_number:Retur pelanggan asal|mandatory_accept:Wajib terima"
      "|entity_id:ID badan usaha", grain="1 baris = 1 dokumen retur antar-PT per sisi"),
    S("roll_cost_history", "Riwayat Nilai Roll", "Gudang", "roll_cost_history", ("inventory", "view"),
      "roll_id:ID roll|reason:Sebab|old_unit_cost:Nilai lama:m|new_unit_cost:Nilai baru:m|ref_number:Dokumen|actor:Oleh",
      joins=[], grain="1 baris = 1 perubahan nilai satuan roll"),
    S("store_credit_ledger", "Mutasi Kredit Toko Pelanggan", "Keuangan", "store_credit_ledger", ("store_credit", "view"),
      "customer_name:Pelanggan|type:Jenis|amount:Nilai:m|balance_after:Saldo:m|ref_number:Dokumen|entity_id:ID badan usaha"),
    S("mdq_cuts", "Potongan MD Quality", "Gudang", "mdq_cuts", ("inventory", "view"),
      "roll_no:Roll|length:Panjang:n|unit:Satuan|status:Status|entity_id:ID badan usaha"),
    S("price_approvals", "Persetujuan Harga", "Penjualan", "price_approvals", ("order", "view"),
      "order_number:Pesanan|status:Status|requested_by:Pengaju|decided_by:Pemutus|entity_id:ID badan usaha"),
    S("logistics_deliveries", "Pengiriman Logistik", "Logistik", "logistics_deliveries", ("logistics", "view"),
      "number:No.|status:Status|driver_name:Sopir|entity_id:ID badan usaha"),
    S("po_variance_tasks", "Tugas Selisih Penerimaan PO", "Pembelian", "po_variance_tasks", ("purchase_order", "view"),
      "po_number:No. PO|supplier_name:Supplier|product_name:Produk|ordered_qty:Dipesan|received_qty:Diterima|short_qty:Kurang|"
      "unit:Satuan|status:Status|assignee_name:Penanggung jawab|entity_id:ID badan usaha"),
]
EXCLUDED_MORE.update({
    "bin_locks": "Kunci transaksi bin (teknis)", "return_create_locks": "Kunci transaksi retur (teknis)",
    "location_migrations": "Catatan migrasi lokasi (teknis)", "custom_roles": "Konfigurasi peran (Pengaturan)",
    "customer_grade_rules": "Konfigurasi rank pelanggan (Pengaturan)", "process_recipes": "Master resep proses (Pengaturan)",
    "design_categories": "Kamus kategori desain", "client_dataset_imports": "Log impor dataset (teknis)",
    "approval_matrix_log": "Jejak audit matriks persetujuan",
    "rfid_print_jobs": "Antrean cetak label RFID (operasional perangkat)",
})

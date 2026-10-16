# KATALOG DATA KAIN NUSANTARA (versi katalog: cat-v1)

## A. Organisasi
- Entitas (kode dokumen): **KSC** = Sukacita (PT Sukacita Berkat Makmur Texindo), **KANDA** = Kanda Fabric (non-PKP),
  **CST** = CV Cipta Sandang Textile. Nomor dokumen berformat `KODE/JENIS-00001` (mis. `CST/SO-00012`).
  Nomor PO lama klien berformat `7476/CST/0726` atau `3351/SCB/0926`.
- Lini produk: **woven** (tenun, satuan umum yard/meter), **knit** (rajut, satuan umum kg), **printing**.
- Grade: A (terbaik), A1, A2, B, BS (barang sortir/terendah).
- Tahap produk: yarn (benang), grey (kain mentah), pfd/pfp (siap celup/print), finished (kain jadi), remnant (sisa), byproduct.

## B. Metrik
Semua nilai uang dalam Rupiah. "Pesanan hidup" = pesanan penjualan dengan status **bukan** cancelled, draft, expired,
rejected. Sampel (order_type = sample) tidak dihitung kecuali `include_samples = true`.

| id | Nama | Definisi | Tanggal acuan | Catatan |
|---|---|---|---|---|
| net_sales | Penjualan bersih | Σ (grand_total − ppn_amount) pesanan hidup. Per produk: line_total × (grand_total − ppn_amount) / Σ line_total pesanan itu (diskon pesanan dibagi proporsional) | tanggal pesanan (WIB) | **Bawaan untuk "penjualan", "omzet"** |
| gross_sales | Penjualan kotor | Σ total_amount (harga × qty sebelum diskon, tanpa PPN) | tanggal pesanan | |
| discount_total | Diskon | Σ diskon baris + diskon pesanan | tanggal pesanan | |
| ppn_amount | PPN keluaran | Σ ppn_amount | tanggal pesanan | |
| orders_count | Jumlah pesanan | jumlah pesanan hidup | tanggal pesanan | |
| avg_order_value | Rata-rata nilai pesanan | net_sales / orders_count | tanggal pesanan | dihitung mesin |
| qty_sold | Qty terjual | Σ base_quantity baris, **per satuan dasar** | tanggal pesanan | tidak pernah dijumlah lintas satuan |
| rolls_sold | Roll terjual | Σ qty_rolls baris (bila diisi) | tanggal pesanan | |
| customers_active | Pelanggan aktif | jumlah pelanggan berbeda yang punya pesanan hidup | tanggal pesanan | |
| new_customers | Pelanggan baru | pelanggan yang pesanan hidup PERTAMA-nya jatuh di periode | tanggal pesanan | |
| gross_margin | Laba kotor | net_sales − Σ (unit_cost × base_quantity) baris | tanggal pesanan | **hanya admin/manager**; HPP = snapshot saat pesanan |
| gross_margin_pct | Margin kotor % | gross_margin / net_sales | | hanya admin/manager |
| returns_value | Nilai retur | Σ net_amount nota kredit (credit_notes) | tanggal nota | |
| recognized_revenue | Pendapatan diakui | Σ kredit − debit akun 4-1000 di jurnal posted | tanggal jurnal | = laporan laba rugi; diakui saat barang dikirim; sudah dikurangi retur; hanya dimensi date & entity |
| sample_orders_count | Pesanan sampel | jumlah pesanan order_type = sample | tanggal pesanan | |
| sales_target | Target penjualan | target_sales_amount di sales_targets (periode bulanan YYYY-MM) | bulan | |
| target_achievement_pct | Pencapaian target | net_sales / sales_target | bulan | dihitung mesin |
| collections_amount | Uang masuk pelanggan | Σ amount penerimaan pelanggan (ar_receipts) status posted | tanggal terima | |
| ar_outstanding | Piutang | Σ sisa tagihan pesanan (grand_total − pembayaran), pesanan tempo | posisi per tanggal | dari mesin umur piutang |
| ar_overdue | Piutang lewat jatuh tempo | bagian ar_outstanding yang lewat jatuh tempo | posisi per tanggal | bucket: current, 1–30, 31–60, 61–90, >90 hari |
| ap_outstanding | Hutang usaha | Σ sisa tagihan supplier (vendor_bills posted) | posisi per tanggal | |
| ap_due | Hutang jatuh tempo | ap_outstanding dengan due_date ≤ akhir periode | jatuh tempo | |
| purchase_value | Nilai pembelian | Σ (grand_total − ppn_amount) PO bukan batal/draft | tanggal PO | |
| po_count | Jumlah PO | | tanggal PO | |
| received_qty | Qty diterima | Σ quantity pergerakan stok jenis penerimaan, per satuan | tanggal terima | |
| stock_qty | Stok fisik | Σ length_remaining roll berstatus fisik (available, reserved, committed, picked, packed, hold, quarantine, blocked, damaged), per satuan | posisi saat ini | tidak termasuk dalam perjalanan & di makloon |
| stock_rolls | Jumlah roll | jumlah roll fisik | posisi saat ini | |
| stock_value | Nilai persediaan | Σ length_remaining × unit_cost roll fisik | posisi saat ini | hanya admin/manager/finance |
| stock_available_qty | Stok tersedia | roll status available | posisi saat ini | |
| stock_reserved_qty | Stok dipesan | roll status reserved/committed/picked/packed | posisi saat ini | |

Metrik stok hanya mendukung posisi saat ini; untuk posisi masa lalu gunakan `run_report` stock_valuation dengan `as_of`
(tersedia bila snapshot harian sudah berjalan).

## C. Dimensi
| id | Arti | Sumber |
|---|---|---|
| date | waktu, dipakai lewat `time_grain` (day/week/month/quarter/year, WIB) | tanggal acuan metrik |
| entity | entitas pemilik transaksi | entity_id / owner_entity_id |
| sales_person | sales yang mendapat kredit penjualan | lihat aturan atribusi |
| customer | pelanggan | customer_id |
| customer_city | kota pelanggan / kota kirim | shipping_city, lalu customer_city |
| customer_segment | Retail / Wholesale / Distributor / VIP | customers.segment |
| product | produk/SKU | items.product_id |
| category | kategori produk saat pesanan | items.category |
| line_code | lini produk saat pesanan | items.line_code |
| fabric_type | woven / knit | products.fabric_type |
| warehouse | gudang | warehouse_id |
| supplier | supplier | supplier_id |
| grade | grade roll | inventory_rolls.grade |
| dye_lot | dye lot roll | inventory_rolls.dye_lot |
| payment_status | pending / unpaid / partial / paid | sales_orders.payment_status |
| order_status | status pesanan | sales_orders.status |
| aging_bucket | current, b1_30, b31_60, b61_90, b90_plus | umur piutang |
| stock_age_bucket | 0–30, 31–60, 61–90, 91–180, >180 hari sejak roll diterima | inventory_rolls |
| unit | satuan dasar | base_unit |

**Aturan atribusi sales** (dipakai `sales_person`): bila pesanan punya sales_team → dibagi sesuai split_pct; bila tidak →
sales_id; bila tidak → pembuat pesanan bila perannya sales; bila tidak → sales penanggung jawab pelanggan; selain itu
"Tanpa sales".

## D. Sinonim istilah pengguna
- penjualan, omzet, jualan, revenue, sales (nilai) → net_sales · "sudah diakui", "di laporan keuangan" → recognized_revenue
- omzet kotor, sebelum diskon → gross_sales · potongan harga → discount_total
- order, PO pelanggan, SO, transaksi → orders_count · laku, keluar, terjual (qty) → qty_sold
- laba, untung, margin, profit (kotor) → gross_margin / gross_margin_pct
- tagihan, piutang, AR, belum bayar → ar_outstanding · telat bayar, macet, lewat tempo → ar_overdue
- pembayaran masuk, tagihan tertagih, collection → collections_amount
- hutang, AP, kewajiban ke supplier → ap_outstanding · belanja, pembelian → purchase_value
- stok, persediaan, barang di gudang → stock_qty / stock_value · ready, bisa dijual → stock_available_qty
- sales, marketing, salesman, SPV → sales_person · toko, customer, konsumen, buyer → customer
- barang, kain, artikel, SKU → product · roll, gulung, piece, pcs (kain) → rolls
- makloon, celup, finishing, maklun → makloon_status · barang masuk, GR, penerimaan → receiving
- SJ, surat jalan → delivery_note / goods_receipt

## E. Format hasil tool
Setiap tool mengembalikan JSON:
`{result_id, title, definition, period:{from,to,tz,label}, entity_scope, columns:[{key,label,type,unit}], rows:[…],
totals:{…}, compare:{period, totals, delta, delta_pct}, row_count, truncated, warnings:[…], denied:[…], source}`.
- Kolom perbandingan dalam baris: `<metrik>_prev`, `<metrik>_delta`, `<metrik>_delta_pct`; pangsa: `<metrik>_share`.
- `denied` berisi metrik/kolom yang disembunyikan karena hak akses.
- `truncated: true` berarti baris dipotong; total tetap dihitung dari seluruh data.
- Rujuk hasil di blok kn-chart/kn-table memakai `result_id` persis.

## F. Contoh pemetaan pertanyaan → tool
1. "Omzet hari ini berapa?" → query_metrics {metrics:[net_sales, orders_count], period:{preset:today}, compare:previous_period}
2. "Siapa sales terbaik bulan lalu?" → query_metrics {metrics:[net_sales, sales_target, target_achievement_pct], group_by:[sales_person], period:{preset:last_month}, sort:{by:net_sales, direction:desc}, limit:10}
3. "Penjualan Toko Jaya Busana 3 bulan terakhir per bulan" → find_entities {kind:customer, query:"Toko Jaya Busana"} → query_metrics {metrics:[net_sales], time_grain:month, period:{preset:last_90d}, filters:[{dimension:customer, op:in, values:[<id>]}]}
4. "Kenapa penjualan knit turun?" → analyze_change {metric:net_sales, dimension:customer, period:{preset:mtd}, compare_to:previous_period, filters:[{dimension:line_code, op:in, values:[knit]}]}
5. "Piutang yang telat lebih dari 60 hari" → list_records {record_type:overdue_invoices, filters:[{dimension:aging_bucket, op:in, values:[b61_90, b90_plus]}]}
6. "Stok Odeza Twill per dye lot" → find_entities {kind:product, query:"Odeza Twill"} → query_metrics {metrics:[stock_available_qty, stock_rolls], group_by:[dye_lot, warehouse], period:{preset:today}, filters:[{dimension:product, op:in, values:[<id>]}]}
7. "Bandingkan omzet tahun ini dengan tahun lalu per bulan" → query_metrics {metrics:[net_sales], time_grain:month, period:{preset:ytd}, compare:same_period_last_year}
8. "Status SO CST/SO-00123" → get_document {doc_type:sales_order, number:"CST/SO-00123"}
9. "Laporan hari ini" → run_report {report:daily_brief, period:{preset:today}}
10. "Produk apa yang paling untung?" → query_metrics {metrics:[gross_margin, gross_margin_pct, net_sales], group_by:[product], sort:{by:gross_margin, direction:desc}} (bila `denied`, jelaskan bahwa margin hanya untuk admin/manager)

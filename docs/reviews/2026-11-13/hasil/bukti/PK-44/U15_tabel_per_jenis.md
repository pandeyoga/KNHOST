| # | Jenis | Label | `view` · `tab` | `focus_type` (← field) | Pembaca layar | Pembaca | Uji jalan |
|---|---|---|---|---|---|---|---|
| 1 | `design_request` | Permintaan Desain | `design-requests` | `design_request` | DesignRequestsView | sudah ada | belum diuji jalan |
| 2 | `md_spec` | Spesifikasi Produk (R&D) | `rnd-specs` | `md_spec` | RndSpecsView (`focusDoc` → fokus R&D di perute) | PK-44 | belum diuji jalan |
| 3 | `md_sample` | Permintaan Sample (Labdip/Proofing) | `rnd-samples` | `md_sample` | RndSamplesView | sudah ada | belum diuji jalan |
| 4 | `special_order` | Pesanan Khusus | `special-orders` | `special_order` | SpecialOrders | sudah ada | belum diuji jalan |
| 5 | `internal_request` | Permintaan Internal (Antar-PT) | `internal-requests` | `internal_request` | InternalRequestsView | sudah ada | belum diuji jalan |
| 6 | `purchase_requisition` | Permintaan Pembelian (PR) | `purchase-requisitions` | `purchase_requisition` | PurchaseRequisitions | sudah ada | belum diuji jalan |
| 7 | `rfq` | Permintaan Penawaran (RFQ) | `rfq` | `rfq` | RFQView — rincian RFQ | PK-44 | belum diuji jalan |
| 8 | `supplier_contract` | Kontrak Pemasok | `supplier-contracts` | `supplier_contract` | ContractsView — form rincian kontrak | PK-44 | belum diuji jalan |
| 9 | `purchase_order` | Pesanan Pembelian (PO) | `purchasing` | `purchase_order` | PurchaseOrderManagement | sudah ada | belum diuji jalan |
| 10 | `goods_receipt` | Kedatangan Barang (Surat Jalan) | `goods-receipts` | `goods_receipt` | GoodsReceiptsView — rincian kedatangan | sudah ada | belum diuji jalan |
| 11 | `grn` | Penerimaan Barang (GRN) | `goods-receipts` · `inbound` | `purchase_order` ← `po_id` | GoodsReceiptsView — tab Scan Terima per PO; tanpa akses pindai & buat kedatangan → rincian PO (PK-44) | sudah ada + PK-44 | belum diuji jalan |
| 12 | `inspection` | Inspeksi & QC | `inspections` | `inspection` | QcHubView (SPK) | sudah ada | belum diuji jalan |
| 13 | `landed_cost` | Biaya Masuk (Landed Cost) | `landed-cost` | `landed_cost` | LandedCostView — rincian biaya masuk | PK-44 | belum diuji jalan |
| 14 | `repair_order` | Perbaikan / Celup Ulang | `repair-orders` | `repair_order` | RepairOrdersView | sudah ada | belum diuji jalan |
| 15 | `vendor_bill` | Tagihan Pemasok | `vendor-bills` | `vendor_bill` | VendorBillsView — rincian tagihan | PK-44 | belum diuji jalan |
| 16 | `contra_bon` | Kontrabon (Tukar Faktur) | `contra-bons` | `contra_bon` | ContraBonsView — tab Daftar + rincian | PK-44 | belum diuji jalan |
| 17 | `purchase_return` | Retur Beli | `purchase-returns` | `purchase_return` | PurchaseReturns — rincian retur beli | PK-44 | belum diuji jalan |
| 18 | `makloon_order` | Order Makloon | `makloon-orders` | `makloon_order` | MakloonOrdersView — rincian order | PK-44 | belum diuji jalan |
| 19 | `sales_order` | Pesanan Penjualan (SO) | `orders` | `sales_order` | OrdersView — rincian pesanan | sudah ada | belum diuji jalan |
| 20 | `picking_task` | Tugas Pengambilan | `wms-outbound` | `wms_task` | OutboundView — tugas ambil | sudah ada | belum diuji jalan |
| 21 | `shipment` | Surat Jalan / Pengiriman | `orders` | `sales_order` ← `order_id` | OrdersView — rincian pesanan induk | sudah ada | belum diuji jalan |
| 22 | `tax_invoice` | Faktur Pajak | `tax-invoices` | `tax_invoice` | TaxInvoices — saring nomor + sorot baris | PK-44 | belum diuji jalan |
| 23 | `ar_receipt` | Kwitansi Pelanggan | `collection-worklist` | `ar_receipt` | CollectionWorklist › riwayat kwitansi — cari nomor + sorot | PK-44 | belum diuji jalan |
| 24 | `sales_return` | Retur Jual | `returns` | `sales_return` | SalesReturns — rincian retur | sudah ada | belum diuji jalan |
| 25 | `doc_amendment` | Amandemen Dokumen | `amendments` | `doc_amendment` | AmendmentCenterView — rincian amandemen | PK-44 | belum diuji jalan |
| 26 | `credit_note` | Nota Kredit / Debit | `amendments` | `credit_note` | AmendmentCenterView — amandemen asal; nota dari retur/pesanan khusus → retur/pesanan | PK-44 | belum diuji jalan |
| 27 | `payment_plan` | Rencana Pembayaran | `payment-plans` · `jadwal` | `payment_plan` | PaymentPlansView — tab Jadwal + saring nomor | sudah ada | belum diuji jalan |
| 28 | `penalty` | Nota Denda Keterlambatan | `payment-plans` · `denda` | `penalty` | PaymentPlansView — tab Denda + saring nomor | sudah ada | belum diuji jalan |
| 29 | `payment_variance` | Keputusan Selisih Pembayaran | `payment-plans` · `selisih` | `payment_variance` | PaymentPlansView — tab Selisih + saring nomor | sudah ada | belum diuji jalan |
| 30 | `warehouse_transfer` | Surat Jalan Transfer | `operations` · `transfer` | `warehouse_transfer` | OperationsView — tab Transfer (preset tab) + rincian | sudah ada | belum diuji jalan |
| 31 | `finance_case` | Kasus Keuangan | `finance-cases` | `finance_case` | FinanceCasesView (`focusDoc` → `focusCase` di perute) | PK-44 | belum diuji jalan |
| 32 | `cycle_count` | Stock Opname | `operations` · `cycle` | `cycle_count` | OperationsView — tab Stock Opname + sesi | sudah ada | belum diuji jalan |
| 33 | `cash_transaction` | Transaksi Kas / Bank | `cash-management` | `cash_transaction` | CashManagementView — cari nomor + sorot baris | PK-44 | belum diuji jalan |
| 34 | `interco_transaction` | Transaksi Antar-PT (Jual-Beli Internal) | `interco-transactions` · `transactions` | `interco_transaction` | IntercoView — tab Daftar Transaksi + rincian | PK-44 | belum diuji jalan |
| 35 | `interco_settlement` | Pelunasan Antar-PT | `interco-transactions` · `settlements` | `interco_settlement` | IntercoView — tab Settlement + sorot | PK-44 | belum diuji jalan |
| 36 | `interco_return` | Retur Antar-PT | `interco-returns` · `returns` | `interco_return` | IntercoView (Retur Antar-PT) — tab Retur Keluar + sorot | PK-44 | belum diuji jalan |
| 37 | `input_tax_invoice` | Faktur Pajak Masukan | `input-tax` | `input_tax_invoice` | InputTaxView — saring nomor + sorot baris | PK-44 | belum diuji jalan |
| 38 | `interco_loan` | Pinjaman Antar-PT | `interco-transactions` · `loans` | `interco_loan` | IntercoView — tab Pinjaman + sorot | PK-44 | belum diuji jalan |
| 39 | `payroll_run` | Penggajian | `hr-payroll-runs` | `payroll_run` | PayrollRunsView — rincian penggajian | PK-44 | belum diuji jalan |
| 40 | `cash_advance` | Pengajuan Dana (PD) | `cash-advances` | `cash_advance` | PettyCashView › CashAdvancesView — rincian PD | PK-44 | belum diuji jalan |
| 41 | `cash_settlement` | Pertanggungjawaban Dana (LPJ) | `settlements` | `cash_settlement` | PettyCashView › SettlementsView — rincian LPJ | PK-44 | belum diuji jalan |
| 42 | `fixed_asset` | Aset Tetap | `fixed-assets` | `fixed_asset` | FixedAssetsView — jadwal penyusutan aset | PK-44 | belum diuji jalan |
| 43 | `journal_entry` | Jurnal | `general-ledger` | `journal_entry` | GeneralLedger — rincian jurnal | sudah ada | belum diuji jalan |

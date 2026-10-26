# Daftar tugas koordinator/P8 dari laporan paket fase 3

## Dari P4
* Alias `costing` → `profitability` preset `{tab:"katalog"}`; cabut tab `costing` di hub `analytics`; katalog akses
  modul `reports` + `profitability`, `fin-reports`.
* Layar baru membaca preset: `financial-statements {tab}`, `cs-pajak {tab, period}`, `input-tax {period}`,
  `profitability {tab}`.
* `verify_custom_modals --update` (P8).
* `verify_error_notice.py`: hapus `InputTaxCreateModal` dari `MODAL_BASELINE`; `LandedCostCreateModal`,
  `VendorBillCreateModal` baseline basi; pelanggaran `PrMergePanel.jsx`, `ReturnRollSettleModal.jsx`,
  `ReturnSettleModal.jsx` (pemilik: P5/P3).
* `components/ErrorNotice.jsx`: tombol × tanpa `type="button"` → ikut submit form di dalam FormModal (perbaiki
  setelah fase paralel).
* Sisa pop-up buatan sendiri di berkas P4 di luar daftar L-03 (Recon×5, JournalEntryModal, TaxInvoices, StoreCredit,
  AmendmentPropose, kontrabon Decision/Deduction/Pay/ReasonNote, VehicleLogs, WhatsAppRules/Settings,
  DocumentActionsBar) — ratchet berikutnya.

## Dari P6
* Alias (aktifkan BERSAMAAN dengan cabut tab): `rnd-labdip|rnd-handfeel|rnd-proofing` → `rnd-samples`
  preset `{mode:"gallery", type:<jenis>, purpose:"all"}` (cabut tab dari `rnd-hub`); `cs-design-gallery` → `rnd-designs`
  preset `{mode:"gallery", status:"acc"}` (cabut tab dari `designer-hub`). Peran setara; rute cadangan tetap.
* Ratchet `--update`: 5 berkas P6 custom_modals, 3 page_tabs.
* Opsional: target backend `design_gallery` → `rnd-designs`; teks basi di `audit_sales_roles_ux.py`;
  `DesignShowcaseModal.jsx`, `AiIllustrationPanel.jsx` tak dipakai.
* `audit_sales_roles_ux.py` sempat terputus (snapshot DB uji tanpa restore) — paling banyak 7 baris audit_logs login
  di kn_test_trial; tidak berbahaya.
* `roleReach.test.js` merah 2 karena layar `settings-cfg-*` & `price-corrections` dari P2 → P8 isi ROLE_REACH_ADDITIONS.

## Dari P2
* WAJIB: `backend/access_modules.py` tambah id menu baru (`settings-*`, `settings-cfg-*`, `settings-devices`,
  `price-corrections`) per modul (rincian P2.md §6.1) → buat ulang fixture fe03 + `navAccess.test`.
* Ratchet `--update` custom_modals & page_tabs.
* `?view=settings-hub` = alias legacy → Master Grade Mutu (opsional ubah `resolveDirectTarget`, sesuaikan uji jangkauan).
* Uji HTTP terpusat: `test_core_e4_master_layers_poc`, `test_gl01_account_mapping`, LPJ, `test_core_role_access_poc`,
  `test_core_e8_roles_poc`.
* Disetujui koordinator: `scripts/check_nav_map.py` (lewati `type:"heading"`), `roleReach.test.js` ROLE_REACH_ADDITIONS.
* P4 sudah selesai → koordinator pasang `DesktopOnlyNotice` di `finance/amendments/AmendmentReasonsPanel.jsx`.
* Untuk P7: `sales/mobile/MobileMore.jsx:89` nav Kebijakan Retur → `"settings-sales"`.
* D-05: AdminView "Buat Pelanggan" bergantung `CustomerFormModal` (P3) — commit bersama.

## Dari P5
* Alias `interco-transfers` → `operations` preset `{tab:"transfer", kind:"inter_entity"}`.
* Tab tersembunyi `supplier-internal-prices` (aliasOf `supplier-contracts`, peran = peran Kontrak) render
  `InternalPricesView` + modul interco & supplier di katalog akses (Kontrak sudah menautkan ke id ini).
* `makloon-claim-recap`: label "Kinerja Mitra Makloon", +peran warehouse (ROLE_REACH_ADDITIONS), perbarui
  `uatV3NavWarehouseMakloon.test.js`. Label menu D-25 `process-recipes` ("Resep Proses Makloon") & `production`
  ("BOM Produksi In-House").
* Preset terbaca: operations `{tab,kind,method,warehouse}`, inspections `{hold}`, logistics `{tab:"history",status}`,
  makloon-claim-recap `{partner}`, production `{tab}`, wms-cutting `{stage,q}`.
* Ratchet `--update`. Saran: `.filter-chips { min-width:0 }` (komponen beku FilterChips) supaya chip tak melebarkan grid di HP.
* `RfidLocationsView` masih tautan mentah `?view=cs-rfid-devices` (alias P2 menanganinya) — opsional ganti `go("settings-devices",{preset:{tab:"rfid"}})`.
* `verify_approval_queues` merah karena DATA (goods_receipts 1 `review`, rfid_print_jobs 4 `verified`) — bukan kode.
* RISIKO: sampai P8, manajer/gudang tanpa editor "Isi massal" di Kontrak & gudang belum bisa buka Kinerja Mitra Makloon.
* Untuk P7: papan "Barang ditahan QC" → `inspections` preset `{hold:true}`.
* D-23 menyimpang dari rencana (beralasan): saringan "Harga Internal" di Kontrak DIPERTAHANKAN (718 kontrak tak bisa
  dikelola di layar Harga Internal).

## Dari P3
* Alias `my-approvals` → `approval-inbox` `{tab:"matrix"}` + cabut tab "Persetujuan Saya" dari hub `approval-inbox`.
* Ratchet `--update` custom_modals (InternalRequestCreateModal → 0).
* Opsional backend: `/reports/order-velocity` belum disaring per sales (panel kecepatan hanya admin/manajer).

## SUDAH dikerjakan koordinator (26 Okt, saat P7 berjalan)
* ErrorNotice: tombol `type="button"` + aria-label ×.
* verify_error_notice PASS: PrMergePanel pakai ErrorNotice; 3 baseline basi dihapus.
* verify_blocking_dialogs PASS: ClientDatasetImportView askConfirm; PutawayOrdersPanel askReason (min 10 = server).
* verify_entity_label 7→1: InternalPriceBulkPanel & LogisticsCostRow `entityOptions`; StockTreePanel `entityShortFromCtx`;
  pola guardrail tidak lagi menuduh perbandingan `(a||b.entity_id) === x`. Sisa MobileMdApp:155 (P7, positif palsu).
* AmendmentReasonsPanel DesktopOnlyNotice.
* verify_approval_queues merah SEJAK SEBELUM fase 3 (11 pintu tanpa antrean + 4 antrean bayangan: credit_notes 8,
  credit_overrides 1, goods_receipts 1, rfid_print_jobs 4) — backend; catat di laporan sebagai sisa.

# Audit pola UI semua layar — langkah 2 (17 Nov 2026)

Asal: rencana empat langkah yang disetujui pemilik (16 Nov: standar + contoh → **audit semua layar** → blueprint per
gelombang → eksekusi berpenjaga). Ukuran: `docs/blueprint/04_POLA_UI.md` §4 "Yang dilarang". Alat: pemindai teks
`scripts/guardrails/audit_pola_ui.py` (baca saja; menghasilkan DAFTAR KANDIDAT — tiap baris diperiksa saat
gelombangnya dikerjakan, karena sebagian hanya tampak mirip pelanggaran).

Cara membaca kolom:
- **Chip/tab saringan** — `FilterChips`/`StatusTabs`/chip buatan dipakai menyaring daftar → ganti dropdown. Pengecualian
  yang sah (bukan saringan): pengalih BAGIAN/mode di dalam satu kartu (mis. bagian kartu pelanggan 360, metode opname,
  mode alokasi pembayaran di formulir) — tetap chip/segmen.
- **Bilah penjelasan** — `notice-bar` info/polos yang tampil terus → pindah ke ikon ? atau satu baris kecil.
- **Kartu angka tanpa klik** — kartu angka yang tidak menyaring/membuka apa pun → beri aksi atau hapus. Pengecualian:
  angka isi LAPORAN (arus kas, perubahan ekuitas) adalah isi, bukan kartu pajangan.
- **Buat di kepala** — tombol Buat/Tambah di kepala halaman → pindah ke ujung kanan bilah daftar.

## Pembagian gelombang
| Gelombang | Layar | Status |
|---|---|---|
| Pilot | Meja (semua), Retur Pelanggan, Pengaturan › kelompok pengaturan | selesai (`008aa68`) |
| Sendiri 17 Nov | Pesanan (tahap dropdown, panel kanan hanya saat dipilih), Pesanan Khusus (templat daftar + lini masa vertikal), Tanya KN, panel rincian global, kartu beranda | selesai |
| Keuangan | Beranda Keuangan (kartu berklik), Antar-PT, Bagan Akun (lingkup ikut PT), Lembar Insentif | selesai (`02c6c4e`) |
| Gudang | Barang Masuk / Keluar / Cutting satu pola, Lokasi Rak, SPK Inspeksi | selesai (`ba42d6d`) |
| Produk | Produk & Harga (alat admin dipindah), rincian produk | selesai (`657605f`) |
| Pengaturan | Hak akses per peran (matriks tanpa gulir), Peran & Hak Akses, Aturan Persetujuan, Kontrol dua orang | selesai (`df4edf6`) |
| Pembelian | PO, PR, Tagihan Supplier, Order Makloon, Retur ke Supplier | selesai (`10ad5fc`) |
| Keuangan-2 | rekonsiliasi, kasus, profitabilitas, faktur pajak, meja kredit, titipan, aset, buku besar, posting gagal, amandemen, kontrabon, GR/IR, RFQ | selesai (`16f93c9`, `f8ab4d0`) |
| Lain-lain | R&D sample/desain/spesifikasi, permintaan desain, transfer, gaji, kas kecil, eskalasi, kontrak, klaim makloon, antrean cetak, pesanan sample, perbaikan, produksi, penjadwal | selesai (`82e92e7`, `0a0cd9b`, `7b2ab43`) |

## Sesudah semua gelombang (17 Nov, pohon akhir)
Kandidat tersisa = sebagian besar PENGECUALIAN SAH (lihat "Cara membaca kolom"): pengalih bagian/mode, angka isi
laporan (arus kas, perubahan ekuitas, wizard kontrabon), kartu ringkasan anggaran. Sisa nyata dicatat untuk gelombang
berikut bila pemilik meminta.

**Bukti uji pohon akhir (`b700c06`)** — jest penuh 190 suite: 1500 lulus, 9 gagal = himpunan lama yang sama persis
(phase3P3 D-05/D-07×2, roleGateSweep2 kasbon, phase4R1 Kwitansi×3, fe07ReturnErrors, phase3P8Activation D-01) ·
`verify_ui_standard.py` tanpa pelanggaran baru · `verify_escape_layers.py` LULUS · gate `--ci` keluar 1 (merah lama:
pagar gudang E4.1, 8 endpoint) tetapi `bandingkan_pelanggaran_gate.py` terhadap
`garis-dasar-gate/2026-11-16_MPT4b_K82_gate_ci.log` = **tidak ada pelanggaran baru**. Log:
`garis-dasar-gate/2026-11-17_pola_ui_gate_ci.log`.

57 berkas · chip/tab saringan 22 · bilah penjelasan 7 · kartu angka tanpa klik 60 · tombol buat di kepala 2

| Berkas | Chip/tab saringan | Bilah penjelasan | Kartu angka tanpa klik | Buat di kepala |
|---|---|---|---|---|
| `features/purchasing/Supplier360Panel.jsx` | 2 |  | 2 |  |
| `features/finance/BudgetView.jsx` |  |  | 5 |  |
| `features/finance/cases/FinanceCasesView.jsx` |  |  | 5 |  |
| `features/finance/CashFlowTab.jsx` |  |  | 4 |  |
| `features/finance/EquityChangesTab.jsx` |  |  | 4 |  |
| `features/finance/ProfitabilityView.jsx` |  |  | 4 |  |
| `features/purchasing/contrabon/ContraBonCreateWizard.jsx` |  |  | 4 |  |
| `features/purchasing/contrabon/ExchangeSchedulesTab.jsx` |  |  | 4 |  |
| `features/purchasing/contrabon/UnbilledReceiptsTab.jsx` |  |  | 4 |  |
| `features/hr/AttendanceView.jsx` |  |  | 3 |  |
| `features/crm/Customer360Panel.jsx` | 2 |  |  |  |
| `features/wms/StockOpnameTab.jsx` | 2 |  |  |  |
| `features/wms/inventory/InventorySummaryCards.jsx` |  |  | 2 |  |
| `features/admin/uom/UomConversionView.jsx` |  | 1 |  |  |
| `features/costing/CostingView.jsx` |  |  | 1 |  |
| `features/crm/CustomerCardSections.jsx` |  |  | 1 |  |
| `features/designer/DesignerKpiTrendChart.jsx` | 1 |  |  |  |
| `features/designer/DesignerKpiView.jsx` |  |  | 1 |  |
| `features/desks/RoleDesk.jsx` |  |  | 1 |  |
| `features/export/ColumnPicker.jsx` | 1 |  |  |  |
| `features/export/CoveragePanel.jsx` | 1 |  |  |  |
| `features/finance/ARAgingView.jsx` |  |  | 1 |  |
| `features/finance/ClosingView.jsx` |  |  | 1 |  |
| `features/finance/PeriodUnlockView.jsx` |  |  | 1 |  |
| `features/finance/TaxOutputRecon.jsx` |  |  | 1 |  |
| `features/finance/amendments/AmendmentCenterView.jsx` |  |  | 1 |  |
| `features/finance/bank/BankRulesSettingsView.jsx` | 1 |  |  |  |
| `features/finance/bank/ReconMatchModal.jsx` | 1 |  |  |  |
| `features/finance/bank/ReconPayablePicker.jsx` | 1 |  |  |  |
| `features/finance/payments/ReceivePaymentModal.jsx` | 1 |  |  |  |
| `features/home/FinanceHomeCard.jsx` |  |  | 1 |  |
| `features/hr/KpiView.jsx` |  |  | 1 |  |
| `features/hr/MyPayslipCard.jsx` | 1 |  |  |  |
| `features/incentive/IncentiveSetupView.jsx` |  | 1 |  |  |
| `features/incentive/IncentiveSheetDetail.jsx` |  | 1 |  |  |
| `features/internal_requests/InternalRequestsView.jsx` |  |  | 1 |  |
| `features/inventory/InventoryStatusBoard.jsx` |  |  | 1 |  |
| `features/inventory/lots/LotsView.jsx` |  | 1 |  |  |
| `features/logistics/LogisticsView.jsx` |  |  |  | 1 |
| `features/orders/RestockPanel.jsx` |  | 1 |  |  |
| `features/pdf/PdfEditorTabs.jsx` | 1 |  |  |  |
| `features/pettycash/VehicleLogsView.jsx` |  |  | 1 |  |
| `features/purchasing/PoBoardView.jsx` |  |  | 1 |  |
| `features/purchasing/PurchaseRequisitions.jsx` |  | 1 |  |  |
| `features/purchasing/ReorderSuggestions.jsx` |  |  | 1 |  |
| `features/purchasing/makloon/MakloonClaimRecapView.jsx` |  |  | 1 |  |
| `features/purchasing/supplier-items/SupplierItemImportModal.jsx` | 1 |  |  |  |
| `features/sales/ReturnDetail.jsx` | 1 |  |  |  |
| `features/sales/ReturnPoliciesView.jsx` |  |  |  | 1 |
| `features/sales_admin/SalesAdminDesk.jsx` |  |  | 1 |  |
| `features/samples/SampleAdminDesk.jsx` |  |  | 1 |  |
| `features/settings/config/SettingsBrowser.jsx` | 1 |  |  |  |
| `features/settings/entities/EntityReadinessPanel.jsx` | 1 |  |  |  |
| `features/settings/masters/ClientDatasetImportView.jsx` | 1 |  |  |  |
| `features/tanya/TanyaActions.jsx` | 1 |  |  |  |
| `features/wms/InventoryStockView.jsx` | 1 |  |  |  |
| `features/wms/RollGradePanel.jsx` |  | 1 |  |  |


## Daftar kandidat (keadaan 17 Nov, sebelum gelombang agen digabung)
92 berkas · chip/tab saringan 64 · bilah penjelasan 8 · kartu angka tanpa klik 78 · tombol buat di kepala 6

| Berkas | Chip/tab saringan | Bilah penjelasan | Kartu angka tanpa klik | Buat di kepala |
|---|---|---|---|---|
| `features/admin/PurchaseOrderManagement.jsx` | 1 |  | 1 | 1 |
| `features/purchasing/PurchaseRequisitions.jsx` | 1 | 1 | 1 |  |
| `features/purchasing/VendorBillsView.jsx` | 1 |  | 1 | 1 |
| `features/finance/BankReconciliationView.jsx` | 1 |  | 6 |  |
| `features/finance/cases/FinanceCasesView.jsx` | 2 |  | 5 |  |
| `features/finance/ProfitabilityView.jsx` | 1 |  | 4 |  |
| `features/purchasing/Supplier360Panel.jsx` | 2 |  | 2 |  |
| `features/finance/amendments/AmendmentCenterView.jsx` | 1 |  | 1 |  |
| `features/purchasing/MakloonOrdersView.jsx` | 1 |  |  | 1 |
| `features/purchasing/PurchaseReturns.jsx` | 1 |  |  | 1 |
| `features/finance/BudgetView.jsx` |  |  | 5 |  |
| `features/admin/scheduler/SchedulerView.jsx` |  |  | 4 |  |
| `features/finance/CashFlowTab.jsx` |  |  | 4 |  |
| `features/finance/EquityChangesTab.jsx` |  |  | 4 |  |
| `features/production/ProductionView.jsx` |  |  | 4 |  |
| `features/purchasing/contrabon/ContraBonCreateWizard.jsx` |  |  | 4 |  |
| `features/purchasing/contrabon/ExchangeSchedulesTab.jsx` |  |  | 4 |  |
| `features/purchasing/contrabon/UnbilledReceiptsTab.jsx` |  |  | 4 |  |
| `features/hr/AttendanceView.jsx` |  |  | 3 |  |
| `features/inspections/InspectionsView.jsx` | 3 |  |  |  |
| `features/rnd/RndSamplesView.jsx` | 3 |  |  |  |
| `features/crm/Customer360Panel.jsx` | 2 |  |  |  |
| `features/finance/TaxInvoices.jsx` | 2 |  |  |  |
| `features/wms/StockOpnameTab.jsx` | 2 |  |  |  |
| `features/wms/TransferManagement.jsx` | 2 |  |  |  |
| `features/wms/inventory/InventorySummaryCards.jsx` |  |  | 2 |  |
| `features/admin/uom/UomConversionView.jsx` |  | 1 |  |  |
| `features/costing/CostingView.jsx` |  |  | 1 |  |
| `features/crm/CustomerCardSections.jsx` |  |  | 1 |  |
| `features/design/DesignRequestsView.jsx` | 1 |  |  |  |
| `features/designer/DesignerKpiTrendChart.jsx` | 1 |  |  |  |
| `features/designer/DesignerKpiView.jsx` |  |  | 1 |  |
| `features/desks/RoleDesk.jsx` |  |  | 1 |  |
| `features/export/ColumnPicker.jsx` | 1 |  |  |  |
| `features/export/CoveragePanel.jsx` | 1 |  |  |  |
| `features/finance/ARAgingView.jsx` |  |  | 1 |  |
| `features/finance/ClosingView.jsx` |  |  | 1 |  |
| `features/finance/CreditDeskView.jsx` | 1 |  |  |  |
| `features/finance/CustomerCreditView.jsx` | 1 |  |  |  |
| `features/finance/FixedAssetsView.jsx` | 1 |  |  |  |
| `features/finance/GeneralLedger.jsx` | 1 |  |  |  |
| `features/finance/PeriodUnlockView.jsx` |  |  | 1 |  |
| `features/finance/PostingFailuresView.jsx` | 1 |  |  |  |
| `features/finance/TaxOutputRecon.jsx` |  |  | 1 |  |
| `features/finance/bank/BankRulesSettingsView.jsx` | 1 |  |  |  |
| `features/finance/bank/ReconMatchModal.jsx` | 1 |  |  |  |
| `features/finance/bank/ReconPayablePicker.jsx` | 1 |  |  |  |
| `features/finance/interco/IntercoView.jsx` |  |  | 1 |  |
| `features/finance/payments/ReceivePaymentModal.jsx` | 1 |  |  |  |
| `features/home/FinanceHomeCard.jsx` |  |  | 1 |  |
| `features/hr/KpiView.jsx` |  |  | 1 |  |
| `features/hr/MyPayslipCard.jsx` | 1 |  |  |  |
| `features/hr/PayComponentsView.jsx` | 1 |  |  |  |
| `features/hr/PayrollRemittancesView.jsx` | 1 |  |  |  |
| `features/incentive/IncentiveSetupView.jsx` |  | 1 |  |  |
| `features/incentive/IncentiveSheetDetail.jsx` |  | 1 |  |  |
| `features/incentive/IncentiveSheetsView.jsx` | 1 |  |  |  |
| `features/internal_requests/InternalRequestsView.jsx` |  |  | 1 |  |
| `features/inventory/InventoryStatusBoard.jsx` |  |  | 1 |  |
| `features/inventory/lots/LotsView.jsx` |  | 1 |  |  |
| `features/logistics/LogisticsView.jsx` |  |  |  | 1 |
| `features/manager/EscalationManagement.jsx` | 1 |  |  |  |
| `features/orders/RestockPanel.jsx` |  | 1 |  |  |
| `features/pdf/PdfEditorTabs.jsx` | 1 |  |  |  |
| `features/pettycash/PettyCashView.jsx` | 1 |  |  |  |
| `features/pettycash/VehicleLogsView.jsx` |  |  | 1 |  |
| `features/purchasing/GrIrView.jsx` | 1 |  |  |  |
| `features/purchasing/PoBoardView.jsx` |  |  | 1 |  |
| `features/purchasing/RFQView.jsx` | 1 |  |  |  |
| `features/purchasing/ReorderSuggestions.jsx` |  |  | 1 |  |
| `features/purchasing/contrabon/ContraBonsView.jsx` | 1 |  |  |  |
| `features/purchasing/contracts/ContractsView.jsx` | 1 |  |  |  |
| `features/purchasing/makloon/MakloonClaimRecapView.jsx` |  |  | 1 |  |
| `features/purchasing/makloon/MakloonClaimsView.jsx` | 1 |  |  |  |
| `features/purchasing/supplier-items/SupplierItemImportModal.jsx` | 1 |  |  |  |
| `features/rfid/PrinterQueuePanel.jsx` | 1 |  |  |  |
| `features/rnd/RndDesignsView.jsx` | 1 |  |  |  |
| `features/rnd/RndSpecsView.jsx` | 1 |  |  |  |
| `features/sales/ReturnDetail.jsx` | 1 |  |  |  |
| `features/sales/ReturnPoliciesView.jsx` |  |  |  | 1 |
| `features/sales_admin/SalesAdminDesk.jsx` |  |  | 1 |  |
| `features/samples/SampleAdminDesk.jsx` |  |  | 1 |  |
| `features/samples/SampleOrdersView.jsx` | 1 |  |  |  |
| `features/settings/ApprovalRulesSettings.jsx` |  | 1 |  |  |
| `features/settings/config/SettingsBrowser.jsx` | 1 |  |  |  |
| `features/settings/entities/EntityReadinessPanel.jsx` | 1 |  |  |  |
| `features/settings/masters/ClientDatasetImportView.jsx` | 1 |  |  |  |
| `features/tanya/TanyaActions.jsx` | 1 |  |  |  |
| `features/wms/InventoryStockView.jsx` | 1 |  |  |  |
| `features/wms/RollGradePanel.jsx` |  | 1 |  |  |
| `features/wms/grn/GoodsReceiptsView.jsx` | 1 |  |  |  |
| `features/wms/repair/RepairOrdersView.jsx` | 1 |  |  |  |

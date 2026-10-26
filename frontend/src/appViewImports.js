// appViewImports — DAFTAR VIEW LAZY untuk `AppViewRouter.jsx` (fase 3 · P1).
//
// Dipindah apa adanya dari AppViewRouter.jsx supaya router di bawah batas 500 baris (KN_00 GATE 2)
// tanpa mengubah sintaks `activeView === "x" && <Komponen …/>` yang diurai guardrail
// (`verify_desk_targets`, `verify_home_kpi`, `verify_approval_queues`, `verify_access_catalog_nav`,
// `audit_config_wiring`). Skrip audit yang memetakan view → berkas (`audit_ia.py`,
// `audit_sales_roles_ux.py`) membaca BERKAS INI + router. Path impor relatif tetap sama (satu folder).
//
// P3 — CODE SPLITTING: setiap view feature dimuat via React.lazy() sehingga bundle
// utama tidak lagi memuat SELURUH view sekaligus (dulu main.js ~3.0 MB).
import { lazy } from "react";

// ── Lazy views (dipisah per chunk) ──────────────────────────────────────────
export const SalesPortal = lazy(() => import("./features/sales/SalesPortal").then((m) => ({ default: m.SalesPortal })));
export const PriceApprovals = lazy(() => import("./features/sales/PriceApprovals"));
export const OrdersView = lazy(() => import("./features/orders/OrdersView"));
export const CrmView = lazy(() => import("./features/crm/CrmView"));
export const OperationsView = lazy(() => import("./features/wms/OperationsView"));
// FASE I — SPK Inspeksi & QC sebagai DOKUMEN (`<ENT>/INS-#####`). Layar QC lama di
// atas tetap ada sebagai antrean karantina; dokumennya hidup di layar ini.
export const QcHubView = lazy(() => import("./features/inspections/QcHubView"));
export const InspectionsView = lazy(() => import("./features/inspections/InspectionsView"));
export const DocumentsView = lazy(() => import("./features/documents/DocumentsView"));
export const AdminView = lazy(() => import("./features/admin/AdminView"));
export const CostingView = lazy(() => import("./features/costing/CostingView"));
export const ARAgingView = lazy(() => import("./features/finance/ARAgingView"));
export const AdvanceReportView = lazy(() => import("./features/finance/AdvanceReportView"));
export const StoreCreditView = lazy(() => import("./features/finance/StoreCreditView"));
export const BankAccountsView = lazy(() => import("./features/finance/BankAccountsView"));
export const BankReconciliationView = lazy(() => import("./features/finance/BankReconciliationView"));
export const FinanceCasesView = lazy(() => import("./features/finance/cases/FinanceCasesView"));
export const FixedAssetsView = lazy(() => import("./features/finance/FixedAssetsView"));
export const ProductionView = lazy(() => import("./features/production/ProductionView"));
export const SchedulerView = lazy(() => import("./features/admin/scheduler/SchedulerView"));
export const ChartOfAccounts = lazy(() => import("./features/finance/ChartOfAccounts"));
export const GeneralLedger = lazy(() => import("./features/finance/GeneralLedger"));
export const GroupConsolidationView = lazy(() => import("./features/finance/GroupConsolidationView"));
export const FinancialStatementsView = lazy(() => import("./features/finance/FinancialStatementsView"));
export const ClosingView = lazy(() => import("./features/finance/ClosingView"));
export const PeriodUnlockView = lazy(() => import("./features/finance/PeriodUnlockView"));
export const PostingFailuresView = lazy(() => import("./features/finance/PostingFailuresView"));
export const BiFinanceView = lazy(() => import("./features/finance/BiFinanceView"));
export const FinanceTowerView = lazy(() => import("./features/finance/FinanceTowerView"));
export const ProfitabilityView = lazy(() => import("./features/finance/ProfitabilityView"));
export const CashFlowForecastView = lazy(() => import("./features/finance/CashFlowForecastView"));
export const BudgetView = lazy(() => import("./features/finance/BudgetView"));
export const TaxCenterView = lazy(() => import("./features/finance/TaxCenterView"));
export const ManagerDashboard = lazy(() => import("./features/manager/ManagerDashboard"));
export const SalesHome = lazy(() => import("./features/home/SalesHome"));
export const AdminHome = lazy(() => import("./features/home/AdminHome"));
// EPIC 1 · PS-18 — Dasbor Manajer (antrean persetujuan, target tim, keterlambatan hari ini).
export const ManagerHome = lazy(() => import("./features/home/ManagerHome"));
export const ReturnDeskSummaryCard = lazy(() => import("./features/home/ReturnDeskSummaryCard"));
export const PurchaseOrderManagement = lazy(() => import("./features/admin/PurchaseOrderManagement"));
export const BlanketPOView = lazy(() => import("./features/purchasing/BlanketPOView"));
// FASE P — Papan PO per lini (progres tahap seperti kertas kerja MD).
export const PoBoardView = lazy(() => import("./features/purchasing/PoBoardView"));
export const InventoryStatusBoard = lazy(() => import("./features/inventory/InventoryStatusBoard"));
export const StockBucketsView = lazy(() => import("./features/inventory/StockBucketsView"));
export const LotsView = lazy(() => import("./features/inventory/lots/LotsView"));
export const InterCompanyTransfers = lazy(() => import("./features/transfers/InterCompanyTransfers"));
export const EscalationManagement = lazy(() => import("./features/manager/EscalationManagement"));
export const TaxInvoices = lazy(() => import("./features/finance/TaxInvoices"));
export const SalesReturns = lazy(() => import("./features/sales/SalesReturns"));
export const ReturnPoliciesView = lazy(() => import("./features/sales/ReturnPoliciesView"));
export const SpecialOrders = lazy(() => import("./features/sales/SpecialOrders"));
export const SamplePriceMaster = lazy(() => import("./features/samples/SamplePriceMaster"));
export const PricelistView = lazy(() => import("./features/sales/PricelistView"));
// F1b (D-14) — Daftar Harga per Pelanggan (harga langganan + penjagaan batas bawah).
export const CustomerPricelistView = lazy(() => import("./features/sales/CustomerPricelistView"));
export const CatalogWorkspace = lazy(() => import("./features/catalog/CatalogWorkspace"));
export const ColorLibraryView = lazy(() => import("./features/sales/ColorLibraryView"));
export const DomainRegistryView = lazy(() => import("./features/admin/domain/DomainRegistryView"));
export const UomConversionView = lazy(() => import("./features/admin/uom/UomConversionView"));
export const ApprovalInbox = lazy(() => import("./features/approvals/ApprovalInbox"));
export const MyApprovalsView = lazy(() => import("./features/approvals/MyApprovalsView"));
// FASE E-8 (E8.7/E8.20) — dua MEJA KERJA: Admin Sales (alur pesanan & pemenuhan) dan
// Finance (uang masuk & pajak keluaran). Keduanya menyusun antrean dari mesin yang sudah
// ada (papan pending SO · backorder · retur · PIN · penagihan) — bukan mesin baru (E8.11).
export const SalesAdminDesk = lazy(() => import("./features/sales_admin/SalesAdminDesk"));
export const FinanceDesk = lazy(() => import("./features/finance/FinanceDesk"));

// FASE G-1 — Pusat Amandemen (koreksi ber-alasan, ber-dampak, ber-penyetuju).
export const AmendmentCenterView = lazy(() => import("./features/finance/amendments/AmendmentCenterView"));
export const ApprovalRulesSettings = lazy(() => import("./features/settings/ApprovalRulesSettings"));
// FASE E-4 (E4d) — satu layar untuk semua master berlapis global → badan usaha.
export const EntityMastersView = lazy(() => import("./features/settings/masters/EntityMastersView"));
export const MakloonClaimRecapView = lazy(() => import("./features/purchasing/makloon/MakloonClaimRecapView"));
export const ClientDatasetImportView = lazy(() => import("./features/settings/masters/ClientDatasetImportView"));
export const GradeMasterView = lazy(() => import("./features/settings/masters/GradeMasterView"));
// FASE E-3 — layar "Badan Usaha & Akses" (entitas + akun + kesiapan) dalam satu pintu.
export const EntitiesAccessView = lazy(() => import("./features/settings/entities/EntitiesAccessView"));
// FASE E-4 (E4.1) — Master Gudang: mode pemakaian (bersama / khusus badan usaha),
// isi gudang per pemilik stok, dan pagar agar barang tidak terkurung.
export const WarehouseMasterView = lazy(() => import("./features/wms/warehouses/WarehouseMasterView"));
// FASE G-0 — Pusat Pengaturan (satu pintu semua konfigurasi: cari, penjelasan,
// simulator "coba dulu", jejak lapisan, riwayat, berlaku-sejak, Daftar Dampak).
export const SettingsHub = lazy(() => import("./features/settings/config/SettingsHub"));
// Fase 3 · P2 (P16-K1) — Pengaturan per domain (`settings-cfg-*`), Perangkat gabungan (D-29), Koreksi Harga,
// Template Dokumen (D-01: Template PDF + Template Dokumen Dasar).
export const SettingsGroupView = lazy(() => import("./features/settings/cfg/SettingsGroupView"));
export const DevicesView = lazy(() => import("./features/settings/devices/DevicesView"));
export const PriceCorrectionsView = lazy(() => import("./features/settings/config/PriceCorrectionsView"));
export const DocTemplatesView = lazy(() => import("./features/pdf/DocTemplatesView"));
export const SuppliersView = lazy(() => import("./features/purchasing/SuppliersView"));
export const MakloonsView = lazy(() => import("./features/purchasing/MakloonsView"));
export const ProcessRecipesView = lazy(() => import("./features/purchasing/ProcessRecipesView"));
export const MakloonOrdersView = lazy(() => import("./features/purchasing/MakloonOrdersView"));
// FASE D (PS-04/PS-11 · D-05/D-07/D-09) — klaim selisih makloon & kontrak mitra
export const MakloonClaimsView = lazy(() => import("./features/purchasing/makloon/MakloonClaimsView"));
export const ContractsView = lazy(() => import("./features/purchasing/contracts/ContractsView"));
export const InternalPricesView = lazy(() => import("./features/interco_prices/InternalPricesView"));
export const AmendmentReasonsPanel = lazy(() => import("./features/finance/amendments/AmendmentReasonsPanel"));
export const IncentiveRatesEditor = lazy(() => import("./features/crm/IncentiveRatesEditor"));
export const BankRulesSettingsView = lazy(() => import("./features/finance/bank/BankRulesSettingsView"));
export const SupplierItemsView = lazy(() => import("./features/purchasing/supplier-items/SupplierItemsView"));
export const PurchaseApprovalView = lazy(() => import("./features/purchasing/PurchaseApprovalView"));
export const CashManagementView = lazy(() => import("./features/purchasing/CashManagementView"));
export const PurchaseReturns = lazy(() => import("./features/purchasing/PurchaseReturns"));
export const VendorBillsView = lazy(() => import("./features/purchasing/VendorBillsView"));
// FASE G-7 — Kontrabon (siklus tukar faktur supplier): gabung banyak faktur jadi satu
// tanda terima + satu pembayaran, plus "GR belum ditagih" & jadwal tukar faktur.
export const ContraBonsView = lazy(() => import("./features/purchasing/contrabon/ContraBonsView"));
// FASE G-6 — Transaksi Antar Entitas (jual-beli antar-PT): dokumen kembar, saldo
// pasangan PT, settlement/netting.
export const IntercoView = lazy(() => import("./features/finance/interco/IntercoView"));
// FASE E-7 (E7d) — Permintaan Internal: sales minta barang dari badan usaha lain,
// admin/manajer menjadikannya transaksi antar-PT.
export const InternalRequestsView = lazy(() => import("./features/internal_requests/InternalRequestsView"));
export const KeepPendingPanel = lazy(() => import("./features/sales_admin/KeepPendingPanel"));   // UAT 24 Okt (P13.3)
export const RepairOrdersView = lazy(() => import("./features/wms/repair/RepairOrdersView"));     // UAT 24 Okt (P7)
// FASE D — Permintaan Desain (papan kanban · penugasan · rapor desainer)
export const DesignRequestsView = lazy(() => import("./features/design/DesignRequestsView"));
export const LogisticsView = lazy(() => import("./features/logistics/LogisticsView"));   // FB-02
export const LandedCostView = lazy(() => import("./features/purchasing/LandedCostView"));
export const InputTaxView = lazy(() => import("./features/purchasing/InputTaxView"));
export const RFQView = lazy(() => import("./features/purchasing/RFQView"));
export const PurchaseRequisitions = lazy(() => import("./features/purchasing/PurchaseRequisitions"));
export const ReorderSuggestions = lazy(() => import("./features/purchasing/ReorderSuggestions"));
export const EmployeesView = lazy(() => import("./features/hr/EmployeesView"));
export const OrgUnitsView = lazy(() => import("./features/hr/OrgUnitsView"));
export const EmployeeSelfService = lazy(() => import("./features/hr/EmployeeSelfService"));
export const AttendanceView = lazy(() => import("./features/hr/AttendanceView"));
export const AttendanceSetupView = lazy(() => import("./features/hr/AttendanceSetupView"));
export const LiveTrackingView = lazy(() => import("./features/hr/LiveTrackingView"));
export const VisitsView = lazy(() => import("./features/hr/VisitsView"));
export const PayrollRunsView = lazy(() => import("./features/hr/PayrollRunsView"));
export const PayslipsView = lazy(() => import("./features/hr/PayslipsView"));
export const LeaveView = lazy(() => import("./features/hr/LeaveView"));
export const OvertimeView = lazy(() => import("./features/hr/OvertimeView"));
export const KpiView = lazy(() => import("./features/hr/KpiView"));
export const DesignGalleryView = lazy(() => import("./features/hr/DesignGalleryView"));
export const HrAnalyticsView = lazy(() => import("./features/hr/HrAnalyticsView"));
export const StockAnalyticsView = lazy(() => import("./features/inventory/StockAnalyticsView"));
export const ExportCenterView = lazy(() => import("./features/export/ExportCenterView"));
export const LocationPutawayView = lazy(() => import("./features/wms/LocationPutawayView"));
export const GoodsReceiptsView = lazy(() => import("./features/wms/grn/GoodsReceiptsView"));
export const OutboundView = lazy(() => import("./features/wms/OutboundView"));
export const CuttingOpsView = lazy(() => import("./features/wms/CuttingOpsView"));
export const ReceivingOcrSettings = lazy(() => import("./features/settings/ReceivingOcrSettings"));
export const RfidTagsView = lazy(() => import("./features/rfid/RfidTagsView"));
export const RfidDevicesView = lazy(() => import("./features/rfid/RfidDevicesView"));
export const RfidGateMonitorView = lazy(() => import("./features/rfid/RfidGateMonitorView"));
export const RfidLocationsView = lazy(() => import("./features/rfid/RfidLocationsView"));
export const CashAdvancesView = lazy(() => import("./features/pettycash/CashAdvancesView"));
export const SettlementsView = lazy(() => import("./features/pettycash/SettlementsView"));
export const ExpenseCategoriesView = lazy(() => import("./features/pettycash/ExpenseCategoriesView"));
export const GLAccountMappingView = lazy(() => import("./features/finance/GLAccountMappingView"));
export const ReimbursePayablesView = lazy(() => import("./features/pettycash/ReimbursePayablesView"));
export const VehicleLogsView = lazy(() => import("./features/pettycash/VehicleLogsView"));
export const PdfTemplateDesigner = lazy(() => import("./features/pdf/PdfTemplateDesigner"));
export const RoleDesk = lazy(() => import("./features/desks/RoleDesk"));
export const TanyaKnView = lazy(() => import("./features/tanya/TanyaKnView"));   // Tanya KN F3
// REVISI SAMPEL — meja & daftar pesanan sample
export const SampleAdminDesk = lazy(() => import("./features/samples/SampleAdminDesk"));
export const SampleOrdersView = lazy(() => import("./features/samples/SampleOrdersView"));
export const DocumentCenter = lazy(() => import("./features/documents/DocumentCenter"));
// FASE G-4 — Jejak Dokumen (relasi `refs[]` dua arah; jangkar bebas, termasuk QR cetak).
export const DocTraceView = lazy(() => import("./features/documents/trace/DocTraceView"));
// FASE G-2 — Rencana Pembayaran fleksibel + denda sebagai dokumen.
export const PaymentPlansView = lazy(() => import("./features/finance/payments/PaymentPlansView"));
// FASE F — R&D & Desain: spesifikasi → labdip/proofing → kontrak harga (hulu rantai).
export const RndSpecsView = lazy(() => import("./features/rnd/RndSpecsView"));
export const RndSamplesView = lazy(() => import("./features/rnd/RndSamplesView"));
export const SampleTypeGalleryView = lazy(() => import("./features/rnd/SampleTypeGalleryView"));
export const RndDesignsView = lazy(() => import("./features/rnd/RndDesignsView"));
export const RndReportsView = lazy(() => import("./features/rnd/RndReportsView"));
// PS-18 — menu DESAINER (terpisah dari R&D): KPI desainer + eskalasi SLA aktif.
export const DesignerKpiView = lazy(() => import("./features/designer/DesignerKpiView"));
export const ContentCalendar = lazy(() => import("./features/marketing/ContentCalendar"));
export const MktCampaigns = lazy(() => import("./features/marketing/Campaigns"));
export const MarketingAnalytics = lazy(() => import("./features/marketing/MarketingAnalytics"));
export const SocialAccounts = lazy(() => import("./features/marketing/SocialAccounts"));
export const DivisionsView = lazy(() => import("./features/designer/DivisionsView"));

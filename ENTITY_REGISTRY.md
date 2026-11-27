# ENTITY REGISTRY — SSOT Map
## Kain Nusantara Platform

**WAJIB DIBACA SEBELUM MEMBUAT COLLECTION, SCHEMA, ATAU ENDPOINT BARU.**

File ini adalah satu-satunya sumber kebenaran untuk semua entitas bisnis.
Sebelum membuat apapun yang baru, tanya: **"Apakah ini sudah ada di sini?"**

**Update wajib setiap kali ada:**
- Collection baru ditambahkan
- Schema baru dibuat
- Endpoint baru untuk entitas yang sudah ada
- Component baru untuk entitas yang sudah ada

---

## 📋 QUICK LOOKUP TABLE

| Entitas | Collection | Router | Schema | Frontend Component |
|---|---|---|---|---|
| User | `users` | `routers/auth.py`, `routers/users.py` | `UserCreate` | `AdminView` (tab Users) |
| Session (Auth) | `sessions` | `routers/auth.py` | — | `LoginScreen` |
| Product | `products` | `routers/products.py` | `ProductPayload` | `ProductCard`, `AdminView` (tab Product) |
| **Registry Enum Domain** *(FASE A — KODE, bukan koleksi)* | `backend/domain_registry.py` | `routers/enums.py` (`GET /api/enums*`) | — | `hooks/useDomainEnums.js`, `DomainRegistryView` (Produk & Harga → Registry Domain) |
| **Riwayat & Override Grade Roll** *(FASE A · PS-09)* | `inventory_rolls.grade_history[]` | `routers/qc_inspection.py`, `services/grade_service.py` | `RollGradeOverrideIn` | `RollGradePanel` (Gudang → Inspeksi QC → tombol Grade) |
| Customer | `customers` | `routers/customers.py` | `CustomerCreate` | `CustomerPanel`, `AdminView` (tab Customer) |
| Warehouse | `warehouses` | `routers/warehouses.py` | `WarehousePayload` | `AdminView` (tab Warehouse) |
| UOM | `uoms` | `routers/uoms.py` | `UOMPayload` | `AdminView` (tab UOM) |
| Sales Order | `sales_orders` | `routers/sales_orders.py` | `SalesOrderCreate` | `SalesPortal`, `OrdersView`, `CartPanel` |
| Invoice | `invoices` | `routers/invoices.py` | `PaymentSimulationCreate` | `DocumentsView` |
| Inventory Balance | `inventory_balances` | `routers/inventory.py` | — | `InventoryStockView` |
| Inventory Roll *(IMPLEMENTED Fase 0.5)* | `inventory_rolls` | `routers/inventory.py`, `services/roll_service.py` | `RollPayload` | `InventoryStockView`, `SalesPortal` |
| Inventory Movement | `inventory_movements` | `routers/inventory.py` | — | `InventoryStockView` (tab Ledger) |
| WMS Task | `wms_tasks` | `routers/wms.py` | `WMSTaskCreate` | `ScannerTaskPanel` |
| Inbound Task | `wms_tasks` *(flow_type=inbound)* | `routers/inbound_receiving.py` | — | `InboundScanInterface` |
| Outbound Task | `wms_tasks` *(flow_type=outbound)* | `routers/outbound_picking.py` | — | `OutboundScanInterface` |
| Transfer | `warehouse_transfers` | `routers/transfers.py` | `TransferCreate` | `TransferManagement` |
| Cycle Count | `cycle_count_sessions` | `routers/cycle_count.py` | — | `CycleCount` |
| Purchase Order | `purchase_orders` | `routers/purchase_orders.py` | `PurchaseOrderCreate` | `PurchaseOrderManagement` |
| Makloon (Subkontraktor) | `makloons` | `routers/makloons.py` | `MakloonCreate` | `MakloonsView`, `Makloon360Panel` (Pembelian → Master Pembelian) |
| Resep Proses (Konversi) | `process_recipes` | `routers/process_recipes.py` | `ProcessRecipeCreate` | `ProcessRecipesView` (Pembelian → Master Pembelian) |
| Rute Produk (MP-T1) | `product_routes` | `routers/product_routes.py` | — (dict, divalidasi `product_route_service.validate`) | `FamilyRoutesTab` (Master Produk › induk › Rute) |
| Order Makloon (Subkontrak) | `makloon_orders` | `routers/makloon_orders.py`, `services/makloon_order_service.py` | — | `MakloonOrdersView`, `MakloonOrderCreateModal` (Pembelian → PO → tab Order Makloon) |
| Document Template | `document_templates` | `routers/documents.py` | `TemplatePayload` | `DocumentsView`, `AdminView` (tab Templates) |
| Generated Document | `generated_documents` | `routers/documents.py` | `DocumentGenerate` | `DocumentsView` |
| Permission Settings | `permission_settings` | `routers/admin.py` | `PermissionUpdate` | `AdminView` (tab Permissions) |
| Audit Log | `audit_logs` | `routers/audit.py` | — | `AdminView` (tab Audit) |
| Onboarding | `user_onboarding` | `routers/onboarding.py` | — | `OnboardingPanel` |
| KPI Design *(FASE H5)* | `hr_kpi` | `routers/hr_kpi.py` | `KpiInput`, `KpiUpdate` | `KpiView`, `MyKpiCard` (ESS) |
| Design Gallery *(FASE H5)* | `design_gallery` | `routers/design_gallery.py` | `GalleryInput`, `GalleryUpdate` | `DesignGalleryView` |
| AI Integrations *(FASE H5)* | `system_settings` *(scope=integrations)* | `routers/integrations.py` | `IntegrationsUpdate` | `IntegrationsPanel` (AdminView tab Integrasi AI) |
| Kebijakan Persetujuan *(KP-T4)* | `approval_policies` | `routers/approval_policies.py`, `services/approval_policy_service.py` (dipanggil semua pintu persetujuan), katalog `approval_kinds.py` | — | `ApprovalPoliciesView` (Pengaturan › Persetujuan › Aturan Persetujuan) |
| Penomoran Dokumen *(KP-T5)* | `doc_number_formats` (+ penghitung `number_sequences`) | `core_utils.next_doc_number` (satu-satunya pembuat nomor), `services/doc_numbering_service.py`, katalog `doc_number_kinds.py`, `routers/doc_numbering.py` | `DocNumberingPut`, `DocNumberingPreview` | `DocNumberingView` (Pengaturan › Dokumen & Cetak › Penomoran Dokumen) |
| Usulan Jurnal Manual *(KF-T6)* | `journal_proposals` | `routers/gl.py` (`POST /gl/journal` → 202, `/gl/journal-proposals*`), `services/journal_proposal_service.py` | `JournalEntryCreate`, `ProposalReject` | `JournalProposalsPanel` (Buku Besar › Jurnal › Menunggu persetujuan) |
| Cara Bayar *(PM-T1)* | `payment_methods` (master berlapis `payment-methods`) | `routers/payment_methods.py` (`GET /api/payment-methods`), `routers/entity_masters.py` (kelola, `cash.configure`), `services/payment_method_service.py` (`normalize`, `get`, `active_for`, `is_cash` — dipanggil kwitansi, bayar hutang, kontrabon, biaya masuk, uang muka, denda, selisih bayar, antar-PT) | — | `config/paymentMethods.js` (`usePaymentMethods`), `EntityMastersView` (Pengaturan › Keuangan & Pajak › Master per Badan Usaha) |
| Kode Bayar & Instruksi Bayar *(PM-T2)* | `payment_codes` (+ field pesanan `payment_method_code`, `receiving_account_id`, `receiving_account`, `payment_code`; `payment_plans.lines[].pay_code`) | `services/payment_code_service.py` (`resolve_destination` dipanggil `create_order` & override SO; `ensure_for_order` dari `confirm_core`; `ensure_for_line` untuk jadwal tagihan CR-T2; `find_in_text` untuk PM-T3; `instruction`), `routers/payment_methods.py` (`GET /api/sales-orders/{id}/payment-instruction`), `services/pdf_resolvers.py` (blok "Instruksi Pembayaran" Konfirmasi Pesanan & Faktur) | `SalesOrderCreate`, `SoOverrideIn` | `CheckoutPaymentDestination` (checkout desktop & HP), `OrderPaymentInstructionCard` (detail pesanan), `SalesOrderOverrideDialog` |
| Perubahan Rekening *(PM-T1)* | `bank_account_changes` | `routers/bank.py` (`POST/PATCH /bank-accounts` → 202 bila dua orang, `GET /bank-account-changes`, `POST …/{id}/decision`), `services/bank_account_change_service.py` | `BankAccountCreate`, `BankAccountUpdate`, `BankAccountChangeDecision` | `BankAccountChangesPanel`, `BankAccountForm` (Keuangan › Kas & Bank › Rekening & Saldo) |
| Pindah Saldo Kas per Rekening *(Kas & Bank 1, Tugas 3)* | `cash_account_cutovers` | `routers/cash_account_cutover.py` (`GET /kas-per-rekening/usulan`, `GET /kas-per-rekening/{entity_id}/pratinjau`, `POST …/{entity_id}/siapkan`, `POST /kas-per-rekening/usulan/{id}/setujui`, `…/tolak` — `accounting.manage`), `services/cash_account_cutover_service.py` | `PindahSaldoSiapkan`, `PindahSaldoSetujui`, `PindahSaldoTolak` | (layar Kas & Bank › Akun per rekening — Tugas 6) |
| Pindah Dana *(Kas & Bank 1, Tugas 4)* | `fund_transfers` (+ kas `cash_transactions` ber-`ref_type: fund_transfer`, `seq` kirim/biaya/terima) | `routers/fund_transfers.py` (`GET/POST /fund-transfers`, `GET /fund-transfers/{id}`, `POST …/{id}/receive` — `cash.create`, `…/approve` — `cash.approve`, `…/cancel` — `cash.delete`), `services/fund_transfer_service.py` (`buat`, `setujui`, `terima`, `batal`, `lanjut_batal`, `daftar`, `rincian`, `dalam_perjalanan` — butir tutup buku) | `FundTransferCreate`, `FundTransferReceive`, `FundTransferCancel` | (layar Kas & Bank › Pindah Dana — Tugas 6) |
| Pengajuan Kas Keluar Manual *(Kas & Bank 2, C6)* | `cash_out_requests` (+ kas `cash_transactions` ber-`ref_type: manual`, `ref_id` = id pengajuan, terbit saat disetujui) | `routers/cash.py` (`POST /cash-transactions` → 202 `{request}` bila kas keluar di atas batas `kontrol.kas_keluar_manual`), `routers/cash_out_requests.py` (`GET /cash-out-requests`, `GET /cash-out-requests/{id}` — `cash.view`, `POST …/{id}/approve` & `…/reject` — `cash.approve`, `…/cancel` — pengaju `cash.create` atau `cash.delete`), `services/cash_out_request_service.py` (`ajukan`, `kiriman_ulang`, `setujui`, `tolak`, `batal`, `daftar`, `rincian`) | `CashTransactionCreate`, `CashOutRequestReject`, `CashOutRequestCancel` | (layar Kas & Bank › Transaksi Kas, bagian Menunggu persetujuan — Tugas 4) |
| Jadwal Tagihan & Saldo Piutang *(CR-T2)* | `payment_plans` (`origin: term` = jadwal tagihan mesin per surat jalan / uang muka / nota debit; `manual` = rencana cicilan), `customer_balances` (saldo turunan per pelanggan × PT) | `services/billing_schedule_service.py` (kait `on_order_confirmed` dari `confirm_core`, `on_shipment_posted` sesudah jurnal surat jalan, `on_order_changed` dari `so_transition` status mati, `on_debit_note`; `open_lines` = satu-satunya pembaca jatuh tempo), `services/customer_balance_service.py` (`compute`, `refresh`, `get`, `rebuild_all`, `job_refresh_overdue`), `routers/customer_balances.py` (`GET /customers/{id}/billing-schedule`, `GET /customers/{id}/balance`, `POST /ar/balances/rebuild`), `scripts/build_billing_schedule.py` | — | `ARAgingDetail` (rincian pelanggan: baris jadwal tersimpan) |
| Profil Kredit Pelanggan *(CR-T1)* | `customer_credit_profiles` (satu per pelanggan × PT pesanan), `credit_profile_requests` | `routers/credit_profiles.py` (`GET /customers/{id}/credit-profile`, `POST /customers/{id}/credit-profile-requests`, `GET /credit-profile-requests`, `POST …/{id}/decision`, `POST …/{id}/cancel`), `services/credit_profile_service.py` (`effective`, `status_from` — dipakai `customer_service.compute_customer_credit`, `ar_aging_service`) | `CreditProfileRequestCreate`, `CreditProfileDecision`, `CreditProfileCancel` | `CustomerCreditTab` + `CreditProfileRequestModal` (kartu pelanggan › Kredit), `CreditProfileRequestsPanel` (Keuangan › Piutang › Kredit & Plafon) |
| Meja Insentif — data dasar *(KM-T1)* | `sales_targets` (kunci baru PT × sales × jenis periode × periode), `incentive_components`, `incentive_definitions`, `fact_shipment_sales`, `fact_collections` (turunan) | `routers/incentive.py` (`GET/PUT /api/incentive/targets`, `POST …/targets/copy`, `GET/POST/PATCH /api/incentive/components`, `GET …/definitions/current`, `GET …/reconciliation`, `POST …/facts/rebuild`; KM-T2 hanya baca: `GET …/achievement`, `GET …/achievement/sources`, `GET …/achievement/export`), `services/incentive_targets.py`, `incentive_periods.py`, `incentive_definitions.py`, `incentive_facts.py`, `incentive_achievement.py` (KM-T2) | `IncentiveTargetSave`, `IncentiveTargetCopy`, `IncentiveComponentCreate`, `IncentiveComponentUpdate`, `IncentiveFactRebuild` (`schemas_incentive.py`) | `IncentiveSetupView` (SDM › Kinerja & Insentif › Target & Aturan), `CapaianView` + `CapaianSourcesPanel` (… › Capaian, KM-T2) |
| Meja Insentif — Lembar Insentif *(KM-T3)* | `incentive_sheets` (dokumen keputusan per PT per periode bayar; baris + potret angka dasar) | `routers/incentive.py` (`GET/POST /api/incentive/sheets`, `GET …/sheets/options`, `GET …/sheets/adjustable-lines`, `GET …/sheets/{id}` (+ `drift`), `POST/PATCH/DELETE …/{id}/lines[/{line_id}]`, `POST …/{id}/refresh · submit · approve · return · cancel`, `GET …/{id}/export`), `services/incentive_sheet_service.py` | `IncentiveSheetCreate`, `IncentiveSheetLineRef`, `IncentiveSheetLineAdd`, `IncentiveSheetLinePatch`, `IncentiveSheetApprove`, `IncentiveSheetCorrection`, `IncentiveSheetReason` (`schemas_incentive.py`) | `IncentiveSheetsView` + `IncentiveSheetDetail` (SDM › Kinerja & Insentif › Lembar Insentif); tombol "Buat lembar insentif dari tampilan ini" di `CapaianView` |
| Lembar Insentif → gaji & buku besar; tagihan insentif antar-PT *(KM-T4)* | `incentive_sheets` (+ `payroll_linked`, `gl_status`, `journal_entry_id`, `journal_date`, status `approving`; baris `employee_id`, `pay_entity_id`, `input_key`, `paid_run_id`), `hr_pay_inputs` (sumber `incentive_sheet`), `hr_pay_components` (`INSENTIF`), `interco_charges` | `routers/incentive.py` (`POST …/sheets/{id}/approve` bercabang menurut `hr.payroll_commission_mode`; `GET /api/incentive/switch-readiness`), `routers/interco_charges.py` (`GET /api/interco/charges[/{id}]`, `POST …/{id}/settle`), `services/incentive_payroll.py`, `services/interco_charge_service.py`, `services/hr_payroll_service.py` (`commission_mode`, `post_run_gl`, `void_run`) | `ChargeSettleInput` (`routers/interco_charges.py`) | `IncentiveSheetDetail` (lencana jurnal, "Dibayar lewat …", pita PT belum dialihkan); kartu Kesiapan di `IncentiveSetupView`; `IntercoChargesPanel` (Antar-PT › Pinjaman Antar-PT); tarif komisi tanpa Satuan |
| Kartu "Capaian & Insentif Saya"; layar insentif lama dicabut *(KM-T5)* | — (tanpa koleksi/field baru; membaca `fact_*`, `sales_targets`, `incentive_sheets`; `incentive_rates` & `sales_incentives` tetap untuk PT bermode komisi otomatis) | `routers/incentive.py` (`GET /api/incentive/me` — login, milik sendiri; `GET …/targets` + `commission_mode(s)`), `services/incentive_me.py`; `routers/home.py` (`/api/home/sales` + `incentive_mode`, `/api/home/admin` + `incentive_payout_label`); `routers/crm.py` (`/api/sales-users` & papan peringkat dari `sales_roster`; `/api/sales/commission[-history]` 409 di PT `sheet`/`off`; `GET /api/sales/incentive/gl-status` + `mode`, `estimate`; **`GET`/`POST /api/sales-targets` dihapus**) | — | `MyIncentiveCard` (Beranda Sales, Profil Saya, HP Target & Insentif, HP Beranda PT Lembar Insentif); bagian "Komisi otomatis (cara lama)" di `IncentiveSetupView` (`LegacyRatesEditor`, `LegacySchemeEditor`) — KA-9: dipindah ke tab Skema & Tarif (`IncentiveSchemeView`), `LegacyRatesEditor` dihapus; `SalesForceDashboard`, `IncentiveSchemeEditor`, `IncentiveRatesEditor` dihapus |
| Komisi per artikel + tab Skema & Tarif *(KA-1…KA-10)* | `incentive_rates` (+ `template_id`, `product_id`, `rate_key`, `target_name`, `target_code`, `price_bands`, `price_source_rules`; indeks `uq_incentive_rate_key`), `commission_period_rules` (baru, potret aturan bulan saat akrual; indeks `uq_commission_period`), `sales_orders.items[].commission_rule` (potret aturan baris); kunci `commission.price_basis`/`price_bands`/`price_source_rules`/`achievement_multiplier`/`achievement_basis`/`achievement_tiers`; pilihan `hr.payroll_commission_mode` = `auto_and_sheet` | `routers/incentive_rates.py` (`GET …/categories`, `…/articles`, `…/articles/{template_id}/variants`, `POST …/bulk`, `GET …/export`, `POST …/import/preview`, `…/import/apply`, `…/simulate`; POST/PATCH tarif + isian artikel/varian), `services/commission_rules.py` (tarif, potret, pengali harga, hitung baris, pengali capaian, `bekukan_periode`), `services/commission_rate_service.py` (pohon, ubah banyak, Excel), `services/sales_force_service.py` (`_compute_commission_per_sku` membaca potret, `simulate_commission`), `routers/sales_orders.py:create_order` (`potret_pesanan`), `bootstrap.py` (`backfill_incentive_rate_key`, `backfill_so_line_commission_rule`), `gl_service.post_incentive_accrual` (beku sesudah jurnal), `services/incentive_payroll.py` (`MODE_BOTH`, `akru`, `lembar_ke_gaji`), `services/incentive_me.py` (rincian daftar putih) | `RatePayload`, `GenericPatch`, `BulkPayload`, `ImportApplyPayload`, `SimulatePayload` | `IncentiveSchemeView` (SDM › Kinerja & Insentif › Skema & Tarif: `SchemeSourcePicker`, `ArticleRatesTable`, `RateFormModal`, `RatesExcelImport`, `GroupRatesList`, `KartuAkrual`, `SchemeSimulation`); rincian faktor di `MyIncentiveCard` & `SalesHome` |
| Titipan Tunai Sales & Setoran *(PM-T4)* | `cash_holdings` (satu per kwitansi tunai yang menjadi titipan, nomor `TTP-`), `cash_deposits` (setoran, nomor `STT-`) (+ field `ar_receipts.cash_holding_id`) | `routers/cash_holdings.py` (`GET /api/cash-holdings`, `GET /api/cash-holdings/me/summary`, `GET/POST /api/cash-deposits`, `POST …/{id}/receive` · `/reject` · `/cancel`), `services/cash_holding_service.py` (`mode_tunai`, `periksa_batas`, `buat_titipan` dipanggil `ar_receipt_service.create_receipt`; `terima_setoran` → `cash_ledger.create_cash(ref_type="cash_deposit")`; `rekonsiliasi` = INV-TTP-01), `gl_service.post_cash_holding` / `reverse_cash_holding` | `DepositIn`, `ReceiveIn`, `ReasonIn` | `CashHoldingsView` (Keuangan › Kas & Bank › Titipan Sales), `MobileCashHoldingCard` (Beranda HP sales "Titipan Saya"), `ARReceiptModal` (teks bantu tunai) |
| Kartu Tindakan Asisten *(AG-T1, AG-T3, AG-T5)* | `ai_action_proposals` | `routers/ai_assist.py` (`GET /api/ai/actions?box=`, `GET /api/ai/actions/{id}`, `POST …/{id}/confirm`, `POST …/{id}/dismiss`, `POST …/{id}/second` — orang kedua AG-T5), `services/ai_actions.py` (jenis lama, alat `propose_action`), `services/ai_cards.py` (golongan A/B/C, alat `prepare_action`, `POST /api/ai/tools/prepare_action`), `services/ai_card_rules.py` (daftar larangan) | — | `TanyaActionCard` (percakapan & tab), `TanyaActions` (Tanya KN › Tindakan) |
| Kunci Masa Pajak *(PK-40)* | `tax_period_locks` | `routers/tax_center.py` (`/api/tax/periods*`), `services/tax_center_service.py` (`assert_masa_terbuka` dipanggil layanan faktur & PPh) | `TaxPeriodLockInput`, `TaxPeriodUnlockInput` | `TaxCenterView` (Akuntansi & Pajak › Pusat Pajak) |
| Niat Bayar Hutang *(PK-05)* | `ap_payment_intents` | `routers/ap_payments.py`, `services/ap_payment_service.py` (dipanggil bayar faktur & bayar kontrabon) | `VendorBillPaymentCreate`, `ContraBonPayIn` | `VendorBillDetailPanel` & `contrabon/PayModal` (panel bayar, `features/purchasing/apPayment.jsx`) |
| Kontrabon *(FASE G-7)* | `contra_bons` | `routers/contra_bons.py`, `services/contra_bon_service.py`, `services/contra_bon_reminder.py` | `ContraBonCreate`, `ContraBonDeductionIn`, `ContraBonDecisionIn`, `ContraBonScheduleIn`, `ContraBonPayIn`, `InvoiceExchangeIn` | `ContraBonsView` (Pembelian → Hutang Supplier (AP) → Kontrabon) |
| Transaksi Antar Entitas *(FASE G-6)* | `interco_transactions`, `interco_accounts`, `interco_settlements` | `routers/interco.py`, `services/interco_service.py`, `services/consolidation_service.py` (eliminasi margin) | `IntercoCreate`, `IntercoActionIn`, `IntercoSettlementCreate` | `IntercoView` (Pembelian → Hutang Supplier (AP) → Antar Entitas (Jual-Beli)) · `GroupConsolidationView` (eliminasi AUTO G-6) |
| Finance Case *(FASE G-9)* | `finance_cases` | `routers/finance_cases.py`, `services/finance_case_service.py` | `CaseCreate`, `CaseResolveInput`, `CaseRejectInput` | `FinanceCasesView` (Keuangan → Pusat Kasus Keuangan) |
| Bank Statement Line *(R6.1)* | `bank_statement_lines` | `routers/bank_reconciliation.py`, `services/bank_recon_service.py` | — | `BankReconciliationView` (Keuangan → Rekonsiliasi Bank) |
| Fixed Asset *(R6.2)* | `fin_fixed_assets` | `routers/fixed_assets.py`, `services/fixed_asset_service.py` | `FixedAssetIn/Patch` | `FixedAssetsView` (Kas & Aset → Aset Tetap) |
| Depreciation Entry *(R6.2)* | `fin_depreciation_entries` | `routers/fixed_assets.py`, `services/fixed_asset_service.py` | — | `FixedAssetsView` (histori penyusutan) |
| Budget *(P1-4 / R6.3)* | `budgets` | `routers/budgets.py`, `services/budget_service.py` | `BudgetCreate/Update` | `BudgetView` (Keuangan → Laporan & Analitik → Anggaran vs Realisasi) |
| Budget Rule *(R6.3)* | `fin_budget_rules` | `routers/budgets.py`, `services/budget_service.py` | `BudgetRulesIn` | `BudgetView` (panel Kebijakan Anggaran) |
| Riwayat Pagu *(PK-39)* | `budget_history` | `services/budget_service.py` (`_write_history` dari `create_budget`/`update_budget`/`delete_budget`), `routers/budgets.py` (`GET /api/finance/budgets/{id}/history`) | `BudgetUpdate.reason`, `?reason=` | `BudgetHistoryModal` (`BudgetDialogs.jsx`) |
| BOM / Resep Produksi *(R6.4)* | `mfg_boms` | `routers/production.py`, `services/production_service.py` | `BomIn/BomPatch` | `ProductionView` (Gudang → Produksi (BOM & WO) → tab BOM/Resep) |
| Work Order *(R6.4)* | `mfg_work_orders` | `routers/production.py`, `services/production_service.py` | `WorkOrderIn` | `ProductionView` + `ProductionWO` (tab Work Order) |
| Histori Job Scheduler *(R6.5)* | `sys_scheduler_runs` | `routers/scheduler.py`, `services/scheduler_service.py` | — | `SchedulerView` (Pengaturan → Penjadwal & Notifikasi → tab Riwayat Eksekusi) |
| Outbox WhatsApp *(R6.5)* | `sys_wa_outbox` | `routers/scheduler.py`, `services/wa_alert_service.py` | `WaTestRequest` | `SchedulerWa` (tab WhatsApp → Outbox) |
| Pengaturan Alert *(R6.5)* | `system_settings` *(scope=alerts)* | `routers/scheduler.py`, `services/wa_alert_service.py` | `SchedulerSettingsUpdate` | `SchedulerWa` + `JobTable` (editor jadwal inline) |
| Tampilan Tersimpan Daftar *(FIX-8 · K-B4-12)* | `saved_views` | `routers/saved_views.py`, `services/saved_view_service.py` | `SavedViewIn`, `SavedViewPatch` | `SavedViewsMenu` + `useSavedViews` (Operasi Gudang › Stok › Roll · Transfer · Barang Keluar) |

---

## 🗂️ DETAIL ENTITAS

### users
```
Collection:  users
Routers:     routers/auth.py (login, me, logout)
             routers/users.py (CRUD)
Schema:      schemas.py → UserCreate, UserResponse
Component:   AdminView.jsx (tab Users), LoginScreen (CoreWidgets.jsx)
Key Fields:
  id          string   prefix "user_"
  name        string
  email       string   UNIQUE
  role        enum     admin | sales | manager | warehouse
  password_hash string  SHA256 hash (kain-nusantara::password)
  status      enum     active | inactive
  allowed_line_codes list  [FASE L] lini produk yang boleh dikerjakan akun ini
                           (mis. ["printing"]). **KOSONG = SEMUA LINI** — itu
                           bawaannya, supaya akun lama tidak kehilangan apa pun.
                           Divalidasi ke master `product_lines` (services/line_scope.py);
                           mengubahnya MENCABUT sesi (hak baca berubah).
  ai_finance  object   [AG-T2] `{"enabled": bool}` sakelar Asisten Keuangan per akun (K-45). TIDAK ADA = mati.
                           Diubah lewat `PATCH /api/users/{id}` `{"data": {"ai_finance": {...}}}` hanya oleh pemegang
                           izin `ai.configure` (jejak `ai_finance_toggled`). Memakai mode Keuangan = izin
                           `ai_finance.view` DAN sakelar ini.
                           [AG-T3] `classes`: daftar golongan kartu tindakan yang boleh disetujui akun ini; nilai sah
                           hanya `"B"` (uang masuk: kwitansi, pencocokan bank, alokasi titipan, ulang jurnal gagal).
                           Kosong/tidak ada = golongan B ditolak. PATCH boleh mengirim `enabled` dan/atau `classes`; yang
                           tidak dikirim dipertahankan. Golongan B juga menuntut izin `ai_finance.create` dan
                           `ai.tindakan_uang_masuk` menyala untuk PT kartu.
                           [AG-T5] nilai `"C"` = uang keluar dan jurnal (bayar tagihan pemasok & kontrabon, kas manual);
                           layar Akun menawarkan "Baca saja" `[]` · "Uang masuk" `["B"]` · "Uang masuk, uang keluar, dan
                           jurnal" `["B","C"]`. Golongan C juga menuntut izin `ai_finance.pay` dan `ai.tindakan_uang_keluar`
                           menyala untuk PT kartu; orang kedua = izin `ai_finance.approve` + `C` + izin pintu tindakannya.
  created_at  string   ISO 8601 UTC

⚠️ JANGAN BUAT: staff, karyawan, operator, employee (untuk user system)
⚠️ Auth: Bearer token via Authorization header (BUKAN cookie)
⚠️ Password: hash_password() dari core_utils.py — jangan pake bcrypt
```

### sessions
```
Collection:  sessions
Router:      routers/auth.py (auto-managed)
Key Fields:
  token       string   format: "sess_[hex12]"
  user_id     string   FK → users.id
  created_at  string
  expires_at  datetime kedaluwarsa (indeks TTL); diperpanjang saat sisa < ½ umur sesi
  ttl_hours   int      KF-T7 — umur sesi saat dibuat (`keamanan.umur_sesi_jam`); kosong pada sesi lama = 24

⚠️ JANGAN query sessions langsung dari router lain
⚠️ Gunakan current_user() dari dependencies.py
```

### products
```
Collection:  products
Router:      routers/products.py
Schema:      schemas.py → ProductPayload
Component:   ProductCard.jsx, AdminView.jsx (tab Product), SalesPortal.jsx
Key Fields:
  id          string   prefix "prod_"
  sku         string   UNIQUE — format: CAT-MOTIF-NNN (e.g. BTK-MEGA-001)
  name        string
  category    enum     Batik | Tenun | Lurik | Songket | Ulos | Jumputan | Endek
  variant     string
  color       string
  motif       string
  grade       enum     [FASE A · D-01] A | A1 | A2 | B | BS   (rank 1..5; BS = barang sortir)
                       ⚠️ A+ / C DIPENSIUNKAN → dimigrasi (A+→A, C→BS) oleh
                       backend/scripts/migrate_fase_a_domain.py; nilai asli disimpan di grade_legacy
  grade_legacy string?  [FASE A] nilai grade lama sebelum normalisasi (audit migrasi)
  stage       enum     [FASE A · PS-01] yarn | grey | pfd | pfp | finished | remnant | byproduct
                       (transisi dikunci server — GET /api/enums/stage-transitions)
  fabric_type enum     [FASE A · PS-02/D-02] woven | knit  — WAJIB sejak stage yarn
  line_code   string   [FASE L] LINI PRODUK = pembagian kerja MD (woven|knit|printing|…,
                       bisa ditambah pemilik di master `product_lines`). **BUKAN**
                       pengganti `fabric_type`: lini = siapa yang mengerjakan & papan
                       mana; `fabric_type` = fisika kain (SSOT rumus & satuan kendali).
                       Kosong = belum bergolong lini → TETAP terlihat semua akun.
                       Dijaga INV-LINE-01/02 (scripts/guardrails/verify_line_scope.py).
  fabric_type_migrated bool?  [FASE A · D-20] true bila diisi otomatis oleh migrasi (default woven)
  yarn_count        string?  [FASE A · D-22] nomor benang (WAJIB bila stage=yarn & woven), mis. "30s"
  yarn_count_system enum?    [FASE A · D-22] Ne | Nm | Denier | Tex
  needs_review      bool     [FASE A · D-22] true bila kelengkapan domain kurang (GSM/lebar/yarn_count)
  needs_review_reasons list   field yang disarankan tapi belum terisi (turunan validasi)
  domain_gaps       list      pesan kelengkapan WAJIB yang belum terpenuhi (turunan validasi migrasi)
  gramasi     float    GSM (gram/m²) — WAJIB stage ≥ grey untuk woven (PS-03/D-22)
  lebar       float    lebar kain (meter) — WAJIB stage ≥ grey untuk woven (PS-03)
  supplier    string   (string only saat ini, bukan FK)
  base_unit   string   meter | yard | roll | pcs
  price       float    IDR per base_unit
  image       string   URL
  status      enum     active | inactive
  uom_conversions  list  [{from_unit, to_unit, factor}]
  batch_lot_rolls  list  [{batch, lot, roll_id}]
  --- METADATA SMART-SEARCH / AI-READY [PROPOSED KN_16 §8B.6] (disiapkan, diisi bertahap) ---
  description      text   deskripsi panjang (marketing/search)
  specifications   object {komposisi, lebar_cm, gramasi, perawatan, asal, ...} (key-value terstruktur)
  tags             list   [string]
  media            list   [{type: image|video, url}]  (multi-media; image lama tetap kompat)
  search_keywords  list   [string]  (untuk smart search)
  attributes       object {} facet/filter terstruktur
  ai_meta          object { embedding: [], recommender_tags: [], updated_at }  (KOSONG dulu — engine nanti)
  created_at  string
  updated_at  string

⚠️ SSOT TUNGGAL: Sales-view & Inventory-view = PROYEKSI dari products yang sama, BUKAN tabel terpisah
   (mis. GET /products?view=sales vs ?view=inventory). Cegah data ganda/konflik.
⚠️ JANGAN BUAT: items, goods, materials, kain, fabric, accessories, products_sales, products_inventory
⚠️ Stok ADA DI inventory_balances/inventory_rolls, BUKAN di products
```

### product_categories  [EPIC2 IMPLEMENTED — Master Kategori Produk]
```
Collection:  product_categories         Prefix: cat_
Router:      routers/categories.py
Schema:      routers/categories.py → CategoryPayload (inline)
Component:   features/admin/CategoryManager.jsx, AdminView.jsx (tab Kategori + dropdown form produk)
Key Fields:
  id            string   prefix "cat_"
  code          string   UNIQUE — uppercase slug (mis. BATIK)
  name          string   UNIQUE — nama kategori (mis. Batik) = nilai products.category
  base_unit     string   default UOM kategori (meter|yard|kg|roll|pcs) → default produk baru
  description   string
  sort_order    int      urutan tampil
  status        enum     active | inactive
  product_count int      DERIVED (count products by name) — tidak disimpan
  created_at    string
  updated_at    string

ℹ️ SSOT nama kategori. products.category menyimpan NAME (string), bukan id → kompat data historis.
ℹ️ Rename kategori mem-propagasi ke products.category (jaga konsistensi).
ℹ️ SO line meng-snapshot `category` (+base_unit, base_quantity) saat create; backfill historis idempotent.
⚠️ JANGAN BUAT: categories, product_category, kategori, product_groups
```

### color_library  [M0 IMPLEMENTED — Master Warna Pantone-style]
```
Collection:  color_library              Prefix: col_
Scope:       SHARED (tak di-scope entitas, mirip products/uoms)
Router:      routers/color_library.py
Service:     services/color_service.py
Schema:      schemas.py → ColorCreate, ColorPatch
Component:   features/sales/ColorLibraryView.jsx, components/PantoneFinder.jsx
Key Fields:
  id          string   prefix "col_"
  code        string   UNIQUE — kode warna (mis. KN-BLU-01, TCX-19-4052)
  name        string   nama warna (mis. Biru Indigo)
  hex         string   "#RRGGBB" (uppercase)
  system      enum     TPX | TCX | C | U | KN (default KN)
  family      string   kelompok warna (Biru/Merah/…)
  status      enum     active | inactive (delete = soft/nonaktif)
  created_by  string
  created_at  string
  updated_at  string

ℹ️ Master warna dipakai lintas menu (Master Produk, Template Varian, POS, Makloon).
ℹ️ Produk meng-snapshot warna: products.color_code / color_name / color_hex (fallback teks `color`).
ℹ️ Endpoint /api/color-library/nearest?hex= → cari warna terdekat (ΔE redmean).
⚠️ JANGAN BUAT: colors, warna, pantone, color_master
```

### makloons  [M1 IMPLEMENTED — Master Mitra Makloon/Subkontraktor]
```
Collection:  makloons                    Prefix: mak_
Scope:       SCOPED (entity_id) — mirror suppliers
Router:      routers/makloons.py
Service:     services/makloon_service.py (makloon_360, compute_makloon_scorecard)
Schema:      schemas_makloon.py → MakloonCreate (+ GenericPatch untuk update)
Component:   features/purchasing/MakloonsView.jsx, Makloon360Panel.jsx, MakloonFormModal.jsx, components/MakloonSelect.jsx
Key Fields:
  id, code (MAK-NNNNN), name, npwp, pic_name, phone, email, address, city,
  process_types [tenun|celup|finishing|printing|lainnya], capacity_note,
  capacity_per_month, capacity_unit, default_tariff, tariff_unit [output|input|roll],
  payment_term_code, lead_time_days, entity_id, notes, status, created_*
Endpoints:   GET/POST /makloons · GET /makloons/{id} (360) · PATCH/DELETE /makloons/{id} · GET /makloons/{id}/scorecard
⚠️ JANGAN BUAT: makloon, subcontractors, vendors_makloon, toll_manufacturers
```

### process_recipes  [M1 IMPLEMENTED — Resep Konversi Proses]
```
Collection:  process_recipes             Prefix: prcp_
Scope:       SCOPED (entity_id)
Router:      routers/process_recipes.py
Service:     services/process_recipe_service.py (compute_forecast + safe formula eval)
Schema:      schemas_makloon.py → ProcessRecipeCreate, ForecastPreviewIn (+ GenericPatch)
Component:   features/purchasing/ProcessRecipesView.jsx, RecipeFormModal.jsx
Key Fields:
  id, name, process_type, input_product_id, input_stage, output_product_id, output_stage,
  yield_factor, waste_pct, byproduct_pct, byproduct_product_id,
  default_makloon_id, default_tariff, tariff_unit, aux_cost_default,
  formula (ekspresi bebas opsional; var: input_qty/gramasi/lebar/yield_factor/waste_pct/byproduct_pct),
  entity_id, status, created_*
Endpoints:   GET/POST /process-recipes · PATCH/DELETE /process-recipes/{id} · POST /process-recipes/forecast
⚠️ JANGAN BUAT: recipes, konversi, bom_makloon, process_bom
```

> MP-T3 (16 Nov 2026): peserta & round `md_samples` boleh mitra makloon — `participants[]/rounds[]` membawa
> `partner_kind` (`supplier`|`makloon`; `supplier_id` tetap nama kolomnya); keputusan membawa `partner_kind`, `process_type`.
> Master jenis sampling (`sample_types`) mendapat `partner_process_types` (labdip → celup, proofing → printing, handfeel →
> tenun/rajut/pre_treatment). Pemenang mitra makloon → kontrak `makloon` (per proses / borongan `lot`) + rute utama
> `origin=rnd`. Produk dari spesifikasi membawa `color_id`. Sample membawa `base_fabric_override` bila kain dasar proofing
> menyimpang (K-72).

### makloon_shipments  [MP-T5a IMPLEMENTED — Surat jalan kirim bahan makloon, 16 Nov 2026]
```
Collection:  makloon_shipments           Prefix: msj_    Nomor: SJM- (jenis penomoran `msj`, per PT)
Scope:       SCOPED (entity_id)
Writer:      services/makloon_order_service._record_shipment (dipanggil issue_step; idempoten per mko_id × step_seq)
Router:      GET /makloon-orders/{id}/shipments · cetak `makloon_sj` (services/pdf_resolvers.resolve_makloon_sj)
Key Fields:  id, entity_id, number, kind (kirim|teruskan), mko_id, mko_number, step_seq, stage_label,
             from{kind gudang|mitra, id, name}, to{makloon_id, name, address, phone}, product{id, sku, name, color},
             rolls[{roll_id, roll_no, lot, length, unit, grade}], total_rolls, total_qty, unit, purpose, created_*
```
> MP-T5b: `makloon_orders.purpose {kind pelanggan|toko|stok|pr, label, customer_id?, customer_name?, store_name?, note}`.

### product_routes  [MP-T1 IMPLEMENTED — Rute Produk, 16 Nov 2026]
```
Collection:  product_routes              Prefix: rte_
Scope:       SCOPED (entity_id) — rute per artikel per PT (mitra, kontrak, resep, BOM milik PT)
Router:      routers/product_routes.py
Service:     services/product_route_service.py (validate R1–R9, effective_for_product, suggest, step_options)
Component:   frontend/src/features/catalog/FamilyRoutesTab.jsx
Key Fields:
  id, entity_id, template_id, product_id ("" = semua varian; diisi = pengecualian varian), name, is_primary,
  status (active|inactive), origin (manual|rute_awal|rnd), origin_ref{kind,id,number},
  steps[{seq, kind (purchase|makloon|inhouse), stage_code, stage_label, process_type, from_stage, to_stage,
         input_product_id, output_product_id, partner_kind, partner_id, partner_name, contract_id, contract_number,
         recipe_id, bom_id, note}], created_*, updated_*, history[]
Aturan:      tahap asal/hasil langkah makloon dari master `process_stages` (K-57), rantai bersambung, berakhir di
             tahap artikel/varian; satu rute utama per (PT, artikel, varian).
Pembaca:     restock_source_service.check_lines/auto_route (jalur PR/PO/SPK), rnd_spec_service.release_product
             (rilis wajib rute utama, `rnd.release_requires_route`).
Endpoints:   GET/POST /product-templates/{id}/routes · GET /product-templates/{id}/routes/suggest ·
             PATCH /product-routes/{id} · POST /product-routes/{id}/primary · GET /products/{id}/route ·
             GET /product-routes/step-options
Skrip data:  backend/scripts/mpt1_rute_awal.py (rute awal dari resep/BOM/sumber restock; data nyata = H3)
⚠️ JANGAN BUAT: product_route_steps, routings, bom_routes — langkah tinggal di `steps[]`.
```

> MP-T2 (16 Nov 2026): SPK baru menolak langkah yang bahan masuk/hasilnya tidak bertahap sesuai Master Tahapan Proses
> (`makloon_order_service._assert_stage_chain`); `GET /makloon-orders/plan-from-route` mengisi langkah dari rute utama
> (`product_route_service.plan_makloon`, juga dipakai prefill PR); `POST /makloon-orders/{id}/steps/{seq}/partner` mengisi
> mitra langkah draf; kirim bahan ditolak bila mitra kosong (K-61). Modal lama `MakloonOrderCreateModal` dihapus — kedua
> pintu memakai `MakloonWizard`.

> MP-T4a (16 Nov 2026): `steps[].forwarded_to {seq, partner, at, by, qty, roll_ids}` / `steps[].forwarded_from` — kain
> diteruskan langsung mitra → mitra (`POST /makloon-orders/{id}/steps/{seq}/forward`, izin `makloon_order.forward`, bawaan
> Admin/Manajer/MD); jurnal yang sudah ada (terima langkah N + kirim langkah N+1). `steps[].claim.qc_rejects[]` (tolak QC
> hasil makloon membuka klaim); klaim yang ditolak kembali `open` dengan `rejected_*` (SPK tetap Sebagian).

### makloon_orders  [M3 IMPLEMENTED — Transaksi Makloon/Subkontrak (Procure→Process→Pay)]
```
Collection:  makloon_orders             Prefix: mko_   (number: MKO-#####)
Scope:       SCOPED (entity_id)
Router:      routers/makloon_orders.py
Service:     services/makloon_order_service.py (create/issue/receive/cancel + costing)
Schema:      schemas_makloon.py → MakloonOrderCreate, MakloonStepInput, MakloonIssueIn,
             MakloonReceiveIn, MakloonReceiveRoll, MakloonOrderCancel
Component:   features/purchasing/MakloonOrdersView.jsx, MakloonOrderCreateModal.jsx,
             MakloonOrderDetailPanel.jsx
Key Fields:
  id, mko_number, entity_id, mode (process_only|buy_process),
  material_product_id/sku/name/qty/unit, material_source (stock|purchase),
  from_warehouse_id, target_warehouse_id, po_id, po_number,
  final_output_product_id, steps[] (seq, process_type, makloon_id, recipe_id,
    input_product_id, input_qty, output_product_id, expected_output_qty,
    actual_output_qty, expected_byproduct_qty, actual_byproduct_qty, byproduct_product_id,
    tariff, aux_cost, service_bill_id, issue_ref, material_value, service_value, output_value,
    output_unit_cost, status(pending|issued|received|cancelled), issued_at, received_at, lots[]),
  forecast{}, costing{material_cost, service_cost, aux_cost, byproduct_credit, hpp_output, hpp_per_unit},
  status(draft|in_process|partially_received|completed|cancelled), timeline[], created_*
FASE D (additive · D-04/D-05/D-07/D-09) pada steps[]:
    contract_id, contract_number, tariff_basis, tariff_rate,
    tariff_plan{} (rencana saat create) · tariff_actual{source, basis, basis_qty, rate,
      amount, explain[], conversion{}} (aktual saat receive · INV-MKO-03),
    shrinkage_pct, shrinkage_source (input langkah|kontrak <no>|resep proses|kebijakan global),
    tolerance_pct, estimate{method(gsm|yield|formula|unknown), expected_output_qty,
      expected_byproduct_qty, explain[]},
    issue_uom_trail{}, receive_uom_trail{} (doc→base · D-04),
    variance{variance_qty, variance_pct, tolerance_pct, shortfall_qty, shortfall_value,
      unit, unit_value, claim_required, message},
    claim{status(none|open|pending_approval|approved|rejected), required, action
      (potong_bon|tagih_ganti|terima_catatan), amount, amount_suggested, reason, history[],
      proposed_by/at, approved_by/at, approval_note, rejected_by/at/reason, effect{}},
    input_lot_ids[], output_lot_ids[], output_lot_id
  order-level: order_warnings[] (mode kontrak `warn`),
    claim_summary{open, pending_approval, approved, rejected, approved_amount, needs_action}
GL:          Dr 1-1350 WIP/Cr 1-1300 (issue) · Dr 1-1350+PPN/Cr 2-1100 (service via vendor_bills
             bill_type=makloon_service) · Dr 1-1300/Cr 1-1350 (receive). WIP net 0 per siklus.
             KLAIM (D-09): potong_bon Dr 2-1100/Cr 4-9200 (+vendor_bill dipotong) ·
             tagih_ganti Dr 1-1260/Cr 4-9200 · terima_catatan TANPA jurnal (kerugian sudah
             terserap ke HPP output saat receive).
             MP-T4b (K-78…K-82, 16 Nov 2026) — sakelar per PT `makloon.jasa_jadi_hutang`
             (bawaan `saat_faktur` sejak K-82, semua PT; `saat_terima` = baris di atas). `saat_faktur`: terima →
             Dr 1-1350/Cr GR/IR 2-1150
             (tagihan `awaiting_invoice`, `ap_mode` dipotret di tagihan, PPN 0); faktur mitra dicocokkan
             (POST /makloon-orders/{id}/steps/{seq}/service-invoice, izin vendor_bill.create, nilai jasa = nilai
             tagihan) → Dr 2-1150 + Dr 1-1500 / Cr 2-1100 (source `subcon_service_invoice`), tagihan `posted`.
             Klaim di mode ini dibagi per roll hasil: di stok → Cr 1-1300 (unit_cost roll turun, `claim_refs`,
             roll_cost_history), di mitra → Cr 1-1350, sudah keluar → Cr 4-9200; debit 2-1150 bila faktur
             belum dicocokkan. Borongan (K-81): kontrak basis `lot` yang sama di beberapa langkah →
             langkah sebelumnya tarif 0 (`borongan_contract_id`, `borongan_billed_at_seq`, `tariff_note`),
             ditagih sekali di langkah terakhir. Langkah: `service_invoice_status` (menunggu_faktur|cocok).
             Jurnal yang menyentuh GR/IR membawa `ref.grir_mko_id` → Hutang › GR/IR berbaris per SPK (kunci
             `mko:<id>` di `vendor_bill_service.grir_by_po`). Susut di mitra (L01) potong bon dari tagihan
             `awaiting_invoice` → Dr 2-1150 (bukan 2-1100).
Stock:       roll status 'subcon' (WIP-at-vendor, owned non-ATP) → 'consumed' saat receive;
             output+barang sisa (is_remnant) jadi roll 'available' dgn LOT manual per roll.
Endpoints:   GET/POST /makloon-orders · GET /makloon-orders/{id} ·
             POST /makloon-orders/{id}/issue|receive|cancel ·
             POST /makloon-orders/estimate (pratinjau wizard) ·
             GET /makloon-orders/claims · GET /makloon-orders/claims/stats ·
             POST /makloon-orders/{id}/claim|claim/approve|claim/reject
Invariants:  INV-MKO-01..06 (verify_data_integrity blok L4-MKO)
Docs:        docs/KN_24_PLAN_FASE_D_MAKLOON.md
⚠️ JANGAN BUAT: subcon_orders, toll_orders, maklon_orders, work_orders, makloon_claims
```

### supplier_contracts  [FASE D IMPLEMENTED — Kontrak Mitra Makloon & Supplier]
```
Collection:  supplier_contracts          Prefix: sct_   (number: <ENT>/SCT-#####)
Scope:       SCOPED (entity_id)
Router:      routers/supplier_contracts.py
Service:     services/contract_service.py (kebijakan + CRUD + resolve_active + compute_tariff
             + tariff_preview + stats + mark_used)
Schema:      schemas_contracts.py → SupplierContractCreate, SupplierContractPatch,
             ContractStatusIn, ContractAuxFee, TariffPreviewIn, ContractResolveIn
Component:   features/purchasing/contracts/ContractsView.jsx, ContractFormModal.jsx,
             MakloonPolicyModal.jsx
             (Pembelian → Master Pembelian → tab "Kontrak Mitra & Supplier")
Key Fields:
  id, contract_number, entity_id, contract_type (makloon|purchase),
  partner_kind, partner_id, partner_name, title,
  process_type (WAJIB bila makloon; enum registry process_type),
  product_id/sku/name, input_product_id,
  tariff_basis (pick|kg|meter|yard|ball|cone|roll|lot|lumpsum|custom · D-07),
  tariff_rate, tariff_formula (safe-eval AST), tariff_qty_source (output|input), ppi,
  aux_fees[{code,label,basis(lumpsum|per_roll|per_color|per_repeat|per_kg|per_meter|
    per_output_unit),amount}], min_charge, currency,
  shrinkage_pct (D-05), tolerance_pct (nullable → kebijakan · D-09), yield_factor, byproduct_pct,
  moq, lead_time_days, payment_term_code, valid_from, valid_to,
  status (draft|active|expired|terminated), sample_ref, notes,
  usage_count (>0 ⇒ DELETE 409), created_at/by, updated_at/by
Policy:      system_settings scope `makloon` → variance_tolerance_pct, default_shrinkage_pct,
             contract_mode (off|warn|block), auto_claim, claim_approval_roles[],
             require_output_product, require_yield_reason  (configurable TANPA deploy)
Endpoints:   GET/POST /supplier-contracts · GET /supplier-contracts/stats ·
             GET/PUT /supplier-contracts/policy · POST /supplier-contracts/resolve ·
             POST /supplier-contracts/tariff-preview · GET /supplier-contracts/{id} ·
             PATCH /supplier-contracts/{id} · POST /supplier-contracts/{id}/status ·
             DELETE /supplier-contracts/{id} (409 bila terpakai) ·
             GET /makloon-partners/scorecard
RBAC:        permission resource `supplier_contract` (admin/manager CRUD · warehouse view ·
             sales TIDAK punya akses — data komersial)
Indexes:     indexes.py → (entity_id, contract_type, status), (partner_id, process_type, status),
             contract_number unik
Invariant:   INV-MKO-06 (steps[].contract_id valid & bernomor sah)
Docs:        docs/KN_24_PLAN_FASE_D_MAKLOON.md
ℹ️ contract_type=`purchase` dipakai **Fase E** (routing PR/PO berbasis kontrak): `tariff_basis`
   = satuan harga, `tariff_rate` = harga per satuan itu, `moq` = MOQ kontrak.
⚠️ JANGAN BUAT: contracts, makloon_contracts, purchase_contracts, tariffs, price_contracts
```

### supplier_items  [FASE E IMPLEMENTED — Barang Supplier (katalog versi supplier)]
```
Collection:  supplier_items              Prefix: sit_
Scope:       SCOPED (entity_id)
Router:      routers/supplier_items.py
Service:     services/supplier_item_service.py (CRUD + lookup + resolve_for_product
             + validate_rows/import_rows + csv_template + mark_used)
Schema:      schemas_supplier_items.py → SupplierItemCreate, SupplierItemPatch,
             SupplierItemImportRow, SupplierItemImportIn
Component:   features/purchasing/supplier-items/SupplierItemsView.jsx,
             SupplierItemFormModal.jsx, SupplierItemImportModal.jsx
             (Pembelian → Master Pembelian → tab "Barang Supplier")
Masalah yang diselesaikan:
  Supplier menyebut barang dengan KODE & NAMA sendiri (mis. `TX-COT-30S` "Cotton Combed 30s
  Cone 1,89kg") sementara KN memakai SKU sendiri (`BNG-KTN-001`). Tanpa peta ini, tim
  purchasing menerjemahkan manual saat buat PO & saat terima barang → salah barang/satuan/harga.
Key Fields:
  id, entity_id, supplier_id, supplier_name,
  product_id, sku, product_name, base_unit            (sisi KN)
  supplier_sku          KODE barang versi supplier — WAJIB (kunci logis)
  supplier_item_name    NAMA barang versi supplier
  supplier_uom          satuan supplier ("" = sama dengan base_unit produk)
  conv_factor           1 supplier_uom = conv_factor × base_unit  (> 0 · E-03)
  last_price, currency, moq, lead_time_days, expected_grade, barcode, notes,
  status (active|inactive), usage_count (>0 ⇒ DELETE 409),
  created_at/by, updated_at/by, last_used_at
🔑 KUNCI LOGIS UNIK: (supplier_id, supplier_sku) → impor **idempotent** (upsert · E-02)
Endpoints:   GET/POST /supplier-items · GET /supplier-items/stats ·
             GET /supplier-items/lookup?supplier_sku=&supplier_id=  (cari barang KN dari kode supplier) ·
             GET /supplier-items/import-template  (unduh template CSV) ·
             POST /supplier-items/import          (JSON: rows[] atau csv_text · dry_run) ·
             POST /supplier-items/import-file     (multipart CSV/XLSX · dry_run) ·
             GET/PATCH/DELETE /supplier-items/{id}
Impor:       kolom dikenali + alias Indonesia (kode_supplier, nama_barang_supplier, satuan_supplier,
             faktor_konversi, harga, …). Pemisah CSV auto-deteksi `,` atau `;`.
             `dry_run=true` → pratinjau (will_create/will_update + errors[] per baris).
RBAC:        resource `supplier_item` — admin/manager: view/create/update/delete/**import** ·
             warehouse: view · sales: TIDAK punya akses
Indexes:     indexes.py → (supplier_id, supplier_sku), (entity_id, created_at),
             (supplier_id, product_id, status), (product_id), (supplier_sku), (barcode)
Invariant:   INV-SRC-05 (kunci unik, referensi & faktor konversi valid, referensi PO hidup)
Docs:        docs/KN_25_PLAN_FASE_E_SOURCING_CONTRACTS.md
⚠️ JANGAN BUAT: supplier_products, supplier_skus, vendor_items, item_supplier_map, supplier_catalog
```

### purchase_requisitions  [FASE E EXTENDED — routing pemenuhan per baris + realisasi]
```
Collection:  purchase_requisitions       Prefix: pr_   (number: PR-#####)
Router:      routers/purchase_requisitions.py
Service:     services/purchase_requisition_service.py (CRUD/approval/reorder) +
             services/pr_sourcing_service.py (FASE E: routing & realisasi)
FASE E — field additive:
  items[].line_no             nomor baris 1-based (unik per PR)
  items[].fulfillment_mode    purchase | makloon   (default `purchase`, backward-compatible)
  items[].realized_qty        akumulasi qty yang sudah direalisasi
  items[].realizations[]      [{type(purchase_order|makloon_order), ref_id, ref_number, qty, at, by}]
  realization{}               TURUNAN: realization_status, realized_lines, total_lines,
                              realized_qty, total_qty, realized_pct, purchase_lines, makloon_lines
  realization_status          open | partially_realized | realized  (turunan · INV-SRC-03)
  po_ids[], makloon_order_ids[], timeline[]
Endpoints (FASE E):
  GET  /purchase-requisitions/{id}/sourcing          ringkasan realisasi + aksi per baris
  POST /purchase-requisitions/{id}/realize-po        realisasi baris `purchase` (boleh sebagian)
  GET  /purchase-requisitions/{id}/makloon-prefill?line_no=N   payload Wizard Makloon ter-prefill
  POST /purchase-requisitions/{id}/realize-makloon   realisasi 1 baris `makloon` → Order Makloon
ℹ️ `POST /{id}/convert-to-po` (lama) kini **mendelegasi** ke `realize_to_po` — perilaku lama tetap
   bila semua baris ber-mode `purchase`. PR jadi `converted` HANYA bila semua baris penuh.
ℹ️ PO hasil realisasi membawa jejak sourcing per baris: `contract_id`/`contract_number`,
   `supplier_item_id`/`supplier_sku`/`supplier_item_name`, `price_source`, `sourcing_explain[]`,
   `pr_line_no`; order-level `source_pr_line_nos[]`, `contract_ids[]`.
ℹ️ [FASE F-1] Baris PO (manual **dan** hasil realisasi PR) juga membawa `supplier_uom` +
   `supplier_conv_factor` — diteruskan ke `wms_tasks` agar penerimaan bisa menerima qty dalam
   SATUAN SUPPLIER. `_create_po_core` me-resolve `supplier_items` per (supplier × produk).
Invariants:  INV-SRC-01..04
⚠️ JANGAN BUAT: requisitions, pr_lines, pr_realizations, purchase_requests
```

### ar_receipts  [EPIC3B IMPLEMENTED — AR Receipt / Payment Application]
```
Collection:  ar_receipts                Prefix: arc_   (number: AR-#####)
Router:      routers/ar_receipts.py
Service:     services/ar_receipt_service.py
Component:   features/crm/CollectionWorklist.jsx (modal Catat Pembayaran) + ARReceiptsList
Key Fields:
  id              string   prefix "arc_"
  number          string   UNIQUE — AR-00001 (next_doc_number, deletion-safe)
  customer_id     string   FK customers.id
  customer_name   string   snapshot
  entity_id       string   FK entities.id
  receipt_date    string   ISO
  method          enum     transfer | cash | giro | qris | ...
  amount          float    nominal diterima
  applied_total   float    total ter-alokasi ke order
  unapplied_amount float   sisa (amount - applied_total)
  allocations     array    [{order_id, order_number, applied, outstanding_after, payment_status,
                            parts: [{kind: kas|deposit, amount, payment_id}]}]   (PK-19 — pecahan sumber dana)
  notes           string
  status          enum     posted | void
  void_intent     object   PK-19 — niat pembatalan: {status: pending|done, reason, by, at, done_at,
                            steps: {deposit_pulled, decision_reversed, orders: [id pesanan], cash: [id kas],
                            deposit_restored}}; panggilan ulang meneruskan dari langkah yang belum bertanda
  reversed_orders array    PK-19 — [{order_id, reversed, outstanding_after, payment_status}] per pesanan yang dibalik
  variance.decision_status  pending | failed | done — PK-19, cermin status keputusan selisih kwitansi ini
  ai_card_id      string   AG-T3 — id kartu tindakan asisten yang mencatat kwitansi ini (tidak ada = dicatat di layar)
  dup_decision    object   PK-25 — keputusan kasus "pembayaran dobel" atas kwitansi ini: {case_id, case_number,
                            status: resolved|rejected, at}; pemindai kasus tidak membuat kasus dobel lagi
  account_id      string   PK-20 — rekening penerima (`bank_accounts`) kas kwitansi; kosong = tanpa uang baru (deposit saja)
  payment_method_code string PM-T3 — kode cara bayar kanonik (PM-T1); `method` tetap ditulis sama untuk pembaca lama
  account_snapshot object  PM-T3 — potret rekening penerima {name, bank_name, account_number} saat kwitansi dibuat (D3)
  reference_no    string   PM-T3 — nomor referensi bukti bayar; wajib bila cara bayar `needs_reference` DAN
                            `payment.wajib_nomor_referensi` menyala untuk PT kwitansi
  giro_due_date   string   PM-T3 — YYYY-MM-DD, hanya cara bayar ber-`needs_due_date` (giro); wajib dengan syarat sama
  proof_url       string   PM-T3 — tautan bukti bayar (opsional)
  instruction_mismatch bool PM-T3 — true bila rekening penerima ≠ `receiving_account_id` salah satu pesanan yang
                            dialokasi; `mismatch_note` (≥ 5 huruf) wajib; `instruction_mismatch_orders[]`
                            = [{order_id, order_number, account_id, account_text}] potret instruksi yang tidak diikuti
  bank_verified   bool     PM-T3 — "Terverifikasi bank": kas kwitansi cocok PENUH dengan mutasi rekening yang sama
                            (ditulis `bank_recon_service.sinkron_verifikasi_kwitansi` sesudah cocok/lepas; bawaan false);
                            `bank_verified_at` ISO, `bank_verified_by` nama pelaku, `bank_line_ids[]` id mutasi.
                            Kwitansi terverifikasi (atau kasnya sudah dicocokkan sebagian) tidak bisa dibatalkan (409)
  created_by / created_by_name / created_at / updated_at

Indeks: `(entity_id, bank_verified, receipt_date)` (PM-T3 — daftar "Belum terverifikasi lebih dari N hari").
PM-T4 — `cash_holding_id` (id `cth_…`, kosong = kwitansi biasa): kwitansi tunai yang dicatat bukan pemegang `cash.create`
di PT ber-`pembayaran.sales_terima_tunai = titipan` — TANPA kas (`cash_txn_id` kosong) dan tanpa rekening; uangnya
tercatat di `cash_holdings` sampai disetor. `gl_status` kwitansi = cermin jurnal titipannya. Pembatalan: titipan yang
sudah (sebagian) disetor atau sedang diajukan dalam setoran → 409; selain itu titipan `batal` + jurnal pembalik
(`void_gl_status`, sumber `cash_holding_reversal`). `bootstrap.backfill_ar_cash_postings` melewati kwitansi ini.
Saringan daftar `GET /api/ar-receipts?bank_verified=&older_than_days=&method=` (PM-T3): kwitansi tunai & titipan tidak
pernah masuk daftar belum terverifikasi; `older_than_days` tanpa nilai = `payment.hari_wajar_verifikasi_bank`.

ℹ️ PK-19 — baris `sales_orders.payments[]` HANYA ditulis lewat `services/ar_allocation_service.py` (`allocate`,
   `reverse`, `withdraw`, `remove_unborn`; pemeriksa `validate_targets`: pelanggan, PT, status pesanan, sisa tagihan).
   Bentuk baris baru (baris lama tidak diubah; tanpa `kind` → `payment_kind(row)` dari `method`):
     id               "pay_" + 24 heksadesimal SHA-1 dari "kind|source_id|order_id|seq" (rujukan sama → id sama)
     kind             kas | deposit | titipan_bank | saldo_kredit | nota_kredit | hapus_sisa | kasus
     amount           positif = alokasi; negatif = pembalik (atau penarikan `withdrawal: true` kasus realokasi)
     receipt_id, receipt_number   dokumen sumber (kwitansi, keputusan, baris mutasi, penebusan, nota kredit, kasus)
     method, date, created_at, plan_line_seq, gl_bucket   seperti sebelumnya (`date` pembalik = tanggal pembatalan)
     reverses         (hanya pembalik) id baris yang dibalik — menyalin kind/method/gl_bucket/plan_line_seq asalnya
     reversed_by      (pada baris asal) id pembaliknya
   Pembatalan MENAMBAH baris pembalik bertanggal (tidak menghapus), jadi angka periode lalu tidak berubah mundur.
ℹ️ EFEK SAMPING: meng-apply ke sales_orders.payments[] (+paid_total, +payment_status).
   payment_status: unpaid | partial | paid. Credit gate & Collection Worklist membaca payments[] → auto-update.
ℹ️ Alokasi eksplisit (allocations) atau auto-FIFO (order terbuka tertua) bila kosong.
ℹ️ SSOT outstanding = nilai tagihan (grand_total + Σ extra_billing_lines.gross, `customer_service._order_grand_total`)
   − Σ payments[].amount (lihat customer_service._order_paid).
ℹ️ PK-32 — baris `kind="nota_kredit"` nota kredit AMANDEMEN ber-`gl_bucket`: `nota_koreksi` (bagian yang dijurnal
   Cr 1-1200) atau `nota_tangguh` (bagian yang pendapatannya belum diakui). Keduanya mengurangi sisa tagihan tetapi tidak
   dihitung `gl_service.order_direct_ar_paid` (piutangnya dihitung dari jurnal nota di `order_revenue_recognized`).
⚠️ JANGAN BUAT: payments, receipts, ar_payments, collections (sebagai koleksi).
```

### incentive_rates  [EPIC4 IMPLEMENTED — Incentive Engine v2 rate matrix]
```
Collection:  incentive_rates             Prefix: irate_
Router:      routers/incentive_rates.py
Service:     services/sales_force_service.py (_compute_commission_per_sku), services/commission_rules.py
             (rate_key, muat_indeks_tarif, pilih_tarif, potret), services/commission_rate_service.py (pohon, ubah banyak, Excel)
Component:   features/incentive/ArticleRatesTable.jsx + RateFormModal.jsx (tab Skema & Tarif, KA-9; pohon kategori →
             artikel → varian) · GroupRatesList.jsx (tarif Semua PT). `IncentiveRatesEditor`/`LegacyRatesEditor` dihapus
Key Fields:
  id                      string  prefix "irate_"
  entity_id               string  FK entities.id | "all" (fallback semua entitas)
  category                string  = products.category / SO line snapshot (baris artikel/varian: dipotret dari katalog)
  template_id             string  KA-2 · FK product_templates.id ("" = bukan tarif artikel)
  product_id              string  KA-2 · FK products.id — pengecualian per varian ("" = bukan varian); template_id & product_id tidak boleh keduanya
  rate_key                string  KA-2 · "varian:<product_id>" | "artikel:<template_id>" | "kategori:<category>" (indeks unik (entity_id, rate_key))
  target_name / target_code string KA-2 · potret nama & kode (sku_prefix artikel / sku varian); "" untuk baris kategori
  price_bands             list?   KA-2 · pita pengali harga khusus artikel/varian; null = ikut `commission.price_bands` PT
  price_source_rules      list?   KA-2 · aturan sumber harga khusus; null = ikut `commission.price_source_rules` PT
  incentive_unit          string  UOM dasar per_unit_amount (default meter)
  per_unit_amount         float   Rp per incentive_unit
  discount_threshold_type enum    pct | rp_per_unit  (basis ambang diskon line)
  discount_threshold      float   ambang diskon (>= → mekanik aktif)
  discount_mechanic       enum    tier_factor | potong_rp | cutoff
  discount_factor         float   tier_factor: komisi × faktor bila diskon > ambang
  discount_potong_rp      float   potong_rp: kurangi per_unit_amount (Rp/unit)
  margin_cap_pct          float   komisi/line ≤ X% margin line (margin-aware, WAC EPIC3)
  status                  enum    active | inactive
  created_at / updated_at

ℹ️ UNIK per (entity_id, rate_key) — indeks `uq_incentive_rate_key` (KA-2; bootstrap `backfill_incentive_rate_key`). Lookup engine: entity spesifik → fallback "all".
ℹ️ KA-3/KA-4 — urutan pencarian varian → artikel → kategori (tiap tingkat PT dulu lalu "all"); hasilnya DIPOTRET ke
   `sales_orders.items[].commission_rule` saat pesanan dibuat. Mengubah/menghapus tarif tidak mengubah pesanan lama.
   Tulisan banyak (`POST …/bulk`, `…/import/apply`) lewat `commission_rate_service.terapkan_tarif` (jejak audit beralasan).
ℹ️ Mode strategi di system_settings.commission.strategy (per_sku default | achievement_tiered arsip).
ℹ️ Engine on-collection: iterasi line terbayar (pro-rata partial payment), cap by margin.
⚠️ JANGAN BUAT: incentive_rate, commission_rates, rates, sku_rates (sebagai koleksi).
```

### commission_period_rules  [KA-6 — potret aturan komisi per PT per bulan saat akrual dibukukan]
```
Collection:  commission_period_rules     Prefix: cmpr_  (`cpr_` sudah dipakai credit_profile_requests & customer_prices)
Penulis:     services/commission_rules.py (bekukan_periode) — dipanggil gl_service.post_incentive_accrual SESUDAH jurnal
             akrual pertama tersimpan dan SEBELUM jurnal koreksi (bulan yang diakru sebelum KA-6 dibekukan pada koreksi
             pertamanya). Akrual ditolak (mis. periode tertutup) → tidak ada potret.
Pembaca:     services/commission_rules.py (pengali_capaian, capaian_aktif — jenjang beku menang atas nilai kunci akhir
             bulan, HANYA selama jurnal `journal_id` tidak dianulir)
Key Fields:
  id            string  prefix "cmpr_"
  entity_id     string  FK business_entities.id (PT spesifik, bukan "all")
  period        string  "YYYY-MM" bulan komisi (bulan uang masuk)
  achievement   object  {aktif, basis, jenjang} = kunci `commission.achievement_*` yang berlaku pada akhir bulan
                        23.59.59 WIB (kunci bertanggal)
  sales         list    CATATAN per sales (tinjauan akhir I2 — tidak pernah menggagalkan akrual):
                        posting gaji → [{sales_id (user_id slip), employee_id, total}] = komisi mesin slip yang diakru;
                        akrual manual → [{sales_id, total, breakdown[]}] = hasil mesin yang sama dengan total jurnal;
                        tanpa rincian pemanggil → dihitung ulang upaya terbaik, sales yang mesinnya galat =
                        {sales_id, total: null, galat}
  sales_sumber  string  "slip_gaji" | "akrual" | "hitung_ulang" — asal catatan `sales`
  sales_galat   string? kalimat bila daftar sales / rincian slip tidak bisa disusun (sales = [])
  journal_id    string  FK journal_entries.id — jurnal `incentive_accrual` (source_id "<entity_id>:<period>") yang
                        membekukan; dianulir → dokumen diabaikan pembaca dan DIGANTI pada akrual berikutnya
  recorded_at   string  ISO UTC
  recorded_by   string  nama pembuat akrual
  replaces      object? {id, journal_id, recorded_at, recorded_by} potret yang diganti (jurnalnya tidak hidup lagi)

ℹ️ UNIK per (entity_id, period) — indeks wajib `uq_commission_period` (PK-14 REQUIRED_UNIQUE_INDEXES). Dokumen yang
   jurnal akrualnya hidup dikembalikan, tidak ditimpa; yang jurnalnya tidak ada/dianulir diganti di tempat
   (replace_one); dua akrual bersamaan → yang kalah membaca pemenang.
ℹ️ Yang dibekukan = ATURAN (jenjang capaian bulan itu; aturan per baris sudah dipotret di `items[].commission_rule`).
   Gaji/kartu/koreksi akrual tetap menghitung dari aturan beku ini, sehingga angka hanya berubah karena data sumber
   (bayar/retur). `sales[]` adalah catatan (D3), bukan sumber angka.
⚠️ JANGAN BUAT: commission_freezes, commission_snapshots, period_commission (sebagai koleksi).
```

### commission_carry_balances  [BTP-5 — finalisasi komisi & saldo potongan per PT per sales per bulan (A1-6, R13/R16/R17)]
```
Collection:  commission_carry_balances   Prefix: cmsb_
Penulis:     services/commission_rules.py (catat_saldo_potongan) — dipanggil setiap komisi PT·bulan DIFINALKAN:
             gl_service.post_incentive_accrual (akrual manual, termasuk total PT 0 tanpa jurnal; akrual diulang/koreksi)
             dan posting_registry.post_payroll (akrual dari slip; tanpa akrual — mode `pay_on_invoice` atau komisi slip 0
             — dicatat sesudah jurnal gaji, bertaut jurnal gaji). Sumber angka = hasil mesin (`compute_commission`):
             akrual manual langsung, posting gaji dari `hr_payslips.commission_engine`. Satu catatan per sales yang
             difinalkan (juga saldo 0).
Pembaca:     services/commission_rules.py (saldo_potongan_awal → `carry_in` bulan berikutnya = `carry_out` bulan ini, PT
             yang sama; "Semua PT" = jumlah per PT; penilai_final → bulan bayar final sebelum batal/tutup sisa, R16) →
             sales_force_service._compute_commission_per_sku
Key Fields:
  id              string  prefix "cmsb_"
  entity_id       string  FK business_entities.id (PT spesifik)
  sales_id        string  FK users.id
  period          string  "YYYY-MM" bulan yang difinalkan
  carry_out       number  ≤ 0 — sisa potongan yang dibawa ke bulan berikutnya (min(0, commission_raw + carry_in))
  carry_in        number  ≤ 0 — saldo yang masuk ke bulan ini
  commission_raw  number  komisi mentah bulan ini (bisa negatif karena koreksi batal / tutup sisa)
  total           number  komisi yang dibayar/diakru bulan ini (≥ 0)
  source          string  "akrual" | "slip_gaji" — jalur finalisasi
  journal_id      string  jurnal finalisasi: `incentive_accrual` hidup, atau jurnal gaji `payroll_run` (mode tanpa
                          akrual / komisi slip 0); "" = bulan difinalkan tanpa jurnal (akrual bertotal 0)
  finalized_at    string  ISO UTC — saat ANGKA yang difinalkan dihitung (R19): `computed_at` slip (buat / hitung ulang
                          proses gaji) atau hitung mesin saat akrual; ditimpa HANYA bila finalisasi lama sudah tidak
                          berlaku (jurnalnya void / dibalik) saat catatan ditulis
  recorded_at     string  ISO UTC — finalisasi terakhir
  recorded_by     string  nama pemfinal

ℹ️ UNIK per (entity_id, sales_id, period) — indeks wajib `uq_commission_carry` (PK-14 REQUIRED_UNIQUE_INDEXES).
   Setiap finalisasi = upsert (tidak pernah basi). Bulan bayar "final sebelum batal/tutup sisa" (R16) =
   `finalized_at` < waktu peristiwa dan catatan berlaku.
ℹ️ Catatan berlaku (`catatan_berlaku`) bila `journal_id` kosong atau jurnalnya tidak `void` dan belum dibalik (anulir
   proses gaji membalik jurnal gaji); tidak berlaku → saldo & status final bulan itu tidak dibaca sampai difinalkan lagi.
⚠️ JANGAN BUAT: commission_carry, carry_balances, commission_deductions (sebagai koleksi); saldo TIDAK disimpan di
   `commission_period_rules.sales[]`.
```

### cash_holdings + cash_deposits  [PM-T4 — tunai yang diterima sales dicatat sebagai titipan sampai disetor]

Bila PT memilih `pembayaran.sales_terima_tunai = titipan` (bawaan `kas_langsung` = perilaku lama), kwitansi tunai yang
dicatat orang tanpa izin `cash.create` tidak membuat kas: piutang tetap turun (alokasi kwitansi biasa), uangnya tercatat
di sini. `dilarang` = 403. Logika: `services/cash_holding_service.py`. Kedua koleksi ber-PT (`entity_scope`).

```
cash_holdings — satu per kwitansi titipan (id `cth_` + id kwitansi tanpa awalan; `$setOnInsert`), nomor `TTP-` per PT
  id, number, entity_id                PT kwitansi
  holder_user_id, holder_name          pencatat kwitansi = pemegang uang
  receipt_id, receipt_number, customer_id, customer_name
  amount                               uang baru kwitansi (tetap)
  deposited_amount                     sudah disetor — naik HANYA lewat penerimaan setoran (syarat ≤ amount − alokasi)
  deposit_ids[]                        setoran yang sudah diterapkan (penanda: ulang tidak menggandakan)
  status                               dipegang · sebagian_disetor · disetor · batal
  received_at, due_at                  waktu terima (= tanggal kwitansi); batas setor saat dibuat ("" = PT tanpa tenggat)
  gl_status, gl_error, gl_failed_at, journal_entry_id, je_id   jurnal titipan (P3; jenis Posting Gagal `cash_holding`)
  void_gl_status …                     hanya kompensasi kwitansi gagal lahir
  voided_at, voided_reason
cash_deposits — setoran, id `cdp_…`, nomor `STT-` per PT (`STR-` sudah dipakai setoran kewajiban gaji PK-22)
  id, number, entity_id, holder_user_id, holder_name, amount, note
  allocations[] {holding_id, holding_number, receipt_number, amount}   tanpa pilihan = titipan tertua lebih dulu
  status                               diajukan · diterima · ditolak · dibatalkan
  receive_intent {status pending|done, account_id, cash_txn_id, by, by_id, at, done_at}   NIAT penerimaan (id kas tetap)
  account_id, account_snapshot, received_by, received_by_id, received_at
  cash_txn_id                          kas masuk `ref_type: cash_deposit` (Dr kas rekening / Cr 1-1280 lewat `contra_account_code`)
  gl_status, gl_error, journal_entry_id   jurnal kas setoran (jenis Posting Gagal `cash_deposit`)
  decided_by(_id), decided_at, decision_reason   tolak / batal
```

Jurnal: titipan = Dr `kas_bank.piutang_karyawan` (1-1280) / Cr sisi kredit jurnal kas kwitansi biasa
(`gl_service._receipt_lines`: Piutang untuk bagian yang sudah diakui, Uang Muka Pelanggan untuk sisanya), sumber
`cash_holding`. Setoran diterima = jurnal kas biasa. Indeks: `cash_holdings.uq_holding_receipt` (unik `receipt_id`,
wajib-ada), `(entity_id, holder_user_id, status)`, `(entity_id, status, received_at)`; `cash_deposits (entity_id, status,
created_at)`, `(entity_id, holder_user_id, status)`. Invarian INV-TTP-01 (`verify_data_integrity.py` lapisan `titipan`):
per PT Σ (amount − deposited_amount) titipan tidak batal = Σ debit 1-1280 jurnal `cash_holding` − Σ kreditnya di
`cash_holding_reversal` − Σ kredit 1-1280 jurnal kas `cash_deposit`; pembangun ulang `hitung_ulang_disetor`.
⚠️ JANGAN BUAT: titipan_sales, sales_cash, setoran (sebagai koleksi).

### bank_accounts  [EPIC7-B IMPLEMENTED — Kas & Bank multi-akun + rekonsiliasi]
Koleksi kanonik `bank_accounts` (prefix `bank_`). Master akun kas/bank; mutasi tetap
di `cash_transactions` (SSOT kas) dgn field opsional `account_id`.
```
Collection:  bank_accounts                Prefix: bank_
Router:      routers/bank.py
Service:     services/bank_service.py
Component:   features/finance/BankAccountsView.jsx
Key Fields:
  id                string  prefix "bank_"
  name              string  nama tampilan akun
  account_type      enum    bank | cash
  bank_name         string  nama bank (kosong utk cash)
  account_number    string  no rekening
  entity_id         string  FK entities.id | "all"
  opening_balance   float   saldo awal
  currency          string  default IDR
  is_active         bool
  created_at / updated_at
  — PM-T1 (K-34): field atas nama, peruntukan, cara bayar, bawaan per PT —
  holder_name               string  atas nama ("" = belum diisi)
  purposes                  list    penerimaan_pelanggan · pembayaran_pemasok · gaji · operasional
  payment_method_codes      list    kode `payment_methods` yang dilayani (bank: ber-rekening bank; kas: tunai)
  default_receiving_methods list    rekening ini bawaan penerimaan PT-nya untuk cara bayar itu
                                    (indeks wajib uq_default_receiving: unik (entity_id, kode), parsial ".0 ada")
  show_on_documents         bool    tampil di dokumen pelanggan (wajib atas nama + nomor, jenis bank)
  Rekening lama tanpa field ini dibaca dengan nilai awal (`bank_service.bidang_efektif`); disimpan saat rekening PT
  itu ditulis lagi, atau lewat `scripts/blueprint/pmt1_isi_rekening.py --terapkan` (bawaan lapor; data nyata = H3).
  Field peka (nomor, bank, atas nama, peruntukan, cara bayar, bawaan, tampil di dokumen, aktif) + rekening baru
  mengikuti `kontrol.ubah_rekening.*` → `bank_account_changes`.

Saldo akun (derived) = opening_balance + Σ(in) − Σ(out) cash_transactions
  posted (status≠void) dengan account_id = akun tsb.
Rekonsiliasi (PK-21): saldo terekonsiliasi & "belum dicocokkan" diturunkan dari
  cash_transactions.reconciled_amount (`bank_recon_service.txn_reconciled`), bukan dari tanda tersimpan.
ℹ️ Endpoint: GET /api/bank-accounts, POST /api/bank-accounts,
  PATCH /api/bank-accounts/{id}, GET /api/bank-accounts/{id}/ledger. RBAC: permission "cash" (admin/manager).
  PM-T1: GET /api/bank-accounts/receiving?entity_id=&method= (salah satu `order.create`, `ar_receipt.create`,
  `cash.view`; tanpa saldo) — rekening penerima uang pelanggan per PT & cara bayar, `is_default`.
  POST /api/cash-transactions/{id}/reconcile — PK-21: DIMATIKAN, selalu 410 (sesudah cek izin `cash.create`
  + entitas); tanda manual ya/tidak tidak ada lagi.
⚠️ JANGAN BUAT: bank, banks, accounts, rekening (sebagai koleksi).
```

### bank_statement_lines  [R6.1 IMPLEMENTED — Bank Reconciliation otomatis]
Koleksi baru `bank_statement_lines` (prefix `stmtline_`, batch `stmtbatch_`). Mutasi
rekening koran yang diimpor untuk direkonsiliasi terhadap `cash_transactions` (SSOT kas).
**GL-SAFE**: rekonsiliasi TIDAK mengubah jurnal terposting — hanya MENAUTKAN
statement line ↔ cash_transaction + menandai `reconciled`.
```
Collection:  bank_statement_lines        Prefix: stmtline_ (import_batch: stmtbatch_)
Router:      routers/bank_reconciliation.py
Service:     services/bank_recon_service.py
Component:   features/finance/BankReconciliationView.jsx (Keuangan → Rekonsiliasi Bank)
Key Fields:
  id                string  prefix "stmtline_"
  bank_account_id   string  FK bank_accounts.id
  entity_id         string  FK business_entities.id
  stmt_date         string  YYYY-MM-DD (tanggal mutasi)
  amount            float   >0 (nilai absolut)
  direction         enum    in | out
  description       string  keterangan mutasi
  ref               string  referensi (no. dok/invoice) utk heuristik match
  external_id       string  id unik dari bank (dedupe kuat bila tersedia)
  status            enum    unmatched | matched | ignored | holding   (holding = FASE G-8)
  matched_txn_id    string  FK cash_transactions.id (bila matched 1:1)
  matched_txn_ids[] string  FASE G-8 — daftar transaksi tertaut (split 1:N / gabung N:1)
  allocations[]     object  FASE G-8 — {txn_id, amount} Σ == amount baris (INV-BNK-01)
  match_kind        enum    FASE G-8 — 1:1 | 1:N | N:1
  score             float   FASE G-8 — skor berbobot pencocokan (0..100+)
  score_explain[]   object  FASE G-8 — {label, points} alasan skor yang dibaca manusia
  suggestions[]     object  FASE G-8 — usulan berperingkat (pita 60..79) belum ditautkan
  counterparty      string  FASE G-8 — nama pihak hasil tebakan parser
  desc_key          string  FASE G-8 — sidik jari berita transfer (untuk aturan belajar)
  holding           object  FASE G-8 — {cash_txn_id, cash_number, je_id, je_number, at, by, note}
  holding_allocated[] object FASE G-8 — {order_id, amount, je_id, reason_code, by, at}
                     PK-15 — + id (`bha_…`, bagian kunci jurnal `<id baris>:<id alokasi>`), status
                     pending|applied|done (butir lama tanpa status = done), gl_status posted|failed, gl_error,
                     je_number, order_number, outstanding_after. `sales_orders.payments[].alloc_id` = id alokasi
                     (metode `bank_holding`). Sisa tersedia = holding_remaining − Σ butir pending.
  holding_remaining float   FASE G-8 — sisa titipan belum dialokasikan (INV-BNK-03)
  ai_card_id        string  AG-T3 — catatan cocok dari kartu tindakan asisten (dicocokkan di layar → field dihapus);
                     juga `holding_allocated[].ai_card_id` untuk alokasi titipan dari kartu
  format_id         string  FASE G-8 — FK bank_statement_formats.id (template pembaca)
  pay_code_hits[]   object  PM-T3 — kode bayar (PM-T2, `payment_codes`) milik PT mutasi yang ditemukan di berita +
                     referensi saat impor: {code, order_id, order_number, customer_id}. Mutasi lama tanpa field ini
                     dihitung di memori saat dibaca (tidak ditulis). Skor: kode menunjuk pesanan yang dialokasi kwitansi
                     di balik kas → nominal sama = minimal ambang otomatis; nominal beda = usulan saja (tidak otomatis)
  match_type        enum    auto | manual
  matched_at / matched_by / import_batch / created_at / updated_at
Auto-match:  1:1 line↔txn (akun sama, arah sama, |Δamount| ≤ toleransi,
             |Δtanggal| ≤ window hari; prioritas ref cocok lalu tanggal terdekat).
             Idempotent: hanya proses line unmatched & txn reconciled≠true.
Efek match:  cash_transactions.reconciled_amount += alokasi (bersyarat ≤ amount) dan turunannya
             (reconciled, reconciled_at, matched_line_ids, matched_line_id) dalam SATU pembaruan ber-pipeline.
             Unmatch (PK-21): klaim baris `match_lock` (status matched) → pengurangan bersyarat
             reconciled_amount ≥ alokasi − 0,01 per alokasi → baris unmatched; kalah klaim = 409 (append-only;
             GL tak berubah, kecuali baris biaya bank: kas void + jurnal dibalik sesudah klaim).
  match_lock / match_lock_at  string  kunci operasi cocok/lepas (basi > 10 menit boleh diambil alih)
Endpoints:   POST /api/bank-reconciliation/import · POST /api/bank-reconciliation/auto-match ·
             GET /api/bank-reconciliation/lines · GET /api/bank-reconciliation/summary ·
             POST /api/bank-reconciliation/lines/{id}/match|unmatch|ignore
RBAC:        permission "cash" (admin/manager).
⚠️ JANGAN BUAT: bank_statements, rekening_koran, statements, reconciliations,
   fin_bank_statements, fin_reconciliation_sessions — gunakan bank_statement_lines.
```

### bank_statement_formats + bank_match_rules  [FASE G-8 IMPLEMENTED — parser multi-bank & aturan belajar]
Dua koleksi pendukung rekonsiliasi bank. **Keduanya SCOPED** (`entity_id`) bersama
`bank_statement_lines` — sebelum FASE G-8 mutasi bank TIDAK ter-scope sehingga user PT-A
cukup mengirim `bank_account_id` PT-B untuk membacanya (ditutup + POC bukti-merah).
```
Collections: bank_statement_formats (prefix bsf_) · bank_match_rules (prefix bmr_)
Router:      routers/bank_reconciliation.py
Services:    services/bank_statement_parser.py (murni, tanpa DB) · services/bank_recon_service.py
Components:  features/finance/bank/ReconFormatsPanel.jsx · ReconRulesPanel.jsx
Config:      config_catalog_bank.py (grup `bank` di Pusat Pengaturan)

bank_statement_formats — TEMPLATE cara membaca rekening koran (bisa dibuat user):
  id                string  prefix "bsf_"
  entity_id         string  FK business_entities.id  (SCOPED)
  name              string  nama template
  bank_code         string  bca | mandiri | bni | bri | permata | generic | custom
  file_kind         enum    csv | mt940 | ofx
  delimiter         string  pemisah kolom CSV
  has_header        bool    baris pertama header?
  skip_rows         int     baris awal yang dilewati
  decimal_style     enum    auto | id (1.234.567,89) | en (1,234,567.89)
  date_format       string  auto | dd/mm/yyyy | dd-mm-yyyy | yyyy-mm-dd | yyyymmdd | yymmdd
  columns           object  {date, description, ref, amount, amount_in, amount_out,
                            direction, balance, external_id} → NAMA header ATAU indeks kolom
  in_markers[] / out_markers[]  penanda arah dana (mis. CR/DB, K/D)
  header_signature[]  tanda tangan untuk DETEKSI OTOMATIS template
  builtin           bool    preset bawaan (5 bank + MT940 + OFX), boleh disalin & diubah
  active            bool    hapus = nonaktifkan (bukan hilang)

bank_match_rules — aturan hasil PEMBELAJARAN dari pencocokan manual:
  id                string  prefix "bmr_"
  entity_id         string  FK business_entities.id  (SCOPED)
  bank_account_id   string  FK bank_accounts.id
  desc_key          string  sidik jari berita transfer (angka dibuang)
  direction         enum    in | out
  counterparty      string  nama pihak hasil tebakan parser
  sample_desc       string  contoh berita transfer asli
  hits              int     berapa kali pola ini dicocokkan manual
  status            enum    suggested | active | rejected
  created_by / decided_by / decided_at / created_at / updated_at

Aturan HANYA ditawarkan (status `suggested`) setelah pola sama dicocokkan manual
`bank.rule_learn_after` kali (bawaan 3×) dan baru berlaku setelah MANUSIA menyetujui
(`activate`). Aturan aktif menambah `bank.rule_bonus_score` poin pada skor pencocokan.
Endpoints:   GET/POST /api/bank-reconciliation/formats · DELETE .../formats/{id} ·
             POST /api/bank-reconciliation/preview · POST .../import-file ·
             GET /api/bank-reconciliation/rules · POST .../rules/{id}/decide
RBAC:        permission "cash" (admin/manager).
⚠️ JANGAN BUAT: bank_formats, statement_templates, bank_rules, match_rules — gunakan
   bank_statement_formats & bank_match_rules.
```

### contra_bons  [FASE G-7 IMPLEMENTED — Kontrabon / siklus tukar faktur supplier]
Supplier tekstil tidak ditagih per surat jalan: mereka datang **sekali per siklus** membawa
setumpuk faktur, lalu terjadi ritual **tukar faktur** (faktur supplier ditukar tanda terima
kami, pembayarannya dijadwalkan). Satu kontrabon menggabungkan BANYAK `vendor_bills` satu
supplier menjadi **satu tanda terima + satu pembayaran**, berikut potongan terstruktur yang
menunjuk dokumen nyata. **SCOPED** (`entity_id`) — kontrabon PT lain tidak terlihat (403).
```
Collection:  contra_bons                Prefix: cbn_   Nomor: <ENT>/CB-#####
Router:      routers/contra_bons.py
Services:    services/contra_bon_service.py   (siklus, potongan, 3-way, pembayaran)
             services/contra_bon_reminder.py  (jadwal tukar faktur + pengingat H-n)
             services/contra_bon_scan.py      (pemeriksa INV-CB-01..04)
Components:  features/purchasing/contrabon/ContraBonsView.jsx · ContraBonListTable.jsx ·
             ContraBonDetailPanel.jsx · ContraBonParts.jsx · ContraBonCreateWizard.jsx ·
             UnbilledReceiptsTab.jsx · ExchangeSchedulesTab.jsx · ExchangeScheduleModal.jsx ·
             DeductionModal.jsx · DecisionModal.jsx · PayModal.jsx ·
             PaymentScheduleModal.jsx · ReasonNoteModal.jsx · contraBonApi.js
             (jembatan G-8: features/finance/bank/ReconContraBonModal.jsx)
Config:      config_catalog_contrabon.py (grup `kontrabon` di Pusat Pengaturan — 10 kunci)
Invarian:    INV-CB-01..04 (scripts/verify_data_integrity.py lapisan `contrabon`)
Job:         contra_bon_reminder (harian 07:30 WIB, services/scheduler_service.py)
PDF:         doc_type `contra_bon` → "Tanda Terima Kontrabon" (esignable)

  id                string  prefix "cbn_"
  number            string  <ENT>/CB-##### (sequence atomik number_sequences, doc_type CB)
  entity_id         string  FK business_entities.id  (SCOPED)
  supplier_id       string  FK suppliers.id · supplier_name/code/npwp/supplier_pic snapshot
  cycle_date        string  tanggal tukar faktur · due_date: jatuh tempo (dari termin supplier)
  status            enum    draft | submitted | verified | approved | scheduled_payment |
                            paid | disputed | cancelled
  bills[]           object  {bill_id, bill_number, supplier_invoice_no, po_id, po_number,
                            bill_date, due_date, grand_total, outstanding_at_pick,
                            applied_amount, settled_amount, claim_deduction_info,
                            match:{status, exceptions[], po_status, evaluated_at}}
  deductions[]      object  {id, kind, label, ref_type, ref_id, ref_number, bill_id,
                            exception_key, amount, reason_code, note, posts_gl,
                            gl_journal_id, applied_at, added_by, added_at}
                            kind: purchase_return | supplier_advance | supplier_penalty |
                                  match_variance | other_agreed
  decisions[]       object  {at, by, exception_key, bill_id, action(accept|deduct|dispute),
                            reason_code, reason_label, amount, note, exception_detail}
  totals            object  {bills_total, deductions_total, net_payable, paid_total, outstanding}
  match_summary     object  {status, exceptions_count, pending_count, pending_keys[],
                            exceptions_value}
  schedule          object  {planned_payment_date, method, bank_account_id, notes}
  payments[]        object  {id, amount, method, cash_type, cash_txn_id, cash_txn_number,
                            bank_account_id, bank_line_id, notes, paid_by, paid_at,
                            allocations[]}
  policy_snapshot   object  toleransi & ambang yang berlaku saat dokumen dibuat
  timeline[]        object  {at, event, label, actor, note}
  refs[]            object  relasi dokumen dua arah (FASE G-4)
  created_by / created_by_id / created_at / updated_at · submitted_* verified_* approved_*
  paid_at · disputed_at · dispute_reason_code · dispute_note · cancelled_at · cancel_note

PK-05 — field tambahan: `version` (bilangan; simpan berprasyarat versi, kalah → 409), `gl_status`/`gl_error`
(jurnal potongan; panel Posting Gagal jenis `contra_bon`), `payments[].payment_intent_id`.

### journal_proposals  [KF-T6 — jurnal manual yang menunggu orang kedua]
Bila `kontrol.jurnal_manual.min_orang` PT itu = "2" (atau nilai jurnal di atas `kontrol.jurnal_manual.batas_nominal`),
`POST /api/gl/journal` memvalidasi isi + periode (`gl_service.create_manual_entry(hanya_periksa=True)`) lalu menyimpan
USULAN (202 `menunggu_orang_kedua`); tidak ada baris `journal_entries`. Orang lain yang berwenang menyetujui → jurnal
diposting lewat `create_manual_entry` (periode diperiksa ulang) dengan `created_by` = pengusul, `approved_by` = penyetuju.
**SCOPED** (`entity_id` = PT buku). Dataset Pusat Export `journal_proposals`.
```
Collection:  journal_proposals          Prefix: jprop_
Router:      routers/gl.py              (GET /gl/journal-proposals?status=, POST {id}/approve, POST {id}/reject)
Service:     services/journal_proposal_service.py  (ajukan, daftar, setujui, tolak)
Index:       uq_id (unik) · (entity_id, status, proposed_at)

  id · entity_id · payload (isi JournalEntryCreate) · total_debit
  status            pending | posting (klaim sementara) | posted | rejected
  proposed_by_id · proposed_by · proposed_at · decided_by_id · decided_by · decided_at
  reject_reason · journal_id · journal_number · updated_at
```
`journal_entries` jurnal manual dua orang mendapat `created_by_id`, `approved_by`, `approved_by_id`, `approved_at`,
`proposal_id`.

### ap_payment_intents  [PK-05 — niat bayar hutang: satu pintu bayar faktur pemasok & kontrabon]
Setiap pembayaran hutang (faktur langsung, kontrabon, kontrabon dari mutasi bank) lahir sebagai NIAT dengan id tetap
dari kunci idempotensi. Langkahnya berurutan dan masing-masing idempoten: periksa (tanpa tulis) → niat → faktur → kas →
dokumen kontrabon → jurnal (tahan-gagal) → selesai. **SCOPED** (`entity_id` = PT dokumen sasaran).
```
Collection:  ap_payment_intents         Prefix: apn_ (apn_ + 24 heksa SHA-256 dari kind|target_id|kunci)
Router:      routers/ap_payments.py     (GET pending, GET accounts, POST {id}/resume, POST {id}/cancel)
Service:     services/ap_payment_service.py  (pay_payable, resume, cancel, repost_journals)
Index:       uq_id (unik) · (kind, target_id, status) · (entity_id, status, created_at)

  id · entity_id · kind (vendor_bill | contra_bon) · target_id · target_number
  request_hash      SHA-256 nominal|tanggal|rekening|metode — kunci sama + isi beda → 409
  amount · advance_amount · deduction_total · paid_at · bank_account_id · cash_type · method · notes · bank_line_id
  allocations[]     {bill_id, bill_number, amount, source(deduction|cash), payment_entry_id (pay_<24 heksa>_<n>), applied_at}
  deductions[]      {deduction_id, kind, amount, posts_gl, journal_id, label}
  cash_txn_id / cash_txn_number · advance_cash_txn_id / advance_cash_txn_number  (cash_<24 heksa>, …a)
  status            pending | done | cancelled      step: intent | bills | cash | document | journal
  gl_status/gl_error · lock_token · error · attempts · variance_decision_id · created_* · updated_at · done_at
```
`cash_transactions` mendapat `payment_intent_id` dan selalu `account_id` untuk kas bayar hutang. `vendor_bills`: indeks
unik parsial `uq_supplier_invoice` (entity_id, supplier_id, supplier_invoice_no) untuk status aktif.

suppliers.invoice_exchange (BUKAN koleksi baru — jadwal adalah ATRIBUT supplier):
  {mode: none|weekly|biweekly|monthly, weekday 0..6, day_of_month 1..28, pic_name,
   notes, anchor_date, updated_by, updated_at}

ATURAN YANG DIJAGA:
  * Satu `vendor_bill` hanya boleh berada di SATU kontrabon belum `cancelled`, dan
    Σ `applied_amount` atas satu faktur ≤ `grand_total` (INV-CB-01).
  * `net_payable == Σ bills.applied_amount − Σ deductions.amount` (≥ 0); kontrabon `paid`
    → `Σ payments.amount == net_payable` (INV-CB-02).
  * Setiap pengecualian 3-way DI LUAR toleransi wajib punya keputusan berlabel sebelum
    status melewati `verified` (INV-CB-03).
  * Satu dokumen potongan (`purchase_return`/`ap_advance`) hanya boleh dipakai di SATU
    kontrabon belum `cancelled`; potongan klaim makloon yang sudah menempel di faktur
    DITOLAK jadi potongan kontrabon (INV-CB-04) — kalau tidak, hutang berkurang dua kali.
  * Pembuat kontrabon TIDAK boleh menyetujui kontrabonnya sendiri; di atas
    `contra_bon.approval_threshold_rupiah` wewenangnya naik ke `high_value_approval_role`.
Jurnal potongan saat kontrabon DIBAYAR (services/gl_service.post_contra_bon_deduction):
  purchase_return  : TIDAK ada jurnal baru (Dr 2-1100 / Cr 1-1300 sudah lahir saat retur
                     disetujui) — di kontrabon ia jadi pelunasan NON-KAS pada faktur
  supplier_advance : Dr 2-1100 / Cr 1-1400      supplier_penalty : Dr 2-1100 / Cr 4-9300
  match_variance   : Dr 2-1100 / Cr 2-1150      other_agreed     : Dr 2-1100 / Cr 4-9000
Pembayaran        : SATU `cash_transactions` (ref_type `contra_bon`, nomor kontrabon di
                    deskripsi → langsung jadi kandidat Rekonsiliasi Bank G-8)
Endpoints:   GET /api/contra-bons · .../meta · .../summary · .../status-counts ·
             .../prepare · .../unbilled-receipts · .../exchange-schedules ·
             .../bank-line-candidates/{line_id} · GET .../{id} · .../{id}/receipt ·
             POST /api/contra-bons · .../{id}/deductions · DELETE .../deductions/{ded_id} ·
             POST .../{id}/decide · submit · verify · approve · schedule · pay ·
             pay-from-bank-line/{line_id} · dispute · cancel · POST .../run-reminder ·
             PUT /api/suppliers/{supplier_id}/invoice-exchange
RBAC:        permission "contra_bon": view · create · update · verify · approve · pay
             (warehouse: view saja — mereka pemilik jawaban "GR belum ditagih",
              tetapi tidak memutus uang)
⚠️ JANGAN BUAT: contrabons, contra_bon_items, invoice_exchanges, supplier_cycles,
   contra_bon_deductions — gunakan `contra_bons` (potongan & jadwal sudah inline).
```

### interco_transactions + interco_accounts + interco_settlements  [FASE G-6 IMPLEMENTED — Transaksi Antar Entitas (jual-beli antar-PT)]
PK-06 — field tambahan: `interco_transactions` dan `interco_returns` (tiap dokumen = satu sisi) `gl_status`
(`pending|posted|failed|not_required`), `gl_error`, `gl_journal_id`; `interco_transactions.settlement_ids`.
`interco_settlements`: `status` `pending|posted|cancelled`, `gl_status_payer/_payee`, `gl_error_payer/_payee`,
`gl_journal_id_payer/_payee`, ringkasan `gl_status`/`gl_error`, `payer_account_id`, `payee_account_id`, `cash_out_id`,
`cash_in_id`, `idempotency_key`, `cancel_reason`, `applied[].applied_at`, `applied[].previous_status`. Jurnal kembar lewat
`services/twin_journal.py` (`preflight_twin`, `post_twin`); panel Posting Gagal jenis `interco_transaction`,
`interco_return`, `interco_settlement_payer`, `interco_settlement_payee`.
PK-30 — field tambahan `interco_transactions` (kedua dokumen kembar): `items[].quantity_ordered` (jumlah pesanan semula,
diisi saat penyesuaian panjang; `quantity`/`line_subtotal` = nilai aktual), `length_adjustment` `{transfer_id,
from_subtotal, to_subtotal, delta_subtotal, delta_tax, delta_total, lines[{product_id, from_qty, to_qty}], by, at}` (ada =
sudah disesuaikan, penanda aman-diulang), `gl_status_adj`/`gl_error_adj`/`gl_journal_id_adj` (jurnal
`{pair}:adj:seller|buyer`; panel Posting Gagal jenis `interco_adj`), `terms_override` `{by, by_id, reason, at,
pricing_mode {standar, dipakai}|null, ppn_mode {standar, dipakai}|null, lines[{product_id, standard_price|null,
used_price}]}`, `seller_is_pkp`/`buyer_is_pkp` (potret PKP saat dibuat), `tax_warning` (`pembeli_non_pkp` | ""). Tanpa
migrasi. Kunci `antar_entitas.selisih_panjang` (PT penjual). Jalur `POST /api/transfers/inter-company` ditutup (410).
Antar-PT itu **jual-beli**, bukan pindah gudang: PT KSC menjual kain ke CV Kanda dengan
**harga internal dari kontrak** dan mengambil **margin**; keduanya PT terpisah dengan buku,
pajak, dan pelanggan sendiri. Satu transaksi lahir sebagai **DOKUMEN KEMBAR** (satu di tiap
PT, saling menunjuk lewat `pair_id`) sehingga isolasi lintas-PT TIDAK dilonggarkan. Barang
fisiknya tetap berjalan lewat **tugas gudang** (`warehouse_transfers` ber-`interco_pair_id`)
— dan justru karena itu jurnal at-cost M-3 DILEWATI supaya tidak dobel. **SCOPED** (`entity_id`).
```
Collections: interco_transactions  Prefix: ict_   Nomor: <ENT>/IC-#####   (2 dokumen per pair)
             interco_accounts      id: ica_{from}_{to}   (saldo per pasangan PT, proyeksi)
             interco_settlements   Prefix: ics_   Nomor: <ENT>/ICS-#####  (netting)
Router:      routers/interco.py            (/api/interco/*)
             routers/consolidation.py      (POST /api/consolidation/sync-g6)
Services:    services/interco_service.py       (harga · PPN · siklus · jurnal · saldo · netting ·
                                                jembatan gudang · pembalikan · pair_journal)
             services/consolidation_service.py (eliminasi unrealized profit: create/update/remove)
             services/roll_service.py          (execute_ownership_transfer + lot pindah pemilik)
Components:  features/finance/interco/IntercoView.jsx · IntercoCreateModal.jsx ·
             IntercoSettlementModal.jsx · IntercoDetailPanel.jsx · IntercoCancelModal.jsx ·
             InternalContractWizardModal.jsx · intercoApi.js
             (eliminasi: features/finance/GroupConsolidationView.jsx)
Config:      config_catalog_interco.py (grup `antar_entitas` — 8 kunci; `ppn_mode`, `selisih_panjang` ber-scope PT)
Invarian:    INV-IC-01..06 (scripts/verify_data_integrity.py lapisan `interco`)
POC:         backend/tests/test_g6_poc.py (21 skenario, bukti-merah, nol residu)
Doc types:   `interco_transaction` & `interco_settlement` terdaftar di doc_refs_service (G-4)
Akun GL:     1-1250 IC-AR · 2-1250 IC-AP · 1-1310 **Persediaan Dalam Perjalanan (Antar-PT)** ·
             1-1300 Persediaan · 4-1000 Pendapatan · 5-1000 HPP · 2-1200/1-1500 PPN

interco_transactions:
  id                string  prefix "ict_"          pair_id  string  prefix "icp_" (dokumen kembar)
  number            string  <ENT>/IC-##### (sequence per entitas)
  entity_id         string  SCOPE = PT pemilik dokumen ini
  role              enum    seller | buyer         counterpart_id / counterpart_number
  seller_entity_id / seller_entity_name · buyer_entity_id / buyer_entity_name
  items[]           object  {product_id, sku, product_name, quantity, unit, unit_price,
                            price_source(fixed_price|at_cost|cost_plus_pct|override),
                            contract_id, line_subtotal, notes}
  subtotal / tax_apply / tax_rate / tax_amount / grand_total / settled_amount
  pricing_mode      enum    fixed_price | at_cost | cost_plus_pct   (bawaan dari config)
  ppn_mode          enum    ikut_pkp | tanpa_ppn | dengan_ppn       (scope PT)
  status            enum    draft | confirmed | shipped | received | invoiced | settled |
                            disputed | cancelled
  doc_date / due_date / notes
  warehouse_transfer_id / warehouse_transfer_code / warehouse_transfer_status
                            (jembatan US8: waiting_approval | completed | cancelled)
  timeline stamp    created_at/by · confirmed_at/by · shipped_at/by · received_at/by ·
                    invoiced_at/by · settled_at · cancelled_at/by · cancel_reason
  refs[]            object  relasi dokumen dua arah (FASE G-4)

interco_accounts (PROYEKSI — jangan pernah $inc, selalu hitung ulang):
  id ica_{from}_{to} · entity_id (SCOPE) · from_entity_id/name · to_entity_id/name
  role enum receivable|payable · open_count · gross_amount · settled_amount · outstanding
  aging_days · reminder_active (dari `antar_entitas.settlement_reminder_days`) · updated_at

interco_settlements:
  id ics_ · number <ENT>/ICS-##### · entity_id = PT pembayar (SCOPE)
  payer_entity_id/name · payee_entity_id/name · settle_date · method netting|transfer|cash
  applied[]  {interco_id, counterpart_id, pair_id, number, counterpart_number, grand_total,
              previous_settled, applied_amount}
  total_applied · status posted · notes · created_by/at

ATURAN YANG DIJAGA:
  * Harga `fixed_price` WAJIB dari kontrak internal aktif (`supplier_contracts` dengan
    `partner_kind="entity"`, `partner_id` = PT pembeli, `product_id` = barang). Tidak ada
    kontrak → transaksi DITOLAK dengan kalimat menuntun (sistem TIDAK menebak harga).
  * Jurnal saat DIKONFIRMASI: penjual `Dr 1-1250 / Cr 4-1000 (+2-1200)`; pembeli
    `Dr 1-1310 (+1-1500) / Cr 2-1250`. Jurnal saat BARANG BERPINDAH: penjual
    `Dr 5-1000 / Cr 1-1300` (biaya nyata roll yang keluar); pembeli `Dr 1-1300 / Cr 1-1310`.
    (INV-IC-01 · INV-IC-06 · menutup drift GL↔subledger)
  * `IC-AR` penjual == `IC-AP` pembeli untuk setiap pasangan PT (INV-IC-02); saldo
    `interco_accounts` == Σ transaksi terbuka − Σ settlement (INV-IC-04).
  * Margin antar-PT WAJIB tereliminasi di konsolidasi selama barang belum terjual keluar —
    dijaga OTOMATIS (`intercompany_eliminations.source_g6_pair_id`, `auto_generated=true`),
    ikut diperbarui saat settlement & dihapus saat pembatalan (INV-IC-03).
  * PPN keluaran penjual == PPN masukan pembeli; mode `tanpa_ppn` → nol di KEDUA sisi (INV-IC-05).
  * Tugas gudang tertaut `interco_pair_id`: jurnal at-cost M-3 TIDAK diposting lagi & roll
    pembeli dinilai ulang ke harga beli internal (INV-IC-06). Satu tugas per transaksi.
  * "Tandai Diterima" DITOLAK bila belum ada tugas gudang selesai (persediaan pembeli tidak
    boleh naik untuk barang yang tidak ada di gudang mana pun).
  * Pembatalan sesudah dikonfirmasi WAJIB ber-alasan (≥5 huruf) → jurnal pembalik
    `{pair}:{sisi}:reversal` di kedua buku + tugas gudang menunggu ikut batal (roll dilepas).
Endpoints:   GET /api/interco/meta · /summary · /transactions · /transactions/{id} ·
             /transactions/{id}/journal · /accounts · /accounts/{from}/{to} · /settlements ·
             /settlements/{id} · /contracts
             POST /api/interco/transactions · .../{id}/confirm|ship|receive|invoice|cancel ·
             .../{id}/warehouse-task · POST /api/interco/settlements ·
             POST /api/consolidation/sync-g6
RBAC:        permission "interco": view · create · update · approve · ship · receive ·
             invoice · cancel · settle   (warehouse: view · ship · receive saja)
⚠️ JANGAN BUAT: intercompany_transactions, interco_docs, interco_balances, ic_settlements,
   internal_price_lists — harga internal hidup di `supplier_contracts` (`partner_kind="entity"`),
   saldo di `interco_accounts`, pelunasan di `interco_settlements`.
```

### finance_cases  [FASE G-9 IMPLEMENTED — Pusat Kasus Keuangan (Finance Exception Desk)]
Antrean **uang yang nyangkut**: salah transfer rekening, masuk rekening pribadi karyawan,
bayar dobel, bayar invoice yang salah, nominal terpotong biaya bank, giro ditolak, dana
tak dikenal, salah PT, kelebihan bayar supplier. **SCOPED** (`entity_id`) — kasus PT lain
tidak boleh terlihat maupun ditutup (403).
```
Collection:  finance_cases              Prefix: fcs_   Nomor: <ENT>/CASE-#####
Router:      routers/finance_cases.py
Services:    services/finance_case_service.py   (siklus, SLA, wewenang, ringkasan)
             services/finance_case_playbooks.py (11 playbook — kesepakatan bisnis)
             services/finance_case_actions.py   (eksekutor: uang benar-benar berpindah)
             services/finance_case_scan.py      (kasus otomatis + pemeriksa INV-CASE)
Components:  features/finance/cases/FinanceCasesView.jsx · CaseInboxTable.jsx ·
             CaseDetailPanel.jsx · CasePlaybookWizard.jsx · CaseCreateModal.jsx
Config:      config_catalog_case.py (grup `kasus` di Pusat Pengaturan — 12 kunci)
Invarian:    INV-CASE-01..03 (scripts/verify_data_integrity.py lapisan `case`)
Job:         finance_case_scan (harian 08:25 WIB, services/scheduler_service.py)

  id                string  prefix "fcs_"
  number            string  <ENT>/CASE-##### (sequence atomik number_sequences)
  entity_id         string  FK business_entities.id  (SCOPED)
  case_type         enum    dana_tak_dikenal | bayar_dobel | salah_rekening_internal |
                            rekening_pribadi_karyawan | pembayar_pihak_ketiga |
                            salah_invoice | selisih_biaya_bank | giro_ditolak |
                            refund_pelanggan | salah_entitas | lebih_bayar_supplier
  title / description string  kalimat manusia (bukan kode)
  amount            float   nominal uang yang dipertaruhkan
  customer_id       string  FK customers.id (opsional)
  supplier_id       string  FK suppliers.id (opsional)
  order_ids[]       string  FK sales_orders.id
  source            object  {kind: bank_holding|bank_line|ar_receipt|vendor_bill|manual,
                             id, label} — asal kasus (deep-link dari layar sumbernya)
  status            enum    open | in_progress | resolved | rejected
  assignee          string  penanggung jawab
  attachments[]     object  {name, path, content_type} — bukti (wajib utk jenis ber-klaim)
  sla_hours         int     dari `case.sla_hours` / `case.sla_hours_high` (nominal besar)
  sla_due_at        string  batas waktu; lewat = TERLAMBAT di inbox
  escalation_level  int     0..2 (naik ke manager lalu admin lewat notifikasi critical)
  reason_code       string  FK amendment_reasons.code (applies_to `finance_case`, G-1)
  reason_label      string  snapshot label alasan
  resolution        object  {action, action_label, effect, produces, amount, note,
                             extra, next_action, auto_resolved, at, by}
  documents[]       object  {kind, id, number, label} — DOKUMEN TURUNAN yang benar-benar
                            lahir: journal_entry · cash_transaction · order_payment ·
                            ar_receipt · penalty · store_credit_entry · supplier_advance ·
                            interco_loan (PK-25 — dokumen antar-PT salah transfer di PT kasus)
  approved_by / approved_at   penyetuju bila nominal >= `case.require_approval_above`
  resolved_by / resolved_at   siapa & kapan kasus ditutup
  auto_source       string  "" | "titipan menganggur" | "kwitansi kembar"
  resolution_intent object  PK-25 — niat penyelesaian: {op_id, action, payload, status: pending|done, started_by,
                            started_at, approver, auto_resolved, steps: {<efek sekali>: {hasil, at}}, last_error,
                            done_at}. `op_id` = "{id kasus}_{aksi}_{jumlah dokumen saat mulai}" (id kas, baris
                            pelunasan, dan nomor kunci jurnal diturunkan darinya). `pending` = efek tersimpan, belum
                            tuntas → `resolve` dengan aksi & isi sama meneruskan, isi lain 409; tutup-tanpa-tindakan 409
  gl_status / gl_error / gl_failed_at / journal_entry_id   PK-18/PK-25 — status jurnal penyelesaian terakhir
                            (posted | failed | not_required); `failed` = panel Posting Gagal jenis `finance_case`
                            (ulang = `resolve` dengan isi niat). Kasus salah PT: juga `gl_status_ic_ap` / `_ic_ar`
                            (+ `gl_error_*`, `gl_journal_id_*`) per sisi jurnal kembar PK-06
  timeline[]        object  {event, label, actor, note, at} — jejak waktu kasus
  refs[]            object  relasi dokumen dua arah (FASE G-4)
  created_by / created_at / updated_at

ATURAN YANG DIJAGA:
  * Kasus `resolved` WAJIB punya dokumen turunan + alasan berlabel + penyelesai
    (INV-CASE-01) — tidak ada "sudah beres kok" tanpa surat.
  * Titipan dana (2-1950) menganggur > `case.holding_case_after_days` WAJIB punya kasus
    terbuka (INV-CASE-02) — uang tak dikenal tidak boleh terlupakan.
  * Playbook `moves_cash=True` WAJIB melahirkan jurnal seimbang (INV-CASE-03). Playbook
    `salah_invoice` dikecualikan DENGAN SENGAJA: realokasi antar pesanan memakai akun GL
    yang sama (1-1200) sehingga jurnal baru justru menyesatkan.
  * Kasus yang sudah melahirkan dokumen TIDAK bisa dibuka ulang (ledger tambah-saja) —
    tindak lanjutnya kasus BARU.
  * PK-25 — penyelesaian = PERIKSA (tanpa tulisan; `finance_case_actions.precheck`, periode SETIAP PT) → NIAT →
    EFEK → JURNAL (`post_durable`; kunci `finance_case` · `{id}:{suffix}:{n}`, kunci lama `{id}:{suffix}` dikenali
    untuk n = 0) → SELESAI. Kasus salah PT: jurnal kembar dua buku (`{id}:ic_ap:{n}` di PT penerima, `{id}:ic_ar:{n}`
    di PT pemilik) + dokumen `interco_loans` `kind="salah_transfer"`.
  * PK-25 — pemindai: kasus `bayar_dobel` untuk kwitansi yang sama tidak lahir lagi bila sudah ada kasus BERSTATUS APA
    PUN atau kwitansinya ber-`ar_receipts.dup_decision`; `dana_tak_dikenal` tetap hanya kasus terbuka.
Akun GL baru: 1-1150 Kas & Bank Transit (pindah-buku) · 1-1280 Piutang Titipan Karyawan.
Endpoints:   GET /api/finance-cases · GET .../playbooks · .../reasons · .../policy ·
             .../stats · GET .../{id} · POST /api/finance-cases ·
             POST .../{id}/assign · .../note · .../resolve · .../reject · .../reopen ·
             POST /api/finance-cases/scan
RBAC:        permission "finance_case": view · create · resolve · admin
             (sales: view+create — melapor & memantau, TIDAK menutup kasus uang)
⚠️ JANGAN BUAT: fin_cases, exception_cases, finance_exceptions, case_files — gunakan
   finance_cases.
```

### fin_fixed_assets + fin_depreciation_entries  [R6.2 IMPLEMENTED — Aset Tetap & Penyusutan]
Master aset tetap + histori penyusutan (straight-line) + disposal (gain/loss). Semua event
diposting ke GL & **idempotent** per sumber.
```
Collections: fin_fixed_assets (prefix fasset_, number FA-##### per entitas)
             fin_depreciation_entries (prefix depe_)
Router:      routers/fixed_assets.py   Service: services/fixed_asset_service.py
             services/fixed_asset_transfer_service.py (PK-23 — pindah antar-PT & pembayarannya)
Component:   features/finance/FixedAssetsView.jsx (Kas & Aset → Aset Tetap)
fin_fixed_assets fields:
  id, number, name, category (Peralatan & Mesin|Kendaraan|Inventaris & Perabot Kantor|Bangunan)
  acquisition_cost, acquisition_date, useful_life_months, salvage_value, method="straight_line"
  entity_id (FK business_entities), gl_account_asset (1-2100/2200/2300/2400),
  gl_account_dep_exp="6-6000", gl_account_acc_dep="1-2900",
  funding_source (PK-23: kas|hutang|saldo_awal|antar_pt — wajib untuk aset baru; aset lama tanpa field = kas;
                  antar_pt hanya diisi pindah aset), funding_account (DITURUNKAN dari funding_source, bukan isian
                  klien: kas → 1-1100/1-1110 menurut jenis rekening; hutang → pemetaan aset.sumber_hutang;
                  saldo_awal → pemetaan aset.sumber_saldo_awal; antar_pt → 2-1250),
  account_id + funding_cash_type + acquisition_cash_txn_id (sumber kas: rekening, jenis kasnya, kas keluar
                  ref_type="fixed_asset" · ref_id=id aset, dijurnal dokumen induk → not_required),
  monthly_depreciation, accumulated_depreciation, book_value, depreciated_months,
  last_depreciation_period, status (active|fully_depreciated|disposed|transferred
                  + PK-23 status antara transferring|disposing — klaim yang belum selesai),
  acquisition_je, disposal {date, proceeds, book_value, gain_loss, result, je_id, je_number},
  disposal_intent {prev_status, proceeds, date, note, by, at} + disposal_gl_status/_error/_failed_at
                  (PK-23, hanya selama `disposing`),
  transfer {intent {id, status pending|done, steps {target_created, journals, source_marked}, plan, lease_until},
            from/to_entity_id+name, transfer_date, book_value, price, gain, reason, new_asset_id/number,
            useful_life_left_months, settled, settle_status none|settling|settled (PK-23), settle_lease_until,
            settled_at, settled_by, cash_txn_ids}  — field `settled` tetap diisi,
  gl_status_transfer/_error_transfer/gl_journal_id_transfer (sisi pengirim jurnal kembar pindah),
  gl_status_settle_payer|payee (+_error, gl_journal_id_…) (jurnal kembar pembayaran),
  transfer_from {asset_id, number, entity_id, entity_name} (aset pengganti di PT penerima, id `{id lama}_tr`)
fin_depreciation_entries fields:
  id, asset_id, asset_number, entity_id, period (YYYY-MM), amount,
  accumulated_after, book_value_after, je_id, je_number, created_at,
  gl_status (PK-23: pending → posted|failed; register aset diperbarui HANYA sesudah posted; entri lama tanpa
  field = posted), gl_error, gl_failed_at, journal_entry_id, gl_label ("{nomor aset} · {periode}", baris panel)
Straight-line: monthly = (acquisition_cost − salvage_value) / useful_life_months; bulan terakhir umur
  (depreciated_months == useful_life_months − 1) = SELURUH sisa (PK-23 · FY-20). Idempotent per (asset_id, period).
Posting GL (via gl_service):
  Perolehan  : Dr <akun aset> / Cr <akun sumber dana>          (source_type fixed_asset_acquisition)
  Penyusutan : Dr 6-6000 Beban Penyusutan / Cr 1-2900 Akum.   (source_type fixed_asset_depreciation, sid=asset:period)
  Disposal   : Dr 1-2900 akum + Dr 1-1100 proceeds [+Dr 6-9500 rugi]
               / Cr <akun aset> perolehan [+Cr 4-9100 laba]   (source_type fixed_asset_disposal)
Akun COA baru: 1-2200 Kendaraan, 1-2300 Inventaris & Perabot, 1-2400 Bangunan,
  1-2900 Akumulasi Penyusutan (contra-asset, saldo kredit), 6-6000 Beban Penyusutan,
  4-9100 Laba Pelepasan Aset, 6-9500 Rugi Pelepasan Aset.
  Pindah PT  : pengirim Dr 1-2900 akum + Dr 1-1250 harga [+Dr 6-9500] / Cr <akun aset> [+Cr 4-9100]
               (fixed_asset_transfer · {id}:from); penerima = perolehan aset pengganti Dr <akun aset> / Cr 2-1250
               (fixed_asset_acquisition · {id}_tr) — dua sisi lewat twin_journal (PK-06)
  Bayar pindah: Dr 2-1250 / Cr kas (pembayar) & Dr kas / Cr 1-1250 (penerima uang)
               (fixed_asset_transfer_settlement · {id}:settle:a|b)
Endpoints: GET /api/fixed-assets · GET /api/fixed-assets/meta (+ funding_sources per PT) · GET /api/fixed-assets/summary ·
  POST /api/fixed-assets (funding_source wajib, account_id untuk kas) · GET/PATCH /api/fixed-assets/{id} ·
  POST /api/fixed-assets/run-depreciation (+ failed[], skipped_assets[]) · POST /api/fixed-assets/{id}/dispose ·
  POST /api/fixed-assets/{id}/transfer · POST /api/fixed-assets/{id}/transfer/settle (pelaku wajib berwenang di PT
  pembayar)
RBAC: permission "fixed_asset" (admin/manager).
Invarian integritas: FA-1 accumulated==Σentri · FA-2 book_value==cost−akum ·
  FA-3 GL 1-2900==Σakum aktif · FA-4 GL akun aset==Σperolehan aktif.
⚠️ JANGAN BUAT: fixed_assets, assets, aset, depreciation, penyusutan (koleksi) —
   gunakan fin_fixed_assets & fin_depreciation_entries.
```

### budgets + fin_budget_rules  [P1-4 / R6.3 IMPLEMENTED — Budget Control penuh]
Anggaran per entitas dengan **dua dimensi** (akun COA & kategori beban) + kebijakan
over-budget per entitas. Komitmen & realisasi **diturunkan (derived)** — tidak ada
materialized cache sehingga selalu konsisten dengan sumber (GL-safe).
```
Collections: budgets            (prefix budget_)
             fin_budget_rules   (prefix bgrule_, 1 dokumen per entity_id)
             budget_history     (prefix bgh_, PK-39 — satu baris per buat/ubah/hapus pagu)
Router:      routers/budgets.py    Service: services/budget_service.py
Component:   features/finance/BudgetView.jsx + BudgetParts.jsx + BudgetDialogs.jsx
             (Keuangan → Laporan & Analitik → Anggaran vs Realisasi)
budgets fields:
  id, entity_id (FK business_entities), year, month (0=tahunan | 1–12 bulanan),
  dimension ("account" | "category"), key (kode akun COA | kode expense_categories),
  label, account_code, account_name, account_type, amount, note, created_at, updated_at
  UNIK per (entity_id, year, month, dimension, key)  → invarian BG-1; PK-39: indeks wajib `uq_budget_key`
  (REQUIRED_UNIQUE_INDEXES, parsial key terisi) — simpan kembar / bersamaan → 409.
budget_history fields (PK-39):
  id, budget_id, entity_id, dimension, key, label, action ("created"|"updated"|"deleted"),
  before {amount, year, month, note}, after {…; kosong saat hapus}, reason, by, by_id, at · indeks (budget_id, at)
fin_budget_rules fields:
  id, entity_id, warn_threshold_pct (0–100, default 85),
  unbudgeted_action ("allow"|"warn"|"block"), enforce_po_create, enforce_po_approve,
  updated_by, updated_at
  `mode` ("off"|"warn"|"block") TIDAK DIBACA lagi sejak PK-39: mode = pengaturan `budget.mode`
  (mati · peringatan · blokir; global → PT). Nilai lama PT dipakai sebagai penimpa terdaftar
  (`config_overrides.mode_anggaran_lama`) sampai lapisan PT kunci baru diisi; tanpa penulisan data.
Sumber angka (derived; bulan = bulan buku WIB `book_date.periode_buku`; dihitung PER PT pemilik pagu):
  Realisasi dimension=account   → journal_entries (non-void, exclude closing): pendapatan kredit−debit,
                                   beban debit−kredit, ASET = Σ debit `goods_receipt` − Σ kredit
                                   `purchase_return` (HPP/opname/transfer diabaikan; jurnal yang dibalik tidak)
  Realisasi dimension=category  → jurnal `petty_cash_settlement` tahun itu → LPJ (`source_id`) `category_totals`
                                   pada bulan JURNAL (teks `periode` LPJ tidak dipakai)
  Komitmen  PO terbuka          → purchase_orders status ∉ (cancelled, rejected, closed_short, completed)
                                   (termasuk `partial`); key = PO.budget_dimension/budget_key atau akun
                                   pemetaan `persediaan.persediaan`; nilai = SISA PO `po_open_value`
                                   = net_subtotal × (1 − nilai diterima / nilai dipesan)
  Komitmen  LPJ petty cash      → cash_advance_settlements status draft|submitted|approved (per kategori, bulan created_at WIB)
Rumus: spent = actual + committed · remaining = budget − spent · variance = budget − actual
Mode gabungan: tiap baris `entity_id`/`entity_name`; `is_combined` + `combined_note` (belum dieliminasi).
Pemeriksaan (budget_service.enforce_budget; enforce_po_budget = pembungkus PO), hasil di dokumen `budget_check`
  {mode, mode_label, when, warnings[], checks[], blocked, skipped}:
  po_create/po_approve (router PO, PR→PO) · bill_approve (tagihan tanpa PO berakun beban: kampanye) ·
  cash_out (kas keluar manual, akun lawan `gl_service.cash_contra_account` berjenis beban) ·
  lpj_submit (tolak = peringatan) / lpj_approve.
  mode off → dilewati · warn → peringatan (transaksi jalan) · block → HTTP 400 (PO setujui 409).
PO menyimpan: budget_dimension, budget_key, budget_check {mode, when, warnings[], checks[], blocked}
Endpoints: GET/POST /api/finance/budgets · PATCH/DELETE /api/finance/budgets/{id} (+ reason) ·
  GET /api/finance/budgets/{id}/history · GET /api/finance/budget-vs-actual · GET /api/finance/budget-keys ·
  GET/PUT /api/finance/budget-rules (PUT dengan `mode` → 400) · POST /api/finance/budget-check
  (+ `source="cash_out"` + `category`: pratinjau form kas)
RBAC: permission "budget" (admin: view/create/update/delete/configure; manager: tanpa configure).
Invarian integritas: BG-1 tak ada duplikat kunci · BG-2 amount>0 & month 0–12 ·
  BG-3 key terdaftar (akun COA/kategori) · BG-4 kebijakan rules valid.
⚠️ JANGAN BUAT: fin_budgets, anggaran, budget_lines, fin_budget_commitments,
   fin_budget_actuals — gunakan `budgets` (+ derived) & `fin_budget_rules`.
```

### mfg_boms + mfg_work_orders  [R6.4 IMPLEMENTED — Produksi In-House (BOM & Work Order)]
Resep produksi MULTI-komponen + perintah kerja yang **mengonsumsi roll bahan (FEFO)** dan
**memproduksi roll barang jadi** (Roll-as-SSOT). HPP = Σ nilai bahan + overhead (opsional).
```
Collections: mfg_boms          (prefix bom_)
             mfg_work_orders   (prefix wo_, number WO-##### )
Router:      routers/production.py   Service: services/production_service.py
Component:   features/production/ProductionView.jsx + ProductionWO.jsx + ProductionParts.jsx
             (Gudang → Produksi (BOM & WO))
mfg_boms fields:
  id, entity_id (FK business_entities), name, output_product_id (FK products), output_sku,
  output_name, output_unit, overhead_per_unit (>=0, Rp per unit output),
  components[] {material_product_id (FK products), sku, name, unit, qty_per_unit (>0)},
  status ("active"|"inactive"), notes, created_by, created_at, updated_at
  Validasi: >=1 komponen · qty_per_unit>0 · bahan != output · tanpa komponen duplikat.
mfg_work_orders fields:
  id, wo_number, entity_id, bom_id (FK mfg_boms), bom_name, output_product_id, output_sku,
  output_name, output_unit, warehouse_id (FK warehouses), warehouse_name, planned_qty (>0),
  overhead_per_unit (snapshot dari BOM), material_plan[] {material_product_id, sku, name, unit,
  qty_per_unit, required_qty, available_qty, sufficient}, status ("draft"|"released"|
  "completed"|"cancelled"), notes, consumed[] {material_product_id, sku, name, unit, qty, value},
  produced_roll_ids[] (FK inventory_rolls), produced_qty, material_cost, overhead_cost,
  total_cost, unit_cost, je_id (FK journal_entries, hanya bila overhead>0),
  created_by/at, released_by/at, completed_by/at, cancelled_by/at, cancel_reason
Alur: draft → released → completed (cancel hanya dari draft/released; completed TIDAK bisa dibatalkan).
Complete (idempotent per WO):
  1. Pre-check ketersediaan SEMUA bahan (fail-fast 400 sebelum mutasi apa pun)
  2. Konsumsi roll bahan FEFO per (product, warehouse, owner_entity) → movement
     `production_consume` (qty negatif) + rebuild_balance
  3. Produksi 1 roll barang jadi via roll_service.create_inbound_roll
     (acquired.via="production_output", unit_cost = HPP/unit)
  4. GL: hanya OVERHEAD dikapitalisasi → Dr 1-1300 / Cr 5-1100 (source_type production_output)
HPP: material_cost = Σ(qty konsumsi × unit_cost roll) · overhead_cost = overhead_per_unit × qty
     total_cost = material + overhead · unit_cost = total_cost / planned_qty
GL-safe: bahan & barang jadi memakai akun Persediaan 1-1300 yang sama → porsi bahan NET-0
  (subledger roll sudah menyeimbangkan); akun baru 5-1100 Overhead Produksi Diserap.
Endpoints: GET/POST /api/production/boms · GET/PATCH/DELETE /api/production/boms/{id} ·
  GET/POST /api/production/work-orders · GET /api/production/work-orders/{id} ·
  POST /api/production/work-orders/{id}/release|complete|cancel · GET /api/production/summary
RBAC: permission "production" — admin/manager: view, manage_bom, create, release, complete, cancel;
  warehouse: view, create, release, complete (TANPA manage_bom & cancel); sales: tidak ada akses (403).
Invarian integritas: MFG-1 resep BOM valid · MFG-2 HPP WO konsisten (total=bahan+overhead,
  unit=total/qty, roll output ada) · MFG-3 konsumsi == movement & roll output senilai HPP ·
  MFG-4 overhead terkapitalisasi tepat di GL 5-1100 (je_id iff overhead>0).
Seed demo: `seed_production()` di seed_realistic.py (2 BOM + 3 WO: 1 selesai, 1 dirilis, 1 draft).
⚠️ JANGAN BUAT: boms, bill_of_materials, work_orders, production_orders, resep_produksi —
   gunakan `mfg_boms` & `mfg_work_orders`. (Resep MAKLOON/subkon tetap `process_recipes`.)
```

### sys_scheduler_runs + sys_wa_outbox  [R6.5 IMPLEMENTED — Penjadwal, Notifikasi & Kanal WhatsApp]
Scheduler **APScheduler** (AsyncIOScheduler, zona **Asia/Jakarta**) menjalankan **12 job** alert dari
**data nyata** → menulis ke koleksi `notifications` yang SUDAH ADA (Fase 0) dan — bila kanal
WhatsApp diaktifkan — mendorong pesan ke `sys_wa_outbox` lewat provider pluggable `services/wa/`.
Mode default provider = **`simulated`**: pesan TIDAK dikirim ke jaringan tetapi TETAP tercatat
lengkap (tujuan + isi) agar user bisa verifikasi sebelum mengisi kredensial nyata.
```
Collections: sys_scheduler_runs  (prefix srun_)   — histori eksekusi job
             sys_wa_outbox       (prefix waout_)  — antrean/arsip pesan WhatsApp
             system_settings (scope="alerts")     — jadwal job override + config WA + lock
Router:      routers/scheduler.py     Schemas: schemas_scheduler.py
Services:    services/scheduler_service.py (registry job + APScheduler + histori)
             services/alert_service.py     (7 generator alert dari data nyata)
             services/alert_ops_service.py (PS-21 — 3 generator operasional + notifikasi restock)
             services/wa_alert_service.py  (penerima, compose, dispatch, outbox, dedupe)
             services/digest_service.py    (R6.6 — ringkasan harian per penerima)
             services/escalation_service.py (R6.6 — eskalasi bertingkat)
             services/wa/{simulated,meta_cloud,fonnte}.py (provider pluggable)
Component:   features/admin/scheduler/SchedulerView.jsx + SchedulerParts.jsx + SchedulerWa.jsx
             + SchedulerPolicy.jsx (R6.6 — panel eskalasi & pratinjau ringkasan)
             (Pengaturan & Master Data → Penjadwal & Notifikasi) · bell: components/NotificationCenter.jsx

Registry job (12, di services/scheduler_service.py — JADWAL dapat diubah user tanpa deploy):
  ar_overdue         harian 08:00 WIB  piutang lewat jatuh tempo (ar_aging_service)
  ap_due             harian 08:05 WIB  tagihan supplier due<=7 hari / lewat (vendor_bills + payment_terms)
  depreciation_due   harian 08:10 WIB  penyusutan bulan lalu belum dijalankan (fin_fixed_assets)
  budget_alert       harian 08:15 WIB  anggaran over/mendekati batas (budget_service)
  production_stalled harian 08:20 WIB  WO dirilis >3 hari / draft >7 hari / bahan kurang
  ops_stalled        tiap 4 jam        tugas gudang terbuka >2 hari (wms_tasks)
  event_scan         tiap 4 jam        stok menipis · reservasi kedaluwarsa · approval SO/PO
  escalation_scan    tiap 2 jam        [R6.6] alert belum dibaca > batas jam → naik ke atasan
  daily_digest       harian 08:30 WIB  [R6.6] semua alert hari ini → 1 pesan ringkas/penerima
  po_arrival         tiap 2 jam        [PS-21] GR/inbound PO selesai <24 jam → MD + gudang + sales
                                        pemilik order pendingan (juga dipanggil SEKETIKA saat GR selesai)
  backorder_ready    tiap 2 jam        [PS-21] pendingan (backorder) yang stoknya sudah tersedia →
                                        sales pemegang akun + manager (juga dipanggil saat auto-fulfill)
  ar_due_soon        harian 07:55 WIB  [PS-21] piutang pada offset H-3/H-1/H/H+1 (melengkapi ar_overdue);
                                        sumber angka = ar_aging_service.orders_due_soon (SSOT AR)

sys_scheduler_runs fields:
  id (srun_), job_id, job_label, trigger ("schedule"|"manual"), actor, started_at, finished_at,
  status ("running"|"success"|"failed"), created (jml notifikasi baru), scanned, wa_queued,
  detail, error, duration_ms
sys_wa_outbox fields:
  id (waout_), dedupe_key ("<dedupe_key notif>|<nomor>" → maks 1 pesan/hari/tujuan;
    untuk ringkasan harian: "digest:<YYYY-MM-DD>|<nomor>"),
  to (E.164 tanpa '+', mis. 6281...), to_name, to_role, notification_id (FK notifications),
  notif_type (termasuk "daily_digest" & "escalation" sejak R6.6), severity,
  title, text (isi pesan LENGKAP untuk audit), provider,
  status ("simulated"|"sent"|"failed"), error, message_id, entity_id, created_at, sent_at, retried_at,
  digest_groups / digest_alerts (hanya baris ringkasan harian — jumlah kelompok & alert)
system_settings scope="alerts" fields:
  jobs{<job_id>: {enabled, hour, minute | interval_hours | interval_minutes}}, updated_at,
    (KP-T7: `interval_minutes` 1–1440 hanya untuk job bersatuan menit, `interval_hours` hanya untuk job bersatuan jam;
     sisa `interval_hours` pada job bersatuan menit dibuang `scripts/migrate_kpt7_jadwal.py --apply`)
  wa{enabled, provider, phone_number_id, template_name, template_lang, sender, pic_number,
     send_to_roles, min_severity, access_token*, fonnte_token*,
     delivery_mode ("instant"|"digest", R6.6), critical_bypass (bool, R6.6)},
  escalation{enabled, after_hours (1–72), min_severity, max_level (1–3)}   ← R6.6
  lock{owner, heartbeat, since}  ← guard single-instance scheduler (TTL 180s, heartbeat 60s;
    R6.6: lock dengan PID mati di node yang sama langsung diambil alih + retry tiap 30s)
  (*) kredensial: TIDAK PERNAH dikembalikan API — respons hanya `has_access_token`/`has_fonnte_token`.

notifications — field tambahan R6.6 (koleksi Fase 0, JANGAN ganti nama):
  escalation_level    0/absen = belum dieskalasi · 1 = sudah dinaikkan (anti-berulang)
  escalated_to        role tujuan eskalasi ("manager"|"admin")
  escalated_at        ISO waktu eskalasi
  escalation_notif_id FK notifications (anak eskalasi)
  escalation_depth    kedalaman rantai pada notifikasi ESKALASI (1..max_level)
  escalated_from      FK notifications (induk) pada notifikasi ESKALASI
  escalated_from_role role induk saat dieskalasi
  Rantai: sales/warehouse → manager · manager/all → admin · admin = berhenti.

Idempotensi & anti-spam:
  - `create_notification(dedupe_scope="day")` → dedupe_key `<type>:<ref>:<YYYY-MM-DD>`
    ⇒ job dijalankan berkali-kali dalam hari yang sama TIDAK menduplikasi notifikasi.
  - WA hanya untuk severity >= `min_severity` (default `warning`) + dedupe per (kunci, nomor).
  - **R6.6** `delivery_mode="digest"` → pesan per-alert DITEKAN, digabung job `daily_digest`
    (1 pesan/penerima/hari, dedupe `digest:<hari>|<nomor>`); alert `critical` tetap dikirim
    seketika bila `critical_bypass` aktif.
  - MAX_ALERTS_PER_JOB = 40 per run · MAX_PER_RUN eskalasi = 40 (pagar anti-flood).
Endpoints: GET /api/scheduler/jobs · /summary · /runs?job_id&limit · /settings ·
  /digest-preview?role= (R6.6) · PUT /api/scheduler/settings (jobs | wa | escalation) ·
  POST /api/scheduler/jobs/{job_id|all}/run ·
  GET /api/scheduler/wa-outbox?status&limit · POST /api/scheduler/wa-outbox/{id}/retry ·
  POST /api/scheduler/wa-test   (bell: GET /api/notifications · /unread-count · POST .../read · /read-all)
RBAC: permission "scheduler" — admin: view+run+configure · manager: view+run (TANPA configure) ·
  sales/warehouse: tidak ada akses (403). Nav: tab "Penjadwal & Notifikasi" (admin + manager).
Invarian integritas: SCH-1 histori run valid (status/durasi/urutan waktu, error iff gagal) ·
  SCH-2 notifikasi valid & dedupe_key konsisten · SCH-3 alert scheduler idempotent harian
  (tanpa dedupe_key ganda) · SCH-4 outbox ternormalisasi 62xx + tanpa kebocoran kredensial +
  pengaturan provider konsisten · **SCH-5** rantai eskalasi valid (1 eskalasi per induk,
  critical, depth 1..max_level, induk ditandai, tanpa yatim) · **SCH-6** ringkasan harian &
  konfigurasi kanal (maks 1 ringkasan/nomor/hari, isi bergrup, delivery_mode & kebijakan valid).
Invarian PS-21: **INV-PS21-01** dedupe harian job operasional (kunci unik & konsisten) ·
  **INV-PS21-02** ar_due_soon hanya pada offset H-3/H-1/H/H+1 · **INV-PS21-03** jejak dua arah
  restock SO↔PR · **INV-PS21-04** item PR restock menunjuk produk master yang sah.
Jenis notifikasi PS-21 (label FE di components/NotificationCenter.jsx TYPE_LABEL):
  `po_arrival` · `backorder_ready` · `ar_due_soon` · `restock_request`
Seed demo: `scripts/seed_escalation_demo.py` (R6.6) menggeser umur beberapa alert NYATA
  (default 20 jam, dedupe_key disesuaikan) lalu menjalankan job eskalasi agar rantai terlihat.
  `scripts/seed_ar_due_soon_demo.py` (PS-21) menggeser TANGGAL beberapa order berpiutang NYATA
  agar jatuh tempo mendarat tepat di H-3/H-1/H/H+1 (nominal & pelanggan tidak diubah).
⚠️ JANGAN BUAT: `sys_notifications`, `notification_queue`, `alerts`, `wa_messages`,
   `scheduler_jobs`, `job_logs` — pakai `notifications` (sudah ada) + `sys_scheduler_runs` +
   `sys_wa_outbox`. Jadwal job disimpan sebagai override di `system_settings` scope="alerts",
   BUKAN koleksi terpisah.
```

### gl_accounts  [EPIC7-C IMPLEMENTED — Chart of Accounts / Bagan Akun]
Koleksi kanonik `gl_accounts` (prefix `gla_`). Master bagan akun double-entry.
Normal balance: asset & expense = debit; liability, equity, income = credit.
```
Collection:  gl_accounts                  Prefix: gla_
Router:      routers/gl.py
Service:     services/gl_service.py
Component:   features/finance/ChartOfAccounts.jsx
Key Fields:
  id                string  prefix "gla_"
  code              string  UNIK, mis. "1-1100"
  name              string  nama akun
  type              enum    asset | liability | equity | income | expense
  normal_balance    enum    debit | credit (derived dari type)
  parent_code       string  FK gl_accounts.code (hierarki; "" = root)
  is_postable       bool    true = akun detail (boleh dijurnal); false = header
  is_active         bool
  system            bool    akun baku — tak boleh dihapus (boleh dinonaktifkan)
  currency          string  default IDR
  created_at / updated_at
ℹ️ Endpoint: GET/POST /api/gl/accounts, PATCH/DELETE /api/gl/accounts/{code},
  GET /api/gl/accounts/{code}/ledger. RBAC: permission "accounting" (admin/manager).
⚠️ JANGAN BUAT: accounts, coa, chart_of_accounts, akun (sebagai koleksi).
```

### journal_entries  [EPIC7-C IMPLEMENTED — General Ledger / Jurnal Umum]
Koleksi kanonik `journal_entries` (prefix `je_`). Jurnal double-entry SEIMBANG
(Σdebit == Σkredit). Auto-posting idempotent diturunkan dari SSOT
(`sales_orders` → pengakuan pendapatan; `cash_transactions` → mutasi kas) via
`POST /api/gl/sync` (source_type + source_id mencegah double-post).
```
Collection:  journal_entries              Prefix: je_
Router:      routers/gl.py
Service:     services/gl_service.py
Component:   features/finance/GeneralLedger.jsx
Key Fields:
  id                string  prefix "je_"
  number            string  JE-NNNNN (number series)
  date              string  tanggal buku WIB `YYYY-MM-DD` (10 huruf) — PK-37 (GL-05): semua jurnal baru lewat
                            `services/book_date.tanggal_buku` (stempel ber-zona → WIB; isian tanpa zona apa adanya).
                            Jurnal LAMA bisa masih berstempel ISO UTC; skrip `scripts/blueprint/pk37_tanggal_buku_lama.py`
                            (bawaan baca-saja; `--terapkan` = keputusan pemilik H3) mengubahnya dan menyimpan
  date_asli         string  (hanya jurnal yang diubah skrip PK-37) nilai `date` lama
  description       string
  source / source_type  enum  manual | sales_order | cash_transaction
  source_id         string  FK dokumen sumber ("" utk manual)
  source_label      string  label dokumen (mis. SO-0007, CASH-00001)
  lines             array   [{account_code, account_name, debit, credit, description}]
  total_debit       float   == total_credit (invarian)
  total_credit      float
  status            enum    posted | void (hanya manual yg boleh di-void)
  entity_id         string  FK entities.id
  created_by / created_at / updated_at
  ai_card_id        string  AG-T5 — id kartu tindakan asisten bila jurnal lahir dari permintaan kartu (jurnal manual,
                            jurnal pembalik, jurnal kas bayar hutang / kas manual); tidak ada = dari layar / sistem
  -- Penanda pembalik (PK-10; satu aturan untuk pembalik manual, pembatalan dokumen, batal kas/deposit) --
  reversed_by_entry_id      string  (di jurnal ASAL) id pembalik; "pending" selama klaim
  reversed_by_entry_number  string  nomor pembalik
  reversal_id               string  = reversed_by_entry_id (nama lama, tetap ditulis)
  reversed / reversed_at    bool / string
  ref.reverses_entry_id     string  (di jurnal PEMBALIK) id jurnal asal
  Tipe pembalik: source_type `reversal`, berakhiran `_reversal` atau `_void` → tidak bisa dibalik
  (`gl_service.is_reversal_type`). Jurnal sudah dibalik: `gl_service.reversal_of`.
  Invarian: INV-GL-REV-02 (`scripts/verify_data_integrity.py`) — satu jurnal ≤ 1 pembalik bukan void.
Laporan derived: Neraca Saldo (GET /api/gl/trial-balance) & Buku Besar per-akun
  (GET /api/gl/accounts/{code}/ledger). KPI: GET /api/gl/summary.
ℹ️ Endpoint: GET/POST /api/gl/journal, GET /api/gl/journal/{id},
  POST /api/gl/journal/{id}/void, POST /api/gl/sync. RBAC: permission "accounting".
⚠️ JANGAN BUAT: journals, general_ledger, gl, jurnal, ledger (sebagai koleksi).
```

### Penanda jurnal dokumen (`gl_status` dan kerabatnya) + registri Posting Gagal  [PK-18]

Status jurnal ditulis dari **hasil** posting oleh satu pintu tahan-gagal `gl_service.post_durable(...)` (kas:
`post_cash_durable`, pembungkus tipisnya). Jenis dokumen yang menjurnal, saringan "gagal", nomor, nominal, dan jalur ulang
terdaftar di **`backend/services/posting_registry.py::KINDS`** (dibaca `routers/posting_failures.py`; dijaga
`scripts/guardrails/verify_posting_coverage.py`, INV-POST-01). Tanpa migrasi: dokumen lama tanpa `gl_status` tidak berlencana
(mencari dokumen lama tanpa jurnal = PK-03).

| Field | Tipe | Arti |
|---|---|---|
| `gl_status` | `pending` · `posted` · `failed` · `not_required` | `pending` = efek bisnis sudah ditulis, jurnal belum dicoba (ditulis bersama perubahan status dokumen); `not_required` = fungsi posting sengaja tidak menjurnal (nominal nol, sudah dijurnal jalur lain) |
| `gl_error` | teks ≤ 300 | galat terakhir; dikosongkan saat `posted`/`not_required` |
| `gl_failed_at` | ISO | waktu gagal terakhir (urutan panel) |
| `journal_entry_id` | id `je_…` | jurnal yang terbit (utama) |

| Koleksi | Letak penanda | Tambahan |
|---|---|---|
| `credit_notes` | dokumen (dicerminkan ke `sales_returns` untuk nota kredit retur) | PK-27: **`cogs_source`** (`surat_jalan` · `rata_surat_jalan` · `wac`) — dari mana HPP balik (`cogs_amount`) diambil (`return_service.return_unit_cost`); nota dengan baris campuran memakai sumber paling kasar |
| `vendor_bills` | dokumen | — |
| `landed_cost_vouchers` | dokumen | **`allocated_total`** (angka, wajib saat `applied`): nominal voucher yang dialokasikan — ulang posting memakai angka ini; sejak PK-26 beserta pecahannya **`capitalization`** (lihat bagian koleksi) |
| `makloon_orders` | tiap unsur **`steps[]`** (`steps.$.gl_status`, `…gl_error`, `…gl_failed_at`, `…journal_entry_id`) | `steps[].material_returns[].gl_part` = akhiran `source_id` jurnal pembalik retur bahan |
| `inventory_movements` | baris `movement_type: cut_waste` | `gl_amount` (susut × biaya roll), `gl_source_id` (`cutw:<op>`), `gl_reason`, `gl_label` |
| `ar_receipts` | **`void_gl_status`**, `void_gl_error`, `void_gl_failed_at`, `void_journal_entry_id` | status jurnal PEMBALIK saat kwitansi dibatalkan (`gl_status` tetap milik jurnal penerimaan) |
| `fin_fixed_assets` | dokumen | `acquisition_je` (nomor jurnal perolehan) diisi saat `posted`; PK-23: `disposal_gl_status` (jenis `fixed_asset_disposal`, hanya pelepasan macet), `gl_status_transfer` (jenis `fixed_asset_transfer`), `gl_status_settle_payer`/`_payee` (jenis `fixed_asset_settle_payer`/`_payee`); aset pengganti pindah antar-PT memakai `gl_status` (jenis `fixed_asset`, ulang = teruskan niat pindah) |
| `fin_depreciation_entries` | entri per (aset, periode) — PK-23 | jenis `asset_depreciation` ("Penyusutan Aset"); tautan panel → aset (`link_id_field: asset_id`) |
| `shipments` | dokumen (sudah ada) | `posted` hanya bila jurnal `shipment_revenue` surat jalan itu ada (GL-12); `journal_entry_id` baru |
| `cash_transactions` | dokumen (sudah ada) | `gl_failed_at` baru |
| `purchase_orders` | tiap unsur **`grir_clearings[]`** (`grir_clearings.$.gl_status`, …) — PK-28 | jenis registri `grir_clearing` ("Kliring GR/IR"), baris panel `<po_id>:<seq>` |
| `payment_variance_decisions` | dokumen (`gl_status` = jurnal keputusan; **`reversal_gl_status`** = jurnal pembaliknya) — PK-19 | jenis registri `payment_variance` ("Keputusan Selisih Bayar"); ulang hanya untuk keputusan `done`/`reversed` |
| `cash_holdings` | dokumen — PM-T4 | jenis registri `cash_holding` ("Titipan Tunai Sales"); status dicerminkan ke kwitansinya |
| `cash_deposits` | dokumen — PM-T4 | jenis registri `cash_deposit` ("Setoran Titipan Tunai"); ulang = jurnal kas setoran yang sama |

### Sisa GR/IR per PO, selisih harga faktur, dan kliring  [PK-28 · IV-03]

Sumber angka sisa GR/IR = **buku besar** akun `pembelian.gr_ir` (semua kode yang pernah dipakai kebutuhan itu), dikelompokkan
per PO oleh `services/vendor_bill_service.grir_by_po(entity_id, po_id="")` (satu agregasi, tanpa batas `to_list`). Tidak ada
angka GR/IR yang disimpan di PO (D1). Daftar: `GET /api/finance/gr-ir` (`vendor_bill.view`, satu PT); kliring:
`POST /api/finance/gr-ir/{po_id}/clear` (`accounting.manage`, `services/grir_service.py`). Tanpa migrasi.

| Koleksi · field | Tipe | Arti |
|---|---|---|
| `vendor_bills.grir_amount` | angka | Σ `billed_qty` × harga neto baris PO (`services/po_pricing.po_line_net_unit_price`); ditulis sekali pada tulisan `posted` (faktur ber-PO; bukan kampanye/jasa makloon) |
| `vendor_bills.price_variance_amount` | angka | neto faktur (grand − PPN) − `grir_amount`; positif = faktur lebih mahal dari PO |
| `vendor_bills.price_variance_posted` | boolean | `true` = selisih sudah masuk akun `pembelian.selisih_harga` (atau selisih nol); `false` = akun belum dipetakan saat faktur dijurnal → selisih masih di GR/IR (tampil di daftar GR/IR) |
| `purchase_returns.ap_basis` | `gr_ir` · `hutang` · `kas` | akun yang didebit jurnal retur; ditentukan sekali dan ditulis bersama `gl_status: pending` (ulang memakai dasar tersimpan). `gr_ir` = retur sebelum ada faktur terposting: Dr GR/IR **tanpa PPN**, PPN masukan tidak dibalik; qty-nya mengurangi boleh-tagih (`returned_unbilled_map`). Retur lama tanpa field: `gr_ir` bila jurnalnya mendebit akun GR/IR |
| `purchase_orders.grir_clearings[]` | larik `{id, seq, amount, direction: debit_grir\|kredit_grir, reason, by, by_id, at, gl_status, gl_error, gl_failed_at, journal_entry_id}` | tiap kliring sisa GR/IR; lahir `pending` (bersyarat: tidak ada unsur `pending`/`failed`, larik tidak berubah sejak saldo dibaca), jurnal `grir_clearing` (`source_id = <po_id>:<seq>`) lewat `posting_registry.durable_grir_clearing` |
| `journal_entries.ref.po_id` | teks | diisi pada jurnal **baru** ber-sumber `goods_receipt`, `vendor_bill` (ber-PO), `purchase_return` (ber-PO), `grir_clearing`. Jurnal lama dihubungkan lewat `wms_tasks.po_id` / `vendor_bills.po_id` / `purchase_returns.po_id` (sumber `…_reversal` mengikuti asalnya); sisanya = "tidak terhubung ke PO" |
| `purchase_orders.close_settlement.grir_balance` | angka | sisa GR/IR saat tutup-kurang; tindak lanjut `grir_clearing` (Finance) bila sisa ≠ 0 dan tidak ada lagi nilai terima yang belum ditagih. Tidak ada jurnal otomatis |

Kunci pemetaan akun baru `pembelian.selisih_harga` (`gl_mapping_registry`, bawaan **kosong** — akun dipilih pemilik, titik
henti H4; jenis beban/pendapatan; wajib).

### Peta jenis dokumen Jejak Dokumen (`services/doc_refs_service.py::DOC_TYPES`)  [PK-44]
Bukan koleksi: SATU peta jenis dokumen → koleksi · field nomor · label · tujuan layar (`view` · `tab` · `focus_type` ·
`focus_from`) · izin modul sumber (`perm`, dipakai penyaring nominal PK-17 `SOURCE_PERMISSION`). Tujuan tautan dibentuk
`doc_refs_service.link_of(doc_type, doc)` — satu-satunya pembentuk tautan (Jejak Dokumen, panel Dokumen Terkait,
linimasa proses `document_relations_service`); `nav_id` tidak dikirim server.
```
43 jenis (PK-44: 39 + 4). Jenis baru — koleksi yang SUDAH ada, tanpa field baru selain `refs[]` G-4:
  payroll_run      hr_payroll_runs · number           "Penggajian"                      perm hr.view            → hr-payroll-runs
  cash_advance     cash_advances · number             "Pengajuan Dana (PD)"             perm cash_advance.view  → cash-advances
  cash_settlement  cash_advance_settlements · number  "Pertanggungjawaban Dana (LPJ)"   perm cash_settlement.view → settlements
                   WAJIB berinduk PD (`source_fk` cash_advance_id): relasi `parent` ditulis saat LPJ lahir
                   (`cash_advance_service.create_settlement`) + `backfill()`; LPJ lama: `scripts/apply_pk44_lpj_refs.py`
                   (bawaan laporan baca-saja; `--apply` = keputusan pemilik H3)
  fixed_asset      fin_fixed_assets · number          "Aset Tetap"                      perm fixed_asset.view   → fixed-assets
Jurnal → dokumen (`JOURNAL_SOURCE_TYPE`, source_id berawalan id dokumen): petty_cash_settlement → cash_settlement ·
  fixed_asset_acquisition/_depreciation/_disposal → fixed_asset · makloon_claim, makloon_material_loss,
  subcon_service_unabsorbed, subcon_issue_reversal → makloon_order · penalty_reversal/_payment → penalty ·
  payment_variance_writeoff/_alloc/_reversal, ap_variance_writeoff → payment_variance · cash_transaction_void →
  cash_transaction · vendor_bill_reversal → vendor_bill. Gaji (payroll_run, payroll_pay): PK-22 — source_id = id
  proses (`prun_…`); jurnal lama "{entity_id}:{period}" → run dicari lewat journal_id/paid_journal_id lalu (entity_id,
  period) non-void (`gl_service.payroll_source_id`).
Label (satu dokumen satu nama): Tagihan Pemasok · Kontrak Pemasok · Permintaan Pembelian (PR) · Pesanan Pembelian (PO)
  · Pesanan Penjualan (SO) · Biaya Masuk (Landed Cost) · Kwitansi Pelanggan · Pelunasan Antar-PT · Jurnal.
⚠️ JANGAN BUAT peta tujuan kedua (dulu `document_relations_service._link` menulis `view` sendiri).
```







### customers
```
Collection:  customers
Router:      routers/customers.py
Schema:      schemas.py → CustomerCreate, CustomerAddress
Component:   CustomerPanel.jsx, AdminView.jsx (tab Customer)
Key Fields:
  id          string   prefix "cust_"
  code        string   format: "CUST-NNNN"
  name        string
  pic_name    string   nama contact person
  phone       string
  email       string
  type        enum     Retailer | Wholesaler | Boutique
  city        string
  status      enum     active | inactive
  addresses   list     [{id, label, recipient_name, phone, city, address, is_primary}]
  npwp, credit_limit, sales_pic, entity_id   (sudah ada)
  credit_limit       USANG (CR-T1) — tidak ditulis lagi (POST selalu 0) dan tidak dibaca mesin; plafon = profil kredit
                     `customer_credit_profiles` (dibaca sebagai cadangan `data_lama` HANYA sampai skrip
                     `scripts/migrate_credit_profiles.py --terapkan` dijalankan pemilik — H3; cadangan dihapus CR-T3)
  --- CRM-LITE [PROPOSED KN_17] ---
  assigned_sales_id  string  FK users (salesperson pemilik) — WAJIB (kunci manajemen; sales kelola miliknya)
  segment            enum    Retail|Wholesale|Distributor|VIP  (KLASIFIKASI saja, BUKAN penentu harga)
  tags               list    [string]
  contacts           list    [{name, role, phone, email, is_primary}]
  lot_policy         enum    prefer_single|strict_single|allow_mixed (default prefer_single; KN_15)
  enforce_single_dye_lot  bool  P0-4 — bila true → alokasi SO dipaksa 1 dye_lot (dye_lot_strict)
  payment_profile    object  {allowed_methods:[kontan|tunai|tempo|dp|bertahap], default_method,
                              term_days, dp_percent, installment:{count,interval_days}}
  credit             object  {credit_limit (= profil kredit EFEKTIF, CR-T1), limit_source, ar_outstanding(derived),
                              overdue_amount(derived), status: active|warning|blocked (`credit_profile_service.status_from`)}
  customer_group_id  string? penghubung customer sama lintas-entitas (DISIAPKAN, default kosong) [KN_17 S38]
  status      enum     active | inactive | blocked (USANG sejak CR-T1: blokir kredit = profil kredit `blokir_manual`;
                       PATCH menerima active/inactive saja; migrasi mengubah `blocked` → `active`) | merged
  created_by  string
  created_at  string

⚠️ scoped entity_id (customer terpisah per entitas; customer sama boleh lintas-entitas; kunci=assigned_sales_id)
⚠️ RBAC row-level: role=sales hanya lihat/kelola customer assigned_sales_id==dirinya (enforce backend)
⚠️ PK-45 (K-28) → CR-T1: plafon & blokir kredit HANYA lewat pengajuan profil kredit (`credit_profile_requests`, diputus
   pemegang `credit_profile.approve`). `PUT /api/customers/{id}/credit` (jalur sementara PK-45) dijawab 410;
   `customer.manage_credit` dicabut. POST menyimpan `credit_limit` 0; isian > 0 → pengajuan `diajukan` atas nama pembuat.
⚠️ JANGAN BUAT: clients, buyers, pembeli, pelanggan_toko, crm_customers
```

### warehouses
```
Collection:  warehouses
Router:      routers/warehouses.py
Schema:      schemas.py → WarehousePayload
Component:   AdminView.jsx (tab Warehouse)
Key Fields:
  id          string   prefix "wh_" (contoh: wh_jakarta, wh_bandung)
  code        string   format: "WH-XXX"
  name        string
  city        string
  lat, lng    float    koordinat GPS
  active      bool
  zones       list     [{id, name, racks: [{id, name, bins: [{id, code, capacity}]}]}]
  created_at  string
  is_test     bool     FIX-1 (K-B1-10) — penanda data uji (skrip fix_data_2026_11_09_tandai_data_uji.py, bisa
                       dibalik); gudang bertanda tidak ditawarkan di pemilih bawaan & tampilan "semua lokasi".
                       Field yang sama dipakai `warehouse_sites` & `business_entities`.

⚠️ Hierarchy: Zone → Rack → Bin
⚠️ FIX-1 — `zones` lewat PATCH dialihkan ke jalur struktur berpenjaga (save_warehouse_structure); kunci
   struktur/profil (zones, sharing_mode, entity_ids, site_id, roles, storage_rules, gate_config, stock_mode,
   storage_form, active, loading_check_policy) hanya admin & Admin Gudang.
⚠️ Lokasi kerja akun: users.location_site_ids / location_warehouse_ids — pagar keras peran `warehouse`
   (setelan wms.location_scope_enforced) + saringan TAMPILAN bawaan semua peran (header X-Location-Scope).
⚠️ JANGAN BUAT: gudang, depot, storage_location sebagai collection terpisah
⚠️ Zone/Rack/Bin adalah EMBEDDED dalam warehouse document
```

### uoms
```
Collection:  uoms
Router:      routers/uoms.py
Schema:      schemas.py → UOMPayload
Component:   AdminView.jsx (tab UOM)
Default UOMs:
  uom_meter  → MTR (length, precision 2)
  uom_yard   → YRD (length, precision 2)
  uom_roll   → RLL (volume, precision 0)
  uom_pcs    → PCS (count, precision 0)
Key Fields:
  id, code, name, base_type (length|volume|weight|count), precision, status

⚠️ JANGAN BUAT: satuan, unit_ukur, measurement
```

### sales_orders
```
Collection:  sales_orders
Router:      routers/sales_orders.py
Schema:      schemas.py → SalesOrderCreate, SalesOrderItemIn
Component:   SalesPortal.jsx, OrdersView.jsx, CartPanel.jsx
Status Lifecycle:
  reserved → waiting_approval → approved → confirmed → dispatched → done
  (cancelled tersedia di setiap stage)
Key Fields:
  id          string   prefix "so_"
  number       string  format: "SO-NNNNN"  (FIELD = "number", BUKAN "order_number")
  customer_id  string  FK → customers.id
  customer_name string SNAPSHOT (denormalized)
  items        list    [{product_id, product_name, sku, quantity, unit, price, subtotal,
                          discount_percent, discount_amount, line_total}]
                        (FIELD item = "quantity" & "price"; BUKAN "qty"/"unit_price")
                        subtotal = price×quantity (GROSS, invarian); line_total = subtotal−discount_amount
                        items[].commission_rule  KA-4 — potret aturan komisi baris (v1) saat pesanan dibuat:
                          {v, sumber (pesanan|isi_awal), dipotret_pada, artikel{id,nama,kode}|null,
                           tarif{id, asal_tingkat (varian|artikel|kategori), asal_lingkup (pt|semua_pt), per_unit_amount,
                           margin_cap_pct, discount_*}|null, price_basis, acuan, price_bands, price_source_rules}
                          Pesanan lama diisi sekali oleh `bootstrap.backfill_so_line_commission_rule` (sumber "isi_awal").
  allocations  list    [{warehouse_id, warehouse_name, warehouse_city, product_id, quantity}]
                        SNAPSHOT fulfillment (top-level, dipakai render dokumen)
  status       enum    (lihat lifecycle di atas)
  credit_hold  bool    CR-T3 — penanda TUNGGAL "Tahan kredit" (gerbang kredit; sub-status `tahan_kredit`): ditolak
                       `confirm_core` & `dispatch_guard` walau titik periksanya mati
  credit_hold_info     {since, checkpoint, reasons[{code, result, message}], exposure, by} — tahanan berjalan (null = tidak)
  credit_hold_history  [{…info, released_at, released_by, release_reason, release_result, override_id}] satu baris/tahanan
  pay_before_ship bool CR-T3 (K-27) — lahir untuk pelanggan yang sedang ditahan dengan termin bayar penuh dulu →
                       gerbang bayar kirim memakai 100 %
  pay_hold     {since, due_at, required, basis} | absen — Lapor Bayar LB-T2: pesanan `approved` wajib bayar dulu
                       (hitungan `dispatch_payment_gate.evaluate`; bukan sample / SO Pesanan Khusus) ditahan SEBELUM
                       gudang (sub-status `menunggu_bayar`);
                       ditulis `pay_hold_service.start` (idempoten), dicabut `clear_if_paid` / `confirm_core` / OD;
                       `release.waiting = "bayar"` = "Periksa & lepas" sudah ditekan, dilepas otomatis sesudah dibuka
  credit_gate_at_order potret hasil gerbang kredit saat pesanan dibuat (D3) · credit_override_id · credit_override_used
                       {id, amount, reason_label, decided_by}
  total_amount float    = Σ items.subtotal (GROSS — invarian verify_data_integrity L4)
  # Fase 1B — breakdown diskon + PPN (field TERPISAH agar total_amount tetap GROSS):
  items_discount_total   float
  order_discount_percent float   order_discount_amount float   discount_total float
  net_subtotal float   = total_amount − discount_total (= DPP base)
  dpp float   ppn_rate float   ppn_mode enum(excluded|included)   is_pkp bool
  ppn_amount float   grand_total float  (= yang dibayar customer)
  payment_term_code string   payment_term_name string   payment_status enum(pending|paid_partial|paid)
  # PK-32 (K-14) — tagihan tambahan dari nota debit amandemen; `grand_total` dan `items[]` TIDAK diubah nota
  extra_billing_lines list [{id "xbl_", debit_note_id, debit_note_number, description, net, ppn, gross,
                          due_date (tanggal nota + hari termin pesanan), created_at}] — ditulis HANYA
                          `credit_note_service.settle` ($push bersyarat id nota belum ada)
  # NILAI TAGIHAN = grand_total + Σ extra_billing_lines.gross (`customer_service._order_grand_total`);
  # nilai efektif pendapatan = nilai tagihan − Σ nota kredit amandemen (`gl_service.order_effective_totals`)
  credit_note_lock / credit_note_lock_until  PK-32 — kunci penerbitan nota kredit (batas total, ±30 dtk)
  # PM-T2 — cara bayar & rekening tujuan (master PM-T1), kode bayar:
  payment_method_code string  kode kanonik daftar induk cara bayar | "" (belum ditentukan; pesanan lama & bawaan)
  receiving_account_id string FK → bank_accounts.id (PT pesanan, penerimaan pelanggan, melayani cara bayar) | ""
  receiving_account  {bank_name, account_number, holder_name}  POTRET saat dipilih (D3) — dokumen lama tetap
                     menyebut rekening yang berlaku saat itu; {} bila tanpa rekening
  payment_code string  kode bayar tingkat pesanan (hanya pesanan bayar-dulu, diisi saat dikonfirmasi) | ""
  tax_override string  "" (ikut PKP PT) | "non_ppn" — PK-45 (K-33): "non_ppn" butuh izin `order.tax_override`
  tax_override_reason string  PK-45 — alasan pesanan tanpa PPN (≥ 10 huruf); terisi HANYA bila tax_override == "non_ppn"
  # Fase 1B — approval dinamis (dari approval_rules):
  approval_required bool   required_approval_role string|null   approval_amount float
  sales_name   string
  # PS-21 — permintaan repeat/restock dari layar order (jejak ke PR; TANPA koleksi baru)
  restock_requests list  [{pr_id, pr_number, status, items[{product_id, product_name,
                          quantity, unit}], total_est_amount, requested_by, requested_by_id,
                          requested_at, reason}]
  last_restock_note string  ringkasan permintaan terakhir (untuk tampilan cepat)
  ar_demo_offset int?   HANYA data demo — ditulis scripts/seed_ar_due_soon_demo.py
  shipping_address_id string
  reservation_expires_at string  UTC ISO
  created_at, updated_at string

⚠️ JANGAN BUAT: orders, customer_orders, so_list, penjualan
⚠️ Stock reservation terjadi di inventory_balances SAAT order dibuat
⚠️ Dispatch flow: sales_orders.confirm → wms.outbound_from_order → outbound_picking.dispatch
⚠️ Fase 1B: pricing dihitung services/config_service.compute_order_pricing (PPN ikut PKP entitas);
   approval via evaluate_approval + role_satisfies. INVARIAN: total_amount & item.subtotal tetap GROSS.
```

### inventory_lots  [FASE C IMPLEMENTED — Lot KELAS SATU + Genealogi + Recall (D-10/D-26/D-27)]
```
Collection:  inventory_lots           Prefix: lot_
Router:      routers/lots.py                  Schema: schemas_lots.py
Services:    services/lot_service.py        (SSOT: nomor, agregat, split/merge/rework, kebijakan)
             services/lot_trace_service.py  (silsilah · recall · label/QR)
             services/lot_migration.py      (backfill IDEMPOTEN — dipakai bootstrap, seed, CLI)
Migrasi:     backend/scripts/migrate_fase_c_lots.py  (--dry-run)
Component:   features/inventory/lots/LotsView.jsx + LotParts.jsx + LotDetailPanel.jsx
             + LotGenealogyTree.jsx + LotRecallPanel.jsx + LotActionModals.jsx + lotApi.js
Nav:         Gudang → Stok & ATP → tab "Lot & Silsilah" (view: admin/manager/warehouse/sales;
             mutasi: inventory:update; kebijakan: admin/manager)
Key Fields:
  id                string  prefix "lot_"
  lot_number        string  UNIK — "KSC/LOT-YYMM-####" (per entitas · D-26; deletion-safe)
  entity_id         string  entitas penomoran (dipakai sequence number_sequences)
  owner_entity_id   string  PEMILIK lot (selaras inventory_rolls · KN_15) → SCOPED
  product_id, sku, product_name, unit, warehouse_id   (snapshot ringan utk tampilan/label)
  stage, fabric_type  enum  snapshot domain Fase A (roll_domain_snapshot)
  source            enum    receiving|makloon|production|split|merge|rework|return|transfer|
                            adjustment|migration|manual      (registry enum `lot_source`)
  source_ref        object  {type,id,number} → wms_task|purchase_order|makloon_order|
                            work_order|lot|sales_return|legacy_roll|manual
  supplier_lot      string  nomor lot versi supplier (titik input GR & inspeksi QC)
  dye_lot           string  batch warna; shade_ref string (referensi shade/Pantone)
  supplier_id, supplier_name
  process           object  {process_type, partner_id, partner_name}  (rework/makloon)
  parent_lot_ids    array   genealogi HULU (dua arah, WAJIB bebas siklus)
  child_lot_ids     array   genealogi HILIR
  lot_status        enum    karantina|released|in_process|hold_shade|rework  (registry `lot_status`)
  status_history    array   {status, status_before, reason, actor, at}
  roll_count, active_roll_count, qty_initial, qty_remaining, qty_available, status_breakdown
                            ← PROYEKSI: selalu recompute dari inventory_rolls (TIDAK pernah $inc)
  legacy_lot_codes  array   jejak string lot lama (mis. "LOT-001", "LOT-MIGRATED")
  merged_into       string? diisi bila lot digabung ke lot lain (jejak audit)
  note, created_at, updated_at, created_by, created_by_name
Index:  lot_number · (owner_entity_id, created_at) · (product_id, owner_entity_id) ·
        (source_ref.id, product_id) · legacy_lot_codes · dye_lot · supplier_lot ·
        lot_status · parent_lot_ids · child_lot_ids
Invarian: INV-LOT-01..06 (scripts/verify_data_integrity.py → L4-LOT)
Field baru pada koleksi lain: inventory_rolls.lot_id + .supplier_lot ·
        inventory_movements.lot_id · wms_tasks.lot_ids/lot_numbers/supplier_lot/lot_warnings ·
        mfg_work_orders.output_lot_id/input_lot_ids · makloon_orders.steps[].lots[].lot_id
LARANGAN NAMA: jangan buat `lots`, `dye_lots`, `batches`, `stock_lots` — pakai `inventory_lots`.
```
```
Collection:  uom_conversion_rules   Prefix: uomr_
Router:      routers/uom_conversions.py      Schema: schemas_uom.py
Services:    services/uom_rules_service.py (registry + toleransi + JEJAK konversi)
             services/uom_service.py        (MATEMATIKA konversi — SATU tempat, R3)
Component:   features/admin/uom/UomConversionView.jsx + UomConversionParts.jsx
             components/UomInputConvert.jsx · components/UomConvertHint.jsx
             hooks/useUomConversions.js   (SSOT FE — komponen dilarang hardcode satuan, R7)
Nav:         Produk & Harga → Konversi Satuan (admin & manager; ubah butuh izin uom:update)
Key Fields:
  id            string  prefix "uomr_"
  from_unit     string  kode satuan asal (ternormalisasi: "yd" → "yard", "pcs" → "piece")
  to_unit       string  kode satuan tujuan
  kind          enum    fixed (faktor fisika/standar) | pack (ukuran kemasan roll/bal/cone/box)
                        | formula (lintas dimensi, butuh spesifikasi produk)
  factor        float   > 0 untuk fixed/pack (1 from_unit = factor × to_unit); 0 untuk formula
  formula       enum?   gsm_width  (kg = meter × GSM × lebar ÷ 1000 — KN_18 §3.1)
  dimension     enum    length | weight | count | area | cross
  label, note   string  label ringkas + catatan user
  status        enum    active | inactive   (SATU aturan aktif per pasangan from→to)
  source        enum    standard (di-seed migrasi/bootstrap) | user
  created_by, created_at, updated_by, updated_at
Endpoints:   GET  /api/uom-conversions/catalog   (katalog satuan + jenis + formula + setting)
             GET  /api/uom-conversions/rules?status&dimension&kind
             POST /api/uom-conversions/rules · PATCH /api/uom-conversions/rules/{id}
             POST /api/uom-conversions/rules/{id}/status?status=active|inactive
             GET/PUT /api/uom-conversions/settings      (toleransi — configurable)
             POST /api/uom-conversions/convert          (hasil + JEJAK; dipakai FE & dokumen)
             POST /api/uom-conversions/check-variance   (level ok|warn|block)
             GET  /api/uom-conversions/usage?limit      (jejak konversi dokumen — audit D-07)
Urutan resolusi faktor (dikunci server):
  satuan sama → uoms.factor_to_base → products.uom_conversions[] → aturan GLOBAL aktif
  → formula GSM × lebar → 1-hop lewat satuan dasar → HTTP 400 (tidak pernah diam-diam 1:1)
system_settings scope="uom" (kebijakan toleransi, dapat diubah user tanpa deploy):
  warn_pct (default 2) · block_pct (default 5) · allow_override (bool) ·
  precision (0–6) · require_trail (bool) · updated_at · updated_by
JEJAK konversi (D-07) disimpan sebagai objek `uom_trail` pada:
  purchase_orders.items[] · purchase_requisitions.items[] · wms_tasks (GR)
  {doc_uom, doc_qty, base_uom, base_qty, factor, source, rule_id, formula, path[],
   context, converted_at, source_migrated?}
  source ∈ same_unit | fixed_uom | product_override | global_rule | formula_gsm_width | hop_base
wms_tasks (GR) tambahan Fase B:
  conversion_variance {level(ok|warn|block), variance_pct, expected_kg, actual_kg, factor,
                       message, override_reason?, overridden?} · needs_review bool
Invarian: INV-UOM-01 aturan sah & satu aktif per pasangan · INV-UOM-02 jejak konsisten
  (doc_qty × factor == base_qty == quantity_base) · INV-UOM-03 toleransi sah
  (0 < warn ≤ block ≤ 100, precision 0–6) · INV-UOM-04 selisih di luar toleransi ditandai
  needs_review & yang di atas blokir wajib beralasan.
Migrasi:  backend/scripts/migrate_fase_b_uom.py (idempoten; --dry-run tersedia)
⚠️ JANGAN BUAT: `uom_conversions` (koleksi), `unit_conversions`, `konversi_satuan`,
   tabel konversi per kontrak/mitra — keputusan pemilik: registry GLOBAL + override
   master produk. Faktor per produk TETAP di `products.uom_conversions[]`.
⚠️ JANGAN menghitung faktor di frontend — pakai POST /api/uom-conversions/convert.
```

### invoices
```
Collection:  invoices
Router:      routers/invoices.py
Schema:      schemas.py → PaymentSimulationCreate
Key Fields:
  id, number ("INV-NNNNN-NN"), order_id, order_number, customer_id, customer_name, entity_id,
  amount (= grand_total order), status (paid), method, created_by, created_at
  # Fase 1B — snapshot pajak untuk Faktur/Invoice:
  total_amount, discount_total, net_subtotal, dpp, ppn_rate, ppn_mode, ppn_amount, grand_total,
  payment_term_code, payment_term_name

⚠️ SIMULATED payment — belum real gateway
⚠️ amount default = order.grand_total (server-authoritative); jangan embed _id sub-dok (RC ObjectId)
⚠️ JANGAN BUAT: bills, tagihan, faktur sebagai collection terpisah
```

### inventory_balances
```
Collection:  inventory_balances
Router:      routers/inventory.py
Component:   InventoryStockView.jsx
Key Fields:
  id           string   prefix "bal_"
  product_id   string   FK → products.id
  warehouse_id string   FK → warehouses.id
  owner_entity_id string FK → business_entities.id   [IMPLEMENTED Fase 0.5 — kepemilikan, 3-key]
  on_hand_qty  float    total fisik (= Σ bucket fisik)
  available_qty / reserved_qty / committed_qty / picked_qty / packed_qty / quarantine_qty / blocked_qty / damaged_qty  float (bucket fisik)
  on_order_qty / in_transit_inbound_qty / in_transit_transfer_qty / in_transit_intercompany_qty / in_transit_sales_qty  float (pipeline/transit)
  owned_qty / incoming_qty / atp_qty  float (derived)
  in_transit_qty float  legacy alias (= Σ transit)
  updated_at   string

⚠️ UNIQUE per (product_id + warehouse_id + owner_entity_id)  [IMPLEMENTED Fase 0.5]
   Balance = PROYEKSI/cache yang diturunkan dari inventory_rolls (SSOT fisik) via roll_service.rebuild_balance().
   [KN_15 §3.4] Bucket DETAIL: fisik (available/reserved/committed/picked/packed/quarantine/blocked/damaged→on_hand)
   + transit (on_order/in_transit_*) + derived (owned/incoming/atp). Status: IMPLEMENTED Fase 0.5.
⚠️ JANGAN pindahkan stok dengan update langsung — selalu buat inventory_movements + rebuild_balance
⚠️ JANGAN BUAT: stock, stok, stock_levels, inventory_count, stock_units, rolls (lepas)
```

### inventory_rolls  [IMPLEMENTED Fase 0.5 — koleksi baru, SSOT fisik]
```
Collection:  inventory_rolls            Prefix: roll_
Router:      routers/inventory.py (atau routers/rolls.py saat coding)
Component:   InventoryStockView.jsx (+ stock-breakdown matrix), SalesPortal (visibilitas)
Status:      DRAFT / PROPOSED (belum ada di DB/kode). Lihat KN_15.
Key Fields:
  id               string   prefix "roll_"  (1 dokumen = 1 roll fisik)
  product_id       string   FK → products.id  (katalog SHARED)
  owner_entity_id  string   FK → business_entities.id  (KEPEMILIKAN — wajib utk internal)
  ownership_type   enum     internal | supplier_consignment | reseller_consignment
                            (DEFAULT internal; konsinyasi DISIAPKAN, default OFF — KN_16 G1)
  consignor_ref    object?  {type: supplier|customer, id, name}  (bila konsinyasi)
  warehouse_id     string   FK → warehouses.id  (LOKASI gudang — netral)
  bin_id           string   lokasi detail (Zone→Rack→[Level]→Bin)
  lot              string   dye-lot generik (WAJIB) — penentu warna/celup (gate: harus terisi)
  dye_lot          string   P0-4 — dye lot AKTUAL tekstil (default = `lot` agar backward-compatible)
  batch            string   batch produksi/pembelian
  roll_no          string   nomor/serial roll fisik (label)
  length_initial   float    panjang awal aktual (catch weight)
  length_remaining float    sisa panjang (0 ≤ x ≤ length_initial)
  unit             string   base unit (meter|yard|...)
  grade            enum     [FASE A · D-01] A | A1 | A2 | B | BS  (rank 1..5; BS = barang sortir)
                            ⚠️ diubah HANYA lewat services/grade_service.py (PS-09)
  grade_source     enum?    [FASE A · D-23] qc_inspection | quarantine_release | manager_override | migration
  grade_updated_at string?  [FASE A] waktu perubahan grade terakhir
  grade_history    list     [FASE A · PS-09] [{grade_before, grade_after, rank_before, rank_after,
                            direction, source, source_label, reason, changed_by, changed_by_id,
                            changed_by_role, changed_at}] — WAJIB terisi setiap perubahan grade
  stage            enum?    [FASE A · PS-01] snapshot stage produk saat roll dibuat
  fabric_type      enum?    [FASE A · PS-02] snapshot woven|knit dari master produk
  qc_grade         string   P0-4 — grade hasil keputusan QC (saat accept; = grade)
  defects          list     P0-4 — profil cacat tekstil [string] (mis. ["belang","noda"])
  status           enum     receiving|quarantine|available|reserved|committed|picked|packed|hold|wip|
                            blocked|damaged|in_transit_transfer|in_transit_sales|in_transit_inbound|
                            in_transit_intercompany|subcon|delivered|consumed|returned_supplier
                            — [FIX-10 · SSOT-1] SSOT kosakata = `services/roll_state.STATUSES` (label = FE
                            `utils/statusVocab.js` DOMAIN_LABELS.roll). ⚠️ status DIUBAH HANYA lewat
                            `roll_state.transition()` (daftar-izin `ROLL_TRANSITIONS` + CAS + `status_history[]`
                            + rebuild saldo) — guardrail INV-ROLL-02 `verify_roll_status_writer.py`. Kode lama
                            registry `on_order/cross_dock/sold/returned/scrapped` tidak pernah ditulis (dibuang);
                            `allocated` = status alokasi SO (`sales_orders.allocations[].status`), BUKAN status roll.
  status_history   list     [FIX-10] [{status, timestamp, user, note, from, action, ref_type, ref_id, ref_no}]
                            (bentuk SSOT `services/status_history.py`, ≤ 30 entri terakhir; roll lama tanpa riwayat)
  tracking_mode    enum     rfid | barcode | document | manual   (stok visible TANPA RFID — KN_15 §7B)
  earmarked_for    object?  {type: sales_order|special_order, id}  (pegging supply↔demand)
  location_type    enum     warehouse_bin|transit_in|transit_out|cross_dock|drop_ship|transit_transfer
  reserved_ref     object   {type: sales_order|transfer, id}
  unit_cost        float?   HPP final per BASE unit (P0-5: base + Σ landed cost; NULLABLE bila tak ada harga PO)
  base_unit_cost   float?   P0-5 — HPP dasar per unit dari harga PO saat GR (sebelum landed cost)
  landed_cost_total float   P0-5 — Σ biaya landed cost yang dialokasikan ke roll ini (audit; default 0)
  landed_cost_refs list     P0-5 — daftar voucher landed cost (LCV-NNNNN) yang sudah di-apply
  writeoff_je_id, writeoff_je_number, writeoff_amount  — jurnal hapus-buku scrap retur (R5.1)
  writeoff_unit_cost, writeoff_base_unit_cost  float  [PK-27 · IV-02] biaya roll sesaat sebelum di-scrap; scrap
                            menolkan `unit_cost`/`base_unit_cost` (nilai sudah keluar dari 1-1300), batal scrap
                            (`reverse_writeoff`) memulihkannya dari dua field ini. Roll scrap lama: skrip
                            `scripts/migrasi_pk27_biaya_roll_scrap.py` (H3); invarian GL-SCRAP
  acquired         object   {via: po|transfer|initial|adjustment|return, ref_id, date}
  grade            string?  Grade tekstil (A|A+|B|C|BS) — P0-4 / di-set objektif oleh inspeksi 4-Point (6.2)
  defects          list     profil cacat; P0-4 free-text atau 6.2 [{point_value 1..4, count, note}]
  inspection       object?  Fase 6.2 — {points, grade, defects[], gsm_actual?, width_actual?, thresholds, inspected_by, inspected_at}
  rfid_tag_id      string?  FK → rfid_tags (Fase 5)
  is_remnant       bool     true bila roll = sisa potongan (BS)
  created_at, updated_at, created_by, created_by_name

⚠️ SSOT fisik stok. inventory_balances = PROYEKSI yang di-rebuild dari sini.
⚠️ Reservasi terjadi di LEVEL ROLL (atomic find_one_and_update status available→reserved).
⚠️ Penjualan owner-scoped: roll hanya boleh dijual entitas pemiliknya (owner_entity_id == SO.entity_id).
⚠️ JANGAN BUAT: stock_units, rolls (lepas), stock — gunakan inventory_rolls (namespace inventory_*).
```

### inventory_movements
```
Collection:  inventory_movements
Router:      routers/inventory.py
Component:   InventoryStockView.jsx (tab Ledger)
Movement Types:
  initial_stock | inbound_receiving | outbound_dispatch |
  transfer_out | transfer_in | cycle_count_adjustment | reservation | release_reservation
  [PROPOSED KN_15] + ownership_transfer_out | ownership_transfer_in (inter-company, owner berubah)
  [PROPOSED KN_15] + remnant_created | quarantine_in | quarantine_out | scrap
Key Fields:
  id, product_id, warehouse_id, movement_type, quantity, unit,
  batch, lot, roll_id, source_document, timestamp
  [PROPOSED KN_15] + owner_entity_id (wajib), roll_id (FK inventory_rolls),
                     from_owner_entity_id & to_owner_entity_id (utk ownership_transfer)

⚠️ APPEND-ONLY — tidak pernah update/delete movement yang sudah ada
⚠️ JANGAN BUAT: stock_history, gerakan_stok, stock_log
```

### system_settings  [Fase 1A IMPLEMENTED — Configuration Foundation]
```
Collection:  system_settings          Prefix: set_
Router:      routers/settings.py       Service: services/config_service.py
Component:   SettingsPanel.jsx (Admin → Pengaturan)
Key Fields:
  id, scope ("global" | entity_id),
  tax       {ppn_rate, ppn_mode(excluded|included), efaktur_enabled, is_pkp(derived)}
  finance   {base_currency, fiscal_year_end_month, default_payment_term_code}
  sales     {quotation_enabled, allow_partial_shipment, allow_order_discount, allow_item_discount}
  inventory {default_uom, min_cut_qty, intercompany_transfer_required}
  created_at, updated_at

⚠️ Effective settings = global di-override per-entitas (config_service.get_effective_settings).
⚠️ SEMUA configurable — JANGAN hardcode PPN/term/currency di kode.
⚠️ JANGAN BUAT: settings, config, configuration (lepas) — gunakan system_settings.
```

### config_values — sifat `bertanggal` pada pengaturan  [PK-46]
```
Collection:  config_values            Prefix: cfgv_   (append-only; FASE G-0)
Service:     services/config_resolver.py (set_value · resolve(key, ctx, at=…) · apply_due_values)
Registry:    config_registry.E(..., bertanggal=True, value_format="tarif_berjenjang")
Key Fields:  key, scope_type, scope_id, value, prev_value, effective_from, reason, changed_by, applied_at, cleared

⚠️ Kunci `bertanggal` (PK-46): nilai HANYA dari bawaan registry + baris config_values menurut effective_from;
   TIDAK diproyeksikan ke system_settings dan resolver TIDAK membaca lapisan lama (legacy_global/legacy_entity).
   Pembaca wajib memberi tanggal: resolve(key, ctx, at=<akhir hari tanggal dokumen, WIB>). value_of() = hari ini (layar).
⚠️ Enam kunci PPh 21 bertanggal (grup sdm, lapisan grup saja, izin hr.manage_payroll, alasan wajib):
   hr.pph21.ter_table · hr.pph21.ptkp_to_ter · hr.ptkp_table (kini aktif) · hr.pph21.pasal17_table ·
   hr.pph21.biaya_jabatan_pct · hr.pph21.biaya_jabatan_maks_bulanan
   Pembaca: services/hr_payroll_service.py:aturan_pph21(tanggal akhir periode gaji).
Berkas data pajak:
   backend/data/pph21_bawaan.py — bawaan registry = konstanta kode lama dipindah apa adanya (BELUM diverifikasi, PY-03)
   docs/blueprint/data/pph21_terverifikasi.json — berkas PEMILIK (K-42); BELUM ADA (titik henti H4).
     Dimuat dengan scripts/muat_pph21_terverifikasi.py --dry-run | --apply (--apply di data nyata = H3)
   backend/tests_mem/data/pph21_sintetis.json — tabel uji sintetis, BUKAN tarif nyata
   backend/tests_mem/data/pph21_snapshot_kode_lama.json — perilaku kode lama (dibuat buat_snapshot_pph21.py)
```

### config_values — pembatalan jadwal  [KF-T3]
```
Collection:  config_values            Prefix: cfgv_   (append-only; FASE G-0)
Service:     services/config_resolver.py (cancel_scheduled · ensure_due_applied · apply_due_values · history)
Router:      POST /api/config/values/cancel-scheduled  {id, reason} — izin pengubah kunci itu + lapisan barisnya
Field baru (PENANDA, bukan field nilai — hanya pada baris berjadwal yang dibatalkan sebelum berlaku):
  cancelled_at      teks ISO   saat jadwal dibatalkan; ada = baris diabaikan resolver & apply_due_values
  cancelled_by      teks       nama pembatal
  cancelled_by_id   teks       id pembatal
  cancel_reason     teks       alasan (wajib untuk kunci berisiko tinggi)

⚠️ INV-CFG-03 diperluas: penanda yang boleh diisi SEKALI = applied_at, cancelled_at. Field nilai tetap tidak diubah.
⚠️ Riwayat (`GET /api/config/history`) tetap memuat baris yang dibatalkan dengan `cancelled: true`.
⚠️ Tanpa migrasi. Penimpaan terdaftar (PT bukan PKP, wajib transfer antar-PT, Master Grade) = services/config_overrides.py
   — tidak menyimpan apa pun; resolver menambah `stored_value` + `overridden_by` pada jawabannya.
```

### payment_methods  [PM-T1 — daftar induk cara bayar, master berlapis global → PT]
```
Collection:  payment_methods           Prefix: pmeth_
Router:      routers/payment_methods.py (GET /api/payment-methods?direction=&entity_id= — login, data rujukan)
             routers/entity_masters.py  (kind `payment-methods`, tulis = `cash.configure`)
Service:     services/payment_method_service.py (normalize · get · active_for · is_cash · ensure_seed)
Component:   config/paymentMethods.js (usePaymentMethods) · Pengaturan › Keuangan & Pajak › Master per Badan Usaha
Key Fields:
  id, entity_id ("all" = global), code (kanonik huruf kecil, unik per lapisan), name,
  needs_account (bank|kas|tidak), needs_reference, needs_due_date, is_new_money,
  directions [masuk, keluar], aliases [kata lama], sort, active, notes
Benih global: transfer · cash (tunai, kontan) · giro (cek) · qris · va (nonaktif) · edc (nonaktif, kartu) ·
  deposit (titipan; is_new_money false). Baris khusus PT MENANG walau nonaktif (mematikan untuk satu PT).
⚠️ BUKAN termin: `payment_terms` (tunai/kredit/DP/bertahap) dan profil bayar pelanggan tetap kosakata termin.
```

### payment_codes  [PM-T2 — kode bayar per pesanan / baris tagihan (berita transfer pelanggan)]
```
Collection:  payment_codes             Prefix: pyc_
Service:     services/payment_code_service.py (ensure_for_order, ensure_for_line, find_in_text, instruction)
Router:      routers/payment_methods.py (GET /api/sales-orders/{id}/payment-instruction — `order.view` + PT + pemilik)
Index:       uq_id · (entity_id, status, created_at) · WAJIB uq_pay_code (code, unik LINTAS PT) ·
             WAJIB uq_pay_code_line (order_id, line_id)
**SCOPED** (`entity_id` = PT pesanan).

  id · code "{awalan}-{5 karakter}" (karakter 23456789ABCDEFGHJKLMNPQRSTUVWXYZ — tanpa 0, 1, I, O; awalan
       `payment.kode_bayar_awalan`, bawaan "KN"; dibuat `secrets`, tabrakan → ulang ≤ 5 kali)
  entity_id · order_id · order_number · customer_id
  plan_id · line_id   baris tagihan `payment_plans.lines[].line_id`; "" = kode tingkat pesanan
  order_level bool    kode tingkat pesanan (baris `dp` jadwal tagihan memakai ulang kode ini: plan_id/line_id diisi)
  percent             persen wajib bayar-dulu saat kode lahir (tunai 100, DP50 50; 0 untuk kode baris)
  amount · due_date   POTRET jumlah & jatuh tempo saat kode lahir ("" = sebelum barang dikirim)
  status              aktif | lunas | batal   (lunas/batal diurus PM-T3)
  created_at · updated_at
Lahir: pesanan bayar-dulu (termin `type: cash` atau `dp_percent > 0`) dikonfirmasi → satu kode (nilai × persen);
  pesanan tempo → belum ada kode sampai jadwal tagihan CR-T2 memanggil `ensure_for_line`.
Instruksi bayar dicetak hanya bila cara bayar ber-rekening bank DAN rekening tujuan `show_on_documents: true`.
```

### bank_account_changes  [PM-T1 — perubahan rekening kas/bank, menunggu orang kedua / riwayat]
```
Collection:  bank_account_changes      Prefix: bac_
Router:      routers/bank.py (GET /api/bank-account-changes?status=&page=, POST /{id}/decision — `cash.approve`)
Service:     services/bank_account_change_service.py (buat, ubah, putuskan, daftar, daftar_penerima)
Index:       uq_id (unik) · (entity_id, status, created_at)
**SCOPED** (`entity_id` = PT rekening).

  id · entity_id · entity_name · account_id ("" untuk rekening baru) · account_name
  action            buat | ubah
  changes[]         {field, from, to}   (nilai lama yang BERLAKU, termasuk nilai awal rekening lama)
  payload · reason
  status            menunggu | diterapkan | ditolak
  requested_by(_id) · decided_by(_id) · decision_note · created_at · decided_at
Setujui: pengaju ≠ pemutus bila `kontrol.ubah_rekening.min_orang` = 2; diterapkan hanya bila nilai `from` masih
sama (beda → 409 "…sudah diputus atau datanya sudah berubah. Ajukan ulang.").
```

### cash_account_cutovers  [Kas & Bank 1, Tugas 3 — pindah saldo kas lama ke akun buku besar per rekening, per PT]
```
Collection:  cash_account_cutovers     Prefix: psk_ (psk_{id PT}_{urut 3 digit} — dua siapkan bersamaan = satu usulan)
Router:      routers/cash_account_cutover.py (semua `accounting.manage`)
Service:     services/cash_account_cutover_service.py (pratinjau, siapkan, setujui, lanjutkan, tolak, posting_tertunda)
Index:       uq_id (unik) · (entity_id, status, created_at)
**SCOPED** (`entity_id` = PT yang dipindah).

  id · entity_id · label · pilihan_akun {id rekening: kode akun}
  status            menunggu | memproses (klaim persetujuan, `lease_until`) | disetujui | ditolak
  hitungan_disiapkan · sidik_disiapkan · total_dipindah
  disiapkan_oleh(_id) · disiapkan_pada · disetujui_oleh(_id) · disetujui_pada · tanggal_jurnal (hari persetujuan WIB)
  sidik_disetujui (dilihat penyetuju) · sidik_diposting (hitung ulang sesudah `nyalakan`) · hitungan_diposting
  selisih_diperiksa · selisih_disetujui[{rekening_id, nama, selisih}] (R10: wajib dicentang bila ada selisih)
  rencana {aktif_sejak, baris_jurnal, tunggal[{rekening_id, kas_ids}]} (niat; tidak dikirim API) · aktif_sejak
  gl_status · gl_error · gl_failed_at · journal_entry_id · journal_number (jurnal `pindah_saldo_kas`, Posting Gagal
  jenis `pindah_saldo_kas`) · kas_ditautkan · selesai_pada
  ditolak_oleh(_id) · ditolak_pada · alasan_tolak · jejak[{aksi, oleh, oleh_id, pada, catatan}]
  akun_pilihan_sebelum[{rekening_id, kode, akun_id, sebelum{is_cash, bank_account_id, is_cash_dari_rekening}}] (potret
  akun bagan PT pilihan Finance sebelum ditandai; tidak dikirim API) · akun_pilihan_dilepas[kode] (saat ditolak)
  created_at · updated_at
Tolak: sub-akun buatan sistem tetap (kosong); akun pilihan Finance dipulihkan persis dari potret, rekening kembali tanpa
akun (tinjauan akhir I2). Pratinjau PT aktif = keadaan sesudah pindah (saldo akun rekening vs buku kas, angka
`hitungan_diposting`; tinjauan akhir I1).
Setujui: penyiap ≠ penyetuju (`kontrol.pindah_saldo_kas.min_orang`, bawaan 2); sidik beda → 409 "Angka berubah, muat
ulang."; jurnal Dr akun rekening / Cr akun asal per rekening per akun asal; `cash_account_mode.nyalakan`; kas lama tanpa
rekening yang ikut rekening tunggal mendapat `account_id` + `account_id_dari_pindah_saldo`.
```

### fund_transfers  [Kas & Bank 1, Tugas 4 — Pindah Dana antar dua rekening satu PT]
```
Collection:  fund_transfers     Prefix: pdn_ (acak)   Nomor: {KODE PT}/PDN-NNNNN (deret per PT, `doc_number_kinds` `pdn`)
Router:      routers/fund_transfers.py (lihat `cash.view`, buat/terima `cash.create`, setujui `cash.approve`, batal
             `cash.delete`)
Service:     services/fund_transfer_service.py
Index:       uq_id (unik) · uq_number (unik) · (entity_id, status, tanggal_kirim) · (entity_id, dua_tahap, tanggal_kirim)
**SCOPED** (`entity_id` = PT kedua rekening).

  id · number · entity_id
  status            menunggu_persetujuan (kas belum terbit) | dalam_perjalanan (kas kirim terbit, belum diterima) |
                    selesai | batal
  rekening_asal_id · rekening_asal_nama · rekening_tujuan_id · rekening_tujuan_nama (nama = potret saat dibuat)
  nominal · biaya (biaya transfer, dibebankan ke rekening asal) · catatan
  tanggal_kirim · tanggal_terima (rencana; = tanggal kirim bila sekali jalan) · tanggal_diterima (nyata) · dua_tahap
  butuh_persetujuan (kontrol.pindah_dana saat dibuat) · disetujui_oleh(_id) · disetujui_pada
  kas_ids {kirim, biaya, terima} (juga kas yang sudah terbit bila terbit terhenti) · akun_transit · akun_beban_bank (akun lawan saat kas terbit) · terbit_pada · terbit_error
  gl_status · gl_error (ringkasan jurnal kasnya; ulang dari Posting Gagal › Transaksi Kas menyegarkan)
  diterima_oleh(_id) · diterima_pada
  alasan_batal · dibatalkan_oleh(_id) · dibatalkan_pada · status_sebelum_batal · batal_gl_status (pending | posted |
  failed — Posting Gagal jenis `fund_transfer_cancel`) · batal_gl_error · batal_gl_failed_at · batal_selesai_pada ·
  void_journal_entry_ids · jejak[{aksi, oleh, oleh_id, pada, catatan}] · saga_lock (selama aksi berjalan)
  created_by(_id) · created_at · updated_at
Kas: `create_cash(ref_type="fund_transfer", ref_id=id, seq=kirim|biaya|terima)` dengan `contra_account_code` = akun
transit (`kas_bank.kas_transit`) atau beban bank (`kas_bank.beban_bank`); akun kas dipilih pintu kas (`akun_kas`).
Batal: semua kas tidak-batal dibalik (`post_cash_void`), ditolak bila ada kas ber-`reconciled_amount` > 0.
```

### cash_out_requests  [Kas & Bank 2, C6 — kas keluar manual di atas batas menunggu orang kedua]
```
Collection:  cash_out_requests  Prefix: pkk_ (turunan PT + Idempotency-Key; tanpa kunci: acak)
             Nomor: {KODE PT}/PKK-NNNNN (deret per PT, `doc_number_kinds` `pkk`)
Router:      routers/cash.py (`POST /cash-transactions` → 202 `{request}`), routers/cash_out_requests.py (lihat
             `cash.view`, setujui/tolak `cash.approve`, batal pengaju `cash.create` atau `cash.delete`)
Service:     services/cash_out_request_service.py
Index:       uq_id (unik) · uq_number (unik) · uq_cor_idem_key (entity_id, idempotency_key | kunci tidak kosong) UNIK,
             WAJIB-ADA · (entity_id, status, created_at)
**SCOPED** (`entity_id` = PT rekening kas). BUKAN dokumen kas: tidak terhitung di saldo kas, daftar/ringkasan Transaksi
Kas, maupun buku kas rekening sampai disetujui.

  id · number · entity_id
  status            menunggu_persetujuan | disetujui (kas terbit) | ditolak | dibatalkan
  cash_type · direction ("out") · amount · category · description · account_id · account_name (rekening hasil
  pemeriksaan saat diajukan) · txn_date (tanggal yang diajukan = tanggal kas saat disetujui)
  idempotency_key (kunci kiriman; unik per PT) · sidik (sidik isi kiriman, tidak dikirim API)
  pengaju {id, name} · created_by(_id) (= pengaju) · ai_card_id (bila dari kartu Asisten)
  budget_check (pemeriksaan anggaran saat diajukan) · budget_check_setuju (saat disetujui — yang menentukan)
  cash_id · cash_number (kas yang terbit) · terbit_error (kas ditolak di tengah terbit; bisa disetujui lagi)
  disetujui_oleh(_id) · disetujui_pada · alasan_tolak · ditolak_oleh(_id) · ditolak_pada
  alasan_batal · dibatalkan_oleh(_id) · dibatalkan_pada
  jejak[{aksi (ajukan | setujui | tolak | batal), oleh, oleh_id, pada, catatan}] · saga_lock (selama aksi berjalan)
  created_at · updated_at
Kontrol: `kontrol.kas_keluar_manual.{min_orang,batas_nominal}` per PT (bawaan "1" + Rp 1.000.000, "di atas" = lebih
dari); dinilai saat diajukan dan TIDAK dinilai ulang saat disetujui. Pengaju ≠ penyetuju (`tolak_bila_pelaku_sama`;
Admin pun — bawaan `kontrol.admin_tetap_dua_orang`).
Kas: `create_cash(ref_type="manual", ref_id=id, txn_date=txn_date)`; pembuat kas = pengaju, `extra` = `disetujui_oleh(_id)`,
`disetujui_pada`, `cash_out_request_number`, `budget_check`. Kas yang terbit = kas manual biasa (batal lewat Transaksi Kas).
```

### payment_plans — jadwal tagihan  [CR-T2 — tambahan field; satu jadwal hidup per pesanan]
```
Collection:  payment_plans   Prefix: pyp_   (tidak ada koleksi kedua, `02` D1)
Service:     services/billing_schedule_service.py (jadwal `term`) · services/payment_plan_service.py (rencana `manual`)
Index:       uq_plan_active_doc (doc_type, doc_id | status active) · uq_plan_live_doc (doc_id, doc_type | status
             active/closed) UNIK, WAJIB-ADA (H6 bila data kembar) · lines.line_id · (origin, status) · (customer_id, status)

  origin            term | manual   (term = lahir otomatis dari termin, tidak bisa diubah/di-void tangan;
                                     manual = rencana cicilan buatan orang; membuatnya me-void jadwal term)
  mode              + `term` ("Mengikuti termin")
  term_code · term_type · net_days · dp_percent   potret termin saat jadwal lahir (lapisan PT menang)
  billed_total      Σ lines[].amount (jadwal term = total_amount)
  recognized_total  Σ debit akun piutang jurnal pengakuan penjualan pesanan (cara `recognized_by_order`)
  billed_complete   Σ baris ≥ nilai tagihan − nota kredit tertangguh (jadwal term boleh `closed` bila juga lunas)
  rev               int; syarat tulis-bersyarat (`recompute_paid`, `sync_order`, ubah/void)
  lines[]:
    line_id         ppl_… identitas tetap (semua baris; baris lama diisi `scripts/build_billing_schedule.py`)
    kind            + shipment (per nomor surat jalan) · debit_note (nota debit PK-32); dp = uang muka
    source_type · source_id   shipment + nomor surat jalan · order + `dp:<id pesanan>` (uang muka) / id pesanan (jurnal
                              lama per pesanan) · debit_note + id nota · manual — kunci idempotensi baris
    shipment_ids    dokumen `shipments` yang dicakup · journal_ids · journal_numbers (tautan jurnal, L8)
    billed_at       saat baris lahir (posisi "per tanggal")
    due_date        jatuh tempo = `report_basis.jatuh_tempo(tanggal, report_basis.hari_termin(...))` (satu rumus)
Baris term: K-16 — tempo/tunai: per nomor surat jalan berjurnal; DP: baris dp saat konfirmasi + surat jalan ×
(100 − DP) %; nota debit: satu baris senilai tagihan tambahan. Pesanan sample/mati tidak berjadwal (batal → void).
INV-PAY-01 (term): Σ baris = billed_total ≤ nilai + toleransi; = nilai bila terkirim penuh. INV-PAY-05 (WARN): pesanan
berjurnal tanpa jadwal tersimpan.
```

### customer_balances  [CR-T2 — saldo piutang tersimpan per pelanggan per PT; TURUNAN]
```
Collection:  customer_balances   Prefix: cbl_
Service:     services/customer_balance_service.py (compute murni dari dokumen · refresh hitung ulang penuh · get ·
             rebuild_all · job_refresh_overdue 00.10 WIB · verify_stored INV-BAL-01 · reconcile_gl INV-BAL-02)
Router:      routers/customer_balances.py
Index:       uq_id (unik) · uq_customer_entity (customer_id, entity_id) UNIK, WAJIB-ADA · (entity_id, overdue_as_of)
**SCOPED** (`entity_id` = PT pesanan).

  id · customer_id · entity_id
  ar_delivered          Σ min(sisa, max(0, pengakuan − terbayar)) pesanan hidup (barang terkirim belum lunas)
  cash_term_amount      bagiannya dari pesanan bertermin tunai tanpa DP
  open_orders_amount    Σ (sisa − bagian terkirim) — pesanan belum dikirim
  cash_term_open_amount bagiannya dari pesanan bertermin tunai tanpa DP
  open_orders_count     pesanan berpiutang (bukan tunai) yang masih bersisa
  overdue_amount        Σ sisa baris jadwal ber-jatuh tempo < hari ini (pesanan berpiutang)
  oldest_due_date       jatuh tempo tertua baris yang masih bersisa · overdue_as_of = tanggal hitung (WIB)
  giro_outstanding      Σ kwitansi giro tidak-batal belum terverifikasi bank (PM-T3)
  deposit_balance       cermin customers.deposit_balance (PT pemilik data pelanggan) · store_credit_balance (buku saldo
                        kredit pasangan) · penalty_outstanding (Σ nota denda terbit − terbayar)
  last_payment_at · last_payment_amount   kwitansi tidak-batal terakhir
  stale · stale_reason  refresh gagal (dibetulkan pembaca `get` / job harian) · rebuilt_at · updated_at · created_at
Ditulis HANYA `customer_balance_service` (`refresh`, `rebuild_all`). Pemicu refresh: fungsi alokasi PK-19 (`_segarkan`,
`remove_unborn`), simpan/batal kwitansi, deposit, saldo kredit, kait jadwal tagihan, nota denda, rencana cicilan baru.
`days_overdue` dihitung saat baca (`GET /customers/{id}/balance`).
```

### customer_credit_profiles  [CR-T1 — profil kredit per pelanggan per PT]
```
Collection:  customer_credit_profiles   Prefix: ccp_
Service:     services/credit_profile_service.py (effective, status_from, migrasi_data_lama)
Index:       uq_id (unik) · uq_customer_entity (customer_id, entity_id) UNIK, WAJIB-ADA (D7)
**SCOPED** (`entity_id` = PT PESANAN, bukan PT pemilik data pelanggan). Tidak ada dokumen = semua nilai ikut bawaan PT.

  id · customer_id · entity_id
  limit_mode          ikut_pt | khusus | tanpa_batas   ("tanpa batas" pilihan tersendiri, bukan angka 0)
  credit_limit        angka ≥ 0 (wajib bila khusus)
  limit_valid_until   YYYY-MM-DD | ""   (lewat tanggal → plafon efektif = `ar.default_credit_limit` PT, asal "kedaluwarsa")
  allowed_term_codes  [kode termin]  (kosong = semua termin aktif PT; ditegakkan CR-T3)
  default_term_code   string (anggota allowed_term_codes bila terisi)
  overdue_block_days  int ≥ 0 | null  (null = `ar.overdue_block_days` PT)
  credit_status       normal | blokir_manual   (awas/tahan DIHITUNG, tidak disimpan)
  block_reason        string (≥ 5 huruf bila blokir_manual)
  penalty_rule        null (= ikut PT) | {mode: khusus|bebas, rate_pct_per_month, base, cap_pct, grace_days, reason,
                      valid_until} — CR-T4: DIBACA mesin denda (`penalty_service.penalty_policy`, lapisan pelanggan per
                      PT; satu-satunya pemilik — lima kunci denda Pusat Pengaturan tanpa lapisan `customer`).
                      khusus: angka/`base` terisi menimpa PT (null/"" = ikut PT; tarif & batas 0–100, tenggang 0–180);
                      bebas: `reason` ≥ 5 huruf + `valid_until` WAJIB, lewat tanggal → dibaca ikut PT (mode mati selama
                      berlaku, nota draf lama tidak disentuh). Diubah lewat pengajuan (`credit_profile_service.submit`)
                      atau skrip `scripts/migrate_penalty_customer_layer.py` (H3)
  credit_group_id     string (K-29, belum dihitung mesin)
  version             int (naik 1 tiap perubahan; syarat tulis)
  updated_at · updated_by(_id) · last_request_id · created_at
Ditulis HANYA `credit_profile_service.decide` (pengajuan disetujui) dan skrip migrasi.
```

### credit_profile_requests  [CR-T1 — pengajuan perubahan profil kredit]
```
Collection:  credit_profile_requests    Prefix: cpr_    Nomor: {KODE PT}/PKR-NNNNN (`next_doc_number`, jenis `pkr`)
Router:      routers/credit_profiles.py
Index:       uq_id (unik) · uq_open_request (customer_id, entity_id) UNIK parsial status "diajukan", WAJIB-ADA ·
             (entity_id, status, created_at) · (customer_id, entity_id, status, decided_at)
**SCOPED** (`entity_id` = PT profil yang diubah).

  id · number · customer_id · customer_name · entity_id
  changes[]        {field, from, to}   (`from` = nilai tersimpan saat diajukan; null bila belum ada profil)
  base_version     versi profil saat diajukan
  reason (≥ 5 huruf) · attachment_url
  credit_snapshot  potret `compute_customer_credit` saat diajukan (D3; tidak dihitung ulang)
  status           diajukan → disetujui | ditolak | dibatalkan
  requested_by(_id) · created_at · decided_by(_id) · decided_at · decision_note · profile_version
Putus: `credit_profile.approve` + `kontrol.ubah_profil_kredit.*` (nominal = plafon baru). `from` berbeda dari profil
sekarang → 409 "Profil kredit sudah berubah sejak pengajuan dibuat. Buat pengajuan baru." (pengajuan dibatalkan otomatis).

### credit_overrides  [KN_17 S37 · CR-T3 — izin kredit bernominal, berlingkup, bermasa berlaku]
```
Collection:  credit_overrides          Prefix: cro_
Layanan:     services/credit_override_service.py (`create`, `decide`, `reasons`, `tampil`) · services/credit_gate.py
             (`use_override` — pembaruan bersyarat sisa + masa berlaku; `release_use`)
Router:      routers/crm.py (`POST /customers/{id}/credit-override` credit_override.create · `GET /credit-overrides`,
             `GET …/{id}` credit_override.view · `POST …/{id}/decision` credit_override.approve + Aturan Persetujuan
             `credit_override` + `kontrol.lewat_batas_kredit.*`) · routers/so_approvals.py (pembungkus
             `request-credit-approval` → lingkup pesanan + entri persetujuan `kredit`)
SCOPED lewat `entity_id` (PT izin = PT pesanan; `guard_doc`).

  id · customer_id · customer_name · entity_id · status pending → approved | rejected | cancelled
  scope            pesanan | pelanggan   (CR-T3; dokumen lama tanpa `scope` = pelanggan)
  order_id · order_number    wajib bila `scope: pesanan` · has_so_entry (true = diajukan lewat entri persetujuan pesanan)
  amount (> 0, PK-45) · remaining_amount (mulai = amount; dikurangi tiap pemakaian, tidak pernah negatif)
  valid_until      ISO | ""  — diisi saat disetujui = waktu putus + `ar.izin_kredit_masa_berlaku_hari` (0 = "" tanpa batas)
  reason_code · reason_label (master alasan `amendment_reasons`, applies_to `credit_override`) · reason (catatan)
  used_by[]        {order_id, order_number, amount, at}   jejak pemakaian (kartu pelanggan, pesanan)
  credit_snapshot · gate_snapshot (potret saat diajukan, D3) · rejection_id · evidence_url
  requested_by(_id) · created_at · decided_by(_id) · decided_at · decision_reason · consumed (jejak lama)
⚠️ Izin lama bernominal 0 (dulu "tanpa batas") yang belum dipakai dianggap KEDALUWARSA (tidak melepas tahan). Kueri pencari:
   db.credit_overrides.find({status:"approved", $or:[{amount:0},{amount:null}], consumed:{$ne:true}})
```

### credit_gate_rejections  [CR-T3 — pesanan yang ditolak gerbang kredit saat dibuat]
```
Collection:  credit_gate_rejections    Prefix: cgr_
Layanan:     services/credit_gate.py (`record_rejection`, `tandai_penolakan_dilanjutkan`)
Router:      routers/crm.py (`GET /credit-gate-rejections?status=&customer_id=` berhalaman, `GET …/{id}` memuat
             `payload_snapshot`; credit_override.view — pembuat pesanan sendiri selalu boleh)
Index:       uq_id (unik) · (entity_id, status, created_at)
**SCOPED** (`entity_id` = PT pesanan yang ditolak).

  id · entity_id · customer_id · customer_name · actor_id · actor_name · amount · term_code · result
  reasons[]        {code, result, message, data}
  exposure · limit · overdue    potret hasil gerbang (D3; tidak dihitung ulang)
  payload_snapshot isi permintaan `POST /api/sales-orders`
  status           terbuka → dilanjutkan (izin kredit pelanggan itu di PT itu disetujui) | kedaluwarsa · override_id
  created_at · updated_at
```

### ai_action_proposals  [AG-T1 — kartu tindakan Tanya KN: draf PO, pengingat tagih, tindak lanjut pelanggan]
Kartu disiapkan asisten (alat `propose_action`) dan baru dijalankan saat pembuatnya menekan Setujui. **USER_SCOPED**
(dibaca pemiliknya, `user_id`; izin `ai.configure` boleh melihat milik orang lain); PT kartu = `entity_id` (PT aktif saat
disiapkan; mode "Semua PT" ditolak) dan kartu hanya bisa disetujui saat PT aktif = PT kartu.
```
Collection:  ai_action_proposals       Prefix: aiact_
Router:      routers/ai_assist.py      (GET /api/ai/actions/{id}, POST {id}/confirm, POST {id}/dismiss)
Service:     services/ai_actions.py    (propose_action, load, confirm, dismiss)
Index:       uq_id (unik) · (user_id, status, created_at)

  id · type (draft_po | collection_followup | customer_followup) · title · reason · note · payload {pos | reminders}
  user_id · user_name · entity_id · session_id · created_at
  expires_at        created_at + `ai.kartu_masa_berlaku_jam` PT kartu (kartu baru). Kartu lama tanpa field ini dianggap
                    berlaku sampai created_at + nilai pengaturan PT kartu (dihitung saat dibaca, tidak disimpan)
  status            pending → running → confirmed | failed · pending → dismissed | expired (tidak pernah kembali ke pending)
  result[]          nomor PO / pengingat yang sudah jadi, ditambahkan BERTAHAP (sebelum butir berikutnya dijalankan)
  error             ≤ 500 huruf, galat asli pelaksana bila `failed`
  started_at · updated_at · finished_at (saat confirmed/failed/dismissed/expired) · confirmed_at (lama, tetap diisi)
Saat dibaca: `pending` lewat `expires_at` → `expired`; `running` tak berubah > 10 menit (batas teknis) → `failed`
"Proses berhenti sebelum selesai. Periksa daftar PO sebelum meminta draf baru."
```

**AG-T3 — kartu golongan A/B** (`services/ai_cards.py`, satu koleksi untuk semua kartu; tanpa migrasi). Kartu disiapkan
alat `prepare_action` (hanya GET lewat pintu baca-saja) dan sesudah disetujui memanggil SATU endpoint layar
(`Idempotency-Key` + `X-Asisten-Kartu` = id kartu). Field tambahan:
```
  type              followup_note | payment_promise | collection_reminder (golongan A) · ar_receipt_create | bank_match |
                    holding_allocate | posting_retry (golongan B) — atau tiga jenis lama
  class · risk      A | B · low | medium | high (tingkat konfirmasi: high = alasan ≥ 10 huruf + ketik ulang nominal)
  request           ≤ 500 — kalimat permintaan pengguna
  args · args_initial   isian yang dikirim ke endpoint · salinan awal sebelum diubah pengguna
  editable[]        {path, label, kind} isian yang boleh diubah di kartu (kwitansi: tanggal, cara bayar, catatan)
  plan              {summary, rows: [{label, kind: money|text|date, before, after}], amount, confirm_text (nominal tanpa
                    pemisah), note ("Jurnal dibuat sistem saat disimpan."), meta}
  fingerprint · fingerprint_source[] · fingerprint_snapshot[]   sha256 potret data dasar saat disiapkan + cara membacanya
                    ulang ({path, params, pick}) + potretnya (D3). Sidik berbeda saat disetujui → `failed`/`stale`
  reason · edits    alasan & isian yang diubah pengguna saat menyetujui/mengabaikan
  decided_by · decided_at   {id, name} · ISO — siapa menyetujui atau mengabaikan
  result            {status_code, document: {type, label, id, number, link}, gl_status, message}
  error_code        stale (data berubah) | door (endpoint menolak) | uncertain (hasil tidak pasti)
  superseded_by     id kartu baru di percakapan yang sama
  status            + superseded (pending → superseded saat kartu baru disiapkan di percakapan yang sama)
Index:  (entity_id, status) · uq_pending_session — unik parsial (session_id) {status: "pending", session_id > ""}
        (REQUIRED_UNIQUE_INDEXES, satu kartu menunggu per percakapan; berlaku juga untuk jenis lama)
Dokumen hasil ber-`ai_card_id` (id kartu; diisi dari konteks `ai_card_context` hanya bila kartu `running` milik sesi):
  ar_receipts.ai_card_id · collection_followups.ai_card_id · bank_statement_lines.ai_card_id (catatan cocok) dan
  bank_statement_lines.holding_allocated[].ai_card_id · ulang jurnal: `audit_logs` `posting_failure_retried` saja.
```

**AG-T5 — kartu golongan C (uang keluar dan jurnal) dan orang kedua.** Tindakan `vendor_bill_pay`
(`POST /api/vendor-bills/{id}/pay`), `contra_bon_pay` (`POST /api/contra-bons/{id}/pay`), `cash_manual`
(`POST /api/cash-transactions`) — izin kartu `ai_finance.pay`; `journal_manual` (`POST /api/gl/journal`) dan
`journal_reverse` (`POST /api/gl/journal/{id}/reverse`, ketik ulang NOMOR jurnal) — izin kartu `ai_finance.post`; semua
`high`. Antrean Pusat Persetujuan `ai_card_second` (`approval_backlog_service.QUEUES`, preset tab Tindakan › Menunggu orang
lain). Kode di
luar REGISTRY yang cocok daftar larangan (`services/ai_card_rules.FORBIDDEN`, L1–L13) dijawab alasan barisnya. Field tambahan:
```
  class             + C (uang keluar dan jurnal)
  status            + awaiting_second ("Menunggu orang kedua"): pending → awaiting_second → running → confirmed | failed ·
                    awaiting_second → dismissed (ditolak orang kedua / ditarik pembuat) | expired. Masuk awaiting_second →
                    `expires_at` dihitung ulang dari saat itu (`ai.kartu_masa_berlaku_jam` PT kartu)
  second_required   {needed: bool, basis: "min_orang" | "batas_nominal" | ""} — potret keputusan kontrol
                    `kontrol.asisten_uang_keluar.*` saat pembuat menyetujui (D3)
  first_by · first_at              {id, name} · ISO — pembuat yang menyetujui tahap pertama
  second_by · second_at · second_reason   {id, name} · ISO · teks — orang kedua (alasan wajib saat menolak)
  executor_id       id pengguna yang sesinya menjalankan pintu (pembuat, atau orang kedua) — dibaca `ai_card_context`
  retype_kind       amount (ketik ulang digit nominal) | text (ketik ulang nomor dokumen persis: balik jurnal)
Index:  (entity_id, status) yang sudah ada melayani kotak "Menunggu orang lain" (`box=others`)
Dokumen hasil ber-`ai_card_id`: cash_transactions.ai_card_id (kas bayar hutang dan kas manual) · ap_payment_intents.ai_card_id ·
  vendor_bills.payments[].ai_card_id · contra_bons.payments[].ai_card_id · journal_entries.ai_card_id (jurnal manual, jurnal
  pembalik, dan jurnal kas yang lahir di permintaan kartu) · journal_proposals.ai_card_id (usulan bila pintu jurnal
  menuntut dua orang, KF-T6).
```

### ai_chat_sessions · ai_results — field AG-T2 (Asisten Keuangan)
Percakapan Tanya KN (`services/ai_chat_service.py`) dan hasil alat (`services/analytics_engine.save_result`). AG-T2 menambah
field berikut (tanpa migrasi; dokumen lama tanpa field = mode umum / tanpa keterangan):
```
ai_chat_sessions
  mode        umum | keuangan    mode percakapan (diisi saat sesi dibuat; giliran mode Keuangan menimpanya)
  alias_map   {by_name: {nama asli → kode}, counters: {awalan → nomor}}  peta samaran nama pihak sesi itu
              (PLG- pelanggan, PMS- pemasok, KRY- sales/karyawan, PHK- pihak lain; 3 digit berurutan per sesi).
              HANYA di server — tidak pernah dikirim ke penyedia model maupun ke layar (`services/ai_privacy.py`).
              Diisi di kedua mode (umum & keuangan) selama `ai.samarkan_nama` menyala untuk salah satu PT cakupan
  turns[].mode · turns[].sources   giliran mode Keuangan: sumber jawaban {result_id, title, entity_label, period_label,
              notes, link} yang disusun server dari hasil alat; `verification` tanpa daftar angka yang tidak cocok
ai_results (hasil alat keuangan `fin_*`, `services/ai_finance_tools.py`)
  entity_label  label PT / cakupan dari `scope_meta` endpoint (gabungan = "Penjumlahan … belum dieliminasi")
  period_label  periode atau "per {tanggal}" / "saat ini"
  notes[]       keterangan wajib (PT gabungan belum dieliminasi, rentang tanggal, dasar jatuh tempo, batas pemindaian …)
  link          {view, nav_id, focus_type, focus_id, tab?} — tombol "Buka di layar" di bagian Sumber
```

### ai_finance_packs  [AG-T4 — paket tutup buku bulanan Asisten Keuangan]
Paket satu bulan untuk satu PT, disusun dari endpoint layar lewat pintu baca-saja `SelfApi` (sesi & PT pembuat). **USER_SCOPED**
(dibaca pembuatnya, `user_id`); PT paket = `entity_id` (PT aktif saat dibuat; mode "Semua PT" ditolak 409). Tiap lembar
disimpan sebagai satu dokumen `ai_results` (bentuk hasil Tanya KN, 30 hari); koleksi ini tidak dibaca kode lain.
```
Collection:  ai_finance_packs          Prefix: aipack_
Router:      routers/ai_finance_packs.py  (POST /api/ai/finance/closing-pack [?stream=1], GET …/{id}, GET …/{id}/export.xlsx)
Service:     services/ai_finance_reports.py (build_closing_pack, iter_closing_pack, month_bounds, build_morning_brief)
Index:       uq_id (unik) · (user_id, created_at)

  id · user_id · user_name · entity_id · entity_label · entity_code · created_at
  period        YYYY-MM (bulan yang sudah berakhir) · period_label "Februari 2026" · start · end (hari pertama/terakhir)
  sections[]    {key, title, status ok|skipped|error, note, result_id} — 12 lembar berurutan (Ringkasan … Status Periode);
                `skipped` = endpoint menjawab 403 ("Tidak disertakan: Anda belum punya akses {modul}.")
  summary · summary_source auto|model   ringkasan; `model` hanya bila teks penyedia lolos pemeriksa angka
  verification  {checked, unmatched, ok} pemeriksa angka atas ringkasan yang dipakai
```

### ai_schedules — field AG-T4 (ringkasan pagi keuangan)
```
  kind          template (bawaan; dokumen lama tanpa field = template) | finance_morning
  finance_morning: template_id "" · frequency daily (selalu) · entity_id = PT aktif saat dibuat · entity_label
                title "Ringkasan pagi keuangan · {nama PT}". Saat dijalankan: izin `ai_finance.view` + sakelar akun pemilik
                diperiksa; sesi sementara pemilik (10 menit, `purpose: ai_schedule`) ditutup di `finally`
ai_schedule_runs (finance_morning): kind · sections[] {key, title, status, note, result_id} · narrative (teks notifikasi)
```

### payment_terms  [Fase 1A IMPLEMENTED]
```
Collection:  payment_terms             Prefix: pterm_
Router:      routers/settings.py
Component:   SettingsPanel.jsx (tab Term Pembayaran)
Key Fields:
  id, code (UNIQUE), name, type (cash|credit|dp|installment),
  net_days, dp_percent, installment_count, sort, active, created_at, updated_at

⚠️ JANGAN BUAT: terms, payment_term (singular) — gunakan payment_terms.
```

### product_lines  [FASE L IMPLEMENTED 2026-08-18]
```
Collection:  product_lines             Prefix: pline_
Jenis:       MASTER BERLAPIS global → badan usaha (entity_id="all" = global, override PT menang)
Router:      routers/entity_masters.py  (`/api/entity-masters/product-lines`)
Service:     services/entity_master_service.py (MASTERS["product-lines"])
             services/master_registry.py  → nilai HIDUP untuk `/api/enums` (enum `product_line`)
             services/line_scope.py       → pagar baca/tulis per akun (`users.allowed_line_codes`)
Component:   features/settings/masters/EntityMastersView.jsx + masters/masterFieldsConfig.js
             components/LineFilter.jsx (chip penyaring lini — dipakai 12 layar)
Key Fields:
  id                   string  prefix "pline_"
  entity_id            string  "all" = GLOBAL (INHERITED_GLOBAL_VALUES) | ent_xxx = override PT
  code                 string  UNIK per lapisan — woven | knit | printing | (bisa ditambah)
  name                 string  nama untuk manusia (mis. "Woven (Tenun)")
  sort                 int     urutan tampil di chip & dropdown
  active               bool
  fabric_type_required enum    "" | woven | knit — INV-LINE-02: produk ber-lini ini WAJIB
                               ber-`fabric_type` sama. `printing` SENGAJA "" (kain print
                               bisa woven maupun knit).
  measure_unit_default string  USULAN satuan saat membuat produk/PO (yard|kg|panel).
                               BUKAN sumber satuan kendali (itu `fabric_type.control_uom`
                               + `products.base_unit`) — kalau dipakai sebagai sumber,
                               FASE U melahirkan satuan ketiga.
  stage_sequence       list    urutan tahap untuk papan PO & SPK makloon (kode master FASE T)
  sample_types_default list    usulan jenis sampling saat membuat permintaan sample (FASE S)
  notes                string

Pemakai `line_code` (snapshot, bukan join):
  products.line_code · users.allowed_line_codes · inventory_rolls/inventory_lots
  (lewat domain_registry.roll_domain_snapshot) · wms_tasks · md_specs · md_samples ·
  design_gallery · makloon_orders · dan baris dokumen: sales_orders/purchase_orders/
  purchase_requisitions/warehouse_transfers/sales_returns/purchase_returns/
  interco_transactions/special_orders/internal_requests/rfqs → `items[].line_code`
  + turunan `line_codes[]` di kepala dokumen.

⚠️ TURUNAN: `line_codes[]` WAJIB == kumpulan `items[].line_code`. Dihitung SATU pintu
  `line_scope.stamp_doc()` / `codes_from_items()`; dijaga gate INV-LINE-01.
⚠️ SNAPSHOT: mengubah lini master produk TIDAK mengubah baris dokumen yang sudah terbit.
⚠️ KOSONG BUKAN PELANGGARAN: dokumen/produk tanpa lini TETAP terlihat semua akun
  (data lama) — pagar hanya menyembunyikan lini LAIN, bukan yang belum bergolong.
⚠️ JANGAN BUAT: lines, product_line (singular), fabric_lines — gunakan product_lines.
⚠️ JANGAN memakai `line_code` di rumus/konversi apa pun — itu tugas `fabric_type`.
Migrasi: scripts/migrate_lini_produk.py (idempotent · --dry-run · laporan
  docs/LAPORAN_MIGRASI_LINI_PRODUK.md untuk dikoreksi pemilik lewat layar).
```

### process_stages  [FASE T IMPLEMENTED 2026-08-19]
```
Collection:  process_stages            Prefix: pstg_
Jenis:       MASTER BERLAPIS global → badan usaha (entity_id="all" = global, override PT menang)
Router:      routers/entity_masters.py  (`/api/entity-masters/process-stages`)
             routers/makloon_orders.py  (`/api/process-stages`, `/api/process-stages/for-line/{code}`)
Service:     services/entity_master_service.py (MASTERS["process-stages"])
             services/master_registry.py  → nilai HIDUP untuk `/api/enums` (enum `process_stage`)
                                            + `process_types()` (benih ∪ nilai master)
             services/makloon_order_service.py → `_resolve_stage()` & `_resolve_material_flow()`
Component:   features/settings/masters/EntityMastersView.jsx + masters/masterFieldsConfig.js
             features/purchasing/MakloonOrderCreateModal.jsx (pemilih TAHAP langkah SPK)
             features/purchasing/MakloonOrderDetailPanel.jsx (aksi Issue / Terima / Catat Jasa)
Key Fields:
  id                    string  prefix "pstg_"
  entity_id             string  "all" = GLOBAL (INHERITED_GLOBAL_VALUES) | ent_xxx = override PT
  code                  string  UNIK per lapisan — benang | tenun | rajut | pfp | pfd |
                                celup | screen | printing | proofing | inspect | (bisa ditambah)
  name                  string  nama untuk manusia
  kind                  enum    material | makloon | sampling | inspection
                                (`process_stage_kind`; hanya makloon & sampling boleh jadi
                                 langkah SPK — lihat `spk_step` di registry)
  seq                   int     urutan papan PO & dropdown langkah
  active                bool
  applies_to_lines      list    KOSONG = SEMUA lini (aturan yang sama dengan
                                `users.allowed_line_codes` FASE L — jangan dijadikan wajib-isi)
  needs_vendor          bool    langkah dikerjakan mitra. SPK tanpa mitra hanya DIPERINGATKAN
                                (keputusan pemilik 3b); gate INV-DOMAIN-06 aturan E memerah
                                bila TIDAK ADA mitra terdaftar untuk prosesnya
  process_type          enum    sambungan ke `domain_registry.PROCESS_TYPES` (mesin tarif &
                                estimasi). KOSONG untuk tahap non-makloon
  target_use            enum    "" | dye | print — pemilah `pre_treatment` (PFD vs PFP)
  changes_stage         bool    FALSE = tahap TIDAK mengubah kain → mesin memaksa susut 0,
                                yield 1, qty keluar = qty masuk, `estimate.method="no_transform"`
  from_stage/to_stage   enum    tahap KAIN (`stage`). Bila `changes_stage=true`, pasangan
                                (from, process_type, to) WAJIB ada di STAGE_TRANSITIONS
  tariff_basis_default  enum    usulan basis tarif saat membuat langkah (`tariff_basis`)
  material_flow         enum    moves | service_only | either  ← APAKAH KAIN BERGERAK
                                moves        = kain dikirim ke mitra & kembali (jalur
                                               Issue → Terima, biaya masuk HPP kain)
                                service_only = JASA MURNI, kain tidak bergerak (jalur
                                               "Catat Jasa"; tidak ada roll yang lahir)
                                either       = boleh dua-duanya, dipilih per langkah SPK
  material_flow_default enum    moves | service_only — dipakai bila langkah SPK tidak memilih
                                (hanya berlaku saat `material_flow="either"`); pilihannya
                                DICATAT di `estimate.explain[]`, bukan ditebak diam-diam

Pemakai:
  makloon_orders.steps[].stage_code + stage_label · stage_kind · stage_seq ·
  stage_from_stage · stage_to_stage · stage_source · changes_stage · needs_vendor ·
  material_flow · material_flow_source
  product_lines.stage_sequence (urutan tahap per lini kerja)

ALIRAN UANG langkah `service_only` (FASE T — tiga pintu, tidak boleh ada pintu keempat):
  1. dicatat  → vendor_bill (`service_only: true`) + Dr 1-1350 WIP / Cr 2-1100 Hutang,
                lalu `makloon_orders.service_absorption_pending` bertambah
  2. diserap  → langkah kain berikutnya menambahkannya ke `wip_total` saat Terima Hasil
                → mendarat di HPP kain (`steps[].absorbed_service_value`)
  3. tak terserap → SPK selesai tanpa langkah kain sesudahnya:
                Dr 5-1200 Beban Jasa Makloon Tak Terserap / Cr 1-1350 WIP
                (`costing.service_unabsorbed`)
  Dijaga gate INV-MKO-07: Σ jasa murni == Σ diserap + menggantung + dibebankan.

⚠️ DUA KOSAKATA, JANGAN DICAMPUR: `process_stages` = LANGKAH KERJA (daftar pemilik) ·
  `stage` = KEADAAN KAIN · `process_type` = JENIS PROSES. Tahap MENUNJUK ke dua yang
  terakhir, tidak menggantikannya.
⚠️ `changes_stage=false` BUKAN "tahap tidak penting": ia punya mitra, tarif & tagihan
  sendiri. Yang tidak berubah hanyalah KAINNYA.
⚠️ JANGAN BUAT: process_steps, stages, makloon_stages — gunakan process_stages.
⚠️ Langkah SPK sebelum FASE T tidak punya `stage_code`; `_resolve_stage()` mencarinya
  dari `process_type` (+`target_use`) supaya angka SPK lama TIDAK bergeser.
Gate:    scripts/guardrails/verify_master_stages.py (INV-DOMAIN-06, ber-`--self-test`)
Migrasi: scripts/migrate_process_stages.py (idempotent · --dry-run = hasil sungguhan ·
  hanya MENAMBAH field turunan; `estimate`/`tariff*`/nilai HPP tidak disentuh)
```

### sample_types  [FASE S IMPLEMENTED 2026-08-23]
```
Collection:  sample_types              Prefix: stype_
Jenis:       MASTER BERLAPIS global → badan usaha (entity_id="all" = global, override PT menang)
Router:      routers/entity_masters.py  (`/api/entity-masters/sample-types`)
             routers/rnd.py             (`/api/rnd/sample-types?line=`, `/api/rnd/meta`)
Service:     services/entity_master_service.py (MASTERS["sample-types"])
             services/master_registry.py  → nilai HIDUP untuk `/api/enums` (enum `sample_type`)
                                            + `sample_type_options()` · `measurement_fields_of()`
                                            + `default_sample_types_for_line()`
             services/rnd_sample_service.py → `_resolve_types()` & `_validate_measurements()`
Component:   features/settings/masters/EntityMastersView.jsx + masters/masterFieldsConfig.js
             features/rnd/SampleFormModal.jsx (pemilih JENIS — boleh lebih dari satu)
             features/rnd/RoundActionModal.jsx (kolom hasil ukur DINAMIS dari master)
Key Fields:
  id                    string  prefix "stype_"
  entity_id             string  "all" = GLOBAL (INHERITED_GLOBAL_VALUES) | ent_xxx = override PT
  code                  string  UNIK per lapisan — labdip | handfeel | proofing |
                                bulk_sample | (bisa ditambah pemilik)
  name                  string  nama untuk manusia
  seq                   int     urutan form & pemilih jenis
  active                bool    `bulk_sample` = FALSE (keputusan pemilik #4, 2026-08-19):
                                dinonaktifkan, TIDAK dihapus dari enum, supaya dokumen lama
                                tetap punya labelnya
  applies_to_lines      list    KOSONG = SEMUA lini (aturan yang sama dengan FASE L/T —
                                jangan dijadikan wajib-isi, layar akan mendadak kosong)
  requires_design       bool    TRUE = permintaan yang memuat jenis ini WAJIB merujuk kode
                                desain. Dulu `if stype == "proofing"` di dalam kode; kini
                                DATA, sehingga jenis baru yang butuh desain tidak perlu
                                programmer. Tombol mati/hidupnya: kebijakan
                                `rnd.require_design_for_proofing`
  measurement_fields    list    nama field hasil ukur yang WAJIB diisi saat menutup round
                                jenis ini. Bentuk tiap field (label · satuan · batas wajar)
                                ada di `domain_registry.SAMPLE_MEASUREMENTS` (enum
                                `sample_measurement`) — SATU sumber untuk validator server,
                                form setor hasil, dan ringkasan panel
  notes                 string

Pemakai:
  md_samples.sample_types[]  (DAFTAR — satu permintaan boleh menempuh labdip + handfeel)
  md_samples.rounds[].type_code  (tiap round milik SATU jenis; kuota `rnd.max_rounds`
                                  dihitung per (supplier × jenis))
  md_samples.rounds[].measurements  (kunci ⊆ measurement_fields jenis round itu)
  md_specs.sample_type_hint  (usulan jenis saat spesifikasi dibuat)
  product_lines.sample_types_default  (usulan jenis per lini — keputusan pemilik #3:
                                       woven/knit = labdip+handfeel · printing = proofing)

⚠️ SATU SUMBER JENIS: `md_samples.sample_type` (tunggal) **DIHAPUS** oleh
  `scripts/migrate_sample_types.py`. Selama dua field hidup bersama, tiap pembaca baru
  punya dua tempat untuk bertanya dan keduanya menyimpang dalam beberapa sesi.
⚠️ JANGAN BUAT: sampling_types, sample_type (singular), sampling_kinds — gunakan sample_types.
⚠️ SKOR TIDAK SEBANDING ANTAR-JENIS: 90 pada labdip = warnanya tepat, 90 pada handfeel =
  rasanya tepat. Karena itu papan perbandingan supplier dipecah PER JENIS, dan
  `participants[].types[type_code]` menyimpan ringkasannya masing-masing.
Gate:    scripts/guardrails/verify_sample_types.py (INV-SAMPLE-01, ber-`--self-test`)
Migrasi: scripts/migrate_sample_types.py (idempotent · --dry-run = hasil sungguhan ·
  memindahkan `sample_type` → `sample_types[]`, memberi `rounds[].type_code`, lalu
  MENGHAPUS field lama)
```

### complaint_reasons  [FASE I IMPLEMENTED 2026-08-23]
```
Collection:  complaint_reasons          Prefix: creas_
Jenis:       MASTER BERLAPIS global → badan usaha (entity_id="all" = global, override PT menang)
Router:      routers/entity_masters.py  (`/api/entity-masters/complaint-reasons`)
             routers/sales_returns.py   (`/api/sales-returns/meta/complaint-reasons`)
Service:     services/entity_master_service.py (MASTERS["complaint-reasons"])
             services/master_registry.py  → nilai HIDUP untuk `/api/enums`
                                            (enum `complaint_reason`) +
                                            `complaint_reason_options()` ·
                                            `complaint_reason_meta()` ·
                                            `complaint_reason_label()`
             services/return_service.py   → `_resolve_complaint()` (SATU validator untuk
                                            `create_return` DAN `set_complaint`)
Component:   features/settings/masters/EntityMastersView.jsx + masters/masterFieldsConfig.js
             features/sales/ReturnJourneyPanel.jsx (pemilih sebab keluhan + garis waktu)
Key Fields:
  id                    string  prefix "creas_"
  entity_id             string  "all" = GLOBAL (INHERITED_GLOBAL_VALUES) | ent_xxx = override PT
  code                  string  UNIK per lapisan — warna_beda | kotor_stain | sobek_lubang |
                                salah_kirim | kurang_yard | handfeel | lain
                                (bisa ditambah pemilik lewat layar Master Data)
  name                  string  nama untuk manusia
  seq                   int     urutan pemilih di form retur
  active                bool    FALSE = tidak ditawarkan lagi, TETAPI labelnya tetap terbaca
                                untuk retur LAMA (pola yang sama dengan `bulk_sample` FASE S)
  applies_to_lines      list    KOSONG = SEMUA lini (aturan sama dengan FASE L/T/S)
  needs_inspection      bool    TRUE = keluhan yang WAJIB dibuktikan lewat inspeksi fisik
                                (SPK `inspections`) sebelum kredit/ganti diberikan. Keluhan
                                administratif (mis. `salah_kirim`) = FALSE. Dulu tidak ada
                                sama sekali: semua retur diperlakukan sama
  claimable             bool    TRUE = wajar diteruskan sebagai klaim ke supplier/makloon
  notes                 string

Pemakai:
  sales_returns.complaint_code + complaint_label + complaint_note
  sales_returns.complaint_needs_inspection · complaint_claimable   (snapshot keputusan
                                                                    master saat dicatat)

⚠️ BUKAN teks bebas. Tiga pertanyaan pemilik — supplier/lini mana yang paling sering
  bermasalah · keluhan mana yang berujung klaim · apakah inspeksi MENYETUJUI keluhan
  pelanggan — hanya bisa dijawab kalau sebabnya punya kode yang stabil.
⚠️ JANGAN BUAT: return_reasons, complaint_codes, alasan_retur — gunakan complaint_reasons.
⚠️ Label DI-SNAPSHOT ke dokumen (`complaint_label`) supaya retur lama tetap terbaca kalau
  baris master kelak diganti namanya — pola yang sama dengan snapshot lini (FASE L) dan
  satuan (FASE U).
```

### inspections   *(prefix `ins_` · nomor `<ENT>/INS-#####` · SCOPED `entity_id`)*  [FASE I IMPLEMENTED 2026-08-23]
**SPK INSPEKSI & QC** — dokumen **PEKERJAAN PEMERIKSAAN**: siapa memeriksa, kapan, atas
dasar sample yang mana, dan apa keputusannya. Angka cacat & grade sudah lama dihitung
`qc_inspection_service` (4-point) dan tersimpan di roll; yang TIDAK pernah ada adalah
**SPK-nya**. Praktik pemilik memakai lembar kertas "Inspect PO", "Inspect Retur (per PT)",
"Inspect retur & replacement" — tanpa dokumennya, tiga pertanyaan tidak terjawab: siapa
memeriksa, kapan, dan atas dasar apa barang diterima/ditolak.

Collection: `inspections`   Prefix: `ins_`   Router: `routers/inspections.py`
Service: `services/inspection_service.py`   Schema: `schemas_inspection.py`
SCOPED via `entity_id` (`entity_scope.SCOPED_COLLECTIONS`; `qc_inspections` DICABUT pada
commit yang sama — koleksi hantu, 0 dokumen, 0 penulis) · `doc_refs` type `inspection`
(order 26, `source_fk=["ref_doc_id"]`) · dipantau `scripts/gate_residue.py` WATCH ·
index di `indexes.py` · PDF `pdf_resolvers.resolve_inspection_spk` (doc_type
`inspection_spk`, e-signable).

```
id · number (<ENT>/INS-#####) · entity_id · line_code        (FASE L: snapshot lini)
kind: po_receipt | makloon_output | return_customer | return_supplier | replacement
ref_doc_type · ref_doc_id · ref_doc_number                   (PO / MKO / retur)
task_id                                                       (tugas penerimaan QC)
supplier_id · supplier_name | customer_id · customer_name
spk_date · assigned_to · assigned_name · bagian ("Bagian Inspect")
started_at · finished_at
status: draft → assigned → in_progress → done (→ closed)     (reopen: done → in_progress)
        [FIX-10] tabel transisi `services/inspection_state.py` (daftar-izin per aksi + CAS status asal di filter
        tulis `inspection_service._save`); `status_history[]` bentuk SSOT `{status,timestamp,user,note,from,action}`
        — terpisah dari linimasa peristiwa `history[]`
baseline_sample_id · baseline_sample_number · baseline_contract_id · baseline_color
summary {lines, rolls, measure, unit, points_total, grade_after_counts{},
         inspected, color_mismatch, handfeel_mismatch, hold, rejected}   (DIHITUNG)
decision: terima | terima_sebagian | turun_grade | tolak  · decision_label
remark · reject_reason · reopen_reason · decided_by · decided_at
history[] · created_at · updated_at

lines[] {
  id · roll_id · roll_no · lot · dye_lot · product_id · sku · article
  color_id · color_code · gsm_standard · width_standard
  qty_rolls · quantity · unit                     (FASE U — bentuk KANONIK & DATAR)
  points_snapshot · grade_before · grade_after     (RINGKASAN — bukan sumber angka)
  gsm_actual · width_actual
  color_result: sesuai | beda_shade | tolak        · delta_e
  handfeel_result: sesuai | beda | tolak           · handfeel_score (1..5)
  decision · remark · hold · hold_reason
  hold_released_by · hold_released_at · hold_release_reason
  inspected_by · inspected_at
  return_item_index                                (baris retur: menunjuk items[] retur)
}
```

**BATAS TEGAS: DOKUMEN INI BUKAN PINTU KE-3 UNTUK GRADE** (§3.4 rencana MD-ERP).
Melanggarnya = dua angka untuk satu roll, dan tidak ada cara memilih mana yang benar.
* poin cacat & grade **hanya** dihitung `qc_inspection_service.inspect_roll()` yang
  memanggil `grade_service.set_roll_grade(source="qc_inspection")`;
* warna & handfeel disimpan **DI ROLL** (`inventory_rolls.inspection.color_result`,
  `handfeel_result`, `handfeel_score`, `baseline_sample_id`, `hold{}`) karena pertanyaan
  "roll ini warnanya beda dari sample — boleh masuk gudang?" ditanyakan di ROLL, dan di
  sanalah pagar putaway (`services/location_service.py`) membacanya;
* `lines[]` = **RINGKASAN + keputusan**; `points_snapshot`/`grade_after` DISALIN dari
  hasil pemanggilan di atas, tidak dihitung ulang.

* **RBAC** (modul `inspection`, `permissions_config.py`): `view` admin·manajer·gudang·
  Admin Sales · `create`/`assign`/`decide`/`reopen` admin·manajer ·
  `inspect` admin·manajer·**gudang** (petugas Bagian Inspect).
* **Pelepas tahanan = MANAJER/admin** (`inspection_service.HOLD_RELEASE_ROLES`,
  keputusan pemilik #5 dikonfirmasi 2026-08-23). Gudang yang mencoba → **403**
  ber-kalimat menuntun.
* **Antrean keputusan**: `approval_backlog_service.QUEUES` baris `inspection_hold`
  (`lines.hold=true` + status assigned|in_progress|done) → KPI beranda & Pusat
  Persetujuan. Yang menunggu BUKAN "inspeksi belum selesai" (itu pekerjaan, bukan
  keputusan) melainkan **tahanan** yang hanya manajer boleh lepas. Hitung-ulang mandiri
  di `verify_home_kpi.EXPECT` (**INV-HOME-01**) & pintunya di `DOOR_QUEUE`
  (**INV-APPR-01**).
* **Kebijakan selisih** dari Pusat Pengaturan: `qc.color_mismatch_action` (bawaan
  **tahan**) · `qc.handfeel_mismatch_action` (bawaan **peringatkan**) ∈
  `abaikan | peringatkan | tahan` — tipe registry `enum` (BUKAN `select`: itu galat yang
  menghentikan backend 2026-08-23).
* **`tolak` & `reopen` & lepas-tahanan WAJIB ber-alasan**, dan alasannya tersimpan di
  DOKUMEN (`reject_reason` / `reopen_reason` / `lines[].hold_release_reason`) — bukan
  hanya di jejak audit yang tidak pernah dibaca orang yang sedang bertanya.
* **Jejak dua arah**: ke dokumen sumber `rel="parent"`; ke sample acuan
  `rel="references"` (BUKAN `parent` — inspeksi tidak LAHIR dari sample, ia hanya
  membandingkan diri dengannya; pasangan `references`/`referenced_by` lahir di FASE I
  bersama pencabutan label mati `applied_to`, DRIFT D6).
* **LAHIR OTOMATIS**: `ensure_for_qc_task()` dipanggil jalur penerimaan
  (`routers/inbound_receiving.py`) tepat saat tugas menjadi `qc_pending` — idempotent.
  Jaring pengamannya `GET /api/inspections/queue/qc-tasks` (tugas QC yang belum punya
  SPK) supaya otomatisasi yang pernah gagal TERLIHAT, bukan ditemukan setahun kemudian.
* Layar: `features/inspections/InspectionsView.jsx` (daftar berhalaman + Unduh CSV +
  chip jenis/status + penyaring "hanya yang DITAHAN") · `InspectionDetailPanel` ·
  `InspectionFormModal` · `InspectLineModal`. Nav: hub **Gudang → Operasi Gudang (WMS)**
  tab "SPK Inspeksi & QC" (`view: "inspections"`).
* Gate: **INV-QC-01/02a/02b/03** di `scripts/verify_data_integrity.py`
  (lapisan `inspection`) · POC `backend/test_core_inspeksi_poc.py`.

⚠️ **JANGAN BUAT** koleksi baru: `qc_inspections` (DICABUT), `inspection_orders`,
`qc_docs`, `inspeksi` — gunakan `inspections`.
⚠️ **JANGAN** menyimpan angka poin/grade sebagai SUMBER di sini (itu
`inventory_rolls.inspection` + `grade_history[]`), dan JANGAN menyimpan hasil per barang
retur di sini (itu `sales_returns.items[].inspection`, ditulis `return_service`).

### sales_returns — field baru (FASE I.F)
Milestone perjalanan retur dari lembar pemilik + sebab keluhan:
`complaint_code` · `complaint_label` · `complaint_note` · `complaint_needs_inspection` ·
`complaint_claimable` (master `complaint_reasons`) · `shipped_to_store_at` ("SJ Kirim
Toko") · `shipped_to_customer_at` ("Kirim ke pelanggan") · `goods_arrived_at` ("Barang
sampai") · `milestones[]` {id, milestone, label, at, by, note, replaced, recorded_at} ·
`inspection_id` · `inspection_number` · `inspect_done_at`.

* Tiga tonggak pertama ditandai manusia: `POST /api/sales-returns/{id}/milestone`
  (izin `update` — ini pencatatan pekerjaan, BUKAN keputusan, jadi sengaja TIDAK
  terdaftar di `QUEUES`). Server menolak **tanggal masa depan** dan menolak "Barang
  sampai" sebelum ada pengiriman — supaya garis waktunya bisa dibaca sebagai cerita.
* Tonggak keempat **DITURUNKAN** dari dokumen: `inspection_service.finish()` mengisi
  `inspect_done_at`. Tidak ada endpoint manual untuk field itu — dua tanggal "inspeksi
  selesai" yang bisa berbeda adalah kelas cacat yang paling sering menipu di repo ini.
* Menandai ULANG diperbolehkan (koreksi salah tanggal itu wajar) tetapi tanggal lama
  TIDAK hilang: setiap penandaan menambah baris `milestones[]` ber-`replaced`.
* Layar: `features/sales/ReturnJourneyPanel.jsx` (di dalam `ReturnDetail`).

### approval_policies  [KP-T4 — satu tabel kebijakan persetujuan untuk semua antrean]
Satu baris = satu rentang nominal pada satu jenjang satu jenis dokumen (`approval_kinds.APPROVAL_KINDS`: tiap kunci
`approval_backlog_service.QUEUES` punya ≥ 1 jenis, dijaga INV-APPR-01 aturan G). Yang boleh memutus = pemegang izin
setujui jenis itu **dan** (`any_holder` atau perannya ∈ `roles` rentang yang memuat nilai dokumen) — tidak ada peringkat
peran. Baris PT menggantikan baris grup jenis yang sama; tanpa baris sama sekali → baris bawaan dihitung dari sumber lama
(`approval_policy_service.default_rows_for`, sumber `bawaan`) sampai `scripts/migrate_kpt4_kebijakan_persetujuan.py`
menuliskannya (bawaan hanya-lapor; data nyata = H3). Pembuat ≠ penyetuju tetap `kontrol.<aksi>.*` (KF-T6).
**SCOPED** dengan baris grup `entity_id = "all"` (INHERITED_GLOBAL_VALUES).
```
Collection:  approval_policies          Prefix: appol_
Router:      routers/approval_policies.py   (GET /kinds, GET ?entity_id=&doc_kind=, GET /check, PUT /{doc_kind},
             DELETE /{doc_kind}?entity_id=&reason=, GET /can-decide/me)
Service:     services/approval_policy_service.py  (required_levels, can_decide, assert_can_decide, who_can_decide,
             build_default_rows, default_rows_for, rows_for, policy_view, check_view)
Index:       uq_id (unik) · (doc_kind, entity_id, level, sort)

  id · doc_kind · entity_id ("all" | id PT) · level (≥ 1) · label (mis. "Direksi")
  min_amount (≥ 0) · max_amount (kosong = tanpa batas; berlaku bila min ≤ nilai < max) — jenis tanpa nominal: 0 & kosong
  roles (id peran; kosong = rentang ini tidak butuh persetujuan) · any_holder (benar = siapa pun pemegang izinnya)
  sort · active · source (bawaan | migrasi | pengguna) · version · reason · created_at · created_by · updated_at · updated_by
```
Batas nominal sebuah peran untuk satu jenis = batas atas rentang tempat peran itu tercantum (K-51).
`PUT` mengganti SELURUH baris (jenis, lapisan): baris lama `active=false` + `replaced_at/by` (jejak tetap), baris baru
`source="pengguna"`, `version+1` (`expected_version` basi → 409). `legacy_role` = nilai kompatibel `required_role`
(tampilan/notifikasi lama), tidak pernah dipakai memutus.
Field dokumen yang ikut lahir (KP-T4, D3 — potret saat dokumen dibuat): `purchase_orders.approval_chain[]` dan
`special_orders.approval_chain[]` menambah `roles`, `rule_id`, `policy_kind`; `doc_amendments.approval_amount` (nilai yang
dinilai saat diusulkan, termasuk akumulasi); `special_orders.approved_automatically` (tidak butuh persetujuan menurut tabel).
⚠️ JANGAN BUAT daftar peran penyetuju baru di kode pintu atau kunci registry — tambah baris/jenis di sini.

### doc_number_formats  [KP-T5 — Penomoran Dokumen: format nomor per jenis dokumen per PT]
Hanya format yang **diubah**; tanpa baris = bawaan katalog `doc_number_kinds.py` = bentuk nomor sebelum KP-T5 (tidak ada
migrasi data, tidak ada dokumen dinomori ulang — H3). Pembaca: `doc_numbering_service.effective_format` (baris PT → baris
grup `entity_id = "all"` → katalog); `scope` hanya pada baris grup. Pembuat nomor tetap `core_utils.next_doc_number`.
```
Collection:  doc_number_formats         Prefix: dnf_
Router:      routers/doc_numbering.py   (GET ?entity_id=, POST /preview, PUT /{kind}, DELETE /{kind}?entity_id=&reason=)
Service:     services/doc_numbering_service.py  (effective_format, plan, seed_number, render, list_formats, row_view,
             preview, save_format, clear_format)
Index:       uq_id (unik) · uq_kind_entity (kind, entity_id) unik — wajib-ada (indexes.REQUIRED_UNIQUE_INDEXES, D7)

  id · kind (kunci katalog, mis. so, cn_retur, lot) · entity_id ("all" = grup | id PT)
  prefix  teks [A-Z0-9][A-Z0-9-]{0,11} — awalan tercetak (awalan IDENTITAS katalog tetap kunci deret)
  width   bilangan 3–8 · date_token "" | YY | YYYY | YYMM | YYYYMM | YYMMDD · reset tidak | tahunan | bulanan | harian
  scope   per_pt | bersama — hanya baris grup
  version · reason · created_at · created_by · updated_at · updated_by
```
Bentuk nomor: per PT `{KODE PT}/{prefix}{sisipan-}{angka}`; bersama `{prefix}{sisipan-}{angka}`. Kunci `number_sequences`
tidak berubah: per PT (`entity_id`=PT, `doc_type` = awalan identitas + bagian periode, tanpa `-` akhir, huruf besar),
bersama (`"__shared__"`, `koleksi:field:awalan identitas + bagian periode-`). Bagian periode menurut `reset`. Deret
periode baru disemai dari nomor tertinggi yang sudah ada. Perubahan dicatat di `audit_logs` (`doc_number_format_saved`,
`doc_number_format_cleared`) beserta format sebelum/sesudah dan alasan.
⚠️ JANGAN menulis awalan/lebar nomor baru di titik panggil tanpa entri katalog `doc_number_kinds.py` (uji U1 KP-T5).

### approval_rules  [Fase 1A IMPLEMENTED]
```
Collection:  approval_rules            Prefix: aprule_
Router:      routers/settings.py       Service: config_service.evaluate_approval()
Component:   SettingsPanel.jsx (tab Matriks Approval)
Key Fields:
  id, doc_type (sales_order|purchase_order|transfer|discount), entity_id ("all"|entity_id),
  min_amount, max_amount (null = tak terhingga), required_role ("" = tanpa approval),
  is_percent (utk discount), sort, active, created_at, updated_at

⚠️ Matriks CONFIGURABLE menyesuaikan flow. Rule entitas-spesifik diutamakan, fallback "all".
⚠️ JANGAN BUAT: approval_matrix, approvals (lepas) — gunakan approval_rules.
FASE F-6 (2026-08-17): koleksi ini **TETAP HIDUP**. Rute CRUD-nya kini
  `routers/approval_rules.py` (+ `services/approval_service.py`), layar
  Pengaturan → "Aturan Persetujuan" (`features/settings/ApprovalRulesSettings.jsx`).
  Penilai ambang yang BERLAKU hanya `config_service.evaluate_approval()` /
  `build_approval_chain()` (dipakai `routers/sales_orders.py` & `routers/purchase_orders.py`);
  penilai kembar `approval_service.check_approval_required()` DIHAPUS agar tak ada dua pendapat.
KP-T4 (2026-11-14): jalur tulis `POST/PATCH/DELETE /api/approval-rules` DIMATIKAN (410). Baris di sini hanya terbaca
  (riwayat, Master per PT, `/approval-rules/effective`) dan membentuk baris BAWAAN `approval_policies` (SO/PO/PR) selama
  tabel kebijakan belum punya baris untuk jenis itu. Penilai mesin = `approval_policy_service` (`evaluate_approval` /
  `build_approval_chain` kini pembungkusnya).
KP-T3 (2026-11-14): doc_type yang dinilai mesin hanya sales_order|purchase_order|purchase_requisition
  (`discount` dipensiunkan: tidak dibenihkan, ditolak saat simpan, tidak ditampilkan); required_role =
  "" atau peran di registry peran (`owner` ditolak). Pemilih aturan satu fungsi
  `config_service.approval_pool()` (dipakai `evaluate_approval` dan `GET /api/approval-rules/effective`).
  Field opsional, DITULIS HANYA oleh `scripts/migrate_kpt3_aturan_persetujuan.py` (--apply):
    migrated_from_role  teks — nilai required_role lama yang tidak dikenal (mis. "owner") sebelum diganti "manager"
    retired_reason      teks — alasan aturan dinonaktifkan migrasi ("Jenis aturan tidak dipakai mesin", aturan discount)
```

### approval_requests  [DIPENSIUNKAN FASE F-6 (2026-08-17) — JANGAN DIPAKAI LAGI]
```
Collection:  approval_requests         Prefix: appreq_        STATUS: RETIRED
Router:      (DIHAPUS — dulu routers/approval_requests.py)
Alasan pensiun (semuanya TERUKUR, bukan pendapat):
  · `create_approval_request()` NOL pemanggil → koleksi selalu kosong (0 dok), sementara
    `POST /approval-requests/{id}/approve|reject` ADA & izin `approval.approve` dipegang
    admin+manajer → wewenang di kertas tanpa satu pun dokumen yang bisa diputuskan.
    (KPI beranda yang berbohong 0-padahal-17 lahir dari koleksi mati ini — lihat F-3.)
  · NOL pemakai di layar: tak satu pun berkas `frontend/src` memanggil `/approval-requests`.
  · Menghidupkannya MELANGGAR arsitektur: setiap persetujuan nyata diputuskan di endpoint
    dokumennya sendiri (Pusat Persetujuan sengaja read-only) → mesin generik akan menjadi
    JALUR PENULISAN STATUS KEDUA untuk dokumen yang sama.
  · Endpointnya membaca tanpa saringan badan usaha (pada `get` bahkan `resolve_scope_ids()`
    dihitung lalu tak dipakai) → pagar multi-PT bocor pada fitur yang tak pernah dipakai.
Gantinya: 14 antrean keputusan NYATA didaftarkan di
  `services/approval_backlog_service.QUEUES` (transfer gudang · kontrabon verifikasi/
  persetujuan/sengketa · permintaan internal · retur antar-PT · tagihan supplier · biaya
  masuk · uang muka + pertanggungjawaban · klaim makloon · buka periode · cuti · lembur),
  dijaga gate **INV-APPR-01** (`scripts/guardrails/verify_approval_queues.py`).
⚠️ JANGAN MEMBUAT ULANG mesin generik tanpa produsen: invarian F pada INV-APPR-01 akan
   MEMERAH bila `approval_requests` dipakai lagi sementara produsennya masih nol.
```

### price_approvals  [Sub-fase 1.7 IMPLEMENTED — Special Price / Approval Harga]
```
Collection:  price_approvals           Prefix: pra_
Router:      routers/price_approvals.py
Service:     services/storage_service.py (upload bukti — Emergent Object Storage)
Component:   features/sales/PriceApprovals.jsx
Consumed by: routers/sales_orders.py (get_effective_special_price → override harga item)
Key Fields:
  id, entity_id, customer_id, customer_name, product_id, sku, product_name,
  normal_price (snapshot harga produk), requested_price (harga khusus/unit),
  min_quantity, unit, reason, valid_from, valid_until ("" = tanpa kadaluarsa),
  status (draft|pending|approved|rejected), attachments[] (bukti),
  requested_by, requested_by_name, approved_by, approved_by_name,
  decision_notes, decided_at, created_at, updated_at
Attachment item:
  id (att_), storage_path, original_filename, content_type, size,
  uploaded_by, uploaded_at, is_deleted (soft-delete; storage tak punya delete API)
Status flow:  draft → pending → approved | rejected
RBAC:
  sales   → create/update/delete pengajuan SENDIRI (row-level)
  manager → approve/reject; admin → semua
Konsumsi SO:
  item.price_approval_id valid (approved, berlaku, qty ≥ min_quantity) → price = requested_price.
  INVARIAN tetap: item.subtotal = price × quantity.

⚠️ Special Price = price_approvals (BUKAN koleksi 'special_prices'/'price_lists' lepas).
⚠️ JANGAN BUAT: special_prices, nego_harga, price_overrides — gunakan price_approvals.
```


### shipments  [Sub-fase 1.8 IMPLEMENTED — Status SO diperluas + Partial Shipment]
```
Collection:  shipments               Prefix: shp_   (No. Surat Jalan: SJ-#####)
Router:      routers/outbound_picking.py (GET /shipments, GET /shipments/{id}/surat-jalan)
Service:     services/shipment_service.py (dispatch_task), services/fulfillment_status.py
Component:   features/wms/OutboundScanInterface.jsx, features/orders/OrderDetailPanel.jsx
Key Fields:
  id, shipment_no (SJ-#####), order_id, order_number, task_id, allocation_id,
  warehouse_id, warehouse_name, warehouse_city, product_id, product_name, sku,
  qty (BASE UNIT), unit, rolls[] ({roll_id, lot, length, unit}),
  is_partial, status (dispatched), created_by, created_at
Dibuat saat:  dispatch task outbound (parsial/penuh) — 1 record per event dispatch.
INVARIAN (verify_data_integrity L4-SHIP):
  shipped_qty ≤ quantity per task · Σ shipments.qty == Σ task.shipped_qty per order ·
  status SO ⟺ progres task (picked / partially_shipped / shipped / done).
SSOT-safe (KN_15 §10): pengiriman = roll committed → in_transit_sales (BUKAN $inc balance);
  mark-delivered → roll in_transit_sales → 'delivered' (keluar dari owned_qty).
Status SO (Sub-fase 1.8): confirmed → partially_picked → picked → partially_shipped
  → shipped → done (manual via /sales-orders/{id}/mark-delivered).
⚠️ Status 'dispatched' di SO DEPRECATED → gunakan shipped/done. Task tetap pakai 'dispatched'.
```

### tax_invoices  [Sub-fase 1.9 IMPLEMENTED — Faktur Pajak Jual]
```
Collection:  tax_invoices             Prefix: fkt_   (No. Internal: FKT-##### + NSFP resmi 16-digit)
Router:      routers/tax_invoices.py (GET /tax-invoices?status=&doc_kind=, POST /sales-orders/{id}/tax-invoice,
             PATCH /tax-invoices/{id}/nsfp, POST .../replace, POST .../cancel, GET .../document;
             TX-T2: POST .../{id}/issue, POST .../{id}/discard, POST /tax-invoices/drafts/rebuild,
             GET /tax/output-reconciliation)
Service:     services/tax_invoice_service.py (issue/replace/cancel/set_nsfp/render_faktur_html; TX-T2:
             draft_for_shipment, draft_for_credit_note, issue_draft, discard_draft, rebuild_drafts,
             output_reconciliation, job_tax_draft_backfill)
Component:   features/finance/TaxInvoices.jsx, features/finance/TaxOutputRecon.jsx, features/orders/OrderDetailPanel.jsx
Key Fields:
  id, number (FKT-#####), nsfp (16-digit resmi, opsional/menyusul), kode_transaksi (01..09),
  status (TX-T2: draf|normal|pengganti|diganti|batal), replaces_id, replaced_by_id, cancel_reason, replace_reason,
  doc_kind (TX-T2: faktur|retur — tanpa field = faktur), trigger (TX-T2: pesanan|surat_jalan|retur — tanpa field =
  pesanan), shipment_no, shipment_ids, credit_note_id, credit_note_number, ref_tax_invoice_id, ref_tax_invoice_number,
  journal_entry_ids, journal_entry_numbers (jurnal sumber angka draf), status_before_replaced (status sebelum
  `diganti`), drafted_at, issued_at, issued_by, discard_reason, discarded_at, discarded_by,
  faktur_date, order_id, order_number, entity_id,
  seller_name, seller_npwp, seller_address (snapshot entitas PKP),
  customer_id, customer_name, customer_npwp, customer_address, has_customer_npwp (snapshot),
  items[] ({product_name, sku, quantity, unit, price, subtotal, discount_amount, line_total}),
  total_amount, discount_total, net_subtotal, dpp, ppn_rate, ppn_mode, ppn_amount, grand_total,
  is_pkp, created_by, created_at, updated_at,
  active_key (PK-40: HANYA pada dokumen hidup — `so:{order_id}` / `ic:{interco_pair_id}`; TX-T2 + `sj:{order_id}:{nomor
  surat jalan}` / `retur:{credit_note_id}`; dimiliki draf/normal/pengganti, dicabut saat diganti/batal),
  nsfp_key (PK-40: digit NSFP faktur aktif ber-NSFP)
Dibuat saat:  MANUAL (opsional — pajak TIDAK wajib) dari Order detail; PKP-only + ppn_amount>0; idempotent (1 aktif/order).
  TX-T2 (K-32): pengaturan `tax.pemicu_faktur` per PT — `pesanan` (bawaan = perilaku di atas) · `surat_jalan` (draf
  otomatis sesudah jurnal tiap surat jalan, `shipment_service.dispatch_task`; angka dari jurnal surat jalan; pemulih
  job harian `tax_draft_backfill`; terbit per pesanan ditolak 409) · `uang_muka` (terdaftar, ditolak saat disimpan — H4).
  Dokumen pajak retur (`doc_kind: retur`) lahir sebagai draf dari `credit_note_service.settle` (nota kredit ber-PPN atas
  pesanan berfaktur terbit; angka = PPN yang dibalik jurnal nota). Draf diterbitkan orang (`issue_draft`) atau dibuang
  beralasan (`discard_draft`, tidak dibuat ulang otomatis). Faktur asal yang diganti → `diganti`; membatalkan pengganti
  memulihkan status asal. Data lama: scripts/migrate_tax_invoice_status.py (H3).
Rekap PPN keluaran (TX-T2): Σ faktur `normal`/`pengganti` (belum diganti) − Σ dokumen retur `normal`.
Keunikan (PK-40, dijamin indeks unik wajib): `uq_fkt_active` (satu faktur aktif per pesanan / transaksi antar-PT),
  `uq_fkt_nsfp` (satu NSFP per faktur aktif, lintas PT). Penulis kunci: services/tax_invoice_service.py
  (`kunci_aktif_keluaran`), services/interco_tax_service.py; data lama: scripts/blueprint/pk40_kunci_faktur.py.
  Masa pajak terkunci (`tax_period_locks`) → terbit/ganti/batal/ubah NSFP ditolak 409.
INVARIAN (verify_data_integrity L4-FKT):
  PPN == DPP × rate · Grand == DPP + PPN · ref order valid · normal/pengganti ⟹ is_pkp & ppn>0 ·
  ≤1 faktur aktif (bukan batal & belum diganti) per pemilik (`so:`/`ic:`) · nomor unik · rantai pengganti (replaces_id
  valid) · FKT-5 (PK-40) active_key/nsfp_key = keadaan faktur (kunci lama belum diisi = WARN) · TX-T2: FKT-3 per
  `active_key` (sj:/retur: ikut; pesanan tidak boleh berfaktur per pesanan sekaligus per surat jalan) ·
  INV-TAX-OUT-01 (wajib hijau): tiap PT PKP × masa — selisih faktur − retur vs buku besar akun pemetaan
  `penjualan.ppn_keluaran` terjelaskan seluruhnya (`output_reconciliation.unexplained == 0`; sebab terjelaskan = WARN).
⚠️ Penomoran HYBRID: FKT-##### internal + NSFP resmi diisi menyusul (alokasi DJP/Coretax e-Faktur).
⚠️ JANGAN BUAT: faktur, faktur_pajak, bills, tagihan — gunakan tax_invoices.
```



### wms_tasks
```
Collection:  wms_tasks
Routers:     routers/wms.py (generic CRUD)
             routers/inbound_receiving.py (inbound-specific ops)
             routers/outbound_picking.py (outbound-specific ops)
Schema:      schemas.py → WMSTaskCreate, ScannerScan
Components:  ScannerTaskPanel.jsx (generic)
             InboundScanInterface.jsx (inbound)
             OutboundScanInterface.jsx (outbound)
flow_type:   inbound | outbound
Status Inbound:
  waiting_goods → receiving → qc_check → completed | escalated
  [Depth #3a] QC Hold aktif (config.purchasing.qc_on_receipt=True, default):
    waiting_goods → receiving → qc_check → (complete) → qc_pending
      → (qc-decision) → completed | qc_rejected
Status Outbound:
  created → picking → packing → staging → dispatched | escalated
Key Fields:
  id, flow_type, source_type, product_id, product_name, sku,
  quantity, unit, warehouse_id, bin_id, batch, lot, roll_id,
  status, scanned_items: [{scan_value, scan_type, timestamp, actor}],
  source_document (PO id atau SO id), escalation_info, created_at
  [Depth #3a QC] quarantine_qty, qc_status (pending|passed|partial|rejected),
  qc_accept_qty, qc_reject_qty, qc_reject_disposition (damaged|return),
  qc_reason, qc_by, qc_at
  [FASE E] supplier_sku, supplier_item_name, supplier_item_id, expected_grade
           (penamaan versi supplier tampil berdampingan dengan nama KN saat penerimaan)
  [FASE F-1] supplier_uom, supplier_conv_factor    # satuan & faktor versi supplier
             last_receive_doc_uom                  # satuan terakhir yang dipakai operator
             receive_uom_trails: [{...uom_trail, scan_id, actor}]   # akumulasi jejak
             scan_log[].uom_trail: {doc_uom, doc_qty, doc_uom_label, task_uom, task_qty,
               base_uom, base_qty, factor, source, rule_id, path[], supplier_item_id,
               supplier_sku, supplier_item_name, supplier_uom, context, converted_at}
             source ∈ same_unit | supplier_item | fixed_uom | product_override |
                      global_rule | formula_gsm_width | hop_base
  Invarian FASE F-1: INV-RCV-01 jejak lengkap · INV-RCV-02 doc_qty×factor == task_qty ==
    scan_log[].actual_qty · INV-RCV-03 source sah + supplier_item_id hidup +
    receive_uom_trails sinkron dengan scan_log.
  Kebijakan (system_settings scope `receiving`, tanpa deploy):
    supplier_uom_input_mode (off|optional|prefer) · require_supplier_item_for_supplier_uom ·
    block_over_remaining        → services/receiving_uom_service.py
  ⚠️ JANGAN BUAT koleksi baru untuk jejak satuan penerimaan — jejak tinggal di dalam
     `wms_tasks` (scan_log[].uom_trail + receive_uom_trails[]).

⚠️ Depth #3a — QC Hold/Quarantine saat GR:
  • inbound_receiving.complete → roll dibuat status `quarantine` (BUKAN available)
    + roll.qc_task_id = task.id; task → `qc_pending`; TIDAK auto-fulfill.
  • Endpoints (routers/inbound_receiving.py + services/qc_service.py):
    GET  /api/inbound/qc/queue             — antrian qc_pending + quarantine_qty
    POST /api/inbound/tasks/{id}/qc-decision {accept_qty, reject_qty,
         reject_disposition: damaged|return, reason}
  • Accept → roll quarantine→available + auto_fulfill_backorders.
  • Reject damaged → roll quarantine→`damaged`.
  • Reject return  → roll quarantine→`returned_supplier` (keluar on_hand) +
    buat purchase_returns (Nota Debit, stock_adjusted=True, source=qc_reject).
  • SSOT: semua transisi level ROLL (split bila parsial) → rebuild_balance.

⚠️ SATU collection untuk inbound DAN outbound — dibedakan oleh flow_type
⚠️ JANGAN BUAT: inbound_tasks, outbound_tasks, receiving_tasks sebagai collection terpisah
```

### warehouse_transfers
```
Collection:  warehouse_transfers
Router:      routers/transfers.py
Schema:      schemas.py → TransferCreate, TransferApprove, TransferReject
Component:   TransferManagement.jsx
Status Lifecycle:
  draft → waiting_approval → approved → picking → staging → dispatched → received | rejected
Key Fields:
  id, transfer_number, source_warehouse_id, dest_warehouse_id,
  items: [{product_id, product_name, qty, unit, batch, lot, roll_id}],
  status, requested_by, approved_by, notes, created_at, updated_at
  [PROPOSED KN_15] + transfer_kind (intra_entity | inter_entity),
                     source_entity_id, dest_entity_id, transfer_price?, linked_order_id?

⚠️ [PROPOSED KN_15] Inter-company (beda entitas) = EXTEND koleksi ini (transfer_kind=inter_entity),
   BUKAN koleksi baru. Memicu ownership_transfer movement + (Fase 4) AR/AP antar entitas. Lihat KN_15 §7.
⚠️ JANGAN BUAT: transfers, stock_transfer, pemindahan_barang, inter_entity_transfers
```

### cycle_count_sessions
```
Collection:  cycle_count_sessions
Router:      routers/cycle_count.py
Component:   CycleCount.jsx
Status Lifecycle:  [FIX-10 — tabel transisi `services/cycle_count_state.py`, CAS + `status_history[]` SSOT]
  opname (item / mode roll): open → submitted → approved | approved_with_exceptions | rejected;
                             submitted|rejected → open (buka kembali); mode roll: open → approved[_with_exceptions]
  pendaftaran awal (mode=registration): draft → running → pending_approval → approved[_with_exceptions];
                             running → draft (kalah balapan mulai); pending_approval → running; draft|running|pending → rejected
  (status lama "in_progress" di dokumen ini tidak pernah ditulis kode)
  opname RFID = koleksi lain `rfid_verify_sessions` kind=cycle_count: open → completed (+ status_history)
Key Fields:
  id, session_number, warehouse_id, status, status_history[],
  items: [{id, product_id, expected_qty, actual_qty, variance, status}],
  submitted_by, approved_by, created_at

⚠️ Approval generate inventory_movements (cycle_count_adjustment)
⚠️ JANGAN BUAT: stock_count, physical_count, stock_opname
```

### purchase_orders
```
Collection:  purchase_orders
Router:      routers/purchase_orders.py
Schema:      schemas.py → PurchaseOrderCreate, POItemCreate, POReceiveItem
Component:   PurchaseOrderManagement.jsx
Status Lifecycle:
  [waiting_approval →] pending → receiving → completed | partial | cancelled
  (waiting_approval hanya jika total_amount memicu approval_rules; lihat Fase 1B)
Key Fields:
  id, po_number (format: PO-NNNNN), supplier_name, supplier_contact,
  warehouse_id, items: [{product_id, quantity, unit, price, subtotal, received_qty}],
  status, expected_delivery_date, notes, created_by, created_at, total_amount
  # Fase 1B — approval dinamis:
  approval_required bool   required_approval_role string|null
  approval_status enum(not_required|pending|approved)   approval_amount float   approved_by string
  # Depth #3 — guard penyimpangan harga:
  approval_reason string(amount_threshold|price_deviation|amount_threshold+price_deviation|"")
  price_deviation {flagged bool, threshold_pct, max_deviation_pct, items:[{sku,price,ref_price,unit,deviation_pct}]}
  last_received_at string|null   # Depth #3 — timestamp penerimaan (scorecard)
  # Setting terkait: settings.purchasing.price_deviation_approval_percent (default 10.0)
  grir_clearings[]   # PK-28 — kliring sisa GR/IR (lihat "Sisa GR/IR per PO …" di bagian penanda jurnal)

⚠️ Supplier adalah STRING saat ini — belum ada supplier master collection
⚠️ Supplier: gunakan FK `supplier_id` → suppliers.id (Fase 3). `supplier_name`/
   `supplier_npwp`/`supplier_contact` = SNAPSHOT saat PO dibuat (backward compat;
   PO lama tanpa supplier_id tetap valid via string).
⚠️ PO tanpa approval → langsung buat wms_tasks (inbound). PO butuh approval → wms_tasks
   dibuat HANYA setelah /purchase-orders/{id}/approve (role_satisfies dari approval_rules).
   /purchase-orders/{id}/reject → status 'rejected' (tanpa task).
⚠️ Depth 1A — status lifecycle: waiting_approval → pending → receiving → partial → completed
   (dihitung dari Σ received_qty vs quantity ± toleransi via recompute_po_status).
   /purchase-orders/{id}/close → 'closed_short' (tutup kurang; batalkan task terbuka).
⚠️ Depth 1C — keuangan/AP: field amount_paid, returned_amount, outstanding, payment_status
   (unpaid|partial|paid), payments[]. /purchase-orders/{id}/pay → cash_transaction(out,
   ref_type=purchase_order) + update AP. /purchase-orders/payables/summary → AP + aging.
⚠️ JANGAN BUAT: po, pembelian, supplier_orders, procurement
```

### makloons
```
Collection:  makloons          Prefix: mak_
Router:      routers/makloons.py
Schema:      schemas.py → MakloonCreate (PATCH via GenericPatch)
Component:   MakloonsView.jsx + Makloon360Panel.jsx (Pembelian → Master Pembelian → Mitra Makloon)
Scope:       SCOPED (entity_id) — mirror suppliers (bisa dipakai lintas-entitas)
Status:      active | inactive (soft delete via DELETE)
Key Fields:
  id, code, name, npwp, pic_name, phone, email, address, city,
  process_types [tenun|celup|printing|jahit|finishing|...], payment_term_code,
  lead_time_days, entity_id, notes, status, created_by, created_at, updated_at
Endpoints:   GET/POST /makloons · GET/PATCH/DELETE /makloons/{id}
             GET /makloons/{id}/scorecard   (metrik dari makloon_orders)
⚠️ Mitra subkontrak (bukan supplier beli-putus). JANGAN BUAT: subcon, subkontraktor, vendor_makloon
```

### process_recipes
```
Collection:  process_recipes   Prefix: prcp_
Router:      routers/process_recipes.py
Schema:      schemas.py → ProcessRecipeCreate (PATCH via GenericPatch)
Component:   ProcessRecipesView.jsx (Pembelian → Master Pembelian → Resep Proses)
Scope:       SCOPED (entity_id)
Status:      active | inactive
Key Fields:
  id, name, process_type, input_product_id, output_product_id, byproduct_product_id,
  input_unit, yield_factor, waste_pct, byproduct_pct, default_makloon_id,
  default_tariff, aux_cost_default, entity_id, notes, status, created_at, updated_at
Endpoints:   GET/POST /process-recipes · PATCH/DELETE /process-recipes/{id}
             POST /process-recipes/forecast   (hitung expected_output & byproduct)
⚠️ Rumus konversi bahan→output makloon. JANGAN BUAT: bom, recipe, formula, konversi_makloon
```

### makloon_orders
```
Collection:  makloon_orders    Prefix: mko_
Router:      routers/makloon_orders.py
Service:     services/makloon_order_service.py (create/issue/receive/cancel + costing + GL)
Schema:      payload dict (steps[]) — divalidasi di service
Component:   MakloonOrdersView.jsx, MakloonOrderCreateModal.jsx, MakloonOrderDetailPanel.jsx
             (Pembelian → Pesanan Pembelian → tab "Order Makloon"; dibuat via Mode Pengadaan
              "Raw Material & Proses" / "Proses Saja" pada tombol Buat di hub PO)
Scope:       SCOPED (entity_id). Respons list = ARRAY.
Status Lifecycle:
  draft → in_process → partially_received → completed | cancelled
Mode:        process_only (bahan dari stok) | buy_process (spawn PO bahan)
Key Fields:
  id, mko_number, mode, material_product_id, material_qty, material_unit,
  from_warehouse_id, target_warehouse_id, supplier_id, material_price,
  steps: [{process_type, makloon_id, recipe_id, input_product_id, output_product_id,
           byproduct_product_id, yield_factor, waste_pct, byproduct_pct, tariff,
           aux_cost, status, lots[]}],
  forecast {expected_finished_qty, ...}, final_output_name, timeline[],
  entity_id, status, created_by, created_at, updated_at
Endpoints:   GET/POST /makloon-orders · GET /makloon-orders/{id}
             POST /makloon-orders/{id}/issue     (kirim bahan → roll status subcon / WIP)
             POST /makloon-orders/{id}/receive   (terima output + barang sisa + costing/GL)
             POST /makloon-orders/{id}/cancel
GL:          akun WIP 1-1350 (WIP-at-Vendor); vendor bill per-step via vendor_bills.
⚠️ JANGAN BUAT: subcon_orders, order_subkontrak, makloon_transactions
```

### suppliers
```
Collection:  suppliers          Prefix: sup_
Router:      routers/suppliers.py
Schema:      schemas.py → SupplierCreate, SupplierPriceListCreate, GenericPatch
Component:   SuppliersView.jsx (Pembelian → Pemasok) + SupplierDetailPanel.jsx
Status:      active | inactive (soft delete via DELETE)
Key Fields:
  id, code (format: SUP-NNNNN), name, npwp, pic_name, phone, email, address,
  city, goods_type (jenis barang), payment_term_code, lead_time_days (Depth #3),
  entity_id, notes, status, created_by, created_at, updated_at
Endpoints:   GET/POST /suppliers · GET/PATCH/DELETE /suppliers/{id}
             # Depth #3 — Supplier Intelligence:
             GET /suppliers/{id}/scorecard       (metrik dari PO + penerimaan + retur)
⚠️ entity_id = default scoped (ent_ksc); supplier bisa dipakai lintas-entitas.
⚠️ JANGAN BUAT: vendor, vendors, pemasok
```

### supplier_price_lists
```
Collection:  supplier_price_lists   Prefix: spl_
Router:      routers/suppliers.py
Schema:      schemas.py → SupplierPriceListCreate (PATCH via GenericPatch)
Service:     services/supplier_service.py → resolve_price()
Component:   SupplierPriceList.jsx (tab di SupplierDetailPanel)
Status:      active | inactive (soft delete via DELETE)
Key Fields:
  id, supplier_id (FK → suppliers.id), supplier_name (snapshot),
  product_id (FK → products.id), sku, product_name (snapshot),
  price (per unit), unit (UOM; default base_unit produk — ikut UOM engine 1.13),
  min_qty (MOQ), lead_time_days (0=pakai default supplier),
  valid_from, valid_until ("" = open), currency (IDR), entity_id, notes,
  status, created_by, created_at, updated_at
Endpoints:   GET/POST /suppliers/{id}/price-list ·
             PATCH/DELETE /supplier-price-list/{entry_id} ·
             GET /supplier-price-list/resolve?supplier_id=&product_id=&qty=
Dipakai:     auto-isi harga di PO create + PR→PO convert (Depth #3).
⚠️ JANGAN BUAT: price_list, harga, vendor_prices
```

### cash_transactions
```
Collection:  cash_transactions  Prefix: cash_
Router:      routers/cash.py
Index:       uq_id · (ref_type, ref_id, direction) · kn_ref_journal_entry_id & kn_ref_parent_journal (parsial `$gt ""`,
             Kas & Bank 1 — `gl_service.kas_jurnal`)
Schema:      schemas.py → CashTransactionCreate
Component:   CashManagementView.jsx (Pembelian → Pengelolaan Kas)
cash_type:   kas_kecil | kas_besar (buku bank) — jenis BUKU, bukan kepemilikan (kas grup dihapus, E7.4)
direction:   in (masuk) | out (keluar)   ·   status: posted | void
Key Fields:
  id, number (format: CASH-NNNNN), cash_type, direction, amount, category,
  description, entity_id, ref_type, ref_id, txn_date, status, created_by,
  created_at, updated_at
Satu pembuat (PK-20 · SL-11, `02` §1 P5) — kas BARU hanya lahir dari `services/cash_ledger.create_cash` (penjaga
INV-CASH-01 `scripts/guardrails/verify_cash_single_door.py`); nomor hanya dari `cash_ledger.next_cash_number`:
  id                 string  tetap: `cash_` + 24 heksa pertama SHA-1 `ref_type|ref_id|direction|seq` (atau id turunan
                             pemanggil, mis. niat bayar PK-05 / kasus keuangan). Kejadian sesudah kas lama `void` →
                             `seq#2`, `#3`…  Unik: indeks `uq_id` (`indexes.ID_INDEX_COLLECTIONS`).
  ref_type, ref_id   string  WAJIB — dokumen induk. Kas manual: `ref_type="manual"`, `ref_id` = kunci idempotensi
                             permintaan (atau id baru); kas keluar manual dari pengajuan yang disetujui (Kas & Bank 2,
                             C6): `ref_id` = id `cash_out_requests` + `disetujui_oleh(_id)`, `disetujui_pada`,
                             `cash_out_request_number` (pembuat = pengaju). Indeks tidak unik (ref_type, ref_id, direction).
  sidik_kiriman      string  Kas & Bank 2 (C6) — kas manual langsung berkunci: sidik isi kiriman
                             (`cash_out_request_service.sidik_isian`); kiriman ulang kas keluar berkunci sama berisi lain
                             → 409, berisi sama → kas yang sama (bukan pengajuan di sampingnya).
  ai_card_id         string  AG-T5 — id kartu tindakan asisten (kas manual, bayar tagihan pemasok / kontrabon) yang
                             mencatat kas ini; tidak ada = dicatat di layar.
  seq                string  pembeda kas searah satu dokumen (id pembayaran landed cost, `out`/`in` antar-PT, langkah
                             kasus, `charge`/`holding` baris mutasi bank); kosong untuk satu kas per dokumen.
  account_id         string  WAJIB — id `bank_accounts` AKTIF milik `entity_id` (dikirim, atau rekening tunggal PT
                             untuk jenis kasnya). Tidak pernah berisi kode akun (dulu refund retur / gaji: kode akun).
  account_code       string  akun kas buku besar jurnalnya (1-1110 kas kecil · 1-1100 bank), dari jenis rekening.
  cash_type                  diturunkan dari rekening (`bank_service.account_cash_type`), bukan dari pemanggil.
  entity_id          string  PT dokumen induk; tidak pernah "all".
  gl_status          string  pending (baru lahir) → posted | failed | not_required (`gl_posted: true` — dijurnal
                             dokumen induk: nota kredit/nota debit/gaji/antar-PT; `parent_journal` = id/rujukan
                             jurnal induk). Jurnal kas gagal → kas TETAP tersimpan `failed` (panel Posting Gagal).
  void_gl_status     string  hasil jurnal pembalik saat kas dibatalkan (batal kas manual, lepas biaya bank,
                             batal titipan) lewat `gl_service.post_durable`.
  Kas lama tanpa rekening / berkode akun di `account_id` TIDAK dimigrasi (paket perbaikan data, H3).
  counterparty_name  string  PM-T3 — kas kwitansi: nama pelanggan (bahan skor nama rekonsiliasi); `reference_no` =
                             nomor referensi kwitansi; `description` memuat nomor referensi dan kode bayar pesanan
                             yang dialokasi ("Penerimaan AR-… — {pelanggan} · Ref … · Kode KN-…").
Rekonsiliasi bank (PK-21, satu pemilik — `02` D1):
  reconciled_amount  float   PEMILIK: hanya services/bank_recon_service.py (`_link`, `_unlink`, titipan,
                             biaya bank). = Σ allocations[].amount baris bank_statement_lines `matched` yang
                             menunjuk transaksi ini + `amount` bila ia kas titipan baris `holding`.
  reconciled         bool    TURUNAN = reconciled_amount ≥ amount − 0,01 (dan > 0). Tidak pernah ditulis
                             sendirian; pembaca memakai `txn_reconciled()` (tanda manual lama tidak dipercaya).
  matched_line_ids[] string  TURUNAN = id baris yang masuk hitungan di atas (matched_line_id bila tepat satu).
  reconciled_at      string  kosong bila tidak penuh.
  Pembangun ulang: `bank_recon_service.rebuild_reconciled(txn_id)` (skrip perbaikan/uji). Invarian: INV-BNK-02.
  Batal kas ditahan hanya bila reconciled_amount > 0 (cash.py, vendor_bills.py, marketing_cost_service.py).
Endpoints:   GET /cash-transactions · GET /cash-transactions/summary ·
             POST /cash-transactions · POST /cash-transactions/{id}/void ·
             POST /cash-transactions/{id}/reconcile → 410 (PK-21)
Invarian:    saldo = Σ(amount where direction=in) − Σ(amount where direction=out)
             untuk status≠void.
⚠️ JANGAN BUAT: kas, petty_cash, cash
```

### purchase_returns
```
Collection:  purchase_returns  Prefix: pret_
Router:      routers/purchase_returns.py · Service: services/purchase_return_service.py
Schema:      schemas.py → PurchaseReturnCreate, PurchaseReturnItem, PurchaseReturnDecision
Component:   PurchaseReturns.jsx (Pembelian → Retur Beli)
Status:      draft → pending_approval → approved | rejected
Key Fields:
  id, number (PRET-NNNNN), supplier_id, supplier_name, po_id, po_number,
  warehouse_id, warehouse_name, entity_id, items[{product_id, sku, product_name,
  quantity, unit, price, subtotal, reason, condition}], total_amount, reason,
  status, debit_note_number (DN-NNNNN saat approved), stock_adjusted,
  ap_basis (gr_ir|hutang|kas — PK-28: akun yang didebit jurnal retur),
  created_by, approved_by, rejected_by, ...
Endpoints:   GET/POST /purchase-returns · GET /purchase-returns/{id} ·
             POST /{id}/submit · /{id}/approve · /{id}/reject
Efek approve: KURANGI inventory_rolls available (FIFO, status→returned_supplier),
             movement return_out, terbitkan Nota Debit, KURANGI AP (PO.returned_amount).
PK-27:       (IV-06) nilai buku roll yang keluar, potret ditulis SEKALI bersama `stock_adjusted: true` (`02` D3):
             `book_value` = Σ (panjang diretur × biaya roll) dalam sen → rupiah 2 desimal;
             `book_value_rolls[{roll_id, qty, unit_cost, value}]`; sesudah jurnal: `book_value_diff` (nilai buku −
             nilai nota tanpa PPN) dan `book_value_posted` (selisih nol, atau jurnal memuat baris
             `retur.selisih_retur_beli`). Jurnal: Cr persediaan = nilai buku + baris selisih bila kunci
             `retur.selisih_retur_beli` terpetakan untuk PT; belum terpetakan / retur lama tanpa `book_value` =
             jurnal lama (Cr persediaan = nilai nota tanpa PPN).
⚠️ JANGAN BUAT: retur_beli, debit_notes, po_returns, vendor_returns
```

### purchase_requisitions
```
Collection:  purchase_requisitions  Prefix: pr_
Router:      routers/purchase_requisitions.py · Service: services/purchase_requisition_service.py
Schema:      schemas.py → PurchaseRequisitionCreate, PurchaseRequisitionItem,
             PurchaseRequisitionDecision, PurchaseRequisitionConvert, SpecialOrderToPR
Component:   PurchaseRequisitions.jsx, ReorderSuggestions.jsx (Pembelian)
Status:      draft → pending_approval → approved → converted | rejected | cancelled
Key Fields:
  id, number (PR-NNNNN), entity_id, warehouse_id, warehouse_name,
  items[{product_id (opsional), sku, product_name, description, quantity, unit,
  est_price, subtotal, note, base_unit, quantity_base, uom_trail{...} ← FASE B/D-07}],
  total_est_amount,
  source (manual|reorder|special_order|**so_repeat** ← PS-21 repeat/restock dari SO),
  source_ref_id, preferred_supplier_id, preferred_supplier_name, reason,
  needed_by_date, status, approval_required, required_approval_role, approval_status,
  po_id, po_number (saat converted), created_by, approved_by, rejected_by, ...
Endpoints:   GET/POST /purchase-requisitions · GET /purchase-requisitions/{id} ·
             GET /purchase-requisitions/reorder-suggestions ·
             POST /{id}/submit · /{id}/approve · /{id}/reject · /{id}/cancel ·
             POST /{id}/convert-to-po · POST /special-orders/{id}/create-pr (jembatan OD)
             POST /sales-orders/{id}/repeat-restock (PS-21 — 1 klik SO → PR + notifikasi MD) ·
             GET  /sales-orders/{id}/restock-state (kandidat restock + pendingan + PR terkait)
             Service PS-21: services/restock_service.py · Component: features/orders/RestockPanel.jsx
Depth #2a:   PR → approval (matriks 'purchase_requisition') → konversi ke PO (catalog only)
Depth #2b:   reorder-suggestions berbasis products.reorder_point/reorder_qty + on_order (anti double-order)
Depth #2c:   jembatan Special Order → PR (item non-katalog) + on_order/ATP (status_board)
⚠️ JANGAN BUAT: requisitions, pr_list, permintaan_pembelian, material_requests
```

### vendor_bills  [Fase 5.2 P0-2 IMPLEMENTED — Vendor Bill + 3-Way Matching]
```
Collection:  vendor_bills      Prefix: vbill_
Router:      routers/vendor_bills.py · Service: services/vendor_bill_service.py
Schema:      schemas.py → VendorBillCreate, VendorBillItemInput,
             VendorBillPaymentCreate, VendorBillDecision
Component:   VendorBillsView.jsx (Pembelian → Tagihan Supplier) +
             VendorBillCreateModal.jsx + VendorBillDetailPanel.jsx
Status:      draft → pending_approval → posted → paid (+ cancelled)
Key Fields:
  id, bill_number (VB-NNNNN), supplier_invoice_no (dedupe per supplier),
  po_id, po_number, supplier_id, supplier_name, supplier_npwp,
  warehouse_id, warehouse_name, entity_id, bill_date, due_date,
  match_mode (received|ordered),
  items[{product_id, sku, product_name, unit, billed_qty, quantity(=billed_qty),
    price, po_price, discount_percent, discount_amount, subtotal, line_total,
    ordered_qty, received_qty, already_billed_qty, remaining_qty,
    match{qty_status, price_status, price_variance_pct, messages[]}}],
  total_amount (GROSS Σ subtotal), items_discount_total, order_discount_percent,
  order_discount_amount, discount_total, net_subtotal, dpp, ppn_rate, ppn_mode,
  is_pkp, ppn_amount, grand_total, tax_mode,
  match_status (matched|warning|blocked), match_exceptions[], within_tolerance,
  approval_required, required_approval_role, approval_status, approved_by,
  amount_paid, outstanding, payment_status (unpaid|partial|paid), payments[],
  grir_amount, price_variance_amount, price_variance_posted   # PK-28 — nilai GR/IR & selisih harga terhadap PO
  timeline[], created_by, created_by_id, created_at, updated_at
Endpoints:   GET/POST /vendor-bills · GET /vendor-bills/{id} ·
             GET /vendor-bills/payables/summary ·
             GET /purchase-orders/{id}/billing-context ·
             POST /vendor-bills/{id}/submit · /{id}/approve · /{id}/reject ·
             POST /vendor-bills/{id}/pay · /{id}/cancel
3-Way Match: PO (ordered) ↔ GR (received_qty) ↔ Bill (billed_qty). Toleransi
             settings.purchasing.bill_qty_tolerance_percent (default 0) &
             bill_price_tolerance_percent (default 5). blocked = over-billing di
             luar toleransi (tak bisa submit). warning = variance dalam toleransi
             (butuh approval manager). matched = bersih (auto-post).
Efek post:   AP berbasis bill. sync_po_billing() update PO.billed_total/unbilled_total.
Pay:         cash_transaction(out, ref_type=vendor_bill) + update AP bill.
⚠️ JANGAN BUAT: bills, tagihan, vendor_invoice, ap_bills, supplier_bills, vendor_invoices
```

### landed_cost_vouchers  [Fase 5.4 P0-5 IMPLEMENTED — Landed Cost → alokasi HPP roll]
```
Collection:  landed_cost_vouchers   Prefix: lcv_
Router:      routers/landed_cost.py · Service: services/landed_cost_service.py
Schema:      schemas.py → LandedCostCreate, LandedCostLineInput,
             LandedCostPaymentCreate, LandedCostDecision
Component:   LandedCostView.jsx (Pembelian → Landed Cost) +
             LandedCostCreateModal.jsx + LandedCostDetailPanel.jsx
Status:      draft → pending_approval → applied → paid (+ cancelled)
Key Fields:
  id, voucher_number (LCV-NNNNN), provider_name, supplier_invoice_no (dedupe),
  po_ids[], po_numbers[], entity_id,
  basis (value|quantity), effective_basis,
  cost_lines[{category(freight|duty|insurance|handling|other), description, amount}],
  total_cost, voucher_date, due_date, target_roll_count,
  allocation_preview[{… , treatment}], allocations[{roll_id, roll_no, product_id, length, weight,
    base_unit_cost, current_unit_cost, alloc_amount, per_unit, new_unit_cost,
    treatment, capitalized_amount}],
  capitalization{inventory_amount, wip_amount, expensed_amount, expensed_to, computed_at},
  approval_required(true), required_approval_role(manager), approval_status,
  approved_by, approved_at, applied_at,
  amount_paid, payment_status (n/a|unpaid|partial|paid), payments[],
  timeline[], created_by, created_by_id, created_at, updated_at
Endpoints:   GET/POST /landed-costs · GET /landed-costs/{id} ·
             GET /landed-costs/payables/summary ·
             GET /purchase-orders/{id}/landed-cost-context ·
             POST /landed-costs/{id}/submit · /{id}/approve · /{id}/reject ·
             POST /landed-costs/{id}/pay · /{id}/cancel
Alokasi:     biaya total dibagi ke roll (acquired.ref_id ∈ po_ids). Basis value =
             base_unit_cost × length; quantity = length. Fallback value→quantity bila
             Σbobot=0; lalu bagi rata. Σalloc == total_cost (sisa pembulatan ke roll akhir).
Efek apply:  HANYA saat APPROVE (manager+, SoD pembuat≠approver, idempotent via status).
             roll.unit_cost += per_unit (additive); roll.landed_cost_total += alloc;
             roll.landed_cost_refs += voucher_number.
PK-26:       (IV-01, K-05) golongan roll saat disetujui → `allocations[].treatment`:
             `persediaan` (status lain) · `wip` (`subcon`) · `keluar` (`in_transit_sales`, `delivered`,
             `returned_supplier`, `in_transit_intercompany`). `allocations[].capitalized_amount` = kenaikan nilai
             roll itu (sisa × per_unit dalam sen; 0 untuk `keluar`). `capitalization` (wajib saat `applied`,
             ditulis bersama status, tidak dihitung ulang — 02 D3): `inventory_amount` (Dr persediaan),
             `wip_amount` (Dr WIP makloon), `expensed_amount` (sisa = roll keluar + bagian roll yang sudah susut +
             pembulatan; Dr HPP bila `expensed_to="hpp"`, Dr `pembelian.landed_cost` bila `varians` — pengaturan
             `inventory.landed_cost_porsi_terjual` PT voucher); jumlah ketiganya = `allocated_total` = Cr hutang.
             `allocation_preview[].treatment` hanya tampilan (dihitung saat dibuat). Voucher lama tanpa
             `capitalization`: jurnal & ulang posting seperti dulu (seluruhnya Dr persediaan). Tanpa migrasi.
Pay:         cash_transaction(out, ref_type=landed_cost) (opsional, setelah applied).
⚠️ JANGAN BUAT: landed_costs, import_costs, freight_vouchers, biaya_impor, hpp_adjustments
```

### tax_invoices_in  [Fase 5.5 P0-3 IMPLEMENTED — Faktur Pajak Masukan / Input VAT]
```
Collection:  tax_invoices_in   Prefix: fpm_   (No. internal FPM-NNNNN)
Router:      routers/input_tax.py · Service: services/input_tax_service.py
Schema:      schemas.py → InputTaxInvoiceCreate, InputTaxInvoiceCancel
Component:   InputTaxView.jsx (Pembelian → Faktur Pajak Masukan) + InputTaxCreateModal.jsx
Status:      recorded → cancelled
Sumber:      Vendor Bill (status posted|paid, ppn_amount>0). DPP/PPN/supplier disalin dari bill.
Key Fields:
  id, number (FPM-NNNNN), nsfp (NSFP supplier), nsfp_digits (dedupe key), kode_transaksi,
  status (recorded|cancelled), faktur_date, period (YYYY-MM),
  vendor_bill_id, bill_number, supplier_invoice_no, po_id, po_number,
  supplier_id, supplier_name, supplier_npwp, entity_id,
  dpp, ppn_rate, ppn_mode, ppn_amount, grand_total,
  notes, timeline[], cancel_reason, cancelled_by, cancelled_at,
  created_by, created_by_id, created_at, updated_at,
  active_key (PK-40: hanya status=recorded — `vb:{vendor_bill_id}` / `ic:{interco_pair_id}`), nsfp_key (= nsfp_digits)
Dedupe:      NSFP (digit-only) unik di antara faktur status=recorded → 409 bila ganda.
             1 Vendor Bill → max 1 faktur masukan aktif (vendor_bills.input_faktur_status).
             PK-40: dijamin indeks unik wajib `uq_fpm_active`, `uq_fpm_nsfp` (`kunci_aktif_masukan`); indeks biasa
             (entity_id, faktur_date) untuk rekap per masa.
Endpoints:   GET/POST /input-tax-invoices · GET /input-tax-invoices/{id} ·
             GET /input-tax-invoices/eligible-bills · POST /input-tax-invoices/{id}/cancel ·
             GET /tax/vat-summary?period=YYYY-MM (Rekap PPN Masukan vs Keluaran)
Rekap PPN:   /tax/vat-summary → keluaran (tax_invoices aktif: bukan batal & belum diganti) vs masukan
             (tax_invoices_in, status=recorded) per period; net = keluaran−masukan →
             >0 kurang_bayar (setor), <0 lebih_bayar (kredit), =0 nihil.
             PK-40: masa = periode WIB `faktur_date` (saringan di kueri, tanpa batas 5.000 baris); keluaran/masukan
             memuat `gl_ppn` (mutasi akun PPN keluaran/masukan buku besar masa itu) + `selisih` (rekap − buku besar).
Efek:        create → vendor_bills.input_faktur_id/number/status='recorded'/nsfp.
             cancel → unset flag bill (eligible lagi), NSFP bisa dipakai ulang.
⚠️ JANGAN BUAT: faktur_masukan, input_vat, ppn_masukan, vat_in, purchase_tax_invoices
```

### rfqs  [Fase 6.1 P1 IMPLEMENTED — RFQ / Quotation (sourcing)]
```
Collection:  rfqs   Prefix: rfq_   (No. RFQ-NNNNN)
Router:      routers/rfq.py · Service: services/rfq_service.py
Schema:      schemas.py → RFQCreate, RFQItemInput, RFQQuoteSubmit, RFQQuoteLine, RFQAward, RFQLineAward, RFQDecision
Component:   RFQView.jsx (Pembelian → RFQ / Quotation) + RFQCreateModal.jsx + RFQDetailPanel.jsx
Status:      draft → open → awarded | cancelled
Sumber:      PR approved (tarik item) | manual (pilih produk). Undang N supplier.
Key Fields:
  id, rfq_number (RFQ-NNNNN), title, entity_id, source ("manual"|"pr"), pr_id, pr_number,
  warehouse_id, warehouse_name, status, needed_by_date, due_date, notes,
  items[] { line_id, product_id, sku, product_name, quantity, unit, note },
  suppliers[] { supplier_id, supplier_name, quote_status ("pending"|"quoted"), quoted_at,
                valid_until, lead_time_days, note, lines[]{line_id,price,available,note}, total },
  award { mode ("full"|"line"), full_supplier_id, line_awards[]{line_id,supplier_id,price},
          po_ids[], po_numbers[], awarded_by, awarded_at },
  timeline[], created_by, created_by_id, created_at, updated_at
Endpoints:   GET/POST /rfqs · GET /rfqs/{id} · GET /rfqs/{id}/compare ·
             POST /rfqs/{id}/send · POST /rfqs/{id}/quote · POST /rfqs/{id}/award ·
             POST /rfqs/{id}/cancel
Compare:     matriks item×supplier + lowest_per_line + total/supplier + recommended_full +
             recommended_line_awards (harga termurah per baris).
Award:       FULL (1 supplier → 1 PO) | LINE (split → 1 PO per supplier). Reuse pricing P0-1
             (compute_order_pricing) + approval threshold + inbound tasks. PO.source_rfq_id/number.
             Upsert supplier_price_lists dari harga pemenang (source=rfq_award, min_qty=0).
             Bila pr_id → PR.status='converted', po_id=PO pertama.
⚠️ JANGAN BUAT: quotations, tenders, bid_requests, penawaran, request_for_quote
```

### document_templates
```
Collection:  document_templates
Router:      routers/documents.py
Schema:      schemas.py → TemplatePayload
Component:   DocumentsView.jsx, AdminView.jsx (tab Templates)
document_type: surat_jalan | invoice
Key Fields:
  id, document_type, name, header, footer, columns, logo_url,
  paper_size, orientation, margin_mm, signature_left, signature_right,
  section_order, status, created_by, created_at

⚠️ JANGAN BUAT: templates, print_templates, doc_config
```

### generated_documents
```
Collection:  generated_documents
Router:      routers/documents.py
Schema:      schemas.py → DocumentGenerate
Key Fields:
  id, document_type, source_id (order_id atau po_id),
  html_content, generated_by, generated_at

⚠️ Dokumen disimpan sebagai HTML string untuk print
```

### permission_settings
```
Collection:  permission_settings
Router:      routers/admin.py
Schema:      schemas.py → PermissionUpdate
Component:   AdminView.jsx (tab Permissions)
Struktur:    {id: "default", matrix: {role: {module: [actions]}}}
Field lain:  hidden_views {role: [nav id]}, cross_entity {role: bool},
             assignable_roles {<id peran pengelola>: [<id peran>]} — PR-T1: peran yang akunnya boleh dikelola
             pemegang peran pengelola (buat/ubah/reset sandi/nonaktifkan/cabut sesi). Tanpa kunci = tidak boleh
             mengelola akun siapa pun. `admin` tidak pernah disimpan sebagai isi; Admin selalu boleh semua.
             Hanya Admin yang mengubahnya (`PATCH /api/access/roles/{rid}` field `assignable_roles`).
             defaults_applied {role: {resource: [actions]}} — aksi bawaan yang sudah pernah ditambahkan
             `sync_permission_modules` (pencabutan Admin tidak dihidupkan lagi).
             migrations_applied [id] — PR-T9: id butir `bootstrap.PERMISSION_MIGRATIONS` (cabut/atur ulang izin
             SEKALI-JALAN) yang sudah dijalankan; butir yang id-nya ada tidak dijalankan lagi. Tidak ada field =
             belum dicatat → garis dasar `ensure_permission_ledger` mencatat semua butir lama tanpa mengubah matrix.
             role_traits {<id peran>: {data_scope?, home_view?, kategori_kerja?, notify_like?}} — PR-T4: sifat peran
             (bawaan & kustom) yang DISIMPAN Admin di Peran & Hak Akses › Sifat peran. `data_scope` ∈ milik_sendiri ·
             tim · semua; `home_view` ∈ `role_registry.HOME_CHOICES`; `kategori_kerja` ∈ "" · sales · sopir ·
             desainer · gudang · pengawas; `notify_like` = daftar id peran bawaan. Kunci yang tidak ada = nilai
             turunan (peran bawaan → bawaan sistem; kustom → efektif peran dasarnya). Diterapkan ke registry oleh
             `role_registry.apply_traits` (`custom_role_service.sync_registry`). Migrasi sekali `prt4:sifat-peran`
             (peran kustom tanpa peran dasar yang hanya memegang `design_request.view` → `data_scope: milik_sendiri`)
             dan `prt4:izin-kpi-sales` (`order.view_sales_kpi` untuk peran yang dulu melihat KPI sales lain lewat nama).

⚠️ Hanya ADA 1 document dengan id="default"
⚠️ Izin peran bawaan TIDAK lagi ditimpa saat start (PR-T9); bawaan tunggal = permissions_config.DEFAULT_PERMISSIONS
⚠️ KF-T1 — penanda migrasi sekali-jalan `system_settings{scope:"__migrations__"}.kft1_izin_pengaturan`: peran
   kustom ber-base_role manager menerima rnd.manage, inventory.configure, goods_receipt.configure, makloon.configure
   (pengganti jalur nama peran `roles=("manager",)` di Pusat Pengaturan). Pencabutan Admin sesudahnya bertahan.
```

### custom_roles
```
Collection:  custom_roles
Router:      routers/access_roles.py
Service:     services/custom_role_service.py
Component:   RoleAccessPanel.jsx / RoleEditorDrawer.jsx (tab Peran & Hak Akses)
Key Fields:
  id (cr_*), label, description, base_role, levels {module: level}, created_at, updated_at,
  pending_defaults {resource: [actions]} — PR-T9: izin BARU peran dasar yang belum diikuti peran ini karena
    modulnya pernah diubah; diikuti lewat `POST /api/access/roles/{rid}/follow-base`
Izin efektif peran kustom ada di permission_settings.matrix[id], bukan di dokumen ini.
⚠️ Fallback: DEFAULT_PERMISSIONS dari permissions_config.py
```

### audit_logs
```
Collection:  audit_logs
Router:      routers/audit.py (read-only list)
Ditulis:     dependencies.py → audit() helper
Component:   AdminView.jsx (tab Audit)
Key Fields:
  id, actor (user name), role, action, entity_type, entity_id,
  before, after, reason, timestamp

⚠️ APPEND-ONLY — tidak pernah update atau delete
⚠️ Gunakan audit() helper dari dependencies.py, BUKAN insert langsung
```

### user_onboarding
```
Collection:  user_onboarding
Router:      routers/onboarding.py
Component:   OnboardingPanel.jsx
Key Fields:
  id (= user_id), tasks: [{id, title, completed, completed_at}]

⚠️ Satu document per user
```

---

<!-- Discovery module (koleksi discovery_sessions/answers/attachments) dihapus 2026-06-17 — fitur assessment online-form. -->



---

## 🚨 FORBIDDEN — NAMA YANG PERNAH MENYEBABKAN DUPLIKAT

Jangan pernah buat collection atau schema dengan nama berikut
(karena sudah ada atau sudah pernah jadi sumber duplikat):

```
❌ items           → gunakan products
❌ goods           → gunakan products
❌ materials       → gunakan products
❌ accessories     → gunakan products
❌ kain            → gunakan products
❌ stock           → gunakan inventory_balances
❌ stok            → gunakan inventory_balances
❌ stock_levels    → gunakan inventory_balances
❌ orders          → gunakan sales_orders
❌ customer_orders → gunakan sales_orders
❌ penjualan       → gunakan sales_orders
❌ inbound_tasks   → gunakan wms_tasks (flow_type=inbound)
❌ outbound_tasks  → gunakan wms_tasks (flow_type=outbound)
❌ receiving_tasks → gunakan wms_tasks (flow_type=inbound)
❌ transfers       → gunakan warehouse_transfers
❌ stock_transfer  → gunakan warehouse_transfers
❌ po              → gunakan purchase_orders
❌ pembelian       → gunakan purchase_orders
❌ bills           → gunakan invoices
❌ tagihan         → gunakan invoices
❌ templates       → gunakan document_templates
❌ staff           → gunakan users
❌ operator        → gunakan users
❌ gudang          → gunakan warehouses
❌ depot           → gunakan warehouses
```

---

## 📐 BASE SCHEMA TEMPLATE

Setiap document baru WAJIB punya field-field ini:
```python
{
    "id":           new_id("prefix"),   # dari core_utils.new_id()
    "created_at":   now_iso(),           # dari core_utils.now_iso()
    "updated_at":   now_iso(),
    "created_by":   user["id"],          # dari token auth
    "created_by_name": user["name"],    # snapshot
    # ... business fields
}
```

Prefix ID yang sudah digunakan:
```
user_   → users
sess_   → sessions
prod_   → products
cust_   → customers
wh_     → warehouses
uom_    → uoms
so_     → sales_orders
bal_    → inventory_balances
roll_   → inventory_rolls            [Fase 0.5 IMPLEMENTED]
mov_    → inventory_movements
wms_    → wms_tasks
trf_    → warehouse_transfers
cc_     → cycle_count_sessions
po_     → purchase_orders
tmpl_   → document_templates
doc_    → generated_documents
inv_    → invoices
audit_  → audit_logs
addr_   → customer addresses (embedded)
ent_    → business_entities         [Fase 0 IMPLEMENTED]
ntf_    → notifications             [Fase 0 IMPLEMENTED]
set_    → system_settings           [Fase 1A IMPLEMENTED]
pterm_  → payment_terms             [Fase 1A IMPLEMENTED]
pmeth_  → payment_methods           [PM-T1]
bac_    → bank_account_changes      [PM-T1]
ccp_    → customer_credit_profiles  [CR-T1]
cpr_    → credit_profile_requests   [CR-T1]
cmpr_   → commission_period_rules   [KA-6]
cmsb_   → commission_carry_balances [BTP-5]
cgr_    → credit_gate_rejections    [CR-T3]
aiact_  → ai_action_proposals       [AG-T1]
pyc_    → payment_codes             [PM-T2]
bgh_    → budget_history            [PK-39]
aprule_ → approval_rules            [Fase 1A IMPLEMENTED]
```
> Prefix PLANNED (lihat bagian PLANNED ENTITIES): `pra_` price_approvals (= "special price"),
> `sord_` special_orders, `bank_` bank_accounts, `cpl_` customer_price_lists, `sret_` sales_returns, `fkt_` tax_invoices.

---

## 🆕 PLANNED ENTITIES (IA KN_14 — belum diimplementasi)

> **Sumber:** `KN_14_INFORMATION_ARCHITECTURE.md`. Entitas berikut **direncanakan**
> per fase roadmap. Didaftarkan di sini lebih dulu (Navigation-First + SSOT) agar
> tidak terjadi duplikat/drift saat coding. Status: **[PLANNED]** — belum ada di DB/kode.
> Saat diimplementasi: pindahkan ke bagian DETAIL di atas + daftarkan ke `verify_contract.py`.

### Lapis Fundamental — Multi-Entity  (✅ IMPLEMENTED Fase 0)
```
Collection: business_entities            Prefix: ent_    Fase 0  [IMPLEMENTED]
  id, legal_name, short_name, type(PT|CV), npwp, address, city,
  default_tax_mode(ppn|non_ppn), doc_prefix, logo_url, status, created_at, updated_at
  is_group            bool    PT induk grup: tidak ikut dijumlahkan sebagai baris konsolidasi / pilihan PT tutup buku
  ownership_pct       float   KP-T1 (K-10) — persen kepemilikan grup atas PT, > 0 dan ≤ 100 (2 desimal), bawaan 100.
                              Belum dibaca hitungan (PK-31). Diisi untuk data lama: scripts/migrate_kpt1_profil_pt.py
  tax_status_history  list    KP-T1 — riwayat ubah status PKP (hanya ditambah):
                              {from, to, effective_date YYYY-MM-DD, reason, by, by_id, at[, scheduled_at]}
  tax_status_pending  obj?    KP-T1 — perubahan status PKP bertanggal berlaku maju:
                              {to, effective_date, reason, by, by_id, at}; diterapkan job `entity_tax_status_due`
  provisioning        obj?    KP-T2 — langkah penyiapan awal yang sudah berhasil:
                              {coa: bool, config_layer: bool, group_partners: bool, at: iso}. Ditulis saat PT dibuat
                              (bagan akun bersama dipastikan SEBELUM PT disimpan → {coa: true, …}) dan oleh
                              POST /api/entities/{id}/provisioning/retry (izin entity.update; tiap langkah aman diulang).
                              Hanya catatan: butir kesiapan "Penyiapan awal" dihitung dari DATA (gl_accounts bersama > 0
                              + system_settings{scope: id}), jadi PT lama tanpa field ini tetap terbaca. Tanpa migrasi.
  print_name          str?    KP-T6 — nama yang dicetak di kop surat bila berbeda dari nama legal; kosong = legal_name.
                              Nama legal tetap dipakai faktur pajak & dokumen hukum.
  tagline             str?    KP-T6 — slogan di bawah nama pada kop surat
  website             str?    KP-T6 — situs web di kop surat
                              (phone, email, npwp, address + city juga dibaca kop: Profil PT = satu sumber identitas kop,
                              `pdf_service.get_branding`; dulu teks terpisah di document_branding)
  ⚠️ default_tax_mode TETAP nilai yang dibaca mesin (K-08); diubah HANYA lewat POST /api/entities/{id}/tax-status
     (PATCH ditolak 400). Tanpa indeks baru.
  ⚠️ KP-T1 — TIDAK DIPAKAI LAGI (tidak dibaca, ditulis, atau dikirim; field lama di dokumen tidak dihapus):
     numbering_scheme (→ tabel Penomoran Dokumen, KP-T5) · incentive_payer (→ commission.*) ·
     coa_template (→ bagan akun bersama gl_service.seed_default_coa) · parent_entity_id (→ is_group + ownership_pct) ·
     fiscal_year_start (→ registry finance.fiscal_year_end_month, lapisan PT) ·
     currency (→ registry finance.base_currency, lapisan PT; jawaban API `currency` = nilai registry)
⚠️ entity_id (FK) ditambahkan ke koleksi TRANSAKSI (scoped): sales_orders, invoices,
   tax_invoices, purchase_orders, cash_transactions, journal_entries, bank_accounts,
   tax_records, fiscal_periods, price_approvals, sales_returns, special_orders.
   Master SHARED (products, warehouses, uoms, document_templates) TIDAK wajib entity_id.
   customers & suppliers = default scoped (opsi shared). JANGAN buat: tenant, company.
```

#### 🔒 FASE E-0 — REGISTRY CAKUPAN ENTITAS DIRAPIKAN (2026-08-10)
`backend/entity_scope.py` adalah **satu-satunya** sumber kebenaran cakupan entitas.
Sebelum FASE E-0 ada **18 koleksi ber-`entity_id` yang tidak terdaftar** (bukan SCOPED,
bukan SHARED) sehingga lolos dari gate kepatuhan dan bocor lintas badan usaha.

**Ditambahkan ke `SCOPED_COLLECTIONS`** (keputusan per koleksi, eksplisit):
`notifications` · `audit_logs` · `payment_plans` · `payment_variance_decisions` ·
`penalties` · `sales_targets` · `sales_incentives` · `warehouse_transfers` ·
`purchase_returns` · `credit_notes` · `budgets` · `fin_budget_rules` ·
`approval_rules` · `cycle_count_sessions` · `supplier_price_lists` · `rfid_tags` ·
`rfid_reads` · `rnd_person_divisions` · `landed_cost_vouchers`.

**Field entitas non-standar** (`SCOPE_FIELD`):
| Koleksi | Field | Alasan |
|---|---|---|
| `inventory_rolls` / `balances` / `movements` / `lots` | `owner_entity_id` | semantik KEPEMILIKAN (dukung konsinyasi) |
| `rfid_tags`, `rfid_reads` | `owner_entity_id` | mengikuti kepemilikan roll |
| `audit_logs` | **`scope_entity_id`** | `audit_logs.entity_id` SUDAH lama berarti **id sumber daya** (mis. `so_001`), bukan badan usaha. Menimpanya akan merusak arti kolom lama. |

**Drift nama koleksi yang dibetulkan:**
- `input_tax_invoices` → **`tax_invoices_in`** (koleksi nyata di DB; nama lama tak pernah ada).
- `landed_costs` → koleksi nyata **`landed_cost_vouchers`** (nama lama dipertahankan sebagai alias).

**`INHERITED_GLOBAL_VALUES`** — koleksi yang SAH punya baris global dan WAJIB dibaca
dengan `resolve_list_scope_inherit()` supaya baris global tidak hilang dari layar:
`notifications` (`None`) · `audit_logs` (`None`) · `incentive_rates` (`"all"`) ·
`approval_rules` (`"all"`) · `cash_transactions` (`"all"`) · `bank_accounts` (`"all"`).

**Helper baru di `entity_scope.py`:**
`resolve_list_scope_inherit()` · `scope_value()` (nilai siap-pakai `str`/`{"$in":[…]}`) ·
`assert_write_entity()` (pagar mode “Semua Entitas” = hanya-baca) ·
`resolve_requested_entity()` (payload boleh menyebut entitas, **wajib** ∈ allowed → tutup L21) ·
`guard_party()` / `doc_parties()` (PK-09 — penjaga pihak dokumen antar-PT) · `resolve_write_entity()` (PK-09 — tulis:
`all` → 400, di luar penugasan → 403).

**Pagar anti-regresi:** `scripts/audit_entity_isolation.py` (masuk `scripts/gate.sh`) —
sapuan 301 endpoint GET × 2 sales beda entitas + IDOR 15 endpoint by-id + 3 pemeriksaan
statik registry. POC bukti-merah: `backend/test_core_e0_isolation_poc.py` (83 assert).
Migrasi data: `scripts/fix_orphan_entity_refs.py`.

**Izin baru (`permissions_config.py`):** `audit: [view]` (admin saja — dulu jejak audit
digerbang `product.view` sehingga sales & gudang membacanya) dan
`interco_finance: [view]` (admin/manager — memisahkan sisi UANG antar-PT dari sisi BARANG
`interco: [view, ship, receive]` yang tetap boleh gudang).

### Platform  (✅ `notifications` IMPLEMENTED Fase 0)
```
Collection: notifications    Prefix: ntf_    Fase 0  [IMPLEMENTED]
  id, entity_id, recipient_role|recipient_user, type, title, body,
  link(navigation_target), severity(info|warning|critical), ref, read, read_at, created_at
⚠️ JANGAN buat: notif, alerts (gunakan notifications)
```

### Sales (Fase 1)
```
customer_price_lists   Prefix: cpl_   — harga khusus per customer/kategori/produk + periode [DEPRIORITAS: harga manual/nego]
price_approvals        Prefix: pra_   — special price (negosiasi harga + upload bukti + approval Finance/Admin)
Collection:  sales_returns   Prefix: sret_  — retur/tukar/Barang Sisa (BS) cacat + dampak stok
Collection:  sales_return_policies Prefix: srp_ — R0 kebijakan retur JUAL (scope global|category|customer): window_days, allowed_return_types[], allowed_outcomes[], restocking_fee_pct, require_inspection, enforce_window, link_to_supplier_window, condition_requirements, custom_fields{} (extensible), valid_from/until. SHARED master (entity_id ""=semua). Router: routers/return_policies.py · Service: services/return_policy_service.py
Collection:  special_orders  Prefix: sord_  — Special Order (SKU belum ada → MD + Purchasing) + estimasi
tax_invoices           Prefix: fkt_   — Faktur Pajak (nomor, DPP, PPN, status) per entitas
sales_targets          Prefix: starg_ — target sales per salesperson per periode (penjualan/pencairan/customer baru) [KN_17]
sales_incentives       Prefix: sinc_  — komisi/bonus per sales per periode (basis sales|pencairan|tiered) [KN_17]
campaigns              Prefix: camp_  — product focus / campaign + target per sales (advanced) [KN_17]
collection_followups   Prefix: cfu_   — jejak follow-up penagihan jatuh tempo [KN_17 S39]
                       AG-T3 — `ai_card_id` bila dicatat lewat kartu tindakan asisten (tindak lanjut, janji bayar
                       `outcome=promised` + `next_action_date` = tanggal janji, tanda sudah diingatkan)
                       CR-T5 — janji bayar: `promise_date` (YYYY-MM-DD, tidak lampau) + `promise_amount` (> 0) WAJIB bila
                       `outcome=promised` (POST /api/customers/{id}/followups → 400 berkalimat). Status janji TIDAK disimpan,
                       dihitung saat dibaca (`credit_desk_service.promise_status`): ditepati = Σ kwitansi tidak-batal
                       pelanggan itu di PT itu bertanggal catatan s.d. `promise_date` ≥ nominal; menunggu (tanggal belum
                       lewat) / ingkar. Indeks (`entity_id`, `outcome`, `promise_date`). Catatan lama tanpa `promise_date`
                       tidak masuk antrean "Janji bayar".
credit_overrides       Prefix: cro_   — bypass blokir kredit via approval Finance + bukti (case-by-case) [KN_17 S37]
⚠️ KPI salesperson = DERIVED (dari sales_orders/invoices/payments/customers), BUKAN koleksi.
⚠️ JANGAN buat: discounts, faktur, returns_generic, salespersons (pakai users role=sales), leads/crm_* (fase lanjut)
```

### Procurement (Fase 3)
```
suppliers          Prefix: sup_    — master pemasok (nama, npwp, kontak, jenis barang, entity_id?). R0: +origin_type (local|import), +country, +return_policy{} embedded (window_days, refund_modes[], returnable_to_supplier, rma_required, restocking_fee_pct, condition_requirements, custom_fields{} extensible). purchase_orders.import_flag (bool|None) = override asal per-PO.
bom_printing       Prefix: bom_    — BOM benang + bahan printing per produk/order
cash_transactions  Prefix: cash_   — kas kecil per entitas + kas besar gabungan
⚠️ purchase_orders.supplier_name (string) → refactor jadi FK suppliers.id
⚠️ Approval pembelian = workflow state + attachment pada purchase_orders (bukan koleksi baru)
⚠️ JANGAN buat: vendor, procurement, kas (pakai suppliers/cash_transactions)
```

### Finance (Fase 4)
```
chart_of_accounts  Prefix: coa_    — COA fleksibel (Aktiva/Hutang/Modal/Pendapatan/Beban)
journal_entries    Prefix: je_     — jurnal/GL double-entry (auto-posting dari invoice/kas)
bank_accounts      Prefix: bank_   — rekening per entitas (MULTI-rekening/entitas), entity_id,
                                    bank_name, account_no, account_name, branch,
                                    designation(ppn|non_ppn|both), is_active, is_default
                                    ⚠️ SO + destination_bank_account_id (dipilih saat buat SO; KN_16 §8B.3).
                                       Invoice PPN→akun ppn/both; non-PPN→non_ppn/both.
tax_records        Prefix: tax_    — rekap PPN/PPH (export Coretax = fase lanjut)
fiscal_periods     Prefix: fper_   — periode + closing (28/30/31) + lock
period_closings    Prefix: close_  — Tutup Buku per PT (services/closing_service.py): period_type month|year,
                                    period_key, start_date/end_date, status closing|closed|reopened
                                    (PK-11: `closing` = sedang ditutup, tidak mengunci posting; hanya `closed`
                                    yang mengunci), journal_entry_id (jurnal source_type `closing`),
                                    stale/stale_at/stale_reason ("Perlu tutup ulang"), suspense_override.
                                    Tutup hanya bila akhir periode < hari ini (WIB).
                                    KF-T6: reopen_request {by_id, by, at} = pengajuan buka kembali yang menunggu
                                    orang kedua (`kontrol.buka_kembali_tutup_buku.min_orang` = 2); dihapus saat
                                    dijalankan orang kedua.
period_close_locks _id = id PT     — kunci proses tutup buku per PT: token (pemilik; hanya pemilik yang
                                    melepas — PK-11), period, by, started_at (diambil alih bila > 600 dtk)
INDEKS UNIK WAJIB (PK-14, `backend/indexes.py` REQUIRED_UNIQUE_INDEXES — aplikasi tidak mulai bila tak terpasang;
  periksa baca-saja: `scripts/check_required_indexes.py`; sakelar `KN_REQUIRED_INDEX_MODE` enforce|warn):
  journal_entries.uq_je_source_active (source_type, source_id | status posted/draft) ·
  interco_transactions / interco_settlements / interco_returns / interco_loans .uq_number (number) ·
  penalties.uq_penalty_line_period (doc_id, plan_id, line_seq, period_key) ·
  payment_plans.uq_plan_active_doc (doc_type, doc_id | status active) ·
  CR-T2: payment_plans.uq_plan_live_doc (doc_id, doc_type | status active/closed) ·
  customer_balances.uq_customer_entity (customer_id, entity_id) ·
  finance_cases.uq_case_open_source (case_type, source.id | status open/in_progress) ·
  PK-40: tax_invoices.uq_fkt_active (active_key) · tax_invoices.uq_fkt_nsfp (nsfp_key) ·
  tax_invoices_in.uq_fpm_active (active_key) · tax_invoices_in.uq_fpm_nsfp (nsfp_key) ·
  tax_period_locks.uq_tax_period (entity_id, period) ·
  PK-31: intercompany_eliminations.uq_pair_period (source_g6_pair_id, period_key | keduanya terisi)
  PM-T1: bank_accounts.uq_default_receiving (entity_id, default_receiving_methods) ·
  PM-T2: payment_codes.uq_pay_code (code) · payment_codes.uq_pay_code_line (order_id, line_id)
  PK-39: budgets.uq_budget_key (entity_id, year, month, dimension, key | key terisi)
⚠️ AR aging/Outstanding = DERIVED dari invoices + credit_limit; denda 1–3% pada invoices
⚠️ JANGAN buat: ledger, accounts, gl (pakai journal_entries/chart_of_accounts/bank_accounts)
```

### Warehouse & RFID (Fase 5)
```
inventory_classifications Prefix: icls_ — klasifikasi fast/slow/dead (>3 bln) + analitik tren
warehouse_locations   Prefix: loc_  — master lokasi RFID hierarki (Zone→Rack→Level→Bin)
rfid_tags             Prefix: tag_  — registrasi tag ↔ item/lot/roll
rfid_devices          Prefix: dev_  — printer/reader/handheld/gate/server
rfid_events           Prefix: evt_  — log scan/gate (green/red) + alarm → notifications
⚠️ warehouses: tambah level "Level" (Zone→Rack→Level→Bin) — enhancement embedded
⚠️ JANGAN buat: rfid (terlalu generik), locations, tags_generic
```

### HRD (Fase 2)

#### hr_org_units  [FASE H0 IMPLEMENTED — Struktur Organisasi berjenjang]
```
Collection:  hr_org_units      Prefix: orgu_
Router:      routers/hr.py
Schema:      schemas_hr.py → HrOrgUnitCreate (PATCH via GenericPatch)
Service:     services/hr_service.py → build_org_tree()
Component:   features/hr/OrgUnitsView.jsx (SDM → Struktur Organisasi)
unit_type:   department | position        (hierarki: Company(entitas) > department > position)
Status:      active | inactive (soft delete via DELETE)
Key Fields:
  id, code, name, unit_type, parent_id (position→department; department→""),
  head_employee_id (opsional), description, entity_id, status,
  created_by, created_at, updated_at
Endpoints:   GET/POST /hr/org-units · GET /hr/org-units/tree ·
             GET/PATCH/DELETE /hr/org-units/{id}
⚠️ entity_id = SCOPED (per-PT). Company = entitas (business_entities) sebagai root tree.
⚠️ JANGAN BUAT: departments, positions, divisi, jabatan, org_chart (pakai hr_org_units).
```

#### hr_employees  [FASE H0 IMPLEMENTED — Master Karyawan HR]
```
Collection:  hr_employees      Prefix: emp_
Router:      routers/hr.py
Schema:      schemas_hr.py → HrEmployeeCreate, AllowanceInput (PATCH via GenericPatch)
Service:     services/hr_service.py → redact_employee_pii(), enrich_employee()
Component:   features/hr/EmployeesView.jsx + EmployeeFormDrawer.jsx (SDM → Karyawan),
             features/hr/EmployeeSelfService.jsx (ESS → Profil Saya)
employment_type: tetap | kontrak | harian | borongan
Status:      active | inactive | resigned (soft delete via DELETE → resigned)
Key Fields:
  id, code (EMP-NNNNN), user_id (nullable FK → users.id), name, nik,
  dob, gender (L|P), phone, email, address,
  department_id (FK hr_org_units), position_id (FK hr_org_units),
  employment_type, join_date, status,
  # PII-sensitive (redacted tanpa hr.view_pii; ESS lihat data sendiri penuh):
  npwp, ptkp_status (TK0..K3), bpjs_kes_enabled, bpjs_kes_no,
  bpjs_tk_enabled, bpjs_tk_no, jkk_risk_class,
  bank_name, bank_acc_no, bank_acc_name, base_salary, allowances[] {name, amount},
  photo_url, entity_id, created_by, created_at, updated_at
Endpoints:   GET/POST /hr/employees · GET /hr/employees/me (ESS, auth only) ·
             GET/PATCH/DELETE /hr/employees/{id} · GET /hr/summary
⚠️ entity_id = SCOPED (per-PT). user_id menyatukan karyawan dgn akun login (sales→komisi→payroll).
⚠️ employees/employee/staff/karyawan = TERLARANG (alias→users). Domain HRD WAJIB 'hr_employees'.
⚠️ PY-T2 — base_salary, allowances, entity_id = NILAI TURUNAN baris riwayat yang berlaku hari ini (WIB)
   (hr_compensation_history / hr_employee_assignments), ditulis HANYA hr_compensation_service.apply_effective;
   PATCH /hr/employees/{id} menolak ketiganya (400). Invarian INV-PY-2. Lihat bagian PY-T2.
```

#### system_settings (scope="hr")  [FASE H0 — Config HR/Payroll]
```
Collection:  system_settings (scope="hr")     (SHARED, bukan koleksi baru)
Router:      routers/hr.py → GET/PUT /hr/settings
Schema:      schemas_hr.py → HrSettingsUpdate
Key Fields:  bpjs (rates+ceiling), jkk_classes[], ptkp_table, ter_enabled,
             feature_toggles {bpjs_kesehatan, bpjs_ketenagakerjaan, pph21, npwp_required},
             employment_types[], payroll_commission_mode (default accrue_then_settle)
⚠️ Config-driven (regulasi mudah update). Perhitungan statutory dipakai di FASE H4 (payroll).
⚠️ PK-46 — `ptkp_table` di dokumen ini TIDAK dibaca mesin gaji. Tabel PPh 21 (TER, kategori PTKP, PTKP setahun,
   pasal 17, biaya jabatan) = kunci `bertanggal` di config_values (lihat bagian config_values), tidak diproyeksikan ke sini.
```

#### HRD H1 — Absensi (IMPLEMENTED · FASE H1)
```
hr_shifts (shift_)      — Router: routers/hr_attendance.py → GET/POST /hr/shifts, PATCH/DELETE /hr/shifts/{id}
  Fields: id, code, name, jam_in(HH:MM WIB), jam_out, grace_late_min, break_min,
          work_days[1..7], status(active|inactive), entity_id, created_at/by, updated_at
hr_geofences (geo_)     — GET/POST /hr/geofences, PATCH/DELETE /hr/geofences/{id}
  Fields: id, name, lat, lon, radius_m, address, status, entity_id, audit. (validasi haversine)
hr_devices (dev_)       — GET/POST /hr/devices, PATCH/DELETE /hr/devices/{id}, POST /hr/devices/{id}/rotate-token (KP-T8)
  Fields: id, name, code(SN), location, device_token_hash(SHA-256 token, auth ingest; indeks unik parsial
          uq_device_token_hash), device_token_hint(4 karakter terakhir), device_token_at, token_rotation_required,
          last_sync, status, entity_id, audit
  KP-T8: token tampil SEKALI saat buat/ganti (`at_`+32 heks); daftar tidak pernah mengirim token/hash. Bentuk lama
          `device_token` polos masih dibaca ingest sampai `scripts/migrate_kpt8_rahasia.py` dijalankan pemilik (H3).
hr_attendance (att_)    — GET /hr/attendance, /hr/attendance/recap, /hr/attendance/me,
                          POST /hr/attendance/{clock-in,clock-out,manual,import,ingest}, PATCH /hr/attendance/{id}
  Fields: id, employee_id, employee_name, date(YYYY-MM-DD WIB), shift_id, shift_name,
          clock_in(iso+07:00), clock_out, method(geo|fingerprint|manual), status(hadir|telat|flagged|izin|cuti|alpha|libur),
          outside_geofence, geo{in{lat,lon,distance_m,inside,geofence_id},out{...}}, photo_url, note,
          work_min, late_min, early_leave_min, overtime_min, std_min, approved, entity_id, audit
  IDEMPOTENT: unik per (employee_id, date). Import/ingest gabung multi-punch (in=min, out=max).
Schema: schemas_hr_attendance.py · Service: services/hr_attendance_service.py (haversine, metrics, ZKTeco parse, recap)
RBAC:   hr.view (read) · hr.manage_attendance (CRUD master + manual/approve/import; admin+manager)
        clock-in/out + /me = auth + karyawan ter-link (lihat data sendiri) · ingest = device_token
Employee link: hr_employees.shift_id (FK hr_shifts) + hr_employees.device_user_id (ID enroll mesin)
⚠️ entity_id = SCOPED. JANGAN pakai 'attendance/absensi/shift/device' polos → WAJIB prefiks 'hr_'.
```

#### HRD H5 — KPI Design + Design Gallery + AI (IMPLEMENTED · FASE H5)
```
hr_kpi (hkpi_)         — Router: routers/hr_kpi.py → GET/POST /hr/kpi, PUT/DELETE /hr/kpi/{id}, GET /hr/kpi/me (ESS)
  Fields: id, employee_id, employee_name, entity_id, period(YYYY-MM), metric,
          target(num), actual(num), score(0–150; auto=min(actual/target,1.5)*100 bila kosong),
          weight, note, status(recorded), created_by, created_at, updated_at
  Service: services/hr_kpi_service.py (compute_score, list/submit/update/delete, my_kpi rekap tertimbang)
  RBAC:   hr.view (read) · hr.manage_attendance (CRUD; admin+manager) · /me = auth + karyawan ter-link
  Frontend: features/hr/KpiView.jsx (HRD) + features/hr/MyKpiCard.jsx (ESS "KPI Saya")
design_gallery (dsgn_) — Router: routers/design_gallery.py → GET/POST /design-gallery, GET/PUT/DELETE /design-gallery/{id},
          POST /design-gallery/{id}/files (UploadFile), GET/DELETE /design-gallery/{id}/files/{file_id},
          POST /design-gallery/{id}/autotag (AI, graceful)
  Fields: id, title, story, tags[], files[]({id,filename,path,content_type,size,uploaded_at}),
          product_id(opsional), ai_meta{enabled,model,tags[],summary,attributes,analyzed_at,error},
          entity_id, created_by, created_at, updated_at
  Service: services/design_gallery_service.py (storage lokal via storage_service; get_object MENGEMBALIKAN TUPLE)
  RBAC:   hr.view (read+file) · hr.manage_attendance (create/update/delete/upload/autotag; admin+manager)
  Frontend: features/hr/DesignGalleryView.jsx (gambar via blob-fetch ber-Authorization → objectURL)
  AI:     services/hr_ai_service.py — Anthropic Claude DIRECT SDK (paket `anthropic`), key di
          system_settings scope='integrations'. GRACEFUL: key kosong → autotag {enabled:false} (galeri tetap jalan).
system_settings (scope="integrations")  (SHARED, bukan koleksi baru) — Router: routers/integrations.py →
          GET/PUT /admin/integrations (izin integration.manage — KP-T8; dulu hr.manage_settings). Key TIDAK pernah
          dikembalikan plaintext (GET → has_key:bool + model + enabled + secrets_key_configured). Service:
          services/integrations_service.py (deep-merge anti data-loss). Kunci dibungkus services/secret_box.py
          (`enc:v1:`, KN_SECRETS_KEY). `anthropic.enabled|model` = kunci registry `integrations.anthropic.*` (KP-T8).
  KP-T8 objek `whatsapp` = KONEKSI WhatsApp TUNGGAL untuk Pengingat & Kirim Dokumen: {provider, access_token,
          fonnte_token (keduanya selalu terbungkus), phone_number_id, sender, sender_label, default_country_code,
          template_name, template_lang, source(manual|alerts|documents|gabungan), updated_at, updated_by}.
          Service: services/wa_connection.py (`for_consumer("alerts"|"documents")`). Router: GET/PUT
          /admin/integrations/whatsapp, POST …/whatsapp/adopt, POST …/whatsapp/test (integration.manage). Pengaturan
          pemakaian tetap di system_settings{scope:"alerts"}.wa (enabled, pic_number, send_to_roles, min_severity,
          delivery_mode, critical_bypass) dan integration_settings{id:"whatsapp"} (enabled, simulate); field koneksi
          lama di dua tempat itu hanya dibaca selama koneksi tunggal belum ada.
⚠️ entity_id = SCOPED (hr_kpi, design_gallery). JANGAN pakai 'kpi/gallery/motif' polos.
```

#### HRD — koleksi fase berikut (BELUM, planned)
```
hr_schedules                                                 (H1+ — jadwal shift per-tanggal, opsional)
⚠️ Semua prefiks 'hr_'. JANGAN BUAT: attendance/absensi/payroll/gaji/kpi polos.
```

---

### Gate G-1 — Koleksi operasional HR & Pajak (didaftarkan Gelombang 3, anti self-drift)

#### hr_shifts  [FASE H1 IMPLEMENTED — Master Shift Kerja]
```
Collection:  hr_shifts         Prefix: shift_
Router:      routers/hr_attendance.py
Service:     services/hr_attendance_service.py
Key Fields:  id, code, name, jam_in, jam_out, grace_late_min, break_min, work_days[], status, entity_id
⚠️ entity_id = SCOPED (per-PT).
```

#### hr_geofences  [FASE H1 IMPLEMENTED — Geofence Absensi GPS]
```
Collection:  hr_geofences      Prefix: geo_
Router:      routers/hr_attendance.py
Service:     services/hr_attendance_service.py
Key Fields:  id, name, lat, lon, radius_m, address, status, entity_id
⚠️ entity_id = SCOPED (per-PT).
```

#### hr_attendance  [FASE H1 IMPLEMENTED — Kehadiran Harian]
```
Collection:  hr_attendance     Prefix: att_
Router:      routers/hr_attendance.py
Service:     services/hr_attendance_service.py → upsert_attendance()
Key Fields:  id, employee_id, date, check_in, check_out, method (fingerprint|geo|manual),
             late_min, overtime_min, status, entity_id
⚠️ entity_id = SCOPED (per-PT). Unik per (employee_id, date).
```

#### hr_devices  [FASE H1 IMPLEMENTED — Registry Mesin Absensi]
```
Collection:  hr_devices        Prefix: dev_
Router:      routers/hr_attendance.py
Service:     services/hr_attendance_service.py
Key Fields:  id, name, code, location, device_token_hash, device_token_hint, device_token_at,
             token_rotation_required, last_sync, status, entity_id
⚠️ entity_id = SCOPED (per-PT). Token mesin = kredensial push mesin: disimpan hanya hash-nya (KP-T8); `device_token`
   polos = bentuk lama (dibaca ingest sampai dimigrasi `scripts/migrate_kpt8_rahasia.py`).
```

#### hr_field_tracks  [FASE H2 IMPLEMENTED — Breadcrumb GPS Live Tracking]
```
Collection:  hr_field_tracks   Prefix: trk_
Router:      routers/hr_tracking.py
Service:     services/tracking_service.py → hydrate_latest()
Key Fields:  id, employee_id, employee_name, lat, lon, accuracy, battery, ts, source, entity_id
⚠️ entity_id = SCOPED (per-PT). Append-only (jejak posisi).
```

#### hr_visits  [FASE H2 IMPLEMENTED — Kunjungan Lapangan Sales]
```
Collection:  hr_visits         Prefix: visit_
Router:      routers/hr_tracking.py
Service:     services/tracking_service.py
Key Fields:  id, employee_id, customer_id, date, check_in{ts,lat,lon,photo_url},
             check_out{...}, notes, outcome (order|followup|none), linked_so_id,
             status, duration_min, entity_id
⚠️ entity_id = SCOPED (per-PT).
```

#### tax_pph_records  [EPIC 7 IMPLEMENTED — Rekam PPh Manual/Omzet]
```
Collection:  tax_pph_records   Prefix: pph_
Router:      routers/tax_center.py
Service:     services/tax_center_service.py → record_pph()
Key Fields:  id, code (pph21|pph23|...), period (YYYY-MM), rate, dpp, amount, note,
             status, entity_id, created_by
⚠️ entity_id = SCOPED (per-PT). Basis payroll dihitung dari hr_payroll_runs (bukan koleksi ini).
   PK-40 (FY-16): butir PPh 21 = penggajian `posted`/`paid` saja; dpp = Σ hr_payslips.tax_gross (slip lama: gross),
   amount = Σ pph21 slip, gl_amount = kredit − debit 2-1800 jurnal `payroll_run` berkunci proses itu (PK-22: id proses;
   proses lama `{entity_id}:{period}` — `gl_service.payroll_source_id`), selisih.
   Rekam/hapus rekaman pada masa yang sudah dilaporkan (`tax_period_locks`) → 409.
```

#### tax_period_locks  [PK-40 — masa pajak ditandai dilaporkan / terkunci]
```
Collection:  tax_period_locks   Prefix: tpl_
Router:      routers/tax_center.py (GET /api/tax/periods · POST /api/tax/periods/{period}/lock ·
             POST /api/tax/periods/{period}/unlock) — baca `accounting.view`, kunci/buka `accounting.manage`
Service:     services/tax_center_service.py (`assert_masa_terbuka`, `lock_period`, `unlock_period`,
             `list_period_locks`)
Component:   features/finance/TaxCenterView.jsx (lencana Sudah/Belum dilaporkan, Tandai Sudah Dilaporkan, Buka Masa Pajak)
Key Fields:  id, entity_id, period (YYYY-MM), status (reported|reopened), reported_at, reported_by, reported_by_id,
             note, snapshot {keluaran_ppn, masukan_ppn, net_ppn, pph_total, gl_keluaran_ppn, gl_masukan_ppn}
             (potret saat ditandai — tidak dihitung ulang, D3), reopened_at, reopened_by, reopened_by_id,
             reopen_reason, history[] (kejadian laporan yang dibuka lagi: reported_* + snapshot + reopen_*),
             created_at, updated_at
Indeks:      uq_tax_period (entity_id, period) — unik, wajib-ada (PK-14 REQUIRED_UNIQUE_INDEXES)
Aturan:      kunci hanya untuk masa yang SUDAH berakhir (WIB); buka wajib alasan ≥ 5 huruf; satu orang berizin.
             `status == reported` → terbit/ganti/batal/ubah NSFP faktur keluaran, catat/batal faktur masukan, faktur
             internal antar-PT, rekam/hapus PPh masa itu ditolak 409 (langkah PERIKSA, sebelum tulisan).
⚠️ entity_id = SCOPED (per-PT). Tanpa dokumen = masa terbuka (perilaku sebelum PK-40).
```

#### rfid_tags  [FASE 5 IMPLEMENTED — RFID Simulator: tag ↔ roll]
```
Collection:  rfid_tags         Prefix: rtag_
Router:      routers/rfid.py
Service:     services/rfid_service.py
Key Fields:  id, epc (unik saat active), roll_id (FK inventory_rolls), product_id, sku,
             product_name, roll_no, lot, owner_entity_id, warehouse_id, status (active|retired),
             last_seen_at, last_seen_device_id, last_seen_device_name, last_seen_location,
             last_seen_warehouse_id, encoded_at, encoded_by
⚠️ owner_entity_id = SCOPED (per-PT). Roll-as-SSOT: encode hanya set inventory_rolls.rfid_tag_id
   + tracking_mode="rfid" (TIDAK ubah kuantitas / inventory_balances).
```

#### rfid_devices  [FASE 5 IMPLEMENTED — RFID Reader/Gate (infra per-gudang)]
```
Collection:  rfid_devices      Prefix: rdev_
Router:      routers/rfid.py
Service:     services/rfid_service.py
Key Fields:  id, code (unik), name, type (gate|fixed_reader|handheld), direction (in|out|n/a),
             warehouse_id, warehouse_name, location, status (online|offline), last_heartbeat,
             created_at, created_by
ℹ️ SHARED (infra fisik per-gudang, bukan per-PT). Write = role admin.
```

#### rfid_reads  [FASE 5 IMPLEMENTED — Log pembacaan RFID (event)]
```
Collection:  rfid_reads        Prefix: rread_
Router:      routers/rfid.py
Service:     services/rfid_service.py
Key Fields:  id, epc, tag_id, roll_id, sku, product_name, roll_no, device_id, device_name,
             device_type, read_type (gate_in|gate_out|inventory), warehouse_id, location,
             owner_entity_id, result (green|red|info), reason, timestamp
⚠️ owner_entity_id = SCOPED (per-PT). Append-only event log; gate memutuskan HIJAU/MERAH
   berbasis status roll (kontrol keluar-masuk). Tidak mengubah stok.
```

---

## ADDENDUM — Collections registered during copy+fix session (2026-07-05)

> Koleksi berikut sudah dipakai di kode lintas router/service namun belum tercatat eksplisit
> di atas. Didaftarkan resmi di sini + di allowlist `scripts/validate_compliance.py`
> (CHECK 8 ENTITY_REGISTRY & CHECK 13 NAMING). Semua adalah domain-entity yang sah.

| Collection | Prefix/ID | Router utama | Catatan |
|-----------|-----------|--------------|---------|
| vendor_bills | vb_ | routers/vendor_bills.py | Tagihan vendor (AP). owner_entity_id SCOPED. |
| landed_cost_vouchers | lcv_ | routers/landed_cost.py | Voucher biaya masuk (impor/logistik). |
| rfqs | rfq_ | routers/rfq.py | Request for Quotation (procurement). |
| tax_invoices_in | tii_ | routers/input_tax.py | Faktur Pajak Masukan (PPN in). |
| credit_notes | cn_ | routers/sales_returns.py, crm | Nota kredit pelanggan. |
| amendment_reasons | amr_ | services/amendment_service.py, services/penalty_service.py | FASE G-1/G-2 — taksonomi label alasan koreksi & keputusan denda (dikelola admin). |
| customer_balances | cbl_ | services/customer_balance_service.py, routers/customer_balances.py | CR-T2 — saldo piutang tersimpan per (pelanggan, PT), turunan (hitung ulang penuh; INV-BAL-01/02). |
| `mkt_campaign_costs` | mcc_ (nomor `MCC-`) | services/marketing_cost_service.py, routers/marketing.py | COMM-04 — realisasi biaya kampanye pemasaran (uang satu PT: kas + jurnal Beban Pemasaran). `entity_id` SCOPED. Didaftarkan 18 Nov 2026 (gate L0: sudah di `scripts/verify_contract.py`, belum di sini). |
| `roll_label_prints` | rlp_ | services/rfid_print_service.py, services/putaway_order_service.py | LN-042-T03 — histori cetak label roll, append-only (satu baris per label; `reprint`, `print_seq`). `owner_entity_id` mengikuti pemilik roll (SCOPED). Didaftarkan 18 Nov 2026 (gate L0). |
| payment_plans | pyp_ | services/payment_plan_service.py, services/billing_schedule_service.py, routers/payment_plans.py | FASE G-2 — rencana pembayaran fleksibel per dokumen (DP/cicilan/milestone), nomor `<ENT>/RPB-#####`. CR-T2: juga jadwal tagihan mesin (`origin: term`, tanpa nomor) — satu jadwal hidup per pesanan. Scoped `entity_id`. PK-09: `schedule_history[]` (`at` · `by` · `reason` · `lines_before`) — satu butir tiap ubah baris jadwal; status & terbayar baris tidak dari klien. PM-T2: `lines[].pay_code` = kode bayar baris tagihan (`payment_codes`, diisi `payment_code_service.ensure_for_line`). |
| penalties | pnl_ | services/penalty_service.py, routers/payment_plans.py | FASE G-2 — nota denda keterlambatan (`draft` tanpa jurnal → `issued`/`waived`/`adjusted`/`paid`), nomor `<ENT>/DN-DENDA-#####`. Scoped `entity_id`. CR-T4: lahir dari SEMUA jadwal hidup (`payment_plans` `origin` `term` jadwal tagihan CR-T2 maupun `manual`; `plan_id` = jadwal, `line_seq` = baris) — jalur "pesanan tanpa rencana" (`plan_id: ""`, `line_seq: 0`) tidak lagi membuat nota baru; `policy_snapshot` = aturan yang dipakai (`penalty_service.penalty_policy`) + `sources` {mode, base, rate_pct_per_month, cap_pct, grace_days, min_amount: `global`·`pt`·`pelanggan`·`rencana`} + `waiver` ({reason, valid_until} bila bebas denda) — diperbarui selama nota masih `draft`. PK-08: `days_prior` (hari yang sudah dimuat nota sebelumnya untuk baris yang sama; `billable_days` = hari nota ini saja, `days_late` kumulatif), `payments[]` (`id` pnp_ · `amount` · `method` · `account_id` · `cash_txn_id` · `status` pending→applied→done · `at` · `by` · `cash_doc`), `adjustments[]` (`seq` · `from` · `to` · `delta` · `reason_code` · `je_id` · `at` · `by`; jurnal pembalik `<id>:adjust:<seq>`). Bayar denda = kas `cash_transactions` `cash_pnl_<id pembayaran>` (`ref_type: "penalty"`, `ref_id` = nota, lawan 1-1270). |
| payment_variance_decisions | pvd_ | services/payment_variance_service.py, routers/payment_variance.py | FASE G-3 — keputusan **selisih pembayaran** (lebih/kurang bayar), nomor `<ENT>/SLB-#####`. Jenis: `outstanding`/`reschedule`/`writeoff`/`deposit`/`allocate`/`refund` (+`rounding_*` otomatis, +`ap_*` sisi supplier). Wajib `reason_code` & pemutus; pemindahan uang selalu ber-jurnal; `status: reversed` bila dianulir. Scoped `entity_id`. PK-19: `status` `pending` → `done` · `failed` · `reversed` (niat dulu; ulang dengan pilihan sama meneruskan), `plan[]` (baris rencana efek: `{order_id, amount, deposit_taken, allocated, ar}` untuk alih deposit; `{order_id, amount}` untuk hapus sisa), `gl_status`/`gl_error`/`journal_entry_id` (jurnal keputusan, PK-18; jenis registri `payment_variance`), `reversal_gl_status`/`reversal_gl_error` + `reversal_steps.deposit_restored` (pembatalan), `error` (galat efek terakhir). Jurnal alih deposit per baris `source_id = <id>:<id pesanan>`. |
| credit_overrides | cro_ | services/credit_override_service.py, services/credit_gate.py, routers/crm.py, routers/so_approvals.py | Izin kredit (pending→approved). CR-T3: `scope` pesanan/pelanggan, `amount` > 0, `remaining_amount`, `valid_until`, `reason_code`/`reason_label`, `used_by[]`. |
| credit_gate_rejections | cgr_ | services/credit_gate.py, routers/crm.py | CR-T3 — pesanan yang ditolak gerbang kredit saat dibuat (potret eksposur + isi permintaan). Scoped `entity_id`. |
| collection_followups | cf_ | routers/crm.py | Follow-up penagihan AR. CR-T5: + `promise_date`, `promise_amount` (janji bayar; status dihitung saat dibaca, `services/credit_desk_service.py`). |
| sales_targets | st_ | routers/hr_kpi, home | Target penjualan per sales/periode. |
| sales_incentives | si_ | routers/incentive_rates, home | Perhitungan insentif sales. |
| login_attempts | la_ | routers/auth.py | Log percobaan login (rate-limit/security). |
| hr_employees | emp_ | routers/hr*.py | Master karyawan (SCOPED). |
| hr_attendance | att_ | routers/hr_attendance.py | Absensi harian. |
| hr_devices | dev_ | routers/hr_tracking.py | Device absensi/tracking. |
| hr_field_tracks | trk_ | routers/hr_tracking.py | Jejak posisi lapangan (live tracking). |
| hr_geofences | gf_ | routers/hr_tracking.py | Area geofence kunjungan. |
| hr_kpi | kpi_ | routers/hr_kpi.py | KPI karyawan/periode. |
| hr_leave_requests | lv_ | routers/hr_leave.py | Pengajuan cuti. |
| hr_org_units | org_ | routers/hr.py | Unit organisasi (struktur). |
| hr_overtime | ot_ | routers/hr_attendance.py | Lembur. |
| hr_shifts | shf_ | routers/hr_attendance.py | Shift kerja. |
| hr_visits | vis_ | routers/hr_tracking.py | Kunjungan lapangan sales/karyawan. |

> **Modul Digitalisasi Formulir Sukacita (Petty Cash / PD · Settlement · Kendaraan)** — koleksi baru
> FASE 0-5: `cash_advances`, `cash_advance_settlements`, `expense_categories`, `vehicles`, `vehicle_usage_logs`.
> Semua entity-scoped (`entity_id`), terdaftar di `entity_scope.SCOPED_COLLECTIONS` &
> `verify_contract.CANONICAL_COLLECTIONS`.

| Collection | Prefix/ID | Router utama | Catatan |
|-----------|-----------|--------------|---------|
| cash_advances | ca_ (number: {PT}/PD-#####) | routers/cash_advances.py | Form Pengajuan Dana (PD). State-machine draft→pending_atasan→pending_pimpinan→pending_finance→approved→disbursed→settled. SCOPED. |
| cash_advance_settlements | stl_ (number: {PT}/STL-#####) | routers/cash_advances.py | Laporan Pertanggungjawaban (LPJ) atas PD. Posting GL saat approved (Dr beban/Cr Kas Kecil). SCOPED. PK-44: `refs[]` (G-4) — relasi `parent` ke PD-nya ditulis saat lahir (jenis dokumen `cash_settlement`). PK-24: lihat blok "PK-24 — kas kecil" di bawah. |
| expense_categories | — (code kategori) | routers/cash_advances.py | Mapping kategori beban petty cash → akun COA (6-4100..6-4900). Config. |

**PK-24 — kas kecil (pengembalian sisa uang muka, LPJ terkunci, lampiran).** Tanpa migrasi: LPJ lama tanpa field baru
tetap terbaca (LPJ `posted_to_gl` lama yang bersisa tidak dibuka kewajiban kembalinya — keputusan pemilik, H3).

| Koleksi · field | Tipe | Arti |
|---|---|---|
| `cash_advance_settlements.status` | teks | `draft` → `submitted` → **`approved`** (disetujui, jurnal belum terbit/gagal) → `posted_to_gl`; `rejected` (pembuat bisa `POST …/reopen` → `draft`). Ubah & lampiri hanya `draft`; setujui/tolak hanya `submitted` |
| `cash_advance_settlements.gl_status`, `gl_error`, `gl_failed_at`, `journal_entry_id` | menurut PK-18 | Status jurnal LPJ (`post_durable`); gagal → panel Posting Gagal jenis `petty_cash_settlement` |
| `cash_advance_settlements.sisa_dikembalikan` | `{amount, status: none\|open\|returning\|returned, cash_txn_id, cash_txn_number, journal_entry_number, account_id, returned_at, returned_by, returned_by_id, last_error}` | Sisa uang muka (uang muka − pengeluaran) yang harus kembali; ditulis saat LPJ dijurnal, ditutup `POST …/return-remainder` (kas masuk `ref_type="cash_advance_return"`, `ref_id` = id LPJ: Dr kas / Cr `kas_bank.uang_muka_karyawan`) |
| `cash_advance_settlements.attachments[]` | `{id, filename, content_type, size, path, uploaded_by, uploaded_by_id, uploaded_at}` | Bukti pengeluaran (`services/storage_service`, `cash_advance_settlements/{id}/{att}.{ext}`); wajib ≥ 1 saat diajukan bila `finance.lpj_wajib_lampiran` menyala untuk PT itu |
| `cash_advance_settlements.submitted_by_id`, `approved_by_id`, `rejected_by_id`, `reopened_by_id` (+ nama & waktu) | teks | Id pelaku (bahan kontrol dua orang) |
| `cash_advance_settlements.hutang_reimburse.paid_by_id`, `.account_id` | teks | Pembayar & rekening bayar reimburse |
| `cash_advances.disbursed_by_id`, `disbursement.account_id`, `disbursement.disbursed_by_id` | teks | Pencair & rekening sumber pencairan (kontrol `kontrol.cairkan_uang_muka.*`, pembanding = pemohon PD) |
| vehicles | veh_ | routers/vehicle_logs.py | Master kendaraan ringan (no_polisi/nama/jenis). SCOPED. |
| vehicle_usage_logs | vhl_ (number: {PT}/VHL-#####) | routers/vehicle_logs.py | Laporan Penggunaan & Biaya Kendaraan (km, BBM, tol, parkir). SCOPED. |

> **Fix terkait:** `routers/hr_payroll.py` sebelumnya query `db.entities` (koleksi salah/kosong) →
> diperbaiki ke `db.business_entities` agar nama entitas muncul benar di PDF slip gaji.

---

### Platform Dokumen (PDF · WhatsApp · e-Sign) + Payroll Slip  [DIDAFTARKAN 2026-07-26]

Empat koleksi ini sudah dipakai mesin sejak lama tetapi **belum pernah tercatat** di registry,
sehingga muncul sebagai WARN `[ENTITY_REGISTRY]`/`[NAMING]` di `validate_compliance`.
Didaftarkan di sini beserta penulis/pembacanya yang sebenarnya.

| Collection | Prefix/ID | Penulis (SSOT) | Pembaca | Catatan |
|-----------|-----------|----------------|---------|---------|
| `document_deliveries` | `wadlv_` | `services/delivery_service.py:108` | `routers/pdf.py:141`, `delivery_service.list_deliveries()` | Arsip pengiriman dokumen PDF via kanal (WhatsApp). Menyimpan `doc_type`, `source_id`, `to`, `caption`, `status`, `provider`, `simulated`, `attachment_name/size`, `trigger`, `auto`, `rule_id`. **SCOPED** (`entity_id`). Provider `simulated` tetap mencatat penuh tanpa mengirim ke jaringan. |
| `document_signatures` | `esig_` | `services/esign_service.py:138` | `esign_service` (verifikasi + status ttd di daftar dokumen) | Tanda tangan elektronik terverifikasi OTP. Menyimpan `doc_hash` (integritas isi), `verification_code` (QR publik `/verify-document/<code>`), `signer_name/role`, `signature_b64`, `ip`, `channel`. Pasangannya `esign_requests` (OTP, attempts, expiry). **SCOPED**. |
| `hr_payslips` | `id` + `number` | `services/hr_payroll_service.py:287` (`insert_many`) | `routers/hr.py:344` (profil karyawan), `hr_payroll_service:295/366` | Slip gaji per karyawan per periode. Turunan dari `hr_payroll_runs` (bukan sumber). Menyimpan komponen PPh21 metode **TER** (`ter_category`, `pph21_rate`), BPJS (`bpjs_emp/er`), lembur (`overtime_auto_min`/`overtime_filed_min`), `pdf_url`. **SCOPED**. |
| `pdf_templates` | kunci majemuk `doc_type` + `entity_id` | `services/pdf_service.py` (`save_template_cfg`, `reset_template_cfg`) | `pdf_service.get_template_cfg` (`build_document`), `routers/pdf.py` (`/api/pdf/templates*`) | Konfigurasi template cetak BERLAPIS: bawaan kode → `__default__` grup → jenis dokumen grup → `__default__` PT → jenis dokumen PT. Lapisan grup menyimpan konfigurasi penuh (`__default__`) atau perbedaan (jenis dokumen); `config`, `version`, `updated_by`, `updated_at`. **KP-T6** — `entity_id`: `"all"` (semua PT) atau id PT; baris lama tanpa `entity_id` dibaca sebagai `"all"` (diisi `scripts/migrate_kpt6_template_pt.py`, H3). Lapisan PT hanya `intro_text`, `closing_note`, `footer_text`, `show_place_date`, `place`, `signature_slots`, `watermark_text`, `watermark_opacity` (`PT_LAYER_KEYS`). Indeks unik wajib `uq_doctype_entity` (`indexes.REQUIRED_UNIQUE_INDEXES`). |
| `document_branding` | kunci `entity_id` | `services/pdf_service.py` (`save_branding`, `resolve_identity`) | `pdf_service.get_branding` (semua dokumen cetak, kartu warna, jejak cetak, materi pemasaran), `entity_readiness_service` (kesiapan logo/kop & penanda tangan) | Kop per PT. **KP-T6** — yang masih DITULIS hanya gambar & tanda tangan: `logo_b64`, `header_image_b64`, `footer_image_b64`, `stamp_b64`, `signatures[]` ({label, role, name, signature_b64}). Teks lama `company_name`, `address`, `phone`, `email`, `website`, `npwp`, `tagline` tidak dihapus dan tetap DIBACA (menang atas Profil PT) sampai PT itu diselesaikan pemilik (`POST /api/pdf/branding/{id}/identity` → `identity_resolved_at`, `identity_resolved_by`, `identity_resolved_action` `pakai_profil`/`salin_ke_profil`, `identity_resolved_reason`). Membatalkan: kosongkan `identity_resolved_at`. |
| `hr_kpi` | `hkpi_` | `services/hr_kpi_service.py:51` | `routers/hr.py:346`, `routers/hr_kpi.py` | KPI karyawan per periode (`metric`, `target`, `actual`, `score`, `weight`). **SCOPED**. |
| `rnd_person_divisions` | kunci majemuk `entity_id` + `name` | `services/rnd_org_service.py:set_member_division` | `rnd_org_service.division_map/list_members`, `services/rnd_kpi_service.py` (kolom & filter DIVISI), `services/approval_matrix_service.py` | **PS-17 (D-13)** penempatan divisi orang R&D. Disimpan per-NAMA karena desainer sering BUKAN akun user (hanya nama pada round sample); bila namanya seorang user, nilainya dicerminkan ke `users.division`. 1 orang = 1 divisi. **SCOPED** (`entity_id`). |
| `approval_matrix_log` | `amlog_` | `services/approval_matrix_service.py:record` | `services/approval_matrix_service.py:log`, `routers/approvals_matrix.py` (`GET /api/approvals/matrix-log`), `MyApprovalsView` (panel Jejak Persetujuan) | **PS-20 (D-14)** jejak keputusan matriks persetujuan divisi untuk 4 tahap (`design_acc`, `sample_acc`, `po_custom`, `purchase_request`): siapa memutus, tingkat berapa, hasilnya, dan **percobaan yang ditolak sistem** (`violation=true`, mis. peran salah / pengaju menyetujui dokumen sendiri). Jejak ganda juga ditulis ke `audit_logs` (`approval_matrix_*`). **SCOPED** (`entity_id`). |

> 🔴 **BUG DITUTUP 2026-07-26 (ditemukan setelah `check_imports` diperbaiki):**
> `routers/hr.py:346` membaca `db.hr_kpi_entries` — koleksi yang **nol penulis** di seluruh repo
> (0 dokumen). Akibatnya seksi **KPI di profil karyawan selalu kosong** tanpa error.
> Koleksi yang benar adalah **`hr_kpi`** (6 dokumen di data demo, field `employee_id`/`period`/`score`).
> Sudah diperbaiki. `hr_kpi_entries` **tidak dipakai lagi** — jangan dihidupkan kembali.

**Dibuat:** 28 Mei 2026 · **Update IA:** 15 Jun 2026 (planned entities KN_14) · **Update H5:** 01 Jul 2026 (hr_kpi, design_gallery, integrations) · **Update G-1:** Gelombang 3 (hr_shifts, hr_geofences, hr_attendance, hr_devices, hr_field_tracks, hr_visits, tax_pph_records) · **Update 2026-07-26:** document_deliveries, document_signatures, hr_payslips, hr_kpi didaftarkan  
**Update wajib:** Setiap kali ada entitas baru ditambahkan  
**IA induk:** `KN_14_INFORMATION_ARCHITECTURE.md` (SSOT triangle: KN_14 ⇄ KN_13 ⇄ ENTITY_REGISTRY)


---

## ADDENDUM — FASE G-6b (lanjutan Transaksi Antar Entitas) · 2026-08-06

### interco_returns   *(prefix `icr_` · nomor `<ENT>/ICR-#####` · SCOPED `entity_id`)*
**RETUR ANTAR-PT** — jalan resmi ketika barang antar-PT SUDAH berpindah (pembatalan
dokumen sengaja ditolak saat itu). **Dokumen kembar**, satu per PT:
`role="returner"` (nota retur di PT pembeli) ↔ `role="receiver"` (nota kredit di PT
penjual), saling menunjuk `return_pair_id` + `counterpart_id`/`counterpart_number`.

```
id · number · return_pair_id · role(returner|receiver) · entity_id
origin_pair_id · origin_number
seller_entity_id/name · buyer_entity_id/name
items[] {product_id, sku, product_name, unit, quantity, unit_price, line_subtotal, notes}
subtotal · tax_apply · tax_rate · tax_amount · grand_total · returned_cost
reason (WAJIB ≥5 huruf) · notes · doc_date
status: draft → approved → completed  (+ cancelled)
warehouse_transfer_id/code/status   (tugas gudang ARAH BALIK)
timeline[] · created_by/at · approved_by/at · completed_by/at · cancel_reason
```
* Jurnal (`source_type="interco_return"`): `{rp}:seller` `{rp}:buyer` (sisi dokumen,
  saat disetujui) · `{rp}:goods_out` `{rp}:goods_in` (sisi barang, saat tugas gudang
  selesai). Akun: 4-1000 · 2-1200 · 1-1250 · 2-1250 · 1-1310 · 1-1500 · 1-1300 · 5-1000.
* RBAC: `interco:{return, approve, ship}` · **dual-control**: pembuat ≠ penyetuju.
* Invarian: **INV-IC-08**. Endpoint: `/api/interco/returns*`,
  `/api/interco/transactions/{id}/returnable`.
* **JANGAN BUAT**: koleksi retur antar-PT lain (`intercompany_returns`,
  `ic_returns`), dan JANGAN mengedit `grand_total` transaksi asal — retur dicatat
  sebagai `returned_amount`/`returned_subtotal`/`returned_tax`/`returned_cost`/
  `returned_qty` pada dokumen kembar transaksi (ledger append-only).

### tax_invoices / tax_invoices_in — kini juga memuat **FAKTUR PAJAK INTERNAL**
Transaksi antar-PT ber-PPN menerbitkan pasangan dokumen pajak di koleksi yang SUDAH
ADA (sengaja tanpa koleksi baru, supaya rekap `vat_summary` & layar Pusat Pajak ikut
memperhitungkannya tanpa perubahan di sana). Penanda: `source_type="interco"` ·
`is_internal: true` · `interco_pair_id` · `interco_seller_id`/`interco_buyer_id` ·
`counterpart_faktur_id`/`counterpart_faktur_number` · `needs_replacement` (+ `_note`).
`order_id` KOSONG untuk dokumen internal (referensinya `interco_pair_id`).
Invarian: **INV-IC-07**. Jalur pengganti umum (`/api/tax-invoices/{id}/replace`)
MENOLAK dokumen internal dengan kalimat menuntun ke layar Antar Entitas.

### interco_accounts — field baru
`returned_amount` (Σ retur yang berlaku) · `last_activity_at` (aktivitas NYATA
terakhir: dokumen terbuka & settlement — dipakai untuk umur saldo, menggantikan
`updated_at` yang bisa direset oleh hitung-ulang; lihat KN-G6-IDLE-FAKE).

### intercompany_eliminations — field baru (auto G-6)
`g6_unsold_ratio` · `g6_subtotal_effective` · `g6_cost_effective` · `g6_qty_base` ·
`g6_qty_remaining` — jejak angka yang dipakai mesin eliminasi, dibaca invarian
INV-IC-03 & layar Rapor Margin Grup (satu sumber kebenaran, bukan dua rumus).
**PK-31 — field `g6_*` di atas hanya ada di entri LAMA (satu per pasangan, tanpa `period_key`); entri baru per bulan
di bawah.**

### PK-31 — eliminasi antar-PT per bulan, rantai roll, refund retur sesudah lunas
Mesin: `backend/services/interco_elimination_engine.py` (`pair_state`, `period_entry`, `sync_period`, `eliminations_for`).
| Koleksi · field | Tipe | Arti |
|---|---|---|
| `intercompany_eliminations.period_key` | `YYYY-MM` | Entri otomatis antar-PT **satu per pasangan per bulan** (`source_g6_pair_id` + `period_key`, indeks unik `uq_pair_period`); `effective_date` = hari terakhir bulan; `lines` = keadaan akhir bulan − akhir bulan sebelumnya |
| `.cumulative` / `.previous` | objek | Potret keadaan akhir bulan / akhir bulan sebelumnya `{revenue, cogs, urp, delivered, unsold_ratio, moved_len, sold_len, ic_balance}` |
| `.frozen` | bool | Bulan sudah ditutup di PT penjual DAN pembeli; entri beku tidak ditimpa (hitung ulang yang berbeda → `stale`, INV-IC-03) |
| `.period_label`, `.seller_number` | teks | "Desember 2026"; nomor dokumen penjual |
| `inventory_rolls.cost_basis.chain[]` | larik `{interco_pair_id, interco_number, seller_entity_id, buyer_entity_id, unit_price, previous_unit_cost, at}` | Satu unsur per perpindahan antar-PT (`interco_service.on_warehouse_task_executed`); retur antar-PT membuang unsur pasangan asal; potongan roll mewarisi `cost_basis`. Tingkat atas `cost_basis` tetap = perpindahan terakhir. Roll lama tanpa `chain` dikenali dari `cost_basis.interco_pair_id` |
| `interco_transactions.refund_due`, `.refund_paid`, `.refund_ids` | angka · larik | `refund_due = max(0, returned_amount + settled_amount − grand_total)` (ditulis `interco_return_service._refresh_origin`, kedua dokumen kembar); `refund_paid` dinaikkan CAS oleh refund; `refund_ids` = id refund yang sudah diterapkan |
| `interco_accounts.refund_due`, `.refund_paid`, `.refund_outstanding`, `.refund_count` | angka | Σ per arah dagang; `refund_outstanding` = Σ (`refund_due − refund_paid`); tidak masuk `outstanding` |
| `interco_settlements.kind` | `settlement` (bawaan, field tidak ada) · `refund` | Refund (`POST /api/interco/refunds`, izin `interco.settle`): `payer_entity_id` = PT penjual; jurnal `{id}:payer` Dr 1-1250 / Cr kas, `{id}:payee` Dr kas / Cr 2-1250; kas kembar `ref_type="interco_settlement"` |
Migrasi entri lama → per bulan: `scripts/migrasi_pk31_eliminasi_per_periode.py` (baca-saja; `--apply` = H3).
⚠️ JANGAN membuat koleksi eliminasi kedua (`interco_eliminations`, `consolidation_entries`) — pakai `intercompany_eliminations`.

### customer_prices — F1b (D-14) **Daftar Harga per Pelanggan** (harga langganan)
Collection: `customer_prices`   Prefix: `cpr_`   Router: `routers/customer_prices.py`
Service: `services/customer_price_service.py`   SCOPED via `entity_id` (entity_scope.SCOPED_COLLECTIONS).

Menjawab "harga tetap pelanggan X untuk produk Y" — beda dari `entity_prices` (harga per PT)
dan dari `price_approvals` (izin potong harga). Rantai resolusi SATU definisi
(`customer_price_service.resolve_many`, dipakai SO, POS, dan grid):
    harga khusus disetujui → harga pelanggan → harga PT → harga umum (`products.price`)

Field: `{id, entity_id, customer_id, customer_name, product_id, sku, product_name,
base_unit, sell_price (per base unit), currency, valid_from, valid_until, is_listed,
status (active|pending_approval|rejected|inactive), price_approval_id, guard{...},
note, created_by, created_by_id, approved_by/approved_at | rejected_by/rejected_at |
revoked_by/revoked_at, created_at, updated_at}`

PENJAGAAN HARGA: harga di bawah batas bawah (harga PT / HPP — dihitung
`services/price_guard_service.py`, diatur 3 kunci `pricelist.customer_price_*` di Pusat
Pengaturan) TIDAK langsung berlaku. Record disimpan `pending_approval` dan pengajuan
dibuka di `price_approvals` (`source="customer_pricelist"`, `customer_price_id`) —
MESIN PERSETUJUAN YANG SUDAH ADA, bukan koleksi/alur baru. Approve → record `active`;
reject → `rejected`; aturan diakhiri (`/revoke`) → record `inactive`.

⚠️ JANGAN BUAT koleksi baru: `customer_pricelists`, `harga_pelanggan`,
`contract_prices` — gunakan `customer_prices`.
⚠️ Record `price_approvals` yang punya `customer_price_id` BUKAN aturan harga khusus
tersendiri (hanya jejak keputusan) → dikecualikan dari resolusi aturan STANDING.

### price_approvals — field baru (F1b)
`source` (`sales_request` bawaan | `customer_pricelist`) · `customer_price_id` ·
`guard{floor, floor_from, threshold, basis, hpp, entity_reference, below_floor, gap,
gap_pct, margin_pct, reasons[], summary, tolerance_pct}` (snapshot batas bawah saat
diajukan) · status baru `cancelled` (pengaju menarik) dan `revoked` (approver
mengakhiri aturan yang sudah disetujui, lewat `POST /api/price-approvals/{id}/revoke`
— sebelumnya aturan `approved` TIDAK BISA dihentikan sama sekali) ·
`revoked_by`/`revoked_by_name`/`revoked_at`.

---
## ADDENDUM — FASE D (Permintaan Desain + peran ke-7 `designer`) · 2026-08-20

### design_requests   *(prefix `dsr_` · nomor `<ENT>/DSR-#####` · SCOPED `entity_id`)*
**PERMINTAAN DESAIN ("Design PO")** — dokumen **PEKERJAAN DESAIN**: siapa mengerjakan,
kapan tenggatnya, dan apa keputusan atasannya. Sebelum ini penugasan desain hidup di
WhatsApp, jadi tidak ada satu pun angka yang bisa menjawab "desain ini diminta siapa,
untuk pesanan mana, berapa lama dikerjakan, dan berapa kali direvisi".

Collection: `design_requests`   Prefix: `dsr_`   Router: `routers/design_requests.py`
Service: `services/design_request_service.py`   Schema: `schemas_design_request.py`
SCOPED via `entity_id` (`entity_scope.SCOPED_COLLECTIONS`) · `doc_refs` type
`design_request` · dipantau `scripts/gate_residue.py` WATCH · index di `indexes.py`.

```
id · number (<ENT>/DSR-#####) · entity_id · line_code        (FASE L: snapshot lini)
source (so | customer | internal)
so_id · so_number · customer_id · customer_name
requested_by · requested_by_id · requested_at
assigned_to · assigned_name · division · assigned_at         (desainer)
due_date · brief (min. 5 huruf) · target_type (motif | pattern | artwork)
color_targets[] {color_id, code, name, hex}                  (dari Pustaka Warna)
status: draft → submitted → assigned → in_progress → delivered → approved
        (+ revision → kembali ke desainer · cancelled)
gallery_ids[]            (hasil kerja → `design_gallery`, 1..n VERSI)
delivered_at · decided_by · decided_at · reject_reason · revision_count
cancelled_reason · history[] · created_at · updated_at
```

**BATAS TEGAS ANTAR TIGA DOKUMEN DESAIN** (melanggarnya = melahirkan dokumen ke-4 yang
saling menimpa, dan rapor mana pun jadi tidak bisa dipercaya):
* `design_requests` = **pekerjaan siapa & kapan** (penugasan · tenggat · keputusan)
* `design_gallery`  = **artwork-nya** (berkas · versi · kode `DSG-…` · ACC · bintang)
* `md_specs`        = **angka tekniknya** (gramasi · lebar · konstruksi → melahirkan produk)

* **RBAC** (modul `design_request`, `permissions_config.py`):
  `view` admin·manajer·Admin Sales·**Desainer** (desainer: HANYA tugasnya — pagar
  kepemilikan di router, pola E8.4) · `create` admin·manajer·Admin Sales ·
  `update`/`assign`/`decide`/`cancel` admin·manajer ·
  `deliver` admin·manajer·**Desainer** · `report` admin·manajer.
* **Antrean keputusan**: `approval_backlog_service.QUEUES` baris `design_request`
  (`status="delivered"`) → muncul di KPI beranda & Pusat Persetujuan. Pintunya
  (`/approve`, `/reject`) terdaftar di `verify_approval_queues.DOOR_QUEUE`
  (**INV-APPR-01**) dan punya hitung-ulang mandiri di `verify_home_kpi.EXPECT`
  (**INV-HOME-01**). `revision` SENGAJA tidak dihitung: bolanya sudah kembali ke
  desainer, bukan di meja atasan.
* **Alasan WAJIB** saat minta revisi / batal (`reason`) — revisi tanpa alasan adalah
  cara termurah membuat desainer mengulang kerja tanpa tahu apa yang salah.
* **`deliver` wajib menunjuk artwork NYATA** di `design_gallery` badan usaha yang sama
  (bukan catatan bebas "sudah dikirim lewat email").
* **Jejak dua arah**: dibuat dari SO → `doc_refs.safe_link(design_request ↔ sales_order,
  "parent")`; panel "permintaan desain untuk pesanan ini" lewat
  `GET /api/design-requests-for-so/{so_id}`.
* **Rapor**: `GET /api/design/reports/by-designer` (lintas desainer — izin `report`,
  wewenang atasan) dan `GET /api/design/reports/mine` (**angka DIRI SENDIRI** — izin
  `view` saja, tanpa satu nama rekan pun; pola privasi PS-18 seperti
  `/rnd/reports/my-kpi`). Keduanya dihitung dari dokumen, tidak pernah diketik.
* Layar: `features/design/DesignRequestsView.jsx` (papan kanban + daftar berhalaman
  + Unduh CSV) · `DesignRequestCreateModal` · `DesignRequestDetailPanel` ·
  `DesignerReportPanel` · `MyDesignerReportPanel`. Nav: hub **Desainer**
  (`designer-hub`) tab "Permintaan Desain".

⚠️ **JANGAN BUAT** koleksi baru: `design_orders`, `design_po`, `permintaan_desain`,
`design_tasks`, `design_assignments` — gunakan `design_requests`.
⚠️ **JANGAN** menyimpan berkas/versi artwork di sini (itu `design_gallery.files[]`),
dan JANGAN menyimpan gramasi/lebar/konstruksi di sini (itu `md_specs`).

### design_gallery — field baru (FASE D)
`request_id` — tautan balik ke `design_requests` yang melahirkan artwork ini (satu
permintaan boleh punya beberapa versi, jadi relasinya 1-permintaan → n-galeri).
Perbaikan **DRIFT D4**: `code` (`DSG-<slug>-NN`) kini WAJIB terisi saat artwork dibuat;
`scripts/migrate_design_codes.py` mengisi entri lama (idempotent).

### users — peran ke-7 `designer` (FASE D)
`users.role` menerima `designer` (registry: `backend/role_registry.py`, cermin layar
`frontend/src/config/roles.js`). **Bukan** koleksi baru — peran adalah nilai, bukan
entitas. Wilayahnya SENGAJA sempit: papan pekerjaannya + galeri karyanya + Profil Saya.
Akun demo: `designer@kainnusantara.id` (lihat `memory/test_credentials.md`).
⚠️ Daftar peran TIDAK boleh di-hardcode lagi di gate/POC — baca dari registry
(pelajaran FASE D: `check_nav_map.py` CRASH `KeyError: 'designer'` karena daftar basi).

### ocr_samples · ocr_sample_runs — Sampel Uji OCR (2026-09-28)
`ocr_samples` (prefix `ocs_`, SCOPED per entitas): foto SJ nyata (`files[]` — path storage, boleh berbagi
dengan `goods_receipts.files[]`) + kunci jawaban `answer {dn_number, dn_date, supplier_name, lines[{qty, unit,
rolls, po_ref, is_non_stock}]}` yang dicek manusia. `ocr_sample_runs` (prefix `ocr_run_`, SCOPED): hasil uji per
sampel + ringkasan akurasi per field (gerbang: nomor SJ ≥98%, qty & satuan ≥95%). Layanan:
`backend/services/ocr_sample_service.py`, router `/api/ocr-samples`.
`supplier_dn_profiles` — field baru: `corrections[]` (koreksi manusia terakhir, maks 30) & `format_notes`
(catatan admin) → dikirim ke AI sebagai petunjuk saat membaca SJ mitra yang sama (belajar dari koreksi).

## KF-T6 — kontrol "harus dua orang" (field pengaju & potret aturan)

Aturan "pengaju tidak boleh memutuskan sendiri" dibaca dari `kontrol.<aksi>.min_orang` / `.batas_nominal`
(`backend/config_catalog_kontrol.py`, pembantu `services/dual_control.py`). Titik pengajuan yang dulu hanya menyimpan
NAMA pengaju kini juga menyimpan id akun (pembanding nama tetap dipakai untuk dokumen lama):

| Koleksi · field baru | Diisi oleh |
|---|---|
| `warehouse_transfers.requested_by_id` | `POST /transfers`, `POST /transfers/inter-company` |
| `cycle_count_sessions.submitted_by_id` | submit sesi opname |
| `purchase_returns.created_by_id` | `POST /purchase-returns` |
| `hr_payroll_runs.submitted_by_id` | `submit_run` |
| `cash_advances.created_by_id`, `cash_advance_settlements.created_by_id` | buat pengajuan dana / LPJ |
| `makloon_orders.steps[].claim.proposed_by_id` | `propose_claim` |

Potret aturan saat diputus (dibaca invarian `scripts/verify_data_integrity.py`): `period_unlock_requests.kontrol_dua_orang`
(INV-CLS-02) dan `doc_amendments.kontrol_dua_orang` (INV-AMD-02) = `{dua_orang, sendiri, admin_sendiri}`. Sakelar lama
`approval.matrix_sod` dan `amendment.dual_control` berstatus `not_used` (dipindahkan sekali jalan, penanda
`system_settings{scope:"__migrations__"}.kft6_kontrol`). Jejak Admin yang memutuskan sendiri: `approval_matrix_log`
`outcome = "diputuskan sendiri oleh admin"` (`stage` = nama aksi).


## TX-T1 — potret aturan pajak di dokumen & data pajak pelanggan (K-33)

Aturan pajak per PT dibaca SATU pintu `backend/services/tax_config_service.py` (`tax_settings(entity_id, at)`) dari
kunci Pusat Pengaturan `tax.ppn_rate`, `tax.dpp_nilai_lain`, `tax.ppn_mode`, `tax.dpp_nilai_lain_pembilang` / `_penyebut`,
`tax.pembulatan_tingkat`, `tax.pembulatan_satuan`, `tax.kode_transaksi_diizinkan`, `tax.kode_transaksi_bawaan`,
`tax.kode_transaksi_bawaan_dpp_nilai_lain` (lapisan PT + jadwal "berlaku sejak"; PT bukan PKP → tarif 0).

| Koleksi · field baru | Isi | Ditulis oleh |
|---|---|---|
| `sales_orders.tax_snapshot`, `purchase_orders.tax_snapshot`, `vendor_bills.tax_snapshot`, `tax_invoices.tax_snapshot` | `{ppn_rate, dpp_nilai_lain, dpp_pembilang, dpp_penyebut, ppn_mode, pembulatan_tingkat, pembulatan_satuan, is_pkp, berlaku_pada}` — aturan saat dokumen dibuat (D3: tidak pernah dihitung ulang; hitung ulang dokumen = DARI potret). Faktur: potret pesanannya; dokumen lama tanpa potret dianggap 11/12 · per dokumen · dua desimal (`asal: "dokumen_lama"`, tanpa migrasi) | `compute_order_pricing` (`create_order`, pembuat PO/tagihan pemasok), `tax_invoice_service`, `interco_tax_service` |
| `sales_orders.items[].ppn_amount` | PPN baris — HANYA bila `pembulatan_tingkat = baris` | `compute_order_pricing` |
| `sales_orders.tax_override_by` | Nama pembuat pesanan tanpa PPN (melengkapi `tax_override_reason` PK-45) | `create_order` |
| `interco_transactions.tax_dpp_pembilang` / `tax_dpp_penyebut` | Faktor DPP nilai lain saat transaksi antar-PT dibuat | `interco_service.create` |
| `customers.tax_profile` | `{id_type: npwp·nik·"", nik, tax_name, tax_address, is_pkp: true·false·null, kode_transaksi ("" = ikut PT), always_tax_invoice}` — `customers.npwp` tetap pemilik nomor NPWP | `POST/PATCH /api/customers` (izin `customer.update`), `tax_config_service.periksa_profil_pajak` |
| `tax_invoices.customer_tax` | Potret pembeli: `{id_type, id_number, tax_name, tax_address, is_pkp}` | `tax_invoice_service` |
| `tax_invoices.data_incomplete` | Daftar kekurangan: `identitas_pajak`, `alamat_pajak` (penerbitan tidak ditolak di TX-T1) | `tax_invoice_service` |
| `products.tax_treatment` / `products.tax_item_code` | `kena` (bawaan) · `dibebaskan` · `tidak_dipungut` / kode barang pajak — disimpan & ditampilkan, **belum dipakai mesin** | `POST/PATCH /api/products` |

⚠️ Kode transaksi sah faktur = `tax.kode_transaksi_diizinkan` PT (dulu konstanta `KODE_TRANSAKSI_VALID`); bawaan faktur =
kode pelanggan → bawaan PT menurut DPP nilai lain (`default_kode`).

## PK-22 — penggajian: tanggal buku, hitung ulang, batal, anulir, setoran kewajiban

`hr_payroll_runs` — daur `draft → pending_approval → approved → posted → paid`; batal dari tiga status pertama →
`cancelled`; anulir dari `posted` → `void` (status antara `posting`, `paying`, `voiding` = klaim langkah). Proses
`cancelled`/`void` tidak menghalangi proses baru PT+periode yang sama (`hr_payroll_service.existing_run`). Kunci jurnal
gaji, bayar, dan pembaliknya = **id proses** (`gl_service.payroll_source_id`; proses lama tetap "{entity_id}:{period}").

| Field baru | Arti | Ditulis oleh |
|---|---|---|
| `journal_date` | Tanggal buku jurnal gaji (`periodic_posting.journal_date`: akhir periode atau hari posting, `gl.tanggal_jurnal_periodik`) | `post_run_gl` (klaim) |
| `gl_status`, `gl_error`, `gl_failed_at`, `journal_entry_id` | Penanda jurnal gaji (PK-18); `failed` → proses tetap `approved`, tampil di Posting Gagal jenis `payroll_run` | `post_run_gl` lewat `post_durable` |
| `pay_gl_status`, `pay_gl_error`, `pay_journal_entry_id` · `void_gl_status`, `void_gl_error`, `void_journal_entry_id` | Penanda jurnal bayar / pembalik (gagal → status kembali `posted`) | `pay_run`, `void_run` |
| `recalculated_at`, `recalculated_by`, `recalculated_by_id`, `recalc_count`, `recalc_claim` (sementara) | Jejak hitung ulang draf (slip diperbarui di tempat) | `recalculate_run` |
| `cancelled_by`, `cancelled_by_id`, `cancelled_at`, `cancel_reason`, `cancelled_from` | Jejak batal | `cancel_run` |
| `voided_by`, `voided_by_id`, `voided_at`, `void_reason`, `void_journal_id`, `void_journal_number` | Jejak anulir | `void_run` |
| `created_by_id`, `approved_by_id`, `rejected_by_id`, `posted_by`, `posted_by_id`, `paid_by`, `paid_by_id` | Id pelaku tiap langkah (kontrol dua orang KF-T6 `kontrol.proses_gaji.*` pada sahkan, posting, bayar) | langkah masing-masing |

`hr_payslips.status` mengikuti proses (`cancelled`, `void`).

| Collection | Prefix/ID | Penulis (SSOT) | Pembaca | Catatan |
|-----------|-----------|----------------|---------|---------|
| `hr_statutory_remittances` | `strm_` (id dari kunci idempotensi bila ada) + `number` `STR-` per PT | `services/hr_remittance_service.py:create_remittance` / `finish_remittance` | `GET /api/hr/payroll/remittances`, `/outstanding`; `PayrollRemittancesView` | **PK-22 (FY-07)** setoran hutang BPJS (2-1700, `sdm.hutang_bpjs`) dan PPh 21 (2-1800, `sdm.hutang_pph21`): `kind` (`bpjs`·`pph21`), `period` (masa gaji), `amount`, `paid_date` (= tanggal jurnal), `account_id` (rekening), `cash_type`, `contra_account_code`, `cash_txn_id`, `journal_entry_id`, `status` (`pending` → `done`), `gl_status`/`gl_error`, `reference`, `notes`, `created_by(_id)`. Satu setoran = satu kas keluar `ref_type="statutory_remittance"` (pembuat kas PK-20) → jurnal kas Dr hutang / Cr kas. Sisa kewajiban masa = Σ `totals` proses `posted`/`paid` (BPJS = `bpjs_emp + bpjs_er`, PPh 21 = `pph21`) − Σ setoran masa itu. Indeks `(entity_id, period, kind)` tidak unik; `uq_id`. **SCOPED**. |

## PK-25 — dokumen antar-PT dari kasus "pelanggan membayar ke PT yang salah"

| Koleksi · field | Tipe | Arti |
|---|---|---|
| `interco_loans.kind` | `pinjaman` (bawaan; dokumen lama tanpa field = pinjaman) · `salah_transfer` | Jenis dokumen kembar di koleksi pinjaman antar-PT. `salah_transfer` lahir dari `interco_loan_service.create_from_case` saat kasus `salah_entitas` diselesaikan |
| `interco_loans.origin` | `{kind: "finance_case", id, number}` | Kasus asal dokumen `salah_transfer` |
| `interco_loans.pair_id` / `id` | `iclp_case_{id kasus}` · `icl_case_{id kasus}_l` (PT pemilik tagihan, `role="lender"`) / `_b` (PT penerima uang, `role="borrower"`) | Tetap per kasus — sisip bersyarat, tanpa nomor baru saat diulang; `uq_id` |

Dokumen `salah_transfer` lahir `status="disbursed"`, `outstanding = nominal`, TANPA kas dan TANPA jurnal pencairan (jurnal
kedua buku = jurnal kembar kasus: PT penerima Dr 2-1950 / Cr 2-1250, PT pemilik Dr 1-1250 / Cr 1-1200). Saldonya dibaca
`interco_money_service.non_trade_outstanding` (Saldo Antar-PT non-dagang) dan dieliminasi otomatis; pelunasan lewat
`repay` yang ada (kas kembar + jurnal di dua buku).

## KM-T1 — Meja Insentif: target per PT, komponen, definisi angka, fakta omzet terkirim & pencairan

`sales_targets` — **kunci baru** (`entity_id`, `sales_id`, `period_type`, `period`), indeks unik WAJIB-ADA
`uq_target_pt_sales_periode` (D7; baris tanpa `entity_id`/`period_type` belum ikut sampai
`scripts/migrate_sales_targets_km_t1.py` — data nyata H3, kunci kembar H6). Ditulis `services/incentive_targets.py:save_target`
(PUT `/api/incentive/targets`; KM-T1 (b): juga `POST /api/sales-targets` lama — layar "Set Target" sampai KM-T5 —
dengan `period_type = "month"` dan PT konteks; **KM-T5: `GET`/`POST /api/sales-targets` dihapus**) dan `copy_targets`.

| Field | Arti |
|---|---|
| `entity_id` | PT target = PT konteks pengguna (N1), **bukan** PT asal sales |
| `sales_id`, `sales_name` | Akun aktif mana pun yang ditugaskan di PT itu (`allowed_entity_ids`/`home_entity_id`) |
| `period_type`, `period` | `month` `YYYY-MM` · `quarter` `YYYY-Qn` · `year` `YYYY`; triwulan & tahun mengikuti tahun buku PT (`YYYY` = tahun berakhirnya, K-24; `services/incentive_periods.py:period_bounds`) |
| `target_sales_amount`, `target_collection_amount` | Angka ≥ 0, **tersendiri** per jenis periode (triwulan/tahun tidak dijumlah dari bulan) |
| `target_new_customers`, `notes`, `copied_from` | — |
| `created_by`, `created_at`, `updated_by`, `updated_at` | Jejak |

| Collection | Prefix/ID | Penulis (SSOT) | Pembaca | Catatan |
|-----------|-----------|----------------|---------|---------|
| `incentive_components` | `icomp_` | `services/incentive_targets.py:create_component` / `update_component` | `GET /api/incentive/components`; `IncentiveSetupView` | Per PT: `code` (huruf besar, unik per PT — indeks `uq_component_code` WAJIB-ADA), `name`, `basis_period_type` (`month`·`quarter`·`year`·`free`), `columns` (⊆ `omzet`·`pencairan`·`harga`), `taxable` (bawaan ya), `is_active`, jejak. Tanpa isi bawaan. **SCOPED**. |
| `incentive_definitions` | `idef_` | `services/incentive_definitions.py:current_definition` (hanya-tambah) | `GET /api/incentive/definitions/current`; KM-T3 (potret lembar) | Versi definisi angka per PT: `version` (naik; unik per PT `uq_definition_version` WAJIB-ADA), `effective_from` (tanggal WIB terbaca), `dasar_omzet`, `isi_pencairan`, `pemilik_angka`, `harga_acuan`, `recorded_at`. Pemilik nilai = Pusat Pengaturan (`insentif.*`, `config_catalog_insentif.py`); versi baru disisipkan bila nilai PT berbeda dari versi terakhir. **SCOPED**. |
| `fact_shipment_sales` | `_id` = `<source_kind>:<source_id>:<line_idx>:<sales_id>` | `services/incentive_facts.py` (`rebuild`, `sync`; tugas `incentive_fact_sync` 5 menit, `incentive_fact_nightly` 02.30 bangun ulang 90 hari) | `GET /api/incentive/reconciliation`; KM-T2 | **TURUNAN** (D2). Satu dokumen per (sumber × baris pesanan × sales). `source_kind` `kirim` (surat jalan; nilai bersih pesanan × `shipment_value_share`, surat jalan terakhir pesanan `shipped`/`done` mengambil sisa) · `retur` (nota kredit retur, negatif) · `koreksi` (nota kredit amandemen / batal item OD berjurnal, negatif) · `pesanan_lama` (pesanan berpendapatan tanpa surat jalan); `source_id`, `source_number`; dari pesanan `entity_id`, `so_id`, `so_number`, `customer_id`, `customer_name`, `line_idx` (kosong untuk nota kredit); `sales_id`, `split` (dari `sales_attribution`; `""` = tanpa sales); `product_id`, `sku`, `category`, `line_code`, `price_source`, `qty_base`; `net` (tanpa PPN × split); `list_value`, `global_value`, `floor_value` (`net × pembanding ÷ price`, kosong bila pembanding kosong); `cost`, `cost_known`; `date_wib` (= tanggal jurnal pendapatannya), `period`, `built_at`, `build_gen`. Indeks (`entity_id`,`date_wib`), (`entity_id`,`sales_id`,`date_wib`), (`so_id`). Invarian INV-KM-1 (= mutasi akun pendapatan penjualan) dan INV-KM-3 (`scripts/verify_data_integrity.py` lapisan `incentive`). **SCOPED**. |
| `fact_collections` | `_id` = `<so_id>:<id baris payments>:<sales_id>` | `services/incentive_facts.py` (sama) | sama | **TURUNAN** (D2). Satu dokumen per (baris `sales_orders.payments[]` × sales): `entity_id`, `so_id`, `so_number`, `customer_id`, `sales_id`, `split`, `receipt_id`, `receipt_number`, `source_kind` (= `ar_allocation_service.payment_kind`: `kas`·`deposit`·`titipan_bank`·`saldo_kredit`·`nota_kredit`·`hapus_sisa`·`kasus`), `method`, `is_reversal` (baris ber-`reverses` — pembatalan mengurangi periode batal), `amount` (± × split), `date_wib`, `period`, `settles_order`, `giro_uncleared` (giro dihitung pada tanggal kwitansi sampai PM-T3), `built_at`, `build_gen`. Kwitansi lama tanpa `kind` yang memakai deposit dalam satu baris: deposit dianggap terpakai lebih dulu menurut urutan `allocations[]` (baris `…:deposit`). Invarian INV-KM-2 (pencairan + kas belum dialokasikan = kwitansi = kas masuk) dan INV-KM-3. **SCOPED**. |

Tanda air kedua fakta: `ai_fact_state` id `fact_shipment_sales` / `fact_collections` (`watermark`, `last_sync_at`,
`last_rebuild_at`, `build_lock_until` = satu pembangun pada satu waktu).

**KM-T1 (b) — field baru pesanan (`routers/sales_orders.py:create_order`, semua pesanan baru):**

| Field | Arti |
|---|---|
| `items[].list_price` | Harga daftar PT per satuan jual saat pesanan dibuat; PT belum punya harga → harga umum (K-23) |
| `items[].list_price_source` | `entity` (harga daftar PT) · `global` (harga umum) |
| `items[].global_price` | Harga umum (`products.price`) per satuan jual |
| `items[].floor_price`, `items[].floor_from` | Batas bawah `price_guard_service.floor_for` per satuan jual (kosong bila tidak ada batas); asal batas (`entity_price` · `hpp`) |
| `sales_attribution` | `[{sales_id, split}]` — potret pemilik angka saat pesanan dibuat (`analytics_facts.attribute_sales` mode tim; K-21). Dibaca `incentive_facts` dan `analytics_facts.build_rows` (mode tim); pesanan lama tanpa potret memakai aturan tim |

Pesanan lama: `scripts/backfill_order_price_refs.py` mengisi `list_price = price` hanya untuk baris ber-`price_source`
`entity`/`global` (baris lain dibiarkan kosong dan dilaporkan). Target lama: `scripts/migrate_sales_targets_km_t1.py`
(`YYYY-MM` → `period_type = "month"`, `entity_id` kosong → PT asal sales; kunci kembar = H6). Serah-terima pelanggan
(`POST /api/customers/{id}/reassign`) kini juga mengganti anggota `pic` `customers.sales_team` (pendamping tetap) dan hanya
menerima akun dari `incentive_targets.sales_roster` PT pelanggan (KM-06).

## KM-T3 — Lembar Insentif: dokumen keputusan dengan nominal diketik dan angka dasar dipotret

| Collection | Prefix/ID | Penulis (SSOT) | Pembaca | Catatan |
|-----------|-----------|----------------|---------|---------|
| `incentive_sheets` | `isheet_` (baris `iline_`); nomor `{KODE PT}/LIN-00001` (`doc_number_kinds` `lin`, per PT) | `services/incentive_sheet_service.py` (`create_sheet`, `add_line`, `patch_line`, `delete_line`, `refresh_sheet`, `submit_sheet`, `approve_sheet`, `return_sheet`, `cancel_sheet`; semua lewat `_simpan` = pembaruan bersyarat status lama + `rev`) | `GET /api/incentive/sheets[/{id}]`, ekspor `.xlsx`; antrean Pusat Persetujuan `incentive_sheet` (`{status: "submitted"}`); KM-T4 (`incentive_payroll`: gaji, jurnal, tanda bayar) | **KM-T3 (KM-05, K-25)**. `entity_id` (PT konteks, N1), `pay_period` (`YYYY-MM` bulan penggajian), `title`, `status` (`draft`·`submitted`·`approving` (KM-T4, status antara pengesahan di PT bermode `sheet`)·`approved`·`paid`·`cancelled`; `paid` ditulis KM-T4), `lines[]`, `active_keys[]` (`<sales_id>\|<component_id>\|<basis_period>` tiap baris bukan penyesuaian; dikosongkan saat `cancelled`), `totals` `{lines, amount}` (Σ nominal rupiah bulat), `prepared_by`/`submitted_by`/`approved_by`/`returned_by`/`cancelled_by` `{id, name}`, `submitted_at`, `approved_at`, `returned_at`+`return_reason`, `cancelled_at`+`cancel_reason`, `created_at`, `updated_at`, `rev`, `history[]` `{action, by_id, by_name, at, reason, from_status, to_status}` (hanya-tambah: buat, segarkan, ajukan, sahkan, kembalikan, batal). Indeks: unik `number` (UNIQUE_DOC_NUMBER_FIELDS), unik WAJIB `uq_isheet_active_key` (`entity_id`, `active_keys`, parsial `active_keys` teks terisi) — satu (sales, komponen, periode dasar) diputus sekali di lembar yang masih berlaku; (`entity_id`, `pay_period`, `status`), (`entity_id`, `status`, `created_at`). Lembar `approved`/`paid`/`cancelled` tidak bisa diubah; koreksi = baris penyesuaian di lembar lain. KM-T3 tidak menjurnal; KM-T4 di bawah. **SCOPED**. |

Baris (`incentive_sheets.lines[]`):

| Field | Arti |
|---|---|
| `id` | `iline_…`, tetap seumur baris |
| `sales_id`, `sales_name`, `employee_id` | Akun sales yang ditugaskan di PT (`incentive_targets.assigned_user`); karyawan tertaut `hr_employees.user_id` (boleh kosong sampai KM-T4) |
| `component_id`, `component_code`, `component_name` | Komponen `incentive_components` PT itu yang aktif; jenis periode baris = periode dasar komponen (komponen `free`: bulan/triwulan/tahun) |
| `basis_period_type`, `basis_period`, `basis_label` | `month` · `2026-10` · "Okt 2026"; `quarter` · `2026-Q3` · "Triwulan III 2026"; `year` · `2026` · "Tahun buku 2026" |
| `snapshot` | Potret saat baris dibuat / disegarkan (draf): `taken_at`, `definition_version`, `definition_effective_from`, `definition` (`dasar_omzet`, `isi_pencairan`, `pemilik_angka`, `harga_acuan`), `basis_from`, `basis_to`, `target_sales`, `omzet`, `retur`, `omzet_bersih`, `pct_omzet`, `target_collection`, `uang_masuk`, `pct_pencairan`, `realisasi_harga_pct`, `porsi_bawah_acuan_pct`, `margin_pct` (dikirim hanya ke pemegang `incentive.view_margin`), `catatan_data`, `fingerprint` (SHA-256 daftar terurut `doc_id:amount` dokumen omzet, retur, uang masuk), `source_counts`. Disalin apa adanya dari pengumpul Capaian `incentive_achievement.angka_sales` (D3) |
| `amount` | Nominal rupiah bulat, **diketik orang** (server tidak pernah mengisi). Negatif hanya pada baris penyesuaian; kosong boleh selama draf |
| `note` | Catatan; wajib untuk baris penyesuaian |
| `is_adjustment`, `adjusts` | Baris penyesuaian dan rujukannya `{sheet_id, sheet_number, line_id}` ke baris bukan penyesuaian lembar `approved`/`paid` PT yang sama untuk sales yang sama |
| `amount_prepared`, `approver_note` | Terisi bila pemutus mengoreksi nominal saat mengesahkan (nominal penyiap + catatan pemutus) |
| `created_by`, `created_at`, `updated_by`, `updated_at` | Jejak baris |

`drift` (jawaban `GET …/sheets/{id}`, tidak disimpan): per baris, angka `omzet_bersih` · `uang_masuk` · `realisasi_harga_pct` yang kini
berbeda dari potret, dihitung dengan definisi yang dipotret baris itu → `{line_id, field, label, snapshot, current, diff}`.

## KM-T4 — Lembar Insentif ke gaji dan buku besar; tagihan insentif antar-PT

Sakelar per PT `hr.payroll_commission_mode` (`hr_payroll_service.commission_mode`, bawaan `accrue_then_settle`): `off` dan
`sheet` mematikan komisi mesin di slip; `sheet` membuat lembar yang disahkan menjadi jurnal dan masukan gaji.

Field tambahan `incentive_sheets` (penulis `services/incentive_payroll.py`, kecuali disebut lain):

| Field | Arti |
|---|---|
| `payroll_linked` | `true` = disahkan saat PT bermode `sheet` (jurnal + masukan gaji); `false` = keputusan saja (`incentive_sheet_service.approve_sheet`) |
| `gl_status`, `gl_error`, `gl_failed_at`, `journal_entry_id` | Hasil `post_durable` jurnal lembar (`posted` · `failed` · `not_required` · `pending`); gagal → Posting Gagal jenis `incentive_sheet` |
| `journal_date` | `periodic_posting.journal_date(PT lembar, bulan terakhir periode dasar paling akhir)` (K-13) |
| `approval_note`, `approving_lease_until` | Catatan koreksi pemutus (masuk riwayat saat selesai); jatah kerja status antara `approving` (2 menit; habis → Sahkan berikutnya meneruskan) |
| `lines[].employee_id`, `lines[].pay_entity_id` | Karyawan aktif tertaut akun sales (`hr_employees.user_id`) dan PT induknya (PT antrean masukan gaji) |
| `lines[].input_key` | `isheet:<id lembar>:<id baris>` = `hr_pay_inputs.source_key` |
| `lines[].paid_run_id`, `paid_run_number`, `paid_at` | Diisi sesudah proses gaji yang memuat masukan baris itu diposting (`tandai_dibayar`); dikosongkan saat proses dianulir (`lepas_dibayar`). Semua baris bernominal terbayar → lembar `paid` |

Masukan gaji (`hr_pay_inputs`, sumber `incentive_sheet`): `entity_id` = PT induk karyawan, `component_code` `INSENTIF`,
`label` "{komponen} — {periode dasar}", `source_ref` `{sheet_id, sheet_number, number, line_id, charge_entity_id}`
(`charge_entity_id` = PT lembar, penanggung beban). Baris slip (`hr_payslips.components[]`) membawa `charge_entity_id` dan
`source.sheet_id`/`line_id`. Komponen `INSENTIF` (isi awal tiap PT): pendapatan, `masukan`, kena pajak, kolom `commission`,
proses `regular` & `susulan`, `system`.

| Collection | Prefix/ID | Penulis (SSOT) | Pembaca | Catatan |
|-----------|-----------|----------------|---------|---------|
| `interco_charges` | `icc_` + SHA-1 (`run_id`\|`to_entity_id`, turunan — ulang posting = tagihan yang sama; `uq_id`); nomor `{KODE PT penagih}/ICC-00001` (`doc_number_kinds` `icc`) | `services/interco_charge_service.py` (`siapkan` saat posting gaji PT penagih, `terbitkan` sesudah jurnal gaji, `settle`, `batal_tertunda`, `batal_void`, `ulang`) | `GET /api/interco/charges[/{id}]` (`interco.view`); `interco_money_service.non_trade_outstanding` (+ `charge_outstanding`, `charge_count`); eliminasi konsolidasi `sync_non_trade_elimination` (`source_non_trade_key` `icc:<id>`); INV-KM-5 | **KM-T4 (K-26)**. `kind` (`incentive`), `entity_id` = `from_entity_id` (PT penagih = PT induk karyawan, yang menggaji), `from_entity_name`, `to_entity_id` (PT tertagih = PT lembar), `to_entity_name`, `amount`, `outstanding`, `status` (`pending` niat sebelum jurnal gaji · `open` · `settled` · `cancelled`), `source` `{run_id, run_number, period, lines: [{sheet_id, sheet_number, line_id, employee_id, employee_name, label, amount}]}`, `journal_date`, `payroll_journal_id`, `journals[]` `{kind: payroll·charge·settlement, entity_id, journal_id}`, `gl_status`/`gl_error`/`gl_journal_id` (jurnal PT tertagih `interco_incentive_charge`, kunci = id tagihan), `void_gl_status` (pembalik saat anulir), `settle_status` (`none`·`settling`), `pending_settlement`, `settle_lease_until`, `gl_status_settle_payer`/`_payee`, `settlements[]` `{seq, amount, date, account_id_from, account_id_to, note, by, by_id, at, cash_ids, cash_numbers, journal_ids}`, `history[]`, `cancel_reason`/`cancelled_by`/`cancelled_at`, `created_by`, `created_at`, `updated_at`. Indeks: unik `number`; unik WAJIB `uq_charge_run_to` (`source.run_id`, `to_entity_id`, parsial `source.run_id` terisi); (`from_entity_id`, `status`, `created_at`), (`to_entity_id`, `status`, `created_at`). Baris jurnal piutang/utang antar-PT tagihan ber-`memo` = nomor tagihan. **SCOPED** (`entity_id`; daftar & pelunasan memakai pihak). |

Jurnal (`journal_entries.source_type`): `incentive_sheet` (lembar; id lembar), `interco_incentive_charge` (sisi PT
tertagih; id tagihan) + `_reversal`, `interco_incentive_charge_settlement` (`<id>:st<n>:a`/`:b`); kas pelunasan
`cash_transactions.ref_type` `interco_incentive_charge_settlement`.

## PK-32 — satu pembuat nota kredit / nota debit (`credit_notes`)

Semua dokumen `credit_notes` lahir lewat **`backend/services/credit_note_service.py::issue`** (satu-satunya penyisip,
INV-POST-01 + uji U12) lalu efeknya dijalankan **`settle`**: retur per barang (`return_service`), retur per roll
(`return_roll_settlement_service.issue_settlement_note`), amandemen (`amendment_service._apply_note`), batal item Pesanan
Khusus (`od_cancel_credit_note`), dan migrasi nota debit lama (`scripts/migrasi_pk32_nota_debit_menunggu.py`). Field lama
dipertahankan; data lama dibaca `credit_note_service.normalize` tanpa migrasi.

| Field | Tipe | Arti |
|---|---|---|
| `kind` | `credit_note` · `debit_note` | Dokumen lama tanpa field = `credit_note` |
| `source` | `sales_return` · `sales_return_roll` · `amendment` · `od_item_cancel` | Nota retur lama tanpa field dibaca dari `settlement_id`/`return_id` |
| `status` | `pending_finance` · `issued` · `posted` · `void` | `issued` = terbit, efek belum tuntas; `posted` = semua efek tuntas. Nilai lama `offset` dibaca `posted`; nota batal item lama `issued` + `accounting` dibaca `posted`. Label layar: Menunggu Finance · Terbit · Selesai · Batal (`status_label` di jawaban API) |
| `effects` | `{allocation, store_credit, journal}` = `pending` · `done` · `skipped` | Penanda langkah `settle`; ulang (panel Posting Gagal jenis `credit_note`) meneruskan dari yang belum `done`. Nota debit: `allocation` = baris tagihan tambahan |
| `gl_status`, `gl_error`, `gl_failed_at`, `journal_entry_id` | seperti PK-18 | Untuk semua sumber |
| `revenue_reversed_net`, `revenue_reversed_ppn` | angka | Nota kredit amandemen/batal item: bagian yang dijurnal saat terbit (= pendapatan yang sudah diakui − porsi terkirim × nilai efektif baru) |
| `revenue_added_net`, `revenue_added_ppn` | angka | Nota debit: bagian yang dijurnal saat terbit (porsi terkirim × nilai nota) |
| `deferred_net`, `deferred_ppn` | angka | Bagian yang tidak dijurnal karena barangnya belum dikirim; diakui surat jalan berikutnya lewat nilai efektif |
| `shipped_share` | 0..1 | Porsi terkirim saat rencana dibuat |
| `ar_part`, `store_credit_part` | angka | Jurnal nota koreksi: Cr 1-1200 sebesar piutang yang masih terbuka; sisanya Cr 2-1450 saldo kredit pelanggan (rujukan `credit_note` = id nota) |
| `excess_payment` | angka | Uang pelanggan di atas nilai efektif baru yang tidak menjadi saldo kredit; tetap uang muka pelanggan (2-1400) |
| `allocation_amount`, `allocation_deferred` | angka | Rencana baris `payments[]` (≤ sisa tagihan); bagian di atas `ar_part` = `nota_tangguh` |
| `debit_note_offset`, `debit_note_offsets[]` | angka / larik | Nota kredit amandemen yang menutup nota debit LAMA yang belum ditagih (perilaku lama dipertahankan) |
| `billing_status` (nota debit) | `billed` | Menggantikan `awaiting_billing_rule` untuk nota baru; nota lama ditagihkan skrip migrasi (H3) |
| `bill_gross`, `bill_ppn`, `migrated_pk32_at`, `migrated_pk32_by` | | Hanya nota debit lama yang ditagihkan skrip migrasi |
| `issued_at`, `posted_at`, `voided_at`, `void_reason`, `voided_by` | | Jejak langkah |

Batas: Σ `gross_amount` nota kredit tidak-`void` sumber retur/roll/amandemen ≤ nilai tagihan + 0,01 (`assert_cap`, 409
"…melebihi nilai pesanan…"; nota batal item tidak dihitung karena total pesanannya sudah turun saat batal). Batal nota
(`void`) hanya `pending_finance`/`issued` tanpa efek `done` (409 "…sudah mengurangi tagihan atau sudah dijurnal…").
Jurnal baru `amendment_debit_note` (Dr 1-1200 / Cr 4-1000 / Cr 2-1200, `ref.order_id`).

## PY-T1 — slip gaji sebagai daftar komponen per PT, antrean masukan

| Collection | Prefix/ID | Penulis (SSOT) | Pembaca | Catatan |
|-----------|-----------|----------------|---------|---------|
| `hr_pay_components` | `pcomp_` | `services/hr_pay_components.py:ensure_defaults` (isi awal tiap PT, saat server menyala dan saat daftar PT pertama dibaca) · `create_component` / `update_component` | `GET /api/hr/payroll/components`; `hr_payroll_service.compute_payslip`; `PayComponentsView` | **PY-T1 (K-37)** komponen gaji per PT: `entity_id`, `code` (huruf besar), `name` (tampil di slip), `kind` (`pendapatan`·`potongan`·`tanggungan_perusahaan`), `calc` (`tetap_bulanan`·`per_jam`·`masukan`·`undang_undang`), `bucket` (kolom lama slip tempat nominalnya dijumlahkan: `base_salary`·`allowances`·`overtime`·`commission`·`other_earnings`·`bpjs_emp`·`bpjs_er`·`pph21`·`other_deductions`), `taxable`, `in_bpjs_base`/`in_overtime_base`/`prorate` (disimpan; **belum dipakai mesin** sampai PY-T3), `statutory_code` (BPJS & PPh 21), `account_code` (wajib untuk potongan non-undang-undang = akun yang dikredit; opsional untuk pendapatan), `allowed_run_types` (`regular`·`thr`·`susulan`), `sort`, `is_active`, `system` (komponen bawaan: tidak bisa dihapus, diganti jenis, atau dinonaktifkan). Isi awal 14 komponen menghasilkan slip yang sama persis dengan hitungan kolom lama. Unik `(entity_id, code)` (`uq_entity_code`, REQUIRED_UNIQUE_INDEXES). **SCOPED**. |
| `hr_pay_inputs` | `pinp_` | `services/hr_pay_inputs.py:enqueue_input` (modul sumber, langsung `approved`) · `create_manual_input` (`pending`) · `approve_input` · `cancel_input(_by_id)` · `take_for_run` · `release_for_run` | `GET /api/hr/payroll/inputs`; proses gaji (serah-terima b); `PayComponentsView` | **PY-T1 (K-37, K-40)** antrean masukan komponen: `employee_id`(+`employee_name`), `pay_period` (`YYYY-MM`, proses gaji PT itu yang dituju), `component_code`(+`component_name`, harus `masukan` & aktif), `label` (teks baris slip), `basis_period`, `amount` (rupiah bulat ≠ 0, boleh negatif), `source_type` (`incentive_sheet`·`overtime`·`cash_advance`·`rapel`·`manual`), `source_key` (unik per baris sumber; kirim ulang = dokumen sama), `source_ref`, `status` (`pending` → `approved` → `used` ⇄ `approved`; `cancelled`), `reason` (wajib untuk manual), `created_by(_id)`, `approved_by(_id)/_at`, `used_run_id`, `used_run_number`, `used_at`, `cancelled_by(_id)/_at`, `cancel_reason`, `cancelled_from`. Pindah status bersyarat status lama. Indeks: unik `source_key` (`uq_source_key`), `(entity_id, pay_period, status)`, `(used_run_id)`. **SCOPED**. |

`hr_payslips.components[]` = `{code, name, label, kind, bucket, amount, taxable, statutory_code?, account_code?, qty?,
rate? (persen), method? (PPh 21), basis_period?, source?: {type, key, id, number?}}` — satu baris per komponen (tunjangan
satu baris per nama di master karyawan, masukan satu baris per masukan). **Kolom lama slip diturunkan dari komponen**
(`hr_pay_components.derive_columns`): tiap kolom = Σ `amount` komponen ber-`bucket` itu; `salary_earnings = base_salary +
allowances + overtime + other_earnings`; `gross = salary_earnings + commission`; `net = gross − bpjs_emp_total − pph21 −
other_deductions`; `tax_gross` = Σ komponen kena pajak. Slip lama tanpa `components` tetap dibaca dari kolomnya.

| Field baru | Arti | Ditulis oleh |
|---|---|---|
| `hr_payroll_runs.run_type` | `regular` · `thr` · `susulan` (proses lama tanpa field = reguler) | `create_run` |
| `hr_payroll_runs.seq` | Urutan proses per PT, periode, jenis | `create_run` |
| `hr_payroll_runs.active_key` | "<PT>:<periode>:regular" — hanya proses reguler yang tidak dibatalkan/dianulir; unik parsial `uq_active_key` (REQUIRED_UNIQUE_INDEXES, menggantikan penjaga baca-lalu-hapus); dilepas saat batal/anulir. Proses lama: `scripts/migrasi_pyt1_proses_gaji.py` | `create_run`, `cancel_run`, `void_run` |
| `hr_payroll_runs.inputs_stale_at` | Masukan yang dipakai proses draf dibatalkan → ajukan ditolak (409) sampai dihitung ulang | `hr_pay_inputs._cancel` / dihapus `recalculate_run` |
| `hr_payroll_runs.totals.other_deductions` | Σ potongan lain (komponen) | `_accumulate` |
| `hr_payslips.run_type`, `other_earnings`, `other_deductions` | Jenis proses; Σ pendapatan lain (THR, bonus, …); Σ potongan lain (berakun) | `compute_payslip` |
| `hr_payslips.pph21_month`, `pph21_month_detail` | PPh 21 gabungan bulan (bruto pajak slip ini + slip terdahulu bulan itu di proses lain yang hidup dan dibuat lebih dulu) dan rinciannya `{tax_gross_month, rate, prior_pph21, prior[]}`; `pph21` slip = `pph21_month − prior_pph21` | `compute_payslip` |

Jurnal gaji dari komponen (`gl_service.payroll_journal_lines`): pendapatan → Dr 6-1000 (atau `account_code` komponen),
komisi menurut `commission_mode`, tanggungan → Dr 6-1100, BPJS → Cr 2-1700, PPh 21 → Cr/Dr 2-1800, potongan lain → Cr
`account_code` komponen, bersih → Cr 2-1600; kunci = id proses (PK-22). PDF slip dari `hr_payroll_pdf.payslip_pdf_rows`.

## PY-T2 — riwayat kompensasi dan penugasan PT karyawan bertanggal berlaku

| Collection | Prefix/ID | Penulis (SSOT) | Pembaca | Catatan |
|-----------|-----------|----------------|---------|---------|
| `hr_compensation_history` | `hcomp_` | `services/hr_compensation_service.py:propose_compensation` (`pending`) · `decide_compensation` (sahkan / tolak / batal, bersyarat status lama) · `initial_rows` (karyawan baru `POST /hr/employees`, migrasi `scripts/migrate_hr_compensation_py_t2.py`) | `segments` / `employees_for_run` (proses gaji), `compensation_at`, `rapel_lines`, `master_drift` (INV-PY-2); `GET /api/hr/employees/{id}/compensation`; kartu karyawan (`EmployeeCompensationSection`) | **PY-T2 (PY-09, K-37, K-38)** per karyawan (TIDAK ber-PT — PT pada tanggal berlaku dibaca dari penugasan): `employee_id`(+`employee_name`), `effective_from` (`YYYY-MM-DD`), `effective_to` (diisi sistem: sehari sebelum baris sah berikutnya; kosong = terbuka), `base_salary` (rupiah ≥ 0), `fixed_components[]` `{component_code, label, amount}` (komponen `tetap_bulanan` PT selain Gaji Pokok, mis. TUNJANGAN berlabel nama tunjangan), `status` (`pending`·`approved`·`rejected`·`cancelled` — hanya `approved` dibaca proses gaji), `reason`, `source` (`manual`·`migrasi`), `proposed_by`/`approved_by` `{id, name}`, `proposed_at`, `approved_at`, `decision_reason`, `rejected_by/_at`, `cancelled_by/_at`, `applied_at`. Baris sah paling awal berlaku sejak awal (prorata masuk/keluar = PY-T3). Unik parsial `(employee_id, effective_from)` untuk `status: "approved"` (`uq_employee_effective_approved`, REQUIRED_UNIQUE_INDEXES); indeks `(employee_id, status, effective_from)`. Nilai gaji = data pribadi: baca butuh `hr.view_pii`. |
| `hr_employee_assignments` | `hasg_` | `services/hr_compensation_service.py:propose_assignment` (`pending`; PT tujuan dalam cakupan pelaku, departemen/jabatan milik PT tujuan) · `decide_assignment` · `initial_rows` | `employees_for_run` (pemilihan karyawan proses gaji per PT), `assignment_at`, `master_drift`; `GET /api/hr/employees/{id}/compensation` | **PY-T2** PT tempat karyawan digaji: `employee_id`, `entity_id` (PT tujuan), `effective_from`, `effective_to`, `department_id`, `position_id`, `status`, `reason`, `source`, `proposed_by`, `approved_by`, `approved_at`, `applied_at` (departemen/jabatan disalin ke master saat baris pertama kali berlaku). Unik parsial sama (`uq_employee_effective_approved`); indeks `(employee_id, status, effective_from)`, `(entity_id, status)`. **SCOPED**. |

Aturan hitung (`hr_compensation_service.build_segments`, pengaturan `hr.prorata_perubahan_gaji` global → PT, bawaan
`mati` = perilaku sebelum PY-T2): `mati` → satu potongan sebulan penuh bernilai baris yang berlaku pada hari terakhir
periode (atau hari terakhir bekerja); PT pada hari itu yang menggaji. `hari_kalender` → potongan menurut perubahan
kompensasi dan penugasan di PT itu; baris slip "{nama} ({tgl awal}–{tgl akhir} {bulan})" = nilai × hari ÷ hari kalender
(rupiah penuh). Karyawan tanpa riwayat (sebelum migrasi) → master (perilaku lama).

| Field / perubahan | Arti | Ditulis oleh |
|---|---|---|
| `hr_employees.base_salary`, `allowances`, `entity_id` | Nilai turunan baris yang berlaku hari ini (WIB); PATCH master menolaknya (400 "Gaji dan penugasan PT diubah lewat Riwayat Kompensasi di kartu karyawan.") | `apply_effective` (saat pengesahan + tugas terjadwal `hr_compensation_effective` harian 00.10 WIB) |
| `hr_pay_components` kode `RAPEL` | Komponen bawaan baru tiap PT: pendapatan, `masukan`, kena pajak, kolom `other_earnings`, proses reguler & susulan | `hr_pay_components.ensure_defaults` |
| `hr_pay_inputs` ber-`source_type: "rapel"` | Baris kompensasi disahkan dengan `effective_from` pada periode yang proses regulernya `posted`/`paid` → satu masukan `pending` per periode (`pay_period` = bulan berjalan, `amount` = nilai baru − nilai dibayar, label "Rapel gaji {bulan tahun}", `source_key` `rapel:<id baris>:<periode>`, PT = PT karyawan akhir bulan berjalan) | `hr_compensation_service.enqueue_rapel` → `hr_pay_inputs.enqueue_input(status="pending")` |
| PPh 21 hitung ulang tahunan | Slip terdahulu hanya di PT proses itu (`_prior_year_slips` disaring `entity_id`) | `hr_payroll_service.compute_payslip` |


## MN-T3 — kartu pelanggan & kartu pemasok (tanpa koleksi/field baru)

Tidak ada koleksi atau field tersimpan baru. Jawaban baca yang bertambah (dihitung saat dibaca, `services/party_card.py`):
`GET /api/customers/{id}/360` + `sections_allowed` (bagian kartu yang izinnya dipegang; angka kredit/piutang yang sudah
ada = `null` tanpa izin `payment_plan.view`/`credit_profile.view`, K-18); `GET /api/suppliers/{id}/360` + `payables`
(`outstanding` · `due_soon` · `advance` per PT dari `vendor_bills` lewat `vendor_bill_service.open_payables` dan uang muka
`contra_bon_service.available_credits`), `bills`, `contra_bons`, `payments` (= `vendor_bills.payments[]` tidak batal),
`landed_costs`, `sections_allowed` — `null` bila izin sumbernya tidak dipegang. Saringan baru: `vendor_bills.supplier_id`
(`GET /vendor-bills?supplier_id`), `finance_cases.customer_id` (`GET /finance-cases?customer_id`).

## PY-T3 — aturan hitung gaji dari pengaturan per PT: prorata, potongan, lembur, kalender libur, saldo awal pajak

| Collection | Prefix/ID | Penulis (SSOT) | Pembaca | Catatan |
|-----------|-----------|----------------|---------|---------|
| `hr_holidays` | `hhol_` | `services/hr_work_calendar.py:add_holiday` / `delete_holiday` (`POST`/`DELETE /api/hr/holidays`, izin `hr.manage_attendance`, PT aktif; 409 saat "Semua PT") | `hr_work_calendar.calendar_for` / `is_holiday` / `work_days` → proses gaji (jenis hari lembur; hari kerja untuk prorata & potongan); `GET /api/hr/holidays`; layar Pengaturan › SDM › Kalender Libur (`HolidaysView`) | **PY-T3 (PY-07)** hari libur PT: `entity_id`, `date` (`YYYY-MM-DD`), `name`, `kind` (`nasional`·`cuti_bersama`·`perusahaan`), `created_by(_id)`, `created_at`. **Tanpa isi awal** — tanggal libur resmi diisi pemilik (H4). Unik `(entity_id, date)` (`uq_entity_date`, REQUIRED_UNIQUE_INDEXES; tanggal kembar → 409 "Tanggal {tanggal} sudah terdaftar sebagai hari libur di PT ini."). Menggantikan daftar tersembunyi `system_settings{scope:"hr"}.overtime.holidays` (tanpa layar; tidak dibaca lagi). **SCOPED**. |
| `hr_tax_opening_balances` | `htob_` | `services/hr_pay_rules.py:set_tax_opening` (`PUT /api/hr/employees/{id}/tax-opening`, izin `hr.manage_payroll`, PT aktif; upsert per kunci unik) | `hr_pay_rules.tax_opening(s)` → `hr_payroll_service.compute_payslip` masa pajak terakhir; `GET …/tax-opening` (`hr.view` + `hr.view_pii`); kartu karyawan (`EmployeeTaxOpeningSection`) | **PY-T3 (PY-12)** saldo awal pajak per PT per karyawan per tahun: `entity_id`, `employee_id`(+`employee_name`), `year`, `months` (1–11: masa pajak tahun itu yang dibayar di luar sistem), `tax_gross`, `pension_deduction` (JHT + JP karyawan), `pph21_withheld`, `note`, `created_by(_id)/_at`, `updated_by(_id)/_at`. Terkunci (409 "Pajak {tahun} karyawan ini sudah dihitung ulang, jadi saldo awalnya tidak bisa diubah.") bila slip masa pajak terakhir (`pph21_method: annual_pasal17`) tahun itu di PT itu sudah `posted`/`paid`. Unik `(entity_id, employee_id, year)` (`uq_entity_employee_year`). Nominal = data pribadi. **SCOPED**. |

Aturan hitung (`services/hr_pay_rules.py:rules` — satu-satunya pembaca kunci `hr.prorata_masuk_keluar`,
`hr.potongan_alpha`, `hr.potongan_cuti_tanpa_gaji`, `hr.potongan_telat_per_menit`, `hr.overtime.sumber` (bawaan
`pengajuan`, K-39), `hr.overtime.ambang_menit`, `hr.overtime.mode`, `hr.overtime.work_days_per_week`,
`hr.overtime.hitung_absensi`, `hr.pembulatan_rupiah`, dan — juga dibaca di tempat lamanya — `hr.prorata_perubahan_gaji`,
`hr.overtime.multiplier`, `hr.overtime.hours_divisor`). Kalender kerja PT: `services/hr_work_calendar.py`.

| Field / perubahan | Arti | Ditulis oleh |
|---|---|---|
| `hr_payslips.pay_rules` | Potret aturan hitung yang dipakai slip (prorata, potongan, sumber/menit minimal/cara pengali lembur, hari kerja seminggu, pembulatan) — 02 §5 D3 | `hr_payroll_service.compute_payslip` |
| `hr_payslips.overtime_base`, `bpjs_base` | Dasar upah lembur (Σ komponen ber-`in_overtime_base`) dan dasar iuran BPJS (Σ komponen ber-`in_bpjs_base`); isi awal = gaji pokok saja (angka sama dengan sebelum unit ini) | `compute_payslip` |
| `hr_payslips.pph21_annual.opening` | Saldo awal pajak yang ikut hitung ulang setahun (`{year, months, tax_gross, pension_deduction, pph21_withheld}`) atau `null` | `compute_payslip` |
| `hr_payslips.components[]` LEMBUR, KOMISI | Kembali masuk slip reguler (sejak PY-T2 tidak pernah masuk — lembur & komisi tidak terbayar) | `hr_pay_components.earning_components` |
| `hr_payslips.tax_gross` | Σ pendapatan & tanggungan kena pajak − Σ potongan bertanda kena pajak | `hr_pay_components.derive_columns` |
| `hr_pay_components.in_bpjs_base`, `in_overtime_base` | Dipakai mesin (dulu "belum dipakai") | layar Komponen & Masukan |
| `hr_attendance.overtime_min` | `hr.overtime.hitung_absensi`: `jam_kerja_lebih` (bawaan, menit kerja − durasi shift) · `lewat_jam_pulang` (menit sesudah jam pulang shift) | `hr_attendance_service.compute_metrics` (absen manual/impor/mesin, clock-out, ubah jam) |
| `hr_pay_components` kode `POT_ALPHA`, `POT_CUTI_TG`, `POT_TELAT` | Komponen bawaan baru tiap PT ("Potongan tidak hadir", "Potongan cuti tanpa gaji", "Potongan terlambat"): `kind: potongan`, `calc: absensi`, `bucket: other_deductions`, `taxable: true` (mengurangi bruto pajak), `account_code` = `gl_service.ACC_BEBAN_GAJI` (dikredit → mengurangi beban gaji). Muncul di slip hanya bila pengaturan potongannya menyala | `hr_pay_components.ensure_defaults` |
| `hr_pay_components.prorate` | Isi awal `GAJI_POKOK` & `TUNJANGAN` = `true` (dibagi saat prorata masuk/keluar menyala; dasar upah sehari potongan). PT lama: `scripts/migrasi_pyt3_aturan_gaji.py --apply` (H3) | `ensure_defaults` · layar Komponen & Masukan |
| `hr_pay_components.calc` `per_hari_hadir` / `persen_dasar` + `rate` | Komponen buatan pengguna: `rate` × hari hadir (rekaman hadir/telat, atau di luar lokasi yang disetujui) / `rate` % × gaji pokok slip (sesudah prorata). Hanya proses reguler (`allowed_run_types = ["regular"]`) | `create_component` / `update_component` |
| `hr_payslips.attendance_summary` | Ringkasan kehadiran masa kerja bila dipakai (potongan / per hari hadir): `work_days`, `alpha_days`, `unpaid_days`, `late_min`, `present_days` | `compute_payslip` (`hr_pay_rules.hitung_kehadiran`) |
| Baris slip prorata masuk/keluar | `hr.prorata_masuk_keluar` `hari_kalender` / `hari_kerja`: komponen ber-`prorate` × hari (kerja) masa kerja ÷ hari (kerja) bulan, label "{nama} ({tgl}–{tgl} {bulan})", pembulatan slip. Karyawan yang masuk sesudah akhir periode tidak ikut proses (tanpa sakelar) | `hr_pay_rules.atur_potongan` + `hr_pay_components.nilai_tetap` |

## PY-T4 — bayar gaji dari rekening berperuntukan Gaji, daftar transfer, batal setoran kewajiban

Bayar gaji (`services/hr_payroll_pay.py:pay_run`, `POST /api/hr/payroll/runs/{id}/pay`, izin `payroll.pay`): rekening
sumber = rekening AKTIF milik PT proses yang `purposes`-nya (PM-T1) memuat `gaji` (kosong → satu-satunya rekening gaji
PT); tanggal bayar `paid_date` (bawaan hari ini WIB, tidak sebelum tanggal jurnal gaji). Satu kas keluar
`cash_transactions` `ref_type="payroll_run"`, `ref_id` = id proses (id kas tetap dari id proses — kirim ulang = kas yang
sama), `contra_account_code` = akun pemetaan `sdm.hutang_gaji` → jurnal kas (`source_type="cash_transaction"`) Dr hutang
gaji / Cr kas rekening itu, bertanggal bayar. Jurnal bayar `payroll_pay` (jalur lama, kode akun dari isi permintaan) tidak
terbit lagi; jurnal lama tetap dibaca (Jejak Dokumen, label sumber). Proses dengan jurnal `payroll_pay` lama yang kasnya
gagal: kas baru menumpang jurnal itu (`journal_by_parent`). **Daftar transfer tidak disimpan** — diturunkan dari slip
(`hr_payslips.net` + potret `bank`) tiap kali dibaca (`transfer_list`), Σ wajib = `totals.net` (selain itu 409).

| Field (`hr_payroll_runs`, ditambah) | Arti | Ditulis oleh |
|---|---|---|
| `pay_account_id`, `pay_account_name` | Rekening sumber pembayaran (nama = potret saat dibayar, untuk tampilan "Dibayar … dari …") | `pay_run` (niat) → `_selesai` (dari kas) |
| `paid_date` (`YYYY-MM-DD`) | Tanggal bayar = tanggal kas & jurnal bayar | `pay_run` (niat) → `_selesai` |
| `transfer_total`, `transfer_count` | Σ nominal daftar transfer (= kas keluar) dan jumlah penerima saat dibayar | `_selesai` |
| `paid_by`, `paid_by_id` | Pembayar (kontrol dua orang `kontrol.proses_gaji`, K-41) | `pay_run` (niat) |
| `cash_txn_id`, `cash_txn_number`, `paid_journal_id`, `paid_journal_number` | Kas keluar dan jurnal kasnya (L8) | `_selesai` (kas juga saat jurnal gagal) |
| `pay_gl_status` (`pending` · `posted` · `failed` · `not_required`), `pay_gl_error`, `pay_gl_failed_at` | Penanda jurnal bayar; `failed` → proses kembali `posted`, kas tersimpan dan tampil di Posting Gagal jenis Transaksi Kas; ulang dari panel → `hr_payroll_pay.selesaikan_dari_kas` (`posting_registry._retry_cash`) | `pay_run` |

Tanpa migrasi: proses lama yang sudah dibayar tidak diisi field baru. Proses `posted` dengan kas pembayaran hidup tidak
bisa dianulir (`void_run` 409).

| Field (`hr_statutory_remittances`, ditambah) | Arti | Ditulis oleh |
|---|---|---|
| `status` `voiding` · `void` | Batal setoran (`POST /api/hr/payroll/remittances/{id}/void`, izin `payroll.void`, alasan ≥ 5 huruf): klaim `done → voiding` → kas setoran dibalik lewat `post_durable` (`cash_transaction_void`, bertanggal setor) lalu kas `void` → `void`; gagal → kembali `done`. Setoran `void` tidak dihitung "sudah disetor" (`outstanding`, `outstanding_year`) | `hr_remittance_service.void_remittance` |
| `void_reason`, `voided_by`, `voided_by_id`, `voided_at`, `void_journal_id`, `void_journal_number` | Jejak batal setoran | `void_remittance` |

`GET /api/hr/payroll/remittances` dan `…/outstanding` (`?period=` atau `?year=` → 12 masa per jenis) menerima `hr.view`
**atau** `payroll.pay`. `cash_transactions` setoran yang dibatalkan: `status: void`, `void_journal_entry_id`, `void_reason`,
`voided_by`, `voided_at`.

## KM-T5 — kartu "Capaian & Insentif Saya"; layar insentif lama dicabut

Tidak ada koleksi atau field tersimpan baru. Endpoint baru dan perubahan jawaban (semua hanya baca kecuali disebut):

| Endpoint | Isi / perubahan | Sumber |
|---|---|---|
| `GET /api/incentive/me?period=YYYY-MM` | Cukup login (`login_only_endpoints.LOGIN_ONLY`, milik sendiri). PT = PT aktif; sales = pelaku (`sales_id` diabaikan). `{period, entity_id, mode, achievement: {target_sales, omzet_bersih, pct_omzet, target_collection, uang_masuk, pct_pencairan, realisasi_harga_pct, facts_as_of}, sheets: [{sheet_number, pay_period, status, lines: [{component_name, basis_label, amount, is_adjustment, note, paid_run_number, snapshot: {target_sales, omzet_bersih, target_collection, uang_masuk, realisasi_harga_pct}}]}], auto_commission: {mtd, projection_month_end} \| null}`. `sheets` = lembar `approved`/`paid` PT itu dengan `pay_period` = `period`, hanya baris pelaku; persen tanpa pembagi = `null`; tanpa margin & piutang | `services/incentive_me.py` (pengumpul Capaian KM-T2, `incentive_sheets`, mesin komisi lama hanya untuk PT bukan `sheet`/`off`) |
| `GET /api/incentive/targets` | + `commission_mode` (PT aktif; "" di Semua PT) dan `commission_modes` `{PT: mode}` | `incentive_payroll.mode_pt` |
| `GET /api/home/sales` | + `incentive_mode`; PT `sheet`/`off`: `commission` = `null`, `history` = `[]`, `target` tanpa `amount`/`achievement_pct` (mesin komisi tidak dipanggil) | `home_service.sales_home` |
| `GET /api/home/admin` | `incentive_payout` per PT: `sheet` → Σ baris lembar disahkan belum ber-`paid_run_id` (`incentive_payroll.belum_dibayar`); lain → estimasi mesin. + `incentive_payout_label` ("Belum dibayar" · "Estimasi bulan ini" · "Belum dibayar + estimasi bulan ini" untuk Semua PT campuran) | `home_service._incentive_payout` |
| `GET /api/sales-users`, `GET /api/sales/leaderboard`, `GET /api/sales/my-rank` | Daftar sales = `incentive_targets.sales_roster` PT itu (Semua PT = gabungan) — akun berperan kustom beracuan sales ikut; sales PT lain tidak | `routers/crm.py`, `sales_force_service.leaderboard` |
| `GET /api/sales/commission`, `…/commission-history` | 409 "PT ini tidak memakai komisi otomatis. Lihat Capaian & Insentif." untuk PT bermode `sheet`/`off` | `routers/crm.py:_tolak_tanpa_komisi` |
| `GET /api/sales/incentive/gl-status` | + `mode`, `estimate` (Σ komisi otomatis daftar sales PT = angka akrual manual; 0 bila mode ≠ `accrue_then_settle`) | `gl_service.incentive_accrual_estimate` |
| `GET`/`POST /api/sales-targets` | **Dihapus** (pemanggil terakhir: layar lama yang dihapus unit ini). Target: `GET`/`PUT /api/incentive/targets` | — |

Tetap: `GET/POST /api/sales-incentives`, `GET/POST/PATCH/DELETE /api/incentive-rates` (bagian "Komisi otomatis (cara lama)"),
koleksi `incentive_rates` dan `sales_incentives` (dibaca mesin komisi PT bermode otomatis). Menghapus mesin komisi dan kedua
koleksi = pekerjaan lanjutan sesudah tidak ada PT bermode komisi otomatis.
**KA (23 Nov 2026):** mesin komisi otomatis tidak lagi dianggap "cara lama" — dikembangkan menjadi komisi per artikel
(tarif varian/artikel/kategori, pengali harga & capaian, potret aturan per baris pesanan) dan diatur di tab **Skema & Tarif**;
PT boleh memakai keduanya bersama Lembar Insentif (`auto_and_sheet`). Rute `/api/incentive-rates` + rute layar KA-8 tetap.

### saved_views — Tampilan Tersimpan Daftar Gudang  [FIX-8 IMPLEMENTED — K-B4-12, 10 Nov 2026]
Satu dokumen = kombinasi **saringan + urut + kolom (+ mode)** satu daftar, milik satu pengguna, opsional dibagikan
admin ke peran dan/atau PT. Dipulihkan saat daftar dibuka (bawaan pribadi → bawaan bersama).
* Field: `id` (`sv_…`) · `list_key` (`wms.inventory_rolls` | `wms.transfers` | `wms.outbound_tasks` — daftar di
  `saved_view_service.LISTS`) · `name` (1–60) · `state {filters{…}, sort{key,dir}|null, columns[kunci kolom
  DISEMBUNYIKAN], mode}` (di-whitelist per daftar, ≤ 4 KB) · `share {roles[], entity_ids[], is_default}` ·
  `is_default` (bawaan pribadi; satu per pengguna per daftar) · `owner_user_id` · `owner_name` · `created_at` ·
  `updated_at` · `updated_by`.
* **Cakupan:** USER-SCOPED (`entity_scope.USER_SCOPED_COLLECTIONS`) — TANPA `entity_id`. Kunci cakupan PT/lokasi
  (`entity_id`, `owner_entity_id`, `location_view`, `site_id`, …) DITOLAK 400 di `state`: cakupan tetap dari bilah
  "Lokasi: … ▾" + PT aktif dan dipagari endpoint daftarnya (FIX-1). Penerima tampilan bersama = peran cocok DAN PT
  yang bisa ia baca beririsan (`share.entity_ids` ⊆ PT yang dibaca admin pembuatnya).
* **Izin:** = izin LIHAT daftar (`product.view` roll · `transfer.view` transfer · `wms.view` tugas keluar). Pribadi:
  hanya pemilik (orang lain 404). Bersama: buat/ubah/hapus hanya `admin`. Jejak: `audit_logs` `saved_view.*`.
* Pagar tulis "Semua Entitas": `/api/saved-views` terdaftar (S) di `entity_write_guard.GROUP_LEVEL_EXACT`.
* Index: `(list_key, owner_user_id)`, `id`. Batas 30 tampilan per pengguna per daftar.

⚠️ **JANGAN BUAT** koleksi preferensi daftar lain (`list_presets`, `user_filters`, `view_prefs`) — perluas `LISTS`.
⚠️ Preset navigasi (`useViewPreset`, alias menu) BUKAN tampilan tersimpan — itu sekali-jalan dari tautan.

### material_reservations — Cadangan Bahan Makloon  [FIX-9 IMPLEMENTED — kunci per roll, 10 Nov 2026]
Cadangan bahan (produk × PT) untuk PR/MKO makloon (`services/material_reservation_service.py`). Sejak FIX-9 panjangnya
**dikunci di roll nyata** (`services/makloon_roll_lock.py`) — roll = SSOT, cadangan hanya cermin.
* Field inti: `id` (unik — dulu bisa ganda saat replan PR, bentrok `uq_id` FIX-5) · `product_id` · `owner_entity_id` ·
  `ref_type` (`purchase_requisition` | `makloon_order`) · `ref_id` · `pr_id`/`pr_number` · `mko_id`/`mko_number` ·
  `required_qty` · `qty` · `shortage_qty` · `status` (`active` | `consumed` | `released`) · `history[]`.
* Field FIX-9: `source_warehouse_id` (gudang sumber MKO `from_warehouse_id` / PR `warehouse_id`; kosong → gudang
  ber-panjang-bebas terbesar) · `locked_qty` · `locks[] {roll_id, roll_no, warehouse_id, lot, qty, unit, status}` —
  dibangun ulang dari roll sesudah setiap operasi. `qty − locked_qty` = **cadangan belum terkunci** (stok kurang); hanya
  bagian ini yang masih dikurangi `stock_figures.allocate_makloon`.
* Kunci di roll: `inventory_rolls.length_reservations[] {id: "rsv_…", qty, status: "reserved", ref: {type: "makloon",
  id: <id cadangan>, number, mko_id, mko_number, pr_id, pr_number, entity_id}}` — skema reservasi panjang WM-02 yang
  sama dengan potong SO (bukan skema kedua). Saldo: `inventory_balances.makloon_locked_qty` (bagian dari `reserved_qty`).
* Mutex per bahan × PT: `material_reservation_locks` (`_id = "rl:<id>"`, dihapus sesudah operasi).
* Migrasi cadangan lama: `scripts/fix_data_2026_11_10_fix9_kunci_makloon.py` (dry-run bawaan, `--undo`, pagar produksi).

⚠️ **JANGAN** mengunci cadangan makloon di field roll lain (`reserved_ref`, `makloon_hold`, …) — pakai
`makloon_roll_lock` (CAS per roll + cermin). Pengurang angka stok tetap satu: `stock_figures`.

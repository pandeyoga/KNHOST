<!-- DIHASILKAN OTOMATIS oleh scripts/gen_codebase_map.py — JANGAN EDIT TANGAN -->
<!-- Dihasilkan dari commit: 5110452 pada 2026-10-26 -->
# CODEBASE MAP — Kain Nusantara (dihasilkan otomatis)

Peta ini dihitung dari kode oleh `scripts/gen_codebase_map.py`. Kalau angka di sini
tidak cocok lagi dengan kenyataan, `scripts/guardrails/verify_codebase_map.py` (INV-DOC-01)
memerah — jalankan ulang generatornya, jangan sunting tangan.

**Batas ukuran berkas (dari FRONTEND/ENGINEERING_GUARDRAILS):** `.jsx` ≤ 500 · router `.py` ≤ 800 · util `.js` ≤ 300.

## Ringkasan angka

| Ukuran | Nilai |
|---|---:|
| Router (`backend/routers/*.py`) | 153 |
| Endpoint (`@router.<method>`) | 1621 |
| Service (`backend/services/*.py`) | 332 |
| Koleksi MongoDB disentuh kode produksi | 197 |
| Direktori fitur frontend (`src/features/*`) | 39 |

## Backend — berkas inti

| Berkas | Baris |
|---|---:|
| `server.py` | 403 |
| `db.py` | 12 |
| `core_utils.py` | 385 |
| `schemas.py` | 1114 |
| `schemas_purchasing.py` | 621 |
| `dependencies.py` | 226 |
| `permissions_config.py` | 685 |
| `entity_scope.py` | 614 |
| `pagination.py` | 123 |
| `indexes.py` | 478 |
| `bootstrap.py` | 1858 |

### Fungsi utilitas — JANGAN re-implementasi

**`backend/core_utils.py`**

| Fungsi | Ringkas (baris pertama docstring) |
|---|---|
| `now_iso()` |  |
| `next_doc_number()` | Generate nomor dokumen berurutan (deletion-safe). |
| `entity_code()` | Kode pendek entitas untuk nomor dokumen (doc_prefix → short_name → upper id). |
| `invalidate_entity_code()` | FASE E-1 (E1.4) — buang cache kode entitas setelah entitas dibuat/diubah. |
| `new_id()` |  |
| `parse_decimal()` | Ubah input pengguna menjadi float desimal (mendukung koma-desimal). |
| `to_cents()` | Nominal rupiah → SEN BULAT (int, pembulatan setengah-ke-atas). |
| `from_cents()` | SEN BULAT → rupiah berdesimal dua (pasangan `to_cents`). |
| `rupiah()` | Format nominal ke gaya Indonesia: `rupiah(5131200)` → `"Rp 5.131.200"`. |
| `qty_num_id()` | Angka gaya Indonesia: `540.5` → `"540,5"` · `12.0` → `"12"`. |
| `qty_dual()` | Satu kalimat untuk DUA satuan: `qty_dual(12, 540.5, "yard")` → |
| `timeline_entry()` | Entri riwayat/timeline standar (dipakai PO approval history, dll). |
| `safe_doc()` | Recursively remove _id fields and convert ObjectId to str. |
| `hash_password()` | SEC-1 — bcrypt (salt otomatis per-hash). |
| `legacy_hash_password()` | Skema lama SHA256+pepper — hanya untuk verifikasi migrasi (rehash saat login). |
| `is_legacy_hash()` |  |
| `verify_password()` |  |
| `strip_cost_fields()` | S-10 — hapus field biaya (HPP/margin) dari respons bila role bukan admin/manager. |

**`backend/dependencies.py`**

| Fungsi | Ringkas (baris pertama docstring) |
|---|---|
| `session_expiry()` |  |
| `extract_token()` | SEC-2 — HttpOnly cookie diutamakan; fallback header Bearer (kompat). |
| `current_user()` |  |
| `require_role()` |  |
| `permission_matrix()` |  |
| `has_permission()` | Cek izin tanpa melempar (untuk cabang "boleh override?"). |
| `require_permission()` |  |
| `require_any_permission()` | Izin "SALAH SATU dari" — untuk layar yang menyatukan beberapa domain. |
| `audit_diff()` | Field yang berubah (level atas) dari before → after; after parsial hanya membandingkan kuncinya. |
| `audit()` | Tulis satu baris jejak audit. |

**`backend/entity_scope.py`**

| Fungsi | Ringkas (baris pertama docstring) |
|---|---|
| `field_for()` | Field entitas untuk koleksi. None bila SHARED. |
| `allowed_entities_for()` | Daftar badan usaha yang boleh dioperasikan user (satu sumber untuk HTTP & WebSocket). |
| `entity_ctx()` | FastAPI dependency: resolve badan usaha aktif untuk request. |
| `apply_entity_scope()` | Suntik filter entitas ke query. |
| `stamp_entity()` | Set field entitas saat create (jika belum ada). |
| `assert_entity_access()` | Cegah akses lintas-entitas (anti-IDOR) untuk GET/{id}. |
| `assert_active_entity_access()` | Isolasi detail SEKETAT daftarnya: dokumen harus milik badan usaha AKTIF. |
| `guard_doc()` | Audit 2026-09-21 (KN-A01..A07, B29..B35) — penjaga entitas SATU BARIS untuk jalur TULIS. |
| `resolve_list_scope()` | Logika scope LIST yang baku & backward-compatible. |
| `resolve_scope_ids()` | Daftar entity_id dalam cakupan baca. Dipakai koleksi yang punya record |
| `resolve_list_scope_inherit()` | Seperti `resolve_list_scope`, tetapi baris **GLOBAL tetap terlihat**. |
| `scope_value()` | Nilai siap-pakai untuk field entitas: `str` bila satu, `{"$in": [...]}` bila banyak. |
| `assert_write_entity()` | Pagar mode "Semua Entitas": TULIS wajib memilih satu entitas (tutup E4). |
| `resolve_requested_entity()` | Entitas efektif untuk PRATINJAU/TULIS bila pemanggil menyebut entitas di payload. |

**`backend/pagination.py`**

| Fungsi | Ringkas (baris pertama docstring) |
|---|---|
| `is_paged()` | True bila klien meminta paginasi (ada param page / page_size). |
| `get_page_params()` | Ambil (page, page_size, q, sort) dari query string dengan aman. |
| `build_search()` | Bangun filter `$or` regex case-insensitive untuk daftar field. |
| `merge_query()` | Gabung dua filter Mongo dengan aman (pakai $and bila keduanya isi). |
| `fetch_page()` | Hitung total + ambil satu halaman (skip/limit). Return (items, total). |
| `envelope()` | Bungkus hasil sesuai kontrak paginasi. |
| `paginate_list()` | Paginasi in-memory (untuk list yang sudah ter-enrich/di-hitung penuh). |

## Backend — router

| Berkas | Endpoint | Baris | Path |
|---|---:|---:|---|
| `access_review.py` | 2 | 87 | `/access/role-reality`, `/access/role-reality/{user_id}/apply` |
| `access_roles.py` | 9 | 113 | `/modules`, `/roles`, `/roles/preview`, `/roles/{rid}`, `/roles/{rid}/move-users`, `/roles/{rid}/reset` |
| `admin.py` | 10 | 558 | `/admin/seed-demo`, `/master-data/export-customers`, `/master-data/export-products`, `/master-data/export-warehouses`, `/master-data/export-yarn`, `/master-data/import-customers` … |
| `ai_analytics.py` | 32 | 430 | `/analyze-change`, `/catalog`, `/chat`, `/export.xlsx`, `/facts/rebuild`, `/facts/status` … |
| `ai_assist.py` | 5 | 43 | `/actions/{pid}`, `/actions/{pid}/confirm`, `/actions/{pid}/dismiss`, `/insights`, `/insights/scan` |
| `amendments.py` | 10 | 183 | `/amendment-reasons`, `/amendments`, `/amendments/doc/{doc_type}/{doc_id}`, `/amendments/preview`, `/amendments/stats/summary`, `/amendments/{amd_id}` … |
| `approval_rules.py` | 5 | 138 | `/approval-rules`, `/approval-rules/{rule_id}` |
| `approvals_matrix.py` | 3 | 78 | `/approvals/matrix`, `/approvals/matrix-log`, `/approvals/my-queue` |
| `ar_aging.py` | 4 | 103 | `/ar/advance-report`, `/ar/aging`, `/ar/aging/{customer_id}`, `/ar/aging/{customer_id}/accrue-penalties` |
| `ar_receipts.py` | 7 | 141 | `/ar-receipts`, `/ar-receipts/deposit`, `/ar-receipts/open-orders`, `/ar-receipts/{receipt_id}`, `/ar-receipts/{receipt_id}/repost`, `/ar-receipts/{receipt_id}/void` |
| `audit.py` | 2 | 98 | `/audit-logs`, `/audit-logs/resource` |
| `auth.py` | 5 | 184 | `/auth/context`, `/auth/login`, `/auth/logout`, `/auth/me`, `/roles` |
| `bank.py` | 6 | 131 | `/bank-accounts`, `/bank-accounts/position`, `/bank-accounts/{account_id}`, `/bank-accounts/{account_id}/ledger`, `/cash-transactions/{txn_id}/reconcile` |
| `bank_reconciliation.py` | 23 | 431 | `/bank-reconciliation/auto-match`, `/bank-reconciliation/formats`, `/bank-reconciliation/formats/{format_id}`, `/bank-reconciliation/holding`, `/bank-reconciliation/import`, `/bank-reconciliation/import-file` … |
| `budgets.py` | 9 | 174 | `/finance/budget-check`, `/finance/budget-keys`, `/finance/budget-rules`, `/finance/budget-vs-actual`, `/finance/budgets`, `/finance/budgets/{budget_id}` |
| `cash.py` | 4 | 239 | `/cash-transactions`, `/cash-transactions/summary`, `/cash-transactions/{txn_id}/void` |
| `cash_advances.py` | 19 | 168 | `/cash-advance-settlements`, `/cash-advance-settlements/reimburse-payables`, `/cash-advance-settlements/{stl_id}`, `/cash-advance-settlements/{stl_id}/approve`, `/cash-advance-settlements/{stl_id}/pay-reimburse`, `/cash-advance-settlements/{stl_id}/reject` … |
| `categories.py` | 5 | 169 | `/product-categories`, `/product-categories/{category_id}`, `/product-motifs` |
| `client_dataset.py` | 6 | 60 | `/batches`, `/batches/{batch_id}`, `/batches/{batch_id}/commit`, `/batches/{batch_id}/rollback`, `/template`, `/upload` |
| `closing.py` | 6 | 134 | `/finance/closing`, `/finance/closing/close`, `/finance/closing/preview`, `/finance/closing/status`, `/finance/closing/{closing_id}/reclose`, `/finance/closing/{closing_id}/reopen` |
| `color_library.py` | 14 | 194 | `/color-library`, `/color-library/customer-colors`, `/color-library/customer-colors/{customer_id}/card`, `/color-library/nearest`, `/color-library/supplier-variants`, `/color-library/use-requests` … |
| `config.py` | 12 | 405 | `/effective`, `/explain`, `/health`, `/history`, `/impact-apply`, `/impact-preview` … |
| `consolidation.py` | 7 | 133 | `/consolidation/sync-g6`, `/finance/consolidation/eliminations`, `/finance/consolidation/eliminations/sync-from-pairs`, `/finance/consolidation/eliminations/{elim_id}`, `/finance/consolidation/ic-candidates`, `/finance/consolidation/summary` |
| `contra_bons.py` | 24 | 329 | `/contra-bons`, `/contra-bons/bank-line-candidates/{line_id}`, `/contra-bons/exchange-schedules`, `/contra-bons/meta`, `/contra-bons/prepare`, `/contra-bons/run-reminder` … |
| `costing.py` | 2 | 27 | `/wac`, `/wac/{product_id}` |
| `crm.py` | 24 | 456 | `/collection-reminders`, `/collection-reminders/mark`, `/collection-worklist`, `/credit-overrides`, `/credit-overrides/{override_id}`, `/credit-overrides/{override_id}/decision` … |
| `crm_omnichannel.py` | 10 | 206 | `/crm/interactions`, `/crm/interactions/{intx_id}`, `/crm/leads`, `/crm/leads/board`, `/crm/leads/{lead_id}`, `/crm/leads/{lead_id}/convert` … |
| `customer_feedback.py` | 5 | 95 | `/customer-feedback`, `/customer-feedback/meta`, `/customer-feedback/summary`, `/customer-feedback/{fb_id}` |
| `customer_prices.py` | 9 | 221 | `/customer-prices`, `/customer-prices/export`, `/customer-prices/floor`, `/customer-prices/import`, `/customer-prices/quote`, `/customer-prices/records` … |
| `customers.py` | 6 | 285 | `/customers`, `/customers/{customer_id}`, `/customers/{customer_id}/addresses`, `/customers/{customer_id}/merge`, `/customers/{customer_id}/merge-preview` |
| `cutting.py` | 5 | 60 | `/desk`, `/locations`, `/locations/{wid}`, `/orders/{order_id}/receive`, `/tasks/{task_id}/receive` |
| `cycle_count.py` | 14 | 552 | `/cycle-count/sessions`, `/cycle-count/sessions/{session_id}`, `/cycle-count/sessions/{session_id}/approve`, `/cycle-count/sessions/{session_id}/items`, `/cycle-count/sessions/{session_id}/items/{item_id}`, `/cycle-count/sessions/{session_id}/reject` … |
| `dashboard.py` | 1 | 174 | `/dashboard` |
| `data_hygiene.py` | 9 | 85 | `/data-hygiene/location/{collection}/{doc_id}`, `/data-hygiene/log`, `/data-hygiene/log/{log_id}/revert`, `/data-hygiene/preview`, `/data-hygiene/run`, `/data-hygiene/summary` … |
| `deliveries.py` | 9 | 119 | `/whatsapp/recipient/{doc_type}/{source_id}`, `/whatsapp/rules`, `/whatsapp/rules/{rule_id}`, `/whatsapp/send`, `/whatsapp/settings`, `/{doc_type}/{source_id}` |
| `design_gallery.py` | 26 | 494 | `/design-gallery`, `/design-gallery-ai/status`, `/design-gallery-products/unlink`, `/design-gallery/{gallery_id}`, `/design-gallery/{gallery_id}/ai-illustrate`, `/design-gallery/{gallery_id}/approve` … |
| `design_requests.py` | 20 | 398 | `/design-requests`, `/design-requests-for-so/{so_id}`, `/design-requests/meta`, `/design-requests/{req_id}`, `/design-requests/{req_id}/approve`, `/design-requests/{req_id}/assign` … |
| `design_studio.py` | 25 | 341 | `/design-gallery/{gallery_id}/colorways`, `/design-gallery/{gallery_id}/colorways/{cw_id}`, `/design-gallery/{gallery_id}/feedback`, `/design-gallery/{gallery_id}/files-kind/{kind}`, `/design-gallery/{gallery_id}/history`, `/design-gallery/{gallery_id}/lifecycle/activate` … |
| `documents.py` | 17 | 426 | `/document-templates`, `/document-templates/{template_id}`, `/document-templates/{template_id}/preview`, `/documents/barcode`, `/documents/generate`, `/documents/preview/{order_id}` … |
| `entities.py` | 11 | 232 | `/entities`, `/entities/count`, `/entities/{entity_id}`, `/entities/{entity_id}/archive`, `/entities/{entity_id}/audit`, `/entities/{entity_id}/deactivation-impact` … |
| `entity_masters.py` | 7 | 103 | `/entity-masters`, `/entity-masters/{kind}`, `/entity-masters/{kind}/effective`, `/entity-masters/{kind}/{row_id}`, `/entity-masters/{kind}/{row_id}/override` |
| `enums.py` | 5 | 124 | `/enums`, `/enums/products/validate`, `/enums/stage-transitions`, `/enums/stage-transitions/validate`, `/enums/{name}` |
| `esign.py` | 4 | 91 | `/request`, `/signatures/{doc_type}/{source_id}`, `/verify`, `/verify/{code}` |
| `export_center.py` | 14 | 324 | `/coverage`, `/datasets`, `/jobs`, `/jobs/{job_id}`, `/jobs/{job_id}/download`, `/jobs/{job_id}/retry` … |
| `fabric_type_master.py` | 2 | 31 | `/master/fabric-types` |
| `finance_analytics.py` | 4 | 140 | `/finance/cashflow-forecast`, `/finance/profitability`, `/finance/profitability/export.xlsx`, `/finance/tower` |
| `finance_bi.py` | 1 | 36 | `/finance/bi` |
| `finance_cases.py` | 13 | 191 | `/finance-cases`, `/finance-cases/playbooks`, `/finance-cases/policy`, `/finance-cases/reasons`, `/finance-cases/scan`, `/finance-cases/stats` … |
| `financial_statements.py` | 8 | 261 | `/finance/balance-sheet`, `/finance/balance-sheet/export.csv`, `/finance/cash-flow`, `/finance/cash-flow/export.csv`, `/finance/equity-changes`, `/finance/equity-changes/export.csv` … |
| `fixed_assets.py` | 10 | 199 | `/fixed-assets`, `/fixed-assets/meta`, `/fixed-assets/run-depreciation`, `/fixed-assets/summary`, `/fixed-assets/{asset_id}`, `/fixed-assets/{asset_id}/dispose` … |
| `fulfillment.py` | 3 | 49 | `/fulfillment/wizard/{so_id}`, `/fulfillment/wizard/{so_id}/create-interco`, `/fulfillment/wizard/{so_id}/create-pr` |
| `gl.py` | 20 | 338 | `/gl/accounts`, `/gl/accounts/{code}`, `/gl/accounts/{code}/ledger`, `/gl/cash-accounts`, `/gl/consolidation`, `/gl/inventory-drift-explain` … |
| `gl_mappings.py` | 5 | 82 | `/gl/account-mappings`, `/gl/account-mappings/history`, `/gl/account-mappings/{key}`, `/gl/account-mappings/{key}/candidates`, `/gl/account-mappings/{key}/reset` |
| `goods_receipts.py` | 37 | 301 | `/goods-receipts`, `/goods-receipts/dn-profiles`, `/goods-receipts/dn-profiles/{partner_id}`, `/goods-receipts/doc-variance`, `/goods-receipts/mode`, `/goods-receipts/partners` … |
| `grade_master.py` | 4 | 62 | `/master/grades`, `/master/grades/{code}`, `/master/grades/{code}/active` |
| `home.py` | 5 | 106 | `/admin`, `/finance`, `/manager`, `/sales`, `/warehouse` |
| `hr.py` | 15 | 517 | `/hr/employees`, `/hr/employees/me`, `/hr/employees/{employee_id}`, `/hr/employees/{employee_id}/360`, `/hr/org-units`, `/hr/org-units/tree` … |
| `hr_analytics.py` | 1 | 23 | `/hr/analytics/summary` |
| `hr_attendance.py` | 21 | 514 | `/hr/attendance`, `/hr/attendance/clock-in`, `/hr/attendance/clock-out`, `/hr/attendance/import`, `/hr/attendance/ingest`, `/hr/attendance/manual` … |
| `hr_kpi.py` | 5 | 107 | `/hr/kpi`, `/hr/kpi/me`, `/hr/kpi/{kpi_id}` |
| `hr_leave.py` | 18 | 275 | `/hr/leave-balance/me`, `/hr/leave-balances`, `/hr/leave-balances/set`, `/hr/leave-calendar`, `/hr/leave-requests`, `/hr/leave-requests/me` … |
| `hr_payroll.py` | 15 | 263 | `/hr/payroll/runs`, `/hr/payroll/runs/preview`, `/hr/payroll/runs/{run_id}`, `/hr/payroll/runs/{run_id}/approve`, `/hr/payroll/runs/{run_id}/pay`, `/hr/payroll/runs/{run_id}/post-gl` … |
| `hr_tracking.py` | 9 | 254 | `/hr/field-tracks`, `/hr/field-tracks/latest`, `/hr/visits`, `/hr/visits/check-in`, `/hr/visits/me`, `/hr/visits/mine` … |
| `inbound_receiving.py` | 5 | 308 | `/inbound/tasks`, `/inbound/tasks/{task_id}/complete`, `/inbound/tasks/{task_id}/escalate`, `/inbound/tasks/{task_id}/resolve-escalation`, `/inbound/tasks/{task_id}/scan-receive` |
| `inbound_receiving_extra.py` | 7 | 291 | `/inbound/po/{po_id}/receiving-goods-document`, `/inbound/qc/queue`, `/inbound/tasks/{task_id}/preview-uom`, `/inbound/tasks/{task_id}/qc-decision`, `/inbound/tasks/{task_id}/uom-options`, `/receiving/uom-settings` |
| `inbound_scan_label.py` | 10 | 328 | `/inbound/rolls/{roll_id}/confirm-measure`, `/inbound/rolls/{roll_id}/putaway`, `/inbound/rolls/{roll_id}/scan`, `/inbound/rolls/{roll_id}/tag`, `/inbound/scan-label/stats`, `/inbound/tasks/{task_id}/scan-label` … |
| `incentive_rates.py` | 4 | 105 | `/incentive-rates`, `/incentive-rates/{rate_id}` |
| `input_tax.py` | 6 | 194 | `/input-tax-invoices`, `/input-tax-invoices/eligible-bills`, `/input-tax-invoices/{fpm_id}`, `/input-tax-invoices/{fpm_id}/cancel`, `/tax/vat-summary` |
| `inspections.py` | 18 | 522 | `/inspections`, `/inspections/export`, `/inspections/meta`, `/inspections/meta/ref-docs`, `/inspections/qc-4point`, `/inspections/queue/qc-tasks` … |
| `integrations.py` | 4 | 84 | `/admin/integrations`, `/admin/integrations/gemini/test`, `/admin/integrations/openai/test` |
| `interco.py` | 38 | 577 | `/interco/accounts`, `/interco/accounts/{from_entity_id}/{to_entity_id}`, `/interco/accounts/{payer_entity_id}/{payee_entity_id}/remind`, `/interco/contracts`, `/interco/margin-by-product`, `/interco/margin-report` … |
| `interco_loans.py` | 8 | 138 | `/interco/loans`, `/interco/loans/meta`, `/interco/loans/{loan_id}`, `/interco/loans/{loan_id}/cancel`, `/interco/loans/{loan_id}/disburse`, `/interco/loans/{loan_id}/repay` … |
| `interco_prices.py` | 5 | 76 | `/interco/prices/access`, `/interco/prices/bulk`, `/interco/prices/missing`, `/interco/prices/request`, `/interco/prices/summary` |
| `internal_requests.py` | 9 | 226 | `/internal-requests`, `/internal-requests-availability/{product_id}`, `/internal-requests/meta`, `/internal-requests/{req_id}`, `/internal-requests/{req_id}/cancel`, `/internal-requests/{req_id}/convert` … |
| `inventory.py` | 22 | 607 | `/history/{product_id}`, `/inventory/balances`, `/inventory/cut-children-unverified`, `/inventory/initial-stock`, `/inventory/low-stock-summary`, `/inventory/movements` … |
| `invoices.py` | 3 | 155 | `/invoices`, `/sales-orders/{order_id}/invoices`, `/sales-orders/{order_id}/simulate-payment` |
| `label_printer.py` | 2 | 144 | `/labels/generate`, `/labels/preview` |
| `landed_cost.py` | 10 | 392 | `/landed-costs`, `/landed-costs/payables/summary`, `/landed-costs/{voucher_id}`, `/landed-costs/{voucher_id}/approve`, `/landed-costs/{voucher_id}/cancel`, `/landed-costs/{voucher_id}/pay` … |
| `logistics.py` | 27 | 337 | `/dashboard`, `/deliveries`, `/deliveries/{delivery_id}`, `/deliveries/{delivery_id}/manifest`, `/deliveries/{delivery_id}/photos`, `/deliveries/{delivery_id}/photos/{photo_id}` … |
| `lots.py` | 18 | 364 | `/lots`, `/lots/identity-trace`, `/lots/merge`, `/lots/settings`, `/lots/stats`, `/lots/unassigned-rolls` … |
| `makloon_orders.py` | 23 | 398 | `/makloon-orders`, `/makloon-orders/claims`, `/makloon-orders/claims/stats`, `/makloon-orders/estimate`, `/makloon-orders/{mko_id}`, `/makloon-orders/{mko_id}/cancel` … |
| `makloons.py` | 6 | 142 | `/makloons`, `/makloons/{makloon_id}`, `/makloons/{makloon_id}/scorecard` |
| `marketing.py` | 35 | 560 | `/marketing/accounts`, `/marketing/accounts/{aid}`, `/marketing/analytics`, `/marketing/assets`, `/marketing/calendar.pdf`, `/marketing/campaigns` … |
| `master_governance.py` | 7 | 66 | `/master-governance/batches`, `/master-governance/batches/{batch_id}/rollback`, `/master-governance/preview`, `/master/usage/{kind}/{mid}`, `/master/{kind}/{mid}/purge`, `/products/{product_id}/rename` |
| `notifications.py` | 5 | 114 | `/notifications`, `/notifications/generate`, `/notifications/read-all`, `/notifications/unread-count`, `/notifications/{notification_id}/read` |
| `ocr_samples.py` | 7 | 89 | `/from-grn/{grn_id}`, `/runs`, `/runs/{run_id}`, `/{sample_id}`, `/{sample_id}/files/{page}` |
| `onboarding.py` | 3 | 84 | `/onboarding`, `/onboarding/reset`, `/onboarding/{task_id}/complete` |
| `outbound_picking.py` | 16 | 623 | `/outbound/loading-check/{session_id}/complete`, `/outbound/loading-check/{session_id}/scan`, `/outbound/loading-check/{session_id}/scan-label`, `/outbound/so/{order_id}/dispatch-batch`, `/outbound/so/{order_id}/loading-check`, `/outbound/so/{order_id}/loading-check/override` … |
| `outbound_picking_extra.py` | 3 | 318 | `/outbound/so/{order_id}/surat-jalan`, `/shipments`, `/shipments/{shipment_id}/surat-jalan` |
| `payment_plans.py` | 14 | 262 | `/payment-plans`, `/payment-plans/by-doc/{doc_type}/{doc_id}`, `/payment-plans/meta`, `/payment-plans/preview`, `/payment-plans/{plan_id}`, `/payment-plans/{plan_id}/accrue` … |
| `payment_variance.py` | 8 | 183 | `/payment-variances`, `/payment-variances/assess`, `/payment-variances/meta`, `/payment-variances/pending`, `/payment-variances/receipt/{receipt_id}`, `/payment-variances/receipt/{receipt_id}/decide` … |
| `pdf.py` | 12 | 295 | `/branding/{entity_id}`, `/doc-types`, `/documents/{doc_type}`, `/preview`, `/render/{doc_type}/{source_id}`, `/sample/{doc_type}` … |
| `pegging.py` | 3 | 120 | `/inventory/rolls/{roll_id}/earmark`, `/pegging/rolls` |
| `period_unlocks.py` | 6 | 122 | `/finance/period-unlocks`, `/finance/period-unlocks/active`, `/finance/period-unlocks/reclose-expired`, `/finance/period-unlocks/{plu_id}/approve`, `/finance/period-unlocks/{plu_id}/reject` |
| `po_board.py` | 2 | 90 | `/purchase-orders/board`, `/purchase-orders/{po_id}/stage` |
| `pos.py` | 8 | 133 | `/pos/best-sellers`, `/pos/featured`, `/pos/featured/{product_id}`, `/pos/frequently-bought-together`, `/pos/highlights-config`, `/pos/recommendations` … |
| `posting_failures.py` | 3 | 114 | `/finance/posting-failures`, `/finance/posting-failures/count`, `/finance/posting-failures/{kind}/{doc_id}/retry` |
| `price_approvals.py` | 15 | 632 | `/price-approvals`, `/price-approvals/effective`, `/price-approvals/hint`, `/price-approvals/stats/summary`, `/price-approvals/{approval_id}`, `/price-approvals/{approval_id}/approve` … |
| `pricelist.py` | 8 | 163 | `/pricelist`, `/pricelist/export`, `/pricelist/import`, `/pricelist/override/{product_id}`, `/pricelist/records`, `/pricelist/{price_id}` |
| `process_recipes.py` | 5 | 142 | `/process-recipes`, `/process-recipes/forecast`, `/process-recipes/{recipe_id}` |
| `product_media.py` | 9 | 186 | `/product-catalog/meta`, `/products/{product_id}/catalog-relations`, `/products/{product_id}/media`, `/products/{product_id}/media/from-design`, `/products/{product_id}/media/generate-mockup`, `/products/{product_id}/media/{media_id}` … |
| `product_templates.py` | 10 | 144 | `/product-templates`, `/product-templates/detach`, `/product-templates/resolve-orphans`, `/product-templates/{template_id}`, `/product-templates/{template_id}/assign`, `/product-templates/{template_id}/generate-variants` … |
| `product_traceability.py` | 1 | 238 | `/products/{product_id}/purchase-history` |
| `production.py` | 12 | 228 | `/production/boms`, `/production/boms/{bom_id}`, `/production/summary`, `/production/work-orders`, `/production/work-orders/{wo_id}`, `/production/work-orders/{wo_id}/cancel` … |
| `products.py` | 6 | 341 | `/products`, `/products/sales-owners`, `/products/{product_id}`, `/products/{product_id}/stock-breakdown` |
| `purchase_orders.py` ⚠️>800 | 8 | 1002 | `/purchase-orders`, `/purchase-orders/resolve-sourcing`, `/purchase-orders/status-counts`, `/purchase-orders/{po_id}`, `/purchase-orders/{po_id}/amend`, `/purchase-orders/{po_id}/approve` … |
| `purchase_orders_extra.py` | 11 | 283 | `/po-variance-tasks`, `/po-variance-tasks/{task_id}/decide`, `/purchase-orders/blanket`, `/purchase-orders/payables/summary`, `/purchase-orders/{blanket_id}/call-off`, `/purchase-orders/{blanket_id}/close-contract` … |
| `purchase_requisitions.py` | 18 | 338 | `/material-reservations`, `/purchase-requisitions`, `/purchase-requisitions/eligible-suppliers`, `/purchase-requisitions/merge-suggestions`, `/purchase-requisitions/realize-many`, `/purchase-requisitions/reorder-suggestions` … |
| `purchase_returns.py` | 18 | 323 | `/purchase-returns`, `/purchase-returns/source-rolls`, `/purchase-returns/status-counts`, `/purchase-returns/{return_id}`, `/purchase-returns/{return_id}/approve`, `/purchase-returns/{return_id}/attachments` … |
| `push.py` | 5 | 87 | `/push/public-key`, `/push/status`, `/push/subscribe`, `/push/test`, `/push/unsubscribe` |
| `putaway_orders.py` | 8 | 124 | `/putaway-orders`, `/putaway-orders/suggest`, `/putaway-orders/verify-labels`, `/putaway-orders/{order_id}/confirm-arrival`, `/putaway-orders/{order_id}/dispatch`, `/putaway-orders/{order_id}/resolve-exception` … |
| `qc_inspection.py` | 9 | 190 | `/inbound/qc/tasks/{task_id}/plan`, `/inbound/qc/tasks/{task_id}/rolls`, `/inbound/rolls/{roll_id}/inspect`, `/inventory/rolls/{roll_id}/grade-history`, `/inventory/rolls/{roll_id}/grade-override`, `/inventory/rolls/{roll_id}/hold` … |
| `repair_orders.py` | 9 | 164 | `/inventory/rolls/{roll_id}/repairs`, `/repair-orders`, `/repair-orders/candidate-rolls`, `/repair-orders/target-products`, `/repair-orders/{ro_id}`, `/repair-orders/{ro_id}/cancel` … |
| `reporting.py` | 6 | 323 | `/reports/order-velocity`, `/reports/reservation-funnel`, `/reports/stock-aging`, `/reports/summary`, `/reports/top-customers`, `/reports/warehouse-utilization` |
| `restock_sources.py` | 3 | 38 | `/product-templates/{template_id}/restock-source`, `/restock-sources` |
| `return_disposition.py` | 8 | 137 | `/return-dispositions/inbox`, `/return-dispositions/summary`, `/sales-returns/{return_id}/disposition`, `/sales-returns/{return_id}/disposition/internal`, `/sales-returns/{return_id}/disposition/photos`, `/sales-returns/{return_id}/disposition/photos/{att_id}` … |
| `return_policies.py` | 7 | 241 | `/return-policies/supplier-deadlines`, `/sales-return-policies`, `/sales-return-policies/eligibility`, `/sales-return-policies/{policy_id}` |
| `rfid.py` | 48 | 710 | `/rfid/cycle-count/start`, `/rfid/cycle-count/{session_id}/complete`, `/rfid/cycle-counts`, `/rfid/cycle-counts/{cc_id}`, `/rfid/device-health`, `/rfid/device-jobs/pending` … |
| `rfq.py` | 8 | 222 | `/rfqs`, `/rfqs/{rfq_id}`, `/rfqs/{rfq_id}/award`, `/rfqs/{rfq_id}/cancel`, `/rfqs/{rfq_id}/compare`, `/rfqs/{rfq_id}/quote` … |
| `rnd.py` ⚠️>800 | 46 | 1062 | `/rnd/base-fabrics`, `/rnd/labdip-history`, `/rnd/lifecycle-board`, `/rnd/meta`, `/rnd/products/{product_id}/supplier-eligibility`, `/rnd/reports/designer-kpi` … |
| `rnd_org.py` | 3 | 73 | `/rnd/divisions`, `/rnd/divisions/members` |
| `saga_locks.py` | 3 | 121 | `/saga-locks`, `/saga-locks/{collection}/{doc_id}/inspect`, `/saga-locks/{collection}/{doc_id}/release` |
| `sales_orders.py` | 3 | 774 | `/sales-orders`, `/sales-orders/{order_id}` |
| `sales_orders_extra.py` ⚠️>800 | 21 | 952 | `/sales-orders`, `/sales-orders/frequent-products`, `/sales-orders/preview-allocation`, `/sales-orders/preview-lots`, `/sales-orders/preview-roll-reconcile`, `/sales-orders/stats/summary` … |
| `sales_p04.py` | 5 | 75 | `/customers/{customer_id}/grade-rules`, `/sales-orders/{order_id}/items/{product_id}/roll-candidates`, `/sales/keep-pending`, `/sales/stock-summary` |
| `sales_return_exceptions.py` | 15 | 291 | `/sales-returns/cutloss/simulate`, `/sales-returns/discount/simulate`, `/sales-returns/{return_id}/compensation`, `/sales-returns/{return_id}/cutloss`, `/sales-returns/{return_id}/cutloss/{ctl_id}/return-shipment`, `/sales-returns/{return_id}/cutloss/{ctl_id}/split` … |
| `sales_returns.py` ⚠️>800 | 41 | 1289 | `/credit-notes`, `/credit-notes/{cn_id}`, `/returns/chain/{doc_id}`, `/sales-returns`, `/sales-returns/eligible-orders`, `/sales-returns/meta/complaint-reasons` … |
| `sample_orders.py` | 11 | 259 | `/sample-orders`, `/sample-orders/catalogue/preview`, `/sample-orders/catalogue/templates`, `/sample-orders/desk`, `/sample-orders/kinds`, `/sample-orders/limits` … |
| `sample_sales.py` | 5 | 102 | `/outbound/so/{order_id}/cut-samples`, `/outbound/tasks/{task_id}/cut-sample`, `/sample-prices`, `/sample-prices/{template_id}`, `/sample-quote` |
| `scheduler.py` | 10 | 216 | `/scheduler/digest-preview`, `/scheduler/jobs`, `/scheduler/jobs/{job_id}/run`, `/scheduler/runs`, `/scheduler/settings`, `/scheduler/summary` … |
| `settings.py` | 10 | 187 | `/payment-terms`, `/payment-terms/{term_id}`, `/payment-terms/{term_id}/override`, `/settings`, `/settings/compute-tax`, `/settings/effective` … |
| `so_approvals.py` | 8 | 536 | `/approvals/backlog`, `/approvals/queue`, `/approvals/queue-board/{key}`, `/sales-orders/{order_id}/approvals/{approval_id}/decide`, `/sales-orders/{order_id}/approvals/{approval_id}/evidence`, `/sales-orders/{order_id}/approvals/{approval_id}/evidence/{att_id}/download` … |
| `so_override.py` | 2 | 45 | `/sales-orders/{order_id}/override`, `/sales-orders/{order_id}/override-context` |
| `so_release.py` | 3 | 60 | `/sales-orders/{order_id}/approvals/{approval_id}/continue-normal-price`, `/sales-orders/{order_id}/release`, `/sales-orders/{order_id}/review-release` |
| `special_orders.py` ⚠️>800 | 30 | 1492 | `/special-orders`, `/special-orders/{order_id}`, `/special-orders/{order_id}/approve`, `/special-orders/{order_id}/convert-to-so`, `/special-orders/{order_id}/create-pr`, `/special-orders/{order_id}/create-sku` … |
| `stock_buckets.py` | 9 | 105 | `/stock/atp`, `/stock/buckets`, `/stock/hold`, `/stock/hold/{hold_id}/release`, `/stock/holds`, `/stock/pending-so` … |
| `store_credit.py` | 7 | 139 | `/store-credit`, `/store-credit/adjust`, `/store-credit/balance`, `/store-credit/entries/{entry_id}/reverse`, `/store-credit/ledger`, `/store-credit/open-orders` … |
| `supplier_contracts.py` | 14 | 291 | `/makloon-claims/recap`, `/makloon-claims/recap.xlsx`, `/makloon-partners/scorecard`, `/supplier-contracts`, `/supplier-contracts/policy`, `/supplier-contracts/resolve` … |
| `supplier_items.py` | 11 | 208 | `/supplier-items`, `/supplier-items/import`, `/supplier-items/import-file`, `/supplier-items/import-template`, `/supplier-items/lookup`, `/supplier-items/stats` … |
| `suppliers.py` | 13 | 388 | `/supplier-price-list/resolve`, `/supplier-price-list/{entry_id}`, `/suppliers`, `/suppliers/{supplier_id}`, `/suppliers/{supplier_id}/360`, `/suppliers/{supplier_id}/price-list` … |
| `tax_center.py` | 4 | 83 | `/tax/pph-records`, `/tax/pph-records/{record_id}`, `/tax/summary` |
| `tax_invoices.py` | 7 | 97 | `/sales-orders/{order_id}/tax-invoice`, `/tax-invoices`, `/tax-invoices/{fkt_id}`, `/tax-invoices/{fkt_id}/cancel`, `/tax-invoices/{fkt_id}/document`, `/tax-invoices/{fkt_id}/nsfp` … |
| `transfers.py` | 14 | 796 | `/transfers`, `/transfers/inter-company`, `/transfers/so-options`, `/transfers/so-rolls`, `/transfers/{transfer_id}`, `/transfers/{transfer_id}/approve` … |
| `uom_conversions.py` | 10 | 226 | `/uom-conversions/catalog`, `/uom-conversions/check-variance`, `/uom-conversions/convert`, `/uom-conversions/rules`, `/uom-conversions/rules/{rule_id}`, `/uom-conversions/rules/{rule_id}/status` … |
| `uoms.py` | 5 | 186 | `/uoms`, `/uoms/vocab`, `/uoms/{uom_id}` |
| `users.py` | 10 | 206 | `/hr-employees-available`, `/users`, `/users/count`, `/users/{user_id}`, `/users/{user_id}/reactivate`, `/users/{user_id}/reset-password` … |
| `vehicle_logs.py` | 9 | 214 | `/vehicle-usage-logs`, `/vehicle-usage-logs/summary`, `/vehicle-usage-logs/{log_id}`, `/vehicles`, `/vehicles/{veh_id}` |
| `vendor_bills.py` | 12 | 719 | `/purchase-orders/{po_id}/billing-context`, `/vendor-bills`, `/vendor-bills/payables/summary`, `/vendor-bills/status-counts`, `/vendor-bills/{bill_id}`, `/vendor-bills/{bill_id}/approve` … |
| `warehouse_sites.py` | 6 | 88 | `/warehouse-sites`, `/warehouse-sites/seed-blueprint`, `/warehouse-sites/{site_id}`, `/warehouse-sites/{site_id}/receiving` |
| `warehouses.py` | 10 | 301 | `/warehouse-sites/{site_id}/stock-tree`, `/warehouses`, `/warehouses/{warehouse_id}`, `/warehouses/{warehouse_id}/locations`, `/warehouses/{warehouse_id}/occupancy`, `/warehouses/{warehouse_id}/orphans` … |
| `wilayah.py` | 8 | 55 | `/wilayah/countries`, `/wilayah/districts`, `/wilayah/postal-code/{code}`, `/wilayah/provinces`, `/wilayah/regencies`, `/wilayah/search` … |
| `wms.py` | 7 | 276 | `/wms/my-location-scope`, `/wms/tasks`, `/wms/tasks/outbound-from-order/{order_id}`, `/wms/tasks/{task_id}/advance`, `/wms/tasks/{task_id}/scan`, `/wms/tasks/{task_id}/takeover` |
| `work_desks.py` | 12 | 262 | `/desks/me`, `/desks/so-tracker`, `/finance/desk`, `/md/desk`, `/sales-admin/desk`, `/sales-admin/orders/{order_id}/fulfillment` … |

## Backend — service

| Berkas | Baris | Ringkas |
|---|---:|---|
| `advance_report_service.py` | 111 | KEB-PDPT (Sesi #090) — Laporan Uang Muka Pelanggan. |
| `ai_actions.py` | 222 | Tanya KN — draf tindakan dari jawaban AI. Tidak ada yang tersimpan/terkirim sebelum pengguna menekan Setujui. |
| `ai_chat_service.py` | 345 | Tanya KN F2.2 — orkestrator chat bebas (OpenAI Responses API + function calling). |
| `ai_cost.py` | 42 | Tanya KN F2.5 — biaya per panggilan model + rem anggaran bulanan (`ai.monthly_budget_usd`). |
| `ai_forecast.py` | 112 | Tanya KN — perkiraan: kebutuhan stok 4–8 minggu + saran reorder, risiko pelanggan berhenti order. |
| `ai_insights.py` | 147 | Tanya KN — peringatan anomali otomatis (tanpa model; angka & penyebab dihitung server). |
| `ai_narrative.py` | 115 | Tanya KN F4 — narasi template: ringkasan otomatis dari angka server, atau AI (luna/sol) bila aktif. |
| `ai_number_check.py` | 88 | Tanya KN F2.4 — pemeriksa angka: setiap angka di jawaban harus ada di hasil tool giliran itu. |
| `ai_ops_metrics.py` | 163 | Tanya KN — metrik operasional gudang, QC, makloon & performa supplier (dihitung server, baca-saja). |
| `ai_schedules.py` | 127 | Tanya KN F4 — laporan terjadwal (in-app) + pemeliharaan harian (retensi sesi chat). |
| `ai_templates.py` | 147 | Tanya KN F4 (dasar) — template laporan `tpl-v1`: resep dijalankan server TANPA model. |
| `ai_tools.py` | 504 | Tanya KN F2.1 — eksekusi 6 tool (Lampiran C). Semua baca-saja, identitas pengguna asli. |
| `ai_usage_report.py` | 112 | Halaman Biaya AI — pemakaian harian per fitur, per pengguna, per model (tanggal WIB). |
| `alert_ops_service.py` | 356 | PS-21 — Generator ALERT OPERASIONAL (quick win di atas mesin R6.5/R6.6). |
| `alert_service.py` | 331 | R6.5 — Generator ALERT untuk Scheduler & Notifikasi (Kain Nusantara). |
| `amendment_service.py` | 1058 | FASE G-1 — **FONDASI AMANDEMEN**: tidak ada lagi perubahan angka secara diam-diam. |
| `analytics_catalog.py` | 144 | Tanya KN F1.2 — katalog semantik `cat-v1` sebagai DATA (satu-satunya tempat definisi). |
| `analytics_config.py` | 22 | Tanya KN F0.5 — kebijakan data asisten analitik (keputusan klien §7) dari konfigurasi. |
| `analytics_engine.py` | 732 | Tanya KN F1.3 — kompilator `query_metrics` & `analyze_change` → agregasi Mongo. |
| `analytics_facts.py` | 289 | Tanya KN F1.1 — tabel fakta `fact_sales_lines`. |
| `analytics_snapshots.py` | 73 | Tanya KN F5 — snapshot harian stok & piutang (23.55 WIB) → posisi `as_of` masa lalu di mesin analitik. |
| `analytics_time.py` | 218 | Tanya KN F0.1 — periode analitik dalam WIB (Asia/Jakarta) → batas UTC. |
| `app_url.py` | 90 | app_url — SATU sumber kebenaran **URL publik aplikasi** (untuk QR & tautan cetak). |
| `approval_backlog_service.py` | 848 | services/approval_backlog_service.py — SATU sumber "apa yang menunggu keputusan". |
| `approval_matrix_service.py` | 584 | PS-20 (D-14) — **Penegakan matriks persetujuan divisi** + antrean "Persetujuan Saya". |
| `approval_reminder.py` | 133 | services/approval_reminder.py — PENGINGAT HARIAN "keputusan yang menunggu Anda". |
| `approval_service.py` | 138 | services/approval_service.py — **ATURAN AMBANG PERSETUJUAN** (`approval_rules`). |
| `ar_aging_service.py` | 515 | EPIC7-A — AR / Piutang Aging (read/derived report). |
| `ar_receipt_service.py` | 809 | AR Receipt service (EPIC3B) — Penerimaan pembayaran customer + aplikasi ke SO. |
| `atomic_claim.py` | 63 | Klaim atomik dokumen induk untuk endpoint tulis multi-koleksi (T-01 Opsi B — saga). |
| `atp_policy.py` | 98 | KN-D11 (audit 2026-09-21) — SATU definisi ATP (Available-to-Promise) untuk seluruh sistem. |
| `backorder_service.py` | 218 | Backorder service (Sub-fase 1.6) — auto-fulfill lifecycle. |
| `bank_recon_service.py` | 1414 | FASE G-8 — REKONSILIASI BANK OTOMATIS (skor berbobot · split · aturan · titipan). |
| `bank_service.py` | 277 | Bank/Cash Accounts service (EPIC7-B) — multi-akun kas & bank + rekonsiliasi. |
| `bank_statement_parser.py` | 536 | FASE G-8 — PARSER MUTASI BANK MULTI-FORMAT. |
| `base_fabric.py` | 26 | Kain dasar — rujukan induk master data (mis. kain polos woven yang menjadi bahan printing). |
| `blanket_po_service.py` | 348 | Blanket / Contract PO service (P2 — call-off). |
| `budget_service.py` | 531 | R6.3 — Budget Control penuh: Anggaran vs Komitmen vs Realisasi + enforcement. |
| `cash_advance_service.py` | 647 | Service — Cash Advance (Form PD) + Pertanggungjawaban (Settlement) + Expense Categories. |
| `cash_entity_service.py` | 98 | FASE E-7 (E7.4 · keputusan pemilik 3a) — **KAS TINGKAT GRUP DIHAPUS**. |
| `cash_flow_service.py` | 154 | FINANCE — Laporan Arus Kas (Cash Flow Statement). FN-04: klasifikasi per jurnal kas |
| `cash_ledger.py` | 73 | R5.3 — Cash ledger helper untuk refund retur (sales & purchase). |
| `cashflow_forecast_service.py` | 136 | FINANCE — Proyeksi Arus Kas (Cash Flow Forecast) (EPIC P1-3). |
| `catalog_access.py` | 53 | Pagar bersama template, SKU, media dan relasi R&D. Produk tetap SHARED. |
| `catalog_rules.py` | 102 | Kontrak murni induk/axis/SKU; digunakan R&D, generator, editor dan impor. |
| `client_dataset_service.py` | 291 | L01 LN-011 — IMPOR DATASET CLIENT (DATA-01): artikel · tahap · jenis kain · supplier/warna. |
| `closing_service.py` | 538 | FINANCE — Tutup Buku (Period Closing) bulanan & tahunan. |
| `color_card_pdf.py` | 76 | Kartu Warna Pelanggan (PDF) — swatch, kode, versi supplier per warna + kop badan usaha aktif. |
| `color_lock_service.py` | 165 | Kunci Warna Eksklusif + Penanda Warna Otomatis. |
| `color_service.py` | 410 | M0 — Color Library service (Pantone-style master warna). |
| `config_currency.py` | 64 | FASE G-0 — Konsumen nyata untuk `finance.base_currency` & `finance.fiscal_year_end_month`. |
| `config_health.py` | 121 | FASE G-0 — KESEHATAN KONFIGURASI: apakah setiap setting benar-benar tersambung? |
| `config_impact_service.py` | 258 | FASE G-0 — DAFTAR DAMPAK (Blast-Radius Picker). |
| `config_resolver.py` | 603 | FASE G-0 — CONFIG RESOLVER: nilai efektif berlapis + jejak "kenapa begini" + berlaku-sejak. |
| `config_service.py` | 557 | Config service (Fase 1A) — Configuration Foundation. |
| `config_simulator.py` | 628 | FASE G-0 — SIMULATOR KONFIGURASI ("Coba dulu"). |
| `consolidation_service.py` | 767 | FINANCE — Konsolidasi Grup + Eliminasi Intercompany. |
| `consolidation_stale_service.py` | 57 | consolidation_stale_service — deteksi entri eliminasi antar-PT yang BASI (Fase 4 · R6, G1-33). |
| `contra_bon_reminder.py` | 236 | FASE G-7 — **JADWAL TUKAR FAKTUR** per supplier + pengingat otomatis. |
| `contra_bon_scan.py` | 247 | FASE G-7 — Pemeriksa invarian **KONTRABON** (INV-CB-01..04). |
| `contra_bon_service.py` | 1415 | FASE G-7 — KONTRABON ADVANCED (siklus tukar faktur supplier). |
| `contract_service.py` | 582 | FASE D — KONTRAK MITRA/SUPPLIER (`supplier_contracts`) + MESIN TARIF CONFIGURABLE. |
| `costing_service.py` | 146 | Costing service (EPIC3A) — Weighted Average Cost (WAC) per produk/entitas. |
| `crm_omnichannel_service.py` | 249 | CRM Omnichannel (MVP manual) — Lead pipeline + timeline interaksi. |
| `csv_money.py` | 39 | SATU definisi “cara membaca angka rupiah dari CSV” untuk seluruh sistem. |
| `custom_role_service.py` | 369 | PERAN KUSTOM & TINGKAT AKSES — aturan bisnis untuk layar "Peran & Hak Akses". |
| `customer_feedback_service.py` | 153 | FEEDBACK / KOMPLAIN PELANGGAN per Sales Order (2026-09, sesi #075). |
| `customer_merge_service.py` | 99 | P18 MASTER-05 / COMM-01 — gabung pelanggan duplikat (sumber → target) tanpa memutus riwayat. |
| `customer_price_service.py` | 568 | F1b (D-14) — **Daftar Harga per Pelanggan** (customer pricelist) dengan histori, |
| `customer_service.py` | 562 | Customer/CRM service (KN_17 CRM-lite). |
| `cutting_service.py` | 223 | L06 LN-061 — Meja Cutting/Admin Cutting: kemampuan lokasi, antrean potong, serah-terima hasil potong. |
| `cycle_count_service.py` | 176 | CYCLE COUNT RFID — stock opname kilat via sweep handheld. |
| `data_hygiene_service.py` | 204 | Kebersihan Data (K-1/K-2 otomatis) — normalisasi EYD nama & nomor telepon pada data LAMA. |
| `delivery_service.py` | 267 | delivery_service.py — Pengiriman dokumen via WhatsApp (mode simulasi default) + |
| `demo_seed_service.py` | 97 | Demo Seed Service |
| `design_gallery_service.py` | 721 | HRD H5 services — Design Gallery (motif kain) + upload gambar (storage lokal). |
| `design_ownership_service.py` | 265 | UAT 24 Okt (P1 + P6) — KEPEMILIKAN DESAIN & rantai desain → SKU. |
| `design_request_service.py` | 890 | FASE D — **PERMINTAAN DESAIN** (`<ENT>/DSR-#####`) + rapor desainer. |
| `design_studio_service.py` | 762 | Design Studio — pengembangan master desain (`design_gallery`) menjadi siklus hidup utuh. |
| `digest_service.py` | 231 | R6.6 — RINGKASAN HARIAN (Daily Digest) untuk kanal WhatsApp. |
| `dispatch_payment_gate.py` | 160 | F-10 (uji pra-UAT 2026-10-21, keputusan owner Q-02) — termin bayar-sebelum-kirim MENAHAN pengiriman. |
| `dn_rules.py` | 339 | GRN Fase 4 — aturan murni pembacaan surat jalan (§4.8): angka, qty declared, nomor PO, pencocokan baris, total |
| `doc_label_service.py` | 174 | doc_label_service — NOMOR DOKUMEN yang layak dibaca untuk pasangan (jenis sumber daya, id teknis). |
| `doc_refs_service.py` | 939 | FASE G-4 — **RELASI DOKUMEN TERSIMPAN** (`refs[]` dua arah) + Jejak Dokumen. |
| `document_relations_service.py` | 285 | EPIC 6 — Document Relations / Process Timeline service. |
| `dual_qty_service.py` | 318 | FASE U — DUA SATUAN (jumlah roll + ukuran) · satu pintu untuk semua dokumen. |
| `entity_context_service.py` | 169 | F0-A — Entity identity & context helper (Multi-Entity foundation). |
| `entity_lifecycle_service.py` | 605 | FASE E-1 — SIKLUS HIDUP BADAN USAHA (satu pintu untuk semua pagar). |
| `entity_location_service.py` | 32 | entity_location_service — lokasi tervalidasi pada UBAH badan usaha (Fase 4 · R6, G5-25). |
| `entity_master_service.py` | 611 | entity_master_service (FASE E-4 · E4a) — MASTER BERLAPIS: **global → badan usaha**. |
| `entity_provisioning_service.py` | 198 | F0-F + FASE E-1 — Provisioning & VALIDASI badan usaha (SATU JALUR). |
| `entity_readiness_service.py` | 135 | FASE E-1 (E1.9) — DAFTAR KESIAPAN BADAN USAHA. |
| `epc.py` | 45 | RF-01/RF-11 — SATU kontrak EPC: disimpan & dicocokkan sebagai 24 hex UPPERCASE tanpa pemisah. |
| `equity_statement_service.py` | 65 | FINANCE — Laporan Perubahan Ekuitas (Statement of Changes in Equity). |
| `escalation_service.py` | 239 | R6.6 — ESKALASI BERTINGKAT alert yang belum ditindak. |
| `esign_service.py` | 205 | esign_service.py — Logika e-sign: request OTP, verifikasi + simpan tanda tangan, |
| `export_engine.py` | 636 | L11 LN-110/LN-113 — mesin Pusat Export: validasi kolom/filter, kueri ber-scope, join to-one, |
| `export_registry.py` | 296 | L11 LN-110 — registry dataset bisnis untuk Pusat Export. |
| `export_registry_more.py` | 326 | L11 lanjutan — dataset tambahan: analitik Finance (LN-111), rapor staf (LN-112), dan pemetaan sisa koleksi bis |
| `export_schedule.py` | 105 | L11 — Export terjadwal: template berjalan mingguan/bulanan dengan identitas & hak PEMILIK saat itu. |
| `fabric_type_master_service.py` | 51 | L01 — MASTER JENIS KAIN (`md_fabric_types`): woven/knit benih + tambahan admin (mis. dari laporan |
| `field_visibility.py` | 245 | L01 (LN-012) — visibilitas atribut stok per peran: grade · LOT · asal lokal/impor. |
| `finance_bi_service.py` | 133 | FINANCE — BI Keuangan (dashboard analitik) diturunkan dari GL. |
| `finance_case_actions.py` | 612 | FASE G-9 — EKSEKUTOR AKSI PLAYBOOK KASUS KEUANGAN. |
| `finance_case_playbooks.py` | 245 | FASE G-9 — REGISTRY 11 PLAYBOOK KASUS KEUANGAN. |
| `finance_case_scan.py` | 259 | FASE G-9 — PEMINDAI KASUS OTOMATIS + PEMERIKSA INVARIAN. |
| `finance_case_service.py` | 553 | FASE G-9 — PUSAT KASUS KEUANGAN (Finance Exception Desk). |
| `finance_tower_service.py` | 128 | FINANCE — Control Tower (Dashboard Keuangan terpadu) (EPIC P1-5). |
| `financial_statement_service.py` | 313 | FINANCE — Laporan Keuangan (Laba-Rugi & Neraca) diturunkan dari GL. |
| `fixed_asset_service.py` | 546 | R6.2 — Fixed Assets & Depresiasi (straight-line) + disposal gain/loss. |
| `fleet_service.py` | 137 | Armada internal — master kendaraan (`fleet_vehicles`, SCOPED) + ketersediaan sopir. |
| `fulfillment_decision_service.py` | 370 | FASE E-8 (E8.10b#4 · US16) — **KEPUTUSAN PEMENUHAN** milik Admin Sales. |
| `fulfillment_plan_service.py` | 294 | 2026-10 — RENCANA PEMENUHAN per baris (keputusan pemilik): Admin Sales membagi |
| `fulfillment_service.py` | 386 | Fulfillment & ATP service (Fase 1 / Sub-fase 1.4 — ATP & Fulfillment Modes). |
| `fulfillment_status.py` | 144 | Fulfillment status engine (Sub-fase 1.8). |
| `fulfillment_wizard_service.py` | 182 | FASE R7 — FULFILLMENT WIZARD: matriks skenario S1–S8 menjadi aksi terpandu. |
| `gate_evaluator.py` | 134 | P09 — SATU evaluator gate (ingest perangkat, simulator, kiosk). Keputusan berbasis MOVEMENT aktif |
| `gemini_image_service.py` | 193 | FB-01 — Ilustrasi AI Galeri Desain via Google Gemini "Nano Banana Pro" (SDK google-genai LANGSUNG). |
| `gl_mapping_registry.py` | 159 | GL-01 — registri kebutuhan akun (SSOT di kode). Satu baris = satu kebutuhan fitur. |
| `gl_mapping_service.py` | 187 | GL-01 — pemetaan akun terpusat. Resolver: mapping PT → mapping global → bawaan registri. |
| `gl_service.py` | 3757 | EPIC7-C — General Ledger & Chart of Accounts (akuntansi inti). |
| `goods_receipt_close_service.py` | 595 | GRN Fase 2 — rekonsiliasi (§4.4), penyelesaian selisih, penutupan (§4.5), sisa PO, tolak & batal. |
| `goods_receipt_ocr_service.py` | 591 | GRN Fase 4 — baca surat jalan dengan OpenAI: praproses, panggil, pembaca kedua, log biaya, rem anggaran, pemet |
| `goods_receipt_service.py` | 1001 | GRN Fase 2 — Kedatangan Barang (satu surat jalan · satu mitra): buat, berkas, kepala SJ, baris, hitung. |
| `grade_master_service.py` | 171 | L01 LN-012 — MASTER GRADE (`md_grades`): tambah, ubah, aktif/nonaktif tanpa ubah kode. |
| `grade_service.py` | 161 | Grade governance service — Fase A · PS-09 · D-01/D-19/D-23. |
| `group_partner_service.py` | 305 | FASE E-7 (E7.2 + E7.7) — **PAGAR "LAWAN TRANSAKSI TERNYATA PT SENDIRI"**. |
| `home_service.py` | 498 | EPIC 1 — Agregasi Home/landing per role (Control Tower / Performa Saya). |
| `hr_ai_service.py` | 117 | H5 service — AI auto-tag motif via Anthropic Claude (SDK LANGSUNG, bukan Emergent). |
| `hr_analytics_service.py` | 210 | HRD H6 service — HR Analytics (Dashboard BI SDM). |
| `hr_attendance_service.py` | 273 | HRD H1 services — Absensi (attendance). |
| `hr_kpi_service.py` | 167 | HRD H5 services — KPI Design (input manual per karyawan/periode + rekap). |
| `hr_leave_service.py` | 404 | HRD H3 services — Cuti, Izin & Lembur (Leave/Permit & Overtime). |
| `hr_payroll_pdf.py` | 111 | HRD H4 — Payslip PDF (reportlab). Slip gaji ringkas, profesional, Bahasa Indonesia. |
| `hr_payroll_service.py` | 601 | HRD H4 — Payroll & Payslip engine + run lifecycle. |
| `hr_service.py` | 176 | HRD services (FASE H0) — helper murni-orchestration untuk modul HR. |
| `inbound_complete_service.py` | 613 | Penyelesaian penerimaan tugas inbound — SATU-SATUNYA jalur yang memposting stok, `received_qty` PO, |
| `input_tax_service.py` | 164 | Faktur Pajak Masukan (tax_invoices_in) service — Fase 5.5 / P0-3. |
| `inspection_service.py` | 1809 | FASE I — **INSPEKSI & QC SEBAGAI DOKUMEN** (`<ENT>/INS-#####`). |
| `integrations_service.py` | 159 | H5 service — Integrasi pihak ketiga (config runtime di system_settings). |
| `interco_loan_service.py` | 274 | FASE E-7 (E7f) — **PINJAMAN UANG ANTAR-PT** (`<ENT>/ICL-#####`). |
| `interco_margin.py` | 427 | FASE G-6b — **RAPOR MARGIN GRUP** antar-PT (realized vs unrealized). |
| `interco_money_service.py` | 213 | FASE E-7 (E7f + E7g) — **UANG & ASET ANTAR-PT** yang bukan jual-beli. |
| `interco_price_service.py` | 176 | 2026-10 — HARGA INTERNAL antar-PT (kontrak `supplier_contracts` contract_type=internal). |
| `interco_reminder.py` | 179 | FASE G-6b — **PENGINGAT SETTLEMENT** saldo antar-PT yang menganggur. |
| `interco_return_service.py` | 914 | FASE G-6b — **RETUR ANTAR-PT** (jalan resmi setelah barangnya sudah berpindah). |
| `interco_service.py` | 1947 | FASE G-6 — Layanan **TRANSAKSI ANTAR ENTITAS** (jual-beli antar-PT dalam grup). |
| `interco_tax_service.py` | 394 | FASE G-6b — **FAKTUR PAJAK INTERNAL** untuk transaksi antar-PT ber-PPN. |
| `internal_request_service.py` | 513 | FASE E-7 (E7.1 · gelombang 2 “E7d”) — **PERMINTAAN INTERNAL** (`<ENT>/PIN-#####`). |
| `inventory_drift_watch.py` | 127 | services/inventory_drift_watch.py — PEMANTAU DRIFT PERSEDIAAN (INV-GL-DRIFT). |
| `inventory_service.py` | 213 | Inventory service: reservation expiry projections & document rendering. |
| `label_decoder_service.py` | 268 | FASE SL — Decoder LABEL SUPPLIER (GS1-128 · QR JSON · teks berpemisah · regex). |
| `label_printer_service.py` | 198 | Label printer service: Generate ZPL and ESC/POS commands for barcode labels. |
| `landed_cost_service.py` | 244 | Landed Cost service (Fase 5.4 — P0-5). |
| `line_scope.py` | 434 | FASE L — PAGAR LINI PRODUK (woven · knit · printing · dan lini baru berikutnya). |
| `loading_check_service.py` | 344 | FASE R4 — FINAL LOADING CHECK: sweep handheld vs manifest SO sebelum naik mobil. |
| `location_scope.py` | 122 | IMP-20 (P01) — cakupan LOKASI KERJA pengguna gudang (site → gudang). |
| `location_service.py` | 354 | Location (Zona → Lemari/Rak → Tingkat → Bin) & Putaway — Fase 5, diperkuat P02. |
| `location_stock_tree.py` | 121 | L10 LN-100/LN-102 — stok per alamat fisik (Lokasi → Gudang → Zona → Lemari → Rak → Bin). |
| `logistics_service.py` | 689 | FB-02 — Modul Logistik (koleksi `logistics_deliveries`, SCOPED, nomor LG-). |
| `lot_migration.py` | 132 | FASE C — Migrasi & backfill lot (IDEMPOTEN). |
| `lot_service.py` | 643 | FASE C — LOT KELAS SATU (`inventory_lots`) · SSOT identitas batch & genealogi. |
| `lot_trace_service.py` | 318 | FASE C — Silsilah (genealogi), Recall, dan Label lot. |
| `makloon_calc_service.py` | 215 | FASE D — ESTIMASI OUTPUT MAKLOON BERBASIS GSM (PS-03) + EVALUASI SELISIH (PS-11). |
| `makloon_claim_service.py` | 363 | FASE D — SELISIH & KLAIM MAKLOON (PS-11 · keputusan **D-09**). |
| `makloon_loss_service.py` | 258 | L01 (keputusan owner 2026-10-16) — SUSUT / HILANG BAHAN DI MITRA untuk MKO batal. |
| `makloon_material_ledger.py` | 98 | L04 LN-043 — buku bahan makloon per MKO: forecast · dicadangkan · dikirim/di mitra · terpakai · kembali · susu |
| `makloon_order_service.py` | 1817 | M3 + FASE D — Makloon Order service: orkestrasi transaksi subkontrak (Procure→Process→Pay). |
| `makloon_recap_service.py` | 106 | L01 — REKAP SUSUT & KLAIM PER MITRA MAKLOON (baca saja). |
| `makloon_service.py` | 150 | M1 — Makloon service: Makloon 360 + scorecard proses (dari data nyata). |
| `marketing_cost_service.py` | 309 | COMM-04 (keputusan PG04) — realisasi biaya kampanye marketing → jurnal Beban Pemasaran. |
| `marketing_ext.py` | 299 | marketing_ext.py — Marketing lanjutan: master Akun Sosmed per badan usaha, dashboard analitik |
| `marketing_service.py` | 378 | marketing_service.py — Sosial Media & Konten: kampanye, kalender/perencana post, lampiran, |
| `master_governance_service.py` | 143 | W2-REQ-02 — tata kelola master produk: preview legacy → batch migrasi berjejak → rollback per batch. |
| `master_registry.py` | 466 | master_registry (FASE L, diperluas FASE T) — JEMBATAN master ↔ `domain_registry`. |
| `master_usage_service.py` | 82 | IMP-14 (P01) — jejak pemakaian master & kebijakan hapus. |
| `material_reservation_service.py` | 191 | W2-REQ-07 — reservasi bahan makloon sejak PR makloon disetujui (soft-reservation, tanpa jurnal). |
| `mdq_cut_service.py` | 107 | L04 LN-042 — POTONG MD QUALITY (default 0,25 yard) sebagai MUTASI PEMAKAIAN tersendiri. |
| `movement_label_service.py` | 269 | movement_label_service — nomor dokumen yang LAYAK DIBACA pada mutasi stok. |
| `notification_audience.py` | 189 | notification_audience — SATU penyelesai "siapa yang harus diberi tahu". |
| `notification_doc_ref.py` | 94 | notification_doc_ref — DOKUMEN yang dituju sebuah notifikasi (bukan hanya layarnya). |
| `notification_read.py` | 35 | Status DIBACA per orang. |
| `notification_scope.py` | 58 | notification_scope — SATU aturan "notifikasi mana yang relevan untuk pengguna ini". |
| `notification_service.py` | 475 | Notification service — pembuatan notifikasi + generator dari event REAL. |
| `ocr_openai_client.py` | 168 | GRN Fase 4 — satu-satunya modul yang meng-import `openai` (§4.8). |
| `ocr_sample_service.py` | 245 | Sample Uji OCR — foto SJ nyata + kunci jawaban yang dicek manusia, untuk mengukur ketepatan baca sebelum dipak |
| `ocr_sj_v2.py` | 159 | GRN Fase 4 — prompt & JSON Schema `sj-v2` (disalin persis dari Lampiran A & B spesifikasi GRN/OCR). |
| `od_cancel_credit_note.py` | 142 | Keputusan owner 2026-10-21 — batal item Pesanan Khusus pada SO yang SUDAH TERBIT → NOTA KREDIT otomatis. |
| `od_pricing_service.py` | 363 | UAT 24 Okt (P2) — harga Pesanan Khusus sesuai arahan pemilik SO-12 + nego lewat harga khusus SO. |
| `order_journey_service.py` | 332 | FASE E-8 (E8.14 · US12) — **PERJALANAN PESANAN** (read-only, untuk sales lapangan). |
| `payment_plan_service.py` | 659 | FASE G-2 — **RENCANA PEMBAYARAN FLEKSIBEL** (`payment_plans`). |
| `payment_variance_service.py` | 1285 | FASE G-3 — **SELISIH PEMBAYARAN: LEBIH & KURANG BAYAR** (`payment_variance_decisions`). |
| `pdf_engine.py` | 378 | pdf_engine.py — Mesin render PDF asli (server-side) untuk semua dokumen bisnis. |
| `pdf_resolvers.py` | 1337 | pdf_resolvers.py — Ubah dokumen sumber (per doc_type) menjadi CONTEXT ternormalisasi |
| `pdf_service.py` | 461 | pdf_service.py — Orkestrasi render dokumen: template config + branding entitas + |
| `penalty_service.py` | 596 | FASE G-2 — **DENDA KETERLAMBATAN SEBAGAI DOKUMEN** (`penalties`). |
| `period_unlock_service.py` | 293 | FASE G-5 — UNLOCK PERIODE BEROTORITAS ("wajib dua orang & menutup sendiri"). |
| `placement_rules.py` | 260 | P02 (IMP-22/24/25) — evaluator penempatan BERSAMA untuk semua jalur (putaway manual, scan |
| `po_amendment_service.py` | 376 | Phase 7.2 — PO Amendment / Version History (logic extracted from router). |
| `po_board_service.py` | 640 | FASE P — **PAPAN PO PER LINI** (progres tahap seperti kertas kerja MD). |
| `po_close_settlement_service.py` | 85 | L02 LN-023-T02 — rekonsiliasi PO saat ditutup-kurang: sisa order, tagihan (AP) dan kelebihan bayar. |
| `po_line_guard.py` | 16 | KN-B15 — satu produk hanya boleh muncul di SATU baris PO (semua jalur: buat PO, PR→PO, amandemen). |
| `po_variance_task_service.py` | 194 | W2-REQ-06 — tugas keputusan MD atas selisih penerimaan PO (tunggu / amendment / short-close). |
| `pos_recommendation_service.py` | 215 | F-4b — POS advanced recommendations, dihitung dari histori `sales_orders` (TANPA AI, TANPA koleksi baru). |
| `pr_sourcing_service.py` | 1029 | FASE E — SOURCING PR: routing `purchase|makloon` + realisasi PR → PO / Order Makloon. |
| `price_approval_service.py` | 268 | Sub-fase 1.7 + F1b — bagian **BERSAMA** alur Harga Khusus (`price_approvals`). |
| `price_guard_service.py` | 172 | F1b — SATU definisi **batas bawah harga jual** (price floor) untuk seluruh sistem. |
| `pricelist_service.py` | 418 | F1a — Pricelist per-entitas (harga jual per-PT) dengan histori & tanggal efektif. |
| `printer_stuck_watch.py` | 60 | Sesi 15 — label tertahan: antrean label menunggu > N menit tanpa printer online di gudang itu. |
| `process_recipe_service.py` | 114 | M1 — Process Recipe service: CRUD helper + forecast konversi (aman). |
| `product_exclusivity.py` | 149 | PS-20 — Produk eksklusif per sales ("PO sendiri"). |
| `product_media_service.py` | 111 | Media per SKU, lokal, ber-versi CAS. Foto nyata/mockup ditinjau sebelum sales melihat. |
| `product_template_service.py` | 398 | F1b — Product Templates & Variants (pendekatan ADDITIVE/non-destruktif). |
| `product_variant_service.py` | 240 | Satu induk, SKU tetap: jalur bersama untuk seluruh penulis produk. |
| `production_service.py` | 563 | R6.4 — Produksi In-House (BOM + Work Order). |
| `profitability_service.py` | 275 | FINANCE — Analisis Profitabilitas / Margin (EPIC P0-2 · R5.6). |
| `purchase_requisition_service.py` | 560 | Depth #2 — Purchase Requisition (PR) service + Reorder/Replenishment. |
| `purchase_return_service.py` | 1098 | Depth #1 — Retur Beli (Purchase Return / Nota Debit). |
| `purchase_return_state.py` | 66 | R4 — Supplier RMA lifecycle untuk Retur Beli (Purchase Return). |
| `putaway_order_service.py` | 505 | FASE R2 — PUTAWAY ORDER (PA): dokumen pemindahan roll dari gedung transit ke |
| `qc_inspection_service.py` | 391 | QC 4-Point Inspection service — Fase 6.2 (P1). |
| `qc_service.py` | 488 | Depth #3a — QC Hold / Quarantine saat Goods Receipt. |
| `receiving_mode_service.py` | 84 | GRN Fase 7 — beralih penuh: mode penerimaan per badan usaha (`receiving.mode` = legacy | grn). |
| `receiving_roll_service.py` | 426 | Kelahiran roll `receiving` saat penerimaan (GRN Fase 1: dipindah dari `routers/inbound_scan_label.py`). |
| `receiving_uom_service.py` | 497 | FASE F-1 — PENERIMAAN BERBASIS **SATUAN SUPPLIER** (lanjutan Fase B & Fase E). |
| `repair_order_service.py` | 344 | UAT 24 Okt (P7) — dokumen Perbaikan (`repair_orders`, nomor RPR-…): roll jadi yang cacat / warnanya meleset |
| `restock_service.py` | 288 | PS-21(a) — Repeat/Restock 1-klik dari Sales Order → Purchase Requisition. |
| `restock_source_service.py` | 133 | P05 IMP-19 — sumber restock per ARTIKEL (product_templates) dan penegakan jalur PR/PO/MKO. |
| `return_attachment_service.py` | 57 | Lampiran bukti retur — satu jalur untuk retur ke supplier & retur antar-PT (permintaan pemilik 23 Okt 2026). |
| `return_chain_service.py` | 328 | FASE E-9 (E9.6) — **JEJAK RANTAI RETUR**. |
| `return_compensation_service.py` | 143 | LN-092 — cutloss & diskon retur (KLR-01/02/06/07, owner 2026-10-19). |
| `return_cutloss_split_service.py` | 248 | CUT-01..05 — pemecahan fisik roll cutloss setelah QC: potongan baik / BS / dibuang. |
| `return_disposition_service.py` | 474 | LN-093 — tujuan barang retur berantai Sukacita → CST → supplier. |
| `return_evidence_service.py` | 38 | L08 LN-080-T03 — kewajiban bukti (lampiran) retur per tahap, dapat dikonfigurasi per badan usaha. |
| `return_exception_service.py` | 76 | LN-083/LN-092 — pengecualian retur (alasan + bukti foto + keputusan berwenang) dan gerbang settle. |
| `return_grade_impairment.py` | 76 | LN-091-T02 — kerugian turun grade barang retur. |
| `return_identity_service.py` | 156 | L08 LN-082 — identitas roll retur: roll utuh kembali dengan ID/nomor/EPC yang sama, |
| `return_journey_service.py` | 189 | L08 LN-081 — perjalanan fisik barang retur per roll (terima → kirim/dalam perjalanan → tiba), |
| `return_logistics_service.py` | 158 | GL-01 × KLR-11 — biaya logistik retur: cara kirim, penanggung, dan jurnal otomatis. |
| `return_operator_view.py` | 84 | F-11-layar (uji pra-UAT 2026-10-21) — Gudang & QC membuka retur pelanggan untuk scan & QC. |
| `return_policy_service.py` | 473 | R0 — Return Policy Engine (Master Data). |
| `return_replacement_service.py` | 239 | LN-090 T02/T03 — pesanan pengganti nyata untuk retur tukar barang (KLR-03/04/05, owner 2026-10-19). |
| `return_roll_settlement_service.py` | 534 | UAT 23 Okt (permintaan pemilik) — PENYELESAIAN RETUR PER ROLL, boleh bertahap. |
| `return_rolls_service.py` | 272 | L08 LN-080 — retur hanya dari barang yang BENAR-BENAR terkirim (roll per SJ) + batas kumulatif atomik per SO. |
| `return_service.py` | 1980 | Sub-fase 1.11 — Returns & Barang Sisa |
| `return_settlement_policy.py` | 37 | LN-091/LN-092 — kebijakan penyelesaian retur (owner 2026-10-19: KLR-01/02/06/07/10). |
| `return_state.py` | 99 | R1 — State machine retur jual (Sales Return). |
| `return_timeline_service.py` | 157 | L08 LN-081 — satu timeline kasus retur dengan jalur terpisah: izin · perjalanan masuk · |
| `rfid_incident_service.py` | 209 | FASE R6 — Insiden gate MERAH: alarm → acknowledge operator → resolve, |
| `rfid_ingest_service.py` | 373 | FASE R3 — Device Ingest API (kontrak hardware: gate Chainway UR300 / handheld / |
| `rfid_print_service.py` | 435 | FASE R1 — Print job tag RFID (bulk dari GR/roll transit) + sesi verifikasi handheld. |
| `rfid_service.py` | 486 | RFID service (Fase 5 — SIMULATOR). |
| `rfq_service.py` | 385 | RFQ / Quotation service — Fase 6.1 (P1 Sourcing). |
| `rnd_catalog_validation.py` | 65 | Validate source relations before saving any R&D specification. |
| `rnd_flow_service.py` | 236 | UAT 24 Okt (P3/P4) — aturan alur R&D produk baru yang dipakai `rnd_sample_service` & router. |
| `rnd_gate.py` | 133 | FASE F (PS-12) — **Penjaga lifecycle produk** + resolver kebijakan R&D. |
| `rnd_kpi_export.py` | 553 | PS-18 — **EKSPOR LAPORAN KPI DESAINER** (CSV · Excel · PDF). |
| `rnd_kpi_service.py` | 774 | PS-18 — Layanan **KPI DESAINER** (kinerja pelaksana R&D yang terhitung sendiri). |
| `rnd_org_service.py` | 95 | PS-17 — Layanan Organisasi R&D (divisi + anggota). |
| `rnd_required_tests.py` | 91 | W2-REQ-03 — uji wajib SKU hasil MD (keputusan pemilik 2026-10-04: PERINGATAN, bukan blokir). |
| `rnd_revalidation_service.py` | 340 | L03 LN-034 — uji ulang SKU existing per supplier: siklus terpisah, hasil teknis tanpa kontrak, keputusan PIC. |
| `rnd_sample_service.py` | 1627 | FASE F · PS-12/13/14/18/19 — Layanan **PERMINTAAN SAMPLE** (`md_samples`), |
| `rnd_sla_service.py` | 176 | PS-18 — **ESKALASI SLA SAMPLE R&D** (dari papan pasif menjadi pengingat aktif). |
| `rnd_spec_service.py` | 507 | FASE F · PS-12 — Layanan **SPESIFIKASI PRODUK versi R&D** (`md_specs`). |
| `role_desk_service.py` | 241 | U-2 (2026-09) — Meja kerja untuk 6 peran tersisa: admin, manager, sales, warehouse, designer, driver. |
| `role_reality_service.py` | 691 | **CEK KENYATAAN PERAN** — utang migrasi (ii) FASE E-8/E-6. |
| `roll_cost_history.py` | 88 | services/roll_cost_history.py — JEJAK setiap perubahan HPP satu roll. |
| `roll_hold_service.py` | 76 | QC-06 — Tahan (HOLD) & Lepas (RELEASE) manual satu roll. |
| `roll_service.py` | 2510 | Roll service (Fase 0.5) — Roll-as-SSOT inventory engine. |
| `roll_timeline_service.py` | 173 | JEJAK BARANG (Item Passport) — timeline satu roll lintas SEMUA dokumen. |
| `saga_lock_watch.py` | 93 | services/saga_lock_watch.py — PEMANTAU KUNCI SAGA MENGGANTUNG (T-01 Opsi B). |
| `sales_force_service.py` | 465 | Sales Force service (KN_17 §6) — KPI per salesperson + komisi (pencairan + tiered). |
| `sales_order_dashboard.py` | 99 | Dasbor Pesanan HP sales — omzet, status, tren 8 minggu, pelanggan teratas & pesanan butuh tindakan (data milik |
| `sales_order_helpers.py` | 310 | Helper functions extracted from routers/sales_orders.py. |
| `sales_ownership.py` | 120 | FASE E-8 (E8.4 · US11) — **SATU definisi "Pesanan Saya"**. |
| `sales_p04_service.py` | 393 | P04 — Keep/Pending, aturan grade pelanggan, kandidat roll berkelayakan, ringkasan stok Sales. |
| `sales_stock_service.py` | 87 | Stok GLOBAL untuk layar sales (Kasir/POS, katalog): sales tidak memilah per entitas — |
| `sample_sale_service.py` | 527 | §3-C Jual Sample — SATU alur dengan pesanan roll (keputusan pemilik 2026-09-16). |
| `scheduler_service.py` | 564 | R6.5 — Scheduler (APScheduler) untuk alert & notifikasi terjadwal. |
| `shipment_service.py` | 180 | Shipment service (Sub-fase 1.8) — partial/multi shipment, SSOT-safe. |
| `site_receiving_service.py` | 110 | UAT 24 Okt (P9, fase F1) — LOKASI (site) sebagai tujuan kirim & konteks kerja. |
| `site_stock_service.py` | 46 | UAT 24 Okt (P8, fase F1) — stok per LOKASI untuk katalog POS / HP. |
| `so_approvals.py` | 316 | F5 — Unified Approval SSOT pada Sales Order (`pending_approvals[]`). |
| `so_delivery_service.py` | 65 | F-06 (uji pra-UAT 2026-10-21, keputusan owner Q-01a) — bukti terima (POD) menutup SO otomatis. |
| `so_lifecycle_service.py` | 100 | Inti siklus SO yang dipakai bersama rute & `so_release_service` (Trial 22 Okt 2026, E8): **ajukan persetujuan* |
| `so_line_cancel_service.py` | 126 | FE-01 lanjutan (keputusan owner 2026-10-21) — batalkan SATU baris SO yang lahir dari item Pesanan Khusus. |
| `so_override_service.py` | 352 | 2026-10 — OVERRIDE SO oleh Admin Sales · Manager · Admin, SEBELUM picking. |
| `so_release_service.py` | 162 | Trial 22 Okt 2026 (E8/E10, keputusan pemilik) — **Periksa & lepas ke gudang** dalam SATU langkah Admin Sales. |
| `so_special_price_service.py` | 36 | Trial 22 Okt 2026 (E10, keputusan pemilik) — harga khusus yang diminta di CHECKOUT berlaku **hanya untuk pesan |
| `so_status.py` | 199 | F4 — SSOT Status SO 2-level: STAGE (induk, linear) + SUB-STATUS (anak, kontekstual). |
| `so_tracker_service.py` | 129 | Pelacak SO di setiap meja — pesanan aktif (baru muncul, hilang saat selesai/batal) beserta |
| `so_verify_service.py` | 322 | FASE E-8 (E8.13) — **VERIFIKASI ADMINISTRATIF** pesanan oleh Admin Sales. |
| `special_order_fulfillment.py` | 737 | L03 LN-033 — rute pemenuhan per item Pesanan Khusus: supplier (PR→PO) atau makloon (PR→MKO). |
| `special_order_items.py` | 171 | L03 LN-030 — item Pesanan Khusus: multi-produk, sumber desain per item, redesign. |
| `special_order_link.py` | 80 | Tautan Pesanan Khusus (OD) ↔ SKU hasil R&D: SKU yang lahir dari OD otomatis jadi katalog eksklusif pelanggan. |
| `special_order_phase2.py` | 936 | special_order_phase2.py — Fase 2 Special Order (OD): |
| `special_order_routing.py` | 388 | special_order_routing.py — Fase 1 Special Order (OD) terstruktur: |
| `special_order_service.py` | 439 | Special Order Service - Sub-fase 1.12 |
| `status_history.py` | 50 | SSOT bentuk satu entri `status_history[]` — dipakai SEMUA koleksi. |
| `stock_analytics_service.py` | 470 | Stock Analytics service (Fase 5) — kelas laju jual + aging + nilai persediaan. |
| `stock_availability.py` | 113 | K-04 (keputusan pemilik 26 Okt 2026) — SATU definisi stok "Tersedia" & "Stok rendah". |
| `stock_bucket_service.py` | 659 | F2 — Multi-bucket Stock: operasi WIP & Hold (Pending SO) + papan bucket. |
| `stock_count_roll_service.py` | 394 | L10 LN-101 — opname per roll: snapshot scope node → scan → rekonsiliasi → finalisasi. |
| `stock_count_service.py` | 157 | P10 — stock opname: scope hitung per bin, adjustment per baris (CAS) + jurnal selisih. |
| `storage_service.py` | 146 | Local filesystem storage wrapper (FASE 5 — keputusan owner: storage LOKAL). |
| `store_credit_service.py` | 513 | R5.2 — Store Credit (Saldo Kredit Pelanggan) ledger service. |
| `supplier_dn_profile_service.py` | 237 | GRN — profil surat jalan per mitra (`supplier_dn_profiles`): format angka, nama lain, pemetaan barang. |
| `supplier_item_service.py` | 578 | FASE E — SERVICE `supplier_items` (Barang Supplier / katalog versi supplier). |
| `supplier_service.py` | 485 | Depth #3 — Supplier Intelligence: Price-List resolution + Scorecard. |
| `tax_center_service.py` | 205 | EPIC 7 — Pusat Pajak (PPN + PPh) service. |
| `tax_invoice_service.py` | 321 | Faktur Pajak Jual (tax_invoices) service — Sub-fase 1.9. |
| `text_normalize.py` | 88 | K-1/K-2 (feedback klien 2026-09) — normalisasi penulisan (EYD) & nomor telepon/WhatsApp. |
| `three_way_policy.py` | 32 | KN-D16 (audit 2026-09-21) — SATU ambang toleransi 3-way match (PO ↔ terima ↔ faktur). |
| `tolerances.py` | 9 | KN-A13 (audit 2026-09-21) — SATU sumber toleransi numerik. |
| `trace_print_service.py` | 63 | Cetak Jejak Dokumen — seluruh rantai dokumen satu jangkar sebagai satu PDF audit. |
| `tracking_service.py` | 134 | HRD H2 services — Live Field Tracking (WebSocket). |
| `transfer_receipt_service.py` | 449 | P03 (IMP-26/27) + sisa P02 — transfer terkait SO, penerimaan AKTUAL per roll, exception, cek ulang aturan tuju |
| `trip_service.py` | 140 | L07 LN-070/071 — picking list multi-gudang, cek kesiapan trip multi-SO, manifest armada. |
| `turn_notification_service.py` | 207 | Notifikasi "giliran Anda" — setiap dokumen berpindah tahap, peran yang harus bertindak |
| `uom_rules_service.py` | 482 | FASE B — REGISTRY KONVERSI SATUAN **GLOBAL** + TOLERANSI (D-06/D-07). |
| `uom_service.py` | 503 | Sub-fase 1.13 — UOM Conversion Engine (Multi-UOM). |
| `user_admin_service.py` | 396 | FASE E-2 — AKUN PENGGUNA TERTAUT BADAN USAHA (via HR) & PENEGAKAN AKSES. |
| `variant_axes.py` | 56 | Sumbu varian yang dapat dikonfigurasi pemilik (rnd.variant_axes_default / _optional). |
| `vendor_bill_service.py` | 307 | Vendor Bill service (Fase 5.2 — P0-2) — 3-Way Matching PO ↔ GR ↔ Bill. |
| `wa_alert_service.py` | 278 | R6.5 — Kanal WhatsApp untuk notifikasi/alert (Kain Nusantara). |
| `warehouse_profile_service.py` | 180 | FASE R0 — Profil gudang: site (lokasi), peran gedung, rules penyimpanan, gate config. |
| `warehouse_scope_service.py` | 283 | FASE E-4 (E4.1) — GUDANG BERSAMA vs GUDANG KHUSUS BADAN USAHA. |
| `web_push_service.py` | 110 | Web Push (PWA) — kirim notifikasi lonceng ke HP walau aplikasi sedang ditutup. |
| `wilayah_service.py` | 213 | Wilayah (2026-09) — registry wilayah Indonesia (Kepmendagri 300.2.2-2138/2025 + kode pos) dan |
| `wms_health_service.py` | 125 | DASHBOARD KESEHATAN GUDANG — satu layar ringkas per gudang: |
| `work_desk_service.py` | 1026 | FASE E-8 (E8.7/E8.15/E8.20) — **MEJA KERJA BERBASIS ANTREAN** (Admin Sales & Finance). |
| `zpl_text.py` | 18 | RF-11 — teks bebas di label ZPL di-encode lewat ^FH (hex escape) sehingga ^ ~ _ tidak pernah |

## Koleksi MongoDB (dari pola `db.<nama>.<op>` di kode produksi)

`ai_action_proposals`, `ai_chat_sessions`, `ai_fact_state`, `ai_feedback`, `ai_insights`, `ai_result_cache`, `ai_results`, `ai_schedule_runs`, `ai_schedules`, `ai_usage_log`, `ai_user_templates`, `amendment_reasons`, `approval_rules`, `ar_receipt_failures`, `ar_receipts`, `audit_logs`, `bank_accounts`, `bank_match_rules`, `bank_statement_formats`, `bank_statement_lines`, `bin_locks`, `budgets`, `business_entities`, `cash_advance_settlements`, `cash_transactions`, `client_dataset_imports`, `collection_followups`, `color_library`, `complaint_reasons`, `config_values`, `contra_bons`, `credit_notes`, `credit_overrides`, `crm_interactions`, `crm_leads`, `custom_roles`, `customer_grade_rules`, `customer_prices`, `customers`, `cycle_count_sessions`, `data_hygiene_log`, `data_hygiene_runs`, `design_categories`, `design_gallery`, `design_requests`, `design_tags`, `doc_amendments`, `document_branding`, `document_deliveries`, `document_signatures`, `document_templates`, `entities`, `entity_prices`, `esign_requests`, `expense_categories`, `export_jobs`, `export_templates`, `fact_ar_daily`, `fact_sales_lines`, `fact_stock_daily`, `fin_budget_rules`, `fin_depreciation_entries`, `fin_fixed_assets`, `finance_cases`, `fleet_vehicles`, `generated_documents`, `gl_accounts`, `goods_receipts`, `hr_attendance`, `hr_devices`, `hr_employees`, `hr_field_tracks`, `hr_geofences`, `hr_kpi`, `hr_leave_balances`, `hr_leave_requests`, `hr_org_units`, `hr_overtime`, `hr_payroll_runs`, `hr_payslips`, `hr_shifts`, `hr_visits`, `idempotency_keys`, `incentive_rates`, `inspections`, `integration_settings`, `interco_accounts`, `interco_loans`, `interco_returns`, `interco_transactions`, `intercompany_eliminations`, `internal_requests`, `inventory_balances`, `inventory_lots`, `inventory_movements`, `inventory_rolls`, `invoices`, `journal_entries`, `landed_cost_vouchers`, `location_corrections`, `location_migrations`, `login_attempts`, `logistics_deliveries`, `makloon_orders`, `makloons`, `master_governance_batches`, `material_reservation_locks`, `material_reservations`, `md_samples`, `md_specs`, `mdq_cuts`, `mfg_boms`, `mfg_work_orders`, `migrations`, `mkt_accounts`, `mkt_campaign_costs`, `mkt_campaigns`, `mkt_posts`, `mkt_templates`, `notifications`, `number_sequences`, `ocr_sample_runs`, `ocr_samples`, `payment_plans`, `payment_terms`, `payment_variance_decisions`, `pdf_templates`, `penalties`, `period_close_locks`, `period_closings`, `period_unlock_requests`, `permission_settings`, `po_variance_tasks`, `price_approvals`, `process_recipes`, `process_stages`, `product_categories`, `product_lines`, `product_templates`, `products`, `purchase_orders`, `purchase_requisitions`, `purchase_returns`, `push_subscriptions`, `putaway_orders`, `repair_orders`, `return_create_locks`, `rfid_cycle_counts`, `rfid_devices`, `rfid_incidents`, `rfid_observations`, `rfid_passages`, `rfid_print_jobs`, `rfid_reads`, `rfid_tags`, `rfid_verify_sessions`, `rfqs`, `rnd_person_divisions`, `rnd_specs`, `roll_label_prints`, `roll_scans`, `sales_incentives`, `sales_invoices`, `sales_orders`, `sales_return_policies`, `sales_returns`, `sales_targets`, `sample_price_master`, `sample_types`, `sessions`, `shipments`, `special_order_reconciliation`, `special_orders`, `store_credit_ledger`, `store_credit_redemptions`, `supplier_contracts`, `supplier_dn_profiles`, `supplier_items`, `supplier_price_lists`, `supplier_roll_claims`, `suppliers`, `sys_digest_claims`, `sys_scheduler_runs`, `sys_wa_outbox`, `system_settings`, `tax_invoices`, `tax_invoices_in`, `tax_pph_records`, `turn_marks`, `uoms`, `user_onboarding`, `users`, `vendor_bills`, `warehouse_sites`, `warehouse_transfers`, `warehouses`, `wms_tasks`

## Frontend

| Fitur (`src/features/`) | Berkas | Baris |
|---|---:|---:|
| `__tests__` | 59 | 7440 |
| `admin` | 34 | 6574 |
| `approvals` | 9 | 1699 |
| `catalog` | 21 | 1203 |
| `costing` | 1 | 150 |
| `crm` | 17 | 3568 |
| `design` | 8 | 1580 |
| `designer` | 8 | 1624 |
| `desks` | 2 | 220 |
| `documents` | 18 | 2640 |
| `export` | 9 | 700 |
| `finance` | 93 | 20380 |
| `home` | 5 | 1127 |
| `hr` | 33 | 5340 |
| `inspections` | 12 | 2161 |
| `interco_prices` | 4 | 279 |
| `internal_requests` | 3 | 854 |
| `inventory` | 18 | 3985 |
| `logistics` | 15 | 1670 |
| `manager` | 2 | 603 |
| `marketing` | 13 | 1270 |
| `mobile` | 10 | 1290 |
| `notifications` | 1 | 33 |
| `orders` | 23 | 3851 |
| `pdf` | 5 | 901 |
| `pettycash` | 11 | 1565 |
| `pos` | 23 | 2633 |
| `pricing` | 1 | 151 |
| `production` | 3 | 751 |
| `purchasing` | 84 | 17772 |
| `rfid` | 10 | 1706 |
| `rnd` | 66 | 7874 |
| `sales` | 97 | 15778 |
| `sales_admin` | 11 | 1862 |
| `samples` | 8 | 764 |
| `settings` | 49 | 9077 |
| `tanya` | 25 | 1592 |
| `transfers` | 1 | 20 |
| `wms` | 92 | 12324 |

**Komponen bersama (`src/components/*.jsx`, 98):** `ArchivedReadOnlyBanner.jsx`, `AskKnButton.jsx`, `AttachmentThumb.jsx`, `AuditHistoryPanel.jsx`, `BaseFabricPicker.jsx`, `CartPanel.jsx`, `CartPanelBanners.jsx`, `Collapse.jsx`, `CommandPalette.jsx`, `ConfirmHost.jsx`, `ConfirmModal.jsx`, `CoreWidgets.jsx`, `CustomerPanel.jsx`, `DecimalInput.jsx`, `DesktopOnlyNotice.jsx`, `DetailDrawer.jsx`, `DetailModal.jsx`, `DetailParts.jsx`, `DetailPopup.jsx`, `DualName.jsx`, `EntityBadge.jsx`, `EntityRequiredNotice.jsx`, `EntitySwitcher.jsx`, `ErrorBoundary.jsx`, `ErrorNotice.jsx`, `FilterChips.jsx`, `FormModal.jsx`, `FormSection.jsx`, `FulfillmentInfo.jsx`, `GroupEntityBadge.jsx`, `GuidedActionPanel.jsx`, `GuidedTour.jsx`, `HubTabs.jsx`, `KNDatePicker.jsx`, `KNDateTimePicker.jsx`, `KNMonthPicker.jsx`, `KNPager.jsx`, `KNSelect.jsx`, `KNTimePicker.jsx`, `LabelPrinterModal.jsx`, `LineFilter.jsx`, `LinkCard.jsx`, `ListControls.jsx`, `ListPageParts.jsx`, `LoadingLine.jsx`, `LocationFields.jsx`, `LoginScreen.jsx`, `MakloonSelect.jsx`, `MediaLightbox.jsx`, `MixedLotConfirmModal.jsx`, `MoneyInput.jsx`, `NotificationCenter.jsx`, `OkNotice.jsx`, `OnboardingPanel.jsx`, `OpeningCostBanner.jsx`, `PageTabs.jsx`, `PagedRows.jsx`, `PaginationBar.jsx`, `PantoneFinder.jsx`, `PaymentBadge.jsx`, `PeggingModal.jsx`, `PeriodUnlockBanner.jsx`, `PeriodUnlockCard.jsx`, `PrinterStatusWidget.jsx`, `ProductCard.jsx`, `ProductColorChip.jsx`, `ProductColorTriad.jsx`, `ProductDetail.jsx`, `ProductGallery.jsx`, `ProductQuickView.jsx`, `ProductSelect.jsx`, `QcRequestPicker.jsx`, `QcStatusBadge.jsx`, `QtyDual.jsx`, `ResponsiveTable.jsx`, `ReturnPolicyEditor.jsx`, `ReturnTimeline.jsx`, `RevisionProgress.jsx`, `RollCheckChips.jsx`, `RollLabelActions.jsx`, `RollPicker.jsx`, `RollReconcileSheet.jsx`, `SalesStockSummary.jsx`, `SampleKindChooser.jsx`, `ScopeReadOnlyBanner.jsx`, `SeeAllModal.jsx`, `SiteSelect.jsx`, `SoStatusBadges.jsx`, `StarRating.jsx`, `StoreCreditBadge.jsx`, `TableFilter.jsx`, `TourMenu.jsx`, `UomConvertHint.jsx`, `UomInputConvert.jsx`, `VariantAxisPicker.jsx`, `WaitingBoardsStrip.jsx`, `WaitingQueueBoard.jsx`, `WarehouseModeBadge.jsx`

**Hooks (`src/hooks/`):** `use-toast.js`, `useAppActions.js`, `useAppNavigation.js`, `useBlobUrl.js`, `useCaseDeepLink.js`, `useCatalogMasters.js`, `useConfigDeepLink.js`, `useDeepLinks.js`, `useDomainEnums.js`, `useEffectivePrices.js`, `useIntentKey.js`, `useIsMobile.js`, `useListSearch.jsx`, `useLogisticsDeepLink.js`, `usePagedList.js`, `usePagedRows.js`, `useProcessTypes.js`, `useReceivingMode.js`, `useReceivingUom.js`, `useRndDeepLink.js`, `useSessionSync.js`, `useTraceDeepLink.js`, `useUomConversions.js`, `useViewDeepLink.js`, `useViewPreset.js`

**Utils (`src/utils/`):** `actorLabel.js`, `apiError.js`, `cleanText.js`, `csvExport.js`, `decimalInput.js`, `docLink.js`, `docPrint.js`, `docStatus.js`, `entityLabel.js`, `escapeLayers.js`, `feedback.js`, `formatters.js`, `fulfillment.js`, `lifecycle.js`, `offlineQueue.js`, `overlayDismiss.js`, `overlayStack.js`, `pricing.js`, `productImage.js`, `productSearch.js`, `qtyByUnit.js`, `qtyDualCsv.js`, `rollLabels.js`, `sampleOrder.js`, `sirenAlarm.js`, `soStatus.js`, `sourcingVisibility.js`, `taxBreakdown.js`, `text.js`, `uom.js`, `uomCatalog.js`, `variants.js`, `viewAlias.js`, `writeScope.js`

## Berkas melewati batas ukuran

13 berkas.

| Berkas | Baris | Batas |
|---|---:|---:|
| `backend\routers\special_orders.py` | 1492 | 800 |
| `backend\routers\sales_returns.py` | 1289 | 800 |
| `backend\routers\rnd.py` | 1062 | 800 |
| `backend\routers\purchase_orders.py` | 1002 | 800 |
| `backend\routers\sales_orders_extra.py` | 952 | 800 |
| `frontend\src\features\orders\OrderDetailPanel.jsx` | 702 | 500 |
| `frontend\src\features\purchasing\PurchaseReturns.jsx` | 628 | 500 |
| `frontend\src\features\wms\OutboundScanInterface.jsx` | 603 | 500 |
| `frontend\src\features\internal_requests\InternalRequestsView.jsx` | 561 | 500 |
| `frontend\src\features\wms\InventoryStockView.jsx` | 559 | 500 |
| `frontend\src\features\purchasing\makloon\MakloonWizard.jsx` | 542 | 500 |
| `frontend\src\features\pos\CheckoutDrawer.jsx` | 535 | 500 |
| `frontend\src\features\settings\entities\RoleRealityPanel.jsx` | 511 | 500 |

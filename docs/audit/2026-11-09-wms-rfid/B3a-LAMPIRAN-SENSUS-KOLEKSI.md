# B3a — Lampiran: Sensus koleksi (kode HEAD 5f1e36e × DB kn_test_trial × ENTITY_REGISTRY.md)

Dibangkitkan: `python scripts/audit/b3a_collection_census.py --calls calls.json --db db_collections.tsv --registry ENTITY_REGISTRY.md --root .` (calls.json dari `scripts/audit/b3a_db_writers.py --json`).

* Kolom **app baca/tulis** = jumlah panggilan Mongo di kode aplikasi (backend non-uji, non-seed); **script** = seed/migrasi/fix; **test** = uji/POC.
* **dok DB** = `estimatedDocumentCount` 9 Nov 2026 ±05:00 WIB; `—` = koleksi tidak ada di DB.
* Kelas: `TAK_TERDAFTAR` (dipakai app & ada di DB, tak disebut registry) · `TAK_ADA_DI_DB` (dipakai kode, belum pernah tercipta di DB uji) · `KOSONG` (0 dok) · `AKSES_DINAMIS` (dibaca lewat nama variabel/helper) · `HANYA_TULIS`/`HANYA_BACA` (sisi app; `HANYA_TULIS` bisa palsu bila dibaca lewat helper dinamis, mis. `fact_stock_daily` dibaca `services/analytics_engine.py:348` lewat `_group("fact_stock_daily")`).
* Registry dibaca heuristik (judul `###`, baris `Collection:`, sel tabel ber-backtick, atau sebutan `` `nama` `` di mana pun) — sengaja longgar: koleksi yang hanya disebut sambil lalu dihitung TERDAFTAR.

| koleksi | app baca | app tulis | script | test | dok DB | registry | kelas |
|---|---:|---:|---:|---:|---:|:---:|---|
| `_poc_hr_attendance` | 0 | 0 | 0 | 4 | · | **tidak** |  |
| `_poc_number_series` | 0 | 0 | 0 | 14 | · | **tidak** |  |
| `ai_action_proposals` | 1 | 5 | 0 | 0 | 3 | **tidak** | TAK_TERDAFTAR |
| `ai_chat_sessions` | 3 | 4 | 0 | 0 | 12 | **tidak** | TAK_TERDAFTAR |
| `ai_fact_state` | 4 | 5 | 0 | 1 | 1 | **tidak** | TAK_TERDAFTAR |
| `ai_feedback` | 0 | 1 | 0 | 0 | 1 | **tidak** | TAK_TERDAFTAR HANYA_TULIS |
| `ai_insights` | 1 | 1 | 0 | 0 | 37 | **tidak** | TAK_TERDAFTAR |
| `ai_result_cache` | 1 | 1 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `ai_results` | 2 | 1 | 2 | 0 | 144 | **tidak** | TAK_TERDAFTAR |
| `ai_schedule_runs` | 2 | 2 | 4 | 0 | · | **tidak** | TAK_ADA_DI_DB |
| `ai_schedules` | 4 | 5 | 4 | 0 | · | **tidak** | TAK_ADA_DI_DB |
| `ai_usage_log` | 6 | 8 | 8 | 14 | 3 | **tidak** | TAK_TERDAFTAR |
| `ai_user_templates` | 2 | 2 | 0 | 0 | · | **tidak** | TAK_ADA_DI_DB |
| `amendment_reasons` | 13 | 2 | 3 | 1 | 33 | **tidak** | TAK_TERDAFTAR |
| `approval_matrix_log` | 1 | 1 | 0 | 0 | 1031 | ya |  |
| `approval_records` | 0 | 0 | 2 | 0 | · | **tidak** |  |
| `approval_requests` | 0 | 0 | 0 | 2 | · | ya |  |
| `approval_rules` | 6 | 6 | 0 | 0 | 7 | ya |  |
| `ar_receipt_failures` | 0 | 1 | 0 | 0 | · | **tidak** | TAK_ADA_DI_DB HANYA_TULIS |
| `ar_receipts` | 28 | 15 | 33 | 48 | 25 | ya |  |
| `audit_logs` | 6 | 1 | 79 | 97 | 13425 | ya |  |
| `audit_rows` | 0 | 0 | 4 | 0 | · | **tidak** |  |
| `bank_accounts` | 18 | 5 | 32 | 11 | 11 | ya |  |
| `bank_match_rules` | 6 | 3 | 0 | 2 | · | ya | TAK_ADA_DI_DB |
| `bank_statement_formats` | 5 | 6 | 2 | 1 | 7 | ya |  |
| `bank_statement_lines` | 23 | 18 | 16 | 27 | · | ya | TAK_ADA_DI_DB |
| `bin_locks` | 0 | 3 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG HANYA_TULIS |
| `budgets` | 6 | 4 | 7 | 3 | 0 | ya | KOSONG |
| `business_entities` | 94 | 7 | 86 | 17 | 6 | ya |  |
| `cash_advance_settlements` | 6 | 6 | 6 | 4 | 0 | ya | KOSONG |
| `cash_advances` | 2 | 10 | 2 | 0 | · | ya | TAK_ADA_DI_DB |
| `cash_transactions` | 39 | 42 | 128 | 101 | 43 | ya |  |
| `client_dataset_imports` | 4 | 8 | 0 | 0 | · | **tidak** | TAK_ADA_DI_DB |
| `collection_followups` | 2 | 2 | 0 | 2 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `color_library` | 25 | 9 | 14 | 4 | 110 | ya |  |
| `complaint_reasons` | 0 | 0 | 2 | 0 | 7 | ya | AKSES_DINAMIS(4_berkas) |
| `config_values` | 3 | 4 | 8 | 20 | 189 | **tidak** | TAK_TERDAFTAR |
| `contra_bons` | 5 | 2 | 4 | 22 | 0 | ya | KOSONG |
| `counters` | 0 | 0 | 2 | 0 | · | **tidak** |  |
| `credit_notes` | 18 | 18 | 13 | 10 | 55 | ya |  |
| `credit_overrides` | 4 | 5 | 2 | 6 | 1 | **tidak** | TAK_TERDAFTAR |
| `crm_interactions` | 2 | 3 | 0 | 2 | · | **tidak** | TAK_ADA_DI_DB |
| `crm_leads` | 8 | 4 | 1 | 5 | · | **tidak** | TAK_ADA_DI_DB |
| `custom_roles` | 1 | 3 | 1 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `customer_feedbacks` | 4 | 2 | 0 | 0 | 9 | **tidak** | TAK_TERDAFTAR |
| `customer_grade_rules` | 2 | 1 | 1 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `customer_prices` | 11 | 6 | 14 | 1 | · | ya | TAK_ADA_DI_DB |
| `customers` | 75 | 13 | 131 | 89 | 34 | ya |  |
| `cycle_count_sessions` | 16 | 34 | 32 | 7 | 0 | ya | KOSONG |
| `data_hygiene_log` | 6 | 3 | 0 | 0 | 51 | **tidak** | TAK_TERDAFTAR |
| `data_hygiene_runs` | 1 | 1 | 0 | 0 | 16 | **tidak** | TAK_TERDAFTAR |
| `debit_notes` | 0 | 0 | 0 | 1 | · | **tidak** |  |
| `design_categories` | 4 | 4 | 0 | 0 | 11 | **tidak** | TAK_TERDAFTAR |
| `design_gallery` | 60 | 33 | 39 | 13 | 16 | ya |  |
| `design_requests` | 13 | 6 | 6 | 6 | 9 | ya |  |
| `design_tags` | 1 | 1 | 0 | 3 | 11 | **tidak** | TAK_TERDAFTAR |
| `doc_amendments` | 13 | 7 | 3 | 1 | 25 | **tidak** | TAK_TERDAFTAR |
| `doc_refs` | 0 | 0 | 10 | 2 | · | ya |  |
| `document_branding` | 2 | 1 | 0 | 0 | 1 | **tidak** | TAK_TERDAFTAR |
| `document_deliveries` | 2 | 1 | 0 | 0 | · | ya | TAK_ADA_DI_DB |
| `document_relations` | 0 | 0 | 0 | 3 | · | **tidak** |  |
| `document_signatures` | 5 | 1 | 9 | 4 | 0 | ya | KOSONG |
| `document_templates` | 2 | 4 | 2 | 1 | 3 | ya |  |
| `entities` | 1 | 0 | 0 | 2 | · | **tidak** | TAK_ADA_DI_DB HANYA_BACA |
| `entity_prices` | 12 | 7 | 7 | 8 | 325 | ya |  |
| `esign_requests` | 2 | 5 | 6 | 3 | 0 | ya | KOSONG |
| `expense_categories` | 4 | 2 | 3 | 1 | 8 | ya |  |
| `export_jobs` | 3 | 4 | 0 | 0 | 44 | **tidak** | TAK_TERDAFTAR |
| `export_templates` | 5 | 8 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `fact_ar_daily` | 1 | 2 | 0 | 0 | 54 | **tidak** | TAK_TERDAFTAR |
| `fact_sales_lines` | 6 | 3 | 6 | 6 | 576 | **tidak** | TAK_TERDAFTAR |
| `fact_stock_daily` | 0 | 2 | 3 | 1 | 2054 | **tidak** | TAK_TERDAFTAR HANYA_TULIS |
| `fin_budget_rules` | 1 | 1 | 5 | 0 | · | ya | TAK_ADA_DI_DB |
| `fin_depreciation_entries` | 3 | 1 | 5 | 9 | · | ya | TAK_ADA_DI_DB |
| `fin_fixed_assets` | 11 | 8 | 7 | 9 | · | ya | TAK_ADA_DI_DB |
| `finance_cases` | 3 | 2 | 6 | 13 | 8 | ya |  |
| `fleet_vehicles` | 10 | 5 | 1 | 2 | · | **tidak** | TAK_ADA_DI_DB |
| `generated_documents` | 3 | 1 | 2 | 1 | · | ya | TAK_ADA_DI_DB |
| `gl_account_mapping_history` | 2 | 1 | 0 | 0 | 8 | **tidak** | TAK_TERDAFTAR |
| `gl_account_mappings` | 2 | 2 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `gl_accounts` | 22 | 5 | 41 | 2 | 77 | ya |  |
| `gl_postings` | 0 | 0 | 0 | 0 | 0 | **tidak** | AKSES_DINAMIS(2_berkas) |
| `goods_receipts` | 17 | 8 | 51 | 6 | 15 | **tidak** | TAK_TERDAFTAR |
| `hr_attendance` | 13 | 7 | 18 | 8 | 24 | ya |  |
| `hr_devices` | 5 | 6 | 0 | 0 | 1 | ya |  |
| `hr_employees` | 48 | 8 | 26 | 12 | 30 | ya |  |
| `hr_field_tracks` | 4 | 2 | 0 | 0 | 6 | ya |  |
| `hr_geofences` | 5 | 4 | 0 | 0 | 6 | ya |  |
| `hr_kpi` | 7 | 3 | 2 | 1 | 6 | ya |  |
| `hr_leave_balances` | 4 | 5 | 2 | 0 | 22 | **tidak** | TAK_TERDAFTAR |
| `hr_leave_requests` | 13 | 5 | 1 | 1 | 2 | **tidak** | TAK_TERDAFTAR |
| `hr_org_units` | 14 | 4 | 0 | 0 | 72 | ya |  |
| `hr_overtime` | 11 | 3 | 7 | 2 | 1 | **tidak** | TAK_TERDAFTAR |
| `hr_payroll_runs` | 19 | 9 | 13 | 26 | 3 | ya |  |
| `hr_payslips` | 7 | 3 | 4 | 6 | 32 | ya |  |
| `hr_shifts` | 8 | 4 | 0 | 2 | 6 | ya |  |
| `hr_visits` | 8 | 3 | 0 | 1 | 2 | ya |  |
| `idempotency_keys` | 1 | 4 | 2 | 6 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `inbound_tasks` | 0 | 0 | 0 | 1 | · | **tidak** |  |
| `incentive_rates` | 5 | 4 | 7 | 2 | 7 | ya |  |
| `initial_registration_lines` | 7 | 7 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `inspection_orders` | 0 | 0 | 0 | 1 | · | ya |  |
| `inspections` | 32 | 8 | 25 | 18 | 113 | ya |  |
| `integration_settings` | 2 | 1 | 0 | 0 | · | **tidak** | TAK_ADA_DI_DB |
| `interco_accounts` | 4 | 3 | 4 | 19 | 6 | ya |  |
| `interco_loans` | 8 | 3 | 2 | 5 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `interco_returns` | 19 | 10 | 4 | 37 | 2 | ya |  |
| `interco_settlements` | 3 | 1 | 2 | 8 | 2 | ya |  |
| `interco_transactions` | 31 | 6 | 11 | 34 | 4 | ya |  |
| `intercompany_eliminations` | 8 | 10 | 15 | 31 | 2 | ya |  |
| `internal_requests` | 5 | 3 | 12 | 4 | 1 | **tidak** | TAK_TERDAFTAR |
| `inventory_balances` | 29 | 7 | 95 | 61 | 393 | ya |  |
| `inventory_lots` | 17 | 10 | 10 | 54 | 462 | ya |  |
| `inventory_movements` | 15 | 64 | 114 | 70 | 85363 | ya |  |
| `inventory_rolls` | 349 | 182 | 652 | 352 | 46700 | ya |  |
| `invoices` | 3 | 1 | 4 | 16 | 1 | ya |  |
| `journal_entries` | 88 | 15 | 243 | 253 | 664 | ya |  |
| `landed_cost_vouchers` | 13 | 6 | 8 | 5 | 0 | ya | KOSONG |
| `location_corrections` | 0 | 1 | 0 | 2 | · | **tidak** | TAK_ADA_DI_DB HANYA_TULIS |
| `location_migrations` | 0 | 1 | 0 | 0 | · | **tidak** | TAK_ADA_DI_DB HANYA_TULIS |
| `login_attempts` | 1 | 3 | 1 | 1 | 5 | **tidak** | TAK_TERDAFTAR |
| `logistics_deliveries` | 13 | 10 | 17 | 3 | 6 | **tidak** | TAK_TERDAFTAR |
| `makloon_orders` | 40 | 17 | 68 | 21 | 56 | ya |  |
| `makloons` | 11 | 3 | 5 | 5 | 8 | ya |  |
| `master_cleanup_batches` | 5 | 4 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `master_governance_batches` | 3 | 4 | 5 | 1 | · | **tidak** | TAK_ADA_DI_DB |
| `material_reservation_locks` | 0 | 4 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG HANYA_TULIS |
| `material_reservations` | 11 | 5 | 25 | 11 | 56 | **tidak** | TAK_TERDAFTAR |
| `md_fabric_types` | 4 | 2 | 0 | 0 | 2 | **tidak** | TAK_TERDAFTAR |
| `md_grades` | 10 | 4 | 0 | 0 | 7 | **tidak** | TAK_TERDAFTAR |
| `md_samples` | 47 | 30 | 91 | 24 | 22 | **tidak** | TAK_TERDAFTAR |
| `md_specs` | 34 | 10 | 26 | 3 | 159 | ya |  |
| `mdq_cuts` | 2 | 4 | 0 | 0 | 16 | **tidak** | TAK_TERDAFTAR |
| `mfg_boms` | 3 | 3 | 3 | 0 | · | ya | TAK_ADA_DI_DB |
| `mfg_work_orders` | 13 | 8 | 45 | 0 | 0 | ya | KOSONG |
| `migrations` | 3 | 3 | 25 | 0 | 17 | **tidak** | TAK_TERDAFTAR |
| `mkt_accounts` | 5 | 2 | 0 | 0 | · | **tidak** | TAK_ADA_DI_DB |
| `mkt_campaign_costs` | 4 | 4 | 0 | 10 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `mkt_campaigns` | 7 | 2 | 0 | 3 | 1 | **tidak** | TAK_TERDAFTAR |
| `mkt_posts` | 20 | 14 | 11 | 8 | 1 | **tidak** | TAK_TERDAFTAR |
| `mkt_templates` | 4 | 3 | 0 | 0 | · | **tidak** | TAK_ADA_DI_DB |
| `notifications` | 19 | 9 | 46 | 167 | 5349 | ya |  |
| `number_sequences` | 5 | 8 | 4 | 14 | 186 | **tidak** | TAK_TERDAFTAR |
| `ocr_sample_runs` | 4 | 3 | 0 | 0 | 0 | ya | KOSONG |
| `ocr_samples` | 5 | 4 | 2 | 0 | 0 | ya | KOSONG |
| `payment_plans` | 3 | 7 | 8 | 3 | · | ya | TAK_ADA_DI_DB |
| `payment_terms` | 5 | 3 | 4 | 5 | 9 | ya |  |
| `payment_variance_decisions` | 7 | 2 | 4 | 11 | 1 | ya |  |
| `pdf_templates` | 6 | 2 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `penalties` | 12 | 7 | 8 | 10 | · | ya | TAK_ADA_DI_DB |
| `period_close_locks` | 0 | 3 | 4 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG HANYA_TULIS |
| `period_closings` | 11 | 6 | 42 | 25 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `period_unlock_requests` | 9 | 5 | 14 | 12 | 1 | **tidak** | TAK_TERDAFTAR |
| `permission_settings` | 10 | 9 | 108 | 19 | 1 | ya |  |
| `po_variance_tasks` | 5 | 7 | 17 | 4 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `poc_gate_selftest` | 0 | 0 | 1 | 0 | · | **tidak** |  |
| `price_approvals` | 11 | 19 | 18 | 7 | 34 | ya |  |
| `process_recipes` | 8 | 3 | 5 | 2 | 0 | ya | KOSONG |
| `process_stages` | 2 | 0 | 9 | 6 | 10 | ya | HANYA_BACA |
| `product_categories` | 7 | 4 | 5 | 8 | 10 | ya |  |
| `product_lines` | 3 | 0 | 11 | 5 | 3 | ya | HANYA_BACA |
| `product_templates` | 40 | 10 | 17 | 19 | 75 | **tidak** | TAK_TERDAFTAR |
| `products` | 283 | 42 | 324 | 144 | 411 | ya |  |
| `purchase_orders` | 103 | 30 | 269 | 112 | 40 | ya |  |
| `purchase_requisitions` | 47 | 14 | 31 | 17 | 21 | ya |  |
| `purchase_returns` | 35 | 20 | 38 | 17 | 12 | ya |  |
| `push_subscriptions` | 4 | 4 | 0 | 0 | · | **tidak** | TAK_ADA_DI_DB |
| `putaway_orders` | 14 | 10 | 9 | 12 | 2 | **tidak** | TAK_TERDAFTAR |
| `registration_area_status` | 1 | 1 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `repair_orders` | 5 | 2 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `return_create_locks` | 0 | 3 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG HANYA_TULIS |
| `return_grade_impairments` | 2 | 1 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `rfid_cycle_counts` | 6 | 2 | 13 | 5 | · | **tidak** | TAK_ADA_DI_DB |
| `rfid_devices` | 24 | 11 | 14 | 11 | 1 | ya |  |
| `rfid_incidents` | 6 | 4 | 64 | 10 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `rfid_observations` | 1 | 2 | 2 | 2 | 2 | **tidak** | TAK_TERDAFTAR |
| `rfid_passages` | 4 | 4 | 0 | 0 | 1 | **tidak** | TAK_TERDAFTAR |
| `rfid_print_jobs` | 7 | 8 | 18 | 7 | 8 | **tidak** | TAK_TERDAFTAR |
| `rfid_reads` | 11 | 4 | 37 | 4 | 1 | ya |  |
| `rfid_tags` | 39 | 18 | 61 | 22 | 41 | ya |  |
| `rfid_v2_bindings` | 3 | 2 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `rfid_v2_claim_corrections` | 1 | 1 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `rfid_v2_configs` | 3 | 1 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `rfid_v2_crossings` | 6 | 2 | 0 | 2 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `rfid_v2_doc_sessions` | 2 | 4 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `rfid_v2_edges` | 0 | 0 | 0 | 0 | 0 | **tidak** | AKSES_DINAMIS(1_berkas) |
| `rfid_v2_event_ids` | 1 | 1 | 0 | 0 | · | **tidak** | TAK_ADA_DI_DB |
| `rfid_v2_events` | 1 | 0 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG HANYA_BACA |
| `rfid_v2_gate_latches` | 2 | 3 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `rfid_v2_gate_txn` | 1 | 3 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `rfid_v2_health` | 1 | 3 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `rfid_v2_overflow` | 2 | 1 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `rfid_v2_passages` | 11 | 9 | 0 | 1 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `rfid_v2_reviews` | 7 | 4 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG |
| `rfid_v2_summaries` | 1 | 0 | 0 | 0 | 0 | **tidak** | TAK_TERDAFTAR KOSONG HANYA_BACA |
| `rfid_verify_sessions` | 18 | 12 | 20 | 11 | 11 | **tidak** | TAK_TERDAFTAR |
| `rfqs` | 3 | 5 | 10 | 20 | 0 | ya | KOSONG |
| `rnd_person_divisions` | 3 | 1 | 1 | 0 | · | ya | TAK_ADA_DI_DB |
| `rnd_specs` | 0 | 0 | 0 | 1 | · | **tidak** |  |
| `roll_cost_history` | 1 | 1 | 2 | 3 | 22 | **tidak** | TAK_TERDAFTAR |
| `roll_label_prints` | 3 | 1 | 0 | 5 | 20 | **tidak** | TAK_TERDAFTAR |
| `roll_scans` | 2 | 2 | 0 | 8 | · | **tidak** | TAK_ADA_DI_DB |
| `sales_incentives` | 4 | 1 | 2 | 0 | · | ya | TAK_ADA_DI_DB |
| `sales_invoices` | 0 | 0 | 1 | 1 | · | **tidak** |  |
| `sales_orders` | 252 | 71 | 372 | 269 | 445 | ya |  |
| `sales_return_policies` | 4 | 3 | 6 | 0 | · | ya | TAK_ADA_DI_DB |
| `sales_returns` | 88 | 51 | 52 | 44 | 91 | ya |  |
| `sales_targets` | 3 | 1 | 7 | 3 | 4 | ya |  |
| `sample_price_master` | 2 | 1 | 0 | 1 | · | **tidak** | TAK_ADA_DI_DB |
| `sample_requests` | 0 | 0 | 0 | 3 | · | **tidak** |  |
| `sample_types` | 0 | 0 | 8 | 1 | 4 | ya | AKSES_DINAMIS(19_berkas) |
| `sessions` | 6 | 8 | 50 | 23 | 23 | ya |  |
| `settings` | 0 | 0 | 0 | 4 | · | **tidak** |  |
| `shipments` | 33 | 12 | 47 | 45 | 75 | ya |  |
| `special_order_reconciliation` | 0 | 1 | 3 | 0 | · | **tidak** | TAK_ADA_DI_DB HANYA_TULIS |
| `special_orders` | 60 | 60 | 56 | 80 | 28 | ya |  |
| `stock_movements` | 0 | 0 | 2 | 3 | · | **tidak** |  |
| `store_credit_ledger` | 13 | 4 | 1 | 3 | 92 | **tidak** | TAK_TERDAFTAR |
| `store_credit_redemptions` | 3 | 2 | 2 | 0 | 49 | **tidak** | TAK_TERDAFTAR |
| `supplier_contracts` | 16 | 5 | 17 | 11 | 734 | ya |  |
| `supplier_dn_profiles` | 8 | 4 | 0 | 2 | 2 | ya |  |
| `supplier_items` | 31 | 13 | 21 | 20 | 8 | ya |  |
| `supplier_price_lists` | 6 | 5 | 4 | 4 | · | ya | TAK_ADA_DI_DB |
| `supplier_roll_claims` | 0 | 3 | 0 | 0 | · | **tidak** | TAK_ADA_DI_DB HANYA_TULIS |
| `suppliers` | 68 | 12 | 89 | 28 | 92 | ya |  |
| `sys_digest_claims` | 0 | 2 | 0 | 0 | · | **tidak** | TAK_ADA_DI_DB HANYA_TULIS |
| `sys_scheduler_lock` | 0 | 0 | 2 | 0 | · | **tidak** |  |
| `sys_scheduler_runs` | 4 | 1 | 1 | 1 | 10855 | ya |  |
| `sys_wa_outbox` | 8 | 4 | 3 | 12 | 0 | ya | KOSONG |
| `system_settings` | 22 | 28 | 30 | 26 | 14 | ya |  |
| `tax_invoices` | 18 | 10 | 14 | 18 | 0 | ya | KOSONG |
| `tax_invoices_in` | 8 | 5 | 1 | 20 | 0 | ya | KOSONG |
| `tax_pph_records` | 3 | 2 | 0 | 0 | · | ya | TAK_ADA_DI_DB |
| `turn_marks` | 0 | 1 | 0 | 3 | 1115 | **tidak** | TAK_TERDAFTAR HANYA_TULIS |
| `uom_conversion_rules` | 7 | 4 | 1 | 0 | 14 | ya |  |
| `uoms` | 9 | 6 | 23 | 4 | 9 | ya |  |
| `user_onboarding` | 2 | 2 | 0 | 0 | · | ya | TAK_ADA_DI_DB |
| `user_sessions` | 0 | 0 | 4 | 1 | · | **tidak** |  |
| `users` | 82 | 13 | 232 | 31 | 22 | ya |  |
| `vehicle_usage_logs` | 5 | 3 | 0 | 0 | · | ya | TAK_ADA_DI_DB |
| `vehicles` | 5 | 4 | 0 | 0 | · | ya | TAK_ADA_DI_DB |
| `vendor_bills` | 47 | 28 | 63 | 54 | 10 | ya |  |
| `wa_auto_rules` | 3 | 3 | 0 | 0 | · | **tidak** | TAK_ADA_DI_DB |
| `warehouse_sites` | 15 | 4 | 4 | 1 | 6 | **tidak** | TAK_TERDAFTAR |
| `warehouse_transfers` | 22 | 20 | 20 | 40 | 17 | ya |  |
| `warehouses` | 140 | 10 | 156 | 50 | 18 | ya |  |
| `wms_tasks` | 108 | 58 | 208 | 208 | 252 | ya |  |

Ringkasan: {'TAK_TERDAFTAR': 86, 'TAK_ADA_DI_DB': 44, 'KOSONG': 50, 'AKSES_DINAMIS': 4, 'HANYA_DB': 0, 'TANPA_KODE_APP': 0, 'HANYA_TULIS': 13, 'HANYA_BACA': 5, 'NAMA_TERLARANG': 0}
Koleksi DB: 184 · dipakai kode app: 224 · nama di registry (heuristik): 108
Nama di registry tanpa koleksi di DB maupun kode (heuristik, termasuk rencana): amlog_, customer_pricelist, esig_, esign_service, hkpi_, owner_entity_id, wadlv_
Pasangan nama mirip: design_requests~esign_requests, material_reservation_locks~material_reservations, rfid_passages~rfid_v2_passages, rfid_v2_event_ids~rfid_v2_events, tax_invoices~tax_invoices_in

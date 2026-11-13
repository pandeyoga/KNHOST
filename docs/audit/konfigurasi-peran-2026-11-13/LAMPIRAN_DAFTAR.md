# Lampiran — daftar hasil inventaris dan uji jalan (13 Nov 2026, `dca195b`)

Dihasilkan skrip di folder `bukti/`. Daftar ini bahan kerja untuk unit `PR-T*` dan `KF-T*`; jalankan ulang skripnya untuk memperbarui.

## A. Endpoint yang dijaga nama peran saja (38)

| Metode | Jalur | Berkas:baris | Peran yang ditulis |
|---|---|---|---|
| POST | `/api/customers/{customer_id}/reassign` | `backend/routers/crm.py:71` | manager |
| POST | `/api/credit-overrides/{override_id}/decision` | `backend/routers/crm.py:141` | manager |
| GET | `/api/sales/leaderboard` | `backend/routers/crm.py:267` | manager |
| GET | `/api/sales/incentive/gl-status` | `backend/routers/crm.py:309` | manager |
| POST | `/api/sales/incentive/post-gl` | `backend/routers/crm.py:321` | manager |
| POST | `/api/sales-targets` | `backend/routers/crm.py:369` | manager |
| POST | `/api/sales-incentives` | `backend/routers/crm.py:424` | manager |
| GET | `/api/data-hygiene/log` | `backend/routers/data_hygiene.py:20` | (lewat pembantu) |
| POST | `/api/data-hygiene/run` | `backend/routers/data_hygiene.py:45` | admin |
| POST | `/api/data-hygiene/log/{log_id}/revert` | `backend/routers/data_hygiene.py:53` | admin |
| POST | `/api/data-hygiene/{collection}/{doc_id}/unlock` | `backend/routers/data_hygiene.py:61` | admin |
| GET | `/api/turn-notifications/map` | `backend/routers/data_hygiene.py:69` | (lewat pembantu) |
| GET | `/api/data-hygiene/unverified-locations` | `backend/routers/data_hygiene.py:75` | (lewat pembantu) |
| POST | `/api/data-hygiene/location/{collection}/{doc_id}` | `backend/routers/data_hygiene.py:81` | (lewat pembantu) |
| GET | `/api/incentive-rates` | `backend/routers/incentive_rates.py:44` | manager |
| PATCH | `/api/incentive-rates/{rate_id}` | `backend/routers/incentive_rates.py:78` | manager |
| DELETE | `/api/incentive-rates/{rate_id}` | `backend/routers/incentive_rates.py:93` | manager |
| POST | `/api/rfid/v2/ops/health/check` | `backend/routers/rfid_v2_ops.py:164` | admin |
| GET | `/api/home/admin` | `backend/routers/home.py:57` | manager |
| GET | `/api/home/manager` | `backend/routers/home.py:65` | manager |
| DELETE | `/api/rfid/devices/{device_id}` | `backend/routers/rfid.py:436` | admin |
| POST | `/api/rfid/devices/seed-defaults` | `backend/routers/rfid.py:444` | admin |
| POST | `/api/rfid/devices/{device_id}/api-key` | `backend/routers/rfid.py:660` | admin |
| GET | `/api/costing/wac` | `backend/routers/costing.py:17` | manager |
| GET | `/api/costing/wac/{product_id}` | `backend/routers/costing.py:24` | manager |
| POST | `/api/handheld/devices/{device_id}/rotate-key` | `backend/routers/handheld.py:316` | admin |
| POST | `/api/handheld/devices/{device_id}/revoke` | `backend/routers/handheld.py:324` | admin, warehouse_admin |
| POST | `/api/handheld/devices/{device_id}/enable` | `backend/routers/handheld.py:332` | admin |
| PUT | `/api/handheld/devices/{device_id}/profile` | `backend/routers/handheld.py:340` | admin |
| GET | `/api/saga-locks` | `backend/routers/saga_locks.py:23` | admin |
| GET | `/api/saga-locks/{collection}/{doc_id}/inspect` | `backend/routers/saga_locks.py:80` | admin |
| POST | `/api/saga-locks/{collection}/{doc_id}/release` | `backend/routers/saga_locks.py:91` | admin |
| POST | `/api/notifications/generate` | `backend/routers/notifications.py:110` | manager |
| GET | `/api/ai/facts/status` | `backend/routers/ai_analytics.py:65` | admin, manager |
| POST | `/api/ai/facts/rebuild` | `backend/routers/ai_analytics.py:72` | admin |
| GET | `/api/ai/snapshots/status` | `backend/routers/ai_analytics.py:390` | admin, manager |
| POST | `/api/ai/snapshots/run` | `backend/routers/ai_analytics.py:397` | admin |
| GET | `/api/ai/usage` | `backend/routers/ai_analytics.py:406` | admin, manager |

## B. Endpoint tulis yang hanya butuh login (41)

| Metode | Jalur | Berkas:baris |
|---|---|---|
| POST | `/api/hr/leave-requests/me` | `backend/routers/hr_leave.py:50` |
| POST | `/api/hr/overtime/me` | `backend/routers/hr_leave.py:205` |
| POST | `/api/landed-costs/{voucher_id}/approve` | `backend/routers/landed_cost.py:238` |
| POST | `/api/landed-costs/{voucher_id}/reject` | `backend/routers/landed_cost.py:291` |
| POST | `/api/purchase-orders/{po_id}/approve` | `backend/routers/purchase_orders.py:798` |
| POST | `/api/purchase-orders/{po_id}/reject` | `backend/routers/purchase_orders.py:920` |
| POST | `/api/special-orders/{order_id}/fulfillment/{item_key}/route` | `backend/routers/special_orders.py:750` |
| POST | `/api/special-orders/{order_id}/fulfillment/{item_key}/realize` | `backend/routers/special_orders.py:765` |
| POST | `/api/config/values/reset` | `backend/routers/config.py:299` |
| POST | `/api/config/values/clear` | `backend/routers/config.py:322` |
| POST | `/api/onboarding/{task_id}/complete` | `backend/routers/onboarding.py:66` |
| POST | `/api/onboarding/reset` | `backend/routers/onboarding.py:81` |
| POST | `/api/hr/field-tracks` | `backend/routers/hr_tracking.py:85` |
| POST | `/api/hr/visits/check-in` | `backend/routers/hr_tracking.py:197` |
| POST | `/api/hr/visits/{visit_id}/check-out` | `backend/routers/hr_tracking.py:226` |
| PUT | `/api/stock/my-site` | `backend/routers/stock_figures.py:76` |
| POST | `/api/ai/actions/{pid}/confirm` | `backend/routers/ai_assist.py:20` |
| POST | `/api/ai/actions/{pid}/dismiss` | `backend/routers/ai_assist.py:25` |
| POST | `/api/ai/insights/scan` | `backend/routers/ai_assist.py:38` |
| POST | `/api/push/subscribe` | `backend/routers/push.py:45` |
| POST | `/api/push/unsubscribe` | `backend/routers/push.py:62` |
| POST | `/api/push/test` | `backend/routers/push.py:76` |
| POST | `/api/hr/attendance/clock-in` | `backend/routers/hr_attendance.py:329` |
| POST | `/api/hr/attendance/clock-out` | `backend/routers/hr_attendance.py:371` |
| POST | `/api/vendor-bills/{bill_id}/approve` | `backend/routers/vendor_bills.py:443` |
| POST | `/api/vendor-bills/{bill_id}/reject` | `backend/routers/vendor_bills.py:470` |
| POST | `/api/enums/stage-transitions/validate` | `backend/routers/enums.py:94` |
| POST | `/api/enums/products/validate` | `backend/routers/enums.py:105` |
| POST | `/api/wilayah/validate` | `backend/routers/wilayah.py:53` |
| POST | `/api/notifications/read-all` | `backend/routers/notifications.py:92` |
| POST | `/api/notifications/{notification_id}/read` | `backend/routers/notifications.py:98` |
| POST | `/api/ai/templates/{template_id}/run` | `backend/routers/ai_analytics.py:95` |
| POST | `/api/ai/tools/{tool}` | `backend/routers/ai_analytics.py:105` |
| POST | `/api/ai/chat` | `backend/routers/ai_analytics.py:115` |
| DELETE | `/api/ai/sessions/{session_id}` | `backend/routers/ai_analytics.py:151` |
| POST | `/api/ai/feedback` | `backend/routers/ai_analytics.py:170` |
| POST | `/api/ai/narrative` | `backend/routers/ai_analytics.py:262` |
| POST | `/api/ai/my-templates` | `backend/routers/ai_analytics.py:285` |
| DELETE | `/api/ai/my-templates/{template_id}` | `backend/routers/ai_analytics.py:300` |
| DELETE | `/api/ai/schedules/{schedule_id}` | `backend/routers/ai_analytics.py:355` |
| POST | `/api/ai/schedules/{schedule_id}/run` | `backend/routers/ai_analytics.py:363` |

## C. Endpoint baca yang hanya butuh login (66)

| Jalur | Berkas:baris |
|---|---|
| `/api/hr/kpi/me` | `backend/routers/hr_kpi.py:52` |
| `/api/hr/leave-requests/me` | `backend/routers/hr_leave.py:44` |
| `/api/hr/overtime/me` | `backend/routers/hr_leave.py:199` |
| `/api/sales-users` | `backend/routers/crm.py:31` |
| `/api/sales-targets` | `backend/routers/crm.py:351` |
| `/api/sales-incentives` | `backend/routers/crm.py:407` |
| `/api/master/fabric-types` | `backend/routers/fabric_type_master.py:21` |
| `/api/documents/resolve` | `backend/routers/documents.py:385` |
| `/api/purchase-orders/resolve-sourcing` | `backend/routers/purchase_orders.py:298` |
| `/api/roles` | `backend/routers/auth.py:149` |
| `/api/auth/context` | `backend/routers/auth.py:176` |
| `/api/config/registry` | `backend/routers/config.py:160` |
| `/api/config/effective` | `backend/routers/config.py:184` |
| `/api/config/history` | `backend/routers/config.py:351` |
| `/api/config/simulators` | `backend/routers/config.py:402` |
| `/api/home/sales` | `backend/routers/home.py:47` |
| `/api/home/warehouse` | `backend/routers/home.py:81` |
| `/api/home/finance` | `backend/routers/home.py:101` |
| `/api/settings` | `backend/routers/settings.py:26` |
| `/api/settings/effective` | `backend/routers/settings.py:32` |
| `/api/settings/compute-tax` | `backend/routers/settings.py:95` |
| `/api/settings/evaluate-approval` | `backend/routers/settings.py:102` |
| `/api/payment-terms` | `backend/routers/settings.py:112` |
| `/api/onboarding` | `backend/routers/onboarding.py:44` |
| `/api/hr/visits/me` | `backend/routers/hr_tracking.py:150` |
| `/api/hr/visits/mine` | `backend/routers/hr_tracking.py:163` |
| `/api/stock/my-site` | `backend/routers/stock_figures.py:67` |
| `/api/hr/payslips/me` | `backend/routers/hr_payroll.py:223` |
| `/api/ai/actions/{pid}` | `backend/routers/ai_assist.py:15` |
| `/api/ai/insights` | `backend/routers/ai_assist.py:30` |
| `/api/dashboard` | `backend/routers/dashboard.py:42` |
| `/api/hr/employees/me` | `backend/routers/hr.py:236` |
| `/api/entities` | `backend/routers/entities.py:35` |
| `/api/entities/count` | `backend/routers/entities.py:84` |
| `/api/entities/{entity_id}` | `backend/routers/entities.py:99` |
| `/api/entities/{entity_id}/readiness` | `backend/routers/entities.py:110` |
| `/api/finance/period-unlocks/active` | `backend/routers/period_unlocks.py:51` |
| `/api/push/public-key` | `backend/routers/push.py:38` |
| `/api/push/status` | `backend/routers/push.py:69` |
| `/api/hr/attendance/me` | `backend/routers/hr_attendance.py:311` |
| `/api/enums` | `backend/routers/enums.py:73` |
| `/api/enums/stage-transitions` | `backend/routers/enums.py:83` |
| `/api/enums/{name}` | `backend/routers/enums.py:112` |
| `/api/wilayah/countries` | `backend/routers/wilayah.py:11` |
| `/api/wilayah/provinces` | `backend/routers/wilayah.py:17` |
| `/api/wilayah/regencies` | `backend/routers/wilayah.py:23` |
| `/api/wilayah/districts` | `backend/routers/wilayah.py:29` |
| `/api/wilayah/villages` | `backend/routers/wilayah.py:35` |
| `/api/wilayah/postal-code/{code}` | `backend/routers/wilayah.py:41` |
| `/api/wilayah/search` | `backend/routers/wilayah.py:47` |
| `/api/notifications` | `backend/routers/notifications.py:59` |
| `/api/notifications/unread-count` | `backend/routers/notifications.py:85` |
| `/api/rnd/reports/my-kpi` | `backend/routers/rnd.py:913` |
| `/api/ai/catalog` | `backend/routers/ai_analytics.py:37` |
| `/api/ai/results/{result_id}` | `backend/routers/ai_analytics.py:56` |
| `/api/ai/status` | `backend/routers/ai_analytics.py:81` |
| `/api/ai/templates` | `backend/routers/ai_analytics.py:87` |
| `/api/ai/sessions` | `backend/routers/ai_analytics.py:137` |
| `/api/ai/sessions/{session_id}` | `backend/routers/ai_analytics.py:160` |
| `/api/ai/results/{result_id}/export.xlsx` | `backend/routers/ai_analytics.py:224` |
| `/api/ai/my-templates` | `backend/routers/ai_analytics.py:279` |
| `/api/ai/schedules` | `backend/routers/ai_analytics.py:316` |
| `/api/ai/schedule-runs` | `backend/routers/ai_analytics.py:370` |
| `/api/ai/schedule-runs/{run_id}` | `backend/routers/ai_analytics.py:378` |
| `/api/ai/usage/daily` | `backend/routers/ai_analytics.py:424` |
| `/api/desks/me` | `backend/routers/work_desks.py:255` |

## D. Endpoint tanpa gerbang sesi (21) — perangkat, login, verifikasi publik

| Metode | Jalur | Berkas:baris |
|---|---|---|
| GET | `/api/` | `backend/server.py:332` |
| GET | `/rfid/printer-agent/config` | `backend/routers/rfid_printers.py:76` |
| POST | `/rfid/printer-agent/telemetry` | `backend/routers/rfid_printers.py:82` |
| POST | `/rfid/device-jobs/claim` | `backend/routers/rfid_printers.py:88` |
| GET | `/rfid/device-jobs/{job_id}/attempts/{attempt_id}` | `backend/routers/rfid_printers.py:96` |
| POST | `/rfid/device-jobs/{job_id}/attempts/{attempt_id}/renew` | `backend/routers/rfid_printers.py:102` |
| POST | `/rfid/device-jobs/{job_id}/attempts/{attempt_id}/start` | `backend/routers/rfid_printers.py:110` |
| POST | `/rfid/device-jobs/{job_id}/attempts/{attempt_id}/results` | `backend/routers/rfid_printers.py:117` |
| POST | `/api/auth/login` | `backend/routers/auth.py:94` |
| POST | `/api/auth/logout` | `backend/routers/auth.py:184` |
| GET | `/api/esign/verify/{code}` | `backend/routers/esign.py:89` |
| POST | `/api/rfid/ingest` | `backend/routers/rfid.py:671` |
| POST | `/api/rfid/heartbeat` | `backend/routers/rfid.py:689` |
| GET | `/api/rfid/device-jobs/pending` | `backend/routers/rfid.py:696` |
| POST | `/api/rfid/device-jobs/{job_id}/ack` | `backend/routers/rfid.py:705` |
| GET | `/api/rfid/v2/device/config` | `backend/routers/rfid_v2.py:98` |
| POST | `/api/rfid/v2/events` | `backend/routers/rfid_v2.py:103` |
| POST | `/api/rfid/v2/device/telemetry` | `backend/routers/rfid_v2.py:109` |
| GET | `/api/rfid/v2/device/gate-state` | `backend/routers/rfid_v2.py:115` |
| GET | `/api/handheld/device/config` | `backend/routers/handheld.py:139` |
| POST | `/api/hr/attendance/ingest` | `backend/routers/hr_attendance.py:504` |

## E. Rute baca yang menjawab 200 untuk peran kustom beracuan Manajer dengan semua modul "Tidak ada"

Hanya yang bagi peran Sopir (peran bawaan tersempit) dijawab 403 — artinya terbuka karena peran acuan, bukan karena memang terbuka untuk semua.

| Jalur | Gerbang di kode |
|---|---|
| `/api/ai/catalog` | LOGIN |
| `/api/ai/facts/status` | PERAN |
| `/api/ai/insights` | LOGIN |
| `/api/ai/my-templates` | LOGIN |
| `/api/ai/schedule-runs` | LOGIN |
| `/api/ai/schedules` | LOGIN |
| `/api/ai/sessions` | LOGIN |
| `/api/ai/snapshots/status` | PERAN |
| `/api/ai/status` | LOGIN |
| `/api/ai/templates` | LOGIN |
| `/api/ai/usage` | PERAN |
| `/api/ai/usage/daily` | LOGIN |
| `/api/costing/wac` | PERAN |
| `/api/costing/wac/{product_id}` | PERAN |
| `/api/data-hygiene/log` | PERAN |
| `/api/data-hygiene/preview` | IZIN |
| `/api/data-hygiene/summary` | IZIN |
| `/api/data-hygiene/unverified-locations` | PERAN |
| `/api/home/admin` | PERAN |
| `/api/home/manager` | PERAN |
| `/api/incentive-rates` | PERAN |
| `/api/sales/leaderboard` | PERAN |
| `/api/turn-notifications/map` | PERAN |

## F. Rute baca yang menolak walau peran memegang izin yang disebut endpoint (gerbang nama peran di dalam handler)

| Jalur | Pesan penolakan |
|---|---|
| `/api/internal-requests/{req_id}/sources` | Rincian stok badan usaha lain bukan wewenang peran Anda. Aju |
| `/api/lots` | Registri LOT tidak tersedia untuk peran Anda. |
| `/api/lots/identity-trace` | Registri LOT tidak tersedia untuk peran Anda. |
| `/api/lots/stats` | Registri LOT tidak tersedia untuk peran Anda. |
| `/api/lots/unassigned-rolls` | Registri LOT tidak tersedia untuk peran Anda. |
| `/api/lots/{lot_id}/genealogy` | Registri LOT tidak tersedia untuk peran Anda. |
| `/api/lots/{lot_id}/recall` | Registri LOT tidak tersedia untuk peran Anda. |
| `/api/rnd/divisions` | Hanya admin/manager yang dapat mengelola divisi R&D. |
| `/api/rnd/divisions/members` | Hanya admin/manager yang dapat mengelola divisi R&D. |
| `/api/rnd/reports/designer-kpi` | Laporan penilaian desainer hanya untuk manager & admin. Pera |
| `/api/rnd/reports/designer-kpi/export` | Laporan penilaian desainer hanya untuk manager & admin. Pera |
| `/api/rnd/reports/designer-kpi/trend` | Laporan penilaian desainer hanya untuk manager & admin. Pera |
| `/api/rnd/sla/board` | Laporan penilaian desainer hanya untuk manager & admin. Pera |

## G. Pengaturan yang bisa diubah lewat nama peran `manager` (48)

`lot.enforcement_mode`, `lot.require_supplier_lot`, `lot.require_dye_lot`, `lot.alias_mode`, `lot.alias_unique_scope`, `lot.auto_create_on_receiving`, `lot.status_on_receipt`, `lot.number_format`, `receiving.supplier_dn_mode`, `makloon.variance_tolerance_pct`, `makloon.auto_claim`, `makloon.claim_approval_roles`, `makloon.contract_mode`, `makloon.default_shrinkage_pct`, `makloon.require_output_product`, `makloon.require_yield_reason`, `rnd.lifecycle_enforcement`, `rnd.new_product_default_lifecycle`, `rnd.variant_axes_default`, `rnd.variant_axes_optional`, `rnd.spec_approval_roles`, `rnd.sample_decision_roles`, `rnd.max_rounds`, `rnd.round_sla_days`, `rnd.require_attachment_on_round`, `rnd.require_design_for_proofing`, `rnd.require_stage_chain`, `rnd.labdip_max_colors`, `rnd.design_code_pattern`, `rnd.design_code_seq_digits`, `rnd.design_prefix_motif`, `rnd.design_prefix_pattern`, `rnd.design_prefix_artwork`, `rnd.design_acc_min_score`, `rnd.sla_escalate_admin_days`, `rnd.kpi_weight_on_time`, `rnd.kpi_weight_score`, `rnd.kpi_weight_acc`, `rnd.kpi_weight_design`, `rnd.kpi_penalty_rework`, `rnd.kpi_penalty_overdue`, `rnd.auto_contract_on_decide`, `rnd.sample_material_from_stock`, `approval.matrix_enforcement`, `approval.matrix_scope`, `approval.matrix_effective_from`, `approval.matrix_sod`, `approval.po_custom_direksi_min`

## H. Pengaturan yang nilai cadangannya di kode berbeda dari bawaan registry (12)

| Kunci | Bawaan registry | Cadangan di kode | Berkas:baris |
|---|---|---|---|
| `tax.ppn_rate` | 12.0 | 0 | `backend/services/config_service.py:274` |
| `tax.dpp_nilai_lain` | True | False | `backend/services/config_service.py:279` |
| `ar.denda_rate_pct_per_month` | 2.0 | 0 | `backend/services/ar_aging_service.py:77` |
| `sales.allow_item_discount` | False | True | `backend/services/config_service.py:430` |
| `sales.allow_order_discount` | False | True | `backend/services/config_service.py:431` |
| `commission.discount_threshold` | 10.0 | 0 | `backend/services/sales_force_service.py:259` |
| `commission.discount_factor` | 0.5 | 1.0 | `backend/services/sales_force_service.py:269` |
| `sales.require_so_validation` | False | True | `backend/services/so_approvals.py:227` |
| `inventory.intercompany_transfer_required` | True | False | `backend/services/config_service.py:539` |
| `allocation.lot_selection` | fifo | fefo | `backend/services/roll_service.py:1081` |
| `hr.feature_toggles.pph21` | True | 0 | `backend/services/hr_payroll_service.py:292` |
| `approval.po_custom_direksi_min` | 50000000 | 0.0 | `backend/services/approval_matrix_service.py:217` |


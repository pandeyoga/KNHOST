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

## I. Sapuan endpoint tulis oleh akun tanpa izin (T9)

Sumber: `bukti/t9_tulis_tanpa_izin.py` + `bukti/t9_analyze.py`. 962 rute tulis dipanggil dengan isi permintaan yang dibuat
otomatis dari skema. "Lolos" = jawaban selain 401/403/422, yaitu permintaan melewati gerbang dan sampai ke logika
(kebanyakan lalu dijawab 404 karena dokumen contoh tidak ada).

| Akun | Ditolak (401/403) | Lolos gerbang | Tidak teruji (422) | Galat (5xx) |
|---|---|---|---|---|
| Peran kustom tanpa acuan, semua modul "Tidak ada" | 898 | 37 | 25 | 2 |
| Sopir (peran bawaan) | 892 | 43 | 25 | 2 |
| Peran kustom beracuan Manajer, semua modul "Tidak ada" | 870 | 65 | 25 | 2 |

### I.1 Lolos bagi peran beracuan Manajer tanpa izin, ditolak bagi peran tanpa acuan (28)

Gerbangnya nama atau pangkat peran acuan, bukan izin (temuan PR-01).

| Endpoint | Jawaban | Berkas |
|---|---|---|
| `DELETE /api/ai/my-templates/{template_id}` | 404 | `backend/routers/ai_analytics.py:300` |
| `DELETE /api/ai/schedules/{schedule_id}` | 404 | `backend/routers/ai_analytics.py:355` |
| `DELETE /api/ai/sessions/{session_id}` | 404 | `backend/routers/ai_analytics.py:151` |
| `DELETE /api/incentive-rates/{rate_id}` | 404 | `backend/routers/incentive_rates.py:93` |
| `PATCH /api/ai/schedules/{schedule_id}` | 404 | `backend/routers/ai_analytics.py:340` |
| `PATCH /api/incentive-rates/{rate_id}` | 400 | `backend/routers/incentive_rates.py:78` |
| `POST /api/ai/actions/{pid}/confirm` | 404 | `backend/routers/ai_assist.py:20` |
| `POST /api/ai/actions/{pid}/dismiss` | 404 | `backend/routers/ai_assist.py:25` |
| `POST /api/ai/analyze-change` | 400 | `backend/routers/ai_analytics.py:51` |
| `POST /api/ai/chat` | 400 | `backend/routers/ai_analytics.py:115` |
| `POST /api/ai/feedback` | 400 | `backend/routers/ai_analytics.py:170` |
| `POST /api/ai/insights/scan` | 200 | `backend/routers/ai_assist.py:38` |
| `POST /api/ai/my-templates` | 400 | `backend/routers/ai_analytics.py:285` |
| `POST /api/ai/narrative` | 404 | `backend/routers/ai_analytics.py:262` |
| `POST /api/ai/query` | 400 | `backend/routers/ai_analytics.py:46` |
| `POST /api/ai/schedules` | 400 | `backend/routers/ai_analytics.py:322` |
| `POST /api/ai/schedules/{schedule_id}/run` | 404 | `backend/routers/ai_analytics.py:363` |
| `POST /api/ai/templates/{template_id}/run` | 400 | `backend/routers/ai_analytics.py:95` |
| `POST /api/ai/tools/{tool}` | 400 | `backend/routers/ai_analytics.py:105` |
| `POST /api/credit-overrides/{override_id}/decision` | 400 | `backend/routers/crm.py:141` |
| `POST /api/customers/{customer_id}/reassign` | 400 | `backend/routers/crm.py:71` |
| `POST /api/data-hygiene/location/{collection}/{doc_id}` | 404 | `backend/routers/data_hygiene.py:81` |
| `POST /api/incentive-rates` | 200 | `backend/routers/incentive_rates.py:56` |
| `POST /api/notifications/generate` | 200 | `backend/routers/notifications.py:110` |
| `POST /api/sales-incentives` | 400 | `backend/routers/crm.py:424` |
| `POST /api/sales-targets` | 400 | `backend/routers/crm.py:369` |
| `POST /api/sales/incentive/post-gl` | 200 | `backend/routers/crm.py:321` |
| `PUT /api/supplier-contracts/policy` | 200 | `backend/routers/supplier_contracts.py:77` |

### I.2 Lolos bagi akun tanpa izin apa pun (37)

| Endpoint | Jawaban | Gerbang statik | Berkas | Catatan |
|---|---|---|---|---|
| `DELETE /api/registration/sessions/{sid}/lines/{line_id}` | 404 | — | `backend/routers/initial_registration.py:192` | Pencarian dokumen mendahului gerbang; gerbang izin ada sesudahnya (dibaca) |
| `PATCH /api/registration/sessions/{sid}/lines/{line_id}` | 404 | — | `backend/routers/initial_registration.py:192` | Pencarian dokumen mendahului gerbang; gerbang izin ada sesudahnya (dibaca) |
| `POST /api/config/simulate` | 404 | IZIN | `backend/routers/config.py:224` | Validasi isi atau pencarian dokumen mendahului gerbang; gerbang izin ada sesudahnya (dibaca) |
| `POST /api/config/values/clear` | 404 | LOGIN | `backend/routers/config.py:322` | Wewenang diperiksa per kunci (teruji di T3) |
| `POST /api/config/values/reset` | 404 | LOGIN | `backend/routers/config.py:299` | Wewenang diperiksa per kunci (teruji di T3) |
| `POST /api/customers/{customer_id}/merge` | 400 | IZIN | `backend/routers/customers.py:271` | Validasi isi atau pencarian dokumen mendahului gerbang; gerbang izin ada sesudahnya (dibaca) |
| `POST /api/enums/products/validate` | 200 | LOGIN | `backend/routers/enums.py:105` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/enums/stage-transitions/validate` | 400 | LOGIN | `backend/routers/enums.py:94` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/handheld/batches` | 404 | IZIN_CABANG | `backend/routers/handheld.py:200` | Validasi isi atau pencarian dokumen mendahului gerbang; gerbang izin ada sesudahnya (dibaca) |
| `POST /api/handheld/tasks/{kind}/{doc_id}/complete` | 404 | IZIN_CABANG | `backend/routers/handheld.py:208` | Validasi isi atau pencarian dokumen mendahului gerbang; gerbang izin ada sesudahnya (dibaca) |
| `POST /api/hr/attendance/clock-in` | 404 | LOGIN | `backend/routers/hr_attendance.py:329` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/hr/attendance/clock-out` | 404 | LOGIN | `backend/routers/hr_attendance.py:371` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/hr/field-tracks` | 404 | LOGIN | `backend/routers/hr_tracking.py:85` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/hr/leave-requests/me` | 404 | LOGIN | `backend/routers/hr_leave.py:50` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/hr/leave-requests/{leave_id}/cancel` | 404 | IZIN | `backend/routers/hr_leave.py:180` | Validasi isi atau pencarian dokumen mendahului gerbang; gerbang izin ada sesudahnya (dibaca) |
| `POST /api/hr/overtime/me` | 404 | LOGIN | `backend/routers/hr_leave.py:205` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/hr/visits/check-in` | 404 | LOGIN | `backend/routers/hr_tracking.py:197` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/hr/visits/{visit_id}/check-out` | 404 | LOGIN | `backend/routers/hr_tracking.py:226` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/landed-costs/{voucher_id}/approve` | 404 | LOGIN | `backend/routers/landed_cost.py:238` | Wewenang diperiksa lewat pangkat peran sesudah dokumen ditemukan (PR-05, T10) |
| `POST /api/landed-costs/{voucher_id}/reject` | 404 | LOGIN | `backend/routers/landed_cost.py:291` | Wewenang diperiksa lewat pangkat peran sesudah dokumen ditemukan (PR-05, T10) |
| `POST /api/notifications/read-all` | 200 | LOGIN | `backend/routers/notifications.py:92` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/notifications/{notification_id}/read` | 404 | LOGIN | `backend/routers/notifications.py:98` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/onboarding/reset` | 200 | LOGIN | `backend/routers/onboarding.py:81` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/onboarding/{task_id}/complete` | 404 | LOGIN | `backend/routers/onboarding.py:66` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/purchase-orders/{po_id}/approve` | 404 | LOGIN | `backend/routers/purchase_orders.py:798` | Wewenang diperiksa lewat pangkat peran sesudah dokumen ditemukan (PR-05, T10) |
| `POST /api/purchase-orders/{po_id}/reject` | 404 | LOGIN | `backend/routers/purchase_orders.py:920` | Wewenang diperiksa lewat pangkat peran sesudah dokumen ditemukan (PR-05, T10) |
| `POST /api/push/test` | 404 | LOGIN | `backend/routers/push.py:76` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/push/unsubscribe` | 200 | LOGIN | `backend/routers/push.py:62` | Milik sendiri atau validasi tanpa tulis |
| `POST /api/rfid/v2/passages/{passage_id}/acknowledge` | 400 | IZIN | `backend/routers/rfid_v2.py:212` | Validasi isi atau pencarian dokumen mendahului gerbang; gerbang izin ada sesudahnya (dibaca) |
| `POST /api/special-orders/{order_id}/fulfillment/{item_key}/cancel` | 404 | IZIN | `backend/routers/special_orders.py:786` | Validasi isi atau pencarian dokumen mendahului gerbang; gerbang izin ada sesudahnya (dibaca) |
| `POST /api/special-orders/{order_id}/fulfillment/{item_key}/realize` | 404 | LOGIN | `backend/routers/special_orders.py:765` | Wewenang diperiksa lewat pangkat peran sesudah dokumen ditemukan (PR-05, T10) |
| `POST /api/special-orders/{order_id}/fulfillment/{item_key}/route` | 404 | LOGIN | `backend/routers/special_orders.py:750` | Wewenang diperiksa lewat pangkat peran sesudah dokumen ditemukan (PR-05, T10) |
| `POST /api/vendor-bills/{bill_id}/approve` | 404 | LOGIN | `backend/routers/vendor_bills.py:443` | Wewenang diperiksa lewat pangkat peran sesudah dokumen ditemukan (PR-05, T10) |
| `POST /api/vendor-bills/{bill_id}/reject` | 404 | LOGIN | `backend/routers/vendor_bills.py:470` | Wewenang diperiksa lewat pangkat peran sesudah dokumen ditemukan (PR-05, T10) |
| `POST /api/wilayah/validate` | 400 | LOGIN | `backend/routers/wilayah.py:53` | Milik sendiri atau validasi tanpa tulis |
| `PUT /api/config/values` | 400 | IZIN | `backend/routers/config.py:262` | Validasi isi atau pencarian dokumen mendahului gerbang; gerbang izin ada sesudahnya (dibaca) |
| `PUT /api/stock/my-site` | 200 | LOGIN | `backend/routers/stock_figures.py:76` | Milik sendiri atau validasi tanpa tulis |

### I.3 Tidak teruji (25)

Isi buatan tidak lolos validasi (parameter jalur harus angka, alasan minimal 5 huruf, nomor telepon), sehingga gerbang
izinnya tidak tercapai. Semuanya berkategori gerbang izin di inventaris statik.

`DELETE /api/goods-receipts/{grn_id}/files/{page}`, `DELETE /api/goods-receipts/{grn_id}/lines/{line_no}`, `PATCH /api/goods-receipts/{grn_id}/lines/{line_no}`, `PATCH /api/purchase-requisitions/{pr_id}/lines/{line_no}`, `POST /api/customers`, `POST /api/cycle-count/sessions/{session_id}/reject`, `POST /api/design-gallery/{gallery_id}/rounds/{version}/paper`, `POST /api/goods-receipts/{grn_id}/cancel`, `POST /api/goods-receipts/{grn_id}/discrepancies/{key}/resolve`, `POST /api/goods-receipts/{grn_id}/lines/{line_no}/rolls`, `POST /api/goods-receipts/{grn_id}/lines/{line_no}/save-catalog`, `POST /api/goods-receipts/{grn_id}/lines/{line_no}/scan-label`, `POST /api/goods-receipts/{grn_id}/reject`, `POST /api/makloon-orders/{mko_id}/steps/{seq}/material-loss`, `POST /api/makloon-orders/{mko_id}/steps/{seq}/material-loss/{loss_id}/decide`, `POST /api/makloon-orders/{mko_id}/steps/{seq}/partial-receipts/{grn_id}/cancel`, `POST /api/makloon-orders/{mko_id}/steps/{seq}/return-material`, `POST /api/makloon-orders/{mko_id}/steps/{seq}/tolerance`, `POST /api/master/grades`, `POST /api/purchase-orders/{po_id}/close`, `POST /api/registration/sessions/{sid}/approve`, `POST /api/registration/sessions/{sid}/approve-count`, `POST /api/registration/sessions/{sid}/reject`, `POST /api/registration/sessions/{sid}/return`, `PUT /api/goods-receipts/mode`

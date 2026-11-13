# PR-T3 — Pilah endpoint yang hanya butuh login: tetap, beri izin, atau saring isinya

| | |
|---|---|
| Gelombang | Jalur peran (sejajar dengan gelombang 3–7) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | PR-T2 |
| Menutup temuan | PR-04 (beserta butir layar PR-UX-43) |
| Keputusan | K-47; merujuk K-18 (PK-17) dan K-49 (KF-T1) |
| Standar | §3.1 (Z1, Z3), §3.2, §6 |
| Lingkungan uji | B |

## Tujuan

Setiap endpoint yang hari ini cukup dengan login punya satu putusan tertulis: tetap terbuka karena milik sendiri, data
rujukan, atau urusan sesi; dijaga izin; atau isinya disaring menurut izin. Sopir tidak lagi bisa membaca target sales,
daftar sales, rincian PT, atau isi dasbor pesanan lewat API.

## Keadaan sekarang

| # | Fakta | Jangkar | Bukti |
|---|---|---|---|
| 1 | Inventaris mencatat 107 endpoint hanya butuh login (41 tulis, 66 baca) | `docs/audit/konfigurasi-peran-2026-11-13/LAMPIRAN_DAFTAR.md` | [statik] `bukti/inv_endpoints.py`, §B dan §C |
| 2 | Pembacaan langsung pada HEAD menemukan 12 lagi yang oleh inventaris digolongkan "berizin" karena pembantu bernama sama di berkas lain; di tabel A bertanda (+) | `backend/routers/period_unlocks.py:43` (`list_unlocks`); `backend/routers/ai_analytics.py:46` (`post_query`); `backend/routers/config.py:262` (`write_values`) | [dibaca] |
| 3 | Sopir mendapat 200 dan isi lengkap di `GET /api/sales-targets`, `GET /api/sales-users`, `GET /api/entities`, `GET /api/home/finance`, `GET /api/config/effective` | `backend/routers/crm.py:351` (`list_targets`); `backend/routers/crm.py:31` (`list_sales_users`); `backend/routers/entities.py:35` (`list_entities`) | [dijalankan] `docs/audit/konfigurasi-peran-2026-11-13/bukti/t3_escalation.py` baris (f1)–(f5) |
| 4 | `GET /api/dashboard` mengirim pesanan, pelanggan, produk, gudang, dan angka stok kepada siapa pun yang login; yang disaring hanya kepemilikan sales, lini produk, dan kolom biaya | `backend/routers/dashboard.py:42` (`dashboard`) | [dibaca] |
| 5 | `GET /api/entities/{id}` mengirim jumlah akun dan kunci awalan nomor kepada siapa pun yang login; layar pemanggilnya hanya layar Badan Usaha & Akses | `backend/routers/entities.py:99` (`get_entity`); `frontend/src/features/settings/entities/entityApi.js:40` (`getEntity`) | [dibaca] |
| 6 | Dua aksi pemenuhan pesanan khusus tidak punya gerbang di handler; izinnya baru diperiksa di dalam layanan, setelah dokumen dimuat | `backend/routers/special_orders.py:750` (`fulfillment_set_route`); `backend/services/special_order_fulfillment.py:213` (`has_permission`) | [dibaca] |
| 7 | Riwayat dan antrean usul buka periode bisa dibaca tanpa izin | `backend/routers/period_unlocks.py:43` (`list_unlocks`) | [dibaca] |
| 8 | Beberapa endpoint tulis hanya menuntut izin lihat, mis. cetak label lot | `backend/routers/lots.py:185` (`lot_label`); `backend/routers/rfid.py:225` (`post_roll_scan`) | [dibaca] lampiran B Lampiran F |

## Perubahan

### Data

Tidak ada.

### Server

**Tabel A — 119 endpoint (107 dari lampiran + 12 bertanda (+)), satu putusan per baris.**

| Metode | Jalur | Jangkar | Putusan |
|---|---|---|---|
| GET | `/api/ai/catalog` | `backend/routers/ai_analytics.py:37` (`get_catalog`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| POST | `/api/ai/query` (+) | `backend/routers/ai_analytics.py:46` (`post_query`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| POST | `/api/ai/analyze-change` (+) | `backend/routers/ai_analytics.py:51` (`post_analyze_change`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| GET | `/api/ai/results/{result_id}` | `backend/routers/ai_analytics.py:56` (`get_result`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| GET | `/api/ai/status` | `backend/routers/ai_analytics.py:81` (`get_status`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| GET | `/api/ai/templates` | `backend/routers/ai_analytics.py:87` (`list_templates`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| POST | `/api/ai/templates/{template_id}/run` | `backend/routers/ai_analytics.py:95` (`run_template`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| POST | `/api/ai/tools/{tool}` | `backend/routers/ai_analytics.py:105` (`run_tool`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| POST | `/api/ai/chat` | `backend/routers/ai_analytics.py:115` (`post_chat`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| GET | `/api/ai/sessions` | `backend/routers/ai_analytics.py:137` (`list_sessions`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| DELETE | `/api/ai/sessions/{session_id}` | `backend/routers/ai_analytics.py:151` (`delete_session`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| GET | `/api/ai/sessions/{session_id}` | `backend/routers/ai_analytics.py:160` (`get_session`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| POST | `/api/ai/feedback` | `backend/routers/ai_analytics.py:170` (`post_feedback`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| GET | `/api/ai/results/{result_id}/export.xlsx` | `backend/routers/ai_analytics.py:224` (`export_result`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| GET | `/api/ai/export.xlsx` (+) | `backend/routers/ai_analytics.py:234` (`export_answer`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| POST | `/api/ai/narrative` | `backend/routers/ai_analytics.py:262` (`post_narrative`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| GET | `/api/ai/my-templates` | `backend/routers/ai_analytics.py:279` (`list_my_templates`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| POST | `/api/ai/my-templates` | `backend/routers/ai_analytics.py:285` (`create_my_template`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| DELETE | `/api/ai/my-templates/{template_id}` | `backend/routers/ai_analytics.py:300` (`delete_my_template`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| GET | `/api/ai/schedules` | `backend/routers/ai_analytics.py:316` (`list_schedules`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| POST | `/api/ai/schedules` (+) | `backend/routers/ai_analytics.py:322` (`create_schedule`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| PATCH | `/api/ai/schedules/{schedule_id}` (+) | `backend/routers/ai_analytics.py:340` (`update_schedule`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| DELETE | `/api/ai/schedules/{schedule_id}` | `backend/routers/ai_analytics.py:355` (`delete_schedule`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| POST | `/api/ai/schedules/{schedule_id}/run` | `backend/routers/ai_analytics.py:363` (`run_schedule_now`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| GET | `/api/ai/schedule-runs` | `backend/routers/ai_analytics.py:370` (`list_schedule_runs`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| GET | `/api/ai/schedule-runs/{run_id}` | `backend/routers/ai_analytics.py:378` (`get_schedule_run`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| GET | `/api/ai/usage/daily` | `backend/routers/ai_analytics.py:424` (`usage_daily`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`); isi tetap milik sendiri |
| GET | `/api/ai/actions/{pid}` | `backend/routers/ai_assist.py:15` (`get_action`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`) |
| POST | `/api/ai/actions/{pid}/confirm` | `backend/routers/ai_assist.py:20` (`confirm_action`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`) |
| POST | `/api/ai/actions/{pid}/dismiss` | `backend/routers/ai_assist.py:25` (`dismiss_action`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`) |
| GET | `/api/ai/insights` | `backend/routers/ai_assist.py:30` (`get_insights`) | Beri izin `ai.view` — dikerjakan PR-T2 (`_ai_user`) |
| POST | `/api/ai/insights/scan` | `backend/routers/ai_assist.py:38` (`scan_insights`) | Beri izin `ai.manage` — dikerjakan PR-T2 |
| GET | `/api/roles` | `backend/routers/auth.py:149` (`list_roles`) | Tetap — data rujukan (daftar peran: label, lintas PT, beranda); tanpa nominal |
| GET | `/api/auth/me` (+) | `backend/routers/auth.py:163` (`me`) | Tetap — infrastruktur sesi |
| GET | `/api/auth/context` | `backend/routers/auth.py:176` (`auth_context`) | Tetap — infrastruktur sesi |
| GET | `/api/config/registry` | `backend/routers/config.py:160` (`read_registry`) | Dikerjakan KF-T1 |
| GET | `/api/config/effective` | `backend/routers/config.py:184` (`read_effective`) | Dikerjakan KF-T1 |
| GET | `/api/config/explain` (+) | `backend/routers/config.py:204` (`explain`) | Dikerjakan KF-T1 |
| POST | `/api/config/simulate` (+) | `backend/routers/config.py:224` (`simulate`) | Dikerjakan KF-T1 |
| PUT | `/api/config/values` (+) | `backend/routers/config.py:262` (`write_values`) | Dikerjakan KF-T1 |
| POST | `/api/config/values/reset` | `backend/routers/config.py:299` (`reset_value`) | Dikerjakan KF-T1 |
| POST | `/api/config/values/clear` | `backend/routers/config.py:322` (`clear_value_layer`) | Dikerjakan KF-T1 |
| GET | `/api/config/history` | `backend/routers/config.py:351` (`read_history`) | Dikerjakan KF-T1 |
| GET | `/api/config/simulators` | `backend/routers/config.py:402` (`list_simulators`) | Dikerjakan KF-T1 |
| GET | `/api/sales-users` | `backend/routers/crm.py:31` (`list_sales_users`) | Beri izin: salah satu dari `customer.view`, `order.view`, `sales_force.view` |
| GET | `/api/sales-targets` | `backend/routers/crm.py:351` (`list_targets`) | Beri izin `order.view` + saring isi: milik sendiri, kecuali yang boleh melihat sales lain menurut `_kpi_scope` atau pemegang `sales_force.view` |
| GET | `/api/sales-incentives` | `backend/routers/crm.py:407` (`list_incentives`) | Beri izin `order.view` + saring isi: milik sendiri, kecuali yang boleh melihat sales lain menurut `_kpi_scope` atau pemegang `sales_force.view` |
| GET | `/api/dashboard` | `backend/routers/dashboard.py:42` (`dashboard`) | Saring isi per bagian (lihat S1) |
| GET | `/api/documents/resolve` | `backend/routers/documents.py:385` (`resolve_document_number`) | Tetap — isi sudah disaring izin modul di dalam handler (`_may_view`) |
| GET | `/api/entities` | `backend/routers/entities.py:35` (`list_entities`) | Tetap sebagai rujukan + saring isi (lihat S2) |
| GET | `/api/entities/count` | `backend/routers/entities.py:84` (`count_entities`) | Beri izin `entity.view` |
| GET | `/api/entities/{entity_id}` | `backend/routers/entities.py:99` (`get_entity`) | Beri izin `entity.view` |
| GET | `/api/entities/{entity_id}/readiness` | `backend/routers/entities.py:110` (`get_readiness`) | Beri izin `entity.view` |
| GET | `/api/enums` | `backend/routers/enums.py:73` (`list_enums`) | Tetap — data rujukan |
| GET | `/api/enums/stage-transitions` | `backend/routers/enums.py:83` (`stage_transitions`) | Tetap — data rujukan |
| POST | `/api/enums/stage-transitions/validate` | `backend/routers/enums.py:94` (`validate_stage_transition`) | Tetap — data rujukan |
| POST | `/api/enums/products/validate` | `backend/routers/enums.py:105` (`validate_product_domain`) | Tetap — data rujukan |
| GET | `/api/enums/{name}` | `backend/routers/enums.py:112` (`get_enum`) | Tetap — data rujukan |
| GET | `/api/master/fabric-types` | `backend/routers/fabric_type_master.py:21` (`list_fabric_types`) | Tetap — data rujukan |
| GET | `/api/home/sales` | `backend/routers/home.py:47` (`home_sales`) | Dikerjakan PK-17 |
| GET | `/api/home/warehouse` | `backend/routers/home.py:81` (`home_warehouse`) | Dikerjakan PK-17 |
| GET | `/api/home/finance` | `backend/routers/home.py:101` (`home_finance`) | Dikerjakan PK-17 |
| GET | `/api/hr/employees/me` | `backend/routers/hr.py:236` (`my_employee`) | Tetap — milik sendiri |
| GET | `/api/hr/attendance/me` | `backend/routers/hr_attendance.py:311` (`my_attendance`) | Tetap — milik sendiri |
| POST | `/api/hr/attendance/clock-in` | `backend/routers/hr_attendance.py:329` (`clock_in`) | Tetap — milik sendiri |
| POST | `/api/hr/attendance/clock-out` | `backend/routers/hr_attendance.py:371` (`clock_out`) | Tetap — milik sendiri |
| GET | `/api/hr/kpi/me` | `backend/routers/hr_kpi.py:52` (`my_kpi_endpoint`) | Tetap — milik sendiri |
| GET | `/api/hr/leave-requests/me` | `backend/routers/hr_leave.py:44` (`my_leave_requests`) | Tetap — milik sendiri |
| POST | `/api/hr/leave-requests/me` | `backend/routers/hr_leave.py:50` (`submit_my_leave`) | Tetap — milik sendiri |
| GET | `/api/hr/leave-balance/me` (+) | `backend/routers/hr_leave.py:62` (`my_leave_balance`) | Tetap — milik sendiri |
| GET | `/api/hr/overtime/me` | `backend/routers/hr_leave.py:199` (`my_overtime_requests`) | Tetap — milik sendiri |
| POST | `/api/hr/overtime/me` | `backend/routers/hr_leave.py:205` (`submit_my_overtime`) | Tetap — milik sendiri |
| GET | `/api/hr/payslips/me` | `backend/routers/hr_payroll.py:223` (`my_payslips`) | Tetap — milik sendiri |
| POST | `/api/hr/field-tracks` | `backend/routers/hr_tracking.py:85` (`push_track`) | Tetap — milik sendiri |
| GET | `/api/hr/visits/me` | `backend/routers/hr_tracking.py:150` (`my_visits`) | Tetap — milik sendiri |
| GET | `/api/hr/visits/mine` | `backend/routers/hr_tracking.py:163` (`my_visits_history`) | Tetap — milik sendiri |
| POST | `/api/hr/visits/check-in` | `backend/routers/hr_tracking.py:197` (`visit_check_in`) | Tetap — milik sendiri |
| POST | `/api/hr/visits/{visit_id}/check-out` | `backend/routers/hr_tracking.py:226` (`visit_check_out`) | Tetap — milik sendiri |
| POST | `/api/landed-costs/{voucher_id}/approve` | `backend/routers/landed_cost.py:238` (`approve_landed_cost`) | Dikerjakan KP-T4 |
| POST | `/api/landed-costs/{voucher_id}/reject` | `backend/routers/landed_cost.py:291` (`reject_landed_cost`) | Dikerjakan KP-T4 |
| GET | `/api/notifications` | `backend/routers/notifications.py:59` (`list_notifications`) | Tetap — milik sendiri (notifikasi pengguna itu) |
| GET | `/api/notifications/unread-count` | `backend/routers/notifications.py:85` (`unread_count`) | Tetap — milik sendiri (notifikasi pengguna itu) |
| POST | `/api/notifications/read-all` | `backend/routers/notifications.py:92` (`mark_all_read`) | Tetap — milik sendiri (notifikasi pengguna itu) |
| POST | `/api/notifications/{notification_id}/read` | `backend/routers/notifications.py:98` (`mark_read`) | Tetap — milik sendiri (notifikasi pengguna itu) |
| GET | `/api/onboarding` | `backend/routers/onboarding.py:44` (`get_onboarding`) | Tetap — milik sendiri |
| POST | `/api/onboarding/{task_id}/complete` | `backend/routers/onboarding.py:66` (`complete_task`) | Tetap — milik sendiri |
| POST | `/api/onboarding/reset` | `backend/routers/onboarding.py:81` (`reset_onboarding`) | Tetap — milik sendiri |
| GET | `/api/finance/period-unlocks` (+) | `backend/routers/period_unlocks.py:43` (`list_unlocks`) | Beri izin: salah satu dari `period.unlock`, `accounting.view` |
| GET | `/api/finance/period-unlocks/active` | `backend/routers/period_unlocks.py:51` (`active_unlocks`) | Tetap — pemberitahuan tanpa nominal (banner periode terbuka), terbatas PT pengguna |
| GET | `/api/purchase-orders/resolve-sourcing` | `backend/routers/purchase_orders.py:298` (`resolve_po_sourcing`) | Beri izin: salah satu dari `purchase_order.create`, `purchase_order.update` |
| POST | `/api/purchase-orders/{po_id}/approve` | `backend/routers/purchase_orders.py:798` (`approve_purchase_order`) | Dikerjakan KP-T4 |
| POST | `/api/purchase-orders/{po_id}/reject` | `backend/routers/purchase_orders.py:920` (`reject_purchase_order`) | Dikerjakan KP-T4 |
| GET | `/api/push/public-key` | `backend/routers/push.py:38` (`public_key`) | Tetap — infrastruktur sesi |
| POST | `/api/push/subscribe` | `backend/routers/push.py:45` (`subscribe`) | Tetap — milik sendiri (langganan perangkat pengguna) |
| POST | `/api/push/unsubscribe` | `backend/routers/push.py:62` (`unsubscribe`) | Tetap — milik sendiri (langganan perangkat pengguna) |
| GET | `/api/push/status` | `backend/routers/push.py:69` (`status`) | Tetap — milik sendiri (langganan perangkat pengguna) |
| POST | `/api/push/test` | `backend/routers/push.py:76` (`test_push`) | Tetap — milik sendiri (langganan perangkat pengguna) |
| GET | `/api/rnd/reports/my-kpi` | `backend/routers/rnd.py:913` (`my_designer_kpi`) | Tetap — milik sendiri |
| GET | `/api/settings` | `backend/routers/settings.py:26` (`read_settings`) | Dikerjakan KF-T1 |
| GET | `/api/settings/effective` | `backend/routers/settings.py:32` (`read_effective_settings`) | Dikerjakan KF-T1 |
| GET | `/api/settings/compute-tax` | `backend/routers/settings.py:95` (`compute_tax_endpoint`) | Dikerjakan KF-T1 |
| GET | `/api/settings/evaluate-approval` | `backend/routers/settings.py:102` (`evaluate_approval_endpoint`) | Dikerjakan KF-T1 |
| GET | `/api/payment-terms` | `backend/routers/settings.py:112` (`list_payment_terms`) | Tetap — data rujukan (kode, nama, dan hari termin) |
| POST | `/api/special-orders/{order_id}/fulfillment/{item_key}/route` | `backend/routers/special_orders.py:750` (`fulfillment_set_route`) | Beri izin `od_fulfillment.choose_route` di baris pertama handler (kini diperiksa di layanan) |
| POST | `/api/special-orders/{order_id}/fulfillment/{item_key}/realize` | `backend/routers/special_orders.py:765` (`fulfillment_realize`) | Beri izin `od_fulfillment.realize` di baris pertama handler (kini diperiksa di layanan) |
| GET | `/api/stock/my-site` | `backend/routers/stock_figures.py:67` (`get_my_site`) | Tetap — milik sendiri |
| PUT | `/api/stock/my-site` | `backend/routers/stock_figures.py:76` (`put_my_site`) | Tetap — milik sendiri |
| POST | `/api/vendor-bills/{bill_id}/approve` | `backend/routers/vendor_bills.py:443` (`approve_vendor_bill`) | Dikerjakan KP-T4 |
| POST | `/api/vendor-bills/{bill_id}/reject` | `backend/routers/vendor_bills.py:470` (`reject_vendor_bill`) | Dikerjakan KP-T4 |
| GET | `/api/wilayah/countries` | `backend/routers/wilayah.py:11` (`countries`) | Tetap — data rujukan |
| GET | `/api/wilayah/provinces` | `backend/routers/wilayah.py:17` (`provinces`) | Tetap — data rujukan |
| GET | `/api/wilayah/regencies` | `backend/routers/wilayah.py:23` (`regencies`) | Tetap — data rujukan |
| GET | `/api/wilayah/districts` | `backend/routers/wilayah.py:29` (`districts`) | Tetap — data rujukan |
| GET | `/api/wilayah/villages` | `backend/routers/wilayah.py:35` (`villages`) | Tetap — data rujukan |
| GET | `/api/wilayah/postal-code/{code}` | `backend/routers/wilayah.py:41` (`postal_code`) | Tetap — data rujukan |
| GET | `/api/wilayah/search` | `backend/routers/wilayah.py:47` (`search`) | Tetap — data rujukan |
| POST | `/api/wilayah/validate` | `backend/routers/wilayah.py:53` (`validate`) | Tetap — data rujukan |
| GET | `/api/location-scope` (+) | `backend/routers/wms.py:181` (`location_scope_summary`) | Tetap — milik sendiri (lokasi kerja pengguna) |
| GET | `/api/desks/me` | `backend/routers/work_desks.py:255` (`my_desk`) | Dikerjakan PR-T4 (meja kerja mengikuti sifat peran) |

Ringkasan: tetap 53 · dikerjakan PR-T2 32 · KF-T1 13 · KP-T4 6 · PK-17 3 · PR-T4 1 · diberi izin atau disaring oleh
unit ini 11.

**Rincian putusan milik unit ini**

| Kode | Endpoint | Aturan |
|---|---|---|
| S1 | `GET /api/dashboard` | Tetap 200 untuk semua yang login (dipanggil sekali untuk seluruh aplikasi), tetapi tiap bagian hanya diisi bila peran memegang izinnya: `orders` dan `metrics.active_orders` ← `order.view`; `customers` dan `metrics.customers` ← `customer.view`; `products` dan `metrics.products` ← `product.view`; `warehouses` dan `metrics.warehouses` ← `warehouse.view`; angka stok (`available_qty`, `reserved_qty`, `available_by_unit`, `reserved_by_unit`, `available_rolls`, `unitless_product_ids`, `stock_scope`) ← `inventory.view`. Bagian tanpa izin = daftar kosong atau 0, kuncinya tetap ada. Kueri bagian yang tidak diizinkan tidak dijalankan |
| S2 | `GET /api/entities` | Tetap 200 (pemilih PT dan nama PT lawan dipakai banyak layar). Tanpa `entity.view`: tiap baris hanya memuat `id`, `code`, `name`, `short_name`, `legal_name`, `type`, `is_pkp`, `currency`, `status`, `doc_prefix`, `logo_url`; `user_count` dan `readiness` tidak dikirim dan `with_readiness` diabaikan |
| S3 | `GET /api/sales-targets`, `GET /api/sales-incentives` | `require_permission(request, "order", "view")`. Isi: pemegang `sales_force.view` melihat semua (dalam PT-nya); selain itu memakai aturan yang sama dengan KPI dan komisi (`backend/routers/crm.py:240`, `_kpi_scope`): hanya miliknya kecuali peran pengawas |
| S4 | `GET /api/sales-users` | `require_any_permission(request, [("customer", "view"), ("order", "view"), ("sales_force", "view")])` |
| S5 | `GET /api/entities/count`, `GET /api/entities/{entity_id}`, `GET /api/entities/{entity_id}/readiness` | `require_permission(request, "entity", "view")` |
| S6 | `GET /api/finance/period-unlocks` | `require_any_permission(request, [("period", "unlock"), ("accounting", "view")])` |
| S7 | `GET /api/purchase-orders/resolve-sourcing` | `require_any_permission(request, [("purchase_order", "create"), ("purchase_order", "update")])` |
| S8 | `POST …/fulfillment/{item_key}/route`, `POST …/fulfillment/{item_key}/realize` | `require_permission(request, "od_fulfillment", "choose_route")` dan `("od_fulfillment", "realize")` sebagai pernyataan pertama; pemeriksaan di layanan dipertahankan |

Pesan 403 semuanya dari `require_permission` / `require_any_permission` (teks manusianya dipetakan pusat di PR-T6).

**Daftar endpoint login-saja yang sah.** Berkas baru `backend/login_only_endpoints.py` memuat
`LOGIN_ONLY: Dict[Tuple[str, str], str]` — kunci `(metode, jalur)`, nilai salah satu dari `"milik_sendiri"`,
`"rujukan"`, `"sesi"`. Isinya 53 baris berputusan "Tetap" di tabel A. Endpoint yang ditangani unit lain ditambahkan
atau tidak oleh unit itu. Daftar ini dibaca penjaga matriks (PR-T8): rute login-saja di luar daftar = merah.

**Tabel B — endpoint tulis yang hanya menuntut izin lihat (lampiran B Lampiran F).**

| Metode | Jalur | Jangkar | Izin sekarang | Putusan |
|---|---|---|---|---|
| POST | `/api/lots/{lot_id}/label` | `backend/routers/lots.py:185` (`lot_label`) | `inventory.view` | Naik ke `label.generate` (izin lama: Admin, Manajer, Gudang, Admin Gudang) |
| POST | `/api/rfid/roll-scans` | `backend/routers/rfid.py:225` (`post_roll_scan`) | `wms.view` | Tetap — hanya mencatat jejak pindai milik pengguna itu; tidak mengubah stok |
| POST | `/api/color-library/{color_id}/use-requests` | `backend/routers/color_library.py:82` (`create_use_request`) | `color.view` | Tetap — pengajuan yang diputus pemegang `color.approve` |
| PATCH | `/api/products/{product_id}/media/{media_id}` | `backend/routers/product_media.py:89` (`update`) | `product.view` + kemampuan foto | Tetap — izin ubah/tinjau foto diperiksa di dalam (`capabilities`) |
| DELETE | `/api/export/templates/{tpl_id}` | `backend/routers/export_center.py:363` (`delete_template`) | `data_export.view` | Tetap — hanya templat milik sendiri (`_own_tpl`) |
| PUT | `/api/rnd/divisions/members` | `backend/routers/rnd_org.py:59` (`set_member_division`) | `rnd.view` + nama peran | Dikerjakan PR-T2 (`rnd.manage_org`) |
| DELETE | `/api/master/{kind}/{mid}/purge` | `backend/routers/master_governance.py:146` (`master_purge`) | `product.view` + nama peran | Dikerjakan PR-T2 (`product.retire`) |
| POST | 23 endpoint pratinjau dan simulasi yang didaftar Lampiran F (`…/preview*`, `…/simulate`, `…/resolve`, `…/convert`, `…/check-variance`, `…/budget-check`, `…/estimate`, `…/assess`, `…/validate-script`, `…/forecast`, `…/label-pattern/test`, `…/label-preview`, `…/tariff-preview`) | — | izin lihat modulnya | Tetap — tidak menulis apa pun; uji U11 membuktikannya |

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada pasangan izin baru. Semua izin yang dipakai sudah ada atau lahir di PR-T2 (`sales_force.view`).

### Layar

Tidak ada layar yang diubah. Pemanggil endpoint yang kini berizin sudah berada di layar yang menuntut izin yang sama
(`entityApi.js` untuk S5; form PO untuk S7; layar Buka Periode untuk S6). Pemeriksaan pada langkah kerja 5: cari
pemakaian field di luar daftar S2 dari jawaban `/api/entities` di `frontend/src`; field yang dipakai layar non-Admin
ditambahkan ke daftar S2 dan dicatat di laporan.

## Uji penerimaan

Persiapan bersama: peran uji baku `02` §6; `sls` = sales seed; `adm` = admin seed. Berkas
`backend/tests_mem/data/kode_sebelum_PRT3.json` dibuat pada langkah kerja 1 sebelum kode diubah: kode jawaban 13 peran
bawaan untuk rute S3–S8 dan baris pertama tabel B.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | "Tanpa Acuan" + `customer.view` | `GET /api/sales-users` oleh Tanpa Acuan, Manajer Kosong, Sopir | 200 · 403 · 403 |
| U2 | B | `adm` membuat satu target untuk `sls` dan satu untuk akun sales kedua | `GET /api/sales-targets` oleh Sopir, `sls`, "Tanpa Acuan" + `order.view`, lalu "Tanpa Acuan" + `order.view` + `sales_force.view` | 403 · 1 baris (miliknya) · 0 baris · 2 baris |
| U3 | B | — | `GET /api/entities` oleh Sopir dan oleh `adm` | Keduanya 200 dengan jumlah baris sama; baris Sopir hanya berisi 11 kunci S2; baris `adm` memuat `user_count` |
| U4 | B | "Tanpa Acuan" + `entity.view` | `GET /api/entities/ent_ksc` dan `…/readiness` oleh Tanpa Acuan, Manajer Kosong, Sopir | 200, 200 · 403, 403 · 403, 403 |
| U5 | B | satu pesanan dan satu pelanggan milik `sls` (fixture) | `GET /api/dashboard` oleh Sopir | 200; `orders`, `customers`, `products`, `warehouses` = `[]`; `metrics.active_orders` = 0 |
| U6 | B | seperti U5; "Tanpa Acuan" + `order.view` | `GET /api/dashboard` | `orders` berisi 1; `customers` = `[]`; `products` = `[]` |
| U7 | B | "Tanpa Acuan" + `period.unlock` | `GET /api/finance/period-unlocks` oleh Tanpa Acuan, Manajer Kosong, Sopir; `GET /api/finance/period-unlocks/active` oleh Sopir | 200 · 403 · 403; 200 |
| U8 | B | "Tanpa Acuan" + `purchase_order.create` | `GET /api/purchase-orders/resolve-sourcing?product_id=x` oleh Tanpa Acuan dan Sopir | bukan 403 · 403 |
| U9 | B | — | `POST /api/special-orders/tidak-ada/fulfillment/k/route` dengan isi sah oleh Sopir, lalu oleh "Tanpa Acuan" + `od_fulfillment.choose_route` | 403 (sebelum unit: 404) · 404 |
| U10 | B | "Tanpa Acuan" + `inventory.view` + `field_visibility.lot` | `POST /api/lots/tidak-ada/label` dengan isi sah, sebelum dan sesudah ditambah `label.generate` | 403 · bukan 403 |
| U11 | B | catat jumlah dokumen semua koleksi | `adm` memanggil tiap endpoint pratinjau/simulasi tabel B dengan isi sah atau kosong | Jumlah dokumen tiap koleksi tidak berubah (selain `audit_logs` dan `sessions`) |
| U12 | B | — | Sopir: `GET /api/enums`, `/api/wilayah/provinces`, `/api/notifications`, `/api/roles`, `/api/payment-terms`, `/api/auth/me`, `/api/onboarding`, `/api/stock/my-site` | Tidak ada yang 403 |
| U13 | B | — | Bandingkan `LOGIN_ONLY` dengan `server.app.routes` | 53 entri; tiap entri menunjuk rute yang ada dengan metode yang sama |
| U14 | B | berkas "sebelum" | Sapu ulang rute yang sama oleh 13 peran bawaan | Admin dan Manajer: kode sama di semua rute. Selisih yang diizinkan hanya dari 200 ke 403 pada: S4 dan S3 untuk Desainer, Sopir, MD Quality, QC; S5 untuk semua selain Admin dan Manajer; S6 untuk semua selain Admin, Manajer, Finance; S7 untuk semua selain Admin dan Manajer; label lot untuk peran tanpa `label.generate` |
| U15 | B | isi `GET /api/dashboard` Manajer sebelum unit (jumlah butir tiap bagian, fixture U5) | `GET /api/dashboard` oleh manajer seed | Jumlah butir tiap bagian sama |

Setelah unit selesai, `t3_escalation.py` baris (f3) dan (f4) menampilkan 403; baris (f5) tetap 200.

## Langkah kerja

1. Berkas "sebelum"; `backend/tests_mem/test_PRT3_login_saja.py` (U1–U15). Merah: U1–U10, U13, U14.
2. S4–S8 dan baris pertama tabel B (satu baris gerbang per handler). Hijau: U1, U4, U7–U10.
3. S3 (pakai `_kpi_scope`), S2, S1. Hijau: U2, U3, U5, U6, U15.
4. `login_only_endpoints.py`. Hijau: U13. U11 dan U12 sebagai penjaga.
5. Pemeriksaan pemakaian field `/api/entities` di layar; gate; laporan.

## Dokumen ikut berubah

`CODEBASE_MAP.md` (`backend/login_only_endpoints.py`).

## Di luar lingkup

- `/api/home/sales`, `/api/home/warehouse`, `/api/home/finance` dan nominal di jejak dokumen → PK-17.
- `/api/config/*`, `/api/settings*` → KF-T1 (K-49).
- Persetujuan dan penolakan PO, tagihan pemasok, voucher biaya masuk → KP-T4.
- `/api/ai/*` → PR-T2 (`ai.view`, `ai.manage`).
- `/api/desks/me` dan cakupan "milik sendiri" berdasarkan sifat peran → PR-T4.
- Endpoint tanpa sesi (perangkat, login, verifikasi publik; `LAMPIRAN_DAFTAR.md` §D) tidak diubah.
- `GET /api/entities/count` yang selalu galat 500 → PK-47; unit ini hanya menambah gerbangnya.

## Asumsi dan risiko

- `ASUMSI:` sebelas field S2 cukup untuk semua layar non-Admin yang memakai `/api/entities` (pemilih PT, nama PT lawan).
  Langkah kerja 5 memeriksanya.
- `ASUMSI:` peran pemegang `inventory.view` tanpa `label.generate` (Sales, Admin Sales, MD, Admin Sample, MD Quality,
  QC) tidak mencetak label lot; tidak ada layar mereka yang memanggilnya. Bila ternyata ada, putusan baris itu menjadi
  "tetap" dan dicatat.
- `ASUMSI:` Lampiran F menyebut 32 endpoint tetapi merinci 30 (7 menulis + 23 pratinjau); tabel B mengikuti rinciannya.
- `ASUMSI:` peran selain pengawas tidak perlu melihat target dan skema insentif orang lain; aturan `_kpi_scope` yang
  sudah berlaku untuk KPI dan komisi dipakai apa adanya.
- `RISIKO:` layar umum kehilangan data karena S1 atau S2. Penangkal: U3, U15, dan pemeriksaan langkah 5. Membatalkan:
  tiap putusan adalah satu baris gerbang atau satu saringan; kembalikan per handler.

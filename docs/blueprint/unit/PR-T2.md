# PR-T2 — Ganti gerbang nama peran dengan izin, dan beri izin setara kepada yang hari ini lolos

| | |
|---|---|
| Gelombang | Jalur peran (sejajar dengan gelombang 3–7) |
| Jenis | perbaikan |
| Risiko | tinggi (dua serah-terima) |
| Prasyarat | PR-T1, PR-T9 |
| Menutup temuan | PR-01, PR-03 (beserta butir layar PR-UX-11) |
| Keputusan | K-47 |
| Standar | §3.1 (Z1, Z2), §3.2, §6 |
| Lingkungan uji | B |

## Tujuan

Akses ke fitur yang selama ini ditentukan nama peran (atau peran dasar) kini ditentukan izin yang tampil dan bisa
dicabut di layar Peran & Hak Akses. Peran kustom tanpa peran dasar bisa diberi fitur itu; peran kustom berdasar
Manajer dengan semua modul "Tidak ada" tidak lagi mendapatkannya diam-diam. Tidak ada peran yang kehilangan akses saat
unit dipasang.

## Keadaan sekarang

| # | Fakta | Jangkar | Bukti |
|---|---|---|---|
| 1 | `require_role` meloloskan `admin` dan siapa pun yang peran atau peran dasarnya ada di daftar, tanpa membaca matriks izin | `backend/dependencies.py:93` (`require_role`); `backend/role_registry.py:334` (`role_in`) | [dibaca] |
| 2 | Peran kustom berdasar Manajer dengan semua modul "Tidak ada" mendapat 200 di 23 rute baca yang bagi Sopir 403 (HPP, beranda Manajer, papan peringkat, tarif insentif, kebersihan data, pemakaian asisten) | `backend/routers/costing.py:17` (`list_wac`); `backend/routers/home.py:65` (`home_manager`) | [dijalankan] `docs/audit/konfigurasi-peran-2026-11-13/bukti/t3_escalation.py` baris (e1), (e2); `t2_roles.py` + `t2_analyze.py` (daftar di `LAMPIRAN_DAFTAR.md` §E) |
| 3 | Peran kustom tanpa peran dasar yang memegang izin endpoint tetap ditolak di 13 rute baca oleh gerbang kedua di dalam handler | `backend/routers/rnd_org.py:21` (`_assert_appraisal`); `backend/routers/rnd.py:149` (`_assert_appraisal_role`); `backend/routers/internal_requests.py:41` (`_is_cross`) | [dijalankan] `t2_analyze.py` bagian B (`LAMPIRAN_DAFTAR.md` §F) |
| 4 | Enam dari 13 rute di butir 3 (`/api/lots*`) ditolak bukan oleh nama peran, melainkan oleh izin kedua `field_visibility.lot` di lapisan tengah | `backend/services/field_visibility.py:226` (`dispatch`) | [dibaca] |
| 5 | Di `backend/routers` ada 51 pemanggilan `require_role(` di 15 berkas. `LAMPIRAN_DAFTAR.md` §A memuat 38; 13 lainnya salah digolongkan "berizin" oleh `inv_endpoints.py` karena pembantu bernama sama di berkas lain | `backend/routers/incentive_rates.py:56` (`create_rate`); `backend/routers/data_hygiene.py:14` (`hygiene_summary`); `backend/routers/lots.py:98` (`update_lot_settings`) | [dibaca] pencarian langsung pada HEAD |
| 6 | Asisten Tanya KN dibuka menurut daftar peran di pengaturan; margin dan nilai persediaan menurut dua daftar peran lain yang dicocokkan nama persis | `backend/routers/ai_analytics.py:19` (`_ai_user`); `backend/services/analytics_config.py:21` (`role_may`); `backend/config_catalog_ai.py:74` (`ai.enabled_roles`) | [dibaca]; penolakan "Asisten analitik belum dibuka untuk peran Anda" [dijalankan] `t2_analyze.py` |
| 7 | Templat laporan asisten ditawarkan menurut daftar `roles` per templat (34 templat) yang dicocokkan nama persis, sehingga peran kustom tidak pernah mendapat templat | `backend/services/ai_templates.py:26` (`for_role`); `backend/services/ai_templates.py:111` (`run`); `backend/services/ai_schedules.py:41` (`validate`) | [dibaca] |
| 8 | Kolom biaya dan HPP dibuang dari jawaban kecuali untuk peran `admin`/`manager` atau yang berdasar keduanya | `backend/core_utils.py:368` (`COST_SAFE_ROLES`); `backend/core_utils.py:371` (`strip_cost_fields`) | [dibaca] |
| 9 | Izin `marketing.approve` ada di matriks tetapi persetujuan konten diputuskan nama peran | `backend/services/marketing_service.py:208` (`APPROVE_ROLES`) | [dibaca] |
| 10 | Peran kustom baru menyalin izin peran dasarnya lalu menerapkan tingkat per modul; modul "Tidak ada" menghapus semua sumber daya modul itu | `backend/services/custom_role_service.py:218` (`apply_levels`); `backend/access_modules.py:239` (`apply_levels`) | [dibaca] |

## Perubahan

### Data

- `permission_settings.migrations_applied` (daftar teks; lahir di PR-T9) mendapat id `"prt2:gerbang-peran"` setelah
  migrasi di bawah berjalan.
- Tidak ada koleksi atau field lain.

**Migrasi sekali (K-47)** — fungsi baru `async def migrate_role_gates_to_permissions() -> None` di
`backend/bootstrap.py`, dipanggil di `run_bootstrap` sebelum `sync_permission_modules`. Bila id-nya sudah tercatat →
tidak melakukan apa pun. Selain itu, pada `matrix`:

1. **Peran bawaan**: tiap peran pada kolom "Penerima bawaan" tabel "Izin dan peran" menerima pasangannya, walau
   matriks peran itu sudah diubah Admin (hari ini ia lolos lewat nama). Untuk sumber daya `ai`, penerima dibaca dari
   nilai pengaturan yang sedang berlaku, bukan dari bawaan: `ai.view` → isi `ai.enabled_roles`; `ai.view_margin` → isi
   `ai.margin_roles`; `ai.view_stock_value` → isi `ai.stock_value_roles`.
2. **Peran kustom yang sudah ada**: untuk tiap baris tabel "Endpoint" dan "Gerbang di dalam handler" bertanda
   **N** (nama peran saja): peran kustom yang `base_role`-nya ada di daftar peran baris itu menerima pasangan
   penggantinya, apa pun tingkat modulnya. Untuk baris bertanda **P+N** (izin P ditambah nama peran): hanya bila peran
   kustom itu juga memegang izin P baris tersebut. `ai.view` juga diberikan ke peran kustom yang `base_role`-nya ada
   di `ai.enabled_roles` (begitulah `_ai_user` hari ini); `ai.view_margin`, `ai.view_stock_value`, dan `ai_template.*`
   tidak (hari ini dicocokkan nama persis).
3. Semua pasangan baru dicatat di `defaults_applied` supaya `sync_permission_modules` tidak memberikannya lagi setelah
   dicabut Admin; `custom_roles.levels` dihitung ulang; `pending_defaults` (PR-T9) untuk pasangan yang sama dihapus.
4. Catat id; tulis satu baris jejak audit `role_gates_migrated` berisi `{peran: {sumber daya: [aksi]}}` yang diberikan.

Peran kustom yang dibuat **setelah** migrasi tidak menerima apa pun dari langkah 2: ia mengikuti tingkat modulnya.

### Server

**1. Endpoint ber-`require_role` (51).** Baris pertama handler diganti `require_permission(request, <sumber daya>,
<aksi>)`. Tanda (+) = tidak ada di `LAMPIRAN_DAFTAR.md` §A. Semua baris bertanda **N** kecuali disebut lain.

| Metode | Jalur | Jangkar | Peran sekarang | Izin pengganti |
|---|---|---|---|---|
| POST | `/api/customers/{customer_id}/reassign` | `backend/routers/crm.py:71` (`reassign_customer`) | manager | `sales_force.assign` |
| POST | `/api/credit-overrides/{override_id}/decision` | `backend/routers/crm.py:141` (`decide_credit_override`) | manager | `credit_override.approve` |
| GET | `/api/sales/leaderboard` | `backend/routers/crm.py:267` (`get_leaderboard`) | manager | `sales_force.view` |
| GET | `/api/sales/incentive/gl-status` | `backend/routers/crm.py:309` (`get_incentive_gl_status`) | manager | `sales_force.view` |
| POST | `/api/sales/incentive/post-gl` | `backend/routers/crm.py:321` (`post_incentive_gl`) | manager | `sales_force.post` |
| POST | `/api/sales-targets` | `backend/routers/crm.py:369` (`create_target`) | manager | `sales_force.update` |
| POST | `/api/sales-incentives` | `backend/routers/crm.py:424` (`create_incentive`) | manager | `sales_force.update` |
| GET | `/api/incentive-rates` | `backend/routers/incentive_rates.py:44` (`list_rates`) | manager | `sales_force.view` |
| POST | `/api/incentive-rates` (+) | `backend/routers/incentive_rates.py:56` (`create_rate`) | manager | `sales_force.update` |
| PATCH | `/api/incentive-rates/{rate_id}` | `backend/routers/incentive_rates.py:78` (`update_rate`) | manager | `sales_force.update` |
| DELETE | `/api/incentive-rates/{rate_id}` | `backend/routers/incentive_rates.py:93` (`delete_rate`) | manager | `sales_force.delete` |
| GET | `/api/costing/wac` | `backend/routers/costing.py:17` (`list_wac`) | manager | `costing.view` |
| GET | `/api/costing/wac/{product_id}` | `backend/routers/costing.py:24` (`get_wac`) | manager | `costing.view` |
| GET | `/api/home/admin` | `backend/routers/home.py:57` (`home_admin`) | manager | `manager_home.view` |
| GET | `/api/home/manager` | `backend/routers/home.py:65` (`home_manager`) | manager | `manager_home.view` |
| GET | `/api/data-hygiene/summary` (+) | `backend/routers/data_hygiene.py:14` (`hygiene_summary`) | admin, manager | `system_tools.view` |
| GET | `/api/data-hygiene/log` | `backend/routers/data_hygiene.py:20` (`hygiene_log`) | admin, manager | `system_tools.view` |
| GET | `/api/data-hygiene/preview` (+) | `backend/routers/data_hygiene.py:39` (`hygiene_preview`) | admin, manager | `system_tools.view` |
| GET | `/api/data-hygiene/unverified-locations` | `backend/routers/data_hygiene.py:75` (`unverified_locations`) | admin, manager | `system_tools.view` |
| GET | `/api/turn-notifications/map` | `backend/routers/data_hygiene.py:69` (`turn_map`) | admin, manager | `system_tools.view` |
| POST | `/api/data-hygiene/location/{collection}/{doc_id}` | `backend/routers/data_hygiene.py:81` (`fix_location`) | admin, manager | `system_tools.update` |
| POST | `/api/notifications/generate` | `backend/routers/notifications.py:110` (`generate`) | manager | `system_tools.update` |
| POST | `/api/data-hygiene/run` | `backend/routers/data_hygiene.py:45` (`hygiene_run`) | admin | `system_tools.configure` |
| POST | `/api/data-hygiene/log/{log_id}/revert` | `backend/routers/data_hygiene.py:53` (`hygiene_revert`) | admin | `system_tools.configure` |
| POST | `/api/data-hygiene/{collection}/{doc_id}/unlock` | `backend/routers/data_hygiene.py:61` (`hygiene_unlock`) | admin | `system_tools.configure` |
| GET | `/api/saga-locks` | `backend/routers/saga_locks.py:23` (`list_saga_locks`) | admin | `system_tools.configure` |
| GET | `/api/saga-locks/{collection}/{doc_id}/inspect` | `backend/routers/saga_locks.py:80` (`inspect_saga_lock`) | admin | `system_tools.configure` |
| POST | `/api/saga-locks/{collection}/{doc_id}/release` | `backend/routers/saga_locks.py:91` (`release_saga_lock`) | admin | `system_tools.configure` |
| GET | `/api/ai/facts/status` | `backend/routers/ai_analytics.py:65` (`facts_status`) | admin, manager | `ai.manage` |
| GET | `/api/ai/snapshots/status` | `backend/routers/ai_analytics.py:390` (`snapshots_status`) | admin, manager | `ai.manage` |
| GET | `/api/ai/usage` | `backend/routers/ai_analytics.py:406` (`usage_summary`) | admin, manager | `ai.manage` |
| POST | `/api/ai/facts/rebuild` | `backend/routers/ai_analytics.py:72` (`facts_rebuild`) | admin | `ai.configure` |
| POST | `/api/ai/snapshots/run` | `backend/routers/ai_analytics.py:397` (`snapshots_run`) | admin | `ai.configure` |
| POST | `/api/rfid/devices` (+) | `backend/routers/rfid.py:418` (`post_device`) | admin | `rfid_device.configure` |
| PATCH | `/api/rfid/devices/{device_id}` (+) | `backend/routers/rfid.py:427` (`patch_device`) | admin | `rfid_device.configure` |
| DELETE | `/api/rfid/devices/{device_id}` | `backend/routers/rfid.py:436` (`del_device`) | admin | `rfid_device.configure` |
| POST | `/api/rfid/devices/seed-defaults` | `backend/routers/rfid.py:444` (`post_seed_devices`) | admin | `rfid_device.configure` |
| POST | `/api/rfid/devices/{device_id}/api-key` | `backend/routers/rfid.py:660` (`post_device_api_key`) | admin | `rfid_device.configure` |
| PUT | `/rfid/printers/{device_id}/profile` (+) | `backend/routers/rfid_printers.py:244` (`put_printer_profile`) | admin | `rfid_device.configure` |
| PUT | `/api/rfid/v2/ops/devices/{device_id}/config` (+) | `backend/routers/rfid_v2.py:126` (`put_config`) | admin (+ izin `wms` di pembantu) | `rfid_device.configure` (pembantu tetap) |
| PUT | `/api/rfid/v2/ops/devices/{device_id}/protocol` (+) | `backend/routers/rfid_v2_ops.py:110` (`put_protocol`) | admin (+ izin `wms`) | `rfid_device.configure` |
| POST | `/api/rfid/v2/ops/devices/{device_id}/gate-parameters` (+) | `backend/routers/rfid_v2_ops.py:126` (`post_gate_parameters`) | admin (+ izin `wms`) | `rfid_device.configure` |
| POST | `/api/rfid/v2/ops/devices/{device_id}/simulate` (+) | `backend/routers/rfid_v2_ops.py:141` (`simulate`) | admin (+ izin `wms`) | `rfid_device.configure` |
| POST | `/api/rfid/v2/ops/health/check` | `backend/routers/rfid_v2_ops.py:164` (`health_check`) | admin | `rfid_device.configure` |
| POST | `/api/handheld/devices` (+) | `backend/routers/handheld.py:307` (`create_device`) | admin | `rfid_device.configure` |
| POST | `/api/handheld/devices/{device_id}/rotate-key` | `backend/routers/handheld.py:316` (`rotate_key`) | admin | `rfid_device.configure` |
| POST | `/api/handheld/devices/{device_id}/enable` | `backend/routers/handheld.py:332` (`enable`) | admin | `rfid_device.configure` |
| PUT | `/api/handheld/devices/{device_id}/profile` | `backend/routers/handheld.py:340` (`set_profile`) | admin | `rfid_device.configure` |
| POST | `/api/handheld/devices/{device_id}/revoke` | `backend/routers/handheld.py:324` (`revoke`) | admin, warehouse_admin | `rfid_device.revoke` |
| PUT | `/api/lots/settings` (+) | `backend/routers/lots.py:98` (`update_lot_settings`) | manager | Boleh mengubah kunci `lot.enforcement_mode` menurut aturan Pusat Pengaturan |
| PUT | `/api/supplier-contracts/policy` (+) | `backend/routers/supplier_contracts.py:77` (`update_policy`) | admin, manager | Boleh mengubah kunci `makloon.contract_mode` menurut aturan Pusat Pengaturan |

Dua baris terakhir memanggil pemeriksa yang sama dengan `PUT /api/config/values` (`backend/routers/config.py:45`,
`_may_edit`, yang setelah KF-T1 hanya membaca izin) sehingga layar lama dan Pusat Pengaturan selalu sepakat; unit ini
tidak menetapkan izinnya. Pesan 403 keduanya: "Anda belum punya akses untuk mengubah pengaturan ini. Minta Admin
menambahkan akses 'Pengaturan'."

Pada berkas `rfid*.py` dan `handheld.py` yang diubah hanya baris gerbang izin di router; `services/rfid_*`,
`gate_evaluator`, dan `middleware/` tidak disentuh.

**2. Gerbang nama peran di dalam handler (wewenang).** **P+N** kecuali disebut lain.

| # | Jangkar | Gerbang sekarang | Pengganti |
|---|---|---|---|
| 1 | `backend/routers/internal_requests.py:41` (`_is_cross`), dipakai `backend/routers/internal_requests.py:112` (`request_sources`) | `internal_request.view` + admin, manager, sales_admin | `internal_request.convert` (izin lama; sama dengan `backend/routers/work_desks.py:75`, `_assert_may_choose_source`) |
| 2 | `backend/routers/rnd_org.py:21` (`_assert_appraisal`) — tiga rute `/api/rnd/divisions*` | `rnd.view` + admin, manager | `rnd.manage_org` (aksi baru) |
| 3 | `backend/routers/rnd.py:149` (`_assert_appraisal_role`) — rapor desainer dan papan SLA | `rnd.view` + admin, manager | `rnd.report` (aksi baru) |
| 4 | `backend/routers/ai_analytics.py:19` (`_ai_user`); `backend/services/ai_schedules.py:74` (`run_schedule`) | N: `ai.enabled_roles` | `ai.view` |
| 5 | `backend/routers/ai_assist.py:38` (`scan_insights`); `backend/services/ai_chat_service.py:85` (`can_edit_rules`); `backend/routers/ai_analytics.py:424` (`usage_daily`, melihat pemakaian semua orang) | admin, manager | `ai.manage` |
| 6 | `backend/services/analytics_config.py:21` (`role_may`) dan pemanggilnya `backend/services/analytics_engine.py:464` (`role_may`); `backend/services/ai_chat_service.py:100` (`margin_roles`) | N: `ai.margin_roles`, `ai.stock_value_roles` | `ai.view_margin`, `ai.view_stock_value` (`role_may` diganti `Scope.allowed`) |
| 7 | `backend/services/ai_templates.py:26` (`for_role`); `backend/services/ai_templates.py:111` (`run`); `backend/services/ai_schedules.py:41` (`validate`); `backend/routers/ai_analytics.py:262` (`post_narrative`) | N: `roles` per templat | `ai_template.<id templat>` |
| 8 | `backend/routers/ai_analytics.py:56` (`get_result`); `backend/routers/ai_analytics.py:255` (`_owned_results`); `backend/services/ai_actions.py:142` (`user_id`) — Admin membuka milik pengguna lain | N: `== "admin"` | `ai.configure` |
| 9 | `backend/routers/color_library.py:164` (`patch_color`) — mengubah pelanggan eksklusif warna | `color.update` + admin, manager | `color.approve` (izin lama) |
| 10 | `backend/routers/price_approvals.py:153` (`_ensure_owner_or_privileged`) — mengelola pengajuan orang lain | izin `price_approval` + admin, manager | `price_approval.approve` (izin lama) |
| 11 | `backend/routers/goods_receipts.py:116` (`grn_mode_switch`) | `goods_receipt.approve` + admin, manager | `goods_receipt.configure` (aksi baru) |
| 12 | `backend/routers/closing.py:74` (`close_period`, menembus blokir akun sementara); `backend/routers/closing.py:105` (`reopen_period`) | `accounting.manage` + admin | `accounting.reopen` (aksi baru) |
| 13 | `backend/routers/warehouses.py:283` (`STRUCTURE_ROLES`) | izin `warehouse` + admin, warehouse_admin | `warehouse.configure` (aksi baru) |
| 14 | `backend/routers/sample_orders.py:179` (`approve_payment`); bendera `backend/routers/sample_orders.py:157` (`can_pay`) | `sample_order.approve_payment` + finance, sample_admin, manager, admin | Gerbang nama dicabut; bendera = `has_permission` yang sama |
| 15 | `backend/services/master_usage_service.py:68` (`assert_lifecycle_role`); `backend/services/master_cleanup_validate.py:256` (`LIFECYCLE_ROLES`); `backend/services/master_cleanup_service.py:287` (`LIFECYCLE_ROLES`) | izin `product`/`color` + admin, md | `product.retire` (aksi baru) |
| 16 | `backend/services/rnd_sample_service.py:914` (`max_rounds`) — ronde di atas batas | izin `rnd` + admin, manager | `rnd.extend_rounds` (aksi baru) |
| 17 | `backend/services/inspection_service.py:1678` (`release_hold`); `backend/services/inspection_service.py:1719` (`reject_hold`); bendera `backend/routers/inspections.py:74` (`can_release_hold`) | izin `inspection` + admin, manager (atau `md_quality.decide` untuk jenisnya) | `inspection.release` (aksi baru) atau `md_quality.decide` seperti sekarang |
| 18 | `backend/routers/inspections.py:464` (`can_create`) | bendera layar: admin, manager | `has_permission(actor, "inspection", "create")` (sama dengan gerbang `POST /api/inspections`) |
| 19 | `backend/services/marketing_service.py:208` (`APPROVE_ROLES`) | izin `marketing` + admin, manager | `marketing.approve` (izin lama yang selama ini tidak diperiksa) |
| 20 | `backend/routers/marketing.py:377` (`delete_template`) — menghapus templat orang lain | `marketing.update` + admin, manager | `marketing.delete` (izin lama) |
| 21 | `backend/services/placement_rules.py:55` (`is_supervisor`); `backend/routers/wms.py:190` (`takeover_task`) | izin `wms`/`transfer` + warehouse_admin, manager, admin | `wms.approve` (izin lama) |
| 22 | `backend/services/return_cutloss_split_service.py:22` (`assert_can_choose`) | izin `sales_return` + admin, manager + isi `returns.cutloss_treatment_roles` | `sales_return.treat_cutloss` (aksi baru; penerima saat migrasi = admin, manager, dan isi pengaturan itu) |
| 23 | `backend/core_utils.py:371` (`strip_cost_fields`); `backend/routers/sales_returns.py:708` (`COST_SAFE_ROLES`); `backend/routers/finance_analytics.py:64` (`cost_ok`); `backend/services/export_engine.py:50` (`COST_SAFE_ROLES`) | N: admin, manager | `costing.view` |
| 24 | `backend/services/special_order_phase2.py:699` (`unlock_price`) | `order.update` + admin | `od_pricing.unlock` (aksi baru) |
| 25 | `backend/services/entity_lifecycle_service.py:315` (`archive_entity`, `force`) | izin `entity` + admin | `entity.delete` (izin lama) |
| 26 | `backend/routers/documents.py:401` (`_may_view`); `backend/routers/work_desks.py:207` (`has_permission`) | jalan pintas `== "admin"` sebelum cek izin | Jalan pintas dihapus (Admin memegang semua izin dan matriksnya terkunci) |
| 27 | `backend/routers/approvals_matrix.py:25` (`_assert_approver`) | tidak punya pemanggil | Fungsi dan `APPROVER_ROLES` dihapus |
| 28 | `backend/services/field_visibility.py:226` (`dispatch`) | izin `field_visibility.lot` | Tetap (bukan nama peran); teks pesan diganti di PR-T6 |
| 29 | `backend/routers/scheduler.py:84` (`digest_preview`) | memvalidasi parameter `role`, bukan pelaku | Tetap |

Aturan untuk titik yang tidak tercantum dan ditemukan saat mengerjakan (pencarian `role_in(`, `== "admin"`,
`in (… "admin" …)` di `backend/routers` dan `backend/services`): jalan pintas Admin di depan cek izin → dihapus;
"hanya Admin" → aksi `configure` pada sumber daya handler itu, penerima bawaan `admin`; daftar peran → aksi baru pada
sumber daya handler itu, penerima = daftar itu. Tiap tambahan dicatat di laporan beserta jangkarnya.

**3. Pembantu dan pembersihan**

- `COST_SAFE_ROLES` menjadi himpunan yang diisi ulang di tempat dari matriks (peran pemegang `costing.view`) oleh
  `custom_role_service.sync_registry`, pola yang sama dengan `CROSS_ENTITY_ROLES` (`backend/role_registry.py:280`).
  `strip_cost_fields(data, role)` memakai `role in COST_SAFE_ROLES`; tanda tangannya tetap, 37 pemanggil tidak berubah.
- Templat: `backend/permissions_config.py` memuat `backend/data/ai/templates_laporan_v1.json` saat impor dan
  membangun `DEFAULT_PERMISSIONS[peran]["ai_template"]` dari field `roles` tiap templat (Admin: semua id). Field
  `roles` tetap di JSON sebagai sumber nilai bawaan; kode asisten tidak lagi membacanya.
- Kunci `ai.enabled_roles`, `ai.margin_roles`, `ai.stock_value_roles` diberi status tidak dipakai di registry dengan
  alasan "Diatur di Peran & Hak Akses › Asisten Tanya KN" (cara yang sama dengan empat kunci tidak dipakai yang ada).
- Setelah semua pemanggil dialihkan: `require_role` dihapus dari `backend/dependencies.py`; konstanta daftar peran
  yang tidak lagi dibaca dihapus.

Pesan 403 mengikuti `require_permission` (teks manusianya dipetakan pusat di PR-T6).

### Pengaturan

Tidak ada kunci baru. Tiga kunci `ai.*_roles` dinonaktifkan (lihat di atas).

### Izin dan peran

| Sumber daya | Label | Aksi (label aksi baru) | Modul akses | Penerima bawaan |
|---|---|---|---|---|
| `sales_force` (baru) | Tim Sales: Target, Insentif & Penugasan | `view`, `update`, `delete`, `post` ("Catat akrual ke buku besar"), `assign` | modul baru `sales_force` | admin, manager |
| `credit_override` (baru) | Pengecualian Batas Kredit | `approve` | `sales_force` | admin, manager |
| `costing` (baru) | HPP & Margin Produk | `view` | modul baru `costing` | admin, manager |
| `manager_home` (baru) | Beranda Manajer | `view` | modul baru `manager_home` | admin, manager |
| `system_tools` (baru) | Kebersihan Data & Alat Sistem | `view`, `update`, `configure` | modul baru `system_tools` | admin: semua; manager: `view`, `update` |
| `rfid_device` (baru) | Perangkat RFID & Handheld | `configure`, `revoke` ("Cabut akses perangkat") | modul baru `devices` | admin: semua; warehouse_admin: `revoke` |
| `ai` (baru) | Asisten Tanya KN | `view`, `view_margin` ("Lihat margin & laba kotor"), `view_stock_value` ("Lihat nilai persediaan"), `manage`, `configure` | modul baru `assistant` | `view`: admin, manager, sales_admin, finance, md, warehouse_admin, sales · `view_margin`: admin, manager · `view_stock_value`: admin, manager, finance · `manage`: admin, manager · `configure`: admin |
| `ai_template` (baru) | Templat Laporan Tanya KN | satu aksi per templat, id = id templat, label = judul templat | `assistant` | menurut `roles` tiap templat; admin: semua |
| `rnd` | — | `manage_org`, `report`, `extend_rounds` ("Buka ronde di atas batas") | `rnd` | admin, manager |
| `goods_receipt` | — | `configure` | `warehouse_ops` | admin, manager |
| `warehouse` | — | `configure` | `warehouse_ops` | admin, warehouse_admin |
| `accounting` | — | `reopen` | `accounting` | admin |
| `inspection` | — | `release` | `inspection` | admin, manager |
| `product` | — | `retire` ("Nonaktifkan / hapus permanen master") | `product` | admin, md |
| `sales_return` | — | `treat_cutloss` ("Pilih potongan cacat: masuk BS atau dibuang") | `penjualan` | admin, manager, md, md_quality |
| `od_pricing` | — | `unlock` | `penjualan` | admin |

Modul baru di `backend/access_modules.py` (`MODULE_CATALOG`):

| id | Grup | Label | Menu (`nav`) | Sensitif |
|---|---|---|---|---|
| `sales_force` | Penjualan | Pengawasan Tim Sales & Kredit | `settings-hub`, `settings-sales`, `incentive-rates` | tidak |
| `costing` | Alat | HPP & Margin Produk | `costing`, `akuntansi`, `fin-reports`, `profitability` | ya |
| `manager_home` | Alat | Beranda Manajer | — | tidak |
| `system_tools` | Organisasi | Kebersihan Data & Alat Sistem | — | ya |
| `devices` | Gudang | Perangkat RFID & Handheld | `settings-hub`, `settings-system`, `settings-devices` | ya |
| `assistant` | Alat | Asisten Tanya KN | `tanya-kn` | tidak |

`VIEW_RESOURCE_OVERRIDES` ditambah `"costing": ["costing"]` dan `"incentive-rates": ["sales_force"]`, supaya menu itu
hanya tampil bagi pemegang izinnya. Label sumber daya masuk `RESOURCE_LABEL`, label aksi masuk `ACTION_LABEL`.

### Layar

Tidak ada layar baru. Enam modul dan aksi baru tampil di editor peran lewat `GET /api/access/modules`. Tombol yang
masih memakai nama peran di layar terkait (mis. tab "Persetujuan Kredit", "Pindah Sales") dialihkan di PR-T7.

## Uji penerimaan

Persiapan bersama: peran uji baku `02` §6 dibuat lewat API **setelah** proses awal (jadi setelah migrasi). `mgr` =
manajer seed; `adm` = admin seed. Berkas `backend/tests_mem/data/kode_sebelum_PRT2.json` dibuat pada langkah kerja 1,
sebelum kode diubah: kode jawaban 13 peran bawaan untuk semua rute GET di kedua tabel dan untuk POST tanpa efek
samping yang disebut U12.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | "Tanpa Acuan" + `costing.view` | `GET /api/costing/wac` oleh Tanpa Acuan, Manajer Kosong, Sopir | 200 · 403 · 403 |
| U2 | B | "Tanpa Acuan" + `manager_home.view` | `GET /api/home/manager` oleh ketiganya | 200 · 403 · 403 |
| U3 | B | "Tanpa Acuan" + `sales_force.view` | `GET /api/sales/leaderboard` dan `GET /api/incentive-rates` oleh ketiganya | 200, 200 · 403, 403 · 403, 403 |
| U4 | B | "Tanpa Acuan" + `sales_force.update`; id akun sales seed | `POST /api/sales-targets` dengan isi sah oleh Tanpa Acuan dan Manajer Kosong | 200 · 403; hanya satu dokumen `sales_targets` |
| U5 | B | "Tanpa Acuan" + `system_tools.view` | `GET /api/data-hygiene/summary`, `/log`, `/preview`, `/unverified-locations`, `/api/turn-notifications/map`; lalu `POST /api/data-hygiene/run` | lima kali 200; POST 403 (butuh `configure`) |
| U6 | B | "Tanpa Acuan" + `ai.view` | `GET /api/ai/status`, `GET /api/ai/usage` oleh Tanpa Acuan; `GET /api/ai/status` oleh Manajer Kosong dan Sopir | 200, 403 · 403 · 403 |
| U7 | B | "Tanpa Acuan" + `ai.view` + `ai_template.daily_brief` | `GET /api/ai/templates` | Daftar memuat tepat satu templat, `daily_brief` |
| U8 | B | "Tanpa Acuan" + `rnd.view` | `GET /api/rnd/divisions` sebelum dan sesudah ditambah `rnd.manage_org` | 403 → 200 |
| U9 | B | "Tanpa Acuan" + `rnd.view` + `rnd.report` | `GET /api/rnd/reports/designer-kpi`, `GET /api/rnd/sla/board` | 200, 200 |
| U10 | B | "Tanpa Acuan" + `rfid_device.revoke` | `POST /api/handheld/devices/x/revoke` dengan isi sah; `POST /api/handheld/devices/x/enable` | bukan 403 (404 perangkat tidak ada) · 403 |
| U11 | B | fixture sisip: peran kustom "Manajer Lama" (`base_role: "manager"`, `matrix` kosong) dan "Gudang Lama" (`base_role: "warehouse_admin"`, kosong); hapus id migrasi; nyalakan ulang | `GET /api/access/roles/{Manajer Lama}`; `GET /api/costing/wac` olehnya; `GET /api/access/roles/{Gudang Lama}` | "Manajer Lama" memegang semua pasangan baris **N** berperan manager (antara lain `costing.view`, `manager_home.view`, `sales_force.*`, `system_tools.view`, `system_tools.update`, `ai.view`) dan tidak memegang pasangan **P+N**; 200; "Gudang Lama" memegang `rfid_device.revoke` dan `ai.view` saja (Admin Gudang ada di `ai.enabled_roles` bawaan — koreksi: langkah migrasi 2 memberi `ai.view` ke peran kustom yang peran dasarnya ada di daftar itu) |
| U12 | B | berkas "sebelum" | Sapu ulang rute yang sama oleh 13 peran bawaan | Kode jawaban tiap (peran, rute) sama dengan berkas — termasuk Manajer: 200 di semua rute manager, 403 di `/api/saga-locks`, `POST /api/data-hygiene/run`, `POST /api/rfid/devices/seed-defaults` |
| U13 | B | `adm` mencabut `costing.view` dari Manajer; nyalakan ulang | `GET /api/costing/wac` oleh `mgr`; `GET /api/sales-orders` oleh `mgr`, periksa field biaya | 403; jawaban pesanan tanpa field biaya (`strip_cost_fields`) — pencabutan bertahan setelah start |
| U14 | B | nilai `ai.enabled_roles` diubah menjadi `["admin", "manager"]` **sebelum** migrasi (fixture), hapus id migrasi, nyalakan ulang | `GET /api/ai/status` oleh sales seed | 403 (migrasi membaca nilai pengaturan, bukan bawaan) |
| U15 | B | — | Cari pemanggilan `require_role(` di `backend/` di luar folder uji dan komentar | 0 pemanggilan; `from dependencies import require_role` gagal impor |
| U16 | B | "Tanpa Acuan" + `marketing.view` + `marketing.update` | Ubah status post ke `approved` sebelum dan sesudah ditambah `marketing.approve` | ditolak → berhasil |

Setelah unit selesai: `t3_escalation.py` baris (e1) dan (e2) menampilkan 403; `t2_analyze.py` bagian B tidak lagi
memuat `/api/rnd/*` dan `/api/internal-requests/{req_id}/sources`.

## Langkah kerja

**Serah-terima (a) — jalur baru, jalur lama belum disentuh**

1. Buat berkas "sebelum" (U12); tulis `backend/tests_mem/test_PRT2_gerbang_peran.py` (U1–U16). Merah: semua kecuali U12.
2. Katalog: `permissions_config.py`, `access_modules.py` (modul, label, `VIEW_RESOURCE_OVERRIDES`).
3. `migrate_role_gates_to_permissions` + pencatatan. Hijau: U11, U12, U14 (gerbang lama masih berjalan).

**Serah-terima (b) — pengalihan dan pematian jalur lama**

4. Tabel 1 per berkas router, satu commit per berkas; jalankan U12 setelah tiap berkas.
5. Tabel 2; `COST_SAFE_ROLES`; templat; tiga kunci `ai.*_roles` dinonaktifkan.
6. Hapus `require_role` dan konstanta mati. Hijau: U1–U10, U13, U15, U16.
7. Gate (`bash scripts/gate.sh --quick` dan penuh), `role_registry --self-test`, `verify_access_catalog_nav.py`; laporan
   memuat SHA (a) dan (b).

## Dokumen ikut berubah

`CODEBASE_MAP.md` (fungsi migrasi); `memory/PRD.md` (enam modul akses baru); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`
(label modul dan aksi baru).

## Di luar lingkup

- `role_in` bermakna cakupan data (35 titik) dan kueri `users.role` persis → PR-T4.
- `role_satisfies`, `required_approval_role`, dan daftar peran penyetuju: `backend/services/finance_case_service.py:409`,
  `backend/services/penalty_service.py:410`, `backend/services/payment_variance_service.py:624`,
  `backend/services/amendment_service.py:729`, `backend/services/cash_advance_service.py:247`,
  `backend/services/marketing_cost_service.py:220`, `backend/services/rnd_spec_service.py:343`,
  `backend/services/special_order_fulfillment.py:335`, `backend/services/approval_matrix_service.py:243` → KP-T4.
- Gerbang ubah dan baca Pusat Pengaturan (`backend/routers/config.py:59`, `backend/routers/config.py:104`) → KF-T1.
- Alat laporan laba rugi asisten (`backend/services/ai_tools.py:331`) → AG-T2 (asisten membaca keuangan lewat pintu
  aplikasi).
- Rekening tingkat grup dan pelanggan lintas PT bagi `admin`/`manager` (`backend/routers/bank.py:31`,
  `backend/routers/cash.py:48`, `backend/services/customer_service.py:412`) → PR-T6 (PR-UX-21).
- Endpoint yang hanya butuh login → PR-T3. Tombol layar → PR-T7. Penjaga matriks → PR-T8.

## Asumsi dan risiko

- `ASUMSI:` mengganti baris gerbang izin di `backend/routers/rfid*.py` dan `handheld.py` bukan "gerbang RFID" menurut
  `00` §6 H7. Bila berkas itu sedang diubah pihak lain, baris-baris itu ditandai `tahan` dan sisanya dilanjutkan.
- `ASUMSI:` 34 aksi `ai_template.*` (satu per templat) dapat diterima di "Atur rinci"; ini satu-satunya cara yang
  mempertahankan persis siapa mendapat templat apa hari ini tanpa keputusan baru per templat.
- `ASUMSI:` `credit_override.approve` cukup sampai unit CR-T3 membangun izin kredit; CR-T3 boleh mengganti namanya.
- `ASUMSI:` memakai izin lama yang lebih sempit dalam sumber daya yang sama (`internal_request.convert`,
  `color.approve`, `price_approval.approve`, `marketing.delete`, `wms.approve`, `entity.delete`) tidak mengubah siapa
  yang lolos pada matriks bawaan; peran kustom ber-P yang kehilangan jalan lewat nama menerima izin itu saat migrasi.
- `RISIKO:` peran yang hari ini lolos kehilangan akses karena satu baris terlewat. Penangkal: U12 menyapu semua rute
  tabel untuk 13 peran. Membatalkan (b): kembalikan commit per berkas router; izin baru dan migrasi (a) tidak perlu
  dicabut karena belum dibaca siapa pun.
- `RISIKO:` menu modul baru muncul pada peran kustom yang menerima izin lewat migrasi. Itu disengaja: aksesnya memang
  ada hari ini, kini terlihat dan bisa dicabut.

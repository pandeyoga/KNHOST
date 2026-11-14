# PR-T2 — Wewenang dari izin, bukan nama peran acuan

- Commit awal: sesudah `[PK-46]` (`ba0565c`)        - Serah-terima (a): `45a9d73`        - Serah-terima (b): `653e87e`
- Koreksi blueprint: `eaeeaf5`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PR-01, PR-03 (+ butir layar PR-UX-11: modul/aksi baru tampil di editor peran) — K-47

## Cek ulang "Keadaan sekarang"

Berlaku: `dependencies.py:93` (`require_role`), `role_registry.py:334`; Manajer Kosong (peran kustom berdasar Manajer,
semua modul "Tidak ada") lolos lewat nama peran — terbukti uji merah (200 di HPP, beranda manajer, papan peringkat, tarif,
asisten, target sales); `rnd_org.py:21`, `rnd.py:149`, `internal_requests.py:41`; 51 pemanggilan `require_role` di 15
berkas; baris 6–9 di tempatnya. Bergeser: butir 4 → `field_visibility.py:217`; butir 10 → `custom_role_service.py:273`
dan `access_modules.py:244`. `goods_receipt.configure` sudah ada sejak KF-T1 (tidak ada aksi baru).

Bukti merah: uji `tests_mem/test_PRT2_*.py` pada salinan berisi versi kode lama — U1–U11, U13–U16 dan dua uji tambahan
gagal karena sebab yang dimaksud (Manajer Kosong 200; sumber daya/aksi belum dikenal katalog; `require_role` masih ada;
"Hanya manager/admin…" walau `marketing.approve` dicentang); U12 lulus di kode lama (memang harus sama: kode jawaban 13
peran bawaan tidak berubah).

## Perubahan

### Serah-terima (a) `45a9d73` — jalur baru, gerbang lama belum disentuh

| Berkas | Isi |
|---|---|
| `backend/permissions_config.py` | `PRT2_RESOURCES`/`PRT2_ACTIONS` (penjualan tim, izin kredit, biaya pokok, beranda manajer, alat sistem, perangkat RFID, asisten), `AI_TEMPLATES`/`AI_TEMPLATE_IDS` + izin `ai_template.<id>` dari JSON |
| `backend/access_modules.py` | Enam modul baru (Pengawasan Tim Sales & Kredit, HPP & Margin Produk, Beranda Manajer, Kebersihan Data & Alat Sistem, Perangkat RFID & Handheld, Asisten Tanya KN), label sumber daya/aksi, `VIEW_RESOURCE_OVERRIDES` untuk `costing` dan `incentive-rates` |
| `backend/bootstrap.py` | `migrate_role_gates_to_permissions` (id `PRT2_MIGRATION_ID`, sekali jalan, sesudah `ensure_permission_ledger`): pasangan pengganti diberikan kepada yang hari ini lolos lewat nama peran (`PRT2_NAME_GATES`, `PRT2_PERM_NAME_GATES`, `_prt2_default_pairs`) |
| Uji | `tests_mem/test_PRT2_migrasi.py`, `test_PRT2_sapuan.py`, `data/kode_sebelum_PRT2.json` (dibuat dari kode sebelum perubahan); `test_PRT9_izin_bawaan.py` (migrasi 16, tambahan PR-T2); fixture akses frontend dibangkitkan ulang |

Keadaan (a) saja: `tests_mem` 300 lulus / 2 dilewati (H4 PK-46) / 3 diharapkan gagal; `test_fe03_access_catalog` 6;
jest `src/config` 88/88.

### Serah-terima (b) `653e87e` — pengalihan pemanggil, jalur lama dimatikan (73 berkas)

- **Tabel 1 (51 gerbang)** → `require_permission(...)` dengan izin pengganti spesifikasi; `PUT /lots/settings` dan
  `PUT /supplier-contracts/policy` memakai `routers/config.require_setting_edit` (= `_may_edit` Pusat Pengaturan).
- **Tabel 2 baris 1–27** → izin (`assert_lifecycle_role` + `may_retire`, `placement_rules.is_supervisor`/
  `assert_supervisor`/`check_override`, `_ensure_owner_or_privileged`, `_assert_appraisal*` kini async).
- **Templat asisten**: `ai_templates.allowed_ids(user)`/`available(allowed)` menggantikan `for_role` (`suggest`, `route`,
  `ai_schedules.validate`).
- **Kolom biaya**: `COST_SAFE_ROLES` diisi ulang dari pemegang `costing.view` oleh `sync_registry`;
  `PUT /api/permissions` memanggil `sync_registry`.
- **Kunci tidak dipakai**: `ai.enabled_roles`, `ai.margin_roles`, `ai.stock_value_roles` (dan `returns.cutloss_treatment_roles`,
  lihat Menyimpang) berstatus `not_used` "Diatur di Peran & Hak Akses".
- **Dihapus**: `require_role`, `AI_ROLES`, `APPRAISAL_ROLES` ×2, `STRUCTURE_ROLES`, `SAMPLE_PAYMENT_APPROVERS`,
  `LIFECYCLE_ROLES`, `HOLD_RELEASE_ROLES`, `APPROVE_ROLES`, `SUPERVISOR_ROLES` (penempatan), `ROLES_KEY`, `role_may`,
  `COST_SAFE_DEFAULT`, `_assert_approver`/`APPROVER_ROLES`.
- **Titik tambahan** (aturan "titik tidak tercantum"): `ai_analytics` `get_session`/`_own_schedule`/`get_schedule_run`
  (`== "admin"` → `ai.configure`); `special_orders.py:1012` → `od_pricing.unlock`.
- `scripts/guardrails/verify_scope_guard.py`: pola `require_role\(` diganti penerusnya
  `require_permission\(request, "rfid_device"` (tanpa ini 4 endpoint perangkat merah palsu).
- Uji/dokumen: `tests_mem/test_PRT2_gerbang.py`; `test_KFT1_izin_pengaturan.py` U02 232 → 229 (tiga kunci `ai.*_roles`
  kini tidak dipakai); uji lapis A `tests/test_bp_PRT2_gerbang_peran.py`; `tests/test_tanya_kn_streaming_costpage.py`
  memakai pencabutan `ai.view` (menulis `ai.enabled_roles` kini ditolak); `memory/PRD.md`; glosarium;
  `CODEBASE_MAP.md` dihasilkan ulang.

### Koreksi blueprint `eaeeaf5`

U11: peran kustom "Gudang Lama" (`base_role: warehouse_admin`) juga memegang `ai.view`, karena Admin Gudang ada di
`ai.enabled_roles` bawaan dan langkah migrasi 2 memberinya. Harapan U11 di berkas unit dikoreksi; uji memakai harapan
yang benar.

## Uji penerimaan

| ID | Lapis | Hasil |
|---|---|---|
| U1, U2, U3, U6 | B | Lulus — Tanpa Acuan ber-izin 200; Manajer Kosong 403; Sopir 403 (kode lama: Manajer Kosong 200) |
| U4 | B | Lulus — Manajer Kosong POST 403 (kode lama 200) |
| U5, U7, U9, U10 | B | Lulus — sumber daya/aksi baru dikenal katalog dan berlaku |
| U8 | B | Lulus — aksi `manage_org` |
| U11 | B | Lulus (dengan koreksi blueprint) — "Manajer Lama"/"Gudang Lama" menerima pasangan pengganti lewat migrasi |
| U12 | B | Lulus — kode jawaban 13 peran bawaan untuk semua rute di kedua tabel sama dengan sebelum unit |
| U13 | B | Lulus — manajer 403 setelah `costing` dicabut (kode lama 200) |
| U14 | B | Lulus |
| U15 | B | Lulus — `require_role` tidak ada lagi |
| U16 | B | Lulus — pemegang `marketing.approve` bisa menyetujui (kode lama "Hanya manager/admin…") |
| Tambahan | B | Lulus — kunci pengaturan Tabel 1 (kebijakan makloon: Manajer Kosong 403); contoh baris P+N (`internal_request.convert`) |
| Lapis A | A | `tests/test_bp_PRT2_gerbang_peran.py` di MongoDB asli: 3 lulus, 1 dilewati (data acuan tanpa peran kustom beracuan Manajer yang ada sebelum PR-T2) |

`backend/tests_mem` seluruhnya (sesudah digabung dengan PK-45/PK-46): 315 lulus, 2 dilewati (H4), 3 diharapkan gagal.
Katalog modul lewat API: 37 modul, enam modul baru tampil (editor peran). `role_registry.py --self-test`: 13 peran.
Penjaga: `verify_auth_coverage` 28 → 28 (daftar identik); `verify_access_catalog_nav` 0; `verify_scope_guard`,
`verify_role_label`, `verify_escape_layers`, `verify_view_aliases`, `verify_notification_audience`,
`verify_money_idempotency`, `verify_custom_modals`, `verify_codebase_map` hijau.

Skrip arsip `docs/audit/konfigurasi-peran-2026-11-13/bukti/t3_escalation.py` tidak sampai ke baris (e1)/(e2): berhenti
lebih awal (`IndexError`: daftar kunci yang bisa diubah manajer kosong — perilaku sejak KF-T1). Skrip arsip tidak diubah;
padanan e1/e2 diuji U1–U3/U6 dan lapis A. `t2_analyze.py` bagian B: belum dijalankan.

## Gate

Dijalankan pada keadaan (a)+(b) (`eaeeaf5`), sesudah kontainer dinyalakan ulang (MongoDB dan backend dihidupkan kembali,
data acuan dipulihkan; penjalan seed yang gagal saat pemulihan sama dengan sebelum unit).

| Gate | FAIL | Garis dasar | Lebih merah |
|---|---|---|---|
| `--quick` | 16 | 16 | 0 |
| `--ci` | 43 | 43 | 0 |

Gate `--ci` ini juga mengonfirmasi POC FASE E-4 hijau sesudah perbaikan PK-46 (`04df310`).

## Menyimpang dari blueprint

1. **Baris P+N untuk peran bawaan** diberikan hanya bila peran itu memegang izin P (seperti peran kustom), bukan "tanpa
   syarat": hari ini peran tanpa P memang tidak lolos, dan tanpa syarat itu menu modul yang sudah dicabut Admin akan
   muncul lagi. Di database baru hasilnya identik.
2. **Bawaan `ai_template`** hanya untuk peran ber-`ai.view` (Gudang tidak menerima enam templat dari JSON karena hari ini
   tidak bisa membuka asisten); migrasi tetap memberi templat ke peran bawaan yang menerima `ai.view` dari nilai
   pengaturan — tidak ada yang kehilangan akses.
3. **Peran kustom dicocokkan nama persis** seperti hari ini: baris 20 (hapus templat marketing orang lain) tidak memberi
   `marketing.delete` ke peran kustom; `ai.view_margin`/`ai.view_stock_value` diberikan ke peran kustom yang id-nya
   tercantum persis di daftar pengaturannya.
4. **`returns.cutloss_treatment_roles` ikut `not_used`** (aturan L5; tidak disebut spesifikasi) — nilai global dan per-PT
   dibaca sekali oleh migrasi.
5. **Bentuk respons berubah**: `/api/ai/status` memakai `can_view_margin`/`can_view_stock_value` (layar tidak memakai field
   lama); `hold_release_roles` dibuang dari meta inspeksi.
6. Pesan 403 gerbang Tabel 1 = pesan bawaan `require_permission`; gerbang di dalam handler yang dulu berpesan nama peran
   diberi kalimat bentuk Z6.
7. `CODEBASE_MAP.md` (generator) tidak mendaftar fungsi `bootstrap`.

## Yang perlu direview

- Migrasi berjalan otomatis saat server mulai (preseden PR-T9); memasang di data nyata = H3.
- Hanya baris gerbang di `rfid*.py`/`handheld.py` yang diubah (asumsi spesifikasi, H7); `services/rfid_*` dan
  `middleware/` tidak disentuh.
- Titik yang ditemukan tetapi milik unit lain (tidak diubah): `design_gallery_service.py:620` (PR-T6/PR-T7),
  `ai_insights.py:138` (PR-T4), `routers/settings.py`/`config.py` (KF-T1), `access_roles`/`admin.py` (PR-T1),
  `bank`/`cash`/`customer_service` (PR-T6), `role_satisfies` dan daftar penyetuju (KP-T4), `ai_tools:331` (AG-T2),
  `scheduler:84`, cakupan data `role_in` (PR-T4), `location_scope.is_supervisor` dan bendera `internal_requests` (PR-T7).
- `COST_SAFE_ROLES` disimpan per proses (pola `CROSS_ENTITY_ROLES`); pada multi-worker, worker lain ikut berubah saat
  `sync_registry` berikutnya.
- Editor peran: modul "Asisten Tanya KN" untuk peran pemegang templat tampil "Kelola penuh (sebagian)" (konsekuensi satu
  aksi per templat).

Status: implemented_pending_review.

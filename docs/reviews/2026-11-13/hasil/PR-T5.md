# PR-T5 — Katalog izin dirapikan; modul akses dipecah

- Commit awal: `d0c92d3` (dikerjakan) · digabung di atas `cb49f7c` (sesudah KF-T5, KF-T3, KP-T1)        - Commit akhir: `b8bd0a2` · perbaikan sesudah gate `311c8f3` · koreksi blueprint `4999b2e`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PR-07, PR-08 (beserta butir layar PR-UX-12, PR-UX-13, PR-UX-14, PR-UX-15, PR-UX-16, PR-UX-18, PR-UX-28,
  PR-UX-30 — tidak punya baris sendiri di TRACKER) — K-47, K-50

## Cek ulang "Keadaan sekarang" (di `d0c92d3`)

| # | Hasil |
|---|---|
| 1 | Bergeser (PR-T2, PR-T3, KP-T4 sudah masuk). Matriks bawaan **449 pasangan pada 87 sumber daya** (spesifikasi: 381/79 — PR-T2 menambah 8 sumber daya dan 34 aksi templat `ai_template.*`). Tanpa pemeriksa literal: **39** + 34 `ai_template.*` (diperiksa dinamis `routers/ai_analytics.py:270`). Dibanding 42 di tabel 1: `marketing.approve` (PR-T2), `purchase_order.approve` (KP-T4, tupel di `routers/marketing.py`/`approval_backlog_service.py`) dan `od_fulfillment.choose_route` (`routers/special_orders.py:778`, PR-T3) kini literal; `purchase_order.reject`, `vendor_bill.reject`, `landed_cost.approve`, `landed_cost.reject` diperiksa lewat katalog persetujuan KP-T4 (`approval_kinds.py` → `approval_policy_service.assert_can_decide`). Jangkar dinamis berlaku: `goods_receipts.py:23` (`_act`), `rnd.py:115` (`_require_typed`), `field_visibility.py:45`, `special_order_fulfillment.py:214`, `sales_return_exceptions.py:234/243`, `gl.py:169`; amandemen bergeser ke `routers/amendments.py:172` (`approval_permission`) + `services/amendment_service.py:669` (`PRICE_EDIT_PERMISSION`) |
| 2 | Berlaku. `InventoryStockView.jsx:374` (`inventory.create`); `inventory.py:633-636` (`product.create`) |
| 3 | Berlaku. `reporting.py:290` (summary), `:187` (top-customers), `:31` (stock-aging, `product.view`), `:221` (warehouse-utilization, `warehouse.view`); `reports.view` tidak diperiksa di mana pun |
| 4 | Berlaku, bergeser: `access_modules.py:230` (`admin`) |
| 5 | Berlaku, bergeser: `access_modules.py:201` (`sales_profile`); `field_visibility.py:45-52`; `permissions_config.py:689` (`EXTRA_ACTIONS`) |
| 6 | Berlaku, bergeser: `apply_levels` `:272`; modul `field_visibility` `:197` |
| 7 | Berlaku, bergeser: `level_of` `:254`; `RoleModuleRow.jsx:52`; `RoleAccessPanel.jsx:43` |
| 8 | Berlaku, bergeser: `RESOURCE_LABEL` `:308`, `ACTION_LABEL` `:343`; `auditLabels.js:4` |
| 9 | Sebagian: kini **empat** modul bertanda sensitif (`costing`, `system_tools`, `devices` dari PR-T2 + `admin`), tetap per modul, bukan per aksi |
| 10 | Berlaku, bergeser: `hubTabs.js:36` (`customers-master`), `:263` (`settings-receiving-ocr`); `all_nav_ids` `:470`. `tanya-kn` dan `incentive-rates` sudah bermodul (PR-T2) |
| 11 | Berlaku, bergeser: `VIEW_RESOURCE_OVERRIDES` `:427`; `roles.js:365` (`accessBlocks`) |

Berkas "sebelum": `backend/tests_mem/data/kode_sebelum_PRT5.json` — dibuat dari kode `d0c92d3` sebelum perubahan apa pun
(`KN_PRT5_TULIS_SEBELUM=1 python -m pytest tests_mem/test_PRT5_sapuan.py`), 13 peran bawaan × 15 rute.

## PR-07 — Izin yang tidak diperiksa server
- Berlaku di HEAD: ya (butir 1–3).
- Akar masalah: katalog izin tumbuh tanpa syarat "harus ada pemeriksa"; layar laporan & inspeksi memakai izin modul lain.
- Perubahan perilaku (sebelum → sesudah):
  - 14 pasangan dihapus (`PRT5_REMOVED_PAIRS`: `esign.manage`, `finance_case.admin`, `interco.update`,
    `inventory.create`, `order|tax_invoice|template.print`, `template|uom.import|export`, `transfer.complete`,
    `reports.export`, `sales_pov.commercial` + sumber daya `sales_pov`). `PATCH` berisi `order: ["view","print"]` →
    400 "Aksi ['print'] tidak berlaku untuk “Pesanan Penjualan (SO)”.".
  - Migrasi sekali `prt5:katalog` (`custom_role_service.migrate_prt5_catalog`, dipanggil `run_bootstrap` sesudah migrasi
    PR-T4, sebelum `sync_permission_modules`): pasangan itu dibuang dari `matrix` semua peran, `defaults_applied`,
    `custom_roles.pending_defaults`; `custom_roles.levels` dihitung ulang dengan id modul baru; jejak audit
    `role_catalog_cleaned` bila ada yang dibuang. Tidak ada izin ditambahkan.
  - `GET /api/reports/summary|warehouse-utilization|stock-aging|top-customers` → `reports.view` sebagai pernyataan
    pertama (cakupan kepemilikan sales tetap). `reservation-funnel`/`order-velocity` tetap `order.view`.
  - Empat endpoint baca inspeksi (`meta`, daftar, unduhan, detail) → `require_any_permission` atas `inspection.view`,
    `md_quality.view`, `qc.view`.
  - Tombol "Tambah Stok" → `can(…, "product", "create")` (izin yang diperiksa endpoint-nya).
  - Penjaga baru INV-PERM-01 `scripts/guardrails/verify_permission_checked.py` (+ `--self-test`, 12 kasus), dipasang di
    `gate.sh` (daftar statik). Golongan: literal (AST, tanpa komentar; `permissions_config.py`, `access_modules.py`,
    `bootstrap.py`, berkas uji tidak dihitung) · katalog persetujuan (`approval_kinds`) · `DINAMIS` (19 pasangan +
    `ai_template.*`, tiap entri ber-berkas pemeriksa + penanda teks; entri yang ternyata literal = merah) ·
    `MENUNGGU_KPT4` (kosong, wajib kosong). Juga: tiap sumber daya tepat satu modul & berlabel, tiap aksi berlabel, tiap
    pasangan `SENSITIVE_ACTIONS` ada di katalog. Sesudah unit: 435 pasangan / 86 sumber daya = 378 literal + 5 katalog
    persetujuan + 52 dinamis (`bukti/PR-T5/pasangan_izin_per_pemeriksa.txt`).
- Fixture disiapkan langsung vs proses bisnis: U4 menyisipkan peran kustom + garis dasar lama langsung ke basis data
  (fixture), lalu menjalankan `run_bootstrap` (alur); sisanya lewat API.

## PR-08 — Modul "Pengaturan, Pengguna & Hak Akses" dan tombol tingkat
- Berlaku di HEAD: ya (butir 4–11).
- Perubahan perilaku (sebelum → sesudah):
  - Modul `admin` → `accounts` (Akun Pengguna), `roles` (Peran & Hak Akses), `entities` (Badan Usaha (PT)), `settings`
    (Pusat Pengaturan), `scheduler` (Penjadwal & Notifikasi Otomatis); empat pertama sensitif. `MODULE_ALIASES`:
    `{"admin": …}` diterima `apply_levels`/`nav_for_levels`, jawaban memakai id baru. `pdf-templates`,
    `settings-documents` → modul Dokumen. Modul `sales_profile` dihapus; `field_visibility` → grup Gudang, label
    "Melihat grade, nomor lot & asal barang".
  - `public_catalog()` + `levels_available`, `view_excludes`, `sensitive_actions`; `level_of` + `held`/`total`;
    `LEVEL_LABEL["manage"]` = "Semua aksi". Tingkat di luar `levels_available` → 400 "Tingkat “{tingkat}” tidak berlaku
    untuk modul “{modul}”." (`check_levels`, dipanggil `_clean_levels`; `apply_levels` juga menolak).
  - `SENSITIVE_ACTIONS` (39 pasangan, 13 kalimat tabel spesifikasi).
  - Menu di luar katalog → modul (tabel "Menu di luar katalog"); `VIEW_ACTION_REQUIREMENTS` dikirim sebagai
    `view_actions` di `GET /api/auth/me` dan jawaban login; `roles.accessBlocks` menyembunyikan menu bila tidak ada
    pasangan yang dipegang; `nav_allowed_for_perms` (pratinjau `screens`, relevansi notifikasi) ikut aturan yang sama.
    `home`/`my-desk` peran kustom: dari sifat peran (`role_registry.apply_traits` menulis overlay `nav`).
  - `GET /api/access/labels` (login; `LOGIN_ONLY` + 1) = `{resources, actions, modules}`. Layar:
    `auditLabels.setServerLabels` diisi saat sesi dimuat (`useSessionSync`); `moduleLabel`/`actionLabel(aksi,
    sumber daya)` dan penerjemah pesan 403 (`apiError`) membaca kamus server; peta setempat tinggal 11 kunci bukan sumber
    daya izin; `ACTION_LABEL` setempat kosong. Label server yang belum ada ditambah: `marketing` "Pemasaran", aksi
    `count` "Hitung", `review` "Tinjau", `close` "Tutup", `set` "Atur".
  - Pesan Z6 yang menyebut modul lama kini menyebut modul pemilik izinnya ('Pusat Pengaturan' / 'Badan Usaha (PT)'):
    `routers/config.py`, `settings.py`, `kontrol.py`, `approval_policies.py`, `approval_rules.py`, `entities.py`,
    `services/entity_lifecycle_service.py`.
  - Editor peran: tombol **Tidak ada · Lihat saja · Semua aksi** sesuai `levels_available` (sakelar **Mati · Nyala**);
    `partial` → tidak ada tombol menyala + lencana "Sebagian ({held} dari {total} aksi)"; "Tidak termasuk pada Lihat saja:
    …"; dialog simpan: "{halaman}: +aksi, +aksi · −aksi" per modul dan "Perhatian — peran ini akan bisa: …; …."
    (menggantikan kalimat modul sensitif lama); "Atur rinci": ikon peringatan + petunjuk "Peran ini bisa …."; kartu
    peran "{n} semua aksi · {n} sebagian · {n} lihat · {n} tidak ada"; ringkasan editor empat keadaan; "Semua modul: …"
    melewati modul yang tidak punya tingkat itu; baris bertanda "diubah" juga bila hanya aksi rincinya berubah.

## Berkas berubah

| Berkas | Isi |
|---|---|
| `backend/permissions_config.py` | Blok `PR-T5`: `PRT5_REMOVED_PAIRS`, `PRT5_REMOVED_RESOURCES`, pembuangan dari `DEFAULT_PERMISSIONS`/`EXTRA_ACTIONS` |
| `backend/access_modules.py` | Lima modul, `MODULE_ALIASES`, blok `_PRT5_NAV`, `expand_aliases`, `levels_available`, `view_excludes`, `check_levels`, `level_of` (+held/total), `SENSITIVE_ACTIONS`, `sensitive_actions_of`, `VIEW_ACTION_REQUIREMENTS`, `view_actions_index`, `labels_dictionary`, `module_label_of`; label baru; `sales_pov`/`commercial` dihapus |
| `backend/services/custom_role_service.py` | `_clean_levels` → `check_levels` (400); `migrate_prt5_catalog` |
| `backend/bootstrap.py` | Dua baris panggilan migrasi |
| `backend/routers/access_roles.py`, `backend/login_only_endpoints.py` | `GET /api/access/labels`; daftar login-saja |
| `backend/routers/reporting.py`, `backend/routers/inspections.py`, `backend/routers/auth.py` | Gerbang `reports.view`; `_VIEW_ANY`; `view_actions` |
| `backend/role_registry.py` | `home`/`my-desk` peran kustom menurut sifat peran |
| `backend/routers/{config,settings,kontrol,approval_policies,approval_rules,entities}.py`, `backend/services/entity_lifecycle_service.py`, `backend/services/field_visibility.py` | Nama modul di pesan Z6; docstring janji POV dihapus |
| `frontend/src/features/settings/entities/{RoleModuleRow,RoleEditorDrawer,RoleAdvancedPanel,RoleAccessPanel,RoleRealityPanel}.jsx`, `roleAccessUtil.js` | Editor peran (di atas) |
| `frontend/src/config/auditLabels.js`, `utils/apiError.js`, `hooks/useSessionSync.js`, `hooks/useAppActions.js`, `config/roles.js`, `features/wms/InventoryStockView.jsx` | Kamus server, `view_actions`, tombol Tambah Stok |
| `scripts/guardrails/verify_permission_checked.py` (baru), `scripts/gate.sh` | INV-PERM-01 + self-test di daftar statik |
| Uji baru | `backend/tests_mem/test_PRT5_katalog.py` (U1–U13 + U9b, U13b), `test_PRT5_sapuan.py` (U14) + `data/kode_sebelum_PRT5.json`; jest `frontend/src/features/__tests__/prt5EditorPeran.test.js`; lapis A `backend/tests/test_bp_PRT5_katalog.py` (lulus di MongoDB asli) |
| Uji lama disesuaikan (disengaja) | `test_PRT9_izin_bawaan.py` (`DICABUT_SESUDAH` dari `PRT5_REMOVED_PAIRS`, `JUMLAH_MIGRASI` 18 → 19); `test_PRT3_login_saja.py` (53 + 1); `test_KFT1_izin_pengaturan.py` (nama modul 'Pusat Pengaturan'); `test_KPT4b_pengalihan.py` U7 (tingkat tertinggi yang berlaku, bukan "manage" untuk semua modul); jest `navAccess.test.js` (cr_settings_admin tanpa Template Dokumen & Perangkat; cr_warehouse_ops + `settings-receiving-ocr`), `serverAccessReach.test.js` (+`view_actions`), `g0SharedApi.test.js` (pesan 403 memakai label server); lapis A `tests/test_tanya_kn_f0_access.py` dan POC gate `backend/test_core_e8_desk_poc.py` (Sales kini 403 pada laporan) |
| Fixture | `tests/fe03_access_fixture.py` (+`view_actions`), `access_nav_fixture.json`, `access_builtin_fixture.json` dibangkitkan ulang |
| Dokumen | `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.1 (tingkat, Sebagian, aksi berisiko, lima modul), `docs/KN_13_NAVIGATION_MAP.md` (changelog pemilik menu/tab), `memory/PRD.md`, `CODEBASE_MAP.md` (generator) |

## Uji penerimaan

Merah di kode lama: berkas uji final dijalankan pada salinan `git archive d0c92d3` (`bukti/PR-T5/merah_kode_lama.log`)
→ **16 dari 16 gagal** dengan sebab masalahnya. Hijau: `bukti/PR-T5/hijau_kode_baru.log` (16 lulus).

| ID | Lapis | Merah di lama | Hasil |
|---|---|---|---|
| U1 | B | ya (`admin`, `sales_profile` ada) | Lulus — lima modul baru; tiap sumber daya tepat satu modul; `sales_pov` tidak ada |
| U2 | B | ya (`[403,403,403]`: `accounts` tak dikenal) | Lulus — 200 · 403 · 403 |
| U3 | B | ya (`levels` ber-id `admin`) | Lulus — 200; izin `user`/`permission`/`settings`/`entity`/`scheduler`; `levels` lima id baru |
| U4 | B | ya (`order` tetap memuat `print`) | Lulus — tiga pasangan hilang, izin lain utuh; `defaults_applied` & `pending_defaults` bersih; `levels` dihitung ulang; id tercatat |
| U5 | B | ya (200) | Lulus — 400 kalimat persis spesifikasi |
| U6 | B | ya (`[403,403,403]`) | Lulus — 200 · 403 · 403 |
| U7 | B | ya (`[200,200]`) | Lulus — 403 · 200 |
| U8 | B | ya (403 `inspection.view`) | Lulus — 200 |
| U9 | B | ya (200) | Lulus — 400 "Tingkat “Lihat saja” tidak berlaku…" · 400 "Tingkat “Semua aksi” tidak berlaku…" |
| U9b | B | ya | Lulus — `levels_available`, `view_excludes`, `sensitive_actions`, label "Semua aksi", grup/label `field_visibility`, sensitif lima modul, `pdf-templates` di modul Dokumen |
| U10 | B | ya (`held` tidak ada) | Lulus — `penjualan` Sales: manage, partial, held 11 < total 41 |
| U11 | B | ya (404) | Lulus — Sopir 200; `permission` = "Peran & Hak Akses"; semua sumber daya & aksi `DEFAULT_PERMISSIONS` berlabel; `modules.user` = "Akun Pengguna" |
| U12 | B | ya (penjaga belum ada; dijalankan pada kode lama: **21 pelanggaran** — 16 pasangan + 5 label, `bukti/PR-T5/penjaga_INV-PERM-01_kode_lama.log`) | Lulus — keluar 0 (580 cek); `--self-test` 12/12 (sisipan pasangan tanpa pemeriksa memerah) |
| U13 | B | ya (`view_actions` tidak ada) | Lulus — `view_actions["sales-admin-desk"] = [["order","confirm"]]`; menu itu terblokir menurut aturan `accessBlocks` dan tidak ada di `screens` pratinjau, `sales-orders` ada |
| U13b | B | ya | Lulus — peran kustom tanpa acuan: `home`/`my-desk` di `remove`; turunan Manajer: di `add` |
| U14 | B | ya (tidak ada selisih) | Lulus — Admin & Manajer sama di 15 rute; selisih hanya empat endpoint laporan: 200 → 403 keempatnya bagi Sales, Gudang, MD, Admin Gudang, Admin Sample; `stock-aging` + `warehouse-utilization` bagi MD Quality dan QC; `stock-aging` bagi Desainer; **403 → 200 Finance pada `warehouse-utilization`** (lihat Menyimpang 1). Rute lain (inspeksi, akun, peran, PT, penjadwal, registri pengaturan) tidak berubah untuk 13 peran |
| U15 | layar | ya (jest pada `frontend/src` lama: 9/9 gagal, `bukti/PR-T5/jest_merah_kode_lama.log`) | Uji komponen `prt5EditorPeran.test.js` 9/9 lulus: lencana "Sebagian (2 dari 6 aksi)" tanpa tombol menyala, modul sakelar Mati/Nyala, modul hanya-lihat tanpa "Semua aksi", "Semua aksi" → simpan → "+Ubah, +Kirim tanpa lunas" dan "Perhatian — peran ini akan bisa: …", ikon aksi berisiko, kartu peran, kamus label, `view_actions`. **Uji jalan peramban belum dijalankan** (dev server tidak dinyalakan di sesi ini) |
| §3.2-4 | B | — | `reports.view`/`md_quality.view`: Tanpa Acuan berizin 200; Manajer Kosong 403 (U6) |
| Lapis A | A | — | `backend/tests/test_bp_PRT5_katalog.py` (migrasi sekali & matriks bersih di MongoDB asli, katalog & kamus label, Ringkasan Sales 403): **lulus** di lingkungan A (backend `b8bd0a2`, data acuan), bersama `test_tanya_kn_f0_access.py` dan lapis A PR-T3/PR-T4/PR-T7/KP-T1/KF-T5 (24 lulus) |

`backend/tests_mem`: sebelum **433 lulus / 2 dilewati / 3 xfail** → sesudah **449 / 2 / 3** (+16 uji PR-T5; uji lama yang
disesuaikan di atas hijau; sapuan `test_PRT2_*`, `test_PRT3_sapuan.py`, `test_PRT4_sapuan.py` hijau tanpa perubahan).
`tests/test_fe03_access_catalog.py --noconftest`: 6 lulus.

Sesudah digabung di atas KF-T5 + KF-T3 + KP-T1: `tests_mem` **494 → 510 lulus** / 2 / 3; jest seluruhnya 496/496 (34 suite
gagal dimuat karena `@radix-ui`, kendala lingkungan). Penggabungan tiga arah (basis `d0c92d3`): satu konflik di
`routers/entities.py` — KP-T1 menambah pesan 403 rincian PT dan status PKP yang masih menyebut modul lama; keduanya kini
menyebut modul pemilik izin `entity`, "Badan Usaha (PT)". Uji KF-T5 (`B1`, pesan lapisan) ikut nama modul "Pusat
Pengaturan". Berkas lain (`bootstrap.py`, `routers/config.py`, `entity_lifecycle_service.py`, `test_KFT1`, glosarium,
`auditLabels.js`, `PRD.md`) tergabung otomatis; fixture akses dan `CODEBASE_MAP.md` dibangkitkan ulang. Hitungan penjaga
statik berhitung sama dengan sebelum; `verify_permission_checked` 580 cek lolos + self-test; `verify_role_gate_ui` PASS;
`audit_config_wiring --strict` bersih.

Jest (folder kerja terpisah): HEAD 68 suite lulus / 35 gagal dimuat (`@radix-ui/primitive/is-development` tidak termuat
lokal — kendala lingkungan, suite yang sama) / 482 uji → sesudah 69 / 35 (sama) / 491 uji, semua lulus.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli), sesudah `restore_demo` (data acuan; tiga skrip seed yang sama seperti
garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`).

| Jalan | Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|---|
| 1 (`b8bd0a2`) | `--quick` | 14 FAIL | 16 | 0 | 2 (`config_wiring` + self-test, sejak KF-T2) |
| 1 (`b8bd0a2`) | `--ci` | 42 FAIL | 43 | **1** | 2 |
| 2 (`311c8f3`) | `--quick` | 14 FAIL | 16 | 0 | 2 |
| 2 (`311c8f3`) | `--ci` | 41 FAIL | 43 | 0 | 2 |

Yang lebih merah di jalan 1: **POC FASE E-8 G1** — menuntut Finance memegang `order.view` + `order.print`; unit ini
menghapus `order.print` (tidak pernah diperiksa server; cetak dokumen pesanan cukup `order.view`). Harapan POC tinggal
`view`, alasan tertulis; yang dijaga E8.2 tetap. `311c8f3`, POC 65/65. Dua baris gate baru unit ini
(`guard:permission_checked` + self-test) PASS di kedua mode.

Yang dijalankan di salinan kerja sebelum penggabungan:

- Penjaga statik berhitung (`hitung_penjaga.sh`), sebelum → sesudah **identik** (`bukti/PR-T5/penjaga_hitung_sebelum_sesudah.log`):
  `verify_auth_coverage` 28, `verify_ui_standard` 23 (hitungan berkas editor peran tidak naik: `RoleEditorDrawer` hex 58 →
  57, huruf 28 → 27), `audit_i18n_id` 111, `audit_create_modal` 6, `verify_page_tabs` 1, `verify_to_list_bound` 6,
  `verify_entity_label` 2, lainnya PASS/0.
- Daftar STATIK `gate.sh` (56 perintah) di `d0c92d3` vs sesudah: hasil sama, kecuali dua perintah penjaga baru (tidak ada
  di HEAD) dan `verify_ref_unlink --self-test` (merah di salinan HEAD hanya karena salinan itu tidak punya `backend/.env`).
- `verify_role_gate_ui` PASS 33 + self-test hijau; `verify_role_label --self-test` hijau; `verify_access_catalog_nav` 0;
  `audit_config_wiring --strict` (jalur `/app` diganti) keluar 0 sebelum & sesudah.

## Menyimpang dari blueprint

1. **U14 — bunyi harapan kurang satu arah.** Mengganti gerbang `warehouse.view` dengan `reports.view` pada
   `/api/reports/warehouse-utilization` membuat Finance (memegang `reports.view`, tidak `warehouse.view`) 403 → 200. Uji
   mencatatnya persis (satu-satunya selisih ke 200). Usulan koreksi `unit/PR-T5.md` U14, kolom "Hasil yang diharapkan",
   teks pengganti persis:
   > Admin dan Manajer: kode sama di semua rute. Selisih yang diizinkan hanya pada empat endpoint `/api/reports/*` tabel 1: 200 → 403 bagi peran tanpa `reports.view` (Sales, Gudang, MD, Admin Gudang, Admin Sample, dan lainnya), dan 403 → 200 bagi peran yang memegang `reports.view` tetapi tidak memegang izin lama endpoint itu (Finance pada `/api/reports/warehouse-utilization`)
2. **`settings-documents` juga di modul Pusat Pengaturan** (selain modul Dokumen). Tanpa itu tab `settings-cfg-documents`
   (milik modul Pusat Pengaturan menurut tabel 2) tidak terjangkau — induk grupnya hanya milik modul Dokumen. Usulan
   koreksi tabel 2 baris `settings`, kolom Menu: tambahkan `settings-documents` sesudah `settings-cfg-documents`.
3. **Tabel 1 dihitung ulang di HEAD** (cek ulang butir 1): daftar `DINAMIS` penjaga = 19 pasangan "Tetap" +
   `ai_template.*` (`od_fulfillment.choose_route` sudah literal, jadi tidak dicantumkan — penjaga memerahkan entri basi);
   `MENUNGGU_KPT4` kosong karena KP-T4 sudah memasang pemeriksa kelima pasangan (4 lewat katalog persetujuan). Nama
   pemeriksa amandemen di `routers/amendments.py:172` (bukan `amendment_service.py:729`).
4. **Akibat penghapusan `reports.export`:** modul "Laporan & Analitik" kini hanya-lihat (`levels_available` `none`/`view`),
   di samping `approval`, `manager_home`, `costing`. Modul `devices` (`rfid_device`: `configure`, `revoke`) juga sakelar.
   `view_excludes` hari ini juga memuat "Pengecualian Batas Kredit" (`sales_force`) dan "Templat Laporan Tanya KN"
   (`assistant`) — sumber daya PR-T2 tanpa aksi lihat.
5. **Pesan Z6 yang menyebut modul lama** (tujuh berkas di atas) diganti nama modul pemilik izinnya; harapan
   `test_KFT1_izin_pengaturan.py` (B1, U04) ikut — teks lain tidak berubah.
6. **`nav_allowed_for_perms` ikut `VIEW_ACTION_REQUIREMENTS`** (spesifikasi hanya menyebut `/auth/me` + layar), supaya
   pratinjau `screens` dan relevansi notifikasi sama dengan menu. Efek samping yang disengaja: notifikasi yang
   bertautan meja peran (mis. `so_verify` → `sales-admin-desk`, `od_cancel_credit_note` → `finance-desk`) kini sampai ke
   pemegang aksinya; dulu tautan itu di luar katalog sehingga tidak lolos relevansi bagi peran mana pun selain Admin.
7. **Uji U14 di berkas sendiri** `test_PRT5_sapuan.py` (basis data sendiri, pola PR-T3); U9b/U13b tambahan.
8. **`apply_levels` melempar `ValueError`**; 400 diberikan `_clean_levels` (semua jalur layanan memanggilnya lebih dulu).
   Pemanggil yang mengirim "manage" untuk SEMUA modul kini 400 (modul hanya-lihat) — satu uji lama (KP-T4 U7)
   disesuaikan ke tingkat tertinggi yang berlaku; editor peran melewati modul yang tidak punya tingkat itu.
9. Layar: ringkasan editor empat keadaan (spesifikasi hanya menyebut kartu); baris bertanda "diubah" bila aksi rincinya
   berubah walau tingkatnya sama (PR-UX-12).

## Asumsi

- `ASUMSI` spesifikasi dipakai apa adanya: Ringkasan laporan hanya untuk pemegang `reports.view`; Sales, Gudang, MD, Admin
  Gudang, Admin Sample, MD Quality, QC bawaan kehilangan akses API empat endpoint itu (layar Ringkasan sudah tersembunyi
  bagi mereka — menu ikut modul Laporan). Ini satu-satunya pengurangan akses; "tidak ada izin yang ditambahkan"
  (spesifikasi) didahulukan atas K-47.
- Kamus label dimuat sesudah login; sebelum termuat pesan 403 memakai "modul ini" / label generik.
- Kalimat deskripsi modul `entities`, `settings`, `scheduler` (tidak ditulis spesifikasi) — teks perancang, bisa diganti
  PR-T6.

## Hambatan lingkungan

- Peramban/dev server tidak dijalankan → uji jalan U15 belum (lapis A dan gate dijalankan saat penggabungan).
- Jest: 35 suite gagal dimuat karena `@radix-ui/...` (sama di HEAD).

## Titik henti

- H3: migrasi `prt5:katalog` berjalan otomatis saat server mulai (preseden PR-T9/PR-T2/PR-T4); menjalankannya pada
  data nyata = keputusan pemilik. Tidak dijalankan terhadap basis data `backend/.env`.
- H7: tidak ada yang disentuh di `middleware/` maupun gerbang RFID (`rfid_device.configure` hanya diberi kalimat aksi
  berisiko).

## Yang perlu direview

- Daftar `DINAMIS` di penjaga: pemeriksa baru yang memakai variabel harus ditambahkan di sana dengan penandanya.
- Penggabungan dengan KF-T3 / KP-T1 (berkas bersama yang disentuh unit ini secara lokal: `routers/config.py` satu
  konstanta, `routers/settings.py`, `routers/entities.py`, `services/entity_lifecycle_service.py` teks pesan;
  `bootstrap.py` dua baris; `role_registry.py` satu blok di `apply_traits`). KF-T5 tidak bersinggungan.
- PR-T6 (layar Peran & Hak Akses) mewarisi: kata per label, menu peran bawaan dari izin; PR-T8: `GET /api/access/labels`
  tercatat login-saja.

Status: implemented_pending_review.

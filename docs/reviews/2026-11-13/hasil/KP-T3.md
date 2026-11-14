# KP-T3 — Aturan Persetujuan: buang pilihan palsu, tampilkan jenjang efektif per PT

- Commit awal: `eaeeaf5` (dikerjakan) · digabung di atas `f9ef3a9` (sesudah KF-T6)        - Commit akhir: `3224848` (koreksi blueprint `2d25142`)        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KP-03, KP-04, KP-08 (spesifikasi `docs/blueprint/unit/KP-T3.md`)

## Cek ulang "Keadaan sekarang"

Spesifikasi dibaca pada `3132cc4`; dicek ulang pada `eaeeaf5`.

| # | Hasil di `eaeeaf5` |
|---|---|
| 1 | Berlaku. `approvalRulesConstants.js:13` `ROLES` memuat "Owner"; `approval_rules.py:17` `VALID_ROLES` memuat `owner` |
| 2 | Berlaku. `role_registry.py:355` `required_rank`, `:316` `_DEFAULT_REQUIRED_RANK` = peringkat Manajer. Dibuktikan U4 (sebelum migrasi: aturan `owner` → `role_satisfies("manager", "owner")` benar) |
| 3 | Berlaku. `approvalRulesConstants.js:10`, `approval_rules.py:16`; benih bergeser: `DEFAULT_APPROVAL_RULES` kini `config_service.py:162`, dua baris `discount` di 167–168. Data acuan lokal memuat dua aturan `discount` aktif (laporan skrip, lihat Bukti) |
| 4 | Berlaku; baris bergeser: `sales_orders.py:389` (dari 362), `purchase_orders.py:586`, `purchase_requisition_service.py:185` (+288). Pemanggil lain yang ditemukan, semuanya SO/PO/PR: `so_lifecycle_service.py:26`, `pr_sourcing_service.py:602`, `rfq_service.py:204`, `po_amendment_service.py:210/222/281`, `seed_realistic.py:2445`. Satu-satunya jalan ber-`doc_type` bebas: `GET /api/settings/evaluate-approval` (parameter klien) |
| 5 | Berlaku; bergeser ke `config_service.py:358` (`pool`). Dibuktikan U8 (PO Rp200 jt ent_kanda lolos) |
| 6 | Berlaku. `approval_rules.py:42` `_validate` |
| 7 | Berlaku; bergeser: `config_service.py:397` (`extra`), `config_catalog_core.py:348`. Dibuktikan U11 (merah lama: `direktur` tersimpan 200) |
| 8 | Berlaku. `ApprovalRulesSettings.jsx:258`, `ApprovalRuleForm.jsx:13` |
| 9 | Berlaku; bergeser ke `routers/settings.py:117` (dari 102) |

## KP-03 / KP-04 / KP-08 — pilihan palsu, aturan PT menggantikan grup, jenjang tak terlihat

- Berlaku di HEAD: ya (tabel di atas; bukti merah di bawah).
- Akar masalah: daftar pilihan layar dan server ditulis statis (`owner`, `discount`) tanpa dicocokkan dengan registry
  peran dan pemanggil penilai; pemilihan aturan (PT menggantikan seluruh grup) tersembunyi di dalam `evaluate_approval`
  sehingga layar tidak bisa menampilkan apa yang sungguh dipakai mesin.
- Perubahan perilaku (sebelum → sesudah):
  - `POST/PATCH /api/approval-rules` dengan `required_role` `owner` (atau peran lain yang tidak ada) → 200 tersimpan →
    **400** "Peran penyetuju tidak dikenal. Pilih peran yang ada di Peran & Hak Akses." Peran yang ada di registry
    (termasuk peran kustom) tetap diterima server; layar hanya menawarkan Tanpa persetujuan / Manajer / Admin.
  - `doc_type` `discount` → 200 → **400** "Jenis aturan 'Diskon (%)' sudah tidak dipakai. Potongan harga diatur lewat
    Harga Khusus."; jenis lain yang tidak dikenal → 400 berlabel Indonesia. PATCH memeriksa jenis dokumen hasil gabungan,
    jadi aturan `discount` lama tidak bisa dihidupkan lagi (DELETE/nonaktifkan tetap bisa).
  - Benih: 7 → 5 aturan (dua `discount` dibuang). `GET /api/approval-rules` tidak menampilkan jenis di luar SO/PO/PR dan
    menambah `required_role_label`, `role_known`.
  - Baru `GET /api/approval-rules/effective?entity_id=…&doc_type=…` (izin `settings.view`, PT lewat
    `resolve_requested_entity`): sumber (`pt`/`grup`/`kosong`), `tiers` (tingkat 1 dari `approval_pool`), `extra_levels`
    (dari `get_effective_settings(PT)["approval"]["extra_levels"]`, sumber dari `config_resolver.resolve`),
    `unused_group_rules`, `warnings` (`celah`, `tumpang_tindih`, `lebih_longgar_dari_grup`, `peran_tak_dikenal`).
    `entity_id` kosong/"all" → 400 "Pilih PT untuk melihat jenjang yang berlaku."
  - Jawaban POST/PATCH aturan memuat `warnings` untuk pasangan (PT, jenis dokumen) aturan itu; tidak menolak simpan.
  - `PUT /api/config/values` kunci `approval.extra_levels`: isi diperiksa (`config_service.validate_extra_levels`,
    dipanggil `config_resolver.set_value`) — peran harus dikenal, nilai minimal angka ≥ 0 → 400 berpesan.
  - Mesin **tidak** berubah: `evaluate_approval` kini memanggil `approval_pool` + `_rule_for` (logika pemilihan dipindah
    utuh). Dibuktikan U8 dan U10 (36/36 pasangan sama).
  - Layar Pengaturan › Persetujuan › Aturan Persetujuan: bagian **Jenjang yang berlaku** (pemilih PT; bawaan PT aktif;
    "Semua PT" → petunjuk), kartu per jenis dokumen (lencana sumber, kalimat jenjang, peringatan kuning dari server,
    tautan "Lihat {n} aturan grup yang tidak dipakai"), kerangka abu-abu saat memuat, `ErrorNotice` + Coba lagi saat galat,
    "Belum ada aturan untuk PT ini." saat kosong. Tabel: "Semua PT", kolom "Berlaku untuk PT", tanda "peran tidak dikenal —
    diperlakukan sebagai Manajer", catatan `migrated_from_role`. Form: tanpa "Diskon (%)" dan "Owner", label
    "Berlaku untuk PT", keterangan "Aturan khusus PT **menggantikan** semua aturan grup …". Sesudah simpan dengan
    peringatan: pop-up "Aturan tersimpan. Perhatikan:" + daftar pesan.
  - Pesan 403 seluruh rute `approval-rules` kini kalimat manusia (Z6), 404/validasi berbahasa Indonesia.
- Data: skrip `scripts/migrate_kpt3_aturan_persetujuan.py` (bawaan hanya-lapor; `--apply` menulis): `discount` →
  `active: false` + `retired_reason`; peran tak dikenal → `manager` + `migrated_from_role`; `approval.extra_levels`
  ber-peran tak dikenal (grup & tiap PT di `system_settings`) hanya dilaporkan. Idempoten; peran kustom dikenali
  (`custom_role_service.sync_registry`). **Tidak dijalankan `--apply` pada data mana pun di luar database tiruan (H3).**
- Berkas berubah:

| Berkas | Isi |
|---|---|
| `backend/services/config_service.py` | Blok `KP-T3` sebelum `evaluate_approval`: `APPROVAL_DOC_TYPES`, `approval_pool`, `_rule_for`, `required_role_for`, `validate_extra_levels`, `role_view`, `effective_tiers` + perhitungan peringatan. `evaluate_approval` memakai `approval_pool`. Dua baris benih `discount` dibuang |
| `backend/services/config_resolver.py` | `set_value`: 3 baris (blok `KP-T3`) — `validate_extra_levels` untuk kunci `approval.extra_levels` |
| `backend/routers/approval_rules.py` | `VALID_DOC_TYPES` dari `APPROVAL_DOC_TYPES`; `VALID_ROLES` dihapus (→ `role_registry.is_role`); pesan galat spesifikasi; penyaring + label di daftar; `GET /approval-rules/effective` (sebelum `/{rule_id}`); `warnings` di POST/PATCH; pesan Z6 |
| `backend/config_catalog_core.py` | `approval.extra_levels.consumers` + `services/config_service.py:effective_tiers` |
| `scripts/migrate_kpt3_aturan_persetujuan.py` | Baru — skrip migrasi (lapor / `--apply`) |
| `frontend/src/features/settings/approvalRulesConstants.js` | `DOC_TYPES` tanpa diskon; `RETIRED_DOC_TYPES` (hanya membaca baris lama); `ROLES` statis dihapus → `approverRoleOptions()` berlabel registry; `tierLines`, `tierRange`, `fmtRp`, `SOURCE_BADGE` |
| `frontend/src/features/settings/ApprovalEffectiveTiers.jsx` | Baru — bagian "Jenjang yang berlaku" |
| `frontend/src/features/settings/ApprovalRulesSettings.jsx` | Memasang bagian baru, teks PT, tanda peran tak dikenal/migrasi, pop-up peringatan simpan, muat ulang jenjang sesudah perubahan |
| `frontend/src/features/settings/ApprovalRuleForm.jsx` | Pilihan baru, `unknownLabel` untuk nilai tersimpan di luar pilihan, label & keterangan PT |
| `frontend/src/features/settings/masters/masterFieldsConfig.js` | Label kolom memakai `DOC_TYPES` + `RETIRED_DOC_TYPES` (baris lama tetap berlabel "Diskon (%)") |
| `backend/tests_mem/test_KPT3_aturan_persetujuan.py` | Baru — U1–U13 |
| `backend/tests/test_bp_KPT3_jenjang_efektif.py` | Baru — pelengkap lapis A (lulus di MongoDB asli) |
| `backend/tests/test_iter273_approval_rules.py` | Disesuaikan kontrak baru (komentar `KP-T3`): `discount`/`owner` kini 400, daftar ≥ 5 tanpa `discount`, ada `role_known`/`required_role_label` |
| `frontend/src/features/__tests__/kpt3ApprovalTiers.test.js` | Baru — uji komponen (U14 bagian layar) |
| `ENTITY_REGISTRY.md`, `memory/PRD.md`, `CODEBASE_MAP.md` | Dua field `approval_rules`; baris KP-T3; peta dihasilkan ulang (`scripts/gen_codebase_map.py`) |

- Commit: `3224848`; koreksi blueprint U10 terpisah `2d25142`. Penggabungan di atas KF-T6: hanya `ENTITY_REGISTRY.md` dan
  `memory/PRD.md` yang juga berubah di cabang, tergabung otomatis; `CODEBASE_MAP.md` dibangkitkan ulang.
- Pengujian: lihat tabel uji di bawah.
- Bukti UI: belum diuji jalan di peramban (lihat U14).
- Fixture disiapkan langsung vs proses bisnis dijalankan: U4 (aturan `owner`, aturan `discount`, jenjang tambahan
  `direktur` di `system_settings` ent_kanda, penonaktifan aturan SO benih) dan U9 (penonaktifan aturan SO grup) =
  fixture sisip langsung. U1, U2, U6, U9 (dua aturan), U11, U13 (izin peran `sales`) = lewat API.
- Dampak pada modul terkait: penilai SO/PO/PR tidak berubah (U8, U10). Layar Pusat Pengaturan (`approval.extra_levels`)
  kini mendapat 400 berpesan untuk peran tak dikenal. Layar Master per PT (tabel `approval-rules`) tetap membaca baris
  `discount` lama berlabel.
- Keterbatasan / yang belum diuji: uji jalan peramban; lapis A belum dijalankan; perilaku bersamaan tidak relevan.
- Status: implemented_pending_review

## Uji penerimaan

`backend/tests_mem/test_KPT3_aturan_persetujuan.py` (lingkungan B). Merah = berkas backend versi `git show HEAD:` (tiga
berkas server + skrip dilepas), uji baru tetap (`bukti/KP-T3/tests_mem_KPT3_merah_kode_lama.log`): **13 gagal**. U8
dalam satu modul ikut gagal karena U1 di kode lama berhasil menyimpan aturan PO `owner` grup (efek berantai); dijalankan
bersama prasyaratnya saja (`-k "U6 or U8"`) U8 **lulus** di kode lama, sesuai spesifikasi ("merah kecuali U8").

| ID | Lapis | Merah di lama | Hasil |
|---|---|---|---|
| U1 | B | ya (200, tersimpan) | Lulus — 400 "Peran penyetuju tidak dikenal…"; jumlah aturan tetap |
| U2 | B | ya (200) | Lulus — 400 pesan diskon; jenis lain (`invoice`) 400 pesan jenis; jumlah tetap |
| U3 | B | ya (2 baris `discount`) | Lulus — 5 baris (1 SO + 2 PO + 2 PR), berlabel, `role_known` benar |
| U4 | B | ya (skrip belum ada) | Lulus — sebelum `owner`; mode lapor tidak menulis; `--apply` → `manager` + `migrated_from_role: "owner"`, `discount` → nonaktif + `retired_reason` (tidak dihapus), jenjang `direktur` hanya dilaporkan; `role_satisfies` manager benar / sales salah pada kedua keadaan; ulang = 0 tulis |
| U5 | B | ya (404 — rute tertangkap `/{rule_id}`) | Lulus — `grup`; 2 tingkat; jenjang tambahan 500 jt Admin "Direksi" (`source: grup`); peringatan kosong; `entity_name` bukan id |
| U6 | B | ya (tanpa `warnings`) | Lulus — POST dan PATCH memuat `warnings`; GET: `pt`, 1 tingkat, 2 aturan grup tak dipakai, `celah` (0, 500 jt), `lebih_longgar_dari_grup` (100 jt, 500 jt, "Manajer") |
| U7 | B | ya (404) | Lulus — sama persis dengan U5 |
| U8 | B | tidak (dengan prasyaratnya saja) | Lulus — ent_kanda `requires_approval` salah; ent_ksc `manager` |
| U9 | B | ya (404) | Lulus — `tumpang_tindih` (30 jt, 50 jt); tanpa `celah` |
| U10 | B | ya (`approval_pool` tidak ada) | Lulus — 36/36 sama (lihat Menyimpang) |
| U11 | B | ya (200, tersimpan) | Lulus — 400 "Jenjang tambahan baris 1: peran “direktur” tidak ada."; nilai efektif tetap; nilai minimal negatif juga 400 |
| U12 | B | ya (Tanpa Acuan 404; pesan 403 Sopir memuat `settings.view`) | Lulus — Sopir 403 berpesan Z6; Tanpa Acuan `settings.view` 200 (3 jenis dokumen) |
| U13 | B | ya (404) | Lulus — akun `sales` (peran diberi `settings.view`) ent_ksc 200, ent_kanda 403 |
| U14 | layar | ya (jest, 7/7 merah di komponen lama) | Uji komponen `frontend/src/features/__tests__/kpt3ApprovalTiers.test.js` 7/7 lulus (lencana "Aturan khusus PT ini", dua peringatan kuning, tanpa "Owner"/"Diskon (%)", pop-up simpan, memuat/galat/kosong). **Uji jalan peramban belum dilakukan** |

Lapis A: unit tidak punya butir lapis A. `backend/tests/test_bp_KPT3_jenjang_efektif.py` ditulis sebagai pelengkap untuk
data acuan (jenjang efektif = keputusan mesin untuk SO/PO/PR × 9 nilai × 2 PT; daftar tanpa `discount`; skrip mode lapor
tidak menulis) — **lulus** di lingkungan A (MongoDB 7 asli, backend `3224848`, data acuan), bersama
`test_iter273_approval_rules.py` yang disesuaikan: 15 lulus.

`backend/tests_mem` seluruhnya: **315 lulus / 2 dilewati / 3 diharapkan gagal → 328 lulus / 2 dilewati / 3 diharapkan
gagal** (13 uji baru) di salinan kerja; sesudah digabung di atas KF-T6: **351 → 364 lulus** / 2 / 3. Jumlah kunci pengaturan tidak berubah (harapan `test_KFT1_izin_pengaturan.py` tetap).
`access_modules.py` tidak berubah (fixture akses frontend tidak perlu dibangkitkan).

Jest (lingkungan lokal; `cmdk`/radix tidak termuat — salinan suite lama diberi tiruan `KNSelect` hanya di folder uji):
`kpt3ApprovalTiers` + `phase3Settings` + `auditUi2G5b` 26/26 lulus (kode lama: 19/19 + 7 merah). Seluruh suite: kode lama
35 suite gagal muat (cmdk) / 60 lulus / 425 uji → kode baru 35 / 61 / 432; daftar suite gagal identik.

## Bukti

`bukti/KP-T3/`: `tests_mem_KPT3_merah_kode_lama.log`, `tests_mem_KPT3_hijau_kode_baru.log`,
`tests_mem_seluruh_sebelum_sesudah.log`, `jest_KPT3.log`, `skrip_migrasi_mode_lapor_data_acuan.log` (database lokal
data acuan, hanya-baca: 2 aturan `discount` aktif akan dipensiunkan; 0 aturan ber-peran tak dikenal; 0 jenjang tambahan
ber-peran tak dikenal).

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli + backend `3224848`), sesudah `restore_demo` (data acuan; tiga skrip seed
yang sama seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `gate.sh --quick` | 16 FAIL | 16 | 0 | 0 |
| `gate.sh --ci` | 43 FAIL | 43 | 0 | 0 |

Penjaga statik dari worktree, sebelum → sesudah: `verify_auth_coverage` 28 → 28 (cek 1735 → 1736, rute baru lolos),
`verify_access_catalog_nav` 0 → 0, `verify_money_idempotency` lulus → lulus, `verify_custom_modals` lulus → lulus,
`verify_knselect_contract` 0 → 0, `verify_error_notice` lulus → lulus (277 → 279 cek), `verify_blocking_dialogs` lulus,
`verify_codebase_map` lulus, `verify_modal_dismiss` lulus, `audit_config_wiring.py` (tanpa DB) "9 kunci bermasalah + 2
editor ganda" → sama persis, `audit_i18n_id --strict` 113 → 113 (isi sama), `audit_create_modal` 6 → 6,
`verify_page_tabs` 1 → 1, `verify_approval_queues` 4 → 4 (pelanggaran yang sama: `initial_registration.py`,
`fact_sales_lines`). Tidak ada penjaga `verify_config_*` di repo.

## Menyimpang dari blueprint

- **U10 — jumlah pasangan.** Spesifikasi menulis "20 pasangan", tetapi rinciannya (8 nilai × PO, PR × dua PT + 4 nilai
  SO) = 8 × 2 × 2 + 4 = **36**. Uji memakai ke-36 (himpunan yang lebih besar; tidak ada yang dilewati). Usulan koreksi
  blueprint (commit terpisah `2d25142` `[KP-T3] Koreksi blueprint: U10 — 36 pasangan, bukan 20`): "36 pasangan … 36 dari 36 sama".
- `source` jenjang tambahan dihitung **per jenis dokumen**: `pt` hanya bila lapisan PT (`entity`/`legacy_entity`)
  menang **dan** memuat jenis dokumen itu. Alasan: penggabungan `get_effective_settings` per kunci jenis dokumen — PT yang
  hanya menimpa daftar PR tetap mewarisi daftar PO grup; `source_layer` saja akan menyebut PO "pt" padahal grup.
- `peran_tak_dikenal` juga untuk baris jenjang tambahan (pesan "Jenjang tambahan ≥ Rp… menunjuk peran “…” yang tidak
  ada. …"), karena mesin memperlakukannya sama (peringkat Manajer saat menyetujui).
- `validate_extra_levels`: pesan tambahan di luar tabel galat — peran kosong ("peran belum dipilih"), nilai minimal
  bukan angka/negatif ("nilai minimal harus angka ≥ 0"), nilai bukan objek per jenis dokumen. Spesifikasi menuntut
  pemeriksaannya tanpa menulis pesannya.
- `entity_id` kosong atau "all" di `…/effective` → 400 "Pilih PT untuk melihat jenjang yang berlaku." (spesifikasi:
  wajib; `resolve_requested_entity` sendiri memetakan "all" ke PT aktif).
- Pesan 403 Z6 dan pesan 404/validasi Indonesia untuk semua rute `approval-rules` (bukan hanya rute baru); PATCH
  memeriksa jenis dokumen hasil gabungan; `GET /approval-rules/{id}` ikut berlabel.
- Pop-up hasil simpan memakai `askConfirm` (tombol "Mengerti"/"Tutup"): tidak ada dialog info satu tombol di
  `confirmService`.
- Uji lama lapis A `backend/tests/test_iter273_approval_rules.py` disesuaikan (menguji perilaku yang sengaja dicabut unit
  ini: `discount`/`owner` diterima). Ambang jumlah daftar 9 → 5 karena dua baris `discount` tidak ditampilkan lagi.
- `config_service.py` bertambah ±215 baris (806 baris; berkas layanan tidak dibatasi penjaga ukuran). Penempatan
  mengikuti spesifikasi.

## Asumsi / keraguan

- `ASUMSI` spesifikasi dipakai apa adanya: `owner` → `manager` (perlakuan mesin hari ini), celah di bawah jenjang pertama
  tetap "tanpa persetujuan" (hanya diperingatkan), dua aturan ber-`sort` sama mengikuti urutan baca basis data.
- Server menerima `required_role` peran kustom (`is_role`) walau layar hanya menawarkan Tanpa/Manajer/Admin; form
  menampilkan nilai tersimpan di luar pilihan lewat `unknownLabel`. Penyetuju dari izin + batas nominal = KP-T4.
- Peringatan simpan untuk aturan **grup** dihitung untuk grup itu sendiri (celah/tumpang tindih/peran); PT lain yang
  punya aturan sendiri tidak diperingatkan di jawaban simpan (terlihat di "Jenjang yang berlaku" per PT).
- Titik henti H3: menjalankan `--apply` di data nyata = keputusan pemilik. Di data acuan lokal mode lapor menemukan
  2 aturan `discount`; tidak ditulis. Skrip mode lapor (hanya baca) dijalankan beberapa kali ke database lokal data acuan
  `test_database`, sekali tanpa sengaja (saat itu `--help` belum dikenali dan skrip langsung berjalan dalam mode lapor);
  sekarang argumen tak dikenal → keluar 2. Tidak ada penulisan di semua jalan itu.

## Usulan (di luar lingkup)

- `GET /api/settings/evaluate-approval` (`routers/settings.py:117`) hanya butuh login (tanpa `require_permission`) dan
  menerima `doc_type` bebas — pola Z1/Z3.
- `PATCH`/`DELETE /api/approval-rules/{id}` tidak mengadu PT aturan **yang ada** dengan cakupan pengguna (hanya PT baru di
  PATCH) — pemegang `settings.manage` satu PT bisa mengubah aturan PT lain lewat id (N1/N2). Bersinggungan dengan KF-T6.
- `help` kunci `approval.extra_levels` masih menyebut "Approval Rules" (L1/L2).

## Hambatan lingkungan

- Tanpa peramban: U14 belum diuji jalan (lapis A dijalankan saat penggabungan).
- Jest lokal: `cmdk`/radix tidak termuat; suite lama yang memuat `KNSelect` asli diberi tiruan hanya di folder uji
  (tidak di repo).

## Yang perlu direview

- Bentuk jawaban `…/effective` dan rumus ruas peringatan (`config_service._tier_warnings`), khususnya penggabungan ruas
  bersebelahan dan aturan `source` jenjang tambahan per jenis dokumen.
- Koreksi blueprint U10 (20 → 36).

Status: implemented_pending_review.

# KF-T4 — Pusat Pengaturan berbahasa awam, berkelompok rapi, dan bereditor yang layak

- Commit awal: `69cc4e3` (dikerjakan) · digabung di atas `c1b2888` (sesudah PR-T5, PK-21, KP-T7)        - Commit akhir: `13b84dd`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KF-12, KF-13, KF-UX 04, 08, 09, 10, 11, 12, 13 (saringan tema + kalimat pembeda), 14 (`receiving.mode`,
  nama "Pengaturan"), 15, 16/18/26 (teks, editor, `permission_label`), 17, 19, 20, 21, 22, 23, 24, 25, 27
  (spesifikasi `docs/blueprint/unit/KF-T4.md`)
- Risiko sedang → satu serah-terima (langkah 1–8 utuh; tidak dipecah KF-T4a/b/c).

## Cek ulang "Keadaan sekarang" (spesifikasi ditulis di `3132cc4`; dicek di `69cc4e3`)

| # | Hasil di `69cc4e3` |
|---|---|
| 1 | Berlaku, bergeser: **383 kunci** (bukan 310), 23 kelompok; terbesar `persetujuan` 67 (57 kunci `kontrol.*` KF-T6), `stok-satuan` 40, `rnd` 27, `penerimaan` 26. `config_registry.py:60` (`GROUPS`); `configGroupViews.js:31` (`CONFIG_GROUP_VIEWS`) |
| 2 | Berlaku, bergeser: 61 label > 45 huruf (11 di antaranya label `kontrol.*` buatan KF-T6), 23 kunci angka tanpa satuan, 68 kunci angka aktif boleh 0 tanpa angka 0 di penjelasan. `config_registry.py:250` (`E`) |
| 3 | Berlaku. `scripts/audit_i18n_id.py:385` (`RE_PY_TEKS`) tidak membaca argumen `label="…"` |
| 4 | Berlaku. `configDeepLink.js:35` (`LEGACY_DEEPLINK`), `:79` (`CONFIG_GROUP_IDS`) |
| 5 | Berlaku. `SettingCard.jsx:254` (tombol `cfg-reset` "Default"), `SettingsHub.jsx:240` (`onReset`), `routers/config.py:375` (`reset_value`, alasan otomatis "Kembalikan ke default sistem") |
| 6 | Berlaku. `SettingsHub.jsx:248` (`onClearEntity`), `routers/config.py:399` (`clear_value_layer`), `config_resolver.py:478` (`clear_layer`, alasan otomatis "Kembalikan ke nilai global", tanpa cek alasan wajib) |
| 7 | Berlaku sebagian. QC: `config_simulator.py:220` masih A/B/C (KF-T3 sudah memberi nilai penimpa Master Grade ke simulator, rumusnya tetap). Pajak: `config_simulator.py:39` masih membaca `tax.efaktur_enabled` (kini `not_used` sejak KF-T3) sebagai PKP |
| 8 | Berlaku. `config_resolver.py:327` (`resolve_group` tanpa `value_format`/`permission`); `SettingEditor.jsx:142` |
| 9 | Berlaku, bergeser: 15 kunci `list` (KF-T6 menambah `kontrol.admin_tetap_dua_orang`). **Berbeda:** 7 kunci daftar peran + `approval.extra_levels` + `approval.matrix_effective_from` kini `not_used` (KP-T3/KP-T4, PR-T2) — editornya tetap dibuat (kartu menampilkan nilai hanya-baca), validasinya diuji langsung (lihat Usulan koreksi U10/U11) |
| 10 | Berubah: `approval.extra_levels` `not_used` (KP-T4, isi pindah ke Aturan Persetujuan); KP-T3 menambah `config_service.validate_extra_levels` |
| 11 | Berlaku. `receiving.mode` diubah di kartu dan di `GrnModePanel.jsx` |
| 12 | Berlaku. `SettingsHub.jsx:116` (`ctx` cakupan grup = PT aktif), `SettingCard.jsx:41` (`draft`), `:203` (`submit`) |
| 13 | Berlaku (`config_resolver.py:47` `LAYER_LABEL`, `configApi.js:173` `SCOPE_LABEL`, `SettingsScopeBar.jsx:85`, `ConfigDrawers.jsx:142` "Status wiring", `SettingsHub.jsx:465` "append-only", `SettingCard.jsx:309` "Hanya admin…", `ConfigRedirectCard.jsx:44`) |
| 14 | Berlaku sebagian: KF-T5 sudah membangun layar lapisan pelanggan/barang (kalimat "Bisa dibedakan per pelanggan dari kartu pelanggan." kini benar dan dipertahankan) |
| 15 | Berlaku. `config_registry.py:309` (`search`), `routers/config.py:426` (`read_history`), `configApi.js:141` (`shortVal`), `config_registry.py:498` (`_bounded` "'{key}' minimum …"), `config_resolver.py:380` ("Level '…'") |

## KF-12 / KF-13 / KF-UX

- Berlaku di HEAD: ya (tabel di atas; 22 uji tests_mem + 11 uji komponen merah di kode lama).
- Akar masalah: registry hanya mewajibkan label/penjelasan/dampak terisi — tidak ada aturan bahasa, satuan, arti 0, atau
  sub-judul, dan penjaga bahasa repo tidak membaca katalog; kelompok disalin tangan ke layar; "Default" menulis bawaan
  pada lapisan aktif dengan alasan otomatis; editor dipilih dari `type` saja; simulator punya rumus sendiri.
- Perubahan perilaku (sebelum → sesudah):
  - **Registry**: 23 kelompok → **13 kelompok bersub-judul** (tabel (c); kunci sesudah `3132cc4` mengikuti pola
    awalannya — `hr.pph21.*` → `sdm`·`pph21`, `interco_payment.*` → `pajak-pembukuan`·`antar-pt`, `kontrol.*` →
    `persetujuan` dibagi 8 sub-judul "Dua orang: …" agar ≤ 14). `E(section=…)` wajib; id kelompok lama diterima
    (`GROUP_ALIASES`) di `E()`, `by_group`, `GET /effective?group=`, dan layar. Jumlah per kelompok/sub-judul:
    `bukti/KF-T4/kelompok_dan_teks.txt`.
  - **Teks** 293 kunci disentuh (label 208 · penjelasan 241 · dampak 75 · contoh 103 · satuan 26 · label pilihan 25):
    Lampiran A + glosarium tabel (b) + pola umum (contoh memakai label pilihan, tanpa kode HTTP/nama isian/kode
    keputusan) + satuan aturan (a)5 + **arti 0 ditulis baru untuk 68 kunci** (daftar di `bukti/KF-T4/kelompok_dan_teks.txt`;
    tiga di antaranya menulis apa adanya bahwa 0 **dibaca sebagai nilai lain** oleh mesin — lihat Asumsi).
    `verify_config_text.py`: **825 → 0** pelanggaran.
  - **Pengembalian nilai (KF-12)**: tombol "Default" hilang. Satu PT bernilai sendiri → **Ikuti nilai grup** (cabut);
    Satu PT mengikuti grup → keterangan "Mengikuti nilai grup"; nilai ≠ bawaan → "Pakai nilai bawaan sistem untuk PT
    ini" / (grup) "Pakai nilai bawaan sistem" — semua berdialog dengan kalimat spesifikasi + isian alasan (wajib bila
    berisiko tinggi). Server: `values/reset` & `values/clear` kunci `requires_reason` tanpa alasan → **400 "'{label}'
    berisiko tinggi — alasan wajib diisi."** (dulu 200 beralasan otomatis); alasan bawaan kunci lain "Dikembalikan ke
    nilai bawaan sistem" / "Kembali mengikuti nilai grup".
  - **Cakupan grup (KF-UX-09)**: layar meminta `scope=global` → nilai grup tanpa lapisan PT + `entity_overrides`
    (PT yang boleh dilihat & bernilai sendiri) → baris "PT dengan nilai sendiri: KANDA = …" yang bisa diklik.
  - **Editor (KF-13)**: daftar peran/pilihan = centang (`items: roles|options`), daftar berurutan = baris geser
    (`allocation.priority_order` "PT pemilik stok" terkunci pertama), `ar.aging_buckets` = deret angka + pratinjau
    "kolom 1–30, 31–60, 61–90, di atas 90 hari", `hr.employment_types` = daftar teks, `ai.glossary`/`ocr_price_table` =
    kotak multi-baris, `approval.matrix_effective_from` = pemilih tanggal, syarat bayar/satuan/departemen = daftar pilih
    dari master (`ref_options`), `approval.extra_levels` = tabel berkelompok (`grouped_list`; jenis tanpa pembaca
    hanya-baca "belum dipakai"), rupiah berpemisah ribuan + "paling kecil … · paling besar …", `receiving.mode` &
    `kontrol.*` tanpa editor + tautan ke layarnya (`edit_at`). Server: butir daftar divalidasi (pilihan, peran dikenal
    termasuk kustom, bulat menaik, teks tak kosong, tanpa kembar, `owner` pertama), `grouped_list` (jenis, peran, min ≥
    0), rujukan master (`ref`) harus ada di daftar; pesan galat memakai label + satuan ("'Masa tenggang sebelum denda'
    paling kecil 0 hari.").
  - **"Coba dulu" (KF-UX-04)**: pajak memakai `config_service.ppn_breakdown` (fungsi murni yang juga dipakai
    `compute_tax`) + PKP dari profil PT (`facts.is_pkp`); `tax.efaktur_enabled` keluar dari `needs`. QC memakai
    `qc_inspection_service.thresholds_from` (dipakai `grade_thresholds`) + `grade_from_points` (Master Grade aktif):
    20/40 → 25 = A1, 45 = BS, 18 = A.
  - **Pencarian (KF-UX-24)**: + contoh, label sub-judul, padanan dua arah (pemasok/supplier/vendor, roll/gulungan, …).
    **Riwayat (KF-UX-19)**: saringan kelompok/orang/PT/tanggal WIB + halaman (`{rows, total}`), nilai diformat, "Muat
    berikutnya", "Pulihkan nilai ini" (mengisi draf kartu), tautan "Riwayat perubahan kelompok ini".
  - **Layar**: kartu di bawah sub-judul, "Lanjutan (teknis)" tertutup, kartu ringkas satu baris yang terbuka saat
    diklik, kunci tidak dipakai dikumpulkan di bawah; saringan Semua · Sudah diubah · Risiko tinggi · Persetujuan ·
    Pengingat & batas waktu · Toleransi selisih (lintas kelompok di Semua pengaturan); contoh tampil langsung, "Detail
    teknis"; "Bisa dibedakan untuk: Semua PT · Satu PT"; lencana "Bawaan sistem"/"Aturan grup"/"Khusus {PT}"; laci
    "Kenapa nilainya begini?" satu baris per lapisan (lapisan lama digabung), tanpa nama koleksi; Simpan mati sampai
    alasan terisi bila wajib + dialog "Ubah '{label}'? Dari … menjadi … untuk …" untuk kunci berisiko tinggi; draf/alasan/
    jadwal kosong saat ganti cakupan; meninggalkan kelompok/cakupan berdraf ditanya; kartu hanya-grup/terkunci berkalimat
    spesifikasi; bilah "Berlaku untuk" "Semua PT (aturan grup)" / "Satu PT" + satu pita; tab "Kesehatan Pengaturan",
    kolom kelompok berlabel, "Tersambung ke sistem?", berkas di Detail teknis; kartu pengalih "… diatur di Pengaturan".
  - **Navigasi**: `settings-cfg-documents` / `settings-cfg-notify` → alias ke `settings-cfg-approval` (preset
    `section`); tab dicabut, rute cadangan `activeView === "<id>"` + id di `access_modules.py` tetap. Label tab
    "Ketegasan, Pengingat & Dokumen" dan "AI & Tampilan"; `PAGE_META` delapan layar. Tautan langsung membaca
    `configKeyIndex.json` (`scripts/gen_config_key_index.py`); `openConfig({group: <id lama>})` diterjemahkan.
- Data: tidak ada migrasi, tidak ada field/koleksi baru. Bidang perilaku (`type`, `default`, `min`, `max`, `scopes`,
  nilai pilihan, `permission`, `status`, `sensitif_baca`) 383 kunci sama dengan potret `69cc4e3` (U2), kecuali
  **pilihan baru** pada tiga daftar yang dulu tanpa pilihan (editor spesifikasi): `allocation.priority_order`,
  `rnd.variant_axes_default`, `rnd.variant_axes_optional`.
- Berkas berubah:
  - Server: `backend/config_registry.py` (GROUPS+sections, `GROUP_ALIASES`, `SECTION_IDS`, `resolve_group_id`,
    `THEMES`/`themes_for`, `LIST_ITEMS`/`REFS`, `E(section, items, ordered, ref, edit_at)`, `ROW_SHAPES`+`grouped_list`,
    `VALUE_FORMATS`+`date`/`multiline`, `groups()` bersub-judul, `by_group` alias, `SEARCH_SYNONYMS`/`search`, `coerce`
    → `_check_items`/`_check_grouped`, pesan berlabel), `backend/config_catalog_*.py` (15 berkas: kelompok, sub-judul,
    teks, metadata editor; `kontrol.*` label pendek + `edit_at`), `backend/services/config_resolver.py` (`LAYER_LABEL`,
    catatan lapisan, `resolve_group` + 11 bidang, `permission_label`, `role_options`, `ref_options`, `_check_ref`,
    `entity_overrides`, `alasan_wajib`/alasan bawaan, `clear_layer` beralasan, `history` bersaring + `total`),
    `backend/routers/config.py` (alias kelompok, `scope=global`, `_sim_facts`, reset/clear beralasan, riwayat),
    `backend/services/config_simulator.py` (`_tax`, `_qc_grade`, `run(…, facts)`), `backend/services/config_service.py`
    (`ppn_breakdown`), `backend/services/qc_inspection_service.py` (`thresholds_from`).
  - Penjaga & skrip: `scripts/guardrails/verify_config_text.py` (baru), `scripts/gen_config_key_index.py` (baru),
    `scripts/gate.sh` (3 baris statik), `scripts/audit_config_wiring.py` (render generik juga dibaca dari
    `SettingsBrowser.jsx` — lihat Menyimpang 4).
  - Layar: `frontend/src/features/settings/config/` `SettingCard.jsx`, `SettingEditor.jsx`, `SettingTableEditor.jsx`,
    `SettingsHub.jsx`, `SettingsBrowser.jsx` (baru, dipindah dari SettingsHub), `SettingsScopeBar.jsx`,
    `ConfigDrawers.jsx`, `ConfigHealthPanel.jsx`, `ConfigRedirectCard.jsx`, `configApi.js`, `configDeepLink.js`,
    `configGroupViews.js`, `configKeyIndex.json` (baru, dibangkitkan); `features/settings/cfg/SettingsGroupView.jsx`,
    `features/settings/ReceivingOcrSettings.jsx` (preset `tab`), `AppViewRouter.jsx`, `config/viewAliases.js`,
    `config/hubTabs.js`, `config/navMeta.js`, `styles/config.css`.
  - Uji: `backend/tests_mem/test_KFT4_registry.py`, `test_KFT4_pengembalian.py`, `test_KFT4_simulator_validasi.py`,
    `tests_mem/data/potret_registry_sebelum_KFT4.json` (baru); `backend/tests/test_bp_KFT4_pengaturan_awam.py` (baru, lapis
    A); `frontend/src/features/settings/config/__tests__/kft4SettingCard.test.js` (baru). Disesuaikan (perilaku sengaja
    diubah, berkomentar `KF-T4`): `tests_mem/test_KFT1_izin_pengaturan.py` (pesan "lintas PT", label kelompok alias,
    9 layar), `tests_mem/test_KFT2_kunci_pengaturan.py` (kelompok lewat alias), `backend/tests/test_phase3_p2_settings_groups.py`
    (indeks), `features/__tests__/phase3Settings.test.js`, `phase4R5.test.js`, `config/__tests__/navAccess.test.js`,
    `settings/config/__tests__/kft3SettingCard.test.js` ("WIB · Semua PT").
  - Dokumen: `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.3, `docs/KN_13_NAVIGATION_MAP.md` (changelog),
    `docs/blueprint/02_STANDAR.md` §2.1 (`section`, `items`/`ordered`, `ref`, `edit_at`, penjaga), `memory/PRD.md`,
    `CODEBASE_MAP.md` (dibangkitkan).
- Commit: belum (instruksi).
- Pengujian: tabel di bawah.
- Bukti UI: **belum diuji jalan di peramban** (U14 bagian uji jalan) — pengganti: uji komponen jest 11/11.
- Fixture disiapkan langsung vs proses bisnis: semua uji tests_mem lewat API (PUT/POST/GET `/api/config/*`); U2 =
  potret registry (berkas data); U10/U11 butir peran dan tabel berkelompok diuji langsung di `registry.coerce` karena
  kuncinya `not_used`.
- Dampak pada modul terkait: Komisi & Insentif, Kebijakan Retur (batas retur umum), Jadwal Bayar antar-PT mengunci id
  kelompok lama — tetap jalan karena `useSettingsBrowser` menerjemahkan id lama; tab Kontrol dua orang (KF-T6) tidak
  berubah (kartu `kontrol.*` di Semua pengaturan menautkan ke sana); POS/PO/tagihan yang membaca `GET
  /api/settings/effective` tetap menerima `ui.*`/`pos.*` (keterbacaan per kunci dijaga U2).
- Keterbatasan / belum teruji: uji jalan peramban (U14).
- Status: implemented_pending_review

## Uji penerimaan

Merah: kode `69cc4e3` utuh (`git archive`), berkas uji baru disalin: **22/22 gagal**
(`bukti/KF-T4/merah_kode_lama.log`, sebab per uji `merah_kode_lama_sebab.log`); jest baru di kode lama **11/11 gagal**
(`jest_merah_kode_lama.log`).

| ID | Lapis | Merah di kode lama (sebab) | Hasil kode baru |
|---|---|---|---|
| U1 | B (statik) | ya — penjaga belum ada; di registry lama 825 pelanggaran (T1 61 · T3 65 · T4 23 · T5 68 · T6 225 · T7 383) | Lulus — 0 pelanggaran; self-test 21 kasus hijau (merah per aturan T1–T7); terdaftar di gate statik (U1b) |
| U2 | B (statik) | ya — tiga daftar belum berpilihan | Lulus — 383 kunci, bidang perilaku sama dengan potret (kecuali pilihan baru tiga daftar) |
| U3 | B | ya — 23 kelompok lama | Lulus — 13 id tabel (c); tiap kunci ber-sub-judul terdaftar; `ar.grace_days`→denda, `receiving.ocr_enabled`→baca-sj, `payment.variance_ap_tolerance_rupiah`→tagihan, `pos.fbt.enabled`→saran-pos; jumlah sub-judul = jumlah kelompok |
| U3b (tambahan) | B | ya | Lulus — kunci baru ikut pola; semua alias → kelompok + sub-judul sah; tema 35 / 20 / 15 |
| U4 | B | ya — 403 kelompok tak dikenal | Lulus — `uang-masuk` → 24 butir `pembayaran-pelanggan`; `dokumen` → `persetujuan` |
| U4b (tambahan) | B | ya | Lulus — butir memuat `value_format` regex, `section`, `themes`, `items`, `ref_options`, `edit_at`, `permission(_label)`, `never_changed` |
| U5 | B | ya — reset tanpa alasan 200 | Lulus — 400 "'Tarif PPN' berisiko tinggi — alasan wajib diisi." & nilai tetap 11; 200 → 12; clear tanpa alasan 400; 200 |
| U6 | B | ya — alasan otomatis "Kembalikan ke nilai global" | Lulus — ent_kanda 5 (`global`); grup 6 → ent_kanda 6 |
| U7 | B | ya — alasan "Kembalikan ke default sistem" | Lulus — ent_kanda 0 (`entity`), tetap 0 sesudah grup 7; ent_ksc 7 |
| U8 | B | ya — "Grade B"/"C" | Lulus — "Grade A1", "Grade BS", "Grade A" = `grade_from_points(thresholds_from(20, 40))` |
| U9 | B | ya — `breakdown`/fakta PKP tidak ada | Lulus — ent_ksc PPN 1.100.000 total 11.100.000; ent_kanda tanpa PPN 10.000.000; = `ppn_breakdown`; `compute_tax` = `ppn_breakdown` (U9b) |
| U10 | B | ya — `[30, 20]` diterima, pesan berkunci | Lulus — pola sah 200 / `["("]` 400; `[30,20]`, `["a"]` 400 berlabel; `[14,30,60]` 200; `["lot","owner"]` 400; butir kembar 400; peran `Manager` ditolak di `coerce` (PUT `ai.margin_roles` 400 "tidak dipakai") — lihat Usulan koreksi 1 |
| U10b (tambahan) | B | ya — "'ar.grace_days' minimum 0" | Lulus — "'Masa tenggang sebelum denda' paling kecil 0 hari." |
| U11 | B | ya — `row_shape` json | Lulus — `coerce` bentuk sama / `owner` & jenis tak dikenal ditolak; butir `grouped_list` empat kolom; PUT 400 "tidak dipakai" — lihat Usulan koreksi 2 |
| U12 | B | ya — `supplier` ≠ `pemasok` | Lulus — supplier/pemasok, gulungan/roll, termin/syarat bayar, telat/terlambat sama dan tidak kosong; contoh & sub-judul ikut dicari |
| U13 | B | ya — 403 kelompok tak dikenal / tanpa `entity_overrides` | Lulus — `value` excluded, `entity_overrides` memuat ent_kanda = included (bernama), tanpa ent_ksc |
| Riwayat (tambahan) | B | ya — `limit` & saringan tidak ada | Lulus — kelompok lama/baru, `total`, halaman tanpa tumpang tindih, saringan orang & tanggal, tanggal tak sah 400 |
| Rujukan (tambahan) | B | ya | Lulus — `ref_options` memuat NET30; NET999 400; satuan "parsec" 400, "yard" 200 |
| Indeks & layar (tambahan) | B (statik) | ya | Lulus — `configKeyIndex.json` = keluaran skrip; delapan layar `settings-cfg-*` |
| U14 | layar | ya — 11/11 uji komponen merah | Uji komponen **11/11 lulus** (tanpa "Default"; "Ikuti nilai grup" hanya saat PT bernilai sendiri; Simpan mati sampai alasan; draf kosong sesudah ganti PT; editor; tautan). **Uji jalan peramban belum** |
| Lapis A | A | — | **Lulus** di lingkungan A (backend `13b84dd`, data acuan): `backend/tests/test_bp_KFT4_pengaturan_awam.py` (U3/U4, U5/U13, U8/U9, U12), bersama `tests/test_phase3_p2_settings_groups.py` dan lapis A KP-T7/KF-T2/KF-T3/KF-T5 (22 lulus) |

`backend/tests_mem` seluruhnya: `69cc4e3` **494 lulus / 2 dilewati / 3 xfail** → sesudah **515 lulus / 1 gagal / 2
dilewati / 3 xfail** (+22 uji KF-T4). Satu gagal = `test_PRT3_U13…` **kendala lingkungan**: `test_KFT2_kunci_pengaturan.py`
mengimpor `scripts/audit_config_wiring.py` yang menyisipkan `/app/backend` ke `sys.path`; di mesin ini `/app` → repo
utama, yang sejak baseline sudah memuat PR-T5 (54 rute login-saja). Pesan galatnya menyebut
`login_only_endpoints' from '/app/backend/…'`; uji itu lulus bila dijalankan sendiri (13/13), dan kode `69cc4e3` yang
dijalankan ulang sekarang gagal di uji yang sama (493 lulus / 1 gagal — `bukti/KF-T4/tests_mem_HEAD_sekarang.log`).
Bukan perubahan unit ini; di lingkungan integrator (repo = `/app`) tidak terjadi.

Jest seluruh suite (`bukti/KF-T4/jest_seluruh.log`): lama 35 suite gagal dimuat / 71 lulus / **507** uji lulus → baru
35 / 72 / **518** uji lulus (+11 `kft4SettingCard`); suite gagal dimuat identik (`@radix-ui`/`cmdk` tidak termuat —
kendala lingkungan). `phase3Settings.test.js`
(gagal dimuat di sini) dijalankan dengan tiruan KNSelect lokal: lulus.

## Bukti

`docs/reviews/2026-11-13/hasil/bukti/KF-T4/`: `merah_kode_lama.log`, `merah_kode_lama_sebab.log`,
`jest_merah_kode_lama.log`, `penjaga_teks_HEAD.log`, `penjaga_teks_sesudah.log`, `penjaga_statik_sebelum_sesudah.log`,
`tests_mem_sebelum.log`, `tests_mem_sesudah.log`, `tests_mem_HEAD_sekarang.log`, `jest_seluruh.log`,
`kelompok_dan_teks.txt`.

## Penggabungan

Dikerjakan di atas `69cc4e3`; sementara itu PR-T5, PK-21, KP-T7 masuk. Penggabungan tiga arah (basis `69cc4e3`); konflik
di `KN_13` (dua bagian dipertahankan), `configApi.js` (bentuk KF-T4 `itemLabel` sudah membaca label pilihan, menggantikan
blok KP-T7), `SettingEditor.jsx` (bentuk KF-T4), `navAccess.test.js`. Penyesuaian yang perlu:

| Tempat | Sebab | Penyelesaian |
|---|---|---|
| 19 kunci KP-T7 (`config_catalog_core.py`) | Lahir sesudah KF-T4 dirancang, tanpa `section` → registry gagal dimuat | `approval.reminder_max_listed` → `persetujuan/pemberitahuan`; `rnd.design_due_soon_days` → `rnd/nilai-desainer`; `notif.*` lewat alias `notifikasi` → `persetujuan/pemberitahuan`, 11 kunci tenggat dipindah ke sub-judul baru **"Kapan pengingat dikirim"** (`tenggat-pengingat`) agar ≤ 14 kunci (INV-CFG-TXT T7); label `inventory.drift_critical_multiplier` tanpa kata "ambang" (T6); contoh konten tanpa "posting" (T3). `verify_config_text` 0 pelanggaran |
| `SettingEditor.ListEditor` | Daftar berpilihan KP-T7 (mis. peran penerima WA) tidak memakai `items` | Daftar tanpa `items` tetapi ber-`options` → kotak centang (`ChecklistField`) |
| `access_modules.py` modul `settings` | PR-T5 memberi grup `settings-documents`/`settings-notify`; KF-T4 menjadikan tab keduanya alias → `verify_access_catalog_nav` 2 temuan | Grup induk tidak lagi diberikan modul Pusat Pengaturan (milik modul Dokumen dan Penjadwal); id tab alias tetap; penjaga 0 |
| `configDeepLink.openConfig` | Tautan KP-T7 mengirim id kelompok lama → mendarat di sub-judul alias | Kunci yang dikenal indeks memakai kelompok & sub-judul kunci itu sendiri |
| Uji | `navAccess` (PR-T5 + KF-T4), `test_KFT4_registry` U3b (tema +1/+5 dari KP-T7) & U4b (nama modul PR-T5), jest KP-T7 (kelompok baru, id uji `ChecklistField`) | Disesuaikan dengan alasan tertulis |

`tests_mem` sesudah digabung **545 → 567 lulus** / 2 / 3 (tanpa gagal: kendala `/app` yang tercatat di atas tidak muncul di
repo utama). Jest seluruhnya 523/523 (35 suite gagal dimuat karena `@radix-ui`). Hitungan penjaga: `audit_i18n_id` 111 → 109,
lainnya sama; `audit_config_wiring --strict` bersih; `verify_role_gate_ui`, `verify_view_aliases` PASS.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli + backend `303e709`), sesudah `restore_demo` (data acuan; tiga skrip seed yang
sama seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`). Satu jalan gate untuk dua unit
yang digabung berturut-turut (KF-T4 `13b84dd`, PR-T8 `303e709`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `gate.sh --quick` | 14 FAIL | 16 | 0 | 2 (`config_wiring` + self-test, sejak KF-T2) |
| `gate.sh --ci` | 41 FAIL | 43 | 0 | 2 |

Baris gate baru KF-T4 (`guard:config_text` + self-test, `config_key_index`) PASS di kedua mode. Baris PR-T8
(`guard:matriks_izin` + self-test) hanya di `--full` (tidak dijalankan); penjaga dijalankan terpisah di lingkungan B pada
`303e709`: self-test HIJAU, sapuan cepat MERAH dengan 20 baris yang sama dengan temuan PR-T8 (`bukti/PR-T8/sapuan_cepat_HEAD_gabungan.txt`).

Sebelum penggabungan, di salinan kerja:
`audit_i18n_id` **111 → 109** temuan (turun); `verify_role_gate_ui` PASS (33 cek, 0); `audit_config_wiring --strict`
hijau; `verify_config_text` 0 pelanggaran + self-test hijau; `gen_config_key_index --check` selaras; `verify_view_aliases`
PASS (16 alias); `verify_access_catalog_nav` 0; `verify_page_tabs` sama (1 pelanggaran lama `InventoryStockView.jsx`;
`SettingsHub.jsx` 1 → 0).

## Menyimpang dari blueprint

1. **Penerapan teks dengan alat penerap**: perubahan 306 panggilan `E("…")` berkunci literal dibuat alat AST yang
   deterministik (data: Lampiran A + glosarium + koreksi tangan); panggilan buatan putaran (`kontrol.*`, `pos.*`,
   `hr.bpjs.*`, `hr.feature_toggles.*`, `role_home.*`, `**_PPH21`) diubah tangan. Hasil diperiksa penjaga dan U2.
2. **`kontrol.*` (lahir sesudah spesifikasi)**: sub-judul "Dua orang: …" mengikuti bagian layar KF-T6, dua bagian dipecah
   (pembelian/tagihan pemasok, penjualan & retur/piutang) supaya ≤ 14 (T7); label memakai nama pendek (`_PENDEK`) agar
   ≤ 45 huruf ("…: dua orang di atas", tanpa "(Rp)" karena satuan tampil). Kartu `kontrol.*` di Semua pengaturan tanpa
   editor + tautan ke tab Kontrol dua orang (`edit_at`) — satu tempat ubah.
3. **`sensitif_baca` tingkat kelompok dihapus**: kelompok Tampilan dulu membuka semua kuncinya; kunci `ui.*`/`pos.*`
   kini menyebut `sensitif_baca=False` sendiri (keterbacaan tiap kunci sama — diuji U2), supaya kelompok `sistem` (AI,
   baca surat jalan, RFID) tidak ikut terbuka.
4. **`SettingsBrowser.jsx` dipisah dari `SettingsHub.jsx`** (batas 500 baris komponen); `audit_config_wiring.py`
   membaca kedua berkas untuk cek "merender daftar setting secara generik" (pemeriksaan sama, mengikuti kode yang
   dipindah). Kolom kelompok kiri "Semua pengaturan" diganti `FilterChips` (ratchet `verify_page_tabs` turun).
5. **Pilihan di tiga daftar** (`allocation.priority_order`, `rnd.variant_axes_*`) ditambahkan karena tabel editor
   memintanya; U2 mencatatnya sebagai satu-satunya perubahan "nilai pilihan".
6. **`ref_options` peran** (`items: "roles"`, kolom `ref: "role"`) dikirim server (`role_registry`, termasuk peran kustom)
   alih-alih dibaca layar dari daftar peran statik.
7. Lencana/kalimat lapisan produk tetap "barang" (KF-T5 menetapkan "Bisa dibedakan per barang dari kartu barang."; uji
   KF-T5 menguncinya); glosarium tabel (b) "produk (master)" berlaku untuk teks lain.
8. `CODEBASE_MAP.md` dibangkitkan ulang; generatornya tidak mendaftar penjaga, skrip, maupun `configKeyIndex.json` satu
   per satu.

## Usulan koreksi blueprint (teks pengganti persis)

1. U10 — `ai.margin_roles` `not_used` sejak PR-T2/KP-T4, sehingga PUT selalu 400. Ganti sel langkah
   "`PUT` `ai.margin_roles` = `["admin", "Manager"]` lalu `["admin", "manager"]`" dengan
   "`registry.coerce(ai.margin_roles, ["admin", "Manager"])` lalu `["admin", "manager"]`; `PUT` `ai.margin_roles`" dan sel
   hasil "400 (menyebut butir \"Manager\"), 200" dengan "ValueError menyebut butir \"Manager\", diterima; PUT 400 \"tidak
   dipakai\"".
2. U11 — `approval.extra_levels` `not_used` sejak KP-T4. Ganti langkah "`PUT` `approval.extra_levels` = `{…}`; lalu
   `role: \"owner\"`" dengan "`registry.coerce(approval.extra_levels, {…})`; lalu `role: \"owner\"`; `PUT` nilai sah" dan
   hasil "200 dan nilai tersimpan berbentuk sama; lalu 400; …" dengan "bentuk sama; lalu ValueError; PUT 400 \"tidak
   dipakai\"; butir memuat `row_shape: \"grouped_list\"` dengan empat kolom".
3. Keadaan sekarang #1/#2 dan aturan (c): jumlah pada `69cc4e3` = 383 kunci; tema `pengingat` 20 (18 + `returns.supplier_reminder_days`, `interco_payment.reminder_days`); kelompok `persetujuan` 72 kunci (57 `kontrol.*` dalam 8 sub-judul "Dua orang: …").

## Asumsi / keraguan

- `ASUMSI` spesifikasi dipakai (PT & pemasok; empat penempatan; tema pengingat; satuan turunan; departemen = nama unit
  organisasi SDM).
- Arti 0 ditulis menurut kode: `purchasing.price_deviation_approval_percent` 0 **dibaca 10%**
  (`routers/purchase_orders.py:600` `or 10.0`), `qc.grade_thresholds.a_max/b_max` 0 **dibaca 20/40**
  (`qc_inspection_service.grade_thresholds`), `antar_entitas.settlement_reminder_days` 0 **dibaca 30 hari**
  (`interco_reminder.py:94` `or 30`). Teksnya jujur; memperbaiki pembacanya (pola KF-T3 `default_of`) di luar unit ini —
  usul unit lanjutan. `receiving.ocr_image_max_side`/`ocr_max_output_tokens` tanpa `min`: 0 membuat pembacaan gagal
  (diuji: PIL `thumbnail((0, 0))` → ZeroDivisionError); `min` tidak diubah (spesifikasi).
- Teks `role_home.*`, `tax.efaktur_enabled`, `contra_bon.qty_tolerance_percent` ditulis untuk status `not_used` yang
  berlaku (KF-T2/KF-T3/PR-T4); label `contra_bon.qty_tolerance_percent` tanpa "(Lama)" (uji KF-T2).
- `LAYER_LABEL`/lencana: "Global" di baris jadwal kini "Semua PT" (glosarium); uji KF-T3 disesuaikan.
- 24 pesan server di luar Pengaturan masih menyebut "Pusat Pengaturan" (mis. `amendment_service.py:555` menyebut kelompok
  lama "Harga, Diskon & Komisi"); pintasan layarnya tetap jalan karena `openConfig` menerjemahkan id lama. Di luar
  lingkup (bukan teks registry/layar Pengaturan).
- `config_catalog_rfid.py` hanya kelompok/sub-judul/satuan yang berubah (kunci masa simpan bukti RFID, bukan logika
  gerbang — bukan H7).

## Titik henti

- **H3** — `RISIKO` spesifikasi, kueri hanya-baca untuk pemilik (tidak dijalankan):
  - PT yang dulu menekan "Default" masih terkunci pada nilai bawaan:
    `db.config_values.find({scope_type: "entity", reason: "Kembalikan ke default sistem", cleared: {$ne: true}}, {key: 1, scope_id: 1, value: 1, changed_by: 1, changed_at: 1})`
    (pemulihan = "Ikuti nilai grup" per kunci, keputusan pemilik).
  - Nilai daftar tersimpan yang kini ditolak saat disimpan ulang (butir peran salah ketik, butir di luar pilihan,
    umur piutang tidak menaik, urutan alokasi tanpa `owner` pertama):
    `db.config_values.find({key: {$in: ["ar.aging_buckets", "allocation.priority_order", "catalog.sales_hidden_stages", "rnd.variant_axes_default", "rnd.variant_axes_optional", "hr.employment_types", "finance.default_payment_term_code", "inventory.default_uom", "commission.incentive_unit", "notif.low_stock_division"]}, cancelled_at: {$exists: false}}).sort({created_at: -1})`
    dan dokumen lama `db.system_settings.find({}, {scope: 1, "ar.aging_buckets": 1, "allocation.priority_order": 1, "finance.default_payment_term_code": 1, "inventory.default_uom": 1})`
    — nilai tetap terbaca; kartunya menolak disimpan ulang sampai diperbaiki.

# KF-T5 — Aturan khusus per pelanggan dan per barang punya layar

- Commit awal: `ccff778` (basis lokal sementara = `2d164c9` + KF-T2) · digabung di atas `0c5486e` (sesudah KF-T2, KP-T4)        - Commit akhir: `0da3656` (koreksi blueprint `1d089c9`)        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KF-07 (spesifikasi `docs/blueprint/unit/KF-T5.md`)

## Cek ulang "Keadaan sekarang"

Spesifikasi dibaca dan dicek ulang pada `ccff778`.

| Butir | Hasil di `ccff778` |
|---|---|
| 13 kunci berlapis `customer` (10) / `product` (3) | Berlaku (registry 383 kunci). Tidak ada kunci ber-`supplier`/`document` |
| `SettingsScopeBar.jsx:68` (`cfg-scope-type`) hanya Global dan PT | Berlaku; bergeser ke `:65`. Tidak diubah (aturan khusus diatur dari kartu pelanggan/barang) |
| `SettingCard.jsx:132` (`scopes`) "Bisa diatur pada level: … Pelanggan tertentu" | Berlaku, baris sama |
| `config_resolver.py:58` (`WRITABLE_LAYERS`) | Berlaku; bergeser ke `:60` |
| `routers/config.py:146` (`_assert_scope_write`) hanya memeriksa lapisan PT/grup | Berlaku; bergeser ke `:164`. Dibuktikan U8/U9 (kode lama: id pelanggan `tidak_ada` dan pelanggan PT lain → 200, baris tersimpan) |
| `ar_aging_service.py:47` (`customer_id`) | Berlaku, baris sama |
| `penalty_service.py:67` (`penalty_policy`), `:73/74/75` | Berlaku; bergeser ke `:63`, `:77/78/79` |
| `payment_variance_service.py:110` (`variance_policy`) | Berlaku; bergeser ke `:109` |
| `allocation.lot_mode`: lapisan pelanggan tidak dibaca; yang dipakai `lot_policy`/`allocation_policy` kartu pelanggan — `config_service.py:544` | Berlaku; bergeser ke `config_service.py:807` (`allocation_policy`), `:810–813` (`lot_policy`). `CustomerFormModal.jsx:192` bergeser: isian di bagian "Kebijakan lot / dye lot" (`:248`), nilai `lot_policy` `:68/93/168` |
| `allocation.dye_lot_strict`: yang dipakai `enforce_single_dye_lot` — `config_service.py:552` | Berlaku; bergeser ke `:815` |
| `roll_service.py:616/622/643` | Berlaku; bergeser: `apply_remnant_rule` `:611` (baca ambang `:618`), `remnant_grade` `:622`, `cut_waste_limit_pct` `:640` (baca `:643`) |
| Pemanggil dengan id pelanggan: `ar_aging_service.py:235`, `penalty_service.py:395`, `payment_variance_service.py:710` | Berlaku; bergeser ke `:236`, `:440`; `:710` sama. Pemanggil lain yang juga meneruskan id pelanggan: `penalty_service.py:168/276`, `payment_variance_service.py:327`, `ar_aging_service.py:412` |
| `Customer360Panel.jsx:86` (`Kontrol Kredit`) | Berlaku; bergeser ke `:85` |
| Catatan baru (basis sementara; tidak berlaku di cabang) | Commit basis `ccff778` masih memuat `frontend/src/features/sales/ReturnAssumptionsPanel.jsx` (KF-T2 menghapusnya). Akibatnya `test_KFT2_U14…` (tests_mem), uji jest KF-T2 U14 dan `audit_config_wiring.py --strict` ("1 editor ganda") **sudah merah di HEAD** — bukan perubahan unit ini; berkas itu tidak disentuh |

## KF-07 — 13 kunci menawarkan lapisan pelanggan/barang tanpa layar

- Berlaku di HEAD: ya (tabel di atas; bukti merah di bawah).
- Akar masalah: registry mengizinkan lapisan `customer`/`product` dan resolver membacanya, tetapi tidak ada layar yang
  menulisnya (Pusat Pengaturan hanya Global/PT), penjaga tulis tidak membuktikan id sasaran, dan dua kunci `allocation.*`
  menjanjikan lapisan pelanggan yang tidak pernah dibaca mesin (yang dipakai isian kartu pelanggan).
- Perubahan perilaku (sebelum → sesudah):
  - **Registry** (`scopes`, `help`): `allocation.lot_mode` dan `allocation.dye_lot_strict` → `("global", "entity")`,
    `help` + "Untuk pelanggan tertentu, atur di kartu pelanggan (Kebijakan lot)." 8 kunci pelanggan → `help` + "Bisa
    dibedakan per pelanggan dari kartu pelanggan."; 3 kunci barang → `help` + "Bisa dibedakan per barang dari kartu
    barang."; kalimat lama "Bisa diatur per produk/kategori lewat lapisan produk." dibuang. Jumlah kunci, izin, bawaan
    tidak berubah. Baris lapisan pelanggan lama untuk dua kunci `allocation.*` tidak dihapus (resolver mengabaikannya).
  - **`PUT /api/config/values`, `POST …/values/reset`, `POST …/values/clear`** lapisan `customer`: pelanggan harus ada
    (404 "Pelanggan tidak ditemukan.") dan PT pelanggan harus dalam cakupan pelaku (`resolve_requested_entity` → 403
    "Tidak berwenang atas entitas ini"); lapisan `product`: barang harus ada (404 "Barang tidak ditemukan."); lapisan
    `supplier`/`document` → 400 "Aturan khusus per pemasok atau per dokumen belum tersedia." Kunci yang tidak mendukung
    lapisan itu → 400 "“{label}” tidak bisa dibedakan per pelanggan." / "… per barang." (dulu "… tidak bisa diatur pada
    level 'customer'. Level yang didukung: global, entity."). Izin tetap `_may_edit` kunci (KF-T1).
  - **`GET /api/config/effective?scope=customer|product`** (+ `customer_id`/`product_id`): hanya kunci yang `scopes`-nya
    memuat lapisan itu; tiap butir + `layer_value` (nilai milik pelanggan/barang itu, `null` bila tidak punya / dicabut)
    dan `inherited_value` (nilai tanpa lapisan itu = PT/grup). Pelanggan/barang dibuktikan ada (404) dan pelanggan dalam
    cakupan PT pembaca (403); tanpa `entity_id`, aturan PT = PT pelanggan.
  - **`GET /api/config/layers?key=…&scope_type=customer|product`** baru (izin `_may_read`): `{"rows": [{scope_id,
    scope_label, value, changed_by, changed_at, reason}], "total"}` — satu baris per pelanggan/barang yang punya nilai
    sendiri (nisan tidak dihitung), bernama, terbaru dulu, ≤ 200 baris; pelanggan PT di luar cakupan pembaca tidak ikut;
    kunci tak dikenal 404.
  - **`GET /api/config/history`**: baris lapisan pelanggan/barang membawa `scope_label` (nama); layar riwayat menampilkan
    "Pelanggan: {nama}" / "Barang: {nama}", bukan id.
  - **Layar**: komponen baru `frontend/src/features/settings/config/ScopedRulesSection.jsx`:
    - Penjualan › Pelanggan & CRM › detail pelanggan, sesudah "Kontrol Kredit": **Aturan khusus pelanggan ini** —
      "Kosong berarti pelanggan mengikuti aturan PT-nya."; 8 kartu; status "Mengikuti aturan PT: {nilai}" atau
      "Khusus pelanggan ini: {nilai} (aturan PT: {nilai})"; **Atur khusus** → editor + alasan (wajib untuk kunci
      berisiko tinggi; Simpan mati sampai diisi) + **Simpan**/Batal; **Kembali ikut aturan PT** (hanya bila punya nilai
      sendiri) dengan konfirmasi "Hapus aturan khusus ini? {Nama} akan kembali mengikuti aturan PT."
    - Produk & Harga › Master Produk › ubah barang (hanya barang tersimpan): **Aturan khusus barang ini** (3 kartu); PT
      = PT yang dipilih di kepala aplikasi ("Semua PT" → "aturan semua PT").
    - Memuat "Memuat aturan…"; galat `ErrorNotice` + Coba lagi; 403 atau tanpa kartu → bagian tidak tampil; tanpa izin
      ubah → kartu hanya-baca tanpa tombol.
    - Pusat Pengaturan (`SettingCard.jsx`): baris "Bisa diatur pada level: …" dihapus; kunci berlapis pelanggan/barang
      menampilkan "Bisa dibedakan per pelanggan — {n} pelanggan diatur khusus" (atau "per barang"), `{n}` dari
      `GET /api/config/layers`; klik → daftar "{nama}: {nilai}". Kunci lain: baris tidak tampil.
    - `configApi.layers` baru; `SCOPE_LABEL.customer` "Pelanggan ini", `SCOPE_LABEL.product` "Barang ini".
- Data: tidak ada koleksi/field baru, tanpa migrasi. Hitungan baris `config_values` ber-`scope_type` `customer`/`product`
  di database lokal `backend/.env` (`test_database`, hanya baca `count_documents`): **0 / 0** (juga `supplier`/`document`
  0) — tidak ada nilai lama yang tiba-tiba terlihat (`bukti/KF-T5/hitungan_lapisan_data_acuan.log`).
- Berkas berubah:

| Berkas | Isi |
|---|---|
| `backend/services/config_scoped_rules.py` | Baru — `periksa_lapisan`, `sasaran`, `pastikan_sasaran` (404/403/400), `tambah_nilai_lapisan`, `daftar_lapisan`, `beri_nama` |
| `backend/routers/config.py` | Impor; cabang KF-T5 di `_assert_scope_write`; parameter `scope` di `/effective`; `beri_nama` di `/history`; `GET /layers` baru |
| `backend/services/config_resolver.py` | `PER_LAPISAN` + pesan `set_value` "“{label}” tidak bisa dibedakan per …" (3 baris, blok KF-T5) |
| `backend/config_catalog_core.py` | `scopes` dua kunci `allocation.*`; `help` dua kunci `ar.*` dan dua kunci `allocation.*`; `impact` `ar.denda_rate_pct_per_month` tanpa kalimat ganda |
| `backend/config_catalog_payment.py`, `backend/config_catalog_ops.py` | `help` 6 kunci `payment.*` dan 3 kunci `cutting.*` |
| `frontend/src/features/settings/config/ScopedRulesSection.jsx` | Baru — `ScopedRulesSection` (bagian kartu pelanggan/barang) + `ScopedRulesSummary` (baris kartu Pusat Pengaturan) |
| `frontend/src/features/settings/config/SettingCard.jsx` | Baris "Bisa diatur pada level" → `ScopedRulesSummary` (sesudah "Kalau diubah") |
| `frontend/src/features/settings/config/configApi.js` | `layers`; `SCOPE_LABEL` customer/product; `scopeText` tanpa id pelanggan/barang (+ `label`), "Produk" → "Barang" |
| `frontend/src/features/settings/config/ConfigDrawers.jsx` | Dua tabel riwayat meneruskan `r.scope_label` ke `scopeText` |
| `frontend/src/features/crm/Customer360Panel.jsx` | Pasang bagian sesudah "Kontrol Kredit" |
| `frontend/src/features/admin/products/ProductMasterForm.jsx` | Pasang bagian saat `editingProductId`; PT dari `useEntityScope` |
| `backend/tests_mem/test_KFT5_aturan_khusus.py` | Baru — U1–U13 + 4 tambahan |
| `backend/tests/test_bp_KFT5_aturan_khusus.py` | Baru — pelengkap lapis A (lulus di MongoDB asli, 4/4) |
| `frontend/src/features/__tests__/kft5AturanKhusus.test.js` | Baru — uji komponen (bagian layar U14/U15) |
| `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`, `CODEBASE_MAP.md` | Baris KF-T5; istilah "Aturan khusus"; peta dibangkitkan ulang (`scripts/gen_codebase_map.py`) |

- Tidak disentuh: `config_registry.py`, `config_service.py`, `access_modules.py`, `AppViewRouter.jsx`,
  `permissions_config.py` (tidak ada izin baru → fixture akses frontend tidak perlu dibangkitkan; jumlah kunci berizin
  tetap → `test_KFT1_izin_pengaturan.py` tidak diubah).
- Commit: belum (instruksi: jangan commit).
- Pengujian: lihat tabel uji di bawah.
- Bukti UI: belum diuji jalan di peramban (U14, U15) — tidak menjalankan backend/dev server di sesi ini.
- Fixture disiapkan langsung vs proses bisnis dijalankan: pelanggan C1–C3, barang P1–P2, roll R1–R2 = fixture sisip
  langsung; semua tulis/cabut aturan khusus (U1–U12, tambahan) = lewat API; pembacaan mesin lewat fungsi pemakai
  (`get_ar_config`, `penalty_policy`, `variance_policy`, `cut_waste_limit_pct`, `apply_remnant_rule`,
  `get_allocation_policy`).
- Dampak pada modul terkait: mesin pembaca tidak berubah (U1–U6 hijau di kode lama dan baru). Pemanggil lain jalur tulis
  lapisan pelanggan/barang tidak ada (dicari: `set_value(`/`clear_layer(` di `backend/`). `_assert_scope_write` juga
  dipakai `values/reset` dan `values/clear`, jadi id sasaran dibuktikan di ketiganya.
- Keterbatasan / yang belum diuji: U14/U15 (uji jalan); lapis A belum dijalankan; `gate.sh` belum dijalankan.
- Status: implemented_pending_review.

## Uji penerimaan

`backend/tests_mem/test_KFT5_aturan_khusus.py` (lingkungan B). Merah = berkas uji dijalankan di salinan
`git archive ccff778` (kode lama utuh): **10 gagal, 7 lulus** (U1–U6 dan U10)
(`bukti/KF-T5/tests_mem_KFT5_merah_kode_lama.log`). Hijau di kode baru: **17/17**
(`bukti/KF-T5/tests_mem_KFT5_hijau_kode_baru.log`).

| ID | Lapis | Merah di lama (sebab) | Hasil |
|---|---|---|---|
| U1 | B | tidak — penjaga (resolver sudah membaca lapisan pelanggan) | Lulus — C1 10, C2 0, `penalty_policy` C1 10 |
| U2 | B | tidak — penjaga | Lulus — sesudah cabut C1 = 0 |
| U3 | B | tidak — penjaga | Lulus — 20.000,0 / 5.000,0 / 5.000,0 (C3 di `ent_kanda`) |
| U4 | B | tidak — penjaga | Lulus — C1 `off`, C2 `draft` |
| U5 | B | tidak — penjaga | Lulus — P1 7,0; P2 3,0 |
| U6 | B | tidak — penjaga | Lulus — R1 sisa (4 < 5), R2 bukan sisa (4 ≥ 2) |
| U7 | B | ya (200, baris lapisan pelanggan tersimpan) | Lulus — 400 "“Kebijakan campur lot” tidak bisa dibedakan per pelanggan."; tanpa baris baru; `get_allocation_policy(…, lot_policy strict_single)` = `strict_single` |
| U8 | B | ya (200, baris untuk id `tidak_ada` tersimpan) | Lulus — 404 "Pelanggan tidak ditemukan." / "Barang tidak ditemukan."; jumlah `config_values` tetap |
| U9 | B | ya (200 untuk pelanggan PT `ent_kanda`) | Lulus — 403 "Tidak berwenang atas entitas ini"; tanpa baris baru; pembanding pelanggan PT sendiri 200 |
| U10 | B | **tidak** — sudah benar sejak KF-T1 (lihat Usulan koreksi) | Lulus — `PUT` 403 pesan U ("…“Masa tenggang sebelum denda”… 'Pengaturan, Pengguna & Hak Akses'."); `GET` 403 B1 |
| U11 | B | ya (383 butir, tanpa `layer_value`) | Lulus — 8 butir (himpunan tepat 8 kunci) / 3 butir; semua punya `layer_value`, `inherited_value`; contoh toleransi C1 20.000 (PT 5.000), susut P1 7 (PT 3) |
| U12 | B | ya (404 — rute belum ada) | Lulus — `total` 1, `scope_id` C1, `scope_label` nama C1, `value` 10 |
| U13 | B | ya (10 kunci ber-`customer`) | Lulus — 8 + 3; tanpa `supplier`/`document`; `help` 13 kunci sesuai tabel; dua kunci lot `["global", "entity"]` |
| tambahan | B | ya (400 berpesan "level") | Lulus — lapisan `supplier`/`document`: 400 pesan spesifikasi (tulis dan `/layers`), tanpa baris baru |
| tambahan | B | ya (404 rute) | Lulus — `/layers` tidak menghitung nisan (sesudah cabut P1 → `{"rows": [], "total": 0}`); kunci tak dikenal 404 |
| tambahan | B | ya (`scope` diabaikan) | Lulus — pembaca `settings.view` hanya `ent_ksc`: `effective` pelanggan C3 403, C1 200 hanya-baca, aturan PT = PT pelanggan tanpa `entity_id`; `/layers` tidak memuat C3 (Admin melihat C1 + C3) |
| tambahan | B | ya (`scope_label` tidak ada) | Lulus — riwayat lapisan pelanggan/barang menyebut nama |
| U14 | layar (uji jalan) | ya (jest: modul `ScopedRulesSection` tidak ada) | **Belum diuji jalan.** Pengganti: uji komponen `kft5AturanKhusus.test.js` — "Mengikuti aturan PT: 0 hari" → Atur khusus 10 → Simpan (satu `PUT` lapisan `customer`) → "Khusus pelanggan ini: 10 hari (aturan PT: 0 hari)" → konfirmasi persis → `POST …/values/clear` → "Mengikuti aturan PT: 0 hari"; kartu Pusat Pengaturan "Bisa dibedakan per pelanggan — 1 pelanggan diatur khusus" → klik → "Toko Abadi: 10 hari" |
| U15 | layar (uji jalan) | ya (idem) | **Belum diuji jalan.** Pengganti: uji komponen bagian barang ("Khusus barang ini: 7 % (aturan PT: 3 %)", PT terpilih dikirim, "Semua PT" → "aturan semua PT"); nama barang di daftar Pusat Pengaturan dibuktikan tambahan `/layers` (`scope_label` = nama P1) |

Jest `kft5AturanKhusus.test.js`: **11/11 lulus** di kode baru; kode lama: suite gagal dimuat ("Cannot find module
'../settings/config/ScopedRulesSection'") (`bukti/KF-T5/jest_KFT5.log`). Suite terkait (`settingCardBertanggal`,
`kft6DualControl`, `phase4R5`, `roleReach`, `serverAccessReach`, `kft2KunciPengaturan`, `decisionsD3`, `phase3Settings`,
`auditUi2G5b`): kode lama 5 lulus / 4 gagal (61 uji lulus, 1 gagal) → kode baru 6 lulus / 4 gagal (72 lulus, 1 gagal);
daftar suite gagal identik — tiga gagal dimuat karena `cmdk` → `@radix-ui/primitive/is-development` tidak ada di
`node_modules` lokal (kendala lingkungan), `kft2KunciPengaturan` U14 gagal di kedua kode (`ReturnAssumptionsPanel.jsx`
masih ada di `ccff778`).

`backend/tests_mem` seluruhnya (`bukti/KF-T5/tests_mem_seluruh_sebelum_sesudah.log`): **414 lulus / 1 gagal / 2 dilewati /
3 diharapkan gagal → 431 lulus / 1 gagal / 2 dilewati / 3 diharapkan gagal** (17 uji baru). Satu gagal di kedua jalan =
`test_KFT2_U14_tidak_ada_layar_menulis_settings_lama` (berkas `ReturnAssumptionsPanel.jsx` di commit basis; lihat Cek
ulang). Harapan "415 lulus" pada HEAD hanya tercapai bila berkas itu sudah dihapus.

Uji pelengkap: `docs/audit/konfigurasi-peran-2026-11-13/bukti/t1_config.py` (standar §2.4.1, database tiruan, seluruh
registry): 13 kunci unit ini lulus putaran (tulis grup 200 → terbaca; lapisan PT 200 → hanya PT itu; nilai tak sah 400;
pulihkan 200 → bawaan); seluruh registry tulis grup 344 = terbaca 344, tulis PT 301 = terbaca 301
(`bukti/KF-T5/t1_config_13_kunci.log`).

Lapis A (**lulus 4/4** di lingkungan A, backend `0da3656`): `backend/tests/test_bp_KFT5_aturan_khusus.py` — hitungan baris lapisan
pelanggan/barang di data acuan (cetak `-s`), atur → baca → `/layers` → cabut untuk satu pelanggan dan satu barang nyata
data acuan, penolakan 404/400 tanpa baris baru. `python -m py_compile` lulus.

## Penggabungan

Digabung di atas `0c5486e` (KP-T4 (b)) tanpa konflik: katalog `config_catalog_core|ops|payment.py`, glosarium dan
`PRD.md` tergabung otomatis (tiga arah, basis `ccff778`); `CODEBASE_MAP.md` dibangkitkan ulang. Di cabang, berkas
`ReturnAssumptionsPanel.jsx` sudah dihapus (KF-T2), jadi catatan "merah di HEAD" di atas tidak berlaku: `tests_mem` sesudah
digabung **433 → 450 lulus** / 2 / 3, `audit_config_wiring --strict` bersih, jest `kft5AturanKhusus` + `kft2KunciPengaturan`
+ `kpt4ApprovalPolicies` + `src/config/__tests__` 116/116. Koreksi blueprint langkah 1 (U10 tidak merah) di commit
terpisah `1d089c9`.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli + backend `69cc4e3`), sesudah `restore_demo` (data acuan; tiga skrip seed yang
sama seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`). Satu jalan gate untuk tiga unit
yang digabung berturut-turut (KF-T5 `0da3656`, KF-T3 `dbe1633`·`9783875`, KP-T1 `69cc4e3`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `gate.sh --quick` | 14 FAIL | 16 | 0 | 2 (`config_wiring` + self-test, sejak KF-T2) |
| `gate.sh --ci` | 41 FAIL | 43 | 0 | 2 |

Hitungan penjaga statik berhitung (`scripts`… `verify_auth_coverage` 28, `verify_ui_standard` 23, `audit_i18n_id` 111,
`audit_create_modal` 6, `verify_page_tabs` 1, `verify_to_list_bound` 6, `verify_entity_label` 2, lainnya 0/PASS) sama
sebelum dan sesudah tiap unit; `verify_role_gate_ui` PASS; `audit_config_wiring --strict` bersih; `config_health` 0 rusak.
Jest (`src/config`, `src/features`, `src/hooks`, `src/components`) di HEAD akhir: 487/487 uji lulus; 34 suite gagal dimuat
karena `@radix-ui/primitive/is-development` (kendala lingkungan).

Penjaga statik dari worktree, sebelum (`ccff778`) → sesudah (`bukti/KF-T5/penjaga_sebelum_sesudah.log`):
`verify_auth_coverage` 28 → 28, `verify_ui_standard` 23 → 23, `audit_i18n_id` 113 → 113, `audit_create_modal` 6 → 6,
`verify_page_tabs` 1 → 1, `verify_to_list_bound` 6 → 6, `verify_entity_label` 2 → 2, `verify_list_export`,
`verify_error_notice`, `verify_custom_modals`, `verify_money_idempotency`, `verify_codebase_map` lulus → lulus,
`verify_knselect_contract` 0 → 0, `verify_access_catalog_nav` 0 → 0, `verify_scope_guard` hijau → hijau,
`verify_role_gate_ui.py` lulus (39 cek, 0 pelanggaran) → sama; tambahan `verify_blocking_dialogs`, `verify_modal_dismiss`,
`verify_role_label`, `verify_ui_contrast` lulus → lulus, `verify_numeric_bounds` 3 → 3. `verify_approval_queues`
bergantung isi database — tidak dibandingkan. `scripts/audit_config_wiring.py --strict` (salinan, `/app` → jalur
worktree; tanpa database): "0 kunci bermasalah + 1 editor ganda" (`ReturnAssumptionsPanel.jsx`), keluar 1 → sama persis
(`bukti/KF-T5/audit_config_wiring_sebelum_sesudah.log`).

## Menyimpang dari blueprint

- **Kartu bagian memakai `SettingEditor`, bukan `SettingCard` utuh.** Spesifikasi menulis "memakai `SettingCard` dan
  `configApi`"; isi kartu yang diminta (baris status, Atur khusus, Kembali ikut aturan PT) berbeda dari kartu Pusat
  Pengaturan yang terikat pilihan cakupan Global/PT, laci "Kenapa nilainya begini?"/riwayat/simulasi, dan baris jadwal.
  Editor nilai, format nilai, dan pembersih teks tetap yang sama (`SettingEditor`, `formatValue`, `cleanCfgText`).
- **Baris "Bisa dibedakan per pelanggan — n …" tampil di muka kartu** (sesudah "Kalau diubah"), bukan di dalam lipatan
  "Contoh & detail teknis" tempat baris lama: L6 — pengubah aturan PT perlu melihat bahwa sebagian pelanggan/barang
  memakai nilai sendiri tanpa membuka detail. Hanya kunci berlapis pelanggan/barang yang memanggil `/layers`. n = 0 →
  "0 pelanggan diatur khusus" tanpa tautan; lebih dari 200 → "Menampilkan 200 dari n …".
- **Pembacaan berlapis juga dijaga**: `GET /effective?scope=customer&customer_id=…` membuktikan pelanggan ada (404) dan
  PT-nya dalam cakupan pembaca (403); `entity_id` kosong → PT pelanggan. `/layers` hanya menghitung pelanggan dalam
  cakupan PT pembaca (`total` = jumlah sesudah saring). Spesifikasi hanya menyebut izin baca KF-T1; tambahan ini
  menerapkan N2 pada id dari klien.
- **`/layers` dan `?scope=`** selain `customer`/`product`: `supplier`/`document` → 400 pesan spesifikasi; nilai lain →
  400 "Aturan khusus hanya bisa dibedakan per pelanggan atau per barang."
- **Riwayat menyebut nama sasaran** (`scope_label` di `/history`; `scopeText` tidak menampilkan id pelanggan/barang;
  "Produk" → "Barang" di label cakupan riwayat) — L1, karena baris lapisan pelanggan/barang kini lahir dari layar.
- **Pesan "tidak bisa dibedakan …" untuk semua lapisan** (`per PT`, `per pemasok`, `per dokumen`, `untuk semua PT`), bukan
  hanya pelanggan/barang, supaya teks lama yang menyebut "level" dan id lapisan hilang seluruhnya.
- `impact` `ar.denda_rate_pct_per_month`: kalimat "Bisa dibedakan per pelanggan." dibuang karena kini ada di `help`.
- Cabut aturan khusus memakai konfirmasi tanpa isian alasan (server tidak mewajibkan alasan untuk cabut); alasan tercatat
  "Kembali ikut aturan PT".
- `daftar_lapisan` melewati baris ber-`cancelled_at` (penanda pembatalan jadwal dari KF-T3 yang sedang dikerjakan) —
  tanpa efek hari ini, mencegah jadwal batal terhitung sesudah penggabungan.

## Usulan koreksi blueprint

Langkah kerja 1 menulis "U7–U13 merah", padahal U10 sudah hijau di kode lama (KF-T1 sudah menolak tulis tanpa izin kunci
dan baca tanpa satu pun kunci terbaca). Teks pengganti persis untuk butir 1 bagian "Langkah kerja":

> 1. `backend/tests_mem/test_KFT5_aturan_khusus.py`: U1–U13; U1–U6 sudah hijau untuk bagian "terbaca mesin" (resolver
>    sudah mendukung) dan U10 sudah hijau sejak KF-T1 — tes tetap ditulis sebagai penjaga; U7–U9 dan U11–U13 merah.

## Asumsi / keraguan

- `ASUMSI` spesifikasi dipakai apa adanya: wewenang mengatur aturan khusus = izin kunci itu (`settings.manage`, bawaan
  hanya Admin); nilai khusus pelanggan berlaku di semua PT tempat pelanggan itu bertransaksi.
- Barang tidak ber-PT di master (berlaku untuk seluruh grup), jadi lapisan barang hanya dibuktikan ada, tanpa
  pemeriksaan cakupan PT.
- Pelanggan tanpa `entity_id` (data lama) lolos pemeriksaan cakupan (`resolve_requested_entity("")` = PT aktif).
- Kartu "Aturan khusus barang ini" pada mode "Semua PT" menampilkan nilai grup ("aturan semua PT"); nilai yang dipakai
  mesin untuk satu PT bisa berbeda bila PT itu punya nilai sendiri.
- `RISIKO` spesifikasi: di database lokal (hanya baca) tidak ada baris lapisan pelanggan/barang, jadi tidak ada nilai lama
  yang mendadak tampil. Data nyata belum diperiksa; kueri: `db.config_values.countDocuments({scope_type: {$in:
  ["customer", "product"]}})`.
- Titik henti: tidak ada yang tersentuh (tanpa migrasi, tanpa data nyata, tanpa `middleware/`/RFID, tanpa rahasia).

## Catatan penggabungan

Berkas bersama yang disentuh, semuanya blok ber-komentar `KF-T5`: `services/config_resolver.py` (konstanta `PER_LAPISAN`
+ pesan di `set_value`), `routers/config.py` (impor, satu cabang `_assert_scope_write`, parameter `scope` di
`/effective`, satu baris di `/history`, rute `/layers` sebelum `/health`), katalog `config_catalog_core|payment|ops.py`
(`help`/`scopes` 13 kunci), `SettingCard.jsx` (impor + 2 baris; 3 baris dibuang di lipatan detail), `configApi.js`.
`CODEBASE_MAP.md` dibangkitkan dari salinan kerja yang masih memuat `ReturnAssumptionsPanel.jsx` (hitungan `sales` 98);
bangkitkan ulang sesudah penggabungan.

## Bukti

`bukti/KF-T5/`: `tests_mem_KFT5_merah_kode_lama.log`, `tests_mem_KFT5_hijau_kode_baru.log`,
`tests_mem_seluruh_sebelum_sesudah.log`, `jest_KFT5.log`, `penjaga_sebelum_sesudah.log`,
`audit_config_wiring_sebelum_sesudah.log`, `t1_config_13_kunci.log`, `hitungan_lapisan_data_acuan.log`.

## Hambatan lingkungan

- Tanpa peramban/backend berjalan di sesi ini: U14/U15 hanya diuji di tingkat komponen.
- Jest lokal: `cmdk`/`@radix-ui` tidak termuat (tiga suite lama gagal dimuat di kode lama dan baru); uji baru meniru
  `KNSelect`.

## Yang perlu direview

- Penempatan baris jumlah aturan khusus di muka kartu Pusat Pengaturan (lihat Menyimpang).
- Pemeriksaan cakupan PT pada pembacaan (`/effective?scope=customer`, `/layers`) — tambahan di luar spesifikasi.

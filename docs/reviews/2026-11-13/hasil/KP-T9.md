# KP-T9 — Menu Pengaturan menjadi sembilan hub dengan satu istilah "PT"

- Commit awal: `a742da9` (dikerjakan) · digabung di atas `27efaa4` (sesudah PK-30, PK-42, PM-T1)        - Commit: `b95bd0d` · cek visual `ad17fa0` · koreksi blueprint `a3838f5`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KP-33; bagian tautan dari KP-29 (penyimpanannya ditutup KF-T2); bagian menu dari KF-UX-28 — keputusan K-46
- Spesifikasi: `docs/blueprint/unit/KP-T9.md` · standar `02` §3.2 butir 2, §4 (L1, L2, L3, L7), §7 · risiko sedang (satu serah-terima)

## Cek ulang "Keadaan sekarang" (di `a742da9`)

Spesifikasi dibaca pada `3132cc4`; MN-T1, KF-T4, KF-T6, KP-T5, KP-T6, KP-T8, PR-T5 sudah mengubah berkas yang sama.

| # | Hasil |
|---|---|
| 1 | Bergeser: grup `settings-hub` 12 hub + 2 sub-judul (`navStructure.js:388`–`401`); **29 tab tampak + 1 alias** (`permission-matrix`), bukan 30 — MN-T1 mengeluarkan Komisi & Insentif, KF-T4 mencabut Aturan Dokumen & Penerima Notifikasi, KF-T6/KP-T5 menambah Kontrol dua orang & Penomoran Dokumen. Tiga hub ber-tab tunggal tetap tiga, tetapi kini Pembelian & Produksi, R&D, **Notifikasi & Penjadwal** (Perusahaan & Akun = 1 tab tampak + 1 alias) |
| 2 | Berlaku: sembilan wadah ber-tab-dalam masih ada (`EntitiesAccessView.jsx:33` 5, `DocTemplatesView` 2, `SchedulerView.jsx:22` 3 — `tab-pills`, `DevicesView.jsx:38` 2, `ReceivingOcrSettings` 4, `BankRulesSettingsView` 2, `AttendanceSetupView` 2, `SettingsHub` 5, `AdminView.jsx:232` 2) |
| 3 | Berlaku: `AppViewRouter.jsx:145` (`EntitiesAccessView` + `initialTab`), `:140` (`AdminView only`), `AttendanceSetupView.jsx:48` (`only`), `viewAliases.js:47` (`cs-rfid-devices` preset), `hubTabs.js:268` (`aliasOf`), `navigationConfig.js:52` (`hubForView`) |
| 4 | Berlaku: `role_registry.py:274` (`nav_for_levels` tiap muat), `access_modules.py:424`, `roles.js:409` (`roleCanSee`) |
| 5 | Bergeser: PR-T5 sudah memecah modul `admin` menjadi lima (`accounts`, `roles`, `entities`, `settings`, `scheduler` — `access_modules.py:235`–`259`); `settings-purchasing` ada di `purchasing`/`supplier`/`payable` (`:53`, `:63`, `:69`); `settings-devices` di `warehouse_ops`, `hr`, `devices` |
| 6 | Sebagian tidak berlaku: keempat tab SUDAH bermodul (PR-T5 `_PRT5_NAV`: `settings-receiving-ocr` → Operasi Gudang, `amendment-reasons`/`bank-recon-rules` → Kas, Bank & Kasus; PR-T2: `incentive-rates` → `sales_force`, kini di SDM sejak MN-T1) dan endpoint `incentive_rates.py:45` sudah `require_permission`. Yang masih berlaku: penjaga hanya memeriksa id yang ada di katalog, dan **hub induk tidak ikut** — `finance_ops` tanpa `settings-sales` (Alasan Koreksi tak terjangkau peran kustom), `documents` tanpa `settings-hub` (grup Pengaturan disembunyikan untuk peran yang hanya bermodul Dokumen), `product` tanpa `settings-hub`/hub induk Impor Data Awal. Dibuktikan merah U1 (aturan 3 & 4 tidak ada) |
| 7 | Berlaku: `custom_role_service.py:816` (`_clean_hidden` → `all_nav_ids`); id tab baru ditolak 400 di kode lama (merah U9) |
| 8 | Berlaku: `roles.js:202` (Admin Sales `settings-hub`/`settings-sales`/`settings-warehouse`); Finance kini melihat Pengaturan › Keuangan & Pajak › Pemetaan Akun (MN-T1 `roles.js:283`) |
| 9 | Berlaku (baris bergeser): `verify_view_aliases.py:15–17`, `check_nav_map.py:488` (`check_page_meta`), `audit_config_wiring.py:263`, `verify_page_tabs.py` (+ INV-UI-13/14 dari MN-T1) |
| 10 | Berlaku: `IntercoPaymentSchedule.jsx:36`, `DocumentCenter.jsx:275`, `hubTabs.js:163` (`bank-accounts`), `navStructure.js:275` (`md-warehouses`), `ReturnPoliciesView.jsx:7` |
| 11 | Bergeser: "Antar Entitas (Grup)" sudah "Antar-PT" (MN-T1). Tersisa: `hubTabs.js` 3 label ("Badan Usaha & Akses", "Harga per Badan Usaha", "Transfer Antar-Entitas"), `navMeta.js` 8 judul/kicker, `EntitySwitcher.jsx:67` ("Semua Entitas", "Badan usaha"), katalog modul 7 teks (`access_modules.py:21`, `:42`, `:70`, `:109`, `:190`, `:241`, `:489`) |
| 12 | Berlaku: `EntityMastersView.jsx:30` (`DOMAIN_HOME` "Dokumen & Cetak", `:38` "Master Data"), `SettingsGroupView.jsx:63` (`settings-all-link` "Integrasi & Sistem") |

## KP-33 — Menu Pengaturan: 12 hub, tiga ber-tab tunggal, wadah ber-tab-dalam, empat kata untuk "PT"
- Berlaku di HEAD: ya (butir 1, 2, 11; merah U3, U4, U10, U2-istilah).
- Akar masalah: hub ditambah per keputusan lepas (P16-K1, KF-T4, KF-T6, KP-T5) tanpa urutan isi PT baru; bagian layar wadah
  lama (Badan Usaha & Akses, Perangkat, Penjadwal) tidak bisa dibuka sebagai tab hub; istilah menu tidak dijaga penjaga.
- Perubahan perilaku (sebelum → sesudah):
  - Grup **Pengaturan** (`settings-hub`): 12 hub + 2 sub-judul → **9 hub tanpa sub-judul**: Perusahaan (PT) · Pengguna & Hak
    Akses (baru) · Persetujuan · Penjualan · Gudang, Pembelian & Produksi · Keuangan & Pajak · SDM · Dokumen & Notifikasi ·
    Sistem. **35 tab tampak** (3/3/4/3/5/4/3/4/6), paling banyak 6 per hub. Label & urutan persis tabel unit (Komisi &
    Insentif tidak ada lagi di Penjualan — MN-T1; Kontrol dua orang di Persetujuan — KF-T6).
  - Enam view baru = bagian layar wadah lama, komponen sama dengan prop `only`, tanpa bilah tab dalam bila tinggal satu
    bagian: `settings-pt-profile`/`settings-pt-readiness`/`settings-accounts`/`settings-role-check` (+ `permission-matrix`
    kini tab nyata) → `EntitiesAccessView only`; `settings-attendance-devices`/`settings-devices` → `DevicesView only`;
    `scheduler`/`settings-whatsapp` → `SchedulerView only`. Isi bagian tidak berubah; kartu angka & "Jalankan Semua" ikut
    bagiannya; judul dalam Penjadwal mengikuti tab (Pengingat Otomatis / WhatsApp).
  - Alamat lama (`viewAliases.js`, `since: "KP-T9"`): `entities-access` → Profil PT (rute cadangan tetap, label "Badan Usaha
    & Akses" di palet); `settings-purchasing` → Aturan Pembelian & Makloon, `settings-rnd` → R&D & Desain,
    `settings-masters` → Master per PT, `settings-notify` → Pengingat Otomatis (keempatnya `legacy`).
  - `inheritsHiddenFrom` (hubTabs) + `roles.hiddenByRoleSetting` → `hubTabsForRole`: lima tab pecahan tersembunyi bila
    `hidden_views` memuat `entities-access`; Mesin Absen bila `settings-devices`/`hr-attendance-setup`; WhatsApp bila
    `scheduler`; Perangkat RFID bila `cs-rfid-devices`. Untuk peran kustom hanya `hidden_views` (bukan `remove` turunan
    tingkat modul) — lihat Menyimpang 3. Editor peran menulisnya: centang mati + "(ikut disembunyikan bersama …)".
  - `PAGE_META`: enam id baru + semua tab Pengaturan ber-kicker "Pengaturan · {hub}"; tab berganti label → judul = label.
  - Istilah PT: "Semua Entitas" → **Semua PT** (pemilih PT, + teks cadangan/judul/placeholder "PT"); "Harga per PT",
    "Transfer Antar-PT", "Akun Sosmed · per PT", kicker "Antar-PT", "Transaksi Antar-PT · Jual-Beli dalam Grup"; katalog
    modul: `interco` "Transaksi Antar-PT", modul `entities` **"Data PT"**, `RESOURCE_LABEL["entity"]` "PT", deskripsi modul
    tanpa "badan usaha/entitas". Pesan 403 modul PT kini mengambil nama modul dari katalog (`module_label_of`).
- Berkas: `frontend/src/config/{navStructure,hubTabs,navMeta,viewAliases,navigationConfig,roles}.js`, `AppViewRouter.jsx`,
  `appViewImports.js`, `features/settings/entities/{EntitiesAccessView,EntityCompletionSteps,RoleNavTree}.jsx`,
  `features/settings/devices/DevicesView.jsx`, `features/admin/scheduler/SchedulerView.jsx`, `components/EntitySwitcher.jsx`,
  `features/pdf/PdfTemplateDesigner.jsx`; `backend/access_modules.py`, `routers/{entities,settings}.py`,
  `services/{entity_lifecycle,entity_readiness}_service.py`.
- Fixture vs proses: U6–U9 lewat API (peran dibuat `POST /api/access/roles`); U10 konteks akses disuntik di jest.
- Status: implemented_pending_review

## KP-29 (bagian tautan) — pengaturan di luar grup Pengaturan tanpa petunjuk
- Berlaku di HEAD: ya (butir 10; merah U12 — komponen belum ada).
- Perubahan: peta `SETTINGS_LINKS` (`configGroupViews.js`) + komponen `features/settings/cfg/SettingsLinkCards.jsx`
  (`LinkCard hideWhenDenied`, judul kecil "Pengaturan terkait di menu lain") di bawah daftar kartu `SettingsGroupView`:
  Aturan Keuangan & Pajak → "Jadwal bayar antar-PT" (Keuangan › Antar-PT), "Rekening bank dan kas tiap PT" (Keuangan › Kas &
  Bank › Rekening & Saldo), "Syarat pembayaran" (Pengaturan › Perusahaan (PT) › Master per PT); Aturan Gudang & Mutu →
  "Daftar gudang dan lokasi" (Gudang & Logistik › Data Gudang); tab WhatsApp (rute di bawah layar) → "WhatsApp untuk
  mengirim dokumen dan aturan kirim otomatis" (Pusat Dokumen › Daftar Dokumen). Teks letak = breadcrumb menu tujuan (dijaga
  uji). Peran tanpa akses layar tujuan tidak melihat kartunya.
- Status: implemented_pending_review

## KF-UX-28 (bagian menu) — penjaga katalog & teks letak
- Berlaku di HEAD: ya (butir 6, 12; merah U1, U11).
- Perubahan:
  - `access_modules.py` blok `KP-T9` (`_KPT9_NAV_REPLACE/ADD/REMOVE`): hub hilang diganti hub barunya di tiap modul;
    `entities` + Profil/Kesiapan PT; `accounts` + Pengguna & Hak Akses/Akun; `roles` + Pengguna & Hak Akses/Peran & Hak
    Akses/Cek Peran; `hr` + Mesin Absen, − Sistem/Perangkat RFID; `scheduler` + Dokumen & Notifikasi/WhatsApp; hub induk:
    `finance_ops` + Penjualan (Alasan Koreksi), `documents` + `settings-hub`, `product` + `settings-hub`/Sistem (Impor Data
    Awal); `accounts`/`roles` − Perusahaan (PT).
  - `verify_access_catalog_nav.py`: aturan (3) tab tampak hub Pengaturan wajib bermodul, (4) modul pemuat tab Pengaturan
    wajib memuat hub induk + `settings-hub`; rute `[...].includes(activeView)` dikenal; `--self-test` 9 kasus, didaftarkan
    di `scripts/gate.sh` (statik). `check_nav_map.py` CHECK 6: `label`/`title`/`kicker` tiga berkas menu tanpa
    "Entitas"/"Badan Usaha".
  - Teks letak "Pengaturan › …" (40-an berkas `frontend/src` + `backend`, termasuk komentar) memakai nama hub & tab baru;
    juga petunjuk lain yang menunjuk menu lama ("Badan Usaha & Akses → Akun", "Pengaturan › Penerimaan", "Pusat Pengaturan
    › Stok, Satuan & Alokasi", "Pusat Pengaturan › Harga, Diskon & Komisi", "Pengaturan › Penjualan › Komisi & Insentif").
    "Lengkapi" daftar kesiapan PT menuju `settings-pt-profile` / `settings-accounts` (data lama `entities-access` + `tab`
    tetap dipetakan di layar).
- Status: implemented_pending_review

## Dokumen ikut berubah

`docs/KN_13_NAVIGATION_MAP.md` (bagian baru "MENU PENGATURAN (KP-T9)" dibangkitkan dari konfigurasi: hub › tab › peran,
alamat lama, tab dalam yang tersisa, kartu tautan; changelog), `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (§9.5 baru:
label lama → baru, "Semua PT", modul "Data PT"; kolom "Tempat" baris KP-T1/T2/T6/T7 ke letak baru), `CODEBASE_MAP.md`
(generator). `docs/LOCAL_DEV.md` tidak menyebut letak menu Pengaturan (dicek). `memory/PRD.md`/`ENTITY_REGISTRY.md` hanya
memuat catatan riwayat unit lain — tidak diubah. Arsip UAT (`docs/uat/…`) tidak diubah.

## Uji penerimaan

Merah di kode lama: berkas uji final dijalankan pada salinan `git archive a742da9` (`bukti/KP-T9/tests_mem_merah_kode_lama.log`,
`jest_merah_kode_lama.log`). Hijau: `tests_mem_hijau_kode_baru.log`, `jest_hijau_kode_baru.log`.

| ID | Lapis | Merah di kode lama | Hasil kode baru |
|---|---|---|---|
| U1 | statik (tests_mem) | ya — mutasi `settings-accounts` dicabut → 0 temuan (aturan 3 & 4 tidak ada); `self_test` tidak ada | Lulus — 0 temuan; mutasi → 1 temuan aturan (3) + 1 aturan (2) (Menyimpang 2); mutasi `finance_ops` tanpa `settings-sales` / `documents` tanpa `settings-hub` → tepat 1 temuan aturan (4); `--self-test` 9/9 |
| U2 | statik (tests_mem) | ya — `check_terms` tidak ada; enam id baru tanpa judul | Lulus — `check_nav_map` CHECK 1/3/4/5/6 hijau (158 layar berjudul; 0 label "Entitas"/"Badan Usaha"); `verify_view_aliases` + uji-diri hijau (162 cek, 27 alias); INV-UI-13 0 / INV-UI-14 0 (41 → 41 berkas); `audit_config_wiring --strict` keluar 0 |
| U3 | komponen | ya (12 hub + 2 sub-judul; hub lama ada) | Lulus — 9 hub berurutan, label persis, tanpa sub-judul; tab tiap hub persis tabel; 3–6 tab; **35** tab; empat id hub lama = alias `legacy` `since: "KP-T9"`; tab pecahan ber-`inheritsHiddenFrom` |
| U4 | komponen | ya (mis. `entities-access` → `entities-access`, `settings-access` null) | Lulus — 44 alamat (31 id tab lama termasuk `permission-matrix` & `incentive-rates`, 4 hub hilang, 5 alias lama, 4 id hub) → layar & hub tabel lama → baru; preset `dasar`/`rfid`/`pemberitahuan` terbawa |
| U5 | komponen | tidak — potret = keadaan kode lama (penjaga regresi; potret `bukti/KP-T9/potret_jangkauan_awal.json`) | Lulus — 13 peran × (tanpa / dengan izin server): jangkauan tab Pengaturan dipetakan ke wadah lama = potret. + manajer dengan izin server: Pengguna & Hak Akses hanya Akun (tanpa izin `permission`), SDM + Mesin Absen, Sistem tanpa Integrasi & Audit / Perangkat RFID / Impor Data Awal (merah di lama: hub `settings-access` tidak ada) |
| U6 | B | ya — `settings-attendance-devices` tidak ada di menu modul SDM | Lulus — + `settings-hub`, `settings-hr`, `settings-cfg-hr`, `hr-attendance-setup`, `settings-attendance-devices`; tanpa `settings-system`, `settings-devices` |
| U7 | B | ya — modul PT memberi `settings-masters`, tanpa Profil/Kesiapan PT | Lulus — PT saja: Perusahaan (PT) + Profil & Kesiapan PT, tanpa Pengguna & Hak Akses; Peran saja: Pengguna & Hak Akses + Peran & Hak Akses + Cek Peran, tanpa Profil PT; Akun saja: Akun tanpa Peran |
| U8 | B | ya — `remove` tidak memuat id hub/tab baru (bagian `add` tanpa `settings-*` memang sudah berlaku di lama) | Lulus — `add` tanpa id `settings-*`; `remove` memuat semua hub & tab baru (warisan Manajer tercabut) |
| U9 | B | ya — `settings-accounts` 400 "Menu/tab tidak dikenal" | Lulus — 200 + tersimpan; `settings-tidak-ada` → 400 "Menu/tab tidak dikenal: settings-tidak-ada" |
| U10 | komponen | ya — tab pecahan tidak ada | Lulus — `hidden_views ["entities-access"]` → Perusahaan (PT) hanya Master per PT, Pengguna & Hak Akses kosong, alamat `entities-access`/`settings-pt-profile` tertutup; `settings-devices` → Mesin Absen ikut; `scheduler` → WhatsApp ikut; `cs-rfid-devices` → Perangkat RFID; `remove` turunan modul tidak menyembunyikan |
| U11 | statik (tests_mem) | ya — puluhan teks "Pengaturan › Integrasi & Sistem/Dokumen & Cetak/Master Data …" | Lulus — 0 kemunculan nama hub lama di teks "Pengaturan › …" `frontend/src` + `backend` (termasuk komentar & teks terpotong di akhir baris) |
| U12 | komponen | ya — komponen `SettingsLinkCards` tidak ada (varian bukti dengan tiruan: 18 dari 19 uji berkas itu merah) | Lulus — admin: 3 kartu (Antar-PT, Rekening & Saldo, Master per PT) di Aturan Keuangan & Pajak; peran tanpa izin kas: kartu Rekening tidak tampil; Aturan Gudang & Mutu: Data Gudang; WhatsApp: Pusat Dokumen; teks letak = breadcrumb menu |
| U13 | layar (uji jalan) | — | **Dipotret** integrator (menu Pengaturan admin, Profil PT, Sistem 1024 px) — lihat "Cek layar (potret integrator)" |
| tambahan | komponen | ya | Lulus — bagian `only` Badan Usaha & Akses (5), Perangkat (2), Penjadwal (2): tanpa bilah tab dalam, isi bagian benar, preset Profil PT membuka detail PT, tombol buka Akun lewat jalur navigasi baku, kalimat Z6 bila bagian tanpa izin; pemilih "Semua PT"; Lengkapi → tab baru (data lama dipetakan); editor peran menulis tab yang ikut tersembunyi |
| tambahan | B / statik | ya | Lulus — katalog modul tanpa "badan usaha"/"entitas" (`entity` = "PT", `interco` = "Transaksi Antar-PT"); kesiapan PT menuju `settings-pt-profile`/`settings-accounts`, semua tujuan = layar menu |
| A | A (ditulis) | — | `backend/tests/test_bp_KPT9_hub_pengaturan.py`: U6, U7, U9, kesiapan PT di MongoDB asli. **Lulus** (4 uji, lingkungan A) |

`backend/tests_mem`: **1253 lulus / 2 dilewati / 4 xfail → 1263 lulus / 2 dilewati / 4 xfail** (+10 uji KP-T9; uji lama
disesuaikan: `test_KPT2` U12b nama modul "Data PT", `test_KPT8` kalimat koneksi WhatsApp, `test_KFT2` teks kunci penomoran
lot). `tests/test_fe03_access_catalog.py --noconftest` 6/6 (daftar manajer diperbarui ke hub baru). Jest seluruhnya: HEAD
121 suite (86 lulus, 35 gagal dimuat radix) / 662 uji → 123 suite (88 lulus, **35 gagal dimuat yang sama**) / **715 uji,
semua lulus** (+53 uji baru). Dengan tiruan pemilih: `phase3Settings` 13/13; `phase3P8Activation` 1 gagal **sama persis**
di HEAD dan kode baru (D-01 Desainer PDF peran kustom — tidak disentuh unit ini).

## Penjaga statik (sebelum → sesudah)

| Penjaga | Sebelum | Sesudah |
|---|---|---|
| `hitung_penjaga.sh` (16 statik) | auth 28 · ui_standard 15 · i18n 109 · create_modal 6 · page_tabs 1 (INV-UI-12, berkas lama di luar unit) · to_list 6 · entity_label 2 · lainnya 0 | **identik** (`bukti/KP-T9/penjaga_sebelum_sesudah.log`) |
| `verify_page_tabs` INV-UI-13 / INV-UI-14 | 0 / 0 (41 berkas tingkat 3) | 0 / 0 (41 berkas; `EntitiesAccessView`, `DevicesView` tetap di baseline — `PageTabs` masih ada untuk mode utuh) |
| `verify_access_catalog_nav` | 0 temuan (aturan 1–2) | 0 temuan (aturan 1–4) + `--self-test` 9/9 (baru di `gate.sh`) |
| `verify_view_aliases` (+ uji-diri) | PASS 132 cek, 22 alias | PASS 162 cek, 27 alias; uji-diri hijau |
| `check_nav_map` (salinan berjalur) | PASS (CHECK 1–5) | PASS (CHECK 1–6) |
| `verify_role_gate_ui` (+ uji-diri) | PASS 31/0 | PASS 31/0 |
| `audit_config_wiring --strict` (salinan berjalur) | keluar 0 | keluar 0 (442 kunci, registry 434) |
| `verify_config_text`, `verify_config_fallback` (+ `--entity`) | PASS | PASS (3052 / 145 / 145 cek) |
| `verify_desk_targets`, `verify_codebase_map` | 0 / PASS | 0 / PASS (`CODEBASE_MAP.md` dibangkitkan ulang: + `SettingsLinkCards.jsx`) |
| ESLint berkas tersentuh | 2 peringatan lama (`AttendanceSetupView:77`, `PdfTemplateDesigner:158`) | sama |

## Cek layar (`docs/KN_37_STANDAR_UI_GUDANG.md`, butir pemilik 14 Nov)

Belum dipotret (tanpa peramban di lingkungan ini; integrator memotret 1280/1024/390 px). Dicek dari kode + uji komponen.
Kelas baru hanya token (`text-fs-12/13`, `text-kn-*`, `section-card section-pad`); `verify_ui_standard` identik (15),
tidak ada hex/huruf < 12 px baru.

| Butir | Sidebar Pengaturan (9 hub) | Bilah tab hub | Profil PT / Kesiapan PT / Akun / Peran & Hak Akses / Cek Peran | Mesin Absen / Perangkat RFID | Pengingat Otomatis / WhatsApp | Kartu tautan (Keuangan, Gudang, WhatsApp) | Pemilih PT · editor peran |
|---|---|---|---|---|---|---|---|
| 1 tabel melebihi kartu | — | — | isi bagian tidak diubah; tidak ada tabel baru | isi tidak diubah | isi tidak diubah | tidak ada tabel | — |
| 2 bantalan kartu | — | — | kalimat tanpa izin: `section-card section-pad` | — | — | `LinkCard` baku (bantalan sendiri) | — |
| 3 kepala padat | label terpanjang "Gudang, Pembelian & Produksi" — label sidebar boleh 2 baris (L-05) | 6 tab di Sistem: ±870 px label → di 1024 px bilah membungkus 2 baris; di ≤ 640 px bergulir (aturan `.tab-bar` lama) | bilah tombol (Tambah PT hanya di Profil PT + Muat ulang) di baris sendiri, rata kanan | — | tanpa tab dalam; "Jalankan Semua" hanya di Pengingat Otomatis | satu kalimat + tombol "Buka" (`flex-wrap` di HP) | — |
| 4 tombol mati + alasan | — | — | tidak ada tombol mati baru | — | — | kartu disembunyikan bila tak berwenang (bukan tombol mati) | centang tab yang ikut tersembunyi mati **dengan alasan di samping** "(ikut disembunyikan bersama …)" |
| 5 status ikon+teks+warna | — | — | kalimat tanpa izin: ikon + teks | — | — | — | — |
| 6 daftar tanpa cari | 9 butir | — | — | — | — | ≤ 3 kartu | pemilih PT tetap cari otomatis > 8 PT |
| 7 teks vs izin | — | — | kalimat tanpa izin pola Z6 "Anda belum punya akses … Minta Admin menambahkan akses '{modul}'." (hanya bila tab terlihat tetapi bagian butuh izin lain) | pengantar Perangkat kini menunjuk tab lain ("Mesin absen karyawan diatur di Pengaturan › SDM › Mesin Absen"), bukan "di satu tempat" | judul dalam = label tab | — | "Semua PT · hanya lihat" |
| 8 kosong ganda / angka 0 | — | — | — | — | WhatsApp: satu kartu angka (Pesan WhatsApp), bukan empat | tidak tampil bila kosong | — |

Temuan di layar yang tidak diubah unit ini (di luar lingkup — isi layar, pemilik unit lain): `RfidDevicesView` menulis
"Mode baca-saja. Perubahan perangkat memerlukan peran admin." (gerbang nama peran `role === "admin"`, wilayah RFID H7);
pita pengantar `EntitiesAccessView` ("Satu perusahaan, beberapa badan usaha…") kini tampil di kelima tab pecahan dan masih
memakai "badan usaha" + hex lama (KP-T1/KP-T2/PR-T6); judul dalam "Label Alasan Amandemen", "Impor Dataset Klien",
"Registri Domain", "Master Grade Mutu" belum mengikuti label tab baru (kepala layar dalam komponen — di luar lingkup unit).

## Menyimpang dari blueprint

1. **Perangkat RFID (`settings-devices`) `roles: ["admin"]`**, bukan `["admin", "manager"]`: bagian RFID layar lama khusus admin
   (`roleCanSee(["admin"], role, "cs-rfid-devices")`), dan isinya untuk non-admin berbunyi "Mode baca-saja … memerlukan peran
   admin". Dengan "admin, manager" manajer mendapat tab yang dulu tidak pernah ia lihat (U5 & U13). Manajer tetap menjangkau
   wadah lama lewat Mesin Absen (U5 = potret). Peran kustom lewat modul Operasi Gudang / Perangkat seperti sebelumnya.
2. **U1 — dua temuan, bukan satu**: mencabut `settings-accounts` dari semua modul membuat modul Akun Pengguna memberi hub
   Pengguna & Hak Akses tanpa satu pun tabnya → aturan (2) juga merah. Uji menegaskan tepat satu temuan aturan (3) + satu
   aturan (2). Usulan koreksi di bawah.
3. **`inheritsHiddenFrom` untuk peran kustom = `hidden_views` saja**: `ROLE_NAV.remove` peran kustom adalah turunan tingkat
   modul (menu modul "Tidak ada"), bukan pilihan sembunyi — peran bermodul SDM saja memuat `settings-devices` di `remove`
   sehingga Mesin Absen akan hilang (bertentangan dengan U6). `ROLE_NAV.remove` dipakai untuk peran bawaan. Fungsi
   `roles.hiddenByRoleSetting`; `hubTabsForRole` sendiri ada di `navigationConfig.js` (spesifikasi menyebut `roles.js`).
   `inheritsHiddenFrom` menerima daftar: Mesin Absen ← `settings-devices` + `hr-attendance-setup`, Perangkat RFID ←
   `cs-rfid-devices` (gerbang bagian lama `DevicesView` memakai kedua id itu — `hidden_views` lama tetap berlaku).
4. **Katalog modul — hub induk tambahan** (aturan 4): `finance_ops` + `settings-sales` (Alasan Koreksi), `documents` +
   `settings-hub` (Template Dokumen), `product` + `settings-hub`/`settings-system` (Impor Data Awal, `product.import`);
   `accounts`/`roles` − `settings-company` (aturan 2). `entities-access` tetap di tiga modul (alias + `hidden_views`).
5. **Nama modul `entities` "Data PT"** (dulu "Badan Usaha (PT)"; spesifikasi: PT di katalog modul). Empat pesan 403 yang
   menulis nama itu kini memakai `module_label_of("entity")` (`routers/entities.py`, `routers/settings.py`,
   `services/entity_lifecycle_service.py`); `test_KPT2` U12b disesuaikan.
6. **Daftar kesiapan PT (server)**: butir profil/akun `view` → `settings-pt-profile` / `settings-accounts` (+ `how_to`
   "Pengaturan › Pengguna & Hak Akses › Akun"); `tab` lama tetap dikirim. Layar memetakan data lama `entities-access` + `tab`.
   Tautan "Ubah di Profil PT" Desainer PDF (KP-T6) → `settings-pt-profile` preset `{entity_id}`.
7. **Kulit layar per bagian**: Penjadwal — kartu angka, "Jalankan Semua", dan judul dalam ikut bagiannya; Perangkat —
   kalimat pengantar menunjuk tab lain (dulu "di satu tempat"). Isi tiap bagian tidak diubah.
8. **`PAGE_META`**: kicker semua tab Pengaturan "Pengaturan · {hub}" (bukan hanya yang berganti label); judul `admin`
   "Master Data & Audit" → "Integrasi & Audit"; `entities-access` "Profil PT (alamat lama)" (dipakai editor peran).
9. **Teks letak di luar daftar U11** ikut diperbarui (petunjuk yang menunjuk menu lama: "Badan Usaha & Akses → Akun",
   "Pengaturan › Penerimaan", "Pusat Pengaturan › Stok, Satuan & Alokasi", "Pusat Pengaturan › Harga, Diskon & Komisi",
   "Pengaturan › Penjualan › Komisi & Insentif", "Pengaturan › Pengguna", "Pengaturan › Perangkat RFID"); label tautan
   kunci `receiving.mode` "Penerimaan Barang › Mode Penerimaan"; `aria-label` Shift & Lokasi Absen / Penerimaan Barang.
10. **Label palet untuk id hub lama** ("Pembelian & Produksi", "Master Data", "Notifikasi & Penjadwal") — mitigasi RISIKO
    unit; `settings-rnd` tanpa label (label tab "R&D & Desain" sudah memuat "R&D").
11. **Editor peran** (`RoleNavTree`): tab yang ikut tersembunyi bersama wadahnya ditulis centang mati + "(ikut disembunyikan
    bersama …)" — tanpa ini editor menampilkan tab "tampil" padahal tersembunyi.
12. **U5 diperluas** dengan Finance (Pemetaan Akun sejak MN-T1) dan mode dengan izin server; **U8 diperketat** dengan `remove`.
13. Uji lama disesuaikan (disengaja): `phase3Settings` (sembilan hub, `nav` Pembelian/R&D), `navAccess` (peran kustom
    modul Admin & SDM), `roleReach` (`KPT9_PART_TABS` di `ROLE_REACH_ADDITIONS` admin/manajer), `serverAccessReach`
    (`SERVER_GATED.manager = ["permission-matrix"]` — dulu mendarat di bagian Badan Usaha karena bagian Peran disaring izin),
    `kpt2LengkapiPt` (tujuan tab baru), `test_fe03_access_catalog` (daftar hub manajer); fixture akses dibangkitkan ulang.

## Usulan koreksi blueprint (teks pengganti persis)

- `unit/KP-T9.md` § Layar, tabel lama → baru baris 25, kolom "Terlihat oleh": ganti `admin, manager` dengan `admin`.
- `unit/KP-T9.md` § Uji penerimaan U1, kolom hasil: ganti `bila `settings-accounts` dicabut dari semua modul → 1 temuan` dengan
  `bila `settings-accounts` dicabut dari semua modul → 1 temuan aturan (3), ditambah 1 temuan aturan (2) karena modul Akun Pengguna kini memberi hub `settings-access` tanpa tab`.
- `unit/KP-T9.md` § Uji penerimaan U5, kolom hasil: ganti `sales_admin hanya `return-policies` dan `grade-master`; peran lain tidak melihat grup` dengan
  `sales_admin hanya `return-policies` dan `grade-master`; finance hanya `gl-account-mappings` (MN-T1); peran lain tidak melihat grup`.
- `unit/KP-T9.md` § Layar, baris `hubTabs.js`, `roles.js`: ganti `hubTabsForRole menyembunyikannya bila id wadah lama ada di hidden_views atau ROLE_NAV.remove peran itu` dengan
  `hubTabsForRole (navigationConfig.js) menyembunyikannya bila id wadah lama ada di hidden_views peran itu, atau di ROLE_NAV.remove peran bawaan (remove peran kustom = turunan tingkat modul, tidak dihitung)`.
- `unit/KP-T9.md` § Keadaan sekarang butir 1 (pada `a742da9`): `Grup Pengaturan berisi 12 butir hub dan 2 sub-judul; 12 hub itu memuat 29 tab tampak dan 1 alias tersembunyi. Tiga hub ber-tab tunggal: Pembelian & Produksi, R&D, Notifikasi & Penjadwal`.

## Asumsi

- `ASUMSI` unit terpenuhi: PR-T2/PR-T5 selesai (modul dipecah; empat tab sudah bermodul); `incentive-rates` sudah dipindah
  MN-T1 → hub 4 berisi tiga tab; penjaga "enam tab" dan "tab-dalam" MN-T1 ada (INV-UI-13/14) dan dipakai.
- Tab Penomoran Dokumen (KP-T5) sudah ada → hub 8 empat tab, ditaruh terakhir (urutan tabel unit).
- `roles` tab pecahan = gerbang bagian lamanya (lihat Menyimpang 1 untuk Perangkat RFID).
- Nama modul `entities` "Data PT" (spesifikasi: PT menggantikan "Badan Usaha" di katalog modul; nama persisnya tidak disebut).

## Titik henti

Tidak ada butir H1–H8 yang disentuh. Berkas `features/rfid/*` hanya diubah **teks petunjuk letak** (tanpa logika gerbang);
`rfid_ingest_service`, `rfid_service`, `gate_evaluator`, `middleware/`, `services/rfid_v2_*` tidak disentuh (teks lama di
`rfid_v2_retention.py` docstring dibiarkan). Tidak ada data yang diubah (H3): `hidden_views` tersimpan tidak disentuh.

## Hambatan lingkungan

- Potret dan lapis A dijalankan integrator (lihat "Penggabungan", "Cek layar (potret integrator)").
- Jest lokal: 35 suite lama gagal dimuat (`@radix-ui/primitive/is-development`), identik di HEAD; `phase3Settings` dijalankan
  dengan tiruan pemilih (salinan saja, pola PK-13).
- `check_nav_map.py` membaca `/app/frontend/src` (= repo utama) → dijalankan lewat salinan berjalur worktree.

## Penggabungan

Dikerjakan di `a742da9`; digabung di atas `27f0853`/`27efaa4` (PK-30, PK-42, PM-T1): `access_modules.py`, `bootstrap.py`,
`entity_master_service.py`, `gate.sh`, fixture akses digabung tiga arah tanpa bentrok; peta kode dibangkitkan ulang.
tests_mem 1313; jest 751/751; lapis A 4 lulus. Catatan: `scripts/check_nav_map.py` memakai jalur `/app` tetap, jadi bila
dijalankan dari salinan kerja ia memeriksa pohon utama (memerah palsu CHECK 6 sebelum digabung); dengan jalur salinan
dan sesudah digabung: PASS. Usulan koreksi blueprint diterapkan di `a3838f5`.

## Cek layar (potret integrator)

Dipotret di lingkungan A (`admin@`, data acuan).

| Temuan | Perbaikan |
|---|---|
| Menu Pengaturan admin: 9 hub (Perusahaan (PT), Pengguna & Hak Akses, Persetujuan, Penjualan, Gudang, Pembelian & Produksi, Keuangan & Pajak, SDM, Dokumen & Notifikasi, Sistem) tanpa sub-judul | Sesuai spesifikasi |
| Profil PT: tab bernama "Profil PT", tetapi isi layar "Daftar Badan Usaha", "3 badan usaha", "Tambah Badan Usaha", pita "Satu perusahaan, beberapa badan usaha" | Hanya layar ini: "Daftar PT", "{n} PT", "Tambah PT", "Jenis badan hukum", "Satu grup, beberapa PT …" (`ad17fa0`); "badan usaha" di layar lain tetap untuk unit pemiliknya (L2) |
| 1024 px: SEMUA layar bergulir mendatar 117 px — teks "Lokasi kerja belum diatur — minta admin …" di bilah atas tidak bisa menyusut (cacat lama, bukan dari unit ini) | Di bawah 1280 px teks disembunyikan; ikon peringatan + tooltip + petunjuk menu tetap (`26e5dfc`); 1024/1280/1366 px → luapan 0 |
| Hub Sistem 6 tab di 1024 px | Membungkus menjadi dua baris (diterima, L3) |

Bukti: `bukti/KP-T9/menu_pengaturan_admin_1280.png`, `layar_profil_pt_1280_sebelum_istilah.png`,
`layar_profil_pt_1280_sesudah.png`, `layar_sistem_1024_bilah_atas_meluap.png`, `bilah_atas_1024_sesudah.png`.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan; tiga skrip seed yang sama seperti garis dasar
gagal), di `a3838f5` (KP-T9 `b95bd0d` + cek visual `26e5dfc`, `ad17fa0`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 14 FAIL | 16 | 1 (ganti nama `guard:page_tabs`, merah garis dasar yang sama) | 2 (`config_wiring` + uji-diri) |
| `--ci` | 41 FAIL | 43 | 1 (ganti nama) | 2 |

`guard:page_tabs`: INV-UI-13 (≤ 6 tab per hub) dan INV-UI-14 (tanpa tab tingkat ketiga) hijau dengan susunan sembilan hub;
merah INV-UI-12 tetap `wms/InventoryStockView.jsx` (berkas lama). `check_nav_map` (CHECK 6 istilah) dan
`verify_access_catalog_nav` (aturan 3 & 4 + uji-diri) hijau di gate.


## Yang perlu direview

- Menyimpang 1 (Perangkat RFID khusus admin) dan 3 (`inheritsHiddenFrom` hanya `hidden_views` untuk peran kustom).
- Peran kustom yang menyembunyikan **id hub lama** (`settings-purchasing`, `settings-rnd`, `settings-masters`,
  `settings-notify`): id itu tidak dikenal katalog lagi dan dibuang saat dimuat (aturan MN-T1), sehingga tab di hub barunya
  tampil menurut modul. Tidak dicek di data nyata (H3).
- Modul Produk kini membuka Pengaturan › Sistem › Impor Data Awal untuk peran kustom ber-`product` (endpoint
  `product.import`); dulu id tab itu ada di modul tetapi hubnya tidak — pintu mati.

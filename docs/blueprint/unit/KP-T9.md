# KP-T9 — Menu Pengaturan menjadi sembilan hub dengan satu istilah "PT"

| | |
|---|---|
| Gelombang | Jalur menu (M) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | MN-T1, KF-T4 |
| Menutup temuan | KP-33; bagian tautan dari KP-29 (penyimpanannya ditutup KF-T2); bagian menu dari KF-UX-28 |
| Keputusan | K-46 |
| Standar | §3.2 (butir 2), §4 (L1, L2, L3, L7), §7 |
| Lingkungan uji | B untuk katalog modul; uji statik dan uji komponen; uji jalan layar di A |

## Tujuan

Pemilik menemukan setiap layar pengaturan dari sembilan butir menu yang urutannya mengikuti cara mengisi PT baru: PT →
orang → persetujuan → aturan per bagian → dokumen → sistem. Tidak ada hub ber-tab tunggal, alamat lama tetap membuka
layar yang benar, peran kustom tetap mendapat menu yang sesuai izinnya, dan menu memakai satu kata: "PT".

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`, kecuali butir 6 dan 11 yang `[dijalankan]` (dihitung dengan skrip atas
`MODULE_CATALOG` dan berkas menu). MN-T1 dan KF-T4 mengubah berkas yang sama sebelum unit ini; nomor baris akan bergeser.

| # | Fakta | Jangkar |
|---|---|---|
| 1 | Grup Pengaturan berisi 12 butir hub dan 2 sub-judul; 12 hub itu memuat 30 tab tampak dan 1 alias tersembunyi. Tiga hub ber-tab tunggal: Perusahaan & Akun, Pembelian & Produksi, R&D | `frontend/src/config/navStructure.js:406` (`settings-hub`); `frontend/src/config/hubTabs.js:238` (`settings-company`); `frontend/src/config/hubTabs.js:265` (`settings-cfg-purchasing`); `frontend/src/config/hubTabs.js:280` (`settings-cfg-rnd`) |
| 2 | Sembilan tab adalah wadah ber-tab-dalam (sumber menyebut tujuh): Badan Usaha & Akses 5, Template Dokumen 2, Penjadwal & Notifikasi 3, Perangkat 2, Penerimaan & OCR 4, Aturan & Template Bank 2, Shift & Geofence 2, Semua pengaturan 5, Integrasi & Audit 2 | `frontend/src/features/settings/entities/EntitiesAccessView.jsx:28` (`TABS`); `frontend/src/features/pdf/DocTemplatesView.jsx:50` (`dasar`); `frontend/src/features/admin/scheduler/SchedulerView.jsx:22` (`TABS`); `frontend/src/features/settings/devices/DevicesView.jsx:41` (`absen`); `frontend/src/features/settings/ReceivingOcrSettings.jsx:11` (`profiles`); `frontend/src/features/finance/bank/BankRulesSettingsView.jsx:40` (`rules`); `frontend/src/features/hr/AttendanceSetupView.jsx:128` (`geofence`); `frontend/src/features/settings/config/SettingsHub.jsx:45` (`TABS`); `frontend/src/features/admin/AdminView.jsx:232` (`PageTabs`) |
| 3 | Cara membuka satu bagian dari layar wadah sudah ada: rute dengan `initialTab`, komponen ber-`only`, alias ber-`preset`, dan tab tersembunyi ber-`aliasOf` | `frontend/src/AppViewRouter.jsx:144` (`EntitiesAccessView`); `frontend/src/AppViewRouter.jsx:139` (`only`); `frontend/src/features/hr/AttendanceSetupView.jsx:48` (`only`); `frontend/src/config/viewAliases.js:47` (`cs-rfid-devices`); `frontend/src/config/hubTabs.js:241` (`aliasOf`); `frontend/src/config/navigationConfig.js:52` (`hubForView`) |
| 4 | Menu peran kustom dihitung dari tingkat modulnya setiap registry peran dimuat (tidak disimpan); peran kustom tanpa peran acuan hanya melihat tab yang id-nya ada di `nav` salah satu modul | `backend/role_registry.py:273` (`nav_for_levels`); `backend/access_modules.py:259` (`nav_for_levels`); `frontend/src/config/roles.js:385` (`roleCanSee`) |
| 5 | Id hub Pengaturan tersebar di `nav` banyak modul; satu modul "Pengaturan, Pengguna & Hak Akses" memuat lima hub sekaligus | `backend/access_modules.py:50` (`settings-purchasing`); `backend/access_modules.py:166` (`settings-devices`); `backend/access_modules.py:207` (`settings-company`) |
| 6 | Empat tab tampak tidak ada di `nav` modul mana pun: `settings-receiving-ocr`, `incentive-rates`, `amendment-reasons`, `bank-recon-rules`. Penjaga katalog tidak menangkapnya karena hanya memeriksa id yang ada di katalog; layar-layar itu masih bergerbang nama peran | `backend/access_modules.py:16` (`MODULE_CATALOG`); `scripts/guardrails/verify_access_catalog_nav.py:34` (`scan`); `backend/routers/incentive_rates.py:45` (`require_role`) |
| 7 | Tab yang disembunyikan per peran kustom disimpan (`hidden_views`) dan hanya menerima id yang dikenal katalog | `backend/services/custom_role_service.py:257` (`all_nav_ids`) |
| 8 | Admin Sales melihat Pengaturan lewat tambahan menu `settings-hub`, `settings-sales`, `settings-warehouse`. Peran Finance tercantum pada tab Pemetaan Akun, tetapi butir hub-nya hanya untuk Admin dan Manajer | `frontend/src/config/roles.js:201` (`settings-warehouse`); `frontend/src/config/hubTabs.js:269` (`gl-account-mappings`); `frontend/src/config/navStructure.js:417` (`settings-finance`) |
| 9 | Penjaga yang harus tetap hijau: alias wajib punya rute cadangan `activeView === "<lama>"` dan `since`; tiap layar wajib punya judul di `PAGE_META`; `settings-config` wajib ada di menu; tab buatan sendiri tidak boleh bertambah | `scripts/guardrails/verify_view_aliases.py:16` (`activeView`); `scripts/check_nav_map.py:489` (`PAGE_META`); `scripts/audit_config_wiring.py:263` (`settings-config`); `scripts/guardrails/verify_page_tabs.py:48` (`count`) |
| 10 | Layar pengaturan di luar grup Pengaturan (KP-29): jadwal bayar antar-PT di layar Antar-PT; WhatsApp dokumen di Pusat Dokumen; rekening dan kas di Kas & Bank; gudang di Data Gudang. Asumsi retur sudah berada di Pengaturan › Penjualan › Kebijakan Retur | `frontend/src/features/finance/interco/IntercoPaymentSchedule.jsx:36` (`interco_payment`); `frontend/src/features/documents/DocumentCenter.jsx:275` (`WhatsAppSettings`); `frontend/src/config/hubTabs.js:160` (`bank-accounts`); `frontend/src/config/navStructure.js:285` (`md-warehouses`); `frontend/src/features/sales/ReturnPoliciesView.jsx:7` (`ReturnAssumptionsPanel`) |
| 11 | Empat kata untuk satu hal: "Perusahaan & Akun" (hub), "Badan Usaha & Akses" (tab), "… Entitas, Akun, Kesiapan" (judul), "Antar Entitas (Grup)" dan "Semua Entitas". 14 label di tiga berkas menu dan 8 teks di katalog modul memuat "Badan Usaha" atau "Entitas" | `frontend/src/config/navStructure.js:411` (`settings-company`); `frontend/src/config/hubTabs.js:239` (`entities-access`); `frontend/src/config/navMeta.js:175` (`entities-access`); `frontend/src/config/navStructure.js:332` (`interco-transactions`); `frontend/src/components/EntitySwitcher.jsx:67` (`viewAll`); `backend/access_modules.py:67` (`interco`) |
| 12 | Petunjuk letak di layar menyebut nama hub lama | `frontend/src/features/settings/masters/EntityMastersView.jsx:30` (`DOMAIN_HOME`); `frontend/src/features/settings/cfg/SettingsGroupView.jsx:46` (`settings-all-link`) |

## Perubahan

### Data

Tidak ada koleksi atau field baru. `hidden_views` yang tersimpan tidak diubah; perlakuannya ada di bagian "Layar".

### Server

`backend/access_modules.py` — aturan umum: **modul yang memuat id tab Pengaturan juga memuat id hub induknya dan
`settings-hub`**. Modul disebut menurut sumber daya izinnya, karena PR-T5 sudah memecah modul "Pengaturan, Pengguna &
Hak Akses" sebelum unit ini.

| Id di `MODULE_CATALOG[*].nav` | Perubahan |
|---|---|
| `settings-purchasing`, `settings-rnd` | Diganti `settings-warehouse` di tiap modul yang memuatnya |
| `settings-masters` | Diganti `settings-company` (modul pemuat `entity-masters`) atau `settings-system` (modul pemuat `domain-registry`, `client-dataset-import`) |
| `settings-notify` | Diganti `settings-documents` |
| `settings-pt-profile`, `settings-pt-readiness` (baru) | Modul pemegang `entity`, bersama `settings-company` |
| `settings-access`, `settings-accounts`, `permission-matrix`, `settings-role-check` | Modul pemegang `user` (Akun) dan `permission` (Peran & Hak Akses, Cek Peran) |
| `settings-attendance-devices` (baru) | Modul `hr`; `settings-system` dan `settings-devices` dicabut dari modul `hr` |
| `settings-devices` | Tetap di modul operasi gudang bersama `settings-system` |
| `settings-whatsapp` (baru) | Modul pemegang `scheduler`, bersama `settings-documents` |
| `settings-receiving-ocr`, `incentive-rates`, `amendment-reasons`, `bank-recon-rules` | Masuk modul pemilik izin yang diperiksa endpoint layarnya (hasil PR-T2), bersama hub induknya |
| `entities-access`, `settings-cfg-documents`, `settings-cfg-notify` | Tetap (alias yang masih punya rute) |

Label ikut istilah PT: modul `interco` "Transaksi Antar-PT"; `RESOURCE_LABEL["entity"]` "PT"; kata "badan usaha" dan
"entitas" pada deskripsi modul ditulis "PT".

`scripts/guardrails/verify_access_catalog_nav.py` mendapat dua aturan: (3) tiap tab tampak pada hub `settings-*` ada di
`nav` minimal satu modul; (4) modul yang memuat tab Pengaturan memuat hub induknya dan `settings-hub`.
`scripts/check_nav_map.py` mendapat satu pemeriksaan: `label`, `title`, dan `kicker` di `navStructure.js`, `hubTabs.js`,
`navMeta.js` tidak memuat "Entitas" atau "Badan Usaha".

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada pasangan izin baru. Daftar `roles` tiap tab disalin apa adanya dari tab lamanya (kolom terakhir tabel "lama →
baru"); butir hub memakai `roles` yang sama dengan hub lamanya, dan `settings-access` memakai `["admin", "manager"]`.
`ROLE_NAV` Admin Sales tidak berubah karena `settings-sales` dan `settings-warehouse` tetap ada.

### Layar

Grup `settings-hub` (id tetap) berisi sembilan butir tanpa sub-judul. Hub yang bertahan memakai id lamanya.

| # | Id hub · label | Tab berurutan (id · label) |
|---|---|---|
| 1 | `settings-company` · **Perusahaan (PT)** | `settings-pt-profile` Profil PT · `settings-pt-readiness` Kesiapan PT · `entity-masters` Master per PT |
| 2 | `settings-access` (baru) · **Pengguna & Hak Akses** | `settings-accounts` Akun · `permission-matrix` Peran & Hak Akses · `settings-role-check` Cek Peran |
| 3 | `settings-approval` · **Persetujuan** | `approval-rules` Aturan Persetujuan · `rnd-divisions` Persetujuan R&D · `settings-cfg-approval` Ketegasan, Pengingat & Dokumen |
| 4 | `settings-sales` · **Penjualan** | `settings-cfg-sales` Aturan Penjualan · `incentive-rates` Komisi & Insentif · `return-policies` Kebijakan Retur · `amendment-reasons` Alasan Koreksi |
| 5 | `settings-warehouse` · **Gudang, Pembelian & Produksi** | `settings-cfg-warehouse` Aturan Gudang & Mutu · `settings-receiving-ocr` Penerimaan Barang · `grade-master` Grade Mutu · `settings-cfg-purchasing` Aturan Pembelian & Makloon · `settings-cfg-rnd` R&D & Desain |
| 6 | `settings-finance` · **Keuangan & Pajak** | `settings-cfg-finance` Aturan Keuangan & Pajak · `gl-account-mappings` Pemetaan Akun · `expense-categories` Kategori Beban · `bank-recon-rules` Bank |
| 7 | `settings-hr` · **SDM** | `settings-cfg-hr` Aturan SDM & Penggajian · `hr-attendance-setup` Shift & Lokasi Absen · `settings-attendance-devices` Mesin Absen |
| 8 | `settings-documents` · **Dokumen & Notifikasi** | `pdf-templates` Template Dokumen · `scheduler` Pengingat Otomatis · `settings-whatsapp` WhatsApp · tab "Penomoran Dokumen" hanya bila layar KP-T5 sudah ada |
| 9 | `settings-system` · **Sistem** | `admin` Integrasi & Audit · `settings-devices` Perangkat RFID · `domain-registry` Kamus Aturan Kain · `client-dataset-import` Impor Data Awal · `settings-cfg-system` AI & Tampilan · `settings-config` Cari Semua Pengaturan |

Jumlah: 9 hub, 34 tab tampak (35 dengan Penomoran Dokumen), paling banyak 6 per hub. Perbedaan dari usulan sumber
(`lampiran/C_konfigurasi_perusahaan.md` §5.2) dan alasannya:

| Usulan sumber | Di unit ini | Alasan |
|---|---|---|
| Tab "Rekening, Kas & Gudang (ringkasan + tautan)" | Tidak dibuat; diganti kartu tautan (tabel KP-29) | Layar baru; unit ini tidak mengubah isi layar (`00` §7 butir 4) |
| "Syarat Pembayaran", alasan keluhan retur, dan lini/tahapan/jenis sampling dipecah ke tiga hub | `entity-masters` tetap satu tab "Master per PT" di hub 1 | Memecahnya mengubah isi layar; hub Master Data tetap hilang |
| "Kop & Tanda Tangan per PT" terpisah dari "Template Dokumen" | Satu tab `pdf-templates` | Kedua tab dalamnya sama-sama memuat kop; pemisahannya bagian KP-T6 |
| Tab "Aturan Dokumen" dan "Penerima Notifikasi" | Sudah menjadi alias ke `settings-cfg-approval` sejak KF-T4 | Kelompok "Persetujuan, pengingat & dokumen" tampil utuh di hub 3; dengan dua tab itu hub 8 menjadi 7 tab |
| "Integrasi" dan "Riwayat & Audit" dua tab; "Data Awal & Rujukan" satu tab | `admin` satu tab; `domain-registry` dan `client-dataset-import` dua tab | Tidak ada layar gabungan; hub 9 tepat 6 tab |

Tabel lengkap lama → baru. "tab dalam" = bagian layar wadah yang dinaikkan menjadi tab hub:

| # | Id layar lama · label lama | Hub lama → baru | Id tab baru · label baru | Alias yang ditinggalkan | Terlihat oleh (`roles` tab) |
|---|---|---|---|---|---|
| 1 | `entities-access` Badan Usaha & Akses — tab dalam "Badan Usaha" | `settings-company` → tetap | `settings-pt-profile` · Profil PT | `entities-access` → `settings-pt-profile` | admin, manager |
| 2 | — tab dalam "Kesiapan" | `settings-company` → tetap | `settings-pt-readiness` · Kesiapan PT | — | admin, manager |
| 3 | — tab dalam "Akun & Akses" | `settings-company` → `settings-access` | `settings-accounts` · Akun | — | admin, manager |
| 4 | `permission-matrix` (alias tersembunyi) dan tab dalam "Peran & Hak Akses" | `settings-company` → `settings-access` | `permission-matrix` · Peran & Hak Akses (kini tab nyata) | — | admin, manager |
| 5 | — tab dalam "Cek Peran" | `settings-company` → `settings-access` | `settings-role-check` · Cek Peran | — | admin, manager |
| 6 | `approval-rules` Aturan Persetujuan | `settings-approval` → tetap | tetap | — | admin, manager |
| 7 | `rnd-divisions` Divisi & Persetujuan R&D | `settings-approval` → tetap | id tetap · Persetujuan R&D | — | admin, manager |
| 8 | `settings-cfg-approval` | `settings-approval` → tetap | id tetap · Ketegasan, Pengingat & Dokumen (label KF-T4) | `settings-cfg-documents`, `settings-cfg-notify` (sejak KF-T4) | admin, manager |
| 9 | `settings-cfg-sales` Aturan Penjualan | `settings-sales` → tetap | tetap | — | admin, manager |
| 10 | `incentive-rates` Komisi & Insentif | `settings-sales` → tetap | tetap, urutan ke-2 | — | admin, manager |
| 11 | `return-policies` Kebijakan Retur | `settings-sales` → tetap | tetap, urutan ke-3 | — | admin, manager; Admin Sales lewat `ROLE_NAV` |
| 12 | `amendment-reasons` Label Alasan Amandemen | `settings-sales` → tetap | id tetap · Alasan Koreksi | — | admin, manager |
| 13 | `settings-cfg-warehouse` Aturan Gudang & Mutu | `settings-warehouse` → tetap | tetap | — | admin, manager |
| 14 | `settings-receiving-ocr` Penerimaan & OCR | `settings-warehouse` → tetap | id tetap · Penerimaan Barang | — | admin, manager, warehouse_admin |
| 15 | `grade-master` Master Grade Mutu | `settings-warehouse` → tetap | id tetap · Grade Mutu | `settings-hub` (alias lama) tetap ke sini | admin, manager, md, sales_admin, warehouse_admin, md_quality, qc |
| 16 | `settings-cfg-purchasing` Aturan Pembelian & Makloon | `settings-purchasing` → `settings-warehouse` | tetap | id hub `settings-purchasing` → `settings-cfg-purchasing` | admin, manager |
| 17 | `settings-cfg-rnd` R&D & Desain | `settings-rnd` → `settings-warehouse` | tetap | id hub `settings-rnd` → `settings-cfg-rnd` | admin, manager |
| 18 | `settings-cfg-finance` Aturan Keuangan & Pajak | `settings-finance` → tetap | tetap | — | admin, manager |
| 19 | `gl-account-mappings` Pemetaan Akun | `settings-finance` → tetap | tetap | — | admin, manager, finance |
| 20 | `expense-categories` Kategori Beban | `settings-finance` → tetap | tetap | — | admin, manager |
| 21 | `bank-recon-rules` Aturan & Template Bank | `settings-finance` → tetap | id tetap · Bank | — | admin, manager |
| 22 | `settings-cfg-hr` SDM & Penggajian | `settings-hr` → tetap | id tetap · Aturan SDM & Penggajian | — | admin, manager |
| 23 | `hr-attendance-setup` Shift & Geofence | `settings-hr` → tetap | id tetap · Shift & Lokasi Absen | — | admin, manager |
| 24 | `settings-devices` Perangkat — tab dalam "Mesin absen" | `settings-system` → `settings-hr` | `settings-attendance-devices` · Mesin Absen | — | admin, manager |
| 25 | `settings-devices` Perangkat — tab dalam "RFID" | `settings-system` → tetap | `settings-devices` · Perangkat RFID | `cs-rfid-devices` tetap ke sini | admin, manager |
| 26 | `entity-masters` Master per Badan Usaha | `settings-masters` → `settings-company` | id tetap · Master per PT | id hub `settings-masters` → `entity-masters` | admin, manager |
| 27 | `domain-registry` Registri Domain | `settings-masters` → `settings-system` | id tetap · Kamus Aturan Kain | — | admin, manager |
| 28 | `client-dataset-import` Impor Dataset Klien | `settings-masters` → `settings-system` | id tetap · Impor Data Awal | — | admin |
| 29 | `pdf-templates` Template Dokumen | `settings-documents` → tetap | tetap | `doc-templates-basic` tetap ke sini | admin, manager |
| 30 | `scheduler` Penjadwal & Notifikasi — tab dalam "Job Terjadwal", "Riwayat Eksekusi" | `settings-notify` → `settings-documents` | `scheduler` · Pengingat Otomatis | id hub `settings-notify` → `scheduler` | admin, manager |
| 31 | — tab dalam "WhatsApp" | `settings-notify` → `settings-documents` | `settings-whatsapp` · WhatsApp | — | admin, manager |
| 32 | `settings-config` Semua pengaturan | `settings-system` → tetap | id tetap · Cari Semua Pengaturan, urutan terakhir | — | admin, manager |
| 33 | `settings-cfg-system` | `settings-system` → tetap | id tetap · AI & Tampilan (label KF-T4) | — | admin, manager |
| 34 | `admin` Integrasi & Audit | `settings-system` → tetap | tetap, urutan pertama | — | admin |

| Berkas | Kontrak |
|---|---|
| `frontend/src/config/viewAliases.js` | Entri baru ber-`since: "KP-T9"`: `entities-access` → `{to: "settings-pt-profile", nav: "settings-company", label: "Badan Usaha & Akses"}`; empat id hub lama ber-`legacy: true`: `settings-purchasing` → `settings-cfg-purchasing` (`nav: "settings-warehouse"`), `settings-rnd` → `settings-cfg-rnd` (`nav: "settings-warehouse"`), `settings-masters` → `entity-masters` (`nav: "settings-company"`), `settings-notify` → `scheduler` (`nav: "settings-documents"`). Alias lama tidak diubah |
| `frontend/src/AppViewRouter.jsx` | Rute enam id baru dan `permission-matrix` merender komponen yang sama dengan satu bagian saja: `EntitiesAccessView only="entities" \| "readiness" \| "accounts" \| "roles" \| "role-reality"`; `DevicesView only="absen" \| "rfid"`; `SchedulerView only={["jobs", "runs"]}` atau `only={["wa"]}`. Rute `entities-access` dipertahankan (bagian "entities") |
| Tiga komponen wadah di atas | Prop baru `only`: bilah tab dalam tidak dirender bila hanya satu bagian yang tersisa; isi tiap bagian tidak diubah |
| `frontend/src/config/hubTabs.js`, `roles.js` | Tab pecahan mendapat `inheritsHiddenFrom: "<id wadah lama>"` (`entities-access`, `settings-devices`, `scheduler`); `hubTabsForRole` menyembunyikannya bila id wadah lama ada di `hidden_views` atau `ROLE_NAV.remove` peran itu |
| `frontend/src/config/navMeta.js` | `PAGE_META` untuk enam id baru dan semua tab yang berganti label: `kicker` "Pengaturan · {label hub}", `title` = label tab |
| Teks petunjuk letak | Setiap teks "Pengaturan › …" di `frontend/src` dan `backend` memakai nama hub dan tab baru (mis. "Pengaturan › Sistem › Cari Semua Pengaturan") |

Tautan untuk pengaturan yang berada di luar grup (KP-29) — kartu `LinkCard` ber-`hideWhenDenied`, didaftarkan di peta
baru `SETTINGS_LINKS` (`configGroupViews.js`) dan dirender `SettingsGroupView` di bawah daftar kartu; teks letak
mengikuti nama menu saat unit dikerjakan:

| Tampil di tab | Kalimat tautan | Tujuan |
|---|---|---|
| Aturan Keuangan & Pajak | "Jadwal bayar antar-PT" | `interco-transactions` |
| Aturan Keuangan & Pajak | "Rekening bank dan kas tiap PT" | `bank-accounts` |
| Aturan Keuangan & Pajak | "Syarat pembayaran" | `entity-masters` |
| Aturan Gudang & Mutu | "Daftar gudang dan lokasi" | `md-warehouses` |
| WhatsApp (dirender rute di bawah layar) | "WhatsApp untuk mengirim dokumen dan aturan kirim otomatis" | `document-center` |

Istilah — "PT" menggantikan "Perusahaan" (sebagai badan hukum), "Badan Usaha", dan "Entitas" di tiga berkas menu,
katalog modul, dan pemilih PT; satu-satunya pengecualian adalah nama hub "Perusahaan (PT)":

| Tempat | Lama → baru |
|---|---|
| `hubTabs.js`, `navMeta.js` | "Harga per Badan Usaha" → "Harga per PT"; "Transfer Antar-Entitas" → "Transfer Antar-PT"; "Akun Sosmed · per Badan Usaha" → "Akun Sosmed · per PT"; kicker "Antar Entitas" → "Antar-PT"; "Transaksi Antar Entitas · Jual-Beli Antar-PT" → "Transaksi Antar-PT · Jual-Beli dalam Grup" |
| `navStructure.js` | "Antar Entitas (Grup)" → "Antar-PT" (bila belum diganti MN-T1) |
| `frontend/src/components/EntitySwitcher.jsx` | "Semua Entitas" → "Semua PT"; teks cadangan "Badan usaha" → "PT" |

Tab dalam yang tersisa — **menyimpang dari standar §4 L3 karena** unit ini tidak mengubah isi layar dan menaikkannya
akan melampaui enam tab per hub: Penerimaan Barang (4), Bank (2), Pengingat Otomatis (2), Template Dokumen (2), Shift &
Lokasi Absen (2), Integrasi & Audit (2), Cari Semua Pengaturan (5). Tujuh layar ini menjadi batas atas pada penjaga
tab-dalam; unit pemilik layarnya (KP-T6, KP-T7, KP-T8) boleh menurunkannya.

## Uji penerimaan

Persiapan bersama: potret jangkauan menu peran bawaan dan daftar alias pada awal unit; peran uji baku `02` §6.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | statik | — | `python scripts/guardrails/verify_access_catalog_nav.py` | 0 temuan, termasuk aturan (3) dan (4); bila `settings-accounts` dicabut dari semua modul → 1 temuan |
| U2 | statik | — | `python scripts/guardrails/verify_view_aliases.py` dan `--self-test`; `python scripts/check_nav_map.py`; `python scripts/guardrails/verify_page_tabs.py`; `python scripts/audit_config_wiring.py --strict` | Tiga yang pertama hijau (enam id baru berjudul; 0 label memuat "Entitas"/"Badan Usaha"); penjaga tab tidak naik; penjaga pengaturan tidak bertambah merah |
| U3 | uji komponen | — | Baca `NAV_STRUCTURE` dan `HUB_TABS` | Grup `settings-hub` berisi tepat 9 butir berurutan: `settings-company`, `settings-access`, `settings-approval`, `settings-sales`, `settings-warehouse`, `settings-finance`, `settings-hr`, `settings-documents`, `settings-system`; tiap hub 3–6 tab tampak; jumlah 34 (35 dengan Penomoran Dokumen) |
| U4 | uji komponen | Peran admin | `resolveDeepLinkTarget(id, "admin")` untuk 31 id tab lama, 4 id hub yang hilang, dan `settings-hub`, `doc-templates-basic`, `cs-rfid-devices`, `settings-cfg-documents`, `settings-cfg-notify` | Tiap id menghasilkan layar dan hub pada tabel lama → baru; contoh: `entities-access` → `settings-pt-profile` di `settings-company`; `settings-notify` → `scheduler` di `settings-documents`; `settings-cfg-rnd` → dirinya di `settings-warehouse`; tidak ada yang `null` |
| U5 | uji komponen | Potret awal | Jangkauan tab Pengaturan tiap peran bawaan (id baru dipetakan ke wadah lamanya) | Sama dengan potret: manager semua kecuali `admin` dan `client-dataset-import`; warehouse_admin hanya `settings-receiving-ocr` dan `grade-master`; sales_admin hanya `return-policies` dan `grade-master`; peran lain tidak melihat grup |
| U6 | B | Peran **Tanpa Acuan** dengan modul `hr` "Lihat saja" | Baca menu peran itu dari jawaban daftar peran | Memuat `settings-hub`, `settings-hr`, `settings-cfg-hr`, `hr-attendance-setup`, `settings-attendance-devices`; tidak memuat `settings-system`, `settings-devices` |
| U7 | B | Peran **Tanpa Acuan** dengan modul pemegang `entity` saja; lalu modul pemegang `permission` saja | Baca menu peran | Pertama: `settings-company`, `settings-pt-profile`, `settings-pt-readiness`, tanpa `settings-access`. Kedua: `settings-access`, `permission-matrix`, `settings-role-check`, tanpa `settings-pt-profile` |
| U8 | B | Peran **Manajer Kosong** | Baca menu peran | Tidak memuat satu pun id `settings-*` |
| U9 | B | Peran kustom | Simpan `hidden_views: ["settings-accounts"]`, lalu `["settings-tidak-ada"]` | 200; lalu ditolak dengan pesan id tidak dikenal |
| U10 | uji komponen | Peran kustom ber-`hidden_views: ["entities-access"]` | `hubTabsForRole("settings-company", peran)` dan `("settings-access", peran)` | Lima tab pecahan tidak tampil; `entity-masters` tetap tampil |
| U11 | statik | — | Cari nama hub lama pada teks "Pengaturan › …" di `frontend/src` dan `backend`: "Perusahaan & Akun", "Pembelian & Produksi", "Master Data", "Dokumen & Cetak", "Notifikasi & Penjadwal", "Integrasi & Sistem" | 0 kemunculan |
| U12 | uji komponen | — | Render `SettingsGroupView` untuk `settings-cfg-finance` sebagai admin, lalu sebagai peran tanpa izin kas | Tiga kartu tautan tampil; untuk peran kedua kartu "Rekening bank dan kas tiap PT" tidak tampil |
| U13 | layar (uji jalan) | Login admin, manager, warehouse_admin, sales_admin, dan satu peran Tanpa Acuan bermodul `hr` | Buka tiap tab pada sembilan hub; buka `?view=entities-access` dan `?view=settings-purchasing` | Tidak ada tab yang berujung "tidak berwenang"; dua alamat lama membuka Profil PT dan Aturan Pembelian & Makloon; pemilih PT menulis "Semua PT" |

## Langkah kerja

1. Cek ulang tabel lama → baru terhadap `hubTabs.js` hasil MN-T1 dan KF-T4; simpan potret jangkauan peran dan alias.
2. Tulis uji U1–U12 (merah): uji komponen di `frontend/src/config/__tests__/`, uji B di `backend/tests_mem/`.
3. Prop `only` pada tiga komponen wadah; rute enam id baru; `PAGE_META`.
4. `navStructure.js` dan `hubTabs.js` sesuai tabel sembilan hub; `viewAliases.js`; `inheritsHiddenFrom`.
5. `access_modules.py` dan dua aturan baru penjaga katalog; pemeriksaan istilah di `check_nav_map.py`.
6. Kartu tautan KP-29; teks petunjuk letak; istilah PT.
7. Perbarui uji lama yang menegaskan susunan lama (`phase3Settings.test.js`, `roleReach.test.js`, `viewAliases.test.js`).
8. U13; gate; laporan.

## Dokumen ikut berubah

`docs/KN_13_NAVIGATION_MAP.md` (grup Pengaturan); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("PT", "Semua PT");
`docs/LOCAL_DEV.md` dan dokumen lain yang menyebut letak menu Pengaturan lama, bila ada.

## Di luar lingkup

- Isi layar dan kepala layar di dalam komponen (mis. judul "Badan Usaha & Akses" di dalam layar) → KP-T1, KP-T2, PR-T6.
- Satu layar Aturan Persetujuan untuk semua antrean → KP-T3, KP-T4. Tab Penomoran Dokumen → KP-T5.
- Pemisahan kop per PT dari template → KP-T6. Penerima dan ambang pengingat → KP-T7. Integrasi dan perangkat → KP-T8.
- Memindahkan penyimpanan jadwal bayar antar-PT dan asumsi retur ke registry → KF-T2.
- Menu keuangan dan SDM, termasuk pemindahan Komisi & Insentif ke Kinerja & Insentif → MN-T1, KM-T5.
- Tab tampil menurut izin, bukan daftar nama peran (mis. Finance pada Pemetaan Akun) → PR-T7.
- Kata "entitas" dan "badan usaha" di dalam layar selain menu dan pemilih PT → unit pemilik tiap layar (L2).

## Asumsi dan risiko

- `ASUMSI:` PR-T2 dan PR-T5 selesai lebih dulu (rantai prasyarat MN-T1), sehingga empat layar pada butir 6 sudah
  memeriksa izin dan modul "Pengaturan, Pengguna & Hak Akses" sudah dipecah. Bila belum, id tab masuk modul yang ada.
- `ASUMSI:` `incentive-rates` masih berada di hub Penjualan. Bila MN-T1 sudah memindahkannya, baris 10 dilewati dan hub 4
  berisi tiga tab.
- `ASUMSI:` penjaga "enam tab" dan "tab-dalam" yang dijanjikan MN-T1 berbentuk batas yang hanya boleh turun. Bila
  belum ada, batas enam tab per hub diperiksa uji U3 saja.
- `ASUMSI:` label "Kamus Aturan Kain", "Impor Data Awal", "Shift & Lokasi Absen", "Alasan Koreksi", "Grade Mutu", dan
  "Bank" diturunkan dari usulan sumber §5.2; label "Persetujuan R&D" dan "Master per PT" dari istilah KF-T4.
- `RISIKO:` peran kustom yang menyembunyikan `settings-devices` atau `scheduler` kini juga tidak melihat Mesin Absen
  atau WhatsApp (`inheritsHiddenFrom`). Itu perilaku yang sama dengan sebelum tab dinaikkan.
- `RISIKO:` pengguna kehilangan letak yang biasa. Ditangani alias, label lama pada palet perintah (`label` alias), dan
  uji U4. Membatalkan unit = mengembalikan lima berkas menu dan `access_modules.py`; tidak ada data yang berubah.

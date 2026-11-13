# MN-T1 — Menu keuangan dan SDM: pindah dan kelompokkan tanpa mengubah isi layar

| | |
|---|---|
| Gelombang | Jalur menu (sejajar gelombang 3–7) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | PR-T5 |
| Menutup temuan | UX-17, IA-06, IA-15 |
| Keputusan | K-09, K-17, K-18, K-46 |
| Standar | §3.1 (Z2), §3.2, §4 (L1, L2, L3, L7), §6, §7 |
| Lingkungan uji | B (izin ↔ endpoint) · uji komponen frontend · uji jalan layar di A |

## Tujuan

Pekerjaan keuangan tampil sebagai **10 entri dalam 2 grup** (dari 18 entri dalam 4 grup), sub-tab keuangan dan insentif
keluar dari CRM dan Pengaturan, dan tiap peran melihat persis entri yang izinnya ia pegang. Semua alamat lama tetap
membuka layar yang benar. Isi layar tidak diubah.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| # | Fakta | Jangkar |
|---|---|---|
| 1 | Grup Keuangan 7 entri; Akuntansi & Pajak 7; Kas & Aset 3; Hutang Pemasok di grup Pembelian | `frontend/src/config/navStructure.js:298` (`keuangan`) · `frontend/src/config/navStructure.js:320` (`akuntansi`) · `frontend/src/config/navStructure.js:339` (`kas-aset`) · `frontend/src/config/navStructure.js:222` (`accounts-payable`) |
| 2 | CRM punya tujuh sub-tab di dalam tab hub, empat di antaranya keuangan atau insentif; dua digerbang nama peran | `frontend/src/features/crm/CrmView.jsx:20` (`TABS`) · `frontend/src/features/crm/CrmView.jsx:19` (`roleIs`) |
| 3 | "Komisi & Insentif" berada di Pengaturan › Penjualan; hub KPI berisi satu tab | `frontend/src/config/hubTabs.js:254` (`incentive-rates`) · `frontend/src/config/hubTabs.js:202` (`hr-kpi-hub`) |
| 4 | Menu peran Finance ditulis tangan: tanpa Rekening & Saldo, Rekonsiliasi Bank, Buku Besar, Kas Kecil, Hutang — padahal izinnya memuat `cash`, `accounting.view`, `cash_advance`, `cash_settlement` (UX-17) | `frontend/src/config/roles.js:251` (`finance`) · `backend/permissions_config.py:346` (`finance`) |
| 5 | "Kasus Keuangan" mencantumkan sales, tetapi grup induknya hanya admin dan manager, dan peran bawaan mengikuti `roles` grup → Sales tidak pernah melihatnya walau memegang `finance_case.view/create` (IA-06) | `frontend/src/config/navStructure.js:312` (`finance-cases`) · `frontend/src/config/navigationConfig.js:148` (`isModuleNavRole`) · `backend/permissions_config.py:131` (`finance_case`) |
| 6 | Tab "Pemetaan Akun" mencantumkan finance, tetapi menu Finance tidak memuat grup Pengaturan (IA-06) | `frontend/src/config/hubTabs.js:269` (`gl-account-mappings`) |
| 7 | "Cairkan" uang muka hanya dipegang admin | `backend/permissions_config.py:96` (`cash_advance`) |
| 8 | Menu peran kustom diturunkan dari `nav` tiap modul. Di HEAD `reimburse-payables`, `incentive-rates`, `finance-desk` tidak ada di modul mana pun (PR-T2 dan PR-T5, prasyarat, memasukkannya); `finance-tower` dibuka modul kas padahal layarnya menuntut `accounting.view` | `backend/access_modules.py:16` (`MODULE_CATALOG`) · `backend/access_modules.py:140` (`finance-tower`) |
| 9 | Penjaga tab hanya menghitung pola tab buatan sendiri; tidak ada batas jumlah tab per hub dan tidak ada pemeriksaan tab di dalam tab hub | `scripts/guardrails/verify_page_tabs.py:44` (`count`) |
| 10 | Hub `products-pricing` sudah 8 tab tampak; `purchase-orders` 6 | `frontend/src/config/hubTabs.js:38` (`products-pricing`) · `frontend/src/config/hubTabs.js:57` (`purchase-orders`) |
| 11 | Layar yang menjadi tab hub dan punya tab lagi di dalamnya sudah ada, mis. Jurnal & Buku Besar (5 tab) | `frontend/src/features/finance/GeneralLedger.jsx:41` (`TABS`) |
| 12 | Beranda peran Finance = `finance-desk`, ditulis di dua tempat yang harus sama | `frontend/src/config/navMeta.js:226` (`finance`) · `backend/role_registry.py:95` (`home_view`) |
| 13 | Jangkauan peran dijaga uji berbaseline; tambahan sah dicatat per peran | `frontend/src/config/__tests__/roleReach.test.js:14` (`ROLE_IDS`) |
| 14 | Alias layar dijaga aturan A–F; alias bukan `legacy` wajib tetap punya rute cadangan | `scripts/guardrails/verify_view_aliases.py:16` (`legacy`) |

## Perubahan

### Data

Tidak ada koleksi baru. `hidden_views` peran kustom yang memuat id `kas-aset` dibuang saat dimuat (id grup itu hilang).

### Server

**Katalog modul** (`backend/access_modules.py`) — ditulis menurut **sumber daya izin**, karena PR-T5 mungkin sudah
memecah modulnya. Aturan: tiap id menu atau tab masuk `nav` modul yang memuat sumber daya yang dituntut endpoint utama
layarnya, bersama id grup dan id hub induknya.

| Modul pemilik sumber daya | `nav` ditambah | `nav` dicabut |
|---|---|---|
| `accounting` | `keuangan`, `finance-tower`, `bi-finance`, `cash-bank`, `petty-cash` | `kas-aset` |
| `cash`, `finance_case` | `ar-aging` (induk tab Kasus) | `finance-tower` |
| `ar_receipt`, `payment_plan`, `penalty`, `payment_variance` | `customer-credit`, `finance-tower`, `finance-desk` (bila PR-T5 belum memasukkannya) | — |
| `order` | `keuangan`, `ar-aging`, `collection-worklist`, `hrd`, `hr-kpi-hub`, `sales-performance` | — |
| `customer` | `keuangan`, `ar-aging`, `credit-overrides` | — |
| `vendor_bill`, `contra_bon` | `keuangan` | `pembelian` (kecuali masih dibutuhkan tab lain) |
| `landed_cost` | `pembelian`, `purchase-orders`, `landed-cost` | `accounts-payable` |
| `interco`, `interco_finance` | `keuangan` | `akuntansi` |
| `cash_advance`, `cash_settlement` | `keuangan`, `cash-bank`, `petty-cash` | `kas-aset` |
| `vehicle_log` | `gudang` | `kas-aset` |
| `sales_force` (modul hasil PR-T2; di HEAD masih gerbang nama peran) | `hrd`, `hr-kpi-hub`, `incentive-schemes` (`incentive-rates` sudah di sana) | `settings-sales` bila tidak ada tab lain modul itu di hub tersebut |

`LINK_ALIASES["finance"]` tetap. `home_nav_id` peran finance di `backend/role_registry.py` menjadi `finance-tower`
(`home_view` tetap `finance-desk`).

**Izin bawaan peran Finance menurut K-09 dan K-17** (ditambahkan lewat sumber izin bawaan hasil PR-T9; bila PR-T9 belum
selesai, lewat `GRANT` di `backend/bootstrap.py:460`; hanya menambah, tidak mencabut). PK-24 dan PK-38 memuat baris
yang sama dengan catatan "lewati bila sudah ada"; siapa pun yang lebih dulu, hasilnya sama:

| Hal | Pasangan izin | Di HEAD | Sesudah unit ini |
|---|---|---|---|
| Rekonsiliasi Bank (K-09: ya) | `cash.view`, `cash.create` | sudah | tetap; menunya ditambah |
| Buku Besar lihat saja (K-09) | `accounting.view` | sudah | tetap; tombol tulis mengikuti izin tulis yang tidak ia pegang |
| Hutang: melihat | `vendor_bill.view`, `contra_bon.view` | tidak | ditambah |
| Hutang: membayar (K-17) | `vendor_bill.pay`, `contra_bon.pay` | tidak | ditambah |
| Mencairkan uang muka (K-17) | `cash_advance.disburse` | hanya admin | ditambah untuk finance dan manager |

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada pasangan izin baru; yang berubah adalah pemegang bawaan (tabel di atas) dan menu per peran (di bawah).

### Layar

**Tabel lama → baru.** Peran: A admin · M manager · F finance · S sales · SA sales_admin · G warehouse · GA
warehouse_admin. "Izin layar" = yang dituntut endpoint utamanya di HEAD. Id yang tidak disebut berubah tetap sama.

| Entri › tab baru (label persis) | id menu · view | Berasal dari | Alias / id lama | Izin layar | Peran bawaan |
|---|---|---|---|---|---|
| **Keuangan › Beranda Keuangan** › Perlu Tindakan | `finance-tower` · `finance-desk` | Meja Finance (menu lepas dan grup Meja Peran) | entri lepas dan butir Meja Peran dihapus; view tetap | `payment_variance.decide` | A M F |
| › Posisi | · `finance-tower` | Dasbor Keuangan › Posisi & Kontrol | — | `accounting.view` | A M F |
| › Analisis | · `bi-finance` | Dasbor Keuangan › BI Keuangan | — | `accounting.view` | A M F |
| **Keuangan › Piutang** › Saldo & Umur | `ar-aging` (kini hub) · `ar-aging` | Keuangan › Piutang | — | `accounting.view` atau `penalty.issue` | A M F |
| › Penagihan & Penerimaan | · `collection-worklist` (baru) | CRM › sub-tab Penagihan | — | `order.view` | A M F S SA |
| › Rencana & Denda | · `payment-plans` | Keuangan › Rencana Bayar | view sama | `payment_plan.view` | A M F |
| › Titipan & Saldo Kredit | · `customer-credit` (baru, pembungkus) | Keuangan › Uang Muka Pelanggan dan Saldo Kredit | `advance-report` → `{bagian: "titipan"}`; `store-credit` → `{bagian: "saldo"}` | sama dengan Saldo & Umur; `ar_receipt.view` | A M F |
| › Kredit & Plafon | · `credit-overrides` (baru) | CRM › sub-tab Persetujuan Kredit | — | `customer.view`; memutus `credit_override.approve` (hasil PR-T2) | A M F (F tanpa hak memutus) |
| › Kasus | · `finance-cases` | Keuangan › Kasus Keuangan | view sama | `finance_case.view` | A M F S SA |
| **Keuangan › Hutang** › Tagihan | `accounts-payable` · `vendor-bills` | Pembelian › Hutang Pemasok › Tagihan Supplier | — | `vendor_bill.view` | A M F |
| › Kontrabon | · `contra-bons` | … › Kontrabon (Tukar Faktur) | — | `contra_bon.view` | A M F G GA |
| **Keuangan › Kas & Bank** › Rekening & Saldo · Transaksi Kas · Rekonsiliasi | `cash-bank` · `bank-accounts`, `cash-management`, `bank-reconciliation` | tetap ("Rekonsiliasi Bank" → "Rekonsiliasi") | — | `cash.view` | A M F |
| › Kas Kecil | · `petty-cash` (dulu id hub; kini view pembungkus) | Kas & Aset › Kas Kecil (3 tab) | `cash-advances`, `settlements`, `reimburse-payables` → `{bagian: …}`; id grup `kas-aset` → alias `legacy` | `cash_advance.view` atau `cash_settlement.view` | A M F S SA |
| **Keuangan › Antar-PT** | `interco-transactions` | Akuntansi & Pajak › Antar Entitas (Grup) | view sama | `interco.view` | A M F G GA SA |
| **Akuntansi & Pajak › Buku Besar** › Jurnal · Bagan Akun | `ledger` · `general-ledger`, `chart-of-accounts` | "Jurnal & Buku Besar", "Chart of Accounts" | — | `accounting.view` | A M F |
| **› Tutup Buku** › Daftar Periksa & Tutup · Buka Periode · Posting Gagal | `closing` (kini hub) · `closing`, `period-unlock`, `posting-failures` | tiga entri terpisah | view sama | `accounting.view` | A M |
| **› Laporan** › Laba-Rugi, Neraca & Arus Kas · Profitabilitas · Proyeksi Kas · Anggaran · Konsolidasi | `fin-reports` · id tetap | label lama: "Profitabilitas & Margin", "Proyeksi Arus Kas", "Anggaran vs Realisasi", "Konsolidasi Grup" | — | `accounting.view`, `budget.view` | A M |
| **› Pajak** › Faktur Keluaran · Faktur Masukan · PPN & PPh | `tax-hub` · id tetap | "Pajak (PPN & PPh)" | — | `tax_invoice.view`, `input_tax.view`, `accounting.view` | A M; F hanya Faktur Keluaran |
| **› Aset Tetap** | `fixed-assets` | Kas & Aset › Aset Tetap | view sama | `fixed_asset.view` | A M |
| **Pembelian › Pesanan Pembelian** › Landed Cost | `purchase-orders` · `landed-cost` | Hutang Pemasok › Landed Cost (HPP) | view sama | `landed_cost.view` | A M |
| **Gudang & Logistik › Kendaraan** | `vehicle-logs` | Kas & Aset › Kendaraan | view sama | `vehicle_log.view` | A M G S |
| **SDM › Penggajian** › Proses Gaji · Slip Gaji | `hr-payroll-hub` · id tetap | "Payroll Run" | — | `hr.view` | A M |
| **SDM › Kinerja & Insentif** › Kinerja Sales | `hr-kpi-hub` · `sales-performance` (baru) | CRM › sub-tab Kinerja Sales | — | `order.view` | A M S SA |
| › Target & Aturan | · `incentive-rates` | Pengaturan › Penjualan › Komisi & Insentif | view sama | `sales_force.view` (hasil PR-T2) | A M |
| › Skema (Arsip) | · `incentive-schemes` (baru) | CRM › sub-tab Skema (Arsip) | — | sama | A M |
| › KPI Karyawan | · `cs-kpi` | SDM › KPI › KPI Karyawan (manual) | — | `hr.view` | A M |
| **Penjualan › Pelanggan › CRM & Pelanggan** | `customers-crm` | sub-tab tinggal: Pelanggan · Prospek · Interaksi | — | `customer.view` | tetap |

Grup "Kas & Aset" dihapus. SDM › Karyawan dan Kehadiran tidak berubah. Tab "Pembayaran" (Hutang), "Komponen & Masukan",
"Setoran & Pajak" (Penggajian), "Capaian", dan "Lembar Insentif" **tidak** ditambahkan: layarnya belum ada.

**Berkas yang berubah**

- `frontend/src/config/navStructure.js`, `hubTabs.js`: susunan di atas; `roles` grup dan tab mengikuti kolom "Peran
  bawaan" (sales ditambahkan ke grup `keuangan` dan `hrd`; warehouse ke grup `keuangan`, dicabut dari `akuntansi`).
- `frontend/src/config/roles.js` `ROLE_NAV.finance.add`: tambah `bank-accounts`, `bank-reconciliation`, `petty-cash`,
  `ledger`, `general-ledger`, `chart-of-accounts`, `accounts-payable`, `vendor-bills`, `contra-bons`,
  `collection-worklist`, `customer-credit`, `credit-overrides`, `bi-finance`, `settings-hub`, `settings-finance`,
  `gl-account-mappings`. `ROLE_NAV.sales_admin.add`: cabut `akuntansi`; `remove` tetap memuat `accounts-payable`.
- `frontend/src/config/viewAliases.js`: enam alias pada tabel, `since: "MN-T1"`, masing-masing ber-`label` nama lama.
- `frontend/src/config/navMeta.js`: judul halaman untuk lima view baru; `ROLE_HOME_REGISTRY.finance.navId` =
  `finance-tower`.
- `frontend/src/AppViewRouter.jsx`: rute lima view baru. `collection-worklist`, `credit-overrides`,
  `sales-performance`, `incentive-schemes` merender komponen CRM yang ada tanpa perubahan. Dua pembungkus baru,
  `frontend/src/features/finance/CustomerCreditView.jsx` dan `frontend/src/features/pettycash/PettyCashView.jsx`, hanya
  berisi `FilterChips` dan salah satu layar lama: chip "Titipan pelanggan" · "Saldo kredit", dan "Pengajuan dana" ·
  "Pertanggungjawaban" · "Hutang reimburse" (chip terakhir tampil hanya dengan `accounting.view`). Rute cadangan id
  lama tetap ada.
- `frontend/src/features/crm/CrmView.jsx`: `TABS` tinggal tiga; gerbang `roleIs` dicabut.

**Penjaga** — yang sudah ada harus hijau: `verify_access_catalog_nav.py`, `verify_view_aliases.py`,
`verify_desk_targets.py`, `verify_page_tabs.py`, `roleReach.test.js`, `serverAccessReach.test.js`,
`viewAliases.test.js`, `navAccess.test.js`. `role_reach_baseline.json` **tidak dibuat ulang**; jangkauan baru dicatat
di `ROLE_REACH_ADDITIONS` dengan rujukan K-09, K-17, atau IA-06.

Dua pemeriksaan ditambahkan ke `scripts/guardrails/verify_page_tabs.py`:

| Kode | Aturan | Baseline |
|---|---|---|
| INV-UI-13 | Tiap hub di `hubTabs.js` paling banyak **enam** tab tampak (tanpa `hidden: true`; komentar diabaikan). Hub pada baseline tidak boleh melebihi angka baseline-nya | berkas baru `scripts/guardrails/baselines/hub_tab_limit.json`: `{"products-pricing": 8, "purchase-orders": 7}` |
| INV-UI-14 | Komponen yang dirender `AppViewRouter.jsx` untuk view yang menjadi tab hub tampak tidak boleh memuat `PageTabs` atau kelas `tab-bar`. Berkas pada baseline hanya boleh berkurang; berkas baru tidak boleh masuk | berkas baru `scripts/guardrails/baselines/third_level_tabs.json`, diisi dari keadaan sesudah unit ini (`CrmView.jsx` tetap di dalamnya dengan tiga sub-tab) |

Keduanya mendapat kasus `--self-test`: hub 7 tab → merah; hub baseline 8 → hijau, 9 → merah; berkas baru ber-`PageTabs`
di bawah tab hub → merah.

## Uji penerimaan

Uji komponen memakai `access_builtin_fixture.json` yang dibuat ulang oleh generator backend sesudah izin Finance
berubah. Tabel bantu baru `frontend/src/config/__tests__/fixtures/view_main_permission.json`: tiap view pada tabel
lama → baru → daftar pasangan izin alternatif dan satu endpoint `GET` utamanya.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | komponen | — | Hitung entri: grup `keuangan` dan `akuntansi` untuk admin | 5 + 5 = 10 entri; grup `kas-aset` tidak ada |
| U2 | komponen | — | Jumlah tab tampak per hub untuk admin | `finance-tower` 3 · `ar-aging` 6 · `accounts-payable` 2 · `cash-bank` 4 · `closing` 3 · `ledger` 2 · `hr-kpi-hub` 4 · `purchase-orders` 7 |
| U3 | komponen | Tiap peran bawaan dengan izin dari fixture | Untuk tiap menu dan tab yang tampak, cari izinnya di tabel bantu | Peran memegang salah satu pasangan izinnya — nol entri "tampak tetapi tanpa izin" untuk 13 peran |
| U4 | B | Peran Tanpa Acuan diberi tepat satu pasangan izin dari tabel bantu, bergiliran per view | `GET` endpoint utama view itu | Tidak 403 untuk tiap baris; Manajer Kosong → 403 untuk tiap baris |
| U5 | komponen | — | `roleReach.test.js` tanpa mengubah baseline | Lulus: tiap id lama tiap peran masih mendarat di layar yang sama atau di tujuan aliasnya |
| U6 | komponen | — | `resolveDeepLinkTarget` untuk `advance-report`, `store-credit`, `cash-advances`, `settlements`, `reimburse-payables`, `period-unlock`, `posting-failures`, `payment-plans`, `landed-cost`, `vehicle-logs`, `fixed-assets`, `finance-desk`, `petty-cash`, `kas-aset` sebagai admin | Semuanya bukan `null`; lima pertama membawa `preset.bagian` yang benar; `navId` berturut-turut `ar-aging` ×2, `cash-bank` ×3, `closing` ×2, `ar-aging`, `purchase-orders`, `vehicle-logs`, `fixed-assets`, `finance-tower`, `cash-bank` ×2 |
| U7 | komponen | finance | Menu Finance | Memuat Keuangan (Beranda 3 tab, Piutang 6, Hutang 2, Kas & Bank 4, Antar-PT) dan Akuntansi & Pajak (Buku Besar 2, Pajak › Faktur Keluaran); tidak memuat Tutup Buku, Laporan, Aset Tetap |
| U8 | komponen | sales | Menu Sales | Keuangan hanya Piutang (Penagihan & Penerimaan, Kasus) dan Kas & Bank (Kas Kecil); SDM hanya Kinerja & Insentif › Kinerja Sales |
| U9 | komponen | warehouse | Menu Gudang | Keuangan hanya Hutang › Kontrabon dan Antar-PT; grup Akuntansi & Pajak tidak tampil |
| U10 | komponen | sales_admin | Menu Admin Sales | Tidak memuat Hutang; memuat Antar-PT |
| U11 | B | Peran kustom Tanpa Acuan dengan modul pemilik `order` "Lihat saja" | `GET /api/access/roles/{id}` | `nav.add` memuat `keuangan`, `ar-aging`, `collection-worklist`; tidak memuat `vendor-bills` |
| U12 | B | Peran kustom dengan `hidden_views: ["kas-aset"]` tersimpan (fixture) | Muat peran | Tidak galat; `hidden_views` tidak lagi memuat `kas-aset` |
| U13 | B | Akun finance seed | `GET /api/vendor-bills`, `GET /api/contra-bons`, `POST /api/cash-advances/{id}/disburse` (isi sah, dokumen fixture disetujui) | 200, 200, bukan 403 |
| U14 | penjaga | — | `verify_access_catalog_nav.py`, `verify_view_aliases.py`, `verify_desk_targets.py`, `verify_page_tabs.py` dan `--self-test`-nya | Semua 0 temuan; kasus self-test baru lulus |
| U15 | penjaga | — | `scripts/audit_i18n_id.py` | Tidak bertambah merah; "Payroll Run" dan "Chart of Accounts" tidak lagi tampil |
| U16 | layar (uji jalan) | Data acuan; login bergiliran sebagai admin, manager, finance, sales, sales_admin, warehouse, warehouse_admin | Klik tiap entri dan tiap tab Keuangan, Akuntansi & Pajak, SDM yang tampak | Tidak ada layar "tidak berwenang", layar kosong karena 403, atau pantulan ke Beranda; laporan memuat satu tangkapan layar sidebar per peran |
| U17 | layar (uji jalan) | admin | Buka `?view=advance-report`, `?view=cash-advances`, `?view=period-unlock` | Mendarat di Piutang › Titipan & Saldo Kredit (chip Titipan), Kas & Bank › Kas Kecil (chip Pengajuan dana), Tutup Buku › Buka Periode |

## Langkah kerja

1. Tabel bantu izin dan U1–U12 (merah). Catat garis dasar empat penjaga dan uji komponen navigasi.
2. Katalog modul dan izin bawaan Finance; buat ulang `access_builtin_fixture.json`; U4, U11–U13.
3. `navStructure.js`, `hubTabs.js`, `roles.js`, `navMeta.js`, `role_registry.py`.
4. Lima rute baru, dua pembungkus, `CrmView.jsx`, alias; `ROLE_REACH_ADDITIONS`.
5. Dua pemeriksaan penjaga dan baseline-nya; U14, U15.
6. Dokumen navigasi. Uji jalan U16, U17. Gate; laporan.

## Dokumen ikut berubah

`docs/KN_13_NAVIGATION_MAP.md`, `docs/KN_14_INFORMATION_ARCHITECTURE.md`, `docs/KN_16_END_TO_END_PROCESS_FLOWS.md`
(bagian keuangan dan SDM ditulis ulang dari konfigurasi; menutup IA-15); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`
(label baru; "pemasok", "PT"); `CODEBASE_MAP.md` (dua pembungkus).

## Di luar lingkup

- Menyatukan isi layar: Titipan & Saldo Kredit, Kas Kecil, Tutup Buku, Beranda Keuangan → MN-T2. Tab Slip Gaji
  dicabut PY-T1.
- Form pembayaran tunggal, kartu pelanggan, kartu pemasok, telusur angka → MN-T3.
- Peta tujuan Jejak Dokumen dan fokus dokumen → PK-44. Nominal kontrabon untuk gudang (K-18) → PK-17.
- Tab baru yang layarnya belum ada: Capaian dan Lembar Insentif (KM-T2, KM-T3, KM-T5), Komponen & Masukan dan Setoran
  & Pajak (PY-T1, PY-T4). Susunan hub Pengaturan → KP-T9.
- Menu peran bawaan yang bertambah otomatis dari modul (PR-UX-05) dan Beranda/Tanya KN di katalog (PR-UX-18) → PR-T6.

## Asumsi dan risiko

- `ASUMSI:` id menu lama dipertahankan sejauh mungkin (`ar-aging`, `closing`, `accounts-payable`, `hr-kpi-hub`
  menjadi induk barunya) supaya menu tersimpan, katalog, dan tautan antrean tidak perlu alias.
- `ASUMSI:` dua pembungkus ber-chip tidak dihitung "mengubah isi layar": layar lama dirender utuh di dalamnya.
- `ASUMSI:` "Kinerja Sales" pindah ke SDM › Kinerja & Insentif dan tetap tampil bagi sales sampai KM-T5 menggantinya
  dengan kartu beranda; finance tidak lagi melihatnya (rancangan `01` §4).
- `ASUMSI:` hub Pesanan Pembelian menjadi 7 tab karena Landed Cost; dicatat di baseline, bukan dilonggarkan.
- `ASUMSI:` izin bayar hutang memakai nama aksi yang ada (`vendor_bill.pay`, `contra_bon.pay`); PK-38 boleh
  memecahnya kemudian.
- `RISIKO:` pengguna mencari menu di tempat lama. Palet Ctrl+K menampilkan "nama lama → kini di …" dari `label` alias.
  Membatalkan: kembalikan enam berkas konfigurasi; view baru dan pembungkus tidak berbahaya bila tertinggal.

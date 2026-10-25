CATATAN: sesi ini berjalan dalam mode perencanaan baca-saja (tanpa alat tulis, dilarang membuat berkas), jadi saya **tidak bisa menulis** `S\phase3_plan.md`. Isi lengkapnya ada di bawah (bagian "ISI phase3_plan.md"). Silakan simpan apa adanya ke
`C:\Users\abc\AppData\Local\Temp\claude\C--Users-abc-Documents-Codex-KNHOST\4f003146-8d75-4e0b-9783-daa1d8e525b4\scratchpad\crawl\phase3_plan.md`. Tidak ada berkas repo yang diubah.

## Ringkasan

**Paket** (P1 dan P8 berurutan; P2–P7 paralel dengan berkas yang tidak beririsan)
| Paket | Isi | Berkas utama | Prasyarat | Ukuran |
|---|---|---|---|---|
| P1 Fondasi | infrastruktur alias + preset, komponen standar (PageTabs, FilterChips, ResponsiveTable, LinkCard, EntityRequiredNotice, DesktopOnlyNotice, FormSection), FormModal/DetailModal layar penuh di HP, HubTabs gaya baku, sidebar dan breadcrumb dari menu, papan "mode tautan", helper keputusan SORD, guardrail ratchet, uji jangkauan peran | `config/viewAliases.js`(baru), `config/navigationConfig.js`, `App.js`, `AppViewRouter.jsx`, `components/**`, `context/**`, `services/approvalDecisions.js`, `styles/components.css`, `styles/layout.css` | D1/D2/D3 selesai | L (≈25 berkas, 3–4 hari-agen) |
| P2 Pengaturan & master | P16-K1 (7 kelompok), D-01, D-02, D-03, D-04, D-21, D-29, Koreksi Harga, serta L-xx layar pengaturan | `config/navStructure.js`, `hubTabs.js`, `navMeta.js`, `roles.js`, `AppViewRouter.jsx`, `features/settings/**`, `features/pdf/**`, `features/admin/AdminView.jsx`, `admin/uom/**` | P1 | XL (≈35 berkas; bisa dipecah P2a/P2b) |
| P3 Penjualan, persetujuan, beranda & sampel | D-05 (desktop/POS), D-06, D-07, D-14 harga, D-17, D-24a, L-04 beranda/SO/sampel | `features/approvals/**`, `home/**`, `orders/**`, `sales/**` (tanpa mobile), `crm/**`, `pos/**`, `samples/**`, `catalog/**` | P1 | L |
| P4 Keuangan, hutang & pajak, dokumen | D-10, D-11, D-12(B), D-13(B), D-14 tutup buku, D-20, L-03/L-07/L-08 keuangan | `features/finance/**`, `costing/**`, `pettycash/**`, `purchasing/contrabon/**`, `InputTax*`, `documents/**` | P1 | L |
| P5 Rantai pasok | D-15, D-16, D-18, D-19, D-22, D-23, D-25(B), D-28 desktop, L-04 RFQ/Inspeksi/Barang Masuk | `features/wms/**`, `inventory/**`, `inspections/**`, `purchasing/**`, `admin/po/**`, `logistics/**`, `rfid/**` | P1 | XL (bisa dipecah P5a/P5b) |
| P6 R&D, desain, SDM, marketing | D-08, D-09, D-24b/c, L-xx R&D/SDM | `features/rnd/**`, `design/**`, `designer/**`, `hr/**`, `marketing/**` | P1 | L |
| P7 Aplikasi HP | L-09, D-26, D-27, plus bagian HP dari D-05, D-06, D-07, D-28 | `features/mobile/**`, `sales/mobile/**`, `pos/mobile/**`, `styles/mobile.css`, `App.js` | P1; API P3/P6 | L |
| P8 Aktivasi & penutup | mengaktifkan alias dan menu untuk penggabungan P3–P7, katalog akses backend, fixture, uji navigasi, crawl ulang | `hubTabs.js`, `viewAliases.js`, `navMeta.js`, `AppViewRouter.jsx`, `backend/access_modules.py`, fixture fe03 | P2–P7 | M |

**Ringkasan per D (G):**
- D-01: layar utama "Template Dokumen" (`pdf-templates`). Template Dasar menjadi alias. Master per BU dan Pusat Cetak hanya menautkan.
- D-02: Kategori Beban dibangun di atas tabel master berlapis plus pemilih akun COA.
- D-03: Komisi & Insentif (editor tarif + bawaan `commission.*`).
- D-04: Aturan Persetujuan dengan satu jalan nonaktif; manajer bisa membaca.
- D-05: CustomerFormModal satu-satunya form, dengan isian lengkap juga di HP.
- D-06: Pusat Persetujuan dengan tab "Matriks divisi"; `my-approvals` menjadi alias.
- D-07: keputusan hanya di Pesanan Khusus. Papan beranda jadi tautan. Desktop dan HP memakai satu dialog Setujui.
- D-08: KPI Desainer (tab Pekerjaan DSR) untuk menilai tim; Profil Saya › KPI Saya untuk diri sendiri.
- D-09: Desain & Pattern punya mode Galeri; `cs-design-gallery` menjadi alias.
- D-10: Laba-Rugi di Laporan Keuangan. Dasbor dan BI menautkan, metrik ganda dibuang.
- D-11: Profitabilitas & Margin dengan tab Margin katalog; `costing` menjadi alias.
- D-14: pemilih PT hanya di header (EntityRequiredNotice).
- D-15: Stock Opname di Operasi Gudang dengan metode Sapu RFID.
- D-16: satu daftar Transfer dengan kolom Jenis.
- D-17: Dasbor di Pesanan (data server) dan satu kontrol filter status.
- D-18: rincian PO hanya lewat pop-up.
- D-19: daftar pengiriman tunggal dan satu tombol Buat.
- D-20: rekap PPN di Pajak; Faktur Masukan menautkan.
- D-21: satu tabel Satuan & faktor.
- D-22: Kinerja Mitra Makloon (rekap + skor + rincian mitra).
- D-23: Harga Internal; tab Kontrak menautkan lewat alias tersembunyi supaya hak gudang dan manajer tetap ada.
- D-24: (a) Cutting gudang, (b) RndSamplesView Papan/Daftar/Galeri dengan Labdip, Handfeel, Proofing jadi alias, (c) SpecFormModal.
- D-26: satu pintu "Tampilan desktop".
- D-28: Stok & ATP untuk HP MD; Inspeksi "Hanya ditahan" sebagai layar utama.
- D-29: satu layar "Perangkat" (mesin absen + RFID).

**Ringkasan butir B:**
- D-12: bucket umur Uang Muka disamakan dengan Piutang.
- D-13: cek angka kas (K-02); kartu "per entitas" disembunyikan bila hanya satu PT.
- D-25: nama diperjelas, ditambah tautan silang.
- D-27: form HP memakai komponen desktop.

**Ringkasan L** (urutan pemilik): L-04 → L-03 → L-01 & L-05 → L-09 → L-02, L-06, L-07, L-08, L-10. Di dalam tiap paket, penggabungan D dikerjakan lebih dulu supaya tata letak tidak dikerjakan di layar yang akan menjadi alias.

**Pertanyaan sisa** (masing-masing dengan usulan bawaan): ada enam, lihat §9 di bawah.

---

# ISI phase3_plan.md

# Rencana Fase 3: penggabungan layar duplikat dan rombakan tata letak (ERP Kain Nusantara)

Disusun 26 Okt 2026 dari `fixplan.md` §5.1 (D-01..D-29) dan §5.2 (L-01..L-10), keputusan pemilik (semua D disetujui; P16-K1 disetujui; urutan L ditetapkan) dan pemeriksaan kode di HEAD `e508e7d` dengan perubahan D1/D2/D3 yang belum di-commit. Repo: `C:\Users\abc\Documents\Codex\KNHOST`. Semua path frontend relatif terhadap `frontend/src/`.

## 0. Ringkasan eksekutif
- **Delapan paket.** P1 Fondasi dikerjakan berurutan lebih dulu. P2–P7 berjalan paralel dengan himpunan berkas yang tidak beririsan. P8 Aktivasi & penutup dikerjakan berurutan di akhir.
- **Tidak ada layar yang dihapus dari sisi alamat.** Setiap view lama tetap bisa dibuka (deep link `?view=`, notifikasi, giliran, uji). View lama dialihkan ke layar utama dengan *preset* (tab, mode, atau saringan). Baris rute `activeView === "<lama>"` tetap ada di `AppViewRouter.jsx` sebagai cadangan, karena guardrail `verify_desk_targets.py`, `verify_home_kpi.py`, `verify_approval_queues.py`, `verify_access_catalog_nav.py` dan backend `approval_backlog_service` (mis. target `cs-design-gallery`) menuntutnya.
- **Hak akses setara dibuktikan oleh uji.** P1 menambah uji "jangkauan peran" berbaseline: daftar view yang bisa dicapai tiap peran bawaan sebelum dan sesudah perubahan harus sama setelah pemetaan alias diterapkan. Penambahan hanya boleh bila tercatat di §6.
- **Syarat pemilik untuk form HP:** HP memakai komponen form yang sama dengan desktop dengan isian lengkap. Yang boleh beda hanya tata letak (1 kolom, layar penuh). Ini berlaku untuk D-05 dan D-27.

## 1. Prinsip dan pola teknis bersama

### 1.1 Pola "gabung" (alias pengalihan), disediakan P1
1. **Registri** `config/viewAliases.js` (baru) mendaftarkan view lama beserta tujuannya:
   ```js
   export const VIEW_ALIASES = {
     // lama: { to: <view utama>, nav: <navId utama>, preset: {...}, since: "D-xx" }
   };
   export function resolveAlias(view) { /* → {to, nav, preset} | null */ }
   ```
   `utils/viewAlias.js` (`resolveView`) membaca registri yang sama. Tiga peta lama (`approvals`, `finance`, `purchase-orders`) tetap ada karena dijaga `uatV3ReturnsOps.test.js`.
2. **Satu jalur navigasi.** `App.js:handleNavSelect` menjalankan `resolveAlias` lalu `setViewPreset({view, ...preset, nonce})`. Semua jalan masuk harus lewat jalur ini:
   - sidebar, palet Ctrl+K, deep link (`resolveDeepLinkTarget` memeriksa alias lebih dulu dan memvalidasi peran terhadap view utama);
   - `openDocument`;
   - `NotificationCenter.onNavigate`, yang sekarang memakai `setActiveView(resolveView(target))` dan harus diganti ke `handleNavSelect`;
   - `DetailDrawer.onNavigate` dan `PeriodUnlockBanner`.
3. **Preset ke layar.** `context/ViewPresetContext.jsx` dan `hooks/useViewPreset.js` (baru). Layar utama membaca `useViewPreset("<view>")` sekali, pola yang sama dengan `focusDoc`. Dengan cara ini paket fitur tidak perlu menyentuh `AppViewRouter`. `context/AppNavContext.jsx` menyediakan `go(view, {preset, focus})` untuk LinkCard dan tombol tautan.
4. **Menu.**
   - Tab lama dicabut dari `hubTabs.js` (tidak lagi tampil).
   - Palet Ctrl+K menambah entri "Nama lama → kini di <utama>" bila peran boleh melihat layar utama.
   - `hubForView` memetakan alias ke hub layar utama.
5. **Katalog akses backend** (`backend/access_modules.py`, hanya P8). Modul yang dulu memuat id lama ditambah id layar utama (dan hub-nya). Id lama tetap terdaftar karena masih "dikenal" lewat rute cadangan. Fixture `backend/tests/fe03_access_fixture.py` lalu `frontend/src/config/__tests__/fixtures/access_nav_fixture.json` dibuat ulang.
6. **Gerbang per bagian.** Bagian dalam layar utama yang berasal dari layar lama digerbang dengan `roleCanSee(<roles lama>, role, "<id lama>")` dan izin endpoint aslinya. Contoh: tab "Matriks divisi" hanya untuk peran yang dulu melihat `my-approvals`. `hidden_views` peran kustom terhadap id lama (mis. `rnd-labdip`, diuji di `test_l01_custom_role.py`) juga dipatuhi.

### 1.2 Pola tautan
`components/LinkCard.jsx` (baru) berbentuk kartu satu baris: "<Hal> kini dikelola di <Menu › Layar>" dengan tombol [Buka]. Kartu ini memakai `go()` dan hanya tampil bila `roleCanSee` mengizinkan. Bila peran tidak boleh membuka layar utama, yang tampil adalah ringkasan baca-saja satu baris, bukan tabel duplikat.

### 1.3 Komponen standar baru dan yang diubah (P1)
| Komponen | Isi |
|---|---|
| `components/PageTabs.jsx` | tab tingkat-2 baku (`.tab-bar`/`.tab-button`, `role=tablist`, hitungan, ikon, testId per tab, gulir 1 baris di ≤640 px) |
| `components/FilterChips.jsx` | saringan segmen baku (pengganti pil/segmented buatan sendiri) |
| `components/HubTabs.jsx` | tab tingkat-1 bergaya `.tab-bar.hub-tabs` (garis bawah, 13 px tebal); testid `hub-tab-<view>` dipertahankan karena dipakai tur `data/tours/*`; sub-judul seksi di bawah bilah sebagai pemisah tipis |
| `components/ResponsiveTable.jsx` | definisi kolom → `.data-table` (≥640) / kartu (<640) dengan kolom prioritas & aksi di kaki kartu |
| `components/FormModal.jsx`, `DetailModal.jsx` | ≤640 px: layar penuh (tinggi 100dvh, kepala & kaki tetap); grid `sm:grid-cols-2` → 1 kolom. API tidak berubah |
| `components/FormSection.jsx` | bagian form bernomor yang bisa dilipat (L-10) |
| `components/EntityRequiredNotice.jsx` | "Pilih badan usaha" yang mengubah HEADER (`useEntityScope().pickEntity`), dipakai D-14 |
| `components/DesktopOnlyNotice.jsx` | banner "Layar ini paling nyaman di desktop" (layar tetap bisa dipakai), dipakai L-04 kelas C |
| `components/ListPageParts.jsx` | `MetricRow`: nilai 0 netral (L-08); `PageHeader` tetap |
| `components/WaitingQueueBoard.jsx` / `WaitingBoardsStrip.jsx` | `mode="link"` / `linkKeys`: tanpa tombol aksi, baris diklik membuka dokumen di layar utama (D-07, D-28) |
| `components/CoreWidgets.jsx` | Sidebar: label 2 baris + `title`, sub-judul di dalam grup (`{type:"heading"}`); TopBar: breadcrumb dari menu (`breadcrumbFor()` di `navigationConfig.js`: grup › menu › tab), dengan PAGE_META.kicker hanya sebagai cadangan (L-05) |
| `services/approvalDecisions.js` | `approveSpecialOrder/rejectSpecialOrder/approvePrice`: satu dialog (askReason, catatan opsional untuk setuju, alasan ≥5 huruf untuk tolak sesuai K-14, pesan hasil berantai), dipakai desktop dan HP (D-07, D-27) |

### 1.4 Aturan tab maksimal 2 tingkat (L-01)
- **Tingkat 1** = HubTabs (bilah hub).
- **Tingkat 2** = PageTabs di dalam layar.
- Saringan memakai FilterChips atau KNSelect, tidak pernah berupa tab.
- Kebutuhan tingkat ke-3 diubah menjadi chip, seksi berjudul, atau pop-up.

Dijaga guardrail ratchet `scripts/guardrails/verify_page_tabs.py`, yang mendeteksi pil `rounded-full … bg-[#1C1C1E]`, tombol-toggle `primary-button !py-1.5`, `TabBtn` buatan sendiri, dan `cfg-group-btn`. Baseline diambil saat P1, dan jumlah per berkas hanya boleh turun.

### 1.5 Aturan pop-up (L-03)
- Buat/Ubah memakai `FormModal`; rincian memakai `DetailModal` (framed).
- Tidak ada lagi `.modal-card` polos, `div fixed inset-0`, form inline, panel tetap, atau halaman penuh untuk form.
- Komponen yang sudah punya `<form>` sendiri memakai FormModal **tanpa** `onSubmit`, supaya tidak ada form di dalam form.

Dijaga guardrail ratchet `scripts/guardrails/verify_custom_modals.py`. Saat ini ada 161 berkas berpola `modal-card`/`fixed inset-0`; baseline per berkas hanya boleh turun.

### 1.6 Kepemilikan berkas dan bentrok
- P1 dan P8 boleh menyentuh berkas apa pun karena berjalan berurutan.
- Selama P2–P7 berjalan, `components/**`, `utils/**`, `hooks/**` (kecuali `useDeepLinks.js`→P2 dan `useAppActions.js`→P3), `context/**` dan `config/navigationConfig.js` **dibekukan**. Kebutuhan perubahan di sana dicatat untuk P8.
- Berkas konfigurasi menu (`navStructure.js`, `hubTabs.js`, `navMeta.js`, `roles.js`, `viewAliases.js`, `AppViewRouter.jsx`) dimiliki **P2** selama fase paralel, karena hanya P2 yang menata ulang menu (P16-K1). Paket lain menulis kebutuhan menunya di laporan, dan P8 yang mengaktifkan.
- **Bentrok dengan agen K-xx yang sedang bekerja** (rencana ini dieksekusi sesudah mereka; rebase di atas hasilnya):

| Paket fase 3 | Berkas yang juga disentuh agen K-xx |
|---|---|
| P2 | D3 (`features/settings/**` K-11 akses MD, `roles.js`, `features/hr/AttendanceSetupView.jsx`); D2 (kunci setelan baru K-05/B1 di `config_catalog*` → grupnya harus dipetakan ke halaman domain) |
| P3 | D1 (`features/home/**` K-01); D2 (`features/orders/**` K-06) |
| P4 | D1 (seluruh `features/finance/**`, `features/documents/**`, `PurchaseApprovalView`, `CashManagementView`) |
| P5 | D2 (`features/inventory/**`, `wms/**`, `inspections/**`, `purchasing/Reorder*`); D1 (`admin/po/PODetailPanel.jsx` K-03) |
| P6 | D3 (`features/rnd/**` K-16, `design/**`, `designer/DesignerKpiView.jsx`+`designerMeta.js` K-08, `hr/**` K-09) |
| P7 | D3 (`features/mobile/MobileOpsApp.jsx`, `MobileApprovalInbox.jsx`, `MobileRoleSummary.jsx` baru, `features/sales/mobile/**` K-11/K-12) |
| P8 | D3 (`backend/services/approval_backlog_service.py`, hanya bila target view diganti; opsional) |

  Uji baru milik agen K-xx yang harus tetap hijau: `features/__tests__/decisionsD1.test.js`, `decisionsD3.test.js`, `backend/tests/test_decisions_d1_finance.py`, `test_uat26_d2_*.py`, `test_uat26_d3_decisions.py`.
- **Batas ukuran berkas** (KN_00 GATE 1: React ≤500 baris). Sudah lewat batas: `AppViewRouter.jsx` 514, `App.js` 665, `SettingsHub.jsx` 569, `EntityMastersView.jsx` 554. Setiap paket yang menambah isi ke berkas-berkas ini wajib mengekstrak bagiannya, dengan rincian di paketnya masing-masing.

## 2. Paket kerja

### P1: Fondasi navigasi dan komponen bersama (berurutan, pertama) — L, ±25 berkas, 3–4 hari-agen
Urutan kerja di P1 mengikuti urutan pemilik: primitif L-04, lalu L-03, lalu L-01/L-05.
1. **Alias dan preset (§1.1)**:
   - `config/viewAliases.js` (baru, isi awal hanya alias lama), `utils/viewAlias.js`;
   - `config/navigationConfig.js` (`resolveDeepLinkTarget`, `hubForView`, `buildPaletteEntries`, `breadcrumbFor`);
   - `App.js` (`handleNavSelect`, `viewPreset`, onNavigate notifikasi/drawer/banner lewat `handleNavSelect`);
   - `context/ViewPresetContext.jsx`, `context/AppNavContext.jsx`, `hooks/useViewPreset.js` (semua baru);
   - `AppViewRouter.jsx`: provider ditambahkan; impor `lazy` dipindah ke `appViewImports.js` (baru) supaya di bawah 500 baris. Sintaks `activeView === "x"` tidak diubah karena diurai guardrail.
2. **Komponen §1.3** dan CSS di `styles/components.css`: `.tab-bar` nowrap+gulir di ≤640, `.hub-tabs`, `.rt-card`, `.detail-head-grid`, FormModal/DetailModal layar penuh ≤640. Di `styles/layout.css`: label sidebar 2 baris. `styles/mobile.css` **tidak** disentuh (milik P7).
3. **Label sidebar** yang terpotong dipendekkan di `config/navStructure.js` sebelum diserahkan ke P2. Contoh: grup "Akuntansi & Pajak" dibiarkan tetapi diberi wrap; "Uang Muka Pelanggan" diberi wrap.
4. **Guardrail baru:**
   - `scripts/guardrails/verify_custom_modals.py`, `verify_page_tabs.py` (ratchet);
   - `verify_view_aliases.py`: setiap alias punya rute cadangan, tujuannya ada di menu, dan peran lama ⊆ peran tujuan.
5. **Uji baru:**
   - `config/__tests__/viewAliases.test.js` (deep link alias, preset, palet, breadcrumb);
   - `config/__tests__/roleReach.test.js` + `fixtures/role_reach_baseline.json` (dibuat dari konfigurasi SEBELUM perubahan apa pun);
   - `components/__tests__/pageTabs.test.js`, `responsiveTable.test.js`, `formModalMobile.test.js`.
- **Cek:**
  - `?view=approvals` masih mendarat di Pusat Persetujuan;
  - tur `data/tours/*` tetap menemukan `hub-tab-goods-receipts`, `tab-dashboard`, `wms-tab-stok`;
  - Jest penuh (37+ suite) dan ESLint 0 error;
  - `check_nav_map.py`, `verify_access_catalog_nav.py`, `verify_detail_modal.py`, `verify_modal_dismiss.py`, `verify_escape_layers.py` hijau.

### P2: Pengaturan dan master data — XL, ±35 berkas, 5–6 hari-agen (bisa dipecah)
**Isi:** P16-K1 (L-05 Pengaturan), D-01, D-02, D-03, D-04, D-21, D-29, Koreksi Harga, dan L-xx untuk layar pengaturan:
- L-02: approval-rules, cs-rfid-devices;
- L-03: md-categories, Buat Template Dokumen, cs-rfid-devices inline, incentive-rates panel tetap;
- L-06: entity-masters;
- L-07: DivisionsView;
- L-04 kelas C: DesktopOnlyNotice di semua layar Pengaturan;
- L-10: Buat Template Dokumen.

**Berkas:**
- Konfigurasi: `config/navStructure.js`, `config/hubTabs.js`, `config/navMeta.js`, `config/roles.js`, `config/viewAliases.js`, `AppViewRouter.jsx`, `hooks/useDeepLinks.js`.
- `features/settings/**`. Yang baru: `cfg/SettingsGroupView.jsx`, `devices/DevicesView.jsx`, `config/PriceCorrectionsView.jsx`, `masters/EntityMasterKindPanel.jsx`. Ekstrak `SettingsHub` agar di bawah 500 baris.
- `features/pdf/**` (baru: `DocTemplatesView.jsx`).
- `features/admin/AdminView.jsx`, `features/admin/DocTemplateForm.jsx` (baru), `features/admin/CategoryManager.jsx`, `features/admin/uom/**`, `features/admin/scheduler/**`, `features/admin/domain/**`.
- `features/documents/DocumentsView.jsx` (hanya berkas ini).
- `features/pettycash/ExpenseCategoriesView.jsx`, `features/finance/GLAccountMappingView.jsx`, `features/finance/bank/BankRulesSettingsView.jsx`, `features/crm/IncentiveRatesEditor.jsx`.
- `features/hr/AttendanceSetupView.jsx`, `features/rfid/RfidDevicesView.jsx`, `features/designer/DivisionsView.jsx`.
- Backend: `backend/services/entity_master_service.py` (hanya teks `screen`/`hint`).

**Pemecahan bila ada agen tambahan:**
- P2a: konfigurasi, `SettingsHub`, `SettingsGroupView`, Devices, Koreksi Harga, AttendanceSetup, RfidDevices, DivisionsView, `useDeepLinks`.
- P2b: EntityMasters, `pdf/**`, `AdminView`, DocumentsView, ExpenseCategories, GLMapping, IncentiveRates, ApprovalRules, `admin/uom`, CategoryManager.
- Ketergantungan: P2b memakai prop `keys` dan rute dari P2a.

**Ketergantungan lain:** tombol Buat di `AdminView` (tab customers) membuka `CustomerFormModal` milik P3. Kerjakan langkah ini di akhir P2 setelah API P3 stabil.

### P3: Penjualan, persetujuan, beranda dan sampel — L, ±30 berkas, 4–5 hari-agen
**Isi:**
- Penggabungan D: D-05 (desktop/POS/Master Data via P2), D-06, D-07, D-14 (Harga per BU), D-17, D-24a.
- L-04: Control Tower, Dasbor Manajer, Pesanan SO, Meja Admin Sample, Pesanan Sample.
- L-01: orders, keep-pending.
- L-02: product-templates.
- L-03: cs-price-list, Tambah/Ubah Warna (ColorLibraryView), InternalRequestCreateModal → FormModal (prasyarat D-27).
- L-06: returns.
- L-10: Induk produk baru (`catalog/FamilyForm.jsx`), form Pelanggan CRM.

**Berkas:**
- `features/approvals/**`, `features/home/**`, `features/manager/ManagerDashboard.jsx`, `features/orders/**`.
- `features/sales/**` (kecuali `sales/mobile/**`).
- `features/crm/**` (kecuali `IncentiveRatesEditor.jsx`).
- `features/pos/**` (kecuali `pos/mobile/**`).
- `features/catalog/**`, `features/samples/**`, `features/sales_admin/**`, `features/internal_requests/**`.
- `config/waitingBoards.js`, `hooks/useAppActions.js`.

### P4: Keuangan, hutang dan pajak, dokumen — L, ±35 berkas (banyak konversi kecil), 4–5 hari-agen
**Isi:**
- Penggabungan dan butir B: D-10, D-11, D-12(B), D-13(B), D-14 (Tutup Buku, Buka Periode), D-20.
- L-01: amendments, bank-reconciliation, contra-bons, budget, chart-of-accounts, consolidation, financial-statements, general-ledger, input-tax.
- L-02: bank-reconciliation, contra-bons, finance-cases, export-center.
- L-03: contra-bons Jadwal, consolidation (2), interco (4 gaya; tombol hitam → biru), fixed-assets, document-center (WA/TTD/Kirim), chart-of-accounts (buat inline), cash-advances (halaman penuh), settlements, budget inline, input-tax.
- L-07: ARAging, Settlements, consolidation.
- L-08: KPI bergaris kiri di budget/Arus Kas/Perubahan Ekuitas, landed-cost nol berwarna, 4 tombol consolidation.

**Berkas:**
- `features/finance/**` (kecuali `GLAccountMappingView.jsx` dan `bank/BankRulesSettingsView.jsx`).
- `features/costing/**`, `features/pettycash/**` (kecuali `ExpenseCategoriesView.jsx`).
- `features/purchasing/contrabon/**`, `features/purchasing/InputTax*.jsx`, `VendorBill*.jsx`, `LandedCost*.jsx`, `PurchaseApprovalView.jsx`, `CashManagementView.jsx`.
- `features/documents/**` (kecuali `DocumentsView.jsx`), `features/export/**`.

### P5: Rantai pasok (pembelian, makloon, gudang, kualitas, logistik) — XL, ±45 berkas, 6–7 hari-agen (bisa dipecah)
**Isi:**
- Penggabungan dan butir B: D-15, D-16, D-18, D-19, D-22, D-23, D-24a (sisi Cutting: preset), D-25(B), D-28 (desktop: Operasi Gudang dan Inspeksi).
- L-04: RFQ, Inspeksi, Barang Masuk.
- L-01: operations, inventory-lots, inspections.
- L-02: cs-rfid-gate/tags/lokasi, cs-stock-analytics, escalations, repair-orders.
- L-03: blanket-po, RFQ, PR Baru, md-warehouses (4 pola), makloons, process-recipes.
- L-06: purchasing (D-18), operations (KPI BTK 6 baris).
- L-07: RfidTags, StockAnalytics, InspectionsView.
- L-08: makloon-claim-recap, logistics, inventory-board (nilai 0).
- L-10: form Kontrak (rumus), Wizard Order Makloon.

**Berkas:**
- `features/admin/PurchaseOrderManagement.jsx`, `features/admin/po/**`.
- `features/purchasing/**` (kecuali milik P4 di atas), `features/interco_prices/**`.
- `features/wms/**`, `features/transfers/**`, `features/inventory/**`, `features/inspections/**`.
- `features/rfid/**` (kecuali `RfidDevicesView.jsx`), `features/logistics/**`, `features/production/**`, `features/manager/EscalationManagement.jsx`.

**Pemecahan:**
- P5a "Pembelian & makloon": `admin/po`, `purchasing`, `interco_prices`.
- P5b "Gudang, kualitas, logistik": `wms`, `transfers`, `inventory`, `inspections`, `rfid`, `logistics`, `production`, `escalations`.

### P6: R&D, desain, SDM, marketing — L, ±25 berkas, 3–4 hari-agen
**Isi:**
- Penggabungan: D-08, D-09, D-24b, D-24c. Juga memastikan `DesignRequestCreateModal` layak dibuka layar penuh di HP (D-27).
- L-04: Permintaan Desain, Labdip/Desain & Pattern/Proofing.
- L-01: design-requests, rnd-revalidation, rnd-specs, hr-attendance.
- L-02: mkt-accounts.
- L-03: Riwayat Labdip, LifecycleActions, Sheet SDM (EmployeeFormDrawer), ESS cuti (MyLeaveCard), cs-kpi.
- L-06: designer-kpi (15+ kolom).
- L-07: KpiView, AttendanceView.
- L-08: toolbar designer-kpi (8 kontrol), mkt-calendar, hr-leave nol, aksen ungu.
- L-10: form Karyawan.

**Berkas:**
- `features/rnd/**`, `features/design/**`.
- `features/designer/**` (kecuali `DivisionsView.jsx`).
- `features/hr/**` (kecuali `AttendanceSetupView.jsx`), `features/marketing/**`.

### P7: Aplikasi HP satu kerangka — L, ±20 berkas, 3–4 hari-agen
**Isi:**
- L-09 dan D-26.
- D-27: form HP Permintaan Internal dan DSR memakai komponen desktop; dialog Setujui memakai `approvalDecisions`.
- Bagian HP dari D-05: `MobileCustomerForm` menjadi pembungkus `CustomerFormModal`.
- Bagian HP dari D-06: dedup antrean.
- Bagian HP dari D-07: papan Beranda HP dalam mode tautan, MobileApprovalInbox memakai helper.
- Bagian HP dari D-28: MD "Status Stok" → `MobileStockAtp`.
- Audit form HP lain (PR, permintaan sample, kwitansi, amandemen): hasilnya hanya laporan, tidak diubah.

**Berkas:** `features/mobile/**`, `features/sales/mobile/**`, `features/pos/mobile/**`, `styles/mobile.css`, `App.js` (props lonceng/notifikasi ke aplikasi Ops/Gudang).

**Prasyarat:** P1. Langkah D-05/D-27 menunggu API dari P3 (`CustomerFormModal`, `InternalRequestCreateModal`) dan P6 (`DesignRequestCreateModal`), jadi dikerjakan paling akhir di P7.

### P8: Aktivasi dan penutup (berurutan, terakhir) — M, ±12 berkas, 1–2 hari-agen
**Isi:**
- Menerapkan tabel §6 di `config/hubTabs.js`, `viewAliases.js`, `navMeta.js` (+label D-25), `roles.js` (bila ada catatan) dan `AppViewRouter.jsx` (rute cadangan merender layar utama dengan preset; rute alias tersembunyi `supplier-internal-prices`).
- `backend/access_modules.py`, regenerasi `backend/tests/fe03_access_fixture.py` lalu fixture JSON; `backend/tests/test_fe03_access_catalog.py`.
- `frontend/src/config/__tests__/navAccess.test.js`, `features/__tests__/uatV3NavWarehouseMakloon.test.js` (gudang mendapat tab Kinerja Mitra), dan pembaruan baseline jangkauan peran (hanya penambahan yang tercatat).
- Opsional: target `cs-design-gallery` → `rnd-designs` di `backend/services/approval_backlog_service.py` (wilayah D3).
- Laporan UAT (`docs/uat/...` dan `docs/reviews/TRACKER.md`).
- Crawl ulang desktop 1440 dan HP 390 untuk semua layar D/L.

**Gate:**
- Jest penuh `--maxWorkers=1`, ESLint, pyflakes.
- `scripts/check_nav_map.py`, `audit_config_wiring.py` (menuntut `view: "settings-config"` ada di menu dan `<SettingsHub>` dirender), `audit_ia.py`.
- Seluruh `scripts/guardrails/verify_*.py`.
- POC backend yang mengurai menu: `test_core_role_access_poc.py`, `test_core_e8_roles_poc.py`, `test_core_f6_approval_coverage_poc.py`, `test_core_approval_reminder_poc.py`.

## 3. Rincian per D-xx (G)
Format tiap butir: **Utama** (dan alasannya) · **Tautan/alias** · **Menu** · **Peran** · **Berkas** · **Uji** · **Cek**.

### D-01: Template dokumen di 4 tempat (P2)
- **Utama:** Pengaturan › Dokumen & Cetak › **Template Dokumen** (`pdf-templates`, dirender `features/pdf/DocTemplatesView.jsx`). Isinya PageTabs:
  - (a) "Kop & tata letak dasar": satu tabel berlapis global→badan usaha (`EntityMasterKindPanel kind="document-templates"`). Koleksinya `document_templates`, koleksi yang SAMA dengan yang diedit Template Dokumen Dasar di AdminView. Form ubahnya = `DocTemplateForm` yang diekstrak dari AdminView (kertas, orientasi, margin, kolom, urutan bagian), ditambah aksi Pratinjau.
  - (b) "Desainer PDF": `PdfTemplateDesigner`.
  - Alasan: satu data diedit dua layar. Tabel berlapis paling lengkap untuk cakupan (global + khusus PT), form AdminView paling lengkap untuk isian. Mock P16 menggabungkan keduanya.
- **Tautan:**
  - `doc-templates-basic` → alias `pdf-templates` {tab:"dasar"}.
  - Master per BU kind `document-templates` → LinkCard.
  - Pusat Cetak (`documents`) kartu "Template aktif" → satu baris ringkas: tautan untuk admin, "dikelola Admin" untuk peran lain.
- **Menu:** tab dihapus dari `settings-documents`; judul baru "Template Dokumen · Kop, Tata Letak & Desainer PDF".
- **Peran:**
  - Dulu: Template Dasar admin; Master per BU admin+manager.
  - Kini: `pdf-templates` admin+manager, dengan tab "Desainer PDF" tetap admin. Hak tulis tetap dijaga server (izin `template` / WRITE_PERMISSION `entity_master_service`).
- **Berkas:** `features/pdf/DocTemplatesView.jsx`(baru), `PdfTemplateDesigner.jsx`, `features/admin/AdminView.jsx`, `features/admin/DocTemplateForm.jsx`(baru), `features/settings/masters/EntityMastersView.jsx`, `EntityMasterKindPanel.jsx`(baru), `masterFieldsConfig.js`, `features/documents/DocumentsView.jsx`, `AppViewRouter.jsx`, konfigurasi menu, `backend/services/entity_master_service.py` (hint).
- **Uji:** `auditUi2G5b.test.js` (G5-03 `cellText` masterFieldsConfig); backend `test_core_e4_master_layers_poc.py`.
- **Cek:**
  - `?view=doc-templates-basic` membuka Template Dokumen tab dasar.
  - Ubah template global → buat khusus Sukacita → Pratinjau.
  - Pusat Cetak tidak lagi menampilkan daftar template.

### D-02: Kategori beban dua editor (P2)
- **Utama:** Pengaturan › Kebijakan · Keuangan & Pajak › **Kategori Beban** (`expense-categories`), dibangun ulang di atas `EntityMasterKindPanel kind="expense-categories"` dengan kolom akun berupa KNSelect COA (`/gl/accounts`). Alasan: tabel berlapis punya global, override per PT, dan baris baru; editor lama punya pemilih COA. Keduanya digabung.
- **Tautan:** Master per BU kind ini → LinkCard. Pemetaan Akun tetap layar sendiri (cakupannya pemetaan fitur, bukan kategori LPJ), diberi tautan silang dua arah.
- **Data:** kategori kembar "Office Supplies" dan "ATK" → 6-4100 hanya diberi peringatan di layar; pembersihannya menunggu izin pemilik (Q5).
- **Peran:** sama (admin, manager; tulis = `cash_settlement.manage`).
- **Berkas:** `features/pettycash/ExpenseCategoriesView.jsx`, `EntityMasterKindPanel.jsx`, `masterFieldsConfig.js`, `EntityMastersView.jsx`, `features/finance/GLAccountMappingView.jsx`.
- **Uji:** backend `test_gl01_account_mapping.py`, `test_core_e4_master_layers_poc.py`, uji LPJ yang memakai `/expense-categories`.
- **Cek:** ubah akun kategori global lalu override per PT; Master per BU hanya menampilkan kartu tautan.

### D-03: Tarif insentif di tiga tempat (P2)
- **Utama:** Pengaturan › Kebijakan · Penjualan › **Komisi & Insentif** (`incentive-rates`). Isinya:
  - panel "Bawaan komisi" = `SettingsGroupView` terkunci ke kunci `commission.*` (strategi, ambang, mekanik, batas margin);
  - tabel tarif per kategori di bawahnya.
  - Alasan: editor tarif per kategori adalah yang terlengkap; kunci bawaan adalah fallback-nya dan harus terbaca di tempat yang sama.
- **Tautan:**
  - Grup Pusat Pengaturan `harga-diskon` menyembunyikan `commission.*` dan menggantinya dengan LinkCard (SettingsHub mendapat prop `keys`/`excludeKeys`).
  - ConfigRedirectCard di IncentiveRatesEditor dihapus.
  - Master per BU kind `incentive-rates` (manage=False) → LinkCard.
  - Teks backend "CRM › Tarif Insentif" dan `screen="crm"` diganti.
- **Peran:** sama (admin, manager).
- **Berkas:** `features/crm/IncentiveRatesEditor.jsx`, `features/settings/config/SettingsHub.jsx`, `cfg/SettingsGroupView.jsx`, `EntityMastersView.jsx`, `backend/services/entity_master_service.py`.
- **Uji:** belum ada uji langsung. Tambah `features/__tests__/phase3Settings.test.js` (kunci commission tidak tampil ganda).
- **Cek:** ubah ambang bawaan → tabel memakai nilai bawaan pada kategori tanpa ambang; grup harga-diskon tidak memuat kunci komisi.

### D-04: Aturan persetujuan (P2)
- **Utama:** Pengaturan › Persetujuan › **Aturan nilai & peran** (`approval-rules`).
  - Satu jalan aktif/nonaktif: tombol "Nonaktifkan/Aktifkan" dengan askConfirm.
  - Lencana status hanya label; ikon sampah dicabut.
- **Tautan:** Master per BU kind `approval-rules` → LinkCard (kode mentah hilang dengan sendirinya).
- **Peran:** Master per BU dulu memberi **manager** akses lihat → tab `approval-rules` + manager dengan mode baca (tombol ubah hanya bila izin tulis aturan). Tercatat di §6.
- **Berkas:** `features/settings/ApprovalRulesSettings.jsx`, `ApprovalRuleForm.jsx`, `EntityMastersView.jsx`, `config/hubTabs.js`.
- **Uji:** POC aturan persetujuan backend (tanpa perubahan API).
- **Cek:**
  - Manajer melihat aturan tanpa tombol ubah.
  - Admin menonaktifkan aturan → dialog konfirmasi → status berubah, tanpa jalur kedua.

### D-05: Tiga form pelanggan (P3 + P7 + P2)
- **Utama:** `features/crm/CustomerFormModal.jsx`, yang paling lengkap: segmen, sales penanggung jawab/tim, kebijakan lot, metode bayar/termin/DP, limit kredit, NPWP, alamat terstruktur `LocationFields`.
  - Dikonversi dari `.modal-card` ke FormModal + `FormSection` (L-03/L-10); di HP otomatis layar penuh 1 kolom (P1).
  - API baru `onSaved(customer, isEdit)` dan prop `variant` hanya mengatur urutan seksi; **tidak ada isian yang dibuang**.
- **Tautan/pemakaian ulang:**
  - POS desktop "Pelanggan baru": `features/pos/CreateCustomerModal.jsx` menjadi pembungkus CustomerFormModal; setelah simpan, pelanggan terpilih (`onCreated`). Dipakai di `CheckoutDrawer.jsx`, `SalesPortal.jsx`.
  - HP: `MobileCustomerForm.jsx` dan pemakaian di `MobileSalesApp.jsx` → pembungkus yang sama (P7).
  - Master Data › Impor/Ekspor & Status: form 8 isian di `AdminView` dihapus; tombol Buat membuka CustomerFormModal (P2).
  - `hooks/useAppActions.js:createCustomer` dipertahankan untuk kompatibilitas, tetapi pemanggil baru memakai `onCreated`.
- **Peran:** tidak berubah (`customer.create`; sales otomatis menjadi penanggung jawab, sudah ada di form).
- **Berkas:** P3: `crm/CustomerFormModal.jsx`, `pos/CreateCustomerModal.jsx`, `pos/CheckoutDrawer.jsx`, `sales/SalesPortal.jsx`, `hooks/useAppActions.js`. P7: `sales/mobile/MobileCustomerForm.jsx`, `MobileCustomers.jsx`, `MobileSalesApp.jsx`. P2: `admin/AdminView.jsx`.
- **Uji:** `audit2G2.test.js` G2-01/G2-22 (testid `create-customer-modal`, `create-customer-body`, `new-customer-*-input`, `create-customer-missing`, `create-customer-button`). Pertahankan lewat `testId` pembungkus, atau perbarui uji dengan menyebut alasannya.
- **Cek:**
  - POS desktop dan HP 390 px menampilkan isian yang sama dengan CRM; simpan → pelanggan terpilih di keranjang.
  - Master Data membuka form yang sama.

### D-06: Antrean persetujuan berlapis (P3 + P7 + P8)
- **Utama:** **Pusat Persetujuan** (`approval-inbox`, `ApprovalInbox.jsx`) sebagai satu antrean lintas jenis.
  - `MyApprovalsView` diekstrak menjadi `MyApprovalsPanel` (ACC desain, PO custom 2 tingkat, PR, klaim makloon + jejak keputusan).
  - Panel itu menjadi tab "Matriks divisi", digerbang `roleCanSee(["manager","admin"], role, "my-approvals")`.
  - Alasan: inbox sudah menjadi agregator semua jenis; matriks adalah satu jenis antrean.
- **Tautan:**
  - `my-approvals` → alias `approval-inbox` {tab:"matrix"}.
  - Tab inbox "Amandemen" → LinkCard berhitungan ke Pusat Amandemen; keputusan amandemen hanya di sana.
  - Control Tower "Antrean Persetujuan (N)" → kartu ringkas (total + chip per jenis yang membuka inbox {tab:<jenis>}) tanpa daftar ganda.
  - HP (P7): bagian "Antrean lintas tahap" hanya memuat dokumen yang tidak bisa diputus di HP (yang sudah tampil di daftar harga/pesanan khusus dibuang), masing-masing dengan "Buka layar lengkap".
- **Menu (P8):** tab `my-approvals` dicabut dari hub `approval-inbox`.
- **Peran:** setara. Matriks hanya untuk manager/admin seperti dulu; sales_admin tetap melihat inbox dalam mode baca.
- **Berkas:** P3: `approvals/ApprovalInbox.jsx`, `MyApprovalsView.jsx` (pembungkus `MyApprovalsPanel.jsx` baru), `home/AdminHome.jsx`. P7: `mobile/MobileOpsApp.jsx`. P8: konfigurasi + rute cadangan.
- **Uji:** `auditUi2G5b.test.js` G5-08 (≤5 tab HP), `decisionsD3.test.js` K-11, `uatV3ReturnsOps.test.js` (`resolveView`); backend `verify_approval_queues.py`, `test_core_f6_approval_coverage_poc.py`.
- **Cek:** `?view=my-approvals` membuka tab Matriks; jumlah di Control Tower = inbox; HP tanpa dokumen ganda.

### D-07: Papan PO Custom di 4 tempat (P3 + P7 + P1)
- **Utama:** **Pesanan Khusus** (`special-orders`) tab "Menunggu persetujuan" + `SpecialOrderDetail`. Satu dialog Setujui/Tolak = `services/approvalDecisions.js` (P1), dipakai:
  - `SpecialOrderDetail` (sekarang askConfirm tanpa catatan),
  - `MobileApprovalInbox` (askReason, catatan opsional),
  - `MyApprovalsPanel` (approveSpecialOrder di `approvalsMatrixApi.js`).
- **Tautan:**
  - Papan `special_order` di Control Tower, Dasbor Manajer, Beranda Sales dan Beranda HP Sales → `mode="link"`: baris membuka SORD terfokus, tanpa tombol Setujui.
  - HP Persetujuan tetap menjadi tempat keputusan di HP (tidak ada layar desktop di HP), memakai dialog yang sama.
  - `config/waitingBoards.js`: teks "Buka Pesanan Khusus →", aksen biru.
- **Peran:** tidak berubah (izin `order.approve`; K-11 Admin Sample tetap tanpa SORD).
- **Berkas:** P1: `services/approvalDecisions.js`, `components/WaitingQueueBoard.jsx`. P3: `home/AdminHome.jsx`, `ManagerHome.jsx`, `SalesHome.jsx`, `sales/SpecialOrderDetail.jsx`, `SpecialOrders.jsx`, `approvals/approvalsMatrixApi.js`, `config/waitingBoards.js`. P7: `mobile/MobileApprovalInbox.jsx`, `sales/mobile/MobileSalesHome.jsx`.
- **Uji:** `auditUi2G5b.test.js` G5-09, `decisionsD3.test.js` K-11, `uatV3SpecialOrder.test.js`; `verify_home_kpi.py`, `verify_approval_queues.py`.
- **Cek:** papan beranda tanpa tombol Setujui; klik baris membuka dokumen; dialog desktop dan HP identik (judul, catatan opsional, pesan hasil).

### D-08: Rapor desainer di 3 tempat (P6 + P8)
- **Utama:**
  - Menilai tim: **Desainer › KPI Desainer** (`designer-kpi`) dengan PageTabs "Skor & SLA" | "Pekerjaan DSR" (`DesignerReportPanel` dipindah ke sini).
  - Diri sendiri: **Profil Saya › KPI Saya** (`MyDesignerKpiCard` + `MyDesignerReportPanel` dalam satu kartu bertab). Endpoint privasi tetap (`/design/reports/mine`, `/rnd/reports/my-kpi`).
- **Tautan:** Permintaan Desain tab "Rapor Desainer" → tombol tautan `designer-kpi` {tab:"dsr"}; tab "Rapor Saya" → `hr-my-profile` {section:"kpi"}.
- **Peran:** setara. `canReport` = admin/manager = peran `designer-kpi`. Desainer membuka Profil Saya (ROLE_NAV designer sudah memuat `hr-my-profile`).
- **Berkas:** `features/designer/DesignerKpiView.jsx`, `features/design/DesignRequestsView.jsx`, `DesignerReportPanel.jsx`, `MyDesignerReportPanel.jsx`, `features/hr/EmployeeSelfService.jsx`, `MyDesignerKpiCard.jsx`.
- **Uji:** `decisionsD3.test.js` K-08, `auditUi2G5a.test.js` G5-38.
- **Cek:** admin klik "Rapor desainer" → KPI Desainer tab DSR; desainer melihat angka sendiri tanpa nama rekan.

### D-09: Dua "galeri" desain (P6 + P7 + P8)
- **Utama:** **Desain & Pattern** (`rnd-designs`, `RndDesignsView`), master lengkap (kode, versi, pengesahan, buat).
  - Tambah mode tampilan **Galeri** (kartu sampul + saringan kepemilikan/diproduksi dari `DesignGalleryView`).
  - Klik kartu membuka rincian desain yang sama. Isi unik showcase (kepemilikan/klaim, ilustrasi AI) menjadi panel di rincian. `DesignShowcaseModal` keluar dari alur.
- **Tautan:**
  - `cs-design-gallery` → alias `rnd-designs` {mode:"gallery", status:"acc"}; `DesignGalleryView` menjadi pembungkus tipis.
  - Menu HP MD "Galeri & Studio Desain" → label "Desain & Pattern" (P7).
  - Antrean backend `design_gallery` (target `cs-design-gallery`) tetap berfungsi lewat rute cadangan.
- **Peran:** setara (admin, manager + designer/md via ROLE_NAV di keduanya).
- **Berkas:** `features/rnd/RndDesignsView.jsx`, `rnd/design/*`, `features/hr/DesignGalleryView.jsx`, `DesignShowcaseModal.jsx`, `DesignOwnershipPanel.jsx`, `AiIllustrationPanel.jsx`; P7 `sales/mobile/MobileMdApp.jsx`.
- **Uji:** `auditUi2G5a.test.js` G5-39; `verify_approval_queues.py`.
- **Cek:** `?view=cs-design-gallery` → Desain & Pattern mode Galeri; papan "Desain menunggu pengesahan" membuka layar yang sama.

### D-10: Ringkasan laba-rugi berulang (P4)
- **Utama:** Akuntansi & Pajak › Laporan › **Laba-Rugi** (`financial-statements`).
- **Tautan/ringkas:**
  - Dasbor Keuangan: baris KPI YTD (Pendapatan/Laba/Marjin, ditambah "Marjin Bersih" dan "Posisi Kas" yang muncul dua kali) dipadatkan menjadi satu kartu "Laba-Rugi YTD" + "Rincian di Laporan Keuangan →".
  - BI Keuangan: kartu KPI atas dihapus; yang tersisa tren, rasio (Marjin Bersih sekali), dan perbandingan PT + tautan.
  - Konsolidasi: tetap, berlabel "setelah eliminasi antar-PT".
  - Tutup Buku: pratinjau tetap (bagian dari konfirmasi) + tautan.
- **Peran:** sama (admin, manager).
- **Berkas:** `features/finance/FinanceTowerView.jsx`, `BiFinanceView.jsx`, `GroupConsolidationView.jsx`, `ClosingView.jsx`.
- **Uji:** `decisionsD1.test.js` (label sumber K-01/K-02 tetap).
- **Cek:** angka YTD di Dasbor sama dengan Laba-Rugi; tidak ada metrik ganda di satu layar.

### D-11: Margin di beberapa layar (P4 + P8)
- **Utama:** **Profitabilitas & Margin** (`profitability`) dengan PageTabs "Realisasi (pelanggan/sales/produk)" | "Margin katalog (HPP/WAC)". `CostingView` menjadi panel di tab kedua. Alasan: profitabilitas sudah punya realisasi + `qty_by_unit`; margin katalog adalah pelengkapnya.
- **Tautan:** tab Analitik › Margin & HPP (`costing`) → alias `profitability` {tab:"katalog"}; tautan "Profitabilitas per pelanggan →" di CostingView dihapus.
- **Peran:** bawaan setara (admin, manager). Peran kustom: modul `reports` (memuat `costing`) ditambah `profitability` dan `fin-reports` (P8). Tab katalog digerbang izin endpoint `/costing/wac`, tab realisasi digerbang izin akuntansi.
- **Berkas:** `features/finance/ProfitabilityView.jsx`, `features/costing/CostingView.jsx`; P8: menu + `access_modules.py`.
- **Uji:** fixture/`navAccess.test.js` (P8).
- **Cek:** `?view=costing` → tab Margin katalog; hub Analitik tanpa tab Margin.

### D-14: Pemilih badan usaha lokal (P3 + P4; komponen dari P1)
- **Utama:** pemilih di header (`EntitySwitcher`) satu-satunya sumber.
  - Tutup Buku: hapus `closing-entity-select` dan KPI `closing-kpi-entity`.
  - Buka Periode dan Harga per BU (`pl-entity-select`): pemilih lokal dihapus.
  - Mode "Semua" → `EntityRequiredNotice` (memilih PT = mengubah header). Akun satu-PT tidak terpengaruh.
- **Berkas:** P4 `finance/ClosingView.jsx`, `PeriodUnlockView.jsx`; P3 `sales/PricelistView.jsx`.
- **Uji:** `decisionsD1.test.js` (alur K-15 Tutup Buku harus tetap lolos).
- **Cek:** header Sukacita → layar langsung Sukacita tanpa pemilih kedua; header "Semua" → kartu pilih PT.

### D-15: Dua alur stock opname (P5 + P8)
- **Utama:** Operasi Gudang › **Stock Opname** (`CycleCount`, mengubah stok via persetujuan). Tambah bagian "Metode: Sapu RFID (laporan saja)" yang merender `CycleCountPanel`, digerbang izin RFID. Testid `wms-tab-cycle` dipertahankan (dituntut `check_nav_map.py`).
- **Tautan:** Lokasi RFID tab "Stock Opname (RFID)" → LinkCard ke `operations` {tab:"cycle", method:"rfid", warehouse}.
- **Peran:** setara (hub RFID: admin, warehouse ⊆ peran Operasi Gudang).
- **Berkas:** `features/wms/OperationsView.jsx`, `features/inventory/CycleCount.jsx`, `features/rfid/CycleCountPanel.jsx`, `RfidLocationsView.jsx`.
- **Uji:** POC RFID cycle count backend; `check_nav_map.py`.
- **Cek:** sapuan RFID dimulai dari Operasi Gudang; Lokasi RFID hanya menampilkan tautan.

### D-16: Transfer tampil di dua sub-tab (P5 + P8)
- **Utama:** Operasi Gudang › Transfer: satu daftar (`TransferManagement`) dengan kolom "Jenis" + FilterChips (Semua/Antar gudang/Antar PT). Satu `TransferDetailModal` dengan aksi sesuai jenis: tombol biru "Setujui", untuk antar-PT berlabel "Setujui & pindahkan kepemilikan"; status lewat `docStatusLabel` ("Waiting Approval" hilang).
- **Tautan:** StatusTabs "Antar entitas (PT)" dihapus; `InterCompanyTransfers.jsx` → pembungkus `TransferManagement kindFilter="inter_entity"`; `interco-transfers` → alias `operations` {tab:"transfer", kind:"inter_entity"}.
- **Peran:** aksi antar-PT tetap untuk `IC_ROLES`/manager-admin.
- **Berkas:** `wms/OperationsView.jsx`, `wms/TransferManagement.jsx`, `wms/transfer/TransferDetailModal.jsx`, `transferConstants.jsx`, `transfers/InterCompanyTransfers.jsx`.
- **Uji:** `features/wms/transfer/__tests__/TransferDetailModal.test.js`; uji transfer backend; `verify_approval_queues.py` (papan transfer → `operations`).
- **Cek:** KSC/TRF-0000x tampil sekali dengan satu gaya tombol.

### D-17: Dua dasbor pesanan + tiga kontrol filter (P3)
- **Utama dasbor:** Penjualan › Pesanan › **Dasbor** (`OrderDashboard`). Widget pesanan dari `ManagerDashboard` (corong, pelanggan teratas, kecepatan) dipindah ke `OrderAnalyticsPanel` bersama dengan sumber server `/reports/reservation-funnel` dan `/reports/top-customers` (`order.view`, cakupan sales, populasi K-06). Alasan: bisa dibuka sales, dan angkanya satu sumber.
- **Tautan:** Analitik › Ringkasan → widget pesanan diganti LinkCard; utilisasi gudang dan umur stok tetap di sana.
- **Filter:** satu kontrol = PageTabs status (hitungan + nilai Rp per tab). Kartu pipeline klik dihapus. Dropdown menjadi "Sub-status" yang hanya memuat sub-status tab aktif. Tombol pil "Dasbor & Analitik/Daftar Pesanan" → PageTabs dengan testid `tab-dashboard`/`tab-list` dipertahankan (tur `salesTours.js`, juga `dashboard-status-distribution`, `dashboard-top-customers`).
- **Berkas:** `orders/OrdersView.jsx`, `OrderDashboard.jsx`, `manager/ManagerDashboard.jsx`.
- **Uji:** backend `test_uat26_d2_decisions.py` (K-06); tur.
- **Cek:** corong di Pesanan sama dengan data yang dulu tampil di Analitik; satu filter status.

### D-18: Dua tingkat detail PO dan dua pintu cetak PR (P5)
- **Utama:** PO: klik baris membuka langsung pop-up rincian lengkap (`PODetailPanel`). `POCompactPanel` menjadi kepala ringkas + aksi di dalam pop-up (komponen dipertahankan karena diuji `roleGateSweep.test.js`). Daftar PO lebar penuh (sekaligus L-06). PR: `DocumentActionsBar` satu-satunya pintu cetak; tombol "Cetak PR" tidak ditemukan di HEAD, jadi verifikasi dulu (mungkin sudah dibereskan di fase 2).
- **Berkas:** `admin/PurchaseOrderManagement.jsx`, `admin/po/POCompactPanel.jsx`, `PODetailPanel.jsx`, `purchasing/PurchaseRequisitionDetailPanel.jsx`.
- **Uji:** `roleGateSweep.test.js`.
- **Cek:** satu klik baris = satu pop-up; tidak ada panel kanan kosong di 1440 px.

### D-19: Pengiriman (P5)
- **Utama:** Pengiriman › **Daftar** (`DeliveryTable`) ditambah rentang tanggal, CSV dan saringan status. Isi tab Riwayat (`HistoryPanel`) dilebur; `tab=history` → alias tab Daftar dengan saringan "selesai".
- **Tombol Buat:** satu tombol di PageHeader. Aksi kontekstual per Surat Jalan di Dasbor dipertahankan (terisi otomatis); "Buat pengiriman…" generik di kartu KPI (`dispatch-create-any`) dihapus.
- **Berkas:** `logistics/LogisticsView.jsx`, `DeliveryTable.jsx`, `HistoryPanel.jsx`, `DispatchDashboard.jsx`.
- **Uji:** `f06PodProgress.test.js`; uji logistik backend.

### D-20: PPN berulang (P4)
- **Utama:**
  - Rekap/posisi PPN: Pajak › **Pajak (PPN & PPh)** (`cs-pajak`) tab PPN.
  - Daftar faktur masukan: **Faktur Masukan** (`input-tax`).
- **Tautan:**
  - InputTaxView: kartu ringkasan atas dan tab "Rekap PPN" (`it-view-rekap`) → satu baris "Posisi PPN periode ini" + tautan ke cs-pajak (ringkas baca-saja bila peran tidak boleh membuka).
  - TaxCenterView: "Rincian Pajak Masukan per Pemasok" → LinkCard ke input-tax (periode sama).
- **Peran:** sama (admin, manager); peran kustom dijaga gerbang LinkCard.
- **Berkas:** `purchasing/InputTaxView.jsx`, `InputTaxCreateModal.jsx` (L-03), `finance/TaxCenterView.jsx`.
- **Cek:** angka PPN masukan hanya di satu tabel.

### D-21: Satuan dua daftar (P2)
- **Utama:** Produk & Harga › **Satuan & Konversi** = `UomConversionView` dengan satu tabel "Satuan & faktor" (kode, nama seragam dari `uomCatalog`, dimensi, faktor ke satuan dasar, sumber). Aksi "Satuan baru" (FormModal dari form AdminView) dan "Ubah faktor".
- **Tautan:** rute `md-uoms` merender `UomConversionView` (bukan AdminView tab uoms); `uom-conversions` → alias `md-uoms`.
- **Berkas:** `admin/uom/UomConversionView.jsx`, `UomConversionParts.jsx`, `admin/AdminView.jsx`, `AppViewRouter.jsx`.
- **Uji:** `ui05UnitsStates.test.js`, guardrail `verify_uom_vocab.py`.
- **Cek:** faktor satuan tampil sekali; nama satuan sama di seluruh layar.

### D-22: Kinerja mitra makloon di tiga tempat (P5 + P8)
- **Utama:** Pesanan Pembelian › **Kinerja Mitra Makloon** (`makloon-claim-recap`, `MakloonClaimRecapView`):
  - rekap susut & klaim,
  - bagian "Skor mitra" (`/makloon-partners/scorecard`),
  - klik mitra → DetailModal skor per mitra (`/makloons/{id}/scorecard`, komponen dari `Makloon360Panel`).
- **Tautan:** Klaim Selisih Makloon kartu "Skor Mitra Makloon" → LinkCard; `Makloon360Panel` tab "Skor Mitra" → LinkCard {partner}.
- **Peran:** gudang dulu melihat skor di Klaim, jadi tab recap + `warehouse` (P8). Bagian rekap digerbang izin endpoint-nya; bila gudang tidak berizin, hanya bagian skor yang tampil.
- **Berkas:** `purchasing/makloon/MakloonClaimRecapView.jsx`, `MakloonClaimsView.jsx`, `purchasing/Makloon360Panel.jsx`.
- **Uji:** `mkl02RecapPaging.test.js`, `uatV3NavWarehouseMakloon.test.js` (harapan diperbarui di P8).

### D-23: Harga internal dua tampilan (P5 + P8)
- **Utama:** Produk & Harga › **Harga Internal Antar-PT** (`internal-prices`, kartu pasangan + editor massal), dengan satu sumber angka (beda 21 vs 6 dibereskan).
- **Tautan:** Kontrak › tab "Harga Internal" + "Isi massal" → LinkCard. Manager dan gudang dulu melihatnya di Kontrak, tetapi tidak punya menu Produk & Harga untuk tab itu. Karena itu P8 menambah tab tersembunyi `supplier-internal-prices` (aliasOf `supplier-contracts`, peran = peran Kontrak) yang merender `InternalPricesView` dengan izin tulis dari server (`interco_price`).
- **Berkas:** `interco_prices/InternalPricesView.jsx`, `InternalPriceBulkPanel.jsx`, `purchasing/contracts/ContractsView.jsx`; P8: rute + hub + `access_modules` (modul interco & supplier).
- **Uji:** `roleGateSweep.test.js`.

### D-24: Sample dan spesifikasi (P3 a · P6 b,c · P5 preset Cutting)
- **(a) Utama:** Operasi Gudang › **Cutting** (`wms-cutting`) untuk "menunggu dipotong". Pesanan Sample › Meja Cutting (`samples/CuttingDesk.jsx`): bagian "Menunggu dipotong gudang" → ringkas (jumlah + nomor) + tautan bila peran boleh; bagian penerimaan potongan oleh Admin Cutting tetap.
- **(b) Utama:** R&D › `RndSamplesView` dengan PageTabs Papan · Daftar · **Galeri** (kartu `SampleTypeCard` + saringan hasil/bukti/skor dari `SampleTypeGalleryView`) serta chip jenis dan tujuan.
  - `rnd-labdip`/`rnd-handfeel`/`rnd-proofing` → alias `rnd-samples` {mode:"gallery", type}. Tombol "Sample <Jenis> Baru" → "Buat Permintaan" dengan jenis terkunci saat chip jenis aktif.
  - Hub R&D: Produk Baru · Uji Ulang · Laporan R&D. Empty state uji ulang tidak lagi membahas labdip.
- **(c) Utama:** `SpecFormModal` (lengkap). "Ubah spesifikasi" (`EditSpecModal` 6 isian di `SampleSpecPanel.jsx`) → SpecFormModal mode ubah.
- **Peran:** setara (daftar peran sama). `hidden_views` peran kustom untuk `rnd-labdip` dkk. menyembunyikan chip jenisnya.
- **Berkas:** P3 `samples/CuttingDesk.jsx`, `SampleOrdersView.jsx`; P6 `rnd/RndSamplesView.jsx`, `SampleTypeGalleryView.jsx` (pembungkus), `SampleTypeCard.jsx`, `SampleSpecPanel.jsx`, `SpecFormModal.jsx`; P5 `wms/CuttingOpsView.jsx` (preset); P7 label menu HP MD.
- **Uji:** `f15SamplePaymentReapproval.test.js`, `decisionsD3.test.js` K-16; backend `test_l01_custom_role.py`, `test_ln015_typed_rnd_and_role_version.py` (id `rnd-labdip` tetap sah).

### D-26: Pintu ke tampilan desktop di HP (P7)
- **Utama:** satu baris "Tampilan desktop" di menu Akun/Lainnya kerangka HP. Yang dihapus: ikon monitor di bilah atas (`mobile-force-desktop`), `DesktopPanel` di Ringkas (`mo-open-desktop`), dan baris kedua di MD.
- Sales Lainnya: "Hub lengkap · setara desktop" dan "Fitur lainnya · tampilan penuh" digabung menjadi satu seksi "Layar lengkap", tanpa butir yang sudah ada di submenu HP.
- **Berkas:** `mobile/MobileShell.jsx`, `MobileOpsApp.jsx`, `sales/mobile/MobileMore.jsx`, `MobileHubMenu.jsx`, `MoreSection.jsx`, `MobileMdApp.jsx`.
- **Uji:** `uatV3MobileSales.test.js`, `auditUi2G5b.test.js` G5-08, `decisionsD3.test.js` K-12.

### D-28: Stok HP dua daftar dan "Barang ditahan QC" (P7 + P3 + P5)
- **HP — Utama:** `MobileStockAtp` (`/inventory/status-board`, definisi "Tersedia" K-04). MD › "Status Stok" memakai komponen ini; `MobileStock` (`/inventory/balances`) dicabut.
- **Desktop — Utama:** Kualitas › **SPK Inspeksi** dengan preset saringan "Hanya ditahan" (keputusan lepas/tolak). Papan `inspection_hold` di Dasbor Manajer (P3) dan Operasi Gudang (P5, `WaitingBoardsStrip linkKeys`) → mode tautan.
- **Berkas:** P7 `sales/mobile/MobileMdApp.jsx`, `MobileFieldViews.jsx`; P3 `home/ManagerHome.jsx`; P5 `wms/OperationsView.jsx`, `inspections/QcHubView.jsx`/`InspectionsView.jsx`.
- **Uji:** `verify_home_kpi.py`.

### D-29: Dua menu "Perangkat" (P2)
- **Utama:** Pengaturan › Integrasi & Sistem › **Perangkat** (`settings-devices`, baru) dengan tab "Mesin absen" (dari Shift & Geofence) | "RFID (pembaca/gerbang)" (`RfidDevicesView`; form inline → FormModal untuk L-03).
- **Tautan:** Shift & Geofence tab Perangkat → LinkCard; `cs-rfid-devices` → alias `settings-devices` {tab:"rfid"}.
- **Peran:** item admin+manager; tab Mesin absen admin+manager (dulu `hr-attendance-setup`); tab RFID admin (dulu `cs-rfid-devices`). Katalog akses: id baru ke modul `hr`, `warehouse_ops`, `admin` (P8).
- **Berkas:** `settings/devices/DevicesView.jsx`(baru), `hr/AttendanceSetupView.jsx`, `rfid/RfidDevicesView.jsx`.
- **Penempatan:** lihat Q2.

## 4. Butir B (dibiarkan, dengan penyesuaian)
- **D-12 (P4):** layar dibiarkan; bucket umur Uang Muka Pelanggan disamakan dengan Piutang (Lancar/1-30/31-60/61-90/90+) lewat satu util `features/finance/agingBuckets.js` dipakai `AdvanceReportView.jsx` dan `ARAgingView.jsx`.
- **D-13 (P4):** layar dibiarkan; pastikan label sumber K-02 (D1) tampil di Rekening & Saldo, Transaksi Kas dan Proyeksi. Kartu "KAS KECIL PER ENTITAS" disembunyikan bila hanya satu PT (`CashManagementView.jsx`).
- **D-25 (P5 + P8):**
  - Nama diperjelas: "Resep Proses Makloon (konversi bahan → hasil)" dan "BOM Produksi In-House", dengan tautan silang satu kalimat di kepala masing-masing.
  - Komponen: `purchasing/ProcessRecipesView.jsx`, `production/ProductionView.jsx`.
  - Label menu/PAGE_META diubah di P8.
- **D-27 (P7, komponen dari P3/P6):** entri HP tetap ada, tetapi **form-nya komponen desktop**:
  - HP Permintaan Internal (`MobileInternalRequests.jsx`) → `InternalRequestCreateModal`. P3 lebih dulu mengubahnya dari `.modal-card` ke FormModal; di HP otomatis layar penuh.
  - Form DSR HP (`MobileMdViews.jsx` DesignCreate) → `DesignRequestCreateModal` (P6 memastikan layak HP; sudah FormModal).
  - Dialog Setujui HP → `approvalDecisions` (D-07).
- **D-29 sisanya:** ikon riwayat di Bagan Akun, dua tabel mutu pemasok di Barang Masuk, Posting Gagal vs blok NOT POSTED, dan notifikasi "PO datang" vs "Penerimaan selesai" tidak diubah.

## 5. Tata letak

### 5.1 L-04: Halaman desktop yang tampil mentah di HP (prioritas 1)
- **Keputusan kelas** (usulan bawaan, Q1):
  - **A — sudah punya versi HP:** aplikasi HP Sales/MD/Gudang/Ops. Tidak dibuka sebagai desktop.
  - **B — layak HP wajib:** semua layar yang bisa dibuka dari aplikasi HP (menu "Layar lengkap"/FULL, notifikasi, Meja, tombol QC): Permintaan Desain, Labdip/Desain & Pattern/Proofing (R&D), RFQ, SPK Inspeksi, Pesanan SO, Meja Admin Sample, Pesanan Sample, Barang Masuk, Control Tower, Dasbor Manajer, Order Makloon, Jejak Dokumen, Produk & Varian.
  - **C — cukup "buka di desktop":** seluruh Pengaturan, Bagan Akun, Konsolidasi, Desainer PDF, Master per BU, Registri Domain, Impor Dataset. Mendapat `DesktopOnlyNotice` di ≤640 px; layar tetap bisa dipakai.
- **Pola kelas B:**
  - KPI → `MetricRow` (2 kolom), bukan kartu satu kolom panjang.
  - Tab → `.tab-bar` satu baris bergulir (P1 CSS).
  - Kepala detail 3 kolom → `.detail-head-grid` (1 kolom).
  - Tabel `min-w` → `ResponsiveTable` (kartu) atau kolom aksi `sticky right-0`.
  - Form → FormModal layar penuh 1 kolom.
  - Pesan kosong dan pager di luar wadah gulir (P-05).
- **Layar dan berkas per paket:**
  - P3: `home/AdminHome.jsx`, `ManagerHome.jsx`, `orders/OrdersView.jsx` + `OrderDetailPanel.jsx`, `samples/SampleAdminDesk.jsx`, `SampleOrdersView.jsx`.
  - P5: `purchasing/RFQView.jsx`/`RFQDetailPanel.jsx`, `inspections/*`, `wms/grn/GoodsReceiptsView.jsx`.
  - P6: `design/DesignRequestsView.jsx`, `rnd/RndSamplesView.jsx`, `SampleTypeGalleryView.jsx`, `RndDesignsView.jsx`.
  - P2: DesktopOnlyNotice di layar Pengaturan.
- **Urutan:** primitif P1 → tiap paket mengerjakan layar B miliknya sebelum L-03.
- **Cek:** crawl HP 390 px (alat `scratchpad/hpapp*`): `scrollWidth ≤ clientWidth`, KPI ≤ 2 baris layar, tab 1 baris, aksi utama terlihat tanpa gulir samping.
- **Risiko:**
  - Aturan CSS global `.tab-bar` memengaruhi semua layar → uji visual 1440 dan 390.
  - Kartu tabel menyembunyikan kolom → kolom prioritas wajib ditetapkan per layar.
  - Aturan `:has(grid-cols-[…])` lama di `components.css` harus tetap kompatibel.

### 5.2 L-03: Pop-up buatan sendiri → FormModal/DetailModal (prioritas 2)
| Paket | Layar dan berkas |
|---|---|
| P2 | md-categories (`admin/CategoryManager.jsx`, `AdminView.jsx`), Buat Template Dokumen (D-01), cs-rfid-devices inline (`rfid/RfidDevicesView.jsx`), incentive-rates panel tetap (`crm/IncentiveRatesEditor.jsx`) |
| P3 | cs-price-list (`sales/customerPricelist/*Modal.jsx`), Tambah/Ubah Warna (`sales/ColorLibraryView.jsx`, `ColorUseRequestModal.jsx`), `crm/CustomerFormModal.jsx`, `internal_requests/InternalRequestCreateModal.jsx` |
| P4 | contra-bons Jadwal (`purchasing/contrabon/ExchangeScheduleModal.jsx`, `PaymentScheduleModal.jsx`), consolidation (`finance/GroupConsolidationView.jsx`), interco (`finance/interco/Interco*Modal.jsx`, `InternalContractWizardModal.jsx`; tombol hitam → `.primary-button`), fixed-assets (`FixedAssetsView.jsx`, `FixedAssetsParts.jsx`), document-center WA/TTD/Kirim (`documents/WhatsAppModal.jsx`, `ESignModal.jsx`, `DocumentCenter.jsx`), chart-of-accounts buat inline (`ChartOfAccounts.jsx`), cash-advances halaman penuh (`pettycash/CashAdvancesView.jsx`, `CashAdvanceForm.jsx`, `CashAdvanceDetail.jsx`), settlements (`SettlementsView.jsx`, `SettlementForm.jsx`), budget inline (`BudgetView.jsx`), input-tax (`InputTaxCreateModal.jsx`) |
| P5 | blanket-po (`purchasing/BlanketPOCreateModal.jsx`, `CallOffModal.jsx`), RFQ (`RFQCreateModal.jsx`), PR Baru (`PurchaseRequisitions.jsx`), md-warehouses 4 pola (`wms/warehouses/*`), makloons (`MakloonFormModal.jsx`), process-recipes (`RecipeFormModal.jsx`) |
| P6 | Riwayat Labdip (`rnd/LabdipHistoryModal.jsx`), LifecycleActions (`rnd/design/LifecycleActions.jsx`), Sheet SDM (`hr/EmployeeFormDrawer.jsx`), ESS cuti (`hr/MyLeaveCard.jsx` → FormModal yang sama dengan `LeaveView`), cs-kpi (`hr/KpiView.jsx`) |

- **Cek:** `verify_custom_modals.py` turun per berkas; `verify_modal_dismiss.py`, `verify_escape_layers.py`, `verify_detail_modal.py` hijau; Esc/klik latar/KNSelect di dalam modal tidak membuang isian (INV-UI-01/10).
- **Risiko:** form bersarang (komponen ber-`<form>` sendiri → FormModal tanpa `onSubmit`); fokus awal; ukuran `size` yang pas.

### 5.3 L-01 dan L-05: Navigasi berlapis, menu Pengaturan, sidebar (prioritas 3)
- **L-01 (aturan §1.4).** Layar, paket dan perubahannya:
  - **P2:** `admin` (tab AdminView → PageTabs), `entities-access`/`permission-matrix` (`settings/entities/*`), `pdf-templates` (`pdf/PdfEditorTabs.jsx`).
  - **P3:**
    - `orders`: pil biru → PageTabs (D-17).
    - `keep-pending`: `sales_admin/KeepPendingPanel.jsx`.
  - **P4:** `amendments` (`finance/amendments/*`), `bank-reconciliation`, `contra-bons`, `budget`, `chart-of-accounts`, `consolidation`, `financial-statements`, `general-ledger`, `input-tax`.
  - **P5:**
    - `operations`: testid `wms-tab-*` dipertahankan.
    - `inventory-lots`: `inventory/lots/*`.
    - `inspections`: `inspections/QcHubView.jsx`.
  - **P6:**
    - `design-requests`: tombol-toggle → PageTabs.
    - `rnd-revalidation`/`rnd-specs`: pil jenis → FilterChips.
    - `hr-attendance`: `hr/AttendanceView.jsx`.
- **L-05:**
  1. **Pengaturan (P16-K1, P2).** `settings-hub` diubah dari standalone menjadi **grup sidebar** dengan groupId tetap `settings-hub` (ROLE_NAV `sales_admin` dan katalog modul `admin` tetap sah). Isi grup:

     | Kelompok | Tab hub |
     |---|---|
     | Perusahaan & Akun (`settings-company`) | `entities-access` (+alias `permission-matrix`) |
     | Persetujuan (`settings-approval`) | `approval-rules` · matriks approver dari `rnd-divisions` · `settings-cfg-approval` (grup `persetujuan`) |
     | — sub-judul "Kebijakan per Domain" — | |
     | Penjualan (`settings-sales`) | `settings-cfg-sales` (harga-diskon tanpa commission.*, retur, amandemen) · `amendment-reasons` · `incentive-rates` (D-03) · `return-policies` (dipindah dari hub Retur) |
     | Gudang & Mutu (`settings-warehouse`) | `settings-cfg-warehouse` (penerimaan, stok-satuan, kualitas, lot) · `settings-receiving-ocr` · `grade-master` |
     | Pembelian & Produksi (`settings-purchasing`) | `settings-cfg-purchasing` (pembelian, makloon, kontrabon) |
     | Keuangan & Pajak (`settings-finance`) | `settings-cfg-finance` (uang-masuk, pajak, keuangan-dasar, bank, kasus, antar-entitas) · `gl-account-mappings` · `expense-categories` · `bank-recon-rules` |
     | SDM (`settings-hr`) | `settings-cfg-hr` (sdm) · `hr-attendance-setup` (Shift & Geofence) |
     | R&D (`settings-rnd`) | `settings-cfg-rnd` (rnd) · penempatan tim dari `rnd-divisions` |
     | — — | |
     | Master Data (`settings-masters`) | `entity-masters` (indeks tautan master domain di kepalanya; kind yang punya rumah domain → LinkCard) · `domain-registry` · `client-dataset-import` |
     | Dokumen & Cetak (`settings-documents`) | `pdf-templates` (D-01) · `settings-cfg-documents` (dokumen) |
     | Notifikasi & Penjadwal (`settings-notify`) | `scheduler` · `settings-cfg-notify` (notifikasi) |
     | Integrasi & Sistem (`settings-system`) | `admin` (Integrasi & Audit) · `settings-config` "Semua pengaturan" (cari, kesehatan, riwayat, kunci proses, kebersihan data — `view: "settings-config"` wajib tetap ada untuk `audit_config_wiring.py`) · `settings-devices` (D-29) |

     - **Koreksi Harga** (tab `impact` SettingsHub) pindah menjadi view `price-corrections` di hub Produk & Harga (admin, manager).
     - `DivisionsView` dipecah menjadi panel "Penempatan tim" (R&D) dan "Matriks approver" (Persetujuan) dengan view id tetap `rnd-divisions`. Satu id hanya boleh di satu hub, jadi bawaannya: id tetap di Persetujuan, sedangkan panel tim dirender juga di `settings-cfg-rnd` sebagai seksi.
     - Kunci setelan baru dari D2 (K-05/B1) dan grup baru wajib dipetakan ke salah satu `settings-cfg-*` (uji: tidak ada grup registry yang yatim).
     - Deep link `?config=<kunci>` (`hooks/useDeepLinks.js`, `settings/config/configDeepLink.js`) diarahkan ke `settings-cfg-*` yang memuat grup kunci itu.
     - Peran:
       - manager: semua yang dulu terlihat;
       - warehouse_admin: Gudang & Mutu (`settings-receiving-ocr`, `grade-master`);
       - sales_admin: Penjualan › `return-policies`, lewat ROLE_NAV add id item/tab baru;
       - md: sesuai hasil K-11 D3 (hanya R&D, baca).
     - Semua editor lama **mempertahankan view id** (tanpa alias); yang baru hanya view `settings-cfg-*`, `settings-devices` dan `price-corrections`.
  2. **Sidebar (P1):** label 2 baris + tooltip, sub-judul di dalam grup.
  3. **Breadcrumb dari menu (P1):** perbaiki kicker amendments ("Keuangan · Kendali" padahal ada di Penjualan › Pesanan), cs-stock-analytics, costing, consolidation, financial-statements, profitability, interco ("Pembelian" padahal ada di Akuntansi & Pajak).
- **Cek:**
  - Tidak ada baris pil bersisipan label seksi.
  - Breadcrumb sama dengan sorotan sidebar untuk 7 layar di atas.
  - Uji jangkauan peran sama dengan baseline.
  - `navAccess.test.js` dan fixture diperbarui (P8).
- **Risiko:** pemindahan `return-policies` dari hub Retur (sales_admin harus tetap mencapainya); tumpang tindih dengan K-11 D3 (MD); peran kustom (katalog `access_modules` harus memuat id item/hub baru, oleh P8).

### 5.4 L-09: Satu kerangka aplikasi HP (prioritas 4, P7)
- **`features/mobile/MobileShell.jsx` v2:**
  - Appbar seragam (gradien biru standar; ungu MD dan pil merah Gudang hilang).
  - Tombol lonceng membuka `NotifSheet` (dari `sales/mobile/MobileNotifSheet.jsx`) untuk semua peran.
  - Tab terkendali (`tab`/`onTabChange`) dengan lencana per tab (keranjang).
  - Slot `main` flush.
  - Tab terakhir standar "Lainnya/Akun" (`MobileAccountMenu`, baru): profil, pengalih PT, kartu push/pasang, **satu** "Tampilan desktop" (D-26), Keluar.
- **Aplikasi yang dipindah ke kerangka v2:** `sales/mobile/MobileSalesApp.jsx` dan `MobileMdApp.jsx` (sekarang punya header/tabbar sendiri), serta `mobile/MobileWarehouseApp.jsx` dan `MobileOpsApp.jsx` (sudah memakai MobileShell lama).
- **`App.js`:** meneruskan notifikasi dan `onSelectEntity` ke aplikasi Ops/Gudang.
- **CSS:** satu set di `styles/mobile.css`.
- **Uji:** `auditUi2G5b.test.js` (≤5 tab), `decisionsD3.test.js` (K-11/K-12), `uatV3MobileSales.test.js`, `audit2G2.test.js` (kartu SO HP), `uatV3ReturnsOps.test.js` (MobileOrders); tambah `mobileShell.test.js`.
- **Cek:** empat aplikasi HP: header/lonceng/tab bar identik, satu pintu desktop, ≤5 tab.
- **Risiko:**
  - Notifikasi push/service worker (`syncPushSubscription`) jangan dipanggil dobel.
  - Pintasan PWA `?m=`/`?notif=` di MobileSalesApp harus tetap jalan.
  - Testid yang dipakai uji/crawler (`mobile-tab-btn-*`, `m-md-tab-*`, `mobile-notif-btn`, `m-md-notif-btn`) dipertahankan atau dipetakan.

### 5.5 Sisanya (prioritas 5)
- **L-02** (kepala halaman → `PageHeader` + `.section-card`):
  - P2: approval-rules, cs-rfid-devices.
  - P4: bank-reconciliation, contra-bons, finance-cases, export-center.
  - P5: cs-rfid-gate/tags/lokasi, cs-stock-analytics, escalations, repair-orders.
  - P6: mkt-accounts.
  - P3: product-templates (`catalog/CatalogWorkspace.jsx`, h1 28 px → `view-title`).
- **L-06** (tabel lebar di 1440 px; kolom prioritas, pemilih "Kolom", rincian di DetailModal):
  - P6: designer-kpi.
  - P5: purchasing (D-18), operations (KPI BTK).
  - P3: returns (tabel item & roll).
  - P2: entity-masters.
- **L-07** (`<table>`/grid mentah → `.data-table` / `ResponsiveTable`):
  - P6: KpiView, AttendanceView.
  - P4: ARAging, Settlements, consolidation.
  - P5: RfidTags, StockAnalytics, InspectionsView.
  - P2: DivisionsView.
- **L-08** (gaya KPI dan bilah alat):
  - `MetricRow` baku (tanpa garis kiri warna-warni); nilai 0 netral; aksen #6B219A/#6C3FD1 → `--ios-blue`.
  - Bilah alat padat → tombol "Saring (n)" ke panel lipat; berlaku di designer-kpi, mkt-calendar dan consolidation.
  - Pembagian: P4 budget/Arus Kas/Perubahan Ekuitas/landed-cost/consolidation; P5 makloon recap/logistics/inventory-board; P6 hr-leave/designer-kpi/mkt-calendar.
- **L-10** (form panjang → `FormSection` bernomor, sumbu varian terlipat, ringkasan + tombol tetap):
  - P3: Induk produk baru (`catalog/FamilyForm.jsx`), form Pelanggan CRM (D-05).
  - P2: Buat Template Dokumen.
  - P6: form Karyawan (`hr/EmployeeFormDrawer.jsx`).
  - P5: form Kontrak (rumus) (`purchasing/contracts/ContractFormModal.jsx`), Wizard Order Makloon (`purchasing/makloon/MakloonWizard.jsx`, stepper baku).

## 6. Tabel aktivasi (P8, kecuali yang ditandai P2)
| View lama | Tujuan | Preset | Menu | Katalog akses (`access_modules`) |
|---|---|---|---|---|
| `my-approvals` | `approval-inbox` | tab=matrix | cabut tab di hub approval-inbox | – (modul approval sudah memuat keduanya) |
| `cs-design-gallery` | `rnd-designs` | mode=gallery,status=acc | cabut tab di designer-hub | – (design memuat keduanya) |
| `costing` | `profitability` | tab=katalog | cabut tab di analytics | reports + `profitability`, `fin-reports` |
| `interco-transfers` | `operations` | tab=transfer,kind=inter_entity | tab tersembunyi tetap | – |
| `rnd-labdip` / `rnd-handfeel` / `rnd-proofing` | `rnd-samples` | mode=gallery,type=… | cabut 3 tab di rnd-hub | – |
| `doc-templates-basic` (P2) | `pdf-templates` | tab=dasar | cabut tab | admin (sudah ada `pdf-templates`) |
| `uom-conversions` (P2) | `md-uoms` | – | – | – |
| `cs-rfid-devices` (P2) | `settings-devices` | tab=rfid | pindah ke settings-system | warehouse_ops + hr + admin + `settings-devices` |
| baru: `supplier-internal-prices` | merender InternalPricesView | pair | tab tersembunyi di master-pembelian (peran = supplier-contracts) | interco + supplier |
| baru (P2): `settings-*`, `settings-cfg-*`, `price-corrections` | – | – | grup Pengaturan | admin + modul domain terkait (sales→penjualan/pricing, warehouse→warehouse_ops/inspection, purchasing→purchasing/supplier/payable, finance→ar/finance_ops/accounting/petty_cash, hr→hr, rnd→rnd/design); price-corrections → pricing |

Perubahan peran yang tercatat (satu-satunya penambahan yang boleh muncul di baseline jangkauan):
- `approval-rules` + manager (baca, D-04);
- `pdf-templates` + manager (tab dasar, D-01);
- `makloon-claim-recap` + warehouse (D-22);
- `settings-devices` admin+manager (D-29).

Label yang diubah: `makloon-claim-recap` → "Kinerja Mitra Makloon", `process-recipes`/`production` (D-25), `profitability`, `pdf-templates` → "Template Dokumen".

## 7. Uji dan verifikasi
- **Per paket:**
  - Jest relevan `--maxWorkers=1`; ESLint 0 error di berkas yang berubah; pyflakes untuk backend.
  - Guardrail yang menyentuh berkas paket.
  - Laporan memuat: id butir, berkas:baris, cara cek, uji, perubahan perilaku, dan kebutuhan menu untuk P8.
- **Uji frontend terdampak:**
  - Konfigurasi menu: `config/__tests__/navAccess.test.js` (+fixture), `features/__tests__/f11LayarOperatorView.test.js` (hub Retur tanpa Kebijakan Retur), `uatV3NavWarehouseMakloon.test.js`.
  - Per butir: `audit2G2.test.js` (D-05), `auditUi2G5b.test.js` (D-06/D-26/P2 masterFieldsConfig & SettingsHub), `decisionsD3.test.js` (D-06/D-08/D-24/L-09), `decisionsD1.test.js` (D-10/D-14), `uatV3MobileSales.test.js` (D-26), `f15SamplePaymentReapproval.test.js` (D-24a), `mkl02RecapPaging.test.js` (D-22), `roleGateSweep.test.js` (D-18/D-23), `features/wms/transfer/__tests__/TransferDetailModal.test.js` (D-16), `uatV3ReturnsOps.test.js` (resolveView), `fe06PriceFocus.test.js`, `f06PodProgress.test.js` (D-19), `auditUi2G5a.test.js` (D-08/D-09), `uatV3SpecialOrder.test.js` (D-07), `trial22Okt.test.js` (luas).
  - Tur `data/tours/*.js`: testid dipertahankan.
- **Uji backend dan guardrail:**
  - `backend/tests/test_fe03_access_catalog.py`, `test_l01_custom_role.py`, `test_ln015_typed_rnd_and_role_version.py`, `test_core_e4_master_layers_poc.py`.
  - `test_core_role_access_poc.py`, `test_core_e8_roles_poc.py`, `test_core_f6_approval_coverage_poc.py`, `test_core_approval_reminder_poc.py`, `test_gl01_account_mapping.py`, `test_uat26_d2_decisions.py`.
  - `scripts/check_nav_map.py`, `audit_config_wiring.py`, `audit_ia.py`.
  - `scripts/guardrails/verify_access_catalog_nav.py`, `verify_desk_targets.py`, `verify_home_kpi.py`, `verify_approval_queues.py`, `verify_detail_modal.py`, `verify_modal_dismiss.py`, `verify_escape_layers.py`, `verify_uom_vocab.py`.
  - Guardrail baru dari P1.
- **Uji backend yang butuh HTTP** → ditulis lalu dicatat untuk koordinator. Aturan `decisions_brief`: jangan restart kontainer.
- **Akhir (P8):**
  - Crawl ulang desktop 1440 dan HP 390 untuk semua layar D/L, termasuk `?view=<lama>` untuk setiap alias.
  - Login per peran bawaan (admin, manager, sales, sales_admin, finance, warehouse, warehouse_admin, md, designer, sample_admin, qc, md_quality, driver): menu dan layar yang tercapai sama dengan baseline.

## 8. Risiko utama
1. **Aktivasi menu tertunda ke P8.** Selama fase paralel, layar utama sudah berisi gabungan tetapi tab lama masih tampil. Ini aman (tidak ada fungsi hilang), tetapi **jangan rilis ke UAT sebelum P8 selesai**.
2. **Berkas yang di-rebase di atas hasil D1/D2/D3** (lihat §1.6). Jalankan ulang uji `decisions*` setelah rebase.
3. **Katalog akses peran kustom.** Setiap id menu baru wajib masuk `MODULE_CATALOG.nav`. Kalau tidak, `verify_access_catalog_nav.py` merah dan pengguna berizin kehilangan pintu kerjanya.
4. **Batas 500 baris.** Ekstraksi wajib di `AppViewRouter`, `App.js`, `SettingsHub`, `EntityMastersView`, `ApprovalInbox` dan `RndSamplesView`.
5. **Mencabut "papan bisa ditindak"** untuk PO Custom dan Barang ditahan QC (D-07/D-28) mengubah kebiasaan pengguna (Q4).
6. **`hidden_views` peran kustom** yang menunjuk id yang kini menjadi alias (`rnd-labdip` dkk.) harus dipetakan ke chip/tab di layar utama. Kalau tidak, penyembunyian diam-diam gugur.

## 9. Pertanyaan sisa (dengan usulan bawaan)
1. **L-04 kelas layar.** Bawaan: kelas B dan C seperti §5.1. Semua layar yang bisa dibuka dari aplikasi HP dibuat layak 390 px; Pengaturan, akuntansi, master dan konsolidasi cukup diberi banner "paling nyaman di desktop".
2. **D-29: letak layar "Perangkat" gabungan.** Bawaan: Pengaturan › Integrasi & Sistem (admin + manager; tab RFID hanya admin). Alternatifnya Gudang & Mutu.
3. **D-24b: tab Labdip/Handfeel/Proofing hilang dari bilah R&D.** Ini membalik permintaan UAT 24 Okt yang meminta "galeri per jenis". Bawaan: digabung (keputusan G terbaru yang berlaku); galeri tetap ada sebagai mode tampilan dengan chip jenis.
4. **D-07/D-28: papan beranda PO Custom dan Barang ditahan QC menjadi tautan** (tanpa tombol Setujui/Lepas). Bawaan: ya, hanya untuk dua papan itu; papan lain (kontrabon, retur antar-PT, tagihan, opname, transfer) tetap bisa ditindak karena tidak termasuk D.
5. **D-02: data kembar "Office Supplies"/"ATK"** yang sama-sama ke 6-4100. Bawaan: tidak disentuh; hanya peringatan di layar sampai pemilik mengizinkan pembersihan data.
6. **"Semua pengaturan"** (Pusat Pengaturan penuh: cari, riwayat, kesehatan, kunci proses, kebersihan data). Bawaan: Pengaturan › Integrasi & Sistem untuk admin + manager, dan pencarian kunci di sana tetap lintas semua kelompok.

### Critical Files for Implementation
- C:\Users\abc\Documents\Codex\KNHOST\frontend\src\config\hubTabs.js
- C:\Users\abc\Documents\Codex\KNHOST\frontend\src\config\navigationConfig.js
- C:\Users\abc\Documents\Codex\KNHOST\frontend\src\AppViewRouter.jsx
- C:\Users\abc\Documents\Codex\KNHOST\frontend\src\features\settings\masters\EntityMastersView.jsx
- C:\Users\abc\Documents\Codex\KNHOST\backend\access_modules.py
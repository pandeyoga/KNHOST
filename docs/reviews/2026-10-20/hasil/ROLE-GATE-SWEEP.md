# ROLE-GATE-SWEEP — Sisir gerbang nama peran di frontend

- Commit awal: `f3496b0` · Commit perbaikan: `ac62dc3` · Branch: `main`
- ID ditangani: ROLE-01 (usulan implementer; lanjutan kelas FE-04 — "81 gerbang" yang dicatat di
  [UI-03](UI-03.md) sebagai keterbatasan)
- Lingkungan uji: Docker lokal, data acuan `scripts/dev_restore_demo.sh`, matriks izin dibaca dari DB
  (`permission_settings`), jest (`craco test`) di container frontend

## ROLE-01 — Tombol/aksi dibatasi nama peran, padahal server menegakkan izin
- **Berlaku di HEAD:** ya. Pola `["…"].includes(user?.role)` / `role === "…"` ditemukan di
  **83 lokasi dalam 72 berkas** (UI-03 menyebut 81/69 karena App.js & 3 lokasi baris-ganda belum
  dihitung). Daftar dibuat dengan
  `grep -rnE "\]\.includes\((currentUser|user)\?\.role\)|(currentUser|user)\?\.role [!=]== \"" frontend/src`.
- **Metode:** untuk tiap gerbang, endpoint yang dipanggil aksi itu dipetakan ke penjaganya di backend
  (`require_permission` / `require_any_permission` / `require_role` / pemeriksaan peran di service).
  Aturan keputusan:
  1. **IZIN** — server menegakkan izin → tombol memakai `can(user.permissions, modul, aksi)` yang
     **sama dengan endpoint**, satu izin per aksi (gerbang gabungan dipecah).
  2. **PERINGKAT** — server memakai `role_satisfies(peran, required_approval_role)` → FE memakai
     `roleSatisfies` (fungsi yang sudah ada, sama persis dengan BE).
  3. **PERAN-BE** — server sengaja memeriksa peran (literal atau `require_role`) → tetap berbasis peran,
     dicatat alasannya. Bila server memakai `role_in`/`require_role`, FE memakai `roleIs` (peran acuan dikenali).
  4. **ACUAN** — gerbang tata letak murni (tanpa penjaga server) → `roleIs` agar peran kustom turunan
     ikut.
  5. **TEKS** — hanya mengubah teks/placeholder yang mencerminkan aturan server literal → dibiarkan.
  6. **MATI** — variabel/prop yang tidak dipakai → dihapus.
- Aturan bisnis, scope, approval bertingkat, SoD, dan larangan Admin sebagai acuan **tidak diubah**;
  server tetap penegak utama. Tidak ada perubahan backend.

### Tabel keputusan (baris = `f3496b0`)

| # | Lokasi | Sebelum | Penjaga server | Keputusan → sesudah |
|---|---|---|---|---|
| 1 | `App.js:471` tombol Tanya KN | daftar 7 peran | `ai_analytics._ai_user`: peran literal, daftar dari konfig `ai.enabled_roles` | **PERAN-BE**, tetap |
| 2 | `App.js:484` pindai notifikasi | admin/manager | `require_role(["manager"])` (= `role_in` + admin) | **ACUAN** `roleIs(["admin","manager"])` |
| 3 | `components/PeriodUnlockBanner.jsx:21` | admin\|\|manager | GET tanpa izin; aksi `period.unlock` | **IZIN** `period.unlock` |
| 4 | `features/admin/AdminView.jsx:510` rilis produk | admin/manager | spec → `POST /rnd/specs/{id}/release-product` (`rnd.decide`); tanpa spec → `PATCH /products` (`product.update`) | **IZIN** per baris: `rnd.decide` / `product.update` |
| 5 | `admin/po/POCompactPanel.jsx:29` | admin/manager | ACC: `role_satisfies(required_approval_role)` + matriks; amend/close/cancel: `purchase_order.update` | **PERINGKAT** (ACC) + **IZIN** `purchase_order.update` |
| 6 | `admin/po/PODetailPanel.jsx:86` | admin/manager | sama dengan #5 | sama dengan #5 |
| 7 | `admin/PurchaseOrderManagement.jsx:133` | `role !== "finance"` | `POST /purchase-orders`: `purchase_order.create` | **IZIN** `purchase_order.create` |
| 8 | `admin/uom/UomConversionView.jsx:34` | admin \|\| `uom.update` | `uom.update` | **IZIN** `uom.update` (admin tanpa jalan pintas) |
| 9 | `catalog/CatalogWorkspace.jsx:38` hapus master | admin/md | `master_usage_service.LIFECYCLE_ROLES` literal | **PERAN-BE**, tetap |
| 10 | `documents/trace/DocTraceView.jsx:50` | admin | pintasan Pusat Pengaturan (`settings.view`); backfill `pdf_template.manage` | **IZIN** dipecah: `settings.view` · `pdf_template.manage` |
| 11 | `finance/amendments/AmendmentCenterView.jsx:56` tautan alasan | admin/manager | `GET /amendment-reasons`: `finance_amendment.propose` | **IZIN** `finance_amendment.propose` |
| 12 | `finance/amendments/AmendmentDetailPanel.jsx:102` (+`:105`, `:211`) | fallback `APPROVER_ROLES` | izin = `approval_permission` dokumen atau `finance_amendment.approve`; tanpa `approval_permission` service menuntut peran persis | **IZIN** (`approval_permission` \|\| `finance_amendment.approve`) + **PERAN-BE** peran persis tetap; `APPROVER_ROLES` dihapus |
| 13 | `finance/amendments/AmendmentReasonsPanel.jsx:28` | admin | `PUT /amendment-reasons`: `finance_amendment.admin` | **IZIN** `finance_amendment.admin` |
| 14 | `finance/BudgetView.jsx:37` aturan anggaran | admin | `PUT /finance/budget-rules`: `budget.configure` | **IZIN** `budget.configure` |
| 15 | `finance/ClosingView.jsx:37` buka kembali | admin | `accounting.manage` **dan** peran admin (closing.py) | **IZIN** `accounting.manage` + **PERAN-BE** admin tetap |
| 16 | `finance/ClosingView.jsx:135` tutup ulang | admin\|\|manager | `accounting.manage` | **IZIN** `accounting.manage` |
| 17 | `finance/GLAccountMappingView.jsx:23` | admin/finance | `gl_mapping.update` | **IZIN** `gl_mapping.update` |
| 18 | `finance/interco/IntercoView.jsx:288` jadwal bayar | admin | `PUT /settings`: `entity.update` (+ global hanya peran lintas PT) | **IZIN** `entity.update` |
| 19 | `finance/payments/PaymentPlansView.jsx:57` | admin/manager | pintasan Pusat Pengaturan | **IZIN** `settings.view` |
| 20 | `finance/payments/PenaltyPanel.jsx:27` | admin/manager | `penalty.issue` / `.adjust` / `.waive` / `.pay` | **IZIN** dipecah 4 aksi |
| 21 | `finance/payments/SoPaymentPanel.jsx:24` | admin/manager/sales | `payment_plan.create` / `.update` | **IZIN** `create` (belum ada rencana) / `update` |
| 22 | `finance/payments/SoPaymentPanel.jsx:66` hitung denda | admin/manager | `POST /payment-plans/{id}/accrue`: `penalty.issue` | **IZIN** `penalty.issue` |
| 23 | `finance/PeriodUnlockView.jsx:49` | admin\|\|manager | `period.unlock` (semua aksi) | **IZIN** `period.unlock`; teks peringatan menyebut izin |
| 24 | `finance/TaxCenterView.jsx:46` | admin/manager | `/tax/pph-records`: `accounting.manage` | **IZIN** `accounting.manage` |
| 25 | `hr/AttendanceSetupView.jsx:42` | admin/manager | shift/geofence/device: `hr.manage_attendance` | **IZIN** `hr.manage_attendance` |
| 26 | `hr/AttendanceView.jsx:56` | admin/manager | `hr.manage_attendance` | **IZIN** `hr.manage_attendance` |
| 27 | `hr/Employee360Panel.jsx:30` | admin/manager | ubah karyawan: `hr.update` | **IZIN** `hr.update` |
| 28 | `hr/EmployeesView.jsx:53` | admin/manager | `hr.create` / `.update` / `.delete` | **IZIN** dipecah 3 aksi |
| 29 | `hr/KpiView.jsx:11` | admin/manager | `/hr/kpi`: `hr.manage_attendance` | **IZIN** `hr.manage_attendance` |
| 30 | `hr/LeaveView.jsx:98` | admin/manager | `/hr/leave-requests*`: `hr.manage_attendance` | **IZIN** `hr.manage_attendance` |
| 31 | `hr/OrgUnitsView.jsx:32` | admin/manager | `/hr/org-units`: `hr.manage_org` | **IZIN** `hr.manage_org` |
| 32 | `hr/OvertimeView.jsx:79` | admin/manager | `/hr/overtime*`: `hr.manage_attendance` | **IZIN** `hr.manage_attendance` |
| 33 | `hr/VisitsView.jsx:178` tampilan Sales | `role === "sales"` | dasbor penyelia `GET /hr/visits`: `hr.view`; "Kunjungan Saya" `/hr/visits/me` (akun sendiri) | **ACUAN** `roleIs(["sales"])` **atau** tanpa `hr.view` → Kunjungan Saya |
| 34 | `inspections/QcHubView.jsx:14` | `md_quality` → dokumen saja | antrean `GET /inbound/qc/queue`: `wms.view` | **IZIN** tanpa `wms.view` → tab dokumen saja |
| 35 | `inventory/lots/LotsView.jsx:32` | admin/manager/warehouse | semua tulis `/lots*`: `inventory.update` | **IZIN** `inventory.update` |
| 36 | `inventory/lots/LotsView.jsx:33` `canConfig` | admin/manager | — (tidak dipakai) | **MATI**, dihapus |
| 37 | `inventory/StockBucketsView.jsx:41` | admin/manager/warehouse | `/stock/hold*`, `/stock/wip*`: `inventory.update` | **IZIN** `inventory.update` |
| 38 | `marketing/Campaigns.jsx:20` | 5 peran | buat `marketing.create`; ubah & ajukan tagihan `marketing.update` | **IZIN** dipecah |
| 39 | `marketing/Campaigns.jsx:21` biaya & ACC tagihan | admin/manager/finance | catat biaya `accounting.create`; anulir `accounting.void`; ACC tagihan `BILL_APPROVER_ROLES` literal + (`accounting.view` \| `vendor_bill.approve`) | **IZIN** (catat/anulir dipisah, prop `canVoid` baru di `CampaignCostsModal`) + **PERAN-BE** penyetuju tagihan |
| 40 | `marketing/ContentCalendar.jsx:55` | 5 peran | `marketing.create` | **IZIN** `marketing.create` |
| 41 | `marketing/SocialAccounts.jsx:19` | 5 peran | `marketing.create` / `.update` | **IZIN** dipecah |
| 42 | `marketing/TemplatePicker.jsx:13` hapus templat | admin/manager \|\| pembuat | `marketing.update` + (`APPROVE_ROLES` literal \|\| pembuat) | **IZIN** `marketing.update` + **PERAN-BE** tetap |
| 43 | `pettycash/CashAdvancesView.jsx:36` | admin/manager/sales | `cash_advance.create` | **IZIN** `cash_advance.create` |
| 44 | `pettycash/ExpenseCategoriesView.jsx:22` | admin/manager | `cash_settlement.manage` | **IZIN** `cash_settlement.manage` |
| 45 | `pettycash/SettlementsView.jsx:33` | admin/manager/sales | `cash_settlement.create` | **IZIN** `cash_settlement.create` |
| 46 | `pos/CheckoutDrawer.jsx:58` `canApprovePrice` | admin/manager | — (`RequestSpecialPriceModal` tidak menerima prop ini) | **MATI**, variabel & prop dihapus |
| 47 | `pos/CreateCustomerModal.jsx:52` | teks pemilik sales | `customers.py`: `role == "sales"` literal | **TEKS**, tetap |
| 48 | `purchasing/BlanketPODetailPanel.jsx:22` | admin/manager | call-off `purchase_order.create`; tutup kontrak `purchase_order.update` | **IZIN** dipecah |
| 49 | `purchasing/BlanketPOView.jsx:42` | admin/manager | `POST /purchase-orders/blanket`: `purchase_order.create` | **IZIN** |
| 50 | `purchasing/CashManagementView.jsx:42` | admin/manager | `cash.create` / `cash.delete` | **IZIN** dipecah |
| 51 | `purchasing/contracts/ContractsView.jsx:49` | admin/manager | `supplier_contract.create/update/delete`; pintasan kebijakan (Pusat Pengaturan) | **IZIN** dipecah + `settings.view` |
| 52 | `purchasing/LandedCostView.jsx:45` ACC | admin/manager | `role_satisfies(required_approval_role \|\| "manager")` | **PERINGKAT** per voucher |
| 53 | `purchasing/LandedCostView.jsx:46` buat | admin/manager | `landed_cost.create` | **IZIN** |
| 54 | `purchasing/MakloonOrderDetailPanel.jsx:65` | admin/manager/warehouse | kirim `makloon_order.issue`; terima & catat jasa `makloon_order.receive` | **IZIN** dipecah |
| 55 | `purchasing/MakloonOrderDetailPanel.jsx:66` batal | admin/manager | `makloon_order.cancel` | **IZIN** |
| 56 | `purchasing/MakloonOrdersView.jsx:37` | admin/manager | `makloon_order.create` | **IZIN** |
| 57 | `purchasing/MakloonsView.jsx:25` | admin/manager | `makloon.create/update/delete` | **IZIN** dipecah |
| 58 | `purchasing/ProcessRecipesView.jsx:25` | admin/manager | `process_recipe.create/update/delete` | **IZIN** dipecah |
| 59 | `purchasing/PurchaseApprovalView.jsx:352` `isCreator` | `role !== "admin"` | SoD: `approval_matrix_service.is_admin` → admin boleh menyetujui sendiri | **PERAN-BE**, tetap |
| 60 | `purchasing/PurchaseReturns.jsx:98` | admin/manager | ACC `purchase_return.approve`; tolak `purchase_return.reject` | **IZIN** dipecah (daftar) |
| 61 | `purchasing/PurchaseReturns.jsx:99` hapus draf | admin/manager | `DELETE /purchase-returns/{id}`: `purchase_return.update` | **IZIN** |
| 62 | `purchasing/RFQDetailPanel.jsx:27` | admin/manager | kirim/batal `rfq.update`; award `rfq.award` | **IZIN** dipecah |
| 63 | `purchasing/RFQDetailPanel.jsx:28` isi penawaran | admin/manager/warehouse | `rfq.update` | **IZIN** |
| 64 | `purchasing/RFQView.jsx:43` | admin/manager/warehouse | `rfq.create` | **IZIN** |
| 65 | `purchasing/supplier-items/SupplierItemsView.jsx:36` | admin/manager | `supplier_item.import/create/update/delete` | **IZIN** dipecah 4 aksi |
| 66 | `purchasing/Supplier360Panel.jsx:38` | admin/manager | ubah supplier & daftar harga: `supplier.update` | **IZIN** |
| 67 | `purchasing/SupplierDetailPanel.jsx:29` | admin/manager | daftar harga: `supplier.update` | **IZIN** |
| 68 | `purchasing/SuppliersView.jsx:73` | admin/manager | `supplier.create/update/delete` | **IZIN** dipecah |
| 69 | `purchasing/VendorBillsView.jsx:66` ACC | admin/manager | `role_satisfies(required_approval_role \|\| "manager")`; anulir pembayaran (detail) `vendor_bill.pay` | **PERINGKAT** per tagihan; `VendorBillDetailPanel` anulir = **IZIN** `vendor_bill.pay` |
| 70 | `purchasing/VendorBillsView.jsx:67` buat | admin/manager | `vendor_bill.create` | **IZIN** |
| 71 | `rfid/RfidDevicesView.jsx:43` | admin | `require_role(["admin"])` | **PERAN-BE**, tetap |
| 72 | `rnd/design/FeedbackThread.jsx:48` | placeholder desainer | — | **TEKS**, tetap |
| 73 | `sales/CustomerPricelistView.jsx:35` | admin/manager | `/customer-prices*`: `pricelist.manage` | **IZIN** |
| 74 | `sales/mobile/MobileCustomerForm.jsx:48` | teks pemilik sales | `customers.py` literal | **TEKS**, tetap |
| 75 | `sales/mobile/MobileSalesApp.jsx:37` meja Admin Sales | `sales_admin` | — (tata letak) | **ACUAN** `roleIs(["sales_admin"])` |
| 76 | `sales/PricelistView.jsx:73` | admin/manager | `pricelist.manage` | **IZIN** |
| 77 | `sales/ReturnPoliciesView.jsx:53` | admin/manager | `/sales-return-policies`: `settings.manage` | **IZIN** |
| 78 | `sales/ReturnPoliciesView.jsx:151` asumsi retur | admin/manager | `PUT /settings` (global): `entity.update` + lintas PT | **IZIN** `entity.update` |
| 79 | `sales/SalesPortal.jsx:245` pilih roll | `role === "sales"` + konfig | `sales_orders.py` literal + `allocation.roll_pick_sales` | **PERAN-BE**, tetap |
| 80 | `sales/SpecialOrderShippingPanel.jsx:16` | admin/manager/sales_admin/warehouse_admin | `prepare-shipment`: `order.update` | **IZIN** `order.update` |
| 81 | `settings/ApprovalRulesSettings.jsx:38` | admin | tulis `/approval-rules`: `settings.manage` | **IZIN**; teks menyebut izin |
| 82 | `settings/config/SettingsHub.jsx:66` | admin | tab Kunci Saga & aksi Data Hygiene: `require_role(["admin"])`; pemberitahuan hak terbatas | **PERAN-BE** (saga/hygiene) + pemberitahuan = `caps.settings_manage` server |
| 83 | `settings/masters/EntityMastersView.jsx:79` | admin/manager | `/entity-masters*`: `settings.manage` | **IZIN** |

Ringkas: **75 lokasi diubah**, **8 tetap**. Yang diubah: IZIN di 70 lokasi (5 di antaranya tetap
menyertakan pemeriksaan peran server: #12, #15, #39, #42, #82) · PERINGKAT 4 (#5, #6, #52, #69) ·
ACUAN 3 (#2, #33, #75) · MATI 2 (#36, #46); satu baris bisa memakai lebih dari satu kategori.
Yang tetap: PERAN-BE 5 (#1, #9, #59, #71, #79) · TEKS 3 (#47, #72, #74).

### Perubahan perilaku untuk peran bawaan (matriks DB data acuan)
Semua perubahan di bawah membuat UI **sama dengan keputusan server**; tidak ada izin yang ditambah/dicabut.

| Layar / aksi | Kini tampil juga untuk | Kini tidak tampil untuk (server memang menolak) |
|---|---|---|
| Buat PO (Manajemen PO) | — | sales, sales_admin, warehouse, md, dll. (sebelumnya semua kecuali Finance) |
| ACC PO / landed cost / tagihan supplier | peran berperingkat ≥ yang dituntut dokumen (mis. aturan "finance") | — (untuk tuntutan "manager" tetap admin/manager) |
| Rilis produk (Master Produk) | md | manager untuk produk **tanpa** spesifikasi R&D (`product.update` hanya admin/md) |
| Pintasan Aturan Relasi & Cetak, isi ulang relasi (Jejak Dokumen) | manager | — |
| Tautan Alasan Amandemen (baca-saja) | sales, sales_admin, finance | — |
| Terbitkan denda · Hitung denda (SO) | finance | — |
| Rencana bayar SO (susun/ubah) | sales_admin; finance (ubah) | sales |
| Antrean QC kedatangan (tab) | — | **qc** (tanpa `wms.view`; GET antrean 403) |
| Kunjungan: dasbor penyelia | — | akun tanpa `hr.view` kini melihat "Kunjungan Saya" alih-alih dasbor 403 |
| Lot · Stok hold/WIP · Kirim/terima makloon | warehouse_admin | — |
| Catat biaya kampanye | — | finance (`accounting.create` tidak dimiliki) |
| Kasbon & LPJ — buat | sales_admin, finance | — |
| Kas — catat transaksi | finance | — |
| RFQ — buat/kirim/batal/isi penawaran | md | — |
| Daftar harga & harga pelanggan | md | — |
| Kebijakan retur · asumsi retur · master entitas | — | manager (`settings.manage`/`entity.update` hanya admin) |
| OD — Siapkan pengiriman | sales, sample_admin | warehouse_admin |

Peran kustom kini mendapat tombol sesuai izin efektifnya (sebelumnya tidak pernah, karena nama
perannya tidak ada di daftar); peran kustom turunan Manager/Sales/Admin Sales dikenali di #2, #33, #75.

## Pengujian
- **Jest render baru** `frontend/src/features/__tests__/roleGateSweep.test.js` — **15/15** (react-dom/server):
  PO (Manager hanya-lihat: Setujui ada/Batalkan tidak; Admin Sales berizin update: kebalikannya),
  Denda (issue-saja, adjust-saja), OD siapkan pengiriman (warehouse_admin tanpa izin / sales berizin),
  QC hub (qc tanpa `wms.view` / warehouse), Kunjungan (manager ± `hr.view`, sales), Barang supplier
  (impor-saja), Kontrak (pintasan vs buat), Kasbon (finance berizin / sales tanpa izin).
  **Bukti-merah:** tes yang sama pada kode `f3496b0` → **13 gagal, 2 lulus** (2 yang lulus adalah kasus
  positif yang perilakunya memang tidak berubah).
- **Semua jest frontend:** 4 suite, **30/30**.
- **Uji asap render** (sementara, tidak di-commit): 66 komponen yang diubah × 2 akun (izin penuh
  dan tanpa izin) = 132 render, dibandingkan sebelum/sesudah: **identik** — 128 OK, 4 gagal sama di
  kedua versi (AdminView butuh prop `data`; MobileSalesApp mengimpor paket ESM yang tidak
  ditransformasi jest). Menangkap galat runtime seperti variabel belum dideklarasi (mis. `plan` di
  SoPaymentPanel — `canEdit` dipindah ke sesudah deklarasi).
- **ESLint** pada 67 berkas yang diubah, konfigurasi repo **ditambah** `no-undef`, `no-unused-vars`,
  `react/jsx-no-undef`, `react-hooks/*` (konfigurasi repo mematikan `no-undef`): sebelum vs sesudah
  **tanpa temuan baru**; satu hilang (`canConfig` tak terpakai). Dengan konfigurasi repo: 55 = 55
  (semua "unused eslint-disable directive" lama). Dev server: `webpack compiled` (peringatan lama).
- Tidak ada perubahan backend → pytest tidak dijalankan ulang untuk fase ini.

## Hambatan lingkungan
- Panel browser bawaan sedang login sebagai akun lain dan berukuran ponsel, jadi verifikasi UI memakai
  render otomatis (jest/SSR), bukan klik di browser.

## Keterbatasan / belum diuji
- Render SSR hanya memeriksa render awal (efek & data jaringan tidak jalan); tombol di baris data
  (mis. ACC voucher per baris, hapus kontrak) dibuktikan lewat kode + pemetaan endpoint, bukan render.
- Pintasan Pusat Pengaturan (#10, #19, #51) memakai `settings.view` = siapa yang boleh membuka Pusat
  Pengaturan; hak ubah per setelan tetap ditentukan server (`can_edit` di registri).
- Pemeriksaan **peran literal di backend** (bukan `role_in`) membuat peran kustom turunan tidak dianggap
  peran acuannya: pemilik pelanggan & pilih roll (`sales`), Tanya KN (`ai.enabled_roles`), hapus master
  (`admin/md`), buka kembali periode (`admin`), putusan amandemen tanpa `approval_permission`, hapus
  templat marketing, penyetuju tagihan kampanye. FE mengikuti server apa adanya; menyelaraskan backend
  ke `role_in` adalah keputusan terpisah (tidak dikerjakan).
- Satu gerbang di luar pola grep tidak dijamin tertangkap (mis. peran dibandingkan lewat variabel lain).

## Yang perlu direview
- **QC bawaan kehilangan tab "Antrean QC Kedatangan"** karena matriks tidak memberi `qc` izin `wms.view`
  (GET antrean memang 403). Bila QC seharusnya memproses antrean, perbaikannya di matriks izin, bukan UI.
- Manager tidak lagi melihat tombol ubah **Kebijakan Retur, Asumsi Retur, Master Entitas** (server
  menolak karena `settings.manage`/`entity.update` hanya admin). Konfirmasi apakah matriks yang benar.
- Admin Gudang tidak lagi melihat **Siapkan pengiriman OD** (tanpa `order.update`); Finance tidak lagi
  melihat **catat biaya kampanye** (tanpa `accounting.create`); Sales tidak lagi melihat **ubah rencana
  bayar SO** (tanpa `payment_plan.*`). Semuanya sebelumnya berakhir 403.
- Kategori PERAN-BE (#1, #9, #15, #39, #42, #59, #71, #79, #82): setuju dibiarkan berbasis peran?
- **Status:** ROLE-01 → implemented_pending_review

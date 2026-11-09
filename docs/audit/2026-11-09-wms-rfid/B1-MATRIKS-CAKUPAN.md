# B1 — Matriks cakupan: menu/tab × peran × desktop/HP

Lampiran [`B1-UI-MENU-PERAN.md`](B1-UI-MENU-PERAN.md) dan [`B1b-SAPUAN-LANJUTAN.md`](B1b-SAPUAN-LANJUTAN.md). Basis kode
B1 `main@5f1e36e`, B1b `main@cb9f924`. Verifikasi peramban B1 9 Nov 2026 06:19–06:37 WIB; **B1b 07:54–08:52 WIB** (stack
`kn-uji`, DB `kn_test_trial`; stack mati ±06:49–07:54, tidak di-restart oleh audit).

**Cara dibuat.** Visibilitas dihitung dari kode oleh `scripts/audit/b1_matrix_report.py` (tiruan `roleCanSee` +
`hubTabsForRole` atas `navStructure.js`, `hubTabs.js`, `ROLE_NAV` di `roles.js`); aplikasi HP per peran dari
`features/mobile/MobileAppSwitch.jsx:46-56`. Izin server per akun (`view_resources`/`hidden_views`) tidak ditiru — sel
"tampil menurut kode" masih bisa disembunyikan server (contoh: sales › Lot & Silsilah → `–(V)`). Tabel di bawah
dibangkitkan ulang oleh `scripts/audit/b1b_build_matrix.py` dari anotasi gabungan B1 + B1b
`scripts/audit/b1b_matrix_notes.json`; angka per sel ada di B1b §0.2–0.3.

**Legenda sel.**
- `K` = tampil menurut kode, **belum** dikunjungi di peramban (tidak ada lagi sesudah B1b).
- `V` = dikunjungi di peramban, tanpa temuan baru · `T:UI-nn` = dikunjungi, ada temuan (nomor B1 atau B1b) · `–(V)` =
  dipastikan di peramban memang tidak tampil (dialihkan/tersembunyi) · `–` = tidak tampil menurut kode.
- HP (390 × 844): `T:`/`V` = layar dibuka di 390 untuk peran itu lewat aplikasi HP-nya (tab, Pintasan, Layar lengkap,
  tampilan penuh) dan diukur · `T·d:`/`V·d` = dibuka di 390 lewat **"Tampilan desktop"** (peran tanpa pintu di aplikasinya)
  dan diukur · `d(V)` = aplikasi HP peran itu sudah dikunjungi dan **dipastikan tidak punya pintu** ke layar ini (hanya
  "Tampilan desktop"); tata letak 390 layar ini diukur pada peran lain · `p(V)` = pintu di aplikasi HP **ada** (dipastikan),
  tata letak 390 diukur pada peran lain. Kode B1 lama `K·p`/`K·d` sudah tidak dipakai; legenda `K·p` B1 terlalu luas
  (Pintasan `MobileOpsApp` hanya 4 layar) — lihat B1b §4.

**Peran (singkatan):** adm = admin · mgr = manager · wha = warehouse_admin (Admin Gudang) · wh = warehouse (3 akun site:
Jakarta, Soreang, Rancamalang) · sls = sales · sla = sales_admin · fin = finance · md · mdq = md_quality · qc · sma =
sample_admin · drv = driver.

**Ringkas (menurut kode, 37 baris × 12 peran = 444 sel desktop):** 166 sel tampil — adm 35 · mgr 31 · wha 32 · wh 28 ·
sls 7 · sla 13 · fin 5 · md 6 · mdq 2 · qc 3 · sma 2 · drv 2.

| Sel tampil (166 per mode) | B1 | B1b |
|---|---:|---:|
| Desktop dikunjungi | 15 | **166** (115 `T`, 50 `V`, 1 `–(V)`) |
| HP diukur langsung di 390 untuk peran itu | 3 | **51** (14 `T`, 37 `T·d`) |
| HP jalur dipastikan, tata letak diukur pada peran lain | 0 | **114** (98 `d(V)`, 16 `p(V)`) + 1 `–(V)` |

Laporan B1 menulis "16 desktop + 2 HP"; dua sel `–(V)` B1 (manajer › Lokasi RFID, Admin Gudang › Perangkat) ada di luar sel
tampil, dan sel HP B1 ada 3 (sales Stok & ATP, QC SPK, sopir Pengiriman). Akun yang dipakai B1b: admin, manager, wh.admin,
whadmin, warehouse (Jakarta, Soreang, Rancamalang), sales, salesadmin, finance, md, mdquality, qc, sampleadmin, driver —
PT aktif tiap akun dipasang ke PT bawaan (catatan UI-39). Kolom `wh` = gabungan tiga akun gudang (semua layar di akun
Jakarta; layar sensitif cakupan juga di Soreang & Rancamalang). Sidebar yang terlihat sama dengan hasil kode, kecuali
sales tanpa tab Lot & Silsilah; isi sidebar petugas gudang (Pengadaan, Hutang Pemasok, Antar Entitas, Kas & Aset) = UI-34.

### Desktop (1024 px)

| Grup › Menu › Tab (view) | adm | mgr | wha | wh | sls | sla | fin | md | mdq | qc | sma | drv |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gudang & Logistik › Operasi Gudang › Stok, Transfer & Opname (`operations`) | T:UI-04,05,29 | T:UI-04,05 | T:UI-04,05 | T:UI-04,05 | – | T:UI-04,05 | – | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Barang Masuk (`goods-receipts`) | T:UI-38 | V | T:UI-38 | T:UI-38 | – | – | V | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Barang Keluar (`wms-outbound`) | T:UI-41 | T:UI-41 | T:UI-41 | T:UI-41 | – | V | – | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Cutting (`wms-cutting`) | T:UI-10 | V | V | V | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Perbaikan (`repair-orders`) | V | V | V | V | – | – | – | V | – | – | – | – |
| Gudang & Logistik › Stok & ATP › Status Stok & ATP (`inventory-board`) | T:UI-40 | V | T:UI-45 | T:UI-45 | T:UI-45 | T:UI-45 | – | – | – | – | – | – |
| Gudang & Logistik › Stok & ATP › Stok Multi-Bucket (`stock-buckets`) | T:UI-06,40 | T:UI-40 | T:UI-45 | T:UI-45 | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Stok & ATP › Lot & Silsilah (`inventory-lots`) | T:UI-50,52,59 | T:UI-50,59 | T:UI-50 | T:UI-50 | –(V) | T:UI-50 | – | – | – | – | – | – |
| Gudang & Logistik › BOM Produksi In-House (`production`) | V | V | V | V | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Lokasi Rak (`wms-locations`) | T:UI-42 | T:UI-42,46,59 | T:UI-46 | T:UI-46,59 | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Data Gudang (`md-warehouses`) | T:UI-05,50,52 | T:UI-05,50 | T:UI-05,50 | T:UI-05,50 | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Pengiriman (`logistics`) | V | T:UI-47 | V | V | V | V | – | – | – | – | V | V |
| Gudang & Logistik › RFID › Lokasi RFID (`cs-rfid-lokasi`) | V | –(V) | T:UI-55 | T:UI-55 | – | – | – | – | – | – | – | – |
| Gudang & Logistik › RFID › Tag RFID (`cs-rfid-tags`) | T:UI-55 | – | T:UI-14 | T:UI-14,55 | – | – | – | – | – | – | – | – |
| Gudang & Logistik › RFID › Monitor Gerbang (`cs-rfid-gate`) | T:UI-22 | T:UI-20 | T:UI-22,50 | T:UI-50,55 | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Eskalasi Gudang (`escalations`) | V | V | V | V | – | – | – | – | – | – | – | – |
| (lepas) › Kualitas › Antrean QC Kedatangan (`qc-inspection`) | T:UI-17 | V | V | V | – | – | – | – | – | T:UI-17,18 | – | – |
| (lepas) › Kualitas › SPK Inspeksi (`inspections`) | T:UI-52 | T:UI-52 | T:UI-52 | T:UI-52 | – | – | – | T:UI-52 | T:UI-52 | T:UI-19 | – | – |
| (lepas) › Retur › Retur Pelanggan (`returns`) | T:UI-05,58 | T:UI-05 | V | V | V | T:UI-05 | T:UI-05 | T:UI-05 | T:UI-05 | V | – | – |
| (lepas) › Retur › Retur Antar-PT (`interco-returns`) | T:UI-50 | T:UI-50 | V | V | – | T:UI-50 | V | – | – | – | – | – |
| (lepas) › Retur › Retur ke Supplier (Nota Debit) (`purchase-returns`) | T:UI-58 | T:UI-58 | T:UI-58 | V | – | – | – | – | – | – | – | – |
| (lepas) › Meja Gudang (`warehouse-admin-desk`) | – | – | T:UI-02,05 | – | – | – | – | – | – | – | – | – |
| (lepas) › Meja Saya (`my-desk`) | T:UI-05 | T:UI-05 | T:UI-48 | T:UI-05 | T:UI-05 | T:UI-48 | – | – | – | – | – | T:UI-56 |
| (lepas) › Meja Sample (`sample-admin-desk`) | – | – | – | – | – | – | – | – | – | – | T:UI-50 | – |
| Pembelian › Pesanan Pembelian › Order Makloon (`makloon-orders`) | T:UI-60 | V | V | V | – | – | – | – | – | – | – | – |
| Pembelian › Pesanan Pembelian › Kinerja Mitra Makloon (`makloon-claim-recap`) | T:UI-05 | T:UI-05 | T:UI-05 | T:UI-34 | – | – | T:UI-49 | T:UI-05 | – | – | – | – |
| Pembelian › Pesanan Pembelian › Klaim Selisih Makloon (`makloon-claims`) | T:UI-58 | T:UI-05 | T:UI-05 | V | – | – | – | – | – | – | – | – |
| Pembelian › Pengadaan › Permintaan Pembelian (`purchase-requisitions`) | T:UI-05,58 | T:UI-05,58 | T:UI-05 | T:UI-05 | – | T:UI-05 | – | T:UI-05 | – | – | – | – |
| Pembelian › Hutang Pemasok › Kontrabon (Tukar Faktur) (`contra-bons`) | V | V | T:UI-34 | T:UI-34 | – | – | – | – | – | – | – | – |
| Akuntansi & Pajak › Antar Entitas (Grup) (`interco-transactions`) | T:UI-50 | T:UI-50 | T:UI-34 | T:UI-34,50 | – | T:UI-50 | T:UI-50 | – | – | – | – | – |
| (lepas) › Analitik › Analitik Stok (`cs-stock-analytics`) | T:UI-05,50 | T:UI-05,50 | T:UI-05,50 | – | – | – | – | – | – | – | – | – |
| Penjualan › POS (`sales`) | T:UI-50 | – | – | – | V | V | – | – | – | – | – | – |
| Penjualan › Produk & Harga › Produk & Varian (`md-products`) | T:UI-50,61 | T:UI-61 | – | – | T:UI-61 | T:UI-61 | – | V | – | – | – | – |
| Pengaturan › Gudang & Mutu › Aturan Gudang & Mutu (`settings-cfg-warehouse`) | T:UI-51,52 | T:UI-51,52 | – | – | – | – | – | – | – | – | – | – |
| Pengaturan › Gudang & Mutu › Penerimaan & OCR (`settings-receiving-ocr`) | T:UI-52 | T:UI-52 | T:UI-52 | – | – | – | – | – | – | – | – | – |
| Pengaturan › Gudang & Mutu › Master Grade Mutu (`grade-master`) | T:UI-59 | T:UI-59 | V | – | – | V | – | –(V) UI-35 | –(V) UI-35 | –(V) UI-35 | – | – |
| Pengaturan › Integrasi & Sistem › Perangkat (`settings-devices`) | T:UI-21 | T:UI-57 | –(V) UI-21 | – | – | – | – | – | – | – | – | – |

### HP (390 × 844)

| Grup › Menu › Tab (view) | adm | mgr | wha | wh | sls | sla | fin | md | mdq | qc | sma | drv |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gudang & Logistik › Operasi Gudang › Stok, Transfer & Opname (`operations`) | d(V) | d(V) | d(V) | T·d:UI-24,36 | – | T:UI-24 | – | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Barang Masuk (`goods-receipts`) | p(V) | T:UI-52 | p(V) | T:UI-24 | – | – | d(V) | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Barang Keluar (`wms-outbound`) | d(V) | d(V) | d(V) | T·d:UI-24,36 | – | d(V) | – | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Cutting (`wms-cutting`) | d(V) | d(V) | d(V) | T·d:UI-24,36 | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Perbaikan (`repair-orders`) | d(V) | d(V) | d(V) | T·d:UI-24,36 | – | – | – | d(V) | – | – | – | – |
| Gudang & Logistik › Stok & ATP › Status Stok & ATP (`inventory-board`) | d(V) | d(V) | d(V) | T·d:UI-45 | T:UI-06,40 | T:UI-06,45 | – | – | – | – | – | – |
| Gudang & Logistik › Stok & ATP › Stok Multi-Bucket (`stock-buckets`) | d(V) | d(V) | d(V) | T·d:UI-24,45 | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Stok & ATP › Lot & Silsilah (`inventory-lots`) | d(V) | d(V) | d(V) | T·d:UI-24,52 | –(V) | T:UI-24 | – | – | – | – | – | – |
| Gudang & Logistik › BOM Produksi In-House (`production`) | d(V) | d(V) | d(V) | T·d:UI-24,36 | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Lokasi Rak (`wms-locations`) | d(V) | d(V) | d(V) | T·d:UI-36,46 | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Data Gudang (`md-warehouses`) | T·d:UI-52 | d(V) | d(V) | T·d:UI-24,36 | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Pengiriman (`logistics`) | d(V) | d(V) | d(V) | T·d:UI-24,36 | p(V) | T:UI-24 | – | – | – | – | d(V) | T:UI-23 |
| Gudang & Logistik › RFID › Lokasi RFID (`cs-rfid-lokasi`) | d(V) | – | d(V) | T·d:UI-24,55 | – | – | – | – | – | – | – | – |
| Gudang & Logistik › RFID › Tag RFID (`cs-rfid-tags`) | d(V) | – | d(V) | T·d:UI-24,36 | – | – | – | – | – | – | – | – |
| Gudang & Logistik › RFID › Monitor Gerbang (`cs-rfid-gate`) | T·d:UI-24 | – | d(V) | T·d:UI-24,55 | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Eskalasi Gudang (`escalations`) | d(V) | d(V) | d(V) | T·d:UI-24,36 | – | – | – | – | – | – | – | – |
| (lepas) › Kualitas › Antrean QC Kedatangan (`qc-inspection`) | d(V) | d(V) | d(V) | T·d:UI-24,36 | – | – | – | – | – | d(V) | – | – |
| (lepas) › Kualitas › SPK Inspeksi (`inspections`) | p(V) | d(V) | d(V) | T·d:UI-24 | – | – | – | p(V) | T:UI-24,37 | T:UI-24,37 | – | – |
| (lepas) › Retur › Retur Pelanggan (`returns`) | d(V) | d(V) | d(V) | T·d:UI-24,36 | p(V) | p(V) | d(V) | d(V) | d(V) | d(V) | – | – |
| (lepas) › Retur › Retur Antar-PT (`interco-returns`) | d(V) | d(V) | d(V) | T·d:UI-24,36 | – | d(V) | d(V) | – | – | – | – | – |
| (lepas) › Retur › Retur ke Supplier (Nota Debit) (`purchase-returns`) | d(V) | d(V) | d(V) | T·d:UI-24,36 | – | – | – | – | – | – | – | – |
| (lepas) › Meja Gudang (`warehouse-admin-desk`) | – | – | d(V) | – | – | – | – | – | – | – | – | – |
| (lepas) › Meja Saya (`my-desk`) | d(V) | d(V) | d(V) | T·d:UI-24,36 | d(V) | d(V) | – | – | – | – | – | d(V) |
| (lepas) › Meja Sample (`sample-admin-desk`) | – | – | – | – | – | – | – | – | – | – | T:UI-52 | – |
| Pembelian › Pesanan Pembelian › Order Makloon (`makloon-orders`) | p(V) | T:UI-24 | d(V) | T·d:UI-24,36 | – | – | – | – | – | – | – | – |
| Pembelian › Pesanan Pembelian › Kinerja Mitra Makloon (`makloon-claim-recap`) | d(V) | d(V) | d(V) | T·d:UI-24,34 | – | – | d(V) | d(V) | – | – | – | – |
| Pembelian › Pesanan Pembelian › Klaim Selisih Makloon (`makloon-claims`) | d(V) | d(V) | d(V) | T·d:UI-24,36 | – | – | – | – | – | – | – | – |
| Pembelian › Pengadaan › Permintaan Pembelian (`purchase-requisitions`) | d(V) | d(V) | d(V) | T·d:UI-24,36 | – | p(V) | – | p(V) | – | – | – | – |
| Pembelian › Hutang Pemasok › Kontrabon (Tukar Faktur) (`contra-bons`) | d(V) | d(V) | d(V) | T·d:UI-24,34 | – | – | – | – | – | – | – | – |
| Akuntansi & Pajak › Antar Entitas (Grup) (`interco-transactions`) | d(V) | d(V) | d(V) | T·d:UI-34 | – | p(V) | d(V) | – | – | – | – | – |
| (lepas) › Analitik › Analitik Stok (`cs-stock-analytics`) | d(V) | T·d:UI-24 | d(V) | – | – | – | – | – | – | – | – | – |
| Penjualan › POS (`sales`) | T·d:UI-24 | – | – | – | p(V) | p(V) | – | – | – | – | – | – |
| Penjualan › Produk & Harga › Produk & Varian (`md-products`) | p(V) | T:UI-24,61 | – | – | p(V) | p(V) | – | T:UI-52 | – | – | – | – |
| Pengaturan › Gudang & Mutu › Aturan Gudang & Mutu (`settings-cfg-warehouse`) | T·d:UI-24 | T·d:UI-24 | – | – | – | – | – | – | – | – | – | – |
| Pengaturan › Gudang & Mutu › Penerimaan & OCR (`settings-receiving-ocr`) | d(V) | T·d:UI-24 | d(V) | – | – | – | – | – | – | – | – | – |
| Pengaturan › Gudang & Mutu › Master Grade Mutu (`grade-master`) | d(V) | T·d:UI-24 | d(V) | – | – | d(V) | – | – | – | – | – | – |
| Pengaturan › Integrasi & Sistem › Perangkat (`settings-devices`) | T·d:UI-24 | T·d:UI-57 | – | – | – | – | – | – | – | – | – | – |


### Aplikasi HP per peran (tab bawah) — kode + kunjungan 390 × 844 (B1 + B1b)

| Aplikasi (berkas) | Peran | Tab | Kunjungan | Pekerjaan gudang yang TIDAK ada (→ "Tampilan desktop") |
|---|---|---|---|---|
| `MobileWarehouseApp` (`features/mobile/MobileWarehouseApp.jsx:284-290`) | warehouse, warehouse_admin, **driver** | Masuk (kartu Kedatangan + tugas PO) · Keluar (tugas SO) · Sample (potong per baris) · Pindai (Pindai · Belum Tag · Daftar Awal) · Lainnya | B1: `warehouse.soreang` semua tab → T:UI-01, 11, 12, 24, 36, 43 · `wh.admin` → T:UI-01, 05, 08, 39 · `driver` → T:UI-23, 39. **B1b:** `warehouse` Jakarta 5 tab + 3 sub-tab (390 & **360 × 780**) → T:UI-53, 54 (Masuk 30 "terbuka" = 13 Menunggu QC + 4 Ditolak QC; teks < 14 px 75–90 %; tata letak 360 lolos) · `whadmin` (PT bawaan Cipta Sandang) Masuk/Keluar/Sample → V | putaway (Lokasi Rak), transfer kirim/terima, stock opname, potong roll SO, makloon kirim/terima, perbaikan, terima retur, cek muat, gate RFID, Meja Gudang, Pengiriman (sopir) — UI-23, UI-36 |
| `MobileOpsApp` (`MobileOpsApp.jsx:180-216`) | admin, manager, finance, qc, md_quality, sample_admin, designer | Persetujuan (bila berizin) · Ringkas · Pintasan (admin/manager/md: Produk & Varian, Kedatangan Barang, Order Makloon, SPK bila izin QC) **atau** QC (qc/md_quality) · Tanya · Lainnya | B1: `admin` → V · `qc` mendarat di SPK desktop → T:UI-37. **B1b:** `manager` 5 tab + 3 Pintasan tampilan penuh → T:UI-52 (Setujui/Tolak 36 px, "Buka layar lengkap" 122 × 18, "Kembali ke aplikasi HP" 169 × 32) · `finance` 4 tab, tanpa Pintasan → d(V) untuk 5 layarnya · `sample_admin` 2 tab + Meja Admin Sample penuh → T:UI-52 · `md_quality` sama dengan QC (mendarat di SPK, tanpa aplikasi) → T:UI-37 | Antrean QC Kedatangan (UI-37), semua layar stok, RFID, Retur, Pengiriman |
| `MobileSalesApp` | sales, sales_admin | Beranda/Meja · Katalog · Keranjang · Pesanan · Lainnya (… Retur Penjualan · Stok & ATP · PIN · **Layar lengkap**) | B1: `sales` Stok & ATP → T:UI-06, 40. **B1b:** `salesadmin` Lainnya + Layar lengkap (Operasi Gudang (pantau), Lot & Silsilah, Pengiriman, Produk & Varian, PR, Transaksi Antar-PT) — 4 dibuka penuh → T:UI-24, 45 · `sales` Layar lengkap (Produk & Varian, Pengiriman, …) → p(V) | – (stok: angka utama = grup, UI-06/UI-45) |
| `MobileMdApp` | md | Meja · Desain · Sample · Produk · Lainnya (PR, Pantau PO, Stok & ATP, SPK Inspeksi, Order Makloon, …) | **B1b:** 5 tab + Stok & ATP → T:UI-06, 52 ("Muat ulang" 15 × 15; angka utama Stok & ATP = grup, satuan 10 px) | Perbaikan, Retur Pelanggan, Kinerja Mitra Makloon |

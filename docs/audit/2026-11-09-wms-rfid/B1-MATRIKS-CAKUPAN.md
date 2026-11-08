# B1 — Matriks cakupan: menu/tab × peran × desktop/HP

Lampiran [`B1-UI-MENU-PERAN.md`](B1-UI-MENU-PERAN.md). Basis kode `main@5f1e36e`. Verifikasi peramban 9 Nov 2026
06:19–06:37 WIB (stack `kn-uji`, DB `kn_test_trial`), sesudah stack pulih dari macet Docker (05:35–06:18).

**Cara dibuat.** Visibilitas dihitung dari kode oleh `scripts/audit/b1_matrix_report.py` (tiruan `roleCanSee` +
`hubTabsForRole` atas `navStructure.js`, `hubTabs.js`, `ROLE_NAV` di `roles.js`); aplikasi HP per peran dari
`features/mobile/MobileAppSwitch.jsx:46-56`. Izin server per akun (`view_resources`/`hidden_views`) tidak ditiru — sel
`K` masih bisa disembunyikan server. Sel kunjungan ditimpakan dari berkas anotasi (`--notes`).

**Legenda sel.**
- `K` = tampil menurut kode, **belum** dikunjungi di peramban.
- `V` = dikunjungi di peramban, tanpa temuan baru · `T:UI-nn` = dikunjungi, ada temuan · `–(V)` = dipastikan di peramban
  memang tidak tampil · `–` = tidak tampil menurut kode.
- HP: `K·p` = peran memakai aplikasi HP umum (`MobileOpsApp`) atau layar ini *responsive workspace* (`App.js:251` —
  `goods-receipts`, `inspections`, `makloon-orders`, `md-products`, …) → dibuka sebagai tampilan penuh 390 px; `K·d` = peran
  punya aplikasi HP khusus yang **tidak** memuat layar ini → hanya lewat "Tampilan desktop".

**Peran (singkatan):** adm = admin · mgr = manager · wha = warehouse_admin (Admin Gudang) · wh = warehouse (3 akun site:
Jakarta, Soreang, Rancamalang) · sls = sales · sla = sales_admin · fin = finance · md · mdq = md_quality · qc · sma =
sample_admin · drv = driver.

**Ringkas (menurut kode, 37 baris × 12 peran = 444 sel desktop):** 166 sel tampil — adm 35 · mgr 31 · wha 32 · wh 28 ·
sls 7 · sla 13 · fin 5 · md 6 · mdq 2 · qc 3 · sma 2 · drv 2. **Dikunjungi di peramban:** 18 sel matriks (16 desktop + 2 HP)
ditambah 4 aplikasi HP per peran (tabel bawah) dan sidebar 4 peran (admin, Admin Gudang, manajer, QC). Sidebar yang
terlihat **sama** dengan hasil kode untuk keempat peran itu (manajer tanpa RFID — UI-20; Admin Gudang tanpa Perangkat — UI-21).

### Desktop (1440 px)

| Grup › Menu › Tab (view) | adm | mgr | wha | wh | sls | sla | fin | md | mdq | qc | sma | drv |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gudang & Logistik › Operasi Gudang › Stok, Transfer & Opname (`operations`) | T:UI-04,05,29 | K | K | K | – | K | – | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Barang Masuk (`goods-receipts`) | T:UI-38 | K | K | K | – | – | K | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Barang Keluar (`wms-outbound`) | T:UI-41 | K | K | K | – | K | – | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Cutting (`wms-cutting`) | T:UI-10 | K | K | K | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Perbaikan (`repair-orders`) | K | K | K | K | – | – | – | K | – | – | – | – |
| Gudang & Logistik › Stok & ATP › Status Stok & ATP (`inventory-board`) | T:UI-40 | K | K | K | K | K | – | – | – | – | – | – |
| Gudang & Logistik › Stok & ATP › Stok Multi-Bucket (`stock-buckets`) | T:UI-06,40 | K | K | K | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Stok & ATP › Lot & Silsilah (`inventory-lots`) | K | K | K | K | K | K | – | – | – | – | – | – |
| Gudang & Logistik › BOM Produksi In-House (`production`) | K | K | K | K | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Lokasi Rak (`wms-locations`) | T:UI-42 | K | K | K | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Data Gudang (`md-warehouses`) | K | K | K | K | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Pengiriman (`logistics`) | K | K | K | K | K | K | – | – | – | – | K | K |
| Gudang & Logistik › RFID › Lokasi RFID (`cs-rfid-lokasi`) | K | –(V) | K | K | – | – | – | – | – | – | – | – |
| Gudang & Logistik › RFID › Tag RFID (`cs-rfid-tags`) | V | – | K | K | – | – | – | – | – | – | – | – |
| Gudang & Logistik › RFID › Monitor Gerbang (`cs-rfid-gate`) | T:UI-22 | T:UI-20 | K | K | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Eskalasi Gudang (`escalations`) | V | K | K | K | – | – | – | – | – | – | – | – |
| (lepas) › Kualitas › Antrean QC Kedatangan (`qc-inspection`) | T:UI-17 | K | K | K | – | – | – | – | – | T:UI-17,18 | – | – |
| (lepas) › Kualitas › SPK Inspeksi (`inspections`) | K | K | K | K | – | – | – | K | K | T:UI-19 | – | – |
| (lepas) › Retur › Retur Pelanggan (`returns`) | K | K | K | K | K | K | K | K | K | K | – | – |
| (lepas) › Retur › Retur Antar-PT (`interco-returns`) | K | K | K | K | – | K | K | – | – | – | – | – |
| (lepas) › Retur › Retur ke Supplier (Nota Debit) (`purchase-returns`) | K | K | K | K | – | – | – | – | – | – | – | – |
| (lepas) › Meja Gudang (`warehouse-admin-desk`) | – | – | T:UI-02,05 | – | – | – | – | – | – | – | – | – |
| (lepas) › Meja Saya (`my-desk`) | K | K | K | K | K | K | – | – | – | – | – | K |
| (lepas) › Meja Sample (`sample-admin-desk`) | – | – | – | – | – | – | – | – | – | – | K | – |
| Pembelian › Pesanan Pembelian › Order Makloon (`makloon-orders`) | K | K | K | K | – | – | – | – | – | – | – | – |
| Pembelian › Pesanan Pembelian › Kinerja Mitra Makloon (`makloon-claim-recap`) | K | K | K | K | – | – | K | K | – | – | – | – |
| Pembelian › Pesanan Pembelian › Klaim Selisih Makloon (`makloon-claims`) | K | K | K | K | – | – | – | – | – | – | – | – |
| Pembelian › Pengadaan › Permintaan Pembelian (`purchase-requisitions`) | K | K | K | K | – | K | – | K | – | – | – | – |
| Pembelian › Hutang Pemasok › Kontrabon (Tukar Faktur) (`contra-bons`) | K | K | K | K | – | – | – | – | – | – | – | – |
| Akuntansi & Pajak › Antar Entitas (Grup) (`interco-transactions`) | K | K | K | K | – | K | K | – | – | – | – | – |
| (lepas) › Analitik › Analitik Stok (`cs-stock-analytics`) | K | K | K | – | – | – | – | – | – | – | – | – |
| Penjualan › POS (`sales`) | K | – | – | – | K | K | – | – | – | – | – | – |
| Penjualan › Produk & Harga › Produk & Varian (`md-products`) | K | K | – | – | K | K | – | K | – | – | – | – |
| Pengaturan › Gudang & Mutu › Aturan Gudang & Mutu (`settings-cfg-warehouse`) | K | K | – | – | – | – | – | – | – | – | – | – |
| Pengaturan › Gudang & Mutu › Penerimaan & OCR (`settings-receiving-ocr`) | K | K | K | – | – | – | – | – | – | – | – | – |
| Pengaturan › Gudang & Mutu › Master Grade Mutu (`grade-master`) | K | K | K | – | – | K | – | – | – | – | – | – |
| Pengaturan › Integrasi & Sistem › Perangkat (`settings-devices`) | T:UI-21 | K | –(V) UI-21 | – | – | – | – | – | – | – | – | – |

### HP (390 × 844)

| Grup › Menu › Tab (view) | adm | mgr | wha | wh | sls | sla | fin | md | mdq | qc | sma | drv |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gudang & Logistik › Operasi Gudang › Stok, Transfer & Opname (`operations`) | K·p | K·p | K·d | K·d | – | K·d | – | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Barang Masuk (`goods-receipts`) | K·p | K·p | K·p | K·p | – | – | K·p | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Barang Keluar (`wms-outbound`) | K·p | K·p | K·d | K·d | – | K·d | – | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Cutting (`wms-cutting`) | K·p | K·p | K·d | K·d | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Operasi Gudang › Perbaikan (`repair-orders`) | K·p | K·p | K·d | K·d | – | – | – | K·d | – | – | – | – |
| Gudang & Logistik › Stok & ATP › Status Stok & ATP (`inventory-board`) | K·p | K·p | K·d | K·d | T:UI-06,40 | K·d | – | – | – | – | – | – |
| Gudang & Logistik › Stok & ATP › Stok Multi-Bucket (`stock-buckets`) | K·p | K·p | K·d | K·d | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Stok & ATP › Lot & Silsilah (`inventory-lots`) | K·p | K·p | K·d | K·d | K·d | K·d | – | – | – | – | – | – |
| Gudang & Logistik › BOM Produksi In-House (`production`) | K·p | K·p | K·d | K·d | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Lokasi Rak (`wms-locations`) | K·p | K·p | K·d | K·d | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Data Gudang (`md-warehouses`) | K·p | K·p | K·d | K·d | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Pengiriman (`logistics`) | K·p | K·p | K·d | K·d | K·d | K·d | – | – | – | – | K·p | T:UI-23 |
| Gudang & Logistik › RFID › Lokasi RFID (`cs-rfid-lokasi`) | K·p | – | K·d | K·d | – | – | – | – | – | – | – | – |
| Gudang & Logistik › RFID › Tag RFID (`cs-rfid-tags`) | K·p | – | K·d | K·d | – | – | – | – | – | – | – | – |
| Gudang & Logistik › RFID › Monitor Gerbang (`cs-rfid-gate`) | K·p | – | K·d | K·d | – | – | – | – | – | – | – | – |
| Gudang & Logistik › Eskalasi Gudang (`escalations`) | K·p | K·p | K·d | K·d | – | – | – | – | – | – | – | – |
| (lepas) › Kualitas › Antrean QC Kedatangan (`qc-inspection`) | K·p | K·p | K·d | K·d | – | – | – | – | – | K·p | – | – |
| (lepas) › Kualitas › SPK Inspeksi (`inspections`) | K·p | K·p | K·p | K·p | – | – | – | K·p | K·p | T:UI-24,37 | – | – |
| (lepas) › Retur › Retur Pelanggan (`returns`) | K·p | K·p | K·d | K·d | K·d | K·d | K·p | K·d | K·p | K·p | – | – |
| (lepas) › Retur › Retur Antar-PT (`interco-returns`) | K·p | K·p | K·d | K·d | – | K·d | K·p | – | – | – | – | – |
| (lepas) › Retur › Retur ke Supplier (Nota Debit) (`purchase-returns`) | K·p | K·p | K·d | K·d | – | – | – | – | – | – | – | – |
| (lepas) › Meja Gudang (`warehouse-admin-desk`) | – | – | K·d | – | – | – | – | – | – | – | – | – |
| (lepas) › Meja Saya (`my-desk`) | K·p | K·p | K·d | K·d | K·d | K·d | – | – | – | – | – | K·d |
| (lepas) › Meja Sample (`sample-admin-desk`) | – | – | – | – | – | – | – | – | – | – | K·p | – |
| Pembelian › Pesanan Pembelian › Order Makloon (`makloon-orders`) | K·p | K·p | K·p | K·p | – | – | – | – | – | – | – | – |
| Pembelian › Pesanan Pembelian › Kinerja Mitra Makloon (`makloon-claim-recap`) | K·p | K·p | K·d | K·d | – | – | K·p | K·d | – | – | – | – |
| Pembelian › Pesanan Pembelian › Klaim Selisih Makloon (`makloon-claims`) | K·p | K·p | K·d | K·d | – | – | – | – | – | – | – | – |
| Pembelian › Pengadaan › Permintaan Pembelian (`purchase-requisitions`) | K·p | K·p | K·d | K·d | – | K·d | – | K·d | – | – | – | – |
| Pembelian › Hutang Pemasok › Kontrabon (Tukar Faktur) (`contra-bons`) | K·p | K·p | K·d | K·d | – | – | – | – | – | – | – | – |
| Akuntansi & Pajak › Antar Entitas (Grup) (`interco-transactions`) | K·p | K·p | K·d | K·d | – | K·d | K·p | – | – | – | – | – |
| (lepas) › Analitik › Analitik Stok (`cs-stock-analytics`) | K·p | K·p | K·d | – | – | – | – | – | – | – | – | – |
| Penjualan › POS (`sales`) | K·p | – | – | – | K·d | K·d | – | – | – | – | – | – |
| Penjualan › Produk & Harga › Produk & Varian (`md-products`) | K·p | K·p | – | – | K·p | K·p | – | K·p | – | – | – | – |
| Pengaturan › Gudang & Mutu › Aturan Gudang & Mutu (`settings-cfg-warehouse`) | K·p | K·p | – | – | – | – | – | – | – | – | – | – |
| Pengaturan › Gudang & Mutu › Penerimaan & OCR (`settings-receiving-ocr`) | K·p | K·p | K·d | – | – | – | – | – | – | – | – | – |
| Pengaturan › Gudang & Mutu › Master Grade Mutu (`grade-master`) | K·p | K·p | K·d | – | – | K·d | – | – | – | – | – | – |
| Pengaturan › Integrasi & Sistem › Perangkat (`settings-devices`) | K·p | K·p | – | – | – | – | – | – | – | – | – | – |


### Aplikasi HP per peran (tab bawah) — kode + kunjungan 390 × 844

| Aplikasi (berkas) | Peran | Tab | Kunjungan | Pekerjaan gudang yang TIDAK ada (→ "Tampilan desktop") |
|---|---|---|---|---|
| `MobileWarehouseApp` (`features/mobile/MobileWarehouseApp.jsx:284-290`) | warehouse, warehouse_admin, **driver** | Masuk (kartu Kedatangan + tugas PO) · Keluar (tugas SO) · Sample (potong per baris) · Pindai (Pindai · Belum Tag · Daftar Awal) · Lainnya | `warehouse.soreang`: semua tab + 3 sub-tab + Lainnya → T:UI-01, 11, 12, 24, 36, 43 · `wh.admin`: Masuk/Keluar/Sample di 2 PT + Lainnya → T:UI-01, 05, 08, 39 · `driver`: 4 tab → T:UI-23, 39 | putaway (Lokasi Rak), transfer kirim/terima, stock opname, potong roll SO, makloon kirim/terima, perbaikan, terima retur, cek muat, gate RFID, Meja Gudang, Pengiriman (sopir) — UI-23, UI-36 |
| `MobileOpsApp` (`MobileOpsApp.jsx:180-216`) | admin, manager, finance, qc, md_quality, sample_admin, designer | Persetujuan (bila berizin) · Ringkas · Pintasan (admin/manager/md) **atau** QC (qc/md_quality) · Tanya · Lainnya | `admin`: tab terlihat Persetujuan (10) · Ringkas · Pintasan · Tanya · Lainnya (PT: Semua/Sukacita/Kanda/Cipta Sandang) → V · `qc`: **tidak pernah sampai** ke aplikasi ini (mendarat di SPK desktop) → T:UI-37 | Antrean QC Kedatangan (UI-37), semua layar stok & RFID |
| `MobileSalesApp` | sales, sales_admin | Beranda · Katalog · Keranjang · Pesanan · Lainnya (… · Stok & Pemenuhan › Stok & ATP, PIN · Layar lengkap) | `sales`: Lainnya → Stok & ATP → T:UI-06, 40 | – (stok: angka utama = grup, UI-06) |
| `MobileMdApp` | md | Meja · Desain · Lainnya (Status Stok, …) | tidak dikunjungi (K) | – |

# Revalidasi temuan frontend pada main terbaru — 8dab383

**Baseline laporan sebelumnya:** `63c38bd11b49ddfb59cbbfdb915c2e11e16d5c9c`  
**Main terbaru yang diperiksa:** `8dab383f764df80737bfe02f887422b3fd72aa70`  
**Tanggal revalidasi:** 20 Oktober 2026  
**Metode:** membandingkan Git blob lama dan terbaru, mengevaluasi ulang fungsi navigasi asli dan merender ulang JSX dari commit terbaru. Laporan lama dipertahankan sebagai bukti baseline; addendum ini menjadi status terkini keempat temuan FNA.

## Hasil terkini

| Temuan | Status pada 8dab383 | Hasil pemeriksaan ulang |
|---|---|---|
| FNA-01 — katalog akses tertinggal dari struktur menu | **Masih ada** | Grup `akuntansi`, hub `rfid-hub`, tab `goods-receipts` dan `wms-outbound` masih belum terpetakan ke modul yang diperlukan. Ada perubahan gejala interco karena menu Retur baru. |
| FNA-02 — Data Gudang menolak Admin Gudang | **Masih ada** | Pemanggil `scope=all`, daftar MASTER_SCOPE_ROLES backend, dan pembatas canManage frontend tidak berubah. |
| FNA-03 — tombol/petugas menggunakan nama role | **Masih ada** | Seluruh 15 hasil render ulang pada lima komponen sama dengan baseline. Helper `canCurrent` sudah ditambahkan, tetapi belum menggantikan gate yang dilaporkan. |
| FNA-04 — Meja Saya membuka Harga Khusus ke view salah | **Masih ada** | Peta price_approval tetap mengarah ke `approvals`; router hanya merender `price-approvals`. |

Tidak ada dari empat temuan ini yang dapat ditandai fixed. Penilaian tersebut terbatas pada empat temuan FNA dan bukan pernyataan bahwa seluruh perubahan main terbaru sudah diaudit.

## Koreksi yang wajib dipakai saat mengutip FNA-01

**Contoh lama “role custom interco hanya memperoleh Profil Saya” tidak boleh diulang sebagai hasil terbaru.** Pada 8dab383, katalog menambahkan `returns-hub` dan `interco-returns`. Role kustom tanpa acuan dengan modul Interco Kelola penuh kini memperoleh:

1. Retur → Retur Antar-PT (`interco-returns`).
2. Profil Saya (`hr-my-profile`).

Namun, menu utama **Antar Entitas (Grup)** dengan view `interco-transactions` tetap tidak muncul karena grup induk `akuntansi` belum ditambahkan oleh modul Interco. Jadi, ada pintu retur baru, sedangkan bagian transaksi utama pada temuan awal masih bermasalah.

Hasil terbaru untuk modul lain:

| Custom role tanpa acuan | View yang relevan pada hasil evaluasi |
|---|---|
| Accounting Kelola penuh | Hanya `fixed-assets` dan `hr-my-profile`; Buku Besar, laporan keuangan dan tutup buku tetap tidak tersedia melalui menu. |
| Warehouse Ops Kelola penuh | `operations`, `qc-inspection`, `production`, `wms-locations`, `md-warehouses`, `escalations`, `hr-my-profile`. Barang Masuk/Keluar dan hub RFID tetap tidak muncul. |

Katalog terbaru masih berada pada `backend/access_modules.py:56` (Interco), `:74` (Warehouse Ops), `:111` (Accounting), dan builder `nav_for_levels` pada `:210`. Pencocokan ID induk dilakukan oleh builder frontend, sehingga menambahkan izin anak tanpa induk belum menyelesaikan masalah.

## Revalidasi FNA-02

Bagian kode berikut tidak berubah antara kedua commit:

- `backend/routers/warehouses.py:36`: MASTER_SCOPE_ROLES hanya `admin`, `manager`, `warehouse`.
- `backend/routers/warehouses.py:165`: `scope=all` menolak role di luar set tersebut.
- `frontend/src/features/wms/warehouses/warehouseApi.js:11–12`: master meminta `scope=all`.
- `WarehouseMasterView.jsx:58`: canManage juga hanya tiga nama role tersebut.
- `WarehouseMasterView.jsx:83`: daftar dimuat melalui listAllWarehouses.

Izin bawaan warehouse_admin masih mencakup warehouse view/create/update. Dengan demikian rantai penolakan yang didokumentasikan tetap berlaku. Subaudit ini tidak mengklaim login HTTP/browser ulang sebagai warehouse_admin; status didasarkan pada trace kode yang eksplisit dan tidak berubah.

## Revalidasi FNA-03

Sumber JSX diambil dari commit terbaru, bukan memakai hasil baseline saja. Kelima komponen kembali dirender dengan tiga variasi akun: Admin berizin create, role kustom berizin create, serta Manager dengan view saja.

| Komponen | Gate yang masih berlaku | Hasil role kustom berizin create |
|---|---|---|
| SpecialOrders | `SpecialOrders.jsx:118`, daftar admin/sales/manager | Tombol Buat Pesanan Khusus tidak muncul. |
| InspectionsView | `InspectionsView.jsx:73`, daftar admin/manager | Tombol Buat SPK tidak muncul. |
| WarehouseMasterView | `WarehouseMasterView.jsx:58`, daftar admin/manager/warehouse | Tombol Gudang baru tidak muncul. |
| GoodsReceiptsView | `GoodsReceiptsView.jsx:14`, CREATE_ROLES | Tombol Kedatangan baru tidak muncul. |
| EntitiesAccessView | `EntitiesAccessView.jsx:47`, hanya admin | Tombol Tambah Badan Usaha tidak muncul. |

Pembanding Manager view-only tetap melihat tombol Buat pada SpecialOrders, InspectionsView dan WarehouseMasterView. Tidak ada klaim bahwa ini melewati pemeriksaan backend: endpoint masih memeriksa izin yang relevan.

Perubahan GoodsReceiptsView dan GrnDetail pada commit baru mengganti istilah sampel menjadi sample. Daftar CREATE_ROLES/REVIEW_ROLES/COUNT_ROLES tidak berubah. Perubahan EntitiesAccessView menambahkan `initialTab`, sedangkan `isAdmin` dan penerusan canManage tetap sama. Daftar officers inspeksi pada backend juga tidak berubah dari pembatas role bawaan.

Helper baru `canCurrent` pada `config/roles.js` merupakan perubahan terpisah. Kehadirannya belum memperbaiki gate lima komponen di atas karena gate tersebut tidak memakainya.

## Revalidasi FNA-04

`workDeskApi.js` tidak berubah. Evaluasi fungsi asli terhadap baris price_approval masih menghasilkan:

```json
{
  "view": "approvals",
  "nav_id": "approvals",
  "focus_type": "price_approval",
  "focus_id": "audit_price",
  "number": "PRA-AUDIT"
}
```

`has_router_render` kembali bernilai false. Renderer yang benar bergeser menjadi `AppViewRouter.jsx:345` dan tetap menggunakan `price-approvals`. `docLinkTarget` menghasilkan target salah yang sama.

## Perubahan terkait yang memang sudah terlihat

- Menu Retur terpadu dengan tab Pelanggan, Antar-PT, Supplier dan Kebijakan sudah ditambahkan.
- Matriks Izin lama menjadi alias menuju Badan Usaha & Akses → Peran & Hak Akses. Ini mengurangi duplikasi pintu pengaturan yang sebelumnya terpisah.
- Alias hidden mendapat `activeTab/aliasOf` untuk menyorot tab induknya.

Perubahan tersebut dicatat sebagai perubahan aktual; tidak dipakai untuk menutup temuan yang penyebabnya berbeda.

## Bukti terbaru dan batasnya

Evaluasi ulang mencakup 13 role bawaan, 31 variasi custom role satu modul, satu variasi semua modul, **151 ID renderer** yang terdeteksi, dan **15 render JSX**. Jumlah renderer bertambah karena view `interco-returns` baru.

- `latest-8dab.json`: status per temuan, referensi baris terbaru, dan Git blob sebelum/sesudah.
- `latest-8dab/navigation-inventory.json`: hasil fungsi navigasi terbaru.
- `latest-8dab/navigation-role-views.csv`: daftar menu per role/modul terbaru.
- `latest-8dab/button-render.json`: hasil render ulang terbaru.
- `latest-8dab/access_catalog.json`: katalog/izin dari backend terbaru.

Harness terbaru menggunakan fixture terpisah `work/KNHOST-navigation-recheck-8dab` yang dibentuk dari exact Git blob, dan dependensi Babel/React lokal yang sudah tersedia. Tidak ada kode aplikasi atau laporan baseline yang diubah. API dan komponen anak pada SSR tetap diisolasi; belum menjadi bukti klik browser, pemuatan API per akun, atau seluruh rantai transaksi.

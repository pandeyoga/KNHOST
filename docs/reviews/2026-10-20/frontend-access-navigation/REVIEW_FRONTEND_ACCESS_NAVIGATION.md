# Audit frontend — navigasi, tombol, dan custom role

**Project:** ERP Kain Nussantara  
**Baseline:** `main` commit `63c38bd11b49ddfb59cbbfdb915c2e11e16d5c9c`  
**Pemeriksaan:** 19–20 Oktober 2026  
**Sumber lokal:** `C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-plan-audit-2026-10-19`  
**Jenis pemeriksaan:** penelusuran kode frontend dan backend, evaluasi fungsi navigasi asli, serta render komponen JSX terisolasi. Tidak menggunakan browser pada subaudit ini dan tidak mengubah kode aplikasi.

## Kesimpulan

Menu bawaan yang dievaluasi mempunyai renderer tujuan. Alias Beranda ditangani oleh `App.handleNavSelect`, sehingga target `home` bukan halaman hilang. Namun, konfigurasi custom role belum lengkap mengikuti struktur menu terbaru. Pemberian izin melalui editor tidak selalu menghasilkan menu atau tombol yang dibutuhkan.

Empat temuan terkonfirmasi dalam lingkup ini:

| ID | Prioritas | Masalah | Bukti utama |
|---|---|---|---|
| FNA-01 | P1 | Katalog akses belum mengikuti perubahan induk menu dan tab; role kustom dapat mempunyai izin penuh tetapi kehilangan seluruh pintu keuangan/interco atau tab WMS/RFID. | Evaluasi fungsi navigasi asli untuk 31 modul dan 13 role bawaan. |
| FNA-02 | P2 | Admin Gudang mendapat halaman Data Gudang yang memanggil API `scope=all`, tetapi API menolak role tersebut. | Rantai pemanggil frontend → pembatasan backend yang eksplisit. |
| FNA-03 | P2 | Sejumlah tombol dan pilihan petugas masih mengikuti nama role, sehingga tidak mengikuti izin rinci yang dikonfigurasi. | 15 kasus render JSX pada lima komponen dan pembandingan endpoint backend; tambahan penelusuran detail QC/GRN. |
| FNA-04 | P2 | Tombol pengajuan harga khusus dari Meja Saya mengarah ke view `approvals` yang tidak dirender. | Fungsi `rowLink`/`docLinkTarget` asli mengembalikan target tanpa renderer. |

Temuan ini membuktikan bagian role/menu/tombol belum dapat dinyatakan tuntas. Pemeriksaan tidak membuktikan bahwa semua tombol di seluruh aplikasi telah diuji klik, atau bahwa setiap transaksi yang dipicu tombol sudah benar hingga jurnal akhirnya.

## Cakupan dan metode

1. Membaca `AppViewRouter`, `App.handleNavSelect`, registri navigasi, tab hub, registri role, editor role, serta katalog izin backend.
2. Mengevaluasi fungsi konfigurasi JavaScript asli dengan Babel. Impor ikon diganti komponen kosong; kode logika role, builder menu, palette, dan target dokumen tidak diganti.
3. Memeriksa 13 role bawaan dan 31 variasi role kustom tanpa role acuan: satu modul diberi Kelola penuh, modul lain Tidak ada. Ditambahkan satu variasi semua modul Kelola penuh.
4. Mendeteksi 150 ID view render, termasuk tiga varian galeri R&D yang dirender melalui kondisi kelompok. Membandingkan tujuan menu yang dihasilkan terhadap renderer. `home` diperiksa sebagai alias yang sengaja di-resolve oleh `App.js`.
5. Merender JSX asli lima komponen menggunakan React SSR. Impor komponen anak, hook data, dan API diganti agar tidak melakukan jaringan. State awal dan kondisi tombol dari komponen yang diperiksa tetap asli. Ini bukti unit render, bukan bukti interaksi browser.
6. Membandingkan kondisi tombol dengan izin endpoint backend terkait. Tidak mengirim POST/PATCH transaksi produksi.

Jumlah tujuan menu menurut konfigurasi izin bawaan:

| Role | Tujuan palette yang dihasilkan |
|---|---:|
| Admin | 143 |
| Manager | 125 |
| Admin Sales | 39 |
| Finance | 25 |
| Sales | 34 |
| Gudang | 31 |
| Designer | 10 |
| Driver | 3 |
| MD | 27 |
| Admin Gudang | 34 |
| Admin Sampel | 8 |
| MD Quality | 4 |
| QC | 5 |

Angka merupakan jumlah target palette yang dihasilkan, bukan jumlah transaksi yang lulus UAT. Daftar lengkap tersedia di `navigation-inventory.json` dan `navigation-role-views.csv`.

## FNA-01 — izin aktif tidak mempunyai menu yang sesuai

**Prioritas P1. Status: terkonfirmasi melalui evaluasi fungsi navigasi asli.**

### Kondisi aktual

`backend/access_modules.py` menjadi sumber pilihan Modul/Menu/Tab di editor dan membentuk `nav.add/remove` role kustom melalui `nav_for_levels` (baris 210). Namun, katalog ini belum seluruhnya mengikuti restrukturisasi menu:

- Modul `interco` (baris 56) masih menambahkan `pembelian`, `accounts-payable`, dan `interco-transactions`, sedangkan menu Antar Entitas telah dipindahkan ke grup `akuntansi` pada `frontend/src/config/navStructure.js:290–302`.
- Modul `accounting` (`access_modules.py:111`) menambahkan `keuangan`, `ledger`, `fin-reports`, `closing`, dan `period-unlock`, tetapi tidak menambahkan grup induk `akuntansi`.
- Modul `warehouse_ops` (`access_modules.py:74`) belum memuat tab `goods-receipts`, `wms-outbound`, dan induk `rfid-hub`; katalog masih menyebut `rfid`. Struktur terbaru menggunakan `rfid-hub` pada `navStructure.js:259`.
- Sejumlah view operasional lain tidak terdaftar dalam katalog, misalnya `internal-prices`, `customers-master`, `posting-failures`, dan beberapa tab Pengaturan. Tidak semua ID yang tidak terdaftar otomatis merupakan bug: `home` adalah alias dan `hr-my-profile` memang disediakan melalui ALWAYS_NAV.

`buildNavGroups` di `frontend/src/config/navigationConfig.js:105` lebih dahulu menyaring grup induk menggunakan `roleCanSee`. Karena role kustom tanpa acuan tidak terdapat pada daftar role bawaan grup tersebut dan `nav.add` tidak memuat induknya, anak menu tidak pernah diproses meskipun izin API dan ID anak aktif.

### Reproduksi dan hasil

1. Buat role baru tanpa menyalin role bawaan.
2. Atur **Transaksi Antar Badan Usaha → Kelola penuh**, modul lain Tidak ada.
3. Preview/menu yang dievaluasi hanya berisi **Profil Saya**. Menu Antar Entitas tidak muncul.
4. Ulangi untuk **Akuntansi & Tutup Buku → Kelola penuh**.
5. Preview/menu hanya berisi **Aset Tetap** dan **Profil Saya**; Buku Besar, laporan, Tutup Buku, dan Buka Periode tidak dapat ditemukan melalui navigasi.
6. Ulangi untuk **Operasi Gudang → Kelola penuh**.
7. Operasi, Produksi, Lokasi Rak, Data Gudang, dan Eskalasi tampil. **Barang Masuk, Barang Keluar, serta hub RFID tidak tampil**.

Menyertakan semua modul dengan izin penuh juga tidak memperbaiki ID yang tidak terdaftar atau induk `akuntansi`/`rfid-hub`. Role dengan acuan tertentu dapat mewarisi sebagian pintu tersebut, sehingga masalah mudah terlewat bila pengujian hanya menduplikat role bawaan.

### Dampak

Role yang disiapkan untuk petugas keuangan atau gudang dapat memiliki izin yang benar tetapi tidak mempunyai antarmuka untuk bekerja. Editor juga tidak dapat menyembunyikan/menampilkan tab yang belum berada dalam katalog. Backend memvalidasi `hidden_views` terhadap `all_nav_ids` pada `custom_role_service.py:239–245`, sehingga sekadar mengirim ID tab baru bukan penyelesaian.

### Arah perbaikan dan titik selesai

Sinkronkan seluruh induk grup, hub, view, dan alias ke satu registri yang dipakai navigasi serta editor. Hindari menambah izin API untuk mengatasi menu hilang. Setiap modul yang aktif harus mempunyai menu yang sah, dan setiap tab operasional yang dapat dikonfigurasi harus terpetakan ke resource yang tepat.

Selesai jika role baru **tanpa acuan** untuk interco, akuntansi, WMS, GRN, dan RFID mempunyai menu sesuai izin, tampilan preview sama dengan sesi pengguna sebenarnya, dan pencabutan hak menghilangkan tombol/menu terkait. Tambahkan tes parity ID induk-anak dan pemetaan view/resource.

**Acceptance terdampak:** LN-015-T01, LN-015-T02, LN-015-T04.

## FNA-02 — Data Gudang menolak Admin Gudang

**Prioritas P2. Status: terkonfirmasi dari rantai kode; belum dinyatakan diuji browser/HTTP sebagai role tersebut pada subaudit ini.**

### Rantai masalah

1. `frontend/src/config/roles.js:294` menyatakan `warehouse_admin` mewarisi menu `warehouse`. Menu Data Gudang mempunyai view `md-warehouses`.
2. Izin bawaan pada `backend/permissions_config.py:527` memberi Admin Gudang `warehouse: [view, create, update]`.
3. `WarehouseMasterView.jsx:83` memuat data melalui `listAllWarehouses()`.
4. `warehouseApi.js:11–12` selalu mengirim `GET /warehouses?scope=all`.
5. `backend/routers/warehouses.py:36` mendefinisikan `MASTER_SCOPE_ROLES = {admin, manager, warehouse}`. Baris 165–167 menolak role di luar set ini dengan 403.
6. Frontend `WarehouseMasterView.jsx:58` juga membatasi `canManage` ke tiga nama role yang sama. Jadi setelah akses data dibenahi sekalipun, Admin Gudang tetap kehilangan tombol sesuai izin create/update yang dimilikinya.

### Dampak

Admin Gudang melihat pintu Data Gudang tetapi gagal memuat daftar, dan izin yang disediakan tidak menghasilkan kemampuan yang dijanjikan. Role kustom yang mempunyai izin warehouse juga mengalami pembatasan berdasarkan nama role ini.

### Arah perbaikan dan titik selesai

Putuskan visibilitas gudang melalui izin dan scope lokasi/badan usaha akun; jangan membuat role baru otomatis dapat melihat semua gudang. Halaman master perlu meminta cakupan yang sah untuk pengguna, sedangkan server tetap memeriksa izin dan scope. Tombol Buat/Ubah/Nonaktifkan harus mengikuti aksi masing-masing; jangan menyamakan `warehouse.update` dengan `warehouse.delete`.

Selesai jika Admin Gudang dan role kustom berizin dapat memuat gudang dalam scope mereka, mengubah hanya sesuai hak, dan tetap ditolak untuk gudang di luar scope. Uji juga role read-only agar tombol mutasi tidak muncul.

**Acceptance terdampak:** LN-015-T01, LN-015-T04; cakupan operasional WMS L10.

## FNA-03 — tombol dan pilihan petugas masih berdasarkan nama role

**Prioritas P2. Status: kondisi kode terkonfirmasi; 15 kasus render JSX terisolasi tersedia.**

### Bukti render

`button-render.json` merekam render komponen asli:

| Komponen/tombol | Izin role kustom dalam fixture | Tombol pada role kustom | Kontrol pembanding |
|---|---|---|---|
| SpecialOrders — Buat Pesanan Khusus | `order.view/create` | Tidak muncul | Admin dengan izin sama: muncul; Manager dengan view saja: tetap muncul. |
| InspectionsView — Buat SPK Inspeksi | `inspection.view/create` | Tidak muncul | Admin dengan izin sama: muncul; Manager dengan view saja: tetap muncul. |
| WarehouseMasterView — Gudang baru | `warehouse.view/create` | Tidak muncul | Admin dengan izin sama: muncul; Manager dengan view saja: tetap muncul. |
| GoodsReceiptsView — Kedatangan baru | `goods_receipt.view/create` | Tidak muncul | Admin dengan izin sama: muncul. |
| EntitiesAccessView — Tambah Badan Usaha | `entity.view/create` | Tidak muncul | Admin dengan izin sama: muncul. |

Fixture Manager dengan view saja menggambarkan role bawaan yang haknya sudah dicabut/dibatasi melalui editor. API tetap menjaga penolakan; masalahnya tombol masih menawarkan tindakan yang pasti ditolak. Tidak ada klaim bahwa kondisi ini menembus otorisasi backend.

### Pemetaan kondisi terhadap backend

| Layar dan kondisi UI | Letak frontend | Enforcement backend |
|---|---|---|
| Buat Special Order berdasarkan admin/sales/manager | `SpecialOrders.jsx:118`, tombol baris 175 | `special_orders.py:195` memakai `order.create`. |
| ACC/transisi dan edit bagian OD berdasarkan role literal | `SpecialOrderDetail.jsx:43–44`, 420, 432, 435 | Endpoint route/customer-decision/status memakai aksi order tersendiri, misalnya `special_orders.py:542`, 724, 863. Kelayakan status dan aturan approval tetap harus dipertahankan. |
| Buat inspeksi hanya admin/manager | `InspectionsView.jsx:73`, 164 | `inspections.py:178` memakai `inspection.create`. |
| Tugaskan/tutup/reopen inspeksi hanya admin/manager, dengan pengecualian random QC | `InspectionDetailPanel.jsx:56–57`, 377, 407, 422 | `inspections.py:193`, 279, 294 memakai `inspection.assign/decide/reopen`. |
| Buat GRN berdasarkan CREATE_ROLES | `GoodsReceiptsView.jsx:14`, 65 | `goods_receipts.py:33` memakai `goods_receipt.create`. |
| Review/count GRN berdasarkan REVIEW_ROLES/COUNT_ROLES | `GrnDetail.jsx:12–23` | Router goods_receipts memakai `goods_receipt.review/count/close` sesuai aksi. |
| Kelola gudang berdasarkan admin/manager/warehouse | `WarehouseMasterView.jsx:58` | `warehouses.py:176`, 224, 287 memisahkan `warehouse.create/update/delete`. |
| Badan usaha, akun, dan pintu buat role baru berdasarkan admin literal | `EntitiesAccessView.jsx:47`, 108, 165; `AccountList.jsx:51`, 216, 341 | `entities.py:142`, `users.py:123/137`, `access_roles.py:78` memakai `entity.create`, `user.create/update`, `permission.update`. |

Ada masalah tambahan pada pemilihan petugas inspeksi. `backend/routers/inspections.py:58–61` membangun daftar `officers` dengan daftar role bawaan yang tetap. Petugas dengan role kustom QC/MD Quality tidak akan muncul dalam pilihan meskipun izin inspect miliknya aktif. Sementara `_resolve_assignee` pada `inspection_service.py:500–507` menerima akun berdasarkan ID dan tidak memakai pembatas role tersebut. Dengan demikian alur penugasan lewat form tertinggal dari kemampuan izin sistem.

### Contoh dampak bisnis

Admin membuat role **PIC Proofing** atau **Petugas Receiving Bandung** dengan hak yang dipilih secara rinci. Pengguna dapat masuk dan melihat sebagian layar, tetapi tombol tugasnya tidak muncul karena nama role-nya bukan salah satu string bawaan. Sebaliknya, Manager yang dipindahkan ke akses Lihat saja masih ditawari tombol Buat. Ini bertentangan dengan target custom role yang dikonfigurasi tanpa mengubah kode.

### Arah perbaikan dan titik selesai

Setiap tombol memakai izin aksi yang sama dengan endpoint, ditambah prasyarat status, penugasan, scope, dan aturan bisnis yang memang berlaku. Bila keputusan juga mensyaratkan tingkat approval, server perlu memberikan capability yang memperhitungkan keduanya; jangan mengganti semua pembatas begitu saja dengan `manage` umum.

Daftar petugas harus berasal dari akun aktif yang mempunyai kemampuan tugas dan scope sesuai dokumen. Selesai jika satu role kustom dengan izin yang sama menghasilkan tombol yang sama, pengurangan izin langsung menonaktifkan/menghilangkan tindakan, pengguna tanpa izin tetap ditolak API, dan pilihan petugas hanya memuat akun yang sah.

**Acceptance terdampak:** LN-015-T01, LN-015-T03, LN-015-T04, LN-015-T06. Kasus race ACC, invalidasi sesi, dan semua variasi scope tidak dinyatakan selesai hanya dari render ini.

## FNA-04 — tombol Harga Khusus dari Meja Saya membuka view kosong

**Prioritas P2. Status: terkonfirmasi melalui fungsi target asli dan renderer router.**

### Reproduksi

1. Terdapat pengajuan harga dengan status pending.
2. `backend/services/role_desk_service.py:72–75` memasukkannya ke antrean Manager **Permintaan harga khusus** dengan `ref_type=price_approval`.
3. Pengguna membuka baris/menekan Putuskan dari Meja Saya.
4. `RoleDesk.jsx:74` memanggil `rowLink(row, queue.id, desk)`.
5. `workDeskApi.js:217` mengembalikan `view: approvals`, `nav_id: approvals`.
6. `App.js:299–307` langsung menetapkan activeView ke nilai itu.
7. `AppViewRouter.jsx:344` hanya mempunyai view `price-approvals`. Tidak ada renderer atau alias untuk `approvals`. `isComingSoonView` juga tidak menganggap nilai tersebut sebagai placeholder.

Hasil evaluasi `rowLink` dengan fixture ref_type price_approval:

```json
{
  "view": "approvals",
  "nav_id": "approvals",
  "focus_type": "price_approval",
  "focus_id": "audit_price",
  "number": "PRA-AUDIT"
}
```

`has_router_render` bernilai false. `docLinkTarget` memakai peta yang sama sehingga mewarisi target salah jika resolver memberikan dokumen bertipe tersebut.

### Arah perbaikan dan titik selesai

Ganti target ke hub/view yang benar, lalu dukung fokus pengajuan yang dipilih. Mengubah string view saja akan membuka daftar tetapi `PriceApprovals` saat ini belum menerima `focusDoc` dari AppViewRouter; konteks baris tetap dapat hilang. Selesai jika klik antrean membuka pengajuan yang benar, ID tidak dikenal memberi pesan yang jelas, dan pengujian memeriksa seluruh target `rowLink` terhadap router.

**Acceptance terdampak:** LN-102 (aksi Meja Saya membuka detail yang relevan), LN-015-T01.

## Bagian yang sudah ada dan tidak dicatat sebagai bug

- Builder sidebar, palette, hub tab, dan resolver deep link menggunakan fungsi `roleCanSee` yang sama. Ini landasan konsistensi yang baik.
- Editor sudah memiliki Modul, pemilih Menu/Tab, panel aksi rinci, status partial, ringkasan diff, preview menu, daftar akun terdampak, peringatan perubahan belum disimpan, dan pengiriman expected_version saat mengubah role.
- Server membersihkan izin rinci, memberi `view` ketika aksi memerlukannya, memvalidasi ID hidden_views, dan mengunci role Admin.
- Menu `home` yang tidak mempunyai cabang renderer langsung merupakan alias yang sah; tidak dimasukkan sebagai temuan.
- Tidak ditemukan target menu bawaan tanpa renderer setelah alias yang diketahui diperhitungkan. Ini tidak menjamin datanya berhasil dimuat atau tombol internalnya benar.

## Batas audit dan langkah validasi berikutnya

Belum ada klaim lulus untuk seluruh kombinasi scope entitas/lokasi/lini, keyboard/tablet, semua tombol modal, unggah berkas, pengunduhan dokumen, atau transaksi final per role. Tidak seluruh renderer dicoba melalui browser pada subaudit ini. React SSR tidak menjalankan effect API maupun klik tombol.

Prioritas UAT berikutnya: role tanpa acuan untuk keuangan/interco dan receiving, Admin Gudang membuka Data Gudang, role kustom QC muncul di daftar petugas, Manager read-only, lalu klik harga khusus dari Meja Saya. Semua perbaikan harus tetap menjaga pembatasan scope, status proses, dan penolakan server yang benar.

## Bukti dan reproduksi

- `navigation-inventory.json`: hasil evaluasi fungsi konfigurasi; daftar per role/modul serta target harga khusus.
- `navigation-role-views.csv`: daftar tujuan navigasi bawaan dan role kustom.
- `access_catalog.json`: snapshot katalog dan izin bawaan yang dibaca dari backend commit ini.
- `button-render.json`: hasil 15 render JSX terisolasi.
- `findings.json`: temuan terstruktur untuk konsolidasi dan pelacakan.
- Harness di workspace: `work/audit_navigation.cjs` dan `work/audit_role_button_render.cjs`.

Harness navigasi dan render dijalankan menggunakan Node lokal dengan dependensi frontend yang sudah tersedia. Ikon dan dependency tampilan terisolasi sebagaimana dijelaskan di atas. Keduanya tidak menulis ke database dan tidak mengubah aplikasi.

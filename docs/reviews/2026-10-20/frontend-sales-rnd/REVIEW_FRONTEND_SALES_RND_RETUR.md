# Review frontend Sales, Special Order, R&D, QC, dan retur

Tanggal finalisasi: 20 Oktober 2026. Acuan: snapshot main `63c38bd11b49ddfb59cbbfdb915c2e11e16d5c9c` di `work/KNHOST-plan-audit-2026-10-19`. Kode aplikasi tidak diubah.

## Kesimpulan

Tombol utama sudah memiliki handler dan banyak alur yang dibutuhkan sudah tersedia. Kehadiran tombol belum menjamin bahwa alur akhirnya benar. Pemeriksaan menemukan satu masalah besar pada Special Order multiitem: formulir menerima beberapa produk dan pengadaan bekerja per item, tetapi harga akhir serta konversi penjualannya masih memakai struktur satu produk. Ditemukan pula masalah penanganan kegagalan retur, hak custom role, satuan QC, dan pemilihan SO sumber retur.

Pemeriksaan ini adalah review kode dan pengujian fungsi frontend yang diekstrak dari kode asli. Browser/UAT dilakukan oleh pemeriksa utama dan harus digabungkan dengan laporan ini. Jangan menandai seluruh UI lulus berdasarkan inventaris statis.

## Temuan

### FE-SR-04 — P1 — Special Order multiitem menyusut menjadi satu produk ketika dihitung dan dikonversi ke SO

**Perjalanan di UI.** Sales membuka Pesanan Khusus → Buat → menambah Artikel A 100 yard dan Artikel B 200 yard → keduanya menyelesaikan sample dan ACC pelanggan → mengunci harga → pengadaan/konversi ke SO. Form multiitem tersedia pada `SpecialOrderItemsEditor.jsx:34`. Panel harga tetap hanya menampilkan satu harga, satu kuantitas, dan satu total pada `SpecialOrderPricingPanel.jsx:73`. Konversi manual tersedia pada detail; endpoint kunci harga juga mencoba konversi otomatis setelah pengadaan berhasil (`backend/routers/special_orders.py:601`).

**Kesalahan kode.** `backend/routers/special_orders.py:221` membuat `custom_item.quantity/unit` dari item pertama untuk kompatibilitas. `backend/services/special_order_phase2.py:275` memilih satu sample pemenang terakhir, kemudian pada baris 283 mengambil kuantitas dari `custom_item`, bukan menghitung per item. Endpoint konversi pada `backend/routers/special_orders.py:1034` membangun `items=[SalesOrderItemIn(...)]`: tepat satu produk `linked_product_id` dengan kuantitas item pertama.

**Guard sudah ditelusuri.** Tidak ada penolakan multiitem sebelum pricing/konversi. `create_order` downstream memproses item payload yang diterimanya; `source_special_order_id` digunakan untuk harga pada `backend/routers/sales_orders.py:215`, tanpa merekonsiliasi kembali daftar item Special Order. Jalur pengadaan per item dalam `special_order_fulfillment.py` tidak memperbaiki payload penjualan ini.

**Bukti.** Fungsi pricing asli dijalankan dengan fixture baca dua sample: A biaya 10 × 100 yard, B biaya 30 × 200 yard, margin 30%. Hasil asli: produk B, harga 39, qty 100, total **3.900**. Perhitungan dua item dengan aturan margin yang sama menghasilkan **9.100** (1.300 + 7.800). Ekspresi payload konversi yang diambil langsung dari AST router menghasilkan hanya **B 100 yard**, bukan A 100 dan B 200. Bukti: `multi-item-evidence.json`, harness `verify-multi-item.py`.

**Batas bukti.** Ini reproduksi unit fungsi asli dengan fixture baca DB dan ekspresi payload asli. Koneksi Mongo real terhambat inisialisasi Windows asyncio, sehingga tidak diklaim sebagai uji HTTP atau pengiriman/AR end-to-end.

**Dampak.** Artikel hilang dari SO, kuantitas artikel yang tersisa dapat salah, total pesanan berubah, dan pengadaan tidak lagi cocok dengan pemenuhan/penagihan.

**Arahan perbaikan.** Jadikan item Special Order sebagai sumber seluruh harga dan konversi: produk hasil R&D, qty, unit, supplier, kontrak, harga final, dan relasi source item harus tersimpan per item. Harga header menjadi agregat sesuai satuan uang, bukan satu item. Konversi wajib menghasilkan semua item tepat satu kali; larang konversi parsial diam-diam. Rekonsiliasi data existing yang telanjur dikonversi sebelum menjalankan migrasi.

**Titik selesai.** Dua item berbeda, dua supplier, dan dua unit menghasilkan SO dengan pasangan item/qty/unit/harga yang benar; pengadaan, receiving, reservasi, pengiriman, invoice/AR mengikuti item yang sama. Retry tidak menambah atau menghilangkan item. Uji item yang belum lulus harus memblokir konversi sesuai aturan finalisasi. Skenario ini melengkapi LN-030-T01 dan verifikasi rantai L14; lulus tes realisasi pengadaan saja belum menutupnya.

### FE-SR-01 — P2 — Retur yang gagal diselesaikan menutup dialog dan menyembunyikan alasannya

**Skenario.** Buka detail retur berstatus inspected → Selesaikan → pilih refund → server menolak karena kebijakan/bukti/keadaan transaksi → dialog harus tetap terbuka dan pesan harus terlihat.

**Kesalahan kode.** `SalesReturns.jsx:163` menangkap kegagalan settlement dan memanggil `setError`, tetapi tidak melempar ulang atau mengembalikan penanda gagal. Cabang detail langsung `return <ReturnDetail>` pada baris 207, tanpa meneruskan error. Komponen error justru dirender pada daftar di baris 300. `ReturnSettleModal.jsx:63` menganggap `await onSettle` berhasil lalu `onClose()` pada baris 65. Pola error tersembunyi juga berlaku untuk approve, mulai/selesai inspeksi, reject, dan submit pada detail.

**Bukti.** Harness mengeksekusi `handleSettle` dan `confirm` asli dari AST JSX, kemudian menyuntikkan penolakan API. Hasil: `modal_closed=true`, error hanya berada dalam state parent yang tidak dirender di cabang detail. Bukti: `callback-evidence.json` FE-SR-01. Ini verifikasi callback, bukan screenshot browser.

**Arahan perbaikan.** Render error pada detail yang aktif. Tetapkan kontrak callback yang eksplisit: lempar ulang setelah pencatatan, atau kembalikan `{ok:false}` yang diperiksa child. Tutup modal hanya setelah sukses. Pertahankan keputusan, qty, akun, dan catatan saat gagal. Gunakan pola yang sama untuk seluruh aksi detail retur.

**Titik selesai.** Penolakan 400/403/409 dan gangguan jaringan pada tiap aksi terlihat pada halaman aktif; settlement gagal tidak menutup dialog dan tidak menampilkan sukses; retry memakai input sebelumnya dan menghasilkan satu transaksi.

### FE-SR-03 — P2 — Hak custom role tidak menentukan beberapa tombol Special Order dan retur

**Skenario.** Buat custom role dengan izin `order.create/update/approve` atau `sales_return.approve` yang sah, lalu buka halaman yang sama. Menu dapat diizinkan, tetapi tombol inti tetap hilang karena nama role tidak termasuk array literal.

**Letak.** `SpecialOrders.jsx:118` membatasi Buat pada admin/sales/manager (bahkan sales_admin tidak termasuk). `SpecialOrderDetail.jsx:43` membatasi ACC pada manager/admin; pada baris 420, 432, dan 435 upload/re-routing/redesign/ACC customer dibatasi literal admin/manager/sales/sales_admin. `SalesReturns.jsx:124` membatasi ACC/settlement/disposisi pada admin/manager. Endpoint ACC customer memakai `require_permission(request,"order","update")` pada `backend/routers/special_orders.py:542`; ACC retur memakai `sales_return.approve` pada `backend/routers/sales_returns.py:278`. Artinya izin efektif server dapat sah ketika tindakan UI tetap tidak tersedia.

`roleIs` di sejumlah layar R&D sudah mendukung base role, tetapi belum setara dengan hak aktivitas yang sepenuhnya dapat dikonfigurasi. Mengganti array literal dengan `roleIs` saja belum cukup untuk memenuhi LN-015-T01/T03: izin aktivitas perlu menjadi sumber tombol dan backend. Khusus lock-price, backend juga memiliki pembatas role literal pada `special_orders.py:590`; perbaikan harus konsisten pada kedua sisi.

**Bukti.** Evaluasi kondisi literal menunjukkan custom role selalu `canEdit=false` meskipun izin yang dimaksud telah diberikan. Enforcement backend ditelusuri sampai `dependencies.has_permission`: izin dibaca berdasarkan matrix role. Pengujian akun custom role melalui browser/API penuh masih perlu dilakukan oleh pemeriksa utama.

**Arahan perbaikan dan titik selesai.** Gunakan capability/permission yang dikirim server untuk masing-masing aksi. Uji role custom yang diberi satu izin saja dan role standar yang izinnya dicabut: tombol mengikuti grant, API mengikuti grant yang sama, scope tetap dibatasi, dan nama/base role tidak memberi wewenang tambahan. Status dokumen tetap menjadi pagar terpisah.

### FE-SR-05 — P2 — Antrean QC melabeli semua kuantitas sebagai meter dan menjumlah angka tanpa satuan

**Letak.** `QCInspection.jsx:75` menjumlah `quarantine_qty` seluruh task. Baris 142 menampilkan hasilnya sebagai `m`; kuantitas per task, modal, input diterima/ditolak, dan total alokasi juga dilabel `m` pada baris 193, 219, 229, dan 248. Halaman ini aktif melalui `features/inspections/QcHubView.jsx:22`.

**Sumber data.** Endpoint `backend/routers/inbound_receiving_extra.py:93` menambahkan kuantitas mentah dari `quarantine_qty_for_task`. Service `backend/services/qc_service.py:30` menjumlah `length_remaining` roll, tanpa mengonversi ke meter. Movement QC sendiri tetap mengambil `roll.unit` (`qc_service.py:86`). Tidak ada konversi yang mendukung label meter yang ditampilkan UI.

**Dampak.** Pengguna dapat membaca 100 yard sebagai 100 meter. Bila antrean memuat basis satuan berbeda, angka totalnya tidak memiliki makna operasional. Label input yang salah juga berpotensi membuat keputusan qty salah, walaupun backend menyimpan angka tersebut dalam basis aslinya.

**Batas bukti.** Penelusuran kode dan kontrak endpoint; belum screenshot fixture yard/kg. Jangan mengklaim kehilangan stok hanya dari temuan tampilan ini.

**Arahan perbaikan dan titik selesai.** Endpoint menyatakan unit basis task/roll secara eksplisit; UI menampilkan unit tersebut. Kelompokkan total per unit. Jika ingin meter ekuivalen, tampilkan sebagai nilai konversi terpisah dengan faktor yang jelas. Uji task yard dan kg/meter sekaligus; tidak ada penjumlahan berbeda unit menjadi satu angka.

### FE-SR-02 — P2 — Memilih SO retur dengan cepat dapat menampilkan barang dari SO sebelumnya

**Letak.** `CreateReturnForm.jsx:59` memulai GET returnable untuk setiap perubahan SO, tetapi callback tidak memeriksa apakah SO masih terpilih dan tidak membatalkan request lama.

**Bukti.** Jalankan handler asli: pilih SO-A, pilih SO-B, respons B selesai dahulu, kemudian respons A. Hasil akhir: `orderId=SO-B`, baris produk **product-A**. Bukti deterministik pada `callback-evidence.json` FE-SR-02. Unit/batas qty/roll yang terlihat juga berasal dari respons lama.

**Dampak.** Sales menyiapkan retur dengan sumber tampilan salah; server dapat menolaknya karena item tidak terkait. Temuan ini tidak mengklaim bahwa backend menerima retur lintas SO.

**Arahan perbaikan dan titik selesai.** Gunakan request sequence atau cancellation; set loading dan blok submit sampai data returnable untuk SO aktif selesai. Uji dua respons terbalik, pemilihan kosong, error request terbaru, dan pergantian setelah roll dicentang. Tampilan dan payload selalu bersumber dari SO yang aktif.

### FE-SR-06 — P2 — Pilihan SO sumber retur terpotong pada 200 pesanan terbaru

**Letak.** `SalesReturns.jsx:110` memanggil `/sales-orders` tanpa pagination, status, atau pencarian server lalu memfilter eligible di browser. Jalur nonpaged `backend/routers/sales_orders_extra.py:183` mengambil maksimal 200 dokumen terbaru. Form pada `CreateReturnForm.jsx:143` hanya menawarkan hasil tersebut; tidak ada mekanisme mencari/memuat SO eligible di luar cap.

**Skenario.** Pesanan ke-201 masih memenuhi masa retur tetapi ada 200 pesanan lebih baru dalam scope user. SO lama tidak dapat dipilih, meskipun returnable endpoint sebenarnya dapat melayaninya. Bahkan 200 pesanan baru yang belum dikirim dapat menghabiskan seluruh pilihan, karena penyaringan status dilakukan setelah cap.

**Batas bukti.** Kontrak cap dan konsumen ditelusuri statis. Belum dibuat fixture 201 pesanan melalui browser; jangan menyebutnya hasil load test.

**Arahan perbaikan dan titik selesai.** Pakai pemilih SO dengan pencarian dan pagination server, scope user/entitas, serta filter barang yang sudah dikirim. Uji lebih dari 200 pesanan, pencarian nomor/pelanggan, dan SO lama yang eligible. Jangan memperbesar cap sebagai pengganti pemilih yang terpaginate.

## Hal yang sudah tersedia dan ditelusuri

| Domain | Tindakan/jalur yang ditelusuri | Batas review |
|---|---|---|
| Special Order | Buat multiitem; sumber induk/artwork ACC/referensi; submit; ACC/tolak; upload referensi; link sample; redesign; keputusan customer ACC/revisi/tolak + bukti; preview/lock/unlock harga; pilih jalur supplier/makloon; realisasi per item; konversi SO; prepare shipment | Handler dan endpoint ditelusuri; belum seluruh variasi browser/role/E2E. |
| Retur | Daftar/filter/status counts; create dari returnable; pilih roll; qty/unit; foto; submit; approve/reject; mulai/selesai inspect; settle; reverse; keluhan; scan terima/kirim/tiba; timeline; disposisi antar-PT/supplier/BS | Callback kegagalan dan race direproduksi. Seluruh konsekuensi finance/stock bukan cakupan verifikasi frontend ini. |
| R&D | Daftar/papan/detail sample; buat/kirim; round submit/assess; pilih pemenang; uji ulang existing; PIC queue/decision; material issue; form kontrak; desain/HOLD/paper; link status proofing | Gate role dan fungsi API ditelusuri. Cacat revalidation ACC tipe lain/round lama sudah masuk temuan audit sebelumnya, tidak dihitung ulang sebagai temuan frontend baru. |
| QC/MD Quality | Hub antrean/dokumen; rencana sampling/cakupan; form keputusan kedatangan; 4-point entry; detail inspeksi; assign/start/finish/reopen; hasil MD Quality dan release/reject hold | Terdapat dua keluarga UI inspeksi yang harus diuji bersama. Aturan rumus/grade yang masih pending tidak ditetapkan sendiri. |
| Meja Admin Sales | Load antrean; deep link; verifikasi; konfirmasi; rencana pemenuhan; permintaan harga internal; feedback setelah partial execution | Perbaikan execError terpisah dari load error terlihat di source. Tidak ada klaim lulus semua kombinasi alokasi. |

## Inventaris dan batas cakupan

`control-inventory.json` berisi **155 berkas / 893 elemen** button, input, KNSelect, dan FormModal di Sales, Sales Admin, R&D, Inspections, dan QC queue. Ini inventaris AST otomatis untuk membantu pemeriksaan tombol. **Jumlah tersebut bukan jumlah tombol yang telah diklik atau halaman yang telah lulus.** Elemen yang dihasilkan dinamis dan komponen reusable juga membutuhkan UAT sesuai konteks.

Pembacaan manual yang lebih dalam meliputi SpecialOrders, CreateSpecialOrderForm, SpecialOrderItemsEditor, SpecialOrderDetail, SpecialOrderItemsPanel, SpecialOrderChainPanel, SpecialOrderCustomerApprovalPanel, SpecialOrderPricingPanel, SpecialOrderFulfillmentPanel, SpecialOrderShippingPanel, SalesReturns, CreateReturnForm, ReturnDetail, ReturnSettleModal, ReturnInspectPanel, ReturnJourneyPanel, ReturnTimelinePanel, ReturnDispositionPanel, ReturnChainPanel, RndSamplesView, RndDesignsView, SampleDetailPanel, RevalDecideModal, rndApi, SalesAdminDesk, FulfillmentDecisionDialog, CustomerGradeRulesCard, QCInspection, QcPlanPanel, QcHubView, InspectionsView, InspectionDetailPanel, DesignDetailPage, apiClient, dan roles. Beberapa komponen anak hanya diperiksa melalui pencarian handler/import dan tidak dianggap lulus penuh.

Backend yang ditelusuri untuk kontrak: routers special_orders, sales_orders, sales_orders_extra, sales_returns, inbound_receiving_extra; services special_order_phase2/routing/items/fulfillment, qc_service, custom_role_service; dependencies permission matrix dan entity context. Review ini tidak menggantikan audit keseluruhan backend.

Yang belum bisa ditutup: seluruh perilaku visual/responsif, seluruh kombinasi role/grant/scope, operasi offline, file gagal setelah sebagian terunggah, semua transisi antarlayar setelah multiitem, dan rekonsiliasi invoice/AR hasil konversi. Rantai multiitem harus menjadi tes integrasi prioritas setelah perbaikan.

## Bukti yang dapat diulang

- `verify-controls.cjs` — mengambil fungsi aktual dari AST JSX, membuktikan error settlement dan race respons; juga menghasilkan inventaris kontrol.
- `callback-evidence.json` — hasil callback aktual, dengan batas metode.
- `verify-multi-item.py` — fungsi pricing aktual memakai fixture baca deterministik dan ekspresi payload konversi asli. Tidak memakai Mongo/HTTP sebagai bukti final.
- `multi-item-evidence.json` — angka harga/qty dan item konversi aktual.

Semua harness hanya membuat artefak audit. Tidak ada patch aplikasi atau push repo.

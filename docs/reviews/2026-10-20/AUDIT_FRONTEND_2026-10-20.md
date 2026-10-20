# Audit frontend, tombol, form dan hubungan API

**ERP Kain Nussantara — PT Kubus Teknologi Indonesia**  
Tanggal pemeriksaan: **20 Oktober 2026**  
Commit terbaru yang diperiksa: **`8dab383f764df80737bfe02f887422b3fd72aa70`**  
Baseline sebelumnya: `63c38bd11b49ddfb59cbbfdb915c2e11e16d5c9c`.

## Kesimpulan

**Frontend belum dapat dinyatakan lengkap dan benar.** Ada tombol yang hilang bagi pengguna berizin, pilihan form yang tidak mengubah nilai, navigasi yang salah, kegagalan yang tidak terlihat, serta satu rantai Special Order multi-produk yang menghasilkan SO dengan item/kuantitas tidak sesuai.

Laporan ini mengonsolidasikan **13 kelompok temuan**. Beberapa laporan domain menyebut masalah role pada beberapa layar secara terpisah; di sini akar masalah yang sama dikelompokkan agar jumlah temuan tidak membengkak. Ini tambahan audit frontend, bukan penutupan seluruh audit ERP atau sertifikasi bahwa semua tombol sudah dicoba melalui browser.

Seluruh temuan di bawah diperiksa kembali terhadap commit terbaru. Perubahan menu Retur pada main memang ada; laporan lama tentang menu custom role Interco yang hanya berisi Profil Saya sudah dikoreksi. Pada commit terbaru role tersebut memperoleh Retur Antar-PT dan Profil Saya, tetapi pintu transaksi utama masih hilang.

## Cakupan dan jenis bukti

| Pemeriksaan | Hasil | Arti dan batas |
|---|---|---|
| Parsing/inventaris source frontend | 953 berkas JS/JSX/TS/TSX; tidak ada error parse | Mencakup komponen, konfigurasi, utilitas dan hook. Bukan 953 halaman yang diuji melalui browser. |
| Inventaris elemen | 4.202 elemen: 2.847 button, 21 Button, 1.124 input, 140 textarea, 18 select, 44 link, 8 form | Hitungan statis kategori tersebut; elemen yang dirender berulang dan komponen kontrol khusus tidak setara satu banding satu dengan jumlah ini. Bukan hitungan tes lulus. |
| Navigasi/role | 151 ID renderer; 13 role bawaan, 31 variasi custom role satu modul, dan satu variasi semua modul dievaluasi | Fungsi konfigurasi asli dievaluasi. Semua target menu bawaan mempunyai renderer setelah alias sah diperhitungkan. Pintu menu custom role dan tautan antrean tetap memiliki masalah. |
| Render tombol dan formatter | 15 kasus pada lima komponen role + 18 kasus WMS/Finance; dijalankan ulang dari source commit terbaru | React/JSX asli dengan state/dependensi terkontrol. Bukan seluruh klik browser dan bukan seluruh transaksi. |
| Kontrak panggilan HTTP | 1.662 lokasi panggilan diinventaris; 1.596 bentuk method/path cocok, 21 dinamis berpotensi cocok, 45 memerlukan konteks helper | Tambahan 92 kombinasi dinamis ditelusuri dan mempunyai route/method. Tidak ada mismatch method/path baru yang terkonfirmasi. Route tersedia tidak membuktikan payload, izin atau prosesnya benar. |
| HTTP backend versi terbaru | Reproduksi konversi multi-item, akses Data Gudang, dan batas pemilih SO retur | Backend commit terbaru pada port 8020; database khusus `kn_frontend_audit_20261020`, hasil salinan fixture audit sintetis. |
| Build produksi terbaru | Berhasil, exit 0, dengan warning | Memakai cache dependensi yang tersedia, bukan instalasi bersih lockfile. Source dan output build berada pada snapshot 20 Oktober terpisah dari snapshot lama. |
| Browser terbaru | Login Admin/Admin Gudang/Manager; pilihan buyer transaksi dan payee settlement; Data Gudang; tautan Harga Khusus | Empat observasi kegagalan pada tiga FE-ID dibuktikan langsung dan difoto. Memakai proxy uji satu origin; seluruh tombol/role/flow belum dicoba. |

Kandidat native button tanpa handler yang ditemukan pada `AskKnButton` **dikeluarkan**: tombol tersebut merupakan anak `DropdownMenuTrigger`, sehingga handler berasal dari komponen induk. Kandidat custom-admin RFID juga dikeluarkan karena sistem memang melarang Admin sebagai role acuan. Temuan tidak dibuat hanya dari pencarian teks atau nama tombol.

Build terbaru semula dibuka pada port 3020. Login browser langsung gagal sementara HTTP backend 8020 dan preflight berhasil. Kendala koneksi diatasi untuk pengujian dengan server harness satu origin pada port 3021: `/api` diteruskan ke backend 8020 dan hanya base URL API dalam JS yang disajikan diadaptasi di memori. Kode bisnis/UI dan file build di disk tidak diubah. Melalui lingkungan ini login Admin, Admin Gudang dan Manager berhasil, dan beberapa temuan dicoba langsung. Ini bukan bukti konfigurasi jaringan deployment produksi telah diuji.

## Temuan prioritas

| ID konsolidasi | Prioritas | Masalah | Bukti utama |
|---|---|---|---|
| FE-01 | P1 | Special Order dua produk berubah menjadi SO satu produk dan qty salah | HTTP terbaru + source pricing/konversi |
| FE-02 | P1 | Sembilan pilihan Interco tidak memperbarui nilai form | Eksekusi callback JSX asli + scan kontrak KNSelect |
| FE-03 | P1 | Katalog akses tidak mengikuti induk menu/hub terbaru | Evaluasi konfigurasi navigasi asli |
| FE-04 | P2 | Banyak tombol dan pilihan petugas mengikuti nama role, bukan izin efektif | Render JSX + pencocokan izin backend |
| FE-05 | P2 | Data Gudang menolak Admin Gudang yang mempunyai izin warehouse | HTTP terbaru 403 + source pemanggil |
| FE-06 | P2 | Harga Khusus dari Meja Saya menuju view yang tidak dirender | Evaluasi resolver navigasi asli |
| FE-07 | P2 | Error aksi retur tersembunyi; modal penyelesaian menutup saat gagal | Eksekusi callback asli dengan penolakan disimulasikan |
| FE-08 | P2 | Respons SO lama menimpa isi form retur setelah pilihan SO berubah | Simulasi urutan respons pada callback asli |
| FE-09 | P2 | Pemilih SO retur hanya menjangkau 200 SO terbaru | HTTP terbaru dengan 202 fixture sementara |
| FE-10 | P2 | Antrean QC memberi label meter pada qty unit dasar dan mencampur total | Trace sumber data dan JSX |
| FE-11 | P2 | Error pertama penerimaan transfer menjadi loading tanpa akhir | Render JSX dengan data kosong dan error terisi |
| FE-12 | P2 | Neraca berstatus Seimbang ketika hasil belum diketahui | Render formatter/KPI asli |
| FE-13 | P2 | Tooltip defisit posisi kas mengubah angka negatif menjadi positif | Formatter asli dengan saldo negatif |

### FE-01 — Multi-produk tidak utuh sampai menjadi SO

**Alur pengguna:** Penjualan → Pesanan Khusus → buat dua item → proses R&D/keputusan item → harga → konversi menjadi SO.

Form sudah menerima lebih dari satu item. Pengadaan juga mempunyai rute per item. Namun, pricing dan payload konversi masih menggunakan satu pemenang/header legacy: `custom_item.quantity`, satu produk hasil dan satu harga.

**Reproduksi pada API terbaru:** Special Order dibuat dengan A 100 yard dan B 200 yard. Setelah fixture hasil R&D/keputusan siap dimasukkan, preview harga memakai B sebanyak 100 yard. Dengan biaya A=10, B=30 dan margin 30%, total dua item pada aturan margin yang sama seharusnya 9.100 sebelum pajak; preview menjadi 3.900. Lock harga dan konversi berhasil HTTP 200. SO `KSC/SO-00039` yang dibuat hanya mempunyai **B 100 yard**, status `waiting_stock`, dengan grand total 4.329 setelah pajak. A hilang dan kuantitas B juga salah.

**Lokasi:** `backend/services/special_order_phase2.py`, fungsi `pricing_preview` sekitar baris 273; `backend/routers/special_orders.py`, payload `SalesOrderCreate` sekitar baris 1034; `frontend/src/features/sales/SpecialOrderPricingPanel.jsx:73`.

**Dampak:** ringkasan harga, konversi pesanan dan kebutuhan pemenuhan tidak lagi mewakili permintaan customer. Pengujian ini belum mem-posting pembayaran/AR atau mengirim barang; jangan mengklaim nilai kerugian produksi sudah terjadi.

**Perbaikan dan selesai jika:** harga, produk hasil, qty/unit, persetujuan harga dan hubungan pengadaan disimpan per item stabil. Konversi harus membawa seluruh item yang sah, menghitung total/pajak dari rincian tersebut, dan tidak melebur dua produk menjadi header legacy. Retry tidak membuat SO ganda. Uji A100+B200 sampai SO, alokasi, invoice/AR dan pengiriman; tambahkan perbedaan satuan, pembatalan satu item dan perubahan harga per item.

**Bukti:** `frontend-sales-rnd/multi-item-http-latest-evidence.json`. Fixture R&D/ready disiapkan langsung; ini bukti nyata lapisan pricing/konversi, bukan UAT proses desain sampai akhir. Fixture milik pengujian telah dibersihkan, tidak ada pembayaran dibuat.

### FE-02 — Form Interco tidak menyimpan pilihan

**Alur:** Akuntansi & Pajak → Antar Entitas (Grup) → transaksi baru atau Settlement.

`KNSelect` menerima callback **`onValueChange`**, tetapi pemanggil memakai **`onChange`** pada sembilan lokasi. Pilihan dapat dibuka, tetapi callback perubahan state tidak dipanggil. Saat buyer/payee kosong, form tidak dapat dilengkapi; mode harga, mode PPN, produk dan filter juga tidak berubah sesuai pilihan.

**Lokasi:** `frontend/src/components/KNSelect.jsx:149,189`; `finance/interco/IntercoCreateModal.jsx:109,112,115,118,137`; `IntercoPanels.jsx:32`; `IntercoSettlementModal.jsx:107,111,115`.

**Bukti kode:** callback pilihan dari JSX asli dijalankan dan menghasilkan `stateUpdates=[]`; seluruh source penyebab identik pada main terbaru. `frontend-wms-finance/select-contract-results.json` dan `render-results-8dab.json`.

**Bukti browser terbaru:** Admin membuka Transaksi Baru, memilih Kanda Fabric pada PT Pembeli, tetapi field kembali ke **Pilih...**. Pada Buat Settlement, memilih Kanda Fabric sebagai PT Penerima juga kembali ke Pilih..., dan tombol Terbitkan Settlement tetap disabled. Tidak ada transaksi atau pembayaran diterbitkan. Screenshot: `evidence/frontend-20261020/interco-buyer-browser.jpg` dan `interco-settlement-browser.jpg`; catatan `browser-observations.json`.

**Perbaikan dan selesai jika:** gunakan kontrak callback yang sama di seluruh pemanggil, lalu uji pilihan melalui komponen sampai payload yang dikirim. Jangan menyelesaikannya dengan melewati field wajib. Uji transaksi manual, settlement dari tombol utama tanpa preset, settlement dari pasangan tertentu, pilihan produk dan filter per sisi.

### FE-03 — Hak modul tidak menghasilkan menu yang dapat dipakai

**Alur:** Pengaturan → Badan Usaha & Akses → Peran & Hak Akses → role kustom tanpa acuan → aktifkan satu modul Kelola penuh.

Katalog modul backend tertinggal dari struktur induk menu frontend. Evaluasi fungsi navigasi asli pada main terbaru menghasilkan:

- Interco penuh: Retur Antar-PT dan Profil Saya, tetapi tidak ada transaksi utama Interco.
- Accounting penuh: Aset Tetap dan Profil Saya; Buku Besar, laporan dan tutup buku tidak muncul melalui menu.
- Warehouse Ops penuh: sebagian operasi tersedia, tetapi tab Barang Masuk/Keluar dan hub RFID tidak tersedia.

**Lokasi:** `backend/access_modules.py:56,74,111,210`, `frontend/src/config/navStructure.js`, `navigationConfig.js` dan builder role/menu.

**Perbaikan dan selesai jika:** peta modul, menu induk, tab dan aktivitas memiliki kontrak yang konsisten. Menu induk tersedia bila ada anak sah, tetapi tidak membuka anak yang tidak berizin. Preview role harus sama dengan menu akun sebenarnya. Uji role tanpa acuan, role turunan, pembatasan tab dan scope lokasi/entitas.

**Bukti:** `frontend-access-navigation/latest-8dab/` serta addendum `latest-8dab.md`. Tidak ada klaim API menjadi bocor; masalahnya pengguna berizin kehilangan pintu kerja.

### FE-04 — Tombol dan daftar petugas masih bergantung nama role

Masalah muncul di beberapa domain dan digabungkan sebagai satu kelompok akar penyebab:

| Contoh aksi | Kondisi yang salah | Acuan source |
|---|---|---|
| Buat Pesanan Khusus | Role kustom berizin `order.create` tidak mendapat tombol; Manager view-only masih melihatnya | `sales/SpecialOrders.jsx:118` |
| Buat/tugaskan/putus inspeksi | Nama role membatasi tombol dan daftar petugas | `inspections/InspectionsView.jsx:73`, `InspectionDetailPanel.jsx`, `backend/routers/inspections.py:58` |
| Buat/review/count GRN | Daftar role literal mengabaikan izin aksi rinci | `wms/grn/GoodsReceiptsView.jsx:14`, `GrnDetail.jsx:12` |
| Setujui/tolak transfer | Hanya literal manager; Admin yang diizinkan API kehilangan tombol | `wms/transfer/TransferDetailModal.jsx:219` |
| Keputusan selisih pembayaran | Finance mempunyai `payment_variance.decide`, tombol tidak muncul | `finance/payments/PaymentVarianceQueue.jsx:53`; `backend/permissions_config.py:377` |
| Struktur/exception WMS dan adjustment saldo kredit | Role turunan yang sah tidak ekuivalen dengan role acuan pada kontrol | `wms/LocationPutawayView.jsx:18,37`; `TransferReceiptPanel.jsx:13,25`; `finance/StoreCreditView.jsx:37` |
| Kelola badan usaha/akun | Sebagian tombol memakai Admin literal sementara endpoint mempunyai izin aksi | `settings/entities/EntitiesAccessView.jsx:47`, `AccountList.jsx` |

**Perbaikan dan selesai jika:** UI memakai capability/izin aksi efektif yang sama dengan backend, ditambah status proses, penugasan dan scope yang relevan. Jangan menghapus aturan approval bisnis atau membuka hak Admin melalui template yang memang dilarang. Pilihan petugas memakai akun aktif berkemampuan dan berscope sesuai tugas. Uji izin ditambah/dicabut, role turunan dan role tanpa acuan, serta Manager yang menjadi view-only.

**Bukti:** 15 render JSX terbaru pada lima komponen, tambahan render WMS/Finance dan trace izin endpoint dalam laporan domain. Tidak semua kombinasi akun/scope sudah diuji melalui browser.

### FE-05 — Admin Gudang tidak bisa membuka Data Gudang

**Alur:** login sebagai Admin Gudang → Gudang & Logistik → Data Gudang.

Halaman memakai daftar master dengan `scope=all`. Backend membatasi scope tersebut ke nama role admin/manager/warehouse, sehingga `warehouse_admin` ditolak walaupun izin efektifnya berisi warehouse view/create/update.

**Reproduksi HTTP terbaru:** login `warehouse_admin` berhasil; `/auth/me` menunjukkan tiga izin tersebut; `GET /warehouses?scope=all` menghasilkan **403**. Admin dengan permintaan yang sama mendapat 200. Akun yang digunakan akun demo lokal.

**Lokasi:** `backend/routers/warehouses.py:36,165`; `frontend/src/features/wms/warehouses/warehouseApi.js:11`; `WarehouseMasterView.jsx:58,83`.

**Perbaikan dan selesai jika:** halaman memuat gudang sesuai scope pengguna dan izin yang sah. Perbaikan bukan memberi akses semua gudang kepada setiap Admin Gudang; pembatasan lokasi/entitas tetap harus ditegakkan. Uji muat daftar, detail, create/update/delete masing-masing dan gudang di luar akses.

**Bukti:** `evidence/frontend-20261020/warehouse-role-http.json`. Browser terbaru dengan akun Admin Gudang juga menampilkan pesan penolakan yang sama, total nol dan daftar kosong walaupun menu Data Gudang tersedia. Screenshot `warehouse-admin-browser.jpg`; angka nol ini tidak boleh dibaca sebagai bukti gudang benar-benar tidak ada.

### FE-06 — Harga Khusus dari Meja Saya membuka target yang salah

Manager menerima antrean `price_approval`, lalu resolver baris mengirim `view=approvals`. Renderer hanya mempunyai `price-approvals`; tidak ada alias yang menyelesaikan target tersebut. Jadi tombol kerja dari antrean tidak membawa pengguna ke layar pengajuan yang tepat.

**Lokasi:** `frontend/src/features/sales_admin/workDeskApi.js`, peta `ROLE_DESK_TARGET` sekitar baris 217; `frontend/src/features/desks/RoleDesk.jsx:74`; `AppViewRouter.jsx`; `backend/services/role_desk_service.py:72`.

**Perbaikan dan selesai jika:** target menuju view yang sah sekaligus membawa fokus ID pengajuan. Jangan cukup membuka daftar umum tanpa memilih dokumen asal. Uji semua target resolver antrean terhadap renderer, dokumen yang sudah tidak tersedia, dan akses pengguna.

**Bukti:** evaluasi `rowLink` pada inventaris navigasi terbaru. Browser terbaru sebagai Manager juga mereproduksi Meja Saya → Permintaan harga khusus → Putuskan pada pengajuan `pra_3685381fa99d`: URL menjadi `?view=approvals&entity=ent_ksc` dan isi elemen main tetap kosong. Tidak ada keputusan harga yang dikirim. Screenshot `price-approval-deadlink-browser.jpg`.

### FE-07 — Aksi retur gagal, tetapi error tidak terlihat dan modal ditutup

Saat detail retur terbuka, `SalesReturns` melakukan early return ke `ReturnDetail`. Error aksi disimpan di state parent tetapi tidak diteruskan ke detail. Pada settlement, parent menangkap penolakan backend tanpa melemparkannya lagi. Modal menganggap `await onSettle` selesai lalu menjalankan `onClose`.

**Lokasi:** `sales/SalesReturns.jsx:163` dan cabang `if (selected)`; `sales/ReturnSettleModal.jsx:55,63`. Main baru menambahkan aksi buang draf, tetapi pola penanganan error ini tetap ada.

**Hasil reproduksi callback:** penolakan QC/evidence disimulasikan; `modal_closed=true`, error hanya berada di parent. Tidak ada klaim settlement backend berhasil atau pembayaran sudah terjadi.

**Perbaikan dan selesai jika:** tampilkan pesan pada detail/modal aktif, pertahankan input, dan tutup modal hanya setelah keberhasilan yang jelas. Terapkan pada submit, approve, inspect, reject dan settle sesuai handler. Uji validasi bisnis 400/409, izin 403, jaringan terputus dan klik ulang.

**Bukti:** `frontend-sales-rnd/callback-evidence-latest.json`.

### FE-08 — Respons terlambat menimpa SO yang baru dipilih

Di form retur, pengguna memilih SO A lalu SO B. Jika respons A datang paling akhir, callback tetap memasang baris produk A meskipun selected order B. Tidak ada pembatalan atau pemeriksaan identitas permintaan aktif.

**Lokasi:** `sales/CreateReturnForm.jsx:59`, `handleOrderChange`.

**Perbaikan dan selesai jika:** hanya respons untuk SO yang masih aktif boleh mengubah form. Reset pilihan roll/qty/bukti yang terkait SO sebelumnya. Uji A lambat→B cepat, batal form saat loading, dan error pada salah satu permintaan. Penolakan backend atas payload lintas SO tetap wajib; reproduksi ini tidak mengklaim backend menerima retur salah SO.

**Bukti:** callback race asli dalam `callback-evidence-latest.json`: selected SO-B dengan `product-A`.

### FE-09 — SO yang baru dikirim pun dapat hilang dari pemilih retur

Halaman mengambil `/sales-orders` tanpa pagination/search, lalu menyaring status eligible di browser. Endpoint nonpaged membatasi hasil pada 200 SO terbaru. Pemilih tidak menyediakan cara mengambil SO eligible yang tersingkir oleh pesanan lebih baru.

**Reproduksi HTTP terbaru:** satu SO berstatus shipped dibuat 30 menit sebelumnya, lalu 201 draft yang lebih baru ditambahkan sebagai fixture. Sumber pemilih mengembalikan 200 draft, sehingga setelah filter eligible hasilnya kosong. Pencarian paginated server dapat menemukan SO shipped yang sama. Seluruh 202 fixture dibersihkan.

**Lokasi:** `sales/SalesReturns.jsx:110`, `CreateReturnForm.jsx`; `backend/routers/sales_orders_extra.py:183`.

**Perbaikan dan selesai jika:** pemilih melakukan pencarian/pagination server terhadap SO yang sesuai scope dan mempunyai barang yang dapat diretur. Jangan menaikkan batas lalu mengunduh semua data. Uji lebih dari 200 SO, pencarian nomor/customer, partial shipment dan jumlah retur yang sudah diklaim.

**Bukti:** `evidence/frontend-20261020/return-picker-http.json`.

### FE-10 — Label dan total satuan antrean QC tidak sesuai sumber

Antrean menghitung `quarantine_qty` dari jumlah unit dasar roll, tetapi tampilan menambahkan label `m` dan form menyebut Diterima/Ditolak (m). Total dijumlahkan tanpa pemisahan unit. Bila sumber memakai yard/kg, pengguna mendapat instruksi satuan yang salah; total kg dan yard juga tidak boleh dijumlahkan sebagai meter.

**Lokasi:** `wms/QCInspection.jsx:75,142,229`; sumber `backend/routers/inbound_receiving_extra.py:93` dan `backend/services/qc_service.py:30`.

**Perbaikan dan selesai jika:** sertakan satuan eksplisit per tugas/roll dan pisahkan total menurut satuan. Tetap bedakan panjang interval mesin inspect yang selalu yard dari unit stok/penjualan knitting yang kg. Jangan melakukan konversi otomatis dengan rasio yang belum tervalidasi. Uji yard, kg dan daftar campuran. Belum ada bukti kehilangan stok akibat temuan label ini.

### FE-11 — Penerimaan transfer tampak terus memuat setelah GET gagal

`load` mengisi error ketika GET receipt gagal, tetapi data tetap null. Cabang `if (!data) return loading` berada sebelum render `ErrorNotice`, sehingga pengguna tidak melihat kegagalan atau tombol retry.

**Lokasi:** `wms/transfer/TransferReceiptPanel.jsx:31,55,101`.

**Perbaikan dan selesai jika:** state loading, error, kosong dan data dibedakan. Error pertama harus tampil dengan retry yang dapat dipakai dan konteks transfer tetap tersimpan. Uji 403, 404, timeout dan retry berhasil; jangan menyamarkan error sebagai tidak ada barang diterima.

**Bukti:** render JSX aktual dengan `data=null` dan error terisi pada `render-results-8dab.json`.

### FE-12 — Status neraca belum diketahui ditampilkan hijau Seimbang

`BalancedKpi` memakai `balanced !== false`. Nilai undefined/null, termasuk sebelum respons tersedia, menjadi true. Pemanggil meneruskan `data?.balanced`, sehingga state belum diketahui dapat tampil sebagai kesimpulan akuntansi.

**Lokasi:** `finance/FinancialStatementsParts.jsx:113,122`; `FinancialStatementsView.jsx:294`.

**Perbaikan dan selesai jika:** hanya boolean true dari hasil yang valid boleh menampilkan Seimbang; false berarti tidak seimbang; unknown/error/loading mempunyai tampilan tersendiri. Uji kegagalan API dan pergantian periode. Temuan ini mengenai representasi UI, bukan bukti bahwa kalkulasi neraca backend salah.

### FE-13 — Tooltip defisit kas menjadi angka positif

Grafik menyimpan `cumulative_cash` beserta tanda negatifnya. Namun satu formatter tooltip untuk semua seri memakai `Math.abs(v)`. Saldo kumulatif -100 ditampilkan Rp100 ketika di-hover, sehingga defisit terbaca positif meskipun posisi garis masih di bawah nol.

**Lokasi:** `finance/CashFlowForecastView.jsx:38,75`.

**Perbaikan dan selesai jika:** format berdasarkan makna seri; saldo kumulatif wajib mempertahankan tanda. Penyajian besaran arus keluar boleh mengikuti konvensi yang dijelaskan, tanpa mengubah arti saldo. Uji defisit, surplus, nol dan periode saldo berpindah tanda.

**Bukti:** formatter sumber terbaru dijalankan pada `render-results-8dab.json`.

## Pekerjaan yang masih diperlukan

1. Klik browser per role, seluruh state proses, dialog, upload/download, keyboard, ukuran layar dan kondisi jaringan belum seluruhnya dilakukan.
2. Tidak semua payload dinamis dan seluruh kombinasi permission/scope telah diuji melalui HTTP. Peta route tidak menggantikan pengujian bisnis.
3. Konversi multi-item perlu regresi sampai alokasi, invoice/AR dan pengiriman setelah diperbaiki. Reproduksi saat ini berhenti pada SO yang salah.
4. Temuan backend sebelumnya tetap memiliki baseline dan bukti sendiri; laporan ini tidak otomatis memverifikasi ulang semua 11 temuan lama pada main baru.
5. Pengujian perangkat RFID/absensi/printer fisik tetap terpisah.

## Paket bukti

- `frontend-access-navigation/latest-8dab.md`, `latest-8dab.json`, subfolder `latest-8dab/`.
- `frontend-wms-finance/latest-8dab.md`, `latest-8dab.json`, `render-results-8dab.json`, `API_ROUTE_PARITY_8DAB.md` dan inventaris route.
- `frontend-sales-rnd/ADDENDUM_MAIN_8dab_2026-10-20.md`, `findings.json`, callback terbaru dan bukti HTTP multi-item.
- `evidence/frontend-20261020/frontend-control-inventory.json`, `warehouse-role-http.json`, `return-picker-http.json`, catatan environment/build dan clone fixture.

Semua kode aplikasi dipertahankan. Perubahan hanya pada harness/bukti audit dan data uji terisolasi. Tidak ada push atau perubahan pada data produksi.

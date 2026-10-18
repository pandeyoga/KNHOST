# Memo Internal Developer - WMS

Putaway, struktur lokasi, transfer, stock opname, aturan dan visibilitas stok

**Tanggal:** 8 Oktober 2026  
**Snapshot kode:** `f59b8a60d7b7e078888c537ca93c046afae460a9`

Memo tambahan, bukan perubahan kode aplikasi. Sumber remote/deployment terbaru belum terverifikasi.


## Tujuan, cakupan dan hasil penelusuran

Memo tambahan untuk developer ini merapikan enam catatan internal dan menghubungkannya dengan kode WMS. Dokumen berisi kondisi saat ini, alur yang perlu dipertahankan, masalah terkonfirmasi dan kriteria penerimaan perbaikan.

**Catatan:** Klarifikasi pengguna: Lemari merupakan unit fisik yang berisi beberapa rak. Istilah di aplikasi boleh berbeda selama makna dan hubungannya sama. Karena itu Rack dapat dipetakan ke Lemari, Level ke Rak di dalam lemari, dan Bin ke posisi penyimpanan. Perbedaan bahasa tidak dihitung sebagai cacat.

| Poin | Kebutuhan internal | Kondisi pada snapshot yang diperiksa |
| --- | --- | --- |
| DEV-WMS-01 | Putaway dapat ditemukan dan dipakai | Kode/menu ada; pengalaman yang dilaporkan hilang belum diverifikasi pada deployment. Ada cacat lookup bin saat scan. |
| DEV-WMS-02 | Lokasi > Gudang > Zona > Lemari > Rak | Dapat direpresentasikan oleh Site > Warehouse > Zone > Rack > Level > Bin. Perlu konsistensi alamat, penjagaan perubahan dan aturan sublokasi. |
| DEV-WMS-03 | Transfer antar gudang untuk pemenuhan SO | Lifecycle transfer ada. Hubungan komitmen SO, penerimaan per roll/parsial dan rules tujuan perlu dilengkapi. |
| DEV-WMS-04 | Stock opname | Ada sesi penyesuaian qty dan sweep RFID yang hanya membuat laporan. Keduanya tidak boleh disamakan. |
| DEV-WMS-05 | Rules gudang dan lemari/rak | Shared/dedicated, peran gudang serta rules kategori ATAU grade ada. Penegakan antarjalur dan rules sublokasi belum lengkap. |
| DEV-WMS-06 | Stok per seluruh tingkat lokasi | Saldo per gudang dan okupansi per bin ada. Drill-down seluruh tingkat dan pemisahan satuan masih perlu penyelesaian. |


### Dasar validasi

Sumber lokal berasal dari snapshot repo tanggal 7 Oktober 2026, commit f59b8a60d7b7e078888c537ca93c046afae460a9. Versi terbaru GitHub/deployment tidak berhasil diverifikasi dalam sesi ini; seluruh klaim kondisi kode dibatasi pada snapshot tersebut.

Sembilan kasus fungsi dijalankan secara terisolasi: lima reproduksi cacat, tiga observasi gap kemampuan/alur, dan satu pemeriksaan kontrol hold inspeksi yang berhasil menolak penempatan. Fungsi diambil dari AST kode asli; database, autentikasi dan batas framework diganti objek dalam memori. Ini bukan pengujian HTTP aplikasi berjalan, MongoDB nyata atau perangkat RFID.

Memo ini merupakan tambahan penelusuran enam poin WMS. Kelulusan seluruh kode WMS, deployment dan perangkat tidak dinyatakan. Hasil mesin disimpan dalam wms-focused-validation.json; rincian kasus dijelaskan pada bagian temuan.


## DEV-WMS-01 - Putaway dan akses operasional


### Catatan yang dirapikan

Pastikan fitur putaway tetap tersedia, mudah ditemukan dan dapat dijalankan oleh petugas yang berwenang. Laporan bahwa putaway tidak terlihat harus ditelusuri sebagai masalah navigasi, hak akses, versi deployment atau fungsi; jangan langsung menyimpulkan kodenya dihapus.


### Kondisi kode dan navigasi

Gudang & Logistik > Lokasi Rak membuka LocationPutawayView. Halaman mempunyai tab Struktur Lokasi, Putaway, Perintah Simpan ke Rak (Antar Gedung) dan Antrean Potong. Router aplikasi masih memasang view tersebut. Admin Gudang mewarisi navigasi warehouse; custom role dapat mengubah akses. [R01-R03]

| Jalur | Makna dan efek saat ini |
| --- | --- |
| Penempatan dalam gudang | Tab Putaway > pilih gudang > pilih roll belum ditempatkan > pilih bin > Tempatkan. Mengubah bin_id dan menulis jejak; tidak menambah/mengurangi saldo gudang. |
| PA antar gedung | Tab Perintah Simpan ke Rak > saran tujuan > buat PA > Kirim > Konfirmasi Tiba/BTG. Memindahkan warehouse_id dengan pemilik tetap; setelah tiba bin_id kosong. Ini belum menempatkan roll pada rak tujuan. |
| Scan pada penerimaan | Barang Masuk > baris roll hasil scan > scan/input kode bin. Jalur ini masih membaca struktur legacy rack.bins, sehingga bin dari editor modern rack.levels[].bins tidak ditemukan. |

**Catatan:** Terminologi operasional: putaway = menempatkan/memindah alamat di gudang yang sama; transfer = mengganti gudang fisik. PA antar gedung yang sudah ada adalah perpindahan fisik, kemudian masih perlu penempatan pada rak tujuan. Nama dokumen boleh tetap PA, tetapi penjelasan dan efeknya harus tegas.

**Alur:** Roll fisik diterima > Pilih alamat valid > Validasi rules/izin > Tempatkan + jejak


### Tugas developer dan hasil yang diterima

Verifikasi menu untuk peran nyata dan custom role, hubungkan antrean dari Meja Gudang ke pekerjaan putaway, serta tampilkan jumlah siap/terhambat beserta alasan. Satukan resolver alamat untuk editor, scan dan endpoint penempatan. Pertahankan hold inspeksi; setelah PA tiba, tampilkan pekerjaan penempatan rack/bin yang masih tersisa.

Developer perlu membandingkan build/commit deployment dengan snapshot, menguji navigasi desktop/mobile yang dipakai petugas, dan merekam langkah reproduksi laporan fitur hilang. Keberadaan kode belum membuktikan layar yang dipakai pengguna berfungsi. [R02-R05]


## DEV-WMS-02 - Hierarki alamat dan penyimpanan


### Padanan istilah yang dapat dipakai

| Bahasa bisnis | Model saat ini | Hubungan/identitas |
| --- | --- | --- |
| Lokasi | warehouse_sites / site_id | Satu lokasi fisik dapat memiliki beberapa gudang. |
| Gudang | warehouses.id | Pemilik stok tetap berada pada roll; gudang menyimpan alamat fisik dan profil. |
| Zona | zones[].id | Pembagian area dalam gudang. |
| Lemari | zones[].racks[].id | Wadah fisik yang berisi beberapa rak/tingkat. |
| Rak dalam lemari | racks[].levels[].id | Rak/tingkat dalam satu lemari. |
| Posisi penyimpanan | levels[].bins[].id | Alamat akhir yang ditunjuk inventory_rolls.bin_id. Dapat satu posisi default per rak bila detail posisi belum dibutuhkan. |

Padanan ini adalah cara menerapkan klarifikasi tanpa menambah hierarki paralel. UI boleh mempertahankan istilah Rack/Level atau memakai Lemari/Rak. Yang harus sama adalah wadah, hubungan induk-anak, identitas node dan alamat roll. [R02, R04, R06]

**Alur:** Lokasi Jakarta > Gudang penyimpanan > Zona Woven > Lemari A > Rak 02 > Posisi BIN-A02


### Sumber kebenaran dan aturan perubahan

Struktur sublokasi saat ini tersimpan embedded pada warehouses.zones. Identitas barang fisik berada pada inventory_rolls; warehouse_id dan bin_id menjadi alamatnya. Saldo gudang merupakan proyeksi roll menurut produk, gudang dan pemilik. Jangan membuat tabel stok lemari/rak yang diperbarui sendiri dan dapat berbeda dari roll.

Setiap node perlu ID stabil, kode/nama, induk, status aktif dan atribut penyimpanan yang relevan. Bila kapasitas dipakai, dimensinya harus jelas: roll, berat, volume atau panjang tertentu beserta satuan. Nama dapat diedit tanpa mengganti ID. Pemindahan parent dan penghapusan harus memeriksa stok, tugas terbuka dan dokumen; stok pada alamat lama tidak boleh menghilang dari dashboard.


### Cara menentukan tujuan penempatan

Periksa berurutan: izin lokasi pengguna > gudang usable untuk pemilik > peran/routing gudang > jenis/tahap/mutu barang > aturan zona/lemari/rak/bin > kapasitas > status roll. Saran memilih alamat yang valid beserta alasan. Penempatan akhir tervalidasi kembali di server; selector saja tidak cukup.

Antarmuka menampilkan alamat lengkap, aturan yang berlaku, kapasitas dan pemakaian, isi roll serta alasan penolakan. Dalam kode saat ini pemilihan bin masih manual dan tidak mempunyai rekomendasi alamat sublokasi berdasarkan atribut produk. [R02, R04]


## DEV-WMS-03 - Transfer Bandung ke Jakarta


### Kasus bisnis

SO Sukacita Jakarta dipenuhi oleh barang di Gudang Sukacita Bandung. Barang dikirim dari Bandung, diterima di Gudang Jakarta, lalu dikirim kepada pelanggan. Nama Sukacita di sini mengikuti contoh pengguna; kesamaan badan usaha pemilik harus diperiksa dari entity_id, bukan nama gudang/kota.

**Catatan:** Jika pemilik badan usaha sama, gunakan transfer antar gudang dan pertahankan owner_entity_id, SKU, LOT, identitas roll serta dasar perolehan/HPP. Jika pemilik berbeda, proses kepemilikan/jual-beli internal tetap diperlukan; transfer fisik sendiri tidak menggantikan transaksi antar entitas.

**Alur:** Rencana SO > Reservasi transfer > Picking + staging > Kirim Bandung > Terima Jakarta > Kirim ke pelanggan


### Mekanisme yang sudah ada

Gudang & Logistik > Operasi Gudang > Stok, Transfer & Opname > Transfer > Antar gudang. Pilih gudang asal dan tujuan, produk dan roll fisik; qty/satuan mengikuti pilihan dan master. Dokumen SJ Transfer tersedia pada detail. [R07-R09]

| Tahap saat ini | Proses stok/roll |
| --- | --- |
| Buat: waiting_approval | Roll available di sumber dicadangkan dengan reserved_ref wh_transfer. Stok tidak menjadi reservasi SO secara bersamaan. |
| Approve > picking > staging | Persetujuan dan pekerjaan sebelum barang dikirim. Pemilik/gudang fisik belum berpindah. |
| Dispatched | Status roll menjadi in_transit_transfer. Keluar dari stok fisik sumber, tetap milik entitas yang sama. |
| Completed / terima | Roll pindah warehouse_id tujuan dan menjadi available; tag aktif ikut pindah, bin asal dikosongkan. Saldo sumber/tujuan dibangun ulang. |
| Setelah terima Jakarta | Tempatkan jika disimpan, atau staging untuk SO jika segera dikirim. Alokasi SO > picking/loading > shipment/SJ pelanggan mengikuti alur penjualan. |


### Gap yang harus diselesaikan

Roll yang sudah reserved untuk SO ditolak oleh transfer biasa karena transfer mensyaratkan available. Alternatif yang dapat dipakai adalah transfer sebelum alokasi SO, kemudian alokasikan setelah terima; ini perlu pengendalian operasional karena tidak menjaga komitmen SO selama perjalanan secara otomatis. Jangan melepas reservasi lewat perubahan data langsung. [P08; R09, R14]

Target pengembangan: relasi transfer ke SO/baris kebutuhan, menjaga komitmen barang tanpa reservasi ganda, penerimaan aktual per roll, parsial/selisih/rusak, dan pemeriksaan rules tujuan. Jalur status completed saat ini menerima seluruh roll yang tercatat in-transit tanpa payload roll hasil penerimaan. [R09-R10]


## DEV-WMS-04 - Stock opname dan tindak lanjut

| Jalur | Navigasi dan hasil |
| --- | --- |
| Opname kuantitas | Operasi Gudang > Stok, Transfer & Opname > Stock Opname. Sesi produk/pemilik/gudang/bin; setelah hitung, submit dan approve, selisih dapat menyesuaikan roll, saldo dan jurnal. |
| Sweep RFID | Gudang & Logistik > RFID > Lokasi RFID > Stock Opname (RFID). Expected tag aktif roll fisik dibanding scan handheld: ditemukan, missing, extra/salah lokasi dan tanpa tag. Hasil laporan; tidak langsung menambah/mengurangi qty. |

**Alur:** Tentukan scope > Snapshot expected > Hitung fisik > Submit selisih > Review/approve > Terapkan + jejak


### Proses sistem pada sesi kuantitas

Buat sesi di gudang yang boleh dipakai. Tambah item produk/pemilik dan bin bila perlu; expected dihitung dari roll berstatus fisik pada scope yang sama. Masukkan actual_qty dalam satuan dasar produk, lalu submit. Sistem menyimpan selisih actual minus expected. Saat approve, stok yang berubah sejak snapshot ditolak untuk hitung ulang. [R11-R12]

Selisih kurang mengurangi kuantitas roll dengan urutan status yang ditetapkan layanan; reservasi/picking yang terdampak dicatat dan dapat memicu notifikasi. Selisih lebih membuat roll penyesuaian dan memakai biaya acuan/WAC yang tersedia; biaya nol memerlukan alasan. Penyesuaian serta jurnal ditelusuri per baris, termasuk exception yang belum tertutup. Kebijakan akun/valuasi tetap perlu disepakati Finance; memo tidak mengesahkan kebijakan akuntansinya.


### Hal yang perlu dilengkapi developer

Pilih bin lewat tree/scan alamat, bukan mengetik ID mentah. Scope dapat dipilih dari zona/lemari/rak, tetapi harus diterjemahkan menjadi kumpulan bin dan owner yang tidak bertumpang tindih. Pertahankan larangan menghitung produk/pemilik yang sama pada level gudang dan bin dalam sesi yang sama.

Bedakan kehilangan satu roll, salah lokasi, selisih ukuran dan kesalahan master/konversi. Model koreksi agregat saat ini tidak meminta daftar roll fisik aktual; surplus dapat menjadi satu roll penyesuaian walaupun fisik yang ditemukan terdiri dari beberapa roll. Setelah koreksi, identitas roll/tag, lokasi, LOT dan ukuran harus ditinjau. Jangan menyamakan 100% tag terbaca dengan 100% ukuran barang akurat.

**Catatan:** Jika hanya salah rak/bin dan total barang tetap sama, lakukan koreksi alamat berjejak; tidak perlu menulis rugi/lebih persediaan sebagai seolah-olah barang hilang. Jika stok berubah saat proses hitung, gunakan hitung ulang/cutoff yang disepakati. Integrasi hasil RFID ke kasus opname perlu referensi yang jelas, bukan dua penyesuaian atas selisih yang sama.

Kriteria selesai: tidak ada perubahan stok sebelum approve kuantitas, retry tidak menggandakan penyesuaian/jurnal, hasil RFID simulasi dibedakan dari scan nyata, reservasi SO terdampak ditindaklanjuti, dan jumlah/identitas roll setelah penyesuaian cocok dengan fisik. [R11-R13]


## DEV-WMS-05 - Rules gudang dan sublokasi


### Pisahkan tiga dimensi konfigurasi

| Dimensi | Dukungan saat ini | Makna |
| --- | --- | --- |
| Hak pemakaian | sharing_mode shared / dedicated + entity_ids | Shared dapat menyimpan stok beberapa entitas. Dedicated membatasi entitas yang boleh menggunakan gudang; dapat dikonfigurasi hanya satu. |
| Fungsi fisik | roles transit, storage, return, staging, central_inbound | Transit adalah fungsi gudang; tidak sama dengan shared. Gudang transit bisa shared ataupun dedicated. |
| Kelayakan barang | storage_rules mode none / category / grade | Saat ini kategori ATAU grade diperiksa pada jalur PA. Belum model aturan multiatribut per zona/lemari/rak/bin. |

Profil tersedia di Data Gudang: mode pemakaian entitas serta Profil Gedung untuk site/peran/rules/gate. Identitas gudang, lokasi fisik, fungsi transit/penyimpanan dan pemilik barang harus tetap berbeda. [R06, R15-R16]


### Contoh aturan yang perlu dapat dinyatakan

Gudang penyimpanan shared menerima roll milik entitas yang diizinkan; dedicated satu entitas menolak pemilik lain. Woven only harus merujuk fabric_type woven atau klasifikasi master yang memang disepakati bermakna woven, bukan mengandalkan nama kategori bebas. Printing sebagai lini/proses tidak otomatis menggantikan jenis kain.

Zona, lemari, rak dan bin menyimpan referensi klasifikasi produk yang diperbolehkan, tahap bahan, grade/mutu bila diperlukan, status khusus dan kapasitas. Pilihan harus memakai ID/enum stabil. Jika nama supplier/artikel ikut aturan, gunakan relasi master dan tampilkan alasannya; jangan membuat nama alias menjadi identitas aturan yang berdiri sendiri.


### Evaluasi dan penegakan yang dituju

Rekomendasi pewarisan: aturan anak dapat mempersempit aturan induk; seluruh larangan/hard constraint yang berlaku harus terpenuhi. Rule kategori + grade menggunakan AND bila keduanya diwajibkan, bukan diam-diam memilih satu. Soft recommendation/prioritas penempatan dipisahkan dari larangan. Pengecualian memerlukan izin, alasan dan jejak sesuai kebijakan.

Satu evaluator dipakai oleh saran, penempatan manual/scan, PA antar gedung, transfer kirim/terima dan jalur penerimaan atau retur yang menaruh barang. Evaluasi ulang pada aksi akhir karena rules/kapasitas dapat berubah. Periksa juga gudang aktif, owner, scope lokasi petugas, status kualitas dan komitmen roll.

**Catatan:** Dua ketidaksamaan jalur sudah terlihat: transfer biasa memeriksa shared/dedicated tetapi tidak menjalankan storage_rules tujuan; PA memeriksa storage_rules tetapi create_order belum memeriksa dedicated tujuan terhadap pemilik roll. Dukungan konfigurasi tidak sama dengan penegakan yang konsisten. [P06; R05, R09, R15-R16]


## DEV-WMS-06 - Dashboard stok per alamat


### Tampilan yang dituju

WMS dapat menampilkan stok dari Lokasi > Gudang > Zona > Lemari > Rak, lalu membuka isi roll/bin. Setiap angka ringkasan dapat diklik ke rincian yang membentuknya, dengan filter owner, artikel/warna, tahap, status dan satuan yang sama. Ini melanjutkan memo meja pengguna serta visibilitas Gudang per lokasi.

| Tingkat | Informasi minimum dan aksi drill-down |
| --- | --- |
| Lokasi / site | Daftar gudang, stok fisik menurut satuan, jumlah roll, belum ditempatkan dan pekerjaan transfer/putaway. Klik membuka gudang. |
| Gudang | Pemilik, available, reserved/committed, QC/hold dan fisik total; transit/incoming terpisah. Klik membuka zona. |
| Zona / lemari / rak | Agregat hanya bin anak yang sah, qty per satuan/status, roll, kapasitas, aturan efektif serta pekerjaan tersisa. Klik membuka tingkat berikutnya. |
| Bin / isi roll | Kode/alamat, SKU, LOT, grade, ukuran aktual, status, owner dan referensi kebutuhan/perpindahan sesuai izin. |
| Belum valid alamatnya | Belum ditempatkan dan orphan/invalid-bin ditampilkan terpisah agar barang tidak hilang dari laporan. |


### Kondisi saat ini dan sumber data

Layar Stok mempunyai saldo per produk/gudang/pemilik dan daftar roll. Lokasi Rak mempunyai kapasitas, terisi, belum ditempatkan dan kartu okupansi per bin. warehouse_locations memberi data bin, total kapasitas/terisi dan unassigned; belum memberi ringkasan stok berjenjang lengkap untuk semua node. [R02, R04, R17]

Stok fisik per alamat dihitung dari inventory_rolls dengan warehouse_id, owner_entity_id, bin_id, status fisik dan length_remaining dalam unit produknya. Angka gudang mengikuti proyeksi roll yang sama; roll in-transit, shipment keluar dan WIP di luar lokasi tidak boleh dihitung sebagai fisik di rak. Incoming/ATP adalah informasi kebutuhan/pipeline, bukan barang yang sudah menempati bin.

**Catatan:** Contoh wajib: 100 meter + 100 kg ditampilkan sebagai dua subtotal, bukan 200 meter. Jumlah roll boleh ditotal sebagai unit fisik dengan pengelompokan yang jelas. Yard-meter dapat dikonversi hanya dengan basis sah dan jejak konversi; kg-panjang tidak dapat dicampur tanpa spesifikasi konversi.


### Kapasitas dan rekonsiliasi

Bedakan kapasitas fisik dengan qty transaksi. Pada gudang shared, kapasitas fisik diukur atas seluruh isi yang sah, bukan hanya owner yang sedang difilter. Jika pengguna tidak berhak melihat isi entitas lain, tampilkan informasi kapasitas yang diizinkan tanpa membuka rinciannya.

Rekonsiliasi: jumlah fisik per bin sah + belum ditempatkan + orphan harus sama dengan fisik gudang pada scope dan satuan yang sama. Induk adalah agregat anak, bukan counter stok terpisah. Perubahan penempatan/transfer/opname menyegarkan ringkasan dan detail; hasil paginasi tidak boleh dipakai sebagai total seluruh lokasi.


## Cacat terkonfirmasi - lookup dan data lokasi

ID DEV-F di bawah adalah ID memo internal untuk triase, bukan pengganti ID gelombang audit lama. Developer perlu mengecek hubungan temuan sebelum membuat tiket duplikat.


### DEV-F01 - Scan penerimaan menolak bin dari struktur modern

**Kategori:** Cacat fungsional - prioritas tinggi  
**Rujukan:** R04, R18

**Bukti.** P01: flatten_bins menemukan satu bin pada rack.levels[].bins, tetapi putaway_scanned_roll dengan BIN-01 memberi HTTPException 400: bin tidak ada di master. Lookup endpoint hanya mengiterasi rack.bins.

**Dampak.** Alamat yang dibuat melalui editor dapat tidak dipakai saat scan penerimaan. Pengguna dapat menilai putaway hilang/tidak berfungsi walau menu dan kode masih ada; ini belum membuktikan penyebab deployment yang dilaporkan.

**Perbaikan.** Pakai resolver alamat bersama yang membaca skema modern dan legacy. Cocokkan kode/ID di gudang yang benar; pakai validasi penempatan konsisten. Uji bin tingkat baru serta bin legacy.


### DEV-F02 - Menghapus struktur berisi stok menghilangkan qty dari dashboard

**Kategori:** Cacat integritas referensi - prioritas tinggi  
**Rujukan:** R04

**Bukti.** P02: roll 100 meter berada di bin-1. save_warehouse_structure menerima zones=[] tanpa menolak; roll masih 100 dan bin_id masih bin-1, tetapi total_occupied=0 dan unassigned=0.

**Dampak.** Stock tidak terhapus dari roll, tetapi terlepas dari master alamat. Dashboard lokasi dapat memberi kesan barang tidak ada, dan antrean unassigned tidak memunculkan roll tersebut.

**Perbaikan.** Tolak hapus node yang berisi stok/tugas aktif, atau lakukan migrasi alamat berjejak sesuai otorisasi. Sediakan kelompok orphan untuk bin_id yang tidak lagi ditemukan; validasi ID unik dan relasi parent sebelum menyimpan.


### DEV-F03 - Okupansi menjumlahkan unit berbeda lalu dilabeli meter

**Kategori:** Cacat kalkulasi/presentasi - prioritas tinggi  
**Rujukan:** R02, R04

**Bukti.** P03: dua roll di bin yang sama, 100 meter dan 100 kg, menghasilkan occupied=200 serta utilization=400% untuk capacity=50. UI LocationPutawayView memberi label m. Query okupansi tidak membawa unit dan agregat tidak memisahkannya.

**Dampak.** Qty terlihat numerik benar sebagai penjumlahan dua angka, tetapi maknanya salah. Utilisasi tidak sah jika kapasitas dan unit campuran tidak berdimensi sama.

**Perbaikan.** Agregasikan qty per unit/jenis ukuran, gunakan definisi kapasitas yang jelas dan hitung utilisasi pada basis yang sesuai. UI menerima metadata satuan, tidak menempel label meter tetap.

**Catatan:** Hubungan audit lama: D4-PA-03 memperbaiki total pada PutawayOrdersPanel/PA; lokasi-bin memakai consumer lain yang masih bermasalah. D4-WMS-03 mengenai pembacaan struktur di reporting; lookup scan penerimaan juga consumer berbeda. Jangan menandai seluruh pola sudah selesai hanya karena satu layar/layanan diperbaiki.


## Cacat terkonfirmasi - penempatan dan PA


### DEV-F04 - Penempatan bin menerima roll yang masih dalam perjalanan

**Kategori:** Cacat validasi state - prioritas tinggi  
**Rujukan:** R04, R19

**Bukti.** P05: putaway_roll menerima roll berstatus in_transit_transfer dan mengisi bin_id. Fungsi memeriksa inspection.hold serta keberadaan bin dalam warehouse_id roll, tetapi tidak membatasi status pada barang yang benar-benar ada di lokasi.

**Dampak.** Alamat fisik dapat tercatat seolah-olah barang telah ditaruh di rak sumber padahal masih berjalan. Aksi langsung dan antrean putaway dapat mempunyai aturan kelayakan berbeda.

**Perbaikan.** Tetapkan matriks status/jenis area yang sah. Untuk penempatan stok fisik, tolak transit/offsite/consumed; barang QC hanya boleh ditempatkan di area yang diizinkan SOP. Validasi komitmen perpindahan, owner dan cakupan lokasi pada aksi, bukan hanya pada daftar.


### DEV-F05 - PA dapat dibuat menuju gudang dedicated entitas lain

**Kategori:** Cacat penegakan aturan gudang - prioritas tinggi  
**Rujukan:** R05, R15

**Bukti.** P06: roll milik ent-a yang terverifikasi berhasil dibuatkan PA open ke wh-b dengan sharing_mode dedicated dan entity_ids=[ent-b]. create_order memeriksa scope pemilik roll dan storage_rules, tetapi tidak menjalankan assert_usable tujuan bagi pemilik roll.

**Dampak.** PA dapat menawarkan/menerima tujuan yang bertentangan dengan konfigurasi dedicated. Transfer biasa mempunyai pemeriksaan ini, sehingga dua jalur perpindahan tidak memberi hasil konsisten.

**Perbaikan.** Filter kandidat memakai pemilik roll dan mode gudang; validasi kedua gudang pada create, dispatch/arrival yang relevan dan exception acceptance. Evaluator rules yang sama harus dipakai seluruh jalur perpindahan.


### Kontrol existing yang harus dipertahankan

C01: roll dengan inspection.hold.held=True ditolak putaway_roll dengan status 400. Pagar ini teruji pada fungsi yang dipanggil. Perbaikan resolver lokasi dan rules tidak boleh menghapus kontrol tersebut.

PA saat ini juga mempunyai pemeriksaan status available, komitmen panjang, active_movement dan identitas tag pada create/dispatch. Arrival dapat menghasilkan exception serta BTG untuk roll yang benar-benar dinyatakan tiba. Dukungan yang sudah ada perlu diperluas secara konsisten ke jalur lain, bukan dibuang saat menata istilah. [R05]


### Batas kekuatan bukti

Reproduksi menunjukkan perilaku fungsi kode asli untuk data uji yang ditentukan. Auth/context dan database diganti boundary doubles. Validasi deployment perlu menjalankan API/UI dengan MongoDB nyata, concurrency, failure recovery, printer/handheld/gate serta peran lokasi. Tidak ada data produksi yang diubah dalam pemeriksaan ini.


## Gap kemampuan dan rantai proses

| ID | Bukti/kondisi | Kebutuhan penyelesaian |
| --- | --- | --- |
| DEV-G01 | P04: roll 100 dapat ditempatkan ke bin kapasitas 50. Kapasitas saat ini menjadi informasi; tidak ada validasi pada putaway_roll. | Tetapkan dimensi kapasitas dan kebijakan hard-block/soft-warning; enforce seluruh jalur penempatan. Ini gap aturan, bukan asumsi bahwa semua kapasitas wajib hard-block. |
| DEV-G02 | P07: mode category dengan Woven dan grades=[A] tetap menerima BS. Branch elif memeriksa satu dimensi. Subnode editor hanya nama/kode/kapasitas. | Model rules multiatribut, referensi master stabil, pewarisan induk-anak serta atribut lemari/rak/bin. Kategori AND grade jika diwajibkan; nilai anak tidak boleh membuka larangan induk. |
| DEV-G03 | P08: roll reserved untuk SO ditolak transfer biasa 409. SO-reservation dan wh_transfer adalah dua tujuan komitmen terpisah. | Rencana fulfillment lintas gudang dengan relasi SO/baris kebutuhan dan pemindahan fisik yang menjaga komitmen. Tidak menjadikan stok bebas bagi SO lain atau reservasi dua kali. |
| DEV-G04 | Penelusuran create_transfer dan receive_wh_transfer_rolls: shared/dedicated diperiksa, tetapi storage_rules tujuan tidak dipanggil. | Gudang Woven only harus diuji terhadap barang yang akan diterima lewat transfer, bukan hanya PA. Evaluasi ulang sebelum posting penerimaan. |
| DEV-G05 | TransferStatusUpdate hanya status/updated_by. completed memanggil receive untuk seluruh roll in-transit milik transfer; tidak memuat actual roll receipt. | Penerimaan per roll, scan/bukti, parsial, roll salah/hilang/rusak dan exception. Jangan mengaku semuanya tiba hanya karena status dokumen diubah. |
| DEV-G06 | Saldo gudang dan okupansi bin ada; warehouse_locations belum menyediakan ringkasan semua node dan daftar orphan. | Drill-down stok per site/gudang/zona/lemari/rak dengan per-unit/status/owner serta rekonsiliasi anak-induk. |

DEV-G01 sampai DEV-G03 diamati dalam probe terisolasi. DEV-G04 sampai DEV-G06 merupakan hasil penelusuran kontrak/flow kode; belum diuji sebagai skenario HTTP/UI lengkap. Rujukan: G01 R04; G02 R02/R16; G03 R09/R14; G04 R09; G05 R09/R10; G06 R02/R04/R17.

**Catatan:** Tambahan pada opname: input agregat dan koreksi surplus belum cukup untuk membuktikan identitas/jumlah seluruh roll fisik. Lengkapi hasil hitung per roll atau review penyesuaian identitas, lalu cetak/verifikasi tag bila dibutuhkan. Ini dicatat sebagai kebutuhan DEV-WMS-04, bukan reproduksi cacat baru pada sesi ini.


## Urutan kerja dan definisi selesai

| Fase | Pekerjaan | Hasil yang perlu divalidasi |
| --- | --- | --- |
| A - Alamat dan state | Satukan resolver lokasi; jaga ID/parent dan penghapusan; tampilkan orphan; matriks status putaway; pastikan menu/role. | F01/F02/F04 selesai. Penempatan tidak mengganti saldo/owner dan kontrol hold tetap berjalan. |
| B - Rules dan ukuran | Evaluator rules bersama; dedicated pada PA; aturan subnode; kapasitas berdimensi; subtotal unit; jelaskan istilah UI. | F03/F05 dan G01/G02/G04 selesai. Saran dan validasi aksi akhir memberi keputusan yang sama. |
| C - Transfer untuk SO | Hubungkan kebutuhan SO dengan transfer; jaga komitmen selama jalan; penerimaan aktual/parsial; lanjut staging/shipment pelanggan. | G03/G05 selesai. Satu barang tidak siap dijual dua kali; owner/LOT/tag benar; SJ transfer dan SJ pelanggan sesuai rantai. |
| D - Opname dan dashboard | Scope tree/scan, review selisih roll/RFID, dampak reservasi/jurnal; agregat seluruh tingkat, detail dan rekonsiliasi. | DEV-WMS-04 dan G06 selesai. Semua angka bisa ditelusuri dan cocok pada scope/satuan yang sama. |


### Format bukti yang diserahkan agent development

Gunakan ID DEV-WMS/DEV-F/DEV-G sebagai referensi. Untuk setiap pekerjaan, catat commit, perubahan kontrak data, layar terdampak, migrasi/backfill, skenario regresi, hasil uji dan keterbatasan. Status berurutan: todo > in_progress > implemented_pending_validation > validated. Klaim implemented saja tidak menutup temuan.

Tutup pekerjaan setelah uji fungsi, API, integrasi database dan UI yang relevan lulus. Perubahan scope lokasi dan rules harus diuji dengan peran gudang Jakarta/Bandung, multi-owner shared dan dedicated. Perubahan stok wajib mencakup retry, duplikasi aksi, kegagalan di tengah dan rekonsiliasi saldo/roll/jurnal yang terdampak.


### Konfigurasi/SOP yang perlu diputuskan

| Topik | Keputusan yang dibutuhkan |
| --- | --- |
| Kapasitas dan rules | Dimensi kapasitas; hard/soft; atribut barang wajib; kombinasi/pewarisan dan otorisasi pengecualian. |
| Transfer untuk SO | Gudang fulfillment yang dituju; komitmen selama perjalanan; penerimaan parsial/rusak/hilang; PIC dan bukti serah terima. |
| Opname | Cutoff atau count saat transaksi berjalan; siapa menghitung/menyetujui; standar koreksi per roll, tag dan valuasi selisih. |
| Hak lokasi | Petugas yang ditugaskan per lokasi serta supervisor lintas lokasi, sesuai memo meeting W-01. |

Struktur Lemari berisi Rak sudah diklarifikasi. Nama Inggris/Indonesia tidak perlu menjadi blocker bila makna fisik, ID dan alamat sama. Pemetaan istilah harus konsisten pada master, scan, label alamat, dashboard serta dokumen.


## Skenario penerimaan dan regresi

Checklist berikut adalah target uji developer. Selain sembilan probe yang dijelaskan, skenario ini belum dinyatakan lulus pada aplikasi berjalan. Data uji harus dipisahkan dari produksi.

| Uji | Skenario | Hasil yang diharapkan |
| --- | --- | --- |
| U01 / F01 | Bin modern dan legacy, dipilih/di-scan pada penerimaan serta putaway. | Kode/ID yang sama ditemukan konsisten; bin gudang lain ditolak. |
| U02 / F02 | Hapus/move lemari, rak atau bin berisi stok/tugas. | Ditolak atau dimigrasikan resmi; orphan selalu terlihat; qty fisik tidak hilang dari agregat. |
| U03 / F03 | 100 meter + 100 kg + data yard; filter satu owner. | Subtotal sah per unit; tanpa label meter tetap atau konversi berat-panjang tanpa dasar. |
| U04 / F04 | Putaway available, hold inspeksi, QC, reserved, transit, offsite, consumed. | Keputusan mengikuti matriks status/area; transit/offsite bukan stok pada rak. |
| U05 / F05 | PA owner A ke shared, dedicated A, dedicated B dan gudang nonaktif. | Tujuan yang sah saja diterima; kandidat dan validasi akhir konsisten. |
| U06 / G01-G02 | Aturan woven, grade/tahap, anak lebih ketat, kapasitas penuh; dua penempatan bersamaan. | Tidak melonggarkan larangan induk; batas/dimensi dan concurrency sesuai kebijakan. |
| U07 / G03 | SO Jakarta dengan barang sudah reserved di Bandung. | Transfer resmi menjaga komitmen SO dan qty tersedia; tidak perlu membuka stok lewat edit manual. |
| U08 / G04-G05 | Transfer ke gudang khusus jenis barang; terima sebagian, roll salah/rusak/hilang. | Validasi rules, actual receipt dan exception; hanya yang benar-benar diterima menjadi fisik tujuan. |
| U09 / DEV-03 | Alur Bandung > Jakarta > customer, termasuk staging/cross-dock dan SJ. | Dua perjalanan terlacak, owner tetap bila satu entitas, tag/LOT/roll benar dan tidak dikirim sebelum diterima. |
| U10 / DEV-04 | Opname per bin versus seluruh gudang; owner berbeda; duplikasi count key. | Scope jelas tanpa tumpang tindih; tidak menghitung qty dua kali. |
| U11 / DEV-04 | Qty berubah setelah snapshot; shortage pada reserved; surplus beberapa roll. | Hasil hitung di-review/recount, SO terdampak ditindaklanjuti, roll/tag aktual cocok. |
| U12 / DEV-04 | Approve/retry, kegagalan di tengah, biaya nol dan jurnal variance. | Penyesuaian/jurnal tidak ganda; exception terlihat; biaya nol beralasan sesuai izin. |
| U13 / DEV-04 | Sweep RFID missing/extra/salah lokasi/tanpa tag; simulasi. | Laporan dipisah dari adjustment qty; simulasi tidak disamakan dengan bukti scan nyata. |
| U14 / G06 | Drill-down seluruh tingkat, orphan, owner shared, paginasi dan akses lokasi. | Ringkasan/detail cocok, total lengkap, subtotal anak sama induk pada scope/unit sama. |


## Rujukan kode dan hasil validasi

Tautan menunjuk snapshot yang diperiksa; nomor baris adalah titik masuk.

- **R01 - Navigasi dan pewarisan peran:** [frontend/src/config/roles.js:273](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/config/roles.js#L273)
- **R02 - UI struktur, queue dan okupansi:** [frontend/src/features/wms/LocationPutawayView.jsx:50](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/features/wms/LocationPutawayView.jsx#L50)
- **R03 - Pemasangan view lokasi:** [frontend/src/AppViewRouter.jsx:474](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/AppViewRouter.jsx#L474)
- **R04 - Resolver, save, occupancy dan penempatan:** [backend/services/location_service.py:18](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/location_service.py#L18)
- **R05 - Saran/create/dispatch/arrival PA:** [backend/services/putaway_order_service.py:127](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/putaway_order_service.py#L127)
- **R06 - Site, profil dan peran gudang:** [backend/services/warehouse_profile_service.py:16](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/warehouse_profile_service.py#L16)
- **R07 - Tab stok, transfer dan opname:** [frontend/src/features/wms/OperationsView.jsx:45](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/features/wms/OperationsView.jsx#L45)
- **R08 - Picker dan dokumen transfer:** [frontend/src/features/wms/transfer/TransferCreateForm.jsx:6](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/features/wms/transfer/TransferCreateForm.jsx#L6)
- **R09 - Create/approve/status transfer:** [backend/routers/transfers.py:147](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/routers/transfers.py#L147)
- **R10 - Kontrak payload transfer:** [backend/schemas.py:620](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/schemas.py#L620)
- **R11 - Sesi opname qty, snapshot dan approve:** [backend/routers/cycle_count.py:109](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/routers/cycle_count.py#L109)
- **R12 - Qty scope dan koreksi/valuasi opname:** [backend/services/stock_count_service.py:37](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/stock_count_service.py#L37)
- **R13 - Sweep RFID dan hasil laporan:** [backend/services/cycle_count_service.py:17](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/cycle_count_service.py#L17)
- **R14 - Reservasi SO dan transfer pada roll:** [backend/services/roll_service.py:1753](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/roll_service.py#L1753)
- **R15 - Shared/dedicated dan assert_usable:** [backend/services/warehouse_scope_service.py:64](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/warehouse_scope_service.py#L64)
- **R16 - Kontrak rules kategori/grade:** [backend/services/warehouse_profile_service.py:54](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/warehouse_profile_service.py#L54)
- **R17 - Saldo dan daftar stok UI:** [frontend/src/features/wms/InventoryStockView.jsx:151](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/features/wms/InventoryStockView.jsx#L151)
- **R18 - Lookup bin pada scan penerimaan:** [backend/routers/inbound_scan_label.py:237](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/routers/inbound_scan_label.py#L237)
- **R19 - Endpoint putaway manual:** [backend/routers/inventory.py:79](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/routers/inventory.py#L79)
- **R20 - Menu Lokasi Rak:** [frontend/src/config/navStructure.js:253](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/config/navStructure.js#L253)
- **R21 - Reservasi own-stock untuk SO:** [backend/services/sales_order_helpers.py:129](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/sales_order_helpers.py#L129)

### Berkas bukti pendamping

- [Hasil validasi JSON](wms-developer-2026-10-08/wms-focused-validation.json)
- [Harness validasi terisolasi](wms-developer-2026-10-08/wms-focused-probes.py)

Harness mengambil fungsi AST dari checkout commit yang diperiksa. `WMS_AUDIT_REPO` dapat ditetapkan ke checkout lokal yang sesuai. Boundary database/framework/auth diganti in-memory doubles; ini tidak menjalankan API/deployment atau perangkat.

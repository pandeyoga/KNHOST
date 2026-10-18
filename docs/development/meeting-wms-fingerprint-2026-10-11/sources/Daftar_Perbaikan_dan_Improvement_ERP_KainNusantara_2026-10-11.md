# Daftar Perbaikan dan Improvement ERP KainNusantara

**Tanggal:** 11 Oktober 2026  
**Status:** Draf kebutuhan untuk ditinjau bersama pemilik proses.  
**Isi:** 35 poin konsolidasi catatan meeting, catatan internal WMS, dan kebutuhan absensi fingerprint.

Dokumen ini menetapkan perubahan perilaku sistem dan hasil yang diharapkan. Fase pengerjaan, estimasi, pembagian tugas developer, dan prompt implementasi belum disusun; itu menjadi development plan setelah daftar kebutuhan disepakati.

## Dasar dan cara membaca

Dasar utama adalah [memo meeting](Memo_Meeting_KainNusantara_2026-10-07.md), [memo internal WMS](Memo_Internal_Developer_WMS_2026-10-08.md), serta klarifikasi pengguna di percakapan. Konteks kode kedua memo menggunakan snapshot `f59b8a60d7b7e078888c537ca93c046afae460a9`. Jalur absensi pada snapshot tersebut diperiksa kembali untuk konsolidasi ini.

Kondisi kode di sini bukan sertifikasi atas deployment atau commit terbaru. Temuan DEV-F/DEV-G mempertahankan status dan batas bukti memo sebelumnya; dokumen ini tidak menyatakan temuan tersebut masih terbuka pada setiap versi repo atau sudah diperbaiki.

- **Perbaikan:** membenahi cacat atau perilaku yang bertentangan dengan kebutuhan yang disepakati.
- **Improvement:** menambah kemampuan atau menyelaraskan fitur yang sudah ada dengan proses operasional.
- **Menunggu keputusan:** tujuan umumnya jelas, tetapi parameter bisnis atau otoritas belum ditetapkan. Parameter tersebut tidak boleh diisi berdasarkan asumsi developer.

Nomor IMP-01 sampai IMP-35 adalah identitas kebutuhan pada dokumen ini, bukan pengganti nomor temuan audit sebelumnya. Beberapa catatan digabung karena menyangkut kemampuan yang sama; satu catatan juga dapat dijabarkan menjadi beberapa kebutuhan.

## A. Meja pengguna

### IMP-01 — Setiap antrean membuka detail pekerjaan yang relevan

**Jenis:** Improvement. **Asal:** U-01.

Semua baris pekerjaan di meja Sales/Admin Sales, MD, Gudang, Sampel, dan Finance yang memerlukan tindak lanjut dapat dibuka ke detail prosesnya. Detail menampilkan dokumen sumber, produk, qty/satuan/roll jika relevan, status, kendala, PIC, histori, dan tindakan berikutnya sesuai izin.

**Hasil yang diharapkan:** angka ringkasan dapat ditelusuri ke daftar pembentuknya; kembali ke antrean mempertahankan filter dan posisi kerja. Ringkasan dan rincian memakai sumber serta cakupan data yang sama.

## B. Sales dan Admin Sales

### IMP-02 — Tampilan khusus Keep dengan definisi yang konsisten

**Jenis:** Improvement/penyelarasan. **Asal:** S-01.

Keep berarti SO sudah dibuat tetapi belum diverifikasi Admin Sales. Sediakan daftar, jumlah pesanan, nilai/qty yang relevan, umur antrean, dan akses detail verifikasi. Keep tidak otomatis berarti stok telah dicadangkan.

**Hasil yang diharapkan:** status verifikasi tidak dicampur dengan status ketersediaan barang. SO yang juga Pending dapat dikenali tanpa menggandakan total pesanan unik.

**Menunggu keputusan:** pengecualian status batal/tolak dan apakah ada kebijakan batas waktu Keep atau penahanan stok yang terpisah.

### IMP-03 — Pending dimulai dari kebutuhan produk, lalu dokumen pemenuhannya

**Jenis:** Improvement. **Asal:** S-01.

Pending berarti kebutuhan barang pada SO masih menunggu pemenuhan/backorder. Tampilan dimulai dari artikel/warna, qty belum terpenuhi, satuan, SO terkait, jalur pemenuhan, progres, dan ETA apabila tercatat. Pengguna kemudian membuka PR, PO, order makloon/MKO, pengadaan internal, atau transfer yang benar-benar terkait.

**Hasil yang diharapkan:** penerimaan atau pemenuhan parsial mengurangi sisa Pending secara tepat. PR yang belum menjadi PO tidak diberi nomor PO fiktif. Incoming tidak ditampilkan seolah stok fisik yang sudah tersedia.

### IMP-04 — Pisahkan tampilan komersial Sales dari detail alokasi internal

**Jenis:** Perbaikan presentasi/akses. **Asal:** S-03 dan klarifikasi stok lintas entitas sebelumnya.

Sales memilih artikel dan warna. LOT, grade, asal impor/lokal, serta identitas pemilik stok disajikan kepada peran operasional yang berwenang; detail tersebut tidak menjadi pilihan alokasi Sales. Sales dapat melihat ringkasan stok lintas entitas yang diizinkan untuk penjualan: stok fisik, cadangan, incoming, dan available to order dengan definisi yang jelas.

**Hasil yang diharapkan:** penyaringan konsisten di katalog, pencarian, detail pesanan, mobile, dan layanan data yang dipakai Sales. Atribut internal tetap tersimpan untuk Admin Sales, gudang, traceability, HPP, dan transaksi antar entitas. Stok entitas lain tidak dianggap otomatis telah menjadi milik entitas penjual.

### IMP-05 — Roll picker untuk seluruh alokasi dan perubahan pemenuhan

**Jenis:** Improvement/penyelarasan. **Asal:** S-04.

Admin Sales memilih roll fisik melalui pemilih yang menampilkan kode roll, qty aktual, satuan, LOT, grade, asal, gudang, pemilik, dan status kelayakan. Sistem menjumlahkan qty serta jumlah roll terpilih dan menjelaskan alasan roll tidak dapat dipilih.

**Hasil yang diharapkan:** perubahan pilihan memperbarui reservasi dan memeriksa tugas picking/transfer yang sudah berjalan. Roll yang sama tidak dialokasikan ke dua kebutuhan. Barang entitas lain mengikuti transaksi internal yang sah.

### IMP-06 — Qty, satuan, dan rincian roll jelas sepanjang alur SO

**Jenis:** Perbaikan informasi dan konsistensi kalkulasi. **Asal:** S-09 dan klarifikasi pesanan yard/roll sebelumnya.

Daftar/detail SO dan layar pemenuhan menunjukkan qty dipesan, dialokasikan, dikirim, dan sisa secara terpisah, beserta satuan dan jumlah roll. Rincian membuka kode serta panjang/berat aktual masing-masing roll. Sebelum roll ditentukan, tampilkan belum dialokasikan; jangan menyajikan estimasi sebagai angka aktual.

**Hasil yang diharapkan:** pesanan berdasarkan yard maupun roll dapat ditelusuri ke fisik. Jika pemenuhan roll utuh membuat 1.000 yard menjadi 1.005 yard, tampilkan selisih dan keputusan pemenuhannya; quantity komersial serta dokumen turunannya mengikuti keputusan yang sah. Tidak ada asumsi setiap roll 100 yard atau penjumlahan kg dengan yard.

### IMP-07 — Special Order dari artikel existing atau desain pelanggan

**Jenis:** Improvement. **Asal:** S-02.

Special Order dapat mereferensikan artikel existing untuk perubahan warna/spesifikasi. Bedakan desain internal, desain pelanggan, dan desain existing. Catat berkas, versi, penerimaan, serta keputusan apakah desain siap proofing atau perlu pekerjaan Desainer.

**Hasil yang diharapkan:** desain pelanggan yang telah diterima dapat dilanjutkan ke proofing tanpa tahap pembuatan desain yang tidak diperlukan. Referensi artikel asal tidak otomatis mengubah SKU yang sudah aktif.

**Menunggu keputusan:** siapa pembuat/pengelola Special Order, siapa menyetujui desain pelanggan, dan kriteria desain siap proofing.

### IMP-08 — Special Order berisi beberapa produk dengan progres per baris

**Jenis:** Improvement. **Asal:** S-05.

Satu Special Order mendukung beberapa baris produk. Setiap baris memiliki artikel/warna/spesifikasi, qty/satuan, desain, uji, harga, tenggat, progres, dan hubungan ke SKU/pengadaan/SO sendiri.

**Hasil yang diharapkan:** satu produk selesai tidak otomatis menyelesaikan seluruh pesanan. Persetujuan, pembatalan, dan pemenuhan dapat ditelusuri per produk.

**Menunggu keputusan:** persetujuan/pengiriman parsial serta pemecahan SO dan dokumen pengadaan antarproduk.

### IMP-09 — Tiga jenis sampel tampil jelas bagi Sales

**Jenis:** Improvement/penyelarasan. **Asal:** S-06.

Jenis fisik sampel adalah Hanger, Katalog, dan Cutting. Tampilkan pilihan tersebut pada permintaan Sales dan dokumen/tugas terkait. Bedakan jenis fisik dari skema gratis/berbayar dan jenis pengujian R&D.

**Hasil yang diharapkan:** pilihan jenis sampel tetap konsisten dari permintaan sampai pengiriman.

**Menunggu keputusan:** batas qty, biaya/harga, persetujuan, dan aturan masing-masing jenis. Tidak menetapkan ketiganya gratis atau berbayar secara otomatis.

### IMP-10 — Tambahkan serah terima dan proses Admin Cutting setelah pemotongan

**Jenis:** Improvement proses. **Asal:** S-06.

Alur yang dituju: permintaan → persetujuan yang berlaku → potong di gudang → serah terima hasil ke Admin Cutting → proses akhir → pengiriman oleh Admin Cutting. Tambahkan antrean, PIC, qty aktual, bukti serah terima, dan kriteria siap kirim.

**Hasil yang diharapkan:** selesai potong tidak langsung dianggap terkirim. Handoff tidak mencatat stok baru atau mengurangi roll sumber untuk kedua kalinya.

**Menunggu keputusan:** Admin Cutting merupakan peran tersendiri atau nama operasional Admin Sampel; kegiatan proses akhir dan pejabat pelepas pengiriman.

### IMP-11 — Samakan harga non-BS dan berikan rekomendasi grade yang dapat dijelaskan

**Jenis:** Perbaikan aturan harga/improvement alokasi. **Asal:** S-08.

Untuk artikel/warna, satuan, dan kondisi komersial yang sama, grade non-BS memiliki harga jual sama. BS diperlakukan terpisah. Identitas, mutu, serta HPP roll tidak digabung karena harga jualnya sama.

Rekomendasi alokasi memakai standar minimum pelanggan dan aturan efisiensi yang disetujui; tampilkan alasan kepada Admin Sales. Pemilihan akhir dilakukan sesuai otorisasi, bukan dugaan sistem tentang kelas pelanggan.

**Menunggu keputusan:** matriks pelanggan-grade, aturan pengecualian, dan cara menawarkan BS agar konsisten dengan tampilan warna saja bagi Sales.

## C. Master data

### IMP-12 — Rapikan klasifikasi tahap bahan dan kelayakan tampil di Sales

**Jenis:** Perbaikan klasifikasi/presentasi serta kesiapan data. **Asal:** S-07, M-01.

Greige, PFD, PFP, dan Finished merupakan tahap barang; Woven/Knitting merupakan jenis kain, sedangkan Printing berkaitan dengan lini/proses. Gunakan klasifikasi yang konsisten dan saring greige/PFD/PFP dari seluruh pilihan produk Sales. Bahan tetap tersedia bagi MD, pembelian, gudang, dan makloon.

**Hasil yang diharapkan:** master bahan dapat dibuat tanpa kewajiban menjalani R&D produk hasil MD. Klien menyiapkan kode, nama, satuan, spesifikasi, tahap, dan hubungan resep; stok awal per pemilik/gudang/LOT/roll diimpor sebagai data terpisah.

### IMP-13 — Pemetaan supplier, barang supplier, dan warna supplier lengkap

**Jenis:** Improvement master/informasi. **Asal:** M-02, D-03.

Simpan serta tampilkan supplier, kode/nama barang versi supplier, kode/nama warna supplier, dan pasangan artikel/warna internal. Satu item internal dapat memiliki beberapa supplier atau alias. Kode warna pelanggan tetap dibedakan dari kode supplier dan kode internal.

**Hasil yang diharapkan:** pemetaan yang sama dipakai pada master, PO, dan penerimaan. Pemetaan belum jelas masuk review; tidak menciptakan SKU baru atau menimpa identitas internal hanya karena ejaan supplier berbeda.

**Ketergantungan data:** klien menyerahkan daftar supplier beserta kode/nama dan pasangan internal yang diketahui.

### IMP-14 — Perjelas tambah, edit, nonaktif, dan hapus master

**Jenis:** Improvement pengelolaan/integritas. **Asal:** D-03.

Bedakan pengubahan induk produk, varian, spesifikasi, alias supplier, warna, dan harga. Detail menjelaskan relasi serta dampak tindakan. Data yang telah dipakai pada stok atau transaksi memiliki kebijakan nonaktif/arsip dan jejak perubahan yang mempertahankan histori.

**Hasil yang diharapkan:** perubahan nama tidak mengganti identitas. Penghapusan yang memutus referensi ditolak; pengguna mengetahui dokumen atau stok yang masih memakai master tersebut.

### IMP-15 — Filter master produk/varian lengkap dan dapat digabung

**Jenis:** Improvement UI. **Asal:** D-04.

Sediakan filter jenis kain, tahap, lini/kategori, warna/motif, supplier, status lifecycle, dan metode restock ketika tersedia. Filter dapat digabung, direset, dan menunjukkan jumlah hasil; pembatasan sesuai peran tetap berlaku.

**Hasil yang diharapkan:** MD dapat memisahkan bahan dan barang jadi serta mencari artikel berdasarkan klasifikasi. Nilai Greige/Grey tidak menjadi dua klasifikasi yang tumpang tindih tanpa aturan master yang jelas.

## D. MD, R&D, dan makloon

### IMP-16 — Bedakan MD Quality dengan QC beserta dampak prosesnya

**Jenis:** Penyelarasan proses dan tanggung jawab. **Asal:** D-01.

Petakan MD Quality dan QC berdasarkan objek pemeriksaan, tahap, PIC, bukti, hasil, dan pengaruhnya terhadap stok. Cakup pengujian/spesifikasi, mutu hasil produksi/kedatangan, retur, serta random check sesuai definisi klien.

**Hasil yang diharapkan:** pemisahan bukan sekadar mengganti nama menu. Kontrol hold/release dan penanggung jawab pelepasan stok yang sudah ada tetap jelas.

**Menunggu keputusan:** batas MD Quality, kebutuhan QC kedatangan, serta pemicu dan aturan random check.

### IMP-17 — Uji tambahan SKU existing tanpa membuat master duplikat

**Jenis:** Improvement R&D. **Asal:** D-02 dan klarifikasi R&D sebelumnya.

Bedakan pengembangan baru dengan pengujian tambahan/revalidasi barang aktif. Labdip dan Handfeel dapat dilanjutkan pada SKU yang sama apabila identitas barang tidak berubah. Simpan request, ronde, pelaksana, hasil, bukti, dan persetujuan; peran serta jenis uji mengikuti lini dan penugasan MD.

**Hasil yang diharapkan:** histori menunjukkan siapa mengerjakan dan menyetujui. Uji tambahan tidak melahirkan SKU duplikat. Jika warna/konstruksi atau identitas produk berubah, gunakan keputusan varian/spec melalui alur resmi.

**Menunggu keputusan:** apakah hasil tambahan hanya catatan atau revisi spesifikasi aktif; approver dan kebutuhan menahan SKU yang sedang dijual.

### IMP-18 — Tampilkan kebutuhan bahan makloon, reservasi, issue, dan WIP secara jelas

**Jenis:** Improvement visibilitas/kontrol pemenuhan. **Asal:** D-05.

MD/Admin Sales melihat jenis bahan yang benar untuk artikel/resep, stok fisik, komitmen, tersedia, incoming, dan kekurangan. Pisahkan keputusan rencana pemenuhan, reservasi bahan, issue fisik, dan bahan di proses makloon/WIP.

**Hasil yang diharapkan:** dengan resep 1:1, stok 1.000 yard dan reservasi 600 menyisakan tersedia 400. Saat 600 di-issue, saldo gudang menjadi 400 dan barang terlacak dalam proses; tidak berkurang lagi menjadi minus atau dihitung dua kali. Kasus nyata mengikuti resep, yield, satuan, dan konversi sah.

**Menunggu keputusan/data:** resep bahan-output, yield, lead time, dan ambang peringatan/restock.

### IMP-19 — Tetapkan sumber restock per artikel dan arahkan backorder sesuai master

**Jenis:** Improvement aturan pengadaan. **Asal:** D-06.

Master menetapkan supplier saja, makloon saja, atau keduanya, beserta supplier/mitra/resep yang diizinkan. Pemenuhan Pending menggunakan kemampuan tersebut: PR beli → PO → terima, atau PR proses → reservasi bahan → MKO → issue → terima hasil.

**Hasil yang diharapkan:** artikel makloon-only tidak diarahkan ke pembelian produk jadi yang tidak berlaku. Kekurangan bahan terlihat sebelum menjanjikan hasil produksi. Stok siap dan pembelian internal tetap dapat menjadi jalur pemenuhan yang sah sesuai aturan entitas.

**Menunggu keputusan/data:** klasifikasi artikel, lead time, serta prioritas bila pembelian dan makloon sama-sama tersedia.

## E. Gudang dan WMS

### IMP-20 — Batasi pekerjaan gudang menurut lokasi penugasan pengguna

**Jenis:** Perbaikan akses/visibilitas. **Asal:** W-01.

Antrean, angka pekerjaan, detail, notifikasi, serta tindakan mengikuti lokasi/gudang kerja pengguna. Petugas Bandung tidak otomatis melihat atau memproses pekerjaan Jakarta hanya karena badan usaha sama. Supervisor lintas lokasi memiliki kewenangan tersendiri.

**Hasil yang diharapkan:** cakupan berlaku di UI dan server, termasuk barang masuk/keluar, QC, putaway, transfer, opname, dan RFID. Penugasan lokasi dibedakan dari pemilik stok dan hak memakai gudang shared/dedicated.

**Menunggu keputusan:** daftar pengguna-lokasi serta otoritas melihat/mengambil alih pekerjaan lintas lokasi.

### IMP-21 — OCR SJ/packing list mengisi kandidat roll secara kelompok

**Jenis:** Improvement penerimaan. **Asal:** W-02.

Ekstrak artikel/warna, LOT, jumlah roll, kode/urutan roll, dan qty/satuan tiap roll apabila dokumen memuatnya. Pengguna meninjau hasil, memperbaiki pembacaan ragu, mencocokkan subtotal, lalu memvalidasi fisik sesuai SOP. Simpan qty dokumen dan qty aktual/koreksi secara terpisah.

**Hasil yang diharapkan:** mengurangi input satu per satu tanpa menyamakan OCR dengan hasil ukur fisik. Dokumen yang hanya memuat total tidak dipecah menjadi roll berukuran sama berdasarkan asumsi.

**Menunggu keputusan/data:** contoh SJ, format per supplier, aturan adopsi ukuran setelah review atau kewajiban ukur ulang.

### IMP-22 — Pulihkan pengalaman putaway dan satukan jalur scan/alamat

**Jenis:** Perbaikan fungsional/akses. **Asal:** DEV-WMS-01, DEV-F01, DEV-F04.

Telusuri laporan putaway tidak terlihat terhadap menu, custom role, versi aplikasi, dan fungsi yang digunakan. Pada snapshot, kode/menu masih ada; hilangnya fitur di deployment belum terbukti sebagai penghapusan kode. Hubungkan meja gudang dengan antrean siap ditempatkan dan alasan pekerjaan terhambat.

Gunakan pencarian alamat bersama untuk struktur modern `rack.levels[].bins` dan legacy. Putaway hanya mengubah alamat di gudang yang sama dan tidak menambah/mengurangi stok. Roll dalam perjalanan tidak boleh diberi alamat seolah sudah ada secara fisik. Pertahankan kontrol QC/hold.

**Hasil yang diharapkan:** barang penerimaan dapat dipindai dan ditempatkan pada alamat yang dibuat melalui editor. Setelah transfer tiba, muncul tugas penempatan bila disimpan; barang yang langsung dikirim dapat diarahkan ke staging/transit. Semua barang tetap mengikuti kewajiban tag RFID yang telah dijelaskan pengguna.

### IMP-23 — Hierarki fisik konsisten dari lokasi sampai posisi penyimpanan

**Jenis:** Improvement/penyelarasan model dan UI. **Asal:** DEV-WMS-02 dan klarifikasi Lemari.

Hierarki bisnis: Lokasi → Gudang → Zona → Lemari → Rak → posisi penyimpanan bila diperlukan. Lemari adalah wadah tersendiri berisi rak. Istilah aplikasi boleh berbeda apabila hubungan fisiknya sama: model Rack dapat mewakili Lemari, Level mewakili Rak di dalamnya, dan Bin mewakili posisi akhir.

**Hasil yang diharapkan:** master, label, scan, alamat roll, dan dashboard memakai padanan yang sama. Setiap node mempunyai ID stabil, kode/nama, induk, status, serta atribut yang relevan. Tidak membuat struktur paralel atau stok per lemari yang diperbarui terpisah dari roll.

### IMP-24 — Rules gudang dan sublokasi berlaku konsisten di seluruh jalur

**Jenis:** Perbaikan penegakan aturan/improvement rules. **Asal:** DEV-WMS-05, DEV-F05, DEV-G01, DEV-G02, DEV-G04; terkait DEV-F04.

Pisahkan hak pemakaian shared/dedicated, fungsi transit/storage/staging/return, dan kelayakan barang. Rules dapat membatasi jenis kain, tahap, grade, status mutu, atau atribut relevan pada gudang, zona, lemari, rak, dan bin. Shared dapat menyimpan beberapa owner yang diizinkan; dedicated menolak owner yang tidak diizinkan.

Aturan induk-anak dan kapasitas harus memiliki arti jelas. Jika kategori serta grade sama-sama diwajibkan, keduanya diperiksa; aturan anak tidak diam-diam menghapus larangan induk. Saran penempatan dan validasi akhir memakai evaluator yang sama untuk putaway, scan, PA, transfer, penerimaan, dan retur.

**Hasil yang diharapkan:** tujuan yang ditawarkan memang sah, pemeriksaan server tidak dapat dilewati, dan penolakan menjelaskan alasannya.

**Menunggu keputusan:** atribut wajib, pewarisan, kapasitas berdasarkan roll/berat/volume/panjang, batas keras atau peringatan, serta otoritas pengecualian. Kapasitas saat ini yang belum memblokir tidak otomatis berarti semua lokasi wajib hard-block.

### IMP-25 — Lindungi stok dan tugas saat struktur lokasi diubah

**Jenis:** Perbaikan integritas referensi. **Asal:** DEV-F02; terkait DEV-WMS-02/06.

Tolak penghapusan atau perpindahan node yang memutus alamat stok/tugas aktif, kecuali melalui migrasi berjejak yang sah. Penggantian nama mempertahankan ID. Alamat hilang/tidak valid masuk daftar orphan yang dapat ditindaklanjuti.

**Hasil yang diharapkan:** roll tidak menghilang dari dashboard ketika struktur diubah. Fisik pada bin sah + belum ditempatkan + orphan dapat direkonsiliasi ke fisik gudang pada cakupan dan satuan yang sama.

### IMP-26 — Transfer antar gudang untuk memenuhi SO menjaga komitmen barang

**Jenis:** Improvement alur pemenuhan. **Asal:** DEV-WMS-03, DEV-G03.

Bedakan putaway dalam satu gudang dengan transfer yang mengganti gudang fisik. Untuk SO Jakarta dengan barang di Bandung: kebutuhan SO → picking/staging sumber → kirim transfer → terima Jakarta → staging/penempatan sesuai kebutuhan → pengiriman pelanggan.

Transfer yang terkait SO mempertahankan komitmen roll selama perjalanan tanpa membebaskannya bagi pesanan lain atau membuat reservasi ganda. Identitas roll, LOT, tag, owner, dan dasar biaya terlacak. Penerimaan Jakarta tidak otomatis berarti barang sudah dikirim ke pelanggan.

**Hasil yang diharapkan:** SJ transfer dan SJ pelanggan memiliki sumber/proses yang jelas; petugas masing-masing lokasi mengerjakan tahapnya. Transfer same-owner tidak menjadi jual-beli; jika owner berbeda, transaksi internal tetap diperlukan. Penolakan roll reserved pada transfer umum diperlakukan sebagai batas kemampuan, bukan izin melepas reservasi melalui edit data langsung.

### IMP-27 — Terima transfer berdasarkan roll aktual, termasuk parsial dan selisih

**Jenis:** Perbaikan/improvement penerimaan transfer. **Asal:** DEV-G05; terkait DEV-WMS-03.

Penerimaan mencatat roll yang benar-benar diterima melalui scan/pilihan dan bukti serah terima. Dukung penerimaan parsial, barang belum tiba, roll salah, rusak, dan kehilangan dengan antrean exception serta PIC tindak lanjut.

**Hasil yang diharapkan:** hanya barang diterima yang berpindah ke stok tujuan. Sisa tetap terlacak in-transit/exception. Mengganti status dokumen tidak menyatakan semua barang telah tiba tanpa bukti penerimaan. Retry tidak menggandakan penerimaan.

### IMP-28 — Stock opname menyatukan qty, identitas roll, alamat, dan RFID

**Jenis:** Improvement kontrol persediaan. **Asal:** DEV-WMS-04.

Pilih scope lokasi/gudang/zona/lemari/rak/bin dengan pemilik yang jelas; ambil snapshot, hitung fisik, review selisih, approve, lalu terapkan penyesuaian yang sah. Hasil RFID menunjukkan ditemukan/missing/extra/salah lokasi, tetapi keberhasilan baca tag tidak membuktikan panjang/berat benar.

**Hasil yang diharapkan:** daftar aktual menjaga jumlah dan identitas roll. Salah rak ditangani sebagai koreksi alamat; kehilangan/kelebihan atau selisih ukuran ditangani sesuai kasus. Reservasi terdampak ditindaklanjuti. Selisih yang sama tidak diposting ulang dari opname qty dan sweep RFID; penyesuaian stok/jurnal tidak berganda saat retry.

**Menunggu keputusan:** cutoff/transaksi berjalan, penghitung dan approver, valuasi serta akun Finance, dan SOP tag/roll surplus atau hilang.

### IMP-29 — Dashboard stok berjenjang dengan subtotal satuan dan status yang benar

**Jenis:** Perbaikan kalkulasi/improvement analitik. **Asal:** DEV-WMS-06, DEV-F03, DEV-G06.

Tampilkan qty serta jumlah roll per lokasi, gudang, zona, lemari, rak, hingga bin, dengan rincian pembentuk angka. Pisahkan stok fisik, available, reserved/committed, QC/hold, incoming, dan in-transit agar pengguna tidak menjumlahkan kategori yang tumpang tindih.

**Hasil yang diharapkan:** 100 meter + 100 kg tetap menjadi dua subtotal. Utilisasi kapasitas memakai dimensi yang sah. Agregat induk sesuai anak; total tidak dihitung dari halaman data yang sedang terbuka saja. Belum ditempatkan dan orphan terlihat. Pada shared warehouse, kapasitas fisik memperhitungkan seluruh isi, dengan rincian owner tetap mengikuti izin.

## F. Fingerprint dan absensi HR

### IMP-30 — Mesin mengirim absensi langsung ke penerima di server ERP

**Jenis:** Improvement integrasi. **Asal:** kebutuhan pengguna tanpa PC/laptop/gateway tambahan.

Target: mesin absensi → jaringan → penerima protokol perangkat di server ERP → pencatatan kehadiran. Penerima/adapter dapat menjadi bagian backend ERP; tidak mensyaratkan software vendor atau laptop lokal yang selalu menyala. Tetap diperlukan jaringan dan server ERP yang dapat diakses perangkat.

Pada snapshot, `/api/hr/attendance/ingest` menerima JSON `device_token` dan `records`, sedangkan UI menjelaskan agen jembatan on-prem. Ini belum membuktikan kompatibilitas langsung dengan protokol native mesin ZKTeco. Implementasikan penerima sesuai protokol model/firmware terpilih, termasuk respons penerimaan dan retry.

**Hasil yang diharapkan:** transaksi fingerprint pada mesin nyata muncul di ERP tanpa perantara lokal dan tanpa import CSV rutin.

### IMP-31 — Registrasi perangkat dan pemetaan ID pegawai terkontrol

**Jenis:** Improvement konfigurasi/integritas identitas. **Asal:** kebutuhan fingerprint; fondasi device dan ID fingerprint sudah ada pada snapshot.

Catat identitas/serial mesin, status, lokasi, cakupan entitas, konfigurasi koneksi, dan otoritas pengelola. Peta ID pengguna pada mesin ke pegawai harus eksplisit, termasuk kebijakan ketika nomor enrollment sama digunakan oleh mesin atau lokasi berbeda.

**Hasil yang diharapkan:** log tidak jatuh ke pegawai atau entitas yang salah. Perangkat tidak terdaftar/nonaktif ditangani sesuai aturan. Log dengan ID belum terpetakan masuk review dan dapat diproses ulang tanpa mengubah bukti asal.

### IMP-32 — Pisahkan log punch mentah dari hasil perhitungan kehadiran

**Jenis:** Improvement akurasi dan jejak. **Asal:** kebutuhan integrasi langsung; aturan perhitungan perlu divalidasi terhadap SOP HR.

Simpan peristiwa asli beserta ID perangkat, ID pegawai mesin, waktu perangkat, waktu diterima, dan jenis peristiwa bila tersedia. Hasil absensi harian/shift merupakan perhitungan yang dapat ditelusuri ke log tersebut. Verifikasi fingerprint berlangsung di mesin; integrasi kehadiran tidak memerlukan penyimpanan template sidik jari dalam ERP.

**Hasil yang diharapkan:** masuk/pulang, punch berulang, shift lintas tengah malam, keterlambatan, dan lembur tidak disimpulkan hanya dari tanggal kalender atau dua jam tanpa konteks shift. Koreksi HR beralasan mempertahankan log asal. Hasil untuk payroll mengikuti review/otorisasi yang berlaku.

**Menunggu keputusan:** jadwal/shift, toleransi, aturan punch hilang/duplikat, lintas lokasi, lembur, dan koreksi.

### IMP-33 — Tahan putus koneksi dan cegah pencatatan ganda

**Jenis:** Improvement keandalan. **Asal:** kebutuhan operasional fingerprint.

Mesin harus menyimpan log saat offline dan mengirim backlog setelah jaringan pulih sesuai kemampuannya. ERP mengenali kiriman ulang berdasarkan identitas peristiwa/protokol yang sah, memberikan konfirmasi setelah penerimaan tersimpan, dan memisahkan log gagal dari log berhasil.

**Hasil yang diharapkan:** reconnect/retry tidak menambah absensi atau perhitungan payroll dua kali; keterlambatan kiriman tidak menghilangkan histori. Kegagalan di tengah batch dapat dipulihkan dan jam perangkat yang menyimpang dapat dikenali.

### IMP-34 — Antarmuka HR memantau sinkronisasi dan exception

**Jenis:** Improvement UI/operasional. **Asal:** kebutuhan pengoperasian fingerprint langsung.

Tampilkan perangkat/lokasi, waktu kontak dan kiriman berhasil terakhir, riwayat sync, log gagal, ID belum terpetakan, serta tindakan review/reprocess sesuai izin. Bedakan perangkat menghubungi server dari data absensi berhasil tersimpan.

**Hasil yang diharapkan:** HR mengetahui masalah sebelum data dipakai untuk payroll. Koreksi manual dan pemrosesan ulang mempunyai alasan, pelaksana, dan histori; pengguna tidak perlu menjalankan skrip untuk pekerjaan rutin.

### IMP-35 — Tetapkan kompatibilitas hardware melalui uji perangkat nyata

**Jenis:** Validasi prasyarat integrasi; belum merupakan keputusan pembelian.

Pilih terminal yang memang ditujukan untuk time attendance dan mendukung protokol pengiriman ke server yang dapat dikonfigurasi. Dukungan ADMS/PUSH pada brosur bukan bukti otomatis cocok dengan endpoint JSON ERP. Model, varian, firmware, dokumentasi protokol, serta kemampuan koneksi harus dicocokkan.

**Hasil yang diharapkan:** demonstrasi mesin → ERP tanpa laptop/gateway, termasuk offline/reconnect, kiriman ulang, pegawai belum terpetakan, dan jam/shift lintas hari. Keputusan model dibuat berdasarkan unit yang dapat diperoleh serta hasil uji; model paling baru secara global tidak otomatis tersedia di marketplace Indonesia.

**Menunggu keputusan/data:** calon model/firmware dan akses unit untuk pengujian. Usulan arsitektur ini belum menyatakan integrasi hardware sudah siap pakai.

## G. Keputusan bisnis dan data yang masih diperlukan

Daftar berikut mengumpulkan hal yang belum final; ini bukan pertanyaan ulang atau syarat menghentikan peninjauan kebutuhan.

| Referensi | Keputusan/data yang diperlukan |
|---|---|
| IMP-02–03 | Status yang dihitung sebagai Keep/Pending, perlakuan parsial/batal, dan kebijakan penahanan bila ada. |
| IMP-07–08 | PIC Special Order, penerimaan desain pelanggan, serta persetujuan/pengiriman/pemisahan dokumen parsial. |
| IMP-09–10 | Rules Hanger/Katalog/Cutting, identitas peran Admin Cutting, proses akhir, dan bukti siap kirim. |
| IMP-11 | Matriks pelanggan-grade, pengecualian, serta cara menawarkan BS. |
| IMP-12–15 | Dataset bahan/supplier/warna, pasangan ke master internal, dan kebijakan lifecycle master. |
| IMP-16–17 | Batas MD Quality/QC, random check, dan pengaruh uji tambahan pada spesifikasi/stok aktif. |
| IMP-18–19 | Resep, yield, bahan-output, sumber restock, lead time, dan prioritas pengadaan. |
| IMP-20–21 | Penugasan pengguna-lokasi, supervisor lintas lokasi, contoh SJ, serta SOP menerima ukuran dari OCR. |
| IMP-24, 26–28 | Rules/kapasitas/pengecualian, serah terima transfer, cutoff opname, dan kebijakan valuasi Finance. |
| IMP-30–35 | Model/firmware/protokol mesin, koneksi, shift/toleransi/lembur, otoritas koreksi, serta pegawai-lokasi-perangkat. |

## H. Hubungan antarmodul yang harus tetap benar

1. **Keep/Pending → pemenuhan → transfer → pengiriman.** Verifikasi, komitmen barang, lokasi fisik, penerimaan, dan pengiriman pelanggan merupakan tahap berbeda. Qty sisa dan referensi dokumen mengikuti kejadian yang benar-benar terjadi.
2. **Special Order → desain/R&D → master → pengadaan → SO.** Hubungan per baris produk terjaga; uji tambahan tidak menggandakan master dan persetujuan satu baris tidak menutup baris lain.
3. **Backorder makloon → bahan → reservasi → issue → WIP → hasil.** Kebutuhan bahan mengikuti resep; saldo fisik, komitmen, dan biaya proses tidak diposting dua kali.
4. **Sampel → cutting → Admin Cutting → pengiriman.** Status serah terima jelas dan pengurangan roll sumber dilakukan sekali berdasarkan hasil aktual.
5. **OCR/penerimaan → tag → alamat → transfer/opname → dashboard.** Identitas roll, owner, LOT, satuan, dan status mengikuti sumber yang sama. Salah lokasi dibedakan dari kehilangan persediaan.
6. **Fingerprint → log asal → absensi shift → review HR → payroll.** Kiriman ulang tidak menambah peristiwa/kehadiran ganda; koreksi serta perhitungan dapat ditelusuri.

Ini merupakan batas perilaku yang harus dijaga oleh development plan berikutnya, bukan klaim pengujian seluruh rantai tersebut telah lulus.

## I. Pemetaan ke catatan sebelumnya

### Seluruh catatan meeting

| Catatan asal | Kebutuhan konsolidasi |
|---|---|
| U-01 — meja pengguna | IMP-01 |
| S-01 — Keep/Pending | IMP-02, IMP-03 |
| S-02 — artikel/desain/PIC Special Order | IMP-07 |
| S-03 — tampilan Sales warna saja | IMP-04 |
| S-04 — roll picker | IMP-05 |
| S-05 — Special Order multi-produk | IMP-08 |
| S-06 — jenis sampel dan proses setelah cutting | IMP-09, IMP-10 |
| S-07 — bahan disembunyikan dari Sales | IMP-12 |
| S-08 — harga/rekomendasi grade | IMP-11 |
| S-09 — qty/satuan/roll SO | IMP-06 |
| M-01 — data bahan | IMP-12 |
| M-02 — data supplier | IMP-13 |
| D-01 — MD Quality/QC | IMP-16 |
| D-02 — R&D barang existing | IMP-17 |
| D-03 — detail dan pengelolaan master | IMP-13, IMP-14 |
| D-04 — filter produk/varian | IMP-15 |
| D-05 — stok greige/makloon | IMP-18 |
| D-06 — sumber restock | IMP-19 |
| W-01 — visibilitas lokasi | IMP-20 |
| W-02 — OCR roll | IMP-21 |

### Seluruh catatan internal WMS

| Catatan asal | Kebutuhan konsolidasi |
|---|---|
| DEV-WMS-01 — putaway | IMP-22 |
| DEV-WMS-02 — hierarki | IMP-23, IMP-25 |
| DEV-WMS-03 — transfer Bandung/Jakarta | IMP-26, IMP-27 |
| DEV-WMS-04 — stock opname | IMP-28 |
| DEV-WMS-05 — rules | IMP-24 |
| DEV-WMS-06 — stok per alamat | IMP-29 |

### Temuan WMS yang menjadi dasar perbaikan

| Temuan asal | Ringkasan dan kebutuhan terkait |
|---|---|
| DEV-F01 | Lookup scan tidak membaca bin struktur modern → IMP-22. |
| DEV-F02 | Hapus struktur dapat membuat alamat stok orphan dan luput dari dashboard → IMP-25, IMP-29. |
| DEV-F03 | Okupansi mencampur unit dan UI melabeli meter → IMP-29. |
| DEV-F04 | Penempatan menerima roll masih in-transit → IMP-22, IMP-24. |
| DEV-F05 | PA dapat dibuat ke dedicated owner lain → IMP-24. |
| DEV-G01 | Kapasitas belum ditegakkan sesuai kebijakan yang harus diputuskan → IMP-24, IMP-29. |
| DEV-G02 | Kategori/grade tidak diperiksa bersamaan dan rules subnode terbatas → IMP-24. |
| DEV-G03 | Transfer umum menolak roll reserved SO; perlu alur transfer terkait SO → IMP-26. |
| DEV-G04 | Transfer belum menerapkan storage rules tujuan pada jalur yang ditelusuri → IMP-24, IMP-27. |
| DEV-G05 | Completed menerima semua roll tanpa payload penerimaan aktual → IMP-27. |
| DEV-G06 | Belum tersedia ringkasan stok seluruh node dan orphan yang lengkap → IMP-25, IMP-29. |

DEV-F01–F05 direproduksi dalam probe terisolasi pada memo WMS. DEV-G01–G03 diamati dalam probe; DEV-G04–G06 didasarkan pada kontrak/flow kode. Itu tidak setara dengan pengujian deployment/UI lengkap. Bukti dan batas validasi tersedia di [hasil validasi WMS](wms-developer-2026-10-08/wms-focused-validation.json).

### Titik masuk kode absensi yang diperiksa kembali

- [Schema ingest: agen jembatan dengan payload JSON](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/schemas_hr_attendance.py#L75).
- [Endpoint ingest perangkat](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/routers/hr_attendance.py#L503).
- [Petunjuk konfigurasi agen jembatan di UI](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/features/hr/AttendanceSetupView.jsx#L196).

## Batas daftar ini

Daftar ini mencakup seluruh 20 catatan meeting, 6 catatan internal WMS beserta 5 cacat dan 6 gap pendukung, serta kebutuhan fingerprint yang dibahas. Ini bukan pengganti backlog semua temuan gelombang audit 1–3 dan bukan pernyataan seluruh kode ERP telah diaudit kembali.

Saat daftar disepakati, development plan perlu menurunkan tiap IMP menjadi perubahan yang konkret, dependensi data, migrasi bila ada, pekerjaan UI/server, dan bukti penerimaan. Status implementasi harus dibedakan dari status sudah divalidasi.

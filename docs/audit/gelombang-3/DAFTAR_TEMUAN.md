# Register seluruh temuan Gelombang 3

| ID | Prioritas | Fase | Domain | Asal | Temuan |
|---|---|---|---|---|---|
| V3-PROD-01 | P1 | 01 | MD, R&D dan master komersial | checkpoint sebelumnya | Konsumsi bahan dapat berulang setelah movement insert gagal |
| V3-PROD-02 | P1 | 01 | MD, R&D dan master komersial | checkpoint sebelumnya | Reversal dianggap selesai sebelum panjang roll dipulihkan |
| V3-MRES-01 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Dua PR mencadangkan bahan lebih banyak daripada stok |
| V3-AR-01 | P1 | 01 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Receipt gagal dibuat tetapi SO terbayar dan deposit kembali utuh |
| V3-BANK-01 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Satu baris bank dapat direkonsiliasi ke dua transaksi kas penuh |
| V3-WEIGHT-01 | P1 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Split bersamaan menggandakan berat walaupun panjang benar |
| V3-PO-01 | P2 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Task selisih PO tidak refresh dan kehilangan identitas baris |
| V3-MKO-01 | P1 | 01 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Retry penerimaan maklon menambah output fisik dan nilai stok |
| V3-RFID-01 | P1 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Read green dari passage lama dipakai kembali pada passage baru |
| V3-CF-01 | P1 | 03 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Jurnal campuran kas/nonkas menghasilkan klasifikasi arus kas salah |
| V3-DATE-01 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Jurnal date-only pada awal periode hilang dari laporan |
| V3-WMS-02 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Loading gudang siap ditahan oleh pending cut gudang lain |
| V3-MASTER-01 | P2 | 01 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Apply master mengubah produk sebelum snapshot batch durable |
| V3-PO-02 | P2 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Pilihan amend ke jumlah diterima bertentangan dengan guard PO lama |
| V3-CUT-01 | P1 | 01 | RFID, WMS dan stok | checkpoint sebelumnya | Gagal membuat child cut menghilangkan stok dan reservasi |
| V3-MRES-02 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Total cadangan maklon tetap terpotong pada batas query |
| V3-PO-03 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Tugas selisih selesai meski amendment belum disetujui dan qty belum berubah |
| V3-DUP-01 | P3 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Helper _clean_perms didefinisikan dua kali |
| V3-BUILD-01 | P2 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Dependency build frontend tidak mempunyai lockfile terlacak |
| D4-STOCK-01 | P1 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Nilai dan kecepatan stok terhitung dua kali ketika pemilik berbagi SKU dan gudang |
| D4-STOCK-02 | P2 | 04 | RFID, WMS dan stok | checkpoint sebelumnya | Filter kategori tidak diterapkan pada bucket umur stok |
| D4-STOCK-03 | P2 | 04 | RFID, WMS dan stok | checkpoint sebelumnya | Nilai persediaan analitik mengabaikan landed cost |
| D4-STOCK-04 | P2 | 04 | RFID, WMS dan stok | checkpoint sebelumnya | Tanggal roll tanpa timezone dapat menjatuhkan laporan umur stok |
| D4-FIN-01 | P1 | 03 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Control Tower menggabungkan AR semua entitas ketika parameter entitas dihilangkan |
| D4-SALES-01 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Target penjualan dan penagihan tidak mengikuti scope entitas |
| D4-SALES-02 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Sales Home masih menampilkan order dan piutang lintas entitas di kartu pelanggan |
| D4-SALES-03 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Komisi per-SKU memasukkan SO tim sales milik entitas lain |
| D4-FIN-02 | P1 | 03 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Forecast kas memakai basis AR dan termin berbeda dari AR kanonis |
| D4-FIN-03 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Revenue profitabilitas memasukkan PPN included dan mengabaikan diskon header legacy |
| D4-FIN-04 | P2 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Label pendapatan realisasi sebenarnya memakai pesanan reserved dan WAC terkini |
| D4-AI-01 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Analytics AP mengabaikan fallback vendor bill yang masih dipakai sumber kanonis |
| D4-AI-02 | P2 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Metric pelanggan baru mengabaikan scope lini |
| D4-AI-03 | P2 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Refresh fact sales menghapus data lama sebelum replacement berhasil |
| D4-AI-04 | P2 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Pembulatan alokasi tim sales tidak mengonservasi nilai dokumen |
| D4-AI-05 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Stok tersedia dan reserved di live analytics serta snapshot mengabaikan reservasi parsial |
| D4-AI-06 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Total quantity lintas produk menjumlahkan meter dengan kilogram |
| D4-CASH-01 | P1 | 03 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Saldo awal kas kecil berpindah menjadi kas besar setelah transaksi terakhir di-void |
| D4-DASH-01 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Batas katalog 3.000 SKU masih menghilangkan master dan cadangan pada KPI |
| D4-HR-01 | P1 | 04 | HR dan KPI | checkpoint sebelumnya | Payroll gabungan memakai satu run pada KPI dan menimpa run lain pada trend |
| D4-HR-02 | P2 | 04 | HR dan KPI | checkpoint sebelumnya | Turnover menggunakan waktu edit data sebagai waktu karyawan keluar |
| D4-WMS-01 | P2 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | RFID RED hari ini pada Warehouse Health memakai hari UTC |
| D4-WMS-02 | P2 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Cycle count terbaru yang belum selesai menghapus angka akurasi terakhir |
| D4-WMS-03 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Utilisasi gudang mengabaikan struktur Rack→Level→Bin yang didukung master |
| D4-MKT-01 | P2 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Reach agregat post disajikan ulang sebagai reach tiap platform dan akun |
| D4-RND-01 | P2 | 04 | MD, R&D dan master komersial | checkpoint sebelumnya | KPI R&D menggabungkan orang berbeda yang mempunyai nama sama |
| D4-FE-01 | P2 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Grafik velocity Manager selalu memotong menjadi14hari |
| D4-FE-02 | P1 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Respons periode lama dapat menimpa grafik setelah periode diganti |
| D4-TEST-01 | P2 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Tes konsistensi ATP dapat lulus walaupun mencatat mismatch |
| D4-DATE-01 | P2 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Penjualan dan Home menggunakan bulan/tahun UTC yang berbeda dari periode bisnis WIB |
| D4-PLAN-01 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Rencana pembelian mencatat qty yang berbeda dari PR yang dirujuk |
| D4-PLAN-02 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Baris produk ganda pada API rencana dapat membuat pembelian melebihi kekurangan |
| D4-PLAN-03 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Riwayat mengatakan pemenuhan penuh walaupun sebagian eksekusi gagal |
| D4-PLAN-04 | P2 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Pesan kegagalan pemenuhan parsial terhapus oleh refresh otomatis |
| D4-PLAN-05 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Pasokan masuk yang sama dapat direncanakan penuh untuk beberapa SO |
| D4-GLOBAL-01 | P1 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Barang datang 100 yard dilabelkan 100 meter pada katalog stok global |
| D4-SUPPLY-01 | P1 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Sisa PO diterima sebagian hilang dari incoming karena definisi status berbeda |
| D4-BACKORDER-01 | P1 | 01 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Pemenuhan stok bersamaan mereservasi 160 untuk SO yang hanya kurang 100 |
| D4-CAP-01 | P1 | 02 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | SKU yang benar-benar ada ditolak saat membuat PO setelah 1.000 master pertama |
| D4-ORDER-01 | P1 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Rata-rata pesanan membagi revenue seluruh pesanan dengan hanya 20 pesanan terbaru |
| D4-CASE-01 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Refund store credit menjurnal pengurangan kewajiban dua kali dan menciptakan pendapatan semu |
| D4-CASE-02 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Penyelesaian kasus keuangan dapat mengulang kas yang sudah tercatat setelah konflik atau kegagalan |
| D4-INTERCO-01 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Transfer roll retur dapat selesai memindahkan pemilik tetapi kehilangan jurnal pasangan dan dokumen pemulihan |
| D4-INTERCO-02 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Nilai transfer antarentitas memakai WAC sesudah stok sumber dipindahkan |
| D4-DOC-01 | P2 | 05 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Pratinjau Template Dokumen Dasar memanggil endpoint yang tidak tersedia dan mengabaikan jenis template |
| D4-CASE-03 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Alur dana dipegang karyawan tidak menjaga urutan langkah dan sisa piutang |
| D4-CLOSE-01 | P2 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Reopen bulan tidak menandai penutupan tahun yang bergantung padanya sebagai basi |
| D4-CLOSE-02 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Tutup ulang gagal mengadopsi jurnal yang sudah tersimpan sehingga recovery admin tetap gagal |
| D4-GL-01 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Jurnal manual yang sudah dibalik masih dapat dianulir dan membentuk pembatalan dua kali |
| D4-GL-02 | P1 | 01 | Finance dan kontrol pembayaran | checkpoint sebelumnya | Jurnal manual meloloskan NaN/Infinity dan menghilangkan angka transaksi sah dari laporan |
| D4-EQ-01 | P1 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | KPI Laba Periode Berjalan pada perubahan ekuitas berubah menjadi nol sesudah tutup buku |
| D4-COA-01 | P1 | 03 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | Mode Semua Entitas pada laporan keuangan menghilangkan akun khusus entitas yang sah |
| D4-PA-01 | P1 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Reservasi SO mengambil roll yang sudah diklaim putaway dan meninggalkan lokasi alokasi lama |
| D4-PA-02 | P1 | 01 | RFID, WMS dan stok | checkpoint sebelumnya | Putaway kehilangan checkpoint setelah roll berpindah sehingga recovery stok dan tag gagal |
| D4-PA-03 | P2 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Total putaway menjumlahkan meter dan yard lalu memberi satu label satuan |
| D4-WMS-04 | P2 | 04 | Sales, procurement, logistik dan consumer lain | checkpoint sebelumnya | KPI antrean simpan menghitung roll reserved yang tidak boleh diputaway |
| D4-RFID-01 | P1 | 01 | RFID, WMS dan stok | checkpoint sebelumnya | Deduplikasi event RFID melewati recovery keputusan, insiden dan status passage |
| D4-CC-01 | P2 | 01 | RFID, WMS dan stok | checkpoint sebelumnya | Recovery cycle count membuat dua laporan dan nomor untuk satu sesi |
| D4-TAG-01 | P1 | 02 | RFID, WMS dan stok | checkpoint sebelumnya | Verifikasi tag lama tetap berlaku setelah tag dihapus atau diganti dengan tag pending |
| D4-SIM-01 | P2 | 04 | Sales, procurement, logistik dan consumer lain | tambahan | Simulator menyatakan 3-way match lolos saat barang belum diterima |
| D4-BANK-01 | P2 | 04 | Finance dan kontrol pembayaran | tambahan | Tanggal kalender yang tidak mungkin masuk ke data rekonsiliasi bank |
| D4-BANK-02 | P2 | 04 | Finance dan kontrol pembayaran | tambahan | Parser MT940 tidak membaca kode pembalikan transaksi RC dan RD |
| D4-ASSET-01 | P1 | 01 | Finance dan kontrol pembayaran | tambahan | Penyusutan yang gagal mengunci periode sehingga retry tidak memperbaiki aset |
| D4-ASSET-02 | P1 | 01 | Finance dan kontrol pembayaran | tambahan | Penyusutan dua periode bersamaan membuat register aset tertinggal dari jurnal |
| D4-ICLOAN-01 | P1 | 02 | Finance dan kontrol pembayaran | tambahan | Akun Finance dapat mengubah pinjaman entitas yang tidak ditugaskan kepadanya |
| D4-RFQ-01 | P1 | 02 | Sales, procurement, logistik dan consumer lain | tambahan | Award RFQ tetap membuat PO untuk item yang dinyatakan tidak tersedia |
| D4-RFQ-02 | P1 | 02 | Sales, procurement, logistik dan consumer lain | tambahan | Perbandingan dan pembatalan RFQ tidak mengikuti pembatasan entitas pada halaman detail |
| D4-CB-01 | P2 | 05 | Finance dan kontrol pembayaran | tambahan | Pemeriksa kontrabon dapat memberi hasil bersih karena hanya memeriksa 2.000 dokumen pertama |
| D4-UOM-BF-01 | P2 | 03 | Sales, procurement, logistik dan consumer lain | tambahan | Backfill jumlah roll memakai panjang daftar ID mentah, berbeda dari resolver roll nyata |
| D4-RET-CHAIN-01 | P2 | 04 | Sales, procurement, logistik dan consumer lain | tambahan | Ringkasan fisik rantai retur menjumlahkan barang berlainan satuan menjadi satu angka |
| D4-ALERT-DATE-01 | P2 | 04 | Sales, procurement, logistik dan consumer lain | tambahan | Peringatan AP menyebut jatuh tempo hari ini sudah terlambat satu hari |
| D4-ALERT-AMT-01 | P2 | 04 | Sales, procurement, logistik dan consumer lain | tambahan | Peringatan utang menampilkan nominal penuh meskipun pembayaran sebagian sudah tercatat |
| D4-ALERT-WMS-01 | P1 | 02 | Sales, procurement, logistik dan consumer lain | tambahan | Notifikasi tugas WMS mencampur pesanan dua entitas yang memakai gudang sama |
| D4-PRICE-SCOPE-01 | P1 | 02 | Sales, procurement, logistik dan consumer lain | tambahan | Scope harga khusus berbeda antara detail, perubahan, harga efektif dan ringkasan |
| D4-OD-LOCK-01 | P1 | 01 | MD, R&D dan master komersial | tambahan | Kegagalan pembaruan SKU meninggalkan harga OD terkunci dan pengulangan tidak dapat memulihkannya |
| D4-COMM-BOUNDS-01 | P1 | 03 | MD, R&D dan master komersial | tambahan | Perubahan master komersial melewati batas angka dan dapat menghasilkan ongkos makloon negatif |
| D4-KPI-WEIGHT-01 | P2 | 04 | HR dan KPI | tambahan | Bobot KPI nol menjadi satu dan mengubah rata-rata tertimbang |
| D4-KPI-PERIOD-01 | P2 | 04 | HR dan KPI | tambahan | Periode KPI yang bukan bulan kalender diterima dan dipilih sebagai periode terbaru |
| D4-KPI-SCORE-01 | P2 | 04 | HR dan KPI | tambahan | Skor otomatis KPI dapat negatif meskipun kontrak fungsi menyatakan rentang 0–150 |
| D4-BUD-EDIT-01 | P1 | 03 | Finance dan kontrol pembayaran | tambahan | Perubahan anggaran melewati keunikan periode/kunci dan batas tahun |
| D4-BUD-THRESHOLD-01 | P2 | 04 | Finance dan kontrol pembayaran | tambahan | Ambang peringatan anggaran 0% berubah menjadi 85% pada laporan |
| D4-RET-POLICY-01 | P1 | 02 | Sales, procurement, logistik dan consumer lain | tambahan | Deadline retur dapat berubah karena PO terbaru entitas lain dengan produk yang sama |

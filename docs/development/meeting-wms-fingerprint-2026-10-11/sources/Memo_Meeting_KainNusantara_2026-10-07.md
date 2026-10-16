# Memo Catatan Meeting ERP KainNusantara

Penyelarasan alur kerja, tampilan per peran dan master data

**Tanggal meeting:** 7 Oktober 2026  
**Disusun:** 8 Oktober 2026

**Status:** memo kebutuhan dan penyelarasan; keputusan yang belum final ditandai secara eksplisit.

## Tujuan dan dasar pembacaan

Memo merapikan 20 poin arahan klien dan menghubungkannya dengan konteks ERP. Arahan meeting adalah kebutuhan yang disampaikan; konteks sistem merangkum kode yang ditelusuri; tindak lanjut merupakan usulan penerapan. Poin tersebut tidak otomatis sudah diimplementasikan atau menjadi keputusan final klien.

Konteks teknis memakai snapshot `f59b8a60d7b7e078888c537ca93c046afae460a9` pada repo KNHOST. Penelusuran ini bukan pengujian aplikasi berjalan. Menu dapat berbeda menurut peran/hak akses.

**Klarifikasi terkonfirmasi:** greige, PFD dan PFP tidak tampil di katalog Sales, namun tetap tersedia bagi MD, pembelian dan gudang.

**Penyelarasan istilah:** Keep adalah SO belum diverifikasi; Pending adalah kebutuhan barang yang masih menunggu pemenuhan. Dua kondisi ini dapat terjadi pada SO yang sama dan tidak boleh dihitung dua kali.

## Meja pengguna dan definisi pesanan

### U-01 - Meja pengguna: setiap antrean membuka detail proses

**Arahan meeting.** Setiap baris data pada meja pengguna dapat diklik untuk membuka informasi lebih rinci yang berkaitan dengan pekerjaan pada baris tersebut. Detail harus membantu pengguna memahami kondisi terakhir dan tindakan berikutnya.

**Konteks sistem.** Sistem mempunyai meja Admin Sales, MD, Finance, Gudang dan Sampel. Sebagian antrean sudah membuka dokumen atau dialog tindakan; arahan meeting adalah konsistensi pada seluruh daftar yang relevan.

**Tindak lanjut yang disarankan.** Detail menampilkan nomor dokumen, artikel/warna, qty dan roll bila relevan, status, kendala, histori serta PIC/tindakan berikutnya. Pengguna kembali ke antrean dengan filter semula. Detail dan angka ringkasan memakai sumber data serta cakupan akses yang sama.

**Area/menu terkait.** Kerja Saya > Meja Peran; atau meja yang langsung muncul untuk peran pengguna.

### S-01 - Pending dan Keep: definisi bisnis serta tampilan khusus Sales

**Arahan meeting.** Pending adalah kebutuhan barang pada SO yang masih menunggu pemenuhan/backorder, termasuk pengadaan internal antar entitas dan restock melalui PR. Keep adalah SO yang sudah dibuat tetapi belum diverifikasi Admin Sales.

**Konteks sistem.** Verifikasi administrasi dan ketersediaan barang merupakan dua dimensi berbeda. SO yang belum diverifikasi dapat sekaligus mempunyai barang Pending. Keep tidak otomatis sama dengan stok reserved; reservasi tetap dibaca dari catatan stok/alokasi.

**Tindak lanjut yang disarankan.** Sediakan tampilan Keep dan Pending di area Pesanan. Keep memudahkan pencarian SO belum diverifikasi. Pending dimulai dari artikel/warna dan qty kekurangan, kemudian dibuka ke SO serta referensi PR, PO, MKO atau transfer yang benar-benar ada. Tampilkan progres, ETA bila tercatat dan tindak lanjut. Jangan memaksakan nomor PO jika pengadaan masih berupa PR atau rencana.

**Area/menu terkait.** Penjualan > Pesanan > Pesanan (SO); Meja Admin Sales dan Rencana Pemenuhan.

**Menunggu klien.** Perlu dirinci aturan akhir daftar: status aktif yang dihitung, barang parsial, pengecualian batal/tolak, dan apakah Keep juga dimaksudkan sebagai batas waktu penahanan barang.


## Sales: peran, pilihan varian dan alokasi

### S-02 - Special Order: PIC, artikel existing dan desain pelanggan

**Arahan meeting.** Pengguna utama Special Order masih menunggu keputusan klien. Pesanan khusus dapat menggunakan artikel existing sebagai basis, misalnya untuk perubahan warna. Jika pelanggan sudah mempunyai desain, alur harus memungkinkan desain tersebut diterima/di-ACC lalu dilanjutkan ke proofing tanpa pekerjaan desain baru yang tidak diperlukan.

**Konteks sistem.** Menu Pesanan Khusus sudah menghubungkan brief dengan Desainer/R&D, keputusan pelanggan, harga, pengadaan dan SO. Form menyediakan Induk produk basis pada mode Spesifikasi lengkap. Jalur printing yang ditelusuri masih menjelaskan pekerjaan Desainer lalu proofing; desain milik pelanggan perlu jalur keputusan yang jelas.

**Tindak lanjut yang disarankan.** Pisahkan sumber desain: dibuat internal, desain pelanggan, atau referensi desain existing. Catat versi/bukti dan keputusan penerimaan. Jika desain siap produksi dan disetujui, lanjutkan proofing; jika perlu penyesuaian, kirim ke Desainer. Artikel existing menjadi referensi, sedangkan warna/spesifikasi baru dapat menghasilkan varian baru bila identitas barang memang berubah.

**Area/menu terkait.** Penjualan > Pesanan Khusus; Desainer > Permintaan Desain; Riset & Sampel > Proofing / Labdip.

**Menunggu klien.** Klien menentukan PIC pembuat/pengelola OD, pejabat ACC desain pelanggan, serta kriteria desain siap diteruskan ke proofing.

### S-03 - Sudut pandang Sales: varian komersial hanya warna

**Arahan meeting.** Sales melihat pilihan varian warna. LOT, grade dan asal impor/lokal tidak ditampilkan sebagai pilihan atau informasi operasional untuk Sales. Admin Sales melihat dimensi tersebut dan bertanggung jawab menentukan alokasi.

**Konteks sistem.** Master varian saat ini dapat mempunyai beberapa atribut; pemilih atribut mengenal warna, grade dan asal. Detail produk Sales yang ditelusuri masih menampilkan grade. Arahan ini merupakan perubahan presentasi dan pembagian tanggung jawab, bukan penghapusan atribut master.

**Tindak lanjut yang disarankan.** Sales memilih artikel/warna dan menyampaikan kebutuhan. Admin Sales memilih SKU/roll internal berdasarkan grade, LOT, asal dan syarat pelanggan. Informasi tersembunyi tetap dipakai stok, HPP dan traceability. Sesuaikan konsisten pada katalog, pencarian, detail SO dan layar mobile; ukuran serta jumlah roll tetap boleh ditampilkan sesuai S-09.

**Area/menu terkait.** Kasir & Portal; detail produk; Pesanan (SO); Meja Admin Sales dan layar alokasi.

**Menunggu klien.** Cara penawaran BS yang berbeda harga perlu diputuskan agar tidak bertentangan dengan tampilan warna saja; lihat S-08.

### S-04 - Admin Sales: roll picker untuk edit dan pemenuhan SO

**Arahan meeting.** Saat mengedit alokasi atau menentukan pemenuhan, Admin Sales membutuhkan pemilih roll yang jelas. Pemilihan dilakukan atas roll fisik yang tersedia, bukan hanya mengetik jumlah agregat.

**Konteks sistem.** Sistem sudah memiliki komponen pemilih roll dan rencana pemenuhan. Keberadaan komponen tersebut belum berarti seluruh layar Admin Sales telah memakai pengalaman pemilihan yang sesuai kebutuhan meeting.

**Tindak lanjut yang disarankan.** Pemilih menampilkan kode roll, ukuran aktual, satuan, LOT, grade, asal, gudang/pemilik dan status ketersediaan sesuai izin Admin Sales. Total qty dan jumlah roll dihitung dari pilihan. Roll reserved untuk kebutuhan lain atau tidak layak harus dijelaskan. Perubahan pilihan ditinjau terhadap reservasi/tugas yang sudah ada; barang milik entitas lain tetap mengikuti transaksi internal.

**Area/menu terkait.** Meja Admin Sales > Rencana Pemenuhan; detail SO > edit/alokasi yang tersedia.


## Sales: pesanan khusus, sampel dan bahan

### S-05 - Special Order: satu pesanan dapat berisi beberapa produk

**Arahan meeting.** Satu Special Order harus dapat menampung lebih dari satu artikel/produk untuk pelanggan yang sama.

**Konteks sistem.** Form OD yang ditelusuri memakai satu spesifikasi dan satu jumlah/satuan utama. Pilihan beberapa jenis uji tidak sama dengan beberapa produk dalam satu pesanan.

**Tindak lanjut yang disarankan.** Sediakan baris produk; tiap baris mempunyai referensi artikel, warna/spesifikasi, qty, satuan, desain/uji, harga, tenggat dan progres. Hubungan ke SKU, pengadaan dan SO ditelusuri per baris. Status keseluruhan mencerminkan seluruh baris; satu produk selesai tidak otomatis menyelesaikan produk lainnya.

**Area/menu terkait.** Penjualan > Pesanan Khusus; rantai dokumen OD ke R&D, PR/PO/MKO dan SO.

**Menunggu klien.** Aturan pengiriman/ACC parsial serta pemisahan SO atau dokumen pengadaan antarproduk perlu diputuskan sesuai kebutuhan klien.

### S-06 - Sampel: Hanger, Katalog dan Cutting; proses setelah pemotongan

**Arahan meeting.** Jenis sampel yang tampil bagi Sales adalah Hanger, Katalog dan Cutting. Aturan masing-masing jenis masih menunggu klien. Untuk sampel cutting, setelah dipotong Gudang, barang kembali ke Admin Cutting untuk diproses; pengiriman menjadi tanggung jawab Admin Cutting setelah tahap tersebut.

**Konteks sistem.** Sistem sudah memisahkan Pesanan Sampel (SOS), skema Gratis/Berbayar, meja Admin Sampel dan tugas potong Gudang. Jenis fisik sampel berbeda dari skema pembayaran dan berbeda dari sampling R&D seperti Labdip/Proofing/Handfeel.

**Tindak lanjut yang disarankan.** Alur cutting yang dituju: permintaan Sales > pemeriksaan/ACC yang berlaku > tugas potong Gudang > serah terima hasil ke Admin Cutting > proses akhir > kirim/serah terima dan bukti. Tambahkan status antrean serta qty hasil aktual. Pengembalian hasil potong ke Admin Cutting tidak mencatat penerimaan stok baru atau konsumsi roll sumber kedua kali.

**Area/menu terkait.** Kasir & Portal > sampel; Penjualan > Pesanan Sampel; Meja Sampel; Barang Keluar > tugas sampel.

**Menunggu klien.** Belum diputus: Admin Cutting adalah nama operasional Admin Sampel atau peran terpisah; batas qty/harga/biaya Hanger-Katalog-Cutting; proses akhir, PIC dan kriteria siap kirim.

### S-07 - Bahan baku: greige, PFD dan PFP tidak tampil di katalog Sales

**Arahan meeting.** Sudah dikonfirmasi: greige, PFD dan PFP tidak ditampilkan di katalog Sales, tetapi tetap tersedia bagi MD, pembelian dan gudang.

**Konteks sistem.** Sistem mempunyai Tahap bahan yang membedakan Grey/Greige, PFD, PFP dan Finished. Tahap berbeda dari jenis kain woven/knit maupun lini/proses printing.

**Tindak lanjut yang disarankan.** Gunakan klasifikasi tahap dan aturan kelayakan jual untuk menyaring semua pintu pemilihan produk Sales. Master, stok, bahan makloon dan penerimaan tetap menyimpan bahan tersebut. Penyembunyian katalog tidak menghapus data atau membuat bahan menjadi barang jadi.

**Area/menu terkait.** Kasir & Portal; pilihan produk Sales/SO; Produk & Varian; pengadaan dan stok MD/Gudang.


## Sales: kebijakan grade dan informasi SO

### S-08 - Grade: harga non-BS sama, alokasi berbasis rekomendasi

**Arahan meeting.** Untuk artikel/warna, satuan dan kondisi komersial yang sama, grade selain BS mempunyai harga jual yang sama. BS mempunyai perlakuan harga berbeda. Admin Sales mengalokasikan grade sesuai kebutuhan pelanggan; sistem memberi rekomendasi berdasarkan aturan klien yang belum diterima.

**Konteks sistem.** Grade tetap menjadi atribut kualitas/stock. Kesamaan harga tidak menggabungkan identitas roll, mutu atau HPP. Harga khusus pelanggan/badan usaha tetap dapat berbeda; arahan ini menyamakan dampak grade non-BS, bukan seluruh harga produk.

**Tindak lanjut yang disarankan.** Kebutuhan pelanggan dengan standar tinggi dapat merekomendasikan grade A; kebutuhan lain dapat memakai grade yang lebih rendah bila memenuhi standar. Kriteria minimum/larangan dan prioritas efisiensi harus eksplisit. Tampilkan alasan rekomendasi dan biarkan Admin Sales meninjau/memilih; jangan membuat alokasi otomatis berdasarkan dugaan kelas pelanggan.

**Area/menu terkait.** Produk & Harga; profil kebutuhan pelanggan; Meja Admin Sales > pemenuhan/roll picker.

**Menunggu klien.** Menunggu matriks standar pelanggan-versus-grade, aturan rekomendasi/pengecualian dan cara menawarkan BS saat Sales hanya melihat warna.

### S-09 - SO: kuantitas, satuan dan rincian roll selalu jelas

**Arahan meeting.** Semua tampilan produk pada detail SO harus menunjukkan qty beserta satuannya dan jumlah roll terkait. Daftar SO juga menyediakan informasi roll, termasuk kode dan ukuran per roll dalam yard, meter atau kg.

**Konteks sistem.** Qty jual, jumlah roll dan ukuran aktual bukan angka yang saling menggantikan. Sebelum alokasi, jumlah roll dapat belum ditentukan; setelah alokasi/dispatch, jumlah serta ukuran mengikuti roll dan dokumen yang benar-benar tercatat.

**Tindak lanjut yang disarankan.** Tampilkan qty dipesan, qty dialokasikan, qty dikirim dan sisa secara jelas; ringkasan roll dapat dibuka menjadi rincian kode/ukuran. Contoh: 1.005 yard - 10 roll, dengan daftar panjang tiap roll. Angka rencana dibedakan dari aktual. Jangan menjumlahkan yard, kg dan roll menjadi satu total tanpa konversi yang sah; jangan mengasumsikan tiap roll berukuran 100 yard.

**Area/menu terkait.** Daftar/detail SO; Meja Admin Sales; alokasi; picking; shipment/SJ sesuai dokumen dan izin peran.


## Master data yang disiapkan klien

### M-01 - Data bahan: klien menyiapkan greige, PFD dan PFP

**Arahan meeting.** Klien menyiapkan daftar master bahan greige, PFD dan PFP sebagai dasar stok serta proses makloon.

**Konteks sistem.** Bahan dapat menjadi SKU. Pembentukan master bahan tidak wajib mengikuti seluruh uji produk hasil pengembangan MD. Bahan yang berbeda tahap/spec tidak boleh disamakan hanya karena nama mirip.

**Tindak lanjut yang disarankan.** Data minimum yang perlu disiapkan: kode/nama internal, tahap, jenis/lini, satuan dasar, spesifikasi yang relevan, hubungan bahan-output/resep dan sumber pengadaan. Lengkapi lebar/GSM bila dibutuhkan konversi. Data stok awal per gudang/pemilik/LOT/roll disiapkan sebagai dataset terpisah dari definisi master.

**Area/menu terkait.** Penjualan > Produk & Harga > Produk & Varian / Satuan & Konversi; Master Pembelian > Resep Proses.

**Menunggu klien.** PIC, kelengkapan data, format impor dan jadwal penyerahan ditentukan klien.

### M-02 - Data supplier: kode, nama barang dan warna versi supplier

**Arahan meeting.** Klien menyiapkan identitas supplier dan pemetaan kode/nama barang serta warna menurut supplier.

**Konteks sistem.** Sistem mempunyai Pemasok, Barang Supplier, Pustaka Warna dan kontrak. Nama/kode supplier adalah alias/pemetaan terhadap artikel/SKU internal; bukan alasan mengganti kode internal atau LOT.

**Tindak lanjut yang disarankan.** Daftar memuat supplier, kode/nama barang versi supplier, kode/nama warna supplier, artikel/warna internal tujuan, satuan dan spesifikasi terkait. Satu barang internal dapat mempunyai beberapa pemasok/alias. Kode warna pelanggan tetap dibedakan dari kode supplier. Tampilkan pemetaan pada master, PO dan penerimaan agar barang dikenali konsisten.

**Area/menu terkait.** Pembelian > Master Pembelian; Penjualan > Produk & Harga > Pustaka Warna.

**Menunggu klien.** Klien mengirim data asli beserta pasangan internal yang sudah diketahui; pasangan yang belum jelas ditinjau sebelum dipakai transaksi.


## MD: kualitas, R&D existing dan informasi produk

### D-01 - Pisahkan MD Quality dari QC

**Arahan meeting.** Meeting meminta pembedaan MD Quality dan QC. Menurut catatan klien, layar/fungsi yang sekarang disebut QC lebih dekat dengan kebutuhan MD Quality; QC yang dimaksud klien terutama pemeriksaan retur atau random check.

**Konteks sistem.** Kode yang ditelusuri memiliki QC kedatangan dengan efek karantina/release stok, dokumen inspeksi dan inspeksi retur. Karena itu perubahan tidak cukup berupa mengganti nama menu. Makna MD Quality dan tahap penerapannya belum dirinci sepenuhnya.

**Tindak lanjut yang disarankan.** Petakan kegiatan yang termasuk MD Quality dan yang termasuk QC, berikut PIC, objek pemeriksaan, bukti, hasil serta akibatnya pada stok/alokasi. R&D/spec, pemeriksaan mutu hasil produksi/kedatangan, retur dan random check perlu diberi posisi yang jelas. Kontrol pelepasan barang yang sudah ada harus tetap mempunyai penanggung jawab setelah penataan.

**Area/menu terkait.** Riset & Sampel; Operasi Gudang > QC & Inspeksi; retur penjualan/pembelian.

**Menunggu klien.** Klien menentukan definisi MD Quality, titik pemeriksaan, apakah QC kedatangan tetap diperlukan, serta cakupan dan aturan random check.

### D-02 - Uji R&D lanjutan atas barang existing tanpa master duplikat

**Arahan meeting.** Barang yang sudah menjalani Labdip dapat dilanjutkan ke Handfeel tanpa membuat master/SKU baru; demikian pula sebaliknya. Permintaan R&D perlu dapat mereferensikan barang existing.

**Konteks sistem.** Form/layanan saat ini mempunyai referensi induk dan SKU target, tetapi jalur yang ditelusuri menolak SKU yang sudah dirilis atau sudah terhubung spesifikasi. Dengan demikian, memilih SKU konsep berbeda dari kebutuhan pengujian tambahan pada SKU aktif.

**Tindak lanjut yang disarankan.** Bedakan pengembangan produk baru dengan pengujian tambahan/revalidasi produk existing. Untuk uji tanpa perubahan identitas, simpan request, ronde, hasil, keputusan dan hubungan ke SKU yang sama; jangan ulangi kelahiran SKU. Jika hasil uji mengubah warna/konstruksi sehingga identitas barang berbeda, putuskan varian/spec baru melalui jalur resmi.

**Area/menu terkait.** Riset & Sampel > Permintaan Sample / Labdip / Handfeel; hubungan ke Produk & Varian.

**Menunggu klien.** Tentukan apakah hasil uji hanya catatan mutu atau mengubah spesifikasi aktif, siapa approver, dan kapan SKU existing perlu ditahan atau dirilis ulang.

### D-03 - Master produk: supplier, warna supplier dan tindakan pengelolaan

**Arahan meeting.** Detail produk harus lebih lengkap, khususnya informasi nama supplier, nama/kode barang supplier dan warna supplier. Aksi tambah, edit dan hapus/nonaktif perlu mempunyai cakupan serta akibat yang jelas.

**Konteks sistem.** Master sudah mempunyai induk, varian, informasi spesifikasi serta referensi supplier; pemetaan barang/warna supplier juga berada pada master pembelian/warna. Satu field Supplier pada ringkasan bukan pengganti daftar pemetaan lengkap.

**Tindak lanjut yang disarankan.** Tampilkan relasi supplier/mitra yang relevan beserta item/warna mereka dan status pemetaan. Bedakan mengubah induk, varian, alias supplier, spesifikasi atau harga. Pada penghapusan/nonaktif, jelaskan dependensi stok/transaksi; rekomendasi untuk data yang sudah dipakai adalah menonaktifkan/mengarsipkan dengan jejak, bukan memutus histori.

**Area/menu terkait.** Produk & Harga > Produk & Varian; Master Pembelian > Barang Supplier; Pustaka Warna.


## MD: pencarian produk dan sumber restock

### D-04 - Produk & Varian: filter yang lengkap dan konsisten

**Arahan meeting.** Lengkapi filter master produk agar MD dapat membedakan barang berdasarkan jenis, tahapan dan klasifikasi lain yang relevan.

**Konteks sistem.** Master sudah menyimpan kategori, jenis kain, tahap, lini, motif dan atribut varian. Layar katalog induk yang ditelusuri menonjolkan pencarian teks; dimensi tersebut perlu tersedia sebagai filter terstruktur sesuai peran.

**Tindak lanjut yang disarankan.** Prioritas filter: jenis kain, tahap bahan, lini/kategori, warna/motif, supplier dan status lifecycle. Tambahkan metode restock dari D-06 saat tersedia. Sediakan gabungan filter, jumlah hasil dan reset. Gunakan nilai master yang konsisten; label Greige tidak membuat kategori kedua yang terpisah dari Grey/Greige pada registry.

**Area/menu terkait.** Penjualan > Produk & Harga > Produk & Varian untuk MD/pengelola master; pembatasan Sales mengikuti S-03/S-07.

### D-05 - Ketersediaan greige dan jejak pemakaian makloon

**Arahan meeting.** Karena greige memiliki banyak jenis, MD perlu mengetahui stok bahan yang tepat untuk artikel/resep. Sistem harus memberi informasi kekurangan bahan sebelum keputusan pemenuhan produksi dan menjelaskan perubahan stok ketika bahan dipakai.

**Konteks sistem.** Rencana pemenuhan, PR proses, reservasi bahan, issue ke mitra dan WIP adalah tahap berbeda. Jalur PR proses yang disetujui dapat mencadangkan bahan; issue memindahkan bahan fisik ke proses makloon. Qty output tidak selalu sama dengan bahan yang dibutuhkan.

**Tindak lanjut yang disarankan.** Tampilkan stok fisik, cadangan/komitmen, tersedia, incoming dan kebutuhan per resep/SO/MKO. Contoh dengan asumsi bahan 1:1: dari 1.000 yard, reservasi 600 menyisakan tersedia 400; saat 600 di-issue, bahan menjadi WIP dan saldo gudang 400, bukan dikurangi dua kali. Perhitungan nyata mengikuti resep/yield dan satuan yang benar. Kekurangan harus terlihat beserta tindak lanjut MD sebelum janji produksi diberikan.

**Area/menu terkait.** Meja MD; Stok & ATP; detail PR proses dan Order Makloon > bahan/issue/costing.

**Menunggu klien.** Menunggu hubungan jenis greige ke artikel/resep, yield, lead time serta batas/peringatan restock yang disetujui klien.

### D-06 - Master artikel: sumber restock supplier, makloon atau keduanya

**Arahan meeting.** Tidak semua artikel dapat dibeli langsung dari supplier. Master perlu menunjukkan artikel yang direstock melalui pembelian supplier, makloon saja, atau keduanya.

**Konteks sistem.** Sistem mempunyai jalur PR Beli dan Proses via Makloon, PO dan MKO. Pilihan jalur pada transaksi perlu mengikuti kemampuan artikel, bukan menawarkan seluruh jalur untuk setiap barang.

**Tindak lanjut yang disarankan.** Untuk pembelian: PR > PO > terima. Untuk makloon: PR proses/resep > cadangkan bahan > MKO > issue > terima hasil. Untuk keduanya: MD/Admin Sales memilih berdasarkan stok, kesiapan bahan, biaya dan waktu. Kekurangan bahan/kapasitas harus terlihat. Pembatasan sumber restock tidak menghapus opsi memenuhi SO dari stok siap atau pengadaan antar entitas yang sah.

**Area/menu terkait.** Produk & Varian; Pengadaan > Permintaan Pembelian; Meja Admin Sales > pemenuhan; Order Makloon.

**Menunggu klien.** Klien menyiapkan klasifikasi artikel, supplier/mitra/resep yang diizinkan, lead time dan aturan pilihan prioritas. Tempat penyimpanan aturan mengikuti master yang menjadi sumber kebenaran agar tidak dibuat dua aturan berbeda.


## Gudang: cakupan lokasi dan OCR

### W-01 - Gudang: meja dan aktivitas mengikuti lokasi pengguna

**Arahan meeting.** Admin Gudang Bandung tidak perlu melihat antrean pekerjaan Gudang Jakarta, walaupun keduanya berada dalam badan usaha yang sama. Stok, tugas dan aktivitas kerja perlu dibedakan menurut lokasi.

**Konteks sistem.** Sistem mempunyai gudang/lokasi dan pengaturan gudang bersama atau khusus entitas. Pembatasan pemakaian gudang oleh badan usaha berbeda dari penugasan pengguna ke lokasi; konfigurasi entitas saja tidak menjawab kebutuhan ini.

**Tindak lanjut yang disarankan.** Tetapkan lokasi/gudang kerja pengguna dan terapkan cakupannya pada meja, jumlah antrean, detail serta notifikasi. Visibilitas pekerjaan harus sesuai lokasi. Hak melihat atau mengambil alih pekerjaan lintas gudang ditetapkan terpisah untuk supervisor/koordinator. Perubahan ini tetap mempertahankan ringkasan stok global Sales sesuai kebijakan penjualan.

**Area/menu terkait.** Pengaturan pengguna/peran; Data Gudang; Meja Gudang; Barang Masuk/Keluar, QC, transfer dan RFID.

**Menunggu klien.** Klien menetapkan pemetaan pengguna-lokasi dan pejabat yang boleh membaca/menindak pekerjaan lintas gudang.

### W-02 - OCR SJ: jumlah roll dan ukuran per roll sebagai kandidat penerimaan

**Arahan meeting.** OCR harus membaca jumlah roll serta panjang/qty tiap roll bila informasi tersebut tertulis pada SJ/packing list, sehingga pengguna tidak perlu mengetik seluruh ukuran satu per satu.

**Konteks sistem.** Schema OCR sudah mengenal jumlah/panjang/berat dan packing list per roll. Ekstraksi packing list mengikuti konfigurasi; hasil dapat menjadi expected rolls. Pada panel hitung yang ditelusuri, memilih expected roll membantu LOT/grade, sedangkan ukuran aktual masih diisi. Data dokumen dan hasil hitung fisik perlu tetap dibedakan.

**Tindak lanjut yang disarankan.** Sediakan review/import kandidat roll hasil OCR secara kelompok, dengan artikel/warna, LOT, kode/urutan roll, ukuran dan satuan. Pengguna mengoreksi hasil yang ragu, mencocokkan jumlah roll serta total, lalu memvalidasi fisik menurut SOP. Simpan ukuran dokumen dan koreksi aktual. Jika SJ hanya memuat total, jangan membagi rata menjadi ukuran setiap roll tanpa data.

**Area/menu terkait.** Operasi Gudang > Barang Masuk > Tinjau SJ / Hitung fisik / Rekonsiliasi; Pengaturan > Penerimaan & OCR.

**Menunggu klien.** Klien memberi contoh SJ/packing list, format label dan SOP validasi fisik. Tentukan apakah ukuran dokumen boleh diadopsi setelah review atau wajib diukur ulang untuk kategori tertentu.


## Keputusan dan data yang masih ditunggu

Fungsi di kolom kanan merupakan usulan pihak yang dimintai jawaban; nama PIC dan tenggat belum diberikan.

| Poin | Informasi/keputusan | Fungsi yang dimintai jawaban |
|---|---|---|
| S-02 | PIC Special Order; pejabat ACC desain pelanggan; desain siap proofing | Klien / kepala Sales dan MD |
| S-05 | ACC/pengiriman parsial dan pemecahan dokumen untuk OD multi-produk | Klien / Sales, MD dan operasional |
| S-06 | Admin Cutting sama dengan Admin Sampel atau peran baru; SOP setelah cutting; rules 3 jenis sampel | Klien / PIC sampel |
| S-08 | Cara menawarkan BS; standar pelanggan, grade minimum dan aturan rekomendasi | Klien / Sales dan MD |
| S-01 | Batas Keep/Pending, pengecualian status dan kebijakan penahanan barang jika diperlukan | Klien / Admin Sales |
| D-01, D-02 | Batas MD Quality/QC, random check dan akibat uji tambahan pada SKU aktif | Klien / MD dan Gudang |
| D-05, D-06 | Pemetaan bahan-resep-artikel; sumber restock; yield/lead time dan prioritas | Klien / MD |
| M-01, M-02 | Master bahan serta kode/nama barang/warna supplier | Klien / PIC master data |
| W-01, W-02 | Pengguna-lokasi; akses lintas lokasi; contoh SJ dan SOP adopsi ukuran OCR | Klien / Gudang |

## Urutan tindak lanjut yang disarankan

1. Validasi definisi, pembagian peran dan keputusan terbuka; lengkapi PIC dan tenggat.
2. Lengkapi master bahan/supplier dan SOP grade, restock, sampel, kualitas serta cakupan lokasi.
3. Petakan setiap kode poin ke pekerjaan pengembangan, dampak antar modul dan skenario UAT. Prioritaskan master/sumber data serta aturan bisnis sebelum penyelesaian tampilan.

## Rujukan konteks sistem

Snapshot: `f59b8a60d7b7e078888c537ca93c046afae460a9`. Rujukan adalah titik masuk kode untuk konteks memo, bukan inventaris seluruh kode atau bukti kelulusan pengujian.

- Meja dan pemenuhan: [frontend/src/features/sales_admin/SalesAdminDesk.jsx](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/features/sales_admin/SalesAdminDesk.jsx)
- Tampilan grade Sales: [frontend/src/components/ProductQuickView.jsx](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/components/ProductQuickView.jsx)
- Form Special Order: [frontend/src/features/sales/CreateSpecialOrderForm.jsx](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/features/sales/CreateSpecialOrderForm.jsx)
- Katalog dan detail: [frontend/src/features/catalog/CatalogWorkspace.jsx](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/features/catalog/CatalogWorkspace.jsx)
- SKU existing untuk R&D: [frontend/src/features/catalog/SpecVariantFields.jsx](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/features/catalog/SpecVariantFields.jsx)
- ACC spesifikasi R&D: [backend/services/rnd_spec_service.py](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/rnd_spec_service.py)
- QC kedatangan: [frontend/src/features/wms/QCInspection.jsx](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/features/wms/QCInspection.jsx)
- Gudang dan entitas: [backend/services/warehouse_scope_service.py](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/warehouse_scope_service.py)
- OCR packing list: [backend/services/goods_receipt_ocr_service.py](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/goods_receipt_ocr_service.py)
- Hitung fisik GRN: [frontend/src/features/wms/grn/GrnCountPanel.jsx](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/frontend/src/features/wms/grn/GrnCountPanel.jsx)

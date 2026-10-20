# Prompt perbaikan frontend dan rantai terkait

ERP Kain Nussantara — PT Kubus Teknologi Indonesia  
Acuan temuan: `8dab383f764df80737bfe02f887422b3fd72aa70`, 20 Oktober 2026.

Paket ini adalah arahan perbaikan dari audit, belum bukti implementasi. Baca `AUDIT_FRONTEND_2026-10-20.md` dan JSON/harness domain terkait. Saat mulai, catat SHA yang dikerjakan dan cek apakah temuan masih berlaku. Pertahankan keputusan bisnis yang sudah disahkan dalam plan; jangan menambah toleransi, aturan grade, atau kewenangan baru berdasarkan asumsi.

## Fase UI-01 — Special Order multi-produk sampai SO

Perbaiki FE-01. Form dan pengadaan sudah mengenal item, tetapi pricing dan konversi masih membaca header legacy. Trace identitas item sejak permintaan, hasil R&D, SKU hasil, supplier/route, cost dan harga jual. Gunakan satu sumber data per item; definisikan agregasi header hanya sebagai hasil perhitungan rincian. Jangan membuat sumber harga kedua yang tidak direkonsiliasi.

Implementasikan preview, lock/unlock, keputusan customer dan konversi yang mempertahankan seluruh produk, qty/unit dan aturan harga. Jika ada item belum siap, tampilkan alasan yang jelas dan cegah konversi yang menghilangkan item. Data legacy satu item tetap berfungsi. Retry memakai dokumen SO yang sama dan tidak menggandakan reservasi/pengadaan.

**Titik selesai:** contoh A100 yard+B200 yard menghasilkan dua rincian SO dengan qty yang sama, harga/pajak/total sesuai rincian, referensi dokumen per item utuh, dan tidak ada produk hilang. Uji satuan berbeda, perubahan harga salah satu item, item dibatalkan, dua item SKU sama yang memang berbeda kebutuhan, gagal di tengah konversi dan retry. Buktikan juga dampaknya sampai alokasi, invoice/AR dan pengiriman. Jangan menyatakan selesai hanya karena 18 tes realisasi pengadaan lama lulus.

## Fase UI-02 — Pulihkan kontrol pilihan Interco

Perbaiki FE-02 di sembilan lokasi. Samakan callback pemanggil dengan kontrak `KNSelect`. Periksa apakah nilai selectedEntity yang diteruskan ke form adalah ID string atau objek; perbedaan bentuk prop perlu diuji sebelum dijadikan perubahan terpisah. Jangan mengubah scope transaksi agar form sekadar dapat dikirim.

**Titik selesai:** pengguna dapat mengganti seller/buyer, mode harga/PPN, produk dan filter; nilai tersimpan pada state serta payload yang benar. Settlement dari tombol utama dan dari pasangan tertentu sama-sama dapat diisi. Tes memeriksa perubahan nilai dan payload, bukan hanya adanya tombol/opsi. API tetap menolak pihak, produk, rekening dan scope yang tidak sah.

## Fase UI-03 — Peta role, menu, tab dan aksi

Perbaiki FE-03, FE-04 dan FE-05. Rekonsiliasi katalog akses dengan struktur menu terbaru: induk Akuntansi, menu Interco, tab Barang Masuk/Keluar, hub RFID dan menu Retur yang sudah diperkenalkan. Gunakan sumber konfigurasi yang konsisten untuk sidebar, pencarian, tab, preview role dan deep link.

Ganti gate nama role yang mengabaikan izin efektif pada tombol yang ditunjukkan laporan. Pertahankan pemeriksaan scope, status dokumen, penugasan, approval rule dan larangan menjadikan Admin sebagai template. Aksi create/update/delete/approve tidak boleh dianggap satu hak umum. Backend tetap menjadi enforcement utama.

Data Gudang harus meminta/menyediakan scope master yang sah bagi Admin Gudang. Jangan memberi seluruh lokasi/entitas hanya untuk menghilangkan 403. Daftar petugas inspeksi harus mengikuti kemampuan aktif serta scope penugasan, termasuk role kustom.

**Titik selesai:** matriks role tanpa acuan, role turunan dan role bawaan yang diubah menjadi read-only menghasilkan menu/tombol yang benar. Finance dapat memutus selisih bila diizinkan; Admin berizin dapat menyetujui transfer; receiving/QC kustom mendapat aksi dan penugasan yang sah. Preview menu sama dengan akun nyata. Pencabutan izin tercermin sesuai mekanisme refresh yang ada, dan manipulasi request tetap ditolak backend.

## Fase UI-04 — Navigasi tugas dan form retur

Perbaiki FE-06 sampai FE-09. Target antrean Harga Khusus harus menuju renderer yang sah dan membuka ID pengajuan yang dipilih. Koreksi error propagation dari parent retur ke detail/modal. Modal hanya ditutup setelah keberhasilan; pesan gagal dan input tetap terlihat.

Lindungi form dari respons SO lama yang selesai terlambat. Hanya respons untuk pilihan aktif boleh dipakai. Pemilih sumber retur harus memakai pencarian/pagination server yang sesuai scope dan sisa barang eligible; jangan sekadar menaikkan batas 200.

**Titik selesai:** klik Meja Saya membuka pengajuan yang sama; error submit/approve/inspect/settle terlihat pada layar aktif; retry tidak menduplikasi transaksi. A lambat lalu B cepat tetap menampilkan B. SO baru dikirim tetap dapat ditemukan walau ada lebih dari 200 pesanan lain. Validasi kumulatif klaim/roll di backend tetap berjalan.

## Fase UI-05 — Satuan, status pemuatan dan representasi Finance

Perbaiki FE-10 sampai FE-13. Antrean QC harus memakai unit sumber yang eksplisit, memisahkan agregasi kg/yard dan membedakannya dari interval inspect yard. Jangan membuat konversi baru memakai GSM/rasio perkiraan sebagai kebenaran fisik.

Penerimaan transfer harus membedakan loading, error, empty dan data, termasuk kegagalan GET pertama. Neraca hanya boleh dinyatakan Seimbang dari hasil valid bernilai true; unknown/loading/error tidak boleh diberi badge keberhasilan. Tooltip saldo kumulatif harus menjaga tanda negatif, terpisah dari cara menampilkan besaran arus keluar.

**Titik selesai:** fixture yard, kg dan campuran tidak diberi label meter; receipt yang gagal memuat dapat diulang; neraca gagal dimuat tidak terlihat sebagai Seimbang; defisit kas terlihat negatif pada tooltip. Cocokkan tampilan, payload dan sumber backend. Uji juga data kosong, pergantian periode/entitas dan pengguna tanpa akses.

## Bukti yang wajib diserahkan

Untuk tiap FE-ID, catat status implemented/pending validation/validated, SHA, file yang berubah, hasil sebelum/sesudah, dan batas uji. Lampirkan tes relevan serta rekaman/screenshot UI untuk langkah yang diuji melalui browser. Bedakan fixture yang disiapkan langsung dengan proses bisnis yang benar-benar dijalankan. Catat error lingkungan sebagai hambatan, jangan mengubah expected result agar tes lulus. Audit lama tidak otomatis ditutup oleh perubahan frontend.

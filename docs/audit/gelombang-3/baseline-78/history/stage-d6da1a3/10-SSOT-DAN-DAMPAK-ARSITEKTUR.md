# SSOT, duplikasi logika dan dampak perbaikan

Temuan berkaitan satu sama lain. Memperbaiki satu angka di frontend tidak cukup jika sumber, dimensi atau lifecycle di backend tetap berbeda. Rekomendasi berikut mengikat catatan rinci; bukan temuan runtime tambahan yang dihitung lagi.

## 1. Kontrak metrik belum seragam

Satu nama “available” dipakai untuk roll berstatus available, panjang bebas setelah partial reserve, dan jumlah yang bisa dijanjikan. “Pendapatan realisasi” mengambil nilai SO yang masih reserved; “target” tidak memakai entitas yang sama dengan numerator. “Nilai persediaan” menggunakan biaya dasar pada satu laporan dan biaya penuh di laporan lain.

Setiap metrik perlu kontrak: sumber dokumen/collection, field nominal atau quantity, grain, status eligible, tanggal bisnis, entitas/owner, unit, rounding, biaya/tax basis, freshness dan penanganan nilai tidak tersedia. Dua metrik berbeda boleh ditampilkan, tetapi label dan definisinya harus berbeda. Mengubah sumber harus disertai review semua consumer.

Catatan terkait: D4-AI-05/06, D4-DASH-01, D4-FIN-03/04, D4-STOCK-03, D4-SALES-01.

## 2. Grain data merupakan bagian identitas

Grain stok fisik dan valuasi minimal product + warehouse + owner; satu warehouse dapat menyimpan barang beberapa entitas. Penggabungan POV sales dilakukan setelah tiap partisi benar. Menghilangkan owner terlalu awal membuat nilai/velocity ditambahkan ulang. Identitas orang juga harus user_id, bukan nama yang bisa sama atau berubah.

Catatan terkait: D4-STOCK-01, D4-RND-01, D4-HR-01. Hubungan hukum/ledger per-entitas tetap dipertahankan ketika UI sales menampilkan stok gabungan.

## 3. Helper kanonis tidak cukup bila consumer melewatinya

compute_customer_credit sudah menerima entity_id dan sales_kpi sudah meneruskannya; sales_home masih memanggil tanpa scope. Vendor bill canonical mendukung total_amount fallback, AP analytics membuat formula sendiri. Forecast mendefinisikan NON_AR_METHODS tetapi tidak memakainya dan membuat due date dari default pelanggan, melewati snapshot termin SO. Reporting capacity menulis traversal sendiri yang tidak mengikuti Rack→Level→Bin.

Ini duplikasi semantik yang sudah menghasilkan counterexample, meskipun bukan semua baris merupakan salinan teks identik. Sumber/helper harus dipakai bersama atau kontraknya diuji dengan golden fixtures independen pada seluruh consumer.

Catatan terkait: D4-SALES-02, D4-AI-01, D4-FIN-02, D4-WMS-03. Duplicate top-level _clean_perms yang terdeteksi AST tetap tercatat sebagai V3-DUP-01; jumlah finite query caps pada inventory tidak dinyatakan sebagai jumlah bug.

## 4. Rantai write harus bisa dipulihkan

Konsumsi roll, insert movement, posting GL, perubahan saldo AR, penciptaan child roll dan publish fact adalah efek yang terpisah. Marker “done/reversed” tidak boleh mendahului efek yang perlu dipulihkan tanpa stage recovery. Retry harus membuktikan kontribusi yang sudah terjadi, bukan menebak dari dokumen yang gagal dibuat.

Catatan terkait: V3-PROD-01/02, V3-MKO-01, V3-AR-01, V3-CUT-01, V3-MASTER-01 serta D4-AI-03. ETL read model dan ledger mempunyai tingkat dampak berbeda; perbaikannya tidak boleh menganggap semua membutuhkan mekanisme identik, tetapi harus memenuhi konservasi dan retry tepat sekali.

## 5. Waktu dan state harus ditampilkan dengan makna bisnis

UTC timestamp adalah format penyimpanan, bukan otomatis definisi “hari ini” WIB. updated_at adalah waktu edit, bukan tanggal karyawan keluar. Latest cycle count open bukan last measured accuracy. Response generation lama bukan scope entitas yang sedang dipilih. Current WAC merupakan estimasi biaya kini, bukan otomatis snapshot biaya penjualan historis.

Catatan terkait: D4-WMS-01/02, D4-HR-02, D4-FE-02, D4-FIN-04 dan V3-DATE-01.

## 6. Dampak positif patch terbaru dan batasnya

Perubahan terbaru menambahkan scope SO/credit pada sales_kpi, memperbaiki consumer reference pada configuration catalog, meneruskan entitas aktif pada beberapa home/leaderboard, memperbaiki label pending/hold dan menyesuaikan collection rate ratio ke persen di tampilan tertentu. Build frontend berhasil, replay W2 82/82 dan banyak regression berhasil.

Perbaikan tersebut tidak otomatis menutup setiap consumer: sales_home kartu pelanggan, lookup target, query komisi per-SKU, serta komponen AR Tower masih mempunyai celah yang dibuktikan tersendiri. Differential testcase yang berubah menjadi pass juga tidak selalu bukti akibat patch, karena fixture full suite bersifat stateful.

## 7. Penutupan audit memerlukan bukti lintas consumer

Sesudah patch, bandingkan API, KPI, tabel, chart, tooltip dan export pada snapshot/filter yang sama. Gunakan angka independen dari dokumen sumber, bukan membandingkan dua projection yang sama-sama salah. Simpan actual HEAD, fixture, expected/actual, lifecycle dan hasil retry/reversal. Jangan menutup seluruh domain hanya karena satu example endpoint atau 100% statement coverage tercapai.

# Prompt develop — W2-004 dan W2-005

Baca [laporan detail](04_TEMUAN_KLAIM_DAN_PEMBAYARAN.md), tracker Gelombang2, dan perubahan Gelombang1 yang sedang berjalan sebelum mengedit. Reproduksi pada commit kerja sekarang. Simpan SHA, fixture, perintah dan hasil dalam evidence iterasi baru; jangan menimpa hasil historis. Implementer hanya menandai ready_for_validation, validator independen menentukan verified_fixed atau reopened.

## W2-004 — pembatalan bill jasa makloon

Periksa seluruh lifecycle bill_type=makloon_service dari issue/receive/record_service sampai pembatalan. Reproduksi bill100.000 yang dibatalkan API200 tetapi utang GL100.000 masih ada karena reverse_vendor_bill hanya mencari source_type=vendor_bill, sementara sumbernya subcon_service. Kontrol: supplier bill umum harus tetap dapat dibalik dengan benar.

Tentukan kontrak koreksi bill turunan: tolak cancel generik dan arahkan ke sumber bila orkestrasi koreksi belum tersedia, atau implementasikan koreksi sumber yang mempertahankan AP/WIP/output/COGS sesuai state. Jangan hanya memperluas filter jurnal lalu membalik WIP tanpa memeriksa biaya sudah diserap output. Tampilkan alasan dan tindakan yang dapat dilakukan user. Posting yang hilang/tidak ditemukan tidak boleh dianggap cancel sukses tanpa kontrak yang jelas.

Tambahkan regression test untuk makloon output normal, jasa murni, klaim terkait, pembayaran parsial, output sudah dikonsumsi, retry dan closed period. Verifikasi jumlah jurnal, AP, WIP, nilai stok dan status sumber. Buat rencana tersendiri untuk data historis; jangan menjalankan perbaikan produksi otomatis. Laporkan desain, file yang berubah, commit, hasil uji dan keterbatasan; update W2-004 menjadi ready_for_validation.

## W2-005 — atomicity pembayaran versus potong bon

Reproduksi kedua urutan pada wave2_claim_payment.py: (1) payment membaca grand100.000, claim menurunkannya60.000, payment80.000 tetap lolos; (2) claim memvalidasi unpaid100.000, payment80.000 selesai, claim40.000 menulis grand60.000. Hasil salah keduanya paid80.000>grand60.000 dan saldo debit AP20.000 tanpa klasifikasi advance.

Perbaiki kontrak bersama semua writer vendor_bill, termasuk payment dan makloon claim. Guard pembayaran harus menggunakan state grand_total yang masih sah, sedangkan guard klaim harus mempertimbangkan paid terkini. Jangan berhenti setelah mengubah satu perbandingan karena arah kedua tetap rentan. Koordinasikan CAS/claim dengan jurnal dan kas melalui operation ID serta recovery yang idempotent: CAS kalah setelah journal write tidak boleh meninggalkan GL yatim. Jika overpayment sah secara bisnis, buat keputusan advance/credit eksplisit dan reconcile; jangan memotong paid atau grand secara diam-diam.

Uji kedua barrier, dua pembayaran80.000 pada grand100.000 (harus tetap satu berhasil), serial claim40.000→pay60.000, pay80.000→claim40.000 ditolak, retry klaim, double approval, cancel-versus-pay, dan kegagalan pada batas write/GL. Pastikan tidak ada efek ganda atau kehilangan kas. Catat commit dan bukti lengkap, lalu W2-005 ready_for_validation. Jangan menutup CX-13 atau tiket Gelombang1 dari hasil uji ini.

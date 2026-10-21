# Lembar hasil UAT — ERP Kain Nusantara (KN-UAT-E2E-003 v3.0)

**Tanggal:** ______ (09.00–17.00 WIB)  **Kandidat:** VPS setelah update.sh · commit ______  **Fasilitator:** ______  **Pencatat:** ______

Status: `L` Lulus · `G` Gagal · `T` Terblokir. Isi nomor dokumen sistem & ID temuan.

## S1 — Penjualan biasa · stok ada · kirim ekspedisi · NET 30 → lunas (Kelompok 1 · Penjualan & Retur, 09.15–10.00)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S1-01 | Sales | Lembar produk: harga/yard, stok, pilihan Warna, Order biasa / Order sample, Per yard / Per Roll, QTY. | ✓ HP |  |  |  |
| S1-02 | Sales | Bila qty tidak pas roll muncul Genapkan ke Roll Utuh (ke atas / ke bawah / potong). | ✓ HP |  |  |  |
| S1-03 | Sales | Tab Keranjang berlencana jumlah baris; isi keranjang: produk, 1 roll dipilih, nilai. | ✓ HP |  |  |  |
| S1-04 | Sales | Item, nomor roll & qty (mis. 50,95 yard) tampil; langkah 2 terbuka. | ✓ HP |  |  |  |
| S1-05 | Sales | Jumlah roll tersedia tampil per item; termin & QC terpilih. | ✓ HP |  |  |  |
| S1-06 | Sales | Pesan KSC/SO-xxxxx dibuat (reserved) … Grand total Rp …; pindah ke tab Pesanan. Catat nomor SO. | ✓ HP |  |  |  |
| S1-07 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ S1 |  |  |  |
| S1-08 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ✓ S1 |  |  |  |
| S1-09 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ✓ S1 |  |  |  |
| S1-10 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ S1 |  |  |  |
| S1-11 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ S1 |  |  |  |
| S1-12 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ S1 |  |  |  |
| S1-13 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S1-14 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ S1 |  |  |  |
| S1-15 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ S1 |  |  |  |
| S1-16 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ S1 |  |  |  |
| S1-17 | Admin Gudang | Status Dalam perjalanan. | ✓ S1 |  |  |  |
| S1-18 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ S1 |  |  |  |
| S1-19 | Finance | Banner Faktur Pajak KSC/FKT-xxxxx diterbitkan untuk KSC/SO-xxxxx. | ✓ S1 |  |  |  |
| S1-20 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ S1 |  |  |  |
| S1-21 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S2 — Termin CBD (bayar sebelum kirim) · armada sendiri → lunas (Kelompok 1 · Penjualan & Retur, 10.00–10.35)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S2-01 | Sales | Lembar produk: harga/yard, stok, pilihan Warna, Order biasa / Order sample, Per yard / Per Roll, QTY. | ✓ HP |  |  |  |
| S2-02 | Sales | Bila qty tidak pas roll muncul Genapkan ke Roll Utuh (ke atas / ke bawah / potong). | ✓ HP |  |  |  |
| S2-03 | Sales | Tab Keranjang berlencana jumlah baris; isi keranjang: produk, 1 roll dipilih, nilai. | ✓ HP |  |  |  |
| S2-04 | Sales | Item, nomor roll & qty (mis. 50,95 yard) tampil; langkah 2 terbuka. | ✓ HP |  |  |  |
| S2-05 | Sales | Jumlah roll tersedia tampil per item; termin & QC terpilih. | ✓ HP |  |  |  |
| S2-06 | Sales | Kotak Pemenuhan memberi tahu: Termin CBD wajib dibayar 100% (Rp …) sebelum kirim — pengiriman tertahan sampai Finance mencatat pembayaran. Pesan KSC/S… | ✓ HP |  |  |  |
| S2-07 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ S2 |  |  |  |
| S2-08 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ✓ S2 |  |  |  |
| S2-09 | Admin Sales | dikonfirmasi — tugas gudang lahir. Pelacak SO: tahap berikutnya Dibayar sesuai termin CBD sebelum kirim — Finance. | ✓ S2 |  |  |  |
| S2-10 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ S2 |  |  |  |
| S2-11 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ S2 |  |  |  |
| S2-12 | Gudang | Kotak merah Tertahan — belum dibayar sesuai termin (wajib Rp …, sudah dibayar Rp 0, kurang Rp …); [Kirim Sebagian] / [Kirim Semua] nonaktif dengan ala… | ✓ S2 |  |  |  |
| S2-13 | Finance | Pembayaran KSC/AR-xxxxx dicatat; SO keluar dari antrean; kiriman otomatis terbuka. | ✓ S2 |  |  |  |
| S2-14 | Finance / Manajer | Boleh kirim — pengecualian berizin + pelaku, waktu, alasan. Gudang & Sales tidak punya tombol ini. | ✓ S2 |  |  |  |
| S2-15 | Admin Gudang | Barang Keluar dengan tugas terpilih. Kotak hijau Boleh kirim — termin terpenuhi (sudah dibayar Rp …). | ✓ S2 |  |  |  |
| S2-16 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S2-17 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ S2 |  |  |  |
| S2-18 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ S2 |  |  |  |
| S2-19 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ S2 |  |  |  |
| S2-20 | Admin Gudang | Status Dalam perjalanan. | ✓ S2 |  |  |  |
| S2-21 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ S2 |  |  |  |
| S2-22 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S3 — Ambil sendiri di gudang · bayar tunai (Kelompok 1 · Penjualan & Retur, 10.35–11.05)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S3-01 | Sales | Lembar produk: harga/yard, stok, pilihan Warna, Order biasa / Order sample, Per yard / Per Roll, QTY. | ✓ HP |  |  |  |
| S3-02 | Sales | Bila qty tidak pas roll muncul Genapkan ke Roll Utuh (ke atas / ke bawah / potong). | ✓ HP |  |  |  |
| S3-03 | Sales | Tab Keranjang berlencana jumlah baris; isi keranjang: produk, 1 roll dipilih, nilai. | ✓ HP |  |  |  |
| S3-04 | Sales | Item, nomor roll & qty (mis. 50,95 yard) tampil; langkah 2 terbuka. | ✓ HP |  |  |  |
| S3-05 | Sales | Jumlah roll tersedia tampil per item; termin & QC terpilih. | ✓ HP |  |  |  |
| S3-06 | Sales | Ringkasan Diambil oleh … · Ambil di gudang · tanggal (tanggal tidak boleh lampau). Pesan KSC/SO-xxxxx dibuat (reserved) … Grand total Rp …; pindah ke … | ✓ HP |  |  |  |
| S3-07 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ =S1 |  |  |  |
| S3-08 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ✓ =S1 |  |  |  |
| S3-09 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ✓ =S1 |  |  |  |
| S3-10 | Gudang | Kotak ungu Barang baru disiapkan pada/setelah tanggal ambil; setelah rilis tugas masuk antrean pengambilan. | ✓ S3 |  |  |  |
| S3-11 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ =S1 |  |  |  |
| S3-12 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ =S1 |  |  |  |
| S3-13 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ S3 |  |  |  |
| S3-14 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S3-15 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ S3 |  |  |  |
| S3-16 | Admin Gudang | Pengiriman Menunggu diambil; HP: kartu SO menampilkan Diambil di gudang · tanggal & kode pickup. | ✓ S3 |  |  |  |
| S3-17 | Admin Gudang | Kode salah → KODE PICKUP SALAH — barang tidak boleh diserahkan. Benar → Diserahkan; SO Selesai. | ✓ S3 |  |  |  |
| S3-18 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ S3 |  |  |  |
| S3-19 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S4 — Harga khusus ditolak → diajukan ulang → disetujui (Kelompok 1 · Penjualan & Retur, 11.05–11.45)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S4-01 | Sales | Lembar produk: harga/yard, stok, pilihan Warna, Order biasa / Order sample, Per yard / Per Roll, QTY. | ✓ HP |  |  |  |
| S4-02 | Sales | Bila qty tidak pas roll muncul Genapkan ke Roll Utuh (ke atas / ke bawah / potong). | ✓ HP |  |  |  |
| S4-03 | Sales | Tab Keranjang berlencana jumlah baris; isi keranjang: produk, 1 roll dipilih, nilai. | ✓ HP |  |  |  |
| S4-04 | Sales | Item, nomor roll & qty (mis. 50,95 yard) tampil; langkah 2 terbuka. | ✓ HP |  |  |  |
| S4-05 | Sales | Jumlah roll tersedia tampil per item; termin & QC terpilih. | ✓ HP |  |  |  |
| S4-06 | Sales | Pesan KSC/SO-xxxxx dibuat (reserved) … Grand total Rp …; pindah ke tab Pesanan. Catat nomor SO. | ✓ HP |  |  |  |
| S4-07 | Sales | Entri Persetujuan Harga Khusus · Rp 20.000 → … · MENUNGGU; kartu SO Menunggu approval harga khusus. | ✓ HP |  |  |  |
| S4-08 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ =S1 |  |  |  |
| S4-09 | Admin Sales | SO Menunggu persetujuan (Menunggu approval harga khusus); pindah ke antrean Menunggu keputusan manajer. | ✓ S1 |  |  |  |
| S4-10 | Manajer | Entri ditolak + pemutus & catatan. | ✓ S4 |  |  |  |
| S4-11 | Sales | Entri lama Digantikan pengajuan baru; entri baru MENUNGGU. SO tidak terkunci (F-09). | ✓ HP |  |  |  |
| S4-12 | Manajer | Harga baris = harga khusus; subtotal, PPN, grand total dihitung ulang; SO otomatis Disetujui. | ✓ S4 |  |  |  |
| S4-13 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ✓ =S1 |  |  |  |
| S4-14 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ =S1 |  |  |  |
| S4-15 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ =S1 |  |  |  |
| S4-16 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ =S3 |  |  |  |
| S4-17 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S4-18 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ =S3 |  |  |  |
| S4-19 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S1 |  |  |  |
| S4-20 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S1 |  |  |  |
| S4-21 | Admin Gudang | Status Dalam perjalanan. | ✓ =S1 |  |  |  |
| S4-22 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S1 |  |  |  |
| S4-23 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ =S1 |  |  |  |
| S4-24 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S5 — Kredit melewati limit → disetujui manajer (Kelompok 1 · Penjualan & Retur, 11.45–12.20)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S5-01 | Sales | Langkah 3 Review: kotak kredit Terblokir kredit + alasan, AR vs limit, proyeksi; [Buat Sales Order] terkunci. | ✓ S5 |  |  |  |
| S5-02 | Sales | Pengajuan override kredit terkirim — menunggu Manajer. | ✓ S5 |  |  |  |
| S5-03 | Manajer | Override disetujui. | ✓ S5 |  |  |  |
| S5-04 | Sales | SO KANDA/SO-xxxxx dibuat. | ✓ S5 |  |  |  |
| S5-05 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ S5 |  |  |  |
| S5-06 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ✓ S5 |  |  |  |
| S5-07 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ✓ S5 |  |  |  |
| S5-08 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Soreang · Gudang Kanda); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, LOT… | ✓ S5 |  |  |  |
| S5-09 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ S5 |  |  |  |
| S5-10 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ S5 |  |  |  |
| S5-11 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S5-12 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ S5 |  |  |  |
| S5-13 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S2 |  |  |  |
| S5-14 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S2 |  |  |  |
| S5-15 | Admin Gudang | Status Dalam perjalanan. | ✓ =S2 |  |  |  |
| S5-16 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S2 |  |  |  |
| S5-17 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ =S1 |  |  |  |
| S5-18 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S6 — Pelanggan minta QC sebelum kirim (Kelompok 1 · Penjualan & Retur, 13.20–14.00)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S6-01 | Sales | Lembar produk: harga/yard, stok, pilihan Warna, Order biasa / Order sample, Per yard / Per Roll, QTY. | ✓ HP |  |  |  |
| S6-02 | Sales | Bila qty tidak pas roll muncul Genapkan ke Roll Utuh (ke atas / ke bawah / potong). | ✓ HP |  |  |  |
| S6-03 | Sales | Tab Keranjang berlencana jumlah baris; isi keranjang: produk, 1 roll dipilih, nilai. | ✓ HP |  |  |  |
| S6-04 | Sales | Item, nomor roll & qty (mis. 50,95 yard) tampil; langkah 2 terbuka. | ✓ HP |  |  |  |
| S6-05 | Sales | Jumlah roll tersedia tampil per item; termin & QC terpilih. | ✓ HP |  |  |  |
| S6-06 | Sales | Pesan KSC/SO-xxxxx dibuat (reserved) … Grand total Rp …; pindah ke tab Pesanan. Catat nomor SO. | ✓ HP |  |  |  |
| S6-07 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ =S1 |  |  |  |
| S6-08 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ✓ =S1 |  |  |  |
| S6-09 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ✓ =S1 |  |  |  |
| S6-10 | Gudang | Roll anak terverifikasi; muncul di daftar ambil. | ✓ S6 |  |  |  |
| S6-11 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ S6 |  |  |  |
| S6-12 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ S6 |  |  |  |
| S6-13 | Gudang | Ditolak: SO meminta QC … kirim menunggu SPK QC selesai. | ✓ S6 |  |  |  |
| S6-14 | Admin Gudang | SPK Ditugaskan; muncul di antrean QC. | ✓ S6 |  |  |  |
| S6-15 | QC | Hasil per roll + grade saran tersimpan. | ✓ S6 |  |  |  |
| S6-16 | Admin Gudang | SPK Selesai; pesan tahan QC hilang dari panel kirim. | ✓ S6 |  |  |  |
| S6-17 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ S6 |  |  |  |
| S6-18 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S6-19 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ S6 |  |  |  |
| S6-20 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S1 |  |  |  |
| S6-21 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S1 |  |  |  |
| S6-22 | Admin Gudang | Status Dalam perjalanan. | ✓ =S1 |  |  |  |
| S6-23 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S1 |  |  |  |
| S6-24 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ =S1 |  |  |  |
| S6-25 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S7 — Stok kurang → dipenuhi dari PT lain (antar-PT) (Kelompok 1 · Penjualan & Retur, 14.00–14.50)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S7-01 | Sales | SO Menunggu stok; Sebagian via backorder. | ✓ S7 |  |  |  |
| S7-02 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ =S1 |  |  |  |
| S7-03 | Admin Sales | Transaksi Antar-PT KSC/IC-xxxxx terbentuk & tertaut ke SO. | ✓ S7 |  |  |  |
| S7-04 | Gudang | Tugas gudang IC lahir; transfer gudang Menunggu persetujuan. | ✓ S7 |  |  |  |
| S7-05 | Admin Gudang CST | Transfer Disetujui → Selesai; pemilik roll = Sukacita; SO Dicadangkan untuk qty yang tersedia. | ✓ S7 |  |  |  |
| S7-06 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ✓ =S1 |  |  |  |
| S7-07 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ✓ =S1 |  |  |  |
| S7-08 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Rancamalang · Gudang Knitting); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (ro… | ✓ =S1 |  |  |  |
| S7-09 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ =S1 |  |  |  |
| S7-10 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ =S3 |  |  |  |
| S7-11 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S7-12 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ =S3 |  |  |  |
| S7-13 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S2 |  |  |  |
| S7-14 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S2 |  |  |  |
| S7-15 | Admin Gudang | Status Dalam perjalanan. | ✓ =S2 |  |  |  |
| S7-16 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S2 |  |  |  |
| S7-17 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ =S1 |  |  |  |
| S7-18 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S14 — Retur → kompensasi (refund / saldo / nego) (Kelompok 1 · Penjualan & Retur, 15.05–15.50)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S14-01 | Sales | SRET-xxxxx Menunggu persetujuan. Klaim > 21 hari dari SJ → ditolak / [Ajukan pengecualian]. | ✓ S14 |  |  |  |
| S14-02 | Manajer | Retur Disetujui. | ✓ S14 |  |  |  |
| S14-03 | Gudang | Lokasi fisik roll: Jakarta · Gudang Sukacita · SRET-…/TRM-1; belum jadi stok jual. | ✓ S14 |  |  |  |
| S14-04 | Gudang | Status Dalam perjalanan Jakarta → Rancamalang · Gudang Transit. | ✓ S14 |  |  |  |
| S14-05 | Gudang | Roll di Rancamalang · Gudang Transit menunggu QC. | ✓ S14 |  |  |  |
| S14-06 | QC | Retur Selesai Inspeksi; tonggak Inspeksi selesai · inspeksi 4-point di retur. QC sebelum barang diterima → ditolak (F-12). | ✓ S14 |  |  |  |
| S14-07 | MD Quality | Roll anak berurutan; potongan BS tercatat. | ○ |  |  |  |
| S14-08 | Finance | Diputus Finance: Rp … · nama; dasar hitung terlihat. | ✓ S14 |  |  |  |
| S14-09 | Manajer | Retur Nego; Nota Kredit CN-xxxxx (diskon + PPN); saldo pelanggan bertambah. Admin Sales tidak bisa (403). | ✓ S14 |  |  |  |
| S14-10 | Finance | Saldo pelanggan & piutang benar; satu posting. | ○ |  |  |  |
| S14-11 | Admin Sales | Roll tersimpan dengan grade/hold hasil QC (bukan otomatis tersedia). | ○ |  |  |  |

## S15 — Retur → barang pengganti (Kelompok 1 · Penjualan & Retur, 15.50–16.30)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S15-01 | Sales | SRET-xxxxx Menunggu persetujuan. Klaim > 21 hari dari SJ → ditolak / [Ajukan pengecualian]. | ✓ =S14 |  |  |  |
| S15-02 | Manajer | Retur Disetujui. | ✓ =S14 |  |  |  |
| S15-03 | Gudang | Lokasi fisik roll: Jakarta · Gudang Sukacita · SRET-…/TRM-1; belum jadi stok jual. | ✓ =S14 |  |  |  |
| S15-04 | Gudang | Status Dalam perjalanan Jakarta → Rancamalang · Gudang Transit. | ✓ =S14 |  |  |  |
| S15-05 | Gudang | Roll di Rancamalang · Gudang Transit menunggu QC. | ✓ =S14 |  |  |  |
| S15-06 | QC | Retur Selesai Inspeksi; tonggak Inspeksi selesai · inspeksi 4-point di retur. QC sebelum barang diterima → ditolak (F-12). | ✓ =S14 |  |  |  |
| S15-07 | Manajer | Retur Store Credit; roll retur karantina. | ✓ S15 |  |  |  |
| S15-08 | Admin Sales | SO pengganti tertaut retur: saldo retur dipakai Rp … · ditagih Rp 0; roll yang diretur tidak dialokasikan lagi. | ✓ S15 |  |  |  |
| S15-09 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ S15 |  |  |  |
| S15-10 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ✓ S15 |  |  |  |
| S15-11 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ✓ S15 |  |  |  |
| S15-12 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ =S6 |  |  |  |
| S15-13 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ =S6 |  |  |  |
| S15-14 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ =S3 |  |  |  |
| S15-15 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S15-16 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ =S3 |  |  |  |
| S15-17 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S1 |  |  |  |
| S15-18 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S1 |  |  |  |
| S15-19 | Admin Gudang | Status Dalam perjalanan. | ✓ =S1 |  |  |  |
| S15-20 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S1 |  |  |  |
| S15-21 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S8 — Stok kurang → PO supplier → kedatangan → SPK → kirim (Kelompok 2 · Hulu, Pengadaan & Sample, 09.15–10.30)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S8-01 | Sales | SO Menunggu stok. | ✓ =S7 |  |  |  |
| S8-02 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ S8 |  |  |  |
| S8-03 | Admin Sales | Penuh — … PO ke supplier (PR-xxxxx); PR merujuk SO. | ✓ S8 |  |  |  |
| S8-04 | Pembelian | PO KSC/PO-xxxxx; PR Terealisasi Penuh; qty PO = incoming. | ✓ S8 |  |  |  |
| S8-05 | Supplier | — | ○ |  |  |  |
| S8-06 | Admin Gudang | KSC/GRN-xxxxx Draf → Tinjau SJ; baris Siap. | ✓ S8 |  |  |  |
| S8-07 | Gudang | Roll lahir status receiving; tab Rekonsiliasi terbuka. | ✓ S8 |  |  |  |
| S8-08 | Admin Gudang | GRN Ditutup, baris Terposting; stok bertambah sebesar fisik; roll karantina; SPK inspeksi (INS) otomatis. | ✓ S8 |  |  |  |
| S8-09 | Admin Gudang | SPK Ditugaskan. MD Quality baru bisa mengisi sesudah ini (F-13). | ✓ S8 |  |  |  |
| S8-10 | MD Quality | Kolom WARNA/HANDFEEL per roll terisi; MDQ: nama. | ✓ S8 |  |  |  |
| S8-11 | QC | Poin & grade saran per roll; QC: nama. | ✓ S8 |  |  |  |
| S8-12 | Admin Gudang | SPK Selesai; roll tersedia; sistem mencadangkan ke SO backorder → SO Dicadangkan (sisa SJ kurang tetap backorder). | ✓ S8 |  |  |  |
| S8-13 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ✓ =S1 |  |  |  |
| S8-14 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ✓ =S1 |  |  |  |
| S8-15 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ =S1 |  |  |  |
| S8-16 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ =S1 |  |  |  |
| S8-17 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ =S3 |  |  |  |
| S8-18 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S8-19 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ =S3 |  |  |  |
| S8-20 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S1 |  |  |  |
| S8-21 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S1 |  |  |  |
| S8-22 | Admin Gudang | Status Dalam perjalanan. | ✓ =S1 |  |  |  |
| S8-23 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S1 |  |  |  |
| S8-24 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ =S1 |  |  |  |
| S8-25 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |
| S8-26 | Pembelian | Vendor Bill VB-xxxxx dibuat — langsung di-posting (match bersih); total + PPN masukan; status Terposting. | ✓ S8 |  |  |  |
| S8-27 | Pembelian | VB Lunas; Sudah dibayar = total; jurnal terposting. | ✓ S8 |  |  |  |

## S9 — Stok kurang → makloon (proses di mitra) (Kelompok 2 · Hulu, Pengadaan & Sample, 10.30–11.30)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S9-01 | Sales | SO Dicadangkan sebagian + backorder. | ✓ =S7 |  |  |  |
| S9-02 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ =S8 |  |  |  |
| S9-03 | Admin Sales | PR lahir dengan baris Makloon. | ✓ S9 |  |  |  |
| S9-04 | Pembelian | MKO-xxxxx (Pesanan Pembelian › Order Makloon) Draf; bahan dicadangkan (fisik belum berkurang). | ✓ S9 |  |  |  |
| S9-05 | Gudang | Stok bahan keluar tepat sekali (fisik berkurang); MKO Diproses. | ✓ S9 |  |  |  |
| S9-06 | Mitra | Hasil aktual boleh ≠ rencana. | ○ |  |  |  |
| S9-07 | Admin Gudang | GRN Ditutup; MKO Selesai; roll hasil tersedia & SO backorder otomatis dicadangkan; sisa cadangan bahan dilepas. QC hasil makloon (opsional): QC & Insp… | ✓ S9 |  |  |  |
| S9-08 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ✓ =S1 |  |  |  |
| S9-09 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ✓ =S1 |  |  |  |
| S9-10 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ =S1 |  |  |  |
| S9-11 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ =S1 |  |  |  |
| S9-12 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ =S3 |  |  |  |
| S9-13 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S9-14 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ =S3 |  |  |  |
| S9-15 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S1 |  |  |  |
| S9-16 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S1 |  |  |  |
| S9-17 | Admin Gudang | Status Dalam perjalanan. | ✓ =S1 |  |  |  |
| S9-18 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S1 |  |  |  |
| S9-19 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ =S1 |  |  |  |
| S9-20 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S10 — Multi-gudang Rancamalang → transit → pelanggan Jakarta (Kelompok 2 · Hulu, Pengadaan & Sample, 11.30–12.10)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S10-01 | Sales CST | SO Dicadangkan; alokasi per gudang (Woven / Knitting). | ✓ =S1 |  |  |  |
| S10-02 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ =S1 |  |  |  |
| S10-03 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ✓ =S1 |  |  |  |
| S10-04 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ✓ =S1 |  |  |  |
| S10-05 | Gudang | Roll anak terverifikasi & berkomitmen ke SO. | ✓ =S6 |  |  |  |
| S10-06 | Gudang | CST/TRF-xxxxx Menunggu Persetujuan; roll tetap terkunci untuk SO. | ✓ S10 |  |  |  |
| S10-07 | Admin Gudang CST | Transfer Selesai; roll di Transit tetap berkomitmen ke SO; tugas pengambilan pindah ke Gudang Transit. | ✓ S10 |  |  |  |
| S10-08 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Rancamalang · Gudang Transit); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (rol… | ✓ S10 |  |  |  |
| S10-09 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ S10 |  |  |  |
| S10-10 | Gudang | Ditolak: Roll … tidak ditemukan untuk produk tugas ini. | ✓ S10 |  |  |  |
| S10-11 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ =S3 |  |  |  |
| S10-12 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S10-13 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ =S3 |  |  |  |
| S10-14 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S2 |  |  |  |
| S10-15 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S2 |  |  |  |
| S10-16 | Admin Gudang | Status Dalam perjalanan. | ✓ =S2 |  |  |  |
| S10-17 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S2 |  |  |  |
| S10-18 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ =S1 |  |  |  |
| S10-19 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S11 — Sample gratis (Kelompok 2 · Hulu, Pengadaan & Sample, 13.20–13.45)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S11-01 | Sales | Keranjang Sample; melebihi batas → ditolak (jual sebagai ECER berbayar). | ✓ S11 |  |  |  |
| S11-02 | Sales | KSC/SOS-xxxxx (terpisah dari SO); kartu HP Gratis tanpa tombol bayar. | ✓ S11 |  |  |  |
| S11-03 | Admin Sample | SOS pindah ke Sedang dipotong / disiapkan gudang. | ✓ S11 |  |  |  |
| S11-04 | Gudang | Sample dipotong — RL-… → RL-…-n · panjang; nilai SOS mengikuti panjang aktual. | ✓ S11 |  |  |  |
| S11-05 | Admin Sample | Pindah ke Diterima Admin Cutting — siap kirim/ambil. Kirim sebelum diterima → ditolak belum diterima Admin Cutting. | ✓ S11 |  |  |  |
| S11-06 | Gudang | Barang terkirim — No. Surat Jalan KSC/SJ-xxxxx; SOS Dikirim. | ✓ S11 |  |  |  |
| S11-07 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S1 |  |  |  |
| S11-08 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S1 |  |  |  |
| S11-09 | Admin Gudang | Status Dalam perjalanan. | ✓ =S1 |  |  |  |
| S11-10 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S1 |  |  |  |
| S11-11 | Sales | SOS Dikirim/Selesai · Gratis. | ✓ S11 |  |  |  |

## S12 — Sample berbayar (Kelompok 2 · Hulu, Pengadaan & Sample, 13.45–14.20)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S12-01 | Sales | Keranjang Sample; melebihi batas → ditolak (jual sebagai ECER berbayar). | ✓ S12 |  |  |  |
| S12-02 | Sales | KSC/SOS-xxxxx (terpisah dari SO); harga × panjang + PPN; Menunggu persetujuan bayar sample. | ✓ S12 |  |  |  |
| S12-03 | Finance | SOS Disetujui. Sales tidak punya tombol; teruskan sebelum disetujui → ditolak. | ✓ S12 |  |  |  |
| S12-04 | Admin Sample | SOS pindah ke Sedang dipotong / disiapkan gudang. | ✓ S12 |  |  |  |
| S12-05 | Gudang | Sample dipotong — RL-… → RL-…-n · panjang; nilai SOS mengikuti panjang aktual. | ✓ S12 |  |  |  |
| S12-06 | Finance | Pembayaran disetujui; kirim tertahan sampai disetujui ulang. | ✓ S12 |  |  |  |
| S12-07 | Admin Sample | Pindah ke Diterima Admin Cutting — siap kirim/ambil. Kirim sebelum diterima → ditolak belum diterima Admin Cutting. | ✓ S12 |  |  |  |
| S12-08 | Gudang | Barang terkirim — No. Surat Jalan KSC/SJ-xxxxx; SOS Dikirim. | ✓ S12 |  |  |  |
| S12-09 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S1 |  |  |  |
| S12-10 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S1 |  |  |  |
| S12-11 | Admin Gudang | Status Dalam perjalanan. | ✓ =S1 |  |  |  |
| S12-12 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S1 |  |  |  |
| S12-13 | Finance | SOS lunas. | ✓ =S1 |  |  |  |
| S12-14 | Sales | SOS Dikirim/Selesai & lunas. | ✓ S12 |  |  |  |

## S13 — Pesanan Khusus (desain/warna baru) → SO → lunas (Kelompok 2 · Hulu, Pengadaan & Sample, 14.20–15.35)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S13-01 | Sales | Formulir 6 bagian; pesan Belum lengkap: … menyebut isian yang kurang. | ✓ S13 |  |  |  |
| S13-02 | Sales | SORD-yymmdd-xxxx Menunggu persetujuan. | ✓ S13 |  |  |  |
| S13-03 | Manajer | OD disetujui → otomatis Permintaan Desain (DSR) untuk printing & Sample R&D (SMP) untuk labdip/handfeel; tampil di Rantai dokumen detail OD. | ✓ S13 |  |  |  |
| S13-04 | MD | DSR Ditugaskan. | ○ |  |  |  |
| S13-05 | Desainer | Menunggu keputusan; versi & checklist per ronde. | ○ |  |  |  |
| S13-06 | PIC | Sample proofing lahir otomatis; MD diberi tahu. | ○ |  |  |  |
| S13-07 | R&D | Permintaan Terkirim. | ○ |  |  |  |
| S13-08 | R&D | OD fase Sample siap. | ○ |  |  |  |
| S13-09 | Sales | OD Menunggu ACC pelanggan. | ○ |  |  |  |
| S13-10 | Admin Sales | OD lanjut ke kunci harga. | ○ |  |  |  |
| S13-11 | Admin Sales | Harga terkunci per item; PR/PO ke supplier pemenang lahir. | ○ |  |  |  |
| S13-12 | MD | SKU aktif. | ○ |  |  |  |
| S13-13 | Pembelian · Admin Gudang · QC | Stok item OD tersedia. | ○ |  |  |  |
| S13-14 | Admin Sales | SO tertaut OD; ulang tidak membuat SO kedua. | ○ |  |  |  |
| S13-15 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ○ |  |  |  |
| S13-16 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ○ |  |  |  |
| S13-17 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ○ |  |  |  |
| S13-18 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ○ |  |  |  |
| S13-19 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ○ |  |  |  |
| S13-20 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ○ |  |  |  |
| S13-21 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ○ |  |  |  |
| S13-22 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ○ |  |  |  |
| S13-23 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ○ |  |  |  |
| S13-24 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ○ |  |  |  |
| S13-25 | Admin Gudang | Status Dalam perjalanan. | ○ |  |  |  |
| S13-26 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ○ |  |  |  |
| S13-27 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ○ |  |  |  |
| S13-28 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ○ |  |  |  |

## S16 — Pembelian stok (restock) → hutang supplier lunas (Kelompok 2 · Hulu, Pengadaan & Sample, 15.35–16.20)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S16-01 | Pembelian | PR-xxxxx dibuat … Lihat di tab Permintaan Pembelian (≥ Rp50 jt → Menunggu Persetujuan). | ✓ S16 |  |  |  |
| S16-02 | Admin | PR Disetujui. | ✓ S16 |  |  |  |
| S16-03 | Pembelian | PO KSC/PO-xxxxx (≥ Rp100 jt → ACC Admin dulu). | ✓ =S8 |  |  |  |
| S16-04 | Supplier | — | ○ |  |  |  |
| S16-05 | Admin Gudang | GRN Draf → Tinjau SJ. | ✓ =S8 |  |  |  |
| S16-06 | Gudang | Roll receiving. | ✓ =S8 |  |  |  |
| S16-07 | Admin Gudang | Stok +960 yd; tugas sisa 40 dibuat (PO tetap incoming 40); roll karantina + SPK. | ✓ S16 |  |  |  |
| S16-08 | Admin Gudang · MD Quality · QC | Roll tersedia. | ✓ =S8 |  |  |  |
| S16-09 | Pembelian | Vendor Bill VB-xxxxx dibuat — langsung di-posting (match bersih); total + PPN masukan; status Terposting. | ✓ =S8 |  |  |  |
| S16-10 | Pembelian | VB Lunas; Sudah dibayar = total; jurnal terposting. | ✓ =S8 |  |  |  |

## Penutupan

- Lulus ___ · Gagal ___ · Terblokir ___
- Alur siap pakai: ___
- Keputusan bisnis: ___
- Rencana perbaikan & uji ulang: ___
- Tanda tangan: pemilik proses ___ · Production IT ___ · fasilitator ___ · pencatat ___

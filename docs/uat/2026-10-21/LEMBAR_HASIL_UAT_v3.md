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
| S1-13 | Admin Gudang | OVERRIDE oleh … — berlaku untuk n roll saat ini (tombol Override nonaktif sampai alasan diisi). Staf Gudang yang menekan Kirim tanpa ini ditolak: roll… | ✓ S1 |  |  |  |
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
| S2-16 | Admin Gudang | OVERRIDE oleh … — berlaku untuk n roll saat ini (tombol Override nonaktif sampai alasan diisi). Staf Gudang yang menekan Kirim tanpa ini ditolak: roll… | ✓ S2 |  |  |  |
| S2-17 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ S2 |  |  |  |
| S2-18 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ S2 |  |  |  |
| S2-19 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ S2 |  |  |  |
| S2-20 | Admin Gudang | Status Dalam perjalanan. | ✓ S2 |  |  |  |
| S2-21 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ S2 |  |  |  |
| S2-22 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S3 — Ambil sendiri di gudang · bayar tunai (Kelompok 1 · Penjualan & Retur, 10.35–11.05)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S3-01 | Sales | Lembar produk: harga/yard, stok, pilihan Warna, Order biasa / Order sample, Per yard / Per Roll, QTY. | ○ |  |  |  |
| S3-02 | Sales | Bila qty tidak pas roll muncul Genapkan ke Roll Utuh (ke atas / ke bawah / potong). | ○ |  |  |  |
| S3-03 | Sales | Tab Keranjang berlencana jumlah baris; isi keranjang: produk, 1 roll dipilih, nilai. | ○ |  |  |  |
| S3-04 | Sales | Item, nomor roll & qty (mis. 50,95 yard) tampil; langkah 2 terbuka. | ○ |  |  |  |
| S3-05 | Sales | Jumlah roll tersedia tampil per item; termin & QC terpilih. | ○ |  |  |  |
| S3-06 | Sales | Ringkasan Diambil oleh … · Ambil di gudang · tanggal. Pesan KSC/SO-xxxxx dibuat (reserved) … Grand total Rp …; pindah ke tab Pesanan. Catat nomor SO. | ○ |  |  |  |
| S3-07 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ S1 |  |  |  |
| S3-08 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ✓ S1 |  |  |  |
| S3-09 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ✓ S1 |  |  |  |
| S3-10 | Gudang | Kotak ungu Barang baru disiapkan pada/setelah tanggal ambil; setelah rilis tugas masuk antrean pengambilan. | ○ |  |  |  |
| S3-11 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ S1 |  |  |  |
| S3-12 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ S1 |  |  |  |
| S3-13 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ S1 |  |  |  |
| S3-14 | Admin Gudang | OVERRIDE oleh … — berlaku untuk n roll saat ini (tombol Override nonaktif sampai alasan diisi). Staf Gudang yang menekan Kirim tanpa ini ditolak: roll… | ✓ S1 |  |  |  |
| S3-15 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ S1 |  |  |  |
| S3-16 | Admin Gudang | Pengiriman Menunggu diambil. | ○ |  |  |  |
| S3-17 | Admin Gudang | Kode salah → KODE PICKUP SALAH — barang tidak boleh diserahkan. Benar → Diserahkan; SO Selesai. | ○ |  |  |  |
| S3-18 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ S1 |  |  |  |
| S3-19 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ○ |  |  |  |

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
| S4-08 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ S1 |  |  |  |
| S4-09 | Admin Sales | SO Menunggu persetujuan (Menunggu approval harga khusus); pindah ke antrean Menunggu keputusan manajer. | ✓ S1 |  |  |  |
| S4-10 | Manajer | Entri ditolak + pemutus & catatan. | ○ |  |  |  |
| S4-11 | Sales | Entri lama Digantikan pengajuan baru; entri baru MENUNGGU. SO tidak terkunci (F-09). | ✓ HP |  |  |  |
| S4-12 | Manajer | Harga baris = harga khusus; subtotal, PPN, grand total dihitung ulang; SO otomatis Disetujui. | ○ |  |  |  |
| S4-13 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ✓ S1 |  |  |  |
| S4-14 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ S1 |  |  |  |
| S4-15 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ S1 |  |  |  |
| S4-16 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ S1 |  |  |  |
| S4-17 | Admin Gudang | OVERRIDE oleh … — berlaku untuk n roll saat ini (tombol Override nonaktif sampai alasan diisi). Staf Gudang yang menekan Kirim tanpa ini ditolak: roll… | ✓ S1 |  |  |  |
| S4-18 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ S1 |  |  |  |
| S4-19 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ S1 |  |  |  |
| S4-20 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ S1 |  |  |  |
| S4-21 | Admin Gudang | Status Dalam perjalanan. | ✓ S1 |  |  |  |
| S4-22 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ S1 |  |  |  |
| S4-23 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ S1 |  |  |  |
| S4-24 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ○ |  |  |  |

## S5 — Kredit melewati limit → disetujui manajer (Kelompok 1 · Penjualan & Retur, 11.45–12.20)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S5-01 | Sales | Langkah 3 Review: kotak kredit Peringatan / Terblokir kredit + alasan, AR vs limit, proyeksi. | ○ |  |  |  |
| S5-02 | Sales | SO terbentuk; kartu SO menandai masalah kredit. | ○ |  |  |  |
| S5-03 | Sales | Entri Persetujuan Kredit (Melebihi Batas) · MENUNGGU; SO Menunggu approval kredit. | ○ |  |  |  |
| S5-04 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ○ |  |  |  |
| S5-05 | Admin Sales | SO Menunggu persetujuan (kredit). Approve langsung oleh Admin Sales ditolak. | ○ |  |  |  |
| S5-06 | Manajer | Credit hold dilepas, override tercatat terpakai, SO otomatis Disetujui. | ○ |  |  |  |
| S5-07 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ○ |  |  |  |
| S5-08 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Soreang · Gudang Kanda); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, LOT… | ○ |  |  |  |
| S5-09 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ○ |  |  |  |
| S5-10 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ○ |  |  |  |
| S5-11 | Admin Gudang | OVERRIDE oleh … — berlaku untuk n roll saat ini (tombol Override nonaktif sampai alasan diisi). Staf Gudang yang menekan Kirim tanpa ini ditolak: roll… | ○ |  |  |  |
| S5-12 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ○ |  |  |  |
| S5-13 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ○ |  |  |  |
| S5-14 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ○ |  |  |  |
| S5-15 | Admin Gudang | Status Dalam perjalanan. | ○ |  |  |  |
| S5-16 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ○ |  |  |  |
| S5-17 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ○ |  |  |  |
| S5-18 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ○ |  |  |  |

## S6 — Pelanggan minta QC sebelum kirim (Kelompok 1 · Penjualan & Retur, 13.20–14.00)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S6-01 | Sales | Lembar produk: harga/yard, stok, pilihan Warna, Order biasa / Order sample, Per yard / Per Roll, QTY. | ○ |  |  |  |
| S6-02 | Sales | Bila qty tidak pas roll muncul Genapkan ke Roll Utuh (ke atas / ke bawah / potong). | ○ |  |  |  |
| S6-03 | Sales | Tab Keranjang berlencana jumlah baris; isi keranjang: produk, 1 roll dipilih, nilai. | ○ |  |  |  |
| S6-04 | Sales | Item, nomor roll & qty (mis. 50,95 yard) tampil; langkah 2 terbuka. | ○ |  |  |  |
| S6-05 | Sales | Jumlah roll tersedia tampil per item; termin & QC terpilih. | ○ |  |  |  |
| S6-06 | Sales | Pesan KSC/SO-xxxxx dibuat (reserved) … Grand total Rp …; pindah ke tab Pesanan. Catat nomor SO. | ○ |  |  |  |
| S6-07 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ S1 |  |  |  |
| S6-08 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ✓ S1 |  |  |  |
| S6-09 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ✓ S1 |  |  |  |
| S6-10 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ S1 |  |  |  |
| S6-11 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ S1 |  |  |  |
| S6-12 | Gudang | Ditolak: SO meminta QC … kirim menunggu SPK QC selesai. | ○ |  |  |  |
| S6-13 | Admin Gudang | SPK Ditugaskan; muncul di antrean QC. | ○ |  |  |  |
| S6-14 | QC | Hasil per roll + grade saran tersimpan. | ○ |  |  |  |
| S6-15 | Admin Gudang | SPK Selesai; pesan tahan QC hilang dari panel kirim. | ○ |  |  |  |
| S6-16 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ S1 |  |  |  |
| S6-17 | Admin Gudang | OVERRIDE oleh … — berlaku untuk n roll saat ini (tombol Override nonaktif sampai alasan diisi). Staf Gudang yang menekan Kirim tanpa ini ditolak: roll… | ✓ S1 |  |  |  |
| S6-18 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ S1 |  |  |  |
| S6-19 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ S1 |  |  |  |
| S6-20 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ S1 |  |  |  |
| S6-21 | Admin Gudang | Status Dalam perjalanan. | ✓ S1 |  |  |  |
| S6-22 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ S1 |  |  |  |
| S6-23 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ S1 |  |  |  |
| S6-24 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ○ |  |  |  |

## S7 — Stok kurang → dipenuhi dari PT lain (antar-PT) (Kelompok 1 · Penjualan & Retur, 14.00–14.50)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S7-01 | Sales | Tanpa backorder → ditolak Stok milik entitas tidak mencukupi … Aktifkan backorder. Dengan backorder → SO Menunggu stok; Sebagian via backorder (disetu… | ○ |  |  |  |
| S7-02 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ✓ S1 |  |  |  |
| S7-03 | Admin Sales | Total rencana > kekurangan → ditolak. Tersimpan: Keputusan pemenuhan; Permintaan Internal (PIN) → Transaksi Antar-PT KSC/IC-xxxxx terbentuk & tertaut … | ○ |  |  |  |
| S7-04 | CST | Pemilik roll = Sukacita; lokasi fisik masih Rancamalang · Gudang Knitting. | ○ |  |  |  |
| S7-05 | Sistem | SO kembali Dicadangkan untuk qty yang tersedia; antrean Perlu dipenuhi berkurang. | ○ |  |  |  |
| S7-06 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ○ |  |  |  |
| S7-07 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ○ |  |  |  |
| S7-08 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Rancamalang · Gudang Knitting); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (ro… | ○ |  |  |  |
| S7-09 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ○ |  |  |  |
| S7-10 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ○ |  |  |  |
| S7-11 | Admin Gudang | OVERRIDE oleh … — berlaku untuk n roll saat ini (tombol Override nonaktif sampai alasan diisi). Staf Gudang yang menekan Kirim tanpa ini ditolak: roll… | ○ |  |  |  |
| S7-12 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ○ |  |  |  |
| S7-13 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ○ |  |  |  |
| S7-14 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ○ |  |  |  |
| S7-15 | Admin Gudang | Status Dalam perjalanan. | ○ |  |  |  |
| S7-16 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ○ |  |  |  |
| S7-17 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ○ |  |  |  |
| S7-18 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ○ |  |  |  |

## S14 — Retur → kompensasi (refund / saldo / nego) (Kelompok 1 · Penjualan & Retur, 15.05–15.50)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S14-01 | Sales | SRET-xxxxx Menunggu persetujuan. Klaim > 21 hari dari SJ → ditolak / [Ajukan pengecualian]. | ○ |  |  |  |
| S14-02 | Manajer | Retur Disetujui. | ○ |  |  |  |
| S14-03 | Gudang | Posisi fisik per roll tercatat; belum jadi stok jual. (F-11: Gudang kini bisa membuka & memproses.) | ○ |  |  |  |
| S14-04 | Gudang | Status dalam perjalanan. | ○ |  |  |  |
| S14-05 | Gudang | Roll di area transit menunggu QC. | ○ |  |  |  |
| S14-06 | QC | Retur Selesai inspeksi. QC sebelum barang diterima → ditolak (F-12). | ○ |  |  |  |
| S14-07 | MD Quality | Roll anak berurutan; potongan BS tercatat. | ○ |  |  |  |
| S14-08 | Finance | Kompensasi diputus; dasar hitung terlihat. | ○ |  |  |  |
| S14-09 | Manajer | Retur refund_settled / credit_settled / nego_settled. Admin Sales tidak bisa (403). | ○ |  |  |  |
| S14-10 | Finance | Saldo pelanggan & piutang benar; satu posting. | ○ |  |  |  |
| S14-11 | Admin Sales | Roll tersimpan dengan grade/hold hasil QC (bukan otomatis tersedia). | ○ |  |  |  |

## S15 — Retur → barang pengganti (Kelompok 1 · Penjualan & Retur, 15.50–16.30)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S15-01 | Sales | SRET-xxxxx Menunggu persetujuan. Klaim > 21 hari dari SJ → ditolak / [Ajukan pengecualian]. | ○ |  |  |  |
| S15-02 | Manajer | Retur Disetujui. | ○ |  |  |  |
| S15-03 | Gudang | Posisi fisik per roll tercatat; belum jadi stok jual. (F-11: Gudang kini bisa membuka & memproses.) | ○ |  |  |  |
| S15-04 | Gudang | Status dalam perjalanan. | ○ |  |  |  |
| S15-05 | Gudang | Roll di area transit menunggu QC. | ○ |  |  |  |
| S15-06 | QC | Retur Selesai inspeksi. QC sebelum barang diterima → ditolak (F-12). | ○ |  |  |  |
| S15-07 | Manajer | Retur menunggu pesanan pengganti. | ○ |  |  |  |
| S15-08 | Admin Sales | SO pengganti tertaut retur; roll yang diretur tidak boleh dikirim lagi ke pelanggan asal. | ○ |  |  |  |
| S15-09 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ○ |  |  |  |
| S15-10 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ○ |  |  |  |
| S15-11 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ○ |  |  |  |
| S15-12 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ○ |  |  |  |
| S15-13 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ○ |  |  |  |
| S15-14 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ○ |  |  |  |
| S15-15 | Admin Gudang | OVERRIDE oleh … — berlaku untuk n roll saat ini (tombol Override nonaktif sampai alasan diisi). Staf Gudang yang menekan Kirim tanpa ini ditolak: roll… | ○ |  |  |  |
| S15-16 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ○ |  |  |  |
| S15-17 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ○ |  |  |  |
| S15-18 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ○ |  |  |  |
| S15-19 | Admin Gudang | Status Dalam perjalanan. | ○ |  |  |  |
| S15-20 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ○ |  |  |  |
| S15-21 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ○ |  |  |  |

## S8 — Stok kurang → PO supplier → kedatangan → SPK → kirim (Kelompok 2 · Hulu, Pengadaan & Sample, 09.15–10.30)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S8-01 | Sales | SO Menunggu stok. | ○ |  |  |  |
| S8-02 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ○ |  |  |  |
| S8-03 | Admin Sales | Permintaan Pembelian PR-xxxxx lahir & merujuk SO. | ○ |  |  |  |
| S8-04 | Pembelian | PO KSC/PO-xxxxx + tugas inbound menunggu barang; qty PO = incoming (bukan stok). PR ≥ Rp50 jt / PO ≥ Rp100 jt → ACC manajer dulu (Pusat Persetujuan). | ○ |  |  |  |
| S8-05 | Supplier | — | ○ |  |  |  |
| S8-06 | Admin Gudang | KSC/GRN-xxxxx Draf → Review → Hitung. | ○ |  |  |  |
| S8-07 | Gudang | Roll lahir status receiving. | ○ |  |  |  |
| S8-08 | Admin Gudang | Stok bertambah sebesar fisik; PO Sebagian/Penuh diterima; roll karantina; SPK inspeksi (INS) otomatis. | ○ |  |  |  |
| S8-09 | Admin Gudang | SPK Ditugaskan. MD Quality baru bisa mengisi sesudah ini (F-13). | ○ |  |  |  |
| S8-10 | MD Quality | Dua indikator tersimpan terpisah. | ○ |  |  |  |
| S8-11 | QC | Hasil per roll + grade saran. | ○ |  |  |  |
| S8-12 | Admin Gudang | SPK Selesai; roll tersedia; sistem mencadangkan ke SO backorder → SO Dicadangkan. | ○ |  |  |  |
| S8-13 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ○ |  |  |  |
| S8-14 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ○ |  |  |  |
| S8-15 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ○ |  |  |  |
| S8-16 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ○ |  |  |  |
| S8-17 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ○ |  |  |  |
| S8-18 | Admin Gudang | OVERRIDE oleh … — berlaku untuk n roll saat ini (tombol Override nonaktif sampai alasan diisi). Staf Gudang yang menekan Kirim tanpa ini ditolak: roll… | ○ |  |  |  |
| S8-19 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ○ |  |  |  |
| S8-20 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ○ |  |  |  |
| S8-21 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ○ |  |  |  |
| S8-22 | Admin Gudang | Status Dalam perjalanan. | ○ |  |  |  |
| S8-23 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ○ |  |  |  |
| S8-24 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ○ |  |  |  |
| S8-25 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ○ |  |  |  |
| S8-26 | Finance | Hutang PO lunas. | ○ |  |  |  |

## S9 — Stok kurang → makloon (proses di mitra) (Kelompok 2 · Hulu, Pengadaan & Sample, 10.30–11.30)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S9-01 | Sales | SO Menunggu stok. | ○ |  |  |  |
| S9-02 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ○ |  |  |  |
| S9-03 | Admin Sales | PR lahir & merujuk SO. | ○ |  |  |  |
| S9-04 | Pembelian | Order Makloon MKO-xxxxx (Pesanan Pembelian › Order Makloon); bahan dipesan (reservasi ≠ pengeluaran). | ○ |  |  |  |
| S9-05 | Gudang | Stok bahan keluar tepat sekali; MKO Diproses mitra. | ○ |  |  |  |
| S9-06 | Mitra | Hasil aktual boleh ≠ rencana (mis. 192 dari 200 yd). | ○ |  |  |  |
| S9-07 | Admin Gudang | Roll hasil karantina + SPK inspeksi; susut & klaim mitra terlihat di Rekap Susut & Klaim Mitra. | ○ |  |  |  |
| S9-08 | Admin Gudang · QC · MD Quality | Roll tersedia & dicadangkan ke SO. | ○ |  |  |  |
| S9-09 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ○ |  |  |  |
| S9-10 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ○ |  |  |  |
| S9-11 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ○ |  |  |  |
| S9-12 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ○ |  |  |  |
| S9-13 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ○ |  |  |  |
| S9-14 | Admin Gudang | OVERRIDE oleh … — berlaku untuk n roll saat ini (tombol Override nonaktif sampai alasan diisi). Staf Gudang yang menekan Kirim tanpa ini ditolak: roll… | ○ |  |  |  |
| S9-15 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ○ |  |  |  |
| S9-16 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ○ |  |  |  |
| S9-17 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ○ |  |  |  |
| S9-18 | Admin Gudang | Status Dalam perjalanan. | ○ |  |  |  |
| S9-19 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ○ |  |  |  |
| S9-20 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ○ |  |  |  |
| S9-21 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ○ |  |  |  |

## S10 — Multi-gudang Rancamalang → transit → Jakarta → pelanggan (Kelompok 2 · Hulu, Pengadaan & Sample, 11.30–12.10)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S10-01 | Sales | SO Dicadangkan. | ○ |  |  |  |
| S10-02 | Admin Sales | Banner KSC/SO-xxxxx terverifikasi … — lanjut [Ajukan persetujuan] di antrean Terverifikasi. | ○ |  |  |  |
| S10-03 | Admin Sales | Tanpa gerbang: disetujui otomatis (tanpa gerbang) — lanjut di antrean Siap dikonfirmasi. | ○ |  |  |  |
| S10-04 | Admin Sales | KSC/SO-xxxxx dikonfirmasi — tugas gudang lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ○ |  |  |  |
| S10-05 | Gudang | Semua tugas diambil penuh. | ○ |  |  |  |
| S10-06 | Gudang | Lokasi fisik pindah ke transit. | ○ |  |  |  |
| S10-07 | Admin Gudang | Barang dalam perjalanan internal. | ○ |  |  |  |
| S10-08 | Gudang | Roll tiba di Jakarta; reservasi SO tetap. | ○ |  |  |  |
| S10-09 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ○ |  |  |  |
| S10-10 | Admin Gudang | OVERRIDE oleh … — berlaku untuk n roll saat ini (tombol Override nonaktif sampai alasan diisi). Staf Gudang yang menekan Kirim tanpa ini ditolak: roll… | ○ |  |  |  |
| S10-11 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ○ |  |  |  |
| S10-12 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ○ |  |  |  |
| S10-13 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ○ |  |  |  |
| S10-14 | Admin Gudang | Status Dalam perjalanan. | ○ |  |  |  |
| S10-15 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ○ |  |  |  |
| S10-16 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ○ |  |  |  |
| S10-17 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ○ |  |  |  |

## S11 — Sample gratis (Kelompok 2 · Hulu, Pengadaan & Sample, 13.20–13.45)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S11-01 | Sales | Keranjang ORDER SAMPLE; melebihi batas → ditolak (jual sebagai ECER berbayar). | ○ |  |  |  |
| S11-02 | Sales | Nomor KSC/SOS-xxxxx (terpisah dari SO); harga tampil Free. | ○ |  |  |  |
| S11-03 | Admin Sample | Tugas potong sample lahir di gudang. | ○ |  |  |  |
| S11-04 | Gudang | Roll anak tertaut induk; nilai SOS mengikuti panjang aktual. Roll produk lain → ditolak. | ○ |  |  |  |
| S11-05 | Admin Sample | Kirim sebelum diterima → ditolak belum diterima Admin Cutting. | ○ |  |  |  |
| S11-06 | Gudang | SJ sample terbit; SOS Dikirim. | ○ |  |  |  |
| S11-07 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ○ |  |  |  |
| S11-08 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ○ |  |  |  |
| S11-09 | Admin Gudang | Status Dalam perjalanan. | ○ |  |  |  |
| S11-10 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ○ |  |  |  |
| S11-11 | Sales | SOS Selesai (tanpa tagihan). | ○ |  |  |  |

## S12 — Sample berbayar (Kelompok 2 · Hulu, Pengadaan & Sample, 13.45–14.20)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S12-01 | Sales | Keranjang ORDER SAMPLE; melebihi batas → ditolak (jual sebagai ECER berbayar). | ○ |  |  |  |
| S12-02 | Sales | Nomor KSC/SOS-xxxxx (terpisah dari SO); harga dari master harga sample. | ○ |  |  |  |
| S12-03 | Finance | SOS Disetujui. Sales → tidak punya tombol; teruskan sebelum disetujui → ditolak. | ○ |  |  |  |
| S12-04 | Admin Sample | Tugas potong sample lahir di gudang. | ○ |  |  |  |
| S12-05 | Gudang | Roll anak tertaut induk; nilai SOS mengikuti panjang aktual. Roll produk lain → ditolak. | ○ |  |  |  |
| S12-06 | Admin Sample | Status persetujuan ulang tampil; kirim tertahan sampai disetujui. | ○ |  |  |  |
| S12-07 | Admin Sample | Kirim sebelum diterima → ditolak belum diterima Admin Cutting. | ○ |  |  |  |
| S12-08 | Gudang | SJ sample terbit; SOS Dikirim. | ○ |  |  |  |
| S12-09 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ○ |  |  |  |
| S12-10 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ○ |  |  |  |
| S12-11 | Admin Gudang | Status Dalam perjalanan. | ○ |  |  |  |
| S12-12 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ○ |  |  |  |
| S12-13 | Finance | SOS lunas. | ○ |  |  |  |
| S12-14 | Sales | SOS Selesai & lunas. | ○ |  |  |  |

## S13 — Pesanan Khusus (desain/warna baru) → SO → lunas (Kelompok 2 · Hulu, Pengadaan & Sample, 14.20–15.35)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S13-01 | Sales | Formulir 6 bagian; pesan Belum lengkap: … menyebut isian yang kurang. | ○ |  |  |  |
| S13-02 | Sales | SORD-yymmdd-xxxx Menunggu persetujuan. | ○ |  |  |  |
| S13-03 | Manajer | OD Disetujui → otomatis Permintaan Desain (DSR) untuk printing & Permintaan Sample R&D untuk labdip/handfeel. | ○ |  |  |  |
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
| S13-21 | Admin Gudang | OVERRIDE oleh … — berlaku untuk n roll saat ini (tombol Override nonaktif sampai alasan diisi). Staf Gudang yang menekan Kirim tanpa ini ditolak: roll… | ○ |  |  |  |
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
| S16-01 | Pembelian | PR-xxxxx (≥ Rp50 jt → ACC manajer). | ○ |  |  |  |
| S16-02 | Manajer | PR Disetujui. | ○ |  |  |  |
| S16-03 | Pembelian | PO KSC/PO-xxxxx (≥ Rp100 jt → ACC manajer). | ○ |  |  |  |
| S16-04 | Supplier | — | ○ |  |  |  |
| S16-05 | Admin Gudang | GRN Draf → Review → Hitung. | ○ |  |  |  |
| S16-06 | Gudang | Roll receiving. | ○ |  |  |  |
| S16-07 | Admin Gudang | Stok +960 yd; PO Sebagian diterima (sisa incoming); roll karantina + SPK. | ○ |  |  |  |
| S16-08 | Admin Gudang · MD Quality · QC | Roll tersedia sekali keputusan. | ○ |  |  |  |
| S16-09 | Gudang | Saldo per gudang/bin benar; roll muncul di katalog POS. | ○ |  |  |  |
| S16-10 | Finance | Hutang PO lunas; jurnal terposting. | ○ |  |  |  |

## Penutupan

- Lulus ___ · Gagal ___ · Terblokir ___
- Alur siap pakai: ___
- Keputusan bisnis: ___
- Rencana perbaikan & uji ulang: ___
- Tanda tangan: pemilik proses ___ · Production IT ___ · fasilitator ___ · pencatat ___

# Lembar hasil UAT — ERP Kain Nusantara (KN-UAT-E2E-003 v3.1)

**Tanggal:** ______ (09.00–17.00 WIB)  **Kandidat:** VPS setelah update.sh · commit ______  **Fasilitator:** ______  **Pencatat:** ______

Status: `L` Lulus · `G` Gagal · `T` Terblokir. Isi nomor dokumen sistem & ID temuan.

## S1 — Penjualan biasa · stok ada · kirim ekspedisi · NET 30 → lunas (Kelompok 1 · Penjualan & Retur, 09.15–10.00)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S1-01 | Sales | Bilah menulis nama pelanggan + lencana kredit (Kredit aman / Mendekati limit / Kredit terblokir / Izin kredit disetujui). | ○ |  |  |  |
| S1-02 | Sales | Kartu menulis stok PT penjual dulu (mis. Sukacita: 120 yard · 3 roll atau Sukacita: kosong), lalu Grup: … roll / … yard (semua PT). Lembar produk: har… | ○ |  |  |  |
| S1-03 | Sales | Bila qty tidak pas roll muncul Genapkan ke Roll Utuh (ke atas / ke bawah / potong). | ✓ HP |  |  |  |
| S1-04 | Sales | Tab Keranjang berlencana jumlah baris; isi keranjang: produk, 1 roll dipilih, nilai. | ✓ HP |  |  |  |
| S1-05 | Sales | Item, nomor roll & qty (mis. 50,95 yard) tampil; langkah 2 terbuka. | ○ |  |  |  |
| S1-06 | Sales | Per item tertulis Stok Sukacita: … yard (stok PT penjual; bila kurang: kurang … (diatur Admin Sales)); termin & QC terpilih. | ○ |  |  |  |
| S1-07 | Sales | Pesan KSC/SO-xxxxx dibuat (reserved) … Grand total Rp …; pindah ke tab Pesanan. Catat nomor SO. | ✓ HP |  |  |  |
| S1-08 | Admin Sales | Banner KSC/SO-xxxxx diperiksa & dilepas ke gudang — tugas ambil sudah lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ○ |  |  |  |
| S1-09 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ S1 |  |  |  |
| S1-10 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ S1 |  |  |  |
| S1-11 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ S1 |  |  |  |
| S1-12 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S1-13 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ S1 |  |  |  |
| S1-14 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ S1 |  |  |  |
| S1-15 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ S1 |  |  |  |
| S1-16 | Admin Gudang | Status Dalam perjalanan. | ✓ S1 |  |  |  |
| S1-17 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ S1 |  |  |  |
| S1-18 | Finance | Banner Faktur Pajak KSC/FKT-xxxxx diterbitkan untuk KSC/SO-xxxxx. | ✓ S1 |  |  |  |
| S1-19 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ S1 |  |  |  |
| S1-20 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S2 — Termin CBD (bayar sebelum kirim) · armada sendiri → lunas (Kelompok 1 · Penjualan & Retur, 10.00–10.35)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S2-01 | Sales | Bilah menulis nama pelanggan + lencana kredit (Kredit aman / Mendekati limit / Kredit terblokir / Izin kredit disetujui). | ○ |  |  |  |
| S2-02 | Sales | Kartu menulis stok PT penjual dulu (mis. Sukacita: 120 yard · 3 roll atau Sukacita: kosong), lalu Grup: … roll / … yard (semua PT). Lembar produk: har… | ○ |  |  |  |
| S2-03 | Sales | Bila qty tidak pas roll muncul Genapkan ke Roll Utuh (ke atas / ke bawah / potong). | ✓ HP |  |  |  |
| S2-04 | Sales | Tab Keranjang berlencana jumlah baris; isi keranjang: produk, 1 roll dipilih, nilai. | ✓ HP |  |  |  |
| S2-05 | Sales | Item, nomor roll & qty (mis. 50,95 yard) tampil; langkah 2 terbuka. | ○ |  |  |  |
| S2-06 | Sales | Per item tertulis Stok Sukacita: … yard (stok PT penjual; bila kurang: kurang … (diatur Admin Sales)); termin & QC terpilih. | ○ |  |  |  |
| S2-07 | Sales | Kotak Pemenuhan memberi tahu: Termin CBD wajib dibayar 100% (Rp …) sebelum kirim — pengiriman tertahan sampai Finance mencatat pembayaran. Pesan KSC/S… | ✓ HP |  |  |  |
| S2-08 | Admin Sales | Banner KSC/SO-xxxxx diperiksa & dilepas ke gudang — tugas ambil sudah lahir. Pelacak SO: tahap berikutnya Dibayar sesuai termin CBD sebelum kirim — Fi… | ○ |  |  |  |
| S2-09 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ S2 |  |  |  |
| S2-10 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ S2 |  |  |  |
| S2-11 | Gudang | Kotak merah Tertahan — belum dibayar sesuai termin (wajib Rp …, sudah dibayar Rp 0, kurang Rp …); [Kirim Sebagian] / [Kirim Semua] nonaktif dengan ala… | ✓ S2 |  |  |  |
| S2-12 | Finance | Pembayaran KSC/AR-xxxxx dicatat; SO keluar dari antrean; kiriman otomatis terbuka. | ✓ S2 |  |  |  |
| S2-13 | Finance / Manajer | Boleh kirim — pengecualian berizin + pelaku, waktu, alasan. Gudang & Sales tidak punya tombol ini. | ✓ S2 |  |  |  |
| S2-14 | Admin Gudang | Barang Keluar dengan tugas terpilih. Kotak hijau Boleh kirim — termin terpenuhi (sudah dibayar Rp …). | ✓ S2 |  |  |  |
| S2-15 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S2-16 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ S2 |  |  |  |
| S2-17 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ S2 |  |  |  |
| S2-18 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ S2 |  |  |  |
| S2-19 | Admin Gudang | Status Dalam perjalanan. | ✓ S2 |  |  |  |
| S2-20 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ S2 |  |  |  |
| S2-21 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S3 — Ambil sendiri di gudang · bayar tunai (Kelompok 1 · Penjualan & Retur, 10.35–11.05)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S3-01 | Sales | Bilah menulis nama pelanggan + lencana kredit (Kredit aman / Mendekati limit / Kredit terblokir / Izin kredit disetujui). | ○ |  |  |  |
| S3-02 | Sales | Kartu menulis stok PT penjual dulu (mis. Sukacita: 120 yard · 3 roll atau Sukacita: kosong), lalu Grup: … roll / … yard (semua PT). Lembar produk: har… | ○ |  |  |  |
| S3-03 | Sales | Bila qty tidak pas roll muncul Genapkan ke Roll Utuh (ke atas / ke bawah / potong). | ✓ HP |  |  |  |
| S3-04 | Sales | Tab Keranjang berlencana jumlah baris; isi keranjang: produk, 1 roll dipilih, nilai. | ✓ HP |  |  |  |
| S3-05 | Sales | Item, nomor roll & qty (mis. 50,95 yard) tampil; langkah 2 terbuka. | ○ |  |  |  |
| S3-06 | Sales | Per item tertulis Stok Sukacita: … yard (stok PT penjual; bila kurang: kurang … (diatur Admin Sales)); termin & QC terpilih. | ○ |  |  |  |
| S3-07 | Sales | Ringkasan Diambil oleh … · Ambil di gudang · tanggal (tanggal tidak boleh lampau). Pesan KSC/SO-xxxxx dibuat (reserved) … Grand total Rp …; pindah ke … | ✓ HP |  |  |  |
| S3-08 | Admin Sales | Banner KSC/SO-xxxxx diperiksa & dilepas ke gudang — tugas ambil sudah lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ○ |  |  |  |
| S3-09 | Gudang | Kotak ungu Barang baru disiapkan pada/setelah tanggal ambil; setelah rilis tugas masuk antrean pengambilan. | ✓ S3 |  |  |  |
| S3-10 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ =S1 |  |  |  |
| S3-11 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ =S1 |  |  |  |
| S3-12 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ S3 |  |  |  |
| S3-13 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S3-14 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ S3 |  |  |  |
| S3-15 | Admin Gudang | Pengiriman Menunggu diambil; HP: kartu SO menampilkan Diambil di gudang · tanggal & kode pickup. | ✓ S3 |  |  |  |
| S3-16 | Admin Gudang | Kode salah → KODE PICKUP SALAH — barang tidak boleh diserahkan. Benar → Diserahkan; SO Selesai. | ✓ S3 |  |  |  |
| S3-17 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ S3 |  |  |  |
| S3-18 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S4 — Harga khusus dari checkout ditolak → diajukan ulang → disetujui (Kelompok 1 · Penjualan & Retur, 11.05–11.45)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S4-01 | Sales | Bilah menulis nama pelanggan + lencana kredit (Kredit aman / Mendekati limit / Kredit terblokir / Izin kredit disetujui). | ○ |  |  |  |
| S4-02 | Sales | Kartu menulis stok PT penjual dulu (mis. Sukacita: 120 yard · 3 roll atau Sukacita: kosong), lalu Grup: … roll / … yard (semua PT). Lembar produk: har… | ○ |  |  |  |
| S4-03 | Sales | Bila qty tidak pas roll muncul Genapkan ke Roll Utuh (ke atas / ke bawah / potong). | ✓ HP |  |  |  |
| S4-04 | Sales | Tab Keranjang berlencana jumlah baris; isi keranjang: produk, 1 roll dipilih, nilai. | ✓ HP |  |  |  |
| S4-05 | Sales | Item, nomor roll & qty (mis. 50,95 yard) tampil; langkah 2 terbuka. | ○ |  |  |  |
| S4-06 | Sales | Per item tertulis Stok Sukacita: … yard (stok PT penjual; bila kurang: kurang … (diatur Admin Sales)); termin & QC terpilih. Kartu item: Diminta Rp … … | ○ |  |  |  |
| S4-07 | Sales | Sebelum buat: kotak Harga khusus diminta (pesanan ini) — normal → diminta, Total harga normal & Total bila disetujui. Sesudah buat: SO lahir dengan ha… | ○ |  |  |  |
| S4-08 | Admin Sales | Banner KSC/SO-xxxxx diperiksa — menunggu ACC Manajer; dilepas ke gudang otomatis sesudah ACC. SO pindah ke antrean Menunggu keputusan manajer. | ○ |  |  |  |
| S4-09 | Manajer | Entri ditolak + pemutus & catatan. Meja Admin Sales: SO di antrean Harga khusus ditolak — menunggu sales. | ○ |  |  |  |
| S4-10 | Sales | Entri lama Digantikan pengajuan baru; entri baru MENUNGGU. (Bila memilih Lanjut harga normal: SO dilepas otomatis dengan harga normal. Batalkan pesana… | ○ |  |  |  |
| S4-11 | Manajer | Harga baris = harga khusus; subtotal, PPN, grand total dihitung ulang; SO otomatis dilepas ke gudang (sudah diperiksa Admin Sales) — tugas ambil lahir… | ○ |  |  |  |
| S4-12 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ =S1 |  |  |  |
| S4-13 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ =S1 |  |  |  |
| S4-14 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ =S3 |  |  |  |
| S4-15 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S4-16 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ =S3 |  |  |  |
| S4-17 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S1 |  |  |  |
| S4-18 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S1 |  |  |  |
| S4-19 | Admin Gudang | Status Dalam perjalanan. | ✓ =S1 |  |  |  |
| S4-20 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S1 |  |  |  |
| S4-21 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ =S1 |  |  |  |
| S4-22 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S5 — Kredit melewati limit → izin kredit Manajer → SO (Kelompok 1 · Penjualan & Retur, 11.45–12.20)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S5-01 | Sales | Lencana Kredit terblokir + kotak merah Pelanggan ini tidak bisa membeli — … Checkout terkunci sampai izin kredit disetujui Manajer; tombol checkout be… | ○ |  |  |  |
| S5-02 | Sales | Override kredit diajukan — menunggu persetujuan Manajer/Finance. Setelah disetujui, buka lagi checkout ini lalu [Buat Sales Order]. | ○ |  |  |  |
| S5-03 | Manajer | Override disetujui. | ✓ S5 |  |  |  |
| S5-04 | Sales | SO KANDA/SO-xxxxx dibuat. | ○ |  |  |  |
| S5-05 | Admin Sales | Banner KSC/SO-xxxxx diperiksa & dilepas ke gudang — tugas ambil sudah lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ○ |  |  |  |
| S5-06 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Soreang · Gudang Kanda); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, LOT… | ✓ S5 |  |  |  |
| S5-07 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ S5 |  |  |  |
| S5-08 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ S5 |  |  |  |
| S5-09 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S5-10 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ S5 |  |  |  |
| S5-11 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S2 |  |  |  |
| S5-12 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S2 |  |  |  |
| S5-13 | Admin Gudang | Status Dalam perjalanan. | ✓ =S2 |  |  |  |
| S5-14 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S2 |  |  |  |
| S5-15 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ =S1 |  |  |  |
| S5-16 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S6 — Pelanggan minta QC sebelum kirim (Kelompok 1 · Penjualan & Retur, 13.20–14.00)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S6-01 | Sales | Bilah menulis nama pelanggan + lencana kredit (Kredit aman / Mendekati limit / Kredit terblokir / Izin kredit disetujui). | ○ |  |  |  |
| S6-02 | Sales | Kartu menulis stok PT penjual dulu (mis. Sukacita: 120 yard · 3 roll atau Sukacita: kosong), lalu Grup: … roll / … yard (semua PT). Lembar produk: har… | ○ |  |  |  |
| S6-03 | Sales | Bila qty tidak pas roll muncul Genapkan ke Roll Utuh (ke atas / ke bawah / potong). | ✓ HP |  |  |  |
| S6-04 | Sales | Tab Keranjang berlencana jumlah baris; isi keranjang: produk, 1 roll dipilih, nilai. | ✓ HP |  |  |  |
| S6-05 | Sales | Item, nomor roll & qty (mis. 50,95 yard) tampil; langkah 2 terbuka. | ○ |  |  |  |
| S6-06 | Sales | Per item tertulis Stok Sukacita: … yard (stok PT penjual; bila kurang: kurang … (diatur Admin Sales)); termin & QC terpilih. | ○ |  |  |  |
| S6-07 | Sales | Pesan KSC/SO-xxxxx dibuat (reserved) … Grand total Rp …; pindah ke tab Pesanan. Catat nomor SO. | ✓ HP |  |  |  |
| S6-08 | Admin Sales | Banner KSC/SO-xxxxx diperiksa & dilepas ke gudang — tugas ambil sudah lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ○ |  |  |  |
| S6-09 | Gudang | Roll anak terverifikasi; muncul di daftar ambil. | ○ |  |  |  |
| S6-10 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ S6 |  |  |  |
| S6-11 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ S6 |  |  |  |
| S6-12 | Gudang | Ditolak: SO meminta QC … kirim menunggu SPK QC selesai. | ✓ S6 |  |  |  |
| S6-13 | Admin Gudang | SPK Ditugaskan; muncul di antrean QC. | ✓ S6 |  |  |  |
| S6-14 | QC | Hasil per roll + grade pilihan petugas tersimpan; tanpa grade → Pilih grade roll — grade ditentukan petugas QC dari total poin. | ○ |  |  |  |
| S6-15 | Admin Gudang | SPK Selesai; pesan tahan QC hilang dari panel kirim. | ✓ S6 |  |  |  |
| S6-16 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ S6 |  |  |  |
| S6-17 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S6-18 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ S6 |  |  |  |
| S6-19 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S1 |  |  |  |
| S6-20 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S1 |  |  |  |
| S6-21 | Admin Gudang | Status Dalam perjalanan. | ✓ =S1 |  |  |  |
| S6-22 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S1 |  |  |  |
| S6-23 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ =S1 |  |  |  |
| S6-24 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S7 — Stok kurang → dipenuhi dari PT lain (antar-PT) (Kelompok 1 · Penjualan & Retur, 14.00–14.50)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S7-01 | Sales | SO Menunggu stok; Sebagian via backorder. | ✓ S7 |  |  |  |
| S7-02 | Admin Sales | Banner KSC/SO-xxxxx diperiksa — kurang stok: lanjut [Putuskan pemenuhan]; dilepas otomatis saat stok tersedia. | ○ |  |  |  |
| S7-03 | Admin Sales | Transaksi Antar-PT KSC/IC-xxxxx terbentuk & tertaut ke SO; roll pilihan tercatat di permintaan. | ○ |  |  |  |
| S7-04 | Gudang | Tugas gudang IC lahir; transfer gudang Menunggu persetujuan. | ✓ S7 |  |  |  |
| S7-05 | Admin Gudang CST | Transfer Disetujui → Selesai; pemilik roll = Sukacita; SO Dicadangkan untuk qty yang tersedia; SO otomatis dilepas ke gudang (sudah diperiksa Admin Sa… | ○ |  |  |  |
| S7-06 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Rancamalang · Gudang Knitting); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (ro… | ✓ =S1 |  |  |  |
| S7-07 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ =S1 |  |  |  |
| S7-08 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ =S3 |  |  |  |
| S7-09 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S7-10 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ =S3 |  |  |  |
| S7-11 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S2 |  |  |  |
| S7-12 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S2 |  |  |  |
| S7-13 | Admin Gudang | Status Dalam perjalanan. | ✓ =S2 |  |  |  |
| S7-14 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S2 |  |  |  |
| S7-15 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ =S1 |  |  |  |
| S7-16 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S14 — Retur → kompensasi (refund / saldo / nego) (Kelompok 1 · Penjualan & Retur, 15.05–15.50)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S14-01 | Sales | SRET-xxxxx Menunggu persetujuan. Klaim > 21 hari dari SJ → ditolak / [Ajukan pengecualian]. | ✓ S14 |  |  |  |
| S14-02 | Manajer / Admin Sales | Roll ditolak keluar dari klaim; qty & nilai retur menyesuaikan. | ✓ S14 |  |  |  |
| S14-03 | Manajer | Retur Disetujui; SPK QC retur KSC/INS-… (satu baris per roll) terbit otomatis — panel QC retur · SPK inspeksi per roll. | ✓ S14 |  |  |  |
| S14-04 | Sales / Admin Sales | Stepper tahap 3 Pengembalian barang; tonggak Barang dikirim/dijemput dari pelanggan. | ✓ S14 |  |  |  |
| S14-05 | Gudang | Lokasi fisik roll: Jakarta · Gudang Sukacita · SRET-…/TRM-1; belum jadi stok jual. | ✓ S14 |  |  |  |
| S14-06 | Gudang | Status Dalam perjalanan Jakarta → Rancamalang · Gudang Transit. | ✓ S14 |  |  |  |
| S14-07 | Gudang | Roll di Rancamalang · Gudang Transit menunggu QC. | ✓ S14 |  |  |  |
| S14-08 | QC | Retur Selesai Inspeksi; hasil per roll (grade, cacat, qty aktual) tersalin ke retur. QC sebelum barang diterima → ditolak (F-12). | ✓ S14 |  |  |  |
| S14-09 | MD Quality | Roll anak berurutan; potongan BS tercatat. | ○ |  |  |  |
| S14-10 | Finance | Diputus Finance: Rp … · nama; dasar hitung terlihat. | ✓ S14 |  |  |  |
| S14-11 | Manajer | Retur Nego; Nota Kredit CN-xxxxx (diskon + PPN); saldo pelanggan bertambah. Admin Sales tidak bisa (403). | ✓ S14 |  |  |  |
| S14-12 | Finance | Saldo pelanggan & piutang benar; satu posting. | ○ |  |  |  |
| S14-13 | Admin Sales | Roll tersimpan dengan grade/hold hasil QC (bukan otomatis tersedia). | ○ |  |  |  |

## S15 — Retur → barang pengganti (Kelompok 1 · Penjualan & Retur, 15.50–16.30)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S15-01 | Sales | SRET-xxxxx Menunggu persetujuan. Klaim > 21 hari dari SJ → ditolak / [Ajukan pengecualian]. | ✓ =S14 |  |  |  |
| S15-02 | Manajer / Admin Sales | Roll ditolak keluar dari klaim; qty & nilai retur menyesuaikan. | ✓ =S14 |  |  |  |
| S15-03 | Manajer | Retur Disetujui; SPK QC retur KSC/INS-… (satu baris per roll) terbit otomatis — panel QC retur · SPK inspeksi per roll. | ✓ =S14 |  |  |  |
| S15-04 | Sales / Admin Sales | Stepper tahap 3 Pengembalian barang; tonggak Barang dikirim/dijemput dari pelanggan. | ✓ =S14 |  |  |  |
| S15-05 | Gudang | Lokasi fisik roll: Jakarta · Gudang Sukacita · SRET-…/TRM-1; belum jadi stok jual. | ✓ =S14 |  |  |  |
| S15-06 | Gudang | Status Dalam perjalanan Jakarta → Rancamalang · Gudang Transit. | ✓ =S14 |  |  |  |
| S15-07 | Gudang | Roll di Rancamalang · Gudang Transit menunggu QC. | ✓ =S14 |  |  |  |
| S15-08 | QC | Retur Selesai Inspeksi; hasil per roll (grade, cacat, qty aktual) tersalin ke retur. QC sebelum barang diterima → ditolak (F-12). | ✓ =S14 |  |  |  |
| S15-09 | Manajer | Retur Store Credit; roll retur karantina. | ✓ S15 |  |  |  |
| S15-10 | Admin Sales | SO pengganti tertaut retur: saldo retur dipakai Rp … · ditagih Rp 0; roll yang diretur tidak dialokasikan lagi. | ✓ S15 |  |  |  |
| S15-11 | Admin Sales | Banner KSC/SO-xxxxx diperiksa & dilepas ke gudang — tugas ambil sudah lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ○ |  |  |  |
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
| S8-02 | Admin Sales | Banner KSC/SO-xxxxx diperiksa — kurang stok: lanjut [Putuskan pemenuhan]; dilepas otomatis saat stok tersedia. | ○ |  |  |  |
| S8-03 | Admin Sales | Penuh — … PO ke supplier (PR-xxxxx); PR merujuk SO. | ✓ S8 |  |  |  |
| S8-04 | Pembelian | PO KSC/PO-xxxxx; PR Terealisasi Penuh; qty PO = incoming. | ✓ S8 |  |  |  |
| S8-05 | Supplier | — | ○ |  |  |  |
| S8-06 | Admin Gudang | KSC/GRN-xxxxx Draf → Tinjau SJ; baris Siap. | ○ |  |  |  |
| S8-07 | Gudang | Roll lahir status receiving, daftar roll tampil dua satuan (mis. 109,36 yard (= 100 meter)); tab Rekonsiliasi terbuka. | ○ |  |  |  |
| S8-08 | Admin Gudang | GRN Ditutup, baris Terposting; stok bertambah sebesar fisik; roll karantina; SPK inspeksi (INS) MD Quality otomatis. | ✓ S8 |  |  |  |
| S8-09 | Admin Gudang | SPK Ditugaskan. MD Quality baru bisa mengisi sesudah ini (F-13). | ○ |  |  |  |
| S8-10 | MD Quality | Kolom WARNA/HANDFEEL per roll terisi; MDQ: nama. | ✓ S8 |  |  |  |
| S8-11 | Admin Gudang | SPK Selesai; roll tersedia; sistem mencadangkan ke SO backorder → SO Dicadangkan (sisa SJ kurang tetap backorder); SO otomatis dilepas ke gudang (suda… | ○ |  |  |  |
| S8-12 | QC (opsional) | Poin & STDRT terhitung per roll; tanpa grade → Pilih grade roll: RL-…. Roll yang ditolak QC ditahan. | ○ |  |  |  |
| S8-13 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ =S1 |  |  |  |
| S8-14 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ =S1 |  |  |  |
| S8-15 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ =S3 |  |  |  |
| S8-16 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S8-17 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ =S3 |  |  |  |
| S8-18 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S1 |  |  |  |
| S8-19 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S1 |  |  |  |
| S8-20 | Admin Gudang | Status Dalam perjalanan. | ✓ =S1 |  |  |  |
| S8-21 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S1 |  |  |  |
| S8-22 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ =S1 |  |  |  |
| S8-23 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |
| S8-24 | Pembelian | Vendor Bill VB-xxxxx dibuat — langsung di-posting (match bersih); total + PPN masukan; status Terposting. | ✓ S8 |  |  |  |
| S8-25 | Pembelian | VB Lunas; Sudah dibayar = total; jurnal terposting. | ✓ S8 |  |  |  |

## S9 — Stok kurang → makloon (proses di mitra) (Kelompok 2 · Hulu, Pengadaan & Sample, 10.30–11.30)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S9-01 | Sales | SO Dicadangkan sebagian + backorder. | ✓ =S7 |  |  |  |
| S9-02 | Admin Sales | Banner KSC/SO-xxxxx diperiksa — kurang stok: lanjut [Putuskan pemenuhan]; dilepas otomatis saat stok tersedia. | ○ |  |  |  |
| S9-03 | Admin Sales | PR lahir dengan baris Makloon. | ✓ S9 |  |  |  |
| S9-04 | Pembelian | MKO-xxxxx (Pesanan Pembelian › Order Makloon) Draf; bahan dicadangkan (fisik belum berkurang). | ✓ S9 |  |  |  |
| S9-05 | Gudang | Stok bahan keluar tepat sekali (fisik berkurang); MKO Diproses. | ✓ S9 |  |  |  |
| S9-06 | Mitra | Hasil aktual boleh ≠ rencana. | ○ |  |  |  |
| S9-07 | Admin Gudang | GRN Ditutup; MKO Selesai; roll hasil tersedia & SO backorder otomatis dicadangkan; sisa cadangan bahan dilepas; SO otomatis dilepas ke gudang (sudah d… | ○ |  |  |  |
| S9-08 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ =S1 |  |  |  |
| S9-09 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ =S1 |  |  |  |
| S9-10 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ =S3 |  |  |  |
| S9-11 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S9-12 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ =S3 |  |  |  |
| S9-13 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S1 |  |  |  |
| S9-14 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S1 |  |  |  |
| S9-15 | Admin Gudang | Status Dalam perjalanan. | ✓ =S1 |  |  |  |
| S9-16 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S1 |  |  |  |
| S9-17 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ =S1 |  |  |  |
| S9-18 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S10 — Multi-gudang Rancamalang → transit → pelanggan Jakarta (Kelompok 2 · Hulu, Pengadaan & Sample, 11.30–12.10)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S10-01 | Sales CST | SO Dicadangkan; alokasi per gudang (Woven / Knitting). | ✓ =S1 |  |  |  |
| S10-02 | Admin Sales | Banner KSC/SO-xxxxx diperiksa & dilepas ke gudang — tugas ambil sudah lahir. Pelacak SO menunjukkan tahap berikutnya & peran pemiliknya. | ○ |  |  |  |
| S10-03 | Gudang | Roll anak terverifikasi & berkomitmen ke SO. | ○ |  |  |  |
| S10-04 | Gudang | CST/TRF-xxxxx Menunggu Persetujuan; roll tetap terkunci untuk SO. | ✓ S10 |  |  |  |
| S10-05 | Admin Gudang CST | Transfer Disetujui. | ✓ S10 |  |  |  |
| S10-06 | Gudang | Transfer Dalam Perjalanan. | ✓ S10 |  |  |  |
| S10-07 | Gudang | Transfer Selesai; roll di Transit tetap berkomitmen ke SO; tugas pengambilan pindah ke Gudang Transit. | ✓ S10 |  |  |  |
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
| S11-04 | Gudang | Sample dipotong — RL-… → RL-…-n · panjang; paket pindah ke tab Menunggu Admin Cutting; nilai SOS mengikuti panjang aktual. | ○ |  |  |  |
| S11-05 | Admin Sample | Pindah ke Diterima Admin Cutting — siap kirim/ambil. Kirim sebelum diterima → ditolak belum diterima Admin Cutting. | ○ |  |  |  |
| S11-06 | Gudang | Barang terkirim — No. Surat Jalan KSC/SJ-xxxxx (satu nomor untuk semua baris); SOS Dikirim. | ○ |  |  |  |
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
| S12-05 | Gudang | Sample dipotong — RL-… → RL-…-n · panjang; paket pindah ke tab Menunggu Admin Cutting; nilai SOS mengikuti panjang aktual. | ○ |  |  |  |
| S12-06 | Finance | Pembayaran disetujui; kirim tertahan sampai disetujui ulang. | ✓ S12 |  |  |  |
| S12-07 | Admin Sample | Pindah ke Diterima Admin Cutting — siap kirim/ambil. Kirim sebelum diterima → ditolak belum diterima Admin Cutting. | ○ |  |  |  |
| S12-08 | Gudang | Barang terkirim — No. Surat Jalan KSC/SJ-xxxxx (satu nomor untuk semua baris); SOS Dikirim. | ○ |  |  |  |
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
| S13-02 | Sales | SORD-yymmdd-xxxx (tanggal WIB) Menunggu persetujuan. | ✓ S13 |  |  |  |
| S13-03 | Manajer | Pesan hijau Pesanan disetujui. Diteruskan otomatis: KSC/DSR-…, KSC/SMP-…; DSR (printing) & SMP per item tercatat atas nama Sales pembuat OD; lencana k… | ✓ S13 |  |  |  |
| S13-04 | MD | DSR Ditugaskan; hilang dari antrean MD sampai desain diserahkan. | ✓ S13 |  |  |  |
| S13-05 | Desainer | DSR Menunggu keputusan; versi & checklist per ronde. | ✓ S13 |  |  |  |
| S13-06 | Manajer | DSR Disetujui (ACC); sample proofing item A siap dikirim ke supplier. | ✓ S13 |  |  |  |
| S13-07 | MD | Spesifikasi Draf dengan gramasi & lebar terisi. | ✓ S13 |  |  |  |
| S13-08 | R&D (MD) | Supplier yang lolos tertanda ACC. | ✓ S13 |  |  |  |
| S13-09 | MD (atau Manajer) | Kontrak harga KSC/SCT-… terbit; nama barang & warna versi supplier tersimpan. Diputus MD → panel Master data: Menunggu ACC spesifikasi oleh Manajer / … | ✓ S13 |  |  |  |
| S13-10 | Manajer | SKU eksklusif pelanggan lahir (Disetujui · belum rilis); artikel bersumber restock Supplier. | ✓ S13 |  |  |  |
| S13-11 | Sales | Keputusan pelanggan tersimpan; riwayat ACC + bukti; OD masuk antrean kunci harga. | ✓ S13 |  |  |  |
| S13-12 | Admin Sales | Notifikasi Harga dikunci; total OD = jumlah per item (contoh Rp 19.500.000 + PPN). SKU baru → panel pengadaan: menunggu Manajer: rilis SKU baru ke pro… | ✓ S13 |  |  |  |
| S13-13 | MD | Item Siap direalisasi. | ✓ S13 |  |  |  |
| S13-14 | Manajer | Per item PR-xxxxx → PO KSC/PO-xxxxx ke supplier pemenang (Belum diterima); OD Dalam Produksi. | ✓ S13 |  |  |  |
| S13-15 | Admin Sales | KSC/SO-xxxxx Menunggu stok (backorder per item) tertaut OD; ulang tidak membuat SO kedua. | ✓ S13 |  |  |  |
| S13-16 | Admin Gudang · Gudang · MD Quality | Roll item OD berkomitmen ke SO OD; SO Terkonfirmasi otomatis (barang pesanan khusus diterima gudang); OD Siap baru setelah semua PO item diterima; tug… | ○ |  |  |  |
| S13-17 | Gudang | Pindah ke Operasi Gudang › Barang Keluar dengan tugas terpilih (Jakarta · Gudang Sukacita); panel AMBIL & KIRIM memuat ROLL YANG HARUS DIAMBIL (roll, … | ✓ =S1 |  |  |  |
| S13-18 | Gudang | Toast Pengambilan tercatat — Terkumpul x dari x yard; roll bertanda sudah diambil; muncul Pemeriksaan Muat Akhir dan panel Siap dikirim. Nama pelangga… | ✓ =S1 |  |  |  |
| S13-19 | Admin Gudang | Barang Keluar dengan tugas terpilih. | ✓ =S3 |  |  |  |
| S13-20 | Admin Gudang | SIMULASI (mode UAT) — n/n cocok; dianggap sah, dispatch dibuka. Riwayat scan bertanda SIMULASI (sah di mode simulasi UAT). Roll di luar SO / kurang → … | ✓ S3 |  |  |  |
| S13-21 | Admin Gudang | Terkirim Penuh! … · KSC/SJ-xxxxx + tombol [Surat Jalan] [Buat Pengiriman]. Catat nomor SJ. | ✓ =S3 |  |  |  |
| S13-22 | Admin Gudang | Nomor KSC/LG-xxxxx status Disiapkan; detail pengiriman langsung terbuka. | ✓ =S1 |  |  |  |
| S13-23 | Admin Gudang | Status Dimuat; muncul [Berangkat] · [Bongkar (kembali ke Disiapkan)] · [Gagal kirim]. | ✓ =S1 |  |  |  |
| S13-24 | Admin Gudang | Status Dalam perjalanan. | ✓ =S1 |  |  |  |
| S13-25 | Admin Gudang | LG Terkirim (POD tidak bisa diubah lagi); SO otomatis Selesai saat semua SJ ber-POD. | ✓ =S1 |  |  |  |
| S13-26 | Finance | Pembayaran KSC/AR-xxxxx (Rp …) dicatat untuk … Baris hilang dari antrean. | ✓ =S1 |  |  |  |
| S13-27 | Sales | Perjalanan 100%: Dipesan · Diverifikasi Admin Sales · Disetujui · Dikonfirmasi · Disiapkan gudang · Dikirim (SJ) · Diterima pelanggan · Ditagih (Faktu… | ✓ HP |  |  |  |

## S16 — Pembelian stok (restock) → hutang supplier lunas (Kelompok 2 · Hulu, Pengadaan & Sample, 15.35–16.20)

| Langkah | Peran | Hasil yang harus terlihat | Cek UI | Status | No. dokumen | Catatan / ID temuan |
|---|---|---|---|---|---|---|
| S16-01 | Pembelian | PR-xxxxx dibuat … Lihat di tab Permintaan Pembelian (≥ Rp50 jt → Menunggu Persetujuan). | ✓ S16 |  |  |  |
| S16-02 | Admin | PR Disetujui. | ✓ S16 |  |  |  |
| S16-03 | Pembelian | PO KSC/PO-xxxxx (≥ Rp100 jt → ACC Admin dulu). | ✓ =S8 |  |  |  |
| S16-04 | Supplier | — | ○ |  |  |  |
| S16-05 | Admin Gudang | GRN Draf → Tinjau SJ. | ○ |  |  |  |
| S16-06 | Gudang | Roll receiving. | ✓ =S8 |  |  |  |
| S16-07 | Admin Gudang | Stok +960 yd; tugas sisa 40 dibuat (PO tetap incoming 40); roll karantina + SPK. | ✓ S16 |  |  |  |
| S16-08 | Admin Gudang · MD Quality | Roll tersedia. | ○ |  |  |  |
| S16-09 | QC (opsional) | Poin & STDRT terhitung per roll; tanpa grade → Pilih grade roll: RL-…. Roll yang ditolak QC ditahan. | ○ |  |  |  |
| S16-10 | Pembelian | Vendor Bill VB-xxxxx dibuat — langsung di-posting (match bersih); total + PPN masukan; status Terposting. | ✓ =S8 |  |  |  |
| S16-11 | Pembelian | VB Lunas; Sudah dibayar = total; jurnal terposting. | ✓ =S8 |  |  |  |

## Penutupan

- Lulus ___ · Gagal ___ · Terblokir ___
- Alur siap pakai: ___
- Keputusan bisnis: ___
- Rencana perbaikan & uji ulang: ___
- Tanda tangan: pemilik proses ___ · Production IT ___ · fasilitator ___ · pencatat ___

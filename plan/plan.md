# KNHOST ERP: Melanjutkan Audit dan Pengujian Sampai Tuntas

Kelanjutan pengembangan KNHOST, ERP tekstil untuk Kain Nusantara. Isinya gudang (WMS), penjualan, faktur, dan alur desain.
Putaran ini menuntaskan pengujian yang tertunda dan menutup sisa kasus audit. Setiap bug yang ditemukan langsung diperbaiki lalu diuji ulang sampai lulus.

## Untuk siapa
- Tim operasional Kain Nusantara: admin, manajer, staf gudang, staf penjualan, dan tim desain di entitas ent_ksc.
- Pemilik repo, supaya ERP tetap stabil dan alurnya bisa dipercaya dari awal sampai akhir.

## Fitur inti dan pengalaman yang diverifikasi
1. **Pembatalan transfer (tertunda dari putaran sebelumnya)**
   - Kalau transfer dibatalkan lewat jalur ubah status, sistem menolaknya. Pembatalan hanya bisa lewat aksi "Batalkan" yang wajib disertai alasan.
   - Begitu dibatalkan, roll yang tadinya dipesan untuk transfer itu kembali tersedia di gudang asalnya, tanpa sisa pesanan.
   - Alur status normal tetap jalan: disetujui → picking → staging → dikirim → selesai.
   - Di layar Manajemen Transfer: buat transfer Jakarta → Bandung berisi 1 roll, klik Batalkan, isi alasan. Status harus berubah jadi "Dibatalkan" tanpa pesan error.
   - Opsi "dibatalkan" yang sudah tidak terpakai dihapus dari aturan transisi status, supaya aturannya tidak membingungkan.
2. **Stok antargudang**
   - Transfer di dalam satu entitas dan antarentitas: jumlah stok di gudang asal dan tujuan harus cocok di setiap tahap.
   - Panjang kain yang dipesan dan yang tersedia harus selalu konsisten. Tidak boleh ada roll ganda atau roll yang hilang.
   - Riwayat audit tercatat untuk setiap perubahan.
3. **Penjualan sampai faktur**
   - Pesanan penjualan → pemesanan stok → pengambilan/pengiriman → faktur.
   - Total, pajak, dan sisa tagihan pada faktur harus sesuai dengan pesanan dan jumlah yang benar-benar dikirim.
   - Pembatalan atau perubahan di tengah alur harus melepas stok dengan benar.
4. **Alur desain**
   - Desain dibuat, ditinjau, disetujui atau ditolak, lalu dipakai di produksi atau penjualan.
   - Perpindahan status harus mengikuti aturan, dan hak akses per peran harus sesuai.

## Alur kerja
1. Uji pembatalan transfer dari sisi sistem dan layar aplikasi.
2. Rapikan aturan transisi status transfer.
3. Uji tiga area sisa satu per satu, dari sisi sistem dan layar aplikasi.
4. Untuk setiap temuan: perbaiki, uji ulang, dan catat di laporan audit.
5. Hapus semua data uji (berawalan TEST_) dan kembalikan roll ke kondisi tersedia.
6. Buat ringkasan akhir berisi status lulus/gagal per area dan daftar perbaikan.

## Nuansa UI/UX
- Tidak ada desain ulang. Tampilan dan bahasa (Indonesia) tetap seperti sekarang.
- Perubahan di layar dibatasi pada perbaikan bug. Contohnya pesan error yang jelas atau penanda tombol untuk pengujian.

## Tahapan implementasi
- **Fase 1 (MVP, dikerjakan sekarang):** semua yang ada di atas. Mulai dari verifikasi pembatalan transfer, perapian aturan transisi, sampai audit stok antargudang, penjualan sampai faktur, dan alur desain, berikut perbaikan bug dan uji ulang sampai lulus.
- **Fase 2:** pengujian regresi otomatis yang bisa diulang untuk alur-alur kritis di atas setiap kali ada perubahan.
- **Fase 3:** audit modul lain di luar tiga area ini, misalnya pembelian, produksi, dan laporan keuangan, dengan pola yang sama.

## Asumsi
- Kode yang dipakai adalah kondisi terakhir di lingkungan kerja ini, yang melanjutkan repo pandeyoga/KNHOST, termasuk laporan audit sebelumnya.
- Pengujian memakai akun yang sudah ada (admin@kainnusantara.id dan manajer) di entitas ent_ksc, dengan gudang wh_jakarta dan wh_bandung.
- Perbaikan bug dibatasi pada akar masalah. Tidak ada fitur baru atau refaktor besar.
- "Selesai" berarti semua kasus di tiga area plus pembatalan transfer lulus uji. Kalau ada kasus yang tidak bisa diselesaikan, akan dilaporkan terbuka sebagai belum lulus.
- Data uji ditandai TEST_ dan dibersihkan setelah selesai.
- Aturan bisnis yang tidak jelas, misalnya pembulatan pajak, mengikuti perilaku sistem saat ini kecuali jelas-jelas salah.

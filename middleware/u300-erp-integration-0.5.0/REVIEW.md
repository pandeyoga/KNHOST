# Review implementasi 0.5

## Hasil pemeriksaan dan perbaikan

- Validasi dokumen gabungan menggunakan sumber bisnis asli, bukan daftar roll yang diberikan client. Roll yang muncul pada dua SJ dalam kelompok ditolak.
- Evaluator memeriksa bahwa pergerakan aktif roll sama dengan sumber yang dipilih. Dokumen aktif lain tidak dapat digunakan untuk meloloskan manifest yang salah.
- Close memeriksa ulang setiap sumber terhadap snapshot awal. Pembatalan/perubahan dokumen setelah capture diuji; perubahan binding tidak mengubah lintasan yang sudah dimulai.
- Crossing claim tetap per SJ asli, bukan per kelompok. Regrouping setelah clearance tidak mengizinkan roll keluar kembali.
- Pagination menggunakan created_at dan identitas unik sebagai pembeda. Respons polling UI lama diabaikan setelah permintaan halaman yang lebih baru.
- Ekspor dan acknowledge memeriksa cakupan entitas seluruh dokumen dalam lintasan. Akun tanpa izin WMS dan kunci perangkat tidak dapat mengekspor.
- Acknowledge mempertahankan verdict lama dan event. Tidak ada pembersihan otomatis terhadap evidence maupun claim.

## Batas yang masih harus ditangani

1. **Hardware dan Android runtime:** belum tersedia U300. Tes host Java/HTTPS serta APK build tidak membuktikan perilaku RF, GPIO, antena, sensor, boot atau antrean SQLite ketika Android dihentikan.
2. **Frontend:** parsing JSX lulus. Build produksi penuh dan pengujian interaksi browser belum berhasil divalidasi pada checkout ini; dependency lokal belum tersedia secara normal. Wajib dilakukan sebelum merge/release.
3. **Staging:** belum ada alamat staging. Tes menjalankan router dan middleware terkait dengan MongoDB nyata, bukan seluruh aplikasi ERP.
4. **Recovery crossing:** belum ada flow administratif untuk membatalkan clearance yang salah secara terkontrol. Jangan menghapus claim manual sebagai prosedur rutin. Acknowledge hanya reset alarm.
5. **Hak akses:** masih menggunakan izin WMS view/scan dan admin konfigurasi yang tersedia. Izin terpisah khusus commissioning dan acknowledge belum dibuat.
6. **Kapasitas UI:** kandidat sumber masih dibatasi 200 dokumen aktif terbaru. Belum ada pencarian/pagination kandidat sumber. Riwayat lintasan sudah memiliki pagination.
7. **Pengelompokan:** gabungan hanya untuk SJ keluar. Transfer dan putaway diproses satu dokumen per lintasan. Satu logical gate per aplikasi. Kelompok gate tidak menggantikan dokumen dispatch.
8. **Dokumen sumber hilang:** akses bukti lintasan terkait ditolak ketika dokumen sumber tidak ditemukan untuk pemeriksaan scope. Prosedur arsip dokumen harus mempertahankan keterlacakan dan aksesnya sebelum produksi.
9. **Retensi dan operasi:** belum ada kebijakan retensi disetujui, signing produksi, distribusi update, dan acceptance beban nyata. Riwayat tidak dihapus otomatis.
10. **C72 dan CP30EN:** tidak termasuk aplikasi reader ini.

## Urutan lanjutan

Selesaikan build/acceptance UI, pencarian kandidat dokumen dan pemisahan izin operasional; rancang recovery crossing dengan jejak persetujuan; jalankan staging; kemudian commissioning hardware dan persetujuan produksi. Seluruh batas ini tetap terbuka meskipun 96 assertion integrasi lokal lulus.

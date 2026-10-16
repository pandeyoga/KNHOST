# Prompt perbaikan lanjutan IX07–IX10

Baseline `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. Gunakan bersama [bukti dan batas temuan](22_AUDIT_PERIODE_SCOPE_DAN_INSPEKSI.md). Setiap blok adalah tugas terpisah untuk agent develop. Jangan menganggap characterization test yang berhasil mereproduksi bug sebagai test regresi yang sudah benar.

## IX07 — Pengaturan Finance entitas lain dapat diubah melalui scope

```text
Perbaiki IX07 pada KNHOST.

Lokasi awal: backend/routers/settings.py:45, backend/services/entity_lifecycle_service.py:452.

Bukti: I5-SEC01 dan kontrol I5-C01. User finance U hanya mempunyai allowed_entity_ids=[A], dengan izin entity.update. GET /api/settings/effective?entity_id=B ditolak 403. PUT /api/settings dengan scope=B dan finance.base_currency=USD justru menghasilkan 200; konfigurasi efektif B berubah dari IDR menjadi USD.

Akar masalah: Route update hanya memeriksa apakah scope adalah entitas yang ada. Ia tidak memanggil resolver akses entitas seperti route baca. Penjaga body generik hanya mengenali entity_id dan owner_entity_id, sehingga nama field scope melewatinya. Keberadaan permission entity.update tidak memberikan user ini akses baca B; hak modul dan hak badan usaha menjadi tidak konsisten.

Tugas: Resolusi target scope harus memakai kebijakan entitas yang sama untuk baca dan tulis. Pisahkan hak perubahan global dari override entitas. Periksa status entitas dan penugasan aktor sebelum lookup/upsert; audit harus mencatat target B secara benar, bukan hanya konteks header A.

Acceptance: User A dengan entity.update tetap mendapatkan 403 saat menulis B; user yang ditugaskan ke B dapat mengubah B sesuai kebijakan. Uji scope global, all, entitas arsip, entitas tidak dikenal, header A/body scope B, dan perubahan melalui UI. Pastikan penolakan tidak meninggalkan perubahan konfigurasi.

Jalankan reproduksi pada database sintetis lokal terlebih dahulu. Tambahkan regression test yang mengharapkan perilaku benar, termasuk kontrol positif. Tinjau caller, router, UI dan job yang menggunakan kontrak sama. Jelaskan rencana rekonsiliasi record historis yang sudah terdampak; jangan memperbaiki atau menghapus data produksi otomatis. Laporkan perubahan, bukti pengujian dan batas cakupan.
```

## IX08 — Approval basi dapat menimpa penolakan buka periode dan mengaktifkan izin posting

```text
Perbaiki IX08 pada KNHOST.

Lokasi awal: backend/services/period_unlock_service.py:179, backend/services/period_unlock_service.py:208, backend/services/gl_service.py:463.

Bukti: I5-FN01, kontrol I5-C02. Permintaan dibuat memakai request_unlock terhadap periode September 2026 yang tertutup. Approval membaca pending lalu ditahan sementara. Rejection lain menyelesaikan penulisan rejected. Approval dilanjutkan dan menulis approved. Record akhir masih membawa rejected_by=Rejector, tetapi enforce_closed_period_guard menerima unlock tersebut. Kontrol terpisah menunjukkan pengusul memang ditolak jika menyetujui permintaannya sendiri.

Akar masalah: Approve dan reject memeriksa status dari snapshot, lalu update_one hanya memfilter id. Tidak ada conditional write status=pending atau version yang menjamin satu keputusan terminal. Dual control terhadap identitas pengusul tidak menyelesaikan konflik keputusan.

Tugas: Lakukan compare-and-set atas status pending dan versi, atau conditional find_one_and_update yang mengembalikan satu hasil keputusan. Pihak yang kalah wajib menerima konflik dan tidak membuat audit sukses. Pertahankan riwayat keputusan; jangan menghapus jejak penolakan dengan menormalisasi field secara buta. Tinjau idempotensi approve/reject serta permintaan ganda.

Acceptance: Jalankan approve-vs-reject, approve-vs-approve dan retry dengan barrier deterministik serta database nyata. Hanya satu keputusan boleh berhasil. Jika reject menang, find_active_unlock kosong dan guard jurnal harus menolak. Pertahankan kontrol self-approval dan expiry. Tambahkan uji jurnal lengkap serta rekonsiliasi sesudah reversal/periode tertutup.

Jalankan reproduksi pada database sintetis lokal terlebih dahulu. Tambahkan regression test yang mengharapkan perilaku benar, termasuk kontrol positif. Tinjau caller, router, UI dan job yang menggunakan kontrak sama. Jelaskan rencana rekonsiliasi record historis yang sudah terdampak; jangan memperbaiki atau menghapus data produksi otomatis. Laporkan perubahan, bukti pengujian dan batas cakupan.
```

## IX09 — Membuka kembali inspeksi tidak membatalkan indikator selesai pada retur

```text
Perbaiki IX09 pada KNHOST.

Lokasi awal: backend/services/inspection_service.py:798, backend/services/inspection_service.py:832, backend/services/return_service.py:580, frontend/src/features/sales/ReturnJourneyPanel.jsx:190.

Bukti: I5-WM02. finish pada dokumen inspeksi terkait retur mengisi sales_returns.inspect_done_at. Setelah reopen, inspeksi kembali in_progress dan finished_at kosong, tetapi inspect_done_at retur tetap berisi waktu penyelesaian lama. UI ReturnJourneyPanel menggunakan field retur ini untuk warna dan waktu milestone selesai. Efek visual ditelusuri dari kode; belum dilihat melalui browser.

Akar masalah: Sinkronisasi berjalan satu arah pada finish melalui mark_inspected_by_document. Reopen hanya mengubah dokumen inspeksi, tanpa memperbarui proyeksi milestone retur atau menandainya telah dibatalkan. Dua representasi status yang seharusnya konsisten menjadi berbeda.

Tugas: Tentukan SSOT status inspeksi dan cara proyeksi ke retur diperbarui pada finish, reopen, cancel dan pergantian dokumen aktif. Pertahankan history selesai sebelumnya dengan event pembatalan. Jika beberapa inspeksi dapat terkait ke satu retur, jangan mengosongkan milestone secara buta; hitung dari dokumen aktif yang menjadi dasar keputusan.

Acceptance: Finish → reopen mengubah milestone aktif retur menjadi belum selesai; history menyimpan keputusan sebelumnya. Finish ulang mengisi timestamp/versi baru. Uji beberapa SPK, retry sinkronisasi, kegagalan update retur, dan rendering ReturnJourneyPanel tanpa perlu refresh manual yang menyesatkan.

Jalankan reproduksi pada database sintetis lokal terlebih dahulu. Tambahkan regression test yang mengharapkan perilaku benar, termasuk kontrol positif. Tinjau caller, router, UI dan job yang menggunakan kontrak sama. Jelaskan rencana rekonsiliasi record historis yang sudah terdampak; jangan memperbaiki atau menghapus data produksi otomatis. Laporkan perubahan, bukti pengujian dan batas cakupan.
```

## IX10 — Baca dan keputusan buka periode tidak memeriksa penugasan entitas

```text
Perbaiki IX10 pada KNHOST.

Lokasi awal: backend/routers/period_unlocks.py:42, backend/routers/period_unlocks.py:75, backend/routers/period_unlocks.py:88, backend/services/period_unlock_service.py:179.

Bukti: I5-SEC02/SEC03 dan kontrol I5-C03. User U hanya ditugaskan ke A dan diberi period.unlock. POST membuat usul untuk B ditolak 403, tetapi GET list dengan entity_id=B mengembalikan usul sintetis B (200); POST /finance/period-unlocks/FOREIGN/approve mengubahnya menjadi approved (200). Pengusul usul B berbeda dari U sehingga kontrol dua orang tetap lolos.

Akar masalah: Create memanggil _resolve_entity. List dan active hanya memanggil current_user lalu meneruskan entity_id tanpa resolver; approve/reject mencari record berdasarkan id dan memanggil service tanpa memeriksa pemilik entitas. Validasi body tidak menolong karena approve tidak membawa entity_id.

Tugas: Resolve scope daftar dari konteks pengguna dan validasi semua query override. Untuk approve/reject, load resource lalu wajibkan akses write terhadap entity_id pemilik sebelum perubahan; jangan percaya header sebagai pemilik resource. Terapkan kontrak sama pada active dan batch reclose dengan membedakan operasi scheduler internal dari operasi user.

Acceptance: User A tidak dapat list/active/read/approve/reject milik B walaupun tahu ID dan memiliki period.unlock. User yang sah pada B tetap dapat memutuskan dengan dual control. Uji header A/query B, tanpa query, all, entitas arsip, dan request langsung tanpa UI. Tidak ada record maupun audit sukses yang berubah saat ditolak.

Jalankan reproduksi pada database sintetis lokal terlebih dahulu. Tambahkan regression test yang mengharapkan perilaku benar, termasuk kontrol positif. Tinjau caller, router, UI dan job yang menggunakan kontrak sama. Jelaskan rencana rekonsiliasi record historis yang sudah terdampak; jangan memperbaiki atau menghapus data produksi otomatis. Laporkan perubahan, bukti pengujian dan batas cakupan.
```

## PG01 — Tetapkan kontrak penyelesaian inspeksi

```text
Evaluasi PG01 pada inspection_service.finish dan InspectionDetailPanel. Saat ini satu dari dua baris selesai sudah memungkinkan keputusan terima untuk SPK. Cari persyaratan bisnis yang terdokumentasi: pemeriksaan penuh atau sampling. Jangan menganggap sampling selalu salah. Jika wajib penuh, validasi semua baris wajib sebelum finish. Jika sampling sah, implementasikan deklarasi plan, unit/lot yang dicakup, alasan pengecualian, hak override dan status unit belum diperiksa. Uji konsekuensi hold, retur dan pelepasan stok. Jika kebijakan belum ada, siapkan opsi konkret untuk keputusan pemilik; jangan mengarang aturan mutu universal.
```

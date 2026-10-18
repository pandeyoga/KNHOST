# Cara import, menyerahkan pekerjaan dan meminta validasi ulang

1. Ekstrak ZIP ke folder sementara. ZIP sudah memuat struktur `docs/development/gelombang-lanjutan-pasca-p05-2026-10-16/`; salin subtree tersebut ke repo. Source code ERP tidak disertakan dan tidak ditimpa oleh paket ini. Arsip plan lama tetap dipertahankan.
2. Buka README, DEVELOPMENT_PLAN dan KEPUTUSAN_AKTIF_RINGKAS. Berikan PROMPT_MULAI kepada agent. Mulai L00 dengan branch/commit repo aktual; jangan menganggap snapshot 14 Oktober adalah HEAD selamanya.
3. Kerjakan fase menurut dependency dan kirim report sesuai template. Requirement jelas dapat berjalan sementara jawaban client menunggu. Cabang yang memengaruhi keputusan/nominal tetap pending.
4. Saat implementasi tersedia, simpan commit dan evidence, lalu set `implemented_pending_validation`. Jangan mengganti status berdasarkan kalimat “sudah selesai” tanpa output yang dapat diperiksa.
5. Untuk meminta validasi ulang, berikan branch/full SHA, phase report, daftar requirement/acceptance yang diklaim selesai, data fixture dan bukti UI/API/stock/Finance yang relevan, migrasi, serta issue tersisa. Bila ada keputusan baru, berikan catatan asli dan interpretasi yang disetujui.
6. Reviewer menelusuri perubahan dan evidence, menguji ulang bagian terdampak, lalu mencatat verified commit dan hasil. Temuan yang gagal menjadi `reopened`, bukan tetap validated. Persetujuan owner dicatat sebagai file dengan SHA dan lingkup yang jelas.
7. Ulangi siklus sampai L14 dan closure. Semua sumber pending tetap terlihat. Jika owner memilih pilot sebagian, catat lingkup pilot dan jangan menyebut seluruh gelombang tuntas.

Dokumen turunan dirender dari BACKLOG; hindari dua tracker aktif dengan arti status berbeda. Perubahan keputusan diberi ID/tanggal/source dan riwayat penggantian, sehingga agent berikutnya tidak memakai asumsi lama kembali.

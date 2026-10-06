# Cakupan dan batas saat audit dihentikan

Denominator backend runtime/startup tetap 480 berkas, 72,221 statement dan 23,008 cabang. Tercakup 59,594 statement (82.52%) dan 15,727 cabang (68.35%). Belum tercakup 12,627 statement serta 7,281 cabang. Target 90% belum tercapai; audit tidak diberi label selesai menyeluruh.

Inventory seluruh file, parse, pencarian literal API, pembacaan source, eksekusi statement, eksekusi cabang, dan kebenaran angka UI adalah jenis bukti yang berbeda. Pemetaan frontend statis 1.431/1.477 panggilan (96,89%) tidak membuktikan 96,89% angka rendered benar. Sebanyak 46 pemetaan belum terselesaikan. Denominator seluruh tracked backend berisi 603 file, 102.029 statement dan 29.916 cabang, termasuk 107 native/POC test dan 16 skrip offline; pemisahan ini tidak diubah untuk menaikkan angka.

## Pekerjaan yang belum dinyatakan selesai

- Cabang/fungsi yang masih kosong di `evidence/continuation-90/function-gaps90.json` dan laporan coverage per file. Register dihasilkan dari tracing; daftar gap harus diperbarui terhadap commit sesudah perbaikan.
- Penelaahan semua kegagalan suite lama. Replay tambahan 49 modul menghasilkan 551 kasus: 357 lulus, 157 nonpass, 37 skip. Ini snapshot replay, bukan seluruh jumlah testcase unik audit. Sebagian memakai fixture lama/hardcoded resource atau kontrak lama; tetap terbuka untuk adjudikasi. Sampling performer adapter tercatat dan assertion asli dipertahankan.
- Browser/DOM numerik seluruh dashboard, RFID/gate fisik, pembacaan tag nyata, printer/stiker, dan integrasi AI/OCR provider nyata. Pemeriksaan source/ekspresi bukan uji perangkat atau browser.
- Dua jalur PDF OCR belum diuji karena PyMuPDF tidak tersedia dan instalasi mengalami batas lingkungan/TLS. Native mock OCR 67 kontrol lulus tidak membuktikan akurasi ekstraksi dokumen nyata.
- Data produksi dan migrasi produksi belum diuji. Fixture master/legacy yang sengaja tidak konsisten digunakan hanya untuk menguji scanner/backfill; tidak membuktikan producer normal membuat kerusakan tersebut.
- Semua temuan Gelombang 3 masih berstatus open sampai perbaikan dan validasi independen. Register 137 ID lama memiliki tingkat bukti berbeda; status historis bukan klaim terbaru bahwa seluruh acceptance sudah lulus.

## Kontrol yang lulus pada lanjutan

Label/master/tarif: 134 kontrol lulus. R&D edit dan feedback counter: 98 lulus. Cash-advance lifecycle: 52 lulus. Budget/GL/policy: 214 observasi, termasuk kontrol account direction, jumlah seimbang, anti-duplikasi replay dan batas amount; tujuh perbedaan menghasilkan tiga temuan. HR KPI: 36 observasi dengan tujuh perbedaan yang menghasilkan tiga temuan. Jumlah observasi bukan jumlah bug, bukan persentase kebenaran sistem, dan bukan penjumlahan testcase unik dari berbagai replay.

Beberapa hipotesis ditolak: kewenangan lintas entitas manager yang memang disengaja, helper gudang bersama yang bukan validator entitas, dan dua label dengan ekspektasi tes salah. Bukti awal dipertahankan sebagai histori, sementara hasil final menggunakan oracle/fixture yang dikoreksi. Penolakan otomatis saat membuat probe QC/CRM/config baru membuat aksi itu tidak dijalankan; probe tersebut tidak dimasukkan sebagai hasil pengujian.

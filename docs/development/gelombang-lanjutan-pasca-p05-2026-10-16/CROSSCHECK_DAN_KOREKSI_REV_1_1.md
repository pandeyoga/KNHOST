# Crosscheck paket dan koreksi revisi 1.1

ERP Kain Nussantara · Produksi IT PT Kubus Teknologi Indonesia · 16 Oktober 2026

Pemeriksaan ini mencocokkan planning dengan jawaban owner, sumber historis dan kode snapshot main `64d81f29577dae4daa86ddc64689dec7243804f2`. Pemeriksaan tidak mengambil HEAD remote baru dan tidak menjalankan audit ulang seluruh implementasi ERP.

## Koreksi substansi dan ketegasan aturan

| Bagian | Kekeliruan atau celah pada paket awal | Koreksi |
|---|---|---|
| LN-032 / L03 | Kalimat “Special Order tetap proofing” terlalu umum dan dapat mengubah jalur polos/woven/knitting menjadi proofing printing. MD-06 justru menetapkan uji sesuai lini. | Proofing/reproofing dan paper diberi konteks printing; labdip/handfeel lini lain dipertahankan. Ditambahkan acceptance jalur polos. Approval proofing saja tidak melewati uji lain yang diwajibkan. |
| LN-060 / L06 | Hanger 0,5 yard/2 kg tidak ditegaskan sebagai batas maksimal sehingga dapat dibaca sebagai qty wajib. | Dinyatakan sebagai maksimum, ditambah acceptance qty lebih kecil dan pelanggaran batas. Tidak ada konversi tetap kg menjadi yard. |
| LN-012 / L01 | Larangan grade sudah tegas, tetapi default LOT dan asal lokal/impor pada POV Sales belum cukup eksplisit. | Default Sales hanya varian warna; LOT/asal tersembunyi kecuali konfigurasi role yang diizinkan. Grade tetap tersembunyi termasuk trial. Profil akses menggunakan capability custom role, bukan nama role literal. |
| LN-020-T01 | Contoh ATP belum memberikan hasil numerik pembanding yang pasti. | Untuk 100 yard layak jual, 30 reserved dan 20 incoming: on-hand 100, reserved 30, free physical 70, incoming 20 terpisah. Forecast available-to-order harus dijelaskan sumbernya. |
| LN-093 / L09 | Retur supplier bergantung end-event deadline yang masih pending, tetapi hubungan ke KLR-09 belum tercatat pada requirement ini. | Ditambahkan dependency keputusan KLR-09 sehingga cabang supplier tidak dapat dinyatakan final berdasarkan tenggat asumsi. |
| LN-120 / L12 | Requirement parity juga memuat UAT integrasi fisik, tetapi dependency kesiapan hardware hanya ditautkan ke requirement perangkat lainnya. | LN-120 ikut ditautkan ke HW-01. Pekerjaan kontrak tetap dapat berjalan, validasi keseluruhan menunggu unit nyata. |

Pemeriksaan source mendukung pemisahan jenis sampling: handler desain approved di `backend/services/special_order_phase2.py` membuat proofing untuk konteks desain printing, sementara jalur revisi lain mempunyai pilihan labdip/handfeel. Ini digunakan untuk mencegah instruksi plan yang meratakan seluruh lini; bukan klaim handler tersebut telah diperbaiki.

## Koreksi tracker dan validator

1. **Lingkup dapat berkurang tanpa terdeteksi.** Validator awal memeriksa hubungan yang masih ada, tetapi satu acceptance biasa dapat dihapus bersama referensinya. SCOPE_BASELINE.json sekarang menyimpan inventory fase, requirement, acceptance, keputusan dan hubungan wajib. Perubahan inventory harus menjadi revisi lingkup yang ditinjau, bukan edit status biasa.
2. **Bukti commit berbeda dapat lolos pada tingkat requirement/fase.** Sekarang hasil acceptance harus cocok dengan commit verifikasi requirement, dan requirement dengan commit fase, atau memiliki impact assessment yang menunjuk commit tersebut. Pemeriksaan kandidat final tetap berlaku.
3. **Manifest sumber bersifat opsional.** Sekarang SOURCE_MANIFEST.json wajib tersedia. Inventory lingkup juga masuk pemeriksaan hash. Ini mendeteksi kehilangan/perubahan file tanpa penyesuaian paket yang disengaja; bukan tanda tangan kriptografis dari owner.
4. **Self-test bergantung kemajuan tracker.** Uji penolakan closure sebelumnya akan salah gagal ketika tracker sungguh sudah lengkap. Self-test sekarang memakai salinan fixture metadata yang terisolasi, memeriksa kondisi gagal tertentu dan memastikan struktur metadata lengkap dapat diterima. Fixture tidak ditulis ke BACKLOG dan tidak menjadi bukti ERP/hardware.

## Hasil dan batas validasi

Paket revisi tetap **15 fase dan 52 requirement**, kini **196 skenario penerimaan**. Terdapat **24 topik pending**: 14 topik client dan 10 kebutuhan data/review/operasional/perangkat/HR/UAT. Tidak ada jawaban client yang dibuat sendiri atau pending yang ditandai resolved dalam crosscheck ini.

Pemeriksaan mencakup pemetaan 369 ID sumber, konsistensi dependency, link dokumen aktif, lokasi file acuan pada snapshot, JSON, inventory lingkup, pengaman status/commit, hash sumber, isi ZIP serta kemampuan menjalankan validator dari paket yang diekstrak terpisah. Angka dan hasil aktual pemeriksaan paket dicatat pada PACKAGE_QA.json.

Seluruh status implementasi gelombang tetap not_started dan acceptance not_run. Kelulusan validator adalah kelulusan struktur/metadata paket; reviewer masih harus memeriksa substansi bukti implementasi. Dokumen sumber historis dipertahankan, termasuk aturan lama yang digantikan; keputusan aktif dibaca dari ringkasan, requirement dan overlay terbaru.

Gunakan ZIP berlabel Rev1_1. Nama ZIP tanpa nomor revisi juga diperbarui dengan isi yang sama agar tautan lama menunjuk paket terbaru. Arsip Rev1_0 dipertahankan sebagai jejak revisi, bukan untuk pengerjaan baru.

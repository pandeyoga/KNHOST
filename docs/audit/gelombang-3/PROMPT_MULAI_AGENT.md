# Prompt awal untuk agent development

Kerjakan Gelombang 3 dari commit repo saat ini. Baca README, findings-tracker.json, laporan detail, dan source terkait sebelum mengubah kode. Catat actual HEAD; commit audit hanya baseline bukti, bukan asumsi bahwa repo belum berubah. Periksa dulu apakah kasus sudah diperbaiki untuk menghindari patch ganda. Jangan menimpa dokumen Gelombang 1/2 atau mengubah hasil audit historis.

Untuk setiap ID: telusuri input UI → request/schema → permission/entity/lini → service → persist/ledger → projection/report → frontend, termasuk retry, concurrency, pembatalan dan reversal yang relevan. Pertahankan kuantitas fisik, unit, pemilik barang, source document, harga/HPP serta legal entity. Jangan mengubah expected menjadi hasil bug, menyembunyikan warning, atau menyimpulkan fixed hanya dari HTTP 200. Keputusan definisi bisnis yang belum tegas harus dicatat sebagai needs_business_decision.

Setelah implementasi, isi implementation_commit, implementation_evidence, daftar file, perbandingan expected/actual sebelum-sesudah, perintah uji, batas pengujian, dan risiko migrasi. Status agent paling jauh implemented_pending_validation; reviewer independen yang menetapkan verified_fixed setelah seluruh acceptance dan flow terkait lulus. Simpan proof baru terpisah, tanpa menimpa evidence baseline.

Mulai dari fase 01; lanjutkan sesuai repair-phases.json. Untuk satu PR, laporkan ID yang ditangani, scope perubahan, validasi numerik/flow, migrasi, risiko, dan temuan baru. Gunakan template di templates/STATUS_IMPLEMENTASI.md dan templates/PERMINTAAN_VALIDASI.md. Jangan menandai seluruh fase selesai bila ada acceptance yang belum diuji.

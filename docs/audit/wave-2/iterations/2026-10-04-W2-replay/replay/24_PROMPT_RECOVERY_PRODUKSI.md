# Prompt agent — konsistensi completion dan recovery produksi

Baca [laporan23](23_AUDIT_RECOVERY_DAN_KAPASITAS_PRODUKSI.md), [laporan21](21_AUDIT_PRODUKSI_PAYROLL_BANK.md), GN-06 Wave1 dan W2-024 pada tracker Wave2. Cocokkan source kandidat dengan snapshot `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Koordinasikan dengan agent yang mengerjakan GN-06 agar tidak membuat patch bersaing pada production_service. Simpan bukti baseline; reproducer lama mengassert cacat, bukan hasil regression yang benar.

## Fase1 — desain satu operation completion

Bekukan revision BOM/material plan pada release; klaim WO dengan status/version yang sesuai. Catat identitas operasi dan efek per input roll, movement, output lot/roll dan overhead JE secara durable. Gunakan transaction bila deployment mendukung atau saga terukur. Semua jalur retry harus melanjutkan operasi yang sama, bukan mengulang konsumsi/output. Helper idempotent harus mengembalikan identitas JE yang sudah ada; jangan mengosongkan je_id pada retry.

## Fase2 — W2-024 konsumsi penuh dan kontrol stok

Hilangkan batas diam-diam5.000 roll pada eksekusi. Iterasi/chunk dengan kontrol konkurensi; pastikan jumlah yang berhasil dikonsumsi sesuai requirement BOM sebelum output final. Scope owner/gudang/status/hold/unit tetap berlaku. Jika shortage muncul setelah sebagian konsumsi, simpan state recoverable. Menambah exception setelah mutasi tanpa recovery bukan perbaikan lengkap.

Acceptance:4.999/5.000/5.001 roll, ukuran campuran, beberapa komponen, stok tepat/kurang, roll held/reserved, dua WO berebut stok. Pada fixture rasio1:1 sebanyak5.001, harus tepat5.001 consumed untuk output5.001 dan biaya input50.010 sebelum overhead, atau operasi ditolak/pending tanpa completed palsu. Periksa movement, nilai roll, inventory balance dan rekonsiliasi GL, bukan hanya response.

## Fase3 — failure GL, retry dan cancel

Uji closed period asli sebelum complete, reopen lalu retry, kegagalan sesudah output/sebelum JE, sesudah JE/sebelum WO update, response hilang dan dua caller WO sama. Satu WO output5 harus mempunyai tepat satu output5, biaya bahan200+overhead15=215 dan overhead GL15. `produced_roll_ids`, `produced_qty`, movement dan je_id harus cocok. Cancel sesudah efek parsial harus menolak dengan instruksi recovery atau melakukan kompensasi aman. Jangan menghapus output yang sudah dikonsumsi/dikirim tanpa flow koreksi terhubung.

## Fase4 — data historis dan serah-terima

Sediakan dry-run untuk released/cancelled WO yang sudah memiliki output, completed WO dengan output lebih dari produced_roll_ids, missing je_id walau JE ada, overhead stok≠GL, dan consumed<required. Jangan otomatis menghapus stok atau menulis jurnal koreksi tanpa rekonsiliasi pemakaian turunannya. Serahkan commit, hasil regression normal/fault/concurrent/capacity, perubahan schema/migration dan batas yang belum diuji. Tandai siap validasi, bukan validated-fixed sebelum audit kandidat selesai.

# Prompt agent develop — tambahan Gelombang 2

Baca [laporan19](19_AUDIT_REFUND_ADVANCE_MULTI_PO_GL.md), tracker Gelombang2 dan bukti JSON. Snapshot audit `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`; cocokkan source kandidat terlebih dahulu. Jangan menimpa bukti baseline. Jangan menandai fixed hanya karena reproducer historis exit0: script tersebut mengassert perilaku cacat. Tulis regression dengan hasil bisnis yang benar.

## Fase 1 — W2-021: kebenaran agregasi laporan

Perbaiki total neraca saldo, buku besar dan shared financial-statement aggregation agar menghitung seluruh transaksi eligible, bukan `to_list(50000/100000)`. Periksa caller laba rugi, neraca dan tutup buku. Gunakan aggregation/streaming menyeluruh sesuai kebutuhan; pagination detail tidak boleh memengaruhi total. Pertahankan filter entity/date/status dan perlakuan closing masing-masing laporan. Jangan hanya menaikkan limit.

Acceptance: dataset 49.999/50.000/50.001 dan 99.999/100.000/100.001 jurnal, campuran debit/kredit, void, dua entitas, tanggal batas dan source closing. Total per akun, total laporan dan closing harus cocok oracle independen. Jumlah transaksi berbeda tidak boleh tersembunyi oleh indikator balanced. Uji API dan export yang memanggil service tersebut. Ukur penggunaan resource tanpa membatasi kebenaran hasil. Sertakan daftar laporan/caller yang sudah diverifikasi.

## Fase 2 — W2-020: kelengkapan efek settlement refund

Rancang durable operation identity dan status efek refund yang mengikat stok, credit note, GL dan buku kas. Jangan menyatakan `refund_settled` bila efek wajib belum tercatat. Pilih transaksi yang didukung deployment atau saga/outbox dengan recovery terukur. Retry harus memeriksa kelengkapan dan melanjutkan efek yang hilang; tidak menggandakan yang sudah berhasil. Hilangkan sukses palsu dari broad exception handling tanpa meninggalkan efek terdahulu yang tidak dapat dipulihkan.

Acceptance: normal refund, retry serial/concurrent, kehilangan HTTP response setelah commit, exception sebelum/sesudah setiap efek, restart worker, reversal sebelum/sesudah recovery. Contoh Rp50.000 harus selalu mempunyai kas/GL/credit note konsisten dan satu efek stok, atau status pending/failed yang terlihat dengan recovery deterministik. Sediakan dry-run rekonsiliasi retur historis final yang kasnya hilang/salah akun/salah entitas/void. Jangan otomatis menciptakan transfer bank berdasarkan catatan audit; koreksi pencatatan harus mengikuti bukti transaksi nyata.

## Fase 3 — koordinasi CX-04/CX-05 dengan agent Gelombang1

Jangan membuat implementasi paralel atas file yang sedang diperbaiki agent Gelombang1. Gunakan `advance-results.json` sebagai acceptance tambahan: dua caller membaca approved harus hanya menghasilkan satu pencairan Rp100.000; retry setelah partial failure harus bisa dipulihkan. Settlement kumulatif tidak boleh Rp200.000 untuk advance Rp100.000 tanpa kewajiban/reimbursement sah. Expense Rp80.000 tidak boleh menutup residual Rp20.000 sebelum cash return/penyelesaian sah. Uji atomicity residual, refund, reimbursement, cancellation, GL failure dan semua approval role. Pertahankan ID CX-04/CX-05; catat evidence tambahan di tempat yang tidak menimpa pekerjaan agent lain.

## Fase 4 — koordinasi FN-09 dan regresi lintas laporan

Terapkan aturan periode tertutup pada void/koreksi selain create. Gunakan mekanisme unlock berotorisasi atau reversal pada periode berjalan sesuai kebijakan; penandaan stale saja tidak mencukupi. Uji dataset `wave2_gl_close.py` dengan ekspektasi void tanpa izin ditolak dan angka September tidak berubah. Uji reopen/reclose, unlock yang expired, dua keputusan bersamaan dan audit history. Pastikan W2-021 tidak membuat closing memakai laba terpotong di dataset besar.

## Serah-terima dan validasi

Untuk setiap ID W2: catat commit implementasi, file/baris berubah, hasil regression, batas yang belum diuji dan hasil rekonsiliasi historis. Status implementation-ready tidak sama dengan validated-fixed; auditor akan menjalankan validasi pada commit kandidat. Pertahankan fixture dan hasil audit lama. Tambahkan kontrol multi-PO dari `wave2_multi_po.py` untuk memastikan perubahan receiving/recovery tidak mencampur produk/PO atau menghasilkan remainder palsu. Seluruh browser/hardware dan flow yang belum dites tetap terbuka di matriks utama.

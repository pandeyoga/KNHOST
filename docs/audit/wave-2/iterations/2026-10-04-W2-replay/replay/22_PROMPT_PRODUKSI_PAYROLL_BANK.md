# Prompt perbaikan — produksi, payroll dan bank

Baca [laporan21](21_AUDIT_PRODUKSI_PAYROLL_BANK.md), bukti JSON dan tracker. Snapshot audit `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Cocokkan source kandidat dengan snapshot; jangan menimpa evidence lama. Reproducer mengassert cacat historis; ubah menjadi regression dengan ekspektasi bisnis benar pada folder validasi terpisah.

## Fase A — W2-023: validasi sumber dana sebelum mutasi

Perbaiki kontrak payout payroll. Akun/rekening harus merupakan sumber kas/bank aktif yang sah bagi entitas run. Tolak kode beban `6-1000`, akun header/nonaktif, kode salah dan mapping owner yang salah. Default hanya ketika input kosong dengan konfigurasi valid. Jangan mengganti input salah diam-diam. UI memilih master yang sama; backend tetap memvalidasi request langsung.

Acceptance: input salah tidak mengubah status payroll, utang gaji, jurnal atau buku kas. Input kas/bank valid tetap berhasil. Sertakan API tests memakai role berizin dan scope yang sesuai.

## Fase B — W2-022: payroll payment sebagai satu operasi bisnis

Hubungkan run, rekening kanonik, jurnal dan cash transaction dengan durable payment operation ID. Buat kas keluar tanpa double-post GL. Status paid hanya setelah efek wajib konsisten; gunakan transaksi bila deployment mendukung atau saga dengan pending/error/recovery yang terlihat. Idempotency harus berlaku pada operasi bisnis, bukan hanya satu tabel. Tetapkan cara menghubungkan bukti pembayaran nyata sesuai flow produk; jangan menganggap menulis GL sama dengan transfer bank.

Acceptance: fixture100.000 menghasilkan satu utang gaji saat accrual, kemudian satu kas keluar dan satu JE pembayaran yang menetralkan utang. Uji retry serial/bersamaan, exception setelah setiap write, restart/recovery, response hilang dan koreksi pembayaran. Cash account/owner/amount cocok antar-subledger. Sediakan dry-run payroll paid tanpa cash row, dengan pemeriksaan kemungkinan pencatatan manual sebelum backfill. Jangan otomatis melakukan pembayaran bank historis.

## Fase C — perluasan W2-021: agregasi rekening

Tambahkan `bank_service._txns_for`, `_enrich`, `list_accounts` dan `account_ledger` ke scope W2-021. Pisahkan total keseluruhan dari pagination transaksi. Saldo, reconciled balance, inflow/outflow, jumlah transaksi dan opening/running balance harus berasal dari seluruh data eligible, bukan5000 baris terakhir. Pertahankan void/filter rekening/entitas dan urutan kronologis detail.

Acceptance:4.999/5.000/5.001 transaksi campuran in/out/void/reconciled, beberapa tanggal dan rekening. Bandingkan total dengan aggregation oracle; pagination detail tidak mengubah total. Jalankan kembali regresi50.001/100.001 jurnal dari fase sebelumnya. Jangan sekadar menaikkan limit.

## Fase D — koordinasi GN-06 dan FN-08 milik Gelombang1

GN-06: bekukan BOM revision/plan saat release, klaim completion dan kendalikan konsumsi roll secara atomik. Simpan progres konsumsi per komponen/roll, identitas output dan posting overhead. Failure setelah konsumsi A harus dapat dilanjutkan tanpa mengonsumsi A lagi. Fixture dua bahan harus berakhir dengan biaya bahan200, overhead15, output215; tidak boleh ada konsumsi tambahan100 yang hilang. Uji shortage preflight, perubahan BOM sesudah release, dua WO berebut stok, duplicate completion, crash per langkah dan recovery. Pertahankan genealogy dan nilai stok.

FN-08: opening rekening harus memiliki basis jurnal/tanggal/entitas yang dapat direkonsiliasi. Edit opening setelah digunakan memerlukan koreksi yang ditelusuri, tidak boleh sekadar menggeser saldo historis. Uji opening100, inflow20/outflow5, koreksi opening dan konsistensi GL/subledger. Jangan menimpa patch agent Gelombang1; tambahkan evidence ini ke validasi tiket yang sama.

## Serah-terima

Catat commit, perubahan file, hasil uji, rekonsiliasi historis dan batas belum diuji per ID. Jangan mengubah status menjadi validated-fixed sebelum auditor mereview kandidat. Payroll fixture ini menonaktifkan BPJS/PPh; tidak boleh digunakan sebagai bukti keakuratan pajak. Simpan raw hasil/commit/database sintetis dan daftar known failure yang tersisa.

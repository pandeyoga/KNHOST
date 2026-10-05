# Bukti uji lanjutan

Snapshot `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. Ada 14 skenario: 13 menunjukkan perilaku cacat, 1 kontrol yang benar. CX-10 mempunyai dua skenario; karena itu jumlah skenario bukan jumlah temuan. CX-13 belum diuji secara runtime.

Metode: badan fungsi asli diambil dengan AST dari checkout, lalu dieksekusi dengan fixture sintetis dan dependency/query model terbatas. Fungsi GL, rendering/QR, policy tertentu dan layanan samping dapat diganti stand-in; hasil ini tidak membuktikan startup aplikasi, izin HTTP, transaksi Mongo, concurrency aktual atau bentuk PDF akhir. Unsupported query pada model menyebabkan error, bukan dianggap cocok.

[Harness lanjutan](review_repro/review3_proofs.py) bergantung pada [harness dasar](review_repro/review2_flow_proofs.py). [Hasil JSON](review_repro/review3_proofs.json). Jalankan dengan Python dan KNHOST_REPO menunjuk checkout audit. Instruksi ada di [README](review_repro/README.md).

| Skenario | Jenis | Hasil teramati |
|---|---|---|
| V3-01 | defect | `{"requested": 10, "applied": 150.0, "balance": -50.0}` |
| V3-02 | defect | `{"credit_customer": "C", "credit_entity": "A", "paid_customer": "OTHER", "paid_entity": "B", "applied": 50.0}` |
| V3-03 | defect | `{"order_paid": 50.0, "credit_balance": 100.0, "customer_locked": false, "redemptions": 0}` |
| V3-C1 | control | `{"wrong_customer_rejected_when_passed": true}` |
| V3-04 | defect | `{"cash_entries": 2, "cash_sum": 200.0, "approved_amount": 100}` |
| V3-05 | defect | `{"advance": 100, "settlement_count": 2, "expense_posted": 200.0}` |
| V3-06 | defect | `{"line_direction": "out", "txn_direction": "in", "line_bank": "BANK1", "txn_bank": "BANK2", "result": "matched"}` |
| V3-07 | defect | `{"txn_amount": 100, "reconciled_amount": 120.0}` |
| V3-08 | defect | `{"original_second_paid": 100, "new_second_paid": 50.0, "new_second_seq": 3, "targeted_payment_seq": 2}` |
| V3-09 | defect | `{"scope": ["A"], "foreign_elimination": ["B", "C"], "assets": 70.0, "balanced": true}` |
| V3-10 | defect | `{"stored_hash": "OLD_HASH", "current_document_amount": 999, "valid": true}` |
| V3-12 | defect | `{"new_document_amount": 999, "signature_attached": true}` |
| V3-13 | defect | `{"parent_status": "done", "other_delivery_status": "in_transit"}` |
| V3-11 | defect | `{"original_net": 300, "full_return_net": 400.0}` |

## Batas interpretasi per kelompok

- V3-01–03 memakai fungsi penebusan, validator dan aplikasi AR asli; penghitungan finansial/pencatatan GL tertentu memakai stand-in. Kesimpulan adalah urutan side effect dan input validation, bukan rekonsiliasi akun aktual.
- V3-04 menyuntikkan satu kegagalan GL, lalu mengulang command asli. Dua record kas tidak berarti bank sungguhan telah mendebit dua kali.
- V3-05 merekam dua jumlah settlement melalui stand-in GL. Sumber post_petty_cash_settlement diperiksa terpisah dan memang mengkredit advance sebesar expense.
- V3-06/07 memakai manual_match/match_split/_link asli; normalisasi direction dan learn-from-manual disederhanakan. Fixture menggunakan enum in/out langsung.
- V3-08 menggunakan reschedule/recompute asli dengan targeted-payment mapping sintetis seq2:100. _receipt_line_targets dibaca terpisah untuk mengonfirmasi kontrak seq, bukan menjalankan seluruh receipt lifecycle.
- V3-09 menyederhanakan laporan satu entitas menjadi assets100/equity100 dan mematikan auto-sync eliminasi; pengambilan serta penjumlahan eliminasi memakai fungsi asli.
- V3-10/12 menggunakan hash sentinel OLD_HASH dan dokumen nominal999 untuk membuktikan tidak adanya pemeriksaan hash saat verify/attach. Tidak membuat tanda tangan kriptografis, OTP nyata atau PDF sungguhan.
- V3-11 memakai pembentukan credit note asli, dengan cost dan GL stand-in; diskon, tax dan refund bank tidak diuji oleh fixture ini.
- V3-13 menjalankan callback serta transition parent asli. Lookup relasi OD/SO distub; fixture dua delivery menggambarkan keadaan yang tidak dibaca callback. Caller logistics diperiksa statis. Koleksi delivery pada fixture adalah penanda kondisi, bukan klaim bahwa seluruh logistics API telah dieksekusi.

## Cara membaca hasil

Semua assertion harness yang dilaporkan lulus berarti bug berhasil direproduksi atau kontrol memberikan hasil yang diharapkan, **bukan aplikasi lolos uji kelayakan**. Setelah diperbaiki, assertion karakterisasi bug ini harus diganti dengan expectation perilaku yang benar dalam test suite proyek.


## Verifikasi paket laporan

Harness yang diekspor dijalankan ulang dari folder deliverable dengan KNHOST_REPO menunjuk checkout yang sama: hasil14 skenario identik dengan hasil kerja. Pemeriksaan otomatis menemukan0 tautan rusak pada8780 tautan sumber dan38 tautan lokal dalam paket laporan yang diperiksa (00,04,07,13–17). Checkout aplikasi tetap bersih; tidak ada source aplikasi yang diubah.

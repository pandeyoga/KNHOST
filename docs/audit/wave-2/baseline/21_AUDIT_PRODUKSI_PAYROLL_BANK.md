# Produksi → valuasi; payroll → kas; rekening → laporan

Tanggal 2026-10-03. Snapshot `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Audit tambahan Gelombang2, bukan validasi fix. Source aplikasi dan tracker Gelombang1 tidak diubah.

## Hasil dan metode

30 checkpoint tambahan:20 kontrol,4 reproduksi cacat W2,6 pendalaman Wave1. Total226 checkpoint:169 kontrol,32 reproduksi cacat W2,6 observasi kebijakan,19 pendalaman Wave1. Tracker23 ID W2: dua baru022/023, perluasan021 tanpa ID duplikat. Satu flow bisa memiliki beberapa checkpoint; angka ini bukan persentase coverage.

| Harness dan bukti | Cakupan | Batas |
|---|---|---|
| [production-flow-results.json](production-flow-results.json), [reproducer](repro/wave2_production_flow.py) | 11 checkpoint; BOM → WO → release → konsumsi dua bahan → output → overhead GL; shortage, edit BOM, fault dan retry | Service asli + Mongo berindeks; fault sintetis sebelum bahan kedua, bukan crash proses; bukan seluruh race/yield/byproduct. |
| [payroll-flow-results.json](payroll-flow-results.json), [reproducer](repro/wave2_payroll_flow.py) | 11 checkpoint; create → submit/reject → approve → GL → pay; pembayaran via HTTP ASGI | Fixture satu karyawan, BPJS/PPh dinonaktifkan untuk mengisolasi pencatatan; **bukan validasi tarif/pajak atau kepatuhan payroll**. Approval melalui service; matriks pemisahan role belum lengkap. |
| [bank-flow-results.json](bank-flow-results.json), [reproducer](repro/wave2_bank_flow.py) | 8 checkpoint; opening/update rekening, ledger, reconcile dan kapasitas5.001 transaksi | Cash transactions ditanam langsung sebagai fixture; tidak mengklaim5.001 pembayaran bisnis dieksekusi. Tidak ada bank eksternal. |

Ketiga harness selesai tanpa mengubah source. Replay payroll kedua memperkuat pembayaran dari service menjadi API; hanya11 checkpoint unik dihitung, bukan22. DB sintetis terpisah; koneksi keluar diblok oleh harness. Keberhasilan reproducer berarti bukti lama konsisten, bukan cacat sudah diperbaiki.

## W2-022 — P1: payroll paid tanpa transaksi buku kas

**Lokasi:** [hr_payroll_service.py:419](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/hr_payroll_service.py#L419), [gl_service.py:2684](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/gl_service.py#L2684), [router pembayaran:164](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/hr_payroll.py#L164).

**Bukti `W2-PAY-F01`:** satu karyawan menghasilkan gross/net100.000 sesuai fixture tanpa potongan. Draft tidak dapat langsung disetujui/dibayar. Setelah submit, approve dan post, jurnal utang gaji100.000 terbentuk. `POST /api/hr/payroll/runs/{id}/pay` dengan akun `1-1100` menghasilkan HTTP200 dan status paid. Buku besar kas menjadi−100.000; utang gaji nol. Akan tetapi seluruh `cash_transactions` entitas A tetap0.

**Akar masalah:** `pay_run` memanggil helper GL, lalu menandai paid. `pay_payroll_run` membuat pasangan Dr utang gaji / Cr kas dan mengembalikan jurnal; tidak ada pencatatan buku kas. Router setelah service hanya menulis audit. Kontrak buku kas/rekening menggunakan `cash_transactions`, sehingga pembayaran tidak muncul sebagai mutasi yang dapat dicocokkan di rekonsiliasi bank. Ini bukan kegagalan sesaat seperti W2-020: jalur normal memang melewatkan subledger kas.

**Dampak:** GL dan buku kas berbeda pada pembayaran sah; operator rekonsiliasi tidak mempunyai transaksi sumber untuk payroll. Tidak menyimpulkan uang sungguhan ditransfer: tidak ada koneksi bank dalam pengujian. Status paid adalah status aplikasi.

**Perbaikan:** gunakan operation identity payroll payment yang mengikat run, entitas, rekening, GL, cash ledger dan bukti pembayaran. Pencatatan kas harus tidak memposting GL kedua kali. Finalisasi paid sesudah semua efek wajib selesai atau durable pending jelas. Tentukan mapping rekening kanonik, bukan hanya kode GL. Rekonsiliasi historis mencari payroll paid dengan GL tetapi tanpa cash ledger sebelum membuat koreksi, agar tidak menduplikasi catatan manual yang sudah dibuat operator.

**Acceptance:** pembayaran normal, retry serial/bersamaan, kegagalan setiap write, response hilang, recovery dan pembatalan/koreksi menghasilkan tepat satu mutasi kas dan satu jurnal yang saling terhubung. Nilai/akun/owner buku kas cocok GL dan utang gaji. Cek transaksi bank yang telah dicocokkan sebelum membatalkan.

## W2-023 — P1: akun beban diterima sebagai akun pembayaran payroll

**Lokasi:** [PayRunInput:11](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/schemas_hr_payroll.py#L11) menerima string opsional; [gl_service.py:2698](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/gl_service.py#L2698) hanya mencari kode akun postable global, tanpa validasi kategori kas/bank. Bila tidak ditemukan, helper menggantinya dengan akun default.

**Bukti `W2-PAY-F02`:** payroll periode berikutnya100.000 dibuat, disetujui dan diposting. Endpoint pay menerima `cash_account='6-1000'` (Beban Gaji), HTTP200. Status menjadi paid dan jurnal pembayaran mengkredit Beban Gaji100.000. Dengan demikian beban yang sebelumnya dibukukan terhapus untuk run itu dan kas tidak berkurang melalui jurnal pembayaran.

**Akar masalah:** keberadaan akun postable dianggap cukup untuk menjadi kas. Validasi harus memeriksa peran akun pembayaran, status aktif, pemetaan rekening dan kepemilikan, bukan sekadar string/kode valid. Ini bukan uji akses pengguna tanpa izin: sesi fixture memang memiliki `hr.manage_payroll`.

**Perbaikan:** validasi rekening/akun payout terhadap master dan kebijakan kas/bank; tolak akun beban/utang/pendapatan, akun nonaktif/header dan kode salah secara eksplisit sebelum mutasi. Bedakan input kosong yang boleh memakai default konfigurasi dari input salah yang tidak boleh diam-diam diganti. Pastikan UI memakai daftar sumber yang sama, tetapi guard backend tetap wajib.

**Acceptance:** akun kas/bank sah berhasil; akun beban contoh di atas ditolak tanpa JE/status/cash mutation. Uji invalid code, inactive/header, mapping hilang dan owner tidak cocok. Validasi server harus tetap berlaku ketika request dibuat langsung tanpa UI.

## GN-06 — pendalaman produksi, tanpa tiket baru

**Lokasi:** [production_service.py:358](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/production_service.py#L358), konsumsi pada [302](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/production_service.py#L302), pengambilan BOM terbaru dan loop konsumsi sebelum status final.

**Kontrol normal:** output5 membutuhkan A10@10 dan B5@20, biaya bahan200. Overhead3 per output menambah15; output bernilai215/unit43. Bahan tersisa A10/B15 dari masing-masing20. GL hanya mengkapitalisasi overhead15. Retry completed tidak menambah output; cancel completed ditolak. Bila bahan B sejak awal hanya4, preflight menolak tanpa mengubah A/B.

**Bukti edit BOM `W2-PROD-E01`:** setelah WO dirilis dengan kebutuhan A10, BOM diubah dari2 menjadi3 per output. Complete mengonsumsi A15. WO lama mengikuti resep terbaru, bukan komitmen yang dirilis.

**Bukti fault/retry `E02..E04`:** pertama A10 dikonsumsi, lalu exception sebelum konsumsi B. WO tetap released; A tersisa10, B20, output0. Hook dilepas dan complete diulang. A10 dikonsumsi lagi, B5 dikonsumsi, output5 dibuat. WO hanya mencatat biaya bahan200, sedangkan movement aktual menunjukkan bahan bernilai300 telah keluar. Output215 sudah termasuk overhead15; nilai bahan100 hilang dari stok tanpa masuk valuasi output atau adjustment loss yang terhubung.

**Implikasi:** preflight seluruh bahan membantu shortage statis tetapi tidak memberi atomicity/recovery. Retry harus melanjutkan langkah yang tersimpan, bukan menjalankan ulang loop dari awal. Bekukan revision BOM/material plan pada release dan gunakan klaim WO, kontrol stok atomik, operation identity movement/output serta recovery durable. Koordinasikan dengan agent Wave1 yang menangani GN-06; jangan membuat patch bersaing.

## FN-08 dan perluasan W2-021 — saldo rekening

**FN-08 runtime:** [bank_service.py:68/89](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/bank_service.py#L68). Opening100 menciptakan saldo bank100 tanpa jurnal. Setelah kas masuk20 dan keluar5, saldo115; transaksi void999 dikecualikan. Menandai inflow reconciled memberi saldo rekonsiliasi120 dan satu transaksi belum dicocokkan. Mengedit opening menjadi200 menggeser saldo menjadi215, jurnal tetap0. Bukti `W2-BANK-E01/E02`, tanpa ID baru.

**W2-021 bertambah area rekening:** [bank_service.py:23](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/bank_service.py#L23) memakai `.to_list(5000)`. Rekening terpisah opening0 dengan5.000 inflow masing-masing1 menghasilkan5000, benar. Inflow ke5.001 ada di Mongo, tetapi ledger, saldo reconciled dan overview rekening tetap5000. Bukti `W2-BANK-F01/F02`. Bahkan running balance detail berasal dari kumpulan terpotong. W2-021 kini mencakup batas5.000 kas,50.000 jurnal TB/ledger,100.000 jurnal financial statements. Pertahankan satu tiket agregasi terpotong dengan daftar lokasi lengkap; perbaikan harus meliputi semuanya.

## Status coverage

PROD-01/04, HR-03 dan APAR-06 memperoleh bukti tambahan; semuanya tetap memiliki batas. Bukti recovery terkait PROD-02 adalah failure konsumsi bahan, belum failure GL. Multi-step/yield/byproduct, dua WO berebut stok, full payroll tax/commission/reversal, bank statement matching lengkap, UI dan hardware belum ditutup. Lihat [matriks](18_MATRIKS_FLOW_KRITIS.md) dan [prompt](22_PROMPT_PRODUKSI_PAYROLL_BANK.md). Semua temuan tetap open pada snapshot ini.

# Pendalaman refund, uang muka, multi-PO dan buku besar

Tanggal 2026-10-03. Snapshot `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`. Ini audit Gelombang 2 pada snapshot lama, **bukan validasi perbaikan** yang sedang dikerjakan agent lain. Tidak mengubah source aplikasi atau tracker Gelombang 1.

## Metode dan cakupan

Service aplikasi asli, Mongo lokal dengan indeks aplikasi, database sintetis terpisah per harness. Refund melalui API ASGI; uang muka, multi-PO dan GL melalui service asli. Tidak ada pembayaran bank nyata, browser, scheduler atau hardware. Reproducer mengharapkan kondisi cacat historis; exit sukses tidak berarti bug sudah fixed.

| Bukti | Checkpoint | Cakupan dan batas |
|---|---:|---|
| [advance-results.json](advance-results.json) | 8 | 5 kontrol, 3 pendalaman CX-04/CX-05. Approval memakai actor admin sintetis; bukan matriks pemisahan tugas seluruh role. |
| [multi-po-results.json](multi-po-results.json) | 8 | 8 kontrol. Dua PO, dua produk, dua task, satu supplier/gudang/entitas; partial dan cancel. |
| [cash-refund-results.json](cash-refund-results.json) | 8 | 6 kontrol, 2 reproduksi W2-020. Delivered order melalui lifecycle API; klasifikasi cash disetel sebagai fixture setelah delivery. Penerimaan tender awal belum teruji. |
| [gl-close-results.json](gl-close-results.json) | 10 | 9 kontrol, 1 pendalaman FN-09. Dataset jurnal manual, laporan dan close/reopen asli; belum seluruh posting subledger. |
| [gl-capacity-results.json](gl-capacity-results.json) | 7 | 4 kontrol, 3 reproduksi W2-021. Jurnal seimbang ditanam massal; yang diuji query laporan asli, bukan 100.001 proses posting bisnis. |

Total tambahan 41 checkpoint: 32 kontrol, 5 reproduksi cacat baru, 4 pendalaman temuan lama. Replay 19 kontrol sales sebagai pembentuk fixture refund tidak dihitung lagi. Total kumulatif 196 checkpoint: 149 kontrol, 28 reproduksi cacat W2, 6 observasi kebijakan, 13 pendalaman Wave1; 21 ID W2. Ini bukan persentase source coverage maupun 196 flow independen.

## W2-020 — P1: refund dinyatakan selesai walau buku kas gagal ditulis

**Letak kode:** [return_service.py:1268](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/return_service.py#L1268), handler exception pada 1279, finalisasi pada 1311, dan early return retry pada 1196. Helper [cash_ledger.py:30](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/cash_ledger.py#L30) mencatat buku kas tanpa memposting GL lagi.

**Flow:** retur 5 meter × Rp10.000 → approve → inspect → settle refund. Pada kontrol normal terbentuk satu kas keluar Rp50.000, kredit kas GL Rp50.000 dan stok karantina 5 meter. Retry tidak menggandakan kas/jurnal; reversal membuat kas void, menghapus stok karantina dan menetralkan kredit kas GL.

**Reproduksi kegagalan:** harness menyisipkan exception sebelum helper buku kas menulis data, setelah jurnal credit note berhasil. API tetap HTTP 200 dengan `status=refund_settled`; GL mengkredit kas Rp50.000, tetapi `cash_transactions` untuk retur tersebut berjumlah nol. Helper dipulihkan, permintaan settle diulang: buku kas tetap kosong. Bukti `W2-CR-F01/F02`.

**Akar logika:** exception buku kas hanya dicatat ke log. Kode melanjutkan `finish_set` ke status final. Idempotency hanya memeriksa status/outcome, sehingga respons sukses lama dikembalikan tanpa memeriksa kelengkapan efek. Lock mencegah dua eksekusi aktif, tetapi tidak menjamin kas, GL, credit note dan stok selesai sebagai satu operasi bisnis.

**Dampak:** buku kas dan GL berbeda, operator melihat refund selesai, proses retry biasa tidak memulihkan transaksi. Ini bukti pencatatan internal tidak konsisten; tidak membuktikan uang sungguhan sudah ditransfer atau belum. Berhubungan dengan pola FN-10/GN-11, tetapi kegagalan buku kas pada refund jual ini mempunyai lokasi, efek dan acceptance tersendiri sehingga dicatat W2-020.

**Perbaikan:** catat kewajiban efek refund secara durable, gunakan identitas operasi tetap dan status tiap efek; final hanya setelah kewajiban terpenuhi. Jika memakai transaksi, sesuaikan dukungan deployment. Jika memakai saga/outbox, tampilkan status gagal/pending yang dapat dilanjutkan; retry melengkapi efek yang hilang tanpa memposting GL/stok lagi. Jangan sekadar menghapus catch: stok dan GL sebelumnya sudah berubah. Rekonsiliasi historis harus mengidentifikasi retur final tanpa buku kas, termasuk nominal, akun, entitas dan status reversal, sebelum koreksi disetujui.

## W2-021 — P1: batas query memotong laporan keuangan tanpa indikator

**Letak kode:** [gl_service.py:2734](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/gl_service.py#L2734) menggunakan `to_list(50000)` untuk neraca saldo; [2787](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/gl_service.py#L2787) memakai batas sama untuk buku besar. [financial_statement_service.py:60](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/financial_statement_service.py#L60) membatasi agregasi laporan pada 100.000 jurnal.

**Dataset:** setiap jurnal fixture posted entitas A mendebit kas 1 dan mengkredit pendapatan 1, pada periode yang sama. Identitas/nomor berbeda; indeks asli aktif. Jumlah dokumen dan agregasi Mongo independen menjadi oracle, tanpa mengandalkan jawaban fungsi laporan yang sedang diuji.

**Bukti:** tepat 50.000 jurnal menghasilkan neraca saldo 50.000, sesuai. Setelah menjadi 50.001 jurnal, oracle menunjukkan 50.001, tetapi neraca saldo dan buku besar kas tetap 50.000. Neraca saldo bahkan `balanced=true`. Laba rugi masih menunjukkan 50.001 pada dataset itu. Setelah dataset menjadi 100.001 jurnal, laba rugi berhenti pada pendapatan 100.000. Lihat `W2-GCAP-C01..C04/F01..F03`.

**Akar logika:** batas materialisasi dipakai seolah hasil seluruh data. Tidak ada pagination untuk perhitungan total, pemeriksaan truncation, atau agregasi seluruh transaksi. Memotong jurnal yang masing-masing seimbang tetap menghasilkan neraca saldo seimbang, sehingga indikator tersebut tidak mendeteksi kehilangan data. Query tanpa urutan eksplisit juga tidak menjamin transaksi tertentu yang akan terlewat.

**Dampak:** laporan berbeda antarhalaman dan salah setelah data tumbuh. Shared aggregation juga digunakan laporan keuangan lain; dampak neraca/tutup buku berskala besar perlu regression tambahan, tidak diklaim sudah seluruhnya dieksekusi di sini. Ini risiko kebenaran hasil, bukan kesimpulan benchmark kecepatan.

**Perbaikan:** hitung total dengan agregasi Mongo pada seluruh matching journal/line, pertahankan scope entitas, tanggal, exclusion void/closing yang sesuai kontrak tiap laporan. Pagination hanya untuk detail. Jangan memperbesar konstanta sebagai solusi. Bandingkan seluruh laporan dengan oracle independen pada batas dan di atas batas; periksa downstream closing yang memakai laba rugi.

## Pendalaman Wave1 — tidak membuat tiket duplikat

### CX-04: dua pencairan uang muka dari satu persetujuan

[cash_advance_service.py:288](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/cash_advance_service.py#L288). Setelah tiga tahap approval, pencairan serial Rp100.000 menghasilkan satu kas, retry serial 409. Tetapi dua caller yang sama-sama membaca `approved` berhasil mencatat dua kas, total Rp200.000. Barrier hanya menahan hasil pembacaan pertama; penulisan kas/jurnal tetap asli. Bukti `W2-CA-E03`. Status check berbasis snapshot tidak menggantikan klaim atomik sebelum efek pertama. Jadikan transaksi/operation key unik sebagai dasar recovery; tidak cukup memindahkan update status tanpa desain pemulihan.

### CX-05: settlement menggunakan nominal awal, tidak mengendalikan residual

[create_settlement:357](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/cash_advance_service.py#L357) menerima parent disbursed maupun settled; [approve_settlement:440](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/cash_advance_service.py#L440) menutup parent tanpa membuktikan residual selesai. Satu pencairan Rp100.000 dapat memiliki dua settlement berbeda Rp100.000, masing-masing punya jurnal. Settlement Rp80.000 menyisakan Rp20.000 tetapi parent sudah settled. Bukti `W2-CA-E01/E02`. Retry ID settlement yang sama ditolak, tetapi ID baru melewati batas bisnis yang seharusnya berlaku pada advance. Aturan single/multi-settlement perlu eksplisit; seluruh expenses, cash return dan reimbursement harus direkonsiliasi kumulatif.

### FN-09: void mengubah periode yang benar-benar sudah ditutup

[gl_service.py:673](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/gl_service.py#L673). Dataset jurnal manual: modal Rp100.000, pendapatan Rp20.000, beban Rp5.000. Saldo kas Rp115.000 dan laba Rp15.000 cocok; entitas B tidak masuk laporan A. Close September mengunci posting dan duplicate close. Reopen men-void jurnal penutup; tambahan pendapatan Rp3.000 lalu close ulang menghasilkan laba Rp18.000. Namun void jurnal pendapatan awal tetap berhasil tanpa unlock: kas turun dari Rp118.000 menjadi Rp98.000, periode tetap closed dan hanya ditandai stale. Bukti `W2-GL-E01`. Stale indicator bukan otorisasi membuka periode. Test ini pada service, bukan validasi seluruh permission router.

## Multi-PO yang sudah terbukti dan batasnya

GRN menampung PO A 10 meter dan PO B 20 meter, produk/task berbeda. Hitung 10+12 tidak mengubah PO sebelum close. Close memposting dua kelompok dengan angka tepat 10 dan 12; roll mempertahankan PO, produk, owner A dan status quarantine. Hanya PO B memiliki task sisa 8. Penerimaan sisa melengkapi PO B menjadi20 tanpa mengubah A. Cancel GRN baru membersihkan roll kedua produk, menghapus active GRN task, mereset counter dan mempertahankan received PO nol. Delapan kontrol lolos. Belum mencakup supplier berbeda, gudang berbeda, race antar-GRN, unit campuran pada multi-PO atau kegagalan tengah commit dua task.

## Koreksi cakupan POS

Trace source: `CheckoutDrawer.jsx:178` memanggil `onSubmitOrder`; `AppViewRouter.jsx:314` meneruskan `submitOrder`; `useAppActions.js:310–349` membentuk payload dan mengirim `/sales-orders` melalui `offlinePost`. Jalur yang diperiksa adalah pemasukan sales order, termasuk termin pembayaran dan backorder. Belum ada bukti lifecycle cashier shift dan split tender pada jalur ini. Karena itu SALE-02 tidak boleh diperlakukan sebagai fitur yang sudah tersedia lalu sekadar belum dites. Catat sebagai **scope fitur perlu dipastikan**, sedangkan cash refund backend di atas adalah flow terpisah. Ini pembacaan source, bukan browser UAT atau bukti ketiadaan fitur di seluruh aplikasi.

## Status kelayakan dan langkah berikutnya

Belum layak sign-off semua flow: W2-020/W2-021 dan temuan lama masih open pada snapshot ini. Kontrol positif mempersempit ketidakpastian, tidak membatalkan temuan kegagalan. [Matriks utama](18_MATRIKS_FLOW_KRITIS.md) tetap memuat celah: seluruh sumber posting/subledger, multi-entitas/intercompany, variasi QC/produksi, recovery, akses/master, modul pendukung, browser dan perangkat RFID. Gunakan [prompt fase perbaikan](20_PROMPT_REFUND_LAPORAN_DAN_PENDALAMAN.md) dan simpan validasi pada commit kandidat terpisah.

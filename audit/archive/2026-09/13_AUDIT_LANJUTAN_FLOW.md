# Audit lanjutan: flow yang sebelumnya belum diuji mendalam

Snapshot `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`; pemeriksaan lanjutan 29 September 2026.

**Belum seluruh kode dan seluruh flow selesai diuji.** Laporan ini menambah 13 temuan pada flow yang diperluas; 12 temuan didukung 13 skenario reproduksi fungsi asli, dan 1 temuan berupa analisis statis interleaving. Satu skenario kontrol menunjukkan validator yang benar. Ini tambahan terhadap validasi65 dalam [08](08_VALIDASI_65_TEMUAN.md), bukan penggantinya dan bukan angka unik seluruh bug sistem.

[Status cakupan](14_STATUS_CAKUPAN_DAN_SISA.md) · [Prompt perbaikan](15_PROMPT_PERBAIKAN_LANJUTAN.md) · [Bukti uji](16_BUKTI_UJI_LANJUTAN.md) · [Register fungsi](17_REGISTER_FUNGSI_BACKEND.md)

Seluruh temuan ini P1: berpotensi merusak nilai, scope, integritas bukti atau penyelesaian bisnis pada kondisi pemicunya. Tidak berarti semua transaksi produksi telah terdampak. Reproduksi memakai data sintetis, model query terbatas dan fungsi asli, bukan server produksi/Mongo/HTTP.

## Daftar temuan

| ID | Temuan | Bukti |
|---|---|---|
| CX-01 | Penebusan store credit dapat melampaui nominal permintaan dan saldo | V3-01 |
| CX-02 | Store credit dapat dialokasikan ke pelanggan atau badan usaha yang berbeda | V3-02; V3-C1 kontrol |
| CX-03 | Gagal posting store credit meninggalkan AR terbayar tetapi kredit belum terpotong | V3-03 |
| CX-04 | Retry pencairan uang muka membuat transaksi kas keluar kedua | V3-04 |
| CX-05 | Uang muka yang telah selesai dapat dipertanggungjawabkan penuh lagi | V3-05 |
| CX-06 | Manual bank matching menerima arah dan rekening yang tidak cocok | V3-06 |
| CX-07 | Split bank reconciliation menghitung target yang sama lebih dari kapasitasnya | V3-07 |
| CX-08 | Reschedule cicilan mengubah arti referensi pembayaran historis | V3-08 |
| CX-09 | Konsolidasi memakai eliminasi di luar entitas yang dilaporkan | V3-09 |
| CX-10 | E-sign tidak terikat pada versi dokumen yang ditampilkan | V3-10; V3-12 |
| CX-11 | Retur dua baris produk yang sama memakai harga baris terakhir | V3-11 |
| CX-12 | Pengiriman pertama menutup special order sebelum pengiriman lain selesai | V3-13 |
| CX-13 | Makloon receive mengunci order tanpa mengikat versi step yang sudah dibaca | Statis L2; belum bukti runtime concurrency |

## CX-01 — Penebusan store credit dapat melampaui nominal permintaan dan saldo

**Prioritas:** P1 · **Bukti:** V3-01

**Letak kode:**

- [backend/services/store_credit_service.py:161 — redeem](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/store_credit_service.py#L161)
- [backend/services/store_credit_service.py:190 — _redeem_locked](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/store_credit_service.py#L190)

**Pemicu/reproduksi:** Pelanggan memiliki saldo 100. Kirim penebusan amount=10 dengan allocations=[SO:150], SO mempunyai piutang 200.

**Kesalahan dan hubungan flow:** redeem menguji amount terhadap balance dan mengunci pelanggan. _redeem_locked memakai nominal setiap alokasi tanpa membatasi jumlahnya terhadap amount; remaining dikurangi tetapi tidak menjadi pagar pada cabang alokasi eksplisit. Kunci pelanggan mencegah sebagian balapan, tetapi tidak memvalidasi konservasi nilai.

**Dampak:** Piutang berkurang 150 dan saldo kredit menjadi -50 walaupun permintaan hanya 10. Laporan pembayaran, saldo titipan, dan jurnal dapat menggambarkan nominal berbeda dari permintaan pengguna.

**Perbaikan yang diperlukan:** Normalisasi seluruh alokasi sebelum mutation. Wajib amount positif, target valid, jumlah alokasi sama dengan amount yang benar-benar ditebus, dan jumlah tersebut tidak melebihi saldo tersedia maupun piutang eligible. Bila partial redemption diperbolehkan, tetapkan applied_amount sebagai nominal kanonik yang sama pada ledger, AR, jurnal dan respons. Gunakan desimal uang serta lindungi saldo di transaksi/claim yang sama.

**Kriteria penerimaan:** Saldo100/request10/alokasi150 harus ditolak tanpa satu pun write; dua alokasi60+60 terhadap100 ditolak; alokasi sah40+60 menghasilkan pengurangan kredit100 dan pembayaran100; nol/negatif/NaN/duplikat target divalidasi.


## CX-02 — Store credit dapat dialokasikan ke pelanggan atau badan usaha yang berbeda

**Prioritas:** P1 · **Bukti:** V3-02; V3-C1 kontrol

**Letak kode:**

- [backend/services/store_credit_service.py:190 — _redeem_locked](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/store_credit_service.py#L190)
- [backend/services/ar_receipt_service.py:273 — _validate_allocation_target](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ar_receipt_service.py#L273)
- [backend/services/ar_receipt_service.py:317 — _apply_to_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ar_receipt_service.py#L317)
- [backend/services/ar_receipt_service.py:245 — list_open_orders](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ar_receipt_service.py#L245)

**Pemicu/reproduksi:** Kredit pelanggan C pada A dipakai untuk SO pelanggan OTHER pada B melalui ID pesanan dalam allocations.

**Kesalahan dan hubungan flow:** Validator bersama sebenarnya menyediakan pemeriksaan customer_id/entity_id. Caller store credit tidak meneruskan kedua argumen tersebut. Validasi entitas sumber pada router tidak menggantikan validasi objek tujuan. Jalur alokasi otomatis juga memanggil daftar order pelanggan tanpa filter entitas.

**Dampak:** Saldo satu pelanggan/badan usaha dapat mengurangi piutang pihak lain. Rekonsiliasi per pelanggan dan intercompany rusak sekalipun nominal grup tampak cocok.

**Perbaikan yang diperlukan:** Jadikan konteks customer dan owner wajib untuk operasi pembayaran, teruskan dari sumber yang sudah diotorisasi dan validasi setiap target sebelum write. Filter kandidat otomatis dengan owner yang sama. Pemindahan kredit lintas PT, jika memang dibutuhkan, harus melalui dokumen intercompany eksplisit, bukan bypass validator.

**Kriteria penerimaan:** C/A ke OTHER/B ditolak; C/A ke C/B ditolak; C/A ke C/A diterima; auto-allocation tidak mengambil SO milik B. Pertahankan positive control validator bersama.


## CX-03 — Gagal posting store credit meninggalkan AR terbayar tetapi kredit belum terpotong

**Prioritas:** P1 · **Bukti:** V3-03

**Letak kode:**

- [backend/services/store_credit_service.py:161 — redeem](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/store_credit_service.py#L161)
- [backend/services/store_credit_service.py:190 — _redeem_locked](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/store_credit_service.py#L190)

**Pemicu/reproduksi:** Injeksi kegagalan posting GL setelah _apply_to_order berhasil untuk50.

**Kesalahan dan hubungan flow:** Pembayaran SO dimutasi sebelum jurnal, ledger kredit dan dokumen redemption. Kegagalan keluar melalui finally yang melepaskan kunci pelanggan; tidak ada keadaan recovery yang menahan percobaan baru atas operasi parsial itu.

**Dampak:** Dalam fixture, AR paid50, saldo kredit masih100, redemption0 dan lock sudah lepas. Retry dapat menggunakan kredit yang sama kembali. Ini satu keluarga akar masalah dengan posting best-effort terdahulu, kini terbukti pada jalur credit redemption.

**Perbaikan yang diperlukan:** Buat redemption operation dengan ID stabil, idempotency key terikat owner+customer+payload, dan tahapan persisten. Mutasi AR, credit ledger dan jurnal harus transactional atau dapat di-resume tepat satu kali. Jangan melepaskan status gagal menjadi seolah belum pernah diproses. Sediakan rekonsiliasi serta reversal terhubung untuk data parsial.

**Kriteria penerimaan:** Fault injection sebelum/sesudah setiap write; retry dengan key sama menghasilkan satu pengurangan saldo, satu pembayaran dan satu posting; key sama payload berbeda ditolak. Proses mati lalu restart dapat melanjutkan tanpa pembayaran ulang.


## CX-04 — Retry pencairan uang muka membuat transaksi kas keluar kedua

**Prioritas:** P1 · **Bukti:** V3-04

**Letak kode:**

- [backend/services/cash_advance_service.py:288 — disburse_cash_advance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cash_advance_service.py#L288)

**Pemicu/reproduksi:** Uang muka approved100 dicairkan. Pembuatan transaksi kas berhasil, GL gagal, lalu pengguna mengulangi pencairan.

**Kesalahan dan hubungan flow:** Cash record dibuat sebelum posting GL dan perubahan status akhir. Pengecekan status awal bukan claim/CAS. Setelah GL gagal, advance tetap dapat dicairkan lagi dengan ID kas baru.

**Dampak:** Dua catatan kas berjumlah200 untuk persetujuan100. Ini membuktikan duplikasi pencatatan internal; audit tidak melakukan ataupun membuktikan transfer bank nyata.

**Perbaikan yang diperlukan:** Gunakan operation identity stabil per pencairan advance, claim status approved dengan versi, link cash record sebelum step berikutnya, dan resume operasi lama ketika retry. Jangan sekadar memindahkan status lebih awal karena itu menciptakan advance disbursed tanpa kas/GL saat crash.

**Kriteria penerimaan:** GL gagal pada percobaan pertama lalu retry: tepat satu cash transaction100; dua request bersamaan tepat satu pencairan; kegagalan setelah GL sebelum status tidak membuat posting kedua; recovery dapat diaudit.


## CX-05 — Uang muka yang telah selesai dapat dipertanggungjawabkan penuh lagi

**Prioritas:** P1 · **Bukti:** V3-05

**Letak kode:**

- [backend/services/cash_advance_service.py:357 — create_settlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cash_advance_service.py#L357)
- [backend/services/cash_advance_service.py:440 — approve_settlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cash_advance_service.py#L440)
- [backend/services/gl_service.py:2565 — post_petty_cash_settlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L2565)

**Pemicu/reproduksi:** Advance100 disbursed; settlement100 disetujui. Buat dan approve settlement kedua100 untuk advance yang sama.

**Kesalahan dan hubungan flow:** Pembuatan settlement menerima status disbursed maupun settled, memakai jumlah awal advance, dan tidak membatasi outstanding yang belum dipertanggungjawabkan. GL idempotent per settlement_id, sehingga dua settlement berbeda tetap masing-masing memposting. Posting asli mendebit beban dan mengkredit Uang Muka sebesar total expense.

**Dampak:** Fixture menerima dua settlement dengan expense200 atas advance100. Secara posting, akun uang muka dapat terkredit berlebihan. Selisih dana juga tidak boleh dianggap sudah selesai hanya karena status parent settled.

**Perbaikan yang diperlukan:** Tentukan apakah satu atau banyak settlement diizinkan. Untuk banyak settlement, simpan dan lindungi residual advance serta hubungan expense/refund/reimbursement, larang settlement tambahan melampaui saldo yang sah. Close advance hanya saat persamaan advance = expenses yang dibiayai + cash return - reimbursement terkait telah direkonsiliasi sesuai kebijakan yang disepakati.

**Kriteria penerimaan:** Advance100 dengan settlement100 berikutnya100 ditolak; partial40+60 valid bila kebijakan mengizinkan; expense80 menyisakan20 hingga cash return; expense120 memerlukan alur reimbursement20, bukan menutup saldo secara diam-diam.


## CX-06 — Manual bank matching menerima arah dan rekening yang tidak cocok

**Prioritas:** P1 · **Bukti:** V3-06

**Letak kode:**

- [backend/services/bank_recon_service.py:691 — manual_match](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_recon_service.py#L691)
- [backend/services/bank_recon_service.py:575 — _link](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_recon_service.py#L575)

**Pemicu/reproduksi:** Baris rekening BANK1 berarah out100 dicocokkan ke cash transaction BANK2 berarah in100 pada owner yang sama.

**Kesalahan dan hubungan flow:** manual_match memeriksa status baris, akses entitas dan ketersediaan nominal, tetapi tidak memeriksa kompatibilitas arah dan rekening sebelum _link. Cabang split memiliki cek arah: kontrak validasi berbeda antar pintu masuk.

**Dampak:** Transaksi yang secara ekonomi berlawanan ditandai matched. Status rekonsiliasi menjadi keyakinan palsu, tanpa berarti saldo GL otomatis berubah oleh match itu sendiri.

**Perbaikan yang diperlukan:** Pusatkan validator bank-line/cash target untuk manual/split/auto/group, meliputi owner, account mapping, currency bila didukung, direction, posted/non-void status dan sisa nominal. Transfer bank harus mencocokkan leg yang benar, bukan memberi pengecualian global.

**Kriteria penerimaan:** OUT vs IN ditolak; BANK1 vs BANK2 ditolak kecuali mapping/leg sah yang eksplisit; transaksi void ditolak; same bank/direction/owner dengan nominal tersedia diterima.


## CX-07 — Split bank reconciliation menghitung target yang sama lebih dari kapasitasnya

**Prioritas:** P1 · **Bukti:** V3-07

**Letak kode:**

- [backend/services/bank_recon_service.py:724 — match_split](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_recon_service.py#L724)
- [backend/services/bank_recon_service.py:575 — _link](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_recon_service.py#L575)

**Pemicu/reproduksi:** Baris bank120; satu cash transaction100; allocations=[T:60,T:60].

**Kesalahan dan hubungan flow:** Validasi setiap elemen membaca available100 sebelum linking. Dua referensi ID sama masing-masing lolos; _link lalu mengakumulasi keduanya menjadi120. Selain duplicate-in-payload, pola read/set reconciled_amount perlu diuji antar request.

**Dampak:** Cash transaction100 mempunyai reconciled_amount120. Matching per baris dan angka tersedia tidak lagi konservatif.

**Perbaikan yang diperlukan:** Tolak atau gabungkan duplicate txn_id sebelum validasi; validasi agregat terhadap remaining capacity. Reservasi/alokasi harus atomik per line dan per cash transaction. Pembatalan match harus mengembalikan kapasitas alokasi yang tepat.

**Kriteria penerimaan:** T60+T60 atas100 ditolak tanpa write; T40+T60 boleh hanya jika dinormalisasi menjadi100; dua baris bersamaan berebut remaining100 tidak dapat mengalokasikan120; unlink dan retry tidak menambah kapasitas palsu.


## CX-08 — Reschedule cicilan mengubah arti referensi pembayaran historis

**Prioritas:** P1 · **Bukti:** V3-08

**Letak kode:**

- [backend/services/payment_plan_service.py:485 — reschedule_line](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/payment_plan_service.py#L485)
- [backend/services/payment_plan_service.py:398 — _receipt_line_targets](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/payment_plan_service.py#L398)
- [backend/services/payment_plan_service.py:426 — recompute_paid](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/payment_plan_service.py#L426)

**Pemicu/reproduksi:** Line1 amount100 paid50; line2 amount100 paid100. Receipt historis menarget seq2. Sisa50 line1 dipindah ke tanggal baru sehingga disisipkan baris baru.

**Kesalahan dan hubungan flow:** reschedule_line menomori ulang seluruh seq, sementara receipt menyimpan plan_line_seq. Line lama2 pindah menjadi3 dan seq2 sekarang menunjuk remainder baru. recompute_paid mengutamakan target seq tersebut lalu waterfall; total paid tetap150, distribusinya berubah.

**Dampak:** Line kedua yang sudah dibayar100 menjadi paid50 pada fixture. Aging, reminder, denda dan status cicilan dapat salah walaupun total piutang tetap cocok.

**Perbaikan yang diperlukan:** Pisahkan immutable plan_line_id dari display sequence. Receipts menunjuk ID/version immutable; reschedule membuat hubungan supersedes/parent_line_id tanpa mengganti identitas historis. Migrasikan referensi lama dengan laporan ambiguity, jangan menebak pembayaran lama hanya dari urutan terbaru.

**Kriteria penerimaan:** Setelah split line1, line2 tetap paid100; pembayaran lama tetap terkait line_id yang sama; reorder/merge/cancel tidak memindahkan pembayaran; total paid tetap150; receipt historis dapat ditelusuri setelah migrasi.


## CX-09 — Konsolidasi memakai eliminasi di luar entitas yang dilaporkan

**Prioritas:** P1 · **Bukti:** V3-09

**Letak kode:**

- [backend/services/consolidation_service.py:107 — summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/consolidation_service.py#L107)
- [backend/services/consolidation_service.py:89 — _applicable_eliminations](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/consolidation_service.py#L89)
- [backend/services/consolidation_service.py:98 — _aggregate_impacts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/consolidation_service.py#L98)

**Pemicu/reproduksi:** Minta laporan hanya entitas A yang assets100/equity100. Ada eliminasi B↔C dengan impact assets-30/liabilities-30.

**Kesalahan dan hubungan flow:** Baris entitas dibatasi entity_ids, tetapi _applicable_eliminations membaca seluruh koleksi dan hanya menyaring tanggal. summary mengagregasi eliminasi tersebut ke subset yang diminta. Sinkronisasi eliminasi otomatis juga dipanggil saat membaca laporan.

**Dampak:** Assets A menjadi70 dan balanced tetaptrue pada fixture. Keseimbangan matematis tidak membuktikan laporan berada pada perimeter konsolidasi yang benar.

**Perbaikan yang diperlukan:** Definisikan perimeter konsolidasi eksplisit. Terapkan eliminasi hanya bila sisi entitas relevan termasuk di dalam perimeter, dengan kebijakan khusus untuk ownership/non-controlling interest jika kelak didukung. Validasi scope, status approval dan effective date; pisahkan sinkronisasi mutation dari pembacaan snapshot laporan.

**Kriteria penerimaan:** A-only tidak mengandung B/C; A+B hanya memakai eliminasi eligible A↔B; eliminasi dengan satu sisi di luar grup tidak dihapus seolah intragroup; historical snapshot tidak berubah karena read berikutnya; balanced dan reconciliation per entity diuji terpisah.


## CX-10 — E-sign tidak terikat pada versi dokumen yang ditampilkan

**Prioritas:** P1 · **Bukti:** V3-10; V3-12

**Letak kode:**

- [backend/services/esign_service.py:106 — verify_and_sign](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/esign_service.py#L106)
- [backend/services/esign_service.py:169 — public_verify](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/esign_service.py#L169)
- [backend/services/pdf_service.py:307 — _attach_esign](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/pdf_service.py#L307)

**Pemicu/reproduksi:** Dokumen memiliki signature signed dan hash versi lama. Isi sumber kemudian berubah; PDF baru dibangun dan kode verifikasi lama dibuka.

**Kesalahan dan hubungan flow:** public_verify mengembalikan valid berdasarkan keberadaan signature signed, bukan kecocokan isi. _attach_esign menempelkan metadata signature lama ke dokumen baru hanya berdasarkan doc_type/source_id. verify_and_sign juga dapat memakai verification_code signature terdahulu tanpa membedakan hash versi.

**Dampak:** Dokumen dengan isi baru dapat tampil bertanda tangan dan membawa halaman valid yang merujuk hash lama. Bukti di sini adalah cacat binding integritas dokumen; bukan penilaian keabsahan hukum tanda tangan.

**Perbaikan yang diperlukan:** Simpan immutable signed artifact atau canonical snapshot/version beserta hash, identitas penanda tangan dan timestamp. QR menunjuk versi tersebut. PDF draft/versi baru tidak membawa signature lama; perubahan menghasilkan unsigned/superseded state dan permintaan tanda tangan baru. Halaman verify harus menjelaskan versi yang diverifikasi.

**Kriteria penerimaan:** Ubah total/item/receiver setelah sign: PDF baru tidak mendapat signature lama; QR lama hanya memverifikasi artifact lama; signature kedua atas versi berbeda tidak dicampur dalam kode/hash lama. Fixture OLD_HASH bersifat sintetis dan belum menghitung hash PDF sebenarnya.


## CX-11 — Retur dua baris produk yang sama memakai harga baris terakhir

**Prioritas:** P1 · **Bukti:** V3-11

**Letak kode:**

- [backend/services/return_service.py:156 — _create_credit_note_and_post_gl](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/return_service.py#L156)

**Pemicu/reproduksi:** SO berisi produk P:10 unit dengan line_total100 dan10 unit dengan line_total200. Kembalikan seluruh20 unit.

**Kesalahan dan hubungan flow:** Harga net disimpan dalam price_by_pid; baris produk yang berulang menimpa harga sebelumnya. Quantity return kemudian dikalikan harga terakhir. Hubungan ke original sales line dan net price asal hilang.

**Dampak:** Credit note net400 untuk penjualan net300. Bila dipakai sebagai saldo kredit atau pengurang AR, over-credit mengalir ke finance. Fixture tanpa pajak/diskon agar kesalahan harga dapat diisolasi.

**Perbaikan yang diperlukan:** Return line harus merujuk original sales/shipment line dan jumlah eligible yang belum diretur. Prorata net, diskon dan pajak dari baris sumber dengan aturan rounding yang konsisten; cumulative refund tidak boleh melebihi nilai returnable setelah penyesuaian sah. Jangan sekadar memakai harga rata-rata jika line-specific return masih diperlukan.

**Kriteria penerimaan:** Full return10@10+10@20 menghasilkan300; partial return dari baris pertama memakai10; beberapa retur bertahap tidak melebihi quantity/nilai awal; uji diskon, tax-inclusive/exclusive dan pembulatan secara terpisah.


## CX-12 — Pengiriman pertama menutup special order sebelum pengiriman lain selesai

**Prioritas:** P1 · **Bukti:** V3-13

**Letak kode:**

- [backend/services/logistics_service.py:494 — transition](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/logistics_service.py#L494)
- [backend/services/special_order_phase2.py:432 — on_delivered](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/special_order_phase2.py#L432)
- [backend/services/special_order_service.py:361 — transition_special_order_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/special_order_service.py#L361)
- [backend/services/logistics_service.py:571 — pickup_handover](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/logistics_service.py#L571)

**Pemicu/reproduksi:** Satu SO mempunyai dua pengiriman. OD sudah shipped karena seluruh task sudah dispatch. D1 diterima, D2 masih in_transit.

**Kesalahan dan hubungan flow:** transition memanggil on_delivered(order_id) saat satu delivery menjadi delivered. Handler hanya memeriksa OD shipped lalu mengubahnya done. CAS pada transition parent sudah ada, tetapi tidak memeriksa kelengkapan seluruh delivery/qty. Pickup mempunyai jalur terpisah tanpa callback yang sama.

**Dampak:** Dalam fixture original handler+transition, OD done sementara delivery lain in_transit. Dashboard/order closure dan tindak lanjut pelanggan dapat menyatakan pekerjaan tuntas terlalu awal. Jalur pickup berpotensi tertinggal dari kebijakan yang sama.

**Perbaikan yang diperlukan:** Buat satu recompute fulfillment berbasis kewajiban kuantitas dan delivery yang sah, menangani partial, failed, cancelled, replacement dan self-pickup. Status shipped/delivered/done mempunyai definisi terpisah yang konsisten. Event delivery dan pickup memanggil kebijakan yang sama; CAS/version pada parent tetap dipertahankan.

**Kriteria penerimaan:** D1 delivered+D2 in_transit tidak done; semua qty accepted baru selesai; failed/cancelled replacement tidak dihitung ganda; pickup akhir juga mengubah parent sesuai kebijakan; replay event tidak menambah pengiriman atau mengubah histori selesai.


## CX-13 — Makloon receive mengunci order tanpa mengikat versi step yang sudah dibaca

**Prioritas:** P1 · **Bukti:** Statis L2; belum bukti runtime concurrency

**Letak kode:**

- [backend/services/makloon_order_service.py:869 — receive_step](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/makloon_order_service.py#L869)

**Pemicu/reproduksi:** Dua request membaca step berstatus issued. Request kedua tertunda sebelum claim. Request pertama menyelesaikan receipt dan melepas kunci; request kedua lalu memperoleh claim dengan snapshot lama.

**Kesalahan dan hubungan flow:** Validasi step terjadi sebelum await-claim. Claim pada order tidak menyertakan precondition status step/version dan hasilnya tidak digunakan untuk mengganti snapshot. Jika input sudah dikonsumsi, material_value memakai fallback nilai step. Tagihan dibuat dengan ID baru, output rolls dibuat lagi, lalu keseluruhan order direplace dari snapshot lama. replace_one menghapus lock dan release sesudahnya juga perlu ownership token agar tidak melepas claim berikutnya.

**Dampak:** Jalur interleaving memungkinkan penerimaan/tagihan/output berulang dan histori receipt pertama tertimpa, meski ada saga lock. Ini analisis statis lintas await, belum simulasi interleaving penuh di Mongo; jumlah duplikasi GL tergantung idempotency helper yang terpisah dan tidak diasumsikan otomatis ganda.

**Perbaikan yang diperlukan:** Claim harus mencakup step issued + expected version dan mengembalikan snapshot yang menjadi dasar perhitungan. Gunakan receiving operation_id unik per step/final GRN, resume child artifacts idempotently, fail bila input consumption0 tanpa receipt operation yang sah. Update field terarah dan token-owned release; hindari whole-document stale replacement.

**Kriteria penerimaan:** Barrier concurrency sebelum claim: request stale ditolak409 atau mengembalikan hasil operation lama, satu konsumsi, satu set output rolls, satu service bill. Crash setelah tiap child write dapat di-resume. Uji final GRN yang menggabungkan partial receipts dan release yang bertabrakan dengan claim baru.


## Akar masalah yang melintasi modul

1. **Validasi sumber tidak menutup validasi target.** Scope pelanggan/entitas pada redemption tidak otomatis berlaku bagi SO target; scope baris laporan tidak otomatis berlaku bagi eliminasi. Buat kontrak target yang wajib, bukan argumen guard opsional pada command keuangan.
2. **Lock harus menjaga invariant, bukan sekadar antrian.** Store credit sudah punya lock tetapi nilai alokasi masih salah. Makloon perlu versi state yang dibaca. Special order punya CAS tetapi predikat selesai tetap salah. Menambahkan lock ke semua fungsi bukan perbaikan yang cukup.
3. **ID operasi, ID baris dan versi dokumen berbeda dari nomor tampilan.** Cicilan memakai seq yang berubah; return memakai product_id yang tidak unik per line; e-sign memakai source_id tanpa versi. Ketiganya kehilangan identitas yang dibutuhkan downstream.
4. **Laporan hijau dapat berasal dari data yang salah.** Bank matched, konsolidasi balanced, e-sign valid dan OD done adalah kesimpulan yang harus dibuktikan dengan invariant, bukan hanya status tersimpan.
5. **Jurnal tidak dapat menyembuhkan subledger sendiri.** GL idempotency per settlement tidak mencegah dua settlement terhadap advance yang sama. GL gagal setelah AR atau kas berhasil memerlukan recovery lintas dokumen.

## Hubungan ke RFID dan WMS

Temuan tambahan memperpanjang rantai audit: RFID read → identitas roll → WMS release → shipment → delivery/POD → closure → retur → credit note → AR/store credit → kas/bank → laporan. Koreksi gate/picking belum cukup jika parent ditutup terlalu dini atau retur dihargai salah. Makloon juga merupakan jalur lahirnya stok dan biaya yang kemudian ditag dan discan; kontrol gate tidak dapat mendeteksi output fiktif yang sudah telanjur diciptakan oleh receipt ganda.

Matriks 41 kapabilitas serta pembanding enterprise tetap ada di [10 — blueprint RFID/WMS](10_BLUEPRINT_RFID_WMS_ENTERPRISE.md). Putaran ini memperluas bukti internal, bukan membuat klaim benchmark vendor baru. Readiness tetap belum dapat diberikan untuk autonomous goods release dan ketepatan finance menyeluruh.

## Kontrol yang benar dan batas temuan

- Shared AR validator menolak target pelanggan salah jika caller memasok konteks: V3-C1. Pertahankan guard tersebut.
- Special-order transition sudah memakai CAS status. CX-12 adalah kekurangan predikat kelengkapan, bukan ketiadaan seluruh kontrol konkurensi.
- E-sign verify sudah mengklaim request pending untuk mencegah penandatanganan request yang sama bersamaan. CX-10 berkaitan dengan versi isi, bukan meniadakan kontrol OTP itu.
- GRN close dan partial-makloon memiliki beberapa pengecekan version/status/duplikasi. CX-13 menunjuk final receive_step; jangan menghapus kontrol jalur partial yang ada.
- Pernyataan pengujian tidak mencakup transfer bank nyata, validitas hukum e-sign, nilai pajak terbaru, UAT antarmuka seluruh modul, atau pembuktian semua interleaving Mongo.

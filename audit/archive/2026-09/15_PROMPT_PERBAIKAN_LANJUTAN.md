# Prompt perbaikan lanjutan untuk agent development

Gunakan setelah membaca [13 — temuan](13_AUDIT_LANJUTAN_FLOW.md). Baseline audit `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. Agent harus memeriksa HEAD yang akan diperbaiki: bila sudah berubah, validasi ulang sebelum mengedit. Setiap blok dapat diberikan terpisah; CX-01–03 sebaiknya satu batch karena satu command.

Urutan: kredit pelanggan → pencairan/settlement → bank matching → harga retur → cicilan/konsolidasi → makloon → delivery → integritas e-sign. Jangan menjalankan migrasi korektif atau reversal terhadap produksi tanpa dry-run yang memperlihatkan dokumen dan nilai perubahan.

## Prompt CX-01 — Penebusan store credit dapat melampaui nominal permintaan dan saldo

```text
Perbaiki CX-01 pada KNHOST. Baca implementasi aktual dan seluruh caller sebelum mengubahnya.

Masalah terverifikasi/hipotesis yang harus divalidasi: redeem menguji amount terhadap balance dan mengunci pelanggan. _redeem_locked memakai nominal setiap alokasi tanpa membatasi jumlahnya terhadap amount; remaining dikurangi tetapi tidak menjadi pagar pada cabang alokasi eksplisit. Kunci pelanggan mencegah sebagian balapan, tetapi tidak memvalidasi konservasi nilai.
Pemicu: Pelanggan memiliki saldo 100. Kirim penebusan amount=10 dengan allocations=[SO:150], SO mempunyai piutang 200.
Bukti audit: V3-01.

Lokasi awal: backend/services/store_credit_service.py::redeem, backend/services/store_credit_service.py::_redeem_locked

Kontrak perbaikan: Normalisasi seluruh alokasi sebelum mutation. Wajib amount positif, target valid, jumlah alokasi sama dengan amount yang benar-benar ditebus, dan jumlah tersebut tidak melebihi saldo tersedia maupun piutang eligible. Bila partial redemption diperbolehkan, tetapkan applied_amount sebagai nominal kanonik yang sama pada ledger, AR, jurnal dan respons. Gunakan desimal uang serta lindungi saldo di transaksi/claim yang sama.

Wajib uji regresi: Saldo100/request10/alokasi150 harus ditolak tanpa satu pun write; dua alokasi60+60 terhadap100 ditolak; alokasi sah40+60 menghasilkan pengurangan kredit100 dan pembayaran100; nol/negatif/NaN/duplikat target divalidasi.

Telusuri router, service, schema, UI caller, database index dan jurnal/subledger downstream. Pertahankan scope/permission/CAS yang sudah benar. Jangan menutup kegagalan dengan except-pass atau hanya menyembunyikan tombol UI. Tambahkan pengujian unit atas invariant dan integration test Mongo untuk transaksi/CAS bila relevan; harness audit memakai dependency model sehingga bukan pengganti integration test.

Untuk data historis: berikan query pendeteksi, jumlah kasus dan rancangan rekonsiliasi; jangan mengasumsikan semua data terdampak atau otomatis menghapus jurnal. Siapkan dry-run migrasi, penanganan ambiguous records, reversal terhubung dan rollback bila diperlukan. Laporkan file yang berubah, skenario sebelum/sesudah, hasil test aktual, risiko migrasi dan bagian yang belum terverifikasi.
```


## Prompt CX-02 — Store credit dapat dialokasikan ke pelanggan atau badan usaha yang berbeda

```text
Perbaiki CX-02 pada KNHOST. Baca implementasi aktual dan seluruh caller sebelum mengubahnya.

Masalah terverifikasi/hipotesis yang harus divalidasi: Validator bersama sebenarnya menyediakan pemeriksaan customer_id/entity_id. Caller store credit tidak meneruskan kedua argumen tersebut. Validasi entitas sumber pada router tidak menggantikan validasi objek tujuan. Jalur alokasi otomatis juga memanggil daftar order pelanggan tanpa filter entitas.
Pemicu: Kredit pelanggan C pada A dipakai untuk SO pelanggan OTHER pada B melalui ID pesanan dalam allocations.
Bukti audit: V3-02; V3-C1 kontrol.

Lokasi awal: backend/services/store_credit_service.py::_redeem_locked, backend/services/ar_receipt_service.py::_validate_allocation_target, backend/services/ar_receipt_service.py::_apply_to_order, backend/services/ar_receipt_service.py::list_open_orders

Kontrak perbaikan: Jadikan konteks customer dan owner wajib untuk operasi pembayaran, teruskan dari sumber yang sudah diotorisasi dan validasi setiap target sebelum write. Filter kandidat otomatis dengan owner yang sama. Pemindahan kredit lintas PT, jika memang dibutuhkan, harus melalui dokumen intercompany eksplisit, bukan bypass validator.

Wajib uji regresi: C/A ke OTHER/B ditolak; C/A ke C/B ditolak; C/A ke C/A diterima; auto-allocation tidak mengambil SO milik B. Pertahankan positive control validator bersama.

Telusuri router, service, schema, UI caller, database index dan jurnal/subledger downstream. Pertahankan scope/permission/CAS yang sudah benar. Jangan menutup kegagalan dengan except-pass atau hanya menyembunyikan tombol UI. Tambahkan pengujian unit atas invariant dan integration test Mongo untuk transaksi/CAS bila relevan; harness audit memakai dependency model sehingga bukan pengganti integration test.

Untuk data historis: berikan query pendeteksi, jumlah kasus dan rancangan rekonsiliasi; jangan mengasumsikan semua data terdampak atau otomatis menghapus jurnal. Siapkan dry-run migrasi, penanganan ambiguous records, reversal terhubung dan rollback bila diperlukan. Laporkan file yang berubah, skenario sebelum/sesudah, hasil test aktual, risiko migrasi dan bagian yang belum terverifikasi.
```


## Prompt CX-03 — Gagal posting store credit meninggalkan AR terbayar tetapi kredit belum terpotong

```text
Perbaiki CX-03 pada KNHOST. Baca implementasi aktual dan seluruh caller sebelum mengubahnya.

Masalah terverifikasi/hipotesis yang harus divalidasi: Pembayaran SO dimutasi sebelum jurnal, ledger kredit dan dokumen redemption. Kegagalan keluar melalui finally yang melepaskan kunci pelanggan; tidak ada keadaan recovery yang menahan percobaan baru atas operasi parsial itu.
Pemicu: Injeksi kegagalan posting GL setelah _apply_to_order berhasil untuk50.
Bukti audit: V3-03.

Lokasi awal: backend/services/store_credit_service.py::redeem, backend/services/store_credit_service.py::_redeem_locked

Kontrak perbaikan: Buat redemption operation dengan ID stabil, idempotency key terikat owner+customer+payload, dan tahapan persisten. Mutasi AR, credit ledger dan jurnal harus transactional atau dapat di-resume tepat satu kali. Jangan melepaskan status gagal menjadi seolah belum pernah diproses. Sediakan rekonsiliasi serta reversal terhubung untuk data parsial.

Wajib uji regresi: Fault injection sebelum/sesudah setiap write; retry dengan key sama menghasilkan satu pengurangan saldo, satu pembayaran dan satu posting; key sama payload berbeda ditolak. Proses mati lalu restart dapat melanjutkan tanpa pembayaran ulang.

Telusuri router, service, schema, UI caller, database index dan jurnal/subledger downstream. Pertahankan scope/permission/CAS yang sudah benar. Jangan menutup kegagalan dengan except-pass atau hanya menyembunyikan tombol UI. Tambahkan pengujian unit atas invariant dan integration test Mongo untuk transaksi/CAS bila relevan; harness audit memakai dependency model sehingga bukan pengganti integration test.

Untuk data historis: berikan query pendeteksi, jumlah kasus dan rancangan rekonsiliasi; jangan mengasumsikan semua data terdampak atau otomatis menghapus jurnal. Siapkan dry-run migrasi, penanganan ambiguous records, reversal terhubung dan rollback bila diperlukan. Laporkan file yang berubah, skenario sebelum/sesudah, hasil test aktual, risiko migrasi dan bagian yang belum terverifikasi.
```


## Prompt CX-04 — Retry pencairan uang muka membuat transaksi kas keluar kedua

```text
Perbaiki CX-04 pada KNHOST. Baca implementasi aktual dan seluruh caller sebelum mengubahnya.

Masalah terverifikasi/hipotesis yang harus divalidasi: Cash record dibuat sebelum posting GL dan perubahan status akhir. Pengecekan status awal bukan claim/CAS. Setelah GL gagal, advance tetap dapat dicairkan lagi dengan ID kas baru.
Pemicu: Uang muka approved100 dicairkan. Pembuatan transaksi kas berhasil, GL gagal, lalu pengguna mengulangi pencairan.
Bukti audit: V3-04.

Lokasi awal: backend/services/cash_advance_service.py::disburse_cash_advance

Kontrak perbaikan: Gunakan operation identity stabil per pencairan advance, claim status approved dengan versi, link cash record sebelum step berikutnya, dan resume operasi lama ketika retry. Jangan sekadar memindahkan status lebih awal karena itu menciptakan advance disbursed tanpa kas/GL saat crash.

Wajib uji regresi: GL gagal pada percobaan pertama lalu retry: tepat satu cash transaction100; dua request bersamaan tepat satu pencairan; kegagalan setelah GL sebelum status tidak membuat posting kedua; recovery dapat diaudit.

Telusuri router, service, schema, UI caller, database index dan jurnal/subledger downstream. Pertahankan scope/permission/CAS yang sudah benar. Jangan menutup kegagalan dengan except-pass atau hanya menyembunyikan tombol UI. Tambahkan pengujian unit atas invariant dan integration test Mongo untuk transaksi/CAS bila relevan; harness audit memakai dependency model sehingga bukan pengganti integration test.

Untuk data historis: berikan query pendeteksi, jumlah kasus dan rancangan rekonsiliasi; jangan mengasumsikan semua data terdampak atau otomatis menghapus jurnal. Siapkan dry-run migrasi, penanganan ambiguous records, reversal terhubung dan rollback bila diperlukan. Laporkan file yang berubah, skenario sebelum/sesudah, hasil test aktual, risiko migrasi dan bagian yang belum terverifikasi.
```


## Prompt CX-05 — Uang muka yang telah selesai dapat dipertanggungjawabkan penuh lagi

```text
Perbaiki CX-05 pada KNHOST. Baca implementasi aktual dan seluruh caller sebelum mengubahnya.

Masalah terverifikasi/hipotesis yang harus divalidasi: Pembuatan settlement menerima status disbursed maupun settled, memakai jumlah awal advance, dan tidak membatasi outstanding yang belum dipertanggungjawabkan. GL idempotent per settlement_id, sehingga dua settlement berbeda tetap masing-masing memposting. Posting asli mendebit beban dan mengkredit Uang Muka sebesar total expense.
Pemicu: Advance100 disbursed; settlement100 disetujui. Buat dan approve settlement kedua100 untuk advance yang sama.
Bukti audit: V3-05.

Lokasi awal: backend/services/cash_advance_service.py::create_settlement, backend/services/cash_advance_service.py::approve_settlement, backend/services/gl_service.py::post_petty_cash_settlement

Kontrak perbaikan: Tentukan apakah satu atau banyak settlement diizinkan. Untuk banyak settlement, simpan dan lindungi residual advance serta hubungan expense/refund/reimbursement, larang settlement tambahan melampaui saldo yang sah. Close advance hanya saat persamaan advance = expenses yang dibiayai + cash return - reimbursement terkait telah direkonsiliasi sesuai kebijakan yang disepakati.

Wajib uji regresi: Advance100 dengan settlement100 berikutnya100 ditolak; partial40+60 valid bila kebijakan mengizinkan; expense80 menyisakan20 hingga cash return; expense120 memerlukan alur reimbursement20, bukan menutup saldo secara diam-diam.

Telusuri router, service, schema, UI caller, database index dan jurnal/subledger downstream. Pertahankan scope/permission/CAS yang sudah benar. Jangan menutup kegagalan dengan except-pass atau hanya menyembunyikan tombol UI. Tambahkan pengujian unit atas invariant dan integration test Mongo untuk transaksi/CAS bila relevan; harness audit memakai dependency model sehingga bukan pengganti integration test.

Untuk data historis: berikan query pendeteksi, jumlah kasus dan rancangan rekonsiliasi; jangan mengasumsikan semua data terdampak atau otomatis menghapus jurnal. Siapkan dry-run migrasi, penanganan ambiguous records, reversal terhubung dan rollback bila diperlukan. Laporkan file yang berubah, skenario sebelum/sesudah, hasil test aktual, risiko migrasi dan bagian yang belum terverifikasi.
```


## Prompt CX-06 — Manual bank matching menerima arah dan rekening yang tidak cocok

```text
Perbaiki CX-06 pada KNHOST. Baca implementasi aktual dan seluruh caller sebelum mengubahnya.

Masalah terverifikasi/hipotesis yang harus divalidasi: manual_match memeriksa status baris, akses entitas dan ketersediaan nominal, tetapi tidak memeriksa kompatibilitas arah dan rekening sebelum _link. Cabang split memiliki cek arah: kontrak validasi berbeda antar pintu masuk.
Pemicu: Baris rekening BANK1 berarah out100 dicocokkan ke cash transaction BANK2 berarah in100 pada owner yang sama.
Bukti audit: V3-06.

Lokasi awal: backend/services/bank_recon_service.py::manual_match, backend/services/bank_recon_service.py::_link

Kontrak perbaikan: Pusatkan validator bank-line/cash target untuk manual/split/auto/group, meliputi owner, account mapping, currency bila didukung, direction, posted/non-void status dan sisa nominal. Transfer bank harus mencocokkan leg yang benar, bukan memberi pengecualian global.

Wajib uji regresi: OUT vs IN ditolak; BANK1 vs BANK2 ditolak kecuali mapping/leg sah yang eksplisit; transaksi void ditolak; same bank/direction/owner dengan nominal tersedia diterima.

Telusuri router, service, schema, UI caller, database index dan jurnal/subledger downstream. Pertahankan scope/permission/CAS yang sudah benar. Jangan menutup kegagalan dengan except-pass atau hanya menyembunyikan tombol UI. Tambahkan pengujian unit atas invariant dan integration test Mongo untuk transaksi/CAS bila relevan; harness audit memakai dependency model sehingga bukan pengganti integration test.

Untuk data historis: berikan query pendeteksi, jumlah kasus dan rancangan rekonsiliasi; jangan mengasumsikan semua data terdampak atau otomatis menghapus jurnal. Siapkan dry-run migrasi, penanganan ambiguous records, reversal terhubung dan rollback bila diperlukan. Laporkan file yang berubah, skenario sebelum/sesudah, hasil test aktual, risiko migrasi dan bagian yang belum terverifikasi.
```


## Prompt CX-07 — Split bank reconciliation menghitung target yang sama lebih dari kapasitasnya

```text
Perbaiki CX-07 pada KNHOST. Baca implementasi aktual dan seluruh caller sebelum mengubahnya.

Masalah terverifikasi/hipotesis yang harus divalidasi: Validasi setiap elemen membaca available100 sebelum linking. Dua referensi ID sama masing-masing lolos; _link lalu mengakumulasi keduanya menjadi120. Selain duplicate-in-payload, pola read/set reconciled_amount perlu diuji antar request.
Pemicu: Baris bank120; satu cash transaction100; allocations=[T:60,T:60].
Bukti audit: V3-07.

Lokasi awal: backend/services/bank_recon_service.py::match_split, backend/services/bank_recon_service.py::_link

Kontrak perbaikan: Tolak atau gabungkan duplicate txn_id sebelum validasi; validasi agregat terhadap remaining capacity. Reservasi/alokasi harus atomik per line dan per cash transaction. Pembatalan match harus mengembalikan kapasitas alokasi yang tepat.

Wajib uji regresi: T60+T60 atas100 ditolak tanpa write; T40+T60 boleh hanya jika dinormalisasi menjadi100; dua baris bersamaan berebut remaining100 tidak dapat mengalokasikan120; unlink dan retry tidak menambah kapasitas palsu.

Telusuri router, service, schema, UI caller, database index dan jurnal/subledger downstream. Pertahankan scope/permission/CAS yang sudah benar. Jangan menutup kegagalan dengan except-pass atau hanya menyembunyikan tombol UI. Tambahkan pengujian unit atas invariant dan integration test Mongo untuk transaksi/CAS bila relevan; harness audit memakai dependency model sehingga bukan pengganti integration test.

Untuk data historis: berikan query pendeteksi, jumlah kasus dan rancangan rekonsiliasi; jangan mengasumsikan semua data terdampak atau otomatis menghapus jurnal. Siapkan dry-run migrasi, penanganan ambiguous records, reversal terhubung dan rollback bila diperlukan. Laporkan file yang berubah, skenario sebelum/sesudah, hasil test aktual, risiko migrasi dan bagian yang belum terverifikasi.
```


## Prompt CX-08 — Reschedule cicilan mengubah arti referensi pembayaran historis

```text
Perbaiki CX-08 pada KNHOST. Baca implementasi aktual dan seluruh caller sebelum mengubahnya.

Masalah terverifikasi/hipotesis yang harus divalidasi: reschedule_line menomori ulang seluruh seq, sementara receipt menyimpan plan_line_seq. Line lama2 pindah menjadi3 dan seq2 sekarang menunjuk remainder baru. recompute_paid mengutamakan target seq tersebut lalu waterfall; total paid tetap150, distribusinya berubah.
Pemicu: Line1 amount100 paid50; line2 amount100 paid100. Receipt historis menarget seq2. Sisa50 line1 dipindah ke tanggal baru sehingga disisipkan baris baru.
Bukti audit: V3-08.

Lokasi awal: backend/services/payment_plan_service.py::reschedule_line, backend/services/payment_plan_service.py::_receipt_line_targets, backend/services/payment_plan_service.py::recompute_paid

Kontrak perbaikan: Pisahkan immutable plan_line_id dari display sequence. Receipts menunjuk ID/version immutable; reschedule membuat hubungan supersedes/parent_line_id tanpa mengganti identitas historis. Migrasikan referensi lama dengan laporan ambiguity, jangan menebak pembayaran lama hanya dari urutan terbaru.

Wajib uji regresi: Setelah split line1, line2 tetap paid100; pembayaran lama tetap terkait line_id yang sama; reorder/merge/cancel tidak memindahkan pembayaran; total paid tetap150; receipt historis dapat ditelusuri setelah migrasi.

Telusuri router, service, schema, UI caller, database index dan jurnal/subledger downstream. Pertahankan scope/permission/CAS yang sudah benar. Jangan menutup kegagalan dengan except-pass atau hanya menyembunyikan tombol UI. Tambahkan pengujian unit atas invariant dan integration test Mongo untuk transaksi/CAS bila relevan; harness audit memakai dependency model sehingga bukan pengganti integration test.

Untuk data historis: berikan query pendeteksi, jumlah kasus dan rancangan rekonsiliasi; jangan mengasumsikan semua data terdampak atau otomatis menghapus jurnal. Siapkan dry-run migrasi, penanganan ambiguous records, reversal terhubung dan rollback bila diperlukan. Laporkan file yang berubah, skenario sebelum/sesudah, hasil test aktual, risiko migrasi dan bagian yang belum terverifikasi.
```


## Prompt CX-09 — Konsolidasi memakai eliminasi di luar entitas yang dilaporkan

```text
Perbaiki CX-09 pada KNHOST. Baca implementasi aktual dan seluruh caller sebelum mengubahnya.

Masalah terverifikasi/hipotesis yang harus divalidasi: Baris entitas dibatasi entity_ids, tetapi _applicable_eliminations membaca seluruh koleksi dan hanya menyaring tanggal. summary mengagregasi eliminasi tersebut ke subset yang diminta. Sinkronisasi eliminasi otomatis juga dipanggil saat membaca laporan.
Pemicu: Minta laporan hanya entitas A yang assets100/equity100. Ada eliminasi B↔C dengan impact assets-30/liabilities-30.
Bukti audit: V3-09.

Lokasi awal: backend/services/consolidation_service.py::summary, backend/services/consolidation_service.py::_applicable_eliminations, backend/services/consolidation_service.py::_aggregate_impacts

Kontrak perbaikan: Definisikan perimeter konsolidasi eksplisit. Terapkan eliminasi hanya bila sisi entitas relevan termasuk di dalam perimeter, dengan kebijakan khusus untuk ownership/non-controlling interest jika kelak didukung. Validasi scope, status approval dan effective date; pisahkan sinkronisasi mutation dari pembacaan snapshot laporan.

Wajib uji regresi: A-only tidak mengandung B/C; A+B hanya memakai eliminasi eligible A↔B; eliminasi dengan satu sisi di luar grup tidak dihapus seolah intragroup; historical snapshot tidak berubah karena read berikutnya; balanced dan reconciliation per entity diuji terpisah.

Telusuri router, service, schema, UI caller, database index dan jurnal/subledger downstream. Pertahankan scope/permission/CAS yang sudah benar. Jangan menutup kegagalan dengan except-pass atau hanya menyembunyikan tombol UI. Tambahkan pengujian unit atas invariant dan integration test Mongo untuk transaksi/CAS bila relevan; harness audit memakai dependency model sehingga bukan pengganti integration test.

Untuk data historis: berikan query pendeteksi, jumlah kasus dan rancangan rekonsiliasi; jangan mengasumsikan semua data terdampak atau otomatis menghapus jurnal. Siapkan dry-run migrasi, penanganan ambiguous records, reversal terhubung dan rollback bila diperlukan. Laporkan file yang berubah, skenario sebelum/sesudah, hasil test aktual, risiko migrasi dan bagian yang belum terverifikasi.
```


## Prompt CX-10 — E-sign tidak terikat pada versi dokumen yang ditampilkan

```text
Perbaiki CX-10 pada KNHOST. Baca implementasi aktual dan seluruh caller sebelum mengubahnya.

Masalah terverifikasi/hipotesis yang harus divalidasi: public_verify mengembalikan valid berdasarkan keberadaan signature signed, bukan kecocokan isi. _attach_esign menempelkan metadata signature lama ke dokumen baru hanya berdasarkan doc_type/source_id. verify_and_sign juga dapat memakai verification_code signature terdahulu tanpa membedakan hash versi.
Pemicu: Dokumen memiliki signature signed dan hash versi lama. Isi sumber kemudian berubah; PDF baru dibangun dan kode verifikasi lama dibuka.
Bukti audit: V3-10; V3-12.

Lokasi awal: backend/services/esign_service.py::verify_and_sign, backend/services/esign_service.py::public_verify, backend/services/pdf_service.py::_attach_esign

Kontrak perbaikan: Simpan immutable signed artifact atau canonical snapshot/version beserta hash, identitas penanda tangan dan timestamp. QR menunjuk versi tersebut. PDF draft/versi baru tidak membawa signature lama; perubahan menghasilkan unsigned/superseded state dan permintaan tanda tangan baru. Halaman verify harus menjelaskan versi yang diverifikasi.

Wajib uji regresi: Ubah total/item/receiver setelah sign: PDF baru tidak mendapat signature lama; QR lama hanya memverifikasi artifact lama; signature kedua atas versi berbeda tidak dicampur dalam kode/hash lama. Fixture OLD_HASH bersifat sintetis dan belum menghitung hash PDF sebenarnya.

Telusuri router, service, schema, UI caller, database index dan jurnal/subledger downstream. Pertahankan scope/permission/CAS yang sudah benar. Jangan menutup kegagalan dengan except-pass atau hanya menyembunyikan tombol UI. Tambahkan pengujian unit atas invariant dan integration test Mongo untuk transaksi/CAS bila relevan; harness audit memakai dependency model sehingga bukan pengganti integration test.

Untuk data historis: berikan query pendeteksi, jumlah kasus dan rancangan rekonsiliasi; jangan mengasumsikan semua data terdampak atau otomatis menghapus jurnal. Siapkan dry-run migrasi, penanganan ambiguous records, reversal terhubung dan rollback bila diperlukan. Laporkan file yang berubah, skenario sebelum/sesudah, hasil test aktual, risiko migrasi dan bagian yang belum terverifikasi.
```


## Prompt CX-11 — Retur dua baris produk yang sama memakai harga baris terakhir

```text
Perbaiki CX-11 pada KNHOST. Baca implementasi aktual dan seluruh caller sebelum mengubahnya.

Masalah terverifikasi/hipotesis yang harus divalidasi: Harga net disimpan dalam price_by_pid; baris produk yang berulang menimpa harga sebelumnya. Quantity return kemudian dikalikan harga terakhir. Hubungan ke original sales line dan net price asal hilang.
Pemicu: SO berisi produk P:10 unit dengan line_total100 dan10 unit dengan line_total200. Kembalikan seluruh20 unit.
Bukti audit: V3-11.

Lokasi awal: backend/services/return_service.py::_create_credit_note_and_post_gl

Kontrak perbaikan: Return line harus merujuk original sales/shipment line dan jumlah eligible yang belum diretur. Prorata net, diskon dan pajak dari baris sumber dengan aturan rounding yang konsisten; cumulative refund tidak boleh melebihi nilai returnable setelah penyesuaian sah. Jangan sekadar memakai harga rata-rata jika line-specific return masih diperlukan.

Wajib uji regresi: Full return10@10+10@20 menghasilkan300; partial return dari baris pertama memakai10; beberapa retur bertahap tidak melebihi quantity/nilai awal; uji diskon, tax-inclusive/exclusive dan pembulatan secara terpisah.

Telusuri router, service, schema, UI caller, database index dan jurnal/subledger downstream. Pertahankan scope/permission/CAS yang sudah benar. Jangan menutup kegagalan dengan except-pass atau hanya menyembunyikan tombol UI. Tambahkan pengujian unit atas invariant dan integration test Mongo untuk transaksi/CAS bila relevan; harness audit memakai dependency model sehingga bukan pengganti integration test.

Untuk data historis: berikan query pendeteksi, jumlah kasus dan rancangan rekonsiliasi; jangan mengasumsikan semua data terdampak atau otomatis menghapus jurnal. Siapkan dry-run migrasi, penanganan ambiguous records, reversal terhubung dan rollback bila diperlukan. Laporkan file yang berubah, skenario sebelum/sesudah, hasil test aktual, risiko migrasi dan bagian yang belum terverifikasi.
```


## Prompt CX-12 — Pengiriman pertama menutup special order sebelum pengiriman lain selesai

```text
Perbaiki CX-12 pada KNHOST. Baca implementasi aktual dan seluruh caller sebelum mengubahnya.

Masalah terverifikasi/hipotesis yang harus divalidasi: transition memanggil on_delivered(order_id) saat satu delivery menjadi delivered. Handler hanya memeriksa OD shipped lalu mengubahnya done. CAS pada transition parent sudah ada, tetapi tidak memeriksa kelengkapan seluruh delivery/qty. Pickup mempunyai jalur terpisah tanpa callback yang sama.
Pemicu: Satu SO mempunyai dua pengiriman. OD sudah shipped karena seluruh task sudah dispatch. D1 diterima, D2 masih in_transit.
Bukti audit: V3-13.

Lokasi awal: backend/services/logistics_service.py::transition, backend/services/special_order_phase2.py::on_delivered, backend/services/special_order_service.py::transition_special_order_status, backend/services/logistics_service.py::pickup_handover

Kontrak perbaikan: Buat satu recompute fulfillment berbasis kewajiban kuantitas dan delivery yang sah, menangani partial, failed, cancelled, replacement dan self-pickup. Status shipped/delivered/done mempunyai definisi terpisah yang konsisten. Event delivery dan pickup memanggil kebijakan yang sama; CAS/version pada parent tetap dipertahankan.

Wajib uji regresi: D1 delivered+D2 in_transit tidak done; semua qty accepted baru selesai; failed/cancelled replacement tidak dihitung ganda; pickup akhir juga mengubah parent sesuai kebijakan; replay event tidak menambah pengiriman atau mengubah histori selesai.

Telusuri router, service, schema, UI caller, database index dan jurnal/subledger downstream. Pertahankan scope/permission/CAS yang sudah benar. Jangan menutup kegagalan dengan except-pass atau hanya menyembunyikan tombol UI. Tambahkan pengujian unit atas invariant dan integration test Mongo untuk transaksi/CAS bila relevan; harness audit memakai dependency model sehingga bukan pengganti integration test.

Untuk data historis: berikan query pendeteksi, jumlah kasus dan rancangan rekonsiliasi; jangan mengasumsikan semua data terdampak atau otomatis menghapus jurnal. Siapkan dry-run migrasi, penanganan ambiguous records, reversal terhubung dan rollback bila diperlukan. Laporkan file yang berubah, skenario sebelum/sesudah, hasil test aktual, risiko migrasi dan bagian yang belum terverifikasi.
```


## Prompt CX-13 — Makloon receive mengunci order tanpa mengikat versi step yang sudah dibaca

```text
Perbaiki CX-13 pada KNHOST. Baca implementasi aktual dan seluruh caller sebelum mengubahnya.

Masalah terverifikasi/hipotesis yang harus divalidasi: Validasi step terjadi sebelum await-claim. Claim pada order tidak menyertakan precondition status step/version dan hasilnya tidak digunakan untuk mengganti snapshot. Jika input sudah dikonsumsi, material_value memakai fallback nilai step. Tagihan dibuat dengan ID baru, output rolls dibuat lagi, lalu keseluruhan order direplace dari snapshot lama. replace_one menghapus lock dan release sesudahnya juga perlu ownership token agar tidak melepas claim berikutnya.
Pemicu: Dua request membaca step berstatus issued. Request kedua tertunda sebelum claim. Request pertama menyelesaikan receipt dan melepas kunci; request kedua lalu memperoleh claim dengan snapshot lama.
Bukti audit: Statis L2; belum bukti runtime concurrency.

Lokasi awal: backend/services/makloon_order_service.py::receive_step

Kontrak perbaikan: Claim harus mencakup step issued + expected version dan mengembalikan snapshot yang menjadi dasar perhitungan. Gunakan receiving operation_id unik per step/final GRN, resume child artifacts idempotently, fail bila input consumption0 tanpa receipt operation yang sah. Update field terarah dan token-owned release; hindari whole-document stale replacement.

Wajib uji regresi: Barrier concurrency sebelum claim: request stale ditolak409 atau mengembalikan hasil operation lama, satu konsumsi, satu set output rolls, satu service bill. Crash setelah tiap child write dapat di-resume. Uji final GRN yang menggabungkan partial receipts dan release yang bertabrakan dengan claim baru.

Telusuri router, service, schema, UI caller, database index dan jurnal/subledger downstream. Pertahankan scope/permission/CAS yang sudah benar. Jangan menutup kegagalan dengan except-pass atau hanya menyembunyikan tombol UI. Tambahkan pengujian unit atas invariant dan integration test Mongo untuk transaksi/CAS bila relevan; harness audit memakai dependency model sehingga bukan pengganti integration test.

Untuk data historis: berikan query pendeteksi, jumlah kasus dan rancangan rekonsiliasi; jangan mengasumsikan semua data terdampak atau otomatis menghapus jurnal. Siapkan dry-run migrasi, penanganan ambiguous records, reversal terhubung dan rollback bila diperlukan. Laporkan file yang berubah, skenario sebelum/sesudah, hasil test aktual, risiko migrasi dan bagian yang belum terverifikasi.
```

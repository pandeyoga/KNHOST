# Gelombang 3 · Fase 01 — Transaksi, recovery, dan konsistensi stok/jurnal

Kerjakan Gelombang 3 dari commit repo saat ini. Baca README, findings-tracker.json, laporan detail, dan source terkait sebelum mengubah kode. Catat actual HEAD; commit audit hanya baseline bukti, bukan asumsi bahwa repo belum berubah. Periksa dulu apakah kasus sudah diperbaiki untuk menghindari patch ganda. Jangan menimpa dokumen Gelombang 1/2 atau mengubah hasil audit historis.

Untuk setiap ID: telusuri input UI → request/schema → permission/entity/lini → service → persist/ledger → projection/report → frontend, termasuk retry, concurrency, pembatalan dan reversal yang relevan. Pertahankan kuantitas fisik, unit, pemilik barang, source document, harga/HPP serta legal entity. Jangan mengubah expected menjadi hasil bug, menyembunyikan warning, atau menyimpulkan fixed hanya dari HTTP 200. Keputusan definisi bisnis yang belum tegas harus dicatat sebagai needs_business_decision.

Setelah implementasi, isi implementation_commit, implementation_evidence, daftar file, perbandingan expected/actual sebelum-sesudah, perintah uji, batas pengujian, dan risiko migrasi. Status agent paling jauh implemented_pending_validation; reviewer independen yang menetapkan verified_fixed setelah seluruh acceptance dan flow terkait lulus. Simpan proof baru terpisah, tanpa menimpa evidence baseline.

Prasyarat: tidak ada. Jumlah ID: 23.

## V3-PROD-01 — Konsumsi bahan dapat berulang setelah movement insert gagal

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/production_service.py#L363). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-PROD-01`.

**Penyebab:** CAS mengurangi roll sebelum journal inventory_movements ditulis. Recovery menghitung konsumsi dari movement; write yang gagal tidak tercatat, sehingga retry mengonsumsi lagi.

**Prompt perbaikan:** Buat operasi konsumsi per material/roll dengan identity stabil dan state durable sebelum efek, lalu lakukan perubahan fisik dan ledger dalam transaksi atau step idempoten yang dapat direkonsiliasi. Jangan menyelesaikan recovery hanya dari movement yang mungkin belum lahir.

**Kriteria validasi:** Fault sebelum/sesudah tiap write, retry key sama/berbeda dan dua worker: stok20→15, output5, movement5 tepat sekali. Recovery harus bekerja melalui endpoint sah; penghapusan lock di probe hanya kontrol pemulihan lokal.

## V3-PROD-02 — Reversal dianggap selesai sebelum panjang roll dipulihkan

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/production_service.py#L389). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-PROD-02`.

**Penyebab:** Movement ditandai reversed sebelum update stok. Kalau update stok gagal, retry mengecualikan movement tersebut dan tidak melakukan restore.

**Prompt perbaikan:** Claim reversal dengan token/stage dan stable operation ID. Commit restore stock dengan marker yang sama secara atomik, atau simpan progress yang membedakan claimed dari applied; retry memeriksa kontribusi aktual.

**Kriteria validasi:** Restore operasi5 selalu menghasilkan roll10, satu reversal movement dan projection10, termasuk fault restore dan dua worker; jangan double-increment saat response hilang.

## V3-AR-01 — Receipt gagal dibuat tetapi SO terbayar dan deposit kembali utuh

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/ar_receipt_service.py#L448). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-AR-01`.

**Penyebab:** Receipt mengurangi deposit, mengalokasikan payments ke SO, baru insert receipt. Except mengembalikan deposit tetapi tidak membatalkan alokasi SO. Tidak ada receipt durable untuk resume.

**Prompt perbaikan:** Persist receipt operation sebelum allocations. Setiap alokasi harus terkait stable receipt ID dan dapat resume/compensate tanpa menghapus payment milik operasi lain. Tangani insert/GL/cash/deposit sebagai satu protokol durable.

**Kriteria validasi:** Fault sebelum receipt insert, setelah SO allocation, sebelum/sesudah GL dan saat rollback. Akhir harus semua effect100 tepat sekali atau semua batal; tidak ada SO paid tanpa receipt/deposit konsumsi. Uji multi-SO dan pembayaran bersamaan.

## V3-BANK-01 — Satu baris bank dapat direkonsiliasi ke dua transaksi kas penuh

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/bank_recon_service.py#L614). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-BANK-01`.

**Penyebab:** CAS membatasi capacity cash transaction, tetapi statement line ditulis berdasarkan ID tanpa claim status/version/capacity yang sama. Dua transaksi berbeda dapat sama-sama mengklaim line bank.

**Prompt perbaikan:** Claim kedua sisi allocation dengan stable match operation dan transaksi/compensation idempoten. Revalidate statement remaining setelah claim; jangan hanya melindungi tiap cash record.

**Kriteria validasi:** Dua matching paralel atas line100: satu sukses dan satu conflict atau total allocated100. Jumlah dari statement links harus sama dengan cash links. Uji split, duplicate payload, unlink/rerun/fault antar-write.

## V3-MKO-01 — Retry penerimaan maklon menambah output fisik dan nilai stok

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/makloon_order_service.py#L1093). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-MKO-01`.

**Penyebab:** Progress lots disimpan sesudah seluruh loop output. Output pertama yang sudah dibuat tidak tersimpan dalam progress jika pembuatan kedua gagal. Retry membuat seluruh roll lagi.

**Prompt perbaikan:** Beri deterministic roll identity per operation+receipt line/index sebelum loop. Persist plan dan state tiap output sebelum/bersama creation; resume harus reconcile actual roll dan movement sebelum membuat lagi. Simpan original warehouse/lot/cost snapshot.

**Kriteria validasi:** Fault pada output1/2/N serta setelah jurnal/status: output total10 dan dua roll saja, inventory value sama GL120. Uji partial multi-gudang, duplicate lot input, response-lost dan authorized saga recovery.

## V3-MASTER-01 — Apply master mengubah produk sebelum snapshot batch durable

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/master_governance_service.py#L96). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-MASTER-01`.

**Penyebab:** Apply mengubah produk dan last_governance_batch lalu insert dokumen batch before/after. Jika insert gagal, perubahan tidak mempunyai snapshot rollback.

**Prompt perbaikan:** Persist batch plan/hash/before snapshots dan stage prepared sebelum produk diubah; pakai CAS version tiap produk dan idempoten operation. Progress parsial harus bisa resume/rollback tanpa menimpa edit sesudahnya.

**Kriteria validasi:** Fault sebelum/antara product update dan batch insert menghasilkan batch recoverable atau tidak ada perubahan. Uji multi-produk, edits concurrent, dry-run signature stale, rollback conflict dan retry identitas sama.

## V3-CUT-01 — Gagal membuat child cut menghilangkan stok dan reservasi

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/roll_service.py#L614). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-CUT-01`.

**Penyebab:** Parent decrement dan pull reservation dilakukan sebelum child insert. Bila insert gagal sebelum write, tidak ada durable cut command yang dapat melanjutkan dan reservation telah hilang.

**Prompt perbaikan:** Persist cut operation dan output identity stabil sebelum mutation; parent/reservation/child/movement/weight/tag lifecycle satu transaksi atau recoverable state machine. Retry mencari cut operation lama, bukan hanya reservation yang sudah dipull.

**Kriteria validasi:** Fault setiap tahap cut100→70+30 selalu conservation quantity/value/weight+documented waste; retry menghasilkan satu child dan satu movement, tag identity baru harus diverifikasi sebelum loading. Tidak boleh menambah kembali parent bila child sudah ada.

## D4-BACKORDER-01 — Pemenuhan stok bersamaan mereservasi 160 untuk SO yang hanya kurang 100

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/backorder_service.py#L82). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-BACKORDER-01`.

**Penyebab:** Roll allocator menjaga stok fisik per roll, tetapi _fill_order tidak mengunci demand/version SO. Dua proses membaca shortage100 yang sama, masing-masing reserve80; $push mempertahankan allocations160 sedangkan $set items/backorders menimpa state dari pembacaan lama80/20.

**Prompt perbaikan:** Claim demand atomik per SO line/version sebelum reserve supply, atau serialisasi operation yang dapat dipulihkan dengan idempotency dan CAS. Kegagalan CAS harus release/compensate allocation yang terlanjur dibuat. Jangan hanya mengganti $set menjadi $inc tanpa demand bound.

**Kriteria validasi:** Dua request80 pada shortage100 tidak pernah menghasilkan reserve total>100; item/allocations/backorder/physical reserved balance sama. Uji dua SKU pada SO sama, auto GR fulfillment vs admin manual, retry, partial failure dan cancel bersamaan.

## D4-CASE-01 — Refund store credit menjurnal pengurangan kewajiban dua kali dan menciptakan pendapatan semu

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L238). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-CASE-01`.

**Penyebab:** act_refund_store_credit memakai adjust yang ditujukan untuk koreksi/hangus saldo. store_credit_service.adjust sudah memposting Dr2-1450/Cr4-9000, lalu _cash_txn kembali memposting Dr2-1450/CrKas. Dua jurnal masing-masing seimbang, tetapi kedua jurnal untuk satu refund mengurangi kewajiban dua kali.

**Prompt perbaikan:** Sediakan operasi pencairan store credit dengan identitas aksi stabil: klaim saldo, buat satu jurnal DrStoreCredit/CrCash, lalu baris ledger menunjuk jurnal yang sama. Hindari memakai adjust/hangus yang menciptakan pendapatan. Pertahankan append-only ledger, legal entity dan referensi kasus. Audit redemption, reversal, return issue, backfill serta semua caller adjust agar GL dan saldo pelanggan tidak terpisah.

**Kriteria validasi:** Saldo100, refund80: cash80, liability-debit80, OtherIncome0, ledger20=GL20. Public response dan dokumen turunannya lengkap. Uji refund dari credit note asli, partial refund, dua klik, saldo tidak cukup, closed period, GL failure, ledger failure, retry dan reversal; tidak boleh ada journal/ledger yatim atau refund kedua.

## D4-CASE-02 — Penyelesaian kasus keuangan dapat mengulang kas yang sudah tercatat setelah konflik atau kegagalan

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L206). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-CASE-02`.

**Penyebab:** finance_case_service.resolve tidak mengklaim action sebelum side effects dan baru menulis status di akhir. _cash_txn selalu membuat UUID baru; idempotensi jurnal per UUID kas tidak melindungi kasus/aksi. Refund mencatat kas sebelum CAS deposit. Pindah buku membuat dua leg berurutan tanpa checkpoint stabil yang dapat dilanjutkan.

**Prompt perbaikan:** Terapkan durable operation identity per case+action/version serta atomic claim dengan precondition lifecycle. Klaim dana sebelum kas; simpan leg/checkpoint dan idempotency keys sebelum side effect. Retry melanjutkan leg yang belum selesai dan mengembalikan hasil committed beserta journal reference yang sudah ada, bukan None. Supplier advance mutation juga harus idempotent dan refund memakai balance CAS. Preflight closed period/account/entity sebelum cash atau balance diposting; failed fund/period claim tidak menulis posted cash. Crash recovery/compensation tidak boleh sekadar melepas lock lalu mengulang semua aksi. Audit seluruh executor playbook karena pola status di akhir dipakai bersama; jangan menganggap executor lain terbukti gagal hanya dari source ini.

**Kriteria validasi:** Normal dan concurrent customer refund tetap satu cash80/JE80/deposit20; loser tidak meninggalkan cash. Supplier advance100/refund80: saldo20, cash-in80; retry penetapan advance tidak menambah saldo kedua kali dan saldo=GL100. Semua fault boundary cash insert, JE, balance, case-status dan doc-link diuji. Own-bank transfer80 setelah failure/retry harus out80/in80/transit0. Periode terkunci menolak sebelum cash/balance mutation; unlock sah berjalan normal. Dua request satu case dan dua case berbeda atas dana sama tidak overspend. Dokumen resolusi merujuk seluruh committed legs, reversal append-only, recovery tetap dapat berjalan setelah restart.

## D4-INTERCO-01 — Transfer roll retur dapat selesai memindahkan pemilik tetapi kehilangan jurnal pasangan dan dokumen pemulihan

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L1333). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-INTERCO-01`.

**Penyebab:** return_service.transfer_return_roll_ownership memindahkan owner, lot, RFID owner, movements dan balances sebelum post_intercompany_transfer. Failure rollback mencari reserved_ref yang sudah dibersihkan oleh transfer sehingga owner tidak kembali. warehouse_transfers baru ditulis sesudah kedua JE. Helper GL memakai OR guard: ada salah satu sisi dianggap sudah selesai, tanpa mengisi sisi lain.

**Prompt perbaikan:** Persist intent transfer dengan operation ID dan cost snapshot sebelum pemindahan. Checkpoint owner/lot/tag/movements/GL tiap sisi; retry harus menyelesaikan missing leg secara idempotent. already_posted harus memeriksa pasangan lengkap dan nilai/ref yang sama, bukan OR existence. Gunakan compensation yang sadar state bila dipilih rollback. Terapkan perbaikan helper shared juga pada transfers.approve dan recovery sesudah crash tanpa memindahkan roll dua kali.

**Kriteria validasi:** Fault destination JE, pair-link, transfer-doc insert, return-history write dan balances: hasil dapat dipulihkan sampai owner/lot/tag/ledger kedua PT/history konsisten, atau rollback penuh yang auditable. Satu source JE tidak dianggap selesai. Retry original API harus recover atau menunjukkan operation pending yang dapat dilanjutkan; concurrent request tidak membuat extra movements/JE. Kontrol internal-purchase return tetap menuju Retur Antar-PT.

## D4-INTERCO-02 — Nilai transfer antarentitas memakai WAC sesudah stok sumber dipindahkan

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L1337). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-INTERCO-02`.

**Penyebab:** _transfer_items_value_at_cost mengambil WAC live entitas sumber. Kedua caller shared menjalankan ownership transfer sebelum memposting helper. Roll yang menjadi objek transfer sudah dikeluarkan dari query source WAC: cost yang dipakai berasal dari sisa barang lain atau fallback master lama. Tidak ada snapshot biaya sebelum perpindahan.

**Prompt perbaikan:** Tentukan dan simpan immutable valuation sebelum owner/status berubah, dengan quantity/UOM, per-line/per-roll cost dan legal entity source. Pilih kebijakan WAC atau actual roll-cost secara eksplisit dan jaga rekonsiliasi GL terhadap SSOT roll cost; jangan recompute retry dari live remaining source atau cache/fallback. Helper GL mengonsumsi snapshot tervalidasi dan kedua sisi memakai total sama. Audit transfers.approve, return transfer, destination revaluation serta konsolidasi.

**Kriteria validasi:** Satu roll10×15 dengan stale master1 menghasilkan JE150, ownerB dan subledger150. Sumber campuran5/15 mengikuti policy yang terdokumentasi dan kedua entitas tetap rekonsiliasi. Uji source menjadi kosong, source tetap berisi roll biaya berbeda, landed cost, conversion yard/meter, zero-cost nyata versus missing-cost, concurrent cost update, partial transfer, failure/retry tanpa revaluasi ulang.

## D4-CASE-03 — Alur dana dipegang karyawan tidak menjaga urutan langkah dan sisa piutang

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/finance_case_actions.py#L310). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-CASE-03`.

**Penyebab:** Service memvalidasi action terdaftar pada playbook, tetapi tidak memvalidasi state/step/next_action atau remaining acknowledged receivable. act_setor_dari_karyawan tidak menuntut bukti step1 berhasil, tidak membatasi amount terhadap sisa piutang, dan tidak mengembalikan hold untuk partial settlement. resolve menutup semua aksi yang tidak memberi hold.

**Prompt perbaikan:** Tentukan state machine per playbook di backend dengan permitted action, prerequisites, operation version dan remaining amount yang diturunkan dari acknowledged/settled legs. Setoran harus menunjuk acknowledgment/employee yang sah, menjaga legal entity dan source debt. Partial settlement tetap in_progress dengan remaining dan next_action, atau ditolak sebelum efek bila policy tidak membolehkannya. Excess memerlukan keputusan eksplisit dengan akun/ledger surplus yang tepat; jangan mengkredit piutang lebih besar dari yang ada. UI menampilkan step yang sah tetapi server tetap menjadi gate.

**Kriteria validasi:** Step2 sebelum acknowledgment ditolak tanpa cash/JE. Holding80→deposit80: debt0 dan resolved. Holding80→deposit40: remaining40, case pending dan dapat menerima40 berikutnya. Deposit100 tidak membuat employee receivable negatif; surplus20 diproses sesuai keputusan terdokumentasi atau request ditolak tanpa side effect. Uji wrong employee/entity/source, repeated step1, multiple partial settlements, concurrent settlements, rejection/reopen, reversal dan restart recovery; kriteria CASE-02 juga harus terpenuhi.

## D4-CLOSE-01 — Reopen bulan tidak menandai penutupan tahun yang bergantung padanya sebagai basi

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L346). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-CLOSE-01`.

**Penyebab:** reopen_period menganulir jurnal bulan dan memperbarui record bulan, tetapi tidak menginvalidasi penutupan aktif yang mencakupnya. reclose_period memiliki propagasi stale ke parent; reopen tidak. UI menyediakan Tutup Ulang hanya bila closed dan stale, sehingga penutupan tahun tetap tampil final tanpa akses normal ke aksi pemulihannya.

**Prompt perbaikan:** Definisikan dependency/invalidation graph penutupan bulanan/tahunan dan terapkan pada reopen, reclose, unlock corrections serta void. Setelah journal penutup anak berubah, parent harus stale/pending dengan alasan dan residual yang dapat direkonsiliasi, atau reopen ditolak sebelum efek bila policy mewajibkan urutan parent dahulu. Tampilkan tindakan pemulihan sesuai status; jangan menandai final hanya karena record closed masih ada.

**Kriteria validasi:** Close bulan100 lalu tahun residual0 → reopen bulan: parent tahun diberi stale dan tersedia reclose, atau aksi ditolak tanpa void sebelum parent ditangani. Setelah pemulihan, residual100 tertutup satu kali; P&L operasional100 tetap100 dan total equity tetap rekonsiliasi. Uji tahun buku non-Desember, beberapa bulan, parent residual bukan0, reopen/reclose berulang, concurrency, entity dan fault checkpoints.

## D4-CLOSE-02 — Tutup ulang gagal mengadopsi jurnal yang sudah tersimpan sehingga recovery admin tetap gagal

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/closing_service.py#L371). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-CLOSE-02`.

**Penyebab:** reclose_period menganulir jurnal lama, membuat jurnal baru dengan source_id closing yang sama, lalu baru memperbarui snapshot dan link parent. Tidak ada checkpoint/adopsi jurnal aktif yang sudah dibuat bila acknowledgment atau parent update gagal. Retry menggunakan parent journal_entry_id lama yang sudah void lalu mencoba insert ulang, bertabrakan dengan unique active source index. Kunci saga memang terlihat dan memblokir replay, tetapi pelepasan yang sah tidak menyediakan resumable recovery.

**Prompt perbaikan:** Persist reclose operation/version dan checkpoint intent, old/new journal IDs serta frozen totals sebelum efek. Retry harus mengadopsi JE yang cocok dengan operation/version dan memfinalisasi parent, bukan menganggap unique-index error sebagai sukses atau membuat jurnal baru. Rancang atomic switch/compensation agar status/link/snapshot konsisten, tandai failure yang dapat diperiksa, dan recovery admin menyelesaikan/membatalkan operation secara sadar efek. Pertahankan unique index, fencing dan guard periode; audit close/reopen/unlock auto-close serta concurrent yearly/monthly operations.

**Kriteria validasi:** Lost acknowledgment sesudah JE insert dan kegagalan parent update dapat direcover lewat fitur asli: tepat satu active JE130, parent menunjuknya/net130/staleFalse, lock selesai dan histori jelas. Fault sebelum insert tidak membuang journal lama tanpa recovery; retry setelah restart tidak menciptakan extraJE. Uji reopen bersamaan, akun nonaktif, partial unlock, fiscal year, parent invalidation dan laporan/print yang mengikuti snapshot final.

## D4-GL-01 — Jurnal manual yang sudah dibalik masih dapat dianulir dan membentuk pembatalan dua kali

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L755). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-GL-01`.

**Penyebab:** void_entry memeriksa status non-void dan sumber manual, tetapi mengabaikan reversed_by_entry_id termasuk pending reversal. Filter CAS void juga hanya status non-void. Frontend tetap menampilkan Anulir Jurnal untuk manual/posted walaupun sudah reversed. Membalik dan menganulir asal dapat terjadi berurutan atau beradu tanpa mutually exclusive cancellation state.

**Prompt perbaikan:** Tentukan satu state machine cancellation: void dan reverse saling eksklusif secara atomik, termasuk reversal pending. Tolak void atas jurnal reversed sebelum efek; bila business policy mengizinkan koreksi pasangan, gunakan aksi terpisah yang memproses pasangan/link/period secara auditable, bukan void asal saja. UI menyembunyikan/menjelaskan aksi tidak sah tetapi backend gate wajib. Review source reversal, backfill dan laporan agar pembalik tetap teridentifikasi.

**Kriteria validasi:** Manual100 → reverse: net0; void asal sesudahnya ditolak4xx tanpa mengubah jurnal/PL. Manual100 → void: net0; reverse asal ditolak. Dua request reverse/void bersamaan hanya satu cancellation menang, tidak pernah menyisakan pembalik tunggal. Uji pending/failed reversal, retry, closed period, partial fault dan drilldown/print/link jurnal.

## D4-GL-02 — Jurnal manual meloloskan NaN/Infinity dan menghilangkan angka transaksi sah dari laporan

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L640). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-GL-02`.

**Penyebab:** Validator pusat _validate_entry_lines memakai math.isfinite, tetapi create_manual_entry menyisipkan langsung ke journal_entries tanpa melewatinya. Perbandingan negatif/zero/difference terhadap NaN tidak menolak; Infinity-Infinity juga NaN. Schema JournalLineIn menerima coercion string ke float. Response sanitizer mengubah angka tidak finite menjadi null, tanpa membatalkan penulisan.

**Prompt perbaikan:** Gunakan validator pusat yang sama untuk seluruh manual/autopost/import producers sebelum side effect, dengan field finite di schema dan validasi aggregate balance sesudah normalisasi. Tolak NaN/Infinity dari angka maupun string4xx sebelum insert atau perubahan counters material. Jangan mengubah invalid values menjadi0 sebagai perbaikan. Audit data existing dengan penandaan dan koreksi/reversal yang disetujui; laporan harus menampilkan masalah integritas, bukan silently menghapus akun sah.

**Kriteria validasi:** NaN/±Infinity pada setiap field debit/credit dan total tidak tersimpan;4xx dengan detail jelas, jurnal/GL tidak berubah. Fixture expense50 tetap summarydebit50 dan PLexpense50 setelah invalid request. Uji numeric strings, overflow1e309, rounding, huge/negative/zero values, import/manual/autopost, legacy damaged-record quarantine dan safe display tanpa menyatakan balanced jika data rusak.

## D4-PA-02 — Putaway kehilangan checkpoint setelah roll berpindah sehingga recovery stok dan tag gagal

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/putaway_order_service.py#L232). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-PA-02`.

**Penyebab:** _land_items memindahkan roll dan menghapus active_movement sebelum tag, mutasi, saldo dan parent difinalisasi. Retry menuntut warehouse asal dan active_movement yang sudah dihapus; tidak ada checkpoint/adopsi efek operation yang sama. Inspector saga tidak memeriksa perubahan existing roll atau PA reference secara memadai.

**Prompt perbaikan:** Persist operation/version dan checkpoint landed/tagged/audit-posted/balance-rebuilt/parent-finalized per item. Pertahankan token/provenance transisi agar retry mengadopsi efek sah dan melengkapi langkah tersisa. Mutasi out/in memakai unique operation+roll+leg. Inspector admin mencakup roll update, PA number/reference, tag dan invalidation saldo; pelepasan lock bukan penyelesaian efek. Jangan menerima semua roll di tujuan tanpa provenance atau memakai manual edit Mongo sebagai recovery.

**Kriteria validasi:** Fault setiap batas roll/tag/mutasi/saldo/parent pulih lewat fitur asli: satu BTG, dua mutasi per roll, parent completed, tag+roll tujuan, asal0/tujuan10 dan owned10. Uji multiroll partial, lost acknowledgment/restart, concurrent/fenced recovery, exception accept/return, stock/ATP/lot. Kontrol normal tetap lulus.

## D4-RFID-01 — Deduplikasi event RFID melewati recovery keputusan, insiden dan status passage

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/rfid_ingest_service.py#L138). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-RFID-01`.

**Penyebab:** Observation event_id durable dianggap processed untuk seluruh pipeline tanpa checkpoint read/stamp/incident/passage. Retry event sama dibuang; event baru dapat melewati efek yang belum selesai melalui dwell atau menjadi REPLAY_EXIT akibat stamp yang lebih dahulu durable. Ini berbeda dari cache keputusan basi V3-RFID-01.

**Prompt perbaikan:** Gunakan observation sebagai durable inbox dengan processing state/checkpoint. Per event/decision operation punya read/movement/incident IDs dan passage delta deterministik. Retry melengkapi efek dengan idempotent writes; dwell tidak melewati unfinished operation. Selaraskan exit stamp/read commit melalui transaction/outbox atau resumable sequence dengan provenance. Passage/latch mempertahankan keputusan red durable dan menjelaskan processing/unavailable bila belum final. Pertahankan no-stock-mutation, auth/EPC dan event guards.

**Kriteria validasi:** Fault tiap batas observation/stamp/read/incident/passage pulih dari event sama tanpa kehilangan/duplikasi. Green belum final tidak menjadi false replay hanya karena recovery. Red durable menghasilkan satu incident dan red/latched, bukan info. Uji multi-EPC/mixed batch, dwell/new event, restart/reconnect, duplicate/concurrent events, movement change dan acknowledge. Uji perangkat fisik tetap terpisah.

## D4-CC-01 — Recovery cycle count membuat dua laporan dan nomor untuk satu sesi

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/cycle_count_service.py#L124). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-CC-01`.

**Penyebab:** complete membuat UUID/nomor baru tiap eksekusi, insert result kemudian finalize session/link. Retry tidak mengadopsi existing result; startup indexes tidak menjamin satu result/session. Inspector tidak mencari rfid_cycle_counts.session_id.

**Prompt perbaikan:** Persist result ID/nomor operation/session sebelum efek, adopt result cocok saat retry dan finalize parent recoverably. Unique session+revision mengikuti policy recount; recount harus revision/session baru eksplisit. Inspector menampilkan CC durable dan langkah recovery. Rekonsiliasikan data existing secara auditable, jangan menghapus histori sembarangan.

**Kriteria validasi:** Lost acknowledgment atau failed parent update: satu result/nomor dan session completed yang menunjuknya. Uji restart/concurrency/stale lock, recount revision, entity scope, simulated/manual/device evidence dan health/history/export. Stock tidak dimutasi oleh laporan count.

## D4-ASSET-01 — Penyusutan yang gagal mengunci periode sehingga retry tidak memperbaiki aset

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_service_fault_or_concurrency_counterexample`.

**Layar/alur:** Keuangan → Aset Tetap → jalankan penyusutan.

**Rantai kejadian:** Klaim periode → posting jurnal gagal → klaim tertinggal → retry skip → akumulasi/entri tetap0.

**Letak kesalahan dan penyebab:** Periode dimasukkan ke depreciation_periods sebelum jurnal dan register penyusutan selesai. Kegagalan tidak melepas klaim atau menyediakan status saga yang dapat dilanjutkan.

**Dampak, hasil reproduksi, dan batas klaim:** Fault satu kali hanya pada batas post_depreciation: public run500. Setelah batas normal dipulihkan, public retry200 tetapi posted0, accumulated0 dan tidak ada entri untuk periode itu. Kontrol proses normal memposting100 dan retry periode yang sudah selesai tidak menggandakan jurnal.

**Lokasi source pada commit audit:**

- [backend/services/fixed_asset_service.py:244](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L244) — `"depreciation_periods": {"$ne": period}`.
- [backend/services/fixed_asset_service.py:256](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L256) — `je = await gl_service.post_depreciation(`.
- [backend/services/gl_service.py:2286](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/gl_service.py#L2286) — `async def post_depreciation(`.

```python
242:         won = await db.fin_fixed_assets.find_one_and_update(
243:             {"id": a["id"], "status": a.get("status", "active"),
244:              "depreciation_periods": {"$ne": period}},
245:             {"$addToSet": {"depreciation_periods": period}},
246:             projection={"_id": 0, "id": 1})
247:         if not won:
248:             skipped += 1
249:             continue
250:         monthly = _monthly_amount(cost, salvage, life)
```

**Bukti asli:** [evidence/repro/assets-loans-lifecycle90-results.json](evidence/repro/assets-loans-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| FA90-failure-retry-posted | 1 | 0 | observed_difference |
| FA90-failure-retry-accumulated | 100 | 0.0 | observed_difference |
| FA90-failure-retry-entry-count | 1 | 0 | observed_difference |
| FA90-parallel-months-accumulated | 200 | 100.0 | observed_difference |
| FA90-parallel-months-book-value | 100 | 200.0 | observed_difference |
| FA90-parallel-months-count | 2 | 1 | observed_difference |
| ICL90-foreign-repayment-denied | 403 | 200 | observed_difference |
| ICL90-foreign-repayment-outstanding | 50 | 40.0 | observed_difference |
| ICL90-foreign-repayment-no-cash | 0 | 2 | observed_difference |
| ICL90-foreign-cancellation-denied | 403 | 200 | observed_difference |

**Prompt agent development:**

Buat operasi penyusutan dapat dipulihkan: preflight, operation ID per aset/periode, status started/GL posted/register applied/completed, dan resume yang idempoten. Jangan melepas klaim secara buta setelah jurnal mungkin terbentuk; bedakan kegagalan sebelum dan sesudah side effect.

**Kriteria penerimaan untuk reviewer:**

Fault sebelum posting, sesudah journal tersimpan, sebelum register, sebelum finalize: retry menghasilkan tepat1 jurnal+1 entri dan akumulasi100. Uji restart/timeout, periode tertutup, akun invalid, single-asset dan batch, duplicate same-period concurrency.

## D4-ASSET-02 — Penyusutan dua periode bersamaan membuat register aset tertinggal dari jurnal

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_service_fault_or_concurrency_counterexample`.

**Layar/alur:** Keuangan → Aset Tetap → register, nilai buku dan penyusutan.

**Rantai kejadian:** Dua periode membaca acc0 → keduanya klaim periode berbeda → dua entri100 → keduanya set acc100.

**Letak kesalahan dan penyebab:** CAS hanya melindungi period key masing-masing. Perhitungan akumulasi dan bulan memakai snapshot yang dibaca sebelum klaim, lalu disimpan dengan $set, sehingga update lintas periode dapat saling menimpa.

**Dampak, hasil reproduksi, dan batas klaim:** Aset300/life3: dua public run periode Jan dan Feb dengan barrier di batas jurnal menghasilkan2 entri penyusutan. Register menunjukkan accumulated100/book200/months1, seharusnya accumulated200/book100/months2. Kontrol run normal dan duplicate same-period tetap benar. Barrier menyinkronkan urutan; perhitungan asli tidak diganti.

**Lokasi source pada commit audit:**

- [backend/services/fixed_asset_service.py:261](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L261) — `new_acc = round(acc + amt, 2)`.
- [backend/services/fixed_asset_service.py:262](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L262) — `new_months = int(a.get("depreciated_months", 0)) + 1`.
- [backend/services/fixed_asset_service.py:274](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/fixed_asset_service.py#L274) — `"accumulated_depreciation": new_acc`.

```python
259:             dep_exp_acc=a.get("gl_account_dep_exp", gl_service.ACC_DEP_EXPENSE),
260:             acc_dep_acc=a.get("gl_account_acc_dep", gl_service.ACC_FA_ACCUM_DEP))
261:         new_acc = round(acc + amt, 2)
262:         new_months = int(a.get("depreciated_months", 0)) + 1
263:         new_book = round(cost - new_acc, 2)
264:         status = "fully_depreciated" if (new_acc >= depreciable - EPS or new_months >= life) else "active"
265:         await db.fin_depreciation_entries.insert_one({
266:             "id": new_id("depe"),
267:             "asset_id": a["id"], "asset_number": a.get("number", ""),
```

**Bukti asli:** [evidence/repro/assets-loans-lifecycle90-results.json](evidence/repro/assets-loans-lifecycle90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| FA90-failure-retry-posted | 1 | 0 | observed_difference |
| FA90-failure-retry-accumulated | 100 | 0.0 | observed_difference |
| FA90-failure-retry-entry-count | 1 | 0 | observed_difference |
| FA90-parallel-months-accumulated | 200 | 100.0 | observed_difference |
| FA90-parallel-months-book-value | 100 | 200.0 | observed_difference |
| FA90-parallel-months-count | 2 | 1 | observed_difference |
| ICL90-foreign-repayment-denied | 403 | 200 | observed_difference |
| ICL90-foreign-repayment-outstanding | 50 | 40.0 | observed_difference |
| ICL90-foreign-repayment-no-cash | 0 | 2 | observed_difference |
| ICL90-foreign-cancellation-denied | 403 | 200 | observed_difference |

**Prompt agent development:**

Serialisasikan mutasi per aset atau gunakan update atomik/optimistic version dengan resume idempoten per periode. Hindari snapshot stale; batas depreciable amount/salvage/life harus berlaku terhadap akumulasi final setelah semua operasi, termasuk disposal/capitalization.

**Kriteria penerimaan untuk reviewer:**

Jan/Feb concurrent:2 entri, akumulasi200, nilai buku100 dan2 bulan; GL-register-detail-summary harus merekonsiliasi. Uji last-month concurrent, salvage, disposal vs depreciation, amendment vs run, same-period retries dan interrupted batch.

## D4-OD-LOCK-01 — Kegagalan pembaruan SKU meninggalkan harga OD terkunci dan pengulangan tidak dapat memulihkannya

**Prioritas:** P1 · **Status:** open · **Jenis bukti:** `original_service_fault_or_concurrency_counterexample`.

**Layar/alur:** Pesanan Khusus → keputusan pelanggan → kunci harga final → katalog SKU.

**Rantai kejadian:** Customer ACC → lockprice commitOD130 → DBwrite SKU gagal → SKU100 → retry sudahterkunci.

**Letak kesalahan dan penyebab:** Harga OD dan akhir claim dicatat sebelum pembaruan produk. Kegagalan di write produk tidak ditangani dengan resume/rollback; pengecekan awal locked menolak retry.

**Dampak, hasil reproduksi, dan batas klaim:** Fault hanya di boundary database products.update_one, bisnis asli tidak diganti. PersistedOD price_locked=True/final130, SKUprice100; retry gagal already-locked. Kontrol normal lock menghasilkanOD1300/SKU130, dan unlock memerlukanadmin+reason serta menolak bila PR/PO/SO sudah lahir. Pemulihan manual lewat unlock dapat diperlukan; bukan klaim tidak mungkin dipulihkan sama sekali.

**Lokasi source pada commit audit:**

- [backend/services/special_order_phase2.py:235](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/special_order_phase2.py#L235) — `_saga.finish_set({"pricing": pricing`.
- [backend/services/special_order_phase2.py:244](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/special_order_phase2.py#L244) — `await db.products.update_one({"id": pid_final}`.
- [backend/services/special_order_phase2.py:216](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/special_order_phase2.py#L216) — `Harga OD ini sudah dikunci.`.

```python
233:                       precondition={"price_locked": {"$ne": True}}, actor=actor.get("name", ""))
234:     _res = await db.special_orders.update_one({"id": od["id"], "price_locked": {"$ne": True}}, {
235:         **_saga.finish_set({"pricing": pricing, "final_price": pricing["final_unit_price"], "total_amount": pricing["total"],
236:                  "price_locked": True, "updated_at": now_iso(),
237:                  **({"linked_product_id": pv["product_id"], "linked_product_sku": pv["product_sku"]} if pv["product_id"] else {})}),
238:         "$push": {"status_history": {"status": od.get("status"), "timestamp": now_iso(), "user": actor.get("email", ""),
239:                                      "note": f"Harga final dikunci: {rupiah(pricing['final_unit_price'])}/{pricing['unit']} (kontrak {rupiah(pricing['cost_price'])} + margin {pricing['margin_pct']:g}%)"}}})
240:     if _res.matched_count == 0:
241:         raise ODError("Harga OD ini baru saja dikunci oleh pihak lain. Muat ulang.")
```

**Bukti asli:** [evidence/repro/special-order-chain90-results.json](evidence/repro/special-order-chain90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| od.latest_revision_blocks_old_winner | false | false | pass |
| od.decision_guard_locked | true | true | pass |
| od.lock_needs_acc | true | true | pass |
| od.lock_needs_winning_contract | true | true | pass |
| od.lock_total | 1300 | 1300.0 | pass |
| od.lock_sku_price | 130 | 130.0 | pass |
| od.lock_repeat_guard | true | true | pass |
| od.locked_preview_snapshot | 1300 | 1300.0 | pass |
| od.unlock_requires_admin | true | true | pass |
| od.unlock_requires_reason | true | true | pass |

**Prompt agent development:**

Gunakan saga/checkpoint yang selesai hanya setelah semua effect harga/SKU tersimpan, atau transaksi dengan recovery yang jelas. Retry harus mengenali partial commit dan menyelesaikannya sekali tanpa duplicateprocurement. Jangan mengubah snapshot dokumen historis melalui repairmassal.

**Kriteria penerimaan untuk reviewer:**

Fault sebelum/sesudah OD commit, SKUwrite dan autoPO: state konsisten atau pending dan dapat dipulihkan. Retry tidak ditolak ketika pekerjaan belum selesai; harga akhir OD/SKU/PR/PO konsisten, idempotent dan SOD/lock rules tetap berlaku.


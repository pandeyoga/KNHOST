# Prompt perbaikan tervalidasi untuk AI agent developer

Gunakan dokumen ini bersama 08/09/10. Ini menggantikan interpretasi prompt awal pada bagian yang dikoreksi, terutama FN-14, RF-13, RF-17, GN-14 dan FN-11. ID audit tetap dipertahankan agar tidak kehilangan tracking. Seluruh 65 ID awal tercakup pada 13 batch di bawah; AX adalah perluasan/temuan lanjutan, bukan otomatis 8 tiket tambahan yang independen.

Jangan memberikan seluruh batch sebagai satu instruksi rewrite besar. Mulai B01 untuk exposure/scope, sepakati contract B02–B04–B08–B09, lalu implementasi vertikal kecil dengan migration dan test yang membuktikan invariant. Untuk perbaikan logic gunakan regression test yang gagal pada baseline; untuk schema/multi-write gunakan integration test MongoDB dan fault injection. Koreksi UI ringan tidak memerlukan test yang hanya meniru markup.

## Instruksi pembuka yang disertakan pada setiap batch

```text
Audit acuan KNHOST adalah commit d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467.
Pertama bandingkan dengan HEAD workspace Anda dan periksa apakah jalur itu sudah berubah. Jangan menerapkan nomor baris lama secara membabi buta. Baca AGENTS.md yang berlaku dan jaga perubahan pengguna. Validasi ulang trigger sebelum mengedit.

Implementasikan batch yang dipilih sampai reviewable. Jangan memperbaiki gejala UI saja jika invariant backend rusak. Jangan melakukan deploy, memodifikasi data produksi, atau rewrite history. Untuk data lama buat dry-run migration, daftar anomali, strategi rollback dan record perubahan. Pisahkan bukti unit/model, Mongo integration, API, browser dan hardware; jangan menyebut semuanya sudah diuji jika belum.

Laporan akhir wajib memuat akar masalah, file yang berubah, behavior sebelum/sesudah, test dengan expected numeric outcomes, compatibility/migration, dan keterbatasan. Nilai uang/unit memakai policy yang eksplisit; jangan mengganti metode biaya atau aturan pajak tanpa menyatakan basisnya. Tidak boleh menutup exception dengan catch/pass atau menyamakan pending posting dengan posted.
```

## Batch kerja

### B01 — Scope, credentials dan request identity

**Cakupan:** GN-01 GN-02 GN-03 GN-04 GN-09 GN-10 GN-16 RF-08 RF-09 RF-12 RF-13; AX-04 AX-06.

```text
Perbaiki authorization boundary dari request sampai setiap roll/item. Ikat idempotency pada authenticated principal, active scope, method/path dan canonical payload hash; replay tetap memeriksa izin. Jangan menyimpan API key dalam DTO list. Pisahkan enabled/revoked dan heartbeat device. Perbaiki websocket subscriber scope/expiry, bank/cash ID guards, R&D source owner, CRM dan rekomendasi POS. Typed count scope harus immutable dan mendukung satu/multi-owner tanpa None-as-all. Notifikasi harus mempertahankan recipient+entity sampai digest; jangan menghapus global announcements yang memang sah.

Acceptance wajib: A-only/A+B/admin/custom-role; ID entity lain, body/header mismatch, same key payload berbeda, expired session, device revoked reconnect, personal notification nonrecipient, count bersama, dan print job campuran. Semua denial sebelum side effect; tidak ada secret pada response/log.
```

Lokasi awal untuk inspeksi:

- [backend/idempotency.py:32](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/idempotency.py#L32)
- [backend/server.py:294](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/server.py#L294)
- [backend/routers/bank.py:82](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank.py#L82)
- [backend/routers/rnd.py:318](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L318)
- [backend/routers/crm_omnichannel.py:126](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm_omnichannel.py#L126)
- [backend/routers/pos.py:20](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pos.py#L20)
- [backend/services/ai_schedules.py:92](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ai_schedules.py#L92)
- [backend/services/cycle_count_service.py:22](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cycle_count_service.py#L22)
- [backend/services/cycle_count_service.py:44](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cycle_count_service.py#L44)
- [backend/services/rfid_service.py:197](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L197)
- [backend/services/rfid_ingest_service.py:35](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L35)

### B02 — Core roll, split, provenance dan projection

**Cakupan:** WM-01 WM-02 GN-12 GN-13 GN-15 FN-03; AX-05 AX-07.

```text
Pisahkan logical reservation dari physical cut dengan migrasi kompatibel. Perbaiki stale normalization setelah CAS dan atomicity parent+child. Tegakkan conservation qty dalam base unit, immediate-parent/root genealogy, acquisition origin immutable dan source cost-layer identity. Hilangkan silent aggregate truncation serta raw-unit fallback. Projection harus versioned/watermarked agar rebuild lama tidak menimpa baru. Jangan memaksa semua status array identik: dokumentasikan predicate taggable/onsite/allocatable/countable.

Acceptance wajib: Split concurrent30+40 atas100 tidak boleh total140; failed child insert dapat dipulihkan; sequential100 tetap100; tiga generasi parent tepat; cancel reservation tidak mencipta physical roll; initial/legacy mixed UOM direkonsiliasi; data melebihi cap tetap terhitung; reverse-order rebuild tidak mundur.
```

Lokasi awal untuk inspeksi:

- [backend/services/roll_service.py:490](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L490)
- [backend/services/roll_service.py:184](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L184)
- [backend/services/contract_service.py:62](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/contract_service.py#L62)
- [backend/services/costing_service.py:70](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/costing_service.py#L70)

### B03 — Putaway, transfer, QC dan lokasi

**Cakupan:** WM-03 WM-04 WM-05 WM-09; AX-04 AX-05 AX-08.

```text
Terapkan shared movement authorization dan version/claim per roll. PA harus memeriksa owner/source/current status/QC/doc membership; transit tidak tersedia untuk demand lain. Pisahkan dispatch, arrival staging dan bin confirmation. [] bukan wildcard receive; manual acceptance command eksplisit dengan permission/reason. Transfer explicit IDs wajib owner/product/source/qty match dan menjalankan projection update. Receipt tidak menimpa acquisition dan tidak retain bin asal. Exception resolution menulis movement setara normal path dan menghitung ulang status parent.

Acceptance wajib: Concurrent PA/SO/transfer; quarantine vs QC relocation khusus; cancelled PA; arrival kosong/salah EPC/duplikat; stale qty70 versus PA100; cross-owner explicit roll; same roll duaPA; exception accept/return; arrival W2 tidak membawa BIN-W1; landed cost PO tetap menemukan roll sesudah transfer.
```

Lokasi awal untuk inspeksi:

- [backend/services/putaway_order_service.py:177](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L177)
- [backend/services/putaway_order_service.py:154](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L154)
- [backend/services/putaway_order_service.py:129](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L129)
- [backend/services/putaway_order_service.py:228](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/putaway_order_service.py#L228)

### B04 — Pick, shipment manifest dan dispatch atomik

**Cakupan:** WM-06 RF-04 RF-05 RF-06 GN-11; AX-01 AX-02 AX-03.

```text
Konfirmasi pick memverifikasi roll/bin/lot/qty positif dan menyimpan work-line identity. Shipment mengambil pick lines yang telah dikonfirmasi, tidak reselect roll berdasarkan jumlah. Manifest harus terversi dan seluruh physical child sudah ada sebelum loading. Buat required-loading policy per flow/warehouse dan override auditable. Claim memeriksa task version/re-read; stale request tidak menimpa progres. Persist operation, movement, shipment, task dan posting obligation secara atomik atau saga recoverable; finish setelah semua core effects durable. Recovery bukan sekadar unlock.

Acceptance wajib: Pick NEW50 tidak ship OLD50; partial cut tidak mencipta untagged child setelah loading; expected2/tag1 tidak clean; alokasi berubah invalidasi proof; concurrentpartial30+30 menghasilkan shipped60 atau conflict; failure sebelum/sesudah tiap write, response loss dan retry tidak orphan atau double; one operation one shipment effect.
```

Lokasi awal untuk inspeksi:

- [backend/routers/outbound_picking.py:82](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L82)
- [backend/services/loading_check_service.py:104](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L104)
- [backend/services/loading_check_service.py:56](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L56)
- [backend/services/loading_check_service.py:54](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L54)
- [backend/routers/saga_locks.py:36](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/saga_locks.py#L36)

### B05 — Tag, printer dan typed verification

**Cakupan:** RF-01 RF-07 RF-10 RF-11 RF-14 RF-15 UX-02; AX-06 AX-08.

```text
Gunakan canonical EPC bersama encode/ZPL/ingest/verify, dengan migrasi collision-safe. Escape ZPL field dan validasi kapasitas/format identifier yang disepakati. Typed sessions memeriksa kind dan transition; scan menggunakan atomic union/event append dan completion konsisten terhadap concurrent scan. Semua simulation evidence ditandai dan tidak dapat release produksi. Pisahkan tag lifecycle dari stock journey. Print job satu owner+warehouse atau full-member authorization; printer claim lease/attempt dan kind-scoped ACK. Reprint/replace serta uncertain print harus punya recovery. Download mempertahankan active entity tanpa membocorkan token di URL.

Acceptance wajib: Encode→raw reader→verify; malformedEPC/ZPL; batchlastiteminvalid noorphan; A+Bjob→Aonly; wrongkindcomplete; duplicate/concurrentscans; verified_with_issues retry; two printers/lateACK/restart; reprintstoredroll tidak tag_verified operasional; download pada entity non-home.
```

Lokasi awal untuk inspeksi:

- [backend/services/rfid_service.py:43](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L43)
- [frontend/src/features/rfid/CycleCountPanel.jsx:67](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/CycleCountPanel.jsx#L67)
- [backend/services/rfid_print_service.py:219](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L219)
- [backend/services/rfid_print_service.py:43](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L43)
- [backend/services/rfid_print_service.py:20](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L20)
- [backend/services/rfid_ingest_service.py:144](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L144)
- [frontend/src/features/rfid/RfidPrintVerifyPanel.jsx:180](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/RfidPrintVerifyPanel.jsx#L180)

### B06 — Gate edge contract, evaluator dan kiosk

**Cakupan:** RF-02 RF-03 RF-16 UX-01; AX-08.

```text
Tulis kontrak edge yang tersedia terlebih dahulu; jangan mengarang API middleware Kotlin yang belum diberikan. Gunakan event/passage IDs, capture/server time, lane/config version, dedup lintas restart dan ACK lengkap. Implementasikan evaluator sama untuk simulator dan production tetapi proof simulation terisolasi. Device enabled, QC, source/destination, current released manifest membership/version dan direction evidence harus valid. Kiosk per passage dengan stale/disconnected state; alarm ack tidak commit inventory. Offline policy eksplisit, tidak automatic green.

Acceptance wajib: PA aktif tujuan salah tetap red; transit tanpa tujuan sah blocked; cancelled PA+quarantine tidak green; unknown/retired/wronglane; mixedpassage; staleproof; repeatedbatch; sequencegap; restart; >500input dengan hasil eksplisit; networkloss clearstate. Hardware acceptance harus dilaporkan terpisah dari unit tests.
```

Lokasi awal untuk inspeksi:

- [backend/services/rfid_ingest_service.py:78](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L78)
- [backend/services/rfid_ingest_service.py:65](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L65)
- [backend/services/rfid_ingest_service.py:98](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L98)
- [frontend/src/features/rfid/RfidGateMonitorView.jsx:71](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/rfid/RfidGateMonitorView.jsx#L71)

### B07 — Count, opname dan adjustment financial

**Cakupan:** RF-17 WM-07 WM-08 FN-14.

```text
Pisahkan presence count dari meter quantity count. Scope expected harus owner/warehouse/bin/status/cutoff tepat; countable untagged jangan diam-diam hilang. Accuracy label jangan menyamakan recall dengan semua benar; result extra tetap diuji. Adjustment menyebut roll/dimensi, full success atau explicit unresolved, tidak approve shortageparsial. Terapkan variance valuation dan JE melalui posting contract. Koreksi audit: surplus helper sudah fallback product.harga_pokok, tidak selalu zero; jangan membuat patch berdasarkan asumsi salah itu.

Acceptance wajib: Foundexpected10+extra2 tidak tampil allclear; missingtag bukan langsung missingmeters; binA tidak countbinB; duplicateitems; movementduringcount; shortageunfulfillable; reserved/picked policy; surplus HPP100 benar, missingcostpolicy eksplisit; adjustment retry tepat sekali; valuation delta sama variance JE.
```

Lokasi awal untuk inspeksi:

- [backend/services/rfid_service.py:21](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L21)
- [backend/routers/cycle_count.py:119](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L119)
- [backend/services/roll_service.py:1602](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L1602)

### B08 — Landed cost, costing dan AP match

**Cakupan:** FN-01 FN-02 FN-11; AX-05 AX-07.

```text
Pilih dan dokumentasikan valuation policy sesuai bisnis; jangan menganggap WAC selalu salah. Resolve receipt/PO line dan cost-layer asal immutable. Alokasikan landed cost tepat sekali per unit ekonomi, tidak sekaligus direct child dan propagation parent. Hasil harus order-independent; pisahkan bagian onhand/consumed/shipped sesuai policy periode. COGS konsisten dengan shipment actual dan metode subledger, bukan mutable order-average yang tak terdefinisi. AP match akumulasi current duplicate lines dan invoice lain atomik terhadap matched capacity.

Acceptance wajib: Parent70 child30 landed100: kedua urutan total100, bukan130; transfer sebelumlatecost tetap tercakup; grandchild; zeroqty/deleted/cancelled target; partialsold; samevoucherretry; duplicateproduct lines melewati PO qty ditolak; dua bills race tidak overbill; actualrollcost versus averagepolicy direkonsiliasi.
```

Lokasi awal untuk inspeksi:

- [backend/services/landed_cost_service.py:62](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/landed_cost_service.py#L62)
- [backend/services/vendor_bill_service.py:78](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/vendor_bill_service.py#L78)
- [backend/services/gl_service.py:992](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L992)

### B09 — Cash, AR, bank, aset dan durable posting

**Cakupan:** FN-07 FN-08 FN-10 FN-12 FN-15; AX-02.

```text
Bangun reusable posting obligation/outbox yang di-commit bersama source change dan idempotent source event ID; gunakan pending/failed/posted yang terlihat. Cash manual dan void harus memiliki JE/reversal sesuai lifecycle. Opening bank merupakan opening transaction yang dapat direkonsiliasi, bukan mutable master value tanpa jejak. Perubahan aset yang telah posted perlu amendment/reclass/reversal. Validasi finite amounts, balance, effective accounts, entity, currency dan period pada persistence journal bersama. Jangan menuntut transaksi kas/stock yang nyata dibatalkan hanya karena downstream posting sedang retry; pertahankan kewajiban posting yang durable.

Acceptance wajib: Fail GL sesudah ARcash, retry, crashoutbox, doubleworker; manualcashcreate/void; banksaldoopening+transfer; accountmissing; NaN/Infinity/unbalanced; assetamendment before/afterdep; sourceamount=sumGL; pendingposting membuat close control bekerja. Recovery historis dry-run berisi residual per sumber.
```

Lokasi awal untuk inspeksi:

- [backend/routers/cash.py:108](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash.py#L108)
- [backend/services/bank_service.py:78](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_service.py#L78)
- [backend/services/ar_receipt_service.py:71](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ar_receipt_service.py#L71)
- [backend/services/fixed_asset_service.py:141](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/fixed_asset_service.py#L141)
- [backend/services/gl_service.py:503](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L503)

### B10 — COA, laporan dan period close

**Cakupan:** FN-04 FN-05 FN-06 FN-09 FN-13 FN-16.

```text
Resolver effective COA per entity dipakai manual journal dan laporan; jangan last-write-wins global code. Neraca default mempunyai cutoff aktual sesuai label. Arus kas memakai metode yang dinyatakan dan membedakan noncash/reclassification, bukan sekadar delta tiap akun. Period guard berlaku pada void/reversal/amendment. Close/reopen/posting terserialisasi dan unique per entity+period+operation; validasi kewajiban posting dan reconciliation sebelum close.

Acceptance wajib: Entity A/B override code beda type; customaccount manual; futurejournal defaultreport; depreciation dan assetcreditpurchase tidak mencipta net cash palsu atau komponen salah; transferantarbank bukan operatingcash; closedvoid; concurrentclose menghasilkan satu hasil; posting bersamaan cutoff teratur; reopenretry aman.
```

Lokasi awal untuk inspeksi:

- [backend/services/cash_flow_service.py:61](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/cash_flow_service.py#L61)
- [backend/services/financial_statement_service.py:41](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/financial_statement_service.py#L41)
- [backend/services/gl_service.py:567](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L567)
- [backend/services/gl_service.py:673](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L673)
- [backend/services/closing_service.py:253](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/closing_service.py#L253)
- [backend/services/financial_statement_service.py:174](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/financial_statement_service.py#L174)

### B11 — Mutasi alternatif dan konversi dokumen

**Cakupan:** GN-05 GN-06 GN-07 GN-08.

```text
Bawa R&D issue/compensation, production completion, supplier return dan internal-request conversion ke operation contract bersama. Jangan restore snapshot roll yang telah dipakai transaksi lain. WO menyimpan BOM version dan actual consumption; physical partial return mempertahankan object identity. Conversion klaim request dan unique source_request business key sebelum membuat interco. Audit write paths lain yang memakai helper yang sama dan dokumentasikan cakupannya.

Acceptance wajib: GLfail setelahissue sementara concurrentconsume; retryWO setelah partialwrites; BOM berubah setelahrelease; partialreturnlot/tag/qty; doubleconvert requests dengan key berbeda; recovery tidak menghapus operasi sukses pihak lain; conservation + owner + cost invariant di semua jalur.
```

Lokasi awal untuk inspeksi:

- [backend/services/rnd_sample_service.py:1246](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_sample_service.py#L1246)
- [backend/services/production_service.py:358](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/production_service.py#L358)
- [backend/services/purchase_return_service.py:621](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/purchase_return_service.py#L621)
- [backend/services/internal_request_service.py:415](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/internal_request_service.py#L415)

### B12 — Payroll, HR dan marketing

**Cakupan:** HR-01 HR-02 HR-03 MK-01.

```text
Payroll PPh21 harus memisahkan masa normal dan terakhir sesuai kategori/aturan berlaku, menghitung rekonsiliasi tahunan dengan fixture independen. Lembur berdasar daytype/jam/eligibility dan dedup sumber event, bukan flat multiplier umum. Leave approval recheck saldo secara atomik, allocatehari per tahun dan cegah overlap. Marketing partialmetrics harus merge atau API replacement eksplisit. Jangan menambah perubahan payroll hanya berdasar asumsi tarif tanpa sumber resmi dan tanggal efektif.

Acceptance wajib: Pegawai setahun/berhenti tengahtahun, kategoriTER, bonus dan reconciliation; hari kerja/libur, jam pertama/berikutnya, event attendance+request sama; dua pending cuti berbedatanggal oversubscribe; crossyear/cancelreversal; PATCH satu metric mempertahankan metric lain.
```

Lokasi awal untuk inspeksi:

- [backend/services/hr_payroll_service.py:191](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L191)
- [backend/services/hr_payroll_service.py:180](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L180)
- [backend/services/hr_leave_service.py:87](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L87)
- [backend/services/marketing_service.py:259](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/marketing_service.py#L259)

### B13 — Audit trail, kandidat secret dan label ringan

**Cakupan:** GN-14 UX-03.

```text
Perbaiki audit perubahan dengan before/after atau bounded diff dan source operation identity, sambil menyamarkan data sensitif. Jangan menyatakan kandidat token repo masih aktif tanpa bukti; lakukan secret inventory aman tanpa mencetak nilainya atau mencoba login. Rotasi credential nyata melalui pemiliknya dan jangan menghapus history secara otomatis. Panel OCR menampilkan nama entity dengan ID teknis sekunder bila perlu.

Acceptance wajib: Mutationaudit before/after terbaca dan redacted; domaincosthistory tetap utuh; no credentials in logs/output; artifactclassification tanpa validcredentialclaim; entitylabel non-home benar. Perubahan label tidak membutuhkan suite besar yang hanya meniru implementasi.
```

Lokasi awal untuk inspeksi:

- [backend/dependencies.py:168](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L168)
- [frontend/src/features/wms/grn/GrnOcrUsagePanel.jsx:53](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/frontend/src/features/wms/grn/GrnOcrUsagePanel.jsx#L53)

## Urutan rekonsiliasi Finance yang harus menjadi bukti selesai

| Fixture | Invariant penerimaan |
|---|---|
| Receipt100m@Rp10.000 lalu cut30/70 tanpa loss | Totalqty100; valueRp1.000.000; cost conservation |
| Landed costRp100.000 sebelum/sesudah split dan transfer | Total uplift tepatRp100.000, urutan tidak memengaruhi hasil; acquisition tetap |
| Shipment30m dengan actualroll yang ditetapkan | Qty/movement/shipment/COGS menggunakan identitas dan metode biaya yang sama |
| Surplus10m HPPfallbackRp10.000 | Unitcost tidak otomatis0; valuationRp100.000 menurut policy dan varianceJE sesuai |
| ARcashRp1.000.000, posting service gagal lalu pulih | AR/cash tetap terkontrol, obligation pending terlihat, GL tepat sekaliRp1.000.000 |
| Void kas/jurnal pada closed period | Ditolak atau reversal pada periode sah dengan link; historic period tidak berubah diam-diam |
| Pembelian aset kredit tanpa pembayaran | Tidak menciptakan arus kas investasi saat itu; liability/asset tercatat sesuai policy |
| Depresiasi tanpa cash | Tidak menjadi pembayaran kas; penyajian cash-flow konsisten metode yang dipilih |
| Akun code sama metadata berbeda A/B | Report A memakai override A dan B memakai B; manual journal memakai resolver sama |
| Dua close period bersamaan | Satu closing operation, tidak dua jurnal penutup |

Angka ini fixture pengujian, bukan angka produksi. Tambahkan pajak/currency/rounding sesuai kebijakan aktual. Debit=kredit saja bukan acceptance yang cukup: source amount, account, entity, date, classification dan lifecycle juga harus cocok.

## Definition of done untuk keseluruhan perbaikan

Setiap ID ditutup dengan bukti reproduksi sebelum, perbaikan setelah, cakupan caller alternatif, dan data-migration disposition. Bug dan gap policy tidak ditutup hanya dengan dokumentasi apabila policy tersebut akan dipakai sebagai kontrol operasional. Sebaliknya, fitur optional enterprise tidak perlu dibangun untuk menutup bug yang tidak terkait. Pertahankan ID yang belum selesai sebagai open dengan alasan dan residual risk yang konkret.

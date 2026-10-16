> **Review lanjutan 29 September 2026:** baca [hasil validasi Astra](07_REVIEW_ASTRA_MULAI_DI_SINI.md) dan [koreksi per temuan](08_VALIDASI_65_TEMUAN.md) sebelum memakai laporan/prompt awal ini. Sebagian klaim telah dipersempit atau dikoreksi.

# Prompt perbaikan untuk AI agent developer

Gunakan satu batch atau satu tiket per pekerjaan agar perubahannya dapat ditinjau. Semua 65 tiket tercakup tepat satu kali dalam batch di bawah. Temuan menyertakan bukti kode pada snapshot; agent wajib mengecek ulang branch terbaru.

## Prompt pembuka wajib

```text
Anda adalah agent developer KNHOST. Perbaiki tiket yang saya pilih berdasarkan audit snapshot d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467. Mulai dengan memeriksa HEAD saat ini dan membuktikan apakah jalur yang diaudit masih berlaku; jangan menyalin asumsi audit bila kode telah berubah.

Baca temuan, source, router, schema, index/bootstrap, callers alternatif, background job, UI dan guard terkait. Buat test yang gagal sebelum fix untuk perilaku yang salah. Untuk scope, concurrency, retry dan pemulihan lintas-koleksi, gunakan Mongo test database terisolasi dan integration tests yang bermakna; mock tunggal tidak membuktikan atomisitas. Jangan menyentuh database/credential/perangkat produksi.

Tegakkan invariant quantity/value conservation, owner/entity isolation, canonical physical identity, base UOM, source-linked GL lifecycle, period lock dan operation idempotency. Dokumentasi SSOT harus menunjuk jalur mutation yang benar-benar dipakai. Pertahankan kontrol yang sudah benar dan batasi perubahan pada tiket.

Jika perlu migrasi: buat read-only discrepancy report, dry-run, backup/checkpoint, idempotent migration dan rollback/compensation plan. Perbaikan akuntansi memakai reversal/adjustment yang disetujui pemilik buku; jangan menghapus transaksi posted atau menutup selisih dengan opening equity agar laporan terlihat seimbang.

Jangan menaikkan baseline guardrail, menambahkan exception tanpa dasar, mematikan tes, mengubah hasil expected agar bug lolos, melonggarkan scope, atau mengubah UI agar kegagalan terlihat sukses. Index unik harus diuji keberadaannya, bukan diasumsikan dari bootstrap yang menangkap exception.

Laporkan reproduksi before/after, file yang diubah, test benar-benar dijalankan dan hasilnya, risiko kompatibilitas/migrasi, serta keterbatasan tersisa. Selesaikan patch dan test lokal; jangan deploy, menjalankan migrasi produksi, atau mengubah hardware tanpa instruksi terpisah.
```

## Urutan batch dan dependensi

Urutan ini membantu mengamankan integritas sebelum optimasi. Canonical EPC RF-01 dapat dikerjakan awal; integrasi gate final membutuhkan movement/physical identity yang sudah benar. Finance valuation bergantung pada mutation stok yang konservatif. Jangan menganggap satu batch otomatis menutup seluruh temuan di flow yang sama.

| Batch | Tujuan | Tiket |
|---|---|---|
| 01 | Credential dan perangkat | RF-12 RF-13 GN-14 |
| 02 | Isolasi entity dan replay | GN-01 GN-02 GN-03 GN-04 GN-09 GN-10 GN-16 RF-08 RF-09 |
| 03 | Mutation stok dan konkurensi | WM-01 WM-06 GN-05 GN-06 GN-07 WM-07 WM-08 GN-13 |
| 04 | Identitas fisik dan status | WM-02 RF-17 |
| 05 | Valuation dan HPP | FN-01 FN-03 FN-11 FN-14 |
| 06 | Kas/bank/AR dan reversal | FN-07 FN-08 FN-10 |
| 07 | COA/journal/date/aggregation | FN-05 FN-06 FN-15 FN-16 GN-12 |
| 08 | Cashflow | FN-04 |
| 09 | Closing dan aset | FN-09 FN-13 FN-12 |
| 10 | Canonical EPC dan movement gate | RF-01 RF-02 RF-03 RF-16 UX-01 |
| 11 | Print/verify/printer queue | RF-10 RF-11 RF-14 RF-15 UX-02 |
| 12 | Loading dan bukti fisik | RF-04 RF-05 RF-06 RF-07 |
| 13 | Putaway dan perjalanan lokasi | WM-03 WM-04 WM-05 WM-09 UX-03 |
| 14 | Konversi/recovery/SSOT helper | GN-08 GN-11 GN-15 |
| 15 | Payroll/leave/marketing | HR-01 HR-02 HR-03 MK-01 |
| 16 | AP matching | FN-02 |

## Prompt siap salin per tiket

Tempel prompt pembuka, lalu salah satu prompt berikut. Kriteria selesai pada tiket adalah minimum; integration matrix lintas-flow tetap diperlukan.

### RF-01 — Format EPC database berbeda dari EPC yang ditulis ke chip

Rujukan: [RF-01](01_TEMUAN_AUDIT_KNHOST.md#rf-01).

```text
Perbaiki RF-01 (P1): Format EPC database berbeda dari EPC yang ditulis ke chip.

Status bukti audit: Direproduksi.

Periksa lokasi awal: backend/services/rfid_service.py:43; backend/services/rfid_print_service.py:43; backend/services/rfid_ingest_service.py:99. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Generator menyimpan EPC dengan tanda hubung; ZPL menghapus tanda hubung; ingest dan scan_verify hanya strip/uppercase lalu mencari kecocokan persis. Tidak ada canonicalizer bersama. Middleware eksternal mungkin memformat ulang, tetapi kontrak backend sendiri tidak menjamin itu.

Reproduksi/negative case: RF-01 menghasilkan EPC berkelompok dari fungsi asli, mengambil payload ^RFW, dan membuktikan kedua string berbeda. Reader yang mengirim 24 hex tanpa hubung akan dianggap EPC asing atau extra meskipun tag dicetak sistem sendiri.

Arah perbaikan: Simpan EPC canonical uppercase hex tanpa separator; formatter hanya untuk tampilan. Migrasi data dan referensi expected/scanned; deteksi benturan sebelum unique index. Validasi panjang/hex secara eksplisit.

Acceptance criteria: Encode→ZPL→raw reader→ingest→verify harus menunjuk roll yang sama; input berseparator/lowercase di normalisasi konsisten; dua representasi tidak boleh menghasilkan dua tag.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-02 — Gate OUT menganggap status sebagai izin keluar

Rujukan: [RF-02](01_TEMUAN_AUDIT_KNHOST.md#rf-02).

```text
Perbaiki RF-02 (P1): Gate OUT menganggap status sebagai izin keluar.

Status bukti audit: Direproduksi.

Periksa lokasi awal: backend/services/rfid_ingest_service.py:78; backend/services/rfid_service.py:32. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Cabang umum OUT menerima reserved/allocated/committed/picked/packed/transit/delivered/consumed. SO hanya dibaca untuk nomor; tidak diperiksa status, gudang asal, shipment aktif, atau keanggotaan roll pada manifest. PA juga diterima dari journey tanpa cek status PA pada cabang OUT.

Reproduksi/negative case: RF-02: roll delivered milik gudang SOURCE dibaca gate OTHER, tanpa SO/PA; hasil green. Reserved saja juga dapat green sebelum benar-benar siap pengiriman.

Arah perbaikan: Gunakan otorisasi movement aktif berisi roll_id, source/destination, status release, manifest_version, waktu, lane dan owner. OUT harus cocok source dan manifest; delivered/consumed tidak otomatis sah. Simulator memakai evaluator yang sama.

Acceptance criteria: Uji SO batal, PA selesai, roll salah gudang, roll belum release, tag consumed, salah shipment, dan replay keluar: seluruhnya ditahan dengan reason code yang jelas.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-03 — Gate IN menerima transit di gudang mana pun

Rujukan: [RF-03](01_TEMUAN_AUDIT_KNHOST.md#rf-03).

```text
Perbaiki RF-03 (P1): Gate IN menerima transit di gudang mana pun.

Status bukti audit: Direproduksi.

Periksa lokasi awal: backend/services/rfid_ingest_service.py:65. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Jika PA tidak ditemukan/aktif, status transit langsung green. Transfer dan shipment tujuan tidak dicari; bahkan transit penjualan dianggap boleh diterima di gudang internal mana saja.

Reproduksi/negative case: RF-03 mengirim roll in_transit_transfer ke warehouse WRONG tanpa dokumen tujuan; fungsi asli memberi green.

Arah perbaikan: Resolusi dokumen transit wajib dari ref dan validasi destination, membership, owner, expected route dan status. Dokumen hilang atau tidak konsisten masuk exception; jangan fallback green.

Acceptance criteria: Roll menuju D dibaca IN H harus red; IN D hanya green saat movement aktif dan roll tercantum. Transit_sales tidak boleh dianggap transfer internal.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-04 — Final Loading Check belum menjadi prasyarat dispatch

Rujukan: [RF-04](01_TEMUAN_AUDIT_KNHOST.md#rf-04).

```text
Perbaiki RF-04 (P1): Final Loading Check belum menjadi prasyarat dispatch.

Status bukti audit: Perilaku terbukti; gap kontrol.

Periksa lokasi awal: backend/services/loading_check_service.py:104. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: dispatch_guard menahan sesi terbuka dan hasil bermasalah, tetapi bila loading_check tidak pernah dibuat ia mengizinkan dispatch. Kontrol ini opsional secara implementasi. Ini gap terhadap tujuan pencegahan wrong-roll shipment, bukan klaim bahwa semua gudang wajib RFID.

Reproduksi/negative case: RF-04 memanggil guard untuk SO tanpa sesi atau hasil check; kembali normal.

Arah perbaikan: Buat policy per gudang/tracking_mode: RFID wajib check valid; barcode/manual memakai proses alternatif eksplisit. Override hanya permission tertentu dengan alasan dan audit, bukan ketiadaan data.

Acceptance criteria: Untuk policy RFID mandatory, dispatch tanpa check ditolak. Policy barcode tetap operasional melalui scan/override yang terkontrol; UI menjelaskan alasan blokir.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-05 — Loading Check clean walaupun sebagian roll tidak punya tag

Rujukan: [RF-05](01_TEMUAN_AUDIT_KNHOST.md#rf-05).

```text
Perbaiki RF-05 (P1): Loading Check clean walaupun sebagian roll tidak punya tag.

Status bukti audit: Terbukti dari jalur kode.

Periksa lokasi awal: backend/services/loading_check_service.py:56; backend/services/loading_check_service.py:77. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Expected hanya berisi roll yang punya tag aktif. untagged_count di catat sebagai angka peringatan tetapi tidak ikut menentukan clean dan tidak disimpan sebagai blocker pada SO.

Reproduksi/negative case: Alokasi dua roll: satu bertag dan satu tanpa tag. Scan satu EPC; missing/extra kosong, sesi menjadi clean walau roll kedua belum diverifikasi.

Arah perbaikan: Manifest verifikasi mencakup semua roll fisik. Roll tanpa RFID perlu scan barcode id entitas atau pengecualian berizin; untagged unresolved berarti tidak clean.

Acceptance criteria: Satu tagged+ satu untagged tidak boleh clean setelah satu EPC. Tidak aktifnya tag, retired tag dan dangling tag_id juga di hitung unresolved.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-06 — Hasil loading melekat pada SO, tidak pada versi shipment aktual

Rujukan: [RF-06](01_TEMUAN_AUDIT_KNHOST.md#rf-06).

```text
Perbaiki RF-06 (P1): Hasil loading melekat pada SO, tidak pada versi shipment aktual.

Status bukti audit: Risiko kontrol dari kode.

Periksa lokasi awal: backend/services/loading_check_service.py:54; backend/services/loading_check_service.py:84; backend/services/loading_check_service.py:93. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Snapshot expected seluruh roll SO tidak mengikat task/shipment, gudang, allocation_version atau hash manifest. Guard hanya membaca result terakhir; perubahan alokasi/picking setelah check tidak membatalkan hasil.

Reproduksi/negative case: Check clean, ganti roll alokasi atau tambah pengiriman parsial gudang lain, lalu dispatch dengan result lama. Skenario ini perlu integration test untuk memastikan seluruh jalur perubahan; guard sendiri tidak mempunyai validasi versi.

Arah perbaikan: Sesi per shipment/task+warehouse dengan manifest immutable/version; invalidasi bila roll/qty/order berubah; guard membandingkan hash/version dan freshness.

Acceptance criteria: Pergantian satu roll setelah clean wajib recheck. Dua shipment parsial punya sesi independen. Check shipment A tidak membuka dispatch B.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-07 — Tombol simulasi dapat mengisi bukti verifikasi operasional

Rujukan: [RF-07](01_TEMUAN_AUDIT_KNHOST.md#rf-07).

```text
Perbaiki RF-07 (P1): Tombol simulasi dapat mengisi bukti verifikasi operasional.

Status bukti audit: Terbukti dari UI dan API.

Periksa lokasi awal: frontend/src/features/rfid/CycleCountPanel.jsx:67; frontend/src/features/rfid/RfidPrintVerifyPanel.jsx:244; frontend/src/features/wms/LoadingCheckPanel.jsx:79. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: UI mengirim semua EPC expected ke endpoint scan produksi untuk simulasi. Tidak ada pemisahan namespace/sesi simulasi yang menjaga hasil tidak digunakan sebagai verifikasi nyata. Endpoint menerima EPC dari user biasa tanpa bukti device.

Reproduksi/negative case: Mulai count/print verify/loading; gunakan simulasi semua tag; selesaikan. Sistem tidak dapat membedakan bukti fisik dari daftar yang disalin dari expected.

Arah perbaikan: Simulation hanya environment/sesi test yang tidak boleh dispatch atau memutakhirkan journey produksi. Untuk operasi, sertakan asal scan dan id entitas reader; manual override terpisah dan di audit.

Acceptance criteria: Hasil simulated tidak dapat memberi clean operasional atau izin dispatch. User tanpa override tidak dapat mengesahkan seluruh expected lewat tombol simulasi.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-08 — Sesi dan histori Cycle Count RFID tidak terisolasi entitas

Rujukan: [RF-08](01_TEMUAN_AUDIT_KNHOST.md#rf-08).

```text
Perbaiki RF-08 (P1): Sesi dan histori Cycle Count RFID tidak terisolasi entitas.

Status bukti audit: Direproduksi sebagian; jalur lengkap statis.

Periksa lokasi awal: backend/services/cycle_count_service.py:22; backend/services/cycle_count_service.py:53; backend/services/cycle_count_service.py:111. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Pencarian sesi existing hanya gudang/kind/status. complete tidak menerima scope; histori/count detail tidak punya guard owner. Dokumen hasil count bahkan tidak menyimpan owner scope. Ini berbeda dari cycle-count non-RFID yang sudah memakai guard_doc.

Reproduksi/negative case: RF-08: sesi entitas A terbuka di gudang shared; pengguna B start dan mendapat sesi A. Permission wms tidak sama dengan izin terhadap data badan usaha A.

Arah perbaikan: Stempel immutable scope_ids/owner; existing harus tepat scope; guard scan, progress, complete, history dan detail. Backfill histori lama dengan asal session; data tidak bisa dipetakan jangan dianggap global bebas.

Acceptance criteria: User B tidak dapat melihat, reuse, scan atau complete sesi A meski warehouse sama. Histori hanya scope authorized; admin view-all eksplisit.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-09 — Cycle count lintas entitas dibuat tetapi tidak dapat dipindai

Rujukan: [RF-09](01_TEMUAN_AUDIT_KNHOST.md#rf-09).

```text
Perbaiki RF-09 (P2): Cycle count lintas entitas dibuat tetapi tidak dapat dipindai.

Status bukti audit: Direproduksi.

Periksa lokasi awal: backend/services/cycle_count_service.py:44; backend/services/rfid_print_service.py:214. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Saat scope lebih dari satu, session.owner_entity_id=None. scan_verify membandingkan None dengan daftar entity ID dan menolak. Representasi scope berbeda antara pembuat dan pemakai sesi.

Reproduksi/negative case: RF-09: sesi multi-owner valid dengan scope A/B selalu 403 pada scan.

Arah perbaikan: Representasikan scope sebagai set entity IDs dan validasi subset authorized; atau buat sesi per owner secara eksplisit. Jangan memakai None untuk arti lintas entitas.

Acceptance criteria: Single owner, multi-owner authorized, user dengan subset owner, dan view-all diuji tanpa kebocoran cross-scope.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-10 — Mesin sesi bersama tidak memvalidasi jenis sesi dan kehilangan scan konkuren

Rujukan: [RF-10](01_TEMUAN_AUDIT_KNHOST.md#rf-10).

```text
Perbaiki RF-10 (P1): Mesin sesi bersama tidak memvalidasi jenis sesi dan kehilangan scan konkuren.

Status bukti audit: Terbukti statis; konkurensi perlu DB test.

Periksa lokasi awal: backend/services/rfid_print_service.py:219; backend/services/rfid_print_service.py:236. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: scan membaca lalu $set keseluruhan scanned_epcs sehingga dua batch bersamaan dapat saling menimpa. Update tidak berprasyarat status open. complete_verify tidak memastikan kind print_verify dan dapat memproses loading_check/cycle_count karena memakai koleksi yang sama.

Reproduksi/negative case: Dua scan A/B membaca []; tulisan terakhir menghilangkan batch lain. Panggil print complete dengan ID sesi loading: sesi selesai, journey berubah tag_verified, tetapi loading_check SO tidak diperbarui.

Arah perbaikan: Sesi punya kind wajib; semua endpoint assert kind. Scan gunakan atomic $addToSet/$each dengan status/scope guard; complete snapshot/claim mencegah late write. Unknown ID harus 404, bukan sess.get pada None.

Acceptance criteria: Dua batch paralel mempertahankan union; scan setelah complete ditolak; endpoint print tidak menerima loading/count; unknown session menghasilkan 404.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-11 — Payload ZPL dan custom EPC tidak divalidasi aman

Rujukan: [RF-11](01_TEMUAN_AUDIT_KNHOST.md#rf-11).

```text
Perbaiki RF-11 (P2): Payload ZPL dan custom EPC tidak divalidasi aman.

Status bukti audit: Direproduksi untuk ZPL; EPC statis.

Periksa lokasi awal: backend/services/rfid_print_service.py:43; backend/services/rfid_print_service.py:52; backend/services/rfid_service.py:122. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Nama/SKU/roll/lot disisipkan langsung ke bahasa perintah printer. EPC custom tidak dijamin 24 hex; ZPL memotong 24 karakter sehingga dua EPC data base dapat ditulis sebagai chip yang sama.

Reproduksi/negative case: RF-11 memasukkan product_name berisi ^FS^FO0,0^FDINJECTED dan perintah itu muncul verbatim di label. Dua EPC dengan awalan 24 hex sama dan suffix berbeda ditulis identik.

Arah perbaikan: Escape/encode field text ZPL, batasi control characters; validasi EPC canonical dan panjang; jangan silently truncate. Dokumentasikan jenis encoding EPC internal vs GS1.

Acceptance criteria: Test ^, ~, new line, Unicode, string panjang, nonhex, 23/25/32hex; tidak ada command injection atau collision akibat truncation.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-12 — Daftar device membocorkan API key hardware

Rujukan: [RF-12](01_TEMUAN_AUDIT_KNHOST.md#rf-12).

```text
Perbaiki RF-12 (P1): Daftar device membocorkan API key hardware.

Status bukti audit: Direproduksi.

Periksa lokasi awal: backend/services/rfid_service.py:197; backend/routers/rfid.py:304. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: ensure_api_key menyimpan api_key di device. list_devices memproyeksikan hanya _id keluar dan mengembalikan semua field. Route list biasa bukan endpoint khusus pengambilan credential.

Reproduksi/negative case: RF-12: record device bertest key dikembalikan apa adanya oleh fungsi list. Key tersebut dapat dipakai device ingest/heartbeat tanpa login user.

Arah perbaikan: Whitelist public DTO; key hanya ditampilkan sekali pada provisioning berizin. Simpan hash key untuk authenticate; rotasi credential yang pernah terbuka; sanitasi audit/log.

Acceptance criteria: Semua list/detail/update response tidak berisi key/hash. Viewer tidak dapat mengambil key. Rotasi membuat key lama tidak berlaku.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-13 — Device dinonaktifkan masih diterima autentikasi

Rujukan: [RF-13](01_TEMUAN_AUDIT_KNHOST.md#rf-13).

```text
Perbaiki RF-13 (P1): Device dinonaktifkan masih diterima autentikasi.

Status bukti audit: Direproduksi.

Periksa lokasi awal: backend/services/rfid_ingest_service.py:35. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Authenticate hanya menguji keberadaan key. Disabled/status offline tidak merupakan revocation; heartbeat dan ingest kemudian dapat menyetelnya online kembali.

Reproduksi/negative case: RF-13: record status disabled dengan key valid tetap diterima authenticate.

Arah perbaikan: Pisahkan lifecycle enabled dari health; reject disabled/revoked; key rotation dan grace policy eksplisit. Heartbeat tidak mengaktifkan kembali device.

Acceptance criteria: Disabled ditolak pada ingest, heartbeat dan printer pull/ack; offline tetapi enabled bisa reconnect sesuai policy.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-14 — Lifecycle cetak mengklaim tag tercetak terlalu dini dan retry verifikasi buntu

Rujukan: [RF-14](01_TEMUAN_AUDIT_KNHOST.md#rf-14).

```text
Perbaiki RF-14 (P2): Lifecycle cetak mengklaim tag tercetak terlalu dini dan retry verifikasi buntu.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/services/rfid_print_service.py:20; backend/services/rfid_print_service.py:189. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Create job mengaktifkan tag dan menaikkan journey ke tag_printed ketika job baru queued. start_verify mengizinkan queued tetapi menolak verified_with_issues, padahal operator perlu ulang untuk missing. Reprint juga bisa menurunkan journey stored menjadi tag_printed/tag_verified.

Reproduksi/negative case: Printer belum pernah menerima job, tetapi roll ter tulis “Tag Dicetak”. Selesaikan verify dengan missing, lalu start verify lagi ditolak. Reprint roll tersimpan berpotensi masuk antrean perjalanan ulang.

Arah perbaikan: Pisahkan encode intent→queued→printer acknowledged→read-after-write verified→active. Tag replacement/reprint tidak reset storage journey; retry buat revision session yang jelas.

Acceptance criteria: Queued tidak berlabel printed. Verify gagal bisa di ulang; reprint stored tidak memindahkan lokasi atau routing; kegagalan item ke-2 tidak meninggalkan tag item ke-1 aktif tanpa job.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-15 — Antrean printer tidak memiliki claim dan ack tidak membatasi tipe device

Rujukan: [RF-15](01_TEMUAN_AUDIT_KNHOST.md#rf-15).

```text
Perbaiki RF-15 (P1): Antrean printer tidak memiliki claim dan ack tidak membatasi tipe device.

Status bukti audit: Terbukti statis; balapan perlu integration test.

Periksa lokasi awal: backend/services/rfid_ingest_service.py:144; backend/services/rfid_ingest_service.py:153. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Dua printer di gudang yang sama membaca job queued yang sama tanpa lease/claim/printer assignment. Ack hanya mengecek gudang dan status, bukan bahwa device printer pemilik claim.

Reproduksi/negative case: Printer P1/P2 pull sebelum ack: keduanya bisa mencetak tag ber-EPC sama pada dua fisik. Gate/handheld dengan key gudang sama dapat ack job printed.

Arah perbaikan: Atomic job lease ke pada printer tertentu, attempt_id, TTL dan recovery; ack wajib printer pemilik attempt; kemampuan QR/RFID berbeda; simpan hasil perlabel/write-readback.

Acceptance criteria: Dua pull paralel tidak mendapatkan ownership job yang sama. Ack dari gate, wrong printer, expired lease atau attempt lama ditolak.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-16 — Ingest belum mempunyai event identity, passage window dan deduplikasi lintas batch

Rujukan: [RF-16](01_TEMUAN_AUDIT_KNHOST.md#rf-16).

```text
Perbaiki RF-16 (P2): Ingest belum mempunyai event identity, passage window dan deduplikasi lintas batch.

Status bukti audit: Gap integrasi terbukti dari kontrak.

Periksa lokasi awal: backend/services/rfid_ingest_service.py:98; backend/services/rfid_ingest_service.py:110. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Dedup hanya dalam satu request; limit 500 dipotong diam-diam. Kontrak tidak menyimpan event_id/device timestamp/antenna/RSSI/session passage atau arah hasil sensor. Arah berasal dari konfigurasi device. Unique EPC aktif juga tidak tampak di bootstrap repo; index DB deployed belum diperiksa.

Reproduksi/negative case: Reader terus membaca tag diam: retry/batch berikut menciptakan read/incident baru. Lebih dari 500 EPC tidak seluruhnya di proses dan tidak dilaporkan dropped.

Arah perbaikan: Kontrak event batch dengan idempotency identity, capture time, antenna, passage/lane, direction confidence, limit explicit dan dead-letter. Simpan raw observation terpisah business event; active EPC uniqueness canonical.

Acceptance criteria: Replay event sama tidak menggandakan business event/incident. Tag diam tidak dianggap berulang kali keluar. >limit ditolak/dipecah dengan acknowledgement jelas.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### RF-17 — Definisi stok fisik RFID berbeda dari SSOT dan metrik count mengabaikan extra

Rujukan: [RF-17](01_TEMUAN_AUDIT_KNHOST.md#rf-17).

```text
Perbaiki RF-17 (P2): Definisi stok fisik RFID berbeda dari SSOT dan metrik count mengabaikan extra.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/services/rfid_service.py:21; backend/services/cycle_count_service.py:80. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: RFID mempunyai daftar physical ter sendiri yang memasukkan transit sales/transfer dan menghilangkan blocked/damaged/wip dibanding status fisik roll. Expected hanya tag aktif; roll tanpa tag hilang dari denominator. accuracy=found/expected tetap 100% jika seluruh expected plus EPC extra ter baca.

Reproduksi/negative case: Roll WIP di gudang tidak di hitung, barang transit ikut expected asal, dan extra tidak menurunkan angka accuracy meski result with_issues.

Arah perbaikan: Pisahkan owned/on_hand/at_location/eligible_count; gunakan satu definisi domain bersama. Tampilkan coverage tag, read recall, extra rate dan unresolved count secara terpisah.

Acceptance criteria: Matriks semua status roll diuji terhadap count eligibility. UI tidak menampilkan 100% inventori hanya dari subset tagged; extra selalu terlihat sebagai masalah.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### WM-01 — Normalisasi setelah split atomik dapat mengembalikan stok yang sudah diambil

Rujukan: [WM-01](01_TEMUAN_AUDIT_KNHOST.md#wm-01).

```text
Perbaiki WM-01 (P1): Normalisasi setelah split atomik dapat mengembalikan stok yang sudah diambil.

Status bukti audit: Risiko konkurensi dibuktikan urutan kode.

Periksa lokasi awal: backend/services/roll_service.py:490; backend/services/roll_service.py:508. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Pengurangan parent memakai atomic $inc, lalu update kedua melakukan $set dari snapshot hasil operasi pertama tanpa CAS/version. Atomic decrement kehilangan manfaat bila snapshot lama ditulis setelah split berikutnya. Jika insert_child_roll gagal, parent sudah berkurang tanpa kompensasi.

Reproduksi/negative case: Parent 100: A decrement30→snapshot 70; B decrement40→snapshot 30; B normalisasi 30; A normalisasi 70. Child total 70 + parent 70=140, padahal awal 100. Kegagalan insert child setelah decrement membuat panjang hilang. Ini trace interleaving, bukan hasil uji Mongo konkuren.

Arah perbaikan: Hapus stale normalization; gunakan integer scaled quantity atau atomic pipeline rounding. Split harus durable operation dengan parent/child conservation dan idempotent recovery; CAS/version menyertakan status dan qty.

Acceptance criteria: Parallel split30/40 dari 100 selalu total 100 parent 30; fault injection sesudah decrement/child insert pulih tanpa loss/duplicate. Jangan hanya menambah lock parent-document sales order.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### WM-02 — Reservasi parsial langsung melahirkan roll anak sebelum pemotongan fisik

Rujukan: [WM-02](01_TEMUAN_AUDIT_KNHOST.md#wm-02).

```text
Perbaiki WM-02 (P1): Reservasi parsial langsung melahirkan roll anak sebelum pemotongan fisik.

Status bukti audit: Gap SSOT fisik dari desain.

Periksa lokasi awal: backend/services/roll_service.py:490; backend/services/roll_service.py:523. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Alokasi parsial mengurangi panjang parent dan membuat child reserved saat checkout. Sebelum petugas memotong, fisik masih satu roll bertag parent tetapi data base sudah dua id entitas. insert_child_roll membersihkan tag child; tidak otomatis membuat bukti pemotongan dan pemasangan tag baru.

Reproduksi/negative case: Roll 100 di tag; SO reserve30. Data base parent 70+child 30, tag lama di fisik100. Gate/picking memerlukan child yang belum ada secara fisik.

Arah perbaikan: Pisahkan quantity reservation dari physical cut work. Child fisik hanya diposting setelah cut confirmation dengan actual length/waste/remnant dan tag/barcode anak. Alternatif reserved fragment harus jelas bukan inventory_roll fisik.

Acceptance criteria: Reserve30 belum menciptakan id entitas fisik baru. Cut 100→70+30 conservation, parent/child tags unik, child tidak boleh loading sebelum identity verification.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### WM-03 — Konfirmasi tiba dengan scan kosong memindahkan semua roll

Rujukan: [WM-03](01_TEMUAN_AUDIT_KNHOST.md#wm-03).

```text
Perbaiki WM-03 (P1): Konfirmasi tiba dengan scan kosong memindahkan semua roll.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/services/putaway_order_service.py:177; backend/services/putaway_order_service.py:180. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: None dan [] sama-sama menjadi set kosong. Kondisi if scanned gagal sehingga semua item masuk cabang arrived. Dokstring mengatakan EPC diberikan membatasi roll, tetapi explicit empty batch berarti semua diterima.

Reproduksi/negative case: PA berisi 10 roll; POST arrival dengan scanned_epcs=[]; seluruh roll berpindah ke gudang tujuan, terbit mutasi/BTG, walau nol EPC ter baca.

Arah perbaikan: Bedakan field tidak disediakan dari scan kosong. Mode scan: kosong berarti none arrived. Mode manual: aksi ter sendiri dengan permission/alasan dan item selection; no silent all.

Acceptance criteria: [] memindahkan0; subset memindahkan subset; None tidak otomatis menerima semua pada flow hardware. Override all mengharuskan reason dan jejak aktor.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### WM-04 — Putaway antar-gudang in-transit tidak mengubah bucket stok roll

Rujukan: [WM-04](01_TEMUAN_AUDIT_KNHOST.md#wm-04).

```text
Perbaiki WM-04 (P1): Putaway antar-gudang in-transit tidak mengubah bucket stok roll.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/services/putaway_order_service.py:154; backend/services/putaway_order_service.py:160. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Dispatch PA hanya mengubah status dokumen dan journey. Roll tetap available di gudang asal sampai arrival; balance/ATP berasal dari roll.status, bukan journey. Barang dalam perjalanan masih dapat dijanjikan dari lokasi asal.

Reproduksi/negative case: Dispatch roll available dari Transit ke D; baca inventory/ATP atau lakukan reservasi sebelum arrival: status fisik yang digunakan allocator masih available.

Arah perbaikan: Integrasikan movement PA dengan mesin transfer roll bersama: at_source→in_transit→at_destination, reservation blocked, ownership tetap; movement dan balance rebuild tersinkron.

Acceptance criteria: Sesudah PA dispatch ATP source berkurang, owned tidak hilang, transit terlapor; arrival hanya sekali menambah location destination; cancellation/recovery punya state eksplisit.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### WM-05 — PA dapat berebut roll dan arrival menulis lokasi tanpa prasyarat roll

Rujukan: [WM-05](01_TEMUAN_AUDIT_KNHOST.md#wm-05).

```text
Perbaiki WM-05 (P1): PA dapat berebut roll dan arrival menulis lokasi tanpa prasyarat roll.

Status bukti audit: Risiko konkurensi statis.

Periksa lokasi awal: backend/services/putaway_order_service.py:129; backend/services/putaway_order_service.py:192. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Create memeriksa journey tag_verified lalu insert PA dan set_journey tanpa claim per roll. Dua PA dapat lolos sebelum journey berubah. Arrival mengunci PA sendiri tetapi update roll hanya id, tidak cek PA yang sedang memiliki roll, asal, status atau version.

Reproduksi/negative case: PA A dan B dibuat serentak untuk roll sama ke D/H. Confirm A lalu B: doc claims berbeda tidak mencegah lokasi roll ditimpa.

Arah perbaikan: Movement ownership per roll dengan active_movement unique/atomic claim; PA create all-or-none dengan recovery; arrival CAS sesuai movement/source/owner/version.

Acceptance criteria: Dua PA satu roll: hanya satu menang; stale PA tidak dapat memindahkan roll lagi; reserved/quarantine/zero roll ditolak sesuai policy.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### WM-06 — Scan picking tidak memvalidasi identitas roll dan menerima qty negatif

Rujukan: [WM-06](01_TEMUAN_AUDIT_KNHOST.md#wm-06).

```text
Perbaiki WM-06 (P1): Scan picking tidak memvalidasi identitas roll dan menerima qty negatif.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/routers/outbound_picking.py:82; backend/routers/outbound_picking.py:112; backend/routers/outbound_picking.py:139. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Endpoint menambah qty task lalu menyimpan roll_id/bin_id/lot dari parameter tanpa memuat roll atau memastikan product/owner/warehouse/reserved_ref/bin cocok. Hanya batas atas qty dicek; actual_qty negatif tidak ditolak. CAS picked_qty sudah ada, tetapi CAS tidak memperbaiki validasi bisnis.

Reproduksi/negative case: Pick task produkA dengan roll_id produkB atau randomstring dan qty memenuhi expected; task bisa packing. Pick qty-5 menurunkan progress tanpa reversal audit.

Arah perbaikan: Scan identity server-resolved; validasi roll membership/status/bin/owner serta unit; qty finite>0; koreksi negative via undo event terpisah. Tasks per roll atau manifest yang jelas.

Acceptance criteria: Salah SKU/bin/gudang/owner/EPC atau roll tidak allocated ditolak. Negative/NaN/inf/zero ditolak; concurrent good scans tetap tidak hilang.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### WM-07 — Stock opname per bin memakai expected seluruh gudang dan membolehkan duplikasi

Rujukan: [WM-07](01_TEMUAN_AUDIT_KNHOST.md#wm-07).

```text
Perbaiki WM-07 (P1): Stock opname per bin memakai expected seluruh gudang dan membolehkan duplikasi.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/routers/cycle_count.py:119; backend/routers/cycle_count.py:117; backend/routers/cycle_count.py:36. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Bin disimpan sebagai metadata tetapi expected diperoleh dari inventory_balances produk×warehouse×owner, tanpa bin. Item sama dapat ditambahkan berkali-kali; actual_qty tidak punya ge=0. Discrepancy kemudian diterapkan perbaris.

Reproduksi/negative case: Warehouse100 dengan binA40/binB60; hitung binA aktual 40, expected 100 menghasilkan shortage60 palsu. Dua item identik dengan expected 100/actual 90 masing-masing dapat menerapkan -10 dua kali. Nilai actual negatif juga diterima schema.

Arah perbaikan: Snapshot count scope dari rolls perbin/owner; unique count key, freeze/version & blind count policy; validasi nonnegative finite quantity. Jangan mengulang discrepancy agregat perbin.

Acceptance criteria: BinA40 menghasilkan diff0; duplicate count key409; negative/NaN ditolak. Approve dua bin menghitung perbin tanpa double reduction.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### WM-08 — Adjustment shortage dapat parsial tetapi sesi tetap approved

Rujukan: [WM-08](01_TEMUAN_AUDIT_KNHOST.md#wm-08).

```text
Perbaiki WM-08 (P1): Adjustment shortage dapat parsial tetapi sesi tetap approved.

Status bukti audit: Terbukti statis; konkurensi belum dieksekusi.

Periksa lokasi awal: backend/services/roll_service.py:1602; backend/routers/cycle_count.py:231. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Helper shortage mengurangi roll dengan read→set tanpa CAS; kandidat status tidak mencakup semua bucket fisik yang membentuk on_hand. Kekurangan residual hanya warning dan return jumlah aktual; approve mengabaikan return dan menandai seluruh sesi approved.

Reproduksi/negative case: Expected mencakup picked/packed tetapi shortage hanya memiliki cukup available/reserved sebagian. Adjustment yang berhasil kurang dari discrepancy, namun dokumen menyatakan approved. Reservation simultan dapat ditimpa.

Arah perbaikan: Adjustment by roll/count line dengan CAS dan target lengkap; periksa actual_applied==requested, durable recovery; selisih yang belum diterapkan tetap exception. Setiap stock status punya policy terpusat.

Acceptance criteria: Tidak cukup eligible stock harus fail/exception tanpa approve palsu. Parallel count vs reservation tidak over write. Detail tampil requested/applied/unresolved per line.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### WM-09 — Penerimaan exception PA tidak menulis mutasi transfer

Rujukan: [WM-09](01_TEMUAN_AUDIT_KNHOST.md#wm-09).

```text
Perbaiki WM-09 (P2): Penerimaan exception PA tidak menulis mutasi transfer.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/services/putaway_order_service.py:228. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Resolve accept memindahkan warehouse roll/tag dan rebuild balance, tetapi tidak menulis inventory_movements seperti confirm_arrival. Jalur alternatif menghasilkan perubahan fisik yang tidak ada di ledger movement.

Reproduksi/negative case: Arrival missed satu roll; manager accept exception. Lokasi dan balance berubah tetapi history transfer out/in untuk roll itu tidak muncul.

Arah perbaikan: Gunakan posting movement tunggal yang sama untuk arrival normal/exception; reference PA/BTG, override reason, qty snapshot dan actor; update counters dari hasil nyata.

Acceptance criteria: Accept exception menulis tepat satu out/in pasangan, rebuild dua lokasi dan counters; retry tidak menggandakan mutasi.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-01 — Landed cost menghitung anak split dua kali

Rujukan: [FN-01](01_TEMUAN_AUDIT_KNHOST.md#fn-01).

```text
Perbaiki FN-01 (P1): Landed cost menghitung anak split dua kali.

Status bukti audit: Direproduksi.

Periksa lokasi awal: backend/services/landed_cost_service.py:62; backend/services/landed_cost_service.py:159; backend/services/landed_cost_service.py:173. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Target PO dapat berisi parent dan child yang mewarisi acquired.ref_id. Apply parent mempropagasi per_unit ke anak; loop kemudian melakukan increment langsung anak tanpa guard landed_cost_refs. Guard hanya ada pada update_many descendant.

Reproduksi/negative case: FN-01: parent 70 dan child 30, unit_cost10, voucher100 basis qty. Alokasi70/30 (per unit 1) tetapi parent+1, child+2; nilai stok naik130. Reproduksi menjalankan compute/apply asli dengan DB mock.

Arah perbaikan: Pilih target ekonomi disjoint: semua physical fragments tanpa propagate, atau root-level propagate yang tidak dibilling ulang. Per-voucher per roll idempotency dan conservation nilai; rekonsiliasi voucher→rolls→GL.

Acceptance criteria: Parent 70+child 30 voucher100 menghasilkan nilai+100; multiple levels, roll sold, partial/scrapped, retry dan order loop berbeda tidak mengubah hasil.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-02 — 3-way match lolos overbilling dari baris produk duplikat

Rujukan: [FN-02](01_TEMUAN_AUDIT_KNHOST.md#fn-02).

```text
Perbaiki FN-02 (P1): 3-way match lolos overbilling dari baris produk duplikat.

Status bukti audit: Direproduksi.

Periksa lokasi awal: backend/services/vendor_bill_service.py:78; backend/services/vendor_bill_service.py:73; backend/routers/vendor_bills.py:204. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Setiap baris membandingkan qty dengan received-prior yang sama; qty baris sebelumnya pada bill ini tidak diakumulasikan. Router/schema tidak menolak duplicate product lines pada flow create yang diperiksa. PO mapping byproduct juga menghilangkan id entitas line PO.

Reproduksi/negative case: FN-02: receipt 100, prior 0, dua billed60 pada produk sama, toleransi0; match_status matched walau total 120. Satu billed120 berhasil diblok sebagai kontrol pembanding.

Arah perbaikan: Cocokkan PO line ID dan receipt line; aggregate current bill+posted prior+concurrent pending reservations. Duplicate explicit ditolak atau di jumlah konsisten; submit/approve revalidasi atomik.

Acceptance criteria: 60+60 vs100 blocked; PO produk sama dua harga tidak over write; dua bill bersamaan tidak melewati receipt cap. Credit note/cancel mengembalikan billable sesuai policy.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-03 — WAC menjumlah panjang dan cost lintas unit tanpa konversi

Rujukan: [FN-03](01_TEMUAN_AUDIT_KNHOST.md#fn-03).

```text
Perbaiki FN-03 (P1): WAC menjumlah panjang dan cost lintas unit tanpa konversi.

Status bukti audit: Direproduksi.

Periksa lokasi awal: backend/services/costing_service.py:70; backend/services/costing_service.py:74. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: wac_for_product menghitung total raw length_remaining lalu total_value/raw length tanpa membaca roll.unit. Hasil diberi base_unit produk sehingga yard dan meter seolah unit sama. Valuation cost per roll dapat benar sendiri; kesalahan muncul denominator dan cost per base.

Reproduksi/negative case: FN-03: 1yard cost 91.44/yard dan1meter cost 100/m, keduanya100/m. Fungsi mengembalikan qty2 dan WAC 95.72; benar qty 1.9144m dan WAC 100/m.

Arah perbaikan: Normalize quantity ke base unit memakai satu resolver konversi; nilai tetap qty_native×cost_native. Snapshot conversion di transaksi; missing/invalid conversion hard exception, jangan penjumlahan raw.

Acceptance criteria: Mixed meter/yard/kg sesuai konversi produk menghasilkan nilai/qtybase yang benar; unknown conversion tidak dianggap1. Pembagian dan rounding diuji pada partial roll.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-04 — Arus kas seimbang tetapi klasifikasi transaksi nonkas salah

Rujukan: [FN-04](01_TEMUAN_AUDIT_KNHOST.md#fn-04).

```text
Perbaiki FN-04 (P1): Arus kas seimbang tetapi klasifikasi transaksi nonkas salah.

Status bukti audit: Direproduksi dua skenario.

Periksa lokasi awal: backend/services/cash_flow_service.py:61; backend/services/cash_flow_service.py:75. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Laporan membagi perubahan saldo semua akun nonkas berdasarkan prefix. Id entitas neraca menjamin total delta kas, tetapi tidak mengidentifikasi apakah transaksi benar-benar kas atau nonkas. Penyusutan, reclass dan beli aset kredit salah ditempatkan; cash codes juga fixed dua akun.

Reproduksi/negative case: FN-04: Dr beban100/Cr akumulasi penyusutan100 → CFO-100 CFI+100, reconciled true; seharusnya keduanya0. FN-04B: beli aset kredit100 → CFO+100 CFI-100, padahal tanpa arus kas.

Arah perbaikan: Bangun noncash adjustments dan business classification berbasis journal/source/account metadata; exclude noncash investing/financing dan disclose; cash equivalence tidak hardcoded prefix semata.

Acceptance criteria: Depresiasi/beli aset kredit/reclass/landed accrual memberi nol cashflow; actual cash asset purchase masuk CFI; accrual sale+receipt CFO benar; angka diverifikasi fixture akuntan. Acuan IAS7 tercantum di fit-gap.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-05 — Master akun laporan menggabungkan override entitas dengan last-write-wins

Rujukan: [FN-05](01_TEMUAN_AUDIT_KNHOST.md#fn-05).

```text
Perbaiki FN-05 (P1): Master akun laporan menggabungkan override entitas dengan last-write-wins.

Status bukti audit: Direproduksi.

Periksa lokasi awal: backend/services/financial_statement_service.py:41; backend/services/financial_statement_service.py:42. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Scope journal sudah dipisahkan, tetapi _accounts_map membaca seluruh COA dan key hanya code. Override kode sama entitas B dapat menjadi nama/type laporan A, tergantung urutan cursor. Scope laporan tidak diteruskan ke resolver akun.

Reproduksi/negative case: FN-05: kode 4-1000 A income, B expense; map menghasilkan B sehingga revenue A bisa masuk expense. Bahkan jika konfigurasi hanya mengganti nama, nama badan usaha lain tetap digunakan.

Arah perbaikan: Resolve effective COA per entity: global default + exact entity override; enforce invariant type/code bila override dibatasi. Consolidation agregasi account dimension eksplisit.

Acceptance criteria: Laporan A selalu memakai akun A/global; urutan insert tidak mengubah hasil; kode custom hanya A tidak mengubah B; consolidation tidak mengambil random override.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-06 — Jurnal manual menolak akun custom entitas dan mengabaikan override

Rujukan: [FN-06](01_TEMUAN_AUDIT_KNHOST.md#fn-06).

```text
Perbaiki FN-06 (P2): Jurnal manual menolak akun custom entitas dan mengabaikan override.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/services/gl_service.py:567. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: create_manual_entry memuat hanya akun global meski master mendukung akun per entitas. Akun valid milik entitas dipilih di UI dapat ditolak; override inactive/header badan usaha juga tidak diperiksa jika global tetap active/postable.

Reproduksi/negative case: Buat akun custom khususA lalu post manual: akun tidak ditemukan. Override global account A inactive dapat tetap diposting memakai record global.

Arah perbaikan: Gunakan resolver akun effective yang sama untuk list, manual, auto post dan reports; validasi active/postable/type sebelum entry.

Acceptance criteria: Custom A berhasil di A, ditolak B; inactive override menghalangi post; global default bekerja saat tidak ada override.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-07 — Kas manual tidak langsung berjurnal dan void kas tidak membalik jurnal

Rujukan: [FN-07](01_TEMUAN_AUDIT_KNHOST.md#fn-07).

```text
Perbaiki FN-07 (P1): Kas manual tidak langsung berjurnal dan void kas tidak membalik jurnal.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/routers/cash.py:108; backend/routers/cash.py:156. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Create kas menyimpan cash_transactions tanpa posting GL pada jalur itu. Backfill/sync dapat membuat jurnal kemudian, tetapi void kas hanya mengubah status transaksi. Void generic juga perlu membedakan transaksi berasal dari receipt/AP agar subledger sumber tidak ditinggal aktif.

Reproduksi/negative case: Input kas masuk100 → dashboard kas naik tetapi GL kas belum naik sampai sync. Setelah sync, void kas → dashboardturun sedangkan JE tetap aktif. Jalur backfill bukan reversal.

Arah perbaikan: Posting journal+cash sebagai satu durable operation; void sumber harus reversal jurnal dan unwind sumber sesuai lifecycle. Cash autogenerated hanya dibatalkan melalui dokumen asal; no generic source bypass.

Acceptance criteria: Create/void manual dan receipt/AP derived diuji cashledger=GL sesudah setiap aksi, retry/failure dan periode tertutup. Sync tidak melahirkan double posting/revive void.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-08 — Opening balance rekening dan perubahan rekening tidak tersambung GL

Rujukan: [FN-08](01_TEMUAN_AUDIT_KNHOST.md#fn-08).

```text
Perbaiki FN-08 (P1): Opening balance rekening dan perubahan rekening tidak tersambung GL.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/services/bank_service.py:78; backend/services/bank_service.py:94. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Saldo awal rekening disimpan sebagai field yang dipakai menghitung saldo berjalan. Create/update opening_balance tidak membuat jurnal pembukaan atau koreksi, sehingga buku rekening dan GL dapat memakai basis awal yang berbeda.

Reproduksi/negative case: Buat rekening dengan saldo awal Rp1 juta: ledger rekening bertambah, tetapi operasi ini tidak menambah GL. Ubah menjadi Rp2 juta: saldo historis rekening bergeser tanpa jurnal perubahan.

Arah perbaikan: Pembukaan rekening harus terikat jurnal, tanggal, pemetaan akun dan entitas. Kunci saldo awal setelah posting; koreksi melalui adjustment/reversal berizin. Periksa juga account_id pada penerimaan/pembayaran agar masuk rekening yang benar.

Acceptance criteria: Saldo awal rekening sesuai GL; edit historis tidak diam-diam mengubah saldo. Transfer mempunyai dua sisi, dan penerimaan AR/AP muncul pada ledger rekening yang sesuai.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-09 — Void jurnal manual melewati penguncian periode

Rujukan: [FN-09](01_TEMUAN_AUDIT_KNHOST.md#fn-09).

```text
Perbaiki FN-09 (P1): Void jurnal manual melewati penguncian periode.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/services/gl_service.py:673; backend/services/gl_service.py:687. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Posting memanggil enforce_closed_period_guard, tetapi void_entry tidak. Menandai closing stale setelah void tidak menggantikan izin membuka periode. Route void yang diperiksa juga tidak menjalankan guard periode sendiri.

Reproduksi/negative case: Tutup bulan yang berisi jurnal manual, lalu void jurnal bulan tersebut menggunakan izin accounting manage tanpa unlock. Saldo laporan berubah walaupun periode masih tertutup.

Arah perbaikan: Terapkan kebijakan periode yang sama pada void/reversal. Untuk periode terkunci, utamakan reversal pada periode berjalan sesuai kebijakan buku. Pembukaan periode memerlukan hak, alasan dan audit; mutation status/source memakai CAS.

Acceptance criteria: Periode tertutup tidak berubah melalui void tanpa otorisasi unlock. Reversal periode berjalan mempertahankan jurnal asli dan jejak pembatalannya.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-10 — Pembayaran AR dapat sukses walau jurnal kas gagal

Rujukan: [FN-10](01_TEMUAN_AUDIT_KNHOST.md#fn-10).

```text
Perbaiki FN-10 (P1): Pembayaran AR dapat sukses walau jurnal kas gagal.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/services/ar_receipt_service.py:71; backend/services/ar_receipt_service.py:106. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: _post_cash_in memasukkan transaksi kas lalu mencoba posting GL dalam try/except yang mengabaikan kegagalan. Receipt dan alokasi pesanan dapat terlanjur berubah ketika GL ditolak. Tidak terlihat outbox posting durable pada fungsi tersebut.

Reproduksi/negative case: Buat gl.post_cash_transaction melempar error: receipt/kas dapat tetap dibuat sementara GL belum mencatat kas. Sync mungkin memperbaiki kemudian, tetapi fungsi ini tidak memberikan jaminan penyelesaian atau status pending yang dapat dipantau.

Arah perbaikan: Gunakan operasi bisnis atomik atau saga durable dengan posting outbox dan status pending/failed. Preflight periode dan gunakan compensation yang aman; kegagalan finansial tidak boleh ditampilkan sebagai sukses final.

Acceptance criteria: Kegagalan GL menghasilkan status pending/failed yang terlihat atau rollback konsisten. Retry tidak menggandakan jurnal, dan receipt belum final sebelum posting wajib selesai.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-11 — HPP per shipment memakai rata-rata semua roll pesanan

Rujukan: [FN-11](01_TEMUAN_AUDIT_KNHOST.md#fn-11).

```text
Perbaiki FN-11 (P1): HPP per shipment memakai rata-rata semua roll pesanan.

Status bukti audit: Terbukti statis; angka contoh deterministik.

Periksa lokasi awal: backend/services/gl_service.py:992; backend/services/gl_service.py:1070. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: post_shipment_cogs memakai _order_item_unit_cost untuk baris pesanan, yang merata-ratakan roll milik order. Ia tidak mengambil snapshot biaya roll pada shipment aktual. Unit biaya juga harus sesuai unit kuantitas shipment.

Reproduksi/negative case: Pesanan memiliki dua roll masing-masing 100 meter, dengan biaya 10 dan 30 per meter. Shipment pertama hanya membawa roll murah: rata-rata 20 menghasilkan HPP 2.000, sedangkan biaya roll keluar 1.000. Total dua shipment mungkin akhirnya sama, tetapi margin/periode masing-masing salah.

Arah perbaikan: Simpan alokasi shipment per roll, jumlah dalam unit asal/base, serta biaya yang dibekukan saat dispatch. Jurnal berasal dari jumlah extended cost aktual. Koreksi landed cost setelah shipment mengikuti kebijakan variance eksplisit.

Acceptance criteria: Shipment roll murah mencatat HPP 1.000 dan shipment roll mahal 3.000. Edit biaya roll tidak mengubah laporan historis tanpa event koreksi. Partial roll, mixed UOM dan retur mengacu snapshot yang sama.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-12 — Edit master aset mengubah nilai/akun tanpa mengoreksi jurnal perolehan

Rujukan: [FN-12](01_TEMUAN_AUDIT_KNHOST.md#fn-12).

```text
Perbaiki FN-12 (P1): Edit master aset mengubah nilai/akun tanpa mengoreksi jurnal perolehan.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/services/fixed_asset_service.py:141. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: update_asset mengizinkan perubahan field finansial tertentu tanpa menyelaraskan jurnal perolehan yang sudah ada. Pembatasan saat depresiasi bukan pengganti amendment terhadap financial event perolehan.

Reproduksi/negative case: Aset sudah diperoleh dengan nilai 100, belum didepresiasi. Ubah nilai menjadi 150 atau akun aset: kartu/basis depresiasi berubah, tetapi jurnal perolehan tetap 100 pada akun lama.

Arah perbaikan: Kunci field finansial setelah kapitalisasi. Perubahan memakai amendment/reclassification/reversal yang berizin dan mematuhi periode; edit nonfinansial tetap dapat dilakukan biasa.

Acceptance criteria: Nilai perolehan dan akumulasi depresiasi pada register sesuai GL. Edit biaya/tanggal/akun yang diizinkan menghasilkan jurnal koreksi yang benar atau ditolak dengan alasan jelas.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-13 — Close periode dapat berjalan dua kali secara bersamaan

Rujukan: [FN-13](01_TEMUAN_AUDIT_KNHOST.md#fn-13).

```text
Perbaiki FN-13 (P1): Close periode dapat berjalan dua kali secara bersamaan.

Status bukti audit: Risiko konkurensi statis.

Periksa lokasi awal: backend/services/closing_service.py:253; backend/services/closing_service.py:270; backend/services/closing_service.py:312. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: close_period mengecek penutupan sebelumnya, kemudian membuat jurnal dan record tanpa claim atomik atas periode. Unique source jurnal tidak cukup karena setiap panggilan membuat closing_id baru. Bootstrap yang diperiksa tidak menetapkan unique logical closing key.

Reproduksi/negative case: Dua request bersamaan melihat periode belum ditutup dan laba yang sama. Keduanya dapat membuat jurnal penutup laba 100 sehingga laba ditahan dipindah 200. Ini interleaving dari source, belum uji konkurensi Mongo.

Arah perbaikan: Gunakan operation key durable berdasarkan entitas, tipe dan periode, policy overlap bulan/tahun, CAS lifecycle/revision dan source jurnal idempotent. Pulihkan failure antara posting jurnal dan penyimpanan closing record.

Acceptance criteria: Parallel close/reclose dan overlap bulan/tahun hanya menghasilkan satu revision sah. Failure injection tidak meninggalkan jurnal orphan/ganda; reopen mengikuti prosedur pemulihan yang tervalidasi.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-14 — Stock opname tidak memposting variance GL dan surplus dibuat tanpa cost

Rujukan: [FN-14](01_TEMUAN_AUDIT_KNHOST.md#fn-14).

```text
Perbaiki FN-14 (P1): Stock opname tidak memposting variance GL dan surplus dibuat tanpa cost.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/services/roll_service.py:1602; backend/routers/cycle_count.py:224. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Approval opname mengubah roll dan rebuild balance tanpa jurnal selisih stok. Surplus yang dibuat lewat create_inbound_roll tidak diberi unit_cost sehingga menjadi stok bernilai nol. Opening-equity true-up bukan pengganti klasifikasi selisih operasional.

Reproduksi/negative case: Shortage 10 meter pada biaya 100 mengurangi subledger 1.000 tetapi GL inventory tetap. Surplus 10 meter menambah kuantitas tanpa valuation yang jelas.

Arah perbaikan: Tetapkan valuation policy per selisih yang disetujui pemilik buku. Kekurangan umumnya mengurangi inventory dan mencatat stock loss; surplus mengikuti klasifikasi kebijakan. Wajib ada snapshot biaya, reason dan tautan jurnal.

Acceptance criteria: Setiap adjustment mempunyai nilai dan jurnal yang sesuai serta dapat direkonsiliasi. Zero cost memerlukan alasan/override eksplisit; shortage roll reserved/picked tidak diam-diam merusak pesanan.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-15 — Helper autopost tidak menegakkan invariant jurnal di pintu insert

Rujukan: [FN-15](01_TEMUAN_AUDIT_KNHOST.md#fn-15).

```text
Perbaiki FN-15 (P2): Helper autopost tidak menegakkan invariant jurnal di pintu insert.

Status bukti audit: Kelemahan kontrol statis.

Periksa lokasi awal: backend/services/gl_service.py:503; backend/services/gl_service.py:508. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: _insert_entry menormalisasi angka lalu menulis posted tanpa menolak debit/kredit yang berbeda, angka nonfinite, negatif atau akun yang tidak layak posting. Setiap caller diminta menjaga sendiri. Ini kelemahan pintu kontrol, bukan bukti seluruh autopost saat ini tidak seimbang.

Reproduksi/negative case: Caller baru atau edge case mengirim baris tidak seimbang: helper tetap dapat posting jika guard periode lolos. Keamanan ledger tidak seharusnya bergantung pada komentar tanggung jawab caller.

Arah perbaikan: Gunakan validator pusat dengan Decimal/scaled amount, equality setelah rounding, resolusi akun effective, tanggal/entitas/periode serta source identity. Tambahkan fixture bermakna pada setiap jenis autopost.

Acceptance criteria: Jurnal tidak seimbang, NaN/Infinity, angka negatif yang tidak sesuai model, akun hilang/inactive/nonpostable dan baris dual-sided ditolak sebelum insert. Posting valid tetap menghasilkan total yang tepat.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### FN-16 — Neraca default tidak membatasi tanggal meski diberi label hari ini

Rujukan: [FN-16](01_TEMUAN_AUDIT_KNHOST.md#fn-16).

```text
Perbaiki FN-16 (P2): Neraca default tidak membatasi tanggal meski diberi label hari ini.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/services/financial_statement_service.py:174. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Saat as_of tidak diberikan, filter tanggal tidak dipasang pada aggregate; respons memakai tanggal sekarang sebagai label as_of. Jurnal bertanggal masa depan dapat masuk neraca yang terlihat berlaku hari ini. Format tanggal/timezone juga harus konsisten.

Reproduksi/negative case: Tambahkan jurnal bulan depan lalu buka neraca tanpa as_of. Query tanpa cutoff dapat memasukkannya, sedangkan permintaan dengan tanggal hari ini mengecualikannya.

Arah perbaikan: Resolve effective_as_of sekali dan gunakan pada filter serta label. Validasi tanggal jurnal dengan format/timezone yang jelas; dokumentasikan default laporan finansial secara konsisten.

Acceptance criteria: Jurnal masa depan tidak masuk neraca default hari ini, tetapi masuk bila as_of memang masa depan. Uji batas akhir hari/timezone; label tanggal sama dengan cutoff query.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-01 — Idempotency tidak terikat user cookie, entitas dan payload

Rujukan: [GN-01](01_TEMUAN_AUDIT_KNHOST.md#gn-01).

```text
Perbaiki GN-01 (P1): Idempotency tidak terikat user cookie, entitas dan payload.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/idempotency.py:32; backend/dependencies.py:9; backend/idempotency.py:33. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Middleware membaca cookie kn_session, sementara autentikasi memakai session_token. Pengguna cookie tanpa Authorization mempunyai who kosong yang sama. Kunci tidak memuat entitas atau hash payload, dan respons cache dikembalikan sebelum autentikasi endpoint berjalan.

Reproduksi/negative case: User A menyimpan respons untuk key K dan path P. User B yang memakai cookie dengan key/path sama dapat menerima respons A; caller yang mengetahui key juga dapat mencoba replay tanpa autentikasi ulang. Mengganti entitas atau isi request dengan key sama tidak menghasilkan validasi mismatch. UUID acak mengurangi tabrakan kebetulan, tetapi tidak memperbaiki isolasi.

Arah perbaikan: Autentikasi harus berjalan sebelum lookup. Ikat kunci pada user ID stabil, entitas yang diizinkan, metode, path dan payload hash. Payload berbeda harus 409. Simpan hasil pemulihan operasi secara durable; jangan menggunakan potongan token sebagai identitas.

Acceptance criteria: Key sama pada dua user/entitas tidak berbagi respons; replay tanpa login ditolak; payload berbeda 409; retry sah tidak menggandakan efek walaupun proses sempat mati.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-02 — WebSocket GPS dapat dilanggan user biasa dan mengabaikan expiry/scope

Rujukan: [GN-02](01_TEMUAN_AUDIT_KNHOST.md#gn-02).

```text
Perbaiki GN-02 (P1): WebSocket GPS dapat dilanggan user biasa dan mengabaikan expiry/scope.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/server.py:294; backend/services/tracking_service.py:61; backend/services/tracking_service.py:41. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: mode=subscribe mengalahkan pemeriksaan is_manager. auth_ws_token hanya mencari sesi dan user aktif tanpa expires_at, berbeda dari autentikasi HTTP. Snapshot dan broadcast TrackManager juga tidak menyaring entitas penerima.

Reproduksi/negative case: User biasa memilih mode subscribe dan menerima lokasi semua karyawan. Token kedaluwarsa yang belum dibersihkan TTL masih diterima. Manager yang hanya ditugaskan ke A menerima posisi B karena subscriber tidak mempunyai scope.

Arah perbaikan: Pakai validasi sesi bersama untuk HTTP/WS, permission tracking khusus dan scope per subscriber. Saring snapshot/broadcast, periksa expiry/revocation dan tutup koneksi yang tidak lagi sah. Hindari token sesi panjang di URL/log.

Acceptance criteria: User sales tidak dapat subscribe; token expired ditolak meski record masih ada; manager A hanya menerima A; pencabutan akses menghentikan koneksi dan event baru.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-03 — Ledger rekening dan reconcile kas berdasarkan ID tidak memeriksa entitas dokumen

Rujukan: [GN-03](01_TEMUAN_AUDIT_KNHOST.md#gn-03).

```text
Perbaiki GN-03 (P1): Ledger rekening dan reconcile kas berdasarkan ID tidak memeriksa entitas dokumen.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/routers/bank.py:82; backend/routers/bank.py:92. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: List dan patch rekening mempunyai scope/guard_doc, tetapi ledger rekening serta reconcile kas hanya memeriksa permission lalu memuat arbitrary ID. current_user memvalidasi entitas pada header/body; ia tidak otomatis memvalidasi pemilik setiap dokumen yang dicari lewat ID.

Reproduksi/negative case: User yang boleh mengelola kas A mengetahui account_id/txn_id B lalu meminta ledger atau reconcile. Payload reconciled tidak menyebut entitas B, sehingga penjaga entity pada body tidak mencegah akses ini.

Arah perbaikan: Muat dokumen dan guard entitas sebelum service dipanggil. Ambil entity dari record, bukan dari input. Rekening legacy shared mengikuti kebijakan migrasi eksplisit.

Acceptance criteria: User A ditolak pada ledger/reconcile milik B; admin lintas entitas mengikuti izin eksplisit; ID yang ditebak tidak membocorkan nomor rekening atau saldo.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-04 — R&D dapat mengambil bahan dari roll badan usaha lain

Rujukan: [GN-04](01_TEMUAN_AUDIT_KNHOST.md#gn-04).

```text
Perbaiki GN-04 (P1): R&D dapat mengambil bahan dari roll badan usaha lain.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/routers/rnd.py:318; backend/services/rnd_sample_service.py:1188. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Route R&D mengamankan sample, tetapi tidak mengamankan roll bahan. issue_material mencari roll dari payload.roll_id dan memeriksa status/panjang tanpa membandingkan owner roll dengan entitas sample atau scope pengguna. CAS roll menjaga konkurensi, bukan otorisasi.

Reproduksi/negative case: User R&D A pada sample A memasukkan roll available milik B. Stok B berkurang dan beban dapat diposting ke B, sementara material issue ditautkan ke sample A. Payload roll_id tidak memicu body entity guard.

Arah perbaikan: Validasi owner roll terhadap sample dan user context sebelum mutasi. Penggunaan material lintas entitas harus melalui intercompany yang disahkan. Validasi produk/gudang/unit sesuai kebutuhan sample.

Acceptance criteria: Sample A tidak dapat mengurangi roll B sebelum movement/JE apa pun; transfer ownership yang sah memungkinkan pemakaian; material A untuk sample A tetap berfungsi.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-05 — Rollback pengambilan bahan R&D dapat menimpa pemakaian roll lain

Rujukan: [GN-05](01_TEMUAN_AUDIT_KNHOST.md#gn-05).

```text
Perbaiki GN-05 (P1): Rollback pengambilan bahan R&D dapat menimpa pemakaian roll lain.

Status bukti audit: Risiko konkurensi statis.

Periksa lokasi awal: backend/services/rnd_sample_service.py:1246. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Pengambilan awal memakai CAS yang baik. Tetapi bila GL gagal, rollback melakukan $set ke panjang/status awal tanpa version guard. Transaksi lain bisa sudah memakai sisa roll sebelum kompensasi tersebut dijalankan.

Reproduksi/negative case: Roll100: issue A10 membuat90; issue B20 sukses membuat70; posting GL A gagal, lalu rollback A mengembalikan panjang100. Pemakaian B hilang dari stok walaupun movement dan JE B masih ada.

Arah perbaikan: Gunakan operation/version dan kompensasi yang hanya membalik kontribusi A. Klaim/fencing harus mencakup posting dan pemulihan; status serta balance dihitung dari hasil yang konsisten.

Acceptance criteria: GL A gagal bersamaan dengan B sukses menghasilkan panjang80, bukan100/90; rollback tidak menimpa status/ref operasi lain; pemulihan ulang tidak menambah stok lagi.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-06 — Produksi menyelesaikan WO tanpa claim dan memakai BOM terbaru

Rujukan: [GN-06](01_TEMUAN_AUDIT_KNHOST.md#gn-06).

```text
Perbaiki GN-06 (P1): Produksi menyelesaikan WO tanpa claim dan memakai BOM terbaru.

Status bukti audit: Terbukti statis; konkurensi belum DB test.

Periksa lokasi awal: backend/services/production_service.py:358; backend/services/production_service.py:278; backend/services/production_service.py:339. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: complete_work_order tidak mengklaim WO; konsumsi bahan melakukan read lalu set roll tanpa CAS. Pemeriksaan available sebelumnya tidak atomik. Draft juga bisa diselesaikan. Bahan diambil dari BOM terbaru, bukan revision/material plan yang dibekukan saat WO dibuat atau dirilis.

Reproduksi/negative case: Dua complete WO yang sama dapat membuat dua output. Dua WO berbeda bisa membaca dan mengonsumsi stok100 yang sama. Edit BOM setelah release mengubah bahan yang dipakai WO lama; kegagalan pada bahan kedua dapat meninggalkan konsumsi bahan pertama.

Arah perbaikan: Bekukan BOM revision dan material plan pada WO. Klaim WO, reservasi/CAS bahan dan gunakan tahapan durable consume→output→JE. Validasi jumlah aktual yang diterapkan serta yield/waste; draft harus mengikuti release policy.

Acceptance criteria: Complete bersamaan hanya membuat satu output; dua WO tidak memakai qty yang sama; draft tidak langsung selesai; perubahan BOM tidak mengubah WO released; fault setiap tahap dapat dipulihkan.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-07 — Retur supplier mengurangi roll dengan read-set dan partial return kehilangan identitas fisik

Rujukan: [GN-07](01_TEMUAN_AUDIT_KNHOST.md#gn-07).

```text
Perbaiki GN-07 (P1): Retur supplier mengurangi roll dengan read-set dan partial return kehilangan identitas fisik.

Status bukti audit: Risiko konkurensi dan gap traceability statis.

Periksa lokasi awal: backend/services/purchase_return_service.py:621; backend/services/purchase_return_service.py:663. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Konsumsi roll untuk retur supplier memakai update berdasarkan ID setelah read, tanpa prasyarat status/panjang. Partial return hanya mengurangi parent tanpa membuat identitas fisik potongan retur. Helper specific juga tidak menyaring owner/status; validasi caller harus dibuktikan pada semua jalur.

Reproduksi/negative case: Reservation atau penjualan bersamaan dapat ditimpa retur. Retur30 dari roll100 mencatat keluar30 tetapi tag parent tetap pada sisa70; potongan30 yang dikirim tidak mempunyai roll retur baru. Ini bukan klaim bahwa seluruh caller sudah terbukti menembus owner.

Arah perbaikan: Gunakan core consume/split dengan CAS, konversi unit, owner/status dan provenance supplier yang wajib. Buat identitas child fisik retur serta tag/barcode; pastikan actual_applied sama dengan requested.

Acceptance criteria: Retur bersamaan dengan sale tidak mengonsumsi dua kali; parent70 dan child retur30 terpisah; mixed UOM benar; roll wrong-owner ditolak di semua entrypoint.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-08 — Konversi permintaan internal dapat melahirkan transaksi antar-PT ganda

Rujukan: [GN-08](01_TEMUAN_AUDIT_KNHOST.md#gn-08).

```text
Perbaiki GN-08 (P1): Konversi permintaan internal dapat melahirkan transaksi antar-PT ganda.

Status bukti audit: Risiko konkurensi statis.

Periksa lokasi awal: backend/services/internal_request_service.py:415; backend/services/internal_request_service.py:427. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: convert membaca request open, membuat pair intercompany, kemudian menulis converted. Tidak ada claim pada request atau unique logical conversion key. source_request_id disimpan tetapi tidak digunakan untuk dedup creation pada flow yang diperiksa.

Reproduksi/negative case: Dua convert bersamaan dari request yang sama masing-masing membuat pair seller/buyer. Request hanya menyimpan pair yang terakhir ditulis.

Arah perbaikan: Klaim request sebelum create pair; gunakan key source request+revision untuk operasi conversion. Retry memuat pair existing. Partial pair creation harus dapat dilanjutkan atau dikompensasi dengan benar.

Acceptance criteria: Convert paralel menghasilkan satu pair; cancel vs convert tidak saling menimpa; fault setelah create sebelum update request melanjutkan pair yang sama.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-09 — CRM mengamankan owner sales tetapi tidak entitas pada operasi berdasarkan ID

Rujukan: [GN-09](01_TEMUAN_AUDIT_KNHOST.md#gn-09).

```text
Perbaiki GN-09 (P1): CRM mengamankan owner sales tetapi tidak entitas pada operasi berdasarkan ID.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/routers/crm_omnichannel.py:126; backend/services/crm_omnichannel_service.py:148. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: _guard_lead_owner memeriksa kepemilikan hanya untuk role sales, tanpa assert entity. Custom role dengan customer.create/update dapat memutasi lead entitas lain melalui ID. Convert ke existing_customer_id juga tidak memeriksa kesamaan entity customer dan lead; delete interaction mempunyai pola serupa.

Reproduksi/negative case: User A dengan custom permission mengirim patch/convert/delete lead B. Lead A dapat ditautkan ke customer B meski tidak ada kebijakan hubungan lintas entitas yang membenarkannya.

Arah perbaikan: Guard entity dan row ownership pada seluruh aksi ID; validasi referenced customer. Turunkan scope dari context server. Jangan menjadikan nama role sales satu-satunya aturan row access.

Acceptance criteria: A tidak memutasi B melalui ID; perpindahan entity/ownership mencabut akses lama; konversi customer beda entity ditolak; admin mengikuti policy eksplisit.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-10 — Rekomendasi POS memakai entity query tanpa resolusi izin dan stok global

Rujukan: [GN-10](01_TEMUAN_AUDIT_KNHOST.md#gn-10).

```text
Perbaiki GN-10 (P2): Rekomendasi POS memakai entity query tanpa resolusi izin dan stok global.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/routers/pos.py:20; backend/services/pos_recommendation_service.py:15; backend/services/pos_recommendation_service.py:26. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Route rekomendasi POS mempunyai permission order.view, tetapi entity_id query tidak diresolusikan melalui entity_ctx/resolve_scope_ids. Tanpa entity, service membaca semua order. Enrichment stok/substitute memakai product_summary global tanpa owner scope.

Reproduksi/negative case: User A meminta entity B, all atau kosong dan mendapat agregat revenue/qty di luar scope. Produk yang hanya tersedia di B juga dapat ditawarkan sebagai substitute tersedia untuk A.

Arah perbaikan: Resolve entity scope authorized pada router dan teruskan ke analytics serta inventory enrichment. Pisahkan available langsung dari opsi yang memerlukan transfer/intercompany dan lead time.

Acceptance criteria: Query B tanpa izin ditolak; default memakai A; stok hanya B bukan available A; opsi intercompany ditampilkan dengan syarat approval/lead time.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-11 — Saga release menghapus lock tanpa mengecek efek yang sudah terposting

Rujukan: [GN-11](01_TEMUAN_AUDIT_KNHOST.md#gn-11).

```text
Perbaiki GN-11 (P1): Saga release menghapus lock tanpa mengecek efek yang sudah terposting.

Status bukti audit: Risiko pemulihan statis.

Periksa lokasi awal: backend/routers/saga_locks.py:36; backend/services/atomic_claim.py:53. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Claim mengunci dokumen induk, bukan seluruh transaksi lintas koleksi atau roll yang juga digunakan induk lain. Endpoint release admin langsung menghapus lock tanpa memeriksa tahap/efek yang telah diposting. Lock sendiri tidak membuktikan exactly-once recovery.

Reproduksi/negative case: Inbound/return/PA mati sesudah roll atau movement dibuat tetapi sebelum status akhir. Admin release lalu retry dapat mengulang efek yang sudah ada. Hasil persis bergantung guard masing-masing source; fault test wajib, bukan asumsi semua flow pasti duplicate.

Arah perbaikan: Simpan operation ledger dengan tahap, effect keys dan version/fencing. Release harus mengikuti pemeriksaan efek dan rencana resume/compensate, bukan unlock generik. UI recovery menunjukkan apa yang sudah terjadi.

Acceptance criteria: Fault pada setiap tahap pulih tepat sekali; lock operasi aktif tidak dilepas tanpa fencing; audit pemulihan mencatat efek, aktor dan hasil.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-12 — Agregasi kritis berhenti pada batas to_list tanpa penanda truncation

Rujukan: [GN-12](01_TEMUAN_AUDIT_KNHOST.md#gn-12).

```text
Perbaiki GN-12 (P2): Agregasi kritis berhenti pada batas to_list tanpa penanda truncation.

Status bukti audit: Terbukti statis; kasus skala belum DB test.

Periksa lokasi awal: backend/services/roll_service.py:184; backend/services/financial_statement_service.py:60; backend/services/costing_service.py:60; backend/routers/cash.py:76. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Rebuild balance menarik maksimum10.000 roll, WAC5.000, laporan keuangan100.000 jurnal dan cash summary2.000 transaksi. Banyak analitik mempunyai cap serupa. Batas daftar UI boleh, tetapi total/projection tidak boleh menganggap halaman tersebut sebagai seluruh data.

Reproduksi/negative case: Pada10.001 roll atau100.001 jurnal, record setelah cap tidak dihitung. Cash summary menyaring entity setelah pengambilan capped, sehingga data entitas lain dapat memenuhi batas dan menyembunyikan saldo entitas aktif.

Arah perbaikan: Pakai aggregation/streaming untuk total dan nilai; scope sebelum query. Detail memakai pagination dengan total/has_more. Verifikasi index dan fixture tepat di sekitar setiap batas.

Acceptance criteria: Cap−1/cap/cap+1 menghasilkan total akurat; laporan100k+ jurnal reconcile; UI tidak menjadikan satu halaman sebagai total financial.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-13 — Rebuild projection dapat menulis snapshot lama dan fallback UOM mencampur unit

Rujukan: [GN-13](01_TEMUAN_AUDIT_KNHOST.md#gn-13).

```text
Perbaiki GN-13 (P2): Rebuild projection dapat menulis snapshot lama dan fallback UOM mencampur unit.

Status bukti audit: Risiko konkurensi dan logika statis.

Periksa lokasi awal: backend/services/roll_service.py:184. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Rebuild membaca state roll lalu menulis projection tanpa revision barrier; dua rebuild dapat selesai di luar urutan pembacaan. Saat konversi unit gagal, error ditangkap dan panjang native tetap dapat ditambahkan ke bucket base unit.

Reproduksi/negative case: Rebuild A membaca stok lama; mutasi B dan rebuild B menulis saldo baru; A kemudian menimpa saldo baru dengan snapshot lama. Yard yang gagal dikonversi tetap ikut dijumlahkan seolah meter.

Arah perbaikan: Gunakan revision/watermark atau pembacaan stabil dengan retry. Konversi unit wajib valid; projection gagal/invalid harus terlihat sebagai exception, bukan fallback1:1. Pantau lag dan drift.

Acceptance criteria: Rebuild out-of-order tidak menurunkan revision; conversion failure menandai saldo invalid; source dan projection reconcile setelah mutasi konkurensi.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-14 — Audit log selalu before=None dan source secrets tersimpan dalam repo publik

Rujukan: [GN-14](01_TEMUAN_AUDIT_KNHOST.md#gn-14).

```text
Perbaiki GN-14 (P2): Audit log selalu before=None dan source secrets tersimpan dalam repo publik.

Status bukti audit: Kontrol statis; validitas secret belum diverifikasi.

Periksa lokasi awal: backend/dependencies.py:168. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Helper audit selalu menulis before=None; after bergantung caller dan sering hanya ringkasan. Ia adalah event log, belum cukup untuk merekonstruksi semua perubahan financial. Repo publik juga melacak .tok dan .tok_mgr, masing-masing45byte nonempty, serta artifact restore env. Nilai tidak dicetak, dipakai atau dikirim dalam audit; credential aktif belum dibuktikan.

Reproduksi/negative case: Perubahan saldo awal/field financial tidak mempunyai nilai sebelum perubahan dari helper. Bila file token berisi sesi yang masih berlaku, pembaca repo dapat mengambilnya. Domain histories lain perlu diperiksa sebagai sumber tambahan, bukan dianggap tidak ada.

Arah perbaikan: Audit financial memuat actor ID, entity, operation/source, alasan serta before/after diff immutable dengan redaction. Inventaris/rotasi token berisiko, bersihkan history secara terkontrol dan pasang secret scanning; jangan sekadar menghapus file tree terbaru.

Acceptance criteria: Perubahan amount/status/account dapat direkonstruksi; audit tidak memuat secret; repo/history bebas secret nyata; validitas credential diperiksa pemilik tanpa menaruh nilainya di laporan.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-15 — Duplikasi helper dan definisi status menunjukkan SSOT belum konsisten

Rujukan: [GN-15](01_TEMUAN_AUDIT_KNHOST.md#gn-15).

```text
Perbaiki GN-15 (P3): Duplikasi helper dan definisi status menunjukkan SSOT belum konsisten.

Status bukti audit: Terbukti static exact AST; sebagian risiko desain.

Periksa lokasi awal: backend/services/contract_service.py:62; backend/services/lot_service.py:59; backend/services/receiving_uom_service.py:63; backend/services/uom_rules_service.py:146. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Scanner menemukan dua pasangan get_settings dengan AST identik. Duplikasi business policy lebih penting: physical status RFID berbeda dari roll, resolver COA berbeda antarposting/report, dan evaluator gate simulator berbeda dari hardware. Tidak semua duplikasi kode adalah bug.

Reproduksi/negative case: Menambah status atau mengubah fallback pada satu jalur dapat memberi hasil berbeda pada jalur lain. Pasangan helper get_settings sendiri belum terbukti menghasilkan data salah.

Arah perbaikan: Satukan policy/resolver domain dan contract tests. Gabungkan helper config hanya bila semantiknya benar-benar sama. Snapshot dokumen tetap immutable dan jangan diganti konfigurasi live saat laporan historis.

Acceptance criteria: Entry point yang setara memberi keputusan yang sama; refactor helper mempertahankan entity fallback; semua status diuji terhadap policy yang terpusat.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### HR-01 — PPh21 memakai TER bahkan pada masa pajak terakhir

Rujukan: [HR-01](01_TEMUAN_AUDIT_KNHOST.md#hr-01).

```text
Perbaiki HR-01 (P1): PPh21 memakai TER bahkan pada masa pajak terakhir.

Status bukti audit: Gap akurasi statis terhadap acuan resmi.

Periksa lokasi awal: backend/services/hr_payroll_service.py:191; backend/services/hr_payroll_service.py:192. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: compute_payslip tidak membedakan Desember atau bulan terakhir bekerja; setiap period menggunakan TER. Tidak ditemukan rekonsiliasi tahunan Pasal17 pada flow payroll yang ditelusuri. TER disabled menghasilkan0, bukan formula progresif alternatif.

Reproduksi/negative case: Pegawai tetap dengan penghasilan bervariasi atau berhenti sebelum Desember tetap mendapat pajak monthly TER pada masa terakhir, bukan pajak tahunan/bagian tahun dikurangi potongan sebelumnya.

Arah perbaikan: Bangun policy pajak effective-dated dengan annual/part-year earnings, pengurang, PTKP/PKP, Pasal17, prior withholding/refund dan termination. Akuntan memvalidasi fixture independen sesuai aturan resmi yang berlaku.

Acceptance criteria: TER masa biasa dan rekonsiliasi masa terakhir, bonus, join/leave tengah tahun, refund serta basis BPJS/PTKP diuji terhadap perhitungan independen. Rujukan DJP pada dokumen fit-gap.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### HR-02 — Lembur memakai multiplier flat dan dua sumber menit berpotensi tumpang tindih

Rujukan: [HR-02](01_TEMUAN_AUDIT_KNHOST.md#hr-02).

```text
Perbaiki HR-02 (P1): Lembur memakai multiplier flat dan dua sumber menit berpotensi tumpang tindih.

Status bukti audit: Direproduksi formula; dedup risiko statis.

Periksa lokasi awal: backend/services/hr_payroll_service.py:180; backend/services/hr_payroll_service.py:156. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Total menit lembur dikalikan satu multiplier default1.5, tanpa pembagian jam pertama/berikutnya dan jenis hari. Menit attendance otomatis dan approved filed dijumlah tanpa pairing shift/date; overlap aktual harus diperiksa dari data.

Reproduksi/negative case: HR-02: upah sejam1000, lembur2jam hari kerja menghasilkan3000; acuan1.5jam pertama+2jam berikutnya menghasilkan3500. Bila attendance120menit dan pengajuan120menit menggambarkan kejadian sama, jumlah240 akan menggandakan waktu.

Arah perbaikan: Satu overtime event per hari/shift yang di-approve. Attendance mengusulkan actual time dan filed approval mengesahkan event yang sama. Hitung tier hari kerja/istirahat/libur, wage base serta batas sesuai kebijakan/regulasi.

Acceptance criteria: Dua jam normal=3.5×upah sejam; hari libur dan jadwal5/6hari mengikuti fixture resmi; overlap sumber dihitung sekali; kejadian unapproved/duplicate tidak dibayar.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### HR-03 — Persetujuan cuti tidak mengecek ulang saldo dan cuti lintas tahun salah pembebanan

Rujukan: [HR-03](01_TEMUAN_AUDIT_KNHOST.md#hr-03).

```text
Perbaiki HR-03 (P2): Persetujuan cuti tidak mengecek ulang saldo dan cuti lintas tahun salah pembebanan.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/services/hr_leave_service.py:87; backend/services/hr_leave_service.py:202; backend/services/hr_leave_service.py:96. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Submit membandingkan days dengan remaining tanpa mengurangi pending reservation; approve tidak memeriksa ulang saldo. Recompute membebankan seluruh days menurut tahun date_from, bukan tahun setiap work_date. Kehadiran cuti juga tidak ditautkan ke request ID pada clear.

Reproduksi/negative case: Entitlement12: dua pengajuan10hari dapat diterima dan keduanya disetujui sehingga used20/remaining−8. Cuti yang melintasi Desember–Januari dibebankan seluruhnya ke tahun awal. Membatalkan satu cuti dapat menghapus attendance leave yang dibuat request lain pada tanggal sama.

Arah perbaikan: Reservasi/revalidasi saldo secara atomik per employee/year; bagi days ke tahun masing-masing dengan kalender kerja/libur; guard overlap. Simpan leave_request_id pada attendance dan hapus hanya record sumber yang benar.

Acceptance criteria: Approved days tidak melebihi entitlement tanpa override; lintas tahun dibebankan benar; overlap ditolak; cancel satu request tidak menghapus attendance request lain.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### MK-01 — Input metrik marketing parsial mengganti seluruh metrik sebelumnya

Rujukan: [MK-01](01_TEMUAN_AUDIT_KNHOST.md#mk-01).

```text
Perbaiki MK-01 (P2): Input metrik marketing parsial mengganti seluruh metrik sebelumnya.

Status bukti audit: Terbukti statis.

Periksa lokasi awal: backend/services/marketing_service.py:259. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: record_metrics memilih hanya field yang dikirim lalu mengganti seluruh metrics. Request parsial dapat menghapus nilai sebelumnya; history menyimpan patch tetapi dashboard membaca snapshot baru yang tidak lengkap.

Reproduksi/negative case: Catat likes10, lalu kirim hanya reach100. Current metrics kehilangan likes sehingga engagement campaign turun. Bila kontrak sengaja full replacement, schema/UI harus mewajibkan snapshot lengkap; saat ini tidak.

Arah perbaikan: PATCH per field metrics.<name> atau merge snapshot dengan version. Bedakan nilai0 eksplisit dari field tidak dikirim; simpan metadata/full snapshot history yang konsisten.

Acceptance criteria: Update reach tidak menghapus likes; likes0 mengganti nilainya; dua update field berbeda bersamaan tidak saling menimpa; total campaign reconcile.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### UX-01 — Gate kiosk menampilkan hasil lama sebagai LIVE dan tidak mengagregasi satu passage

Rujukan: [UX-01](01_TEMUAN_AUDIT_KNHOST.md#ux-01).

```text
Perbaiki UX-01 (P1): Gate kiosk menampilkan hasil lama sebagai LIVE dan tidak mengagregasi satu passage.

Status bukti audit: Terbukti dari source UI; belum uji visual hardware.

Periksa lokasi awal: frontend/src/features/rfid/RfidGateMonitorView.jsx:71; frontend/src/features/rfid/RfidGateMonitorView.jsx:76; frontend/src/features/rfid/RfidGateMonitorView.jsx:121. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Read limit25 diambil sebelum filter inventory/gate pada frontend; traffic lain dapat menutupi gate pilihan. Kegagalan polling disenyapkan tanpa expiry hasil; label LIVE dan green lama tetap terlihat. Verdict kiosk memakai satu EPC, bukan seluruh passage.

Reproduksi/negative case: Sesudah green, reader/network mati dan layar tetap green/LIVE. Passage mempunyai satu roll unauthorized dan roll lain green; hasil teratas dapat menampilkan green. Lebih25 inventory reads menenggelamkan event gate.

Arah perbaikan: Filter gate/device di server dengan cursor. Agregasi passage harus red-dominant, alarm latched dan acknowledge terpisah. Tampilkan heartbeat age, network status, waktu fetch terakhir dan verdict TTL; offline menjadi UNKNOWN/TAHAN sesuai policy.

Acceptance criteria: Disconnect mengubah status sesuai TTL; passage campuran selalu TAHAN; traffic lain tidak menutupi gate; acknowledge tidak menghapus pelanggaran sumber.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### UX-02 — Unduhan ZPL lewat tautan tidak membawa konteks entitas yang dipilih

Rujukan: [UX-02](01_TEMUAN_AUDIT_KNHOST.md#ux-02).

```text
Perbaiki UX-02 (P2): Unduhan ZPL lewat tautan tidak membawa konteks entitas yang dipilih.

Status bukti audit: Risiko UI statis.

Periksa lokasi awal: frontend/src/features/rfid/RfidPrintVerifyPanel.jsx:180. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Unduh lewat href browser membawa cookie tetapi tidak membawa X-Entity-Id dari apiClient. User multi-entitas yang memilih entity berbeda dari home dapat ditolak pada job valid karena konteks download kembali ke home. Jangan memperbaikinya dengan melonggarkan guard server.

Reproduksi/negative case: Login homeA, pilihB, buka jobB lalu klik direct download ZPL. Request tidak membawa header entitas pilihan. Browser integration test diperlukan untuk memastikan respons pada deployment aktual.

Arah perbaikan: Fetch blob melalui apiClient dengan entity header lalu download object URL; atau ticket singkat yang terikat job/entity/user. Jangan memakai token sesi permanen di URL.

Acceptance criteria: Job B dapat diunduh dari selected B dengan scope benar; job tanpa izin ditolak; ticket expired tidak berlaku dan object URL dibersihkan.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### GN-16 — Laporan AI pribadi disiarkan melalui notifikasi dan digest tidak membatasi entitas

Rujukan: [GN-16](01_TEMUAN_AUDIT_KNHOST.md#gn-16).

```text
Perbaiki GN-16 (P1): Laporan AI pribadi disiarkan melalui notifikasi dan digest tidak membatasi entitas.

Status bukti audit: Terbukti dari kontrak audience dan query.

Periksa lokasi awal: backend/services/ai_schedules.py:92; backend/services/notification_service.py:67; backend/services/notification_scope.py:47; backend/services/digest_service.py:119. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: run_schedule mengirim recipient_user tanpa mengosongkan recipient_role yang default all. Filter pembaca menggunakan OR role/user; pengguna lain pada entitas sama yang boleh membuka Tanya KN dapat menerima body narasi laporan pribadi. Admin mempunyai pengecualian filter pribadi sendiri, jadi bukan seluruh pengguna otomatis menerima. Selain itu summarize_for pada digest menerapkan relevance_filter tetapi tidak filter entity/allowed_entity_ids; projection judul dapat memasukkan notifikasi entitas lain.

Reproduksi/negative case: Buat laporan terjadwal privat untuk user U1, lalu buka notifikasi sebagai U2 pada entitas sama dengan izin Tanya KN. Untuk digest, buat dua notifikasi role-compatible milik A/B dan jalankan ringkasan untuk user hanya A: query tidak membatasi B. Ini skenario source-based, belum pengiriman WhatsApp nyata.

Arah perbaikan: Untuk notifikasi individual set recipient_role kosong atau pakai helper audience khusus. Satukan audience/relevance/entity policy antara inbox, digest, WA dan web push. Periksa notifikasi historis yang sudah salah audience dengan dry-run tanpa menyebarkan kembali isinya.

Acceptance criteria: U2 tidak menerima laporan U1; user A tidak menerima judul/notifikasi B di inbox, digest, push atau WA. Penerima U1 tetap menerima sekali. Notifikasi sistem/shared hanya mengikuti policy eksplisit.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

### UX-03 — Panel biaya OCR menampilkan ID entitas mentah

Rujukan: [UX-03](01_TEMUAN_AUDIT_KNHOST.md#ux-03).

```text
Perbaiki UX-03 (P3): Panel biaya OCR menampilkan ID entitas mentah.

Status bukti audit: Terbukti dari render source.

Periksa lokasi awal: frontend/src/features/wms/grn/GrnOcrUsagePanel.jsx:53. Telusuri semua callers dan jalur alternatif sebelum mengubah.

Masalah: Kolom Badan usaha menampilkan entity_id teknis meskipun helper label bersama tersedia pada frontend. Ini mengurangi kejelasan bagi operator dan finance saat meninjau biaya OCR.

Reproduksi/negative case: Rows usage berisi entity_id internal: tabel menampilkan ID alih-alih nama badan usaha. Guardrail juga menandai MobileMdApp, tetapi itu false positive karena user.name berbagi baris dengan entityShortById; temuan ini hanya panel OCR yang benar-benar memakai raw ID.

Arah perbaikan: Gunakan resolver label entitas atau EntityBadge yang sesuai context, dengan fallback manusiawi untuk legacy entity tidak ditemukan. Pertahankan ID sebagai metadata teknis bila diperlukan.

Acceptance criteria: Tabel menampilkan nama entitas yang benar, fallback jelas untuk record legacy, dan tidak memunculkan ID mentah sebagai label utama.

Verifikasi dampak regresi pada owner/entity, UOM, stok/nilai, retry dan audit trail yang relevan. Tunjukkan before/after; untuk risiko statis atau konkurensi, buktikan dahulu dengan integration fixture. Jangan menyatakan selesai hanya berdasarkan syntax/lint.
```

# Gelombang 2, W2-05 — RFID gate, ingest, insiden, dan isolasi entitas

Snapshot `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`; uji **24 skenario baru** melalui route ASGI dan service asli, Motor serta MongoDB lokal dengan data sintetis. W2-R-F09 memanggil service langsung untuk mengendalikan race deduplikasi; skenario lain memakai API HTTP. Rincian observasi per skenario: [rfid-results.json](rfid-results.json); harness: [wave2_rfid.py](repro/wave2_rfid.py); tindakan agent: [11_PROMPT_RFID_GATE_DAN_INSIDEN.md](11_PROMPT_RFID_GATE_DAN_INSIDEN.md). Aplikasi belum dijalankan melalui browser atau reader/gate fisik. `app` lifespan/scheduler tidak dijalankan. Barrier pada dua skenario konkurensi hanya mengatur urutan operasi Mongo, tanpa mengganti aturan bisnis.

**Direvisi setelah [validasi ulang](12_VALIDASI_ULANG_W2_05.md).** Semua observasi runtime awal terulang, tetapi interpretasi enam skenario harus dikoreksi. Hasil W2-05 kini: **10 kontrol, tiga reproduksi cacat W2-010–012, enam observasi kebijakan akses yang belum terbukti sebagai pelanggaran, dan lima pendalaman Gelombang 1**. Kumulatif tetap **63 skenario unik, 38 kontrol, 14 reproduksi cacat W2, enam observasi kebijakan, lima pendalaman Gelombang 1; 12 ID W2**. Uji ulang tidak menambah angka coverage. Raw JSON awal dipertahankan sebagai histori; gunakan klasifikasi terbaru di [classification.json](validation/W2-05-review/classification.json).

## W2-010 · P1 — histori pembacaan RFID melanggar scope owner roll

### Bukti dan alur

Fixture awal: pengguna U berizin `wms.view/update`, `allowed_entity_ids=[A]`, entitas aktif A. Sebuah roll B dibaca merah, menghasilkan read dan insiden ber-owner B lewat ingest asli. **Koreksi:** gudang awal hanya memakai `entity_id=B`, sehingga sebenarnya tetap shared menurut `warehouse_scope_service`; perangkat juga didesain sebagai infrastruktur bersama. Gudang itu tidak boleh disebut dedicated B. Uji ulang membuat gudang `sharing_mode=dedicated, entity_ids=[B]` serta gudang shared, roll/tag/device lewat service asli. Pada kedua jenis gudang, API tags menyembunyikan tag B dari A, tetapi API reads tetap mengembalikan EPC, roll dan owner B. Pemaksaan header entitas B pada API tags ditolak403. Ini membuktikan scope actor benar-benar terbatas A.

| Skenario | API / observasi | Implikasi |
|---|---|---|
| W2-R-F01 | `GET /rfid/reads?warehouse_id=WB` → 200, row owner B | **Cacat terkonfirmasi:** bertentangan dengan registry scope `rfid_reads`. |
| W2-R-F02 | `GET /rfid/incidents?warehouse_id=WB` → 200, insiden owner B | Observasi kebijakan: incidents dinyatakan SHARED oleh registry. |
| W2-R-F03 | `POST /rfid/incidents/{B}/acknowledge` → 200 | Aksi lintas owner terkonfirmasi, tetapi tidak cukup bukti bahwa kebijakan melarangnya. |
| W2-R-F04 | `POST /rfid/incidents/{B}/resolve` → 200 | Klasifikasi pelanggaran akses ditarik; perlu kontrak hak operator keamanan. |
| W2-R-F05 | `GET /rfid/shrinkage-report` → 200, statistik WB | Aggregate lintas entitas terbukti; otorisasi laporan pusat belum ditentukan. |
| W2-R-F06 | `GET /rfid/device-health` → 200, B-OUT | Device infra SHARED; visibilitas ini sendiri bukan bukti kebocoran terlarang. |
| W2-R-F07 | `GET /rfid/incidents` tanpa filter → 200, memuat B | Konsisten dengan registry SHARED; perlu keputusan akses pusat/lokal. |

Kontrol W2-R-C09 memeriksa filter WA, tetapi daftar terbatasi100 dan didominasi alarm EPC asing; hasilnya tidak membuktikan kelengkapan tampilan insiden A. Hanya menunjukkan row hasil filter tidak memuat B. Bukti scope yang lebih kuat adalah pembandingan API tags dengan reads pada roll B yang sama dan kontrol header403 di uji ulang.

### Letak akar masalah

- [backend/routers/rfid.py:343](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/routers/rfid.py#L343) memanggil `list_reads` setelah `require_permission`, tanpa `entity_ctx`/scope. [rfid_service.py:268](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/rfid_service.py#L268) hanya memakai filter query yang diberikan caller.
- [entity_scope.py:38](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/entity_scope.py#L38) mensyaratkan `rfid_reads` mengikuti `owner_entity_id`; route/service reads tidak menggunakan aturan ini.
- Sebaliknya [entity_scope.py:45](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/entity_scope.py#L45) secara eksplisit menyebut log keamanan lintas entitas dan menetapkan `rfid_incidents: SHARED`. [rfid_service.py:190](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/rfid_service.py#L190) menyebut device sebagai SHARED infra per-gudang. Ketiadaan owner filter di route insiden/device tidak otomatis cacat terhadap kontrak saat ini.

`RfidSecurityPanel` melakukan [permintaan insiden dengan `whId` tetapi statistik dan device tanpa filter](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/frontend/src/features/rfid/RfidSecurityPanel.jsx#L23), dan me-render angka [L48](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/frontend/src/features/rfid/RfidSecurityPanel.jsx#L48) serta daftar gudang/device [L121](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/frontend/src/features/rfid/RfidSecurityPanel.jsx#L121). Ini mendukung dampak UI, tetapi belum browser UAT. Warehouse shared dapat menampung banyak owner; pembatasan berdasarkan `warehouse_id` saja **tidak cukup**. EPC asing punya `owner_entity_id=None`; tentukan kebijakan per-device/warehouse untuk event tak dikenal tanpa membuka insiden owner lain.

**Kontrak perbaikan W2-010:** ambil scope reads dari sesi server dan gunakan owner filter pada `list_reads`, termasuk ketika query warehouse/device kosong atau dipaksakan caller. Uji A/B/multi-entity pada gudang dedicated/shared, serta unknown EPC dengan policy yang eksplisit. Jangan otomatis menerapkan owner filter yang sama pada incidents/device health atau mengganti registry SHARED: bila bisnis menginginkan operator keamanan pusat, akses lintas entitas bisa sah. Pisahkan keputusan itu dari patch cacat reads yang sudah terbukti. P01 dan RF-08 adalah pekerjaan terkait, bukan alasan untuk mengubah kebijakan tanpa menelusuri kontraknya.

## W2-011 · P2 — status insiden bisa mundur dari resolved ke acknowledged

Validasi ulang mengonfirmasi melalui dua sesi operator berbeda, insiden yang dibuat ingest asli, dan indeks bootstrap aplikasi. Kedua respons200; status akhir acknowledged dengan resolved_by operator2 dan ack_by operator1. Prioritas dikoreksi P1→P2: cacat workflow terbukti, tetapi belum terbukti mengubah stok atau memberi izin keluar gate. State insiden perlu diperbaiki, tanpa menyamakan dampaknya dengan bypass gate.

**W2-R-F08.** Dua aksi pada insiden A yang sama dijadwalkan berbarengan. Acknowledge membaca status `open`, lalu ditahan tepat sebelum `update_one`. Resolve membaca `open` dan menulis `resolved`. Acknowledge lalu melanjutkan. Kedua API menjawab 200, tetapi row akhir berstatus `acknowledged` **dan** memiliki `resolved_at`. UI [menampilkan pill DI-ACK sekaligus metadata selesai](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/frontend/src/features/rfid/RfidSecurityPanel.jsx#L81); alarm yang sudah dinyatakan selesai dapat muncul lagi sebagai belum tuntas. Audit log kedua tindakan ada, tetapi final state tidak lagi merepresentasikan tindakan terakhir yang lebih kuat.

Sumber: [rfid_incident_service.py:78–94](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/rfid_incident_service.py#L78) memeriksa state dari `find_one`, lalu `update_one({"id": incident_id}, ...)` tanpa precondition status/versi. Kontrol W2-R-C10: urutan serial open→ack→resolved benar (200/200), dan ack setelah resolved ditolak 400. Cacat khusus race read–write.

Perbaikan: transisi bersyarat pada status asal yang masih diizinkan, atau versi monoton/transaction yang membuktikan tepat satu state berikutnya. Bila update tidak match, baca ulang dan kembalikan conflict; jangan log sukses. `resolved` terminal kecuali workflow reopen eksplisit dengan alasan dan event baru. Uji dua aksi berbarengan, dua ack, dua resolve, retry, serta urutan ack/read→resolve/write→ack/write. Validasi isi `ack_at`, `resolved_at`, notes dan audit trail sejalan dengan status akhir.

## W2-012 · P2 — deduplikasi insiden bukan operasi atomik

**W2-R-F09.** Dua pembacaan merah EPC+device yang sama memulai `create_from_read` serentak. Barrier membuat keduanya membaca “tidak ada open incident” sebelum salah satu insert. Hasilnya **dua insiden open**, masing-masing `hits=1`, padahal kontrak docstring service adalah satu insiden dan `hits=2` untuk jendela 10 menit. [rfid_incident_service.py:25–34](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/rfid_incident_service.py#L25) memakai `find_one` lalu `insert_one`; tidak ada unique partial index/upsert/claim atomik. Jalur ingest [rfid_ingest_service.py:122](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/rfid_ingest_service.py#L122) memanggilnya untuk setiap read merah. Kontrol W2-R-E01: dua batch **serial** menghasilkan satu open incident `hits=2`, jadi bug spesifik konkurensi.

Konsekuensi: satu passage dapat menjadi dua alarm dan dua notifikasi, operator dapat menyelesaikan satu sementara yang lain tetap open, dan angka shrinkage “insiden terbuka” membesar. Ini **terkait RF-16** (identitas/passage event), tetapi akar tambahan adalah check-then-insert non-atomik pada insiden. Perbaikan harus menetapkan kunci identitas insiden/passage dan dedupe window yang dapat ditulis atomik, dilindungi unique constraint atau mekanisme setara; hati-hati bahwa `status=resolved` lalu passage baru memang dapat membuat insiden baru sesuai kebijakan. Jaga hits dan notifikasi sekali per incident baru. Uji konkurensi antar worker/proses serta retriable write.

**Bukti tambahan validasi:** dua request HTTP ingest membuat dua read ID berbeda, dua open incident, dua notifikasi. Bootstrap indeks berhasil, koleksi insiden tetap hanya memiliki indeks `_id`. Tanpa barrier, sembilan dari sepuluh pasangan request lokal menghasilkan dua insiden. Ini bukti race dapat terjadi tanpa instrumentasi; rasio9/10 bukan estimasi probabilitas produksi. W2-012 tetap submasalah konkuren terkait RF-16; jumlah ID tiket tidak menyatakan akar masalah seluruh aplikasi saling independen.

## Validasi ulang temuan Gelombang 1 dan kontrol gate

| ID skenario | Klasifikasi | Observasi |
|---|---|---|
| C01–C03 | kontrol | Key kosong/invalid ditolak401; printer menolak ingest400. |
| C04–C05 | kontrol | Roll available/quarantine di gate keluar → red. |
| C06 | kontrol | EPC duplikat dalam satu batch menjadi satu read. |
| E01 | RF-16 | Batch berikutnya EPC sama menambah read lagi; dedupe incident serial hanya menaikkan hits. |
| E02 | RF-02 | Roll `reserved`, tanpa dokumen dan milik WA, di gate keluar WX → green. |
| E03 | RF-03 | Roll `in_transit_transfer` tanpa dokumen tujuan di gate masuk WX → green. |
| C07–C08 | kontrol | PA aktif dengan tujuan WB → green di WB dan red di WX. Guard PA yang benar harus dipertahankan saat memperbaiki RF-03. |
| E04 | RF-13 | Device `offline` dengan key valid diterima ingest, lalu diubah `online`. |
| E05 | RF-16 | 501 EPC di-submit, response200 hanya mengakui500; EPC ke-501 tidak tersimpan, tanpa sinyal dropped. |

RF-02/03/13/16 **bukan ID W2 baru**. Temuan Gelombang 1 masih punya tracker sendiri; jangan menandai fixed karena snapshot ini belum berisi perbaikan. Perangkat offline dipilih sesuai jalur UI “Matikan”; `disabled` bukan satu-satunya representasi status. Kasus PA menjaga koreksi review Astra sebelumnya: masalah RF-03 ada pada fallback tanpa dokumen, bukan semua PA.

## Implikasi operasional dan pembanding enterprise

Untuk gate produksi, satu “green” harus mengikat EPC/roll, lane/read point, arah, transaksi serta tujuan yang masih berlaku. Model event [GS1 EPCIS 2.0.1](https://ref.gs1.org/standards/epcis/2.0.1/) mendefinisikan `eventTime`, `readPoint`, `bizLocation`, business transaction, source/destination dan identitas event opsional sebagai konteks traceability. Ini **pembanding desain**, bukan klaim KNHOST wajib bersertifikasi EPCIS. RF-16 menyangkut identitas/passage event; RF-02/03 adalah aturan keputusan yang melewatkan validasi dokumen. Menambahkan eventID saja tidak memperbaiki keputusan gate tersebut.

[SAP EWM RF exception handling](https://help.sap.com/docs/SAP_EXTENDED_WAREHOUSE_MANAGEMENT/3d97bec9bf1649099384bb8167df3cf2/87c9a6d3b0af47ddb2219030425ff535.html) mengaitkan exception dengan konteks tugas gudang dan dapat memicu workflow/alert; [Warehouse Monitor](https://help.sap.com/docs/SAP_S4HANA_CLOUD/87f9b54f9c4f4e75aff0061860a6589a/e8a30c35c57f4391a22aa6102fa3be24.html) menyediakan jejak siapa dan kapan menyelesaikan exception. KNHOST sudah punya alarm, ack/resolve, notes, health dan ringkasan. Gap terbukti ialah scope histori reads, konsistensi transisi dan dedupe insiden, serta keterikatan gate ke pekerjaan gudang. Ini perbandingan kapabilitas, bukan benchmarking performa vendor. RF-02/03/13/16 mendasari kesimpulan **belum layak menjadi kontrol tunggal pelepasan gate fisik**. Pernyataan sebelumnya yang melarang penutupan insiden lintas entitas secara umum ditarik: kebijakan keamanan bersama memang ada di kode, sementara batas hak operatornya perlu diperjelas. Race insiden tetap perlu diperbaiki sebelum workflow itu dapat diandalkan.

## Batas dan koordinasi

Tidak diuji: kestabilan RF di area nyata, kualitas antenna/RSSI, pembacaan tag simultan oleh banyak reader, middleware Kotlin yang tidak ada di repo ini, integrasi lampu/sirene/PLC, mode offline, UI browser, latency dan recovery setelah crash. W2-010–012 ditemukan pada snapshot saat user mengerjakan Gelombang 1 di tempat lain. Perbaikan P01/P09 Gelombang 1 kemungkinan menyentuh file sama; implementasikan dari branch terkini dan validasi ulang seluruh skenario, tanpa menganggap hasil snapshot ini mewakili kode baru.

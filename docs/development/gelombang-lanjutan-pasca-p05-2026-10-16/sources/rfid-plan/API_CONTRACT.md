# API RFID: Kondisi Existing dan Target Integrasi Chainway

**Tanggal pemeriksaan:** 12 Oktober 2026. **Snapshot:** `f59b8a60d7b7e078888c537ca93c046afae460a9`. Penelusuran berikut adalah pembacaan kode dan pencarian artifact, bukan uji hardware/API deployment terbaru.

## 1. Endpoint existing

Prefix router adalah `/api`. API key perangkat dikirim melalui `X-Device-Key`; sesi user ERP tetap diperlukan untuk pekerjaan operator yang memerlukan otorisasi. Jangan memberi perangkat akun admin agar dapat menjalankan semua endpoint.

| Endpoint | Identitas | Fungsi existing / batasnya |
|---|---|---|
| POST /api/rfid/devices/{device_id}/api-key | User admin | Terbit/rotasi key; key ditampilkan sekali, server menyimpan hash. |
| POST /api/rfid/ingest | Device key | EPC/events gate atau inventory; session_id mengarahkan scan handheld/fixed reader ke sesi. |
| POST /api/rfid/heartbeat | Device key | Menandai kontak/online dan memberi server time; bukan laporan lengkap radio/outbox. |
| GET /api/rfid/gate/{device_id}/status | User WMS view | Passage/status untuk UI; bukan endpoint device-key tanpa sesi user. |
| GET /api/rfid/passages | User WMS view | Riwayat passage. |
| POST /api/rfid/passages/{passage_id}/acknowledge | User WMS scan | Akui alarm dengan catatan; tidak menghapus bukti read/insiden. |
| POST /api/rfid/print-jobs/{job_id}/verify/start | User WMS scan | Mulai sesi verifikasi tag dari expected print job. |
| POST /api/rfid/verify-sessions/{session_id}/complete | User berizin | Selesaikan verifikasi sesuai scope/hasil; jangan dianggap completion otomatis saat API menerima satu EPC. |
| POST /api/outbound/so/{order_id}/loading-check/start | User berizin | Mulai loading check per SO/gudang sesuai flow existing. |
| POST /api/outbound/loading-check/{session_id}/complete | User berizin | Selesaikan loading check; arah selanjutnya mengikuti shipment/dispatch. |
| POST /api/rfid/cycle-count/start | User WMS scan | Mulai expected physical-tag scope; bukan penerimaan stok baru. |
| POST /api/rfid/cycle-count/{session_id}/complete | User WMS scan | Hasil found/missing/extra/untagged; tidak otomatis mengubah qty. |
| GET /api/rfid/device-health | User WMS view | Monitoring perangkat; detail radio/queue versi client perlu diperluas jika belum tersedia. |
| GET /api/rfid/device-jobs/pending | Device printer key | Pull/claim job cetak untuk connector CP30EN; capability dan warehouse mengikuti registrasi device. |
| POST /api/rfid/device-jobs/{job_id}/ack | Device printer key | Konfirmasi attempt/lease cetak; bukan bukti C72 telah membaca hasil tag. |

Rujukan: [router RFID](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/routers/rfid.py#L519), [service ingest](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/rfid_ingest_service.py), [loading router](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/routers/outbound_picking.py#L486).

## 2. Contoh payload existing

Gate/reader mengirim pada POST `/api/rfid/ingest` dengan header `X-Device-Key` berisi key perangkat yang diprovisioning. Identitas gudang serta arah gate berasal dari konfigurasi device server, bukan dipilih bebas oleh payload.

```json
{
  "batch_id": "batch-000001",
  "events": [
    {
      "event_id": "read-000001",
      "epc": "E20034120123456789ABCDEF",
      "captured_at": "2026-10-12T01:00:00Z",
      "antenna": 1,
      "rssi": -48.5
    }
  ]
}
```

Nilai di atas hanya contoh. ID event tetap sama ketika event yang sama dikirim ulang, tetapi berbeda untuk observasi asli yang berbeda. Gunakan `events` atau `epcs` untuk pembacaan yang sama; jangan menggandakan daftar yang identik ke dua field. Kontrak EPC internal adalah 24 hex uppercase; raw EPC asing/rusak ditangani sebagai exception, bukan dipotong agar tampak valid.

Untuk sweep C72 ke sesi, tambahkan `session_id` yang diberikan flow operator ERP:

```json
{
  "session_id": "rvs-example",
  "batch_id": "batch-c72-000001",
  "events": [
    {"event_id": "c72-read-000001", "epc": "E20034120123456789ABCDEF", "captured_at": "2026-10-12T01:00:00Z"}
  ]
}
```

**Batas penting:** schema menerima fields di atas, tetapi pada snapshot cabang session mereduksi events menjadi EPC sebelum memanggil ingest_into_session. Itu berarti persistensi event_id/timestamp/antenna/RSSI dan perilaku ACK/limit yang setara belum boleh diasumsikan. Kontrak ini perlu dirapikan pada RF01 sebelum client produksi mengandalkan metadata tersebut.

Pada jalur umum, service mempunyai limit 500 raw events dan menolak batch berlebih dengan 413. Batch_id hanya disimpan sebagai metadata; idempotensi transport bertumpu pada event_id per device serta recovery processing, bukan batch_id saja. Cabang session perlu pengujian/penyelarasan tersendiri.

Response umum mencakup accepted/duplicates/count, hasil per EPC/read, green/red serta passage jika gate. Pada sesi response berisi progress sesi dari scan_session, bukan response gate umum. Client tidak boleh memaksa satu bentuk ACK untuk dua jalur ini tanpa kontrak server yang eksplisit.

## 3. Apa yang telah ditelusuri dan yang belum terbukti

| Kondisi kode | Implikasi pengembangan |
|---|---|
| Device authentication, observations, retry unfinished processing dan gate evaluator ada. | Fondasi dipakai dan diuji ulang, bukan dibangun sebagai service bisnis kedua. |
| Gate direction berasal dari device.direction. | Antenna metadata tidak otomatis membuktikan arah; mapping reader dua arah perlu desain logical gate. |
| Passage window/dwell serta verdict menggunakan waktu pemrosesan server; captured_at disimpan sebagai metadata pada ingest umum. | Backlog historis tidak aman diperlakukan sebagai keputusan fisik saat ini tanpa mode replay serta kebijakan yang eksplisit. |
| Cabang session menyerahkan EPC saja ke session service. | Audit metadata, limit, idempotensi dan traceability sesi diperlukan. Ini temuan kontrak statis, belum reproduksi runtime baru. |
| /rfid/reader/scan mengambil tag aktif dari database dan mencatat read. | Tombol ini tidak memanggil SDK C72/UR300; tidak menjadi bukti radio benar-benar memindai barang. |
| Pencarian snapshot tidak menemukan project Kotlin/Java/Gradle/APK/AAR. | Adapter produksi belum terbukti ada dalam repo ini; periksa repo/app vendor terpisah sebelum membangun ulang. |
| Print job menghasilkan ZPL untuk encoding RFID. | CP30EN telah dipilih; ZPL/firmware/media serta hasil encode aktual perlu PoC. ACK printer terpisah dari verifikasi C72. |

Rujukan: [reader_scan](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/rfid_service.py#L350), [session ingest](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/rfid_ingest_service.py#L297), [gate evaluator](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/gate_evaluator.py), [EPC contract](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/epc.py), [print service](https://github.com/pandeyoga/KNHOST/blob/f59b8a60d7b7e078888c537ca93c046afae460a9/backend/services/rfid_print_service.py).

## 4. Perluasan kontrak yang diusulkan — belum endpoint existing

RF01 harus menilai dan mendokumentasikan kebutuhan berikut sebelum menetapkan path/schema final. Tidak ada nama endpoint baru yang dinyatakan sudah tersedia.

1. Discovery/binding task operator dan progress sesi untuk app C72, dengan resource scope serta completion user yang sah.
2. Metadata event dan durable acknowledgement pada session maupun general ingest, termasuk partial failure serta batas batch yang konsisten.
3. Kontrak live vs historical replay, waktu peristiwa, passage/task context dan TTL verdict. Unsupported version tidak diabaikan diam-diam.
4. Device-scoped gate state/config jika service unattended perlu melihat latched alarm setelah user acknowledge; jangan menyimpan token user admin sebagai jalan pintas.
5. Device telemetry radio/queue/error/config/app/SDK version; health kontak, radio dan sukses upload dibedakan.
6. Binding physical reader/antena/logical gate untuk kasus dua arah setelah PoC. Gudang/owner/izin tetap diputuskan server.

Server dan client dirilis dengan compatibility teruji; simulator/manually pasted EPC tetap berlabel asal yang benar. Semua stock transitions tetap melalui layanan transaksi ERP, bukan efek otomatis dari raw read.

## 5. Kontrak printer CP30EN

[Rencana printer](PRINTER_CP30EN_PLAN.md) menjelaskan API claim/attempt/ACK existing serta usulan per-item result, uncertain output, lease renewal dan recovery yang belum tersedia sebagai kontrak lengkap. Connector tidak mengirim ACK printed hanya karena socket/spool menerima payload. Kutipan status pending_print/active/verified pada memo adalah state database yang harus dibedakan dari bukti encoding serta penempelan tag fisik.

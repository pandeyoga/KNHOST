# 1. Arsitektur Bersama dan Batas Tanggung Jawab

**Project:** ERP Kain Nussantara  
**Produksi IT:** PT Kubus Teknologi Indonesia  
**Versi:** 1.0 - 13 Oktober 2026  

## 1.1 Status dan keputusan desain

Dokumen ini adalah spesifikasi pembuatan, bukan implementasi aplikasi. Kontrak API target dalam paket ini diperlakukan tersedia bagi tim pengembangan middleware sesuai arahan pemilik project. Kontrak tersebut menjadi satu acuan integrasi; catatan penyelarasan implementasi ERP disediakan pada berkas terpisah di folder catatan-erp dan tidak menjadi bagian manual middleware.

Reader UR300 menggunakan native Android sebagaimana dijelaskan pemilik project. Arsitektur operasional WAJIB berupa APK/agent yang berjalan langsung pada reader dan berkomunikasi dengan ERP. Laptop/PC tidak menjadi perantara wajib reader. Komputer pengembangan dapat digunakan saat build, instalasi awal, debugging dan pengujian; itu berbeda dari kebutuhan runtime gudang.

Handheld C72 menjalankan aplikasi Android pada unit. Printer CP30EN dikendalikan connector sesuai protokol dan koneksi unit; runtime printer ditetapkan melalui SDK/media PoC. Keputusan reader on-device tidak berarti printer otomatis dapat menjalankan APK atau SDK Windows/Linux.

Nama model yang diberikan pengguna dipertahankan: UR300, C72, CP30EN. Profil label/serial/firmware/module/SDK dicatat saat commissioning. Dokumentasi vendor yang dirujuk menggunakan nama keluarga U300 dan CP30; pencocokan profil bukan izin mengganti nama atau menambah PC pada rancangan reader tanpa revisi desain.

## 1.2 Topologi operasional

```text
C72 [APK operator + SDK + outbox] <--HTTPS--> ERP RFID API
UR300 [APK agent + SDK + outbox] <--HTTPS--> ERP RFID API
CP30EN <--protokol printer--> Print Connector <--HTTPS--> ERP RFID API
ERP RFID API --> WMS / roll / task / movement / print job / audit
```

Ketiga modul memakai satu kontrak integrasi, satu registry perangkat dan satu monitoring ERP. Setiap modul mempunyai adapter hardware sendiri. Code reuse mengikuti runtime dan SDK; kesamaan contract tidak mensyaratkan satu binary untuk Android dan connector printer.

Jika ERP di cloud, C72 dan reader membuat koneksi keluar HTTPS dari gudang. Connector printer ditempatkan pada host yang dapat menjangkau printer atau server dengan rute jaringan yang sesuai. Kegagalan connector printer tidak boleh menghentikan reader. Reader tidak bergantung pada C72 yang dibawa operator.

## 1.3 Sumber kebenaran

| Data/keputusan | Penanggung jawab utama | Middleware menyimpan |
|---|---|---|
| Produk, SKU, LOT, grade, qty/unit dan owner | ERP | Snapshot tugas yang diberi server. |
| Identitas EPC dan relasi tag-roll | ERP | EPC terbaca, expected snapshot dan evidence. |
| Alamat resmi site/warehouse/bin | ERP | Binding device dan target alamat tugas. |
| Reservasi, transfer, receipt, shipment, adjustment | ERP | Referensi task/movement; bukan saldo stok kedua. |
| Antena, trigger, radio dan printer transport | Adapter hardware | Profil terverifikasi serta status lokal. |
| Observasi fisik | Device + ledger middleware | Raw evidence, captured_at, event_id, outbox. |
| Persetujuan operator dan verdict bisnis | ERP | Respons ber-versi dan validity yang dibatasi. |

Read RFID tidak mengukur yard/kg, menetapkan owner, atau membuktikan alamat rak. Qty label dan jumlah tag tidak menggantikan qty barang. Observasi gate tidak mem-post receipt/dispatch sendiri. Transaksi tersebut tetap melalui API bisnis yang sah dan user yang berwenang.

## 1.4 Komponen bersama

| Komponen internal | Tanggung jawab |
|---|---|
| DeviceIdentity | Device ID/key, provisioning, lifecycle, rotasi, binding scope. |
| ConfigRepository | Config version, active profile, staged update dan persistence. |
| ApiTransport | HTTPS, serialization, timeout, correlation ID, typed response. |
| EvidenceStore | Raw observation, task context, captured/received timestamp. |
| OutboxRepository | Persist-before-send, status upload, retry dan quarantine. |
| ClockMonitor | UTC metadata, clock offset/quality dan freshness decision. |
| TelemetryReporter | Hardware/ERP/queue/version health yang dibedakan. |
| DiagnosticsExporter | Log yang dapat direview dengan credential direduksi. |
| ReleaseManager | Build identity, install/update/rollback, schema migration. |

Nama komponen di atas adalah interface desain internal project, bukan nama API SDK Chainway. Tim pengembangan memetakan SDK aktual ke interface tersebut dan mendokumentasikan method/permission/threading yang benar-benar dipakai.

## 1.5 Identitas, waktu dan replay

1. Setiap observasi asli mendapat event_id unik pada device dan ditulis durable sebelum dikirim. Kiriman ulang mempertahankan event_id serta captured_at.
2. batch_id mengidentifikasi paket transport. Replay batch tidak menciptakan observasi baru; server memberi acknowledgement per event.
3. session_id/task_context_id membatasi pekerjaan C72. local_passage_id membatasi lintasan gate. Identitas tersebut tidak boleh tertukar ketika operator berpindah tugas atau reader reboot.
4. Semua waktu API menggunakan ISO 8601 UTC. UI dapat memakai zona lokasi. Waktu monotonic lokal digunakan untuk interval/freshness selama satu boot, bukan mengganti timestamp UTC.
5. mode=backfill mengirim bukti lama untuk rekonsiliasi. Backfill tidak menghasilkan izin fisik hijau pada gate saat ini.
6. EPC internal disajikan kanonik 24 hex uppercase. Raw EPC asing/rusak tetap menjadi evidence/exception; tidak dipotong agar menyerupai tag valid.

## 1.6 Kebijakan antrean dan kegagalan

State outbox: CAPTURED -> PENDING -> IN_FLIGHT -> ACKED. Kesalahan data definitif menuju QUARANTINED; network timeout kembali PENDING dengan ID tetap. Record IN_FLIGHT saat proses mati dipulihkan sebagai pending pada startup. Retry memiliki backoff/jitter serta batas sesuai konfigurasi server.

Event storage mempunyai unique(device_id,event_id), payload digest, context, mode, captured_at, created_at, attempt_count, next_retry_at dan last_error. Update state serta evidence dilakukan atomik di database lokal. ACKED baru diberikan setelah durable acknowledgement event yang tepat. HTTP sukses transport tidak otomatis berarti semua event diterima.

Antrean tidak membuang evidence belum di-ACK untuk memberi ruang. Jika kapasitas penuh, tampilkan/telemetri STORAGE_PRESSURE dan terapkan SOP pembatasan scan. Limit bytes, retensi acknowledged events, queue alert dan backoff merupakan konfigurasi project yang disahkan saat pilot; nilainya tidak dibuat sebagai aturan bisnis fiktif.

Printer memakai ledger output yang berbeda dari outbox RFID. Retry event RFID tidak sama dengan retry pencetakan fisik. Hasil print ambigu harus direkonsiliasi sebelum perintah cetak diulang.

## 1.7 Autentikasi dan otorisasi

X-Device-Key mengidentifikasi perangkat. Sesi user ERP mengotorisasi pembuatan/pemilihan/penutupan tugas, reprint/retag dan acknowledgement alarm. Context token yang diberikan ERP terikat user-device-task-scope-expiry; nama user atau warehouse dalam body bukan sumber izin.

Reader unattended memakai identitas device sendiri dan endpoint device-scoped. Ia tidak menyimpan akun admin untuk membaca gate-state. Credential lokal menggunakan penyimpanan yang sesuai platform; secret tidak masuk log, screenshot atau contoh konfigurasi. Perangkat nonaktif berhenti memulai pekerjaan baru dan menunjukkan status administratif, bukan menandai dirinya online untuk melewati lifecycle.

## 1.8 Config dan versioning

Server memberi schema_version, config_version, hardware_profile, logical gate map, batch/byte limits, heartbeat/telemetry policy, gate freshness, lease policy, dan queue policy. Perubahan disimpan sebagai staged config lalu diterapkan pada safe boundary. Radio/antena/GPIO tidak diganti di tengah passage tanpa menutup context yang sedang aktif sesuai SOP.

Client mengirim app_version, build_id, sdk_profile_id dan supported contract version. Field/mode yang tidak didukung menghasilkan typed error. Middleware tidak diam-diam berpindah ke contract legacy dengan semantik berbeda. Profil SDK serta firmware yang diuji dicatat pada release matrix.

## 1.9 Struktur repository yang direkomendasikan

```text
middleware/
  contracts/          OpenAPI, schema, contoh pesan dan compatibility tests
  android-common/    komponen bersama Android bila SDK/runtime cocok
  handheld-c72/      APK operator C72
  reader-android/    APK agent UR300 on-device
  printer-connector/ service CP30EN dan adapter transport
  qa/                fixture, hardware evidence dan test reports
  docs/              spesifikasi, commissioning dan runbook
```

Struktur adalah rancangan project; bukan folder aplikasi yang sudah diimplementasikan. SDK vendor disimpan/distribusikan sesuai ketentuan vendor. Version dependency dikunci setelah build nyata lolos; tidak diasumsikan semua SDK terbaru cocok dengan unit lama.

## 1.10 Terminologi normatif

WAJIB = kriteria penerimaan. DISARANKAN = pendekatan yang dapat diganti dengan alasan dan bukti setara. OPSIONAL = hanya aktif jika hardware/konfigurasi mendukung. AVAILABLE CONTRACT = kontrak target yang tim pengembangan middleware gunakan pada lingkungan integrasi. No-PC reader = reader dapat beroperasi setelah deployment tanpa proses penghubung pada laptop/PC.

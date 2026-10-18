# 3. Modul Reader UR300 - Agent Android On-Device

**Project:** ERP Kain Nussantara  
**Produksi IT:** PT Kubus Teknologi Indonesia  
**Artefak serah terima:** APK agent reader, source, SDK/profile map, boot/operating runbook dan evidence gate nyata.  
**Arsitektur wajib:** native Android pada reader; operasi harian tanpa laptop/PC penghubung.

## 3.1 Penegasan topologi

```text
Antena/sensor -> SDK native UR300 -> APK agent pada UR300
APK agent -> HTTPS ERP -> verdict/config/ack -> APK -> indikator gate
APK agent -> database lokal/outbox pada reader
```

Agent tidak berjalan pada komputer gudang untuk menerjemahkan pembacaan reader. Reader tidak membutuhkan C72 atau service printer untuk tetap bekerja. Dashboard ERP/layar maintenance boleh digunakan untuk supervisi; keberadaannya bukan prasyarat pembacaan dan upload otomatis setelah provisioning.

Unit yang disediakan mempunyai Android menurut arahan pemilik project. Tim pengembangan mencatat OS/firmware/SDK/install permissions aktual. Jika unit atau akses SDK tidak memenuhi profil, keluarkan RFI hardware kepada penanggung jawab; jangan diam-diam mengubah rancangan menjadi PC gateway.

## 3.2 Tujuan dan input/output

Input hardware: EPC, antenna/channel jika tersedia, RSSI jika tersedia, timestamp SDK jika dapat dibuktikan, trigger/sensor dan error/status radio. Input server: device config, logical gate mapping, allowed movement context, limits/freshness, supervisor acknowledgement dan typed verdict.

Output: raw observations durable, passage/context evidence, live indicator decision yang sah, telemetry dan diagnostics. Output tidak mencakup perubahan saldo/qty yang ditulis langsung oleh APK. Pembacaan valid per EPC tidak disebut muatan lengkap sebelum completion_basis yang diwajibkan ERP terpenuhi.

## 3.3 Stack dan komponen agent

DISARANKAN Kotlin/Java interop untuk SDK Android, database lokal durable, dan service foreground untuk operasi hardware berkelanjutan pada platform yang telah diuji. Upload/backfill dan polling config dipisahkan dari controller RF agar gangguan internet tidak memblokir SDK callback.

| Komponen | Tanggung jawab |
|---|---|
| ReaderBootCoordinator | Startup, profile validation dan recovery persisted state. |
| ReaderSdkAdapter | Init/config/start/stop, callback, capability, release. |
| TriggerInputAdapter | Input sensor yang tersedia dan edge/debounce policy. |
| PassageAssembler | Context lintasan, start/end dan evidence mapping. |
| ObservationJournal | Persist-before-send dan counter raw observations. |
| LiveDecisionClient | Submit live/close passage dan cocokkan response. |
| BackfillWorker | Upload historis tanpa aksi indikator live. |
| GateStatePoller | Device-scoped latched/config state. |
| SignalController | Lampu/buzzer yang didukung, red latch dan neutral/error state. |
| ReaderHealthReporter | Radio/antena/network/queue/config/build status. |

Interface SDK internal: initialize(profile), applyRadioConfig(config), inventoryStart(callback), inventoryStop(), queryHealth(), release(); GPIO methods opsional sesuai mapping SDK nyata. Nama ini adalah interface internal, bukan klaim method vendor tersedia. Akses SDK diserialisasi; output GPIO tidak dipanggil dari callback yang bersaing tanpa controller.

## 3.4 Lifecycle Android dan startup

State utama: UNPROVISIONED -> INITIALIZING -> CONFIGURED -> RUNNING. ERROR_PROFILE, RADIO_UNAVAILABLE, NETWORK_DEGRADED, STORAGE_PRESSURE, ADMIN_DISABLED dan MAINTENANCE adalah state yang dilaporkan terpisah.

Saat boot, agent membaca identity/config, memeriksa integrity schema lokal, memulihkan outbox, membuka adapter SDK dan memulai radio sesuai profil. Context yang terputus reboot dicatat interrupted; pembacaan berikutnya mendapat passage/context baru. Observasi lama tidak diberi event_id baru.

Strategi autostart WAJIB diuji pada build unit: boot receiver, permission, foreground service type, kondisi lock/unlock, OEM autostart/power policy, update dan force-stop. Memilih connectedDevice atau tipe lain harus sesuai fungsi dan prasyarat platform; jangan memilih type sembarang hanya agar service dapat hidup. Work scheduling upload tidak diperlakukan sebagai jaminan loop radio terus-menerus.

Force-stop dan pembatasan OS tidak dianggap selalu dapat dipulihkan oleh kode aplikasi sendiri. Commissioning menentukan kebijakan device management/OEM serta recovery berizin melalui unit. Target penerimaan adalah operasi tanpa PC harian dengan startup/recovery yang dibuktikan, bukan klaim restart abadi tanpa menguji platform.

## 3.5 Direction dan logical gate

Satu physical reader dapat mempunyai satu atau beberapa logical gate yang sudah dipetakan server. Profile menetapkan logical_gate_id, warehouse_id, direction dan antenna/sensor map. Arah tidak berasal dari warehouse bebas pada body API atau dugaan satu nilai RSSI.

Single-direction installation dapat menggunakan mapping tetap yang disahkan. Untuk dua arah, sensor/zone sequence yang teruji atau context server menentukan direction. Jika callback channel tidak cukup membedakan arah, jangan mengaktifkan automatic clearance dua arah; gunakan SOP review yang disediakan config.

Antena/sensor/profile memakai ID stabil dan config_version. Pengubahan mapping diterapkan pada safe boundary; passage aktif mempertahankan version asal. Dua logical gate tidak saling membuka alarm maupun memproses response yang salah scope.

## 3.6 State passage dan observasi

IDLE -> OPEN -> COLLECTING -> CLOSING -> DECISION_PENDING -> FINALIZED. REJECTED/UNKNOWN/INTERRUPTED merupakan hasil final atau exception. local_passage_id dibuat saat opening dan disimpan sebelum menerima events untuk context tersebut.

Boundary berasal dari trigger/sensor jika tersedia, atau profile waktu yang disahkan dan dibuktikan saat kalibrasi. Debounce dan dwell profile bukan angka hardcoded yang sama untuk semua gudang. Reader terus dapat melaporkan raw observation sementara PassageAssembler menghitung unique EPC untuk UI/context.

Repeated RF read tidak diperlakukan sebagai pengiriman ulang transport. Tag diam boleh menghasilkan banyak observasi namun satu evaluasi passage sesuai policy. Re-entry atau passage baru wajib memperoleh evaluasi baru; EPC sama tidak dibuang lintas passage. Metadata ambiguous dipertahankan sebagai evidence.

## 3.7 Flow lintasan live

1. Trigger/profile membuka passage dan menetapkan logical gate/context/config version.
2. SDK membaca tag; agent mempersist observasi dengan event_id, captured_at dan local_passage_id.
3. Agent mengirim live batch yang memenuhi limits. Durable ACK menutup record transport, bukan otomatis memberi green.
4. Pada end boundary, agent menutup capture passage, menunggu ACK durable semua event passage, lalu meminta passage close dengan context/version yang sesuai. Pending/rejected evidence atau capture gap mencegah green; close response yang masih final=false ditindaklanjuti polling gate-state dengan passage yang sama.
5. ERP mengevaluasi movement, anggota manifest, status, lokasi, quality, replay dan completeness yang relevan.
6. Agent menerima final verdict dengan passage ID, decision ID, config/version dan expires_at. Response salah context/basi tidak mengubah indikator.
7. SignalController memperbarui indikator menurut rule red/green/unknown/neutral. Evidence keputusan serta tindakan indikator dicatat.
8. Task receipt/dispatch/putaway yang diperlukan dikerjakan flow ERP; agent tidak menulis qty sendiri.

## 3.8 Aturan indikator

| Kondisi | Aksi yang wajib |
|---|---|
| Fresh final green untuk passage live saat ini | Beri indikasi yang diizinkan config; simpan decision proof. |
| Known invalid/extra/wrong movement atau final red | Tampilkan alarm/indikasi red, red-dominant sampai acknowledgement sah. |
| Missing/unread, arah ambiguous, context/config conflict | UNKNOWN/REVIEW menurut SOP; jangan dianggap semuanya benar. |
| Timeout/ERP unavailable atau verdict expired | Status unknown/hold operasional yang ditetapkan config. |
| Backfill/old response/duplicate transport | Catat/ACK evidence tanpa green untuk lintasan sekarang. |
| Supervisor acknowledge alarm lama | Clear latch sesuai server; tidak menggunakan verdict lama sebagai izin green baru. |
| IDLE tanpa passage aktif | Indikator neutral sesuai config, bukan izin pengiriman. |

Red satu item tidak tertutupi green item lain dalam passage yang sama. Hardware indikator hanya aktif jika profile membuktikan SDK/GPIO/relay tersedia dan konfigurasi instalasinya disahkan. Tim pengembangan menyerahkan mapping, tidak mengarang nomor pin atau rating hardware.

## 3.9 Kelengkapan manifest

ERP memberikan completion_basis: per_epc_only, manifest_subset atau manifest_full. Agent tidak meningkatkan per_epc_only menjadi klaim muatan lengkap. Expected subset dapat mewakili pengiriman parsial yang sah; tidak selalu seluruh SO.

Jika tidak semua tag terbaca, hasil missing/unread perlu SOP checker/rescan. RFID tidak membuktikan barang tak bertag atau tag yang terhalang pasti tidak berada di kendaraan/troli. Pengakuan manual berasal dari user berwenang dan dicatat terpisah dari actual read.

## 3.10 Offline, waktu dan recovery

Raw observation tetap disimpan ketika ERP tidak terjangkau selama policy/capacity mengizinkan. Local passage dicatat dengan status offline/unknown, dan physical clearance mengikuti SOP offline yang disahkan. Reconnect mengirim evidence sebagai backfill, tanpa memutar ulang indikator live atau mengubah captured_at menjadi sekarang.

ClockMonitor mencatat time_quality serta offset yang diketahui. Freshness dinilai pada response/passage yang tepat dengan deadline lokal yang aman; perubahan jam wall clock tidak memperpanjang green tanpa batas. Limit queue, oldest_pending_age dan dropped=0 atau explicit failure count tampil di telemetry.

SDK error ditangani bounded retry dan reinitialize sesuai profile. Reboot, process kill, update dan storage failure tidak menghapus queue. Radio dan upload health dibedakan; heartbeat HTTP yang sukses tidak menyembunyikan radio yang berhenti membaca.

## 3.11 Maintenance dan deployment

Reader menyediakan halaman maintenance minimal atau diagnostics terotorisasi melalui metode unit yang tersedia. Daily operation tidak memerlukan membuka halaman ini. Configure/start/stop/manual test mempunyai audit serta membedakan test source dari data operasional.

Release APK membawa package/signing/build/config compatibility. Instalasi awal dilakukan dengan metode OEM/internal yang sah; identitas device serta server config diprovisioning, lalu boot test, RF test dan network interruption test. OTA/update tidak mengubah mapping atau key diam-diam. Rollback mempertahankan ledger/outbox dan schema compatibility.

## 3.12 Kriteria penerimaan modul

| ID | Kriteria yang wajib dibuktikan |
|---|---|
| RD-01 | Reader menjalankan APK agent native Android tanpa PC runtime. |
| RD-02 | SDK/permission/firmware serta autostart unit tercatat dan diuji. |
| RD-03 | Antena/trigger/direction/logical gate mapping tepat. |
| RD-04 | Passage/re-entry/tag diam tidak mencampur context. |
| RD-05 | Observasi dipersist sebelum send dan retry mempertahankan ID. |
| RD-06 | Final green hanya fresh/current/live/authorized context. |
| RD-07 | Red-dominant latch dan acknowledgement tidak memberi green lama. |
| RD-08 | Completeness/subset/unknown/missing sesuai manifest policy. |
| RD-09 | Offline/backfill/stale response tidak memicu clearance live. |
| RD-10 | Reboot/process death/update/storage error menjaga evidence. |
| RD-11 | Health membedakan radio, ERP, queue, config dan lifecycle. |
| RD-12 | APK/source/SDK mapping/runbook dan evidence fisik diserahkan. |


## 3.13 Urutan integrasi runtime tanpa PC

| Step | Input | Proses dan output |
|---|---|---|
| 1. Boot | Identity/config lokal, runtime OS | Pulihkan schema/outbox, service policy, SDK radio; API-01 memvalidasi binding/profile terbaru. |
| 2. Ready | Logical gate, antenna/sensor profile | Terapkan config pada safe boundary, poll API-04; radio/ERP/latch health terpisah. |
| 3. Open passage | Trusted trigger/direction evidence | Buat local_passage_id; simpan config version, gate, direction dan boundary. |
| 4. Capture | Actual callback EPC/time/metadata | Persist dahulu; API-02 live dengan context passage; ACK setiap event. |
| 5. Close | End boundary dan seluruh capture IDs | ACK barrier; API-05 membawa event count/capture_complete/direction evidence. Pending/error tidak memberi green. |
| 6. Final | ERP decision untuk passage/gate/version yang sama | Poll API-04 bila masih pending; cek final/mode/freshness/allow_live_signal sebelum output indikator. |
| 7. Alarm review | Current latch/decision ID | Supervisor memakai API-06 di ERP atau UI berizin; polling state menghapus latch yang tepat tanpa replay green. |
| 8. Offline/recovery | Local observations/passage dan policy | Mode backfill pada reconnect; archive historical verdict; passage live baru tetap context sendiri. |
| 9. Monitoring | Radio/queue/network/build/clock | API-03 melaporkan health; log keputusan dan tindakan indikator memiliki correlation. |

Installer/debugger digunakan untuk pemasangan dan pengujian. Kabel ke laptop tidak dibutuhkan setelah provisioning/commissioning; reader tidak menunggu aplikasi PC, C72 atau print connector untuk memulai loop SDK.

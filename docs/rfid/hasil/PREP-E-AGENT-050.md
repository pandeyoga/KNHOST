# PREP-E — Aplikasi reader U300 (middleware Android) 0.5.0-lab

**Tanggal:** 9 Nov 2026 · **Pelaksana:** Claude Code (implementer) · **Branch:** `worktree-agent-afde79fdb1f8cf3a5`
· **Commit:** `1b0fc41` (kode, tes, dokumen, APK) → commit laporan ini.
Acuan mengikat: [`KEPUTUSAN_GATE_RFID.md`](../KEPUTUSAN_GATE_RFID.md) (K-RFID-01/09/10), temuan agent di
[`AUDIT_MIDDLEWARE_RFID_2026-11-08.md`](../AUDIT_MIDDLEWARE_RFID_2026-11-08.md) (§3, §7, §8.2–§8.3), kontrak **2.1.0**
dari [`PREP-D1-GATE-V2.md`](PREP-D1-GATE-V2.md). Paralel: paket D2 (backend/frontend — tidak disentuh di sini).
**Tidak ada yang diuji di U300 fisik, photo-eye, atau runtime Android.**

## 1. Ringkasan
- Agent naik ke **0.5.0-lab** (versionCode 5, label LAB) dan memakai kontrak 2.1 penuh: TagSummary + GpiEdge,
  `seq`/`boot_id`, `open_reason`/`close_reason`/`beam_times`/`sensor_health`, `document_session`, kuning.
- **Photo-eye utama + cadangan RF** (K-RFID-01): `PassageMachine` gate satu arah (A masuk, B keluar) — EXITED,
  REVERSED, ABORTED (+ state BETWEEN untuk muatan 1–3 roll yang lebih pendek dari jarak sinar), TIMEOUT, beriringan
  digabung, SENSOR_FAULT → **cadangan RF** (tidak berhenti), pulih otomatis; mode `rf_only` & `legacy_bidirectional`.
- Inventory menyala terus + **RingBuffer** (pre-buffer label depan), **BackgroundLearner** (daftar latar saat IDLE),
  **callback SDK salin-saja** → antrean RAM + `dropped_reads`; ringkasan per EPC × antena per 250 ms dengan cap waktu
  monotonik; multi-batch per siklus.
- Parse RSSI/antena tahan locale; galat terstruktur `detail.code`; setelan radio set + baca ulang (fail-closed); peta
  port → atas/kiri/kanan; pemeriksaan layanan UHF bawaan; indikator 4 GPO; sinkron jam dari setiap respons; config
  segera saat versi beda; antrean berindeks.
- **Mode diagnostik uji meja K-RFID-03** (9 butir audit §7) di aplikasi: aksi ber-PIN, hasil + pengamatan operator,
  ekspor JSON — siap dijalankan saat perangkat datang.
- Semua angka = **titik awal kalibrasi**; K-RFID-03/05/08 tidak diputuskan.

## 2. Berkas (semua di `middleware/u300-agent/` kecuali disebut)
| Berkas | Isi |
|---|---|
| `app/.../core/PassageMachine.java` | State machine lintasan (photo-eye + cadangan RF + dua arah lama) |
| `core/GatePipeline.java` | Rantai thread kontrol: parse → RingBuffer → BackgroundLearner → PassageMachine → Aggregator; antarmuka `Store` |
| `core/Aggregator.java`, `RingBuffer`, `BackgroundLearner`, `BeamDebouncer`, `ReadQueue`, `RawRead`, `Sample` | Ringkasan TagSummary, buffer, daftar latar, debounce, antrean RAM |
| `core/Parse.java`, `Batcher`, `Envelope`, `ErrorPolicy`, `ClockSync`, `Indicator`, `RadioSetup`, `PortProbe`, `Safety` | Parse tahan locale, multi-batch, payload 2.1, galat, jam, 4 GPO, setelan radio, probe port, kebijakan |
| `AgentService.java` | Orkestrasi baru (loop kontrol `gpi_poll_ms`, Store SQLite, transport, gate-state, telemetry, simulasi gate) |
| `Reader.java` | Callback salin-saja, `RadioSetup.Port` di atas SDK, statistik GPI, cek layanan bawaan |
| `Journal.java` | SQLite skema 2 (`items`, `batches.seq/boot`, `bench`) + migrasi 1→2 tanpa menghapus |
| `Config.java`, `Api.java`, `DecisionPolicy.java`, `Telemetry.java`, `Bench.java`, `MainActivity.java` | Profil 2.1 + ekstensi, galat/jam/simulator 2.1, hijau/kuning, telemetry, uji meja, layar |
| `AndroidManifest.xml` | `<queries>` paket `cn.cw.uhf.tcpserver` (Android 11+) |
| `tests/CoreTest`, `PassageMachineTest`, `PipelineTest` (baru), `HostTest`, `DecisionPolicyTest`, `SafetyTest`, `TransportTest` | Tes host |
| `tests/ErpLocalV2Test.java`, `tests/run_erp_local_v2.py` (baru) | Uji integrasi Java → ERP lokal |
| `tests/validate_contract.py`, `test_snapshot.py`, `verify-snapshot.py` | Fixture `Nama#varian`, cek negatif 2.1, template; snapshot skema 2 |
| `test-host.ps1`, `build-debug.ps1`, `run-android-tests.ps1`, `package.py` | `-ToolRoot`/`KN_ANDROID_TOOLS`, `-encoding UTF-8`, `-Offline`, manifest 0.5 |
| `docs/01…05`, `docs/08_PERUBAHAN_050.md` (baru), catatan historis 06/07, `docs/device-config.template.json` | Dokumen & template profil 2.1 |
| `delivery/KN-U300-Agent-0.5.0-lab-debug.apk`, `delivery/KN-U300-Agent-0.5.0-androidTest.apk`, `HANDOVER.json`, `SHA256SUMS.txt`, `tests/lint-results.txt` | Serah-terima (APK 0.4.0 tetap sebagai arsip) |
| `middleware/README.md` | Baris status versi agent diperbarui (0.4.0 → 0.5.0-lab, photo-eye masuk pengadaan) |

## 3. Status temuan audit (sisi agent)
| ID | Status | Catatan |
|---|---|---|
| AUD-MW-01 | **implemented** | (a) TagSummary per jendela 250 ms; (b) multi-batch sampai antrean habis / `upload_budget_ms`; (d) kode galat; luapan `quarantined` (CAPTURE_OVERFLOW) dihitung sebagai diterima server — tidak macet |
| AUD-MW-02 | **implemented** | `PassageMachine` + close 2.1; sensor rusak → cadangan RF + laporan kesehatan |
| AUD-MW-04 | **implemented, menunggu uji meja** | `RadioSetup` set + baca ulang; gagal → tidak mulai. Arti int `getTagFocus/getFastId` & persistensi = butir 4 |
| AUD-MW-05 | **implemented** | `elapsedRealtimeNanos` di callback; `*_mono` + jam server; `getCount/phase/frequency` hanya direkam uji meja butir 3 |
| AUD-MW-06 | **implemented** | `ErrorPolicy` dari `detail.code`; status transport terpisah, pulih sendiri |
| AUD-MW-11 | **implemented** | indeks status + kolom `bytes`; hitung/layar 1×/s; callback tanpa query |
| AUD-MW-12 | **implemented** | `ClockSync` dari setiap respons ber-`server_time` (½ RTT) |
| AUD-MW-13 | **implemented** | versi gate-state tak dikenal → ambil config segera |
| AUD-MW-14 | **implemented, menunggu uji meja** | 4 GPO hijau/kuning/merah/buzzer; polling `gpi_poll_ms` 20; latensi `inputStatus()` di telemetry & butir 8 |
| AUD-MW-19 | **implemented** | `BeamDebouncer` `min_block_ms`/`min_clear_ms`; profil menolak debounce < polling |
| AUD-MW-23 | **implemented, menunggu uji meja** | `Parse` + penghitung `rssi_missing/rssi_invalid/antenna_invalid/antenna_unmapped` |
| AUD-MW-24 | **implemented, menunggu uji meja** | callback salin-saja + `ReadQueue` + `dropped_reads`; laju nyata = butir 7 |

(Status di atas = klaim implementer; verifikasi oleh reviewer.)

## 4. Hasil build & uji (apa adanya)
| Pemeriksaan | Hasil |
|---|---|
| `:app:assembleDebug :app:assembleDebugAndroidTest` (JDK 17, AGP 8.2.2, SDK 34, `--offline` dari cache Gradle lokal) | **BUILD SUCCESSFUL** — tidak ada unduhan, versi AGP/Gradle tidak diubah |
| `:app:lintDebug` | **0 error, 1 warning** (`UnusedAttribute dataExtractionRules`, sama dengan 0.4) |
| `apksigner verify` | APK & androidTest **v2 debug**; `versionCode 5`, `versionName 0.5.0-lab` |
| SHA-256 APK | `9f2b2d281f48da7d4171251283b1b7bfb6637e1e67d143ff372396c7e6ef0c15` (lab-debug) · `82866a786e60a98b07564f46c4e53451cf1946be10be9b49228337248d954b58` (androidTest) |
| `test-host.ps1` | **396 assertion Java PASS**: Safety 27 · Core 91 · PassageMachine 52 · Host 44 · Pipeline 83 · DecisionPolicy 75 · Transport (HTTPS loopback) 24 |
| `validate_contract.py` vs kontrak **2.1.0** | **21 payload / 9 skema PASS** (DeviceConfig, EventsRequest, EventsResponse, PassageClose ×5, GateDecision ×4, GateState ×2, TagSummary ×2, GpiEdge, Telemetry); **9 cek negatif PASS**; template profil (tanpa catatan) PASS, template mentah ditolak |
| `test_snapshot.py` | **9 kasus PASS** (skema 1 & 2) |
| **Integrasi Java → ERP lokal** (`tests/run_erp_local_v2.py`; `kn-tmp-e-mongo` + `kn-tmp-e-be` dari worktree ini, snapshot `kn_test_trial_2026-11-08`, **HTTP** lokal) | **41 assertion PASS** — GREEN `document_session` trip parsial (`pending` 3, `background` 1, 3 envelope `seq` 0–2 tanpa celah); sinar macet → SENSOR_FAULT → CANCELLED; cadangan RF → REVIEW kuning tanpa kunci; kosong & mundur → CANCELLED; EPC asing kuat → RED + kunci gate; telemetry 0.5 diterima; key salah → AUTH_INVALID → blokir. Putaran ulang tanpa memulihkan data: roll sama → RED `REPLAY_EXIT` (benar) |
| Runtime Android / perangkat | **tidak dijalankan** (tidak ada perangkat/emulator) |

HTTPS lokal tidak dipakai untuk uji integrasi (TLS sudah dibuktikan `TransportTest`); kontainer `kn-tmp-e-*` dan
`backend/.env` sementara sudah dihapus.

## 5. Uji meja K-RFID-03 yang siap dijalankan (mode diagnostik, layanan agent berhenti)
1. Format `getAnt()` (string mentah + parse, `getANT()`).
2. Format `getRssi()` pada locale perangkat (N/A, desimal koma, min/maks).
3. `getCount()`, phase/frequency (`InventoryParameter` — API ada di AAR), selisih `getTimestamp()`.
4. Gen2 (14 field) / TagFocus / FastID / RF link / FastInventory bawaan + setelah `free()/init()`; opsi terapkan profil.
5. Region & firmware (`getVersion`, `getHardwareVersion`); opsi set 63 → baca → kembalikan.
6. Daya 5–33 dBm per port + baca-balik + kembalikan (tanpa memancar).
7. Laju callback 3 × 10 s (kosong / SQLite per bacaan / antrean 0.5).
8. GPI idle, latensi `inputStatus()` p50/p95/maks (inventory mati & menyala), rekam tepi 15 s, opsi siklus GPO 1–4.
9. Layanan bawaan: `sys.uhf.service.enable`, paket `cn.cw.uhf.tcpserver`, port 9160/9260/8080 sebelum/sesudah `init()`.
Hasil + pengamatan operator → **Ekspor seluruh hasil uji meja (JSON)** → bahan keputusan K-RFID-03 (tidak ada
"lulus otomatis"). Prosedur: `middleware/u300-agent/docs/03_COMMISSIONING_DAN_UAT.md` §5.

## 6. Keputusan desain (implementer)
1. Tutup cadangan RF = tidak ada bacaan kuat non-latar `stable_interval_ms` (dokumen keputusan §4.2), bukan "EPC baru".
2. Muatan beriringan digabung → `capture_complete=false` + `sensor_health degraded` (ERP kuning) — kontrak belum punya
   penanda khusus (usulan §9).
3. B↓ sebelum A↓ langsung SENSOR_FAULT (`b_before_a_limit` 1, sesuai audit), dapat diatur.
4. Antena di luar peta / format asing tidak menghentikan capture (0.4 berhenti) — dikirim, server mengkarantina.
5. Layanan UHF bawaan: `action block` bawaan (fail-closed), memakai fakta AAR (`UhfBase.sendBroadcastCloseUHF`:
   `sys.uhf.service.enable`, broadcast `com.cw.reader.TcpServiceDisable` ke `cn.cw.uhf.tcpserver`); tidak menebak API lain.
6. Restart di tengah lintasan → close `ABORTED` tidak lengkap (tanpa klaim lewat), bukan TIMEOUT.
7. Kuning ditahan `yellow_hold_ms`; merah selalu menang; buzzer `buzzer_ms` sekali per kunci baru.
8. 413 → batas body adaptif separuh; PASSAGE_FROZEN → item `rejected` lokal (disimpan, tidak dihitung), transport lanjut;
   EVIDENCE_PENDING → backoff per lintasan.
9. Parameter yang tidak ada di `GateParameters` (min_clear, between/stuck timeout, ambang latar, tuning) di
   `hardware_profile.parameters.agent_tuning` (skema mengizinkan).
10. Simulasi RSSI sengaja memakai format locale Indonesia (`-48,50`).

## 7. Perubahan perilaku dibanding 0.4
- Lintasan tidak dibuka bacaan pertama; tag diam / tag rak tidak membuka/memperpanjang lintasan saat photo-eye sehat.
- Sensor rusak tidak menghentikan reader (0.4: `fault()`); antena tak terpetakan tidak menghentikan capture.
- 401/403 tanpa kode AUTH_* tidak lagi memblokir permanen; 409 CONFIG_REQUIRED tidak memblokir.
- Capture tidak lengkap / cadangan RF di simulator = REVIEW (0.4: UNKNOWN/RED).
- Hijau juga untuk `document_session` dengan sisa > 0 (0.4 hanya `manifest_full` sisa 0).
- DB skema 2 (migrasi otomatis; `events` lama → `events_v1_archive`).

## 8. Sisa / risiko
- **Belum ada bukti perangkat**: format antena/RSSI, setelan radio (arti int TagFocus/FastID, persistensi Gen2), region
  0x3F, laju callback, latensi `inputStatus()`, layanan bawaan setelah reboot — semua butir uji meja.
- **Kalibrasi lokasi**: pre-buffer/tail, `min_clear_ms` (celah garpu), ambang RSSI per antena, parameter latar, ukuran
  rombongan cadangan RF; risiko kuning berlebih atau latar salah tandai sebelum kalibrasi.
- **Muatan berurutan rapat**: roll muatan pertama yang masih terbaca kuat di jendela lintasan berikut bisa memicu
  `REPLAY_CROSSING` (merah palsu) di ERP — butuh aturan server (usulan §9.2) atau SOP jarak antar muatan.
- **Objek pendek mundur dari sinar B** dalam `tail_ms` tidak bisa dibedakan dari lewat (batas dua sinar).
- Runtime Android (SQLite, migrasi 1→2 di perangkat, boot, lifecycle, soak 24 jam) belum dijalankan; APK debug-signed.
- `backend/tests/run_u300_https.py` (0.4, milik backend) hanya mengompilasi 5 berkas agent → **akan gagal kompilasi**
  dengan 0.5 (perlu `core/*.java`, `Telemetry.java`, `-encoding UTF-8`). Tidak diubah (di luar batas paket E); pengganti
  untuk 0.5 = `middleware/u300-agent/tests/run_erp_local_v2.py`.

## 9. Usulan kontrak (tidak diubah — untuk diselaraskan koordinator dengan D2)
1. Penanda lintasan digabung: `PassageClose.boundary_flags: ["OVERLAP"]` (atau `close_reason: MERGED`).
2. Penilaian `t_peak_mono` terhadap `beam_times` di server: EPC yang puncaknya sebelum A↓ dan sudah diklaim lintasan
   sebelumnya di gate yang sama → INFO, bukan `REPLAY_CROSSING`.
3. `TagSummary.antenna_position` opsional (atau server membaca `antenna_positions` profil) untuk skor per antena.
4. Kunci baku di `Telemetry.platform_health` (`sensor_health`, `dropped_reads`, `rssi_missing`, `background_size`,
   `transport_state`) agar aturan kesehatan ERP (AUD-MW-17) dapat memakainya.
5. Pertimbangkan memindah `min_clear_ms`, `between_timeout_ms`, `sensor_stuck_ms`, ambang latar ke `GateParameters`
   bila ERP ingin mengelolanya di panel.

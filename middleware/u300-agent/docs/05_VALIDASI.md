# Validasi versi 0.5.0-lab

ERP Kain Nussantara · PT Kubus Teknologi Indonesia · 9 November 2026

Semua bukti di bawah **tanpa perangkat**: tidak ada pengujian U300 fisik, photo-eye, runtime Android, staging, atau
produksi yang diklaim. APK instrumentasi hanya dikompilasi.

| Pemeriksaan | Hasil |
|---|---|
| `gradlew :app:assembleDebug :app:assembleDebugAndroidTest` (JDK 17, AGP 8.2.2, SDK 34, offline dari cache) | **BUILD SUCCESSFUL** |
| `:app:lintDebug` | **0 error, 1 warning** (`dataExtractionRules` hanya API 31+, sama dengan 0.4) — `tests/lint-results.txt` |
| `apksigner verify` APK aplikasi & androidTest | **v2 (debug)**; `versionCode 5`, `versionName 0.5.0-lab`, minSdk 30, targetSdk 34 |
| `test-host.ps1` — `SafetyTest` | 27 assertion PASS |
| `CoreTest` (parse RSSI/antena, ReadQueue, RingBuffer, BackgroundLearner, Aggregator, Batcher, ErrorPolicy, ClockSync, Indicator, RadioSetup, PortProbe) | 91 PASS |
| `PassageMachineTest` (lewat, berikut, mundur, batal masuk, entry timeout, muatan pendek, beriringan, ekor digabung, timeout, sinar macet → cadangan RF, lemah/latar, pulih, B sebelum A, GPI hilang, RF saja + tag diam, photo-eye sehat, inhibit, manual, dua arah lama, debounce) | 52 PASS |
| `HostTest` (validasi profil 2.1, mode sensor, indikator, GateParameters, tuning, radio, commissioning, simulator) | 44 PASS |
| `PipelineTest` (ujung-ke-ujung: debounce → pipeline → ringkasan → multi-batch seq/boot_id → simulator ERP → close 2.1 → keputusan hijau trip parsial/kuning/batal/cadangan RF, galat terstruktur, luapan, telemetry) | 83 PASS |
| `DecisionPolicyTest` (0.4 + `document_session` & kuning) | 75 PASS |
| `TransportTest` (HTTPS loopback: header, idempotency, redirect, Retry-After, batas respons, galat terstruktur `detail.code`, 403 proxy, sinkron jam dari `server_time`) | 24 PASS |
| **Total assertion Java host** | **396 PASS** |
| `validate_contract.py` terhadap `OPENAPI_RFID_V2.json` **2.1.0** | **21 payload** (9 skema: DeviceConfig, EventsRequest, EventsResponse, PassageClose, GateDecision, GateState, TagSummary, GpiEdge, Telemetry) PASS; **9** cek negatif PASS; template profil PASS |
| `test_snapshot.py` (skema 1 & 2) | 9 kasus PASS |
| **Integrasi Java → ERP lokal** (`tests/run_erp_local_v2.py`: backend `kn-tmp-e-*` + snapshot `kn_test_trial_2026-11-08`, HTTP lokal) | **41 assertion PASS** — lihat di bawah |

## Integrasi agent → ERP lokal (router/service `rfid_v2` nyata, MongoDB uji)

Kelas agent asli (`Api`, `Config` non-simulasi, `GatePipeline`, `BeamDebouncer`, `Batcher`, `Envelope`, `ClockSync`,
`DecisionPolicy`, `Telemetry`) melawan backend di branch ini (kontrak 2.1, profil diterbitkan dari template):

| Skenario | Keputusan ERP |
|---|---|
| A — trip 1 dari SJ 6 roll bertag (3 roll), label depan dari pre-buffer, tag rak latar; **3 envelope** (`seq` 0–2 tanpa celah) | **GREEN** `document_session`, `pending` 3, `background` 1, `matched` 3; agent menerima hijau |
| B — stacker berhenti, sinar macet 12 s (profil uji) → lintasan ditutup `SENSOR_FAULT` | **CANCELLED** (tanpa roll) |
| B — cadangan RF trip 2 (3 roll kuat + 3 EPC lemah) | **REVIEW** `SENSOR_FAULT` (kuning, tanpa kunci), `weak` 3; agent menyalakan kuning; photo-eye pulih setelah 2 urutan sah |
| C — orang lewat (hanya tag latar) | **CANCELLED** `EMPTY_PASSAGE` |
| D — mundur tanpa roll | **CANCELLED** `PASSAGE_CANCELLED` |
| E — EPC asing bersinyal kuat | **RED** `UNKNOWN_EPC` + gate terkunci; agent tidak hijau/kuning |
| F — telemetry 0.5 | diterima |
| G — key salah | 401 `AUTH_INVALID` → agent memblokir (provisioning ulang) |
| (putaran ulang tanpa memulihkan data) roll trip yang sama dikirim lagi | **RED** `REPLAY_EXIT` — klaim lewat terbukti (perilaku server) |

HTTPS lokal tidak dipakai untuk uji ini (transport TLS dibuktikan `TransportTest`); server uji dihapus setelahnya.

## Yang belum dibuktikan

Runtime Android (SQLite nyata, service, boot, lifecycle), SDK di U300 (format antena/RSSI, setelan radio, laju
callback, latensi GPI, layanan bawaan) — semuanya butir **uji meja K-RFID-03** (dokumen 03 §5) yang sudah disiapkan
sebagai mode diagnostik; wiring photo-eye/indikator; kalibrasi lokasi; soak 24 jam.

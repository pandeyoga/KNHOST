# PREP-D1 — Inti gate ERP: patch Kubus V2 + perbaikan audit sisi server + kontrak 2.1 + simulator lintasan

**Tanggal:** 8–9 Nov 2026 · **Pelaksana:** Claude Code (implementer) · **Branch:** `worktree-agent-ae628851436acce1d`
· **Commit:** `9824240` (patch Kubus diterapkan apa adanya) → `e7d53d1` (perbaikan D1) → commit laporan ini.
Acuan: [`KEPUTUSAN_GATE_RFID.md`](../KEPUTUSAN_GATE_RFID.md) (K-RFID-01/07/09/10 mengikat),
[`AUDIT_MIDDLEWARE_RFID_2026-11-08.md`](../AUDIT_MIDDLEWARE_RFID_2026-11-08.md) (AUD-MW-xx, §8.3).
Di luar cakupan (sengaja): gate → transaksi putaway/transfer/kirim + antrean periksa (paket D2), aplikasi reader
Java 0.5 (paket E). Kode Java `middleware/u300-agent/app/` **tidak diubah**.

## 1. Ringkasan
- Patch `erp-u300-v2.patch` diterapkan: backend bersih (`git apply --check`), `RfidDevicesView.jsx` bentrok 3 hunk →
  digabung manual lalu diganti tombol **Integrasi reader U300** yang membuka panel di `DetailModal`.
- Basis GABUNGAN (K-RFID-07): transport/bukti Kubus V2 dipertahankan (outbox, ACK journaled, close idempoten,
  device key), aturan bisnis tetap `gate_evaluator` (P18 Makloon & Perbaikan utuh), lapisan lintasan baru di server:
  kebijakan alarm K-RFID-09, sesi dokumen bertahap K-RFID-10, kelas sinyal EPC (kuat/lemah/latar/tanpa skor),
  lintasan kosong/mundur, luapan, auto-cocok dokumen, alert kesehatan, parameter gate berversi.
- **Kontrak 2.1.0** (dua salinan identik) — semua field baru opsional; fixture agent 0.4 tetap valid.
- **Simulator lintasan tanpa perangkat**: endpoint admin `POST /api/rfid/v2/ops/devices/{id}/simulate` (10 skenario)
  + `scripts/rfid_v2_simulate.py` (mode `device` lewat X-Device-Key, mode `ops` lewat login admin).
- Jalur lama `/api/rfid/ingest` ditutup untuk perangkat ber-protokol `v2` (otomatis saat profil V2 terbit).

## 2. Berkas
| Berkas | Isi |
|---|---|
| `backend/contracts/rfid_v2.json`, `middleware/u300-agent/contracts/OPENAPI_RFID_V2.json` | Kontrak 2.1.0 (identik byte) |
| `backend/services/rfid_v2_service.py` | Fasad: binding manual, riwayat, **close** (orkestrasi), gate-state, telemetry, bukti, sesi per reader |
| `backend/services/rfid_v2_common.py` | `now/digest/fail(detail.code)/collection(w=majority,j)` , ukuran ringkas (AUD-MW-18) |
| `backend/services/rfid_v2_core.py` | Kontrak & validasi, indeks, profil berversi, protokol, lintasan, binding aktif (TTL), muat bukti |
| `backend/services/rfid_v2_ingest.py` | Penerimaan event 0.4 + TagSummary + GpiEdge: koleksi sendiri, bulk, pesan kapasitas atomik, luapan, seq/boot_id |
| `backend/services/rfid_v2_policy.py` | Kebijakan keputusan (K-RFID-09/10, kosong/mundur, kelas sinyal) |
| `backend/services/rfid_v2_sessions.py` | Klaim crossing tanpa bocor + status/tutup sesi dokumen |
| `backend/services/rfid_v2_latch.py` | Satu kunci per gate + pengakuan (lintasan / kunci gate) |
| `backend/services/rfid_v2_sources.py` | Manifest dari dokumen bisnis (SJ/transfer/putaway/MKO/perbaikan), auto-cocok, kandidat |
| `backend/services/rfid_v2_params.py` | Parameter lintasan per gate (bawaan = titik awal kalibrasi) |
| `backend/services/rfid_v2_health.py` | Aturan kesehatan reader → notifikasi + job |
| `backend/services/rfid_v2_envelope.py` / `rfid_v2_simulator.py` | Pembangun envelope 2.1 (murni) / runner skenario |
| `backend/routers/rfid_v2.py` / `rfid_v2_ops.py` | Endpoint device & ops patch / ops PREP-D1 (prefix `/api`, path `/rfid/v2/...`) |
| `backend/services/rfid_ingest_service.py` | `assert_legacy_protocol` di `ingest`/`ingest_into_session` |
| `backend/server.py` | Registrasi router `rfid_v2_ops` (indeks V2 sudah dari patch) |
| `backend/services/scheduler_service.py` | +1 job `rfid_reader_health_watch` (5 menit) — **di luar daftar milik D1, tambahan kecil** |
| `scripts/guardrails/verify_auth_coverage.py` | +5 entri PUBLIC_ALLOWLIST endpoint device-key V2 (pola sama dengan `/rfid/ingest`) |
| `scripts/rfid_v2_simulate.py` | Skrip simulator (stdlib saja) |
| `frontend/src/features/rfid/{U300Operations,U300DocSession,U300PassageList}.jsx`, `u300Labels.js`, `RfidDevicesView.jsx` | Panel U300 (komponen KN, istilah Indonesia) |
| `backend/tests/test_prep_d1_gate_v2.py`, `frontend/src/features/__tests__/prepD1GateV2.test.js` | Tes baru |
| `backend/tests/run_rfid_v2_{integration,extended}.py` | Ekspektasi "roll kurang" disesuaikan K-RFID-10 (lihat §4) |
| `backend/tests/test_iter117_p09.py` | Fixture transfer kini memuat `items[].rolls[]` (lihat §4) |

## 3. Status temuan audit yang disentuh
| ID | Status | Catatan |
|---|---|---|
| AUD-MW-01 | **sebagian** (sisi server) | (c) luapan → ACK `quarantined` durable di `rfid_v2_overflow` + REVIEW `CAPTURE_OVERFLOW`, tidak ada 409 permanen; (a) TagSummary di kontrak 2.1 & diterima server; (b)/(d) multi-batch & kode galat di agent = paket E |
| AUD-MW-02 | **sebagian** (sisi server) | `open_reason/close_reason`, GpiEdge, CANCELLED, REVERSED/ABORTED, TIMEOUT, SENSOR_FAULT/RF_FALLBACK dinilai server; state machine photo-eye di agent = paket E |
| AUD-MW-03 | **selesai** | K-RFID-09: RED hanya pelanggaran; kuning tanpa kunci; satu kunci per gate; `reason_codes[]` + `reasons[]` + verdict terberat |
| AUD-MW-06 | **sebagian** | Server: `detail.code` AUTH_REQUIRED/AUTH_INVALID (401), ADMIN_DISABLED (403, retryable), CONFIG_REQUIRED (409, retryable), PASSAGE_FROZEN, dsb. di `x-error-codes`; penanganan di agent = paket E |
| AUD-MW-07 | **sebagian** | Projection `{'decision':1}` di gate-state; bukti di koleksi sendiri (unik lintasan+item) + bulk; tag/roll via `$in`; evaluasi `gate_evaluator` per roll masih beberapa query/roll (paralel 25) — **uji beban 2.000 roll belum** |
| AUD-MW-08 | **selesai** (server) | Periksa semua klaim dulu → sisipkan sekaligus → kompensasi hanya milik lintasan sendiri; RED tidak memasang klaim. Alur koreksi klaim beraudit = D2 |
| AUD-MW-09 | **selesai** | `rfid_devices.protocol` (`legacy`/`v2`), otomatis `v2` saat profil terbit, admin bisa ubah; jalur lama 409 `PROTOCOL_V2_DEVICE`; uji regresi gate lama dijalankan (§5) |
| AUD-MW-10 | **sebagian** | Panel memakai komponen KN, istilah Indonesia, status kuning, daftar alasan, kesehatan, kunci gate; antrean periksa lengkap & izin ack terpisah = D2 |
| AUD-MW-15 | **selesai** | Auto-cocok dokumen aktif gudang/arah (`auto_match`, bisa dimatikan per gate); binding manual tetap + TTL `manual_binding_ttl_s` + lepas |
| AUD-MW-16 | **selesai** | `GateAcknowledge` = implementasi (`device_id`,`note`, opsional `latch_id`/`decision_id` → 409 `STALE_ACKNOWLEDGE`); `ErrorResponse {detail}`; 16 endpoint `/ops/*` di OpenAPI |
| AUD-MW-17 | **selesai** (ambang = titik awal) | READER_STOPPED / TELEMETRY_STALE / QUEUE_RISING → notifikasi kepala gudang & manager saat aturan berubah aktif; dipicu telemetry, layar, job 5 menit |
| AUD-MW-18 | **selesai** (server) | Ukuran body dihitung separator ringkas |
| AUD-MW-22 | **selesai** (server) | K-RFID-10: sesi dokumen bertahap; `counts.pending` = sisa; tutup sesi → `ROLLS_MISSING` (kuning) |
| AUD-MW-04/05/11–14/19–21/23/24 | **belum** | Agent/perangkat (paket E) atau di luar D1 |

## 4. Perubahan perilaku (dibanding patch Kubus 0.5 apa adanya)
1. **Roll kurang per lintasan bukan merah lagi**: lintasan parsial yang semua roll kuatnya milik dokumen = **GREEN**
   dengan `counts.pending` = sisa (dua ekspektasi di `run_rfid_v2_integration/extended.py` disesuaikan). Agent 0.4
   (`DecisionPolicy.validGreen` mensyaratkan `pending = 0` & `manifest_full`) tetap **tidak** menyalakan hijau pada trip
   parsial → kompatibel mundur fail-closed; hijau per trip butuh agent 0.5 (`document_session`).
2. **REVIEW tidak mengunci** (`latched=false`), `GATE_LATCHED` paksa dihapus; satu kunci per gate.
3. Lintasan 0 bukti / kosong / mundur tanpa roll → **CANCELLED** (dulu REVIEW/RED terkunci).
4. EPC/antena tidak valid (`quarantine`) → REVIEW `QUARANTINED_EVIDENCE` (dulu RED `MANIFEST_MISMATCH`).
5. Tag lemah (RSSI < ambang) atau ditandai latar diabaikan (dicatat `weak/background`), tidak pernah alarm/klaim.
   Bacaan tanpa RSSI (`unscored`) diperlakukan seperti kuat; EPC asing tanpa skor → REVIEW (bukan RED).
6. Klaim crossing dipasang untuk GREEN **dan** REVIEW yang barangnya jalan (klaim bertanda `review: true`), tidak untuk
   RED/CANCELLED/mundur/TIMEOUT/konteks dokumen tidak valid.
7. Tanpa binding manual: auto-cocok (bawaan aktif). Binding manual kedaluwarsa 4 jam (titik awal) atau dilepas.
8. Perangkat dengan profil V2 terbit tidak bisa lagi memakai `/api/rfid/ingest` / simulator gate lama (409).
9. Resolver transfer patch (keanggotaan roll dari `items[].rolls[]`) memengaruhi jalur lama: `test_iter117_p09`
   `test_wh_transfer_green_at_destination` memakai transfer sintetis TANPA items → merah. Data nyata (17/17 transfer di
   snapshot uji memuat `items.rolls`, 0 roll ter-reservasi di luar daftar) → fixture tes diperbaiki, aturan
   ketat dipertahankan (fail-closed).
10. Path router V2 tidak berubah dari sisi klien (`/api/rfid/v2/...`); deklarasi kini prefix `/api` agar allowlist
    guardrail tidak generik.

## 5. Kontrak 2.1 ringkas untuk paket E (agent 0.5)
- **Envelope `EventsRequest`**: `seq` (urut per `boot_id`), `boot_id`, `sent_at`; isi boleh `events` (0.4),
  `tag_summaries[]` (≤ 500/batch) dan/atau `gpi_edges[]` (≤ 200); minimal satu tidak kosong. Respons: `event_acks`,
  `summary_acks`, `edge_acks` (`ItemAck`), `last_seq`, `seq_gap`.
- **`GpiEdge`**: `edge_id` (stabil), `sensor` A|B (A = mulut masuk, B = mulut keluar), `state` blocked|clear,
  `t_mono` (ms `elapsedRealtime`), `t_wall`.
- **`TagSummary`** per lintasan × EPC × antena: `summary_id` (stabil), `raw_epc`, `epc`, `antenna`,
  `first_seen/last_seen` (+`_mono`), `peak_rssi`, `t_peak` (+`_mono`), `count`, `mean_rssi`,
  `buckets[{t_off,n,max_rssi}]`, `in_background` (true/false/null), `time_quality`. Ulang = `duplicate`, isi beda = 409.
- **`PassageClose`** tambahan: `open_reason` BEAM_A|RF_FALLBACK|MANUAL, `close_reason`
  EXITED|REVERSED|ABORTED|TIMEOUT|SENSOR_FAULT|MANUAL, `window_start`, `beam_times`, `pre_buffer_ms`, `tail_ms`,
  `observed_summary_count`, `observed_edge_count` (wajib = item ter-ACK termasuk quarantined), `sensor_health`.
- **`GateDecision`**: verdict + `CANCELLED`; `reason_codes[]`, `reasons[{code,level RED|REVIEW|INFO,...}]`,
  `indicator` GREEN|YELLOW|RED|OFF, `binding_mode`, `sources[]`, `latch_id`, `simulated`; `counts.pending` = sisa roll
  dokumen; `weak/background/overflow/already_passed`. `completion_basis` baru `document_session`.
- **`GateState`**: `latched` = kunci GATE (bukan lintasan); `latch_since`, `latch_reason_codes`, `latch_passage_count`.
- **`LogicalGate.passage_parameters`** (`GateParameters`): pre_buffer_ms 3000, tail_ms 1500, min_block_ms 50,
  entry_timeout_ms 10000, max_passage_ms 30000, stable_interval_ms 3000, bucket_ms 250, rf_fallback_group_size 3,
  rf_fallback_window_ms 1500, rssi_strong_dbm{ant}, rssi_default_strong_dbm −65, background_retention_s 86400,
  auto_match true, manual_binding_ttl_s 14400, rf_fallback_review true — **semua titik awal kalibrasi**.
- **Galat**: `{"detail": {"code","message","retryable","details"}}`; daftar kode di `x-error-codes`
  (ADMIN_DISABLED & CONFIG_REQUIRED = polling lambat, bukan blokir).
- Agent hijau hanya bila: verdict GREEN, `allow_live_signal`, gate-state `latched=false`, final, segar (aturan 0.4
  tetap); untuk `document_session` `counts.pending` boleh > 0. Kuning = REVIEW (lampu kuning/GPO ke-3).

## 6. Bukti uji (apa adanya; lingkungan `kn-tmp-d1-*`, snapshot `kn_test_trial_2026-11-08`)
| Pemeriksaan | Sebelum (HEAD `0ed4ea8`) | Sesudah |
|---|---|---|
| `test_prep_d1_gate_v2.py` (baru: HTTP + izin + device key) | — | **18 passed** |
| Jest `prepD1GateV2.test.js` (baru) | — | **6 passed**; `phase3P8Activation` 9 passed |
| ESLint berkas frontend D1 | — | **0 error**, 1 warning lama (`RfidDevicesView.jsx:70` unused eslint-disable, sudah ada) |
| `run_rfid_v2_integration.py` | 53 PASS (patch mentah) | **53 PASS** (1 ekspektasi diganti K-RFID-10) |
| `run_rfid_v2_extended.py` | 34 PASS (patch mentah) | **35 PASS** (+1 cek sisa pending) |
| `run_u300_https.py` | tidak dijalankan | **tidak dijalankan**: butuh JDK 17 + jar org.json di lingkungan yang sama dengan backend (host tidak punya dependensi Python backend; kontainer tanpa JDK; skrip memakai `javac.exe`) |
| `middleware/u300-agent/tests/validate_contract.py` (fixture 0.4 vs kontrak 2.1) | — | **PASS** 6 skema + negatif; `test_snapshot.py` 5 PASS |
| `test_iter117_p09.py` | 18 passed | **18 passed** (setelah fixture transfer diberi `items.rolls`; tanpa itu 1 gagal — §4.9) |
| `test_iter118_p10.py` | 8 passed | **8 passed** |
| `test_iter263_wms_rfid_r0r1r2.py` | 30 passed | **30 passed** |
| `test_fase_sl_rfid_alias.py` | **9 failed** (404 "Inbound task tidak ditemukan" — data snapshot) | **9 failed** (sama, tidak terkait D1) |
| `test_makloon_celup_rolls.py` (P18) | 20 passed | **20 passed** |
| Skrip `rfid_v2_simulate.py` (smoke di kontainer) | — | mode `device` GREEN rc 0; mode `ops` partial_trip GREEN,GREEN rc 0 |

Guardrail (sesudah): custom_modals, error_notice, escape_layers, uom_vocab, knselect_contract, picker_portal,
detail_modal, modal_dismiss, page_tabs, role_label, rfid_tag_unique, notification_audience **PASS**. Ratchet
(baseline → sesudah): atomic_claim 6 → **6** (BELUM DITINJAU 77 → 77), auth_coverage 8 → **8** (endpoint V2 tidak
menambah), ref_unlink 3 → **3**, to_list_bound 6 → **6**, qty_dual 5 → **5**, numeric_bounds HARD 3 → **3**.
`verify_state_machine.py` tidak dijalankan (sesuai brief); CODEBASE_MAP tidak diregenerasi.

## 7. Keputusan desain (implementer)
- **Kelas sinyal** per EPC dari puncak RSSI per antena vs ambang per antena (`rssi_strong_dbm`, bawaan −65 dBm);
  `in_background` dari agent dipercaya (daftar latar dibangun di agent, paket E).
- **RED vs REVIEW**: semua kode merah `gate_evaluator` = pelanggaran (termasuk NOT_RELEASED/DOC_MISSING: roll keluar
  tanpa dokumen aktif). Dokumen binding dibatalkan → RED `DOC_CANCELLED`; tidak aktif lain → REVIEW. Pelanggaran di
  lintasan mundur/batal diturunkan ke INFO + REVIEW `REVERSED_WITH_ROLLS` (barang tidak keluar).
- **Klaim pada REVIEW**: barang kuning tetap jalan (K-RFID-09) → roll diklaim lewat (bertanda `review`) agar sesi
  dokumen tidak menghitungnya dua kali; D2 yang memeriksa/mengoreksi.
- **Kunci gate** di koleksi sendiri (`rfid_v2_gate_latches`, CAS aktif/latch_id); pengakuan lintasan anggota kunci
  juga melepas kunci; pengakuan memakai sesi pengguna `wms.scan` + cakupan entitas dokumen.
- **Auto-cocok** di saat close (bukan saat lintasan dibuka) dari movement aktif roll kuat; identitas sumber sama
  dengan `gate_evaluator` sehingga `expected_source` & klaim konsisten.
- **Kapasitas** per lintasan (event 10.000, ringkasan 10.000, tepi 500, 32 MB) — titik awal.
- **Simulator** tidak membuat stok/dokumen palsu; memakai dokumen aktif gudang; lintasan/klaim bertanda `simulated`.
- Job kesehatan ditambahkan ke `scheduler_service.JOBS` (berkas bersama; 8 baris aditif) karena telemetry basi hanya
  bisa dideteksi pemicu dari luar perangkat.

## 8. Sisa (butuh perangkat / keputusan / paket lain)
- K-RFID-03 (uji meja SDK), K-RFID-05 (setelan reader & kabel), K-RFID-08 (target uji) **tetap terbuka** — semua
  ambang/parameter di sini titik awal kalibrasi.
- Paket E: agent 0.5 (state machine photo-eye + cadangan RF, TagSummary, seq/boot_id, multi-batch, penanganan
  `detail.code`, lampu kuning, `document_session`). Paket D2: gate → transaksi + antrean periksa + koreksi klaim
  beraudit + penutupan sesi otomatis saat SJ/transfer/putaway ditutup + izin ack terpisah.
- Uji beban 2.000 roll / 10.000 ringkasan (AUD-MW-07) dan `run_u300_https.py` (butuh JDK 17 + org.json).
- `middleware/README.md` butir 2 ("Patch ERP BELUM diterapkan") perlu diperbarui saat branch ini di-merge.
- Penamaan alamat rak/bin, interlock pasangan gate berdampingan (K-RFID-04) belum disentuh.

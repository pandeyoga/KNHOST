# Reader U300 — perubahan 0.5.0 LAB (paket PREP-E)

ERP Kain Nussantara · Production IT PT Kubus Teknologi Indonesia · 9 November 2026 · **LAB, belum produksi**

Versi ini menyesuaikan agent dengan keputusan pemilik di
[`docs/rfid/KEPUTUSAN_GATE_RFID.md`](../../../docs/rfid/KEPUTUSAN_GATE_RFID.md) (K-RFID-01 photo-eye utama + cadangan
RF, K-RFID-09 merah hanya pelanggaran, K-RFID-10 sesi dokumen bertahap), temuan agent di
[`AUDIT_MIDDLEWARE_RFID_2026-11-08.md`](../../../docs/rfid/AUDIT_MIDDLEWARE_RFID_2026-11-08.md) (§3, §7, §8.2–§8.3) dan
**kontrak 2.1.0** sisi server ([`PREP-D1`](../../../docs/rfid/hasil/PREP-D1-GATE-V2.md)). Tidak ada yang diuji di U300
fisik atau runtime Android: semua bukti = tes host, build, lint, dan simulasi (lihat dokumen 05).

## 1. Ringkasan perubahan

| Area | 0.4.0 | 0.5.0 |
|---|---|---|
| Batas lintasan | dibuka bacaan pertama, ditutup jeda 3 s / 30 s; sensor = arah | **state machine gate satu arah**: A↓ buka (window = A↓ − pre_buffer), B↓ masuk, bebas (B terakhir) → ekor → `EXITED`; mundur → `REVERSED`; batal masuk → `ABORTED`; `TIMEOUT`; sensor rusak → `SENSOR_FAULT` → **cadangan RF** (tidak berhenti) |
| Pre-buffer | tidak ada (RF menyala, bacaan sebelum lintasan hilang) | inventory menyala terus + **RingBuffer RAM ±10 s**; label depan sebelum sinar ikut lintasan |
| Tag latar | tidak ada | **BackgroundLearner** saat IDLE (EPC × antena × RSSI biasa); `in_background` di ringkasan; lepas bila melonjak/antena lain; laporan "kronis" di telemetry |
| Callback SDK | lock global + scan antrean + `StatFs` + INSERT per bacaan | **salin saja** ke antrean RAM terbatas; `dropped_reads` dihitung; thread kontrol menulis batch |
| Data ke ERP | 1 event per bacaan | **TagSummary** per lintasan × EPC × antena (count, puncak/rata-rata RSSI, first/last/t_peak monotonik + jam, bucket 250 ms) + **GpiEdge**; event 0.4 lama tetap terkirim |
| Envelope | — | `seq` per `boot_id`, `sent_at`; **multi-batch** per siklus sampai antrean habis/anggaran waktu |
| RSSI / antena | `Double.valueOf` (gagal diam-diam pada locale id-ID); antena wajib persis "1"…"8" | parse **tahan locale** ("-58,30", "N/A", "−58.3 dBm"); antena "1"/"01"/"ANT1"/"port1", basis 0/1; yang gagal dihitung di telemetry, bukti tetap dikirim |
| Galat ERP | 401/403 blokir permanen; 400/409 blokir kontrak | keputusan dari **`detail.code`**: hanya AUTH_* yang memblokir; ADMIN_DISABLED / CONFIG_REQUIRED / 403 tanpa kode = **polling lambat, pulih sendiri**; 413 → pecah adaptif; PASSAGE_FROZEN → tolak lokal (tidak macet); EVIDENCE_PENDING → coba ulang per lintasan |
| Setelan radio | verifikasi region & daya | **set + baca ulang** region, daya per port, Gen2 (session/target/Q…), TagFocus, FastID, RF link, filter; gagal → tidak mulai |
| Peta antena | — | `antenna_positions` port → atas/kiri/kanan (wajib saat commissioned) |
| Indikator | merah/hijau | **4 GPO: hijau / kuning / merah / buzzer**; kuning = REVIEW (barang jalan, antrean periksa); merah = kunci gate; buzzer saat kunci baru |
| Hijau | hanya `manifest_full` & sisa 0 | juga **`document_session`** dengan `counts.pending > 0` (trip parsial, K-RFID-10) |
| Jam | sinkron dari config tiap 60 s | sinkron dari **setiap** respons ber-`server_time` (koreksi ½ RTT) |
| Versi config | gate-state beda versi → exception → offline ≤ 60 s | ambil config **segera** |
| Antrean | `SUM(LENGTH)` seluruh histori per bacaan, layar 10×/s | indeks status + kolom `bytes`, dihitung 1×/s |
| GPI | dipoll 100 ms, debounce 10–2000 ms tidak konsisten | dipoll `gpi_poll_ms` (awal 20 ms), debounce `min_block_ms` / `min_clear_ms`, statistik latensi `inputStatus()` |
| Layanan UHF bawaan | tidak diperiksa | cek `readTcpServiceState()` + paket `cn.cw.uhf.tcpserver` + port 9160/9260 sebelum & sesudah `init()` |
| Uji meja K-RFID-03 | daftar di audit | **mode diagnostik ber-PIN** 9 butir → hasil + pengamatan operator → ekspor JSON |

## 2. State machine lintasan (gate satu arah, photo-eye)

```text
IDLE ──A↓──▶ ENTERING ──B↓──▶ IN_PORTAL ──semua bebas, B terakhir──▶ EXITING ──tail_ms──▶ EXITED   (boundary sensor)
ENTERING ──A↑ tanpa B↓──▶ BETWEEN (muatan pendek di antara sinar) ──B↓──▶ IN_PORTAL
BETWEEN / ENTERING ──between_timeout / entry_timeout──▶ ABORTED                                  (boundary cancelled)
IN_PORTAL ──semua bebas, A terakhir──▶ REVERSED                                                 (boundary cancelled)
IN_PORTAL ──A↓ lagi saat B terhalang── / EXITING ──A↓──  → lintasan DIGABUNG (merged): sensor_health degraded,
                                                             capture_complete=false → ERP menilai kuning
lintasan terbuka ≥ max_passage_ms ──▶ TIMEOUT (boundary max_duration)
sinar terhalang > sensor_stuck_ms · B↓ sebelum A↓ · inputStatus() gagal ──▶ SENSOR_FAULT → CADANGAN RF
CADANGAN RF: ≥ rf_fallback_group_size EPC kuat non-latar dalam rf_fallback_window_ms → buka RF_FALLBACK
             (window = bacaan kuat pertama − pre_buffer); tidak ada bacaan kuat non-latar stable_interval_ms → tutup
             SENSOR_FAULT (boundary idle_timeout); pulih otomatis setelah sensor_recovery_sequences urutan A↓→B↓→bebas sah
```

- Window lintasan tidak pernah dimulai sebelum lintasan sebelumnya ditutup (tiap bacaan masuk tepat satu lintasan).
- Photo-eye sehat: bacaan RF **tidak** membuka atau memperpanjang lintasan (tag diam / tag rak tidak berpengaruh).
- Gate tanpa sensor (`sensor_bindings` kosong): mode `rf_only`, `open_reason RF_FALLBACK`, `sensor_health absent`.
- Gate dua arah lama (`direction: bidirectional`): mode `legacy_bidirectional` — buka oleh tepi/bacaan kuat, tutup
  sepi `passage_idle_close_milliseconds`, arah dari urutan dua tepi aktivasi (`sensor_sequence` seperti 0.4).
- Muatan pendek (1–3 roll dibawa orang, lebih pendek dari jarak A–B 1,5 m) membebaskan A sebelum memotong B: ditangani
  `BETWEEN`. Keterbatasan dua sinar: objek pendek yang sampai B lalu mundur dalam `tail_ms` tidak bisa dibedakan dari
  lewat — SOP melarang mundur (K-RFID-06).

## 3. Arsitektur thread

```text
callback SDK ──salin (EPC/TID/antena/RSSI + elapsedRealtimeNanos)──▶ ReadQueue RAM (penuh → dropped_reads)
thread kontrol (tiap gpi_poll_ms): inputStatus() → BeamDebouncer A/B ─┐
                                   kuras ReadQueue → Parse ────────────┴─▶ urut waktu ─▶ GatePipeline
       GatePipeline: RingBuffer · BackgroundLearner (IDLE) · PassageMachine · Aggregator (TagSummary)
       → SQLite: lintasan OPEN, GpiEdge (pending), draf ringkasan tiap checkpoint_ms, close (CLOSING) — transaksi
       → indikator 4 GPO (padamkan dulu, lalu nyalakan)
thread jaringan (1 s + segera setelah close): config · multi-batch /events · /close · /gate-state · telemetry
```

Kelas murni (tanpa Android, teruji di host) ada di `core/`: `Parse`, `RawRead`, `Sample`, `ReadQueue`, `RingBuffer`,
`BackgroundLearner`, `BeamDebouncer`, `PassageMachine`, `Aggregator`, `GatePipeline`, `Batcher`, `Envelope`,
`ErrorPolicy`, `ClockSync`, `Indicator`, `RadioSetup`, `PortProbe`, `Safety`.

## 4. Penyimpanan (SQLite skema 2)

- `items(kind, id)` — `event` (0.4), `summary` (draf → pending saat lintasan ditutup), `edge`; status
  `draft/pending/acked/quarantined/rejected`; kolom `bytes` untuk hitung antrean berindeks.
- `batches` — body persis untuk retry + `seq`, `boot`.
- `passages` — `close_attempts`, `close_due` (EVIDENCE_PENDING tidak menahan lintasan lain).
- `bench` — hasil uji meja + pengamatan operator.
- **Migrasi 1 → 2** otomatis: event 0.4 disalin ke `items`, tabel lama diganti nama `events_v1_archive`, tidak ada
  baris yang dihapus. Restart di tengah lintasan: draf ringkasan dikirim, close `ABORTED` + `capture_complete=false`
  (tanpa klaim lewat di ERP).
- `observed_event_count/summary_count/edge_count` di close = item yang diterima server (acked + quarantined); item
  `rejected` lokal tidak dihitung.

## 5. Ekstensi profil `kn-u300-v1` (hardware_profile.parameters)

| Kunci | Isi |
|---|---|
| `antenna_positions` | port → `atas`/`kiri`/`kanan`/`lainnya`; wajib untuk setiap antena bila `commissioned` |
| `radio.apply` | `true` set + baca ulang; `false` verifikasi saja |
| `radio.region_code` | kandidat **63 (0x3F) Indonesia 920–923 MHz** [DOC] — wajib dikonfirmasi uji meja butir 5 |
| `radio.antenna_power_dbm` | daya per port (titik awal riset ±15–16 dBm konduksi) |
| `radio.gen2` | `query_session`, `query_target`, `q`, `start_q`, `min_q`, `max_q`, `query_sel`, `query_dr`, `query_m`, `query_trext`, `link_frequency`, `select_*` (hanya yang diisi yang diubah) |
| `radio.tag_focus` / `fast_id` / `rf_link` / `filter` | null = tidak disentuh; filter tanpa baca-balik (AAR tidak punya `getFilter`) |
| `agent_tuning.*` | `gpi_poll_ms` 20, `min_clear_ms` 200, `between_timeout_ms` 5000, `sensor_stuck_ms` 45000, `sensor_recovery_sequences` 2, `b_before_a_limit` 1, `ring_buffer_ms` 10000, `read_queue_capacity` 20000, `background_min_reads` 3, `background_min_span_ms` 2000, `background_jump_db` 10, `background_warmup_ms` 5000, `checkpoint_ms` 1000, `upload_budget_ms` 3000, `antenna_index_base` 1, `yellow_hold_ms` (= masa berlaku keputusan), `buzzer_ms` 3000, `builtin_service {ports [9160,9260], action block}` |
| `expected_region_code` / `expected_antenna_power_dbm` | field 0.4 masih diterima (dipetakan ke `radio`, verifikasi saja) |

Dari `logical_gates[].passage_parameters` (GateParameters 2.1) agent memakai `pre_buffer_ms`, `tail_ms`,
`min_block_ms`, `entry_timeout_ms`, `max_passage_ms`, `stable_interval_ms`, `bucket_ms`, `rf_fallback_group_size`,
`rf_fallback_window_ms`, `rssi_strong_dbm`, `rssi_default_strong_dbm`, `background_retention_s`; nilai bawaan sama
dengan server. Profil ditolak (fail-closed) bila: bucket > 400 per ringkasan, `ring_buffer_ms < pre_buffer_ms + 1000`,
`min_block_ms < gpi_poll_ms`, `entry_timeout/tail ≥ max_passage`, sensor A/B tidak lengkap/sama/bukan GPI1–4,
output indikator bentrok, kunci Gen2 asing. Indikator: `green_output`, `red_output` wajib; `yellow_output`,
`buzzer_output` opsional (0 = tidak dipasang).

## 6. Status temuan audit (sisi agent)

| ID | Status | Bukti / catatan |
|---|---|---|
| AUD-MW-01 | **selesai (agent)** | TagSummary per jendela 250 ms, multi-batch per siklus, envelope `seq`/`boot_id`; luapan `quarantined` ditangani (tidak macet). Server (c) sudah D1 |
| AUD-MW-02 | **selesai (agent)** | `PassageMachine` + `open_reason`/`close_reason`/`beam_times`/`sensor_health`/`window_start`; cadangan RF; 52 assertion state machine |
| AUD-MW-04 | **selesai, menunggu uji meja** | `RadioSetup` set + baca ulang, fail-closed; arti int TagFocus/FastID & persistensi = butir 4 |
| AUD-MW-05 | **selesai (agent)** | `elapsedRealtimeNanos` di callback; `*_mono` + jam server; `getCount/phase` hanya direkam di uji meja butir 3 (belum dipakai keputusan) |
| AUD-MW-06 | **selesai (agent)** | `ErrorPolicy` dari `detail.code`; status transport terpisah; HTTPS loopback 24 assertion |
| AUD-MW-11 | **selesai** | indeks status + `bytes`; hitung & layar 1×/s; callback tanpa query |
| AUD-MW-12 | **selesai** | `ClockSync` dari setiap respons ber-`server_time` |
| AUD-MW-13 | **selesai** | versi gate-state tak dikenal → ambil config segera |
| AUD-MW-14 | **selesai, menunggu uji meja** | 4 GPO hijau/kuning/merah/buzzer; polling `gpi_poll_ms` 20; latensi `inputStatus()` di telemetry + butir 8 |
| AUD-MW-19 | **selesai** | `BeamDebouncer` (`min_block_ms`/`min_clear_ms`, cap waktu tepi mentah); profil menolak debounce < polling |
| AUD-MW-23 | **selesai, menunggu uji meja** | `Parse.rssi/antenna` + penghitung telemetry; format nyata = butir 1–2 |
| AUD-MW-24 | **selesai, menunggu uji meja** | callback salin-saja + `ReadQueue` + `dropped_reads`; laju nyata = butir 7 |

## 7. Keputusan desain implementer (bukan keputusan pemilik)

1. **Penutupan cadangan RF** memakai "tidak ada bacaan kuat non-latar selama `stable_interval_ms`" (dokumen keputusan
   §4.2 mengikat), bukan "tidak ada EPC baru" (deskripsi kontrak). Tag diam di muatan berhenti → TIMEOUT, bukan
   lintasan baru berulang.
2. **Muatan beriringan** (A dipotong lagi saat B masih terhalang, atau A↓ selama ekor) digabung menjadi satu lintasan
   dengan `capture_complete=false` + `sensor_health degraded` → ERP menilai kuning (audit §8.3 meminta REVIEW). Kontrak
   2.1 belum punya penanda khusus — lihat usulan §9.
3. **B↓ sebelum A↓** langsung `SENSOR_FAULT` (`b_before_a_limit` 1, sesuai audit). Orang lewat dari arah salah
   (pelanggaran SOP) juga memicu cadangan RF sampai 2 urutan sah.
4. **Antena di luar peta / format tak dikenal** tidak menghentikan capture (0.4 berhenti): bacaan dikirim dan
   dikarantina server (`ANTENNA_NOT_BOUND` → kuning). Dihitung di telemetry.
5. **Layanan UHF bawaan**: bawaan `action block` (fail-closed) bila port 9160/9260 terbuka sebelum atau sesudah `init()`.
   Nama paket `cn.cw.uhf.tcpserver` & properti `sys.uhf.service.enable` diambil dari bytecode AAR
   (`UhfBase.sendBroadcastCloseUHF`/`readTcpServiceState`): SDK sendiri mengirim broadcast
   `com.cw.reader.TcpServiceDisable` saat `init()` bila properti = "1". Agent tidak memanggil API lain.
6. **Kuning** ditahan `yellow_hold_ms` (bawaan = masa berlaku keputusan) hanya untuk keputusan segar lintasan terakhir;
   tidak saat gate terkunci; CANCELLED = padam.
7. **Restart di tengah lintasan** dikirim `ABORTED` (tanpa klaim lewat), bukan TIMEOUT: lebih aman (roll tetap "sisa"
   di sesi dokumen, diperiksa saat dokumen ditutup).
8. **413**: batas body adaptif separuh ukuran batch yang ditolak (mencegah 413 berulang dengan ukuran sama).

## 8. Mode diagnostik uji meja K-RFID-03

Tombol **Uji meja K-RFID-03 (mode diagnostik)** (PIN) — layanan agent harus berhenti (modul dipakai eksklusif).
Sembilan butir audit §7: (1) format `getAnt()`, (2) format `getRssi()` pada locale perangkat, (3) `getCount()`,
phase/frequency (`InventoryParameter`), selisih `getTimestamp()`, (4) Gen2/TagFocus/FastID bawaan + persistensi
`free()/init()` (+ opsi terapkan profil), (5) region 63 & versi firmware (set → baca → kembalikan, opsi), (6) rentang
daya 5–33 dBm per port + baca-balik + kembalikan, (7) laju callback 3 × 10 s (kosong / SQLite per bacaan / antrean
0.5), (8) level idle GPI, latensi `inputStatus()` (inventory mati & menyala, p50/p95/maks), rekam tepi 15 s, opsi
siklus GPO 1–4, (9) layanan bawaan sebelum/sesudah `init()`. Tiap hasil tersimpan (tabel `bench`) dengan status
`selesai_otomatis` / `butuh_pengamatan_operator` / `gagal`; **Catat pengamatan operator** menyimpan verdict + catatan;
**Ekspor seluruh hasil uji meja (JSON)** lewat pemilih berkas. Tidak ada butir yang menyatakan "lulus" sendiri.
Mode simulasi menghasilkan data bertanda `SIMULASI` hanya untuk menguji alur.

## 9. Usulan kontrak (untuk koordinator, diselaraskan dengan D2 — kontrak TIDAK diubah di paket ini)

1. **Penanda lintasan digabung**: `PassageClose.boundary_flags: ["OVERLAP"]` (atau `close_reason: MERGED`) agar ERP
   menampilkan "dua muatan beriringan", bukan "bukti tidak lengkap".
2. **Pembagian bukti antar lintasan berurutan**: roll muatan pertama yang masih terbaca kuat di jendela lintasan
   berikut berisiko `REPLAY_CROSSING` (merah). Usul server menilai `t_peak_mono` terhadap `beam_times`
   (puncak sebelum A↓ lintasan ini dan sudah diklaim lintasan sebelumnya di gate yang sama → INFO, bukan RED).
3. **`TagSummary.antenna_position`** (opsional) atau peta posisi di profil yang dibaca server untuk skor per antena.
4. **Kesehatan sensor di telemetry**: skema `platform_health` bebas; usul kunci baku `sensor_health`,
   `dropped_reads`, `rssi_missing`, `background_size` agar aturan kesehatan ERP (AUD-MW-17) bisa memakainya.
5. **`GateParameters`** belum memuat `min_clear_ms`, `between_timeout_ms`, `sensor_stuck_ms`, ambang latar —
   sementara di `hardware_profile.parameters.agent_tuning`; bisa dipindah bila ERP ingin mengelolanya di panel.

## 10. Yang masih menunggu perangkat / keputusan

- Uji meja K-RFID-03 (9 butir) di U300 nyata; region 0x3F; daya per port; arti int TagFocus/FastID; format antena &
  RSSI; laju callback; latensi `inputStatus()`; perilaku layanan bawaan setelah reboot.
- K-RFID-05 (setelan reader & kabel, peta port), K-RFID-08 (target uji) — tetap terbuka; semua angka titik awal.
- Kalibrasi lokasi: `pre_buffer_ms`, `tail_ms`, `min_clear_ms` (celah garpu), ambang RSSI per antena, parameter latar.
- Runtime Android (instrumentasi SQLite, lifecycle, boot), soak 24 jam inventory menyala terus, suhu.
- Wiring photo-eye 24 VDC → relay → input optocoupler U300 (maks 12 V/50 mA [S]); polaritas `active_state`.
- Release signing, kebijakan retensi histori.

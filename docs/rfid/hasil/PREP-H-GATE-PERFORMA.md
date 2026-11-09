# PREP-H — Performa & ketahanan jalur gate RFID V2

**Tanggal:** 9 Nov 2026 · **Pelaksana:** Claude Code (implementer) · **Branch:** `worktree-agent-a5aea77a6f771f1c8`
(basis `main` `5f1e36e`) · **Commit:** `53a9c0e` (kode + uji + alat) → commit laporan ini.
Status: `implemented_pending_review` (belum diverifikasi reviewer).
Acuan: [`KEPUTUSAN_GATE_RFID.md`](../KEPUTUSAN_GATE_RFID.md) §1, §6–§10 (merah hanya pelanggaran, kuning tanpa kunci,
satu kunci per gate, sesi dokumen bertahap; **tidak ada hijau tanpa keputusan server**; ERP tak terjangkau → gate
padam), [`AUDIT_MIDDLEWARE_RFID_2026-11-08.md`](../AUDIT_MIDDLEWARE_RFID_2026-11-08.md) AUD-MW-07 & target M10 ≤ 3 dtk,
[`PREP-D1`](PREP-D1-GATE-V2.md), [`PREP-D2`](PREP-D2-GATE-TRANSAKSI.md), [`PREP-GELOMBANG-2`](PREP-GELOMBANG-2.md).
Kontrak `rfid_v2.json`, agent `middleware/u300-agent`, `deploy/*` **tidak diubah**. Tanpa peramban.

## 1. Ringkasan
- **Lampu tidak lagi menunggu transaksi gudang.** `close` mengembalikan keputusan sesudah penilaian + klaim; tiba PA,
  terima transfer, dan bukti keluar per trip dikerjakan **pekerja latar** (antrean = dokumen lintasan, CAS + sewa,
  idempoten berlapis) dengan **job ulang otomatis** (2 mnt) + sapuan saat start. Gate IN transfer 500 roll:
  close **159,8 dtk → 0,10 dtk**; SJ 500 roll **6,2 dtk → 0,30 dtk**; 2.000 roll **0,3–0,63 dtk**.
- **Penilaian tanpa N+1**: memo satu lintasan (`GateLookup`) — dokumen movement, SJ per SO×roll, klaim crossing,
  himpunan anggota dibaca sekali per jenis dokumen (`$in`). Keputusan **identik** (uji pembanding 10 jenis kasus).
- **Temuan terbesar: hampir semua koleksi bisnis tanpa index `id`** (181 dari 182 koleksi di DB uji; `inventory_rolls`
  dicari per `id` = COLLSCAN 346.700 dok ±135–263 ms per lookup pada volume sintetis). Index jalur gate ditambahkan.
  Akibat lain yang ditemukan: **startup backend berjam-jam** pada ratusan ribu tag (`retire_orphan_tags` N+1) → diperbaiki.
- **Beban berkelanjutan ×10 puncak** (18.000 roll/jam, 4 gate): close p95 **19,4 dtk → 0,13 dtk**, p99 **29,7 → 0,54 dtk**.
- **Masa simpan bukti** (registri konfigurasi): bukti mentah lintasan > 90 hari & bacaan gate lama > 180 hari diarsip
  JSONL.gz ke `LOCAL_STORAGE_DIR/rfid_archive/` lalu dihapus; keputusan/klaim/sesi/kasus/buku **tidak pernah**.
- **FE**: polling monitor/kios/panel U300/antrean berhenti saat tab tersembunyi + mundur bertahap; status transaksi
  gudang terlihat per lintasan (panel U300) dan jumlah antrean transaksi (tab Antrean periksa).
- **Lingkungan tidak stabil:** VM Docker Desktop host mati/tersendat 5× selama sesi (memori host penuh). Pengukuran
  yang terputus diulang; angka saat mesin bermasalah **tidak dipakai** (§3.6). **Uji inti gate sesudah = sama dengan
  sebelum (semua hijau)**, Jest 17/17, tetapi **perbandingan suite 96 berkas sesudah TIDAK selesai** dan 2 dari 3 uji
  batas kinerja gagal karena lingkungan (§10) — wajib diulang di lingkungan stabil sebelum merge.

## 2. Target (p95) per operasi
Dasar: batas tunggu agent ke ERP **5 dtk** (`Api.java`), target M10 **≤ 3 dtk** dari muatan keluar sampai lampu
(ekor lintasan `tail_ms` 1,5 dtk + kirim sisa batch + close), validitas keputusan `gate_decision_validity_seconds`
5 dtk (agent tidak menyalakan hijau dari keputusan basi → gagal-tertutup). Angka = target implementer, bukan K-RFID-08.

| Operasi | Target p95 | Alasan |
|---|---|---|
| `POST /events` (≤ 400 ringkasan ≈ 270 KB) | ≤ 500 ms | agent mengirim bertahap selama lintasan; 2.000 roll = 10 batch |
| `POST /close` muatan biasa (≤ 200 roll) | ≤ 500 ms | sisa anggaran M10 sesudah ekor 1,5 dtk + RTT gudang→VPS |
| `POST /close` 2.000 roll (kapasitas manifest) | ≤ 2,5 dtk | < 5 dtk batas agent dengan ruang 2× |
| `GET /gate-state` (poll 1×/dtk/gate) | ≤ 100 ms | 4 gate × 1 rps tidak boleh menumpuk |
| `POST /telemetry` (30 dtk/gate) | ≤ 300 ms | tidak kritis lampu |
| Transaksi latar ≤ 200 roll / 2.000 roll | ≤ 15 dtk / ≤ 5 mnt | informasi admin; tidak memblok lampu |

## 3. Hasil ukur sebelum vs sesudah (apa adanya)
**Lingkungan:** kontainer sementara `kn-tmp-h-*` (backend `--cpus 2 --memory 1500m`, satu proses uvicorn seperti
`deploy/Dockerfile.backend`; Mongo 7 `--memory 1500m --wiredTigerCacheSizeGB 0.5` seperti produksi), host Windows +
Docker Desktop yang **dipakai bersama agen lain** (latensi berfluktuasi). Klien uji di kontainer yang sama (tanpa RTT
jaringan — RTT gudang→VPS ditambahkan di §5). **Sebelum** = `5f1e36e` (index lama), **sesudah** = `53a9c0e`.
DB `kn_load` = salinan snapshot `kn_test_trial_2026-11-08` + data sintetis sebesar produksi (alat `synth`):

| Koleksi | Dokumen | Ukuran (tanpa kompresi) | Rata-rata |
|---|---|---|---|
| `inventory_rolls` | 346.700 | 197 MB | 567 B |
| `rfid_tags` | 300.041 (180 rb hidup) | 65 MB | 215 B |
| `rfid_v2_crossings` (90 hari × 6.000 roll) | 534.904 | 230 MB + index 99 MB | 430 B |
| `rfid_v2_summaries` (30 hari × 12.000) | 360.000 | 354 MB + index 59 MB | 984 B |
| `rfid_v2_passages` (90 hari, muatan + kosong) | 21.904 | 33 MB | 1,5 KB |
| SJ / transfer / PA lama | 5.580 / 2.747 / 2.719 | 24 / 9 / 13 MB | 3–4,7 KB |

Profil Mongo (`slowms` 50) & `explain` dari `rfid_v2_loadtest.py` (ringkas di §3.5; berkas JSON mentah ada di
kontainer sementara yang sudah dihapus — ulangi dengan alat yang sama).

### 3.1 Satu lintasan besar (gate kosong, `scenario big`)
| Dokumen × roll | close sebelum | close sesudah | transaksi sebelum (di dalam close) | transaksi sesudah (latar) |
|---|---|---|---|---|
| SJ keluar × 50 | 1.760 ms | **85 ms** | 527 ms | 31 ms |
| SJ keluar × 500 | 6.182 ms (> batas agent) | **296 ms** | 543 ms | 55 ms |
| SJ keluar × 2.000 | tidak diukur (±25 dtk, ekstrapolasi N+1) | **572 ms** | — | 179 ms |
| Transfer masuk × 50 | 16.537 ms | **50 ms** | 16.147 ms | 7,4 dtk |
| Transfer masuk × 500 | 159.796 ms | **104 ms** | 156.427 ms | 30,4 dtk |
| Transfer masuk × 2.000 | tidak diukur (> 10 mnt) | **631 ms** | — | 174 dtk |
| Putaway masuk × 50 | 12.850 ms | **65 ms** | 11.342 ms | 3,7 dtk |
| Putaway masuk × 500 | 91.416 ms | **102 ms** | 89.315 ms | 33,3 dtk |
| Putaway masuk × 2.000 | tidak diukur | **317 ms** | — | 142 dtk |

§3.1 diukur sebelum penyempurnaan pekerja (semafor khusus transaksi berat, mendahulukan permintaan reader, sewa
diperpanjang) — jalur close tidak berubah oleh penyempurnaan itu; §3.2 (hangat), §3.3, §6, §10 memakai kode akhir.
`events` per batch 400 ringkasan: sebelum p95 263–526 ms, sesudah p50 210–250 / p95 230–875 ms (batch pertama
lintasan 2.000 roll paling lambat). Ulangan pertama sebelum (sebelum profiler diperbaiki): SJ 500 = 5.053 ms,
transfer 500 = 178,6 dtk — konsisten.

### 3.2 Empat gate bersamaan (`scenario concurrent`)
| Skenario | Sebelum | Sesudah (pekerja di proses API) | Sesudah (pekerja terpisah) |
|---|---|---|---|
| 4 × 200 roll (2 OUT SJ, 2 IN transfer) | OUT close 4,2 dtk; **IN close gagal** (koneksi diputus uvicorn sesudah ±64 dtk; transaksi selesai 62 dtk di server) | close p95 759 ms (dingin) | — |
| 4 × 500 roll, hangat, 2 putaran | — | close p95 **406 ms** | close p95 **353 ms** (8 close), events p95 1,18 dtk |
| 4 × 2.000 roll (dingin) | — | close p95 3,07 dtk, maks 3,11 dtk | — |

Transaksi 2 × transfer 2.000 roll **bersamaan** di proses API: > 10 mnt (CPU backend 100 % satu inti; pengukuran
dihentikan). OUT tidak lagi menunggu IN: dulu bukti SJ ikut antre di belakang transfer besar (38,6 dtk), kini 0,1–0,3 dtk
(semafor hanya untuk transaksi berat).

### 3.3 Beban berkelanjutan (`scenario sustained`, 5 mnt, 4 gate, ×10 puncak)
**Asumsi puncak (ditulis terbuka):** 6.000 roll/hari total, **30 % dalam 1 jam** (1.800 roll/jam — muat pagi/sore),
muatan rata-rata ±50 roll (180×180 cm, 7 lapis × ±7 roll; 20 % muatan 1–3 roll, 10 % 100–200 roll), satu lintasan
kosong (orang/forklift) per muatan, agent poll gate-state 1×/dtk + telemetry 30 dtk per gate. Dijalankan **×10**
(18.000 roll/jam ≈ 3× volume SEHARI dalam satu jam) agar ada cukup sampel dan ruang tumbuh terlihat.

| ×10 puncak, 5 mnt | Sebelum | Sesudah (proses API) | Sesudah (pekerja terpisah) |
|---|---|---|---|
| Muatan / roll terkirim | 36 / 1.764 | 36 / 1.532 | 36 / 1.539 |
| close muatan p50 / p95 / p99 / maks | 2.215 / **19.366** / 29.664 / 35.159 ms | 51 / **130** / 535 / 745 ms | 52 / 1.307 / 2.251 / 2.717 ms |
| close lintasan kosong p95 | 41 ms | 84 ms | 711 ms |
| events p50 / p95 | 89 / 272 ms | 84 / 156 ms | 91 / 1.755 ms |
| gate-state p95 / maks | 34 / 310 ms | 33 / 1.178 ms | 27 / 177 ms |
| telemetry p95 | 598 ms | 1.014 ms | 216 ms |
| transaksi tuntas p50 / p95 (dari keputusan) | 795 / 18.900 ms | 74 / 3.390 ms | 652 / 6.854 ms |
| CPU backend rata / maks (cgroup, 2 CPU = 200 %) | 17 / 91 % | 12 / 102 % | 29 / 112 % |
| CPU Mongo rata / p95 | 85 / 185 % | 6 / 38 % | 13 / 51 % |
| RAM backend maks / Mongo RSS | 445 MB / 674 MB | 430 MB / 993 MB | 537 MB / 1.047 MB |

Catatan jujur: putaran "pekerja terpisah" diukur lebih dulu, saat agen lain memakai CPU host (mis. `kn-tmp-fix1-be`
98 %); p95-nya lebih buruk dari putaran proses-API meski CPU Mongo rendah — fluktuasi lingkungan bersama, bukan bukti
bahwa pekerja terpisah lebih lambat. Kedua putaran jauh di bawah target. Telemetry p95 ±1 dtk berasal dari cek
kesehatan reader (3 aturan × tulis CAS) yang ikut dijalankan per telemetry — tidak kritis lampu.

### 3.4 Startup backend pada volume produksi
| | Sebelum | Sesudah |
|---|---|---|
| Startup `kn_load` (180 rb tag hidup) | **tidak selesai** — `retire_orphan_tags` mencari roll per tag tanpa index (±135 ms × 180.000 ≈ 6,7 jam); diukur dengan tag sintetis disembunyikan sementara | **55 dtk** (sekali bangun index jalur gate), restart berikutnya 30–77 dtk |

Dua migrasi startup lain (isi `lot_id`, HPP `proxy_demo` per roll) sempat berjalan per roll karena data sintetis awal
tidak punya field itu — artefak data uji; alat `synth` kini mengisinya (roll nyata sudah punya).

### 3.5 Index & `explain` (volume sintetis)
| Query jalur gate | Sebelum (rencana · dok diperiksa · ms) | Sesudah |
|---|---|---|
| `inventory_rolls` `id $in` (lookup lintasan) | COLLSCAN · 346.700 · 263 | IXSCAN `kn_gate_id_1` · 200 · 1 |
| `inventory_rolls` `find_one(id)` (per roll di transaksi) | COLLSCAN · 346.700 · 135 | IXSCAN · 1 · 0 |
| `rfid_tags` `roll_id,status` (antrean periksa, tiba PA) | COLLSCAN · 300.041 · 131 | IXSCAN · 0 · 0 |
| `shipments` `order_id + rolls.roll_id` (resolve_movement) | COLLSCAN · 5.580 · 14 | IXSCAN · 2 · 0 |
| `shipments`/`putaway_orders`/`warehouse_transfers`/`sales_orders` `id` | COLLSCAN · 445–5.580 · 1–6 | IXSCAN · ≤1 · 0 |
| `rfid_v2_passages` antrean transaksi (`gate_txn_state`) | COLLSCAN · 21.904 · 26 | IXSCAN `kn_gate_txn_queue` · 0 · 0 |
| `rfid_v2_passages` retensi (`created_at <`) | COLLSCAN · 21.904 · 20 | IXSCAN `kn_passage_created` |
| `rfid_v2_doc_sessions` terbuka gudang/arah urut terbaru | IXSCAN (warehouse_id,status) + sort | IXSCAN `kn_doc_session_open` |
| `rfid_reads` gate lama (retensi) | COLLSCAN · 10.953 · 11 | IXSCAN `kn_gate_read_type_1__timestamp_1` |
| klaim `_id $in`, bawaan muatan, sesi per dokumen, bukti per lintasan | IXSCAN (index V2 lama) | sama |

Profil Mongo sebelum (transaksi di close): `inventory_rolls` per `id` 943× rata 159 ms, `rfid_tags` update per
`roll_id` 654× rata 111 ms — semuanya COLLSCAN. Sesudah: tersisa `inventory_movements` update per `id` (COLLSCAN 92 rb,
±63 ms, 69× per 2.000 roll; di layanan terima transfer — lihat §9).

### 3.6 Pengukuran terganggu (tidak dipakai)
- 05:17–06:15 WIB: VM Docker mati (`no route to host`); suite pembanding pertama terputus di `test_iter265` → diulang
  penuh dari restore bersih. Ukuran `kn-tmp-h-be` saat itu tidak dipakai.
- 06:55 WIB: mesin Docker mulai ulang sendiri saat backend lama baru start di `kn_load` → diulang.
- 09:10–10:40 WIB: VM Docker mati lagi di tengah uji kegagalan `kill_close` (tidak bisa diulang, §6); 10:45–11:40
  engine menjawab putus-sambung (HTTP 500), restore & suite sesudah 100× lebih lambat → suite dihentikan (§10).
- Penyebab: memori host 16 GB habis (0,6–1,1 GB bebas; beberapa stack agen paralel, mis. kontainer FE agen lain
  2 GB). Stack ini memakai ±1,5–2 GB (Mongo RSS ≤ 1,05 GB + backend ≤ 0,54 GB) dalam batas brief.
- Putaran konkuren pertama sesudah perubahan (4 × 500 p95 6,7 dtk) berjalan tepat sesudah transaksi PA 2.000 roll dan
  tanpa pemanasan (perangkat baru, cache dingin) → diganti putaran hangat (alat kini selalu memanaskan 1 lintasan/gate).

## 4. Kapasitas & pertumbuhan data
**Keputusan lampu:** pada ×10 puncak (≈ 60 muatan bermuatan + 60 kosong per 5 mnt di 4 gate) CPU backend rata 12 %
dari 200 % — kapasitas penilaian jauh di atas 6.000 roll/hari. **Pembatasnya transaksi gudang gate IN** (di luar
lampu): terima transfer ±60–90 ms/roll, tiba PA ±70 ms/roll (2.000 roll ≈ 2,5–3 mnt). Kebutuhan harian ≈ 3.000 roll
IN × 80 ms ≈ 4 mnt kerja pekerja/hari; jam puncak (900 roll IN) ≈ 72 dtk/jam → cukup, tetapi 2 transfer 2.000 roll
bersamaan di proses API memakan > 10 mnt satu inti → alasan rekomendasi pekerja terpisah (§7).

**Pertumbuhan** (ukuran BSON tanpa kompresi dari `collStats` data sintetis; di disk WiredTiger/snappy lebih kecil —
rasio data sintetis 4–7× tidak realistis, perkirakan 2–3×). 6.000 roll/hari, 2 ringkasan/roll (agent nyata: 3 antena &
lebih banyak bucket → ringkasan ×1,5–3):

| Data | Per hari | Disimpan | Ukuran jenuh / per tahun |
|---|---|---|---|
| Bukti mentah `rfid_v2_summaries` (+edges/events/overflow) | 12.000 dok ≈ 13,8 MB (+ index) | **90 hari** (retensi) | jenuh ≈ 1,2 GB (×1,5–3 agent nyata ≈ 1,9–3,7 GB) |
| Klaim crossing `rfid_v2_crossings` | 6.000 dok ≈ 3,7 MB (+3 index) | permanen | ≈ 1,35 GB/thn |
| Keputusan lintasan `rfid_v2_passages` | ±240 dok ≈ 0,4–2,4 MB | permanen | ≈ 0,15–0,9 GB/thn |
| Buku transaksi + sesi dokumen + kasus | ±250 dok ≈ 0,5 MB | permanen | ≈ 0,2 GB/thn |
| Berkas arsip JSONL.gz (disk lokal) | ±2–3 MB | belum ada batas (saran: salin ke luar server) | ≈ 1 GB/thn |

Tanpa retensi, bukti mentah saja tumbuh ±5 GB/thn (≈ 15 GB/thn untuk agent 3 antena). Data permanen ±2–2,5 GB/thn
(tanpa kompresi) — perlu keputusan pemilik bila ingin batas untuk klaim/keputusan lama (§9).

## 5. Jaringan gudang → VPS (50 Mbit/s)
- Ukuran envelope (simulator, 2 ringkasan/roll, 6 bucket): **±1,37 KB/roll** (diukur 1,5 KB/roll termasuk lintasan
  kosong & tepi sinar). Lintasan 2.000 roll = 10 batch = **2,7 MB** → 0,44 dtk pada 50 Mbit/s (6,25 MB/dtk) bila
  dikirim sekaligus; agent mengirim bertahap selama lintasan. Agent nyata (3 antena, bucket 250 ms × 4–8 dtk) bisa
  ±3–5 KB/roll → 2.000 roll ≈ 6–10 MB ≈ 1–1,6 dtk. Gzip body memampatkan JSON ini sangat baik (sintetis 50×,
  nyata kira-kira 5–10×) — **rekomendasi kontrak berikut** (Content-Encoding gzip), bukan perubahan sekarang.
- Volume harian: 6.000 roll × 1,5–5 KB ≈ **9–30 MB/hari**; poll gate-state 4 gate × 1 rps × ±0,6 KB ≈ 20 kbit/s;
  telemetry diabaikan. **50 Mbit/s lebih dari cukup** (< 1 % rata-rata; puncak lintasan 2.000 roll < 2 dtk).
- Yang menentukan lampu adalah **latensi bolak-balik (RTT)**, bukan bandwidth: batch dikirim berurutan → sisa batch
  di ekor × RTT. VPS di Jakarta/Singapura (RTT 10–40 ms) aman; RTT > 150 ms (luar Asia) memakan anggaran M10.

## 6. Uji kegagalan (stack sementara, kode sesudah)
Alat: `scripts/rfid_v2_loadtest.py fault` di `kn_load` (perangkat & dokumen baru per putaran).

| Kegagalan | Hasil |
|---|---|
| **Close ganda bersamaan** (3 close identik serentak, SJ 500 roll) | 1× 200 + 2× **503 `EVIDENCE_PENDING`** (retryable — penghitung lain sedang menilai); **satu** `decision_id`, 500 klaim (tidak dobel), buku transaksi 1 baris `attempts 1`, transaksi `done`. Agent mengulang close → mendapat keputusan yang sama. Uji pytest `test_concurrent_double_close_single_decision_and_ledger` (4 utas + ulang 503 → semua 200, satu keputusan) |
| **Jaringan putus saat batch events** (SJ 500 roll, 3 batch) | respons batch 0 hilang (`ReadTimeout`) → kirim ulang → ACK `duplicate`; batch 1 tertinggal, batch 2 terkirim → `seq_gap=True`; close sebelum batch 1 → **503 `EVIDENCE_PENDING`** (jumlah bukti belum sama); batch 1 dikirim → close **GREEN, 500/500 cocok** |
| **Backend dimatikan di tengah close** (SIGKILL ±250 ms sesudah close 2.000 roll dikirim, lalu close diulang) | **terputus**: mesin Docker host mati bersamaan (09:10 WIB) sebelum hasil tercatat — **belum ada angka**. Perilaku menurut kode: sewa penghitung (15 dtk) basi → close ulang mengambil alih; klaim & jejak sesi idempoten per lintasan; lintasan yang sudah FINAL → keputusan tersimpan dikembalikan |
| **Pekerja transaksi mati di tengah** (SIGKILL saat transfer 500 roll diproses) | **belum dijalankan di stack** (Docker mati). Dicakup uji `test_stale_worker_recovered_by_retry_job_without_double_receipt`: lintasan & buku tertinggal `processing` basi → job ulang mengambil alih (`attempts 2`), semua roll `already`, `receipt_events` tetap 1, gerak stok tidak bertambah |
| **DB lambat** | tidak diukur terpisah (CPU Mongo tidak bisa dibatasi tanpa mengganggu agen lain). Rancangan: close > 5 dtk → agent tidak menerima keputusan → lampu padam (gagal-tertutup, §10 opsi a) → close ulang menunggu penghitung yang sedang berjalan ≤ 3 dtk (tidak menghitung ulang → beban tidak berlipat) → keputusan yang sudah tersimpan dikembalikan; keputusan kedaluwarsa (`expires_at` 5 dtk) tidak pernah dipakai untuk hijau |

Sebelum perubahan (diamati di uji beban, bukan disengaja): close transfer 200 roll > 60 dtk → koneksi diputus uvicorn
(`h11 LocalProtocolError`) sementara transaksi tetap berjalan di server → agent tidak pernah mendapat keputusan.

## 7. Rekomendasi infrastruktur (laporan saja — `deploy/*` tidak diubah)
**VPS dedicated (bukan shared)** — dasar ukur: gate memakai ≤ 1 inti backend saat puncak ×10; Mongo ≤ 2 inti saat
transaksi besar; cache WiredTiger 0,5 GB **penuh** (424–499 MB) pada volume sintetis → halaman dingin & latensi ekor.
| Komponen | Minimum sekarang | Ruang tumbuh 2–3 thn |
|---|---|---|
| vCPU | **4** dedicated (API 2 worker + pekerja gate + Mongo) | 8 |
| RAM | **16 GB** (Mongo cache 6 GB, API+pekerja 2 GB, sisanya OS/page cache/Caddy/frontend) | 32 GB |
| Disk | NVMe SSD **200 GB** (DB ±10–15 GB/thn semua modul + arsip + 14 cadangan harian) | 500 GB |
| IOPS / fsync | ≥ 3.000 IOPS tahan lama, latensi fsync < 2 ms (setiap tulisan gate `j:true`) | — |

- **Proses**: uvicorn **2–4 worker** untuk API; **penjadwal di satu proses saja** (kunci `system_settings.lock` sudah
  mencegah ganda, tetapi pisahkan agar job berat tidak berbagi loop dengan API); **pekerja transaksi gate terpisah**:
  API `KN_GATE_TXN_INPROCESS=0` + `python scripts/gate_txn_worker.py` (kontainer/service sendiri, restart otomatis).
  Dengan > 1 worker uvicorn **wajib** pekerja terpisah (urutan trip per perangkat hanya dijamin dalam satu pemroses).
- **MongoDB**: `--wiredTigerCacheSizeGB` **4–6** (working set: roll+tag+klaim+index ±3 GB setelah 1–2 thn);
  **replica set** (minimal 1 node RS; ideal 3 node untuk HA) → transaksi multi-dokumen (klaim + sesi + keputusan
  atomik) dan **change stream** untuk push SSE layar kios/monitor (mengganti polling). Tanpa RS, `w:'majority'` = 1 node.
- **Cadangan**: `deploy/backup.sh` (mongodump harian + tar `uploads`, simpan 14 hari) menulis ke disk VPS yang sama →
  tambah salinan **di luar server** (object storage/NAS kantor); arsip bukti `uploads/rfid_archive/` ikut tar harian
  (≈ +1 GB/thn ×14 salinan) → sinkron inkremental terpisah lebih hemat. **Uji pulih bulanan** ke DB salinan +
  `scripts/rfid_v2_loadtest.py explain` untuk memastikan index ikut. Dengan RS: PITR dari oplog.
- **Index**: tambahkan index `id` untuk koleksi bisnis lain (181 koleksi tanpa `id` di DB uji; yang disentuh gate
  sudah ditambahkan di sini) — jadikan unik setelah audit duplikat.
- **uvicorn/h11**: sebelum perubahan, close panjang (> 60 dtk) diputus timer keep-alive uvicorn (`LocalProtocolError`
  di log). Sekarang close < 1 dtk; tetap sarankan `--http httptools` + `--timeout-keep-alive 30` dan batas waktu proxy
  Caddy ≥ 30 dtk.

## 8. Keputusan implementer (mohon ditinjau)
1. **Antrean = dokumen lintasan** (field `gate_txn_*`), bukan koleksi baru — satu sumber kebenaran, buku per dokumen
   (`rfid_v2_gate_txn`) tetap dipakai. Status: `pending → processing (sewa STALE_S 120 dtk, diperpanjang tiap 40 dtk)
   → done | error` (jeda 30 dtk, 2, 5, 15, 30, 60 mnt; sesudah 7 percobaan `gate_txn_gave_up` → tombol "Ulangi
   transaksi" di Antrean periksa).
2. **Simulator tetap bertransaksi langsung** (alat admin; hasil deterministik untuk UAT). Lintasan reader sungguhan
   selalu di latar.
3. **Satu penghitung keputusan per lintasan** (sewa 15 dtk). Close ulang/bersamaan menunggu ≤ 3 dtk lalu
   **503 `EVIDENCE_PENDING`** (kode kontrak yang sudah ada, `retryable`) — agent mengulang; tidak ada kode baru.
4. **Transaksi berat** (gate IN tiba PA/terima transfer) dibatasi `KN_GATE_TXN_WORKERS` (2) dan menunggu ≤ 2 dtk bila
   ada permintaan reader berjalan; transaksi ringan (bukti keluar, kasus antrean) tidak antre di belakangnya.
5. **Bawaan pekerja di proses API** (tidak mengubah deploy); pekerja terpisah = opsi yang direkomendasikan.
6. **Memo hanya per lintasan** (`GateLookup`, dibuang sesudah close) + memo profil V2 berversi (immutable, 60 dtk).
   Tidak ada cache dokumen bisnis lintas permintaan (tidak ada SSOT kedua). Sakelar darurat `KN_GATE_PREFETCH=0`.
7. **Index jalur gate non-unik** (`kn_gate_*`, dibuat di `rfid_v2_core.ensure_indexes`, gagal = peringatan saja) —
   unik bisa menolak data lama kembar dan mengubah perilaku tulis.
8. **Retensi bawaan aktif** (`archive`, 90 hari bukti V2, 180 hari bacaan gate lama, minimum 7 hari): 90 hari menutup
   keluhan pelanggan/selisih kirim triwulan berjalan; 180 hari untuk jalur lama yang hanya pelengkap. Bukti dari
   lintasan dengan **kasus antrean terbuka** atau **transaksi belum tuntas** ditahan. Berkas ditulis atomik, dibaca &
   dihitung ulang sebelum hapus; `_delete` menolak koleksi yang dilindungi (pagar kode + uji). Mode `dry_run` untuk uji.
9. **TTL** hanya untuk log job retensi (`rfid_v2_retention_runs.expire_at`, 400 hari). Telemetry tidak tumbuh (ditimpa
   di dokumen perangkat), daftar latar ada di agent (server hanya ≤ 50 EPC per lintasan), `rfid_v2_health` = satu baris
   per perangkat × aturan → tidak perlu TTL.
10. **Celah idempotensi D2 ditutup**: ulang transaksi sesudah transfer `completed`/PA tertutup (pemroses mati sesudah
    menulis, atau handheld menuntaskan di antara keputusan & transaksi) dulu → 400 → galat palsu berulang; kini per
    roll `already`/`not_in_transit` atau trip lintasan yang sudah ada = selesai. Hasil sumber `processing` (pemroses
    lain basi) tidak lagi dihitung `done`.
11. **Polling FE**: kios 4 dtk (mundur ≤ 30 dtk), monitor 4 dtk (≤ 60 dtk), panel U300 10 dtk (≤ 60 dtk), antrean
    periksa 30 dtk (≤ 120 dtk, berhenti saat rincian terbuka). Mundur tidak pernah memberi hijau basi: kios tetap
    "TIDAK TERHUBUNG — TAHAN" bila data > 15 dtk. **SSE = rekomendasi** (butuh change stream/replica set).

## 9. Sisa / di luar cakupan
- **Layanan terima transfer & tiba PA** (`transfer_receipt_service`, `putaway_arrival_service`, `roll_service`) —
  ±18 query per roll (profil 200 roll: 3.630 query, `rebuild_balance` 2.800×) dan `inventory_movements.id` tanpa index;
  2.000 roll ≈ 3 mnt. Perbaiki di paket pemilik layanan itu (rebuild saldo sekali per produk×gudang, batch).
- Batas simpan **klaim crossing & keputusan lintasan** (permanen ±2 GB/thn) → keputusan pemilik bila perlu.
- Gzip body kontrak device (versi kontrak berikut), push SSE (butuh replica set), interlock gate berdampingan.
- Angka di sini dari stack 2 CPU di laptop bersama + klien lokal; ulangi `rfid_v2_loadtest.py run --scenario all` di
  VPS baru sebelum pilot (dengan RTT gudang nyata) dan sesudah perangkat datang (ringkasan agent nyata lebih besar).
- `CODEBASE_MAP.md` tidak diregenerasi; `verify_state_machine.py` tidak dijalankan (sesuai brief).

## 10. Uji (apa adanya)
Stack `kn-tmp-h-*`, DB `test_database` di-restore bersih dari `kn_test_trial_2026-11-08` sebelum MASING-MASING putaran
(sebelum = `5f1e36e`, sesudah = `53a9c0e`+), urutan berkas identik (`grep -l "gate\|rfid" tests/test_*.py`, satu proses
pytest per berkas; inti dulu, iter117/118 terpisah; `run_rfid_v2_*` dengan `MONGO_URL=mongodb://127.0.0.1:27017`).

| Pemeriksaan | Sebelum | Sesudah |
|---|---|---|
| `test_prep_h_gate_worker.py` (baru, 7) | — | **7 passed** (close tak menunggu transaksi; close ganda bersamaan; pemroses basi diambil alih tanpa terima ganda; jeda bertahap → berhenti → Ulangi; memo identik 10 kasus & ≤ 12 query untuk 300 roll; retensi uji coba/arsip/terlindung; registri & job) |
| `test_prep_h_gate_perf.py` (baru, 3; dapat dilewati `KN_SKIP_PERF=1`/kalibrasi lambat) | — | **1 passed, 2 failed — lingkungan rusak**: kalibrasi lulus (close 20 roll 127 ms, gate-state p95 48 ms ≤ 150), lalu VM Docker melambat menjelang mati ke-5 → satu close 500 roll dinilai > 30 dtk sesudah dikirim (`TIME_UNVERIFIED` → REVIEW) dan transfer 2.000 roll tidak tuntas dalam 150 dtk. Ambang (`CLOSE_500_P95` 1,5 dtk, `CLOSE_2000` 4 dtk, `EVENTS_BATCH_P95` 600 ms, `TXN_2000_TRANSFER` 120 dtk, `GATE_STATE_P95` 150 ms) = ±2× angka §3.1/§3.3; **ulangi di lingkungan stabil** |
| `test_prep_d1_gate_v2.py` | 20 passed | **20 passed** |
| `test_prep_d2_gate_txn.py` | 11 passed | **11 passed** (helper `send()` kini menunggu transaksi latar) |
| `test_iter117_p09` · `test_iter118_p10` (proses terpisah) | 18 · 8 passed | **18 · 8 passed** |
| `test_makloon_celup_rolls.py` | 20 passed | **20 passed** |
| `run_rfid_v2_integration.py` / `run_rfid_v2_extended.py` | 54 / 36 PASS | **54 / 36 PASS** |
| Suite gate/RFID lama (96 berkas) | 748 passed · 161 failed · 13 error · 41 skipped (174 id gagal/error unik) | **TIDAK SELESAI** — sesudah 9 berkas inti (semua sama dengan sebelum) VM Docker mati/melambat berulang: `test_audit_findings_reproduction` 2 passed + 5 error dalam 438 dtk (sebelum 6 passed, 11 dtk), `test_cut01` 1 passed dalam 237 dtk (sebelum 2 dtk) → hasil tercemar lingkungan, putaran dihentikan. **Perbandingan daftar gagal sebelum vs sesudah untuk 87 berkas sisanya BELUM ADA** |
| Jest `prepHGatePolling.test.js` (baru, 4) + `prepD1GateV2` (6) + `prepD2GateReview` (7) | — | **3 suite, 17 passed** (kontainer FE sementara 1,2 GB sesudah stack backend dihapus) |
| ESLint 8 berkas FE yang diubah/baru | — | **0 error**; 1 peringatan lama (`RfidGateMonitorView.jsx:104` unused eslint-disable, sudah ada); peringatan direktif di `usePolling.js` dihapus |

**Wajib sebelum merge (reviewer/koordinator, lingkungan stabil):** suite 96 berkas sesudah vs daftar sebelum
([`PREP-H-baseline-gagal.txt`](PREP-H-baseline-gagal.txt) — 174 id gagal/error, kode `5f1e36e`) dan
`test_prep_h_gate_perf.py`. Risiko ke berkas lain rendah (perubahan di luar gate V2: `retire_orphan_tags` hasil sama,
+2 job penjadwal, +3 kunci registri, index non-unik baru, `gate_evaluator` tanpa `ctx` = logika lama), tetapi
**belum terbukti** di sini.

Kode yang tidak bisa diuji di lingkungan ini: `scripts/gate_txn_worker.py` hanya dijalankan pada uji beban mode
terpisah (§3.2–3.3), tidak ada uji pytest khusus.

## 11. Berkas
| Berkas | Isi |
|---|---|
| `backend/services/gate_txn_service.py` | Pekerja latar (klaim CAS + sewa diperpanjang, jeda bertahap, semafor berat, mendahulukan reader, mode terpisah), `sweep`, `queue_summary`, job `rfid_gate_txn_retry`, idempotensi sesudah tuntas |
| `backend/services/rfid_v2_service.py` | close: sewa penghitung keputusan, transaksi ke latar (simulator langsung), penanda permintaan reader (`events`/`close`), `ensure_indexes` + sapuan start, riwayat tanpa daftar roll transaksi |
| `backend/services/gate_evaluator.py`, `gate_doc_movements.py`, `rfid_v2_policy.py`, `rfid_v2_sources.py` | `GateLookup` (memo satu lintasan) — opsional `ctx=`; jalur lama tanpa `ctx` tidak berubah |
| `backend/services/rfid_v2_core.py` | Index V2 + jalur gate, memo profil berversi |
| `backend/services/rfid_v2_retention.py`, `backend/config_catalog_rfid.py`, `backend/config_registry.py` (+1 baris) | Masa simpan bukti + 3 setelan registri |
| `backend/services/scheduler_service.py` (+2 job) | `rfid_gate_txn_retry` (2 mnt), `rfid_evidence_retention` (harian 02.30) |
| `backend/services/gate_review_service.py` (+3 baris) | Ringkasan antrean menyertakan jumlah transaksi gate |
| `backend/services/rfid_service.py` (`retire_orphan_tags`) | Startup: `$in` per 1.000 tag (di luar daftar milik — perbaikan kecil, perilaku sama) |
| `scripts/rfid_v2_loadtest.py`, `scripts/gate_txn_worker.py` | Alat uji beban/kegagalan; pekerja transaksi terpisah |
| `frontend/src/features/rfid/usePolling.js` (+ `GateLiveVerdict`, `RfidGateMonitorView`, `U300Operations`, `U300PassageList`, `GateReviewQueue`, `u300Labels`) | Polling ramah server + status transaksi |
| `backend/tests/test_prep_h_gate_worker.py`, `test_prep_h_gate_perf.py`, `_prep_h_bed.py`; `frontend/src/features/__tests__/prepHGatePolling.test.js` | Uji baru |
| `backend/tests/test_prep_d2_gate_txn.py` | `send()` menunggu transaksi latar tuntas sebelum memeriksa efek (asersi tidak diubah) |
| `docs/rfid/hasil/PREP-H-baseline-gagal.txt` | 174 id uji gagal/error SEBELUM (pembanding suite sesudah yang belum selesai) |

**Berisiko bentrok dengan agen lain:** `scheduler_service.py` (+2 job, +2 impor), `config_registry.py` (+1 impor),
`rfid_service.py` (`retire_orphan_tags` saja), `gate_review_service.py` (`summary`), `gate_doc_movements.py`
(parameter `ctx`), `test_prep_d2_gate_txn.py` (helper `send`). Tidak menyentuh printer/handheld/kontrak/agent.

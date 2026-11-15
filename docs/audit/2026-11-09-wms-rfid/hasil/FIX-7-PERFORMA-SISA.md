# FIX-7 — Performa & daftar sisa, masa simpan log, skrip data aman untuk produksi

- Tanggal: 10 Nov 2026 (WIB, ±00.20–03.35) · Pelaksana: Claude Code (paket perbaikan FIX-7) · Branch worktree
  `worktree-agent-a443ac00e9ee19b37`, dasar `main` `c729f4e` (sudah ter-deploy ke produksi). Commit: `72f8377` (butir 6 —
  skrip data produksi), `b3d4bcc` (butir 4 — daftar berhalaman server), `628151b` (butir 1, 2, 3, 5, 7), commit laporan.
  Butir 4 dan 6 dikerjakan dua sub-agen paralel di worktree & stack yang sama (berkas terpisah, tanpa commit sendiri);
  hasilnya saya tinjau, gabungkan, dan ukur ulang bersama (§6).
- Bahan: `hasil/FIX-5-PERFORMA-WMS.md` §8 (sisa), `B3b-FORM-INPUT-DAFTAR.md` LST-01…09 + `B3b-MATRIKS-DAFTAR.md`,
  `hasil/FIX-4-STANDAR-UI.md` (ExportMenu, `PaginationBar exportSpec`), `docs/rfid/hasil/PREP-H-GATE-PERFORMA.md` §4/§7.
- Lingkungan: stack sementara `kn-tmp-fix7-{mongo,be}` (Mongo 7 `--memory 1g --wiredTigerCacheSizeGB 0.4`, backend 1,5 GB,
  satu proses uvicorn per port), tanpa mount folder Windows, tanpa peramban. DB: `test_database` = salinan data acuan
  `kn_test_trial_2026-11-08` (46.700 roll ≈ produksi ±46.600; dipulihkan sebelum tiap putaran), `kn_perf` = acuan + data
  sintetis ×7 (lihat §3.1), `kainnusantara` = salinan acuan berganti nama seperti produksi (uji skrip data). Stack bersama
  `kn-uji-*`, DB koordinator, dan data UAT "test" tidak disentuh. **Mesin dipakai bersama paket lain** (`kn-tmp-fix6-*`,
  `kn-tmp-fix9-*` aktif bersamaan; Docker Desktop sempat mati ±01.20 WIB dan dinyalakan ulang, data utuh) → angka
  waktu berfluktuasi ±30 % dan beberapa p95 berisi pencilan; yang dibandingkan terutama p50 dan jumlah dokumen/kueri.
  Sesudah selesai: kontainer `kn-tmp-fix7-{mongo,be,fe}` + 2 volume anonim Mongo milik `kn-tmp-fix7-mongo` dihapus (data
  sintetis & salinan `kainnusantara` ikut hilang); berkas sementara besar di scratch dihapus.

---

## 1. Ringkasan

* **Cari roll `?q=`** (FIX-5 §8.1): pada 346.700 roll **2,3–2,9 dtk → 0,21–0,25 dtk** (p50); pada volume produksi
  **195–230 → 49–51 ms**. Hasil sama persis dengan definisi lama (regex "mengandung" di 6 field + nama/SKU, kutip =
  persis); tiap cabang kini ber-index. Tambahan: EPC heksadesimal yang dipindai ke kotak cari menemukan rollnya.
* **Papan stok** (`/inventory/status-board`): backorder dibaca **sekali** (dulu satu kueri `sales_orders` per segmen saldo
  — data acuan **759 kueri** per buka, ×7 ±31 ribu). Volume produksi **720–1.030 → 67–104 ms**; ×7 (30.512 segmen)
  **41–46 dtk → 1,3–1,9 dtk**.
* **Dasbor** (`/dashboard`, dimuat semua peran saat buka aplikasi): HPP (WAC) kini hanya dihitung untuk peran yang
  menerimanya (admin/manajer) dan sekali baca roll berproyeksi (dulu satu kueri dokumen-roll-utuh **per produk** untuk
  semua peran, lalu dibuang `strip_cost_fields`). ×7 **5,7–7,1 dtk → 1,2–1,5 dtk**; produksi, panggilan pertama: admin
  **5,2 → 0,38 dtk**, sales **7,3 → 0,17 dtk**.
* **Pohon stok** (`/warehouses/{id}/stock-tree`): `_bucket` per roll kini `$group` di Mongo → ×7 **0,50–0,57 → 0,30–0,38
  dtk**, produksi **0,32–0,34 → 0,17 dtk**.
* **Mutasi petugas berpagar lokasi** (FIX-5 §8.3): index `(warehouse_id, timestamp)` → ×7 halaman 1 **1,9 dtk → 0,27 dtk**,
  hitung **528.603 → 88.731 dokumen diperiksa**.
* **Daftar** (butir 4): **17 endpoint · 19 layar** kini berhalaman server (jumlah sungguhan, `limit` berbatas,
  "Muat berikutnya"), termasuk **LST-02 (P1) Meja Cutting** yang kehilangan tugas baru setelah 500 tugas sample.
* **Masa simpan log teknis**: job malam `log_retention` + 5 setelan registri (`sys_scheduler_runs` berhasil 30 hari / gagal
  90 hari, outbox WhatsApp 90, klaim ringkasan 30; baris terakhir tiap job disimpan; jejak audit bisnis dilindungi).
  Volume ±73 ribu riwayat: 36.619 baris dihapus dalam 2,5 dtk.
* **Skrip data untuk produksi** (butir 6): 5 skrip menerima `kainnusantara` hanya dengan `--production` + bukti backup
  < 24 jam; dry-run bawaan per dokumen; `--apply` berjejak; `--undo`. Panduan: `PANDUAN-SKRIP-DATA-PRODUKSI.md`.
* **Index `id`** (FIX-5 §8.7): `uq_id` untuk **62 koleksi bisnis/master lagi** (sensus 0 `id` kembar).
* **Kesetaraan**: 24 respons (6 kelompok endpoint × 4 peran) **identik** sebelum/sesudah pada 346.700 roll; pada data acuan
  23 identik + 1 beda yang disengaja (cari EPC kini menemukan roll).
* **Regresi**: 172 berkas uji, dasar 1.417 lulus / 498 id gagal-error → FIX-7 1.435 / 480; **0 yang hanya gagal di FIX-7**.
  Guardrail: tidak ada angka merah yang naik (`ui_standard`, `list_export` PASS).

## 2. Temuan yang ditutup (ID → perubahan → uji)

Uji baru: `backend/tests/test_fix7_perf_sisa.py` (33 uji, butir 1/2/3/5/7), `backend/tests/test_fix7_lists.py` (21 uji,
butir 4), `frontend/src/features/__tests__/fix7DaftarServer.test.js` (4 uji, butir 4), `backend/tests/test_fix7_data_scripts.py`
(7 uji, butir 6). Alat ukur & kesetaraan: `scripts/fix7_perf.py` (`balances`/`bench`/`snap`/`diff`/`explain`).

| ID | Perubahan | Uji |
|---|---|---|
| **FIX-5 §8.1** cari roll 2,0–2,5 dtk | `routers/inventory._roll_search` (dipakai daftar roll berhalaman/array & roll berkelompok): pola regex dari **satu** fungsi `pagination.search_pattern` (juga dipakai `build_search`) → tiap cabang `$or` ber-index: lot/dye_lot/batch/grade/consignor_ref = nilai berbeda dibaca lewat index (`distinct`, DISTINCT_SCAN; data acuan 423/416/79/6/1 nilai) lalu dicocokkan di Python dengan regex yang sama → `{field: {$in}}`; nomor roll = regex dievaluasi pada **kunci** `kn_roll_no_1` saja (kueri tertutup, 0 dokumen dibaca) → `{roll_no: {$in}}` (> 5.000 cocok → kembali ke regex, hasil sama); nama/SKU produk seperti dulu; **EPC** heksadesimal ≥ 16 karakter → `rfid_tags.epc` persis → roll. Index baru `inventory_rolls`: `lot`, `batch`, `grade`, `consignor_ref` (agar rencana OR terpakai). | 11 penjaga kesetaraan (nomor tepat/sebagian/kutip/huruf kecil, lot, batch, SKU, nama, karakter khusus, tanpa hasil — jumlah & himpunan id = definisi lama), `…indexes_exist_and_no_full_scan` (profil Mongo: 0 COLLSCAN, < 1.000 dokumen roll), `…by_epc_finds_roll`; `snap/diff` |
| **FIX-5 §8.2** papan stok 0,7–1,2 dtk | `atp_policy.BackorderIndex` + `backorder_index()`: baris backorder aktif dibaca sekali, `pending()` = aturan gudang/tanpa-gudang yang SAMA; `pending_backorder_qty` kini juga lewat kelas ini (satu aturan, bukan dua). `fulfillment_service.build_supply_index` memakai satu indeks (dulu `pending_backorder_qty` per (produk, PT) + per (produk, PT, gudang)). Segmen saldo (`stock_figures.segments`) dibaca sekali untuk papan + dua angka (`segs=`). | `…reads_backorders_once` (dasar **759** kueri backorder → 1), `test_backorder_function_matches_old_algorithm` + `…pending_demand_equals_per_segment_formula` (orakel independen = isi fungsi lama disalin; 4 PT × semua gudang × tanpa-gudang × `fulfilled`) |
| **FIX-5 §8.2** pohon stok ±0,5 dtk | `location_stock_tree.warehouse_tree`: aturan `_bucket` dinyatakan sebagai `$switch` Mongo (urutan pemeriksaan sama; truthy Python dinyatakan eksplisit karena `$cond` Mongo menganggap `""` benar) → `$group` per (bin, satuan, PT, jenis, ada-pesanan-panjang) → node ditambah per kelompok. `by_owner` kini berurutan tetap (id PT). | `…bins_equal_per_roll_rule` (angka tiap bin = `_bucket` per roll dari roll mentah), `…aggregated_in_mongo` (dokumen roll yang dikirim ke backend < ¼ jumlah roll; dasar = semua roll) |
| **FIX-5 §8.2 / B1b UI-51** dasbor p95 2–4 dtk | `routers/dashboard`: HPP hanya untuk `COST_SAFE_ROLES` (peran lain menerima respons identik — field dibuang `strip_cost_fields`); `costing_service.wac_for_products` = satu kursor roll hidup berproyeksi untuk semua produk, langkah per roll `_wac_add` & hasil `_wac_result` dipakai juga oleh `wac_for_product` (refaktor tanpa ubah rumus; `wac_for_product` kini juga berproyeksi). Saldo dibaca sekali (`apply_global(segs=)`). | `…sales_no_wac_queries` (dasar 136 kueri WAC → 0), `…admin_wac_single_read_and_same_values` (dasar 411 kueri → 1; nilai = `wac_for_product`) |
| **FIX-5 §8.3** mutasi berpagar lokasi 1,1–1,2 dtk | Index `inventory_movements (warehouse_id, timestamp)`. | `…uses_warehouse_timestamp_index` (explain), §3.4 |
| **B3b LST-01/02/03/04/06/07/09** · FIX-5 §8.6 · FIX-4 §11 (butir 4) | 17 endpoint: `skip` + jumlah sungguhan (`X-Total-Count`/`X-Truncated` atau `total/truncated` di badan), `limit` dijepit, cari di-escape, proyeksi, N+1 → batch; 19 layar: `ListLimitNote` (FIX-5) "Menampilkan a–b dari N … Muat berikutnya"; Antrean periksa gate D2 memakai kursor `next_before`. Rincian §2.1. | `test_fix7_lists.py` (dasar 19 gagal → 21/21), Jest `fix7DaftarServer` (dasar 4/4 gagal → lulus) |
| Brief butir 5 — log teknis tumbuh tanpa batas (`sys_scheduler_runs` produksi 73 ribu) | `services/log_retention.py` + job `log_retention` (03.40 WIB) + `config_catalog_retention.py` (5 kunci `ops.*`, grup "Notifikasi & Pemberitahuan"). Rincian §2.2. | `…job_registered_and_settings_in_registry`, `…deletes_old_technical_logs_only` (berhasil > 30 hari dihapus, gagal 40 hari disimpan, gagal 120 hari dihapus, baris terakhir job disimpan, outbox antre disimpan, `audit_logs` 11 tahun tidak disentuh, pagar `_delete_batched("audit_logs")` → AssertionError, dry-run tidak menghapus) |
| Brief butir 6 — skrip data hanya DB uji | `services/data_fix_guard.py` + 5 skrip. Rincian §2.3 dan panduan. | `test_fix7_data_scripts.py` (dasar 6 gagal/1 lulus → 7/7) |
| **FIX-5 §8.7 · B3a SCH-9 · PREP-H §7** index `id` koleksi lain | `indexes.ID_INDEX_COLLECTIONS_MORE` (62 koleksi; dibuat hanya bila koleksi ada — data acuan 52); index `{id: 1}` milik modul sendiri (mis. `product_templates.catalog_parent_id`, unik) dihormati, tidak digandakan. Index daftar butir 4: `wms_tasks (task_subtype, status, created_at)`, `logistics_deliveries` ×3, `repair_orders`, `rfid_print_jobs`, `rfid_cycle_counts`. | `test_id_index_on_more_business_collections[8]` (unik + dipakai explain), `test_existing_id_index_respected_not_duplicated` |

### 2.1 Daftar berhalaman server (butir 4)

| Layar | Endpoint | Sebelum → sesudah |
|---|---|---|
| Meja Cutting (**LST-02, P1**) | `/cutting/desk` | 500 tugas TERLAMA tanpa saring status (tugas baru hilang setelah 500 tugas sample) → hanya tugas terbuka, 500 terbaru, `total_open`/`truncated` + catatan |
| Tugas barang keluar · Eskalasi | `/outbound/tasks` | 200 diam → 200 (maks 500) + header jumlah, `skip`, Muat berikutnya |
| Cutting › paket potong | `/outbound/tasks` | dulu disaring di layar dari 200 tugas → `task_subtype`/`exclude_status` di server, 500 + Muat berikutnya |
| Pengiriman | `/logistics/deliveries` | cari setelah dipotong 1.000 → cari di server (escape), header jumlah, Muat berikutnya |
| Riwayat pengiriman | `/logistics/history` | 3.000 dokumen dimuat lalu dipotong di memori → agregat Mongo (saring tanggal/urut/halaman), statistik atas semua hasil |
| Sesi opname · kotak persetujuan | `/cycle-count/sessions` | 100 dokumen utuh (items + scans) → ringkas (`item_count`, `scan_count`), saring `status`, header, Muat berikutnya |
| Pendaftaran awal | `/registration/sessions` | 200 diam → header + Muat berikutnya |
| Perbaikan | `/repair-orders` | 200 diam, hitung per status atas 2.000 dokumen, regex tanpa escape (galat 500) → `total/truncated`, `$group`, escape |
| Pesanan sample | `/sample-orders` | 300 diam → header + Muat berikutnya |
| Order makloon | `/makloon-orders` | 500 diam → header + Muat berikutnya; kartu "Total order" = jumlah server |
| Tugas masuk (mode lama) | `/inbound/tasks` | 200 diam, PO dipotong 100 → header + Muat berikutnya, PO lengkap |
| RFID belum ber-tag / siap cetak · lokasi tag · job cetak · perangkat · riwayat opname | `/rfid/untagged-rolls` (500), `/rfid/locations` (1.000), `/rfid/print-jobs` (100), `/rfid/devices` (500), `/rfid/cycle-counts` (30) | → `total/truncated/skip/limit` + Muat berikutnya; saringan gudang job cetak tidak hilang (LST-04); galat opname RFID ditampilkan (LST-06) |
| Antrean periksa gate D2 (**LST-09**) | `/rfid/v2/ops/reviews` | kursor tak dipakai → "Muat lebih lama" (`next_before`); tanpa ekspor (K-I8 FIX-4) |
| HP daftar tugas | `/wms/tasks` | header `X-Truncated` FIX-5 kini tampil sebagai peringatan |
| (tanpa layar) | `/logistics/fleet/vehicles` | 500 → header + `skip` |

Tombol **Unduh** (ExportMenu FIX-4) yang sudah ada di layar-layar ini tidak diubah — saringannya sudah mengikuti kueri
server; tidak ada `PaginationBar` baru (pola "Muat berikutnya" FIX-5) sehingga ratchet `list_no_excel` & `verify_list_export`
tidak naik. Komponen baku `components/*` (FIX-8) dan berkas GRN/retur/PO (FIX-6) tidak disentuh.

### 2.2 Masa simpan log teknis (butir 5)

| Log (koleksi) | Pertumbuhan | Aturan bawaan (setelan) |
|---|---|---|
| Riwayat job penjadwal `sys_scheduler_runs` | ±700–2.000 baris/hari (job tiap 2–5 mnt; acuan 10.565 dalam 15 hari, produksi 73 ribu) | berhasil > **30 hari** (`ops.scheduler_runs_retention_days`), gagal > **90 hari** (`ops.scheduler_runs_failed_retention_days`); baris TERAKHIR tiap job selalu disimpan |
| Kotak keluar WhatsApp `sys_wa_outbox` | 1 baris per pesan × penerima | > **90 hari** (`ops.wa_outbox_retention_days`); status antre/pending tidak dihapus; kunci anti-dobel berisi tanggal → tidak ada kirim ulang |
| Klaim ringkasan harian `sys_digest_claims` | 1 per penerima per hari | > **30 hari** (`ops.digest_claims_retention_days`) |
| Mode | — | `ops.log_retention_mode` = `delete` (bawaan) · `dry_run` · `off`; minimum 7 hari |

Sudah punya masa simpan sendiri (tidak diubah): `rfid_v2_*` bukti gate (PREP-H, 90/180 hari + arsip), `rfid_v2_retention_runs`
(TTL 400 hari), `ai_schedule_runs`/sesi chat (`ai_maintenance`), `sessions`/`idempotency_keys`/`ai_result_cache`/`ai_results`
(TTL). **Tidak pernah dihapus** (pagar `PROTECTED`, diuji): `audit_logs`, `status_history` (field dokumen), jurnal & posting
GL, mutasi stok, riwayat nilai roll, log kebersihan data, log matriks persetujuan, peristiwa tag RFID, pemakaian AI (dasar
anggaran), notifikasi (penanda "pernah dibuat" dipakai anti-dobel), dokumen bisnis.

### 2.3 Skrip data aman untuk produksi (butir 6)

`backend/services/data_fix_guard.py` (diimpor skrip `scripts/*.py` dan `backend/scripts/*.py`; modul ada di image produksi
karena `Dockerfile.backend` menyalin `backend/`): DB uji lama diterima seperti dulu; `kainnusantara` **wajib `--production`**
+ bukti backup < 24 jam — berkas `deploy/backups/kainnusantara-*.archive.gz` yang terlihat (umur, ≥ 100 KB, gzip utuh,
penanda mongodump), ATAU nama berkas bercap waktu (kontainer `exec` tidak melihat `deploy/backups`), ATAU
`--backup-confirmed "<keterangan>"`; DB lain ditolak (migrasi FIX-2 dulu menulis ke DB apa pun). Dry-run bawaan mencetak
`koleksi id label: field: sebelum → sesudah` + jumlah per langkah (`--show`, `--report json`). `--apply` mencatat satu baris
`audit_logs` per dokumen (`data_fix_applied`, before/after) + sumber undo di `migrations`. `--undo` memulihkan nilai sebelum
persis, mencabut riwayat & mutasi sisipan, membangun ulang saldo segmen, melewati dokumen yang sudah diubah orang lain.
Uji di salinan `kainnusantara`:

| Skrip | Dry-run | Apply (jejak) | Apply ulang | Undo |
|---|---|---|---|---|
| tandai_data_uji | 12 | 12 | 0 | 12 |
| gedung_bersama | 2 | 2 | 0 | 2 |
| fix3a_alur_masuk | 3 (+3 tag & 0 PO laporan) | 3 | 0 | 3 |
| fix3b_alur_keluar | 9 | 9 (+1 saldo dibangun ulang) | 0 | 9 |
| migrate_fix2 | 0 kandidat (acuan) | diuji dengan roll sintetis | — | dipulihkan persis |

Potret 11 koleksi sebelum apply vs sesudah undo: identik (kecuali `updated_at` 2 gedung — disengaja — dan metadata rebuild 1
saldo; angka saldo sama). Penolakan diuji: tanpa `--production`, tanpa bukti, backup tua, DB lain → `DITOLAK` (kode 2).

## 3. Angka sebelum / sesudah

### 3.1 Data
* **Produksi-setara** — `test_database` = data acuan: 46.700 roll, 85.363 mutasi, 393 saldo, 411 produk, 18 gudang.
* **×7** — `kn_perf` = acuan + `wms_perf_bench.py synth` (300.000 roll sintetis seperti FIX-5): **346.700 roll** (275 MB),
  **685.630 mutasi**, 300.041 tag, 1.962 lot; + `fix7_perf.py balances` membangun saldo segmen roll sintetis lewat
  `rebuild_balance` asli (**30.512 saldo**, 20 menit) agar papan stok/dasbor melihat volume itu. Catatan: sebaran sintetis
  acak ke 411 produk × 18 gudang × 3 PT → jumlah segmen ±77× acuan (produksi 2 tahun kemungkinan jauh lebih sedikit) —
  angka papan stok ×7 = batas atas.

### 3.2 HTTP ×7 (346.700 roll; p50 / p95 ms; dasar 5 ulangan untuk cari, 3 untuk pohon/dasbor/mutasi, 1 untuk papan stok;
sesudah 5 ulangan + 1 pemanasan; penjadwal mati)

| Endpoint (peran) | Sebelum | Sesudah | Ukuran |
|---|---|---|---|
| cari roll: nomor tepat (admin) | 2.287 / 2.615 | **248 / 250** | 1 KB |
| cari roll: 6 digit akhir | 2.527 / 3.068 | **212 / 267** | 1 KB |
| cari roll: nomor roll acuan | 2.343 / 2.517 | **208 / 214** | 0 KB |
| cari roll: lot | 1.294 / 1.566 | **211 / 404** | 47 KB |
| cari roll: kata nama produk | 959 / 1.086 | **252 / 276** | 68 KB |
| cari roll: tanpa hasil | 2.856 / 3.511 | **255** / 2.010 *(pencilan)* | 0 KB |
| cari roll: teks EPC | 2.811 / 3.077 | **219 / 295** | 0 KB |
| cari roll mode array (`limit=50`) | 1.786 / 2.229 | **230 / 254** | 1 KB |
| cari roll petugas berpagar (`location_view`) | 412 / 746 | **222 / 247** | 1 KB |
| roll berkelompok + cari lot | 951 / 1.257 | **232 / 359** | 12 KB |
| papan stok — admin | 46.113 (n=1) | **1.918 / 2.812** | 8,0 MB |
| papan stok — petugas gudang | 43.240 (n=1) | **1.334 / 1.485** | 544 KB |
| papan stok — sales | 41.401 (n=1) | **1.861** / 13.532 *(pencilan)* | 1,9 MB |
| pohon stok gudang tersibuk (admin) | 565 / 577 | **375 / 453** | 133 KB |
| pohon stok satu lokasi (admin) | 521 / 577 | **338 / 564** | 134 KB |
| pohon stok gudang petugas | 497 / 533 | **297 / 348** | 132 KB |
| dasbor — admin | 6.769 / 7.450 | **1.400 / 3.597** | 1,1 MB |
| dasbor — manajer | 7.133 / 13.582 | **1.470 / 3.002** | 1,1 MB |
| dasbor — sales | 5.683 / 6.668 | **1.225 / 1.505** | 1,0 MB |
| dasbor — petugas gudang | 6.833 / 7.573 | **1.380 / 1.575** | 1,1 MB |
| mutasi halaman 1 — admin | 169 / 173 | 181 / 201 (setara) | 35 KB |
| mutasi halaman 1 — petugas berpagar | 1.890 / 2.347 | **267 / 345** | 35 KB |
| mutasi halaman 1 — petugas, satu gudang | 1.727 / 1.995 | **204 / 257** | 35 KB |
| mutasi halaman 5 — petugas berpagar | 2.316 / 2.820 | **325 / 391** | 42 KB |

### 3.3 HTTP volume produksi (data acuan 46.700 roll; p50 / p95 ms, 5 ulangan)

| Endpoint | Sebelum | Sesudah |
|---|---|---|
| cari roll (nomor tepat · sebagian · lot · tanpa hasil) | 194 · 229 · 196 · 215 | **51 · 51 · 49 · 51** |
| papan stok admin · petugas · sales | 723 · 754 · 1.027 | **104 · 67 · 87** |
| pohon stok gudang · lokasi · petugas | 333 · 323 · 344 | **173 · 167 · 171** |
| dasbor admin · manajer · sales · petugas — panggilan PERTAMA (cache WAC 5 dtk dingin) | 5.242 · 1.830 · 7.301 · 254 | **384 · 125 · 173 · 131** |
| dasbor — ulangan cepat (cache WAC 5 dtk dasar hangat) | 140 · 142 · 378 · 202 | 127 · 122 · 182 · 145 |
| mutasi halaman 1 admin · petugas | 30 · 64 | 32 · 66 (setara; data acuan kecil) |

Catatan dasbor: kode dasar menyimpan WAC per produk 5 dtk, jadi ulangan cepat di bangku uji terlihat ringan; pengguna
nyata membuka aplikasi pada waktu berbeda (cache dingin) → angka "panggilan pertama" yang dialami.

### 3.4 `explain` (×7, `fix7_perf.py explain`)

| Kueri | Sebelum (rencana · kunci · dokumen · ms) | Sesudah |
|---|---|---|
| mutasi berpagar lokasi, halaman 1 (urut waktu) | IXSCAN `owner_entity_id,timestamp` · 1.190 · 1.189 · 323 | IXSCAN **`warehouse_id,timestamp`** · 125 · 125 · 27 |
| mutasi berpagar lokasi, hitung | IXSCAN `owner_entity_id,timestamp` · 528.604 · 528.603 · 3.497 | IXSCAN `warehouse_id,timestamp` · 88.731 · 88.731 · 507 |
| mutasi satu gudang, halaman 1 | 1.190 · 1.189 · 10 | 125 · 125 · 1 |
| cari roll — kueri lama (`$or` regex) | IXSCAN `created_at` (jalan penuh) · 346.700 · 346.700 · 1.987 | (tidak dipakai lagi) |
| cari roll — nomor roll (baru) | — | PROJECTION_COVERED `kn_roll_no_1` · 346.700 · **0** · 204 |
| cari roll — halaman OR `$in` (baru) | — | IXSCAN `roll_no`/`lot`/`dye_lot` · 201 · 200 · 11 |
| papan stok — kueri backorder per buka (profil, acuan) | **759** kueri `sales_orders` | **1** |
| dasbor — kueri WAC per buka (profil, acuan) admin · sales | 411 · 136 kueri roll per produk (dokumen utuh) | 1 · 0 |

### 3.5 Start backend (×7) & masa simpan log
* Start ulang: dasar 42,2 dtk → FIX-7 31,5–34,7 dtk (tidak memburuk; fluktuasi mesin bersama). Start pertama yang membangun
  index baru (4 index roll 346.700 dok, 1 index mutasi 685.630 dok, `uq_id` 51 koleksi): **50,1 dtk**.
* `log_retention` pada 83.565 riwayat job (73.000 sintetis 60 hari ±1.200/hari + 10.565 acuan): dry-run 0,3 dtk
  (36.619 calon); hapus **36.619 baris dalam 2,5 dtk** (per 2.000 + jeda 50 ms); sisa 46.946.

## 4. Kesetaraan hasil (sebelum vs sesudah)
`fix7_perf.py snap` (satu respons per endpoint × peran, dinormalisasi: kunci diurutkan, tanpa cap waktu, desimal 6 digit,
`by_owner` pohon stok diurutkan) lalu `diff`:

| Data | Hasil |
|---|---|
| ×7 (`kn_perf`, 346.700 roll, 30.512 saldo): 10 variasi cari roll + roll berkelompok, papan stok ×3 peran, pohon stok ×3, dasbor ×4 peran (termasuk HPP admin/manajer), mutasi ×4 | **24 / 24 identik** |
| Data acuan (`test_database`) — set yang sama | **23 identik + 1 beda disengaja**: cari teks EPC (dasar 0 roll → kini 1 roll pemilik tag) |

Selain itu uji pytest membandingkan dengan **orakel independen**: definisi cari lama (regex 6 field + produk), isi fungsi
`pending_backorder_qty` lama (disalin), aturan `_bucket` per roll, dan `wac_for_product`.

## 5. Perubahan perilaku untuk pengguna
1. **Kotak cari roll**: hasil sama, jauh lebih cepat; **EPC** yang ditempel/dipindai (heks ≥ 16 karakter) kini menemukan
   rollnya.
2. **19 layar daftar** menampilkan "Menampilkan a–b dari N … Muat berikutnya" bila terpotong (dulu diam-diam). **Meja
   Cutting** kini selalu memuat tugas terbuka TERBARU (tugas selesai tidak lagi memakan jatah 500). Cari **Pengiriman**
   mencakup semua pengiriman (dulu hanya 1.000 terbaru; karakter khusus dicari apa adanya). **Riwayat pengiriman** tidak
   berhenti di 3.000 baris — angka statistik bisa lebih besar dari dulu karena kini dihitung atas semua riwayat. Jumlah per
   status **Perbaikan** dihitung atas semua dokumen. Antrean periksa gate D2: tombol "Muat lebih lama".
3. **API** `/cycle-count/sessions` tidak lagi mengirim `items`/`roll_count` (diganti `item_count`, `scan_count`,
   `roll_mode`; dua pemakai di layar sudah disesuaikan); `/outbound/tasks` & daftar lain kini berbatas (`limit` maks) dengan
   header jumlah.
4. **Pengaturan baru** (Pusat Pengaturan › Notifikasi & Pemberitahuan): 5 setelan masa simpan log teknis; job baru
   "Masa Simpan Log Teknis" (03.40 WIB) di layar Penjadwal. Riwayat job berhasil yang lebih tua dari 30 hari hilang dari
   layar Penjadwal (baris terakhir tiap job tetap).
5. **Pohon stok**: urutan rincian per PT kini tetap (urut id PT; dulu urutan roll pertama terbaca).
6. **Integritas**: menyisipkan dokumen dengan `id` yang sudah ada di 51 koleksi tambahan (data acuan) kini ditolak DB
   (`E11000`), seperti FIX-5 untuk 40 koleksi WMS.
7. **Skrip data**: perintah lama di DB uji tetap; produksi butuh `--production` + bukti backup (panduan).

## 6. Keputusan implementer (mohon ditinjau)
1. **Cari roll mempertahankan arti "mengandung"** (bukan awalan/teks index): brief mengizinkan awalan/teks, tetapi itu
   mengubah hasil (cari 5 digit akhir nomor roll tidak ketemu). Dengan DISTINCT_SCAN + kueri tertutup nomor roll, hasil
   identik dan tetap ±10× lebih cepat. Biaya tetap: pindai kunci index nomor roll (±0,2 dtk pada 346.700 roll, ±0,03 dtk
   produksi).
2. **EPC ditambahkan** ke kotak cari (perubahan perilaku kecil, hanya untuk teks heks ≥ 16 karakter) — petugas memindai EPC
   ke kotak cari.
3. **Papan stok/dasbor tanpa cache**: tidak ada cache lintas permintaan (angka stok selalu segar); yang dihilangkan adalah
   kueri N+1 dan pembacaan ganda. Rumus `stock_figures`, `atp_policy` (ATP, horizon) dan WAC tidak diubah — hanya
   dipecah agar satu aturan dipakai satu kali-baca dan per-panggilan.
4. **HPP dasbor hanya untuk peran yang menerimanya** (admin/manajer = `COST_SAFE_ROLES`): keluaran peran lain identik karena
   field itu memang dibuang; menghemat satu kueri per produk.
5. **Masa simpan log = job terjadwal, bukan index TTL**: cap waktu log teks ISO (TTL Mongo hanya untuk tanggal BSON), masa
   simpan bisa diubah tanpa `collMod`, ada mode uji coba, penghapusan bertahap untuk VPS bersama (cache 0,5 GB). Bawaan:
   berhasil 30 hari (sebulan penelusuran), gagal 90 hari, outbox 90 hari, klaim ringkasan 30 hari. Tanpa arsip berkas —
   log teknis sekali pakai (bukti gate RFID sudah punya arsip PREP-H).
6. **Notifikasi tidak diberi masa simpan**: dedupe "pernah dibuat" (`dedupe_scope="ever"`) membaca notifikasi lama →
   menghapusnya membuat pemberitahuan terkirim ulang. Dicatat sebagai sisa.
7. **`uq_id` 62 koleksi lagi** (kriteria: ≥ 3 pencarian per `id` di kode, bukan log/teknis, 0 kembar). Koleksi yang sudah
   punya index `{id:1}` sendiri dihormati.
8. **Butir 4 memakai pola "Muat berikutnya" FIX-5**, bukan `PaginationBar` baru (komponen baku milik FIX-8; pager baru wajib
   Excel). Koleksi panas tetap diurut `created_at` saja agar index lama terpakai.
9. **Butir 6: jejak di `audit_logs` + `migrations`, bukan `data_hygiene_log`** — tombol "Kembalikan" per baris layar
   Kebersihan Data hanya menimpa field (tanpa rebuild saldo) dan mengunci dokumen; tidak aman untuk roll/tugas. Bukti backup
   diwajibkan juga untuk dry-run produksi.
10. **Data sintetis saldo ×7 dibangun dengan `rebuild_balance` asli** (bukan rumus bangku uji) agar papan stok diukur pada
    angka yang benar.

## 7. Uji & regresi (apa adanya)

### 7.1 Uji baru
| Uji | Dasar `c729f4e` | FIX-7 |
|---|---|---|
| `test_fix7_perf_sisa.py` (33) | **18 gagal**, 15 lulus (= 15 penjaga kesetaraan) | **33/33 lulus** |
| `test_fix7_lists.py` (21) | 19 gagal, 2 lulus (penjaga) | 21/21 |
| `test_fix7_data_scripts.py` (7) | 6 gagal, 1 lulus (perintah DB uji lama) | 7/7 |
| Jest `fix7DaftarServer.test.js` (4) | 4/4 gagal | 4/4 |

### 7.2 Regresi pytest (satu proses per berkas, DB dipulihkan bersih sebelum tiap putaran)
Berkas = `tests/test_*.py` yang menyebut jalur yang diubah (papan stok/ATP/backorder, pohon stok, dasbor/WAC, daftar &
cari roll, mutasi, index, penjadwal, registri setelan, `build_search`, skrip data) ∪ 115 berkas regresi butir 4 (cutting,
tugas keluar/masuk, logistik, opname, pendaftaran, perbaikan, sample, makloon, RFID, armada, antrean D2) = **172 berkas**
(+ 2 berkas uji baru yang hanya ada di FIX-7). `test_iter117_p09`/`test_iter118_p10` tidak termasuk.

| Putaran | Lulus | Gagal | Error | id gagal/error unik | Waktu |
|---|---|---|---|---|---|
| Dasar `c729f4e` (+ berkas uji `test_fix7_perf_sisa.py`) | 1.417 | 429 | 69 | 498 | 891 dtk |
| FIX-7 (`628151b` + laporan) | **1.435** | **411** | 69 | **480** | 989 dtk |

* **Hanya gagal di FIX-7: 0.** Gagal di dasar & lulus di FIX-7: 18 (seluruhnya uji baru `test_fix7_perf_sisa.py`).
  Berkas baru saja: `test_fix7_lists.py` 21/21, `test_fix7_data_scripts.py` 7/7.
* 480 id gagal/error lama sama persis di kedua putaran (uji lama yang bergantung pada data/peran lama, pola laporan
  FIX-2…FIX-5) — tidak disentuh paket ini.
* **Catatan metode (penting untuk paket lain):** 182 berkas uji mengimpor kode lewat jalur tetap `sys.path.insert(0,
  "/app/backend")`. Putaran "dasar" yang menjalankan server dari direktori lain (mis. `/app_base`) tetap memanggil fungsi
  dalam-proses dari kode BARU di `/app` — perbandingan jadi kabur. Putaran dasar di atas dijalankan dengan kode dasar
  DITUKAR ke `/app` (dan dikembalikan sesudahnya); putaran pertama saya yang belum ditukar (81 berkas) menunjukkan gejala
  ini (index `uq_id` baru sudah ada di putaran "dasar").

### 7.3 Jest & ESLint (butir 4; butir lain hanya backend)
Jest terkait 14 suite: dasar 123/123, FIX-7 127/127; **Jest penuh FIX-7: 86/86 suite, 608/608 uji**. ESLint 23 berkas
diubah: 0 error (18 peringatan "Unused eslint-disable directive" lama).

### 7.4 Guardrail (host, `PYTHONUTF8=1`, pohon dasar `git archive c729f4e` vs pohon FIX-7; `verify_state_machine` tidak
dijalankan)
| Hasil | Guardrail |
|---|---|
| Kode keluar **identik** dasar = FIX-7 (43 guardrail) | hijau tetap hijau (termasuk `ui_standard` 4.316 cek, `list_export` 21, `ui_contrast` 58, `error_notice` 276, `scope_guard`, `codebase_map`, `roll_identity`, `rfid_tag_unique`, `knselect_contract`); merah lama tetap merah dengan jumlah sama (`atomic_claim`, `auth_coverage`, `entity_label`, `line_scope`, `numeric_bounds`, `page_tabs`, `qty_dual`, `to_list_bound`); `concurrency`, `cross_entity`, `home_kpi`, `nonfinancial_sweep`, `ref_unlink` gagal impor modul di host di kedua pohon |
| Selisih hitungan | `escape_layers`/`role_label`/`uom_vocab` 1.194 → 1.195 berkas (berkas Jest baru ikut dipindai, 0 pelanggaran); `no_secrets` 0 → 8 = berkas `test_reports/pytest/*.xml` lama yang tidak ikut arsip dasar (bukan dari FIX-7; dicatat juga oleh FIX-4/5) |
| Angka merah yang naik | **tidak ada** |

## 8. Berkas berisiko bentrok
* Backend baca stok: `routers/inventory.py` (`_roll_search`, papan stok), `services/fulfillment_service.py`,
  `services/atp_policy.py`, `services/costing_service.py`, `services/location_stock_tree.py`, `services/sales_stock_service.py`,
  `routers/dashboard.py`, `pagination.py` (+`search_pattern`).
* Index/bootstrap: `indexes.py` (INDEX_SPECS + `ID_INDEX_COLLECTIONS_MORE` + aturan index `{id:1}` milik modul).
* Penjadwal/registri: `services/scheduler_service.py` (+1 job), `config_registry.py` (+1 impor), baru
  `config_catalog_retention.py`, `services/log_retention.py`.
* Butir 4 (daftar): router `cycle_count`, `inbound_receiving` (hanya GET daftar — **bersinggungan dengan FIX-6** alur
  masuk), `initial_registration`, `logistics`, `makloon_orders`, `outbound_picking`, `repair_orders`, `rfid`, `sample_orders` +
  layanannya; 22 layar (`features/wms`, `rfid`, `logistics`, `samples`, `inventory`, `purchasing/MakloonOrdersView`,
  `manager/EscalationManagement`, `mobile/MobileWarehouseApp`, `approvals/approvalInboxData`). Komponen baku tidak disentuh.
* Butir 6: `scripts/fix_data_2026_11_09_*.py`, `backend/scripts/migrate_fix2_inspection_hold_status.py`, baru
  `services/data_fix_guard.py`.

## 9. Sisa / di luar cakupan
1. `rebuild_balance` tetap menghitung ulang **semua lot** segmen tiap panggilan (FIX-5 §8.4) — butuh perubahan kontrak hook
   (jalur tulis); tidak disentuh.
2. Dasbor tetap mengirim ±1,1 MB (semua produk + pesanan + gudang + pelanggan) ke semua peran saat buka aplikasi
   (rekomendasi UI-51: data dimuat layar pemakainya) — perubahan kerangka FE.
3. Papan stok ×7 masih 1,3–1,9 dtk karena keluarannya sendiri besar (8 MB untuk admin pada 30.512 segmen) — halaman/ringkas
   per produk bila produksi mencapai ribuan segmen.
4. Daftar yang belum: antrean QC kedatangan (N+1), selisih supplier (5.000), profil SJ/OCR, retur antar-PT (wilayah FIX-6);
   master gudang `/warehouses` + N× okupansi; antrean potong `/inventory/pending-cuts`; daftar ambil; `/sample-orders/desk`;
   N+1 `subcon_qty_by_ref` daftar makloon; saringan/cari layar masih atas baris yang sudah dimuat (disebut di catatan).
5. Masa simpan notifikasi (lihat keputusan 6), `export_jobs` + berkas ekspor, `ocr_sample_runs`, `ai_usage_log`
   (dasar anggaran AI) — belum.
6. Skrip data: undo tidak tersedia untuk putaran yang dijalankan SEBELUM FIX-7 (tidak ada nilai sebelum); panduan belum
   dicoba di VPS sungguhan (disimulasikan di kontainer); jalur `exec` butuh image yang sudah memuat FIX-7.
7. Guardrail runtime (`concurrency`, `cross_entity`, `home_kpi`, `nonfinancial_sweep`, `ref_unlink`, …) tidak jalan di host
   (modul DB/HTTP tidak terpasang) — sama di dasar & FIX-7.
8. `CODEBASE_MAP.md` tidak dibangkitkan ulang (penjaga ±10 % tetap hijau).

## 10. Ringkasan untuk koordinator
* **Perubahan:** cari roll ber-index (hasil sama + EPC); papan stok backorder sekali-baca & saldo sekali-baca; pohon stok
  `$group` Mongo; dasbor tanpa WAC untuk peran tanpa HPP + WAC sekali-baca; index mutasi `(warehouse_id, timestamp)`;
  17 endpoint/19 layar berhalaman server (termasuk LST-02 P1 Meja Cutting, LST-09 kursor D2); job `log_retention` + 5
  setelan `ops.*`; 5 skrip data dengan mode `--production` + bukti backup + jejak + undo + panduan VPS; `uq_id` 62 koleksi
  lagi (51 ada di data acuan) + 7 index daftar. Rumus `stock_figures`/ATP/WAC tidak diubah.
* **Angka (×7, 346.700 roll):** cari roll 2,3–2,9 dtk → 0,21–0,25 dtk; papan stok 41–46 dtk → 1,3–1,9 dtk; dasbor
  5,7–7,1 → 1,2–1,5 dtk; pohon stok 0,50–0,57 → 0,30–0,38 dtk; mutasi petugas berpagar 1,9–2,3 → 0,27–0,33 dtk.
  **Volume produksi:** cari 0,2 → 0,05 dtk; papan stok 0,7–1,0 → 0,07–0,10 dtk; dasbor panggilan pertama admin 5,2 →
  0,38 dtk, sales 7,3 → 0,17 dtk. Log: 36.619 riwayat job lama dihapus dalam 2,5 dtk.
* **Kesetaraan:** ×7 24/24 respons identik; acuan 23/24 + 1 beda disengaja (EPC).
* **Uji:** baru 33 + 21 + 7 pytest & 4 Jest (gagal di dasar → lulus); regresi 172 berkas dasar 1.417 / 498 id merah →
  FIX-7 1.435 / 480, **0 yang hanya gagal di FIX-7**; Jest penuh 608/608; guardrail tidak naik (§7.4). Catatan metode
  §7.2: 182 berkas uji mengimpor `/app/backend` tetap — putaran "dasar" paket lain yang tidak menukar direktori kode
  memakai kode baru untuk panggilan dalam-proses.
* **Perlu keputusan/aksi koordinator:** jalankan skrip data di produksi mengikuti panduan (masih menunggu pemilik);
  tinjau keputusan implementer §6 (cari tetap "mengandung", job bukan TTL, notifikasi tanpa masa simpan, `uq_id` 62
  koleksi). Bentrok potensial: `inbound_receiving.py` (FIX-6), layar daftar (FIX-8 hanya bila menyentuh berkas yang sama).

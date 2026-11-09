# FIX-5 — Performa WMS (index, N+1, halaman server, layar roll besar)

- Tanggal: 9 Nov 2026 (WIB, ±17.00–19.10) · Pelaksana: Claude Code (paket perbaikan FIX-5) · Branch worktree
  `worktree-agent-aaa7d039aa12cbeac`, dasar `main` `dc2bc4c` (gelombang 1–3 + printer F + C72 G + PREP-H + FIX-1/2/3a/3b +
  keputusan koordinator). Commit: `027a1fc` (server), `57efd2f` (layar), `294cceb` (laporan), `a645522` (gabung `main`
  `6d76afd` = FIX-4), penyesuaian standar UI + laporan akhir.
- Bahan: `docs/rfid/hasil/PREP-H-GATE-PERFORMA.md` §3.5/§9 (terima transfer & tiba PA ±18 kueri/roll; `inventory_movements.id`
  tanpa index), B3a SCH-9 (index `id` tidak ada di 131/132 koleksi), B3b LST-01/03/07 (daftar tanpa halaman, `limit` tanpa
  batas, N+1 daftar), B1b UI-46 (Lokasi Rak 12–21 dtk, 1.509 tombol) & UI-51 (`loadAll` 3×), B4 §3.8 (penampil ribuan roll),
  pertanyaan pemilik 9 Nov ("ada banyak data juga bagaimana optimizednya?", "roll bisa sangat banyak — ada cara lebih mudah
  UI/UX-nya?").
- Lingkungan: stack sementara `kn-tmp-fix5-*` (Mongo 7 `--memory 1g --wiredTigerCacheSizeGB 0.4`, backend `--memory 1500m`,
  satu proses uvicorn), salinan `kn_test_trial_2026-11-08` dipulihkan sebelum tiap putaran, tanpa mount folder Windows, tanpa
  peramban. Stack bersama `kn-uji-*` dan DB koordinator tidak disentuh. Data sintetis dihapus (drop DB) sesudah pengukuran;
  kontainer `kn-tmp-fix5-{mongo,be,fe}` dihapus beserta dua volume anonim Mongo milik `kn-tmp-fix5-mongo` (dibuat
  10.24.58Z, ±428 MB).
- **Catatan lingkungan (penting untuk koordinator):** di tengah sesi **disk C: host penuh (0 MB bebas)** — dilaporkan alat
  berkali-kali sejak ±18.20 WIB; Docker sendiri melaporkan 9,7 GB build cache + 10,3 GB volume yang bisa diklaim (bukan
  milik paket ini, tidak saya hapus). Saya hanya menghapus berkas sementara saya sendiri (tar sumber 260 MB, data sintetis di
  Mongo). Menjelang akhir sesi ruang bebas kembali (±2,5 GB, bukan karena tindakan saya selain itu) → suite Jest penuh
  dijalankan sesudah gabung `main` (§6.3).

---

## 1. Ringkasan

* **Uji batas kinerja PREP-H yang merah kini hijau.** `test_prep_h_gate_perf.py::…2000_rolls…txn_completes`: transaksi latar
  terima transfer 2.000 roll **148 dtk (gagal, data acuan) / 138,8 dtk (gagal, 346.700 roll) → 7,6 dtk / 10,5 dtk**.
  Langsung di layanan pada volume produksi: terima transfer 2.000 roll **8,4 dtk**, tiba PA 2.000 roll **4,5 dtk**.
* **Hasil DB identik** sebelum vs sesudah pada skenario yang sama (530 roll, 724 mutasi, 18 saldo, 3 lot, transfer, PA, SO &
  tugas pindahan — ternormalisasi) di data acuan **dan** di volume 346.700 roll (`scripts/fix5_equivalence.py`).
* **Index `id` unik-parsial (`uq_id`)** di 40 koleksi jalur WMS-RFID & stok (sensus: **0 `id` kembar** di 166 koleksi data
  acuan) + 10 rujukan bersarang roll + 7 index jalur panas. Contoh volume: upsert mutasi per `id` **COLLSCAN 685.630 dok
  330 ms → IXSCAN 0 ms**; roll per `reserved_ref.id` 275 → 2 ms; tag per EPC 138 → 0 ms. **Start backend pada volume
  produksi 71,6 dtk → 22–24 dtk** (index dibuat di awal bootstrap; start pertama yang membangun index 29,3 dtk).
* **Daftar tidak lagi memotong diam-diam**: `limit` dibatasi di 12 endpoint (dulu `limit=-1` → 500), jumlah sungguhan +
  "Muat berikutnya" di Kedatangan, Perintah Simpan ke Rak (kini **semua PA berjalan** tampil), Transfer, Tag RFID, Insiden.
* **Roll dalam jumlah besar (jawaban untuk pemilik):** tab Stok › Roll punya tampilan **"Kelompok"**: Produk › Lot › Lokasi
  (gudang · bin) › Roll — dikelompokkan & dihitung di server (jumlah roll, total & min–maks panjang, jumlah lot/lokasi, jumlah
  roll per status), tertutup bawaan, roll dimuat 50 per klik. Lokasi Rak merender baris antrean bertahap; muat awal aplikasi
  tidak lagi 3× (UI-51).

## 2. Temuan yang ditutup (ID → perubahan → uji)

Uji baru: `backend/tests/test_fix5_perf_wms.py` (**31 uji**; di kode dasar **24 gagal**, 7 lulus = penjaga/endpoint yang memang
sudah berbatas) dan `frontend/src/features/__tests__/fix5PerformaWms.test.js` (**4 uji**; UI-51 di dasar: dasbor dimuat
**3×**, diharapkan 1; tiga lainnya menguji modul baru). Alat ukur/kesetaraan: `scripts/fix5_equivalence.py`,
`scripts/wms_perf_bench.py`.

| ID | Perubahan | Uji |
|---|---|---|
| **PREP-H §9** terima transfer ±18 kueri/roll (gate IN 2.000 roll ±3 mnt) | `transfer_receipt_service.receive`: `_ReceiptMemo` per panggilan — roll yang dirujuk dibaca **sekali** (`$in` id → nomor roll → EPC/kode tag aktif, urutan & aturan sama dengan `_find_roll`), produk sekali, `warehouse_violations` sekali per (PT, produk, grade), status SO & tahap journey tujuan sekali; **saldo segmen dibangun ulang per 100 roll mendarat + di akhir (juga saat galat, `finally`)** — dulu `rebuild_balance` 2× PER ROLL, masing-masing membaca semua roll segmen & menghitung ulang semua lot segmen. CAS per roll, mutasi & update tag per roll **tidak diubah** (jendela kehilangan saat proses mati tetap 1 roll). Baris ganda dalam satu permintaan tetap "sudah" (keadaan roll yang baru ditulis diingat). CAS kalah → klasifikasi dari pembacaan **segar** (`_cas_lost`), sama dengan hasil pembacaan per baris dulu. | `test_transfer_receive_rebuilds_per_batch_and_balance_correct` (rebuild ≤ 16× untuk 300 roll — dasar 600×; saldo tersimpan = hitung ulang segar), `test_transfer_receive_line_resolution_guard` (penjaga), `test_prep_h_gate_perf.py`, kesetaraan §4 |
| **PREP-H §9** tiba PA per roll | `putaway_order_service._land_items`: produk sekali per PA (`$in`), pelanggaran tujuan sekali per (produk, grade), mutasi id-deterministik lewat **`bulk_write` upsert** per 1.000 (dulu upsert satu-satu tanpa index `id` = COLLSCAN mutasi ×2 per roll). | `test_putaway_trip_checks_destination_once_per_product_grade` (≤ 2× untuk 240 roll; mutasi 480, trip ulang = duplikat, tidak bertambah), kesetaraan §4 |
| **PREP-H §3.5** `inventory_movements.id` tanpa index · **B3a SCH-9** index `id` tidak ada (131/132) | `indexes.ensure_id_indexes`: `uq_id` = **unik + parsial `{id: {$gt: ""}}`** pada 40 koleksi (stok/roll, RFID, dokumen WMS, order & mitra yang dibaca gudang — daftar `ID_INDEX_COLLECTIONS`). Parsial `$gt ""` dipilih karena **dipakai planner** untuk `{id}` & `{id:{$in}}` (diuji `explain` Mongo 7; parsial `$type:"string"` TIDAK dipakai); dokumen tanpa `id`/`id` null/kosong tidak ikut index sehingga tidak saling bentrok. Bila data sudah kembar → index **non-unik** `kn_id_dupe` + galat berisik + daftar `id_dupes` (temuan data). `kn_gate_id_1` (PREP-H, kunci sama) dibuang; `rfid_v2_core.ensure_indexes` kini memanggil `ensure_id_index` untuk entri `id` (tanpa ini index lama lahir lagi tiap start). Dipanggil di **awal** `run_bootstrap` (migrasi start ikut cepat) dan lagi di `ensure_performance_indexes`; hanya koleksi yang sudah ada (tidak membuat koleksi kosong); idempoten. | `test_id_index_unique_partial_and_used[11 koleksi]` (index ada, unik-parsial, `explain` memakai `uq_id`, tanpa `kn_gate_id_1`) |
| **B3a SCH-9** rujukan bersarang tak terindeks (`reserved_ref.id` dipakai 46 kueri, index `reserved_ref` utuh tak terpakai) | Index parsial `kn_ref_*` di `inventory_rolls`: `reserved_ref.id`, `transfer_ref.id`, `last_transfer.ref_id`, `returned_from_transfer.ref_id`, `active_movement.id`, `bucket_ref.id`, `length_reservations.id`, `length_reservations.ref.id` (lepas reservasi SO dulu COLLSCAN), `earmarked_for.id`, `acquired.ref_id`. Jalur panas: `rfid_tags.epc`, `rfid_tags(owner_entity_id,status,encoded_at)`, `putaway_orders(status,created_at)`, `warehouse_transfers(status,created_at)`, `wms_tasks(allocation_id,flow_type,status)`, `material_reservations(product_id,status)`. | `test_roll_reference_fields_indexed`; explain §3.4 |
| **B3b LST-07 / N+1 opname** | Cycle count `complete`: EPC lebih (salah lokasi/asing) dibaca sekaligus (tag → roll → gudang = 3 kueri, dulu 3 per EPC). `rebuild_balance` hanya membaca field yang dihitung (dulu dokumen roll utuh × semua roll segmen). Pemenuhan SO/alokasi: per roll tetap satu CAS (wajib untuk kebenaran konkuren) — biaya per roll kini IXSCAN (`uq_id`, `kn_ref_reserved_ref_id`, `kn_ref_length_reservations_ref_id`), bukan COLLSCAN. | regresi §6; explain §3.4 |
| **B3b LST-03** `limit` tanpa batas / negatif (17 endpoint) | `pagination.clamp_limit` (bukan angka / < 1 → bawaan; > batas → batas): GRN 500, PA 500, transfer 500, tag 2.000, insiden 500, bacaan 300 (dulu `-1` → 500), lintasan 100, lot tanpa halaman 1.000, klaim makloon 500, interco transaksi/settlement/retur 500, roll tanpa halaman 5.000. Sisanya (rolls/available, rolls-without-cost, putaway/suggest, low-stock-summary, config/history, lots/unassigned) sudah dijepit di kode dasar. | `test_list_limit_negative_and_huge_are_bounded[12 endpoint]` (6 gagal di dasar: interco ×3, insiden, bacaan, lintasan) |
| **B3b LST-01** batas keras diam-diam (WMS-RFID) | Server: `skip` + jumlah sungguhan — header `X-Total-Count`/`X-Truncated` (sudah diekspos CORS, KN-D25) untuk `/goods-receipts`, `/transfers`, `/wms/tasks` (aktif ≤ 2.000 + riwayat 200, `X-Truncated` = tugas AKTIF terpotong); `total/truncated/skip/limit` di badan `/putaway-orders` (+ `status=live` = draf/terbuka/dikirim/tiba sebagian), `/rfid/tags`, `/rfid/incidents`; `/inventory/rolls` tanpa halaman: `X-Truncated` dari baris ke-(n+1), jumlah hanya bila `with_total=1`. Layar: `ListLimitNote` ("Menampilkan a–b dari N … Muat berikutnya") di Kedatangan (chip = jumlah sungguhan), Perintah Simpan ke Rak (semua PA berjalan ≤ 500 + riwayat 100 bertahap), Transfer, Tag RFID (label tab = jumlah sungguhan, dulu "(1000)"), Insiden RFID. | `test_goods_receipts_and_transfers_report_real_total`, `test_putaway_orders_tags_incidents_meta`, `test_unpaged_rolls_and_tasks_say_when_truncated`; Jest "LST-01" |
| **B1b UI-46** (sisa FIX-2) render antrean & muat ulang | `LazyMount` (IntersectionObserver, margin 600 px): 12 baris pertama langsung, sisanya dirender saat mendekati layar lalu menetap (tanpa pustaka baru; tanpa IntersectionObserver = langsung). Pindah halaman antrean hanya memuat antrean (dulu struktur + okupansi gudang ikut dimuat ulang). `_queue_block` **bukan** N+1 DB (fungsi murni tanpa kueri) — tidak diubah. Halaman 100 + jumlah sungguhan sudah dari FIX-2. | Jest "UI-46"; Jest suite terkait (prepCWarehousePutaway, phase4R3) lulus |
| **B1b UI-51** `loadAll` 3× per buka | Efek muat kini dikunci pada identitas pengguna + peran + PT + **sidik izin** (dulu objek `user`, yang dibuat ulang setiap `/auth/me` walau isinya sama); izin yang berubah tetap memuat ulang (dulu `loadAll` malah memakai izin basi dari closure lama). StrictMode dev (2×) tidak diubah (hanya dev). | Jest "UI-51" (dasar: 3 muat, sesudah: 1; izin berubah → 2) |
| **B4 §3.8** penampil ribuan roll · pertanyaan pemilik | `GET /inventory/roll-groups?level=product|lot|location` (agregat `$group` di server, berhalaman ≤ 200 kelompok, cakupan & saringan sama dengan daftar roll lewat helper `_rolls_query`; bawaan **roll fisik di gudang**, `scope=all` untuk semua status). Layar `RollGroupView` (tombol "Kelompok \| Daftar" di Stok › Roll, pilihan diingat per peramban, bawaan "Daftar"): Produk (jumlah roll, total panjang, lot, gudang, status) › Lot (min–maks panjang, lokasi, grade) › Lokasi (gudang · bin / "Belum ditempatkan") › Roll (50 per muat, `/inventory/rolls?scope=physical&bin_id&lot=__none__`). Angka per status roll — **bukan** angka "Tersedia" (tetap satu layanan `stock_figures`, FIX-2). | `test_roll_groups_product_lot_location_consistent` (jumlah tiap tingkat konsisten sampai daftar roll), Jest "roll berkelompok" |

## 3. Angka sebelum / sesudah

### 3.1 Data uji sebesar produksi (`scripts/wms_perf_bench.py synth`, 80 dtk)
| Koleksi | Dokumen | Ukuran | Index |
|---|---|---|---|
| `inventory_rolls` | **346.700** (46.700 acuan + 300.000 sintetis; ±45 % tersedia, ±35 % terkirim, 80 % roll fisik ber-bin) | 275 MB | 76 MB (sebelum FIX-5) |
| `inventory_movements` | **685.630** (85.363 + ±2 per roll) | 256 MB | 202 MB |
| `rfid_tags` | 300.041 | 62,5 MB | 15 MB |
| `inventory_lots` | 1.962 | 0,9 MB | — |
Sama besar dengan uji PREP-H (346.700 roll) dan menyerupai pertumbuhan ±6.000 roll/hari × ±2 tahun. Cache WiredTiger 0,4 GB
(lebih kecil dari produksi yang direkomendasikan PREP-H 4–6 GB) → angka di sini batas atas.

### 3.2 Transaksi gudang (layanan sungguhan)
| Operasi | Sebelum (acuan) | Sesudah (acuan) | Sebelum (346.700 roll) | Sesudah (346.700 roll) |
|---|---|---|---|---|
| Terima transfer, 150 baris (id/nomor/EPC/ganda/asing/rusak, 20 roll SO) | 6.976 ms | 668–737 ms | 5.002 ms | 975 ms |
| Terima transfer, 100 baris | 5.051 ms | 356–386 ms | 3.494 ms | 362 ms |
| Terima transfer berperaturan grade (30 roll) | 823 ms | 104–180 ms | 802 ms | 112 ms |
| Trip PA gate 120 roll (+EPC asing & ganda) | 8.632 ms | 331–339 ms | **82.200 ms** | **355 ms** |
| Trip PA handheld 100 EPC (80 baru) | 5.518 ms | 246–282 ms | 37.203 ms | 264 ms |
| Trip PA 30 roll dengan pengecualian aturan | 1.576 ms | 135–142 ms | 10.341 ms | 160 ms |
| **Gate IN transfer 2.000 roll, transaksi latar** (`test_prep_h_gate_perf`, batas 120 dtk) | **148 dtk+ (gagal)**; putaran regresi kedua 126 dtk berkas (lulus tipis) | **7,6 dtk** | **138,8 dtk (gagal)** | **10,5 dtk** |
| Terima transfer 2.000 roll langsung (4 × 500 baris) / trip PA 2.000 roll | — | — | tidak diukur (perkiraan dari 120 roll: ±23 mnt untuk PA) | **8,4 dtk / 4,5 dtk** |
| close 500 roll p95 / close 2.000 roll (jalur close tidak diubah; kontrol lingkungan) | tidak tercatat | 442 ms / 215 ms | 985 ms / 412 ms | 116 ms / 243 ms |

### 3.3 Start backend
| | Sebelum | Sesudah |
|---|---|---|
| Data acuan, start pertama sesudah restore / start ulang | 12,8 / 10,3–12,3 dtk | 13,3 (membangun `uq_id`) / 11,5 dtk |
| **346.700 roll, start ulang** | **71,6 dtk** | **22,3–23,8 dtk** (start pertama yang membangun semua index baru: 29,3 dtk) |

### 3.4 `explain` (346.700 roll, `wms_perf_bench.py explain`)
| Kueri | Sebelum (rencana · dok diperiksa · ms) | Sesudah |
|---|---|---|
| mutasi per `id` (upsert tiba PA) | COLLSCAN · 685.630 · 330 | IXSCAN `uq_id` · 0 · 0 |
| roll per `reserved_ref.id` | COLLSCAN · 346.700 · 275 | IXSCAN `kn_ref_reserved_ref_id` · 0 · 2 |
| roll diterima transfer (`last_transfer.ref_id`, tiap terima) | COLLSCAN · 346.700 · 222 | IXSCAN · 0 · 0 |
| roll milik transfer (`$or reserved_ref / transfer_ref`, tiap terima) | IXSCAN status · 5.970 · 82 | IXSCAN 2 index ref · 0 · 2 |
| tag per EPC | COLLSCAN · 300.041 · 138 | IXSCAN `kn_epc_1` · 0 · 0 |
| lot per `id` (hitung ulang lot) | COLLSCAN · 1.962 · 3 | IXSCAN `uq_id` · 1 · 0 |
| roll per `id` / `id $in 200` | IXSCAN `kn_gate_id_1` · 1 / 200 · 0 / 12 | IXSCAN `uq_id` · 1 / 200 · 1 / 2 |

### 3.5 Endpoint panas (HTTP, 346.700 roll; p50 / p95 ms dari 10 ulangan + 2 pemanasan; mesin dipakai bersama → fluktuasi ±30 %)
Admin (dua putaran sesudah):

| Endpoint | Sebelum | Sesudah | Ukuran |
|---|---|---|---|
| `/inventory/rolls?page=1&page_size=100` | 90 / 99 | 105 / 135 · 90 / 98 | 94 KB |
| `/inventory/rolls` + gudang | 90 / 172 | 116 / 217 · 92 / 100 | 94 KB |
| `/inventory/rolls?q=<nomor roll>` (cari) | 2.008 / 2.114 | 2.248 / 2.406 · 2.318 / 2.485 | 1 KB — **sisa §8** |
| `/inventory/rolls` tanpa halaman (5.000 baris) | 162 / 369 | 525–604 / 735–740 *(putaran sebelum jumlah dibuat opsional; kini `X-Total-Count` hanya dengan `with_total=1` — tidak diukur ulang, data sintetis sudah dihapus karena disk penuh)* | 4,7 MB |
| `/inventory/roll-groups` per produk (baru) | — (404) | 234 / 308 · 210 / 216 | 23 KB |
| `/inventory/putaway/queue` | 138 / 152 | 187 / 254 · 142 / 218 | 34 KB |
| `/warehouses/{id}/locations` | 146 / 151 | 340 / 435 · 155 / 158 | 157 KB |
| `/warehouses/{id}/stock-tree` | 508 / 528 | 545 / 746 · 527 / 540 | 133 KB |
| `/inventory/movements?page=1` | 157 / 168 | 158 / 181 · 155 / 156 | 35 KB |
| `/lots?page=1` | 18 / 19 | 33 / 43 · 20 / 29 | 39 KB |
| `/inventory/status-board` | 701 / 800 | 689 / 833 · 784 / 1.194 | 510 KB — sisa |
| **`/rfid/tags`** | **116 / 118** | 211 / 216 *(sebelum index daftar tag)* · **17 / 19** | 22 KB |
| `/putaway-orders` · `/transfers` · `/goods-receipts` · `/wms/tasks` | 16 · 22 · 13 · 30 | 17–19 · 24–25 · 16–17 · 32–33 | 2–411 KB |
| `/dashboard` | 486 / 3.904 | 147 / 2.114 · 552 / 3.961 | 1,1 MB — sisa (UI-51) |

Petugas gudang Jakarta (cakupan lokasi): `/rfid/tags` **119 → 21 ms**, `/inventory/rolls` + gudang 151 → 88 ms,
`/inventory/movements?page=1` 1.211 / 1.470 → 1.128 / 1.235 ms (sisa), lainnya setara (±10 %). Bacaan: endpoint daftar ini
memang tidak memakai lookup per `id` — percepatan besar FIX-5 ada di **transaksi** (§3.2) dan start (§3.3); endpoint baca
tidak memburuk kecuali `/inventory/rolls` tanpa halaman yang sementara membayar jumlah (sudah dijadikan opsional).

## 4. Kesetaraan hasil (sebelum vs sesudah, skenario yang sama)
`scripts/fix5_equivalence.py` menjalankan layanan sungguhan pada data deterministik `*_EQ5_*`: 2 transfer (250 roll — id,
nomor roll, EPC, baris ganda dalam & antar panggilan, kode asing, rusak + keterangan, 20 roll berkomitmen SO dengan alokasi &
tugas ambil yang ikut pindah; 30 roll ke gudang beraturan grade → ditolak → pengecualian supervisor → ditahan) dan 2 PA (trip
gate + EPC asing/ganda, trip yang sama diulang, trip handheld tumpang tindih, tutup sisa → kembali ke transit; PA ke gudang
beraturan grade → pengecualian). Keluaran: roll (status, gudang, bin, rujukan, `last_transfer`, journey, hold, `last_pa_landed`),
tag, mutasi, saldo, lot, dokumen transfer/PA/SO, tugas, dan hasil per baris — dinormalisasi (tanpa waktu/id acak).

| Putaran | Hasil |
|---|---|
| Data acuan: kode dasar vs FIX-5 | **IDENTIK** (530 roll, 530 tag, 724 mutasi, 18 saldo, 3 lot, 2 transfer, 2 PA, 1 SO, 6 tugas, 9 hasil panggilan) |
| 346.700 roll: kode dasar vs FIX-5 | **IDENTIK** (sama) |
Catatan: putaran pertama sempat berbeda karena **perapian data uji** saya (tugas pindahan ber-id acak dan `site_EQ5` tertinggal
dari putaran dasar — index `uq_id` justru menolak `site_EQ5` kembar); skrip diperbaiki (hapus per `order_id` & id situs),
diulang → identik.

## 5. Perubahan perilaku untuk pengguna
1. **Stok › Roll**: tombol baru "Kelompok | Daftar". Kelompok = Produk › Lot › Lokasi › Roll (stok fisik di gudang), angka per
   kelompok dihitung server. Daftar = seperti dulu (bawaan).
2. **Kedatangan (GRN)**: angka chip status = jumlah sungguhan; bila lebih dari 100, muncul "Menampilkan kedatangan 1–100 dari
   N" + "Muat berikutnya" (dulu 100 terbaru tanpa tanda).
3. **Perintah Simpan ke Rak**: semua PA yang masih berjalan selalu tampil (≤ 500), riwayat selesai bertahap 100 per muat.
4. **Transfer**: catatan "a–b dari N" + "Muat berikutnya" bila > 200 (saringan/cari layar hanya atas yang sudah dimuat — disebut).
5. **Tag RFID**: label tab "Tag Aktif (N)" = jumlah sungguhan (dulu "(1000)"); catatan + muat berikutnya.
6. **Insiden RFID**: catatan bila lebih dari 100 insiden (dulu terpotong diam).
7. **Lokasi Rak**: baris antrean muncul bertahap saat digulir; pindah halaman tidak memuat ulang KPI/struktur.
8. **Aplikasi**: data awal (dasbor dkk.) dimuat sekali per buka, bukan 3× (UI-51); izin yang berubah tetap memuat ulang.
9. **API**: `limit` tidak sah/negatif → nilai bawaan (dulu 500 untuk bacaan RFID), di atas batas → batas (§2 LST-03).
   `/inventory/rolls` tanpa halaman membawa header `X-Truncated` (`X-Total-Count` bila tidak terpotong atau `with_total=1`).
10. **Integritas data**: menyisipkan dokumen dengan `id` yang sudah ada di 40 koleksi kini **ditolak DB** (`E11000`) — dulu
    diam-diam membuat kembar (data acuan: 0 kembar; uji regresi §6 tidak menunjukkan jalur yang bergantung pada kembar).

## 6. Uji & regresi (apa adanya)

### 6.1 Uji baru
| Uji | Dasar `dc2bc4c` | FIX-5 |
|---|---|---|
| `test_fix5_perf_wms.py` (31) | **24 gagal**, 7 lulus (penjaga resolusi baris + 6 endpoint yang memang sudah berbatas) | **31 lulus** |
| Jest `fix5PerformaWms.test.js` (4) | UI-51 **gagal** (dasbor 3×; 3 lainnya menguji modul baru) | **4 lulus** |
| `test_prep_h_gate_perf.py` (3) | data acuan: gagal (148 dtk+) lalu lulus tipis di putaran regresi (126 dtk berkas); 346.700 roll: **gagal** (138,8 dtk) | data acuan & 346.700 roll: **3 lulus** (txn 7,6 / 10,5 dtk) |

### 6.2 Perbandingan regresi (pytest, satu proses per berkas, DB dipulihkan bersih sebelum tiap putaran)
Berkas = semua `tests/test_*.py` yang menyebut jalur yang diubah (transfer, putaway, GRN, tag/insiden/bacaan/lintasan RFID,
`inventory/rolls`, lot, tugas WMS, interco, klaim makloon, cycle count, lokasi, index, roll-groups) + uji gate PREP-D1/D2/H =
**113 berkas**.

| Putaran | Lulus | Gagal | Error | Lewat | id gagal/error unik | Waktu |
|---|---|---|---|---|---|---|
| Dasar `dc2bc4c` (+ berkas uji FIX-5) | 935 | 294 | 70 | 85 | 364 | 672 dtk + uji kinerja |
| FIX-5 `57efd2f` | **959** | **270** | 70 | 85 | **340** | 537 dtk |

* **Hanya gagal di FIX-5: 0.** Gagal di dasar & lulus di FIX-5: 24 (seluruhnya uji baru `test_fix5_perf_wms.py`).
* Kegagalan lama (340 id, sama persis di kedua putaran) adalah kegagalan yang sudah ada di dasar (uji lama yang bergantung
  pada data/peran lama, sama dengan pola laporan FIX-2/FIX-3) — tidak disentuh paket ini.
* Daftar mentah ada di kontainer uji selama sesi (`/tmp/regress_{base,new}*.txt`; kontainer sudah dihapus). Pemilihan berkas:
  `tests/test_*.py` yang memuat salah satu pola `transfer_receipt|/transfers|putaway|goods-receipts|/rfid/(tags|incidents|reads|passages)|inventory/rolls|/lots|/wms/tasks|interco/(transactions|settlements|returns)|makloon-orders/claims|cycle_count|cycle-count|warehouses/.*/locations|indexes|roll-groups`
  + `test_fix5_perf_wms`, `test_prep_h_gate_worker/perf`, `test_prep_d1_gate_v2`, `test_prep_d2_gate_txn`; satu proses
  `pytest -q -p no:cacheprovider -n0 -rfE` per berkas, batas 900 dtk.

### 6.3 Jest & ESLint
* Suite Jest terkait berkas yang diubah (8 suite: `fix5PerformaWms`, `fix1Cakupan`, `fix3aForms`, `phase4R3`,
  `prepCWarehousePutaway`, `trial22Okt`, `uat24F0`, `navAccess`): **8/8 suite, 71/71 uji lulus** (kontainer `node:20` +
  volume `kn-dev_fe_node_modules` baca-saja).
* **Suite Jest penuh** (sesudah gabung `main` + FIX-4, §6.5; dijalankan setelah disk host lega kembali): **84/85 suite,
  603/604 uji lulus**. Satu gagal: `config/__tests__/serverAccessReach.test.js` ("manager → logistics tidak sampai") — masukan
  uji itu (`config/`, fixture akses, `navigationConfig`, `roles`) **identik dengan `main`** (`git diff main` kosong untuk
  berkas tersebut; FIX-5 tidak menyentuh navigasi/izin) → kegagalan bawaan `main`, bukan FIX-5.
* ESLint 13 berkas FE yang diubah/baru (sesudah gabung): **0 error**, 15 peringatan "Unused eslint-disable directive" (pola
  lama berkas-berkas itu — konfigurasi ESLint repo tidak memuat aturan `react-hooks`; direktif baru mengikuti pola yang sama).

### 6.4 Guardrail
Dijalankan di kontainer uji (Linux, dependensi backend lengkap; berkas dasar `dc2bc4c` vs FIX-5 pada kontainer yang sama,
DB salinan). `verify_state_machine` **dikecualikan** (larangan brief).

| Hasil | Guardrail |
|---|---|
| Kode keluar & jumlah pelanggaran **identik** dasar = FIX-5 (41 guardrail) | merah lama tetap sama: `approval_queues` 3, `atomic_claim` 6, `auth_coverage` 28, `entity_label` 2, `line_scope` 17, `no_secrets` 10, `numeric_bounds` 3 (FAIL-HARD), `qty_dual` 5, `ref_unlink` 3, `to_list_bound` 6 (INV-PERF-01); 31 lainnya hijau (termasuk `scope_guard`, `list_export`, `roll_identity`, `rfid_tag_unique`, `error_notice`, `knselect_contract`, `codebase_map`) |
| Angka merah yang naik | **tidak ada** |

Catatan jujur: putaran pertama guardrail saya jalankan di **host Windows** untuk semua `verify_*.py` dengan loop berkas —
`scripts/guardrails/verify_state_machine.py` ikut terpanggil dan **langsung gagal impor** (`No module named 'pymongo'`)
tanpa menyentuh DB mana pun; putaran host itu tidak dipakai (separator jalur Windows memberi hitungan palsu).

Sesudah gabung `main` (FIX-4 membawa guardrail baru): `verify_ui_standard` (ratchet G-UI) awalnya **merah 8** karena kode
baru FIX-5 memakai hex/huruf arbitrer & tombol bergaya sendiri → disesuaikan ke token & kelas baku (`text-fs-12/13`,
`text-kn-*`/`bg-kn-*`, `ghost-button`/`secondary-button btn-sm`/`primary-button btn-sm`) → **PASS (4.316 cek, 0
pelanggaran)**; angka `font_lt12` 6.937 → 6.935 dan `hex` 16.810 → 16.808 (turun), lainnya = baseline. `verify_ui_contrast`
PASS 58/58.

### 6.5 Gabung `main` terbaru (FIX-4 Standar UI)
`main` maju ke `6d76afd` (FIX-4 + integrasi) selama paket berjalan → digabung ke branch ini (commit `a645522`). Konflik teks
hanya di **baris impor** 4 berkas (`GoodsReceiptsView`, `TransferManagement`, `RfidTagsView`, `RfidSecurityPanel`: impor
`ExportMenu` FIX-4 + `ListLimitNote` FIX-5) dan satu baris chip GRN (jumlah sungguhan FIX-5 + tombol Unduh FIX-4) — keduanya
dipertahankan. Tidak ada berkas backend yang diubah kedua paket. Regresi pytest §6.2 dijalankan **sebelum** gabung
(backend FIX-4 = Pusat Export & dataset ekspor, +3 baris `permissions_config`, +1 baris `entity_write_guard`, uji
`test_fix4_ekspor.py` — tidak tumpang tindih dengan berkas FIX-5; uji gabungan backend belum dijalankan); Jest penuh, ESLint & guardrail UI
dijalankan **sesudah** gabung.

## 7. Keputusan implementer (mohon ditinjau)
1. **`uq_id` UNIK**, bukan non-unik (brief: unik bila data mengizinkan): sensus 166 koleksi data acuan = 0 kembar. Data
   produksi yang ternyata kembar tidak menggagalkan start — koleksi itu mendapat index non-unik `kn_id_dupe` + galat log.
2. **Parsial `{id: {$gt: ""}}`** (bukan penuh): index penuh unik akan menolak dokumen ke-2 tanpa `id`; `$type:"string"`
   tidak dipakai planner untuk `{id: …}` (diuji). Kueri `{id: None}`/regex tidak memakai index (jarang, bukan jalur panas).
3. **Hanya 40 koleksi jalur WMS-RFID & stok** (bukan semua 166): koleksi log/riwayat bisa saja sengaja menyimpan `id` dokumen
   lain berulang; unik di sana berisiko menolak tulisan. Sisanya = sisa §8.
4. **`kn_gate_id_1` dibuang** bila `uq_id` ada (kunci sama; dua index = tulis & memori ganda); `rfid_v2_core` (berkas PREP-H)
   hanya diubah di cabang index `id`.
5. **Saldo dibangun ulang per 100 roll + di akhir**, bukan per roll: hasil akhir identik (§4); bila proses mati di tengah,
   paling banyak 100 roll yang sudah pindah punya saldo basi sampai rebuild segmen berikutnya (dulu ≤ 1 roll). Mutasi & tag
   tetap ditulis per roll agar jejak tidak hilang.
6. **CAS kalah dibaca ulang** (bukan langsung "sudah"): hasil sama dengan pembacaan per baris dulu pada balapan.
7. **`limit` dijepit, bukan 422**: pemanggil lama yang mengirim angka besar tetap jalan; bawaan tidak diubah.
8. **`/inventory/rolls` tanpa halaman**: `X-Total-Count` saat terpotong hanya dengan `with_total=1` (menghitung 346.700 roll
   +0,3 dtk; tidak ada layar yang memakainya — layar memakai mode berhalaman yang sudah membawa `total`).
9. **Panel PA**: dua permintaan (semua PA berjalan ≤ 500 + riwayat 100) — menjamin PA aktif lama selalu tampil.
10. **Tampilan Kelompok bawaan "Daftar"**: tidak mengubah kebiasaan/uji yang ada; satu klik ke "Kelompok", diingat per peramban.
    Angka kelompok = jumlah roll per **status roll**, bukan "Tersedia" (satu definisi FIX-2).
11. **`LazyMount`** (IntersectionObserver) alih-alih pustaka virtualisasi: tanpa dependensi baru, baris yang sudah tampil
    menetap (pilihan bin/saran tidak hilang saat digulir).
12. **UI-51**: kunci efek = id pengguna + peran + PT + sidik izin; perubahan izin kini benar-benar memakai izin baru.
13. **Komponen baku FIX-4 tidak diubah**: `ListLimitNote` diletakkan di `features/wms/`, bukan `components/`.

## 8. Sisa / di luar cakupan
1. **Cari roll `?q=`** 2,0–2,5 dtk pada 346.700 roll (regex "mengandung" di 6 field + nama produk → pindai penuh). Usul: jalur
   cepat nomor roll/EPC tepat (pindai), cari awalan ber-index, atau index teks.
2. `/inventory/status-board` 0,7–1,2 dtk, `/warehouses/{id}/stock-tree` ±0,5 dtk, `/dashboard` p95 2–4 dtk (1,1 MB;
   rekomendasi UI-51: data dasbor dimuat layar pemakainya) — wilayah FIX-2/kerangka aplikasi.
3. `/inventory/movements?page=` untuk petugas berpagar lokasi 1,1–1,2 dtk (hitung atas saringan gudang) — usul index
   `inventory_movements(warehouse_id, timestamp)`; belum diukur (data sintetis sudah dihapus karena disk penuh).
4. `rebuild_balance` tetap menghitung ulang **semua lot** segmen setiap kali (±4 kueri per lot) — kini sekali per 100 roll,
   tetapi segmen dengan ratusan lot historis tetap mahal; usul: hitung ulang hanya lot roll yang berubah (perubahan kontrak hook).
5. `_rehome_allocation` (roll transfer berkomitmen SO) masih per roll (baca + tulis SO per roll) — semantik pembatalan tugas
   sumber berurutan; dibiarkan, dibatasi jumlah roll SO.
6. LST-01 lainnya (±40 daftar): pengiriman 1.000/riwayat 3.000, Meja Cutting (LST-02), antrean periksa gate kursor (LST-09),
   daftar tugas HP (`/wms/tasks` 2.000 aktif + `scan_log` penuh; kini bertanda header, layar HP belum menampilkan catatan).
7. Index `id` untuk ±127 koleksi lain (di luar jalur WMS-RFID & stok).
8. Suite gate 96 berkas PREP-H penuh tidak dijalankan ulang (yang dijalankan: 113 berkas §6.2); uji backend sesudah gabung
   `main` (FIX-4) belum dijalankan (berkas tidak tumpang tindih).
9. Disk host C: sempat penuh (0 MB) ±18.20–18.55 WIB — perlu pembersihan Docker build cache/volume tak terpakai (milik paket
   lain) oleh koordinator/pemilik agar stack uji berikutnya tidak macet.
10. `CODEBASE_MAP.md` tidak dibangkitkan ulang.

## 9. Berkas berisiko bentrok
* Server: `backend/routers/inventory.py` (`list_rolls` direfaktor ke `_rolls_query`/`_roll_search` + endpoint baru),
  `backend/services/roll_service.py` (proyeksi `rebuild_balance` saja), `transfer_receipt_service.py` (`receive` dipecah,
  `_land(memo=)`), `putaway_order_service.py` (`_land_items`, `list_orders(skip=)` + `count_orders`), `indexes.py`,
  `bootstrap.py` (+7 baris di awal `run_bootstrap`), `services/rfid_v2_core.py` (cabang index `id`), router `goods_receipts`,
  `transfers`, `putaway_orders`, `rfid`, `wms`, `lots`, `interco`, `makloon_orders`; `rfid_service.list_tags`,
  `rfid_incident_service.list_incidents`, `cycle_count_service.complete`, `pagination.py` (+3 helper).
* Layar: `InventoryStockView.jsx`, `LocationPutawayView.jsx`, `PutawayOrdersPanel.jsx`, `TransferManagement.jsx`,
  `grn/GoodsReceiptsView.jsx`, `grn/grnApi.js`, `rfid/RfidTagsView.jsx`, `rfid/RfidSecurityPanel.jsx`,
  `hooks/useAppActions.js` — FIX-4 (tombol ekspor di layar daftar) kemungkinan menyentuh bilah alat layar yang sama; perubahan
  saya menambah catatan di bawah daftar, tidak mengubah bilah alat/komponen baku.

## 10. Ringkasan untuk koordinator
* **Perubahan:** index `uq_id` unik-parsial di 40 koleksi + 10 rujukan roll + 7 jalur panas (awal bootstrap); terima transfer
  & tiba PA tanpa N+1 (memo per panggilan, saldo per 100 roll, mutasi `bulk_write`); `limit` dijepit + jumlah sungguhan +
  "Muat berikutnya" di 5 daftar WMS-RFID; endpoint & layar **roll berkelompok Produk › Lot › Lokasi › Roll**; Lokasi Rak
  render bertahap; `loadAll` sekali.
* **Angka:** gate IN 2.000 roll transaksi 148 / 138,8 dtk (merah) → **7,6 / 10,5 dtk** (hijau); trip PA 120 roll pada 346.700
  roll **82,2 dtk → 0,36 dtk**; start backend volume **71,6 → 22–24 dtk**; upsert mutasi per id 330 ms COLLSCAN → 0 ms;
  `/rfid/tags` 116 → 17 ms. Endpoint baca lain setara (cari roll 2 dtk = sisa).
* **Kesetaraan:** DB ternormalisasi sebelum/sesudah **identik** (acuan & 346.700 roll).
* **Uji:** baru 31 pytest (24 gagal di dasar → 31 lulus) + 4 Jest (UI-51 gagal di dasar → lulus); regresi 113 berkas
  dasar 935 lulus / 364 id gagal-error → FIX-5 959 / 340, **0 yang hanya gagal di FIX-5**; Jest terkait 8 suite 71/71
  + Jest penuh sesudah gabung 84/85 suite (1 gagal bawaan `main`: `serverAccessReach`); ESLint 0 error; guardrail 41 identik
  dengan dasar (tidak ada yang naik) + `verify_ui_standard` FIX-4 PASS sesudah penyesuaian token/kelas baku.
* **Berisiko bentrok:** `routers/inventory.py`, `transfer_receipt_service.py`, `putaway_order_service.py`, `indexes.py`,
  `bootstrap.py`, `rfid_v2_core.py` (index), layar daftar WMS (catatan batas) & `useAppActions.js`.
* **Sisa utama:** cari roll regex, status-board/stock-tree/dashboard, mutasi berpagar lokasi, lot rebuild per segmen, ±40
  daftar lain, index `id` koleksi lain. **Disk C: host sempat penuh — perlu dibersihkan.** Branch sudah memuat `main`
  (FIX-4) — konflik impor diselesaikan (§6.5).

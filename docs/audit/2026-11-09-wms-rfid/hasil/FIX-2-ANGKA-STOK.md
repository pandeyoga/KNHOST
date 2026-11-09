# FIX-2 — Satu rumus angka stok + aturan "dua angka" (LOKAL + GLOBAL) dengan rincian

**Tanggal:** 9 Nov 2026 (WIB) · **Paket:** FIX-2 · **Implementer:** Claude Code (worktree `agent-a40d21bb6c3b9386e`)
**Dasar:** `main` sesudah `git merge --ff-only main` (gelombang 1–3 + audit B1, B1b, B2a, B2b, B3a, B3b, B4).
**Bahan:** B3a §5/§10/§11 + lampiran uji angka, B1 UI-06/07/40 + K-B1-03, B1b UI-45/46/54/59 + K-B1-12, B4 §1.2/§3.7
(ADS-1…7), KN_15, KN_32.

> Status: implementasi selesai & ter-commit. **Hasil uji di §6 — lihat catatan pelaksanaan (Docker Desktop host macet di
> tengah sesi; angka yang tercantum adalah yang benar-benar dijalankan).**

---

## 1. Ringkasan

* **Satu layanan angka stok** `backend/services/stock_figures.py` (SSOT perhitungan). Semua endpoint yang mengeluarkan
  kuantitas stok kini mengambil angka dari sana — langsung, atau lewat pembungkus lama (`stock_availability`,
  `sales_stock_service`, `site_stock_service`, `fulfillment_service.build_supply_index`) supaya pemanggil lain tidak putus.
* **API dua angka**: `GET /api/stock/figures?product_ids=…` → per produk `{local, global}` (roll lalu panjang + satuan +
  status habis/rendah/ada); `GET /api/stock/figures/{product_id}` → rincian per site/gedung, per PT, per status, transit
  (dikaitkan ke gedung tujuan), akan datang (PO, transfer, antar-PT, makloon, retur), ATP lokal & global, dan definisi
  tiap angka; `GET|PUT /api/stock/my-site` → lokasi jualan POS disimpan di server. `stock_figures` juga ikut di
  `/products`, `/dashboard`, `/inventory/status-board`, `/product-templates/{id}/summary`.
* **Komponen bersama FE** `frontend/src/components/StockFigures.jsx`: dua angka (LOKAL lalu "Total grup (semua PT)"),
  klik/ketuk → `DetailModal` baku berisi rincian. Dipakai di kartu POS desktop & HP, quick view desktop & HP, Stok & ATP
  desktop & HP, katalog Produk & Varian, HP MD.
* **Uji silang otomatis** `scripts/audit/fix2_stock_crosscheck.py` (dasar: `b3a_compare_numbers.py`): **sebelum 912
  perbandingan / 64 berselisih → sesudah 1.672 perbandingan / 0 berselisih** (endpoint lama + kelompok baru dua angka per
  7 akun & rincian).

---

## 2. Tabel definisi angka (satu definisi; dipakai semua layar)

Satuan = satuan dasar produk; tidak pernah dijumlah lintas satuan; tampil **roll dulu, lalu panjang** (`QtyDual`).
Nama dari KN_32. Definisi tertulis juga di respons API (`definitions`) dan tooltip `StockFigures`.

| Nama (UI) | Rumus | Sumber (kode) | Ditampilkan di |
|---|---|---|---|
| **Gudang yang dihitung** | gudang master `active ≠ false` dan tidak bertanda `is_test: true`; saldo yatim (gudang tak terdaftar) tidak pernah ikut | `stock_figures.warehouse_map/counted_warehouse_ids` | semua angka di bawah |
| **Tersedia** (K-04) | Σ ember `available_qty` saldo yang dibangun ulang dari roll (`rebuild_balance`: roll `available`, tanpa klaim PA, **dikurangi panjang dipesan potong & reservasi**; tahan QC/karantina/blokir/hold/**MD Quality** = status ≠ available) **− cadangan bahan makloon** aktif yang dialokasikan ke gudang PT itu (tersedia terbesar dulu) | `stock_figures.segments` + `allocate_makloon` | semua layar stok |
| **Roll tersedia** | Σ saldo `roll_count` (roll yang masih punya panjang bebas) | `segments` | dua angka, rincian |
| **LOKAL** | Tersedia ∩ PT aktif (mode gabungan: semua PT yang diizinkan) ∩ site kerja: sales/Admin Sales = site POS tersimpan (`users.pos_site_id`) → `location_site_ids[0]` → semua site; gudang = `location_site_ids` (dipersempit `location_warehouse_ids`); peran lain = penugasan lokasi bila ada, selain itu semua site; `?site_id=` menimpa (tampilan saja) | `stock_figures.viewer_scope`, `in_local` (titik kait FIX-1: `location_scope.work_site_ids`) | angka 1 `StockFigures` |
| **GLOBAL / "Total grup (semua PT)"** | Tersedia semua PT × semua gudang yang dihitung; PT di luar izin = angka saja (K-B1-12, B3a #7) | `figures_for` | angka 2 `StockFigures`, rincian |
| **Cadangan makloon** | Σ `material_reservations.qty` (status active) per produk × PT, dialokasikan ke segmen dengan aturan tunggal | `makloon_by_product_entity`, `allocate_makloon` | rincian, kartu POS/HP, pemilih roll, ringkasan Sales |
| **Dipesan** | ember `reserved_qty` (termasuk panjang dipesan untuk dipotong) | saldo | rincian per status/lokasi |
| **Dialokasikan** | `committed_qty + picked_qty + packed_qty` | saldo | rincian; papan stok `total_committed` |
| **Ditahan / QC** | `quarantine_qty + blocked_qty + hold_qty + damaged_qty` (klaim PA masuk `hold_qty`) | saldo | rincian; papan stok `total_hold` |
| **Dalam proses / Di makloon** | `wip_qty` / `subcon_qty` | saldo | rincian |
| **Dalam Perjalanan** | `in_transit_transfer_qty` (+ baris "akan datang" di **gudang tujuan**), `in_transit_intercompany_qty`, `in_transit_inbound_qty`; `in_transit_sales_qty` = "Dikirim ke pelanggan" | saldo + `warehouse_transfers.dest_warehouse_id` | rincian |
| **Stok Fisik** | `on_hand_qty` = Tersedia + Cadangan makloon + Dipesan + Dialokasikan + Ditahan/QC + Dalam proses | saldo | rincian, papan stok |
| **Akan datang** | PO terbuka: `(qty − received_qty) × quantity_base/qty`; transfer dikirim: Σ sisa roll `in_transit_transfer` per dokumen → gudang tujuan; antar-PT pembeli dikonfirmasi/dikirim (`quantity_base`; draf = `tentative`); makloon berjalan: langkah terakhir `expected_output_qty − actual_output_qty` → `target_warehouse_id`; retur penjualan `approved` belum diterima | `stock_figures.incoming_rows` (+ `po_open_base_qty`) | rincian; `_incoming_supply`, papan stok, saran reorder, saldo `on_order_qty` |
| **ATP** | Tersedia + barang masuk dalam horizon (PO terbuka + roll menuju gudang + antar-PT dikonfirmasi) − backorder aktif (sekali per produk×PT). GLOBAL tidak menghitung antar-PT (sudah di stok PT penjual). Horizon = setelan `stock.atp_horizon_days` (bawaan 14) | `atp_policy.compute_atp`, `horizon_days`, `stock_figures.atp_pair` | rincian, Stok & ATP, `/stock/atp`, ringkasan Sales |
| **Status stok** | `habis` (0) · `rendah` (0 < Tersedia < 100, `stock_availability.LOW_STOCK_QTY`) · `ada` | `stock_figures.stock_state` | chip kartu/papan; FE tidak lagi memakai ambang ≤ 40 sendiri |
| **Stok rendah** (jumlah produk) | tetap K-04 per produk × PT | `stock_availability.low_stock_summary` | Control Tower, Dasbor Manajer, Operasi Gudang |

---

## 3. Temuan yang ditutup (ID → perubahan → uji)

| Temuan | Perubahan | Uji |
|---|---|---|
| **STK-1** (P0) katalog Produk & Varian selalu 0 | `product_variant_service.family_summary` → `stock_figures` (Tersedia, Dipesan+Dialokasikan, roll tersedia, `stock_figures` per varian); FE `VariantCard`, `FamilyHero` ("Tersedia (PT aktif)"), `CatalogWorkspace` (+`StockFigures`) | `test_stk1_katalog_produk_varian_tidak_lagi_nol`; uji silang "product-templates summary" |
| **STK-2** (P0) Control Tower "Stok fisik 0" | `AdminHome.jsx` membaca `available`, label **Tersedia** (+tooltip) | Jest `decisionsD1.test.js` "FIX-2 (B3a STK-2)" |
| **STK-6** (P0) ringkasan Sales tanpa committed/wip | `sales_stock_summary`: Fisik = semua status fisik; Bebas − klaim PA/tahan inspeksi − cadangan makloon; Dikunci + dialokasikan; gudang dihitung saja; `makloon_reserved`; teks ATP dibetulkan | `test_stk6_…`; uji silang "sales/stock-summary bebas/fisik" |
| **STK-13** (P0) POS "Di {site}" menghitung potong dipesan | `site_stock_service` dari `segments` (definisi tunggal, + `group_rolls`) | `test_stk13_…`; uji silang "pos/site-stock own_qty" |
| **STK-14** (P0) `/rfid/summary` mentok 5.000 | `count_untagged_rolls` (kueri sama dengan daftar) | `test_stk14_…`; uji silang "rfid/summary" |
| **SSOT-4** (P0) cadangan makloon tak dikurangi di 9 endpoint | satu alokasi `allocate_makloon`; dipakai `/inventory/balances` (+`balance_available_qty`, `makloon_reserved_qty`, `counted`), `/stock/buckets`, `/stock/atp`, stock-breakdown (saldo & matriks), `/sales/stock-summary`, `/pos/site-stock`, `/inventory/rolls/available` (`available_total`, `makloon_reserved_qty`), `/internal-requests-availability`, `/products` `entity_available_qty`, so_verify, restock (`alert_ops_service`), fulfillment-plan (`fulfillment_decision_service`), rekomendasi POS | `test_ssot4_*`; uji silang 13 kelompok endpoint |
| **STK-8** (P1) KPI dasbor "Semua PT" +300 kg | `/dashboard` KPI dari `segments` di cakupan PT+lokasi; makloon per PT pemilik | `test_stk8_…`; uji silang "dasbor KPI Semua PT" |
| **STK-3** (P1) on_order saldo membaca `base_quantity` | `roll_service._on_order_qty` → `po_open_base_qty` (quantity_base); `to_list(500)` dilepas | `test_po_open_base_qty_…` |
| **STK-4** (P1) "datang" = qty PO penuh; draf antar-PT dihitung | `_open_po_incoming`/`_open_interco_incoming` → `incoming_rows` (sisa, satuan dasar; draf `tentative` tidak masuk ATP); `atp_detail` + roll menuju gudang; papan stok kini ikut antar-PT dikonfirmasi | uji silang `stock/atp` |
| **STK-5 / DUP-1** (P1) ≥ 8 definisi "Tersedia", dua saringan gudang | satu definisi; `stock_availability.registered_warehouse_ids` = gudang dihitung | uji silang (0 selisih) |
| **DUP-2** (P1) barang datang 4 rumus | `po_open_base_qty` + `incoming_rows` dipakai saldo, papan stok, ATP, Sales, katalog, reorder | `test_po_open_base_qty_…` |
| **STK-7** (P2) matriks tanpa potong dipesan/hold, batas 5.000 | matriks dari agregasi SELURUH roll (definisi tunggal + makloon per lot terbesar), daftar roll ber-`rolls_total`/`rolls_truncated` | uji silang "stock-breakdown matriks" |
| **STK-9** (P3) "tertahan" memuat dialokasikan | papan stok: `total_committed`, `total_makloon_reserved`, `total_hold` tanpa keduanya; teks rumus FE | — |
| **STK-10** (P3) ambang stok rendah 3 versi; label ATP salah | status dari server (`state`, `low_stock_qty`) di kartu POS/HP, quick view, saringan POS; label "Tersedia > 0" | Jest `stockFigures.test.js` |
| **STK-12** (P2) makloon/transit/retur tak dihitung datang | tampil di rincian "Akan datang" (transfer ke gudang **tujuan**); tidak masuk ATP (lihat keputusan implementer #3) | Jest rincian |
| **SSOT-3** (P1) + keputusan #2 | `roll_hold_service.sync_inspection_hold` (status `blocked`, `hold.source="inspection"`, `prev_status`; pembalikan saat lepas), dipanggil dari simpan baris MD Quality/4-point & `release_hold`; skrip data lama `backend/scripts/migrate_fix2_inspection_hold_status.py` (dry-run bawaan; data acuan 0 kandidat) | `test_keputusan2_…` |
| **SCP-4** (P2) + keputusan #7 | stock-breakdown: roll PT di luar izin = identitas + angka saja (`restricted: true`) | — |
| **DUP-4** (P2) "panjang bebas" lupa di 3 tempat | site stock, fulfillment_decision, matriks produk kini definisi tunggal | uji silang |
| **UI-06 / K-B1-03** (P1) terlalu banyak angka, tanpa angka lokal | `StockFigures` (angka 1 = lokal, angka 2 = grup, sisanya di rincian) di layar kunci | Jest |
| **UI-40** (P1) ATP 60.996 vs 61.071; "Stok Habis" 292 vs 128 | makloon di Multi-Bucket; chip "Habis di cakupan saya" / "Habis di grup" dari angka server yang sama di desktop & HP | `test_ui40_ui45_…`, Jest `figureState` |
| **UI-45** (P1, B1b) angka grup berlabel "Konteks: PT" | kolom & KPI papan stok = cakupan yang tertulis; grup hanya baris kedua "Total grup (semua PT)" (K-B1-12) | `test_ui40_ui45_…` |
| **UI-46** (P1, B1b) Lokasi Rak dipotong 500 diam-diam | antrean berhalaman (bawaan 100, maks 500) + `total`, `total_building`, `truncated`; FE "roll a–b dari N", "gedung ini (semua PT)", tombol halaman; KPI "Belum Ditempatkan" berlabel "gedung ini · semua PT" | `test_ui46_…` |
| **UI-54** (P2, B1b) HP Masuk "30 terbuka" | hitungan "N perlu dikerjakan · M menunggu/ditolak QC", pil abu untuk tugas QC | — |
| **UI-59** (P3, B1b) roll tanpa pemisah ribuan | `formatQty` di Lot & Silsilah, Lokasi Rak (KPI & tab), Master Grade | — |
| Keputusan #3 (site POS di server) | `PUT /stock/my-site`; `savePosCtx` menyimpan ke server; "Mulai jualan" bawaan `pos_site_id` | `test_keputusan3_…` |
| Keputusan #4 (horizon setelan) | `atp_policy.horizon_days()` membaca `stock.atp_horizon_days` (katalog setelan `config_catalog_ops.py`, grup stok-satuan) | `test_keputusan4_…` |

---

## 4. Perubahan perilaku untuk pengguna

1. **Angka "Tersedia" turun sebesar cadangan makloon** di semua layar yang dulu tidak menguranginya (contoh data acuan:
   DMO-GRY-KNT-001 2.997,62 → 2.697,62 kg; KNKNT0021-L-BEIX 5.684,33 → 5.609,33 kg; PT Kanda "stok PT" di katalog 477,63
   → 177,63 kg — kini sama dengan dasbor). Kolom `/inventory/balances` "Tersedia" mengikuti; angka saldo mentah tetap
   dikirim sebagai `balance_available_qty`.
2. **POS/HP "Di {lokasi}"** tidak lagi menghitung panjang yang dipesan untuk dipotong (BTK-MEGA-001 Jakarta 12 → 10 yd).
3. **Ringkasan stok Sales** "Fisik" kini termasuk barang dialokasikan/dalam proses (BTK-MEGA-001 KSC 162 → 662 yd);
   "Bebas" dikurangi cadangan makloon; tampil "Cadangan makloon" bila ada.
4. **Katalog Produk & Varian** menampilkan stok sungguhan (dulu 0) — "Tersedia (PT aktif)" + dua angka per varian.
5. **Control Tower** "Stok Perlu Reorder": angka sungguhan berlabel **Tersedia** (dulu "Stok fisik 0").
6. **Ringkasan RFID** "roll belum ber-tag" = jumlah sungguhan (KSC ±23.274, dulu 5.000).
7. **Kartu POS & HP sales**: tiga baris (Di {site} · PT · Grup) diganti **dua angka** (lokasi jualan × PT penjual, lalu
   Total grup) — ketuk → rincian. Lencana: "Habis" hanya bila grup habis; "Habis di lokasi ini" bila lokal 0 tetapi grup
   ada (tombol jual tetap aktif — pemenuhan lintas PT diputuskan Admin Sales, perilaku lama).
8. **Stok & ATP (desktop & HP)**: kolom/KPI = cakupan "Konteks" (PT sendiri); grup hanya angka kedua. Untuk sales/gudang
   angka utama ATP/Stok Fisik/Dipesan **turun dari angka grup ke angka PT sendiri** (UI-45). Chip "Stok Habis" diganti
   "Habis di cakupan saya" + "Habis di grup" (angka sama di desktop & HP). HP: kartu = dua angka; ATP/akan datang/per
   gudang di rincian.
9. **Roll yang ditahan MD Quality / 4-point** (warna/handfeel) kini berstatus **Diblokir** — tidak Tersedia, tidak bisa
   dialokasikan/dijual/dipilih; kembali ke status sebelumnya saat dilepas.
10. **Horizon ATP** bisa diubah di Pusat Pengaturan (Stok & Satuan → "Horizon ATP (hari)", bawaan 14 — angka tidak berubah).
11. **Lokasi jualan POS** diingat lintas perangkat/sesi (server); pelanggan tetap per sesi tab.
12. **Pemilih roll** menampilkan "n roll ditawarkan · Tersedia X" dan peringatan cadangan makloon.
13. **Lokasi Rak**: antrean 100 roll per halaman dengan jumlah total; tidak lagi "(500)" diam-diam.
14. **HP Masuk**: hitungan memisah "perlu dikerjakan" vs "menunggu/ditolak QC".
15. Draf pembelian antar-PT **tidak** lagi dihitung ATP (tetap tampil di papan Pending SO sebagai perkiraan, E9.2).
16. Gudang **non-aktif** tidak lagi ikut angka stok K-04 (dulu "terdaftar" termasuk non-aktif) — data acuan: 0 roll di
    gudang non-aktif, angka tidak berubah.

Istilah (K-13): layar lama tidak diganti istilahnya kecuali salah/menyesatkan — yang diganti: "Stok fisik" → "Tersedia"
(Control Tower, angkanya memang Tersedia), "Stok entitas aktif" → "Tersedia (PT aktif)" (katalog), "Tersedia (ATP > 0)"
→ "Tersedia > 0" (saringan POS), "Stok Habis" → "Habis di cakupan saya"/"Habis di grup". Kosakata `SalesStockSummary`
(Fisik/Dikunci/Bebas) dipertahankan (K-B4-06).

---

## 5. Keputusan implementer (di luar keputusan koordinator)

1. **Keputusan #1 (cadangan makloon dikunci per roll) — langkah minimum dipakai.** Mengunci per roll menyentuh
   reservasi potong (`length_reservations`, wilayah FIX-3), alur issue makloon (`issue_rolls_to_subcon`), mode
   persetujuan `makloon_reserve_mode=approve`, dan pelepasan saat PR/MKO batal/selesai. Dalam paket ini cadangan
   **dikurangi konsisten di satu layanan** (`allocate_makloon`, satu aturan alokasi gudang) dan pemilih roll menampilkan
   Tersedia + cadangan; reservasi pesanan tetap dijaga `makloon_guard`. **Langkah lanjut:** `material_reservation_service`
   menulis `length_reservations[type=makloon]` pada roll FIFO saat cadangan lahir, `consume_for_issue` melepasnya per roll
   yang di-issue, `release` melepas semua; `allocate_makloon` lalu dihapus (saldo sudah benar).
2. **Data uji tidak ditebak dari nama.** Koordinator: GLOBAL "bukan data uji". Penanda nama ("TEST_WH …") tidak dipakai
   karena puluhan uji otomatis membuat gudang bernama TEST lalu memeriksa angkanya; yang dikecualikan: gudang non-aktif,
   bertanda `is_test: true`, dan saldo yatim. Gudang uji tertinggal di data acuan tidak berisi roll/saldo → angka sama.
3. **ATP tidak memasukkan transfer/makloon/retur.** Ketiganya tampil di "Akan datang" (B3a STK-12) bertanda "info";
   ATP tetap rumus `atp_policy` (PO + roll menuju gudang + antar-PT dikonfirmasi) agar pratinjau alokasi SO
   (`from_incoming`) tidak berubah diam-diam. Perluasan ATP = keputusan pemilik terpisah.
4. **Draf antar-PT** (`draft`) tidak dihitung ATP di mana pun, tetapi tetap muncul di papan Pending SO (perkiraan E9.2)
   bertanda `tentative`.
5. **Roll tersedia tidak dikurangi cadangan makloon** (cadangan belum per roll) — tertulis di definisi.
6. **Label grup seragam "Total grup (semua PT)"** untuk semua peran (K-B1-12 untuk gudang; dipakai juga sales agar satu
   istilah).
7. **Status board `total_hold`** kini tidak memuat dialokasikan & cadangan makloon (STK-9); kolom terpisah dikirim.
8. **Roll ber-peg pelanggan (`earmarked_for`) yang ditahan inspeksi** tidak diubah statusnya (aturan `hold_roll` lama);
   bendera tahan tetap dibaca predikat stok (pemilih roll, uji silang).
9. **Saran reorder** tetap memakai status PO miliknya (termasuk `waiting_approval`, mencegah PO ganda) tetapi sisa PO kini
   dalam satuan dasar.
10. **`/stock/figures` `?site_id=`** hanya mengubah cakupan TAMPILAN angka LOKAL (bukan pagar akses).

---

## 6. Hasil uji & perbandingan regresi

### 6.1 Uji silang angka (endpoint vs hitungan langsung dari `inventory_rolls`)
Skrip: `scripts/audit/fix2_stock_crosscheck.py` (baca-saja; GET + login), sampel = 31 produk sampel B3a + semua varian
templatnya, 7 akun demo, salinan data acuan `kn_test_trial_2026-11-08` dipulihkan sebelum tiap putaran.

| Putaran | Kode | Perbandingan | Berselisih |
|---|---|---:|---:|
| B3a (audit, 9 Nov) | `5f1e36e` | 895 | 48 |
| **Sebelum** (FIX-2 dasar `main`) | `main` | **912** | **64** |
| Sesudah — putaran 1 (sebelum tambahan B1b) | worktree | 1.672 | 1 ¹ |
| **Sesudah — putaran akhir** (kode final, DB dipulihkan ulang) | worktree `HEAD` | **1.672** | **0** |

¹ satu-satunya selisih = acuan skrip untuk `rfid/summary` memakai daftar status yang kurang lengkap (endpoint 23.274,
acuan 23.214 karena skrip belum memasukkan `in_transit_*`/`receiving` yang memang kandidat tag); acuan skrip
dibetulkan. Rincian "sebelum" per kelompok: product-templates 29/30, pos/site-stock 6/186, stock-breakdown matriks 6/31,
sales/stock-summary fisik 5/63, bebas 2/63, /products entity_available 2/63, stock/atp 4/94, buckets 2/31,
breakdown saldo 2/31, rolls/available 2/31, internal-requests 2/31, KPI dasbor Semua PT 1/3, rfid 1/1.
Sesudah: endpoint lama 0 selisih di semua kelompok + kelompok baru (`/products stock_figures.global` 93, dua angka
LOKAL/GLOBAL/roll per 7 akun, rincian Σ per PT & per site) 0 selisih.

Cakupan LOKAL per akun (putaran sesudah): admin/manager/wh.admin/sales = Sukacita (tanpa site); sales.kanda = Kanda
Fabric (tanpa site, belum memilih lokasi jualan); warehouse.soreang = Soreang · Kanda Fabric; warehouse.rancamalang =
Rancamalang · Cipta Sandang.

### 6.2 Pytest, Jest, ESLint, regresi
_(lihat §6.4 catatan pelaksanaan)_

### 6.3 Guardrail (`PYTHONUTF8=1 python scripts/guardrails/verify_*.py`, host, tanpa Mongo; `verify_state_machine` tidak dijalankan)
Kode keluar 40 guardrail **identik** sebelum (`main`) vs sesudah; jumlah pelanggaran guardrail yang merah sejak dasar
tidak naik (contoh: `verify_qty_dual` 28 pelanggaran dari 1.717 → 28 dari 1.721 cek; `verify_entity_label` 28 → 28;
`verify_to_list_bound` hanya pergeseran baris `roll_service.py:387,401 → 386,400` yang sudah merah). Hijau sebelum &
sesudah: detail_modal (28 → 29 cek), escape_layers, role_label, uom_vocab, codebase_map, auth_coverage-baseline sama.

### 6.4 Catatan pelaksanaan
_(diisi di bawah)_

---

## 7. Berkas berisiko bentrok dengan paket lain

* `backend/services/roll_service.py` (FIX-3: potong/ambil) — hanya `_on_order_qty` & `list_available_rolls` (ringkas).
* `backend/services/inspection_service.py`, `roll_hold_service.py` — tiga panggilan `sync_inspection_hold` (+ fungsi baru).
* `backend/services/location_service.py`, `routers/inventory.py` (`/inventory/putaway/queue`) — paginasi; **cakupan PT
  antrean tidak diubah** (FIX-1 / keputusan B3a #6).
* `backend/services/location_scope.py` **tidak** disentuh; titik kait `work_site_ids(user)` dibaca bila FIX-1 menambahkannya.
* `frontend/src/features/mobile/MobileWarehouseApp.jsx` (UI-54, dua baris), `LocationPutawayView.jsx`, `PosStartGate.jsx`.
* `CODEBASE_MAP.md` belum dibangkitkan ulang (dihasilkan otomatis; dibiarkan untuk koordinator saat gabung).

## 8. Sisa / langkah lanjut

1. Keputusan #1 penuh: cadangan makloon dikunci per roll (rancangan di §5.1).
2. UI-46 sisanya: antrean Lokasi Rak per gedung semua PT (cakupan akses → FIX-1 / keputusan #6), `_queue_block` batch,
   render virtual; KPI `/warehouses/{id}/locations` masih per gedung semua PT (kini diberi label).
3. Layar yang belum memakai `StockFigures`: Operasi Gudang › Stok (`InventorySummaryCards` tanpa jumlah roll),
   Stok Multi-Bucket (FE menjumlah ulang saat disaring; KPI "Total Tersedia" = "ATP"), Lot & Silsilah, HP gudang
   (roll-level), Produksi `ProductionWO`.
4. STK-3 sisa: PO tanpa `entity_id` masih masuk `on_order_qty` semua PT di `rebuild_balance`.
5. SSOT-8 (reservasi potong pada roll ditahan / SO hantu) — wilayah alur (FIX-3).
6. SCP-5 (`/pos/site-stock?entity_id=` tidak divalidasi) — pagar akses (FIX-1).
7. Guardrail ratchet "hanya `stock_figures` menghitung Tersedia" (cegah rumus pembaca baru) — usulan.

## 9. Ringkasan untuk koordinator
_(lihat akhir berkas)_

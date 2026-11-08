# B3a — Audit SSOT, skema database & duplikasi data/logika, dan angka stok (WMS-RFID)

**Tanggal:** 9 Nov 2026 (WIB) · **Paket:** B3a · **Sifat:** AUDIT — tidak ada kode aplikasi yang diubah.
**Baseline kode:** `main` **5f1e36e** (worktree di-*fast-forward* atas arahan koordinator; gelombang 2 / D2 ikut diperiksa;
`kn-uji-backend` menjalankan kode yang sama).
**Data:** DB `kn_test_trial` di `kn-dev-mongo-1` — hanya `find/aggregate/count/listCollections/getIndexes/explain`;
API `http://127.0.0.1:8063` — hanya GET (+ login) dengan 7 akun demo.
**Lampiran:** [Sensus koleksi](B3a-LAMPIRAN-SENSUS-KOLEKSI.md) · [Profil field](B3a-LAMPIRAN-PROFIL-FIELD.md) ·
[Semua penulis per fakta](B3a-LAMPIRAN-PENULIS.md) · [Inventaris & uji silang angka](B3a-LAMPIRAN-UJI-ANGKA.md)
**Skrip (bisa diulang):** `scripts/audit/b3a_*.py|js|sh` — lihat §12.

> **Catatan pelaksanaan.** Docker Desktop host macet ±05:16–06:17 WIB (dimulai ulang di luar sesi ini). Data yang diambil
> sebelum jeda (sensus, profil, saldo-vs-roll) dan sesudah jeda (anomali roll/dokumen, 523 GET API, indeks) sama-sama
> dipakai; tidak ada query yang gagal-separuh yang dijadikan temuan. Satu agregasi audit saya sendiri
> (`$lookup` mutasi→roll) berjalan > 9 menit karena roll tidak berindeks `id` (lihat SCH-9) — operasi itu saya hentikan
> (`killOp` atas opid query saya sendiri, bukan penulisan data) dan diganti pengecekan di memori.
> Status tiap temuan: **terverifikasi-data** (contoh nyata di DB/API), **terverifikasi-kode** (alur dibuktikan dari kode,
> belum ada contoh di data uji), **kandidat**.

---

## 0. Ringkasan

* **Diperiksa:** 184 koleksi DB × 224 koleksi yang disebut kode app × registry; profil field 40 koleksi
  (`inventory_rolls` 46.700 dok / 389 path); 14.620 panggilan Mongo dipindai AST; 380/380 segmen saldo diuji terhadap
  46.700 roll; 46.700 roll + dokumen WMS diperiksa anomalinya; **31 produk & 49 roll sampel × 19 endpoint = 895
  perbandingan angka** + uji cakupan 15 endpoint × 7 akun; ±30 rumus BE + ±60 tampilan FE diinventarisasi.
* **Yang sehat (terverifikasi-data):** proyeksi `inventory_balances` identik dengan hitung ulang dari roll di
  **380/380 segmen**; 0 nomor roll kembar, 0 EPC kembar, 0 `id` kembar, 0 roll satuan ≠ satuan dasar, 0
  `length_reserved` ≠ Σ reservasi. Papan Status Stok, Stok Rendah, `/dashboard` per PT, `/products` global dan pohon stok
  lokasi = K-04 (0 selisih).
* **Masalahnya "satu fakta, banyak rumus":** dari 895 perbandingan, **48 berselisih** — semuanya dijelaskan rumus pembaca:
  cadangan makloon tidak dikurangi di 9 endpoint (+75 kg & +300 kg pada 2 produk), panjang dipesan-potong ikut
  "tersedia" di katalog POS "Di {site}" (+2 … +25 yard), "Fisik" Sales tanpa `committed` (−500 yard pada BTK-MEGA-001),
  dan katalog Produk & Varian **selalu 0** (17/17 varian). "Tersedia" dihitung di ≥ 12 tempat dengan ≥ 8 definisi;
  "barang datang" di 6 tempat dengan 4 rumus.
* **Temuan: 45** — **P0: 7 · P1: 13 · P2: 17 · P3: 8** (§11). P0: STK-1, STK-2, STK-6, STK-13, STK-14, SSOT-4, SCP-1.
  Yang paling mendesak: **SCP-1** — `/rfid/lookup` (+4 endpoint roll RFID) membuka roll PT & lokasi mana pun beserta HPP
  karena pagar dibangun dari dict dengan nama field salah (terbukti: akun gudang Soreang/Kanda membaca roll KSC Jakarta
  & HPP roll Cipta Sandang 31.680).
* **10 pola kesalahan** §9 · **usulan "dua angka" (lokal + global + rincian)** §10 · **8 butir keputusan** §11.

---

## 1. Sensus koleksi

Tabel lengkap: [B3a-LAMPIRAN-SENSUS-KOLEKSI.md](B3a-LAMPIRAN-SENSUS-KOLEKSI.md) (heuristik longgar → angka "tak
terdaftar" = batas bawah).

| Kelas | Jumlah | Catatan |
|---|---:|---|
| Koleksi di DB `kn_test_trial` | 184 | 64 kosong |
| Disebut/dipakai kode app | 224 | termasuk akses `collection('…')` (rfid_v2) & konstanta |
| **Dipakai app, ada di DB, TIDAK di `ENTITY_REGISTRY.md`** | **86** | 41 di antaranya domain WMS-RFID |
| Dipakai kode, belum pernah ada di DB uji | 44 | `roll_scans`, `rfid_cycle_counts`, `location_corrections`, `supplier_roll_claims`, … |
| Dipakai app, 0 dokumen | 50 | 16 `rfid_v2_*` (gate V2 belum dipakai di data uji), `cycle_count_sessions` (0 opname!), `initial_registration_lines`, `repair_orders`, `bin_locks` |
| Ditulis app, tak dibaca app (kandidat) | 13 | `turn_marks` 1.115 dok; kunci CAS (`*_locks`) wajar; `fact_stock_daily` palsu (dibaca dinamis `analytics_engine.py:348`) |
| Nama mirip | 5 pasang | `rfid_passages`~`rfid_v2_passages`, `rfid_v2_event_ids`~`rfid_v2_events`, `material_reservation_locks`~`material_reservations`, `tax_invoices`~`tax_invoices_in` |
| Koleksi ber-dokumen **tanpa indeks `id`** | **131 / 132** | hanya `product_templates` (SCH-9) |

**WMS-RFID yang tak terdaftar:** `putaway_orders`, `warehouse_sites`, `goods_receipts`*, `logistics_deliveries`,
`material_reservations`(+`_locks`), `mdq_cuts`, `repair_orders`, `bin_locks`, `rfid_verify_sessions`, `rfid_print_jobs`,
`roll_label_prints`, `rfid_passages`, `rfid_observations`, `rfid_incidents`, `rfid_cycle_counts`, `roll_scans`,
`roll_cost_history`, `initial_registration_lines`, `registration_area_status`, `turn_marks`, `fact_stock_daily`, dan
**ke-17 `rfid_v2_*`** termasuk D2 (`rfid_v2_gate_txn`, `rfid_v2_reviews`, `rfid_v2_claim_corrections`).
(*disebut sambil lalu satu kali.) Riwayat git dipadatkan di `b01c779` (18 Okt 2026) sehingga tanggal lahir koleksi lama
tak bisa ditelusuri; yang bisa: `site_stock_service.py` lahir `663745a` (24 Okt), `stock_availability.py` `c9b3f76` (26 Okt).

---

## 2. Peta SSOT — fakta → pemilik → penulis → salinan

"Penulis" = panggilan tulis langsung di kode app (AST) — daftar berkas:baris di [lampiran penulis](B3a-LAMPIRAN-PENULIS.md).

| Fakta | SSOT (koleksi.field) | Pemilik semestinya | Penulis nyata | Salinan & mekanisme sinkron | Nilai |
|---|---|---|---|---|---|
| Panjang/sisa roll | `inventory_rolls.length_remaining` | `roll_service` | **35 / 17 berkas** (termasuk router `inbound_scan_label.py:204`, `inventory.py:495`) | saldo `*_qty` (`rebuild_balance`, dipanggil manual di 69 titik; INV-ROLL-1 di `verify_data_integrity`); lot `qty_*` (`lot_service.recompute_many` dari `rebuild_balance`); `roll.length` (13 roll retur, tak disinkron kode — saat ini sama) | **dijaga (0 selisih)** |
| Panjang dipesan (potong) | `length_reservations[]` | `roll_service._reserve_length` | 2 berkas | `length_reserved` (pipeline sama `roll_service.py:587-592`; dihitung ulang `_recompute_reserved_stage` `:600-601`) | dijaga (0 selisih) — tapi lihat SSOT-8 |
| Status roll | `inventory_rolls.status` | — (tak ada mesin status roll) | **63 / 18 berkas + 2 router** | bucket saldo; `journey.stage` (136 roll); `qc_status` (13); `location_type` (tak pernah diubah) | **liar** (SSOT-1) |
| Gudang roll | `inventory_rolls.warehouse_id` | `roll_service`, `transfer_receipt_service`, `putaway_order_service` | 12 / 11 berkas | `last_scan.warehouse_id` (GET `/rfid/lookup`), `rfid_tags.warehouse_id`+`last_seen_*`, `inventory_lots.warehouse_id` (snapshot; 3 basi), `wms_tasks.warehouse_name/_city` (snapshot, dibaca ulang dari master `routers/wms.py:46-52`) | campur (SSOT-6) |
| Bin roll | `inventory_rolls.bin_id` | `location_service.place_roll` | 10 / 8 berkas | `bin_code` (13; 1 beda), `bin_sim` (37.210 data simulasi) | — · 9.394 roll fisik tanpa bin |
| PT pemilik | `inventory_rolls.owner_entity_id` | `roll_service.execute_ownership_transfer` | 5 pembuat + 1 pemindah | `inventory_lots.owner_entity_id` **dan** `.entity_id`, `rfid_tags.owner_entity_id`, `material_reservations`; dokumen pakai `entity_id` | nama ganda (SCH-1); 3 lot beda pemilik (SSOT-9) |
| Alokasi ke SO | `reserved_ref` + `length_reservations[].ref` | `roll_service` | 26 / 10 berkas (+ router `sales_orders_extra.py:628,742`) | `sales_orders.allocations[].rolls[]` | dijaga sebagian — 3 reservasi yatim (SSOT-8) |
| Transit transfer | `status=in_transit_transfer` + `transfer_ref`/`reserved_ref` | `roll_service`, `transfer_receipt_service` | 2 berkas | `warehouse_transfers.status` (10/10 konsisten), saldo `in_transit_transfer_qty` di gudang **ASAL** | dijaga |
| Karantina / tahan | `status ∈ {quarantine, blocked, hold}` | `qc_service`, `roll_hold_service` | lihat status | `hold.held` (QC-06) · `inspection.hold.held` (MD Quality — status TIDAK berubah) | **tiga kebenaran** (SSOT-3) |
| Grade | `inventory_rolls.grade` | `grade_service.set_roll_grade` (registry PS-09) | **14 / 13 berkas**; 7 update di luar `grade_service` | `qc_grade` (40), `inspection.grade` (25), `grade_history[]` (15) | liar (SSOT-2) |
| Tag RFID roll | `rfid_tags.roll_id` ↔ `inventory_rolls.rfid_tag_id` | `rfid_service` | tag 10 berkas; roll 11 / 8 berkas | `journey.verified_tag_id`, `tracking_mode` | dijaga (`rfid_tag_unique`); 3 roll berisi label di `rfid_tag_id` |
| Lot | `inventory_lots` | `lot_service` | — | `roll.lot`, `dye_lot`, `batch`, `supplier_lot`, `legacy_lot_codes` | dijaga (INV-LOT); 100 `dye_lot`≠`lot` (SSOT-9) |
| Cadangan makloon | `material_reservations.qty` (produk×PT, **tanpa gudang & roll**) | `material_reservation_service` | 1 berkas | dikurangkan 4 cara, diabaikan 9 endpoint | **liar** (SSOT-4) |
| Saldo per segmen | `inventory_balances` | `roll_service.rebuild_balance` | **1** | proyeksi | **dijaga — 0 selisih** |
| Mutasi | `inventory_movements` (append-only) | — (tak ada pintu tunggal) | **64 / 23 berkas** | — | dua skema, tanda campur (SCH-6) |
| Status tugas WMS | `wms_tasks.status` | — | 23 / 13 berkas | `qc_status` tugas | — |
| Status transfer | `warehouse_transfers.status` | `routers/transfers.py`, `transfer_receipt_service` | 8 / 5 | `interco_transactions.warehouse_transfer_status` | — |
| Status PA / SJ / opname | `putaway_orders`/`shipments`/`cycle_count_sessions.status` | layanan masing-masing | 3/2 · 3/3 · 10/2 | `logistics_deliveries` (SJ) | dijaga |
| Bukti lewat gate | `rfid_v2_passages` | `rfid_v2_*` | 5 berkas | `doc.gate_exits[]/gate_arrivals[]` (D2), `roll.gate_exit` (V1), `rfid_tags.last_seen_*`, `rfid_passages`/`rfid_reads` (V1) | dua jalur hidup (SSOT-6) |

**D2 (gelombang 2) — positif:** `gate_txn_service` tidak menulis roll sendiri; pemindahan stok didelegasikan ke pemilik
(`putaway_arrival_service.confirm_arrival_trip` `gate_txn_service.py:229`, `transfer_receipt_service.receive` `:248`),
idempoten per (lintasan, dokumen) lewat `rfid_v2_gate_txn` (`:296-319`).

---

## 3. Temuan SSOT

### SSOT-1 — Status roll tanpa pemilik: 63 penulis di 18 berkas, tanpa tabel transisi
* **Area:** `inventory_rolls.status` · **Klasifikasi:** inkonsistensi / butuh keputusan · **Keparahan:** P1 · **terverifikasi-kode+data**
* **Bukti:** `b3a_db_writers.py --coll inventory_rolls --field status --kind app` → 63 panggilan di 18 berkas layanan +
  `routers/inventory.py:495` (stok awal manual) + `routers/sales_orders_extra.py:628,742` (melepas reservasi dari router,
  menduplikasi `roll_service.release_*`). Tidak ada tabel transisi (`ROLL_TRANSITIONS`/`ALLOWED_ROLL` = 0);
  `verify_state_machine.py` hanya SM-1 (batal SO). Data: 12 status hidup — available 46.436 · in_transit_sales 81 ·
  consumed 44 · subcon 32 · quarantine 29 · reserved 20 · delivered 13 · committed 12 · in_transit_transfer 10 · blocked 8
  · damaged 8 · returned_supplier 7. **96 roll** berstatus yang tak ada di enum registry (`consumed`, `delivered`, `subcon`,
  `returned_supplier`; juga `hold`/`wip` di kode), sedangkan `sold/returned/scrapped` di registry tak pernah ditulis.
  Status alokasi `allocated` (milik `sales_orders.allocations[].status`) bocor ke daftar status roll di
  `services/loading_check_service.py:17` dan `services/rfid_service.py:22`.
* **Dampak:** pembaca menebak status mana yang "fisik" → STK-6 (−500 yard), DUP-3.
* **Rekomendasi:** `roll_state.transition(roll_id, from, to, reason, ref)` ber-CAS + `rebuild_balance`; guardrail
  ratchet "hanya `roll_state` boleh `$set status` di inventory_rolls" (63 → 0); enum registry dibangkitkan dari kode.

### SSOT-2 — Grade diubah di 7 tempat di luar `grade_service` (melanggar PS-09)
* **Area:** `inventory_rolls.grade` · **Klasifikasi:** inkonsistensi · **Keparahan:** P2 · **terverifikasi-kode** (dampak data kecil)
* **Bukti:** registry: "diubah HANYA lewat services/grade_service.py (PS-09)". Update di luar: `purchase_return_service.py:600-606`
  (`grade` + `regraded_from`, tanpa riwayat), `qc_service.py:409` (riwayat ditulis manual), `repair_order_service.py:305`,
  `return_cutloss_split_service.py:160`, `return_identity_service.py:124`, `routers/inbound_scan_label.py:204`,
  `bootstrap.py:596`. Data: grade ≠ A tanpa `grade_history` 1.785 roll — 1.784 data impor/seed (wajar), **1** di luar
  impor (roll retur `roll_2ac2772f7df1`, grade B). Enum registry A|A1|A2|B|BS tertinggal dari master `md_grades`
  (memuat juga `B1`, `C` non-aktif).
* **Rekomendasi:** 7 titik → `grade_service.set_roll_grade(source=…)`; guardrail `$set grade`.

### SSOT-3 — "Ditahan" punya tiga kebenaran; tahan MD Quality tak dihitung saldo & tetap bisa dijual
* **Area:** `status`, `hold.held`, `inspection.hold.held` · **Klasifikasi:** bug laten · **Keparahan:** P1 ·
  **terverifikasi-kode** (data: 0 roll `inspection.hold.held=true` saat ini dari 72 ber-`inspection.hold`)
* **Bukti:** `qc_inspection_service.py:145,168` (`record_quality`, dipanggil SPK MD Quality `inspection_service.py:1065`
  untuk baris roll apa pun termasuk *random check* stok) menulis `inspection.hold.held=True` tanpa ubah status & tanpa
  `rebuild_balance`. Menghormati tahan: `location_stock_tree.py:30-41`, `putaway_order_service.py:246,368`,
  `production_service.py:176`. Mengabaikan: `rebuild_balance` (`roll_service.py:261-350`), alokasi SO
  `roll_service.py:902-907`, pemilih roll `roll_service.py:2215`, `site_stock_service.py:28`, `sales_p04_service.py:348`,
  `fulfillment_decision_service.py:61`. Tahan QC-06 (`roll_hold_service.py:34`) justru mengubah status → `blocked`.
* **Dampak:** roll "DITAHAN sampai MD Quality memutuskan" tampil Tersedia & bisa dialokasikan/dikirim; layar Lokasi Rak
  bilang "ditahan".
* **Rekomendasi:** satu representasi (status `blocked` lewat `roll_hold_service`) atau satu predikat `is_sellable(roll)`
  dipakai saldo & semua kueri ketersediaan; invarian "inspection.hold.held ⇒ status ≠ available".

### SSOT-4 — Cadangan bahan makloon di luar roll → 9 endpoint menampilkannya sebagai "Tersedia" — P0
* **Area:** `material_reservations` (56 dok; aktif: 300 kg Kanda `MKO-00005`, 75 kg KSC `KSC/MKO-00082`) ·
  **Klasifikasi:** angka salah / duplikasi · **Keparahan:** P0 · **terverifikasi-data**
* **Bukti kode:** koleksi tanpa `warehouse_id`/`roll_ids`. Empat rumus pengurang: `stock_availability.py:37-55` (per PT,
  dibagi ke gudang terbesar dulu), `sales_stock_service.py:17-20,76-78` (global), `material_reservation_service.py:24-36`
  (PT aktif saja; `/dashboard` `routers/dashboard.py:136-137`), `pos_recommendation_service.py:57-65` (global).
  Tidak dikurangi: `/inventory/balances`, `/stock/buckets`, `/stock/atp`, `/products/{id}/stock-breakdown`,
  `/sales/stock-summary`, `/pos/site-stock`, `/inventory/rolls/available`, `/internal-requests-availability`,
  `/products` `entity_available_qty`, `so_verify`, `restock`, `fulfillment-plan`.
* **Bukti data (lampiran C.3):** DMO-GRY-KNT-001 (kg): K-04 grup 2.697,62 — **6 endpoint = 2.997,62 (+300)**; PT Kanda:
  `/dashboard` `entity_available_qty` = **177,63**, `/products` `entity_available_qty` = **477,63** untuk produk & PT
  yang sama; KNKNT0021-L-BEIX (kg): +75 di 9 endpoint. `/inventory/rolls/available` (pemilih roll SO/transfer) menawarkan
  roll senilai cadangan itu → bahan makloon bisa terjual.
* **Rekomendasi (butuh keputusan #1):** kunci cadangan makloon **di roll** (`length_reservations`/`reserved_ref` ber-
  `type=makloon_order`) sehingga `rebuild_balance` sudah benar di mana-mana; atau satu fungsi pengurang untuk semua endpoint.

### SSOT-5 — `ENTITY_REGISTRY.md` tidak lagi menggambarkan stok yang berjalan
* **Klasifikasi:** inkonsistensi dokumen · **Keparahan:** P2 · **terverifikasi-data**
* **Bukti:** §inventory_rolls masih "Status: DRAFT / PROPOSED (belum ada di DB/kode)" (46.700 dok); enum status kurang 6;
  field nyata tak terdaftar: `length_reserved`, `length_reservations`, `active_movement`, `hold`, `hold_history`, `journey`,
  `bucket_ref`, `transfer_ref`, `last_scan`, `gate_exit`, `qc_status`, `cut`, `pending_cut_ops`, `md_quality_*`,
  `inspected_4point*`; `inventory_balances` tanpa `hold_qty`/`wip_qty`/`subcon_qty`/`pending_demand_qty`/`roll_counts`/
  `projection_valid`/`rebuild_ticket`; §inventory_movements masih "[PROPOSED] owner_entity_id" (terisi 100%); 41 koleksi
  WMS-RFID tak terdaftar.
* **Rekomendasi:** bagian enum & daftar koleksi dibangkitkan dari kode; gate "koleksi baru wajib terdaftar" memakai
  `scripts/audit/b3a_collection_census.py`.

### SSOT-6 — "Di mana roll terakhir terlihat" di 7 tempat; jalur gate V1 & V2 sama-sama hidup
* **Klasifikasi:** duplikasi · **Keparahan:** P2 · **terverifikasi-kode**
* **Bukti:** `roll.warehouse_id/bin_id` · `roll.last_scan` ditulis **GET** `/rfid/lookup` (`routers/rfid.py:136-144`,
  `record=True` bawaan) · `roll.gate_exit` (`gate_evaluator.py:173`, V1) · `rfid_tags.last_seen_*` (V1) ·
  `doc.gate_exits[]/gate_arrivals[]` (D2, `gate_txn_service.py:187-192`) · `rfid_v2_passages` · `rfid_passages`/
  `rfid_reads`/`rfid_observations` (V1 `rfid_ingest_service.py`). K-RFID-07 menutup `/api/rfid/ingest` untuk reader V2,
  tetapi endpoint V1 tetap terpasang (`routers/rfid.py:589`).
* **Rekomendasi:** `rfid_v2_passages` satu-satunya log bukti; "terakhir terlihat" jadi proyeksi satu fungsi; jadwalkan
  pensiun V1.

### SSOT-7 — Stok awal punya dua pintu
* **Klasifikasi:** duplikasi / butuh keputusan · **Keparahan:** P2 · **terverifikasi-kode**
* **Bukti:** `POST /inventory/initial-stock` (`routers/inventory.py:443-500`, router menulis roll sendiri, status
  `available`, `created_by` = id pengguna) vs alur opname awal `initial_registration_*` (K-OPN-01..06 / K-RFID-11 —
  cara sah pemilik). Data: `initial_registration_lines` = 0, `cycle_count_sessions` = 0.
* **Rekomendasi:** sesudah opname awal dipakai, tutup/bungkus `POST /inventory/initial-stock` (butuh keputusan #8).

### SSOT-8 — Reservasi potong bisa tertinggal: di roll yang ditahan, dan menunjuk SO yang sudah tidak ada
* **Area:** `length_reservations`, `roll_hold_service` · **Klasifikasi:** bug · **Keparahan:** P1 · **terverifikasi-data**
* **Bukti:** RL-00005 (`roll_4bffd67fe1b2`, BTK-MEGA-001, 50 yd, KSC @Jakarta) di-*hold* QC 4-point gagal
  (`hold.reason` "SPK KSC/INS-00072: noda KO", 23 Okt) **sambil membawa 2 reservasi potong**: 5 yd `committed` untuk
  `KSC/SO-00159` (status `confirmed`) dan 1 yd untuk `so_c808e3a91d92` yang **tidak ada lagi**. Saldo memasukkan seluruh
  50 yd ke `blocked_qty` (`rebuild_balance` hanya memecah reservasi pada roll `available`), sehingga 5 yd milik SO
  terkonfirmasi tidak muncul sebagai "dialokasikan" di mana pun, dan SO itu menunggu potongan dari roll yang ditahan.
  `roll_hold_service.hold_roll` (`:27-31`) memeriksa `earmarked_for` tetapi **tidak** `length_reservations`. Reservasi ke
  SO yang tak ada: 3 (RL-00005 1 yd; RL-46582 1 yd ke `so_97da5e9786df` dan 1 yd ke `so_3a9b62992124`) — inilah
  `reserved_qty` 2,00 BTK-MEGA-001 di Jakarta: **2 yard terkunci untuk pesanan hantu** (SO uji yang dihapus tanpa
  melepas reservasi).
* **Rekomendasi:** `hold_roll` menolak/memindahkan reservasi potong; penghapusan SO (termasuk skrip pembersih uji) wajib
  melepas `length_reservations`; invarian "setiap `length_reservations.ref.id` menunjuk SO hidup".

### SSOT-9 — Pindah kepemilikan antar-PT tidak merapikan identitas lot
* **Area:** `lot`, `dye_lot`, `lot_id` · **Klasifikasi:** inkonsistensi · **Keparahan:** P2 · **terverifikasi-data**
* **Bukti:** 100 roll `dye_lot` ≠ `lot` (registry: `dye_lot` bawaan = `lot`), mis. `roll_74d7283673bd`
  lot `KSC/LOT-2610-0124` vs dye_lot `CST/LOT-2610-0123` (asal: inbound 64, subcon 19, transfer 9, initial 4, retur 2…);
  3 roll milik KSC berlot milik Cipta Sandang (`roll_8fc6567625bc`, `roll_118a6d5edb7c`, `roll_2ebab701b8d8`).
  `roll_service._rehome_lot_to_owner` (`:1765`) memindah `lot`/`lot_id` tetapi `dye_lot` tetap nomor lot lama.
* **Rekomendasi:** putuskan arti `dye_lot` (batch celup asli — boleh beda; atau salinan lot — wajib ikut); bila beda makna,
  jangan default-kan ke nomor lot.

---

## 4. Temuan skema (SCH)

### SCH-1 — PT disebut `owner_entity_id` di stok, `entity_id` di dokumen; beberapa koleksi membawa dua/tiga
* **Klasifikasi:** inkonsistensi · **Keparahan:** P1 (sudah melahirkan SCP-1) · **terverifikasi-kode+data**
* **Bukti:** `entity_scope.py:28-44`: `inventory_*`, `rfid_tags`, `rfid_reads`, `roll_label_prints`, `roll_scans`,
  `rfid_print_jobs`, `rfid_verify_sessions`, **`putaway_orders`** → `owner_entity_id`; selainnya `entity_id`
  (`wms_tasks`, `warehouse_transfers`, `goods_receipts`, `shipments`, `cycle_count_sessions`, `inspections`, `mdq_cuts`).
  Data: `inventory_lots` menyimpan keduanya (462/462; saat ini sama); `wms_tasks.owner_entity_id` hanya 2/252 tetapi
  dibaca lebih dulu di `qc_service.py:286`; `warehouse_transfers` tiga (`entity_id`, `source_entity_id`,
  `dest_entity_id`); fallback "salah satu" di 14 tempat, mis. `gate_txn_service.py:129`, `routers/inventory.py:64`,
  `cutting_service.py:126`, `inspection_service.py:914`, `mdq_cut_service.py:98`, `sample_sale_service.py:453`.
* **Rekomendasi:** `owner_entity_id` = pemilik BARANG, `entity_id` = PT PENERBIT dokumen; helper `owner_of(doc)`; larang
  dict sintetis untuk pagar.

### SCH-2 — Gudang asal/tujuan memakai tiga pasang nama
* **Klasifikasi:** inkonsistensi · **Keparahan:** P3 · **terverifikasi-kode+data**
* **Bukti:** `warehouse_transfers.source_/dest_warehouse_id` (17/17), `putaway_orders.from_/to_warehouse_id`
  (+ salinan `_name`), `makloon_orders.from_warehouse_id/target_warehouse_id` + `steps[].output_warehouse_id`.
  Sebutan kode: `from_` 162, `to_` 117, `source_` 70, `dest_` 58, `target_` 26. `location_scope.WAREHOUSE_FIELDS`
  (`location_scope.py:20-28`) mendaftar manual dan **melewatkan** `makloon_orders`, `cycle_count_sessions`,
  `logistics_deliveries`, `rfid_*` (SCP-2).

### SCH-3 — Empat nama untuk "qty satuan dasar"; saldo memakai nama yang salah
* **Klasifikasi:** bug · **Keparahan:** P1 · **terverifikasi-kode+data**
* **Bukti:** `quantity_base` (PO, `routers/purchase_orders.py:542`; data 40/41 item PO, **0** ber-`base_quantity`),
  `base_quantity` (SO items 576/576), `qty_base` (makloon/kontrak/analitik), `base_qty` (`uom_trail`). Sebutan kode:
  37/100/64/95. `roll_service.py:376` (`_on_order_qty` → saldo `on_order_qty/incoming_qty/atp_qty`) membaca
  `base_quantity` dari item **PO** → selalu jatuh ke qty dokumen. `fulfillment_service.py:124` & `sales_stock_service.py:55`
  membaca `quantity_base` (benar). Data uji saat ini: satu-satunya PO terbuka (`KANDA/PO-00001`) satuannya = satuan dasar
  (kg), jadi belum ada angka salah yang tampak.

### SCH-4 — Delapan pembuat roll, bentuk dokumen berbeda
* **Klasifikasi:** inkonsistensi · **Keparahan:** P2 · **terverifikasi-data**
* **Bukti:** `insert_one/insert_many` roll di `inbound_complete_service.py:426`, `receiving_roll_service.py:99`,
  `repair_order_service.py:296`, `return_identity_service.py:71,77`, `return_service.py:1132`,
  `roll_service.py:138,146,557,2158`, `routers/inventory.py:495`. Profil: **12 roll** tanpa `tracking_mode`,
  `location_type`, `ownership_type`, `is_remnant`, `batch`, `created_by` — cocok dengan pembuat roll retur
  (`return_service.py:1105-1130`) yang malah menambah `length`, `qc_status`, `origin_type`, `committed_to` dan nomor `RTN-`
  dari skema penomoran lain. `created_by` berisi nama di sebagian besar roll tetapi id pengguna di `routers/inventory.py:493`.
* **Rekomendasi:** satu `new_roll_doc(**)` (pola `insert_child_roll` sudah ada); perluas guardrail `verify_roll_identity`
  ke field wajib.

### SCH-5 — Field roll yang basi / tak dibaca
* **Klasifikasi:** inkonsistensi · **Keparahan:** P3 · **terverifikasi-data**
* **Bukti:** `location_type` = `warehouse_bin` pada **91 roll `in_transit_*`** (tak pernah diubah; 0 pembaca FE);
  `length` (13 roll retur; saat ini = sisa, tetapi tak disinkron kode); `weight_kg` vs `secondary_measures.kg` (65 roll,
  ditulis bersama `inbound_scan_label.py:198`, FE memilih salah satu `RollsTable.jsx:108-112`); `bin_code` (13; 1 kosong
  padahal bin `K01-L1-01`); saldo `projection_valid` & `unconvertible_roll_count` ditulis di 393 saldo, tak pernah dibaca;
  `bin_sim`/`sim_anomaly` (37.210 / 12) data simulasi tanpa kode.

### SCH-6 — `inventory_movements` bukan buku besar yang bisa diulang
* **Klasifikasi:** inkonsistensi · **Keparahan:** P2 · **terverifikasi-data**
* **Bukti:** 64 penulis/23 berkas tanpa pintu tunggal; 5 berkas retur menulis `type`+`direction` (16 mutasi) di samping
  `movement_type`. Tanda qty campur: `putaway` (+) 37.149 (penempatan bin, bukan perubahan stok), `reservation` (+) 524,
  `release_reservation` (+) 700, `subcon_consume`/`subcon_loss`/`qc_reject_damaged` **positif**; `outbound_ship`/
  `transfer_out` negatif. **203 mutasi `reservation` menyimpan beberapa id roll dipisah koma di `roll_id`**; total 71
  nilai `roll_id` / 243 mutasi tidak menunjuk roll (`ROLL-005`, `roll_TEST_*`, CSV). Σ mutasi per PT ≠ Σ roll (KSC
  1.453.827 vs 1.381.918 — campur satuan).
* **Rekomendasi:** `record_movement(roll, type, qty_bertanda, ref)` satu pintu; kosakata tipe + tanda tetap; satu
  mutasi per roll.

### SCH-7 — Id dan label tertukar
* **Klasifikasi:** inkonsistensi · **Keparahan:** P3 · **terverifikasi-data**
* **Bukti:** `wms_tasks.roll_id` berisi label pada **26** tugas (`wms_bef96c0e9725` → `DM-9A129A-020`); `routers/rfid.py:125`
  mencari tugas dengan `roll_id` = id **dan** = `roll_no` (kompensasi). `inventory_rolls.rfid_tag_id` berisi label pada
  **3** roll (RL-46505 `DM-9A129A-020`, RL-46560 `F14-303FF0-00`, RL-46542 `F14-48C98C-00`, tracking `barcode`).

### SCH-8 — `journey.stage` adalah sumbu status kedua tanpa aturan sinkron
* **Klasifikasi:** inkonsistensi · **Keparahan:** P3 · **terverifikasi-data**
* **Bukti:** 136 roll ber-`journey.stage`; 20 kombinasi dengan status, mis. `label_verified`+`in_transit_sales` 32,
  `received_transit`+`quarantine` 19, `stored`+`available` 23, `received_transit`+`available` 13, `tag_verified`+`consumed` 3;
  penulis 4 berkas (`backorder_service.py:170`, `putaway_order_service.py:586`, `rfid_print_service.py:432`,
  `roll_service.py:782`). Tidak ada definisi kapan `journey` "selesai".

### SCH-9 — Kunci aplikasi `id` tidak berindeks di 131/132 koleksi; indeks rujukan bersarang tak terpakai — performa
* **Klasifikasi:** performa · **Keparahan:** P1 · **terverifikasi-data**
* **Bukti:** `getIndexes`: hanya `product_templates` punya indeks `id` (`product_variant_service.py:47`);
  `backend/indexes.py:29-43` (INDEX_SPECS `inventory_rolls`) tidak memuat `id`. `explain`: `inventory_rolls.find({id})` →
  **COLLSCAN 46.700 dok, 18 ms**; `find({"reserved_ref.id"})` → COLLSCAN 23 ms, padahal yang diindeks `reserved_ref`
  utuh (`indexes.py:35`) dan 36 kueri memakai `reserved_ref.id`. ±90 `find_one({"id": …})` + ratusan `update_one({"id": …})`
  roll. Pada volume pemilik 6.000 roll/hari (KEPUTUSAN_GATE_RFID §10), satu lintasan gate ±180 roll yang diterima per roll
  (`transfer_receipt_service.receive`, find+update) ≈ 360 COLLSCAN ≈ 6–7 detik pada data hari ini, tumbuh linear.
  Juga tak ada keunikan `id` di tingkat DB (hari ini 0 kembar).
* **Rekomendasi:** indeks unik `id` untuk semua koleksi bisnis; indeks `reserved_ref.id`, `bucket_ref.id`,
  `length_reservations.id`, `active_movement.id`, `rfid_tags.roll_id`, `material_reservations(product_id,status)`.

---

## 5. Uji silang angka stok (STK)

Inventaris endpoint × layar × rumus dan semua baris selisih: [B3a-LAMPIRAN-UJI-ANGKA.md](B3a-LAMPIRAN-UJI-ANGKA.md).
Saldo vs roll: **380/380 segmen identik** (sisa uji: 1 saldo yatim `prod_TEST_F2_ee52f0 @ wh_TEST_F2_ee52f0_transit`
`hold_qty=50` di gudang tak terdaftar). **895 perbandingan endpoint, 48 berselisih**, semuanya karena rumus pembaca.

### STK-1 — Katalog "Produk & Varian" selalu 0 tersedia/0 dipesan — P0
* **Area:** GET `/product-templates/{id}/summary` (`routers/product_templates.py:32`) → FE `catalog/CatalogWorkspace.jsx:90`,
  `VariantCard.jsx:29`, `FamilyHero.jsx:18-25` · **Klasifikasi:** bug · **terverifikasi-data**
* **Bukti:** `product_variant_service.py:234-235` menjumlah `b.get('available')`/`b.get('reserved')`; saldo hanya punya
  `available_qty`/`reserved_qty` (393/393). API: **17/17 varian sampel = 0**, mis. KNKNT0021-L-KHKX 0 vs 5.048,95 kg,
  KNKNT0054-L-CUBX 0 vs 4.551,15 kg. `v['rolls']` (`:236-237`) menghitung roll segala status (termasuk terkirim/subcon).

### STK-2 — "Stok Perlu Reorder" Control Tower selalu "Stok fisik 0" — P0
* **Area:** FE `features/home/AdminHome.jsx:123` · **Klasifikasi:** bug · **terverifikasi-kode**
* **Bukti:** FE `it.on_hand ?? it.available_qty ?? 0`; server `purchase_requisition_service.py:521,545` mengirim `available`.
  Label "Stok fisik" juga salah makna (angkanya Tersedia K-04).

### STK-3 — `on_order/incoming/atp` di saldo dalam satuan dokumen PO — P1
* **Area:** `roll_service.py:358-380` · **Klasifikasi:** bug · **terverifikasi-kode** (data uji belum memicu, SCH-3)
* **Bukti:** SCH-3; plus PO tanpa `entity_id` masuk ke SEMUA PT (`if po.get("entity_id") and …`), `to_list(500)` diam-diam.

### STK-4 — `/stock/atp`, Pending SO & Ringkasan Stok Sales: "datang" = qty PO penuh tanpa dikurangi yang diterima — P1
* **Area:** `stock_bucket_service.py:449-471` (`_open_po_incoming`), `:480-521` (`_open_interco_incoming`) → `atp_detail`
  (`:583-626`), `pending_so_board`, `sales_p04_service.sales_stock_summary` · **Klasifikasi:** bug · **terverifikasi-kode+data**
* **Bukti:** `:463` `qty = quantity` (tanpa `− received_qty`, tanpa `quantity_base`); `:502` antar-PT `quantity`
  (bukan `quantity_base`, beda dengan `sales_stock_service.py:65`). Benar di `fulfillment_service.py:119-125`.
  `atp_detail` menjumlah `available` semua saldo dalam cakupan tetapi incoming/pending satu owner (`:590-604`).
  Data: PO uji belum diterima sebagian sehingga besaran sama hari ini; **tetapi** antar-PT `KANDA/IC-00035` (status
  **draft**, 5 yd) dihitung "datang" oleh `/stock/atp` & `/sales/stock-summary`, **tidak** oleh `/inventory/status-board`
  (0) — dua layar ATP berbeda untuk produk & PT yang sama.

### STK-5 — "Tersedia" ≥ 8 definisi — P1
* **Klasifikasi:** duplikasi logika / angka salah · **terverifikasi-kode+data**

| # | Rumus | Gudang | Makloon | Potong dipesan | Klaim PA / tahan inspeksi | Dipakai | Hasil uji |
|---|---|---|---|---|---|---|---|
| D1 | `stock_availability.available_index` (K-04) | terdaftar | per PT | dikurangi | PA ya / inspeksi tidak | stok rendah, papan status, reorder, `/reports/summary`, `/home/admin` | acuan |
| D2 | Σ saldo `available_qty` | semua (yatim TEST ikut) | **tidak** | dikurangi | PA ya / tidak | `/inventory/balances` (kartu "Tersedia" `InventoryStockView` — tooltip teks K-04 `:296`), `/stock/buckets`, `/stock/atp`, `so_verify_service.py:180-185`, `internal_request_service.availability`, `alert_ops_service.py:120-126`, `ProductionWO.jsx:101-104` | +75 / +300 |
| D3 | `sales_stock_service.apply_global` | semua | global | dikurangi | PA ya / tidak | `/products`, `/dashboard` produk, rekomendasi POS | = K-04 di sampel; `entity_available_qty` +300 |
| D4 | `site_stock_service.site_stock` | aktif di site | tidak | **tidak** | **tidak** | `/pos/site-stock` | +2 … +25 (STK-13) |
| D5 | `sales_p04_service.sales_stock_summary` | semua | tidak | dikurangi | tidak | `/sales/stock-summary` | +75 / +300; Fisik −500 (STK-6) |
| D6 | `location_stock_tree._bucket` | 1 gudang | tidak | dikurangi | **ya** | `/warehouses/{id}/stock-tree` | = saldo (6 gudang) |
| D7 | `fulfillment_decision_service._usable_stock_by_entity` | boleh-pakai PT | tidak | **tidak** | tidak | rencana pemenuhan Admin Sales | (kode) |
| D8 | matriks `routers/products.py:306-339` | semua, ≤ 5.000 roll | tidak | **tidak** | tidak | stock-breakdown (HP MD) | +2 … +300 |
| D9 | `product_variant_service.family_summary` | — | — | — | — | Produk & Varian | **0** (STK-1) |
| D10 | `roll_service.list_available_rolls` | semua | tidak | dikurangi | PA ya / tidak | pemilih roll | +75 / +300 |

### STK-6 — Ringkasan Stok Sales: "Fisik" & "Dikunci" tanpa `committed`/`wip` — P0
* **Area:** `sales_p04_service.py:363-373` → `components/SalesStockSummary.jsx:21-29` · **Klasifikasi:** bug ·
  **terverifikasi-data**
* **Bukti:** status fisik `("available","reserved","hold","quarantine","blocked","picked","packed","damaged")`.
  API: BTK-MEGA-001 KSC Fisik **162** vs 662 (committed 500); TNI-GRGD-001 **120** vs 270; KNWVN0015-L-TAUX
  −121,39; KNWVN0012-L-4XXX −12,5; KNKNT0021-L-BEIX −24,58 kg. `atp_definition` (`:391`) menyebut "PO/makloon" padahal
  makloon tidak dihitung.

### STK-7 — Matriks stock-breakdown: on_hand tanpa hold/wip, tanpa potong dipesan, batas 5.000/100 tanpa penanda — P2
* **Area:** `routers/products.py:278,293,331` · **terverifikasi-data** (selisih) / **kandidat** (pemotongan: produk
  terbesar saat ini 670 roll)
* **Bukti:** selisih matriks +2/+10/+20/+25 (potong dipesan) & +75/+300 (makloon); status on_hand tanpa `hold`/`wip`
  (beda `PHYSICAL_STATUS_TO_BUCKET`, `roll_service.py:203-214`); `to_list(100)`/`to_list(5000)` tanpa `X-Truncated`
  (bandingkan `routers/inventory.py:199-227`).

### STK-8 — KPI & produk dasbor mencampur cakupan — P1
* **Area:** `routers/dashboard.py:105-150` · **terverifikasi-data**
* **Bukti:** `?entity_id=all` (admin, PT aktif KSC): kg **384.787,60** vs K-04 384.487,60 (**+300**, cadangan Kanda tak
  dikurangi karena hanya PT AKTIF); per PT = K-04. `metrics.available_qty` masih satu angka campur satuan (2.847.079,92).
  `entity_available_qty` produk yang sama: `/dashboard` 177,63 vs `/products` 477,63 (SSOT-4).

### STK-9 — Papan Status Stok: "tertahan" memuat dialokasikan/diambil/dikemas — P3
* **Bukti:** `fulfillment_service.py:366` `total_hold = on_hand − available − reserved`, `reserved` = `reserved_qty` saja;
  teks rumus `:364` "karantina/QC/blokir/cadangan makloon". Data: BTK-MEGA-001 `committed_qty` 500 ikut "tertahan".

### STK-10 — Ambang "Stok rendah" tiga versi; filter POS menyebut ATP — P3
* **Bukti:** server `< 100` per produk×PT (`stock_availability.py:22`); FE `≤ 40` global (`pos/PosProductCard.jsx:23`,
  `components/ProductQuickView.jsx:74`, `sales/SalesPortal.jsx:81`); FE `< 100` per baris gudang
  (`wms/inventory/inventoryConstants.jsx:121`); `pos/FacetRail.jsx:25` "Tersedia (ATP > 0)" menyaring `available_qty`.

### STK-11 — GET yang menulis — P2
* **Bukti:** `routers/products.py:26`, `routers/dashboard.py:43`, `routers/sales_orders_extra.py:153,193` →
  `inventory_service.expire_old_reservations` (`:26-68`: lepas roll, `status=expired`, jurnal balik); GET `/rfid/lookup`
  menulis `roll_scans` + `last_scan` (`routers/rfid.py:136-144`). Pemindai: `scripts/audit/b3a_get_side_effects.py`.
  (Audit ini memastikan 0 SO memenuhi syarat sebelum memanggil endpoint tersebut.)
* **Rekomendasi:** kedaluwarsa reservasi → job penjadwal; `/rfid/lookup` bawaan `record=false`.

### STK-12 — Barang akan datang dari makloon, transit transfer (di tujuan) & retur tidak dihitung — P2
* **Klasifikasi:** fitur belum ada · **terverifikasi-kode+data**
* **Bukti:** `makloon_orders.steps[].expected_output_qty − actual_output_qty` + `target_warehouse_id` tersedia (56 MKO) tapi
  tak dibaca rumus stok mana pun. Transit `KANDA/TRF-00001` 250,65 kg (prod_e867010c6127) tidak masuk "datang" di endpoint
  mana pun dan saldo transitnya tercatat di gudang ASAL. Antar-PT dihitung "datang" di angka GRUP (`/products`
  `incoming_restock_qty` 5 yd untuk semua PT) padahal barang sudah ada di stok PT penjual (hitung ganda) dan dokumennya draft.

### STK-13 — Stok "Di {site}" (katalog POS/HP) menghitung panjang yang sudah dipesan untuk dipotong — P0
* **Area:** `/pos/site-stock` (`routers/pos.py:19-32`) → `site_stock_service.py:22-45` → FE `pos/PosProductCard.jsx:105-112`,
  `pos/mobile/MobileProductCard.jsx:58-71`, `sales/mobile/MobileCatalog.jsx:21` · **Klasifikasi:** bug · **terverifikasi-data**
* **Bukti:** `match {"status":"available"}` + `$sum length_remaining` (`:28-33`) — tanpa `length_reserved`, `active_movement`,
  `inspection.hold`, makloon. API @Jakarta (KSC): BTK-MEGA-001 **12** vs 10; KNWVN0015-L-TAUX 78.854,83 vs 78.844,83
  (+10); KNWVN0012-L-4XXX +20; KNWVN0005-L-FOGX +25 yard. Data: 53 roll ber-`length_reserved`, 34 reservasi aktif.
  Sales membaca angka ini sebagai "siap di depan saya".

### STK-14 — Ringkasan RFID: "roll belum ber-tag" mentok 5.000 — P0
* **Area:** GET `/rfid/summary` → `rfid_service.py:412` `untagged = len(await untagged_rolls(…, limit=5000))` ·
  **terverifikasi-data**
* **Bukti:** admin/manager/wh.admin (KSC) → `untagged_rolls: 5000`; data: KSC 23.371 roll, hanya 35 tag aktif di seluruh grup.
  Angka inilah yang dipakai merencanakan pendaftaran ulang/tagging stok lama (K-RFID-11).
* **Rekomendasi:** `count_documents` dengan kueri yang sama.

---

## 6. Duplikasi logika (DUP)

### DUP-1 — "Tersedia" dihitung ≥ 12 kali (STK-5) — P1
Dua salinan saringan "gudang terdaftar" berbeda definisi: `stock_availability.registered_warehouse_ids` (`:33-34`, semua
gudang di master, termasuk 5 `active=false` & 6 `TEST_WH`) vs `site_stock_service.site_warehouse_ids` (`:18-19`, hanya aktif).

### DUP-2 — "Barang datang / on order" di 6 tempat dengan 4 rumus — P1
| Tempat | Sisa = qty − diterima | Satuan dasar | Horizon | Antar-PT | in_transit_inbound |
|---|---|---|---|---|---|
| `roll_service._on_order_qty` (saldo) | ya | **field salah** (SCH-3) | 14 hr | tidak | ya |
| `fulfillment_service.build_supply_index` (papan status) | ya | `quantity_base` ✓ | ya | **tidak** | ya |
| `stock_bucket_service._open_po_incoming` (ATP detail, Pending SO, Sales summary) | **tidak** | **tidak** | ya | ya (`quantity`, termasuk draft) | **tidak** |
| `sales_stock_service.apply_global` (katalog grup) | ya | `quantity_base` ✓ | **tidak** | ya (hitung ganda di grup) | tidak |
| `purchase_requisition_service.reorder_suggestions` (`:432-440`) | ya | **tidak** | tidak | tidak | tidak |
| FE `StockBucketsView.jsx:85-89` / `InventoryStatusBoard.jsx:85-97` | jumlah ulang per satuan | — | — | — | — |
`atp_policy.ATP_HORIZON_DAYS = 14` diketik keras (`atp_policy.py:22`) sedangkan KN_15 S10: "configurable, default 30".

### DUP-3 — Peta "status → ember" ditulis 7 kali — P2
`roll_service.PHYSICAL_STATUS_TO_BUCKET` (`:203-214`) · `location_stock_tree._bucket` (`:30-41`) · `sales_p04_service`
(`:363-373`, tanpa committed/wip) · `routers/products.py:325-333` (tanpa hold/wip) · `rfid_service.PHYSICAL_STATUSES`
(`:22`, + `allocated`) · `gl_service.COGS_ROLL_STATUSES` (`:1234`) · `placement_rules.QC_STATUSES` (`:27`).

### DUP-4 — "Panjang bebas" diimplementasi ulang ≥ 6 kali; 3 lupa — P2
`roll_service.free_length` (`:575-577`) · pipeline `_reserve_length` (`:587-592`) · `location_stock_tree` (`:41`) ·
`sales_p04_service` (`:351`) · `rebuild_balance` (`:298-303`). Lupa: `site_stock_service.py:28` (STK-13),
`fulfillment_decision_service.py:61`, `routers/products.py:322-329`.

### DUP-5 — Cakupan PT/gudang lewat 5 mekanisme — P2
`resolve_list_scope` (PT + lokasi) · `resolve_scope_ids` (PT saja) · `warehouse_scope_service.usable_query` ·
`location_scope.narrow/doc_in_scope` · saringan `registered_only` (hanya K-04). Hasilnya tak seragam (SCP-2).

### DUP-6 — Dua koleksi untuk "pindah roll antar gudang dalam satu site" — P2 (butuh keputusan #5)
`putaway_orders` (2 dok; `from/to_warehouse_id`, `owner_entity_id`, PA00001/2 Jakarta → RCM-WOVEN) vs
`warehouse_transfers` `transfer_kind=intra_entity` (catatan data: "Putaway benang dari transit ke gudang wo[ven]…").
Keduanya punya status, penerimaan, tag dan kait gate D2 sendiri (`gate_txn_service.DOC_COLL`).

### DUP-7 — Enam penyimpanan "diharapkan vs terpindai" — P2
`rfid_verify_sessions` (`kind ∈ {print_verify, loading_check}`; 5 penulis), `cycle_count_sessions` (+`mode=registration`),
`rfid_cycle_counts` (ditulis `cycle_count_service`, tak pernah ada di DB), `rfid_v2_doc_sessions` (D2),
`initial_registration_lines`, `roll_scans` (tak pernah ada di DB).

### DUP-8 — Satuan: dikonversi di satu tempat, dikelompokkan mentah di tempat lain — P3
`rebuild_balance` mengonversi (`roll_service.py:273-292`); `site_stock`, `location_stock_tree`, `sales_stock_summary`,
`qc_service` mengelompokkan per `roll.unit`. Aman hari ini (0 roll satuan ≠ satuan dasar), aturan tidak satu.

---

## 7. Cakupan data per pengguna (SCP)

Setelan `wms.location_scope_enforced` = **true** (global). Hasil GET per akun: lampiran uji angka §C.4–C.5.

### SCP-1 — Pagar PT & lokasi di 5 endpoint roll RFID tidak berfungsi — P0
* **Area:** `routers/rfid.py:122` (GET `/rfid/lookup`), `:161` (`_roll_in_scope` → GET `/rfid/rolls/{id}/print-history`,
  **POST** `/rfid/rolls/{id}/label-prints`), `:203` (**POST** `/rfid/roll-scans`), `:227` (GET `/rfid/roll-scans/{id}`) ·
  **Klasifikasi:** bug · kebocoran · **terverifikasi-data**
* **Bukti kode:** `assert_entity_access({"entity_id": roll.get("owner_entity_id")}, "inventory_rolls", ctx)` — field
  cakupan rolls = `owner_entity_id` (`entity_scope.py:30`), dict hanya punya `entity_id` → cek PT dilewati
  (`:449-451`); cek lokasi mencari `warehouse_id` yang juga tak ada → lolos (`location_scope.py:77-82`). Respons
  `safe_doc(roll)` tanpa `strip_cost_fields` (beda dengan `routers/inventory.py:308,318`).
* **Bukti data (`record=false`):** warehouse.soreang (PT Kanda, site Soreang) → **200** untuk RL-00014 (KSC, Jakarta) dan
  RL-00016 (Cipta Sandang, RCM-KNITTING) dengan `unit_cost`/`base_unit_cost` **31.680**; `/inventory/rolls?q=RL-00014`
  untuk akun yang sama → **0 baris**. wh.admin (KSC+Kanda) membaca roll Cipta Sandang + HPP, padahal daftar roll yang sama
  menyembunyikan HPP-nya. warehouse.rancamalang membaca roll Jakarta & Soreang (di luar lokasi).
* **Rekomendasi:** kirim dokumen roll asli ke pagar; `strip_cost_fields`; guardrail larang dict literal di argumen
  pertama `assert_*_access` (3 pemakaian `{'warehouse_id': …}` di `rfid_v2.py:91`, `rfid_v2_review.py:24,84` sengaja
  hanya-lokasi — tandai eksplisit).

### SCP-2 — Lokasi kerja hanya menyaring sebagian daftar WMS — P1 · **terverifikasi-data**
* **Bekerja:** `/wms/tasks`, `/inventory/balances`, `/inventory/rolls`, `/stock/buckets|holds|wip|atp`, `/dashboard`,
  `/putaway-orders` (disaring sesudah `limit` — `routers/putaway_orders.py:72-74`), `/goods-receipts`
  (`goods_receipts.py:55`).
* **Tidak bekerja:** `/transfers` (`transfers.py:107`, `resolve_scope_ids`) — warehouse.soreang (lokasi SRG-01) melihat
  **15** transfer termasuk Jakarta & `GU-KANDA`; `/inventory/status-board` — akun yang sama melihat rincian gudang
  **RCM-RETUR** yang disembunyikan `/inventory/balances`-nya; `/cycle-count/sessions`, `/rfid/summary|tags|print-jobs|
  cycle-counts`, `/logistics/deliveries`, `/pos/site-stock`, SCP-1 (koleksi/penyaring tidak terdaftar di
  `WAREHOUSE_FIELDS`, `location_scope.py:20-28`).

### SCP-3 — Daftar tugas WMS dikunci ke PT aktif, padahal gudang Rancamalang dipakai bersama — P2 (keputusan #6)
* **Bukti data:** warehouse.rancamalang (boleh 3 PT, site Rancamalang, gudang RCM-* `shared`) melihat **5** tugas — hanya
  PT rumah Cipta Sandang — dan **0** PA/GRN/tag/print job, padahal PA00001/2 KSC tiba di RCM-WOVEN. Admin/manager/wh.admin
  (PT aktif KSC) melihat 243 tugas KSC termasuk **67 tugas di 6 gudang `TEST_WH`**. Kode: `resolve_list_scope` tanpa
  param → `entity_id = PT aktif` (`entity_scope.py:512-516`).

### SCP-4 — Rincian stok produk memberi dokumen roll utuh semua PT ke setiap `product.view` — P2 (keputusan #7)
* **Bukti:** `routers/products.py:278,293` tanpa cakupan PT (hanya lini) → `rolls` utuh (supplier, PO, faktur supplier,
  `reserved_ref` SO PT lain); redaksi hanya HPP.

### SCP-5 — `/pos/site-stock?entity_id=` tak divalidasi; `/dashboard` mengirim semua produk tanpa pagar lini/eksklusif — P3
* **Bukti:** `routers/pos.py:30`; `routers/dashboard.py:64` `products.find({})` (bandingkan `products.py:32`).

---

## 8. Data uji yang tertinggal di `kn_test_trial` (dicatat, TIDAK dihapus)

| Data | Jumlah | Bukti / dampak |
|---|---:|---|
| Gudang `TEST_WH B/C <hex>` (aktif, dedicated KSC) | 6 | `wh_c2019bb98b13`, `wh_b12325db6630`, `wh_f86c51615caf`, `wh_886c1b4a5888`, `wh_3ee1c580f859`, `wh_6e3adc09454c` — "terdaftar" untuk K-04 |
| Tugas WMS di gudang `TEST_WH` | **67** (54 `waiting_goods`, 13 batal) | tampil di `/wms/tasks` admin/manager/wh.admin |
| Site `TEST_SITE <hex>` | 3 | `site_44f820e02cc1`, `site_58c623d9bc40`, `site_6d8f4f3a3d97` |
| Badan usaha "PT Uji Provisioning F77512/F10873/F5880" (aktif) | 3 | `ent_9e9eedcd5450`, `ent_0d23afab6ff0`, `ent_8fdf6f2ea207` — ikut `allowed_entity_ids` admin (terverifikasi `/auth/login`) |
| Produk / SO / retur ber-TEST | 124 / 90 / 85 | `prod_TEST_*`, `so_TEST_*`, `sr_TEST_*` |
| Saldo yatim `prod_TEST_F2_*` @ `wh_TEST_F2_*_transit` | 2 | `hold_qty=50` |
| Reservasi potong ke SO yang sudah dihapus | 3 (3 yd) | SSOT-8 — ikut "Dipesan" |
| Mutasi `roll_TEST_*` | 32 | SCH-6 |
| Transfer bercatatan "test" | 14 | |
| Cadangan makloon `TEST_P05ACC` | 30 | `release_reason` |
| Tag menunjuk roll terhapus (`retired`) | 6 | `rtag_3bd08b08a9e2` … |
| Penanda simulasi bin `SIMULASI_BIN_KN` | 37.210 roll + 3.406 mutasi | `bin_sim`, `sim_batch`, `bin_sim_hilang_*` |
| Gudang lama non-aktif (`WH-BDG`, `WH-SBY`, `GU-*`) tetap "terdaftar" K-04 | 5 | DUP-1 |

---

## 9. Pola kesalahan berulang (10 teratas)

| # | Pola | Jumlah | Contoh |
|---|---|---:|---|
| 1 | **Pembaca menjumlah stok sendiri** alih-alih satu fungsi | ≥ 12 rumus BE + ≥ 8 jumlah FE; 48 selisih nyata | STK-5, `ProductionWO.jsx:101`, `variants.js:24-64`, `StockBucketsView.jsx:85` |
| 2 | **Satu fakta, banyak nama field** | 6 keluarga | `owner_entity_id`/`entity_id`; `quantity_base`/`base_quantity`/`qty_base`/`base_qty`; `source_/from_/target_warehouse_id`; `weight_kg`/`secondary_measures.kg`; `type`/`movement_type`; `roll_id` id/label/CSV |
| 3 | **Penulis di luar pemilik** | status 63, grade 7, panjang 35, mutasi 64 | SSOT-1/2, routers `sales_orders_extra.py:628`, `inventory.py:495` |
| 4 | **Keadaan disimpan sebagai bendera di samping status** | 3 tahan + `journey` + `qc_status` + `location_type` | SSOT-3, SCH-5, SCH-8 |
| 5 | **Kosakata status disalin ke banyak daftar** | 7 peta | DUP-3 → STK-6 (−500 yd) |
| 6 | **Batas `to_list(N)` / `limit` dipakai sebagai angka atau tanpa penanda** | ≥ 10 | STK-14 (5.000), `products.py:278,293`, `inventory_service.py:15`, `roll_service.py:363`, `stock_bucket_service.py:352,403,456,590`, `alert_ops_service.py:125` |
| 7 | **Pagar dari dict sintetis** | 4 titik | SCP-1 |
| 8 | **Rujukan tidak dilepas saat induk hilang** | 3 reservasi, 6 tag, 71 `roll_id` mutasi | SSOT-8, §8 |
| 9 | **Indeks kunci aplikasi tidak ada / tidak cocok kueri** | 131 koleksi; `reserved_ref` | SCH-9 |
| 10 | **Dokumen registry tertinggal dari kode** | 86 koleksi + 6 status + ±15 field | SSOT-5 |

---

## 10. Usulan definisi angka stok — "dua angka" + rincian

Prinsip: **satu fungsi server** `stock_numbers(product_id, viewer)` → semua layar (papan, katalog, POS, HP, master
produk, dasbor) hanya MENAMPILKAN; FE tidak menjumlah. Satuan = satuan dasar produk; tidak pernah dijumlah lintas satuan.

**Predikat roll (satu tempat, `roll_service`):**
* `is_physical(r)` = status ∈ {available, reserved, committed, picked, packed, hold, wip, quarantine, blocked, damaged}.
* `is_sellable(r)` = status = available ∧ ¬`active_movement` ∧ ¬`inspection.hold.held` ∧ ¬`hold.held` ∧ gudang aktif.
* `free_len(r)` = `length_remaining − length_reserved` bila `is_sellable`, selain itu 0.

**Angka utama:**
1. **LOKAL** = Σ `free_len` roll milik **PT aktif** di gudang aktif **site kerja pengguna**
   (gudang: `users.location_site_ids`; sales: site POS terpilih; admin/manager: site pilihan, bawaan semua)
   − cadangan makloon PT itu (sampai SSOT-4 diputuskan, alokasikan ke site dengan SATU aturan).
2. **GLOBAL** = Σ `free_len` semua roll semua PT di semua gudang aktif − Σ cadangan makloon (≥ 0 per PT).
   *(Hari ini GLOBAL = `/inventory/status-board.global_total.available`, satu-satunya angka yang 0 selisih di semua sampel.)*

**Rincian (saat diklik)** — PT × site × gudang:
| Kolom | Definisi | Sumber |
|---|---|---|
| Tersedia | Σ `free_len` (− makloon) | saldo `available_qty` (+ perbaikan SSOT-3/4) |
| Dipesan | `length_reserved` + reserved/committed/picked/packed | saldo `reserved+committed+picked+packed` |
| QC / ditahan | quarantine + blocked + hold + damaged + tahan inspeksi + klaim PA | saldo + predikat |
| Proses | wip + subcon (di mitra) | `wip_qty`, `subcon_qty` |
| Dalam perjalanan | `in_transit_transfer` diatribusikan ke gudang **TUJUAN** (`warehouse_transfers.dest_warehouse_id`), `in_transit_intercompany`, `in_transit_inbound` | roll + dokumen |
| Akan datang (ETA) | PO terbuka `(quantity − received_qty) × quantity_base/quantity` per `warehouse_id` · transfer dikirim-belum-diterima · antar-PT **dikonfirmasi** (`quantity_base`; tidak dihitung di angka GLOBAL karena sudah ada di stok PT penjual) · makloon `expected_output_qty − actual_output_qty` per `target_warehouse_id` · retur disetujui-belum-diterima | dokumen |
| ATP | Tersedia + Akan datang (ETA ≤ horizon) − backorder aktif (sekali per produk×PT) | `atp_policy` |

**Kemampuan data saat ini (butir 5):**
| Butuh | Ada? | Catatan |
|---|---|---|
| Per gudang / PT / status | **ya, cepat** | 393 saldo identik dengan roll; indeks `(product_id, warehouse_id, owner_entity_id)` |
| Per site | **ya** | 7/7 gudang aktif nyata punya `site_id` |
| Lokasi kerja pengguna | sebagian | gudang: `location_site_ids`; sales: site POS hanya di `sessionStorage` klien |
| Tahan inspeksi di saldo | **tidak** | SSOT-3 |
| Cadangan makloon per gudang | **tidak** | SSOT-4 |
| PO terbuka per gudang | ya | `quantity_base` (perbaiki SCH-3/STK-4) |
| Transfer menuju gudang | ya (dokumen) | saldo transit di gudang ASAL |
| Makloon berjalan | ya (data), tak dipakai | STK-12 |
| Kinerja | cukup bila dari saldo | dua angka = ≤ 400 saldo + dokumen terbuka; hindari membaca roll mentah per permintaan (D4/D5/D7/D8 memindai ribuan roll; tanpa indeks `id`, SCH-9) |

---

## 11. Daftar temuan per keparahan & butir keputusan

| Kep. | Temuan |
|---|---|
| **P0 (7)** | STK-1, STK-2, STK-6, STK-13, STK-14, SSOT-4, SCP-1 |
| **P1 (13)** | SSOT-1, SSOT-3, SSOT-8, SCH-1, SCH-3, SCH-9, STK-3, STK-4, STK-5, STK-8, DUP-1, DUP-2, SCP-2 |
| **P2 (17)** | SSOT-2, SSOT-5, SSOT-6, SSOT-7, SSOT-9, SCH-4, SCH-6, STK-7, STK-11, STK-12, DUP-3, DUP-4, DUP-5, DUP-6, DUP-7, SCP-3, SCP-4 |
| **P3 (8)** | SCH-2, SCH-5, SCH-7, SCH-8, STK-9, STK-10, DUP-8, SCP-5 |

**Terverifikasi-data:** SSOT-4, SSOT-5, SSOT-8, SSOT-9, SCH-3 (field), SCH-4..8, SCH-9, STK-1, STK-6, STK-7 (selisih),
STK-8, STK-12, STK-13, STK-14, SCP-1, SCP-2, SCP-3. **Terverifikasi-kode:** SSOT-1..3, SSOT-6, SSOT-7, SCH-1, SCH-2,
STK-2..5, STK-9..11, DUP-*, SCP-4, SCP-5. **Kandidat (besaran):** STK-3/STK-4 menunggu PO ber-UoM berbeda / diterima
sebagian; STK-7 pemotongan > 5.000 roll.

**Butir keputusan pemilik (rekomendasi dalam kurung):**
1. **Cadangan makloon** dikunci per roll seperti SO, atau tetap per produk? (*per roll* — menghapus 4 rumus & 9 selisih.)
2. **Tahan inspeksi MD Quality** = status atau bendera? (*status `blocked` lewat `roll_hold_service`.*)
3. **"Lokal" untuk sales** = site POS terpilih (disimpan server) atau site rumah? (*simpan pilihan POS; bawaan site rumah.*)
4. **Horizon ATP** 14 hari diketik keras atau setelan (KN_15: 30, configurable)? (*setelan Pusat Pengaturan, bawaan 14.*)
5. **Putaway vs transfer intra-PT** — satu konsep "pemindahan internal" dengan jenis? (*ya.*)
6. **Daftar tugas WMS** per lokasi kerja (semua PT) dengan PT sebagai rincian? (*ya — sesuai "lihat semua PT".*)
7. **Rincian roll lintas PT** di stock-breakdown/lookup: angka saja atau dokumen roll utuh? (*angka + identitas roll.*)
8. **Pintu stok awal** `POST /inventory/initial-stock` sesudah opname awal (*tutup / bungkus alur pendaftaran.*)

---

## 12. Cara mengulang

```bash
# statik (host, stdlib)
python scripts/audit/b3a_db_writers.py --json calls.json                       # semua panggilan Mongo (AST)
python scripts/audit/b3a_db_writers.py --coll inventory_rolls --field status --kind app
python scripts/audit/b3a_collection_census.py --calls calls.json --db db_collections.tsv --registry ENTITY_REGISTRY.md --root .
python scripts/audit/b3a_get_side_effects.py
python scripts/audit/b3a_field_usage.py --profile profile.json --calls calls.json --colls inventory_rolls,inventory_balances
# data (BACA-SAJA; mongosh di kontainer)
bash scripts/audit/b3a_mongo_ro.sh scripts/audit/b3a_db_collections.js > db_collections.tsv
bash scripts/audit/b3a_mongo_ro.sh scripts/audit/b3a_field_profile.js   > profile.json
bash scripts/audit/b3a_mongo_ro.sh scripts/audit/b3a_balance_vs_rolls.js
bash scripts/audit/b3a_mongo_ro.sh scripts/audit/b3a_roll_anomalies.js
bash scripts/audit/b3a_mongo_ro.sh scripts/audit/b3a_doc_checks.js
bash scripts/audit/b3a_mongo_ro.sh scripts/audit/b3a_scope_facts.js
bash scripts/audit/b3a_mongo_ro.sh scripts/audit/b3a_index_facts.js
bash scripts/audit/b3a_mongo_ro.sh scripts/audit/b3a_stock_truth.js     > truth.json
# API (HANYA GET + login; sandi dibaca dari AGENTS.md / env KN_DEMO_PASS, tidak ditulis)
python scripts/audit/b3a_api_fetch.py --base http://127.0.0.1:8063 --out api/ --plan plan.json
python scripts/audit/b3a_compare_numbers.py truth.json api/ sample_pids.json
python scripts/audit/b3a_scope_report.py api/
```
Catatan mongosh: `cursor.forEach(cb)` BERHENTI bila callback mengembalikan `false` — skrip memakai blok `{}`.
Jangan pakai `$lookup … foreignField: "id"` ke `inventory_rolls` (tanpa indeks → COLLSCAN berulang).

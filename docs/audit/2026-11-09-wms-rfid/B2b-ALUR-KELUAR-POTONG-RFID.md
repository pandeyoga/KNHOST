# B2b — Logika alur BARANG KELUAR, POTONG, dan RFID (end-to-end, per cabang)

**Tanggal:** 9 Nov 2026 (07:00–08:30 WIB) · **Pelaksana:** Claude Code (auditor paket B2b) · **Jenis:** AUDIT — tidak ada
kode aplikasi yang diubah · **HEAD diaudit:** `35506d7` (`integrasi-prep3` = `main` + PREP-F printer CP30EN + PREP-G
handheld C72) · **Stack:** sementara `kn-tmp-b2b-*` (Mongo 7 + backend `kn-dev-backend`, kode disalin ke kontainer,
salinan DB `kn_test_trial_2026-11-08` → `test_database`), dihapus sesudah uji · **Akun:** admin@, warehouse@ (Jakarta),
warehouse.soreang@, warehouse.rancamalang@, wh.admin@, manager@, sales@, salesadmin@, finance@, driver@
(sandi: lihat `AGENTS.md`).

Lampiran (tabel transisi LENGKAP dari kode, `berkas:baris`, CAS, efek, pembalikan, idempotensi, pagar):
[`B2b-TRANSISI-SO-AMBIL-KIRIM.md`](B2b-TRANSISI-SO-AMBIL-KIRIM.md) (71 transisi) ·
[`B2b-TRANSISI-POTONG-SAMPEL-NONSO.md`](B2b-TRANSISI-POTONG-SAMPEL-NONSO.md) (134) ·
[`B2b-TRANSISI-RFID.md`](B2b-TRANSISI-RFID.md) (±136). Skrip uji: `scripts/audit/b2b_lib.py`, `b2b_flows.py`,
`b2b_flows2.py`, `b2b_rfid.py`.

---

## 0. Ringkasan

* **Dijalankan sungguhan lewat API** (±370 panggilan, 71 templat endpoint, 10 akun) dengan potret DB sebelum/sesudah
  tiap langkah: **14 alur/cabang keluar** (SO lurus sampai `done`; potong untuk SO dengan susut; backorder + kirim
  sebagian multi-gudang; batal di 4 titik; lepas reservasi + Ganti Roll; override SO; eskalasi/resolve 3 varian;
  kirim sebagian; sampel gratis + potong; sampel berbayar; transfer lurus, transfer 0 diterima, batal transfer di jalan;
  perbaikan) dan **9 alur RFID** (pasang reader V2 di gedung gate, simulator saat mode simulasi PT mati, lintasan nyata
  lewat device key, antrean periksa per peran, gate lama, EPC pensiun dipakai ulang, tandai tercetak manual, handheld
  cakupan + batch idempoten, key handheld di jalur lama).
* **Transisi diperiksa:** ±341 baris transisi dari kode (lampiran) · **±65 transisi diamati runtime** (§3).
* **Temuan resmi: 36** — **P0: 6 · P1: 15 · P2: 13 · P3: 2** (§4; 32 terverifikasi-runtime, 4 terverifikasi-kode).
  Ditambah **38 kandidat statik dalam 17 kelompok** yang belum dijalankan (§8.1, termasuk 4 calon P0: retur bahan
  makloon menghidupkan roll habis, reverse retur QC tidak memulihkan roll tetapi membalik jurnal, SO `approved`
  kedaluwarsa otomatis 3 hari, rollback Ganti Roll melepas semua reservasi SO) dan **6 kandidat yang DIBANTAH runtime**
  (§8.2).
* **Yang sehat (terbukti):** alur SO lurus `reserved → confirmed → partially_picked → picked → shipped → done` lengkap
  dengan roll `reserved → committed → in_transit_sales → delivered`, SJ + jurnal pendapatan & HPP per SJ, logistik
  `prepared → loaded → in_transit → delivered → completed` (foto muat/POD wajib); batal SO melepas reservasi utuh &
  potong; batal sesudah kirim ditolak 409; pagar lokasi `scan-pick` bekerja (404 "Data di luar lokasi tugas Anda");
  sales tidak bisa membuat SO di PT lain (403); konfirmasi SO backorder murni ditolak 409; sampel berbayar tidak bisa
  dikonfirmasi sebelum bayar & sales tidak bisa menyetujui bayar (403); transfer `receive` idempoten per roll; batch
  handheld idempoten (`replay: true`, isi beda → 409).
* **Paling mendesak:**
  1. **STM-OUT-1 (P0)** — menyelesaikan eskalasi ber-qty pada tugas yang sudah terkirim sebagian mengembalikan roll yang
     SUDAH di Surat Jalan menjadi `available` (terbukti: `roll_658609075049` di `KSC/SJ-00077`).
  2. **CUT-1 (P0)** — potong sampel memotong panjang yang sudah dipesan SO lain; potong SO lalu ditolak 409 permanen.
  3. **CUT-3 (P0)** — serah-terima Admin Cutting untuk tugas sampel yang SUDAH BATAL memindah roll Jakarta → Bandung
     tanpa dokumen.
  4. **FLW-OUT-2 (P0)** — SO kirim sebagian dengan backorder macet `partially_shipped` selamanya; roll yang sudah ber-POD
     tetap `in_transit_sales`.
  5. **STM-OUT-3 (P0)** — override SO yang sudah disetujui membuat roll `committed` yatim + reservasi ganda (92,32 kg
     terkunci untuk SO 67,68 kg).
  6. **RFID-2 (P0)** — EPC tag pensiun bisa ditulis ke roll lain dan `GET /rfid/lookup` mengembalikan roll LAMA.
  7. **RFID-1 (P1)** — simulator gate V2 saat mode simulasi PT MATI tetap memasang klaim; lintasan nyata berikutnya
     MERAH `REPLAY_EXIT` + gate terkunci + notifikasi lintas PT.
* **Jawaban keluhan pemilik** (§6): jenis tugas SO vs sampel dibedakan hanya oleh `task_subtype` di koleksi yang sama dan
  daftar HP/desktop mencampur semua jenis & status (termasuk `cancelled/dispatched` dan tugas masuk PO); tugas di gedung
  bersama tidak terlihat petugas lokal kecuali ganti PT aktif (terbukti di RCM-RETUR); pindai per dokumen ada di handheld
  C72 (PREP-G, sesi per dokumen) tetapi ambil SO di HP/desktop tetap per roll/qty dan ambil tanpa roll diterima.

---

## 1. Metode & batas bukti

1. `git merge --ff-only integrasi-prep3` → HEAD `35506d7`. Baca laporan B1, B3a, B3b, B4, PREP-D1/D2/F/G/Gelombang-2,
   `KN_16`, `KN_15`, `KEPUTUSAN_GATE_RFID.md`.
2. **Statik** (tiga pembaca paralel, baca-saja, hasil diperiksa ulang): semua penulis `status` per koleksi
   (`scripts/audit/b3a_db_writers.py --json` 14.767 panggilan Mongo, disaring per koleksi) + grep + baca kode →
   lampiran. Kandidat dengan probe deterministik lalu dijalankan.
3. **Runtime**: stack `kn-tmp-b2b` (satu stack; resep `batch2_common.md`). Setiap langkah: panggilan API (dicatat
   kode/respons) + potret DB sebelum/sesudah (SO, roll terkait termasuk anak, tugas, SJ, logistik, hitungan mutasi
   per jenis, jurnal, audit, notifikasi, sesi cek muat). Keluaran mentah (log JSON + teks) di scratchpad paket, tidak
   di-commit; ID dokumen dikutip di tiap temuan agar bisa diulang.
4. **Manipulasi yang disengaja (diungkap):** (a) setelan `wms.rfid_simulation` PT KSC dimatikan lalu dipulihkan lewat
   `PUT /api/config/values` untuk RFID-1; (b) dua reader V2 uji dibuat & ditautkan ke RCM-WOVEN lewat API
   (`POST /rfid/devices`, `PUT /rfid/v2/ops/devices/{id}/config` fixture kontrak, `PATCH /warehouses/{id}`); (c) jeda
   130 dtk agar klaim simulator lewat jendela "muatan sebelumnya" 120 dtk; (d) dua SO sisa uji dibatalkan untuk
   membebaskan stok. Tidak ada penulisan DB langsung untuk menghasilkan bukti.
5. **Batas:** tanpa perangkat (U300/CP30EN/C72); balapan (dua permintaan bersamaan) tidak dijalankan — temuan tanpa CAS
   dinilai dari kode; alur makloon & retur supplier hanya statik (prasyarat data panjang); `kn_test_trial` berisi data
   uji lama (UI-05/B3a §8) — angka per peran memuatnya.

---

## 2. Alur & cabang yang dijalankan

| # | Alur / cabang | Dokumen uji | Hasil |
|---|---|---|---|
| A1 | SO 2 roll utuh → verifikasi → ajukan (auto-ACC) → konfirmasi → daftar ambil → pindai roll ×2 → cek muat (sesi dimulai sebelum tag) → cek muat ulang → kirim → logistik ekspedisi (foto muat, muat, berangkat, GPS, foto POD, diterima, selesai) | `so_06dab8482244` · `KSC/SJ-00076` · `lgs_d0be0e8f6ee6` | lurus sampai `done`; cek muat pertama `with_issues` (FLW-OUT-6) |
| A2 | Potong untuk SO (`exact_cut`, ½ roll) → potong fisik susut 0,3 → verifikasi label anak → ambil anak → kirim | `so_67267d3df042`, anak `roll_cut_rsv_8588c6712def` | jalan; susut tanpa jurnal (CUT-2), sisa tidak ditandai remnant (CUT-4) |
| A3 | Backorder: SO X 1 roll; SO Y qty > stok (+10, `allow_backorder`) multi-gudang (Jakarta + RCM-RETUR); SO Z backorder murni; konfirmasi; potong; ambil & kirim Jakarta; batal X; rencana pemenuhan Y & Z; POD SJ Y | X `so_788ca8b26865`, Y `so_fcccc19d6aa8`, Z `so_6f9cb39ab4fc` | FLW-OUT-2, FLW-OUT-3, FLW-OUT-5 |
| A4 | Batal: sesudah reservasi potong / sesudah ambil / sesudah kirim | `so_35d013c122db`, `so_fa6e5a0edf25`, `so_8288d7037a24` | lepas benar; batal sesudah ambil tanpa tugas kembalikan (FLW-OUT-4); sesudah kirim 409 ✔ |
| A5 | Eskalasi: (a) tugas `partially_shipped` → resolve `adjusted_qty`; (b) eskalasi → batal SO → resolve; (c) eskalasi → pick → kirim → resolve | `so_f6f3a51e3a29`, `so_4ce9d35bc7fd`, `so_e5afa65e1421` | STM-OUT-1, STM-OUT-2 |
| A6 | Override SO `confirmed` qty +20 | `so_47e78f72c601` | STM-OUT-3 |
| A7 | Lepas reservasi → `draft` → Ganti Roll → batal | `so_bc6e07679b93` | STM-OUT-4 |
| A8 | Pindai roll sama dua kali; ambil sebagian → kirim sebagian | `so_6bb36dca1301`, `so_fa17313186cc` | STM-OUT-5 (kirim sebagian memecah roll tanpa tag) |
| A9 | SO PT lain lewat `entity_id` (sales@); tugas & cek muat SO KSC oleh akun Kanda | — / `so_e001f582bbb5` | 403 ✔ / FLW-OUT-7 |
| B1 | Sampel gratis → konfirmasi → tugas `sample_cut` → potong dari roll yang dipesan SO-A → potong SO-A → batal sampel → serah-terima Cutting ke Bandung | SO-A `so_89386c963e91`, sampel `so_073b4cc26db8`, `wms_9acde69f8246` | CUT-1, CUT-3 |
| B2 | Sampel berbayar: konfirmasi sebelum bayar, bayar oleh sales/finance, konfirmasi, batal (2 pintu) | `so_91c7ed8aed7a` (`KSC/SOS-00084`) | penjaga benar; CUT-6 |
| C1 | Transfer Jakarta → RCM-WOVEN 3 roll: buat → setujui → picking → staging → kirim → K-GDG-09 → terima 1 + rusak 1 → ulang → sisa → selesai | `trn_664a5c12d857` | lurus; FLW-OUT-9 (K-GDG-09) |
| C2 | Transfer 2 roll → kirim → kembalikan ke asal ×2 | `trn_cabc6c4a7793` | FLW-OUT-10 |
| C3 | Transfer → kirim → batal saat di jalan | (run `transfer_cancel`) | FLW-OUT-11 |
| C4 | Perbaikan internal: buat → kirim → terima (grade B, susut) → terima ulang; RO kedua kirim → batal | `rpr_21e84ca3b0cd`, `rpr_e571620312a0` | lurus + idempoten; batal sesudah kirim = FLW-OUT-11 |
| R1 | Pasang 2 reader V2 uji di RCM-WOVEN + profil + pasangan gate | `rdev_efbe95f3d2d6` (IN), `rdev_c7b2cbeabb47` (OUT) | `gate_ready: true` |
| R2 | Mode simulasi KSC MATI → transfer → simulator `full_load` → tunggu 130 dtk → lintasan NYATA (device key) EPC sama | `trn_56aa0d8d2d2e` | RFID-1 |
| R3 | Antrean periksa / ringkasan / sesi reader per 4 akun | kasus RED R2 | RFID-8 |
| R4 | Gate lama `POST /rfid/gate/simulate` oleh petugas | `rdev_891088a797f4`, `roll_84175e8d48e6` | RFID-4 |
| R5 | EPC pensiun dipakai ulang | `roll_65a59e36f957` → `roll_0b30f97778e2` | RFID-2 |
| R6 | Job cetak → tandai tercetak manual oleh petugas | (run `p02`) | RFID-3 |
| R7 | Handheld Soreang: sesi 4 akun, ringkasan tugas, key handheld di `/rfid/ingest` | `rdev_432872d69a56` | RFID-5, RFID-7 |
| R8 | Handheld RCM-WOVEN: transfer KSC diterima petugas Rancamalang; batch ulang/isi beda/tanpa sesi operator | `trn_56aa0d8d2d2e` | idempoten ✔; RFID-6 |
| R9 | Transfer ke gedung gate → simulator `partial_trip` (simulasi menyala) → batal | — | simulator MENERIMA transfer sungguhan (RFID-9) |

---

## 3. Tabel transisi status per dokumen (ringkas + bukti runtime)

Kolom **Runtime**: ✔ diamati sesuai maksud · ✖ diamati menyimpang (ID temuan) · — tidak dijalankan. Rincian
`berkas:baris` per baris ada di lampiran (nomor baris di kurung = ID lampiran).

### 3.1 Sales Order (`sales_orders.status`) — lampiran SO A1

| Dari → ke | Pemicu | Penjaga/CAS | Efek utama | Runtime |
|---|---|---|---|---|
| ∅ → `reserved`/`waiting_stock`/`draft` (SO-01) | `POST /sales-orders` | insert; kredit (409 `CREDIT_BLOCKED`); PT payload ditolak bila bukan PT pengguna | roll `reserved` / `length_reservations`; mutasi `reservation` (1 baris, id roll digabung koma) | ✔ (A1–A8); 403 PT lain ✔ |
| `reserved` → `approved` (auto) → `confirmed` (SO-03/05) | `submit-for-approval` → `confirm` | CAS `so_transition`; verifikasi admin | roll `reserved → committed`; tugas `created` per alokasi (produk×gudang) | ✔ A1 |
| `waiting_stock` → `confirmed` | `confirm` | 409 `INVALID_TRANSITION` | — | ✔ ditolak (A3-Z) |
| `confirmed` → `partially_picked` → `picked` (SO-06) | `scan-pick` → `recompute_so_status` | **tanpa CAS** | `fulfillment.picked_qty`, `stage` | ✔ A1 |
| `picked` → `shipped` / `partially_shipped` (SO-07) | `dispatch` | tanpa CAS (turunan) | `shipped` hanya bila backorder 0 | ✔ A1 / ✖ A3 (FLW-OUT-2) |
| `shipped` → `done` (SO-08) | POD logistik (`on_pod`) | CAS `["shipped"]`; roll dipindah SEBELUM CAS | roll `in_transit_sales → delivered`, **tanpa mutasi** | ✔ A1 |
| `partially_shipped` → `done` | — | tidak ada jalur (backorder tak terisi) | — | ✖ FLW-OUT-2 |
| aktif → `cancelled` (SO-09) | `POST /sales-orders/{id}/cancel` | klaim saga + CAS; tolak `shipped/partially_shipped` | `release_order_rolls` (bukan untuk `draft`); tugas → `cancelled` | ✔ A4 / ✖ STM-OUT-4 (draft) |
| `reserved` → `draft` (SO-10) | `release-reservation` | klaim saga | roll dilepas; `allocations=[]` | ✔ A7 |
| `waiting_stock` → `reserved` (SO-12) | `POST /sales-admin/orders/{id}/fulfillment-plan` | klaim saga ber-prasyarat `ACTIVE` | reservasi baru | ✔ Z; ✖ Y 409 (FLW-OUT-2) |
| sampel `approved`/`waiting_approval` → `confirmed` → `cancelled` (SO-14) | `/sample-orders/{id}/approve-payment`, `/confirm`; batal via `/sales-orders/{id}/cancel` | CAS; `SAMPLE_PAYMENT_PENDING` | tugas `sample_cut` | ✔ B1/B2; ✖ CUT-6 |
| `reserved/…/approved` → `expired` (SO-11) | dipicu **GET** daftar SO/dasbor (STK-11) | tanpa CAS | lepas roll | — (kandidat K-06) |

`allocations[].status` selalu `allocated` (ditulis, tak pernah dibaca/berubah); SO tidak menulis `status_history`
(riwayat hanya `audit_logs`: A1 1 → 5 entri saat konfirmasi).

### 3.2 Roll pada jalur SO (`inventory_rolls`) — lampiran SO A2

| Dari → ke | Pemicu | CAS | Runtime |
|---|---|---|---|
| `available` → `reserved` (utuh) / `available` + `length_reservations` (potong) | buat SO / Ganti Roll / backorder | CAS status+panjang bebas | ✔ |
| `reserved` → `committed` | approve | tanpa CAS | ✔ |
| reservasi potong → anak `committed` (`roll_cut_<rsv>`, `RL-…-1`, tanpa tag, `cut.identity_verified=false` → `true` sesudah verifikasi label) | `POST /inventory/rolls/{r}/reservations/{rsv}/cut` | reservasi ada & panjang cukup | ✔ A2 |
| `committed` → `in_transit_sales` (+ pecah bila kirim < panjang) | `dispatch` | klaim tugas; roll tanpa CAS | ✔ / ✖ STM-OUT-5 |
| `in_transit_sales` → `delivered` | SO `done` (POD semua SJ) | tanpa CAS; per SO, bukan per SJ | ✔ A1 / ✖ FLW-OUT-2 |
| `in_transit_sales` → `available` | resolve eskalasi ber-qty | **tanpa saring status** | ✖ STM-OUT-1 |
| `reserved/committed` → `available` | batal / lepas | tanpa CAS | ✔ A4 (✖ draft STM-OUT-4) |
| `picked`, `packed` | — | dibaca, **tak pernah ditulis** | — |

### 3.3 Tugas ambil (`wms_tasks` outbound, sumber SO) — lampiran SO A3

| Dari → ke | Pemicu | Penjaga/CAS | Runtime |
|---|---|---|---|
| ∅ → `created` (per alokasi) | konfirmasi SO | `count_documents` (idempoten, termasuk `cancelled`) | ✔ |
| `created` → `picking` → `packing` | `scan-pick` (query `actual_qty`, `roll_id`) | CAS `status ∉ {scheduled,dispatched,cancelled,completed}` → **`escalated` lolos**; pagar lokasi ✔ | ✔ / ✖ STM-OUT-2 |
| aktif / `partially_shipped` → `escalated` | `escalate?reason=` | CAS | ✔ |
| `escalated` → `packing` | `resolve-escalation` | **tanpa syarat status tugas bila tanpa qty**; dengan qty melepas roll | ✖ STM-OUT-1/2 |
| `packing` → `dispatched` / `partially_shipped` | `dispatch` (`dispatch_guard`) | klaim saga tugas; reservasi potong satu baris memblokir | ✔ / ✖ FLW-OUT-5 |
| `*` → `cancelled` | batal SO | `update_many` | ✔ (`escalation` tetap `pending_review`) |
| `*` → **dihapus + dibuat ulang** | override SO `confirmed` | — | ✔ A6 (tugas `wms_c312f13d9db1` hilang) |
| `sample_cut` `created` → `packing` → `cancelled` | `cut-sample` / batal SO | klaim tugas | ✔ B1 |

### 3.4 Cek muat (`rfid_verify_sessions.kind=loading_check`) — lampiran SO A4

`∅ → open` (`start`, memotret `expected`/`untagged` SEKALI) → `scan` (`$addToSet`) → `completed` (`clean` |
`with_issues` | `simulated`) atau `override` (`wms.approve`, alasan ≥ 5). Runtime ✔ (A1 `clean`, override di A3–A8),
✖ FLW-OUT-6 (sesi tidak menyegarkan `expected`). Gedung gate OUT tertaut → cek muat handheld opsional (K-GDG-02/§9) —
tidak diuji runtime karena tidak ada SO dari gedung bergate dengan reader tertaut.

### 3.5 Surat Jalan (`shipments`) & logistik (`logistics_deliveries`) — lampiran SO A5/A6

SJ: `∅ → dispatched` (tidak ada `void/cancelled` yang ditulis), `logistics_status` cermin logistik, `gl_status: posted`
(A1: 2 jurnal `shipment_revenue` + `shipment_cogs` ber-`source_id` SJ). Logistik: `prepared → loaded` (foto `load` wajib)
`→ in_transit → delivered` (foto `pod` + nama penerima wajib) `→ completed`; `failed`/bongkar tanpa jalur balik stok.
Semua transisi `update({id})` tanpa CAS. Runtime ✔ A1 (5 transisi), A3 (POD SJ parsial).

### 3.6 Transfer (`warehouse_transfers`) — lampiran POTONG-SAMPEL-NONSO T-A…T-D

`waiting_approval → approved → picking → staging → dispatched` (roll `reserved → in_transit_transfer`,
`transfer_prior_status`) → `partially_received` (roll `available`/`damaged` @tujuan, exception `damaged` terbuka) →
`completed` (`completion_basis: actual_receipt`); `dispatched → cancelled` (roll `available` @asal); exception
`return_to_source` (roll `available` @asal). Runtime ✔ C1 (ulang terima roll sama = tanpa efek), ✖ FLW-OUT-9/10/11.

### 3.7 Perbaikan (`repair_orders`)

`draft → sent` (roll `available → wip`) `→ done` (roll `available`, grade B, panjang aktual, 1 jurnal); terima ulang
→ 400 ✔; `sent → cancelled` → roll langsung `available` di gudang asal (FLW-OUT-11). Runtime ✔ C4.

### 3.8 RFID (tag, cetak, gate V2, handheld) — lampiran RFID §1–§5

| Dokumen | Transisi yang diamati | Runtime |
|---|---|---|
| `rfid_tags` | ∅ → `active` (`/rfid/tags/encode`, EPC sistem) · `active → retired` (`DELETE /rfid/tags/{id}`, `wms.scan`, tanpa alasan) · EPC `retired` → `active` lagi di roll lain | ✖ RFID-2 |
| `rfid_print_jobs` | `queued` (tag `pending_print`) → `printed` (item `confirmed`, `results: []`) lewat `mark-printed` petugas | ✖ RFID-3 |
| `rfid_v2_passages` | simulator: GREEN `MANIFEST_MATCH, SIMULATED_EVIDENCE` (`gate_txn_state: done`, stok tidak dipindah) · nyata: RED `REPLAY_EXIT`, `latched: true` | ✖ RFID-1 |
| `rfid_v2_crossings` | klaim `simulated: true` dipasang walau mode simulasi PT mati | ✖ RFID-1 |
| `rfid_v2_gate_latches` | ∅ → `active` (lintasan RED nyata); `acknowledge` tanpa `latch_id` → 400 `LATCH_REQUIRED` | ✔ |
| `rfid_v2_reviews` | ∅ → `open` (RED, `kind: passage`) + notifikasi `rfid_gate_review` ke manager & warehouse_admin dengan `entity_id: null` | ✖ RFID-8 |
| `rfid_v2_doc_sessions` | `open` (transfer IN) → `closed` (transfer selesai lewat simulator/handheld) | ✔ |
| `warehouse_transfers.gate_arrivals[]` | +1 bukti dari lintasan simulator walau tanpa transaksi | ✖ RFID-1 |
| `inventory_rolls.gate_exit` | ∅ → `{device_id, movement_id}` dari simulator gate lama | ✖ RFID-4 |
| `handheld_operator_sessions` | sesi dibuka untuk 4 akun termasuk sopir (tanpa izin kerja) | ✖ RFID-7 |
| `handheld_requests` | batch `accepted` → kirim ulang `replay: true` → ID sama isi beda 409 `IDEMPOTENCY_CONFLICT` → batch tanpa `operator_session_id` tetap `accepted` | ✔ / ✖ RFID-6 |

---

## 4. Temuan

Format: **Alur/langkah/endpoint** · **Peran** · **Klasifikasi** · **Keparahan** · **Bukti** · **Aturan** · **Dampak** ·
**Rekomendasi** · **Status**. Berkas relatif ke `backend/` kecuali disebut lain.

### A. Ambil, eskalasi, ubah SO (STM-OUT)

### STM-OUT-1 — Resolve eskalasi ber-qty pada tugas `partially_shipped` melepas roll yang SUDAH dikirim ke `available`
- **Alur:** ambil roll A → `POST /outbound/tasks/{id}/dispatch?ship_qty=A` → `escalate` → `resolve-escalation?adjusted_qty=A`.
- **Peran:** warehouse (eskalasi), admin/wh.admin (`wms.approve`, resolve). **Klasifikasi:** bug · **Keparahan:** P0.
- **Bukti (runtime A5a):** SO `so_f6f3a51e3a29` (2 roll, 48,58 kg). Kirim A → `roll_658609075049` `committed →
  in_transit_sales`, `KSC/SJ-00077` terbit (`gl_status: posted`), tugas `wms_382fcfa541b8` `picking → partially_shipped`.
  Eskalasi → `escalated`. Resolve `adjusted_qty=24,25` → Δ DB: `roll_658609075049` **`in_transit_sales → available`,
  `reserved_ref → null`** (roll masih tercantum di `shipments.rolls[]` SJ-00077); roll B `roll_58b0837bc4f6` dipangkas
  24,33 → 24,25 dan **fragmen baru `roll_3ead1f61e6d7` 0,08 kg `available`**; tugas `quantity 48,58 → 24,25`,
  `escalated → packing` padahal `shipped_qty = quantity` (tak bisa dikirim lagi). Kode: eskalasi membolehkan
  `partially_shipped` (`routers/outbound_picking.py:288-289`), resolve memanggil `release_order_rolls_partial`
  (`:393-397`) yang memakai `ORDER_HELD_STATUSES` termasuk `in_transit_sales` (`services/roll_service.py:232,1339-1342`)
  dan melepas dari roll terpendek (`:1366-1392`).
- **Aturan:** KN_16 §7 (`in_transit_sales` hanya → `sold`/`returned`); invarian "roll di SJ aktif bukan stok tersedia".
- **Dampak:** roll yang ada di truk/pelanggan tampil tersedia & bisa dijual lagi; jurnal HPP sudah terposting; sisa
  roll B terkunci ke SO; tugas macet `packing`; muncul roll pecahan 0,08 kg.
- **Rekomendasi:** pelepasan sebagian hanya untuk roll `reserved/committed` yang belum di SJ; tolak eskalasi qty di
  bawah `shipped_qty + picked_qty` dan pada tugas `partially_shipped` cukup "tutup sisa"; tambah invarian guardrail.
- **Status:** terverifikasi-runtime.

### STM-OUT-2 — Eskalasi bisa dilompati dan menghidupkan tugas batal/terkirim
- **Alur:** (a) `escalate` → `POST /sales-orders/{id}/cancel` → `resolve-escalation` (tanpa qty); (b) `escalate` →
  `scan-pick` → `dispatch` → `resolve-escalation`.
- **Peran:** warehouse, admin. **Klasifikasi:** bug · **Keparahan:** P1.
- **Bukti (runtime A5b/c):** (a) SO `so_4ce9d35bc7fd`: tugas `cancelled` (SO batal) → resolve **200** → tugas
  **`packing`** untuk SO batal. (b) SO `so_e5afa65e1421`: saat `escalation.status = pending_review` → `scan-pick` 200,
  `dispatch` 200 (barang berangkat tanpa keputusan supervisor), resolve sesudahnya mengubah `dispatched → packing`.
  Kode: CAS `scan-pick` tidak menolak `escalated` (`outbound_picking.py:231-233`); resolve tanpa qty tidak mensyaratkan
  status `escalated` (`:332-337`, filter akhir hanya `escalation.status ≠ resolved` `:448-450`); batal SO tidak menutup
  sub-dokumen eskalasi (`routers/sales_orders_extra.py:885-888`).
- **Aturan:** eskalasi = keputusan supervisor (izin `wms.approve`); komentar KN-C02 `:286-287` sendiri menyatakan tugas
  batal tidak boleh hidup lagi.
- **Dampak:** tugas hantu di antrean Barang Keluar; status tugas tidak cocok dengan SJ; eskalasi tidak berarti.
- **Rekomendasi:** `scan-pick`/`dispatch` menolak `escalated`; resolve ber-CAS `status = escalated`; batal SO menutup
  `escalation` (`cancelled`).
- **Status:** terverifikasi-runtime.

### STM-OUT-3 — Override SO yang sudah disetujui: roll `committed` tak terlihat → reservasi ganda & roll yatim
- **Alur:** SO `confirmed` → `GET /sales-orders/{id}/override-context` → `POST /sales-orders/{id}/override` qty +20.
- **Peran:** admin (`order.override`). **Klasifikasi:** bug · **Keparahan:** P0.
- **Bukti (runtime A6):** SO `so_47e78f72c601` 47,68 kg = roll utuh `roll_4aaa100e2983` (24,64, `committed`) + potong
  23,04 dari `roll_b7dd45275ff0`. Override → 67,68: sistem memesan **lagi** roll `roll_81a066409d0b` (24,88,
  `reserved`), potong +2,15 di `roll_b7dd45275ff0` dan 17,61 di `roll_e5e0fbcefe7b`. Akhir: roll utuh dipegang 49,52 +
  reservasi potong 42,80 = **92,32 kg terkunci untuk SO 67,68 kg**; `roll_4aaa100e2983` (`committed`, `reserved_ref` = SO)
  **tidak ada lagi di `allocations`**; tugas `wms_c312f13d9db1` **dihapus**, `wms_282c9d1a5dfc` dibuat ulang; roll baru
  berstatus `reserved` pada SO `confirmed`. Kode: `_held` hanya `status: "reserved"` (`services/so_override_service.py:101-108`),
  `EDITABLE` memuat `approved/confirmed` (`:20`); pola sama di Ganti Roll (`sales_orders_extra.py:570,579-581`).
- **Aturan:** SSOT roll (satu alokasi = roll yang dipegang); KN_15 §6.
- **Dampak:** stok terkunci ganda/selamanya; dispatch bisa mengirim roll yatim (SHIPPABLE memuat `committed`); tugas
  gudang berganti id di tengah kerja.
- **Rekomendasi:** `_held` = semua `ORDER_HELD_STATUSES` milik SO + reservasi potong; regenerasi tugas = perbarui
  qty, bukan hapus; tolak override bila ada roll di luar alokasi.
- **Status:** terverifikasi-runtime.

### STM-OUT-4 — SO `draft` memegang roll lewat Ganti Roll dan batal tidak melepasnya
- **Alur:** `POST /sales-orders` → `release-reservation` (→ `draft`) → `POST /sales-orders/{id}/items/{pid}/reallocate`
  → `cancel`.
- **Peran:** admin (`inventory.pegging`, `order.cancel`). **Klasifikasi:** bug · **Keparahan:** P1.
- **Bukti (runtime A7):** SO `so_bc6e07679b93` `cancelled`; roll pengganti tetap `{'status': 'reserved',
  'reserved_ref': {'type': 'sales_order', 'id': 'so_bc6e07679b93'}}`. Kode: Ganti Roll boleh `draft`
  (`sales_orders_extra.py:570`), daftar status yang dilepas saat batal tanpa `draft` (`:871-873`), kedaluwarsa tanpa
  `draft` (`services/inventory_service.py:31`).
- **Aturan:** B3a SSOT-8 (reservasi tertinggal) — jalur baru.
- **Dampak:** stok terkunci untuk pesanan mati, tak terlihat sebagai "dialokasikan" di mana pun.
- **Rekomendasi:** batal selalu melepas semua roll ber-`reserved_ref` SO; Ganti Roll ditolak pada `draft`; invarian
  "roll ber-`reserved_ref` SO terminal = 0".
- **Status:** terverifikasi-runtime.

### STM-OUT-5 — Kirim sebagian roll memecah roll diam-diam; roll anak berangkat tanpa tag
- **Alur:** `scan-pick` 40 % panjang roll → `dispatch?ship_qty=` sama.
- **Peran:** warehouse. **Klasifikasi:** bug / butuh keputusan · **Keparahan:** P1.
- **Bukti (runtime A8):** SO `so_fa17313186cc`: anak `roll_1130855a4dde` 9,78 kg **`in_transit_sales`,
  `rfid_tag_id: null`, tanpa `cut`**; induk sisa tetap milik SO. Kode: `roll_service.py:1484-1498` (pecah saat kirim) vs
  komentar `:1452-1453` "Tidak ada lagi potong otomatis saat dispatch"; gerbang identitas WM-02 hanya untuk anak ber-`cut`
  (`:742-756`).
- **Aturan:** K-OPN-05/K-RFID: roll bertag = identitas; potong harus lewat konfirmasi potong (WM-02).
- **Dampak:** roll tanpa tag lewat gate OUT (merah/kuning di gedung gate); potong fisik tidak tercatat sebagai potong.
- **Rekomendasi:** `dispatch` menolak `ship_qty` < panjang roll; potong wajib lewat reservasi potong.
- **Status:** terverifikasi-runtime. Catatan: pindai roll sama dua kali (½ + ½) diterima dan kirim berhasil — bukan
  anomali bila qty ≤ panjang (ANOM-11 dibantah §8.2).

### B. Alur keluar SO, backorder, batal (FLW-OUT)

### FLW-OUT-1 — Tugas SO di gedung bersama tidak bisa dikerjakan petugas lokal tanpa ganti PT
- **Alur:** SO KSC multi-gudang (Jakarta + RCM-RETUR) → tugas per gudang.
- **Peran:** warehouse (Jakarta), warehouse.rancamalang. **Klasifikasi:** butuh keputusan / bug cakupan · **Keparahan:** P1.
- **Bukti (runtime A3 + R):** SO Y `so_fcccc19d6aa8` → tugas `wh_jakarta` 2.298,2 kg dan `wh_6cccc13554f8` (RCM-RETUR)
  43,75 kg (`wms_9e2a43997df0`). Petugas Jakarta: `scan-pick`/`dispatch` → **404 "Data di luar lokasi tugas Anda"**
  (benar). Petugas Rancamalang (boleh 3 PT): `/wms/tasks` & `/outbound/tasks` tanpa header PT → tugas **tidak tampil**
  (5/4 tugas, semua PT Cipta Sandang); dengan `X-Entity-Id: ent_ksc` → tampil dan `scan-pick` 200. Kode:
  `resolve_list_scope` tanpa param → PT aktif (`services/entity_scope.py:512-516`).
- **Aturan:** K-GDG-07 (semua gedung dipakai bersama); keluhan pemilik #1; B3a SCP-3 (keputusan #6).
- **Dampak:** sebagian SO multi-gudang menggantung (Y tetap `partially_shipped`) sampai petugas tahu harus mengganti PT.
- **Rekomendasi:** daftar tugas fisik per lokasi kerja (semua PT yang diizinkan) dengan lencana PT; Barang Keluar
  menampilkan "tugas di gudang lain belum dikerjakan" di SO.
- **Status:** terverifikasi-runtime.

### FLW-OUT-2 — Kirim sebagian + backorder: SO macet `partially_shipped` selamanya; roll ber-POD tetap di jalan
- **Alur:** SO `allow_backorder` → konfirmasi → kirim yang ada → POD SJ → stok datang (batal SO lain) → rencana pemenuhan.
- **Peran:** admin/salesadmin (`order.confirm`), logistik. **Klasifikasi:** bug · **Keparahan:** P0.
- **Bukti (runtime A3):** Y `so_fcccc19d6aa8` (2.426,95 kg; backorder 85) → kirim Jakarta → `partially_shipped`
  (`fulfillment.backorder_qty 85`). Batal X membebaskan roll; `POST /sales-admin/orders/{Y}/fulfillment-plan` →
  **409 "Pesanan sedang diproses pemenuhan lain — coba lagi sebentar."** (padahal tidak ada proses lain). POD SJ Y →
  roll SJ **tetap `in_transit_sales`**, Y tetap `partially_shipped`. Kode: `ACTIVE` tanpa `partially_picked/picked/
  partially_shipped` (`services/backorder_service.py:26,38-41`), `shipped` menunggu backorder (`services/fulfillment_status.py:47-57`),
  roll `delivered` hanya saat SO utuh `done` (`services/so_delivery_service.py:31-46`, `roll_service.py:1519-1534`).
- **Aturan:** KN_16 §2 "Partial shipment: boleh kirim sebagian → sisa jadi backorder"; KN_16 §7 / KN_15 §3.4.1
  (`in_transit_sales → sold` saat POD).
- **Dampak:** pesanan tak pernah selesai; `in_transit_sales_qty`/`owned_qty` membengkak; pesan galat menyesatkan; satu-
  satunya jalan keluar amandemen qty.
- **Rekomendasi:** `ACTIVE` memuat status ambil/kirim sebagian; POD per SJ memindah roll SJ itu; pesan galat sesuai alasan.
- **Status:** terverifikasi-runtime.

### FLW-OUT-3 — Alokasi otomatis mengambil stok dari Gedung Retur/inspeksi (RCM-RETUR)
- **Alur:** SO qty besar → alokasi multi-gudang. **Peran:** sales/admin. **Klasifikasi:** butuh keputusan · **Keparahan:** P2.
- **Bukti (runtime A3):** Y dialokasikan 43,75 kg dari `wh_6cccc13554f8` "RCM-RETUR" (roll `available`); B1 UI-42 &
  `KEPUTUSAN_GATE_RFID.md` K-GDG-04: Gedung Retur = tempat inspeksi (juga menyimpan grade B/BS/C, §9).
- **Dampak:** barang yang menunggu/sesudah inspeksi bisa terjual sebagai stok biasa dan memicu tugas lintas site.
- **Rekomendasi:** peran gedung "inspeksi/retur" dikecualikan dari alokasi otomatis kecuali grade diminta; putuskan.
- **Status:** terverifikasi-runtime (perilaku); maksud belum diputuskan.

### FLW-OUT-4 — Batal SO sesudah ambil: roll langsung `available` di bin asal, tanpa tugas kembalikan ke rak
- **Alur:** ambil penuh → batal SO. **Peran:** sales/admin. **Klasifikasi:** fitur belum ada · **Keparahan:** P1.
- **Bukti (runtime A4):** SO `so_fa6e5a0edf25`: tugas `cancelled` (`picked_qty 24,52`); roll `available`,
  `bin_id: bin_sim_wh_jkt_k01_l4_02` (bin rak asal) padahal fisik di area muat; 0 tugas kembalikan. Kode:
  `sales_orders_extra.py:871-873,885-888`.
- **Aturan:** SSOT lokasi roll; K-GDG-02 (barang pindah = dokumen).
- **Dampak:** roll "hilang" di area muat; pemilih roll SO berikutnya menunjuk bin yang kosong.
- **Rekomendasi:** status `returning` + tugas "kembalikan ke rak" (bin dipindai saat taruh) untuk roll yang sudah dipick.
- **Status:** terverifikasi-runtime.

### FLW-OUT-5 — Reservasi potong yang belum dipotong memblokir kirim roll utuh lain di tugas yang sama
- **Alur:** SO qty-mode (alokasi = roll utuh + potong) → ambil roll utuh → `dispatch?ship_qty=` roll itu.
- **Peran:** warehouse. **Klasifikasi:** hambatan UX / butuh keputusan · **Keparahan:** P2.
- **Bukti (runtime A3 percobaan 1):** `POST /outbound/tasks/wms_159b5ed31526/dispatch?ship_qty=25.39` → **409 "1 reservasi
  potong belum dikonfirmasi (roll induk RL-12291). Potong fisik & konfirmasi dulu."** (`assert_cut_identity_ready`
  `roll_service.py:1453`).
- **Dampak:** kirim sebagian tidak bisa berangkat menunggu meja potong, walau `shipment_policy = allow_partial_shipment`.
- **Rekomendasi:** gerbang identitas hanya untuk roll yang ikut SJ ini.
- **Status:** terverifikasi-runtime.

### FLW-OUT-6 — Cek muat memotret "yang diharapkan" sekali; tag yang ditulis selama sesi dihitung "lebih"
- **Alur:** `loading-check/start` (roll belum bertag) → tag ditulis (`simulate-tags`; sama untuk tulis tag C72 PREP-G)
  → `scan` EPC roll SO → `complete`.
- **Peran:** warehouse. **Klasifikasi:** bug · **Keparahan:** P2.
- **Bukti (runtime A1):** sesi `rvs_2a3c0748e337`: hasil **`with_issues`**, `expected 0`, `extra` = 2 EPC milik roll SO
  sendiri, `untagged_unresolved` = 2 roll yang sudah bertag; dispatch 400 "Final Loading Check TIDAK BERSIH (missing 0,
  extra 2, roll tanpa tag belum diverifikasi 2)". Sesi baru `rvs_292fdfe04c74` → `clean`. Kode: `expected` dibangun di
  `start` (`services/loading_check_service.py:45-52,55-99`), `complete` tidak menyegarkan.
- **Dampak:** petugas yang menulis tag di depan truk (alur C72 "tulis EPC") mendapat hasil tidak bersih; tidak ada
  tombol batal sesi `open`.
- **Rekomendasi:** `complete` menghitung ulang `expected` dari tag aktif roll SO saat itu; endpoint batal sesi.
- **Status:** terverifikasi-runtime.

### FLW-OUT-7 — Pagar PT bolong di dua endpoint tugas keluar
- **Alur:** `POST /wms/tasks/outbound-from-order/{SO}` dan `GET /outbound/so/{SO}/loading-check` dengan akun PT lain.
- **Peran:** warehouse.soreang (PT Kanda). **Klasifikasi:** bug · kebocoran · **Keparahan:** P1.
- **Bukti (runtime A9):** SO KSC `so_e001f582bbb5` (`confirmed`): akun Soreang/Kanda → `POST outbound-from-order` **200**
  (`[]` karena tugas sudah ada — tidak ada 403), `GET loading-check?warehouse_id=wh_jakarta` **200** berisi
  `open_session`, `by_warehouse`, `rfid_simulation`, daftar roll tanpa tag. Kode: `routers/wms.py:135-156` (tanpa
  `assert_entity_access`), `routers/outbound_picking.py:622-625`.
- **Aturan:** isolasi PT (invarian KN_14 / guardrail entity scope).
- **Dampak:** PT lain bisa melahirkan tugas untuk SO yang belum bertugas dan membaca status muat/roll.
- **Rekomendasi:** `assert_entity_access(order, "sales_orders", ctx)` di kedua endpoint.
- **Status:** terverifikasi-runtime (baca); tulis = terverifikasi-kode (cabang "buat tugas" tidak terpicu).

### FLW-OUT-8 — POD/`done` tanpa mutasi; status tujuan `delivered` bukan `sold`
- **Alur:** POD logistik → SO `done`. **Klasifikasi:** inkonsistensi / dokumen basi · **Keparahan:** P3.
- **Bukti (runtime A1):** roll `in_transit_sales → delivered` (+`delivered_at`), hitungan mutasi tidak berubah (mutasi
  hanya `reservation` & `outbound_ship`). KN_16 §7 & KN_15 §3.4.1 menulis `sold`; registry tak memuat `delivered`
  (B3a SSOT-1).
- **Rekomendasi:** putuskan istilah (`delivered`) lalu perbarui KN_16/registry; catat mutasi serah terima bila buku
  besar per roll dipakai.
- **Status:** terverifikasi-runtime.

### C. Keluar non-SO (transfer, perbaikan)

### FLW-OUT-9 — K-GDG-09 "stok transit boleh dialokasikan/dijual" tidak berlaku untuk transfer
- **Alur:** transfer `dispatched` → pratinjau alokasi & SO roll-mode untuk roll transit.
- **Peran:** sales/admin. **Klasifikasi:** butuh keputusan (dokumen vs kode) · **Keparahan:** P2.
- **Bukti (runtime C1):** `POST /sales-orders/preview-allocation` tidak memakai roll transit; SO dengan `roll_lines`
  roll transit → **409 "Roll RL-05618 sudah tidak tersedia."** Statik: K-GDG-09 hanya berlaku untuk draf putaway
  (lampiran TRF-09).
- **Rekomendasi:** perjelas K-GDG-09 (transit transfer TIDAK dijual, kecuali transfer ber-`sales_order_id`) atau bangun.
- **Status:** terverifikasi-runtime.

### FLW-OUT-10 — Transfer `completed` dengan 0 roll diterima, `completion_basis: actual_receipt`
- **Alur:** transfer 2 roll → kirim → exception `return_to_source` ×2. **Peran:** admin. **Klasifikasi:** bug label/status · **Keparahan:** P2.
- **Bukti (runtime C2):** `trn_cabc6c4a7793` `dispatched → completed`, `completion_basis: actual_receipt`, kedua roll
  `available` @Jakarta. Kode: `services/transfer_receipt_service.py:243-249`.
- **Dampak:** laporan transfer "selesai diterima" padahal tidak ada barang tiba; roll hilang hanya bisa "dikembalikan".
- **Rekomendasi:** status `returned`/`cancelled_in_transit` + basis `returned_to_source`.
- **Status:** terverifikasi-runtime.

### FLW-OUT-11 — Batal saat barang di jalan (transfer `dispatched`, perbaikan `sent`): roll langsung tersedia di asal
- **Alur:** `DELETE /transfers/{id}?reason=` saat `dispatched`; `POST /repair-orders/{id}/cancel` saat `sent`.
- **Peran:** admin (`transfer.cancel`, repair). **Klasifikasi:** fitur belum ada · **Keparahan:** P1.
- **Bukti (runtime C3/C4):** dua roll transfer → `('available', 'wh_jakarta', transfer_prior_status: 'reserved')`
  (penanda basi tertinggal, dipakai ulang transfer berikutnya: `roll_fe31506f590e` tidak menulis ulang penanda);
  RO `rpr_e571620312a0` batal 200 → roll `available` @Jakarta. Kode: `routers/transfers.py:762-790`,
  `services/repair_order_service.py:219-238`.
- **Aturan:** K-GDG-02 (gate memvalidasi barang keluar/masuk); SSOT lokasi.
- **Dampak:** roll yang masih di truk/di bengkel bisa dialokasikan & diambil dari rak kosong.
- **Rekomendasi:** batal di jalan → status `returning` sampai diterima kembali (handheld/gate IN asal); hapus
  `transfer_prior_status` saat selesai/batal.
- **Status:** terverifikasi-runtime.

### D. Potong & sampel (CUT)

### CUT-1 — Potong sampel memotong panjang yang sudah dipesan SO lain → potong SO ditolak permanen
- **Alur:** SO-A pesan potong 22,48 dari roll 23,98 → sampel gratis 2 kg → `POST /outbound/tasks/{t}/cut-sample`
  `roll_id` = roll itu → `POST /inventory/rolls/{r}/reservations/{rsv}/cut` untuk SO-A.
- **Peran:** warehouse (`wms.scan`). **Klasifikasi:** bug · **Keparahan:** P0.
- **Bukti (runtime B1):** roll `roll_4f73eedadc6e`: sesudah potong sampel **`length_remaining 21,98 < length_reserved
  22,48`**; potong SO-A → **409 "Roll induk berubah / panjang fisik tidak cukup untuk dipotong"**; saldo `available_qty
  1.356,86 · reserved_qty 45,26` tetap menghitung reservasi. Kode: `services/sample_sale_service.py:429-433` (tanpa
  `length_reserved`), pola sama `rnd_sample_service.py:1469-1475`, `mdq_cut_service.py:83-84` (lampiran POT-01).
- **Aturan:** B3a DUP-4 ("panjang bebas" diimplementasi ulang); KN_15 §6 (reservasi mengikat).
- **Dampak:** komitmen SO tak bisa dipenuhi dari roll yang dipesan, tanpa peringatan sampai meja potong.
- **Rekomendasi:** satu fungsi `free_length(roll)` untuk semua potong (sampel, R&D, MDQ); CAS `$expr` panjang bebas.
- **Status:** terverifikasi-runtime.

### CUT-2 — Susut potong (`cut_waste`) mengurangi stok tanpa jurnal
- **Alur:** `POST /inventory/rolls/{r}/reservations/{rsv}/cut` `{"waste": 0.3}`. **Peran:** warehouse.
- **Klasifikasi:** bug / inkonsistensi · **Keparahan:** P1.
- **Bukti (runtime A2):** SO `so_67267d3df042`: mutasi `cut_waste −0,3` ada; jurnal terkait potong **0** (sebelum 0).
  Pembanding: potong MDQ memposting write-off (`mdq_cut_service.py:98-101`); `roll_service.py:675-677`.
- **Aturan:** KN_16 §1 prinsip 3 (setiap perubahan stok = mutasi + nilai); invarian INV-GL.
- **Dampak:** nilai persediaan GL > sub-buku roll; sistemik (±6.000 roll/hari, K §10).
- **Rekomendasi:** jurnal write-off susut seperti MDQ (atau ke akun susut potong).
- **Status:** terverifikasi-runtime.

### CUT-3 — Serah-terima Admin Cutting menerima tugas sampel yang sudah BATAL dan memindah roll antar kota
- **Alur:** potong sampel → batal SO sampel → `POST /cutting/tasks/{t}/receive {"to_warehouse_id": "wh_bandung"}`.
- **Peran:** admin (`sample_order.cutting_receive`). **Klasifikasi:** bug · **Keparahan:** P0.
- **Bukti (runtime B1):** tugas `wms_9acde69f8246` `cancelled`; anak sampel `roll_09380f83e707` `available` @Jakarta →
  serah-terima **200** → roll **`available` @`wh_bandung`, `bin_id: ""`** — tanpa transfer, tanpa dokumen gate. Kode:
  `services/cutting_service.py:109-144` (tanpa cek status tugas, tanpa CAS) (lampiran SMP-01/SMP-02).
- **Aturan:** K-GDG-02 (barang pindah gedung = dokumen & gate); SSOT lokasi.
- **Dampak:** stok berpindah site tanpa jejak dokumen; kartu stok Jakarta/Bandung salah.
- **Rekomendasi:** tolak tugas terminal; serah-terima lintas gedung = transfer internal (gate bila gedung gate).
- **Status:** terverifikasi-runtime.

### CUT-4 — Sisa potong tidak menjadi remnant/BS; SO dan sampel berbeda aturan
- **Alur:** potong SO (A2) vs potong sampel (B1). **Klasifikasi:** butuh keputusan / dokumen basi · **Keparahan:** P2.
- **Bukti (runtime A2):** induk sisa 11,93 kg `is_remnant: false`, grade A; potong sampel menandai `is_remnant` bila
  sisa < 2 (`sample_sale_service.py:440`). KN_16 §2/§4 "remnant (BS)".
- **Rekomendasi:** ambang sisa per kategori & aturan grade, sama untuk SO dan sampel; perbarui KN_16.
- **Status:** terverifikasi-runtime (perilaku); maksud belum diputuskan.

### CUT-5 — Tugas sampel dan tugas SO tercampur di daftar yang sama; pembeda hanya `task_subtype`
- **Alur:** `GET /wms/tasks` (HP) & `GET /outbound/tasks` (desktop). **Peran:** warehouse, wh.admin, manager, salesadmin.
- **Klasifikasi:** inkonsistensi · **Keparahan:** P2 · **silang B1 UI-08/UI-10**.
- **Bukti (runtime B1 + R vis):** tugas `sample_cut` `wms_9acde69f8246` tampil di kedua daftar; petugas Jakarta: HP 186
  tugas = SO 109 · sampel 21 · **PO (masuk) 54** · makloon 2, status `dispatched 61 · cancelled 29 · completed 17`
  ikut; desktop 130 (SO 109 · sampel 21). `GET /wms/tasks` tidak punya saringan jenis/status/gudang
  (`routers/wms.py:27-64`; aktif ≤ 2.000 + selesai ≤ 200).
- **Rekomendasi:** endpoint daftar keluar per lokasi dengan `jenis` (SO, sampel, potong SO, transfer, makloon,
  perbaikan, retur) dan status aktif bawaan (B4 §1.3).
- **Status:** terverifikasi-runtime.

### CUT-6 — Sampel berbayar dibatalkan tetap `sample_payment_status: approved`
- **Alur:** `approve-payment` (finance) → `confirm` → `POST /sample-orders/{id}/cancel` (409, sudah di gudang) →
  `POST /sales-orders/{id}/cancel`. **Klasifikasi:** inkonsistensi · **Keparahan:** P2.
- **Bukti (runtime B2):** `KSC/SOS-00084` akhir `{'status': 'cancelled', 'sample_payment_status': 'approved'}`, tugas
  `cancelled`; tidak ada jejak pengembalian/pembatalan bayar. Penjaga lain benar (konfirmasi sebelum bayar 409
  `SAMPLE_PAYMENT_PENDING`, sales 403, persetujuan ulang idempoten 200).
- **Rekomendasi:** batal SO sampel berbayar → `sample_payment_status: void/refund_pending` + notifikasi Finance.
- **Status:** terverifikasi-runtime.

### E. RFID (tag, cetak, gate, handheld)

### RFID-1 — Simulator gate V2 saat mode simulasi PT MATI memasang klaim → lintasan nyata MERAH & gate terkunci
- **Alur:** reader V2 nyata (gedung gate RCM-WOVEN, tertaut) · `wms.rfid_simulation` KSC = mati · transfer KSC
  `dispatched` → `POST /rfid/v2/ops/devices/{id}/simulate {"scenario":"full_load","source_type":"wh_transfer"}` →
  130 dtk → lintasan nyata (device key, EPC sama) `POST /rfid/v2/events` + `/passages/{id}/close`.
- **Peran:** admin (simulator), reader. **Klasifikasi:** bug · **Keparahan:** P1.
- **Bukti (runtime R2):** simulator → GREEN `MANIFEST_MATCH, SIMULATED_EVIDENCE`, stok **tidak** dipindah (roll tetap
  `in_transit_transfer` — benar), **tetapi 2 klaim `rfid_v2_crossings` `simulated: true` dipasang** dan
  `warehouse_transfers.gate_arrivals[]` +1. Lintasan nyata → **RED `REPLAY_EXIT`, `latched: true`**, kunci gate
  `9a5e6d96-…` aktif, transfer tidak diterima; kasus antrean `RED` + notifikasi "Gate MERAH terkunci" ke manager &
  warehouse_admin. Kode: `services/rfid_v2_service.py:233-241`, `rfid_v2_sessions.py:67-71`, `gate_txn_service.py:148-149,272-279`.
- **Aturan:** PREP-D2 §2 ("simulator hanya bertransaksi bila mode simulasi menyala … agar simulasi tidak mengubah stok
  produksi"); K-RFID-09 (merah = pelanggaran nyata).
- **Dampak:** uji coba admin di reader produksi meracuni gate: muatan nyata ditahan merah, petugas harus minta
  supervisor; "roll kurang" tidak muncul karena klaim palsu.
- **Rekomendasi:** saat mode simulasi mati, simulator hanya boleh di perangkat bertanda uji/`simulation_only` dan tidak
  memasang klaim/bukti dokumen; atau klaim simulasi diabaikan penilai replay.
- **Status:** terverifikasi-runtime (G-02 "simulator merah mengunci gate" tidak terpicu: skenario `foreign_roll` → 409
  `NO_DOCUMENT_ROLLS`).

### RFID-2 — EPC tag pensiun dipakai ulang untuk roll lain; lookup EPC mengembalikan roll LAMA
- **Alur:** `POST /rfid/tags/encode` roll R1 → `DELETE /rfid/tags/{tag}` → `POST /rfid/tags/encode {"roll_id": R2,
  "epc": <EPC R1>}` → `GET /rfid/lookup?code=<EPC>`.
- **Peran:** warehouse (`wms.scan`). **Klasifikasi:** bug · **Keparahan:** P0.
- **Bukti (runtime R5):** encode ulang **200**; `rfid_tags` EPC sama = `[{roll_65a59e36f957, retired},
  {roll_0b30f97778e2, active}]`; lookup → **`roll_65a59e36f957` (roll lama)**. Indeks `uniq_live_epc` (parsial
  `active/pending_print`) ada di DB ini, jadi hanya EPC "hidup" yang unik. Kode: `services/rfid_service.py:107-111`
  (encode tidak memeriksa EPC pensiun — beda dengan `allocate_epc`), `routers/rfid.py:114,330-338` (cari EPC tanpa
  status); juga `sample_sale_service.py:295`, `makloon_issue_rolls.py:93` (lampiran T-01/T-02).
- **Aturan:** K-OPN-05 + PREP-F §9.2 ("EPC yang pernah terbit tidak pernah dipakai lagi").
- **Dampak:** pindai/gate/handheld bisa mengenali roll yang salah (roll lama yang sudah keluar); dua chip ber-EPC sama.
- **Rekomendasi:** encode manual menolak EPC yang pernah ada; semua pencarian EPC menyaring `status ∈ {active,
  pending_print}`; indeks unik EPC seumur hidup (bukan parsial) untuk EPC sistem.
- **Status:** terverifikasi-runtime.

### RFID-3 — "Tandai tercetak" manual oleh petugas mengaktifkan tag tanpa bukti chip tertulis
- **Alur:** `POST /rfid/print-jobs {"roll_ids":[R]}` → `POST /rfid/print-jobs/{job}/mark-printed`.
- **Peran:** warehouse (`wms.print/scan`). **Klasifikasi:** bug / butuh keputusan · **Keparahan:** P1.
- **Bukti (runtime R6):** tag `pending_print → active`; job `printed`, item `confirmed`, `results: []` (tanpa baca balik
  EPC). Kode: `routers/rfid.py:539-547`, `services/rfid_print_service.py:542-572,809-815` (lampiran P-02).
- **Aturan:** PREP-F §9.3 ("sukses label RFID yang tidak pasti wajib bukti baca EPC"); RACC-24 (tercetak ≠ terverifikasi).
- **Dampak:** tag aktif yang chip-nya kosong/beda → gate menganggap roll tanpa tag/asing.
- **Rekomendasi:** `mark-printed` hanya untuk label non-RFID, atau tag tetap `pending_verify` sampai sesi verifikasi.
- **Status:** terverifikasi-runtime.

### RFID-4 — Simulator gate lama (`wms.scan`) menulis `gate_exit` dan alarm nyata
- **Alur:** `POST /rfid/gate/simulate {"device_id": "rdev_891088a797f4", "roll_id": R}` (gate OUT lama Jakarta).
- **Peran:** warehouse. **Klasifikasi:** bug · **Keparahan:** P1.
- **Bukti (runtime R4):** roll `roll_84175e8d48e6` (di SJ SO Y) `gate_exit: null → {movement_id: so_fcccc19d6aa8,
  device_id, at}`; percobaan pertama pada roll tanpa SJ membuat insiden `NO_DOCUMENT` dan notifikasi **"🔴 ALARM GATE
  MERAH — Jakarta · Gudang Sukacita"** ke peran warehouse. Kode: `routers/rfid.py:446-455`,
  `services/rfid_ingest_service.py:230-231`, `gate_evaluator.py:147-149` (lampiran G-03).
- **Aturan:** B3b FRM-13 (simulasi menulis bacaan nyata); SSOT-6 (V1 & V2 sama-sama hidup).
- **Dampak:** bukti "sudah keluar" palsu pada roll nyata (dibaca V2 sebagai `REPLAY_EXIT`); alarm palsu.
- **Rekomendasi:** simulator lama hanya di mode simulasi PT & perangkat uji, tanpa `gate_exit`/notifikasi; jadwalkan
  pensiun V1.
- **Status:** terverifikasi-runtime.

### RFID-5 — Key handheld diterima `POST /rfid/ingest` tanpa sesi pengguna
- **Alur:** `POST /rfid/ingest` header `X-Device-Key: <key C72>` saja. **Peran:** perangkat. **Klasifikasi:** bug · **Keparahan:** P1.
- **Bukti (runtime R7):** **200** `{"device": {"id": "rdev_432872d69a56", "code": "C72-B2B-…"}, "accepted": 1}`;
  `rfid_tags.last_seen_device_id` = C72. PREP-G: endpoint kerja handheld butuh key + sesi operator. Kode:
  `routers/rfid.py:605-613`, `rfid_ingest_service.py:136,308-320` (lampiran H-01/L-04).
- **Dampak:** key C72 yang bocor bisa mengisi sesi verifikasi/cek muat (lintas PT) tanpa operator.
- **Rekomendasi:** jalur lama menolak perangkat `type: handheld` (409 seperti protokol V2).
- **Status:** terverifikasi-runtime.

### RFID-6 — Batch handheld tanpa `operator_session_id` tetap diterima
- **Alur:** `POST /handheld/batches` `transfer_in` dengan `operator_session_id: null`. **Klasifikasi:** bug · **Keparahan:** P2.
- **Bukti (runtime R8):** 200 (`snapshot_stale: true`) dan roll diterima; batch biasa: `accepted`, kirim ulang
  `replay: true`, isi beda 409 `IDEMPOTENCY_CONFLICT` (benar). Kode: lampiran H-08.
- **Aturan:** PREP-G §7.10 ("bukti milik operator penangkapnya").
- **Rekomendasi:** `operator_session_id` wajib & harus sesi aktif milik pengguna Bearer.
- **Status:** terverifikasi-runtime.

### RFID-7 — Sesi operator handheld dibuka untuk akun tanpa izin kerja gudang (sopir)
- **Alur:** `POST /handheld/session/start` (key C72 Soreang + Bearer driver@). **Klasifikasi:** inkonsistensi · **Keparahan:** P3.
- **Bukti (runtime R7):** sopir → 200, `warehouses: [SRG-01]`; ringkasan semua jenis `allowed: false`. Petugas Jakarta
  → `warehouses: []` (cakupan perangkat ∩ lokasi kerja bekerja).
- **Rekomendasi:** tolak sesi bila tidak ada jenis tugas yang diizinkan (selaras B1 UI-23).
- **Status:** terverifikasi-runtime.

### RFID-8 — Ringkasan antrean periksa & notifikasi gate tanpa pagar PT/lokasi
- **Alur:** `GET /rfid/v2/ops/reviews`, `/reviews/summary`, notifikasi `rfid_gate_review`.
- **Peran:** warehouse (Jakarta), warehouse.soreang, warehouse.rancamalang, wh.admin. **Klasifikasi:** bug · kebocoran · **Keparahan:** P2.
- **Bukti (runtime R3):** daftar kasus tersaring lokasi (Jakarta/Soreang n=0; Rancamalang & wh.admin n=1 RCM-WOVEN —
  benar), tetapi `summary` untuk SEMUA akun = `{'open': 1, 'red': 1}`; notifikasi kasus `entity_id: null` (semua
  manajer/Admin Gudang semua PT). Gelombang-2 sudah mencatat ringkasan lintas gudang "angka saja".
- **Rekomendasi:** ringkasan & notifikasi memakai cakupan gudang/PT kasus.
- **Status:** terverifikasi-runtime.

### RFID-9 — Mode simulasi RFID menyala untuk tiga PT nyata → simulator memindah stok sungguhan
- **Alur:** `simulate partial_trip` transfer KSC ke RCM-WOVEN (setelan KSC dipulihkan menyala). **Klasifikasi:** butuh keputusan / konfigurasi · **Keparahan:** P1.
- **Bukti (runtime R9):** lintasan simulator GREEN → **transfer `completed`, kedua roll `available` @RCM-WOVEN**, sesi
  dokumen `closed`. `config_values`: `wms.rfid_simulation = true` untuk `ent_ksc`, `ent_kanda`, `ent_82b52ed6ee8b`
  sejak UAT 22 Okt.
- **Aturan:** PREP-D2 §2 (perilaku dirancang); K §10 (gate nyata = keputusan server).
- **Dampak:** sebelum pilot, satu klik simulator admin di reader produksi menerima/mengirim barang sungguhan.
- **Rekomendasi:** matikan `wms.rfid_simulation` tiga PT sebelum reader dipasang; simulator dibatasi ke perangkat uji.
- **Status:** terverifikasi-runtime.

### RFID-10 — Gudang "gate" belum punya reader; SRG-01 "khusus Kanda" bertentangan dengan K-GDG-07
- **Alur:** `GET /warehouses/{id}/gate-policy`; `POST /transfers` KSC → SRG-01. **Klasifikasi:** butuh keputusan / data · **Keparahan:** P2.
- **Bukti (runtime R1/R8):** RCM-WOVEN, RCM-KNITTING, SRG-01 `effective_mode: gate`, `gate_ready: false`, tanpa
  perangkat (hanya reader lama `DEV-84134` di Jakarta); transfer KSC ke SRG-01 → **403 "Gudang Soreang · Gudang Kanda
  khusus untuk Kanda Fabric"**, padahal K-GDG-07: semua gedung dipakai bersama semua PT.
- **Rekomendasi:** konfirmasi pemilik; samakan data master gudang dengan keputusan sebelum opname/gate.
- **Status:** terverifikasi-runtime.

### F. Terverifikasi-kode (belum dijalankan; tinggi keyakinan)

### STM-OUT-6 — Transisi status tanpa CAS di jalur keluar (penulis "baca lalu `update({id})`")
- **Bukti kode:** `recompute_so_status` (`fulfillment_status.py:32-37` vs `:73`), kedaluwarsa (`inventory_service.py:49-52`),
  logistik `transition` & `pickup_handover` (`logistics_service.py:532-538` vs `:588-589`, `:634-637`), rilis manual tugas
  terjadwal (`outbound_picking.py:104-110`), MKO `issue_step`/`cancel_order` `replace_one` (`makloon_order_service.py:651-655,741,1528`),
  potong sampel `length_remaining` (`sample_sale_service.py:438-440`), pecah roll transfer (`roll_service.py:1923-1925`),
  `mark-delivered` memindah roll sebelum CAS (`sales_orders_extra.py:546-548`).
- **Alur:** semua alur keluar (SO, logistik, MKO, sampel, transfer). **Peran:** pengguna paralel (gudang + sales + logistik).
- **Klasifikasi:** bug laten (balapan) · **Keparahan:** P1 · **Status:** terverifikasi-kode (uji bersamaan belum).
- **Aturan:** pola CAS/klaim saga proyek (guardrail `verify_atomic_claim`, regresi WM-01).
- **Dampak:** dua aksi bersamaan (batal ↔ kirim, diterima ↔ gagal, potong sampel ↔ potong SO) menimpa status atau
  menggandakan efek (jurnal, roll anak, timeline).
- **Rekomendasi:** pola baku `find_one_and_update({id, status: from})` + klaim saga untuk efek ganda; guardrail
  `verify_atomic_claim` diperluas ke daftar ini.

### STM-OUT-7 — Status yatim / ditulis tak dibaca / dibaca tak ditulis
- **Bukti kode:** `allocations[].status` selalu `allocated` (0 pembaca); roll `picked/packed` dibaca
  (`roll_service.py:232,1438`, `loading_check_service.py:17`) tak pernah ditulis; tugas `completed/picked/done` hanya
  dibaca; SO `delivered/dispatched/packed/invoiced` hanya dibaca; SJ `void/cancelled` dibaca, tak ada penulis;
  `is_issued` mencari Faktur `"cancelled"` padahal Faktur batal = `"batal"` (`amendment_service.py:277-278` vs
  `tax_invoice_service.py:143,242`) → override/batal-baris terkunci selamanya.
- **Klasifikasi:** inkonsistensi · **Keparahan:** P2 · **Status:** terverifikasi-kode.
- **Rekomendasi:** tabel transisi per dokumen di kode (enum + `ALLOWED`) dan guardrail "status yang ditulis ∈ enum".

### RFID-11 — Sesi dokumen gate tidak ditutup di beberapa titik siklus hidup
- **Bukti kode:** MKO (manual saja — PREP-D2 §9), transfer/perbaikan dibatalkan, transfer selesai lewat `POST
  /transfers/{id}/status`, SJ tanpa logistik (`routers/transfers.py:667-800`, `repair_order_service.py:219-238`,
  `logistics_service.py:592-593`) (lampiran G-04). Runtime R9 tidak memicu (transfer keburu `completed`).
- **Klasifikasi:** bug · **Keparahan:** P2 · **Status:** terverifikasi-kode.
- **Aturan:** K-RFID-10 (roll kurang dinilai saat dokumen ditutup). **Dampak:** roll yang tidak lewat gate tidak pernah
  masuk antrean periksa; sesi `open` menumpuk. **Rekomendasi:** kait penutupan di batal transfer/perbaikan, jalur
  `status`, penerimaan hasil MKO, dan SJ tanpa logistik.

### RFID-12 — "Gedung gate" membebaskan wajib cek muat dari konfigurasi, bukan dari reader yang bekerja
- **Bukti kode:** `gate_txn_service.gate_validates` (`:75-81`) hanya memeriksa profil & pasangan; reader `enabled:false`
  / offline tetap membebaskan `dispatch_guard` (`loading_check_service.py:304-308`) (lampiran G-05).
- **Klasifikasi:** bug · **Keparahan:** P1 · **Status:** terverifikasi-kode.
- **Rekomendasi:** gedung gate memenuhi kebijakan hanya bila reader OUT `enabled` & sehat; selain itu kembali wajib
  cek muat handheld (K §10 opsi a: gate padam → SOP handheld).

---

## 5. Peta alur nyata vs maksud

| Tahap (maksud KN_16 / keputusan) | Nyata (runtime/kode) | Selisih | Jenis |
|---|---|---|---|
| SO `… → committed → picking → packed → shipped → delivered → invoiced` (KN_16 §2) | `reserved → (auto) approved → confirmed → partially_picked → picked → (partially_)shipped → done`; tidak ada `packed/invoiced` | penamaan & tahap | dokumen basi |
| Roll `committed → picked → packed → in_transit_sales → sold` (KN_16 §7) | `committed → in_transit_sales → delivered`; `picked/packed` tak pernah ditulis | `sold` ↔ `delivered`; tahap ambil tidak di roll | dokumen basi (FLW-OUT-8) |
| Pick mengikuti alokasi (KN_16 §4) | ambil desktop = pindai roll; HP/server menerima qty tanpa roll (B3b FRM-03); kirim sebagian memecah roll | identitas roll tidak dijamin | bug (STM-OUT-5) / belum diputuskan (K-B1-05) |
| Partial shipment → sisa backorder (KN_16 §2) | backorder tak terisi lagi sesudah kirim sebagian; SO macet | jalan buntu | bug (FLW-OUT-2) |
| Cut → remnant (BS) (KN_16 §2/§4) | sisa potong SO grade tetap, tanpa remnant; sampel ambang 2 | tidak terimplementasi | belum diputuskan (CUT-4) |
| Setiap perubahan stok = mutasi + nilai (KN_16 §1) | susut tanpa jurnal; POD tanpa mutasi; Ganti Roll tanpa mutasi pelepasan | buku besar tidak lengkap | bug (CUT-2) / B3a SCH-6 |
| Gate OUT memvalidasi SJ/transfer/makloon/perbaikan per trip (K-GDG-02) | bukti per trip ditulis; sesi tidak ditutup di batal/MKO; serah-terima Cutting & retur supplier & bahan R&D keluar tanpa dokumen gate | celah dokumen | bug (CUT-3, RFID-11) / belum diputuskan (SMP-02, PRT-12, SMP-08) |
| Stok transit boleh dijual (K-GDG-09) | transit transfer tidak dijual | keputusan tak berlaku | belum diputuskan (FLW-OUT-9) |
| Semua gedung dipakai bersama (K-GDG-07) | tugas per PT aktif; SRG-01 khusus Kanda | cakupan & data | belum diputuskan (FLW-OUT-1, RFID-10) |
| Simulasi tidak mengubah stok produksi (PREP-D2) | simulasi mati → klaim nyata; simulasi menyala di 3 PT nyata | jejak nyata dari uji | bug (RFID-1) / konfigurasi (RFID-9) |
| EPC tidak pernah dipakai ulang (K-OPN-05, PREP-F) | encode manual menerima EPC pensiun | identitas | bug (RFID-2) |
| Merah hanya pelanggaran nyata (K-RFID-09) | merah karena klaim simulator / `gate_exit` simulator lama | alarm palsu | bug (RFID-1, RFID-4) |

---

## 6. Daftar tugas keluar per peran (siapa melihat apa) — runtime

Hitungan pada DB uji (memuat data uji lama). PT = PT aktif bawaan akun.

| Akun (peran, lokasi) | HP `GET /wms/tasks` | Desktop `GET /outbound/tasks` | Catatan |
|---|---|---|---|
| warehouse@ (Jakarta) | 186: SO 109 · sampel 21 · **PO masuk 54** · makloon 2; 1 gudang; KSC saja; `dispatched 61 · cancelled 29 · completed 17` ikut | 130: SO 109 · sampel 21 | tugas RCM-RETUR SO KSC → 404 (benar) |
| warehouse.soreang (Kanda, Soreang) | 4 (Kanda) | 2 | handheld: 1 tugas `outbound_so` SRG-01 |
| warehouse.rancamalang (3 PT, Rancamalang) | 5, **hanya Cipta Sandang**; 3 gudang | 4 | tugas KSC di RCM-RETUR baru tampil sesudah `X-Entity-Id: ent_ksc` (FLW-OUT-1) |
| wh.admin (KSC+Kanda) | 260: PO 124 · SO 112 · sampel 22; **8 gudang** | 134; 5 gudang | |
| manager | 260 (sama wh.admin) | 134 | |
| salesadmin | **260** (sama wh.admin; termasuk tugas masuk PO) | 134 | peran non-gudang melihat seluruh antrean gudang |
| driver | 403 | 403 | aplikasi HP gudang tetap dibuka (B1 UI-23) |

Jenis tugas: satu koleksi `wms_tasks`, `flow_type` + `source_type` + `task_subtype: sample_cut`; potong SO bukan tugas
(antrean `pending-cuts`), transfer/makloon/perbaikan/retur bukan tugas WMS (layar sendiri) — B1 UI-09. Pindai per
dokumen: handheld C72 (`/api/handheld`, sesi per dokumen, batch idempoten) ✔; HP/desktop: per kode.

---

## 7. Pola kesalahan (10 teratas)

| # | Pola | Contoh (temuan / kandidat) |
|---|---|---|
| 1 | **Penulis tidak memeriksa status asal** (tanpa CAS atau filter hanya sub-dokumen) → dokumen terminal hidup lagi | STM-OUT-2 (tugas batal → `packing`), CUT-3 (serah-terima tugas batal), STM-OUT-6 (12 titik) |
| 2 | **Pelepasan/pembalikan "semua roll milik ref" tanpa saring status roll** → roll yang sudah keluar/habis hidup lagi | STM-OUT-1 (`in_transit_sales → available`), kandidat MKO-03 (`consumed → available`), PRT-03, POT-05 |
| 3 | **Daftar status hard-coded tidak lengkap/basi** | `ACTIVE` backorder (FLW-OUT-2), `_held` hanya `reserved` (STM-OUT-3), batal tanpa `draft` (STM-OUT-4), `SO_CLOSED_STATUSES` tanpa `expired/done` (TRF-01), Faktur `cancelled` vs `batal` (STM-OUT-7) |
| 4 | **Satu fakta dihormati di satu jalur, diabaikan di jalur lain** | panjang dipesan (CUT-1; R&D, MDQ), identitas roll (STM-OUT-5), nilai susut (CUT-2 vs MDQ) |
| 5 | **Uji/simulasi menulis jejak nyata** | RFID-1 (klaim), RFID-4 (`gate_exit` + alarm), RFID-3 (aktif tanpa bukti), RFID-9 (stok), simulate-tags di sesi berjalan (FLW-OUT-6) |
| 6 | **Batal = "langsung tersedia di asal"** tanpa bukti barang kembali | FLW-OUT-4 (sesudah ambil), FLW-OUT-11 (transfer di jalan, perbaikan dikirim), FLW-OUT-10 |
| 7 | **Penyelesaian per SO utuh, bukan per dokumen pengiriman** | POD per SO (FLW-OUT-2), cek muat per SO×gudang (kandidat ANOM-13), reservasi potong memblokir kirim (FLW-OUT-5) |
| 8 | **Cakupan = PT aktif, bukan gedung; pagar PT bolong di endpoint sekunder** | FLW-OUT-1, FLW-OUT-7, RFID-5, RFID-8 |
| 9 | **Kunci identitas lemah** | RFID-2 (EPC dipakai ulang + lookup tanpa status), STM-OUT-5 (anak tanpa tag), kandidat MKO-15 |
| 10 | **Penanda yatim/basi** | `allocations[].status`, roll `picked/packed`, `transfer_prior_status` basi, `completion_basis: actual_receipt` untuk 0 roll, `sample_payment_status: approved` sesudah batal (STM-OUT-7, FLW-OUT-10/11, CUT-6) |

---

## 8. Kandidat statik & yang dibantah

### 8.1 Kandidat statik (belum dijalankan; rincian di lampiran)

| ID lampiran | Ringkas | Perkiraan | Mengapa belum |
|---|---|---|---|
| MKO-03 | retur bahan MKO "semua" menghidupkan roll yang sudah dicatat susut: `consumed → available` panjang 0 (`stock_bucket_service.py:115-127` tanpa saring status — dicek ulang) | **P0** | prasyarat MKO lengkap |
| PRT-01/02 | retur QC ditolak: roll tetap `returned_supplier`; reverse mencari mutasi `type: return_out` padahal QC menulis `qc_reject_return` → 0 roll dipulihkan, jurnal & AP tetap dibalik (`purchase_return_service.py:996-999` — dicek ulang) | **P0** | prasyarat QC tolak |
| ANOM-06 | SO `approved`/`waiting_stock` ikut kedaluwarsa 3 hari, dipicu GET (STK-11), tanpa CAS | **P0** | butuh waktu/jam |
| POT-05 | rollback `reserve_specific_rolls` melepas SEMUA reservasi SO (termasuk anak potong), tanpa mutasi | **P0** | butuh balapan pemilihan roll |
| TRF-01 | roll transit tiba kembali `reserved` untuk SO `expired`/`done` | P1 | butuh SO kedaluwarsa |
| REP-01/02 | terima perbaikan: jurnal & roll ditulis sebelum CAS → ganda bila bersamaan | P1 | balapan |
| MKO-01/02/06/07/08/10 | issue/batal MKO tanpa CAS; batal dengan kiriman sebagian; `replace_one` menghapus bukti gate; sesi OUT tak ditutup | P1 | prasyarat MKO |
| PRT-03/05/08/12 | "barang kembali" tanpa cek status; transisi tanpa CAS; reverse ke `available` (bukan status asal); retur supplier tanpa SJ/gate | P1–P2 | prasyarat |
| SMP-03/07/08 | potong sampel di gudang lain mengubah gudang tugas; gudang cadangan = gudang pertama DB; bahan R&D keluar tanpa dokumen | P1–P2 | — |
| ANOM-07/18/19 | balapan batal ↔ kirim/ambil/POD | P1 | balapan |
| ANOM-09 | batal baris SO tidak menarik reservasi potong | P1 | jalur OD |
| ANOM-13 | cek muat mengharap semua roll SO di gudang → kirim sebagian wajib override | P2 | gudang `required` |
| ANOM-22 | gerbang bayar membaca `is_sample` yang tidak ada | P2 | sampel termin |
| ANOM-27 | eskalasi gudang tanpa notifikasi manajer | P2 | (konsisten runtime: 0 notifikasi) |
| G-06/G-08/G-15 | koreksi klaim tidak membalik transaksi; tutup sesi manual `wms.scan`; klaim antrean → lintasan berikutnya merah | P2 | — |
| P-01/P-04/P-05/P-06 | bukti EPC diketik; job kedua EPC sama; job antre untuk roll keluar; verifikasi dari EPC pensiun | P1 | protokol printer |
| H-02/H-03/H-06 | `once()` mengambil alih `processing` basi; niat tulis perangkat dicabut mengunci roll; potong sampel handheld di gudang lain | P1–P2 | — |

### 8.2 Dibantah / tidak terbukti oleh runtime

| Kandidat | Klaim statik | Hasil runtime |
|---|---|---|
| ANOM-10 | SO backorder murni bisa `confirmed` tanpa tugas | `confirm` pada `waiting_stock` → **409 `INVALID_TRANSITION`**; sesudah rencana pemenuhan SO kembali `reserved` (benar) |
| ANOM-17 | sales PT A bisa membuat SO di PT B lewat `entity_id` | **403** "Anda tidak berwenang menyimpan data ke CV Cipta Sandang Textile" |
| ANOM-11 | pindai roll sama berulang → kirim 409 permanen | ½ + ½ roll diterima, kirim **200** (bukan anomali bila ≤ panjang) |
| SCP-2/POT-08 (sebagian) | `scan-pick`/`dispatch` tanpa pagar lokasi | **404 "Data di luar lokasi tugas Anda"** untuk petugas Jakarta di RCM-RETUR |
| G-07 (daftar) | daftar antrean periksa bocor lintas lokasi | daftar tersaring lokasi; hanya ringkasan & notifikasi bocor (RFID-8) |
| G-02 | simulator merah mengunci gate nyata | `foreign_roll` → 409 `NO_DOCUMENT_ROLLS` (tidak terpicu); kunci di R2 berasal dari lintasan NYATA (RFID-1) |

---

## 9. Butir yang butuh keputusan pemilik (+ rekomendasi)

| ID | Pertanyaan | Rekomendasi B2b |
|---|---|---|
| K-B2b-01 | Eskalasi pada tugas yang sudah terkirim sebagian: boleh mengubah qty? | Hanya "tutup sisa"; roll di SJ tidak pernah disentuh (STM-OUT-1) |
| K-B2b-02 | Kirim sebagian: kapan roll dianggap sampai — per SJ (POD) atau per SO? Istilah `delivered` vs `sold`? | Per SJ; pakai `delivered`, perbarui KN_16/registry (FLW-OUT-2/8) |
| K-B2b-03 | Batal sesudah ambil / transfer di jalan / perbaikan dikirim: roll kembali bagaimana? | Status `returning` + tugas kembalikan ke rak / terima kembali (gate IN atau handheld) (FLW-OUT-4/11) |
| K-B2b-04 | K-GDG-09 untuk transfer: stok transit dijual? | Tidak, kecuali transfer ber-`sales_order_id`; ubah teks keputusan (FLW-OUT-9) |
| K-B2b-05 | Sisa potong → remnant/BS: ambang & grade; sama untuk SO & sampel? | Ambang per kategori, grade tetap sampai inspeksi; satu aturan (CUT-4) |
| K-B2b-06 | Susut potong dijurnal? | Ya — write-off seperti MDQ (CUT-2) |
| K-B2b-07 | Gedung Retur/inspeksi ikut alokasi otomatis SO reguler? | Tidak (kecuali grade diminta) (FLW-OUT-3) |
| K-B2b-08 | SRG-01 "khusus Kanda" vs K-GDG-07 "semua gedung bersama"? | Konfirmasi; samakan data master (RFID-10) |
| K-B2b-09 | Simulator di reader nyata & mode simulasi 3 PT nyata | Matikan mode simulasi PT nyata sebelum pilot; simulator hanya perangkat uji, tanpa klaim (RFID-1/9) |
| K-B2b-10 | Serah-terima Admin Cutting lintas gedung/site butuh dokumen & gate? | Ya — transfer internal (CUT-3, SMP-02) |
| K-B2b-11 | Cakupan daftar tugas fisik: per lokasi kerja semua PT? (= B3a #6, B1 K-B1-02) | Ya, dengan lencana PT (FLW-OUT-1) |
| K-B2b-12 | Reservasi 3 hari berlaku untuk SO `approved`/`waiting_stock`? | Tidak; kedaluwarsa hanya `reserved` belum disetujui, lewat penjadwal bukan GET (ANOM-06) |
| K-B2b-13 | `mark-printed` manual untuk label RFID? | Hanya label teks; RFID wajib bukti baca/verifikasi (RFID-3) |
| (lanjut) | K-B1-05 wajib pindai roll saat ambil | Ya (STM-OUT-5 menambah alasan) |

---

## 10. Silang ke paket lain
- **B3a:** SSOT-1 (63 penulis status roll → STM-OUT-6/7), SSOT-8 (jalur baru STM-OUT-4), DUP-4 (CUT-1), STK-11
  (ANOM-06), SCP-3 (FLW-OUT-1), SCH-6 (FLW-OUT-8, POD/Ganti Roll tanpa mutasi), SSOT-6 (RFID-4).
- **B3b:** FRM-03 (ambil tanpa roll — runtime: `scan-pick?actual_qty=0.01&roll_id=` 200), FRM-11 (cek muat manual),
  FRM-13 (RFID-4), LST-02 (Meja Cutting).
- **B1:** UI-08/09/10/11/41 (CUT-5, §6), UI-23 (RFID-7), UI-42 (RCM-RETUR → FLW-OUT-3).
- **B4:** §1.3 jenis tugas kelas satu, §1.6 sesi per dokumen (handheld C72 sudah; HP/desktop belum).
- **PREP-D2/Gelombang-2:** RFID-1/9/11/12 menyentuh keputusan "cek muat gedung bergate" & simulator.

---

## 11. Ringkasan

| Keparahan | Jumlah | Temuan |
|---|---:|---|
| **P0** | 6 | STM-OUT-1, STM-OUT-3, FLW-OUT-2, CUT-1, CUT-3, RFID-2 |
| **P1** | 15 | STM-OUT-2, STM-OUT-4, STM-OUT-5, STM-OUT-6, FLW-OUT-1, FLW-OUT-4, FLW-OUT-7, FLW-OUT-11, CUT-2, RFID-1, RFID-3, RFID-4, RFID-5, RFID-9, RFID-12 |
| **P2** | 13 | STM-OUT-7, FLW-OUT-3, FLW-OUT-5, FLW-OUT-6, FLW-OUT-9, FLW-OUT-10, CUT-4, CUT-5, CUT-6, RFID-6, RFID-8, RFID-10, RFID-11 |
| **P3** | 2 | FLW-OUT-8, RFID-7 |
| **Total** | **36** | 32 terverifikasi-runtime (FLW-OUT-7 sebagian) · 4 terverifikasi-kode (STM-OUT-6, STM-OUT-7, RFID-11, RFID-12) |

| Klasifikasi | Temuan |
|---|---|
| bug | STM-OUT-1/2/3/4/5/6, FLW-OUT-2/6/7/10, CUT-1/2/3, RFID-1/2/3/4/5/6/8/11/12 |
| butuh keputusan | FLW-OUT-1/3/5/9, CUT-4, RFID-9/10 |
| fitur belum ada | FLW-OUT-4/11 |
| inkonsistensi / dokumen basi | STM-OUT-7, FLW-OUT-8, CUT-5/6, RFID-7 |

**Cara mengulang** (stack sementara sesuai resep paket; kode disalin ke kontainer):
```bash
docker exec kn-tmp-b2b-be python /app/scripts/audit/b2b_flows.py happy anom01 anom02 anom03 anom08 anom11_12
docker exec kn-tmp-b2b-be python /app/scripts/audit/b2b_flows.py cancel cut backorder anom10_16 anom17
docker exec kn-tmp-b2b-be python /app/scripts/audit/b2b_flows2.py sample sord transfer transfer_cancel repair
docker exec kn-tmp-b2b-be sh -c "cd /app/backend && python /app/scripts/audit/b2b_rfid.py setup t01 p02 g03 g01 g07 handheld hh_batch g04 vis"
```
Skrip menulis DB uji (buat SO/transfer/RO/reader/handheld, ubah lalu pulihkan `wms.rfid_simulation` KSC) — hanya untuk
salinan DB. Keluaran `/tmp/b2b/*.json` (log panggilan + hasil). Sandi akun dibaca dari `/app/AGENTS.md`.

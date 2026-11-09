# B2a — Tabel transisi status alur BARANG MASUK, penyimpanan & opname

Lampiran dari [`B2a-ALUR-MASUK-OPNAME.md`](B2a-ALUR-MASUK-OPNAME.md). Disusun dari kode di `HEAD` worktree audit
(fast-forward `main` 9 Nov 2026, `8d4b6cd`) — **semua penulisan `status`/`stage`** pada dokumen alur masuk — lalu
dibuktikan dengan menjalankan alur lewat API di stack sementara `kn-tmp-b2a-*` (DB `test_database` = salinan
`kn_test_trial_2026-11-08`). Kolom **Bukti**: `J` = dijalankan & selisih DB dipotret (berkas `bukti-B2a/<skrip>.txt`),
`K` = dibaca dari kode saja (kandidat), `J+` = dijalankan dan **ditemukan menyimpang** (ID temuan disebut).

Singkatan penjaga: **CAS** = prasyarat status ada di filter tulis (atomik) · **klaim** = `atomic_claim.claim()`
(CAS + kunci saga) · **R→W** = status dicek di Python, tulis hanya `{id}` · **daftar-larang** = penjaga berbentuk
"status X dilarang" (status lain lolos).

Jumlah transisi diperiksa: **112** (PO-terima 7 · tugas masuk 13 · GRN 14 · roll masuk/journey 16 · SPK inspeksi 9 ·
PA 14 · transfer masuk 8 · retur terima 8 · opname 11 · pendaftaran awal 12). Dijalankan lewat API: **86** baris;
**34** baris menyimpang dari maksud (satu temuan bisa muncul di beberapa baris); **26** baris hanya dibaca dari kode.

---

## 1. Purchase Order — sisi penerimaan (`purchase_orders`)

| # | Dari → ke | Pemicu (endpoint · fungsi) | Penjaga | Efek | Bukti |
|---|---|---|---|---|---|
| 1 | — → `pending` + tugas masuk `waiting_goods` | `POST /purchase-orders` (`_create_inbound_tasks_for_po`, `routers/purchase_orders.py:138`) | approval matriks (tidak perlu di data uji) | 1 tugas per **produk** baris PO (dua baris produk sama → satu tugas, `:149-153`); gudang = gudang penerimaan lokasi | J (`f0_probe`) |
| 2 | `pending`/`receiving` → `receiving` | `complete_task` (`inbound_complete_service.py:468-487`) | CAS `status $nin terminal` | `items.$.received_qty += final_qty` (`$inc`), `received_rolls` R→W | J |
| 3 | `receiving` → `partial` / `completed` | `recompute_po_status` (`purchase_orders.py:78-125`) | R→W | `completed` bila semua baris ≥ qty×(1−toleransi); timeline | J (PO-00172 `partial` → `completed`) |
| 4 | `completed` → (tetap) `completed` padahal semua roll ditolak QC & diretur | SPK `tolak` + retur supplier | — | `received_qty` tidak dikurangi, tidak ada tugas sisa | **J+ FLW-IN-11** |
| 5 | `completed` → `received_qty` > qty PO | pindai-terima ulang tugas `qc_rejected` | **daftar-larang** di tugas | PO 50 yd → `received_qty` 101 | **J+ FLW-IN-01** |
| 6 | `pending`/`receiving`/`waiting_approval` → `cancelled` | `POST /purchase-orders/{id}/cancel` (`purchase_orders_extra.py:234-271`, tugas `update_many` `:268`) | CAS status; tolak bila tugas dipegang GRN aktif (KN-E06) | tugas non-terminal → `cancelled` (`update_many`); **roll `receiving` hasil pindai label tidak dibereskan** | **J+ FLW-IN-05**; J (tolak 409 saat GRN menghitung) |
| 7 | `partial` → batal | — | ditolak 400 (hanya lewat tutup-kurang) | — | K |

## 2. Tugas masuk WMS (`wms_tasks`, `flow_type=inbound`)

Status nyata: `waiting_goods → receiving → qc_check → (escalated ⇄) → qc_pending → completed | qc_rejected`, `cancelled`.
`put_away` ada di `stages`/`ACTIVE_TASK` dan dibaca 5 tempat tetapi **tidak pernah ditulis** (status mati).

| # | Dari → ke | Pemicu | Penjaga | Efek | Bukti |
|---|---|---|---|---|---|
| 8 | `waiting_goods` → `receiving` | `POST /inbound/tasks/{id}/scan-receive` (`inbound_receiving.py:130-131`) | **daftar-larang** `completed/cancelled` (`:66`), tulis `{id}` saja (R→W) | `received_qty` = nilai lama + qty (dibaca sebelum tulis) | J |
| 9 | `*` → `qc_check` bila `received ≥ expected` | idem `:134-136` | idem | **menimpa `escalated`, `qc_pending`, `qc_rejected`** | **J+ FLW-IN-01, FLW-IN-06** |
| 10 | `receiving/qc_check/qc_pending` → `escalated` | `POST …/escalate` (`:200-214`) | CAS `$nin completed/cancelled/escalated` + bukan GRN | jejak `escalation` | J |
| 11 | `escalated` → `pre_status` / `qc_check` | `POST …/resolve-escalation` (`:277-287`) | CAS `escalated` + belum resolved; izin `wms.approve` | `expected_qty` boleh diubah | K |
| 12 | `qc_check` → `qc_pending` (QC aktif) / `completed` (QC mati) | `POST …/complete` → `complete_task` | status ∈ `qc_check/put_away` (R→W) + klaim saga | roll lahir (`quarantine`/`available`), mutasi `inbound_receiving`, saldo, lot, **jurnal GR idempoten per tugas** (`gl_service.post_goods_receipt`), SPK otomatis (`ensure_inspection`) / draf PA (QC mati) | J; **J+ FLW-IN-01** (jurnal tidak ikut saat diulang) |
| 13 | `receiving` → `qc_pending` (lewat GRN, kiriman parsial sah) | `goods_receipt_close_service._post_task` | klaim + `via_grn` | tugas sisa dibuat `ensure_remainder_task` (sisa PO, `remainder_of`) | J (`fb_grn`: sisa 99 yd) |
| 14 | `qc_pending` → `completed` / `qc_rejected` | `process_qc_decision` (`qc_service.py:349-371`) via antrean (`/qc-decision`) atau tutup SPK | klaim prasyarat `qc_pending`; **roll DITAHAN → ditolak** (`:296-300`) | roll `available`/`damaged`/`returned_supplier`, saldo, backorder, **draf PA otomatis** | J; **J+ FLW-IN-03** |
| 15 | `qc_pending` + SPK terbuka → keputusan antrean | `/qc-decision` | 409 "ikut SPK" | — | J (`fd_hold`) |
| 16 | `qc_rejected` → `qc_check` → `qc_pending` | pindai-terima + selesai ulang dari HP | **tidak ada** | roll baru 51 yd + PO berlebih, **tanpa jurnal** | **J+ FLW-IN-01** |
| 17 | `escalated` → `qc_check` | pindai-terima saat eskalasi | **tidak ada** | eskalasi tetap `pending_review` | **J+ FLW-IN-06** |
| 18 | non-terminal → `cancelled` | batal PO (`update_many`) | — | roll `receiving` (pindai label) tertinggal | **J+ FLW-IN-05** |
| 19 | `legacy` ⇄ `grn` (mode PT) | `PUT /goods-receipts/mode` | admin/manajer | tugas lama `waiting_goods` (70 di KSC) beralih ke GRN; yang setengah jalan diberi `legacy_in_flight` | J |
| 20 | (GRN) klaim `grn_active_id` / lepas | `start_count` / `release_tasks` | CAS `grn_active_id` kosong | jalur lama ditolak 409 `GRN_MANAGED` | J |

## 3. Kedatangan Barang / GRN (`goods_receipts`)

| # | Dari → ke | Pemicu | Penjaga | Efek | Bukti |
|---|---|---|---|---|---|
| 21 | — → `draft` | `POST /goods-receipts` | satu PT aktif (bukan "Semua"); PO terbuka milik mitra; gudang = gudang PO | doc_refs ke PO, audit | J |
| 22 | `draft/review` + berkas | `POST …/files` | CAS versi | duplikat foto → peringatan | J |
| 23 | `draft` → `reading` → `review` / gagal | `POST …/read` (OCR) | `receiving.ocr_enabled` | data uji: OCR mati → 400 "Isi manual" | J |
| 24 | `draft` → `review` | `POST …/manual-entry` | CAS `draft` + izin `goods_receipt.review` (petugas gudang **ditolak**, peninjau mengisi) | — | J |
| 25 | `review` (baris/target/verifikasi) | `POST/PATCH …/lines` | CAS versi | konversi satuan SJ → satuan PO (`_convert`); **meter vs yard ditolak** (kebijakan `require_supplier_item_for_supplier_uom`) | J (FLW-IN-13) |
| 26 | `review` → `counting` | `POST …/start-count` | CAS + kunci unik `active_key` (PT·mitra·SJ·tahun) | klaim tugas; SJ sama di GRN lain → 409 `DN_DUPLICATE` | J |
| 27 | `counting` (roll `receiving` lahir) | `POST …/lines/{n}/rolls`, `…/scan-label` | CAS status | roll `receiving` **tidak masuk saldo** (tidak ada ember "receiving") | J |
| 28 | `counting` → `reconcile` | `POST …/finish-count` | CAS | selisih (`short_vs_dn`, `rolls_mismatch` … memblokir) | J |
| 29 | `reconcile` → `counting` | `POST …/reopen-count` | CAS | — | K |
| 30 | `reconcile` (selisih diputus) | `POST …/discrepancies/{key}/resolve` | CAS versi; `accept_note` tertentu butuh `approve` | klaim → notifikasi manajer; `reject_goods` → roll dibatalkan | K |
| 31 | `reconcile` → `closing` → `closed` | `POST …/close` | klaim; posting per tugas idempoten (`lines.posted`) | `complete_task(via_grn)`; tugas sisa | J |
| 32 | `closing` → `reconcile` | `POST …/return-to-reconcile` | hanya bila baris gagal posting | — | K |
| 33 | `review` → `rejected` | `POST …/reject` | CAS | `active_key` dicabut | K |
| 34 | `draft/reading/review/counting` → `cancelled` | `POST …/cancel` | CAS + ulangan aman (KN-E13) | roll `receiving` dihapus, tugas dilepas (kembali `waiting_goods`, `received_qty` 0) | J (`fg2` — **benar**) |

## 4. Roll masuk — status bucket & `journey.stage` (`inventory_rolls`)

| # | Dari → ke | Pemicu | Penjaga | Efek | Bukti |
|---|---|---|---|---|---|
| 35 | — → `receiving` (stage `receiving`) | pindai label (lama & GRN) / hitung GRN | idempoten per nomor roll supplier | belum di saldo | J |
| 36 | `receiving`/— → `quarantine` (QC aktif) / `available` | `complete_task` | klaim tugas | `bin_id` = bin roll **atau `task.bin_id` teks bebas**; `rfid_tag_id` = `task.roll_id` teks bebas (satu roll) | **J+ FLW-IN-08, OPN-01** |
| 37 | stage awal `received_transit` (gedung transit) / `stored` (gedung simpan/tunggal) | `inbound_qc_common.stage_for_roles` | — | gedung tunggal: tanpa PA | J (`fc_single`) |
| 38 | `quarantine` → `blocked` (+`hold{}`) | `POST /inventory/rolls/{id}/hold` | CAS status | keluar ATP; **keputusan QC terkunci** | J (`fd_hold`) |
| 39 | `blocked` → status sebelumnya | `POST …/release` (`wms.approve`) | CAS `blocked` | — | J |
| 40 | `quarantine` → `available` / `damaged` / `returned_supplier` | `process_qc_decision` | klaim tugas | grade QC/4-point, riwayat grade, nota retur (`pending_approval`) | J |
| 41 | `quarantine` (+`inspection.hold.held`) | MD Quality warna `tolak/beda_shade` & kebijakan `tahan` | — | tahan baris; tidak mengubah status roll | J (`fg_cancel` G3) |
| 42 | `quarantine` (+`qc_hold_pending`) → `blocked` saat lepas karantina | tutup SPK QC 4-point ber-baris tolak | — | — | K |
| 43 | `available` → `blocked` | tutup SPK QC 4-point (baris tolak) | — | grade B ditulis, roll ditahan | J (`fd2`) |
| 44 | stage `received_transit/tag_printed/gate_exception` → `label_verified` | `POST /putaway-orders/verify-labels` | **tidak memeriksa ada cetak label** | — | **J+ FLW-IN-17** |
| 45 | `label_verified/tag_verified` → `putaway_assigned` | terbit draf / buat PA | CAS klaim `active_movement` | keluar ATP | J |
| 46 | `available` → `in_transit_transfer` (stage `putaway_in_transit`) | `POST …/dispatch` | CAS per roll + kompensasi | saldo transit | J |
| 47 | `available/in_transit_transfer` → `available` di gudang tujuan, stage `stored` | trip tiba (`_land_items`) | CAS `active_movement.id` | `bin_id=None`, mutasi out/in id deterministik, tag pindah gudang | J |
| 48 | → stage `gate_exception` | tutup sisa `exception` / tujuan tak sah saat tiba | — | — | K |
| 49 | → stage asal terverifikasi (`inspection_site`) | tiba di gedung inspeksi | — | siap PA lagi sesudah SPK 4-point | K (routing dibuktikan J `fd2`) |
| 50 | `available` (bin kosong) → `available` + bin | `POST /inventory/putaway` → `place_roll` | evaluator bin + pembekuan + lokasi | mutasi `putaway` qty 0 | J |

## 5. SPK inspeksi (`inspections`: `po_receipt`, `qc_4point`, `return_customer`, …)

| # | Dari → ke | Pemicu | Penjaga | Efek | Bukti |
|---|---|---|---|---|---|
| 51 | — → `draft` | otomatis saat tugas `qc_pending` (`ensure_for_qc_task`, idempoten per tugas) | — | MD-only (`md_only`) untuk PO | J |
| 52 | `draft` → `assigned` | `POST /inspections/{id}/assign` | izin `inspection.assign` (petugas gudang **403**; admin gudang boleh) | notifikasi ke petugas | J |
| 53 | `assigned` → `in_progress` | `start` / baris QC pertama | — | — | J |
| 54 | baris diperiksa | `POST …/lines/{l}/inspect` | CAS status di filter (atomik per baris) | MD: warna/handfeel (tahan per kebijakan); QC: 4-point, grade | J |
| 55 | `assigned/in_progress` → `done` (+ putus karantina) | `POST …/finish` | sampling; B1 `peringatkan/blokir` (`inspection_service.py:1366-1376`) | `_release_quarantine` → `process_qc_decision`; **roll DITAHAN → 400** | **J+ FLW-IN-03** |
| 56 | `qc_4point` → `done` | `finish` | — | baris tolak → roll ditahan; draf PA bila ada yang lulus; **draf PA ke gedung inspeksi tidak dibereskan** | **J+ FLW-IN-12** |
| 57 | `done` → `assigned` | `reopen` | alasan ≥ 15 | — | K |
| 58 | `return_customer` `draft` → (tetap) | retur diinspeksi lewat `/sales-returns/{id}/inspect/complete` | — | SPK retur **menggantung `draft`** sesudah retur selesai | **J+ FLW-IN-09** |
| 59 | `draft…` → `closed` | `close_unneeded_return_spk` | — | — | K |

## 6. Perintah Putaway (`putaway_orders`)

| # | Dari → ke | Pemicu | Penjaga | Efek | Bukti |
|---|---|---|---|---|---|
| 60 | — → `draft` | `auto_draft` (keputusan QC / GRN tanpa QC / tutup SPK 4-point / tombol "Siapkan draf") | `_id` = hash pemicu (idempoten); 1 roll 1 antrean | tujuan = `choose_destination` + `_rank` | **J+ FLW-IN-02** (Woven → Knitting, 5 draf) |
| 61 | `draft` (ubah tujuan/isi) | `PATCH …/draft` | CAS `draft_rev`; lokasi hanya untuk gudang tujuan | — | J |
| 62 | `draft` → `open` | `POST …/publish` | klaim + CAS roll; roll belum siap → 400/409 atau `split_unready` | klaim `active_movement`, saldo | J; **J+ STM-IN-02** (petugas Jakarta) |
| 63 | `draft` → `cancelled` | `POST …/cancel-draft` | CAS `draft`, alasan ≥ 5 | kunci `_id` tetap → pemicu sama tidak melahirkan draf lagi | J |
| 64 | — → `open` | `POST /putaway-orders` (manual) | lokasi kedua gudang; aturan & identitas tag | klaim roll | K |
| 65 | `open` → `in_transit` | `POST …/dispatch` | klaim prasyarat `open` | roll `in_transit_transfer` | J; **J+ STM-IN-02** |
| 66 | `open` → `partially_received` (tanpa kirim) | `POST …/arrival-trips` | klaim prasyarat ARRIVAL (`open` termasuk) | `dispatched_at` kosong | **J+ FLW-IN-15** |
| 67 | `open/in_transit/partially_received` → `partially_received` / `completed` | trip (`confirm_arrival_trip`) | klaim; idempoten `client_trip_id`/`passage_id` | BTG pertama; EPC asing dicatat | J; **J+ FLW-IN-16** (ulang trip sesudah selesai → 400) |
| 68 | → `completed`/`completed_with_exception`/`exception`/`returned` | `POST …/close` (`return_transit`/`exception`) | klaim, alasan ≥ 10 | sisa kembali `label_verified` di asal | J |
| 69 | → selesai (konfirmasi lama) | `POST …/confirm-arrival` | klaim; `manual_all` butuh `approve` | yang tak terbaca → exception | K |
| 70 | item `exception` → `arrived` / `returned_transit` | `POST …/resolve-exception` | klaim **tanpa prasyarat status**, `accept` butuh `approve`; **tanpa cek pembekuan & lokasi** | `_land_items` | K (STM-IN-05) |
| 71 | (gate IN gedung bermode gate) trip | `gate_txn_service._putaway_in` → `confirm_arrival_trip` | kebijakan `effective_mode=gate` + perangkat tertaut; area beku → kuning tanpa transaksi | sama dengan #67 | K (D2: uji 11/11 milik paket D2) |
| 72 | status akhir → sesi dokumen gate ditutup | `gate_session_hook` | best-effort | roll tak terbaca → antrean periksa | K |
| 73 | `resolve-exception` → sesi gate | — | **tidak memanggil** `gate_session_hook` | — | K |

## 7. Transfer masuk (`warehouse_transfers`, sisi tujuan)

| # | Dari → ke | Pemicu | Penjaga | Efek | Bukti |
|---|---|---|---|---|---|
| 74 | `staging` → `dispatched` | `POST /transfers/{id}/status` | klaim | roll `in_transit_transfer` di gudang ASAL | J |
| 75 | `dispatched/partially_received` → `partially_received`/`completed` | `POST …/receive` → `transfer_receipt_service.receive` | CAS roll; status dok CAS `or t` (basi bila kalah) | roll tiba: `available` (atau status SO), `bin_id=None`, **journey tidak dihitung ulang**, mutasi `transfer_in`, tanpa draf PA | J; **J+ STM-IN-02** (petugas RCM menerima di Jakarta) |
| 76 | penerimaan diulang | idem | "already" | aman untuk stok; `receipt_events` bertambah | J |
| 77 | pengecualian `missing` → `resolved` (`return_to_source`) | `POST …/exceptions/{e}/resolve` | supervisor, alasan ≥ 5 | roll kembali `available` di asal | J |
| 78 | → `completed` padahal **0 roll diterima** | `_refresh_status` (`transfer_receipt_service.py:237-253`) | — | `completion_basis="actual_receipt"` | **J+ FLW-IN-10** |
| 79 | `dispatched` → `completed` manual | `/status completed` | 409 bila masih ada roll transit | — | K |
| 80 | roll → `damaged` / `hold` (pelanggaran aturan + override) | `receive` outcome | — | `hold` tanpa jalan keluar (beda dari `blocked`) | K (STM-IN-04) |
| 81 | gate IN transfer | `gate_txn_service._transfer_in` → `receive` | perangkat sebagai aktor, tanpa cek PT/lokasi pengguna | — | K |

## 8. Retur penjualan — terima barang (`sales_returns` + roll)

| # | Dari → ke | Pemicu | Penjaga | Efek | Bukti |
|---|---|---|---|---|---|
| 82 | pindai `received` di gudang | `POST /sales-returns/{id}/journey/scan` | CAS `journey_rev`; gudang `assert_usable` | **hanya `roll_locations`/`journey_events`; `inventory_rolls` tidak berubah** (roll tetap `delivered` di Jakarta) | **J+ FLW-IN-09** |
| 83 | `approved` → `inspecting` | `POST …/inspect/start` | R→W | SPK retur lama tetap `draft` | J |
| 84 | `inspecting` → `inspected` | `POST …/inspect/complete` | R→W | grade per item | J |
| 85 | `inspected` → `credit_settled` (+ restock) | `POST …/settle` | klaim | roll anak 2 yd `quarantine` di Gedung Retur, lot baru, **tanpa tag**, stage `received_transit` ditulis keras (`return_service.py:1122`), mutasi `return_quarantine_in`, jurnal | J |
| 86 | `quarantine` → `available` | `POST …/quarantine/release` | klaim dokumen; roll `{id}` | grade A diterima di Gedung Retur (aturan B/BS/C **tidak dicek**), **tanpa draf PA** | **J+ FLW-IN-09** |
| 87 | `quarantine` → `damaged` (scrap) | idem `scrap` | — | jurnal write-off kunci `roll_id` | K |
| 88 | settle → `cancelled` (reverse) | `POST …/reverse` | sebelum karantina dilepas | — | K |
| 89 | gate IN retur | — | gate hanya bukti (bukan transaksi) | — | K |

## 9. Opname (`cycle_count_sessions`, mode item & roll)

| # | Dari → ke | Pemicu | Penjaga | Efek | Bukti |
|---|---|---|---|---|---|
| 90 | — → `open` | `POST /cycle-count/sessions` | `assert_usable`; **tanpa cek lokasi** | tanpa nomor dokumen | J |
| 91 | `open` (+potret per roll) | `POST …/roll-scope` | CAS `open` & belum ada pindaian | **hanya roll ber-bin di cakupan** | **J+ OPN-02** |
| 92 | pindaian ditambah | `POST …/roll-scans` | CAS `open`; bin ∈ cakupan; **tanpa cek lokasi** | — | **J+ STM-IN-02** |
| 93 | hitung ulang roll hilang | `POST …/roll-missing-recount` | `open` | — | J |
| 94 | `open` → `approved` / `approved_with_exceptions` | `POST …/roll-finalize` | klaim; op per roll (lease+token) | hilang (dihitung ulang) → `consumed` + jurnal 5-9500/1-1300; asing → pindah bin; tak dikenal → roll baru (`cycle_count_found`); **tag RFID roll hilang tetap `active`** | J; **J+ OPN-03, OPN-04** |
| 95 | roll hilang tanpa hitung ulang | idem | — | tetap `available`, sesi terminal tanpa tindak lanjut | **J+ OPN-06** |
| 96 | ACC diulang | idem | 400 "tidak open" | — | J |
| 97 | (item) `open` → `submitted` | `POST …/submit` | **R→W** (`{id}` saja) | — | K |
| 98 | `submitted` → `approved` | `POST …/approve` | klaim | surplus roll id acak (tidak idempoten bila mati di tengah) | K |
| 99 | `submitted/rejected` → `open` | `POST …/reopen` | CAS status; **tanpa filter `mode`**, `$unset saga_lock` | sesi pendaftaran DITOLAK terbuka jadi opname | **J+ STM-IN-03** |
| 100 | item ditambah di bin beku | `POST …/items` | **tanpa cek pembekuan**, bin tidak divalidasi | — | **J+ OPN-05** |

## 10. Pendaftaran awal gedung (`cycle_count_sessions` mode `registration` + `initial_registration_lines`)

| # | Dari → ke | Pemicu | Penjaga | Efek | Bukti |
|---|---|---|---|---|---|
| 101 | — → `draft` | `POST /registration/sessions` | `assert_usable`; cakupan node | nomor `REG-` | J |
| 102 | `draft` → `running` (beku aktif) | `POST …/start` | CAS + cek irisan | `freeze.active`, bin beku | J |
| 103 | beku: `place_roll` ke bin beku | `/inventory/putaway` | `assert_movable` | 409 `REGISTRATION_FREEZE` | J (benar) |
| 104 | beku: terima PO jalur lama dgn bin beku | `scan-receive` + `complete` | **tidak ada kait** | roll lahir di bin beku | **J+ OPN-01** |
| 105 | baris lapangan → `draft` (`live`) | `POST …/lines` | EPC unik (indeks parsial); bin wajib di cakupan; roll lama dicocokkan **hanya yang lahir sebelum mulai** (`initial_registration_plan.py:62-64`) | baris "belum dikenali" **kehilangan qty** | **J+ OPN-01, OPN-07** |
| 106 | `running` → `pending_approval` | `POST …/submit` | CAS | biaya rata-rata dibekukan; **rak belum "selesai" tetap boleh** | **J+ OPN-07** |
| 107 | `pending_approval` → `running` | `POST …/return` | belum ada kelompok disetujui | beku tetap | K |
| 108 | pemetaan produk belum dikenali | `PATCH …/lines/{l}` (penyetuju) | `_line_actor` | — | J |
| 109 | `pending_approval` → `approved` | `POST …/approve` | klaim; langkah idempoten per kelompok | roll baru (`initial_registration`), roll lama dipakai ulang, 66/67 roll lama dihapus, 1 jurnal per kelompok, tag `pending_print`, area terverifikasi, beku dilepas | J; **J+ OPN-01** (stok ganda) |
| 110 | `draft/running/pending` → `rejected` | `POST …/reject` | CAS, belum ada kelompok | baris void, beku dilepas | J |
| 111 | `rejected` → `open` (!) | `/cycle-count/sessions/{id}/reopen` | **tanpa filter mode** | jadi opname per roll lewat `roll-scope` | **J+ STM-IN-03** |
| 112 | tag `pending_write` → `written` / `pending_print` → `active` | `POST …/lines/mark-written` | **tanpa cek status sesi** | — | K |

---

## Catatan pemetaan cepat (efek yang TIDAK terjadi padahal diharapkan)

| Dokumen / langkah | Diharapkan (maksud) | Nyata |
|---|---|---|
| Transfer tiba di gudang simpan | journey `stored` / draf PA bila gudang transit (K-GDG-10) | journey tidak diubah (data lama: `None`), tanpa draf, bin kosong |
| Retur lepas karantina | ke gudang simpan sesuai grade | tetap di gudang scan, `received_transit`, tanpa draf |
| Hasil makloon tanpa QC / hasil perbaikan | draf PA (setara GRN tanpa QC) | tidak ada (PREP-C §6 butir 2 sudah mengakui untuk makloon) |
| Opname hapus roll ber-tag | tag dicabut (setara pendaftaran awal) | tag tetap `active` |
| Tutup SPK 4-point sebelum PA inspeksi | draf PA inspeksi dibatalkan/dialihkan | draf tetap `draft` |

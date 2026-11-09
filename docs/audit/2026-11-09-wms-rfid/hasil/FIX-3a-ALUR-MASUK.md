# FIX-3a — Integritas alur BARANG MASUK, penyimpanan, opname & validasi input

- Tanggal: 9 Nov 2026 (WIB, selesai ±14.40) · Pelaksana: Claude Code (paket perbaikan FIX-3a) · Branch worktree
  `worktree-agent-aaa9b5a66c6fc4e05` (dasar `main` `92cc3c5` = gelombang 1–3 + FIX-2).
- Bahan: audit B2a (`B2a-ALUR-MASUK-OPNAME.md` + `B2a-TRANSISI-STATUS.md`), B3b (`B3b-FORM-INPUT-DAFTAR.md`), B3a
  (`B3a-SSOT-SKEMA-STOK.md` SSOT-1/3/7), keputusan koordinator FIX-3 bagian "Alur masuk & opname".
- Lingkungan uji: stack sementara `kn-tmp-fix3a-*` (salinan `kn_test_trial_2026-11-08`, dipulihkan sebelum tiap
  putaran), tanpa mount folder Windows, tanpa peramban. Stack bersama `kn-uji-*` & DB koordinator tidak disentuh.

---

## 1. Temuan yang ditutup (ID → perubahan → uji)

Uji baru: `backend/tests/test_fix3a_inbound_integrity.py` (28 uji) dan `frontend/src/features/__tests__/fix3aForms.test.js`
(5 uji). Kolom "Uji" menyebut nama fungsi uji.

### 1.1 P0
| ID | Perubahan | Uji |
|---|---|---|
| **B2a FLW-IN-01** | Tabel transisi tugas masuk baru `backend/services/inbound_task_state.py` (DAFTAR-IZIN + CAS). `scan-receive`, `scan-label`, `escalate`, `resolve-escalation`, `complete` memakai daftar-izin; status sesudah barang diposting (`qc_pending`/`qc_rejected`/`completed`) tidak bisa menerima/eskalasi lagi. Eskalasi data lama dari status terposting dipulihkan ke status itu (tidak ke `qc_check`). HP: kartu tugas berstatus QC tidak menampilkan Terima/Selesai. | `test_scan_receive_rejected_for_posted_or_escalated_task[qc_rejected/qc_pending/escalated/completed]`, `test_escalate_only_before_posting_and_reason_k14`, Jest "kartu HP …" |
| **B2a OPN-01 / STM-IN-01** | Kait pembekuan pendaftaran awal di jalur terima PO lama: `scan-receive` (bin di zona beku → 409) dan `complete_task` (gudang beku penuh atau bin beku → 409, sebelum klaim). Roll baru lahir TANPA bin lalu ditempatkan lewat evaluator tunggal `place_roll` (struktur, aturan, kapasitas, pembekuan). | `test_receipt_into_frozen_area_rejected` |
| **B3b INP-02** (+INP-01, INP-05, FLW-IN-08) | Bin = rujukan struktur gudang di server (`placement_rules.resolve_bin`, id **atau** kode rak → id kanonik, tak dikenal → 400) untuk opname per item, Scan Terima, stok awal; FE memakai `BinSelect` baru (`frontend/src/components/BinSelect.jsx`). Isian "Roll ID" tidak lagi menjadi `rfid_tag_id` (disimpan sebagai `supplier_roll_no`). Opname menampilkan kode bin. | `test_cycle_count_item_bin_resolved_and_frozen_area_rejected`, `test_scan_receive_bin_must_exist_and_is_canonicalised`, `test_complete_places_roll_via_evaluator_and_never_maps_roll_id_to_tag`, `test_initial_stock_validates_unit_grade_bin`, Jest "BinSelect …" |

### 1.2 P1
| ID | Perubahan | Uji |
|---|---|---|
| B2a FLW-IN-02 | `putaway_draft_service.is_specific` = ada daftar aturan TERISI (mode tanpa daftar bukan aturan spesifik); `_rank` & saran manual (`putaway_order_service.suggest`) memakai definisi yang sama; draf mencatat `destination_note` "tujuan dipilih menurut urutan kode gudang …" bila tidak ada aturan khusus. | `test_putaway_rank_ignores_mode_without_list` |
| B2a FLW-IN-03 (D3) | `qc_service.process_qc_decision`: roll DITAHAN tidak mengunci keputusan; roll lain diputuskan (peringatan), roll ditahan tetap `blocked`; `reject_held_roll_ids` menolak roll ditahan (tahanan dilepas berjejak → karantina → rusak/retur). Selama roll ditahan tersisa, tugas tetap `qc_pending` (`qc_status=partial_held`, riwayat `qc_decisions`, total akumulatif). SPK penerimaan (`inspection_service._release_quarantine`): roll ditahan boleh dipilih "tolak" pada "Diterima sebagian"/"Ditolak"; bila hanya roll ditahan tersisa, SPK boleh ditutup tanpa mutasi. | `test_qc_decision_with_held_roll_keeps_hold_and_allows_reject` |
| B2a FLW-IN-04 / B3b FRM-02 | Server: rencana `expected_rolls > 1` tanpa rincian roll (dan tanpa roll pindai label) → 400. HP: form Terima LENGKAP (satuan SJ + pratinjau konversi server, batch, lot, dye lot, grade master, Roll ID, bin) dan Selesai memakai form rincian roll desktop (`GRCatchWeightModal`: panjang/berat/dye/grade per roll + lot supplier + no. SJ). "Selesai" hanya di status yang diizinkan. | `test_complete_multi_roll_plan_requires_roll_details` |
| B2a FLW-IN-05 | `cancel_open_inbound_tasks` (dipakai batal PO **dan** tutup-kurang PO): roll `receiving` hasil pindai label dibatalkan seperti batal GRN (hapus, cabut tag, lepas klaim nomor supplier); hanya status sebelum posting yang dibatalkan (tugas `qc_pending` tidak lagi dibatalkan → karantina tidak yatim); batal PO ditolak 409 bila ada barang yang sudah diposting. | `test_cancel_po_undoes_receiving_rolls`, `test_po_cancel_refused_when_goods_posted_and_close_keeps_qc_pending` |
| B2a FLW-IN-06 | Sama dengan FLW-IN-01 (`escalated` di luar daftar-izin pindai-terima). | idem |
| B2a FLW-IN-09 (D6) | Retur jual: roll lepas karantina diarahkan sesuai grade (`return_service.route_released_return_rolls`): B/BS/C yang lolos aturan Gedung Retur → `stored` di sana; A / ditolak aturan → draf PA otomatis ke gudang simpan. SPK QC retur yang lahir otomatis ditutup saat retur diinspeksi lewat form retur. **D5 belum** (lihat §6). | `test_released_return_rolls_routed_by_grade` |
| B2a STM-IN-03 | Semua endpoint tulis opname biasa menolak sesi `mode=registration` (reopen pendaftaran ditolak lewat opname tidak bisa lagi). | `test_receipt_into_frozen_area_rejected` (bagian reopen) |
| B2a OPN-02 (D8) | Potret opname per roll cakupan SELURUH GEDUNG memuat roll tanpa bin & beralamat yatim sebagai "harus ditemukan"; cakupan zona melaporkan jumlah roll tanpa bin di luar cakupan. | `test_roll_snapshot_full_scope_includes_unbinned_rolls` |
| B2a OPN-03 | `stock_count_service.surplus_unit_cost`: rata-rata gudang → rata-rata pemilik → **`harga_pokok` master** (lalu field lama). Dipakai opname & pendaftaran awal. | `test_surplus_cost_falls_back_to_harga_pokok` |
| B3b INP-05 | Stok awal: satuan wajib satuan dasar produk atau terkonversi master (dikonversi), grade lewat `require_grade` (tolak "ZZ"), bin `resolve_bin` + pembekuan; FE grade dari master (opsi "Reject" hilang), panjang/HPP/berat `DecimalInput`, pemilih bin. | `test_initial_stock_validates_unit_grade_bin` |
| B3b INP-09 | `resolve-escalation`: `adjusted_qty` lewat `require_qty` (> 0, berhingga) — -10 ditolak 400. | `test_escalate_only_before_posting_and_reason_k14` |
| B3b INP-10 | Koma desimal Indonesia: `POReceiveItem.actual_qty/doc_qty`, `RollPayload.quantity/unit_cost/weight_kg` (QtyDecimal/MoneyDecimal); FE `ReceiveUomPanel` (DecimalInput), `useReceivingUom`, Scan Terima desktop, packing list GRN (`GrnLineRow`), lembar inspect 4-point (`InspectSheetGrid`), terima hasil makloon (`MkoStepModals`), Daftar Awal HP. | `test_initial_stock_validates_unit_grade_bin` ("12,5") |
| B3b FRM-10/12/13 (K-B3b-09) | PA "Simulasi Scan Semua": server hanya saat `wms.rfid_simulation` aktif untuk PT pemilik PA (403 di luar itu), hasil bertanda `arrived_via=simulated` + `simulated{}` (bukan "gate-in scan"); FE menampilkan tombol hanya bila `rfid_simulation` PA true. Perangkat RFID baru lahir `offline` tanpa detak; "Nyalakan" manual = detak SIMULASI (`heartbeat_source=simulated`) hanya di mode simulasi. "Simulasi Pindai Area" hanya di mode simulasi; bacaan `simulated:true` tanpa mengubah `last_seen_*` tag. | `test_new_device_has_no_fake_heartbeat`, Jest "Simulasi Scan Semua …" |
| B3b FRM-19 | Registri setelan: `value_format` baru (`regex` = tiap butir dikompilasi; `json_map` = teks objek JSON) untuk `receiving.client_po_patterns` & `receiving.ocr_price_table`; `ocr_max_pages` 1–50. Konsumen tahan data lama rusak (`ocr_config` tidak lagi 500 → peringatan `config_warnings`; `dn_rules.po_cores` melewati pola rusak). FE: daftar pola regex = satu butir per baris. | `test_config_regex_and_json_validated_and_ocr_config_robust`, Jest "daftar pola regex …" |
| B3b FRM-09 / K-14 (K-B3b-03) | Validator bersama baru `backend/input_rules.py`: `ReasonStr`/`OptReasonStr` (model, 422) dan `require_reason`/`optional_reason` (query/dict, 400) — **dihitung HURUF** ("....." / 5 spasi / "12345" ditolak), plus `PosQty`/`NonNegQty`/`require_qty` dan `KNIn` (`extra="forbid"`). Diterapkan: eskalasi & catatan penyelesaian eskalasi masuk, QC tolak barang, tolak/selisih GRN & ganti mode penerimaan, tutup-kurang PO, tolak/kembalikan/setujui pendaftaran awal + setujui hitungan, tolak opname (setujui: opsional tetapi bila diisi ≥ 5 huruf, tanpa teks bawaan), finalisasi opname per roll, batal draf PA, pengecualian PA. | `test_reason_validator_counts_letters`, `test_grn_reject_reason_spaces_rejected_by_model`, `test_escalate_…`, `test_cycle_count_…` (tolak "....." 422) |
| INP-13 (sebagian) | `extra="forbid"` (`KNIn`) untuk semua body opname (10 model) & pendaftaran awal (8 model) + body eskalasi baru. Klien web/HP/C72 sudah dicek hanya mengirim kunci yang dikenal. | regresi `test_prep_b/g`, `test_l10_*` hijau |
| numeric_bounds (G-NUM-02) | `scripts/guardrails/verify_numeric_bounds.py` diperluas: model di router & parameter query numerik pada endpoint tulis untuk router cakupan FIX-3a (`ROUTER_SCOPE`); penjaga runtime `require_qty` diakui. Area FIX-3a bersih (HARD tetap 3 lama di `SoOverrideLineIn`). | guardrail |

### 1.3 P2/P3
| ID | Perubahan | Uji |
|---|---|---|
| B2a FLW-IN-10 (D10) | Transfer: tidak ada roll transit, 0 diterima, ≥1 kembali ke asal → `returned` (`completion_basis=all_returned`), sesi gate ditutup; label FE "Dikembalikan". | `test_transfer_all_returned_status_returned` |
| B2a STM-IN-04 | "Diterima ditahan" transfer → `blocked` + `hold{held, prev_status=available, source=transfer_rule}` (satu representasi tahan; dilepas lewat Lepas Tahanan). | `test_transfer_land_hold_uses_blocked_and_recomputes_journey` |
| B2a FLW-IN-19 | Tiba transfer: `journey.stage` dihitung ulang sesuai peran gudang tujuan; roll tersedia yang tiba di gedung transit → draf PA otomatis. | idem |
| B2a FLW-IN-12 | Tutup SPK QC 4-point melepas draf PA `purpose=inspection` roll-nya (draf kosong dibatalkan) sebelum draf simpan dibuat; "Diterima sebagian" 4-point dengan SEMUA baris diperiksa ditolak → 400 "pilih Ditolak". | (kode; regresi `test_p05_*`, `test_prep_c_*` hijau) |
| B2a FLW-IN-13 (D4) | `receiving_uom_service.is_fixed_pair`: konversi BAKU (panjang↔panjang, berat↔berat dari master satuan) sah tanpa barang supplier; jejak "konversi baku master satuan (tanpa barang supplier — D4)". Berlaku juga untuk baris SJ GRN. | `test_fixed_pair_conversion_allowed_without_supplier_item` |
| B2a FLW-IN-15 (D7) | Trip tiba pertama mengisi `dispatched_at` (+`dispatch_implicit`) bila PA belum "Kirim". | (kode) |
| B2a FLW-IN-16 | Trip duplikat (passage_id/client_trip_id sama) dijawab duplikat idempoten SEBELUM cek status (PA selesai tidak lagi 400). | `test_arrival_trip_duplicate_after_completion_is_idempotent` |
| B2a FLW-IN-17 | Verifikasi label: roll tanpa catatan `roll_label_prints` tetap diverifikasi tetapi ditandai `journey.label_print_evidence=none` + daftar `without_print_record` di respons. | (kode) |
| B2a FLW-IN-18 | Hasil makloon langkah terakhir TANPA QC → draf PA otomatis (setara GRN tanpa QC). Perbaikan (repair) belum. | (kode) |
| B2a FLW-IN-21 | Pesan PO ke lokasi yang gudangnya khusus PT lain kini menyebut penyebabnya (gudang dedicated), bukan "belum punya gudang penerimaan". | (kode) |
| B2a STM-IN-05 | `resolve-exception` PA: alasan K-14 wajib, kait pembekuan, klaim BERPRASYARAT (PA bukan draf/batal & roll target masih `exception`, dokumen dibaca dari klaim), sesi gate ditutup bila PA final. | `test_prep_c_*` (disesuaikan) |
| B2a STM-IN-06 | CAS `received_qty` seperti dibaca + status asal pada pindai-terima → 409 untuk penulis yang kalah. | (kode) |
| B2a STM-IN-07 (sebagian) | `status_history` bentuk SSOT (`services/status_history.py`) ditulis pada setiap transisi tugas masuk (termasuk keputusan QC & batal PO) dan transfer masuk. | `test_escalate_…`, `test_complete_places_…`, `test_transfer_all_returned_…` |
| B2a OPN-04 | Roll keluar stok lewat opname (hapus hilang / qty jadi 0 / kurang opname biasa): tag RFID hidup dicabut (`retire_tags_of_roll`). | `test_opname_write_off_retires_tag` |
| B2a OPN-05 | Opname biasa (item level gudang/bin, setujui) & opname per roll (scope, finalisasi) tunduk pembekuan (`registration_freeze.assert_count_scope`). | `test_cycle_count_item_bin_resolved_and_frozen_area_rejected` |
| B2a OPN-06 | ACC per roll dengan roll hilang belum dihitung ulang → sesi turunan "Hitung ulang — …" (`open`, `mode=roll`, `parent_session_id`, daftar harus-ditemukan = roll itu). | (kode; regresi `test_l10_*` hijau) |
| B2a OPN-07 | Diverifikasi: qty baris "produk belum dikenali" tersimpan di `qty_input` dan dipakai saat dipetakan (uji lama `test_prep_b` memeriksa qty 10); peringatan "rak belum selesai" sudah ada di layar Ajukan. Tidak diubah. | `test_prep_b_initial_registration` |
| Opname `submit` | CAS `status=open` (dulu tulis `{id}` saja). | (kode) |
| B3a keputusan 8 / SSOT-7 | `POST /inventory/initial-stock` → **410** `INITIAL_STOCK_CLOSED` bila gedung punya sesi pendaftaran awal (status apa pun). | `test_receipt_into_frozen_area_rejected` |
| Persetujuan pendaftaran awal dua langkah | Setelan `registration.finance_approval` (bawaan **AKTIF**, global/PT). Langkah 1 `POST /registration/sessions/{id}/approve-count` (izin `inventory.approve_count`) → `registration.count_approval`, baris terkunci, baris "belum dikenali" wajib dipetakan dulu. Langkah 2 `POST …/approve` (izin baru **`inventory.approve_value`**: Finance, Manajer, Admin; orang **berbeda** dari penyetuju hitungan) → roll lama dihapus & jurnal diposting. "Kembalikan" (gudang atau Finance) mencabut persetujuan hitungan. Detail sesi: `approval_step` (count/finance/single), FE langkah 1/2. Finance boleh MEMBACA sesi & rekonsiliasi. | `test_registration_two_step_finance_gate`, `test_prep_b_initial_registration::test_main_flow` (disesuaikan), Jest "pendaftaran awal dua langkah …" |

## 2. Keputusan koordinator yang diterapkan
D3 ✔ · D4 ✔ · D6 ✔ (D5 belum — §6) · D7 ✔ · D8 ✔ · D10 ✔ · D2 belum (§6) · D9 ditunda (sesuai keputusan) · persetujuan
dua langkah ✔ · K-B3b-03 ✔ (huruf, satu validator server) · K-B3b-06 ✔ (PT per baris di Daftar Awal HP) · K-B3b-09 ✔
(PA, detak perangkat, pindai area) · B3a keputusan 8 ✔.

## 3. Perubahan perilaku untuk pengguna
1. **Tugas barang masuk** yang sudah masuk karantina/QC/selesai, atau sedang dieskalasi, tidak bisa "Terima" lagi (400)
   dan tidak bisa dieskalasi (409). Kartu HP menampilkan keterangan, bukan tombol.
2. **Bin** di Scan Terima, opname per item, dan stok awal dipilih dari daftar bin gudang; kode/id tak dikenal ditolak.
   Saat "Selesai", bin isian dipasang lewat aturan penempatan — roll karantina (QC aktif) ke bin simpan biasa DITOLAK
   aturan (hanya area QC) sehingga roll masuk antrean Penempatan Rak dengan peringatan `placement_warnings`.
3. **Rencana > 1 roll** wajib rincian per roll saat Selesai (HP & desktop); HP kini memakai form rincian roll yang sama
   dengan desktop.
4. **Area beku pendaftaran awal**: terima PO jalur lama ke bin beku/gudang beku penuh, opname biasa & per roll di area
   beku, pengecualian PA → 409 `REGISTRATION_FREEZE`. *Termasuk "Tutup" GRN ke gudang yang dibekukan PENUH* (konsisten
   dengan terima transfer/PA; zona beku tetap menerima GRN tanpa bin).
5. **Keputusan QC** dengan roll ditahan: roll lain diputus, roll ditahan tetap ditahan (peringatan); tugas tetap
   "Menunggu QC" sampai roll itu dilepas/ditolak. Roll ditahan boleh ditandai "tolak".
6. **Batal PO** ditolak bila sebagian barang sudah di karantina/stok (pakai Tutup kurang terima); batal/tutup-kurang
   membatalkan roll hasil pindai label yang belum masuk stok.
7. **Alasan K-14** (≥ 5 huruf) diwajibkan server di jalur yang disebut §1.2; "....."/spasi ditolak. Tolak opname wajib
   alasan; setujui opname tanpa teks bawaan.
8. **Pendaftaran awal**: dua langkah (gudang → Finance, orang berbeda). Admin/Manajer bisa menjadi penyetuju nilai.
   Stok awal manual ditutup (410) untuk gedung yang memakai pendaftaran awal.
9. **Simulasi** (PA scan semua, nyalakan perangkat, pindai area) hanya saat Mode simulasi RFID aktif untuk PT; perangkat
   baru tampil "offline" sampai mengirim detak.
10. **Transfer** 0 diterima → "Dikembalikan"; diterima ditahan → status ditahan baku (bisa "Lepas tahanan").
11. **Draf PA**: tujuan tanpa aturan khusus diberi catatan "dipilih menurut urutan kode gudang"; draf PA juga lahir
    sesudah tiba transfer di gedung transit, hasil makloon tanpa QC, dan roll retur grade A yang lepas karantina.
12. **Setelan** pola PO klien (regex) disunting satu baris per pola; regex/JSON tak sah ditolak saat disimpan.
13. **Koma desimal** ("12,5") diterima di isian qty penerimaan, stok awal, packing list GRN, lembar inspect, terima makloon.
14. Opname per roll seluruh gedung kini juga mengharapkan roll tanpa bin; ACC dengan roll hilang belum dihitung ulang
    membuat sesi turunan "Hitung ulang".

## 4. Keputusan implementer (beserta alasan)
1. Daftar-izin `scan_receive` = `waiting_goods · receiving · qc_check` (bukan hanya dua status yang disarankan audit):
   `qc_check` = barang belum diposting, menerima tambahan dalam toleransi tetap sah; yang dicegah adalah status
   SESUDAH posting.
2. Eskalasi di luar daftar-izin dijawab **409** (kontrak lama KN-C01 yang diuji `test_kn_c01_*`), pindai-terima **400**
   (kontrak lama).
3. Bin isian penerimaan tidak lagi ditulis langsung ke roll; roll lahir tanpa bin lalu `place_roll`. Gagal aturan →
   peringatan, bukan menolak penerimaan (barang fisik sudah datang; tidak boleh macet karena bin).
4. "Roll ID" isian disimpan ke `supplier_roll_no` (roll tunggal) — field yang sudah ada & dipakai pencocokan.
5. Persetujuan dua langkah memakai SUB-langkah di `pending_approval` (`registration.count_approval`), bukan status baru
   — pembaca status lama (layar, HP, C72, guardrail) tidak berubah; pemisahan orang (SoD) ditegakkan server. Izin baru
   `inventory.approve_value` (bukan meminjam izin akuntansi) supaya Finance tidak mendapat hak stok lain;
   `sync_permission_modules` menambahkannya ke matriks tersimpan saat start.
6. Stok awal ditutup per GEDUNG yang punya sesi pendaftaran (status apa pun, termasuk ditolak) — tafsir "sesudah mode
   pendaftaran awal dipakai".
7. Approve opname: alasan opsional (bila diisi ≥ 5 huruf), tolak wajib — menjaga klien lama (`ApprovalDecisionModal`,
   uji lama `json={}`) sambil menghapus teks bawaan.
8. Detak perangkat & pindai area simulasi memakai mode simulasi **PT aktif pengguna** (perangkat milik gudang, bukan PT).
9. Data FRM-12/13: tombol FE disembunyikan bila mode simulasi mati (endpoint `GET /rfid/devices` kini memuat
   `rfid_simulation`).
10. `extra="forbid"` hanya untuk body opname/pendaftaran/eskalasi (kliennya diperiksa). `POReceiveItem`/
    `GRCompletePayload` belum (banyak klien & uji lama) — dicatat sisa.

## 5. Tabel transisi status yang disentuh

### 5.1 Tugas barang masuk (`wms_tasks`, `flow_type=inbound`) — `backend/services/inbound_task_state.py` (BARU)
Satu tabel `TRANSITIONS` (daftar-izin) + `assert_can()` + `transition()` (CAS: filter = id + status asal ∈ daftar-izin,
jejak `status_history` bentuk SSOT bila status berganti).

| Aksi | Dari (daftar-izin) | Ke | Pemakai |
|---|---|---|---|
| `scan_receive` | waiting_goods · receiving · qc_check | receiving · qc_check | `POST /inbound/tasks/{id}/scan-receive` (CAS + `received_qty` lama) |
| `scan_label` | waiting_goods · receiving · qc_check | receiving · qc_check | `POST …/scan-label` (penjaga rute; CAS di `receiving_roll_service` tetap) |
| `escalate` | waiting_goods · receiving · qc_check | escalated | `POST …/escalate` |
| `resolve_escalation` | escalated | waiting_goods · receiving · qc_check (+ qc_pending/qc_rejected/completed hanya memulihkan eskalasi data lama) | `POST …/resolve-escalation` |
| `complete` | qc_check · put_away | qc_pending · completed | `complete_task` (klaim saga berprasyarat sama) |
| `complete_grn` | qc_check · put_away · receiving | qc_pending · completed | `complete_task(via_grn)` |
| `qc_decision` | qc_pending | completed · qc_rejected · qc_pending (sebagian: roll ditahan tersisa) | `qc_service.process_qc_decision` |
| `cancel` | waiting_goods · receiving · qc_check · escalated | cancelled | `purchase_orders_extra.cancel_open_inbound_tasks` (batal & tutup-kurang PO) |

Belum dirapikan: `put_away` tetap status mati; `goods_receipt_*` (`release_tasks`, `ensure_remainder_task`) dan
`makloon_receipt_qc` menulis status tugas sendiri (CAS masing-masing) — kandidat dipindah ke tabel ini.

### 5.2 Transfer masuk (`warehouse_transfers`) — `transfer_receipt_service._refresh_status`
| Dari | Ke | Syarat |
|---|---|---|
| dispatched · partially_received | partially_received | masih ada roll transit & ≥1 diterima |
| dispatched · partially_received | completed | tidak ada roll transit & ≥1 diterima (`actual_receipt`) |
| dispatched · partially_received | **returned** (baru) | tidak ada roll transit, 0 diterima, ≥1 kembali ke asal (`all_returned`) |
CAS status asal dipertahankan; `status_history` ditulis saat berganti; sesi gate ditutup untuk `completed`/`returned`.

### 5.3 Roll (`inventory_rolls.status`) — titik yang disentuh
| Titik | Sebelum | Sesudah |
|---|---|---|
| Terima transfer "diterima ditahan" | `hold` (tanpa jalan keluar) | `blocked` + `hold{held, prev_status, source=transfer_rule}` |
| Keputusan QC, roll ditahan ditolak | 400, keputusan terkunci | `blocked` → `quarantine` (jejak `hold_history`) → `damaged`/`returned_supplier` |
| Selesai terima dengan bin isian | lahir ber-bin teks bebas | lahir tanpa bin → `place_roll` / antrean Penempatan Rak |
B3a SSOT-1 (63 penulis status roll tanpa tabel) belum dirapikan menyeluruh — di luar batas paket.

### 5.4 Opname & pendaftaran awal (`cycle_count_sessions`)
| Dokumen | Perubahan |
|---|---|
| Opname biasa `submit` | CAS `status=open` |
| Opname biasa (endpoint tulis) | menolak `mode=registration` |
| Opname per roll `roll-finalize` | roll hilang tanpa hitung ulang → sesi turunan `open/mode=roll` |
| Pendaftaran `pending_approval` | sub-langkah `count_approval` (gudang) → nilai & jurnal (Finance, orang berbeda); "Kembalikan" mencabutnya |

## 6. Hasil uji & perbandingan regresi
(lihat §6.1–6.4 — angka apa adanya)

### 6.1 Uji baru
| | dasar `main` | FIX-3a |
|---|---:|---:|
| `test_fix3a_inbound_integrity.py` (28) | **27 gagal**, 1 lulus (kontrol `[completed]` — sudah dicegah daftar-larang lama) | **28 lulus** |
| Jest `fix3aForms.test.js` (5) | lihat §6.3 | lihat §6.3 |

### 6.2 Pytest — 46 berkas lama (urutan sama, DB dipulihkan sebelum tiap putaran)
`test_inbound_complete_characterization`, `test_grn_phase0/2/3_endpoints/4_dn_rules/4_eval/5/6/7`, `test_fase_sl_*` (4),
`test_f14_spk_one_decision`, `test_gelombang1_gl_integrity`, `test_p02_wms_putaway`, `test_p03_transfer_receipt`,
`test_p05_imp16_md_quality_qc`, `test_p19_roll_hold_release`, `test_prep_b/c/g`, `test_prep_integrasi_freeze_putaway`,
`test_iter264_putaway_fixes`, `test_f11_f12_return_receipt_qc`, `test_return_spk_per_roll`, `test_transfer_status_guard`,
`test_wms_advance_expected`, `test_l10_ln101_roll_count`, `test_aud_wms_01`, `test_iter314_saga_and_reopen`,
`test_kn_audit_2026_09_21_extended`, `test_iter266_r6_cc_r7`, `test_l10_t1_review`, `test_iter258_purchase_e2e_and_recon`,
`test_uat23_retur_keputusan`, `test_ln091t02_ln093_chain`, `test_phase4_r6`, `test_p03_damaged_shortnote_fix`,
`test_iter108_regression`, `test_iter255_t1_t8`, `test_review_iter89_features`, `test_iter317_completion_targets`,
`test_uat24_f3`, `test_trial_22okt_flow`, `test_ln014_lot_identity`, `test_saga_lock_registry`.

| | dasar `main` | FIX-3a (putaran akhir) |
|---|---:|---:|
| gagal/error | 114 | **114** (himpunan identik) |
| hanya gagal di FIX-3a | — | **0** |
| `test_iter117_p09` (proses terpisah) | 18 lulus | 18 lulus |
| `test_iter118_p10` (proses terpisah) | 8 lulus | 8 lulus (sesudah penyesuaian) |

Putaran pertama FIX-3a menghasilkan 4 uji yang hanya gagal di FIX-3a; semuanya ditangani:
* `test_kn_audit_2026_09_21_extended::test_kn_c01_inbound_escalate_bad_status` — alasan "TEST" (4 huruf) dinilai
  sebelum status → **kode diperbaiki**: status dinilai dulu, 409 (kontrak KN-C01).
* `test_prep_b_initial_registration::test_main_flow` — uji mengunci persetujuan satu langkah → **uji disesuaikan** ke
  dua langkah (langkah 1 admin, langkah 2 manajer; diuji juga: approve sebelum langkah 1 → 400, orang sama → 403, baris
  terkunci → 409).
* `test_prep_c_warehouse_putaway::test_confirm_arrival_trip_from_gate_service` — uji mengunci perilaku FLW-IN-16 (trip
  sama sesudah selesai → error) → **uji disesuaikan**: trip sama = duplikat idempoten; lintasan BARU ke PA selesai
  tetap ditolak.
* `test_prep_c_warehouse_putaway::test_zero_arrival_never_completed_and_accept_needs_approve` — pengecualian PA tanpa
  alasan → **uji disesuaikan** (alasan K-14; tanpa alasan → 400 juga diuji).
* `test_iter118_p10` memakai bin teks bebas "binA…binD" yang tidak ada di struktur `wh_jakarta` (persis INP-02) → **uji
  disesuaikan** memakai 4 bin nyata gudang itu (produk uji unik, expected tetap roll uji saja).

Gagal lama (sama persis di dasar & FIX-3a) berasal dari data acuan/asumsi uji lama (mis. `test_fase_sl_scan_label` 17,
`test_iter266_r6_cc_r7` 21, `test_p03_transfer_receipt` 11 error setup) — tidak disentuh.

### 6.3 Jest & ESLint
(diisi di bawah — §6.3a)

### 6.4 Guardrail (`PYTHONUTF8=1 python scripts/guardrails/verify_*.py`, host; `verify_state_machine` tidak dijalankan)
Kode keluar 40 guardrail **identik** dasar vs FIX-3a. Jumlah pelanggaran tidak naik:
* `verify_atomic_claim` 6 → 6 (putaran awal 7: `resolve-escalation` tercatat CAS tetapi pola baru tidak dikenali +
  `scan-receive`/`escalate` jadi multi-koleksi → **guardrail dilatih** mengenali `_its.transition(` sebagai CAS & dua
  endpoint dicatat di `REVIEWED`; "BELUM DITINJAU" 76 = 76; self-test merah 2 = sama dengan dasar).
* `verify_numeric_bounds` HARD 3 = 3 (lama, `SoOverrideLineIn`), cek 151 → 148 (field yang kini `QtyDecimal` tidak
  dihitung pola lama) + cakupan baru router FIX-3a bersih.
* `verify_auth_coverage` 28 = 28 (1.721 → 1.722 cek: endpoint `approve-count`), `verify_qty_dual` 28 = 28,
  `verify_entity_label` 1 = 1, `verify_line_scope` 1 = 1, `verify_to_list_bound` 20 = 20, `verify_no_secrets` 8 = 8.
* Hijau tetap hijau: `status_history` (9 cek), `codebase_map`, `knselect_contract`, `uom_vocab`, `role_label`,
  `escape_layers`, `rfid_tag_unique`, `roll_identity`, dll.

## 7. Skrip perbaikan data (dibuat, dry-run bawaan; diuji di salinan)
`scripts/fix_data_2026_11_09_fix3a_alur_masuk.py --db kn_test_trial [--apply]` (menolak DB lain). Hasil di salinan
`kn_test_trial_2026-11-08` (stack sementara):
| Langkah | Dry-run | Sesudah `--apply` (dry-run ulang) |
|---|---:|---:|
| `transfer_returned` (D10) | 0 | 0 |
| `transfer_hold` → blocked | 0 | 0 |
| `fake_tag_ref` — `rfid_tag_id` teks isian "Roll ID" (mis. `DM-9A129A-020`, `F14-48C98C-00`) → `supplier_roll_no` | **3** | 0 |
| `opname_dead_tags` (tag hidup pada roll yang dihapus opname) | 0 (+3 tag hidup pada roll habis karena sebab lain — hanya dilaporkan, wilayah FIX-3b/RFID-2) | 0 |
| `escalation_posted` | 0 | 0 |
| `over_received_report` (laporan PO berlebih) | 0 | — |
Idempoten (putaran ulang 0); jejak di `migrations` (`fix_data_2026_11_09_fix3a_alur_masuk`). **Tidak** dijalankan ke DB
bersama.

## 8. Berkas berisiko bentrok
* **FIX-1 (cakupan akses, berkas router sama)** — hanya bagian logika yang diubah; baris cek akses tidak disentuh:
  `routers/inbound_receiving.py` (scan-receive/escalate/resolve: penjaga status, alasan, CAS — sekitar baris 55–330),
  `routers/purchase_orders_extra.py` (`cancel_open_inbound_tasks` baru di atas `/close`, blok batal tugas di
  `cancel_purchase_order`/`short_close_po`), `routers/putaway_orders.py` (`PAConfirmPayload.simulated` + argumen),
  `routers/cycle_count.py` (`_load_session` menolak registration, `_resolve_count_bin`, kait pembekuan, model → `KNIn`),
  `routers/initial_registration.py` (endpoint `approve-count`, izin baca `require_any_permission`, model → `KNIn`),
  `routers/rfid.py` (`entity_ctx` untuk mode simulasi di 3 endpoint perangkat/pindai), `routers/inventory.py`
  (`add_initial_stock`), `routers/inbound_receiving_extra.py` (qc-decision alasan), `permissions_config.py`
  (`inventory.approve_value` untuk admin/manager/finance), `access_modules.py` (label).
* **FIX-3b** — `services/rfid_service.py` (perangkat/pindai simulasi), `services/inspection_service.py` (`_release_quarantine`,
  `finish`), `services/return_service.py` (release karantina & SPK retur), `config_registry.py` (`value_format`),
  `scripts/guardrails/verify_atomic_claim.py` & `verify_numeric_bounds.py` (`ROUTER_SCOPE` — paket lain menambah
  router-nya), `backend/input_rules.py` (modul bersama baru untuk dipakai FIX-3b).
* FE: `MobileTaskActions.jsx` (InboundActions ditulis ulang; OutboundActions/SampleCut TIDAK diubah), `PutawayOrdersPanel.jsx`,
  `SettingEditor.jsx`, `RfidDevicesView.jsx`, `RfidLocationsView.jsx`, `CycleCount.jsx`, `RegistrationDetail.jsx`.
* `CODEBASE_MAP.md` belum dibangkitkan ulang untuk modul baru (`input_rules.py`, `inbound_task_state.py`, `BinSelect.jsx`)
  — guardrail `codebase_map` tetap hijau; bangkitkan saat gabung.

## 9. Sisa (belum dikerjakan / butuh keputusan)
1. **D5** (barang retur masuk stok saat DIPINDAI di gudang, dinilai saat settle) — belum: perlu memindah restock identitas
   roll dari `settle` ke pindai + jalur balik untuk retur ditolak/dibalik/tanpa barang; berisiko GL (INV-GL-DRIFT) tanpa
   rancangan Finance. D6 dan penutupan SPK retur sudah.
2. **D2 / FLW-IN-11** (tolak QC + retur supplier: "ganti barang" → PO dibuka lagi + tugas sisa; "potong tagihan" → PO
   tutup kurang) — belum: nota retur QC belum punya jenis remedi; "ganti barang" tanpa Nota Debit butuh jurnal pembalik
   GR-IR yang belum dirancang (risiko selisih persediaan vs GL). Usul: field `remedy` di nota retur + jurnal pembalik
   Dr GR-IR/Cr Persediaan dirancang Finance.
3. **D9** (satu SJ dua PT) — ditunda sesuai keputusan.
4. **FLW-IN-07 / D1** (daftar tugas per gedung lintas PT) & **STM-IN-02** (cek lokasi pada aksi tulis) — wilayah FIX-1.
5. **FRM-03** ("Ambil" HP wajib pindai roll) — alur keluar, keputusan K-B1-05/K-B3b-01 ada di FIX-3b.
6. Menu Finance untuk persetujuan nilai pendaftaran awal — server & layar rincian siap (Finance boleh baca & menyetujui),
   tetapi menu "Pendaftaran awal" hanya ada di tab Stock Opname gudang; Admin/Manajer dapat menjadi penyetuju nilai.
   Perlu entri menu/meja Finance (akses — FIX-1/pemilik).
7. `status_history` seragam baru untuk tugas masuk & transfer; GRN, PA, SPK, opname, retur masih jejak masing-masing.
8. `extra="forbid"` untuk `POReceiveItem`/`GRCompletePayload`/model PA; FRM-16 (galat 422 tertelan) hanya diperbaiki di
   `QCInspection`.
9. FLW-IN-18 bagian perbaikan (repair order tidak atomik & tanpa draf PA) — belum.
10. B3a SSOT-1 (satu `roll_state.transition`) — belum; tabel transisi tugas masuk bisa jadi pola.
11. Data profil gedung FLW-IN-20 (kategori RCM-WOVEN/KNITTING/PRINTING kosong) — sesudah perbaikan `_rank`, draf baru
    benar hanya bila kategori gedung diisi; skrip PREP-C perlu ditambah langkah kategori (keputusan data pemilik).

# FIX-10 — Tabel transisi PA / SPK / opname + SATU penulis status roll (SSOT-1)

* **Paket:** FIX-10 (audit WMS-RFID 9 Nov 2026) · **Implementer:** Claude Code · **Tanggal:** 10 Nov 2026 (WIB)
* **Branch:** `worktree-agent-ab0d005af29a92ddf` (dasar `main` **1c41241** = FIX-1…9 + integrasi). Tidak di-push/merge.
* **Temuan yang ditutup:** **B3a SSOT-1** (P1) — status roll tanpa pemilik (63 penulis / 18 berkas + 2 router, tanpa
  tabel transisi, `allocated` bocor ke daftar status roll, enum registry tertinggal); bagian "tabel transisi + CAS +
  riwayat" untuk **Putaway Order** (B2a §6 #60–#73), **SPK inspeksi/QC** (B2a §5 #51–#59) dan **sesi opname**
  (B2a §9–§10 #90–#112, + opname RFID). Bagian SSOT-5 yang menyangkut enum status roll di `ENTITY_REGISTRY.md` ikut
  diselaraskan.
* **Aman untuk data produksi:** TANPA migrasi data. `status_history` lahir bertahap pada transisi berikutnya (roll/dokumen
  lama tanpa riwayat tetap sah); tidak ada field yang diubah massal; status liar di data hanya DILAPORKAN
  (`scripts/audit/fix10_status_census.py`, baca-saja).

---

## 1. Ringkasan perubahan

| Komponen | Isi |
|---|---|
| `backend/services/roll_state.py` (baru) | `STATUSES` (19 status, label = FE), `ROLL_TRANSITIONS` (daftar-izin dari kode & data), `transition(roll_ids, to, *, from_, reason, actor, action, ref, extra_set, extra_filter, unset, push, pipeline, rebuild, return_doc)` — CAS per status asal, jejak `status_history` (SSOT `status_history.entry`, ≤ 30 entri, ditulis di tulisan yang SAMA), saldo segmen terdampak dibangun ulang (sebelum & sesudah pindah gudang/PT), `assert_known` untuk status lahir, `IllegalRollTransition` (subkelas `ValueError`) SEBELUM tulisan apa pun |
| `backend/services/putaway_state.py` (baru) | Tabel transisi PA (termasuk draf PREP-C/FIX-3a), `finish_claimed` (tulisan akhir klaim saga: CAS status asal + kunci masih dipegang + riwayat; kalah → 409, kunci ditandai gagal), `with_history`, `initial_history` |
| `backend/services/inspection_state.py` (baru) | Tabel transisi SPK inspeksi/QC; `inspection_service._save` kini CAS (status asal ∈ daftar-izin aksi peristiwa) + `status_history`; baris pertama QC memindah status lewat CAS terpisah (riwayat tidak ganda) |
| `backend/services/cycle_count_state.py` (baru) | Tabel transisi opname (item/roll), pendaftaran awal (`mode=registration`), opname RFID (`rfid_verify_sessions`); `transition(..., claimed=True)` untuk tulisan akhir klaim; filter mode (aksi opname tidak pernah menyentuh sesi pendaftaran — sabuk-pengaman STM-IN-03) |
| 21 berkas layanan/router | **74 titik tulis status roll** dipindah ke `roll_state.transition()` (§4) |
| `loading_check_service.py`, `rfid_service.py` | `allocated` dibuang dari daftar status roll (§6) |
| `ENTITY_REGISTRY.md`, `frontend/src/utils/statusVocab.js` | enum status roll = `roll_state.STATUSES`; `status_history` didaftarkan; label FE `wip` = "WIP (Proses)" (istilah layar yang sudah ada) |
| `scripts/guardrails/verify_roll_status_writer.py` (baru) + `baselines/roll_status_writer.json` | INV-ROLL-02 ratchet (baseline **0**), terdaftar di `scripts/gate.sh` (statik + SELF-TEST) |
| `scripts/guardrails/verify_atomic_claim.py` | mengenali pembantu CAS FIX-10 (`_rs.transition(`, `ccs.transition(`, `_ist.cas_filter(`, `claimed=True`, `_pst.finish_claimed(`) — tanpa ini 3 entri REVIEWED palsu-merah; contoh self-test "service_cas tanpa CAS" dipindah ke `putaway_order_service.after_claim` (`dispatch` kini ber-CAS) |
| `scripts/audit/fix10_status_census.py` (baru) | sensus status baca-saja vs tabel |
| `backend/tests/test_fix10_roll_state.py` (baru) · `frontend/src/features/__tests__/fix10RollStatusVocab.test.js` (baru) | 26 uji pytest + 4 uji Jest (§8) |

## 2. Tabel transisi status ROLL (`roll_state.ROLL_TRANSITIONS`)

Disusun dari SEMUA penulis status roll di kode (pemindai statik + pembacaan manual penulis dinamis) dan 12 status hidup
data acuan. `frm == to` selalu sah (tulisan field lain di bawah CAS status, tanpa entri riwayat).

| Dari | Ke (diizinkan) | Pemicu (pemilik) |
|---|---|---|
| `receiving` | quarantine, available | posting penerimaan roll hasil pindai label/GRN (`inbound_complete_service.complete_task`) |
| `quarantine` | available, damaged, returned_supplier, blocked, wip, consumed, delivered, hold | keputusan QC (`qc_service`), lepas karantina retur (`return_service.release_quarantine`), tahan QC-06, perbaikan, opname, retur beli dibalik → tersedia, penyelesaian retur dibalik (roll identitas kembali "di pelanggan"), pecah cutloss |
| `available` | reserved, in_transit_transfer, hold, wip, subcon, blocked, consumed, returned_supplier, quarantine, damaged | alokasi/pesan (SO, transfer antar-PT/antar-gudang, roll pilihan), kirim PA, ember tahan/WIP/makloon, tahan QC-06, habis (produksi, sample R&D, opname), retur beli (keluar / dikunci karantina selama RMA), potongan cutloss dibuang |
| `reserved` | available, committed, in_transit_sales, in_transit_transfer, consumed | lepas, SO disetujui, kirim SJ, transfer antar-gudang dikirim, opname |
| `committed` | available, in_transit_sales, in_transit_transfer, consumed | lepas, kirim SJ, transfer (P03 roll SO), opname |
| `picked` / `packed` | available, in_transit_sales, consumed | ember saldo yang TIDAK pernah ditulis kode (data acuan 0) |
| `in_transit_sales` | delivered, reserved, committed, picked, packed | POD per SJ / pesanan; kompensasi kirim yang kalah balapan (status sebelum berangkat) |
| `in_transit_transfer` | available, reserved, committed, damaged, blocked | PA/transfer tiba (status SO dipulihkan), batal/tolak/kompensasi, diterima rusak / ditahan (`blocked`, FIX-3a STM-IN-04) |
| `delivered` | quarantine, hold | retur pelanggan diterima (karantina retur); cutloss masuk gudang untuk dipecah |
| `hold` | available, wip, delivered, damaged, consumed | lepas tahan, perbaikan, potongan baik cutloss dikirim balik, dibuang, opname |
| `wip` | available, consumed, quarantine, damaged, blocked, hold | WIP selesai / hasil perbaikan, habis di perbaikan, perbaikan dibatalkan (status asal) |
| `subcon` | available, consumed | retur bahan makloon; terpakai di mitra |
| `blocked` | available, quarantine, wip, consumed, damaged | lepas tahan (status sebelum ditahan), tolak QC roll ditahan, perbaikan, opname, dibuang |
| `damaged` | wip, consumed, available, quarantine, hold | perbaikan, opname, koreksi write-off / barang kembali dari supplier, pecah cutloss |
| `returned_supplier` | damaged, available, quarantine | retur beli ditolak (rusak) / dibatalkan |
| `consumed` | available | koreksi produksi / pengambilan bahan sample dibatalkan |
| `in_transit_inbound`, `in_transit_intercompany` | — | ember transit tanpa penulis (data acuan 0) |

**Kosakata** (`STATUSES`, 19): receiving · quarantine · available · reserved · committed · picked · packed · hold · wip ·
blocked · damaged · in_transit_transfer · in_transit_sales · in_transit_inbound · in_transit_intercompany · subcon ·
delivered · consumed · returned_supplier. Kode lama registry `on_order/cross_dock/sold/returned/scrapped` tidak pernah
ditulis → dibuang dari enum (bila muncul di data = liar, dilaporkan). `allocated` = status alokasi SO, bukan status roll.

**Jejak — pilihan "satu, tidak ganda":** `status_history` di dokumen roll (bukan mutasi). Alasan: `inventory_movements`
adalah buku KUANTITAS (Ledger, rekonsiliasi GL) — baris qty 0 per perubahan status akan mengotori layar Ledger dan
pembaca saldo. Mutasi kuantitas tetap ditulis pemanggil seperti sebelumnya (tidak ada mutasi tambahan dari
`roll_state`). Riwayat domain yang sudah ada (`hold_history` alasan tahan, `repair_history`, `return_history`) tidak
diubah — itu catatan domain, bukan jejak status kedua.

## 3. Tabel transisi dokumen

### 3.1 Putaway Order (`putaway_state.TRANSITIONS`)
| Aksi | Dari | Ke | Penulis |
|---|---|---|---|
| create_draft | (lahir) | draft | `putaway_draft_service._insert_draft` |
| create | (lahir) | open | `putaway_order_service.create_order` |
| edit_draft | draft | draft | `update_draft` (CAS `draft_rev`, tanpa riwayat) |
| publish | draft | open | `putaway_draft_service.publish` (klaim → `finish_claimed`) |
| cancel_draft | draft | cancelled | `cancel_draft` (CAS + riwayat beralasan) |
| release_inspection_draft | draft | draft / cancelled | `release_inspection_drafts` (SPK QC 4-point ditutup) |
| dispatch | open | in_transit | `dispatch` (klaim → `finish_claimed`) |
| arrival_trip | open / in_transit / partially_received | status turunan item | `putaway_arrival_service.confirm_arrival_trip` |
| confirm_arrival | idem | partially_received / completed / completed_with_exception / exception / returned | `confirm_arrival` |
| close_remaining | idem | idem | `close_remaining` |
| resolve_exception | idem + completed_with_exception / exception | idem | `resolve_exception` |

**Pembalikan saat batal:** draf yang dibatalkan tidak pernah mengklaim roll (roll tetap di antrean siap-putaway);
PA terbit yang tidak jadi dikirim diputus lewat "tutup sisa" `return_transit` (roll kembali `label_verified/
tag_verified` di gudang asal, `active_movement` dicabut, status roll `available`). Tidak ada `open → cancelled` yang
meninggalkan klaim roll. Status akhir tanpa satu roll tiba = `returned`/`exception`, tidak pernah `completed` (PREP-C).

### 3.2 SPK inspeksi / QC penerimaan (`inspection_state.TRANSITIONS`)
| Aksi (peristiwa `_save`) | Dari | Ke |
|---|---|---|
| create | (lahir) | draft / assigned |
| assign (`assigned`) | draft / assigned / in_progress | assigned / in_progress (status tetap bila sudah jalan) |
| start (`started`) | draft / assigned | in_progress |
| inspect_line (baris QC pertama) | assigned / in_progress | in_progress |
| finish (`finished`) | assigned / in_progress | done |
| reopen (`reopened`) | done | in_progress |
| close_unneeded (`closed`) | draft / assigned / in_progress | closed |
| close_lines (`random_check_closed`, `qc4_closed`) | done | done |
| hold_line (`hold_released`, `hold_rejected`) | draft / assigned / in_progress / done | (tetap) |

**Pembalikan:** buka kembali DITOLAK bila keputusan sudah memutus karantina (stok diterima/ditolak → koreksi lewat retur
beli/penyesuaian) atau SPK QC (random check / 4-point → SPK baru); bila boleh, keputusan & alasan tolak dikosongkan dan
tonggak "retur sudah diinspeksi" dibatalkan. `closed` terminal (tidak ada roll yang disentuh).

### 3.3 Sesi opname (`cycle_count_state`)
| Ranah | Aksi | Dari → Ke |
|---|---|---|
| opname item & per roll | create / create_followup | (lahir) → open |
| | submit | open → submitted |
| | reopen | submitted / rejected → open (mode ≠ registration) |
| | approve (klaim) | submitted → approved / approved_with_exceptions |
| | reject | submitted → rejected (tanpa kunci saga) |
| | roll_finalize (klaim) | open → approved / approved_with_exceptions |
| pendaftaran awal | reg_create · reg_start · reg_start_rollback · reg_submit · reg_return · reg_approve (klaim) · reg_reject | (lahir) → draft → running (→ draft bila kalah balapan) → pending_approval (→ running) → approved[_with_exceptions]; draft/running/pending_approval → rejected |
| opname RFID (`rfid_verify_sessions`) | rfid_create · rfid_complete (klaim) | (lahir) → open → completed |

**Pembalikan:** opname ditolak → stok tidak pernah diubah (selisih baru diterapkan saat disetujui); buka kembali hanya
bila belum ada selisih diterapkan (409); pendaftaran ditolak → pembekuan dilepas, baris lapangan `void` (EPC bebas).

## 4. Penulis status roll yang dimigrasi (74 titik, 21 berkas)

`verify_roll_status_writer.py --list` di dasar `1c41241`: **70 penulis statik di 18 berkas** (audit B3a menghitung 63
dengan alatnya; selisih = `AnnAssign`, `IfExp`, `finish_set` yang tidak terbaca alat audit) + **4 penulis dinamis** yang
tidak terbaca pemindai statik (dict dirakit lintas fungsi / dict-comprehension). Sesudah FIX-10: **0** di luar
`roll_state.py`.

| Berkas | Titik | Fungsi |
|---|---|---|
| `services/roll_service.py` | 21 | reservasi SO (`_reserve_single_roll`, `reserve_specific_rolls`, `_rollback_reserved`), lepas (`release_order_rolls`, `release_order_rolls_partial`×2, `_release_rolls_by_ref_id`), `set_order_rolls_status`, kirim/kompensasi (`ship_order_rolls`×2), POD (`deliver_shipment_rolls`, `deliver_order_rolls`), transfer antar-PT (`reserve_rolls_for_transfer`, `execute_ownership_transfer`, `release_transfer_rolls`), transfer antar-gudang (`reserve_rolls_for_wh_transfer`×3, `dispatch_…`, `receive_…`, `release_…`) |
| `services/putaway_order_service.py` | 4 | `dispatch` (+kompensasi), `_land_items`, `return_items_to_transit` |
| `services/transfer_receipt_service.py` | 2 | `_land` (terima transfer), `resolve` (kembali ke asal) |
| `services/qc_service.py` | 2 | `_consume_quarantine` (keputusan QC), roll ditahan → karantina |
| `services/inbound_complete_service.py` | 1 | roll hasil pindai `receiving` → karantina/tersedia (penulis DINAMIS) |
| `services/roll_hold_service.py` | 4 | `hold_roll`, `release_roll`, `sync_inspection_hold`×2 |
| `services/stock_bucket_service.py` | 5 | tahan/WIP/makloon (`move_rolls_by_qty`, `move_rolls_by_ref`, `move_specific_rolls`×2, `consume_subcon_by_ref`) |
| `services/stock_count_service.py` · `stock_count_roll_service.py` | 1 · 1 | opname item `_shortage`; opname per roll / pendaftaran awal `_cas_op` (penulis DINAMIS `**op["upd"]`) |
| `services/return_service.py` | 4 | lepas karantina retur, pindah kepemilikan roll retur (+rollback), batal write-off |
| `services/return_intake_service.py` · `return_identity_service.py` | 2 · 2 | karantina retur saat pindai diterima / dibalik; roll identitas utuh saat settle / reversal (penulis DINAMIS) |
| `services/return_cutloss_split_service.py` | 4 | cutloss masuk gudang, pecah (induk), potongan dibuang, SJ potongan baik |
| `services/return_disposition_service.py` | 1 | BS retur dibuang |
| `services/purchase_return_service.py` · `purchase_return_remedy.py` | 5 · 1 | karantina selama RMA, barang kembali, retur keluar (+undo), reversal; retur ditolak → rusak |
| `services/repair_order_service.py` | 6 | kirim (+kompensasi), terima kembali, terima hasil (habis / celup ulang / kembali stok) |
| `services/production_service.py` | 2 | bahan habis `consumed` (dulu `$cond` pipeline), reversal operasi |
| `services/rnd_sample_service.py` | 2 | bahan sample (habis → consumed), batal karena jurnal gagal |
| `services/so_line_cancel_service.py` | 1 | batal baris OD |
| `routers/sales_orders_extra.py` | 3 | Ganti Roll (committed, lepas), lepas sebagian |

Jalur gate V2 (`gate_txn_service`) tidak menulis status roll sendiri — mendelegasikan ke PA (`putaway_arrival_service`)
dan transfer (`transfer_receipt_service.receive`) yang kini lewat `roll_state`. Logika/kebijakan gate (`gate_evaluator`,
`rfid_ingest_service`) TIDAK disentuh; di `rfid_service.py` hanya daftar status kandidat tag (`allocated` dibuang).

**Penulis yang tersisa: 0** (pemindai statik) + **0 dinamis yang diketahui**. `return_intake_service.finalize` dulu menulis
ulang `status` = karantina (dinamis, tanpa perubahan) — kini tidak menulis `status` sama sekali (CAS-nya sudah menjamin
karantina). Kelahiran roll (`insert_one`: penerimaan, stok awal, opname temuan, retur restock, potongan) bukan transisi;
status lahir di `insert_child_roll` & posting penerimaan kini diperiksa `assert_known` + riwayat lahir.

**Batas pemindai (dicatat):** penjaga statik tidak bisa membaca dict yang dirakit di fungsi LAIN lalu dioper sebagai
argumen (`{"$set": {**param}}`). Empat penulis seperti itu dipindah manual; penulis baru berbentuk itu tidak akan
memerah — tinjauan kode tetap perlu.

## 5. Transisi ilegal / pola lemah yang ditemukan & keputusan

| # | Temuan | Keputusan (implementer) |
|---|---|---|
| T1 | `_release_rolls_by_ref_id` melepas `ORDER_HELD_STATUSES` termasuk **`in_transit_sales → available`** (roll di Surat Jalan "dilepas" ke stok) — bertentangan dengan invarian FIX-3b STM-OUT-1 | Kode salah → dipersempit ke `RELEASABLE_HELD_STATUSES`; tabel menolak `in_transit_sales → available`. Pemanggil nyata (rollback transfer SO baru) hanya punya roll `reserved` → perilaku sah tidak berubah |
| T2 | `set_order_rolls_status` bisa memindah `picked/packed → committed` (mundur) | Status ember tanpa penulis (data 0) → tidak ditambah ke tabel; roll seperti itu dilewati + log peringatan |
| T3 | `return_cutloss_split_service.execute`: induk ber-status fisik apa pun (termasuk **reserved/committed/blocked/wip**) diubah ke `hold/available` → reservasi SO / tahanan hilang diam-diam | Kode salah untuk status terikat → tabel hanya mengizinkan `delivered/quarantine/damaged/available/hold → hold/available`; diperiksa SEBELUM kunci pecah & jurnal → pesan 400 "Perubahan status roll tidak diizinkan …" |
| T4 | `return_disposition._dispose` dari `blocked → damaged` (BS ditahan dibuang) | Sah → ditambah ke tabel |
| T5 | `quarantine/damaged → hold` (pecah cutloss roll yang sudah di gudang) | Sah → ditambah ke tabel |
| T6 | **R→W tanpa CAS** (status dibaca di Python, tulis `{id}` saja): `deliver_order_rolls`, `execute_ownership_transfer`, `release_transfer_rolls`, `receive_wh_transfer_rolls`, `qc_service._consume_quarantine`, `return_service.release_quarantine`, `reverse_writeoff`, `purchase_return._roll_back_to_stock`, `repair.receive`, cutloss induk, roll pindai `receiving` di `complete_task`, `restore_identity_roll`, `production` (pipeline `$cond`), `_dispose` | Kini CAS status asal (+prasyarat lama). Kalah balapan: dilewati (pelepasan/POD/transfer — tanpa mutasi/tag hantu), 409/ValueError (keputusan QC, lepas karantina, penerimaan, perbaikan — saga tetap terlihat). Sebelumnya: menimpa diam-diam |
| T7 | Status roll `hold` dari terima transfer (FIX-3a sudah memetakan ke `blocked`) | Tabel memakai `blocked`; `in_transit_transfer → hold` tidak diizinkan |
| T8 | PA / SPK / sesi opname: tulisan akhir `{id}` saja (PA klaim saga, `inspection_service._save`, `approve`/`roll_finalize`/`reg_approve`) | CAS status asal (+kunci saga masih dipegang untuk tulisan akhir klaim); kalah → 409/InspectionError, kunci ditandai gagal (terlihat di Kunci Saga) |
| T9 | Aksi opname biasa tanpa filter `mode` di filter tulis (STM-IN-03 sudah ditolak di pemuat sesi FIX-3a) | Sabuk-pengaman: filter tulis aksi opname `mode ≠ registration`, aksi pendaftaran `mode = registration` |

## 6. `allocated` & registry

* `loading_check_service.EXPECTED_STATUSES` = `roll_service.RELEASABLE_HELD_STATUSES` (dulu daftar sendiri + `allocated`);
  hitungan "belum committed" kini `reserved` saja.
* `rfid_service.PHYSICAL_STATUSES` (kandidat tag) tanpa `allocated`.
* `allocated` tetap dipakai SAH sebagai `sales_orders.allocations[].status` (tidak disentuh).
* Data acuan: 0 roll berstatus `allocated` → tidak ada perubahan perilaku.
* `ENTITY_REGISTRY.md` §inventory_rolls: enum = `roll_state.STATUSES`, `status_history` didaftarkan; §inspections &
  §cycle_count_sessions memuat tabel transisi + `status_history`. Uji `test_registry_and_fe_vocab_aligned_with_roll_state`
  mengunci registry ⇔ `STATUSES` ⇔ label FE ⇔ ember saldo `roll_service`.

## 7. Perubahan perilaku yang terlihat pengguna

1. **Riwayat status** (`status_history`) kini tercatat di roll, PA, SPK inspeksi, sesi opname/pendaftaran & opname RFID
   (belum ditampilkan di layar — data tersedia untuk layar riwayat/journey berikutnya). Respons API daftar roll membawa
   field tambahan ini (≤ 30 entri/roll; roll lama tanpa riwayat).
2. **Balapan yang dulu menimpa diam-diam kini ditolak/dilewati** (409 "berubah bersamaan — muat ulang", pesan SPK
   "baru saja ditutup/diubah orang lain"). Tidak terjadi pada pemakaian berurutan normal.
3. **Pecah cutloss** roll yang masih dipesan/terkomit/ditahan/WIP kini ditolak dengan pesan (T3).
4. **Label status roll `wip`** tampil "WIP (Proses)" (dulu jatuh ke label umum/kode mentah).
5. Tidak ada perubahan angka stok, rumus `stock_figures`, cakupan FIX-1, atau keputusan pemilik.

## 8. Uji

### 8.1 Uji baru — `backend/tests/test_fix10_roll_state.py` (gagal di dasar → lulus sesudah)
Dasar `1c41241`: **0/26** (galat koleksi: `services.roll_state` tidak ada). FIX-10: **26/26 lulus** (dengan `KN_DEMO_PW`; tanpa sandi di lingkungan: 23 lulus + 3 uji HTTP dilewati). Uji transfer antar-gudang ditambah sesudah putaran pertama (`test_wh_transfer_reserve_dispatch_receive_and_release_history`: pesan → kirim → terima ke gudang lain, batal sesudah dikirim kembali ke gudang asal, terima ulang tidak memindah lagi).

| Bagian | Uji |
|---|---|
| A roll_state | ilegal ditolak sebelum tulisan (+`in_transit_sales→available`, `allocated`/kode lama registry); `from_`/alasan wajib, status di filter ditolak; CAS asal tidak cocok → 0 tulisan (termasuk prasyarat lain); **6 transisi paralel → tepat 1 menang**, 1 entri riwayat; bentuk entri (from/status/user/note/action/ref) & batas 30; saldo segmen dibangun ulang + pindah gudang (dua segmen); pipeline + `return_doc`; roll anak: status lahir dikenal, riwayat induk tidak diwarisi |
| B penulis dimigrasi | tahan/lepas QC-06 (riwayat sekali, `hold_history` tetap); ember tahan/lepas; reservasi roll pilihan + pelepasan per dokumen **tidak** melepas roll di SJ; transfer antar-gudang pesan → kirim → terima (pindah gudang, saldo dua sisi) / batal sesudah kirim kembali ke asal / terima ulang tidak memindah (CAS) |
| C Putaway | PA manual → kirim → trip → tutup sisa: riwayat PA `open→in_transit→partially_received→completed`, riwayat roll `available→in_transit_transfer→available` (tiba & kembali transit); batal draf beralasan (pembalikan bersih, roll tidak diklaim, terbit ditolak); tabel menolak 6 transisi ilegal; `finish_claimed` menolak status berubah di luar klaim (409, kunci ditandai gagal) |
| D SPK | mulai menulis riwayat; tulisan basi (SPK ditutup orang lain) ditolak; draf → selesai ditolak; **4 "mulai" paralel → 1 menang** |
| E opname | kirim → tolak → buka kembali lewat API ber-riwayat (alasan tercatat); aksi opname tidak menyentuh sesi pendaftaran; **5 "kirim" paralel → 1 menang**; opname RFID selesai ber-riwayat & kunci dicabut |
| F kosakata | registry ⇔ `STATUSES` ⇔ label FE ⇔ ember saldo; `allocated` keluar dari dua daftar |
| G guardrail | pemindai merah untuk penulis baru, hijau di repo, self-test lulus, berkas baru = merah |

### 8.2 Regresi dasar vs FIX-10 (DB salinan sama, dipulihkan sebelum tiap putaran)
Stack sementara `kn-tmp-fix10-*` (mongo:7 `--memory 1200m --wiredTigerCacheSizeGB 0.5`, backend `kn-dev-backend`
`--memory 1500m`; kode DISALIN ke `/app` — putaran dasar benar-benar memakai `git archive main` di `/app`, berkas uji baru
ikut disalin agar terbukti gagal), DB = `kn_test_trial_2026-11-08` → `test_database`, **dipulihkan (drop + restore) dan
uvicorn dijalankan ulang sebelum tiap putaran**; tiap berkas uji di proses pytest terpisah.

**Putaran utama — 57 berkas** (FIX-1…9: `fix2/3a/3b/5/6/7×3/9`; putaway: `prep_c`, `iter264`, `prep_integrasi_freeze_putaway`,
`p02`; SPK/QC: `f14`, `p05_imp16`, `p19`, `fe10`, `f11_f12`, `return_spk_per_roll`; opname: `l10_ln101`, `l10_ops01`,
`prep_b`, `l10_ln100_102`; keluar/SO: `roll_pick_and_reallocate`, `iter270`, `f05`, `iter144`; transfer: `iter14`, `p03`,
`transfer_status_guard`, `interco_g6`; retur: `uat23×2`, `return_per_roll`, `l08×2`, `cut01`, `ln091_092`; makloon/ember:
`makloon_celup_rolls`, `iter280`, `f2_stock_buckets`; gate V2: `prep_d1`, `prep_d2`, `prep_g`, `run_rfid_v2_integration`,
`run_rfid_v2_extended`; potong/sampel: `l06_samples_cutting`, `rnd_samples_qa3`, `l04_mdq_cut`, `uat24_f5`):

| Putaran | Lulus | Gagal | Galat | Gagal hanya di putaran ini |
|---|---|---|---|---|
| dasar `main` 1c41241 (+ berkas uji FIX-10) | 427 | 35 | 25 | 1 (= galat koleksi berkas uji FIX-10) |
| FIX-10 (kode akhir `d6d2ec3`+) | 450 | 35 | 24 | **0** |

* **Gagal hanya di FIX-10: 0.** 35 gagal + 24 galat SAMA PERSIS di kedua putaran (lama, data/fixture: `p19` 5 — roll
  fixture tidak ada di data acuan, `f2_stock_buckets` 8 — stok fixture 0, `p03` 11 galat — dokumen `KANDA/TRF-00002`
  tidak ada, `interco_g6` 11, `transfer_status_guard` 3, `f11_f12` 6 galat, `fix7_data_scripts` 7 galat, `iter14` 1,
  `p02` 1, `l10_ln100_102` 1, `f05` 2, `rnd_samples_qa3` 2, `uat24_f5` 1). Gate V2 `run_rfid_v2_integration` &
  `run_rfid_v2_extended`: kode keluar 0 di kedua putaran.
* Putaran FIX-10 pertama (kode sebelum perbaikan `return_doc`) juga 0 gagal-hanya-FIX-10 di 57 berkas.

**Putaran pelengkap — uji yang butuh `KN_DEMO_PW` (diberikan lewat `docker exec -e`, tidak ditulis ke berkas) dan uji G3
yang menulis ke DB sendiri (`DB_NAME=g3_audit_fix10`):**

| Berkas | dasar | FIX-10 |
|---|---|---|
| `test_fix10_roll_state.py` | galat koleksi | **26/26** |
| `test_fix1_cakupan.py` | 30/30 | 30/30 |
| `test_fix8_saved_views.py` | 19/19 | 19/19 |
| `test_fix3a_inbound_integrity.py` | 28/28 | 28/28 |
| `test_g3_phase01.py` (produksi/PA/opname RFID fault-injection) | 27/28 | 27/28 |
| `test_g3_phase02.py` | 20/21 | 20/21 |
| `test_g3_phase02b.py` | 14/16 | 14/16 |
| `test_g3_phase04.py` | 16/17 | 16/17 |

Gagal identik di kedua sisi (lama): `g3 pa02` (suntik galat pada `inventory_movements.update_one` — FIX-5 memindah mutasi
PA ke `bulk_write`, suntikan tidak pernah terpicu), `g3 od_lock01`, `g3 tag01`, `g3 retpolicy01`, `g3 hr_payroll`.

**Temuan selama regresi (diperbaiki):** putaran pelengkap pertama memerahkan `g3 cc01` (selesai opname RFID: suntik galat
pada `rfid_verify_sessions.update_one`) karena tulisan akhir sesi pindah ke `find_one_and_update`. `cycle_count_state.
transition` diberi `return_doc=False` (tetap `update_one`) untuk SEMUA titik yang dulu `update_one` (opname RFID selesai,
finalisasi opname per roll, mulai/kembali/ajukan/setujui pendaftaran awal) → `cc01` lulus; putaran akhir di atas memakai
kode sesudah perbaikan ini.

### 8.3 Jest / ESLint
Kontainer `node:20` sementara, `node_modules` dari volume `kn-dev_fe_node_modules` (read-only), `CI=true`.

| Putaran | Hasil |
|---|---|
| `fix10RollStatusVocab` (baru) dengan `statusVocab.js` dasar | **2/4 gagal** (`wip` tanpa label ranah roll → kode mentah; nada) |
| FIX-10 — suite terkait (`fix10RollStatusVocab`, `fix8StandarUi2`, `fix9KunciMakloon`, `phase4R8`) | **4/4 suite · 39/39 uji lulus** |
| FIX-10 — Jest penuh (`--maxWorkers=2`) | **91/91 suite · 653/653 uji lulus** |
| ESLint `utils/statusVocab.js` + uji baru | 0 galat, 0 peringatan |

## 9. Guardrail
`PYTHONUTF8=1 python scripts/guardrails/verify_*.py` — dasar = `git archive main` (1c41241) diekstrak, FIX-10 = branch ini.

| Guardrail | Dasar | FIX-10 |
|---|---|---|
| **`verify_roll_status_writer` (baru, INV-ROLL-02)** | — (70 penulis statik di 18 berkas bila dijalankan pada kode dasar) | **PASS — 0 penulis, baseline 0**; self-test 20/20 |
| `verify_ui_standard` | PASS 5691 cek | PASS 5691 cek (ratchet tidak naik) |
| `verify_scope_guard` | kode 0 | kode 0 |
| `verify_atomic_claim` | 6 pelanggaran (BELUM DITINJAU 77 + 5 lama); self-test 2 gagal lama | 6 pelanggaran (BELUM DITINJAU **75** + 5 lama yang sama); self-test 2 gagal lama yang sama |
| `verify_ref_unlink` (kontainer) | 3 pelanggaran / 633 cek | 3 pelanggaran (sama) / 637 cek; self-test 8/8 |
| `verify_status_history` | PASS 9 | PASS 9 |
| `verify_to_list_bound` | 20 pelanggaran | 20 (sama; nomor baris `roll_service` bergeser) |
| `verify_codebase_map` | PASS | PASS (peta dibangkitkan ulang) |
| `verify_ui_contrast` · `verify_list_export` · `verify_page_tabs` · `verify_custom_modals` | PASS | PASS |
| `verify_line_scope` · `verify_auth_coverage` | 1 · 28 | 1 · 28 (sama) |

* `verify_atomic_claim`: tanpa perluasan pola, 3 entri REVIEWED akan palsu-merah (`cycle_count_service.complete`,
  `initial_registration_service.reject`, `rnd_sample_service.issue_material`) karena CAS kini lewat pembantu FIX-10 —
  pola diperluas (§1), contoh self-test "service_cas tanpa CAS" dipindah ke fungsi yang memang tanpa CAS.
  **BELUM DITINJAU 77 → 75 adalah artefak ukur, bukan perbaikan:** `handheld.py POST /tasks/{kind}/{doc_id}/complete` dan
  `sales_returns.py …/roll-settlement/{settlement_id}/complete` tidak lagi terhitung multi-koleksi karena tulisan
  `inventory_rolls`-nya kini lewat `roll_state` (inventaris tidak menelusur ke modul itu). Angka baseline tidak diubah.
* `verify_state_machine.py` TIDAK dijalankan (larangan paket). `verify_concurrency` (runtime HTTP, menulis data) tidak
  dijalankan.

## 10. Keputusan implementer (bukan keputusan pemilik/koordinator)
1. **Jejak = `status_history` di dokumen roll** (bukan mutasi) — alasan §2. Dibatasi 30 entri terakhir (`$slice`) agar
   dokumen roll & payload daftar tidak tumbuh tanpa batas.
2. **`roll_state` membangun ulang saldo bawaan (`rebuild=True`)**; pemanggil yang sudah membangun ulang segmen yang sama
   dalam satu putaran memberi `rebuild=False` (menghindari rebuild ganda — performa FIX-5/7 dijaga).
3. **Satu tulisan per status asal** (bukan pipeline `$status`) — entri riwayat tahu persis asalnya; biaya ≤ jumlah status
   asal yang diizinkan pemanggil (umumnya 1).
4. Transisi yang ditolak tabel = `IllegalRollTransition` (subkelas `ValueError`) → pemanggil yang sudah menangkap
   `ValueError` menampilkan 400 berbahasa Indonesia; selebihnya 500 terlihat (galat pemrograman, bukan status liar).
5. T1–T5 di §5 (dua kode dipersempit, dua transisi ditambah, satu dilewati+log).
6. Kegagalan CAS di tengah saga (keputusan QC, lepas karantina retur, terima perbaikan) → galat + kunci saga dibiarkan /
   ditandai gagal (pola saga yang ada), bukan dilanjutkan dengan setengah data.
7. Tidak ada skrip data: tidak ada data yang perlu diubah; status liar hanya dilaporkan (§11).

## 11. Sensus data acuan (baca-saja, `scripts/audit/fix10_status_census.py`)
Dijalankan pada salinan `kn_test_trial` (tanpa tulisan):

| Koleksi | Status | Liar |
|---|---|---|
| `inventory_rolls` | available 46.436 · in_transit_sales 81 · consumed 44 · subcon 32 · quarantine 29 · reserved 20 · delivered 13 · committed 12 · in_transit_transfer 10 · damaged 8 · blocked 8 · returned_supplier 7 | **0** — kode lama registry (`on_order/cross_dock/sold/returned/scrapped`) 0; ember tanpa penulis (`picked/packed/in_transit_inbound/in_transit_intercompany`) 0 |
| `putaway_orders` | completed 2 | 0 |
| `inspections` | draft 64 · done 43 · in_progress 4 · assigned 2 | 0 |
| `cycle_count_sessions` (opname / pendaftaran) · opname RFID | — (0 dokumen) | 0 |

Cek tambahan nilai "status asal" di data: `blocked` → `hold.prev_status` = available (8); `in_transit_transfer` →
`transfer_prior_status` = reserved (10, ref SO); `returned_supplier` → `returned_from_status` = available 2 · quarantine 1 ·
kosong 4 (jalur balik memakai `quarantine/available` menurut jenis mutasi, bukan field ini); roll ber-`bucket_ref` =
subcon 32 · consumed 44. Semua pasangan sah menurut tabel. **Produksi:** jalankan skrip yang sama (baca-saja) sebelum
rilis — status liar yang muncul akan ditolak `roll_state` saat transisi berikutnya (galat terlihat, bukan status diubah
diam-diam).

## 12. Berkas berisiko bentrok
`roll_service.py`, `putaway_*`, `inspection_service.py`, `qc_service.py`, `return_*`, `purchase_return_*`,
`stock_bucket_service.py`, `stock_count_*`, `transfer_receipt_service.py`, `routers/cycle_count.py`,
`routers/sales_orders_extra.py`, `initial_registration_*`, `repair_order_service.py`, `production_service.py`,
`rnd_sample_service.py`, `scripts/gate.sh`, `scripts/guardrails/verify_atomic_claim.py`, `ENTITY_REGISTRY.md`,
`frontend/src/utils/statusVocab.js`, `CODEBASE_MAP.md`. Paket lain yang menambah penulis status roll akan MERAH di
INV-ROLL-02 sampai memakai `roll_state.transition()`.

## 13. Sisa / di luar paket
* **Layar riwayat status** (roll/PA/SPK/opname) belum dibuat — data sudah ada.
* Grade (SSOT-2), satu representasi "ditahan" (SSOT-3 lanjutan), mutasi tanpa pintu tunggal (SCH-6), status tugas WMS
  (`wms_tasks` sudah FIX-3a/3b) — di luar FIX-10.
* `ENTITY_REGISTRY.md` §inventory_rolls masih berlabel "DRAFT / PROPOSED" dan belum ada bagian `putaway_orders`
  (SSOT-5, paket dokumen).
* Pemindai statik INV-ROLL-02 tidak membaca dict yang dirakit di fungsi lain (§4).

---

## Ringkasan untuk koordinator
* **SSOT-1 ditutup:** satu pintu `services/roll_state.transition()` (daftar-izin 19 status, CAS status asal, `status_history`
  ≤ 30 entri di tulisan yang sama, rebuild saldo segmen sebelum/sesudah pindah). **74 titik tulis di 21 berkas dimigrasi**
  (70 statik + 4 dinamis yang tak terbaca pemindai); sisa di luar `roll_state`: **0**. Guardrail baru INV-ROLL-02
  (ratchet baseline 0) terdaftar di `gate.sh`.
* **Tabel transisi + CAS + `status_history`** untuk Putaway Order (termasuk draf), SPK inspeksi/QC, sesi opname (item/roll),
  pendaftaran awal, dan opname RFID. Pembalikan batal didokumentasikan (§3); tulisan akhir klaim saga kini CAS + kunci.
* **`allocated` dibuang** dari daftar status roll (`loading_check_service`, `rfid_service`); registry & label FE selaras
  (`wip` = "WIP (Proses)").
* **Transisi ilegal ditemukan (§5):** `in_transit_sales → available` lewat `_release_rolls_by_ref_id` (dipersempit),
  cutloss bisa mengubah roll terpesan/ditahan ke `hold/available` (kini ditolak sebelum kunci/jurnal), `picked/packed →
  committed` (dilewati+log), 14 penulis R→W tanpa CAS (kini CAS). Dua transisi sah ditambah (`blocked → damaged`,
  `quarantine/damaged → hold`).
* **Uji:** baru pytest 26/26 (dasar 0/26), Jest baru 4/4 (dasar 2/4 gagal), Jest penuh 653/653; regresi 57 berkas dasar vs
  FIX-10: **0 gagal hanya di FIX-10** (450 lulus vs 427; 35 gagal/24 galat lama identik); pelengkap (FIX-1, FIX-8, FIX-3a
  ber-sandi, G3 ×4) identik dengan dasar; gate V2 runner kode 0 di keduanya. Satu regresi ditemukan & diperbaiki selama
  uji (`g3 cc01`, §8.2).
* **Guardrail lain tidak naik** (atomic_claim perlu perluasan pola untuk pembantu CAS FIX-10; BELUM DITINJAU 77→75 =
  artefak ukur, dicatat).
* **Produksi:** tanpa migrasi; `status_history` lahir bertahap. Sensus data acuan: 0 status liar. Saran sebelum rilis:
  jalankan `scripts/audit/fix10_status_census.py` (baca-saja) di produksi.
* **Perlu perhatian koordinator:** (1) perubahan perilaku T3 (cutloss roll terikat ditolak) & T6 (balapan kini 409/
  dilewati); (2) sandi demo sempat tertulis di berkas uji pada commit WIP `1912af9` lalu diganti `KN_DEMO_PW` di `d6d2ec3`
  (riwayat commit lokal tidak ditulis ulang — sandi yang sama sudah ada di `AGENTS.md`); (3) layar riwayat status belum
  ada.

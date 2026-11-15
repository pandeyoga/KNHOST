# FIX-6 — Keputusan pemilik 10 Nov: alur masuk & retur + tabel transisi GRN / retur

- Tanggal: 10 Nov 2026 (WIB ±00.20–01.55) · Pelaksana: Claude Code (paket perbaikan FIX-6) · Branch worktree
  `worktree-agent-a51b85cae919d867d`, dasar `main` `c729f4e` (sudah ter-deploy ke produksi). Commit: `ad12872` (kode),
  `10aa648` (uji lama disesuaikan), `d995d97` (uji tambahan), laporan ini.
- Dasar keputusan: `KEPUTUSAN-KOORDINATOR.md` bagian **"Keputusan pemilik langsung — 10 Nov 2026"** (D5, D2, D9, penanda
  "minta inspeksi", izin unduh lembar master MD). Bahan: B2a FLW-IN-09/-11/-14 + `B2a-TRANSISI-STATUS.md` §3/§8,
  `hasil/FIX-3a-ALUR-MASUK.md` (§6 D5/D2 sisa, D6), pola `services/inbound_task_state.py` (FIX-3a) &
  `outbound_task_state.py` (FIX-3b).
- Lingkungan uji: stack sementara `kn-tmp-fix6-{mongo,be,fe}` (salinan `kn_test_trial_2026-11-08`, dipulihkan sebelum tiap
  putaran), tanpa mount folder Windows, tanpa peramban. Stack bersama `kn-uji-*` / DB koordinator tidak disentuh.
- **Kejadian lingkungan:** ±01.07 WIB Docker Desktop macet (API 500) lalu mulai ulang sendiri ±01.23 — semua kontainer
  (termasuk milik paket lain) berhenti. Saya **tidak** me-restart Docker; kontainer saya dinyalakan lagi dan putaran regresi
  yang terputus diulang penuh dari DB segar (angka di §6 dari putaran utuh).

---

## 1. Keputusan yang diterapkan & temuan yang ditutup (ID → perubahan → uji)

Uji baru: `backend/tests/test_fix6_keputusan_10nov.py` (16 uji) dan `frontend/src/features/__tests__/fix6Decisions.test.js`
(5 uji). Data uji ber-TAG dibuat sendiri dan dibersihkan; roll terkirim SO acuan `KSC/SO-00001` dipulihkan (pola
`test_l08_ln081_journey`).

### 1.1 D5 — retur penjualan MASUK STOK saat dipindai (B2a FLW-IN-09, transisi #82/#85/#88)
| Perubahan | Uji |
|---|---|
| Layanan baru `services/return_intake_service.py` (tabel transisi `return_intake.state`: `received → valued / reversed`, `valued → received`). Pindai **diterima** (`return_journey_service.scan`, sesudah CAS dokumen) → roll klaim jadi **karantina retur** di gudang pindai: `status=quarantine` (kelompok "Ditahan / QC" FIX-2, **rumus `stock_figures` tidak diubah**), `qc_status=return_received`, **nilai nol** (`unit_cost/base_unit_cost=0`), mutasi `return_quarantine_in`, saldo dibangun ulang. Roll utuh = roll yang SAMA (id/nomor/tag; keadaan "di pelanggan" disimpan `return_restore`); klaim sebagian = roll anak bernomor induk (lot `RTN-<retur>`). Pindai **tiba** di gudang lain → roll ikut pindah (mutasi keluar/masuk). | `test_d5_scan_received_enters_return_quarantine_without_value_or_journal`, `test_d5_arrived_elsewhere_moves_return_quarantine`, `test_d5_partial_claim_child_and_roll_decision_reverses` |
| **Nilai & jurnal tetap saat settle; tanpa jurnal ganda.** `return_identity_service.restock_identity` menemukan roll karantina retur dan **menilainya** (`finalize`: qty hasil QC, grade/cacat QC, biaya WAC, riwayat retur) — tanpa roll kedua, tanpa mutasi masuk kedua; selisih qty QC dicatat `return_qc_adjust`. Jurnal Nota Kredit (Dr Persediaan / Cr HPP) tetap SATU dari jalur lama → subledger = GL. Berlaku untuk settle per barang **dan** penyelesaian per roll. | `test_d5_scan_received_…` (1 jurnal, 1 mutasi masuk, Dr 1-1300 = nilai roll ±Rp1), `test_d5_roll_settlement_values_stock_roll_and_reverses_rejected_roll` |
| **Pembalikan:** retur ditolak (`reject_return`), roll klaim ditolak sebelum ACC (`decide_rolls`), outcome tanpa stok (nego / diskon / tolak klaim / sebagian) saat settle, roll dipecah cutloss → karantina retur DIBALIK (roll utuh kembali "di pelanggan" dari `return_restore`, anak dihapus; mutasi `return_reversal_out`; tanpa jurnal). Koreksi penyelesaian per roll yang membuka retur lagi → roll kembali karantina bernilai nol (`unvalue`) karena barangnya masih di gudang. | `test_d5_reject_before_settle_reverses_return_quarantine`, `test_d5_partial_claim_child_…`, `test_d5_roll_settlement_…` |
| Pagar: roll karantina retur yang belum dinilai **tidak bisa dilepas** (`release_quarantine` 400) dan tidak ikut retur ke supplier; layar Karantina retur menandainya "Diterima gudang · nilai saat penyelesaian" (tanpa pilihan release). "Akan datang" retur (`stock_figures.incoming_rows`) dikurangi roll yang sudah dipindai (tidak dihitung dua kali). | `test_d5_scan_received_…`, Jest "D5 — roll retur yang baru dipindai …" |

### 1.2 D2 — tolak QC + retur ke supplier dipilih PER KASUS (B2a FLW-IN-11, transisi PO #4)
| Perubahan | Uji |
|---|---|
| `qc_service.process_qc_decision` (antrean karantina) & tutup SPK penerimaan (`inspection_service.finish`): tolak + disposisi **retur** WAJIB `return_remedy` ∈ {`replace` ganti barang, `bill_cut` potong tagihan} + alasan **K-14** (`return_remedy_reason`, kosong → alasan tolak) — divalidasi SEBELUM klaim saga. Pilihan tercatat di retur beli (`remedy{choice,label,reason,by,at,task_id}`) + audit `purchase_return_remedy_chosen`. Layar: komponen `ReturnRemedyChoice` di antrean QC & panel SPK. | `test_d2_qc_return_requires_remedy_choice_and_reason`, Jest "D2 …" (2) |
| Dieksekusi saat retur beli **DISETUJUI** (`services/purchase_return_remedy.py`, dipanggil `_finalize_supplier_return_financials`). **Ganti barang:** `received_qty` baris − qty retur (`replaced_qty`), PO → `partial`, tugas terima **sisa** `waiting_goods` (`ensure_remainder_task`, `replacement_for_return`); AP tidak berubah; tanpa Nota Debit; jurnal **pembalik GR-IR neto** Dr 2-1150 / Cr 1-1300 (`gl_service.post_purchase_return_grir`). | `test_d2_replace_reopens_po_with_remainder_task_and_grir_reversal` |
| **Potong tagihan:** AP turun lewat dokumen yang sudah ada (retur beli/Nota Debit: `returned_amount` += bruto), `returned_qty` baris → 3-way match tagihan = diterima − diretur (`vendor_bill_service.evaluate_match` & `build_billing_context`); PO yang sudah diterima penuh → **ditutup kurang** (`closed_short` + rekonsiliasi `po_close_settlement_service`). Jurnal: PO **belum ditagih** → pembalik GR-IR neto (tanpa PPN); **sudah ditagih** → Nota Debit lama Dr Hutang (bruto) / Cr Persediaan / Cr PPN Masukan. | `test_d2_bill_cut_unbilled_closes_short_and_reduces_billing`, `test_d2_bill_cut_billed_posts_debit_note_against_payable` |
| Pembalikan jelas: koreksi retur beli (`reverse_settlement`) membatalkan tugas pengganti yang belum menerima barang (sudah menerima → koreksi ditolak), mengembalikan `received_qty/replaced_qty/returned_qty`, status PO sebelum retur, AP hanya bila pernah dipotong. Retur beli dari tolak QC yang **ditolak** sebelum disetujui → roll `returned_supplier` kembali ke gudang sebagai **rusak** (`damaged`; jurnal retur belum pernah ada → subledger kembali = GL). | `test_d2_replace_…` (reverse), `test_d2_rejected_qc_return_rolls_back_as_damaged` |

### 1.3 D9 — satu SJ supplier untuk dua PT → GRN per PT (B2a FLW-IN-14)
| Perubahan | Uji |
|---|---|
| `GET /goods-receipts/arrival-candidates` (PO terbuka supplier di SEMUA PT penugasan akun, per lokasi; gudang di luar lokasi kerja FIX-1 disembunyikan) + `POST /goods-receipts/arrival` → satu GRN per **(PT pemilik × gudang penerimaan PO)**, masing-masing ke PO-nya, saling bertaut `arrival{id, siblings}`. Pagar: PO supplier yang sama, PT ∈ penugasan akun (403), gudang ∈ lokasi kerja (FIX-1 `assert_warehouse`), **satu lokasi/site** (400), gudang `assert_usable` per PT; semua dicek sebelum GRN pertama lahir, gagal di tengah → GRN yang sempat lahir dibatalkan. Kunci SJ tetap `PT|mitra|SJ|tahun` (SJ sama sah di tiap PT). Wizard kedatangan: centang "Satu surat jalan berisi barang beberapa PT", pilih PO lintas PT satu lokasi, foto SJ dilampirkan ke tiap GRN; detail GRN menyebut kedatangan saudaranya. | `test_d9_one_delivery_note_two_pts_split_into_grn_per_pt`, `test_d9_arrival_fences_location_and_pt`, Jest "D9 — wizard …" |

### 1.4 Penanda "minta inspeksi" (butir terbuka gelombang 1 / B2a §6)
| Perubahan | Uji |
|---|---|
| Baris PO `inspection_requested` (form PO: centang "Minta inspeksi"; amandemen mempertahankan) → tugas penerimaan `inspection_request{source=po_line}` → roll saat diposting (`inbound_complete_service`). Saat penerimaan: `POST /inbound/tasks/{id}/inspection-request` (alasan K-14, CAS status sebelum lepas karantina, beraudit; roll `receiving/quarantine/blocked` tugas ikut ditandai). `putaway_draft_service.inspection_requested` = SPK 4-point terbuka **atau** roll bertanda yang belum pernah singgah di gedung inspeksi → draf PA `purpose=inspection` ke gedung berperan inspeksi di lokasi yang sama (logika routing PREP-C/FIX-3a dipakai; label "minta inspeksi" di `PutawayDraftsPanel` sudah ada). Detail PO menampilkan penanda. | `test_inspection_flag_po_line_to_task_roll_and_inspection_draft`, `test_inspection_request_at_receiving_marks_task_and_rolls`, Jest "minta inspeksi …" |

### 1.5 Izin unduh lembar master untuk MD (PREP-A, butir gelombang 1)
`DEFAULT_PERMISSIONS["md"]["product"]` + `export` → `GET /master-governance/cleanup/sheet` (dan ekspor produk lain) terbuka
untuk MD; `sync_permission_modules` menambahkannya ke matriks tersimpan produksi saat start (pencabutan admin tidak
dihidupkan lagi). Fixture izin dibangkitkan ulang (`tests/fe03_access_fixture.py` → `access_builtin_fixture.json`; nav
tidak berubah). Uji: `test_md_can_download_master_cleanup_sheet`, Jest `navAccess`/`serverAccessReach` hijau.

### 1.6 Tabel transisi daftar-izin + CAS + `status_history` (B2a STM-IN-07 untuk dokumen yang disentuh)
| Dokumen | Modul | Isi |
|---|---|---|
| GRN (`goods_receipts`) | `services/grn_state.py` (baru) | `TRANSITIONS` per aksi (read, read_done, manual_entry, start_count(+rollback), finish_count, reopen_count, close_begin/done, return_to_reconcile, reject, cancel). `goods_receipt_service.cas()` menolak transisi tak terdaftar (`check`) dan menulis `status_history` (SSOT) atomik di tulisan yang sama; dua tulisan langsung (OCR selesai, rollback klaim tugas) ikut menulis riwayat. Pembalikan batal: roll `receiving` dihapus, tugas dilepas, kunci SJ dicabut (sudah ada). |
| Retur penjualan (`sales_returns`) | `services/sales_return_transition.py` (baru) di atas tabel murni `return_state.TRANSITIONS` | CAS status asal + `status_history` untuk ajukan, setujui, mulai/selesai QC (dulu R→W `{id}`), tolak, buang draf; settle/reverse/penyelesaian per roll (klaim saga) menulis riwayat di `finish_set`. Pembalikan tolak/batal = §1.1. |
| Retur beli (`purchase_returns.status`) | `services/purchase_return_doc_state.py` (baru) | `submit · approve · reject · reverse` (daftar-izin, CAS, riwayat). Pembalikan tolak (tolak QC → rusak) & reverse (jurnal, roll, AP, efek PO) = §1.2. |
Uji: `test_transition_tables_allowlist_and_cas` + riwayat diperiksa di uji D5/D2/D9.

## 2. Perubahan perilaku untuk pengguna
1. **Pindai "Diterima" retur pelanggan langsung menambah stok gudang** sebagai karantina retur (Ditahan/QC, tidak bisa
   dijual/dipesan, nilai Rp0 sampai diselesaikan). "Lepas karantina" baru bisa sesudah retur diselesaikan.
2. Retur ditolak / roll ditolak / outcome tanpa stok → roll itu keluar lagi dari stok gudang (mutasi "Pembalikan Retur Jual").
3. **Tolak QC + "Retur ke supplier" wajib memilih "Ganti barang" atau "Potong tagihan" + alasan** (antrean QC & SPK).
   Ganti barang: PO kembali "Diterima sebagian" + tugas terima pengganti; tanpa Nota Debit. Potong tagihan: PO "Ditutup
   kurang" (bila sudah diterima penuh), tagihan supplier yang boleh dibuat = diterima − diretur.
4. Retur beli dari tolak QC yang **ditolak** → barangnya tetap di gudang sebagai **Rusak** (dulu menggantung "diretur").
5. **Kedatangan barang**: satu SJ untuk beberapa PT bisa dipecah otomatis jadi GRN per PT dari wizard.
6. **PO**: centang "Minta inspeksi" per baris; roll baris itu didraf ke gedung inspeksi. Bisa juga ditandai saat penerimaan
   (API; tombol layar penerimaan belum — §8).
7. **MD** bisa mengunduh lembar perbaikan master & ekspor produk.
8. Detail PO menampilkan "ganti barang"/"diretur (potong tagihan)" per baris; detail GRN menampilkan kedatangan saudara.

## 3. Keputusan implementer (beserta alasan)
1. **Nilai karantina retur = Rp0 sampai settle** — satu-satunya cara "nilai & jurnal saat settle" tanpa selisih subledger vs
   GL 1-1300 (subledger = Σ panjang × biaya roll) dan tanpa menyeret WAC (roll berbiaya 0 tidak ikut rata-rata).
2. Qty karantina saat pindai = **qty klaim**; qty hasil QC menimpa saat settle + mutasi `return_qc_adjust` (koreksi terlihat).
3. Kirim → tiba antar gudang sebelum settle: roll tetap di gudang asal sampai **tiba** (tidak memakai status transit
   transfer — status itu milik dokumen transfer), lalu pindah gudang dengan mutasi keluar/masuk.
4. Gagal membuat karantina sesudah pindai tidak membatalkan pindai (galat `stock_intake_error` di respons + log); settle
   lalu memakai jalur lama untuk roll itu → tetap tanpa jurnal ganda.
5. Efek D2 dieksekusi saat **retur beli disetujui** (sesuai rekomendasi audit "saat nota retur disetujui"); pilihan dicatat
   saat keputusan QC. Retur beli tolak QC lama yang belum punya pilihan disetujui seperti dulu (Nota Debit) — dilaporkan
   skrip data (4 di data acuan) untuk ditinjau pembelian.
6. Jurnal D2 per kasus (lihat §1.2): pembalik GR-IR **neto tanpa PPN** bila hutang belum lahir dari barang itu (ganti barang /
   belum ditagih); Nota Debit ke Hutang (bruto + PPN) bila sudah ditagih. Basis nilai = nilai retur beli lama (harga PO ×
   qty satuan PO). AP subledger (`returned_amount`) turun bruto pada potong tagihan (kedua kasus) karena `_po_financials`
   berbasis grand total PO.
7. Potong tagihan menutup-kurang PO hanya bila PO sudah `completed`; PO yang masih menunggu qty lain tetap terbuka (qty yang
   diretur tidak ditunggu lagi karena `received_qty` tidak dikurangi) — tercatat `remedy.po_result.po_effect`.
8. D9 dikelompokkan per **(PT × gudang)** karena aturan lama "satu GRN = satu gudang penerimaan PO" dipertahankan; foto SJ
   yang sama diunggah ke tiap GRN (peringatan foto ganda per PT, jadi tidak salah bunyi).
9. Penanda minta inspeksi berlaku sampai roll **pertama kali singgah** di gedung inspeksi (`journey.inspection_site`);
   sesudahnya rute mengikuti aturan biasa (SPK 4-point terbuka tetap menahan rute).
10. Status retur jual memakai tabel yang sudah ada (`return_state.TRANSITIONS`, modul murni) + penulis CAS terpisah — tidak
    membuat tabel kedua.

## 4. Tabel transisi yang disentuh (ringkas)
* **Roll karantina retur** (`inventory_rolls.return_intake.state`): `— →received` (pindai terima) · `received→received`
  (tiba) · `received→valued` (settle stok) · `received→reversed` (tolak/roll ditolak/tanpa stok/cutloss) · `valued→received`
  (koreksi per roll, retur tetap terbuka) · `valued→reversed` (reverse retur, jalur lama `restore_identity_roll`).
* **PO** (D2): `completed|partial|receiving|closed_short → partial` (ganti barang) · `completed → closed_short` (potong
  tagihan) · dibalik saat retur beli dikoreksi.
* **Tugas masuk**: tugas pengganti `→ waiting_goods` (baru, `ensure_remainder_task`) · `waiting_goods → cancelled` lewat
  `inbound_task_state.transition("cancel")` saat koreksi.
* GRN / retur jual / retur beli: §1.6.

## 5. Skrip perbaikan data (dibuat, dry-run bawaan; diuji di salinan)
`scripts/fix_data_2026_11_10_fix6_retur_masuk_stok.py --db <db> [--apply]` — hanya `kn_test_trial`/`test_database`;
DB lain (produksi) wajib `--allow-db <nama>` (keputusan pemilik).
| Langkah | Data acuan (dry-run) | Skenario sintetis "sebelum FIX-6" (1 retur dipindai di kode dasar) |
|---|---:|---|
| `return_intake_backfill` — retur terbuka yang rollnya sudah dipindai tetapi masih `delivered` → karantina retur (layanan yang sama, tanpa jurnal) | 0 | dry-run 1 → `--apply` 1 roll (quarantine, Rp0, `received`, 0 jurnal) → dry-run ulang 0 |
| `qc_return_without_remedy` — LAPORAN retur beli tolak QC tanpa pilihan | 4 (PRET-00037/-49/-69/-70) | — |
Jejak `migrations` (`fix_data_2026_11_10_fix6_retur_masuk_stok`). **Tidak** dijalankan ke DB bersama/produksi.

## 6. Hasil uji & perbandingan regresi (angka apa adanya)

### 6.1 Uji baru
| | dasar `main` (`c729f4e`) | FIX-6 |
|---|---:|---:|
| `test_fix6_keputusan_10nov.py` (16) | **16 gagal** | **16 lulus** |
| Jest `fix6Decisions.test.js` (5) | suite gagal (modul `ReturnRemedyChoice` belum ada) | **5 lulus** |

### 6.2 Pytest — 63 berkas lama (urutan sama, DB dipulihkan sebelum tiap putaran)
46 berkas FIX-3a + retur/GRN/QC/PO/AP/jurnal/akses: `test_l08_ln081_journey`, `test_l08_evidence_identity`,
`test_return_per_roll`, `test_uat23_roll_settlement`, `test_uat23_settle_preview_exchange`, `test_ln091_092_returns_exceptions`,
`test_lanjutan_sched_returns_interco`, `test_iter_sales_return_cancel_draft`, `test_l08_returnable_rolls`,
`test_iter265_r3r4r5`, `test_fix3b_outbound_integrity`, `test_role01_matrix_defaults`, `test_fe03_access_catalog`,
`test_fe04_fe05_access`, `test_f11_layar_return_screen_access`, `test_iter94_po_learning`, `test_iter260_board_returns`,
`test_posting_failures`, `test_l02_ln023_ar_ap_consistency`, `test_interco_g6`, `test_iter292_audit_fixes`,
`test_w2_targeted`, `test_uat24_f1`, `test_audit_bagian_iii`, `test_fix1_cakupan` (daftar lengkap di skrip putaran).

| | dasar `main` | FIX-6 (putaran akhir) |
|---|---:|---:|
| lulus / gagal / error / lewat | 481 / 64 / 19 / 41 | **481 / 64 / 19 / 41** |
| himpunan gagal+error | 83 | **83 (identik)** |
| hanya gagal di FIX-6 | — | **0** |
| `test_iter117_p09` (proses terpisah) | 18 lulus | 18 lulus |
| `test_iter118_p10` (proses terpisah) | 8 lulus | 8 lulus |

Putaran pertama FIX-6: 3 uji hanya gagal di FIX-6 — semuanya perilaku yang memang diubah keputusan pemilik → **uji
disesuaikan** (bukan kode):
* `test_f14_spk_one_decision::test_terima_sebagian_roll_tertentu_diretur_ke_supplier` — tutup SPK "retur ke supplier"
  tanpa pilihan kini 400 (D2); uji kini memeriksa 400 itu lalu mengirim `return_remedy` + alasan.
* `test_l08_ln081_journey::test_t01_jakarta_transit_qc_by_scans_only` — dulu mengunci "roll tetap `delivered` sampai
  settle"; kini memeriksa karantina retur bernilai nol di gudang tiba (D5).
* `test_l08_ln081_journey::test_replacement_shipping_is_not_return_arrival` — gagal berantai dari uji di atas; lulus sesudahnya.
Gagal lama (sama persis di dasar & FIX-6) berasal dari data acuan/asumsi uji lama (mis. supplier nonaktif di
`test_iter258_purchase_e2e_and_recon`, 11 error setup `test_p03_transfer_receipt`) — tidak disentuh.

### 6.3 Jest & ESLint (kontainer `node:20` sementara, `node_modules` dari volume `kn-dev_fe_node_modules` read-only, CI, `--maxWorkers=1`)
14 berkas terarah (semua uji yang mengimpor layar yang diubah + fixture akses): `navAccess`, `serverAccessReach`,
`f11LayarOperatorView`, `f14SpkOneDecision`, `fe07ReturnErrors`, `fix6Decisions`, `phase3P8Activation`, `phase4R3`, `phase4R4`,
`phase5MakloonRolls`, `trial22Okt`, `uat24F0`, `uat26D2Decisions`, `ui05UnitsStates`.

| | dasar `main` | FIX-6 |
|---|---|---|
| Suite | 13 lulus + 1 gagal (`fix6Decisions`: modul belum ada) | **14/14 lulus** |
| Uji | 119 lulus | **124 lulus** (119 + 5 baru) |
`f14SpkOneDecision` (Jest) disesuaikan: tombol Tutup SPK mati sampai pilihan retur + alasan diisi, lalu payload memuat
`return_remedy`. Pesan `ECONNREFUSED` di konsol berasal dari `f11LayarOperatorView` dan muncul sama di dasar. ESLint pada 12
berkas FE yang diubah/baru: **0 error**, 1 peringatan (sama dengan dasar). Suite Jest penuh tidak dijalankan (memori Docker —
lihat kejadian di kepala laporan).

### 6.4 Guardrail (`PYTHONUTF8=1 python scripts/guardrails/verify_*.py`, host; `verify_state_machine` tidak dijalankan)
Kode keluar **43/43 identik** dasar vs FIX-6; jumlah pelanggaran tidak naik:
* `verify_atomic_claim` 6 → 6 (putaran awal "BELUM DITINJAU" 77 → 78: endpoint baru `inspection-request` → diubah ke
  `find_one_and_update` berprasyarat status + dicatat di `REVIEWED`; kini 77 = dasar).
* `verify_auth_coverage` 28 = 28 (cek 1.727 → 1.730: 3 endpoint baru berizin), `verify_qty_dual` 28 = 28,
  `verify_to_list_bound` 20 = 20 (hanya nomor baris `gl_service` bergeser), `verify_numeric_bounds` HARD 3 = 3,
  `verify_entity_label` 2 = 2, `verify_line_scope` 1 = 1, `verify_no_secrets` 8 = 8.
* Hijau tetap hijau: **`verify_ui_standard` (4.316 cek, 0)**, **`verify_scope_guard`**, **`verify_access_catalog_nav` (0
  temuan)**, `verify_status_history` (9), `verify_codebase_map`, `verify_role_label`, `verify_uom_vocab`, dll.

## 7. Berkas berisiko bentrok
* **FIX-7 (performa daftar/pencarian/log)** — `routers/goods_receipts.py` (2 endpoint baru di atas `photo-check`; daftar GRN
  tidak disentuh), `services/stock_figures.py` (hanya pembaca "akan datang" retur — rumus tidak diubah),
  `services/vendor_bill_service.py` (2 baris `received`).
* **FIX-8 (komponen UI baku / tampilan tersimpan)** — tidak menyentuh komponen baku; komponen kecil baru
  `features/wms/ReturnRemedyChoice.jsx` memakai token baku (`text-fs-12`, `text-kn-*`, `form-input`).
* Router/layanan bersama FIX-1/3a/3b: `routers/inbound_receiving_extra.py` (endpoint baru + 2 argumen qc-decision),
  `routers/inspections.py`, `routers/sales_returns.py` (submit/buang draf → CAS), `routers/purchase_orders.py`
  (`_inspection_request_from_po`), `services/qc_service.py`, `inspection_service.py`, `inbound_complete_service.py`,
  `putaway_draft_service.py`, `return_service.py`, `return_identity_service.py`, `return_roll_settlement_service.py`,
  `return_rolls_service.py`, `return_journey_service.py`, `return_cutloss_split_service.py`, `purchase_return_service.py`,
  `goods_receipt_service.py`/`_close_service.py`/`_ocr_service.py` (`cas()` + argumen `action`), `gl_service.py`
  (fungsi baru `post_purchase_return_grir`), `permissions_config.py`, guardrail `verify_atomic_claim.py` (`REVIEWED`).
* FE: `QCInspection.jsx`, `InspectionDetailPanel.jsx`, `POCreateForm.jsx`, `PODetailPanel.jsx`, `ReturnQuarantinePanel.jsx`,
  `GrnCreateWizard.jsx`, `GrnDetail.jsx`, `grnApi.js`, `inventoryConstants.jsx`.
* `CODEBASE_MAP.md` tidak dibangkitkan ulang untuk 5 modul baru (guardrail `codebase_map` tetap hijau).

## 8. Sisa (belum dikerjakan / butuh keputusan)
1. **Tombol "Minta inspeksi" di layar penerimaan** (HP/desktop/GRN) — server & API siap (`POST /inbound/tasks/{id}/inspection-request`),
   layar baru di baris PO.
2. Retur beli **manual** (bukan tolak QC) yang disetujui sebelum PO ditagih masih memakai jurnal lama Dr GR-IR **bruto** /
   Cr PPN Masukan (PPN dibalik sebelum diakui) — kebiasaan lama, tidak diubah agar uji/alur lain tetap; usul: pakai
   `post_purchase_return_grir` + `returned_qty` juga untuk retur manual (perlu persetujuan Finance).
3. `_po_financials` & `sync_po_billing` untuk PO `closed_short` masih berbasis grand total penuh (kebiasaan lama semua PO
   tutup-kurang) — angka "sisa hutang" layar PO bisa lebih tinggi dari rekonsiliasi tutup-kurang.
4. Karantina retur yang sedang **ditahan** (Tahan roll) tidak dibalik otomatis saat retur ditolak (harus lepas tahanan dulu).
5. Selama kirim → tiba antar gudang sebelum settle, roll tetap tercatat di gudang asal (bukan "dalam perjalanan").
6. Kedatangan lintas PT dari wizard memerlukan supplier punya PO terbuka di PT aktif (daftar mitra langkah 1 masih per PT
   aktif); detail GRN PT lain dibuka atas nama PT dokumennya (registri FIX-1).
7. `status_history` seragam kini: tugas masuk/keluar, transfer, GRN, retur jual, retur beli. PA, SPK, opname masih jejak sendiri.
8. Menjalankan skrip data ke produksi + peninjauan 4 retur beli tolak QC tanpa pilihan — pemilik/pembelian.

## 9. Kebersihan
Kontainer `kn-tmp-fix6-mongo/-be/-fe` (+ volume anonim Mongo milik `kn-tmp-fix6-mongo`) dihapus sesudah uji. Tidak ada
tulisan ke DB bersama, stack `kn-uji-*`, atau data UAT "test"; `verify_state_machine.py` tidak dijalankan; tanpa peramban;
`docs/reviews/TRACKER.md` tidak diubah; tidak push/merge.

---

## Ringkasan untuk koordinator
* **Diterapkan (keputusan pemilik 10 Nov):** **D5** retur penjualan masuk stok saat dipindai sebagai karantina retur (nilai
  Rp0, jurnal tetap saat settle — settle menilai roll yang sama, tanpa roll/mutasi/jurnal ganda; tolak/roll ditolak/outcome
  tanpa stok/cutloss membalik). **D2** tolak QC + retur supplier wajib pilih *ganti barang* (PO dibuka lagi + tugas terima
  sisa, pembalik GR-IR neto, AP tetap) / *potong tagihan* (AP via Nota Debit lama, 3-way match = diterima − diretur, PO tutup
  kurang, pembalik GR-IR neto bila belum ditagih) — beralasan K-14 & beraudit; koreksi & tolak retur beli membalik dengan
  jelas. **D9** satu SJ untuk beberapa PT → GRN per PT (× gudang) dengan pagar PT & lokasi FIX-1. **Minta inspeksi** di baris
  PO & saat penerimaan (API) → draf PA ke gedung inspeksi. **MD** `product.export`. **Tabel transisi** daftar-izin + CAS +
  `status_history`: GRN (`grn_state`), retur jual (`sales_return_transition` di atas `return_state`), retur beli
  (`purchase_return_doc_state`). Temuan: B2a FLW-IN-09 (D5), FLW-IN-11, FLW-IN-14, STM-IN-07 (dokumen ini), R→W retur #83/#84.
* **Uji:** pytest baru 16 (dasar 16 gagal → FIX-6 16 lulus); regresi 63 berkas: 83 gagal+error dasar = 83 FIX-6 (himpunan
  identik, 0 hanya-FIX-6) sesudah 3 uji lama disesuaikan dengan keputusan (2 sebab + 1 berantai); p09 18/18, p10 8/8 keduanya.
  Jest 14 suite: dasar 13+1 gagal (modul baru) → FIX-6 14/14 (124 uji); ESLint 0 error. Guardrail: kode keluar 43/43
  identik, tidak ada angka merah naik (`atomic_claim` 77 = 77 sesudah endpoint baru ditinjau); `ui_standard`, `scope_guard`,
  `access_catalog_nav` hijau.
* **Skrip data:** `scripts/fix_data_2026_11_10_fix6_retur_masuk_stok.py` (dry-run bawaan; acuan 0 roll + 4 retur beli tolak
  QC tanpa pilihan dilaporkan; skenario sintetis 1 → 0, tanpa jurnal). Belum dijalankan ke DB bersama/produksi.
* **Keamanan produksi:** tanpa migrasi wajib; izin MD masuk lewat sinkron izin saat start; retur lama yang sudah dipindai
  tetap diselesaikan aman lewat jalur lama sampai skrip dijalankan; retur beli tolak QC lama tanpa pilihan disetujui seperti dulu.
* **Sisa:** tombol minta inspeksi di layar penerimaan, jurnal retur beli manual sebelum ditagih (PPN), angka hutang PO tutup
  kurang, karantina retur yang ditahan, roll retur dalam perjalanan antar gudang, status_history PA/SPK/opname.
* **Lingkungan:** Docker Desktop macet & mulai ulang sendiri ±01.07–01.23 WIB (semua kontainer paket berhenti); putaran regresi
  diulang penuh sesudahnya.

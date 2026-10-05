# Implementasi iterasi — 2026-10-04 · W2 P00–P07

- **Iterasi / fase / ID:** P00 (rekonsiliasi) + P01–P07; ID W2-001 … W2-025. P08 (9 kebutuhan klien) dan P09 belum dikerjakan.
- **SHA sebelum / sesudah:** basis GitHub `main` = `8934e12` (riwayat job: `60cda94` checkpoint platform). Perubahan aplikasi **belum di-commit** ke `main` — jalankan `KN_COMMIT_MSG="Wave2 P00-P07" bash scripts/git_sync_check.sh --fix` lalu Save to GitHub; SHA hasil commit itu = SHA kandidat validasi.
- **Snapshot audit paket:** `ea874d3b…`. Repo sudah berubah (Wave1 P10–P21). Baseline paket TIDAK diubah.

## P00 — rekonsiliasi terhadap kode terbaru & Wave1 (`audit/tracker.json`)

| ID | Kondisi di kode kandidat sebelum patch | Keputusan |
|---|---|---|
| W2-008 | Wave1 **AX-04** sudah menambah filter `owner_entity_id` + guard update pada cabang `roll_ids` (`roll_service.reserve_rolls_for_wh_transfer`). Masih bocor bila owner hasil resolver = B (akar W2-006). | Tidak ada patch tandingan; ditutup via kontrak W2-006 + regression baru. |
| W2-009 | AX-04 sudah memanggil `rebuild_balance` di cabang eksplisit. | Regression baru (reserved 20 / available 0). |
| W2-024 | GN-06 sudah punya postcondition `MaterialShortage` + kompensasi; cap 5000 masih ada. | Cap dihapus (kursor utuh). |
| W2-021 (financial statement) | GN-12 sudah iterasi kursor di `financial_statement_service._aggregate`. | TB, buku besar, saldo rekening diperbaiki. |
| W2-016 | P20 APAR-02 menambah precheck (non-atomik). | Diganti CAS atomik. |
| Lainnya | Masih reproducible pada source. | Dipatch. |

## Akar masalah & perubahan

| ID | File | Perubahan |
|---|---|---|
| W2-006 | `services/roll_service.py::resolve_stock_owner`, `routers/cycle_count.py`, `routers/transfers.py` | Resolver menerima `allowed_owners` (kontrak otorisasi): prefer dipertahankan walau tanpa stok, tidak pernah fallback ke owner lain; explicit di luar scope 403; tanpa kandidat sah 400. Semua pemanggil (opname + transfer) memakai. Submit/approve opname menolak sesi lama berisi item owner asing (403) sebelum membaca expected. |
| W2-007 | `routers/cycle_count.py::reject_session` | Reject = CAS `status=submitted` & tanpa `saga_lock` (protokol sama dengan approve). Kalah → 409 tanpa metadata/audit. |
| W2-010 | `routers/rfid.py::get_reads`, `services/rfid_service.py::list_reads` | Scope `rfid_reads` (registry `owner_entity_id`) diambil dari sesi server dan selalu digabung ke query. Insiden/device TIDAK diubah (observasi kebijakan F02–F07). |
| W2-025 | `routers/rnd.py::_sample_guard`, `_spec_guard` | `line_scope.assert_can_touch` pada guard detail → berlaku utk detail, patch dan semua aksi turunan yang memakai guard. Aturan legacy (akun tanpa lini / dokumen tanpa lini = tidak dikunci) dipertahankan. |
| W2-013 | `inbound_complete_service.py`, `goods_receipt_service.py`, `goods_receipt_close_service.py::_post_task` | Manifest roll `to_list(None)` (tanpa cap 500/2000); baris GRN tidak `done` bila masih ada roll `receiving` (409, GRN tetap closing). |
| W2-014 | `services/qc_service.py` | Retur QC: qty dasar (m) dikonversi ke satuan harga PO per potongan (kg dari berat terukur proporsional; satuan lain via `uom_service.convert`). Dokumen menyimpan `quantity/unit` (PO) + `qty_base/unit_base`. |
| W2-019 | `services/roll_service.py::insert_child_roll` | Satu pintu split: berat induk dibagi proporsional panjang (`weight_provenance=estimated_proportional`), sisa tetap di induk → total konservatif. Berlaku untuk semua caller split. |
| W2-001 | `services/makloon_order_service.py::receive_step` | Basis costing = Σ panjang roll terukur; roll terakhir menyerap residual pembulatan. Replay: roll 120.0002 vs jurnal 120 (sisa < Rp0,01 karena presisi `unit_cost` 4 desimal di `create_inbound_roll`). |
| W2-002 | idem | Gudang hasil efektif (sesudah fallback) + gudang kiriman sebagian divalidasi `warehouse_scope_service.assert_usable` sebelum klaim/efek. |
| W2-003 | idem + `goods_receipt_close_service._post_mko` | Kiriman sebagian menyimpan `warehouse_id`; roll lahir di gudang kedatangannya. Entry lama tanpa gudang diresolusi dari GRN asal; tak terlacak → 409 (tidak menebak). |
| W2-004 | `routers/vendor_bills.py::cancel_vendor_bill`, `VendorBillDetailPanel.jsx` | Bill `makloon_service` posted tidak bisa dibatalkan generik (409, arahkan ke koreksi sumber/potong bon); tombol disembunyikan. Bill umum tetap. |
| W2-005 | `vendor_bills.py` (pay), `makloon_claim_service.py` | Guard pembayaran memakai `$grand_total` TERKINI; potong bon = `find_one_and_update` atomik (`amount_paid+potongan ≤ grand`) SEBELUM jurnal, kompensasi bila jurnal gagal. |
| W2-024 | `services/production_service.py::_consume_material` | Kursor utuh tanpa cap 5000 (postcondition GN-06 tetap). |
| W2-015 | `ar_receipt_service.py`, `gl_service.post_deposit_only_receipt / reverse_deposit_only_receipt` | Kwitansi murni deposit → jurnal reklas nonkas (Dr 2-1400 / Cr 1-1200, porsi berpiutang), idempotent, dibalik saat void; gagal → `gl_status=failed` + repost. Tanpa kas fiktif. |
| W2-016 | `ar_receipt_service.void_receipt` | Penarikan kelebihan bayar dari deposit = CAS di awal; gagal → 409 tanpa membalik SO/kas. |
| W2-017 | `ar_receipt_service.create_receipt` | Deposit direservasi (CAS) sebelum alokasi SO; gagal tengah → kompensasi. |
| W2-018 | `ar_receipt_service.void_receipt` | Tulis ulang `payments` hanya bila array tak berubah sejak dibaca (CAS + retry). |
| W2-020 | `services/return_service.py::settle_return` | Buku kas refund gagal → 409, status TIDAK final, nota kredit/stok disimpan durable (`settlement_pending`); retry melengkapi kas tanpa CN/GL/stok ganda. |
| W2-021 | `gl_service.trial_balance / account_ledger`, `bank_service._txns_for` | Tanpa cap 50.000 / 5.000. |
| W2-022 | `hr_payroll_service.pay_run` | Setelah jurnal, catat `cash_transactions` (ref `payroll_run`, idempotent). Gagal → kembali `posted`, retry aman. |
| W2-023 | `gl_service.pay_payroll_run` | Akun sumber wajib anak `1-1000` (kas/bank) aktif; tidak ada fallback diam-diam. |
| W2-011 | `rfid_incident_service._transition` | CAS status; kalah → 409. |
| W2-012 | `rfid_incident_service.create_from_read` | `dedupe_key` (epc\|device) + indeks unik parsial `uniq_open_incident_dedupe`; dilepas saat ack/resolve atau di luar jendela. |

## Bukti

| Skenario | Hasil | Perintah |
|---|---|---|
| Regression service-level (W2-006/007/008/009/011/012/014/016/017/018/019/021/022/023) | **25/25** | `cd /app/backend && python ../docs/audit/wave-2/iterations/2026-10-04-W2-P00-P07/regression_w2.py` → `regression_results.json` |
| Regression HTTP (W2-010, W2-025, W2-004) | **6/6** | `regression_w2_http.py` → `regression_http_results.json` |
| Agen uji (W2-015, W2-017, W2-020, W2-022/023 + smoke + UI vendor bill) | **8/8 + UI** | `test_w2_targeted.py`, `testing_agent_iteration_140.json` |
| Replay baseline (Mongo sintetis port 27919, salinan `iterations/2026-10-04-W2-replay`) | makloon F01 nilai ≈ jurnal (selisih 0,0002), F02 → 404 tanpa efek, F03 → 409 (fixture partial lama tanpa gudang/GRN — sesuai kontrak baru); klaim F01 409/AP utuh, F02 409, F03 paid ≤ grand; GRN F01 501/501, F02 0 tertinggal; produksi F01 5001 terkonsumsi | `replay_obs/*.obs.txt` |
| Replay terblokir fixture (bukan regresi patch) | `wave2_qc_flow` (rencana inspeksi Wave1 wajib), `wave2_cash_refund`/`sales_flow` (SO kini reservasi saat verifikasi, bukan create), `wave2_ar` (COA sintetis tanpa 1-1200) | `replay_obs/*.fixture_blocked.txt` |

## Data dan operasi

- Indeks baru: `rfid_incidents.dedupe_key` unik parsial (dibuat otomatis saat insiden pertama). Insiden open lama tidak punya `dedupe_key` → tidak ikut dedupe atomik sampai ditutup (aman).
- Field baru: `purchase_returns.items[].qty_base/unit_base`, `inventory_rolls.weight_provenance`, `makloon_orders.steps[].partial_receipts[].warehouse_id`, `sales_returns.settlement_pending`, `hr_payroll_runs.cash_txn_id`.
- Data historis (belum dimigrasi, perlu dry-run + persetujuan Finance): retur QC lama berunit kg dengan qty meter; roll hasil split lama berberat ganda; payroll paid tanpa cash_transactions; kwitansi murni deposit tanpa jurnal reklas; retur refund final tanpa buku kas; partial makloon lama tanpa gudang.

## Serah-terima

- **ready_for_validation:** semua ID kecuali yang di bawah.
- **Catatan:** W2-001 sisa sub-sen (presisi unit_cost); W2-003 belum diuji end-to-end GRN HTTP multi-gudang (hanya kontrak service + replay); W2-013 recovery GN-11 tidak diubah; W2-008/009 bergantung patch Wave1 AX-04.
- **Belum:** P08 (W2-REQ-01..09) — kebutuhan bisnis/kebijakan, tidak dikerjakan sesi ini; P09 validasi gabungan oleh auditor. Browser UAT hanya vendor bill; hardware RFID tidak diuji.

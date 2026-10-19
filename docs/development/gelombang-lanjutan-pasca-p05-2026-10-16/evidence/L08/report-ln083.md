# LN-083 — Batas waktu & syarat retur (in_progress, 2026-10-18)

Navigasi: **Kebijakan Retur Jual** (panel "ASUMSI SEMENTARA"). Detail retur penjualan menampilkan panel kelayakan.

## Sebelum → sesudah
- **Sebelum:** jendela bawaan 30 hari dari tanggal SO/kirim. Opsi `link_to_supplier_window` mengambil deadline **terketat** (customer bisa tertolak karena supplier kedaluwarsa), dan tanggal supplier memakai `last_received_at` PO.
- **Sesudah** — `settings.returns` (asumsi, dapat diubah): `customer_window_days 21`, `supplier_window_days 21`, `klr08_hangtag_cut pending|review|reject`, `klr09_end_event pending|request|goods_received`.
  - Customer: dihitung dari **SJ** (`reference_source` disimpan: jenis, nomor, tanggal).
  - Supplier: dihitung **per receiving roll** (`supplier_linked.receivings`), sepenuhnya independen. Lewatnya batas supplier hanya menjadi peringatan dan tidak pernah memblokir customer.
  - KLR-08/KLR-09 = `pending` → `pending_decisions` + `decision: pending_decision`; tidak otomatis diterima atau ditolak. Kasus di luar batas tetap `outside_window`.
  - Snapshot retur menyimpan `decision`, `reference_source`, `pending_decisions`, dan `assumptions`. Tanggal histori tidak diubah.
- **Endpoint:** `GET /api/sales-return-policies/eligibility` menerima `hangtag_missing`, `cut_by_customer`. Baru: `GET /api/return-policies/supplier-deadlines?po_id=` (izin `purchase_return.view`).

## Uji
- `test_ln083_t01_customer_independent_of_supplier`, `test_ln083_t02_supplier_deadline_per_receiving`, `test_ln083_t03_pending_rules_not_assumed`. Testing agent iteration_228 lulus.

## Belum
- Alur pengecualian (alasan + bukti) belum dibuat.
- Penanda hangtag/potong belum menjadi kolom input di form retur (baru parameter API).

## Update 2026-10-19 (sesi lanjutan) — KLR-08 & KLR-09 diterapkan
- **KLR-09:** kelayakan customer dinilai pada **tanggal pengajuan** (`on_date` = waktu retur dibuat; `policy_eligibility.evaluated_on = request_date`, `request_date` disimpan). Pending KLR-09 dihapus. Supplier: `purchase_returns.claim_window_check` dihitung pada **tanggal klaim diajukan** (`submitted_at`/`created_at`), dicatat saat kirim ke supplier — hanya peringatan (`late_roll_ids`). Disposisi CST→supplier (LN-093) menilai lewat-batas pada hari keputusan "retur ke supplier" (= klaim dikirim).
- **KLR-08:** checklist `hangtag_missing`, `cut_by_customer`, `replacement_proof` (bukti pengganti) di form retur → `warnings` + `condition_review_required`; **tidak memblok**. Gerbang settle 409 KLR-08 & pengecualian jenis `condition` dihapus. Saat settle, bila kondisi ditandai, catatan keputusan Finance wajib (≥5 huruf) dan tersimpan di `decision.condition_decision`.
- Setelan `klr08_hangtag_cut`/`klr09_end_event` dihapus dari Pengaturan & panel Kebijakan Retur.
- **Uji:** `test_ln083_t03_klr08_checklist_warning_klr09_request_date`, `test_ln083_klr08_condition_is_warning_finance_note_required` (lulus, -n0).
- **Belum:** D1 (jendela retur di 4 tempat) menunggu persetujuan owner — tidak diubah.

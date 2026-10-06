# Gelombang 3 · Fase 03 — status implementasi (2026-10-06)

Status tertinggi yang dipakai agent: `implemented_pending_validation`.

Keputusan user (2026-10-06): V3-CF-01 hanya bagian tunai masuk arus kas (sisanya non-kas) · V3-PO-02 qty PO boleh diamandemen ke qty diterima + re-approval · D4-FIN-04 realisasi = barang terkirim (tanggal & HPP saat kirim), nilai pesanan = estimasi terpisah · D4-CASH-01 kolom tetap "jenis kas" (data lama diisi otomatis sekali) · D4-DATE-01 semua periode WIB.

| ID | Status | Perubahan |
|---|---|---|
| D4-PLAN-01 | implemented_pending_validation | `_reorder_supplier` mengembalikan `added`/`existing_pr_qty`; rencana mencatat qty pasokan BARU (reaffirm PR terbuka = 0) |
| D4-PLAN-02 | implemented_pending_validation | `_validate`: produk ganda ditolak; alokasi PT sama dijumlah sebelum dibatasi |
| D4-PLAN-03 | implemented_pending_validation | `decide_plan`: penuh/sebagian dari qty yang benar-benar tercatat; `error` & `remaining` disimpan |
| D4-SALES-01 | implemented_pending_validation | `_targets_in_scope`: target per entitas; target lama tanpa entitas hanya untuk entitas induk sales |
| D4-SALES-02 | implemented_pending_validation | Home sales: kredit pelanggan & SO terbaru dibatasi entitas aktif |
| D4-SALES-03 | implemented_pending_validation | basis komisi per-SKU memfilter `entity_id` SO |
| D4-FIN-01 | implemented_pending_validation | Control Tower tanpa parameter = entitas aktif (AR, jurnal, pembanding sama) |
| D4-COA-01 | implemented_pending_validation | `_accounts_map` multi-entitas menyertakan akun khusus entitas |
| D4-AI-01 | implemented_pending_validation | AP analytics: `grand_total` 0 → `total_amount` (sama dgn `bill_financials`) |
| D4-COMM-BOUNDS-01 | implemented_pending_validation | Patch kontrak & barang supplier memakai batas ge/le yang sama dengan Create |
| D4-BUD-EDIT-01 | implemented_pending_validation | update anggaran: tahun 2000–2999 + keunikan kombinasi hasil merge + CAS |
| D4-UOM-BF-01 | implemented_pending_validation | backfill `qty_rolls` = roll unik yang benar-benar ada |
| V3-DATE-01 | implemented_pending_validation | batas bawah periode memakai tanggal saja (laporan keuangan, arus kas, anggaran, profitabilitas) |
| D4-FIN-02 | implemented_pending_validation | forecast kas memakai AR kanonis (`_eligible_outstanding`, `term_days`); termin 0 eksplisit tetap 0 (berlaku juga untuk aging) |
| D4-FIN-03 | implemented_pending_validation | pendapatan per order = grand_total − ppn_amount dialokasikan proporsional ke baris |
| V3-PO-01 | implemented_pending_validation | tugas selisih per baris (`line_key`), diperbarui saat penerimaan berubah, `obsolete` bila tertutup; saran qty dari PO terkini |
| V3-PO-02 | implemented_pending_validation | baris ber-penerimaan boleh diamandemen qty TEPAT ke qty diterima; harga/satuan/diskon tetap terkunci. Keputusan user (2026-10-06, opsi a): amandemen qty→qty diterima SELALU minta persetujuan ulang berapa pun nilainya (rantai dipaksa level-1 manager, `approval_reason` memuat `qty_to_received`) |
| V3-PO-03 | implemented_pending_validation | tugas `pending_amendment` selesai hanya bila PO sudah disetujui DAN qty baris = qty diterima; dipanggil juga sesudah approval penuh |
| V3-CF-01 | implemented_pending_validation | `split_journal_cash`: kas bersih jurnal dialokasikan pro-rata HANYA ke lawan akun searah kas; sisanya + lawan berlawanan arah = nonkas (diungkap bila investasi/pendanaan). Fixture aset kas 40 + kredit 60 → CFI −40 / CFO 0 / nonkas −60. Field baru `allocation: pro_rata_cash_side`; `method` tetap |
| D4-FIN-04 | implemented_pending_validation | profitabilitas: `totals/by_*/monthly` = REALISASI dari surat jalan (porsi nilai pesanan, tanggal kirim WIB, HPP snapshot roll saat dispatch; fallback WAC). Pesanan lama shipped/done tanpa surat jalan diakui per pesanan (`legacy_orders`). `estimate` = nilai pesanan (tanggal SO, WAC kini) terpisah. Label UI diperbarui |
| D4-CASH-01 | implemented_pending_validation | `bank_accounts.cash_type` (kolom tetap). Backfill sekali saat startup (hanya yang kosong): mayoritas riwayat transaksi (termasuk void) → bila tak ada, dari `account_type` (cash→kas_kecil, bank→kas_besar), `cash_type_source` dicatat. Ringkasan kas memakai `account_cash_type`; saldo awal kas kecil per entitas ikut walau tanpa transaksi. Badge jenis kas di kartu rekening |
| D4-DATE-01 | implemented_pending_validation | `sales_force._in_period` mengonversi timestamp ke tanggal WIB (`to_wib_date`); Home `_current_month/_today_prefix/_month_progress` = WIB; penjualan hari ini memakai rentang UTC dari batas WIB; anchor riwayat komisi WIB |

Rekap: 22 ID — 22 implemented_pending_validation, 0 open.
Dampak tambahan: rekening tipe `cash` tanpa transaksi kas kecil kini dihitung saldo awalnya sebagai kas kecil (dulu kas besar) — selaras dengan jurnal saldo awal 1-1110. Rekonsiliasi bank `_book_query` ikut memakai `cash_type` rekening yang kini terisi.
Bukti uji: `tests/test_g3_phase03.py` 15/15 (DB_NAME=g3_audit_phase03, `-n 0`); iteration_167 (12 tes service + 16 smoke API live lulus; V3-PO-01/02/03 ditambahkan sesudahnya, diuji pytest service saja). Regresi Fase 01/02: 65/65 + 15/15.
Dampak ke konsumen lain: `customer_service._term_days` dipakai ±21 tempat — termin 0 eksplisit kini 0 hari (sebelumnya 30).

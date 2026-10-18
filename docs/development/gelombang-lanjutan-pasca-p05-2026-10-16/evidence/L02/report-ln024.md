# LN-024 — Utang/piutang antar-PT, bayar per transaksi (in_progress, 2026-10-18)

Navigasi: **Transaksi Antar Entitas → tab Jadwal Bayar** (izin `interco_finance.view`; form cutoff hanya admin via `PUT /api/settings`).

## Sebelum → sesudah
- **Sebelum:** settlement boleh *netting* (saling hapus IC-AR/IC-AP) dan pembayaran sebagian. Tidak ada daftar jadwal bayar per transaksi.
- **Sesudah:** pengaturan baru `settings.interco_payment` = `{allow_netting:false, require_full_payment:true, cutoff_day:null, payment_day:null, basis:null}`.
  - `POST /api/interco/settlements` menolak netting (400 "Netting dinonaktifkan") dan pembayaran sebagian (400 "harus dibayar penuh"). Transaksi arah berlawanan tidak ikut dihapus.
  - UI settlement tidak lagi menawarkan netting, dan kolom nilainya hanya-baca (penuh).
- **Endpoint baru** `GET /api/interco/payment-schedule?payer_entity_id=&payee_entity_id=`:
  - Baris per transaksi (tidak digabung) dengan sisa, umur, tanggal terima, dan tanggal invoice. Ada ringkasan per pasangan PT (pembayar→penerima, saldo tiap PT terpisah).
  - KLX-03 belum diputuskan → `cutoff_status: pending_KLX-03` dan `period: null`. Tanggal tidak diasumsikan.
  - Setelah cutoff, tanggal bayar, dan basis (terima/invoice/dokumen) diisi → transaksi s.d. cutoff masuk periode bulan itu, setelah cutoff masuk bulan berikutnya. Nilai ini ditandai **ASUMSI** sampai owner memutuskan.
- Export: dataset "Transaksi Antar-PT (per sisi)", "Pembayaran Antar-PT", dan "Saldo Antar-PT per Pasangan".

## Uji
- `tests/test_lanjutan_sched_returns_interco.py::test_ln024_t01_t02_per_transaction_no_netting`, `::test_ln024_t03_cutoff_pending_then_configured`. Testing agent iteration_228 lulus.
- `tests/test_interco_g6.py` test_10/11 disesuaikan (netting/sebagian → 400, pelunasan penuh transfer). Jangan dijalankan di DB demo karena test ini menghapus koleksi interco.

## Belum
- T01 bagian "stock owner berpindah saat diterima" memakai alur Tugas Gudang yang sudah ada. Di test, penerimaan disimulasikan, jadi belum diuji ulang end-to-end.
- KLX-03 tetap pending. Reviewer dan owner belum ada.

## 2026-10-18 — Pengingat bayar
- Job scheduler `interco_payment_reminder` (tiap jam). Notifikasi ke peran **finance** PT pembayar bila `pay_date` ≤ `reminder_days` (bawaan 3) hari lagi, satu kali per transaksi × tanggal bayar.
- Tidak berjalan selama cutoff KLX-03 belum dikonfigurasi. Isian "Ingatkan (hari sebelum)" ada di tab Jadwal Bayar.
- Tes: `test_ln091_092_returns_exceptions.py::test_ln024_payment_reminder_job`.

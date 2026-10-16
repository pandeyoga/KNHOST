# Laporan Fase L05 — status `in_progress` (2026-10-16, agent E1)

Belum ber-SHA. Acceptance tetap `not_run`; hasil lokal dicatat di `actual_result`.

## Navigasi aktual
- **Inspeksi (`?view=inspections`) → SPK → baris roll → "QC · 4-point & ukur":**
  - Isi panjang diinspeksi (yard), lalu tambah kejadian cacat: interval 15 yd, kode, poin, jumlah, keterangan.
  - Ringkasan interval: 0–150 yd, dan berlanjut bila roll lebih panjang.
- **Random check:**
  - Tombol `ins-random-check-button` → scan roll fisik (`ins-random-scan`), atau pilih gudang + jumlah acak.
- **SPK Baru → jenis "Inspeksi Barang Pengganti":**
  - Wajib scan/ketik roll PENGGANTI (`ins-replacement-rolls`).

## LN-051 — form per interval

**Sebelum:** cacat hanya berupa jumlah per nilai poin. Tidak ada posisi, kode, atau panjang inspect.

**Sesudah:**
- Item cacat memuat `{interval, code, point_value, count, note}` dengan `from_yard`/`to_yard`.
  - Jumlah interval = max(10, ceil(panjang/15)), tanpa batas 150.
  - Setiap kejadian disimpan sebagai baris sendiri.
- Form menyimpan `{inspect_length_yard, stock_qty, stock_unit, header}`.
  - Header diambil dari sumber: customer, supplier, jenis kain, artikel, SKU, roll, warna internal/supplier, tanggal, dokumen sumber.
- Baris SPK menyalin `defects`, `inspect_form`, `grade_rule`, sehingga riwayat tidak berubah bila roll diinspeksi ulang.

**Schema:**
- `RollDefectInput` += `interval`, `code`.
- `InspectionLineInspect` += `inspect_length_yard`.
- Kompatibel ke belakang (ringkasan tanpa posisi tetap bisa).

## LN-052 — aturan & versi
- Rumus dibiarkan tetap; KLX-02 masih pending.
- Setiap hasil menyimpan `rule {version 4point_sum_v1, status candidate_unvalidated, pending_decision KLX-02, thresholds, grades}` dan `raw_defects_input`.
- UI menandai hasilnya sebagai "kandidat".
- T01/T02 menunggu contoh hitung resmi client (KLX-02).

## LN-050 — sumber antrean
- **T03:** random check dari scan sah (no. roll/EPC), dengan cakupan badan usaha.
- **T02:** SPK pengganti memakai roll pengganti eksplisit dan menolak roll retur.
  - Alur tukar barang yang menghasilkan roll pengganti adalah L09; uji E2E menunggu itu.
- **T01: BELUM.** Checkout belum punya "Request QC" (tidak/seluruh/sampling) dan pagar dispatch.
  - Butuh field SO, jenis SPK `sales_order` dari roll alokasi terbaru, dan pagar di dispatch.
  - Ini dikerjakan berikutnya.

## Bukti
- `backend/tests/test_l05_interval_form.py` (4 tes).
- Regresi: `test_l04_ln041_mdq_select.py`.

## Blocker
- **KLX-02:** kode cacat, rumus, dan ambang grade client.
- **L09:** roll pengganti dari tukar barang.

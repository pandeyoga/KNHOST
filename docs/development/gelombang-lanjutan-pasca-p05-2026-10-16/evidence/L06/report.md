# Laporan Fase L06 — status `in_progress` (2026-10-17, agent E1)

Belum ber-SHA GitHub. Acceptance tetap `not_run` sesuai DEFINITION_OF_DONE; hasil uji lokal dicatat di sini.

## Navigasi aktual
- Kasir (POS) → quick view produk kain → "Pesanan Sampel" (standar/hanger) atau catalogue (`sample-catalogue-create`).
- Meja Cutting (`?view=cutting-desk`): antrean Menunggu pembelian internal → Menunggu dipotong → Hasil potong menunggu Admin Cutting → Siap kirim.
- Pusat Pengaturan → grup Stok & Satuan → `cutting.wait_warn_minutes` / `cutting.wait_late_minutes`.

## LN-060 — tiga jenis sampel & catalogue terurai
- Batas: standar woven 5 yard / knit 2 kg; hanger woven 0,5 yard / knit 2 kg (`sample_sale_service.SAMPLE_KINDS`); lewat batas → 400 `SAMPLE_LIMIT`, kasir menawarkan "Jadikan ecer".
- Catalogue = 1 yard tiap warna tersedia + 2 yard satu warna soft (komponen terpisah).
- Benang (stage yarn) tidak bisa disampel: tombol disembunyikan di kasir, server 400 `SAMPLE_NOT_ALLOWED`.
- Keranjang campur sampel + ecer ditolak (`SAMPLE_MIXED`), UI memberi pilihan pisah.

## LN-061 — cutting lintas lokasi/entitas
- Kemampuan potong per lokasi (`PUT /api/cutting/locations/{id}`), API = UI.
- Roll milik PT lain → antrean pembelian internal dulu; terima hasil ke gudang PT lain → 400 `CUTTING_DEST_OTHER_OWNER`.
- Hasil potong wajib diterima Admin Cutting sebelum kirim. Durasi tunggu ditampilkan; **batas kuning/merah kini bisa diatur per entitas** (sesi ini; bawaan 120/240 menit, batas merah tidak pernah di bawah kuning).

## LN-062 — ecer berbayar & mutasi potong
- Ecer = SO biasa potong roll; tidak terkena batas sampel; potong idempoten saat retry.

## Bukti
- `backend/tests/test_l06_samples_cutting.py` 8/8 (T01–T04 LN-060, T01–T03 LN-061, T01–T02 LN-062).
- `backend/tests/test_l06_cutting_wait_config.py` 1/1.
- Testing agent iteration_199–203.

## Blocker
- Reviewer terpisah + persetujuan owner; SHA GitHub untuk `implementation_commit`.

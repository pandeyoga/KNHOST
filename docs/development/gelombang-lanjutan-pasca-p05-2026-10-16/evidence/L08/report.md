# Laporan Fase L08 — status `in_progress` (2026-10-17, agent E1)

Belum ber-SHA GitHub. Pending KLR-08 (hangtag hilang / kain sudah dipotong) dan KLR-09 (batas 21 hari dihitung sampai kapan) memblok LN-083; tidak diasumsikan.

## Navigasi aktual
- Retur Penjualan (`?view=sales-returns`) → Buat Return → pilih SO (`return-order-select`) → baris produk otomatis dari Surat Jalan (`item-product-<i>`, satuan `item-unit-<i>`), centang roll terkirim (`item-roll-<rollId>`, menampilkan no. roll · SJ · sisa) → qty terisi dari roll → Buat Return.

## LN-080 — form retur dari barang terkirim (T01, T02 selesai lokal)
- Sebelum: baris retur diketik manual (ID produk mentah); batas retur per produk memakai qty terkirim, tetapi jatuh ke qty TERJUAL bila belum ada pengiriman; roll yang diklaim tidak tersimpan (skema membuang `roll_ids`); dua klaim paralel bisa lolos cek batas bersamaan.
- Sesudah:
  - `GET /api/sales-returns/returnable?order_id=` (izin `sales_return.create`, cakupan badan usaha): roll per SJ (`shipments.rolls`) dengan no. roll, SJ, nama produk, SKU, warna, qty kirim, sudah diretur, sisa; ringkasan per produk.
  - `create_return` memakai `return_rolls_service.assert_shipped_items`: produk wajib ada di SJ SO ini, roll wajib roll terkirim produk itu, klaim per roll (`roll_qtys`, kosong = seluruh panjang) dan kumulatif per produk ≤ terkirim. SO tanpa SJ → 400.
  - Kunci per SO (`return_create_locks`, TTL 60 detik) membungkus cek + simpan → klaim paralel: hanya satu yang tersimpan, sisanya 400 jelas.
  - Skema `SalesReturnItem` += `roll_ids`, `roll_qtys`. Retur lama tidak dimigrasi; approve tetap memakai cek lama.
  - UI: tidak ada lagi "Tambah Item" bebas / input ID produk.
- Perbaikan review (iteration_206): cek akses badan usaha saat membuat retur; qty tanpa `roll_qtys` dibagi ke roll terpilih sesuai SISA (bukan panjang kirim penuh) dan disimpan; roll sama di dua baris dijumlah dulu; qty harus = jumlah klaim per roll.
- Belum: T03 (bukti foto wajib per tahap configurable), T04 (filter status/kategori + definisi hitungan kartu total).

## LN-081, LN-082, LN-083
- Belum dikerjakan sesi ini. LN-083 terblokir KLR-08/KLR-09.

## Bukti
- `backend/tests/test_l08_returnable_rolls.py` 2/2 (roll asing & SO belum terkirim ditolak; 4 klaim paralel → 1 tersimpan, sisa roll tepat).

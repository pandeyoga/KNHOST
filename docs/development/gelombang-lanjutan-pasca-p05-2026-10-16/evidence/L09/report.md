# Laporan Fase L09 — status `in_progress` (2026-10-17, agent E1)

Belum ber-SHA GitHub. Hanya bagian yang TIDAK bergantung keputusan pending yang dikerjakan.

## Navigasi aktual
- Retur Penjualan (`?view=returns`) → Detail retur → panel karantina → "Teruskan ke Supplier" (modal Retur Beli).
- Detail retur → panel Perjalanan Barang → "Kirim ke pelanggan" (pengiriman pengganti).

## LN-093-T02 — retur supplier dipisah per provenance roll (selesai lokal)
- Sebelum: `purchase_return_service.create_from_sales_return` memilih supplier & PO dari **PO terbaru yang memuat produk yang sama** — satu retur beli untuk semua roll; satuan item di-hardcode `meter` (roll yard ditolak "melebihi sisa roll").
- Sesudah: supplier/PO diambil dari roll itu sendiri (`supplier_id`/`po_id`, cadangan: PO dari `acquired`/`acquired_history` penerimaan roll itu). Roll dikelompokkan per (supplier, PO) → satu Retur Beli per kelompok, semua tertaut `origin_sales_return_id`. Retur jual menyimpan `linked_purchase_returns[]` (id, nomor, supplier, PO); `linked_purchase_return_number` = daftar nomor. Roll tanpa asal tercatat → 400 kecuali supplier dipilih manual (hanya berlaku untuk roll tersebut). Satuan item = satuan roll.
- Klaim atomik lama tetap: klik paralel → satu set retur beli saja.
- UI: label supplier di modal kini "Supplier untuk roll tanpa asal tercatat"; pesan sukses menampilkan setiap retur beli → supplier (PO).

## LN-090-T01 — pengganti diblok sebelum QC (selesai lokal)
- Penanda `shipped_to_customer` ditolak 400 selama retur masih draf / menunggu / disetujui / sedang QC; tidak ada movement stok atau jurnal.
- LN-090-T02/T03 (replacement order nyata, qty & selisih tagihan) menunggu KLR-03/04/05 — tidak diasumsikan.

## Belum / terblokir
- LN-091 (KLR-10, KLR-11), LN-092 (KLR-01/02/06/07): tidak dikerjakan.
- LN-093-T01/T03/T04: alur interco return sudah ada (`interco_return_service`), belum diuji ulang terhadap acceptance ini; T03 terkait KLR-09.

## Bukti
- `backend/tests/test_l09_ln093_ln090.py` 4/4 (3 supplier/PO berbeda → 3 retur beli; roll tanpa asal → 400 lalu manual OK; 4 klik paralel → 1 sukses, 2 retur beli; pengganti sebelum QC → 400 tanpa movement/jurnal).
- `backend/tests/test_l08_ln081_journey.py` 4/4 (disesuaikan: kirim pengganti saat masih `approved` kini 400).

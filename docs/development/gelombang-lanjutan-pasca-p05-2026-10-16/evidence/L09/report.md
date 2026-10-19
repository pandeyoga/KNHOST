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

## Update 2026-10-19 (sesi lanjutan) — LN-090-T02/T03 pesanan pengganti nyata (KLR-03/04/05)
- **Alur:** retur jenis `penggantian` → QC selesai → selesaikan sebagai **Store Credit** (Credit Note harga transaksi awal; saldo customer) → `POST /api/sales-returns/{id}/replacement-order` {items:[{product_id, qty_yard}]} (izin `order.create` + `sales_return.update`, klaim atomik; kedua kali → 400/409).
- **Kewajiban (KLR-03):** `GET /api/sales-returns/{id}/replacement` → qty **aktual QC** (`inspection.accepted_qty`) dikonversi ke **yard** lewat master UoM; bila faktor yard belum ada di master produk → ditampilkan sebagai error konversi (tidak diasumsikan).
- **Pesanan pengganti:** SO biasa lewat `create_order` yang sama (alokasi/ATP, QC, picking, SJ, POD), artikel/warna wajib sama dengan barang diretur, flag QC mengikuti SO awal (`qc_request.mode`). Harga = harga transaksi asal (KLR-05) melalui harga khusus sekali pakai (`price_approvals.source=return_replacement`, sesudah dipakai `scope=order` + `so_id`, tidak bocor ke SO lain). SO menyimpan `replacement_for_return`, retur menyimpan `replacement_order_id/number/summary`, relasi dokumen `doc_refs`.
- **Selisih (KLR-04):** saldo retur dipakai otomatis ke SO pengganti (`store_credit.redeem` beralokasi). Pengganti lebih → `to_bill` = sisa tagihan SO; kurang → `remaining_credit` tetap saldo customer (pakai/refund lewat alur saldo).
- UI: `return-replacement-panel` (replacement-obligation-table, replacement-qty-<pid>, replacement-create, replacement-summary, replacement-to-bill, replacement-hint, replacement-error).
- **Uji:** `backend/tests/test_ln090_replacement_order.py` 2/2 (gerbang store credit & artikel sama; SO pengganti 12 yd vs kewajiban 10 yd → harga asal 30.000, saldo 300.000 terpakai, selisih ditagih, harga khusus sekali pakai).
- **Belum:** pemaksaan grade sama pada alokasi roll pengganti (grade QC disimpan di kewajiban; alokasi memakai aturan grade pelanggan existing).

# Laporan Fase L07 — status `in_progress` (2026-10-17, agent E1)

Belum ber-SHA GitHub. Acceptance tetap `not_run`; hasil uji lokal di bawah. DES-02 (penamaan dokumen per leg) masih pending → validasi akhir LN-071 menunggu owner.

## Navigasi aktual
- Logistik (`?view=logistics`) → tab **Picking & Trip** (`logistics-tab-trip`, hanya admin/manager/gudang): centang beberapa SO (`trip-order-<so>`) → `trip-build` → picking list per gudang sumber (`picking-wh-<wh>`, `picking-roll-<roll>`) + hasil cek kesiapan (`trip-check-row-<so>-<wh>`). Cetak `trip-print`.
- Logistik → **Buat Pengiriman**: kini boleh memilih SJ dari beberapa SO (`logistics-multi-order-notice`); pesanan ambil sendiri tidak bisa digabung.
- Detail pengiriman → `logistics-manifest-toggle` → manifest armada (`logistics-manifest-order-<so>`, `logistics-manifest-sj-<shipmentId>`).

## LN-070 — picking multi-gudang & validasi konsolidasi
- Sebelum: tugas ambil per SO × produk × gudang; Final Loading Check per SO × gudang; tidak ada daftar ambil gabungan.
- Sesudah: `POST /api/logistics/trip/picking-list {order_ids}` (izin `logistics.manage`, dibatasi badan usaha aktif) → per gudang: baris tugas + roll alokasi terbaru (bin, LOT, sudah diambil/belum, tanpa tag). Komitmen tetap per SO (roll membawa `order_id`).
- `POST /api/logistics/trip/check {order_ids}` menjalankan `dispatch_guard` yang SAMA per SO × gudang (QC pesanan, Admin Cutting, loading check basi/tidak bersih, roll tanpa tag). Multi-SO tidak melonggarkan pengecekan.
- `GET /api/logistics/trip/candidates`: SO dengan tugas ambil terbuka.

## LN-071 — dokumen per leg & manifest multi-SO
- SJ tetap terbit per SO per keberangkatan saat dispatch (`shipment_service.dispatch_task`, qty hanya keberangkatan itu; agregat dibatasi qty tugas).
- Sebelum: satu pengiriman logistik = satu SO. Sesudah: `logistics_deliveries` menyimpan `order_ids`, `orders[]` (SO, pelanggan, alamat, SJ), `is_multi_order`. SJ diklaim atomik (`update_many` bersyarat `logistics_id` kosong) → retry/klik ganda tidak menerbitkan pengiriman ganda (400).
- `GET /api/logistics/deliveries/{id}/manifest`: semua SO + SJ + roll aktual. Filter `order_id`, Perjalanan Pesanan, status QC, efek `on_delivered` berlaku untuk semua SO dalam armada.
- Picking list bukan SJ; transfer internal (P03) tetap dokumen transfer, bukan pengiriman pelanggan.

## LN-072 — transit Jakarta
- Memakai ulang P03: transfer tertaut SO (`warehouse_transfers.sales_order_id`), terima per roll CAS/idempoten, `partially_received`, exception hilang/rusak, retur ke asal; GL pendapatan/HPP hanya saat SJ pelanggan dispatch.
- Uji: `test_l07_trip_manifest.py::test_ln072_t01_internal_transit_no_customer_gl`; regresi `test_p03_transfer_receipt.py` (T02/T03 terima sebagian & retry).

## Bukti
- `backend/tests/test_l07_trip_manifest.py` 5/5.

## Blocker
- DES-02: persetujuan owner atas contoh dokumen Bandung–Jakarta–customer & manifest 3 SO.
- Reviewer terpisah + SHA GitHub.

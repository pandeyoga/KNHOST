# Gelombang 3 · Fase 02 — status implementasi (2026-10-06)

Status tertinggi yang dipakai agent adalah `implemented_pending_validation`. Bukti uji terpisah dari evidence baseline.

| ID | Validasi temuan | Status | Perubahan |
|---|---|---|---|
| D4-ICLOAN-01 | VALID | implemented_pending_validation | `routers/interco_loans.py` `_guard_loan` dipasang di detail, cair, bayar, batal (iteration_164) |
| D4-RFQ-02 | VALID | implemented_pending_validation | `routers/rfq.py` compare, send, quote, award, cancel kini memeriksa lingkup entitas (iteration_164) |
| D4-CAP-01 | VALID | implemented_pending_validation | `routers/purchase_orders.py` hanya mengambil produk yang dipesan, tanpa batas 1.000 (iteration_164) |
| D4-DASH-01 | VALID | implemented_pending_validation | `routers/dashboard.py` tanpa batas 3.000/5.000. Risiko performa di katalog sangat besar |
| D4-PRICE-SCOPE-01 | VALID | implemented_pending_validation | `_get_or_404(id, request)` memeriksa `assert_entity_access` di semua handler ber-ID; `stats/summary` memakai `resolve_list_scope` |
| D4-RFQ-01 | VALID | implemented_pending_validation | `rfq_service._price_of`: baris tak tersedia dihitung 0 |
| V3-MRES-01 | VALID | implemented_pending_validation | kunci unik per (bahan, entitas) + id cadangan deterministik |
| V3-MRES-02 | VALID | implemented_pending_validation | penjumlahan tanpa batas |
| D4-WMS-03 | VALID | implemented_pending_validation | `routers/reporting.py` membaca `rack.levels[].bins` + legacy |
| D4-ALERT-WMS-01 | VALID | implemented_pending_validation | kunci grup memuat `entity_id` |
| D4-SUPPLY-01 | VALID | implemented_pending_validation | `OPEN_PO_STATUSES` + `partial` |
| D4-GLOBAL-01 | VALID | implemented_pending_validation | `apply_global` memakai `quantity_base` |
| V3-RFID-01 | VALID | implemented_pending_validation | cache dwell hanya bila `passage_id` sama |
| D4-AI-05 | VALID | implemented_pending_validation | snapshot **dan** jalur live `analytics_engine._src_stock`: panjang ter-reservasi di roll available dihitung reserved |
| D4-PA-03 | VALID | implemented_pending_validation | backend `qty_by_unit`/`mixed_units`; frontend `PutawayOrdersPanel` menampilkan total per satuan (`pa-qty-<id>`) |
| D4-RET-POLICY-01 | VALID | implemented_pending_validation | `return_policy_service.physical_origin_po_ids`: roll yang memenuhi SO → `po_id`/riwayat GR → PO; roll potongan lewat `parent_roll_id`. Tanpa asal → `source: untraceable`, pakai kebijakan retur penjualan, `needs_admin_review: true` + peringatan |
| V3-WEIGHT-01 | VALID | implemented_pending_validation | `roll_service`: berat potongan = kepadatan snapshot induk SEBELUM potong; induk dikurangi atomik (pipeline `$subtract`, idempoten via `weight_split_children`); `confirm_cut` menyimpan `weight_basis` di operasi tahan-retry |
| V3-WMS-02 | VALID | implemented_pending_validation | `loading_check_service`: sesi per pengiriman (SO + gudang); guard potong hanya gudang itu; hasil di `sales_orders.loading_checks.<gudang>`; `dispatch_guard` membaca hasil gudangnya; status SO memuat `by_warehouse`. API `?warehouse_id=` + frontend `LoadingCheckPanel` |
| D4-STOCK-01 | VALID | implemented_pending_validation | `stock_analytics_service`: kunci agregasi (produk, gudang, pemilik) |
| D4-AI-06 | VALID | implemented_pending_validation | `analytics_engine.query_metrics`: dimensi produk tanpa dimensi satuan → satuan dari master produk; satuan campur → `totals` qty `null`, `totals_by_unit`, porsi per satuan |
| D4-PLAN-05 | VALID | implemented_pending_validation | `stock_bucket_service.pending_so_board`: pasokan dibagi FIFO (SO tertua dulu), SO berikutnya melihat sisa; `supply_is_forecast`, `incoming_claimed_by_older`; label UI "Perkiraan … (tidak dijamin)"; validasi `wait` memakai sisa |
| D4-PA-01 | VALID | implemented_pending_validation | Saling mengunci: semua jalur reservasi (SO qty/roll eksplisit/potong panjang, transfer, retur, sampel) menolak roll ber-`active_movement`; roll diklaim PA masuk `hold_qty` (keluar dari ATP); dispatch PA menolak roll dengan `length_reserved` live |
| D4-TAG-01 | VALID | implemented_pending_validation | `putaway_order_service.identity_issue`: tag aktif saat ini + tertaut + `journey.verified_tag_id` = tag itu; dipakai di suggest/create/dispatch. Retire menghapus bukti verifikasi dan ditolak saat roll sedang berpindah. Verifikasi cetak menulis `verified_tag_id` |

Rekap: 23 ID. 23 implemented_pending_validation. 0 partially_fixed. 0 open.

Keputusan bisnis (user, 2026-10-06):
1. D4-RET-POLICY-01: asal tidak terlacak → kebijakan retur penjualan saja + tanda "asal tidak diketahui" untuk Sales Admin. Asal disimpan di roll, bukan di tag, jadi re-tag tidak memutus jejak.
2. V3-WMS-02: sesi cek muat per pengiriman.
3. D4-PLAN-05: hanya informasi; dibagi FIFO (SO tertua dulu).
4. D4-PA-01: saling mengunci.

Bukti uji batch akhir: `tests/test_g3_phase02b.py` 16/16 (service asli). Regresi: phase01 28/28, phase02 21/21, phase02_api 15/15.
Catatan jujur: beberapa tes lama di `test_g3_phase02.py` (D4-PA-03 grouping, V3-RFID-01) mereplikasi logika, bukan memanggil service. Tes `D4-RET-POLICY-01` lama disesuaikan dengan perilaku baru (bukan lagi proxy PO).
Batasan: data lama tanpa `journey.verified_tag_id` diterima bila tag lahir sebelum verifikasi terakhir (fallback); belum ada UI khusus untuk menampilkan `needs_admin_review` di layar retur selain daftar peringatan.

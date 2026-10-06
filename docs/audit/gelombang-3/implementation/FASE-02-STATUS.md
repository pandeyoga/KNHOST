# Gelombang 3 · Fase 02 — status implementasi (2026-10-06)

Status tertinggi yang dipakai agent adalah `implemented_pending_validation`. Bukti uji terpisah dari evidence baseline.

| ID | Validasi temuan | Status | Perubahan |
|---|---|---|---|
| D4-ICLOAN-01 | VALID | implemented_pending_validation | `routers/interco_loans.py` `_guard_loan` dipasang di detail, cair, bayar, batal (iteration_164) |
| D4-RFQ-02 | VALID | implemented_pending_validation | `routers/rfq.py` compare, send, quote, award, cancel kini memeriksa lingkup entitas (iteration_164) |
| D4-CAP-01 | VALID | implemented_pending_validation | `routers/purchase_orders.py` hanya mengambil produk yang dipesan, tanpa batas 1.000 (iteration_164) |
| D4-DASH-01 | VALID | implemented_pending_validation | `routers/dashboard.py` tanpa batas 3.000/5.000. Risiko performa di katalog sangat besar |
| D4-PRICE-SCOPE-01 | VALID: mutasi ber-ID dan statistik tanpa lingkup entitas | implemented_pending_validation | `_get_or_404(id, request)` memeriksa `assert_entity_access` di **semua** handler ber-ID; `stats/summary` memakai `resolve_list_scope` |
| D4-RFQ-01 | VALID: award memakai harga baris `available=False` | implemented_pending_validation | `rfq_service._price_of`: baris tak tersedia dihitung 0, sehingga award ditolak atau baris dilewati |
| V3-MRES-01 | VALID: baca-bebas lalu insert tanpa klaim | implemented_pending_validation | kunci unik per (bahan, entitas) `material_reservation_locks` + id cadangan deterministik `mres_<pr>_<baris>` |
| V3-MRES-02 | VALID: total dari daftar terpotong 500/2000/5000 | implemented_pending_validation | `material_reservation_service`: penjumlahan tanpa batas |
| D4-WMS-03 | VALID: konsumen hanya membaca `rack.bins` lama | implemented_pending_validation | `routers/reporting.py` membaca `rack.levels[].bins` + legacy; saldo tanpa batas 1000 |
| D4-ALERT-WMS-01 | VALID: grup tanpa entitas | implemented_pending_validation | `alert_service`: kunci grup memuat `entity_id` |
| D4-SUPPLY-01 | VALID: status `partial` tidak dianggap PO terbuka | implemented_pending_validation | `roll_service.OPEN_PO_STATUSES` + `partial` (dipakai stock bucket dan sales stock) |
| D4-GLOBAL-01 | VALID: qty dokumen mentah dilabeli base_unit | implemented_pending_validation | `sales_stock_service.apply_global` memakai `quantity_base` (PO terbuka proporsional; interco `quantity_base`) |
| V3-RFID-01 | VALID: cache dwell memakai verdict passage lama | implemented_pending_validation | cache dwell hanya bila `passage_id` sama; passage baru dievaluasi ulang |
| D4-AI-05 | VALID | partially_fixed | snapshot harian memecah roll `available` yang ber-`length_reserved` ke reserved. Jalur live tanpa snapshot **belum** diubah |
| D4-PA-03 | VALID | partially_fixed | backend: satuan masuk kunci grup; order PA menyimpan `qty_by_unit` dan `mixed_units`. Label total di frontend **belum** diubah |
| D4-RET-POLICY-01 | VALID | partially_fixed + needs_business_decision | resolver supplier dibatasi ke PO entitas pesanan. Pelacakan asal fisik roll (roll → GR → PO) **belum**. Perlu keputusan bila asal fisik tidak tersedia |
| V3-WEIGHT-01 | belum dikerjakan | open | — |
| V3-WMS-02 | belum dikerjakan. Kemungkinan perlu keputusan: sesi loading per shipment/gudang | open | — |
| D4-STOCK-01 | belum dikerjakan (kunci agregasi perlu `owner_entity_id` di semua konsumen) | open | — |
| D4-AI-06 | belum dikerjakan | open | — |
| D4-PLAN-05 | belum dikerjakan. Kemungkinan perlu keputusan: pasokan masuk dicadangkan per SO | open | — |
| D4-PA-01 | belum dikerjakan | open | — |
| D4-TAG-01 | belum dikerjakan | open | — |

Rekap: 23 ID. 13 implemented_pending_validation, 3 partially_fixed, 7 open.
Bukti uji: iteration_164 (4 ID pertama); iteration_165 (12 ID sesi ini): 64/64 lulus (28 Fase 01 + 21 Fase 02 service + 15 Fase 02 API).
Regresi yang tertangkap reviewer dan sudah diperbaiki: loop `alert_service` masih membongkar kunci 2 elemen, padahal kunci D4-ALERT-WMS-01 sekarang 3 elemen. Akibatnya job notifikasi tugas tertunda crash. Sudah diperbaiki menjadi `(wid, flow, _ent)`.

Keputusan bisnis Fase 02 yang diperlukan:
1. D4-RET-POLICY-01: bila asal fisik roll yang diretur tidak bisa dilacak sampai PO, apakah memakai PO terbaru entitas yang sama (berlaku sekarang) atau tanpa batas waktu retur ke supplier?
2. V3-WMS-02: sesi loading check per SO (sekarang) atau per shipment/gudang?
3. D4-PLAN-05: pasokan PO yang masuk dicadangkan per SO (satu PO tidak dijanjikan ke banyak SO) atau tetap hanya informasi?

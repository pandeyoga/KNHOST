# F — Pesanan pelanggan sesudah POS (alokasi, tagihan, keep/pending, buka lagi)

HEAD: `91a3ec0`.

---

## SO-01 — Dua pintu fulfillment menghitung ketersediaan dari koleksi MENTAH (lewati SSOT)

- **Keparahan:** Kritis · **Jenis akar:** duplikasi / cacat logika → layar beda angka beda
- **Fakta terverifikasi:**
  - **Selaras SSOT** (`stock_figures`, FIX-2 — hanya gudang DIHITUNG & cadangan makloon dialokasikan):
    - `fulfillment_service.build_supply_index` (`:39,56-60`) → `stock_figures.segments`.
    - `fulfillment_decision_service._usable_stock_by_entity` (`:54,62-64`) → `stock_figures.available_by_owner`.
  - **MELEWATI SSOT** (baca koleksi mentah):
    - `fulfillment_plan_service._own_by_warehouse` (`:25`) → `db.inventory_balances.find(...)`; `_rolls_for` (`:39`) → `db.inventory_rolls.find({status:"available"})`.
    - `fulfillment_wizard_service._available_by_owner` (`:20`) → `db.inventory_balances.find({available_qty:{$gt:0}})`.
  - Konsumen: `fulfillment_service` → `routers/inventory.py` + `routers/sales_orders_extra.py`; `decision_service` → `routers/work_desks.py` + `services/sales_p04_service.py` (keep/pending); `plan_service` → `routers/work_desks.py`; `wizard_service` → `routers/fulfillment.py`.
- **Akibat:** rencana per-baris (`plan_service`) & wizard interco/PR (`wizard_service`) bisa menampilkan stok **lebih banyak** daripada papan ATP & meja keputusan karena memasukkan gudang yatim/tak-dihitung dan roll yang sudah dicadangkan makloon. → **angka ketersediaan berbeda untuk SO yang sama antar layar** — akar keluhan: alokasi berubah → tagihan berubah, keep/pending lalu dibuka lagi terasa tak konsisten.
- **Langkah reproduksi (data acuan):** ambil SO kurang stok pada produk yang punya roll di gudang tak-dihitung atau roll cadangan makloon; bandingkan "tersedia/kurang" di papan ATP (`inventory`/`sales_orders_extra`), meja keputusan (`work_desks`), rencana per baris (`work_desks` plan), dan wizard (`/fulfillment/wizard/{so_id}`). Selisih = bukti.
- **Arah perbaikan:** arahkan `plan_service` & `wizard_service` ke `stock_figures` (sumber yang sama dengan ATP/decision); matikan pembacaan mentah.
- **Keputusan pemilik:** Pertanyaan #5.

---

## Pertanyaan pemilik sebelum perbaikan F

1. Bila alokasi berubah **sesudah** DP/pembayaran: tagihan ikut alokasi terakhir, atau nilai bayar mengunci tagihan? (reallocate → `ar_allocation_service` → faktur)
2. Saat keep/pending **dibuka lagi**: reservasi/backorder lama dilepas otomatis atau dipertahankan? (hindari reservasi/backorder basi)

---

## Tindak lanjut (butuh data acuan)

Alur penuh checkout POS → SO → reservasi (`sales_order_helpers.reserve_roll_mode_item`, `material_reservation_service`) →
realokasi (`ReallocateRollsModal`, `sales_orders_extra` reallocate/release-rolls) → backorder → keep/pending
(`sales_p04_service`, DEC-01) → buka lagi → batal baris (`so_line_cancel_service`) → perubahan tagihan (PK-30/PK-32,
`so_special_price_service`, `ar_allocation_service`) — efek uang (DP vs alokasi berubah) perlu dataset acuan. Temuan
struktural duplikasi (SO-01) sudah tegak di kode.

# F — Pesanan pelanggan sesudah POS (alokasi, tagihan, keep/pending, buka lagi)

HEAD: `91a3ec0`.

---

## SO-01 — Empat modul fulfillment menghitung ketersediaan sendiri-sendiri

- **Keparahan:** Kritis
- **Jenis akar:** duplikasi (empat sumber ketersediaan) → layar beda angka beda
- **Bukti (berkas:baris):**
  - `backend/services/fulfillment_service.py` — ATP/papan status: `build_supply_index` (:39), `classify_lines` (:244), `status_board` (:280). Dikonsumsi `routers/inventory.py` + `routers/sales_orders_extra.py`.
  - `backend/services/fulfillment_decision_service.py` — opsi/keputusan: `_usable_stock_by_entity` (:54), `options` (:69), `decide` (:200) dengan tiga jalan (`_take_from_other_entity` :244, `_reorder_supplier` :314, `_wait_incoming` :358). Dikonsumsi `routers/work_desks.py` + `services/sales_p04_service.py` (keep/pending).
  - `backend/services/fulfillment_plan_service.py` — rencana per baris: `_own_by_warehouse` (:22), `_rolls_for` (:32), `plan_options` (:74), `decide_plan` (:253). Dikonsumsi `routers/work_desks.py`.
  - `backend/services/fulfillment_wizard_service.py` — skenario S1–S8: `_available_by_owner` (:16), `analyze` (:29), `create_interco_draft` (:116), `create_pr_draft` (:155). Dikonsumsi `routers/fulfillment.py`.
- **Akar:** **empat** implementasi independen untuk "stok apa yang tersedia memenuhi SO" (`build_supply_index` vs `_usable_stock_by_entity` vs `_own_by_warehouse`/`_rolls_for` vs `_available_by_owner`), dipanggil **empat** router/meja berbeda.
- **Akibat:** layar berbeda (papan ATP, meja keputusan, rencana per baris, wizard interco/PR) bisa menampilkan **angka ketersediaan berbeda untuk SO yang sama**. Inilah akar keluhan pemilik: alokasi berubah-ubah → tagihan berubah, keep/pending lalu dibuka lagi terasa tak konsisten.
- **Langkah reproduksi (data acuan):** ambil satu SO dengan kekurangan stok; buka papan ATP (`inventory`/`sales_orders_extra`), meja keputusan (`work_desks`), dan wizard (`/fulfillment/wizard/{so_id}`); bandingkan angka "tersedia/kurang". Perbedaan = bukti.
- **Arah perbaikan:** satu sumber ketersediaan (satu `supply_index`) + satu pintu keputusan; keempat modul memanggil sumber yang sama; matikan kalkulator duplikat (R6).
- **Keputusan pemilik:** Pertanyaan #5.

---

## Pertanyaan untuk pemilik yang harus dijawab sebelum perbaikan F

1. Bila alokasi berubah **sesudah** DP/pembayaran, tagihan mengikuti alokasi terakhir, atau nilai bayar mengunci tagihan? (menentukan hubungan reallocate → `ar_allocation_service` → faktur)
2. Saat keep/pending **dibuka lagi**, reservasi/backorder lama harus otomatis dilepas, atau dipertahankan? (menghindari reservasi/backorder basi)

---

## Catatan alur (tindak lanjut di data acuan)

Alur penuh checkout POS (`CheckoutDrawer.jsx`/`CheckoutStep3.jsx`) → SO → reservasi (`sales_order_helpers.reserve_roll_mode_item`,
`material_reservation_service`) → realokasi (`ReallocateRollsModal.jsx`, `sales_orders_extra` reallocate/release-rolls) →
backorder (`backorder_service`) → keep/pending (`sales_p04_service`, DEC-01) → buka lagi → batal baris
(`so_line_cancel_service`) → perubahan tagihan (PK-30/PK-32, `so_special_price_service`, `ar_allocation_service`) perlu
dataset acuan untuk membuktikan efek uang (DP vs alokasi berubah). Temuan struktural duplikasi (SO-01) sudah tegak di kode.

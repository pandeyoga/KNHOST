# F — Pesanan pelanggan sesudah POS (alokasi, tagihan, keep/pending, buka lagi)

HEAD: `91a3ec0`.


> **Status domain: BELUM DIKERJAKAN.** Skenario wajib §8 dan inventaris form domain ini belum dijalankan. Semua isi di bawah berlabel **dugaan (baca kode)** sampai diuji lewat layar/API pada sesi domainnya.
---

## SO-01 — Dua pintu fulfillment menghitung ketersediaan dari koleksi MENTAH (lewati SSOT)

- **Keparahan:** Tinggi (semula Kritis — diturunkan: divergensi NYATA di kode, tetapi TIDAK termaterialisasi di data seed; risiko laten) · **Jenis akar:** duplikasi / cacat logika
- **Tingkat bukti:** dugaan (baca kode)

### Verifikasi runtime (backend hidup, data acuan) — JUJUR: divergensi tak tereproduksi pada SO sampel

Diuji di SO `KANDA/SO-00006` (produk RIVERA RIB BW A), ketiga pintu dipanggil:
```
GET /sales-admin/orders/{id}/fulfillment       (decision, SSOT) → own available 0.0
GET /sales-admin/orders/{id}/fulfillment-plan  (plan, MENTAH)   → own 0.0 · lain: Cipta Sandang 700.35, Sukacita 593.58
GET /fulfillment/wizard/{id}                    (wizard, MENTAH) → own 0   · lain: Cipta Sandang 700.35, Sukacita 593.58
```
→ **plan == wizard** (angka sama). Sebab: (a) 1 cadangan makloon aktif di seed sudah **terkunci penuh** (`qty=300, locked=300, left=0`) sehingga `stock_figures` tak mengurangi apa pun ekstra; (b) gudang dengan saldo pada SO itu termasuk dihitung. Jadi kondisi pemicu divergensi tidak hadir di data seed.

**Kesimpulan jujur:** divergensi KODE terkonfirmasi (lihat di bawah), tetapi pada data acuan saat ini ketiga pintu **setuju**. Divergensi akan muncul hanya bila: saldo ada di gudang **tak-dihitung** (`counted` false / nonaktif), atau cadangan makloon **sebagian** (`qty>locked`). Perlu data uji khusus untuk mereproduksi (dicatat sebagai langkah berikut).

### Bukti kode (tetap berlaku)
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

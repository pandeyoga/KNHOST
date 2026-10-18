# Laporan Fase P01 — Master data, lifecycle, dan cakupan lokasi pengguna

## Identitas

- Branch/commit implementasi: `main` @ `c3291a7` (commit otomatis platform).
- Pelaksana: agent developer. Reviewer/validator: belum ditetapkan.
- Tanggal & lingkungan uji: 2026-10-11, container preview, DB data acuan (seed repo + simulasi bin + `seed_p01_kn.py`).
- IMP: IMP-12, IMP-13, IMP-14, IMP-15, IMP-20. Status: **implemented_pending_validation**.

## Keputusan bisnis (dikonfirmasi pemilik 2026-10-11)

| DEC | Keputusan |
|---|---|
| DEC-05 | Sales tidak melihat Grey, PFD, PFP, benang; barang jadi, sisa potong, produk samping tetap tampil — **configurable** `catalog.sales_hidden_stages` (Pusat Pengaturan → Stok, Satuan & Alokasi). Master terpakai: hapus ditolak, nonaktif/arsip hanya **Admin atau MD**; master belum terpakai boleh dihapus permanen. |
| DEC-09 | Penugasan per **site** (Jakarta, Rancamalang, Soreang) mencakup semua gudang site, opsional dipersempit per gudang. Supervisor (warehouse_admin, manager, admin) melihat semua lokasi dan boleh **mengambil alih tugas dengan alasan tercatat**. Toggle `wms.location_scope_enforced`; operator tanpa penugasan tidak melihat pekerjaan gudang. |

## Perubahan perilaku

| IMP | Server | UI |
|---|---|---|
| IMP-12 | `product_exclusivity.visibility_query/can_view/assert_can_order` menambah pagar tahap untuk role sales (semua jalur `catalog_access.visible_query`, `/products`, `/product-templates`, SO). Nilai dari setting, cache 15 dtk, invalidasi saat setting disimpan. | Tidak ada perubahan layar; bahan hilang dari semua pemilih Sales karena datanya tidak dikirim. |
| IMP-13 | `supplier_items` + `supplier_color_code`, `internal_color_code`, `review_status`/`review_reasons` (`color_review`): kode warna internal tak dikenal, warna SKU beda, atau warna supplier sudah dipetakan ke warna internal lain → `needs_review`. Impor CSV memakai aturan yang sama; tidak pernah membuat SKU. `POST /supplier-items/{id}/resolve-review`, filter `review_status`. | Barang Supplier: KPI "Perlu Ditinjau", baris peta warna supplier → internal, tombol "Tandai benar"; form punya kode warna supplier & internal. |
| IMP-14 | `master_usage_service`: `GET /api/master/usage/{product\|template\|color\|supplier_item}/{id}`, `DELETE /api/master/{kind}/{id}/purge` (409 `MASTER_IN_USE` bila terpakai). Nonaktif SKU, arsip induk, nonaktif warna: hanya admin/md. | Panel "Dipakai di" + kebijakan + tombol hapus permanen (admin/md, hanya bila belum dipakai) di header varian katalog. |
| IMP-15 | `GET /product-templates` filter `stage, fabric_type, line_code, color, supplier_id, lifecycle` (digabung, pagar peran tetap). | Toolbar filter katalog (nilai dari registry), jumlah hasil, reset. |
| IMP-20 | `services/location_scope.py`; `EntityContext.warehouse_ids` → `resolve_list_scope/apply_entity_scope/assert_entity_access` mempersempit `wms_tasks, shipments, inventory_rolls, inventory_movements, inventory_balances, goods_receipts, warehouse_transfers` (asal/tujuan). Assert eksplisit: buat tugas, putaway, lokasi & struktur gudang. `GET /wms/my-location-scope`, `POST /wms/tasks/{id}/takeover`. Akun: `location_site_ids`, `location_warehouse_ids` (divalidasi: gudang harus di site terpilih). | Drawer akun: "Lokasi kerja gudang" (chip site & gudang). Badge cakupan di Lokasi Rak & panel scanner; pemilih gudang Lokasi Rak hanya gudang dalam cakupan; tombol "Ambil Alih" (supervisor). |

## Data lama dan migrasi

- Tidak ada perubahan stok/HPP/jurnal. Default setting pembatasan lokasi = **nonaktif** (aman untuk instalasi lama); data acuan menyalakannya lewat `backend/scripts/seed_p01_kn.py` setelah akun demo dipetakan (warehouse@ → Jakarta, warehouse.soreang@ → Soreang, warehouse.rancamalang@ → Rancamalang). Skrip ini masuk `deploy/setup_demo_lengkap.sh` langkah 5d.
- Temuan data: kode warna SKU hasil impor (mis. `001`) tidak ada di Pustaka Warna (`KN-WHT-01`, …) — validasi warna internal menerima keduanya; penyatuan kode warna = keputusan dataset DEC-05.
- Contoh pemetaan (data acuan): SUP-A-001 & SUP-B-9001 (2 supplier → 1 SKU, ok), SUP-A-002 (warna supplier WRN-77 bentrok → needs_review).

## Hasil pengujian

| ACC | Langkah | Hasil | Evidence |
|---|---|---|---|
| ACC-01 | sales vs admin pada /products, /product-templates; SO bahan; toggle setting | pass | iteration_173 |
| ACC-02 | 2 supplier → 1 SKU; bentrok warna → review | pass sebagian (PO & penerimaan end-to-end belum dijalankan) | iteration_173 |
| ACC-03 | usage, purge terpakai 409, manager 403 | pass | iteration_173 |
| ACC-04 | filter gabungan, jumlah, reset, detail | pass | iteration_173 |
| ACC-05 | operator Soreang/Jakarta, supervisor, takeover | pass sebagian (notifikasi & ekspor belum berpagar lokasi) | iteration_173 |

Testing agent: backend 18/18, frontend semua alur lulus (`/app/test_reports/iteration_173.json`). Data uji dibersihkan (takeover di-unset, setting dikembalikan).

## Issue terbuka

1. Notifikasi tidak membawa gudang → belum bisa dipersempit per lokasi; perlu stempel `warehouse_id` saat notifikasi dibuat.
2. Ekspor & angka antrean desk gudang (`work_desk_service`) yang membaca koleksi langsung tanpa `resolve_list_scope` belum diaudit satu per satu.
3. Dataset supplier/warna asli klien belum diterima (DEC-05).
4. Kontrak sumber restock per artikel (bersama P05) belum dibuat.

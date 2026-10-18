# L11 — Pusat Export (LN-110, LN-113)

## Sesi 2026-10-18: LN-110 + LN-113 (in_progress: diimplementasi + uji developer & testing agent, belum ada reviewer/owner)

Navigasi aktual: sidebar **Alat → Pusat Export** (`?view=export-center`). Tab **Buat export** (dataset → 1 Kolom → 2 Periode → 3 Filter → 4 Urutan → Pratinjau / Export XLSX / Export CSV), tab **Pekerjaan** (status, unduh, ulangi), tab **Cakupan data** (semua koleksi DB: dipetakan / dikecualikan + alasan / belum dipetakan).

### Izin baru
`data_export.view` (dataset, cakupan, preview, daftar job) · `data_export.export` (buat job, unduh, retry). Default: admin, manager, finance, sales_admin, sales, md, warehouse_admin, designer. Modul editor peran: "Pusat Export Data" (grup Alat, nav `export-center`). Isi dataset tetap dijaga izin modul sumbernya (mis. `purchase_order.view`), scope entitas/lokasi (`resolve_list_scope`), kepemilikan sales (`sales_ownership`, pelanggan `assigned_sales_id`, desain `assigned_to`), visibilitas grade/LOT/asal (`field_visibility`) dan kolom biaya (`COST_SAFE_ROLES`). Ada juga izin per kolom (mis. gaji `hr.manage_payroll`, NIK/telepon `hr.view_pii`).

### Route/API
| Method · path | Izin | Hasil |
|---|---|---|
| GET `/api/export-center/datasets` | data_export.view | dataset yang boleh dipakai + kolom (dasar + relasi to-one) + `hidden_columns` (alasan) + `unavailable` |
| GET `/api/export-center/coverage` | data_export.view | setiap koleksi: mapped/excluded(alasan)/unmapped + jumlah dokumen |
| POST `/api/export-center/preview` | data_export.view | rows (≤200), total, teks filter/periode/urutan, grain |
| POST `/api/export-center/jobs` | data_export.export | job async; XLSX berpartisi `rows_per_sheet` (100..1.000.000) + sheet **Ringkasan** (definisi kolom, filter, periode, total, partisi); CSV utuh. >2.000.000 baris → 413 (tidak dipotong diam-diam) |
| GET `/api/export-center/jobs`, `/jobs/{id}` | data_export.view | hanya job milik sendiri |
| GET `/api/export-center/jobs/{id}/download` | data_export.export | pemilik saja (lain → 404); izin diperiksa ulang (dataset, kolom, badan usaha) → 403 `ACCESS_CHANGED`; kedaluwarsa 24 jam → 410; diaudit |
| POST `/api/export-center/jobs/{id}/retry` | data_export.export | spesifikasi lama divalidasi ulang dengan hak saat ini |

Filter: pohon `{op: and|or, items: [...]}` (kurung bertingkat ≤4, ≤40 kondisi), pembanding eq/ne/contains/not_contains/starts/gt/gte/lt/lte/in/empty/not_empty. Filter dan urutan hanya untuk kolom dataset utama. Relasi digabung per batch secara to-one, jadi baris tidak berlipat. Periode berbasis WIB dan inklusif. Kolom datetime tersimpan dalam UTC. Bukan query bebas: kolom yang tak dikenal → 422 `FIELD_UNKNOWN`, kolom tak berhak → 403 `FIELD_NOT_ALLOWED`.

### Sebelum → sesudah
- Sebelum: export hanya per layar (CSV/XLSX khusus beberapa modul), dan tidak ada daftar dataset maupun pembuktian cakupan.
- Sesudah: 20 dataset terdaftar (penjualan, gudang, pembelian, keuangan, desain, SDM). Pada DB demo: 19 koleksi dipetakan, 19 dikecualikan dengan alasan (kredensial/teknis), 70 belum dipetakan dan ditampilkan terbuka.
- Schema: koleksi baru `export_jobs` (user-scoped, terdaftar di `USER_SCOPED_COLLECTIONS`). File di `backend/uploads/exports/` (di-gitignore). Tanpa migrasi data.

### Uji
- `backend/tests/test_l11_export_center.py`: 6/6. T01 preview = file untuk filter A DAN (B ATAU C). T02 cakupan. T03 41.658 mutasi → 9 partisi + Ringkasan, total cocok. LN-113-T01 penyisipan grade/lot/HPP/product.grade lewat kolom/filter/urutan → 403 di preview & job, SKU tersamar. LN-113-T02 unduh pemilik saja, izin dicabut → 403, retry → 403. LN-113-T03 sel formula = teks (XLSX `data_type s`, CSV diawali `'`).
- Testing agent iteration_226: backend 100%, UI admin & sales.kanda 100%. Kepemilikan SO sales cocok dengan `/api/sales-orders`.

### Belum / batas
- Asumsi: batas maksimal 2 juta baris per job dan masa unduh 24 jam (bisa diubah di `export_engine.MAX_EXPORT_ROWS` / `JOB_TTL_HOURS`).
- 70 koleksi belum dipetakan (terlihat di tab Cakupan). Ini belum memenuhi "seluruh data bisnis". Perlu putaran pemetaan lanjutan.
- Job berjalan in-process. Bila backend restart saat job berjalan, job tetap "Diproses" dan bisa dijalankan ulang lewat "Ulangi".
- LN-111 (join finance/ordered vs shipped vs cash) dan LN-112 (rapor, menunggu DES-03) belum dikerjakan. Reviewer terpisah & owner belum ada, jadi status maksimal in_progress.

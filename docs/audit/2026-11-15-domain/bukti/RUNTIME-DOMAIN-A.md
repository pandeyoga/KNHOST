# Bukti runtime — Domain A (sesi audit backend hidup)

HEAD: `91a3ec0`. DB: `test_database` (MongoDB asli lokal). Backend 8001 hidup. Data acuan ter-seed.

## Lingkungan
- `backend/.env` lokal (gitignored, TIDAK tracked → tak ikut commit): `MONGO_URL=mongodb://localhost:27017`, `DB_NAME=test_database`, `CORS_ORIGINS=http://localhost:3000`.
- Seed: `bash scripts/restore_local_demo.sh` — `seed_p03_kn.py` gagal (EXIT=1, gudang tujuan nonaktif) spt catatan perintah §6; sisanya sukses.
- Counts: products 282 · inventory_rolls 46535 · users 20 · sales_orders 8 · makloon_orders 3.
- Akun: `demo12345` untuk semua peran KECUALI `admin@` (sandi bootstrap acak; dari log `[bootstrap] SANDI AWAL`).

## MS-01 — asimetri penegakan (diproduksi)
```
# FORM door (token md) — DITOLAK
POST /api/products {"sku":"AUDIT-TEST-X1","name":"..","category":"Tenun","stage":"finished"}
  → HTTP 400 "Jenis kain .. wajib .. Gramasi/GSM wajib .. Lebar kain wajib .. 'Finished'"
POST /api/products {..,"stage":"ngaco123","gramasi":180,"lebar":1.5}
  → HTTP 400 "Tahap bahan (stage) 'ngaco123' tidak dikenal"

# IMPORT door (token admin) — LOLOS
CSV: sku,name,category,price,stage,fabric_type
     AUDIT-IMP-1,..,Tenun,1000,finished,
     AUDIT-IMP-2,..,Tenun,1000,ngaco999,
POST /api/master-data/import-products?dry_run=false  → HTTP 200 {"total":2,"created":2,"errors":[]}

# Query balik
db.products.find({sku:/^AUDIT-IMP/}) →
  AUDIT-IMP-1: stage=finished gramasi=0 lebar=0 needs_review=true domain_gaps=[Gramasi wajib.., Lebar wajib..]
  AUDIT-IMP-2: stage="ngaco999" (TAK SAH, tersimpan) domain_gaps=[Tahap 'ngaco999' tidak dikenal..]
# dibersihkan: db.products.deleteMany({sku:/^AUDIT-IMP/}) → 2
```

## MS-05 — non-finished orderable di POS (diproduksi)
```
GET /api/products?orderable_only=true (token sales) → HTTP 200, 278 produk
  stage: finished 273, pfd 2, pfp 1, byproduct 1, remnant 1
  NON-finished orderable: DMO-PFD-WVN-001 (pfd), DMO-PFD-KNT-001 (pfd), DMO-PFP-WVN-001 (pfp)
```

## Data acuan (hanya-baca)
```
db.products.countDocuments({}) = 282
db.products.countDocuments({needs_review:true}) = 41
db.products.countDocuments({domain_gaps:{$exists:true,$ne:[]}}) = 0
stage dist: yarn 2, grey 2, pfd 2, pfp 1, finished 273, remnant 1, byproduct 1
yarn vs satuan (harus berat/count): 0 cacat ; fabric vs satuan (harus length/weight): 0 cacat
```

## Catatan UI (tak jadi potret)
Agen UI tak bisa menavigasi ke form Master Produk: md/manager mendarat di dashboard Sales/POS; `admin@` ter-logout saat
command palette. (Dicatat sebagai hambatan + sinyal UX; bukan temuan terverifikasi.) Perilaku dropdown `base_unit`
dikonfirmasi via kode: tak tersaring stage (MS-04).

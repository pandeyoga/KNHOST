# Bukti — metode, perintah, dan batas

HEAD diaudit: `91a3ec0612952bfcc88335668ef2b3f601ba926a`.

## Batas lingkungan sesi audit

- Audit **baca-saja** (H2 server · H3 data · H8 rahasia — `docs/blueprint/00_ATURAN_EKSEKUSI.md` §6).
- Backend tidak dijalankan: `backend/.env` tidak memuat `MONGO_URL` (backend crash `KeyError: 'MONGO_URL'` di `backend/db.py:10`), DB acuan belum di-seed (`listDatabases` → admin/config/local/test_database saja), `docker` tidak tersedia. Menyetel env / seed = melanggar batas, jadi tidak dilakukan.
- Konsekuensi: bukti = **kode (berkas:baris)** + **langkah reproduksi** untuk diputar di stack acuan pemilik
  (`docker compose -f docker-compose.dev.yml up -d` lalu `bash scripts/dev_restore_demo.sh`). Potret layar diambil saat
  pelaksana menjalankan unit perbaikan.

## Perintah kunci yang dipakai (hanya-baca, bisa diputar ulang)

```bash
git log -1 --format='%H %ci %s'                       # commit HEAD

# A/MS
grep -nE 'Prepared for|Pre-treatment' backend/domain_registry.py            # dua sistem label (55/57 vs 448-461)
grep -rl 'STAGE_TRANSITIONS' backend --include=*.py                          # hanya line_scope.py + domain_registry.py
grep -rnE 'save_product\(' backend --include=*.py | grep strict             # strict=False: special_order_service:317, admin:184/192
sed -n '91,102p' backend/routers/products.py                                # _apply_domain -> 400 (pintu Master menegakkan)
sed -n '137,172p' backend/services/product_variant_service.py               # validasi hanya bila strict
sed -n '60,92p'  backend/services/special_order_service.py                   # stage default "" (:64)

# B/MK
grep -n 'makloon-orders\|realize-makloon' frontend/src/features/purchasing/makloon/MakloonWizard.jsx   # :305/:307
grep -n 'makloon-orders' frontend/src/features/purchasing/MakloonOrderCreateModal.jsx                   # :192
sed -n '67,82p' frontend/src/features/purchasing/makloon/MakloonStepEditor.jsx                          # dropdown tak disaring
sed -n '289,312p' backend/services/makloon_order_service.py                                             # needs_vendor = peringatan

# C/RD (pintu SKU)
grep -rnE '@router.(post).*(products|product-templates|release-product|create-sku)' backend/routers/*.py

# E/QM
grep -rnE '@router.(post|put)' backend/routers/inspections.py backend/routers/qc_inspection.py          # grade-override :169

# F/SO
for s in fulfillment_service fulfillment_decision_service fulfillment_plan_service fulfillment_wizard_service; do
  grep -nE '^async def |^def ' backend/services/$s.py; done                                             # 4 kalkulator ketersediaan
grep -rln 'import.*fulfillment' backend/routers/*.py                                                    # konsumen per pintu
```

## Kueri data acuan yang DISARANKAN (untuk pelaksana, hanya-baca)

```javascript
// MS: produk dengan stage kosong/tak sah
db.products.countDocuments({ $or: [ {stage: {$in: [null, ""]}}, {stage: {$nin: ["yarn","grey","pfd","pfp","finished","remnant","byproduct"]}} ] })
// MS: produk yang stage-nya tidak cocok satuan (benang bukan kg, kain bukan meter/yard) — sesuaikan field base_unit
// SO-01: ambil 1 SO kurang stok, panggil tiap pintu fulfillment, bandingkan angka 'tersedia/kurang'
// QM-01: roll yang grade-nya berubah via grade-override tanpa SPK 4-point terkait
```

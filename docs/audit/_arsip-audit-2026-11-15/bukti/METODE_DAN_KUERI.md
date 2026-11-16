# Bukti — metode, perintah, batas, dan koreksi

HEAD diaudit: `91a3ec0612952bfcc88335668ef2b3f601ba926a`.

## Batas lingkungan

- Audit baca-saja (H2 server · H3 data · H8 rahasia). Backend tidak dijalankan: `backend/.env` tanpa `MONGO_URL`
  (crash `KeyError: 'MONGO_URL'` di `backend/db.py:10`); DB acuan belum di-seed (`listDatabases` → admin/config/local/test_database);
  `docker` tak tersedia. Menyetel env/seed = melanggar batas → tidak dilakukan.
- Bukti = kode (berkas:baris) + langkah reproduksi untuk diputar di stack acuan pemilik
  (`docker compose -f docker-compose.dev.yml up -d`; `bash scripts/dev_restore_demo.sh`).

## Koreksi terhadap pass awal (jejak audit jujur)

| Klaim awal | Status | Fakta |
|---|---|---|
| MS-01 "SKU Pesanan Khusus ber-stage kosong" | diralat | `stamp_domain_defaults` mengisi stage `finished` (`domain_registry.py:1233`); temuan benar = produk cacat-domain disimpan sebagai `domain_gaps` (`strict=False`) |
| MS-02 "86 titik tulis stage langsung" | diralat | hitungan tercemar proyeksi Mongo `{"stage":1}` & `journey.stage`; temuan benar = dua sumber transisi paralel + validator tak dipakai jalur produksi |
| QM-01 "dua pintu grade / aturan tak ditegakkan" | **ditarik** | grade satu penulis `grade_service.set_roll_grade` + `grade_history`; override terkendali |
| RT-02 "uang/stok ganda retur" | diturunkan | belum terbukti; settlement lewat satu state machine; jadi pertanyaan-perlu-data |

## Perintah kunci (hanya-baca, bisa diputar ulang)

```bash
git log -1 --format='%H %ci %s'

# A/MS-01
sed -n '91,102p' backend/routers/products.py                 # form -> 400
sed -n '137,172p' backend/services/product_variant_service.py # validasi hanya bila strict
sed -n '1219,1270p' backend/domain_registry.py               # stamp_domain_defaults: default finished + domain_gaps (strict=False tak lempar)
grep -rn 'save_product(' backend --include=*.py | grep strict # special_order:317, admin:184/192

# A/MS-02 (dua sumber transisi)
grep -rn 'STAGE_TRANSITIONS' backend --include=*.py           # def + enums + transition_matrix; line_scope hanya komentar
grep -rn 'resolve_transition(\|check_transition(' backend --include=*.py | grep -v 'def '  # enums:98, lot_service:497
grep -n 'stage_by_process_type\|stage_meta\|active_stages' backend/services/master_registry.py  # sumber makloon

# B/MK-01 (dua pintu aktif)
grep -rln '<MakloonWizard\|MakloonWizard(' frontend/src --include=*.jsx
grep -rln '<MakloonOrderCreateModal\|MakloonOrderCreateModal(' frontend/src --include=*.jsx

# E/QM-01 (grade satu penulis)
grep -rn 'set_roll_grade(' backend --include=*.py | grep -v 'def '

# F/SO-01 (divergensi ketersediaan)
grep -n 'stock_figures' backend/services/fulfillment_service.py backend/services/fulfillment_decision_service.py
grep -n 'inventory_balances\|inventory_rolls' backend/services/fulfillment_plan_service.py backend/services/fulfillment_wizard_service.py
```

## Kueri data acuan yang disarankan (pelaksana, hanya-baca)

```javascript
// MS-01: produk cacat-domain yang lolos
db.products.countDocuments({ domain_gaps: { $exists: true } })
db.products.countDocuments({ needs_review: true })
// SO-01: pilih SO kurang stok dgn roll di gudang tak-dihitung / cadangan makloon, bandingkan angka tiap pintu fulfillment
// MS-02: diff GET /api/enums transitions (STAGE_TRANSITIONS) vs master process_stages (dipakai makloon)
```

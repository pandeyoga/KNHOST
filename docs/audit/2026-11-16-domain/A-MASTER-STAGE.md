# A — Master data & jenis barang (stage) — audit §8

HEAD kode diaudit: `91a3ec0`. Lingkungan: backend hidup (8001, `test_database`, MongoDB asli), data acuan ter-seed (282 produk, 46.535 roll, 20 akun `demo12345`). Skenario dijalankan via API/data acuan + kueri hanya-baca; mutasi uji dicatat & dibersihkan. Navigasi layar (1280/390) terhambat (md/manager mendarat di POS; admin ter-logout di command palette) — skenario yang butuh layar ditandai `terhambat` dengan alasan.

## Peta sumber kebenaran: field `stage` (tekstil) — semua penulis

Kata `stage` overloaded (approval/CRM/SO/produksi memakai kata sama). Penulis **stage tekstil** (produk/roll/lot) ditemukan lewat:

```
grep -rnE '\$set.*"stage"|"stage":|save_product\(|stamp_domain_defaults\(' backend/services backend/routers | grep -viE 'from_stage|to_stage|stage_code|journey|"stage": 1'
grep -rn 'resolve_transition(\|check_transition(' backend --include=*.py | grep -v 'def '
```

Penulis terbukti (berkas:baris di HEAD):
- `backend/services/product_variant_service.py:137` — `save_product` (validasi hanya bila `strict=True`).
- `backend/routers/products.py:100` — pintu form (`_apply_domain`→`validate_product`, 400).
- `backend/services/special_order_service.py:310` + `backend/services/special_order_service.py:317` — Pesanan Khusus (`strict=False`).
- `backend/routers/admin.py:122` + `backend/routers/admin.py:184` — impor (`strict=False`).
- `backend/services/lot_service.py:515` — rework (`$set stage`, cek transisi hanya bila `to_stage` diisi `backend/services/lot_service.py:497`).
- `backend/services/rnd_spec_service.py:87` — R&D rilis produk.
Validator transisi `resolve_transition` (`backend/domain_registry.py:949`) dipanggil HANYA `backend/routers/enums.py:98`; makloon pakai master `process_stages` (`backend/services/master_registry.py:199`). Dua sumber transisi paralel.

## Pintu ganda

| Pekerjaan | Pintu sekarang | Seharusnya |
|---|---|---|
| Membuat/menegakkan domain SKU | form `products.py:114` (400) · template `product_templates.py:116` · R&D `rnd.py:325` · Pesanan Khusus `special_orders.py:1303` (strict=False) · impor `admin.py:184` (strict=False) | satu kebijakan validasi di semua pintu |
| Transisi stage sah | `STAGE_TRANSITIONS` kode (enums+lot) vs master `process_stages` (makloon) | satu sumber + satu validator |
| Katalog jual | `is_orderable` (lifecycle saja) | tambah aturan stage |

## Matriks skenario

| Skenario | Status | Bukti/alasan |
|---|---|---|
| A-S1 | lulus | bukti/A-S1.txt — form menolak finished-tanpa-GSM (400), stage tak dikenal (400), yarn tanpa field wajib (400); finished valid 200 |
| A-S2 | lulus | bukti/A-S2.txt — PATCH ubah stage produk ber-stok finished→grey **200 tanpa penjaga transisi** (MS-06), cascade ke template, lalu buntu saat restore |
| A-S3 | terhambat | varian/spec R&D: data acuan 0 `product_specs`/`special_orders`; form A-F3 butuh alur R&D (disiapkan sesi C) |
| A-S4 | lulus | bukti/A-S4.txt — katalog orderable memuat 3 produk non-finished (pfd/pfp) → POS bisa jual greige-siap (MS-05) |
| A-S5 | lulus | bukti/runtime/E-S1.txt — PO greige: satuan `kg` diterima (ada aturan konversi), `lusin` ditolak 400 (tanpa aturan konversi); PO 300 yard diterima, jurnal GR Dr 1-1300/Cr 2-1150 Rp4.200.000 |
| A-S6 | gagal | bukti/runtime/A-S6.txt — lewat API: (1) printing dari bahan GREIGE padahal langkah `stage_from_stage=pfp` → 200; (2) celup di mitra yang `process_types`-nya tanpa celup, bahan benang → 200; (3) bahan jadi → benang (transisi mundur) → 200 (MK-02, MS-02). Lewat layar belum dijalankan |
| A-S7 | terhambat | tambah/nonaktifkan tahapan master `process_stages`: butuh layar master tahapan + SPK pemakai; disiapkan sesi B |
| A-S8 | lulus | bukti/A-S8.txt — dua label PFP/PFD di domain_registry + grey/greige & benang/yarn tersebar (MS-03) |
| A-S9 | lulus | bukti/A-S9.txt — 282 produk, 41 needs_review, 0 domain_gaps keras, 0 roll tanpa stage |

## Inventaris form & dropdown

| Form | Field | Sumber pilihan | Saringan yang ada | Ditegakkan server? | Masalah |
|---|---|---|---|---|---|
| ProductMasterForm.jsx | category (98) | prop `categoryOptions` | — | tidak | kategori bebas |
| ProductMasterForm.jsx | motif (103) | `masters.motifOptions` | searchable | — | tak per aktif/PT |
| ProductMasterForm.jsx | supplier (103) | `masters.supplierOptions` | searchable | — | tak per aktif/PT |
| ProductMasterForm.jsx | base_unit (108) | `baseUnitOptions` (uoms) | TIDAK per stage | sebagian (validate_product) | MS-04: dropdown tak tersaring stage |
| ProductMasterForm.jsx | stage (151) | registry `options("stage")` | tak disaring | ya (400) | semua stage dapat dipilih (wajar master) |
| ProductMasterForm.jsx | fabric_type (159) | registry | tak per stage | ya | — |
| ProductMasterForm.jsx | line_code (174) | registry `product_line` | — | ya | — |
| ProductMasterForm.jsx | grade (191) | registry `grade` | — | ya | grade KNSelect muncul 2× (191 & 221) |
| ProductMasterForm.jsx | grade-yarn (221) | registry `grade` | hanya blok yarn | ya | duplikasi testid dgn 191 |
| ProductMasterForm.jsx | yarn_count_system (235) | registry | blok yarn | ya | — |
| ProductMasterForm.jsx | yarn_material (244) | registry | blok yarn | ya | — |
| ProductMasterForm.jsx | yarn_twist (255) | registry | blok yarn | ya | — |
| ProductMasterForm.jsx | yarn_dye_status (261) | registry | blok yarn | ya | — |
| VariantEditor.jsx | variant-option axes (44) | `a.options` (template axes) | per sumbu template | sebagian | nilai sumbu tak divalidasi domain |
| VariantEditor.jsx | variant-status (46) | konstan [active/…] | — | ya | — |
| VariantEditor.jsx | variant-tax-treatment (59) | `TAX_TREATMENTS` | — | ya | — |
| SpecVariantFields.jsx | spec-family-select (156) | induk produk (fetch) | — | ya | — |
| SpecVariantFields.jsx | spec-axis (165) | `optionList(a)` | per sumbu | sebagian | — |
| LinkExistingVariant.jsx | link-variant-product (14) | `products.map` | — | ya | tak disaring stage/aktif |
| LinkExistingVariant.jsx | link-variant-axis (15) | `a.options` | per sumbu | sebagian | — |
| EntityMastersView.jsx | (tak ada komponen pilihan) | daftar PT (CRUD) | — | — | ikuti anak: tak ada dropdown; master PT berupa tabel |
| UomConversionView.jsx | calc-product (210) | `productOptions` | — | — | — |
| UomConversionView.jsx | filter-dimension (250) | konstan dimensi | — | — | — |
| UomConversionView.jsx | filter-kind (255) | konstan kind | — | — | — |
| UomConversionView.jsx | rule-from (302) | `unitOptions()` | per dimensi? | ya | — |
| UomConversionView.jsx | rule-to (309) | `unitOptions()` | per dimensi? | ya | — |
| UomConversionView.jsx | rule-kind (317) | `kinds` | — | ya | — |
| UomConversionView.jsx | rule-formula (327) | konstan formula | — | ya | — |
| PoStageModal.jsx | po-stage-status (100) | `options` (transisi tahap PO) | per tahap sekarang | ya | — |
| CuttingDesk.jsx | aksi potong/antrian (1 komponen) | status/aksi potong | per tugas | ya | satu komponen pilihan; alur potong |

## Temuan

### MS-01 — pintu non-form menyimpan produk cacat-domain; form menolak 400
- Keparahan: Tinggi
- Jenis akar: aturan tidak ditegakkan seragam / pintu ganda
- Tingkat bukti: terbukti runtime
- Bukti: `backend/routers/admin.py:184` & `backend/services/special_order_service.py:317` (`strict=False`) vs `backend/routers/products.py:100` (400); bukti runtime `bukti/RUNTIME-DOMAIN-A.md` (impor 200 menyimpan stage `ngaco999`).
- Reproduksi: `POST /api/products` finished tanpa gramasi → 400; impor CSV sama → 200 tersimpan `domain_gaps`. Lihat `bukti/A-S1.txt`, `bukti/RUNTIME-DOMAIN-A.md`.
- Dampak: produk cacat (bahkan stage tak sah) masuk katalog lewat impor/Pesanan Khusus.
- Arah perbaikan: satu kebijakan `validate_product` di semua pintu (tolak atau needs_review seragam).
- Keputusan pemilik: tolak atau needs_review untuk pintu non-form?
- Sudah ada: RD-01 (akar sama).

### MS-02 — dua sumber transisi stage; validator tak dipakai jalur produksi
- Keparahan: Tinggi
- Jenis akar: duplikasi / aturan tidak ditegakkan
- Tingkat bukti: terbukti runtime (lewat MS-06: PATCH menulis stage tanpa validator)
- Bukti: `backend/domain_registry.py:949` (`resolve_transition`) dipanggil hanya `backend/routers/enums.py:98`; makloon `backend/services/master_registry.py:199`; `backend/services/lot_service.py:515`.
- Reproduksi: PATCH stage produk ber-stok (A-S2) berhasil tanpa cek transisi; `bukti/A-S2.txt`.
- Dampak: dua daftar transisi bisa menyimpang; transisi stage praktis nominal.
- Arah perbaikan: satu sumber transisi + satu validator dipanggil tiap penulis stage.
- Keputusan pemilik: master `process_stages` atau konstanta kode jadi kebenaran?
- Sudah ada: MS-06 (penulis langsung).

### MS-03 — dua sistem label stage + salinan hardcode
- Keparahan: Sedang
- Jenis akar: duplikasi
- Tingkat bukti: terbukti runtime (grep)
- Bukti: `backend/domain_registry.py:55` & `backend/domain_registry.py:57` vs `backend/domain_registry.py:448`; `bukti/A-S8.txt`.
- Reproduksi: `bukti/A-S8.txt` daftar label PFP/PFD & grey/greige.
- Dampak: istilah stage tak konsisten antar layar.
- Arah perbaikan: satu daftar label dari server; hapus hardcode.
- Keputusan pemilik: istilah baku (PFP/PFD vs pre-treatment; grey vs greige)?
- Sudah ada: —

### MS-04 — dropdown Satuan Dasar tak disaring menurut stage
- Keparahan: Sedang (server menolak kombinasi lewat validate_product; ini soal UI dropdown)
- Jenis akar: pilihan salah (UI)
- Tingkat bukti: dugaan (baca kode) — server ternyata menolak yarn tanpa field wajib (A-S1), penegakan satuan-dimensi-per-stage belum diuji terpisah
- Bukti: `frontend/src/features/admin/products/ProductMasterForm.jsx:52` (`baseUnitOptions` statis).
- Reproduksi: buka Master Produk, stage=yarn, dropdown Satuan tetap memuat meter/yard (perlu layar; terhambat navigasi).
- Dampak: pengguna bisa memilih satuan tak lazim; server menolak sebagian.
- Arah perbaikan: saring dimensi satuan per stage di dropdown.
- Keputusan pemilik: satuan apa sah per stage?
- Sudah ada: —

### MS-05 — katalog POS/orderable memuat barang non-finished
- Keparahan: Tinggi
- Jenis akar: aturan tidak ditegakkan / pilihan salah
- Tingkat bukti: terbukti runtime
- Bukti: `backend/routers/products.py:44` (`is_orderable`, lifecycle saja); `bukti/A-S4.txt` (pfd/pfp orderable).
- Reproduksi: `GET /api/products?orderable_only=true` → DMO-PFD-WVN-001 (pfd) dll; `bukti/A-S4.txt`.
- Dampak: barang setengah jadi bisa dijual di POS tanpa penghalang stage.
- Arah perbaikan: tambah aturan stage pada katalog jual.
- Keputusan pemilik: stage mana boleh dijual di POS?
- Sudah ada: —

### MS-06 — update produk menulis stage langsung tanpa penjaga transisi (cascade template)
- Keparahan: Tinggi
- Jenis akar: cacat logika / aturan tidak ditegakkan
- Tingkat bukti: terbukti runtime
- Bukti: `backend/routers/products.py:167` (`update_product`) menulis stage via `backend/services/product_variant_service.py:137` tanpa `backend/domain_registry.py:949` (`resolve_transition`); `bukti/A-S2.txt`.
- Reproduksi: PATCH produk ber-stok finished→grey → 200; template ikut grey; restore 400 (buntu). `bukti/A-S2.txt`.
- Dampak: stage produk ber-stok bisa dibalik tanpa cek transisi/stok; roll tertinggal di stage lama; cascade template bisa membuat kebuntuan.
- Arah perbaikan: update stage lewat validator transisi tunggal + cek stok/roll + tangani cascade template.
- Keputusan pemilik: boleh ubah stage produk yang sudah punya stok/dokumen?
- Sudah ada: MS-02.

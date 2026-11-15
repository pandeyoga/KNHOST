# A — Master data & jenis barang (stage)

HEAD: `91a3ec0`. Sumber kebenaran rancangan: `backend/domain_registry.py` (`STAGES`, `STAGE_TRANSITIONS`, `PROCESS_TYPES`).

---

## MS-01 — Validasi stage domain di-bypass lewat `save_product(strict=False)`

- **Keparahan:** Kritis
- **Jenis akar:** aturan tidak ditegakkan + pintu ganda + pilihan salah
- **Bukti (berkas:baris di HEAD):**
  - Pintu Master menegakkan: `backend/routers/products.py:100-102` → `_apply_domain` memanggil `dr.validate_product` dan **melempar 400** bila stage/fabric/grade tak sah.
  - `backend/services/product_variant_service.py:137` — `save_product(..., strict=True)`. Validasi domain hanya jalan bila `strict` (baris `166-172`).
  - **Bypass:** `backend/services/special_order_service.py:317` memanggil `save_product(..., strict=False)`. Di fungsi yang sama, `backend/services/special_order_service.py:64` menetapkan `"stage": _spec("stage", "tahap", default="")` → **stage bisa kosong**.
  - **Bypass impor:** `backend/routers/admin.py:184` dan `:192` juga `save_product(..., strict=False)`.
- **Akibat:** SKU yang lahir dari **Pesanan Khusus** dan **impor master-data** bisa tersimpan dengan `stage` kosong atau tak sah, sedangkan SKU yang dibuat dari **Master Produk** ditolak untuk kasus yang sama. Inilah akar keluhan "aturan stage barang belum ditegakkan" dan "dropdown asal": produk bercatat stage tak konsisten lalu muncul di dropdown tempat-tempat lain.
- **Langkah reproduksi (data acuan):**
  1. Buat Pesanan Khusus lalu jalankan `POST /api/special-orders/{id}/create-sku` tanpa mengisi `stage` pada spesifikasi.
  2. Amati produk baru tersimpan (`GET /api/products/{id}`) dengan `stage` kosong.
  3. Bandingkan: `POST /api/products` dengan payload stage kosong/tak sah → **400** dari `_apply_domain`.
- **Potret (saat menjalankan perbaikan):** form Pesanan Khusus → create-sku, lalu Master Produk menampilkan produk tanpa stage di daftar/dropdown.
- **Dampak uang/stok:** produk tanpa stage menyesatkan pemilihan di makloon/POS/retur dan kelengkapan wajib per stage (GSM/lebar) tak terjamin → data acuan kotor.
- **Arah perbaikan (bukan kode):** jadikan `dr.validate_product` **satu jalur wajib** di semua pintu penulis produk; hapus mode `strict=False` atau batasi hanya untuk migrasi terkontrol dengan laporan pelanggaran.
- **Keputusan pemilik:** Pertanyaan #1 (stage wajib di semua pintu?).

---

## MS-02 — `STAGE_TRANSITIONS` tidak ditegakkan; stage ditulis langsung

- **Keparahan:** Tinggi
- **Jenis akar:** cacat logika / aturan tidak ditegakkan
- **Bukti:**
  - `STAGE_TRANSITIONS` didefinisikan di `backend/domain_registry.py` tetapi **satu-satunya** konsumen di luar file itu adalah `backend/services/line_scope.py` (hasil `grep -rl STAGE_TRANSITIONS backend`).
  - Penulisan field `stage` langsung tersebar: **86** kemunculan penulisan `stage` di `backend/services/*.py` (di luar `from_stage/to_stage/stage_code`).
- **Akibat:** tidak ada penjaga tunggal yang memastikan perpindahan stage (makloon per langkah, potong, perbaikan, R&D, penerimaan) sah menurut tabel transisi. Stage bisa meloncat tahap.
- **Langkah reproduksi:** telusuri satu roll yang stage-nya berubah lewat makloon/potong dan bandingkan pasangan (from→to) dengan `STAGE_TRANSITIONS`; cari jalur yang menulis `stage` tanpa mengecek tabel.
- **Arah perbaikan:** satu fungsi `transition_stage(from, to, konteks)` yang memvalidasi terhadap `STAGE_TRANSITIONS`, dipanggil setiap penulis `stage`.

---

## MS-03 — Dua sistem label stage + salinan hardcode di frontend

- **Keparahan:** Sedang
- **Jenis akar:** duplikasi
- **Bukti:**
  - `backend/domain_registry.py:55` `"PFD — Prepared for Dyeing"`, `:57` `"PFP — Prepared for Printing"` vs `:448-461` `"PFP — Pre-treatment untuk printing"` / `"PFD — Pre-treatment untuk celup"`. Satu konsep, dua label.
  - Salinan daftar stage hardcode di ±14 `.jsx` (hasil grep), mis. `frontend/src/features/admin/domain/DomainRegistryParts.jsx`, `frontend/src/features/inventory/lots/LotParts.jsx`, `frontend/src/features/purchasing/makloon/MakloonWizard.jsx`, `frontend/src/features/purchasing/makloon/MakloonStepEditor.jsx`.
- **Akibat:** label stage tidak konsisten antar layar; pemilik melihat istilah berbeda untuk hal yang sama.
- **Arah perbaikan:** satu sumber label (server), layar membaca dari endpoint enum/stages; hapus daftar hardcode.

---

## MS-04 — Dropdown stage langkah makloon tidak disaring; from_stage tak diadu dengan bahan masuk

- **Keparahan:** Tinggi (lihat juga B/MK-02)
- **Jenis akar:** pilihan dropdown salah + aturan tidak ditegakkan
- **Bukti:**
  - `frontend/src/features/purchasing/makloon/MakloonStepEditor.jsx:67-68` — `stageOpts` memetakan **seluruh** `stageOptions` tanpa menyaring menurut stage bahan masuk / `from_stage`.
  - `backend/services/makloon_order_service.py` — `_resolve_stage` (±56–97) mengisi `from_stage/to_stage` dari master, tetapi **tidak ada** pembanding antara stage roll input dengan `from_stage` langkah (grep `from_stage` hanya di :96/:434/:1928, semuanya penulisan, bukan validasi).
- **Akibat:** layar menawarkan langkah (mis. "printing", from_stage=pfp) untuk bahan yang belum PFP; server tidak menolak atas dasar stage → bahan salah-tahap bisa diproses.
- **Langkah reproduksi:** buat SPK makloon dengan roll stage `grey`, pilih langkah `printing`; amati dropdown memuat semua tahap dan server menerima.
- **Arah perbaikan:** saring dropdown menurut stage bahan masuk + validasi server `input.stage == step.from_stage` (lewat satu fungsi transisi MS-02).

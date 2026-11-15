# A — Master data & jenis barang (stage) — audit mendalam

HEAD: `91a3ec0`. Lingkungan audit: **backend hidup** (sandbox, `test_database`, MongoDB asli lokal, data acuan ter-seed:
282 produk, 46.535 roll, 20 akun peran `demo12345`; `seed_p03` gagal spt catatan perintah §6). Bukti runtime diproduksi sendiri.

## Ringkas temuan domain A

| ID | Keparahan | Jenis akar | Status bukti |
|---|---|---|---|
| MS-01 | Tinggi | aturan tidak ditegakkan seragam | **runtime-verified** (form 400 vs impor 200) |
| MS-02 | Tinggi | duplikasi + aturan tidak ditegakkan | kode |
| MS-03 | Sedang | duplikasi | kode |
| MS-04 | Tinggi | pilihan dropdown salah | kode + konfirmasi UI; 0 data cacat di seed |
| MS-05 | Tinggi | aturan tidak ditegakkan / pilihan salah | **runtime-verified** (PFD/PFP orderable di POS) |

---

## MS-01 — Pintu non-form menyimpan produk cacat-domain; pintu form menolaknya (RUNTIME-VERIFIED)

- **Keparahan:** Tinggi · **Jenis akar:** aturan tidak ditegakkan seragam (pintu ganda)
- **Temuan asli (kode, HEAD):**
  - Pintu form menolak: `backend/routers/products.py:100-102` — `_apply_domain` → `dr.validate_product`; error → **HTTP 400**.
  - `backend/services/product_variant_service.py:166-172` — validasi domain di `save_product` hanya bila `strict=True`.
  - Pintu impor: `backend/routers/admin.py:87-132` `_validate_and_enrich_product` **hanya** memeriksa SKU/nama/price/gambar; `stage` diambil mentah (`:122`); lalu `save_product(..., strict=False)` (`:184/192`) → **tak ada validasi domain**.
  - Pintu Pesanan Khusus: `special_order_service.py:310` `stamp_domain_defaults(...)` (default `finished`, tandai `domain_gaps`, tak lempar) + `:317` `save_product(strict=False)`.
- **Uji yang DIJALANKAN (bukti diproduksi):**
  ```
  # Pintu FORM (token md) — finished tanpa gramasi/lebar
  POST /api/products {sku:AUDIT-TEST-X1,stage:finished,category:Tenun}  → HTTP 400
    detail: "Jenis kain … wajib … Gramasi/GSM wajib … Lebar kain wajib … 'Finished'"
  POST /api/products {stage:ngaco123, gramasi:180, lebar:1.5}            → HTTP 400 (stage tak dikenal)
  # Pintu IMPOR (token admin) — CSV berisi finished tanpa GSM + stage ngaco999
  POST /api/master-data/import-products?dry_run=false (upload CSV)       → HTTP 200 {created:2}
  ```
  Hasil tersimpan (dikueri balik lalu dihapus lagi untuk kebersihan):
  - `AUDIT-IMP-1` stage=finished, gramasi=0, lebar=0, `needs_review=true`, `domain_gaps=[Gramasi wajib…, Lebar wajib…]`
  - `AUDIT-IMP-2` **stage=`ngaco999` (tak sah) tetap tersimpan**, `domain_gaps=[Tahap 'ngaco999' tidak dikenal…]`
- **Bantahan yang dicoba:** (a) stage tak dikenal via impor → **tetap lolos** (form menolak); (b) via form dengan field sama → **ditolak 400**. Asimetri terbukti di dua arah.
- **Data acuan:** `db.products.countDocuments({needs_review:true})` = **41**; `{domain_gaps:{$exists:true,$ne:[]}}` = **0** di data seed (seed menutupnya). Jadi risiko keras belum termaterialisasi di seed, tetapi **terbukti bisa** lewat impor.
- **Dampak:** produk cacat-domain (bahkan stage tak sah) bisa masuk katalog lewat impor/Pesanan Khusus lalu mengalir ke makloon/POS/retur; pintu form menolaknya — inkonsistensi yang membingungkan pemilik.
- **Arah perbaikan:** satu kebijakan penegakan domain di semua pintu (tolak, atau `needs_review` yang sama). `_validate_and_enrich_product` harus memanggil `dr.validate_product`/`stamp_domain_defaults(strict=…)` sesuai kebijakan.
- **Keputusan pemilik:** boleh simpan `needs_review` atau wajib tolak? (Pertanyaan #1)
- **Putusan audit:** **reopened/baru (open)** — cacat nyata, runtime-verified.

---

## MS-05 — Katalog POS/orderable menyertakan barang non-finished (RUNTIME-VERIFIED)

- **Keparahan:** Tinggi · **Jenis akar:** aturan tidak ditegakkan / pilihan salah — **menjawab keluhan "bisakah greige dijual di POS"**
- **Temuan (kode):** `backend/routers/products.py:44-45` — katalog jual/beli (POS/Sales Portal) menyaring dengan `rnd_gate.is_orderable(p)`. `backend/services/rnd_gate.py:is_orderable` = `status=='active' AND lifecycle in ORDERABLE` — **tidak memeriksa `stage`**.
- **Uji yang DIJALANKAN (token sales):**
  ```
  GET /api/products?orderable_only=true → HTTP 200, 278 produk
  distribusi stage: finished 273, pfd 2, pfp 1, byproduct 1, remnant 1
  NON-finished yang bisa dipesan: 3 → DMO-PFD-WVN-001 (pfd), DMO-PFD-KNT-001 (pfd), DMO-PFP-WVN-001 (pfp)
  ```
- **Dampak:** barang setengah jadi (PFD/PFP — siap celup/printing) & by-product muncul sebagai barang jual di POS tanpa penghalang stage. Bila tak disengaja → salah jual; bila disengaja (kadang greige dijual) → perlu ditegaskan sebagai aturan, bukan kebetulan gate lifecycle.
- **Bantahan:** `yarn`/`grey` TIDAK muncul di orderable pada data seed (lifecycle/status menyaringnya), jadi efeknya saat ini terbatas pada pfd/pfp/byproduct — tetapi gate tidak menjamin apa pun soal stage.
- **Arah perbaikan:** tambahkan aturan stage pada katalog jual (daftar stage yang boleh dijual, dari pengaturan), bukan hanya lifecycle.
- **Keputusan pemilik:** stage mana yang boleh dijual di POS? (Pertanyaan #3)
- **Putusan audit:** **open** (baru).

---

## MS-02 — Dua sumber transisi stage paralel; validator tak dipakai jalur produksi

- **Keparahan:** Tinggi · **Jenis akar:** duplikasi + aturan tidak ditegakkan
- **Bukti:** Sumber (1) `domain_registry.py:682` `STAGE_TRANSITIONS` + `resolve_transition`(`:949`)/`check_transition`(`:1024`) — pemanggil nyata HANYA `routers/enums.py:98` & `lot_service.py:497` (rework, hanya bila `to_stage` diisi; lalu tulis `$set stage` langsung `:515/520`). Sumber (2) master `process_stages` (`master_registry.py:173/183/199`) — dipakai makloon (`makloon_order_service._resolve_stage:56-101`). `line_scope.py:27` menyebut `STAGE_TRANSITIONS` hanya di komentar. Makloon `receive_step:1019` tak mengadu stage roll input vs `from_stage`/output vs `to_stage`.
- **Dampak:** dua daftar transisi bisa menyimpang; transisi pada jalur produksi utama praktis nominal.
- **Arah perbaikan:** satu sumber transisi + satu validator dipanggil tiap penulis stage. **Keputusan pemilik #2.**

---

## MS-03 — Dua sistem label stage + salinan hardcode

- **Keparahan:** Sedang · **Jenis akar:** duplikasi
- **Bukti:** `domain_registry.py:55/57` ("Prepared for …") vs `:448-461` ("Pre-treatment …"); salinan daftar stage hardcode di ±14 `.jsx`.
- **Catatan (jujur):** `ProductMasterForm.jsx` SENDIRI justru BAIK — membaca stage/fabric/grade dari registry server (`useDomainEnums`, `options("stage")` dst), bukan hardcode. Masalah hardcode ada di layar lain (LotParts, DomainRegistryParts, MakloonWizard, MakloonStepEditor).

---

## MS-04 — Dropdown `base_unit` (Satuan Dasar) tidak disaring menurut stage

- **Keparahan:** Tinggi · **Jenis akar:** pilihan dropdown salah
- **Bukti (form inventaris + konfirmasi UI):** `ProductMasterForm.jsx:52-55` — `baseUnitOptions = uomSelectOptions({dimensions:["length","weight","count"], extra:[...]})` — **statis**, tidak bergantung `stage`. Variabel `stage` (`:66`) hanya mengatur field wajib & panel yarn, TIDAK menyaring satuan. → benang bisa dipilih "meter"; kain bisa "kg".
- **Data acuan (jujur):** `yarn products: 2 | satuan bukan berat/count: 0` dan `fabric: 278 | satuan bukan length/weight: 0`. Jadi **belum ada data cacat**; ini celah form (bukan data rusak).
- **Catatan desain:** komentar `:46-50` menyatakan menampilkan semua satuan master itu disengaja (ekstensibilitas). Saring sebaiknya berdasar **dimensi per stage**, bukan daftar hardcode.
- **Arah perbaikan:** saring dimensi satuan menurut stage (yarn→weight/count; kain→length/weight) + validasi server. **Keputusan pemilik:** satuan apa yang sah per stage?

---

## Inventaris form A-F1: `ProductMasterForm.jsx` (11 komponen pilihan)

| # | Komponen (baris) | Sumber pilihan | Saringan ada? | Ditegakkan server? | Masalah |
|---|---|---|---|---|---|
| 1 | category (98-100) | prop `categoryOptions` | — | tidak (kategori bebas) | — |
| 2 | motif (103-105) | `masters.motifOptions` (useCatalogMasters) | searchable; tak per PT/aktif | — | pilihan master tak tersaring aktif/PT |
| 3 | supplier (103-105) | `masters.supplierOptions` | idem | — | idem |
| 4 | **base_unit (108-110)** | `uomSelectOptions` (master uoms) | **TIDAK per stage** | uom_rules cek konversi, bukan stage | **MS-04** |
| 5 | **stage (151-153)** | registry `options("stage")` (server) | tak disaring | ya (`validate_product`) | semua stage dapat dipilih (wajar utk master) |
| 6 | fabric_type (159-161) | registry `options("fabric_type")` | tak per stage | ya | — |
| 7 | line_code (174-177) | registry `options("product_line")` | — | ya (FASE L) | — |
| 8 | grade (191-193) | registry `options("grade")` | — | ya | **KNSelect grade muncul 2×** (191 & 221) dgn testid sama → duplikasi JSX |
| 9–12 | yarn_count_system/material/twist/dye_status (235-263) | registry | hanya tampil saat stage=yarn | ya (bila diisi) | — |
| 13 | color (ColorPicker 275) | pencari warna | — | — | — |

Kesimpulan inventaris: sumber pilihan **baik** (registry server, bukan hardcode) — kecuali `base_unit` tak tersaring stage (MS-04) dan grade terduplikasi di JSX (minor).

---

## Peta sumber kebenaran: field `stage` (tekstil) — SEMUA penulis

Kata `stage` sangat overloaded (approval/CRM/SO/produksi memakai kata sama). Penulis **stage tekstil** (produk/roll/lot):

| Penulis | Berkas:baris | Validasi transisi/domain? |
|---|---|---|
| Master (form) | `product_variant_service.save_product` (via `products.py:114/patch`) | ya bila `strict=True` (default) |
| Template | `product_template_service.py:67,313` (+validate `:90,341`) | ya |
| R&D spec→produk | `rnd_spec_service.py:87,118` (+validate `:403`) | ya |
| **Pesanan Khusus** | `special_order_service.py:290,317` | **tidak** (`strict=False`) |
| **Impor** | `admin.py:122,184/192` | **tidak** (`strict=False`) |
| **Lot rework** | `lot_service.py:515,520` (`$set stage`) | hanya bila `to_stage` diisi (`:496 check_transition`) |
| Makloon output | (memakai `output_product_id` yang sudah ada) | tidak menulis `product.stage`; stage ikut produk output |

Pintu ganda tanpa penegakan seragam → **MS-01**. Transisi tak lewat validator tunggal → **MS-02**.

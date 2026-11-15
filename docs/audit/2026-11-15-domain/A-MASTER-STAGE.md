# A — Master data & jenis barang (stage)

HEAD: `91a3ec0`.

---

## MS-01 — Pintu non-form menyimpan produk cacat-domain; pintu form menolaknya

- **Keparahan:** Tinggi
- **Jenis akar:** aturan tidak ditegakkan seragam (pintu ganda)
- **Fakta terverifikasi:**
  - Pintu form menolak keras: `backend/routers/products.py:100-102` — `_apply_domain` → `dr.validate_product`; bila ada error (mis. field wajib per stage belum lengkap) → **HTTP 400**.
  - `backend/services/product_variant_service.py:166-172` — validasi domain di `save_product` **hanya** jalan bila `strict=True`.
  - Pintu Pesanan Khusus: `backend/services/special_order_service.py:310` memanggil `stamp_domain_defaults(product, source="special_order")` **tanpa** `strict`/`fill_measurements`, lalu `:317` `save_product(..., strict=False)`.
  - `backend/domain_registry.py:1233-1234` — stage kosong di-default ke `finished` (bukan dibiarkan kosong; **koreksi klaim pass awal**). `:1259-1267` — bila `validate_product` menemukan **error** (mis. `gramasi`/`lebar` wajib untuk `finished`), dokumen ditandai `needs_review=True` + `domain_gaps[]` tetapi **tidak** dilempar karena `strict=False`.
  - Pintu impor: `backend/routers/admin.py:184` dan `:192` juga `save_product(..., strict=False)`.
- **Akibat:** satu produk dengan kelengkapan domain yang sama bisa **ditolak** di Master Produk tetapi **lolos tersimpan** (sebagai `domain_gaps`/`needs_review`) dari Pesanan Khusus/impor. Produk cacat lalu ikut mengalir ke makloon/POS/retur. Inilah dasar keluhan "aturan stage barang belum ditegakkan".
- **Langkah reproduksi (data acuan):**
  1. `POST /api/products` dengan stage `finished` tanpa `gramasi`/`lebar` → **400**.
  2. Buat Pesanan Khusus tanpa gramasi/lebar → approve → `POST /api/special-orders/{id}/create-sku` → produk **tersimpan** dengan `needs_review=true` & `domain_gaps`.
  3. Kueri acuan: `db.products.countDocuments({domain_gaps: {$exists:true}})` dan `{needs_review:true}`.
- **Arah perbaikan (bukan kode):** satu kebijakan — pemilik memutuskan pintu non-form juga menolak, atau form juga boleh `needs_review`. Hilangkan asimetri.
- **Keputusan pemilik:** Pertanyaan #1.

---

## MS-02 — Dua sumber transisi stage paralel; validator tak dipakai jalur produksi

- **Keparahan:** Tinggi
- **Jenis akar:** duplikasi + aturan tidak ditegakkan
- **Fakta terverifikasi:**
  - Sumber (1): `backend/domain_registry.py:682` `STAGE_TRANSITIONS`; validator `resolve_transition` (`:949`) & `check_transition` (`:1024`, pembungkus non-raise). **Pemanggil nyata hanya:** `routers/enums.py:98` (API utk FE) dan `services/lot_service.py:497` (rework) — itupun lot **hanya** memvalidasi bila `to_stage` diisi (`lot_service.py:496 "if target:"`).
  - Sumber (2): master `process_stages` (FASE T, tabel DB) lewat `services/master_registry.py` (`stage_by_process_type:199`, `stage_meta:183`, `active_stages:173`) — dipakai **makloon** `makloon_order_service._resolve_stage` (`:56-101`).
  - `STAGE_TRANSITIONS` disebut di `line_scope.py:27` **hanya sebagai komentar** (bukan kode).
  - Makloon `receive_step` (`:1019`) memakai `output_product_id` yang sudah ada; **tidak** membandingkan stage roll input vs `from_stage`, maupun stage produk output vs `to_stage` (grep `from_stage` hanya di `:96/:434/:1928`, semua penulisan).
- **Akibat:** dua daftar transisi bisa menyimpang (master DB diedit pemilik vs konstanta kode). Makloon menawarkan/menerima langkah menurut master; produk forms & lot menurut kode. Transisi stage pada jalur produksi utama praktis **nominal** (label), tak ditegakkan terhadap stage nyata bahan.
- **Langkah reproduksi:** bandingkan `GET /api/enums/.../transitions` (dari `STAGE_TRANSITIONS`) dengan master `process_stages` (dipakai makloon); cari pasangan from→to yang ada di satu tetapi tidak di lain. Lalu buat SPK makloon memakai roll stage salah dan amati server tetap menerima.
- **Arah perbaikan:** satu sumber transisi; satu validator dipanggil tiap penulis stage (makloon, potong, lot, penerimaan).
- **Keputusan pemilik:** Pertanyaan #2.

---

## MS-03 — Dua sistem label stage + salinan hardcode di frontend

- **Keparahan:** Sedang · **Jenis akar:** duplikasi
- **Bukti:** `domain_registry.py:55` "PFD — Prepared for Dyeing", `:57` "PFP — Prepared for Printing" vs `:448-461` "PFP/PFD — Pre-treatment untuk …". Salinan daftar stage hardcode di ±14 `.jsx` (mis. `features/admin/domain/DomainRegistryParts.jsx`, `features/inventory/lots/LotParts.jsx`, `features/purchasing/makloon/MakloonWizard.jsx`, `MakloonStepEditor.jsx`).
- **Akibat:** istilah stage tak konsisten antar layar.
- **Arah perbaikan:** satu daftar label dari server; layar membaca endpoint enum; hapus hardcode.

---

## MS-04 — Dropdown stage langkah makloon tak disaring; server tak cek stage bahan masuk

(lihat juga B/MK-02)

- **Keparahan:** Tinggi · **Jenis akar:** pilihan dropdown salah + aturan tidak ditegakkan
- **Bukti:** `frontend/src/features/purchasing/makloon/MakloonStepEditor.jsx:67-68` memetakan **seluruh** `stageOptions` tanpa saring menurut stage bahan masuk/`from_stage`; server (`makloon_order_service._resolve_stage`) tak membandingkan (lihat MS-02).
- **Akibat:** langkah "printing" (from_stage=pfp) bisa ditawarkan & diterima untuk bahan `grey`/`pfd`.
- **Arah perbaikan:** saring dropdown menurut stage bahan masuk + validasi server `input.stage == step.from_stage` lewat validator tunggal (MS-02).

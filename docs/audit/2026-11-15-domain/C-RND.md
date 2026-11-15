# C — R&D dan desain

HEAD: `91a3ec0`.

---

## RD-01 — Penciptaan SKU punya 4–5 pintu; penegakan domain tidak seragam

- **Keparahan:** Tinggi
- **Jenis akar:** pintu ganda + aturan tidak ditegakkan
- **Bukti (berkas:baris):**
  - Master: `backend/routers/products.py:114` (`POST /products`) → validasi strict (`_apply_domain`).
  - Template: `backend/routers/product_templates.py:116` generate-variants → `product_template_service.py:340-341` `dr.validate_product` (strict).
  - R&D: `backend/routers/rnd.py:325` `POST /rnd/specs/{id}/release-product` → `rnd_spec_service.py:403` `dr.validate_product`.
  - Pesanan Khusus: `backend/routers/special_orders.py:1303` `POST /special-orders/{id}/create-sku` → `special_order_service.py:317` `save_product(strict=False)` → **tanpa** validasi domain (lihat MS-01).
  - Impor massal: `backend/routers/admin.py:184/192` `save_product(strict=False)`.
- **Akibat:** empat sampai lima pintu melahirkan SKU; hanya tiga menegakkan validasi domain. SKU dari Pesanan Khusus/impor bisa lahir cacat lalu masuk produksi/makloon → keluhan "R&D kacau dari awal sampai akhir" sebagian berakar di pintu pembuatan SKU yang tidak seragam.
- **Langkah reproduksi:** jalankan keempat pintu dengan spesifikasi stage kosong; hanya create-sku & impor yang lolos.
- **Arah perbaikan:** satu jalur validasi domain wajib (`dr.validate_product`) di semua pintu; create-sku & impor memakai jalur yang sama (hapus `strict=False`).
- **Keputusan pemilik:** Pertanyaan #1.
- **Sudah ada:** terkait **MS-01** (akar yang sama di `save_product`).

---

## Catatan alur R&D (tindak lanjut di data acuan)

Alur permintaan → sample → keputusan pelanggan → spesifikasi → SKU/varian → produksi/makloon, serta gerbang `rnd_gate`
yang ditawarkan layar vs ditolak server, dan KPI desainer, memerlukan dataset acuan untuk reproduksi runtime penuh.
Temuan struktural pintu-ganda SKU (RD-01) sudah tegak di tingkat kode. Modul terkait untuk telaah lanjutan: `rnd_flow_service`,
`rnd_gate`, `rnd_spec_service`, `rnd_sample_service`, `design_*_service`, `special_order_routing`.

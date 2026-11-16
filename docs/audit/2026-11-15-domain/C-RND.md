# C — R&D dan desain

HEAD: `91a3ec0`.


> **Status domain: BELUM DIKERJAKAN.** Skenario wajib §8 dan inventaris form domain ini belum dijalankan. Semua isi di bawah berlabel **dugaan (baca kode)** sampai diuji lewat layar/API pada sesi domainnya.
---

## RD-01 — 4–5 pintu pembuatan SKU; penegakan domain tidak seragam

- **Keparahan:** Tinggi · **Jenis akar:** pintu ganda + aturan tidak ditegakkan (akar sama MS-01)
- **Tingkat bukti:** dugaan (baca kode)
- **Bukti terverifikasi:**
  - Master: `routers/products.py:114` → `_apply_domain` strict (400).
  - Template: `routers/product_templates.py:116` → `product_template_service.py:340-341` `dr.validate_product` (strict).
  - R&D: `routers/rnd.py:325` `release-product` → `rnd_spec_service.py:403` `dr.validate_product` (strict).
  - Pesanan Khusus: `routers/special_orders.py:1303` → `special_order_service.py:317` `save_product(strict=False)` → simpan `domain_gaps` (lihat MS-01).
  - Impor: `routers/admin.py:184/192` `save_product(strict=False)`.
- **Akibat:** tiga pintu menolak produk cacat-domain, dua pintu menyimpannya sebagai `needs_review`. SKU cacat dari Pesanan Khusus/impor masuk produksi/makloon → bagian dari keluhan "R&D kacau".
- **Langkah reproduksi:** jalankan kelima pintu dengan spesifikasi kurang field wajib; hanya create-sku & impor yang lolos.
- **Arah perbaikan:** satu kebijakan penegakan domain di semua pintu.
- **Keputusan pemilik:** Pertanyaan #1. **Sudah ada:** akar sama **MS-01**.

---

## Verifikasi runtime (sesi backend hidup)

Status: **TERHAMBAT-DATA**. `db.special_orders.countDocuments({})` = **0** di data acuan (seed tidak membuat Pesanan Khusus). Maka pintu `create-sku` (RD-01) tak bisa dipicu lewat data acuan di sesi ini. Namun akar RD-01 = **sama dengan MS-01** yang sudah **runtime-verified lewat pintu impor** (produk cacat-domain, bahkan stage tak sah, tersimpan via `save_product(strict=False)`; lihat `bukti/RUNTIME-DOMAIN-A.md`). Jadi cacat penegakan domain pada pintu `strict=False` sudah terbukti; khusus jalur R&D→sample→spec→SKU perlu data acuan R&D untuk reproduksi runtime penuh.

## Tindak lanjut R&D (butuh data acuan)

Alur permintaan → sample → keputusan pelanggan → spesifikasi → SKU/varian → produksi/makloon; gerbang `rnd_gate` yang
ditawarkan layar vs ditolak server; KPI desainer dari data benar — memerlukan reproduksi runtime dengan dataset acuan.
Modul: `rnd_flow_service`, `rnd_gate`, `rnd_spec_service`, `rnd_sample_service`, `design_*_service`, `special_order_routing`.
Di sesi ini belum diaudit tuntas tingkat-alur (dicatat jujur sebagai celah cakupan, bukan "bersih").

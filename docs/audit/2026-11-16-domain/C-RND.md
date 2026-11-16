# C — R&D & desain — audit §8

HEAD: `91a3ec0`. Data acuan: 0 `product_specs`/`special_orders` di seed → alur R&D E2E `terhambat`; akar RD-01 sudah terbukti runtime lewat MS-01 (pintu `strict=False`). Pendalaman E2E perlu buat data R&D (sesi khusus).

## Peta sumber kebenaran: pembuatan SKU dari R&D

```
grep -rnE 'release-product|create-sku|generate-variants' backend/routers
grep -rnE 'validate_product|save_product\(' backend/services/rnd_spec_service.py backend/services/special_order_service.py
```
Penulis: `backend/routers/products.py:114` (master) · `backend/routers/product_templates.py:116` (template) · `backend/routers/rnd.py:325`→`backend/services/rnd_spec_service.py:403` (strict) · `backend/routers/special_orders.py:1303`→`backend/services/special_order_service.py:317` (strict=False).

## Pintu ganda

| Pekerjaan | Pintu | Seharusnya |
|---|---|---|
| Buat SKU dari R&D/khusus | master / template / rnd release / special-order create-sku | satu kebijakan validasi domain |
| Sumber stage/fabric form spec | `SpecFormModal` `STAGE_OPTS`/`FABRIC_OPTS` hardcode | server registry |

## Matriks skenario

| Skenario | Status | Bukti/alasan |
|---|---|---|
| C-S1 | terhambat | pintu R&D `POST /rnd/specs` menolak 400 ("Pilih Asal yang sah untuk induk") — alur sample→SKU belum dilanjutkan; bukti/runtime/C-S1-S2.txt |
| C-S2 | gagal | bukti/runtime/C-S1-S2.txt — `create-sku` Pesanan Khusus melahirkan MTO-261116-0002 tanpa GSM/lebar (`needs_review`, 2 `domain_gaps`) dan SKU itu langsung muncul di katalog `orderable_only` POS (RD-02) |
| C-S3 | terhambat | sample tolak/revisi: butuh data sample |
| C-S4 | terhambat | gerbang R&D layar vs server: butuh alur rnd_gate berjalan |
| C-S5 | terhambat | SKU R&D→produksi/makloon: butuh rilis produk |
| C-S6 | terhambat | KPI desainer: butuh data skor desain |

## Inventaris form & dropdown

| Form | Field | Sumber pilihan | Saringan | Ditegakkan server? | Masalah |
|---|---|---|---|---|---|
| SpecFormModal.jsx | sample-type (224) | `typeOpts` | — | ya | — |
| SpecFormModal.jsx | stage (235) | `STAGE_OPTS` hardcode | — | ya | hardcode (MS-03) |
| SpecFormModal.jsx | fabric (240) | `FABRIC_OPTS` hardcode | — | ya | hardcode |
| SpecFormModal.jsx | axis/attr (272) | opsi sumbu | per sumbu | sebagian | — |
| SpecFormModal.jsx | axis (276) | opsi sumbu | per sumbu | sebagian | — |
| SpecFormModal.jsx | axis (284) | opsi sumbu | per sumbu | sebagian | — |
| SpecFormModal.jsx | axis (288) | opsi sumbu | per sumbu | sebagian | — |
| SpecFormModal.jsx | attr (318) | opsi | — | sebagian | — |
| SpecFormModal.jsx | attr (339) | opsi | — | sebagian | — |
| SpecFormModal.jsx | attr (371) | opsi | — | sebagian | — |
| SpecFormModal.jsx | unit (374) | satuan | TIDAK per stage | sebagian | mirip MS-04 |
| SpecFormModal.jsx | grade/line (lain) | registry/opsi | — | ya | — |
| SampleFormModal.jsx | sample-type (201) | pencari tipe | — | ya | — |
| SampleFormModal.jsx | unit (308) | `masters` | — | ya | — |
| ExistingSkuSection.jsx | supplier (39) | opsi supplier | — | ya | tak per aktif/PT |
| SpecDetailPanel.jsx | (ikuti anak) | pakai SpecVariantFields | — | — | tak ada dropdown sendiri |
| DivisionsView.jsx | divisi (328) | `optionsFor` | — | ya | — |

## Temuan

### RD-01 — 4–5 pintu pembuatan SKU; penegakan domain tak seragam
- Keparahan: Tinggi
- Jenis akar: pintu ganda / aturan tidak ditegakkan
- Tingkat bukti: terbukti runtime (akar sama MS-01)
- Bukti: `backend/services/special_order_service.py:317` (strict=False) vs `backend/routers/products.py:100` (400); `bukti/RUNTIME-DOMAIN-A.md`.
- Reproduksi: impor/create-sku lolos produk cacat; form 400. `bukti/A-S1.txt`, `bukti/RUNTIME-DOMAIN-A.md`.
- Dampak: SKU cacat dari R&D/khusus masuk produksi.
- Arah perbaikan: satu kebijakan validasi domain di semua pintu.
- Keputusan pemilik: tolak atau needs_review pintu non-form?
- Sudah ada: MS-01.

### RD-02 — SKU dari Pesanan Khusus lahir cacat-domain dan langsung bisa dijual di POS
- Keparahan: Tinggi
- Jenis akar: aturan tidak ditegakkan
- Tingkat bukti: terbukti runtime (API, data uji berlabel `[UJI-AUDIT-1116]`)
- Bukti: `backend/routers/special_orders.py:1303` · `backend/routers/rnd.py:218` (pintu R&D menolak) · `bukti/runtime/C-S1-S2.txt`
- Reproduksi: `POST /special-orders/sord_ae9d5543756c/create-sku` → 200, SKU `MTO-261116-0002` stage finished tanpa GSM/lebar, `needs_review: true`; `GET /products?orderable_only=true&q=MTO-261116-0002` (akun sales) memuatnya. `POST /rnd/specs` dengan isian minimal → 400.
- Dampak: Barang yang datanya belum lengkap bisa masuk pesanan; konversi satuan dan laporan per gramasi salah.
- Arah perbaikan: Produk `needs_review` dikeluarkan dari katalog jual sampai dilengkapi; satu aturan untuk semua pintu.
- Keputusan pemilik: Sama dengan pertanyaan 1 ringkasan (tolak vs tandai).
- Sudah ada: MS-01, MS-05, RD-01

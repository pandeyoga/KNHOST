# Audit domain (R5) — ringkasan

- **Commit HEAD yang diaudit:** `91a3ec0612952bfcc88335668ef2b3f601ba926a` (2026-11-15, "R5 — perintah audit domain untuk reviewer").
- **Perintah:** `docs/reviews/PERINTAH_AUDIT_DOMAIN_2026-11-15.md`.
- **Sifat:** baca-saja. Tidak ada kode/data/server/`main` yang diubah.
- **Catatan lingkungan:** di sesi audit ini backend tidak bisa dijalankan tanpa melanggar batas baca-saja
  (`backend/.env` tidak memuat `MONGO_URL`; DB acuan belum di-seed; `docker` tidak tersedia). Sesuai H2/H3
  (`docs/blueprint/00_ATURAN_EKSEKUSI.md` §6) auditor **tidak** mem-boot server atau menyetel env. Maka bukti bersifat
  **kode (berkas:baris di HEAD)** disertai **langkah reproduksi presisi** yang bisa diputar ulang di dataset acuan pemilik
  (`bash scripts/dev_restore_demo.sh`). Potret layar tidak diambil karena tidak ada stack acuan yang hidup; tiap temuan
  menyertakan langkah agar pemilik/pelaksana dapat memotret saat menjalankan unit perbaikan.

## Prinsip yang dipakai

Keluhan UI/UX diperlakukan sebagai **gejala**. Untuk tiap gejala ditelusuri sampai akar: duplikasi pintu, aturan yang
hanya ada di layar atau tidak ada, pilihan dropdown dari sumber salah, transisi status yang ditawarkan layar tetapi
ditolak server.

## Peta duplikasi — "pekerjaan → pintu yang ada → yang seharusnya satu"

| Pekerjaan | Pintu yang ada sekarang | Yang seharusnya |
|---|---|---|
| Membuat SKU/produk | `routers/products.py:114` (Master, strict) · `routers/product_templates.py:116` generate-variants (strict) · `routers/rnd.py:325` release-product (strict) · `routers/special_orders.py:1303` create-sku (**strict=False**) · impor `routers/admin.py:184/192` (**strict=False**) | satu jalur validasi domain (`dr.validate_product`) wajib di SEMUA pintu |
| Menegakkan transisi stage kain | `STAGE_TRANSITIONS` (`domain_registry.py`) hanya dibaca `services/line_scope.py`; 86 titik menulis `stage` langsung | satu fungsi transisi yang dipanggil setiap penulis `stage` |
| Label stage PFP/PFD | `domain_registry.py` baris 55/57 ("Prepared for …") vs 448–461 ("Pre-treatment untuk …") + ±14 `.jsx` dengan daftar hardcode | satu daftar dari server, dibaca semua layar |
| Membuat SPK makloon | `MakloonWizard.jsx` (dari PR → `/makloon-orders`) vs `MakloonOrderCreateModal.jsx` (dari resep → `/makloon-orders`) | satu alur pembuatan (atau dua mode satu wizard) |
| Memutuskan pemenuhan SO (ATP/alokasi) | `fulfillment_service` · `fulfillment_decision_service` · `fulfillment_plan_service` · `fulfillment_wizard_service` — 4 kalkulator ketersediaan, 4 router | satu sumber ketersediaan + satu pintu keputusan |
| Menetapkan grade satu roll | `routers/inspections.py` (SPK 4-point / mdq-cut) vs `routers/qc_inspection.py:169` grade-override | satu pintu keputusan grade |

## 10 masalah terbesar (urut dampak)

1. **SO-01 (Kritis)** — empat modul fulfillment menghitung ketersediaan sendiri-sendiri; layar berbeda bisa menampilkan angka berbeda untuk SO yang sama (akar keluhan alokasi/tagihan berubah).
2. **MS-01 (Kritis)** — validasi stage domain di-bypass lewat `save_product(strict=False)`; SKU dari Pesanan Khusus & impor bisa lahir dengan stage kosong/tak sah, padahal Master Produk menolaknya.
3. **MS-02 (Tinggi)** — `STAGE_TRANSITIONS` praktis tak ditegakkan; stage ditulis langsung di 86 titik.
4. **MK-01 (Tinggi)** — dua pintu pembuatan SPK makloon.
5. **MK-02 / MS-04 (Tinggi)** — `from_stage` langkah makloon tidak diadu dengan stage bahan masuk; dropdown stage langkah tak disaring → langkah "printing" bisa menerima bahan non-PFP.
6. **RD-01 (Tinggi)** — penciptaan SKU punya 4–5 pintu; hanya sebagian menegakkan validasi domain.
7. **QM-01 (Tinggi)** — dua pintu menetapkan grade satu roll (SPK 4-point vs grade-override).
8. **MS-03 (Sedang)** — dua sistem label stage + salinan hardcode di ±14 `.jsx`.
9. **RT-02 (Sedang)** — banyak pintu penyelesaian retur (settlement/compensation/replacement/cutloss) — risiko uang/stok ganda; perlu peta penulis di data acuan.
10. **MK-03 (Sedang)** — langkah makloon mitra bisa disimpan tanpa mitra (peringatan, bukan penolakan — keputusan pemilik 3b; berisiko macet di Issue/Catat Jasa).

## Duplikasi yang harus disatukan lebih dulu (sebelum perbaikan UI)

1. Ketersediaan & keputusan pemenuhan SO (SO-01).
2. Satu jalur validasi domain untuk semua pintu pembuatan SKU (MS-01 + RD-01).
3. Satu fungsi transisi stage (MS-02).

## Pertanyaan untuk pemilik (keputusan bisnis, bernomor)

1. **Stage saat pembuatan SKU:** boleh-kah SKU dibuat tanpa stage (mis. dari Pesanan Khusus/impor), atau stage wajib diisi & sah di semua pintu? (menentukan MS-01/RD-01)
2. **Jual non-finished di POS:** apakah benang/greige/PFD/PFP boleh dijual di POS, atau hanya `finished` + `remnant`/`byproduct` tertentu? (menentukan aturan katalog POS)
3. **Dua pintu makloon:** pertahankan dua pintu (PR vs resep) atau satukan jadi satu wizard dua-mode? (MK-01)
4. **Grade override:** siapa (izin apa) yang boleh mengubah grade di luar SPK 4-point, dan apakah override harus menulis jejak ke SPK? (QM-01)
5. **Keep/pending → buka lagi:** bila alokasi berubah sesudah DP/pembayaran, tagihan ikut alokasi terakhir atau terkunci di nilai bayar? (SO — lihat F)
6. **Makloon tanpa mitra:** tetap izinkan SPK darurat tanpa mitra (3b) atau wajibkan mitra sejak awal? (MK-03)

Perbaikan tidak dikerjakan di sesi audit. Daftar temuan ada di `docs/reviews/TRACKER.md` (bagian "Audit domain — 2026-11-15") berstatus `open`.

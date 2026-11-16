# Audit domain (R5) — ringkasan

- **Commit HEAD yang diaudit:** `91a3ec0612952bfcc88335668ef2b3f601ba926a` (2026-11-15).
- **Perintah:** `docs/reviews/PERINTAH_AUDIT_DOMAIN_2026-11-15.md`.
- **Sifat:** baca-saja. Tidak ada kode/data/server/`main` yang diubah.
- **Skala repo:** 456 service (`backend/services`), 177 router, 869 file fitur frontend.
- **Lingkungan:** backend acuan tidak dijalankan (`backend/.env` tanpa `MONGO_URL`; DB acuan belum di-seed; `docker` tak tersedia). Sesuai H2/H3, auditor tidak mem-boot server atau menyetel env. Bukti = **kode (berkas:baris di HEAD)** + **langkah reproduksi** untuk diputar di dataset acuan pemilik (`bash scripts/dev_restore_demo.sh`). Potret layar diambil saat pelaksana menjalankan unit perbaikan.

## Metode & kejujuran audit

Tiap klaim ditelusuri ke kode sampai terbukti/gugur. **Dua klaim pass awal dikoreksi setelah verifikasi** (dicatat agar jejak audit jujur):

1. **Dulu diklaim** "SKU Pesanan Khusus lahir dengan stage kosong" → **salah**: `stamp_domain_defaults` mengisi stage default `finished`. Temuan yang benar (MS-01): produk cacat-domain (kekurangan field WAJIB per stage) tetap **disimpan** sebagai `domain_gaps`/`needs_review` karena `strict=False`, sedangkan pintu form menolak 400.
2. **Dulu diklaim** "dua pintu keputusan grade / aturan grade tak ditegakkan" (QM-01) → **salah / ditarik**: grade roll punya **satu penulis** `grade_service.set_roll_grade()` dengan `grade_history`; `grade-override` adalah jalur koreksi terkendali (izin `wms:approve` + alasan wajib). Lihat `E-QC-MDQ.md`.

## Status per domain dan tingkat bukti (label ditetapkan pemilik, 16 Nov)

| Domain | Status |
|---|---|
| A master & stage | 7 dari 9 skenario dijalankan; A-S3, A-S7 terhambat |
| B makloon | 3 dari 10 dijalankan; sisanya terhambat |
| C R&D | 1 dari 6 dijalankan; sisanya terhambat |
| D retur | 6 dari 8 dijalankan; D-S3, D-S7 terhambat |
| E QC & MD Quality | 3 dari 6 dijalankan; sisanya terhambat |
| F pesanan sesudah POS | 5 dari 8 dijalankan; F-S4, F-S6, F-S7 terhambat |

Pendalaman runtime 16 Nov (16 temuan baru, koreksi QM-01/SO-01/MK-02): [`PENDALAMAN_RUNTIME.md`](PENDALAMAN_RUNTIME.md). Layar belum dipotret.

| ID | Tingkat bukti |
|---|---|
| MS-01, MS-05 | terbukti runtime |
| MS-02, MS-03, MS-04, MK-01, MK-02, MK-03, RD-01, RT-01, RT-02, QM-01, SO-01 | dugaan (baca kode) |

Tidak ada status "withdrawn". QM-01 tetap open sebagai dugaan beserta uji runtime yang dibutuhkan (lihat `E-QC-MDQ.md`).

## Peta duplikasi — "pekerjaan → pintu yang ada → yang seharusnya satu"

| Pekerjaan | Pintu/sumber sekarang | Yang seharusnya |
|---|---|---|
| Membuat SKU/produk & menegakkan domain | form `products.py:114`/`patch` (strict, 400) · template `product_templates.py:116` (strict) · R&D `rnd.py:325` (strict) · Pesanan Khusus `special_orders.py:1303` (**strict=False**, simpan `domain_gaps`) · impor `admin.py:184/192` (**strict=False**) | satu kebijakan: tolak vs `needs_review` sama di semua pintu |
| "Transisi stage apa yang sah" | **(1)** `domain_registry.STAGE_TRANSITIONS` + `resolve_transition` (dipakai HANYA `routers/enums.py` + `lot_service` rework) vs **(2)** master `process_stages` + `master_registry`/`_resolve_stage` (dipakai makloon) | satu sumber transisi; satu validator dipanggil semua jalur |
| Menegakkan transisi pada perubahan stage nyata | lot-rework (`lot_service:497`, hanya bila `to_stage` diisi); makloon TIDAK cek stage roll input vs `from_stage`; potong menulis stage langsung | satu validator wajib di tiap penulis stage |
| Label stage PFP/PFD | `domain_registry.py:55/57` ("Prepared for …") vs `448-461` ("Pre-treatment …") + ±14 `.jsx` hardcode | satu daftar dari server |
| Membuat SPK makloon | `MakloonWizard` (MakloonOrdersView + PrSourcingPanel) vs `MakloonOrderCreateModal` (PurchaseOrderManagement) — dua pintu aktif → `/makloon-orders` | satu wizard dua-mode |
| Angka "stok tersedia" untuk pemenuhan SO | `fulfillment_service` + `decision_service` = SSOT `stock_figures` (FIX-2) **tetapi** `plan_service` & `wizard_service` baca `inventory_balances`/`inventory_rolls` MENTAH | semua pintu baca `stock_figures` |

## 10 masalah terbesar (urut dampak)

1. **MS-01** (Tinggi, terbukti runtime) — pintu non-form menyimpan produk cacat-domain; form menolak 400.
2. **MS-05** (Tinggi, terbukti runtime) — katalog POS/orderable memuat non-finished (pfd/pfp).
3. **MS-06** (Tinggi, terbukti runtime) — PATCH produk ubah stage ber-stok tanpa penjaga transisi, cascade template.
4. **MS-02** (Tinggi) — dua sumber transisi stage paralel; validator tak dipakai jalur produksi.
5. **SO-01** (Tinggi, dugaan) — plan/wizard hitung ketersediaan dari koleksi mentah (risiko laten).
6. **RD-01** (Tinggi, dugaan) — 4–5 pintu pembuatan SKU, penegakan domain tak seragam.
7. **MK-01** (Sedang, dugaan) — dua pintu aktif pembuatan SPK makloon.
8. **MK-02** (Tinggi, dugaan) — langkah makloon tak mengadu stage bahan masuk.
9. **MS-03** (Sedang) — dua label stage + salinan hardcode.
10. **MS-04** (Sedang) — dropdown Satuan Dasar tak disaring stage.
11. **RT-02** (Rendah, dugaan) — banyak sub-service penyelesaian retur.
12. **QM-01** (dugaan) — pintu keputusan grade (baca kode: satu penulis).


1. **SO-01 (Kritis, duplikasi):** `plan_service` & `wizard_service` menghitung ketersediaan dari koleksi mentah, melewati saringan gudang-dihitung & alokasi makloon yang dipakai papan ATP/meja keputusan → layar berbeda, angka berbeda untuk SO yang sama. **Akar keluhan alokasi/tagihan berubah.**
2. **MS-01 (Tinggi, aturan tidak ditegakkan seragam):** pintu non-form menyimpan produk cacat-domain (`domain_gaps`), pintu form menolak 400.
3. **MS-02 (Tinggi, duplikasi + aturan tidak ditegakkan):** dua sumber transisi stage paralel; jalur produksi utama (makloon/potong) tak lewat validator transisi.
4. **MS-05 (Tinggi, RUNTIME-VERIFIED):** katalog POS/orderable memuat barang non-finished (PFD/PFP/byproduct) karena `is_orderable` cek lifecycle saja, bukan stage — menjawab keluhan "bisakah greige dijual di POS".
5. **MS-04/MK-02 (Tinggi, pilihan salah + aturan tidak ditegakkan):** dropdown Satuan Dasar di Master Produk & dropdown stage langkah makloon tak disaring menurut stage (0 data cacat di seed — celah form, bukan data rusak).

> **Catatan pendalaman (Domain A):** diaudit dengan backend hidup + data acuan. MS-01 & MS-05 runtime-verified (bukti diproduksi, lihat `bukti/RUNTIME-DOMAIN-A.md`). Domain B–F masih tingkat kode; pendalaman runtime menyusul per domain.
5. **RD-01 (Tinggi, pintu ganda):** 4–5 pintu pembuatan SKU, penegakan domain tak seragam (akar sama MS-01).
6. **MK-01 (Sedang, pintu ganda):** dua pintu aktif pembuatan SPK makloon.
7. **MS-03 (Sedang, duplikasi):** dua label stage + ±14 salinan hardcode.
8. **MK-03 (Sedang, status/keputusan pemilik):** langkah mitra bisa disimpan tanpa mitra (3b).
9. **RT-02 (Rendah/perlu data):** banyak sub-service penyelesaian retur — risiko uang/stok ganda belum terbukti; settlement tampak lewat satu state machine. Perlu reproduksi data acuan.
10. **RT-01 (info):** pembagian state retur terverifikasi SAH (bukan duplikat).
11. **QM-01 (open, dugaan):** pintu keputusan grade — baca kode menunjuk satu penulis; belum diuji runtime.

## Duplikasi yang harus disatukan lebih dulu

1. Angka ketersediaan SO — arahkan `plan_service` & `wizard_service` ke `stock_figures` (SO-01).
2. Satu sumber transisi stage — satukan `STAGE_TRANSITIONS` (kode) dengan master `process_stages` (DB) (MS-02).
3. Satu kebijakan penegakan domain di semua pintu SKU (MS-01 + RD-01).

## Pertanyaan untuk pemilik (keputusan bisnis)

1. **Produk cacat-domain dari pintu non-form (Pesanan Khusus/impor):** boleh disimpan sebagai `needs_review` lalu dilengkapi, atau harus ditolak seperti pintu form? (MS-01/RD-01)
2. **Sumber transisi stage:** master `process_stages` (bisa diedit pemilik) yang jadi satu-satunya kebenaran, atau konstanta kode `STAGE_TRANSITIONS`? (MS-02)
3. **Jual non-finished di POS:** benang/greige/PFD/PFP boleh dijual, atau hanya `finished`? (perlu aturan katalog POS — lihat F)
4. **Dua pintu makloon:** satukan jadi satu wizard dua-mode? (MK-01)
5. **Keep/pending → buka lagi + alokasi berubah sesudah DP:** tagihan ikut alokasi terakhir atau terkunci nilai bayar? (F)
6. **Makloon tanpa mitra:** tetap izinkan SPK darurat (3b) atau wajibkan mitra? (MK-03)

Perbaikan tidak dikerjakan di sesi audit. Daftar temuan: `docs/reviews/TRACKER.md` → "Audit domain — 2026-11-15".

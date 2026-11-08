# PREP-A — Lembar perbaikan master produk (K-OPN-01 · K-OPN-06)

Tanggal: 9 Nov 2026 · Paket persiapan RFID A (paralel dengan B opname awal, C fondasi gudang, D1 inti gate).
Dasar keputusan: `docs/rfid/KEPUTUSAN_GATE_RFID.md` §8 — **K-OPN-01** (data stok lama hanya referensi; master
dirapikan dulu) dan **K-OPN-06** (SKU salah tidak diubah; produk berkode benar dibuat, kode lama dinonaktifkan &
"digantikan oleh"; lembar kerja → impor satu batch ber-pratinjau & bisa dibatalkan).

## 1. Ringkasan
Master Produk → *Tata kelola master* kini punya panel **"Perbaikan master produk (lembar kerja)"**:

1. **Unduh lembar** (XLSX; CSV UTF-8 ber-BOM sebagai cadangan `?format=csv`) berisi semua produk yang TERLIHAT oleh
   user (`catalog_access.visible_query`, kolom grade ikut aturan *field visibility*): identitas, artikel (induk),
   stage/lini/jenis kain (berlabel), warna & kode warna, motif, grade, gramasi, lebar, satuan, status, pengganti saat
   ini; referensi stok lama (roll · qty + per gudang, dari `inventory_balances`), jumlah & nomor **dokumen terbuka**;
   saran **kelompok duplikat** + **saran kode induk**; 5 kolom tindakan (kuning, daftar pilihan); sheet *Petunjuk*.
2. **Unggah → pratinjau** (tidak menulis apa pun): galat/peringatan per baris dalam Bahasa Indonesia + ringkasan per
   tindakan + tanda tangan pratinjau.
3. **Terapkan** (ConfirmDialog, catatan batch wajib ≥ 5 huruf) = satu batch berjejak `master_cleanup_batches`;
   **Batalkan** (alasan wajib) membalik semuanya.
4. **`superseded_by`**: SKU tergantikan hilang dari pemilih produk dokumen BARU, pencarian dengan SKU lama memberi
   petunjuk "SKU X digantikan oleh Y", laporan & riwayat tetap utuh. Helper `services/product_supersede.py` untuk paket lain.

## 2. Berkas
Baru:
* `backend/services/product_supersede.py` — `not_superseded_query`, `exclude_superseded`, `chain`, **`resolve_active(product_id)`**, `hints(text)`, `annotate(products)`.
* `backend/services/master_cleanup_refs.py` — dokumen terbuka per produk (18 koleksi, satu query/koleksi, `limit 5000`), stok lama, calon duplikat (union-find).
* `backend/services/master_cleanup_sheet.py` — susun baris, tulis XLSX/CSV, baca unggahan (kepala dicari otomatis).
* `backend/services/master_cleanup_validate.py` — pratinjau/validasi + tanda tangan.
* `backend/services/master_cleanup_service.py` — terapkan (saga: rencana durable → `atomic_claim.claim` → CAS per baris → `finish_set`) & batalkan.
* `frontend/src/features/catalog/MasterCleanupPanel.jsx`, `MasterCleanupPreview.jsx`, `masterCleanupApi.js`.
* `frontend/src/components/SupersedeHint.jsx` — petunjuk "digantikan oleh" (versi server & versi data lokal).
* Uji: `backend/tests/test_prep_a_master_cleanup.py`, `frontend/src/features/__tests__/prepAMasterCleanup.test.js`.

Diubah (kait kecil):
* `backend/routers/master_governance.py` — 7 endpoint baru (di bawah).
* `backend/services/master_governance_service.py` — `rename_product(..., expect_name=, batch_id=)` (CAS + penanda batch; perilaku lama tetap).
* `backend/routers/products.py` — `GET /products` menyaring SKU tergantikan (param `include_superseded=true` untuk semua).
* `backend/routers/dashboard.py` — produk tergantikan TETAP dikirim, diberi `superseded_by_sku`.
* `frontend/src/components/ProductSelect.jsx`, `features/sales/SalesPortal.jsx`, `features/pos/mobile/MobilePOS.jsx`,
  `features/pos/ReorderStrip.jsx`, `features/catalog/CatalogWorkspace.jsx` — saring/petunjuk/kait panel.
* `scripts/guardrails/verify_atomic_claim.py` — 2 entri `REVIEWED` (apply & rollback, mekanisme `service`).

Endpoint baru (semua `require_permission`):

| Metode & path | Izin | Fungsi |
|---|---|---|
| `GET /api/master-governance/cleanup/sheet?format=xlsx\|csv` | `product.export` | unduh lembar |
| `POST /api/master-governance/cleanup/preview` (multipart `file`) | `product.update` | pratinjau tanpa menulis |
| `POST /api/master-governance/cleanup/apply` `{actions, preview_signature, note}` | `product.update` | terapkan satu batch |
| `GET /api/master-governance/cleanup/batches` · `/batches/{id}` | `product.update` | riwayat · rincian |
| `POST /api/master-governance/cleanup/batches/{id}/rollback` `{reason}` | `product.update` | batalkan batch |
| `GET /api/master-governance/supersede-hint?q=` | `product.view` | petunjuk SKU lama |

## 3. Perilaku untuk user
Tindakan per baris (`tindakan` kosong = PERTAHANKAN; huruf kecil/spasi diterima, mis. "ganti kode"):

| Tindakan | Kolom wajib | Efek saat Terapkan |
|---|---|---|
| GANTI_NAMA | `nama_benar` | `rename_product` → riwayat nama (`name_history` ber-`batch`), SKU tetap |
| GANTI_KODE | `kode_benar` (opsional `nama_benar`) | SKU lama **tidak diubah**: produk baru berkode benar (salinan atribut, induk/`template_id`, kombinasi varian, harga dasar, `harga_pokok`, lifecycle, eksklusivitas, gambar URL; **harga per PT disalin**, **alias supplier dipindah** ke produk baru), produk lama `inactive` + `superseded_by` = produk baru |
| GABUNG_KE | `digantikan_oleh_sku` (SKU aktif, atau `kode_benar` baris GANTI_KODE di lembar yang sama) | produk lama `inactive` + `superseded_by` = induk; alias supplier ikut ke induk |
| NONAKTIFKAN | — | `inactive` tanpa pengganti |

Galat pratinjau (memblokir Terapkan): SKU/ID tidak dikenal atau di luar akses; ID & SKU tidak cocok; tindakan tidak
dikenal; kolom wajib kosong; satu produk dua baris; `kode_benar` tidak sah / sama dengan SKU sekarang / **sudah dipakai**
(tanpa beda huruf besar-kecil, termasuk produk nonaktif) / ganda di lembar; target tidak dikenal, **nonaktif**, sudah
digantikan, atau ikut digantikan di lembar (**rantai**) / menunjuk balik (**siklus**) / menunjuk diri sendiri; satuan
dasar berbeda; induk/artikel tidak aktif (GANTI_KODE); SKU sedang dikunci saga; di luar lini akses; **produk masih dipakai
dokumen TERBUKA** (GANTI_KODE/GABUNG_KE/NONAKTIFKAN — pesan menyebut nomor dokumen, mis. "SO KSC/SO-00013 …(+N lagi)");
GANTI_KODE/GABUNG_KE/NONAKTIFKAN oleh peran selain Admin/MD.
Peringatan (tidak memblokir): stok lama tetap di SKU lama (didaftarkan ulang lewat opname), kontrak supplier aktif masih
menunjuk SKU lama, stage/jenis kain target berbeda, baris no-op (nama sama, sudah nonaktif), kolom perbaikan terisi pada
PERTAHANKAN.

Dokumen terbuka = status belum selesai pada: SO, PO, PR, Order Makloon (bahan/hasil/langkah), cadangan bahan MKO,
transfer gudang, putaway, permintaan internal, transaksi antar-PT, retur beli, retur jual, penerimaan barang, tugas
gudang, SPK inspeksi, sample R&D, RFQ, order perbaikan. Kontrak supplier aktif hanya diperingatkan.

Batalkan: nama dikembalikan (CAS nama sesudah batch, riwayat nama bertambah "Batal batch …"), status & `superseded_by`
dipulihkan, kombinasi varian dikembalikan ke SKU lama, alias supplier kembali, salinan harga PT dihapus; produk hasil
GANTI_KODE **dihapus bila belum dipakai**, **dinonaktifkan bila sudah dipakai** (+ `superseded_by` = SKU lama, kombinasi
variannya disisihkan). Produk "yatim" (proses mati di tengah) dipindai dari penanda `last_cleanup_batch` /
`created_by_cleanup_batch`. Baris yang sudah diubah lagi sesudah batch tidak ditimpa (tercatat `rollback_skipped`).

Pemilih produk dokumen baru: `GET /products` (sumber ±20 pemilih: PR/PO/RFQ/transfer/MKO/`ProductSelect`/permintaan
internal/antar-PT …) menyaring SKU tergantikan; POS/Sales Portal/POS HP/"Sering dibeli" menyaring dari data `/dashboard`.
Mengetik SKU lama → "SKU X digantikan oleh Y" + tombol pilih/cari pengganti.

## 4. Bukti uji (angka apa adanya)
DB uji: arsip `kn_test_trial_2026-11-08` dipulihkan ke kontainer `kn-tmp-a-mongo`; backend `kn-tmp-a-be` (uvicorn tanpa reload).

* **Pytest baru** `tests/test_prep_a_master_cleanup.py`: **10 passed** (dijalankan 2× berturut-turut — data uji
  bertanda `TPA<tag>` bersih). Mencakup fungsi murni (normalisasi/typo/duplikat/baca CSV-XLSX), unduh XLSX+CSV (dan CSV
  terbaca ulang dengan nomor baris benar), pratinjau 10 jenis galat di 12 baris **tanpa menulis** (dokumen DB identik), terapkan
  kelima tindakan (termasuk GABUNG_KE ke kode baru di lembar yang sama), 422 catatan pendek, 409 tanda tangan basi,
  efek `/products` + `include_superseded` + petunjuk + `resolve_active` + `/dashboard`, izin (sales 403 pratinjau &
  batalkan; manager unduh 200, terapkan 403), batalkan (semua pulih, produk baru belum dipakai dihapus, alias & harga
  kembali, batal kedua 409), batalkan saat produk baru sudah dipakai SO (dinonaktifkan + `superseded_by` SKU lama).
* **Jest baru** `prepAMasterCleanup.test.js`: **6 passed**. Suite FE terkait (phase3P3b, phase3P6Rnd, phase4R1,
  phase4R4, uat24F0, uat24F3, uatV3MobileSales + baru): **8 suite / 59 uji passed**.
* **ESLint** 10 berkas FE baru/diubah: **0 error**, 3 peringatan "unused eslint-disable" di baris lama
  (`CatalogWorkspace.jsx:47`, `SalesPortal.jsx:96,139`) — bukan dari perubahan ini.
* **Uji lama terkait** (iter301 rbac, l01 custom role, f1b templates, fe03 access catalog, iter316 catalog, f1a
  pricelist, global stock, iter276 md audit, iter284, f03 variant label) — DB dipulihkan dari arsip sebelum tiap putaran:
  * HEAD `0ed4ea8` (sebelum): 32 failed, 79 passed, 1 skipped, 50 errors;
  * sesudah PREP-A: 32 failed, 79 passed, 1 skipped, 50 errors — **daftar gagal identik** (82 nama uji, `comm` kosong).
    Merah lama: iter276 (50 error fixture), f1b (13), iter284 (10), global_stock (6), f03/iter301/iter316 (1).
* **Guardrail** (hitungan ✗; baris pelanggaran dibandingkan dengan `diff` → identik):

| Guardrail | Sebelum | Sesudah |
|---|---|---|
| custom_modals, error_notice, escape_layers, uom_vocab, knselect_contract, picker_portal, detail_modal, modal_dismiss, page_tabs, role_label | PASS | PASS |
| auth_coverage | 8 | 8 (cek 1614 → 1621) |
| atomic_claim | 6 (BELUM DITINJAU 77) | 6 (BELUM DITINJAU 77; cek 110 → 112, 2 entri REVIEWED baru lolos) |
| to_list_bound | 6 | 6 |
| numeric_bounds | 3 | 3 |
| qty_dual | 5 | 5 |
| ref_unlink | 3 | 3 |
| line_scope (tambahan) | 17 | 17 |

`verify_state_machine.py` tidak dijalankan (sesuai brief); `CODEBASE_MAP.md` tidak diregenerasi.

## 5. Keputusan desain yang saya ambil
1. **Terapkan menuntut 0 galat** (bukan "terapkan yang lolos saja"): lembar diperbaiki & diunggah ulang. Kegagalan yang
   baru muncul saat menulis (CAS kalah, SKU bentrok) dicatat per baris → status `applied_partial`, baris lain jalan.
2. **Tanda tangan pratinjau** = hash rencana + keadaan produk yang terlibat (status, pengganti, `updated_at`, nama),
   nomor dokumen terbuka, keterpakaian `kode_benar`. Stok **tidak** ikut (stok bergerak terus; hanya peringatan).
   Server memvalidasi ulang semuanya saat Terapkan; `actions` dikirim balik dari pratinjau.
3. **Batch terpisah** `master_cleanup_batches` (bukan `master_governance_batches`) agar panel/rollback lama yang
   berbasis field tidak salah membalik batch jenis lain.
4. **Kombinasi varian** (indeks unik `template_id+variant_key`): diserahkan ke produk berkode benar; SKU lama memegang
   `variant_key~digantikan~<id>` (dipulihkan saat batal). Produk baru disalin langsung (bukan `save_product`) agar data
   lama tidak gagal validasi ketat domain — yang diperbaiki hanya kodenya.
5. **Alias supplier dipindah, harga PT disalin**: indeks unik `supplier_id+supplier_sku` melarang salinan; memindah
   membuat pindai label supplier (paket B) langsung menemukan kode benar. GABUNG_KE juga memindah alias (satuan dasar
   wajib sama).
6. **Tidak disalin**: galeri media (berkas fisik dipakai bersama → risiko hapus), lot roll, riwayat nama, tanda unggulan.
   `spec_id/design_id` ikut tersalin sebagai atribut; tautan `md_specs` tetap ke SKU lama.
7. SO **terkirim (shipped/dispatched)** dianggap selesai untuk pemblokiran (sama dengan `alert_ops.SO_CLOSED_STATUSES`).
8. Peran: GANTI_KODE/GABUNG_KE/NONAKTIFKAN & pembatalannya hanya **Admin/MD** (`master_usage_service.LIFECYCLE_ROLES`,
   sama dengan nonaktifkan SKU biasa).
9. `/dashboard` TIDAK menyaring (stok lama/lot/dokumen/master lama masih menampilkan SKU lama); hanya diberi `superseded_by_sku`.

## 6. Belum dikerjakan / butuh keputusan pemilik
1. **Izin unduh**: sesuai brief = `product.export`. Bawaan peran **MD tidak punya `product.export`** (hanya admin &
   manager) → MD bisa pratinjau/terapkan tetapi tidak bisa mengunduh lembar. Perlu keputusan: beri MD `product.export`
   di Manajemen Peran, atau izinkan unduh dengan `product.update`.
2. **Jeda stok**: sesudah GANTI_KODE/GABUNG_KE, stok lama tetap tercatat di SKU lama yang tidak bisa dipilih di dokumen
   baru sampai gedungnya didaftarkan ulang (paket B). Saran urutan kerja: perbaiki master **tepat sebelum** opname per
   gedung — atau pemilik memutuskan SKU lama berstok tetap boleh dijual sampai cutover.
3. Strip POS lain (Terlaris/Unggulan/Rekomendasi) dan endpoint pencarian lain (`/supplier-items/lookup`, pemindai)
   belum disaring; jaring pengaman server: SKU tergantikan berstatus `inactive` → `rnd_gate.assert_orderable` menolak
   (mode `block`, bawaan) saat SO dibuat. Penyaringan tambahan bisa memakai `product_supersede.exclude_superseded`.
4. Paket B (opname awal) sebaiknya memakai `product_supersede.resolve_active()` saat pindai/pilih produk dan
   menolak produk yang `superseded_by`-nya terisi.
5. Katalog (kartu varian) belum menampilkan lencana "Digantikan oleh"; status nonaktif sudah terlihat.
6. Tidak diuji di peramban (tidak ada akses); UI diverifikasi lewat Jest + ESLint.

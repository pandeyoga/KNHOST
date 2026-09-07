# KN — Audit master produk, varian, R&D, dan media

## Permintaan asli pengguna
"saya ingin anda lanjutkan development dari repo ini https://github.com/snakissb/KN
salah satu di sesi sebelumnya ada perbaikan master data product yang seharusnya memiliki varian dengan ui ux seperti etalase product, saya belum cek bagaimana ui uxnya intinya saya ingin seperti management master data seperti di ecomerce yang besar dimana bisa input varian dan beberapa banyak jenis varianya, kritik saya sebelumnya adalah ui uxnya tidak representasi itu dan logic munculnya dari rnd ini sama sekali tidak support design awal product dengan varian ini cek kembali, yang pasti untuk foto itu belum benar harusnya setiap varian bisa menyiman foto dan lebih dari 1 foto, saya perlu ada foto mockup model dari product tersebut contohnya maka sales saya harus bisa menunjukan ke customer. coba telusuri"

## Pilihan pengguna — batas otorisasi
- **AUDIT DAHULU**, sampaikan temuan sebelum mengubah kode. Jangan implementasi sebelum ada persetujuan lanjutan.
- Atribut varian fleksibel: warna × ukuran × material, beberapa foto per kombinasi.
- Foto diunggah manual serta dibuat dengan AI.
- Provider/model AI dan penggunaan kredensial belum dipilih untuk pekerjaan baru; tidak diminta selama audit.

## Persona
- Admin/MD: mengelola induk produk, atribut, kombinasi, dan media.
- R&D/desainer: merancang, menilai sampel, menyetujui spesifikasi serta menyiapkan visual.
- Sales: memilih varian yang tepat dan menunjukkan foto serta mockup kepada pelanggan.
- Pelanggan: melihat visual varian yang benar tanpa informasi internal.

## Kebutuhan inti (statis)
1. Master produk dengan pengalaman pengelolaan katalog/etalase, bukan sekadar daftar SKU.
2. Satu induk dengan kombinasi atribut fleksibel; satu kombinasi tetap satu SKU/product_id.
3. Alur R&D konsisten dengan induk, varian, persetujuan dan rilis produk.
4. Banyak foto per kombinasi, bukan satu URL; mendukung foto asli dan mockup model.
5. Sales dapat melihat galeri varian terpilih di desktop dan mobile.
6. Akses eksklusivitas/lini dan informasi biaya tetap terlindungi.

## Arsitektur yang ditemukan / keputusan audit
- Repo sumber: `https://github.com/snakissb/KN`, branch `main`, snapshot `0bfdf1aec6b82578527a855f85fc52d181eb3af5`.
- Salinan untuk audit: `/tmp/kn-audit`; **belum diimpor ke aplikasi `/app`**.
- Aplikasi `/app/frontend` dan `/app/backend` masih template awal, bukan KN. Jangan menganggap preview saat ini sebagai KN.
- KN memakai React, FastAPI, MongoDB. `product_templates` adalah induk katalog SHARED; `products` adalah SKU yang dirujuk stok/roll/RFID/SO/PO.
- R&D memakai `md_specs`, `md_samples`, dan `design_gallery`. Galeri desain sudah mempunyai banyak berkas, referensi opsional product_id, dan ilustrasi Gemini.
- Storage yang ditemukan adalah wrapper disk lokal, keputusan lama pemilik menurut komentar kode; jangan menggantinya diam-diam.
- Usulan mempertahankan ID SKU dan referensi transaksi, bukan membangun ulang stok. Ini rekomendasi audit, belum implementasi.
- Tidak ada perubahan kode aplikasi, konfigurasi, database, atau panggilan provider AI dalam sesi ini.

## Yang diselesaikan — 2026-09-06
- Membaca alur R&D → products, induk/varian, pengelolaan master, katalog desktop/mobile, galeri desain dan integrasi AI yang sudah ada.
- Verifikasi independen oleh testing agent: audit statis + fungsi terisolasi; **bukan tes aplikasi berjalan/end-to-end**.
- Tiga reproduksi logika: axis `values[]` dibuang oleh pembaca `options[]`; metadata `hex` hilang; resolver warna+grade ambigu untuk kombinasi lebar/material berbeda.
- Laporan: `/app/memory/AUDIT_PRODUCT_VARIANTS.md`, `/app/test_reports/iteration_1.json`, hasil probe `/app/test_reports/isolated_*_result.json`.
- Temuan belum diperbaiki, sesuai permintaan audit dahulu. Tidak ada fitur baru yang diklaim selesai.

## Yang diselesaikan — 2026-09-06 (sesi 2, sudah lolos iteration_5 & iteration_6)
- Sumbu varian terkonfigurasi Warna×Grade×Asal + picker Kain dasar (lihat `CONTINUATION_2026-09-06_B.md`).
- Form produk anti-typo: kategori/motif/satuan/pemasok KNSelect dari master, input numerik, SKU prefix uppercase; kategori induk WAJIB (`FamilyForm.jsx`).

## Yang diselesaikan — 2026-09-06 (sesi 3 — penutupan, tanpa fitur baru)
- Repo `pandeyoga/KNHOST` diimpor ke `/app`, `.restore_env.sh` dijalankan, fondasi LENGKAP.
- Perbaikan lingkungan: `package.json` `start` → `node static_server.js`; KeyError kosmetik di akhir `seed_realistic.py` dihapus (sebelumnya menghalangi penanaman ulang akun md@).
- Regresi: smoke API ALL PASS; testing agent `iteration_7.json` semua lolos (login 4 akun, product-motifs, meta sumbu, FamilyForm, SpecFormModal, edit induk lama, katalog sales).
- Keputusan pengguna untuk pekerjaan media nanti: disk lokal (bukan object storage); mockup AI ditunda, unggah manual dahulu.

## Yang diselesaikan — 2026-09-06 (sesi 3b — paket deploy VPS)
- `deploy/` (docker-compose `kn-*`, Dockerfile backend/frontend tanpa pustaka Emergent, Caddyfile, nginx-web.conf, `install_vps.sh` sekali jalan, `edge.sh` anti-bentrok 80/443, `update.sh`, `backup.sh`, `frontend.yarn.lock`), `.dockerignore`, `docs/DEPLOY_VPS.md`. Domain kainnusantara.cloud · VPS 187.77.116.148 · ACME pk.yogaswastika@gmail.com. Belum dijalankan di VPS (sesuai permintaan).

## Prioritas backlog — menunggu persetujuan
### P0
- Samakan pembatasan visibilitas/HPP jalur template dengan jalur products; validasi peran dan cakupan stok.
- Satukan kontrak kelahiran SKU R&D/generator/master: induk valid, kombinasi eksplisit, lifecycle eksplisit; cegah varian yatim dan ambigu.
- Pastikan pemilihan varian sales mencocokkan seluruh atribut, tanpa fallback diam-diam ke SKU berbeda.
### P1
- Pengelolaan produk berbasis induk dengan atribut bebas, matriks kombinasi dan pengeditan varian.
- Model media per SKU: banyak foto, cover, urutan, tipe foto/mockup dan status publikasi.
- Hubungkan artwork/sampel R&D yang disetujui ke media varian; galeri sales desktop/mobile.
- Sambungkan mockup AI yang ada ke varian dengan persetujuan manusia sebelum ditampilkan ke customer.
- Perbaiki kontrak options[]/hex dan uji regresi lintas alur.
### P2
- Penyuntingan massal, pencarian/paginasi katalog besar, filter kelengkapan media.
- Mode presentasi pelanggan tanpa HPP/catatan internal.

## Langkah berikutnya
1. ~~P1 media per varian~~ — **SELESAI** (product_media router/service, VariantMedia.jsx, ProductGallery, MobileQuickView; diverifikasi 2026-09-07).
2. ~~P0 kontrak kelahiran SKU + pencocokan varian sales~~ — **SELESAI** (catalog_rules, product_variant_service, rnd_catalog_validation, VariantAxisPicker; smoke_variant_axes_base_fabric ALL PASS 2026-09-07).
3. Provider AI mockup ditentukan hanya saat pengguna menyetujui; untuk sekarang unggah manual.
4. Setiap perubahan `frontend/src` → `bash scripts/rebuild_frontend.sh` (tanpa hot reload).

## 2026-09-07 — Impor repo KNHOST + verifikasi laporan audit "PERKEMBANGAN_KNHOST_2026-09-07"
Repo `pandeyoga/KNHOST` diimpor ke /app, `.restore_env.sh` dijalankan (pip, yarn, seed_realistic, bootstrap), fondasi terverifikasi (75 GL, 8 UoM, 8 kategori, akun md@).

Hasil verifikasi temuan (semua "PERINTAH CEK" dijalankan di kode aktual):
| Temuan | Verdict | Tindakan |
|---|---|---|
| 1.1 Jalur tulis `products` tunggal | TERBUKTI (1 insert_one di product_template_service; `audit_jalur_paralel.py` tidak ada) | — |
| 1.2 Fallback `variants[0]` | TERBUKTI GUGUR (0 hit) | — |
| 3.1 `memory/` menyusut 74→9 (INVARIANTS/GUARDRAILS/BUG_REGISTRY hilang; `validate_compliance` merah) | TERBUKTI | 66 berkas dipulihkan dari `snakissb/KN` (cp -n, tidak menimpa PRD/handoff KNHOST) |
| 3.2 Riwayat git terpangkas (3 commit) | TERBUKTI | tidak bisa diperbaiki dari sini (butuh push ulang dari repo asal) |
| INV-PERF-01 `find({}).to_list(100000)` di generate_variants | TERBUKTI (gate merah) | query `$in` pada SKU kandidat |
| INV-ATOMIC-01 `delete_template` | TERBUKTI **salah tuduh** — kode memakai `family_lock` (klaim+release); guard tidak mengenalinya | guard `verify_atomic_claim.py` mengenali `family_lock(` (bukan allowlist) |
| INV-UI-01/10 lightbox ProductGallery | TERBUKTI (gate merah) | pakai `useEscapeClose` + `overlayDismiss` |
| 3.4 ProductTemplatesView/Parts + `resolveVariant` mati | TERBUKTI | dihapus (+ colorKeyOf/deriveAxisOptions/gradesForColor yang juga mati) |
| R-3a detail sampel tanpa isolasi entitas | TERBUKTI | `assert_active_entity_access` pada GET detail |
| R-4 `move_rolls_by_qty` tanpa CAS | TERBUKTI | filter CAS status+length_remaining; konflik → lewati roll, jika kurang → kompensasi via `move_rolls_by_ref` + 409 |
| R-7 gerbang rnd_gate tidak seragam | SEBAGIAN: blanket_po & rfq award TERBUKTI; pr_sourcing GUGUR (sudah divalidasi saat PR dibuat) | `assert_orderable` di `create_blanket` dan `_create_po_from_lines` |
| §4.2 build FE mati diam-diam | TERBUKTI (2× build terhenti) | `rebuild_frontend.sh` heap 1536→4096 MB; build sukses 50 dtk |

Regresi: gate `--quick` 4 guard yang merah kini hijau; `smoke_variant_axes_base_fabric` ALL PASS; `smoke_audit_2026_09_07.py` (baru) ALL PASS; `test_f2_stock_buckets` 20 passed; `test_iter316/317` 22 passed; testing agent iteration_8 semua PASS (BE + UI lightbox + navigasi).

Backlog tersisa dari laporan: `validate_compliance` masih perlu dijalankan penuh setelah pemulihan memory/ (uji: `bash scripts/gate.sh`), dan riwayat git perlu dipulihkan dari repo asal `snakissb/KN`.

## 2026-09-07 (sesi 2) — §7 Sembilan keluhan klien: verifikasi + implementasi
Verifikasi "PERINTAH CEK" §7: K-1..K-8 memang **belum** (TERBUKTI), K-9 SELESAI. Dikerjakan (urutan saran auditor):
| # | Keluhan | Implementasi |
|---|---|---|
| K-1 | EYD otomatis | `services/text_normalize.py` (`nama_orang`, `nama_usaha`) dipakai di create/update pelanggan, pemasok, alamat; FE `utils/text.js` + onBlur di CustomerFormModal. Hanya dokumen/suntingan baru. |
| K-2 | Validasi nomor WA | `PhoneStr` (Pydantic BeforeValidator) di semua kolom telepon schemas (customer, alamat, kontak, entitas, user, supplier, makloon); normal ke `62xxxxxxxxxx`; PATCH → 400 dengan pesan menuntun. |
| K-3 | Alamat di checkout | Dropdown + `checkout-address-detail` (langkah 1) dan `checkout-review-address` (langkah 3) tampil alamat lengkap + penerima + telepon. |
| K-4 | Termin CBD / Tempo 2 & 3 bulan | `DEFAULT_PAYMENT_TERMS` + CBD, NET60, NET90; backfill idempoten untuk DB lama saat boot. |
| K-5 | Group sales maks 2 + 50-50 | `apply_group_sales_rule` (BE, dipakai customer & SO) + `SalesTeamEditor` (tombol tambah hilang di 2 orang, split rata otomatis, tetap bisa diubah). |
| K-6 | Harga satuan di ringkasan | `checkout-review-line-{id}`: qty × harga efektif (harga khusus pelanggan dihormati) + subtotal baris. |
| K-7 | Dye lot & umur roll | RollPicker: badge `roll-dye-lot-{id}` & `roll-age-{id}` (>180 hari disorot). |
| U-4 | Label retur seragam | 18 varian → "Retur Penjualan" / "Retur Pembelian" (+ varian "(Nota Debit)", "(dari pelanggan)", "(ke pemasok)"); nav map PASS. |
| K-8 | 3 badan usaha | **MENUNGGU PEMILIK** — butuh nama legal, NPWP, gudang awal (Kanda Fabric, Sukacita Textile, Cipta Sandang Textile). Tidak dikerjakan. |
| U-1/U-2 | Notifikasi "giliran Anda" & meja kerja 6 peran | Belum disentuh (fitur besar; di luar urutan saran auditor). |

Bukti: `smoke_feedback_klien_2026_09.py` ALL PASS, testing agent iteration_9 semua PASS (BE + UI checkout langkah 1–3, tim sales, termin), guard FE hijau, nav map PASS, validate_compliance 0 FAIL. Catatan: `test_f0b_entity_scoping::test_cash_kas_besar_visible_in_all_contexts` gagal sebelum & sesudah (data seed) — bukan regresi.

## 2026-09-07 (sesi 3) — K-8 entitas · Giliran Anda · Kebersihan Data
Keputusan pemilik: Kanda Fabric & Sukacita Textile = PENGGANTI nama entitas lama; CV Cipta Sandang Textile = BARU (PKP), detail lain diedit di sistem. Notifikasi giliran: SO+PO+Retur+Sampel, dalam aplikasi saja. Normalisasi data lama: otomatis saat boot + layar Kebersihan Data dengan riwayat & kembalikan per-record.
| Fitur | Implementasi |
|---|---|
| K-8 | `bootstrap.apply_entity_rebrand_2026_09` (sekali jalan, flag `migrations`): ent_ksc→"Sukacita Textile", ent_kanda→"Kanda Fabric" (id & doc_prefix dipertahankan); CV Cipta Sandang Textile dibuat via `entity_provisioning_service.provision_entity` (CoA/penomoran/PKP; prefix CST; NPWP placeholder 00.000.000.0-000.000 — pemilik melengkapi di Badan Usaha & Akses). Pemasok entitas grup ikut berganti nama via sync E-7. |
| Giliran Anda | `services/turn_notification_service.py`: TURN_MAP (koleksi×status → peran/owner, judul, tautan); hook fire-and-forget di `dependencies.audit()`; job scheduler `turn_scan` tiap 5 menit (jaring pengaman untuk transisi tanpa audit; dokumen >7 hari ditandai diam-diam); `turn_marks` mencegah pengiriman ganda; tahap sebelumnya ditutup via `resolve_action("turn", ...)`. FE: label tipe "Giliran Anda" di lonceng. `GET /api/turn-notifications/map`. |
| Kebersihan Data | `services/data_hygiene_service.py` (RULES customers/suppliers/users/employees/makloons; run/revert/unlock/summary/preview), dijalankan saat boot (`run_bootstrap`, setelah sync pemasok grup) + `routers/data_hygiene.py`; FE tab "Kebersihan Data" di Pusat Pengaturan (`DataHygienePanel.jsx`): headline, filter koleksi, rincian sebelum→sesudah per baris alamat/kontak, Pratinjau, Rapikan sekarang (admin), Kembalikan per-record (kunci), Buka kunci. Satu pintu penulisan baru juga untuk users & karyawan HR. |

Bukti: `smoke_turn_hygiene_entities.py` ALL PASS; testing agent iteration_10 semua PASS (BE+UI); guard to_list/atomic hijau; validate_compliance 0 FAIL.
Backlog: U-2 meja kerja 6 peran; NPWP/alamat/gudang CV Cipta Sandang Textile menunggu pemilik; kanal WhatsApp untuk giliran (bila diinginkan nanti).

## 2026-09-07 (sesi 4) — Lokasi tervalidasi ala e-commerce (semua data beralamat)
Sumber data: Kepmendagri 300.2.2-2138/2025 (cahyadsn/wilayah + wilayah_kodepos, MIT) → `backend/data/wilayah_id.json` (38 provinsi · 514 kab/kota · 7.265 kecamatan · 83.345 kelurahan berkode pos, 5,6 MB, dimuat lazy).
- Backend `services/wilayah_service.py`: `normalize_location()` — negara → provinsi → kota/kab → kecamatan → kode pos wajib konsisten; kode pos harus milik kecamatan/kota terpilih; kode pos saja → isi otomatis. Mode STRICT (payload bawa province/postal_code/kode → 400 menuntun) vs LENIENT (klien lama hanya `city` → alias Solo→Kota Surakarta dst., `location_status` verified/partial/unverified/foreign; tidak menolak data lama). Dipasang di customers (create/PATCH/alamat), suppliers, makloons, entity provisioning. `routers/wilayah.py`: /api/wilayah/{countries,provinces,regencies,districts,villages,postal-code/{code},search,validate}.
- Frontend `components/LocationFields.jsx` (dropdown bertingkat searchable + "isi cepat dari kode pos" + mode luar negeri) dipakai di CustomerFormModal, CustomerPanel & CreateCustomerModal (POS), SuppliersView, MakloonFormModal, EntityWizard (tidak wajib). Validasi sisi klien `locationIncomplete()` sebelum simpan.
- Schema: `CustomerCreate.city` kini opsional (boleh diisi dari kode); field lokasi baru opsional (kompatibel klien lama).
Bukti: `smoke_wilayah.py` ALL PASS; testing agent iteration_11 semua PASS (BE+UI). Data lama tidak diubah — hanya ditandai `location_status` saat disentuh berikutnya.
Backlog lokasi: ~~backfill/daftar alamat belum terverifikasi~~ dan ~~gudang & karyawan~~ — SELESAI sesi 5 (lihat bawah).

## 2026-09-07 (sesi 5) — Lokasi gudang/karyawan + backlog "Alamat belum terverifikasi"
- LocationFields dipasang di form Gudang baru (`wh-form-loc-*`), Lokasi/site gudang (`wh-site-loc-*`), Karyawan HR (`employee-loc-*`, tidak wajib). Backend: `WarehousePayload`/`SitePayload`/`EmployeeCreate` + field lokasi; create & PATCH memakai `normalize_location` dengan merge lokasi tersimpan (PATCH kode pos saja tetap dicek terhadap kota yang sudah ada). Koleksi karyawan = `hr_employees` (RULES hygiene diperbaiki).
- `data_hygiene_service.unverified_locations()` (customers/suppliers/makloons/warehouses/warehouse_sites/business_entities/hr_employees; data lama tanpa `location_status` dinilai lenient tanpa menulis) + `fix_location()` (wajib lengkap; alamat utama pelanggan ikut dilengkapi bila belum berkode pos; dicatat di `data_hygiene_log` trigger `location_fix`). Endpoint: GET `/api/data-hygiene/unverified-locations`, POST `/api/data-hygiene/location/{collection}/{doc_id}`.
- FE `LocationBacklogPanel.jsx` di tab Kebersihan Data: filter jenis data, tabel, tombol Lengkapi → LocationFields inline → Simpan.
Bukti: `smoke_wilayah.py` ALL PASS + ALL PASS (sesi 5); testing agent iteration_12 semua PASS (1 temuan alamat utama seed berstatus 'verified' tanpa kode pos → diperbaiki: status tersimpan hanya dipercaya bila kode pos ada).

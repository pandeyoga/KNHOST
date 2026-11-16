# MP-T1 — Rute Produk: satu tempat untuk "barang ini dibeli atau dibuat lewat jalan apa"

- Commit awal: `3865293` (spesifikasi `a98754f`)        - Commit akhir: `1959504`       - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: telusur 16 Nov P2, P9, sebagian P10 (fitur; spesifikasi `docs/blueprint/unit/MP-T1.md`; keputusan K-57, K-65,
  K-70, K-71, K-73)
- Risiko tinggi. Serah-terima (a) jalur baru dan (b) pengalihan pemanggil dikerjakan dalam satu putaran karena pemanggil
  lama tetap berjalan sama persis bila artikel belum punya rute (lihat "Menyimpang dari blueprint").
- **H3 dipatuhi**: skrip rute awal hanya dijalankan di database tiruan (U12); belum pernah di data acuan maupun data nyata.

## Cek ulang "Keadaan sekarang" (spesifikasi `a98754f`, diperiksa di `3865293`)

| Butir spesifikasi | Hasil |
|---|---|
| `restock_source_service.py:13` `MODES`, `:24` `applies`, `:43` `check_lines`, `:89` `auto_route` | Berlaku (baris sama) |
| `schemas_makloon.py:46` `ProcessRecipeCreate` | Berlaku |
| `production_service.py:4` `mfg_boms` | Berlaku |
| `domain_registry.py:395` `PROCESS_STAGES`; `master_registry.py:173` `active_stages`, `:183` `stage_meta` | Berlaku |
| `rnd_sample_service.py:1295` kontrak `purchase`; `_bind_product` `:1187`; `rnd_spec_service.py:460` `release_product` | Berlaku; dibuktikan jalan 16 Nov (AUD-RND-5266D) |
| `entity_scope.py:56-57` (artikel/produk bersama), `:174-179` (mitra/kontrak/resep/BOM per PT) | Berlaku |

## Perubahan

- **Data**: koleksi `product_routes` (per PT) — artikel, varian pengecualian, nama, utama, status, asal, langkah. Indeks
  `(entity_id, template_id, product_id, status)`, `(entity_id, origin)`, `id` unik (daftar id).
- **Aturan** satu fungsi `product_route_service.validate` (R1–R9): tahap asal/hasil langkah makloon dari Master Tahapan
  Proses (klien tidak bisa mengisinya), rantai bersambung, berakhir di tahap artikel/varian, bahan/hasil bertahap sesuai,
  mitra mengerjakan prosesnya, kontrak aktif milik mitra & jenisnya cocok, beli hanya langkah pertama, produksi sendiri
  wajib BOM aktif. R10: rute pertama otomatis utama; menandai utama melepas rute utama lain.
- **Server**: 7 endpoint (`routers/product_routes.py`); tulis menolak mode "Semua PT" ("Pilih satu PT untuk tindakan ini.").
  `step-options` juga mengirim pemasok, kontrak pembelian/makloon aktif, dan BOM aktif PT itu (tanpa nominal tarif) supaya
  pengelola rute tidak butuh izin modul pembelian/produksi hanya untuk memilih.
- **R&D**: `_bind_product` membuat rute "Beli dari <pemasok>" (`origin=rnd`, kontrak hasil putusan) bila artikel belum
  punya rute di PT itu; `release_product` menolak bila `rnd.release_requires_route` menyala dan varian tanpa rute utama.
- **(b) Pengalihan**: `check_lines` membaca rute utama lebih dulu untuk semua tahap (bukan hanya barang jadi): sama dengan
  rute utama → lolos; jalur rute aktif lain → wajib alasan; menyimpang dari rute → wajib alasan + peringatan tercatat
  (sama dengan jalur lama). `auto_route` (PR dari SO) mengikuti rute. Artikel tanpa rute → jalur `restock_source` lama
  tanpa perubahan. Panel "Sumber restock artikel" berlabel "dipakai bila artikel belum punya rute"; tanggal mati = sesudah
  skrip rute awal dijalankan di data nyata.
- **Pengaturan** `rnd.release_requires_route` (bool, bawaan menyala — K-70), kelompok R&D › "Boleh dijual", izin `rnd.manage`.
- **Izin** `product_route.update` "Rute Produk" (modul Produk) — Admin, MD, Manajer (K-73).
- **Layar** tab **Rute** di rincian induk Master Produk (`FamilyRoutesTab.jsx`): kartu rute berantai tahap
  ("Greige → PFP — Pre-treatment … @ PT Bleaching Pratama → PFP → Printing @ PT Rotary Print Indah → Jadi"), lencana Utama /
  Khusus varian / asal; pop-up baku `FormModal` "Buat rute"/"Ubah rute" dengan pilihan tersaring; "Usulkan dari data lama";
  "Jadikan utama"; "Nonaktifkan" (konfirmasi).
- **Skrip** `backend/scripts/mpt1_rute_awal.py` (dry-run bawaan, `--apply`, `--undo --apply`, pagar DB produksi
  `data_fix_guard`).

## Berkas

| Berkas | Isi |
|---|---|
| `backend/services/product_route_service.py`, `backend/routers/product_routes.py` (baru), `backend/server.py` | layanan + router |
| `backend/services/restock_source_service.py`, `backend/services/restock_service.py` | (b) cek jalur membaca rute |
| `backend/services/rnd_sample_service.py`, `backend/services/rnd_spec_service.py` | rute lahir saat putus; gerbang rilis |
| `backend/config_catalog_rnd.py`, `backend/permissions_config.py`, `backend/access_modules.py` | pengaturan, izin, modul |
| `backend/entity_scope.py`, `backend/indexes.py`, `scripts/verify_contract.py` | koleksi per PT, indeks, kontrak koleksi |
| `backend/scripts/mpt1_rute_awal.py` (baru) | rute awal dari data lama (H3) |
| `frontend/src/features/catalog/FamilyRoutesTab.jsx` (baru), `CatalogWorkspace.jsx`, `catalogApi.js` | tab Rute |
| Dibangkitkan | `CODEBASE_MAP.md`, `frontend/src/features/settings/config/configKeyIndex.json`, `frontend/src/config/__tests__/fixtures/access_builtin_fixture.json` |
| Uji | `backend/tests_mem/test_MPT1_rute_produk.py` (14, baru); disesuaikan `test_KFT1_izin_pengaturan.py`, `test_PRT9_izin_bawaan.py`, `backend/tests/test_iter316_catalog_rnd_security.py` |
| Dokumen | `ENTITY_REGISTRY.md`, `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.35, unit `MP-T1.md` (baris U14) |

## Uji penerimaan

Merah sebelum kode (dijalankan pada pohon dengan uji baru, tanpa kode): U1–U8, U12, U14 404/"Sumber daya izin
“product_route” tidak dikenal"; U9 rilis lolos tanpa rute (200); U10 tidak ada rute; U11 `RestockRouteError … default
artikel … adalah pembelian supplier — tulis alasan`.

| ID | Lapis | Hasil |
|---|---|---|
| U1 | B | lulus — 2 langkah `grey→pfp` (pre_treatment), `pfp→finished` (printing); utama |
| U2 | B | lulus — 400 "Langkah 1: bahan masuk harus bertahap PFP; … bertahap Greige." |
| U3 | B | lulus — 400 "Rute berakhir di PFP, padahal artikel ini Jadi." |
| U4 / U4b | B | lulus — 400 "… tidak mengerjakan Printing"; 400 "Langkah 2 (Printing) butuh bahan PFP, sedangkan langkah 1 menghasilkan PFD." |
| U5 | B | lulus — 400 "Langkah 2: beli dari pemasok hanya boleh di langkah pertama." |
| U6 | B | lulus — satu utama; daftar `primary_id` = rute baru, `status` "diatur" |
| U7 | B | lulus — V1 → rute khusus, V2 → rute artikel |
| U8 | B | lulus — Tanpa Acuan (`product.view` + `product_route.update`) 200; Manajer Kosong 403 |
| U9 | B | lulus — tanpa rute 400 "belum punya rute utama"; pengaturan mati → 200 |
| U10 | B (fixture `_bind_product`) | lulus — rute `origin=rnd`, utama, langkah beli @ pemasok + kontrak |
| U11 | B | lulus — `restock_source=supplier`, rute utama makloon → SPK makloon tanpa galat/peringatan, `source=rute` |
| U12 | B | lulus — dry-run 1 rute tanpa menulis; apply 1 rute `pfp`→`printing`; jalan ulang tidak menggandakan |
| U13 | layar (uji jalan, A) | lulus — lihat Cek layar |
| U14 | B | lulus — dari Greige hanya `pfp`/`pfd`; mitra `pfp` hanya mitra pre-treatment |
| Lapis A | MongoDB asli | telusur R&D labdip (`AUD-RND-81C97`): putus → rute "Beli dari Cirebon Craft" (KSC/SCT-00015) utama → rilis 200; `test_iter316…::test_rnd_target_product_id_rejects_released_sku` lulus |

Angka uji (uji hemat, terarah): `test_MPT1_rute_produk.py` 14 lulus; registri izin/pengaturan (KFT1, KFT8, PRT2, PRT3,
PRT5, PRT8, PRT8b, PRT9) 598 lulus + 2 xfail sesudah 3 penyesuaian; jest `serverAccessReach`, `mnt1MenuKeuangan`,
`kpt9HubPengaturan` 101 lulus. Suite penuh tidak dijalankan ulang (kebijakan uji hemat; sekali di akhir gelombang MP).

## Uji lama yang disesuaikan (perilaku yang sengaja diubah unit ini)

- `test_KFT1_izin_pengaturan.py` U04 (+1 kunci katalog) dan U10 (MD 32 → 33 kunci R&D): `MPT1_KUNCI = 1`.
- `test_PRT9_izin_bawaan.py`: `TAMBAHAN_SESUDAH` admin/md/manager `product_route.update`.
- `tests/test_iter316_catalog_rnd_security.py` (lapis A, di luar gate): membuat rute sebelum rilis (K-70). Uji ini **sudah
  merah sebelum MP-T1** karena alasan rilis "oke" < 5 huruf (422); alasannya diganti "oke rilis".

## Cek layar

Uji jalan Playwright sebagai MD (`bukti/MP-T1/uji_jalan_rute.js`), induk "Kain Audit labdip 5266D":
- Pilihan tahap langkah 1: semua tahap makloon (Celup, PFD, PFP, Printing, Rajut, Tenun) dengan asal → hasil; sesudah
  memilih PFP, langkah 2 hanya "Printing (PFP → Jadi)". Mitra langkah PFP hanya 4 mitra pre-treatment; langkah printing
  hanya 4 mitra printing.
- Simpan → kartu "Printing di Rotary (uji jalan)" berlencana Utama, rantai tahap lengkap (`bukti/MP-T1/1280-03-tersimpan.png`).
- Rute salah (hanya PFP) → pesan server di dalam pop-up "Rute berakhir di PFP, padahal artikel ini Jadi." (`1280-04-galat.png`).
- 390 px: pop-up layar penuh satu kolom, tanpa gulir mendatar (`scrollWidth` 390) (`390-01-daftar.png`, `390-02-form.png`).
- Galat API selama uji: hanya 400 yang disengaja (rute salah).

## Menyimpang dari blueprint

- (a) dan (b) satu commit: pengalihan `check_lines`/`auto_route` hanya berlaku bila artikel punya rute di PT itu; tanpa rute
  jalurnya identik dengan kode lama, sehingga tidak ada keadaan antara yang perlu diserahkan terpisah.
- `step-options` juga mengembalikan daftar pemasok/kontrak/BOM (spesifikasi hanya menyebut tahap + mitra) — agar MD
  bisa mengisi rute tanpa izin modul Pembelian/Produksi. Kontrak dibatasi jenis pembelian & makloon (penjaga isolasi PT
  sempat menandai kontrak antar-PT yang mitranya PT lain).
- `scripts/INDEX.md` tidak diubah: berkas itu memuat skrip gate, bukan skrip data.

## Asumsi

- ASUMSI: rute per PT; artikel dipakai bersama semua PT (mitra/kontrak/resep/BOM per PT).
- ASUMSI: langkah "beli" tidak punya tahap asal; hasilnya = tahap barang yang dibeli (atau tahap artikel bila rute satu langkah).
- ASUMSI: tahap bertipe `sampling` (proofing) dan `inspection` bukan langkah rute produksi.
- ASUMSI: putusan R&D yang membuat rute tidak menimpa rute yang sudah ada di PT itu.

## Titik henti

- H3: `backend/scripts/mpt1_rute_awal.py --apply` di data nyata menunggu pemilik (cadangan → dry-run → tinjau → apply).

## Gate

Gate penuh belum dijalankan untuk unit ini (kebijakan `03_LINGKUNGAN_UJI.md` §6: sekali per gelombang — dijalankan di
akhir gelombang MP). Penjaga terkait yang dijalankan:
- `verify_config_text` — 3528 cek, 0 pelanggaran.
- `audit_entity_isolation` — 1 kebocoran baru di `/api/product-routes/step-options` ditemukan lalu ditutup; tersisa 2
  kebocoran garis dasar (`/api/dashboard`, `/api/products`) dan 3 koleksi tak terdaftar + 1 router garis dasar (bukan dari unit ini).
- `audit_i18n_id` (102 temuan garis dasar) dan `audit_create_modal` (2 temuan garis dasar) — tidak ada temuan di berkas unit ini.

## Yang perlu direview

- Bentuk rute (langkah `purchase`/`makloon`/`inhouse`, tahap dari master) dipakai MP-T2…MP-T4.
- Gerbang rilis R&D kini menolak spesifikasi tanpa rute (K-70) — pemakai yang merilis lewat layar R&D akan diminta
  mengisi rute dulu; pesan galat mengarah ke Master Produk › Rute.

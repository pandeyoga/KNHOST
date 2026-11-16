# MP-T1 — Rute Produk: satu tempat untuk "barang ini dibeli atau dibuat lewat jalan apa"

| | |
|---|---|
| Gelombang | Modul master produk & makloon |
| Jenis | fitur |
| Risiko | tinggi (dua serah-terima, `00` §8) |
| Prasyarat | — |
| Menutup temuan | Telusur 16 Nov P2, P9 (sebagian P10: penegakan tahap di rute) |
| Keputusan | K-57, K-65, K-70, K-71, K-73 |
| Standar | `02` §2 (pengaturan), §3 (izin), §4 (layar), §5 D1/D8/D9, §6 |
| Lingkungan uji | B (database tiruan) untuk aturan; A (MongoDB asli) + peramban untuk layar |

## Tujuan

Setiap artikel punya **rute**: urutan langkah dari bahan sampai barang (beli dari pemasok, makloon per tahap, atau
produksi sendiri), dengan mitra, kontrak, dan resep bawaan per langkah. Tahap bahan di tiap langkah dibaca dari Master
Tahapan Proses sehingga rute yang melompat tahap (mis. greige langsung printing) ditolak. Produk hasil R&D tidak bisa
dirilis tanpa rute utama.

## Keadaan sekarang

- Master produk tidak menyimpan dari apa dan lewat jalan apa barang dibuat. Satu-satunya penanda adalah
  `product_templates.restock_source.mode` (`supplier` · `makloon` · `both`), hanya untuk tahap jadi:
  `backend/services/restock_source_service.py:13` (`MODES`), `:24` (`applies`), `:43` (`check_lines`), `:89`
  (`auto_route`). [dibaca]
- Resep proses satu langkah (`process_recipes`: `input_product_id`, `output_product_id`, `process_type`,
  `default_makloon_id`, tarif, susut) — `backend/schemas_makloon.py:46` (`ProcessRecipeCreate`). Tidak berantai dan hanya
  dipakai modal makloon. [dibaca]
- BOM produksi in-house terpisah: `mfg_boms` — `backend/services/production_service.py:4`. [dibaca]
- Master Tahapan Proses (`process_stages`, benih `backend/domain_registry.py:395` `PROCESS_STAGES`) sudah menyimpan
  `from_stage` → `to_stage` per tahap; dibaca lewat `backend/services/master_registry.py:173` (`active_stages`), `:183`
  (`stage_meta`). [dibaca]
- R&D: saat pemenang diputus, kontrak pembelian dibuat (`backend/services/rnd_sample_service.py:1295`) dan sumber
  restock artikel diisi "supplier" (`_bind_product`, `:1187`). Tidak ada rute. Rilis ke produksi
  (`backend/services/rnd_spec_service.py:460` `release_product`) tidak memeriksa jalur pengadaan. [dijalankan 16 Nov:
  produk AUD-RND-5266D lahir, dirilis, SPK makloon diberi peringatan "menyimpang dari default pembelian supplier"]
- Templat dan produk dipakai bersama semua PT (`backend/entity_scope.py:56-57`); mitra, kontrak, resep, BOM per PT
  (`:174-179`).

## Perubahan

### Data

Koleksi baru `product_routes` (per PT, `entity_id`):

| Field | Tipe | Wajib | Arti |
|---|---|---|---|
| `id` | str `rte_…` | ya | |
| `entity_id` | str | ya | PT pemilik rute (mitra & kontrak per PT) |
| `template_id` | str | ya | Artikel |
| `product_id` | str | tidak | Kosong = semua varian; diisi = pengecualian untuk varian itu |
| `name` | str ≤ 80 | ya | Nama rute ("Printing di Rotary") |
| `is_primary` | bool | ya | Satu rute utama per (PT, artikel, varian) |
| `status` | `active` · `inactive` | ya | |
| `origin` | `manual` · `rute_awal` · `rnd` | ya | Asal rute |
| `origin_ref` | obj | tidak | `{kind, id, number}` (resep/BOM/sample asal) |
| `steps[]` | list | ya, ≥ 1 | Lihat di bawah |
| `created_*`, `updated_*`, `history[]` (30 terakhir) | | | |

Langkah (`steps[]`): `seq` · `kind` (`purchase` beli dari pemasok · `makloon` · `inhouse` produksi sendiri) ·
`stage_code` (makloon: kode Master Tahapan Proses) · `process_type`, `from_stage`, `to_stage` (**diisi server dari
master**, masukan klien diabaikan) · `input_product_id` · `output_product_id` · `partner_kind` (`supplier` · `makloon` ·
kosong) · `partner_id` (boleh kosong: mitra bawaan menyusul, K-61) · `contract_id` · `recipe_id` · `bom_id` · `note`.

Indeks: `(entity_id, template_id, product_id, status)`; `id` unik.

### Aturan (server, satu fungsi `product_route_service.validate`)

| # | Aturan | Pesan bila dilanggar |
|---|---|---|
| R1 | Artikel ada; varian (bila diisi) milik artikel itu | "Varian <SKU> bukan bagian artikel <nama>." |
| R2 | Beli dari pemasok hanya boleh sebagai langkah pertama; hasilnya bertahap sama dengan barang yang dibeli | "Langkah <n>: beli dari pemasok hanya boleh di langkah pertama." |
| R3 | Langkah makloon memakai tahap aktif di Master Tahapan Proses berjenis makloon; asal & hasil tahap dari master (K-57) | "Langkah <n>: tahap '<kode>' tidak ada atau tidak aktif di Master Tahapan Proses." |
| R4 | Rantai bersambung: hasil langkah *n* = asal langkah *n+1* | "Langkah <n+1> (<tahap>) butuh bahan <tahap asal>, sedangkan langkah <n> menghasilkan <tahap hasil>." |
| R5 | Hasil langkah terakhir = tahap varian (bila diisi) atau tahap artikel | "Rute berakhir di <tahap>, padahal artikel ini <tahap>." |
| R6 | Bahan masuk/hasil yang dipilih bertahap sesuai asal/hasil langkahnya | "Langkah <n>: bahan masuk harus bertahap <tahap>; <SKU> bertahap <tahap>." |
| R7 | Mitra makloon (bila diisi) mengerjakan proses langkah itu (`makloons.process_types`) | "Langkah <n>: <mitra> tidak mengerjakan <proses>." |
| R8 | Kontrak (bila diisi) aktif, milik mitra langkah itu, jenisnya cocok (pembelian ↔ beli, makloon ↔ makloon), proses cocok | "Langkah <n>: kontrak <nomor> bukan kontrak <jenis> aktif milik <mitra>." |
| R9 | Produksi sendiri wajib BOM aktif di PT ini; hasil BOM bertahap = hasil langkah | "Langkah <n>: pilih BOM produksi yang aktif." |
| R10 | Rute pertama untuk (PT, artikel, varian) otomatis utama; menandai utama melepas tanda utama rute lain | — |

### Server

| Metode + path | Izin | Isi | Jawaban |
|---|---|---|---|
| `GET /api/product-templates/{id}/routes` | `product.view` | — | `{items, primary_id, status: "diatur"/"belum_diatur"}` rute PT aktif (artikel + pengecualian varian) |
| `POST /api/product-templates/{id}/routes` | `product_route.update` | `{name, product_id?, steps[], is_primary?}` | rute; 400 pesan R1–R9 |
| `PATCH /api/product-routes/{id}` | `product_route.update` | `{name?, steps?, status?}` | rute |
| `POST /api/product-routes/{id}/primary` | `product_route.update` | — | rute |
| `GET /api/products/{id}/route` | `product.view` | — | rute utama yang berlaku untuk varian (pengecualian varian dulu, lalu artikel) atau `{route: null}` |
| `GET /api/product-routes/step-options?from_stage=&kind=` | `product.view` | — | tahap yang boleh berikutnya (dari master) + mitra yang mengerjakan prosesnya |
| `GET /api/product-templates/{id}/routes/suggest` | `product_route.update` | — | usulan rute dari data lama (tidak disimpan) |

Pembuat rute awal (K-71): `backend/scripts/mpt1_rute_awal.py --dry-run | --apply [--entity]` membuat rute
`origin=rute_awal` untuk artikel PT yang belum punya rute, dari (1) rantai resep proses yang berakhir di varian artikel,
(2) BOM aktif berhasil varian artikel, (3) sumber restock `supplier` → beli dari pemasok (pemasok dari barang supplier
bila tunggal). Fungsi yang sama dipakai endpoint `suggest`. Menjalankannya di data nyata = H3.

R&D: `_bind_product` membuat rute "Beli dari <pemasok>" (`origin=rnd`, kontrak hasil putusan) bila artikel belum punya
rute di PT itu. `release_product` menolak bila pengaturan `rnd.release_requires_route` menyala dan varian tidak punya
rute utama: "Produk <SKU> belum punya rute utama. Atur di Master Produk › Rute sebelum dirilis."

Serah-terima (b) — pengalihan pemanggil: `restock_source_service.check_lines` dan `auto_route` membaca rute utama
lebih dulu (rute berisi makloon → jalur makloon; rute satu langkah beli → pembelian; ada rute aktif berjenis lain →
keduanya, dengan alasan); `restock_source` hanya dipakai bila artikel belum punya rute di PT itu. Panel "Sumber
restock artikel" tetap ada sebagai cadangan untuk artikel tanpa rute, berlabel "Dipakai bila artikel belum punya rute";
tanggal mati: sesudah pembuat rute awal dijalankan di data nyata (D8).

### Pengaturan

| key | group | type | default | label | catatan |
|---|---|---|---|---|---|
| `rnd.release_requires_route` | rnd | bool | `True` (K-70) | Rilis produk wajib punya rute utama | consumers `services/rnd_spec_service.py:release_product`; permission `("rnd_spec", "configure")` bila ada, bila tidak `("product", "update")`; risk medium |

### Izin dan peran

`product_route.update` ("Kelola Rute Produk") — `admin`, `md`, `manager` (K-73); modul akses `product`; endpoint di atas;
tombol layar memakai `can(perms, "product_route", "update")`.

### Layar

Master Produk › rincian induk › tab baru **"Rute"** (di samping "Varian & galeri", "Informasi produk"):
- Daftar kartu rute: nama, lencana "Utama", lencana "Khusus varian <SKU>", rantai langkah bertahap
  ("Greige → PFP @ Mitra A → Printing @ Mitra B → Jadi"), mitra/kontrak kosong ditandai "belum diisi".
- Kosong: "Artikel ini belum punya rute di PT ini." + tombol "Buat rute" dan "Usulkan dari data lama".
- Pop-up "Buat rute" / "Ubah rute": Nama rute · Berlaku untuk (Semua varian / satu varian) · langkah-langkah. Tiap
  langkah: Jenis (Beli dari pemasok · Makloon · Produksi sendiri) → pilihan **tersaring**: tahap hanya yang boleh sesudah
  tahap sebelumnya (dari server `step-options`), mitra hanya yang mengerjakan proses itu, kontrak hanya milik mitra itu
  dan jenisnya cocok, bahan/hasil hanya produk bertahap sesuai (`ProductSelect` dengan `stage`).
- Tombol "Jadikan utama", "Nonaktifkan". Galat server ditampilkan apa adanya di pop-up.
- Tanpa izin: tab terbaca, tombol tidak tampil.

## Uji penerimaan

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | Artikel jadi; greige G, PFP P; mitra pre-treatment A, printing B | Buat rute: makloon `pfp` (G→P, A) → makloon `printing` (P→jadi, B) | 200; langkah 1 `from_stage=grey, to_stage=pfp`, langkah 2 `pfp→finished`; `is_primary=true` |
| U2 | B | sama | Rute langsung `printing` dengan bahan greige G | 400 R6 "bahan masuk harus bertahap PFP" |
| U3 | B | sama | Rute `pfp` saja (berakhir PFP) untuk artikel jadi | 400 R5 |
| U4 | B | sama | Langkah `printing` dengan mitra A (hanya pre-treatment) | 400 R7 |
| U5 | B | sama | Langkah 1 makloon, langkah 2 beli | 400 R2 |
| U6 | B | rute U1 utama | Buat rute kedua `is_primary=true` | rute kedua utama, U1 tidak |
| U7 | B | rute artikel + rute khusus varian V1 | `GET /products/V1/route` dan `/products/V2/route` | V1 → rute khusus; V2 → rute artikel |
| U8 | B | peran "Tanpa Acuan" hanya `product.view`+`product_route.update`; "Manajer Kosong" | POST rute | 200 · 403 |
| U9 | B | spesifikasi disetujui, produk tanpa rute, pengaturan menyala | rilis | 400 pesan rute; sesudah rute dibuat → 200; pengaturan mati → 200 tanpa rute |
| U10 | B | sample diputus ke pemasok S | putus | artikel punya rute utama "Beli dari S" berkontrak hasil putusan |
| U11 | B | artikel `restock_source=supplier`, rute utama makloon | `check_lines([(produk,"makloon")])` | tanpa galat & tanpa peringatan menyimpang |
| U12 | B | resep G→P (A) dan P→jadi (B) | pembuat rute awal `--dry-run` lalu `--apply` | dry-run tidak menulis; apply membuat 1 rute 2 langkah `origin=rute_awal`; dijalankan ulang tidak menggandakan |
| U14 | B | sama | `GET /product-routes/step-options?from_stage=grey` | hanya tahap ber-asal Greige (`pfp`, `pfd`); mitra `pfp` hanya yang mengerjakan pre-treatment |
| U13 | layar (uji jalan) | data acuan | buka Master Produk › induk › Rute, buat rute 2 langkah | pilihan tahap/mitra/bahan tersaring; potret 1280 & 390 |

## Langkah kerja

(a) Data, layanan, router, izin, pengaturan, pembuat rute awal, tab layar + uji U1–U10, U12, U13.
(b) Pengalihan `check_lines`/`auto_route` ke rute + label panel sumber restock + U11.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (koleksi `product_routes`), `CODEBASE_MAP.md`, `memory/PRD.md`,
`docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (Rute, Rute utama), `scripts/INDEX.md` (pembuat rute awal).

## Di luar lingkup

- SPK makloon membaca rute dan pilihan tersaring di wizard → MP-T2.
- Sample ke mitra makloon; putusan melahirkan rute makloon & kontrak makloon; gerbang kain dasar → MP-T3.
- BOM produksi in-house tetap layar lamanya; rute hanya merujuknya (penyatuan layar menyusul sesudah dipakai).

## Asumsi dan risiko

ASUMSI: rute per PT karena mitra/kontrak/resep per PT; artikel dipakai bersama.
ASUMSI: langkah "beli" tidak punya tahap asal; hasilnya = tahap barang yang dibeli.
RISIKO: rilis R&D tertahan bila rute tidak terbentuk — dibatalkan dengan mematikan `rnd.release_requires_route`.
RISIKO: rute awal salah tebak pemasok — pembuat hanya mengisi pemasok bila tunggal; selebihnya "belum diisi".

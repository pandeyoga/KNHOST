# Rancangan — Komisi per artikel, pengali yang bisa diatur, dan satu layar "Skema & Tarif"

Tanggal: 23 Nov 2026 · Pemilik keputusan: pemilik KNHOST · Status: **draf, menunggu persetujuan pemilik** · Sudah diputus
pemilik: pendekatan A; tarif per **artikel** dengan pengecualian per varian (1.a); aturan mengikuti **tanggal pesanan dibuat**,
bulan yang sudah diakrualkan dibekukan (2.a).

## 1. Maksud dan alasannya

Kata pemilik (22–23 Nov):
- "untuk komisi saya ingin ada tambahan mekanisme perhitungan baru yaitu berdasarkan produk yang terjual … masing-masing
  bisa di set berapa nilai komisi per yardnya … bisa di set juga misalkan harganya dibawah harga pricelist … nilai
  komisinya bisa diatur juga. jangan hapus komisi yang kemarin dibuat."
- "saya ingin bisa diatur per artikel" · "bagaimana jika membelinya dari harga special" · "untuk pengalinya bisa di
  konfigurasi" · "pengaturannya masih terpisah-pisah untuk insentif … pikirkan ui ux flow yang lebih baik".
- Sumber insentif bisa dipilih: "dari komisi otomatis saja atau dengan [Lembar Insentif] sales jadi bisa double atau
  bisa salah satu saja".
- Pendekatan dipilih pemilik: **A — kembangkan komisi otomatis yang ada** (23 Nov, "ya a").
- Tarif per **artikel** (induk), dengan pengecualian per **varian** (warna/grade) bila perlu (23 Nov, "1.a").
- Aturan (tarif & pengali) yang dipakai = yang berlaku pada **tanggal pesanan dibuat**; bulan yang sudah dibukukan
  akrualnya dibekukan beserta rinciannya (23 Nov, "2.a").

Alasannya (dibaca dari percakapan): pemilik ingin komisi yang mendorong sales menjual artikel tertentu dan menjual di
harga pricelist, dengan aturan yang ia atur sendiri tanpa ubah kode, dan dengan satu tempat yang jelas untuk mengaturnya.

## 2. Keadaan sekarang (dibaca di `de02a65`)

- **Mesin komisi otomatis** `backend/services/sales_force_service.py` `_compute_commission_per_sku` (strategi
  `commission.strategy` = `per_sku`): per baris pesanan, komisi = `base_quantity` × fraksi terbayar di periode ×
  `per_unit_amount` tarif **kategori** × faktor diskon, dibatasi `margin_cap_pct`% dari margin baris; bobot `sales_team`
  `split_pct`. Strategi arsip `achievement_tiered` (persen dari pencairan menurut jenjang capaian, `sales_incentives`).
- **Tarif** `incentive_rates` (router `backend/routers/incentive_rates.py`): per (`entity_id` | "all") × `category`;
  isian `per_unit_amount`, `discount_threshold_type/threshold/mechanic/factor/potong_rp`, `margin_cap_pct`. Kunci
  diambil dari `line.category`. Tidak ada tarif per artikel.
- **Faktor diskon** `_discount_factor`: membandingkan **diskon baris** (`discount_percent` atau Rp/unit) dengan ambang;
  tidak membaca harga pricelist dan tidak membaca sumber harga.
- **Baris pesanan sudah menyimpan** `price_source` (`special_approval` = harga khusus ACC Manajer per pesanan,
  `customer` = harga pelanggan, `entity` = harga PT, `global` = harga umum, `special_order` = pesanan khusus) dan potret
  pembanding KM-T1 `list_price` (+ `global_price`, `floor_price`) per satuan jual — `backend/routers/sales_orders.py`
  `_price_refs`. Baris lama sebelum KM-T1 tidak punya `list_price`. Pesanan khusus satu produk tersimpan dengan
  `price_source="global"` dan bendera `special_order_price` (bukan `price_source="special_order"`).
- Mesin menghitung dengan bilangan pecahan + `round(…, 2)` (bukan sen). Mesin selalu memakai aturan yang berlaku saat
  dihitung (`get_effective_settings`), bukan aturan bulan/pesanan yang dihitung; `incentive_rates` tidak bertanggal.
- Tiap baris tarif menyimpan `margin_cap_pct` dan isian diskonnya sendiri yang **menimpa** kunci PT
  (`eff_cfg = {**cfg, **rate_cfg}`), jadi `commission.default_margin_cap_pct`/`commission.discount_*` praktis hanya
  bawaan isian tarif baru.
- "Artikel" di sistem ini = induk produk (`product_templates`, `products.template_id`); tiap warna/grade = varian (SKU
  sendiri). Rute Produk memakai pola "per artikel, pengecualian per varian" (K-65, `product_route_service.py`).
- **Pengaturan bawaan komisi** `commission.*` (8 kunci, `backend/config_catalog_core.py` ±376–460).
- **Cara insentif masuk gaji** `hr.payroll_commission_mode` (`backend/config_catalog_ops.py` ±793):
  `accrue_then_settle` · `pay_on_invoice` · `off` · `sheet`. `sheet` mematikan komisi otomatis
  (`backend/services/hr_payroll_service.py` ±319–340) — "keduanya" belum ada.
- **Lembar Insentif** (KM-T1…T5): nominal diketik orang dari Capaian; target per sales per periode (KM-T1).
- **Layar**: SDM › Kinerja & Insentif (`hr-kpi-hub`): Capaian · Lembar Insentif · Target & Aturan. Bagian "Komisi
  otomatis (cara lama)" di Target & Aturan (`LegacyRatesEditor`, `LegacySchemeEditor`) hanya tampil bila mode PT bukan
  `sheet`/`off`. Masalah UX terlihat: jenjang per sales tampil padahal tidak dipakai strategi `per_sku`; isian "Bonus per
  produk fokus" disimpan tetapi tidak pernah dihitung; "Satuan tarif komisi: Meter — tidak dipakai sistem" bertentangan
  dengan "/satuan dasar"; tidak ada pratinjau dampak.
- Pengaturan insentif tersebar di 4 tempat: Pusat Pengaturan › Komisi sales; Target & Aturan; Pusat Pengaturan › SDM
  (cara masuk gaji); Pengaturan › Persetujuan (kontrol dua orang lembar).

## 3. Tujuan, bukan tujuan, anti-tujuan

**Tujuan**
1. Tarif komisi Rp per satuan dasar (yard) bisa diatur **per artikel**, dengan cadangan tarif kategori.
2. **Pengali harga yang bisa diatur**: pita "di bawah pricelist" (jumlah pita, batas, pengali bebas) dan pengali per
   **sumber harga** (harga khusus, harga pelanggan, pesanan khusus) — masing-masing "ikut pita" atau pengali tetap.
3. **Pengali capaian target** opsional (mati bawaan), jenjangnya bisa diatur.
4. Sumber insentif per PT: komisi otomatis saja · Lembar Insentif saja · **keduanya dibayar**.
5. **Satu layar** "Skema & Tarif" untuk semua aturan komisi PT, dengan **simulasi** sebelum menyimpan.
6. Komisi kategori yang sudah ada tetap berjalan; PT yang tidak mengubah apa pun mendapat hasil yang sama persis.

**Bukan tujuan**: mengubah Lembar Insentif (alur, pengesahan, nominal manual); mengubah cara jurnal/akrual/gaji selain
menambah mode "keduanya"; komisi dari margin/omzet persen (strategi arsip tetap apa adanya).

**Anti-tujuan** (gagal walau "jalan"):
- Komisi PT yang tidak disentuh berubah angka sesudah rilis.
- Insentif terbayar dua kali tanpa pemilik memilih "keduanya".
- Aturan bisnis jadi punya sumber kedua di luar Pusat Pengaturan (standar `docs/blueprint/02_STANDAR.md` §2).
- Pengguna tidak bisa menjelaskan ke sales dari mana angka komisinya (rincian harus menunjukkan tiap faktor).

## 4. Batasan

- Standar proyek: aturan bisnis = pengaturan (`02_STANDAR.md` §2, termasuk uji wajib kunci baru §2.4); wewenang = izin
  (§3); angka keputusan disimpan dengan potretnya (§5 D3); bahasa layar Indonesia, tanpa kode mentah (§4).
- Titik henti H5 (KM-T4): agen tidak mengubah sakelar mode PT nyata; bawaan untuk PT yang ada tetap seperti sekarang.
- Uang bersen: hasil per baris dibulatkan 2 desimal seperti mesin sekarang; layar menampilkan sen bila ada (K-07).
- Tanggal = tanggal buku WIB (`services/book_date.tanggal_buku`).

## 5. Pendekatan (dipilih: A)

| | Pendekatan | Untung | Rugi |
|---|---|---|---|
| **A** ✔ | Kembangkan komisi otomatis yang ada: tarif per artikel di tabel tarif sekarang (+ kolom artikel); semua pengali = kunci Pusat Pengaturan per PT (riwayat, jadwal "berlaku mulai"); diedit dari satu tab baru; mode gaji + "keduanya" | Akrual, jurnal, gaji, dan uji yang ada dipakai ulang; sesuai §2; risiko terkecil | Aturan di Pusat Pengaturan tidak bertanggal per pesanan → perlu potret aturan per baris pesanan (6.5a) |
| B | Dokumen "Skema Komisi" ber-versi (draf → disahkan → berlaku) | Paling rapi untuk audit | Sumber aturan kedua di luar Pusat Pengaturan (melanggar §2); migrasi tarif & 8 kunci; kerja terbesar |
| C | Hitungan per artikel hanya usulan baris Lembar Insentif | Kecil | Tidak bisa "komisi otomatis saja" — tidak sesuai permintaan |

## 6. Rancangan

### 6.1 Rumus per baris pesanan

```
komisi_baris = qty_dasar_terbayar × tarif × pengali_harga × pengali_capaian × bobot_tim
               dibatasi  batas_margin% × margin_baris_terbayar   (hanya bila HPP diketahui — seperti sekarang)
```
- `qty_dasar_terbayar`, fraksi terbayar periode, `bobot_tim`, batas margin, proyeksi penuh: **tetap seperti mesin
  sekarang**.
- Rincian per baris menyimpan tiap faktor (tarif + asalnya, pengali harga + alasannya, pengali capaian) supaya layar dan
  kartu sales bisa menjelaskan angka.

### 6.2 Tarif (urutan pencarian) — per artikel, pengecualian per varian (keputusan 1.a)

1. tarif **varian** (`product_id`) di PT itu → 2. varian "Semua PT" → 3. tarif **artikel** (`template_id`) di PT →
   4. artikel "Semua PT" → 5. tarif **kategori** di PT → 6. kategori "Semua PT" → 7. tidak ada tarif = tidak ada komisi
   baris itu (seperti sekarang).
- Data: `incentive_rates` mendapat isian opsional `template_id` (tarif artikel) atau `product_id` (pengecualian varian),
  dengan potret nama/kode untuk tampilan. Baris tanpa keduanya = tarif kategori (baris lama tidak diubah). Satu tarif
  aktif per (PT, kategori), (PT, artikel), (PT, varian) — dijaga indeks unik.
- Varian/warna baru otomatis ikut tarif artikelnya. Produk tanpa `template_id` hanya bisa diberi tarif varian.
- **Batas margin tetap per baris tarif** (seperti sekarang, supaya angka PT yang tidak disentuh tidak berubah); kunci
  `commission.default_margin_cap_pct` = isian bawaan saat membuat tarif baru (keputusan penulis, lihat §8).
- Isian ambang/mekanik diskon lama tetap ada di baris tarif dan tetap dipakai pada basis `diskon_baris` (6.3).

### 6.3 Pengali harga (kunci Pusat Pengaturan per PT)

**Selisih terhadap harga acuan** per satuan jual: `selisih% = (acuan − harga_bersih) / acuan × 100`, harga bersih =
`line_total / quantity`. **Acuan mengikuti kunci yang sudah ada `insentif.harga_acuan`** (`daftar_pt` → `list_price`,
`umum` → `global_price`, `batas_bawah` → `floor_price`, semua dari potret baris KM-T1) supaya Capaian/Lembar dan komisi
memakai definisi "di bawah harga" yang sama (keputusan penulis). Harga ≥ acuan → 0%.

- `commission.price_bands` (tabel, baru): baris berurutan `{sampai_pct_di_bawah, pengali}`; baris terakhir tanpa batas.
  Bawaan: satu baris "berapa pun → ×1,0" (= tanpa pita).
- `commission.price_source_rules` (tabel, baru): per sumber harga (`special_approval` "Harga khusus", `customer` "Harga
  pelanggan", "Pesanan khusus" = `price_source` `special_order` **atau** bendera `special_order_price`) → `ikut_pita`
  atau `pengali_tetap` + nilai. Bawaan: semua `ikut_pita`. Harga PT/umum selalu ikut pita.
- `commission.price_basis` (enum, baru): `diskon_baris` (cara lama, bawaan) · `pricelist` (pita di atas).
  **Bawaan `diskon_baris`** supaya PT yang tidak disentuh berhasil sama persis (anti-tujuan 1).
- Baris pesanan tanpa harga acuan (pesanan lama sebelum KM-T1, atau acuan kosong) → memakai cara lama (diskon baris)
  walau basis `pricelist`; rincian menulis alasannya ("tanpa harga pembanding").
- Pengali khusus artikel (opsional): baris tarif artikel boleh membawa `price_bands`/`price_source_rules` sendiri yang
  menimpa milik PT untuk artikel itu.

### 6.4 Pengali capaian (opsional)

- `commission.achievement_multiplier` (bool, bawaan mati) · `commission.achievement_basis` (enum: `omzet_bersih` ·
  `uang_masuk`) · `commission.achievement_tiers` (tabel `{capaian_min_pct, pengali}`).
- Capaian = angka sales **bulan** itu dari pengumpul Capaian KM-T2 dibanding **target bulanan** KM-T1. Tanpa target
  bulanan → pengali 1,0 dan rincian menulis "tanpa target bulanan". Target triwulan/tahunan + penyesuaian akhir periode
  = di luar tahap ini (keputusan penulis).
- Capaian dihitung untuk **bulan komisi** (bulan uang masuk), bukan bulan pesanan. Jenjang yang dipakai = jenjang yang
  berlaku pada akhir bulan komisi itu, dipotret saat akrual dibukukan — pengecualian dari 6.5a karena capaian sifatnya
  bulanan, bukan per pesanan (keputusan penulis).
- Strategi arsip `achievement_tiered` dan editor jenjangnya tidak diubah; di layar baru jenjang arsip hanya tampil bila
  strategi itu yang dipakai.

### 6.5 Sumber insentif (mode gaji)

- `hr.payroll_commission_mode` mendapat pilihan baru **`auto_and_sheet`** "Komisi otomatis + Lembar Insentif (keduanya
  dibayar)": komisi otomatis berjalan seperti `accrue_then_settle` **dan** lembar yang disahkan berjalan seperti `sheet`.
  Slip memuat keduanya sebagai baris terpisah; jurnalnya terpisah (akrual komisi otomatis dan beban lembar).
- Pemetaan pilihan ① di layar (keputusan penulis): "Komisi otomatis" → `accrue_then_settle`, **kecuali** PT sedang
  `pay_on_invoice` (nilai itu dipertahankan; cara pembukuan tidak diubah diam-diam); "Lembar Insentif" → `sheet`;
  "Keduanya" → `auto_and_sheet`. `off` dan `pay_on_invoice` tampil apa adanya dengan tautan ke Pusat Pengaturan; memilih
  "Keduanya" dari `pay_on_invoice` meminta konfirmasi yang menyebut perubahan cara pembukuan ke akrual.
- Layar menampilkan peringatan jelas di pilihan "Keduanya": insentif dari dua sumber dibayar bersama.
- Bawaan tidak berubah (`accrue_then_settle`); sakelar PT nyata tidak diubah agen (H5).

### 6.5a Aturan mana yang berlaku — tanggal pesanan (keputusan 2.a)

- Saat **pesanan dibuat**, setiap baris memotret aturan komisinya: tarif + asalnya (varian/artikel/kategori, PT/Semua
  PT), basis harga, pita, aturan sumber harga, ambang/mekanik diskon lama, batas margin. Mesin memakai potret ini, bukan
  aturan terkini. Contoh: tarif Batik Mega naik Rp 3.000 → Rp 3.500 mulai 1 Des; pesanan 25 Nov dibayar 5 Des → Rp 3.000.
- Amandemen pesanan yang mengubah harga/qty baris **tidak** memotret ulang aturan (tetap tanggal pesanan dibuat);
  baris baru hasil amandemen memotret aturan saat baris itu ditambahkan (keputusan penulis).
- Pesanan yang dibuat **sebelum** fitur ini tidak punya potret → memakai aturan yang berlaku saat pertama kali dihitung
  sesudah rilis, lalu dipotret ke pesanan itu (sekali), sehingga sejak itu tidak berubah lagi.
- Saat **akrual bulanan dibukukan**, rincian per sales per baris (qty terbayar, tarif, tiap pengali, batas, hasil)
  disimpan bersama jurnalnya (`02_STANDAR.md` §5 D3). Gaji, "Insentif saya", dan laporan bulan itu membaca rincian
  beku ini; koreksi akrual hanya menghitung selisih akibat data sumber berubah (pembayaran/retur), bukan akibat aturan.

### 6.6 Layar — tab "Skema & Tarif"

Tempat: SDM › Kinerja & Insentif: Capaian · Lembar Insentif · **Skema & Tarif** · Target & Aturan (Target & Aturan tetap
untuk target, komponen lembar, definisi angka; bagian "Komisi otomatis (cara lama)" dipindah ke tab baru).

```
PT Sukacita ▾                                         [Simulasi]  [Riwayat perubahan]
① Sumber insentif   ( ) Komisi otomatis  ( ) Lembar Insentif  (•) Keduanya dibayar
② Tarif per artikel  [Cari] [Kategori ▾] [Ubah banyak] [Unduh / Unggah Excel]
   ▾ Batik — tarif kategori Rp 3.000/yard                         [Ubah]
       BTK-MEGA-001  Batik Mega     Rp 3.500/yard  tarif sendiri  [Ubah] [Hapus]
       BTK-PRG-002   Batik Parang   ikut kategori                 [Atur tarif]
③ Pengali harga     Dasar: (•) di bawah pricelist  ( ) diskon baris (cara lama)
                    s.d. 3% ×0,8 · s.d. 10% ×0,5 · >10% ×0      [Ubah pita]
                    Harga khusus: ×0,5 · Harga pelanggan: ikut pita · Pesanan khusus: ikut pita
④ Pengali capaian   [ ] aktif   (jenjang & basis)
⑤ Batas             komisi maks 50% dari margin baris
```
- ①③④⑤ membaca/menulis **kunci Pusat Pengaturan yang sama** (lewat API pengaturan yang ada, termasuk "berlaku mulai",
  alasan, riwayat); Pusat Pengaturan › Komisi sales menautkan ke tab ini. ② = data tarif.
- **Ubah banyak**: pilih beberapa artikel → set tarif sekaligus. **Excel**: unduh daftar artikel+tarif, unggah →
  pratinjau baris berubah → konfirmasi.
- **Simulasi**: pilih sales + bulan → tabel per artikel: yard × tarif × pengali harga (+alasan) × pengali capaian =
  komisi; total "sekarang" vs "dengan perubahan belum disimpan".
- Dibersihkan dari layar: isian "Bonus per produk fokus" (tidak pernah dihitung; data tetap disimpan), label satuan
  "Meter" diganti "yard / satuan dasar barang".
- Kartu "Insentif saya" (sales) menampilkan rincian faktor per artikel; langkah batas margin hanya ditulis
  "dibatasi batas margin" **tanpa angka margin** (margin tetap dijaga izin `incentive.view_margin`).
- Tabel ② menampilkan **artikel** (bukan kode varian); baris artikel bisa dibuka untuk melihat/menambah pengecualian
  varian. Excel berisi baris artikel + baris pengecualian varian.
- ⑤ "Batas" = bawaan batas margin untuk tarif baru; batas tiap tarif tampil dan diubah di baris tarifnya.

### 6.7 Izin

Lihat tab = `sales_force.view` (sama dengan sekarang); ubah tarif = `sales_force.update`, hapus = `sales_force.delete`;
ubah kunci pengaturan = izin pengaturan kunci masing-masing (registri); ubah mode gaji = izin kunci
`hr.payroll_commission_mode`. Tombol tampil menurut izin; server menolak 403 berkalimat.

## 7. Keputusan yang menjadi milik pembangun

- Bentuk penyimpanan pita/aturan khusus per artikel (isian di baris tarif), nama kunci final, indeks.
- Cara menampilkan simulasi (pop-up atau panel), ukuran halaman tabel artikel, format Excel.
- Satu fungsi potret aturan dipakai semua jalur pembuatan baris pesanan (pesanan biasa, konversi penawaran, pesanan
  khusus, baris baru amandemen); bentuk isian potret di baris pesanan.
- Pengujian: tests_mem untuk rumus (tiap faktor, urutan tarif varian→artikel→kategori, baris lama tanpa `list_price`,
  potret tanggal pesanan vs aturan baru, bulan beku, mode keduanya ke gaji & jurnal, kesetaraan hasil PT yang tidak
  disentuh) dan jest untuk layar; uji layar satu alur ujung ke ujung.

## 8. Keputusan penulis (boleh dikoreksi pemilik saat membaca)

1. Batas margin tetap per baris tarif; kunci PT = bawaan tarif baru (menjaga angka PT yang tidak disentuh).
2. Kartu sales hanya menulis "dibatasi batas margin", tanpa angka margin/HPP.
3. Acuan pita harga mengikuti `insentif.harga_acuan` (sama dengan Capaian/Lembar).
4. Pengali capaian memakai target bulanan saja pada tahap ini.
5. Pilihan "Keduanya" memakai cara pembukuan akrual; PT `pay_on_invoice` tidak diubah tanpa konfirmasi.
6. Amandemen tidak memotret ulang aturan baris lama; pesanan lama dipotret sekali saat pertama dihitung sesudah rilis.
7. Pengali capaian ikut bulan komisi (jenjang akhir bulan itu), bukan tanggal pesanan.

## 9. Catatan untuk keputusan pemilik sesudahnya (tidak menghalangi pembangunan)

- Nilai awal pita dan pengali untuk PT nyata diisi pemilik di layar (bawaan = tanpa perubahan perilaku).
- Memilih "keduanya dibayar" untuk PT nyata dilakukan pemilik sendiri (H5).

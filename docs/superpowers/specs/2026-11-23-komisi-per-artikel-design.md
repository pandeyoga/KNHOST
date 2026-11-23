# Rancangan — Komisi per artikel, pengali yang bisa diatur, dan satu layar "Skema & Tarif"

Tanggal: 23 Nov 2026 · Pemilik keputusan: pemilik KNHOST · Status: **draf, menunggu persetujuan pemilik**

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
  `_price_refs`. Baris lama sebelum KM-T1 tidak punya `list_price`.
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
- Uang bersen: hitung dengan sen (`to_cents`) seperti mesin sekarang; layar menampilkan sen bila ada (K-07).
- Tanggal = tanggal buku WIB (`services/book_date.tanggal_buku`).

## 5. Pendekatan (dipilih: A)

| | Pendekatan | Untung | Rugi |
|---|---|---|---|
| **A** ✔ | Kembangkan komisi otomatis yang ada: tarif per artikel di tabel tarif sekarang (+ kolom artikel); semua pengali = kunci Pusat Pengaturan per PT (riwayat, jadwal "berlaku mulai"); diedit dari satu tab baru; mode gaji + "keduanya" | Akrual, jurnal, gaji, dan uji yang ada dipakai ulang; sesuai §2; risiko terkecil | Perubahan aturan ikut memengaruhi bulan yang belum diakrualkan (diredam "berlaku mulai") |
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

### 6.2 Tarif (urutan pencarian)

1. Tarif **artikel** di PT itu → 2. tarif artikel "Semua PT" → 3. tarif **kategori** di PT → 4. tarif kategori "Semua PT"
   → 5. tidak ada tarif = tidak ada komisi baris itu (seperti sekarang).
- Data: `incentive_rates` mendapat isian opsional `product_id` (+ potret `sku`, `product_name` untuk tampilan). Baris
  tanpa `product_id` = tarif kategori (baris lama tidak diubah). Satu tarif aktif per (PT, artikel) dan per (PT,
  kategori) — dijaga indeks unik.
- Isian ambang/mekanik diskon lama tetap ada di baris kategori untuk kompatibilitas (lihat 6.3, cadangan).

### 6.3 Pengali harga (kunci Pusat Pengaturan per PT)

**Selisih terhadap pricelist** per satuan dasar: `selisih% = (list_price − harga_bersih) / list_price × 100`, memakai
potret `list_price` baris pesanan (KM-T1) dan harga bersih baris (`line_total / quantity`). Harga ≥ pricelist → 0%.

- `commission.price_bands` (tabel, baru): baris berurutan `{sampai_pct_di_bawah, pengali}`; baris terakhir tanpa batas.
  Bawaan: satu baris "berapa pun → ×1,0" (= tanpa pita).
- `commission.price_source_rules` (tabel, baru): per sumber harga (`special_approval` "Harga khusus", `customer` "Harga
  pelanggan", `special_order` "Pesanan khusus") → `ikut_pita` atau `pengali_tetap` + nilai. Bawaan: semua `ikut_pita`.
  Harga PT/umum selalu ikut pita.
- `commission.price_basis` (enum, baru): `diskon_baris` (cara lama, bawaan) · `pricelist` (pita di atas).
  **Bawaan `diskon_baris`** supaya PT yang tidak disentuh berhasil sama persis (anti-tujuan 1).
- Baris pesanan lama tanpa `list_price` → memakai cara lama (diskon baris) walau basis `pricelist`; rincian menulis
  alasannya ("pesanan lama tanpa harga pembanding").
- Pengali khusus artikel (opsional): baris tarif artikel boleh membawa `price_bands`/`price_source_rules` sendiri yang
  menimpa milik PT untuk artikel itu.

### 6.4 Pengali capaian (opsional)

- `commission.achievement_multiplier` (bool, bawaan mati) · `commission.achievement_basis` (enum: `omzet_bersih` ·
  `uang_masuk`) · `commission.achievement_tiers` (tabel `{capaian_min_pct, pengali}`).
- Capaian = angka sales periode itu dari pengumpul Capaian KM-T2 dibanding target KM-T1 (target per sales per PT per
  jenis periode). Tanpa target → pengali 1,0 dan rincian menulis "tanpa target".
- Strategi arsip `achievement_tiered` dan editor jenjangnya tidak diubah; di layar baru jenjang arsip hanya tampil bila
  strategi itu yang dipakai.

### 6.5 Sumber insentif (mode gaji)

- `hr.payroll_commission_mode` mendapat pilihan baru **`auto_and_sheet`** "Komisi otomatis + Lembar Insentif (keduanya
  dibayar)": komisi otomatis berjalan seperti `accrue_then_settle` **dan** lembar yang disahkan berjalan seperti `sheet`.
  Slip memuat keduanya sebagai baris terpisah; jurnalnya terpisah (akrual komisi otomatis dan beban lembar).
- Layar menampilkan peringatan jelas di pilihan ini: insentif dari dua sumber dibayar bersama.
- Bawaan tidak berubah (`accrue_then_settle`); sakelar PT nyata tidak diubah agen (H5).

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
- Kartu "Insentif saya" (sales) menampilkan rincian faktor per artikel.

### 6.7 Izin

Lihat tab = `sales_force.view` (sama dengan sekarang); ubah tarif = `sales_force.update`, hapus = `sales_force.delete`;
ubah kunci pengaturan = izin pengaturan kunci masing-masing (registri); ubah mode gaji = izin kunci
`hr.payroll_commission_mode`. Tombol tampil menurut izin; server menolak 403 berkalimat.

## 7. Keputusan yang menjadi milik pembangun

- Bentuk penyimpanan pita/aturan khusus per artikel (isian di baris tarif), nama kunci final, indeks.
- Cara menampilkan simulasi (pop-up atau panel), ukuran halaman tabel artikel, format Excel.
- Pengujian: tests_mem untuk rumus (tiap faktor, urutan tarif, baris lama tanpa `list_price`, mode keduanya ke gaji &
  jurnal, kesetaraan hasil PT yang tidak disentuh) dan jest untuk layar; uji layar satu alur ujung ke ujung.

## 8. Catatan untuk keputusan pemilik sesudahnya (tidak menghalangi pembangunan)

- Nilai awal pita dan pengali untuk PT nyata diisi pemilik di layar (bawaan = tanpa perubahan perilaku).
- Memilih "keduanya dibayar" untuk PT nyata dilakukan pemilik sendiri (H5).

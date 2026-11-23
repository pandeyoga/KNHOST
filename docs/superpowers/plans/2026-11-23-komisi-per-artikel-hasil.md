# Hasil — Komisi per Artikel, pengali yang bisa diatur, tab "Skema & Tarif" (KA-1…KA-11)

Tanggal: 23 Nov 2026 · Cabang `claude/nifty-carson-jjx3c8` (kode `d7b367b..02dd913`, 30 commit; dokumen akhir KA-11 di commit sesudahnya; gelombang
perbaikan tinjauan akhir `bcfb5f0..` — bagian 7; `main` tidak disentuh) ·
Rancangan: `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md` (keputusan pelaksanaan §8 butir 8–24) ·
Rencana: `docs/superpowers/plans/2026-11-23-komisi-per-artikel.md` · Tangkapan layar: folder
`docs/superpowers/plans/2026-11-23-komisi-per-artikel-hasil/` (skala 2).

Angka di bawah ditulis **apa adanya** seperti terbaca di keluaran perintah; yang merah tetap ditulis merah.

## 1. Yang dibangun (ringkas)

| Unit | Isi |
|---|---|
| KA-1 | 6 kunci Pusat Pengaturan per PT (sub-judul "Komisi sales: pengali"): `commission.price_basis` (bawaan "Diskon baris (cara lama)"), `commission.price_bands`, `commission.price_source_rules`, `commission.achievement_multiplier` (bawaan mati), `commission.achievement_basis`, `commission.achievement_tiers`; validasi nilai tabel |
| KA-2 | Tarif per **artikel** (`template_id`) dan pengecualian per **varian** (`product_id`) di `incentive_rates`, kunci unik `(entity_id, rate_key)` |
| KA-3 | Aturan murni `services/commission_rules.py`: urutan tarif varian → artikel → kategori (PT dulu, lalu Semua PT), pengali harga (pita selisih dari harga acuan / aturan harga khusus / diskon baris lama), hitung baris |
| KA-4 | Aturan tiap baris **dipotret saat pesanan dibuat** (`sales_orders.items[].commission_rule`); pesanan lama dipotret sekali saat aplikasi menyala |
| KA-5 | Mesin komisi membaca potret; rincian per artikel dengan tiap faktor (tanpa angka margin/HPP) |
| KA-6 | Pengali capaian target bulanan (opsional) + pembekuan aturan bulan saat jurnal akrual dibukukan (`commission_period_rules`) |
| KA-7 | Sumber insentif **"Keduanya dibayar"** (`hr.payroll_commission_mode = auto_and_sheet`) |
| KA-8 | API layar: kategori/artikel/varian, ubah banyak, Excel unduh/pratinjau/terapkan, simulasi |
| KA-9 | Tab **SDM › Kinerja & Insentif › Skema & Tarif** (sumber insentif, pohon tarif, pengali, batas margin, akrual, simulasi) |
| KA-10 | Rincian faktor di kartu "Capaian & Insentif Saya" dan Beranda Sales |
| KA-11 | Dokumen, uji penuh, gate, uji layar ujung ke ujung, perbaikan temuan (bagian 5) |

## 2. Uji penuh (sekali)

### 2.1 Backend `tests_mem`
Perintah: `python -m pytest backend/tests_mem -n 0 -q -p no:cacheprovider` (pohon `84f1680` + dokumen; 879,83 dtk).

```
FAILED backend/tests_mem/test_PRT6_layar_peran.py::test_PRT6_U4_pratinjau_memuat_ringkasan_dan_menu_tambahan
1 failed, 2681 passed, 2 skipped, 3 xfailed, 12 warnings in 879.83s (0:14:39)
```

- **Penyebab: cabang ini** (KA-9 `52afb16`). Bukti: uji yang sama di worktree `d7b367b` → `18 passed`. Modul Pengawasan
  Tim Sales & Kredit kembali membuka grup SDM/hub/tab Skema & Tarif, padahal Sales bawaan memegang `credit_override`
  (modul yang sama) → `nav_allowed_for_perms` menganggap Sales sudah membuka grup SDM.
- **Diperbaiki** `3302c1f` (syarat aksi untuk `hrd`/`hr-kpi-hub`/`incentive-scheme`, tanpa `credit_override`). Menu
  semua peran bawaan dibandingkan dengan `d7b367b`: hanya admin/manajer/Finance bertambah `incentive-scheme` (maksud
  KA-9); Sales, Admin Sales, MD, Admin Sample sama persis. Uji ulang terarah sesudah perbaikan: PRT6/PRT5/PRT2/PRT3/
  KFIN01/KMT5 **79 passed**; PRT7/PRT4/PRT9/PRT8b + penyaring notifikasi **107 passed**; `tests/test_fe03_access_catalog.py`
  6 fungsi OK; `verify_access_catalog_nav` 0 temuan; KA6+KA7 **18 passed** (sesudah `576e06f`).
- Suite penuh **tidak** diulang sesudah perbaikan (aturan uji hemat: sekali); perbaikan diuji terarah seperti di atas.

### 2.2 Frontend jest
Perintah: `fe_sync; (cd $S/fe && CI=true npx craco test --watchAll=false)` (pohon `576e06f`).

```
Test Suites: 1 failed, 237 passed, 238 total
Tests:       1 failed, 1813 passed, 1814 total
```

- Yang merah: `tzTanggalBawaan.test.js` › "proses uji ber-zona UTC: tanggal perangkat pada saat beku masih 17 Nov".
  **Kendala lingkungan, bukan cabang ini**: pembantu lingkungan uji (`envA.sh`) mengekspor `TZ=Asia/Jakarta` dari
  `backend/.env`, sedangkan uji ini mensyaratkan proses ber-zona UTC. Berkas yang sama dengan `TZ` dikosongkan →
  `3 passed`; dengan `TZ=Asia/Jakarta` → `1 failed, 2 passed`. Cabang ini tidak menyentuh berkas uji itu maupun layar
  keuangan yang diujinya. Kendala muat suite `cmdk`/`@radix-ui` (`docs/blueprint/03_LINGKUNGAN_UJI.md` §6) tidak muncul
  di putaran ini (238 suite termuat).
- Sesudah perbaikan KA-11 (bagian 5): 23 suite yang memakai berkas yang diubah → **346 passed**.

## 3. Gate

`gate_ci` (= `bash scripts/gate.sh --ci`, pohon `d497c8f`, 448 dtk): **kode 1 — ADA GATE MERAH**, sama seperti garis dasar.
Jumlah gate: **37 merah · 108 hijau** — garis dasar `gate_akhir2.log` (main `686befe`, 18 Nov): **37 merah · 108 hijau**;
196 judul bagian identik.

Penilaian per pelanggaran (`python3 scripts/blueprint/bandingkan_pelanggaran_gate.py gate_akhir2.log gate_last_ci.log`):

```
== POC FASE E-7: garis dasar 7 · sekarang 8 · baru 1 · hilang 0
   + CLEANUP (POC-RESIDU-#): nol residu di SELURUH basis data (# koleksi dihitung, bukan hanya yang dipantau)
== finance: garis dasar 2 · sekarang 0 · baru 0 · hilang 2
== manager: garis dasar 4 · sekarang 2 · baru 0 · hilang 2
== sales: garis dasar 5 · sekarang 4 · baru 0 · hilang 1
== sales_admin: garis dasar 6 · sekarang 5 · baru 0 · hilang 1
HASIL: ADA PELANGGARAN BARU
```

| Pelanggaran baru | Asal | Tindakan |
|---|---|---|
| E-7 CLEANUP: `ai_fact_state +3 · fact_collections +8 · fact_sales_lines +14 · fact_shipment_sales +5 · incentive_definitions +1 · sys_scheduler_runs +7` | **Bukan cabang ini** — penjadwal `incentive_fact_sync`/`ai_fact_sync` (KM-T1 `2ed5c53`, tiap 5 menit) pertama kali berjalan 13.50.15 UTC sesudah backend dinyalakan ulang di data acuan yang faktanya kosong, tepat di tengah POC E-7 | Bukti: POC E-7 dijalankan ulang sendirian → residu **PASS** ("semua koleksi identik"), `41 PASS · 7 FAIL` = garis dasar 7 |
| `validate_compliance`: `❌ [FILE_SIZE] kaSkemaTarif.test.js: 897 baris (MELEBIHI BATAS KERAS 760)` — tidak terbaca pembanding (baris `❌`, bukan `✗`) | **Cabang ini** (KA-9) | Diperbaiki `5724afa` (uji dipecah: 10 + 16 uji, isi sama); `validate_compliance` kembali `1 FAIL` = garis dasar (`frontend/.env` tidak ada) |

Pemeriksaan tambahan atas baris `[FAIL]`/`❌` per bagian (di luar pembanding): hanya dua butir di atas. `verify_data_integrity`
`PASS 257 · FAIL 4 · WARN 7` = garis dasar. Pembanding lama (`bandingkan_gate.py` terhadap garis dasar 13 Nov) menulis
"LEBIH MERAH: POC Cek Kenyataan Peran, POC FASE N" — keduanya sudah merah di `gate_akhir2` (main), tanpa pelanggaran baru.
Commit sesudah gate (`5724afa`, `5d3a58d`, `02dd913`) tidak di-gate ulang; diperiksa `validate_compliance`,
`verify_ui_standard` (112 = `d7b367b`), dan jest terarah.

## 4. Uji layar ujung ke ujung (Playwright, data acuan `final_seed3.gz`, PT Sukacita)

Skrip di ruang kerja sesi (`ka11/s2…s10*.js`), bukan di repo. Data acuan dipulihkan sesudah uji (basis data dibuang +
`mongorestore`), jadi pengaturan & tarif uji tidak tersisa.

### 4.1 Langkah dan jalurnya

| # | Langkah | Jalur | Hasil |
|---|---|---|---|
| 1 | Tarif kategori Woven Rp 200 (PT ini) | **Layar** pop-up tarif | "Tarif kategori Woven tersimpan untuk Sukacita Textile." |
| 2 | Tarif artikel DENIM TENCEL (KNWVN0015) Rp 500 | **Layar** pop-up (gambar 02) | baris artikel "Rp 500 tarif sendiri"; varian lain "ikut artikel Rp 500" |
| 3 | Pengecualian varian DENIM TENCEL HITAM Rp 800 | **Layar** pop-up | "Rp 800 tarif sendiri"; artikel "1 varian bertarif sendiri" (gambar 01) |
| 4 | Dasar harga "Selisih dari harga acuan"; pita s.d. 3% ×0,8 · s.d. 10% ×0,5 · sisa ×0; "Harga khusus: Pengali tetap ×0,5" | **Layar** (Pusat Pengaturan tertanam, alasan + konfirmasi risiko tinggi) | dibaca balik lewat `/config/explain`: `pricelist`, `[{3,0.8},{10,0.5},{null,0}]`, `special_approval pengali_tetap 0.5` (gambar 07) |
| 5 | Excel: unduh → ubah ATHENA STRETCH 350 & BANGKOK TWILL 300 → unggah → pratinjau → Terapkan (alasan) | **Layar** | "2 baru · 0 diubah · 38 sama · 0 galat" → "Excel diterapkan: 2 tarif baru, 0 diubah." (gambar 03) |
| 6 | Harga acuan komisi PT = harga umum (`insentif.harga_acuan = umum`) | API admin (kunci di Pusat Pengaturan › Insentif, di luar tab) | — |
| 7 | Harga PT varian TAUPE Rp 24.400 (harga umum Rp 25.000) | API admin `POST /api/pricelist` | — |
| 8 | Harga khusus HITAM Rp 18.000 untuk pelanggan "Latihan 01 · Toko Kain Peserta 01" | API: sales (draf → bukti → ajukan) → manajer setuju | alur persetujuan lengkap lewat API |
| 9 | Pesanan 1 harga PT (TAUPE, 1 roll) & pesanan 2 harga khusus (HITAM, 1 roll) | API sebagai sales Ayu (`POST /api/sales-orders`) | `KSC/SO-00034`, `KSC/SO-00035`; potret: tarif 500 artikel/PT, acuan umum, basis pricelist · tarif 800 varian/PT |
| 10 | Bayar: SO-00034 lunas Rp 3.268.767,96 · SO-00035 separuh Rp 1.176.822 | API Finance `POST /api/ar-receipts` | `KSC/AR-00018`, `KSC/AR-00019` |
| 11 | Kartu "Capaian & Insentif Saya" + Beranda Sales | **Layar** sebagai sales Ayu | gambar 05, 06 |
| 12 | Simulasi: Ayu · Nov 2026 · tarif percobaan DENIM TENCEL Rp 600 | **Layar** | gambar 04 |

### 4.2 Hitung tangan vs layar

| Baris | Hitung tangan | API `/sales/commission` & `/incentive/me` | Kartu & beranda |
|---|---|---|---|
| SO-00034 TAUPE: 120,69 yd lunas; harga Rp 24.400 vs acuan umum Rp 25.000 → selisih 2,4% → pita s.d. 3% **×0,8**; tarif artikel **Rp 500** | 120,69 × 500 × 0,8 × 1 = **Rp 48.276** | 48.276 · "Tarif artikel (PT ini)" · ×0,8 · "2,4% di bawah harga acuan" | Rp 48.276 · "tarif Rp 500/yard (Tarif artikel (PT ini)) · harga ×0,8 · 2,4% di bawah harga acuan · capaian ×1" |
| SO-00035 HITAM: 117,8 yd, dibayar separuh → 58,9 yd; harga khusus → **×0,5**; tarif varian **Rp 800** | 58,9 × 800 × 0,5 × 1 = **Rp 23.560** | 23.560 · "Tarif varian (PT ini)" · ×0,5 · "Harga khusus, memakai pengali tetap" | Rp 23.560 · "tarif Rp 800/yard (Tarif varian (PT ini)) · harga ×0,5 · …" |
| Batas margin 50% (tidak mengikat) | SO-00034: 50% × (24.400 − 18.000) × 120,69 = 386.208; SO-00035: 50% × (18.000 − 14.400) × 58,9 = 106.020 | `capped: false` | tanpa "dibatasi" |
| Pengali capaian | mati (bawaan) → ×1 | `factor 1, alasan "mati"` | "capaian ×1" / "×1" |
| **Total** | **Rp 71.836** | `mtd 71.836` | "Komisi berjalan Rp 71.836" · "Total Komisi (akrual MTD) Rp 71.836" |

Simulasi (tarif percobaan artikel DENIM TENCEL Rp 600): **Sekarang Rp 71.836 · Dengan perubahan Rp 1.162.805** =
1.802,19 yd × 600 × 1 (15 pesanan latihan DENIM TENCEL TAUPE yang dibayar November dan dipotret **tanpa tarif** saat aplikasi menyala —
tidak berkomisi sekarang) + 120,69 × 600 × 0,8 = 57.931,20 + 58,9 × 800 × 0,5 = 23.560 (pengecualian varian tetap
menang atas tarif artikel percobaan) → 1.162.805,20 ✔.

Tidak ada galat halaman (`pageerror`) atau jawaban 5xx selama uji layar.

### 4.3 Tangkapan layar

| Berkas | Isi |
|---|---|
| `00_ikhtisar_tab_skema_tarif.png` | Ikhtisar tab: sumber insentif (komisi otomatis), awal pohon tarif |
| `01_pohon_tarif_sampai_varian.png` | Pohon Woven → DENIM TENCEL → empat varian (ikut artikel Rp 500 / HITAM Rp 800 tarif sendiri) |
| `02_popup_tarif_artikel.png` | Pop-up "Atur tarif artikel DENIM TENCEL" (Berlaku untuk, tarif, batas margin, pengali khusus artikel) |
| `03_pratinjau_excel.png` | Pratinjau unggah Excel berstatus (2 baru · 38 sama · 0 galat) |
| `04_simulasi.png` | Tabel simulasi Sekarang vs Dengan perubahan |
| `05_kartu_insentif_saya_rincian.png` | Kartu sales: rincian komisi otomatis per artikel dengan tiap faktor |
| `06_beranda_sales_rincian_per_artikel.png` | Beranda Sales: "Rincian Komisi per Artikel" |
| `07_pengali_harga_tersimpan.png` | Bagian 3–4 sesudah disimpan (Khusus Sukacita) |

## 5. Perbaikan di KA-11 (temuan uji penuh, gate, uji layar)

| Commit | Temuan | Perbaikan |
|---|---|---|
| `3302c1f` | tests_mem PRT6 U4 merah (KA-9) | syarat aksi menu `hrd`/`hr-kpi-hub`/`incentive-scheme` tanpa `credit_override`; fixture akses frontend dibuat ulang |
| `576e06f` | Pemeriksaan registri: `commission_period_rules` memakai awalan `cpr_` milik `credit_profile_requests` | awalan `cmpr_`; ENTITY_REGISTRY dilengkapi |
| `5724afa` | Gate: `kaSkemaTarif.test.js` 897 baris > batas keras 760 | dipecah menjadi `kaSkemaTarif.test.js` + `kaSkemaTarifLanjutan.test.js` |
| `5d3a58d` | Uji layar: dua baris DENIM TENCEL bertarif beda tanpa sebab — asal tarif (`rate_origin`) dikirim server tetapi tidak ditulis | kartu & beranda menulis "Tarif artikel (PT ini)" / "Tarif varian (PT ini)"; catatan "dibatasi" beranda memakai kelas token (`verify_ui_standard` 114 → 112 = `d7b367b`) |
| `02dd913` | Uji layar: kolom yard simulasi hanya sisi kiri (179,59) padahal kolom kanan dihitung dari 1.981,78 yard | "179,59 → 1.981,78" (satu angka bila sama) |

## 6. Catatan untuk pemilik

1. **Kesetaraan "Semua PT"** — PT yang tidak mengubah apa pun mendapat komisi sama persis per PT. Tampilan gabungan
   "Semua PT" untuk PT yang punya tarif/pengaturan sendiri bisa berbeda dari sebelum rilis, karena tiap baris memakai
   aturan PT pesanannya (rancangan 6.5a); pengali capaian di "Semua PT" selalu ×1,0.
2. **Galat komisi di gaji ditelan** (sudah ada sebelum fitur ini): `hr_payroll_service._commission_for` (±347) mengubah
   galat `compute_commission` menjadi 0. Dengan pengali capaian **menyala**, galat pengumpul Capaian bisa membuat komisi
   di slip 0 tanpa pesan. Bawaan mati → tidak ada titik gagal baru sampai pemilik menyalakannya.
3. **Jurnal akrual yang dibalik** (reverse) tetap berstatus terposting, jadi potret aturan bulannya tetap berlaku; potret
   hanya diganti bila jurnal akrual **dianulir**, dan tidak ada jalur anulir aplikasi untuk jurnal akrual. Mengoreksi
   aturan bulan yang sudah diakrualkan butuh keputusan/jalur tersendiri.
4. **Tarif tidak berlaku mundur** — terlihat di data acuan: 15 pesanan latihan DENIM TENCEL yang dibayar November
   dipotret tanpa tarif saat aplikasi menyala, jadi tetap tanpa komisi walau tarif Woven dibuat sesudahnya. *(Diperbaiki
   di bagian 7, R18: simulasi kini membandingkan "Aturan sekarang" vs "Dengan perubahan" yang sama-sama mengabaikan potret,
   jadi selisihnya murni efek perubahan; angka yang dibayar tampil sebagai baris info.)*
5. **Sakelar PT nyata (H5)** — sumber insentif "Keduanya dibayar", nilai pita/pengali, dan tarif untuk PT nyata diisi
   pemilik di layar; bawaan = tanpa perubahan perilaku.
6. Teks konfirmasi pengaturan tabel menulis "Dari 3 baris menjadi 3 baris" (pesan umum Pusat Pengaturan, bukan fitur
   ini) — kurang menjelaskan apa yang berubah.
7. Tab memuat bagian 3–5 beberapa detik ("Memuat pengaturan…"): tiap bagian tertanam memanggil `/api/config/registry`
   dan `/api/config/health` sendiri (terlihat 4× di uji layar). Belum diukur di produksi.

## 7. Gelombang perbaikan tinjauan akhir (ledger R18/R19, 23 Nov 2026)

Tinjauan akhir seluruh cabang (`d7b367b..03a72a5`): lima temuan penting (I1–I5) dan minor M1–M7, T7, T9 — semuanya
dikerjakan, masing-masing dengan uji. Keputusan yang mengubah perilaku dicatat di rancangan §8 butir 25–32.

### 7.1 Temuan → perbaikan → uji

| Temuan | Perbaikan (commit) | Uji |
|---|---|---|
| I1 baris pesanan lama ber-kategori kosong diberi kategori produk lalu dibekukan isi awal | `commission_rules.kategori_baris`: kunci `category` ada (juga kosong) → dipakai apa adanya (mesin lama), tidak ada → kategori produk; di isi awal dan jalur baca tanpa potret; pesanan baru tetap kategori produk (`bcfb5f0`) | `test_KA12_mesin_akhir` I1/I1b: baris "" → potret tanpa tarif, komisi hanya baris lain 100 × 500 = 50.000 (sebelum = sesudah isi awal) |
| I2 pembekuan menghitung ulang semua sales di dalam posting gaji; galat satu sales menggagalkan posting | aturan capaian dibekukan dulu; `sales[]` = catatan: posting gaji → komisi slip yang diakru (mesin tidak dipanggil), akrual manual → mesin sekali per sales (`incentive_accrual_rincian`, total jurnal = catatan), cadangan hitung ulang → tanda `galat` per sales; catatan tidak pernah menggagalkan akrual (`bcfb5f0`) | KA12 I2: mesin Budi dipaksa galat → posting gaji 200, akrual 650.000, potret ada, catatan dari slip (Andi 550.000 · Budi 100.000), mesin dipanggil 0×; I2b: tanda galat Budi; I2c: akrual manual = 1× mesin per sales, total 20.000 = catatan |
| I3 simulasi mencampur efek draf dengan efek potret (R18) | dua kolom tanpa potret ("Aturan sekarang" atas indeks tersimpan, "Dengan perubahan" atas indeks + draf, aturan PT sama) + `komisi_menurut_potret` + `tanda` (strategi berjenjang, mode sheet/off) (`fb2dc01`, layar `df96fc4`) | KA8 U7: potret 3.500, tarif kini 3.800 → 380.000 vs 400.000, info 350.000, tanda kedua kasus; jest simulasi (kolom, selisih per baris & total, baris info, tanda) |
| I4 teks Excel "3.500" terbaca Rp 3,5; batas margin tanpa batas atas | sel teks cara Indonesia (titik ribuan, koma desimal; "3,500"/"3.5"/"Rp 3.500" = galat berkalimat); batas margin 0–100 di `periksa_isian` (Excel, POST, ubah banyak, terap) (`00b5965`) | KA12 I4: "3.500" → 3.500 · "3.500,5" · "3,5" · sel angka 3.500 sama; tiga teks ragu galat; batas 150 → galat di pratinjau, 400 di tiga rute |
| I5a PATCH tanpa validasi | dokumen gabungan selalu divalidasi (angka & batas registri, pilihan diskon, status aktif/nonaktif, pita) (`00b5965`) | KA12 I5: sembilan isian salah → 400 berkalimat, tidak ada yang tersimpan; isian sah → 200 |
| I5b daftar tarif terpotong 1.000 baris → pita artikel terhapus diam-diam | `GET /api/incentive-rates/{id}` (PT di luar penugasan = 404); daftar tanpa batas; pop-up membaca per id, tidak terbaca = terkunci, pita tidak dikirim (`00b5965`, `df96fc4`) | KA12 I5b: 1.006 tarif Semua PT → daftar memuat semuanya; baca per id + 404; jest I5: 404 → terkunci, PATCH tanpa `price_bands` |
| M1 isi awal sebelum tarif bawaan | `run_bootstrap`: isi awal sesudah `seed_incentive_rates` (`bcfb5f0`) | KA12 M1: basis data tanpa tarif + pesanan Batik lama → `run_bootstrap` → potret memakai tarif bawaan Semua PT |
| M2 isi awal tidak tahan galat, kueri per pesanan | per kelompok 200 (satu kueri produk & artikel per kelompok), pesanan/tarif/PT rusak dicatat log & dilewati, tetap idempoten (`bcfb5f0`) | KA12 M2: tarif `"abc"` → pesanan itu dilewati + peringatan bernomor, lainnya terpotret; baris bukan objek dilewati; 5 pesanan/5 produk, kelompok 2 → 3 kueri produk; ulang tidak menulis |
| M3 tarif tunggal tanpa cek PT; "Semua PT" tanpa kemampuan lintas PT | `_boleh_lingkup`: PT dalam penugasan; `"all"` hanya `is_cross_entity` (= `caps.global_write`), 403 berkalimat; layar menyembunyikan "Semua PT" & tombol ubah/hapus tarif grup (`00b5965`, `df96fc4`) | KA12 M3: peran satu PT → POST/PATCH/DELETE grup & PT lain 403; jest M3 (pop-up & daftar Semua PT) |
| M4 POST ke tarif nonaktif → 409 | diaktifkan & diubah dengan isian yang dikirim, jejak audit (`00b5965`) | KA12 M4: id sama, aktif, 750, batas 30 tetap; aktif → 409 |
| M5 petunjuk pita artikel | "Pita hanya dipakai bila dasar pengali harga PT ini = Selisih dari harga acuan." (`df96fc4`) | jest M5 (diskon_baris → tampil, pricelist → tidak) |
| M6 kalimat hapus menyebut pengganti yang salah | server mengirim `fallback` (tarif yang berlaku bila tarif PT itu dihapus) di kategori/artikel/varian; kalimat dari situ (`fd99ac0`, `df96fc4`) | KA12 M6 (kategori → Semua PT 700, artikel → artikel Semua PT 1.100 lalu kategori PT 900, varian → artikel PT 1.200, tanpa tarif); jest M6 |
| M7 tarif baru membawa bawaan diskon tertulis | `RatePayload` diskon/batas `None`; isian diskon kosong tidak disimpan → potret memakai kunci PT; batas kosong → bawaan PT (`00b5965`) | KA12 M7: tarif baru tanpa kunci diskon, ambang PT 5 → potret 5; tarif lama → 10; bawaan registri = bawaan lama; KA8 F5 kini 200.000 (ambang PT) |
| T7 uji akrual ganda | KA7 U4 dipindah sebelum gaji: akrual manual 500.000; sesudah gaji tidak ada `incentive_accrual_adj` (`8d32549`) | KA7 6 passed |
| T9 tautan dalam menulis kunci mentah sebagai istilah cari | `useSettingsBrowser({ focusWithoutSearch })` di bagian tertanam (`df96fc4`) | jest T9 (q kosong, kartu terbuka & disorot; layar biasa tetap) |

Uji terarah sesudah perbaikan: KA1–KA8, KA12 (dua berkas), KMT4, KMT5, PK14, PK22, PK40, PRT2 (2), latih variasi gaji —
**161 passed**; jest KA + Pengaturan + kartu sales (11 suite) **105 passed**; `verify_ui_standard` 112 = sebelum.

### 7.2 Bukti anti-tujuan 1 — mesin lama (`d7b367b`) vs kepala, data acuan `final_seed3.gz`

Skrip `scripts/komisi/banding_mesin_komisi.py` (hanya membaca). Urutan tiap putaran (basis data `test_database` di
`kn-mongo`, backend dihentikan saat skrip berjalan):

```bash
# pulihkan data acuan, nyalakan backend d7b367b SEKALI (proses awal versi lama = keadaan produksi sebelum rilis), hentikan
git worktree add --detach $S/wt_d7b d7b367b
docker exec kn-mongo mongosh --quiet test_database --eval 'db.dropDatabase().ok'
docker exec kn-mongo mongorestore --quiet --archive=/tmp/x.gz --gzip
(cd $S/wt_d7b/backend && python -m uvicorn server:app --host 127.0.0.1 --port 8001 &) ; …tunggu /api/ 200… ; be_stop
python scripts/komisi/banding_mesin_komisi.py hitung --backend $S/wt_d7b/backend --keluaran lama.jsonl --akhir 2026-11
be_start; be_stop        # kode kepala menyala sekali: isi awal potret pesanan lama (46 pesanan, 52 baris "isi_awal")
python scripts/komisi/banding_mesin_komisi.py hitung --backend backend --keluaran baru.jsonl --daftar lama.jsonl
python scripts/komisi/banding_mesin_komisi.py banding lama.jsonl baru.jsonl
```

Hitungan per putaran: 3 PT × sales daftar PT × 12 bulan (Des 2025–Nov 2026) + triwulan & tahun = **76 baris**.

| Putaran | Penyiapan sesudah proses awal versi lama | Bukan nol | Beda | Hanya satu sisi |
|---|---|---:|---:|---:|
| (a) data acuan apa adanya | — (tarif acuan hanya kategori Batik/Endek/…; baris pesanan Knitting/Woven → semua 0) | 0 | **0** | 0 |
| (b) tarif kategori berbentuk lama | API lama: tarif PT `ent_d0073be24630` Woven 550 + `ent_kanda` ambang diskon 3 & batas 40; disisip: Semua PT Woven 500 (bawaan seed), KSC Knitting 700 dengan batas & ambang **null**, Kanda Woven 650 potong Rp 100 per ambang Rp 1.000, KSC Woven 450 **tanpa** isian diskon/batas, Kanda Knitting 900 **nonaktif**, Semua PT Knitting 800 batas 0 hangus di atas 5 % | 12 | **0** | 0 |
| (c) pengaturan PT + tarif tanpa isian | API lama: Kanda ambang 3 · batas 40; KSC potong Rp 150 di atas 1 %; disisip tarif tanpa isian diskon/batas (Kanda Woven 650, KSC Woven 450, Semua PT Knitting 800), Kanda Knitting 900 batas null, Semua PT Woven 500 ambang 0 | 12 | **0** | 0 |

Contoh angka (b) Nov 2026: `ent_ksc` les_01 total 810.985,50 / proyeksi 1.629.684 · dc1c32 173.163,60 / 432.909 ·
`ent_d0073be24630` afea5e 96.728,01 / 653.371,50 · `ent_kanda` 2d9bcf 0 / 1.964.120. Putaran (c) mengubah proyeksi
(611.561 dan 2.209.635) — pengaturan PT memang terbaca — dan tetap identik lama vs baru. **Semua 228 baris identik**
(`total_incentive` dan `projection_full`), keluar 0; uji-diri pembanding: satu sen diubah → 3 baris BEDA, keluar 1.
Batas bukti: data acuan kecil (46 pesanan, 18 pembayaran, semua November); tidak ada baris berkategori kosong (I1 diuji di
`tests_mem`); pengali capaian mati. Worktree sementara dihapus sesudahnya.

### 7.3 Pemeriksaan sebelum rilis (produksi / salinan produksi)

Semua hanya membaca kecuali butir 3 (di **salinan**).

1. **Calon kembar indeks unik & tarif rusak** — `mongosh <db_produksi> scripts/komisi/prarilis_tarif.js`: mencetak
   `KEMBAR uq_incentive_rate_key` (dua tarif PT·kategori yang sama sesudah spasi tepi dibuang — isi awal `rate_key` lalu
   indeks unik wajib akan menolak, aplikasi tidak menyala), `TARIF RUSAK / DI LUAR BATAS` (isian bukan angka mematahkan
   potret pesanan; nilai di luar batas membuat ubah tarif ditolak sampai dibetulkan), jumlah pesanan yang akan dipotret,
   dan baris berkategori kosong. Harus **0 · 0** sebelum memasang. Pembuktian di data acuan: 0 · 0 · 0 · 0; di basis
   data uji bercacat: 1 · 2 · 1 · 1.
2. **Pembanding mesin** — di **salinan** produksi, langkah 7.2 (backend lama = versi yang sedang jalan di produksi): beda
   harus 0. Beda apa pun = jangan pasang; periksa baris yang disebut.
3. **Waktu isi awal** — di **salinan** produksi: `cd backend && DB_NAME=<salinan> python -c "import asyncio,time,bootstrap;
   t=time.time(); asyncio.run(bootstrap.backfill_so_line_commission_rule()); print(time.time()-t)"`. Ukuran di sini
   (kn-mongo, 4 inti): data acuan ×435 = **20.056 pesanan / 22.672 baris → 20,4 dtk**, ulang (idempoten) 0,03 dtk. Aplikasi
   pertama kali menyala sesudah rilis selama itu lebih lama.
4. Sesudah memasang: log backend tanpa `[KA-4] potret komisi … dilewati` (bila ada: pesanan/tarif yang disebut dibetulkan,
   aplikasi menyala lagi memotretnya).

### 7.4 Uji penuh & gate pada pohon akhir

**tests_mem** (sekali, pohon `a29366b` = kode akhir; sesudahnya hanya uji jest, skrip, dan dokumen):
`python -m pytest backend/tests_mem -n 0 -q -p no:cacheprovider` →

```
2697 passed, 2 skipped, 3 xfailed, 12 warnings in 887.30s (0:14:47)
```

**jest** (pohon `a29366b`): `Test Suites: 2 failed, 238 passed, 240 total · Tests: 2 failed, 1818 passed, 1820 total`.
- `tzTanggalBawaan.test.js` — kendala zona waktu lingkungan yang sama dengan bagian 2.2 (dengan `env -u TZ` → 3 passed).
- `kaSkemaTarifLanjutan.test.js` › "KA9 LegacySchemeEditor tanpa isian Bonus per produk fokus" — **cabang ini**: akar React
  uji sebelumnya (mesin pengaturan asli) masih terpasang dan menggambar ulang sesudah tiruan pengaturan berganti; muncul
  karena bagian 3 kini meneruskan kemampuan/dasar harga ke induk (render tambahan). Uji terarah lulus; hanya jest penuh
  (lambat, banyak pekerja) yang menangkapnya. Diperbaiki `31061b2` (akar dilepas tiap uji, tiga berkas KA).
- Jest penuh diulang sesudah perbaikan (pohon `31061b2`, ±40 dtk): `Test Suites: 1 failed, 239 passed, 240 total ·
  Tests: 1 failed, 1819 passed, 1820 total` — sisa merah hanya `tzTanggalBawaan` (lingkungan).

**Gate** (`gate_ci` = `bash scripts/gate.sh --ci`, pohon `02b392d` + dokumen bagian ini belum di-commit; backend kepala
dinyalakan di data acuan yang baru dipulihkan, penjadwal fakta sudah berjalan sekali sebelum gate; 412 dtk): **ADA GATE
MERAH**, sama dengan garis dasar — **37 merah · 106 hijau** dihitung dengan cara yang sama pada `gate_akhir2.log` (main
`686befe`): 37 · 106.

```
$ python3 scripts/blueprint/bandingkan_pelanggaran_gate.py gate_akhir2.log gate_last_ci.log
== finance: garis dasar 2 · sekarang 0 · baru 0 · hilang 2
== manager: garis dasar 4 · sekarang 2 · baru 0 · hilang 2
== sales: garis dasar 5 · sekarang 4 · baru 0 · hilang 1
== sales_admin: garis dasar 6 · sekarang 5 · baru 0 · hilang 1
HASIL: tidak ada pelanggaran baru
```

Pemeriksaan tangan atas baris `❌`/`[FAIL]` (pembanding hanya membaca `✗`): kedua log dinormalkan (warna dibuang, angka →
`#`), lalu dibandingkan per baris beserta jumlah kemunculannya — **71 baris jenis di kedua log, isi dan jumlah sama
persis**, tidak ada yang baru. `validate_compliance` 39 PASS · 1 FAIL (`frontend/.env` tidak ada = garis dasar); POC E-7
residu PASS ("nol residu", 0); pembanding lama `bandingkan_gate.py` (garis dasar 13 Nov) tetap menulis "LEBIH MERAH: POC
Cek Kenyataan Peran, POC FASE N" — keduanya sudah merah di `gate_akhir2` (main).


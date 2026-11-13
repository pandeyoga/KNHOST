# KM-T2 — Bangun layar Capaian: cari, telusur, dan jumlahkan angka dasar insentif per sales

| | |
|---|---|
| Gelombang | Modul — Meja Insentif |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | KM-T1, PK-41 |
| Menutup temuan | — |
| Keputusan | K-19, K-20, K-21, K-23, K-24 |
| Standar | §2.2, §3.1 (Z1, Z2, Z6), §3.2, §3.4 (N3), §4 (L1–L4, L6, L7, L8), §5 (D3, D4, D5), §6 |
| Lingkungan uji | B untuk angka dan izin; layar (uji jalan) di A |

## Tujuan

Pemutus insentif membuka satu layar, memilih PT dan periode, lalu melihat per sales: target dan capaian omzet, target
dan capaian pencairan, serta kualitas harga jual. Setiap angka bisa dibuka sampai dokumennya, dan baris yang dicentang
dijumlahkan di layar. Layar ini hanya membaca; ia tidak menghitung dan tidak menyimpan nominal insentif.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

- Layar yang ada menampilkan satu sales per tampilan, dengan angka berdasar tanggal pesanan dan pemilik pelanggan:
  `frontend/src/features/crm/SalesForceDashboard.jsx:116` (`sf-kpi-sales`). Papan peringkatnya lima kolom tanpa target:
  `frontend/src/features/crm/SalesForceDashboard.jsx:182` (`Pencairan`). Tidak ada angka yang bisa dibuka ke dokumen.
- Wewenang layar itu ditentukan nama peran: `frontend/src/features/crm/SalesForceDashboard.jsx:16` (`roleIs`); di
  server: `backend/routers/crm.py:254` (`role_in`) dan `backend/routers/crm.py:268` (`require_role`).
- Papan peringkat hanya memuat akun berperan persis `sales`: `backend/services/sales_force_service.py:456`
  (`leaderboard`).
- Piutang per pelanggan milik seorang sales, per tanggal tertentu, sudah tersedia:
  `backend/services/ar_aging_service.py:177` (`aging_report`).
- Dokumen sumber punya endpoint baca sendiri: surat jalan `backend/routers/outbound_picking_extra.py:30`
  (`shipment_surat_jalan`), kwitansi `backend/routers/ar_receipts.py:134` (`get_receipt`), pesanan
  `backend/routers/sales_orders.py:726` (`get_order`).
- Ekspor Excel sudah punya pola (pustaka `openpyxl`, pengaman rumus di sel): `backend/routers/finance_analytics.py:57`
  (`Workbook`), `backend/routers/finance_analytics.py:66` (`_cell`).
- Hub tujuan saat ini berisi satu tab: `frontend/src/config/hubTabs.js:202` (`hr-kpi-hub`); entri menunya berlabel
  "KPI": `frontend/src/config/navStructure.js:361` (`hr-kpi-hub`).

Yang disediakan KM-T1 dan dipakai di sini: `fact_shipment_sales`, `fact_collections`, `sales_targets` berkunci PT,
`current_definition`, `period_bounds`, `sales_roster`, `ensure_fresh`, dan endpoint rekonsiliasi.

## Perubahan

### Data

Tidak ada koleksi baru. Tampilan tersimpan (saringan, pengelompokan, kolom) disimpan di peramban per pengguna
(`localStorage`, kunci `kn.capaian.tampilan.<id pengguna>`), bukan di server.

### Server

Berkas baru `backend/services/incentive_achievement.py`; endpoint ditambahkan ke `routers/incentive.py` (lahir di KM-T1).
Semua endpoint: PT dari konteks pengguna; saat "Semua PT" → 400 "Pilih satu PT untuk melihat Capaian. Definisi angka
berbeda di tiap PT." Sebelum membaca, panggil `ensure_fresh(60)`.

**`GET /api/incentive/achievement`** — izin `incentive.view`.

| Parameter | Isi |
|---|---|
| `period_type`, `period` | `month` + `YYYY-MM` · `quarter` + `YYYY-Qn` · `year` + `YYYY` · `range` + `date_from`, `date_to` (WIB) |
| `compare` | `none` (bawaan) · `prev` (periode sebelumnya) · `yoy` (periode sama tahun lalu) |
| `cumulative` | `true` hanya untuk `month`: awal tahun buku PT s.d. akhir bulan itu; target = Σ target bulanan dalam rentang |
| `group_by` | `sales` (bawaan) · `customer` · `category` · `price_source` |
| `sales_id[]`, `customer_id`, `category`, `line_code`, `price_source` | Saringan |

Jawaban: `{entity_id, period: {type, key, label, date_from, date_to}, definition: {version, effective_from,
dasar_omzet, isi_pencairan, pemilik_angka, harga_acuan, labels}, facts_as_of, reconciliation: {omzet_ok, omzet_diff,
pencairan_ok, pencairan_diff}, rows[], totals, compare: {label, by_key}}`. Satu baris per sales dari `sales_roster`
ditambah baris `sales_id: ""` berlabel "Tanpa sales" bila ada angkanya:

| Field baris | Cara menghitung |
|---|---|
| `target_sales`, `target_collection` | `sales_targets` PT itu untuk (jenis periode, periode); 0 bila belum diisi |
| `omzet` | Menurut `dasar_omzet`. `terkirim`: Σ `net` jenis `kirim` + `pesanan_lama` bertanggal dalam periode. `pesanan`: Σ `fact_sales_lines.net_alloc` pesanan hidup bertanggal pesanan dalam periode. `lunas`: Σ `net_alloc` pesanan yang baris `settles_order`-nya bertanggal dalam periode |
| `retur` | −Σ `net` jenis `retur` + `koreksi` dalam periode (ditampilkan positif) |
| `omzet_bersih`, `pct_omzet` | `omzet − retur`; `omzet_bersih ÷ target_sales × 100`, satu desimal; `null` bila target 0 |
| `uang_masuk`, `pct_pencairan` | Σ `fact_collections.amount` dalam periode. `uang_masuk`: jenis `kas`, `deposit`, `titipan_bank` termasuk pembaliknya; `semua_baris`: semua jenis. Persen = `uang_masuk ÷ target_collection × 100` |
| `sisa_piutang`, `lewat_tempo` | `aging_report(entity_id, sales_id, as_of = akhir periode)`: total dan bagian lewat jatuh tempo pelanggan yang kini dipegang sales itu |
| `realisasi_harga_pct` | Σ `net` ÷ Σ nilai acuan × 100 atas baris `kirim` yang nilai acuannya terisi; nilai acuan = `list_value`, `global_value`, atau `floor_value` menurut `harga_acuan` |
| `rata_potongan_pct`, `porsi_bawah_acuan_pct` | `100 − realisasi_harga_pct`; Σ `net` baris yang `net` < nilai acuan ÷ Σ `net` baris ber-acuan × 100 |
| `margin_pct` | (Σ `net` − Σ `cost`) ÷ Σ `net` × 100 atas baris `cost_known`. **Hanya dikirim bila pelaku memegang `incentive.view_margin`** |
| `pelanggan_baru`, `jumlah_pesanan` | Pelanggan PT itu yang dibuat dalam periode dan dipegang sales itu; banyaknya `so_id` berbeda pada baris omzet |
| `catatan_data[]` | `{code, count, text}`; teks: "{n} baris tanpa harga acuan", "{n} baris tanpa biaya, tidak ikut hitungan margin", "{n} kwitansi giro belum dipastikan cair", "{n} baris kasus keuangan tidak dihitung sebagai uang masuk" |

Bila `pemilik_angka = pemilik_pelanggan`, baris fakta dikelompokkan menurut sales penanggung jawab pelanggan saat ini
(`customers.assigned_sales_id`), bukan `sales_id` di fakta. Untuk `group_by` selain `sales`, kolom target, piutang, dan
pelanggan baru tidak dikirim. Uang dibulatkan ke rupiah penuh di jawaban; `totals` = Σ baris (D5).

**`GET /api/incentive/achievement/sources`** — izin `incentive.view`. Parameter periode yang sama, `metric`
(`omzet` · `retur` · `uang_masuk`), `sales_id` (wajib; `""` = tanpa sales), `page`, `page_size` (≤ 200). Jawaban:
`{total, sum, items: [{doc_type, doc_id, doc_number, date_wib, customer_name, so_id, so_number, source_kind, split,
amount}]}` dengan `doc_type` `shipment` · `credit_note` · `ar_receipt` · `sales_order`. `sum` harus sama dengan angka sel
yang dibuka (D4: daftar berhalaman dengan jumlah total).

**`GET /api/incentive/achievement/export`** — izin `incentive.view`; parameter sama dengan endpoint pertama; jawaban
berkas `.xlsx` bernama `capaian-<kode PT>-<periode>.xlsx`. Lembar 1 **Definisi**: PT, periode dan rentang tanggalnya,
versi definisi dan tanggal berlakunya, empat definisi dengan label Indonesia, hasil pencocokan, waktu ekspor WIB, nama
pengekspor. Lembar 2 **Capaian**: kolom dan urutan sama dengan layar. Lembar 3 **Dokumen**: seluruh `items` omzet,
retur, dan uang masuk. Kolom margin hanya untuk pemegang `incentive.view_margin`. Isi sel teks lewat pengaman `_cell`.

Galat lain: 400 "Periode tidak sesuai jenisnya. Contoh: 2026-10, 2026-Q4, atau 2026." · 400 "Rentang tanggal paling
panjang 366 hari." · 403 bentuk Z6 dengan nama modul "Kinerja & Insentif".

### Pengaturan

Tidak ada kunci baru. Empat kunci `insentif.*` dari KM-T1 dibaca lewat `current_definition`.

### Izin dan peran

Aksi baru `incentive.view_margin` (label "Lihat margin") → admin, manager; diperiksa di tiga endpoint di atas (kolom
margin). Modul akses `incentive`: `nav` ditambah `incentive-capaian`. Tidak ada pemeriksaan nama peran di kode baru.

### Layar

Hub `hr-kpi-hub`, tab baru **Capaian** (view `incentive-capaian`) di urutan pertama. Komponen baru
`frontend/src/features/incentive/CapaianView.jsx` dan `frontend/src/features/incentive/CapaianSourcesPanel.jsx`.
Banner PT di atas; tidak ada tombol tulis.

- **Bilah saringan:** "Periode" (Bulan · Triwulan · Tahun · Rentang tanggal) dan pemilih nilainya; "Bandingkan dengan"
  (Tidak · Periode sebelumnya · Periode sama tahun lalu); sakelar "Kumulatif tahun berjalan"; "Kelompokkan menurut"
  (Sales · Pelanggan · Kategori produk · Sumber harga); kotak cari "Cari nama…"; tombol "Simpan tampilan" dan "Ekspor Excel".
- **Baris definisi** di bawah saringan: "Omzet: {label} · Pencairan: {label} · Milik: {label} · Harga acuan: {label} —
  berlaku sejak {tanggal} (versi {n})". Tiap judul kolom punya keterangan definisinya saat disorot.
- **Tabel**, judul kelompok dan kolom persis: **Omzet** — "Target", "Omzet", "% capaian", "Retur", "Omzet bersih";
  **Pencairan** — "Target", "Uang masuk", "% capaian", "Sisa piutang", "Lewat tempo"; **Kualitas harga** — "Realisasi
  harga", "Rata-rata potongan", "Di bawah harga acuan", "Margin"; **Lain** — "Pelanggan baru", "Pesanan", "Catatan data".
  Kolom pertama kotak centang dan nama sales. Persen satu desimal dengan koma ("86,2 %"); target 0 tampil "—". Saat
  pembanding aktif, di bawah angka omzet bersih dan uang masuk tampil selisihnya ("+Rp 480.000.000 dari Sep 2026").
- **Telusur:** klik angka "Omzet", "Retur", atau "Uang masuk" membuka panel samping berjudul "{kolom} — {sales} —
  {periode}" berisi "Tanggal", "Dokumen", "Pelanggan", "Pesanan", "Jenis", "Nilai", kotak centang per baris, dan
  "Jumlah Rp … dari {total} dokumen". Nomor dokumen membuka surat jalan, nota kredit, kwitansi, atau pesanan (L8).
- **Bilah jumlah pilihan** (menempel di bawah, muncul bila ada yang dicentang; dihitung di layar dari angka yang sedang
  tampil, tanpa permintaan ke server): "{n} baris dipilih · Omzet bersih: jumlah Rp … · rata-rata Rp … · Uang masuk:
  jumlah Rp … · rata-rata Rp …". Di panel telusur: "{n} dokumen dipilih · jumlah Rp … · rata-rata Rp …".
- **Peringatan** bila `omzet_ok` atau `pencairan_ok` salah: "Angka belum cocok dengan pembukuan (omzet selisih Rp …,
  pencairan selisih Rp …). Lihat rinciannya di tab Target & Aturan."
- Keadaan: memuat "Memuat capaian…"; galat lewat `ErrorNotice` "Capaian gagal dimuat."; kosong "Belum ada penjualan
  atau uang masuk pada periode ini."; kaki tabel "Data per pukul {HH:MM} WIB".

## Uji penerimaan

Fixture **F2** — contoh rancangan `05` §4.2, di `ent_kanda` (non-PKP, tahun buku kalender), disisipkan langsung lalu
`rebuild` fakta. Sales **Andi** dan **Budi**; semua harga jual Rp 50.000/yd, biaya Rp 35.000/yd.

| Dokumen | Isi |
|---|---|
| Target | Andi `2026-10`: omzet 800 jt, pencairan 750 jt · Andi `2026-Q3`: 2.400 jt, 2.250 jt · Budi `2026-10`: 500 jt, 450 jt |
| OA0 (Andi) | 52.000 yd = Rp 2.600.000.000, `list_price` 56.800, dibuat 3 Agu, terkirim penuh 14 Agu 2026 |
| OA1 (Andi) | 20.000 yd = Rp 1.000.000.000, `list_price` 58.000, dibuat 28 Sep, terkirim penuh 12 Okt 2026 |
| OB0 (Budi) | 400 yd = Rp 20.000.000, `list_price` 50.000, terkirim 20 Sep 2026 |
| OB1 (Budi) | 10.000 yd = Rp 500.000.000, `list_price` 50.000, terkirim 9 Okt 2026 |
| Kwitansi | RA0 10 Sep Rp 2.300.000.000 → OA0 · RA1 20 Okt Rp 700.000.000 → OA1 · RB1 15 Okt Rp 500.000.000 → OB1 · RB0 16 Okt Rp 20.000.000 → OB0 |

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | F2 | `GET …/achievement?period_type=month&period=2026-10`, baris Andi | `target_sales` 800.000.000; `omzet` 1.000.000.000; `retur` 0; `pct_omzet` 125,0 (1.000 ÷ 800); `uang_masuk` 700.000.000; `pct_pencairan` 93,3 (700 ÷ 750 = 93,33) |
| U2 | B | F2 | Sama, kualitas harga Andi | `realisasi_harga_pct` 86,2 (1.000 ÷ 1.160; nilai acuan = 1.000 jt × 58.000 ÷ 50.000); `rata_potongan_pct` 13,8; `porsi_bawah_acuan_pct` 100,0; `margin_pct` 30,0 ((1.000 − 700) ÷ 1.000) |
| U3 | B | F2 | Sama, baris Budi | `omzet` 500.000.000; `pct_omzet` 100,0; `uang_masuk` 520.000.000 (500 jt + 20 jt); `pct_pencairan` 115,6 (520 ÷ 450 = 115,56); `realisasi_harga_pct` 100,0; `porsi_bawah_acuan_pct` 0,0 |
| U4 | B | F2 | `period_type=quarter&period=2026-Q3`, baris Andi | `target_sales` 2.400.000.000 (bukan jumlah bulanan); `omzet` 2.600.000.000; `pct_omzet` 108,3; `uang_masuk` 2.300.000.000; `pct_pencairan` 102,2; `realisasi_harga_pct` 88,0 (2.600 ÷ 2.953,6) |
| U5 | B | F2 | `…/sources?metric=uang_masuk&sales_id={Budi}&period=2026-10` | `total` 2; `sum` 520.000.000; dua kwitansi RB1 dan RB0; `sum` = `uang_masuk` U3 |
| U6 | B | F2 | `…/sources?metric=omzet&sales_id={Andi}&period=2026-10` | Satu surat jalan Rp 1.000.000.000, `doc_type` `shipment` |
| U7 | B | F2 | `compare=prev`, baris Budi | `compare.by_key[Budi].omzet_bersih` 20.000.000 (September) |
| U8 | B | F2; `insentif.dasar_omzet` = `pesanan` untuk `ent_kanda` | Oktober dan September, baris Andi | Oktober `omzet` 0; September 1.000.000.000 (OA1 dibuat 28 Sep); `definition.version` naik 1 |
| U9 | B | F2; nota kredit retur Rp 50.000.000 atas OA1 bertanggal 25 Okt | Oktober, baris Andi | `retur` 50.000.000; `omzet_bersih` 950.000.000; `pct_omzet` 118,8 (950 ÷ 800 = 118,75) |
| U10 | B | F2; `cumulative=true` untuk `2026-10` | Baris Andi | `omzet` 3.600.000.000 (2.600 + 1.000); `target_sales` 800.000.000 (hanya target bulanan yang ada dalam rentang) |
| U11 | B | Peran Tanpa Acuan ber-`incentive.view` saja | `GET …/achievement` | 200; tidak ada kunci `margin_pct` di baris mana pun |
| U12 | B | Peran Manajer Kosong; Sopir | `GET …/achievement`; `…/sources`; `…/export` | 403 semuanya, pesan bentuk Z6 |
| U13 | B | Admin dengan "Semua PT" | `GET …/achievement` | 400 "Pilih satu PT untuk melihat Capaian. Definisi angka berbeda di tiap PT." |
| U14 | B | F2 | `…/export` Oktober; buka dengan `openpyxl` | Tiga lembar "Definisi", "Capaian", "Dokumen"; sel omzet Andi 1000000000; lembar Definisi memuat "terkirim" dan nomor versi |
| U15 | B | F2 + akun berperan kustom beracuan `sales` dengan satu pesanan terkirim | Oktober | Akun itu muncul sebagai baris |
| U16 | layar (uji komponen) | Data U1 dan U3 | Centang Andi dan Budi | Bilah: "2 baris dipilih · Omzet bersih: jumlah Rp 1.500.000.000 · rata-rata Rp 750.000.000 · Uang masuk: jumlah Rp 1.220.000.000 · rata-rata Rp 610.000.000"; tidak ada permintaan jaringan baru |
| U17 | layar (uji jalan) | F2, login manager | Buka Kinerja & Insentif › Capaian; klik uang masuk Budi; klik nomor RB0 | Panel menampilkan dua kwitansi berjumlah Rp 520.000.000; kwitansi terbuka |

Catatan: rancangan menulis realisasi harga Andi "86 %" dan "88 %"; dengan omzet bulat nilainya 86,2 % dan 88,0 %.

## Langkah kerja

1. `backend/tests_mem/test_KMT2_capaian.py`: fixture F2 dan U1–U15; merah karena endpoint belum ada.
2. `incentive_achievement.py`: pengumpul baris per sales, lalu saringan, pembanding, kumulatif, pengelompokan.
3. Endpoint telusur dan ekspor; izin `incentive.view_margin`; pesan galat.
4. Layar: tab, tabel, panel telusur, bilah jumlah pilihan (uji komponen U16), simpan tampilan, ekspor.
5. Uji jalan U17 dengan tangkapan layar; gate; laporan memuat tabel hitung tangan F2.

## Dokumen ikut berubah

`CODEBASE_MAP.md` (satu berkas server, dua komponen); `memory/PRD.md`; `docs/KN_13_NAVIGATION_MAP.md` (tab Capaian);
`docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("capaian", "realisasi harga", "omzet bersih").

## Di luar lingkup

- Tombol "Buat lembar insentif dari tampilan ini" dan potret angka → KM-T3.
- Menghapus layar Kinerja Sales dan endpoint `/api/sales/kpi`, `/api/sales/leaderboard` → KM-T5.
- Saringan kanal penjualan (pesanan tidak menyimpan kanal) dan tampilan tersimpan lintas perangkat tidak dibangun.
- Perbaikan umur piutang dan profitabilitas → PK-41. Pencocokan satu bulan nyata dengan rekap manual pemilik
  (rancangan `05` §9) dilakukan pemilik setelah unit ini selesai; hasilnya syarat melepas H5 pada KM-T4.

## Asumsi dan risiko

- `ASUMSI:` "% capaian" omzet memakai omzet bersih (setelah retur), mengikuti K-19.
- `ASUMSI:` sisa piutang dan lewat tempo memakai pemilik pelanggan saat ini (cara `aging_report`), walau omzet memakai
  sales pada pesanan; keterangan kolom menuliskannya: "Piutang pelanggan yang kini dipegang sales ini, per {tanggal}."
- `ASUMSI:` tampilan tersimpan cukup di peramban; ekspor memakai izin `incentive.view` (tanpa aksi ekspor tersendiri).
- `RISIKO:` periode panjang lambat karena agregasi fakta. Penangkal: indeks (`entity_id`, `sales_id`, `date_wib`) dari
  KM-T1 dan batas rentang 366 hari. Membatalkan: cabut tab dan tiga endpoint; tidak ada data yang ditulis.

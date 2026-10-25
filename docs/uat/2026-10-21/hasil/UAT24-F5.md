# UAT 24 Okt — F5 (layar & fitur: P7 Perbaikan · P12 sorotan POS · P13 · P16 · P17 · sapuan UI)

- Commit: `2d4d108` (inti F5) · `ce7cce4` (sapuan UI) · branch `main`.
- Sumber: [`ANALISIS_TEMUAN_UAT_23OKT.md`](../ANALISIS_TEMUAN_UAT_23OKT.md) P7, P12, P13, P16, P17; keputusan pemilik = usulan
  bawaan §4 (P7-K1 biaya **dikapitalisasi**; P7-K2 celup ulang **boleh ganti SKU** → roll anak; P12-K1 rekomendasi **(b)**
  per pelanggan dari desain/kategori yang pernah dibeli; P16-K1 susunan Pengaturan **disajikan dulu sebagai mock**).
- **DB UAT `kn_uat_23okt`**: tanpa migrasi data; izin `repair_order` & kunci konfigurasi `pos.*` terpasang otomatis saat
  backend start (backend & frontend UAT sudah di-restart).

## Perubahan perilaku (sebelum → sesudah)
### P7 — menu Perbaikan (Operasi Gudang › Perbaikan; MD juga)
* Tidak ada dokumen perbaikan → **dokumen RPR-** (perbaikan cacat / celup ulang / finishing ulang; internal atau mitra
  makloon) atas **roll yang dipilih** (milik PT, di gudang: tersedia/karantina/rusak/ditahan, tidak dicadangkan, belum di
  perbaikan lain).
* **Kirim** → roll keluar dari stok jual (status WIP ber-referensi perbaikan, tetap persediaan PT); **Terima** → qty hasil
  per roll (selisih = **susut**, mutasi `repair_loss`), **grade & dye lot baru**, biaya aktual (atau perkiraan tarif per
  satuan / per roll / borongan + biaya lain) **dikapitalisasi** ke HPP roll hasil sebanding qty hasil, jurnal **Dr
  Persediaan / Cr Hutang usaha** (mitra) atau **Cr Overhead diserap** (internal). Tagihan mitra lewat Vendor Bill.
* Celup ulang ke **SKU lain** → roll **anak** ber-SKU baru (roll induk ditutup); **Batal** dari Dikirim → roll kembali.
* Riwayat perbaikan di roll (`repair_history`), mutasi per roll, **Jejak Dokumen** (jenis `repair_order`, tautan ke
  dokumen asal bila dibuat dari retur/QC). Izin `repair_order` (Admin/Manajer/Admin Gudang/MD penuh; Gudang lihat-kirim-
  terima; QC & MD Quality lihat-buat; Finance lihat).

### P12 — sorotan POS bisa dinyalakan/dimatikan (Pusat Pengaturan › Tampilan, per PT)
* `pos.best_sellers.enabled` + `window_days` (bawaan 90), `pos.reorder.enabled`, `pos.fbt.enabled`,
  `pos.featured.enabled`, `pos.recommendation.enabled` — mati → strip hilang di POS desktop & katalog HP tanpa deploy.
* **Terlaris**: dulu seluruh riwayat & menawarkan produk apa saja → hanya N hari terakhir, **disaring** (aktif, boleh
  dipesan, bukan eksklusif pelanggan lain — pembeli lama desain customer label tetap boleh), tanpa query per produk.
* **Produk Unggulan** (baru): ditandai MD/Manajer di editor SKU (urutan, tampil sampai, label singkat) → strip "Produk
  Unggulan" di POS & HP sampai tanggal akhir.
* **Rekomendasi untuk <pelanggan>** (baru, P12-K1 b): produk berstok yang berbagi kode desain / kategori desain / pattern /
  kategori dengan pembelian pelanggan, belum pernah ia beli, boleh ia pesan; lencana alasan ("desain sama", …).

### P13 — Keep & Pending
* Panel hanya di Beranda → juga **tab "Keep & Pending"** di menu Pesanan Penjualan (server tetap membatasi sales ke SO
  miliknya). Bukti UI: `sales2@` melihat 7 SO unik miliknya (KSC/SO-00008 dst., pemilik Bima).

### P16 — UI rusak / tidak konsisten
* **P16.1 GRN**: pil buatan sendiri → **tab langkah standar** "1 Surat jalan · 2 Hitung · 3 Rekonsiliasi"; isi tiap
  langkah dalam **kartu putih ber-judul** ("Langkah 2 · Hitung roll fisik"); isian Hitung **berlabel** (Panjang, Satuan,
  Berat, Lot, Grade) dengan grid **2 kolom di HP**, 3 di tablet; tabel memakai `data-table`; isian `.field` standar.
  (P16.1b pesan rekonsiliasi sudah di F0.)
* **P16.2 Jejak Dokumen**: kartu dokumen kini punya **Pratinjau** (PDF di lightbox halaman yang sama) dan **PDF**
  (unduh) untuk setiap jenis yang punya cetakan (`pdf_doc_type` dari server); jenis lain tertulis "belum bisa
  dicetak". (PDF GRN baru sudah di F0.)
* **P16.3 Pengaturan** — usulan susunan (mock, **menunggu keputusan P16-K1**, belum dipindah):

  | Kelompok baru | Isi (dari menu sekarang) |
  |---|---|
  | 1. Perusahaan & Akun | Badan Usaha & Akses (termasuk Peran & Hak Akses), profil PT dari Master per Badan Usaha |
  | 2. Persetujuan | Aturan Persetujuan + persetujuan R&D dari "Divisi & Persetujuan R&D" + grup "Persetujuan" di Pusat Pengaturan (satu halaman lintas domain) |
  | 3. Kebijakan per domain | Penjualan (Label Alasan Amandemen, Rate Insentif, kebijakan retur) · Gudang & Mutu (Penerimaan & OCR, Perangkat RFID, Master Grade Mutu) · Pembelian & Produksi · Keuangan & Pajak (Pemetaan Akun, Kategori Beban, Aturan & Template Bank) · SDM (Shift & Geofence) · R&D (Divisi R&D) — tiap domain memuat grup Pusat Pengaturan yang sesuai |
  | 4. Master Data | indeks ke master domain + Registri Domain + Impor Dataset Client |
  | 5. Dokumen & Cetak | Template PDF + Template Dokumen Dasar digabung jadi satu "Template Dokumen" |
  | 6. Notifikasi & Penjadwal | Penjadwal & Notifikasi |
  | 7. Integrasi & Sistem (admin) | Integrasi & Audit, kunci sistem (AI/WA/audit), Kunci Saga, Kebersihan Data |

  Koreksi Harga dipindah ke Produk & Harga. Setiap konsep satu rumah; tautan lama (`?view=`) tetap hidup sebagai alias.

### P17 — semua foto bisa dipratinjau tanpa unduh
* Komponen bersama **`AttachmentThumb` / `AttachmentGallery` / `MediaLightbox`** (`hooks/useBlobUrl`): berkas dimuat
  sebagai blob lewat axios (header sesi + badan usaha → tidak 403 di PT non-utama), lightbox ←/→, **Perbesar**, **Unduh
  asli** eksplisit, foto/video/PDF.
* Dipasang di: lampiran retur jual (thumbnail + lightbox), foto per roll retur (juga retur beli & antar-PT), foto
  disposisi BS (pratinjau sebelum dipilih), pemilih foto klaim (pratinjau lokal), retur & bukti putaran sample di HP,
  bukti persetujuan SO, lampiran harga khusus, foto pengiriman (diperbesar), referensi & bukti ACC Pesanan Khusus
  (desktop & HP), lampiran konten marketing, bukti putaran R&D, berkas & ronde desain, mockup colorway, referensi
  permintaan desain.
* **Token di URL dihapus**: endpoint unduh bukti persetujuan SO & lampiran harga khusus tidak lagi menerima `?auth=`;
  lampiran retur foto/video dikirim `inline` (unduhan hanya `?download=1`); berkas yang hilang dari penyimpanan → 404
  jelas (dulu 500).

## Bukti
* `test_uat24_f5.py` **7 lulus**: P7 kirim → saldo tersedia turun 150, roll di perbaikan tidak bisa masuk dokumen lain,
  terima (susut 3, grade B, dye lot baru, HPP = (nilai lama + alokasi) / qty hasil, jurnal 1-1300 / 2-1100 = 196.000,
  mutasi susut), celup ulang ke SKU lain → roll anak, batal → roll kembali, sales 403; P12 terlaris mati → [] lalu menyala
  dengan `window_days`, aturan visibilitas eksklusif, unggulan tampil sampai tanggal akhir & sales 403 mengatur,
  rekomendasi bukan barang yang sudah dibeli; P16.2 `pdf_doc_type`; P17 `?auth=` → 401, `inline`/`attachment`.
* Jest `uat24F5` 3 lulus (jenis lampiran, galeri → lightbox tanpa `href` mentah, strip sorotan); uji navigasi akses
  diperbarui (MD hanya mendapat tab Perbaikan di Operasi Gudang).
* **Regresi** 59 berkas uji (POS, Jejak Dokumen, lampiran/persetujuan, konfigurasi, akses & menu, GRN, rencana pemenuhan),
  DB klon identik, baseline `75239bc` vs inti F5: **0 gagal baru yang disebabkan F5**. 4 uji GRN/OCR (`grn_phase2` ×2,
  `grn_phase7`, `l04_ln040`) error di baseline (fixture restore tidak aktif di lingkungan baseline) dan gagal di lingkungan
  baru karena data pemetaan barang supplier `CBN-MEGA-PREM` tidak ada di DB uji; layanan yang menolak
  (`receiving_roll_service`, UNMAPPED) tidak tersentuh sejak `97b1cf8` (sebelum paket ini). 13 error baseline lain pulih.
  Sisanya (89 gagal / 17 error) sudah ada di baseline.
* UI (DB simulasi): Perbaikan KSC/RPR-00001 (1 roll 150 yd → hasil 147, susut 3, biaya Rp 225.000 dikapitalisasi, jurnal
  KSC/JE-00035); GRN KSC/GRN-00004 tab "1 Surat jalan · 2 Hitung · 3 Rekonsiliasi" + kartu "Langkah 2"; audit tata letak
  desktop & HP bersih; SRET-00004 thumbnail → lightbox foto "4/4 · Perbesar · Unduh asli", 0 tautan lampiran mentah;
  Jejak Dokumen KSC/PO-00003: 3 kartu ber-PDF, 3 "belum bisa dicetak", pratinjau PDF di lightbox; POS sales2 + Toko Kain
  Sejahtera: "Rekomendasi untuk Toko Kain Sejahtera · kategori sama", "Produk Unggulan · Promo Akhir Tahun",
  "Produk Terlaris · 90 hari terakhir".

## Sapuan UI (audit 147 layar desktop + HP, 24 Okt)

> **Koreksi cakupan (25 Okt).** "147 layar" = 147 entri menu/tab hub dalam **keadaan awalnya** (admin; meja kerja
> sesuai peran), ditambah hanya **satu** form "Buat/Tambah" pertama per layar (47 pop-up terbuka, 24 form inline/tidak
> terbuka, 76 layar tanpa tombol buat). Belum tercakup: 11 view (mis. Perbaikan, Keep & Pending, Beranda per peran,
> Matriks Izin, Template Produk, Konversi Satuan), form **ubah**, dialog konfirmasi/alasan, halaman detail, tab di
> dalam halaman, menu tindakan, pop-up bersarang. Ini dikerjakan di **audit UI tahap 2** (crawler mendalam).
Audit visual 147 layar (admin, desktop 1440 px + HP 390 px + form) dan aplikasi HP lima peran, dikerjakan per kelompok
layar. **Tidak ada menu/layar yang dihapus atau digabung** — kandidat duplikasi dicatat di bawah untuk keputusan pemilik.

**Pola yang dibereskan lintas layar**
* **Tabel di HP**: kepala kolom pecah per kata / nama hilang di ≥10 layar. Akar utamanya "tabel grid" Tailwind
  (`grid grid-cols-[…]`) yang tiap barisnya menghitung lebar sendiri → satu blok `@media (max-width: 640px)` di
  `styles/components.css`: wadah tabel bergulir di dalam kartu, kepala `nowrap`, lebar minimum kolom; papan
  "menunggu ACC" tidak lagi melebarkan halaman. Layar yang paling parah juga diberi wadah gulir / kartu khusus HP.
* **Kode & istilah mentah** → label Indonesia: kode alasan (`warna_paling_dekat`), enum UoM (Fixed/Formula/gsm_width),
  status (`converted`, `pending_approval`), kode keputusan (D-05, PB-01, INV-CB-01, INV-IC-08, KLR-09, MD-05, LN-024,
  R7), sumber jurnal (±90 kode), kunci konfigurasi di teks bantuan, catatan pengembang ("Form lama … dihapus", perintah
  skrip migrasi), istilah Inggris (Replenishment, WIP-at-vendor, Awarded, Engagement, Gate Monitor, Kiosk, Take-home…).
* **Akun teknis** "system-seed" tampil "Sistem (data awal)" (`utils/actorLabel.js`) dan tidak dihitung sebagai desainer /
  peringkat.
* **Satuan campur** tidak lagi dijumlah jadi satu angka (kg + yard): Operasi Gudang, Status Stok & ATP, Stok
  Multi-Kantong, Meja Admin Sales HP, Status Stok MD HP, isi gudang (server kini mengirim per satuan).
* **Form**: modal tanpa tombol Simpan/Batal (Buat Tagihan Supplier), kaki modal tak standar (Landed Cost), form harga
  khusus yang berganti di tengah jalan dan membuang isian (kini satu alur, bisa "Simpan sebagai Draf"), tanda `*`,
  galat "Belum lengkap" yang muncul sebelum mengetik, isian HP tanpa label (Kunjungan, Pindai, Minta Harga Khusus —
  tombol Ajukan kini terlihat).
* **Angka & hitungan yang bertentangan di layar**: tab "Semua 0" vs "Aktif 109" (Pustaka Warna), tiga hitungan berbeda di
  Pusat Persetujuan, "Berjalan" PO vs KPI, papan Permintaan Desain yang "kehilangan" 1 permintaan berstatus selesai,
  peringkat Desainer Teratas / KPI Desainer, "Tepat waktu 0%" saat 0/0, rasio keuangan raksasa ("> 50x"), indikator
  "Memuat pesanan…" yang menumpuk di atas data, kalkulator konversi yang macet.
* **Gaya**: tombol utama ungu/hitam/hijau → biru standar, tab buatan sendiri → `tab-bar`, kicker Inggris dihapus, teks
  < 11 px dinaikkan pada bagian yang disentuh, KPI tidak terpotong di HP.

**Per kelompok** (rincian berkas di laporan agen; semua ESLint 0 error)
* Penjualan, persetujuan, POS, CRM, harga (000–009, 014–016, 117–121, 143–145, HP sales/sales_admin) — 41 berkas;
  SKU tersamar di POS tampil rapi (`pos/skuDisplay.js`), tombol keranjang tidak menutupi Bantuan, grafik komisi
  bersumbu Rp & bulan.
* Master, pembelian, makloon, produksi (010–013, 017–030, 122–125, HP md) — 34 berkas; Kategori & Supplier berbentuk
  kartu di HP, kontrak 241 baris berhalaman 50, menu "Buat PO" berbahasa Indonesia.
* Keuangan, pajak, SDM, laporan, dokumen (031–033, 060–093, 128–141) — 66 berkas; tabel SDM/HP bergulir di dalam
  kartu, halaman keuangan HP tidak lagi melebar, pembeda angka saldo rekening vs kas dijelaskan.
* Retur, R&D, desain, marketing (034–050, HP md R&D) — 32 berkas; tab Retur Antar-PT kini mode retur sendiri (bukan
  halaman transaksi interco utuh), warna status retur seragam, Spesifikasi Produk HP tidak melebar.
* Gudang, stok, QC, RFID, logistik, pengaturan (051–059, 094–116, 126–127, 146, HP warehouse/manager) — ±45 berkas
  + CSS global; Pusat Pengaturan tidak tertahan "Memuat…", RFID & penjadwal berbahasa Indonesia, "Reset Demo Data"
  pindah ke "Zona berbahaya".

**Perbaikan backend dari temuan sapuan**
* Mitra makloon milik grup (`entity_id="all"`) tampil di semua PT (daftar Mitra Makloon & pemilih di resep proses
  dulu kosong) — `INHERITED_GLOBAL_VALUES` + `resolve_list_scope_inherit`.
* Isi gudang per satuan (`qty_by_unit`) di Data Gudang.
* SKU hasil Pesanan Khusus tidak ikut "Produk Terlaris" / rekomendasi.
* Dasbor Pesanan HP: semua status hidup masuk kartu status (menunggu stok, dikemas, dalam perjalanan) dan kepemilikan
  sama dengan "Pesanan Saya" (SO yang dibuat Admin Sales atas pelanggan milik sales ikut terhitung).
* Komponen bersama: kalkulator konversi tidak "Menghitung…" tanpa satuan; judul menu Indonesia.

**Belum diperbaiki (perlu backend / komponen bersama / keputusan)**
* Backend: ATP 057 vs 058 (penjumlahan ATP per gudang mengurangi backorder tanpa gudang di tiap gudang —
  `stock_bucket_service.py:299`, `atp_policy.py:58`); saldo rekening vs ringkasan kas (transaksi kas tanpa
  `account_id`); qty profitabilitas menjumlah kg + yard (`profitability_service.py`); MTD Beranda admin vs "hari ini"
  (definisi leaderboard); "Tagihan Rp 0" HP vs piutang Beranda (definisi berbeda); pratinjau PDF template dengan status
  & URL mentah; data uji ("test — SORD…") di DB UAT.
* Komponen bersama: dua gaya dropdown (`KNSelect` berganti ke mode cari pada ≥ 6 opsi), belum ada pemilih tanggal-jam,
  kerangka halaman (judul/kartu) yang berbeda-beda di beberapa layar keuangan & marketing, dua tab-bar kembar di Barang
  Masuk.
* Terlalu besar untuk sapuan: form induk produk ±3000 px, form inline → FormModal di beberapa master, 6 lapis filter
  R&D.

**Kandidat duplikasi — menunggu keputusan pemilik (belum disentuh)**
* Harga: daftar harga 014 ≈ 015 (satu matriks harga + pemilih lapis), harga internal 016 ≈ tab kontrak 028.
* Pelanggan: Impor/Ekspor & Status 009 ≈ CRM 007.
* R&D: Permintaan Sample 038 ≈ Labdip/Handfeel/Proofing 039–041 (entitas & form sama); Desain 049 ≈ Galeri 050;
  Rapor Desainer 047 ≈ KPI Desainer 048 ≈ Desainer Teratas 042.
* Gudang & stok: Operasi 051 ≈ Status Stok 057 ≈ Multi-Kantong 058 (KPI ganda, angka beda); Lokasi Rak 124 ↔ Data
  Gudang 125 (dua struktur lokasi); daftar Surat Jalan 126 ↔ meja Admin Gudang 146.
* Pembelian & makloon: rekap klaim 024 ≈ antrean klaim 025; "Proses Makloon Saja" di PO ≈ Order Makloon.
* Keuangan: tren/rasio 092 ≈ 093, biaya 086 ≈ profitabilitas 072, kas 073 ≈ 092, Rekap PPN 067 ≈ 068, tutup buku 133 ≈
  buka periode 134, kategori kas 061 ≈ kategori beban 113, retur antar-PT 035 ≈ transaksi interco 136.
* Pengaturan & dokumen: Template PDF 106 ≈ Template Dokumen 107 ≈ Daftar Dokumen 091; aturan persetujuan 101 ↔ divisi R&D
  116 ↔ Pusat Pengaturan; pengaturan OCR 108 ↔ 099 — termasuk usulan susunan Pengaturan P16-K1 di atas.
* HP: tiga daftar produk (Katalog / Produk MD / Template), Pantau Persetujuan ≈ Antrean Manajer, Minta Harga Khusus ≈
  "+ Ajukan", menu "Lainnya" sales vs MD dua implementasi.

**Bukti sapuan**: Jest penuh **37 suite / 156 uji lulus** (uji retur & navigasi disesuaikan dengan pratinjau tanpa
`href` dan tab Perbaikan MD); ESLint 0 error di ±220 berkas yang berubah; uji backend terdampak lulus (F1, F4, F5,
dasbor pesanan, rencana pemenuhan, akses sales); audit tata letak di UAT (CDP) 8 layar desktop + 6 layar HP: tanpa
gulir samping, tumpang tindih, atau teks terpotong; agen memeriksa langsung di peramban ±25 layar lain pada 375–390 px.

## Lanjutan 25 Okt — sisa temuan sapuan yang perlu backend / komponen bersama

Commit: `78b14b6` · branch `main`. Tidak ada migrasi data; backend UAT & backend uji di-restart.

| Temuan sapuan | Sebelum | Sesudah | Berkas |
|---|---|---|---|
| ATP Status Stok (057) ≠ Multi-Kantong (058) | backorder tanpa gudang dikurangkan di **setiap** gudang → total papan −180 vs detail −120 | dikurangkan **sekali** per produk × PT; ATP per gudang hanya backorder gudang itu; total papan = rumus tunggal Status Stok (judul KPI menjelaskan rumusnya) | `atp_policy.py` (`include_unassigned`, `backorder_map`), `stock_bucket_service.py`, `roll_service.py`, `fulfillment_service.py`, `StockBucketsView.jsx` |
| Saldo rekening ≠ ringkasan kas | transaksi kas tanpa `account_id` (kas manual lama, kwitansi, refund) tidak masuk saldo rekening mana pun | bila PT hanya punya **satu** rekening untuk jenis kas itu, transaksi tanpa rekening ikut rekening tersebut; kas manual baru otomatis memakai rekening tunggal itu. PT dengan ≥ 2 rekening sejenis tidak ditebak | `bank_service.py` (`sole_account_id`, `_txns_for`), `routers/cash.py` |
| Qty profitabilitas menjumlah kg + yard | "Qty" satu angka campuran | per satuan dasar: "51,17 kg · 238,99 yard" (`qty_by_unit` di tiap baris & total) | `profitability_service.py`, `ProfitabilityView.jsx` |
| Beranda admin: Bulan Ini < Hari Ini | Bulan Ini = jumlah leaderboard (hanya pelanggan ber-sales aktif), Hari Ini = semua SO | keduanya dari populasi SO hidup yang sama; Tertagih Bulan Ini = pembayaran bulan ini atas semua SO | `home_service.py` |
| HP "Tagihan Rp 0" vs piutang Beranda | label "Tagihan" tanpa penjelasan | label "Tagihan ≤ 60 hr" + keterangan: hanya pesanan ber-Surat Jalan (keputusan Q-05a) dengan jatuh tempo ≤ 60 hari; total piutang ada di Beranda. Definisi sengaja tidak diubah | `MobileCollectionTargets.jsx` |
| Akun teknis di peringkat desainer | "system-seed" ikut Desainer Teratas, jumlah desainer & tren | dibuang dari KPI, tren grade & tren nilai desain (`TECH_ACTORS`, sama dengan `actorLabel.js`) | `rnd_kpi_service.py` |
| Pratinjau/cetak PDF: status & URL mentah | chip status & "Status Bayar" tercetak `waiting_stock`, `unpaid`; petunjuk Jejak Dokumen berisi URL ber-id internal | label Indonesia satu sumber di mesin PDF ("Menunggu stok", "Belum dibayar", "Lunas via retur"); petunjuk: "Atau buka ‹alamat aplikasi› › Jejak Dokumen, cari nomor ‹nomor›" (QR tetap ke URL lengkap) | `pdf_engine.py`, `pdf_service.py` |
| Pelacak SO di meja Admin Sample | menampilkan SO roll biasa — tak satu pun tahapnya milik Admin Sample | menampilkan **SO sampel** dengan tahap antrean sampel (bayar → teruskan ke gudang → potong → kirim); meja lain tetap tanpa SO sampel | `so_tracker_service.py` |
| Dua gaya dropdown | ≥ 6 opsi → ikon ⇅, < 6 opsi → ikon ˅ | satu ikon ˅ untuk kedua mode | `components/KNSelect.jsx` |
| Belum ada pemilih tanggal-jam | `datetime-local`/`date` bawaan peramban (format OS) | `KNDateTimePicker` (kalender + kolom jam) di jadwal konten, duplikasi konten, jadwal jemput retur; `KNDatePicker` di kampanye, tampil-sampai varian, tanggal balik jurnal, berlaku-mulai harga internal, tanggal kirim/ambil koreksi SO, tanggal keputusan pelanggan OD. Isian tanggal di HP sengaja tetap pemilih bawaan HP | 9 berkas (lihat diff) |
| Dua tab-bar kembar di Barang Masuk | tab layar + filter status sama-sama `tab-bar` | filter status berbentuk chip di baris pencarian | `wms/grn/GoodsReceiptsView.jsx` |

**Bukti lanjutan**
* `tests/test_uat24_lanjutan.py` **9/9 lulus** (DB uji `kn_test_trial`): backorder tanpa gudang sekali; total ATP papan =
  ATP detail; transaksi tanpa rekening ikut rekening tunggal (dan tidak ditebak bila ada 2 rekening sejenis);
  `qty_by_unit` tiap baris = qty; Bulan Ini ≥ Hari Ini; tanpa akun teknis di KPI & tren; label status PDF; pratinjau
  PDF tanpa kode status mentah & tanpa `/jejak-dokumen/` di teks; pelacak meja Admin Sample hanya SO sampel.
* Regresi backend 55 berkas uji yang menyentuh modul terkait: 517 lulus, 137 gagal, 109 error. Ke-137 kegagalan
  dijalankan ulang pada **baseline `7f814b7`** (salinan `backend` HEAD, kontainer & DB uji sama): 129 gagal + 6 error
  setup yang sama → sudah ada sebelum perubahan ini (data seed lama, mis. kas kecil 9.750.000, desainer "Dewi Lestari").
  2 sisanya: penomoran 40 permintaan serentak lulus saat diulang (berubah-ubah); `test_l04_mdq_cut::test_cleanup` lulus
  bila dijalankan sendiri di baseline & kode baru (gagal hanya karena urutan loop event saat digabung). 2 kegagalan
  `test_review_iter91_trace_print` sama persis di baseline.
* Jest penuh **37 suite / 156 uji lulus**; ESLint 0 error di 14 berkas FE yang berubah (7 peringatan lama).
* Diperiksa langsung di UAT (`kn_uat_23okt`): Beranda (Bulan Ini Rp 79.607.724, Hari Ini Rp 0), Profitabilitas per
  pelanggan "51,17 kg · 238,99 yard", Barang Masuk (chip status), pemilih tanggal-jam di form konten Marketing.

**Masih terbuka**
* Kerangka halaman (judul/kartu) yang berbeda-beda di beberapa layar keuangan & marketing; form induk produk ±3000 px;
  form inline → FormModal di beberapa master; 6 lapis filter R&D — pekerjaan tata letak besar, belum disentuh.
* Isian tanggal OCR/GRN (`grn-dn-date`, `ocr-sample-date`) dan filter tanggal ringkas R&D (`DateQuickNav`) masih
  `type="date"` (lebar kolom & penanda koreksi OCR bergantung pada elemen input).
* Data uji di DB UAT ("test — SORD…", data uji UAT sebelumnya) — **menunggu izin pemilik** sebelum dihapus.
* P16-K1 dan kandidat duplikasi — menunggu keputusan pemilik (lihat di atas).

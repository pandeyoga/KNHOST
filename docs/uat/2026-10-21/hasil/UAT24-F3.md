# UAT 24 Okt — F3 (R&D & desain: P4, P5, P3, P1, P6)

- Commit: `e8c7739` · branch `main`.
- Sumber: [`ANALISIS_TEMUAN_UAT_23OKT.md`](../ANALISIS_TEMUAN_UAT_23OKT.md) P1, P3, P4, P5, P6; keputusan pemilik =
  usulan bawaan §4 (P1-K1 Manajer memutus klaim & pembeli lama boleh repeat; P1-K2 arti HOLD tetap; P1-K3 customer
  label sejak OD disetujui; P4-K1 "pernah PO" boleh dengan label; P4-K2 batas 10 warna, SKU lahir saat spesifikasi
  per warna di-ACC).
- **DB UAT `kn_uat_23okt` sudah dimigrasi** (`uat24_f3_data.py`), backend UAT sudah di-restart.

## Perubahan perilaku (sebelum → sesudah)
### P4 — R&D dua pintu
* Satu tab "Permintaan Sample" untuk semua → **R&D Produk Baru** dan **Uji Ulang** (tab hub terpisah; daftar & form
  mengikuti `purpose`).
* Jenis uji dipilih bebas → **rantai** handfeel → labdip → produk: labdip produk baru wajib merujuk **handfeel yang
  ACC** (konstruksi diwarisi ke spesifikasi), atau menempuh handfeel di permintaan yang sama; proofing wajib **kain
  dasar yang lolos** (SKU berjalan atau handfeel/labdip ACC). Kebijakan `rnd.require_stage_chain` (bawaan aktif).
  **Tidak berlaku** untuk uji ulang dan sampel milik pelanggan (pesanan khusus / SO).
* Labdip satu warna → **multi-warna** (≤ `rnd.labdip_max_colors`, bawaan 10): satu sampel + satu spesifikasi per warna
  dalam satu kelompok; ronde, ACC, pemenang per warna; tombol "Kirim SEMUA warna ke supplier".
* Warna target wajib dari Pustaka → warna **baru** boleh diisi (nama, hex, **Pantone wajib**); saat labdip di-ACC,
  warna itu **lahir di Pustaka Warna** (kode KN otomatis) atau tertaut ke entri ber-Pantone sama. Pustaka punya kolom
  Pantone (form & daftar).
* Supplier uji ulang = semua → **berkontrak** untuk SKU/induknya, lalu "**pernah PO** — tanpa kontrak" (berlabel).
* Aksi: "Sample jadi" (sebelum pemenang) → **Terima sampel fisik** (setelah pemenang); "Kirim sample" →
  **Kirim ke pelanggan** (hanya sampel pelanggan) / **Arsipkan** (lainnya).
* Form: desain & kain dasar hanya untuk proofing; pemilih "Untuk pesanan pelanggan" (200 SO bebas) dihapus — terisi
  otomatis bila sampel lahir dari pesanan.

### P5 — kombinasi varian
* Pesan buntu "Kombinasi ini sudah memiliki SKU…" → opsi yang sudah jadi SKU ditandai "sudah ada (SKU …)" dan tidak
  bisa dipilih; **+ Warna baru dari labdip ACC** menambah nilai sumbu warna (kode 4 huruf) yang lahir di induk saat
  spesifikasi di-ACC; jalan keluar **Uji ulang SKU ini** (membuka tab Uji Ulang dengan SKU terisi).

### P3 — surat perintah kerja & berkas
* Tidak ada dokumen keluar R&D → **Surat Perintah Kerja Sampel R&D** per supplier (PDF): labdip = kotak warna + kode
  KN + **Pantone**; handfeel = konstruksi; proofing = kode desain, versi ACC, repeat/screen, kain dasar + **gambar
  pattern PNG cetak**. Tombol "Cetak untuk <supplier>" di rincian sampel.
* Berkas final desain = mockup + file asli → **+ PNG cetak** (berkas PNG sungguhan, ≥ 600 px); desain final lama tanpa
  PNG diberi peringatan (status tidak dimundurkan).
* Labdip boleh dikirim tanpa Pantone → **ditolak** sampai Pantone jelas.

### P1 — kepemilikan desain
* Eksklusif hanya di SKU → **white label / customer label** di desain (SSOT), turun otomatis ke semua SKU ber-desain
  (`exclusive_customer_id`, sumber "design") sehingga pagar SO/POS yang ada ikut berlaku.
* Klaim pelanggan (sales/Admin Sales/MD) → diputus **Manajer** (pengaju tidak bisa memutus sendiri), notifikasi ke
  pengaju; Manajer juga bisa menetapkan/melepas langsung ber-alasan. Izin baru `design_ownership` (view/claim/decide).
* Pembeli lama saat desain diklaim **boleh repeat dari stok** (tanpa backorder).
* POS/HP: SKU eksklusif pelanggan lain **tidak tampil** saat pelanggan aktif dipilih.
* Panel **Pemakaian**: pembeli, jumlah SO, qty per satuan, nilai, repeat. Galeri: lencana & filter kepemilikan,
  "Sudah/Belum diproduksi".
* Desain asal pesanan khusus otomatis customer label sejak OD disetujui; artwork OD hanya white label atau milik
  pelanggan itu.

### P6 — tag desain di master produk
* Kode desain, kategori pattern/design, tag desain tersalin ke SKU (pemilih **desain** di header induk katalog;
  varian baru mewarisi), ikut berubah bila desain diubah.
* POS: facet Kode desain / Kategori pattern / Kategori design + pencarian; Pusat Export: kolom desain di semua join
  produk + dataset **Penjualan per Desain** (SKU, pelanggan, SO, repeat, qty+satuan, nilai, SO pertama/terakhir).

## Bukti
* `test_uat24_f3.py` **17 lulus** (kepemilikan & penegakan, klaim via API, artwork OD, dataset export, rantai
  handfeel→labdip + warisan konstruksi, kelompok 3 warna, Pantone saat kirim, Pustaka lahir/tertaut, aksi tahap,
  supplier berkontrak, PNG cetak, surat perintah, nilai sumbu baru). Jest `uat24F3` 4 lulus.
* **Subset R&D 54 berkas** (DB klon identik) baseline F0–F2 vs F3: awalnya 20 gagal baru → 15 ternyata jalur OD yang
  ikut terkena aturan produk baru (diperbaiki: sampel pelanggan dikecualikan), 5 uji lama menyandi aturan lama
  (labdip tanpa handfeel ×2, OD labdip tanpa Pantone, fixture menu akses, proofing OD) → disesuaikan. Akhir: **0 gagal
  baru**; 116 gagal / 57 error yang tersisa sudah ada di baseline.
* UI (DB simulasi & UAT): galeri "Customer label · Butik Bali Indah", pemakaian 1 SKU · 1 SO · Rp 26 jt; form R&D
  Produk Baru (handfeel induk, editor 2 warna + Pantone, tanpa pemilih SO/desain untuk labdip); tab Uji Ulang; rincian
  sampel "Kirim ke pelanggan" + "Cetak untuk PT Kimia Warna Prima"; PDF surat perintah; bar desain di katalog; kolom
  Pantone di Pustaka.

## Data (`uat24_f3_data.py`, idempoten; sudah di UAT & simulasi)
* BDI-ABS-AO-001 → customer label Butik Bali Indah (SORD-261023-0003); SKU OD-nya ditautkan ke desain.
* Kandidat pencocokan produk ↔ desain lewat nama/motif hanya dilaporkan (0 kandidat).

## Perhatian untuk pemilik / MD
* **Pantone**: 0 dari 109 warna Pustaka UAT punya kode Pantone eksplisit (6 bersistem TCX/TPX dianggap ber-Pantone
  dari kodenya). Labdip pesanan khusus yang memakai warna Pustaka baru bisa dikirim ke supplier setelah MD mengisi
  kolom **Kode Pantone** di Pustaka Warna — pesan galatnya menyebut warna mana.
* **PNG cetak**: desain final lama perlu diunggahi PNG cetak sebelum proofing produk baru dikirim (proofing OD tetap
  jalan; suratnya memakai artwork ACC dan memberi catatan).
* Rantai produk baru bisa dimatikan di Pengaturan › R&D (`rnd.require_stage_chain`) bila masih transisi.

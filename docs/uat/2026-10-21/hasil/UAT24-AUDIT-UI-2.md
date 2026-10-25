# UAT 24 Okt — Audit UI tahap 2 (semua layar, tab, detail, pop-up, form ubah, konfirmasi — desktop + HP)

- Commit: `fb0d069` (G0) · `683ab1d` (G1) · `90876cb` (G2) · `29ec1a7` (G3) · `fb38851` (G4) · `5cea115` (G5a) ·
  `8358694` (G5b) · `ddad3bc` (lintas grup) · `60318b8` (perbaikan hasil verifikasi) · branch `main`.
  Baseline audit: `e5b2579`.
- Alasan: sapuan 24 Okt hanya 147 entri menu dalam keadaan awal + satu form "Buat" per layar (lihat koreksi di
  [UAT24-F5.md](UAT24-F5.md)). Tahap 2 menelusuri **semua** keadaan yang bisa dicapai dari tiap layar.
- Lampiran (folder [`audit-ui-2/`](audit-ui-2/)): rencana perbaikan gabungan (243 butir + keputusan pemilik),
  matriks cakupan, laporan perbaikan per grup, laporan review per batch, rubrik & brief peninjau. Tangkapan layar
  (±2.400 JPEG) tidak di-commit (ukuran); path di laporan review menunjuk folder kerja audit.

## Metode
* **Crawler mendalam** (Edge headless + CDP) di stack uji (DB `kn_test_trial`, data paling lengkap): untuk tiap view —
  halaman → tombol pembuka pop-up → baris/kartu pertama (detail) → tab di halaman & di detail → menu tindakan →
  pop-up bersarang & tab di dalam pop-up; desktop 1440 px dan **aplikasi HP per peran** (12 akun peran, tab bawah +
  setiap butir menu "Lainnya", 390 px).
* **Aman untuk data:** semua XHR/fetch non-GET diblokir di peramban (kecuali endpoint pratinjau/hitung yang
  hanya-baca); `confirm/alert/prompt/print/window.open` bawaan dicegat & dicatat (temuan bila dipakai); unduhan
  ditolak. Pesan "gagal simpan" sesudah tombol aksi = akibat pemblokiran, bukan temuan.
* **Masalah teknis yang ditemukan & dibereskan selama audit** (dicatat supaya hasil bisa dipercaya):
  1. Putaran pertama memasang sesi tanpa konteks badan usaha (kepala "Badan usaha") → banyak daftar tampak kosong.
     Seluruh crawl diulang dengan sesi seperti login normal; klaim review putaran pertama diverifikasi ulang
     (±45 klaim terbukti artefak, mis. "dropdown rekening kosong", "Negara/Provinsi kosong", "dropdown di pop-up
     tidak terbuka" — yang terakhir diuji manual: terbuka normal).
  2. Backend uji jenuh (1 worker) saat 7 peramban jalan → beban dibagi ke dua stack.
  3. Butir di grup menu "Lainnya" HP tersembunyi setelah kepala grup diklik (status lipat tersimpan) → diulang.
* **Review:** 9 batch oleh agen peninjau memakai rubrik yang sama dengan sapuan 24 Okt (standar kerangka halaman,
  tabel, tombol, isian, KNSelect/KNDatePicker/FormModal; kategori rusak/konsisten/form/HP/duplikasi/istilah).
  Temuan lalu digabung & dideduplikasi menjadi rencana perbaikan dengan himpunan berkas per grup yang tidak
  beririsan (dikerjakan paralel tanpa saling menimpa).

## Cakupan (crawl-2)
| | Desktop | HP per peran | Jumlah |
|---|---:|---:|---:|
| Titik awal (view / tab bawah / butir "Lainnya") | 156 | 99 dari 127 (28 sisanya → crawl verifikasi) | 255 |
| Keadaan bergambar | | | 2.395 |
| Pop-up unik / kemunculan ulang | | | 388 / 132 |
| Pop-up bersarang & tab di dalam pop-up | | | 205 |
| Halaman detail | | | 255 |
| Tab di dalam halaman | | | 442 |
| Menu tindakan | | | 70 |
| Perubahan inline (filter/panel) | | | 780 |
| Klik tanpa efek terlihat | | | 313 |

Rincian per layar: [`audit-ui-2/matriks-cakupan.md`](audit-ui-2/matriks-cakupan.md).

## Temuan
Review mentah 9 batch: 57 T · 377 S · 249 R (dengan duplikasi lintas layar). Sesudah digabung: **243 butir
perbaikan (47 T · 163 S · 33 R)** + 13 pola lintas layar, ditambah 16 keputusan bisnis, 29 kandidat duplikasi dan
10 pekerjaan tata letak besar untuk pemilik ([`rencana-perbaikan.md`](audit-ui-2/rencana-perbaikan.md)).

Pola lintas layar terpenting: aksi berdampak tanpa dialog konfirmasi (Tutup Buku, Auto-Encode RFID, hapus kontrak,
posting gaji, konfirmasi antar-PT …), status/kode internal tampil mentah (`cancelled`, `KLX-03`, `ent_ksc`,
`tahap: shipped`, `oleh all`), gejala KNSelect (placeholder tampil sebagai pilihan ✓), KPI ikut tersaring tab,
tabel desktop terpotong di HP, tanggal UTC/ISO & bulan Inggris di PDF, galat izin dipamerkan mentah atau ditelan
menjadi "kosong", angka yang sama berbeda antar layar.

## Perbaikan
| Grup | Cakupan | Butir | Diperbaiki | Sebagian | Beda definisi → pemilik | Tidak dikerjakan |
|---|---|---:|---:|---:|---:|---:|
| G0 | Komponen bersama | 21 | 21 | – | – | – |
| G1 | Keuangan & akuntansi | 52 | 47 | 2 | 2 | 1 (eliminasi basi G1-33, perlu analisis) |
| G2 | Penjualan/CRM/harga/retur + HP sales | 33 | 28 | 3 | 2 | – |
| G3 | Gudang/inventori/logistik/RFID/inspeksi/GRN + HP gudang | 37 | 33 | 4 | – | – |
| G4 | Pembelian/kontrak/makloon/master | 30 | 27 | 3 | – | – |
| G5a | R&D/desain/SDM/marketing | 35 | 31 | 3 | – | 1 (K-09) |
| G5b | Dokumen-PDF/ekspor/pengaturan/persetujuan + HP Ops & MD | 36 | 32 | 4 | – | – |
| Lintas grup | Router/service tanpa pemilik | 14 | 14 | – | – | – |

Contoh perbaikan T: pemetaan akun Pendapatan kini bisa dipilih (tipe `revenue` vs `income`); Tutup Buku/
Auto-Encode RFID/hapus kontrak lewat dialog konfirmasi; Kontrabon "belum ditagih" = tab GR; TOTAL Umur Piutang ikut
filter; dialog Selisih Pembayaran satu sumber angka; jam foto POD dalam WIB; persen harga khusus tidak lagi
"−-3064%"; pop-up Pelanggan Baru di HP bergulir; aplikasi HP Ops tidak lagi menampilkan "Permission ditolak" dan
"Putuskan di HP" membuka dokumen yang bisa diputus; PDF berbulan Indonesia & berlabel PPN; PO batal melepas PR.
Rincian per butir (berkas:baris, cara cek): [`audit-ui-2/perbaikan/`](audit-ui-2/perbaikan/).

**Perubahan perilaku yang perlu diketahui penguji/skrip E2E:** banyak aksi kini meminta konfirmasi (skrip harus
menekan tombol dialog); Backorder = SO `waiting_stock` (kartu = tab = daftar); hitungan 360 pelanggan tanpa SO batal;
ekspor berisi label status Indonesia; membuat akun wajib sandi awal; aplikasi HP Ops: tab Antrean digabung ke
Persetujuan & tab Desktop dihapus; detail lot sebagai pop-up; tugas gudang batal/tutup tanpa tombol aksi; KNSelect
menyembunyikan opsi kosong ("Semua …") selama terpilih & menandai nilai yang tidak ada di daftar.

## Bukti uji
* **Jest penuh** (sesudah semua grup): **42 suite / 191 uji lulus** (5 berkas uji baru).
* **ESLint** 357 berkas frontend yang berubah: **0 error** (155 peringatan, hampir semua direktif lama tak terpakai).
* **pyflakes** 50 berkas backend: tanpa peringatan baru (peringatan yang ada berasal dari baris lama).
* **pytest**: 7 berkas uji baru per grup lulus. Regresi 73 berkas uji terkait (70 `tests/` + 3 `test_core_*`; backend uji di-restart): 598 lulus,
  147 gagal, 86 error. Kegagalan dijalankan ulang pada **baseline `e5b2579`** (salinan backend HEAD, DB uji sama):
  230 juga gagal/error di baseline (data seed lama), 3 sisanya **lulus bila dijalankan sendiri** (galat urutan loop
  event saat berkas digabung) → **tidak ada regresi dari perubahan ini**.
* **Insiden selama verifikasi:** server dev menahan hasil lint versi setengah jadi (`node_modules/.cache/.eslintcache`)
  sehingga overlay "Parsing error" menutupi layar UAT walau berkasnya benar → cache dihapus, kedua frontend dikompilasi
  ulang bersih ("compiled with 1 warning"). Crawler kini berhenti otomatis bila overlay itu muncul.

## Verifikasi crawl sesudah perbaikan
* **Desktop** — 35 layar tempat butir [T] berada dirayapi ulang (534 keadaan, 143 pop-up unik — kini termasuk
  dialog konfirmasi baru). Dari 80 butir (34 T, 46 S) yang dinilai: **73 terverifikasi** (30 T, 43 S),
  **2 belum** — G5-10 notifikasi LAMA di Meja Saya masih "tahap: cancelled" (→ diperbaiki sesudah verifikasi, lihat
  bawah) dan G1-17 "Kekurangan dipenuhi 1,35" tanpa satuan (→ backend kini mengirim `unit`) — dan **5 tak
  tertangkap**: 4 butir layar Antar-PT karena koleksi antar-PT di DB uji dikosongkan oleh uji regresi
  (`test_interco_g6.py::test_00_cleanup`), 1 butir ada di layar lain (Saran Reorder).
* **Regresi yang ditemukan verifikasi & langsung diperbaiki:** tombol "Nonaktifkan" di tabel Akun & Akses terdorong
  ke luar layar 1440 px (kolom aksi kini menempel di kanan, judul kartu tidak patah).
* **Perbaikan tambahan dari verifikasi:** label tahap notifikasi lama di "Giliran saya"; riwayat audit menampilkan
  sumber & peran berlabel (bukan `bank_account_created` / `admin`); pesan aturan gudang menyebut nama badan usaha
  (bukan `ent_kanda (dedicated)`); peringatan React "uncontrolled → controlled" di lembar inspeksi SPK.
* Penanda otomatis yang ternyata palsu: kode di Cek Peran (ada di blok `<details>` tertutup), `{{nomor}}` di editor
  template PDF (memang placeholder template), 404 lampiran desain (berkas tidak ada di DB uji — layar kini punya
  fallback).
* **HP** — 117 titik awal aplikasi HP per peran dirayapi ulang sesudah perbaikan (993 keadaan; aplikasi HP Ops
  sudah dengan susunan tab baru). Penilaian per butir menyusul di commit berikutnya.

## Belum dikerjakan / menunggu keputusan
* **Keputusan bisnis K-01…K-16** (definisi piutang/kas/stok tersedia/"Cepat laku"/Menunggu/utang antar-PT, DPP vs
  bruto & tampilan PPN, bobot desainer 120 %, awalan nomor "PR-" ganda, bawaan "Langsung dikonfirmasi", wewenang per
  peran, isi tab Ringkas HP, glosarium istilah, ambang alasan, tutup buku saat Suspense ≠ 0, Labdip tanpa handfeel)
  — rincian & dua definisinya di `rencana-perbaikan.md` §5.3. Layar kini memberi label sumber angka.
* **29 kandidat duplikasi** (D-01…) & **P16-K1** — keputusan pemilik; tidak ada menu yang dihapus/digabung.
* **10 pekerjaan tata letak besar** (navigasi berlapis, kepala halaman tanpa kartu, pop-up buatan sendiri → FormModal,
  halaman desktop mentah di HP, gaya aplikasi HP per peran) — butuh keputusan pola.
* **Sebagian/backend lanjutan:** G1-33 eliminasi basi; nama pengaju di matriks persetujuan, nomor dokumen di Jejak
  Audit & Cek Peran, kode wilayah di wizard entitas, host QR dari URL publik, filter `has_backorder`, grade per roll
  di timeline retur (rincian di `perbaikan/COORD.md` & laporan grup).
* **Data uji** di DB uji: saldo yatim `wh_TEST_*`, 15 produk bersaldo tanpa master, cache antar-PT basi — butuh izin
  pemilik sebelum dibersihkan.

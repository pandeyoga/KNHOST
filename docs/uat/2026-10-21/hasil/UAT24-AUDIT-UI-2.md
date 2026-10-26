# UAT 24 Okt — Audit UI tahap 2 (semua layar, tab, detail, pop-up, form ubah, konfirmasi — desktop + HP)

- Commit: `fb0d069` (G0) · `683ab1d` (G1) · `90876cb` (G2) · `29ec1a7` (G3) · `fb38851` (G4) · `5cea115` (G5a) ·
  `8358694` (G5b) · `ddad3bc` (lintas grup) · `60318b8` & `e508e7d` (perbaikan hasil verifikasi desktop & HP) ·
  `c9b3f76` (keputusan pemilik 26 Okt) · branch `main`.
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
* **HP** — 117 titik awal aplikasi HP per peran dirayapi ulang (993 keadaan; aplikasi HP Ops dengan susunan tab
  baru). Dari 53 butir HP: **37 terverifikasi**, 6 belum, 10 tak tertangkap (tab sesudah Notifikasi pada HP Ops
  terlewat crawler; peran QC/MD Quality langsung mendarat di Inspeksi). **Regresi T yang ditemukan & langsung
  diperbaiki (`e508e7d`):** halaman SPK Inspeksi & Spesifikasi Produk melebar di 390 px (`.section-pad` kini
  `min-width: 0`; diukur ulang: lebar dokumen 390 = layar). Juga diperbaiki: notifikasi HP Ops membuka "tampilan
  penuh" sementara (dulu mode desktop menetap), galat kembar tanpa kunci React ganda, form CRM Pelanggan Baru 1
  kolom di HP. Sisa "belum": G4-12 & G5-46 pada **data lama** (perbaikan berlaku untuk dokumen baru), G5-09
  tautan notifikasi nota kredit/desain ke daftar umum, G5-61 riwayat pengaturan MD (ditutup oleh keputusan K-11),
  G5-62 saran Tanya KN tertutup kotak input. Rincian: [`audit-ui-2/verifikasi/`](audit-ui-2/verifikasi/).

## Keputusan pemilik 26 Okt (diterapkan `c9b3f76`)
Semua rekomendasi K-xx disetujui kecuali **K-05** (pemilik: kelas murni dari moving average penjualan, top/bottom
20 %) dan **K-13** (istilah UI tidak diubah). Ringkas yang diterapkan: piutang & lewat tempo satu definisi (semua
pelanggan, lewat ≥ 1 hari), kas utama = saldo GL, Total termasuk PPN + DPP & "DPP nilai lain (11/12)" di layar & PDF
(diskon pratinjau SO tidak lagi dihitung dua kali), stok tersedia berbasis roll (`stock_availability.py`), Analitik
Stok kelas Best seller / Normal / Slow moving / Tidak bergerak / Baru (MA 90 hari, persentil per satuan — dasar
ABC/Pareto & FSN; semua ambang di Pusat Pengaturan), KPI "Menunggu persetujuan", antar-PT posisi bersih, bobot
desainer 100 %, payroll `PAY-`, "Langsung dikonfirmasi" mati bawaan, wewenang per peran (papan PO Custom sales
tersaring, MD hanya pengaturan R&D), tab Ringkas HP per peran, alasan minimum 5 huruf, tutup buku diblokir saat
Suspense ≠ 0 (admin menembus beralasan), Labdip tanpa handfeel boleh beralasan; B1 SPK QC peringatan (setelan bisa
blokir), B3 grade per roll di timeline retur, B4 kasus tanpa nominal. Rincian & cara cek:
[`audit-ui-2/keputusan/`](audit-ui-2/keputusan/).

**Bukti uji keputusan:** Jest penuh **46 suite / 223 uji lulus**; ESLint 57 berkas 0 error; tanpa peringatan pyflakes
baru; pytest 1.149 uji (8 berkas baru + regresi terkait): kegagalan yang tidak ada di daftar gagal sebelumnya (83)
dijalankan ulang di baseline `e508e7d` → 82 juga gagal di baseline, 1 karena input uji alasan "TEST" (< 5 huruf,
K-14) → uji disesuaikan, lulus.

**Tindakan data (izin pemilik):** DB `kn_rnd_base` & `kn_uat_sim` dihapus (cadangan mongodump disimpan); 38 saldo
yatim di DB uji `kn_test_trial` dihapus (dicadangkan); data antar-PT DB uji diisi ulang. Catatan: uji
`tests/test_interco_g6.py` **mengosongkan seluruh koleksi antar-PT** di DB tempat ia dijalankan — jangan pernah
dijalankan ke DB UAT. Data "test" UAT (rantai SORD-261023-0003) **dibiarkan** atas keputusan pemilik.

**Fase 3 (disetujui 26 Okt, dikerjakan `8bbd1fe`…`e7d21bc`):** penggabungan layar duplikat (P16-K1 + D-01…D-29;
layar lama menjadi tautan/alias, form input HP tetap lengkap) dan tata letak L-04 → L-03 → L-01 & L-05 → L-09 —
laporan: [UAT24-AUDIT-UI-2-FASE3.md](UAT24-AUDIT-UI-2-FASE3.md) (rencana:
[`audit-ui-2/rencana-fase3.md`](audit-ui-2/rencana-fase3.md)).

## Belum dikerjakan
* **Sisa fase 3** (form HP PR MD/Kwitansi/Amandemen belum setara desktop, pop-up & tata letak di luar daftar paket,
  antrean persetujuan backend): lihat [UAT24-AUDIT-UI-2-FASE3.md](UAT24-AUDIT-UI-2-FASE3.md) › Belum dikerjakan.
* **Sebagian/backend lanjutan:** G1-33 eliminasi basi (perlu analisis); nama pengaju di matriks persetujuan, nomor
  dokumen di Jejak Audit & Cek Peran, kode wilayah di wizard entitas, host QR dari URL publik, filter
  `has_backorder` (rincian di `perbaikan/COORD.md` & laporan grup); tautan notifikasi nota kredit/desain ke dokumen
  (G5-09); saran Tanya KN tertutup kotak input (G5-62).
* **Data lama:** PR yang menunjuk PO batal sebelum perbaikan G4-12 & teks riwayat sample lama (G5-46) belum
  diperbaiki datanya (butuh skrip rekonsiliasi + izin); 6 segmen saldo basi di DB uji perlu rebuild.

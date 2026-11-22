# Skenario Uji Rekonsiliasi Bank — Rekening Koran Excel (R1–R9)

Pelatihan Keuangan · lanjutan materi 3.3 Kas & Bank (F10) · 18 November 2026

Setiap peserta memegang **rekening koran Excel (.xlsx) miliknya sendiri** — dibuat dari transaksi buku peserta itu —
lalu mencocokkannya di layar **Keuangan › Kas & Bank › Rekonsiliasi**. Sembilan skenario di bawah adalah alur lurus
masing-masing; urutannya R1 → R9 (R8 memakai hasil R2, R9 memakai hasil R1–R8). Setiap langkah sudah dijalankan di layar
dengan akun peserta (uji Playwright, `uji/rekonsiliasi/`) dan dicocokkan dengan buku (kas terekonsiliasi, jurnal seimbang).

| Kode | Situasi di rekening koran | Yang dilakukan peserta | Hasil di buku |
|---|---|---|---|
| R1 | Transfer masuk memuat **kode bayar** pesanan | Impor → Cocokkan otomatis | kas kwitansi Terekonsiliasi, tanpa jurnal baru |
| R2 | Transfer masuk **tanpa kode** (hanya nama) | Impor → Cocokkan otomatis → Terima usulan (skor 75) | idem |
| R3 | Transfer **keluar** ke pemasok, memuat nomor tagihan | Impor → Cocokkan otomatis | kas pembayaran Terekonsiliasi |
| R4 | **Satu** transfer untuk **dua** kwitansi | Cocokkan → Pecah → Kombinasi pas → Isi alokasi → Simpan | kedua kas Terekonsiliasi |
| R5 | **Dua** transfer untuk **satu** kwitansi | Centang 2 baris → Gabung ke 1 transaksi | kas Terekonsiliasi dari 2 baris |
| R6 | **Biaya administrasi** & **bunga** bank | Catat biaya bank · Catat bunga bank | kas + jurnal baru |
| R7 | Setoran **tanpa nama** | Titipkan → Dana Titipan → Alokasikan ke pesanan | jurnal titipan + jurnal alokasi, piutang turun |
| R8 | Tautan keliru | Lepas → Cocokkan → Tautkan | kas kembali Terekonsiliasi |
| R9 | Rekening koran **lengkap** diunggah ulang | Impor | 0 baris baru (tidak ada mutasi ganda) |

---

## 1. Yang berubah di sistem (18 Nov)

1. **Unggah Excel (.xlsx)** di *Impor mutasi bank* — tombol **Pilih berkas (Excel · CSV · MT940 · OFX)**. Unduhan internet
   banking dibaca apa adanya: baris pembuka (rekening, periode), tabel mutasi, dan ringkasan saldo di bawah baris kosong.
   Template bank dikenali otomatis dari judul kolom (sama seperti CSV); pratinjau menyebut **lembar** dan **baris judul
   kolom** yang dipakai. Berkas `.xls` lama (Excel 97–2003) ditolak dengan arahan *Simpan Sebagai Excel Workbook (.xlsx)*;
   batas 5 MB.
2. **Pecah (1:N)** — dulu daftar kandidat hanya transaksi bernominal ≈ transfer, sehingga kwitansi-kwitansi yang lebih
   kecil **tidak pernah tampil** dan pemecahan tidak bisa dilakukan lewat layar. Kini mode *Pecah ke beberapa transaksi*
   menampilkan transaksi yang bisa menjadi **bagian** transfer, dan kotak hijau **Kombinasi pas** menunjuk 2–3 transaksi
   yang jumlahnya persis sama dengan transfer; **Isi alokasi** mengisi nominalnya sekali klik.
3. **Gabung (N:1)** — kandidat dinilai terhadap **total mutasi yang dicentang** (dulu terhadap baris pertama saja); kandidat
   yang sisanya **pas sama** dengan total berada di urutan teratas, lengkap dengan alasan skornya.

## 2. Persiapan (pelatih)

Rekening yang dipakai: **BCA Operasional KSC** (PT Sukacita). Rekening ini dipakai bersama semua peserta — setiap baris
rekening koran memuat **"LATIHAN NN"** (NN = nomor peserta) dan nominalnya berakhiran nomor peserta, sehingga baris
peserta lain tidak tertukar.

Pesanan & kwitansi R1, R2, R4, R5, R7 dibuat atas nama **pelanggan rekonsiliasi** tersendiri per peserta —
*Latihan NN · Toko Rekon Peserta NN* — supaya sisa piutang dari bayar sebagian/titipan tidak mengubah angka pelanggan
latihan utama (*Toko Kain Peserta NN*) yang dipakai materi lain. Tagihan R3 memakai pemasok latihan peserta dan langsung
dibayar lunas. Prep `g_rekon` **tidak** ikut seed bawaan — hanya jalan bila disebut di `--hanya`.

```bash
# 1) Data buku per peserta (kwitansi, pembayaran tagihan, pesanan) — di server/kontainer backend, folder backend/
python scripts/seed_pelatihan_keuangan_kn.py --mulai 1 --peserta 30 --hanya a_dasar:akun,a_dasar:mitra,g_rekon
# 2) Rekening koran Excel per peserta dari data itu
python scripts/buat_mutasi_bank_latihan.py --mulai 1 --peserta 30 --keluar /tmp/mutasi_latihan
```

Keluaran per peserta (`peserta_NN/`):

| Berkas | Isi | Baris |
|---|---|---|
| `R1_kode_bayar_NN.xlsx` | TRSF E-BANKING CR *kode bayar* LATIHAN NN TOKO REKON PESERTA NN | 1 masuk |
| `R2_tanpa_kode_NN.xlsx` | TRSF E-BANKING CR LATIHAN NN TOKO REKON PESERTA NN | 1 masuk |
| `R3_bayar_pemasok_NN.xlsx` | TRSF E-BANKING DB *nomor tagihan* LATIHAN NN PEMASOK GREY PESERTA NN | 1 keluar |
| `R4_pecah_NN.xlsx` | … TOKO REKON PESERTA NN DUA NOTA | 1 masuk |
| `R5_gabung_NN.xlsx` | … TAHAP SATU · … TAHAP DUA | 2 masuk |
| `R6_biaya_bunga_NN.xlsx` | BIAYA ADM LATIHAN NN (Rp 15.000) · BUNGA LATIHAN NN | 1 keluar · 1 masuk |
| `R7_titipan_NN.xlsx` | SETORAN TUNAI CDM LATIHAN NN | 1 masuk |
| `R0_rekening_koran_lengkap_NN.xlsx` | semua baris R1–R7 dalam satu rekening koran | 9 |
| `manifest_NN.json` | daftar berkas, keterangan, nominal (untuk pelatih & uji) | — |

Bentuk berkas meniru unduhan KlikBCA Bisnis: baris 1–5 *Informasi Rekening* (No. rekening, Nama, Periode, Kode Mata
Uang), baris 7 judul kolom **Tanggal Transaksi · Keterangan · Cabang · Jumlah · Saldo**, nominal bergaya
`1,234,061.00 CR` / `DB`, lalu Saldo Awal / Mutasi Kredit / Mutasi Debet / Saldo Akhir di bawah baris kosong.
Tanggal setiap baris = tanggal transaksi buku peserta (jendela pencocokan ±3 hari tetap terpenuhi meski latihan
dilakukan di hari lain).

**Aturan pakai:** peserta mengunggah berkas **per skenario** R1 → R7 sesuai urutan. Berkas **R0** hanya dipakai di R9
(atau sebagai pengganti R1–R7 sekaligus — tetapi jangan keduanya untuk skenario yang sama; hasil "baris baru" berbeda).

Kartu Peserta memuat data pembanding tiap skenario (`--kartu`): *Rekon R1 · kwitansi kode bayar* (SO, kode bayar, kwitansi,
kas, nominal, tanggal) … *Rekon R7 · pesanan untuk titipan* (SO, pelanggan, total pesanan, nominal setoran).

---

## 3. Skenario

Semua skenario: login akun peserta `finance.latihNN@kainnusantara.id` → menu **Keuangan › Kas & Bank** → tab
**Rekonsiliasi** → pilih rekening **BCA Operasional KSC**. Sesudah impor/cocokkan, ketik **LATIHAN NN** di kotak cari
daftar mutasi supaya hanya baris Anda yang tampil.

### R1 · Transfer masuk dengan kode bayar — cocok otomatis

Data: Kartu Peserta *Rekon R1* — kwitansi transfer pelunasan pesanan; berita transfer memuat kode bayar pesanan itu.

| No | Navigasi | Yang dilakukan | Yang harus terlihat |
|---|---|---|---|
| 1 | Keuangan › Kas & Bank › Rekonsiliasi | Pilih rekening BCA Operasional KSC | Kartu ringkasan rekening; tombol **Impor mutasi bank** & **Cocokkan otomatis** |
| 2 | Impor mutasi bank › Pilih berkas | Pilih `R1_kode_bayar_NN.xlsx`; *Template bank* biarkan **Kenali otomatis dari isi berkas** → **Pratinjau** | "Berkas Excel R1_kode_bayar_NN.xlsx dipilih"; pratinjau "Terbaca **1** baris memakai template **BCA — Rekening Koran (CSV)** (dikenali otomatis) · lembar **Mutasi Rekening**, judul kolom di baris **7** · masuk Rp …" |
| 3 | Pop-up impor › Impor | Klik **Impor** | "Impor BCA — Rekening Koran (CSV): 1 baris baru, 0 dilewati (sudah pernah masuk)."; kartu Rekening menyebut "Impor terakhir: R1_kode_bayar_NN.xlsx oleh …" |
| 4 | Cocokkan otomatis | Klik **Cocokkan otomatis** → cari LATIHAN NN → klik angka **Skor** baris itu | Baris **Tercocok** · satu-satu · otomatis; *Transaksi buku* = kas kwitansi R1; alasan skor: "**Kode bayar KN-… cocok dengan pesanan KSC/SO-…**", Nominal sama +40, Tanggal sama +20 (skor ≥ 80) |
| 5 | Kas & Bank › Rekening & Saldo › kartu BCA › Mutasi | Cari kas kwitansi R1 | Kolom Rekonsiliasi = **Terekonsiliasi** |

Cek buku: kas kwitansi R1 `reconciled_amount` = nominal; **tidak ada jurnal baru** (pencocokan hanya menautkan).

### R2 · Transfer tanpa kode — usulan, tautkan manual

Data: *Rekon R2* — kwitansi transfer 90 % pesanan; berita transfer hanya nama pelanggan.

| No | Navigasi | Yang dilakukan | Yang harus terlihat |
|---|---|---|---|
| 1 | Rekonsiliasi › Impor mutasi bank | Pilih `R2_tanpa_kode_NN.xlsx` → Pratinjau → Impor | 1 baris baru |
| 2 | Cocokkan otomatis | Klik **Cocokkan otomatis** → cari LATIHAN NN | Baris **tetap Perlu keputusan** dengan tombol "**Terima usulan: KSC/CASH-… · Rp … (skor 75)**"; alasan skor: Nominal sama +40 · Tanggal sama +20 · nama mirip 'Latihan NN · Toko Rekon Peserta NN' +15 |
| 3 | Baris mutasi › Terima usulan | Periksa nominal, tanggal, nama = kwitansi R2 → klik **Terima usulan** | "Mutasi ditautkan ke KSC/CASH-… (skor 75)."; baris **Tercocok** · satu-satu (tanpa "otomatis") |
| 4 | Rekening & Saldo › BCA › Mutasi | — | kas kwitansi R2 **Terekonsiliasi** |

Mengapa tidak otomatis: tanpa kode bayar/nomor dokumen skornya 75, di bawah ambang otomatis 80 — sistem hanya
mengusulkan, manusia yang memutuskan. Bila sebuah *aturan pencocokan* untuk pola ini sudah **disetujui** (Pengaturan ›
Aturan bank, +15), baris ini tertaut otomatis — itu benar, bukan kesalahan.

### R3 · Transfer keluar ke pemasok — cocok otomatis lewat nomor tagihan

Data: *Rekon R3* — tagihan pemasok peserta (PO → terima → tagihan) dibayar penuh dari BCA.

| No | Navigasi | Yang dilakukan | Yang harus terlihat |
|---|---|---|---|
| 1 | Rekonsiliasi › Impor mutasi bank | Pilih `R3_bayar_pemasok_NN.xlsx` → Pratinjau → Impor | Pratinjau "… masuk Rp 0 · keluar Rp …", kolom Referensi berisi nomor tagihan (VB-…); 1 baris baru |
| 2 | Cocokkan otomatis | Klik **Cocokkan otomatis** → cari LATIHAN NN → klik Skor | Baris keluar **Tercocok** · otomatis ke kas "Pembayaran VB-…"; skor 100: Nominal sama +40 · Tanggal sama +20 · **nomor referensi 'VB-…' ada di transaksi buku +25** · nama mirip +15 |
| 3 | Rekening & Saldo › BCA › Mutasi | — | kas pembayaran **Terekonsiliasi**; tagihan tetap **Lunas** |

### R4 · Satu transfer untuk dua kwitansi — pecah 1:N

Data: *Rekon R4* — dua pesanan, dua kwitansi transfer (kas_1, kas_2); di bank hanya **satu** transfer sebesar jumlahnya.

| No | Navigasi | Yang dilakukan | Yang harus terlihat |
|---|---|---|---|
| 1 | Rekonsiliasi › Impor mutasi bank | Pilih `R4_pecah_NN.xlsx` → Pratinjau → Impor → **Cocokkan otomatis** | Baris "… DUA NOTA" **tetap Perlu keputusan** (tidak ada satu transaksi bernominal sama) |
| 2 | Baris "… DUA NOTA" › Cocokkan | Klik **Cocokkan** | Pop-up *Cocokkan mutasi bank*, mode *Satu transaksi*: "Tidak ada transaksi buku yang layak … Bila satu transfer ini melunasi beberapa transaksi, pilih **Pecah ke beberapa transaksi**." |
| 3 | Pop-up › Pecah ke beberapa transaksi | Klik **Pecah ke beberapa transaksi** | Kotak hijau "**Kombinasi pas:** KSC/CASH-… (Rp …) + KSC/CASH-… (Rp …) = Rp …"; kedua kas di urutan teratas dengan alasan "Bersama KSC/CASH-… pas menutup nominal transfer (+40)" |
| 4 | Kotak Kombinasi pas › Isi alokasi | Klik **Isi alokasi** → periksa nominal → **Simpan pemecahan (2 transaksi)** | "Sisa belum dialokasikan: **Rp 0**"; pesan "Satu transfer dipecah ke 2 transaksi buku (Rp …)."; baris **Tercocok** · 1 transfer → banyak, *Transaksi buku* menyebut kedua kas |
| 5 | Rekening & Saldo › BCA › Mutasi | — | kas_1 dan kas_2 **Terekonsiliasi** |

Pemecahan wajib menutup **seluruh** nominal transfer (sisa Rp 0) — sisa yang menggantung ditolak dengan arahan.

### R5 · Dua transfer untuk satu kwitansi — gabung N:1

Data: *Rekon R5* — satu kwitansi transfer; pelanggan mengirim **dua** transfer (± 60 % lalu sisanya).

| No | Navigasi | Yang dilakukan | Yang harus terlihat |
|---|---|---|---|
| 1 | Rekonsiliasi › Impor mutasi bank | Pilih `R5_gabung_NN.xlsx` → Pratinjau → Impor → **Cocokkan otomatis** | 2 baris baru (TAHAP SATU, TAHAP DUA), keduanya **Perlu keputusan** |
| 2 | Daftar mutasi | Centang kotak di kiri **kedua** baris | Bilah biru "**2 mutasi** dipilih · total Rp … — bisa digabung ke SATU transaksi buku" |
| 3 | Bilah biru › Gabung ke 1 transaksi | Klik **Gabung ke 1 transaksi** | Pop-up "Gabung 2 mutasi ke satu transaksi buku"; kandidat teratas = kas kwitansi R5, sisa = total, alasan "**Sisa transaksi pas sama dengan total mutasi terpilih** (+40)", skor 75 |
| 4 | Pop-up › baris kas | Klik baris kas kwitansi R5 | "2 mutasi digabung ke transaksi KSC/CASH-… (Rp …)."; kedua baris **Tercocok** · banyak → 1 |
| 5 | Rekening & Saldo › BCA › Mutasi | — | kas kwitansi R5 **Terekonsiliasi** (dari 2 baris) |

### R6 · Biaya administrasi & bunga bank — catat dari layar rekonsiliasi

Tidak ada data buku: bank memotong/menambah sendiri. Baris ini **bukan untuk diabaikan** — kalau diabaikan, bebannya hilang
dari laba rugi dan selisih rekening vs buku tidak pernah nol.

| No | Navigasi | Yang dilakukan | Yang harus terlihat |
|---|---|---|---|
| 1 | Rekonsiliasi › Impor mutasi bank | Pilih `R6_biaya_bunga_NN.xlsx` → Pratinjau → Impor | 2 baris baru: BIAYA ADM LATIHAN NN Rp 15.000 (keluar), BUNGA LATIHAN NN (masuk) |
| 2 | Baris BIAYA ADM › Catat biaya bank | Klik **Catat biaya bank** → periksa dialog → **Catat biaya bank** | Dialog "Catat biaya bank?" menyebut Rp 15.000 dan PT Sukacita; pesan "Biaya bank dibukukan (Dr Beban Adm Bank / Cr Bank)."; baris **Tercocok** · "Biaya bank · akun 6-8000" |
| 3 | Baris BUNGA › Catat bunga bank | Klik **Catat bunga bank** → periksa dialog → **Catat bunga bank** | Dialog "Catat bunga bank?" menyebut nominal; pesan "Bunga · jasa giro dibukukan (Dr Bank / Cr Pendapatan Bunga)."; baris **Tercocok** |
| 4 | Akuntansi & Pajak › Buku Besar › Jurnal | Cari "BUNGA LATIHAN NN" → buka jurnalnya | Jurnal bunga: **1-1100** Kas Besar / Bank Debit · **4-9000** Pendapatan Lain-lain Kredit |

Cek buku: dua kas baru di BCA (keluar Rp 15.000, masuk nominal bunga), keduanya Terekonsiliasi; jurnal biaya
**6-8000 Beban Administrasi Bank D / 1-1100 K**; jurnal bunga **1-1100 D / 4-9000 K**. Akun lawan mengikuti
*Pemetaan Akun* PT (`kas_bank.beban_bank`, `kas_bank.pendapatan_bunga`) — bila pemetaan diubah, akun di jurnal ikut berubah.
Biaya/bunga yang terlanjur dicatat bisa **Lepas** (dengan konfirmasi "Lepas & batalkan") — kas & jurnalnya dibatalkan
dengan jurnal pembalik.

### R7 · Setoran tanpa nama — titipkan lalu alokasikan

Data: *Rekon R7* — pesanan terkirim **belum dibayar**; nominal setoran = ± 65 % pesanan.

| No | Navigasi | Yang dilakukan | Yang harus terlihat |
|---|---|---|---|
| 1 | Rekonsiliasi › Impor mutasi bank | Pilih `R7_titipan_NN.xlsx` → Pratinjau → Impor → **Cocokkan otomatis** | Baris "SETORAN TUNAI CDM LATIHAN NN" **tetap Perlu keputusan**, tanpa usulan |
| 2 | Baris setoran › Titipkan | Klik **Titipkan** → periksa dialog → **Titipkan dana** | Dialog "Titipkan dana ini?" menyebut nominal; pesan "Dana dititipkan (jurnal Dr Bank / Cr Titipan terbit)."; status **Dititipkan**, "Sisa Rp …" |
| 3 | Tab **Dana Titipan** › Alokasikan | Klik **Alokasikan** → *Pelanggan* Latihan NN · Toko Rekon Peserta NN → isi nominal setoran pada pesanan R7 → *Alasan keputusan* **Dikonfirmasi pelanggan lewat bukti transfer** → *Catatan* → **Alokasikan** | Pesan "Titipan dialokasikan Rp … · sisa titipan **Rp 0**."; baris titipan: sudah dialokasikan = nominal, sisa Rp 0 |
| 4 | Piutang / Buku Besar | — | Sisa tagihan pesanan R7 turun sebesar setoran |

Cek buku: jurnal titipan **1-1100 Bank D / 2-1950 Titipan Dana Belum Teridentifikasi K**; jurnal alokasi
**2-1950 D / 1-1200 Piutang Usaha K** — tanpa kas ganda (kasnya sudah diakui saat dititipkan). Titipan yang belum ketemu pemiliknya
bisa diserahkan ke **Buka kasus** (Pusat Kasus Keuangan).

### R8 · Lepas & cocokkan ulang

Memakai baris R2 yang sudah Tercocok.

| No | Navigasi | Yang dilakukan | Yang harus terlihat |
|---|---|---|---|
| 1 | Rekonsiliasi › cari LATIHAN NN | Pada baris transfer R2 klik **Lepas** | "Tautan dilepas."; baris kembali **Perlu keputusan**; kas kwitansi R2 kembali belum terekonsiliasi |
| 2 | Baris itu › Cocokkan | Klik **Cocokkan** → kandidat teratas kas kwitansi R2 (skor 75) → **Tautkan** | "Mutasi ditautkan (skor 75)."; baris **Tercocok** lagi |
| 3 | — | — | kas kwitansi R2 Terekonsiliasi; tetap satu jurnal (lepas/tautkan tidak menyentuh jurnal) |

### R9 · Impor ulang rekening koran lengkap — tidak ada mutasi ganda

| No | Navigasi | Yang dilakukan | Yang harus terlihat |
|---|---|---|---|
| 1 | Rekonsiliasi › Impor mutasi bank | Pilih `R0_rekening_koran_lengkap_NN.xlsx` → Pratinjau → Impor | Pratinjau "Terbaca **9** baris"; pesan "… **0 baris baru, 9 dilewati** (sudah pernah masuk)." |
| 2 | Saringan status *Perlu keputusan* + cari LATIHAN NN | — | Tidak ada baris LATIHAN NN tersisa: 8 Tercocok + 1 Dititipkan |

## 4. Kesalahan umum

- **Memilih berkas .xls** (Excel 97–2003) → ditolak; buka di Excel lalu *Simpan Sebagai* → *Excel Workbook (.xlsx)*.
- **Memilih template yang salah** → pratinjau "Terbaca 0 baris" dengan alasan "judul kolom tidak dikenali"; kembalikan ke
  *Kenali otomatis dari isi berkas*.
- **Menerima usulan tanpa memeriksa** (R2) — usulan skor 60–79 berarti sistem RAGU; cocokkan nominal, tanggal, dan nama dulu.
- **Mengabaikan baris biaya/bunga** (R6) — gunakan *Catat biaya bank* / *Catat bunga bank*, bukan *Abaikan*.
- **Memecah dengan sisa menggantung** (R4) — sistem menolak; total alokasi harus sama dengan nominal transfer.
- **Mengunggah R0 sebelum R1–R7** — semua baris masuk sekaligus; hasil "1 baris baru" di tiap skenario tidak muncul lagi.
- **Bingung dengan baris peserta lain** — rekening BCA dipakai bersama; selalu cari "LATIHAN NN".

## 5. Uji otomatis

| Lapis | Berkas | Isi |
|---|---|---|
| Backend (tests_mem) | `backend/tests_mem/test_rekon_impor_excel.py` | P1–P6 pembaca Excel (BCA/Mandiri/BRI, lembar kedua, berkas rusak, judul tak dikenali), A1–A5 lewat API (pratinjau, impor, impor ulang, template eksplisit, berkas rusak/.xls) |
| Backend (tests_mem) | `backend/tests_mem/test_rekon_kandidat_pecah_gabung.py` | K1–K7 kandidat mode pecah/gabung, kombinasi pas, simpan pecah & gabung, mode tak dikenal 422 |
| Frontend (jest) | `frontend/src/features/finance/bank/__tests__/ReconImportPanel.excel.test.js`, `ReconMatchModal.pecah.test.js` | unggah .xlsx base64, tolak .xls; mode pecah meminta kandidat `split`, Isi alokasi, simpan |
| Uji jalan (Playwright) | `uji/rekonsiliasi/R1_kode_bayar.js` … `R9_impor_ulang.js` | langkah di atas, di layar dengan akun peserta + cek buku |

```bash
# Mesin dengan Node + Playwright (backend :8001, frontend :3000):
KN_PESERTA=NN bash docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/jalankan_rekon.sh
# Docker Desktop tanpa Node (tumpukan kn-dev): bangun kontainer uji sekali, lalu
docker build -t kn-uji-pw:1 docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/docker
KN_PESERTA=NN bash docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/jalankan_rekon_docker.sh
```

`KN_MUTASI` = folder berkas Excel (bawaan `docs/pelatihan/2026-11-18_keuangan/rekonsiliasi/mutasi`, tidak di-commit).
Hasil per skenario: `uji/hasil/R1 … R9/hasil.json` + tangkapan layar.

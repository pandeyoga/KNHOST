# Catatan editorial — skenario F01–F18 (17 Nov 2026)

Penyuntingan teks `src/skenario/F01.json` … `F18.json` mengikuti `PANDUAN_GAYA.md`. Yang diuji tidak berubah:
`kode`, `bagian`, `peran`, `menit`, `navigasi`, `uji`, jumlah dan urutan langkah (`no`, `peran`, `gambar`), jumlah simpul
`alur` (beserta `peran` dan ada/tidaknya `cabang`), serta `teks_rekening_koran.format` dan `contoh_peserta_03` di F10.
Semua berkas lolos `json.load`.

## Perubahan umum (semua skenario)

- Kunci baru `modul` (F01 → 0; F02–F06, F13, F14 → 3.1; F11, F12 → 3.2; F07–F10 → 3.3; F15 → 3.4; F16 → 3.5; F17, F18 → 4)
  dan `konsep` (3–4 butir per skenario).
- `tujuan` satu kalimat, `kapan` satu–dua kalimat. `aksi` berupa kalimat perintah dengan paling banyak dua tindakan;
  isian yang diketik dipindah ke `isi`. `hasil` hanya berisi apa yang terlihat (1–2 kalimat); penjelasan dipindah ke
  `konsep`, `cek_buku`, atau `catatan_pelatih`.
- Kunci kartu (`a_dasar:so_lunas` dsb.), nama kolom basis data (`deposit_balance`, `reconciled_amount`, status `paid`,
  `pending` …), kode izin (`credit_override.approve`, `payroll.void` …), nama berkas skrip, dan alamat API dihapus.
  Kartu Peserta disebut dengan labelnya ("Kartu Peserta › SO untuk pelunasan penuh").
- Contoh angka disamakan dengan tangkapan layar uji terakhir (17 Nov 09:10, akun peserta 02). Teks lama memakai angka
  dari uji sebelumnya (mis. Rp 3.359.692,50, Rp 411.924, denda Rp 21.560, gaji Budi Santoso Rp 708.760) yang tidak cocok
  dengan gambar.
- Keterangan jurnal kas ditulis "Kas masuk" / "Kas keluar".
- `cek_buku` ditulis "Akun (D/K) Rp …"; `kesalahan_umum` dipangkas menjadi 3–4 butir (butir yang dibuang dipindah ke
  `catatan_pelatih` bila masih penting).
- Wording "tab Mutasi" pada kartu rekening diganti "daftar mutasi": tangkapan layar F09/02, F09/06, dan F10/12 menunjukkan
  daftar mutasi langsung terbuka tanpa tab.

## Per skenario

**F01** — Teks disederhanakan; penjelasan Posisi/Analisis dipindah ke `konsep` dan `cek_buku`. Selisih dengan layar:
(1) catatan lama "Profil Saya menyebut jabatan Manajer" sudah tidak berlaku — gambar 11 menunjukkan Jabatan *Akunting*,
Departemen *Keuangan & Admin*; catatan dihapus. (2) Perlu Tindakan berisi 5 kelompok ("68 dokumen · 5 kelompok"), bukan 3;
kartu "Piutang lewat jatuh tempo" ditambahkan. (3) "Rincian: Akuntansi & Pajak › Laporan" di kartu Laba-Rugi YTD hanya
teks, bukan tombol.

**F02** — Contoh SO kini bernilai bulat (KSC/SO-00010 Rp 3.336.105), sesuai gambar. Cerita SO bernilai ,50 rupiah
dipindah ke `kesalahan_umum`/`catatan_pelatih`. Daftar kartu angka di Penagihan & Penerimaan ditulis umum karena tidak
terlihat jelas di gambar.

**F03** — Contoh angka diperbarui (Rp 3.300.863; 40% = Rp 1.320.345; sisa Rp 1.980.518). Tidak ada selisih dengan layar.

**F04** — Contoh angka diperbarui (sisa Rp 1.980.518, transfer Rp 2.000.000, titipan Rp 19.483). Perintah skrip pelatih
dipindah dari langkah 9 ke `catatan_pelatih`. **Risiko (perlu diputuskan):** aturan "bulatkan ke atas ke kelipatan
Rp 500.000" bisa menghasilkan kelebihan ≤ Rp 5.000; karena toleransi Rp 5.000, sistem kemungkinan memutusnya otomatis
sebagai pembulatan dan titipan tidak terbentuk. Ditambahkan saran di catatan pelatih (tambah Rp 500.000) — belum diuji.

**F05** — Denda contoh Rp 21.545 (bukan Rp 21.560). Selisih dengan layar: (1) gambar langkah 13 (`13-tab-rencana-denda.png`)
masih menampilkan layar Saldo & Umur sebelum tab diklik; hasil yang diuraikan baru terlihat di gambar 14. (2) **Kemungkinan
bug:** di gambar 14, saat kotak cari berisi nomor nota, kartu RENCANA AKTIF dan tab Jadwal Pembayaran menunjukkan 0
(di langkah 4 bernilai 1), sedangkan kartu DENDA TERBIT tidak ikut tersaring — kartu ringkasan tidak konsisten terhadap
filter. Dicatat di `catatan_pelatih` agar peserta tidak bingung.

**F06** — Teks disederhanakan; kode izin dihapus. Tidak ada selisih dengan layar.

**F07** — Tiga klik konfirmasi digabung menjadi satu kalimat per langkah. Selisih: keterangan jurnal LPJ di layar berbunyi
"Pertanggungjawaban **petty cash** KSC/STL-…" (bahasa campuran, sedangkan menu memakai "Kas Kecil") — usul perbaiki label.

**F08** — Pengaturan teknis (`pembayaran.sales_terima_tunai`, titik henti H5) diganti nama pengaturan di layar. Tidak ada
selisih dengan layar.

**F09** — Contoh nominal peserta 02 = Rp 320.000 (sesuai gambar). Selisih: tidak ada "tab Mutasi" pada jendela rekening
(lihat perubahan umum).

**F10** — Templat rekening koran tetap di `isi` langkah 2 (satu-satunya tempat yang dicetak); aturan penulisan
diringkas di `isi` dan `teks_rekening_koran.aturan` (tanpa kunci kartu). Selisih: kesalahan lama "klik *Catat sebagai
kwitansi* pada transfer yang kwitansinya sudah ada" tidak bisa terjadi — gambar 03 menunjukkan tombol itu tidak tampil
untuk baris yang pesanannya sudah punya kwitansi; butir diganti "menautkan kandidat milik peserta lain".

**F11** — Tidak ada selisih pada langkah. **Kemungkinan bug:** (1) sesudah dibayar, bagian "Pembayaran" di rincian
tagihan menampilkan tautan **[Batalkan]** untuk akun Finance (gambar 07) — periksa apakah Finance memang boleh
membatalkan pembayaran; (2) "Dokumen Terkait" menulis kunci internal "Jurnal · Terposting · **vendor_bill**", dan Riwayat
memakai bahasa Inggris ("Vendor Bill dibuat", "Bill di-posting (AP diakui)", "auto-posted (match bersih)").

**F12** — Teks disederhanakan; kode izin dihapus. **Kemungkinan bug (tampilan):** kartu NILAI FAKTUR / NILAI BERSIH / SISA
memotong angka menjadi "Rp 1.287.60" + "0" di baris berikutnya (gambar 07, 08, 11, 16). "Penerimaan barang terkait"
menampilkan "tugas 945058 · completed" (status bahasa Inggris dan nomor tugas mentah).

**F13** — Alamat API pada catatan tombol cetak dihapus. Tidak ada selisih dengan layar.

**F14** — Status di layar "Siap Ke Gudang" (teks lama "Siap ke gudang"). Kalimat "SOS berstatus bayar Lunas" dihapus
karena tidak terlihat di layar.

**F15** — Contoh diperbarui: KSC/PAY-00004, Rp 721.920, karyawan Dewi Manager, setoran PPh 21 Rp 30.080 (teks lama:
Budi Santoso Rp 708.760, PPh 21 Rp 45.240).

**F16** — Selisih: gambar 02, 03, dan 11 menampilkan keterangan "**Kas in** · Penerimaan …" karena jurnal dibuat skrip
sebelum perbaikan kata; teks memakai "Kas masuk". Bila data tidak disiapkan ulang sebelum pelatihan, peserta akan
melihat "Kas in" (dijelaskan di `catatan_pelatih`). **Kemungkinan bug:** jendela jurnal "Pendapatan Kirim" (gambar 05,
jurnal non-kas) menampilkan tombol [Bukti Kas Keluar] dan [Bukti Kas Masuk].

**F17** — Selisih yang diperbaiki: (1) Neraca menunjukkan 1-9999 Suspense −Rp 2.000.000 dan 1-1150 Kas & Bank Transit
−Rp 10.000.000 (teks lama: Suspense −Rp 12.000.000); (2) "Saldo akhir" buku besar 4-1000 (Rp 151.937.850) sama dengan
baris 4-1000, bukan total Pendapatan Laba-Rugi (Rp 151.981.793, termasuk denda 4-9300); (3) Arus Kas memakai metode
langsung ("Penerimaan/pengeluaran kas atas pendapatan & beban"), bukan "dimulai dari laba bersih". Catatan untuk pemilik:
Arus Kas operasi memuat baris 1-1150 Kas & Bank Transit +Rp 10.000.000.

**F18** — Contoh beban Oktober Rp 54.364.612 (teks lama ±Rp 50,6 jt). Selisih: September bukan bulan kosong — ada
penggajian KSC/PAY-00002 "Menunggu pengesahan", sehingga butir daftar periksa "Perlu Dilihat" dan jendela tutup buku
memberi peringatan; dicatat di `catatan_pelatih`. **Kemungkinan bug (kata):** peringatan di jendela berbunyi
"Penggajian periode ini sudah diposting: Penggajian belum diposting: KSC/PAY-00002 …" — judul butir tergabung dengan
pesan gagalnya sehingga terbaca bertentangan.

## Perlu diputuskan koordinator

1. **Label Kartu Peserta.** Teks memakai label dari instruksi (SO untuk pelunasan penuh · SO untuk bayar sebagian ·
   Pelanggan cicilan · Izin kredit · PD kas kecil · Titipan sales · Kwitansi transfer · Tagihan pemasok untuk dibayar ·
   Tagihan untuk kontrabon · Pesanan sample berbayar · Gaji susulan · SO lunas untuk penelusuran) ditambah **Akun** (F01)
   dan **Tagihan berikutnya** (F04). Label yang tercetak sekarang berbeda di dua tempat: `bangun.py` (KARTU, mis.
   "SO untuk bayar sebagian & lebih bayar", "Tagihan supplier untuk dibayar") dan skrip data latihan (LABEL, mis.
   "F02/F13 SO pelunasan penuh"). Samakan agar peserta menemukan baris yang disebut.
2. `bangun.py` belum menampilkan `konsep` dan `modul`; manual, LEMBAR_LATIHAN, dan PowerPoint perlu dibangun ulang
   (tidak dijalankan di sini).
3. F16: siapkan ulang data atau ambil ulang tangkapan layar agar tertulis "Kas masuk".
4. F05 langkah 13: ganti gambar atau biarkan (gambar memperlihatkan layar sebelum klik).
5. F04: putuskan apakah aturan nominal transfer diubah untuk menghindari kelebihan ≤ Rp 5.000.

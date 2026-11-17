# Paket Pelatihan Keuangan — 18 November 2026

Pelatihan untuk petugas keuangan (akun Finance) dan manajer keuangan di ERP Kain Nusantara. Materi disusun mengikuti
urutan kerja keuangan yang sebenarnya, dan **setiap materi dijalankan di layar** (Playwright, akun peran yang sama dengan
peserta) **lalu dicocokkan dengan buku** (jurnal seimbang, saldo, status dokumen) sebelum dipakai.

## Susunan materi (`src/kurikulum.json`)

| Bagian | Isi | Materi |
|---|---|---|
| 0. Pengantar | Tujuan, siapa mengerjakan apa, cara membaca panduan, akun & Kartu Peserta, cara menuju layar, istilah, orientasi Finance | 0.1 (F01) |
| 1. Fondasi & Konfigurasi | Bagan Akun (COA) → pemetaan akun → profil PT & periode → rekening kas/bank → aturan keuangan & pajak → termin & plafon → hak akses & persetujuan → nomor & naskah dokumen → konfigurasi SDM | 1.1–1.9 (K01–K09) |
| 2. Alur Ujung ke Ujung | Pesanan sampai Uang Masuk · Pengadaan sampai Bayar · Retur penjualan & pembelian · Karyawan sampai Gaji Dibayar · dari Jurnal sampai Laporan & Tutup Buku — siapa mengerjakan apa, dokumen yang lahir, **jurnal di setiap tahap**, titik kontrol | 2.1–2.5 (A1–A5) |
| 3. Praktik Finance per Siklus | 3.1 Piutang · 3.2 Hutang · 3.3 Kas & Bank · 3.4 SDM & Gaji · 3.5 Buku Besar & Dokumen | F02–F16, H01–H04 |
| 4. Manajer | Laporan keuangan · tutup buku | 4.1–4.2 (F17, F18) |
| 5. Situasi Khusus & Koreksi | Amandemen penjualan (nota kredit/debit) · amandemen PO, terima & tagih sebagian, selisih harga · kirim bertahap, uang muka, batal pesanan, satu transfer banyak tagihan, biaya bank · batal bayar, batal kwitansi, anulir gaji, balik jurnal, reklasifikasi | 5.1–5.4 (S1–S4) |

SDM & penggajian dipegang Finance (keputusan pemilik 17 Nov, K-SDM-01): Finance menyiapkan karyawan, kehadiran, masukan
gaji, menghitung & memposting proses gaji, membayar dan menyetor; Manajer mengesahkan dan membatalkan.

## Berkas

| Berkas | Isi |
|---|---|
| `Panduan_Pelatihan_Keuangan_ERP_Kain_Nusantara.pdf` | Manual utama A4 per bagian: halaman pembuka bagian, konsep inti, alur, jurnal di setiap tahap & titik kontrol (alur ujung ke ujung), cara menuju layar, langkah (lakukan › isian › yang harus terlihat) dengan tangkapan layar, cek buku, kesalahan umum, catatan pelatih, rekap uji, evaluasi |
| `Panduan_Pelatihan_Keuangan_ERP_Kain_Nusantara.html` | Versi HTML yang sama (gambar JPEG di `gambar/`; PNG asli uji jalan di `uji/hasil/` tidak di-commit) |
| `Panduan_Pelatihan_Keuangan_ERP_Kain_Nusantara_Ringkas.pdf` | Manual versi cetak (tanpa tangkapan layar per langkah) |
| `Presentasi_Pelatihan_Keuangan_ERP_Kain_Nusantara.pptx` | Slide kelas (16:9) dengan susunan yang sama: urutan pelatihan, siapa mengerjakan apa, halaman tiap bagian, lalu per materi: pembuka, konsep inti, alur, jurnal di setiap tahap + titik kontrol, cara menuju layar ①②③, satu slide per langkah (tangkapan layar + lakukan & yang harus terlihat), hasil di buku & kesalahan umum. Rincian di catatan pembicara |
| `LEMBAR_LATIHAN.md` | Lembar centang peserta per langkah + kolom temuan |
| `LAPORAN_AUDIT.md` | Temuan audit: yang diperbaiki (berkas + uji), yang perlu keputusan pemilik, catatan pelatih |
| `src/kurikulum.json`, `src/PANDUAN_GAYA.md` | Urutan bagian & aturan bahasa/bentuk materi |
| `src/skenario/*.json`, `src/alur_e2e/*.json` | Sumber materi (K = konfigurasi, F = praktik, H = SDM, A = alur ujung ke ujung) |
| `src/bangun.py`, `src/cetak_pdf.js`, `src/ppt/*` | Pembangun manual (HTML/PDF/lembar) dan slide |
| `uji/` | Uji jalan per materi: `F*.js`, `konfigurasi/K*.js`, `sdm/K09, H*.js`, `e2e/A*.js`, `situasi/S*.js`; hasil di `uji/hasil/<kode>/hasil.json` + tangkapan layar |
| `uji/situasi/S1–S4_*.js` | Uji jalan Bagian 5 (situasi khusus & koreksi) di peserta peraga tersendiri |
| `uji/variasi/`, `uji/dokumen/` | Uji variasi isian & hitungan (Lampiran A), dokumen cetak + pengaturan naskah (Lampiran B), dan V9: bukti setiap klaim di teks materi (`src/variasi_klaim_materi.json`) |

## Data latihan

`backend/scripts/seed_pelatihan_keuangan_kn.py` (+ modul `backend/scripts/latih_keuangan/`) menyiapkan data **per peserta**
lewat endpoint resmi: akun `finance.latihNN@kainnusantara.id` (peran Finance, hanya PT Sukacita), pelanggan
`Latihan NN · Toko Kain Peserta NN`, pemasok `Latihan NN · Pemasok Grey Peserta NN`, dokumen awal praktik, serta isian SDM
(Kartu Peserta › Karyawan baru). Dijalankan ulang aman (yang sudah ada dilewati); `--kartu` mencetak Kartu Peserta;
`--nonaktifkan` menonaktifkan akun latihan sesudah pelatihan. Alur ujung ke ujung diperagakan pelatih pada nomor peserta
peraga tersendiri (mis. 21, 31, 41–43) agar dokumen latihan peserta kelas tidak terpakai.

## Membangun ulang dokumen

```bash
python docs/pelatihan/2026-11-18_keuangan/src/bangun.py
```

Slide PowerPoint (butuh `pptxgenjs`, mis. di folder lain lewat `NODE_PATH`):

```bash
python docs/pelatihan/2026-11-18_keuangan/src/ppt/siapkan_data.py && node docs/pelatihan/2026-11-18_keuangan/src/ppt/render_alur.js && node docs/pelatihan/2026-11-18_keuangan/src/ppt/buat_ppt.js
```

## Menjalankan uji jalan (lingkungan lokal)

Semua materi berurutan sesuai kurikulum (praktik di akun peserta kelas; alur ujung ke ujung di peserta peraga), lalu potret
panduan navigasi:

```bash
KN_PESERTA=01 bash docs/pelatihan/2026-11-18_keuangan/uji/jalankan_semua.sh
```

Satu materi: `node docs/pelatihan/2026-11-18_keuangan/uji/F02_pelunasan_penuh.js` (nomor peserta: `KN_PESERTA=07`).
Materi memakai dokumen peserta, jadi peserta yang sudah dipakai tidak bisa diulang — siapkan peserta baru
(`seed_pelatihan_keuangan_kn.py --mulai 07 --peserta 07`).

## Urutan & catatan kelas

- Fondasi dulu: peserta tahu akun apa yang akan terisi sebelum mencatat transaksi.
- Beberapa peragaan Fondasi mengubah pengaturan bersama dan **wajib dikembalikan segera** (K02, K05, K08) — lihat
  `LAPORAN_AUDIT.md` § 4.
- Piutang wajib F02 → F03 → F04 → F05 → F06; Hutang F11 sebelum F12; SDM H01 → H02 → H03 → H04 → F15.
- F04 langkah 9 dijalankan pelatih (membuat tagihan berikutnya) sesudah semua peserta selesai langkah 8.
- Tutup buku (F18) diperagakan pelatih pada bulan kosong; jangan menutup Oktober/November.
- Selengkapnya: `LAPORAN_AUDIT.md` § 4.

# Paket Pelatihan Keuangan — 18 November 2026

Pelatihan satu hari untuk petugas keuangan (akun Finance) dan manajer keuangan di ERP Kain Nusantara.
Setiap skenario **dijalankan di layar** (Playwright, akun peran yang sama dengan peserta) **dan dicocokkan dengan buku**
(jurnal seimbang, saldo, status dokumen) sebelum dipakai.

| Berkas | Isi |
|---|---|
| `Panduan_Pelatihan_Keuangan_ERP_Kain_Nusantara.pdf` | Panduan utama A4: cara pakai, jadwal, kartu peserta, peta menu, istilah, skenario langkah demi langkah (menu › tombol › isian › yang harus terlihat › cek buku › kesalahan umum › catatan pelatih) dengan tangkapan layar, rekap uji, evaluasi |
| `Panduan_Pelatihan_Keuangan_ERP_Kain_Nusantara.html` | Versi HTML yang sama (gambar JPEG di `gambar/`; PNG asli uji jalan di `uji/hasil/` tidak di-commit) |
| `Presentasi_Pelatihan_Keuangan_ERP_Kain_Nusantara.pptx` | Slide kelas (16:9): pembuka (cara belajar, jadwal, peta alur uang, cara navigasi, peta menu, akun & Kartu Peserta, istilah) lalu per skenario: pembuka (tujuan, kapan dipakai), alur, cara menuju layar bertanda ①②③, satu slide per langkah (tangkapan layar + inti *lakukan* & *yang harus terlihat*), hasil di buku & kesalahan umum. Rincian lengkap di catatan pembicara; detail di manual |
| `Panduan_Pelatihan_Keuangan_ERP_Kain_Nusantara_Ringkas.pdf` | Manual versi cetak (tanpa tangkapan layar per langkah) |
| `LEMBAR_LATIHAN.md` | Lembar centang peserta per langkah + kolom temuan |
| `LAPORAN_AUDIT.md` | Temuan audit selama penyusunan skenario: yang diperbaiki (berkas + uji) dan yang perlu keputusan pemilik |
| `src/skenario/Fxx.json` | Sumber tiap skenario (langkah, hasil, cek buku) |
| `src/bangun.py`, `src/cetak_pdf.js` | Pembangun HTML/PDF/Lembar |
| `uji/lib.js`, `uji/Fxx_*.js` | Uji jalan per skenario (layar + buku); hasil di `uji/hasil/Fxx/hasil.json` + tangkapan layar |

## Data latihan

`backend/scripts/seed_pelatihan_keuangan_kn.py` (+ modul `backend/scripts/latih_keuangan/`) menyiapkan data **per peserta**
lewat endpoint resmi: akun `finance.latihNN@kainnusantara.id` (peran Finance, hanya PT Sukacita), pelanggan
`Latihan NN · Toko Kain Peserta NN`, pemasok `Latihan NN · Pemasok Grey Peserta NN`, serta dokumen awal tiap skenario.
Dijalankan ulang aman (yang sudah ada dilewati); `--kartu` mencetak Kartu Peserta; `--nonaktifkan` menonaktifkan akun latihan
sesudah pelatihan.

## Membangun ulang dokumen

```bash
python docs/pelatihan/2026-11-18_keuangan/src/bangun.py
```

Slide PowerPoint (butuh `pptxgenjs`, mis. di folder lain lewat `NODE_PATH`):

```bash
python docs/pelatihan/2026-11-18_keuangan/src/ppt/siapkan_data.py && node docs/pelatihan/2026-11-18_keuangan/src/ppt/render_alur.js && node docs/pelatihan/2026-11-18_keuangan/src/ppt/buat_ppt.js
```

## Menjalankan uji jalan (lingkungan lokal)

Semua skenario berurutan (urutan kelas) untuk satu peserta, lalu potret panduan navigasi:

```bash
KN_PESERTA=01 bash docs/pelatihan/2026-11-18_keuangan/uji/jalankan_semua.sh
```

Satu skenario: `node docs/pelatihan/2026-11-18_keuangan/uji/F02_pelunasan_penuh.js` (nomor peserta: `KN_PESERTA=07`).
Skenario memakai dokumen peserta, jadi peserta yang sudah dipakai tidak bisa diulang — siapkan peserta baru
(`seed_pelatihan_keuangan_kn.py --mulai 07 --peserta 07`).

## Urutan & catatan kelas

- Piutang wajib F02 → F03 → F04 → F05 → F06; Hutang F11 sebelum F12.
- F04 langkah 7 dijalankan pelatih (membuat tagihan berikutnya) sesudah semua peserta selesai langkah 6.
- F07 (persetujuan LPJ), F12 (kontrabon: Manajer & Admin), F17–F18 (Manajer) memakai akun pelatih.
- Tutup buku (F18) diperagakan pelatih pada bulan kosong; jangan menutup Oktober/November.
- Selengkapnya: `LAPORAN_AUDIT.md` § 4.

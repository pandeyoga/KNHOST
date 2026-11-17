# Paket Pelatihan Keuangan — 18 November 2026

Pelatihan satu hari untuk petugas keuangan (akun Finance) dan manajer keuangan di ERP Kain Nusantara.
Setiap skenario **dijalankan di layar** (Playwright, akun peran yang sama dengan peserta) **dan dicocokkan dengan buku**
(jurnal seimbang, saldo, status dokumen) sebelum dipakai.

| Berkas | Isi |
|---|---|
| `Panduan_Pelatihan_Keuangan_ERP_Kain_Nusantara.pdf` | Panduan utama A4: cara pakai, jadwal, kartu peserta, peta menu, istilah, skenario langkah demi langkah (menu › tombol › isian › yang harus terlihat › cek buku › kesalahan umum › catatan pelatih) dengan tangkapan layar, rekap uji, evaluasi |
| `Panduan_Pelatihan_Keuangan_ERP_Kain_Nusantara.html` | Versi HTML yang sama (gambar dari `uji/hasil/`) |
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

## Menjalankan uji jalan (lingkungan lokal)

```bash
node docs/pelatihan/2026-11-18_keuangan/uji/F02_<nama>.js
```

Nomor peserta uji dapat diganti dengan `KN_PESERTA=07`.

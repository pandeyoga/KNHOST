# Paket UAT End-to-End — ERP Kain Nusantara (v3.0)

**Pakai v3.0 untuk pelaksanaan UAT** (22 Okt 2026): 1 hari, mulai **09.00 WIB**, dua kelompok paralel.

| Berkas v3.0 | Isi |
|---|---|
| `Panduan_UAT_E2E_ERP_Kain_Nusantara_v3.0.pdf` | Panduan utama, A4 lanskap, 46 halaman: cara pakai, daftar 16 alur, jadwal 1 hari (2 kelompok), **16 alur end-to-end lurus** (satu cabang = satu alur dari pesanan sampai diterima & lunas; 305 langkah dengan peran·akun, navigasi menu › antrean › tombol, yang diisi, hasil yang harus terlihat, status cek di layar, kolom Lulus/Gagal), data & akun, rekap, form temuan, tanda tangan |
| `Panduan_UAT_E2E_ERP_Kain_Nusantara_v3.0.html` | Versi HTML yang sama |
| `LEMBAR_HASIL_UAT_v3.md` | Lembar hasil yang bisa diedit (305 langkah + penutupan) |
| `src/v3_steps.py`, `src/v3_scenarios.py`, `src/v3_build.py` | Sumber v3 — `python docs/uat/2026-10-21/src/v3_build.py` |

Status cek layar: S1 & S2 seluruh langkah sudah dijalankan di layar dengan akun peran (21–22 Okt 2026);
S3, S4, S6 sebagian (langkah bersama S1); alur lain belum dijalankan di layar — langkahnya ditandai ○ di dokumen.

---

## Arsip v2.0 (21 Okt 2026, diganti v3.0)

Production IT PT Kubus Teknologi Indonesia · disusun 21 Oktober 2026 · menggantikan paket KN-UAT-OPS-001 v1.0.

| Berkas | Isi |
|---|---|
| `Panduan_UAT_E2E_ERP_Kain_Nusantara_v2.0.pdf` | Panduan utama, A4 lanskap, 65 halaman: peta besar end-to-end, 40 titik keputusan, jadwal 2 hari per sesi, kesiapan, data & akun, 19 diagram alur bercabang (A–I) + tabel langkah (navigasi menu › tab › tombol, aktivitas, keputusan, hasil, status uji pra-UAT), akses (J), konsistensi (K), hasil uji pra-UAT, 17 temuan, rencana perbaikan, lembar hasil, berita acara |
| `Panduan_UAT_E2E_ERP_Kain_Nusantara_v2.0.html` | Versi HTML yang sama (bisa dibuka di browser) |
| `RENCANA_PERBAIKAN_TEMUAN_UAT.md` | Detail teknis tiap temuan: reproduksi, akar masalah (berkas:baris), perbaikan, uji regresi, keputusan owner |
| `LEMBAR_HASIL_UAT.md` | Lembar hasil yang bisa diedit (138 langkah + J/K + form temuan + penutupan) |
| `SKENARIO_UAT.json` | Data terstruktur: jadwal, keputusan, alur & langkah, akses, konsistensi, temuan (status awal `NOT_RUN`) |
| `uji_pra_uat/` | Skrip uji API yang dipakai tim IT (dijalankan di container backend) |
| `src/` | Sumber dokumen (Python, tanpa dependensi luar) |

## Membangun ulang PDF

```bash
python docs/uat/2026-10-21/src/build.py
```

Membutuhkan Chrome/Edge di Windows dan container `backend` (PyMuPDF) untuk nomor halaman daftar isi.
`python src/export.py` membuat ulang `LEMBAR_HASIL_UAT.md` dan `SKENARIO_UAT.json` dari sumber yang sama.

## Status

Semua langkah **belum diuji peserta**. Uji pra-UAT tim IT (data acuan lokal) menemukan 17 temuan; 11 di antaranya
dikonfirmasi ulang pada `main @ a3f7936` + perubahan lokal (21 Okt 03.05). Pesanan Khusus belum diuji karena
modulnya berubah selama penyusunan.

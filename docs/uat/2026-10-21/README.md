# Paket UAT End-to-End — ERP Kain Nusantara (v2.0)

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

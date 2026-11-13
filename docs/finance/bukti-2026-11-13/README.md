# Bukti uji — audit keuangan 13 Nov 2026

Skrip di folder ini menjalankan **kode KNHOST apa adanya** (`backend/services/*`) di atas MongoDB **tiruan dalam memori**
(`mongomock`), dengan jurnal dan dokumen contoh yang kecil sehingga hasilnya bisa dicocokkan dengan hitungan tangan.
Tidak ada database nyata yang disentuh, tidak ada kode aplikasi yang diubah. Ini bukti audit, bukan gate dan bukan
bagian aplikasi.

Laporan induk: [`../AUDIT_KEUANGAN_2026-11-13.md`](../AUDIT_KEUANGAN_2026-11-13.md) §14.

| Berkas | Isi |
|---|---|
| `boot.py` | Mengganti klien MongoDB dengan `mongomock_motor` sebelum `backend/db.py` diimpor |
| `skenario1.py` | Laporan inti (Laba-Rugi, Neraca, Neraca Saldo, Buku Besar, tutup buku) vs hitungan tangan — 19 titik uji |
| `skenario2.py` | Reproduksi GL-07, IC-05, GL-01, IC-01, IV-01 |
| `skenario3.py` | Reproduksi FX-02, GL-01 (membalik jurnal pembalik otomatis), GL-04 |
| `HASIL.txt` | Keluaran ketiga skrip pada `ec79643`+ (dijalankan 13 Nov 2026, Python 3.11.18) |

## Menjalankan ulang

```bash
python3.11 -m venv /tmp/venv-audit && . /tmp/venv-audit/bin/activate
pip install motor==3.3.1 pymongo==4.6.3 fastapi==0.110.1 pydantic==2.13.5 python-dotenv==1.2.3 bcrypt==4.1.3 mongomock-motor==0.0.36
cd docs/finance/bukti-2026-11-13 && python skenario1.py && python skenario2.py && python skenario3.py
```

## Batas

- `mongomock` bukan MongoDB asli: perilaku balapan, indeks unik parsial, dan kinerja **tidak** teruji di sini. Skrip tidak
  membuat indeks; idempotensi yang teruji adalah cek-lalu-sisip di kode.
- Fungsi layanan dipanggil langsung, tanpa lapisan HTTP: izin peran, pagar entitas di router, dan middleware tidak ikut
  teruji. Untuk IC-05, yang dibuktikan adalah bahwa layanan memakai entitas dari isi permintaan; bahwa router tidak
  memeriksanya dibaca dari kode (`backend/routers/gl.py:147-159`).
- Data contoh sengaja kecil dan bersih. Skrip membuktikan bahwa rumus dan jalur itu berperilaku seperti tertulis, bukan
  bahwa data nyata Anda benar atau salah.
- `skenario3.py` memakai tanggal hari ini; bagian GL-04 menutup bulan berjalan dan bulan berikutnya relatif terhadap
  tanggal uji (13 Nov 2026).

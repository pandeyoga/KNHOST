# Bukti uji — audit konfigurasi dan peran, 13 Nov 2026

Skrip di folder ini menyalakan **aplikasi KNHOST utuh** (`backend/server.py` beserta proses awal dan seed-nya) di atas
MongoDB tiruan dalam memori, lalu memanggil endpoint lewat HTTP di dalam proses. Tidak ada database nyata yang disentuh
dan tidak ada kode aplikasi yang diubah. Laporan induk:
[`../AUDIT_KONFIGURASI_PERAN_2026-11-13.md`](../AUDIT_KONFIGURASI_PERAN_2026-11-13.md).

Cara memasang lingkungan dan pola uji: `docs/blueprint/03_LINGKUNGAN_UJI.md` §3.

| Berkas | Yang diuji | Hasil pada `dca195b` |
|---|---|---|
| `boot_app.py` | Mengganti klien MongoDB dengan `mongomock-motor` sebelum aplikasi diimpor | Aplikasi menyala: 1.754 rute, 100 koleksi, 4 akun, 3 PT |
| `inv_endpoints.py` | Inventaris statik gerbang tiap endpoint | 1.749 endpoint: 1.566 izin · 17 izin lewat cabang · 38 nama peran · 107 hanya login · 21 tanpa sesi |
| `t1_config.py` | Tiap kunci Pusat Pengaturan: tulis → baca lewat 3 jalur → lapisan PT → nilai tak sah → pulihkan | 310 kunci; 287 tulis grup dan 242 tulis PT terbaca benar; 264 nilai tak sah ditolak; 97 wajib-alasan ditolak; 2 penyimpangan (PT non-PKP) |
| `t2_roles.py` + `t2_analyze.py` | 12 peran bawaan + 4 peran kustom uji × 786 rute baca, dibandingkan dengan matriks | Rute berizin mengikuti matriks; peran kustom beracuan Manajer tanpa izin tetap lolos 23 rute |
| `t3_escalation.py` | Siapa bisa mengubah pengaturan; peran kustom mengubah peran lain | Pemegang `settings.manage`: 0 dari 232 kunci bisa diubah; peran beracuan Manajer tanpa izin: bisa mengubah 48 kunci |
| `t3b_eskalasi_akun.py` | Peran kustom pengelola akun | Menjadikan diri Admin: 200 · reset sandi Admin: 200 · membuat peran beracuan Manajer: 200 |
| `t4_peran_bawaan.py` | Perubahan izin peran bawaan setelah proses awal dijalankan ulang; pindah-massal akun Admin | Izin yang dicabut kembali; akun Admin aktif dari 1 menjadi 0 |
| `t5_jadwal_pengaturan.py` | Perubahan pengaturan berjadwal: kapan dipakai mesin | Pembaca baru tepat waktu; pembaca lama baru setelah layar Pengaturan dibuka |
| `t6_fx01_setoran_ganda.py` | Temuan FX-01 dari audit keuangan, lewat API | Setor 10.000.000 → 2 kas masuk (20.000.000); saldo 1-1280 menjadi −10.000.000 |
| `fe_be_routes.py` | Tiap panggilan API di layar punya rute | 1.790 panggilan; 1 tanpa rute (`GET /api/products/{id}`) |

Catatan: `t3_escalation.py` baris (d3) mengirim isi permintaan yang bentuknya salah (dijawab 422); uji yang benar untuk
butir itu ada di `t3b_eskalasi_akun.py`.

## Batas

- Database tiruan tidak mendukung indeks unik parsial, balapan, maupun transaksi. `boot_app.py` membuat ulang indeks
  yang ditolak tanpa sifat unik (daftarnya di `boot_app.SKIPPED_INDEXES`) dan menambal `find_one_and_update` supaya
  pola klaim atomik berperilaku seperti MongoDB asli. T1–T5 dijalankan sebelum tambalan kedua; tidak ada yang
  bergantung padanya.
- Data hanya seed awal. Rute yang butuh dokumen dijawab 404 dan dihitung "lolos gerbang".
- Permintaan tulis hanya diuji untuk pengaturan, peran, dan akun. Endpoint tulis lain memvalidasi isi permintaan lebih
  dulu, sehingga gerbang izinnya tidak teruji tanpa isi yang sah.
- Layar tidak dibuka; semua penilaian layar berasal dari membaca kode.

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
| `t1_config.py` | Tiap kunci Pusat Pengaturan: tulis → baca lewat 3 jalur → lapisan PT → nilai tak sah → pulihkan | 310 kunci; 287 tulis grup dan 242 tulis PT terbaca benar; 264 nilai tak sah ditolak; 97 wajib-alasan ditolak; 2 penyimpangan (PT non-PKP). Sejak KF-T8 punya padanan gate `config_roundtrip` (INV-CFG-08): `backend/tests_mem/test_KFT8_putaran_pengaturan.py` (pembangkit nilai `backend/tests_mem/_nilai_uji.py`); skrip ini tetap arsip |
| `t2_roles.py` + `t2_analyze.py` | 12 peran bawaan + 4 peran kustom uji × 786 rute baca, dibandingkan dengan matriks | Rute berizin mengikuti matriks; peran kustom beracuan Manajer tanpa izin tetap lolos 23 rute |
| `t3_escalation.py` | Siapa bisa mengubah pengaturan; peran kustom mengubah peran lain | Pemegang `settings.manage`: 0 dari 232 kunci bisa diubah; peran beracuan Manajer tanpa izin: bisa mengubah 48 kunci |
| `t3b_eskalasi_akun.py` | Peran kustom pengelola akun | Menjadikan diri Admin: 200 · reset sandi Admin: 200 · membuat peran beracuan Manajer: 200 |
| `t4_peran_bawaan.py` | Perubahan izin peran bawaan setelah proses awal dijalankan ulang; pindah-massal akun Admin | Izin yang dicabut kembali; akun Admin aktif dari 1 menjadi 0 |
| `t5_jadwal_pengaturan.py` | Perubahan pengaturan berjadwal: kapan dipakai mesin | Pembaca baru tepat waktu; pembaca lama baru setelah layar Pengaturan dibuka |
| `t6_fx01_setoran_ganda.py` | Temuan FX-01 dari audit keuangan, lewat API | Setor 10.000.000 → 2 kas masuk (20.000.000); saldo 1-1280 menjadi −10.000.000 |
| `t7_tx01_faktur_pengganti.py` | Temuan TX-01: faktur pajak diganti, lalu rekap PPN | PPN keluaran 110.000 → 220.000 setelah pengganti terbit |
| `t8_cr01_plafon_oleh_sales.py` | Temuan CR-01: Sales mengubah plafon dan status blokir pelanggannya | 200; plafon 5 juta → 900 juta, terblokir → aktif |
| `t9_tulis_tanpa_izin.py` + `t9_analyze.py` | 962 rute tulis × 3 akun (peran tanpa acuan tanpa izin, Sopir, peran beracuan Manajer tanpa izin); isi permintaan dibuat dari skema | Tanpa izin: 898 ditolak, 37 lolos gerbang (tak satu pun rute berizin terpakai), 25 tak teruji, 2 galat. Beracuan Manajer: 28 gerbang tambahan terbuka, 5 langsung dijawab 200 |
| `t10_setuju_tanpa_izin.py` | Persetujuan oleh peran tanpa izin; persetujuan PO lintas PT | Peran beracuan Manajer tanpa izin: setujui PO 250 juta → 200, setujui tagihan pemasok 75 juta → terposting. Finance PT lain menyetujui PO → 200 |
| `serve_mem.py` | Aplikasi utuh di database tiruan pada port nyata (untuk uji layar) | Backend :8001; frontend dijalankan dari salinan `frontend/` |
| `ui_pengaturan_peran.js` | 21 langkah lewat peramban: ubah pengaturan per PT, riwayat, nilai tak sah, buat peran, buat akun, masuk sebagai peran baru, izin kelola pengaturan | 18 sesuai harapan; 3 temuan (KF-01 di layar, PR-06, PR-16). Tangkapan layar di `layar/` |
| `ui_sapuan_layar.js` | Membuka tiap layar lewat `?view=` dan mencatat panggilan API yang gagal | Lihat laporan §5a |
| `fe_be_routes.py` | Tiap panggilan API di layar punya rute | 1.790 panggilan; 1 tanpa rute (`GET /api/products/{id}`) |

Catatan: `t3_escalation.py` baris (d3) mengirim isi permintaan yang bentuknya salah (dijawab 422); uji yang benar untuk
butir itu ada di `t3b_eskalasi_akun.py`.

## Batas

- Database tiruan tidak mendukung indeks unik parsial, balapan, maupun transaksi. `boot_app.py` membuat ulang indeks
  yang ditolak tanpa sifat unik (daftarnya di `boot_app.SKIPPED_INDEXES`) dan menambal `find_one_and_update` supaya
  pola klaim atomik berperilaku seperti MongoDB asli. T1–T5 dijalankan sebelum tambalan kedua; tidak ada yang
  bergantung padanya.
- Data hanya seed awal. Rute yang butuh dokumen dijawab 404 dan dihitung "lolos gerbang".
- T9 menguji **gerbang** rute tulis dengan isi buatan dari skema; 25 rute tidak tercapai gerbangnya (isi buatan ditolak
  validasi). Hasil kerja rute tulis hanya diuji untuk pengaturan, peran, akun, persetujuan PO/tagihan pemasok, dan tiga
  temuan keuangan (T6–T8).
- Uji layar butuh `yarn install` pada salinan `frontend/`. Paket pengembang `@emergentbase/visual-edits` diunduh dari
  host di luar registry; bila host itu tidak terjangkau, hapus barisnya dari `package.json` salinan — `craco.config.js`
  sudah menoleransi ketiadaannya.
- Layar yang diuji jalan hanya Pusat Pengaturan dan Peran & Hak Akses; penilaian layar lain berasal dari membaca kode.

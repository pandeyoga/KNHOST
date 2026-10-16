# Reproduksi integrasi KNHOST

Harness menggunakan Python 3.12, FastAPI/ASGI, Motor dan MongoDB Community 8.0.12. Setiap proses membuat database baru bernama `knhost_audit_<random>`. Database tidak otomatis dihapus agar bukti tetap tersedia.

1. Siapkan clone KNHOST pada commit `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`.
2. Buat environment Python 3.12 terpisah dan pasang [requirements-audit.lock](requirements-audit.lock). Lock ini merekam dependency pengujian, bukan pengganti requirements aplikasi.
3. Jalankan MongoDB khusus uji dengan bind `127.0.0.1`, port `27919`, serta dbpath baru. Jangan memakai database produksi.
4. Set `KNHOST_REPO` ke absolute path clone. Script mengatur MONGO_URL/DB_NAME lokal dan menonaktifkan dotenv. Jaringan proses dibatasi ke loopback.
5. Jalankan `python integration_round4.py`, kemudian `python integration_rfid_wms_finance.py`.
6. Jalankan `python route_sweep_round4.py` untuk probe anonim. Untuk user tanpa permission, set `AUDIT_ROUTE_MODE=no_permissions` lalu jalankan script yang sama. Kosongkan variabel tersebut sesudahnya. Mode ini melewatkan logout agar sesi pengujian tidak terhapus.

Semua assertion yang lulus berarti perilaku bug atau kontrol berhasil dikarakterisasi; ini bukan tanda aplikasi bebas bug. Setelah patch, regression test harus memverifikasi invariant yang benar.

Hasil JSON dan trace baris source ditulis ke folder harness. Hasil JSON yang disertakan berasal dari pengujian di folder kerja audit. Trace bukan branch coverage. Pada Windows, harness menyediakan adapter os.uname untuk hostname scheduler; source aplikasi tetap tidak diubah. Full lifespan, scheduler dan seluruh indeks deployment belum diuji.

Tidak ada OTP nyata, pembayaran bank atau perintah gate. Hentikan MongoDB khusus audit setelah seluruh proses pengujian selesai; jangan melakukan cleanup massal terhadap database lain.

## Tambahan putaran 5

Jalankan `python integration_round5.py` setelah prasyarat yang sama tersedia. Skrip memakai `integration_round4.py` sebagai bootstrap, sehingga KNHOST_REPO harus menunjuk clone sumber. Sembilan skenario menguji pengaturan lintas entitas, keputusan periode dan inspeksi. Assertion membuktikan perilaku cacat yang teramati; setelah perbaikan, assertion tersebut memang perlu diganti dengan harapan perilaku benar.

Untuk tiga suite bawaan terpilih, jalankan `python -X utf8 run_existing_unit_tests.py`. Konfigurasi audit serial terpisah berada pada pytest-audit.ini; konfigurasi repository tidak diubah. Hasil yang dilampirkan: 19 passed. Tidak diperlukan akun layanan eksternal.

## Tambahan putaran 6

Jalankan `python -X utf8 integration_round6.py` dengan prasyarat yang sama. Sepuluh skenario meliputi produksi, QC hold, penerimaan manual dan lifecycle tag. Dibutuhkan MongoDB lokal port 27919 yang aktif; proses audit sebelumnya telah dihentikan setelah pengujian dan file database dipertahankan. Skrip membuat database baru.

## Putaran 7

Jalankan `python -X utf8 integration_round7.py` dengan environment dan MongoDB lokal yang sama. Skrip membuat database baru, memasang indeks unik active_key yang sesuai repository, dan menjalankan 12 skenario GRN/QC. Master/PO/task awal berupa fixture; lifecycle GRN manual berjalan lewat service asli, keputusan QC lewat HTTP ASGI.

## Putaran 8

Jalankan `python -X utf8 integration_round8.py` setelah MongoDB lokal port 27919 aktif. Sembilan skenario retur memakai service asli, dengan master/PO/stock awal sebagai fixture; tidak memakai data produksi. Nilai PPN adalah parameter sintetis, bukan klaim tarif legal. Hasil mencakup pemeriksaan net per akun setelah reversal.

# Reproduksi, lingkungan dan asal bukti

Source audit `a904d989b622f7da14c4892d03cf6ef0c43f3084`; hasil current tersedia di `latest/`. Root evidence/repro lama adalah tahap `d6da1a3d536228582645abb98aea19f3e491f300` dan tetap bertanda commit. Jangan menjalankan skrip uji terhadap produksi.

Python runtime 3.12, FastAPI 0.110.1, Motor 3.3.1/PyMongo 4.6.3, pytest 9.1.1, coverage 7.16.2 dan Mongo 8.0.12 digunakan secara lokal. Database fixture memakai nama audit terisolasi; server dan koneksi dibatasi localhost. Tidak ada seed/transaksi yang dijalankan pada database perusahaan. Socket eksternal diblokir pada proses audit.

`latest/repro/` memuat fixture dan counterexample. `wave2_env.py` membuat DB UUID baru; `run_local.py` memerlukan KNHOST_REPO, runtime dengan dependency proyek dan Mongo lokal 27919. Runner portable menyiapkan env dan melakukan path resolution; path adaptasi tidak mengganti business functions. Untuk JavaScript diperlukan Node dan Babel parser dari frontend dependency environment. Package memakai `KNHOST_REPO` agar tidak tergantung nama checkout auditor. Review wrapper terlebih dahulu, pastikan HEAD dan env yang digunakan tercatat, lalu jalankan repro terarah.

OrderDashboard diuji dua tahap: original public `/dashboard` dan `/sales-orders/stats/summary` menghasilkan payload fixture; original useMemo kemudian dijalankan pada payload itu. ManagerDashboard memakai original load, dengan transport terkontrol pada period 30→90. FulfillmentDecisionDialog memakai original submit/load untuk melihat error yang terhapus. Ketiga contoh tidak diklaim sebagai browser navigation atau screenshot verification.

Tes audit asli dalam repository disalin ke sandbox. Adaptasi meliputi lokasi `/app`, API localhost, backend/frontend.env lokal, Windows ROOT derivation dan import mode. Assertion tidak diganti. Log awal yang berhenti akibat port salah disimpan dan tiga skrip diulang setelah memperbaiki pembacaan env. Full-suite fixture stateful dan asynchronous loop errors tetap dicatat.

Build frontend memakai dependency cache yang telah ada; bukan fresh installation dari lockfile. Raw coverage/process/database files tersedia lokal tetapi tidak dimasukkan ke ZIP import. JSON hasil, XML testcase, log, manifest adaptasi dan register route/file ikut paket. Token session sintetis pada log disamarkan dalam salinan paket.

## Batas verifikasi browser pada sesi ini

Browser helper gagal sebelum navigasi dengan pesan `failed to write kernel assets: The system cannot find the path specified. (os error 3)`. Satu reset dan percobaan ulang memberikan error sama. Frontend/backend lokal sudah disiapkan, tetapi **DOM, screenshot, angka rendered dan navigasi UI tidak terverifikasi**. Ini kegagalan lingkungan alat, bukan temuan bug aplikasi. Bukti dua percobaan tersedia pada `latest/evidence/browser-ui-attempt.json`. Original-JavaScript probes dan API tests tetap berlaku sesuai batasnya; belum menggantikan browser/perangkat fisik.

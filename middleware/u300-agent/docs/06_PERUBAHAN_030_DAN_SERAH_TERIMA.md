# Reader U300 — pembaruan 0.3.0 LAB

ERP Kain Nussantara · PT Kubus Teknologi Indonesia

> **Historis.** Prosedur pemulihan, ekspor snapshot, dan signing di bawah masih berlaku di 0.5.0; perilaku lintasan,
> sensor, galat, dan simulasi sudah diganti — lihat [08 Perubahan 0.5.0](08_PERUBAHAN_050.md).

## Hasil pengembangan

Versi ini melanjutkan paket 0.2.0. Application ID tetap sama sehingga pembaruan debug dengan signing key yang sama dapat mempertahankan database. Paket 0.2.0 tetap disimpan terpisah sebagai referensi; jangan menurunkan versi pada perangkat yang sudah diperbarui tanpa prosedur migrasi.

| Area | Perubahan |
|---|---|
| Konfigurasi | Config baru menunggu antrean versi lama selesai, lalu diterapkan saat radio berhenti. Identitas device/site/warehouse yang berbeda ditolak. Isi config yang berubah tanpa perubahan versi ditolak. |
| Pemulihan | Tombol ber-PIN untuk mengambil ulang config dan retry setelah perbaikan. Tidak mengubah ID/body event, menghapus antrean, atau memaksa keputusan ERP. 401/403 tetap memerlukan provisioning key. |
| ACK dan retry | ACK hanya mengubah event pending yang sesuai batch. Karantina tidak berubah menjadi acknowledged karena respons terlambat. Batch 413 dipecah dalam transaksi database; partial ACK memakai backoff per batch. |
| Keputusan gate | Gate-state tidak menyelesaikan passage yang belum melewati close/ACK. Green memerlukan boolean yang benar, konteks sesuai, waktu valid, counts bulat, matched sama dengan observed_unique, dan tanpa missing/extra/unknown/pending. |
| Sensor | Input bersamaan dan urutan tambahan yang ambigu menghilangkan kepastian arah; tidak mempertahankan arah lama. |
| Simulasi | Partial ACK, retry, non-durable ACK, HTTP 400/401/403/409/413/429/500, dan perubahan config. State simulator mempertahankan versi, dedup, hasil close dan latch setelah object/proses dibuat ulang. |
| Operasional | Histori dapat dipilih untuk membaca ringkasan lintasan; perubahan PIN; ekspor snapshot JSONL lengkap melalui worker background; verifikasi snapshot tanpa restore/mutasi. |
| Android | Ikon aplikasi, pembatasan backup/transfer data, perbaikan temuan lint, dan paket instrumentation test untuk SQLite nyata. |
| Build rilis | Konfigurasi signing melalui environment; tidak ada private key atau password produksi di source/paket. |

## Penggunaan fitur baru

**Pemulihan:** ekspor diagnosis → periksa penyebab → perbaiki server/config/key → tekan *Pemulihan koneksi / kontrak* → masukkan PIN → *Periksa & coba ulang*. Bila server masih menolak, blok kembali muncul. Capture setelah kesalahan tetap memerlukan pemeriksaan operator dan tombol lanjutkan; perubahan config yang selesai dikuras mengikuti status jeda operator yang tersimpan.

**Perubahan config:** tutup capture aktif sebagai tidak lengkap bila pemetaan harus berubah → hentikan radio → selesaikan events dan close dengan versi lama → tunggu keputusan final → terapkan versi baru → mulai radio jika tidak dijeda. ERP harus dapat memproses snapshot versi lama; agent tidak mengasumsikan server dapat mengubah konteks request lama.

**Ekspor lengkap:** hentikan layanan → *Ekspor seluruh antrean & histori* → pilih berkas `.jsonl` → tunggu selesai. File berisi snapshot state, passages, events, batches dan audit. Footer `snapshot_end` menandai ekspor lengkap. Jalankan `python verify-snapshot.py path/file.jsonl` untuk memeriksa footer, jumlah record, ID duplikat dan referensi passage. Ekspor tidak menghapus data dan tidak menyediakan restore otomatis.

**Simulasi gangguan:** pilih skenario → *Skenario untuk batch berikutnya* → kirim beberapa tag. Gangguan diterapkan satu kali. Untuk perubahan config gunakan tombol simulasi versi baru. Release red latch tetap hanya simulasi; perangkat nyata mengikuti persetujuan ERP.

## Pengujian yang tersedia

- `test-host.ps1`: aturan keputusan, konfigurasi, simulator, persistensi simulator, koneksi HTTPS loopback, schema dan integritas snapshot.
- `build-debug.ps1 -IncludeAndroidTests -Lint`: build aplikasi, APK instrumentation dan pemeriksaan statis Android.
- `run-android-tests.ps1 -Adb <adb.exe> -Serial <serial>`: instal APK aplikasi dan test pada perangkat yang secara eksplisit dipilih, kemudian jalankan pemeriksaan SQLite nyata. Menggunakan database UAT bernama unik; tidak menghapus database operasional.
- Paket instrumentation sudah disiapkan untuk Android, tetapi belum dijalankan jika tidak ada perangkat/emulator. Tes host tidak diklaim menggantikannya.

Untuk menjalankan tes host pada komputer lain, gunakan JDK 17 dan Python, instal `tests/requirements.txt`, serta unduh `org.json:json:20240303` dari Maven Central. URL artefak: `https://repo.maven.apache.org/maven2/org/json/json/20240303/json-20240303.jar`. SHA-256 diverifikasi otomatis oleh skrip. Berikan lokasi melalui `test-host.ps1 -JavaHome <folder-JDK> -JsonJar <file-JAR>`. Tes HTTPS membuat sertifikat sementara khusus localhost di `tests/build`; ini bukan signing key APK atau sertifikat ERP dan tidak dimasukkan ke paket serah-terima.

Penutupan karena batas durasi maksimum selalu dianggap tidak lengkap; jeda/pemulihan menghapus eligibility sinyal dari lintasan sebelumnya. Tombol lanjut tidak memutar ulang izin keluar dari lintasan yang telah dijeda.

## Signing dan pembaruan

Sesudah UAT, tim pemilik aplikasi menyiapkan empat environment variable: `KN_RELEASE_STORE_FILE`, `KN_RELEASE_STORE_PASSWORD`, `KN_RELEASE_KEY_ALIAS`, `KN_RELEASE_KEY_PASSWORD`. Jalankan `gradlew.bat :app:assembleRelease` dengan JDK 17 dan SDK yang sama. Jika semuanya tidak diisi, build release menghasilkan APK unsigned; jangan mendistribusikannya sebagai APK operasional. Pengisian sebagian ditolak.

Jangan menyimpan key/password di repository, chat, ZIP atau parameter command line. Key harus konsisten untuk pembaruan APK. Peralihan dari debug signing ke signing produksi berbeda tidak dapat diperlakukan sebagai update biasa; rencanakan migrasi data sebelum mengganti instalasi. Label LAB dan nomor versi masih mencerminkan status belum lulus UAT.

## Yang tetap menunggu

1. U300, firmware, sensor, indikator dan commissioning RF/GPIO.
2. ERP staging — pengguna telah menyatakan belum tersedia; tes saat ini lokal/simulasi.
3. Perangkat Android/emulator untuk menjalankan instrumentation, UI dan lifecycle.
4. Persetujuan retensi — tidak ada penghapusan otomatis histori.
5. Signing key produksi, SOP operasional, dan hasil uji beban.
6. Kebutuhan beberapa gate independen pada satu reader, jika memang diperlukan; versi ini tetap satu logical gate terpilih.

Tidak ada perubahan yang dipush ke ERP atau perangkat operasional dalam pekerjaan ini. Source dan paket build disiapkan lokal untuk pengujian berikutnya.

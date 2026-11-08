# Integrasi ERP dan pekerjaan tersisa

ERP Kain Nussantara · Production IT PT Kubus Teknologi Indonesia

Status 19 Oktober 2026. Catatan versi 0.3 yang menganggap kontrak tersedia telah digantikan oleh pemeriksaan kode main `055f7ea0f852582867b3ab063d28e7e41f67f410` dan implementasi V2 di salinan kerja lokal. Perubahan belum dipush atau diterapkan ke server.

## Tersedia dalam patch ERP

Konfigurasi versioned, autentikasi device-key yang sudah ada, journaled ACK per event, identitas event per perangkat, passage close idempotent, keputusan manifest penuh, gate-state/latch, acknowledge melalui sesi pengguna, telemetry, panel U300 di menu Perangkat RFID, serta pilihan dokumen SJ/transfer fisik/putaway. Tidak mengubah stok atau finance karena RFID hanya menjadi bukti validasi.

Resolver gate juga diperbaiki untuk transfer fisik roll yang masih reserved untuk SO (`transfer_ref`), dan memeriksa keanggotaan roll pada dokumen transfer. Jalur gate lama menghormati crossing V2 agar tidak memberi izin kedua atas dokumen yang sama.

## Belum dinyatakan selesai

- Runtime Android/SQLite/service/boot pada emulator atau perangkat nyata belum dijalankan; APK dan instrumentation APK sudah dikompilasi.
- Region, power, firmware, antena, sensor, relay dan waktu passage harus dibuktikan pada U300. Profil contoh tetap belum commissioned.
- Integrasi lokal memakai router ERP yang sebenarnya dan MongoDB lokal; startup aplikasi ERP lengkap, bootstrap, konfigurasi deployment, serta uji role pengguna end-to-end masih perlu staging.
- Satu dokumen manifest per passage. Konsolidasi beberapa SJ/SO dalam satu dispatch fisik belum diterapkan pada V2 ini. Jangan memindai gabungan beberapa SJ sebagai satu passage dan mengharapkan GREEN.
- Transaksi pembelian antar-entitas adalah perubahan kepemilikan, bukan otomatis dokumen perpindahan fisik. Gate menggunakan transfer fisik/putaway/SJ yang sesuai. Transfer komersial `inter_entity` tidak dijadikan izin gate.
- Mekanisme koreksi crossing yang salah/recovery claim setelah crash belum memiliki layar supervisor tersendiri. Claim dipertahankan; tidak dibersihkan otomatis.
- Dashboard menampilkan 100 passage terakhir dan pilihan 200 dokumen terbaru. Pagination histori, ekspor evidence server, dan filter lanjutan belum tersedia dalam panel baru.
- Otoritas operasional memakai izin `wms:view`/`wms:scan` yang sudah ada. Konfigurasi perangkat mengikuti aturan admin infrastruktur eksisting. Pemisahan hak acknowledge dan commissioning yang lebih rinci belum diimplementasikan.
- Retensi histori menunggu keputusan; tidak ada penghapusan otomatis.
- Signing produksi, URL staging, credential provisioning dan acceptance operasional masih belum tersedia.
- Handheld C72 dan printer CP30EN tetap modul berbeda, di luar APK reader ini.

Tidak ada status “production ready” yang diberikan oleh hasil build atau simulasi.

# ERP Kain Nussantara — U300 Reader Agent

**Production IT: PT Kubus Teknologi Indonesia**  
Versi software: **0.4.0-lab** · Tanggal: 19 Oktober 2026  
Status: **implementasi untuk pengujian laboratorium; belum disetujui untuk operasional gate**.

Versi ini disertai perubahan ERP lokal pada baseline `055f7ea0f852582867b3ab063d28e7e41f67f410`. Komunikasi Java–ERP melalui HTTPS lokal telah diuji. Lihat [Integrasi versi 0.4](docs/07_INTEGRASI_ERP_040.md).

## Hasil yang tersedia

Project Android native untuk reader Chainway **U300**, melanjutkan aplikasi diagnostik sebelumnya. Application ID baru `id.kubusteknologi.kn.u300.agent` membuatnya dapat dipasang berdampingan dengan aplikasi diagnostik. Fokus paket ini reader; handheld C72 dan printer CP30EN tidak termasuk implementasi APK ini.

| Bagian | Implementasi |
|---|---|
| Operasi Android | Foreground service, notifikasi, pilihan mulai otomatis setelah reboot, wake lock, kontrol mulai/jeda/lanjut/berhenti |
| Integrasi radio | SDK lokal DeviceAPI 20251103; inventory EPC/TID/antena/RSSI; verifikasi region/power dan pemetaan antena |
| Data lokal | SQLite, ID observasi unik, ID lintasan, request batch tersimpan, kunci idempotensi penutupan, histori dan audit |
| Koneksi ERP | HTTPS, device key, konfigurasi, events, passage close, gate-state, telemetry; timeout, retry, partial ACK, 413 dan karantina |
| Pengamanan gate | Keputusan final sesuai konteks dan waktu; red latch dari ERP; green dibatasi waktu monotonik; tanpa green untuk backfill/restart/gap/karantina |
| Sensor/indikator | Adapter GPI1–GPI4 dan GPO1–GPO4; urutan A/B untuk arah; profil indikator aktif-high; wiring wajib commissioning |
| Operasional | Dashboard, PIN pemeliharaan, device key terenkripsi Android Keystore, ekspor diagnosis melalui pemilih file Android |
| Simulasi | Radio/ERP tiruan internal; injeksi EPC valid/tidak valid, offline, verdict dan simulasi acknowledge; database terpisah |

## Batas penting versi ini

1. Satu **logical gate terpilih per instalasi**, dengan beberapa antena. Dua gate independen pada satu reader tidak dijalankan serentak oleh versi ini.
2. Setiap awal layanan memerlukan konfigurasi ERP yang valid. Setelah online, capture offline mengikuti kebijakan ERP. Boot dalam kondisi offline tidak otomatis memakai konfigurasi lama untuk menyalakan radio.
3. Clearance fisik hanya untuk `manifest_full`. Hasil `per_epc_only` dan `manifest_subset` tetap dicatat tetapi tidak menghasilkan green untuk seluruh lintasan.
4. Region dan power diverifikasi terhadap profil yang sudah ditetapkan saat commissioning; aplikasi tidak menebak kode region atau menentukan daya RF yang diperbolehkan.
5. Perubahan versi konfigurasi menghentikan capture dan menunggu antrean lama selesai sebelum diterapkan. Perubahan identitas atau isi konfigurasi tanpa versi baru ditolak. Error kontrak dapat dicoba ulang melalui pemulihan ber-PIN setelah penyebab diperbaiki.
6. Histori tidak dihapus otomatis. Batas antrean dari ERP, batas database 256 MiB, dan ruang bebas minimum 64 MiB menghentikan capture. Kebijakan retensi menunggu keputusan pemilik sistem.
7. APK memakai debug signing dan label LAB. Proses release signing, penerapan device management, dan acceptance perangkat tetap diperlukan sebelum produksi.
8. Simulasi menguji mekanisme agent. Ia bukan implementasi penuh business engine ERP, tidak menentukan kebenaran stok/manifest nyata.

Rincian pembaruan, pemulihan, ekspor, tes Android dan signing: [Serah-terima versi 0.3.0](docs/06_PERUBAHAN_030_DAN_SERAH_TERIMA.md).

## Dokumen pendamping

- [Panduan pemasangan dan penggunaan](docs/01_PANDUAN_OPERASIONAL.md)
- [Arsitektur, antrean, dan kontrak](docs/02_ARSITEKTUR_DAN_KONTRAK.md)
- [Commissioning dan rencana pengujian](docs/03_COMMISSIONING_DAN_UAT.md)
- [Catatan terpisah untuk ERP dan keputusan tertunda](docs/04_CATATAN_ERP_DAN_PENDING.md)
- [Bukti dan batas validasi](docs/05_VALIDASI.md)
- `docs/device-config.template.json`: contoh konfigurasi belum dikomisikan; jangan langsung diaktifkan.

## Build

Toolchain yang telah dipakai: JDK 17, Gradle 8.2, Android Gradle Plugin 8.2.2, compile/target SDK 34, min SDK 30. JDK bawaan Android Studio yang lebih baru belum tentu cocok dengan Gradle ini; pilih JDK 17 untuk project.

Di workspace ini jalankan `build-debug.ps1`. Untuk komputer lain: buka folder project di Android Studio, pilih JDK 17 sebagai Gradle JDK, instal SDK Platform 34 dan Build Tools 34.0.0, isi `local.properties` dengan lokasi SDK lokal, lalu jalankan `gradlew.bat :app:assembleDebug`.

SDK vendor harus tersedia pada `app/libs/DeviceAPI_ver20251103_release.aar`. Hash SHA-256 yang diperiksa: `4eb338266e7abaf3078f14fc5fb78706efecfdc6d4783fdd3577f582fc2a2c7a`. File tersebut berasal dari SDK yang disediakan pengguna; jangan mempublikasikan AAR sebelum ketentuan distribusi vendor dipastikan. `.gitignore` mengecualikan AAR, APK, cache, dan konfigurasi lokal.

Tes host: `test-host.ps1`. Tes ini menggunakan `org.json:json:20240303` hanya untuk pengujian di komputer; runtime APK menggunakan JSON bawaan Android. Skrip memeriksa hash JAR. Validasi kontrak menggunakan Python dan jsonschema 4.23.0, serta OpenAPI RFID V2 dari paket dokumentasi yang sudah ada.

## Sumber teknis

- SDK dan contoh Android yang sudah diunduh: `API_Ver20251103.rar` dan `Demo-uhf-fixed_as.rar`.
- [Halaman resmi Chainway U300](https://www.chainway.net/mobile/Products/Info/146).
- [Dukungan resmi Chainway U300](https://www.chainway.net/support/Info/36).
- Kontrak target internal: paket `ERP_Kain_Nussantara_PT_Kubus_2026-10-13`, `kontrak/OPENAPI_RFID_V2.json`.

Signature pemanggilan SDK diperiksa terhadap binary AAR menggunakan `javap`; hal ini membuktikan ketersediaan metode, bukan keberhasilan akses hardware.

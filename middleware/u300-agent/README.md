# ERP Kain Nussantara — U300 Reader Agent

**Production IT: PT Kubus Teknologi Indonesia**  
Versi software: **0.5.0-lab** (versionCode 5) · Tanggal: 9 November 2026 · Kontrak: **OPENAPI RFID V2 2.1.0**  
Status: **implementasi untuk pengujian laboratorium; belum diuji di U300 fisik maupun runtime Android; belum disetujui
untuk operasional gate.**

Perubahan versi ini: [08 — Perubahan 0.5.0](docs/08_PERUBAHAN_050.md) (photo-eye satu arah + cadangan RF, ringkasan
bacaan, daftar latar, galat terstruktur, setelan radio, indikator 4 GPO, mode uji meja K-RFID-03). Keputusan pemilik
yang mengikat: [`docs/rfid/KEPUTUSAN_GATE_RFID.md`](../../docs/rfid/KEPUTUSAN_GATE_RFID.md).

## Hasil yang tersedia

Project Android native untuk reader Chainway **U300** (application ID `id.kubusteknologi.kn.u300.agent`, bisa dipasang
berdampingan dengan aplikasi diagnostik). Handheld C72 dan printer CP30EN tidak termasuk APK ini.

| Bagian | Implementasi |
|---|---|
| Operasi Android | Foreground service, notifikasi, mulai otomatis setelah reboot (opsional), wake lock, kontrol mulai/jeda/lanjut/berhenti |
| Radio | SDK lokal DeviceAPI 20251103; inventory menyala terus; **callback salin-saja** ke antrean RAM (bacaan terbuang dihitung); **setelan radio set + baca ulang** (region, daya per port, Gen2, TagFocus, FastID, RF link, filter); peta port → atas/kiri/kanan; pemeriksaan layanan UHF bawaan |
| Lintasan | **Photo-eye utama + cadangan RF** (K-RFID-01): state machine gate satu arah A (masuk) / B (keluar) — EXITED, REVERSED, ABORTED, TIMEOUT, SENSOR_FAULT; RingBuffer ±10 s untuk pre-buffer; daftar latar saat IDLE; mode tanpa sensor dan mode dua arah lama |
| Bukti ke ERP | TagSummary per lintasan × EPC × antena (bucket 250 ms, cap waktu monotonik + jam server), GpiEdge, envelope `seq`/`boot_id`, multi-batch per siklus; parse RSSI/antena tahan locale |
| Data lokal | SQLite skema 2 (migrasi otomatis dari 0.4 tanpa menghapus), outbox persist-before-send, ID tetap, draf ringkasan untuk pemulihan crash, kunci idempotensi close |
| Koneksi ERP | HTTPS + device key; keputusan galat dari `detail.code` (hanya AUTH_* memblokir; nonaktif admin / profil belum terbit = polling lambat); 413 pecah adaptif; jam tersinkron dari setiap respons |
| Pengamanan gate | Hijau hanya keputusan final, segar, live, konteks sama, tanpa kunci gate — `manifest_full` (sisa 0) atau `document_session` (trip parsial, K-RFID-10); kuning = REVIEW; merah = kunci gate (K-RFID-09) |
| Indikator | 4 GPO: hijau / kuning / merah / buzzer, aktif-high; polling GPI ≤ 20 ms dengan statistik latensi |
| Diagnostik | **Mode uji meja K-RFID-03** (9 butir, ber-PIN) → hasil + pengamatan operator → ekspor JSON; ekspor diagnosis & snapshot |
| Simulasi | Radio/GPIO/ERP tiruan: skenario gate (lewat, muatan kecil, mundur, batal, kosong, beriringan, B sebelum A, sinar macet, pulih, latar), keputusan GREEN/REVIEW/RED, trip parsial, galat terstruktur |

## Batas penting versi ini

1. Satu **logical gate per instalasi**; gate IN dan OUT terpisah = dua U300.
2. Semua parameter lintasan, ambang RSSI, daftar latar, tuning = **titik awal kalibrasi** (K-RFID-03/05/08 terbuka).
   Profil contoh `docs/device-config.template.json` sengaja belum dikomisikan.
3. Region **kandidat 0x3F (63)** Indonesia 920–923 MHz dari Javadoc — **wajib dikonfirmasi di unit** (uji meja butir 5).
4. Hijau tidak pernah untuk `per_epc_only`/`manifest_subset`, backfill, restart, celah, karantina, lintasan yang
   digabung, atau saat gate terkunci. Keputusan bisnis tetap di ERP.
5. Dua sinar tidak membedakan objek pendek yang sampai sinar B lalu mundur dalam `tail_ms` (SOP melarang mundur).
6. Histori tidak dihapus otomatis; batas antrean dari ERP, DB 256 MiB, ruang bebas 64 MiB menghentikan capture.
7. APK memakai debug signing dan label LAB.

## Dokumen pendamping

- [01 Panduan pemasangan dan penggunaan](docs/01_PANDUAN_OPERASIONAL.md)
- [02 Arsitektur, antrean, dan kontrak](docs/02_ARSITEKTUR_DAN_KONTRAK.md)
- [03 Commissioning, uji meja, dan rencana pengujian](docs/03_COMMISSIONING_DAN_UAT.md)
- [04 Catatan ERP dan keputusan tertunda](docs/04_CATATAN_ERP_DAN_PENDING.md)
- [05 Bukti dan batas validasi](docs/05_VALIDASI.md)
- [08 Perubahan 0.5.0](docs/08_PERUBAHAN_050.md) · historis: [06 (0.3.0)](docs/06_PERUBAHAN_030_DAN_SERAH_TERIMA.md), [07 (0.4.0)](docs/07_INTEGRASI_ERP_040.md)
- Laporan paket: [`docs/rfid/hasil/PREP-E-AGENT-050.md`](../../docs/rfid/hasil/PREP-E-AGENT-050.md)

## Build

Toolchain: JDK 17, Gradle 8.2 (wrapper), Android Gradle Plugin 8.2.2, compile/target SDK 34, min SDK 30.

```powershell
# Folder toolchain lokal berisi jdk/, sdk/ (platform 34 + build-tools 34.0.0), gradle-home/, json-20240303.jar, test-python/
./build-debug.ps1 -ToolRoot <folder-android-build> -IncludeAndroidTests -Lint [-Offline]
./test-host.ps1   -ToolRoot <folder-android-build>
```

Atau set `KN_ANDROID_TOOLS=<folder>`. `build-debug.ps1` menulis `local.properties` (tidak di-commit). Hasil:
`app/build/outputs/apk/...`; salinan serah-terima di `delivery/KN-U300-Agent-0.5.0-lab-debug.apk` dan
`delivery/KN-U300-Agent-0.5.0-androidTest.apk` (hash di `SHA256SUMS.txt`). Pemasangan & tes instrumentasi di
perangkat terpilih: `run-android-tests.ps1 -Adb <adb.exe> -Serial <serial>`.

SDK vendor wajib ada di `app/libs/DeviceAPI_ver20251103_release.aar` (SHA-256
`4eb338266e7abaf3078f14fc5fb78706efecfdc6d4783fdd3577f582fc2a2c7a`). **Hanya internal** — izin distribusi vendor belum
dipastikan; jangan salin AAR/APK ke repo atau tempat publik.

Tes host (`test-host.ps1`): kelas inti (`CoreTest`), state machine (`PassageMachineTest`), pipeline ujung-ke-ujung
(`PipelineTest`), konfigurasi & simulator (`HostTest`), kebijakan keputusan (`DecisionPolicyTest`), HTTPS loopback
(`TransportTest`), validasi skema kontrak 2.1 (`validate_contract.py`, jsonschema 4.23.0) dan integritas snapshot.
`org.json:json:20240303` hanya untuk tes komputer; runtime APK memakai JSON bawaan Android.

## Sumber teknis

- Signature & sebagian bytecode SDK diperiksa dengan `javap` terhadap AAR (membuktikan metode **ada**, bukan bahwa
  firmware U300 mendukungnya — itu tugas uji meja).
- [Halaman resmi Chainway U300](https://www.chainway.net/mobile/Products/Info/146) ·
  [Dukungan resmi](https://www.chainway.net/support/Info/36).

# Middleware RFID — U300 Reader Agent

Aplikasi Android yang berjalan **di reader Chainway U300** (gate RFID): membaca EPC/RSSI per antena, menyimpan
observasi di SQLite, mengirim event ke ERP lewat HTTPS + device key, lalu menyalakan indikator gate sesuai keputusan
ERP. Dibuat oleh PT Kubus Teknologi Indonesia. Status: **0.4.0-lab (19 Okt 2026) — uji laboratorium, belum untuk
operasional gate.**

Disalin ke repo ini pada 8 Nov 2026 dari folder lokal
`Documents/Codex/2026-09-28/sya/output/middleware-development/` agar bisa dikerjakan di sesi cloud.

| Folder | Isi |
|---|---|
| [`u300-agent/`](u300-agent/) | Proyek Android lengkap (Agent 0.4.0): sumber Java, tes host, kontrak `OPENAPI_RFID_V2.json`, dokumen `docs/01…07`, **SDK vendor** `app/libs/DeviceAPI_ver20251103_release.aar`, APK `delivery/KN-U300-Agent-0.4.0-lab-debug.apk` (+ APK androidTest). Mulai dari [`u300-agent/README.md`](u300-agent/README.md). |
| [`u300-erp-integration-0.5.0/`](u300-erp-integration-0.5.0/) | Paket integrasi ERP 0.5.0 LAB: `erp-u300-v2.patch` (kumulatif — router/service `rfid_v2`, kontrak, panel "Integrasi reader U300", tes), `README.md`, `REVIEW.md`, `MANIFEST.json`, `evidence/`. |

## Penting sebelum mengerjakan
0. **Baca dulu [`docs/rfid/KEPUTUSAN_GATE_RFID.md`](../docs/rfid/KEPUTUSAN_GATE_RFID.md)** — bacaan nyasar
   (unintended read), photo-eye, fakta lapangan dari pemilik, dan keputusan yang masih terbuka. Pemilik: hal itu
   diselesaikan dulu sebelum membangun atau merevisi middleware; butir terbuka = tanya pemilik.
1. **SDK vendor Chainway hanya untuk internal.** Repo KNHOST dijadikan **privat** (8 Nov 2026) justru karena AAR &
   APK ini. Izin distribusi vendor belum dipastikan — jangan salin `u300-agent/app/libs/*.aar` atau APK ke repo/
   tempat publik.
2. **Patch ERP 0.5.0 SUDAH diterapkan ke backend KNHOST (9 Nov 2026, PREP-D1)** dan diperbaiki sesuai keputusan
   pemilik (alarm merah hanya pelanggaran, sesi dokumen bertahap, klaim tidak bocor, dll.) + kontrak **2.1.0**
   (`backend/contracts/rfid_v2.json` = `u300-agent/contracts/OPENAPI_RFID_V2.json`). Rincian:
   [`docs/rfid/hasil/PREP-D1-GATE-V2.md`](../docs/rfid/hasil/PREP-D1-GATE-V2.md). Folder `u300-erp-integration-0.5.0/`
   kini arsip. **Aplikasi reader (Java) masih 0.4.0** — penyesuaian ke kontrak 2.1 (photo-eye satu arah, ringkasan
   bacaan, parse RSSI tahan locale, dll.) = paket E.
3. **Belum diuji di U300 fisik maupun runtime Android**; APK memakai debug signing. Lihat
   `u300-agent/docs/03_COMMISSIONING_DAN_UAT.md` dan bagian "Titik selesai produksi" di README paket integrasi.
4. Fakta lapangan dari pemilik (brainstorming 27 Okt 2026): gate IN dan OUT **terpisah, masing-masing satu arah**;
   3 antena per gate (atas, kiri, kanan); **tanpa photo-eye** (tidak ada di pengadaan) → pemicu lintasan harus dari
   rombongan EPC + RSSI; muatan stacker ±180×180 cm tumpuk menyilang maks 7 lapis, label di kiri/kanan/depan;
   dokumen (surat jalan/putaway/transfer) **selalu dibuat sebelum barang lewat**; Indonesia 920–923 MHz.
   Proposal awal: [`PROPOSAL_MIDDLEWARE_RFID.md`](../PROPOSAL_MIDDLEWARE_RFID.md).

## Build (ringkas)
JDK 17, Gradle 8.2 (wrapper), Android Gradle Plugin 8.2.2, compile/target SDK 34, min SDK 30. Buat
`u300-agent/local.properties` berisi `sdk.dir=<lokasi Android SDK>` (tidak di-commit), lalu
`./gradlew :app:assembleDebug`. Lingkungan cloud perlu Android SDK Platform 34 + Build Tools 34.0.0 terpasang.
Tes host (tanpa perangkat): `u300-agent/test-host.ps1` (Java + `org.json`), validasi kontrak:
`u300-agent/tests/validate_contract.py` (Python + jsonschema 4.23.0).

## Yang sengaja tidak disalin
- Versi lama (0.1 diagnostik, 0.2, 0.3), zip rilis, dan `KN_U300_ERP_Integration_0.4.0` — 0.4.0/0.5.0 adalah
  kumulatif. Demo vendor `UHF-A4_v1.8.1.apk` dan arsip SDK mentah juga tidak.
- `erp-files/` paket integrasi (salinan `server.py`, `gate_evaluator.py`, dst. versi baseline lama) — isinya sudah ada
  di patch; tidak disalin agar tidak ada duplikat berkas backend yang bisa tertukar.
- Hasil build (`.gradle/`, `app/build/`, `tests/build/` termasuk sertifikat uji `.p12`), `local.properties`, log build
  lokal.

## Catatan integritas
Berkas teks dinormalkan ke **LF** (aturan repo; `gradlew.bat` tetap CRLF lewat `.gitattributes`). `SHA256SUMS.txt`,
`HANDOVER.json` dan `MANIFEST.json` mencatat byte pengiriman asli 19 Okt, sehingga hash berkas teks bisa berbeda.
Hash biner **cocok** dengan manifest: SDK `DeviceAPI_ver20251103_release.aar`
(`4eb33826…c2a2c7a`), APK `KN-U300-Agent-0.4.0-lab-debug.apk`, dan `gradle-wrapper.jar`.

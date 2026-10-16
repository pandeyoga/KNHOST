# 6. Persiapan, Commissioning dan Deployment

**Project:** ERP Kain Nussantara  
**Produksi IT:** PT Kubus Teknologi Indonesia

## 6.1 Paket persiapan pengembangan

| Kelompok | Yang harus tersedia | Penanggung jawab fungsi |
|---|---|---|
| Unit | C72, reader UR300 Android, CP30EN, tag/media, antena dan indikator/sensor yang digunakan. | Pemilik perangkat/operasi. |
| SDK | File SDK, sample resmi, dokumentasi, firmware map, dependency/JNI ABI dan ketentuan distribusi. | Tim pengembangan + penyedia hardware. |
| Integrasi | Base URL lingkungan, device registry/key, user role test dan dataset tugas/dokumen. | Tim ERP. |
| Hardware profile | Model/serial/OS/firmware/module/interface/media/resolution/capabilities yang diuji. | Tim pengembangan perangkat. |
| Lokasi | Site/warehouse/logical gate/bin map, jaringan, sumber daya dan supervisor scope. | Gudang + tim jaringan. |
| SOP | Gate direction/manifest/offline, approval task, reprint/retag dan exception. | Pemilik proses. |
| QA | Fixture valid/unknown/hold/canceled/partial, kasus network/power/restart dan evidence template. | QA + pengguna domain. |

Fungsi tidak berarti nama personal sudah ditetapkan. Project lead mengisi PIC nyata. Kontrak API target tersedia sebagai acuan tim pengembangan middleware; kesiapan unit/SDK tetap harus dibuktikan.

## 6.2 Hardware profile yang diserahkan

Setiap profile memuat device model label, serial, firmware/OS, module, SDK version/file digest, native ABI, permission/install method, observed capabilities, transport, serta hasil init/read/write/status test yang relevan. Method mapping menyebut nama SDK nyata dan wrapper internalnya; tidak menyalin wrapper sebagai seolah method vendor.

Untuk UR300, tambahkan boot/autostart/power policy, screen-off behavior, trigger/antena/GPIO dan logical gate mapping. Profil wajib mendukung operasi reader on-device tanpa PC harian. Untuk CP30EN, tambahkan resolution, inlay/media, calibration, command/status/outcome support dan koneksi. C72 memuat trigger/barcode/lifecycle/background behavior.

## 6.3 Konfigurasi bootstrap

Bootstrap hanya menetapkan environment/base URL, provisioning identity dan metode memperoleh credential/config. Rule stok, owner, warehouse grant, arah gate dan print routing berasal dari config server yang telah diikat registry.

Contoh data non-secret:

```json
{
  "environment": "integration",
  "api_base_url": "https://erp.example.invalid",
  "contract_version": "2.0",
  "device_key_reference": "secure-storage-alias",
  "hardware_profile_id": "profile-approved-by-project"
}
```

Contoh adalah struktur, bukan alamat deployment atau credential nyata. Instalasi menerima nilai aktual melalui prosedur provisioning yang disahkan. Environment dev/integration/production tidak dipilih bebas oleh operator untuk melewati aturan.

## 6.4 Urutan commissioning C72

Catat profile dan pasang APK. Provision device/config; login user uji; init SDK; pilih satu task; baca known/unknown tags; verify upload/ACK dan progress. Uji trigger stop, pindah task, logout, offline/reconnect, reboot serta update. Konfirmasi task completion dan qty/unit sesuai ERP; serahkan APK/source dan evidence.

## 6.5 Urutan commissioning reader

Pasang APK agent langsung pada reader. Provision profile/key/config; uji radio/antenna/trigger serta logical gate. Uji start tanpa PC runtime, boot/screen-off, lintasan valid/invalid/partial/ambiguous, indikator/latch/ack, network offline, stale response, backfill, process death dan update.

Simpan foto/rekaman instalasi dan log actual EPC/decision/correlation yang diperlukan. Teknik membangun/memasang APK menggunakan komputer pengembangan tidak dicatat sebagai gateway operasional. Jika reader baru berfungsi saat tool desktop terus terhubung, RD-01 belum terpenuhi.

## 6.6 Urutan commissioning printer

Catat profile CP30EN/media/koneksi. Install connector pada runtime terpilih; registry identity/capability; calibrate template serta encode/readback sesuai unit. Cetak satu job label nyata dan baca dengan C72; kemudian batch partial, wrong routing, expired lease, offline, crash setelah send, lost result ACK dan reprint/retag.

Periksa ledger printer vs job/item/tag/verification ERP. Host printer tidak menjadi dependency reader. SDK utility/demo dapat dipakai untuk diagnosis PoC, tetapi workflow produksi harus memakai connector serta contract project yang sama.

## 6.7 Monitoring dan runbook

Minimum dashboard: device type/site/warehouse, lifecycle, hardware ready, ERP reachable, last contact, last durable upload/confirmed output, queue length/age, app/build/SDK/profile/config version dan last error. Reader passage/latch serta printer uncertain output mempunyai antrean tindak lanjut yang berbeda.

Runbook menjelaskan provision, start/stop, restart, key rotate, config change, offline recovery, queue pressure, SDK failure, printer paper/encode issue, uncertain result, supervisor ack, diagnostics export dan rollback. Semua tindakan berizin serta mempertahankan evidence.

## 6.8 Parameter yang ditetapkan pilot

Laju/byte batch, timeout/backoff, heartbeat/telemetry, retensi, queue cap, passage window, direction sensor policy, validity indikator, print lease/budget dan alarm level menggunakan field config dengan satuan. Project lead menetapkan nilai setelah pengujian unit dan layout; dokumen tidak mengarang satu angka production untuk semua gudang.

Target performa ditulis sebagai target yang disepakati, lalu dibuktikan dengan hasil p50/p95/peak, durasi offline, queue drain, laju tag representatif dan recovery. Capture-to-durable-ACK berbeda dari capture-to-final-business-result. Printer throughput diukur bersama media/encode errors, bukan hanya kecepatan transport.

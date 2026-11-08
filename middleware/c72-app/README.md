# KN Handheld C72 — aplikasi Android handheld Chainway C72 (0.1.0-lab)

Aplikasi operator gudang untuk **Chainway C72** (8 unit, bisa bertambah): pindai **per dokumen** (bukan satu per satu),
**tulis EPC buatan sistem** ke tag, cari tag lewat sinyal, pindai barcode, **kerja offline per dokumen** lalu sinkron,
dan **mode diagnostik uji meja** ber-PIN. Dibangun oleh KNHOST (paket PREP-G, 9 Nov 2026) sebelum perangkat datang.

> **Status: LAB.** Belum pernah dijalankan di C72 fisik maupun emulator. Seluruh perilaku SDK (daya, session, tulis,
> cari, barcode, kode tombol pemicu, format RSSI) = **belum terbukti** sampai uji meja
> ([docs/03_COMMISSIONING_UJI_MEJA.md](docs/03_COMMISSIONING_UJI_MEJA.md)). APK memakai debug signing.

| Peran handheld (keputusan pemilik) | |
|---|---|
| Gedung bergate (gedung simpan RCM & Soreang) | **cadangan** gate: tag tak terbaca, cek ulang, trip sisa (K-GDG-02/03) |
| Gedung tanpa gate (Jakarta, dll.) | **alat utama** konfirmasi tiba/terima/cek muat/opname |
| Internet gudang ↔ VPS putus (§10 opsi a) | C72 tetap bekerja **offline per dokumen** (daftar yang diharapkan tersimpan) lalu sinkron |
| EPC tag pabrik dianggap **tidak unik** (K-OPN-05) | EPC dibuat ERP lalu **ditulis** ke tag oleh C72 (Daftar Awal, ganti tag, roll potongan) |

## Jenis tugas (dari lokasi kerja operator ∩ gedung perangkat)
| Tombol | Dokumen | Kiriman ke ERP (layanan asal) |
|---|---|---|
| Masuk · Putaway | Putaway Order (tiba bertahap per trip) | `putaway_arrival_service.confirm_arrival_trip` |
| Keluar · SO / Keluar · Sampel | Final Loading Check SO × gudang | sesi `loading_check` (scan + selesaikan) |
| Transfer masuk | Transfer gudang dalam perjalanan | `transfer_receipt_service.receive` |
| Potong sampel | Tugas `sample_cut` | `sample_sale_service.cut_sample_task` → tulis tag roll potongan |
| Stock Opname RFID | Opname per gudang | sesi `cycle_count` (scan + selesaikan) |
| Verifikasi cetak | Print job label RFID | sesi `print_verify` (scan + selesaikan) |
| Daftar Awal | Sesi pendaftaran ulang stok lama | `initial_registration_lines.add_line` (+ tulis EPC) |

## Struktur
```
app/src/main/java/id/kainnusantara/handheld/
  core/            logika murni Java (diuji di host, tanpa Android):
                   Epc · Parse · ReadAggregator · Snapshot · DocMatcher · Profile · TaskKind · Outbox/OutboxItem ·
                   SyncEngine · ApiClient (adaptor API ERP) · C72HardwareAdapter (antarmuka) · SimulatedHardware ·
                   ScanController · WriteFlow · LocateMeter · BenchRunner · Pin · RegistrationForm · ClockSync · ErrorPolicy · Json · Store/MemoryStore
  ChainwayC72Adapter.java   satu-satunya kelas yang memanggil SDK vendor (RFIDWithUHFUART, BarcodeDecoder, BatteryUtils)
  SqliteStore / SecureStore antrean & cache tahan-mati (SQLite WAL) · kredensial terenkripsi Android Keystore
  App + *Activity.java      UI programatik (tombol ≥ 56 dp, hasil ikon + teks)
tests/             CoreTest · FlowTest · SyncTest · ApiTest (host) · ErpLocalTest + seed_erp_local.py + run-erp-local.ps1 (ERP lokal)
docs/              01 panduan operasional · 02 arsitektur & kontrak API · 03 commissioning & uji meja
delivery/          KN-C72-Handheld-0.1.0-lab-debug.apk + SHA256SUMS.txt
```
Asal kode: `Json`, `Parse`, `ClockSync`, pola `ErrorPolicy` & SQLite persist-before-send **disalin/diadaptasi dari agent
U300 0.5** (`middleware/u300-agent`, PT Kubus) — proyek itu tidak diubah.

## Build & uji (offline, toolchain lokal yang sama dengan agent U300)
JDK 17, Gradle 8.2 (wrapper), AGP 8.2.2, compile/target SDK 34, min SDK 30, Java 8 source, **tanpa pustaka tambahan**
(hanya Android framework + org.json bawaan + AAR vendor).
```powershell
.\build-debug.ps1 -ToolRoot <android-build> -Offline [-Lint] [-Deliver]   # APK debug (+ lint, + salin ke delivery/ & SHA256)
.\test-host.ps1   -ToolRoot <android-build>                               # 101 tes host (tanpa perangkat)
.\tests\run-erp-local.ps1 -ToolRoot <android-build> -BaseUrl http://127.0.0.1:8071 -Container <kontainer backend uji>
```
`local.properties` dibuat skrip dan **tidak** di-commit.

**SDK vendor Chainway hanya untuk internal** (repo KNHOST privat). AAR **tidak digandakan**: `app/build.gradle`
merujuk `../u300-agent/app/libs/DeviceAPI_ver20251103_release.aar`. Jangan menyalin AAR/APK ke tempat publik.

## Sisi ERP
API `/api/handheld/*` (`backend/routers/handheld.py`, `backend/services/handheld_*.py`), uji
`backend/tests/test_prep_g_handheld.py`. Laporan paket: [`docs/rfid/hasil/PREP-G-HANDHELD-C72.md`](../../docs/rfid/hasil/PREP-G-HANDHELD-C72.md).

# 03 — Commissioning & uji meja C72 (0.1.0-lab)

Daftar uji yang **harus dijalankan** saat unit datang — bukan pernyataan lulus. Sampai 9 Nov 2026 tidak ada C72,
emulator, atau runtime Android yang dipakai menguji aplikasi ini; yang terbukti hanya: kompilasi APK, lint (0 error),
101 tes host Java, uji pytest & integrasi Java → ERP lokal (lihat laporan PREP-G).

## 1. Peta metode SDK (AAR `DeviceAPI_ver20251103_release.aar`, signature dari `javap`)
| Adaptor | Metode SDK | Asumsi yang dipakai | Status |
|---|---|---|---|
| `initialize` | `RFIDWithUHFUART.getInstance()` → `init(Context)` | modul UHF C72 = UART; `init` true = siap | belum terbukti |
| daya | `setPower(int)` / `getPower()` | satuan dBm, rentang 5–30 (profil membatasi) | belum terbukti |
| session | `getGen2()` → `Gen2Entity.setQuerySession(n)` → `setGen2()` | S0–S3; bawaan profil S0 | belum terbukti |
| region | `setFrequencyMode(int)` / `getFrequencyMode()` | HANYA bila profil commissioning mengisi `region_code` (920–923 MHz Indonesia, kode dari uji) | belum terbukti — kode region C72 belum diketahui |
| `beginInventory` | `setInventoryCallback(IUHFInventoryCallback)` + `startInventoryTag()` | callback per tag `UHFTAGInfo.getEPC/getTid/getRssi` di utas SDK | belum terbukti |
| `stopInventory` | `stopInventory()` | sinkron; callback berhenti | belum terbukti |
| RSSI | `UHFTAGInfo.getRssi()` (String) | format `"-58,30"` (DecimalFormat tanpa Locale, id-ID) / `"N/A"` — diparse `Parse.rssi` | belum terbukti |
| `writeEpc` | `writeDataToEpc(pwd, IUHF.Bank_EPC=1, 32, 96, epcLama, epcBaru)` | filter bit 32 (sesudah CRC+PC), 96 bit; SDK menyesuaikan PC; sandi akses `00000000` | belum terbukti — urutan argumen ditebak dari nama kelas & praktik Chainway |
| `readSingle` | `inventorySingleTag()` | tag terdekat | belum terbukti |
| `startLocate` | `startLocation(ctx, epc, Bank_EPC, 32, IUHFLocationCallback(int value, boolean valid))` / `stopLocation()` | `value` 0–100 relatif | belum terbukti; cadangan = RSSI pindai terfilter |
| barcode | `BarcodeFactory.getInstance().getBarcodeDecoder()` → `open(ctx)`, `setDecodeCallback`, `startScan/stopScan`, `close` | `BarcodeEntity.getResultCode()==DECODE_SUCCESS(1)`, `getBarcodeData()` | belum terbukti |
| baterai | `BatteryManager` + `com.rscja.utility.BatteryUtils.getCycleCount/getBatteryHealth/…` | BatteryUtils mungkin tidak ada di C72 (galat ditangkap) | belum terbukti |
| pemicu | `Activity.onKeyDown/onKeyUp` keyCode profil `[139,280,291,293,294,311,312,313,315]` | kode tombol samping/pistol C72 (dari demo Chainway, belum dicek) | belum terbukti |
| `release` | `free()` | — | belum terbukti |

## 2. Peralatan
C72 (catat model, nomor seri, versi Android/build, versi aplikasi bawaan Chainway), pengisi daya, Wi-Fi gudang ke ERP
staging, **tag Impinj Monza R6-P** (±30 untuk baca massal; **5 tag uji cadangan** untuk tulis — EPC-nya akan berubah),
beberapa roll bertag, label QR roll & label supplier, label bin. ERP staging: perangkat handheld terdaftar (key), akun
operator & supervisor gudang dengan lokasi kerja, dokumen uji per jenis.

## 3. Uji meja (Diagnostik › PIN) — ekspor JSON tiap putaran
| # | Uji | Cara | Lulus bila |
|---|---|---|---|
| B1 | Pasang APK & izin | `adb install -r delivery/KN-C72-Handheld-0.1.0-lab-debug.apk`; cocokkan SHA256 | terpasang, buka tanpa crash |
| B2 | Layanan/aplikasi bawaan | tutup aplikasi demo UHF Chainway; catat apakah "Keyboard Emulator"/scan wedge aktif | dicatat |
| B3 | Init SDK | *Init SDK ulang* lalu lihat setup | `init` PASS; `power_dbm.readback` = set |
| B4 | Kemampuan & versi | *Jalankan semua* → langkah 2 | versi SDK/HW tercatat |
| B5 | Daya set/baca ulang | langkah 3 (5/10/20/30 dBm) | semua `match: true`; catat bila maks C72 ≠ 30 |
| B6 | Session | langkah 4; ulangi dengan penimpaan lokal S1/S2 | baca ulang = set; bandingkan jumlah tag B7 per session |
| B7 | Baca massal | 30 tag di meja, *Baca 5 detik* | ≥ 95 % tag unik terbaca; RSSI tidak tercatat "tak terbaca"; contoh RSSI mentah tersimpan (format koma/titik) |
| B8 | Laju & panas | baca 60 dtk berulang 10× | tidak crash/freeze; suhu baterai dicatat |
| B9 | Baca tunggal | 1 tag dekat | EPC benar |
| B10 | Tulis + baca ulang | tag uji tunggal ±5 cm, *Tulis + baca ulang (kembalikan)* | PASS keduanya; catat jumlah percobaan & daya |
| B11 | Tulis dua tag berdekatan | 2 tag uji berjarak 3 cm | aplikasi menolak (AMBIGUOUS) — tidak menulis tag yang salah |
| B12 | Tulis daya rendah | ulangi B10 pada daya tulis 5/10/15 dBm | tentukan `write_power_dbm` profil: paling kecil yang stabil 10/10 |
| B13 | Tulis di roll | tag tertempel di roll kain (bukan meja) | PASS; tag roll sebelah tidak berubah |
| B14 | Barcode | QR roll, label supplier, label bin (10 dtk) | data benar; catat simbologi |
| B15 | Cari tag | *Cari tag 3 dtk*, lalu layar Cari tag menjauh/mendekat 0,3–5 m | nilai naik saat mendekat; catat apakah `startLocation` SDK jalan atau cadangan RSSI |
| B16 | Tombol pemicu | tekan semua tombol samping/pistol di Diagnostik | catat keyCode → isi `trigger.keycodes` profil |
| B17 | Pemicu di layar pindai | tahan/lepas; tekan cepat 10× | tahan=mulai, lepas=berhenti; tidak ada sesi ganda/freeze |
| B18 | Baterai | langkah 10 | level & suhu terbaca (BatteryUtils boleh FAIL) |
| B19 | Offline | Wi-Fi mati → pindai dokumen tersimpan → konfirmasi → Wi-Fi hidup | antrean terkirim sekali; ERP tidak dobel |
| B20 | Mati di tengah | matikan paksa aplikasi saat antre / saat pindai | draf & antrean pulih setelah buka ulang |
| B21 | Ganti operator | operator A antre offline → logout → operator B login | antrean A tidak dikirim atas nama B |
| B22 | Lintas perangkat | 2 unit menulis tag roll yang sama | unit kedua ditolak `WRITE_IN_PROGRESS` |
| B23 | Ketahanan | 4 jam kerja pindai berselang | tidak crash; ukuran DB & baterai dicatat |

Hasil uji meja diserahkan sebagai JSON ekspor (`Android/data/id.kainnusantara.handheld.c72/files/ujimeja/`) + catatan
pengamatan, per unit. Profil ERP diisi dari hasil ini lalu `commissioned: true`.

## 4. Commissioning per unit
1. Cocokkan hash APK (`delivery/SHA256SUMS.txt`) dan AAR (`4eb33826…c2a2c7a`, sama dengan agent U300).
2. ERP: buat perangkat (gudang induk + cakupan), terbitkan key, provisioning lewat QR, buat PIN.
3. Uji meja B1–B18; susun profil (`PUT /api/handheld/devices/{id}/profile`):
   ```json
   {"profile": {"profile_id": "c72-rcm-v1", "commissioned": true,
     "rfid": {"power_dbm": 20, "write_power_dbm": 10, "locate_power_dbm": 26, "session": 1, "region_code": null},
     "trigger": {"keycodes": [293, 294], "mode": "hold"},
     "write": {"verify_reads": 2, "max_attempts": 3, "min_rssi_gap_db": 6.0, "scan_ms": 1500}}}
   ```
   (nilai di atas CONTOH; isi dari hasil uji). Di C72: Diagnostik › *Ambil ulang profil dari ERP*.
4. Uji alur per jenis dengan dokumen staging (B19–B22) bersama operator.
5. Rilis produksi: signing rilis (`KN_RELEASE_*`), HTTPS saja (build rilis menolak http), catat matriks
   app/SDK/firmware/skema DB.

## 5. Risiko yang harus dicek di unit
- **Kode tombol & scan wedge:** aplikasi bawaan Chainway (Keyboard Emulator) bisa mengambil tombol pemicu/barcode.
  Matikan untuk aplikasi ini atau petakan; bila barcode SDK gagal, input teks tetap menerima ketikan wedge.
- **Urutan argumen `writeDataToEpc`** tidak terdokumentasi di AAR — B10/B13 membuktikannya. Bila salah, ubah HANYA
  `ChainwayC72Adapter.writeEpc`.
- **Region:** aplikasi tidak menyetel region kecuali profil commissioning mengisinya; pastikan unit Indonesia
  (920–923 MHz) dan catat kode regionnya.
- **Daya baca massal** di tumpukan 7 lapis: jarak & orientasi label (kiri/kanan/depan) menentukan; uji di stacker nyata.
- **Session S0 vs S1/S2** untuk tumpukan padat: bandingkan recall B6/B7 sebelum menetapkan profil.

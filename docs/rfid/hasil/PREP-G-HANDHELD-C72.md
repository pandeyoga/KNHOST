# PREP-G — Aplikasi handheld Chainway C72 0.1.0-lab + API ERP handheld

**Tanggal:** 9 Nov 2026 · **Pelaksana:** Claude Code (implementer) · **Branch:** `worktree-agent-ac67952708af5d072`
(di-*fast-forward* dari `70eb9fd` ke `main` `5f1e36e` sebelum mulai — worktree dibuat dari HEAD lama; perlu PREP-E
`core/*` & keputusan §9–§10) · **Commit:** `5063d48` (kode, tes, dokumen, APK) → commit laporan ini.
Acuan: [`KEPUTUSAN_GATE_RFID.md`](../KEPUTUSAN_GATE_RFID.md) §1 (C72 × 8), §6–§10 (K-GDG-02/03, K-OPN-05, §10 opsi a),
spesifikasi Kubus `02_MODUL_HANDHELD_C72.md` + `05_KONTRAK_API_TARGET.md`, rencana RFID-03/04/07/09.
**Tidak ada yang diuji di C72 fisik, emulator, atau runtime Android.** Semua perilaku SDK = belum terbukti.

## 1. Ringkasan
- **API ERP baru `/api/handheld/*`**: dua identitas wajib (device key per unit terikat gedung/site + sesi ERP operator),
  sesi operator (ganti operator, jejak siapa-perangkat-apa), daftar tugas **8 jenis** dari lokasi kerja pengguna ∩
  gedung perangkat, unduh **yang diharapkan** per dokumen (berhalaman, ber-versi struktur), **batch idempoten**
  ber-`client_batch_id` + cap waktu perangkat, validasi ulang server + **konflik per item**, selesaikan sesi, potong
  sampel, **tulis EPC sistem** (tag baru/ganti tag) dan **cadangan EPC** Daftar Awal untuk kerja offline, registri
  perangkat (buat, rotasi key, cabut, aktifkan, profil, aktivitas). Semua efek bisnis lewat layanan yang SUDAH ADA.
- **Aplikasi `middleware/c72-app/` (Java, tanpa pustaka tambahan, build offline)**: provisioning (QR), login operator,
  beranda per jenis, **layar pindai per dokumen** (Diharapkan/Terbaca/Kurang/Lebih, tombol ≥ 56 dp, pemicu fisik
  tahan/toggle, ikon + teks), **tulis EPC** (tag terdekat/RSSI terkuat, tolak ambigu, baca ulang, gagal ditangani),
  **cari tag**, barcode, **antrean offline SQLite** + sinkron (backoff, urutan per dokumen, pemilik per item), profil
  dari ERP + penimpaan lokal ber-PIN, **mode diagnostik uji meja** ber-PIN (ekspor JSON), Daftar Awal dengan form lengkap
  + foto. Lapisan `C72HardwareAdapter` memisahkan SDK; lapisan tugas = adaptor API.
- **Uji:** 11/11 pytest PREP-G · 101/101 tes host Java · 16/16 uji integrasi Java → ERP lokal · APK debug terbangun ·
  lint 0 error (66 peringatan). Regresi terkait: PREP-B/C/integrasi 22/22, PREP-D1/D2 31/31 (lihat §5).

## 2. Berkas
| Berkas | Isi |
|---|---|
| `backend/routers/handheld.py` (baru) | 27 endpoint `/api/handheld/*` |
| `backend/services/handheld_core.py` | autentikasi perangkat (`rfid_ingest_service.authenticate`), konteks perangkat+pengguna, cakupan gudang, profil bawaan & validasi, sesi operator, jenis tugas & izin |
| `backend/services/handheld_tasks.py` | daftar tugas per jenis, snapshot yang diharapkan (sesi eksplisit `start=true`), katalog produk |
| `backend/services/handheld_sync.py` | penyimpan idempoten `handheld_requests`, batch per jenis, selesaikan, potong |
| `backend/services/handheld_tags.py` | niat tulis tag + konfirmasi/gagal, cadangan EPC, baris Daftar Awal, lookup, belum bertag |
| `backend/services/handheld_devices.py` | registri perangkat handheld |
| `backend/tests/test_prep_g_handheld.py` | 11 skenario (data uji sendiri, dibersihkan) |
| `backend/server.py` | **kait 2 baris**: daftarkan router (sesudah `cutting.router`) |
| `backend/services/initial_registration_lines.py` | **kait 3 baris** di `build_line` mode EPC sistem: terima EPC cadangan perangkat bila kunci privat `_reserved_system_epc` (hanya dari `handheld_tags.process_lines`; model `RegLineIn` web tidak memuatnya) |
| `middleware/c72-app/**` | proyek Android, tes, dokumen `docs/01…03`, `delivery/KN-C72-Handheld-0.1.0-lab-debug.apk` + `SHA256SUMS.txt` |

Koleksi baru: `handheld_operator_sessions`, `handheld_requests` (idempotensi + bukti batch: bacaan mentah ≤ 2000,
`device_time`, `clock_skew_ms`, operator, perangkat), `handheld_tag_writes`, `handheld_epc_reservations`. Field baru di
`rfid_devices` (type `handheld`): `handheld_scope_level`, `handheld_profile`, `handheld_app_version`, `revoked_*`.
Field baru di `initial_registration_lines`: `hh_client_line_id`, `hh_device_id`, `hh_captured_at`. Di `rfid_tags`:
`written_via`, `written_by_device_id`, `write_id`.

## 3. Pemetaan jenis tugas → layanan asal
| Jenis (layar) | Dokumen / `doc_id` | Yang diharapkan | Kiriman |
|---|---|---|---|
| Masuk · Putaway | PA (`open/in_transit/partially_received`, tujuan di cakupan) | item PA | `confirm_arrival_trip` (`client_trip_id` = `client_batch_id`) |
| Keluar · SO / Sampel | `<order_id>~<warehouse_id>` | sesi `loading_check` | `scan_session(source=device)` · `loading_check_service.complete` |
| Transfer masuk | transfer `dispatched/partially_received` | `transfer_receipt_service.summary` + EPC tag aktif | `transfer_receipt_service.receive` (HANYA roll transfer itu) |
| Potong sampel | tugas `sample_cut` | roll calon produk & gudang (+ saran FIFO) | `sample_sale_service.cut_sample_task` |
| Stock Opname RFID | gudang | sesi `cycle_count` | `scan_session` · `cycle_count_service.complete` |
| Verifikasi cetak | print job `printed/verified_with_issues` | sesi `print_verify` | `scan_session` · `rfid_print_service.complete_verify` |
| Daftar Awal | sesi `registration` berjalan | bin cakupan, PT, satuan, EPC baris | `initial_registration_lines.add_line` (+ `mark_written`) |

## 4. Hasil uji (apa adanya)
| Uji | Hasil |
|---|---|
| `pytest tests/test_prep_g_handheld.py` (stack sementara `kn-tmp-g`, data acuan 8 Nov) | **11 passed** (3 putaran; putaran pertama SEBELUM Docker pulih: 8 passed, 1 gagal *ReadTimeout* 30 dtk pada `POST /tag-writes` pertama — tidak terulang di 3 putaran berikutnya maupun uji integrasi; dicatat sebagai risiko §8) |
| Regresi terkait: `test_prep_b_initial_registration`, `test_prep_c_warehouse_putaway`, `test_prep_integrasi_freeze_putaway` | **22 passed** |
| Regresi gate: `test_prep_d1_gate_v2` + `test_prep_d2_gate_txn` | gabungan: 30 passed, **1 failed** (`test_partial_trips_and_session_status`); diulang sendiri & D1 penuh: **20/20 passed** → dianggap *flaky* berbasis waktu, kode gate tidak disentuh |
| Tes host Java `test-host.ps1` (CoreTest 52, FlowTest 22, SyncTest 18, ApiTest 9) | **101 PASS, 0 FAIL** |
| Uji integrasi Java → ERP lokal `tests/run-erp-local.ps1` | **16 PASS** (device config, login ERP, tugas, expected berhalaman, pindai radio tiruan, offline → antre → kirim, kirim ulang = hasil tersimpan, trip 2 menutup PA, konflik final, tulis EPC + konfirmasi, opname 100 %, logout) |
| `assembleDebug` offline (AGP 8.2.2, Gradle 8.2) | **BUILD SUCCESSFUL**; APK `delivery/KN-C72-Handheld-0.1.0-lab-debug.apk` (SHA256 di §9) |
| `lintDebug` | **0 error, 66 peringatan** (54 `SetTextI18n` — UI sengaja teks Indonesia programatik; 11 `LockedOrientationActivity`; 1 `UnusedAttribute`) — `middleware/c72-app/tests/lint-results.txt` |
| `ruff check` berkas Python baru | bersih |
| C72 fisik / emulator / Android runtime | **TIDAK diuji** |

Gate dari `KN_00` (`seed_reset.sh`, `health_check.py`, sweep endpoint, `ux_audit.py`, `verify_contract.py`) **tidak
dijalankan**: DB bersama tidak boleh di-reset; paket ini menambah router baru tanpa mengubah endpoint lama.

## 5. Peta metode SDK (AAR `DeviceAPI_ver20251103_release.aar`, dirujuk dari `middleware/u300-agent/app/libs`)
Signature dari `javap` (classes.jar AAR = `deviceapi-classes.jar` toolchain, SHA256 `354081c7…694819`). Status SEMUA
baris: **belum terbukti** di C72. Rincian: `middleware/c72-app/docs/03_COMMISSIONING_UJI_MEJA.md` §1.

| Fungsi | Metode SDK |
|---|---|
| init / lepas | `RFIDWithUHFUART.getInstance()`, `init(Context)`, `free()`, `getVersion()`, `getHardwareVersion()`, `getErrCode()` |
| daya / session / region | `setPower/getPower`, `getGen2()/setGen2(Gen2Entity.setQuerySession)`, `setFrequencyMode/getFrequencyMode` (hanya bila profil mengisi) |
| baca massal | `setInventoryCallback(IUHFInventoryCallback)`, `startInventoryTag()`, `stopInventory()`; `UHFTAGInfo.getEPC/getTid/getRssi` (RSSI string, locale) |
| baca tunggal | `inventorySingleTag()` |
| tulis EPC | `writeDataToEpc(pwd, IUHF.Bank_EPC, 32, 96, epcLama, epcBaru)` — urutan argumen ditebak |
| cari tag | `startLocation(ctx, epc, Bank_EPC, 32, IUHFLocationCallback)`, `stopLocation()` (cadangan: RSSI pindai terfilter) |
| barcode 2D | `BarcodeFactory.getInstance().getBarcodeDecoder()`, `open/setDecodeCallback/startScan/stopScan/close`, `BarcodeEntity` |
| baterai | `BatteryManager` + `com.rscja.utility.BatteryUtils.*` |
| pemicu | keyCode profil `[139,280,291,293,294,311,312,313,315]` (Activity `onKeyDown/Up`) |

## 6. Daftar uji meja C72 (ringkas — lengkap di dokumen 03 §3)
B1 pasang APK & hash · B2 aplikasi bawaan/scan wedge · B3 init SDK · B4 versi · B5 daya set/baca ulang 5–30 dBm ·
B6 session S0/S1/S2 · B7 baca massal 30 tag (≥ 95 %, format RSSI mentah) · B8 laju & panas · B9 baca tunggal ·
B10 tulis + baca ulang + kembalikan (tag uji) · B11 dua tag berdekatan → ditolak · B12 daya tulis minimum stabil ·
B13 tulis tag di roll · B14 barcode QR/label supplier/bin · B15 cari tag (SDK vs cadangan) · B16 kode tombol →
profil · B17 pemicu di layar pindai (tanpa sesi ganda/freeze) · B18 baterai · B19 offline → sinkron sekali ·
B20 aplikasi dimatikan paksa → draf & antrean pulih · B21 ganti operator · B22 dua unit menulis roll sama ·
B23 ketahanan 4 jam. Hasil = JSON ekspor per unit → isi profil ERP → `commissioned: true`.

## 7. Keputusan implementer (belum keputusan pemilik)
1. **Cakupan perangkat bawaan = seluruh gedung di site gudang induk** (`scope_level: site`), bisa dipersempit ke satu
   gedung. Alasan: operator handheld bergerak antar gedung satu site (putaway transit → gedung simpan, transfer). Gudang
   efektif = perangkat ∩ lokasi kerja pengguna (`location_scope`, setelan `wms.location_scope_enforced`).
2. **PT dalam cakupan = semua PT yang ditugaskan ke pengguna** (bukan hanya PT aktif) — gedung dipakai bersama semua PT
   (K-GDG-07); kepemilikan tiap dokumen tetap dicek layanan asal. Opname memakai hanya PT yang boleh memakai gudang itu.
3. **Hasil bisnis final dikembalikan HTTP 200** (`accepted` / `conflict` / `rejected`) dan disimpan per ID klien;
   galat sementara (5xx, kunci saga, 429) tidak disimpan → diulang. Alasan: perangkat offline tidak boleh mengulang
   konflik tanpa akhir, dan kirim ulang tidak boleh menggandakan efek.
4. **EPC asing/bacaan sekitar tidak dikirim ke layanan mutasi** (transfer: tidak menjadi exception "salah kirim";
   PA: hanya kode milik item). Dicatat sebagai `extra` di hasil & bukti batch.
5. **Sesi cek muat/opname/verifikasi tidak pernah dibuat diam-diam**: snapshot tanpa sesi → `needs_start`; operator
   menekan *MULAI SESI* (`start=true`). Batch wajib membawa `session_id` snapshot (sesi tertutup → `DOC_CLOSED`, tidak
   pindah ke sesi baru). Spesifikasi Kubus §2.10.
6. **Tulis EPC = niat tulis dulu, tag lama tetap berlaku sampai baca ulang dikonfirmasi** (retire lama + aktifkan baru
   saat konfirmasi; kompensasi bila gagal). Satu niat terbuka per roll; perangkat lain ditolak. Konfirmasi boleh antre
   offline; pembuatan EPC butuh sambungan. Verifikasi baca ulang C72 diikat sebagai `journey.verified_tag_id`
   (operator menempel tag dulu lalu menulis).
7. **Daftar Awal offline lewat cadangan EPC per perangkat** (≤ 200, isi ulang otomatis ±50) — butuh kait 3 baris di
   `initial_registration_lines.build_line` (dicatat §2). EPC yang gagal ditulis tidak dipakai ulang.
8. **Potong sampel hanya online** (mutasi stok & harga sesuai keadaan sekarang); roll potongan langsung ditawarkan
   ke alur tulis tag.
9. **Simulasi**: radio tiruan boleh untuk sesi bukti (server mencatat `simulated`, tidak membuka dispatch/journey);
   tiba/terima/daftar ditolak `SIMULATION_NOT_ALLOWED`.
10. **Bukti milik operator penangkapnya**: antrean hanya dikirim saat pemiliknya login; server menolak
    `OPERATOR_MISMATCH`. Logout memanggil `/auth/logout` (token server dihapus) — antrean menunggu pemilik login lagi.
11. **Java + framework Android murni** (tanpa androidx/Kotlin) agar build offline dengan cache Gradle paket E.
    UI programatik bahasa Indonesia (lint `SetTextI18n` diterima).
12. Profil bawaan (titik awal uji meja, `commissioned=false`): baca 20 dBm, tulis 10 dBm, cari 26 dBm, S0, pemicu tahan,
    batch ≤ 2000 bacaan, snapshot ≤ 12 jam, tulis: 2 baca ulang, 3 percobaan, selisih RSSI ≥ 6 dB.

## 8. Sisa & risiko
- **Semua perilaku perangkat belum terbukti** (urutan argumen `writeDataToEpc`, kode region C72, keyCode pemicu,
  format RSSI, `startLocation`, BatteryUtils, aplikasi Keyboard Emulator yang bisa mengambil tombol/barcode). Satu
  titik ubah: `ChainwayC72Adapter`.
- **Tidak ada UI web** untuk registri handheld (pakai API atau menu RFID perangkat yang ada untuk buat & key). Teks QR
  provisioning dikembalikan API; layar QR di ERP = pekerjaan frontend berikutnya.
- **Transfer keluar** (verifikasi muat transfer di asal) dan **pemilihan bin/alamat per roll saat putaway** (API-20
  Kubus) belum dibangun; putaway handheld = konfirmasi tiba per trip.
- **Koreksi baris Daftar Awal yang ditolak** di HP = isi ulang (belum "muat baris ke form"); foto diunggah sesudah baris
  diterima ERP (endpoint foto yang ada).
- Satu *ReadTimeout* 30 dtk pada `POST /tag-writes` pertama di putaran uji pertama (saat Docker host kehabisan memori &
  memulai ulang); tidak terulang. Pantau saat uji staging; indeks dibuat lazim di permintaan pertama.
- `D1 test_partial_trips_and_session_status` gagal sekali di putaran gabungan, lulus saat diulang (flaky waktu).
- **Bentrok berkas**: `backend/server.py` (2 baris, sesudah `cutting.router`), `backend/services/initial_registration_lines.py`
  (3 baris di `build_line`). Ketergantungan ke fungsi paket F (`rfid_print_service.start_verify/scan_session/
  complete_verify/_verify_progress/get_print_job`) — bila paket F mengganti nama/semantik, `handheld_tasks/sync` perlu
  disesuaikan. Tidak menyentuh `rfid_v2_*`/`gate_*`/`u300-agent`/frontend.
- `middleware/README.md` & `CODEBASE_MAP.md` belum menyebut `c72-app` (di luar batas berkas paket) — tugas integrator.
- Volume ±6.000 roll/hari: batch ≤ 2000 bacaan, snapshot ≤ 5000 baris/halaman; uji beban belum dilakukan.

## 9. Pengiriman
- APK: `middleware/c72-app/delivery/KN-C72-Handheld-0.1.0-lab-debug.apk` (7 196 487 byte, debug signing) · SHA256
  `86d3cbfae11f7cef703f42babcc545e9cf378d8f2db14a5d3ee5d63f8febf646` (`delivery/SHA256SUMS.txt`).
- Commit implementasi `5063d48`; laporan ini commit berikutnya. Tidak di-push/merge; `docs/reviews/TRACKER.md` tidak diubah.
- Kontainer uji sementara `kn-tmp-g-*` dihapus setelah uji.

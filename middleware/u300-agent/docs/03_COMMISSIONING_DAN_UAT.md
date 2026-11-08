# Commissioning, uji meja, dan pengujian penerimaan (0.5.0-lab)

ERP Kain Nussantara · PT Kubus Teknologi Indonesia

Dokumen ini adalah daftar uji yang **harus dijalankan**; bukan pernyataan bahwa perangkat sudah lulus. Sampai 9 November
2026 belum ada U300, photo-eye, maupun emulator yang dipakai untuk menguji versi ini.

## 1. Peralatan dan informasi

- U300 + firmware/Android tercatat, catu daya, jaringan, **3 antena (atas/kiri/kanan)** + kabel RF (panjang/jenis
  dicatat — K-RFID-05), tag uji (50–100 untuk butir 7), tag tidak dikenal, barang uji beberapa roll.
- **Photo-eye through-beam 2 pasang** (A mulut masuk, B mulut keluar, ±1,5 m, tinggi 40–60 cm, Dark-ON) — K-RFID-01.
  Input U300 = optocoupler maks **12 V / 50 mA** [S] → sensor 24 VDC **wajib lewat relay/interface**.
- Indikator: lampu hijau, kuning, merah, buzzer pada GPO1–4 (open-collector [S]) lewat relay sesuai rating.
- ERP staging: perangkat terdaftar + device key, profil 2.1 diterbitkan, dokumen uji (SJ/transfer/putaway) dengan roll bertag.
- Laptop hanya untuk build/ADB/debug; layanan agent berjalan di U300.

## 2. Urutan commissioning

1. Cocokkan hash AAR; catat model, firmware, Android, versi APK.
2. **Layanan UHF bawaan** (§4) dimatikan; jalankan **uji meja K-RFID-03** (§5) dengan layanan agent berhenti.
   Ekspor hasil; tim memutuskan nilai profil (region, daya, Gen2, format antena, polaritas sensor).
3. Susun profil dari `docs/device-config.template.json`: `radio` (apply=true), `antenna_positions`, sensor A/B,
   indikator (mula-mula `enabled=false`), `passage_parameters` (`calibration_status: initial`). Terbitkan di ERP.
4. Mulai layanan: periksa audit "Inventory dimulai … setelan radio" — setiap butir `ok=true`.
5. Uji antena satu per satu (tag di depan satu antena → ringkasan hanya port itu). Uji tag rak (daftar latar).
6. Uji photo-eye: polaritas (`active_state`), A lalu B, mundur, muatan kecil, celah garpu/kaki stacker (`min_clear_ms`),
   dua muatan rapat, orang lewat, cahaya matahari. Bandingkan `beam_times` lintasan dengan pengamatan.
7. Sambungkan indikator (`enabled=true`, versi profil baru). Uji hijau/kuning/merah/buzzer tanpa barang lebih dulu.
8. Kasus ERP positif/negatif (trip penuh, trip parsial, roll asing, karantina, mundur, kosong).
9. Gangguan: jaringan putus di tengah lintasan, reboot saat lintasan, jam berubah, penyimpanan penuh, sensor dicabut
   (→ cadangan RF), admin menonaktifkan perangkat sementara (→ pulih sendiri).
10. Soak ≥ 24 jam inventory menyala terus (suhu, memori, `dropped_reads`, `ring_evicted`, ukuran DB).

## 3. Kalibrasi lokasi (titik awal → nilai terukur)

| Parameter | Awal | Cara mengukur |
|---|---|---|
| `pre_buffer_ms` | 3000 | `first_seen_mono` label depan vs `beam_times.a_blocked` pada 20 lintasan |
| `tail_ms` | 1500 | `last_seen_mono` roll belakang vs `b_cleared` |
| `min_block_ms` / `min_clear_ms` | 50 / 200 | celah garpu/kaki stacker dari rekaman tepi (uji meja butir 8) |
| `entry_timeout_ms` / `between_timeout_ms` | 10000 / 5000 | kecepatan terlambat yang masih wajar (≤ 5 km/jam) |
| `rssi_strong_dbm` per antena | −65 | puncak roll di gate vs tag rak terdekat (selisih ±15 dB menurut model) |
| `background_*` | 3 baca / 2 s / 10 dB | tag rak yang terbaca saat gate kosong; lonjakan saat stacker logam lewat |
| `rf_fallback_*` / `stable_interval_ms` | 3 EPC / 1,5 s / 3 s | lintasan dengan photo-eye dicabut |

Ubah = terbitkan `config_version` baru; setelah terukur set `calibration_status: calibrated`.

## 4. Layanan UHF bawaan U300

U300 punya layanan UHF bawaan (TCP 9160 raw, 9260 JSON, web 8080, MQTT) yang **memegang modul UHF** [S]; selama aktif
`init()` APK bisa gagal. Fakta dari AAR: `init()` SDK membaca properti `sys.uhf.service.enable` (`readTcpServiceState()`)
dan bila "1" mengirim broadcast `com.cw.reader.TcpServiceDisable` ke paket `cn.cw.uhf.tcpserver`, menunggu 2 s, lalu
membuka UART. Agent 0.5:

- Sebelum `init()`: mencatat properti, ada tidaknya paket `cn.cw.uhf.tcpserver`, port 9160/9260 terbuka.
- `agent_tuning.builtin_service.action = block` (bawaan): port terbuka sebelum **atau sesudah** `init()` → capture
  tidak dimulai, pesan di layar; `warn` → hanya dicatat. `init()` gagal → pesan menyebut kemungkinan layanan bawaan.

Langkah commissioning (konfirmasi di unit, uji meja butir 9): (1) catat apakah layanan bawaan mulai sendiri setelah
reboot dan sebelum `BootReceiver` agent; (2) matikan permanen lewat antarmuka vendor (web 8080 / pengaturan) bila
tersedia, lalu reboot dan ulangi butir 9; (3) bila web 8080 tetap aktif, **ganti sandi bawaan**; (4) bila layanan
tidak bisa dimatikan permanen, nilai bersama vendor apakah broadcast SDK cukup (port harus tertutup setelah `init()`).
Agent tidak memanggil API lain di luar AAR untuk mematikan layanan.

## 5. Uji meja K-RFID-03 (mode diagnostik di aplikasi)

Hentikan layanan agent → **Uji meja K-RFID-03 (mode diagnostik)** (PIN) → pilih butir → baca instruksi → **Jalankan**.
Hasil tersimpan otomatis; tambahkan **Catat pengamatan operator** (verdict + catatan, nama penguji) → **Ekspor seluruh
hasil uji meja (JSON)** → lampirkan ke keputusan K-RFID-03.

| Butir | Yang dicatat aplikasi | Pengamatan operator |
|---|---|---|
| 1 Format `getAnt()` | string mentah + jumlah per string, hasil parse agent, daftar `getANT()` | port fisik ↔ string; 1-based? (`antenna_index_base`) |
| 2 Format `getRssi()` | locale, string mentah, jumlah N/A, desimal koma, rusak, min/maks | nilai selalu negatif dBm? |
| 3 `getCount()`, phase, frequency, timestamp | sebaran count; porsi phase/frequency ≠ 0 (bawaan vs `InventoryParameter`); selisih timestamp SDK vs callback | arti count |
| 4 Gen2 / TagFocus / FastID | `getGen2` (14 field), TagFocus, FastID, RF link, FastInventory, region — sebelum & sesudah `free()/init()`; opsi terapkan profil + baca-balik | jalankan sebelum & sesudah aplikasi demo vendor |
| 5 Region & firmware | `getVersion`, `getHardwareVersion`, region; opsi set 63 → baca → kembalikan | 63 = 920–923 MHz? |
| 6 Daya per antena | set 5/10/15/16/20/25/26/30/33 → baca-balik → kembalikan, per port | langkah & batas nyata |
| 7 Laju callback | 3 × 10 s: callback kosong / SQLite per bacaan / antrean 0.5 → bacaan/s, unik, terbuang, lama INSERT | jumlah & posisi tag |
| 8 GPI/GPO | level idle GPI1–4, latensi `inputStatus()` p50/p95/maks (inventory mati & menyala), tepi 15 s; opsi siklus GPO 1–4 | terminal ↔ GPI/GPO, lampu yang menyala, level saat sinar terhalang |
| 9 Layanan bawaan | properti, paket, port 9160/9260/8080 sebelum & sesudah `init()`, lama `init()` | perilaku setelah reboot |

Mode simulasi menghasilkan data bertanda `SIMULASI` hanya untuk mencoba alur layar & ekspor.

## 6. Matriks penerimaan

Semua baris **BELUM DIJALANKAN di Android/perangkat nyata**. Isi tanggal, perangkat, hasil, bukti log/ekspor, penanggung jawab.

| ID | Skenario | Hasil yang harus dibuktikan |
|---|---|---|
| U01–U04 | Instal; PIN salah 5×; layanan tetap aktif; reboot + autostart | tanpa crash; PIN terkunci; tidak memberi izin lama |
| U05 | SDK init gagal / layanan bawaan aktif | radio tidak ready; pesan jelas; tidak ada hijau |
| U06 | Setelan radio tidak cocok (region/daya/Gen2/TagFocus) | capture tidak dimulai; laporan per butir |
| U07 | Antena benar/salah/format "ANT1"/"01" | port dipetakan benar; antena di luar peta dikarantina ERP, capture tetap jalan |
| U08–U10 | EPC berulang; EPC sama di lintasan baru; EPC rusak | count ringkasan benar; summary baru per lintasan; EPC mentah tetap terkirim |
| U11–U16 | ACK parsial; timeout; non-durable; karantina; 413; 429 | sama dengan 0.4 (ID tetap, backoff); 413 dipecah adaptif |
| U17 | AUTH_REQUIRED/AUTH_INVALID | blokir transport, antrean utuh |
| U18 | ADMIN_DISABLED / CONFIG_REQUIRED / 403 proxy | polling lambat, pulih sendiri tanpa ke lokasi |
| U19–U21 | Offline sebelum/di tengah lintasan; restart saat OPEN | backfill tanpa hijau; kehilangan izin; ABORTED tidak lengkap |
| U22–U27 | Keputusan salah konteks/basi/REVIEW/RED/acknowledge | hijau hanya keputusan valid; kuning untuk REVIEW; merah sampai diakui |
| U28 | **Lewat normal** A↓ B↓ A↑ B↑ | `BEAM_A`/`EXITED`, `pre_buffer` memuat label depan, latensi lampu ≤ 3 s setelah B↑ (M10) |
| U29 | **Mundur** sebelum/sesudah B | `ABORTED`/`REVERSED`, tanpa transaksi; kuning bila ada roll dokumen |
| U30 | **Muatan kecil** 1–3 roll (A bebas sebelum B) | satu lintasan `EXITED` |
| U31 | **Orang / forklift kosong** | CANCELLED, tanpa alarm |
| U32 | **Dua muatan rapat** | digabung → kuning; tidak merah palsu |
| U33 | **Stacker berhenti di gate** | TIMEOUT → kuning |
| U34 | **Photo-eye dicabut / sinar macet / B sebelum A** | cadangan RF, laporan kesehatan, pulih setelah 2 lintasan sah |
| U35 | **Tag rak / tag diam** | daftar latar; tidak membuka/memperpanjang lintasan; `in_background=true` |
| U36 | **Logam memantulkan sinyal ke rak** (stacker lewat) | tag rak tetap latar/lemah; terburuk kuning, bukan merah |
| U37 | **Trip parsial** dokumen (K-RFID-10) | hijau tiap trip; sisa dinilai saat dokumen ditutup |
| U38 | Locale perangkat Bahasa Indonesia | RSSI terbaca (`rssi_missing` ≈ 0) |
| U39 | Beban 100 roll × 3 antena, session 0 | `dropped_reads` = 0, antrean habis dalam satu siklus multi-batch, keputusan segar |
| U40 | Jam Android dimajukan/dimundurkan | tidak memperpanjang hijau/kuning |
| U41 | Indikator 4 GPO + buzzer, power loss, GPO error | fisik sesuai; fail-safe dibuktikan, bukan diasumsikan |
| U42 | Soak 24 jam | tanpa ANR; suhu; DB & antrean terukur |

## 7. Titik selesai menuju produksi

Release produksi baru dapat disetujui setelah: uji meja K-RFID-03 diputuskan; seluruh kasus wajib lulus; parameter
lintasan terkalibrasi (`calibration_status: calibrated`); profil/wiring dicatat; SOP lintasan disepakati (K-RFID-06);
target M1–M11 diputuskan (K-RFID-08); signing produksi; backup/recovery, monitoring dan retensi diputuskan; bukti uji
ditandatangani tim. Build atau simulasi yang lulus bukan bukti perangkat siap.

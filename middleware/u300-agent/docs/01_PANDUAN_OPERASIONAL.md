# Panduan pemasangan dan penggunaan (0.5.0-lab)

ERP Kain Nussantara · PT Kubus Teknologi Indonesia

## A. Menjalankan simulasi tanpa reader

1. Pasang APK pada perangkat Android ARM API 30 atau lebih baru (emulator harus mendukung ABI ARM). Mode bawaan =
   simulasi; U300 belum diperlukan.
2. Buka **KN U300 Agent · LAB**. Tindakan pemeliharaan pertama meminta PIN 6–12 angka; lima kali salah mengunci satu menit.
3. Tekan **Mulai layanan**. Layanan memakai profil simulasi 2.1 (gate OUT satu arah, photo-eye GPI1 = A mulut masuk,
   GPI2 = B mulut keluar, 3 antena atas/kiri/kanan, basis `document_session`, 4 GPO) dan menampilkan *Radio ready*.
4. Di **Laboratorium simulasi** pilih skenario gate lalu **Jalankan skenario gate**:

| Skenario | Yang disimulasikan | Hasil yang diharapkan di agent |
|---|---|---|
| `lewat` | 6 roll, sinar A↓ B↓ A↑ B↑ | lintasan `BEAM_A → EXITED`, ringkasan per EPC × antena, keputusan sesuai pilihan |
| `lewat_kecil` | 2 roll dibawa orang (A bebas sebelum B terpotong) | tetap satu lintasan `EXITED` |
| `mundur` | masuk lalu mundur (B bebas dulu, A terakhir) | `REVERSED` → simulator: CANCELLED (padam) |
| `batal_masuk` | A terpotong lalu bebas tanpa B | `ABORTED` setelah `between_timeout_ms` |
| `kosong` | orang/forklift kosong | lintasan tanpa ringkasan → CANCELLED, tanpa alarm |
| `beriringan` | dua muatan rapat | satu lintasan digabung, `capture_complete=false` → kuning |
| `b_sebelum_a` | sinar B terpotong lebih dulu | photo-eye **fault** → cadangan RF membuka lintasan dari rombongan tag |
| `sinar_macet` | sinar A terhalang terus | setelah `sensor_stuck_ms` (45 s) → fault → cadangan RF |
| `sinar_pulih` | dua urutan A→B sah | photo-eye kembali sehat |
| `latar` | tag rak terbaca terus di antena 3 saat gate kosong | masuk daftar latar (`in_background=true` di lintasan berikut) |

   RSSI simulasi sengaja berformat locale Indonesia (`-48,50`) untuk menguji parse tahan locale.
5. **Pakai keputusan simulasi** (GREEN / REVIEW / RED / UNKNOWN) berlaku untuk lintasan berikut. Lintasan mundur/kosong
   selalu CANCELLED; capture tidak lengkap atau cadangan RF = REVIEW (kecuali RED). **Sisa roll dokumen** (0/2/5)
   mensimulasikan trip parsial `document_session`: hijau tetap boleh walau sisa > 0.
6. RED mengunci gate (lampu merah + buzzer singkat) sampai **Simulasikan supervisor melepas kunci gate**.
7. Offline (checkbox) sebelum lintasan → lintasan *backfill* (tidak pernah hijau/kuning); di tengah lintasan → lintasan
   itu kehilangan izin sinyal.
8. **Skenario jaringan** untuk satu request berikutnya: `partial`, `retry`, `not-durable`, `overflow` (ACK karantina
   CAPTURE_OVERFLOW), `http-413`, `http-429`, `http-500`, `admin-disabled`, `config-required`, `auth-invalid`,
   `evidence-pending`, `passage-frozen`, `event-id-conflict`, `http-400/403/409`.
9. **Histori lintasan & diagnosis** menampilkan pembuka/penutup lintasan, jumlah ringkasan & tepi, kesehatan photo-eye,
   keputusan + daftar alasan + sisa roll dokumen.

Simulasi memakai keputusan pilihan operator; ia tidak memeriksa manifest, stok, atau dokumen nyata.

## B. Menyiapkan U300 nyata

1. Jalankan dulu **Uji meja K-RFID-03** (dokumen 03 §5) — hentikan layanan agent saat uji meja.
2. Hentikan layanan sebelum **Konfigurasi & provisioning**. Nonaktifkan mode simulasi. Isi origin ERP HTTPS (tanpa path,
   query, kredensial), logical gate ID, device key khusus perangkat. Key disimpan terenkripsi Android Keystore.
3. ERP harus menerbitkan profil 2.1 yang valid: `agent_profile=kn-u300-v1`, `commissioned=true`, `radio.region_code`,
   `radio.antenna_power_dbm` per port, `antenna_positions` per port, sensor A/B, indikator — hasil commissioning,
   bukan tebakan (template: `docs/device-config.template.json`).
4. **Mulai layanan**. Saat start agent memeriksa layanan UHF bawaan, menyetel & membaca ulang setelan radio, lalu
   mengaktifkan antena. Satu butir gagal → capture tidak dimulai; pesan menyebut butirnya. Jangan mengubah profil hanya
   untuk menghilangkan pesan tanpa memeriksa perangkat.
5. Setelah uji boot berhasil, opsi mulai otomatis setelah reboot dapat diaktifkan (uji juga pembatasan baterai vendor
   dan urutan start terhadap layanan UHF bawaan — uji meja butir 9).

## C. Arti status dan indikator

| Status | Makna |
|---|---|
| Indikator **HIJAU** | Keputusan ERP final & segar untuk lintasan terakhir: semua roll kuat milik dokumen aktif (boleh trip parsial) |
| Indikator **KUNING** | REVIEW: barang boleh jalan, lintasan masuk antrean periksa di ERP; gate tidak terkunci |
| Indikator **MERAH** (+ buzzer singkat) | Gate terkunci karena pelanggaran; dilepas hanya lewat pengakuan supervisor di ERP |
| **PADAM** | Belum ada izin (bukan izin bergerak): menunggu keputusan, CANCELLED, offline, backfill, kedaluwarsa |
| Photo-eye `ok` / `fault` / `absent` / `degraded` | sehat / rusak → **CADANGAN RF** aktif / gate tanpa sensor / lintasan digabung |
| ERP `admin_disabled` / `config_required` / `forbidden` | dinonaktifkan admin / profil belum terbit / 403 tanpa kode — dicek ulang berkala, pulih sendiri |
| ERP `auth_block` / `contract_block` | key ditolak (provisioning ulang) / kontrak ditolak (Pemulihan ber-PIN) |
| Latar *n* EPC (belum hangat) | daftar tag latar gate; "belum hangat" = belum cukup waktu IDLE untuk dipercaya |
| Dibuang / Tanpa RSSI | bacaan terbuang karena antrean RAM penuh / bacaan tanpa RSSI (N/A) |
| Antrean / Karantina / Ditolak | item belum ACK / diterima server sebagai karantina / ditolak lokal (PASSAGE_FROZEN) — semuanya tetap tersimpan |

Jeda capture: menutup lintasan aktif (tidak lengkap) dan menghentikan radio; pengiriman antrean tetap berjalan.
PIN adalah otorisasi pemeliharaan lokal, bukan role ERP.

## D. Penanganan gangguan

- **AUTH_REQUIRED / AUTH_INVALID (401):** hentikan layanan, periksa registrasi/key di ERP, perbarui provisioning dengan
  ERP & gate yang sama. Antrean tidak dialihkan ke perangkat lain.
- **ADMIN_DISABLED (403) / CONFIG_REQUIRED (409) / 403 tanpa kode:** tidak perlu ke lokasi. Agent menunggu
  `poll_after_seconds` (bawaan 60 s) lalu mencoba lagi; capture mengikuti kebijakan offline.
- **400 / EVENT_ID_CONFLICT / CLOSE_CONFLICT / DEVICE_MOVED / GATE_NOT_BOUND:** ekspor diagnosis, perbaiki di ERP,
  lalu **Pemulihan koneksi / kontrak** (ID & body asli dikirim ulang).
- **413 BATCH_TOO_LARGE:** otomatis dipecah (batas body sementara separuh). **PASSAGE_FROZEN:** item ditolak lokal,
  lintasan ditandai tidak lengkap, transport lanjut. **EVIDENCE_PENDING:** close lintasan itu dicoba ulang bertahap.
- **Photo-eye fault:** agent tetap bekerja dengan cadangan RF (keputusan kuning sampai terkalibrasi). Periksa kabel,
  relay, kotoran lensa, sinar terhalang; agent pulih sendiri setelah dua lintasan A→B sah.
- **Layanan UHF bawaan aktif (port 9160/9260 terbuka) atau `SDK init gagal`:** dokumen 03 §4.
- **Setelan radio gagal:** pesan menyebut butir (region/daya/Gen2/TagFocus…). Bandingkan dengan hasil uji meja; jangan
  mengubah profil tanpa bukti unit.
- **Antrean penuh / disk:** pulihkan koneksi/kapasitas; tidak ada pembuangan otomatis data lama.
- **Restart saat lintasan terbuka:** lintasan dikirim `ABORTED` tidak lengkap (tanpa klaim lewat di ERP); ulangi sesuai SOP.

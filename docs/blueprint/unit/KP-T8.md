# KP-T8 — Rahasia dan perangkat: token mesin absen aman, satu cara menyimpan rahasia, satu koneksi WhatsApp

| | |
|---|---|
| Gelombang | Jalur konfigurasi perusahaan (U) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | KF-T1 |
| Menutup temuan | KP-14, KP-15, KP-16, KP-31, KP-32 |
| Keputusan | K-47 (izin baru diberikan setara akses yang sudah ada); `00` §4.1; titik henti H3 (migrasi data nyata), H8 (unit tidak meminta rahasia apa pun) |
| Standar | §2.1, §2.2, §3.1 (Z1, Z2, Z6), §3.2, §4 (L1, L5, L6), §5 (D1, D8), §6 |
| Lingkungan uji | B |

## Tujuan

Token mesin absen tidak lagi terbaca siapa pun setelah dibuat dan bisa diganti, tanpa memutus mesin yang sudah
terpasang. Semua rahasia yang harus dikirim ke pihak luar disimpan dengan pembungkus enkripsi yang sama. Koneksi
WhatsApp diatur di satu tempat untuk dua pemakainya. Kunci integrasi dijaga izinnya sendiri.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| # | Fakta | Jangkar |
|---|---|---|
| 1 | Daftar perangkat absen mengembalikan seluruh dokumen, termasuk `device_token`, kepada pemegang `hr.view` | `backend/routers/hr_attendance.py:189` (`list_devices`) |
| 2 | Token dibuat dari 12 karakter heksadesimal dan disimpan apa adanya | `backend/routers/hr_attendance.py:205` (`device_token`); `backend/core_utils.py:128` (`new_id`) |
| 3 | Endpoint penerima absen dari mesin tidak memakai sesi; ia hanya mencocokkan `device_token` polos dengan perangkat aktif | `backend/routers/hr_attendance.py:504` (`ingest_attendance`) |
| 4 | Layar menyediakan tombol "Salin token perangkat" pada tiap baris | `frontend/src/features/hr/AttendanceSetupView.jsx:158` (`copyToken`) |
| 5 | Kunci penyedia asisten dienkripsi (awalan `enc:v1:`, kunci dari variabel lingkungan `KN_SECRETS_KEY`); tanpa variabel itu nilai disimpan polos; kunci polos lama dienkripsi saat pertama dibaca | `backend/services/integrations_service.py:38` (`_fernet`); `backend/services/integrations_service.py:47` (`_enc`); `backend/services/integrations_service.py:62` (`get_integrations`) |
| 6 | Kunci perangkat RFID disimpan sebagai hash dan hanya ditampilkan sekali; kunci polos lama di-hash dan ditandai wajib ganti | `backend/services/rfid_ingest_service.py:22` (`hash_device_key`); `backend/services/rfid_ingest_service.py:26` (`ensure_api_key`) |
| 7 | Token WhatsApp pengingat disimpan polos di `system_settings{scope: "alerts"}.wa`; jawaban API sudah menyamarkannya | `backend/routers/scheduler.py:131` (`cur`); `backend/services/wa_alert_service.py:84` (`mask_wa`) |
| 8 | Token WhatsApp kirim-dokumen disimpan polos di koleksi lain, `integration_settings`, dengan penyedia dan nomornya sendiri | `backend/services/delivery_service.py:49` (`access_token`); `backend/services/delivery_service.py:86` (`access_token`); `backend/routers/deliveries.py:64` (`put_wa_settings`) |
| 9 | Layar pengaturan WhatsApp kedua dibuka dari Pusat Dokumen, bukan dari grup Pengaturan | `frontend/src/features/documents/DocumentCenter.jsx:275` (`WhatsAppSettings`); `frontend/src/features/documents/WhatsAppSettings.jsx:26` (`deliveries/whatsapp/settings`) |
| 10 | Hidup/mati dan model pengenal gambar diatur di layar Integrasi (`anthropic.enabled`, `anthropic.model`); hidup/mati dan model asisten analitik diatur di registry (`ai.enabled`, `ai.model_main`) | `backend/services/hr_ai_service.py:40` (`is_enabled`); `backend/services/ai_narrative.py:70` (`ai_available`); `backend/config_catalog_ai.py:40` (`ai.enabled`) |
| 11 | Empat endpoint integrasi dijaga izin `hr.manage_settings`, yang juga menjaga pengaturan SDM | `backend/routers/integrations.py:20` (`get_integrations`); `backend/routers/integrations.py:27` (`update_integrations`); `backend/routers/hr.py:500` (`manage_settings`) |
| 12 | Kunci registry ber-awalan tertentu disimpan di dokumen `system_settings` ber-`scope` sama dengan awalannya | `backend/config_registry.py:54` (`LEGACY_SCOPED_PREFIXES`) |

## Perubahan

### Data

`hr_devices`:

| Field | Tipe | Arti |
|---|---|---|
| `device_token_hash` | teks (SHA-256 heksadesimal) | Pengganti `device_token` |
| `device_token_hint` | teks 4 karakter | Empat karakter terakhir token, untuk dikenali di layar |
| `device_token_at` | waktu | Kapan token terakhir dibuat/diganti |
| `token_rotation_required` | boolean | Benar untuk token lama yang pernah tampil di layar |

Indeks unik parsial pada `device_token_hash` (hanya dokumen yang punya field itu).

`system_settings{scope: "integrations"}` mendapat objek `whatsapp`: `{provider, access_token, fonnte_token,
phone_number_id, sender, sender_label, default_country_code, template_name, template_lang, source, updated_at,
updated_by}` — **koneksi tunggal**; dua field token selalu tersimpan terbungkus. Pengaturan pemakaian tetap di
tempatnya: pengingat (`alerts.wa`: `enabled`, `pic_number`, `send_to_roles`, `min_severity`, `delivery_mode`,
`critical_bypass`) dan kirim dokumen (`integration_settings`: `enabled`, `simulate`).

Migrasi `scripts/migrate_kpt8_rahasia.py` (hanya-lapor sebagai bawaan; data nyata dijalankan pemilik — H3; aman
diulang):

1. Tiap `hr_devices` ber-`device_token`: tulis `device_token_hash` = SHA-256 token itu, `device_token_hint`,
   `token_rotation_required: true`, lalu buang `device_token`. **Token yang terpasang di mesin tetap berlaku**,
   karena mesin mengirim token yang sama dan server kini membandingkan hash-nya.
2. Token WhatsApp polos di `alerts.wa` dan `integration_settings` dibungkus (hanya bila `KN_SECRETS_KEY` terpasang).
3. Koneksi WhatsApp: bila hanya satu dari dua konfigurasi yang terisi (yang lain simulasi/kosong) → disalin menjadi
   koneksi tunggal; bila keduanya terisi dan **sama** (penyedia, nomor, token) → digabung; bila **berbeda** → tidak
   digabung, dilaporkan sebagai "dua koneksi berbeda" untuk diputuskan pemilik di layar.
4. Peran (bawaan atau kustom) yang memegang `hr.manage_settings` diberi `integration.manage`; daftarnya dilaporkan.

Sebelum skrip dijalankan tidak ada yang putus: pembaca di bawah menerima bentuk lama maupun baru.

### Server

**Pembungkus rahasia.** Berkas baru `backend/services/secret_box.py`, dipindahkan dari `integrations_service`
(awalan dan variabel lingkungan tidak berubah, sehingga nilai lama tetap terbaca):

| Fungsi | Perilaku |
|---|---|
| `def available() -> bool` | `KN_SECRETS_KEY` terpasang |
| `def seal(value: str) -> str` | Kosong, sudah terbungkus, atau kunci belum terpasang → dikembalikan apa adanya; selain itu `enc:v1:…` |
| `def open(value: str) -> str` | Tidak terbungkus → apa adanya; terbungkus tanpa kunci → galat "KN_SECRETS_KEY belum diisi — rahasia terenkripsi tidak bisa dibaca." |
| `def hash_token(value: str) -> str` | SHA-256 heksadesimal (dipakai token yang hanya perlu **dicocokkan**) |

Aturan pakai: rahasia yang harus dikirim ke pihak luar (kunci penyedia, token WhatsApp) → `seal`/`open`; rahasia
yang hanya dicocokkan server (token mesin absen, kunci perangkat RFID) → hash. `integrations_service`,
`wa_alert_service.raw_settings`, `routers/scheduler.py` (simpan), dan `delivery_service` memakainya; token polos
lama dibungkus saat pertama dibaca bila kunci terpasang (pola yang sudah ada pada butir 5).

**Mesin absen** (`backend/routers/hr_attendance.py`):

| Endpoint | Izin | Perubahan |
|---|---|---|
| `GET /api/hr/devices` | `hr.view` (tetap) | Tidak pernah mengirim `device_token` maupun `device_token_hash`; menambah `device_token_hint`, `device_token_at`, `token_rotation_required` |
| `POST /api/hr/devices` | `hr.manage_attendance` (tetap) | Token baru = `at_` + 32 karakter heksadesimal acak; disimpan hash-nya. Jawaban memuat `device_token` **sekali** dan `shown_once: true` |
| `POST /api/hr/devices/{id}/rotate-token` (baru) | `hr.manage_attendance` | Cakupan PT diperiksa seperti `PATCH`. Membuat token baru, menimpa hash, `token_rotation_required: false`. Jawaban `{device_id, device_token, device_token_hint, shown_once: true}`. Token lama langsung tidak berlaku. Jejak `hr_device_token_rotated` (tanpa token) |
| `PATCH /api/hr/devices/{id}` | tetap | Jawaban tanpa field token |
| `POST /api/hr/attendance/ingest` | tanpa sesi (tetap) | Cari perangkat aktif ber-`device_token_hash` = hash token kiriman; bila tidak ada, cari bentuk lama `device_token` = token kiriman. 401 "device_token tidak valid" seperti hari ini |

**Koneksi WhatsApp.** Berkas baru `backend/services/wa_connection.py`:
`async def for_consumer(name: "alerts" | "documents") -> dict` — mengembalikan koneksi tunggal (token sudah dibuka)
bila ada; bila belum ada, mengembalikan konfigurasi lama pemakai itu (perilaku hari ini). `wa_alert_service._dispatch`
dan `delivery_service.send_whatsapp` mengambil penyedia dan kredensial dari sini.

| Metode + path | Izin | Isi → jawaban |
|---|---|---|
| `GET /api/admin/integrations/whatsapp` | `integration.manage` | → `{provider, phone_number_id, sender, sender_label, default_country_code, template_name, template_lang, has_access_token, has_fonnte_token, configured, used_by: {alerts: bool, documents: bool}, conflict: null \| {alerts: {...}, documents: {...}}, secrets_key_configured}`; token tidak pernah dikirim |
| `PUT /api/admin/integrations/whatsapp` | `integration.manage` | Field koneksi; token kosong/tidak dikirim = tidak diubah; `clear_tokens: true` menghapus. Validasi penyedia seperti hari ini ("Meta Cloud butuh access_token + phone_number_id…", "Fonnte butuh fonnte_token…") |
| `POST /api/admin/integrations/whatsapp/adopt` | `integration.manage` | `{from: "alerts" \| "documents", reason}` — menjadikan konfigurasi lama itu koneksi tunggal untuk keduanya. 409 "Koneksi WhatsApp sudah satu." bila tidak ada yang perlu diputuskan |
| `POST /api/admin/integrations/whatsapp/test` | `integration.manage` | `{phone, text?}` → hasil kirim uji (memakai jalur `send_test` yang ada) |

Setelah koneksi tunggal ada: `PUT /api/scheduler/settings` dan `PUT /api/deliveries/whatsapp/settings` menolak field
koneksi (`provider`, `access_token`, `fonnte_token`, `phone_number_id`, `sender`, `template_*`, `sender_label`,
`default_country_code`, `clear_tokens`) dengan 400 "Koneksi WhatsApp diatur di Pengaturan › Integrasi & Sistem." Field
pemakaian tetap diterima. Sebelum koneksi tunggal ada, kedua endpoint bekerja seperti hari ini (token dibungkus).

**Izin integrasi.** Empat endpoint `/api/admin/integrations…` yang ada berpindah dari `hr.manage_settings` ke
`integration.manage`. `GET /api/admin/integrations` menambah `secrets_key_configured`. `hr.manage_settings` tetap
menjaga pengaturan SDM.

Pesan 403 (Z6): "Anda belum punya akses untuk mengatur integrasi. Minta Admin menambahkan akses 'Pengaturan, Pengguna
& Hak Akses'."

### Pengaturan

Satu tempat untuk hidup/mati dan model (KP-31): `LEGACY_SCOPED_PREFIXES` ditambah `"integrations"`, lalu dua kunci
didaftarkan di `backend/config_catalog_ai.py`. Karena awalan itu, nilainya tersimpan di dokumen yang **sama** dengan
hari ini (`system_settings{scope: "integrations"}.anthropic.enabled|model`) — tanpa migrasi, dan
`hr_ai_service.is_enabled` tetap membaca nilai yang sama.

| Field | `integrations.anthropic.enabled` | `integrations.anthropic.model` |
|---|---|---|
| `group` | `asisten-analitik` | `asisten-analitik` |
| `type` · `default` | `bool` · `False` (= `DEFAULT_INTEGRATIONS`) | `enum` · nilai `integrations_service.DEFAULT_MODEL`; `options` = `ANTHROPIC_MODELS` |
| `scopes` | `("global",)` | `("global",)` |
| `label` | "Pengenal gambar desain aktif" | "Model pengenal gambar desain" |
| `help` | "Menyalakan pemberian tag otomatis pada gambar di galeri desain. Butuh kunci penyedia di Integrasi." | "Model yang dipakai memberi tag gambar desain." |
| `impact` | "Mati = unggahan desain tidak diberi tag otomatis; galeri tetap berjalan." | "Model lebih besar lebih teliti dan lebih mahal per gambar." |
| `example` | "Aktif → desain baru mendapat tag motif dan warna dalam beberapa detik" | "Model bawaan untuk pemakaian harian" |
| `risk` · `permission` | `low` · `("integration", "manage")` | `low` · `("integration", "manage")` |
| `consumers` | `services/hr_ai_service.py:is_enabled` | `services/hr_ai_service.py:autotag_image` |

`PUT /api/admin/integrations` berhenti menerima `anthropic_enabled` dan `anthropic_model` (400 "Hidup/mati dan model
diatur di Pusat Pengaturan › Asisten."); kunci penyedia tetap di sana. Uji putaran `t1_config.py` wajib lulus untuk
kedua kunci.

### Izin dan peran

| Pasangan | Peran bawaan | Modul akses | Id menu |
|---|---|---|---|
| `integration.manage` (label aksi "Kelola") | `admin` | "Pengaturan, Pengguna & Hak Akses" (`admin`) — `resources` ditambah `integration` | `admin`, `settings-system` (sudah ada di `nav` modul itu) |

Empat tempat (`02` §3.2): `permissions_config.DEFAULT_PERMISSIONS`, `access_modules.MODULE_CATALOG`, delapan endpoint
integrasi (empat yang ada + empat koneksi WhatsApp), tombol layar (`can(perms, "integration", "manage")`).

### Layar

- **Mesin absen** (Pengaturan › Integrasi & Sistem › Perangkat; `AttendanceSetupView.jsx`): tombol "Salin token
  perangkat" dibuang. Baris perangkat menampilkan "Token berakhiran …{hint}" dan tombol **Ganti token**
  (`hr.manage_attendance`). Konfirmasi: "Ganti token {nama}? Mesin yang masih memakai token lama berhenti mengirim
  absen sampai diisi token baru." Setelah buat atau ganti, pop-up **Token perangkat** menampilkan token, tombol
  **Salin**, dan kalimat "Token hanya ditampilkan sekali. Simpan sekarang." Baris ber-`token_rotation_required`
  diberi tanda "Disarankan ganti — token lama pernah tampil di layar."
- **Integrasi** (Pengaturan › Integrasi & Sistem › Integrasi & Audit): kartu baru **WhatsApp** — isian "Penyedia",
  "Token" (hanya-tulis; "Sudah terisi" bila ada), "ID nomor pengirim", "Nama pengirim", "Kode negara bawaan", "Nama
  template", tombol **Simpan** dan **Kirim uji**; baris "Dipakai oleh: Pengingat · Kirim dokumen". Bila `conflict`
  ada: kotak kuning **Ada dua koneksi WhatsApp berbeda** dengan ringkasan keduanya (tanpa token) dan dua tombol
  **Pakai koneksi Pengingat untuk keduanya** / **Pakai koneksi Kirim Dokumen untuk keduanya** (alasan wajib).
- Bila `secrets_key_configured` salah: peringatan "Kunci enkripsi server belum dipasang. Rahasia yang disimpan
  sekarang belum terenkripsi."
- Sakelar hidup/mati dan pilihan model pengenal gambar dibuang dari kartu penyedia; gantinya tautan "Hidup/mati dan
  model diatur di Pusat Pengaturan › Asisten."
- Tab WhatsApp di Penjadwal & Notifikasi dan pop-up WhatsApp di Pusat Dokumen: setelah koneksi tunggal ada, isian
  koneksi diganti ringkasan hanya-baca + tautan **Atur koneksi di Integrasi**; isian pemakaian tetap.

## Uji penerimaan

Persiapan bersama: seed lingkungan B; akun admin; `KN_SECRETS_KEY` diisi kunci uji yang dibuat di dalam tes
(`Fernet.generate_key()`), kecuali disebut.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | `POST /api/hr/devices` `{name: "Mesin A"}`; lalu `GET /api/hr/devices` | POST memuat `device_token` berawalan `at_` dan `shown_once: true`; dokumen di database tidak punya `device_token`, punya `device_token_hash`; GET tidak memuat kunci `device_token` maupun `device_token_hash` pada baris mana pun |
| U2 | B | Token dari U1 | `POST /api/hr/attendance/ingest` `{device_token: <token>, records: []}`; lalu dengan token diubah satu karakter | 200; 401 "device_token tidak valid" |
| U3 | B | Perangkat lama disisipkan langsung: `{id, device_token: "devtok_abc123abc123", status: "active", entity_id: "ent_ksc"}` | Ingest dengan token itu **sebelum** migrasi; jalankan migrasi mode tulis dua kali; ingest lagi | 200; setelah migrasi dokumen tanpa `device_token`, ber-`token_rotation_required: true`; ingest tetap 200 (mesin terpasang tidak putus) |
| U4 | B | Perangkat U1 | `POST …/rotate-token`; ingest dengan token lama; ingest dengan token baru | 200 dengan token baru; 401; 200 |
| U5 | B | Peran **Tanpa Acuan** berizin `hr.view` saja | `GET /api/hr/devices`; `POST …/rotate-token` | 200 tanpa token; 403 |
| U6 | B | Akun `hr.manage_attendance` yang hanya bertugas di `ent_ksc`; perangkat milik `ent_kanda` | `POST …/{perangkat ent_kanda}/rotate-token` | 403/404 seperti `PATCH` hari ini; hash perangkat tidak berubah |
| U7 | B | — | `PUT /api/scheduler/settings` `{"wa": {"provider": "fonnte", "fonnte_token": "tok-rahasia", "enabled": true}}`; baca dokumen `alerts` langsung; `GET /api/scheduler/settings` | Nilai tersimpan berawalan `enc:v1:` dan tidak memuat "tok-rahasia"; GET hanya `has_fonnte_token: true`; `wa_connection.for_consumer("alerts")` mengembalikan "tok-rahasia" |
| U8 | B | `KN_SECRETS_KEY` dikosongkan | Ulangi simpan U7; `GET /api/admin/integrations` | Tersimpan polos (perilaku hari ini); `secrets_key_configured: false` |
| U9 | B | Dokumen `alerts.wa.access_token` berisi teks polos (data lama) | Panggil `wa_alert_service.raw_settings()` lalu baca dokumen | Hasil panggilan memuat token asli; dokumen kini berawalan `enc:v1:` |
| U10 | B | Hanya `alerts.wa` terisi (Fonnte); `integration_settings` simulasi | Jalankan migrasi mode tulis; `GET /api/admin/integrations/whatsapp`; `wa_connection.for_consumer("documents")` | `configured: true`, `conflict: null`, `used_by` keduanya benar; pemakai dokumen mendapat penyedia Fonnte yang sama |
| U11 | B | `alerts.wa` Fonnte token A; `integration_settings` Meta token B | Migrasi mode tulis; `GET …/whatsapp`; kirim lewat masing-masing pemakai (penyedia ditiru) | `conflict` terisi; tiap pemakai tetap memakai konfigurasi lamanya (tidak ada yang berubah). Lalu `POST …/whatsapp/adopt` `{from: "alerts", reason: "Satu nomor"}` → 200; kedua pemakai memakai token A |
| U12 | B | Koneksi tunggal ada | `PUT /api/scheduler/settings` `{"wa": {"access_token": "x"}}`; `PUT /api/scheduler/settings` `{"wa": {"pic_number": "081234567890"}}` | 400 "Koneksi WhatsApp diatur di Pengaturan › Integrasi & Sistem."; 200 |
| U13 | B | Peran **Tanpa Acuan** berizin `integration.manage`; peran kustom berizin `hr.manage_settings` saja (dibuat sesudah migrasi); peran **Manajer Kosong** | Ketiganya `GET /api/admin/integrations` | 200; 403; 403 |
| U14 | B | Peran kustom berizin `hr.manage_settings` dibuat **sebelum** migrasi | Jalankan migrasi; `GET /api/admin/integrations` sebagai peran itu | 200; laporan migrasi menyebut peran itu |
| U15 | B | — | `PUT /api/config/values` `integrations.anthropic.enabled = true`; baca `system_settings{scope: "integrations"}`; `hr_ai_service.is_enabled()` dengan kunci penyedia terisi | Dokumen memuat `anthropic.enabled: true`; fungsi mengembalikan benar. `PUT /api/admin/integrations` `{anthropic_enabled: false}` → 400 |
| U16 | layar (uji jalan) | Login admin | Buat mesin absen; tutup pop-up; muat ulang | Token tampil sekali di pop-up; sesudah muat ulang hanya "Token berakhiran …"; tombol Ganti token tersedia |

## Langkah kerja

1. `backend/tests_mem/test_KPT8_rahasia_perangkat.py`: U1–U15 (merah).
2. `secret_box.py`; `integrations_service` memakainya (U8, U9 untuk kunci penyedia tetap hijau).
3. Mesin absen: hash, sekali tampil, ganti token, pembaca ganda (U1–U6).
4. Token WhatsApp dibungkus di dua tempat (U7–U9).
5. `wa_connection.py`, endpoint koneksi, `adopt`, penolakan field koneksi di dua endpoint lama (U10–U12).
6. Izin `integration.manage` di empat tempat (U13); dua kunci registry (U15).
7. Skrip migrasi dan ujinya (U3, U10, U11, U14). Layar. Gate; `scripts/audit_config_wiring.py` tidak bertambah merah.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`hr_devices`, objek `whatsapp`); `CODEBASE_MAP.md` (`secret_box.py`, `wa_connection.py`);
`memory/PRD.md`; `docs/LOCAL_DEV.md` (keterangan `KN_SECRETS_KEY`).

## Di luar lingkup

- Memasang `KN_SECRETS_KEY` di server produksi → pemilik (H2/H8); unit ini hanya menampilkan statusnya.
- Kunci perangkat RFID dan alur gerbang → tidak disentuh (H7); hanya fungsi hash-nya dirujuk.
- Penerima dan PIC WhatsApp per PT → KP-T7. Layar cadangan data → tidak ada unitnya.
- Menyatukan tiga layar "baca surat jalan otomatis" (Lampiran B #19) → KF-T2/KP-T9. Memecah modul akses → PR-T5.

## Asumsi dan risiko

- `ASUMSI:` daftar perangkat tetap boleh dibaca pemegang `hr.view`, karena token tidak lagi ikut terkirim.
- `ASUMSI:` token lama tidak dipaksa kedaluwarsa; cukup ditandai "disarankan ganti". Memaksa ganti akan memutus mesin
  terpasang, dan tidak ada keputusan pemilik untuk itu.
- `ASUMSI:` nama aksi izin `manage` dipakai mengikuti pasangan sejenis yang sudah ada (`settings.manage`,
  `pdf_template.manage`), walau kosakata baku `02` §3.2 menyebut `configure`; PR-T5 yang merapikan kosakata.
- `ASUMSI:` menambah `"integrations"` ke `LEGACY_SCOPED_PREFIXES` tidak mengenai kunci lain (tidak ada kunci registry
  ber-awalan itu hari ini).
- `RISIKO:` mesin absen putus bila hash tidak cocok dengan token terpasang. Dicegah pembaca ganda dan U3.
  Membatalkan: pembaca bentuk lama tetap ada; token baru bisa diterbitkan ulang lewat Ganti token.
- `RISIKO:` kunci enkripsi hilang → rahasia terbungkus tidak terbaca. Layar menampilkan galatnya dan rahasia bisa
  diisi ulang; cadangan `KN_SECRETS_KEY` tanggung jawab pemilik.

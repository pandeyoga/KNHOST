# KP-T8 — Rahasia dan perangkat: token mesin absen aman, satu cara menyimpan rahasia, satu koneksi WhatsApp

- Commit awal: `eef7bb9` (dikerjakan) · digabung di atas `1ebbdaa` (KP-T6)        - Commit: `a742da9` · koreksi blueprint `4aa20c3`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KP-14, KP-15, KP-16, KP-31, KP-32 (spesifikasi `docs/blueprint/unit/KP-T8.md`; keputusan K-47, `00` §4.1;
  titik henti H3, H7, H8)
- Risiko: sedang (satu serah-terima).

## Cek ulang "Keadaan sekarang"

Spesifikasi dibaca pada `3132cc4`; dicek ulang pada `eef7bb9`. Semua butir masih berlaku; beberapa baris bergeser.

| # | Hasil di `eef7bb9` |
|---|---|
| 1 | Berlaku. `routers/hr_attendance.py:189` (`list_devices` mengembalikan dokumen utuh termasuk `device_token`) — terbukti merah U1/U5 |
| 2 | Berlaku. `hr_attendance.py:205` (`new_id("devtok")`); `core_utils.py:172` (`new_id`, bergeser dari 128) — 12 heksadesimal |
| 3 | Berlaku. `hr_attendance.py:504` (`ingest_attendance` mencocokkan `device_token` polos) |
| 4 | Berlaku. `AttendanceSetupView.jsx:116` (`copyToken`) + tombol "Salin token perangkat" pada tiap baris — terbukti merah jest |
| 5 | Berlaku, bergeser: `integrations_service.py:38` (`_fernet`), `:48` (`_enc`, dari 47), `:64` (`get_integrations`, dari 62) |
| 6 | Berlaku. `rfid_ingest_service.py:22` (`hash_device_key`), `:26` (`ensure_api_key`) — **tidak disentuh** (H7) |
| 7 | Berlaku, bergeser: `routers/scheduler.py:113` (`cur = dict(st["wa"])`, dari 131) menyimpan token polos; `wa_alert_service.py:84` (`mask_wa`) — terbukti merah U7 |
| 8 | Berlaku, bergeser: `delivery_service.py:49–50` (simpan `access_token` polos), `:86`; `routers/deliveries.py:65` (`put_wa_settings`, dari 64) |
| 9 | Berlaku. `DocumentCenter.jsx:276`; `WhatsAppSettings.jsx:26` |
| 10 | Berlaku, bergeser: `hr_ai_service.py:40` (`is_enabled` membaca `anthropic.enabled`); `ai_narrative.py:70`; `config_catalog_ai.py:51` (`ai.enabled`, dari 40) |
| 11 | Berlaku, bergeser: `routers/integrations.py:18`/`:25` (dari 20/27) dan dua endpoint uji kunci — keempatnya `hr.manage_settings`; `routers/hr.py:500` |
| 12 | Berlaku, bergeser: `config_registry.py:62` (`LEGACY_SCOPED_PREFIXES`, dari 54); belum ada kunci ber-awalan `integrations` (dibuktikan: 0 kunci) |
| Tambahan | PR-T5 sudah memecah modul akses `admin` ("Pengaturan, Pengguna & Hak Akses") menjadi lima modul; sumber daya `integration` masuk modul **Pusat Pengaturan** (`settings`, yang memuat id menu `admin` dan `settings-system`) — lihat Menyimpang 1 |

## KP-14 — token mesin absen

- Berlaku di HEAD: ya (butir 1–4; merah U1, U3, U5, jest).
- Akar masalah: token dibuat pendek, disimpan polos, dan ikut terkirim di daftar perangkat ke semua pemegang `hr.view`;
  layar menyediakan tombol salin di tiap baris. Endpoint ingest tanpa sesi mempercayai token itu.
- Perubahan perilaku (sebelum → sesudah):
  - `POST /api/hr/devices`: token `at_` + 32 heks acak; tersimpan hanya `device_token_hash` (SHA-256), `device_token_hint`
    (4 karakter terakhir), `device_token_at`, `token_rotation_required: false`. Jawaban memuat `device_token` **sekali**
    + `shown_once: true`.
  - `POST /api/hr/devices/{id}/rotate-token` (baru, `hr.manage_attendance`, cakupan PT = `assert_entity_access` seperti
    PATCH): token baru, hash ditimpa, `device_token` polos dibuang, `token_rotation_required: false`; jawaban
    `{device_id, device_token, device_token_hint, shown_once}`; token lama langsung 401; jejak `hr_device_token_rotated`
    (hanya nama, tanpa token).
  - `GET/PATCH/DELETE /api/hr/devices…`: tidak pernah mengirim `device_token` maupun `device_token_hash`; menambah
    `device_token_hint`, `device_token_at`, `token_rotation_required` (baris bentuk lama yang belum dimigrasi ditandai
    `token_rotation_required: true` dan hint dari token lama).
  - `POST /api/hr/attendance/ingest`: cari perangkat aktif ber-`device_token_hash` = hash kiriman; bila tidak ada, bentuk
    lama `device_token` = kiriman; selain itu 401 "device_token tidak valid" (sama seperti sebelumnya).
  - Indeks unik parsial `hr_devices.uq_device_token_hash` (`partialFilterExpression {"device_token_hash": {"$type":
    "string"}}`) di blok indeks unik tidak fatal `indexes.ensure_performance_indexes` (gagal = log, bukan henti mulai).
  - Seed perangkat contoh (`bootstrap.seed_hr_attendance_foundation`, hanya bila PT utama belum punya perangkat): kini
    menyimpan hash token acak yang tidak pernah tampil (pasang mesin lewat Ganti token).
  - Layar Pengaturan › Integrasi & Sistem › Perangkat (tab Mesin absen): tombol "Salin token perangkat" dibuang; baris
    "Token berakhiran …{hint}" + tombol **Ganti token** (`can(perms, "hr", "manage_attendance")`); konfirmasi "Ganti token
    {nama}? Mesin yang masih memakai token lama berhenti mengirim absen sampai diisi token baru."; pop-up **Token
    perangkat** (token, tombol **Salin**, "Token hanya ditampilkan sekali. Simpan sekarang.") sesudah buat/ganti; tanda
    "Disarankan ganti — token lama pernah tampil di layar."
- Berkas: `backend/routers/hr_attendance.py`, `backend/indexes.py`, `backend/bootstrap.py`,
  `frontend/src/features/hr/AttendanceSetupView.jsx`.
- Fixture vs proses: U1, U2, U4–U6 lewat API; U3 perangkat lama disisipkan langsung (fixture), migrasi lewat fungsi skrip.
- Status: implemented_pending_review

## KP-15 — satu cara menyimpan rahasia

- Berlaku di HEAD: ya (butir 5–8; merah U7, U9, secret_box).
- Akar masalah: tiga standar — kunci AI dibungkus Fernet di `integrations_service`, kunci RFID di-hash, token WhatsApp
  polos di dua koleksi.
- Perubahan perilaku: berkas baru `backend/services/secret_box.py` (`available`, `seal`, `open`, `hash_token`,
  `is_sealed`, `SecretBoxError`; awalan `enc:v1:` dan `KN_SECRETS_KEY` tidak berubah → nilai lama tetap terbaca).
  `open` tanpa kunci → "KN_SECRETS_KEY belum diisi — rahasia terenkripsi tidak bisa dibaca."; kunci berbeda → galat
  manusiawi (isi ulang). `integrations_service` memakai `secret_box` (pembungkus lama dihapus). Token WhatsApp dibungkus
  saat simpan di `PUT /api/scheduler/settings`, `delivery_service.save_settings`, koneksi tunggal; token polos lama
  dibungkus saat pertama dibaca (`wa_alert_service.raw_settings`, `delivery_service.raw_row`, lewat
  `wa_connection.bungkus_malas`) bila kunci terpasang. Token yang tidak bisa dibuka dibiarkan terbungkus (penjadwal tetap
  jalan, simpan berikutnya tidak menghapusnya) dan kirim nyata gagal dengan galat itu, tanpa memanggil penyedia.
  `GET /api/admin/integrations` menambah `secrets_key_configured` dan `secret_errors`; layar Integrasi tidak lagi 500 bila
  kunci hilang (mode `strict=False`). Kunci RFID: hanya **aturan hash-nya dirujuk** — `secret_box.hash_token` = SHA-256
  yang sama; uji membandingkan dengan `rfid_ingest_service.hash_device_key` (diimpor, berkas tidak diubah — H7).
- Berkas: `backend/services/secret_box.py` (baru), `integrations_service.py`, `wa_alert_service.py`,
  `delivery_service.py`, `routers/scheduler.py`, `docs/LOCAL_DEV.md`.
- Status: implemented_pending_review

## KP-16 — satu koneksi WhatsApp

- Berlaku di HEAD: ya (butir 7–9; merah U10–U12).
- Perubahan perilaku: berkas baru `backend/services/wa_connection.py`. Koneksi tunggal di
  `system_settings{scope:"integrations"}.whatsapp` (`provider, access_token, fonnte_token, phone_number_id, sender,
  sender_label, default_country_code, template_name, template_lang, source, updated_at, updated_by`; token selalu lewat
  `seal`). `for_consumer("alerts"|"documents")` → koneksi tunggal (token terbuka, `managed: true`) atau konfigurasi lama
  pemakai itu (perilaku hari ini). `wa_alert_service._dispatch` (dipakai alert, ringkasan harian, kirim ulang, kirim uji)
  dan `delivery_service.send_whatsapp` mengambil penyedia & kredensial dari sana; pengaturan pemakaian tetap di tempatnya.
  Endpoint baru (izin `integration.manage`): `GET /api/admin/integrations/whatsapp` (tanpa token; `has_*`, `configured`,
  `used_by`, `conflict`, `secrets_key_configured`, `candidate_from`), `PUT …/whatsapp` (token kosong = tidak diubah;
  `clear_tokens`; validasi penyedia sama dengan hari ini), `POST …/whatsapp/adopt` (`{from, reason}`, alasan wajib; 409
  "Koneksi WhatsApp sudah satu." bila koneksi tunggal sudah ada), `POST …/whatsapp/test` (jalur `send_test`). Setelah
  koneksi tunggal ada: `PUT /api/scheduler/settings` dan `PUT /api/deliveries/whatsapp/settings` menolak field koneksi
  dengan 400 "Koneksi WhatsApp diatur di Pengaturan › Integrasi & Sistem."; field pemakaian diterima; `GET` keduanya
  menambah `connection_managed` + ringkasan `connection` (tanpa token).
  Layar: kartu **WhatsApp** di Integrasi & Audit (Penyedia, Token hanya-tulis "Sudah terisi", ID nomor pengirim, Nama
  pengirim, Kode negara bawaan, Nama template, **Simpan**, **Kirim uji**, "Dipakai oleh: Pengingat · Kirim dokumen", kotak
  kuning **Ada dua koneksi WhatsApp berbeda** + **Pakai koneksi Pengingat untuk keduanya** / **Pakai koneksi Kirim
  Dokumen untuk keduanya** dengan alasan wajib). Tab WhatsApp Penjadwal dan pop-up WhatsApp Pusat Dokumen: setelah
  koneksi tunggal ada, isian koneksi diganti ringkasan + tautan **Atur koneksi di Integrasi**; simpan hanya isian
  pemakaian.
- Berkas: `backend/services/wa_connection.py` (baru), `wa_alert_service.py`, `delivery_service.py`,
  `routers/integrations.py`, `routers/scheduler.py`, `routers/deliveries.py`;
  `frontend/src/features/admin/WhatsAppConnectionPanel.jsx` (baru), `AdminView.jsx`, `scheduler/SchedulerWa.jsx`,
  `documents/WhatsAppSettings.jsx`.
- Status: implemented_pending_review

## KP-31 — hidup/mati & model pengenal gambar di satu tempat

- Berlaku di HEAD: ya (butir 10, 12; merah U15 "Setting 'integrations.anthropic.enabled' tidak ada di registry").
- Perubahan: `LEGACY_SCOPED_PREFIXES` += `"integrations"`; dua kunci di `config_catalog_ai.py`
  (`integrations.anthropic.enabled` bool bawaan `False`, `integrations.anthropic.model` enum bawaan `DEFAULT_MODEL`,
  pilihan = `ANTHROPIC_MODELS`; kelompok `sistem`/sub-judul `tanya-kn` = alias `asisten-analitik`; `scopes=("global",)`;
  izin `integration.manage`; label/help/impact/example sesuai spesifikasi). Nilai tersimpan di dokumen yang sama dengan
  hari ini (tanpa migrasi). `hr_ai_service.is_enabled`/`autotag_image` membaca lewat `value_of`. `PUT
  /api/admin/integrations` menolak `anthropic_enabled`/`anthropic_model` (400); kartu penyedia tidak lagi punya sakelar &
  pilihan model (tautan ke Pengaturan › Integrasi & Sistem › AI & Tampilan). `test_KFT1` (U04 +2, U14
  `VIEW_RESOURCE_OVERRIDES["settings-cfg-system"]` += `integration`) dan `configKeyIndex.json` (dibangkitkan) disesuaikan.
- Uji putaran `t1_config.py` (lingkungan B, seluruh registry 434 kunci, galat 0): kedua kunci — tulis grup 200, terbaca
  API/resolver/penyimpanan lama, nilai tak sah 400, pulihkan ke bawaan (`bukti/KP-T8/t1_config_dua_kunci.log`). Delapan
  penyimpangan kunci lain (mis. `tax.ppn_rate` ent_kanda, `allocation.allow_intercompany`) sudah ada sebelum unit ini.
- Status: implemented_pending_review

## KP-32 — izin integrasi sendiri

- Berlaku di HEAD: ya (butir 11; merah U13/U14).
- Perubahan (empat tempat, `02` §3.2): `permissions_config.KPT8_DEFAULT_PAIRS` (admin `integration: ["manage"]`; instalasi
  lama menerima sekali lewat `sync_permission_modules`); `access_modules`: `integration` di modul `settings` (Pusat
  Pengaturan), label sumber daya "Integrasi & Kunci Layanan Luar", aksi "Kelola", aksi berisiko "mengisi kunci layanan luar
  dan koneksi WhatsApp"; delapan endpoint `/api/admin/integrations…` memeriksa `integration.manage` sebagai pernyataan
  pertama dengan 403 Z6 "Anda belum punya akses untuk mengatur integrasi. Minta Admin menambahkan akses 'Pusat
  Pengaturan'." (nama modul dari `module_label_of`); layar `can(perms, "integration", "manage")` di `AdminView`.
  `hr.manage_settings` tetap menjaga pengaturan SDM. `test_PRT9_izin_bawaan` (TAMBAHAN_SESUDAH dari `KPT8_DEFAULT_PAIRS`)
  dan fixture akses frontend (`fe03_access_fixture.py`) disesuaikan; `test_fe03_access_catalog.py --noconftest` 6/6.
- Peran yang memegang `hr.manage_settings` (bawaan hanya Admin; kustom apa pun) diberi `integration.manage` oleh skrip
  migrasi langkah 4 (U14).
- Status: implemented_pending_review

## Skrip migrasi `scripts/migrate_kpt8_rahasia.py`

Bawaan = `--dry-run` (lapor); `--apply` menulis; argumen asing/bertentangan → keluar 2 sebelum basis data; isi token tidak
pernah dicetak; aman diulang (jalan kedua 0 perubahan). Langkah 1–4 sesuai spesifikasi; mode lapor membaca dua konfigurasi
WhatsApp **tanpa** pembungkusan malas pembaca server. Diuji hanya di lingkungan B (U3, U10, U11, U14 +
`bukti/KP-T8/skrip_migrasi_contoh_lingkungan_B.log`: lapor → tulis → tulis ulang 0). **Tidak dijalankan ke database
nyata (H3)** — pemilik yang menjalankan; lapis A memanggil mode lapor di data acuan saja.

## Uji penerimaan

| ID | Lapis | Merah di kode lama | Hasil kode baru |
|---|---|---|---|
| U1 | B | ya — token `devtok_…` (bukan `at_`), tidak ada `shown_once`/hash | Lulus |
| U2 | B | berantai (butuh token U1); perilaku ingest lama untuk token polos memang sama | Lulus |
| U3 | B | ya — GET mengirim `device_token`; skrip tidak ada (`FileNotFoundError`) | Lulus (ingest 200 sebelum & sesudah migrasi; tulis dua kali) |
| U4 | B | berantai + endpoint `rotate-token` tidak ada | Lulus |
| U5 | B | ya — baris GET memuat `device_token` | Lulus |
| U6 | B | ya — `KeyError device_token_hash` (tidak ada hash) | Lulus (403 sama dengan PATCH; hash tidak berubah) |
| U7 | B | ya — `wa_connection` tidak ada (impor gagal); simpan lama menyimpan token polos (terlihat di U9: dokumen tetap polos) | Lulus |
| U8 | B | ya — `secrets_key_configured` tidak ada | Lulus |
| U9 | B | ya — dokumen tetap polos | Lulus |
| U10 | B | ya — `wa_connection` tidak ada | Lulus |
| U11 | B | ya — skrip/`wa_connection` tidak ada | Lulus (berbeda tidak digabung, tiap pemakai pakai lamanya; adopt → token A; adopt ulang 409) |
| U12 | B | ya — `access_token` diterima (200) | Lulus (+ endpoint Pusat Dokumen) |
| U13 | B | ya — sumber daya `integration` tidak dikenal (400) | Lulus (200; 403; 403 + kalimat Z6) |
| U14 | B | ya — `hr.manage_settings` saja sudah 200 (gerbang lama) | Lulus (403 sebelum migrasi → 200; laporan menyebut peran) |
| U15 | B | ya — kunci tidak ada di registry (404) | Lulus (+ model, + mati lagi → `is_enabled` salah) |
| tambahan | B | ya — `secret_box` tidak ada | Lulus (`seal`/`open`/`hash_token` = `hash_device_key`) |
| U16 | layar (uji jalan) | — | **Belum diuji jalan** (tanpa peramban). Pengganti: jest `kpt8RahasiaPerangkat.test.js` 7/7 (kode lama 5 merah, 2 lulus — "lihat saja" dan kartu WhatsApp baru adalah penjaga regresi/berkas baru) |
| A | A (ditulis) | — | `backend/tests/test_bp_KPT8_rahasia_perangkat.py`: indeks unik parsial terpasang; token tampil sekali/hash/ganti di backend berjalan; skrip mode lapor tidak menulis; integrasi tanpa token. **Belum dijalankan** |

Bukti: `bukti/KP-T8/uji_merah_kode_lama.log` (16 gagal), `uji_hijau_kode_baru.log` (16 lulus), `jest_merah_kode_lama.log`,
`jest_hijau_kode_baru.log`.

`tests_mem`: **762 → 778 lulus** / 2 dilewati / 2 xfail (+16 uji baru; 4 uji lama disesuaikan: `test_PRT9` U01,
`test_KFT1` U04/U14, `test_KFT4` indeks kunci layar — dibangkitkan ulang). Jest seluruhnya: HEAD 644/644 → 651/651 lulus;
35 suite gagal dimuat identik di keduanya (`@radix-ui/primitive/is-development`, kendala lingkungan).

## Penjaga

| Penjaga | Sebelum | Sesudah |
|---|---|---|
| `hitung_penjaga.sh` (16 penjaga statik) | auth 28 · ui_standard 15 · i18n 109 · create_modal 6 · page_tabs 1 · to_list 6 · entity_label 2 · lainnya 0 | **identik** (`bukti/KP-T8/penjaga_statik_sebelum_sesudah.log`) |
| `verify_role_gate_ui` | PASS 31/0 | PASS 31/0 |
| `audit_config_wiring.py --strict` (salinan berjalur; HEAD vs baru dijalankan berurutan) | 121 kunci, 0 pelanggaran | 121 kunci, 0 pelanggaran |
| `sapuan_izin.py` mode cepat (lingkungan B) | 1.780 rute, 20 pelanggaran | 1.785 rute (+5 rute KP-T8), **20 pelanggaran identik** (tidak satu pun rute KP-T8); rute baru: tanpa sesi 401, Kosong/Sopir/Manajer Kosong 403, Penuh 200 |
| `verify_ui_standard` per berkas yang disentuh | — | huruf < 12 px & hex turun di `AttendanceSetupView` (5→3, 14→12) dan `IntegrationsPanel` (5→4, 10→8); berkas baru 0 |

## Cek layar (`docs/KN_37_STANDAR_UI_GUDANG.md`, butir pemilik 14 Nov)

Belum dipotret (tanpa peramban); dicek dari kode + jest. Kelas `data-table head-wrap` / `col-sticky-end` **tidak ada** di
`eef7bb9` — tidak diperlukan: tidak ada tabel baru (daftar perangkat = baris kartu `flex` dengan area aksi `shrink-0`).

| Butir | Mesin absen (baris + Ganti token) | Pop-up Token perangkat | Kartu penyedia AI | Kartu WhatsApp (baru) | Penjadwal › WhatsApp & Pusat Dokumen › WhatsApp |
|---|---|---|---|---|---|
| 1 tabel melebihi kartu | tidak ada tabel; "Ganti token" `secondary-button btn-sm` + 2 ikon di area aksi | — | — | — | — |
| 2 bantalan kartu | `section-card` + `section-head` lama | `FormModal` baku | `section-head`/`section-body` | `section-head`/`section-body` | isi kartu lama |
| 3 kepala kartu padat | kepala tetap judul + Tambah | judul + nama perangkat | judul saja | ikon + judul saja; status & konflik di badan | tidak berubah |
| 4 tombol mati tanpa alasan | tidak ada | tidak ada | Simpan Kunci aktif; kosong → galat tertulis | Kirim uji mati → "Isi nomor tujuan untuk kirim uji." di sampingnya; hanya-baca → kalimat "Hanya-baca: mengubah koneksi butuh akses mengatur integrasi." | tidak ada tombol mati baru |
| 5 status ikon + teks + warna | "Disarankan ganti" = `status-pill pill-warning` + ikon; hint token ikon kunci | peringatan sekali tampil: ikon + teks + `bg-kn-warning-soft` | peringatan kunci enkripsi: ikon + teks + warna | "Dipakai oleh" ikon + teks + warna; "Sudah terisi" ikon; konflik ikon + kuning | ringkasan teks + tautan (bukan status) |
| 6 daftar panjang tanpa cari | daftar perangkat (lama, biasanya < 10) — tidak diubah | — | — | — | — |
| 7 teks vs izin | tombol dari `can(hr.manage_attendance)`; tanpa kalimat "bukan wewenang" | — | tombol dari prop `canManage` (`can(integration.manage)`) | sama | tautan baca-saja bila menu tak bisa dibuka (`LinkCard`) |
| 8 kosong ganda / angka 0 | satu keadaan kosong lama | — | — | satu kalimat "Belum dipakai …" | — |

Teks baru ≥ 12 px (`text-fs-12/13`), warna lewat token `kn-*`, tombol kelas baku; pil panjang dihindari (pil `nowrap`) —
kalimat penjelas di luar pil supaya tidak terpotong di 390 px.

## Menyimpang dari blueprint

1. **Modul akses**: spesifikasi menyebut modul "Pengaturan, Pengguna & Hak Akses" (`admin`). Sejak PR-T5 modul itu
   dipecah lima; `integration` dimasukkan ke modul **Pusat Pengaturan** (`settings`) — pemilik id menu `admin` dan
   `settings-system` yang disebut spesifikasi. Kalimat 403 karenanya "… akses 'Pusat Pengaturan'." (diambil dari
   `module_label_of`, ikut bila modul berpindah). Id lama `admin` tetap alias kelima modul.
2. **Pesan kunci registry**: "Hidup/mati dan model diatur di Pusat Pengaturan › Asisten." → "Hidup/mati dan model diatur
   di Pengaturan › Integrasi & Sistem › AI & Tampilan." — tab "Asisten" tidak ada (KF-T4 menamai ulang); tautan layar
   menuju `settings-cfg-system`.
3. **`group`** `asisten-analitik` ditulis sebagai id barunya (`sistem`, sub-judul `tanya-kn`; alias yang sama di
   `GROUP_ALIASES`). Sub-judul itu kini 14 kunci (batas 14).
4. **Indeks unik** dipasang di blok indeks unik tidak fatal (bukan `REQUIRED_UNIQUE_INDEXES`): spesifikasi tidak
   menyebut D7 untuk unit ini dan field baru tidak mungkin kembar; di database tiruan indeks parsial dilewati (uji lapis A).
5. **`adopt`**: 409 hanya bila koneksi tunggal sudah ada; bila belum ada dan konfigurasi sumber kosong → 400 "…masih kosong".
   `PUT …/whatsapp` saat konflik tidak ditolak (pemilik mengisi koneksi baru secara sadar = keputusan); dasar `PUT` tanpa
   koneksi tunggal = konfigurasi lama yang akan dipakai (satu terisi / dua sama) supaya token tidak hilang.
6. **Tambahan**: `GET /api/admin/integrations` juga mengirim `secret_errors`; `GET …/whatsapp` mengirim `candidate_from`,
   `secret_error`, `providers`; `GET` Penjadwal/Pusat Dokumen mengirim `connection_managed` + `connection`. Token yang tidak
   bisa dibuka tidak menjatuhkan penjadwal maupun layar (lihat KP-15).
7. Seed perangkat contoh kini ber-hash (token tak pernah tampil) — tidak disebut spesifikasi; menghindari lahirnya token
   polos baru di instalasi kosong.

## Usulan koreksi blueprint (teks pengganti persis)

- `unit/KP-T8.md` § Izin dan peran, kolom "Modul akses": ganti
  `"Pengaturan, Pengguna & Hak Akses" (`admin`) — `resources` ditambah `integration`` dengan
  `"Pusat Pengaturan" (`settings`; sejak PR-T5 pecahan modul `admin`) — `resources` ditambah `integration``.
- `unit/KP-T8.md` § Server, pesan 403: ganti `Minta Admin menambahkan akses 'Pengaturan, Pengguna & Hak Akses'.` dengan
  `Minta Admin menambahkan akses 'Pusat Pengaturan'.`
- `unit/KP-T8.md` § Pengaturan dan § Layar: ganti `"Hidup/mati dan model diatur di Pusat Pengaturan › Asisten."` dengan
  `"Hidup/mati dan model diatur di Pengaturan › Integrasi & Sistem › AI & Tampilan."`

## Asumsi

- Sesuai spesifikasi: daftar perangkat tetap boleh dibaca `hr.view`; token lama tidak dipaksa kedaluwarsa (hanya
  "Disarankan ganti"); nama aksi `manage`; awalan `integrations` tidak mengenai kunci lain (0 kunci sebelumnya).
- "Konfigurasi terisi" (migrasi langkah 3) = penyedia bukan simulasi **atau** ada token tersimpan; "sama" = penyedia, ID
  nomor pengirim, dan token penyedia itu sama (dibandingkan setelah dibuka). Penggabungan "sama": isian Pengingat dipakai,
  yang kosong dilengkapi dari Kirim Dokumen.
- Mode simulasi Pusat Dokumen (`simulate`) tetap pengaturan pemakaian: koneksi tunggal Fonnte/Meta + `simulate: true` →
  dokumen tetap disimulasikan.

## Titik henti

- **H3**: skrip migrasi tidak dijalankan ke database nyata (termasuk mode lapor). Catatan untuk pemilik: sampai langkah 4
  dijalankan, peran **kustom** yang hanya memegang `hr.manage_settings` (tanpa modul Pusat Pengaturan "Semua aksi") tidak
  bisa membuka layar Integrasi (403); Admin tidak terdampak (izin bawaan via `sync_permission_modules`). Disarankan skrip
  dijalankan bersama pemasangan.
- **H7**: `rfid_ingest_service`, `rfid_service`, `gate_evaluator`, `middleware/` tidak diubah; kunci perangkat RFID tetap
  memakai `hash_device_key` sendiri (aturan hash sama, dibuktikan uji).
- **H8**: tidak ada rahasia yang diminta/dibuat; uji memakai `Fernet.generate_key()` di dalam tes dan token palsu. Memasang
  `KN_SECRETS_KEY` di produksi = pemilik (layar hanya menampilkan statusnya).

## Hambatan lingkungan

- Tanpa peramban: U16 dan potret 1280/1024/390 px belum. Lapis A dan gate belum dijalankan (lingkungan A milik integrator).
- Jest lokal: 35 suite lama gagal dimuat (`@radix-ui`), identik di HEAD; suite baru meniru `KNSelect`, `KNTimePicker`,
  `ui/switch`.
- `audit_config_wiring.py` berjalan lewat salinan berjalur; hitungan kunci "lingkup lain" ikut isi database lokal yang
  sedang berjalan (sekali terbaca 71, diulang berurutan HEAD/baru = 121/121) — perbandingan dibuat dari dua jalan berurutan.

## Penggabungan

Dikerjakan di `eef7bb9`; digabung di atas `1ebbdaa`: `indexes.py` digabung tiga arah; fixture akses dan peta kode
dibangkitkan ulang. Penjaga KF-T8 di HEAD ikut menilai dua kunci baru `integrations.anthropic.*` (putaran lulus;
`verify_config_fallback` 0 tersisa). tests_mem 1253. Usulan koreksi blueprint diterapkan di `4aa20c3`.

Lapis A (lingkungan A): `tests/test_bp_KPT8_rahasia_perangkat.py` — 4 uji **lulus** (indeks parsial, token tampil
sekali, skrip mode lapor tidak menulis, integrasi tanpa token).

## Cek layar (potret integrator)

Dipotret di lingkungan A (`admin@`, 1280 px): Pengaturan › Integrasi & Sistem › Perangkat (baris mesin absen: "Token
berakhiran …2ac4", lencana "Disarankan ganti" berikon, tombol "Ganti token") dan Integrasi & Audit (kartu Anthropic
dengan peringatan kunci enkripsi berikon, tautan ke AI & Tampilan; kartu WhatsApp baru dengan "Kirim uji" mati beralasan
tertulis "Isi nomor tujuan untuk kirim uji."). Tidak ada temuan baru. Di lingkungan A kunci enkripsi server memang
belum dipasang, jadi peringatan "Rahasia yang disimpan sekarang belum terenkripsi" tampil (benar). Bukti:
`bukti/KP-T8/layar_perangkat_mesin_absen_1280.png`, `layar_integrasi_whatsapp_1280.png`.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli), tiap jalan sesudah `restore_demo` (data acuan; tiga skrip seed yang sama
seperti garis dasar gagal).

| Jalan | Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|---|
| 1 (`c9cf10f` — KF-T8, KP-T6, KP-T8, PK-30) | `--quick` | 16 FAIL | 16 | 3 (ganti nama + 2 balapan, lihat bawah) | 2 |
| 1 (`c9cf10f`) | `--ci` | 42 FAIL | 43 | 2 (ganti nama + 1 balapan) | 2 |
| 2 (`27f0853` — + perbaikan penjaga `c2cc412`, PK-42 `5e747b2`, PM-T1 `fd606e5`, cek visual) | `--quick` | 14 FAIL | 16 | 1 (ganti nama) | 2 (`config_wiring` + uji-diri) |
| 2 (`27f0853`) | `--ci` | 41 FAIL | 43 | 1 (ganti nama) | 2 |

- **`guard:page_tabs`** hanya berganti nama sejak MN-T1 (INV-UI-12 → INV-UI-12/13/14); merahnya sama dengan garis dasar
  (INV-UI-12 `wms/InventoryStockView.jsx`, berkas lama).
- Jalan 1: **`guard:role_gate_ui`** dan **`guard:role_label`** merah palsu karena balapan di kolam statik paralel —
  uji-diri `role_gate_ui` menulis probe sementara `features/__poc_role_gate_probe.jsx` ke `src` yang dipindai penjaga lain.
  Bukan dari unit mana pun; diperbaiki di `c2cc412` (uji-diri menghitung probe di memori; pemindaian melewati probe
  penjaga lain). Jalan 2 keduanya hijau.
- Penjaga statik per hitungan (`hitung_penjaga.sh`) tidak naik; PK-42 menurunkan `verify_ui_standard` 15 → 13 dan
  `audit_i18n_id` 109 → 104.


## Yang perlu direview

- Menyimpang 1 (modul akses pasca PR-T5) dan 5 (aturan `adopt`/`PUT` saat konflik).
- Langkah 4 skrip sebagai satu-satunya jalur K-47 untuk peran kustom pemegang `hr.manage_settings` (lihat H3).
- Dua pembaca `system_settings{scope:"integrations"}`: `get_integrations` mengabaikan objek `whatsapp`;
  `update_integrations` menulis ulang objek `anthropic` utuh (termasuk `enabled/model` dari dokumen yang sama dengan
  proyeksi registry) — konsisten selama kunci registry hanya berlapis global.
- `wa_alert_service.raw_settings` dibaca sering (penjadwal); pembungkusan malas menulis sekali, membuka token tiap baca.

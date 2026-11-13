# CR-T1 — Profil kredit per pelanggan per PT, diubah hanya lewat pengajuan

| | |
|---|---|
| Gelombang | Modul piutang dan kredit |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | PK-45, KF-T6 |
| Menutup temuan | CR-03 |
| Keputusan | K-27, K-28, K-29 |
| Standar | §2 (2.1–2.4), §3.1 (Z1, Z2, Z4, Z6), §3.2, §3.4 (N1, N2), §4 (L1, L4, L6), §5 (D1, D3, D7, D8, D9), §6 |
| Lingkungan uji | keduanya (B untuk izin dan alur; A untuk indeks unik) |

## Tujuan

Plafon, hari blokir, termin yang diizinkan, dan status blokir seorang pelanggan disimpan terpisah dari data pelanggan,
satu set per PT, dan hanya berubah lewat dokumen pengajuan yang diputus pemegang izin kredit. Ambang telat (14 hari) dan
ambang peringatan (80 %) tidak lagi ditulis di kode: keduanya pengaturan per PT yang bisa ditimpa per pelanggan.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| Fakta | Jangkar |
|---|---|
| Ambang peringatan 0,8 dan ambang blokir 14 hari ditulis mati | `backend/services/customer_service.py:14` (`WARNING_RATIO`), `backend/services/customer_service.py:15` (`OVERDUE_BLOCK_DAYS`) |
| Salinan kedua kedua angka itu, dipakai laporan umur piutang | `backend/services/ar_aging_service.py:34` (`WARNING_RATIO`), `backend/services/ar_aging_service.py:89` (`_credit_status`) |
| Plafon dibaca dari `customers.credit_limit`; 0 berarti tanpa batas | `backend/services/customer_service.py:212` (`credit_limit`), `backend/services/customer_service.py:249` (`near_limit`) |
| Status `blocked` pada data pelanggan memaksa status kredit terblokir | `backend/services/customer_service.py:256` (`blocked`) |
| `PATCH /api/customers/{id}` menerima `status` dan `credit_limit` dengan izin `customer.update` (PK-45 mengeluarkan keduanya ke endpoint sementara) | `backend/routers/customers.py:177` (`allowed`) |
| `POST /api/customers` menyimpan `credit_limit` dari isi permintaan — pintu yang tidak ditutup PK-45 | `backend/routers/customers.py:136` (`credit_limit`), `backend/schemas.py:107` (`credit_limit`) |
| Sales memegang `customer.update`; Finance hanya `customer.view` | `backend/permissions_config.py:116` (`customer`), `backend/permissions_config.py:358` (`customer`) |
| Gerbang kredit memanggil hitungan kredit **tanpa** PT, jadi piutang pelanggan dijumlah lintas PT dan diadu dengan satu plafon | `backend/services/customer_service.py:291` (`compute_customer_credit`) |
| Pesanan boleh ber-PT lain dari PT pelanggan (`payload.entity_id` menang) | `backend/routers/sales_orders.py:198` (`entity_id`) |
| Pusat Pengaturan sudah punya `ar.denda_rate_pct_per_month`, `ar.grace_days`, `ar.aging_buckets`; belum ada kunci ambang kredit | `backend/config_catalog_core.py:138` (`ar.denda_rate_pct_per_month`) |
| Kartu pelanggan menampilkan plafon dari `credit.credit_limit`; tab riwayatnya enam | `frontend/src/features/crm/Customer360Panel.jsx:56` (`credit_limit`), `frontend/src/features/crm/Customer360Panel.jsx:18` (`HIST_TABS`) |
| Tab "Persetujuan Kredit" di CRM hanya untuk admin/manajer lewat nama peran | `frontend/src/features/crm/CrmView.jsx:27` (`approvals`) |

## Perubahan

### Data

Koleksi baru `customer_credit_profiles` (awalan id `ccp_`). Satu dokumen per (pelanggan, PT); tidak ada dokumen = semua
nilai ikut bawaan PT.

| Field | Tipe | Wajib | Arti |
|---|---|---|---|
| `customer_id`, `entity_id` | string | ya | Kunci. `entity_id` = PT **pesanan**, bukan PT pemilik data pelanggan |
| `limit_mode` | `ikut_pt` · `khusus` · `tanpa_batas` | ya | Bawaan `ikut_pt`. "Tanpa batas" adalah pilihan tersendiri, bukan angka 0 |
| `credit_limit` | angka ≥ 0 | bila `khusus` | Plafon dalam rupiah |
| `limit_valid_until` | `YYYY-MM-DD` atau `""` | tidak | Lewat tanggal ini plafon efektif kembali ke bawaan PT |
| `allowed_term_codes` | daftar kode termin | tidak | Kosong = semua termin aktif PT boleh (perilaku hari ini). Ditegakkan di CR-T3 |
| `default_term_code` | string | tidak | Harus anggota `allowed_term_codes` bila daftar itu terisi |
| `overdue_block_days` | bilangan bulat ≥ 0 atau `null` | tidak | `null` = ikut `ar.overdue_block_days` PT |
| `credit_status` | `normal` · `blokir_manual` | ya | Status "awas" dan "tahan" dihitung, tidak disimpan |
| `block_reason` | string | bila `blokir_manual` | Minimal 5 huruf |
| `penalty_rule` | objek | tidak | `{mode: ikut_pt·khusus·bebas, rate_pct_per_month, base, cap_pct, grace_days, reason, valid_until}`. Disimpan di sini; baru dibaca mesin denda di CR-T4 |
| `credit_group_id` | string | tidak | Kelompok kredit lintas PT (K-29, opsional). Disimpan; belum dihitung mesin |
| `version` | bilangan bulat | ya | Naik 1 tiap perubahan; dipakai sebagai syarat tulis |
| `updated_at`, `updated_by`, `last_request_id` | string | ya | Jejak. Indeks: `(customer_id, entity_id)` unik, terdaftar wajib-ada (D7) |

Koleksi baru `credit_profile_requests` (awalan id `cpr_`, nomor `PKR-` per PT lewat `next_doc_number`):

| Field | Arti |
|---|---|
| `customer_id`, `customer_name`, `entity_id`, `number` | Sasaran |
| `changes` | Daftar `{field, from, to}`; `from` = nilai tersimpan saat diajukan |
| `reason` (wajib, ≥ 5 huruf), `attachment_url` | Dasar pengajuan |
| `credit_snapshot` | Potret hitungan kredit saat diajukan (D3); tidak dihitung ulang |
| `status` | `diajukan` → `disetujui` · `ditolak` · `dibatalkan` |
| `requested_by`, `requested_by_id`, `created_at` | Pengaju |
| `decided_by`, `decided_by_id`, `decided_at`, `decision_note` | Pemutus |
| Indeks | `(customer_id, entity_id)` unik parsial `status == "diajukan"` (satu pengajuan terbuka per pelanggan per PT); `(entity_id, status, created_at)` |

Migrasi (skrip baru `scripts/migrate_credit_profiles.py`, idempoten, punya mode `--dry-run`; dijalankan pada data nyata
oleh pemilik — H3): untuk tiap pelanggan, PT = `customers.entity_id`:

| Data lama | Profil yang dibuat |
|---|---|
| `credit_limit > 0` | `limit_mode: khusus`, `credit_limit` sama. Bila 0/kosong dan tidak `blocked`: tidak dibuat (ikut PT; bawaan PT 0 = tanpa batas, sama dengan hari ini) |
| `status == "blocked"` | `credit_status: blokir_manual`, `block_reason: "Dipindahkan dari status pelanggan"`; `customers.status` menjadi `active` |

`customers.credit_limit` tidak dihapus dan tidak ditulis lagi; laporan membuktikan dengan pencarian bahwa tidak ada pembaca tersisa.

### Server

Berkas baru `backend/services/credit_profile_service.py`:

| Fungsi | Perilaku |
|---|---|
| `async def effective(customer_id: str, entity_id: str, today: Optional[str] = None) -> dict` | Nilai yang dipakai mesin beserta asalnya: `credit_limit` (angka, 0 = tanpa batas), `limit_source` (`khusus` · `bawaan_pt` · `tanpa_batas` · `kedaluwarsa`), `overdue_block_days` + `block_days_source` (`khusus` · `bawaan_pt`), `warning_ratio`, `allowed_term_codes`, `default_term_code`, `credit_status`, `block_reason`, `limit_valid_until` |
| `def status_from(effective: dict, ar_outstanding: float, max_overdue_days: int) -> str` | **Satu-satunya** penentu `active` · `warning` · `blocked`. Aturan sama dengan hari ini: `warning` bila piutang ≥ rasio × plafon atau telat ≥ 1 hari; `blocked` bila piutang ≥ plafon, atau telat > hari blokir, atau `blokir_manual` |
| `async def submit(customer, entity_id, changes, reason, attachment_url, actor) -> dict` | Validasi, tolak bila sudah ada pengajuan `diajukan`, simpan pengajuan + potret |
| `async def decide(request_id, decision, note, actor) -> dict` | Urutan: periksa status `diajukan` → `tolak_bila_pelaku_sama("ubah_profil_kredit", pengajuan, actor, entity_id)` bila `butuh_orang_kedua("ubah_profil_kredit", entity_id, nominal)` → bila setuju: tulis profil dengan syarat `version` lama → tandai pengajuan → jejak audit. `nominal` = `credit_limit` baru (0 bila pengajuan tidak mengubah plafon) |

`compute_customer_credit` dan `_credit_status` berhenti memakai konstanta: keduanya memanggil `effective(...)` (PT =
argumen `entity_id`, atau `customers.entity_id` bila tidak diberikan) lalu `status_from(...)`. Empat konstanta di dua
berkas itu dihapus. Rumus piutang dan jatuh tempo **tidak** diubah di unit ini (CR-T2, CR-T3).

| Endpoint | Izin | Isi permintaan | Jawaban |
|---|---|---|---|
| `GET /api/customers/{id}/credit-profile?entity_id=` | `credit_profile.view` + `can_view_credit` | — | `{profile, effective, pending_request, history}`; `history` = 20 pengajuan terakhir yang sudah diputus |
| `POST /api/customers/{id}/credit-profile-requests` | `credit_profile.update` + `can_access_customer` | `{entity_id?, changes: {<field>: <nilai baru>}, reason, attachment_url?}` | Dokumen pengajuan |
| `GET /api/credit-profile-requests?status=&customer_id=` | `credit_profile.view` | — | Daftar berhalaman; disaring PT aktif; pelanggan di luar cakupan pengguna tidak tampil |
| `POST /api/credit-profile-requests/{id}/decision` | `credit_profile.approve` | `{decision: "approve"\|"reject", note}`; `note` wajib saat menolak | Pengajuan + profil efektif |
| `POST /api/credit-profile-requests/{id}/cancel` | pengaju sendiri, atau `credit_profile.approve` | `{reason}` | Pengajuan `dibatalkan` |

PT pada semua endpoint lewat `resolve_requested_entity` (N1); pengajuan ber-id diadu dengan `guard_doc` (N2). Awalan
`/api/credit-profile-requests` dan sub-jalur `/api/customers/{id}/credit-profile-requests` masuk `IDEMPOTENT_PREFIXES`.

Galat:

| Keadaan | Kode | Pesan |
|---|---|---|
| Pengajuan terbuka sudah ada | 409 | "Masih ada pengajuan perubahan kredit yang menunggu keputusan untuk pelanggan ini." |
| Nilai tidak sah (plafon negatif, kode termin tak dikenal, tanggal lampau, `khusus` tanpa angka) | 400 | "Isian tidak sah: {nama isian} — {sebab}." Alasan < 5 huruf: "Alasan pengajuan wajib diisi (minimal 5 huruf)." |
| Sudah diputus | 409 | "Pengajuan ini sudah diputus." |
| Profil berubah sejak diajukan (`from` tidak cocok) | 409 | "Profil kredit sudah berubah sejak pengajuan dibuat. Buat pengajuan baru." |
| Pengaju memutus sendiri saat wajib dua orang; tanpa izin | 403 | Pesan dari `dual_control` (KF-T6); bentuk Z6 dengan nama modul "Uang Masuk, Piutang & Faktur Pajak" |

Jalur lama (D8):

- `PATCH /api/customers/{id}`: `credit_limit` tetap diabaikan (PK-45); `status` hanya menerima `active` · `inactive`.
- Endpoint sementara plafon/status dari PK-45 (namanya ada di `docs/reviews/2026-11-13/hasil/PK-45.md`): bagian plafon
  dijawab 410 "Plafon diubah lewat pengajuan perubahan kredit."; pemanggil di layar dialihkan.
- `POST /api/customers`: `credit_limit` tidak disimpan (`customers.credit_limit` = 0). Bila nilainya > 0, server membuat
  pengajuan `diajukan` atas nama pembuat dengan alasan "Plafon diusulkan saat pelanggan dibuat".

### Pengaturan

Dua kunci pertama **milik unit KF-T7**. Bila KF-T7 sudah selesai, kuncinya sudah terdaftar (pendaftaran ganda ditolak
`E()`): cukup tambahkan pembaca di bawah ke `consumers`. Bila belum, daftarkan di `backend/config_catalog_core.py`
persis seperti ini dan tulis di laporan bahwa KF-T7 tinggal memakainya.

| Field | `ar.overdue_block_days` | `ar.credit_warning_ratio` | `ar.default_credit_limit` (baru, milik unit ini) |
|---|---|---|---|
| group | `uang-masuk` | `uang-masuk` | `uang-masuk` |
| type | `duration` | `decimal` | `money` |
| default | 14 | 0.8 | 0 |
| min / max / unit | 0 / 365 / hari | 0 / 1 / bagian dari plafon | 0 / 1.000.000.000.000 / Rp |
| scopes | `("global", "entity")` | `("global", "entity")` | `("global", "entity")` |
| label | "Tahan pesanan bila telat lebih dari (hari)" | "Beri peringatan saat piutang mencapai" | "Plafon bawaan pelanggan baru" |
| help | "Pelanggan yang tagihannya telat lebih dari jumlah hari ini dianggap terblokir. Bisa ditimpa per pelanggan di kartu pelanggan." | "Bagian dari plafon yang memunculkan peringatan. 0,8 = 80 % plafon." | "Dipakai untuk pelanggan yang belum punya plafon khusus. 0 = tanpa batas." |
| impact | "Angka lebih kecil membuat lebih banyak pelanggan terblokir saat membuat pesanan." | "Angka lebih kecil memunculkan peringatan lebih awal; tidak memblokir." | "Mengisi angka membuat semua pelanggan tanpa plafon khusus mulai dibatasi." |
| example | "14 · telat 10 hari → peringatan; telat 15 hari → terblokir" | "0,8 · plafon Rp 10.000.000 · piutang Rp 8.500.000 → peringatan" | "Rp 25.000.000 · piutang Rp 26.000.000 → terblokir" |
| risk / requires_reason | `high` / ya | `medium` / tidak | `high` / ya |
| permission | `("credit_profile", "approve")` | `("credit_profile", "approve")` | `("credit_profile", "approve")` |
| consumers | `services/credit_profile_service.py:effective` | `services/credit_profile_service.py:effective` | `services/credit_profile_service.py:effective` |

Aksi `ubah_profil_kredit` (`kontrol.ubah_profil_kredit.min_orang` bawaan 1, `.batas_nominal` bawaan 0) milik KF-T6.

### Izin dan peran

Sumber daya baru `credit_profile`, masuk modul akses `ar` (`backend/access_modules.py:131`, `payment_variance`); id
menu yang dibukanya: `customers-crm`.

| Pasangan | Arti di layar | Peran bawaan |
|---|---|---|
| `credit_profile.view` | Melihat plafon, status kredit, dan riwayatnya | admin, manager, finance, sales_admin, sales |
| `credit_profile.update` | Mengajukan perubahan kredit | admin, manager, finance, sales_admin, sales |
| `credit_profile.approve` | Memutus pengajuan perubahan kredit dan mengubah ambang kredit PT | admin, manager — Sales tidak (K-28). Dengan `min_orang` = 1 pemegangnya boleh mengajukan lalu memutus sendiri |


### Layar

Kartu pelanggan (`Customer360Panel.jsx`), tab baru **Kredit** (kunci `credit`), tampil bila `can(perms, "credit_profile", "view")`:

- Banner PT (L4); pemilih PT bila pengguna punya lebih dari satu PT. Baris hanya-baca bertanda asal **ikut PT** atau
  **khusus** (L6): "Plafon kredit", "Berlaku sampai", "Termin yang diizinkan", "Termin bawaan", "Tahan pesanan bila
  telat lebih dari", "Status kredit", "Alasan blokir". Plafon kedaluwarsa: "Plafon khusus berakhir {tanggal} — sekarang
  memakai bawaan PT".
- Tombol **Ajukan perubahan** (`credit_profile.update`) membuka pop-up baku berisi isian yang sama + "Alasan pengajuan"
  (wajib) + "Lampiran (tautan)". Pemegang `approve` saat `min_orang` = 1 melihat tombol kedua **Ajukan & setujui**.
- Pengajuan terbuka: kartu "Menunggu keputusan" berisi nilai lama → baru, tombol **Setujui**, **Tolak**
  (`credit_profile.approve`), **Batalkan pengajuan** (pengaju). Konfirmasi menyebut nama pelanggan, PT, dan plafon baru.
- "Riwayat perubahan kredit": tanggal, pengaju, pemutus, perubahan, alasan. Memuat: "Memuat profil kredit…"; kosong:
  "Belum ada perubahan kredit."; galat tampil di dalam kartu.

Kotak ringkasan kredit di atas kartu membaca plafon dari `effective.credit_limit`. Form ubah pelanggan kehilangan
isian plafon dan pilihan status "Diblokir". CRM › tab "Persetujuan Kredit"
(`frontend/src/features/crm/CrmView.jsx:51`, `CreditOverridesPanel`): di bawah panel yang ada, komponen baru
`CreditProfileRequestsPanel.jsx` menampilkan pengajuan `diajukan` PT aktif dengan tombol yang sama; syarat tampil tab
berubah dari nama peran menjadi `can(perms, "credit_profile", "approve")`. CR-T5 memindahkan antrean ini.

## Uji penerimaan

Persiapan: pelanggan **P1** (`ent_ksc`) dan **P2** (`ent_kanda`) dibuat admin lewat API; akun seed `adm`, `mgr`, `sls`.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | `sls`: `PATCH /api/customers/{P1}` `{"data": {"credit_limit": 99000000, "status": "blocked"}}` | 200; `credit_limit` dan `status` di database tidak berubah; tidak ada profil maupun pengajuan |
| U2 | B | — | `sls`: `POST …/{P1}/credit-profile-requests` `{"changes": {"limit_mode": "khusus", "credit_limit": 50000000}, "reason": "Naik kelas grosir"}` | 200, `status: "diajukan"`; `GET …/credit-profile` → `effective.limit_source == "bawaan_pt"` |
| U3 | B | setelah U2 | `sls`: `POST /api/credit-profile-requests/{id}/decision` `{"decision": "approve"}` | 403; pengajuan tetap `diajukan` |
| U4 | B | setelah U2 | `mgr`: keputusan `approve` | 200; `effective.credit_limit == 50000000`, `limit_source == "khusus"`; `history` 1 baris `from: null → to: 50000000`; `version == 1` |
| U5 | B | `adm` menyetel `kontrol.ubah_profil_kredit.min_orang` = 2 pada `ent_ksc` | `mgr` mengajukan untuk P1 lalu memutus sendiri; lalu `adm` memutus | Pertama 403; kedua 200 |
| U6 | B | seperti U5 | `mgr` mengajukan untuk **P2** (`ent_kanda`) lalu memutus sendiri | 200 — PT lain tidak ikut berubah |
| U7 | B | fixture: pesanan P1 dan P2 masing-masing bersisa Rp 1.000.000, jatuh tempo 10 hari lalu; `adm` menyetel `ar.overdue_block_days` = 7 pada `ent_ksc` | `GET /api/customers/{P1}/credit-status`, lalu `{P2}` | P1 `blocked` (10 > 7); P2 `warning` (10 ≤ 14, bawaan) |
| U8 | B | setelah U7 | `mgr` mengajukan + menyetujui `overdue_block_days: 30` untuk P1 | P1 `warning` (10 ≤ 30); `block_days_source == "khusus"` |
| U9 | B | P1 plafon khusus Rp 10.000.000; fixture sisa piutang Rp 8.500.000 belum jatuh tempo | Baca status; setel `ar.credit_warning_ratio` = 0.9 pada `ent_ksc`; baca lagi | `warning` (8.500.000 ≥ 0,8 × 10.000.000 = 8.000.000) lalu `active` (8.500.000 < 9.000.000) |
| U10 | B | pengajuan P1 masih `diajukan` | `sls`: pengajuan kedua untuk P1; `mgr`: pengajuan `credit_limit: -1` dan `allowed_term_codes: ["XX99"]` untuk P2 | 409; 400; 400 — tidak ada pengajuan baru tersimpan |
| U11 | B | P1 plafon khusus Rp 10.000.000 dengan `limit_valid_until` = kemarin; `ar.default_credit_limit` = 0 | `GET …/credit-profile` | `effective.credit_limit == 0`, `limit_source == "kedaluwarsa"` |
| U12 | B | peran uji baku | **Tanpa Acuan** + `credit_profile.view`: `GET …/credit-profile`; sama + `POST` pengajuan; **Manajer Kosong** dan **Sopir**: `GET` | 200; 403; 403; 403 |
| U13 | B | — | `sls`: `POST /api/customers` dengan `credit_limit: 25000000` | Pelanggan terbuat dengan `credit_limit == 0`; satu pengajuan `diajukan` berisi `credit_limit → 25000000` |
| U14 | B | fixture: pelanggan lama `credit_limit: 15000000`, `status: "blocked"` | Jalankan fungsi migrasi dua kali | Satu profil: `khusus`, 15.000.000, `blokir_manual`; `customers.status == "active"`; putaran kedua tidak mengubah apa pun |
| U15 | B | — | Putaran `t1_config.py` untuk tiga kunci di bagian Pengaturan | Lulus (tulis global → terbaca; lapisan PT → hanya PT itu; nilai tak sah → 400) |
| U16 | A | — | Dua `POST` pengajuan bersamaan untuk P1 | Tepat satu 200 dan satu 409; satu dokumen `diajukan` |
| U17 | layar (uji jalan) | setelah U4 | `sls` membuka kartu P1 › Kredit; `mgr` membuka CRM › Persetujuan Kredit | Sales melihat plafon Rp 50.000.000 bertanda "khusus" dan tombol "Ajukan perubahan" tanpa "Setujui"; manajer melihat antrean dan tombol putus |

## Langkah kerja

1. `backend/tests_mem/test_CRT1_profil_kredit.py`: U1–U15; merah kecuali U1.
2. Koleksi, indeks, `credit_profile_service` (`effective`, `status_from`); tiga kunci pengaturan; alihkan
   `compute_customer_credit` dan `_credit_status`. U7–U9, U11, U15 hijau.
3. Pengajuan dan keputusan + izin di empat tempat (§3.2). U2–U6, U10, U12 hijau.
4. `POST /api/customers` dan pematian jalur lama; skrip migrasi. U13, U14 hijau.
5. Layar; U16 di lingkungan A; U17; gate; laporan (memuat kueri pencari pembaca `customers.credit_limit`).

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (dua koleksi baru; `customers.credit_limit` dan nilai `blocked` usang), `CODEBASE_MAP.md`,
`memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("plafon", "profil kredit", "pengajuan perubahan kredit").

## Di luar lingkup

- Piutang per PT dan eksposur empat baris → CR-T2. Gerbang di titik lain, penegakan termin, izin kredit → CR-T3.
- Mesin denda membaca `penalty_rule` → CR-T4. Antrean "Kaji ulang" plafon dan tab "Kredit & Plafon" → CR-T5.
- Kelompok kredit lintas PT dihitung mesin: belum ada unitnya (field disediakan, layar menulis "belum dipakai").

## Asumsi dan risiko

- `ASUMSI:` rancangan mengusulkan "termin yang diizinkan = tunai saja sampai diisi". Itu akan menolak pesanan tempo
  semua pelanggan lama saat CR-T3 dipasang, maka bawaan dibuat kosong = semua termin (`00` §4.1).
- `ASUMSI:` "hari tenggang" pada rancangan profil hanya dipakai denda (`penalty_rule.grace_days`, CR-T4). Status kredit
  tetap memakai aturan hari ini: telat 1 hari sampai hari blokir = peringatan.
- `ASUMSI:` nominal untuk `kontrol.ubah_profil_kredit.batas_nominal` = plafon baru, bukan selisih kenaikan.
- `ASUMSI:` pelanggan yang bertransaksi di PT selain PT pemilik datanya memakai bawaan PT di PT itu setelah migrasi.
  Laporan memuat kueri pencarinya (pesanan dengan `entity_id` ≠ `customers.entity_id`).
- `RISIKO:` plafon lama tidak terbaca setelah kode dipasang tetapi sebelum migrasi dijalankan. Penangkal: `effective`
  membaca `customers.credit_limit` sebagai cadangan **hanya** bila koleksi profil kosong sama sekali
  (`limit_source: "data_lama"`); cadangan itu dihapus di CR-T3. Membatalkan: kembalikan dua pembaca ke konstanta.

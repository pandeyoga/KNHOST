# CR-T1 — Profil kredit per pelanggan per PT, diubah hanya lewat pengajuan

- Commit awal: `b5b7539` (dikerjakan) · digabung pelaksana di atas `f05d8da`        - Commit: `281374f` · cek visual `0f53340`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: — (unit fitur; memakai dua kunci CR-03/KF-T7 dan menambah lapisan per pelanggan)
- Keputusan: K-27, K-28, K-29 · Standar: `02` §2 (2.1–2.4), §3.1 (Z1, Z2, Z4, Z6), §3.2, §3.4 (N1, N2), §4 (L1, L4, L6),
  §5 (D1, D3, D7, D8, D9), §6 · Risiko sedang (satu serah-terima)
- Prasyarat: PK-45, KF-T6, KF-T7 — ketiganya ada di HEAD

## Cek ulang "Keadaan sekarang" (spesifikasi dibaca di `3132cc4`; dicek di `b5b7539`)

| Fakta spesifikasi | Hasil di `b5b7539` |
|---|---|
| Ambang 0,8 / 14 hari ditulis mati (`customer_service.py:14/15`) | **Tidak berlaku lagi** — KF-T7 menghapus konstanta; kini `customer_service.credit_thresholds` `:217` (`ar.overdue_block_days`, `ar.credit_warning_pct` per PT) → `credit_status` `:234` |
| Salinan kedua di umur piutang (`ar_aging_service.py:34`, `:89 _credit_status`) | **Tidak berlaku lagi** (konstanta) — `_credit_status` bergeser ke `:92`, sudah mendelegasikan ke `customer_service.credit_status` |
| Plafon dari `customers.credit_limit`, 0 = tanpa batas | Berlaku, bergeser: `customer_service.py:259` (`credit_limit = float(customer.get("credit_limit"…))`), `:240–241` (`near`/`over`) |
| Status `blocked` memaksa terblokir | Berlaku, bergeser: `customer_service.py:246` (`manual_status == "blocked"`) |
| `PATCH` menerima `status`/`credit_limit`; PK-45 memindahkan ke `PUT …/credit` | Sesuai keadaan sesudah PK-45: `allowed` `routers/customers.py:184` tanpa keduanya; `PUT /customers/{id}/credit` `:261` (`customer.manage_credit`) |
| `POST /customers` menyimpan plafon (PK-45: hanya pemegang `manage_credit`) | Berlaku: `routers/customers.py:141`; `schemas.py:107` |
| Sales `customer.update`; Finance `customer.view` | Berlaku: `permissions_config.py:275` (sales), `:364` (finance) |
| Gerbang kredit menghitung tanpa PT | Berlaku: `check_credit_for_order` `customer_service.py:331` (dibiarkan — CR-T2/CR-T3; PT profil = PT pemilik data pelanggan) |
| Pesanan boleh ber-PT lain (`payload.entity_id` menang) | Berlaku, bergeser: `routers/sales_orders.py:225` |
| Kunci `ar.*` ada; kunci ambang KF-T7 + `credit_thresholds` | Berlaku: `config_catalog_core.py:153` (`ar.denda_rate_pct_per_month`), `config_catalog_nilai.py:24/34` |
| Kartu pelanggan: plafon `credit.credit_limit`, enam tab riwayat | Berlaku: `Customer360Panel.jsx:56`, `:18` (`HIST_TABS`) |
| Tab "Persetujuan Kredit" di CRM lewat nama peran (`CrmView.jsx:27/51`) | **Tidak berlaku lagi** — MN-T1 memindahkannya ke Keuangan › Piutang › **Kredit & Plafon** (`hubTabs.js:242`, `AppViewRouter.jsx:189` `CreditOverridesPanel`); syarat tampil kini dari katalog akses (`access_modules` modul `customer` nav `credit-overrides`), tombol putus `credit_override.approve` |
| Modul `ar` (`access_modules.py:131`) | Bergeser ke `:139` |

Bukti merah (berkas uji baru terhadap kode `b5b7539` utuh): **18 gagal, 1 lulus** (`bukti/CR-T1/tests_mem_CRT1_merah_kode_lama.log`).
Lulus di kode lama: U1 (sesuai spesifikasi — PK-45 sudah mengabaikan keduanya). Sebab merah lain: rute `credit-profile*`
404, kunci `kontrol.ubah_profil_kredit.*` / `ar.default_credit_limit` tidak ada di registry, sumber daya izin
`credit_profile` tidak dikenal, `PUT …/credit` masih 200, migrasi tidak ada. Catatan U7: bagian status (P1 diblokir 10 > 7,
P2 peringatan) sudah benar sejak KF-T7; yang merah adalah butir CR-T1 di uji yang sama (profil efektif menyebut asal hari
blokir `bawaan_pt`).

## CR-T1 — Profil kredit per pelanggan per PT

- Berlaku di HEAD: ya (fitur belum ada; U2–U16b merah di kode lama).
- Akar masalah: plafon dan blokir disimpan sebagai field data pelanggan (satu nilai lintas PT) dan diubah langsung oleh
  satu tombol simpan; tidak ada dokumen usulan, tidak ada potret angka dasar, tidak bisa berbeda per PT.
- Perubahan perilaku (sebelum → sesudah):
  - **Data.** Koleksi baru `customer_credit_profiles` (`ccp_`, satu per pelanggan × PT pesanan, `version` sebagai syarat
    tulis) dan `credit_profile_requests` (`cpr_`, nomor `{PT}/PKR-NNNNN` lewat `next_doc_number` jenis baru `pkr`,
    `changes[] {field, from, to}`, `credit_snapshot` potret `compute_customer_credit` saat diajukan — D3). Dua indeks unik
    wajib-ada (D7): `customer_credit_profiles.uq_customer_entity` dan `credit_profile_requests.uq_open_request` (parsial
    `status == "diajukan"`); indeks antrean `(entity_id, status, created_at)` dan riwayat. Keduanya SCOPED
    (`entity_scope`), dikenali `scripts/verify_contract.py` (D9), `uq_id`.
  - **Satu penentu.** `services/credit_profile_service.py`: `effective(customer_id, entity_id, today)` (nilai yang dipakai
    mesin + asal: `credit_limit`/`limit_source` khusus · bawaan_pt · tanpa_batas · kedaluwarsa · data_lama,
    `overdue_block_days`/`block_days_source`, `warning_ratio`, termin, `credit_status`, `block_reason`, `limit_valid_until`;
    ambang PT dari `customer_service.credit_thresholds` lalu ditimpa profil) dan `status_from(eff, piutang, telat)` —
    satu-satunya penentu active · warning · blocked (aturan sama dengan sebelumnya). `customer_service.credit_status`
    dihapus; `compute_customer_credit` (PT = argumen `entity_id`, atau PT pemilik data pelanggan) dan
    `ar_aging_service._credit_status` (kini async, mengembalikan status + profil efektif) memanggil keduanya; daftar
    (umur piutang, beranda sales, KPI sales) memuat profil sekali per daftar (`cache_baru`/`muat_profil`).
    `compute_customer_credit` menambah `limit_source`, `overdue_block_days`, `block_days_source`, `warning_ratio`,
    `credit_status_manual`, `block_reason` (L6). Rumus piutang & jatuh tempo tidak diubah.
  - **Pengajuan.** `submit` (alasan ≥ 5 huruf → 409 bila ada yang terbuka → isian diperiksa → potret → simpan; DuplicateKey
    → 409), `decide` (status `diajukan` → `tolak_bila_pelaku_sama("ubah_profil_kredit", …, nominal = plafon baru)` → setuju:
    nilai `from` harus sama dengan profil sekarang lalu tulis bersyarat `version` → tandai pengajuan → jejak
    `credit_profile_changed`; tolak: catatan wajib), `cancel` (pengaju sendiri atau pemutus, alasan wajib).
  - **Endpoint** (`routers/credit_profiles.py`): `GET /api/customers/{id}/credit-profile?entity_id=`
    (`credit_profile.view` + `can_view_credit`; `{profile, effective, pending_request, history}` + nama & pilihan PT, termin
    aktif, aturan dua orang PT), `POST /api/customers/{id}/credit-profile-requests` (`credit_profile.update` +
    `can_access_customer`), `GET /api/credit-profile-requests?status=&customer_id=` (berhalaman, PT aktif, cakupan pelanggan
    pengguna), `POST /api/credit-profile-requests/{id}/decision` (`credit_profile.approve`), `POST …/{id}/cancel`. PT lewat
    `resolve_requested_entity` (N1), pengajuan ber-id lewat `guard_doc` (N2). Galat persis tabel spesifikasi.
  - **Jalur lama (D8).** `PUT /api/customers/{id}/credit` → 410 "Plafon dan blokir kredit diubah lewat pengajuan perubahan
    kredit."; `PATCH` menerima kembali `status` aktif/nonaktif (status lama `blocked` dan `merged` tidak bisa dibuka lewat
    sini); `POST /api/customers` selalu `credit_limit: 0`, isian > 0 → pengajuan `diajukan` atas nama pembuat ("Plafon
    diusulkan saat pelanggan dibuat"). Izin `customer.manage_credit` dicabut dari empat tempatnya (permissions_config,
    label `access_modules`, router, form) dan dari matriks tersimpan lewat migrasi katalog sekali jalan `crt1:izin-kredit`
    (lihat Menyimpang 3).
  - **Pengaturan.** `ar.default_credit_limit` (Pembayaran pelanggan › Peringatan & blokir kredit; money 0 – 1 T, Rp, grup +
    PT, risiko tinggi + alasan, izin `credit_profile.approve`, pemakai `credit_profile_service.py:effective`; tab
    Keuangan & Pajak Pengaturan juga terbuka bagi pemegang izin itu — aturan KF-T1 U14). Aksi kontrol dua orang ke-38
    `ubah_profil_kredit` ("Ubah profil kredit pelanggan", kelompok C, awal "1", bernominal) →
    `kontrol.ubah_profil_kredit.min_orang` + `.batas_nominal` (sub-judul "dua-orang-piutang").
  - **Izin** (empat tempat, §3.2): `credit_profile` di modul "Uang Masuk, Piutang & Faktur Pajak" (`ar`, + nav
    `customers-crm`); bawaan view+update: Admin, Manajer, Finance, Admin Sales, Sales; approve: Admin, Manajer
    (`CRT1_DEFAULT_PAIRS`, tersalin lewat `sync_permission_modules`). Pesan 403 Z6 berkalimat.
  - **Idempotensi (N4).** `/api/credit-profile-requests` di `IDEMPOTENT_PREFIXES`; sub-jalur
    `/api/customers/{id}/credit-profile-requests` lewat pola baru `IDEMPOTENT_PATTERNS` (`is_idempotent_path`). Layar
    mengirim lewat `moneyPost` + `useIntentKey`.
  - **Layar.** Kartu pelanggan: tab **Kredit** (`can(perms, "credit_profile", "view")`) — `CustomerCreditTab.jsx`
    (banner PT, pemilih PT di bilah sendiri, baris nilai berlaku bertanda "ikut PT"/"khusus", termin bertanda "belum
    dipakai saat pesanan dibuat" (L5 — ditegakkan CR-T3), kalimat kedaluwarsa, "Ajukan perubahan" / blok "Menunggu
    keputusan" / "Riwayat perubahan kredit"); pop-up baku `CreditProfileRequestModal.jsx` (FormModal + FormSection, hanya
    isian berubah yang dikirim, "Ajukan & setujui" untuk pemutus bila aturan PT satu orang); `creditProfileUi.jsx`
    (label, lencana ikon+teks+warna, aksi putus/batal dengan konfirmasi pelanggan + PT + plafon baru). Kotak ringkasan
    "Plafon Kredit" membaca plafon efektif + asal. Keuangan › Piutang › **Kredit & Plafon**: `CreditProfileRequestsPanel.jsx`
    di bawah panel izin lewat batas (cari, kolom Keputusan lekat kanan, judul kolom dua baris). Form pelanggan: tanpa isian
    plafon dan tanpa "Diblokir" (status Aktif/Nonaktif; status lama "Diblokir (data lama)" hanya-baca), pelanggan baru
    "Usulan plafon kredit (Rp)" bagi pemegang `credit_profile.update`. Daftar pelanggan & laci Master Data membaca plafon
    efektif. Label jejak audit baru (`auditLabels.js`).
  - **Migrasi (H3).** `scripts/migrate_credit_profiles.py` (bawaan lapor = `--dry-run`; `--terapkan` menulis):
    `credit_limit > 0` → profil `khusus`; `status == "blocked"` → `blokir_manual` + "Dipindahkan dari status pelanggan" dan
    `customers.status` → `active`; idempoten; memasang penanda `system_settings{scope:"__migrations__"}.crt1_profil_kredit`;
    melaporkan pesanan yang PT-nya ≠ PT pelanggan. **Tidak dijalankan ke database mana pun**; diuji di lingkungan B (U14).
- Berkas berubah: lihat bagian "Berkas".
- Commit: belum (instruksi).
- Pengujian: tabel "Uji penerimaan" di bawah.
- Bukti UI: **belum diuji jalan di peramban** — pengganti: uji komponen jest 7/7 + form 3/3 (merah di kode lama).
- Fixture disiapkan langsung vs proses bisnis: alur lewat API — pelanggan (`POST /api/customers`), pengajuan, keputusan,
  pembatalan, pengaturan (`PUT /api/config/values`, `values/clear`), peran uji (`POST /api/access/roles`). Fixture sisip:
  pesanan + surat jalan (U7–U9, U15), `limit_valid_until` kemarin (U11 — server menolak tanggal lampau lewat API),
  pelanggan lama ber-plafon & diblokir (U14), matriks izin tersimpan berisi `manage_credit` (uji migrasi katalog).
- Dampak pada modul terkait: kartu pelanggan, Customer 360, daftar pelanggan, umur piutang, beranda sales, KPI sales, dan
  pemeriksaan kredit pesanan kini membaca plafon/blokir dari profil kredit (PT pemilik data pelanggan untuk gerbang
  pesanan — CR-T2/CR-T3); pesan gerbang "Customer berstatus blocked manual" → "Pelanggan diblokir manual: {alasan}".
- Keterbatasan / belum teruji: U16 (indeks unik parsial di MongoDB asli) ditulis, belum dijalankan; uji jalan peramban;
  `penalty_rule` dan `credit_group_id` hanya disimpan (CR-T4, belum ada unit kelompok kredit); `allowed_term_codes` belum
  ditegakkan saat pesanan dibuat (CR-T3).
- Status: implemented_pending_review

## Uji penerimaan

`backend/tests_mem/test_CRT1_profil_kredit.py` (19 uji). Merah di kode `b5b7539`: 18/19 (`bukti/CR-T1/tests_mem_CRT1_merah_kode_lama.log`).

| ID | Lapis | Merah di kode lama (sebab) | Hasil kode baru |
|---|---|---|---|
| U1 | B | **tidak** (sesuai spesifikasi — PK-45) | Lulus — 200; `credit_limit` 0, `status` active; 0 profil, 0 pengajuan |
| U2 | B | ya (404 rute) | Lulus — 200 `diajukan`, `KSC/PKR-00001`, potret plafon 0; `limit_source == "bawaan_pt"` |
| U3 | B | ya (tidak ada pengajuan) | Lulus — 403 berkalimat modul "Uang Masuk, Piutang & Faktur Pajak"; tetap `diajukan` |
| U4 | B | ya | Lulus — 50.000.000 `khusus`, `version == 1`, riwayat 1 baris `from: null → to: 50000000`; kotak 360 = 50 jt `khusus`, `customers.credit_limit` tetap 0 |
| U5 | B | ya (kunci kontrol 404) | Lulus — Manajer memutus sendiri 403 (pesan dua orang), Admin 200 → 60 jt |
| U6 | B | ya (kunci kontrol 404) | Lulus — `ent_kanda` 200 walau `ent_ksc` = 2 |
| U7 | B | ya (butir CR-T1; status sendiri sudah benar sejak KF-T7) | Lulus — P1 `blocked` (10 > 7), P2 `warning` (10 ≤ 14); asal hari blokir `bawaan_pt` 7 / 14 |
| U8 | B | ya | Lulus — `overdue_block_days: 30` `khusus` → P1 `warning` (10 ≤ 30) |
| U9 | B | ya | Lulus — 8.500.000 ≥ 80 % × 10.000.000 = 8.000.000 → `warning`; 90 % → 8.500.000 < 9.000.000 → `active` (kartu & umur piutang) |
| U10 | B | ya | Lulus — 409 pesan persis; 400 "Isian tidak sah: Plafon kredit — harus angka nol atau lebih."; 400 "…Termin yang diizinkan — kode termin tidak dikenal: XX99."; + tanggal lampau, khusus tanpa angka, alasan < 5 huruf (400); jumlah pengajuan tetap; batal oleh Sales lain 403, alasan kosong 400, pengaju 200; putus sesudah batal 409 |
| U11 | B | ya | Lulus — `credit_limit == 0`, `limit_source == "kedaluwarsa"`, plafon khusus tersimpan 10 jt |
| U12 | B | ya (sumber daya izin tidak dikenal) | Lulus — Tanpa Acuan + view: GET 200, POST 403; Manajer Kosong & Sopir GET 403; Tanpa Acuan + view/update/approve: ajukan + putus 200 |
| U13 | B | ya | Lulus — pelanggan `credit_limit == 0`; satu pengajuan `diajukan` `limit_mode → khusus`, `credit_limit → 25000000`, alasan "Plafon diusulkan saat pelanggan dibuat", pengaju = Sales |
| U14 | B | ya (fungsi/skrip tidak ada) | Lulus — sebelum migrasi cadangan `data_lama` (15 jt, `blokir_manual`); skrip `--dry-run` tidak menulis ("1 profil akan dibuat, 1 pelanggan dibuka"); tulis: satu profil `khusus` 15 jt `blokir_manual`, `customers.status == "active"`, `credit_limit` tidak dihapus; putaran kedua 0/0, dokumen identik |
| U15 | B | ya (kunci 404) | Lulus — putaran `t1_config` (fungsi `putaran` KF-T8) tanpa gagal; 5.000.000 di `ent_ksc` → pelanggan tanpa plafon khusus KSC 5 jt `bawaan_pt`, KANDA 0; piutang 5 jt ≥ 5 jt → `blocked`; dicabut → 0 |
| U16 | A | — | **Lulus** di lingkungan A (MongoDB 7 asli; bersama PK-14 lapis A — 18 indeks wajib: 11 lulus): `backend/tests/test_bp_CRT1_profil_kredit.py` (indeks wajib terpasang + lima putaran dua POST bersamaan) |
| U16b | B (tambahan) | ya (404) | Lulus — `asyncio.gather` dua POST: [200, 409], satu `diajukan` (database tiruan tanpa indeks parsial: pembantu "yang terbaru mengalah" di `submit`) |
| U17 | layar | ya (komponen tidak ada) | Uji komponen jest `features/__tests__/crt1ProfilKredit.test.js` 7/7: Sales melihat 50 jt "khusus" + "Ajukan perubahan" tanpa Setujui/Tolak; Manajer melihat antrean + tombol putus. **Uji jalan peramban belum dilakukan** |
| tambahan | B | ya | Jalur lama 410 + PATCH status aktif/nonaktif + `manage_credit` hilang dari bawaan & matriks tersimpan + `credit_profile.*` bawaan per peran; migrasi katalog `crt1:izin-kredit` saat menyala (matriks lama berisi `manage_credit` → dibuang; editor peran bisa menyimpan lagi); kontrol & idempotensi terdaftar |

`backend/tests_mem` seluruhnya: HEAD **1303 lulus / 2 dilewati / 4 xfail** → sesudah **1322 lulus / 2 dilewati / 4 xfail**
(+19 uji CR-T1, +3 kasus putaran KF-T8 untuk tiga kunci baru, −3 uji PK-45 yang dilebur; `bukti/CR-T1/tests_mem_sebelum.log`,
`tests_mem_sesudah.log`).

Jest (`src/config/__tests__` + `src/features/__tests__` + `src/components`, `bukti/CR-T1/jest_seluruh_kode_*.log`): HEAD
83 suite lulus / 34 gagal dimuat / **662** uji lulus → sesudah 84 / 34 / **668** uji lulus (+7 `crt1ProfilKredit`,
`pk45KreditPelanggan` 4 → 3). 34 suite gagal dimuat identik di kedua sisi (`@radix-ui/primitive/is-development` tidak
terpasang lokal — kendala lingkungan). Bukti merah jest: `bukti/CR-T1/jest_merah_kode_lama.log`.

## Uji yang disesuaikan (perilaku sengaja berubah — angka/harapan, tidak dilonggarkan)

| Berkas | Perubahan | Alasan |
|---|---|---|
| `tests_mem/test_PK45_penjaga_cepat.py` | U2/U3/U4/U6 dilebur menjadi `test_PK45_U2_U3_U4_U6_jalur_kredit_lama_410` (410, data & jejak tetap); U5b: plafon Admin kini pengajuan, pelanggan 0; uji izin `manage_credit` → peran dengan pasangan itu ditolak 400; uji matriks tersimpan: hanya `order.tax_override` | Jalur sementara PK-45 dimatikan (D8), izin dicabut; pengganti diuji `test_CRT1_*` |
| `tests_mem/test_PRT9_izin_bawaan.py` | `TAMBAHAN_SESUDAH`: PK-45 tanpa `manage_credit`, + `CRT1_DEFAULT_PAIRS`; `JUMLAH_MIGRASI` 19 → 20 | izin bawaan baru; butir migrasi `crt1:izin-kredit` |
| `tests_mem/test_KFT1_izin_pengaturan.py` | U02 `+ CRT1_KUNCI_KONTROL` (2), U04 `+ CRT1_KUNCI` (3) | dua kunci `kontrol.ubah_profil_kredit.*` (`settings.manage`) + `ar.default_credit_limit` (`credit_profile.approve`) |
| `tests_mem/test_KFT6_kontrol.py` | `N_AKSI` 37 → 38, `N_KUNCI` 60 → 62, `BERNOMINAL` + `ubah_profil_kredit` | aksi ke-38 |
| `tests_mem/test_KFT4_registry.py` | `CRT1_PEMBAYARAN_PELANGGAN = 1` | kunci baru di kelompok Pembayaran pelanggan |
| `tests_mem/test_KPT5a_setara.py`, `test_KPT5b_pengaturan.py` | `AWALAN_SESUDAH_KPT5 = {"PKR-"}`; jumlah jenis 66 → 67 | deret nomor baru `pkr` |
| `tests_mem/test_PK14_indeks_wajib.py`, `tests/test_bp_PK14_indeks_wajib.py` (lapis A) | indeks wajib + 2 (16 → 18) | `uq_customer_entity`, `uq_open_request` |
| `tests_mem/test_KFT7_nilai_tertulis.py` U5 | sumber kedua pembaca kini lewat `credit_profile_service.effective` (yang membaca `credit_thresholds`) | satu jalur status `status_from` |
| `frontend/src/features/__tests__/pk45KreditPelanggan.test.js` | ditulis ulang: form tanpa plafon/"Diblokir", status lewat PATCH, usulan plafon pelanggan baru | form PK-45 sengaja diubah |
| `frontend/src/config/__tests__/fixtures/access_builtin_fixture.json` | dibangkitkan ulang (`tests/fe03_access_fixture.py`; `tests/test_fe03_access_catalog.py --noconftest` 6/6) | izin bawaan baru |
| `frontend/src/features/settings/config/configKeyIndex.json` | dibangkitkan ulang (`gen_config_key_index.py`) | tiga kunci baru |

## Kueri pencari (diminta spesifikasi)

Pembaca `customers.credit_limit` tersisa (backend, di luar uji/seed):
`grep -rn "credit_limit" backend --include=*.py | grep -v "/tests/\|tests_mem\|backend_test_\|seed_"` → hanya
(a) proyeksi `ar_aging_service.py:122/417` yang meneruskan dokumen pelanggan ke `credit_profile_service` (cadangan
`data_lama` + migrasi, `profil_data_lama`), (b) penulis nilai 0 (`routers/customers.py:141`, `crm_omnichannel_service.py:175`,
`scripts/uat24_f0_data.py:65`), (c) isian usulan `schemas.py:107` → pengajuan. Semua angka `credit_limit` lain adalah plafon
EFEKTIF hasil `effective`. Frontend: `CustomerList` dan laci Master Data (`AdminView`) tidak lagi jatuh ke field pelanggan.

Pesanan yang PT-nya ≠ PT pemilik data pelanggan (ASUMSI unit — di PT itu pelanggan memakai bawaan PT; dicetak juga oleh
skrip migrasi):
```
db.sales_orders.aggregate([{$lookup:{from:"customers",localField:"customer_id",foreignField:"id",as:"c"}},{$unwind:"$c"},
  {$match:{$expr:{$ne:["$entity_id","$c.entity_id"]}}},
  {$group:{_id:{pelanggan:"$customer_id",pt_pesanan:"$entity_id",pt_pelanggan:"$c.entity_id"},pesanan:{$sum:1}}}])
```
Calon profil migrasi (baca saja): `db.customers.find({$or:[{credit_limit:{$gt:0}},{status:"blocked"}]},{id:1,name:1,entity_id:1,credit_limit:1,status:1})`.

## Hitungan tangan (status kredit — tidak ada jurnal di unit ini)

- U7: telat terlama 10 hari. `ent_ksc` hari blokir 7 → 10 > 7 → `blocked`; `ent_kanda` 14 → 10 ≤ 14, telat ≥ 1 →
  `warning`; piutang 1.000.000 < 80 % × 60.000.000 (P1) / 100.000.000 (P2) → tidak memicu plafon.
- U8: hari blokir khusus 30 → 10 ≤ 30 → `warning`.
- U9: plafon 10.000.000; piutang 8.500.000 (belum jatuh tempo). 80 % → 8.000.000 ≤ 8.500.000 → `warning`; 90 % →
  9.000.000 > 8.500.000 → `active`.
- U15: plafon bawaan `ent_ksc` 5.000.000; piutang 5.000.000 ≥ 5.000.000 → `blocked`; `ent_kanda` bawaan 0 = tanpa batas.

## Berkas

- Server baru: `backend/services/credit_profile_service.py`, `backend/routers/credit_profiles.py`,
  `scripts/migrate_credit_profiles.py`.
- Server diubah: `services/customer_service.py` (`compute_customer_credit`, `check_credit_for_order`; `credit_status`
  dihapus), `services/ar_aging_service.py`, `services/home_service.py`, `services/sales_force_service.py`,
  `services/so_verify_service.py` (proyeksi), `routers/customers.py`, `schemas.py`, `schemas_crm.py`
  (`CustomerCreditUpdate` → `CreditProfileRequestCreate`/`Decision`/`Cancel`), `server.py`, `permissions_config.py`
  (`CRT1_DEFAULT_PAIRS`, `CRT1_REMOVED_PAIRS`), `access_modules.py`, `services/custom_role_service.py`
  (`migrate_crt1_catalog`, `_buang_pasangan_tersimpan` dipakai bersama PR-T5), `bootstrap.py` (1 panggilan),
  `config_catalog_nilai.py`, `config_catalog_kontrol.py`, `doc_number_kinds.py`, `entity_scope.py`, `indexes.py`,
  `idempotency.py`, `scripts/verify_contract.py`.
- Layar baru: `features/crm/CustomerCreditTab.jsx`, `CreditProfileRequestModal.jsx`, `CreditProfileRequestsPanel.jsx`,
  `creditProfileUi.jsx`. Diubah: `features/crm/Customer360Panel.jsx`, `CustomerFormModal.jsx`, `CustomerList.jsx`,
  `features/admin/AdminView.jsx`, `AppViewRouter.jsx`, `appViewImports.js`, `config/auditLabels.js`.
- Uji: `backend/tests_mem/test_CRT1_profil_kredit.py`, `backend/tests/test_bp_CRT1_profil_kredit.py` (lapis A, ditulis),
  `frontend/src/features/__tests__/crt1ProfilKredit.test.js`; disesuaikan: tabel di atas.
- Dokumen: `ENTITY_REGISTRY.md` (dua koleksi, prefix, `customers.credit_limit` & `blocked` usang), `CODEBASE_MAP.md`
  (`gen_codebase_map.py`), `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9 ("Plafon (kredit)",
  "Profil kredit", "Pengajuan perubahan kredit").

## Cek layar

Belum dipotret (integrator memotret 1280/1024/390 px). Daftar periksa dari kode:

| Layar | (1) tabel ⊂ kartu | (2) bantalan | (3) kepala kartu | (4) tombol mati beralasan | (5) status ikon+teks+warna | (6) cari/saring | (7) teks vs izin | (8) kosong / angka 0 |
|---|---|---|---|---|---|---|---|---|
| Kartu pelanggan › tab **Kredit** (di kartu "Riwayat 360°", `section-body`) | nilai berlaku = daftar `dl` berbaris (bukan tabel; baris membungkus di 390 px); riwayat 5 kolom `data-table head-wrap` di `overflow-x-auto`, tanpa kolom aksi | isi di `section-body` (14 px); blok "Menunggu keputusan" berbingkai dengan bantalan `px-3 py-2` | pemilih PT di bilah sendiri (bukan kepala); kepala blok menunggu = judul + satu lencana | "Ajukan perubahan" mati + "Masih ada pengajuan yang menunggu keputusan — putuskan atau batalkan dulu."; Setujui/Tolak mati + "Anda yang mengajukan — rekan lain yang memutus (aturan dua orang di PT ini)." | lencana asal "khusus" (ikon orang) / "ikut PT" (ikon gedung) / "data lama" (ikon riwayat); status pengajuan Menunggu/Disetujui/Ditolak/Dibatalkan = `status-pill` ikon+teks+token | riwayat ≤ 20 baris (server) — tanpa cari | tanpa `credit_profile.update`: "Perubahan plafon dan blokir diajukan oleh pemegang akses mengajukan perubahan kredit."; tunggu: "Berlaku setelah diputus pemegang akses memutus pengajuan kredit." (tanpa "bukan wewenang") | satu kosong ("Belum ada perubahan kredit."); plafon 0 ditulis "Tanpa batas", bukan "Rp 0" |
| Kartu pelanggan › kotak "Kontrol Kredit" | — | tetap | tetap | — | — | — | — | "Plafon Kredit" + asal ("khusus"/"ikut PT"); 0 → "Tanpa batas" |
| Kartu pelanggan › bilah tab riwayat | 8 tombol (6 lama + Kredit + Riwayat Perubahan); `tab-bar` bergulir mendatar di HP (L-04) — **perlu dinilai di 1024 px** | — | — | — | — | — | tab Kredit hanya bila `credit_profile.view` | — |
| Pop-up "Ajukan perubahan kredit" (`FormModal size=md` + `FormSection` bernomor) | — | baku | judul + subjudul pelanggan · PT | tombol tidak dimatikan; kekurangan ditulis "Lengkapi: …" di kaki | — | — | "Ajukan & setujui" hanya untuk pemutus bila aturan PT satu orang (tidak ada teks "bukan wewenang") | termin tanpa centang: "Tidak ada yang dicentang = semua termin aktif PT boleh."; PT tanpa syarat bayar ditulis |
| Keuangan › Piutang › Kredit & Plafon › **Pengajuan perubahan kredit** | 5 kolom `data-table head-wrap`, kolom "Keputusan" `col-sticky-end`, wadah `overflow-x-auto` | `section-head` + `section-body` | judul + lencana "{n} menunggu" (tanpa tombol) | Setujui/Tolak mati + "Anda yang mengajukan — rekan lain yang memutus." | lencana jumlah = jam + teks + token peringatan | kotak cari (pelanggan / nomor / pengaju) + pager klien; ≤ 50 dari server dengan "Menampilkan n dari N" | tanpa approve: "Pengajuan ini berlaku setelah diputus pemegang akses memutus pengajuan kredit."; kolom berisi "Menunggu pemutus" | satu kosong ("Tidak ada pengajuan perubahan kredit yang menunggu keputusan."); panel tidak tampil tanpa `credit_profile.view` |
| Form pelanggan (ubah / baru) | — | baku | — | — | status lama "Diblokir (data lama)" hanya-baca + petunjuk ke tab Kredit | — | catatan "Plafon dan blokir kredit diatur lewat pengajuan di tab Kredit pada kartu pelanggan."; usulan plafon hanya bagi pemegang `credit_profile.update` | — |

Token `kn-*` dan `text-fs-*` (tanpa hex/`text-[Npx]` baru); `verify_ui_standard` 13 = 13, `verify_role_gate_ui` 0
pelanggaran, `verify_page_tabs` 1 = 1 (panel baru tanpa `tab-bar`), `audit_create_modal` 6 = 6.

## Cek layar (potret integrator)

Dipotret di lingkungan A (`admin@`, data acuan, Toko Kain Sejahtera): tab Kredit kartu pelanggan (1280 dan 1024 px) dan
Keuangan › Piutang › Kredit & Plafon. Profil kredit yang berlaku tampil per baris dengan asal berikon ("Data Lama",
"Khusus", "Ikut PT"), termin bertanda "belum dipakai saat pesanan dibuat", luapan halaman 0. Diperbaiki (`0f53340`):
panel override kosong menulis kode tab mentah "(pending)"; kartu Belum Lunas memakai "ledger"/"eksposur" → "Piutang
tercatat … · pesanan belum dikirim …" (istilah PK-42). Catatan: tab Riwayat 360° kini delapan tombol dan membungkus dua
baris di 1280 px (diterima; bukan hub). Bukti: `bukti/CR-T1/layar_tab_kredit_1280.png`, `layar_tab_kredit_1024.png`,
`layar_kredit_plafon_1280.png`.

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di `a48a0a9` — satu gate untuk
enam unit yang digabung bersamaan (CR-T1, PK-31, AG-T1, PM-T2, TX-T1, PK-18) — lalu `--quick` diulang di `f1b8239` sesudah
perbaikan cek layar (hanya layar):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` (`a48a0a9`) | 14 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama: `InventoryStockView`) | 2 (`config_wiring` + uji-diri) |
| `--ci` (`a48a0a9`) | 41 FAIL | 43 | 1 (ganti nama) | 2 |
| `--quick` (`f1b8239`) | 14 FAIL | 16 | 1 (ganti nama) | 2 |

Kuitansi: `bukti/CR-T1/gate_quick_receipt.md`, `gate_ci_receipt.md`. Lapis A unit-unit itu (6 berkas `tests/test_bp_*`) di
lingkungan A: 19 lulus.

Di salinan kerja (lingkungan B / statik):

| Pemeriksaan | Sebelum (HEAD) | Sesudah |
|---|---|---|
| `tests_mem` | 1303 lulus / 2 dilewati / 4 xfail | 1322 lulus / 2 dilewati / 4 xfail |
| jest (3 folder) | 662 lulus; 34 suite gagal dimuat (radix) | 668 lulus; 34 suite gagal dimuat (sama) |
| `hitung_penjaga.sh` (16 penjaga) | auth 28 · ui 13 · i18n 104 · create_modal 6 · page_tabs 1 · to_list 6 · entity_label 2 · lainnya PASS/0 | **identik** (`bukti/CR-T1/penjaga_statik_sebelum_sesudah.log`) |
| `verify_config_fallback` · `--entity` · `verify_payment_vocab` · `verify_config_text` · `verify_permission_checked` · `verify_ui_contrast` · `verify_role_gate_ui` | PASS | PASS (147 · 147 · 1750 · 3087 · 588 cek · 58 · 31) |
| `verify_atomic_claim` | 6 | 6 |
| `audit_config_wiring.py --strict` (salinan berjalur) | bersih | bersih |
| `gen_config_key_index.py --check` · `verify_codebase_map` | — | selaras · PASS |
| `tests/test_fe03_access_catalog.py --noconftest` | — | 6/6 |

## Penggabungan ke HEAD cabang terbaru

Basis kerja `b5b7539` → worktree tujuan `wt9` di HEAD **`f05d8da`** (14 commit sesudah basis: KP-T9, PK-44, perbaikan
tampilan & penjaga). Per berkas (`git merge-file -p HEAD B W`): 33 berkas sama di HEAD dan basis → disalin; 8 tergabung
otomatis (`ENTITY_REGISTRY.md`, `access_modules.py`, `bootstrap.py`, `doc_number_kinds.py`, `KN_32`, `appViewImports.js`,
`AdminView.jsx`, fixture akses — lalu dibangkitkan ulang); 10 berkas baru disalin. Bentrok (semua tambahan berdampingan, KEDUA sisi dipertahankan):

| Berkas | Bentrok | Keputusan |
|---|---|---|
| `frontend/src/AppViewRouter.jsx` | daftar impor: HEAD menambah `SettingsLinkCards` (KP-T9), unit menambah `CreditProfileRequestsPanel` | keduanya dalam satu daftar |
| `memory/PRD.md` | dua butir baru di tempat yang sama (PK-44 dan CR-T1) | keduanya; CR-T1 di atas PK-44 |
| `CODEBASE_MAP.md` | berkas bangkitan | dibangkitkan ulang (`gen_codebase_map.py`; `verify_codebase_map` PASS) |

Dibangkitkan ulang di T: `configKeyIndex.json`, fixture akses (`tests/test_fe03_access_catalog.py --noconftest` 6/6).
Hitungan uji lama tidak perlu dijumlah ulang: berkas uji yang menghitung (KF-T1, PRT9, PK-14, KF-T6, KF-T4, KP-T5)
identik di HEAD dan basis. Sesudah penggabungan satu perubahan kecil ikut di W dan T: label status pengajuan lewat
`docStatusLabel` (aturan baru brief).

| Pemeriksaan di T | HEAD `f05d8da` | Sesudah gabung |
|---|---|---|
| `tests_mem` | 1334 dikumpulkan (tanpa CR-T1) | **1347 lulus / 2 dilewati / 4 xfail** (1353 dikumpulkan; 0 gagal) |
| jest 3 folder | 726 lulus; 34 suite gagal dimuat (radix) | **732 lulus**; 34 suite gagal dimuat (sama) |
| `hitung_penjaga.sh` | auth 28 · ui 13 · i18n 104 · create_modal 6 · page_tabs 1 · to_list 6 · entity_label 2 · lainnya PASS/0 | **identik** |
| `verify_role_gate_ui` · `verify_config_fallback` · `--entity` · `verify_payment_vocab` · `verify_access_catalog_nav` | — | PASS 31 · 147 · 147 · 1754 · 0 temuan |
| `audit_config_wiring --strict` · `check_nav_map.py` (salinan berjalur T) | — | bersih · PASS (HEAD juga PASS) |

Bukti: `bukti/CR-T1/T_tests_mem.log`, `T_jest_seluruh.log`, `T_jest_HEAD_ringkas.log`, `T_penjaga_statik.log`.

## Menyimpang dari blueprint

1. **Cadangan `data_lama` per pelanggan + penanda migrasi**, bukan "hanya bila koleksi profil kosong sama sekali". Dengan
   aturan spesifikasi, pengajuan PERTAMA yang disetujui sebelum migrasi akan mematikan plafon & blokir lama SEMUA pelanggan
   lain sekaligus. Kini: tanpa profil di PT pemilik datanya dan selama penanda `crt1_profil_kredit` belum dipasang skrip
   `--terapkan`, `effective` membaca nilai yang PERSIS akan ditulis migrasi (`profil_data_lama`; `credit_limit > 0` atau
   `status == "blocked"`; plafon 0 & aktif → ikut PT, jadi U2 tetap `bawaan_pt`). Pengajuan untuk pelanggan seperti itu
   memakai nilai lama sebagai `from` dan dasar profil baru. Cadangan dihapus di CR-T3 (tetap).
2. **Status lama `blocked` ikut cadangan** (spesifikasi hanya menyebut plafon): tanpa itu pelanggan yang diblokir lewat
   PK-45 langsung terbuka saat kode dipasang. Untuk alasan yang sama `PATCH` tidak mengubah status pelanggan yang masih
   `blocked` (aktif/nonaktif hanya dari aktif/nonaktif); form menampilkannya hanya-baca.
3. **Migrasi katalog izin saat menyala** (`crt1:izin-kredit`, pola PR-T5; fungsi pembuangnya dipakai bersama PR-T5): tanpa
   ini matriks tersimpan (yang menerima `customer.manage_credit` lewat PK-45/PR-T9) membuat editor peran gagal menyimpan
   ("Aksi ['manage_credit'] tidak berlaku…" — editor mengirim balik izin tersimpan). Hanya membuang satu pasangan yang tidak
   lagi diperiksa server; tidak menambah izin. Butir migrasi ke-20 (`JUMLAH_MIGRASI`). **Tinjau sebelum rilis (H3?)**.
4. **Sub-jalur ber-id untuk idempotensi**: `/api/customers/{id}/credit-profile-requests` tidak bisa dinyatakan sebagai
   awalan; ditambah `IDEMPOTENT_PATTERNS` (regex jalur penuh) + `is_idempotent_path` di middleware. Awalan
   `/api/credit-profile-requests` di `IDEMPOTENT_PREFIXES` seperti spesifikasi.
5. **Syarat tampil tab "Kredit & Plafon" tidak diubah**: MN-T1 sudah memindahkannya dari nama peran ke katalog akses
   (`customer.view`). Panel pengajuan di dalamnya tampil bila `credit_profile.view`, tombol putus bila
   `credit_profile.approve`.
6. **Menu `customers-crm` di `nav` modul piutang** (§3.2) disertai `VIEW_RESOURCE_OVERRIDES["customers-crm"] = ["customer"]`:
   daftar pelanggan menuntut `customer.view`, jadi pemegang izin piutang tanpa izin pelanggan tidak mendapat menu yang
   langsung menolak. Indeks menu efektif tidak berubah (`['customer']` sebelum dan sesudah).
7. **Urutan `decide`** sesuai spesifikasi (tulis profil bersyarat versi → tandai pengajuan); bila penandaan gagal karena
   pengajuan diputus/dibatalkan orang lain di sela-sela, profil dikembalikan (bersyarat versi baru) dan 409. Bila nilai
   `from` tidak cocok (profil berubah di luar pengajuan), pengajuan dibatalkan otomatis supaya "Buat pengajuan baru" bisa
   dilakukan (satu pengajuan terbuka per pelanggan per PT).
8. **Usulan plafon saat pelanggan dibuat** hanya diajukan bila pembuat memegang `credit_profile.update`; tanpa itu
   pelanggan tetap terbuat dan jawaban memuat `credit_profile_request.error` (spesifikasi tidak menyebut pembuat tanpa izin).
9. **Termin yang diizinkan / termin bawaan** tampil bertanda "belum dipakai saat pesanan dibuat" (L5; ditegakkan CR-T3).
10. Tambahan kecil: pembatalan wajib alasan ≥ 5 huruf (N5); `GET …/credit-profile` juga mengirim nama PT, pilihan PT,
    termin aktif, dan aturan dua orang PT (layar tanpa id teknis); `credit_profile_requests.base_version`; validasi bentuk
    `penalty_rule` (mode, angka ≥ 0, dasar dari pilihan `payment.penalty_base`); pesan gerbang pesanan berbahasa Indonesia.

## Asumsi

- `ASUMSI` unit dipakai apa adanya: termin kosong = semua termin; hari tenggang hanya untuk denda (CR-T4); nominal kontrol
  = plafon baru; Finance mengajukan, tidak memutus; pelanggan yang bertransaksi di PT lain memakai bawaan PT itu.
- Profil gerbang pesanan (`check_credit_for_order`) = PT pemilik data pelanggan (PT pesanan masuk di CR-T3).
- "Riwayat" = 20 pengajuan terakhir berstatus disetujui/ditolak (dibatalkan tidak termasuk "sudah diputus").
- Admin pengaju boleh memutus sendiri bila `kontrol.admin_boleh_sendiri` = ya (perilaku KF-T6).

## Hambatan lingkungan

- **Pelanggaran aturan kerja (dilaporkan apa adanya):** saat memeriksa penjaga statik tambahan, `scripts/guardrails/
  verify_cross_entity.py` ikut terjalankan. Penjaga itu ternyata RUNTIME: memuat `backend/.env` (salinan dari repo utama =
  database lingkungan A), mengambil potret database, login ke backend `:8001` (sales/gudang seed), mencoba baca dan satu
  tulis lintas-PT (semua ditolak 404), lalu memulihkan potret (`run_with_restore`). Tidak ada data uji CR-T1 yang dikirim.
  Risiko: pemulihan potret bisa menimpa tulisan lain di database A pada detik yang sama. Integrator mohon memeriksa.
- U16 dan potret layar dijalankan integrator (lihat "Cek layar (potret integrator)"); alur ajukan → putus belum diklik di peramban.

## Yang perlu direview

Cadangan `data_lama` per pelanggan (Menyimpang 1–2) dan kapan skrip migrasi dijalankan (H3); migrasi katalog izin saat
menyala (Menyimpang 3); pola idempotensi regex (Menyimpang 4); pembatalan otomatis pengajuan basi (Menyimpang 7);
8 tombol di bilah tab riwayat kartu pelanggan (cek 1024 px).

Status: implemented_pending_review.

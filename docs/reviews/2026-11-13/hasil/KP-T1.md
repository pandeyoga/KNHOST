# KP-T1 — Profil PT yang jujur dan bisa diubah

- Commit awal: `4db17eb` (dikerjakan) · digabung di atas `9783875` (sesudah KP-T4, KF-T5, KF-T3)        - Commit akhir: `69cc4e3`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KP-01, KP-02, KP-23 (spesifikasi `docs/blueprint/unit/KP-T1.md`; keputusan K-08, K-10, jawaban pemilik
  butir 3 dan 4)

## Cek ulang "Keadaan sekarang"

Spesifikasi dibaca pada `3132cc4`; dicek ulang pada `4db17eb`. Semua butir masih berlaku; beberapa baris bergeser.

| # | Hasil di `4db17eb` |
|---|---|
| 1 | Berlaku. `entity_context_service.py:24` (`ENTITY_DEFAULTS`), `entity_lifecycle_service.py:40` (`EDITABLE_FIELDS`), `:95` (`uniform_entity`). Pencarian seluruh `backend/` + `frontend/src`: lima isian hanya di layanan PT, `schemas.py:144-152`, `bootstrap.py:341-351` (benih), wizard, detail, dan dua berkas uji lama |
| 2 | Berlaku. `EntityWizard.jsx:292` (fiskal), `:300` (insentif), `:350` (skema) |
| 3 | Bergeser: `closing_service.py:79` (`period_bounds`, dari 76); `config_catalog_core.py:94` (dari 91) |
| 4 | Berlaku/bergeser: `config_currency.py:31`; `gl_service.py:3822` (`consolidation`, dari 3739; `currency` di `:3842`); `EntityList.jsx:213` |
| 5 | Bergeser: `EntityWizard.jsx:288` (dari 287) |
| 6 | Berlaku. `core_utils.py:19` — `scheme` bawaan `per_entity_prefix`, tidak pernah diisi dari PT |
| 7 | Berlaku. `EntityDetailDrawer.jsx:19` (`EDITABLE`), `:140` (`is_pkp`) |
| 8 | Bergeser: `routers/entities.py:182` (`update_entity`, dari 162); `entity_provisioning_service.py:100` |
| 9 | Bergeser: `config_service.py:280` (`get_effective_settings`, dari 250; paksaan 0/False di `:300-302`); `tax_invoice_service.py:32` |
| 10 | Berlaku. `entity_provisioning_service.py:106` (NPWP), `:132` (fiskal `\d{2}-\d{2}`) |
| 11 | Berlaku/bergeser: `consolidation_service.py:132`; `ClosingView.jsx:62` (dari 49; juga `GroupConsolidationParts.jsx:138`, `PeriodUnlockView.jsx:56`, `SuspensePanel.jsx:30`) |
| 12 | Berlaku. `entity_readiness_service.py:109` |
| Dipertahankan | `entity_provisioning_service.py:47` (`validate_entity_input`), `entity_lifecycle_service.py:188` (`assert_prefix_change_allowed`) — berlaku, tetap |
| `ASUMSI` spesifikasi | `currency` dari `/auth/context` tidak dibaca layar mana pun — benar: `frontend/src` hanya `EntityList.jsx:213` dan wizard |
| Unit selesai terkait | PR-T3: kunci S2 `GET /api/entities` (14) memuat `currency` — **tidak diperluas**, `currency` kini diisi dari registry. PK-16/PK-17/PR-T7: tidak bersinggungan; layar memakai `can(...)` yang sudah ada (`EntitiesAccessView.jsx:52-53`) |

## KP-01 / KP-02 / KP-23 — profil PT

- Berlaku di HEAD: ya, semua (tabel di atas; bukti merah di bawah).
- Akar masalah: master PT menyimpan dan mengirim enam isian yang tidak dibaca mesin (tahun buku dan mata uang yang
  dibaca mesin ada di registry), status PKP hanya bisa dipilih saat PT dibuat (atau diubah diam-diam lewat `PATCH`
  tanpa alasan/tanggal), dan validasi isian longgar.
- Perubahan perilaku (sebelum → sesudah):
  - **Isian mati dibuang** dari bawaan (`ENTITY_DEFAULTS = {"is_group": False, "ownership_pct": 100.0}`), skema
    `BusinessEntityCreate`, daftar ubah, `uniform_entity`, jawaban `provisioning` (`numbering_scheme`), benih
    `seed_entities`, wizard, dan detail. Field lama di dokumen PT **tidak dihapus**.
  - **Tahun buku & mata uang satu sumber**: `lifecycle.profile_settings(entity_id)` →
    `{base_currency, fiscal_year_end_month, base_currency_source, fiscal_year_end_month_source}` (resolver,
    `source_layer`); router menempelkannya + `currency = base_currency` ke `GET /api/entities` (baris rujukan S2 tetap 14
    kunci), `GET /api/entities/{id}`, `POST`, `PATCH`, arsip, aktifkan kembali. `POST /api/entities` menerima
    `base_currency`/`fiscal_year_end_month` (diperiksa dengan aturan registry **sebelum** PT lahir → 400) dan menulis
    lapisan PT lewat `config_resolver.set_value(..., reason="Ditetapkan saat PT dibuat")` hanya bila beda dari nilai grup.
    `gl_service.consolidation`: `currency` baris = `config_currency.base_currency(eid)`. Kesiapan "Tahun buku" membaca
    nilai efektif registry.
  - **Validasi** (`validate_entity_input`, hanya isian yang dikirim dan berubah): NPWP 15/16 digit setelah titik/strip/
    spasi dibuang (disimpan dipangkas), `ownership_pct` > 0 dan ≤ 100, `is_group` boolean, `default_tax_mode` berbeda
    lewat `PATCH` → 400 "Status PKP diubah lewat tindakan 'Ubah status PKP', bukan lewat ubah profil.". Validasi
    "MM-DD" lama dibuang bersama isiannya.
  - **Ubah status PKP** (izin `entity.update`, pesan 403 Z6; PT dalam penugasan; PT terarsip → 409 "PT ini sudah
    diarsipkan."): `GET …/tax-status/preview`, `POST …/tax-status`, `DELETE …/tax-status/pending`. Tanggal ≤ hari ini
    (WIB) → ubah bersyarat `{id, default_tax_mode: lama}` + `$push tax_status_history` + `$unset tax_status_pending`
    (kalah balapan → 409); tanggal maju → `tax_status_pending` (bersyarat belum ada jadwal). Jejak
    `entity_tax_status_changed` / `entity_tax_status_scheduled` / `entity_tax_status_cancelled`.
    `apply_due_tax_status(today)` dipanggil saat aplikasi menyala (`bootstrap.run_bootstrap`) dan job harian baru
    `entity_tax_status_due` "Terapkan Perubahan Status PKP Terjadwal" 00.05 WIB. `default_tax_mode` tetap nilai yang
    dibaca mesin (K-08) — `get_effective_settings` tidak diubah.
  - **Layar** (Pengaturan › Perusahaan & Akun › Badan Usaha & Akses › Badan Usaha): wizard langkah 2 "Mata uang
    pembukuan" + "Tahun buku berakhir pada bulan" (pilihan dari registry, bawaan nilai grup; bila pengguna tidak bisa
    membaca pengaturan → keterangan "mengikuti pengaturan grup", tidak dikirim), "Penanggung insentif sales" dan nama
    templat bagan akun dibuang, sakelar **PT induk (konsolidasi)** + **Persen kepemilikan (%)**, NPWP diperiksa di
    tempat; langkah 3 tanpa "Skema penomoran", keterangan kode dokumen baru. Detail PT: "Awal tahun fiskal" dibuang;
    bagian **Pajak** (status, tanggal berlaku terakhir, **Ubah status PKP**, jadwal + **Batalkan jadwal** lewat
    konfirmasi baku), pop-up baku **Ubah Status PKP** (`TaxStatusDialog.jsx`, `FormModal`) dengan panel **Dampak**
    dari pratinjau server, tombol mati selama `can_apply` salah; bagian **Tahun buku & mata uang** (nilai + sumber +
    **Ubah** → `ProfileSettingDialog.jsx` memakai `SettingEditor` dan `PUT /api/config/values` lapisan PT, alasan wajib
    mengikuti registry); bagian **Grup & konsolidasi**. Label jejak tiga aksi baru di `auditLabels.js`.
- Data: field baru `business_entities.ownership_pct`, `tax_status_history`, `tax_status_pending` (tanpa indeks baru).
  Skrip `scripts/migrate_kpt1_profil_pt.py` (bawaan = `--dry-run`, hanya lapor; `--apply` hanya mengisi
  `ownership_pct: 100`; melaporkan tahun buku tersirat ≠ registry, `fiscal_year_start` tak terbaca, `currency` ≠
  registry, NPWP bukan 15/16 digit; tidak menyalin ke registry; argumen tak dikenal/bertentangan → keluar 2 sebelum
  menyentuh database). **Tidak dijalankan terhadap database mana pun selain database tiruan** (instruksi + H3);
  keluaran di lingkungan B: `bukti/KP-T1/skrip_migrasi_lingkungan_b.log`.
- Berkas berubah:

| Berkas | Isi |
|---|---|
| `backend/services/entity_context_service.py` | `ENTITY_DEFAULTS` baru; `BOOT_DEFAULT_KEYS = ("is_group",)` untuk `ensure_entity_defaults` (lihat Menyimpang 1) |
| `backend/services/entity_lifecycle_service.py` | `EDITABLE_FIELDS`, `ownership_of`, `uniform_entity`; blok `KP-T1` di akhir: `profile_settings`, `npwp_valid`, `tax_status_preview`, `change_tax_status`, `cancel_pending_tax_status`, `apply_due_tax_status`, `job_entity_tax_status_due` |
| `backend/services/entity_provisioning_service.py` | Validasi NPWP/kepemilikan/PT induk/PKP-lewat-PATCH; `_profile_value_or_400`, `_write_profile_layers`; `provisioning` tanpa `numbering_scheme` |
| `backend/routers/entities.py` | `_entity_out`/`_with_profile` di semua jawaban PT; PATCH meneruskan `default_tax_mode` ke validasi; tiga endpoint status PKP + `_guard_tax_scope` |
| `backend/schemas.py` | `BusinessEntityCreate` tanpa enam isian; `ownership_pct = Field(100, gt=0, le=100)`, `base_currency`, `fiscal_year_end_month`; `EntityTaxStatusIn` baru |
| `backend/services/entity_readiness_service.py` | Butir `fiscal_year` = "Tahun buku" dari registry |
| `backend/services/gl_service.py` | `consolidation`: `currency` dari `config_currency.base_currency` |
| `backend/services/scheduler_service.py` | Job `entity_tax_status_due` (blok ber-komentar `KP-T1`) + `_entity_tax_status_job` |
| `backend/bootstrap.py` | Benih PT tanpa isian mati (+ `ownership_pct: 100.0`); `apply_due_tax_status()` saat menyala |
| `scripts/migrate_kpt1_profil_pt.py` | Baru — skrip lapor / `--apply` |
| `frontend/src/features/settings/entities/EntityWizard.jsx`, `EntityDetailDrawer.jsx`, `entityApi.js` | Layar dan klien API |
| `frontend/src/features/settings/entities/TaxStatusDialog.jsx`, `ProfileSettingDialog.jsx` | Baru — dua pop-up baku |
| `frontend/src/config/auditLabels.js` | Label tiga aksi jejak |
| `backend/tests_mem/test_KPT1_profil_pt.py`, `test_KPT1_migrasi_profil_pt.py` | Baru — U1–U16 (+U9b, U12b, U16b) dan uji skrip |
| `backend/tests/test_bp_KPT1_profil_pt.py` | Baru — lapis A (lulus di MongoDB asli) |
| `frontend/src/features/__tests__/kpt1ProfilPt.test.js` | Baru — 8 uji komponen |
| `backend/backend_test_f0a_entity_context.py`, `backend/tests/test_f0cdef_multientity.py`, `backend/test_core_e1e2_poc.py` | Uji lama disesuaikan (lihat "Uji lama") |
| `ENTITY_REGISTRY.md`, `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`, `CODEBASE_MAP.md` | Field baru + tidak dipakai lagi; baris KP-T1; istilah "PT induk (konsolidasi)", "Persen kepemilikan", "Ubah status PKP", "Tahun buku & mata uang"; peta dibangkitkan ulang (`gen_codebase_map.py`) |

Berkas bersama yang disebut catatan penggabungan: `scheduler_service.py` (satu entri `JOBS` + satu fungsi, blok
`KP-T1`). `config_registry.py`, `config_service.py`, katalog pengaturan, `access_modules.py`, `AppViewRouter.jsx`,
`entity_scope.py` **tidak disentuh** (tanpa kunci, izin, menu baru → fixture katalog akses tidak perlu dibangkitkan).

- Commit: belum (instruksi: tanpa commit).
- Pengujian: lihat tabel uji di bawah.
- Bukti UI: belum diuji jalan di peramban (U17); uji komponen jest menggantikan sebagian.
- Fixture disiapkan langsung vs proses bisnis dijalankan: fixture = U7 (NPWP "abc"), U9 (pesanan `draft` Kanda), U13
  (NPWP dikosongkan), U9b (PT terarsip), uji skrip (3 PT bentuk lama); alur lewat API = U1–U6, U8, U10–U12, U12b, U14–U16.
- Dampak pada modul terkait: `/auth/context` tidak lagi membawa `currency` (tidak dibaca layar); laporan konsolidasi
  memakai mata uang registry per PT (di data bawaan sama: IDR); kesiapan PT "Tahun buku" selalu siap (registry selalu
  bernilai). `GET /api/entities` kini membaca dua kunci registry per baris (±6 kueri kecil per PT).
- Keterbatasan / yang belum diuji: U17 (peramban); lapis A (balapan di MongoDB asli, data acuan); skrip di data acuan.
- Status: implemented_pending_review.

## Uji penerimaan

`backend/tests_mem/test_KPT1_profil_pt.py` + `test_KPT1_migrasi_profil_pt.py` (lingkungan B). Merah = kedua berkas uji
dijalankan di salinan `git archive 4db17eb` (kode lama utuh): **19 gagal, 1 lulus (U7)**
(`bukti/KP-T1/tests_mem_KPT1_merah_kode_lama.log`; U11 dan U14 juga dijalankan sendiri supaya sebabnya tidak tertutup
efek U8 lama: `…_U11_U14_sendiri.log`). Hijau di kode baru: 20/20 (`…_hijau_kode_baru.log`).

| ID | Lapis | Merah di lama (sebab) | Hasil |
|---|---|---|---|
| U1 | B | ya — lima isian mati dikirim, tanpa `ownership_pct`/`base_currency` | Lulus — tanpa lima kunci; `100, 12, "IDR", "IDR"` |
| U2 | B | ya — dokumen PT menyimpan `numbering_scheme`/`incentive_payer` | Lulus |
| U3 | B | ya — `fiscal_year_end_month` diabaikan (12 ≠ 3) | Lulus — PT baru 3/USD, `ent_ksc` 12; `period_bounds` = (`2025-04-01`, `2026-03-31`); jawaban sumber `entity` |
| U4 | B | ya — 200, PT tercipta | Lulus — 400 "Bulan tutup tahun buku harus bulan 1 sampai 12 (1 = Januari, 12 = Desember)."; jumlah PT tetap |
| U5 | B | ya — 200 | Lulus — 400 pesan persis; NPWP tetap |
| U6 | B | ya — langkah tambahan: NPWP berspasi tersimpan tanpa dipangkas | Lulus — 200 ×3, tersimpan dipangkas |
| U7 | B | **tidak** (perilaku dipertahankan) | Lulus |
| U8 | B | ya — 200, Kanda menjadi PKP diam-diam | Lulus — 400 pesan persis; tetap `non_ppn` |
| U9 | B | ya — 404 (endpoint belum ada) | Lulus — `sekarang`; `sales_orders` count 1; `can_apply` benar; `documents_since` kosong |
| U10 | B | ya — 404 | Lulus — 400 "Alasan perubahan status PKP wajib diisi." |
| U11 | B | ya — 404 (sendiri) | Lulus — `ppn`, riwayat 1 baris `non_ppn→ppn`; tarif PPN efektif Kanda 0,0 → 12,0; KSC sama; jejak ada |
| U12 | B | ya — 404 | Lulus — terjadwal (status tetap `ppn`); `apply_due_tax_status(hari ini)` = 0, `(besok)` = 1; `non_ppn`; riwayat +1; jadwal hilang; ulang = 0 |
| U13 | B | ya — 404 | Lulus — 400 "PT yang menjadi PKP wajib mengisi NPWP."; pratinjau `can_apply` salah |
| U14 | B | ya — `ownership_pct` tidak tersimpan (KeyError) | Lulus — KSC `true/60`, Kanda `false/100`; `consolidation_service.summary` hanya baris Kanda |
| U15 | B | ya — 400 tetapi pesan "Tidak ada field yang bisa diubah" | Lulus — 400 ×2 pesan persis |
| U16 | B | ya — 404 | Lulus — Manajer Kosong 403 (pesan Z6), Tanpa Acuan (`entity.update`) 200 |
| U9b, U12b, U16b (tambahan) | B | ya — 404 | Lulus — tanggal mundur → `documents_since`; tanggal salah → 400; status sama → penghalang; PT terarsip → 409; batal jadwal 404/200; pratinjau & batal → 403 untuk Manajer Kosong |
| Skrip migrasi | B | ya — skrip belum ada | Lulus — argumen salah → 2; lapor tidak menulis; tulis 2 PT; isian lama tetap; registry tidak disalin; ulang 0 |
| U17 | layar | ya — 8/8 uji komponen gagal di `src` lama | Uji komponen 8/8 lulus (`bukti/KP-T1/jest_KPT1.log`); **uji jalan peramban belum** |
| Lapis A (tambahan) | A | — | `backend/tests/test_bp_KPT1_profil_pt.py`: data acuan tanpa isian mati; 6 "Ubah status PKP" paralel → tepat satu 200; skrip mode lapor tidak menulis — **lulus** di lingkungan A (backend `69cc4e3`, data acuan) |

`tests_mem` seluruhnya: sebelum **415 lulus / 2 dilewati / 3 xfail** → sesudah **435 / 2 / 3** (+20 uji KP-T1;
`bukti/KP-T1/tests_mem_sebelum_sesudah.log`).

Jest (`bukti/KP-T1/jest_KPT1.log`): suite baru 8/8 lulus, 8/8 gagal di `src` lama. Seluruh suite: HEAD 479 uji lulus,
35 suite gagal dimuat → KP-T1 487 lulus, 35 suite gagal dimuat (daftar sama; semuanya `@radix-ui`/`cmdk` tidak termuat
lokal — kendala lingkungan). `phase4R6.test.js` (uji lama detail PT) dijalankan dengan tiruan pemilih lokal: lulus di
HEAD dan di KP-T1. ESLint berkas layar yang berubah: bersih.

## Uji lama yang disesuaikan

| Berkas | Perubahan | Alasan |
|---|---|---|
| `backend/backend_test_f0a_entity_context.py` | Cek "isian diperkaya" kini `currency`, `base_currency`, `fiscal_year_end_month`, `is_group`, `ownership_pct` + cek tanpa isian mati (dulu menuntut `coa_template`, `incentive_payer`, `numbering_scheme`) | RISIKO di spesifikasi |
| `backend/tests/test_f0cdef_multientity.py` | `provisioning` tidak lagi memuat `numbering_scheme` | Isian mati dibuang dari jawaban |
| `backend/test_core_e1e2_poc.py` | E1.2a/E1.2b memakai NPWP 15 digit (dulu `"1"`) | Pola NPWP kini diperiksa lebih dulu dari keunikan — tanpa ini POC menerima 400, bukan 409 yang diuji |
| `scripts/entity_audit/probe_entity_flow.py` | **Tidak diubah** — skrip penjelajah (mencetak, tanpa tegas); langkah 7 kini mendapat 400 untuk `default_tax_mode` | Dicatat saja |

Tiga berkas di atas tidak dijalankan (butuh MongoDB asli / backend berjalan).

## Penjaga

| Penjaga | Sebelum (`4db17eb`) | Sesudah |
|---|---|---|
| `hitung_penjaga.sh` (16 penjaga) | auth 28 · ui_standard 23 · i18n 112 · create_modal 6 · page_tabs 1 · to_list 6 · entity_label 2 · lainnya 0 | **sama persis** (tidak ada yang naik; `verify_approval_queues` bergantung data, diabaikan) |
| `verify_role_gate_ui.py` | PASS 39 cek | PASS 39 cek (tanpa `roleIs(` baru) |
| `audit_config_wiring.py --strict` (salinan berjalur `$W`) | keluar 0, bersih | keluar 0, bersih |
| Statik lain (atomic_claim, status_history, numeric_bounds statik, compliance, nav_map, modal_dismiss, detail_modal, picker_portal, escape_layers, blocking_dialogs, derived_fields, notification_audience, role_label, view_aliases, desk_targets, ux_audit, line_scope, ref_unlink) | — | pelanggaran sama; hanya jumlah cek naik karena berkas baru. `verify_numeric_bounds` sempat HARD 3→4 (`ownership_pct` tanpa batas) → dibetulkan dengan `Field(gt=0, le=100)` |

Rincian: `bukti/KP-T1/penjaga_sebelum_sesudah.log`.

## Menyimpang dari blueprint

1. `ensure_entity_defaults` (dipanggil setiap aplikasi menyala) **tidak** mengisi `ownership_pct`
   (`BOOT_DEFAULT_KEYS = ("is_group",)`). Bila memakai `ENTITY_DEFAULTS` baru apa adanya, deploy akan menulis
   `ownership_pct: 100` ke data nyata tanpa keputusan pemilik — padahal spesifikasi menaruh pengisian itu di skrip
   migrasi (H3). Pembaca memakai bawaan 100 (`uniform_entity`/`ownership_of`).
2. Benih `seed_entities` ditulis tanpa enam isian mati, dengan `ownership_pct: 100.0` (hanya berlaku untuk database
   kosong).
3. `GET …/tax-status/preview` menerima `npwp` opsional (NPWP yang sedang diketik di pop-up), supaya `can_apply` benar
   saat PT tanpa NPWP menjadi PKP; `POST` menyimpan NPWP yang dikirim (sudah lolos pola).
4. Penghalang tambahan: bila sudah ada jadwal, perubahan baru ditolak 400 "Sudah ada perubahan status PKP terjadwal
   mulai {tanggal}. Batalkan jadwal itu dulu." (data hanya punya satu `tax_status_pending`; menimpa diam-diam akan
   menghilangkan jadwal lama). Lihat Keraguan.
5. `BusinessEntityCreate.ownership_pct = Field(100, gt=0, le=100)` (penjaga INV-NUM-01): `POST` dengan nilai di luar
   batas mendapat **422 skema**, bukan 400 berpesan; `PATCH` tetap 400 dengan pesan spesifikasi. Wizard memeriksa di
   tempat sehingga 422 tidak terlihat pengguna.
6. Pesan 400 nilai registry tak sah saat `POST` disusun dari entri registry (label, pilihan, batas) — mis. "Bulan tutup
   tahun buku harus bulan 1 sampai 12 (1 = Januari, 12 = Desember)." / "Mata uang pembukuan harus salah satu dari:
   Rupiah (IDR), Dolar AS (USD)." — bukan teks `ValueError` registry yang memuat kunci teknis (`finance.…`, L1).
7. Tambahan jawaban: `GET /api/entities/{id}` juga memuat `tax_status_history` (untuk "tanggal berlaku terakhir");
   jawaban arsip/aktifkan kembali ikut membawa nilai registry; butir `setting_layers` memuat `source` dan `effect`;
   baris riwayat dari jadwal memuat `scheduled_at`; jejak batal jadwal `entity_tax_status_cancelled`; jadwal yang
   diterapkan dicatat atas nama "Sistem (jadwal)".
8. Cakupan PT (N1) untuk tiga endpoint = penugasan aktif ∪ PT terarsip yang boleh dibaca (supaya PT terarsip mendapat
   409 sesuai spesifikasi, bukan 404); di luar itu 404.
9. Tombol **Ubah Status PKP** juga mati selama alasan kosong (spesifikasi: mati selama `can_apply` salah).
10. Kartu "Grup / Kas Bersama" konsolidasi memakai `base_currency(None)` (nilai grup), bukan teks "IDR".
11. Wizard: bila PT induk dicentang, `ownership_pct` dikirim 100 (isian dimatikan).

## Usulan koreksi spesifikasi (tidak diterapkan)

- U6 — langkah pertama memakai NPWP yang **sama** dengan benih `ent_ksc`, sehingga tidak divalidasi (tidak berubah) dan
  tidak membuktikan pola 15 digit bertitik. Teks pengganti kolom "Langkah":
  `PATCH` `{"data": {"npwp": "1234567890123456"}}` lalu `{"data": {"npwp": "01.234.567.8-901.000"}}` (uji yang ditulis
  menjalankan ketiganya, termasuk NPWP berspasi).
- Bagian Server: "`uniform_entity` membuang enam field mati di atas dan `currency`" dan "`BusinessEntityCreate` membuang
  enam field mati dan `currency`" — yang dimaksud lima isian mati + `currency` (enam). Teks pengganti: "membuang lima
  isian mati (`numbering_scheme`, `incentive_payer`, `coa_template`, `parent_entity_id`, `fiscal_year_start`) dan
  `currency`".

## Asumsi

- `ASUMSI` spesifikasi dipakai apa adanya: NPWP 15/16 digit tanpa digit cek; tanggal berlaku boleh mundur/hari ini/maju
  (mundur diterapkan saat itu, dokumen lama tidak dihitung ulang); dokumen di pratinjau = pesanan penjualan + pesanan
  pembelian; tidak ada layar yang membaca `currency` dari `/auth/context` (dicek); satu tingkat induk.
- `apply_due_tax_status` menerapkan jadwal juga pada PT yang sudah diarsipkan (status hanya dibaca; jadwal adalah
  keputusan yang sudah tercatat).
- Wizard tanpa akses baca pengaturan (403 `/config/effective`): tahun buku dan mata uang tidak dikirim → PT mengikuti
  nilai grup; bisa diubah dari detail PT oleh pemegang izin pengaturan keuangan.

## Hambatan lingkungan

- Jest lokal: 35 suite lama gagal dimuat (`@radix-ui`/`cmdk`), sama di HEAD dan KP-T1; suite baru meniru pemilih.
- **Catatan jujur:** saat membandingkan penjaga statik, satu putaran tanpa sengaja ikut menjalankan penjaga runtime
  (`verify_concurrency`, bagian runtime `verify_numeric_bounds`, `verify_state_machine`, `verify_home_kpi`,
  `verify_aging_fields`) terhadap backend :8001 dan database `backend/.env` di worktree. Penjaga itu memotret lalu
  memulihkan database (`_common.run_with_restore`). Backend tidak dinyalakan/dihentikan; skrip migrasi tidak dijalankan.
  Putaran berikutnya memakai `MONGO_URL`/`API_BASE` ke port mati.

## Penggabungan dan catatan lingkungan

Digabung di atas `9783875` (sesudah KP-T4, KF-T5, KF-T3). Satu konflik di `memory/PRD.md` (baris KP-T4 dan KP-T1 di
tempat yang sama — keduanya dipertahankan); `bootstrap.py`, `scheduler_service.py`, glosarium, `ENTITY_REGISTRY.md`
tergabung otomatis. `tests_mem` **474 → 494 lulus** / 2 / 3; jest seluruhnya 487/487.

- Lapis A di lingkungan A: `tests/test_bp_KPT1_profil_pt.py` lulus. Uji lama `tests/test_f0cdef_multientity.py` (bagian
  provisioning yang diubah unit ini) lulus; 7 uji lain di berkas itu gagal (isolasi inventaris `entity=None`, PO wajib grade,
  PO ke gudang khusus PT lain, tarif PPN 11 vs 12) — tidak menyentuh profil PT, berkas itu tidak termasuk gate.
- Saat bekerja, salinan kerja unit ini tanpa sengaja menjalankan lima penjaga runtime (`verify_concurrency`, bagian runtime
  `verify_numeric_bounds`, `verify_state_machine`, `verify_home_kpi`, `verify_aging_fields`) ke backend :8001 dan database
  lokal data acuan. Penjaga itu memotret lalu memulihkan database (`run_with_restore`); tidak ada skrip migrasi yang
  dijalankan. Gate KP-T4 yang berjalan pada periode yang sama memberi hasil yang konsisten (merah jalan 1 berpenyebab jelas,
  jalan 2 hijau).
- Keputusan sesuai rekomendasi (`00` §4.1), dicatat untuk pemilik: satu jadwal perubahan status PKP per PT — jadwal kedua
  ditolak "Sudah ada perubahan status PKP terjadwal … Batalkan jadwal itu dulu." (datanya hanya punya satu slot jadwal).
  Bila pemilik ingin aturan ini menjadi pengaturan, itu pekerjaan lanjutan.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli + backend `69cc4e3`), sesudah `restore_demo` (data acuan; tiga skrip seed yang
sama seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`). Satu jalan gate untuk tiga unit
yang digabung berturut-turut (KF-T5 `0da3656`, KF-T3 `dbe1633`·`9783875`, KP-T1 `69cc4e3`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `gate.sh --quick` | 14 FAIL | 16 | 0 | 2 (`config_wiring` + self-test, sejak KF-T2) |
| `gate.sh --ci` | 41 FAIL | 43 | 0 | 2 |

Hitungan penjaga statik berhitung (`scripts`… `verify_auth_coverage` 28, `verify_ui_standard` 23, `audit_i18n_id` 111,
`audit_create_modal` 6, `verify_page_tabs` 1, `verify_to_list_bound` 6, `verify_entity_label` 2, lainnya 0/PASS) sama
sebelum dan sesudah tiap unit; `verify_role_gate_ui` PASS; `audit_config_wiring --strict` bersih; `config_health` 0 rusak.
Jest (`src/config`, `src/features`, `src/hooks`, `src/components`) di HEAD akhir: 487/487 uji lulus; 34 suite gagal dimuat
karena `@radix-ui/primitive/is-development` (kendala lingkungan).

## Yang perlu direview

- Menyimpang 1 (pengisian `ownership_pct` saat menyala ditahan sampai skrip dijalankan pemilik) dan 4 (penghalang jadwal
  ganda) — keduanya pilihan agen.
- Lapis A dan U17 (uji jalan) belum dijalankan; skrip migrasi di data acuan/nyata = H3.

# KP-T2 — Kesiapan PT yang lengkap, langkah "Lengkapi PT", dan pemeriksaan sebelum arsip

- Commit awal: `0a91095` (dikerjakan) · digabung di atas `16b50fe` (sesudah KF-T4, PR-T8, PK-36)        - Commit akhir: `aea3cec`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KP-10, KP-22, KP-24 (spesifikasi `docs/blueprint/unit/KP-T2.md`; keputusan: jawaban pemilik butir 3
  dan 4; standar §3.1 Z1/Z2/Z6, §3.4 N1, §4 L1–L3/L5/L6, §5 D1/D4, §6)

## Cek ulang "Keadaan sekarang"

Spesifikasi dibaca pada `3132cc4`; dicek ulang pada `0a91095`. Semua butir masih berlaku; sebagian baris bergeser.

| # | Hasil di `0a91095` |
|---|---|
| 1 | Berlaku. 8 butir; `entity_readiness_service.py:58` (`items`, dari 49), `readiness` di `:39` |
| 2 | Berlaku. Baris gudang `view: "admin"` di `entity_readiness_service.py:73` (dari 64); `AppViewRouter.jsx:139` (`AdminView` = "Integrasi & Audit") dan `:174` (`md-warehouses`) tetap |
| 3 | Berlaku. `entity_readiness_service.py:50` (dari 41) — `{"entity_id": {"$in": [id, "all"]}}`, bank dan kas tidak dibedakan |
| 4 | Berlaku. `:72` "Master Data → Gudang", `:104` "Pengaturan → Template PDF", `:114` "ubah status PKP-nya" (dari 63/95/105) |
| 5 | Berlaku. Tidak ada butir pemetaan akun, periode, penanda tangan, akun kas, alamat, pengguna keuangan, termin (`readiness` `:39`) |
| 6 | Berlaku. `entity_provisioning_service.py:195` (`provision_entity`, dari 161): `insert_one` di `:214`, `seed_default_coa` di `:218` |
| 7 | Berlaku. `EntitiesAccessView.jsx:187` (`onCreated`: tutup wizard, pesan, buka detail) |
| 8 | Berlaku. `entity_lifecycle_service.py:54` (`DOC_SOURCES`, 17 koleksi), `:225` (`_open_documents`) |
| 9 | Berlaku. `:239` (`_open_balances`): agregasi semua `sales_orders` tanpa saring status; hutang/kas/karyawan tidak diperiksa |
| 10 | Berlaku. `:229` `to_list(2000)` |
| Sumber angka | `ar_aging_service.py:178` (dari 177), `vendor_bill_service.py:200`, `bank_service.py:78` (dari 76), `gl_mapping_service.py:95`, `closing_service.py:589` (dari 521), `entity_master_service.py:559`, `dependencies.py:100` (dari 101) |
| Dipertahankan | `archive_entity` `entity_lifecycle_service.py:324` (dari 315) — arsip bukan hapus, pratinjau, paksa + alasan (izin `entity.delete` sejak PR-T2, pesan PR-T5), CAS |
| `ASUMSI` pengalih PT | Fungsi pemilih PT di kepala layar adalah `App.js` `onSelectEntity` (bukan `useAppActions.js`); fungsi yang sama tersedia untuk komponen lewat `EntityScopeContext.pickEntity` (`App.js:286`) → dipakai; petunjuk cadangan "Pilih {nama PT} di pemilih PT." tidak diperlukan |
| Unit selesai terkait | KP-T1: profil/kesiapan lama; PR-T3 S2/S5 (kesiapan butuh `entity.view`, baris rujukan 14 kunci) — **tidak diperluas**; PR-T5 (pesan 403 modul "Badan Usaha (PT)") — diikuti |

## KP-10 / KP-24 — kesiapan PT 16 butir, langkah "Lengkapi PT", penyiapan yang bisa diulang

- Berlaku di HEAD: ya (tabel di atas; bukti merah U1–U12, U18b).
- Akar masalah: daftar kesiapan hanya 8 butir dengan tautan/teks basi; PT disimpan lebih dulu sebelum bagan akun dan
  penanda lapisan sehingga kegagalan meninggalkan PT setengah jadi tanpa jalan mengulang; wizard berhenti di pesan.
- Perubahan perilaku (sebelum → sesudah):
  - **Kesiapan** (`entity_readiness_service.readiness`): 16 butir berurutan persis tabel spesifikasi
    (`provisioning`…`signers`), bentuk butir tetap + `tab` (hanya bila ada), ringkasan tidak berubah. Butir `bank_accounts`
    dipecah `bank_account`/`cash_account` (milik PT saja, `is_active ≠ false`, bukan `"all"`); `fiscal_year` dibuang.
    `finance_user` membaca `permission_matrix()` (`cash.create`/`*`) + penugasan (`home_entity_id`, `allowed_entity_ids`,
    atau peran bersifat lintas PT `CROSS_ENTITY_ROLES`) — tanpa nama peran (Z2). `gl_mappings` = jumlah baris wajib
    ber-status ≠ ok dari `list_mappings` (angka sama dengan layar Pemetaan Akun); `period` = `status_for_date(today_wib())`;
    `payment_term` = `default_payment_term_code(id)` → `resolve_row("payment-terms", …)`; `branding` = logo/kop gambar
    sungguhan atau `logo_url`; `signers` = tanda tangan ber-nama. Teks `detail`/`how_to` persis tabel spesifikasi; butir lain
    berbahasa "PT" (L2).
  - **Penyiapan** (`entity_provisioning_service`): validasi → `seed_default_coa()` (gagal → **500** "Bagan akun bersama
    gagal disiapkan, jadi PT belum dibuat. Coba simpan lagi."; PT tidak lahir) → simpan PT dengan
    `provisioning: {coa: true, config_layer: false, group_partners: false, at}` → `run_provisioning_steps` (bagan akun,
    penanda `system_settings{scope: id}` lewat upsert, `sync_group_entity_suppliers`; tiap langkah aman diulang, yang
    berhasil ditandai `true`, kegagalan dilaporkan di `errors` tanpa membatalkan PT). Cache status PT dibuang saat PT
    dibuat (lihat Menyimpang 4).
  - **`POST /api/entities/{id}/provisioning/retry`** · izin `entity.update` (pesan Z6 "…mengulang penyiapan PT… 'Badan
    Usaha (PT)'") · PT dalam penugasan (N1, sama dengan endpoint status PKP) · 404 PT tidak ada · 409 "PT ini sudah
    diarsipkan." · jawaban `{entity_id, provisioning, errors, readiness}` · jejak `entity_provisioning_retried`.
  - **Layar** (Pengaturan › Perusahaan & Akun › Badan Usaha & Akses): komponen baru `EntityCompletionSteps.jsx`
    — judul **Lengkapi PT**, ringkasan "{siap} dari {total} hal sudah siap", langkah bernomor (tanda, label, detail,
    petunjuk bila belum siap), **Lengkapi** (ganti PT aktif dulu → buka `view` lewat jalur navigasi baku, preset `{tab}`;
    untuk hub Badan Usaha & Akses juga membuka detail PT itu), **Ulangi penyiapan** pada baris penyiapan awal yang belum
    siap (bila boleh ubah PT); memuat = kerangka abu-abu, kosong = "Pilih PT untuk melihat daftar kesiapannya.".
    Wizard: sesudah simpan pindah ke langkah 5 **Lengkapi PT** (tidak menutup), "Langkah ini bisa dilanjutkan kapan saja
    dari tab Kesiapan.", tombol **Selesai** (tutup + buka detail). Detail PT (bagian Kesiapan) dan tab Kesiapan memakai
    komponen yang sama; judul panel **Kesiapan PT**.
- Data: field baru `business_entities.provisioning` (tanpa koleksi/indeks baru, tanpa migrasi; PT lama dihitung dari data).

## KP-22 — pemeriksaan sebelum arsip

- Berlaku di HEAD: ya (bukti merah U13–U16).
- Akar masalah: dokumen terbuka hanya 17 koleksi dan dipotong 2.000 baris; piutang dijumlah dari semua pesanan termasuk
  batal; hutang, kas/bank, karyawan tidak diperiksa; layar tidak bisa menampilkan daftar yang sama dengan server.
- Perubahan perilaku (sebelum → sesudah):
  - `ARCHIVE_EXTRA_SOURCES` (uang muka, LPJ uang muka, SPK makloon, permintaan pembelian, pesanan khusus, penerimaan
    barang) ikut `_open_documents` — **tidak** ikut kunci kode dokumen. `_open_documents` = `count_documents` +
    `limit(3)` contoh (D4).
  - `_open_balances`: `piutang` dari `aging_report(entity_id)["totals"]["total"]`; `hutang` = Σ
    `bill_financials(b)["outstanding"]` tagihan `posted`; `kas_bank` = Σ |saldo| tiap rekening PT dengan rumus
    `bank_service._balance` atas mutasi `bank_service._txns_for` (= angka layar Rekening & Saldo); `antar_pt` (label
    "Saldo antar-PT") dan `stok` seperti sebelumnya.
  - `deactivation_impact` + `employees` (`hr_employees` bukan `resigned`) dengan penghalang "{n} karyawan masih terdaftar
    di PT ini — pindahkan atau akhiri dulu", + `checks` (pengguna, dokumen, saldo, karyawan, periode: `{key, label, ok,
    detail}`; nominal `core_utils.rupiah`). Penghalang dokumen kini menyebut jenisnya: "{n} dokumen masih terbuka (Uang
    muka 1, …) — …". Cara memaksa tidak diubah.
  - `ArchiveEntityDialog.jsx`: daftar centang **Sebelum mengarsipkan** dari `checks`; baris belum beres menyebut jumlah
    dan contoh (dokumen per jenis + nomor; saldo per jenis `formatCurrency`); kartu "Karyawan terdaftar"; tombol
    **Arsipkan** tetap mati selama ada penghalang kecuali dipaksa dengan alasan.

## Berkas berubah

| Berkas | Isi |
|---|---|
| `backend/services/entity_readiness_service.py` | 16 butir + pembaca per butir (blok `KP-T2`) |
| `backend/services/entity_provisioning_service.py` | Urutan `provision_entity`; `run_provisioning_steps`, `COA_FAILED_MESSAGE` (blok `KP-T2`) |
| `backend/services/entity_lifecycle_service.py` | `ARCHIVE_EXTRA_SOURCES`, `_open_documents`, `_open_balances`, `_balance_text`, `_archive_checks`, `employees`/`checks` |
| `backend/routers/entities.py` | `POST /entities/{id}/provisioning/retry`, `_ULANG_DITOLAK` (blok `KP-T2` di akhir) |
| `frontend/src/features/settings/entities/EntityCompletionSteps.jsx` | Baru — `EntityCompletionSteps`, `completionPreset`, `WizardCompletionStep` |
| `frontend/src/features/settings/entities/EntityWizard.jsx`, `EntitiesAccessView.jsx`, `EntityDetailDrawer.jsx`, `EntityReadinessPanel.jsx`, `ArchiveEntityDialog.jsx`, `entityApi.js` | Langkah 5, preset navigasi, panel/bagian kesiapan, daftar centang arsip, `retryProvisioning` |
| `frontend/src/config/auditLabels.js` | Label `entity_provisioning_retried` |
| `backend/tests_mem/test_KPT2_kesiapan_arsip.py` | Baru — U1–U17 (+U12b, U18b) |
| `backend/tests/test_bp_KPT2_kesiapan_arsip.py` | Baru — lapis A (ditulis, tidak dijalankan) |
| `frontend/src/features/__tests__/kpt2LengkapiPt.test.js` | Baru — 6 uji komponen |
| `backend/test_core_e1e2_poc.py` | E1.9 menuntut 16 butir baru (lihat "Uji lama") |
| `ENTITY_REGISTRY.md`, `memory/PRD.md`, `CODEBASE_MAP.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` | Field `provisioning`; baris KP-T2; peta dibangkitkan ulang (`gen_codebase_map.py`); istilah "Lengkapi PT / Kesiapan PT", "Pengguna keuangan", "Sebelum mengarsipkan" |

Berkas bersama: `routers/entities.py` (satu endpoint di akhir), tiga layanan PT, layar `features/settings/entities/*` —
perubahan ber-komentar `KP-T2`. **Tidak disentuh**: `access_modules.py`, `permissions_config.py`, katalog/registry
pengaturan, `AppViewRouter.jsx`, `App.js`, layar Peran & Hak Akses / Akun & Akses (PR-T6), Pusat Pengaturan (KF-T4).
Tanpa izin/kunci baru → `test_KFT1_izin_pengaturan.py`, fixture katalog akses, pola PR-T9 tidak perlu disesuaikan.

- Commit: belum.
- Fixture disiapkan langsung vs proses bisnis dijalankan: fixture = rekening U3/U4/U15, periode U6, akun U8 +
  penonaktifan sementara Admin/Manajer, `document_branding` U9, penanda dihapus U11, pelanggan + pesanan U13, tagihan U14,
  uang muka + karyawan U16; alur lewat API = U1, U2, U5, U7 (`PUT /api/config/values`), U10–U12, U12b, U18b, U16
  (`DELETE`), U17.
- Dampak pada modul terkait: PT lama turun persentase kesiapannya (RISIKO spesifikasi — disengaja); di lingkungan B PT
  benih KSC/Kanda tidak punya penanda `system_settings{scope}` sehingga butir "Penyiapan awal" merah sampai **Ulangi
  penyiapan** ditekan (data acuan lingkungan A belum dicek — lapis A mencetaknya). `GET /api/entities?with_readiness=true`
  kini membaca pemetaan akun, periode, termin, matriks izin per PT (±10 kueri kecil tambahan per baris); pratinjau arsip
  menjalankan umur piutang PT.
- Keterbatasan / yang belum diuji: U18 uji jalan peramban; lapis A; gate.
- Status: implemented_pending_review.

## Uji penerimaan

`backend/tests_mem/test_KPT2_kesiapan_arsip.py` (lingkungan B). Merah = berkas uji akhir dijalankan dengan
`routers/entities.py` + tiga layanan PT dari `git show HEAD:<berkas>` (dikembalikan sesudahnya): **19 gagal / 19**
(`bukti/KP-T2/tests_mem_KPT2_merah_kode_lama.log`). Hijau di kode baru: **19/19** (`…_hijau_kode_baru.log`).

| ID | Lapis | Merah di lama (sebab) | Hasil |
|---|---|---|---|
| U1 | B | ya — 8 butir (`assert 8 == 16`) | Lulus — 16, urutan persis, tanpa `bank_accounts`/`fiscal_year` |
| U2 | B | ya — `'admin' == 'md-warehouses'` | Lulus — `md-warehouses`; tidak ada `view: "admin"`; `tab` hub benar |
| U3 | B | ya — butir `cash_account` tidak ada | Lulus — kas siap, bank tidak |
| U4 | B | ya — butir `bank_account` tidak ada (dulu `"all"` ikut terhitung) | Lulus — rekening grup tidak dihitung |
| U5 | B | ya — butir `gl_mappings` tidak ada | Lulus — `count` = baris wajib ≠ ok dari `GET /api/gl/account-mappings`; KSC tidak ikut berubah |
| U6 | B | ya — butir `period` tidak ada | Lulus — Kanda salah, KSC benar |
| U7 | B | ya — butir `payment_term` tidak ada | Lulus — Kanda salah + "TIDAKADA" di detail; KSC siap |
| U8 | B | ya — butir `finance_user` tidak ada | Lulus — salah → benar (`count` 1) |
| U9 | B | ya — butir `signers` tidak ada | Lulus — salah → benar ("Budi") |
| U10 | B | ya — PT tetap tersimpan (`4 == 3`) | Lulus — galat 500, jumlah PT tetap, tanpa PT "KPTDGAGAL" |
| U11 | B | ya — `provisioning` tidak tercatat (`None is True`) | Lulus — salah → retry `config_layer` benar → siap |
| U12 | B | ya — 404 (endpoint belum ada) | Lulus — 200 ×2; penanda = 1; pemasok entitas grup tidak bertambah |
| U12b (tambahan) | B | ya — 404 | Lulus — Manajer Kosong 403 (pesan Z6, tanpa `entity.`); Tanpa Acuan `entity.update` 200 di PT-nya, 404 di PT lain; PT tidak ada 404 |
| U13 | B | ya — piutang Rp1.000.000 dari pesanan batal | Lulus — tanpa `piutang`; pembanding: pesanan terkonfirmasi Rp400.000 → piutang 400.000 |
| U14 | B | ya — tanpa `hutang` | Lulus — `hutang` 300.000 (500.000 − 200.000); `can_archive` salah |
| U15 | B | ya — tanpa `kas_bank` | Lulus — `kas_bank` 250.000 (lihat catatan hitungan di uji) |
| U16 | B | ya — tanpa "Uang muka" | Lulus — "Uang muka" 1 (`KANDA/PD-90001`); `employees` 1; `checks` 5 kelompok, saldo "Rp 300.000"; DELETE 409 dengan penghalang dokumen (menyebut Uang muka) + karyawan |
| U17 | B | sebagian — paksa arsip **lulus** di lama (perilaku dipertahankan); merah hanya di tambahan retry → 404 | Lulus — 200, `archived`; retry PT terarsip → 409 "PT ini sudah diarsipkan." |
| U18b (tambahan, sisi server U18) | B | ya — 403 "Badan usaha … tidak ada" (cache status 20 detik) | Lulus — permintaan ber-`X-Entity-Id` PT baru langsung 200 |
| U18 | layar | ya — 3/6 uji komponen layar gagal di layar lama (wizard tanpa langkah 5, judul panel lama, tanpa daftar centang); suite tidak termuat di `src` lama (komponen belum ada) | Uji komponen 6/6 lulus (`bukti/KP-T2/jest_KPT2.log`): wizard → langkah 5 → **Lengkapi** Gudang memanggil pemilih PT (PT baru) lalu membuka `md-warehouses`; **uji jalan peramban belum** |
| Lapis A (tambahan) | A | — | `backend/tests/test_bp_KPT2_kesiapan_arsip.py`: 16 butir di data acuan (dicetak), 6 retry bersamaan → semua 200 + penanda tetap 1, pratinjau arsip Kanda tidak menulis — **lulus** di lingkungan A (backend `aea3cec`, data acuan) |

`tests_mem` seluruhnya: sebelum **545 lulus / 2 dilewati / 3 xfail** → sesudah **564 / 2 / 3** (+19;
`bukti/KP-T2/tests_mem_sebelum_sesudah.log`).

Jest (`bukti/KP-T2/jest_KPT2.log`): suite baru `kpt2LengkapiPt` 6/6 lulus; di `src` lama gagal dimuat (komponen belum
ada), dan dengan hanya komponen baru disalin ke `src` lama 3/6 gagal (layar lama). `kpt1ProfilPt` 8/8 dan `phase4R6`
6/6 (tiruan pemilih lokal) tetap lulus. Seluruh suite (`src/features|config|hooks|components`): HEAD **514 lulus, 35
suite gagal dimuat** → KP-T2 **520 lulus, 35 suite gagal dimuat** (daftar sama; `@radix-ui`/`cmdk` tidak termuat lokal).
ESLint berkas layar yang berubah: bersih.

## Uji lama yang disesuaikan

| Berkas | Perubahan | Alasan |
|---|---|---|
| `backend/test_core_e1e2_poc.py` | E1.9 menuntut 16 kunci baru (dulu 8 kunci termasuk `bank_accounts`, `fiscal_year`) | Perilaku yang sengaja diubah (U1). Tidak dijalankan (butuh backend + MongoDB asli) |

## Penjaga

| Penjaga | Sebelum (`0a91095`) | Sesudah |
|---|---|---|
| `hitung_penjaga.sh` (16) | auth 28 · ui_standard 23 · i18n 111 · create_modal 6 · page_tabs 1 · to_list 6 · entity_label 2 · lainnya 0/PASS | **sama persis** (`verify_approval_queues` bergantung data, diabaikan) |
| `verify_ui_standard` rincian | font<12 6944 · hex 16820 · btn_custom 783 · btn_force 580 | 6932 · 16783 · 781 · 577 (semua turun) |
| `verify_page_tabs` | 1 (`InventoryStockView.jsx`) | 1 — sempat 2 karena pemilih PT di panel Kesiapan memakai tombol-toggle → diganti `FilterChips` |
| `verify_role_gate_ui.py` | PASS 33 cek | PASS 33 cek |
| `audit_config_wiring.py --strict` (salinan berjalur `$W`) | keluar 0, bersih | keluar 0, bersih |
| Statik lain (modal_dismiss, blocking_dialogs, escape_layers, role_label, permission_checked, derived_fields, ux_audit, nav_map, view_aliases, desk_targets, detail_modal, picker_portal, atomic_claim, status_history, notification_audience, ref_unlink, line_scope) | — | keluaran sama; hanya jumlah berkas diperiksa naik (berkas baru) |
| Batas ukuran berkas (KN_00 GATE 2, `CODEBASE_MAP.md`) | 20 berkas | 20 — `EntityWizard.jsx` 499 baris (langkah 5 di `EntityCompletionSteps.jsx`); `EntityDetailDrawer.jsx` turun 523 → 510 (sudah lewat batas sebelumnya) |

Rincian: `bukti/KP-T2/penjaga_sebelum_sesudah.log`. Penjaga runtime (`verify_concurrency`, `verify_state_machine`,
`verify_home_kpi`, bagian runtime `verify_numeric_bounds`) tidak dijalankan.

## Menyimpang dari blueprint

1. Teks butir yang tidak ada di tabel teks spesifikasi (`users`, `doc_prefix`, `prices`, `opening_balance`, dan semua
   teks "siap") dipilih agen, berbahasa "PT" (L2). `tax` dengan status kosong: "Status pajak belum ditetapkan".
2. U10: galat = **500** berpesan manusia (spesifikasi: "Galat").
3. Jawaban `POST /api/entities` → `provisioning` menambah `steps` dan `errors`; `config_override_created` kini hasil
   sebenarnya. Jawaban retry menambah `errors`.
4. **Tambahan perlu untuk U18:** `provision_entity` memanggil `invalidate_status_cache()` — tanpa itu permintaan
   ber-`X-Entity-Id` PT baru ditolak 403 "tidak ada" sampai 20 detik (U18b).
5. Retry juga memeriksa penugasan PT (N1, `_guard_tax_scope` milik KP-T1) → PT di luar penugasan = 404.
6. Penghalang dokumen menyebut jenis + jumlah (supaya 409 U16 bisa dikenali "dengan dua penghalang itu"); label
   `antar_pt` mengikuti tabel spesifikasi ("Saldo antar-PT").
7. `kas_bank` memakai mutasi `bank_service._txns_for` (bukan hanya `account_id` tertaut) supaya angkanya sama dengan layar
   Rekening & Saldo: bila rekening itu satu-satunya akun jenis kasnya, transaksi kas tanpa rekening milik PT ikut. Karena
   seed Kanda punya satu transaksi kas tanpa rekening (Rp5.000.000), uji U15 memakai dua akun kas (lihat usulan koreksi).
8. Dialog arsip: daftar penghalang teks, kartu "Dokumen terbuka", dan kartu "Saldo yang masih hidup" digabung ke daftar
   centang; tambah kartu "Karyawan terdaftar".
9. Panel Kesiapan PT: pemilih PT memakai `FilterChips` (INV-UI-12) dan pilihan awal = PT aktif; warna lewat token `kn-*`.
10. Wizard: langkah 1–4 terkunci sesudah simpan; tombol tutup/klik latar sesudah simpan = **Selesai**. Preset navigasi
    `{tab, entity_id}` membuka detail PT hanya bila PT itu PT aktif (preset diterapkan ulang saat layar dipasang ulang).
11. `WizardCompletionStep` diletakkan di `EntityCompletionSteps.jsx` supaya `EntityWizard.jsx` ≤ 500 baris (GATE 2).
12. Glosarium diperbarui (`02_STANDAR.md` §7; tidak disebut di "Dokumen ikut berubah"); lapis A ditulis walau spesifikasi
    tidak punya baris lapis A.

## Usulan koreksi spesifikasi (tidak diterapkan)

- U15 — "tanpa transaksi" belum cukup karena saldo rekening ikut menyerap transaksi kas tanpa rekening milik PT bila
  rekening itu satu-satunya akun jenis kasnya. Teks pengganti kolom "Persiapan": "`ent_kanda`: `bank_accounts`
  `{account_type: "cash", opening_balance: 250000}` tanpa transaksi bertaut, dan Kanda punya akun kas lain bersaldo 0
  (transaksi kas tanpa rekening tidak dibebankan ke akun mana pun)".
- `ASUMSI` pengalih PT — teks pengganti: "pengalih PT aktif = `App.js` `onSelectEntity`, tersedia untuk komponen lewat
  `EntityScopeContext.pickEntity`".

## Asumsi

- `ASUMSI` spesifikasi dipakai apa adanya: `cash.create` menandai pengguna keuangan; rekening/akun kas `"all"` bukan milik
  PT; hutang hidup = tagihan `posted` bersisa; status "terbuka" = di luar `CLOSED_STATUSES` (RISIKO dicatat di kode).
- "Peran lintas PT" = sifat peran `CROSS_ENTITY_ROLES` (diatur di Peran & Hak Akses), bukan nama peran.
- Langkah penyiapan yang sudah pernah berhasil tidak dicabut oleh kegagalan berikutnya.

## Hambatan lingkungan

- Jest lokal: 35 suite lama gagal dimuat (`@radix-ui`/`cmdk`), sama di HEAD dan KP-T2; suite baru meniru pemilih dan
  konteks navigasi/PT.
- U18 belum diuji jalan di peramban; lapis A dan gate dijalankan saat penggabungan. Tidak ada skrip/migrasi yang
  dijalankan terhadap database mana pun selain database tiruan (H3: tidak ada migrasi di unit ini).

## Penggabungan

Digabung di atas `16b50fe` tanpa konflik teks (glosarium dan `PRD.md` otomatis); `CODEBASE_MAP.md` dibangkitkan ulang.
Satu uji disesuaikan: **U7** menulis kode termin `TIDAKADA` lewat `PUT /api/config/values`, padahal sejak KF-T4 nilai rujukan
yang tidak ada di master ditolak 400 saat disimpan. Keadaan "termin bawaan PT tidak ada di master" (baris master dihapus
sesudah disimpan, atau nilai lama sebelum validasi) kini ditiru di pembacanya (`default_payment_term_code` di-monkeypatch
untuk `ent_kanda`); harapan uji tidak berubah. `tests_mem` **600 → 619 lulus** / 2 / 3; jest `kpt2LengkapiPt` + `kpt1ProfilPt`
+ `src/config` 106/106. Lapis A `test_bp_KPT2` + `test_bp_KPT1` 6 lulus. POC `backend/test_core_e1e2_poc.py` (tidak termasuk
gate) masih gagal di dua butir E1.10a/E1.10b (401 "Session tidak valid" dari akun sales Kanda) — tidak menyentuh kesiapan PT.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli + backend `1392969`), sesudah `restore_demo` (data acuan; tiga skrip seed yang
sama seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`). Satu jalan gate untuk tiga unit
yang digabung berturut-turut (PK-36 `16b50fe`, KP-T2 `aea3cec`, PR-T6 `1392969`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `gate.sh --quick` | 14 FAIL | 16 | 0 | 2 (`config_wiring` + self-test, sejak KF-T2) |
| `gate.sh --ci` | 41 FAIL | 43 | 0 | 2 |

Hitungan penjaga statik berhitung sesudah ketiga unit: `verify_ui_standard` 23 → 15 (PR-T6), lainnya sama;
`verify_role_gate_ui` PASS (garis dasar 19 → 18 gerbang), `verify_permission_checked` 580 PASS, `verify_config_text` PASS,
`audit_config_wiring --strict` bersih, `verify_access_catalog_nav` 0. Jest seluruhnya di HEAD akhir 551/551.

## Yang perlu direview

- **Butir "Penyiapan awal" bergantung pada `system_settings{scope: id}`** (aturan spesifikasi), padahal
  `config_resolver.clear_layer` ("Kembalikan ke global", KF) sengaja menghapus dokumen `system_settings` PT yang kosong —
  penanda ikut hilang dan butir kembali merah walau tidak ada yang rusak; PT benih (lingkungan B) juga tanpa penanda.
  "Ulangi penyiapan" membuatnya lagi (aman). Pilihan: biarkan (sekarang), atau ubah aturan butir (mis. cukup bagan akun +
  catatan `provisioning.config_layer`) — keputusan reviewer/pemilik.
- Temuan di luar lingkup: `users.allowed_entity_ids` tersimpan untuk peran lintas PT tidak bertambah saat PT baru dibuat,
  sehingga `request_context.resolve_from_user` (stempel jejak, kunci-tulis, `active_entity_or`) jatuh ke PT utama untuk
  permintaan ber-PT baru sampai daftar itu diperbarui; pembaca `entity_ctx` tidak terdampak. Sudah ada sebelum KP-T2,
  hanya lebih terlihat lewat tombol **Lengkapi**.
- **Lengkapi** selalu mengganti PT aktif; bawaannya hanya Admin/Manajer (lintas PT) yang memegang `entity.view`.
- Menyimpang 4 (buang cache status saat PT dibuat) dan 7 (rumus saldo kas & bank) — pilihan agen.

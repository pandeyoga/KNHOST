# KM-T5 — Kartu "Capaian & Insentif Saya" untuk sales; layar insentif lama dipindah dan dihapus

- Commit awal: `fee66fe` (worktree kerja W, basis B)        - Commit akhir: `7183e4f`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: — (fitur; spesifikasi `docs/blueprint/unit/KM-T5.md`; keputusan K-22, K-46)
- Risiko rendah → satu serah-terima. **Titik henti H5 dipatuhi**: tidak ada nilai sakelar `hr.payroll_commission_mode` PT
  yang diubah di kode, seed, atau data (uji memakai `config_resolver.set_value` di database tiruan). **H3**: tanpa skrip data.

## Cek ulang "Keadaan sekarang" (spesifikasi `3132cc4`, diperiksa di `fee66fe`)

| Butir spesifikasi | Hasil di basis B |
|---|---|
| Beranda Sales "Komisi MTD" `SalesHome.jsx:112`, rincian `:145`, tren `:183`; sumber `home_service.py:57` (`compute_commission`), `:102` (`mtd_accrual`) | Berlaku — `:112`, `:145`, `:183`; `home_service.py:57`, `mtd_accrual` `:105` |
| HP sales memanggil mesin `MobileCollectionTargets.jsx:153` (`sales/commission`) | Berlaku, bergeser — `:162` (+ `commission-history` `:163`, isian `type="month"` peramban) |
| Beranda admin "Insentif Sales" = Σ mesin semua sales `home_service.py:468` (`payout`), `AdminHome.jsx:175` | Berlaku, bergeser — `:484`–`:487`, `incentive_payout` `:508`; `AdminHome.jsx:168` (sub-teks tetap "Estimasi bulan ini") |
| Tiga tempat lama: CRM › "Kinerja Sales"/"Skema (Arsip)" `CrmView.jsx:25/26`; Pengaturan › Penjualan › "Komisi & Insentif" `hubTabs.js:254`, dirender `AppViewRouter.jsx:304` | **Bergeser (MN-T1, KM-T1, KM-T3)** — CRM tinggal tiga sub-tab; ketiganya kini tab SDM › Kinerja & Insentif: `hubTabs.js:224` (`sales-performance`, peran A M **S**), `:229` (`incentive-rates`, label "Komisi Otomatis"), `:233` (`incentive-schemes`, `hidden` KM-T3, dibuka tautan "Skema insentif lama (arsip)" `IncentiveSheetsView.jsx:172`); router `:355`, `:440`, `:441`. `HUB_TABS["settings-sales"]` sudah tanpa `incentive-rates` |
| Isi layar lama `SalesForceDashboard.jsx:104` (`sf-set-target`), `:138` (`sf-incentive-gl`); `IncentiveSchemeEditor.jsx:16`, "Tipe Periode" `:196`; `IncentiveRatesEditor.jsx:72` | Berlaku, bergeser — `:110`, `:144`; `:16`, `:196`; `:69` (KM-T4: tanpa "Satuan") |
| Endpoint lama `crm.py:260/266/293/299/368/423`, `incentive_rates.py:43`; sales lain lewat `role_in` `crm.py:254` | Bergeser — `get_sales_kpi` `:411`, `get_leaderboard` `:417`, `get_commission` `:444`, `…history` `:450`, `create_target` `:533`, `create_incentive` `:577`, `list_rates` `:50`. **`role_in` sudah tidak berlaku** (PR-T4: `_kpi_scope` `:385` memakai `own_scoped` / `order.view_sales_kpi`) |
| Daftar sales hanya peran persis `sales` `crm.py:48`, `sales_force_service.py:456` | **Sebagian bergeser** — PR-T4: `roles_in_category("sales")` (`crm.py:57`, `sales_force_service.py:460`): peran kustom beracuan sales sudah ikut (U8 bagian `/api/sales-users` hijau di kode lama), tetapi papan peringkat masih semua akun sales seluruh grup (bukan daftar PT) → diganti `sales_roster` |
| Profil Saya memuat kartu slip, belum ada kartu insentif `EmployeeSelfService.jsx:9` | Berlaku — impor `:9`, render `:218` (kartu slip PY-T5) |
| (tambahan) HP Beranda `MobileSalesHome.jsx` membaca `commission` dari `/api/home/sales` (Komisi MTD, Proyeksi, Capaian Target, rincian, tren) | Ditemukan — tidak disebut spesifikasi; ikut disesuaikan (lihat "Menyimpang" 3) |

## Perubahan

- **Server**
  - `GET /api/incentive/me` (`routers/incentive.py`, `services/incentive_me.py` baru) — cukup login (`LOGIN_ONLY`
    milik sendiri); PT = PT aktif, sales = pelaku (`sales_id` di kueri diabaikan). `achievement` dari pengumpul Capaian
    KM-T2 (`incentive_achievement.achievement`, margin tidak diminta; tanpa sisa piutang), `sheets` = lembar `approved`/
    `paid` PT itu dengan `pay_period` = `period`, hanya baris pelaku (+ potret lima angka), `auto_commission` hanya bila
    mode PT bukan `sheet`/`off`. Periode salah → 400 "Periode harus satu bulan, contoh: 2026-10.".
  - `sales_home`: `incentive_mode`; `sheet`/`off` → mesin tidak dipanggil (`commission` null, `history` [], KPI dari
    `sales_kpi`). `admin_home`: `incentive_payout` per PT (`sheet` → `incentive_payroll.belum_dibayar`) +
    `incentive_payout_label`. `/api/sales-users`, papan peringkat, `my-rank` → `sales_roster` PT (Semua PT = gabungan).
    `/api/sales/commission[-history]` → 409 kalimat spesifikasi untuk PT `sheet`/`off`. `GET /api/sales/incentive/gl-status`
    + `mode`, `estimate` (`gl_service.incentive_accrual_estimate` — satu pembaca dengan akrual manual). `GET
    /api/incentive/targets` + `commission_mode(s)`. **`GET`/`POST /api/sales-targets` dihapus** (pencarian: tanpa pemanggil di
    `frontend/src` sesudah tiga layar lama dihapus — U11).
  - Katalog akses: `incentive-rates`, `sales-performance`, `incentive-schemes` dicabut dari `nav` semua modul; `hrd` +
    `hr-kpi-hub` dicabut dari modul `penjualan` dan `sales_force` (hanya dibuka lewat tab itu); `VIEW_RESOURCE_OVERRIDES`
    kedua id dihapus. `nav` modul `incentive` tidak berubah. Fixture akses dibangkitkan ulang.
- **Layar**
  - `features/incentive/MyIncentiveCard.jsx` (baru) — kartu spesifikasi; dipasang di Beranda Sales (semua mode; di PT
    `sheet`/`off` menggantikan Komisi MTD, Proyeksi Bulan, Capaian Target Penagihan, kartu progres penagihan, rincian & tren
    komisi), Profil Saya (di bawah slip, `hideWhenEmpty`), HP Penagihan & Target › tab "Target & Insentif" (kartu + peringkat;
    komisi otomatis lama hanya untuk PT bermode otomatis; isian `type="month"` dicabut), HP Beranda (PT `sheet`/`off`).
  - Target & Aturan: bagian **"Komisi otomatis (cara lama)"** (hanya PT bukan `sheet`/`off`; Semua PT: bila ada PT
    otomatis) = keterangan + "Akrual komisi bulanan" (pemilih bulan, lencana Sudah/Belum dibukukan, tombol "Bukukan akrual
    komisi {bulan}" / "Bukukan koreksi akrual komisi {bulan}", konfirmasi menyebut nominal & PT, alasan tertulis bila mati)
    + `LegacyRatesEditor` (dipindah dari `crm/IncentiveRatesEditor.jsx`, termasuk "Bawaan komisi") + `LegacySchemeEditor`
    (bagian jenjang dari `crm/IncentiveSchemeEditor.jsx`; bagian target dihapus). Dimuat malas (`React.lazy`).
  - Dihapus: `crm/SalesForceDashboard.jsx`, `crm/IncentiveSchemeEditor.jsx`, `crm/IncentiveRatesEditor.jsx`; tab hub
    `sales-performance`, `incentive-rates`, `incentive-schemes` (alias `since: "KM-T5"` → Capaian / Target & Aturan; rute
    cadangan merender layar tujuan); tautan "Skema insentif lama (arsip)" di Lembar Insentif. `COMMISSION_HOME`,
    `COMMISSION_LINK`, Master per PT `incentive-rates` → Target & Aturan. Grup SDM: `sales` → `sales_admin` (Admin Sales
    tetap Lembar Insentif). Beranda admin: sub-teks dari `incentive_payout_label`.

## Berkas

| Berkas | Isi |
|---|---|
| `backend/services/incentive_me.py` (baru), `backend/routers/incentive.py`, `backend/login_only_endpoints.py` | `GET /api/incentive/me`; `commission_mode(s)` di `/targets`; daftar login-saja + 1 |
| `backend/services/home_service.py`, `backend/services/incentive_payroll.py` (`belum_dibayar`) | beranda sales & admin per mode |
| `backend/services/sales_force_service.py`, `backend/routers/crm.py`, `backend/services/gl_service.py` (`incentive_accrual_estimate`) | `sales_roster`; 409 komisi; `sales-targets` dihapus; `gl-status` + `estimate` |
| `backend/access_modules.py` | id menu dicabut (KM-T5) |
| `frontend/src/features/incentive/MyIncentiveCard.jsx`, `LegacyRatesEditor.jsx`, `LegacySchemeEditor.jsx` (baru); `IncentiveSetupView.jsx`, `IncentiveSheetsView.jsx` | kartu; bagian komisi lama; tautan arsip dicabut |
| `frontend/src/features/home/SalesHome.jsx`, `AdminHome.jsx`, `hr/EmployeeSelfService.jsx`, `sales/mobile/MobileCollectionTargets.jsx`, `MobileSalesHome.jsx` | pemasangan kartu, label beranda admin, huruf HP ≥ 12 px di tab Target |
| `frontend/src/config/hubTabs.js`, `viewAliases.js`, `navStructure.js`, `navMeta.js`, `AppViewRouter.jsx`, `appViewImports.js`, `features/settings/config/configGroupViews.js`, `SettingsHub.jsx`, `settings/masters/EntityMastersView.jsx`, `crm/CrmView.jsx` | menu, alias, rute cadangan, tautan kunci komisi |
| Dihapus | `frontend/src/features/crm/SalesForceDashboard.jsx`, `IncentiveSchemeEditor.jsx`, `IncentiveRatesEditor.jsx` |
| Pemakai jalur yang dihapus | `backend/scripts/seed_demo_lengkap_kn.py` (target demo → `PUT /incentive/targets`), `backend/test_core_e0_isolation_poc.py` (L5 → `/api/incentive/targets`), `backend/tests/audit_numbers.py`, `scripts/entity_audit/verify_leaks.py`, `backend/tests/test_bp_PRT3_login_saja.py` (lapis A, ditulis) |
| Dibangkitkan | `CODEBASE_MAP.md`, `frontend/src/config/__tests__/fixtures/access_nav_fixture.json`, `access_builtin_fixture.json` (`configKeyIndex.json` dibangkitkan — tanpa perubahan) |
| Uji baru | `backend/tests_mem/test_KMT5_kartu_sales.py` (14), `frontend/src/features/__tests__/kmt5KartuSales.test.js` (10) |
| Dokumen | `ENTITY_REGISTRY.md` (baris ringkas + §KM-T5; catatan KM-T1), `memory/PRD.md`, `docs/KN_13_NAVIGATION_MAP.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.34 |

## Uji penerimaan

"Merah lama" = berkas uji dijalankan di B (`bukti/KM-T5/merah_kode_lama.txt`): 14/14 merah — `/api/incentive/me` 404
(U1–U5, U7, U12, tambahan), `KeyError incentive_payout_label` (U10), `KeyError incentive_mode` (U6), papan peringkat memuat
sales PT lain (U8), `/api/sales/commission` 200 (U9), `POST /api/sales-targets` 200 (U11). Jest:
`bukti/KM-T5/jest_merah_kode_lama.txt` (`Cannot find module '../incentive/LegacyRatesEditor'`).

| ID | Lapis | Kode lama | Kode baru |
|---|---|---|---|
| U1 | B | merah | lulus — 800.000.000 · 1.000.000.000 · 125,0 · 750.000.000 · 700.000.000 · 93,3 · 86,2; `sheets` [] (juga untuk periode bayarnya, L1 masih `submitted`); tanpa `margin_pct`/`sisa_piutang`; `mode` `sheet` |
| U2 | B | merah | lulus — satu lembar, dua baris Andi 2.000.000 + 3.000.000 = 5.000.000; tanpa baris/nama Budi; `auto_commission` null; potret baris Okt = 800 jt / 1.000 jt / 750 jt / 700 jt / 86,2 |
| U3 | B | merah | lulus — Budi + `sales_id`=Andi → hanya baris Budi 3.500.000 |
| U4 | B | merah | lulus — gaji November dibuat/diajukan/disahkan/diposting lewat HTTP → `status` `paid`, tiap baris `paid_run_number` = nomor proses |
| U5 | B | merah | lulus — Citra `ent_ksc`, periode bawaan (beku November 2026): `mode` `accrue_then_settle`, `auto_commission.mtd` 500.000 |
| U6 | B | merah | lulus — Andi: `incentive_mode` `sheet`, `commission` null, `history` [], mesin 0 kali dipanggil; Citra: `commission.mtd_accrual` 500.000 |
| U7 | B | merah | lulus — akun gudang: 200; uang 0 semua, persen `null` (lihat "Uji spesifikasi keliru"); `sheets` [] |
| U8 | B | merah (papan peringkat) | lulus — akun peran kustom beracuan sales ada di `/api/sales-users` dan papan peringkat `ent_kanda`; sales `ent_ksc` tidak; `my-rank.total` = jumlah papan. Bagian `/api/sales-users` sudah hijau di kode lama (PR-T4) |
| U9 | B | merah | lulus — 409 kalimat spesifikasi (juga `commission-history`); PT bawaan tetap 200 |
| U10 | B | merah | lulus — admin `ent_kanda`: 8.500.000 "Belum dibayar"; sesudah gaji diposting 0 "Belum dibayar"; `ent_ksc`: "Estimasi bulan ini" |
| U11 | B | merah | lulus — `POST`/`GET /api/sales-targets` 404/405; pencarian `frontend/src` tanpa pemanggil; `fe_be_routes.py` (lewat `runpy`, daftar lengkap): tidak ada panggilan tanpa rute ke `sales-targets` atau dari berkas unit ini; jumlah "TIDAK ADA rute" 72 → 72 (`bukti/KM-T5/fe_be_routes_*.txt`) |
| U12 | B | merah | lulus — lembar Andi di `ent_kanda` dan `ent_ksc`; PT aktif `ent_kanda` → hanya L1; PT aktif `ent_ksc` → hanya lembar `ent_ksc` |
| (tambahan) | B | merah | lulus — periode `2026-Q4` → 400; tanpa login → 401; `LOGIN_ONLY` = `milik_sendiri` |
| U13 | komponen | merah | lulus — "Capaian & Insentif Saya — November 2026", "Insentif Bulanan — Okt 2026", "Rp 2.000.000", "Dibayar bersama gaji November 2026", tanpa "Komisi"; + angka dasar, penyesuaian negatif "-Rp 500.000", dibayar, kosong, memuat, galat, komisi otomatis |
| U14 | komponen | merah | lulus — CRM manajer tanpa "Kinerja Sales"/"Skema (Arsip)"; `settings-sales` & `hr-kpi-hub` tanpa `incentive-rates`; alias ke Target & Aturan / Capaian; sales tidak mendapat pintu ke Capaian |
| U15 | jalan | — | **lulus — uji jalan integrator** (lihat Gate › Integrator). Pelaksana: Pengganti komponen: Beranda Sales PT `sheet` (kartu ada, tanpa "Komisi MTD"), PT otomatis (kartu lama + baris komisi berjalan), Profil Saya (kartu di bawah slip; tidak tampil bila kosong), HP Target (kartu `m-card`, tombol `btn-touch`, tanpa `/sales/commission` di PT `sheet`) |
| U16 | jalan | — | **lulus — uji jalan integrator** (lihat Gate › Integrator). Pelaksana: Pengganti komponen: bagian "Komisi otomatis (cara lama)" tampil di PT bermode bawaan (tarif, jenjang, akrual; konfirmasi "Beban komisi Rp 1.250.000 dibukukan ke buku CV Kanda Suka …"), tidak di PT `sheet` |

Hitung tangan (kepala berkas uji): OA1 Andi 20.000 yd × 50.000 = 1.000 jt, acuan 20.000 × 58.000 = 1.160 jt → realisasi
1.000/1.160 = 86,21 → 86,2; 1.000/800 = 125,0; uang masuk RA1 700 jt, 700/750 = 93,33 → 93,3. L1 = 2 + 3 + 3,5 jt = 8,5 jt;
U2 Andi 2 + 3 = 5 jt; U5 1.000 m × Rp 500 = 500.000.

Log: `bukti/KM-T5/merah_kode_lama.txt`, `tests_mem_KMT5_hijau.txt`, `jest_merah_kode_lama.txt`, `jest_ringkas.txt`,
`tests_mem_ringkas.txt`, `penjaga_sebelum_sesudah.txt`, `fe_be_routes_sebelum.txt`, `fe_be_routes_sesudah.txt`.

## Uji spesifikasi keliru (usulan koreksi, `00` §4)

**U7** — "semua angka 0": persen capaian tanpa target (dan realisasi harga tanpa omzet) tidak punya pembagi; pengumpul
Capaian (KM-T2) dan potret lembar (KM-T3) menulisnya `null`, dan kartu menampilkan "target belum diisi" / "—" (bukan "0 %",
yang menyesatkan). Teks pengganti kolom "Hasil" U7: "200; `target_sales`, `omzet_bersih`, `target_collection`,
`uang_masuk` 0; `pct_omzet`, `pct_pencairan`, `realisasi_harga_pct` `null` (tanpa pembagi); `sheets` kosong".

## Uji lama yang disesuaikan (perilaku yang sengaja diubah unit ini)

| Berkas | Perubahan | Alasan |
|---|---|---|
| `tests_mem/test_PRT2_gerbang.py` U04 | gerbang `sales_force.update` diuji lewat `POST /api/sales-incentives`; + `POST /api/sales-targets` 404/405 | jalur target lama dihapus |
| `tests_mem/test_PRT3_login_saja.py` U2, U13 | U2 hanya `/api/sales-incentives`; `LOGIN_ONLY` 53+1+1+1 **+1** | idem; `/api/incentive/me` login-saja |
| `tests_mem/test_PRT3_sapuan.py` | baris S3 `GET /api/sales-targets` dicabut dari sapuan | rute dihapus |
| `tests_mem/test_KMT1_pengalihan.py` U14 | sifat jalur lama (PT konteks, kunci per PT, 400 periode, 409 Semua PT) diuji lewat `PUT /api/incentive/targets`; + jalur lama 404/405 | jalur lama dihapus |
| `tests_mem/test_PRT4_sifat_peran.py` | `list_targets`/`create_target` keluar dari daftar jangkar; U4 papan peringkat dibaca di PT uji dan dibandingkan dengan akun sales PT itu | fungsi dihapus; papan = `sales_roster` PT |
| `tests_mem/test_MNT1_menu_keuangan.py` U11 | modul `penjualan` tidak lagi membuka `hrd`/`hr-kpi-hub`/`sales-performance` | tab Kinerja Sales dicabut |
| `tests_mem/test_PRT6_layar_peran.py` U4 | `hrd` kembali menu tambahan bagi Sales + `hr` | idem |
| `tests/test_bp_PRT3_login_saja.py` (lapis A, ditulis) | `/sales-targets` → `/sales-incentives`; + 404/405 | idem |
| jest `mnt1MenuKeuangan`, `kpt9HubPengaturan`, `prt7TombolIzin`, `mnt1Pembungkus`, `phase3Settings` (gagal dimuat, statik) | hub Kinerja & Insentif 4 tab; menu sales tanpa SDM; alias `incentive-rates` → `incentive-setup`; mock layar yang dihapus dicabut; `COMMISSION_HOME` | tab/layar dicabut |

## Cek layar

Dari kode (integrator memotret 1280/1024/390 px; kartu ±1018 px di 1280, ±760 px di 1024). Huruf memakai token `text-fs-*`
(≥ 12 px), warna `kn-*` (berkas baru: 0 hex, 0 `text-[Npx]`, 0 tombol bergaya sendiri); rupiah `formatCurrency` dalam
`whitespace-nowrap` ("-Rp" utuh); tanpa `type="date"`/`type="month"`.

| # | Butir | Kartu Capaian & Insentif Saya (Beranda, Profil, HP) | Target & Aturan › Komisi otomatis (cara lama) | Beranda Sales / HP Beranda / HP Target | Beranda admin |
|---|---|---|---|---|---|
| 1 | Tabel lebih lebar dari kartu | Tanpa tabel — daftar baris; di < 640 px label di atas nilai; baris lembar: nama (boleh patah) + nominal `shrink-0` nowrap. HP 390: lebar isi ±340 px, satuan nowrap terpanjang "Rp 1.000.000.000" ±130 px | Tarif: 6 kolom di kartu bersarang (isi ±704 px di 1024): PT ±96 (boleh patah) · Kategori ±80 · Tarif ±110 ("/satuan dasar" baris kedua) · Diskon ±120 (boleh patah) · Batas margin ±70 (judul dua baris `head-wrap`) · Aksi ±72 `col-sticky-end` = 548 + 6 × 24 = ±692; lebih → `table-container` bergulir. Jenjang: 3 kolom, Aksi `col-sticky-end` | Kisi KPI tetap `grid-cols-2 lg:grid-cols-4` (5 kartu di PT Lembar Insentif); HP Target: kartu + peringkat, Kpi 2 kolom | tidak berubah |
| 2 | `section-card` tanpa bantalan | `section-head` + `section-body`; HP `m-card p-3` | `section-head` + `section-body`; kartu akrual `rounded-md border p-3` | — | — |
| 3 | Kepala kartu dijejali | Kepala = ikon + judul; pemilih bulan & "Data per pukul …" di bilah sendiri | Kepala = ikon + judul; tombol (Tarif Baru, Muat ulang, Tambah jenjang, Simpan jenjang, Bukukan akrual) di bilah sendiri | — | — |
| 4 | Tombol mati hanya tooltip | Tidak ada tombol mati | "Bukukan akrual…" mati → alasan di samping ("Akrual komisi {bulan} sudah dibukukan." · "Tidak ada komisi untuk dibukukan pada {bulan}." · "Membukukan akrual butuh akses …"); tanpa izin ubah → tombol tidak tampil + kalimat alasan; Semua PT → "Pilih satu PT untuk membukukan akrual komisi." | — | — |
| 5 | Status hanya warna+teks | Lembar: `status-pill` `status-done` + CheckCircle2 "Disahkan" / `status-shipped` + Wallet "Dibayarkan" + kalimat "Dibayar bersama gaji …"/"Sudah dibayar (gaji …)"; penyesuaian `status-draft` "Penyesuaian" | Akrual: `status-done` + CheckCircle2 "Sudah dibukukan" / `status-pending` + Clock "Belum dibukukan" | — | — |
| 6 | Daftar tanpa cari | Baris = milik sendiri satu bulan (sedikit) | Tarif: daftar master per PT×kategori (tetap tanpa cari, seperti layar asal); jenjang: per sales lewat pemilih | — | — |
| 7 | Teks bertentangan dengan izin | Endpoint milik sendiri; tidak menyebut izin | Alasan menyebut modul "Pengawasan Tim Sales & Kredit" (izin endpoint `sales_force.*`) | Tidak ada lagi "Komisi" di PT Lembar Insentif | Sub-teks "Belum dibayar" / "Estimasi bulan ini" sesuai mode |
| 8 | Kosong ganda / angka 0 / grafik | Satu kalimat kosong lembar; target 0 → "target belum diisi"; persen tanpa pembagi "—"; Profil Saya tidak menampilkan kartu kosong | Satu kalimat per keadaan (memuat · galat · Semua PT · mode tidak memakai akrual) | Tren komisi (grafik) tidak tampil di PT Lembar Insentif | — |

HP 390 px (kartu `variant="mobile"`): pemilih bulan `kn-input-touch` (48 px), tombol "Angka dasar" `btn-touch` (48 px), judul
16 px, isi 13–14 px, catatan 12 px. Tab HP "Target & Insentif": huruf 9–11 px lama (Kpi, peringkat, komisi otomatis) → 12–20 px
token. HP Beranda (`MobileSalesHome`) hanya menyembunyikan ubin komisi di PT Lembar Insentif; huruf kecil lama di layar itu
tidak disentuh.

## Menyimpang dari blueprint

1. **Letak layar lama di HEAD** sudah dipindah MN-T1/KM-T1/KM-T3 (lihat cek ulang): yang dicabut adalah tiga tab SDM ›
   Kinerja & Insentif, bukan sub-tab CRM. Alias: `sales-performance` → Capaian, `incentive-rates` & `incentive-schemes` →
   Target & Aturan (`viewAliases.js`, rute cadangan merender layar tujuan); tautan arsip di Lembar Insentif dicabut.
2. **Grup SDM & menu sales**: `sales` dicabut dari grup SDM dan item Kinerja & Insentif (tanpa tab tersisa untuknya);
   `sales_admin` ditulis eksplisit (dulu lewat warisan menu sales) supaya Lembar Insentif tetap terjangkau. Modul akses
   `penjualan`/`sales_force` tidak lagi membuka `hrd`/`hr-kpi-hub` (penjaga `verify_access_catalog_nav` aturan 2).
3. **HP Beranda (`MobileSalesHome`)** tidak disebut spesifikasi tetapi membaca `commission` dari `/api/home/sales`: di PT
   `sheet`/`off` ubin Komisi MTD/Proyeksi/Capaian Target, kartu target penagihan, rincian & tren komisi disembunyikan dan
   kartu versi HP dipasang (tanpanya HP menampilkan "Komisi MTD Rp 0").
4. **Tombol bagian komisi lama** memakai `canCurrent("sales_force", …)` (izin endpoint yang dipanggil: tarif `view/update/
   delete`, jenjang `update`, akrual `post`), bukan `incentive` — spesifikasi "tombol memakai `canCurrent("incentive", aksi)"`
   berlaku untuk kartu baru (yang tidak punya tombol berizin). Tanpa `sales_force.view` bagian tampil dengan kalimat alasan.
5. **Konfirmasi akrual menyebut nominal** → `GET /api/sales/incentive/gl-status` + `estimate` (dan `mode`) dari
   `gl_service.incentive_accrual_estimate`, satu fungsi dengan akrual manual (refaktor tanpa ubah angka). Bila sudah
   dibukukan dan angka berubah, tombol menjadi "Bukukan koreksi akrual komisi {bulan}" (jalur koreksi P17 yang ada).
6. **`commission_mode` & `commission_modes` di `GET /api/incentive/targets`** (bukan endpoint baru) supaya Target & Aturan
   tahu sakelar PT tanpa izin `incentive.configure` (kartu Kesiapan) — jawaban dibaca bagian Target yang sudah ada.
7. **Beranda Sales di PT `sheet`/`off`** juga menyembunyikan "Proyeksi Bulan", "Capaian Target Penagihan", dan kartu progres
   penagihan (semuanya keluaran mesin komisi: `target.amount`/`achievement_pct` tidak dikirim). Kartu baru tampil juga di PT
   bermode otomatis (spesifikasi: kartu lama tetap + baris "Komisi berjalan").
8. **Catatan kaki di PT bermode otomatis** diganti "Nominal di lembar insentif diputuskan pimpinan … Komisi berjalan dihitung
   otomatis sampai PT ini beralih ke Lembar Insentif." — kalimat spesifikasi ("Tidak ada rumus otomatis") bertentangan dengan
   baris komisi otomatis di PT itu (cek layar 7). PT `sheet`/`off`: kalimat spesifikasi.
9. **"Semua PT"** (tidak disebut spesifikasi): beranda admin = Σ per PT, label "Belum dibayar + estimasi bulan ini" bila
   campuran (tanpa PT `sheet` = perilaku lama persis); 409 komisi hanya bila semua PT `sheet`/`off`; papan peringkat =
   gabungan daftar tiap PT.
10. **Kecil**: persen `"125,0 %"` lewat pembantu kartu (sama dengan rincian lembar KM-T3); "Data per pukul 10.00 WIB"
    memakai format jam id-ID; lembar dengan > 1 baris diberi baris "Jumlah" (D5).
11. **Operasi git tak sengaja**: satu `git rm --cached` atas `SalesForceDashboard.jsx` di W, langsung dipulihkan dengan
    `git reset -- <berkas>` (indeks kembali = HEAD, tidak ada perubahan ter-stage; berkas tetap dihapus di pohon kerja).

## Asumsi

- `ASUMSI:` (spesifikasi) sales hanya melihat nominal lembar yang disahkan; tanpa margin, sisa piutang, atau angka sales lain.
- `ASUMSI:` lembar di kartu = lembar dengan **periode bayar** = bulan kartu (U2/U4 memakai `period=2026-11` untuk lembar
  `pay_period` 2026-11); capaian = bulan kartu sebagai periode dasar.
- `ASUMSI:` catatan baris (`note`) dikirim untuk semua baris (spesifikasi daftar isian); di kartu hanya ditampilkan untuk
  baris penyesuaian.
- `ASUMSI:` Profil Saya: kartu tampil bila muatan pertama berisi (uang capaian ≠ 0 atau ada lembar) atau galat; sesudah tampil
  tidak hilang saat bulan diganti.
- `ASUMSI:` peran kustom yang hanya memegang `sales_force` (tanpa `incentive`) kehilangan menu tarif/jenjang (tab lama dicabut
  spesifikasi; bagian kini di layar ber-izin `incentive.view`).
- Pekerjaan lanjutan (di luar lingkup): menghapus mesin komisi (`compute_commission`), `incentive_rates`, `sales_incentives`,
  bagian "Komisi otomatis (cara lama)", dan alias `incentive-rates`/`incentive-schemes` setelah tidak ada PT bermode komisi
  otomatis. Rujukan lama yang tidak dijalankan gate dibiarkan: `backend/backend_test_crm_enforcements.py` (uji agen lama
  `POST /api/sales-targets`), arsip `audit/`, `docs/audit/`, `tests/archive/`; komentar `IncentiveRatesEditor` di
  `permissions_config.py`, `verify_uom_vocab.py`; entri berkas terhapus di baseline ratchet UI (`--update` tidak dijalankan).

## Titik henti

- H5: tidak ada sakelar PT yang diubah; bagian komisi lama hilang sendiri saat pemilik mengalihkan PT (pertanyaan pemilik
  KM-T4 tetap berlaku).
- H3: tanpa skrip data; uji hanya database tiruan. Tidak ada keputusan pemilik baru yang dibutuhkan.

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`7183e4f`**:

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`d458cd5`: 12 / 39); penghapusan tiga tab dan `GET/POST /api/sales-targets` tidak menambah merah.
Kuitansi: `bukti/KM-T5/gate_quick_receipt.md`, `gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- HEAD cabang tetap `47b48d6` sejak pelaksana menggabung. Pohon T disalin apa adanya → **`7183e4f`** (58 jalur: 49 diubah,
  6 baru, 3 dihapus — `IncentiveRatesEditor.jsx` tercatat git sebagai ganti nama ke `incentive/LegacyRatesEditor.jsx`),
  diperiksa berkas demi berkas sama dengan T. `tests_mem` 2312/2/2 dan jest 1121 dari pelaksana (pohon sama — tidak diulang,
  mode hemat pemilik 15 Nov).
- Lingkungan A (data acuan sesudah `restore_demo`, backend dinyalakan ulang dengan kode `7183e4f`;
  `bukti/KM-T5/integrator_lingkungan_A.txt`): lapis A `tests/test_bp_PRT3_login_saja.py` **3 lulus** (disesuaikan pelaksana: `GET /api/sales-targets`
  yang dihapus → 404/405 untuk sales; `/sales-incentives` tetap tersaring milik sendiri; sopir ditolak/tersaring; manajer tidak
  kehilangan isi).
- Data contoh uji jalan (database uji; `bukti/KM-T5/kmt5_layar_fixture.py`): PT **Sukacita** mode `sheet` (beralasan, lokal),
  satu Lembar Insentif sah untuk sales@ (Ayu Marketing): "Insentif Bulanan", dasar Okt 2026, periode bayar Nov 2026,
  Rp 2.500.000 → `GET /api/incentive/me?period=2026-11` = mode `sheet`, satu lembar Rp 2.500.000; `GET /api/home/sales`
  `incentive_mode` `sheet`, `commission` `null`. Kanda tetap mode bawaan.
- **U15 lulus** (login sales@, PT Sukacita): Beranda Sales 1280/1024 — kartu "Capaian & Insentif Saya — November 2026" (pemilih
  bulan, Omzet/Uang masuk "Rp 0 dari target …", Realisasi harga "—", "Insentif yang sudah disahkan": Insentif Bulanan — Okt 2026
  Rp 2.500.000, Angka dasar, lencana Disahkan + "Dibayar bersama gaji November 2026", catatan kaki), KPI tanpa "Komisi MTD";
  Profil Saya 1024 — kartu yang sama di bawah slip; HP 390 (tampilan HP) — Beranda dan Lainnya › Penagihan & Target › tab
  "Target & Insentif": angka tidak terpotong, pemilih bulan dan tombol besar, `overflowX` 0.
- **U16 lulus** (login manager@): Kinerja & Insentif › Target & Aturan — PT Sukacita (`sheet`): bagian `ins-legacy` **tidak ada**;
  PT Kanda (bawaan): bagian "Komisi otomatis (cara lama)" tampil (akrual bulanan November 2026 + lencana Belum Dibukukan, tombol
  "Bukukan akrual" mati dengan alasan tertulis "Tidak ada komisi untuk dibukukan…", Bawaan komisi, Tarif komisi, Jenjang).
- Tabel **Tarif komisi per PT × kategori** (data acuan: 7 tarif "Semua PT" + 2 tarif contoh Kanda dibuat lewat API di database
  uji): 6 kolom = **702 / 958 px = lebar kartu** (1024 / 1280), Aksi ikon menempel kanan, "/satuan dasar" di baris kedua.
- Tidak ada cacat layar yang perlu diperbaiki integrator. Potret `bukti/KM-T5/cek_*.png`.

Pelaksana (catatan asli):

Belum dijalankan (lingkungan A dipakai integrator). Uji jalan U15, U16 belum. `tests/test_bp_PRT3_login_saja.py` (lapis A)
ditulis ulang, belum teruji.

## Penjaga & angka uji (worktree kerja W, basis `fee66fe`)

| | Sebelum (B) | Sesudah (W) |
|---|---|---|
| `tests_mem` | 2298 lulus / 2 dilewati / 2 xfail | **2312** lulus / 2 / 2 (+14 KM-T5). Jalan penuh: 2311 lulus + 1 merah `test_PRT6_layar_peran.py::U4` (`hrd` kembali menu tambahan Sales) → disesuaikan, berkas itu 18/18 (terarah, hemat uji) |
| jest penuh | 1111 lulus (35 suite gagal dimuat — `cmdk`/`@radix-ui`) | **1121** lulus (+10 `kmt5KartuSales`; 35 suite yang sama) |
| `hitung_penjaga.sh` | auth 26 · ui_standard 9 · i18n 102 · create_modal 5 · page_tabs 1 (INV-UI-13 0) · to_list 5 · entity_label 2 · lainnya 0 | identik kecuali **i18n 101** |
| sensus `verify_ui_standard` (total) | font_lt12 6602 · hex 15950 · btn_force 551 | 6564 · 15879 · 549 (lainnya sama) |
| `verify_role_gate_ui` · `verify_view_aliases` · `verify_access_catalog_nav` · `check_nav_map` | 31/0 · 168/0 · 0 · PASS | 31/0 · 186/0 · 0 · PASS |
| `verify_config_fallback` (+`--entity`) · `audit_config_wiring --strict` · `verify_payment_vocab` · `verify_cash_single_door` | 162/0 (162/0) · hijau · 1866/0 · 753/0 | 162/0 (162/0) · hijau · 1867/0 · 754/0 |
| `verify_posting_coverage` · `verify_atomic_claim` · `verify_detail_modal` · `verify_config_text` · `verify_scope_guard` | 140/0 · 161/0 · 31/0 · 3486/0 · HIJAU | sama |
| `fe_be_routes.py` "TIDAK ADA rute" | 72 | 72 |

## Penggabungan (pelaksana, ke HEAD `47b48d6` — sesudah `d458cd5` KM-T4 cek layar, `58c1c6d`/`47b48d6` laporan)

Worktree tujuan T di-*detach* ke HEAD cabang; per berkas: sama dengan B → disalin dari W; beda → `git merge-file`; baru →
disalin; dihapus → dihapus bila HEAD = B. HEAD sesudah B hanya mengubah `IntercoChargesPanel.jsx`, lapis A
`test_bp_KMT4_sahkan_bersamaan_mongo.py`, STATUS/TRACKER, dan laporan — **tidak ada berkas unit ini yang bentrok**
(49 disalin, 6 baru, 3 dihapus; `bukti/KM-T5/gabung_T_47b48d6.txt`). Turunan dibangkitkan ulang di T: `CODEBASE_MAP.md`,
`configKeyIndex.json` (tanpa perubahan), fixture akses (`access_modules.py` berubah; `test_fe03_access_catalog.py` 6/6).
Hitungan uji lama (KF-T1, PRT9, PK-14, PR-T3 `LOGIN_ONLY`) tidak diubah HEAD → angka unit dipakai apa adanya.

| | HEAD `47b48d6` (murni) | T (HEAD + KM-T5) |
|---|---|---|
| `tests_mem` | tidak dijalankan penuh (hemat uji) — 2298 (= T − 14; HEAD tidak menambah uji `tests_mem`) | **2312** lulus / 2 dilewati / 2 xfail |
| jest penuh | 1111 (= T − 10) | **1121** lulus (35 suite gagal dimuat — `cmdk`/`@radix-ui`, daftar sama dengan B) |
| `hitung_penjaga.sh` | auth 26 · ui_standard 9 · i18n 102 · create_modal 5 · page_tabs 1 · to_list 5 · entity_label 2 | sama, **i18n 101** |
| `verify_role_gate_ui` · `verify_view_aliases` · `verify_access_catalog_nav` · `check_nav_map` | 31/0 · 168/0 · 0 · PASS | 31/0 · 186/0 · 0 · PASS |
| `verify_config_fallback` (+`--entity`) · `verify_payment_vocab` · `audit_config_wiring --strict` | 162/0 (162/0) · 1866/0 · hijau | 162/0 (162/0) · 1867/0 · hijau |
| `verify_posting_coverage` · `verify_atomic_claim` · `verify_cash_single_door` · `verify_detail_modal` · `verify_config_text` | 140/0 · 161/0 · 753/0 · 31/0 · 3486/0 | 140/0 · 161/0 · 754/0 · 31/0 · 3486/0 |

## Hambatan lingkungan

- Suite jest yang memuat `cmdk`/`@radix-ui` gagal dimuat (kendala lama); uji KM-T5 meniru `KNSelect` dan memalsukan
  `LegacyRatesEditor`/`LegacySchemeEditor` (bagian dimuat malas) dan `recharts`.

## Yang perlu direview

- Usulan koreksi U7 (persen tanpa pembagi `null`).
- Menyimpang 2 (grup SDM: `sales` → `sales_admin`), 3 (HP Beranda), 4 (izin tombol bagian lama = `sales_force`), 9 (Semua PT).
- Uji jalan U15, U16 (Beranda/Profil/HP sales di PT `sheet`; Target & Aturan di PT bawaan vs `sheet`).

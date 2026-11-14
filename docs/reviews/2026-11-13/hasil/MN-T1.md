# MN-T1 — Menu keuangan dan SDM: pindah dan kelompokkan tanpa mengubah isi layar

- Commit awal: `1392969` (dikerjakan) · digabung di atas `eb4e0e1` (sesudah KP-T5)        - Commit: `5e94a1d` · POC E-8/F-2 `bcce72a` · teks Meja Finance `c38fc92`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: UX-17, IA-06, IA-15 — K-09, K-17, K-46 (K-18 tidak disentuh: nominal kontrabon untuk gudang = PK-17)
- Spesifikasi: `docs/blueprint/unit/MN-T1.md`; rancangan `docs/finance/rencana-2026-11-13/01_PENGGABUNGAN_MENU.md`

## Cek ulang "Keadaan sekarang" (di `1392969`)

| # | Hasil |
|---|---|
| 1 | Berlaku. `navStructure.js:298` (`keuangan`, 7 entri), `:320` (`akuntansi`, 7), `:339` (`kas-aset`, 3), `:222` (`accounts-payable` di Pembelian) |
| 2 | Sebagian bergeser: tujuh sub-tab `CrmView.jsx:23` (`TABS`), empat keuangan/insentif. Gerbang dua tab **sudah izin** (PR-T7): `CrmView.jsx:21-22` `can(perms, "sales_force", "view")` / `can(perms, "credit_override", "approve")`, bukan `roleIs` |
| 3 | Berlaku, bergeser: `hubTabs.js:256` (`incentive-rates` di `settings-sales`), `:202` (`hr-kpi-hub` satu tab) |
| 4 | Berlaku, bergeser: `roles.js:251` (`ROLE_NAV.finance` tanpa `bank-accounts`, `bank-reconciliation`, `ledger`, `petty-cash`, `accounts-payable`); `permissions_config.py:349` (finance: `cash`, `accounting.view`, `cash_advance`, `cash_settlement`; `vendor_bill` hanya `approve`/`reject` dari KP-T4, tanpa `view`) |
| 5 | Berlaku: `navStructure.js:312` (`finance-cases` mencantumkan sales), grup induk admin+manager; `navigationConfig.js:148` (`isModuleNavRole`); `permissions_config.py:132` (`finance_case` sales `view`,`create`) |
| 6 | Berlaku: `hubTabs.js:271` (`gl-account-mappings` mencantumkan finance; grup Pengaturan tidak di menu Finance) |
| 7 | Berlaku: `permissions_config.py:97` (`cash_advance.disburse` hanya admin) |
| 8 | Bergeser: `access_modules.py:19` (`MODULE_CATALOG`). `reimburse-payables` (`_PRT5_NAV` → `petty_cash`), `finance-desk` (`_PRT5_NAV` → `ar`), `incentive-rates` (PR-T2 → `sales_force`) **sudah** bermodul; `finance-tower` masih dibuka modul kas (`finance_ops`, `:148`) |
| 9 | Berlaku: `verify_page_tabs.py:44` (`count`) — tanpa batas tab per hub, tanpa pemeriksaan tab di dalam tab hub |
| 10 | Berlaku: `products-pricing` 8 tab tampak (`hubTabs.js:38`), `purchase-orders` 6 (`:57`) |
| 11 | Berlaku, bergeser: `GeneralLedger.jsx:48` (`TABS`, 5 tab) |
| 12 | Berlaku: `navMeta.js:229` (`finance` → `finance-desk`/`finance-desk`), `role_registry.py:95` (`home_view`); juga `role_registry.py:349` (`HOME_CHOICES` `finance-desk` → `nav_id` `finance-desk`) |
| 13 | Berlaku: `roleReach.test.js:14` (`ROLE_IDS`), baseline `fixtures/role_reach_baseline.json` |
| 14 | Berlaku: `verify_view_aliases.py:15-17` (aturan C, `legacy`) |

Di HEAD `verify_page_tabs.py` sudah MERAH 1 (INV-UI-12, `features/wms/InventoryStockView.jsx` — berkas baru berpola
tab buatan sendiri, bukan dari unit ini).

## UX-17 — Menu Finance ditulis tangan, tidak mengikuti izinnya
- Berlaku di HEAD: ya (butir 4, 7).
- Akar masalah: menu peran Finance adalah daftar `ROLE_NAV.finance` yang tidak ikut bertambah ketika izinnya bertambah;
  sebagian izin (`cash.create`, `accounting.view`, `cash_advance`, `cash_settlement`) tanpa pintu menu.
- Perubahan perilaku (sebelum → sesudah):
  - Izin bawaan (K-09, K-17; `permissions_config.MNT1_DEFAULT_PAIRS`, hanya menambah): Finance + `vendor_bill.view/pay`,
    `contra_bon.view/pay`, `cash_advance.disburse`; Manajer + `cash_advance.disburse`. Instalasi lama menerimanya sekali
    lewat `sync_permission_modules` (`defaults_applied`, PR-T9).
  - Menu Finance (`ROLE_NAV.finance.add` + 16 id): Keuangan › Beranda Keuangan (3 tab), Piutang (6), Hutang (2),
    Kas & Bank (4: + Rekening & Saldo, Rekonsiliasi, Kas Kecil), Antar-PT; Akuntansi & Pajak › Buku Besar (2, lihat
    saja) dan Pajak › Faktur Keluaran; Pengaturan › Keuangan & Pajak › Pemetaan Akun. Tidak memuat Tutup Buku, Laporan,
    Aset Tetap. Finance tidak lagi melihat Kinerja Sales (dulu sub-tab CRM; rancangan `01` §4).
  - `GET /api/vendor-bills`, `/api/contra-bons` Finance 403 → 200; `POST /api/cash-advances/{id}/disburse` Finance
    403 → 200 (database tiruan).
- Fixture disiapkan langsung vs proses bisnis: U13 PD berstatus `approved` disisipkan langsung; sisanya lewat API.

## IA-06 — Menu mencantumkan peran yang tidak pernah melihatnya
- Berlaku di HEAD: ya (butir 5, 6).
- Perubahan: grup Keuangan `roles` + sales, + gudang (Akuntansi & Pajak tanpa gudang); grup SDM + sales. Sales melihat
  Keuangan › Piutang (Penagihan & Penerimaan, Kasus) dan Kas & Bank › Kas Kecil; SDM › Kinerja & Insentif › Kinerja Sales.
  Admin Sales mewarisi menu itu + Antar-PT (tanpa Hutang). Gudang/Admin Gudang: Keuangan › Hutang › Kontrabon dan
  Antar-PT; Akuntansi & Pajak tidak tampil. Finance: Pemetaan Akun terjangkau.

## IA-15 — Dokumen navigasi basi untuk keuangan
- Berlaku di HEAD: ya. `KN_13` (bagian baru "MENU KEUANGAN, AKUNTANSI & PAJAK, DAN SDM" — tabel per tab × peran
  dibangkitkan dari konfigurasi, `bukti/MN-T1/menu_per_peran_dari_konfigurasi.json`; changelog; IA target), `KN_14`
  (§5.2 grup, §5.6 baris Keuangan/Akuntansi & Pajak/SDM, changelog), `KN_16` (§8A langkah proses → menu › tab),
  `KN_32` (§9.4 label baru; "PT", "pemasok").

## Susunan baru (ringkas)

Keuangan **5 entri** (Beranda Keuangan · Piutang · Hutang · Kas & Bank · Antar-PT) + Akuntansi & Pajak **5 entri** (Buku
Besar · Tutup Buku · Laporan · Pajak · Aset Tetap) = 10 entri dalam 2 grup; grup Kas & Aset dihapus; Landed Cost →
Pembelian › Pesanan Pembelian (hub 7 tab, baseline); Kendaraan → Gudang & Logistik; CRM & Pelanggan tinggal Pelanggan ·
Prospek · Interaksi; Komisi & Insentif → SDM › Kinerja & Insentif › Target & Aturan. Label persis tabel spesifikasi.
Enam alias `since: "MN-T1"` (`advance-report`, `store-credit` → `customer-credit`; `cash-advances`, `settlements`,
`reimburse-payables` → `petty-cash` dengan `preset.bagian`; `kas-aset` → `petty-cash`, `legacy`), masing-masing ber-`label`
nama lama (palet Ctrl+K "nama lama → kini di …"). Rute cadangan id lama tetap.

## Berkas berubah

| Berkas | Isi |
|---|---|
| `frontend/src/config/navStructure.js` | Grup Keuangan/Akuntansi & Pajak baru, Kas & Aset dihapus, Hutang keluar dari Pembelian, Kendaraan ke Gudang, Meja Finance bukan menu lepas/butir Meja Peran, SDM + sales, "Kinerja & Insentif"; tiga ikon tak terpakai dicabut |
| `frontend/src/config/hubTabs.js` | Hub `finance-tower` (3), `ar-aging` (6, baru), `accounts-payable` (2), `cash-bank` (4), `closing` (3, baru), `hr-kpi-hub` (4), `purchase-orders` + Landed Cost; hub `petty-cash` dihapus; `incentive-rates` keluar dari `settings-sales`; label (Jurnal, Bagan Akun, Proses Gaji, dst.) |
| `frontend/src/config/roles.js` | `ROLE_NAV.finance.add` + 16 id; `ROLE_NAV.sales_admin.add` tanpa `akuntansi` |
| `frontend/src/config/viewAliases.js` | Enam alias MN-T1 |
| `frontend/src/config/navMeta.js` | Judul enam view (`collection-worklist`, `customer-credit`, `credit-overrides`, `sales-performance`, `incentive-schemes`, `petty-cash`); `ROLE_HOME_REGISTRY.finance.navId` = `finance-tower`; judul tanpa "Chart of Accounts"/"Payroll Run"; kicker `incentive-rates` |
| `frontend/src/AppViewRouter.jsx`, `appViewImports.js` | Rute enam view baru (empat komponen CRM tanpa perubahan + dua pembungkus) |
| `frontend/src/features/finance/CustomerCreditView.jsx` (baru), `features/pettycash/PettyCashView.jsx` (baru) | Pembungkus `FilterChips` + layar lama utuh; chip menurut izin endpoint layar lama dan `hidden_views`/`ROLE_NAV.remove` atas id lama; `preset.bagian` |
| `frontend/src/features/crm/CrmView.jsx` | `TABS` tinggal tiga; impor & gerbang empat sub-tab dicabut |
| `frontend/src/features/crm/CreditOverridesPanel.jsx` | Tombol Setujui/Tolak hanya dengan `credit_override.approve` (Finance membaca tanpa memutus) |
| `frontend/src/features/approvals/approvalInboxData.js` | Butir kredit Pusat Persetujuan membuka Piutang › Kredit & Plafon (dulu CRM) |
| `frontend/src/features/settings/config/configGroupViews.js`, `SettingsHub.jsx`, `masters/EntityMastersView.jsx` | Rumah kunci komisi: menu `hr-kpi-hub`; teks tempat "SDM › Kinerja & Insentif › Target & Aturan" |
| `backend/access_modules.py` | Blok `MN-T1` `_MNT1_NAV_ADD`/`_MNT1_NAV_REMOVE` (tabel katalog spesifikasi); `VIEW_RESOURCE_OVERRIDES["incentive-schemes"]` |
| `backend/permissions_config.py` | Blok `MN-T1` `MNT1_DEFAULT_PAIRS` + catatan pada komentar Finance |
| `backend/role_registry.py` | Finance `home_nav_id` `finance-tower`; `HOME_CHOICES` Meja Finance `nav_id` `finance-tower` |
| `backend/services/custom_role_service.py` | `load_hidden_views`: id yang tidak dikenal katalog dibuang saat dimuat (data tersimpan tidak diubah) |
| `backend/config_catalog_core.py` | Contoh kunci `notif.reminder_recipients` memakai istilah glosarium (lihat Menyimpang 11) |
| `scripts/guardrails/verify_page_tabs.py`, `baselines/hub_tab_limit.json`, `baselines/third_level_tabs.json` (baru), `scripts/gate.sh` (label), `memory/INVARIANTS.md` | INV-UI-13, INV-UI-14 + uji-diri (14 kasus total) + baris ringkasan; dua baris registri invarian |
| Uji baru | `backend/tests_mem/test_MNT1_menu_keuangan.py` (U4, U4b, U11, U12, U13, U13b); jest `frontend/src/config/__tests__/mnt1MenuKeuangan.test.js` (U1–U3, U6–U10, U15) + tabel bantu `fixtures/view_main_permission.json`; jest `frontend/src/features/__tests__/mnt1Pembungkus.test.js` (pembungkus, preset U17, CRM 3 tab, tombol kredit); lapis A `backend/tests/test_bp_MNT1_menu_keuangan.py` (U4, U12, U13 — **lulus** di lingkungan A, 3 uji) |
| Uji lama disesuaikan (disengaja) | lihat "Menyimpang" 9 |
| Fixture | `access_nav_fixture.json`, `access_builtin_fixture.json` dibangkitkan ulang (`tests/fe03_access_fixture.py`) |
| Dokumen | `docs/KN_13_NAVIGATION_MAP.md`, `KN_14_INFORMATION_ARCHITECTURE.md`, `KN_16_END_TO_END_PROCESS_FLOWS.md`, `KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.4, `CODEBASE_MAP.md` (generator) |

## Uji penerimaan

Merah di kode lama: berkas uji final dijalankan pada salinan `git archive 1392969`
(`bukti/MN-T1/merah_kode_lama_tests_mem.log`, `jest_merah_kode_lama.log`). Hijau: `hijau_kode_baru_tests_mem.log`,
`jest_hijau_kode_baru.log`.

| ID | Lapis | Merah di lama | Hasil |
|---|---|---|---|
| U1 | komponen | ya (Keuangan 7 entri, Akuntansi 7, Kas & Aset ada) | Lulus — 5 + 5 = 10 entri, label & urutan persis; `kas-aset` tidak ada; Hutang bukan di Pembelian; Kendaraan di Gudang; Meja Finance bukan menu lepas |
| U2 | komponen | ya (7 dari 8 hub; `ledger` sudah 2) | Lulus — `finance-tower` 3 · `ar-aging` 6 · `accounts-payable` 2 · `cash-bank` 4 · `closing` 3 · `ledger` 2 · `hr-kpi-hub` 4 · `purchase-orders` 7; label tab persis |
| U3 | komponen | tidak (invarian sudah berlaku di menu lama); bukti-merah mutasi: Finance tanpa `vendor_bill` → "keuangan › accounts-payable › vendor-bills" terdeteksi (merah di lama karena menu Hutang belum ada) | Lulus — 13 peran × menu Keuangan/Akuntansi/SDM/Landed Cost/Kendaraan/CRM: 0 entri tampak tanpa izin (izin dari `access_builtin_fixture.json`) |
| U4 | B | tidak (izin endpoint tidak diubah unit ini — tabel bantu menjaganya) | Lulus — 41 view, 44 pasangan: peran Tanpa Acuan berizin tepat satu pasangan → tidak 403 di tiap endpoint utama; U4b Manajer Kosong → 403 tiap baris |
| U5 | komponen | — | Lulus — `roleReach.test.js` & `serverAccessReach.test.js` tanpa mengubah baseline; tambahan dicatat `ROLE_REACH_ADDITIONS` (K-09, K-17, UX-17, IA-06, MN-T1); dua id hub yang kini mendarat di tab pertama lain dicatat `ROLE_REACH_RELANDED` (Menyimpang 8) |
| U6 | komponen | ya (12 dari 14; `vehicle-logs`, `fixed-assets` sudah benar) | Lulus — semua bukan `null`; lima pertama membawa `preset.bagian` (`titipan`, `saldo`, `pengajuan`, `pertanggungjawaban`, `reimburse`); `navId` persis spesifikasi |
| U7 | komponen | ya | Lulus — Finance: Keuangan (Beranda 3, Piutang 6, Hutang 2, Kas & Bank 4, Antar-PT), Akuntansi & Pajak (Buku Besar 2, Pajak › Faktur Keluaran); tanpa Tutup Buku, Laporan, Aset Tetap; + Pemetaan Akun |
| U8 | komponen | ya | Lulus — Sales: Keuangan `{ar-aging: [collection-worklist, finance-cases], cash-bank: [petty-cash]}`; SDM `{hr-kpi-hub: [sales-performance]}` |
| U9 | komponen | ya | Lulus — Gudang: Keuangan `{accounts-payable: [contra-bons], interco-transactions}`; tanpa Akuntansi & Pajak (Admin Gudang sama) |
| U10 | komponen | ya | Lulus — Admin Sales: tanpa Hutang; memuat Antar-PT; tanpa Akuntansi & Pajak |
| U11 | B | ya (`nav.add` tanpa `keuangan`, `ar-aging`, `collection-worklist`) | Lulus — modul `penjualan` "Lihat saja": `nav.add` ⊇ {keuangan, ar-aging, collection-worklist, hrd, hr-kpi-hub, sales-performance}, tanpa `vendor-bills` (dibaca dari `GET /api/roles` — `GET /api/access/roles/{id}` tidak memuat `nav`) |
| U12 | B | ya (`["finance-cases","kas-aset"]`) | Lulus — dimuat `["finance-cases"]`; PATCH ulang daftar itu 200; daftar peran sama |
| U13 | B | ya (403 `vendor_bill.view`) | Lulus — 200, 200, pencairan 200 (status PD berubah); U13b: izin bawaan Finance & Manajer, Buku Besar tanpa tulis |
| U14 | penjaga | — | `verify_access_catalog_nav` 0 · `verify_view_aliases` 0 (132 cek, 22 alias) · `verify_desk_targets` 0 (33 target) · `verify_page_tabs`: INV-UI-13 0, INV-UI-14 0, **INV-UI-12 1 (sudah merah di HEAD, berkas di luar unit)** · `--self-test` 14/14 hijau (baru: hub 7 → merah; baseline 8 → hijau, 9 → merah; berkas ber-`PageTabs` di bawah tab hub → terdeteksi; alias & komentar diabaikan; kondisi ganda router terbaca) |
| U15 | penjaga | — | `audit_i18n_id` 109 → 109 (temuan identik; `bukti/MN-T1/audit_i18n_id_*.log`); "Payroll Run" dan "Chart of Accounts" tidak lagi di label menu/judul (sisa satu komentar kode `ChartOfAccounts.jsx:2`); jest U15 |
| U16 | layar (uji jalan) | — | **Dipotret** sidebar Finance 1280 px (lihat "Cek layar"; `bukti/MN-T1/menu_finance_1280.png`). Semula: Padanan: menu per peran dari konfigurasi + izin server (`bukti/MN-T1/menu_per_peran_dari_konfigurasi.json`, jest U3/U7–U10) dan U4 lapis B. Tangkapan sidebar per peran belum ada |
| U17 | layar (uji jalan) | — | **Belum diuji jalan**. Padanan: U6 (deep link + preset) dan jest `mnt1Pembungkus` (preset `saldo`/`pertanggungjawaban` membuka chip yang benar; preset `reimburse` untuk peran tanpa `accounting.view` jatuh ke chip pertama) |

`backend/tests_mem`: sebelum **638 lulus / 2 dilewati / 3 xfail** → sesudah **644 lulus / 2 dilewati / 3 xfail** (+6 uji MN-T1; uji lama yang
disesuaikan di "Menyimpang" 9). `tests/test_fe03_access_catalog.py --noconftest`: 6 lulus.

Jest seluruhnya (folder kerja terpisah, `bukti/MN-T1/jest_seluruh_ringkas.log`): HEAD 78 suite lulus / 35 gagal dimuat
(`@radix-ui/primitive/is-development` tidak termuat lokal — kendala lingkungan) / 563 uji → sesudah 80 / 35 (suite yang
sama, semua gagal dimuat radix) / **625 uji, semua lulus**. Dengan tiruan pemilih radix disisipkan ke 35 suite itu
(salinan saja, pola PK-13): HEAD 812 uji, 6 gagal → sesudah 874 uji, **6 gagal yang sama persis**
(`jest_seluruh_tiruan_radix_*.log`; kegagalan akibat tiruan, bukan unit ini). Suite yang memuat uji tersentuh unit ini
dan hanya jalan dengan tiruan (`phase3Settings`) lulus.

## Penjaga statik (sebelum → sesudah)

`hitung_penjaga.sh` (`bukti/MN-T1/penjaga_hitung_*.log`): identik kecuali baris `verify_page_tabs` (kini baris ringkasan
"1 pelanggaran total (INV-UI-12 1 · INV-UI-13 0 · INV-UI-14 0)"): `verify_auth_coverage` 28, `verify_ui_standard` 15,
`audit_i18n_id` 109, `audit_create_modal` 6, `verify_page_tabs` 1, `verify_to_list_bound` 6, `verify_entity_label` 2,
lainnya PASS/0. Daftar STATIK `gate.sh` (60 perintah, `statik_gate_*.log`): kode keluar sama dengan HEAD di semua
perintah kecuali `verify_ref_unlink --self-test` (merah di salinan HEAD hanya karena salinan tanpa `backend/.env`;
`verify_ref_unlink` 3 pelanggaran yang sama di kedua pohon). `verify_role_gate_ui` PASS + uji-diri; `audit_config_wiring
--strict` (salinan berjalur worktree) keluar 0; `check_nav_map` PASS; `verify_codebase_map` PASS.

## Penggabungan

Dikerjakan di `1392969`; digabung di atas `eb4e0e1` (KP-T5): tab Penomoran Dokumen dipertahankan di hub Dokumen &
Cetak; `roleReach` memuat keduanya. Lapis A: nama peran uji dipendekkan ≤ 40 karakter (batas label peran). tests_mem
sesudah gabung 735.

Perbaikan susulan:
- `bcce72a` — gate `--ci` jalan 1 memerahkan dua POC lama yang menuntut sisi hutang tertutup untuk Finance (sebelum
  K-17): **E-8 G1** (cek izin efektif kini: lihat/bayar + putus tagihan, tanpa buat/ubah, tanpa verifikasi/setujui
  kontrabon, tanpa landed cost) dan **F-2** (`GET /vendor-bills` Finance pindah ke "izin baca bekerja" 200; pagar kini
  `POST /vendor-bills` 403). Dijalankan langsung: E-8 65/65, F-2 44/44.
- `c38fc92` — kotak "Bukan wewenang meja ini" di Meja Finance masih menyebut "Sisi hutang lainnya: tagihan supplier ·
  kontrabon · landed cost"; kini "Membuat tagihan pemasok · memverifikasi & menyetujui kontrabon · landed cost".
- Penjaga `page_tabs` berganti nama di gate (INV-UI-12 → INV-UI-12/13/14), jadi pembanding garis dasar mencatatnya
  "lebih merah" + "tidak dijalankan"; merahnya sama dengan garis dasar (INV-UI-12: `wms/InventoryStockView.jsx`, berkas
  lama di luar unit ini), INV-UI-13 dan INV-UI-14 hijau.

## Cek layar

Sidebar peran Finance (`finance@`, 1280 px, data acuan): Keuangan = Beranda Keuangan, Piutang, Hutang, Kas & Bank, Antar-PT;
Akuntansi & Pajak = Buku Besar, Pajak (Tutup Buku, Laporan, Aset Tetap tidak tampak — Finance tidak berizin); Landed Cost
tidak di Keuangan. Sesuai tabel unit. Temuan di layar tujuan **Beranda Keuangan** (Meja Finance, layar lama):
- Teks batas wewenang bertentangan dengan izin baru → diperbaiki `c38fc92`.
- 11 dari 13 kartu antrean bernilai 0 mendominasi layar; tombol melayang "Bantuan & Panduan" menutupi angka kartu kanan
  bawah. Di luar lingkup unit (MN-T1 tidak mengubah isi layar) → diusulkan sebagai tugas terpisah.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli), tiap jalan sesudah `restore_demo` (data acuan; tiga skrip seed yang sama
seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`).

| Jalan | Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|---|
| 1 (`eef7bb9` — KP-T5, MN-T1, PK-38) | `--quick` | 14 FAIL | 16 | 1 (ganti nama, lihat bawah) | 2 (`config_wiring` + uji-diri, sejak KF-T2) |
| 1 (`eef7bb9`) | `--ci` | 43 FAIL | 43 | **3** | 2 |
| 2 (`3092d92` — + POC `bcce72a`, PK-40 `a78f552`, cek visual `d1c090f`·`f2bf995`·`c38fc92`) | `--quick` | 14 FAIL | 16 | 1 (ganti nama) | 2 |
| 2 (`3092d92`) | `--ci` | 41 FAIL | 43 | 1 (ganti nama) | 2 |

- **`guard:page_tabs`** tercatat "lebih merah" + "tidak dijalankan" karena MN-T1 mengganti namanya (INV-UI-12 →
  INV-UI-12/13/14). Merahnya sama dengan garis dasar: INV-UI-12 pada `features/wms/InventoryStockView.jsx` (berkas lama,
  tidak disentuh unit mana pun hari ini); INV-UI-13 dan INV-UI-14 hijau. Bukan merah baru.
- Jalan 1 `--ci`: **POC F-2** dan **POC E-8 G1** merah karena izin bawaan Finance hutang (K-17, MN-T1/PK-38) — POC masih
  menuntut sisi hutang tertutup. Disesuaikan di `bcce72a` (rincian di laporan MN-T1); jalan 2 keduanya hijau.
- Penjaga statik per hitungan (`hitung_penjaga.sh`, karena gate hanya membandingkan PASS/FAIL) sama dengan sebelum unit.


## Menyimpang dari blueprint

1. **U3 dan U4 hijau di kode lama** — keduanya invarian yang sudah berlaku di menu lama (U3) dan di endpoint yang tidak
   diubah unit ini (U4). Bukti merah U3 = uji mutasi (Finance tanpa `vendor_bill` → terdeteksi; merah di lama). U4
   menjaga tabel bantu supaya unit berikut tidak memutus pasangan izin ↔ endpoint.
2. **Enam judul halaman**, bukan lima: `petty-cash` (dulu id hub, kini view pembungkus) juga butuh judul (`check_nav_map`
   CHECK 5).
3. **`HOME_CHOICES` Meja Finance** `nav_id` ikut `finance-tower` (selain `home_nav_id` peran finance) — peran kustom yang
   memilih Meja Finance sebagai halaman awal kalau tidak menyorot id menu yang sudah tidak ada.
4. **Tombol memutus kredit bergerbang izin** (`CreditOverridesPanel`, `can(…, "credit_override", "approve")`) — tanpa itu
   Finance (kini melihat tab Kredit & Plafon, "tanpa hak memutus") mendapat tombol yang pasti 403. Isi layar lain tetap.
5. **`hidden_views` dibersihkan umum**: semua id yang tidak dikenal katalog (bukan hanya `kas-aset`) dibuang saat dimuat,
   di memori saja (tanpa menulis data — H3). Alasan: daftar yang dimuat lalu disimpan ulang editor ditolak `_clean_hidden`.
6. **Katalog modul — dua pencabutan tambahan**: `sales_force` juga mencabut `settings-hub` (tidak ada lagi tab modul itu di
   Pengaturan); `ar` mencabut `meja-peran` (Meja Finance bukan lagi butir grup Meja Peran). Ditambah
   `VIEW_RESOURCE_OVERRIDES["incentive-schemes"] = ["sales_force"]` (sama dengan `incentive-rates`; dulu sub-tab CRM
   bergerbang `sales_force.view`, bukan `credit_override`). Modul `payable` tidak mencabut `pembelian`/`accounts-payable`
   (masih dibutuhkan Landed Cost dan Hutang — "kecuali masih dibutuhkan tab lain").
7. **Bentuk berkas baseline**: `hub_tab_limit.json` = `{"_catatan": …, "hubs": {"products-pricing": 8, "purchase-orders": 7}}`,
   `third_level_tabs.json` = `{"_catatan": …, "files": [41 berkas]}` (pola `_catatan` baseline lain). Isi INV-UI-14 =
   keadaan sesudah unit (41 berkas, termasuk `CrmView.jsx` tiga sub-tab, `CreditOverridesPanel.jsx`, `CollectionWorklist.jsx`,
   `GeneralLedger.jsx`). `verify_page_tabs.py` kini mencetak satu baris ringkasan gabungan di akhir.
8. **U5 — dua id hub mendarat di tab pertama lain** (`hr-kpi-hub` admin/manajer → Kinerja Sales, dulu KPI Karyawan;
   `cash-bank` Finance → Rekening & Saldo, dulu Transaksi Kas) karena urutan/isi tab baru. Dicatat eksplisit
   `ROLE_REACH_RELANDED` (roleReach + serverAccessReach): mendarat persis di tab tercatat DAN layar lama tetap terjangkau
   (diperiksa). Baseline tidak dibuat ulang. Usulan koreksi U5 di bawah.
9. **Uji lama disesuaikan (disengaja)**:
   - `navAccess.test.js`: induk Antar-PT kini Keuangan (cr_interco, turunan Manajer, admin); Akuntansi penuh = Buku
     Besar, Tutup Buku (3 tab), Laporan, Aset Tetap + Beranda Keuangan & Kas Kecil; Sales kini SENGAJA punya grup Keuangan.
   - `viewAliases.test.js`: label palet/breadcrumb "Profitabilitas", "Konsolidasi", Antar-PT di Keuangan (+ dua baris
     breadcrumb baru); sub-judul uji diletakkan sebelum Antar-PT (grup Keuangan kini memuat sales).
   - `roleReach.test.js`, `serverAccessReach.test.js`: `ROLE_REACH_ADDITIONS` (+admin/manager empat tab bekas CRM, manajer
     `finance-desk`; sales/sales_admin `finance-cases` IA-06 + dua tab; finance 11 view K-09/K-17/UX-17/IA-06) dan
     `ROLE_REACH_RELANDED`.
   - `phase3Settings.test.js`: Finance melihat Pengaturan › Keuangan & Pajak › Pemetaan Akun (IA-06); rumah kunci komisi
     `nav: "hr-kpi-hub"`.
   - `prt7TombolIzin.test.js` U7/U8: CRM tak lagi memuat kedua tab; gerbang izin diuji di tempat barunya (Skema =
     `sales_force` lewat katalog akses; Kredit & Plafon terbaca dengan `customer.view`, memutus diuji `mnt1Pembungkus`).
   - `test_PRT6_layar_peran.py` U4/U6: `hrd` kini sudah dibuka modul Pesanan (Kinerja Sales = `order.view`), jadi bukan
     menu tambahan; `hr-people` tetap tambahan.
   - `test_PRT9_izin_bawaan.py`: `TAMBAHAN_SESUDAH` + `MNT1_DEFAULT_PAIRS`.
10. **Butir kredit Pusat Persetujuan** (`approvalInboxData.js`) membuka Piutang › Kredit & Plafon (dulu CRM, mendarat di
    sub-tab Pelanggan).
11. **`config_catalog_core.py` — teks contoh satu kunci** (`notif.reminder_recipients`): "… izin Tagihan Supplier — Bayar"
    → "… izin bayar tagihan pemasok". Penjaga KF-T4 (`verify_config_text` T6) mengecualikan kata "Supplier" hanya bila
    menjadi label menu; label tab "Tagihan Supplier" kini "Tagihan" (spesifikasi), sehingga contoh itu memerah
    (`test_KFT4_U1`). Penjaga tidak dilonggarkan; teks contoh diganti istilah glosarium. Berkas ini wilayah KF-T7 —
    satu baris, titik gabung.
12. **Teks tempat rumah komisi** (`SettingsHub.jsx` tautan "Bawaan komisi sales", `EntityMastersView.jsx` jenis master)
    → "SDM › Kinerja & Insentif › Target & Aturan"; kicker `incentive-rates` "SDM · Kinerja & Insentif".
13. **U13 diperketat**: selain "bukan 403", pencairan di database tiruan = 200 dan status PD berubah.

## Usulan koreksi blueprint (teks pengganti persis)

- U5, kolom "Hasil yang diharapkan":
  > Lulus: tiap id lama tiap peran masih mendarat di layar yang sama atau di tujuan aliasnya; id menu/hub yang tab
  > pertamanya berubah karena urutan tab baru (`hr-kpi-hub` admin/manager → `sales-performance`; `cash-bank` finance →
  > `bank-accounts`) dicatat di `ROLE_REACH_RELANDED` dan layar lamanya tetap terjangkau
- U14, kolom "Hasil yang diharapkan":
  > Semua 0 temuan untuk pemeriksaan unit ini (INV-UI-13, INV-UI-14) dan tiga penjaga lain; pelanggaran yang sudah ada
  > di HEAD (INV-UI-12 `features/wms/InventoryStockView.jsx`) dilaporkan apa adanya; kasus self-test baru lulus
- "Keadaan sekarang" butir 2, kolom Fakta: "… empat di antaranya keuangan atau insentif; dua digerbang izin (`can`, PR-T7)".
- Bagian Layar, `navMeta.js`: "judul halaman untuk enam view (lima view baru + `petty-cash`)".
- Tabel "Katalog modul", baris `sales_force`, kolom dicabut: "`settings-hub`, `settings-sales`"; baris `ar_receipt…`,
  kolom dicabut: "`meja-peran`".
- U3/U4: tambahkan catatan "invarian — hijau juga di kode lama; bukti merah U3 lewat mutasi izin".

## Asumsi

- `ASUMSI` spesifikasi dipakai apa adanya (id lama dipertahankan sebagai induk; pembungkus tidak mengubah isi layar;
  Kinerja Sales tetap bagi sales sampai KM-T5; Pesanan Pembelian 7 tab di baseline; izin bayar memakai `vendor_bill.pay`,
  `contra_bon.pay`).
- Nilai `preset.bagian` Kas Kecil: `pengajuan`, `pertanggungjawaban`, `reimburse` (spesifikasi hanya `{bagian: …}`).
- Chip pembungkus mengikuti izin endpoint layar lamanya (Titipan: `accounting.view`/`penalty.issue`; Saldo kredit:
  `ar_receipt.view`; Pengajuan dana: `cash_advance.view`; Pertanggungjawaban: `cash_settlement.view`; Hutang reimburse:
  `accounting.view`) — spesifikasi hanya menyebut chip terakhir; untuk peran bawaan A M F hasilnya sama.
- Label tab "Landed Cost" mengikuti tabel spesifikasi; kamus izin server sejak PR-T6 menamai sumber dayanya "Biaya Masuk
  Barang" (keraguan, bukan diubah).
- Manajer kini melihat Beranda Keuangan › Perlu Tindakan (Meja Finance; ia memegang `payment_variance.decide`, kolom
  "Peran bawaan" A M F).

## Titik henti

- H3: tidak ada migrasi data. Izin bawaan baru masuk lewat mekanisme yang ada (`sync_permission_modules`,
  `defaults_applied`) saat server mulai — sama dengan preseden PR-T9/PR-T2/PK-45; menjalankannya pada data nyata =
  keputusan pemilik. Pembersihan `hidden_views` hanya di memori.
- H7: tidak ada yang disentuh di `middleware/` maupun gerbang RFID.
- Berkas bersama yang diubah secara lokal (blok ber-komentar `MN-T1`): `navMeta.js`, `hubTabs.js`, `AppViewRouter.jsx`,
  `appViewImports.js`, `access_modules.py`, `docs/KN_13_NAVIGATION_MAP.md`; juga `permissions_config.py` (blok akhir),
  `config_catalog_core.py` (satu teks), `configGroupViews.js`/`SettingsHub.jsx` (satu baris) — titik gabung dengan KF-T7,
  PK-37, KP-T5, PK-38. PK-24/PK-38 memuat baris izin Finance yang sama ("lewati bila sudah ada"): blok MN-T1 idempoten.

## Hambatan lingkungan

- U17 (tautan ber-preset membuka chip yang benar) belum diklik di peramban; sidebar hanya dipotret untuk Finance.
- Jest: 35 suite gagal dimuat karena `@radix-ui/...` (sama di HEAD); ESLint tidak terpasang lokal.

## Yang perlu direview

- Daftar `third_level_tabs.json` (41 berkas) — memuat juga layar yang tab internalnya sudah ada sebelum unit ini
  (Buku Besar 5 tab, dst.); penyatuannya MN-T2.
- `ROLE_REACH_RELANDED` sebagai mekanisme baru di uji jangkauan.
- Kemungkinan bentrok gabung: blok `MN-T1` di `access_modules.py` (sesudah `_PRT5_NAV`), `permissions_config.py` (akhir
  berkas), PAGE_META/ROLE_HOME di `navMeta.js`, grup Keuangan di `navStructure.js`.

Status: implemented_pending_review.

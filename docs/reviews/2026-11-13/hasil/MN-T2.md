# MN-T2 — Penyatuan layar keuangan: titipan, kas kecil, tutup buku, beranda keuangan, slip gaji

- Commit awal: `38c715f` (dikerjakan, worktree terlepas) · digabung di atas `c3fa3f8` (sesudah KM-T2, PY-T3; berkas kode
  sama dengan `649b7dc`)
  - Commit akhir: `1a9c2cf` (kode) · `b7837de` (cek layar)        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: — (unit fitur rancangan `01` §3 butir 4–8) · keputusan K-18, K-46
- Spesifikasi: `docs/blueprint/unit/MN-T2.md`; standar `02` §3.1 (Z1, Z2), §3.4 (N3), §4 (L1–L8), §5 (D1, D4), §6, §7

## Cek ulang "Keadaan sekarang" (di `38c715f`)

| # | Hasil |
|---|---|
| 1 | Berlaku, bergeser: `AdvanceReportView.jsx:25`, `routers/ar_aging.py:96` (`ar_advance_report`, izin `accounting.view`/`penalty.issue`) |
| 2 | Berlaku, bergeser: `StoreCreditView.jsx:36`, `routers/store_credit.py:72` (`list_summary`, `ar_receipt.view`); pakai = `ar_receipt.create`, sesuaikan/balik = `ar_receipt.void` |
| 3 | Berlaku, bergeser: `routers/ar_receipts.py:63` (`deposit_balance`) — tidak diubah (di luar lingkup → PK-19) |
| 4 | Sebagian bergeser: tiga layar `CashAdvancesView.jsx:43`, `SettlementsView.jsx:36`, `ReimbursePayablesView.jsx:22`; **hutang reimburse sudah `cash_settlement.view`** sejak PK-24 (`routers/cash_advances.py:111/114`), bukan `accounting.view` |
| 5 | Bergeser: `STAGE_BY_STATUS` tidak ada lagi — KP-T4 memindah jenjang ke Aturan Persetujuan (`cash_advance_service.py:47` `_STAGE_KEY`, `:51` `_level_status` dari `approval_kinds`). Tahap layar baru diturunkan dari status PD/LPJ, tidak dari tabel itu |
| 6 | Berlaku, bergeser: `ClosingView.jsx:57`, `PeriodUnlockView.jsx:48`, `PostingFailuresView.jsx:29` (sudah tab satu hub sejak MN-T1, tanpa tautan antar-layar) |
| 7 | Berlaku, bergeser: `GeneralLedger.jsx:220–221` (render tab `recon`/`suspense`; impor `:24–25`) |
| 8 | Berlaku, bergeser: `routers/closing.py:52` (`preview_closing`), `:71` (`closing_checklist`); tautan `closing_checklist.py:98` (`suspense_nol` → `general-ledger` `{tab: suspense}`), `:145` (`stok_cocok` → `{tab: recon}`) |
| 9 | Berlaku, bergeser: `routers/posting_failures.py:95` (`count_posting_failures`), `routers/period_unlocks.py:58` (`active_unlocks`) |
| 10 | Berlaku, bergeser: `FinanceDesk.jsx:25`, `WaitingBoardsStrip` `:90`; `routers/work_desks.py:235` (`finance_desk`, `payment_variance.decide`); `routers/home.py:101` (`home_finance`, PK-17 `contra_bon.view`/`vendor_bill.view`) |
| 11 | Berlaku, bergeser: `FinanceTowerView.jsx:22`, `BiFinanceView.jsx:51`, `AdminHome.jsx:46` (KPI Tertagih/Belum Lunas/Piutang Lewat Tempo), `ManagerHome.jsx:31` (KPI Tertagih/Piutang berjalan/lewat tempo) |
| 12 | Berlaku + temuan: `CoreWidgets.jsx:246` lencana pada grup `akuntansi`; baris `:278` menempel ke butir menu `posting-failures` yang **tidak ada lagi** sejak MN-T1 (kode mati) |
| 13 | Sudah tidak berlaku (PY-T1): `PayrollRunsView.jsx:407` tabel slip + panel "Cari slip"; tab Slip Gaji dicabut, `hr-payslips` alias. Dibuktikan U12/U13 |

Prasyarat: MN-T1, PK-18, PK-24, PK-43, PY-T1 `selesai` (STATUS.md). Butir 6 tidak ditunda.

## Status per butir

| Butir | Status | Inti |
|---|---|---|
| 4 Titipan & Saldo Kredit | dikerjakan | `CustomerCreditView.jsx` ditulis ulang: satu tabel per pelanggan |
| 5 Kas Kecil | dikerjakan | endpoint `GET /api/petty-cash/worklist` + `PettyCashView.jsx` ditulis ulang; tiga layar daftar lama dihapus |
| 6 Tutup Buku | dikerjakan | tautan dua butir daftar periksa; dua seksi lipat (`ClosingParts.jsx`); Jurnal tinggal 3 tab |
| 7 Beranda Keuangan | dikerjakan | `FinanceDesk.jsx` = Perlu Tindakan berkelompok berizin; kartu Keuangan di dua beranda; lencana di Tutup Buku |
| 8 Slip gaji | tidak berlaku (PY-T1) | U12/U13 hijau tanpa perubahan kode |

## Perubahan (ringkas)

**Server.** `GET /api/petty-cash/worklist?stage&q&page&page_size&entity_id` (`routers/cash_advances.py`,
`require_any_permission` `cash_advance.view` · `cash_settlement.view` — pernyataan pertama, Z1). Layanan
`cash_advance_service.petty_cash_worklist` memakai kueri daftar yang SAMA dengan `GET /cash-advances` dan
`/cash-advance-settlements` (diekstrak: `cash_advance_query`, `settlement_query`; aturan PT tidak disalin), dibaca dengan
kursor (tanpa batas 1000, D4), dipotong per halaman dengan `total` + `stage_counts` (jumlah per tahap atas hasil cari, tidak
atas saringan tahap). Tahap: `diajukan` (PD belum cair), `dicairkan` (cair, LPJ tidak ada/draf/ditolak), `dipertanggung-
jawabkan` (LPJ diajukan/disetujui, atau dijurnal dengan sisa `open|returning` / hutang reimburse `open`), `selesai`.
Baris: `{id, number, entity_id, requester, purpose, divisi, amount, stage, status, settlement|null, updated_at}`;
`settlement = {id, number, status, spent, refund_due, reimburse_due}` — sisa/hutang dari catatan LPJ dijurnal, atau
perkiraan pengeluaran − uang muka untuk LPJ draf/diajukan/disetujui. 400 "Tahap tidak dikenal.". Daftar periksa:
`closing_checklist.CHECKS` butir `suspense_nol` → `{view: "closing", preset: {seksi: "akun-sementara"}}`, `stok_cocok` →
`{…, seksi: "persediaan"}`; kalimat butir/pesan blokir Suspense menunjuk seksi baru (`closing_service._suspense_message`).
Status, nilai, dan aturan penghalang tidak diubah.

**Layar.**
- *Kas & Bank › Kas Kecil* (`PettyCashView.jsx`): banner PT, kotak cari, chip tahap berjumlah (Semua · Diajukan · Dicairkan ·
  Dipertanggungjawabkan · Selesai), tabel `ResponsiveTable` berhalaman (`KNPager` + "N pengajuan dana"), aksi menempel kanan
  (Bayar bila hutang reimburse & `cash_settlement.pay`, selain itu Buka). Panel = `DetailModal` berisi `CashAdvanceDetail` +
  `SettlementDetail` (atau bilah "Pertanggungjawabkan" → `SettlementForm` ber-PD terpilih); "Ajukan dana" =
  `EntityGatedButton` + `EntityGateNote` → `CashAdvanceForm`. Fokus dokumen PD/LPJ (PK-44) membuka panelnya.
- *Piutang › Titipan & Saldo Kredit* (`CustomerCreditView.jsx`): `gabungPelanggan` dari `/ar/advance-report` + `/store-credit`;
  kolom persis spesifikasi, kepala Deposit/Saldo kredit berketerangan; saringan chip berjumlah; baris dibuka = pesanan
  penyumbang (pil umur `agingBuckets`) + saldo kredit per PT berriwayat (`/store-credit/ledger`); Pakai saldo
  (`ar_receipt.create`), Sesuaikan & Balik (`ar_receipt.void`) per PT — mati + "Pilih satu PT untuk mengubah saldo." di
  Semua PT; kolom yang sumbernya tidak boleh dibaca peran itu tidak ditampilkan (keterangan), bukan 0.
- *Tutup Buku* (`ClosingView.jsx` + `ClosingParts.jsx` baru): seksi lipat "Persediaan vs buku besar" (`InventoryReconTab`) dan
  "Akun sementara" (`SuspensePanel`) di bawah pratinjau, dimuat saat dibuka; `ClosingChecklistPanel` `onOpenSection`
  (tautan `view === "closing"` + `seksi` membuka seksi tanpa navigasi); preset `{seksi}`. `Labeled`/`MiniStat` dipindah ke
  `ClosingParts.jsx` (batas 500 baris, kini huruf ≥ 12 px dan warna token).
- *Jurnal* (`GeneralLedger.jsx`): 3 tab; preset lama `{tab: recon|suspense}` → `go("closing", {preset: {seksi}})` bila peran
  boleh membuka Tutup Buku; tautan "Rekonsiliasi persediaan dan akun sementara kini di Tutup Buku".
- *Beranda Keuangan › Perlu Tindakan* (`FinanceDesk.jsx`): `PERLU_TINDAKAN` (11 kelompok; tujuh nama spesifikasi + empat antrean
  meja lama yang tetap ada), `susunKelompok` dari `/finance/desk` (bila `payment_variance.decide`), `/home/finance` (bila
  `contra_bon.view`/`vendor_bill.view`) dan `/finance/posting-failures` (bila `accounting.view` dan boleh membuka Posting Gagal);
  kelompok tampil hanya bila berizin dan berisi; baris = `DeskQueueCard` (satu tombol), Terbitkan faktur & Catat kwitansi
  (`ARReceiptModal`) tetap langsung; galat per sumber; kosong "Tidak ada yang perlu ditindak hari ini.".
- *Beranda Admin / Dasbor Manajer*: `FinanceHomeCard.jsx` (baru) menggantikan KPI Tertagih · Belum Lunas · Piutang Lewat Tempo
  (Admin) dan Tertagih · Piutang berjalan · Piutang lewat tempo (Manajer); tiga angka `/finance/tower` + "Buka Beranda
  Keuangan".
- *Sidebar* (`CoreWidgets.jsx`): lencana posting gagal di entri `closing` (Tutup Buku); dari grup Akuntansi & Pajak dicabut.
- *Router*: rute cadangan `cash-advances`/`settlements`/`reimburse-payables` → `PettyCashView bagianAwal`, `advance-report`/
  `store-credit` → `CustomerCreditView saringanAwal`; alias `viewAliases.js` tetap (`preset.bagian` dipetakan ke chip/saringan).
- *Dihapus* (sesudah pencarian pemakai, `00` §7 butir 3): `CashAdvancesView.jsx`, `SettlementsView.jsx`,
  `ReimbursePayablesView.jsx`, `AdvanceReportView.jsx`, `StoreCreditView.jsx`; impor `appViewImports.js`; entri
  `NAVIGATE_DISETUJUI` dua berkas di `scripts/audit_create_modal.py`. Komponen detail & form tetap.

## Berkas berubah

| Berkas | Isi |
|---|---|
| `backend/routers/cash_advances.py` | endpoint worklist |
| `backend/services/cash_advance_service.py` | `cash_advance_query`, `settlement_query`, `WORKLIST_STAGES`, `worklist_stage`, `petty_cash_worklist` |
| `backend/services/closing_checklist.py`, `closing_service.py` | dua tautan + kalimat |
| `frontend/src/features/pettycash/PettyCashView.jsx` | ditulis ulang |
| `frontend/src/features/finance/CustomerCreditView.jsx` | ditulis ulang |
| `frontend/src/features/finance/FinanceDesk.jsx` | ditulis ulang (Perlu Tindakan) |
| `frontend/src/features/finance/ClosingView.jsx`, `ClosingParts.jsx` (baru), `ClosingChecklistPanel.jsx`, `GeneralLedger.jsx` | butir 6 |
| `frontend/src/features/home/FinanceHomeCard.jsx` (baru), `AdminHome.jsx`, `ManagerHome.jsx` | kartu Keuangan |
| `frontend/src/components/CoreWidgets.jsx` | lencana |
| `frontend/src/AppViewRouter.jsx`, `appViewImports.js`, `config/navMeta.js` | rute cadangan, impor, judul `finance-desk` |
| `frontend/src/features/finance/StoreCreditModals.jsx`, `pettycash/CashAdvanceDetail.jsx`, `pettycash/SettlementCashModal.jsx` | komentar pemakai |
| 5 berkas layar daftar lama | dihapus |
| `scripts/audit_create_modal.py`, `scripts/guardrails/baselines/third_level_tabs.json` | entri berkas terhapus; baseline dikencangkan (41 → 40) |
| Uji baru | `backend/tests_mem/test_MNT2_layar_keuangan.py` (U3–U8, U11) · jest `features/__tests__/mnt2LayarKeuangan.test.js` (U1, U2, U9, U10, U12, U13, U14 + padanan U16/U17) · lapis A `backend/tests/test_bp_MNT2_layar_keuangan.py` (ditulis, belum dijalankan) |
| Uji lama disesuaikan (disengaja) | lihat "Menyimpang" 8 |
| Fixture | `config/__tests__/fixtures/view_main_permission.json` (`petty-cash` → `/api/petty-cash/worklist`) |
| Dokumen | `docs/KN_13_NAVIGATION_MAP.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (§9.25 di HEAD gabungan; §9.23 di W), `memory/PRD.md`, `CODEBASE_MAP.md` (generator) |

## Uji penerimaan

Merah di kode lama: berkas uji final dijalankan pada berkas `38c715f` (`bukti/MN-T2/merah_kode_lama_tests_mem.log`,
`jest_merah_kode_lama.log`). Hijau: `jest_hijau_kode_baru.log`, tests_mem penuh.

| ID | Lapis | Merah di lama | Hasil |
|---|---|---|---|
| U1 | komponen | ya (tidak ada tabel gabungan) | Lulus — satu baris C: 2.000.000 · 500.000 · 300.000 · jumlah 2.800.000; kepala kolom berketerangan |
| U2 | komponen | ya | Lulus — Semua PT: Pakai saldo, Sesuaikan, Balik mati + `title` + kalimat tertulis |
| U3 | B | ya (404) | Lulus — `total` 4; `stage_counts` 1/1/1/1; halaman 2 ukuran 3 = 1 baris |
| U4 | B | ya (404) | Lulus — satu baris PD-3; `reimburse_due` 300.000 = 1.800.000 − 1.500.000 |
| U5 | B | ya (404) | Lulus — himpunan id = `GET /api/cash-advances` akun itu; `reimburse_due` null |
| U6 | B | ya (404) | Lulus — Sopir 403, pesan tanpa kode izin |
| U7 | B | ya (404) | Lulus — 400 "Tahap tidak dikenal." |
| U8 | B | ya (tautan `general-ledger`) | Lulus — dua tautan `closing` + `preset.seksi`; urutan 11 butir PK-43 tetap; `can_close` = tanpa `blocking` |
| U9 | komponen | ya | Lulus — klik Buka pada `suspense_nol`: seksi Akun sementara terbuka, `onNavigateTo` tidak dipanggil; Posting Gagal = `posting-failures` (tab hub `closing`) |
| U10 | komponen | ya | Lulus — `{tab: suspense}` → `go("closing", {preset: {seksi: "akun-sementara"}})`; `{tab: recon}` → `persediaan`; Tutup Buku ber-preset membuka seksinya |
| U11 | B | ya (404) | Lulus — Manajer Kosong 403; admin Semua PT 200, tiap baris ber-`entity_id` (5 baris: 4 KSC + 1 KANDA); tombol tulis mati di layar = U2 + uji Kas Kecil "Semua PT" |
| U12 | komponen | ya (5 tab) | Lulus — Jurnal · Neraca Saldo · Buku Besar; hub Penggajian tanpa `hr-payslips` |
| U13 | komponen | **tidak** (sudah PY-T1) | Lulus — `hr-payroll-runs` |
| U14 | komponen | ya | Lulus — Finance fixture tanpa `vendor_bill.view` & `contra_bon.view`: tanpa Hutang jatuh tempo & Kontrabon menunggu, `/home/finance` tidak diminta; Uang masuk tampil. + Finance penuh: kedua kelompok tampil, baris Kontrabon membuka `contra-bons` |
| U15 | penjaga | — | `verify_page_tabs` INV-UI-13/14 0 (INV-UI-12 1 = sudah merah di HEAD, berkas lain); `verify_view_aliases` 0; `verify_access_catalog_nav` 0; `verify_desk_targets` 0; `roleReach`/`serverAccessReach` hijau; baseline `third_level_tabs.json` 41 → **40** (lihat Menyimpang 6) |
| U16 | layar (uji jalan) | — | **Belum diuji jalan** (integrator). Padanan jest: chip berjumlah, baris berlabel tahap & sisa, panel PD + LPJ, Pertanggungjawabkan → form LPJ, Bayar per baris |
| U17 | layar (uji jalan) | — | **Belum diuji jalan**. Padanan jest U9/U10 + preset alias → chip/saringan |

## Angka uji

| | W (basis `38c715f`) sebelum | W sesudah | T (`649b7dc` + MN-T2) |
|---|---|---|---|
| tests_mem | 2045 lulus / 2 dilewati / 2 xfail | 2052 lulus / 2 / 2 (+7 uji MN-T2; jalan penuh 2050 + 2 gagal PK-44 → rute cadangan eksplisit dikembalikan, kedua uji hijau — Menyimpang 11) | HEAD murni 2101 / 2 / 2 → T **2108 lulus / 2 dilewati / 2 xfail, 0 gagal** (+7) |
| jest seluruh | 125 suite lulus / 35 gagal dimuat (cmdk/radix) / 995 uji lulus | 126 / 35 (suite sama) / 1006 lulus | HEAD 127 / 35 / 1018 → T 128 / 35 (suite sama) / **1029 lulus** |
| jest 35 suite + tiruan cmdk | 31 lulus / 5 gagal · 257 uji lulus / 9 gagal | 31 / 5 · 257 / 9 — kegagalan identik (akibat tiruan) | — |

Suite yang hanya jalan dengan tiruan dan disentuh unit ini (`decisionsD1`, `phase3P4Finance`, `phase3P4Popups`,
`roleGateSweep`) lulus dengan tiruan.

## Penjaga statik (sebelum → sesudah)

`hitung_penjaga.sh` W: identik kecuali **`verify_ui_standard` 13 → 11** (ClosingView: `font_lt12` & `hex` kembali di bawah
baseline). `verify_auth_coverage` 26 → 26 (endpoint baru berizin di pernyataan pertama), `audit_i18n_id` 103 → 103,
`audit_create_modal` 6 → 6, `verify_page_tabs` 1 → 1 (INV-UI-12, `wms/InventoryStockView.jsx`), `verify_to_list_bound` 5 → 5,
`verify_entity_label` 2 → 2. `verify_role_gate_ui` 31/0 (+ uji-diri hijau), `verify_posting_coverage` 138/0,
`verify_cash_single_door` 736/0, `verify_atomic_claim` 161/0 (endpoint baca), `verify_detail_modal` 29/0 (30 → 29 cek: dua
pop-up layar lama → satu), `verify_config_fallback` (+`--entity`) 159/0, `verify_payment_vocab` 0, `audit_config_wiring
--strict` keluar 0, `check_nav_map` PASS, `verify_codebase_map` PASS.

Di T (`c3fa3f8` + MN-T2) terhadap HEAD murni (`bukti/MN-T2/penjaga_hitung_HEAD.txt` → `penjaga_hitung_T.txt`): identik kecuali
**`verify_ui_standard` 13 → 11**. `verify_role_gate_ui` 31/0 (+ uji-diri), `verify_config_fallback` (+`--entity`) 159/0,
`verify_payment_vocab` 0 (1836 → 1833 cek, berkas layar lama terhapus), `verify_access_catalog_nav` 0,
`verify_view_aliases` 0, `verify_desk_targets` 0, `verify_cash_single_door` 740/0, `verify_detail_modal` 30 → 29 cek /0,
`audit_config_wiring --strict` (salinan berjalur T) keluar 0, `check_nav_map` (salinan berjalur T) PASS. ESLint pada 12 berkas
layar yang diubah: 0 galat (6 peringatan "eslint-disable tak terpakai" pada baris lama).

## Penggabungan

HEAD tujuan dibaca `c3fa3f8` (sesudah `649b7dc` PY-T3(b), `4b219c4` KM-T2; dua commit terakhir hanya STATUS/TRACKER/laporan).
T = worktree terpisah, `git checkout --detach` HEAD itu + `backend/.env`. Per berkas (`git status --porcelain -uall` W, tanpa
`hasil/`):

| Berkas | Cara | Keputusan |
|---|---|---|
| 30 berkas kode/uji yang sama di B dan HEAD; 5 layar lama | salin dari W / hapus | — |
| 5 berkas baru (uji MN-T2 ×3, `ClosingParts.jsx`, `FinanceHomeCard.jsx`) | salin | — |
| `frontend/src/AppViewRouter.jsx`, `appViewImports.js`, `config/navMeta.js`, `config/__tests__/fixtures/view_main_permission.json`, `docs/KN_13_NAVIGATION_MAP.md`, `memory/PRD.md` | `git merge-file` tiga arah, bersih | rute/impor PY-T3 (Kalender Libur) dan MN-T2 berdampingan |
| `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` | **bentrok** di akhir berkas | dua sisi dipertahankan: §9.23 KM-T2, §9.24 PY-T3, bagian MN-T2 dinomori **§9.25** |
| `CODEBASE_MAP.md` | **bentrok** (berkas hasil generator) | dibangkitkan ulang di T (`gen_codebase_map.py`) |

`access_modules.py` tidak berubah (fixture akses tidak dibangkitkan); tidak ada hitungan `*_KUNCI`/PRT9/indeks wajib baru.

## Cek layar (dari kode; integrator memotret 1280/1024/390)

Lebar dihitung: sidebar ±220 px, kartu ±740 px di 1024 dan ±1010 px di 1280; sel `data-table` 24 px bantalan, kepala 12 px
kapital, isi 13 px.

| Layar | (1) lebar tabel | (2) bantalan | (3) kepala kartu | (4) tombol mati | (5) status | (6) cari/saring | (7) teks izin | (8) kosong / nol |
|---|---|---|---|---|---|---|---|---|
| Kas Kecil | Nomor ±136 · [Keperluan · Pemohon ±204, hanya ≥ 1280] · Jumlah ±118 · Tahap ±203 · Pertanggungjawaban ±172 · Aksi (menempel kanan) ±88 → 1024 ±717 · 1280 ±900; di < 1280 keperluan & pemohon ditulis di sel Nomor; HP = kartu | `section-head`/`section-body`, bilah "Pertanggungjawabkan" `section-pad` | judul + muat ulang + Ajukan dana; alasan PT di bilah sendiri (`EntityGateNote`) | Ajukan dana (Semua PT): alasan tertulis | Tahap = `status-pill` + ikon (`status-draft/shipped/pending/done`); LPJ `StatusPill` ikon (`pill-*`) | `SearchBox` + chip tahap berjumlah | tanpa "bukan wewenang"; tanpa izin bayar → tombol Buka | satu pesan kosong per saringan; tanpa kartu KPI nol |
| Titipan & Saldo Kredit | Pelanggan ±183 (≥ 1280 ±223) · 4 × rupiah ±118 · Umur tertua ±84 (≥ 1280) → 1024 ±655 · 1280 ±779; tanpa kolom aksi utama; riwayat di rincian: Waktu ±164 · Jenis ±124 · Nilai ±118 · Saldo ±118 · Aksi ±94 = ±618 | idem | judul + muat ulang | Pakai/Sesuaikan/Balik (Semua PT): kalimat "Pilih satu PT untuk mengubah saldo." + `title`; Pakai saldo ≤ 0 hanya `title` (baris bersaldo ≠ 0 saja) | jenis mutasi & umur = pil ikon + teks + warna; "Dibatalkan" `status-cancelled` | cari pelanggan + 4 chip berjumlah | keterangan kolom tanpa izin, bukan 0 | satu pesan; total satu baris kaki |
| Tutup Buku (seksi) | isi seksi = komponen lama (tak berubah) | seksi `rounded-lg border` + isi `p-3` | judul seksi + keterangan (tombol `ghost-button`) | — | — | — | — | seksi tertutup tidak memuat apa pun |
| Jurnal | 3 tab | — | tautan pindah di badan kartu, bukan kepala | — | — | — | tautan hanya bila boleh membuka Tutup Buku | — |
| Perlu Tindakan | baris `DeskQueueCard` (komponen lama, lebar penuh, satu kolom) | `section-head` + `section-body` | judul + ringkasan + muat ulang | tombol baris dari komponen lama | lencana baris komponen lama | cari per kelompok (bawaan `DeskQueueCard`) | kotak "Bukan wewenang meja ini" dicabut | kelompok kosong tidak digambar; satu pesan kosong; galat tidak berbunyi kosong |
| Kartu Keuangan (beranda) | `MetricRow` 3 kartu (`sm:grid-cols-3`) | `section-head`/`section-body` | judul + tautan | — | — | — | tanpa izin → tidak digambar | nol netral (`metric-zero`); galat → kotak galat, bukan nol |

Isian tanggal/bulan peramban tidak ditambahkan. Tidak ada cek nama peran baru (`verify_role_gate_ui` 31/0).

## Menyimpang dari blueprint

1. **`reimburse_due` bergerbang `cash_settlement.view`, bukan `accounting.view`.** Spesifikasi menurunkan aturan ini dari
   "Keadaan sekarang" 4 (laporan hutang reimburse menuntut `accounting.view`); PK-24 sudah memindah laporan itu ke
   `cash_settlement.view`, jadi pemegang izin itu sudah melihat angka yang sama di laporannya. U5 sama hasilnya.
2. **Pemanggil hanya ber-`cash_settlement.view`** (tanpa `cash_advance.view`) melihat hanya PD yang ber-LPJ (tidak ada di
   spesifikasi; menghindari membuka daftar PD yang tidak boleh ia baca).
3. **Kolom Kas Kecil dirapatkan**: "Diperbarui" ditulis di sel Nomor; "Sisa kembali / hutang reimburse" di sel
   Pertanggungjawaban (dua baris); "Keperluan · Pemohon" satu kolom yang hanya tampil ≥ 1280 px. Delapan kolom terpisah =
   ±1170 px, melebihi kartu di 1280 (±1010) maupun 1024 (±740) — kesalahan (1) cek layar.
4. **Tidak ada "LPJ Baru" lepas**: pertanggungjawaban dibuat dari panel PD dicairkan ("Pertanggungjawabkan", PD terpilih);
   PT LPJ = PT PD (N1).
5. **Perlu Tindakan memuat 11 kelompok**: tujuh nama spesifikasi + Denda perlu diterbitkan, Piutang lewat jatuh tempo, Sample
   berbayar menunggu ACC bayar, Retur selesai QC — empat antrean meja lama yang tidak boleh hilang (`00` §7 butir 3). "Uang
   muka pesanan belum dikirim" (antrean pantau, bukan tindakan) tidak lagi di sini — angkanya kolom Titipan & Saldo Kredit (D1).
   Papan kontrabon/tagihan menjadi kelompok bertombol "Buka" (keputusan di layar Kontrabon), bukan papan bertombol putus;
   Pelacak SO tetap di bawah daftar.
6. **Baseline `third_level_tabs.json` berkurang satu berkas, bukan dua.** Dua pembungkus yang dimaksud spesifikasi
   (`CustomerCreditView`, `PettyCashView`) tidak pernah masuk baseline — MN-T1 membangunnya dengan `FilterChips`. Yang keluar:
   `PostingFailuresView.jsx` (sudah turun sejak PK-18). `GeneralLedger.jsx` tetap (3 tab isi yang berbeda = tab, bukan saringan).
7. **Angka ketiga kartu Keuangan = "Hutang belum dibayar"** (`ap.outstanding` tab Posisi), bukan "hutang jatuh tempo 7 hari":
   angka itu tidak ada di tab Posisi (ASUMSI spesifikasi: tidak ada angka baru). Hutang ≤ 7 hari ada di Perlu Tindakan.
8. **Uji lama disesuaikan (disengaja)**: `pk17NominalBerizin` U15/U15b (papan → kelompok; tanpa izin tidak diminta; 403 tanpa
   galat; galat lain tidak berbunyi kosong), `pk24KasKecil` L5 (Bayar per baris kini di Kas Kecil), `pk42LayarKeuangan` U3
   (`PettyCashView` `pc-create-btn`), `phase3P4Popups` (dua uji pop-up Kas Kecil), `roleGateSweep` (Kasbon), `phase3P4Finance`
   D-12 B (pil umur di rincian Titipan), `decisionsD1` K-01 (kartu Keuangan, sumber piutang sama), `mnt1Pembungkus` (dua blok
   pembungkus pindah ke uji MN-T2), `test_PK43_alur_layar.py` U11 (tautan baru).
9. **`Labeled`/`MiniStat` dipindah** dari `ClosingView.jsx` ke `ClosingParts.jsx` (ClosingView 567 baris > batas 500), huruf
   dinaikkan ke ≥ 12 px dan warna token (G-UI). Satu kotak peringatan Suspense ClosingView ikut ke token.
10. **Judul `finance-desk`** (`navMeta.js`) "Perlu Tindakan · Pekerjaan Uang yang Menunggu" (dulu "Meja Finance · …").
11. **Rute cadangan `cash-advances` · `settlements` · `reimburse-payables` tetap tiga baris `activeView === "…"`** (merender
    `PettyCashView` + `focusDocProps`), bukan satu kondisi gabungan: peta tujuan dokumen PK-44 (`doc_refs_service.DOC_TYPES`,
    PD → `cash-advances`, LPJ → `settlements`) dijaga `test_PK44_U01/U13` yang membaca router. Peta itu tidak diubah.

## Usulan koreksi blueprint (teks pengganti persis)

- "Keadaan sekarang" butir 4: "… hutang reimburse menuntut `cash_settlement.view` (PK-24; dulu `accounting.view`)".
- "Keadaan sekarang" butir 5: "Tahap persetujuan pengajuan dana dibaca dari Aturan Persetujuan (`approval_kinds`, KP-T4)".
- Server: "Kolom `reimburse_due` hanya diisi bagi pemanggil ber-`cash_settlement.view`; bagi yang lain `null`."
- U14, kolom Persiapan: "Peran finance dengan izin dari fixture (tanpa `vendor_bill.view` dan `contra_bon.view` pada salinan
  fixture uji)" — sejak MN-T1 (K-17) Finance memegang keduanya; kelompok Kontrabon bergantung pada `contra_bon.view`.
- U15, kolom Hasil: "… baseline `third_level_tabs.json` tidak bertambah (dua pembungkus memakai chip, tidak pernah masuk
  baseline); berkas yang sudah turun dikencangkan".
- Butir 7 Layar: "… tiga angka (kas dan bank, piutang lewat jatuh tempo, hutang belum dibayar) dari endpoint yang sama dengan
  tab Posisi" — atau tambahkan angka "hutang jatuh tempo 7 hari" ke `/finance/tower` di unit lain.
- Butir 5 Layar: kolom "Diperbarui" dan "Sisa kembali / hutang reimburse" boleh menjadi baris kedua sel lain (lebar kartu).

## Asumsi

- `ASUMSI` spesifikasi dipakai (MN-T1, PK-43 selesai; angka kartu dari tab Posisi).
- Peta `preset.bagian` alias lama: `pengajuan` → Semua; `pertanggungjawaban`, `reimburse` → Dipertanggungjawabkan;
  `titipan` → Punya uang muka; `saldo` → Punya saldo kredit. `hidden_views` atas id lama tidak lagi menyembunyikan bagian
  (satu layar).
- Izin kelompok Perlu Tindakan = izin modul sumber/layar penanganannya (`PERLU_TINDAKAN`): uang masuk `ar_receipt.create`,
  selisih `payment_variance.decide`, faktur `tax_invoice.create`, nota kredit `finance_amendment.review_credit_note`, hutang
  `vendor_bill.view`, kontrabon `contra_bon.view`, posting gagal `accounting.view` (+ boleh membuka Posting Gagal), denda
  `penalty.issue`, piutang lewat tempo `accounting.view`/`penalty.issue`, sample `sample_order.approve_payment`, retur
  `sales_return.decide_compensation`. Server `/finance/desk` tidak diubah (tetap mengirim semua antrean ke pemegang
  `payment_variance.decide`; penyaringan per kelompok di layar).
- Kas Kecil: sisa/hutang LPJ yang belum dijurnal ditampilkan sebagai perkiraan.

## Titik henti

- H3: tidak ada migrasi/perbaikan data. H4/H5: tidak ada nilai peraturan, akun, atau sakelar PT. H7: tidak menyentuh
  `middleware/` maupun gerbang RFID.
- Berkas unit paralel: tidak menyentuh `hr_payroll_service.py` (PY-T3) maupun layar Capaian (KM-T2). Bentrok gabung hanya di
  dokumen/registri bersama (lihat Penggabungan).

## Keraguan / yang perlu direview

- **Finance kehilangan akses layar ke rekonsiliasi persediaan & akun sementara**: dulu tab di Jurnal (Finance melihat Buku
  Besar), kini di Tutup Buku yang tidak ada di menu Finance (MN-T1). Endpointnya tetap `accounting.view`. Bila Finance perlu,
  beri menu Tutup Buku (keputusan menu, bukan unit ini).
- Admin "Lewat Tempo per Sales" (papan tim sales) dibiarkan; KPI Insentif Sales tetap (KM-T5).
- Uji lapis A `test_bp_MNT2_layar_keuangan.py` ditulis, belum dijalankan (lingkungan A milik integrator).
- U16/U17 (uji jalan peramban) belum dijalankan.

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`b7837de`** (MN-T2 + cek
layar):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`649b7dc`: 12 / 39). `guard:page_tabs` tetap 1 pelanggaran (garis dasar). Kuitansi:
`bukti/MN-T2/gate_quick_receipt.md`, `gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- HEAD cabang tidak maju sejak pelaksana menggabung (`c3fa3f8`); T disalin apa adanya → **`1a9c2cf`** (45 berkas, 5 layar lama
  dihapus). `tests_mem` di T 2108/2/2 (pelaksana, pohon sama). Jest penuh di cabang: **1029 lulus** (35 suite gagal dimuat
  `cmdk`/`@radix-ui`, sama). Penjaga statik: `verify_ui_standard` 13 → **11**, lainnya garis dasar; `verify_role_gate_ui`
  31/0. Glosarium KN_32 §9.25.
- Lingkungan A: lapis A `test_bp_MNT2_layar_keuangan.py` **4 lulus**; `test_bp_MNT1_menu_keuangan.py` (tabel
  `view_main_permission.json` diperbarui) **3 lulus**.
- Uji jalan **U16/U17** (integrator, data acuan, peramban zona Asia/Jakarta, 1280/1024 px): Kas Kecil (satu daftar bertahap,
  chip tahap berjumlah, kosong satu kalimat), Titipan & Saldo Kredit (tabel per pelanggan = lebar kartu 762 px di 1024),
  Tutup Buku (seksi lipat "Persediaan vs buku besar" dan "Akun sementara"), Perlu Tindakan (kelompok per izin) rapi;
  `overflowX` 0 semua. **Dua cacat ditemukan dan diperbaiki (`b7837de`)**: (1) Pelacak SO aktif di Perlu Tindakan — tabel
  ±855 px di kartu 762 px, kolom "Tindak lanjut" terpotong di tepi gulir → kolom itu lekat kanan (`col-sticky-end`;
  komponen bersama `SoTrackerCard`, juga di meja Admin Sales/peran/sample); (2) kartu Keuangan di Beranda Admin — saldo Kas
  & bank negatif "-Rp 236.048.300" patah sesudah tanda minus → `MetricRow` dan `kpiValueParts` mengunci "-Rp" satu baris
  (isi teks tetap; jest terkait 69/69). Bukti `bukti/MN-T2/cek_*.png`.
- **Untuk pemilik**: Finance tidak lagi punya layar rekonsiliasi persediaan dan akun sementara (pindah dari Jurnal ke Tutup
  Buku, yang tidak ada di menu Finance sejak MN-T1); endpoint tetap terbuka untuk `accounting.view`. Bila Finance perlu,
  tambahkan Tutup Buku ke menu Finance (keputusan menu).
- Temuan di luar lingkup: `SoTrackerCard` masih memakai warna heks dan huruf < 12 px (pra-KN_37) — kolom Nilai tetap harus
  digulir di 1024 px; perapian penuh layak unit sendiri.

Pelaksana (catatan asli):

Belum dijalankan (lingkungan A milik integrator).

## Hambatan lingkungan

- Jest: 35 suite gagal dimuat karena `@radix-ui/primitive/is-development` (cmdk) — sama di basis; diuji ulang dengan tiruan
  `cmdk` (`bukti/MN-T2/jest_tiruan_cmdk_*.log`).

Status: implemented_pending_review.

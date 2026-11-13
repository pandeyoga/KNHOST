# MN-T2 — Penyatuan layar keuangan: titipan, kas kecil, tutup buku, beranda keuangan, slip gaji

| | |
|---|---|
| Gelombang | Modul — menu dan layar |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | PK-18, PK-24, PY-T1 (dan MN-T1 untuk tempatnya, PK-43 untuk butir 6; lihat "Asumsi") |
| Menutup temuan | — |
| Keputusan | K-18, K-46 |
| Standar | §3.1 (Z1, Z2), §3.4 (N3), §4 (L1–L8), §5 (D1, D4), §6, §7 |
| Lingkungan uji | B (endpoint baca baru) · uji komponen · uji jalan layar di A |

## Tujuan

Lima tempat yang sesudah MN-T1 masih berupa dua atau tiga layar lama yang ditaruh berdampingan menjadi **satu layar**
masing-masing: Titipan & Saldo Kredit, Kas Kecil, Tutup Buku, Beranda Keuangan, dan slip gaji di dalam proses gaji.
Pengguna tidak lagi berpindah layar untuk satu pekerjaan; layar lama dihapus setelah penggantinya terbukti.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`. Sesudah MN-T1, layar-layar ini sudah berada di hub barunya tetapi isinya belum
berubah (dua di antaranya dibungkus pilihan chip).

| # | Fakta | Jangkar |
|---|---|---|
| 1 | Uang Muka Pelanggan membaca satu endpoint: uang muka pesanan belum dikirim dan deposit per pelanggan | `frontend/src/features/finance/AdvanceReportView.jsx:25` (`AdvanceReportView`) · `backend/routers/ar_aging.py:95` (`ar_advance_report`) |
| 2 | Saldo Kredit membaca buku saldo kredit per PT, dengan aksi pakai, sesuaikan, dan balik | `frontend/src/features/finance/StoreCreditView.jsx:39` (`StoreCreditView`) · `backend/routers/store_credit.py:71` (`list_summary`) |
| 3 | Deposit pelanggan adalah satu angka tanpa PT dan tanpa riwayat (duplikasi no. 3 audit) | `backend/routers/ar_receipts.py:52` (`deposit_balance`) |
| 4 | Kas kecil = tiga layar dengan tiga endpoint daftar; hutang reimburse menuntut `accounting.view` | `frontend/src/features/pettycash/CashAdvancesView.jsx:40` (`CashAdvancesView`) · `frontend/src/features/pettycash/SettlementsView.jsx:31` (`SettlementsView`) · `frontend/src/features/pettycash/ReimbursePayablesView.jsx:11` (`ReimbursePayablesView`) · `backend/routers/cash_advances.py:108` (`reimburse_payables`) |
| 5 | Tahap persetujuan pengajuan dana ditentukan tabel tahap di layanan | `backend/services/cash_advance_service.py:42` (`STAGE_BY_STATUS`) |
| 6 | Tutup Buku, Buka Periode, dan Posting Gagal adalah tiga komponen tanpa tautan satu sama lain | `frontend/src/features/finance/ClosingView.jsx:43` (`ClosingView`) · `frontend/src/features/finance/PeriodUnlockView.jsx:53` (`PeriodUnlockView`) · `frontend/src/features/finance/PostingFailuresView.jsx:17` (`PostingFailuresView`) |
| 7 | Rekonsiliasi persediaan dan akun sementara berada di dalam layar Jurnal & Buku Besar sebagai tab keempat dan kelima | `frontend/src/features/finance/GeneralLedger.jsx:164` (`InventoryReconTab`) · `frontend/src/features/finance/GeneralLedger.jsx:165` (`SuspensePanel`) |
| 8 | Pratinjau tutup buku mengembalikan boleh-tidaknya ditutup dan saldo akun sementara; daftar periksa sebelas butir (`GET /api/finance/closing/checklist`) dipasang PK-43, dengan tautan butir akun sementara dan persediaan masih menunjuk layar Jurnal | `backend/routers/closing.py:48` (`preview_closing`) |
| 9 | Bahan daftar periksa lain sudah tersedia sebagai bacaan: jumlah posting gagal, jendela buka periode aktif | `backend/routers/posting_failures.py:106` (`count_posting_failures`) · `backend/routers/period_unlocks.py:50` (`active_unlocks`) |
| 10 | Meja Finance memuat dua sumber antrean: antrean meja (uang masuk, faktur pajak) dan papan hutang | `frontend/src/features/finance/FinanceDesk.jsx:25` (`FinanceDesk`) · `frontend/src/features/finance/FinanceDesk.jsx:90` (`WaitingBoardsStrip`) · `backend/routers/work_desks.py:232` (`finance_desk`) · `backend/routers/home.py:100` (`home_finance`) |
| 11 | Dua dasbor keuangan lain dan dua beranda memuat angka keuangan sendiri-sendiri | `frontend/src/features/finance/FinanceTowerView.jsx:17` (`FinanceTowerView`) · `frontend/src/features/finance/BiFinanceView.jsx:49` (`BiFinanceView`) · `frontend/src/features/home/AdminHome.jsx:46` (`AdminHome`) · `frontend/src/features/home/ManagerHome.jsx:31` (`ManagerHome`) |
| 12 | Lencana posting gagal menempel pada grup Akuntansi & Pajak | `frontend/src/components/CoreWidgets.jsx:243` (`CountBadge`) |
| 13 | Detail proses gaji sudah memuat tabel slip; tab Slip Gaji menampilkan slip yang sama lewat endpoint lain. PY-T1 (prasyarat) mencabut tab itu, memasang kotak "Cari slip", dan menjadikan `hr-payslips` alias | `frontend/src/features/hr/PayrollRunsView.jsx:202` (`payroll-payslips-table`) · `frontend/src/features/hr/PayslipsView.jsx:21` (`PayslipsView`) · `backend/routers/hr_payroll.py:212` (`list_payslips`) |

## Perubahan

### Data

Tidak ada koleksi atau field baru. Unit ini tidak menyatukan `deposit_balance` dengan buku saldo kredit; layar
menampilkan keduanya berdampingan dengan label sumbernya (D1).

### Server

Satu endpoint baca baru; ia memanggil fungsi daftar layanan yang ada sehingga aturan PT dan kepemilikan tidak disalin.

| Metode + path | Izin | Isi → jawaban | Galat |
|---|---|---|---|
| `GET /api/petty-cash/worklist?stage&q&page&page_size` | `cash_advance.view` atau `cash_settlement.view` (`require_any_permission`) | → `{items, total, page, page_size, stage_counts}`; satu baris per pengajuan dana: `{id, number, requester, purpose, amount, stage, status, settlement: {id, number, status, spent, refund_due, reimburse_due} \| null, updated_at}` | 400 "Tahap tidak dikenal." |

`stage` kas kecil dan cara menurunkannya dari status yang ada:

| `stage` | Label layar | Diturunkan dari |
|---|---|---|
| `diajukan` | Diajukan | Pengajuan belum dicairkan (draf, menunggu tiap tahap persetujuan, disetujui, ditolak) |
| `dicairkan` | Dicairkan | Pengajuan sudah dicairkan dan belum punya pertanggungjawaban yang diajukan |
| `dipertanggungjawabkan` | Dipertanggungjawabkan | Pertanggungjawaban diajukan atau disetujui, masih ada sisa kembali atau hutang reimburse |
| `selesai` | Selesai | Pertanggungjawaban selesai dan tidak ada sisa di kedua arah |

Kolom `reimburse_due` hanya diisi bagi pemanggil ber-`accounting.view`; bagi yang lain `null`.

Daftar periksa tutup buku **tidak dibuat ulang**: unit ini memakai `closing_checklist.CHECKS` hasil PK-43 dan hanya
mengubah `link` empat butirnya supaya tetap di dalam hub Tutup Buku:

| `key` (PK-43) | `link` lama | `link` baru |
|---|---|---|
| `suspense_nol` | `general-ledger` (tab akun sementara) | `{view: "closing", preset: {seksi: "akun-sementara"}}` |
| `stok_cocok` | `general-ledger` (tab rekonsiliasi) | `{view: "closing", preset: {seksi: "persediaan"}}` |
| `posting_gagal` | `posting-failures` | tetap (kini tab di hub yang sama) |
| `buka_periode_aktif` | `period-unlock` | tetap (kini tab di hub yang sama) |

Butir, status, dan aturan penghalangnya tidak diubah.

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada pasangan izin baru. View `petty-cash` dan `closing` tetap di modul yang sama seperti hasil MN-T1.

### Layar

Per butir rancangan `01` §3:

| Butir | Layar lama | Layar baru | Komponen yang dipakai ulang | Prasyarat |
|---|---|---|---|---|
| 4 | Pembungkus chip "Titipan pelanggan" · "Saldo kredit" (dua layar utuh) | **Piutang › Titipan & Saldo Kredit**: satu tabel per pelanggan | Baris rinci `AdvanceReportView` (pesanan penyumbang uang muka); modal `StoreCreditModals.jsx` (pakai, sesuaikan, balik); `agingBuckets.js` | MN-T1 |
| 5 | Pembungkus chip tiga layar kas kecil | **Kas & Bank › Kas Kecil**: satu daftar bertahap | `CashAdvanceDetail`, `CashAdvanceForm`, `SettlementDetail`, `SettlementForm`, `pettyCashShared.jsx` | PK-24, MN-T1 |
| 6 | Daftar periksa (PK-43) di Tutup Buku; rekonsiliasi persediaan dan akun sementara masih dua tab di Buku Besar | **Tutup Buku › Daftar Periksa & Tutup**: daftar periksa, pratinjau, dan dua seksi lipat dalam satu layar | `ClosingView` beserta panel daftar periksa PK-43, `InventoryReconTab`, `SuspensePanel`; tab Buka Periode dan Posting Gagal tetap | PK-18, PK-43, MN-T1 |
| 7 | Tab "Perlu Tindakan" = Meja Finance apa adanya; kartu keuangan di dua beranda | **Beranda Keuangan › Perlu Tindakan**: satu antrean; beranda admin dan manajer memuat satu kartu ringkas | Baris antrean dan `ARReceiptModal` dari `FinanceDesk`; `WaitingBoardsStrip`; `CountBadge` | PK-16, PK-17, MN-T1 |
| 8 | Tab "Slip Gaji" | Slip di dalam detail **Penggajian › Proses Gaji** — **sudah dikerjakan PY-T1**; di sini hanya diperiksa | — | PY-T1 |

**Butir 4 — Titipan & Saldo Kredit** (`CustomerCreditView.jsx` ditulis ulang). Kolom: "Pelanggan" · "Uang muka pesanan
belum dikirim" · "Deposit" · "Saldo kredit" · "Jumlah" · "Umur tertua". Kepala kolom Deposit berketerangan "Satu angka
per pelanggan, tanpa PT"; kepala Saldo kredit "Per PT, ada riwayat". Baris bisa dibuka: pesanan penyumbang uang muka
dan riwayat saldo kredit. Aksi baris "Pakai saldo", "Sesuaikan", "Balik" tampil menurut izin yang sudah dipakai layar
lama. Saringan chip: "Semua" · "Punya uang muka" · "Punya deposit" · "Punya saldo kredit". Banner PT; mode Semua PT:
aksi mati dengan petunjuk "Pilih satu PT untuk mengubah saldo." Kosong: "Tidak ada titipan maupun saldo kredit."

**Butir 5 — Kas Kecil** (`PettyCashView.jsx` ditulis ulang). Chip tahap dengan jumlah: "Semua" · "Diajukan" ·
"Dicairkan" · "Dipertanggungjawabkan" · "Selesai". Kolom: "Nomor" · "Pemohon" · "Keperluan" · "Jumlah" · "Tahap" ·
"Pertanggungjawaban" · "Sisa kembali / hutang reimburse" · "Diperbarui". Tombol "Ajukan dana" (pop-up baku). Membuka
baris menampilkan detail pengajuan dan, bila ada, detail pertanggungjawabannya dalam satu panel; aksi di dalamnya
(ajukan, setujui, cairkan, pertanggungjawabkan, bayar reimburse) memakai tombol komponen lama. Daftar berhalaman dengan
jumlah total. Kosong: "Belum ada pengajuan dana."

**Butir 6 — Tutup Buku.** Panel "Daftar Periksa Sebelum Tutup Buku" milik PK-43 tetap di tempatnya. Di bawah
pratinjau ditambah dua seksi lipat berjudul "Persediaan vs buku besar" dan "Akun sementara" yang merender
`InventoryReconTab` dan `SuspensePanel`; tombol "Buka" pada butir `stok_cocok` dan `suspense_nol` membuka seksi itu
tanpa pindah layar, dan pada butir posting gagal dan buka periode berpindah tab di hub yang sama. Layar Jurnal
kehilangan tab "Rekonsiliasi Persediaan" dan "Suspense" (tinggal Jurnal · Neraca Saldo · Buku Besar); di tempatnya satu
tautan "Rekonsiliasi persediaan dan akun sementara kini di Tutup Buku". Preset lama ke dua tab itu diarahkan ke seksi
barunya.

**Butir 7 — Beranda Keuangan › Perlu Tindakan.** Satu daftar berkelompok, tiap kelompok tampil hanya bila pengguna
memegang izin sumbernya: "Uang masuk perlu dicatat" · "Selisih bayar perlu diputus" · "Faktur pajak perlu terbit" ·
"Nota kredit perlu ditinjau" · "Hutang jatuh tempo" · "Kontrabon menunggu" · "Posting gagal". Tiap baris punya satu
tombol tindakan yang membuka layar penanganannya. Lencana posting gagal pindah ke entri Tutup Buku dan muncul juga
sebagai kelompok di sini. Beranda admin dan manajer: kartu-kartu keuangan diganti satu kartu **Keuangan** berisi tiga
angka (kas dan bank, piutang lewat jatuh tempo, hutang jatuh tempo 7 hari) dari endpoint yang sama dengan tab Posisi,
dengan tautan "Buka Beranda Keuangan". Kosong: "Tidak ada yang perlu ditindak hari ini."

**Butir 8 — Slip gaji.** Tidak ada pekerjaan layar baru. Uji U12 dan U13 memeriksa hasil PY-T1; bila salah satunya
merah, perbaikannya dikerjakan di sini: tab `hr-payslips` dicabut dari hub Penggajian, id-nya menjadi alias ke
`hr-payroll-runs`, dan pencarian slip tersedia di layar Proses Gaji.

Baseline `third_level_tabs.json` dikencangkan: dua pembungkus keluar dari daftar.

## Uji penerimaan

Persiapan bersama (fixture): pelanggan **C** dengan uang muka pesanan belum dikirim 2.000.000, deposit 500.000, saldo
kredit 300.000 di `ent_ksc`; pengajuan dana **PD-1** 1.000.000 disetujui belum cair, **PD-2** 2.000.000 sudah cair,
**PD-3** 1.500.000 sudah dipertanggungjawabkan 1.800.000 (hutang reimburse 300.000), **PD-4** selesai tanpa sisa.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | komponen | Tiruan jawaban dua endpoint untuk C | Render Titipan & Saldo Kredit | Satu baris C: 2.000.000 · 500.000 · 300.000 · jumlah 2.800.000 (2.000.000 + 500.000 + 300.000) |
| U2 | komponen | Mode Semua PT | Render | Tombol "Pakai saldo", "Sesuaikan", "Balik" mati dengan petunjuk |
| U3 | B | — | `GET /api/petty-cash/worklist` sebagai admin | `total` = 4; `stage_counts`: diajukan 1, dicairkan 1, dipertanggungjawabkan 1, selesai 1 |
| U4 | B | — | `…/worklist?stage=dipertanggungjawabkan` | Satu baris PD-3; `settlement.reimburse_due` = 300.000 (1.800.000 − 1.500.000) |
| U5 | B | Tanpa Acuan ber-`cash_advance.view` saja, pemilik PD-1 | `…/worklist` | Hanya baris yang juga dikembalikan `GET /api/cash-advances` untuk akun itu; `reimburse_due` `null` |
| U6 | B | Peran Sopir | `…/worklist` | 403 |
| U7 | B | `…/worklist?stage=aneh` | — | 400 "Tahap tidak dikenal." |
| U8 | B | — | `GET /api/finance/closing/checklist?period_type=month&period_key=2026-02` | Butir `suspense_nol` dan `stok_cocok` ber-`link.view` = `closing` dengan `preset.seksi` masing-masing; `status` dan `can_close` tidak berubah dari sebelum unit |
| U9 | komponen | Tiruan jawaban daftar periksa dengan `suspense_nol` berstatus menghalangi | Render Tutup Buku; klik "Buka" pada butir itu | Seksi "Akun sementara" terbuka di layar yang sama; tidak ada navigasi keluar hub |
| U10 | komponen | — | Buka `general-ledger` dengan preset `{tab: "suspense"}`; lalu `{tab: "recon"}` | Mendarat di Tutup Buku dengan seksi "Akun sementara"; lalu "Persediaan vs buku besar" |
| U11 | B | Manajer Kosong; lalu mode Semua PT sebagai admin | `…/worklist` | 403; lalu 200 dengan baris berlabel PT dan tombol tulis mati di layar (N3) |
| U12 | komponen | — | Jumlah tab di layar Jurnal; tab tampak hub `hr-payroll-hub` | 3; tidak memuat `hr-payslips` |
| U13 | komponen | — | `resolveDeepLinkTarget("hr-payslips", "admin")` | `view` = `hr-payroll-runs` |
| U14 | komponen | Peran finance dengan izin dari fixture (tanpa `vendor_bill.view` pada salinan fixture uji) | Render Perlu Tindakan | Kelompok "Hutang jatuh tempo" dan "Kontrabon menunggu" tidak tampil; kelompok uang masuk tampil |
| U15 | penjaga | — | `verify_page_tabs.py`, `verify_view_aliases.py`, `verify_access_catalog_nav.py`, `verify_desk_targets.py`, `roleReach.test.js` | Hijau; baseline `third_level_tabs.json` berkurang dua berkas |
| U16 | layar (uji jalan) | Data acuan; admin dan finance | Kas Kecil: ajukan → setujui → cairkan → pertanggungjawabkan tanpa keluar dari layar | Baris berpindah chip di tiap langkah; jumlah di chip berubah sesuai |
| U17 | layar (uji jalan) | manager | Tutup Buku: buka daftar periksa bulan lalu, klik "Buka" pada tiap butir yang punya tautan | Butir akun sementara dan persediaan membuka seksinya di layar yang sama; butir posting gagal dan buka periode berpindah tab; tidak ada yang keluar dari hub Tutup Buku |

## Langkah kerja

Tiap butir satu commit yang hijau sendiri; urutan bebas menurut prasyarat yang sudah `selesai`.

1. Butir 5: tes U3–U7, U11; endpoint `worklist`; layar; hapus tiga layar daftar lama setelah pencarian pemakai (`00`
   §7 butir 3) — komponen detail dan form tetap.
2. Butir 6: tes U8–U10; `link` empat butir daftar periksa; dua seksi lipat; cabut dua tab di Jurnal.
3. Butir 4: tes U1, U2; layar.
4. Butir 7: tes U14; daftar Perlu Tindakan; kartu ringkas di dua beranda; lencana.
5. Butir 8: tes U12, U13 sebagai pemeriksaan.
6. Penjaga dan baseline; uji jalan U16, U17. Gate; laporan memuat status per butir.

## Dokumen ikut berubah

`docs/KN_13_NAVIGATION_MAP.md` (isi lima layar); `CODEBASE_MAP.md` (layar yang dihapus dan satu endpoint baru); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (nama tahap kas kecil; "daftar periksa"); `memory/PRD.md`.

## Di luar lingkup

- Menyatukan `deposit_balance` ke buku saldo kredit ber-PT (duplikasi no. 3) → PK-19.
- Tautan kartu angka ke layar penjelasnya di tab Posisi dan Analisis (IA-11) → PK-44.
- Tab "Komponen & Masukan" dan "Setoran & Pajak" di Penggajian → PY-T1, PY-T4. Slip untuk karyawan sendiri → PY-T5.
- Isi dan aturan daftar periksa tutup buku → PK-43. Selisih pencocokan antar-PT → PK-31. Form pembayaran tunggal → MN-T3.

## Asumsi dan risiko

- `ASUMSI:` MN-T1 sudah `selesai` saat unit ini dikerjakan (tempat layarnya lahir di sana), walau baris indeks hanya
  menyebut PK-18, PK-24, PY-T1. Bila belum, kerjakan MN-T1 lebih dulu.
- `ASUMSI:` PK-43 sudah `selesai` saat butir 6 dikerjakan (rancangan `01` §3 menyebutnya, indeks tidak). Bila belum,
  butir 6 ditunda sebagai `MN-T2b` (`00` §8); butir lain tidak menunggu.
- `ASUMSI:` tiga angka kartu ringkas beranda (kas dan bank, piutang lewat jatuh tempo, hutang jatuh tempo 7 hari)
  dipilih dari yang sudah ditampilkan tab Posisi; tidak ada angka baru.
- `RISIKO:` menghapus layar daftar lama memutus tautan yang belum terpetakan. Rute cadangan id lama dipertahankan dan
  diarahkan ke layar baru dengan saringan yang sesuai. Membatalkan per butir: kembalikan commit butir itu.

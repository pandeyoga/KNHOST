# MN-T2 — Penyatuan layar keuangan: titipan, kas kecil, tutup buku, beranda keuangan, slip gaji

| | |
|---|---|
| Gelombang | Modul — menu dan layar |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | PK-18, PK-24, PY-T1 (dan MN-T1 untuk tempatnya; lihat "Asumsi") |
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
| 8 | Pratinjau tutup buku sudah mengembalikan boleh-tidaknya ditutup dan saldo akun sementara | `backend/routers/closing.py:48` (`preview_closing`) |
| 9 | Bahan daftar periksa lain sudah tersedia sebagai bacaan: jumlah posting gagal, jendela buka periode aktif | `backend/routers/posting_failures.py:106` (`count_posting_failures`) · `backend/routers/period_unlocks.py:50` (`active_unlocks`) |
| 10 | Meja Finance memuat dua sumber antrean: antrean meja (uang masuk, faktur pajak) dan papan hutang | `frontend/src/features/finance/FinanceDesk.jsx:25` (`FinanceDesk`) · `frontend/src/features/finance/FinanceDesk.jsx:90` (`WaitingBoardsStrip`) · `backend/routers/work_desks.py:232` (`finance_desk`) · `backend/routers/home.py:100` (`home_finance`) |
| 11 | Dua dasbor keuangan lain dan dua beranda memuat angka keuangan sendiri-sendiri | `frontend/src/features/finance/FinanceTowerView.jsx:17` (`FinanceTowerView`) · `frontend/src/features/finance/BiFinanceView.jsx:49` (`BiFinanceView`) · `frontend/src/features/home/AdminHome.jsx:46` (`AdminHome`) · `frontend/src/features/home/ManagerHome.jsx:31` (`ManagerHome`) |
| 12 | Lencana posting gagal menempel pada grup Akuntansi & Pajak | `frontend/src/components/CoreWidgets.jsx:243` (`CountBadge`) |
| 13 | Detail proses gaji sudah memuat tabel slip; tab Slip Gaji menampilkan slip yang sama lewat endpoint lain | `frontend/src/features/hr/PayrollRunsView.jsx:202` (`payroll-payslips-table`) · `frontend/src/features/hr/PayslipsView.jsx:21` (`PayslipsView`) · `backend/routers/hr_payroll.py:212` (`list_payslips`) |

## Perubahan

### Data

Tidak ada koleksi atau field baru. Unit ini tidak menyatukan `deposit_balance` dengan buku saldo kredit; layar
menampilkan keduanya berdampingan dengan label sumbernya (D1).

### Server

Dua endpoint baca baru; keduanya memanggil fungsi daftar layanan yang ada sehingga aturan PT dan kepemilikan tidak
disalin.

| Metode + path | Izin | Isi → jawaban | Galat |
|---|---|---|---|
| `GET /api/petty-cash/worklist?stage&q&page&page_size` | `cash_advance.view` atau `cash_settlement.view` (`require_any_permission`) | → `{items, total, page, page_size, stage_counts}`; satu baris per pengajuan dana: `{id, number, requester, purpose, amount, stage, status, settlement: {id, number, status, spent, refund_due, reimburse_due} \| null, updated_at}` | 400 "Tahap tidak dikenal." |
| `GET /api/finance/closing/checklist?period_key&period_type` | `accounting.view` | → `{period_label, entity_id, items: [{key, label, state, value, note, link}], can_close}` | 409 "Pilih satu PT. Tutup buku dikerjakan per PT." (mode Semua PT) |

`stage` kas kecil dan cara menurunkannya dari status yang ada:

| `stage` | Label layar | Diturunkan dari |
|---|---|---|
| `diajukan` | Diajukan | Pengajuan belum dicairkan (draf, menunggu tiap tahap persetujuan, disetujui, ditolak) |
| `dicairkan` | Dicairkan | Pengajuan sudah dicairkan dan belum punya pertanggungjawaban yang diajukan |
| `dipertanggungjawabkan` | Dipertanggungjawabkan | Pertanggungjawaban diajukan atau disetujui, masih ada sisa kembali atau hutang reimburse |
| `selesai` | Selesai | Pertanggungjawaban selesai dan tidak ada sisa di kedua arah |

Kolom `reimburse_due` hanya diisi bagi pemanggil ber-`accounting.view`; bagi yang lain `null`.

Butir daftar periksa (`items`), semuanya dari bacaan yang ada; `state` = `beres` · `perlu_dilihat` · `menghalangi`:

| `key` | Label | Sumber | `menghalangi` bila |
|---|---|---|---|
| `posting_failures` | "Posting gagal" | jumlah posting gagal | tidak pernah; `perlu_dilihat` bila > 0 |
| `suspense` | "Akun sementara" | `suspense_balance` pratinjau | pratinjau menyatakan `suspense_blocks_close` |
| `inventory_recon` | "Persediaan vs buku besar" | rekonsiliasi persediaan | tidak pernah; `perlu_dilihat` bila selisih ≠ 0 |
| `interco` | "Saldo antar-PT dua sisi" | saldo pasangan PT | tidak pernah; `perlu_dilihat` bila selisih ≠ 0; `note` "Anda belum punya akses" bila tanpa `interco_finance.view` |
| `period_unlock` | "Jendela buka periode aktif" | jendela aktif | tidak pernah; `perlu_dilihat` bila ada |
| `preview` | "Pratinjau jurnal penutup" | pratinjau | pratinjau menyatakan tidak bisa ditutup (`blocking_closing`) |

`can_close` = nilai `can_close` pratinjau. Daftar periksa tidak menambah aturan penghalang baru.

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
| 6 | Tiga tab berisi tiga layar yang tidak saling tahu; dua tab di Buku Besar | **Tutup Buku › Daftar Periksa & Tutup** dengan daftar periksa di atas dan dua seksi lipat | `ClosingView` (bagian pratinjau dan tutup), `InventoryReconTab`, `SuspensePanel`; tab Buka Periode dan Posting Gagal tetap | PK-18, MN-T1 |
| 7 | Tab "Perlu Tindakan" = Meja Finance apa adanya; kartu keuangan di dua beranda | **Beranda Keuangan › Perlu Tindakan**: satu antrean; beranda admin dan manajer memuat satu kartu ringkas | Baris antrean dan `ARReceiptModal` dari `FinanceDesk`; `WaitingBoardsStrip`; `CountBadge` | PK-16, PK-17, MN-T1 |
| 8 | Tab "Slip Gaji" | Slip di dalam detail **Penggajian › Proses Gaji** | Tabel slip di `PayrollRunsView`; unduh PDF dari `PayslipsView` | PY-T1 |

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

**Butir 6 — Tutup Buku.** Di atas tab pertama: **Daftar periksa {periode}** — enam baris berlabel seperti tabel,
masing-masing dengan tanda "Beres", "Perlu dilihat", atau "Menghalangi", nilainya, dan tautan "Lihat" (ke tab Posting
Gagal, tab Buka Periode, Antar-PT, atau seksi di bawah). Dua seksi lipat berjudul "Persediaan vs buku besar" dan "Akun
sementara" merender `InventoryReconTab` dan `SuspensePanel`. Tombol "Tutup periode" tetap milik `ClosingView` dan mati
bila `can_close` salah, dengan petunjuk "Selesaikan butir bertanda Menghalangi." Layar Jurnal kehilangan tab
"Rekonsiliasi Persediaan" dan "Suspense" (tinggal Jurnal · Neraca Saldo · Buku Besar); di tempatnya satu tautan
"Rekonsiliasi persediaan dan akun sementara kini di Tutup Buku".

**Butir 7 — Beranda Keuangan › Perlu Tindakan.** Satu daftar berkelompok, tiap kelompok tampil hanya bila pengguna
memegang izin sumbernya: "Uang masuk perlu dicatat" · "Selisih bayar perlu diputus" · "Faktur pajak perlu terbit" ·
"Nota kredit perlu ditinjau" · "Hutang jatuh tempo" · "Kontrabon menunggu" · "Posting gagal". Tiap baris punya satu
tombol tindakan yang membuka layar penanganannya. Lencana posting gagal pindah ke entri Tutup Buku dan muncul juga
sebagai kelompok di sini. Beranda admin dan manajer: kartu-kartu keuangan diganti satu kartu **Keuangan** berisi tiga
angka (kas dan bank, piutang lewat jatuh tempo, hutang jatuh tempo 7 hari) dari endpoint yang sama dengan tab Posisi,
dengan tautan "Buka Beranda Keuangan". Kosong: "Tidak ada yang perlu ditindak hari ini."

**Butir 8 — Slip gaji.** Tab `hr-payslips` dicabut dari hub Penggajian; id-nya menjadi alias ke `hr-payroll-runs`
dengan preset `{bagian: "slip"}` dan label palet "Slip Gaji". Detail proses mendapat kotak "Cari karyawan" dan tombol
"Unduh PDF" per baris slip. Di kepala daftar proses: tombol "Cari slip semua periode" membuka pop-up berisi daftar
slip lintas periode (komponen `PayslipsView` dirender di dalam pop-up, bukan sebagai tab).

Alias baru (`since: "MN-T2"`): `hr-payslips` seperti di atas. Baseline `third_level_tabs.json` dikencangkan: dua
pembungkus keluar dari daftar.

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
| U6 | B | Manajer Kosong | `…/worklist`; `…/closing/checklist` | 403 dan 403 |
| U7 | B | `…/worklist?stage=aneh` | — | 400 "Tahap tidak dikenal." |
| U8 | B | Satu kwitansi ber-`gl_status: failed`; saldo akun sementara 0 | `GET /api/finance/closing/checklist?period_type=month&period_key=2026-02` | `posting_failures`: `perlu_dilihat`, nilai 1; `suspense`: `beres`; `can_close` sama dengan `can_close` dari `/api/finance/closing/preview` |
| U9 | B | Saldo akun sementara 50.000 | Daftar periksa | `suspense`: `menghalangi`; `can_close` salah — sama dengan pratinjau |
| U10 | B | Mode Semua PT | Daftar periksa | 409 "Pilih satu PT…" |
| U11 | B | Akun ber-`accounting.view` tanpa `interco_finance.view` | Daftar periksa | 200; butir `interco` ber-`note` "Anda belum punya akses"; butir lain terisi |
| U12 | komponen | — | Jumlah tab di layar Jurnal; jumlah tab tampak hub `hr-payroll-hub` | 3; berkurang satu dari keadaan sebelum unit (Slip Gaji tidak ada) |
| U13 | komponen | — | `resolveDeepLinkTarget("hr-payslips", "admin")` | `view` = `hr-payroll-runs`, `preset.bagian` = `slip` |
| U14 | komponen | Peran finance dengan izin dari fixture (tanpa `vendor_bill.view` pada salinan fixture uji) | Render Perlu Tindakan | Kelompok "Hutang jatuh tempo" dan "Kontrabon menunggu" tidak tampil; kelompok uang masuk tampil |
| U15 | penjaga | — | `verify_page_tabs.py`, `verify_view_aliases.py`, `verify_access_catalog_nav.py`, `verify_desk_targets.py`, `roleReach.test.js` | Hijau; baseline `third_level_tabs.json` berkurang dua berkas |
| U16 | layar (uji jalan) | Data acuan; admin dan finance | Kas Kecil: ajukan → setujui → cairkan → pertanggungjawabkan tanpa keluar dari layar | Baris berpindah chip di tiap langkah; jumlah di chip berubah sesuai |
| U17 | layar (uji jalan) | manager | Tutup Buku: buka daftar periksa bulan lalu, klik "Lihat" pada tiap butir | Tiap tautan mendarat di tempat yang disebut; tombol tutup mengikuti `can_close` |

## Langkah kerja

Tiap butir satu commit yang hijau sendiri; urutan bebas menurut prasyarat yang sudah `selesai`.

1. Butir 5: tes U3–U7; endpoint `worklist`; layar; hapus tiga layar daftar lama setelah pencarian pemakai (`00` §7
   butir 3) — komponen detail dan form tetap.
2. Butir 6: tes U8–U11; endpoint `checklist`; layar; cabut dua tab di Jurnal.
3. Butir 4: tes U1, U2; layar.
4. Butir 7: tes U14; daftar Perlu Tindakan; kartu ringkas di dua beranda; lencana.
5. Butir 8: tes U12, U13; alias; pop-up slip.
6. Penjaga dan baseline; uji jalan U16, U17. Gate; laporan memuat status per butir.

## Dokumen ikut berubah

`docs/KN_13_NAVIGATION_MAP.md` (tab Slip Gaji hilang; isi lima layar); `CODEBASE_MAP.md` (layar yang dihapus dan dua
endpoint baru); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (nama tahap kas kecil; "daftar periksa"); `memory/PRD.md`.

## Di luar lingkup

- Menyatukan `deposit_balance` ke buku saldo kredit ber-PT (duplikasi no. 3) → PK-19.
- Tautan kartu angka ke layar penjelasnya di tab Posisi dan Analisis (IA-11) → PK-44.
- Tab "Komponen & Masukan" dan "Setoran & Pajak" di Penggajian → PY-T1, PY-T4. Slip untuk karyawan sendiri → PY-T5.
- Toleransi dan alasan selisih pencocokan antar-PT → PK-31. Form pembayaran tunggal dari antrean → MN-T3.

## Asumsi dan risiko

- `ASUMSI:` MN-T1 sudah `selesai` saat unit ini dikerjakan (tempat layarnya lahir di sana), walau baris indeks hanya
  menyebut PK-18, PK-24, PY-T1. Bila belum, kerjakan MN-T1 lebih dulu.
- `ASUMSI:` daftar periksa bersifat penunjuk; yang menghalangi tutup buku tetap hanya yang hari ini sudah menghalangi
  di pratinjau. Tidak ada aturan penghalang baru.
- `ASUMSI:` bila PK-43 sudah membangun daftar periksa tutup buku (UX-16), butir 6 memakai miliknya dan hanya
  memindahkan dua seksi dari Buku Besar; endpoint `checklist` di sini tidak dibuat dua kali.
- `ASUMSI:` tiga angka kartu ringkas beranda (kas dan bank, piutang lewat jatuh tempo, hutang jatuh tempo 7 hari)
  dipilih dari yang sudah ditampilkan tab Posisi; tidak ada angka baru.
- `RISIKO:` menghapus layar daftar lama memutus tautan yang belum terpetakan. Rute cadangan id lama dipertahankan dan
  diarahkan ke layar baru dengan saringan yang sesuai. Membatalkan per butir: kembalikan commit butir itu.

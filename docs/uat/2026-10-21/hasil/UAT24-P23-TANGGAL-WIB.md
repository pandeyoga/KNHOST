# P23 — Tanggal bawaan form & laporan mengikuti WIB, apa pun zona perangkat

- Commit awal: `cd6963a`        - Commit akhir: `2a77288` (kode + uji)        - Branch: `claude/determined-dijkstra-ohdenb`
- ID ditangani: P23 (permintaan pemilik 15 Nov — uji jalan di peramban berzona UTC pukul 02.20 WIB 15 Nov)

## P23 — Tanggal bawaan dihitung dari jam lokal peramban, bukan WIB

- **Berlaku di HEAD:** ya — direproduksi lewat uji di `cd6963a` (kode lama, uji baru): **6 dari 7 uji merah**.
  Laba-Rugi bawaan meminta `end=2026-11-14`, Neraca `as_of=2026-11-14`, tombol tanggal kwitansi bertuliskan
  "Sab, 14 Nov 2026" (dikirim `2026-11-14`), terima sampel fisik `date: "2026-11-14"` — padahal pukul 02.30 WIB
  15 Nov. Uji prasyarat (perangkat UTC melihat 14 Nov, WIB 15 Nov) hijau di kedua versi.
- **Akar masalah** — tiga pola yang sama-sama mengabaikan standar tanggal aplikasi (WIB, `utils/formatters.js`):
  1. `const NOW = new Date()` di **tingkat modul** (5 berkas keuangan): dievaluasi sekali saat modul dimuat, jadi basi
     bila aplikasi terbuka melewati tengah malam; lalu `getFullYear/getMonth/getDate` = zona **perangkat**.
  2. "Tanggal lokal" lewat `getTimezoneOffset()` / `getFullYear()…getDate()` — benar hanya bila perangkat berzona WIB.
     Perbaikan UAT lama (S2, S13, S15, E1) memakai pola ini dengan asumsi perangkat = WIB.
  3. Potongan ISO `new Date().toISOString().slice(0, 7|10)` = tanggal/bulan **UTC** (00.00–07.00 WIB = kemarin;
     tanggal 1 pukul 00.00–07.00 WIB = bulan lalu).
- **Perubahan perilaku (sebelum → sesudah)** — semua bawaan kini `todayWib()` (atau turunannya) dan dihitung di
  penginisialisasi `useState(() => …)` / saat fungsi dipanggil, bukan saat modul dimuat:

  | Layar / helper | Sebelum | Sesudah |
  |---|---|---|
  | Laporan Keuangan · Laba-Rugi (`FinancialStatementsView`) | rentang `NOW.getFullYear()-01-01` s.d. tanggal perangkat; bulan/tahun periode & pilihan tahun dari `NOW` | `ytdRangeWib()`; bulan/tahun dari `todayWib()`; `yearOptions()` saat tab dipasang |
  | Laporan Keuangan · Neraca | per tanggal perangkat; pembanding = akhir bulan lalu versi perangkat; judul kolom tanggal zona perangkat | `todayWib()`; `endOfPrevMonthWib()` (aritmetika kalender UTC); judul kolom `formatDate` (WIB) |
  | Arus Kas, Perubahan Ekuitas, Profitabilitas | `{ start: NOW…-01-01, end: ymd(NOW) }` (financeShared) | `ytdRangeWib()` |
  | Anggaran, BI Keuangan, Tutup Buku, Konsolidasi Grup | tahun/bulan/per tanggal dari `NOW` modul; `YEARS` modul | `todayWib()`; `yearOptions()` per layar |
  | Eliminasi konsolidasi (tanggal efektif) | `ymd(new Date())` perangkat | `todayWib()` |
  | Aset Tetap (periode penyusutan) | `toISOString().slice(0, 7)` (UTC) | `todayWib().slice(0, 7)` |
  | Impor mutasi bank (`year_hint`) | `new Date().getFullYear()` perangkat | tahun WIB |
  | **Catat Pembayaran / kwitansi** (`ARReceiptModal`, desktop & HP) | tanggal perangkat | `todayWib()` |
  | Checkout POS (batas bawah tanggal ambil/kirim + validasi "tanggal kirim lampau") | tanggal perangkat | `todayWib()` |
  | Keputusan pelanggan OD (HP), Terima sampel fisik (R&D) | tanggal perangkat | `todayWib()` |
  | Kontrabon: tanggal bayar & jadwal bayar (`todayISO`) | tanggal perangkat | `todayWib()` |
  | Faktur Masukan (masa pajak), CRM Target/Insentif (`currentPeriod`), KPI HR (`curMonth`, `lastMonths`) | bulan perangkat | bulan WIB; `lastMonths` mundur dengan aritmetika (y, m) — dulu `setMonth(-1)` di tanggal 31 menggandakan/melompati bulan |
  | Target penagihan HP | `toISOString().slice(0, 7)` (UTC) | bulan WIB |
  | Kalender konten (bulan/minggu ini, sorotan "hari ini") | zona perangkat | WIB (dengan argumen tetap aritmetika kalender lokal) |
  | Preset tanggal daftar desain ("Hari ini", "7/30 hari", "Bulan ini/lalu", geser bulan) | tanggal **UTC** jam sekarang | tanggal WIB; label bulan dibaca di UTC (tanggal murni) |
  | `KNDateTimePicker` (jam dipilih sebelum tanggal) | `format(new Date(), …)` perangkat | `todayWib()` (nilai picker = jam dinding WIB, label "WIB") |
  | `KNMonthPicker` (tahun awal tanpa nilai) | tahun perangkat | tahun WIB |
  | Interaksi CRM: Waktu Interaksi bawaan + kiriman Waktu Interaksi & Tindak Lanjut | jam dinding **perangkat**, dikirim sebagai waktu perangkat; daftar tampil zona perangkat | jam dinding WIB, dikirim `…:00+07:00`; daftar tampil WIB |
  | Pratinjau pesanan (tanggal "Data Pesanan") | tanggal perangkat dari `created_at` | `wibDate(created_at)` |
  | Cetak tanda terima (tanggal di baris tanda tangan) & label roll | zona perangkat | WIB |

  Di perangkat berzona WIB tidak ada perubahan yang terlihat (termasuk kiriman interaksi CRM: jam dinding WIB +07:00 =
  instan yang sama).
- **Berkas berubah** (`2a77288`, 34 berkas):
  * Keuangan: `features/finance/financeShared.jsx` (helper `yearOptions`, `ytdRangeWib`, `endOfPrevMonthWib`;
    `NOW`/`YEARS`/`ymd` dihapus — semua pemakai sudah diganti, `grep` bersih), `FinancialStatementsView.jsx`,
    `CashFlowTab.jsx`, `EquityChangesTab.jsx`, `ProfitabilityView.jsx`, `BudgetView.jsx`, `BiFinanceView.jsx`,
    `ClosingView.jsx`, `GroupConsolidationView.jsx`, `GroupConsolidationParts.jsx`, `FixedAssetsView.jsx`,
    `bank/ReconImportPanel.jsx`.
  * Form & helper lain: `crm/ARReceiptModal.jsx`, `crm/crmUtils.jsx`, `crm/OmnichannelInteractions.jsx`,
    `pos/CheckoutDrawer.jsx`, `pos/CheckoutStep3.jsx`, `sales/mobile/MobileSalesFlows.jsx`,
    `sales/mobile/MobileCollectionTargets.jsx`, `sales_admin/OrderPreviewCard.jsx`, `rnd/SampleFinishModal.jsx`,
    `rnd/design/DateQuickNav.jsx`, `purchasing/contrabon/contraBonApi.js`, `purchasing/InputTaxView.jsx`,
    `hr/kpiUtils.js`, `marketing/marketingShared.jsx`, `marketing/WeekGrid.jsx`, `components/KNDateTimePicker.jsx`,
    `components/KNMonthPicker.jsx`, `utils/docPrint.js`, `utils/rollLabels.js`.
  * Uji: `features/__tests__/tanggalBawaanWib.test.js` (baru), `features/__tests__/uatV3SpecialOrder.test.js`
    (harapan diganti, lihat di bawah), `frontend/jest/utcDeviceEnvironment.js` (baru).
  * `utils/formatters.js` (helper bersama) **tidak diubah** — hanya `todayWib`/`wibDate`/`formatDate` yang sudah ada
    dipakai.
- **Commit:** `2a77288`.
- **Pengujian:**
  * Uji baru `tanggalBawaanWib.test.js` (7 uji): jam dibekukan pada `2026-11-14T19:30:00Z` (hanya `new Date()` tanpa
    argumen & `Date.now()`; timer tetap asli) di lingkungan jest **"perangkat berzona UTC"**
    (`@jest-environment <rootDir>/jest/utcDeviceEnvironment.js` — `process.env.TZ = "UTC"` selama berkas itu, dipulihkan
    saat teardown). Dengan begitu uji tetap bermakna di mesin berzona WIB (di sana kode lama kebetulan benar). Isi:
    prasyarat (perangkat 14 Nov, WIB 15 Nov); helper keuangan (`ytdRangeWib` → 2026-01-01…2026-11-15,
    `endOfPrevMonthWib` → 2026-10-31, juga Jan → 2025-12-31 & 31 Mar → 2026-02-28, `yearOptions`); helper modul lain
    (`currentPeriod`, `curMonth`, `lastMonths` termasuk 31 Mar & Januari, `todayISO`, `monthKey`, `weekStart`,
    `presetRange`); layar: Laba-Rugi meminta `start=2026-01-01, end=2026-11-15`, Neraca `as_of=2026-11-15,
    compare_as_of=2026-10-31`, kwitansi menampilkan "15 Nov 2026" dan mengirim `receipt_date` 2026-11-15, terima sampel
    fisik `date: "2026-11-15"`.
  * Sebelum/sesudah (berkas uji yang sama, `CI=true TZ=Asia/Jakarta yarn test --watchAll=false
    src/features/__tests__/tanggalBawaanWib.test.js`): kode `cd6963a` **6 gagal / 1 lulus** → `2a77288` **7/7 lulus**.
  * **Jest penuh** (`CI=true yarn test --watchAll=false`): sebelum mengganti harapan lama 85/86 suite (1 gagal:
    `uatV3SpecialOrder`, lihat di bawah); sesudah **86/86 suite, 611/611 uji lulus** — dijalankan dua kali, proses
    `TZ=UTC` dan `TZ=Asia/Jakarta`, hasil sama.
  * **`uatV3SpecialOrder.test.js` — harapan diganti (bukan dilonggarkan):** uji "Sample jadi: tanggal bawaan = tanggal
    lokal hari ini" membandingkan dengan tanggal **zona perangkat** (`localToday()`), yaitu perilaku lama yang diminta
    diganti. Uji itu baru merah karena suite penuh kebetulan berjalan pukul 19.5x UTC (= 02.5x WIB): di luar jendela
    00.00–07.00 WIB ia lulus di versi mana pun, sehingga selama ini menyembunyikan bug di perangkat non-WIB. Maksud
    aslinya ("bukan kosong → tanggal UTC server") dipertahankan; harapan kini `todayWib()`.
  * **ESLint** (`npx eslint` 34 berkas berubah/baru): **0 error**, 12 peringatan "Unused eslint-disable directive" —
    semuanya sudah ada di `HEAD` (dicek per berkas dari `git show HEAD:`; nomor baris hanya bergeser). Karena konfigurasi
    repo mematikan `no-undef`, saya jalankan tambahan `--rule '{"no-undef": "error"}'`: **0** di berkas sumber (impor
    `todayWib` lengkap; sisanya hanya global jest di berkas uji).
  * **Gate statik** `bash scripts/gate.sh --quick`: 33 PASS · 19 FAIL · 4 SKIP — **identik per gate** dengan `HEAD`
    murni (perubahan di-stash, gate yang sama dijalankan ulang, receipt dibandingkan baris per baris). Merah yang ada
    adalah bawaan/lingkungan (mis. `ModuleNotFoundError: motor/bcrypt/services` di container ini) — tidak ada yang baru.
    `memory/GATE_RECEIPT.md` dikembalikan ke versi `HEAD` (receipt mode `--quick` dari lingkungan tanpa DB tidak di-commit).
  * Guardrail UI: `verify_ui_standard.py` (G-UI) **PASS 4.316 cek, 0 pelanggaran** (semua hitungan = baseline);
    `verify_ui_contrast.py` **PASS 58/58**.
  * `git diff --check` bersih; semua berkas LF.
- **Bukti UI (screenshot/rekaman):** tidak ada — sesi ini tanpa Docker (tidak ada Mongo/backend), jadi layar tidak dibuka
  di peramban. Bukti perilaku = uji komponen jsdom di atas (render layar sungguhan dengan API tiruan).
- **Fixture disiapkan langsung vs proses bisnis dijalankan:** fixture (API tiruan jest: daftar SO terbuka, deposit);
  tidak ada proses bisnis yang dijalankan terhadap backend.
- **Dampak pada modul terkait:**
  * `financeShared` tidak lagi mengekspor `NOW`, `YEARS`, `ymd` (semua pemakai di repo sudah diganti; impor lain dari
    berkas itu tidak berubah).
  * Interaksi CRM: kiriman `occurred_at`/`follow_up_date` kini ditafsirkan sebagai WIB (+07:00). Di perangkat berzona WIB
    instannya sama persis dengan sebelumnya; di perangkat zona lain instannya berubah menjadi yang benar (sesuai label
    "WIB" di pemilih). Nilai yang bukan `YYYY-MM-DDTHH:MM` diteruskan apa adanya.
  * Backend tidak diubah. Kwitansi tetap mengirim `receipt_date` = `new Date("YYYY-MM-DD").toISOString()` (tengah malam
    UTC); layanan memakai 10 karakter pertamanya → tanggal yang dipilih.
- **Keterbatasan / yang belum diuji:**
  * Tidak diuji di peramban sungguhan (lihat Bukti UI). Layar yang hanya dicek lewat ESLint/`no-undef` + uji helper (tanpa
    render): Aset Tetap, Anggaran, Konsolidasi, Interaksi CRM, kalender konten, checkout POS, KPI HR, impor mutasi bank.
  * **Sengaja tidak diubah (di luar "tanggal bawaan"):**
    - Helper HR `trackingUtils`, `leaveUtils`, `payrollUtils`, `AttendanceView` sudah WIB (`Date.now() + 7 jam` →
      potongan ISO) — benar. Catatan: `lastMonths` di `leaveUtils`/`payrollUtils` masih `setMonth(-1)` (kelas yang sama
      dengan perbaikan `kpiUtils`: tanggal 31 bisa menggandakan bulan) — kandidat lanjutan.
    - `logistics/logisticsApi.js` punya salinan `todayWib` sendiri (benar, duplikat).
    - Tampilan stempel waktu server di zona perangkat: `formatStamp` (`utils/formatters.js`), `InspectionDetailParts`,
      `fmtDateTime` lokal di `ClosingView` dll., `formatCsvDate/DateTime` & nama berkas `csvFilename` (`utils/csvExport.js`)
      — kelas "tampilan/ekspor stempel waktu", bukan tanggal bawaan; mengubahnya juga mengubah isi ekspor. Kandidat lanjutan.
    - Perbandingan jatuh tempo di zona perangkat (`RndReportsView` "terlambat", `MobileCustomers` "lewat jatuh tempo").
- **Status:** implemented_pending_review

## Hambatan lingkungan

- Tidak ada Docker di container sesi ini → gate default `seed_reset.sh`, `health_check.py`, `audit_endpoint_sweep.py`,
  `ux_audit.py` runtime dan `verify_contract.py --all` (butuh Mongo/backend) **tidak dijalankan**. Perubahan hanya di
  frontend (tidak ada endpoint/koleksi yang berubah).
- `yarn install --frozen-lockfile` gagal karena host `assets.emergent.sh` ditolak kebijakan jaringan (403) untuk paket
  opsional `@emergentbase/visual-edits`. Dependensi dipasang tanpa paket itu (`craco.config.js` sudah menanganinya:
  "visual editing disabled"); `package.json` dikembalikan persis, `yarn.lock` hasil instal tidak di-commit.

## Yang perlu direview

1. Daftar layar di tabel atas sudah mencakup semua tanggal bawaan form/laporan? (Penyisiran: `getTimezoneOffset`,
   `toISOString().slice(0, n)`, `getFullYear()/getMonth()/getDate()` pada `new Date()`, `ymd`/`dayKey` lokal,
   `NOW` tingkat modul, `format(new Date(), …)`.)
2. Pergeseran semantik kiriman Interaksi CRM ke +07:00 (hanya berdampak di perangkat non-WIB).
3. Pendekatan uji: lingkungan jest per berkas yang mengganti zona proses ke UTC lalu memulihkannya.
4. Penggantian harapan `uatV3SpecialOrder` (alasan di atas).
5. Butir "sengaja tidak diubah" — perlu dijadwalkan sebagai lanjutan?

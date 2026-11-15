# PY-T4 — Bayar gaji dari rekening berperuntukan Gaji dengan daftar transfer per karyawan; Finance bisa membayar dan menyetor

- Commit awal: `6e79137` (worktree kerja)        - Commit akhir: `61cf7a1`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PY-11 (spesifikasi `docs/blueprint/unit/PY-T4.md`); keputusan K-41 (izin bayar terpisah, pemegang
  bawaan), K-34 (rekening = data master)
- Standar: `02` §1 (P1, P2, P3, P5), §3.1 (Z1, Z2, Z6), §3.2, §3.4 (N1, N2, N4, N5), §4 (L1–L4, L7, L8), §5 (D4, D5), §6
- Risiko **sedang** → satu serah-terima (`00` §8 tidak berlaku). Prasyarat PY-T1, PM-T1 ada di basis.

## Cek ulang "Keadaan sekarang" (spesifikasi dibaca di `3132cc4`; dicek di `6e79137`)

| Butir spesifikasi | Hasil di basis |
|---|---|
| Layar mengirim bayar tanpa isi — `PayrollRunsView.jsx:88` (`pay`) | Berlaku, bergeser — `:203` (`moneyPost(…/pay, {}, k)`) |
| Bawaan akun `ACC_KAS_BESAR` — `gl_service.py:3118` | Berlaku, bergeser — PK-22 `assert_payroll_cash_account` `:3779` (`cash_account or allowed[0]`), dipanggil `pay_payroll_run` `:3791` |
| Isi permintaan hanya kode akun — `schemas_hr_payroll.py:11` (`PayRunInput`) | **Sebagian** — `:12`; PK-20 sudah menambah `account_id` (rekening), tanpa tanggal bayar |
| Akun bayar = anak akun kas/bank tanpa rekening — `gl_service.py:3123` (`parent_code`) | **Sudah berubah** (PK-22/PK-20): akun dibatasi pemetaan `kas_bank.kas_besar/kas_kecil` (`:3779`) dan rekening wajib lewat `cash_ledger.periksa_rekening` (`hr_payroll_service.py:1138`) — tetapi peruntukan rekening tidak diperiksa (bukti merah U3 varian admin: R-OPS dibayar) |
| Satu jurnal + satu mutasi kas, `record_return_cash` — `hr_payroll_service.py:562` | Berlaku, bergeser — `:1164` (jurnal `payroll_pay` + kas menumpang jurnal induk) |
| Bertanggal saat tombol ditekan — `gl_service.py:3128` (`now_iso`) | Berlaku, bergeser — `pay_payroll_run` `date=date or now_iso()` `:3812`, `preflight_posting(…, now_iso())` `hr_payroll_service.py:1140` (bukti merah U6/U7 varian admin) |
| Tidak ada daftar transfer; rekening karyawan dipotret di slip — `hr_payroll_service.py:310` (`bank`) | Berlaku, bergeser — potret `bank` `:565` (`bank_name`, `acc_no`, `acc_name`); tidak ada endpoint (U1 404) |
| Satu izin `manage_payroll` — `routers/hr_payroll.py:199` | **Sudah berubah** (PK-22): lima izin `payroll.*`; bayar = `payroll.pay` `:273`, setor `:317` |
| Finance tanpa izin SDM — `permissions_config.py:346` (`finance`) | Berlaku — `:349`; Finance tidak memegang `payroll.pay` (U2 403) |
| Hub Penggajian hanya Admin & Manajer — `hubTabs.js:195` | Berlaku, bergeser — `hubTabs.js:200`, `navStructure.js:336` |
| Rekening tunggal disaring `status` — `bank_service.py:55` | **Sudah berubah** (PM-T1): `sole_account_id` menyaring `is_active` + `status`; peruntukan tetap tidak diperiksa (bayar gaji kini memakai `hr_payroll_pay.pay_accounts`, bukan rekening tunggal) |
| Izin `payroll.pay`, label "Bayar gaji dan setor BPJS/PPh 21" (PK-22) | **Sudah ada** — `access_modules.py:659`; tidak diubah |
| `purposes` rekening (PM-T1), `create_cash` (PK-20), `hr_statutory_remittances` (PK-22) | Ada — dipakai apa adanya (`bank_service.rekening_pt`/`bidang_efektif`, `cash_ledger.create_cash`, `hr_remittance_service`) |

## PY-11 — bayar gaji tanpa rekening berperuntukan, tanpa daftar transfer, satu izin

- Berlaku di HEAD: ya. Bukti merah `bukti/PY-T4/merah_kode_lama.txt` (17/17 merah: endpoint baru 404, Finance 403) dan
  `bukti/PY-T4/merah_kode_lama_varian_admin.txt` (U3–U8 dengan sesi Admin pada kode lama: R-OPS **dibayar**, tanggal
  bayar diabaikan sehingga U6 dan U7 **dibayar**, gaji bersih negatif **dibayar**, U4 400 karena kode akun 1-1200 dibaca,
  U5 pesan lain).
- Akar masalah: bayar gaji memilih **akun** dari isi permintaan dan rekening "satu-satunya" tanpa melihat peruntukan; tidak
  ada tanggal bayar; tidak ada daftar penerima; semua langkah bayar/setor hanya untuk pemegang izin penggajian Admin &
  Manajer; setoran yang salah catat tidak bisa dibatalkan.
- Perubahan perilaku (sebelum → sesudah):
  - **Rekening pembayaran gaji** `GET /api/hr/payroll/pay-accounts` (`payroll.pay`; PT aktif atau `entity_id` yang
    ditugaskan, `resolve_requested_entity`): rekening aktif PT yang `purposes`-nya memuat `gaji`
    (`[{id, name, bank_name, account_number, holder_name, cash_type}]`, tanpa saldo). Rekening lama tanpa field = empat
    peruntukan (PM-T1).
  - **Antrean bayar** `GET /api/hr/payroll/pay-queue` (`payroll.pay`, berhalaman `{items, total}`): proses `posted` —
    `id, number, period, run_type, employees, net_total, posted_at` + `entity_id`, `journal_date` (pop-up Bayar).
  - **Daftar transfer** `GET …/runs/{id}/transfer-list` (`payroll.pay`; `posted`/`paid`, selain itu 409 "Daftar transfer
    tersedia setelah penggajian diposting."): diturunkan dari slip (tidak disimpan), urut nama, `cash` bila slip tanpa
    nomor rekening; Σ ≠ `totals.net` → 409 (penjaga, satuan sen). `…/export` → `transfer-gaji-<nomor>.xlsx` (kepala PT,
    nomor, periode, rekening sumber, tanggal bayar; kolom No. · Nama penerima · Bank · Nomor rekening · Nominal · Berita
    "Gaji {bulan tahun} {PT}"; baris Total); jejak audit `hr.payroll.transfer_export` berisi nomor, periode, jumlah
    penerima — tanpa nominal.
  - **Bayar** `POST …/runs/{id}/pay` `{account_id?, paid_date?}` (`services/hr_payroll_pay.py:pay_run`): PERIKSA status
    `posted` (sedang/sudah dibayar → 409 "Penggajian {nomor} sedang atau sudah dibayar. Muat ulang."; status lain → 409
    "…berstatus {label}, jadi tidak bisa dibayar.") · gaji bersih negatif 409 · Σ daftar = bersih · rekening (empat pesan
    spesifikasi) · tanggal (bawaan hari ini WIB; < tanggal jurnal gaji 400; bentuk salah 400) · `preflight_posting(PT,
    tanggal bayar)` 409 · kontrol dua orang K-41 → NIAT `posted → paying` bersyarat (+ `pay_account_id`,
    `pay_account_name`, `paid_date`, `paid_by_id`) → EFEK+JURNAL satu kas keluar `create_cash(ref_type="payroll_run",
    ref_id=id proses, account_id, txn_date=paid_date, contra_account_code=<pemetaan sdm.hutang_gaji>)` → jurnal kas
    Dr 2-1600 / Cr kas rekening, bertanggal bayar → SELESAI `paid` + `transfer_total`, `transfer_count`, `cash_txn_id`,
    `paid_journal_id`. `cash_account` diabaikan. Jurnal kas gagal → kembali `posted`, `pay_gl_status=failed`, kas
    tersimpan (Posting Gagal › Transaksi Kas); Bayar lagi atau ulang dari panel memakai kas (id tetap) dan jurnal yang
    sama → `paid`. Jawaban bayar tanpa slip (`bentuk_bayar`).
  - **Jalur lama dimatikan** (D8): `hr_payroll_service.pay_run`, `gl_service.pay_payroll_run`,
    `assert_payroll_cash_account`, `payroll_cash_accounts` dihapus (pemanggil hanya router bayar — dicari di seluruh repo);
    poster `pay_payroll_run` dicabut dari jenis registri `payroll_run`. Jurnal lama `payroll_pay` tetap dibaca (Jejak
    Dokumen, label sumber, `payroll_source_id`); proses lama yang jurnal `payroll_pay`-nya terbit tetapi kasnya gagal →
    kas baru menumpang jurnal itu.
  - **Setoran**: `GET /remittances` dan `…/outstanding` menerima `hr.view` **atau** `payroll.pay`; `outstanding?year=` →
    12 masa per jenis (`hr_remittance_service.outstanding_year`). `POST /remittances/{id}/void` (`payroll.void`, alasan
    ≥ 5 huruf): PERIKSA `done` (selain itu 409 "Setoran {nomor} berstatus {label}, jadi tidak bisa dibatalkan.") ·
    `preflight_posting(PT, tanggal setor)` · kas belum dicocokkan → NIAT `done → voiding` → kas dibalik lewat
    `post_durable` (`cash_transaction_void`, bertanggal setor) + kas `void` → `void`. Setoran `void` tidak dihitung
    `disetor`.
  - **Izin**: Finance bawaan + `payroll.pay` (`permissions_config.PYT4_DEFAULT_PAIRS`; instalasi lama lewat
    `sync_permission_modules`, PR-T9). Finance tidak mendapat `hr.view` (U9: rincian proses dan daftar karyawan 403).
  - **Layar**: tab **Setoran & Pajak** (`hr-payroll-remittances`, + `finance`): Gaji siap dibayar
    (`PayrollPayPanel.jsx`), Setoran BPJS dan PPh 21 (+ Batalkan, + tautan Rekap PPh 21 di Pusat Pajak), Rekap setoran
    setahun; pop-up **Bayar gaji** dan pop-up **Daftar transfer** (`TransferListPanel.jsx`) juga dari rincian Proses
    Gaji; sesudah dibayar "Dibayar {tanggal} dari {rekening}" + Daftar transfer + Lihat jurnal (L8).
- Status: implemented_pending_review

## Berkas berubah

| Berkas | Isi |
|---|---|
| `backend/services/hr_payroll_pay.py` (baru) | rekening gaji, antrean, daftar transfer + Excel, `pay_run`, `selesaikan_dari_kas`, `kas_bayar_hidup` |
| `backend/services/hr_payroll_service.py` | `pay_run` lama dihapus; `void_run` menolak proses yang punya kas pembayaran hidup |
| `backend/services/hr_remittance_service.py` | `STATUS_LABEL`, `RemittanceConflict`, `outstanding` tanpa setoran `void`, `outstanding_year`, `void_remittance` |
| `backend/services/gl_service.py` | `pay_payroll_run`, `assert_payroll_cash_account`, `payroll_cash_accounts` dihapus; `post_cash_void(…, date="")` |
| `backend/services/posting_registry.py` | poster `pay_payroll_run` dicabut; `_retry_cash` → `selesaikan_dari_kas` untuk kas `payroll_run` |
| `backend/services/cash_ledger.py` | teks `record_return_cash` (bayar gaji tidak lagi lewat sini) |
| `backend/services/gl_mapping_registry.py` | layar pemakai `sdm.hutang_gaji/bpjs/pph21` → "Setoran & Pajak" |
| `backend/routers/hr_payroll.py`, `backend/schemas_hr_payroll.py` | lima endpoint baru + bayar baru; baca setoran `require_any_permission`; `PayRunInput.paid_date` |
| `backend/permissions_config.py` | `PYT4_DEFAULT_PAIRS` |
| `backend/access_modules.py` | `VIEW_ACTION_REQUIREMENTS` untuk layar SDM ber-sumber daya `hr` (`PYT4_HR_SCREENS`), `settings-cfg-hr`, dan tab Setoran & Pajak — lihat "Menyimpang" butir 13 |
| `frontend/src/features/hr/PayrollPayPanel.jsx`, `TransferListPanel.jsx` (baru), `PayrollRemittancesView.jsx`, `PayrollRunsView.jsx` | layar |
| `frontend/src/config/hubTabs.js`, `navStructure.js`, `navMeta.js` | label tab, `finance` di hub & tab |
| Uji | `tests_mem/test_PYT4_bayar_gaji.py` (baru, 17), jest `features/__tests__/pyt4BayarGaji.test.js` (baru, 8), lapis A `tests/test_bp_PYT4_bayar_bersamaan_mongo.py` (baru, U14); disesuaikan: `tests_mem/test_PK22_penggajian.py` U9, `tests_mem/test_PRT9_izin_bawaan.py`, `tests/test_w2_targeted.py` (lapis A), jest `mnt1MenuKeuangan.test.js`, `roleReach.test.js`, `fixtures/view_main_permission.json`, `fixtures/access_builtin_fixture.json` (dibangkitkan) |
| Dokumen | `ENTITY_REGISTRY.md`, `memory/PRD.md`, `docs/KN_13_NAVIGATION_MAP.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.25, `CODEBASE_MAP.md`, `memory/INVENTARIS_MULTI_KOLEKSI_2026-09.md` (dibangkitkan; hanya nomor baris) |

## Uji penerimaan

Berkas: `backend/tests_mem/test_PYT4_bayar_gaji.py`. "Kode lama" = berkas yang sama di salinan bersih `6e79137`
(`bukti/PY-T4/merah_kode_lama.txt` 17/17 merah; varian sesi Admin untuk U3–U8 `merah_kode_lama_varian_admin.txt`).
Fixture: rekening, proses & slip, karyawan, setoran kewajiban lewat endpoint PK-22; posting gaji, bayar, daftar transfer,
ekspor, batal setoran, izin lewat HTTP. "Hari ini" dibekukan 2 Des 2026.

| ID | Lapis | Kode lama | Kode baru |
|---|---|---|---|
| U1 | B | merah: 404 | lulus — 3 baris, 12.750.000 = `totals.net`, 1 tanpa rekening (Cici `cash`); proses belum diposting 409 |
| U2 | B | merah: 403 (Finance tanpa `payroll.pay`) | lulus — `paid`, kas 12.750.000 R-GAJI 2026-12-01, jurnal Dr 2-1600 / Cr 1-1100, 0 jurnal `payroll_pay`, saldo 2-1600 proses 0; kirim ulang 409, tetap 1 kas 1 jurnal |
| U2b (tambahan, `02` §1 uji wajib) | B | merah: jurnal tidak gagal (jalur lama) → `paid` | lulus — jurnal dipaksa gagal → 409, `posted` + `pay_gl_status=failed`, kas `failed`; anulir ditolak 409; ulang dari panel → `paid`, 1 kas 1 jurnal |
| U2c (tambahan) | B | merah | lulus — gagal lalu Bayar lagi → `paid`, kas sama, 1 jurnal |
| U3 | B | merah: 403; Admin: **dibayar** dari R-OPS | lulus — 400 pesan spesifikasi; `posted`; 0 kas, 0 jurnal |
| U4 | B | merah: 403; Admin: 400 "Akun pembayaran '1-1200'…" | lulus — R-GAJI dipakai (kode akun 1-1200 diabaikan, Cr 1-1100), tanggal = hari ini; dua rekening gaji → 400 "Pilih rekening pembayaran gaji." |
| U5 | B | merah: 403; Admin: pesan lain | lulus — rekening `ent_ksc` dan rekening nonaktif → 400 "Rekening ini bukan rekening aktif PT penggajian." |
| U6 | B | merah: 403; Admin: **dibayar** | lulus — 400 "Tanggal bayar tidak boleh sebelum 2026-11-30."; bentuk salah 400 |
| U7 | B | merah: 403; Admin: **dibayar** (tanggal = jam sistem) | lulus — 409 pesan periode; `posted`; 0 kas |
| U8 | B | merah: 403; Admin: **dibayar** | lulus — 409 "Gaji bersih Dedi negatif (-Rp 100.000)…"; 0 kas |
| U9 | B | merah: 404 | lulus — antrean 200 (tanpa slip), rekening 200 (hanya R-GAJI), rincian proses 403, karyawan 403, kewajiban setahun 200 (12 masa × 2 jenis), riwayat setoran 200 |
| U10 | B | merah: 404 (transfer-list) | lulus — peran kustom "HR" (`hr.view`, `hr.update`, `payroll.create`): buat & ajukan 200; sahkan, bayar, daftar transfer 403 |
| U11 | B | merah (berantai U2 + 404) | lulus — 3 penerima + Total 12.750.000; Berita "Gaji November 2026 …"; kepala memuat rekening & tanggal; 1 jejak audit tanpa nominal |
| U12 | B | merah: 404 | lulus — Finance 403 (Z6); alasan < 5 huruf 400; `void`, kas `void`, pembalik Dr 1-1100 / Cr 2-1700 900.000 bertanggal 2026-11-10; Oktober disetor 0 sisa 900.000 (masa & setahun); batal ulang 409 |
| U13 | B | merah: 404 | lulus — rekening `[]`; bayar 400 "Belum ada rekening berperuntukan Gaji di PT ini…" |
| U14 | A | — | **ditulis** `tests/test_bp_PYT4_bayar_bersamaan_mongo.py` (dua `pay_run` bersamaan → satu `dict`, satu `PayrollConflict`; 1 kas, 1 jurnal) — belum teruji (lingkungan A milik integrator) |
| U9b (tambahan) | B | merah: menu dasar Finance tanpa Penggajian | lulus — menu dasar Finance = + Penggajian & Setoran & Pajak saja (tanpa Karyawan, Proses Gaji, Pengaturan › SDM); Finance + `hr.view` → Karyawan, Proses Gaji, Pengaturan › SDM bertambah; `view_actions` tab = `hr.view` atau `payroll.pay` |
| U15 | B | merah: 404 | lulus — Manajer Kosong & Sopir: antrean, rekening, daftar transfer, ekspor, bayar 403 "Anda belum punya akses … Minta Admin menambahkan akses 'SDM & Penggajian'." |
| U16 | layar | — (layar baru) | jest `pyt4BayarGaji.test.js` 8/8; **belum diuji jalan** (integrator, 1280/1024/390) |

### Contoh angka (U1 → U2) — daftar transfer → jurnal → kas → saldo hutang gaji

Proses `KND/PAY-U2` November 2026, `ent_kanda`; slip bersih Ani 5.000.000 (BCA 111), Bayu 4.500.000 (Mandiri 222),
Cici 3.250.000 (tanpa rekening).

1. **Daftar transfer**: 1 Ani 5.000.000 · 2 Bayu 4.500.000 · 3 Cici 3.250.000 (tunai). Total = 5.000.000 + 4.500.000 +
   3.250.000 = **12.750.000** = `totals.net`; 3 penerima, 1 tanpa rekening.
2. **Jurnal gaji** (posting, 2026-11-30): Dr 6-1000 12.750.000 / Cr 2-1600 12.750.000.
3. **Bayar** (Finance, R-GAJI, 2026-12-01) → **kas keluar** `cash_transactions` 12.750.000, `account_id` R-GAJI,
   `ref_type` `payroll_run`, `ref_id` id proses → **jurnal kas** (2026-12-01):

| Akun | Debit | Kredit |
|---|---:|---:|
| 2-1600 Hutang gaji (pemetaan `sdm.hutang_gaji`) | 12.750.000 | |
| 1-1100 Kas/bank (jenis kas rekening R-GAJI) | | 12.750.000 |

4. **Saldo 2-1600 untuk proses itu** (normal kredit) = 12.750.000 (jurnal gaji) − 12.750.000 (jurnal bayar) = **0**.
   `transfer_total` 12.750.000 = nominal kas keluar = Σ daftar transfer; `transfer_count` 3.

U12 (batal setoran): setoran BPJS Oktober 900.000 (jurnal kas Dr 2-1700 / Cr 1-1100, 2026-11-10) → pembalik Dr 1-1100
900.000 / Cr 2-1700 900.000 bertanggal 2026-11-10; kewajiban Oktober (360.000 + 540.000 = 900.000) − disetor 0 = sisa
**900.000**.

## Cek layar

Acuan: `docs/KN_37_STANDAR_UI_GUDANG.md`, `KN_08`, `UX_USABILITY_STANDARD.md`. Tanpa hex baru, `text-[<12px]`, `!py-*`
pada tombol, `<button>` bergaya sendiri, atau `type="date"` (form Catat Setoran kini `KNDatePicker`); `verify_ui_standard`
tetap 13 (sama dengan basis). Lebar kartu dihitung: konten 1024 px ≈ 1024 − 220 (bilah sisi) − 48 ≈ 756 px; 1280 px ≈
1012 px; sel tabel 12,5 px + bantalan 24 px.

| Layar | (1) tabel ⊂ kartu | (2) bantalan | (3) kepala kartu | (4) tombol mati | (5) status ikon+teks+warna | (6) cari/saring | (7) teks vs izin | (8) kosong/0 |
|---|---|---|---|---|---|---|---|---|
| Setoran & Pajak › Gaji siap dibayar (`PayrollPayPanel`) | 6 kolom (Nomor ±122 · Periode ±115 · Jenis ±74 · Karyawan ±88 · Total bersih ±115 · Aksi ±234) ≈ 748 px ≤ 756 di 1024; `head-wrap`, `overflow-x-auto`, kolom aksi `col-sticky-end` | `section-head` + `section-body`; kosong/memuat `section-pad` | judul saja; keterangan & alasan di badan | Bayar mati: "Pilih satu PT dulu." / pesan rekening gaji ditulis di bilah "Bayar: …" (bukan tooltip) | — (baris belum berstatus; semua Diposting) | antrean berhalaman 20 (`KNPager`) + "{n} penggajian menunggu dibayar"; isi ±1 baris per PT per bulan | label dari izin `payroll.pay`; bagian tidak tampil tanpa izin | satu keadaan kosong "Tidak ada penggajian yang menunggu dibayar."; galat = kotak + Coba lagi |
| Pop-up Bayar gaji (`PayDialog`, `FormModal`) | — | grid 2 kolom (1 kolom di HP) | judul "Bayar gaji" + subjudul nomor · periode · PT | Bayar gaji mati + alasan tertulis (tanpa rekening gaji / belum memilih / Semua PT) | — | pilihan hanya rekening Gaji (label nama · bank · nomor) | — | ringkasan "Total bersih Rp … untuk n karyawan (m tanpa rekening, dibayar tunai)"; konfirmasi N5 menyebut nominal, rekening, PT, tanggal |
| Daftar transfer (`TransferListPanel`, `DetailModal lg` 896 px) | 6 kolom ≈ 680 px ≤ 864 (bingkai); HP layar penuh + gulir | bingkai `framed` p-4 | judul di baris sendiri; "Dibayar … dari …" + "Unduh Excel" di bilah sendiri | Unduh mati bila tanpa baris (teks kosong tertulis) | baris tunai: `status-pill status-pending` + ikon + "Tanpa rekening — bayar tunai" | ±puluhan baris per proses, urut nama (tanpa kotak cari — sama dengan slip) | — | kosong "Penggajian ini tidak memuat slip."; kaki "Total Rp … · n penerima" |
| Setoran BPJS dan PPh 21 (`PayrollRemittancesView`) | riwayat: Jenis digabung ke sel Nomor (baris kedua) → 6 kolom ≈ 700 px ≤ 756 (dulu 6 kolom + Aksi akan ≈ 770); Aksi `col-sticky-end` | `section-head`/`section-body` | judul + Muat ulang | Catat Setoran (PK-22) tetap; Batalkan hanya pemegang `payroll.void`, mati saat Semua PT + "Batalkan: Pilih satu PT dulu." | Tercatat (`status-done`) / Dibatalkan (`status-cancelled`) / Sedang dibatalkan, Diproses (`status-pending`) / Jurnal gagal (`status-rejected`) — ikon + teks | `FilterChips` jenis + masa; berhalaman 20 | Finance tanpa tombol Batalkan (tanpa teks "bukan wewenang") | kosong satu kali; galat batal = kotak galat sendiri |
| Rekap setoran setahun | dua tabel 4 kolom (Masa ±122 + 3 × ±115 ≈ 467 px): berdampingan ≥ 1280 (`xl:grid-cols-2`, ±500 px per tabel), bertumpuk di 1024 | `section-head` + grid `p-3` | judul + pemilih tahun | — | sisa > 0 jingga + angka (bukan warna saja) | pemilih tahun (3 tahun) | — | masa tanpa angka "—" (bukan 0 mendominasi); Semua PT satu kalimat |
| Proses Gaji › rincian (`PayrollRunsView`) | — (tabel slip tidak berubah) | — | tombol di bilah aksi; "Daftar transfer" btn-sm | Bayar mati saat Semua PT + "Pilih satu PT dulu." | status proses tetap (`PayrollRunStatus`) | — | — | sesudah dibayar: "Dibayar {tanggal} dari {rekening} · n penerima" + Daftar transfer + Lihat jurnal (bila `accounting.view`) |

Belum diuji jalan di peramban (U16) — integrator memotret 1280/1024/390.

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`efc1cc6`** — satu gate
untuk CR-T3 ((a) `2ac8e6c` · (b) `945da6e` · cek layar `eaba57f`), PY-T5 (`b014a38`), PY-T4 (`61cf7a1` · cek layar `efc1cc6`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`fc95d36`: 12 / 39). Kuitansi: `bukti/PY-T4/gate_quick_receipt.md`, `gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- Pelaksana menggabung ke `eaba57f`; cabang lalu maju dengan PY-T5 (`b014a38`, menyentuh `hr_payroll_service.py`,
  `routers/hr_payroll.py`, PRD, KN_32). Integrator menggabung tiga arah di atas PY-T5: `hr_payroll_service.py` dan
  `routers/hr_payroll.py` tergabung bersih (PY-T5 menghapus `my_payslips` lama, PY-T4 menghapus `pay_run` lama — keduanya
  dipertahankan); bentrok PRD (dua catatan) dan KN_32 (PY-T5 §9.28, **PY-T4 → §9.29**); fixture akses dan
  `configKeyIndex.json` dibangkitkan ulang → **`61cf7a1`**. `tests_mem` sesudah gabung **2227 lulus + 1 gagal** (PY-T5 U2: tanggal bayar kini `paid_date` proses dari PY-T4, bukan tanggal `paid_at`) → harapan uji disesuaikan, berkas PY-T5 + PY-T4 **28/28**; uji penuh selebihnya hijau (integrator — gabung sendiri).
- Lingkungan A (data acuan sesudah `restore_demo`, kode `61cf7a1`; `bukti/PY-T4/integrator_lapis_A.txt`): lapis A **U14 lulus**
  (`test_bp_PYT4_bayar_bersamaan_mongo.py`: dua Bayar bersamaan → satu kas); `test_w2_targeted.py` 7 lulus, `w2_020` tidak bisa
  dijalankan di lingkungan ini (uji async ber-`pytest.mark.asyncio`, `pytest-asyncio` tidak terpasang di venv lingkungan A —
  kendala lama, uji itu memang async sejak sebelum unit ini).
- Uji jalan **U16** (integrator; proses Oktober `ent_ksc` diposting lewat API di database uji): SDM › Penggajian › **Setoran &
  Pajak** — "Gaji siap dibayar" 6 kolom = **762 px = kartu** di 1024 (Daftar transfer + Bayar terlihat), Setoran BPJS/PPh 21,
  riwayat setoran, rekap setahun (Oktober kewajiban BPJS Rp 6.256.458, PPh 21 Rp 1.330.710 — sisa berwarna); `overflowX` 0.
  **Cacat ditemukan dan diperbaiki (`efc1cc6`)**: isian Masa gaji tampil "2026-11 (tidak ada di daftar)" — `recentMonths()`
  (`payrollUtils.js`, juga `leaveUtils.js`) menambah 7 jam lalu memakai `setDate`/`setMonth` waktu lokal, sehingga di peramban
  ber-zona WIB pukul 17.00–24.00 daftar bulan mulai dari bulan lalu (layar Proses Gaji, Slip, Komponen & Masukan, Setoran,
  Cuti — perilaku lama sejak PK-22). Kini pengambil UTC; uji `bulanWibPenggajian` (TZ=Asia/Jakarta: lama 1 gagal, baru 2 lulus)
  (`bukti/PY-T4/cek_*.png`).
- **Untuk pemilik:** (1) syarat aksi menu SDM ditambahkan pelaksana — peran kustom yang hanya memegang `payroll.*` tanpa
  `hr.*` tidak lagi melihat menu SDM yang dulu tampil lalu 403 (mohon konfirmasi); (2) tanggal bayar sesudah hari ini tidak
  ditolak (spesifikasi tidak mengatur).

Pelaksana (catatan asli):

Belum dijalankan (gate penuh = integrator, lingkungan A). Yang dijalankan pelaksana di lingkungan B:

- `tests_mem`: basis bersih `6e79137` (salinan `git archive`) **2101 lulus / 2 dilewati / 2 xfail** → W **2118 / 2 / 2**
  (+17 `test_PYT4_bayar_gaji.py`; `bukti/PY-T4/tests_mem_{B,W}.txt`). Lari penuh pertama di W: 1 merah
  `test_PRT6_U6_menu_peran_bawaan_bertambah_dari_izin` (`tests_mem_W_lari1_PRT6.txt`) → diperbaiki (Menyimpang 13), lari
  ulang 0 merah.
- Jest penuh: basis **1018** → W **1026** (+8 `pyt4BayarGaji.test.js`); 35 suite gagal dimuat di keduanya (`cmdk` →
  `@radix-ui`, kendala lingkungan; daftar suite identik).
- `hitung_penjaga.sh`: **identik** basis (auth 26 · ui_standard 13 · i18n 103 · create_modal 6 · page_tabs 1 · to_list 5 ·
  entity_label 2). Penjaga lain basis → W (`penjaga_tambahan_{B,W}.txt`): `verify_posting_coverage` 138/0 → **137/0**
  (fungsi `pay_payroll_run` dihapus) + uji-diri hijau; `verify_cash_single_door` 740/0 → 741/0 + uji-diri hijau;
  `verify_atomic_claim` 161/0 (+uji-diri 64 kasus hijau; inventaris dibangkitkan, hanya nomor baris); `verify_role_gate_ui`
  31/0; `verify_detail_modal` 30/0 → 31/0; `verify_permission_checked` 615/0; `verify_payment_vocab` 1836/0 → 1839/0;
  `verify_access_catalog_nav` 0 (+uji-diri); `verify_money_idempotency` 19/0; `verify_ui_contrast` 58/0;
  `verify_config_fallback` (+`--entity`) 159/0; `verify_config_text` 3402/0; `audit_config_wiring --strict` hijau dan
  `check_nav_map` PASS (salinan berjalur W); `verify_codebase_map` hijau; `gen_config_key_index --check` selaras;
  `tests/test_fe03_access_catalog.py` 6/6; `verify_api_contract` A/C hijau, B 1 galat sama dengan basis
  (`MobileRoleSummary`); `ux_audit --strict` 13 galat / 11 peringatan sama dengan basis; `validate_compliance` (salinan
  berjalur) 3 gagal sama dengan basis (`.env` frontend).

## Penggabungan

- HEAD tujuan: **`945da6e`** (`/home/user/KNHOST`, dibaca saja). Saat mulai HEAD = `c3fa3f8`; `6e79137` **bukan leluhur**
  HEAD (integrator memetik KM-T2 + PY-T3 sebagai `4b219c4`, `9794ec7`, `649b7dc`), tetapi isi kodenya sama (`git diff
  6e79137 c3fa3f8` di luar `docs/reviews` hanya `docs/blueprint/STATUS.md`) — jadi digabung ke HEAD terbaru. Selama
  penggabungan HEAD maju empat kali: `b7837de` (MN-T2) → `c8c6d03` (laporan MN-T2) → `fc95d36` (CR-T4) → `945da6e`
  (laporan CR-T4, CR-T3 (a) `2ac8e6c` + (b) `945da6e`). Tiap kali T disetel ulang ke HEAD baru dan berkas unit digabung
  lagi (`scratchpad/pyt4_gabung.py`: berkas di HEAD sama dengan B → salin; beda → `git merge-file -p <HEAD> <B> <W>`;
  baru → salin).
- Berkas yang juga diubah HEAD, digabung tiga arah dengan kedua perilaku dipertahankan:
  - otomatis: `ENTITY_REGISTRY.md` (CR-T4/CR-T3), `backend/access_modules.py` (CR-T3; blok syarat menu PY-T4 utuh —
    perbandingan menu per peran HEAD → T sama dengan basis → W: hanya Finance + `hr-payroll-hub`, `hr-payroll-remittances`,
    `bukti/PY-T4/nav_H.json`/`nav_T.json`), `docs/KN_13_NAVIGATION_MAP.md`, `memory/PRD.md`,
    `frontend/src/config/navMeta.js`, `frontend/src/config/__tests__/fixtures/view_main_permission.json` (MN-T2);
  - **bentrok** `backend/permissions_config.py` — blok `CRT3_DEFAULT_PAIRS` (CR-T3) dipertahankan utuh, blok
    `PYT4_DEFAULT_PAIRS` menyusul sesudahnya;
  - **bentrok** `backend/tests_mem/test_PRT9_izin_bawaan.py` — dua putaran `TAMBAHAN_SESUDAH` (CR-T3 lalu PY-T4);
  - **bentrok** `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` — §9.25 MN-T2, §9.26 CR-T4, §9.27 CR-T3 dipertahankan; bagian
    PY-T4 menjadi **§9.28** (di W tetap §9.25).
  - `routers/hr_payroll.py`, `PayrollRunsView.jsx`, `PayslipsView.jsx` tidak disentuh unit lain → disalin.
- Dibangkitkan ulang di T: `CODEBASE_MAP.md`, `memory/INVENTARIS_MULTI_KOLEKSI_2026-09.md`, fixture akses
  (`access_builtin_fixture.json`, `access_nav_fixture.json`; `test_fe03_access_catalog.py` 6/6), `configKeyIndex.json`
  (selaras, tidak berubah). Hitungan uji lama: KF-T1 `*_KUNCI` tidak berubah (unit tanpa kunci baru); PR-T9 dijumlahkan
  lewat blok (CR-T3 + PY-T4, tanpa migrasi baru); indeks wajib tidak berubah.
- Sesudah lari uji, HEAD maju ke **`eaba57f`** (CR-T3 cek layar: hanya `CreditOverridesPanel.jsx`, tidak menyentuh berkas
  unit) — T dipindah dengan `checkout --detach`, `CODEBASE_MAP.md` dibangkitkan ulang, jest penuh diulang.
- Angka di T dibanding HEAD murni (salinan `git archive 945da6e`; `bukti/PY-T4/*_{HEAD,T}.txt`):
  - `tests_mem`: HEAD **2199 / 2 / 2** → T **2216 lulus / 2 dilewati / 2 xfail, 0 gagal** (+17).
  - Jest penuh: HEAD **1040** → T **1048** (+8; di `eaba57f` juga 1048); 35 suite gagal dimuat di keduanya (daftar sama).
  - `hitung_penjaga.sh`: T = HEAD (auth 26 · ui_standard 11 · i18n 102 · create_modal 5 · page_tabs 1 · to_list 5 ·
    entity_label 2). Penjaga lain HEAD → T: `verify_posting_coverage` 138/0 → 137/0; `verify_cash_single_door` 743/0 →
    744/0; `verify_detail_modal` 29/0 → 30/0; `verify_payment_vocab` 1842/0 → 1845/0; `verify_role_gate_ui` 31/0;
    `verify_atomic_claim` 161/0; `verify_permission_checked` 617/0; `verify_access_catalog_nav` 0;
    `verify_money_idempotency` 19/0; `verify_ui_contrast` 58/0; `verify_config_fallback` (+`--entity`) 160/0;
    `verify_config_text` 3465/0; `audit_config_wiring --strict` hijau; `check_nav_map` PASS (salinan berjalur T);
    `verify_codebase_map` hijau.

## Uji lama yang disesuaikan (perilaku yang sengaja diubah)

| Uji | Sebab | Penyesuaian |
|---|---|---|
| `tests_mem/test_PK22_penggajian.py` U9 | kode akun `cash_account` tidak dibaca; jurnal bayar = jurnal kas | 400 = belum ada rekening gaji; sesudah rekening ada → dibayar, jurnal kas Dr 2-1600 / Cr 1-1100, 0 jurnal `payroll_pay` |
| `tests_mem/test_PRT9_izin_bawaan.py` | pasangan bawaan baru | `PYT4_DEFAULT_PAIRS` di `TAMBAHAN_SESUDAH` |
| lapis A `tests/test_w2_targeted.py` (W2-022/023) | sama dengan PK-22 U9 | rekening berperuntukan uji, periode lampau 2020-02, jurnal kas, kirim ulang 409 (ditulis; belum dijalankan) |
| jest `mnt1MenuKeuangan.test.js`, `roleReach.test.js`, `fixtures/view_main_permission.json` | label tab; Finance mendapat tab; izin layar `payroll.pay` | label "Setoran & Pajak"; `PYT4_SETORAN_FINANCE`; izin alternatif `["payroll","pay"]` (uji backend MNT1 U4 memakai tabel yang sama) |

## Menyimpang dari blueprint

1. **Daftar transfer = pop-up rincian** (`DetailModal`, standar INV-UI-08 `verify_detail_modal`), bukan "panel samping".
2. **Antrean bayar** memuat `entity_id` dan `journal_date` selain kolom spesifikasi (PT untuk pop-up, batas awal tanggal).
3. **Jawaban bayar tanpa slip** (`bentuk_bayar`): Finance tidak memegang `hr.view`, jadi rincian slip tidak dikirim balik.
4. **Field tambahan** `pay_account_name` (potret nama rekening untuk "Dibayar … dari …") dan `pay_gl_status`/`pay_gl_error`
   kini menandai jurnal kas bayar.
5. **Anulir proses yang punya kas pembayaran hidup → 409** (kas yang jurnalnya gagal menahan proses `posted`; jurnal yang
   menyusul akan mendebit hutang gaji proses yang dibalik).
6. **Ulang dari panel Posting Gagal** (jenis Transaksi Kas) menyelesaikan proses menjadi `paid` (`_retry_cash`).
7. **Status salah** → 409 "…berstatus {label}, jadi tidak bisa dibayar." (dulu 400 "Run status … harus 'posted'"); tanggal
   bayar berbentuk salah → 400 "Tanggal bayar tidak dikenali (TTTT-BB-HH)." (tidak ada di tabel galat).
8. **Pembalik setoran bertanggal setor** (`post_cash_void` menerima `date`; bawaan tetap hari ini) — sesuai PERIKSA
   `preflight_posting(entity_id, paid_date)` spesifikasi. Kas setoran yang sudah dicocokkan dengan mutasi bank → 409.
9. **`outstanding`**: `period` kini opsional; `year` tanpa `period` → `{year, kinds: [{kind, label, rows[12], total}]}`.
10. **Riwayat setoran**: kolom Jenis digabung ke sel Nomor supaya kolom Aksi muat di kartu 1024 px.
11. **Gaji bersih nol** → `paid` tanpa kas (perilaku lama dipertahankan; `create_cash` menolak nominal 0).
12. **Jalur lama dihapus** di unit ini (D8): `gl_service.pay_payroll_run` + dua pembantu akun bayar; `verify_posting_coverage`
    turun satu cek (138 → 137).
13. **Syarat aksi menu SDM** (`access_modules.VIEW_ACTION_REQUIREMENTS`, tidak disebut spesifikasi). Modul "SDM &
    Penggajian" memuat `hr` dan `payroll`, dan menu yang "dibuka izin" dihitung per modul (`nav_allowed_for_perms`). Begitu
    Finance memegang `payroll.pay`, seluruh menu SDM (Karyawan, Kehadiran, Proses Gaji, Pengaturan › SDM, …) masuk menu
    dasar Finance, sehingga ketika Admin memberi Finance akses SDM menu itu **tidak lagi bertambah** (PR-T6: uji
    `test_PRT6_U6_menu_peran_bawaan_bertambah_dari_izin` merah di lari penuh pertama). Kini layar SDM yang hanya melayani
    sumber daya `hr` butuh salah satu aksi `hr.*` (`settings-cfg-hr`: `hr.*` atau `settings.*`), tab Setoran & Pajak butuh
    `hr.view` atau `payroll.pay`. Dibandingkan basis (`bukti/PY-T4/nav_B.json` vs `nav_W.json`): 13 peran bawaan tidak
    berubah kecuali Finance (+ `hr-payroll-hub`, `hr-payroll-remittances`); Finance + `hr.view` menambah menu yang sama
    seperti di basis (kecuali dua itu, kini dasar); peran kustom ber-`hr.*` tidak berubah; peran kustom yang hanya
    memegang `payroll.*` tanpa `hr.*` tidak lagi melihat menu SDM yang endpoint utamanya `hr.view` (dulu tampil lalu 403).

### Usulan koreksi berkas unit (teks pengganti persis; berkas unit tidak diubah pelaksana)

- Layar, butir kedua: "**Daftar transfer** (panel samping): …" → "**Daftar transfer** (pop-up rincian, `DetailModal`): …".
  Alasan: INV-UI-08.
- Server 2: "…berisi proses berstatus `posted` PT aktif: `id`, `number`, `period`, `run_type`, `employees`, `net_total`,
  `posted_at`." → "…: `id`, `number`, `period`, `run_type`, `employees`, `net_total`, `posted_at`, `entity_id`,
  `journal_date`." Alasan: pop-up Bayar butuh PT proses dan batas tanggal tanpa membuka rincian (Finance tanpa `hr.view`).

## Asumsi

- Spesifikasi (`ASUMSI` unit): peran HR = peran kustom; karyawan tanpa rekening ikut satu kas keluar; dibayar sekaligus;
  batal setoran = `payroll.void`.
- Tanggal bayar sesudah hari ini tidak ditolak (spesifikasi diam; periode diperiksa).
- "Semua PT": antrean & riwayat menampilkan PT yang ditugaskan (baca saja); semua tombol tulis mati.
- Excel: baris tunai berisi Bank "Tunai" dan Nomor rekening "Tanpa rekening — bayar tunai"; format berkas khusus bank di
  luar lingkup (H8).

## Hambatan lingkungan

- Lingkungan A (MongoDB asli, peramban) milik integrator: U14 ditulis, belum dijalankan; U16 belum diuji jalan.
- Jest: 35 suite gagal dimuat (`cmdk` → `@radix-ui`) sama dengan basis.

## Yang perlu direview

- Proses yang berhenti di `paying` (proses server mati di antara klaim dan selesai) tidak pulih sendiri — sama dengan
  perilaku sebelum unit ini; tidak ada jalur pemulihan otomatis.
- Data acuan: proses `posted` lama dengan jurnal `payroll_pay` tanpa kas (jalur lama gagal di kas) akan dibayar dengan kas
  yang menumpang jurnal lama — tidak ada kueri data nyata dijalankan (H3).
- Syarat aksi menu SDM (Menyimpang 13): peran kustom yang memegang `payroll.*` tanpa satu pun `hr.*` tidak lagi melihat
  menu Karyawan/Kehadiran/Proses Gaji/Komponen (endpoint utamanya `hr.view`, dulu tampil lalu 403); mohon dikonfirmasi
  sebagai perilaku yang diinginkan.
- Titik henti: H4 tidak tersentuh (akun & arah = spesifikasi: Dr `ACC_HUTANG_GAJI`/pemetaan `sdm.hutang_gaji`, Cr kas
  rekening; pembalik = balikan jurnal asal). H3: tanpa skrip data lama (spesifikasi: tanpa migrasi). H5: tanpa sakelar.
  H8: tanpa rahasia; Excel generik.

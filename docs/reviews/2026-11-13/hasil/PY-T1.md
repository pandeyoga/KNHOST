# PY-T1 — Slip gaji sebagai daftar komponen per PT, antrean masukan, dan jenis proses gaji

- Commit awal: `35a1f9a` (worktree kerja, basis B)        - Commit akhir: (a) `e980399`, (b) `64143aa`, uji lapis A `b62ef45`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PY-01, PY-02, PY-13, PY-14 (spesifikasi `docs/blueprint/unit/PY-T1.md`); keputusan K-37, K-40 (K-41 dari PK-22)
- Risiko tinggi → dua serah-terima (`00` §8): **(a)** jalur baru di samping jalur lama — koleksi `hr_pay_components`
  (isi awal 14 komponen per PT) + `hr_pay_inputs` (antrean, empat fungsi), endpoint komponen & masukan, tab **Komponen &
  Masukan**, pembangun `components[]` murni yang dipanggil `compute_payslip` TANPA mengubah kolom lama (uji: Σ komponen =
  kolom lama). **(b)** pengalihan — kolom lama diturunkan dari komponen, masukan ikut proses (`take_for_run` /
  `release_for_run`), jenis proses Reguler · THR · Susulan, `active_key` berindeks unik parsial (menggantikan penjaga
  baca-lalu-hapus), PPh 21 gabungan bulan, jurnal gaji & PDF dari komponen, layar Proses Gaji (tabel berkomponen, panel
  Cari slip, teks), tab Slip Gaji dihapus (alias), `patch_attendance` menghitung ulang lembur, skrip migrasi proses lama.
- Salinan keadaan (a): `scratchpad/PY-T1_a_state/` (`FILES.txt` 29 berkas, `BASIS.txt` = `35a1f9a`); (a) yang sudah
  digabung ke HEAD tujuan: `scratchpad/PY-T1_a_merged/` (lihat "Penggabungan").

## Cek ulang "Keadaan sekarang" (spesifikasi dibaca di `3132cc4`; dicek di `35a1f9a`)

| Butir spesifikasi | Hasil di HEAD awal |
|---|---|
| Slip berkolom tetap — `hr_payroll_service.py:302` (`base_salary`) | Berlaku, bergeser — `:354` |
| Tunjangan dijumlah satu angka — `:110` (`_sum_allowances`); master `schemas_hr.py:21` (`AllowanceInput`) | Berlaku — `:153`; `schemas_hr.py:21` |
| Komisi satu angka dari mesin — `:245` (`_commission_for`) | Berlaku, bergeser — `:294` |
| Satu proses per PT per periode — `:362` (`existing_run`), `:370` (`create_run`) | Berlaku, bergeser — `:418`, `:424` (PK-22: `cancelled`/`void` tidak menghalangi) |
| Penjaga kembar baca-lalu-hapus — `:392` (`dup`) | Berlaku, bergeser — `:452` |
| Kunci jurnal lama PT+periode — `gl_service.py:3042`, `:3109` (`src_id`) | **Sudah tidak berlaku** (PK-22): `payroll_source_id` `:3461` = id proses (proses lama tetap kunci lama lewat `journal_id`) — posting `:3499`, bayar `:3576`. Tidak diubah |
| PPh 21 dari bruto slip itu saja — `:281` (`ter_rate`); slip lain bulan itu tidak dilihat `:231` (`_prior_year_slips`) | Berlaku, bergeser — `:333`, `:274` |
| Format periode tidak divalidasi — `schemas_hr_payroll.py:8` | Berlaku — `:8` ("2026-13" → 400 dengan pesan lain: "Periode gaji harus berbentuk TTTT-BB (diberi '2026-13')."; "Okt" → 400 serupa) |
| Pembaca kolom lama: jurnal `gl_service.py:3049` | Berlaku, bergeser — `:3506` |
| Total proses `_accumulate` `:320` | Berlaku, bergeser — `:372` |
| PDF `hr_payroll_pdf.py:72`, `:83` (persen ditulis mati) | Berlaku — `:72`, `:83` ("BPJS Kesehatan (1%)") |
| Ekspor `export_registry_more.py:268` | Berlaku — `:268` (kolom lama tetap terisi; tidak diubah) |
| Rekap PPh 21 `tax_center_service.py:49` | Berlaku, bergeser — `_period_pph21` `:65` (PK-40: dpp = Σ `tax_gross` slip; tidak diubah) |
| Analitik `hr_analytics_service.py:28` (`PAY_KEYS`) | Berlaku — `:28` (tidak diubah) |
| Profil karyawan `routers/hr.py:372` (`_PAY_PII`) | Berlaku — `:372`; ditambah kolom baru slip |
| Layar `PayrollRunsView.jsx:204` (`Komisi`), `PayslipsView.jsx:98` (`DRow`) | Berlaku, bergeser — `:330`; `:98` |
| PY-14 label "Payroll Run" `hubTabs.js:196` | **Sudah tidak berlaku** — MN-T1 sudah melabeli "Proses Gaji" (`hubTabs.js:199`) |
| PY-14 teks konfirmasi "pengembalian ke draf" `PayrollRunsView.jsx:66` | Berlaku, bergeser — `:118` |
| PY-14 jam absen tanpa hitung ulang lembur `routers/hr_attendance.py:429`; penghitung `hr_attendance_service.py:76` | Berlaku, bergeser — `:484`; `:76` |
| Tab "Slip Gaji" = tabel yang sama `hubTabs.js:197` | Berlaku, bergeser — `:200` |

## PY-01 — slip berkolom tetap; komponen per PT tidak ada

- Berlaku di HEAD: ya (bukti merah `bukti/PY-T1/merah_kode_lama.txt`: U1 `ImportError hr_pay_components`; U10b/U3/U10
  404 endpoint komponen).
- Akar masalah: slip dibangun sebagai sederet kolom tetap; tunjangan dijumlah (namanya hilang); tidak ada data komponen
  per PT.
- Perubahan perilaku: `services/hr_pay_components.py` — koleksi `hr_pay_components` (unik `(entity_id, code)`), isi awal
  idempoten tiap PT (saat server menyala `bootstrap.py` + saat daftar PT pertama dibaca): `GAJI_POKOK`, `TUNJANGAN`,
  `LEMBUR`, `KOMISI` (mesin komisi), `THR` (hanya proses `thr`), `BPJS_KES/JHT/JP` (potongan), `BPJS_KES_PT/JHT_PT/JP_PT/
  JKK/JKM` (tanggungan), `PPH21`. Fungsi murni `earning_components`, `statutory_components`, `derive_columns`,
  `components_match_columns`. Slip memuat `components[]` (tunjangan satu baris per nama: "Tunjangan — Transport").
  (b): kolom lama slip = Σ komponen per `bucket`; `salary_earnings`/`gross`/`net`/`tax_gross` dari rumus spesifikasi.
  Endpoint `GET/POST/PATCH /api/hr/payroll/components` (`hr.view` / `hr.manage_payroll`) dengan pesan spesifikasi
  (409 kode kembar, 400 potongan tanpa akun, 400 bawaan ganti jenis).

## PY-02 — angka dari modul lain masuk tanpa antrean

- Berlaku di HEAD: ya (U9 `ImportError hr_pay_inputs`; U16/U8 404).
- Perubahan perilaku: `services/hr_pay_inputs.py` — koleksi `hr_pay_inputs` (unik `source_key`, indeks
  `(entity_id, pay_period, status)`, `(used_run_id)`), `enqueue_input` (sumber → `approved`; kunci sama = dokumen sama),
  `create_manual_input` (`pending`, alasan wajib), `approve_input`, `cancel_input`/`cancel_input_by_id`, `take_for_run`
  (`approved → used` bersyarat), `release_for_run` (`used → approved`), `retake_inputs` (kompensasi). Endpoint
  `GET/POST /api/hr/payroll/inputs`, `POST …/{id}/approve`, `…/{id}/cancel` (izin dan pesan spesifikasi). Proses gaji
  (b): `create_run` dan hitung ulang mengambil masukan SEBELUM slip dihitung; batal, anulir, hitung ulang melepasnya.

## PY-13 — satu proses per PT per periode; periode tidak divalidasi; PPh 21 per slip

- Berlaku di HEAD: ya (U4: `POST run_type=thr` → 200 mengembalikan proses reguler; U11: pesan lain; U14 tanpa
  `active_key`).
- Perubahan perilaku: `run_type` (`regular`·`thr`·`susulan`), `seq`, `active_key` = `<PT>:<periode>:regular` hanya pada
  reguler hidup, unik parsial `hr_payroll_runs.uq_active_key` (indeks wajib PK-14) — sisip kembar bersamaan →
  `DuplicateKeyError` → proses pemenang dikembalikan (penjaga baca-lalu-hapus dihapus). Batal/anulir melepas kunci.
  Periode diperiksa `^\d{4}-(0[1-9]|1[0-2])$` → 400 "Periode harus berbentuk TTTT-BB, mis. 2026-10." (buat & pratinjau).
  THR/susulan tanpa masukan → 400 spesifikasi. PPh 21 gabungan bulan: `pph21_month` = bruto pajak bulan × tarif(bruto
  pajak bulan); `pph21` slip = `pph21_month` − Σ PPh 21 slip terdahulu bulan itu (proses lain yang hidup dan dibuat lebih
  dulu); masa terakhir menghitung ulang setahun termasuk slip terdahulu bulan itu. Tarif tetap dari tabel berlaku (PK-46,
  `ter_rate`/`aturan_pph21`); isinya tidak disentuh (H4).

## PY-14 — label, teks konfirmasi, tab Slip Gaji ganda, lembur absen

- Berlaku di HEAD: sebagian (label sudah "Proses Gaji" sejak MN-T1); teks, tab ganda, dan U15 (lembur 120 tetap 120)
  berlaku.
- Perubahan perilaku: teks sahkan & kembalikan persis spesifikasi; tab `hr-payslips` dihapus dari `HUB_TABS`, id lama =
  alias ke Proses Gaji (`viewAliases.js`, preset `cari`; rute cadangan merender Proses Gaji dengan panel Cari slip
  terbuka); `patch_attendance` menghitung ulang `work_min`, `late_min`, `early_leave_min`, `overtime_min` (+`std_min`)
  dengan `compute_metrics` saat `clock_in`/`clock_out` berubah.

## Jurnal, PDF, dan pembaca kolom lama

- Jurnal (`gl_service.payroll_journal_lines`, dipakai `post_payroll_run` — pintu tetap PK-22/`post_durable`, jenis
  registri `payroll_run`, kunci = id proses): pendapatan → Dr 6-1000 (atau `account_code` komponen), komisi menurut
  `commission_mode`, tanggungan → Dr 6-1100, BPJS → Cr 2-1700, PPh 21 → Cr/Dr 2-1800, potongan lain → Cr akun
  komponennya, bersih → Cr 2-1600. Slip lama tanpa komponen → dari kolom (sama dengan sebelumnya).
- PDF: `hr_payroll_pdf.payslip_pdf_rows(slip)` murni (bagian PENERIMAAN · POTONGAN · GAJI BERSIH DITERIMA · TANGGUNGAN
  PERUSAHAAN (INFORMASI); persen BPJS dari `rate` komponen; masa terakhir "PPh 21 (hitung ulang tahunan)").
- Pembaca lain (ekspor, rekap PPh 21, analitik, setoran kewajiban, posting gagal) membaca kolom lama yang tetap terisi;
  tidak diubah. `routers/hr.py` `_PAY_PII` ditambah `components`, `other_earnings`, `other_deductions`, `tax_gross`,
  `pph21_month(_detail)`, `pph21_annual`, `overtime_events` (semuanya nominal gaji).

## Serah-terima (a) — jalur baru, jalur lama tetap

| Berkas | Isi (a) |
|---|---|
| `backend/services/hr_pay_components.py` (baru), `backend/services/hr_pay_inputs.py` (baru) | koleksi, isi awal, validasi, pembangun komponen, antrean + empat fungsi |
| `backend/services/hr_payroll_service.py` | `bpjs_info`, `_components_map`; `compute_payslip` menambah `components[]` di samping kolom lama (kolom lama TIDAK diubah) |
| `backend/routers/hr_payroll.py`, `backend/schemas_hr_payroll.py` | endpoint komponen & masukan |
| `backend/bootstrap.py` | isi awal komponen tiap PT saat server menyala |
| `backend/indexes.py`, `backend/entity_scope.py`, `scripts/verify_contract.py` | indeks (unik `uq_entity_code`, `uq_source_key` — REQUIRED_UNIQUE_INDEXES), koleksi ber-PT, kontrak |
| `backend/access_modules.py` + fixture akses | `nav` modul `hr` + `hr-pay-components` |
| Layar | `features/hr/PayComponentsView.jsx` (baru), `config/hubTabs.js`, `config/navMeta.js`, `appViewImports.js`, `AppViewRouter.jsx` |
| Uji | `tests_mem/test_PYT1_komponen_gaji.py` (U1, U9, U10b, U16 lulus; 12 `xfail(strict)` menunggu (b)); `tests/test_bp_PYT1_data_acuan.py` (U2, U14 — ditulis); jest `features/__tests__/pyt1KomponenMasukan.test.js` (8); disesuaikan: `tests_mem/test_PK14_indeks_wajib.py` (`PYT1_INDEKS = 2`), `tests/test_bp_PK14_indeks_wajib.py` (23 → 25), jest `mnt1MenuKeuangan.test.js` (label tab hub), `roleReach.test.js` (`PYT1_KOMPONEN`), `fixtures/view_main_permission.json` |
| Dokumen | `ENTITY_REGISTRY.md`, `docs/KN_13_NAVIGATION_MAP.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.12 (di T: §9.16), `CODEBASE_MAP.md` |

Angka (a): lihat "Gate".

## Serah-terima (b) — pengalihan

| Berkas | Perubahan (b) |
|---|---|
| `backend/services/hr_payroll_service.py` | `compute_payslip` menurunkan kolom lama dari komponen (`run`, `run_type`, `inputs`, `month_prior`); `_month_prior_index` (PPh 21 gabungan bulan, dua kueri per proses); `_build_slips`, `preview_run(run_type)`, `existing_run` (hanya reguler), `create_run(run_type)` (ambil masukan → hitung → slip; `active_key` + `DuplicateKeyError`; penjaga baca-lalu-hapus dihapus), `rollback_run` (+lepas masukan), `recalculate_run` (lepas → ambil lagi; gagal → `retake_inputs`), `submit_run` (409 bila masukan dibatalkan sesudah dihitung), `cancel_run`/`void_run` (lepas kunci & masukan), `_accumulate` (+`other_deductions`); `_sum_allowances` dihapus (tidak ada pemakai lain — dicari di seluruh repo) |
| `backend/services/hr_pay_inputs.py` | `retake_inputs` |
| `backend/services/gl_service.py` | `payroll_journal_lines` (murni) dipakai `post_payroll_run` |
| `backend/services/hr_payroll_pdf.py` | `payslip_pdf_rows` + `payslip_pdf_bytes` dari baris itu |
| `backend/routers/hr_payroll.py`, `backend/schemas_hr_payroll.py` | `run_type` di buat & pratinjau; periode diperiksa; ajukan memetakan 409 |
| `backend/routers/hr_attendance.py` | `patch_attendance` menghitung ulang menit |
| `backend/routers/hr.py` | `_PAY_PII` kolom baru |
| `backend/indexes.py` + uji PK-14 | `hr_payroll_runs.uq_active_key` (`PYT1_INDEKS = 3`; lapis A 26) |
| `scripts/migrasi_pyt1_proses_gaji.py` (baru) + `scripts/INDEX.md` | proses lama: baca-saja (bawaan) / `--apply` |
| Layar | `features/hr/PayrollRunsView.jsx` (jenis proses, `SlipRow` berkomponen, panel Cari slip, teks, tanda perlu dihitung ulang), `features/hr/PayslipsView.jsx` (mode tertanam, `SlipDetail` berkomponen, token warna), `features/hr/payrollUtils.js` (`RUN_TYPE_*`, `slipGroups`, `slipDeductions`), `config/hubTabs.js` (tab Slip Gaji dihapus), `config/viewAliases.js` (alias `hr-payslips`), `AppViewRouter.jsx` (rute cadangan), `appViewImports.js` |
| Uji | tanda xfail (a) dicabut; + uji migrasi; jest `features/__tests__/pyt1ProsesGaji.test.js` (7); `mnt1MenuKeuangan.test.js` (tab Slip Gaji hilang) |
| Dokumen | `ENTITY_REGISTRY.md` (field proses & slip, jurnal dari komponen), `memory/PRD.md`, `docs/KN_13_NAVIGATION_MAP.md`, `CODEBASE_MAP.md` |

## Uji penerimaan

Berkas: `backend/tests_mem/test_PYT1_komponen_gaji.py`. "Kode lama" = berkas yang sama di salinan bersih `35a1f9a`
(`bukti/PY-T1/merah_kode_lama.txt`, 17/17 merah). Fixture: karyawan disisipkan, BPJS PT dimatikan lewat
`config_resolver.set_value` lapisan PT, "hari ini" 15 Des 2026; komponen, masukan, proses, alur, rekap pajak, absen lewat
HTTP.

| ID | Lapis | Kode lama | (a) | (b) |
|---|---|---|---|---|
| U1 | B | merah: `ImportError hr_pay_components` | lulus (komponen di samping kolom lama) | lulus — E1: Gaji Pokok 8.000.000, "Tunjangan — Transport" 500.000, "Tunjangan — Makan" 300.000, PPh 21 154.000; `base_salary` 8.000.000, `allowances` 800.000, `gross` 8.800.000, `net` 8.646.000; E2 PPh 21 0, `net` 5.000.000; Σ komponen = kolom lama |
| U2 | A | — | ditulis | ditulis (`tests/test_bp_PYT1_data_acuan.py`) — belum teruji |
| U3 | B | merah: 404 endpoint komponen | xfail | lulus — dua baris "Bonus A"/"Bonus B"; `other_earnings` 5.000.000, `gross` 13.800.000, `pph21` 621.000, `net` 13.179.000; dua masukan `used` ber-`used_run_id` |
| U4 | B | merah: THR tanpa masukan → 200 (proses reguler dikembalikan) | xfail | lulus — proses baru, `seq` 1; THR 8.000.000; `pph21_month` 840.000; `pph21` 686.000; `net` 7.314.000 |
| U5 | B | merah (berantai U4) | xfail | lulus — jurnal ber-`source_id` = id THR: Dr 6-1000 8.000.000 / Cr 2-1600 7.314.000 / Cr 2-1800 686.000; jurnal reguler tetap satu |
| U6 | B | merah (berantai U3) | xfail | lulus — dua masukan kembali `approved`, `used_run_id` kosong; `active_key` dilepas |
| U7 | B | merah: 404 | xfail | lulus — hitung ulang pertama: baris baru, total +1.000.000; masukan dibatalkan (proses draf) → ajukan 409 "…hitung ulang…"; hitung ulang kedua: baris hilang, total kembali |
| U8 | B | merah: 404 | xfail | lulus — `pending` tidak ikut; sesudah disahkan + hitung ulang ikut; sesudah **diajukan**, batal → 409 "Masukan ini sudah dipakai di penggajian {nomor}, jadi tidak bisa dibatalkan." (lihat "Usulan koreksi") |
| U9 | B | merah: `ImportError hr_pay_inputs` | lulus | lulus — satu dokumen, nominal 250.000 (kiriman kedua 999.000 diabaikan) |
| U10 | B | merah: 404 | xfail | lulus — E2 `other_deductions` 500.000, `net` 4.500.000; jurnal Cr 1-1400 500.000, Σ debit = Σ kredit 13.800.000; potongan tanpa akun → 400 (U10b) |
| U10b (tambahan) | B | merah: 404 | lulus | lulus — 14 komponen bawaan; 400 potongan tanpa akun; 409 kode kembar; 400 bawaan ganti jenis; ubah nama 200 |
| U11 | B | merah: pesan lain ("…(diberi '2026-13')") | xfail | lulus — "2026-13" & "Okt" → 400 "Periode harus berbentuk TTTT-BB, mis. 2026-10." |
| U12 | B | merah (berantai U1) | xfail | lulus — ("PENERIMAAN", "Tunjangan — Transport", 500000) ada; tidak ada label "(1%)"; PDF terbentuk |
| U13 | B | merah: dpp 0 (THR tidak ada) | xfail | lulus — `dpp` 21.800.000, `amount` 840.000, `gl_amount` 840.000, `count` 2 |
| U14 | B | merah (berantai U1) | xfail | lulus — id sama, `run_type` regular, `seq` 1, `active_key` "ent_kanda:2026-10:regular", satu reguler |
| U14 | A | — | ditulis | ditulis (dua `create_run` bersamaan × 3 putaran) — belum teruji |
| U15 | B | merah: (660, 120, 0) | xfail | lulus — (600, 60, 0) |
| U16 | B | merah: 404 | lulus | lulus — Tanpa Acuan `payroll.create`: buat 200 (`pending`), sahkan 403; alasan kosong 400; komponen bukan masukan 400 |
| migrasi (tambahan) | B | merah: berkas tidak ada | — | lulus — mode lapor tanpa tulisan + daftar KEMBAR (H6); `--apply` mengisi jenis/urutan/kunci, kembar tidak diberi kunci, aman diulang |
| U17 | layar | — | jest (tab baru) | jest `pyt1ProsesGaji.test.js`: tab "Proses Gaji" ada, "Slip Gaji" tidak; dua baris bonus terpisah saat baris E1 dibuka — **belum diuji jalan** di peramban |

### Contoh angka (U1, U4, U5, U13) — slip → jurnal → saldo

PT `ent_kanda`, BPJS mati. Oktober 2026, proses **reguler** (U1): E1 bruto 8.000.000 + 500.000 + 300.000 = 8.800.000 →
tarif A 1,75 % → PPh 21 154.000 → bersih 8.646.000; E2 bruto 5.000.000 → 0 % → bersih 5.000.000.
Proses **THR** (U4), dibuat sesudahnya: E1 THR 8.000.000; bruto pajak bulan = 8.000.000 + 8.800.000 = 16.800.000 → 5 % →
PPh 21 bulan 840.000; dipotong di slip THR = 840.000 − 154.000 = 686.000; bersih 8.000.000 − 686.000 = 7.314.000.

| Jurnal | Akun | Debit | Kredit |
|---|---|---:|---:|
| Reguler (`source_id` = id reguler) | 6-1000 Beban gaji | 13.800.000 | |
| | 2-1600 Hutang gaji | | 13.646.000 (8.646.000 + 5.000.000) |
| | 2-1800 Hutang PPh 21 | | 154.000 |
| THR (`source_id` = id THR) | 6-1000 Beban gaji | 8.000.000 | |
| | 2-1600 Hutang gaji | | 7.314.000 |
| | 2-1800 Hutang PPh 21 | | 686.000 |

Saldo Oktober (kredit): 2-1600 = 13.646.000 + 7.314.000 = **20.960.000**; 2-1800 = 154.000 + 686.000 = **840.000** =
rekap PPh 21 Oktober (U13: dpp 8.800.000 + 5.000.000 + 8.000.000 = 21.800.000; amount 840.000; buku besar 840.000; selisih
0). U10 (PT uji lain, November): potongan E2 500.000 → Cr 1-1400 500.000; Dr 6-1000 13.800.000 = Cr 2-1600 13.146.000 +
Cr 2-1800 154.000 + Cr 1-1400 500.000.

## Cek layar

Dari kode (pelaksana); potret 1280/1024/390 px oleh integrator. Tidak ada hex, `text-[<12px]`, `!py-*` pada tombol, atau
tombol bergaya sendiri yang baru (`verify_ui_standard` total sama dengan B: 13; `PayslipsView.jsx` turun — warna mati &
`text-[11px]` diganti token).

| Layar | (1) tabel ⊂ kartu | (2) bantalan | (3) kepala kartu | (4) tombol mati | (5) status ikon+teks+warna | (6) cari/saring | (7) teks vs izin | (8) kosong/0 |
|---|---|---|---|---|---|---|---|---|
| SDM › Penggajian › **Komponen & Masukan** (`PayComponentsView`, baru) — bagian Komponen gaji | 10 isian spesifikasi dalam 7 kolom + Aksi `col-sticky-end` (hanya pemegang `hr.manage_payroll`): "Jenis · cara hitung" satu sel dua baris, tiga tanda belum-dipakai satu kolom; hitungan lebar isi-minimum ±710 px ≤ ±750 px ruang kartu di 1024 px (sidebar 220 px); `data-table head-wrap` di `overflow-x-auto` sebagai cadangan HP | `section-head` + `section-body`; petunjuk/memuat/galat `section-pad` | judul + satu tombol Muat ulang; "Tambah komponen" di badan | "Tambah komponen" mati dengan alasan tertulis di sampingnya ("Pilih satu PT dulu" / "…butuh izin mengatur penggajian.") | Aktif/Nonaktif = `status-pill` + ikon + teks; tanda Ya/Tidak berikon | ±14–30 baris per PT (tanpa kotak cari; terurut) | izin `hr.manage_payroll` (bukan nama peran) | Semua PT: satu kartu petunjuk; tanda "belum dipakai" ditulis di bawah tabel (L5) |
| — bagian Masukan | 8 kolom + Aksi `col-sticky-end` (Sahkan/Batalkan, `btn-sm` `whitespace-nowrap`) | sama | judul + Muat ulang; saringan & tombol di badan | "Tambah masukan" mati beralasan ("Pilih satu PT dulu" / izin / "Belum ada komponen masukan yang aktif.") | `InputStatus` ikon + teks + `status-pill` (Menunggu disahkan · Disahkan · Terpakai · Dibatalkan) | saringan Periode bayar + `FilterChips` status; berhalaman 20 (`KNPager`) + "{n} masukan" | tanpa `payroll.approve`: kolom aksi tidak tampil + kalimat "Mengesahkan atau membatalkan masukan butuh izin mengesahkan gaji." | kosong "Belum ada masukan untuk periode ini." (satu kali) |
| Pop-up Tambah/Ubah komponen, Tambah masukan | — | `FormModal` baku (grid 2 kolom, 1 kolom di HP) | — | galat isian ditampilkan di modal | — | — | — | Sahkan: `askConfirm` menyebut nominal, karyawan, periode, PT; Batalkan: `askReason`; kirim ber-`Idempotency-Key` (`02` N4, N5) |
| SDM › Penggajian › **Proses Gaji** (`PayrollRunsView`) | tabel slip kini 5 kolom (Karyawan · Pendapatan · Potongan · PPh 21 · Gaji bersih), tanpa kolom aksi (aksi di bilah); rincian komponen di baris terbuka (grid 3 kolom → 1 kolom di HP) | tetap `section-head`/`section-body` | judul proses + jenis + lencana; tombol di bilah sendiri | "Ajukan" mati bila masukan dibatalkan sesudah dihitung + kalimat di samping | status tetap ikon+teks; jenis proses = teks ("THR", "Susulan ke-2") | daftar proses ±12–36/tahun/PT; panel "Cari slip" (nama/periode) | izin `payroll.*` | teks sahkan/kembalikan spesifikasi |
| Panel **Cari slip** (`PayslipsView` tertanam) | 6 kolom `data-table head-wrap` di `overflow-x-auto`; rincian komponen di kartu samping (340 px; 1 kolom di bawah `lg`) | kartu baku | — | — | — | kotak cari (nama/periode/nomor) + saringan periode + halaman 25 | — | "Belum ada slip gaji…" vs "Tidak ada slip yang cocok…" dibedakan |

Belum diuji jalan di peramban (U17) — integrator.

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di `b62ef45` — satu gate untuk
PM-T3 (a/b), PK-41 (a/b), PY-T1 (a/b), PK-33 dan cek layar `b62ef45`:

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, **`guard:atomic_claim`** — PK-33) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

"Tidak dijalankan" tambahan: `guard:atomic_claim SELF-TEST (… 10 kasus)` — ganti label menjadi 64 kasus oleh PK-33 (uji-dirinya
hijau). Kuitansi: `bukti/PY-T1/gate_quick_receipt.md`, `gate_ci_receipt.md`.

### Integrator: penggabungan dan lingkungan A

- Dipasang integrator di atas `976aaca` dalam satu rantai (worktree bantu, lalu dipetik ke cabang): PM-T3 (a) `569c86a`
  · (b) `a2c1e19`, PK-41 (a) `bb0dfcd` · (b) `6093baa`, PY-T1 (a) `e980399` · (b) `64143aa`, PK-33 `6943fb7`, cek layar
  `b62ef45`. Bentrok yang diselesaikan integrator: KN_32 (§9.16 = PK-41, §9.17 = PY-T1), `CODEBASE_MAP.md` (dibangkitkan
  ulang); berkas lain tergabung tiga arah tanpa bentrok. Rantai PM-T3+PK-41+PY-T1: tests_mem **1905 lulus / 2 / 2**, jest
  **957** (35 suite gagal dimuat `cmdk`/`@radix-ui`, sama); penjaga statik = garis dasar kecuali `verify_to_list_bound`
  6 → 5 (PK-41); `verify_atomic_claim` sesudah PK-33 **160/0** (inventaris tetap 123 baris — tidak ada endpoint
  multi-koleksi baru dari PM-T3/PK-41/PY-T1), uji-diri 64 kasus hijau.
- Lingkungan A sesudah `restore_demo` dengan kode baru: **29 dari 29** indeks wajib beres; lapis A
  `test_bp_PK14_indeks_wajib.py` 9 lulus.
- Lapis A `tests/test_bp_PYT1_data_acuan.py`: mula-mula U14 "RuntimeError: Event loop is closed" (dua `asyncio.run`
  terpisah, klien Motor terikat ke loop pertama) — diperbaiki integrator (satu loop per modul, `b62ef45`) → **U2 dan U14
  lulus** (slip data acuan = komponen, selisih 0; dua proses reguler bersamaan → satu proses).
- `scripts/migrasi_pyt1_proses_gaji.py` baca-saja di data acuan: 5 proses · 0 tanpa jenis · 0 PT+periode kembar · 0 slip
  tanpa komponen (`bukti/PY-T1/pyt1_migrasi_baca_saja.txt`).
- Cek layar 1024 px: Proses Gaji (PT · Periode · Jenis proses · "Hitung gaji November 2026", kartu "Cari slip", daftar
  berstatus ikon + teks) dan Komponen & Masukan (tabel 7 kolom + Aksi muat di kartu, `overflowX = 0`) rapi
  (`bukti/PY-T1/cek_*.png`).

Pelaksana (catatan asli):

Gate penuh (`scripts/gate.sh`) dan lapis A belum dijalankan (lingkungan A milik integrator). Yang dijalankan pelaksana
di lingkungan B (W, basis `35a1f9a`):

- `tests_mem`: B **1745 / 2 / 3** (`bukti/PY-T1/tests_mem_B.txt`, salinan bersih) → (a) **1749 / 2 / 15** (+4 uji PY-T1
  lulus, +12 xfail menunggu (b); `tests_mem_a.txt`) → (b) **1762 / 2 / 3** (+17: 16 uji penerimaan/tambahan + uji migrasi;
  `tests_mem_b.txt`). 0 gagal di ketiganya.
- Jest penuh: B **898** → (a) **906** (+8 `pyt1KomponenMasukan.test.js`) → (b) **913** (+7 `pyt1ProsesGaji.test.js`);
  35 suite gagal dimuat di ketiganya (`cmdk`/`@radix-ui`, kendala lingkungan) (`jest_*.txt`).
- `hitung_penjaga.sh`: **identik** B, (a), (b) (`penjaga_{B,a,b}.txt`: auth 27 · ui_standard 13 · i18n 103 ·
  create_modal 6 · page_tabs 1 · to_list 6 · entity_label 2; lainnya 0/PASS). `verify_role_gate_ui` 31/0;
  `verify_permission_checked` 603/0; `verify_posting_coverage` 138/0 (garis dasar tidak berubah — `post_payroll_run`
  sudah terdaftar PK-22); `verify_cash_single_door` 718/0; `verify_config_fallback` (+`--entity`) 155/0;
  `verify_config_text` 3227/0; `verify_payment_vocab` 1797/0; `verify_view_aliases` 168/0 (+6 cek alias `hr-payslips`);
  `verify_ui_contrast` 58/0; `verify_access_catalog_nav` 0; `verify_codebase_map` hijau; `audit_config_wiring --strict`
  hijau; `check_nav_map` PASS; `tests/test_fe03_access_catalog.py` 6/6.

## Uji lama yang disesuaikan (perilaku yang sengaja diubah)

| Uji | Sebab | Penyesuaian |
|---|---|---|
| `tests_mem/test_PK14_indeks_wajib.py` U12 | +3 indeks wajib PY-T1 | `PYT1_INDEKS = 3` |
| lapis A `tests/test_bp_PK14_indeks_wajib.py` U02 | idem | 23 → 26 |
| jest `config/__tests__/mnt1MenuKeuangan.test.js` U2 | tab hub Penggajian | ["Proses Gaji", "Setoran Kewajiban", "Komponen & Masukan"] |
| jest `config/__tests__/roleReach.test.js`, `fixtures/view_main_permission.json`, `access_*_fixture.json` | layar baru `hr-pay-components` (admin, manajer) | `PYT1_KOMPONEN`; baris tabel bantu (`hr.view`, `/api/hr/payroll/inputs`); fixture dibangkitkan ulang |
| `tests_mem/test_PK46_pph21.py` U5 | — (tidak diubah) | merah di tengah pengerjaan (pratinjau reguler menghitung proses yang sudah ada sebagai "slip terdahulu bulan itu") → diperbaiki di kode (menyimpang no. 7), uji tetap |

## Penggabungan

- HEAD tujuan: **`976aaca`** (`/home/user/KNHOST`, dibaca saja). HEAD maju dua kali selama penggabungan: `0562d29` →
  `0616042` (PK-25, KM-T1 (a)(b), PK-32 (a)(b), AG-T3, PK-43 — banyak berkas bersama) → T disetel ulang dan keadaan (a)
  maupun akhir digabung tiga arah lagi; lalu `0616042` → `976aaca` (cek layar PK-25/PK-32: empat berkas layar keuangan,
  tidak ada yang beririsan dengan unit ini) → T dipindah ke `976aaca` tanpa perubahan berkas unit; angka uji di bawah
  diambil di `0616042` + PY-T1, `hitung_penjaga` diulang di `976aaca` (identik HEAD). Penggabungan tiga arah (basis = B `35a1f9a`; skrip `scratchpad/pyt1_gabung.py`: sama dengan B → salin; beda →
  `git merge-file -p`; baru → salin).
- **(a) tergabung**: `scratchpad/PY-T1_a_merged/` (`FILES.txt` 29, `BASIS.txt` = `976aaca`; dibangun di `0616042`,
  `976aaca` tidak menyentuh berkas (a)). **Akhir** (a + b): T (`976aaca` + 41 berkas).
- Bentrok yang diselesaikan (kedua perilaku dipertahankan; `scratchpad/pyt1_selesai.py`, `pyt1_kn32.py`):
  - `ENTITY_REGISTRY.md` — bagian PK-25, KM-T1, PK-32 dari HEAD, lalu bagian PY-T1.
  - `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` — §9.12–§9.15 HEAD (PK-43, PK-25, KM-T1, PK-32) dipertahankan; bagian PY-T1 menjadi
    **§9.16**.
  - `backend/tests_mem/test_PK14_indeks_wajib.py` — `KMT1_INDEKS = 3` + `PYT1_INDEKS` ((a) 2, akhir 3); jumlah
    `… + KMT1_INDEKS + PYT1_INDEKS`. Lapis A `tests/test_bp_PK14_indeks_wajib.py`: 26 (HEAD) + 2 = **28** di (a), + 3 =
    **29** di akhir.
  - `frontend/src/config/__tests__/mnt1MenuKeuangan.test.js` — label hub Penggajian PY-T1 + label hub Kinerja & Insentif
    KM-T1 ("Komisi Otomatis"); `roleReach.test.js` — `KMT1_TARGET_ATURAN` + `PYT1_KOMPONEN`.
  - `scripts/verify_contract.py` — koleksi KM-T1 + PY-T1; `memory/PRD.md` — butir PK-32 + butir PY-T1.
  - Digabung otomatis: `access_modules.py`, `entity_scope.py`, `indexes.py`, `gl_service.py`, `hubTabs.js`, `navMeta.js`,
    `AppViewRouter.jsx`, `appViewImports.js`, fixture akses, `KN_13`, `scripts/INDEX.md`.
- Dibangkitkan ulang di T: `CODEBASE_MAP.md`, `configKeyIndex.json` (tanpa perubahan isi), `access_nav_fixture.json`,
  `access_builtin_fixture.json` (`tests/test_fe03_access_catalog.py` 6/6).
- Angka di T (`0616042` + PY-T1):
  - (a) tergabung, uji terarah (PY-T1, PK-22, PK-14, PK-40, PK-46, KF-T1, PR-T9, PK-44, PK-45, KM-T1): **150 lulus / 2
    dilewati / 12 xfail**; jest terarah (config, pyt1, pk22, kmt1) 202/202; `hitung_penjaga` identik HEAD.
  - Akhir: `tests_mem` **1844 lulus / 2 dilewati / 3 xfail, 0 gagal** (`bukti/PY-T1/T_tests_mem.txt`; HEAD murni tidak
    dijalankan — selisih terhadap W (b) 1762 = uji unit lain di HEAD); jest penuh HEAD murni **928** → T **943** (+15: 8 + 7); 35 suite gagal dimuat di
    keduanya. `hitung_penjaga.sh` **identik** HEAD; `verify_role_gate_ui` 31/0; `verify_permission_checked` 606/0 (HEAD
    606/0); `verify_posting_coverage` 133/0 (HEAD 133/0) + uji-diri hijau; `verify_cash_single_door` 727/0 (HEAD 725/0);
    `verify_payment_vocab` 1812/0 (HEAD 1809/0); `verify_config_fallback` 156/0 dan `--entity` 156/0;
    `verify_config_text` 3255/0; `verify_view_aliases` 168/0; `verify_ui_contrast` 58/0; `verify_access_catalog_nav` 0;
    `verify_codebase_map` hijau; `audit_config_wiring --strict` hijau dan `check_nav_map.py` PASS (salinan berjalur T).

## Menyimpang dari blueprint

1. **Masukan terpakai di proses DRAF boleh dibatalkan** (U7 harfiah): masukan berstatus `cancelled`, proses ditandai
   `inputs_stale_at` dan **ajukan ditolak 409** "Ada masukan yang dibatalkan sesudah penggajian {nomor} dihitung — hitung
   ulang dulu sebelum diajukan." sampai dihitung ulang (layar: Ajukan mati + alasan). Masukan yang dipakai proses yang
   sudah diajukan/disahkan/diposting → 409 spesifikasi. U7 dan U8 spesifikasi saling bertentangan (keduanya berada di
   proses draf yang sudah dihitung ulang); dipilih yang tidak memaksa membatalkan seluruh proses untuk mengoreksi satu
   bonus. Usulan koreksi U8 di bawah. Pembatalan juga boleh dari `pending` (menolak isian manual).
2. **`taxable` tanggungan BPJS Kesehatan, JKK, JKM perusahaan = ya** (spesifikasi: "semua taxable kecuali potongan dan
   tanggungan"): premi itu sudah masuk bruto pajak slip hari ini (HR-01). Dengan tanda ya, `tax_gross` = Σ komponen kena
   pajak = angka lama persis; tanpa tanda, bruto pajak berubah (melanggar "angka slip sama persis").
3. **Komponen buatan pengguna dibatasi** ke cara hitung `masukan`, jenis pendapatan/potongan, kolom `allowances`/
   `overtime`/`other_earnings` (pendapatan) atau `other_deductions` (potongan): komponen tetap/per jam tanpa sumber nilai
   akan selalu 0 (L5; sumbernya PY-T2/PY-T3); tanggungan non-BPJS butuh akun lawan yang tidak disebut unit (H4); kolom
   komisi diakru per PT per bulan (`post_incentive_accrual`) sehingga hanya mesin komisi yang mengisinya.
4. **Komponen bawaan** juga tidak bisa dinonaktifkan atau diganti cara hitung/kolom/kode undang-undang/jenis proses (pesan
   yang sama "Komponen bawaan tidak bisa diubah jenisnya."); BPJS & PPh 21 tetap diatur sakelar `hr.feature_toggles.*`.
   Nama, urutan, akun (pendapatan), dan tiga tanda belum-dipakai boleh diubah.
5. **Akun komponen** harus aktif, bisa diposting, dan **bukan akun kontrol** buku pembantu (`02` §1 P10).
6. **Batal & anulir melepas masukan sesudah** perpindahan status berhasil (bukan "lebih dulu"): pelepasan sebelum klaim
   bisa meninggalkan proses hidup tanpa masukannya bila klaim kalah. Hitung ulang: lepas lebih dulu lalu ambil lagi;
   gagal → masukan yang tadinya dipakai diambil kembali (`retake_inputs`).
7. **Pratinjau reguler** untuk periode yang sudah punya proses reguler = pratinjau hitung ulang proses itu (masukannya
   ikut; PPh 21 gabungan hanya memuat proses yang dibuat lebih dulu darinya). Tanpa ini pratinjau menghitung slip proses
   itu sendiri sebagai "slip terdahulu bulan itu" (ditemukan `test_PK46` U5).
8. **`pph21_month`** = angka (sesuai U4) + rincian di `pph21_month_detail`. Masa terakhir: jumlah bulan = banyaknya
   periode berbeda (dulu banyaknya slip + 1 — sama bila satu slip per bulan).
9. **Kode BPJS** dipilih pelaksana: `BPJS_KES`, `BPJS_JHT`, `BPJS_JP`, `BPJS_KES_PT`, `BPJS_JHT_PT`, `BPJS_JP_PT`,
   `BPJS_JKK`, `BPJS_JKM`. `GET /components` di mode Semua PT → 400 "Pilih satu PT dulu untuk melihat komponen gaji."
10. **"Kotak Cari slip"** = kartu "Cari slip" di Proses Gaji (tombol Buka pencarian → `PayslipsView` tertanam dengan kotak
    cari). Gerbangnya `canOpen("hr-payslips")` (id lama) supaya `hidden_views` peran kustom tetap dipatuhi. Rute cadangan
    `activeView === "hr-payslips"` merender Proses Gaji dengan panel terbuka.
11. **PDF**: judul "TAKE-HOME PAY (NET)" → "GAJI BERSIH DITERIMA"; judul bagian Indonesia saja.
12. **Uji di PT uji tersendiri**: U7, U8, U10 memakai `pt_uji` (bukan `ent_kanda`) supaya aturan satu reguler per PT per
    periode tidak saling mengganggu; BPJS dimatikan dan karyawan E1/E2 disiapkan dengan cara yang sama.
13. **U15**: shift diambil dari rekaman absen (`shift_id`), lalu shift karyawan / bawaan PT.
14. **Skrip migrasi** memakai `--apply` (pola PK-32), bukan `--terapkan`.
15. **Tabel Komponen gaji 7 kolom (+ Aksi)**, bukan 10: "Jenis" dan "Cara hitung" satu sel dua baris; "Dasar BPJS",
    "Dasar lembur", "Diprorata" satu kolom "Dasar BPJS · lembur · diprorata*" (isi: tanda yang dinyalakan atau "—", dengan
    catatan "belum dipakai" di bawah tabel). Semua isian spesifikasi tetap tampil; tujuannya tabel tidak lebih lebar dari
    kartu di 1024 px (standar UI, kesalahan (1)). Ubah tanda tetap di pop-up komponen.

### Usulan koreksi berkas unit (teks pengganti persis; berkas unit tidak diubah pelaksana)

- U8, kolom Langkah: "Buat proses; sahkan masukan; hitung ulang; batalkan masukan" → "Buat proses; sahkan masukan;
  hitung ulang; **ajukan proses**; batalkan masukan". Alasan: U7 menuntut masukan yang dipakai proses draf bisa dibatalkan
  (baris hilang di hitung ulang kedua); U8 harfiah menuntut 409 pada keadaan yang sama.
- Fungsi `cancel_input`, komentar: "# hanya dari approved; used → 409" → "# dari pending/approved; used oleh proses draf →
  dibatalkan dan proses ditandai perlu dihitung ulang; used oleh proses yang sudah diajukan → 409".
- Data, `hr_pay_components`, kalimat isi awal: "Semua `taxable` kecuali potongan dan tanggungan." → "Semua `taxable`
  kecuali potongan dan tanggungan, selain tanggungan BPJS Kesehatan, JKK, dan JKM perusahaan (sudah masuk bruto pajak
  slip, HR-01)."
- Keadaan sekarang: butir kunci jurnal lama `gl_service.py:3042/3109` → "sudah diganti PK-22 (`payroll_source_id`)"; butir
  label "Payroll Run" → "sudah 'Proses Gaji' (MN-T1)".

## Asumsi

- Dari spesifikasi: permintaan kedua reguler mengembalikan proses yang ada; THR & susulan tanpa BPJS; tunjangan master →
  komponen `TUNJANGAN` berlabel namanya; akun potongan dipilih pengguna dari akun aktif.
- Bawaan (`00` §4.1): komponen masukan baru dimuat proses Reguler + Susulan; masukan dari modul sumber langsung
  `approved` (sumbernya sudah disahkan di modulnya); THR dan susulan tidak dibatasi jumlahnya; urutan "dibuat lebih dulu"
  = `created_at` proses.
- K-40 (kasbon) & KM-T4 (lembar insentif): antrean siap (`source_type` `cash_advance`/`incentive_sheet`), pengisinya
  tidak dibangun; sementara lewat isian manual.

## Keraguan dan titik henti

- **H4** — tarif PPh 21: dipakai tabel bawaan PK-46 (isi belum diverifikasi, K-42); unit ini tidak mengubah isinya. Cara
  menggabung bulan (bruto bulan × tarif bulan − yang sudah dipotong) mengikuti spesifikasi; mohon konsultan pajak
  memastikan perlakuan THR di masa Desember/bulan keluar (dihitung lewat hitung ulang tahunan yang memuat slip terdahulu
  bulan itu).
- **H3** — `scripts/migrasi_pyt1_proses_gaji.py` hanya diuji di database tiruan; tidak dijalankan terhadap database
  `backend/.env`. Data acuan: perlu dijalankan integrator (mode baca-saja) — PT+periode kembar = **H6**.
- U2 & U14 lapis A ditulis, belum dijalankan (lingkungan A milik integrator); keunikan bersamaan di MongoDB asli = "belum
  teruji".
- Tanda `in_bpjs_base`, `in_overtime_base`, `prorate` disimpan dan ditandai "belum dipakai" (PY-T3).
- KM-T1 (sudah di HEAD) membuat `incentive_components` (komponen INSENTIF per PT, `icomp_`) — berbeda dari
  `hr_pay_components` (komponen GAJI, `pcomp_`); tidak ada berkas layanan bersama. Sambungan lembar insentif → antrean
  masukan gaji (`source_type="incentive_sheet"`, `enqueue_input`) dibangun KM-T4.

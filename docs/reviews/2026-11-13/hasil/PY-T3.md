# PY-T3 — Aturan hitung gaji dari pengaturan per PT: prorata, potongan, lembur, kalender libur, saldo awal pajak

- Commit awal: `82ef1bb` (worktree kerja, basis B)        - Commit akhir: (a) `9794ec7`, (b) `649b7dc`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PY-04, PY-07, PY-08, PY-12 (spesifikasi `docs/blueprint/unit/PY-T3.md`); keputusan K-38, K-39, K-42
  (tabel tarif tidak disentuh — H4)
- Risiko tinggi → dua serah-terima (`00` §8):
  **(a)** pengaturan dan pembantu, hasil hitung belum berubah — 10 kunci baru + pilihan `hari_kerja` pada
  `hr.prorata_perubahan_gaji` (bawaan = perilaku hari ini, `hr.overtime.sumber` sementara `absensi`),
  `services/hr_work_calendar.py`, `services/hr_pay_rules.py` (`rules`, `prorate_factor`, `bulatkan`, …), koleksi
  `hr_holidays` + `hr_tax_opening_balances` dan endpointnya, tab **Kalender Libur**, bagian kartu karyawan **Saldo awal
  pajak {tahun}**, penghitung slip membaca semua aturan lewat `rules()` (lembur: sumber, menit minimal, pengali, jenis
  hari dari kalender PT; dasar upah lembur & BPJS dari tanda komponen; pembulatan; saldo awal pajak), simulator lembur
  memakai fungsi mesin, menit lembur absensi menurut `hr.overtime.hitung_absensi`, `overtime-impact`; uji setara
  membuktikan slip sama persis dengan kode lama. **(b)** perilaku yang berubah — bawaan K-39 `pengajuan`, perbaikan tanggal
  masuk, prorata masuk/keluar & perubahan gaji hari kerja, tiga potongan absensi (komponen bawaan `POT_ALPHA`,
  `POT_CUTI_TG`, `POT_TELAT`), cara hitung `per_hari_hadir` dan `persen_dasar`, tanda Diprorata dipakai, rapel mengikuti
  aturan slip, skrip data lama.
- Salinan keadaan (a): `scratchpad/PY-T3_a_state/` (`FILES.txt` 49 berkas, `BASIS.txt` = `82ef1bb`); (a) tergabung ke
  HEAD tujuan: `scratchpad/PY-T3_a_merged/` (`BASIS.txt` = `df23cb2`; lihat "Penggabungan").

## Temuan baru saat cek ulang — lembur & komisi tidak masuk slip sejak PY-T2 (regresi, diperbaiki di (a))

Uji setara (a) dijalankan di basis `82ef1bb` untuk membuat potret pembanding: slip S1 (pengajuan lembur 11 jam) bernilai
lembur **0** — baris LEMBUR tidak ada, padahal `overtime_events` menghitung Rp 971.098,27. Sebab:
`backend/services/hr_pay_components.py:199` (`earning_components`) menambahkan baris LEMBUR dan KOMISI hanya di cabang
`elif run_type == "regular"` (tanpa potongan periode), sedangkan sejak PY-T2 (`5edef21`) proses reguler SELALU membawa
`segments` → cabang itu tidak pernah jalan: **lembur dan komisi mesin tidak terbayar di semua proses reguler sejak PY-T2
digabung** (bruto, PPh 21, bersih ikut lebih kecil). Bukti: potret basis
`bukti/PY-T3/pratinjau_basis_82ef1bb.json` vs potret `5f193df` (PY-T1, sebelum PY-T2)
`bukti/PY-T3/pratinjau_5f193df.json` — selisihnya HANYA baris LEMBUR S1 dan S5 beserta turunannya. Diperbaiki: baris
lembur & komisi dibuat untuk semua proses reguler (komentar di kode). Potret pembanding uji setara diambil dari `5f193df`
(perilaku yang dimaksud). **Untuk integrator/pemilik:** proses gaji reguler yang dibuat/dihitung ulang di antara `5edef21`
dan unit ini (data acuan: proses seed `ent_ksc`) tidak memuat lembur/komisi; proses draf cukup dihitung ulang, proses yang
sudah diposting/dibayar = keputusan pemilik (H3, proses susulan).

## Cek ulang "Keadaan sekarang" (spesifikasi dibaca di `3132cc4`; dicek di `82ef1bb`)

| Butir spesifikasi | Hasil di HEAD awal |
|---|---|
| Gaji selalu penuh — `hr_payroll_service.py:262` (`base_salary`) | Berlaku, bergeser — `:412` (Σ gaji pokok potongan PY-T2; tanpa prorata masuk/keluar) |
| Karyawan dari status aktif tanpa tanggal masuk — `:337` (`_active_employees`) | Berlaku, bergeser — `:515` → `hr_compensation_service.employees_for_run` (PY-T2; `_employee_status_query` tanpa `join_date`) |
| Absensi hanya untuk menit lembur — `:200` (`hr_attendance`) | Berlaku, bergeser — `:249` (`overtime_events`) |
| `late_min` tercatat — `hr_attendance_service.py:95`; cuti `unpaid` — `hr_leave_service.py:28` | Berlaku — `:95`; `:28` |
| Pengali `hr.overtime.multiplier` terdaftar — `config_catalog_ops.py:495` | Berlaku, bergeser — `:623` |
| Pengali hanya bila `mode == "flat"` — `:221` (`mode`) | Berlaku, bergeser — `:270` |
| `holidays` & `work_days_per_week` dari setelan tak terdaftar — `:175`, `:181` | Berlaku, bergeser — `:224`, `:230` (+`:265`) |
| Bawaan hanya dua nilai — `hr_service.py:40` (`overtime`) | Berlaku — `:40` |
| Simulator rumus lain — `config_simulator.py:370` (`_payroll_overtime`) | Berlaku, bergeser — `:385` |
| Lembur absensi = menit kerja − durasi shift — `hr_attendance_service.py:104` | Berlaku — `:104` |
| Rekaman langsung disetujui kecuali di luar lokasi — `:218` (`approved`) | Berlaku — `:218` |
| Dibayar untuk tanggal tanpa pengajuan — `hr_payroll_service.py:204` (`by_date`) | Berlaku, bergeser — `:249`–`:255` |
| Upah sejam & dasar BPJS = gaji pokok — `:217` (`hourly`), `:272` (`bpjs_breakdown`) | Berlaku, bergeser — `:266`, `:430` |
| Hitung ulang pajak hanya slip di sistem — `:288` (`annual_pph21`), `:231` (`_prior_year_slips`) | Berlaku, bergeser — `:458`, `:280` (PY-T2: per PT) |
| Uang dibulatkan dua desimal di banyak tempat — `:297` (`net`) | Berlaku, bergeser — `hr_pay_components.py:281` (`derive_columns`, PY-T1) + `round(…, 2)` di `compute_payslip` |
| Hub Pengaturan › SDM dua tab — `hubTabs.js:274` | **Sebagian** — `:325`, kini TIGA tab (KP-T9 menambah Mesin Absen) |
| Dari unit lain: `prorate`/`in_bpjs_base`/`in_overtime_base`/`account_code` (PY-T1), `separation_date` (PK-45), `aturan_pph21` (PK-46) | Ada; tanda tersimpan, "belum dipakai" |
| — (tidak di spesifikasi) | **Regresi PY-T2**: baris LEMBUR & KOMISI tidak masuk slip reguler — lihat bagian di atas |

## PY-04 — tanpa prorata dan potongan absen

- Berlaku di HEAD: ya (bukti merah `bukti/PY-T3/merah_kode_lama.txt`: kunci `hr.prorata_masuk_keluar`/`hr.potongan_*`
  tidak ada di registry; U4 K2 masuk 5 Des ikut slip November).
- Perubahan perilaku: (b) **perbaikan tanggal masuk** (tanpa sakelar): `_active_employees` membuang karyawan yang
  `join_date`-nya sesudah akhir periode (`hr_pay_rules.masuk_setelah`). **Prorata masuk/keluar** (`hr.prorata_masuk_keluar`
  `mati`·`hari_kalender`·`hari_kerja`, bawaan mati): `hr_pay_rules.atur_potongan` memotong potongan periode menurut masa
  kerja (tanggal masuk / `separation_date` di dalam periode); komponen ber-`prorate` = nilai × n ÷ d (`rasio`), label
  "Gaji Pokok (16–30 Nov)". **Potongan** (masing-masing komponen bawaan, bawaan mati): upah sehari = Σ komponen ber-`prorate`
  sesudah prorata ÷ hari kerja bulan (kalender PT); tidak hadir = hari kerja masa kerja tanpa rekaman absensi (atau berekaman
  `alpha`) dan tanpa cuti disetujui; cuti tanpa gaji = hari kerja tercakup cuti `unpaid` disetujui; terlambat = Σ `late_min`
  × `hr.potongan_telat_per_menit`; label memuat banyaknya. Potongan bertanda kena pajak MENGURANGI bruto pajak
  (`derive_columns`) dan berakun beban gaji (jurnal: kredit 6-1000). `hr.pembulatan_rupiah` (bawaan dua desimal) lewat
  `bulatkan`.

## PY-07 — pengaturan lembur tidak berpengaruh

- Berlaku di HEAD: ya (merah: `hr.overtime.mode`/`.work_days_per_week` tidak terdaftar; `POST /api/hr/holidays` 404;
  simulator 4 jam = rumus pengali tunggal).
- Perubahan perilaku: (a) `hr.overtime.mode` (bertingkat · flat), `hr.overtime.work_days_per_week` (5 · 6) terdaftar —
  nilai lama tersembunyi di `system_settings{scope:"hr"}.overtime.{mode,work_days_per_week}` tetap terbaca (lapisan lama
  resolver, terbukti di uji setara keadaan 2); jenis hari dari kalender kerja PT (`hr_holidays`, tab Kalender Libur, tanpa
  isi awal) — daftar tersembunyi `overtime.holidays` tidak dibaca lagi (skrip data lama melaporkannya); upah sejam =
  Σ komponen ber-`in_overtime_base` ÷ `hr.overtime.hours_divisor`; simulator `payroll_overtime` memanggil
  `overtime_units` mesin (`nilai` = nominal); `hr.overtime.multiplier` diberi keterangan "Dipakai hanya bila cara hitung
  pengali = flat." dan kartunya menulis "Tidak dipakai saat ini…" saat mode bertingkat (L6).

## PY-08 — lembur dari absensi otomatis disetujui

- Berlaku di HEAD: ya (merah: U9 menit absensi tanpa pengajuan dibayar; `hr.overtime.sumber` tidak ada).
- Perubahan perilaku: `hr.overtime.sumber` — `pengajuan` (bawaan sejak (b), **K-39**) = hanya pengajuan `approved`;
  `absensi` = cara lama + menit di bawah `hr.overtime.ambang_menit` diabaikan. `hr.overtime.hitung_absensi` —
  `jam_kerja_lebih` (bawaan) / `lewat_jam_pulang` dibaca `compute_metrics` di absen manual, impor/mesin, clock-out, ubah
  jam. `GET /api/hr/payroll/overtime-impact` (+ tautan "Lihat dampaknya") = bahan memutuskan.
- **Kalimat untuk pemilik:** "Sejak unit ini, lembur dari absensi tanpa pengajuan tidak dibayar kecuali pengaturan
  'Lembur dibayar berdasarkan' diubah ke absensi."

## PY-12 — tanpa saldo awal pajak tahun berjalan

- Berlaku di HEAD: ya (merah: `PUT …/tax-opening` 404).
- Perubahan perilaku: (a) `hr_tax_opening_balances` per (PT, karyawan, tahun); masa pajak terakhir menambahkan masa,
  bruto, iuran pensiun, dan PPh 21 terpotong saldo awal sebelum `annual_pph21` (tarif/PTKP/biaya jabatan tetap PK-46);
  `pph21_annual.opening` mencatatnya. 400 "Jumlah masa harus 1 sampai 11."; 409 "Pajak {tahun} karyawan ini sudah dihitung
  ulang, jadi saldo awalnya tidak bisa diubah." bila slip masa terakhir tahun itu sudah `posted`/`paid`.

## Serah-terima (a) — pengaturan & pembantu, hasil hitung belum berubah

| Berkas | Isi (a) |
|---|---|
| `backend/services/hr_pay_rules.py` (baru) | `KUNCI`, `rules` (satu pembaca, `resolve_keys`), `normalize`, `bulatkan`, `rasio`/`prorate_factor`, `masa_kerja`, `masuk_setelah`, `atur_potongan`, `hitung_kehadiran`/`ringkasan_kehadiran`, saldo awal pajak |
| `backend/services/hr_work_calendar.py` (baru) | `Kalender` (murni), `calendar_for`, `is_holiday`, `work_days`, `list/add/delete_holiday` |
| `backend/routers/hr_pay_rules.py` (baru) + `server.py`, `schemas_hr_payroll.py` | 6 endpoint spesifikasi |
| `backend/services/hr_payroll_service.py` | `overtime_units`, `overtime_events`/`_overtime_amount` dari `rules`+kalender, `compute_payslip` (`rl`, `cal`, `tax_opening`; dasar dari tanda; `bulatkan`; `pay_rules`, `overtime_base`, `bpjs_base`), `_build_slips` (sekali per proses), `overtime_impact` |
| `backend/services/hr_pay_components.py` | baris LEMBUR & KOMISI untuk semua proses reguler (regresi PY-T2), `basis`, potongan kena pajak mengurangi bruto pajak |
| `backend/services/hr_attendance_service.py`, `routers/hr_attendance.py` | `compute_metrics(overtime_rule)`, `overtime_rule_for` |
| `backend/services/config_simulator.py` | simulator lembur memakai `overtime_units` |
| `backend/config_catalog_ops.py`, `config_registry.py` | 10 kunci + sub-judul "Prorata, potongan & pembulatan"; `hr_prorata_perubahan_gaji` + `hari_kerja`; konsumen pengali & pembagi |
| `backend/indexes.py`, `entity_scope.py`, `scripts/verify_contract.py` | `uq_entity_date`, `uq_entity_employee_year` (REQUIRED_UNIQUE_INDEXES), `uq_id`, SCOPED, kontrak |
| `backend/access_modules.py` + fixture akses | `nav` modul `hr` + `hr-holidays` |
| Layar | `features/hr/HolidaysView.jsx`, `features/hr/EmployeeTaxOpeningSection.jsx`, `features/settings/config/SettingKeyExtra.jsx` (baru); `Employee360Panel.jsx`, `SettingCard.jsx`, `SettingsBrowser.jsx`, `PayComponentsView.jsx` (tanda Dasar BPJS/lembur dipakai), `hubTabs.js`, `navMeta.js`, `appViewImports.js`, `AppViewRouter.jsx`, `configKeyIndex.json` |
| Uji | `tests_mem/test_PYT3_aturan_hitung.py` (13 lulus + 10 `xfail(strict)` menunggu (b)), `tests_mem/test_PYT3_setara.py` + `data/pratinjau_sebelum_PYT3.json`, `tests/test_bp_PYT3_data_acuan.py` (ditulis), jest `features/__tests__/pyt3AturanGaji.test.js` (12); disesuaikan: lihat "Uji lama" |
| Penjaga | `scripts/guardrails/config_fallback_allow.json` — dua pengecualian basi dihapus (cadangan `hours_divisor`/`multiplier` di kode lama hilang) |
| Dokumen | `ENTITY_REGISTRY.md`, `docs/KN_13_NAVIGATION_MAP.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.19 (di T: §9.21), `memory/PRD.md`, `CODEBASE_MAP.md` |

## Serah-terima (b) — perilaku yang berubah

| Berkas | Perubahan (b) |
|---|---|
| `backend/config_catalog_ops.py` | `hr.overtime.sumber` bawaan `pengajuan` (K-39) |
| `backend/services/hr_pay_components.py` | `POT_ALPHA`/`POT_CUTI_TG`/`POT_TELAT` (isi awal, akun `ACC_BEBAN_GAJI`), `GAJI_POKOK`/`TUNJANGAN` `prorate: true`, `CALCS` + `absensi`/`per_hari_hadir`/`persen_dasar`, `nilai_tetap`, `segment_lines` (prorata masuk/keluar & hari kerja), `rate_components`, `attendance_deductions`, `create/update_component` (`rate`) |
| `backend/services/hr_payroll_service.py` | perbaikan tanggal masuk (`_active_employees`), `atur_potongan`, ringkasan kehadiran, potongan & komponen ber-rate, `attendance_summary` |
| `backend/services/hr_compensation_service.py` | `hr.prorata_perubahan_gaji` = `hari_kerja` (`PRORATA_MODES`, `build_segments`), `segment_total(comps)`, `rapel_lines` memakai aturan slip |
| `backend/schemas_hr_payroll.py` | `rate` |
| `scripts/migrasi_pyt3_aturan_gaji.py` (baru) + `scripts/INDEX.md` | data lama: baca-saja (bawaan) / `--apply` (tanda Diprorata) |
| Layar | `PayComponentsView.jsx` (cara hitung & nilai komponen baru, keterangan "belum dipakai" dicabut) |
| Uji | tanda xfail dicabut; setara (b) dua uji; tambahan: komponen bawaan, per hari hadir/persen gaji pokok, perubahan gaji hari kerja, skrip; jest +1 |
| Dokumen | `ENTITY_REGISTRY.md` (komponen & field b), `CODEBASE_MAP.md`, docstring modul |

## Uji penerimaan

Berkas: `backend/tests_mem/test_PYT3_aturan_hitung.py` + `test_PYT3_setara.py`. "Kode lama" = basis `82ef1bb`
(`bukti/PY-T3/merah_kode_lama.txt`, **23/23 merah**). Fixture: "hari ini" 15 Des 2026; BPJS mati (lapisan PT) kecuali
`PYT3B`; karyawan, absensi, cuti, pengajuan lembur, slip Jul–Nov disisipkan; proses, pratinjau, hari libur, saldo awal,
komponen, pengaturan, absen manual lewat HTTP. Tarif PPh 21 dari fungsi (`ter_rate`, `annual_pph21`).

| ID | Lapis | Kode lama | (a) | (b) |
|---|---|---|---|---|
| U1 | B | merah: kunci tidak ada | lulus — Gaji Pokok 6.000.000 | lulus |
| U2 | B | merah: kunci tidak ada | xfail | lulus — "Gaji Pokok (16–30 Nov)" 3.000.000; K8 (PT lain) 6.000.000 |
| U3 | B | merah | xfail (dua bagian) | lulus — 3.142.857,14; sesudah libur 25 Nov 3.000.000 |
| U4 | B | merah | xfail | lulus — K2 tanpa slip untuk mati/hari_kalender/hari_kerja (proses & pratinjau) |
| U5 | B | merah | xfail | lulus — bawaan 6.000.000; hari kalender "Gaji Pokok (1–15 Nov)" 3.000.000 |
| U6 | B | merah | xfail | lulus — "Potongan tidak hadir (2 hari)" 600.000; bruto pajak 5.700.000; PPh 21 = 5.700.000 × tarif (28.500); bersih 5.671.500; jurnal Dr 6-1000 6.300.000 / Cr 6-1000 600.000, Cr 2-1800 28.500, Cr 2-1600 5.671.500; bawaan: PPh 21 47.250, bersih 6.252.750 |
| U7 | B | merah | xfail | lulus — "Potongan cuti tanpa gaji (1 hari)" 300.000; tidak hadir 0 |
| U8 | B | merah | xfail | lulus — "Potongan terlambat (45 menit)" 45.000 |
| U9 | B | merah | U9a lulus (absensi 210.000; ambang 150 → 105.000), U9b xfail | lulus — bawaan 105.000 (hanya pengajuan) |
| U10 | B | merah | lulus — flat 90.000; simulator `nilai` 225.000 = `overtime_hour_units(4)` 7,5 | lulus |
| U11 | B | merah: 404 | lulus — 120.000, jenis hari `holiday` | lulus |
| U12 | B | merah | lulus — Sabtu 120.000 lalu 105.000; hari kerja 21 lalu 25 | lulus |
| U13 | B | merah: 50.000 ≠ 60.000 | lulus — 60.000 dengan tanda; 50.000 tanpa | lulus |
| U14 | B | merah: 404 | lulus — bruto 96.000.000, 12 masa, biaya jabatan/neto/PKP = fungsi, terpotong 1.320.000, PPh 21 Des = pajak setahun − 1.320.000 (540.000); tanpa saldo awal −600.000; tambahan: 400 masa 0/12, `null`, 409 sesudah posting | lulus |
| U15 | B | merah | lulus — 90 lalu 30 (absen manual) | lulus |
| U16 | B | merah | xfail | lulus — 3.142.857; semua baris bulat |
| U17 | B | merah | lulus — 11 kunci: atribut + putaran `t1_config`; "hari"/−5 → 400 | lulus |
| U18 | B | merah: 404 | lulus — Manajer Kosong 403 (POST libur, PUT saldo, DELETE); Tanpa Acuan `hr.manage_attendance` 200; kembar 409; "Semua PT" 409 | lulus |
| U18 | A | — | ditulis (`tests/test_bp_PYT3_data_acuan.py`: dua `add_holiday` bersamaan × 3) — belum teruji | sama |
| setara | B | merah: S1 tanpa LEMBUR (regresi PY-T2) | lulus — dua keadaan = potret `5f193df` persis | lulus — (1) sumber absensi = potret kecuali S3; (2) bawaan: kejadian absensi S1/S5 tidak dibayar, sisanya sama |
| dampak (tambahan) | B | merah: 404 | lulus — K5 120 menit, 1 hari, 105.000 | lulus |
| tambahan (b) | B | — | — | lulus — komponen bawaan POT_*; per hari hadir 21 × 25.000 = 525.000 & 1 % × 6.300.000 = 63.000 (galat rate 400); perubahan gaji hari kerja 2.857.143 + 3.928.571; skrip baca-saja/--apply dua kali |
| L1, L3 | A | — | L1 ditulis | ditulis — dampak K-39 tiga periode per PT; skrip baca-saja di data acuan — belum teruji |
| layar | jest | — | `pyt3AturanGaji.test.js` 12 | 13 — **belum diuji jalan** |

### Contoh angka (U6) — slip → jurnal → saldo

PT `PYT3P`, BPJS mati, November 2026 (21 hari kerja). K4 gaji 6.300.000, absensi 19 hari (12 & 13 Nov kosong),
`hr.potongan_alpha` ya. Upah sehari = 6.300.000 ÷ 21 = 300.000 → potongan 2 × 300.000 = 600.000. Bruto pajak =
6.300.000 − 600.000 = 5.700.000 → tarif kategori A (tabel bawaan) 0,5 % → PPh 21 28.500. Bersih = 6.300.000 − 600.000 −
28.500 = 5.671.500.

| Akun | Debit | Kredit |
|---|---:|---:|
| 6-1000 Beban gaji (gaji pokok) | 6.300.000 | |
| 6-1000 Beban gaji (potongan tidak hadir) | | 600.000 |
| 2-1800 Hutang PPh 21 | | 28.500 |
| 2-1600 Hutang gaji | | 5.671.500 |

Saldo: 6-1000 = 5.700.000 (beban bersih = bruto pajak); 2-1600 = 5.671.500 = bersih slip; Σ debit = Σ kredit 6.300.000.

## Uji lama yang disesuaikan (perilaku yang sengaja diubah)

| Uji | Sebab | Penyesuaian |
|---|---|---|
| `tests_mem/test_KFT1_izin_pengaturan.py` U04 | +10 kunci berizin `hr.manage_payroll` | `PYT3_KUNCI = 10` (U02 tetap) |
| `tests_mem/test_PK14_indeks_wajib.py` U12; lapis A `tests/test_bp_PK14_indeks_wajib.py` U02 | +2 indeks wajib | `PYT3_INDEKS = 2`; 31 → 33 |
| `tests_mem/test_PYT2_riwayat_kompensasi.py` U13 | pilihan `hari_kerja` ditambah (spesifikasi) | daftar pilihan 3 |
| jest `config/__tests__/kpt9HubPengaturan.test.js`, `navAccess.test.js`, `roleReach.test.js`, `fixtures/view_main_permission.json`, `access_*_fixture.json` | tab baru Kalender Libur (`hr-holidays`, admin & manajer) | hub SDM 4 tab, 36 tab; potret jangkauan + `hr-holidays`; `PYT3_LIBUR`; fixture dibangkitkan ulang |
| jest `features/__tests__/pyt1KomponenMasukan.test.js` | keterangan "belum dipakai" dicabut (spesifikasi) | menguji keterangan baru |

## Cek layar

Dari kode (pelaksana); potret 1280/1024/390 px oleh integrator. Token `kn-*` saja di kode baru (tanpa hex, tanpa
`text-[<12px]`, tanpa `!py-*`); tombol `primary-button`/`secondary-button` + `btn-sm` `whitespace-nowrap`; status jenis
libur `status-pill` + ikon + teks dengan kelas yang ada (`status-shipped`, `status-pending`, `status-draft`);
`verify_ui_standard` sama dengan B (13).

| Layar | (1) tabel ⊂ kartu | (2) bantalan | (3) kepala kartu | (4) tombol mati | (5) status ikon+teks+warna | (6) cari/saring | (7) teks vs izin | (8) kosong/0 |
|---|---|---|---|---|---|---|---|---|
| Pengaturan › SDM › **Kalender Libur** (`HolidaysView`, baru) | 3 kolom (Tanggal · Nama · Jenis) + PT saat "Semua PT" + Aksi `col-sticky-end` (hanya pemegang `hr.manage_attendance` di satu PT); `data-table head-wrap` dalam `overflow-x-auto` (±450 px) | `section-head` + `section-body`; memuat/galat/kosong `section-pad` | judul + satu tombol Muat ulang; pemilih tahun & "Tambah hari libur" di badan | "Tambah hari libur" mati + alasan tertulis ("Pilih satu PT dulu untuk menambah hari libur." / "…butuh izin mengatur absensi.") | Jenis = `status-pill` + ikon (bendera / orang / gedung) + teks | ≤ ±25 baris per PT per tahun, urut tanggal, saringan tahun; "{n} hari libur pada {tahun}." | izin `hr.manage_attendance` (bukan nama peran) | satu kalimat kosong "Belum ada hari libur untuk tahun ini." + keterangan "Isi dari keputusan resmi…" |
| Pop-up **Tambah hari libur** | — | `FormModal` baku (2 kolom → 1 di HP) | — | galat isian di modal | — | — | — | Hapus: `askConfirm` menyebut tanggal, nama, PT |
| Kartu karyawan › **Saldo awal pajak {tahun}** (`EmployeeTaxOpeningSection`, baru; hanya pemegang `hr.view_pii`) | form 5 isian (grid 2 → 1 kolom di HP), tanpa tabel | `section-head` + `section-body` | judul + Muat ulang; pemilih tahun pajak di badan | Simpan & isian mati + alasan tertulis ("Pilih satu PT dulu…" / "…butuh izin mengatur penggajian.") | — | — | izin `hr.manage_payroll` | keterangan spesifikasi; `askConfirm` menyebut nama, PT, masa, bruto, PPh 21; 409 terkunci ditampilkan di bawah isian |
| Pusat Pengaturan › SDM & Penggajian — kartu "Pengali upah lembur" / "Lembur dibayar berdasarkan" (`SettingKeyExtra`) | pop-up dampak: 4 kolom (Karyawan · Hari · Menit · Nilai), `DetailModal md framed` | kartu bawaan | — | tanpa PT terpilih / tanpa izin: kalimat, bukan tombol | — | daftar per karyawan (urut nilai) + baris jumlah | izin `hr.manage_payroll` | "Tidak ada lembur dari absensi tanpa pengajuan pada periode ini." |
| SDM › Penggajian › **Komponen & Masukan** (`PayComponentsView`, (b)) | tetap 7 kolom + Aksi; nilai komponen ber-rate sebagai baris ketiga sel "Jenis · cara hitung" (tanpa kolom baru) | tetap | tetap | tetap | tetap | tetap | — | keterangan "belum dipakai" dicabut; pop-up: "Cara hitung" + "Nilai per hari hadir (Rp)" / "Persen dari gaji pokok (%)" |
| Proses Gaji / Cari slip | tanpa perubahan layar: baris slip baru (potongan, prorata "(16–30 Nov)", uang makan) tampil lewat daftar komponen yang sudah ada | — | — | — | — | — | — | — |

Belum diuji jalan di peramban — integrator.

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`649b7dc`** — satu gate
untuk KM-T2 (`4b219c4`) dan PY-T3 ((a) `9794ec7` · (b) `649b7dc`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`38c715f`: 12 / 39) — tidak ada gate baru yang merah. Kuitansi: `bukti/PY-T3/gate_quick_receipt.md`,
`gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- Pelaksana menggabung ke `df23cb2`; integrator memasang (a) dari keadaan (a) tergabung dan (b) dari T di atas KM-T2:
  bentrok `indexes.py` (koleksi CR-T2 + PY-T3), dua uji PK-14 (lapis B `+ PYT3_INDEKS`, lapis A **36**),
  `test_KFT1_izin_pengaturan.py` (`PMT4_KUNCI + PYT3_KUNCI`), `roleReach.test.js` (`PMT4_TITIPAN` + `PYT3_LIBUR`), KN_32
  (PY-T3 → **§9.24**) — kedua perilaku dipertahankan; fixture akses dan `configKeyIndex.json` dibangkitkan ulang. Commit di
  worktree bantu (a) `2a6eb6c` · (b) `6e79137`, dipetik ke cabang → (a) **`9794ec7`** · (b) **`649b7dc`**. `tests_mem`:
  (a) **2086 lulus / 2 dilewati / 12 xfail** (10 xfail ketat menunggu (b), bersama KM-T2), (b) **2101/2/2** (bersama KM-T2), 0 gagal.
- **Regresi PY-T2 diperiksa ulang integrator di `38c715f`**: `earning_components` hanya membuat baris LEMBUR/KOMISI di
  cabang tanpa `segments`; sejak PY-T2 cabang itu tak pernah jalan untuk proses reguler. Diperbaiki (a); dicatat juga di
  `hasil/PY-T2.md` dan "Menunggu pemilik" (H3: proses gaji yang dihitung dengan kode PY-T2).
- Lingkungan A (data acuan sesudah `restore_demo`, kode `649b7dc`; `bukti/PY-T3/integrator_lapis_A.txt`): lapis A
  **U18 lulus** (dua tambah hari libur bersamaan → satu tersimpan), **L1** dampak K-39 tiga periode: `ent_ksc` November 2026
  **4 karyawan · 148 menit lembur absensi tanpa pengajuan · Rp 200.505,80** (Oktober/September 0; PT lain 0) — nilai yang
  tidak lagi dibayar dengan bawaan "pengajuan"; **L3** skrip `migrasi_pyt3_aturan_gaji.py` baca-saja: 0 komponen akan
  ditandai Diprorata, 0 komponen potongan belum ada, 0 tanggal libur lama tersembunyi, 0 komponen buatan bertanda dasar, 0
  slip draf karyawan masuk kemudian. PK-14 lapis A **9 lulus (36 indeks)**; PY-T2 U1/U11 dan PY-T1 U2/U14 tetap lulus.
- Uji jalan (integrator): Pengaturan › SDM › **Kalender Libur** (tab keempat; pemilih tahun, Tambah hari libur, keadaan
  kosong satu kalimat "Belum ada hari libur untuk tahun ini." — hari libur sengaja tidak diisi, H4) rapi di 1280/1024
  (`bukti/PY-T3/cek_libur_1024.png`). Kartu Saldo awal pajak dan pop-up dampak lembur dicakup jest (13 uji), tidak dipotret.
- Kalimat untuk pemilik: "Sejak unit ini, lembur dari absensi tanpa pengajuan tidak dibayar kecuali pengaturan 'Lembur
  dibayar berdasarkan' diubah ke absensi." (dampak data acuan di atas).

Pelaksana (catatan asli):

Belum dijalankan (lingkungan A milik integrator; lapis A ditulis, belum teruji). Yang dijalankan pelaksana di
lingkungan B (W, basis `82ef1bb`):

- `tests_mem`: B **1941 lulus / 1 gagal / 2 dilewati / 2 xfail** (`bukti/PY-T3/tests_mem_B.txt`; satu-satunya gagal =
  `test_PK18_U14_penjaga_cakupan_posting` — subproses `verify_posting_coverage` melewati batas 120 dtk karena mesin
  sedang dipakai banyak proses; lulus di (a) dan (b)) → (a) **1965 / 2 / 12 xfail, 0 gagal** (+13 uji PY-T3 + 10 xfail
  menunggu (b) + 10 kasus putaran KF-T8 untuk kunci baru; `tests_mem_a.txt`) → (b) **1980 / 2 / 2, 0 gagal** (+26 uji
  aturan + 2 setara; `tests_mem_b.txt`).
- Jest penuh: B **965** → (a) **977** (+12 `pyt3AturanGaji.test.js`) → (b) **978** (+1); 35 suite gagal dimuat di
  ketiganya (`@radix-ui/primitive/is-development` lewat `cmdk`, kendala lingkungan).
- `hitung_penjaga.sh`: **identik** B, (a), (b) (auth 27 · ui_standard 13 · i18n 103 · create_modal 6 · page_tabs 1 ·
  to_list 5 · entity_label 2; lainnya 0/PASS). `verify_role_gate_ui` 31/0; `verify_permission_checked` 606/0;
  `verify_atomic_claim` 160/0 + uji-diri 64 hijau (inventaris multi-koleksi dibangkitkan ulang: tidak berubah);
  `verify_posting_coverage` 133/0; `verify_cash_single_door` 733/0; `verify_detail_modal` 30/0; `verify_payment_vocab`
  1823/0; `verify_view_aliases` 168/0; `verify_ui_contrast` 58/0; `verify_access_catalog_nav` 0; `verify_config_text`
  3353/0; `verify_config_fallback` (+`--entity`) 158/0 (dua pengecualian basi dihapus); `verify_codebase_map` hijau;
  `gen_config_key_index --check` selaras; `check_nav_map` PASS; `audit_config_wiring --strict` hijau tanpa database —
  dengan database lingkungan A merah 1–2 kunci DEAD milik TX-T2/AG-T5 (nilai di `system_settings{scope:ent_ksc}` yang belum
  terdaftar di W; di T hijau); `tests/test_fe03_access_catalog.py` 6/6.

## Penggabungan

- HEAD tujuan: **`df23cb2`** (`/home/user/KNHOST`, dibaca saja). HEAD maju dua kali selama unit dikerjakan: `82ef1bb` →
  `15d3258` (TX-T2 (a)(b) + cek layar) → `df23cb2` (AG-T5 (a)(b) + cek layar). T (`scratchpad/wt29`) disetel ulang ke
  `df23cb2`; penggabungan tiga arah per berkas (basis = B `82ef1bb`; `bukti/PY-T3/pyt3_gabung.py`: sama dengan B → salin;
  baru → salin; beda → `git merge-file -p HEAD B W`; bentrok → `bukti/PY-T3/pyt3_selesai.py`, kedua perilaku dipertahankan).
- **(a) tergabung**: `scratchpad/PY-T3_a_merged/` (`FILES.txt` 49, `BASIS.txt` = `df23cb2`; berkas bangkitan dibangkitkan di
  T) — uji terarah di T (PY-T3, PY-T1, PY-T2, PK-14, KF-T1, KF-T4, TX-T2, AG-T5): **131 lulus / 10 xfail**
  (`bukti/PY-T3/a_merged_terarah.txt`).
- **Akhir (a + b)**: T = `df23cb2` + 53 berkas (41 diubah + 12 baru). Salin 31 · baru 12 · gabung bersih 7
  (`ENTITY_REGISTRY.md`, `access_modules.py`, `AppViewRouter.jsx`, `access_builtin_fixture.json`, `configKeyIndex.json`,
  `memory/PRD.md`, `scripts/INDEX.md`) · bentrok 3:
  - `backend/tests_mem/test_KFT1_izin_pengaturan.py` — konstanta HEAD `TXT2_KUNCI = 1`, `AGT5_KUNCI = 3`,
    `AGT5_KUNCI_KONTROL = 2` + `PYT3_KUNCI = 10`; jumlah U04 `… + PYT2_KUNCI + TXT2_KUNCI + PYT3_KUNCI + AGT5_KUNCI`, komentar
    menyebut ketiganya.
  - `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` — §9.19 (TX-T2) dan §9.20 (AG-T5) dari HEAD dipertahankan; bagian PY-T3 menjadi
    **§9.21**.
  - `CODEBASE_MAP.md` — dibangkitkan ulang (`gen_codebase_map.py`).
- Dibangkitkan ulang di T: `CODEBASE_MAP.md`, `configKeyIndex.json`, `access_nav_fixture.json`, `access_builtin_fixture.json`
  (`tests/test_fe03_access_catalog.py` 6/6). Hitungan lain: PK-14 lapis B `PYT3_INDEKS = 2` (HEAD tidak menambah indeks
  wajib sesudah B) → lapis A 33.
- Angka di T:
  - `tests_mem` HEAD murni **2000 lulus / 2 / 2** (`bukti/PY-T3/tests_mem_HEAD.txt`) → T **2038 lulus / 2 dilewati / 2 xfail,
    0 gagal** (+38: 26 uji aturan + 2 setara + 10 kasus putaran KF-T8; `bukti/PY-T3/tests_mem_T.txt`).
  - Jest penuh HEAD murni **983** → T **996** (+13 `pyt3AturanGaji.test.js`); 35 suite gagal dimuat di keduanya
    (`@radix-ui`).
  - `hitung_penjaga.sh` **identik** HEAD (`penjaga_HEAD.txt`, `penjaga_T.txt`: auth 26 · ui_standard 13 · i18n 103 ·
    create_modal 6 · page_tabs 1 · to_list 5 · entity_label 2). `verify_role_gate_ui` 31/0 (HEAD 31/0);
    `verify_permission_checked` 609/0 (HEAD 609/0); `verify_atomic_claim` 160/0 (HEAD 160/0) + uji-diri 64 hijau;
    `verify_posting_coverage` 133/0; `verify_cash_single_door` 734/0 (HEAD 731/0); `verify_detail_modal` 30/0;
    `verify_payment_vocab` 1825/0 (HEAD 1819/0); `verify_view_aliases` 168/0; `verify_ui_contrast` 58/0;
    `verify_access_catalog_nav` 0; `verify_config_text` 3381/0 (HEAD 3311/0); `verify_config_fallback` 158/0 dan `--entity`
    158/0 (HEAD sama); `verify_codebase_map` hijau; `audit_config_wiring --strict` hijau (dengan & tanpa database) dan
    `check_nav_map.py` PASS (salinan berjalur T).

## Menyimpang dari blueprint

1. **Potret setara dari `5f193df`, bukan basis `82ef1bb`** — di basis lembur & komisi tidak masuk slip (regresi PY-T2,
   bagian pertama laporan); unit ini memulihkannya di (a). Selisih basis vs potret tercatat di bukti.
2. **PT uji tersendiri** untuk U6 (`PYT3P`: jurnal hanya memuat K4), U7/U8 (`PYT3Q`), U13 (`PYT3B`, BPJS menyala),
   U14 (`PYT3T`); U1–U5, U9–U12, U16 di `ent_kanda` sesuai spesifikasi. U7, U8, U9–U14 lewat pratinjau (hitungan sama dengan
   proses). "Hari ini" 15 Des 2026 (U14 butuh periode Desember yang sudah dimulai).
3. **`rules()` membaca lewat `resolve_keys`** (= `value_of` untuk beberapa kunci, sekali muat); juga membaca
   `hr.overtime.multiplier`, `hr.overtime.hours_divisor` (konsumen dipindah ke `rules` — satu pembaca aturan hitung) dan
   `hr.prorata_perubahan_gaji` (tetap juga dibaca PY-T2 `segments`/`prorata_mode`).
4. **Sub-judul baru "Prorata, potongan & pembulatan"** di kelompok sdm (lima kunci + `hr.prorata_perubahan_gaji` dipindah ke
   sana); "Lembur, komisi & kepegawaian" kini 10 kunci (batas 14).
5. **Dasar upah lembur & dasar BPJS** = Σ komponen bertanda pada nilai BULANAN (sebelum prorata masuk/keluar; potongan
   perubahan gaji PY-T2 tetap seperti hari ini) — upah sejam dan iuran BPJS diukur dari upah sebulan; masukan antrean
   bertanda ikut. Upah sehari potongan = sesudah prorata (spesifikasi).
6. **Cara hitung `absensi`** untuk tiga potongan bawaan (spesifikasi tidak menyebut cara hitungnya); label "Dari absensi &
   pengaturan".
7. **Hari tidak hadir**: rekaman berstatus `alpha` dihitung tidak hadir; rekaman lain (hadir, telat, izin, cuti, libur, di
   luar lokasi) bukan. Cuti disetujui dibaca dari `work_dates` (dan rentang tanggalnya bila kosong). **Terlambat** = Σ
   `late_min` rekaman masa kerja selain rekaman cuti. **Hari hadir** (`per_hari_hadir`) = rekaman hadir/telat + di luar lokasi
   yang sudah disetujui.
8. **Pembulatan**: prorata masuk/keluar & semua angka slip lewat `bulatkan` (dua desimal = `round(x, 2)` lama, atau rupiah
   penuh); prorata perubahan gaji PY-T2 (hari kalender, dan hari kerja baru) tetap rupiah penuh seperti PY-T2.
9. **Prorata masuk/keluar + perubahan gaji dalam bulan yang sama**: potongan perubahan dipotong lagi menurut masa kerja dan
   dinilai dengan aturan masuk/keluar; komponen tanpa tanda Diprorata dibayar nilai potongannya.
10. **`per_hari_hadir` / `persen_dasar`** hanya proses reguler (`allowed_run_types` dipaksa `["regular"]`), field baru `rate`
    (`rate` 0 / persen > 100 → 400); label "(21 hari)" / "(1 %)".
11. **Daftar libur tersembunyi** `system_settings.hr.overtime.holidays` tidak dibaca lagi (satu sumber: `hr_holidays`); tidak
    dipindah otomatis (H4 — tanggal resmi diisi pemilik); skrip data lama melaporkannya.
12. **Tanda Diprorata PT lama** tidak diubah otomatis saat server menyala (data nyata = H3): `scripts/migrasi_pyt3_aturan_gaji.py
    --apply`. PT baru (dan data uji) mendapat `prorate: true` dari isi awal. Potongan bawaan baru masuk lewat isi awal
    idempoten seperti RAPEL (PY-T2).
13. **Saldo awal pajak**: PT = PT aktif (N1); GET saat "Semua PT" memakai PT karyawan; GET kosong → `null`.
14. **`overtime-impact`**: `entity_id` opsional (diadu `resolve_requested_entity`), 400 "Pilih satu PT dulu…" saat "Semua PT";
    upah sejam tanpa masukan antrean (perkiraan); tiap karyawan + `dates`.
15. **Rapel PY-T2** mengikuti aturan slip PT (prorata masuk/keluar, hari kerja) supaya selisih = selisih nyata.
16. **U9** dipecah U9a (absensi + ambang, lulus di (a)) dan U9b (bawaan K-39, (b)); uji tambahan: dampak, komponen bawaan,
    per hari hadir/persen gaji pokok, perubahan gaji hari kerja, skrip.

### Usulan koreksi berkas unit (teks pengganti persis; berkas unit tidak diubah pelaksana)

- Keadaan sekarang, butir hub: "Hub Pengaturan › SDM berisi dua tab: `frontend/src/config/hubTabs.js:274`" → "Hub
  Pengaturan › SDM berisi tiga tab (KP-T9 menambah Mesin Absen): `frontend/src/config/hubTabs.js:325`".
- Keadaan sekarang, tambahkan butir: "Sejak PY-T2 baris Lembur dan Komisi tidak masuk slip reguler
  (`backend/services/hr_pay_components.py:199`, `earning_components`) — diperbaiki di PY-T3 (a)."
- Data, `hr_pay_components`: "Isi awal tiap PT ditambah tiga potongan `system` …" → tambahkan "(`calc: absensi`)".

## Asumsi

- Dari spesifikasi: K-39 mengubah perilaku hari ini (keputusan pemilik didahulukan); potongan mengurangi beban gaji dan
  bruto pajak; "hari tidak hadir" = hari kerja tanpa absensi dan tanpa cuti disetujui (sakelar bawaan mati);
  `persen_dasar` memakai gaji pokok, `per_hari_hadir` memakai `rate` komponen untuk semua karyawan.
- Bawaan (`00` §4.1): semua kunci baru bawaan = perilaku hari ini (prorata/potongan mati, bertingkat, 5 hari, jam kerja
  lebih, dua desimal) kecuali K-39; potongan absensi berakun beban gaji (spesifikasi); hari libur tanpa isi awal.
- Upah harian/borongan tetap bulanan (di luar lingkup). Jatah cuti, toleransi telat per shift, radius lokasi → KF-T7.

## Keraguan dan titik henti

- **H4** — tabel tarif PPh 21/PTKP/biaya jabatan tidak disentuh (K-42, PK-46); hari libur nasional tidak diisi agen.
- **H3** — `scripts/migrasi_pyt3_aturan_gaji.py` hanya diuji di database tiruan; tidak dijalankan terhadap `backend/.env`.
  Proses gaji reguler di antara PY-T2 dan unit ini tanpa lembur/komisi (regresi): proses draf cukup dihitung ulang;
  proses yang sudah diposting/dibayar = keputusan pemilik (proses susulan).
- **H5** — tidak ada sakelar potongan/prorata yang dinyalakan untuk PT nyata (seed tidak diubah).
- Lapis A (`tests/test_bp_PYT3_data_acuan.py`: U18 bersamaan, L1 dampak K-39 tiga periode, L3 skrip baca-saja; PK-14 33
  indeks) ditulis, belum dijalankan — keunikan bersamaan di MongoDB asli = "belum teruji"; hitungan dampak K-39 data acuan
  (langkah 1 spesifikasi) belum ada angkanya: integrator menjalankan L1/skrip.
- Mohon konsultan pajak memastikan potongan absensi mengurangi bruto PPh 21 (ASUMSI spesifikasi).
- `audit_config_wiring --strict` dengan database lingkungan A: 1–2 kunci DEAD (`[ent_ksc] tax.pemicu_faktur`,
  `ai.tindakan_uang_keluar`) = nilai milik TX-T2/AG-T5 di database A yang belum terdaftar di W; tanpa database (kode)
  hijau; di T hijau (lihat Penggabungan).

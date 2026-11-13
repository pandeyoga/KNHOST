# PY-T3 — Pindahkan aturan hitung gaji ke pengaturan per PT: prorata, potongan, lembur, kalender libur, saldo awal pajak

| | |
|---|---|
| Gelombang | Modul — Penggajian |
| Jenis | fitur |
| Risiko | tinggi |
| Prasyarat | PY-T1 |
| Menutup temuan | PY-04, PY-07, PY-08, PY-12 |
| Keputusan | K-38, K-39, K-42 (tabel tarif tidak disentuh — H4, unit PK-46) |
| Standar | §2.1, §2.2, §2.4, §3.1 (Z1, Z2), §3.4 (N1), §4 (L1, L4, L5, L6, L7), §5 (D1, D5, D6, D7, D9), §6 |
| Lingkungan uji | keduanya (B untuk angka; A untuk indeks unik dan hitungan dampak di data acuan) |

## Tujuan

Aturan hitung gaji yang sekarang tertanam di kode menjadi pengaturan per PT yang benar-benar berefek. Nilai bawaannya
sama dengan perilaku hari ini (prorata dan potongan mati), kecuali satu yang diputuskan pemilik: lembur hanya dibayar
bila ada pengajuan yang disetujui (K-39). PT yang mulai memakai penggajian di tengah tahun bisa mengisi saldo awal
pajaknya, dan hari libur berasal dari kalender yang diisi pemilik.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`; PY-T1 mengubah bentuk slip — cek ulang di laporannya.

- Gaji selalu penuh: `backend/services/hr_payroll_service.py:262` (`base_salary`). Karyawan dipilih dari status aktif
  tanpa melihat tanggal masuk, sehingga yang baru masuk bulan depan ikut digaji bulan ini:
  `backend/services/hr_payroll_service.py:337` (`_active_employees`).
- Absensi hanya dibaca untuk menit lembur; tidak ada potongan alpha, telat, atau cuti tanpa gaji:
  `backend/services/hr_payroll_service.py:200` (`hr_attendance`). Menit telat dan jenis cuti tanpa gaji sudah tercatat:
  `backend/services/hr_attendance_service.py:95` (`late_min`), `backend/services/hr_leave_service.py:28` (`unpaid`).
- Lembur (PY-07): pengali `hr.overtime.multiplier` terdaftar, `backend/config_catalog_ops.py:495`
  (`hr.overtime.multiplier`), tetapi hanya dipakai bila `mode == "flat"`, `backend/services/hr_payroll_service.py:221`
  (`mode`); `mode`, pola hari kerja, dan daftar libur dibaca dari setelan yang tidak terdaftar dan tidak punya layar:
  `backend/services/hr_payroll_service.py:175` (`holidays`), `backend/services/hr_payroll_service.py:181`
  (`work_days_per_week`); bawaannya hanya dua nilai, `backend/services/hr_service.py:40` (`overtime`). Simulator
  memakai rumus lain: `backend/services/config_simulator.py:370` (`_payroll_overtime`).
- Lembur dari absensi (PY-08) = menit kerja − durasi shift, jadi datang lebih awal ikut terhitung:
  `backend/services/hr_attendance_service.py:104` (`overtime_min`); rekamannya langsung berstatus disetujui kecuali di
  luar lokasi, `backend/services/hr_attendance_service.py:218` (`approved`); dan dibayar untuk tanggal tanpa pengajuan:
  `backend/services/hr_payroll_service.py:204` (`by_date`). Jadi perilaku hari ini = pengajuan **atau** absensi.
- Upah sejam dan dasar BPJS = gaji pokok saja: `backend/services/hr_payroll_service.py:217` (`hourly`),
  `backend/services/hr_payroll_service.py:272` (`bpjs_breakdown`).
- Hitung ulang pajak masa terakhir hanya mengenal slip di sistem (PY-12): `backend/services/hr_payroll_service.py:288`
  (`annual_pph21`), `backend/services/hr_payroll_service.py:231` (`_prior_year_slips`).
- Uang dibulatkan dua desimal di banyak tempat: `backend/services/hr_payroll_service.py:297` (`net`).
- Hub Pengaturan › SDM berisi dua tab: `frontend/src/config/hubTabs.js:274` (`settings-hr`).

Dari unit lain: komponen ber-`prorate`, `in_bpjs_base`, `in_overtime_base`, `taxable`, dan `account_code` (PY-T1);
`separation_date` dibaca penggajian (PK-45); aturan pajak lewat `aturan_pph21` (PK-46) — unit ini tidak mengubahnya.

## Perubahan

### Data

- **`hr_holidays` (baru, per PT):** `id` (`hhol_…`), `entity_id`, `date` (`YYYY-MM-DD`), `name`, `kind` (`nasional` ·
  `cuti_bersama` · `perusahaan`), jejak pembuat. Indeks unik (`entity_id`, `date`). **Tanpa isi awal** — tanggal libur
  nasional berasal dari keputusan pemerintah dan tidak diisi agen (H4).
- **`hr_tax_opening_balances` (baru, per PT):** `id`, `entity_id`, `employee_id`, `year`, `months` (1–11, banyaknya masa
  pajak tahun itu yang dibayar di luar sistem), `tax_gross`, `pension_deduction` (iuran JHT + JP karyawan),
  `pph21_withheld`, `note`, jejak. Indeks unik (`entity_id`, `employee_id`, `year`).
- **`hr_pay_components`:** `calc` menerima `per_hari_hadir` (nilai = `rate` × hari hadir) dan `persen_dasar` (`rate` %
  × gaji pokok). Isi awal tiap PT ditambah tiga potongan `system`: `POT_ALPHA` "Potongan tidak hadir", `POT_CUTI_TG`
  "Potongan cuti tanpa gaji", `POT_TELAT` "Potongan terlambat" — `kind: potongan`, `bucket: other_deductions`,
  `taxable: true`, `account_code` = akun beban gaji (kode hasil pemetaan `ACC_BEBAN_GAJI`), sehingga potongan mengurangi
  beban, bukan menjadi hutang. `GAJI_POKOK` dan `TUNJANGAN` diberi `prorate: true`.
- Kedua koleksi dicatat di `ENTITY_REGISTRY.md`, `SCOPED_COLLECTIONS`, dan `scripts/verify_contract.py`.

### Server

Berkas baru `backend/services/hr_work_calendar.py` dan berkas baru `backend/services/hr_pay_rules.py`:

| Fungsi | Perilaku |
|---|---|
| `async def is_holiday(entity_id, date) -> bool`; `async def work_days(entity_id, date_from, date_to) -> int` | Hari kerja = Senin–Jumat (atau Senin–Sabtu bila pola 6 hari) yang bukan `hr_holidays` PT itu |
| `async def rules(entity_id) -> dict` | Membaca semua kunci di bagian Pengaturan lewat `value_of`; satu-satunya pembaca |
| `def prorate_factor(rule, start, end, period, cal) -> float` | `mati` → 1; `hari_kalender` → hari dalam [start, end] ÷ hari kalender bulan; `hari_kerja` → hari kerja dalam rentang ÷ hari kerja bulan |
| `def bulatkan(amount, rules) -> float` | Dua desimal (bawaan) atau rupiah penuh; semua pembulatan slip lewat sini |

Perubahan penghitung slip:

1. **Perbaikan cacat (tanpa sakelar):** karyawan yang tanggal masuknya setelah akhir periode tidak ikut proses periode itu.
2. **Prorata masuk/keluar:** bila tanggal masuk atau `separation_date` jatuh di dalam periode, komponen ber-`prorate`
   dikalikan `prorate_factor(hr.prorata_masuk_keluar, …)`; labelnya ditambah "({tgl}–{tgl} {bulan})".
3. **Potongan** (masing-masing komponen sendiri; dasar harian = Σ komponen ber-`prorate` setelah prorata ÷ hari kerja
   bulan itu): tidak hadir = dasar harian × hari kerja dalam masa kerja tanpa rekaman absensi dan tanpa cuti disetujui;
   cuti tanpa gaji = dasar harian × hari kerja yang tercakup cuti `unpaid` disetujui; terlambat = Σ `late_min` ×
   `hr.potongan_telat_per_menit`. Label memuat banyaknya, mis. "Potongan tidak hadir (2 hari)".
4. **Bruto pajak** = Σ pendapatan kena pajak − Σ potongan ber-`taxable` + premi tanggungan perusahaan seperti sekarang.
5. **Lembur:** `hr.overtime.sumber = pengajuan` → hanya pengajuan `approved`; `absensi` → perilaku hari ini (pengajuan,
   lalu menit absensi yang disetujui untuk tanggal tanpa pengajuan) dengan menit < `hr.overtime.ambang_menit`
   diabaikan. Jenis hari dari `hr_work_calendar`. Pengali menurut `hr.overtime.mode`. Upah sejam = Σ komponen
   ber-`in_overtime_base` ÷ `hr.overtime.hours_divisor`.
6. **Dasar BPJS** = Σ komponen ber-`in_bpjs_base` (isi awal: gaji pokok, jadi angkanya tetap).
7. **Menit lembur absensi** (`compute_metrics`): `jam_kerja_lebih` (bawaan) seperti sekarang; `lewat_jam_pulang` =
   menit setelah jam pulang shift.
8. **Saldo awal pajak:** pada masa pajak terakhir, bila ada saldo awal untuk (PT, karyawan, tahun): bruto pajak, iuran
   pensiun, jumlah masa, dan pajak yang sudah dipotong ditambah nilai saldo awal sebelum memanggil `annual_pph21`.
   Tarif, PTKP, dan biaya jabatan tetap dari aturan yang berlaku (PK-46).
9. Simulator lembur memanggil fungsi mesin yang sama (`overtime_hour_units`), bukan rumus sendiri.

| Endpoint | Izin | Isi | Jawaban dan galat |
|---|---|---|---|
| `GET /api/hr/holidays` | `hr.view` | `year` | Daftar libur PT aktif |
| `POST /api/hr/holidays`, `DELETE /api/hr/holidays/{id}` | `hr.manage_attendance` | `{date, name, kind}` | 409 "Tanggal {tanggal} sudah terdaftar sebagai hari libur di PT ini." · 409 dari `assert_write_entity` saat "Semua PT" |
| `GET /api/hr/employees/{id}/tax-opening` | `hr.view` + `hr.view_pii` | `year` | Saldo awal atau `null` |
| `PUT /api/hr/employees/{id}/tax-opening` | `hr.manage_payroll` | `{year, months, tax_gross, pension_deduction, pph21_withheld, note?}` | 400 "Jumlah masa harus 1 sampai 11." · 409 "Pajak {tahun} karyawan ini sudah dihitung ulang, jadi saldo awalnya tidak bisa diubah." (sudah ada slip masa terakhir `posted`/`paid` tahun itu) |
| `GET /api/hr/payroll/overtime-impact` | `hr.manage_payroll` | `period` | Per karyawan: menit lembur absensi tanpa pengajuan pada periode itu dan nilainya — bahan memutuskan `hr.overtime.sumber` |

### Pengaturan

Semua di `backend/config_catalog_ops.py`: `group="sdm"`, `scopes=("global", "entity")`, `risk="high"`,
`requires_reason=True`, `permission=("hr", "manage_payroll")`, `consumers=("services/hr_pay_rules.py:rules",)`.

| key | type · default · batas | label | help · impact · example |
|---|---|---|---|
| `hr.prorata_masuk_keluar` | enum `mati` · `hari_kalender` · `hari_kerja`; bawaan `mati` | "Gaji karyawan masuk/keluar tengah bulan" | Cara menghitung gaji bulan pertama dan terakhir. · Selain "mati", gaji bulan itu dibayar sebanding hari bekerja. · "Masuk 16 Nov, gaji Rp 6.000.000, hari kalender → Rp 3.000.000" |
| `hr.prorata_perubahan_gaji` (dari PY-T2) | pilihan ditambah `hari_kerja` | — | — |
| `hr.potongan_alpha` | bool; bawaan tidak | "Potong gaji untuk hari tidak hadir" | Hari kerja tanpa absensi dan tanpa cuti dipotong. Nyalakan hanya bila absensi dipakai semua karyawan. · Mengurangi gaji bersih. · "2 hari dari 21 hari kerja, gaji Rp 6.300.000 → potong Rp 600.000" |
| `hr.potongan_cuti_tanpa_gaji` | bool; bawaan tidak | "Potong gaji untuk cuti tanpa gaji" | Hari cuti berjenis Cuti Tanpa Gaji dipotong sebesar upah sehari. · Mengurangi gaji bersih. · "1 hari → Rp 300.000" |
| `hr.potongan_telat_per_menit` | money; 0; 0–100.000; Rp/menit | "Potongan terlambat per menit (Rp)" | 0 = tidak dipotong. · Mengurangi gaji bersih. · "45 menit × Rp 1.000 → Rp 45.000" |
| `hr.overtime.sumber` | enum `pengajuan` · `absensi`; bawaan `pengajuan` (K-39) | "Lembur dibayar berdasarkan" | Pengajuan yang disetujui saja, atau juga menit lebih di absensi. · Pada "pengajuan", lembur tanpa pengajuan tidak dibayar. · "Pulang 2 jam lebih lama tanpa pengajuan → tidak dibayar" |
| `hr.overtime.ambang_menit` | int; 0; 0–240; menit | "Lembur absensi minimal (menit)" | Menit lebih di bawah angka ini tidak dihitung. 0 = semua dihitung. Hanya untuk sumber absensi. · — · "Ambang 30 → lebih 20 menit diabaikan" |
| `hr.overtime.mode` | enum `bertingkat` · `flat`; bawaan `bertingkat` | "Cara menghitung pengali lembur" | Bertingkat: 1,5× jam pertama lalu 2× (hari libur 2×/3×/4×). Flat: satu pengali dari "Pengali upah lembur". · Mengubah nominal lembur. · "2 jam, upah sejam Rp 30.000 → Rp 105.000 atau Rp 90.000" |
| `hr.overtime.work_days_per_week` | enum `5` · `6`; bawaan `5` | "Hari kerja seminggu" | Menentukan Sabtu hari kerja atau hari istirahat, untuk lembur dan hitungan hari kerja. · — · "6 → Sabtu dihitung hari kerja" |
| `hr.overtime.hitung_absensi` | enum `jam_kerja_lebih` · `lewat_jam_pulang`; bawaan `jam_kerja_lebih` | "Menit lembur di absensi dihitung dari" | Jam kerja melebihi durasi shift, atau hanya waktu setelah jam pulang. · Datang lebih awal tidak lagi terhitung pada pilihan kedua. · "Masuk 07.00, pulang 17.30, shift 08–17 → 90 atau 30 menit" |
| `hr.pembulatan_rupiah` | bool; bawaan tidak | "Bulatkan angka slip ke rupiah penuh" | Tanpa ini slip memakai dua angka di belakang koma. · — · "Rp 3.142.857,14 → Rp 3.142.857" |

`hr.overtime.multiplier` (sudah ada): `help` ditambah "Dipakai hanya bila cara hitung pengali = flat."; di layar, saat
mode bertingkat, kuncinya diberi keterangan itu (L6).

### Izin dan peran

Tidak ada pasangan izin baru. Modul akses `hr`: `nav` ditambah `hr-holidays`.

### Layar

- Pengaturan › SDM, tab baru **Kalender Libur** (view `hr-holidays`, komponen baru
  `frontend/src/features/hr/HolidaysView.jsx`): pemilih tahun; kolom "Tanggal", "Nama", "Jenis" (Nasional · Cuti
  bersama · Perusahaan); tombol "Tambah hari libur" (pop-up baku) dan "Hapus". Keterangan: "Isi dari keputusan resmi
  libur nasional dan cuti bersama. Sistem tidak mengisinya sendiri." Kosong: "Belum ada hari libur untuk tahun ini."
- Kartu karyawan, bagian baru **Saldo awal pajak {tahun}** (hanya pemegang `hr.view_pii`): "Jumlah masa di luar
  sistem", "Bruto", "Iuran pensiun", "PPh 21 sudah dipotong", "Catatan"; tombol "Simpan". Keterangan: "Isi sekali bila
  penggajian mulai dipakai di tengah tahun, supaya hitung ulang pajak akhir tahun benar."
- Pusat Pengaturan › SDM & Penggajian: kunci baru tampil lewat registry; di bawah "Lembur dibayar berdasarkan" ada
  tautan "Lihat dampaknya" yang membuka hasil `overtime-impact` periode berjalan.
- Tab Komponen & Masukan (PY-T1): tanda "belum dipakai" pada kolom "Dasar BPJS", "Dasar lembur", "Diprorata" dicabut.

## Uji penerimaan

Fixture di `ent_kanda`; BPJS dimatikan untuk PT itu kecuali U13; periode November 2026 (30 hari; 21 hari kerja pola 5
hari tanpa libur). Tarif pajak dari aturan bawaan pada `3132cc4` (tes mengambilnya dari fungsi, bukan mengetik ulang).

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | K1 gaji 6.000.000, masuk 16 Nov; semua kunci bawaan | Proses reguler 2026-11 | Gaji Pokok 6.000.000 (prorata mati = perilaku hari ini) |
| U2 | B | U1; `hr.prorata_masuk_keluar = hari_kalender` untuk `ent_kanda` | Hitung ulang | 3.000.000 (6.000.000 × 15 ÷ 30); karyawan PT lain tidak berubah |
| U3 | B | U1; `hari_kerja`; lalu libur perusahaan 25 Nov | Hitung ulang dua kali | 3.142.857,14 (× 11 ÷ 21); lalu 3.000.000 (× 10 ÷ 20) |
| U4 | B | K2 masuk 5 Des 2026 | Proses reguler 2026-11 | K2 tidak punya slip, apa pun nilai kuncinya |
| U5 | B | K3 gaji 6.000.000, `separation_date` 15 Nov; `hari_kalender` | Proses | 3.000.000 (× 15 ÷ 30) |
| U6 | B | K4 gaji 6.300.000; absensi 19 dari 21 hari kerja; `hr.potongan_alpha` ya | Proses, sahkan, posting | "Potongan tidak hadir (2 hari)" 600.000 (6.300.000 ÷ 21 × 2); bruto pajak 5.700.000; `pph21` 28.500 (× 0,5 %); `net` 5.671.500. Jurnal: Dr 6-1000 6.300.000 / Cr 6-1000 600.000, Cr 2-1800 28.500, Cr 2-1600 5.671.500. Dengan kunci bawaan: tanpa potongan, `pph21` 47.250, `net` 6.252.750 |
| U7 | B | K4 hadir penuh kecuali cuti `unpaid` disetujui 12 Nov; `hr.potongan_cuti_tanpa_gaji` ya | Proses | "Potongan cuti tanpa gaji (1 hari)" 300.000 |
| U8 | B | K4 total `late_min` 45; `hr.potongan_telat_per_menit` 1.000 | Proses | "Potongan terlambat (45 menit)" 45.000 |
| U9 | B | K5 gaji 5.190.000 (upah sejam 30.000); pengajuan lembur disetujui 2 jam 10 Nov; absensi 11 Nov lebih 120 menit, disetujui, tanpa pengajuan | Proses dengan bawaan; lalu `sumber = absensi`; lalu ambang 150 | 105.000 (1 × 1,5 + 1 × 2 = 3,5 jam-upah); 210.000; 105.000 |
| U10 | B | K5, hanya pengajuan 2 jam; `hr.overtime.mode = flat`, pengali 1,5 | Proses; jalankan simulator lembur 4 jam pada mode bertingkat | 90.000 (2 × 1,5 × 30.000); simulator 225.000 (1,5 + 3 × 2 = 7,5 jam-upah) — sama dengan mesin |
| U11 | B | K5; 25 Nov terdaftar libur; pengajuan 2 jam pada 25 Nov | Proses | 120.000 (2 × 2 × 30.000) |
| U12 | B | K5; pengajuan 2 jam Sabtu 14 Nov; `work_days_per_week` 5 lalu 6 | Proses dua kali; `work_days` November | 120.000 lalu 105.000; hari kerja 21 lalu 25 |
| U13 | B | BPJS menyala dengan tarif bawaan; K6 gaji pokok 5.000.000 + komponen tetap 1.000.000 ber-`in_bpjs_base` | Proses | BPJS Kesehatan karyawan 60.000 (1 % × 6.000.000); tanpa tanda: 50.000 |
| U14 | B | K7 TK0, 8.000.000 per bulan; slip Jul–Nov di sistem (pajak 5 × 120.000); saldo awal 2026: 6 masa, bruto 48.000.000, PPh 720.000 | Proses reguler 2026-12 | Bruto setahun 96.000.000; biaya jabatan 4.800.000; neto 91.200.000; PKP 37.200.000; pajak setahun 1.860.000; `pph21` Desember 540.000 (1.860.000 − 720.000 − 600.000). Tanpa saldo awal: −600.000 |
| U15 | B | Shift 08.00–17.00; masuk 07.00, pulang 17.30 | Catat absensi dengan bawaan; lalu `lewat_jam_pulang` | `overtime_min` 90; lalu 30 |
| U16 | B | U3 pertama; `hr.pembulatan_rupiah` ya | Hitung ulang | 3.142.857 |
| U17 | B | Sebelas kunci | Putaran `t1_config.py`; nilai tak sah (`hari`, −5) | Lulus; 400 |
| U18 | B, A | Peran Manajer Kosong; di A dua `POST` libur bertanggal sama | `POST /api/hr/holidays`; `PUT` saldo awal | 403; 403; di A satu tersimpan dan satu 409 |

## Langkah kerja

**Serah-terima (a) — pengaturan dan pembantu; hasil hitung belum berubah.**
1. `backend/tests_mem/test_PYT3_aturan_hitung.py`: U1–U17 (merah). Catat dari data acuan (lingkungan A) hasil
   `overtime-impact` tiga periode terakhir: berapa menit lembur absensi tanpa pengajuan yang selama ini dibayar.
2. Kunci-kunci dengan bawaan = perilaku hari ini, **`hr.overtime.sumber` sementara berbawaan `absensi`**;
   `hr_work_calendar`, `hr_pay_rules`, dua koleksi dan endpointnya, layar Kalender Libur dan Saldo awal pajak.
3. Penghitung slip membaca semua aturan lewat `rules()`; dengan bawaan, slip data acuan sama persis dengan sebelum unit
   ini (bandingkan pratinjau). Simulator memakai fungsi mesin. Gate; catat SHA.

**Serah-terima (b) — perilaku yang berubah.**
4. Bawaan `hr.overtime.sumber` menjadi `pengajuan` (K-39); perbaikan tanggal masuk; potongan dan prorata aktif bila
   kuncinya dinyalakan; tiga komponen potongan; calc `per_hari_hadir` dan `persen_dasar`.
5. Gate penuh. Laporan memuat hitungan langkah 1 dan kalimat untuk pemilik: "Sejak unit ini, lembur dari absensi tanpa
   pengajuan tidak dibayar kecuali pengaturan 'Lembur dibayar berdasarkan' diubah ke absensi."

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (dua koleksi); `CODEBASE_MAP.md`; `memory/PRD.md`; `docs/KN_13_NAVIGATION_MAP.md` (tab Kalender
Libur); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("prorata", "saldo awal pajak", "hari kerja").

## Di luar lingkup

- Isi dan tanggal berlaku tabel tarif, PTKP, pasal 17, biaya jabatan → PK-46 (H4). Unit ini tidak mengetik satu pun
  angka peraturan dan tidak mengisi `hr_holidays`.
- Riwayat kompensasi dan prorata perubahan gaji → PY-T2 (di sini hanya menambah pilihan `hari_kerja`).
- Upah harian dan borongan (jenis hubungan kerja selain bulanan) tetap dihitung bulanan; tidak dirancang.
- Jatah cuti, toleransi telat per shift, dan radius lokasi (lampiran C audit konfigurasi #57, #62) → KF-T7.

## Asumsi dan risiko

- `ASUMSI:` bawaan K-39 (`pengajuan`) mengubah perilaku hari ini, yang juga membayar menit lebih dari absensi. Keputusan
  pemilik didahulukan atas aturan "bawaan = hari ini"; pilihan `absensi` mempertahankan cara lama.
- `ASUMSI:` potongan tidak hadir, cuti tanpa gaji, dan terlambat mengurangi beban gaji dan bruto pajak.
- `ASUMSI:` "hari tidak hadir" = hari kerja tanpa rekaman absensi dan tanpa cuti disetujui; karena itu sakelarnya
  berbawaan mati dan diberi peringatan untuk PT yang absensinya belum lengkap.
- `ASUMSI:` `persen_dasar` memakai gaji pokok sebagai dasar; `per_hari_hadir` memakai `rate` komponen untuk semua karyawan.
- `RISIKO:` slip berubah tanpa disadari saat kunci dinyalakan. Penangkal: semua kunci `risk="high"` beralasan, dan
  langkah 3 membuktikan bawaan tidak mengubah slip. Membatalkan: kembalikan nilai kunci ke bawaan; untuk (b), setel
  `hr.overtime.sumber` global ke `absensi`.

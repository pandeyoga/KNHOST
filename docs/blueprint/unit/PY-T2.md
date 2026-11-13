# PY-T2 — Catat riwayat kompensasi dan penugasan PT karyawan dengan tanggal berlaku

| | |
|---|---|
| Gelombang | Modul — Penggajian |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | PY-T1 |
| Menutup temuan | PY-09 |
| Keputusan | K-37, K-38 |
| Standar | §2.1, §2.2, §2.4, §3.1 (Z1, Z2), §3.4 (N1, N2), §4 (L1, L4, L7), §5 (D1, D2, D3, D7, D9), §6 |
| Lingkungan uji | keduanya (B untuk alur dan angka; A untuk indeks unik dan migrasi di data acuan) |

## Tujuan

Gaji pokok, komponen tetap, dan PT tempat karyawan digaji tidak lagi ditimpa di master: tiap perubahan menjadi baris
bertanggal berlaku yang disahkan. Proses gaji memakai nilai yang berlaku pada periodenya, karyawan yang pindah PT
digaji dan dipajaki per PT dengan benar, dan kenaikan yang berlaku mundur menghasilkan usulan rapel.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

- Gaji pokok, tunjangan, dan PT adalah field master yang boleh ditimpa lewat `PATCH`: `backend/routers/hr.py:33`
  (`base_salary`); gaji pokok hanya dibulatkan lalu disimpan, `backend/routers/hr.py:418` (`base_salary`). Tidak ada
  tanggal berlaku, riwayat, maupun penyetuju; jejak audit menyamarkan nilainya, `backend/routers/hr.py:429`
  (`masked_fields`).
- Karyawan baru menerima ketiganya langsung dari isi permintaan: `backend/routers/hr.py:298` (`base_salary`),
  `backend/routers/hr.py:305` (`entity_id`).
- Proses gaji membaca master saat dihitung, bukan nilai pada periodenya: `backend/services/hr_payroll_service.py:262`
  (`base_salary`), `backend/services/hr_payroll_service.py:263` (`_sum_allowances`). Karyawan dipilih dari `entity_id`
  master saat itu: `backend/services/hr_payroll_service.py:341` (`entity_id`).
- Hitung ulang pajak tahunan mengambil slip karyawan dari semua PT: `backend/services/hr_payroll_service.py:235`
  (`hr_payslips`) — saringannya hanya `employee_id` dan tahun.
- Nilai gaji termasuk data pribadi: `backend/services/hr_service.py:17` (`PII_FIELDS`); izin lihatnya
  `backend/routers/hr.py:42` (`view_pii`).
- Layar: isian gaji dan tunjangan ada di form karyawan, `frontend/src/features/hr/EmployeeFormDrawer.jsx:90`
  (`base_salary`); kartu karyawan menampilkan nilai kini saja, `frontend/src/features/hr/Employee360Panel.jsx:72`
  (`Gaji Pokok`).

Yang dipakai dari PY-T1: `hr_pay_components` (komponen `tetap_bulanan`), pembangun `components[]`, `enqueue_input`.

## Perubahan

### Data

**`hr_compensation_history` (baru).**

| Field | Tipe | Wajib | Arti |
|---|---|---|---|
| `id`, `employee_id` | teks | ya | `hcomp_…` |
| `effective_from`, `effective_to` | `YYYY-MM-DD` | ya, tidak | Berlaku sejak; `effective_to` diisi sistem (sehari sebelum baris sah berikutnya) |
| `base_salary` | rupiah ≥ 0 | ya | Gaji pokok |
| `fixed_components[]` | `{component_code, label, amount}` | tidak | Komponen `tetap_bulanan` selain gaji pokok (mis. Tunjangan Jabatan) |
| `status` | `pending` · `approved` · `rejected` · `cancelled` | ya | Hanya `approved` yang dibaca proses gaji |
| `reason`, `source` | teks; `manual` · `migrasi` | ya | Alasan perubahan; asal baris |
| `proposed_by`, `approved_by`, `approved_at` | `{id, name}`, waktu | sesuai status | Pengusul dan penyetuju |

Indeks unik parsial (`employee_id`, `effective_from`) untuk `status: "approved"`.

**`hr_employee_assignments` (baru).** `id` (`hasg_…`), `employee_id`, `entity_id`, `effective_from`, `effective_to`,
`department_id`, `position_id`, `status`, `reason`, `proposed_by`, `approved_by`, `approved_at`, `source`. Indeks unik
parsial yang sama. Keduanya dicatat di `ENTITY_REGISTRY.md`; penugasan masuk `SCOPED_COLLECTIONS`.

**`hr_employees`:** `base_salary`, `allowances`, dan `entity_id` menjadi nilai turunan (baris yang berlaku hari ini),
ditulis hanya oleh layanan riwayat. Invarian baru `INV-PY-2` di `scripts/verify_data_integrity.py`: untuk tiap karyawan
aktif, ketiganya = baris `approved` yang berlaku hari ini (WIB).

**Komponen bawaan baru** tiap PT: `RAPEL` (pendapatan, `masukan`, `taxable`, `other_earnings`, proses `regular` dan
`susulan`, `system`).

**Migrasi** — skrip baru `scripts/migrate_hr_compensation_py_t2.py` (diuji di data acuan; data nyata = H3): tiap
karyawan tanpa riwayat mendapat satu baris kompensasi `approved` ber-`source: "migrasi"` (`effective_from` = tanggal
masuk; bila kosong, tanggal dibuat; `fixed_components` = tiap isi `allowances` dengan `component_code: "TUNJANGAN"` dan
`label` = namanya) dan satu baris penugasan dengan PT, departemen, dan jabatan kini. Idempoten. Laporan memuat jumlah
karyawan dan bukti pratinjau gaji bulan berjalan sebelum = sesudah.

### Server

Berkas baru `backend/services/hr_compensation_service.py`:

| Fungsi | Perilaku |
|---|---|
| `async def compensation_at(employee_id, date) -> dict` | Baris `approved` yang berlaku pada tanggal itu |
| `async def segments(employee_id, entity_id, period) -> list` | Potongan periode menurut perubahan kompensasi dan penugasan di PT itu: `{date_from, date_to, days, base_salary, fixed_components}` |
| `async def employees_for_run(entity_id, period) -> list` | Karyawan yang penugasannya di PT itu bersinggungan dengan periode; menggantikan saringan `entity_id` master |
| `async def apply_effective(today) -> int` | Menyalin baris yang mulai berlaku ke master; dipanggil saat pengesahan dan oleh tugas terjadwal baru `hr_compensation_effective` (harian 00.10 WIB) |

Aturan hitung di proses gaji (`compute_payslip`):

- `hr.prorata_perubahan_gaji = mati` (bawaan): satu baris per komponen dengan nilai yang berlaku pada **hari terakhir
  periode** (atau hari terakhir bekerja di PT itu); karyawan yang pindah di tengah bulan digaji penuh oleh PT tempat ia
  berada pada akhir periode dan tidak ikut proses PT lama bulan itu. Ini perilaku hari ini.
- `hari_kalender`: tiap potongan menjadi baris sendiri berlabel "{nama komponen} ({tgl awal}–{tgl akhir} {bulan})"
  bernilai `nilai × hari potongan ÷ hari kalender bulan itu`, dibulatkan ke rupiah penuh; karyawan yang pindah muncul
  di proses kedua PT dengan potongannya masing-masing.
- Hitung ulang pajak tahunan hanya memakai slip karyawan **di PT proses itu** (`_prior_year_slips` disaring
  `entity_id`).
- Rapel: saat baris kompensasi disahkan dan `effective_from` jatuh pada periode yang proses regulernya sudah `posted`
  atau `paid`, untuk tiap periode itu dibuat masukan `pending` (PY-T1): komponen `RAPEL`, `pay_period` bulan berjalan,
  `amount` = selisih nilai baru − nilai yang dibayar (mengikuti aturan prorata), `label` "Rapel gaji {bulan tahun}",
  `source_type: "rapel"`, `source_key: "rapel:<id baris>:<periode>"`. Statusnya `pending`: orang yang mengesahkannya.

| Endpoint | Izin | Isi | Jawaban dan galat |
|---|---|---|---|
| `GET /api/hr/employees/{id}/compensation` | `hr.view` + `hr.view_pii` | — | `{compensation: [...], assignments: [...]}`. Tanpa `view_pii` → 403 bentuk Z6 |
| `POST /api/hr/employees/{id}/compensation` | `hr.update` | `{effective_from, base_salary, fixed_components?, reason}` | Baris `pending`. 400 "Tanggal berlaku harus berbentuk TTTT-BB-HH." · 400 "Komponen {kode} bukan komponen tetap bulanan di PT ini." · 400 "Alasan wajib diisi." |
| `POST /api/hr/compensation/{row_id}/approve`, `…/reject`, `…/cancel` | `payroll.approve` | `{reason?}` | Baris terbaru. 409 "Sudah ada perubahan kompensasi yang berlaku {tanggal} untuk karyawan ini." · 409 "Baris yang sudah disahkan tidak bisa diubah. Buat baris baru dengan tanggal berlaku baru." |
| `POST /api/hr/employees/{id}/assignments` | `hr.update` | `{entity_id, effective_from, department_id?, position_id?, reason}` | Penugasan `pending`; PT tujuan harus dalam cakupan pelaku, selain itu 403 |
| `POST /api/hr/assignments/{row_id}/approve`, `…/reject` | `payroll.approve` | — | Penugasan terbaru |
| `PATCH /api/hr/employees/{id}` (diubah) | `hr.update` | — | `base_salary`, `allowances`, `entity_id` ditolak: 400 "Gaji dan penugasan PT diubah lewat Riwayat Kompensasi di kartu karyawan." |
| `POST /api/hr/employees` (diubah) | `hr.create` | seperti sekarang | Juga membuat baris kompensasi dan penugasan pertama berstatus `approved`, berlaku sejak tanggal masuk |

Semua endpoint ber-id mengadu PT karyawan dengan cakupan pelaku (`assert_entity_access`).

### Pengaturan

Satu kunci baru di `backend/config_catalog_ops.py`: `key` `hr.prorata_perubahan_gaji` · `group` `sdm` · `type` `enum` ·
`options` `mati` ("Tidak diprorata: pakai nilai akhir bulan") dan `hari_kalender` ("Prorata menurut hari kalender") ·
`default` `mati` (perilaku hari ini; K-38) · `scopes` `("global", "entity")` · `label` "Gaji berubah di tengah bulan" ·
`help` "Menentukan cara menghitung gaji bulan saat gaji atau PT karyawan berubah di tengah bulan." · `impact`
"Prorata membagi gaji bulan itu menurut jumlah hari tiap nilai berlaku; karyawan yang pindah PT dibayar kedua PT
sesuai harinya." · `example` "Naik dari Rp 6.000.000 ke Rp 7.500.000 per 16 November → Rp 3.000.000 + Rp 3.750.000" ·
`risk` `high` · `requires_reason` `True` · `permission` `("hr", "manage_payroll")` · `consumers`
`services/hr_compensation_service.py:segments`. Pilihan `hari_kerja` ditambahkan PY-T3 setelah kalender kerja ada.

### Izin dan peran

Tidak ada pasangan izin baru: mengusulkan = `hr.update` (yang hari ini boleh mengubah gaji); mengesahkan =
`payroll.approve` (PK-22); melihat = `hr.view_pii`.

### Layar

- Kartu karyawan (`Employee360Panel.jsx`), dua bagian baru yang hanya tampil bagi pemegang `hr.view_pii`.
  **Riwayat Kompensasi**: kolom "Berlaku sejak", "Gaji pokok", "Komponen tetap", "Status", "Alasan", "Diajukan oleh",
  "Disahkan oleh"; tombol "Ajukan perubahan" (pop-up baku: Berlaku sejak, Gaji pokok, Komponen tetap, Alasan) dan, pada
  baris `pending`, "Sahkan", "Tolak". **Penugasan PT**: kolom "Berlaku sejak", "PT", "Departemen", "Jabatan", "Status";
  tombol "Pindahkan ke PT lain". Lencana: Menunggu disahkan · Berlaku · Akan berlaku · Berakhir · Ditolak. Konfirmasi
  sahkan: "Sahkan gaji pokok Rp … untuk {nama}, berlaku {tanggal}, di {nama PT}?"
- Form karyawan (`EmployeeFormDrawer.jsx`): saat mengubah, isian "Gaji pokok", "Tunjangan", dan "PT" hanya-baca dengan
  petunjuk "Ubah lewat Riwayat Kompensasi."; saat membuat tetap bisa diisi.

## Uji penerimaan

Fixture: karyawan K1 di `ent_ksc`, gaji pokok 6.000.000, tunjangan Transport 500.000, TK0, masuk 1 Jan 2026; BPJS
dimatikan untuk kedua PT uji.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B, A | K1 tanpa riwayat | Jalankan migrasi dua kali | Satu baris kompensasi (6.000.000 + Transport 500.000) dan satu penugasan, berlaku 2026-01-01; pratinjau gaji bulan berjalan: `gross` 6.500.000 sebelum dan sesudah |
| U2 | B | U1 | Ajukan 7.500.000 berlaku 2026-12-01; sahkan pada November; proses reguler 2026-11 dan 2026-12 | November: Gaji Pokok 6.000.000; Desember: 7.500.000; master `base_salary` tetap 6.000.000 sampai `apply_effective("2026-12-01")` dijalankan, lalu 7.500.000 |
| U3 | B | U1; kenaikan 7.500.000 berlaku 2026-11-16, disahkan; pengaturan bawaan | Proses reguler 2026-11 | Satu baris Gaji Pokok 7.500.000 (nilai akhir bulan) |
| U4 | B | U3 dengan `hr.prorata_perubahan_gaji = hari_kalender` untuk `ent_ksc` | Hitung ulang | Dua baris: "Gaji Pokok (1–15 Nov)" 3.000.000 (6.000.000 × 15 ÷ 30) dan "Gaji Pokok (16–30 Nov)" 3.750.000 (7.500.000 × 15 ÷ 30); `base_salary` 6.750.000. PT lain tidak berubah |
| U5 | B | Proses September dan Oktober `posted` dengan 6.000.000 | Sahkan kenaikan 7.500.000 berlaku 2026-09-01 pada 10 Nov; sahkan lagi permintaan yang sama | Dua masukan `pending` komponen `RAPEL` untuk 2026-11, masing-masing 1.500.000, berlabel "Rapel gaji September 2026" dan "Rapel gaji Oktober 2026"; pengulangan tidak menambah masukan |
| U6 | B | U5; kedua masukan disahkan | Proses reguler 2026-11 | Slip K1 memuat dua baris rapel; `other_earnings` 3.000.000 |
| U7 | B | K1 dipindah ke `ent_kanda` berlaku 2026-11-01, disahkan | Proses reguler 2026-10 dan 2026-11 di kedua PT | Oktober: hanya `ent_ksc` memuat K1. November: hanya `ent_kanda` |
| U8 | B | U7; slip Jan–Okt di `ent_ksc`, Nov di `ent_kanda` | Proses reguler 2026-12 di `ent_kanda` | `pph21_annual.months` = 2 (November dan Desember); slip `ent_ksc` tidak ikut |
| U9 | B | — | `PATCH /api/hr/employees/{K1}` dengan `base_salary`; `POST /api/hr/employees` karyawan baru bergaji 5.000.000 | 400 dengan pesan riwayat; karyawan baru punya satu baris kompensasi `approved` 5.000.000 |
| U10 | B | Peran dengan `hr.view` tanpa `hr.view_pii`; peran dengan `hr.update` tanpa `payroll.approve` | `GET` riwayat; sahkan baris | 403; 403 |
| U11 | B, A | Baris `approved` berlaku 2026-12-01 | Ajukan dan sahkan baris lain bertanggal sama; di A dua pengesahan bersamaan | 409 "Sudah ada perubahan kompensasi yang berlaku 2026-12-01…"; di A tepat satu `approved` |
| U12 | B | Pelaku hanya ditugaskan di `ent_ksc` | Ajukan penugasan K1 ke `ent_kanda` | 403 |
| U13 | B | Kunci baru | Putaran `t1_config.py`; nilai "harian" | Lulus; 400 |
| U14 | B | U2 setelah `apply_effective` | `INV-PY-2` | Lulus; ubah master langsung di database → gagal menyebut K1 |
| U15 | layar (uji jalan) | U2 | Buka kartu K1 | Dua baris riwayat: 6.000.000 "Berlaku", 7.500.000 "Akan berlaku"; isian gaji di form ubah hanya-baca |

## Langkah kerja

1. `backend/tests_mem/test_PYT2_riwayat_kompensasi.py`: U1–U14 (merah); bagian A di `backend/tests/test_bp_PYT2_migrasi.py`.
2. Dua koleksi, indeks, komponen `RAPEL`, kunci pengaturan; `hr_compensation_service` (baca saja) dan skrip migrasi.
3. Endpoint usul, sahkan, tolak; `apply_effective` dan tugas terjadwalnya; invarian.
4. Pengalihan `compute_payslip` dan pemilihan karyawan ke riwayat; pajak tahunan per PT; rapel.
5. Tolak `PATCH` master; `POST` karyawan membuat baris pertama; layar; uji jalan; gate.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (dua koleksi; `hr_employees` bernilai turunan); `CODEBASE_MAP.md`; `memory/PRD.md`;
`docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("riwayat kompensasi", "penugasan PT", "rapel").

## Di luar lingkup

- Prorata masuk dan keluar tengah bulan, potongan absen, kalender kerja, pilihan `hari_kerja` → PY-T3.
- Kontrol dua orang untuk pengesahan kompensasi: belum ada aksinya di `KONTROL_AKSI`; orang yang sama boleh mengusulkan
  lalu mengesahkan bila memegang kedua izin.
- Bukti potong per PT untuk karyawan yang pindah → di luar blueprint (K-08).

## Asumsi dan risiko

- `ASUMSI:` tanpa prorata, PT pada akhir periode membayar gaji sebulan penuh (setara perilaku hari ini, yang membaca
  master saat proses dibuat).
- `ASUMSI:` rapel dibayar di bulan berjalan sebagai masukan `pending`; nominalnya selisih nilai baru dan lama per
  periode yang sudah diposting.
- `ASUMSI:` hitung ulang pajak tahunan per PT, karena tiap PT pemotong pajak tersendiri.
- `RISIKO:` migrasi memberi tanggal berlaku keliru bila tanggal masuk kosong. Penangkal: laporan migrasi mendaftar
  karyawan yang memakai tanggal dibuat. Membatalkan: kembalikan pembaca ke master; kedua koleksi tidak dibaca kode lama.

# PY-T5 — Tampilkan slip di swalayan karyawan hanya setelah gaji dibayar, lengkap dengan riwayat dan rincian komponen

| | |
|---|---|
| Gelombang | Modul — Penggajian |
| Jenis | fitur |
| Risiko | rendah |
| Prasyarat | PY-T1 |
| Menutup temuan | — |
| Keputusan | K-37 (slip berkomponen); aturan "setelah dibayar" dari rancangan `09` §3.6, dijadikan pengaturan (`00` §4.1) |
| Standar | §2.1, §2.2, §2.4, §3.1 (Z1, Z3), §4 (L1, L2, L4), §5 (D4), §6 |
| Lingkungan uji | B untuk endpoint; layar (uji komponen dan uji jalan di A) |

## Tujuan

Karyawan melihat slip gajinya sendiri di Profil Saya setelah gajinya benar-benar dibayar: daftar per tahun, rincian
tiap komponen (termasuk tiap baris insentif), dan PDF. Slip yang masih draf, diajukan, dibatalkan, atau di-void tidak
pernah terlihat olehnya.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`; PK-22 menambah status `cancelled` dan `void`, PY-T1 menambah `components[]` dan
`run_type` — cek ulang di laporannya.

- Daftar slip milik sendiri memuat slip sejak proses **disahkan**, belum dibayar:
  `backend/services/hr_payroll_service.py:596` (`my_payslips`).
- Pemilik slip bisa membuka slipnya lewat id dalam status apa pun, termasuk draf:
  `backend/routers/hr_payroll.py:254` (`_can_view_slip`), dipakai `backend/routers/hr_payroll.py:229` (`get_payslip`)
  dan `backend/routers/hr_payroll.py:240` (`payslip_pdf`).
- Endpoint daftar hanya butuh login dan berakhir `/me`: `backend/routers/hr_payroll.py:223` (`my_payslips`).
- Status slip mengikuti status prosesnya: `backend/services/hr_payroll_service.py:443` (`update_many`).
- Kartu di Profil Saya hanya menampilkan slip terakhir dan jumlah slip:
  `frontend/src/features/hr/MyPayslipCard.jsx:25` (`latest`), `frontend/src/features/hr/MyPayslipCard.jsx:40`
  (`slip tersedia`); dipasang di `frontend/src/features/hr/EmployeeSelfService.jsx:9` (`MyPayslipCard`). Menu Profil
  Saya selalu tersedia untuk peran apa pun: `backend/access_modules.py:14` (`ALWAYS_NAV`).
- PDF slip dibuka lewat `frontend/src/features/hr/payrollUtils.js:32` (`openPayslipPdf`).

## Perubahan

### Data

Tidak ada koleksi atau field baru.

### Server

Satu penentu di `hr_payroll_service.py`: `async def slip_visible_to_owner(slip) -> bool` — benar bila status slip
termasuk daftar yang diizinkan pengaturan PT slip itu: `dibayar` → `{"paid"}`; `disahkan` → `{"approved", "posted",
"paid"}`. Status `draft`, `pending_approval`, `cancelled`, `voiding`, `void` selalu salah, apa pun pengaturannya.

| Endpoint | Izin | Perubahan |
|---|---|---|
| `GET /api/hr/payslips/me` | login (Z3: milik sendiri) | Parameter `year` (bawaan tahun berjalan WIB) dan `period`. Jawaban `{employee, years: [tahun yang punya slip terlihat], payslips: [...]}`; tiap slip: `id`, `number`, `period`, `run_type`, `paid_at`, `gross`, `net`, `pph21`, `components[]`, `bank`. Hanya slip yang lolos `slip_visible_to_owner`; urut periode menurun, lalu `paid_at` |
| `GET /api/hr/payslips/{id}`, `…/{id}/pdf` | pemilik slip atau `hr.view` | Untuk pemilik (tanpa `hr.view`): slip yang tidak lolos `slip_visible_to_owner` → 404 "Slip gaji ini belum terbit." Pemegang `hr.view` tidak berubah. Slip orang lain tetap 403 |

Akun tanpa karyawan tertaut tetap menerima `{employee: null, years: [], payslips: []}` (200).

### Pengaturan

Satu kunci baru di `backend/config_catalog_ops.py`: `key` `hr.slip_swalayan_sejak` · `group` `sdm` · `type` `enum` ·
`options` `dibayar` ("Setelah gaji dibayar") dan `disahkan` ("Sejak penggajian disahkan") · `default` `dibayar` ·
`scopes` `("global", "entity")` · `label` "Slip terlihat karyawan sejak" · `help` "Menentukan kapan karyawan bisa melihat
slip gajinya sendiri di Profil Saya." · `impact` "Pada pilihan 'disahkan', karyawan melihat slip sebelum uangnya
ditransfer." · `example` "Gaji November disahkan 28 Nov, dibayar 1 Des → 'dibayar': slip muncul 1 Des" · `risk`
`medium` · `permission` `("hr", "manage_payroll")` · `consumers` `services/hr_payroll_service.py:slip_visible_to_owner`.

### Izin dan peran

Tidak ada pasangan izin baru.

### Layar

Profil Saya (`EmployeeSelfService.jsx`). `MyPayslipCard.jsx` diganti isinya menjadi kartu **Slip Gaji Saya**:

- Ringkasan slip terakhir: "Periode {bulan tahun}", "Gaji bersih diterima" dan nominalnya, "Dibayar {tanggal}", tombol
  "Lihat slip (PDF)".
- **Riwayat slip** dengan pemilih tahun (dari `years`): kolom "Periode", "Jenis" (Reguler · THR · Susulan), "Dibayar",
  "Gaji bersih"; tiap baris bisa dibuka menjadi rincian komponen — kelompok "Pendapatan" dan "Potongan" dengan label
  dan nominal tiap komponen (mis. "Insentif Bulanan — Okt 2026"), lalu "Gaji bersih"; tombol "PDF" per baris.
- Keadaan: memuat "Memuat slip…"; galat "Slip belum bisa dimuat. Coba lagi." (tidak lagi diam); kosong "Belum ada slip
  gaji yang terbit." dengan keterangan "Slip muncul setelah gaji dibayar." (atau "…setelah penggajian disahkan." bila
  pengaturan PT `disahkan` — nilai dikirim di jawaban sebagai `visible_since`).
- Tidak ada angka karyawan lain, tidak ada tanggungan perusahaan selain yang sudah tercetak di PDF.

## Uji penerimaan

Fixture di `ent_kanda` (BPJS dimatikan untuk PT itu): karyawan E1 tertaut akun `e1`, gaji pokok 8.000.000, tunjangan
Transport 500.000 dan Makan 300.000, TK0; proses reguler 2026-10. Dari PY-T1: `gross` 8.800.000, `pph21` 154.000
(8.800.000 × 1,75 % menurut aturan bawaan pada `3132cc4`), `net` 8.646.000. Karyawan E2 tertaut akun `e2`.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | Proses `approved`; pengaturan bawaan | `e1`: `GET /api/hr/payslips/me` | `payslips` kosong; `visible_since` `dibayar` |
| U2 | B | Proses `posted` lalu `paid` | `e1`: `GET …/me` setelah tiap langkah | Kosong saat `posted`; setelah `paid`: satu slip, `net` 8.646.000, `components` memuat "Tunjangan — Transport" 500.000; `years` `[2026]` |
| U3 | B | Proses `approved`; `hr.slip_swalayan_sejak = disahkan` untuk `ent_kanda` | `e1`: `GET …/me`; karyawan `ent_ksc` dengan proses `approved`: sama | `e1` melihat satu slip; karyawan `ent_ksc` tidak (PT lain tidak ikut) |
| U4 | B | Proses `draft` | `e1`: `GET /api/hr/payslips/{id slip sendiri}` dan `…/pdf`; pemegang `hr.view`: sama | 404 "Slip gaji ini belum terbit." dua kali; pemegang `hr.view` 200 |
| U5 | B | U2 | `e2`: `GET /api/hr/payslips/{id slip E1}` | 403 |
| U6 | B | Proses `posted` di-void (PK-22); proses lain `cancelled` | `e1`: `GET …/me` dengan pengaturan `disahkan` | Keduanya tidak muncul |
| U7 | B | U2; proses THR 2026-10 `paid` (bersih 7.314.000, contoh PY-T1) | `e1`: `GET …/me?year=2026`; `?year=2025` | Dua slip Oktober ber-`run_type` `regular` dan `thr`; tahun 2025 kosong |
| U8 | B | Akun tanpa karyawan tertaut | `GET …/me` | 200 `{employee: null, years: [], payslips: []}` |
| U9 | B | U2 | `e1`: `GET …/{id}/pdf` | 200 `application/pdf` |
| U10 | B | Kunci baru | Putaran `t1_config.py`; nilai "diposting" | Lulus; 400 |
| U11 | layar (uji komponen) | Jawaban U7 | Render kartu; buka baris reguler | Dua baris riwayat berlabel "Reguler" dan "THR"; rincian memuat "Gaji Pokok", "Tunjangan — Transport", "PPh 21", "Gaji bersih" Rp 8.646.000 |
| U12 | layar (uji komponen) | Permintaan gagal (500) | Render kartu | Teks "Slip belum bisa dimuat. Coba lagi." |
| U13 | layar (uji jalan) | U2, login `e1` | Buka Profil Saya | Kartu "Slip Gaji Saya" menampilkan Oktober 2026; PDF terbuka; sebelum dibayar kartu menulis "Belum ada slip gaji yang terbit." |

## Langkah kerja

1. `backend/tests_mem/test_PYT5_swalayan_slip.py`: U1–U10 (merah: U1, U2, U4, U6 gagal karena slip terlihat terlalu dini).
2. Kunci pengaturan; `slip_visible_to_owner`; `my_payslips` dan dua endpoint ber-id.
3. Kartu "Slip Gaji Saya": riwayat, rincian komponen, keadaan galat; uji komponen U11, U12.
4. Uji jalan U13; gate.

## Dokumen ikut berubah

`memory/PRD.md`; `CODEBASE_MAP.md` (kartu berganti isi); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("slip terbit").

## Di luar lingkup

- Kartu "Capaian & Insentif Saya" di Profil Saya → KM-T5 (dipasang di bawah kartu slip).
- Pemberitahuan "slip sudah terbit", unduh banyak slip sekaligus, dan bukti potong pajak tidak dibangun.
- Isi dan bentuk PDF slip → PY-T1. Slip di kartu karyawan untuk HR (`Employee360Panel.jsx`) tidak diubah.

## Asumsi dan risiko

- `ASUMSI:` bawaan `dibayar` mengikuti rancangan yang disetujui pemilik secara garis besar dan judul unit ini, walau
  perilaku hari ini menampilkan slip sejak disahkan; pilihan `disahkan` mengembalikan perilaku lama per PT.
- `ASUMSI:` slip draf, diajukan, dibatalkan, dan di-void tertutup bagi pemiliknya tanpa sakelar, karena angkanya belum
  atau tidak lagi sah.
- `RISIKO:` karyawan yang terbiasa melihat slip lebih awal menganggap slipnya hilang. Penangkal: teks kosong
  menjelaskan kapan slip muncul. Membatalkan: setel `hr.slip_swalayan_sejak` global ke `disahkan`.

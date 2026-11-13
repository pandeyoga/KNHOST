# PY-T1 — Jadikan slip gaji daftar komponen per PT, dengan antrean masukan dan jenis proses gaji

| | |
|---|---|
| Gelombang | Modul — Penggajian |
| Jenis | fitur |
| Risiko | tinggi |
| Prasyarat | PK-22 |
| Menutup temuan | PY-01, PY-02, PY-13, PY-14 |
| Keputusan | K-37, K-40 (K-41 sudah dipasang PK-22) |
| Standar | §1 (P1, P3, P4, P9), §3.1 (Z1, Z2), §3.4 (N1, N4, N5), §4 (L1–L5, L7), §5 (D1, D3, D5, D7, D8, D9), §6 |
| Lingkungan uji | keduanya (B untuk alur dan angka; A untuk indeks unik dan data acuan) |

## Tujuan

Slip gaji bisa memuat berapa pun komponen (beberapa baris insentif, THR, potongan), tiap PT punya daftar komponennya
sendiri, angka dari modul lain masuk lewat satu antrean berstatus, dan dalam satu bulan bisa ada proses reguler, THR,
dan susulan. Kolom lama slip tetap terisi sebagai jumlah, sehingga jurnal, PDF, ekspor, dan rekap pajak yang ada tidak
berubah angkanya.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`. PK-22 (prasyarat) sudah menambah hitung ulang, batal, void, izin `payroll.*`,
dan kunci jurnal gaji = id proses; cek hasilnya di laporan PK-22 saat langkah "cek ulang".

- Slip berkolom tetap: `backend/services/hr_payroll_service.py:302` (`base_salary`). Tunjangan dijumlah menjadi satu
  angka dan namanya hilang: `backend/services/hr_payroll_service.py:110` (`_sum_allowances`); bentuk di master:
  `backend/schemas_hr.py:21` (`AllowanceInput`). Komisi satu angka dari mesin: `backend/services/hr_payroll_service.py:245`
  (`_commission_for`).
- Satu proses per PT per periode; permintaan kedua mengembalikan proses pertama:
  `backend/services/hr_payroll_service.py:362` (`existing_run`), `backend/services/hr_payroll_service.py:370`
  (`create_run`). Penjaga kembarnya membaca-lalu-menghapus, bukan indeks: `backend/services/hr_payroll_service.py:392`
  (`dup`). Kunci jurnal lama PT+periode: `backend/services/gl_service.py:3042` (`src_id`), dan untuk bayar
  `backend/services/gl_service.py:3109` (`src_id`).
- PPh 21 dihitung dari bruto slip itu saja: `backend/services/hr_payroll_service.py:281` (`ter_rate`); slip lain di
  bulan yang sama tidak dilihat, `backend/services/hr_payroll_service.py:231` (`_prior_year_slips`).
- Format periode tidak divalidasi: `backend/schemas_hr_payroll.py:8` (`period`).
- Pembaca kolom lama yang harus tetap benar:

| Pembaca | Kolom yang dibaca | Jangkar |
|---|---|---|
| Jurnal gaji | `salary_earnings`, `commission`, `bpjs_er_total`, `bpjs_emp_total`, `pph21`, `net` | `backend/services/gl_service.py:3049` (`salary_earnings`) |
| Total proses | sama, dijumlah ke `totals` | `backend/services/hr_payroll_service.py:320` (`_accumulate`) |
| PDF slip | baris tetap; persen BPJS ditulis mati; "TER 0,00 %" pada masa terakhir | `backend/services/hr_payroll_pdf.py:72` (`base_salary`), `backend/services/hr_payroll_pdf.py:83` (`BPJS Kesehatan`) |
| Ekspor data | `base_salary`, `overtime`, `commission` | `backend/services/export_registry_more.py:268` (`hr_payslips`) |
| Rekap PPh 21 | `totals.gross`, `totals.pph21` semua proses periode itu | `backend/services/tax_center_service.py:49` (`_period_pph21`) |
| Analitik SDM | `totals` | `backend/services/hr_analytics_service.py:28` (`PAY_KEYS`) |
| Profil karyawan | daftar slip, kolom disamarkan | `backend/routers/hr.py:372` (`_PAY_PII`) |
| Layar | kolom Pokok · Tunj. · Lembur · Komisi | `frontend/src/features/hr/PayrollRunsView.jsx:204` (`Komisi`), `frontend/src/features/hr/PayslipsView.jsx:98` (`DRow`) |

- PY-14: label "Payroll Run", `frontend/src/config/hubTabs.js:196` (`hr-payroll-runs`); teks konfirmasi menyebut
  "pengembalian ke draf" untuk gaji yang sudah disahkan, `frontend/src/features/hr/PayrollRunsView.jsx:66` (`approve`);
  jam absen bisa diubah tanpa menghitung ulang lembur, `backend/routers/hr_attendance.py:429` (`patch_attendance`),
  padahal penghitungnya ada: `backend/services/hr_attendance_service.py:76` (`compute_metrics`).
- Tab "Slip Gaji" menampilkan tabel yang sama dengan detail proses: `frontend/src/config/hubTabs.js:197` (`hr-payslips`).

## Perubahan

### Data

**`hr_pay_components` (baru, per PT).** Indeks unik (`entity_id`, `code`).

| Field | Tipe | Arti |
|---|---|---|
| `id`, `entity_id`, `code`, `name` | teks | `pcomp_…`; kode huruf besar; nama tampil di slip |
| `kind` | `pendapatan` · `potongan` · `tanggungan_perusahaan` | Jenis |
| `calc` | `tetap_bulanan` · `per_jam` · `masukan` · `undang_undang` | Cara hitung. `per_hari_hadir` dan `persen_dasar` ditambahkan PY-T3 |
| `bucket` | `base_salary` · `allowances` · `overtime` · `commission` · `other_earnings` · `bpjs_emp` · `bpjs_er` · `pph21` · `other_deductions` | Kolom lama tempat komponen ini dijumlahkan |
| `taxable`, `in_bpjs_base`, `in_overtime_base`, `prorate` | ya/tidak | Tiga terakhir disimpan dan ditandai "belum dipakai" di layar sampai PY-T3 |
| `statutory_code` | teks | Untuk `undang_undang`: `bpjs_kes_emp`, `bpjs_jht_emp`, `bpjs_jp_emp`, `bpjs_kes_er`, `bpjs_jht_er`, `bpjs_jp_er`, `bpjs_jkk_er`, `bpjs_jkm_er`, `pph21` |
| `account_code` | teks | Wajib untuk `potongan` selain `undang_undang` (akun yang dikredit); opsional untuk `pendapatan` (kosong = akun bawaan kolomnya) |
| `allowed_run_types` | daftar | Jenis proses yang memuatnya |
| `sort`, `is_active`, `system` | — | Komponen `system` tidak bisa dihapus atau diganti jenisnya |

Isi awal tiap PT (idempoten, saat server menyala): `GAJI_POKOK` (pendapatan, tetap, `base_salary`, dasar BPJS dan lembur
ya), `TUNJANGAN` (pendapatan, tetap, `allowances`), `LEMBUR` (per jam, `overtime`), `KOMISI` (masukan dari mesin komisi,
`commission`), tiga potongan BPJS karyawan, lima tanggungan BPJS perusahaan, `PPH21`, dan `THR` (pendapatan, masukan,
`other_earnings`, hanya jenis proses `thr`). Semua `taxable` kecuali potongan dan tanggungan. Dengan isi awal ini angka
slip sama persis dengan hari ini.

**`hr_pay_inputs` (baru) — antrean masukan komponen.**

| Field | Tipe | Arti |
|---|---|---|
| `id`, `entity_id`, `employee_id`, `pay_period` | teks, `YYYY-MM` | `pinp_…`; proses gaji PT dan bulan mana yang dituju |
| `component_code`, `label`, `basis_period` | teks | Komponen (harus `masukan` dan aktif di PT itu); teks baris di slip; periode dasar bila ada |
| `amount` | rupiah bulat ≠ 0 | Boleh negatif (penyesuaian) |
| `source_type`, `source_key`, `source_ref` | teks, teks, `{type, id, number, …}` | `incentive_sheet` · `overtime` · `cash_advance` · `rapel` · `manual`; kunci unik per baris sumber |
| `status` | `pending` · `approved` · `used` · `cancelled` | `pending` hanya untuk isian manual yang belum disahkan |
| `reason`, `created_by`, `approved_by`, `approved_at`, `used_run_id`, `used_at`, `cancelled_by`, `cancel_reason` | — | Jejak; `reason` wajib untuk `manual` |

Indeks: unik `source_key`; (`entity_id`, `pay_period`, `status`); (`used_run_id`).

**`hr_payroll_runs` (ditambah):** `run_type` (`regular` · `thr` · `susulan`; proses lama dibaca `regular`), `seq` (urutan
per PT, periode, jenis), `active_key` = `<entity_id>:<period>:regular`, diisi hanya untuk proses reguler yang tidak
`cancelled`/`void`, berindeks unik parsial (menggantikan penjaga baca-lalu-hapus). THR dan susulan tidak dibatasi.

**`hr_payslips` (ditambah):** `run_type`; `components[]` = `{code, name, label, kind, bucket, amount, taxable, qty?,
rate?, basis_period?, source?: {type, key, id, number}}`; `other_earnings`, `other_deductions`; `pph21_month` (rincian
gabungan bulan itu). Kolom lama diisi dari komponen: tiap kolom = Σ `amount` komponen ber-`bucket` itu;
`salary_earnings = base_salary + allowances + overtime + other_earnings`; `gross = salary_earnings + commission`;
`net = gross − bpjs_emp_total − pph21 − other_deductions`. Slip lama tanpa `components` tetap dibaca dari kolomnya.

### Server

Berkas baru `backend/services/hr_pay_components.py` (isi awal, validasi, pembangun `components[]`) dan berkas baru
`backend/services/hr_pay_inputs.py`:

```python
async def enqueue_input(*, entity_id, employee_id, pay_period, component_code, label, amount, source_type,
                        source_key, source_ref, basis_period="", actor) -> dict   # status approved; kunci sama → dokumen yang sama
async def cancel_input(source_key, *, actor, reason) -> dict                      # hanya dari approved; used → 409
async def take_for_run(entity_id, pay_period, run_type, run_id) -> list           # approved → used, bersyarat status lama
async def release_for_run(run_id) -> int                                          # used → approved; dipanggil batal, void, hitung ulang
```

Aturan proses:

| Jenis | Karyawan | Komponen | Syarat |
|---|---|---|---|
| `regular` | Semua yang digaji periode itu | Semua komponen aktif ber-`regular`, plus masukan `approved` untuk `pay_period` itu | Satu per PT per periode; permintaan kedua tetap mengembalikan proses yang ada |
| `thr` | Yang punya masukan THR | Komponen ber-`thr` + `PPH21` | 400 bila tidak ada masukan |
| `susulan` | Yang punya masukan belum terpakai | Komponen `masukan` + `PPH21` | 400 bila tidak ada masukan |

- `preview_run` tidak menandai masukan; `create_run` dan hitung ulang (PK-22) memanggil `take_for_run`; hitung ulang,
  batal, dan void memanggil `release_for_run` lebih dulu.
- PPh 21 gabungan bulan: untuk slip di proses R, `bruto pajak bulan` = bruto pajak slip ini + Σ bruto pajak slip
  karyawan yang sama pada proses lain periode itu yang tidak `cancelled`/`void` dan dibuat lebih dulu;
  `pph21_month = bruto pajak bulan × tarif(kategori, bruto pajak bulan)`; `pph21` slip ini = `pph21_month` − Σ `pph21`
  slip terdahulu bulan itu. Hitung ulang masa terakhir ikut memuat slip terdahulu bulan itu. Tarif tetap dari tabel yang
  berlaku (PK-46); unit ini tidak mengubah isinya.
- Jurnal gaji dibangun dari komponen dengan akun dan arah yang sudah ada: pendapatan → Dr `ACC_BEBAN_GAJI` (atau
  `account_code` komponen); kolom `commission` → seperti sekarang menurut `commission_mode` proses; tanggungan
  perusahaan → Dr `ACC_BEBAN_BPJS`; BPJS → Cr `ACC_HUTANG_BPJS`; PPh 21 → Cr/Dr `ACC_HUTANG_PPH21`; potongan lain → Cr
  `account_code` komponennya; bersih → Cr `ACC_HUTANG_GAJI`. Kunci jurnal posting dan bayar = id proses (bila PK-22 belum
  mengganti kunci jurnal bayar, ganti di sini dengan cara yang sama; proses lama dikenali dari `paid_journal_id`).
- PDF: fungsi murni baru `payslip_pdf_rows(slip) -> list[tuple[bagian, label, nilai]]` dipakai `payslip_pdf_bytes`;
  satu baris per komponen; persen BPJS dari `rate` komponen di slip; masa terakhir berlabel "PPh 21 (hitung ulang
  tahunan)"; judul bagian "PENERIMAAN", "POTONGAN", "GAJI BERSIH DITERIMA", "TANGGUNGAN PERUSAHAAN (INFORMASI)".
- `patch_attendance`: bila `clock_in`/`clock_out` berubah, hitung ulang `work_min`, `late_min`, `early_leave_min`,
  `overtime_min` dengan `compute_metrics`.

| Endpoint | Izin | Isi | Jawaban dan galat |
|---|---|---|---|
| `GET /api/hr/payroll/components` | `hr.view` | — | Daftar komponen PT aktif |
| `POST`, `PATCH /api/hr/payroll/components[/{id}]` | `hr.manage_payroll` | Field komponen | 409 "Kode komponen sudah dipakai di PT ini." · 400 "Komponen potongan wajib punya akun." · 400 "Komponen bawaan tidak bisa diubah jenisnya." |
| `GET /api/hr/payroll/inputs` | `hr.view` | `pay_period?`, `status?`, `employee_id?`, `page` | `{items, total}` |
| `POST /api/hr/payroll/inputs` | `payroll.create` | `{employee_id, component_code, pay_period, amount, label, reason}` | Masukan `pending`. 400 "Komponen {kode} bukan komponen masukan." · 400 "Alasan wajib diisi." |
| `POST …/inputs/{id}/approve` | `payroll.approve` | — | `approved` |
| `POST …/inputs/{id}/cancel` | `payroll.approve` | `{reason}` | `cancelled`. 409 "Masukan ini sudah dipakai di penggajian {nomor}, jadi tidak bisa dibatalkan." |
| `POST /api/hr/payroll/runs` (diubah) | `payroll.create` | `{period, run_type?}` | 400 "Periode harus berbentuk TTTT-BB, mis. 2026-10." · 400 "Tidak ada masukan THR yang disahkan untuk {bulan tahun}." · 400 "Tidak ada masukan yang belum terpakai untuk {bulan tahun}." |

### Pengaturan

Tidak ada kunci baru.

### Izin dan peran

Tidak ada pasangan izin baru; memakai `hr.view`, `hr.manage_payroll`, dan `payroll.create`/`payroll.approve` dari PK-22.
Modul akses `hr`: `nav` ditambah `hr-pay-components`.

### Layar

Hub Penggajian:

- Tab "Payroll Run" berganti label **Proses Gaji** (view tetap `hr-payroll-runs`). Form buat mendapat "Jenis proses"
  (Reguler · THR · Susulan). Tabel slip di detail proses: "Karyawan", "Pendapatan", "Potongan", "PPh 21", "Gaji bersih";
  baris bisa dibuka menjadi daftar komponen (label dan nominal, dikelompokkan Pendapatan · Potongan · Tanggungan
  perusahaan). Kotak "Cari slip" (nama atau periode) menggantikan tab Slip Gaji; tab `hr-payslips` dihapus dari
  `HUB_TABS` dan view-nya dijadikan alias ke Proses Gaji di `viewAliases.js`.
- Teks konfirmasi sahkan: "Setelah disahkan, penggajian ini tidak bisa diubah. Bila ada koreksi, batalkan lalu hitung
  lagi." Teks kembalikan: "Penggajian kembali menjadi draf dan bisa dihitung ulang. Alasannya tersimpan di dokumen."
- Tab baru **Komponen & Masukan** (view `hr-pay-components`; komponen baru
  `frontend/src/features/hr/PayComponentsView.jsx`). Bagian **Komponen gaji**: "Kode", "Nama", "Jenis", "Cara hitung",
  "Kena pajak", "Dasar BPJS", "Dasar lembur", "Diprorata", "Akun", "Aktif"; tombol "Tambah komponen". Bagian
  **Masukan**: saringan "Periode bayar" dan "Status" (Menunggu disahkan · Disahkan · Terpakai · Dibatalkan); kolom
  "Karyawan", "Komponen", "Keterangan", "Periode dasar", "Nominal", "Sumber", "Status", "Dipakai di"; tombol "Tambah
  masukan" (pop-up baku: Karyawan, Komponen, Periode bayar, Nominal, Keterangan, Alasan), "Sahkan", "Batalkan" (minta
  alasan). Kosong: "Belum ada masukan untuk periode ini."
- `PayslipsView.jsx` (dipakai panel cari slip) menampilkan daftar komponen, bukan empat baris tetap.

## Uji penerimaan

Fixture di `ent_kanda`, BPJS dimatikan untuk PT itu (`hr.feature_toggles.bpjs_kesehatan` dan `…bpjs_ketenagakerjaan`
tidak), sehingga bruto pajak = bruto. E1: gaji pokok 8.000.000, tunjangan Transport 500.000 dan Makan 300.000, TK0.
E2: gaji pokok 5.000.000, TK0. Persen pajak di bawah berasal dari tabel kategori A pada `3132cc4`; tes mengambil
tarifnya lewat `ter_rate` supaya tetap benar bila PK-46 mengganti tabel, dan menuliskan hitungan ini sebagai komentar.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | Proses reguler 2026-10 | E1 `components`: Gaji Pokok 8.000.000; "Tunjangan — Transport" 500.000; "Tunjangan — Makan" 300.000; PPh 21 154.000 (8.800.000 × 1,75 %). Kolom lama: `base_salary` 8.000.000, `allowances` 800.000, `gross` 8.800.000, `net` 8.646.000. E2: `pph21` 0, `net` 5.000.000 |
| U2 | A | Data acuan | Hitung ulang tiap proses draf; bandingkan dengan slip sebelum unit ini | Untuk tiap slip: Σ komponen pendapatan = `gross` lama; `net` sama; selisih 0 |
| U3 | B | Komponen `BONUS` (pendapatan, masukan, `other_earnings`); dua masukan `approved` E1 untuk 2026-11: 2.000.000 "Bonus A" dan 3.000.000 "Bonus B" | Proses reguler 2026-11 | Slip E1 memuat dua baris berlabel itu; `other_earnings` 5.000.000; `gross` 13.800.000; `pph21` 621.000 (× 4,5 %); `net` 13.179.000; kedua masukan `used` ber-`used_run_id` |
| U4 | B | U1 sudah ada; masukan THR E1 8.000.000 untuk 2026-10 | Proses `thr` 2026-10 | Proses baru (id lain), `seq` 1; slip: THR 8.000.000; `pph21_month` 840.000 (16.800.000 × 5 %); `pph21` 686.000 (840.000 − 154.000); `net` 7.314.000 |
| U5 | B | U4 disahkan | Posting | Jurnal ber-`source_id` = id proses THR: Dr 6-1000 8.000.000 / Cr 2-1600 7.314.000, Cr 2-1800 686.000; jurnal proses reguler tetap satu |
| U6 | B | U3 diposting | Void (PK-22) | Dua masukan kembali `approved`, `used_run_id` kosong |
| U7 | B | Proses draf 2026-12; lalu masukan baru disahkan; lalu masukan itu dibatalkan | Hitung ulang dua kali | Setelah pertama: baris baru muncul; setelah kedua: hilang; total proses mengikuti |
| U8 | B | Masukan manual dibuat pemegang `payroll.create` | Buat proses; sahkan masukan; hitung ulang; batalkan masukan | `pending` tidak ikut; setelah disahkan ikut; batal → 409 "…sudah dipakai…" |
| U9 | B | — | `enqueue_input` dua kali dengan `source_key` sama | Satu dokumen; nominal tidak dobel |
| U10 | B | Komponen `POT_UJI` (potongan, masukan, `account_code` 1-1400); masukan E2 500.000 untuk 2026-11 | Proses, sahkan, posting | E2: `other_deductions` 500.000, `net` 4.500.000; jurnal memuat Cr 1-1400 500.000; Σ debit = Σ kredit. Membuat komponen potongan tanpa akun → 400 |
| U11 | B | — | `POST` proses dengan `period` "2026-13" dan "Okt" | 400 dengan pesan periode |
| U12 | B | Slip U1 | `payslip_pdf_rows(slip)` | Memuat ("PENERIMAAN", "Tunjangan — Transport", 500000); tidak ada label berisi "(1%)" |
| U13 | B | U1 dan U4 diposting | Rekap PPh 21 periode 2026-10 | `dpp` 21.800.000 (8.800.000 + 5.000.000 + 8.000.000); `amount` 840.000 (154.000 + 0 + 686.000) |
| U14 | B, A | U1 | `POST` reguler 2026-10 lagi; di A dua `POST` bersamaan | Id proses yang sama; di A tepat satu proses reguler |
| U15 | B | Absen dengan shift 08.00–17.00, pulang 19.00 | `PATCH` `clock_out` menjadi 18.00 | `overtime_min` dari 120 menjadi 60 |
| U16 | B | Peran Tanpa Acuan ber-`payroll.create` | Buat masukan; sahkan masukan | 200; 403 |
| U17 | layar (uji jalan) | U3 | Buka Proses Gaji → detail → buka baris E1 | Dua baris bonus tampil terpisah; tab berlabel "Proses Gaji"; tab Slip Gaji tidak ada |

## Langkah kerja

**Serah-terima (a) — jalur baru di samping jalur lama.**
1. `backend/tests_mem/test_PYT1_komponen_gaji.py`: U1, U3–U13, U16; `backend/tests/test_bp_PYT1_data_acuan.py`: U2, U14.
2. Koleksi komponen + isi awal + endpoint + tab Komponen & Masukan; antrean dan empat fungsinya.
3. Pembangun `components[]` sebagai fungsi murni yang dipanggil `compute_payslip` **tanpa** mengubah kolom lama; tes
   membuktikan Σ komponen = kolom lama (U1, U2). Gate; catat SHA.

**Serah-terima (b) — pengalihan.**
4. Kolom lama diturunkan dari komponen; masukan ikut proses; jenis proses, `active_key`, PPh 21 gabungan bulan.
5. Jurnal dari komponen; PDF dari komponen; layar Proses Gaji, penghapusan tab Slip Gaji (cari pemakai `hr-payslips`
   dulu), teks; perbaikan `patch_attendance`.
6. Gate penuh; laporan memuat contoh U4–U5 (slip → jurnal → saldo 2-1600 dan 2-1800).

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (dua koleksi, field baru proses dan slip); `CODEBASE_MAP.md`; `memory/PRD.md`;
`docs/KN_13_NAVIGATION_MAP.md` (tab Penggajian); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("proses gaji", "komponen
gaji", "masukan"); `scripts/verify_contract.py`.

## Di luar lingkup

- Hitung ulang, batal, void, izin terpisah, setoran kewajiban, tanggal jurnal → PK-22 (sudah).
- Riwayat kompensasi dan komponen tetap per karyawan → PY-T2. Prorata, potongan absen, lembur dari pengaturan, dasar
  BPJS dan lembur dari tanda komponen → PY-T3. Tabel tarif → PK-46 (H4). Usulan THR dari masa kerja tidak dibangun:
  masukan THR diisi lewat antrean (manual).
- Masukan dari Lembar Insentif dan mematikan komisi otomatis → KM-T4. Sambungan otomatis dari uang muka karyawan
  (K-40) dan lembur terlambat: antreannya siap, pengisinya tidak dibangun di sini; sementara lewat isian manual.
- Bayar dengan rekening dan daftar transfer → PY-T4. Slip di swalayan → PY-T5. Rekap pajak pindah tab → MN-T2.

## Asumsi dan risiko

- `ASUMSI:` permintaan kedua untuk proses reguler tetap mengembalikan proses yang ada (perilaku hari ini), bukan galat.
- `ASUMSI:` proses THR dan susulan tidak menghitung BPJS; iuran BPJS hanya di proses reguler.
- `ASUMSI:` tunjangan di master karyawan semuanya masuk komponen `TUNJANGAN` dengan label namanya sampai PY-T2.
- `ASUMSI:` akun kredit komponen potongan dipilih pengguna dari akun aktif; unit ini tidak menetapkan akun kasbon.
- `RISIKO:` angka slip bergeser saat pengalihan. Penangkal: U2 di data acuan sebelum langkah 4 digabung. Membatalkan
  (b): kembalikan `compute_payslip` ke hitungan kolom; `components[]` dan antrean tidak dibaca kode lama.

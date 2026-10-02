# IMPLEMENTATION

Commit sumber yang diuji: patch di atas `5cddfc964ee0b1b84729d13d01a789d31f31bb7d` (P10 dan P11 sudah termasuk). SHA kandidat diisi setelah commit platform.
ID/fase: P12, yaitu HR-01, HR-02, HR-03, IX-01, IX-03, IX-04, MK-01.

Reproduksi HEAD: worktree `5cddfc9` → `cd .head_wt/backend && python <repo>/audit/iterations/2026-10-02-P12-payroll-hr-marketing/repro_p12.py` → [head_before_patch.txt](head_before_patch.txt) `pass=4 fail=18`. Rinciannya:
- Lembur kasus acuan: 9.000 (acuan 3.500).
- Absensi flagged ikut dibayar.
- Shift 22–06: std −960 dengan lembur 1.440.
- Desember dan bulan berhenti tetap memakai TER.
- Override jatah 0 kembali ke 12, dan jatah −1 diterima.
- Dua cuti 10 hari diterima dengan jatah 12, tanggal yang bertabrakan diterima, cuti lintas tahun crash.
- Metrik parsial menghapus metrik lama.

Yang sudah benar di HEAD: TER pada masa biasa, shift siang, approved ≤ jatah untuk satu pengajuan, dan nilai 0 eksplisit pada metrik.

Angka acuan dihitung tangan dari PP 35/2021 ps.31, PMK 168/2023 (TER kategori A), UU HPP ps.17, dan PTKP PMK 101/2016. Repro tidak memanggil fungsi aplikasi untuk menghitung angka acuan. **Fixture pajak wajib divalidasi akuntan.**

## Perubahan

- **HR-02 / IX-04 (`services/hr_payroll_service.py`)**
  - `overtime_events`: satu event per tanggal.
  - Pengajuan formal yang approved mengesahkan tanggal itu dan menggantikan usulan dari absensi.
  - Absensi hanya dihitung bila `approved=true` dan bukan `method=leave`.
  - Duplikat pengajuan pada tanggal yang sama diambil satu.
  - `overtime_hour_units` tier PP 35/2021:
    - Hari kerja: jam pertama 1,5×, jam berikutnya 2×.
    - Hari istirahat/libur, 5 hari kerja: 2× sampai jam ke-8, 3× jam ke-9, 4× jam ke-10–11.
    - Hari istirahat/libur, 6 hari kerja: 2× sampai jam ke-7, 3× jam ke-8, 4× jam ke-9–10.
  - Jenis hari ditentukan dari `rate_basis` (weekend/holiday), `overtime.holidays`, dan `overtime.work_days_per_week`.
  - Mode lama tetap tersedia bila dipilih eksplisit lewat `overtime.mode="flat"`.
  - Slip menyimpan `overtime_events` (tanggal, sumber, ref_id, menit, jenis hari, satuan jam, nilai).
- **HR-01 (payroll + `gl_service.post_payroll_run`)**
  - `tax_gross` = bruto + premi JKK, JKM, dan BPJS Kesehatan yang dibayar pemberi kerja. Dasar ini dipakai untuk TER dan perhitungan tahunan.
  - Masa terakhir = Desember, atau bulan `end_date`/`resign_date`. Di masa itu dihitung PPh setahun Pasal 17 atas penghasilan aktual setahun/bagian tahun:
    - Dikurangi biaya jabatan 5% (maks 500 rb × bulan), JHT+JP karyawan, dan PTKP setahun.
    - PKP dibulatkan ke ribuan ke bawah.
    - Hasilnya dikurangi PPh yang sudah dipotong pada slip tahun itu (run void/cancelled/rejected tidak dihitung).
  - Lebih potong menjadi pph21 negatif. Net bertambah, dan jurnal payroll mendebit Hutang PPh 21 supaya tetap seimbang.
  - Karyawan `resigned`/`inactive` yang `end_date`-nya jatuh di periode itu ikut payroll.
  - Rincian tersimpan di `pph21_method` dan `pph21_annual`.
- **IX-03 (`services/hr_attendance_service.py`)**
  - Jam keluar ≤ jam masuk berarti shift lintas tengah malam: std ditambah 1.440.
  - Awal shift bertanggal = kandidat (kemarin/hari ini/besok) yang paling dekat dengan clock-in.
  - Pulang awal dihitung dari akhir shift bertanggal.
  - Clock-out ≤ clock-in → tanpa kerja dan tanpa lembur.
- **IX-01 / HR-03 (`services/hr_leave_service.py`)**
  - Override jatah 0 dipertahankan. `set_entitlement` wajib bilangan bulat ≥ 0.
  - Terpakai/pending dibebankan per tahun dari `work_dates`.
  - Submit: tanggal yang bertabrakan dengan cuti pending/approved ditolak. Reservasi per tahun memakai CAS `$inc pending` dengan syarat jatah − terpakai − pending ≥ n.
  - Approve: cek ulang (approved lain + n ≤ jatah) plus CAS status. Approve paralel yang melewati jatah dikembalikan ke pending.
  - Reject/cancel memakai CAS status.
  - Absensi cuti menyimpan `leave_request_id`. Cancel hanya menghapus milik request itu (legacy dicocokkan lewat nomor di catatan).
- **MK-01 (`services/marketing_service.py`)**
  - `record_metrics` menulis `$set metrics.<field>` per field yang dikirim, plus `metrics_version`.
  - Riwayat menyimpan `patch_fields` dan `snapshot` lengkap.

## Regression

- `repro_p12.py` → [after_patch.txt](after_patch.txt): `pass=23 fail=0`.

## Batas / keputusan pemilik

- HR-01: belum mencakup pegawai tidak tetap/harian (TER harian), DTP, bonus/THR terpisah, dan karyawan pindah pemberi kerja (bukti potong A1 sebelumnya). Belum ada tampilan khusus "lebih potong" di slip PDF (nilai tampil sebagai PPh21 negatif).
- HR-02: basis upah lembur tetap gaji pokok. Bila tunjangan tetap wajib ikut (ps.32 PP 35/2021: upah sebulan), perlu keputusan dan migrasi konfigurasi. Simulator konfigurasi (`config_simulator._payroll_overtime`) masih memakai pengali tunggal.
- IX-03: jam istirahat belum dipisah, dan validasi shift nol/terlalu panjang belum ditambahkan pada form shift.
- IX-04: slip yang sudah dibuat tidak dihitung ulang. Koreksi persetujuan sesudah posting lewat adjustment belum dibuat.
- HR-03: kalender libur nasional belum dipakai (hari kerja = Senin–Jumat). Reservasi pending bisa sesaat terlampaui saat recompute bersamaan, tetapi approve selalu mengecek ulang.
- Konkurensi diuji in-process (asyncio.gather).

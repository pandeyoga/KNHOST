# PY-T4 — Bayar gaji dari rekening berperuntukan Gaji dengan daftar transfer per karyawan; Finance bisa membayar dan menyetor

| | |
|---|---|
| Gelombang | Modul — Penggajian |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | PY-T1, PM-T1 |
| Menutup temuan | PY-11 |
| Keputusan | K-41 (izin bayar terpisah; pemegang bawaan), K-34 (rekening = data master) |
| Standar | §1 (P1, P2, P3, P5), §3.1 (Z1, Z2, Z6), §3.2, §3.4 (N1, N2, N4, N5), §4 (L1–L4, L7, L8), §5 (D4, D5), §6 |
| Lingkungan uji | keduanya (B untuk alur; A untuk dua pembayaran bersamaan dan uji jalan layar) |

## Tujuan

Pembayar gaji memilih rekening sumber dari rekening PT yang ditandai untuk gaji, melihat dan mengunduh daftar transfer
per karyawan yang jumlahnya sama dengan total gaji bersih dan kas keluar, dan — bila ia orang Finance — bisa membayar
gaji serta menyetor BPJS dan PPh 21 tanpa membuka data karyawan lainnya. Setoran yang salah catat bisa dibatalkan.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`. PK-22, PK-20, PM-T1, dan PY-T1 (terdahulu) sudah mengubah sebagian; cek ulang di
laporannya: izin `payroll.pay`, isian `account_id` pada bayar gaji, `create_cash`, field `purposes` rekening, dokumen
setoran `hr_statutory_remittances`.

- Layar mengirim permintaan bayar tanpa isi, sehingga selalu memakai akun bawaan:
  `frontend/src/features/hr/PayrollRunsView.jsx:88` (`pay`); bawaan itu `backend/services/gl_service.py:3118`
  (`ACC_KAS_BESAR`). Isi permintaan hanya mengenal kode akun: `backend/schemas_hr_payroll.py:11` (`PayRunInput`).
- Akun bayar dibatasi anak akun kas/bank, tanpa rekening: `backend/services/gl_service.py:3123` (`parent_code`).
  Pembayaran menjadi satu jurnal dan satu mutasi kas sebesar total bersih:
  `backend/services/hr_payroll_service.py:562` (`record_return_cash`), bertanggal saat tombol ditekan,
  `backend/services/gl_service.py:3128` (`now_iso`).
- Tidak ada daftar transfer. Rekening karyawan sudah dipotret di slip saat dihitung:
  `backend/services/hr_payroll_service.py:310` (`bank`).
- Semua langkah gaji memakai satu izin yang hanya dipegang Admin dan Manajer:
  `backend/routers/hr_payroll.py:199` (`manage_payroll`); peran Finance tidak punya izin SDM sama sekali,
  `backend/permissions_config.py:346` (`finance`), dan hub Penggajian hanya untuk dua peran itu:
  `frontend/src/config/hubTabs.js:195` (`hr-payroll-hub`).
- Rekening tunggal PT dicari dengan saringan `status`, bukan peruntukan: `backend/services/bank_service.py:55`
  (`bank_accounts`).

## Perubahan

### Data

- `hr_payroll_runs` (ditambah): `pay_account_id`, `paid_date` (`YYYY-MM-DD`), `transfer_total`, `transfer_count`,
  `paid_by_id`. Tanpa migrasi; proses lama yang sudah dibayar tidak diisi.
- `hr_statutory_remittances` (lahir di PK-22): `status` mendapat nilai `voiding` dan `void`; field `voided_by`,
  `voided_at`, `void_reason`, `void_journal_id`.
- Daftar transfer **tidak disimpan**: selalu diturunkan dari slip proses itu (D1), sehingga tidak bisa berbeda dari slip.

### Server

**1. Rekening pembayaran gaji.** `GET /api/hr/payroll/pay-accounts` — izin `payroll.pay`; jawaban: rekening aktif PT
aktif yang `purposes`-nya memuat `gaji`: `[{id, name, bank_name, account_number, holder_name, cash_type}]`, tanpa saldo.

**2. Antrean bayar.** `GET /api/hr/payroll/pay-queue` — izin `payroll.pay`; jawaban berhalaman `{items, total}` berisi
proses berstatus `posted` PT aktif: `id`, `number`, `period`, `run_type`, `employees`, `net_total`, `posted_at`. Tanpa
rincian slip.

**3. Daftar transfer.** `GET /api/hr/payroll/runs/{id}/transfer-list` — izin `payroll.pay`; proses harus `posted` atau
`paid` (selain itu 409 "Daftar transfer tersedia setelah penggajian diposting."). Jawaban:

```text
{run: {id, number, period, run_type, status, entity_id}, pay_account: {...} | null, paid_date,
 items: [{no, employee_id, employee_name, slip_number, bank_name, account_number, account_holder, amount, cash: bool}],
 count, total, without_account}
```

`amount` = `net` slip; `cash` benar bila slip tidak memuat nomor rekening; urut nama. `total` = Σ `amount` dan harus
sama dengan `totals.net` proses — bila berbeda, 409 "Jumlah daftar transfer tidak sama dengan total gaji bersih. Hitung
ulang tidak mungkin setelah posting; hubungi Admin." (penjaga, bukan keadaan normal).
`GET …/transfer-list/export` — izin `payroll.pay` — berkas `.xlsx` `transfer-gaji-<nomor proses>.xlsx`: baris kepala
(PT, nomor proses, periode, rekening sumber, tanggal bayar), kolom "No.", "Nama penerima", "Bank", "Nomor rekening",
"Nominal", "Berita" (isi: "Gaji {bulan tahun} {nama PT}"), baris "Total". Pengunduhan dicatat di jejak audit
(`hr.payroll.transfer_export`) tanpa menyalin nominal.

**4. Bayar** — `POST /api/hr/payroll/runs/{id}/pay`, izin `payroll.pay`, isi `{account_id?, paid_date?}`. Urutan (`02` §1):

1. PERIKSA: status `posted`; tidak ada slip ber-`net` negatif; rekening: `account_id` harus rekening aktif milik PT
   proses yang `purposes`-nya memuat `gaji`; bila kosong dan PT punya **tepat satu** rekening seperti itu, rekening itu
   dipakai; `paid_date` bawaan hari ini (WIB) dan tidak boleh sebelum `journal_date` proses;
   `preflight_posting(entity_id, paid_date)`.
2. NIAT: `posted` → `paying` bersyarat; simpan `pay_account_id`, `paid_date`, `paid_by_id`.
3. EFEK + JURNAL: satu kas keluar lewat `create_cash(ref_type="payroll_run", ref_id=id proses, account_id=…,
   txn_date=paid_date)` (PK-20) yang menjurnal Dr `ACC_HUTANG_GAJI` / Cr akun kas rekening itu sebesar `totals.net`,
   bertanggal `paid_date`. Kode akun tidak lagi diterima dari isi permintaan (`cash_account` diabaikan).
4. SELESAI: `paid`; `transfer_total`, `transfer_count` diisi. Gagal di langkah 3 → kembali `posted` dengan galat
   tampil; pengulangan memakai kas dan jurnal yang sama (kunci = id proses).

**5. Setoran kewajiban** (melengkapi PK-22):

- `GET /api/hr/payroll/remittances` dan `…/remittances/outstanding` menerima `hr.view` **atau** `payroll.pay`
  (`require_any_permission`); `outstanding` menerima `year=YYYY` dan mengembalikan 12 masa per jenis.
- `POST /api/hr/payroll/remittances/{id}/void` — izin `payroll.void`, isi `{reason}` ≥ 5 huruf. PERIKSA status `done`,
  `preflight_posting(entity_id, paid_date)` → NIAT `voiding` → kas setoran di-void dan jurnal pembalik terbit lewat
  pintu kas tahan-gagal → `void`. Setoran `void` tidak dihitung di `disetor`.

Galat:

| Keadaan | Kode | Pesan |
|---|---|---|
| Rekening tidak berperuntukan gaji | 400 | "Rekening {nama} tidak ditandai untuk pembayaran gaji. Pilih rekening lain, atau tambahkan peruntukan Gaji di Rekening & Saldo." |
| Rekening kosong dan PT punya lebih dari satu rekening gaji | 400 | "Pilih rekening pembayaran gaji." |
| PT tidak punya rekening gaji | 400 | "Belum ada rekening berperuntukan Gaji di PT ini. Atur di Keuangan › Kas & Bank › Rekening & Saldo." |
| Rekening milik PT lain atau nonaktif | 400 | "Rekening ini bukan rekening aktif PT penggajian." |
| Ada gaji bersih negatif | 409 | "Gaji bersih {nama} negatif (Rp …). Perbaiki potongannya lewat proses baru sebelum membayar." |
| Tanggal bayar sebelum tanggal jurnal gaji | 400 | "Tanggal bayar tidak boleh sebelum {tanggal jurnal gaji}." |
| Proses sedang atau sudah dibayar | 409 | "Penggajian {nomor} sedang atau sudah dibayar. Muat ulang." |
| Batal setoran yang bukan `done` | 409 | "Setoran {nomor} berstatus {label}, jadi tidak bisa dibatalkan." |
| Periode tertutup | 409 | pesan `ClosedPeriodError` apa adanya |

### Pengaturan

Tidak ada kunci baru. Kontrol dua orang gaji (`kontrol.proses_gaji.min_orang`, K-41) milik KF-T6 dan PK-22; unit ini
hanya memastikan `paid_by_id` terisi.

### Izin dan peran

Tidak ada pasangan izin baru. Perubahan pemegang bawaan dan menu:

| Peran | Perubahan |
|---|---|
| `finance` (bawaan) | Mendapat `payroll.pay` di `DEFAULT_PERMISSIONS`; menu: `hr-payroll-hub` dan tab `hr-payroll-remittances` saja. Tidak mendapat `hr.view`, jadi tidak bisa membuka karyawan, slip rinci, maupun komponen |
| Admin, Manajer | Tetap memegang kelima izin `payroll.*` |
| Peran "HR" | **Tidak dibuat sebagai peran bawaan.** Admin membuatnya sebagai peran kustom dari modul "SDM & Penggajian" dengan mencabut `payroll.approve`, `payroll.post`, `payroll.void`, `payroll.pay` di konfigurasi lanjutan; U10 membuktikan susunan itu bekerja |

Label aksi `pay` untuk sumber daya `payroll` di editor peran: "Bayar gaji dan setor BPJS/PPh 21".

### Layar

Hub Penggajian. Tab "Setoran Kewajiban" (PK-22) berganti label **Setoran & Pajak** (view tetap
`hr-payroll-remittances`; `roles` ditambah `finance`) dan berisi tiga bagian; komponen baru
`frontend/src/features/hr/PayrollPayPanel.jsx` dan `frontend/src/features/hr/TransferListPanel.jsx`.

- **Gaji siap dibayar** (tampil bagi pemegang `payroll.pay`): kolom "Nomor", "Periode", "Jenis", "Karyawan", "Total
  bersih"; tombol "Daftar transfer" dan "Bayar". Kosong: "Tidak ada penggajian yang menunggu dibayar."
  Pop-up **Bayar gaji** (pop-up baku): "Rekening pembayaran" (hanya rekening berperuntukan Gaji; tampil nama, bank,
  nomor), "Tanggal bayar", ringkasan "Total bersih Rp … untuk {n} karyawan ({m} tanpa rekening, dibayar tunai)".
  Konfirmasi (N5): "Bayar gaji {nomor} — {bulan tahun}? Rp … dari {nama rekening} · {nama PT}." Bila PT belum punya
  rekening gaji, tombol Bayar mati dengan petunjuk pesan galat ketiga di atas.
- **Daftar transfer** (panel samping): kolom "No.", "Nama penerima", "Bank", "Nomor rekening", "Nominal", "Slip"; baris
  tanpa rekening bertanda "Tanpa rekening — bayar tunai"; kaki "Total Rp … · {n} penerima"; tombol "Unduh Excel".
- **Setoran BPJS dan PPh 21**: isi PK-22, ditambah pemilih tahun dengan tabel 12 masa ("Masa", "Kewajiban", "Sudah
  disetor", "Sisa") per jenis, tombol "Batalkan" pada baris riwayat (minta alasan; hanya pemegang `payroll.void`), dan
  tautan "Rekap PPh 21 di Pusat Pajak".
- Tombol "Bayar" di detail Proses Gaji membuka pop-up yang sama; setelah dibayar tampil "Dibayar {tanggal} dari
  {rekening}" dan tautan "Daftar transfer" serta "Lihat jurnal" (L8).
- Banner PT; semua tombol tulis mati saat "Semua PT" dengan petunjuk "Pilih satu PT dulu."

## Uji penerimaan

Fixture di `ent_kanda`: proses reguler 2026-11 berstatus `posted`, `journal_date` 2026-11-30, tiga slip — Ani bersih
5.000.000 (BCA 111), Bayu 4.500.000 (Mandiri 222), Cici 3.250.000 (tanpa rekening); `totals.net` 12.750.000. Rekening
PT: R-GAJI (bank; `purposes` gaji + operasional), R-OPS (bank; operasional), R-KAS (kas kecil; operasional). Akun:
`fin` berperan Finance bawaan; `hrx` berperan kustom "HR" (tanpa acuan: `hr.view`, `hr.update`, `payroll.create`).

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | `fin`: `GET …/runs/{id}/transfer-list` | `count` 3; `total` 12.750.000 (5.000.000 + 4.500.000 + 3.250.000) = `totals.net`; `without_account` 1; baris Cici `cash: true` |
| U2 | B | — | `fin`: `POST …/pay` `{account_id: R-GAJI, paid_date: "2026-12-01"}` | `paid`; satu jurnal Dr 2-1600 12.750.000 / Cr 1-1100 12.750.000 bertanggal 2026-12-01; satu kas keluar 12.750.000 ber-`account_id` R-GAJI; saldo 2-1600 PT untuk proses itu 0; `transfer_total` 12.750.000 = kas keluar |
| U3 | B | — | `POST …/pay` dengan R-OPS | 400 "Rekening … tidak ditandai untuk pembayaran gaji…"; status tetap `posted`; 0 jurnal, 0 kas |
| U4 | B | — | `POST …/pay` tanpa `account_id`; lalu R-OPS diberi peruntukan gaji dan diulang pada proses lain | Pertama: R-GAJI dipakai (satu-satunya). Kedua: 400 "Pilih rekening pembayaran gaji." |
| U5 | B | Rekening bank milik `ent_ksc` berperuntukan gaji | `POST …/pay` dengan rekening itu | 400 "Rekening ini bukan rekening aktif PT penggajian." |
| U6 | B | — | `POST …/pay` `{paid_date: "2026-11-15"}` | 400 "Tanggal bayar tidak boleh sebelum 2026-11-30." |
| U7 | B | Periode Desember `ent_kanda` ditutup | `POST …/pay` `{paid_date: "2026-12-01"}` | 409 pesan periode; status `posted` |
| U8 | B | Slip keempat ber-`net` −100.000 | `POST …/pay` | 409 "Gaji bersih … negatif…"; tidak ada kas |
| U9 | B | — | `fin`: `GET …/pay-queue`; `GET …/pay-accounts`; `GET /api/hr/payroll/runs/{id}`; `GET /api/hr/employees`; `GET …/remittances/outstanding?year=2026` | 200; 200 (hanya R-GAJI); 403; 403; 200 dengan 12 masa per jenis |
| U10 | B | — | `hrx`: buat dan ajukan proses; sahkan; `pay`; `transfer-list` | 200, 200; 403; 403; 403 |
| U11 | B | U2 | `GET …/transfer-list/export`; buka dengan `openpyxl` | Tiga baris penerima dan baris Total 12750000; kolom "Berita" berisi "Gaji November 2026"; satu baris jejak audit `hr.payroll.transfer_export` |
| U12 | B | Proses Oktober berkewajiban BPJS 900.000; setoran BPJS 900.000 `done` (dibuat lewat endpoint PK-22) | Admin: `POST …/remittances/{id}/void` beralasan; lalu `outstanding` Oktober | `void`; jurnal pembalik Dr 1-1100 900.000 / Cr 2-1700 900.000; kas setoran void; `disetor` 0, `sisa` 900.000. `fin` mencoba void → 403 |
| U13 | B | PT tanpa rekening berperuntukan gaji | `GET …/pay-accounts`; `POST …/pay` | Daftar kosong; 400 "Belum ada rekening berperuntukan Gaji di PT ini…" |
| U14 | A | Proses `posted` | Dua `POST …/pay` bersamaan | Satu 200 dan satu 409; satu jurnal, satu kas |
| U15 | B | Peran Manajer Kosong; Sopir | `pay-queue`, `transfer-list`, `pay` | 403 semuanya, pesan bentuk Z6 dengan nama modul "SDM & Penggajian" |
| U16 | layar (uji jalan) | Login `fin` | Buka Penggajian › Setoran & Pajak → Daftar transfer → Bayar | Hanya tab Setoran & Pajak yang terlihat; pilihan rekening hanya R-GAJI; konfirmasi menyebut "Rp 12.750.000", nama rekening, dan nama PT; setelah bayar tombol "Unduh Excel" tersedia |

## Langkah kerja

1. `backend/tests_mem/test_PYT4_bayar_gaji.py`: U1–U13, U15 (merah).
2. `pay-accounts`, `pay-queue`, `transfer-list` dan ekspornya (hanya baca).
3. `pay` menurut urutan periksa → niat → kas dan jurnal → selesai; field baru di proses.
4. Izin bawaan Finance dan menunya; `require_any_permission` pada baca setoran; void setoran.
5. Layar: tab Setoran & Pajak, pop-up bayar, panel daftar transfer, tombol di Proses Gaji. U14 di A; uji jalan U16.
6. Gate penuh. Laporan memuat contoh U2: daftar transfer → jurnal → kas → saldo hutang gaji.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (field proses dan setoran); `CODEBASE_MAP.md`; `memory/PRD.md`; `docs/KN_13_NAVIGATION_MAP.md` (tab
Setoran & Pajak; menu Finance); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("daftar transfer", "rekening pembayaran").

## Di luar lingkup

- Membuat dokumen setoran, tanggal jurnal gaji, izin `payroll.*` → PK-22 (sudah). Pembuat kas dan rekening wajib → PK-20.
- Peruntukan rekening dan persetujuan perubahan rekening → PM-T1. Rekening bawaan per cara bayar → PM-T2.
- Berkas unggah dengan format khusus tiap bank, pembayaran sebagian, dan pembayaran per karyawan tidak dibangun.
- Memindahkan isi rekap PPh 21 dari Pusat Pajak → tidak dikerjakan; hanya tautan. Bukti potong → di luar blueprint (K-08).
- Menambah peran bawaan baru bernama HR → bukan di unit ini (lihat Asumsi).

## Asumsi dan risiko

- `ASUMSI:` "peran HR" pada rancangan dipenuhi dengan peran kustom buatan Admin, bukan peran bawaan baru; menambah
  peran bawaan menyentuh registri peran, beranda, dan menu yang dirombak unit jalur peran. Finance mendapat izin bayar
  secara bawaan sesuai usulan K-41.
- `ASUMSI:` karyawan tanpa rekening tetap masuk daftar bertanda tunai dan ikut dalam satu kas keluar; penyerahan tunainya
  di luar sistem.
- `ASUMSI:` gaji dibayar sekaligus per proses; proses dengan gaji bersih negatif ditolak, bukan dipotong dari total.
- `ASUMSI:` membatalkan setoran memakai izin `payroll.void`, bukan `payroll.pay`.
- `RISIKO:` PT yang rekeningnya belum diberi peruntukan Gaji tidak bisa membayar. PM-T1 memberi keempat peruntukan ke
  rekening lama, jadi hanya rekening baru yang perlu ditandai. Membatalkan: lepaskan pemeriksaan peruntukan di langkah
  1 (satu cabang); daftar transfer tidak menyimpan data.

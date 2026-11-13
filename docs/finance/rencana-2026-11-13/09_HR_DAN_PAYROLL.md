# Rancangan — HR dan Penggajian: dampak dan yang harus disiapkan

Status: rancangan untuk diputuskan pemilik. Belum ada kode. Kode dibaca di `9834947`; butir bertanda ✔ dicek langsung
pada berkas:baris yang disebut, sisanya dari pembacaan kode yang belum diuji jalan.

## 0. Ringkasan

- **Mengapa dokumen ini ada:** Meja Insentif ([`05`](05_MEJA_INSENTIF.md)) berakhir di slip gaji. Penggajian yang
  sekarang **tidak bisa menerimanya**: slip berisi kolom tetap dengan satu angka komisi, hanya boleh satu proses gaji
  per PT per bulan, dan slip tidak bisa dihitung ulang maupun diubah.
- **Yang sama dengan permintaan pemilik soal tunjangan:** tunjangan jabatan, makan, hari raya, dan lembur sekarang
  bukan konsep tersendiri. Tunjangan hanyalah daftar nama + nominal bebas di master karyawan yang dijumlah menjadi satu
  angka; THR tidak ada sama sekali.
- **Usulan:** slip menjadi **daftar komponen**; komponen didefinisikan **per PT**; angka dari modul lain (insentif,
  lembur, potongan kasbon) masuk lewat satu **antrean masukan komponen** yang berstatus; proses gaji punya **jenis**
  (reguler, THR, susulan). Dengan itu insentif multi-komponen, tunjangan per PT, dan THR memakai mekanisme yang sama.
- **Tiga hal yang harus diperiksa sebelum penggajian dipakai untuk gaji nyata**, terlepas dari rancangan ini: tabel
  tarif PPh 21 di kode tampak tidak disalin dari peraturan (PY-03); karyawan yang keluar tidak pernah dihitung masa
  terakhirnya (PY-05); semua karyawan aktif digaji penuh tanpa prorata (PY-04).

## 1. Keadaan sekarang

### Slip dan proses gaji

| Hal | Di kode | Bukti |
|---|---|---|
| Slip | Kolom tetap: gaji pokok, tunjangan (satu angka), lembur, komisi (satu angka), BPJS, PPh 21, bersih ✔ | `backend/services/hr_payroll_service.py:298-312` |
| Tunjangan | `hr_employees.allowances[{nama, nominal}]` teks bebas; dijumlah, nama hilang di slip | `backend/schemas_hr.py:21-23`; `hr_payroll_service.py:110-120, 263` |
| Komponen sekali-pakai, potongan | Tidak ada tempatnya; router slip hanya punya baca | `backend/routers/hr_payroll.py:211-251` |
| Satu proses per PT per bulan ✔ | Proses kedua mengembalikan proses pertama | `hr_payroll_service.py:362-372` |
| Alur | Draf → diajukan → disahkan → diposting → dibayar; draf pun tidak bisa dihitung ulang (FY-06) | `hr_payroll_service.py:449-574` |
| Izin | Seluruh izin `hr.*` hanya admin dan manajer; tidak ada peran HR; Finance tidak bisa melihat atau membayar gaji | `backend/permissions_config.py:95, 238` |

### Aturan hitung

| Komponen | Aturan terpasang | Catatan |
|---|---|---|
| Gaji | Bulanan penuh untuk semua yang berstatus aktif saat proses dibuat | Tanpa prorata masuk/keluar; tanpa potongan alpha, telat, cuti tanpa gaji; tipe harian/borongan diperlakukan bulanan |
| Lembur | Upah sejam = gaji pokok ÷ 173; hari kerja 1,5× lalu 2×; hari libur 2×/3×/4× | Pengali di Pusat Pengaturan tidak berpengaruh; kalender libur dan pola 6 hari kerja tidak bisa diatur; lembur dari absensi otomatis dianggap disetujui |
| BPJS | Persen × gaji pokok dengan plafon; per PT bisa diatur | Dasar "gaji pokok saja" ditulis mati |
| PPh 21 | Tarif efektif bulanan; masa terakhir dihitung ulang tahunan | Tabel tarif dan PTKP ditulis mati di kode ✔ `hr_payroll_service.py:23-70`; tanpa saldo awal tahun berjalan |
| Komisi | Dari mesin komisi otomatis, satu angka | Lihat `05` §1 |
| THR, bonus, rapel, kasbon | Tidak ada | — |

### Sambungan dengan modul lain

| Sumber | Tersambung? |
|---|---|
| Absensi, shift, cuti | Tidak, kecuali menit lembur |
| Lembur yang diajukan | Ya; tetapi lembur yang disetujui setelah proses gaji dibuat tidak pernah terbayar (akibat FY-06) |
| Insentif sales | Otomatis, satu angka; mode "mati" tidak dihormati (PY-06) |
| KPI karyawan | Tidak |
| Uang muka karyawan, piutang karyawan, reimburse | Tidak |
| Pembayaran | Satu jurnal dan satu mutasi kas sebesar total bersih; layar tidak menawarkan pilihan rekening sehingga selalu dari akun 1-1100; tanpa daftar transfer per karyawan |
| Setoran BPJS dan PPh 21 | Tidak ada (FY-07) |

Yang sudah baik: ekspor slip dan gaji pokok dijaga izin khusus; antrean persetujuan tidak menampilkan nominal; asisten
dan beranda tidak membaca koleksi gaji; log audit menyamarkan nilai pribadi.

## 2. Temuan tambahan (di luar 139 temuan audit)

ID memakai awalan `PY-` karena `HR-01…05` sudah dipakai paket lama di komentar kode.

| ID | Tingkat | Temuan | Bukti | Ditutup oleh |
|---|---|---|---|---|
| PY-01 ✔ | Tinggi | Slip berkolom tetap; tidak bisa memuat beberapa komponen insentif, THR, atau potongan | `hr_payroll_service.py:298-312`; `routers/hr_payroll.py:211-251` | PY-T1 |
| PY-02 ✔ | Tinggi | Satu proses gaji per PT per periode; kunci jurnal `entitas:periode` — proses THR atau susulan mustahil | `hr_payroll_service.py:362-372`; `services/gl_service.py:3042-3046` | PY-T1 |
| PY-03 ✔ (isi tabel dibaca; kebenaran terhadap peraturan belum dicek) | Tinggi | Tabel tarif efektif PPh 21 tampak tidak disalin dari lampiran peraturan: kategori A, B, C memakai batas penghasilan yang **sama persis** mulai Rp 16,95 jt ke atas; kategori B dan C melompat dari 31 % langsung ke 34 %. Menurut ingatan saya atas lampiran PP 58/2023, tarif kategori A juga lebih rendah dari seharusnya di atas ±Rp 9,65 jt (mis. Rp 15 jt: kode 4,5 %) | `hr_payroll_service.py:23-59` | K-42 (verifikasi orang pajak), lalu PK-46 |
| PY-04 | Tinggi | Tanpa prorata dan tanpa potongan absen; karyawan aktif digaji penuh termasuk untuk periode sebelum tanggal masuknya | `hr_payroll_service.py:262-270, 335-343` | PY-T3 |
| PY-05 ✔ | Tinggi | Penggajian membaca `end_date` / `resign_date`, sedangkan master karyawan hanya menulis `separation_date` — masa terakhir karyawan keluar tidak pernah terhitung, dan hitung ulang pajak tahunannya tidak terjadi | `hr_payroll_service.py:241, 337-338`; `routers/hr.py:30, 453-479` | PK-45 |
| PY-06 | Sedang | Mode komisi "mati" dan "bayar saat faktur" ada di katalog pengaturan tetapi tidak dibaca; komisi selalu masuk slip | `backend/config_catalog_ops.py:545-548`; `hr_payroll_service.py:245-257, 269` | KM-T4 |
| PY-07 | Sedang | Pengali lembur tidak berpengaruh; libur nasional dan 6 hari kerja tidak bisa diatur; simulator memakai rumus lain | `hr_payroll_service.py:175-181, 221`; `backend/config_simulator.py:370-374` | PY-T3 |
| PY-08 | Sedang | Lembur dari absensi = jam kerja − durasi shift (datang lebih awal ikut terhitung) dan langsung berstatus disetujui | `backend/services/hr_attendance_service.py:89-104, 218`; `hr_payroll_service.py:200-206` | PY-T3, K-39 |
| PY-09 | Sedang | Tanpa riwayat atau tanggal berlaku gaji; pindah PT hanya mengganti `entity_id`; pajak tahunan menggabung slip lintas PT | `routers/hr.py:33, 416-431`; `hr_payroll_service.py:231-237` | PY-T2 |
| PY-10 ✔ | Sedang | Pratinjau gaji menerima `entity_id` mentah dari isi permintaan (proses buat sudah dijaga, pratinjau belum) | `routers/hr_payroll.py:106-112` vs `:118-119` | PK-45 |
| PY-11 | Sedang | Bayar gaji selalu dari akun 1-1100; satu mutasi kas; tanpa daftar transfer | `features/hr/PayrollRunsView.jsx:88`; `hr_payroll_service.py:556-573` | PY-T4 |
| PY-12 | Sedang | Tanpa saldo awal bruto dan PPh tahun berjalan — bila mulai dipakai di tengah tahun, hitung ulang Desember mengembalikan potongan | `hr_payroll_service.py:231-237, 284-295` | PY-T3, K-42 |
| PY-13 | Rendah | PDF slip: baris tetap, persen BPJS ditulis mati, label tarif "0,00 %" pada masa terakhir, tanpa rincian tunjangan | `backend/services/hr_payroll_pdf.py:72-104` | PY-T1 |
| PY-14 | Rendah | Format periode tidak divalidasi; mengubah jam absen tidak menghitung ulang lembur; teks layar "perubahan lewat pengembalian ke draf" keliru; label "Payroll Run" belum diindonesiakan | `schemas_hr_payroll.py:8`; `routers/hr_attendance.py:35, 439`; `PayrollRunsView.jsx:66`; `config/hubTabs.js:196` | PY-T1 |

Dari audit, masih berlaku: FY-02 (tanggal jurnal), FY-06 (tidak bisa hitung ulang/batal), FY-07 (setoran), FY-08 (hutang
insentif), FY-09 (pemisahan tugas), FY-16 (basis PPh 21 di rekap) — semuanya di PK-22 dan PK-40.

## 3. Rancangan

### 3.1 Komponen gaji per PT

Satu daftar per PT. Setiap baris slip adalah satu komponen.

| Sifat komponen | Pilihan |
|---|---|
| Jenis | Pendapatan · Potongan · Tanggungan perusahaan |
| Cara hitung | Tetap bulanan · Per hari hadir · Per jam (lembur) · Persen dari dasar · **Masukan** (angka datang dari modul lain atau diisi beralasan) · Menurut undang-undang (BPJS, PPh 21) |
| Kena pajak | Ya / tidak |
| Masuk dasar BPJS | Ya / tidak |
| Masuk dasar upah lembur | Ya / tidak |
| Diprorata bila masuk/keluar tengah bulan | Ya / tidak |
| Akun beban | Lewat pemetaan akun per PT |

Contoh isi, untuk menunjukkan bahwa kebutuhan pemilik tertampung tanpa kode khusus:

| Komponen | Jenis | Cara hitung | Sumber angka |
|---|---|---|---|
| Gaji Pokok | Pendapatan | Tetap bulanan | Riwayat kompensasi |
| Tunjangan Jabatan | Pendapatan | Tetap bulanan | Riwayat kompensasi |
| Tunjangan Makan | Pendapatan | Per hari hadir | Absensi |
| Lembur | Pendapatan | Per jam | Pengajuan lembur yang disetujui |
| Insentif Bulanan / Triwulan / Tahunan | Pendapatan | Masukan | Lembar Insentif yang disahkan (`05`) |
| Tunjangan Hari Raya | Pendapatan | Masukan (jenis proses THR) | Usulan sistem dari masa kerja; disahkan orang |
| Potongan Tidak Hadir | Potongan | Per hari | Absensi |
| Potongan Kasbon | Potongan | Masukan | Uang muka/pinjaman karyawan |
| BPJS, PPh 21 | Potongan / tanggungan | Menurut undang-undang | Tabel bertanggal berlaku |

Satu komponen yang sama boleh berbeda sifat di PT lain (mis. tunjangan makan tetap di PT-A, per hari hadir di PT-B).

### 3.2 Riwayat kompensasi karyawan

Gaji pokok dan komponen tetap tiap karyawan disimpan sebagai baris **bertanggal berlaku** dengan penyetuju, bukan
ditimpa di master. Pindah PT juga baris bertanggal (penugasan), sehingga slip dan pajak tiap PT terpisah benar. Kenaikan
gaji yang berlaku mundur menghasilkan usulan rapel sebagai masukan komponen.

### 3.3 Antrean masukan komponen

Satu koleksi tempat semua angka dari luar penggajian masuk:

| Field | Isi |
|---|---|
| PT, karyawan, periode bayar | Ke proses gaji mana angka ini ditujukan |
| Komponen, label, periode dasar | Mis. "Insentif Triwulan III 2026" |
| Nominal | Boleh negatif (penyesuaian) |
| Sumber | Lembar insentif · lembur · kasbon · rapel · isian manual beralasan |
| Kunci sumber | Unik per baris sumber, supaya tidak masuk dua kali |
| Status | Disahkan → terpakai (oleh proses gaji tertentu) → dibatalkan |

- Proses gaji mengambil semua masukan "disahkan, belum terpakai" untuk PT dan periode bayarnya, lalu menandainya
  terpakai. Bila proses dibatalkan atau di-void, tanda itu dilepas.
- Isian manual (bonus sekali-pakai, koreksi) juga lewat antrean ini, dengan alasan dan penyetuju — tidak ada cara
  mengetik angka langsung di slip.
- Ini satu-satunya titik sambung Meja Insentif ke penggajian.

### 3.4 Jenis proses gaji

| Jenis | Kapan | Isi |
|---|---|---|
| Reguler | Bulanan | Semua komponen |
| THR | Menjelang hari raya | Hanya komponen THR + pajaknya |
| Susulan | Kapan pun | Masukan yang datang setelah proses reguler (lembur terlambat disetujui, insentif di luar tanggal gajian, koreksi) |

Kunci proses dan kunci jurnal memuat jenis dan nomor urutnya. PPh 21 bulan itu dihitung atas gabungan semua proses di
bulan yang sama.

### 3.5 Aturan hitung dari pengaturan, bukan dari kode

| Aturan | Menjadi |
|---|---|
| Tabel tarif efektif dan PTKP | Tabel bertanggal berlaku di pengaturan, diisi dari lampiran peraturan dan **diverifikasi orang pajak** |
| Prorata masuk/keluar | Per PT: hari kalender atau hari kerja |
| Potongan alpha, telat, cuti tanpa gaji | Komponen potongan dengan tarif per PT |
| Lembur | Wajib pengajuan atau otomatis dari absensi dengan ambang minimum (K-39); kalender libur per PT; pola 5 atau 6 hari kerja |
| Dasar BPJS dan dasar upah lembur | Dari tanda di tiap komponen |
| Saldo awal tahun berjalan | Isian sekali saat mulai dipakai |
| Pembulatan | Ke rupiah penuh |

### 3.6 Siklus dan peran

```text
DRAF (bisa dihitung ulang, berkali-kali)  →  DIAJUKAN  →  DISAHKAN  →  DIPOSTING  →  DIBAYAR
        ↑ dikembalikan dengan alasan ─────────┘
BATAL sebelum diposting   ·   VOID + jurnal balik sesudah diposting
```

| Langkah | Usulan pemegang (K-41) |
|---|---|
| Menyiapkan, menghitung, mengajukan | HR (peran baru) |
| Mengesahkan | Manajer / pemilik (≠ penyiap) |
| Memposting | Akuntansi |
| Membayar, menyetor BPJS dan PPh 21 | Finance |

Slip tampil di swalayan karyawan setelah **dibayar**, bukan sejak disahkan.

### 3.7 Pembayaran dan setoran

- Membayar memilih rekening dari daftar ber-peruntukan "Gaji" (rancangan `07` §A3), lalu menghasilkan **daftar
  transfer** per karyawan (bank, nomor, nama, bersih) yang bisa diunduh untuk diunggah ke bank.
- Dokumen **setoran kewajiban** per periode untuk BPJS dan PPh 21 (FY-07).
- Bukti potong per karyawan menunggu K-08.

### 3.8 Layar

Hub Penggajian menjadi tiga tab (lihat [`01`](01_PENGGABUNGAN_MENU.md)):

| Tab | Isi |
|---|---|
| Proses Gaji | Daftar proses; di dalamnya slip per karyawan dengan rincian komponen; cari slip lintas periode. Menggantikan tab "Slip Gaji" yang sekarang menduplikasi tabel di detail proses |
| Komponen & Masukan | Daftar komponen PT; antrean masukan (disahkan, terpakai, dibatalkan) dengan sumbernya |
| Setoran & Pajak | Setoran BPJS/PPh 21; rekap PPh 21 (sekarang di Pusat Pajak) |

Riwayat kompensasi ada di kartu karyawan, bukan menu baru.

## 4. Tahap bangun

| Tahap | Isi | Prasyarat | Selesai bila |
|---|---|---|---|
| (PK-45) | PY-05, PY-10: perbaikan cepat | — | Lihat `02` |
| (PK-46) | PY-03: tabel tarif dipindah ke pengaturan bertanggal berlaku | K-42 | Lihat `02` |
| PY-T1 Komponen dan jenis proses | Daftar komponen per PT; slip berisi daftar komponen (kolom lama tetap diisi sebagai jumlah, supaya jurnal, PDF, ekspor, dan rekap pajak lama tetap jalan); antrean masukan; jenis proses reguler/THR/susulan; PDF dari komponen | PK-22 (hitung ulang, batal, void) | Dua masukan insentif untuk satu karyawan → dua baris di slip; proses THR bisa dibuat di bulan yang sudah punya proses reguler; Σ komponen = bruto lama untuk data acuan |
| PY-T2 Riwayat kompensasi | Baris bertanggal berlaku + penugasan PT; rapel sebagai masukan | PY-T1 | Kenaikan berlaku tanggal 16 → slip bulan itu memuat dua tarif prorata (bila prorata diaktifkan) |
| PY-T3 Aturan hitung | Prorata, potongan absen, lembur dari pengaturan, kalender libur, saldo awal pajak | PY-T1; K-38, K-39 | Kasus uji per aturan dengan hitungan tangan |
| PY-T4 Bayar dan setor | Pilih rekening; daftar transfer; setoran kewajiban; peran HR dan Finance | PK-22 (FY-07, FY-09); PM-T1 | Σ daftar transfer = total bersih = kas keluar; setoran menurunkan hutang BPJS/PPh 21 |
| PY-T5 Swalayan | Slip setelah dibayar; riwayat slip; kartu insentif (bersama KM-T5) | PY-T1 | — |

Urutan terhadap Meja Insentif: KM-T2 dan KM-T3 (cari, jumlahkan, putuskan) **tidak** menunggu penggajian. Hanya KM-T4
(masuk slip dan buku besar) yang menunggu PY-T1.

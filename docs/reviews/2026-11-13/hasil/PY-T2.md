# PY-T2 — Riwayat kompensasi dan penugasan PT karyawan dengan tanggal berlaku

- Commit awal: `5f193df` (worktree kerja, basis B)        - Commit akhir: `5edef21` (kode) · `82ef1bb` (cek layar: warna lencana)        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PY-09 (spesifikasi `docs/blueprint/unit/PY-T2.md`); keputusan K-37, K-38
- Risiko sedang → satu serah-terima. Prasyarat PY-T1 (komponen `tetap_bulanan`, pembangun `components[]`,
  `enqueue_input`) dan PK-22 (`payroll.approve`, proses `posted`/`paid`) sudah di basis.

## Cek ulang "Keadaan sekarang" (spesifikasi dibaca di `3132cc4`; dicek di `5f193df`)

| Butir spesifikasi | Hasil di HEAD awal |
|---|---|
| Gaji pokok, tunjangan, PT field master yang boleh ditimpa `PATCH` — `routers/hr.py:33` (`base_salary`) | Berlaku — `:33` (`EMP_UPDATE_FIELDS` memuat `base_salary`, `allowances`, `entity_id`) |
| Gaji pokok hanya dibulatkan lalu disimpan — `routers/hr.py:418` | Berlaku, bergeser — `:419`–`:423` |
| Jejak audit menyamarkan nilai — `routers/hr.py:429` (`masked_fields`) | Berlaku, bergeser — `:432` |
| Karyawan baru menerima ketiganya dari isi permintaan — `routers/hr.py:298`, `:305` | Berlaku — `:298`, `:305` |
| Proses gaji membaca master saat dihitung — `hr_payroll_service.py:262` (`base_salary`), `:263` (`_sum_allowances`) | Berlaku, bergeser — `:396` (`base = float(emp.get("base_salary"))`), `:406` (PY-T1 mengganti `_sum_allowances` dengan `earning_components(..., allowances=emp.get("allowances"))`) |
| Karyawan dipilih dari `entity_id` master — `hr_payroll_service.py:341` | Berlaku, bergeser — `_active_employees` `:504`; juga `_build_slips` THR/susulan `:523` (saring `entity_id` master) |
| Hitung ulang pajak tahunan mengambil slip semua PT — `hr_payroll_service.py:235` | Berlaku, bergeser — `_prior_year_slips` `:280`–`:287` (saring `employee_id` + tahun saja) |
| Nilai gaji data pribadi — `hr_service.py:17` (`PII_FIELDS`); izin lihat `routers/hr.py:42` (`view_pii`) | Berlaku — `:17`; `:42` |
| Layar: isian gaji di form karyawan — `EmployeeFormDrawer.jsx:90`; kartu karyawan nilai kini saja — `Employee360Panel.jsx:72` | Berlaku — `:90` (payload `base_salary`), `:253` (isian); `:72` (slip) dan `:120` (Kpi "Gaji Pokok") |
| Yang dipakai dari PY-T1: `hr_pay_components` (`tetap_bulanan`), `components[]`, `enqueue_input` | Ada — `hr_pay_components.py` (`GAJI_POKOK`, `TUNJANGAN` = `tetap_bulanan`), `earning_components`, `hr_pay_inputs.enqueue_input` (selalu `approved` — ditambah parameter `status`, lihat "Menyimpang") |
| — (tidak di spesifikasi) | **Data awal** menyemai proses gaji reguler `ent_ksc` untuk dua bulan sebelum jam sistem (`bootstrap.seed_hr_payroll_foundation`: hari ini 15 Nov → Okt `approved`, Sep `pending_approval`) — bentrok dengan U5 (Sep/Okt `posted` di `ent_ksc`); uji memakai PT uji sendiri (menyimpang no. 1) |

## PY-09 — gaji pokok, tunjangan, dan PT ditimpa di master; tanpa tanggal berlaku, riwayat, penyetuju

- Berlaku di HEAD: ya (bukti merah `bukti/PY-T2/merah_kode_lama.txt`, 17/17 merah: endpoint riwayat 404, kunci
  `hr.prorata_perubahan_gaji` tidak ada di registry, `hr_compensation_service` tidak ada, skrip migrasi tidak ada,
  U9 `PATCH base_salary` → 200).
- Akar masalah: satu angka di master yang ditimpa; proses gaji membaca master saat dihitung, memilih karyawan menurut
  `entity_id` master, dan menghitung ulang pajak tahunan dari slip semua PT.
- Perubahan perilaku (sebelum → sesudah):
  - **Data.** `hr_compensation_history` (`hcomp_`) dan `hr_employee_assignments` (`hasg_`, **SCOPED**) — kolom
    spesifikasi; indeks unik parsial `(employee_id, effective_from)` untuk `status: "approved"` di keduanya
    (`uq_employee_effective_approved`, `REQUIRED_UNIQUE_INDEXES`), indeks `(employee_id, status, effective_from)` dan
    `(entity_id, status)`; `uq_id` (`ID_INDEX_COLLECTIONS`). `effective_to` diisi sistem (`_rechain`). Komponen bawaan
    baru **RAPEL** tiap PT (pendapatan, `masukan`, kena pajak, `other_earnings`, reguler + susulan, `system`) — PT lama
    mendapatnya lewat isi awal idempoten `ensure_defaults`.
  - **Layanan** `services/hr_compensation_service.py`: `compensation_at`, `assignment_at`, `segments`,
    `employees_for_run`, `apply_effective` (spesifikasi) + `build_segments` (murni), `propose_*`, `decide_*`,
    `initial_rows`, `master_drift` (INV-PY-2), `rapel_lines` / `enqueue_rapel`, `job_apply_effective`.
  - **Proses gaji** (`hr_payroll_service`): `_active_employees(PT, periode)` → `employees_for_run` (penugasan, bukan
    master; karyawan tanpa riwayat = master); `compute_payslip` membangun baris Gaji Pokok + komponen tetap dari
    potongan periode (`hr_pay_components.segment_lines`); dasar BPJS & upah lembur = Σ gaji pokok potongan;
    `_prior_year_slips(..., entity_id)` hanya slip di PT proses itu; THR/susulan memuat karyawan menurut masukan PT itu
    (bukan `entity_id` master).
  - **Aturan prorata** (pengaturan baru `hr.prorata_perubahan_gaji`, `group` sdm · `section` lembur · enum
    `mati`/`hari_kalender` · bawaan `mati` · `("global", "entity")` · `risk` high · `requires_reason` · izin
    `hr.manage_payroll`; teks spesifikasi): `mati` = nilai pada hari terakhir periode (atau hari terakhir bekerja), PT
    pada hari itu yang menggaji sebulan penuh; `hari_kalender` = tiap potongan baris sendiri "{nama} ({tgl}–{tgl}
    {bulan})", nilai × hari ÷ hari kalender (rupiah penuh, setengah ke atas).
  - **Rapel**: baris kompensasi disahkan dengan `effective_from` pada periode yang proses regulernya `posted`/`paid` →
    satu masukan `pending` komponen RAPEL per periode (bulan berjalan, selisih nilai baru − nilai dibayar menurut aturan
    prorata PT slip itu, label "Rapel gaji {bulan tahun}", `source_type` rapel, `source_key`
    `rapel:<id baris>:<periode>`); mengulang pengesahan tidak menambah masukan.
  - **Endpoint** (`routers/hr_compensation.py`, baru): `GET /api/hr/employees/{id}/compensation` (`hr.view` +
    `hr.view_pii`, tanpa `view_pii` → 403 Z6) · `POST /api/hr/employees/{id}/compensation` (`hr.update`) ·
    `POST /api/hr/compensation/{id}/approve|reject|cancel` (`payroll.approve`) · `POST /api/hr/employees/{id}/assignments`
    (`hr.update`; PT tujuan di luar cakupan → 403) · `POST /api/hr/assignments/{id}/approve|reject` (`payroll.approve`).
    Pesan galat spesifikasi persis. Semua ber-id mengadu PT karyawan (dan PT tujuan penugasan) dengan cakupan pelaku.
    `routers/hr.py`: `PATCH` menolak `base_salary`/`allowances`/`entity_id` (400 spesifikasi); `POST /hr/employees`
    membuat baris kompensasi + penugasan pertama `approved` berlaku sejak tanggal masuk (kosong → hari ini WIB;
    gagal → karyawan & baris dihapus).
  - **Turunan master**: `apply_effective` (saat pengesahan untuk karyawan itu; tugas terjadwal baru
    `hr_compensation_effective` harian 00.10 WIB untuk semua) menyalin baris yang berlaku hari ini ke master
    (+ departemen/jabatan penugasan saat baris itu pertama berlaku), jejak audit nilai gaji disamarkan. Invarian
    **INV-PY-2** (`scripts/verify_data_integrity.py`, lapisan `hr_comp`).
  - **Migrasi** `scripts/migrate_hr_compensation_py_t2.py` (bawaan baca-saja; `--apply`).
  - **Layar**: kartu karyawan (`Employee360Panel` → `EmployeeCompensationSection.jsx`, baru) bagian **Riwayat
    Kompensasi** dan **Penugasan PT** (hanya pemegang `hr.view_pii`); form ubah karyawan menampilkan gaji pokok,
    tunjangan, PT hanya-baca dengan petunjuk "Ubah lewat Riwayat Kompensasi." dan tidak mengirimnya.
- Berkas berubah: lihat "Berkas".
- Status: implemented_pending_review

## Uji penerimaan

Berkas: `backend/tests_mem/test_PYT2_riwayat_kompensasi.py` (17 uji). "Kode lama" = berkas unit di W dikembalikan ke
`5f193df` (`scratchpad/pyt2_swap.sh`; `bukti/PY-T2/merah_kode_lama.txt`, **17/17 merah**). Fixture: PTA/PTB = PT uji
(peran `ent_ksc`/`ent_kanda`, menyimpang no. 1), BPJS mati (lapisan PT), K1–K6 disisipkan TANPA riwayat (6.000.000 +
Transport 500.000, TK0, masuk 1 Jan 2026); "hari ini" dibekukan (`book_date._sekarang`) 10 Nov → 15 Des 2026. Usul,
sahkan, proses gaji, masukan, pengaturan lewat HTTP.

| ID | Lapis | Kode lama | Kode baru |
|---|---|---|---|
| U1 | B | merah: skrip migrasi tidak ada | lulus — baca-saja tidak menulis ("PTA: 5 karyawan tanpa riwayat … → SAMA"); `--apply` dua kali: K1 tepat satu baris kompensasi (6.000.000 + TUNJANGAN "Transport" 500.000, `migrasi`) dan satu penugasan (PTA), berlaku 2026-01-01; jalan kedua "Diterapkan: 0 baris kompensasi · 0 baris penugasan"; pratinjau November K1 `gross` 6.500.000 sebelum = sesudah, baris "Gaji Pokok" & "Tunjangan — Transport" sama |
| U1 | A | — | ditulis (`tests/test_bp_PYT2_migrasi.py`: baca-saja di data acuan; `--apply` dua kali hanya bila `KN_PYT2_TERAPKAN=1`) — belum teruji |
| U2 | B | merah: 404 | lulus — usul 7.500.000 berlaku 2026-12-01, disahkan 10 Nov: master tetap 6.000.000; November Gaji Pokok 6.000.000; Desember 7.500.000; master 7.500.000 sesudah `apply_effective("2026-12-01")` |
| U3 | B | merah: 404 | lulus — kenaikan 16 Nov, aturan bawaan: satu baris "Gaji Pokok" 7.500.000; "Tunjangan — Transport" 500.000 ikut tersalin |
| U4 | B | merah: kunci tidak ada | lulus — `hari_kalender` untuk PTA, hitung ulang: "Gaji Pokok (1–15 Nov)" 3.000.000 + "(16–30 Nov)" 3.750.000, `base_salary` 6.750.000; "Tunjangan — Transport (1–15 Nov)" 250.000 + "(16–30 Nov)" 250.000; K1 tanpa perubahan tetap satu baris; PTB (bawaan) K6 kenaikan 16 Nov → satu baris 7.500.000 |
| U5 | B | merah: 404 | lulus — Sep & Okt PTA `posted` (6.000.000); sahkan 7.500.000 berlaku 2026-09-01 pada 10 Nov → dua masukan `pending` RAPEL November 1.500.000 "Rapel gaji September 2026" / "Rapel gaji Oktober 2026", kunci `rapel:<id>:2026-09/10`; sahkan lagi → 409, masukan tetap 2 |
| U6 | B | merah (berantai U5) | lulus — kedua masukan disahkan, proses November dihitung ulang: dua baris rapel, `other_earnings` 3.000.000 |
| U7 | B | merah: 404 | lulus — K4 pindah PTB berlaku 2026-11-01 (disahkan 10 Nov; master langsung PTB, baris PTA berakhir 2026-10-31); Sep/Okt PTA memuat K4, Okt PTB tidak; Nov PTB memuat K4 (6.000.000), Nov PTA tidak |
| U8 | B | merah (berantai U7) | lulus — slip K4 Jan–Agu (disisipkan) + Sep–Okt di PTA, Nov di PTB; Desember PTB: `pph21_annual.months` = 2, `prior_withheld` = PPh 21 slip November PTB, `tax_gross` 13.000.000 (slip PTA tidak ikut) |
| U9 | B | merah: `PATCH base_salary` 200 | lulus — `PATCH` `base_salary` / `allowances` / `entity_id` → 400 "Gaji dan penugasan PT diubah lewat Riwayat Kompensasi di kartu karyawan."; `phone` 200; `POST` karyawan baru 5.000.000 (+ Makan 300.000, masuk 2026-12-01) → satu baris kompensasi `approved` 5.000.000 berlaku 2026-12-01 + satu penugasan PTA |
| U10 | B | merah: 404 | lulus — peran Tanpa Acuan `hr.view` → GET 403 (kalimat Z6, tanpa kode izin); `hr.view`+`view_pii`+`update` → usul 200, sahkan 403 |
| U11 | B | merah: 404 | lulus — baris sah 2026-12-01; baris lain bertanggal sama disahkan → 409 "Sudah ada perubahan kompensasi yang berlaku 2026-12-01 untuk karyawan ini."; tetap satu `approved` |
| U11 | A | — | ditulis (dua pengesahan bersamaan × 3 putaran → tepat satu `approved`, satu `CompensationConflict`) — belum teruji |
| U12 | B | merah: 404 | lulus — pelaku hanya `PTA`: usul penugasan K1 ke PTB → 403 (pagar tulis PT bersama menjawab lebih dulu: "Anda tidak berwenang menyimpan data ke “PT Uji PYT2B”…"), tidak ada baris |
| U13 | B | merah: kunci tidak ada | lulus — atribut registry spesifikasi; putaran `t1_config` (`test_KFT8_putaran_pengaturan.putaran`) lulus; nilai "harian" → 400 |
| U14 | B | merah: layanan tidak ada | lulus — sesudah `apply_effective`, INV-PY-2 PASS; `base_salary` K2 diubah langsung di database → FAIL menyebut `emp_pyt2_k2` dan `base_salary` |
| tambahan (validasi) | B | merah: 404 | lulus — "2026-13-01" / "16/11/2026" / kosong → 400 "Tanggal berlaku harus berbentuk TTTT-BB-HH."; komponen LEMBUR → 400 "Komponen LEMBUR bukan komponen tetap bulanan di PT ini."; alasan kosong → 400 "Alasan wajib diisi."; tolak/batal baris sah → 409 "Baris yang sudah disahkan tidak bisa diubah. Buat baris baru dengan tanggal berlaku baru."; tolak baris menunggu 200, lalu sahkan → 409 "…Ditolak…"; GET riwayat (semua status, PT pada tanggal berlaku, pilihan komponen tetap tanpa Gaji Pokok); tugas terjadwal `hr_compensation_effective` harian 00.10 |
| U15 | layar | — | jest `features/__tests__/pyt2RiwayatKompensasi.test.js` (8): dua baris 6.000.000 "Berlaku" / 7.500.000 "Akan berlaku", form ubah hanya-baca — **belum diuji jalan** di peramban (integrator) |

### Contoh angka

- **U4** (PTA November, 30 hari): Gaji Pokok 6.000.000 berlaku s.d. 15 Nov, 7.500.000 sejak 16 Nov → 6.000.000 × 15 ÷ 30
  = 3.000.000; 7.500.000 × 15 ÷ 30 = 3.750.000; Σ 6.750.000. Tunjangan Transport 500.000 di kedua baris → 250.000 + 250.000.
  Bruto 7.250.000.
- **U5** Sep: nilai baru 7.500.000 + 500.000 = 8.000.000; dibayar slip Sep (Gaji Pokok 6.000.000 + Tunjangan 500.000)
  6.500.000 → rapel 1.500.000; Okt sama. U6: `other_earnings` = 1.500.000 × 2 = 3.000.000.
- **U8**: Desember PTB masa pajak terakhir — slip terdahulu di PTB = November (6.500.000) → bulan = {Nov, Des} = 2,
  bruto setahun PT itu = 6.500.000 × 2 = 13.000.000; 10 slip PTA (Jan–Okt) tidak dihitung.

Unit tidak membuat jurnal baru: proses gaji tetap dijurnal lewat `post_payroll_run` (PK-22/PY-T1) dari komponen slip;
baris rapel = komponen pendapatan `other_earnings` → Dr 6-1000 / Cr 2-1600 seperti pendapatan lain.

## Uji lama yang disesuaikan (perilaku yang sengaja diubah)

| Uji | Sebab | Penyesuaian |
|---|---|---|
| `tests_mem/test_KFT1_izin_pengaturan.py` U04 | +1 kunci registry berizin `hr.manage_payroll` | `PYT2_KUNCI = 1` (U02 tetap: bukan `settings.manage`) |
| `tests_mem/test_PK14_indeks_wajib.py` U12 | +2 indeks wajib | `PYT2_INDEKS = 2` |
| lapis A `tests/test_bp_PK14_indeks_wajib.py` U02 | idem | 29 → 31 |
| lapis A `tests/test_p13_audit.py::test_patch_base_salary_pii_excluded` | `PATCH base_salary` kini 400 | menguji 400 + pesan; penyamaran PII di jejak audit diuji dengan `npwp` |
| lapis A `tests/test_p14_history.py::test_hr_base_salary_masked` | idem | menguji 400; penyamaran diuji dengan `bank_acc_no` |

## Cek layar

Dari kode (pelaksana); potret 1280/1024/390 px oleh integrator. Token `kn-*` saja di kode baru (tanpa hex, tanpa
`text-[<12px]`, tanpa `!py-*`; tombol `primary-button`/`secondary-button` + `btn-sm` `whitespace-nowrap`);
`verify_ui_standard` sama dengan B (13).

| Layar | (1) tabel ⊂ kartu | (2) bantalan | (3) kepala kartu | (4) tombol mati | (5) status ikon+teks+warna | (6) cari/saring | (7) teks vs izin | (8) kosong/0 |
|---|---|---|---|---|---|---|---|---|
| SDM › Karyawan › kartu karyawan › **Riwayat Kompensasi** (baru, lebar penuh di bawah grid kartu) | 5 kolom + Aksi `col-sticky-end` (hanya pemegang `payroll.approve`): "Gaji pokok · komponen tetap" satu sel (gaji tebal + baris komponen), "Diajukan · disahkan oleh" satu sel dua baris, Alasan `max-w-[160px]`; hitungan isi-minimum ±110+150+140+160+110+85 ≈ 755 px ≤ ±760 px kartu di 1024 px (sidebar 220 px); `data-table head-wrap` dalam `overflow-x-auto` cadangan HP | `section-head` + `section-body`; memuat/galat/kosong `section-pad` | judul + satu tombol Muat ulang; "Ajukan perubahan" di badan | "Ajukan perubahan" mati + "Mengajukan perubahan butuh izin mengubah data karyawan." tertulis di samping | `RowBadge`: Menunggu disahkan (jam) · Berlaku (centang) · Akan berlaku (kalender) · Berakhir (riwayat) · Ditolak (silang) · Dibatalkan — `status-pill` + ikon + teks | riwayat per karyawan (beberapa baris; terurut terbaru dulu) — tanpa kotak cari | izin `hr.update` / `payroll.approve` (bukan nama peran); tanpa sahkan + ada baris menunggu: "Mengesahkan perubahan gaji butuh izin mengesahkan gaji." | kosong satu kalimat "Belum ada riwayat kompensasi. Gaji dibaca dari data karyawan sampai baris pertama dibuat." |
| — **Penugasan PT** | 5 kolom + Aksi `col-sticky-end` (≈ 645 px) | sama | judul saja; "Pindahkan ke PT lain" di badan | sama (alasan tertulis) | `RowBadge` sama | idem | idem | kosong: "Belum ada riwayat penugasan. PT dibaca dari data karyawan: {PT}." |
| Pop-up **Ajukan perubahan kompensasi** / **Pindahkan ke PT lain** | — | `FormModal` baku (grid 2 kolom → 1 kolom di HP) | — | "Tambah komponen tetap" mati + "Belum ada komponen tetap bulanan di PT ini." | — | — | — | Sahkan: `askConfirm` "Sahkan gaji pokok Rp … untuk {nama}, berlaku {tanggal}, di {PT}?"; Tolak: `askReason`; kirim ber-`Idempotency-Key` (`02` N4, N5) |
| Form **Ubah Karyawan** (`EmployeeFormDrawer`) | — | tetap | — | Gaji pokok & PT `disabled` + petunjuk "Ubah lewat Riwayat Kompensasi." tertulis; tunjangan teks hanya-baca + petunjuk (tombol tambah/hapus hilang) | — | — | label "Entitas (PT/CV)" → "PT" (glosarium) | — |

Belum diuji jalan di peramban (U15) — integrator.

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`38c715f`** — satu gate
untuk rantai gelombang 4 (PY-T2, TX-T2 (a/b) + cek layar, AG-T5 (a/b) + cek layar, CR-T2 (a/b), PM-T4):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`b62ef45`: 12 / 39) — tidak ada gate baru yang merah. "Tidak dijalankan" tambahan = ganti label
(`guard:atomic_claim SELF-TEST` 10 → 64 kasus, `guard:page_tabs` + uji-dirinya). Kuitansi: `bukti/PY-T2/gate_quick_receipt.md`,
`gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- Rantai gelombang 4 dipasang integrator berurutan di atas `8ac7059`: PY-T2 `5edef21` · `82ef1bb` → TX-T2 (a) `38b5c9b` · (b) `84744dc` · cek layar `15d3258` → AG-T5 (a) `31a8d54` · (b) `7747302` · cek layar `df23cb2` → CR-T2 (a) `2d9709e` · (b) `76a337d` → PM-T4 `38c715f`. Tiap commit diuji `tests_mem` penuh di worktree bantu sebelum dipetik (angka di bawah). Jest penuh di `38c715f`: **995 lulus** (957 + PY-T2 8 + TX-T2 7 + AG-T5 11 + CR-T2 5 + PM-T4 7; 35 suite gagal dimuat `cmdk`/`@radix-ui`, sama). Penjaga statik di `38c715f` = garis dasar kecuali `verify_auth_coverage` 27 → **26** (AG-T5); `verify_atomic_claim` 161/0, `verify_posting_coverage` 138/0, `verify_cash_single_door` 736/0, `verify_role_gate_ui` 31/0, `verify_detail_modal` 30/0. Glosarium KN_32: §9.18 PY-T2 · §9.19 TX-T2 · §9.20 AG-T5 · §9.21 CR-T2 · §9.22 PM-T4 (nomor pelaksana dirapikan integrator). Indeks wajib lapis A: 29 + PY-T2 2 + CR-T2 2 + PM-T4 1 = **34** (`check_required_indexes` 34/34 di data acuan).
- Dipasang tanpa bentrok di atas `5f193df` (HEAD tidak maju selama unit dikerjakan): **`5edef21`**. Uji jalan
  integrator lalu memperbaiki warna lencana riwayat: **`82ef1bb`** — "Berlaku" memakai `status-approved` (ungu), "Akan
  berlaku" hijau, "Berakhir" `status-closed` (kelas tidak ada → pil tanpa latar) → kini `status-done` (hijau) ·
  `status-shipped` (biru) · `status-draft` (netral); jest PY-T2 8/8 tetap hijau. `tests_mem` di T 1942/2/2 (pelaksana);
  sesudah TX-T2 (a) 1962 · (b) 1972 (rantai).
- Lingkungan A (data acuan sesudah `restore_demo`, kode `5edef21`; `bukti/PY-T2/integrator_lingkungan_A.txt`): lapis A
  `test_bp_PYT2_migrasi.py` **U1 lulus** (migrasi baca-saja di data acuan: 23 karyawan, nilai baris = master per PT) dan
  **U11 lulus** (dua pengesahan bersamaan → satu baris sah); `--apply` dilewati (butuh `KN_PYT2_TERAPKAN=1`).
  `test_bp_PK14_indeks_wajib.py`, `test_p13_audit.py` (kelas karyawan), `test_p14_history.py` lulus. Satu merah lama:
  `test_p13_audit.py::TestCustomerAudit::test_patch_customer_credit_limit` (PATCH plafon → 404 karena plafon tidak lagi
  lewat PATCH sejak PK-45/CR-T1; berkas uji di `5f193df` juga merah terhadap backend yang sama; tidak terkait PY-T2).
  `check_required_indexes` 31/31 (`5edef21`) → 34/34 di akhir rantai. INV-PY-2: WARN 23 karyawan tanpa riwayat
  (sebelum migrasi) — sesuai rancangan.
- **Regresi yang ditemukan PY-T3 (diperiksa ulang integrator di `38c715f`):** `hr_pay_components.earning_components`
  hanya membuat baris LEMBUR dan KOMISI di cabang **tanpa** `segments`; sejak PY-T2 proses reguler selalu mengirim
  potongan periode, jadi lembur dan komisi mesin **tidak masuk** slip reguler (bruto, PPh 21, gaji bersih ikut lebih
  kecil). Uji PY-T2 tidak menangkapnya (fixture tanpa lembur/komisi); uji setara PY-T3 (potret slip `5f193df` vs
  `82ef1bb`) menangkapnya. **Diperbaiki di PY-T3 (a)** (lihat `hasil/PY-T3.md`). Dampak data: hanya proses gaji yang
  dihitung dengan kode PY-T2 sebelum PY-T3 (di data acuan: proses semai `ent_ksc`); cabang ini belum dipasang ke
  produksi. Proses draf cukup dihitung ulang; proses yang sudah diposting/dibayar butuh proses susulan — H3, pemilik.
- Migrasi `--apply` hanya di database UJI lokal (untuk uji jalan): 23 baris kompensasi + 23 penugasan; pratinjau bruto
  November `ent_ksc` 96.300.000 sebelum = sesudah. **Data nyata = H3, menunggu pemilik.**
- Uji jalan (peramban zona Asia/Jakarta): SDM › Karyawan › kartu 360 — Riwayat Kompensasi (baris menunggu disahkan +
  Sahkan/Tolak, baris berlaku, baris berakhir "s.d. 31 Mei 2026") dan Penugasan PT: tabel = lebar kartu di 1280
  (1018 px) dan 1024 (762 px), `overflowX` 0; di 390 px (tampilan penuh) tabel bergulir di dalam kartu, Aksi lekat.
  Pop-up "Ajukan perubahan kompensasi" (komponen tetap terisi dari baris berlaku) dan "Pindahkan ke PT lain" rapi;
  form Ubah Karyawan: PT hanya-baca + "Ubah lewat Riwayat Kompensasi." (`bukti/PY-T2/cek_*.png`).

Pelaksana (catatan asli):

Belum dijalankan (lingkungan A milik integrator). Yang dijalankan pelaksana di lingkungan B (W, basis `5f193df`):

- `tests_mem`: B **1924 lulus / 2 dilewati / 2 xfail** (`bukti/PY-T2/tests_mem_B.txt`) → W **1942 / 2 / 2, 0 gagal**
  (`tests_mem_W.txt`; +17 uji PY-T2 + 1 kasus putaran KF-T8 untuk kunci baru).
- Jest: uji baru 8/8 (`pyt2RiwayatKompensasi`); kode lama merah (modul tidak ada, `bukti/PY-T2/jest_merah_lama.txt`);
  penuh HEAD murni **957** → W **965** (+8); 35 suite gagal dimuat di keduanya (`@radix-ui/primitive/is-development`,
  kendala lingkungan).
- `hitung_penjaga.sh`: **identik** B → W (`penjaga_B.txt`, `penjaga_W.txt`: auth 27 · ui_standard 13 · i18n 103 ·
  create_modal 6 · page_tabs 1 · to_list 5 · entity_label 2; lainnya 0/PASS). `verify_role_gate_ui` 31/0;
  `verify_atomic_claim` 160/0 + uji-diri 64 kasus (inventaris multi-koleksi tidak berubah — endpoint baru menulis lewat
  layanan); `verify_posting_coverage` 133/0; `verify_cash_single_door` 730/0; `verify_detail_modal` 30/0;
  `verify_permission_checked` 606/0; `verify_config_fallback` (+`--entity`) 158/0; `verify_config_text` 3283/0;
  `verify_payment_vocab` 1817/0; `verify_access_catalog_nav` 0; `verify_codebase_map` hijau; `gen_config_key_index
  --check` selaras; `audit_config_wiring --strict` hijau dan `check_nav_map` PASS (salinan berjalur W).

## Penggabungan

- HEAD tujuan: **`5f193df`** (`/home/user/KNHOST`, dibaca saja) = basis B — HEAD tidak maju selama unit dikerjakan, jadi
  semua berkas unit **disalin** dari W ke T (`scratchpad/wt29`; skrip `bukti/PY-T2/pyt2_gabung.sh`: sama dengan B →
  salin; beda → `git merge-file -p`; baru → salin). **Bentrok: tidak ada.** 33 berkas (26 diubah + 7 baru).
- Dibangkitkan ulang di T: `CODEBASE_MAP.md` (sama), `configKeyIndex.json` (`--check` selaras). `access_modules.py`
  tidak berubah (fixture akses tidak dibangkitkan). Hitungan uji lama: KF-T1 `PYT2_KUNCI = 1`, PK-14 lapis B
  `PYT2_INDEKS = 2`, lapis A 29 → **31** — dijumlahkan dengan unit lain yang masuk HEAD sesudah `5f193df` bila ada.
- Angka di T: `tests_mem` **1942 lulus / 2 dilewati / 2 xfail, 0 gagal** (`bukti/PY-T2/tests_mem_T.txt`; HEAD murni = B 1924); jest penuh HEAD murni **957** → T **965** (35 suite gagal dimuat di keduanya,
  `@radix-ui`); `hitung_penjaga.sh` **identik** HEAD (`penjaga_T.txt`); `verify_role_gate_ui` 31/0;
  `verify_atomic_claim` 160/0 + uji-diri 64 hijau; `verify_config_fallback` 158/0 dan `--entity` 158/0;
  `verify_payment_vocab` 1817/0; `verify_access_catalog_nav` 0; `verify_config_text` 3283/0; `verify_posting_coverage`
  133/0; `verify_cash_single_door` 730/0; `audit_config_wiring --strict` hijau dan `check_nav_map.py` PASS (salinan
  berjalur T).

## Menyimpang dari blueprint

1. **PT uji tersendiri** (PTA/PTB) menggantikan `ent_ksc`/`ent_kanda` di uji lapis B: data awal menyemai proses gaji
   reguler `ent_ksc` dua bulan sebelum jam sistem (bergantung tanggal hari uji dijalankan), sehingga Sep/Okt `ent_ksc`
   sudah ada dan tidak memuat K1 (pola PY-T1 menyimpang no. 12). Angka dan langkah sama.
2. **Baris sah paling awal berlaku sejak awal** (potongan hanya lahir dari perubahan): tanggal masuk / tanggal dibuat
   tidak memotong bulan pertama — prorata masuk/keluar tengah bulan di luar lingkup (PY-T3). Karyawan TANPA riwayat
   dibaca dari master (perilaku lama; jalur kembali spesifikasi "kembalikan pembaca ke master").
3. **`fixed_components` tidak dikirim** saat mengusulkan → disalin dari baris yang berlaku pada tanggal itu (kenaikan
   gaji pokok tidak menghapus tunjangan); `[]` = tanpa komponen tetap. Layar selalu mengirim daftarnya (terisi dari
   baris yang berlaku).
4. **`enqueue_input(status="pending")`** (PY-T1): masukan rapel harus `pending` (spesifikasi), sedangkan `enqueue_input`
   selalu `approved`. `hr_pay_inputs._employee` juga menerima karyawan yang punya penugasan sah di PT itu (karyawan
   pindah PT tetap bisa menerima masukan di PT lama/baru sebelum master berganti).
5. **PT masukan rapel** = PT karyawan pada akhir bulan berjalan (yang memuatnya di proses gaji bulan ini); selisih per
   periode dijumlah lintas PT yang membayar periode itu. Satu masukan per periode (kunci spesifikasi).
6. **Sahkan ulang baris yang sudah sah** → 409 "Baris yang sudah disahkan…", sesudah langkah lanjutan idempoten
   (`_rechain`, `apply_effective`, rapel) diulang — supaya pengesahan yang terputus di tengah bisa dilengkapi tanpa
   menambah masukan (U5 "sahkan lagi permintaan yang sama").
7. **Dasar BPJS & upah lembur** = Σ Gaji Pokok potongan periode (aturan `mati` = nilai akhir bulan; `hari_kalender` =
   gaji pokok terprorata). Sebelumnya: master saat dihitung.
8. **`apply_effective`** juga menyalin departemen/jabatan penugasan saat baris itu pertama berlaku (`applied_at`);
   INV-PY-2 hanya memeriksa tiga field spesifikasi. Karyawan aktif tanpa riwayat = **WARN** (bukan FAIL) di INV-PY-2
   sampai migrasi dijalankan (data nyata = H3), supaya gate data acuan tidak merah sebelum keputusan pemilik.
9. **Konsumen kunci** = `hr_compensation_service.py:segments` + `:prorata_mode` (pemilihan karyawan dan rapel membaca
   kunci yang sama lewat `prorata_mode`).
10. **Tabel Riwayat Kompensasi 5 kolom + Aksi** (bukan 7): "Gaji pokok" + "Komponen tetap" satu sel; "Diajukan oleh" +
    "Disahkan oleh" satu sel dua baris — semua isian spesifikasi tampil, tabel muat di kartu 1024 px (standar UI (1)).
11. **Idempotensi**: `/api/hr/compensation/`, `/api/hr/assignments/` masuk `IDEMPOTENT_PREFIXES` dan pola
    `^/api/hr/employees/[^/]+/(compensation|assignments)/?$` masuk `IDEMPOTENT_PATTERNS`; layar mengirim lewat
    `moneyPost` + `useIntentKey`.
12. **Migrasi** memakai `--apply` (pola PY-T1/PK-32); nilai gaji per orang tidak dicetak (data pribadi) — laporan per PT
    (Σ master = Σ baris "SAMA"/"BEDA") + daftar karyawan bertanggal masuk kosong + (mode `--apply`) pratinjau bruto
    bulan berjalan per PT sebelum = sesudah.
13. **Router baru** `routers/hr_compensation.py` (didaftarkan di `server.py`), bukan menambah `routers/hr.py`.

### Usulan koreksi berkas unit (teks pengganti persis; berkas unit tidak diubah pelaksana)

- Uji penerimaan, kolom Persiapan U5: "Proses September dan Oktober `posted` dengan 6.000.000" → "Proses September dan
  Oktober `posted` dengan 6.000.000 (PT uji tersendiri: data awal menyemai proses reguler `ent_ksc` dua bulan sebelum
  hari uji)".
- Keadaan sekarang, butir `hr_payroll_service.py:263` (`_sum_allowances`) → "`hr_payroll_service.py:406`
  (`earning_components(..., allowances=emp.get("allowances"))`, PY-T1)".
- Server, tabel fungsi, `segments`: tambahkan "Baris sah paling awal dianggap berlaku sejak awal (masuk/keluar tengah
  bulan = PY-T3)."

## Asumsi

- Dari spesifikasi: tanpa prorata PT pada akhir periode membayar sebulan penuh; rapel dibayar di bulan berjalan sebagai
  masukan `pending`; hitung ulang pajak tahunan per PT.
- Bawaan (`00` §4.1): pindah PT tidak membuat rapel (hanya baris kompensasi); pengesahan penugasan berlaku mundur ke
  periode yang sudah diposting tidak mengubah proses lama; satu orang boleh mengusulkan lalu mengesahkan (kontrol dua
  orang di luar lingkup spesifikasi).

## Keraguan dan titik henti

- **H3** — `scripts/migrate_hr_compensation_py_t2.py` hanya diuji di database tiruan; tidak dijalankan terhadap database
  `backend/.env`. Data acuan: integrator menjalankan mode baca-saja (lapis A `test_U1_migrasi_baca_saja_data_acuan`);
  `--apply` di data nyata = keputusan pemilik (ambil cadangan `hr_employees` dulu). **H6** tidak mungkin di data lama
  (koleksi baru); bila muncul kembar di data uji, indeks gagal dibuat → titik henti.
- Lapis A (U1 baca-saja/terapkan, U11 bersamaan, PK-14 31 indeks) ditulis, belum dijalankan — keunikan bersamaan di
  MongoDB asli = "belum teruji".
- Komponen tetap buatan pengguna: `create_component` (PY-T1) masih hanya `masukan`; jadi komponen tetap saat ini =
  TUNJANGAN berlabel (mis. "Jabatan"). Mesin PY-T2 sudah memuat komponen `tetap_bulanan` apa pun — membuka pembuatannya
  di layar Komponen & Masukan tidak termasuk unit ini.
- INV-PY-2 di data acuan sebelum migrasi: WARN (jumlah karyawan aktif tanpa riwayat), bukan FAIL.

# PY-T5 — Swalayan karyawan: slip tampil hanya setelah gaji dibayar, lengkap dengan riwayat dan rincian

- Commit awal: `4580bd9` (worktree kerja, basis B)        - Commit akhir: `b014a38`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PY-T5 (fitur; menutup temuan —; spesifikasi `docs/blueprint/unit/PY-T5.md`); keputusan K-37 (slip
  berkomponen); aturan "setelah dibayar" dari rancangan `09` §3.6 dijadikan pengaturan (`00` §4.1)
- Risiko rendah → satu serah-terima.

## Cek ulang "Keadaan sekarang" (spesifikasi dibaca di `3132cc4`; dicek di `4580bd9`)

| Butir spesifikasi | Hasil di HEAD awal |
|---|---|
| Daftar slip sendiri memuat slip sejak disahkan — `hr_payroll_service.py:596` (`my_payslips`) | Berlaku, bergeser — `:1230` (`status ∈ {posted, paid, approved}`, `.to_list(200)`) |
| Pemilik membuka slipnya lewat id dalam status apa pun — `routers/hr_payroll.py:254` (`_can_view_slip`), dipakai `:229` (`get_payslip`), `:240` (`payslip_pdf`) | Berlaku, bergeser — `:496`, `:471`, `:482` (pemilik diperiksa dulu → `True` untuk draf, dibatalkan, dianulir) |
| Endpoint daftar hanya butuh login dan berakhir `/me` — `routers/hr_payroll.py:223` | Berlaku, bergeser — `:464`; tercatat `login_only_endpoints.py:60` sebagai `milik_sendiri` (PR-T3) |
| Status slip mengikuti status proses — `hr_payroll_service.py:443` (`update_many`) | Berlaku, bergeser — `_set_run` `:812`. **Catatan PK-22:** klaim langkah `posting`/`paying`/`voiding` ditulis langsung ke proses (`:1039`, `:1144`, `:1088`), slip tetap berstatus asal (`approved`/`posted`) selama langkah berjalan → penentu ikut membaca status proses |
| Kartu Profil Saya hanya slip terakhir & jumlah slip — `MyPayslipCard.jsx:25` (`latest`), `:40` (`slip tersedia`); dipasang `EmployeeSelfService.jsx:9` | Berlaku — baris sama; dipasang di kisi empat kartu `EmployeeSelfService.jsx:213`. Galat dimuat **diam** (`catch (_) { /* noop */ }`) |
| Menu Profil Saya selalu tersedia — `access_modules.py:14` (`ALWAYS_NAV`) | Berlaku, bergeser — `:17` |
| PDF dibuka lewat `payrollUtils.js:32` (`openPayslipPdf`) | Berlaku, bergeser — `:72` |
| PK-22 status `cancelled`/`void`; PY-T1 `components[]` dan `run_type` | Berlaku — `RUN_STATUS_LABEL` `hr_payroll_service.py:28` (+ `posting`, `paying`, `voiding`, `rejected` data lama); slip memuat `components`, `run_type`, `bank` (`compute_payslip` `:551–567`). PY-T2/PY-T3 tidak mengubah status atau tampilan slip |

## PY-T5 — slip terlihat pemiliknya terlalu dini; kartu hanya slip terakhir

- Berlaku di HEAD: ya (bukti merah `bukti/PY-T5/merah_kode_lama.txt`: U4 200 untuk slip draf; U1 slip `approved`
  terlihat; U2 slip `posted` terlihat; U6/U3/U10 kunci tidak ada di registry; U7 urutan & isian; U8 tanpa `years`;
  U6b `ImportError hr_payslip_self`. Jest `bukti/PY-T5/jest_merah_kode_lama.txt`: 4/4 merah — kartu lama "Slip Gaji
  Terakhir … 2 slip tersedia", tanpa riwayat, galat diam).
- Akar masalah: daftar swalayan menyaring status slip dengan daftar tetap `{approved, posted, paid}` di kode; detail &
  PDF ber-id memeriksa pemilik tanpa melihat status sama sekali; kartu hanya mengambil slip pertama.
- Perubahan perilaku:
  - **Penentu** `services/hr_payslip_self.py:slip_visible_to_owner(slip, run=…, since=…)` (murni: `terbit(since,
    status_slip, status_proses)`): benar bila status slip DAN status prosesnya termasuk daftar pengaturan PT slip itu —
    `dibayar` → `{paid}`, `disahkan` → `{approved, posted, paid}`. `draft`, `pending_approval`, `cancelled`, `voiding`,
    `void` (dan `rejected` data lama) selalu salah; `posting`/`paying` dibaca sebagai `approved`/`posted`.
  - **Pengaturan** `hr.slip_swalayan_sejak` (kelompok Gaji & SDM, sub-judul "Lembur, komisi & kepegawaian"; `enum`
    `dibayar` "Setelah gaji dibayar" · `disahkan` "Sejak penggajian disahkan"; bawaan `dibayar`; global → PT; risiko
    sedang; izin `hr.manage_payroll`; pembaca `services/hr_payslip_self.py:visible_since`, galat → bawaan registry).
  - `GET /api/hr/payslips/me?year=&period=` → `{employee, visible_since, year, years, payslips}`; tiap slip: `id`,
    `number`, `period`, `run_type`, `status`, `paid_at`, `paid_date`, `gross`, `net`, `pph21`, `components[]` (`code`,
    `label`, `kind`, `amount`, `rate`, `basis_period`), `bank` — tanpa id/nama karyawan, akun buku besar, sumber masukan.
    Urut periode menurun lalu tanggal bayar menurun. `year` bawaan tahun berjalan WIB (`book_date.tanggal_buku`);
    `year` salah bentuk → 400 "Tahun harus berbentuk TTTT, mis. 2026."; `period` salah → 400 "Periode harus berbentuk
    TTTT-BB, mis. 2026-10.". Akun tanpa karyawan → `{employee: null, years: [], payslips: []}`.
  - `GET /api/hr/payslips/{id}` dan `…/pdf`: pemegang `hr.view` diperiksa **lebih dulu** (tidak berubah: slip apa pun);
    pemilik tanpa `hr.view` → slip belum terbit 404 "Slip gaji ini belum terbit."; slip orang lain tetap 403.
  - Jalur lama `hr_payroll_service.my_payslips` dihapus (satu-satunya pemanggil = router; dicari di seluruh repo,
    `02` §5 D8).
  - Kartu **Slip Gaji Saya** (`MyPayslipCard.jsx`, isi diganti): ringkasan slip terakhir ("Periode {bulan tahun}",
    "Gaji bersih diterima", nominal, "Dibayar {tanggal}", "Lihat slip (PDF)"); **Riwayat slip** dengan pilihan tahun
    (`FilterChips` dari `years`), kolom Periode · Jenis · Dibayar · Gaji bersih, tiap baris "Rincian" (kelompok
    Pendapatan dan Potongan, lalu Gaji bersih) dan "PDF"; keadaan memuat "Memuat slip…", galat "Slip belum bisa
    dimuat." + "Coba lagi", kosong "Belum ada slip gaji yang terbit." + "Slip muncul setelah gaji dibayar." / "…setelah
    penggajian disahkan." (`visible_since`). Kartu kini selebar halaman di bawah kisi kartu Absen · Cuti & Lembur · KPI.
- Berkas berubah: lihat "Berkas".
- Fixture disiapkan langsung vs proses bisnis dijalankan: lihat "Uji penerimaan".
- Dampak pada modul terkait: layar HR (Proses Gaji, Cari slip, `Employee360Panel`) memakai `hr.view` → tidak berubah.
  Karyawan yang hari ini melihat slip sejak disahkan tidak melihatnya lagi sampai dibayar (RISIKO spesifikasi; teks
  kosong menjelaskan; balik: `hr.slip_swalayan_sejak` global → `disahkan`).
- Keterbatasan / yang belum diuji: U13 (uji jalan di peramban, lingkungan A) — integrator.
- Status: implemented_pending_review

## Berkas

| Berkas | Isi |
|---|---|
| `backend/services/hr_payslip_self.py` (baru) | `KUNCI_SLIP`, `TERBIT`, `SELALU_TERTUTUP`, `visible_since`, `terbit`, `slip_visible_to_owner`, `owner_row`, `my_payslips` |
| `backend/config_catalog_ops.py` | kunci `hr.slip_swalayan_sejak` (sesudah `hr.prorata_perubahan_gaji`) |
| `backend/routers/hr_payroll.py` | `my_payslips` (`year`, `period`, 400), `_can_view_slip` (hr.view dulu, pemilik → penentu, 404) — hanya dua fungsi di ujung berkas; kepala & impor tidak disentuh |
| `backend/services/hr_payroll_service.py` | `my_payslips` lama dihapus (ujung berkas) |
| `backend/tests_mem/test_PYT5_swalayan_slip.py` (baru) | U1–U10 + U6b |
| `backend/tests_mem/test_KFT1_izin_pengaturan.py` | `PYT5_KUNCI = 1` (U04 katalog) |
| `frontend/src/features/hr/MyPayslipCard.jsx` | kartu Slip Gaji Saya (isi diganti) |
| `frontend/src/features/hr/EmployeeSelfService.jsx` | kisi kartu 3 kolom; kartu slip selebar halaman di bawahnya |
| `frontend/src/features/__tests__/pyt5SlipSaya.test.js` (baru) | U11, U12, keadaan kosong, tahun tanpa slip |
| `frontend/src/features/settings/config/configKeyIndex.json` | dibangkitkan (`gen_config_key_index.py`, +1 kunci) |
| `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (§9.27 di W, §9.28 di T — "slip terbit", "slip gaji saya", "riwayat slip"), `CODEBASE_MAP.md` (dibangkitkan) | dokumen |

Tidak ada koleksi, field, indeks, izin, menu, atau endpoint tulis baru (`ENTITY_REGISTRY.md`, `access_modules.py`,
fixture akses, inventaris multi-koleksi, `KN_13` tidak berubah).

## Uji penerimaan

Berkas `backend/tests_mem/test_PYT5_swalayan_slip.py`. "Kode lama" = salinan bersih `4580bd9` (`git archive`) dengan
berkas uji yang sama (`bukti/PY-T5/merah_kode_lama.txt`: 9 merah, 2 lulus). Fixture (disisipkan): "hari ini" 15 Des 2026,
BPJS `ent_kanda` mati (lapisan PT), E1/E2 `ent_kanda` tertaut akun `sales` e1/e2 (tanpa `hr.view`), karyawan lain
`ent_kanda` nonaktif, rekening Bank PT; U3: karyawan E3 `ent_ksc` + proses & slip `ent_ksc` `approved`. Alur lewat HTTP:
buat proses, ajukan, sahkan, posting, bayar (endpoint PK-22), anulir, batal, masukan THR, pengaturan, swalayan.

| ID | Lapis | Kode lama | Kode baru |
|---|---|---|---|
| U1 | B | merah: slip `approved` ada di `payslips` | lulus — `payslips` kosong, `years` kosong, `visible_since` `dibayar`; detail ber-id 404 |
| U2 | B | merah: slip `posted` terlihat | lulus — `posted` kosong; sesudah `paid` satu slip: bruto 8.800.000, PPh 21 154.000, `net` 8.646.000, "Tunjangan — Transport" 500.000, "Gaji Pokok" 8.000.000, "PPh 21" 154.000, `paid_at` = proses, `paid_date` WIB, `bank`; isian hanya daftar swalayan; `years` `[2026]` |
| U3 | B | merah: kunci tidak ada di registry (404) | lulus — `ent_kanda` `disahkan`: e1 melihat slip `approved` (`paid_at` kosong), detail 200; karyawan `ent_ksc` (`approved`, bawaan PT-nya) kosong + detail 404 |
| U4 | B | merah: pemilik 200 untuk slip draf | lulus — detail & PDF 404 "Slip gaji ini belum terbit." dua kali; admin (`hr.view`) 200 dua kali |
| U5 | B | lulus (regresi — slip orang lain sudah 403) | lulus — detail & PDF 403 |
| U6 | B | merah: kunci tidak ada | lulus — `disahkan`: proses November `posted` terlihat, lalu dianulir → hilang; proses November kedua disahkan lalu dibatalkan → tidak muncul; detail kedua slip 404 |
| U6b (tambahan) | B (murni) | merah: `ImportError hr_payslip_self` | lulus — tabel penentu: status tertutup selalu salah di kedua pilihan; `posting`/`paying` = status asal; `voiding` salah |
| U7 | B | merah: urutan & isian lama | lulus — `year=2026`: `[(2026-10, thr) 7.314.000, (2026-10, regular) 8.646.000]`, `years [2026]`; `year=2025` kosong; `period=2026-10` dua slip; `year=26` → 400; `period=2026-13` → 400 |
| U8 | B | merah: jawaban tanpa `years` | lulus — 200 `{employee: null, years: [], payslips: []}` |
| U9 | B | lulus (regresi) | lulus — PDF 200 `application/pdf` `%PDF`; detail 200 `net` 8.646.000 |
| U10 | B | merah: kunci tidak ada | lulus — isian registry spesifikasi; putaran `t1_config` (`test_KFT8_putaran_pengaturan.putaran`) tanpa gagal; "diposting" → 400 |
| U11 | layar (jest) | merah: "Slip Gaji Terakhir…2 slip tersedia" | lulus — dua baris "Reguler" dan "THR"; status bayar `status-pill status-paid` + ikon + teks; rincian reguler: Pendapatan/Potongan, "Gaji Pokok", "Tunjangan — Transport", "PPh 21", "Gaji bersih" Rp 8.646.000 |
| U12 | layar (jest) | merah: galat diam (tidak ada pesan) | lulus — "Slip belum bisa dimuat." + "Coba lagi" (tanpa isi galat server); Coba lagi memuat ulang |
| kosong (tambahan) | layar (jest) | merah | lulus — "Belum ada slip gaji yang terbit." + keterangan menurut `visible_since` |
| tahun tanpa slip (tambahan) | layar (jest) | merah | lulus — tahun berjalan kosong → tahun terbaru ber-slip dibuka; pilih tahun lain memuat ulang; ringkasan tetap slip terakhir |
| U13 | layar (uji jalan, A) | — | **belum diuji jalan** — integrator (lihat "Untuk integrator") |

Hitungan tangan (komentar kepala berkas uji, sama dengan PY-T1): E1 reguler Okt bruto 8.000.000 + 500.000 + 300.000 =
8.800.000 → 1,75 % → PPh 21 154.000 → bersih 8.646.000. THR Okt: bruto pajak bulan 16.800.000 → 5 % → 840.000; dipotong
di slip THR 840.000 − 154.000 = 686.000 → bersih 8.000.000 − 686.000 = 7.314.000.

## Cek layar

Dari kode (pelaksana); potret 1280/1024/390 px oleh integrator. Tidak ada `text-[Npx]`, hex, `!py-*`, atau `<button>`
bergaya sendiri di `MyPayslipCard.jsx` (kartu lama: 7 `text-[Npx]`, 7 hex, 1 `!py-1.5` — semuanya hilang);
`verify_ui_standard` total sama (11). Warna lewat token `kn-*`.

| Layar | (1) tabel ⊂ kartu | (2) bantalan | (3) kepala kartu | (4) tombol mati | (5) status ikon+teks+warna | (6) cari/saring | (7) teks vs izin | (8) kosong/0 |
|---|---|---|---|---|---|---|---|---|
| Profil Saya › kartu **Slip Gaji Saya** | bukan tabel: daftar baris. HP (< 640 px): dua kolom tiga baris per slip (Periode · Jenis / Dibayar · Gaji bersih / Rincian · PDF rata kanan); ≥ 640 px lima kolom berjudul "Periode · Jenis · Dibayar · Gaji bersih · (aksi)" dengan `minmax(0,…)` → tidak melebar; ringkasan di atas riwayat (teks kiri, tombol PDF kanan mulai 640 px), di samping kiri riwayat (260 px) mulai 1280 px — di 1024 px (sidebar 220 px, badan kartu ±740 px) riwayat tetap selebar kartu: 4 kolom isi ±335 px + aksi ±175 px muat; kartu selebar halaman (bukan seperempat kisi) | `section-head` + `section-body` | judul + ikon saja; pilihan tahun di bilah "Riwayat slip" di badan | tombol PDF mati hanya selama satu PDF dibuka (label "Membuka…") — tidak ada tombol mati beralasan | "Dibayar {tanggal}" = `status-pill status-paid` + ikon centang; "Belum dibayar" (pilihan `disahkan`) = `status-pill status-pending` + ikon jam (kelas yang ADA) | ±12–15 slip per tahun; saringan tahun (`FilterChips`, bergulir di HP) | tidak ada teks izin; hanya slip sendiri | satu keadaan kosong ("Belum ada slip gaji yang terbit." + kapan slip muncul); tahun tanpa slip "Tidak ada slip yang terbit di tahun {tahun}."; galat ≠ kosong ("Slip belum bisa dimuat." + Coba lagi); gagal buka PDF → bilah galat sendiri |
| Profil Saya (kisi kartu) | kisi 1 → 2 (768 px) → 3 kolom (1024 px): Absen Hari Ini, Cuti & Lembur, KPI Saya | tidak berubah | tidak berubah | — | tidak berubah | — | — | — |

Tombol: "Lihat slip (PDF)" `primary-button` lebar penuh; "Rincian" `ghost-button btn-sm` (`aria-expanded`,
`aria-controls`); "PDF" `secondary-button btn-sm`; semua `whitespace-nowrap`. Label jenis lewat `runTypeLabel`
(Reguler · THR · Susulan), periode lewat `formatPeriod`, tanggal `formatDate` (WIB), rupiah `formatCurrency`.

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`efc1cc6`** — satu gate
untuk CR-T3 ((a) `2ac8e6c` · (b) `945da6e` · cek layar `eaba57f`), PY-T5 (`b014a38`), PY-T4 (`61cf7a1` · cek layar `efc1cc6`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`fc95d36`: 12 / 39). Kuitansi: `bukti/PY-T5/gate_quick_receipt.md`, `gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- HEAD cabang tetap `eaba57f` sejak pelaksana menggabung; T disalin apa adanya → **`b014a38`**. `tests_mem` di T
  2211/2/2, jest 1044 (pelaksana, pohon sama — tidak diulang, arahan pemilik 15 Nov).
- Uji jalan **U13** (integrator, data acuan, peramban zona Asia/Jakarta): Profil Saya (ESS) karyawan Finance tanpa slip →
  keadaan kosong satu kalimat ("Belum ada slip gaji yang terbit. Slip muncul setelah …"); dengan `hr.slip_swalayan_sejak` =
  "disahkan" untuk `ent_ksc` (database uji lokal) karyawan Sales melihat kartu **Slip Gaji Saya**: ringkasan Oktober 2026 Rp
  5.712.822 "Belum dibayar" + Lihat slip (PDF), riwayat tahun 2026 (pil tahun), baris berstatus ikon+teks ("Belum Dibayar",
  `status-pending`), Rincian dan PDF per baris — 1280/1024 lima kolom, 390 px dua kolom × tiga baris; `overflowX` 0
  (`bukti/PY-T5/cek_*.png`). Dengan bawaan "dibayar" slip `approved` itu tertutup (U1/U2 lapis B). Tidak ada cacat.
- **Untuk pemilik (perilaku berubah):** slip yang baru disahkan/diposting kini hilang dari Profil Saya sampai dibayar;
  membalik: setel `hr.slip_swalayan_sejak` = "Sejak penggajian disahkan".

Pelaksana (catatan asli):

Belum dijalankan (lingkungan A milik integrator). Yang dijalankan pelaksana di lingkungan B:

- `tests_mem` penuh (sekali per keadaan, "hemat uji"): B **2126 lulus / 2 dilewati / 2 xfail** (salinan bersih
  `git archive 4580bd9`; `bukti/PY-T5/tests_mem_B.txt`) → W **2138 / 2 / 2**, 0 gagal (+12: 11 uji PY-T5 + 1 kasus
  putaran KF-T8 untuk kunci baru; `tests_mem_W.txt`). Uji terarah hijau: `hijau_kode_baru.txt`.
- Jest penuh: B **1034** → W **1038** (+4 `pyt5SlipSaya.test.js`); 35 suite gagal dimuat di keduanya (`cmdk`/`@radix-ui`,
  kendala lingkungan; daftar suite sama — `jest_B.txt`, `jest_W.txt`). Sesudah jalan penuh W, kartu hanya diubah kelas
  tata letaknya (ringkasan di samping riwayat mulai 1280 px, bukan 768 px) → `pyt5SlipSaya` + `prt7TombolIzin` diulang
  27/27; jest penuh keadaan akhir dijalankan di T.
- `hitung_penjaga.sh`: **identik** B dan W (`penjaga_B.txt`, `penjaga_W.txt`: auth 26 · ui_standard 11 · i18n 103 ·
  create_modal 6 · page_tabs 1 · to_list 5 · entity_label 2; lainnya 0/PASS — catatan: brief menyebut ui_standard 13,
  terukur 11 di B). Penjaga lain (`penjaga_lain.txt`): `verify_role_gate_ui` 31/0; `verify_config_fallback` 159/0 →
  160/0 (+`--entity` 160/0); `verify_payment_vocab` 1836/0; `verify_config_text` 3409/0; `verify_permission_checked`
  615/0; `verify_atomic_claim` 161/0 (tanpa endpoint tulis baru); `verify_posting_coverage` 138/0;
  `verify_cash_single_door` 741/0; `verify_detail_modal` 29/0; `verify_ui_contrast` 58/0; `verify_access_catalog_nav`
  0; `verify_codebase_map` PASS; `audit_config_wiring --strict` hijau (salinan berjalur W).
- Bukti merah: `merah_kode_lama.txt` (pytest, kode `4580bd9`), `jest_merah_kode_lama.txt` (jest, kartu lama).

## Uji lama yang disesuaikan

| Uji | Sebab | Penyesuaian |
|---|---|---|
| `tests_mem/test_KFT1_izin_pengaturan.py` U04 | +1 kunci berizin `hr.manage_payroll` | `PYT5_KUNCI = 1` di jumlah katalog (U02 tetap: tidak berizin `settings.manage`) |
| `tests_mem/test_KFT8_putaran_pengaturan.py` | parametrize atas registry | +1 kasus otomatis (`[hr.slip_swalayan_sejak]`), tanpa perubahan berkas |

## Penggabungan

- HEAD tujuan: **`eaba57f`** (`/home/user/KNHOST`, dibaca saja; = B + `41c0b60` STATUS + CR-T3 (a) `2ac8e6c` · (b)
  `945da6e` · cek layar `eaba57f`). HEAD tidak bergerak selama penggabungan dan uji T (dicek ulang sesudahnya).
- T (`scratchpad/wt22`) disetel ulang ke HEAD; berkas unit digabung tiga arah dengan basis B (`scratchpad/pyt5_gabung.py`
  = `gabung_unit.py` dengan berkas sementara sendiri):
  - sama dengan B → disalin: `config_catalog_ops.py`, `routers/hr_payroll.py`, `services/hr_payroll_service.py`,
    `EmployeeSelfService.jsx`, `MyPayslipCard.jsx`; baru → disalin: `services/hr_payslip_self.py`,
    `tests_mem/test_PYT5_swalayan_slip.py`, `__tests__/pyt5SlipSaya.test.js`;
  - tiga arah tanpa bentrok: `memory/PRD.md`;
  - **bentrok, kedua perilaku dipertahankan**: `tests_mem/test_KFT1_izin_pengaturan.py` — `CRT3_KUNCI = 9` (HEAD) dan
    `PYT5_KUNCI = 1` keduanya didefinisikan dan dijumlahkan di U04 (`… + PYT3_KUNCI + CRT3_KUNCI + PYT5_KUNCI`);
    `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` — §9.27 Gerbang kredit (CR-T3) tetap, bagian unit ini menjadi **§9.28**;
  - dibangkitkan ulang: `CODEBASE_MAP.md` (`gen_codebase_map.py`), `configKeyIndex.json` (`gen_config_key_index.py`,
    +1 kunci). `access_modules.py` tidak berubah → fixture akses tidak dibangkitkan.
- Angka di T (`bukti/PY-T5/*_T.txt`, `penjaga_HEAD.txt`):
  - `tests_mem` **2211 lulus / 2 dilewati / 2 xfail, 0 gagal** (HEAD murni tidak dijalankan ulang: log integrasi CR-T3
    `scratchpad/crt3_logs/T2_tm.txt` = 2199 / 2 / 2 → +12 = uji unit ini).
  - Jest penuh **1044** (keadaan akhir kartu; log integrasi CR-T3 `T2_jest.txt` = 1040 → +4); 35 suite gagal dimuat,
    daftar sama dengan W.
  - `hitung_penjaga.sh` T **identik** dengan HEAD murni (salinan `git archive eaba57f`): auth 26 · ui_standard 11 ·
    i18n 102 · create_modal 5 · page_tabs 1 · to_list 5 · entity_label 2. `verify_role_gate_ui` 31/0;
    `verify_config_fallback` 161/0 dan `--entity` 161/0; `verify_payment_vocab` 1843/0; `verify_access_catalog_nav` 0;
    `verify_config_text` 3472/0; `verify_codebase_map` PASS; `audit_config_wiring --strict` hijau dan `check_nav_map.py`
    PASS (salinan berjalur T).

## Menyimpang dari blueprint

1. **Penentu di berkas sendiri** `services/hr_payslip_self.py` (spesifikasi: `hr_payroll_service.py`) — supaya
   penggabungan dengan PY-T4 (sedang mengubah `hr_payroll_service.py` dan `routers/hr_payroll.py`) bersih: perubahan
   di dua berkas bersama hanya di ujung berkas (dua handler + `_can_view_slip`; hapus `my_payslips` lama), impor lokal,
   kepala/doc-string router tidak disentuh. `consumers` kunci = `services/hr_payslip_self.py:visible_since` (satu-satunya
   pembaca; `slip_visible_to_owner` memanggilnya).
2. **Status proses ikut dinilai**, bukan hanya status slip: selama `voiding` slip masih `posted` (PK-22 menulis klaim ke
   proses saja), jadi tanpa ini slip yang sedang dianulir terlihat pada pilihan `disahkan`. `posting`/`paying` = status
   asalnya (slip tidak hilang di tengah langkah). `rejected` (data lama) juga selalu tertutup.
3. **Isian tambahan jawaban** `/me`: `status` (layar menulis "Belum dibayar" pada pilihan `disahkan`), `paid_date`
   (tanggal bayar WIB; memakai `paid_date` proses bila ada — PY-T4 menambahnya — selain itu `paid_at` → WIB), `year`
   (tahun yang dijawab). U8 (akun tanpa karyawan) persis tiga kunci spesifikasi.
4. **`year` dan `period` diperiksa** (400 dengan pesan); bila `period` diisi, tahunnya = tahun periode.
5. **Urutan dalam satu periode**: tanggal bayar menurun (THR dibayar sesudah reguler tampil lebih dulu); slip belum
   dibayar (pilihan `disahkan`) di atas.
6. **Teks galat**: "Slip belum bisa dimuat." + tombol "Coba lagi" bawaan `ErrorNotice` (tampil "Slip belum bisa dimuat. ⟳
   Coba lagi") — kalimat spesifikasi tanpa mengulang "Coba lagi" dua kali.
7. **Letak kartu**: dari kisi empat kartu ke kartu selebar halaman di bawah kisi (kisi kini tiga kartu: Absen, Cuti &
   Lembur, KPI Saya). Riwayat lima kolom + rincian tidak muat di seperempat lebar 1280 px (±250 px) dan akan
   meregangkan tiga kartu lain sekisi; KM-T5 dipasang di bawah kartu ini.
8. **Riwayat berbentuk daftar** (bukan `<table>`) — utuh di HP 390 px (kartu, bukan tabel lebar); judul kolom tampil
   mulai 640 px.
9. **Tahun berjalan tanpa slip** (mis. awal Januari): kartu langsung membuka tahun terbaru yang punya slip; ringkasan
   "slip terakhir" tetap dari tahun terbaru walau tahun lain dipilih.
10. **Sub-judul pengaturan** (isian wajib KF-T4, tidak disebut spesifikasi): `lembur` "Lembur, komisi & kepegawaian"
    (9 → 10 kunci); tidak membuat sub-judul baru.
11. **Komponen di jawaban**: hanya `code`, `label`, `kind`, `amount`, `rate`, `basis_period`. Komponen tanggungan
    perusahaan ikut terkirim (tercetak di PDF slip) tetapi rincian layar hanya Pendapatan dan Potongan.
12. **U2 "bayar"** lewat endpoint bayar yang berlaku di HEAD (PK-22: akun kas pemetaan + rekening tunggal PT) dalam satu
    pembantu uji `_bayar`; bila PY-T4 mengganti cara bayar, cukup pembantu itu yang disesuaikan.

### Usulan koreksi berkas unit (teks pengganti persis; berkas unit tidak diubah pelaksana)

- Server, kalimat pertama: "Satu penentu di `hr_payroll_service.py`: `async def slip_visible_to_owner(slip) -> bool`"
  → "Satu penentu di `services/hr_payslip_self.py`: `async def slip_visible_to_owner(slip, run=…, *, since=None) ->
  bool` — status slip **dan status prosesnya** (`posting`/`paying` = status asal)". Alasan: menyimpang no. 1–2.
- Pengaturan: "`consumers` `services/hr_payroll_service.py:slip_visible_to_owner`" →
  "`section` `lembur` · `consumers` `services/hr_payslip_self.py:visible_since`".
- Keadaan sekarang: baris `hr_payroll_service.py:596` → `:1230`; `routers/hr_payroll.py:254/229/240/223` →
  `:496/471/482/464`; `:443` → `_set_run` `:812`; `access_modules.py:14` → `:17`; `payrollUtils.js:32` → `:72`.

## Asumsi

- Dari spesifikasi: bawaan `dibayar`; draf/diajukan/dibatalkan/dianulir tertutup tanpa sakelar; `visible_since` =
  pengaturan PT karyawan saat ini (karyawan pindah PT: tiap slip dinilai dengan pengaturan PT slip itu).
- Bawaan (`00` §4.1): status antara proses = status asal; `year` bawaan tahun berjalan WIB dari `book_date` (satu jam
  "hari ini" WIB).

## Keraguan dan titik henti

- **Perilaku berubah untuk karyawan** (RISIKO spesifikasi): sejak unit ini slip yang disahkan/diposting tetapi belum
  dibayar hilang dari Profil Saya. Balik: `hr.slip_swalayan_sejak` global → "Sejak penggajian disahkan".
- **PY-T4** (paralel): definisi "dibayar" = status `paid` (PK-22) seperti di HEAD; `paid_date` PY-T4 dipakai bila ada.
  Bila PY-T4 menambah status bayar sebagian/per karyawan, penentu perlu menambah status itu ke `TERBIT`.
- Data pribadi gaji: jawaban `/me` hanya slip karyawan yang tertaut akun itu; detail/PDF orang lain tetap 403; pemegang
  `hr.view` tidak berubah. Tidak ada H3 (tanpa skrip data), H4 (tanpa tarif), H5 (tanpa sakelar tulis PT nyata).
- U13 (uji jalan) belum dijalankan.

## Untuk integrator (U13, lingkungan A)

Data acuan: proses gaji `posted`/`paid` ada 2 (PK-22, baca-saja). Uji jalan: login akun yang tertaut karyawan (mis. akun
karyawan seed; atau tautkan lewat Akun & Akses), Profil Saya: sebelum proses dibayar kartu menulis "Belum ada slip gaji
yang terbit." + "Slip muncul setelah gaji dibayar."; sesudah Bayar (Proses Gaji) kartu "Slip Gaji Saya" menampilkan
periode itu, "Lihat slip (PDF)" membuka PDF; buka "Rincian". Potret 1280/1024/390 px.

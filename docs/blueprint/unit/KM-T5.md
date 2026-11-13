# KM-T5 — Tampilkan kartu "Capaian & Insentif Saya" untuk sales; pindahkan dan hapus layar insentif lama

| | |
|---|---|
| Gelombang | Modul — Meja Insentif |
| Jenis | fitur |
| Risiko | rendah |
| Prasyarat | KM-T4, MN-T1 |
| Menutup temuan | — |
| Keputusan | K-22, K-46 |
| Standar | §3.1 (Z1, Z2, Z3, Z5), §4 (L1–L5, L7), §5 (D1, D8), §6, §7 |
| Lingkungan uji | B untuk endpoint; layar (uji komponen dan uji jalan di A) |

## Tujuan

Sales melihat capaian dan insentifnya sendiri di satu kartu: target, capaian berjalan, dan — setelah lembar disahkan —
rincian tiap komponen beserta angka dasarnya. Tiga tempat insentif lama (dua sub-tab di CRM dan satu tab di Pengaturan)
hilang dari menu; yang masih diperlukan PT bermode komisi otomatis dipindah ke Kinerja & Insentif.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

- Beranda Sales menampilkan "Komisi MTD" hasil mesin: `frontend/src/features/home/SalesHome.jsx:112` (`Komisi MTD`),
  rincian per SKU `frontend/src/features/home/SalesHome.jsx:145` (`sales-home-commission-breakdown`), dan tren
  `frontend/src/features/home/SalesHome.jsx:183` (`Tren Komisi`). Sumbernya memanggil mesin tiap dibuka:
  `backend/services/home_service.py:57` (`compute_commission`), `backend/services/home_service.py:102` (`mtd_accrual`).
- Layar HP sales memanggil mesin yang sama: `frontend/src/features/sales/mobile/MobileCollectionTargets.jsx:153`
  (`sales/commission`).
- Beranda admin menampilkan "Insentif Sales" = jumlah hasil mesin semua sales:
  `backend/services/home_service.py:468` (`payout`), `frontend/src/features/home/AdminHome.jsx:175` (`incentive_payout`).
- Tiga tempat lama: CRM › "Kinerja Sales" dan "Skema (Arsip)", `frontend/src/features/crm/CrmView.jsx:25`
  (`salesforce`), `frontend/src/features/crm/CrmView.jsx:26` (`schemes`); Pengaturan › Penjualan › "Komisi & Insentif",
  `frontend/src/config/hubTabs.js:254` (`incentive-rates`), dirender `frontend/src/AppViewRouter.jsx:304`
  (`IncentiveRatesEditor`).
- Isi layar lama: KPI, komisi, tombol akrual, papan peringkat, dan "Set Target",
  `frontend/src/features/crm/SalesForceDashboard.jsx:104` (`sf-set-target`),
  `frontend/src/features/crm/SalesForceDashboard.jsx:138` (`sf-incentive-gl`); penyunting target dan jenjang,
  `frontend/src/features/crm/IncentiveSchemeEditor.jsx:16` (`IncentiveSchemeEditor`), yang pilihan "Tipe Periode"-nya
  tidak mengubah periode yang disimpan: `frontend/src/features/crm/IncentiveSchemeEditor.jsx:196` (`Tipe Periode`);
  tarif per kategori `frontend/src/features/crm/IncentiveRatesEditor.jsx:72` (`IncentiveRatesEditor`).
- Endpoint lama: `backend/routers/crm.py:260` (`get_sales_kpi`), `backend/routers/crm.py:266` (`get_leaderboard`),
  `backend/routers/crm.py:293` (`get_commission`), `backend/routers/crm.py:299` (`get_commission_history`),
  `backend/routers/crm.py:368` (`create_target`), `backend/routers/crm.py:423` (`create_incentive`),
  `backend/routers/incentive_rates.py:43` (`list_rates`). Siapa boleh melihat sales lain ditentukan nama peran:
  `backend/routers/crm.py:254` (`role_in`).
- Daftar sales untuk pilihan dan papan peringkat hanya memuat peran persis `sales` (PR-UX-04):
  `backend/routers/crm.py:48` (`list_sales_users`), `backend/services/sales_force_service.py:456` (`leaderboard`).
- Profil Saya memuat kartu slip, belum ada kartu insentif: `frontend/src/features/hr/EmployeeSelfService.jsx:9`
  (`MyPayslipCard`).

## Perubahan

### Data

Tidak ada koleksi atau field baru. Koleksi `sales_incentives` dan `incentive_rates` tidak dihapus (masih dibaca mesin
komisi pada PT bermode otomatis).

### Server

**`GET /api/incentive/me`** — hanya butuh login (Z3: data milik sendiri). Parameter `period` (`YYYY-MM`, bawaan bulan
berjalan WIB). PT = PT aktif pengguna; `sales_id` selalu id pelaku dan tidak bisa dikirim. Jawaban:

```text
{period, entity_id, mode,                      # mode = hr.payroll_commission_mode PT itu
 achievement: {target_sales, omzet_bersih, pct_omzet, target_collection, uang_masuk, pct_pencairan,
               realisasi_harga_pct, facts_as_of},          # dari pengumpul KM-T2; tanpa margin dan tanpa piutang
 sheets: [{sheet_number, pay_period, status,   # hanya lembar approved / paid; hanya baris milik pelaku
           lines: [{component_name, basis_label, amount, is_adjustment, note, paid_run_number,
                    snapshot: {target_sales, omzet_bersih, target_collection, uang_masuk, realisasi_harga_pct}}]}],
 auto_commission: {mtd, projection_month_end} | null}      # terisi hanya bila mode PT masih komisi otomatis
```

Baris lembar `draft` dan `submitted` tidak pernah dikirim. Pelaku tanpa fakta, target, maupun baris lembar mendapat
`achievement` nol dan `sheets: []` (200, bukan 403).

Perubahan pada endpoint yang ada:

| Tempat | Perubahan |
|---|---|
| `sales_home` (`GET /api/home/sales`) | Menambah `incentive_mode`. Untuk mode `sheet` dan `off`: mesin komisi tidak dipanggil, `commission` = `null`. Mode otomatis: seperti sekarang |
| `admin_home` (kartu "Insentif Sales" di beranda admin) | Per PT bermode `sheet`: `incentive_payout` = Σ nominal baris lembar disahkan yang belum dibayar; PT lain: seperti sekarang. Ditambah `incentive_payout_label`: "Belum dibayar" atau "Estimasi bulan ini" |
| `GET /api/sales-users`, `leaderboard`, `GET /api/sales/my-rank` | Daftar sales dari `sales_roster` (KM-T1), sehingga akun berperan kustom ikut |
| `GET /api/sales/commission`, `…/commission-history` | Untuk PT bermode `sheet` atau `off`: 409 "PT ini tidak memakai komisi otomatis. Lihat Capaian & Insentif." |
| `POST /api/sales-targets`, `GET /api/sales-targets` | Dihapus setelah pencarian membuktikan tidak ada pemanggil di `frontend/src` selain berkas yang dihapus unit ini; pemakai lain memakai `/api/incentive/targets` |
| `GET`/`POST /api/sales-incentives`, `/api/incentive-rates` | Tetap, untuk bagian "Komisi otomatis (cara lama)" |

### Pengaturan

Tidak ada kunci baru.

### Izin dan peran

Tidak ada pasangan izin baru. `nav` modul akses `incentive` tidak berubah; id `incentive-rates` dicabut dari `nav` modul
mana pun yang memuatnya dan dari `HUB_TABS["settings-sales"]`.

### Layar

**Kartu baru** — komponen baru `frontend/src/features/incentive/MyIncentiveCard.jsx`, dipasang di tiga tempat: Beranda
Sales (`SalesHome.jsx`, menggantikan kartu "Komisi MTD", "Rincian Komisi per Kategori / SKU", dan "Tren Komisi" untuk
PT bermode `sheet` atau `off`), Profil Saya (`EmployeeSelfService.jsx`, di bawah kartu slip; tampil hanya bila
`achievement` atau `sheets` berisi), dan layar HP (`MobileCollectionTargets.jsx`, bagian Target). Isi kartu:

- Judul: **Capaian & Insentif Saya — {bulan tahun}**, dengan pemilih bulan.
- Tiga baris capaian: "Omzet" — "Rp … dari target Rp … ({persen} %)"; "Uang masuk" — "Rp … dari target Rp …
  ({persen} %)"; "Realisasi harga" — "{persen} %". Target 0 ditulis "target belum diisi".
- Bagian **Insentif yang sudah disahkan**: per baris "{komponen} — {periode dasar}" dan nominalnya; di bawahnya
  "Dibayar bersama gaji {bulan tahun}" (lembar `approved`) atau "Sudah dibayar (gaji {bulan tahun})" (`paid`); tautan
  "Angka dasar" membuka potret: "Omzet Rp … / target Rp …", "Uang masuk Rp … / target Rp …", "Realisasi harga … %".
  Baris penyesuaian diberi tanda "Penyesuaian" dan catatannya. Kosong: "Belum ada insentif yang disahkan untuk Anda."
- Catatan kaki: "Nominal insentif diputuskan pimpinan dengan melihat capaian. Tidak ada rumus otomatis."
- Hanya untuk PT bermode komisi otomatis: baris "Komisi berjalan (hitungan otomatis)" — "Rp …", dan kartu lama di
  Beranda Sales tetap tampil.
- Keadaan: memuat "Memuat capaian…"; galat "Capaian belum bisa dimuat. Coba lagi."; "Data per pukul {HH:MM} WIB".

**Layar lama:**

| Berkas | Tindakan |
|---|---|
| `frontend/src/features/crm/CrmView.jsx` | Sub-tab `salesforce` ("Kinerja Sales") dan `schemes` ("Skema (Arsip)") dicabut |
| `frontend/src/features/crm/SalesForceDashboard.jsx` | Dihapus. KPI dan papan peringkat digantikan tab Capaian; "Set Target" digantikan Target & Aturan; kartu "Akrual Insentif → GL" dipindah (baris berikut) |
| `frontend/src/features/crm/IncentiveSchemeEditor.jsx` | Bagian target dihapus; bagian jenjang dipindah menjadi `frontend/src/features/incentive/LegacySchemeEditor.jsx` (berkas baru) |
| `frontend/src/features/crm/IncentiveRatesEditor.jsx` | Dipindah menjadi `frontend/src/features/incentive/LegacyRatesEditor.jsx` (berkas baru); tab "Komisi & Insentif" dicabut dari hub Pengaturan › Penjualan; view `incentive-rates` dijadikan alias ke `incentive-setup` di `viewAliases.js` |
| Tab **Target & Aturan** (`IncentiveSetupView.jsx`, lahir di KM-T1) | Bagian baru **Komisi otomatis (cara lama)**, tampil hanya bila mode PT bukan `sheet` dan bukan `off`: tarif per kategori, jenjang, dan tombol akrual bulanan ("Bukukan akrual komisi {bulan}") dengan konfirmasi yang menyebut nominal dan PT. Keterangan: "Bagian ini hilang setelah PT beralih ke Lembar Insentif." |
| `frontend/src/features/home/AdminHome.jsx` | Sub-teks kartu "Insentif Sales" memakai `incentive_payout_label` |

Kode baru tidak memakai `roleIs`; tombol memakai `canCurrent("incentive", aksi)`.

## Uji penerimaan

Fixture: `ent_kanda` bermode `sheet`; `ent_ksc` bermode bawaan. Andi dan Budi sales di `ent_kanda`. Capaian Andi
Oktober 2026 (dari fakta): target omzet 800 jt, omzet bersih 1.000 jt, target pencairan 750 jt, uang masuk 700 jt,
realisasi harga 86,2 %. Lembar L1 (`pay_period` 2026-11): Andi Rp 2.000.000 dan Rp 3.000.000; Budi Rp 3.500.000.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | L1 masih `submitted` | Andi: `GET /api/incentive/me?period=2026-10` | `achievement`: 800.000.000 · 1.000.000.000 · 125,0 · 750.000.000 · 700.000.000 · 93,3 · 86,2; `sheets` kosong; tidak ada `margin_pct` |
| U2 | B | L1 `approved` | Andi: `GET …/me?period=2026-11` | Satu lembar, dua baris Andi berjumlah 5.000.000 (2 + 3 jt); baris Budi tidak ada; `auto_commission` `null` |
| U3 | B | U2 | Budi: `GET …/me?period=2026-11&sales_id={Andi}` | Hanya baris Budi 3.500.000 (parameter diabaikan) |
| U4 | B | Gaji November diposting | Andi: `GET …/me?period=2026-11` | `status` `paid`; tiap baris ber-`paid_run_number` |
| U5 | B | Sales `ent_ksc`, tarif Rp 500 per meter, batas margin 0, pesanan 1.000 m lunas bulan ini | `GET …/me` | `mode` `accrue_then_settle`; `auto_commission.mtd` 500.000 (1.000 × 500) |
| U6 | B | — | Andi: `GET /api/home/sales`; sales `ent_ksc`: sama | Andi: `incentive_mode` `sheet`, `commission` `null`. Sales `ent_ksc`: `commission.mtd_accrual` 500.000 |
| U7 | B | Akun gudang tanpa pesanan | `GET /api/incentive/me` | 200; semua angka 0; `sheets` kosong |
| U8 | B | Akun berperan kustom beracuan `sales` | `GET /api/sales-users`; `GET /api/sales/leaderboard` | Akun itu ada di keduanya |
| U9 | B | — | Andi: `GET /api/sales/commission?period=2026-11` | 409 "PT ini tidak memakai komisi otomatis. Lihat Capaian & Insentif." |
| U10 | B | L1 `approved`, gaji belum diposting; lalu diposting | Admin dengan PT aktif `ent_kanda`: data beranda admin | `incentive_payout` 8.500.000 berlabel "Belum dibayar"; lalu 0 |
| U11 | B | — | `POST /api/sales-targets`; jalankan `fe_be_routes.py` | 404 atau 405; tidak ada panggilan layar tanpa rute |
| U12 | B | Andi punya baris lembar di `ent_kanda` dan `ent_ksc` | `GET …/me` dengan PT aktif `ent_kanda` | Hanya lembar `ent_kanda` |
| U13 | layar (uji komponen) | Data U2 | Render `MyIncentiveCard` | Teks "Insentif Bulanan — Okt 2026", "Rp 2.000.000", "Dibayar bersama gaji November 2026"; tidak ada teks "Komisi" |
| U14 | layar (uji komponen) | — | Render `CrmView` sebagai manajer; baca `HUB_TABS["settings-sales"]` | Tidak ada "Kinerja Sales", "Skema (Arsip)", maupun `incentive-rates` |
| U15 | layar (uji jalan) | U2, login Andi | Buka Beranda dan Profil Saya | Kartu "Capaian & Insentif Saya" tampil di keduanya; tidak ada "Komisi MTD" |
| U16 | layar (uji jalan) | Login manajer, PT aktif `ent_ksc` lalu `ent_kanda` | Buka Kinerja & Insentif › Target & Aturan | Di `ent_ksc` bagian "Komisi otomatis (cara lama)" tampil; di `ent_kanda` tidak |

## Langkah kerja

1. `backend/tests_mem/test_KMT5_kartu_sales.py`: U1–U12 (merah).
2. `GET /api/incentive/me`; perubahan `sales_home`, `admin_home`, daftar sales, penolakan komisi untuk mode baru.
3. `MyIncentiveCard` dan pemasangannya di tiga tempat; uji komponen U13.
4. Pindahkan penyunting tarif dan jenjang; bagian "Komisi otomatis (cara lama)"; cabut sub-tab dan tab; alias view.
5. Cari pemanggil (`rg "sales-targets|SalesForceDashboard|IncentiveSchemeEditor|incentive-rates" frontend/src`), lalu
   hapus berkas dan endpoint yang sudah tanpa pemanggil; U11, U14. Uji jalan U15, U16. Gate.

## Dokumen ikut berubah

`docs/KN_13_NAVIGATION_MAP.md` (CRM, Pengaturan › Penjualan, Kinerja & Insentif); `CODEBASE_MAP.md` (berkas pindah dan
hapus); `memory/PRD.md`; `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("Capaian & Insentif Saya").

## Di luar lingkup

- Menghapus mesin komisi (`compute_commission`), `incentive_rates`, dan `sales_incentives`: baru boleh setelah tidak ada
  PT bermode komisi otomatis; dicatat sebagai pekerjaan lanjutan di laporan, tidak dikerjakan di sini.
- Kartu slip dan riwayat slip di Profil Saya → PY-T5.
- Keberatan sales atas angka (rancangan `05` §10) tidak dibangun.
- Cakupan data per peran untuk endpoint KPI lama (`_kpi_scope`) → PR-T4.

## Asumsi dan risiko

- `ASUMSI:` sales hanya melihat nominal setelah lembar disahkan; lembar draf dan diajukan tidak terlihat olehnya.
- `ASUMSI:` kartu tidak menampilkan margin, sisa piutang, maupun angka sales lain.
- `ASUMSI:` selama masih ada PT bermode komisi otomatis, penyunting tarif dan jenjang dipindah, bukan dihapus.
- `RISIKO:` tautan lama ke `incentive-rates` atau sub-tab CRM putus. Penangkal: alias view dan U14. Membatalkan:
  kembalikan dua entri tab; berkas lama dipulihkan dari riwayat git.

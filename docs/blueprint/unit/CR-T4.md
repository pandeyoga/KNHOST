# CR-T4 — Denda berlapis PT → pelanggan → rencana, dihitung dari jadwal tagihan

| | |
|---|---|
| Gelombang | Modul piutang dan kredit |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | PK-08, CR-T2 |
| Menutup temuan | CR-07 |
| Keputusan | K-30 |
| Standar | §1 (P1, P4), §2 (2.1, 2.2, 2.4), §3.1 (Z1, Z2), §4 (L1, L5, L6), §5 (D1, D2, D8), §6 |
| Lingkungan uji | B |

## Tujuan

Usulan denda lahir untuk **semua** tagihan yang telat, bukan hanya pesanan yang punya rencana cicilan. Aturan denda
seorang pelanggan (tarif khusus, atau bebas denda dengan alasan dan masa berlaku) diatur dari kartu pelanggan lewat
pengajuan perubahan kredit, dan aturan khusus satu rencana bisa diisi di form rencana.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`. PK-08 (prasyarat) mengubah jurnal, hitungan hari lintas bulan, dan cara bayar
denda di berkas yang sama; cek ulang baris di `HEAD`.

| Fakta | Jangkar |
|---|---|
| Aturan denda dibaca berlapis global → PT → pelanggan lewat resolver, lalu ditimpa `plan.penalty` | `backend/services/penalty_service.py:59` (`penalty_policy`), `backend/services/penalty_service.py:83` (`over`) |
| Lima kunci aturan mendukung lapisan `customer`, tetapi layar Pusat Pengaturan hanya menawarkan Global dan PT | `backend/config_catalog_payment.py:20` (`GC`), `backend/config_catalog_core.py:140` (`customer`), `frontend/src/features/settings/config/SettingsScopeBar.jsx:66` (`cfg-scope-type`) |
| Lapisan pelanggan resolver hanya berkunci id pelanggan — tidak bisa berbeda per PT | `backend/services/penalty_service.py:67` (`customer_id`) |
| Job harian hanya memindai `payment_plans` aktif | `backend/services/penalty_service.py:584` (`job_penalty_accrual`), `backend/services/scheduler_service.py:145` (`job_penalty_accrual`) |
| Pesanan tanpa rencana hanya dihitung lewat tombol di umur piutang, dengan jatuh tempo = tanggal pesanan + termin profil | `backend/services/penalty_service.py:219` (`accrue_order`), `backend/routers/ar_aging.py:58` (`ar_aging_accrue`) |
| Dasar denda bawaan = sisa baris yang telat; rumus harian `dasar × tarif × hari ÷ 30` | `backend/services/penalty_service.py:154` (`line_out`), `backend/services/penalty_service.py:109` (`raw`) |
| Mode `off` membuat mesin melewati rencana itu; tidak ada alasan maupun masa berlaku | `backend/services/penalty_service.py:144` (`mode`) |
| Taksiran denda di umur piutang membulatkan ke bulan penuh, berbeda dari nota | `backend/services/ar_aging_service.py:81` (`months`) |
| Form rencana bayar tidak punya isian denda walau `plan.penalty` disimpan | `backend/services/payment_plan_service.py:319` (`penalty`) |

## Perubahan

### Data

Tidak ada koleksi baru. `customer_credit_profiles.penalty_rule` (disediakan CR-T1) mulai dibaca mesin:

| Field | Tipe | Aturan |
|---|---|---|
| `mode` | `ikut_pt` · `khusus` · `bebas` | Bawaan `ikut_pt` |
| `rate_pct_per_month`, `cap_pct`, `grace_days` | angka atau `null` | Hanya saat `khusus`; `null` = ikut PT untuk unsur itu |
| `base` | `installment` · `outstanding` · `""` | Sama dengan pilihan `payment.penalty_base` |
| `reason` | string | Wajib (≥ 5 huruf) saat `bebas` |
| `valid_until` | `YYYY-MM-DD` | Wajib saat `bebas`; sesudah lewat, aturan dibaca sebagai `ikut_pt` |

Nota denda (`penalties.policy_snapshot`, sudah ada) mendapat `sources`: asal tiap unsur (`global` · `pt` · `pelanggan` ·
`rencana`).

Skrip baru `scripts/migrate_penalty_customer_layer.py` (`--dry-run`; H3): mencari nilai lapisan `customer` yang
tersimpan untuk lima kunci di bawah, lalu menuliskannya ke `penalty_rule` profil (PT = `customers.entity_id`) dan
mengosongkan lapisan itu dengan `clear_layer`.

### Server

`penalty_service.penalty_policy(entity_id, customer_id, plan)` — tanda tangan tetap, urutan baru:

1. Global → PT lewat resolver dengan konteks `{"entity_id"}` saja.
2. Profil kredit (pelanggan, PT): `khusus` menimpa unsur yang terisi; `bebas` yang masih berlaku menyetel `mode: off`
   dan mengisi `waiver: {reason, valid_until}`.
3. `plan.penalty` (rencana) menimpa unsur yang terisi — tetap paling khusus.
4. Jawaban tambah `sources`.

Perubahan lain:

| Tempat | Perubahan |
|---|---|
| `job_penalty_accrual`, `accrue_customer` | Memindai semua jadwal hidup (`origin` `term` maupun `manual`). Karena CR-T2 memberi jadwal pada setiap pesanan yang menimbulkan piutang, pesanan tanpa rencana cicilan ikut terhitung |
| `accrue_plan` | Baris yang dibaca = `overdue_lines(plan)` seperti sekarang; dasar = sisa baris (`payment.penalty_base` bawaan `installment`, K-30). Pelanggan `bebas` → tidak ada nota baru; nota draf yang sudah ada tidak disentuh |
| `accrue_order` dan cabang "pesanan tanpa rencana" | Dihapus (D8); `POST /api/ar/aging/{customer_id}/accrue-penalties` tetap ada dan memanggil `accrue_customer` |
| `ar_aging_service._denda_estimate`, `get_ar_config` | Memakai `penalty_policy` dan `compute_amount` yang sama, sehingga taksiran = nota |
| Registry | `scopes` lima kunci (`payment.penalty_mode`, `payment.penalty_base`, `payment.penalty_cap_pct`, `ar.denda_rate_pct_per_month`, `ar.grace_days`) menjadi `("global", "entity")`. Lapisan pelanggan hanya dari profil kredit — satu pemilik (D1) |
| `credit_profile_service.submit` | Memvalidasi `penalty_rule` menurut tabel Data |

| Endpoint | Izin | Jawaban |
|---|---|---|
| `GET /api/customers/{id}/penalty-policy?entity_id=` | `penalty.view` + `can_view_credit` | `{effective: {mode, rate_pct_per_month, base, cap_pct, grace_days, min_amount}, sources: {...}, waiver}` |

Galat pengajuan: `bebas` tanpa alasan atau tanpa tanggal → 400 "Bebas denda wajib beralasan dan punya tanggal berakhir.";
tarif di luar 0–100 → 400 "Tarif denda harus antara 0 dan 100 % per bulan."

Bentuk nota tetap seperti hasil PK-08 (satu nota per baris tagihan per bulan). Layar mengelompokkannya per pelanggan.

### Pengaturan

Tidak ada kunci baru. Lima kunci yang ada kehilangan lapisan `customer` (lihat Server); `consumers` tetap.

### Izin dan peran

Tidak ada pasangan baru. Mengubah aturan denda pelanggan = mengajukan dan memutus perubahan kredit
(`credit_profile.update`, `credit_profile.approve`; kontrol `ubah_profil_kredit`).

### Layar

- Kartu pelanggan › tab **Kredit** (dari CR-T1), bagian baru **Aturan denda**: nilai yang berlaku beserta asalnya
  ("ikut PT", "khusus pelanggan"), dan di pop-up "Ajukan perubahan": pilihan **Ikut PT** · **Khusus** · **Bebas denda**;
  isian "Tarif denda (% per bulan)", "Dasar hitung" [Sisa tagihan yang telat · Seluruh sisa pesanan], "Batas atas (%
  dari dasar)", "Hari tenggang"; untuk bebas denda: "Alasan", "Berlaku sampai". Pelanggan bebas denda diberi lencana
  "Bebas denda s.d. {tanggal}".
- Form rencana bayar (`PaymentPlanBuilder.jsx`): bagian lipat **Aturan denda khusus rencana ini** berisi empat isian
  angka yang sama; keterangan "Kosong = mengikuti aturan pelanggan atau PT."
- Panel denda (`PenaltyPanel.jsx`): tiap nota menulis "Aturan dari: {PT · pelanggan · rencana}".

## Uji penerimaan

Fixture **D1**: `ent_kanda`; kunci bawaan (`ar.denda_rate_pct_per_month` 2, `ar.grace_days` 0, `payment.penalty_mode`
`draft`, `payment.penalty_base` `installment`, `payment.penalty_min_amount` 10.000); pelanggan P; jadwal `origin: term`
dengan satu baris Rp 5.000.000 jatuh tempo 2026-10-01, belum dibayar; tanggal uji 2026-10-31 (telat 30 hari).

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | D1 | Jalankan `job_penalty_accrual` | Satu nota draf Rp 100.000 (5.000.000 × 2 % × 30 ÷ 30) untuk pesanan yang tidak punya rencana cicilan; `sources.rate_pct_per_month == "global"` |
| U2 | B | D1; profil P `penalty_rule: {mode: khusus, rate_pct_per_month: 1}` (disetujui) | Job | Nota Rp 50.000 (5.000.000 × 1 % × 30 ÷ 30); sumber `pelanggan` |
| U3 | B | D1; pelanggan Q di `ent_ksc` dengan baris sama; `ar.denda_rate_pct_per_month` = 3 pada `ent_ksc` | Job | Q Rp 150.000; P tetap Rp 100.000 — PT lain tidak berubah |
| U4 | B | D1; profil P `bebas`, alasan "Kesepakatan direksi", `valid_until` 2026-12-31 | Job | Tidak ada nota untuk P |
| U5 | B | U4 dengan `valid_until` 2026-10-30 (sudah lewat) | Job | Nota Rp 100.000 |
| U6 | B | U2; rencana manual untuk pesanan itu dengan `penalty.rate_pct_per_month: 0.5` dan baris yang sama | Job | Nota Rp 25.000 (5.000.000 × 0,5 %); sumber `rencana` |
| U7 | B | D1; profil P `khusus`, `grace_days: 10` | Job | Nota Rp 66.666,67 (5.000.000 × 2 % × 20 ÷ 30) |
| U8 | B | D1; profil P `khusus`, `cap_pct: 1` | Job | Nota Rp 50.000 (batas 1 % × 5.000.000; hitungan mentah 100.000) |
| U9 | B | D1; baris sudah dibayar Rp 2.000.000 | Job | Nota Rp 60.000 (sisa 3.000.000 × 2 %) |
| U10 | B | D1 dengan baris bersisa Rp 400.000 | Job | Tidak ada nota (8.000 < minimum 10.000) |
| U11 | B | U1; nota diterbitkan, dibayar Rp 60.000, lalu dibebaskan | Baca saldo akun piutang denda untuk nota itu | 0, tidak negatif (regresi PK-08) |
| U12 | B | D1 | `sls` mengajukan `bebas` (belum diputus); job | Nota Rp 100.000 tetap lahir; setelah `mgr` menyetujui dan job dijalankan di bulan berikutnya, tidak ada nota baru |
| U13 | B | D1 telat 45 hari (tanggal uji 2026-11-15) | `GET /api/ar/aging/{P}` lalu job | Taksiran denda = nota = Rp 150.000 (5.000.000 × 2 % × 45 ÷ 30); sebelum unit ini taksirannya 200.000 |
| U14 | B | — | Tulis `payment.penalty_mode` pada lapisan pelanggan lewat API Pusat Pengaturan | 400 (lapisan tidak didukung); putaran `t1_config.py` lima kunci lulus untuk global dan PT |
| U15 | B | peran uji baku | **Tanpa Acuan** + `penalty.view`: `GET …/penalty-policy`; **Manajer Kosong**; **Sopir** | 200; 403; 403 |
| U16 | B | fixture: nilai lapisan pelanggan `ar.denda_rate_pct_per_month` = 1,5 untuk P | Jalankan fungsi migrasi dua kali | Profil P `khusus` bertarif 1,5; lapisan pelanggan kosong; putaran kedua tanpa perubahan |
| U17 | layar (uji jalan) | U2 | Buka kartu P › Kredit, lalu form rencana bayar | Bagian "Aturan denda" menulis tarif 1 % "khusus pelanggan"; form rencana punya bagian aturan denda |

## Langkah kerja

1. `backend/tests_mem/test_CRT4_denda_berlapis.py`: U1–U16; merah kecuali U11.
2. `penalty_policy` berlapis + `sources`; validasi `penalty_rule`; endpoint baca. U2–U8, U12, U15 hijau.
3. Job memindai semua jadwal; hapus `accrue_order`; taksiran umur piutang. U1, U9, U10, U13 hijau.
4. Cabut lapisan `customer` dari lima kunci; skrip migrasi. U14, U16 hijau.
5. Layar; U17; `scripts/audit_config_wiring.py` tidak bertambah merah; gate; laporan dengan contoh angka U1 dan U2.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`penalty_rule`, `policy_snapshot.sources`), `CODEBASE_MAP.md` (skrip migrasi), `memory/PRD.md`.

## Di luar lingkup

- Jurnal denda, hari telat lintas bulan, bayar denda lewat kas → PK-08 (prasyarat).
- Satu nota gabungan per pelanggan per bulan (usulan `06` §3.6): belum ada unitnya; unit ini hanya mengelompokkan di layar.
- Antrean nota draf di daftar kerja kredit → CR-T5.

## Asumsi dan risiko

- `ASUMSI:` lapisan pelanggan diambil dari profil kredit per (pelanggan, PT), bukan dari lapisan `customer` resolver,
  karena lapisan resolver tidak mengenal PT dan akan menjadi penyunting kedua untuk angka yang sama. Akibatnya layar
  lapisan pelanggan yang dibuat KF-T5 tidak lagi memuat lima kunci denda ini (hilang sendiri karena `scopes` berubah);
  nilai yang sudah diisi lewat layar itu dipindahkan skrip migrasi.
- `ASUMSI:` bebas denda wajib bertanggal berakhir (rancangan: "alasan + berlaku sampai"); tidak ada bebas selamanya.
- `ASUMSI:` mode bawaan tetap `draft` (K-30: "sama dengan hari ini").
- `RISIKO:` setelah job memindai semua jadwal, jumlah nota draf bisa naik tajam pada putaran pertama. Nota draf tidak
  berjurnal, jadi aman; laporan memuat jumlahnya pada data acuan. Membatalkan: batasi job ke `origin: manual`.

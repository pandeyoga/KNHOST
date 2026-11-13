# KM-T4 — Sambungkan Lembar Insentif ke gaji dan buku besar; matikan komisi otomatis per PT

| | |
|---|---|
| Gelombang | Modul — Meja Insentif |
| Jenis | fitur |
| Risiko | tinggi |
| Prasyarat | KM-T3, PY-T1 |
| Menutup temuan | KM-07, PY-06 |
| Keputusan | K-13, K-22, K-26 |
| Standar | §1 (P1–P4, P6–P10), §2.1, §2.2, §2.4, §3.1, §3.4 (N1, N4, N5), §4 (L4–L6, L8), §5 (D1, D2, D8), §6 |
| Lingkungan uji | keduanya (B untuk alur dan jurnal; A untuk dua pengesahan bersamaan) |

**Titik henti H5.** Unit ini membangun sakelar per PT dan seluruh alurnya, lalu berhenti: nilai sakelar PT nyata tidak
diubah agen. Pemilik menyalakannya setelah mencocokkan Capaian dan lembar dengan rekap manualnya minimal satu periode.

## Tujuan

Di PT yang sudah dialihkan, lembar yang disahkan langsung menjadi beban dan hutang insentif, tiap barisnya menjadi baris
tersendiri di slip gaji periode bayarnya, dan gaji melunasi hutang itu persis sebesar baris yang dimuat. Komisi otomatis
tidak lagi masuk slip PT tersebut, sehingga insentif tidak terbayar dua kali. PT yang belum dialihkan berjalan seperti
sekarang.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`; PK-22, PY-T1, dan KM-T3 (prasyarat) mengubah sebagian — cek ulang di laporannya.

- Akun yang dipakai insentif: beban `backend/services/gl_service.py:184` (`ACC_BEBAN_INSENTIF`, 6-5000) dan hutang
  `backend/services/gl_service.py:185` (`ACC_HUTANG_INSENTIF`, 2-1500). Akrual: Dr beban / Cr hutang sebesar hasil
  mesin komisi saat tombol ditekan, `backend/services/gl_service.py:2919` (`_balanced_pair`).
- Gaji memuat komisi mesin tanpa membaca mode PT: `backend/services/hr_payroll_service.py:245` (`_commission_for`);
  mode hanya disalin ke proses, `backend/services/hr_payroll_service.py:358` (`payroll_commission_mode`).
- Jurnal gaji mengenal dua cabang: `accrue_then_settle` → Dr hutang insentif; nilai lain apa pun → Dr beban insentif:
  `backend/services/gl_service.py:3078` (`accrue_then_settle`). Jadi nilai `off` hari ini berarti "beban saat gaji",
  bukan "mati" (PY-06).
- Pilihan terdaftar: `accrue_then_settle`, `pay_on_invoice`, `off`: `backend/config_catalog_ops.py:545`
  (`hr.payroll_commission_mode`); bawaan `backend/services/hr_service.py:46` (`payroll_commission_mode`).
- KM-07: daftar sales untuk akrual memakai peran persis `sales`, `backend/services/gl_service.py:2909`
  (`sales_users`), sedangkan gaji memakai peran acuan, `backend/services/hr_payroll_service.py:250` (`role_in`).
  `incentive_unit` disimpan, `backend/routers/incentive_rates.py:23` (`incentive_unit`), tetapi mesin memakai jumlah
  satuan dasar baris: `backend/services/sales_force_service.py:361` (`base_qty`); kuncinya
  `backend/config_catalog_core.py:274` (`commission.incentive_unit`).
- Satu akun hanya tertaut ke satu karyawan, dan karyawan milik satu PT: `backend/routers/hr.py:256` (`user_id`),
  `backend/routers/hr.py:305` (`entity_id`).
- Antar-PT non-dagang yang ada: akun `backend/services/gl_service.py:157` (`ACC_IC_AR`, 1-1250) dan
  `backend/services/gl_service.py:167` (`ACC_IC_AP`, 2-1250); jurnal dua buku
  `backend/services/interco_money_service.py:108` (`twin_je`); kas kembar
  `backend/services/interco_money_service.py:70` (`twin_cash`); saldo non-dagang hanya menjumlah pinjaman dan pindah
  aset, `backend/services/interco_money_service.py:146` (`non_trade_outstanding`); eliminasinya
  `backend/services/interco_money_service.py:163` (`sync_non_trade_elimination`).

Yang dipakai dari unit lain: `enqueue_input`, `cancel_input`, komponen gaji ber-`bucket` (PY-T1); `post_durable` dan
`posting_registry` (PK-18); `journal_date` (PK-22); pembantu jurnal kembar hasil PK-06; `sales_roster` (KM-T1).

## Perubahan

### Data

- `incentive_sheets` (ditambah): `gl_status`, `gl_error`, `journal_entry_id`, `journal_date`, `payroll_linked` (ya bila
  disahkan saat PT bermode `sheet`), status antara `approving`. Baris: `employee_id` (wajib saat disahkan bila
  `payroll_linked`), `pay_entity_id` (PT induk karyawan), `input_key` (`isheet:<id lembar>:<id baris>`), `paid_run_id`.
- `hr_pay_components`: isi awal tiap PT ditambah `INSENTIF` — pendapatan, `masukan`, `taxable`, `bucket: commission`,
  jenis proses `regular` dan `susulan`, `system`.
- Koleksi baru `interco_charges` (tagihan antar-PT non-dagang): `id` (`icc_…`), `number` (`ICC-`), `kind`
  (`incentive`), `from_entity_id` (PT penagih = PT induk karyawan), `to_entity_id` (PT tertagih = PT lembar), `amount`,
  `outstanding`, `status` (`open` · `settled`), `source` (`{run_id, run_number, lines: [{sheet_id, line_id, amount}]}`),
  `journals`, `gl_status`, jejak. Indeks unik (`source.run_id`, `to_entity_id`).
- `incentive_rates`: `incentive_unit` tidak lagi diterima maupun dikirim; dokumen lama dibiarkan.

### Server

**1. Sakelar per PT.** `hr.payroll_commission_mode` mendapat pilihan `sheet` (lihat Pengaturan). Satu pembaca baru
`commission_mode(entity_id)` di `hr_payroll_service.py` dipakai semua tempat:

| Mode PT | Komisi mesin di slip | Lembar disahkan | Jurnal gaji untuk kolom `commission` |
|---|---|---|---|
| `accrue_then_settle` (bawaan) | Ya, seperti sekarang | Hanya keputusan: tanpa jurnal, tanpa masukan (`payroll_linked: false`, `gl_status: "not_required"`) | Seperti hasil PK-22 |
| `off` | **0** — mesin tidak dipanggil | Sama seperti di atas | Tidak ada baris insentif |
| `sheet` | **0** — mesin tidak dipanggil | Jurnal akrual + masukan gaji | Dr `ACC_HUTANG_INSENTIF` sebesar Σ baris `INSENTIF` di slip |
| nilai lain yang tersimpan | Seperti sekarang | Hanya keputusan | Seperti hasil PK-22 |

`_commission_for` mengembalikan 0 untuk `off` dan `sheet`. `POST /api/sales/incentive/post-gl` menolak 409 untuk `off`
dan `sheet` dengan pesan PK-22. Untuk mode `accrue_then_settle`, daftar sales akrual manual memakai `sales_roster`.

**2. Mengesahkan lembar di PT bermode `sheet`** (melanjutkan `approve_sheet` KM-T3; urutan `02` §1):

1. PERIKSA: izin, status `submitted`, kontrol dua orang (KM-T3); tiap baris punya sales yang tertaut karyawan aktif;
   komponen `INSENTIF` aktif di PT induk tiap karyawan; `journal_date = journal_date(entity_id, bulan terakhir periode
   dasar paling akhir di lembar)`; `preflight_posting(entity_id, journal_date)`. Gagal → tidak ada tulisan.
2. NIAT: `submitted` → `approving` bersyarat; simpan `journal_date`, pelaku, koreksi nominal.
3. EFEK: per baris `enqueue_input(entity_id=pay_entity_id, employee_id, pay_period=lembar.pay_period,
   component_code="INSENTIF", label=f"{component_name} — {basis_label}", amount, source_type="incentive_sheet",
   source_key=input_key, source_ref={sheet_id, sheet_number, line_id, charge_entity_id: lembar.entity_id})`.
4. JURNAL lewat `post_durable("incentive_sheets", id, …, source_type="incentive_sheet", source_id=id lembar)`, satu
   jurnal per lembar di buku PT lembar, bertanggal `journal_date`: total T = Σ nominal. T > 0: Dr `ACC_BEBAN_INSENTIF`
   T / Cr `ACC_HUTANG_INSENTIF` T. T < 0: Dr `ACC_HUTANG_INSENTIF` |T| / Cr `ACC_BEBAN_INSENTIF` |T|. T = 0:
   `not_required`.
5. SELESAI: `approved`. Jurnal gagal → lembar tetap `approved` dengan `gl_status: "failed"`, tampil di Posting Gagal
   (jenis `incentive_sheet`, ulang = langkah 4). Pemanggilan ulang meneruskan dari langkah yang tercatat.

**3. Gaji memuat dan melunasi.** PY-T1 sudah mengambil masukan `approved` untuk PT dan `pay_period`-nya menjadi baris
slip. Tambahan di sini:

- Jurnal gaji untuk proses bermode `sheet`: Dr `ACC_HUTANG_INSENTIF` = Σ baris `INSENTIF` yang `charge_entity_id`-nya
  sama dengan PT proses (jumlah negatif menjadi kredit); tidak memanggil `post_incentive_accrual`.
- Setelah proses `posted`: baris lembar diberi `paid_run_id`; lembar yang semua barisnya terbayar → `paid`. Void proses
  (PK-22): `paid_run_id` dikosongkan, lembar kembali `approved` (masukan dilepas PY-T1).
- Masukan yang datang setelah proses reguler periode itu diposting menunggu proses `susulan`.

**4. Sales yang menjual di PT lain (K-26).** Baris lembar PT-B untuk karyawan PT-A: beban dan hutang diakui di PT-B saat
lembar disahkan (langkah 2); masukan masuk antrean PT-A. Saat proses gaji PT-A diposting, untuk Σ baris `INSENTIF`
ber-`charge_entity_id` = PT-B (nilai X):

- Buku PT-A, di dalam jurnal gaji: Dr `ACC_IC_AR` X (menggantikan Dr hutang insentif untuk baris itu).
- Buku PT-B, jurnal kembar lewat pembantu PK-06 (`source_type="interco_incentive_charge"`, kunci = id tagihan):
  Dr `ACC_HUTANG_INSENTIF` X / Cr `ACC_IC_AP` X.
- Satu `interco_charges` per (proses gaji, PT tertagih) dengan `amount = outstanding = X`; ikut dijumlah
  `non_trade_outstanding` dan dieliminasi lewat `sync_non_trade_elimination`.
- Pelunasan `POST /api/interco/charges/{id}/settle` (izin `interco.settle`; isi `{amount, date, account_id_from,
  account_id_to}`): `twin_cash` (keluar PT-B, masuk PT-A) + jurnal kembar Dr `ACC_IC_AP` / Cr kas di PT-B dan Dr kas /
  Cr `ACC_IC_AR` di PT-A; `outstanding` turun bersyarat; 0 → `settled`. `GET /api/interco/charges` (izin
  `interco.view`) mendaftar tagihan. Void proses gaji PT-A membalik jurnal kembar dan menutup tagihan bila
  belum dilunasi; bila sudah ada pelunasan → 409 "Tagihan antar-PT {nomor} sudah dilunasi sebagian. Batalkan
  pelunasannya dulu."

**5. Kesiapan dan invarian.**

- `GET /api/incentive/switch-readiness` (izin `incentive.configure`) → `{mode, checks: [{code, ok, text}]}`: pencocokan
  KM-T1 dua bulan terakhir hijau; saldo hutang insentif PT = 0 (akrual mesin sudah dilunasi); semua sales pada lembar
  draf dan diajukan tertaut karyawan; tidak ada proses gaji draf yang memuat komisi mesin.
- `INV-KM-4` di `scripts/verify_data_integrity.py`, per PT bermode `sheet`: saldo akun hutang insentif (kode hasil
  pemetaan `ACC_HUTANG_INSENTIF`) = Σ `amount` baris lembar `payroll_linked` yang berjurnal dan belum ber-`paid_run_id`.
- `INV-KM-5`: Σ `interco_charges.outstanding` per pasangan PT = saldo `ACC_IC_AR` dari jurnal tagihan insentif di PT
  penagih = saldo `ACC_IC_AP` di PT tertagih.

Galat tambahan:

| Keadaan | Kode | Pesan |
|---|---|---|
| Baris tanpa karyawan tertaut | 400 | "{sales} belum tertaut ke data karyawan, jadi insentifnya tidak bisa masuk gaji. Tautkan akunnya di kartu karyawan." |
| Komponen `INSENTIF` nonaktif di PT induk | 400 | "Komponen gaji Insentif belum aktif di {nama PT}." |
| Periode tanggal jurnal tertutup | 409 | "Periode {bulan tahun} sudah ditutup, jadi beban insentif tidak bisa dibukukan di bulan itu. Buka periodenya atau ubah pengaturan tanggal jurnal periodik." |
| Lembar sedang disahkan pihak lain | 409 | "Lembar {nomor} sedang diproses. Muat ulang." |

### Pengaturan

`hr.payroll_commission_mode` (diubah; berkas `backend/config_catalog_ops.py`): `group` `sdm` · `type` `enum` ·
`default` `accrue_then_settle` (perilaku hari ini; K-22) · `options`: `accrue_then_settle` "Komisi otomatis: dicadangkan,
dilunasi lewat gaji" · `pay_on_invoice` (label lama, tidak diubah) · `off` "Tidak ada komisi di gaji" · `sheet` "Dari
Lembar Insentif yang disahkan" · `scopes` `("global", "entity")` · `label` "Cara insentif sales masuk penggajian" ·
`help` "Menentukan apakah komisi dihitung otomatis, tidak dibayar lewat gaji, atau mengikuti Lembar Insentif yang
disahkan." · `impact` "Pada pilihan Lembar Insentif, komisi otomatis berhenti masuk slip PT ini dan lembar yang
disahkan menjadi beban serta baris slip." · `example` "Lembar Rp 8.500.000 disahkan → beban Rp 8.500.000; gaji bulan
bayarnya memuat tiga baris insentif" · `risk` `high` · `requires_reason` `True` · `permission` `("hr",
"manage_payroll")` · `consumers` `services/hr_payroll_service.py:commission_mode`. `commission.incentive_unit`
ditandai `status="not_used"` dengan alasan "Tarif komisi dihitung dari satuan dasar barang; isian ini tidak dipakai."

### Izin dan peran

Tidak ada pasangan izin baru: `interco.view` dan `interco.settle` sudah dipakai pinjaman antar-PT,
`backend/routers/interco_loans.py:103` (`settle`). Antrean Posting Gagal mendapat jenis
`incentive_sheet` dan `interco_incentive_charge` di `posting_registry`.

### Layar

- **Lembar Insentif › detail:** lencana status jurnal (PK-18) dan tautan "Lihat jurnal" (L8); per baris, setelah
  terbayar: "Dibayar lewat {nomor proses gaji}". Di PT yang belum dialihkan, pita keterangan: "PT ini masih memakai
  komisi otomatis. Lembar ini tercatat sebagai keputusan dan tidak masuk gaji." Konfirmasi Sahkan di PT bermode
  `sheet` ditambah: "Beban insentif Rp … dibukukan per {tanggal jurnal} dan {n} baris masuk gaji {bulan tahun}."
- **Target & Aturan:** kartu **Kesiapan beralih ke Lembar Insentif** — daftar periksa dari endpoint kesiapan, nilai mode
  yang berlaku, dan tautan "Ubah di Pusat Pengaturan". Tidak ada tombol alih di layar ini.
- **Proses Gaji › slip:** baris insentif tampil dengan labelnya, mis. "Insentif Bulanan — Okt 2026".
- **Antar-PT:** daftar "Tagihan insentif antar-PT" (Nomor, Dari PT, Kepada PT, Nominal, Sisa, Status) dengan tombol
  "Catat pelunasan" (pop-up baku; konfirmasi menyebut nominal dan kedua PT), sebagai bagian layar keuangan antar-PT yang ada.
- Layar tarif komisi: kolom dan isian "Satuan insentif" dihapus.

## Uji penerimaan

Fixture: `ent_kanda` bermode `sheet`, BPJS dimatikan untuk PT itu; setelan `gl.tanggal_jurnal_periodik` bawaan
(`akhir_periode`). Karyawan Andi dan Budi, masing-masing gaji pokok 5.000.000, TK0, tertaut ke akun salesnya. Lembar L1
(`pay_period` 2026-11): Andi "Insentif Bulanan" Okt 2026 Rp 2.000.000; Andi "Insentif Triwulan" Triwulan III 2026
Rp 3.000.000; Budi "Insentif Bulanan" Okt 2026 Rp 3.500.000. Tarif pajak dari tabel kategori A pada `3132cc4` (tes
mengambilnya lewat `ter_rate`).

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | L1 diajukan | Sahkan pada 5 Nov 2026 | Jurnal `incentive_sheet` bertanggal 2026-10-31: Dr 6-5000 8.500.000 / Cr 2-1500 8.500.000 (2 + 3 + 3,5 jt); `gl_status` `posted`; tiga masukan `approved` untuk 2026-11 berlabel "Insentif Bulanan — Okt 2026", "Insentif Triwulan — Triwulan III 2026", "Insentif Bulanan — Okt 2026" |
| U2 | B | U1; tarif komisi mesin Rp 500 per meter dan pesanan Andi 1.000 m lunas di November | Proses reguler 2026-11 | Andi: dua baris insentif; `commission` 5.000.000 (bukan 5.500.000: mesin tidak dipanggil); `gross` 10.000.000; `pph21` 200.000 (× 2 %); `net` 9.800.000. Budi: `gross` 8.500.000; `pph21` 127.500 (× 1,5 %); `net` 8.372.500 |
| U3 | B | U2 disahkan | Posting | Dr 6-1000 10.000.000; Dr 2-1500 8.500.000; Cr 2-1600 18.172.500; Cr 2-1800 327.500 (debit 18.500.000 = kredit 18.500.000). Saldo 2-1500 = 8.500.000 − 8.500.000 = 0; L1 `paid`; tiap baris ber-`paid_run_id` |
| U4 | B | Sebelum dan sesudah U3 | `INV-KM-4` | Sebelum: saldo 8.500.000 = Σ baris belum dibayar 8.500.000. Sesudah: 0 = 0 |
| U5 | B | U3; lembar L2 (`pay_period` 2026-12) berisi penyesuaian Andi −500.000 merujuk baris L1 | Sahkan L2; proses dan posting gaji 2026-12 | Jurnal L2: Dr 2-1500 500.000 / Cr 6-5000 500.000. Slip Andi: `commission` −500.000, `gross` 4.500.000, `pph21` 0, `net` 4.500.000. Jurnal gaji memuat Cr 2-1500 500.000; saldo 2-1500 kembali 0 |
| U6 | B | `ent_ksc` bermode bawaan; lembar serupa L1 | Sahkan | `approved`, `payroll_linked` salah, `gl_status` `not_required`; 0 jurnal `incentive_sheet`; 0 masukan |
| U7 | B | `ent_ksc`: tarif Rp 500 per meter, batas margin 0, pesanan sales 1.000 m lunas dalam periode | Pratinjau gaji dengan mode `accrue_then_settle`, lalu `off` | `commission` 500.000 (1.000 × 500); lalu 0 |
| U8 | B | L1 dengan sales yang tidak tertaut karyawan | Sahkan | 400 "…belum tertaut ke data karyawan…"; status tetap `submitted`; 0 masukan, 0 jurnal |
| U9 | B | Akun 6-5000 dinonaktifkan | Sahkan L1; aktifkan akun; ulang dari Posting Gagal dua kali | `approved`, `gl_status` `failed`, tiga masukan; setelah ulang tepat 1 jurnal dan tetap tiga masukan; ulang kedua 404 |
| U10 | B | Periode Oktober `ent_kanda` ditutup | Sahkan L1 | 409 pesan periode; status `submitted`; 0 masukan |
| U11 | B | U3 | Void proses gaji 2026-11 | Masukan kembali `approved`; L1 kembali `approved` tanpa `paid_run_id`; saldo 2-1500 = 8.500.000 |
| U12 | B | Andi karyawan `ent_ksc`; lembar `ent_kanda` (mode `sheet`) Andi Rp 2.000.000; `ent_ksc` juga bermode `sheet` | Sahkan; proses dan posting gaji `ent_ksc` | Saat sah: jurnal di `ent_kanda` Dr 6-5000 / Cr 2-1500 2.000.000; masukan ber-`entity_id` `ent_ksc`. Saat posting: jurnal gaji `ent_ksc` memuat Dr 1-1250 2.000.000 (tanpa Dr 2-1500); jurnal kembar `ent_kanda` Dr 2-1500 2.000.000 / Cr 2-1250 2.000.000; satu `interco_charges` `open` 2.000.000; saldo 2-1500 `ent_kanda` 0 |
| U13 | B | U12 | Lunasi tagihan 2.000.000; `INV-KM-5` | Kas keluar `ent_kanda` dan masuk `ent_ksc` 2.000.000; saldo 1-1250 dan 2-1250 nol; tagihan `settled`; invarian lulus |
| U14 | B | `ent_kanda` bermode `sheet` | `POST /api/sales/incentive/post-gl` | 409; 0 jurnal `incentive_accrual` |
| U15 | B | Kunci mode | Putaran `t1_config.py`; ubah nilai tanpa alasan; ubah oleh peran tanpa `hr.manage_payroll` | Lulus; ditolak; 403 |
| U16 | A | L1 diajukan | Dua `approve` bersamaan | Satu 200, satu 409; 1 jurnal; tiga masukan |
| U17 | layar (uji jalan) | U3 | Buka slip Andi dan detail L1 | Dua baris insentif berlabel; L1 berlencana "Dibayarkan" dan "Dibayar lewat {nomor}" |

## Langkah kerja

**Serah-terima (a) — alur baru, komisi otomatis belum disentuh.**
1. `backend/tests_mem/test_KMT4_insentif_gaji.py`: U1, U3–U6, U8–U11, U14, U15 (merah).
2. Pilihan `sheet`, `commission_mode`, komponen `INSENTIF`; pengesahan ber-niat dengan `enqueue_input` dan jurnal lewat
   `post_durable`; jenis Posting Gagal; pelunasan di jurnal gaji; status `paid`; `INV-KM-4`; endpoint kesiapan.
3. Tagihan antar-PT (U12, U13, `INV-KM-5`). Bila bagian ini membengkak, pecah menjadi `KM-T4c` menurut `00` §8. Gate.

**Serah-terima (b) — mematikan jalur lama per mode.**
4. U2, U7: `_commission_for` menghormati `off` dan `sheet`; akrual manual memakai `sales_roster`; `incentive_unit`
   dicabut dari API dan layar tarif.
5. Layar; U16 di A; U17. Gate penuh. Laporan memuat contoh U1 → U3 (lembar → jurnal → slip → saldo 2-1500).
6. **Berhenti (H5):** tulis di `STATUS.md` pertanyaan "PT mana yang dialihkan ke Lembar Insentif, mulai periode bayar
   kapan?" beserta hasil endpoint kesiapan tiap PT di data acuan. Jangan mengubah nilai mode PT mana pun.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`interco_charges`, field lembar); `CODEBASE_MAP.md`; `memory/PRD.md`;
`docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("tagihan insentif antar-PT").

## Di luar lingkup

- Menghapus mesin komisi, tarif, skema, dan layar lamanya → KM-T5 (setelah semua PT beralih, atau per PT lewat layar).
- Sumber angka akrual mode lama dan tanggal jurnalnya → PK-22. Eliminasi konsolidasi per periode → PK-31.
- Bukti potong dan pembagian PPh 21 antar-PT untuk sales lintas PT: pajak dihitung di PT induk (K-26).

## Asumsi dan risiko

- `ASUMSI:` tagihan insentif antar-PT memakai akun non-dagang yang sudah dipakai pinjaman antar-PT (1-1250 dan 2-1250),
  dengan PT induk karyawan sebagai penagih. Arah ini mengikuti K-26; bila akuntan pemilik menghendaki akun lain,
  hanya pemetaan akun yang diubah.
- `ASUMSI:` label baris slip = "{nama komponen insentif} — {label periode dasar}".
- `ASUMSI:` lembar yang disahkan sebelum PT dialihkan tidak dijurnal surut; bila perlu dibayar, dibuat lembar baru.
- `ASUMSI:` `pay_on_invoice` dibiarkan berperilaku seperti hari ini; pembersihan pilihannya urusan KF-T2.
- `RISIKO:` insentif terbayar dua kali bila mode diubah di tengah periode. Penangkal: daftar periksa kesiapan (tidak ada
  proses gaji draf berkomisi mesin) dan H5. Membatalkan: kembalikan mode PT ke `accrue_then_settle`; lembar yang sudah
  berjurnal tetap sah dan dilunasi lewat gaji seperti biasa.

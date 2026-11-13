# KP-T5 — Penomoran dokumen bisa diatur per PT, tanpa mengubah satu nomor pun saat dipasang

| | |
|---|---|
| Gelombang | Jalur konfigurasi perusahaan (U) |
| Jenis | fitur |
| Risiko | tinggi (dua serah-terima) |
| Prasyarat | KP-T1 |
| Menutup temuan | KP-12, KP-35 |
| Keputusan | `00` §4.1 (nilai awal = perilaku hari ini); titik henti H3 untuk dokumen lama |
| Standar | §2 (menyimpang dari §2.1 — lihat "Pengaturan"), §3.1 (Z1, Z6), §3.4 (N1), §4 (L1, L2, L5, L6), §5 (D7, D9), §6 |
| Lingkungan uji | B (format dan setara); A (dua permintaan bersamaan, indeks unik) |

## Tujuan

Awalan, lebar angka, sisipan tahun/bulan, pengulangan dari 1, dan pilihan "per PT atau bersama" untuk tiap jenis
dokumen diatur dari satu tabel **Penomoran Dokumen**, dibaca satu fungsi. Pada hari dipasang semua nomor berikutnya
sama persis dengan yang akan terbit hari ini. Tiga deret yang masih "baca nomor terakhir + 1" menjadi deret atomik.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| # | Fakta | Jangkar |
|---|---|---|
| 1 | Satu fungsi penomoran dengan dua cara. **Per PT** (ada `entity_id`, `scheme` bawaan): deret atomik `number_sequences` berkunci (`entity_id`, awalan tanpa tanda hubung akhir, huruf besar); hasil `KODE/AWALAN00001`. **Bersama** (`entity_id` kosong/`"all"` atau `scheme="shared"`): deret atomik berkunci (`"__shared__"`, `koleksi:field:awalan`); hasil `AWALAN00001` | `backend/core_utils.py:19` (`next_doc_number`); `backend/core_utils.py:60` (`doc_type`) |
| 2 | Deret baru disemai sekali dari nomor tertinggi yang sudah ada | `backend/core_utils.py:114` (`_max_existing_number`) |
| 3 | Kunci unik (`entity_id`, `doc_type`) pada `number_sequences` sudah ada | `backend/indexes.py:559` (`uq_entity_doctype`) |
| 4 | Awalan, lebar, dan cara (per PT/bersama) ditulis di tiap titik panggil: 93 pemanggilan, 59 awalan berbeda. Contoh per PT dan bersama | `backend/routers/sales_orders.py:305` (`next_doc_number`); `backend/services/return_service.py:148` (`next_doc_number`) |
| 5 | Titik panggil per PT yang menerima `entity_id` kosong jatuh ke deret bersama (mis. kas tingkat grup) | `backend/routers/cash.py:29` (`next_doc_number`) |
| 6 | Nota kredit punya dua bentuk nomor di koleksi dan field yang sama: per PT (amandemen, batal item) dan bersama (retur) | `backend/services/amendment_service.py:878` (`next_doc_number`); `backend/services/return_service.py:154` (`next_doc_number`) |
| 7 | Nomor lot menyisipkan tahun-bulan (jam UTC) di awalan, lebar 4, sehingga deretnya berulang tiap bulan | `backend/services/lot_service.py:133` (`next_lot_number`) |
| 8 | SPK makloon: per PT bila ada PT, selain itu bersama | `backend/services/makloon_order_service.py:181` (`next_doc_number`) |
| 9 | Tagihan jasa makloon `VBM-`: baca nomor terakhir + 1 | `backend/services/makloon_order_service.py:1407` (`_next_service_bill_no`) |
| 10 | Kode karyawan `EMP-`: baca kode terakhir + 1 | `backend/services/hr_service.py:50` (`next_employee_code`) |
| 11 | Pesanan khusus `SORD-YYMMDD-0001`: baca nomor terakhir hari itu (tanggal WIB) + 1 | `backend/services/special_order_service.py:38` (`generate_special_order_number`) |
| 12 | Nomor faktur penjualan diturunkan dari nomor pesanan (`INV-<nomor SO>-01`), lewat fungsi yang sama | `backend/routers/invoices.py:47` (`_inv_prefix`) |
| 13 | Wizard PT berjanji kode dokumen dipakai "SEMUA nomor dokumen"; pratinjaunya empat contoh tetap | `frontend/src/features/settings/entities/EntityWizard.jsx:324` (`hint`); `frontend/src/features/settings/entities/EntityWizard.jsx:334` (`SO-00001`) |

### Daftar lengkap awalan hari ini = nilai awal tabel (59 awalan; lebar 5 kecuali disebut)

**Per PT (44)** — `awalan` → `koleksi.field`:
`SO-`, `SOS-` → `sales_orders.number` · `PO-` → `purchase_orders.po_number` · `SJ-` → `shipments.shipment_no` ·
`FKT-` → `tax_invoices.number` · `AR-` → `ar_receipts.number` · `CASH-` → `cash_transactions.number` ·
`JE-` → `journal_entries.number` · `CN-`, `DN-` → `credit_notes.number` · `AMD-` → `doc_amendments.number` ·
`CB-` → `contra_bons.number` · `RPB-` → `payment_plans.number` · `SLB-` → `payment_variance_decisions.number` ·
`DN-DENDA-` → `penalties.number` · `CASE-` → `finance_cases.number` · `FA-` → `fin_fixed_assets.number` ·
`PD-` → `cash_advances.number` · `STL-` → `cash_advance_settlements.number` · `MCC-` → `mkt_campaign_costs.number` ·
`IC-` → `interco_transactions.number` · `ICS-` → `interco_settlements.number` · `ICL-` → `interco_loans.number` ·
`ICR-` → `interco_returns.number` · `PIN-` → `internal_requests.number` · `TRF-` → `warehouse_transfers.code` ·
`GRN-` → `goods_receipts.number` · `INS-` → `inspections.number` · `REG-` → `cycle_count_sessions.number` ·
`LOT-` + sisipan `YYMM` (lebar 4, ulang bulanan, jam UTC) → `inventory_lots.lot_number` ·
`MKO-` → `makloon_orders.mko_number` · `SCT-` → `supplier_contracts.contract_number` ·
`SCR-` → `store_credit_redemptions.number` · `RPR-` → `repair_orders.number` · `LG-` → `logistics_deliveries.number` ·
`VHL-` → `vehicle_usage_logs.number` · `CF-` → `customer_feedbacks.number` · `DSR-` → `design_requests.number` ·
`SMP-` → `md_samples.number` · `SPEC-` → `md_specs.number` · `LV-` → `hr_leave_requests.number` ·
`OT-` → `hr_overtime.number` · `PAY-` → `hr_payroll_runs.number` · `SLIP-` → `hr_payslips.number`.

**Bersama seluruh grup (18)**:
`SRET-` → `sales_returns.number` · `CN-` → `credit_notes.number` (retur) · `RTN-` → `inventory_rolls.roll_no` ·
`PRET-` → `purchase_returns.number` · `DN-` → `purchase_returns.debit_note_number` · `VB-` → `vendor_bills.bill_number` ·
`FPM-` → `tax_invoices_in.number` · `PR-` → `purchase_requisitions.number` · `RFQ-` → `rfqs.rfq_number` ·
`LCV-` → `landed_cost_vouchers.voucher_number` · `WO-` → `mfg_work_orders.wo_number` · `SUP-` → `suppliers.code` ·
`MAK-` → `makloons.code` · `CC` → `rfid_cycle_counts.cc_number` · `BTG` → `putaway_orders.btg_number` ·
`PA` → `putaway_orders.pa_number` · `PJ` → `rfid_print_jobs.job_number` · `MKO-` (tanpa PT) → `makloon_orders.mko_number`.

`CN-`, `DN-`, `MKO-` muncul di kedua daftar → 44 + 18 − 3 = 59. Di luar fungsi (menjadi jenis ke-60 s/d 62 di unit ini):
`VBM-` → `vendor_bills.bill_number` (bersama), `EMP-` → `hr_employees.code` (bersama), `SORD-` + sisipan `YYMMDD`
(lebar 4, ulang harian, bersama) → `special_orders.number`. `INV-<nomor SO>-` (lebar 2) = jenis turunan, tidak diatur.

## Perubahan

### Data

Katalog jenis nomor (struktur): berkas baru `backend/doc_number_kinds.py` — satu entri per baris daftar di atas:
`kind` (mis. `so`, `cn`, `cn_retur`, `mko`, `lot`), `label`, `group`, `collection`, `field`, `identity_prefix` (awalan
hari ini; **kunci deret**, tidak pernah berubah), `default` = `{prefix, width, date_token, reset, scope}` persis
perilaku hari ini, `clock` (`wib`; `utc` hanya untuk `lot`), `locked` (benar = tidak bisa diubah dari layar: `sup`,
`mak`, `cc`, `btg`, `pa`, `pj`, `inv`), dan `lookup(collection, field, prefix)` yang mengenali awalan bersisipan
(`LOT-2611-`, `SORD-261113-`, `INV-…-`).

Koleksi baru `doc_number_formats` (hanya menyimpan yang **diubah**; tanpa baris = bawaan katalog):

| Field | Tipe | Arti |
|---|---|---|
| `id`, `kind`, `entity_id` | teks | `entity_id`: `"all"` (grup) atau id PT. Unik (`kind`, `entity_id`) |
| `prefix` | teks, cocok `[A-Z0-9][A-Z0-9-]{0,11}` | Awalan yang tercetak |
| `width` | bilangan 3–8 | Lebar angka urut |
| `date_token` | `""` · `YY` · `YYYY` · `YYMM` · `YYYYMM` · `YYMMDD` | Sisipan tanggal sesudah awalan, diikuti `-` |
| `reset` | `tidak` · `tahunan` · `bulanan` · `harian` | Kapan angka urut kembali ke 1 |
| `scope` | `per_pt` · `bersama` | Hanya boleh pada baris grup |
| `version`, `reason`, `updated_by`, `updated_at` | — | Alasan wajib; perubahan dicatat di jejak audit |

Bentuk nomor: per PT `{KODE PT}/{prefix}{sisipan-}{angka}`; bersama `{prefix}{sisipan-}{angka}` — sama dengan hari ini.
Kunci deret di `number_sequences` (tidak berubah, sehingga penghitung berlanjut):

| Cara | `entity_id` | `doc_type` |
|---|---|---|
| Per PT | id PT | (`identity_prefix` + bagian sisipan menurut `reset`) tanpa tanda hubung akhir, huruf besar — mis. `SO`, `LOT-2611` |
| Bersama | `"__shared__"` | `koleksi:field:` + `identity_prefix` + bagian sisipan menurut `reset` — mis. `sales_returns:number:SRET-` |

"Bagian sisipan menurut `reset`": `tidak` → kosong; `tahunan` → tahun dari sisipan + `-`; `bulanan`/`harian` → seluruh
sisipan + `-`. Deret periode baru disemai dari nomor tertinggi ber-awalan-dan-sisipan yang sama (0 bila belum ada).

Tanpa migrasi data: tidak ada baris `doc_number_formats` saat dipasang, tidak ada dokumen dinomori ulang. Menomori
ulang dokumen lama **tidak** disediakan (H3).

### Server

`backend/core_utils.py` — `next_doc_number` tetap satu-satunya pembuat nomor; tanda tangannya menjadi
`next_doc_number(collection, field, prefix, width=5, entity_id=None, scheme="per_entity_prefix", *, kind="")`:

1. `kind` = argumen, atau `doc_number_kinds.lookup(collection, field, prefix)`. Tidak dikenal → perilaku lama dengan
   argumen apa adanya (dan dicatat di log), supaya tidak ada titik panggil yang patah.
2. Format = `doc_numbering_service.effective_format(kind, entity_id)`: baris PT → baris grup → bawaan katalog
   (`scope` hanya dari grup/katalog).
3. Cara: `scope = per_pt` **dan** `entity_id` terisi (bukan `"all"`) → per PT; selain itu bersama. Selama format
   masih bawaan, titik panggil ber-`scheme="shared"` tetap bersama (butir 5 "Keadaan sekarang" dipertahankan).
4. Kunci deret menurut tabel di atas; semai sekali; `$inc` atomik; rakit nomor.

Berkas baru `backend/services/doc_numbering_service.py`: `effective_format`, `list_formats(entity_id)`,
`save_format`, `clear_format`, `preview(kind, entity_id, fmt, n=3)` (tanpa menaikkan penghitung).

Endpoint (baca `settings.view`; ubah `settings.manage`; `entity_id` lewat `resolve_requested_entity`):

| Metode + path | Isi | Jawaban |
|---|---|---|
| `GET /api/doc-numbering?entity_id=` | — | `[{kind, label, group, format, source: "bawaan"\|"grup"\|"pt", next_preview, last_no, locked, version}]` |
| `POST /api/doc-numbering/preview` | `{kind, entity_id, prefix, width, date_token, reset, scope}` | `{samples: [3 nomor], warnings}` |
| `PUT /api/doc-numbering/{kind}` | `{entity_id, prefix, width, date_token, reset, scope?, reason, expected_version}` | baris seperti GET |
| `DELETE /api/doc-numbering/{kind}?entity_id=&reason=` | — | baris kembali ke sumber di atasnya |

Validasi simpan (400 kecuali disebut):

| Keadaan | Pesan |
|---|---|
| Alasan kosong | "Alasan perubahan format nomor wajib diisi." |
| Awalan atau lebar tidak sah | "Awalan hanya huruf besar, angka, dan tanda hubung (paling banyak 12 karakter); lebar angka 3 sampai 8." |
| `reset` tanpa sisipan yang membedakan periode (tahunan butuh tahun; bulanan butuh tahun-bulan; harian butuh `YYMMDD`) | "Agar nomor tidak kembar, pengulangan {tahunan/bulanan/harian} harus disertai sisipan {tahun/tahun-bulan/tanggal}." |
| Dua jenis pada koleksi dan field yang sama akan berbentuk sama (cara + awalan + sisipan) | "Format ini sama dengan {label jenis lain}, sehingga nomornya bisa kembar. Bedakan awalannya." |
| `scope` dikirim pada baris PT | "Pilihan per PT atau bersama diatur untuk seluruh grup." |
| Jenis ber-`locked` | "Format nomor {label} tidak bisa diubah dari layar." |
| `expected_version` basi (409) | "Format ini sudah diubah orang lain. Muat ulang." |

Peringatan (tidak menolak): "Sudah ada {n} dokumen bernomor format lama; nomor lama tidak berubah." dan, saat `scope`
berubah, "Deret baru melanjutkan dari nomor tertinggi {tiap PT / gabungan} yang sudah ada."

Tiga deret KP-35 dialihkan ke fungsi yang sama: `_next_service_bill_no` → `kind="vbm"`; `next_employee_code` →
`kind="emp"`; `generate_special_order_number` → `kind="sord"` (sisipan `YYMMDD` WIB). Bawaan ketiganya = bentuk hari
ini; semai pertama mengambil nomor tertinggi yang ada.

Titik panggil ber-`scheme="shared"` untuk 11 jenis (`sret`, `cn_retur`, `rtn`, `pret`, `dn_retur_beli`, `vb`, `fpm`,
`pr`, `rfq`, `lcv`, `wo`) ditambah `entity_id` = PT dokumennya (N1), supaya pilihan "per PT" bisa berlaku bila grup
mengubah `scope`; selama `scope` bawaan, hasilnya tidak berubah. Enam jenis ber-`locked` tidak disentuh.

`entity_provisioning_service.provision_entity`: `number_preview` diambil dari `preview("so", …)`.

### Pengaturan

Tidak ada kunci registry. **Menyimpang dari standar §2.1 karena** format nomor harus bisa ditimpa per jenis dokumen
per PT, dipratinjau terhadap penghitung nyata, dan divalidasi silang antarjenis; kunci bertipe tabel di registry hanya
bisa ditimpa utuh per PT. Yang dipertahankan dari §2: bawaan = perilaku hari ini, alasan wajib, jejak perubahan.

### Izin dan peran

Tidak ada pasangan baru (`settings.view`, `settings.manage`).

### Layar

Tempat: Pengaturan › Dokumen & Cetak › tab baru **Penomoran Dokumen** (id layar `settings-doc-numbering`; masuk
`nav` modul akses "Pengaturan, Pengguna & Hak Akses"; hub ini menjadi tiga tab).

- Banner PT; saat "Semua PT" layar menampilkan dan mengubah baris **grup**.
- Tabel berkelompok (Penjualan, Pembelian, Keuangan, Gudang, Antar-PT, R&D, SDM, Master): kolom **Jenis dokumen**,
  **Contoh nomor berikutnya**, **Awalan**, **Lebar angka**, **Sisipan tanggal**, **Mulai lagi dari 1**, **Deret**
  ("Per PT" / "Bersama semua PT"), **Sumber** ("Bawaan" / "Aturan grup" / "Khusus PT ini").
- Tombol **Ubah** membuka pop-up baku: isian yang sama + **Alasan**, dengan pratinjau tiga nomor yang diperbarui saat
  mengetik dan peringatan dari server. Pilihan **Deret** hanya aktif pada baris grup. Tombol **Kembalikan ke bawaan**.
- Jenis ber-`locked` tampil abu-abu dengan keterangan "Tidak bisa diubah: dipakai bersama atau diturunkan dari
  dokumen lain."
- Keterangan di kepala tabel: "Perubahan hanya berlaku untuk dokumen baru. Nomor yang sudah terbit tidak berubah."
- `EntityWizard.jsx` langkah 3: pratinjau memakai `POST /api/doc-numbering/preview` untuk empat jenis yang sama.
- Memuat: kerangka abu-abu; galat: `ErrorNotice`; kosong tidak mungkin (katalog selalu ada).

## Uji penerimaan

Persiapan bersama: seed lingkungan B (`ent_ksc` kode `KSC`, `ent_kanda` kode `KANDA`); akun admin.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | Uji statik: telusuri semua pemanggilan `next_doc_number` di `backend/` (di luar uji dan seed) dengan pengurai sintaks | Tiap pemanggilan dikenali `lookup`; jumlah awalan berbeda yang dikenali = 59 |
| U2 | B | Untuk tiap jenis katalog: `number_sequences` diisi `last_no: 41` pada kunci hari ini | **Setara:** `next_doc_number` dipanggil dengan argumen titik panggil aslinya, untuk `ent_ksc` | Hasil = rakitan cara lama dengan angka 42, mis. `KSC/SO-00042`, `SRET-00042`, `KSC/LOT-<YYMM>-0042`, `CC00042`; 62 dari 62 jenis sama |
| U3 | B | Basis data kosong; satu `sales_orders` `{entity_id: "ent_ksc", number: "KSC/SO-00007"}` | `next_doc_number("sales_orders", "number", "SO-", entity_id="ent_ksc")` | `KSC/SO-00008` (semai dari nomor tertinggi — perilaku lama) |
| U4 | B | `PUT /api/doc-numbering/so` `{entity_id: "ent_kanda", prefix: "SP-", width: 6, date_token: "", reset: "tidak", reason: "Uji"}`; penghitung SO `ent_kanda` = 12, `ent_ksc` = 30 | Buat nomor SO untuk kedua PT | `KANDA/SP-000013`; `KSC/SO-00031` (PT lain tidak berubah) |
| U5 | B | `PUT …/so` grup: `date_token: "YYYY"`, `reset: "tahunan"`; penghitung lama 30 | Buat nomor pada tanggal 2026-12-31 lalu 2027-01-01 (jam dibekukan) | `KSC/SO-2026-00001`, lalu `KSC/SO-2027-00001` |
| U6 | B | — | `PUT …/so` dengan `reset: "tahunan"`, `date_token: ""` | 400 "Agar nomor tidak kembar…" |
| U7 | B | — | `PUT …/cn_retur` grup `{scope: "per_pt", prefix: "CN-", …}` | 400 "Format ini sama dengan Nota kredit…" |
| U8 | B | `sales_returns` berisi `SRET-00040` (`ent_ksc`) dan `SRET-00041` (`ent_kanda`); `PUT …/sret` grup `{scope: "per_pt", …}` | Buat retur untuk `ent_ksc` lalu `ent_kanda` | `KSC/SRET-00041`; `KANDA/SRET-00042`; kedua dokumen lama tetap bernomor lama |
| U9 | B | — | `PUT …/sup` | 400 "Format nomor … tidak bisa diubah dari layar." |
| U10 | B | — | `PUT …/so` untuk `ent_kanda` dengan `scope: "bersama"` | 400 "Pilihan per PT atau bersama diatur untuk seluruh grup." |
| U11 | B | `vendor_bills` berisi `VBM-00009`; `hr_employees` berisi `EMP-00120`; `special_orders` berisi `SORD-<hari ini>-0003` | Panggil tiga pembuat nomor KP-35 | `VBM-00010`; `EMP-00121`; `SORD-<hari ini>-0004` |
| U12 | A | Keadaan U11 | 20 permintaan bersamaan membuat kode karyawan; 20 membuat tagihan jasa makloon | 20 kode berbeda `EMP-00121` … `EMP-00140`; 20 nomor `VBM-` berbeda; tidak ada yang kembar |
| U13 | B | — | `POST /api/doc-numbering/preview` untuk `so` dua kali berturut | Contoh sama pada kedua panggilan; `last_no` di `number_sequences` tidak berubah |
| U14 | B | Peran **Sopir**; peran **Tanpa Acuan** berizin `settings.view` saja | `GET /api/doc-numbering`; `PUT …/so` | Sopir: 403, 403. Tanpa Acuan: 200, 403 |
| U15 | B | — | `POST /api/entities` (PT baru kode `UJI`) | `provisioning.number_preview` = `UJI/SO-00001` |
| U16 | layar (uji jalan) | Login admin | Buka Penomoran Dokumen; ubah lebar SO PT Kanda menjadi 6; buat pesanan | Kolom contoh berubah; pesanan baru bernomor 6 digit; pesanan lama tetap |

## Langkah kerja

**Serah-terima (a) — katalog dan pembaca; titik panggil tidak disentuh.**

1. `backend/tests_mem/test_KPT5a_setara.py`: U1–U3 (U1 dan U2 merah karena katalog belum ada).
2. `doc_number_kinds.py` (62 jenis + `inv`), `doc_numbering_service.effective_format`, koleksi dan indeks unik.
3. `next_doc_number` membaca format; U1–U3 hijau. Gate penuh. **SHA (a).**

**Serah-terima (b) — pengaturan, layar, dan pengalihan deret lama.**

4. Endpoint, validasi, pratinjau (U4–U10, U13, U14).
5. KP-35: tiga pembuat nomor dialihkan (U11; U12 di lingkungan A).
6. Titik panggil deret bersama menerima `entity_id` dokumen; U2 diulang penuh dan tetap hijau.
7. Layar, pratinjau wizard (U15, U16). Gate penuh. **SHA (b).**

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`doc_number_formats`); `CODEBASE_MAP.md` (`doc_number_kinds.py`, `doc_numbering_service.py`);
`docs/KN_13_NAVIGATION_MAP.md` (tab baru); `memory/PRD.md`.

## Di luar lingkup

- Menomori ulang dokumen lama atau memisah deret bersama yang sudah terbit → keputusan pemilik (H3); tidak dibangun.
- Kode desain (`KN-…`, `DSG-…`), kode shift, dan nomor roll (`roll_service.next_roll_no`) → tidak diubah.
- Kunci registry `lot.number_format` (tidak dibaca) ditandai "tidak dipakai" oleh KF-T2. Format nomor lot sendiri
  diatur di tabel ini (jenis `lot`); unit ini menambahkan pada alasan tidak-dipakai kunci itu kalimat "Diatur di
  Pengaturan › Dokumen & Cetak › Penomoran Dokumen."
- Indeks unik pada field nomor tiap koleksi → PK-14. Penomoran jurnal → PK-35.
- Nama dan susunan hub → KP-T9.

## Asumsi dan risiko

- `ASUMSI:` deret bersama yang ada dipertahankan sebagai bawaan; memisahnya per PT adalah pilihan pemilik di layar.
- `ASUMSI:` empat nomor RFID (`CC`, `BTG`, `PA`, `PJ`) dan dua kode master (`SUP-`, `MAK-`) dikunci dari layar; yang
  pertama karena berdekatan dengan alur gerbang RFID (H7), yang kedua karena masternya dipakai bersama.
- `ASUMSI:` jam sisipan tanggal adalah WIB, kecuali lot yang tetap UTC seperti hari ini.
- `ASUMSI:` pilihan "per PT atau bersama" berlaku untuk seluruh grup per jenis dokumen, tidak per PT.
- `RISIKO:` nomor kembar bila kunci deret meleset dari yang dipakai hari ini. Mitigasi: U2 untuk semua jenis sebelum
  dan sesudah langkah 6; kunci unik `number_sequences`. Membatalkan (a): kembalikan isi `next_doc_number`; koleksi
  baru kosong. Membatalkan (b): hapus baris `doc_number_formats`; penghitung tidak pernah diturunkan.
- `RISIKO:` lingkungan B tidak membuktikan keunikan saat bersamaan; U12 wajib di lingkungan A, selain itu ditulis
  "belum teruji".

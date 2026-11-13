# KP-T1 — Profil PT yang jujur dan bisa diubah

| | |
|---|---|
| Gelombang | Jalur konfigurasi perusahaan (U) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | KF-T1 |
| Menutup temuan | KP-01, KP-02, KP-23 |
| Keputusan | K-08, K-10; jawaban pemilik butir 3 dan 4 |
| Standar | §2.2, §3.1 (Z1, Z6), §3.4 (N1), §4 (L1, L2, L5, L6, L7), §5 (D1, D8), §6 |
| Lingkungan uji | B |

## Tujuan

Setiap isian pada profil PT benar-benar dipakai mesin. Status PKP bisa diubah dari layar dengan alasan, tanggal berlaku,
dan pratinjau dampak. Tahun buku dan mata uang hanya punya satu sumber, dan NPWP, mata uang, serta tahun buku tidak
lagi menerima isi yang salah bentuk.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| # | Fakta | Jangkar |
|---|---|---|
| 1 | Lima isian master PT hanya disimpan dan dikirim balik; tidak ada kode lain yang membacanya: `numbering_scheme`, `incentive_payer`, `fiscal_year_start`, `coa_template`, `parent_entity_id` | `backend/services/entity_context_service.py:24` (`ENTITY_DEFAULTS`); `backend/services/entity_lifecycle_service.py:40` (`EDITABLE_FIELDS`); `backend/services/entity_lifecycle_service.py:95` (`uniform_entity`) |
| 2 | Wizard menawarkan "Awal tahun fiskal (MM-DD)" dengan keterangan "Menentukan periode laporan & tutup buku.", "Penanggung insentif sales" (pilihan "Tingkat grup"), dan "Skema penomoran" (pilihan "Deret bersama grup") | `frontend/src/features/settings/entities/EntityWizard.jsx:292` (`fiscal_year_start`); `frontend/src/features/settings/entities/EntityWizard.jsx:300` (`incentive_payer`); `frontend/src/features/settings/entities/EntityWizard.jsx:350` (`numbering_scheme`) |
| 3 | Tahun buku yang dipakai tutup buku berasal dari kunci `finance.fiscal_year_end_month` (berlapis grup → PT), bukan dari master PT | `backend/services/closing_service.py:76` (`period_bounds`); `backend/config_catalog_core.py:91` (`finance.fiscal_year_end_month`) |
| 4 | Mata uang yang dipakai laporan dan cetak berasal dari kunci `finance.base_currency`; `business_entities.currency` hanya ditampilkan di daftar PT dan di baris konsolidasi | `backend/services/config_currency.py:31` (`base_currency`); `backend/services/gl_service.py:3739` (`consolidation`); `frontend/src/features/settings/entities/EntityList.jsx:213` (`currency`) |
| 5 | Di wizard, mata uang adalah teks bebas | `frontend/src/features/settings/entities/EntityWizard.jsx:287` (`entity-wizard-currency-input`) |
| 6 | Parameter `scheme` pada penomoran tidak pernah diisi dari master PT; nilainya ditentukan tiap titik panggil | `backend/core_utils.py:19` (`next_doc_number`) |
| 7 | Layar detail PT tidak punya isian status PKP; status hanya ditampilkan | `frontend/src/features/settings/entities/EntityDetailDrawer.jsx:19` (`EDITABLE`); `frontend/src/features/settings/entities/EntityDetailDrawer.jsx:140` (`is_pkp`) |
| 8 | Server menerima `default_tax_mode` lewat `PATCH /api/entities/{id}` tanpa alasan, tanpa tanggal, tanpa jejak khusus | `backend/routers/entities.py:162` (`update_entity`); `backend/services/entity_provisioning_service.py:100` (`default_tax_mode`) |
| 9 | PT non-PKP dipaksa bertarif PPN 0 dan e-faktur mati; status dibaca langsung dari `default_tax_mode` saat dokumen dihitung | `backend/services/config_service.py:250` (`get_effective_settings`); `backend/services/tax_invoice_service.py:32` (`_entity_is_pkp`) |
| 10 | Validasi: NPWP hanya "wajib bila PKP" tanpa pola; tahun fiskal cukup dua digit-dua digit sehingga `13-45` lolos; mata uang tidak diperiksa | `backend/services/entity_provisioning_service.py:106` (`npwp`); `backend/services/entity_provisioning_service.py:132` (`fiscal_year_start`) |
| 11 | `is_group` dibaca konsolidasi dan empat layar keuangan, tetapi tidak punya isian di layar mana pun | `backend/services/consolidation_service.py:132` (`summary`); `frontend/src/features/finance/ClosingView.jsx:49` (`is_group`) |
| 12 | Butir kesiapan "Tahun fiskal" membaca `fiscal_year_start` | `backend/services/entity_readiness_service.py:109` (`fiscal_year`) |

Yang sudah benar dan dipertahankan: satu jalur validasi untuk buat dan ubah —
`backend/services/entity_provisioning_service.py:47` (`validate_entity_input`); kunci kode dokumen setelah dokumen
pertama — `backend/services/entity_lifecycle_service.py:188` (`assert_prefix_change_allowed`).

## Perubahan

### Data

Keputusan per isian mati (sumber tunggal dinyatakan di kolom terakhir):

| Isian | Diapakan | Sumber tunggal sesudahnya |
|---|---|---|
| `numbering_scheme` | Dibuang dari layar, skema, bawaan, dan jawaban | Tabel "Penomoran Dokumen" (unit KP-T5) |
| `incentive_payer` | Dibuang dari layar, skema, bawaan, dan jawaban | Pengaturan insentif (`commission.*`; modul insentif K-19 … K-26) |
| `coa_template` | Dibuang; kalimat wizard tidak lagi menyebut nama templat | Bagan akun bersama (`gl_service.seed_default_coa`) |
| `parent_entity_id` | Dibuang dari daftar yang bisa diubah dan dari jawaban | `is_group` + `ownership_pct` |
| `fiscal_year_start` | Disambungkan: layar menampilkan dan mengubah kunci registry | `finance.fiscal_year_end_month` (lapisan PT) |
| `currency` | Disambungkan: layar menampilkan dan mengubah kunci registry | `finance.base_currency` (lapisan PT) |

Koleksi `business_entities`:

| Field | Tipe | Wajib | Arti |
|---|---|---|---|
| `ownership_pct` | angka, > 0 dan ≤ 100, dua desimal | ya, bawaan 100 | Persen kepemilikan grup atas PT ini (K-10). Dibaca unit PK-31 |
| `tax_status_history` | daftar objek `{from, to, effective_date, reason, by, by_id, at}` | tidak | Riwayat perubahan status PKP; hanya ditambah |
| `tax_status_pending` | objek `{to, effective_date, reason, by, by_id, at}` atau tidak ada | tidak | Perubahan status PKP bertanggal berlaku di masa depan |

`default_tax_mode` tetap menjadi nilai yang dibaca mesin (K-08). Tanpa indeks baru.

Migrasi (`scripts/migrate_kpt1_profil_pt.py`, bawaan hanya-lapor; dijalankan pada data nyata oleh pemilik — H3):

1. Mengisi `ownership_pct: 100` pada PT yang belum punya.
2. **Tidak** menyalin `fiscal_year_start` maupun `currency` ke registry, karena mesin hari ini sudah memakai registry
   dan menyalin akan mengubah perilaku. Skrip hanya melaporkan PT yang isinya berbeda: bulan akhir tersirat
   (`MM` − 1; `01` → 12) ≠ nilai efektif `finance.fiscal_year_end_month`, atau `currency` ≠ nilai efektif
   `finance.base_currency`.
3. Melaporkan PT yang NPWP-nya bukan 15 atau 16 digit.
4. Field lama di dokumen PT tidak dihapus (`00` §7 butir 2); hanya tidak lagi dibaca, ditulis, atau dikirim.

### Server

`backend/services/entity_context_service.py`: `ENTITY_DEFAULTS` menjadi `{"is_group": False, "ownership_pct": 100.0}`.

`backend/services/entity_lifecycle_service.py`:

- `EDITABLE_FIELDS` membuang `currency`, `parent_entity_id`, `coa_template`, `fiscal_year_start`, `incentive_payer`,
  `numbering_scheme`, `default_tax_mode`; menambah `ownership_pct`. `is_group` tetap.
- `uniform_entity` membuang enam field mati di atas dan `currency`; menambah `ownership_pct`, `tax_status_pending`.
- `async def profile_settings(entity_id) -> dict` → `{"base_currency", "fiscal_year_end_month",
  "base_currency_source", "fiscal_year_end_month_source"}` dari `config_resolver.resolve(key, {"entity_id": …})`
  (`source` = `source_layer`). Router menempelkan hasilnya ke jawaban `GET /api/entities`, `GET /api/entities/{id}`,
  `POST`, dan `PATCH`, serta mengisi `currency` = `base_currency` supaya daftar PT tidak berubah bentuk.
- `async def apply_due_tax_status(today: str | None = None) -> int` — menerapkan `tax_status_pending` yang
  `effective_date` ≤ hari ini (WIB). Dipanggil saat aplikasi menyala dan oleh job harian baru
  `entity_tax_status_due` ("Terapkan Perubahan Status PKP Terjadwal", harian 00.05) di `scheduler_service.JOBS`.

`backend/services/gl_service.py` (`consolidation`): `currency` baris diambil dari `config_currency.base_currency(eid)`.

`backend/services/entity_provisioning_service.py` (`validate_entity_input`), berlaku hanya untuk field yang dikirim
dan nilainya berubah, supaya data lama tidak menghalangi perubahan lain:

| Field | Aturan | Galat 400 |
|---|---|---|
| `npwp` | Setelah titik, strip, dan spasi dibuang: tepat 15 atau 16 digit. Disimpan seperti diketik (dipangkas) | "NPWP harus 15 atau 16 digit angka. Periksa kembali nomor yang diketik." |
| `ownership_pct` | angka > 0 dan ≤ 100 | "Persen kepemilikan harus lebih dari 0 dan paling banyak 100." |
| `is_group` | boolean | "Isian PT induk harus ya atau tidak." |
| `default_tax_mode` pada PATCH, berbeda dari nilai sekarang | ditolak | "Status PKP diubah lewat tindakan 'Ubah status PKP', bukan lewat ubah profil." |

`POST /api/entities` (izin `entity.create`): `BusinessEntityCreate` membuang enam field mati dan `currency`; menambah
`ownership_pct: float = 100`, `base_currency: Optional[str]`, `fiscal_year_end_month: Optional[int]`. Bila salah satu
dari dua yang terakhir dikirim dan berbeda dari nilai efektif grup, `provision_entity` menulis lapisan PT lewat
`config_resolver.set_value(key, nilai, scope_type="entity", scope_id=<id PT baru>, reason="Ditetapkan saat PT dibuat")`.
Nilai tak sah → 400 dengan pesan dari registry (pilihan mata uang; bulan 1–12).

Endpoint baru (izin `entity.update`; PT harus aktif, selain itu 409 "PT ini sudah diarsipkan."):

| Metode + path | Isi permintaan | Jawaban |
|---|---|---|
| `GET /api/entities/{id}/tax-status/preview?to=&effective_date=` | `to` ∈ `ppn`, `non_ppn`; `effective_date` `YYYY-MM-DD` | `{entity_id, current, to, effective_date, applies: "sekarang"\|"terjadwal", npwp_ok, open_documents: [{collection, label, count, examples}], documents_since: [{collection, label, count}], tax_invoices_issued, setting_layers: [{key, label, value}], blockers: [teks], can_apply}` |
| `POST /api/entities/{id}/tax-status` | `{to, effective_date, reason, npwp?}` | profil PT seragam + `tax_status_history`; bila terjadwal: `tax_status_pending` terisi dan `default_tax_mode` belum berubah |
| `DELETE /api/entities/{id}/tax-status/pending` | — | profil PT; `tax_status_pending` hilang. 404 bila tidak ada yang terjadwal |

Isi pratinjau: `open_documents` = `sales_orders` dan `purchase_orders` PT itu yang statusnya di luar
`CLOSED_STATUSES` (hitungan pajaknya memakai status lama dan **tidak** diubah); `documents_since` = dua koleksi yang
sama dengan `created_at` ≥ `effective_date` (terisi hanya bila tanggal berlaku sebelum hari ini);
`tax_invoices_issued` = jumlah `tax_invoices` PT itu; `setting_layers` = nilai lapisan PT untuk `tax.ppn_rate` dan
`tax.efaktur_enabled` yang akan mulai atau berhenti dipakai.

Urutan `POST …/tax-status`: periksa izin dan cakupan PT (`guard` entitas, N1) → `to` sah dan berbeda dari sekarang →
bila `to = ppn`: NPWP ada (dari PT atau dari `npwp` di permintaan) dan lolos pola → `reason` tidak kosong →
`effective_date` sah → bila tanggal ≤ hari ini (WIB): ubah bersyarat `{id, default_tax_mode: <nilai lama>}` dengan
`$set default_tax_mode`, `$push tax_status_history`, `$unset tax_status_pending`; bila tanggal > hari ini: `$set
tax_status_pending` → catat jejak `entity_tax_status_changed` atau `entity_tax_status_scheduled`.

| Kode | Keadaan | Pesan |
|---|---|---|
| 400 | `to` sama dengan status sekarang | "PT ini sudah berstatus {PKP/Non-PKP}." |
| 400 | NPWP kosong saat menjadi PKP | "PT yang menjadi PKP wajib mengisi NPWP." |
| 400 | Alasan kosong | "Alasan perubahan status PKP wajib diisi." |
| 400 | Tanggal tidak sah | "Tanggal berlaku tidak valid." |
| 409 | Status sudah berubah oleh proses lain | "Status PKP sudah diubah oleh proses lain. Muat ulang lalu periksa kembali." |

### Pengaturan

Tidak ada kunci baru. Dua kunci yang ada (`finance.base_currency`, `finance.fiscal_year_end_month`) menjadi sumber
tunggal dan ditampilkan di profil PT.

### Izin dan peran

Tidak ada pasangan izin baru. Semua tindakan memakai `entity.create` / `entity.update` yang sudah ada.

### Layar

Tempat: Pengaturan › Perusahaan & Akun › Badan Usaha & Akses › tab Badan Usaha.

`EntityWizard.jsx`:

- Langkah 2: "Mata uang" menjadi pilihan berlabel **Mata uang pembukuan** (isi dari `options` kunci registry);
  "Awal tahun fiskal (MM-DD)" diganti pilihan dua belas bulan berlabel **Tahun buku berakhir pada bulan** dengan
  keterangan "Menentukan batas tahun buku pada laporan dan tutup buku tahunan." Keduanya berbawaan nilai grup.
- Langkah 2: isian "Penanggung insentif sales" dibuang; kalimat bagan akun menjadi "Bagan akun dipakai bersama semua
  PT — kode akun sama, bukunya terpisah."
- Langkah 2: tambah sakelar **PT induk (konsolidasi)** dengan keterangan "PT induk tidak ikut dijumlahkan sebagai
  baris di laporan konsolidasi dan tidak muncul di pilihan PT pada tutup buku." dan isian **Persen kepemilikan (%)**
  (mati bila PT induk) dengan keterangan "Belum memengaruhi angka — dipakai laporan konsolidasi setelah eliminasi per
  periode aktif."
- Langkah 3: isian "Skema penomoran" dibuang; keterangan kode dokumen menjadi "Dipakai sebagai awalan nomor dokumen
  yang bernomor per PT, mis. pesanan, faktur pajak, kwitansi."
- Validasi di tempat untuk NPWP (15/16 digit) dengan pesan yang sama dengan server.

`EntityDetailDrawer.jsx`:

- Bagian "Identitas & kontak": isian "Awal tahun fiskal" dibuang.
- Bagian baru **Pajak**: baris "Status: PKP (memungut PPN)" atau "Status: Non-PKP (tanpa PPN)", tanggal berlaku
  terakhir, dan tombol **Ubah status PKP**. Bila ada yang terjadwal: "Akan menjadi {status} mulai {tanggal}" + tombol
  **Batalkan jadwal**.
- Pop-up **Ubah Status PKP** (pop-up baku, L7): "Status baru", "Berlaku mulai" (tanggal), "NPWP" (tampil bila menjadi
  PKP dan NPWP kosong), "Alasan", lalu panel **Dampak** yang memuat pratinjau: "{n} pesanan penjualan dan {m} pesanan
  pembelian yang masih berjalan tetap memakai hitungan pajak lama.", dan nilai pengaturan pajak PT yang mulai atau
  berhenti dipakai. Tombol **Ubah Status PKP** mati selama `can_apply` salah.
- Bagian baru **Tahun buku & mata uang**: "Tahun buku: {bulan awal}–{bulan akhir}" dan "Mata uang pembukuan: {label}",
  masing-masing dengan keterangan sumber ("mengikuti pengaturan grup" / "khusus PT ini") dan tombol **Ubah** yang
  membuka editor pengaturan baku (`SettingEditor`) untuk kunci itu pada lapisan PT (alasan wajib untuk tahun buku).
- Bagian baru **Grup & konsolidasi**: sakelar **PT induk (konsolidasi)** dan **Persen kepemilikan (%)**.

Keadaan memuat, galat, dan kosong mengikuti pola layar yang ada (`ErrorNotice`, kerangka abu-abu).

## Uji penerimaan

Persiapan bersama: seed lingkungan B (`ent_ksc` PKP, `ent_kanda` non-PKP), akun admin.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | `GET /api/entities/ent_ksc` | Tidak memuat kunci `numbering_scheme`, `incentive_payer`, `coa_template`, `fiscal_year_start`, `parent_entity_id`; memuat `ownership_pct: 100`, `fiscal_year_end_month: 12`, `base_currency: "IDR"`, `currency: "IDR"` |
| U2 | B | — | `POST /api/entities` dengan `numbering_scheme: "shared"`, `incentive_payer: "group"` ikut dikirim | 200; dokumen PT di database tidak punya dua field itu |
| U3 | B | — | `POST /api/entities` dengan `fiscal_year_end_month: 3`, `base_currency: "USD"` | 200; `value_of("finance.fiscal_year_end_month", {entity_id: baru})` = 3; untuk `ent_ksc` tetap 12; `closing_service.period_bounds("year", "2026", baru)` = (`2025-04-01`, `2026-03-31`) |
| U4 | B | — | `POST /api/entities` dengan `fiscal_year_end_month: 13` | 400; tidak ada PT baru |
| U5 | B | — | `PATCH /api/entities/ent_ksc` `{"data": {"npwp": "12345"}}` | 400 "NPWP harus 15 atau 16 digit angka…"; NPWP tetap |
| U6 | B | — | `PATCH` `{"data": {"npwp": "01.234.567.8-901.000"}}` lalu `{"data": {"npwp": "1234567890123456"}}` | 200 dan 200 |
| U7 | B | NPWP `ent_kanda` diisi langsung di database dengan `"abc"` | `PATCH /api/entities/ent_kanda` `{"data": {"address": "Jl. Baru 1"}}` | 200 (field yang tidak dikirim tidak divalidasi ulang) |
| U8 | B | — | `PATCH /api/entities/ent_kanda` `{"data": {"default_tax_mode": "ppn"}}` | 400 "Status PKP diubah lewat tindakan 'Ubah status PKP'…"; status tetap `non_ppn` |
| U9 | B | Satu `sales_orders` berstatus `draft` milik `ent_kanda` (fixture) | `GET …/ent_kanda/tax-status/preview?to=ppn&effective_date=<hari ini>` | 200; `applies: "sekarang"`; `open_documents` memuat `sales_orders` dengan `count: 1`; `can_apply` benar (NPWP seed terisi) |
| U10 | B | — | `POST …/ent_kanda/tax-status` `{to: "ppn", effective_date: <hari ini>, reason: ""}` | 400 "Alasan perubahan status PKP wajib diisi."; status tetap |
| U11 | B | — | `POST …/ent_kanda/tax-status` `{to: "ppn", effective_date: <hari ini>, reason: "Dikukuhkan PKP"}` | 200; `default_tax_mode: "ppn"`; `tax_status_history` 1 baris `{from: "non_ppn", to: "ppn"}`; `get_effective_settings("ent_kanda")["tax"]["ppn_rate"]` = 12.0 (sebelumnya 0.0); untuk `ent_ksc` tidak berubah; jejak `entity_tax_status_changed` ada |
| U12 | B | — | `POST …/ent_ksc/tax-status` `{to: "non_ppn", effective_date: <besok>, reason: "Dicabut"}` lalu `apply_due_tax_status(today=<hari ini>)` lalu `apply_due_tax_status(today=<besok>)` | Setelah POST: status tetap `ppn`, `tax_status_pending` terisi. Panggilan pertama mengembalikan 0. Panggilan kedua mengembalikan 1; status `non_ppn`; riwayat bertambah 1; `tax_status_pending` hilang |
| U13 | B | `ent_kanda` NPWP dikosongkan | `POST …/ent_kanda/tax-status` `{to: "ppn", …, reason: "x"}` tanpa `npwp` | 400 "PT yang menjadi PKP wajib mengisi NPWP." |
| U14 | B | — | `PATCH /api/entities/ent_ksc` `{"data": {"is_group": true, "ownership_pct": 60}}` lalu `GET /api/entities` | 200; `is_group: true`, `ownership_pct: 60`; `consolidation_service.summary` untuk kedua PT tidak memuat baris `ent_ksc`; `ent_kanda` tetap `is_group: false`, `ownership_pct: 100` |
| U15 | B | — | `PATCH` `{"data": {"ownership_pct": 0}}` dan `{"data": {"ownership_pct": 101}}` | 400 dan 400 |
| U16 | B | Peran **Tanpa Acuan** berizin `entity.update`; peran **Manajer Kosong** | Keduanya `POST …/tax-status` dengan isi sah | 200 dan 403 |
| U17 | layar (uji jalan) | Login admin | Buat PT lewat wizard; buka detail; ubah status PKP | Wizard tanpa "Skema penomoran" dan "Penanggung insentif sales"; pop-up menampilkan panel Dampak; setelah simpan lencana berubah |

## Langkah kerja

1. `backend/tests_mem/test_KPT1_profil_pt.py`: U1–U16 (merah).
2. Buang field mati dari bawaan, skema, daftar ubah, dan jawaban; `profile_settings`; penyesuaian `consolidation`.
3. Validasi NPWP, `ownership_pct`, `is_group`; penolakan `default_tax_mode` lewat PATCH.
4. Tiga endpoint status PKP, `apply_due_tax_status`, job harian.
5. Butir kesiapan `fiscal_year` membaca nilai efektif registry (isi daftar lengkap dikerjakan KP-T2).
6. Wizard dan layar detail; skrip migrasi (hanya-lapor) beserta ujinya di data acuan.
7. Gate; laporan.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (field `business_entities` baru dan yang tidak dipakai lagi); `memory/PRD.md` (tindakan ubah
status PKP); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("PT induk (konsolidasi)", "Persen kepemilikan").

## Di luar lingkup

- Tabel penomoran per jenis dokumen → KP-T5.
- Tampilan "tarif PPN lapisan PT tidak dipakai karena non-PKP" di Pusat Pengaturan → KF-T3.
- Pengaturan pajak bertanggal berlaku dan pemakaian status PKP menurut tanggal dokumen → TX-T1.
- Hitungan konsolidasi memakai `ownership_pct` → PK-31.
- Daftar kesiapan baru dan langkah "Lengkapi PT" → KP-T2. Susunan dan nama hub → KP-T9.
- NITKU, NIB, KPP, alamat pajak, nama direktur: tidak ada keputusan; tidak ditambahkan.

## Asumsi dan risiko

- `ASUMSI:` pola NPWP yang sah adalah 15 atau 16 digit (usulan audit KP-23); tidak ada pemeriksaan digit cek.
- `ASUMSI:` tanggal berlaku status PKP boleh mundur, hari ini, atau maju. Tanggal mundur diterapkan saat itu juga dan
  dokumen yang sudah ada tidak dihitung ulang; pratinjau hanya menyebut jumlahnya.
- `ASUMSI:` dokumen yang menyimpan hitungan pajak dan perlu disebut di pratinjau adalah pesanan penjualan dan pesanan
  pembelian (keduanya dihitung `config_service.compute_order_pricing`).
- `ASUMSI:` tidak ada layar yang membaca `currency` dari `/auth/context`; pencarian di `frontend/src` hanya menemukan
  daftar PT dan wizard.
- `ASUMSI:` satu grup hanya punya satu tingkat induk, sehingga `parent_entity_id` tidak diperlukan.
- `RISIKO:` berkas uji lama `backend/backend_test_f0a_entity_context.py` menegaskan field mati masih ada; ia
  diperbarui di unit ini. Membatalkan: kembalikan `ENTITY_DEFAULTS` dan `EDITABLE_FIELDS`; data lama tidak disentuh.
- `RISIKO:` PT yang master-nya berisi tahun buku atau mata uang berbeda dari registry akan terlihat "berubah" di
  layar, padahal mesin memang sudah memakai registry. Skrip migrasi melaporkannya lebih dulu.

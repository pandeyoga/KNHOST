# KM-T1 — Sediakan data insentif: omzet terkirim, pencairan, harga acuan, dan target per PT

| | |
|---|---|
| Gelombang | Modul — Meja Insentif |
| Jenis | fitur |
| Risiko | tinggi |
| Prasyarat | PK-19 |
| Menutup temuan | KM-01, KM-02, KM-03, KM-04, KM-06 |
| Keputusan | K-19, K-20, K-21, K-23, K-24 |
| Standar | §2.1, §2.2, §2.4, §3.1 (Z1, Z2), §3.2, §3.4 (N1, N3), §5 (D1, D2, D4, D5, D6, D7, D9), §6 |
| Lingkungan uji | keduanya (B untuk alur dan angka; A untuk indeks unik) |

## Tujuan

Angka dasar insentif tersedia dan bisa dipercaya: omzet barang terkirim per sales, uang masuk per sales, harga acuan di
tiap baris pesanan, dan target per PT per bulan/triwulan/tahun. Omzet cocok dengan akun pendapatan dan pencairan cocok
dengan kas masuk pelanggan. Unit ini belum menampilkan layar Capaian (KM-T2) dan tidak menghitung nominal insentif.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

- Target berkunci (sales, periode) tanpa PT, `backend/routers/crm.py:395` (`sales_targets`), dan PT-nya dipaksa PT asal
  sales: `backend/routers/crm.py:381` (`home_entity_id`). `period_type` diterima, `backend/schemas_crm.py:40`
  (`period_type`), tetapi triwulan dan tahun dihitung sebagai jumlah target bulanan:
  `backend/services/sales_force_service.py:164` (`_target_collection_for`). Asisten analitik sudah menyaring
  `period_type: "month"`: `backend/services/analytics_engine.py:222` (`period_type`).
- Target hanya bisa diberikan ke akun berperan persis `sales` (PR-UX-04): `backend/routers/crm.py:372`
  (`create_target`); daftar pilihnya sama: `backend/routers/crm.py:48` (`list_sales_users`).
- "Pencairan" menjumlah semua baris `payments[]`: `backend/services/sales_force_service.py:109` (`total_collected`),
  termasuk hapus sisa, `backend/services/payment_variance_service.py:459` (`writeoff`), dan nota kredit,
  `backend/services/return_service.py:352` (`apply_from_case`). Sumber lain dibedakan hanya lewat `method`:
  `backend/services/ar_receipt_service.py:189` (`apply_from_deposit`),
  `backend/services/ar_receipt_service.py:210` (`apply_from_bank_holding`).
- Batal kwitansi menulis ulang `payments[]` tanpa baris kwitansi itu, sehingga angka periode lalu berubah mundur:
  `backend/services/ar_receipt_service.py:739` (`paid_total`).
- Kwitansi memisahkan kas baru dan deposit terpakai, `backend/services/ar_receipt_service.py:577` (`used_deposit`),
  tetapi baris alokasi di pesanan tidak: `backend/services/ar_receipt_service.py:380` (`payment`). Kas masuknya
  ditandai `backend/services/ar_receipt_service.py:91` (`ref_type`). Giro langsung menjadi kas saat kwitansi dicatat;
  tanggal cair tidak ada: `backend/services/ar_receipt_service.py:56` (`_cash_routing`).
- Diskon baris selalu 0: `backend/routers/sales_orders.py:290` (`discount_percent`). `normal_price` hanya ada di baris
  harga khusus, `backend/routers/sales_orders.py:285` (`normal_price`), dan isinya harga langganan pelanggan bila ada,
  bukan harga daftar PT: `backend/routers/sales_orders.py:226` (`base_sell_price`). Harga daftar PT dan harga umum
  tersedia saat pesanan dibuat, `backend/services/customer_price_service.py:153` (`global_price`); batas bawah dihitung
  `backend/services/price_guard_service.py:66` (`floor_for`); keduanya tidak dipotret.
- Tiga aturan "milik siapa": pemilik pelanggan kini, `backend/services/sales_force_service.py:93`
  (`assigned_sales_id`); pemilik atau tim, `backend/services/sales_force_service.py:323` (`order_filter`); tim → sales
  pesanan → pembuat → pemilik, `backend/services/analytics_facts.py:41` (`attribute_sales`).
- Serah-terima pelanggan hanya mengganti `backend/routers/crm.py:81` (`assigned_sales_id`), sedangkan pesanan baru
  mewarisi `sales_team` pelanggan lebih dulu: `backend/services/customer_service.py:83`
  (`resolve_customer_sales_team`), dipakai `backend/routers/sales_orders.py:636` (`sales_team`).
- Fakta yang ada berdasar tanggal pesanan dan tidak membaca pembayaran: `backend/services/analytics_facts.py:82`
  (`build_rows`), `backend/services/analytics_facts.py:31` (`_SO_FIELDS`); segar tiap 5 menit, bangun ulang malam:
  `backend/services/scheduler_service.py:256` (`job_fact_sync`).
- Pendapatan diakui per surat jalan (`shipment_revenue`): `backend/services/gl_service.py:1092`
  (`post_shipment_revenue`); porsinya `backend/services/gl_service.py:1067` (`shipment_value_share`); surat jalan
  penutup mengambil sisa: `backend/services/gl_service.py:1080` (`_is_closing_shipment`). Nilai dan biaya per surat
  jalan sudah dihitung laporan profitabilitas: `backend/services/profitability_service.py:185` (`_shipment_row`). Retur
  dan koreksi mendebit akun yang sama: `backend/services/gl_service.py:2539` (`sales_return_lines`),
  `backend/services/gl_service.py:2613` (`post_amendment_credit_note`). Surat jalan tidak menyimpan rupiah:
  `backend/services/shipment_service.py:97` (`shipment`). Tahun buku per PT:
  `backend/services/config_currency.py:58` (`fiscal_year_of`).

## Perubahan

### Data

**`sales_targets` (diubah).** Kunci baru (PT, sales, jenis periode, periode). Field: `entity_id` (wajib; PT target dari
konteks pengguna — N1 — bukan PT asal sales), `sales_id` dan `sales_name` (akun aktif mana pun yang ditugaskan di PT
itu), `period_type` (`month` · `quarter` · `year`), `period` (`YYYY-MM` · `YYYY-Qn` · `YYYY`; untuk triwulan dan tahun,
`YYYY` = tahun berakhirnya tahun buku PT — K-24), `target_sales_amount` dan `target_collection_amount` (angka ≥ 0,
tersendiri per jenis periode), `target_new_customers`, `notes`. Indeks unik `uq_target_pt_sales_periode` pada
(`entity_id`, `sales_id`, `period_type`, `period`). Migrasi (skrip baru `scripts/migrate_sales_targets_km_t1.py`, diuji
di data acuan; data nyata = H3): `period` berbentuk `YYYY-MM` → `period_type = "month"`; `entity_id` kosong → PT asal
sales. Kunci kembar setelah migrasi → H6.

**`incentive_components` (baru, per PT).** `id` (`icomp_`), `entity_id`, `code` (huruf besar, unik per PT), `name`,
`basis_period_type` (`month` · `quarter` · `year` · `free`), `columns` (daftar dari `omzet`, `pencairan`, `harga`),
`taxable` (bawaan ya), `is_active`, jejak pembuat. Indeks unik (`entity_id`, `code`). Tanpa isi bawaan.
**`incentive_definitions` (baru, hanya-tambah).** `id`, `entity_id`, `version` (bilangan naik), `effective_from`
(tanggal WIB), `dasar_omzet`, `isi_pencairan`, `pemilik_angka`, `harga_acuan`, `recorded_at`. Indeks unik
(`entity_id`, `version`). Pemilik nilainya tetap Pusat Pengaturan; koleksi ini mencatat versi untuk potret KM-T3.

**Baris pesanan `sales_orders.items[]` (ditambah, untuk semua baris baru):** `list_price` (harga daftar PT per satuan
jual saat pesanan dibuat; bila PT belum punya harga, harga umum), `list_price_source` (`entity` · `global`),
`global_price`, `floor_price` (batas bawah dari `floor_for`, boleh kosong), `floor_from`. Pesanan ditambah
`sales_attribution: [{sales_id, split}]`, potret hasil `attribute_sales` saat pesanan dibuat (K-21). Pesanan lama:
skrip baru `scripts/backfill_order_price_refs.py` mengisi `list_price = price` hanya untuk baris ber-`price_source`
`entity` atau `global` (nilainya pasti sama); baris lain dibiarkan kosong dan dilaporkan jumlahnya.

**`fact_shipment_sales` (baru, turunan).** Satu dokumen per (sumber × baris pesanan × sales).

| Field | Arti |
|---|---|
| `_id` | `<source_kind>:<source_id>:<line_idx>:<sales_id>` |
| `source_kind`, `source_id`, `source_number` | `kirim` (surat jalan) · `retur` (nota kredit retur) · `koreksi` (nota kredit amandemen) · `pesanan_lama` (pesanan berpendapatan tanpa surat jalan); id dan nomor dokumen sumbernya |
| `entity_id`, `so_id`, `so_number`, `customer_id`, `customer_name`, `line_idx` | Dari pesanan; baris dicari lewat produk seperti `_order_item_for`; `line_idx` kosong untuk nota kredit |
| `sales_id`, `split` | Dari `sales_attribution`; `""` = tanpa sales |
| `product_id`, `sku`, `category`, `line_code`, `price_source`, `qty_base` | Dari baris pesanan dan surat jalan |
| `net` | Rupiah tanpa PPN × `split`; negatif untuk `retur` dan `koreksi` |
| `list_value`, `global_value`, `floor_value` | `net × harga pembanding ÷ price` baris; kosong bila pembandingnya kosong |
| `cost`, `cost_known` | Biaya roll surat jalan; bila tidak ada, `unit_cost × qty`; `cost_known = false` bila 0 |
| `date_wib`, `period`, `built_at`, `build_gen` | Tanggal WIB dokumen sumber, `YYYY-MM`-nya, dan jejak pembangun |

Nilai `kirim`: `nilai bersih pesanan × shipment_value_share`, surat jalan diproses menurut `created_at`; bila pesanan
`shipped`/`done`, surat jalan terakhir mengambil sisa (aturan yang sama dengan jurnalnya). Nilai bersih pesanan dan
alokasi per baris memakai `profitability_service._order_net_alloc`; pembagian ke sales memakai `analytics_facts._alloc`
supaya Σ baris = nilai sumber sampai sen. Indeks: (`entity_id`, `date_wib`), (`entity_id`, `sales_id`, `date_wib`), (`so_id`).

**`fact_collections` (baru, turunan).** Satu dokumen per (baris `payments[]` × sales): `_id`
`<so_id>:<id baris>:<sales_id>`, `entity_id`, `so_id`, `so_number`, `customer_id`, `sales_id`, `split`, `receipt_id`,
`receipt_number`, `source_kind`, `method`, `is_reversal`, `amount` (± rupiah × `split`), `date_wib`, `period`,
`settles_order` (baris yang membuat pesanan lunas), `giro_uncleared`. Indeks sama dengan fakta omzet.
**Titik sambung PK-19:** `source_kind` = hasil `payment_kind(row)` dari `ar_allocation_service` (lahir di PK-19): `kas` ·
`deposit` · `titipan_bank` · `saldo_kredit` · `nota_kredit` · `hapus_sisa` · `kasus`; fungsi itu juga yang membaca baris
lama tanpa `kind`. `is_reversal` = baris ber-`reverses` (baris pembalik PK-19: nilai negatif, `date` = tanggal
pembatalan), sehingga pembatalan mengurangi periode saat batal, bukan periode asal. Unit ini tidak punya pemetaan jenis
sendiri dan tidak mengubah cara batal. Hanya untuk kwitansi lama yang memakai deposit dalam satu baris: deposit dianggap
terpakai lebih dulu menurut urutan `allocations[]`, sisanya `kas`.

Cara membangun ulang (D2): `rebuild(date_from, entity_id)` menulis generasi baru lalu memensiunkan baris basi (pola
`_write` di `analytics_facts.py`); `sync()` memproses dokumen yang berubah sejak tanda air (`ai_fact_state`, id = nama
koleksi); dua tugas terjadwal baru di `scheduler_service.py`: `incentive_fact_sync` (tiap 5 menit) dan
`incentive_fact_nightly` (02.30, bangun ulang 90 hari).

### Server

Berkas baru `backend/services/incentive_facts.py` (pembangun dua fakta, `rebuild`, `sync`, `ensure_fresh`), berkas
baru `backend/services/incentive_periods.py`, berkas baru `backend/services/incentive_definitions.py`, router baru
`backend/routers/incentive.py`. `period_bounds(period_type, period, entity_id) -> (awal, akhir)` mengembalikan tanggal
WIB; triwulan ke-n = tiga bulan ke-n sejak awal tahun buku PT (`fiscal_year_bounds`). `current_definition(entity_id)`
membaca empat kunci `insentif.*`; bila berbeda dari versi terakhir PT itu, menyisipkan versi baru.

| Endpoint | Izin | Isi | Jawaban dan galat |
|---|---|---|---|
| `GET /api/incentive/targets` | `incentive.view` | `period_type`, `period`, `sales_id?` | Daftar target PT aktif |
| `PUT /api/incentive/targets` | `incentive.configure` | `{sales_id, period_type, period, target_sales_amount, target_collection_amount, target_new_customers?, notes?}` | Simpan menurut kunci unik. 400 "Periode tidak sesuai jenisnya. Contoh: 2026-10, 2026-Q4, atau 2026." · 400 "Akun ini tidak ditugaskan di PT yang sedang dibuka." · 409 dari `assert_write_entity` saat "Semua PT" |
| `POST /api/incentive/targets/copy` | `incentive.configure` | `{period_type, from_period, to_period}` | Menyalin target yang belum ada di periode tujuan; `{copied, skipped}` |
| `GET`/`POST`/`PATCH /api/incentive/components[/{id}]` | `incentive.view` / `incentive.configure` | Field komponen | 409 "Kode komponen sudah dipakai di PT ini." |
| `GET /api/incentive/definitions/current` | `incentive.view` | — | Versi berlaku + label Indonesia tiap pilihan |
| `GET /api/incentive/reconciliation` | `incentive.view` | `period=YYYY-MM` | `{omzet: {fakta, buku, selisih, ok, penyebab[]}, pencairan: {dialokasikan, belum_dialokasikan, kwitansi, kas, selisih, ok, penyebab[]}}` |
| `POST /api/incentive/facts/rebuild` | `incentive.configure` | `{date_from?}` | `{rows_shipment, rows_collection}` |

`sales_roster(entity_id, period)` (satu tempat penentu "daftar sales"; bukan gerbang wewenang) = akun yang punya fakta
atau target pada periode itu ∪ akun aktif yang perannya atau peran acuannya `sales`. Perubahan pada kode yang ada:
`create_order` mengisi field harga pembanding dan `sales_attribution`; `analytics_facts.build_rows` memakai
`sales_attribution` bila ada; `reassign_customer` juga mengganti anggota `pic` pada `customers.sales_team` (KM-06) dan
menerima akun dari `sales_roster`; `POST /api/sales-targets` lama meneruskan ke penyimpan baru dengan `period_type =
"month"` sampai layarnya dihapus KM-T5.

Invarian (ditambahkan ke `scripts/verify_data_integrity.py`, dipakai endpoint rekonsiliasi), per PT per bulan WIB:
- `INV-KM-1` omzet = buku: Σ `fact_shipment_sales.net` (semua sales, termasuk tanpa sales) dibanding Σ (kredit − debit)
  akun pendapatan penjualan (kode hasil `remap_lines` untuk `ACC_PENDAPATAN` di PT itu) pada jurnal tidak batal
  ber-`source_type` `shipment_revenue`, `sales_order`, `sales_return`, `amendment_credit_note`; antar-PT, jurnal manual,
  dan penutup berjenis sumber lain sehingga tidak ikut. Lulus bila selisih mutlak < Rp 1 × jumlah pesanan bulan itu;
  `penyebab[]` memuat pesanan berselisih ≥ Rp 1 (jurnal belum terbit, tanggal beda bulan).
- `INV-KM-2` pencairan = kas: A = Σ `fact_collections.amount` jenis `kas` (termasuk pembalik); B = Σ kas
  kwitansi yang belum dialokasikan = `amount − (applied_total − min(used_deposit, applied_total))`; C = Σ
  `ar_receipts.amount` bertanggal di bulan itu dikurangi kwitansi yang `voided_at`-nya di bulan itu; D = Σ
  `cash_transactions` ber-`ref_type: "ar_receipt"` arah masuk, aturan batal sama. Lulus bila |A + B − C| < 1 dan |C − D| < 1.
- `INV-KM-3`: hasil `rebuild` penuh = isi koleksi (jumlah baris dan Σ `net`/`amount` per PT per bulan).

### Pengaturan

Berkas katalog baru `backend/config_catalog_insentif.py`, diimpor di `config_registry.py`. Semua: `group="harga-diskon"`,
`type="enum"`, `scopes=("global", "entity")`, `risk="high"`, `requires_reason=True`, `permission=("incentive", "configure")`.

| key | default | pilihan | label | help · impact · example | consumers |
|---|---|---|---|---|---|
| `insentif.dasar_omzet` | `terkirim` | `pesanan` · `terkirim` · `lunas` | "Omzet insentif dihitung saat" | Kapan penjualan masuk hitungan omzet sales. · Mengubah angka omzet di Capaian sejak versi definisi berikutnya; lembar yang sudah disahkan tidak berubah. · "Pesanan 10 Okt dikirim 3 Nov → `terkirim`: omzet November" | `incentive_definitions.py:current_definition` |
| `insentif.isi_pencairan` | `uang_masuk` | `uang_masuk` · `semua_baris` | "Yang dihitung sebagai pencairan" | `uang_masuk` = jenis `kas` (tunai, transfer, QRIS, giro), `deposit`, dan `titipan_bank`; `semua_baris` = semua jenis, termasuk hapus sisa, nota kredit, saldo kredit, dan kasus. · Mengubah angka uang masuk. · "Hapus sisa Rp 500.000 tidak dihitung pada `uang_masuk`" | sama |
| `insentif.pemilik_angka` | `sales_pesanan` | `sales_pesanan` · `pemilik_pelanggan` | "Angka penjualan milik" | Sales pada pesanan (dengan pembagian tim) atau sales penanggung jawab pelanggan saat ini. · Memindahkan angka antar-sales. · "Pelanggan pindah ke Budi: pesanan lama tetap milik Andi pada `sales_pesanan`" | sama |
| `insentif.harga_acuan` | `daftar_pt` | `daftar_pt` · `umum` · `batas_bawah` | "Harga pembanding kualitas harga" | Harga yang dipakai menilai apakah sales menjual di bawah harga. · Mengubah persen realisasi harga. · "Jual Rp 50.000, harga daftar Rp 58.000 → realisasi 86,2 %" | sama |

### Izin dan peran

Sumber daya baru `incentive`; aksi lain ditambahkan unit yang memeriksanya. `incentive.view` (label "Lihat") → admin,
manager, finance. `incentive.configure` (label "Konfigurasi") → admin, manager, yaitu yang hari ini boleh mengatur target.
Modul akses baru di `MODULE_CATALOG`: id `incentive`, grup "Organisasi", label "Kinerja & Insentif", `resources:
["incentive"]`, `nav: ["hrd", "hr-kpi-hub", "incentive-setup"]`. `RESOURCE_LABEL["incentive"] = "Kinerja & Insentif"`.

### Layar

Hub `hr-kpi-hub` (label entri menu menjadi **Kinerja & Insentif** bila MN-T1 belum mengubahnya), tab baru **Target &
Aturan** (view `incentive-setup`), komponen baru `frontend/src/features/incentive/IncentiveSetupView.jsx`. Banner PT;
saat "Semua PT" tombol simpan mati dengan petunjuk "Pilih satu PT untuk mengatur target." (L4). Tiga bagian:
- **Target** — pilihan "Jenis periode" (Bulan · Triwulan · Tahun) dan periode; kolom "Sales", "Target omzet", "Target
  pencairan", "Target pelanggan baru", "Catatan"; tombol "Simpan" dan "Salin dari periode sebelumnya". Keterangan:
  "Target triwulan dan tahun adalah angka tersendiri, tidak dijumlah dari target bulanan."
- **Komponen insentif** — kolom "Kode", "Nama", "Periode dasar", "Angka yang ditampilkan", "Aktif"; tombol "Tambah
  komponen" (pop-up baku). Kosong: "Belum ada komponen. Tambahkan mis. Insentif Bulanan."
- **Definisi angka** — empat baris hanya-baca, "Berlaku sejak {tanggal} (versi {n})", tautan "Ubah di Pusat
  Pengaturan"; kartu **Pencocokan angka**: "Omzet vs buku besar" dan "Pencairan vs kas masuk", masing-masing "Cocok"
  atau "Selisih Rp …" beserta daftar penyebab.

## Uji penerimaan

Fixture **F1** di `ent_kanda` (non-PKP, tanpa PPN), disisipkan langsung; jurnal diterbitkan `post_order_revenue_and_cogs`
dan fungsi kwitansi asli. Sales S1, S2; pesanan O1 milik S1: 1.000 yd × Rp 50.000 = Rp 50.000.000, `list_price` 55.000,
`unit_cost` 30.000; SJ1 10 Okt 2026 600 yd, SJ2 3 Nov 400 yd (pesanan `shipped`); kwitansi R1 15 Okt transfer
Rp 20.000.000 ke O1; R2 20 Okt tunai Rp 12.000.000, alokasi O1 Rp 10.000.000 (sisa Rp 2.000.000 menjadi deposit); R3 5 Nov
deposit Rp 2.000.000 ke O1; hapus sisa Rp 500.000 pada O1 6 Nov; nota kredit retur CN1 12 Nov atas O1 Rp 5.000.000.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | F1 | `rebuild`; baca `fact_shipment_sales` Okt | Satu baris `kirim` S1: `net` 30.000.000 (50 jt × 600/1.000), `list_value` 33.000.000 (30 jt × 55/50), `cost` 18.000.000 |
| U2 | B | F1 | Baca November | `kirim` 20.000.000 (sisa 50 jt − 30 jt) dan `retur` −5.000.000; Σ = 15.000.000 |
| U3 | B | F1 | `GET /api/incentive/reconciliation?period=2026-10` lalu `2026-11` | Okt: `omzet.fakta` = `omzet.buku` = 30.000.000, `ok: true`. Nov: keduanya 15.000.000 |
| U4 | B | F1 | Baca `fact_collections` Okt | R1 `kas` 20.000.000; R2 `kas` 10.000.000; Σ jenis kas 30.000.000 |
| U5 | B | F1 | Rekonsiliasi Okt, bagian pencairan | `dialokasikan` 30.000.000, `belum_dialokasikan` 2.000.000, `kwitansi` 32.000.000, `kas` 32.000.000, `ok: true` |
| U6 | B | F1 | Baca `fact_collections` Nov | `deposit` 2.000.000 dan `hapus_sisa` 500.000; baris hapus sisa tidak berjenis kas |
| U7 | B | F1; batalkan R1 pada 8 Nov | `sync`; baca Okt dan Nov | Okt tetap memuat +20.000.000; Nov memuat baris `is_reversal` −20.000.000; rekonsiliasi Okt dan Nov tetap `ok` |
| U8 | B | Pesanan O2: tim S1 60 % dan S2 40 %, nilai bersih Rp 1.000.001, satu surat jalan penuh | `rebuild` | S1 600.000,60 dan S2 400.000,40; jumlah 1.000.001,00 |
| U9 | B | Pelanggan C1 milik S1 dengan `sales_team` PIC S1 | `POST /api/customers/{C1}/reassign` ke S2; buat pesanan baru | `sales_attribution` pesanan baru = S2 100 %; O1 tetap S1 |
| U10 | B | — | Buat pesanan: harga langganan Rp 48.000, harga PT Rp 55.000, harga umum Rp 60.000 | Baris: `price` 48.000, `list_price` 55.000, `list_price_source` `entity`, `global_price` 60.000 |
| U11 | B | — | `PUT /api/incentive/targets` untuk S1 bulan `2026-10` di `ent_ksc` dan di `ent_kanda` | Dua dokumen; `GET` di tiap PT hanya mengembalikan milik PT itu |
| U12 | B | Target bulan Jul, Agu, Sep = 100, 200, 300 jt | `PUT` triwulan `2026-Q3` = 700 jt; `GET` triwulan | 700.000.000 (bukan 600.000.000) |
| U13 | B | `finance.fiscal_year_end_month` = 3 untuk `ent_kanda` | `period_bounds("quarter", "2027-Q1", "ent_kanda")` | `2026-04-01` s.d. `2026-06-30` |
| U14 | B | Peran kustom beracuan `sales` ("Sales Senior") | `PUT` target untuk akunnya | 200 (dulu 400 "Salesperson tidak valid") |
| U15 | B | Peran uji baku | `GET /api/incentive/targets` sebagai Tanpa Acuan ber-`incentive.view`; sebagai Manajer Kosong | 200; 403 dengan pesan bentuk Z6 |
| U16 | B | Kunci `insentif.dasar_omzet` | Putaran `t1_config.py` untuk empat kunci; nilai tak sah | Lulus; nilai tak sah 400; versi definisi PT bertambah 1 setelah nilai PT diubah |
| U17 | A | — | Dua `PUT` target bersamaan dengan kunci sama | Satu dokumen |
| U18 | B | F1 | Hapus tiga baris fakta lalu `rebuild` | `INV-KM-3` lulus; jumlah baris kembali |

## Langkah kerja

**Serah-terima (a) — jalur baru; jalur lama tidak disentuh.**
1. `backend/tests_mem/test_KMT1_data_insentif.py`: U1–U8, U11–U13, U15, U16, U18; merah karena fiturnya belum ada.
2. Katalog `insentif.*`, izin, modul akses, koleksi dan indeks, `incentive_periods`, `incentive_definitions`.
3. `incentive_facts` (hanya membaca dokumen sumber), tugas terjadwal, endpoint baca, rekonsiliasi, tiga invarian;
   endpoint target dan komponen; tab Target & Aturan. Gate; catat SHA.
**Serah-terima (b) — menyentuh jalur yang ada.**
4. U9, U10, U14, U17. `create_order` (harga pembanding, `sales_attribution`), `build_rows`, `reassign_customer`,
   penerusan `POST /api/sales-targets`, dua skrip migrasi (dijalankan di data acuan saja).
5. Gate penuh; laporan memuat contoh angka F1 (dokumen → fakta → mutasi akun).

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (lima koleksi, field baris pesanan) dan `scripts/verify_contract.py`; `CODEBASE_MAP.md`;
`memory/PRD.md`; `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("omzet terkirim", "pencairan", "harga acuan").

## Di luar lingkup

- Layar Capaian → KM-T2; lembar → KM-T3; jurnal dan gaji → KM-T4; menghapus mesin komisi dan layar lama → KM-T4, KM-T5.
- Jenis baris pembayaran dan batal-sebagai-pembalik → PK-19; tanggal cair giro → PM-T3; cakupan data dan pengisian
  `sales_id` untuk peran kustom → PR-T4. Rumus bantu (rancangan §4.3) dan impor target dari Excel tidak dibangun.

## Asumsi dan risiko

- `ASUMSI:` kontrak PK-19 dipakai apa adanya: field `kind`, fungsi `payment_kind`, dan baris pembalik ber-`reverses`.
  Bila laporan PK-19 mencatat penyimpangan, hanya pembaca baris di `incentive_facts` yang disesuaikan; U7 tetap berlaku.
- `ASUMSI:` sampai PM-T3 menyediakan tanggal cair, giro dihitung pada tanggal kwitansi dan ditandai `giro_uncleared`
  (K-20 meminta "saat cair"; datanya belum ada di kode).
- `ASUMSI:` jenis `kasus` dan `saldo_kredit` tidak dihitung sebagai uang masuk; pilihan harga acuan "harga langganan"
  tidak disediakan.
- `ASUMSI:` pesanan sample ikut fakta, karena pendapatannya masuk akun yang sama (tanpa itu `INV-KM-1` selisih).
- `ASUMSI:` saat serah-terima pelanggan hanya anggota `pic` yang diganti; anggota pendamping tetap.
- `RISIKO:` fakta tertinggal dari dokumen. Penangkal: `ensure_fresh`, bangun ulang malam, `INV-KM-3`. Membatalkan:
  matikan dua tugas terjadwal dan cabut router; field baru di pesanan tidak dibaca kode lama.

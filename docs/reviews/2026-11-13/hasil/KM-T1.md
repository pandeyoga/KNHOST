# KM-T1 — Sediakan data insentif: omzet terkirim, pencairan, harga acuan, dan target per PT

- Commit awal: `8c8d5ab` (worktree kerja, basis B)        - Commit akhir: (a) `2ed5c53`, (b) `b9753a3`        - Branch: `claude/nifty-carson-jjx3c8`
- Digabung pelaksana ke HEAD `0562d29` (sesudah PK-22, PK-29, AG-T3, PK-43) — lihat "Penggabungan"
- ID ditangani: KM-01, KM-02, KM-03, KM-04, KM-06 (spesifikasi `docs/blueprint/unit/KM-T1.md`; keputusan K-19, K-20, K-21,
  K-23, K-24)
- Risiko tinggi → dua serah-terima (`00` §8): **(a)** jalur baru — katalog `insentif.*`, izin `incentive.*`, modul akses,
  koleksi & indeks, `incentive_periods`, `incentive_definitions`, `incentive_targets`, `incentive_facts` (hanya membaca
  dokumen sumber), dua tugas terjadwal, router `/api/incentive/*`, tiga invarian INV-KM-1…3, tab Target & Aturan; jalur lama
  belum disentuh. **(b)** pengalihan — `create_order` (harga pembanding + `sales_attribution`), `analytics_facts.build_rows`,
  `reassign_customer`, penerusan `POST /api/sales-targets`, dua skrip data lama.

## Cek ulang "Keadaan sekarang" (spesifikasi `3132cc4`, diperiksa di `8c8d5ab`)

| Butir | Hasil di basis B |
|---|---|
| Target berkunci (sales, periode) tanpa PT `crm.py:395`; PT dipaksa PT asal sales `:381`; `period_type` `schemas_crm.py:40`; triwulan/tahun = Σ bulanan `sales_force_service.py:164`; asisten menyaring bulan `analytics_engine.py:222` | Berlaku, bergeser: upsert `crm.py:457`, PT asal `:447`, `schemas_crm.py:40`, `_target_collection_for` `:167` (`_period_contains` hanya mengenal bulan), `analytics_engine.py:226` |
| Target hanya untuk peran persis `sales` `crm.py:372`; daftar pilih `:48` | **Sebagian tidak berlaku** — PR-T4 mengganti ke kategori kerja (`roles_in_category("sales")`, `crm.py:436`, `:55`), jadi peran kustom beracuan Sales sudah diterima jalur lama (U14 "dulu 400" tidak terulang; lihat tabel uji). Yang tetap berlaku: PT target = PT asal sales, kunci tanpa PT |
| "Pencairan" Σ semua `payments[]` `sales_force_service.py:109`, termasuk hapus sisa `payment_variance_service.py:459` & nota kredit `return_service.py:352`; sumber lain hanya lewat `method` `ar_receipt_service.py:189/:210` | Sebagian: Σ semua baris tetap (`:109-113`, dialihkan KM-T5); **sejak PK-19 tiap baris punya `kind`** (`allocate(kind=…)`; `apply_from_deposit`/`apply_from_bank_holding` sudah dihapus) — fakta memakai `payment_kind` |
| Batal kwitansi menulis ulang `payments[]` `ar_receipt_service.py:739` | **Tidak berlaku** — PK-19: baris pembalik bertanggal batal (`ar_allocation_service.reverse`); U7 membuktikan |
| Kwitansi memisahkan kas & deposit `:577` tetapi baris alokasi tidak `:380`; `ref_type` `:91`; giro langsung kas `:56` | Sebagian: `used_deposit` `:372`; **baris alokasi kini dipecah `kas` lalu `deposit`** (PK-19, `allocations[].parts`); `ref_type` `:88`; `_cash_routing` `:54` (giro tanpa tanggal cair — berlaku, `giro_uncleared`) |
| Diskon baris 0 `sales_orders.py:290`; `normal_price` hanya harga khusus `:285` & berisi harga langganan `:226`; harga PT/umum tersedia `customer_price_service.py:153`; batas bawah `price_guard_service.py:66` | Berlaku, bergeser: `:328`, `:286/:291/:323`, `base_sell_price` `:264`; `global_price` `:153`; `floor_for` `:66` |
| Tiga aturan "milik siapa" `sales_force_service.py:93`, `:323`, `analytics_facts.py:41` | Berlaku: `:93`, `:321`, `:41` |
| Serah-terima hanya `assigned_sales_id` `crm.py:81`; pesanan mewarisi `sales_team` `customer_service.py:83`, `sales_orders.py:636` | Berlaku: `crm.py:78-97`, `:93`, `:683` |
| Fakta berdasar tanggal pesanan `analytics_facts.py:82/:31`; sinkron 5 menit `scheduler_service.py:256` | Berlaku: `:82`, `:31`, `:263` |
| Pendapatan per surat jalan `gl_service.py:1092`, porsi `:1067`, penutup `:1080`; `_shipment_row` `profitability_service.py:185`; retur/koreksi `gl_service.py:2539/:2613`; surat jalan tanpa rupiah `shipment_service.py:97`; tahun buku `config_currency.py:58` | Berlaku, bergeser: `:1383`, `:1358`, `:1371`; `:185`; `:2925`, `:2999`; `:101`; `:58` |

## KM-01 / KM-02 / KM-03 / KM-04 / KM-06

- Berlaku di HEAD: sebagian (tabel di atas) — KM-02 batal-sebagai-pembalik dan jenis baris sudah ditutup PK-19; KM-04
  peran kustom sudah diterima sejak PR-T4.
- Akar masalah: angka dasar insentif tidak punya sumber yang bisa dicocokkan — omzet dihitung dari tanggal pesanan,
  pencairan menjumlah semua jenis pelunasan, harga pembanding tidak dipotret, target tanpa PT dan tanpa triwulan/tahun
  tersendiri, tiga aturan atribusi, serah-terima pelanggan tidak mengganti tim.
- Perubahan perilaku (sebelum → sesudah):
  - **Fakta turunan** `fact_shipment_sales` (sumber `kirim` per surat jalan — aturan nilai sama dengan jurnal
    `post_shipment_revenue`, `retur`, `koreksi`, `pesanan_lama`) dan `fact_collections` (tiap baris `payments[]` × sales,
    `source_kind = payment_kind`, pembalik di bulan batal); pembagian sales sampai sen (`analytics_facts._alloc`).
    `rebuild`/`sync`/`ensure_fresh`, tugas `incentive_fact_sync` (5 menit; sekalian memotret versi definisi tiap PT) dan
    `incentive_fact_nightly` (02.30, 90 hari).
  - **Pencocokan** `GET /api/incentive/reconciliation?period=` = INV-KM-1 (omzet fakta = mutasi akun pendapatan penjualan
    pemetaan PT pada jurnal `shipment_revenue`/`sales_order`/`sales_return`/`amendment_credit_note`) + INV-KM-2 (A + B = C,
    C = D) dengan daftar penyebab per pesanan/kwitansi; INV-KM-3 (fakta = bangun ulang). Ketiganya juga lapisan `incentive`
    di `scripts/verify_data_integrity.py` (satu rumus: `services/incentive_facts.py`).
  - **Target per PT** `PUT/GET /api/incentive/targets`, `POST …/copy`: kunci (PT, sales, jenis, periode), indeks unik wajib
    `uq_target_pt_sales_periode`, PT = konteks (N1), sales = akun aktif mana pun yang ditugaskan di PT; triwulan & tahun
    angka tersendiri, batasnya mengikuti tahun buku PT (`incentive_periods.period_bounds`, K-24).
  - **Komponen insentif** per PT (`incentive_components`, kode unik per PT) dan **definisi angka** berversi
    (`incentive_definitions`; empat kunci `insentif.*` bawaan = usulan K-19…K-23, izin `incentive.configure`).
  - **Izin** `incentive.view` (Admin, Manajer, Finance) dan `incentive.configure` (Admin, Manajer); modul akses "Kinerja &
    Insentif" (grup Organisasi). Layar SDM › Kinerja & Insentif › **Target & Aturan** (`incentive-setup`); tab lama
    `incentive-rates` berganti label "Komisi Otomatis".
  - (b) `create_order` memotret `list_price`/`list_price_source`/`global_price`/`floor_price`/`floor_from` di SEMUA baris
    (KM-01) dan `sales_attribution` (KM-03, K-21); `analytics_facts.build_rows` membaca potret (mode tim);
    `reassign_customer` mengganti anggota `pic` `customers.sales_team` dan hanya menerima akun `sales_roster` PT pelanggan
    (KM-06); `POST /api/sales-targets` lama → `save_target` (`period_type = "month"`, PT konteks; Semua PT → 409).
- Berkas berubah: lihat "Berkas" di bawah.
- Fixture disiapkan langsung vs proses bisnis dijalankan: F1 = fixture (pesanan, surat jalan, retur & nota kredit, satu
  baris hapus sisa lewat `allocate`) + jurnal oleh fungsi posting asli + kwitansi lewat `create_receipt` asli + batal lewat
  `void_receipt` asli; U9/U10/U14 lewat API.
- Dampak pada modul terkait: analitik Tanya KN (fakta penjualan memakai potret atribusi untuk pesanan baru); layar lama
  "Set Target" (CRM) kini menyimpan per PT konteks dan menolak saat "Semua PT"; serah-terima pelanggan menolak sales di
  luar PT pelanggan.
- Status: implemented_pending_review

## Berkas

| Serah-terima | Berkas | Isi |
|---|---|---|
| (a) | `backend/config_catalog_insentif.py` (baru), `config_registry.py` | Empat kunci `insentif.*` (kelompok Penjualan & harga, sub-judul Komisi sales) |
| (a) | `backend/permissions_config.py` | `KMT1_DEFAULT_PAIRS` |
| (a) | `backend/access_modules.py` | Modul `incentive` (+ nav `settings-cfg-sales` untuk mengubah `insentif.*`), label, `VIEW_RESOURCE_OVERRIDES["settings-cfg-sales"] += incentive` (aturan KF-T1 U14) |
| (a) | `backend/indexes.py`, `backend/entity_scope.py` | Indeks fakta & target; tiga indeks unik wajib; empat koleksi SCOPED |
| (a) | `backend/services/incentive_periods.py`, `incentive_definitions.py`, `incentive_targets.py`, `incentive_facts.py`, `backend/schemas_incentive.py`, `backend/routers/incentive.py`, `backend/server.py`, `backend/services/scheduler_service.py` (baru/ubah) | Jalur baru |
| (a) | `scripts/verify_data_integrity.py`, `scripts/verify_contract.py` | Lapisan `incentive` (INV-KM-1…3); koleksi kanonik |
| (a) | `frontend/src/features/incentive/IncentiveSetupView.jsx` (baru), `AppViewRouter.jsx`, `appViewImports.js`, `config/hubTabs.js`, `config/navStructure.js` (+ Finance di grup SDM & Kinerja & Insentif), `config/navMeta.js`, `features/settings/config/SettingsHub.jsx`, `features/settings/masters/EntityMastersView.jsx`, `features/crm/IncentiveRatesEditor.jsx` (teks letak tab) | Layar |
| (a) | `configKeyIndex.json`, `access_builtin_fixture.json`, `access_nav_fixture.json`, `view_main_permission.json`, `CODEBASE_MAP.md` | Dibangkitkan / tabel bantu |
| (a) | `ENTITY_REGISTRY.md`, `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (§9.13) | Dokumen |
| (a) uji | `tests_mem/test_KMT1_data_insentif.py` (baru, 21), `features/__tests__/kmt1TargetAturan.test.js` (baru, 7); disesuaikan: `test_KFT1_izin_pengaturan.py` (`KMT1_KUNCI = 4`), `test_PRT9_izin_bawaan.py` (`KMT1_DEFAULT_PAIRS`), `test_PK14_indeks_wajib.py` (`KMT1_INDEKS = 3`), `tests/test_bp_PK14_indeks_wajib.py` (+3), `config/__tests__/mnt1MenuKeuangan.test.js` (hub 5 tab, label), `config/__tests__/roleReach.test.js` (`incentive-setup` untuk admin, manajer, Finance) | |
| (b) | `backend/routers/sales_orders.py` (`_price_refs`, `sales_attribution`), `backend/services/analytics_facts.py` (`snapshot_attribution`), `backend/routers/crm.py` (`reassign_customer`, `create_target`), `backend/services/incentive_targets.py` (`is_sales_account`, kategori kerja), `backend/services/incentive_facts.py` (pakai `snapshot_attribution`) | Pengalihan |
| (b) | `scripts/migrate_sales_targets_km_t1.py`, `scripts/backfill_order_price_refs.py` (baru) | Data lama (baca-saja bawaan; data nyata = H3) |
| (b) | `ENTITY_REGISTRY.md`, `memory/PRD.md` | Field pesanan baru, skrip |
| (b) uji | `tests_mem/test_KMT1_pengalihan.py` (baru, 7), `backend/tests/test_bp_KMT1_target_bersamaan_mongo.py` (baru, lapis A U17) | |

## Uji penerimaan

"Merah lama": (a) = berkas uji dijalankan dengan semua berkas (a) dikembalikan ke `8c8d5ab` (`bukti/KM-T1/a_merah_kode_lama.txt`);
(b) = berkas uji (b) dijalankan dengan berkas (b) dikembalikan ke keadaan (a) (`bukti/KM-T1/b_merah_kode_a.txt`).

| ID | Lapis | Kode lama | Kode baru |
|---|---|---|---|
| U1 | B | merah: `ImportError incentive_facts` (fitur belum ada) | lulus — satu baris `kirim` S1 Okt: `net` 30.000.000, `list_value` 33.000.000, `cost` 18.000.000 (`global_value` 36.000.000) |
| U2 | B | merah (sama) | lulus — Nov `kirim` 20.000.000 + `retur` −5.000.000 = 15.000.000 |
| U3 | B | merah: 404 | lulus — Okt fakta = buku = 30.000.000; Nov 15.000.000; `ok`, tanpa penyebab |
| U4 | B | merah | lulus — R1 `kas` 20.000.000, R2 `kas` 10.000.000; Σ kas 30.000.000 |
| U5 | B | merah: 404 | lulus — 30.000.000 / 2.000.000 / 32.000.000 / 32.000.000, `ok` |
| U6 | B | merah | lulus — Nov `deposit` 2.000.000 + `hapus_sisa` 500.000; tidak ada baris kas |
| U7 | B | merah | lulus — Okt tetap +20.000.000; Nov pembalik −20.000.000 bertanggal 8 Nov; Okt & Nov `ok` |
| U8 | B | merah | lulus — S1 600.000,60, S2 400.000,40; Σ 1.000.001,00 |
| U9 | B | merah: `KeyError sales_attribution` (pesanan baru tanpa potret; tim pelanggan tetap S1) | lulus — sesudah serah-terima tim pelanggan PIC = S2; pesanan baru `sales_attribution` S2 100 %; pesanan lama tetap S1 |
| U10 | B | merah: `KeyError list_price` | lulus — `price` 48.000, `list_price` 55.000, `entity`, `global_price` 60.000; produk tanpa harga PT → 60.000 `global` |
| U11 | B | merah: 404 | lulus — dua dokumen (KSC, Kanda); GET tiap PT hanya miliknya; simpan ulang = satu dokumen; galat 400 pesan spesifikasi; "Semua PT" 409 |
| U12 | B | merah: 404 | lulus — GET triwulan 700.000.000 (bukan 600.000.000); batas 1 Jul–30 Sep; salin ke Q4 `{copied 1, skipped 0}` lalu `{0, 1}` |
| U13 | B | merah: `ImportError incentive_periods` | lulus — `2027-Q1` Kanda (tutup Maret) = 2026-04-01 s.d. 2026-06-30; KSC tetap kalender |
| U14 | B | merah: `POST /api/sales-targets` menyimpan di PT asal sales (KSC) padahal PT dibuka Kanda; **200 untuk "Sales Senior" sudah sejak PR-T4** (bukan 400) | lulus — PUT 200 (Kanda); POST lama 200 → dokumen Kanda `month`; per PT dua dokumen; periode `2026-Q4` 400; Semua PT 409 |
| U15 | B | merah: 400 "Sumber daya izin incentive tidak dikenal" | lulus — Tanpa Acuan `incentive.view` 200 di empat GET, PUT 403; Manajer Kosong & Sopir 403 bentuk Z6 ('Kinerja & Insentif', tanpa `x.y`) |
| U16 | B | merah: `KeyError Setting 'insentif.*'` | lulus — putaran `t1_config` empat kunci; nilai tak sah 400; versi definisi Kanda +1 sesudah nilai PT diubah, KSC tetap |
| U17 | A | — | **ditulis, belum teruji** — `backend/tests/test_bp_KMT1_target_bersamaan_mongo.py` (5 putaran dua PUT bersamaan → [200, 200], satu dokumen; indeks wajib terpasang) |
| U18 | B | merah | lulus — hapus 3 baris → `rebuild_diff` 3 baris kurang; bangun ulang lewat API → cocok, jumlah baris kembali; lapisan `incentive` penjaga data PASS; bukti-merah: hapus satu baris kas → INV-KM-2 & INV-KM-3 FAIL |
| (a) tambahan | B | merah | komponen per PT (409 kode kembar, PT lain boleh kode sama, PATCH PT lain 404), "Semua PT" hanya baca, tugas terjadwal & indeks wajib |
| (b) tambahan | B | merah | serah-terima ke sales PT lain 400; `build_rows` memakai potret (mode tim) dan bukan pada mode pemilik pelanggan; skrip migrasi target (baca-saja, `--apply`, ulang tanpa perubahan, kunci kembar → keluar 3 / H6); skrip harga pembanding (hanya `entity`/`global`, lainnya dilaporkan) |
| layar | jest | merah (komponen belum ada) | `kmt1TargetAturan` 7/7 — keterangan, kosong, berversi, status berikon, Simpan hanya baris diubah, Semua PT & tanpa izin beralasan. **Belum diuji jalan** di peramban |

### Contoh angka F1 — dokumen → fakta → mutasi akun (hitung tangan; dibuktikan U1–U7)

| Dokumen | Fakta | Jurnal (akun pendapatan PT Kanda = 4-1000) |
|---|---|---|
| SJ1 10 Okt 600 yd dari O1 (1.000 yd × 50.000) | `kirim` S1 `net` = 50.000.000 × 600/1.000 = **30.000.000**; `list_value` 30 jt × 55.000/50.000 = 33.000.000; `cost` 600 × 30.000 = 18.000.000 | `shipment_revenue` SJ1 2026-10-10: Dr 1-1200 30.000.000 / **Cr 4-1000 30.000.000** |
| SJ2 3 Nov 400 yd (pesanan `shipped` → penutup) | `kirim` = 50 jt − 30 jt = **20.000.000** | `shipment_revenue` SJ2 2026-11-03: Dr 1-1200 20.000.000 / **Cr 4-1000 20.000.000** |
| CN1 12 Nov retur 5.000.000 (HPP 3.000.000) | `retur` **−5.000.000**, `cost` −3.000.000 | `sales_return` 2026-11-12: **Dr 4-1000 5.000.000** / Cr 1-1200 5.000.000; Dr 1-1300 3.000.000 / Cr 5-1000 3.000.000 |
| Omzet Okt / Nov | 30.000.000 / 15.000.000 | mutasi 4-1000 Okt 30.000.000 / Nov 20 jt − 5 jt = 15.000.000 → INV-KM-1 cocok |
| R1 15 Okt transfer 20 jt; R2 20 Okt tunai 12 jt (O1 10 jt) | `kas` 20.000.000 + 10.000.000 = A 30.000.000 | kas masuk ber-`ref_type ar_receipt` 32.000.000 = D; kwitansi C 32.000.000; B (R2 belum dialokasikan) 2.000.000 → A + B = C = D |
| R1 dibatalkan 8 Nov | Okt tetap +20 jt; Nov pembalik −20 jt | kas R1 batal di Nov: D Nov = −20 jt; C Nov = 0 − 20 jt → A −20 jt + B 0 = C = D |

## Cek layar

Satu layar baru: **SDM › Kinerja & Insentif › Target & Aturan** (`IncentiveSetupView.jsx`); tab lama `incentive-rates`
hanya berganti label ("Komisi Otomatis"). Dari kode (integrator memotret 1280/1024/390 px):

| # | Butir | Target & Aturan |
|---|---|---|
| 1 | Tabel lebih lebar dari kartu | Tabel target 5 kolom (Sales min 150 px, dua isian angka 144 px, pelanggan baru 80 px, catatan min 160 px ≈ 760 px) dalam `overflow-x-auto`, `data-table head-wrap`, tanpa kolom aksi (Simpan di bilah atas). Tabel komponen 6 kolom, kolom aksi `col-sticky-end` |
| 2 | `section-card` tanpa bantalan | Semua kartu `section-head` + `section-body`; keadaan memuat/galat/kosong `section-pad` |
| 3 | Kepala kartu dijejali | Kepala hanya ikon + judul; tombol, pilihan periode, dan alasan di bilah sendiri di badan kartu |
| 4 | Tombol mati hanya tooltip | Alasan tertulis di samping: "Pilih satu PT untuk mengatur target." / "Mengatur target dan komponen butuh akses Konfigurasi…" / "Belum ada perubahan — ubah angka di tabel lalu Simpan."; komponen & bangun ulang punya alasan sendiri |
| 5 | Status hanya warna+teks | `status-pill` berikon: Cocok (centang) / Selisih Rp … (segitiga), Aktif / Nonaktif |
| 6 | Daftar tanpa cari | Tabel sales berkotak "Cari sales" + hitungan "n dari m sales · k bertarget"; daftar penyebab dibatasi 10 + "dan n lainnya" |
| 7 | Teks bertentangan dengan izin | Tidak ada "bukan wewenang"; teks menyebut akses Konfigurasi modul Kinerja & Insentif (izin baru) |
| 8 | Kosong ganda / angka 0 / grafik | Satu kalimat kosong per bagian; bulan tanpa angka → satu kalimat (bukan deretan Rp 0); tanpa grafik |

Angka rupiah berpemisah ribuan (isian juga), tanggal lewat `formatDate`, tanpa kode mentah (label jenis periode, periode
dasar, kolom, pilihan definisi dari server). Belum diuji jalan di peramban.

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di `976aaca` — satu gate untuk
PK-25, KM-T1 (a/b), PK-32 (a/b), perbaikan pop-up AG-T3 (`2f0fd32`), fixture lapis A PK-25 (`0616042`) dan cek layar
(`976aaca`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 14 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 2 (`config_wiring` + uji-diri) |
| `--ci` | 41 FAIL | 43 | 1 (ganti nama) | 2 |

`guard:detail_modal` (merah baru gate sebelumnya, milik AG-T3) kini hijau. Kuitansi: `bukti/KM-T1/gate_quick_receipt.md`,
`gate_ci_receipt.md`.

### Penggabungan integrator dan lingkungan A

- (a) `2ed5c53` dan (b) `b9753a3` dipasang di atas PK-25 (`06fe1b7`): bentrok `ENTITY_REGISTRY.md` (blok PK-25 lalu KM-T1)
  dan KN_32 (bagian KM-T1 menjadi **§9.14**; §9.13 = PK-25) — kedua sisi dipertahankan; `indexes.py`, `verify_contract.py`
  tergabung tanpa bentrok; `configKeyIndex.json` selaras. Ujung rantai (`7c13605`, + PK-32): tests_mem **1827 / 2 / 3**,
  jest **928**, penjaga statik identik garis dasar, `verify_config_fallback` 156/0 (+`--entity`).
- `restore_demo` dengan kode baru → `scripts/check_required_indexes.py`: **26 dari 26** indeks wajib beres
  (`uq_target_pt_sales_periode`, `uq_component_code`, `uq_definition_version` terpasang, 0 kelompok kembar). Lapis A
  `test_bp_PK14_indeks_wajib.py` **9 lulus**; **U17** `test_bp_KMT1_target_bersamaan_mongo.py` **2 lulus**.
- Fakta dibangun ulang di data acuan (`POST /api/incentive/facts/rebuild`: KSC 6 baris kirim · 12 baris pencairan; Kanda
  0) → `verify_data_integrity.py --only incentive`: INV-KM-1 **PASS** (omzet = buku besar Rp 1.200.000), INV-KM-3 **PASS**;
  INV-KM-2 **FAIL** Δ Rp 5.961.000 — **seluruh 6 penyebab = kwitansi fixture lapis A PK-25** (`KW-BP25-*`, disisipkan uji
  langsung ke database tanpa kas); data acuan sendiri cocok (`bukti/KM-T1/integritas_incentive_data_acuan.txt`). Penjaga
  bekerja sebagaimana mestinya (menunjuk kwitansinya).
- Cek layar 1024 px Target & Aturan (`bukti/KM-T1/cek_target_aturan_1024.png`): `overflowX = 0`; tabel target muat (judul
  "Target pelanggan baru" dua baris), Simpan mati dengan alasan tertulis, pencocokan dengan pil ikon + teks + warna dan
  daftar penyebab. Tidak ada cacat yang perlu diperbaiki.

Pelaksana — lingkungan B:

- `tests_mem` W (basis `8c8d5ab`): B **1714 / 2 / 3** (angka sesi) → (a) putaran pertama **1734 lulus + 5 merah** (uji hitungan
  lama yang memang harus disesuaikan: KF-T1 U04/U14, PR-T9 U01, KF-T4 indeks kunci, PK-14 U12 — disesuaikan, lalu 72/72
  berkas terkait hijau; `bukti/KM-T1/a_tests_mem_W_putaran1.txt`) → (b) **1746 / 2 / 3** (= 1714 + 21 (a) + 4 putaran
  KF-T8 kunci baru + 7 (b); `b_tests_mem_W.txt`).
- Jest W (a): 887 lulus + 3 merah (`roleReach` — layar tujuan baru `incentive-setup` belum tercatat; dicatat di
  `ROLE_REACH_ADDITIONS`), sesudahnya hijau; uji baru `kmt1TargetAturan` 7/7; 35 suite gagal dimuat (`cmdk`/`@radix-ui`).
- `hitung_penjaga.sh`: **identik** B → (a) → (b) → T (auth 27 · ui_standard 13 · i18n 103 · create_modal 6 · page_tabs 1 ·
  to_list 6 · entity_label 2, lainnya 0/PASS; `penjaga_{B,W_a,W_b,T}.txt`).
- Sapuan izin (`tests_mem/sapuan_izin.py`, mode cepat): B 1.810 rute / 20 pelanggaran → W (a) 1.819 rute / **20 pelanggaran
  yang sama** (daftar identik; tidak ada `/api/incentive/*`; `sapuan_izin_{B,W_a}.txt`).
- `tests/test_fe03_access_catalog.py --noconftest` 6/6 (W dan T).
- Lapis A (U17, `test_bp_PK14_indeks_wajib` 26) dan gate `scripts/gate.sh` belum dijalankan.

## Penggabungan

- HEAD tujuan: **`0562d29`** (selama unit dikerjakan HEAD maju `8c8d5ab` → `cc33293` → `3998cb4` (AG-T3) → `d07186e`
  (PK-43) → `0562d29` (hanya `docs/blueprint/STATUS.md`)). Worktree tujuan `wt33` berisi (b) tergabung, belum di-commit.
- Cara: 48 berkas unit (di luar laporan/bukti); berkas yang sama di HEAD dan B disalin; berkas baru disalin; sisanya
  `git merge-file` tiga arah (`bukti/KM-T1/gabung_b.log`). **Tanpa bentrok:** `access_modules.py`, `permissions_config.py`,
  `routers/crm.py`, `server.py`, `scheduler_service.py`, `test_PRT9_izin_bawaan.py`, `AppViewRouter.jsx`, `memory/PRD.md`,
  `configKeyIndex.json`, `access_builtin_fixture.json`. **Bentrok** (tambahan berdampingan; KEDUA sisi dipertahankan):
  `ENTITY_REGISTRY.md` (baris AG-T3 tabel ringkas + baris KM-T1), `backend/indexes.py` (blok indeks wajib AG-T3
  `uq_pending_session` lalu blok KM-T1), `test_KFT1_izin_pengaturan.py` (`AGT3_KUNCI` dan `KMT1_KUNCI`; U04 `… + AGT3_KUNCI +
  KMT1_KUNCI`), `test_PK14_indeks_wajib.py` (`AGT3_INDEKS` + `KMT1_INDEKS`), `tests/test_bp_PK14_indeks_wajib.py` (23 + 3 =
  **26**), `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (§9.12 PK-43 tetap; bagian KM-T1 menjadi **§9.13**). Dibangkitkan ulang
  di T: `CODEBASE_MAP.md`, `configKeyIndex.json`, `access_builtin_fixture.json`/`access_nav_fixture.json`.
- Keadaan **(a)**: basis `$S/KM-T1_a_state/` (`BASIS.txt` = `8c8d5ab`, 41 berkas); tergabung `$S/KM-T1_a_merged/`
  (`BASIS.txt` = `0562d29`; digabung di `d07186e` — `0562d29` hanya mengubah `STATUS.md` — dengan bentrok dan penyelesaian
  yang sama seperti di atas, peta kode/indeks kunci/fixture dibangkitkan pada pohon (a)). `tests_mem` penuh (a) tergabung di
  `3998cb4`: **1770 / 2 / 3** (= HEAD 1745 + 25); di `d07186e` berkas terkait (KM-T1 (a), PR-T9, KF-T1, KF-T4, PK-14, MN-T1,
  KF-T8) **540 lulus / 2 xfail**, jest terkait 85/85 (`a_tergabung_*`).
- Angka di T (`0562d29` + KM-T1 (a)+(b)): `tests_mem` **1795 / 2 dilewati / 3 xfail** (HEAD = 1795 − 32 = 1763: 21 (a) + 4
  putaran KF-T8 + 7 (b); tanpa merah; `T_tests_mem.txt`); jest HEAD (`d07186e`) 147 suite · **912** → T 148 · **919** (+7;
  35 suite gagal dimuat sama); `hitung_penjaga.sh` T = garis dasar; `verify_role_gate_ui` 31/0; `verify_config_fallback`
  156/0 (`--entity` 156/0); `verify_payment_vocab` 1805/0; `verify_access_catalog_nav` 0; `verify_permission_checked`
  606/0; `verify_posting_coverage` 138/0; `verify_cash_single_door` 724/0; `verify_config_text` 3255/0;
  `verify_codebase_map` 0; `verify_contract --all` OK; `audit_config_wiring --strict` hijau dan `check_nav_map` PASS
  (keduanya lewat salinan berjalur T).
- Seed data uji (`seed_realistic.py` akar repo dan `backend/seed_realistic.py`): unit ini tidak menambah isian wajib dokumen
  yang di-seed dan tidak menghapus/mengganti nama fungsi (target seed sudah berbentuk kunci baru: `entity_id` + `period_type
  "month"`); keduanya tidak diubah (dicek `grep`).

## Menyimpang dari blueprint

1. **`services/incentive_targets.py`** (berkas tambahan): target, komponen, dan `sales_roster` di satu layanan (dipakai router
   baru, jalur lama `POST /api/sales-targets`, dan serah-terima pelanggan).
2. **INV-KM-2 B dan aturan batal**: B = kas kwitansi belum dialokasikan memakai `allocations[].parts` (kas lebih dulu,
   PK-19) bila ada; rumus spesifikasi `amount − (applied_total − min(used_deposit, applied_total))` (deposit lebih dulu)
   hanya untuk kwitansi lama tanpa `parts` — dengan rumus spesifikasi, kwitansi PK-19 yang memakai deposit sambil
   menyisakan kas akan selalu tampak berselisih. B juga mengikuti "aturan batal sama" (kwitansi batal di bulan itu
   mengurangi B) — tanpa itu bulan batal kwitansi berkelebihan bayar selalu berselisih sebesar kelebihannya.
3. **Tanggal fakta retur/koreksi** = aturan tanggal jurnalnya (`approved_at` retur; `created_at` nota untuk per roll dan
   amandemen), supaya INV-KM-1 membandingkan bulan yang sama. Pesanan ber-jurnal per pesanan lama memakai tanggal jurnal itu
   (jalur `pesanan_lama`), walau punya surat jalan.
4. **`sales_roster`** juga memuat peran berkategori kerja sales (PR-T4) selain peran/peran acuan `sales` — serah-terima
   pelanggan dulu menerima kategori itu; tanpa ini akses yang sudah jalan menyempit. Serah-terima kini hanya ke sales yang
   ditugaskan di PT pelanggan (pelanggan tanpa PT: akun sales aktif mana pun).
5. **Tab lama `incentive-rates`** berganti label "Komisi Otomatis" (dua tab berlabel sama tidak boleh); grup SDM dan menu
   Kinerja & Insentif kini juga untuk Finance (pemegang `incentive.view` bawaan) — Finance hanya melihat tab Target &
   Aturan.
6. **Modul `incentive` memuat `settings-hub`/`settings-sales`/`settings-cfg-sales`** dan `settings-cfg-sales` bersumber izin
   `incentive` (aturan KF-T1 U14: tab kelompok terbuka bagi pemegang izin pengubah kuncinya).
7. **Teks bantuan `insentif.isi_pencairan`** memakai label pilihan, bukan kode (`uang_masuk`) — penjaga teks pengaturan &
   L1. Contoh `insentif.dasar_omzet` sama.
8. **`incentive_definitions`** dicatat saat dibaca (`current_definition`) dan oleh tugas sinkron 5 menit untuk tiap PT, jadi
   `effective_from` = tanggal perubahan terbaca, bukan detik perubahan disimpan.
9. Endpoint rekonsiliasi & definisi dalam mode "Semua PT" menjawab `{all_pt: true}` (layar meminta satu PT), bukan 409.

## Asumsi

- `ASUMSI:` (spesifikasi) kontrak PK-19 apa adanya (`kind`, `payment_kind`, `reverses`); tidak ada penyimpangan PK-19 yang
  mengubah pembaca (lihat laporan PK-19: `credit_note_void` → `nota_kredit`, `bank_charge`/`titipan_karyawan` → `kasus`).
- `ASUMSI:` (spesifikasi) giro dihitung pada tanggal kwitansi, `giro_uncleared` (kode giro dari benih cara bayar PM-T1).
- `ASUMSI:` (spesifikasi) `kasus` dan `saldo_kredit` bukan uang masuk; pesanan sample ikut fakta; hanya anggota `pic`
  yang diganti saat serah-terima (pendamping tetap; bila sales tujuan sudah pendamping, porsinya digabung ke PIC).
- `ASUMSI:` batas bawah pembanding (`floor_price`) dihitung `floor_for` dengan pengaturan penjagaan harga PT (basis &
  toleransi) walau penjagaan dimatikan; kosong bila tidak ada batas.
- `ASUMSI:` nota kredit batal item pesanan khusus ikut `koreksi` hanya bila berjurnal (`issued` + `revenue_recognized`).

## Hambatan lingkungan

- Lapis A (U17) dan uji jalan peramban tidak dijalankan pelaksana. `audit_config_wiring` membaca database `backend/.env`
  (baca-saja): di W (basis B) satu kunci `ai.tindakan_uang_masuk` lapisan `ent_ksc` tampil DEAD karena kunci AG-T3 belum
  ada di basis B — di T (HEAD dengan AG-T3) hijau.
- Jest: 35 suite gagal dimuat (`cmdk`/`@radix-ui`), sama dengan HEAD.

## Yang perlu direview

- INV-KM-1/INV-KM-2 di data acuan (lingkungan A): `python scripts/verify_data_integrity.py --only incentive` sesudah
  bangun ulang fakta (`POST /api/incentive/facts/rebuild` per PT atau tugas `incentive_fact_nightly`). Data acuan lama dapat
  berselisih karena pesanan seed berjurnal per pesanan dengan surat jalan, atau baris `payments[]` seed tanpa kwitansi —
  daftar penyebab menyebutnya.
- Skrip `migrate_sales_targets_km_t1.py` di data nyata (H3) sebelum indeks `uq_target_pt_sales_periode` diandalkan; kunci
  kembar = H6.
- Butir lama yang tetap jalan sampai KM-T5: KPI/komisi `sales_force_service` masih menjumlah semua baris pembayaran dan
  target bulanan; layar lama "Set Target" & "Skema (Arsip)".

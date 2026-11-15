# KM-T2 — Bangun layar Capaian: cari, telusur, dan jumlahkan angka dasar insentif per sales

- Commit awal: `5f193df` (worktree kerja, basis B)        - Commit akhir: `4b219c4`        - Branch: `claude/nifty-carson-jjx3c8`
- Digabung pelaksana ke HEAD `38c715f` (sesudah PY-T2, TX-T2, AG-T5, CR-T2, PM-T4) — lihat "Penggabungan"
- ID ditangani: — (unit fitur; spesifikasi `docs/blueprint/unit/KM-T2.md`; keputusan K-19, K-20, K-21, K-23, K-24)
- Risiko sedang → satu serah-terima. Layar hanya membaca: tidak ada koleksi, kunci pengaturan, atau tulisan baru.

## Cek ulang "Keadaan sekarang" (spesifikasi `3132cc4`, diperiksa di `5f193df`)

| Butir | Hasil di basis B |
|---|---|
| Layar satu sales per tampilan, `sf-kpi-sales` `SalesForceDashboard.jsx:116`; papan peringkat lima kolom tanpa target `:182`; tanpa telusur ke dokumen | Berlaku, bergeser — `:122` (`sf-kpi-sales`), kepala papan `:188` (`Pencairan`); tidak ada angka yang bisa dibuka ke dokumen. Layar lama tidak disentuh (KM-T5) |
| Wewenang lewat nama peran `SalesForceDashboard.jsx:16` (`roleIs`), server `crm.py:254` (`role_in`), `:268` (`require_role`) | **Tidak berlaku** — layar memakai `can(perms, "sales_force", …)` / `can(perms, "order", "view_sales_kpi")` (`:18–22`); server `_kpi_scope` memakai `has_permission(actor, "order", "view_sales_kpi")` (`crm.py:301`, `:326`) sejak PR-T2/PR-T4. Kode baru unit ini juga hanya memakai izin |
| Papan peringkat hanya peran persis `sales` `sales_force_service.py:456` | Sebagian — `leaderboard` `:458` kini `roles_in_category("sales")` (PR-T4). Capaian memakai `incentive_targets.sales_roster` (peran/peran acuan/kategori kerja sales + siapa pun yang punya fakta/target) — U15 |
| Piutang per pelanggan milik sales per tanggal `ar_aging_service.py:177` (`aging_report`) | Berlaku, bergeser `:269`; sejak PK-41 per surat jalan dan `as_of` = posisi tanggal itu (dipakai apa adanya) |
| Endpoint baca dokumen: surat jalan `outbound_picking_extra.py:30`, kwitansi `ar_receipts.py:134`, pesanan `sales_orders.py:726` | Berlaku, bergeser — `:30`, `:157`, `:809`. Tautan dokumen di panel telusur memakai pembentuk tautan tunggal `doc_refs_service.link_of` (PK-44): surat jalan dibuka lewat pesanannya, kwitansi di Penagihan & Penerimaan, nota kredit di Koreksi & Amandemen |
| Pola ekspor Excel `finance_analytics.py:57` (`Workbook`), `:66` (`_cell`) | Berlaku, bergeser — `:59`, `:69`. `_cell` fungsi bersarang (tidak bisa diimpor) → aturan yang sama (KN-E32) ditulis sebagai `incentive_achievement._cell` |
| Hub tujuan satu tab `hubTabs.js:202` (`hr-kpi-hub`); menu berlabel "KPI" `navStructure.js:361` | **Tidak berlaku** — MN-T1/KM-T1: hub `:213` sudah 5 tab (Kinerja Sales, Target & Aturan, Komisi Otomatis, Skema (Arsip), KPI Karyawan); menu `:338` berlabel "Kinerja & Insentif". Capaian = tab ke-6 (batas L3 enam tab), urutan pertama |
| Disediakan KM-T1: `fact_shipment_sales`, `fact_collections`, `sales_targets` berkunci PT, `current_definition`, `period_bounds`, `sales_roster`, `ensure_fresh`, rekonsiliasi | Ada semua (`services/incentive_*`); dipakai tanpa diubah |

## KM-T2 — Layar Capaian

- Berlaku di HEAD: fitur baru (endpoint `/api/incentive/achievement*` 404 di B — `bukti/KM-T2/merah_kode_lama.txt`).
- Perubahan perilaku (sebelum → sesudah):
  - **Server** `services/incentive_achievement.py` (baru, hanya membaca) + tiga endpoint di `routers/incentive.py`, semua
    `incentive.view` (Z1: pernyataan pertama `_capaian_ctx` = `require_permission`), PT dari konteks, "Semua PT" → 400
    "Pilih satu PT untuk melihat Capaian. Definisi angka berbeda di tiap PT.", `ensure_fresh(60)` sebelum membaca (dan
    `analytics_facts.ensure_fresh` bila dasar omzet `pesanan`/`lunas`):
    - `GET /api/incentive/achievement` — periode `month`/`quarter`/`year` (batas tahun buku PT, K-24) atau `range`
      (≤ 366 hari), `compare` `none`/`prev`/`yoy`, `cumulative` (bulan: awal tahun buku s.d. akhir bulan; target = Σ target
      bulanan dalam rentang), `group_by` `sales`/`customer`/`category`/`price_source`, saringan `sales_id[]`, `customer_id`,
      `category`, `line_code`, `price_source`. Baris per sales dari `sales_roster` (+ "Tanpa sales" bila ada angkanya):
      target, omzet menurut `insentif.dasar_omzet`, retur (+ koreksi), omzet bersih, % capaian, uang masuk menurut
      `insentif.isi_pencairan`, % capaian, sisa piutang & lewat tempo (`aging_report` per akhir periode), realisasi harga,
      rata-rata potongan, di bawah harga acuan (menurut `insentif.harga_acuan`), margin (**hanya pemegang
      `incentive.view_margin`**), pelanggan baru, pesanan, catatan data. `pemilik_pelanggan` → dikelompokkan menurut
      `customers.assigned_sales_id` saat ini. Uang dalam sen bulat, dibulatkan sekali ke rupiah (`_rp`); `totals` = Σ baris
      (D5). `reconciliation` = INV-KM-1/2 KM-T1 untuk tiap bulan yang tersentuh periode.
    - `GET …/achievement/sources` — dokumen di balik satu sel (`metric` omzet · retur · uang_masuk; `sales_id`, `""` =
      tanpa sales), berhalaman (`page_size` ≤ 200), `sum` = angka sel (D4); `doc_type` shipment · credit_note · ar_receipt ·
      sales_order + `link` (L8).
    - `GET …/achievement/export` — `capaian-<kode PT>-<periode>.xlsx`, lembar **Definisi** (PT, periode & rentang, versi &
      tanggal berlaku, empat definisi berlabel + keterangan, hasil pencocokan, waktu ekspor WIB, nama pengekspor),
      **Capaian** (kolom & urutan = layar; margin hanya `view_margin`), **Dokumen** (omzet, retur, uang masuk); sel teks
      lewat `_cell`.
  - **Izin** `incentive.view_margin` ("Lihat margin") → Admin, Manajer (`permissions_config.KMT2_DEFAULT_PAIRS`); masuk
    kelompok peka "melihat HPP dan margin" di editor peran. Modul akses `incentive`: `nav` + `incentive-capaian`.
  - **Layar** SDM › Kinerja & Insentif › **Capaian** (tab pertama; `CapaianView.jsx`, `CapaianSourcesPanel.jsx`): banner
    PT; saringan Periode (Bulan · Triwulan · Tahun · Rentang tanggal) + nilainya, Bandingkan dengan, Kelompokkan menurut,
    Kolom, kotak "Cari nama…", sakelar "Kumulatif tahun berjalan" dan "Hanya yang ada angkanya", tombol "Simpan
    tampilan" (peramban, `kn.capaian.tampilan.<id pengguna>`) dan "Ekspor Excel"; baris definisi "Omzet: … · Pencairan: …
    · Milik: … · Harga acuan: … — berlaku sejak … (versi n)"; peringatan pencocokan; tabel berkelompok Omzet · Pencairan ·
    Kualitas harga · Lain dengan judul persis spesifikasi dan keterangan definisi saat disorot; selisih pembanding di bawah
    omzet bersih & uang masuk ("+Rp 480.000.000 dari Sep 2026"); klik Omzet/Retur/Uang masuk → panel telusur "{kolom} —
    {sales} — {periode}" (kotak centang, "Jumlah Rp … dari {n} dokumen", nomor membuka dokumen); bilah jumlah pilihan
    (dihitung di layar); memuat "Memuat capaian…", galat `ErrorNotice` "Capaian gagal dimuat.", kosong "Belum ada penjualan
    atau uang masuk pada periode ini.", kaki "Data per pukul HH:MM WIB". Tidak ada tombol tulis.
- Fixture disiapkan langsung vs proses bisnis dijalankan: F2 = fixture (pesanan, surat jalan, retur & nota kredit) + jurnal
  oleh fungsi posting asli (`post_order_revenue_and_cogs`, `post_sales_return`) + kwitansi lewat `create_receipt` asli +
  target lewat `save_target` + fakta lewat `rebuild`; layar & izin lewat API (`/api/incentive/achievement*`,
  `/api/access/roles`).
- Dampak pada modul terkait: tab pertama hub Kinerja & Insentif berganti (admin & manajer kini mendarat di Capaian;
  `ROLE_REACH_RELANDED`); peran beracuan Manajer/Admin menerima `incentive.view_margin` lewat sinkron izin bawaan (PR-T9).
  Jalur lama (Kinerja Sales, `/api/sales/kpi`) tidak disentuh (KM-T5).
- Status: implemented_pending_review

## Berkas

| Berkas | Isi |
|---|---|
| `backend/services/incentive_achievement.py` (baru) | Periode/pembanding, pengumpul fakta tunggal, baris & total, telusur, definisi & keterangan kolom, pencocokan per bulan, ekspor `.xlsx` |
| `backend/routers/incentive.py` | `GET /achievement`, `/achievement/sources`, `/achievement/export`; pesan Z6 "melihat capaian insentif" |
| `backend/permissions_config.py`, `backend/access_modules.py` | `KMT2_DEFAULT_PAIRS`; nav `incentive-capaian`; label "Lihat margin"; kelompok peka |
| `frontend/src/features/incentive/CapaianView.jsx`, `CapaianSourcesPanel.jsx` (baru) | Layar & panel telusur |
| `frontend/src/AppViewRouter.jsx`, `appViewImports.js`, `config/hubTabs.js`, `config/navMeta.js` | Tab Capaian (urutan pertama, admin · manajer · Finance) |
| `frontend/src/config/__tests__/fixtures/access_nav_fixture.json`, `access_builtin_fixture.json` (dibangkitkan `tests/fe03_access_fixture.py`), `view_main_permission.json` (+ baris `incentive-capaian`) | Tabel bantu |
| Uji baru | `backend/tests_mem/test_KMT2_capaian.py` (18), `frontend/src/features/__tests__/kmt2Capaian.test.js` (10) |
| Uji lama disesuaikan | `tests_mem/test_PRT9_izin_bawaan.py` (`KMT2_DEFAULT_PAIRS`), `config/__tests__/mnt1MenuKeuangan.test.js` (hub 6 tab, label, urutan), `roleReach.test.js` (`KMT2_CAPAIAN`, `ROLE_REACH_RELANDED` hr-kpi-hub → `incentive-capaian`), `serverAccessReach.test.js` (`RELANDED`) |
| Dokumen | `CODEBASE_MAP.md` (dibangkitkan), `memory/PRD.md`, `docs/KN_13_NAVIGATION_MAP.md` (tab Capaian; baris Target & Aturan/Komisi Otomatis yang basi sejak KM-T1 dibetulkan), `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.18 di W / §9.23 di T (capaian, omzet bersih, realisasi harga, …), `ENTITY_REGISTRY.md` (baris Meja Insentif: endpoint & layar KM-T2) |

## Uji penerimaan

"Merah lama" = berkas uji dijalankan di kode B (`incentive_achievement.py` disingkirkan; router/izin lama) —
`bukti/KM-T2/merah_kode_lama.txt` (18/18 gagal: 404 Not Found / `view_margin` tidak ada); jest
`bukti/KM-T2/jest_merah_kode_lama.txt` (suite gagal: `Cannot find module '../incentive/CapaianView'`).

| ID | Lapis | Kode lama | Kode baru |
|---|---|---|---|
| U1 | B | merah: 404 | lulus — Andi Okt: target 800.000.000, omzet 1.000.000.000, retur 0, % 125,0; uang masuk 700.000.000, % 93,3; + sisa piutang 600.000.000 / lewat tempo 300.000.000 per 31 Okt; pencocokan cocok (selisih 0); total = Σ baris |
| U2 | B | merah: 404 | lulus — realisasi 86,2; potongan 13,8; di bawah acuan 100,0; margin 30,0 |
| U3 | B | merah: 404 | lulus — Budi: omzet 500.000.000, % 100,0; uang masuk 520.000.000, % 115,6; realisasi 100,0; di bawah 0,0; (+ pelanggan baru 1, pesanan 1) |
| U4 | B | merah: 404 | lulus — Q3 Andi: target 2.400.000.000; omzet 2.600.000.000, % 108,3; uang masuk 2.300.000.000, % 102,2; realisasi 88,0; batas 1 Jul–30 Sep |
| U5 | B | merah: 404 | lulus — `total` 2, `sum` 520.000.000 = sel U3; RB1 & RB0 `ar_receipt` bertautan; halaman 2 × 1 baris tetap `total` 2 |
| U6 | B | merah: 404 | lulus — satu `shipment` Rp 1.000.000.000 (SJ OA1, 12 Okt), tautan ke pesanan OA1; `metric` tak dikenal → 400 |
| U7 | B | merah: 404 | lulus — `compare.by_key[Budi].omzet_bersih` 20.000.000, label "Sep 2026"; `yoy` → Okt 2025 |
| U8 | B | merah: 404 | lulus — dasar `pesanan`: Andi Okt 0, Sep 1.000.000.000; versi definisi +1; telusur Sep = pesanan OA1 |
| U9 | B | merah: 404 | lulus — retur 50.000.000, omzet bersih 950.000.000, % 118,8; pencocokan omzet tetap cocok; telusur retur = nota kredit |
| U10 | B | merah: 404 | lulus — kumulatif: omzet 3.600.000.000, target 800.000.000, rentang 1 Jan–31 Okt; kumulatif triwulan → 400 |
| U11 | B | merah: 404 | lulus — Tanpa Acuan `incentive.view` saja: 200, tidak ada `margin_pct` di baris & total; ekspor tanpa kolom Margin |
| U12 | B | merah: 404 (bukan 403) | lulus — Manajer Kosong & Sopir: 403 di tiga endpoint, bentuk Z6 ("… 'Kinerja & Insentif'", tanpa `x.y`) |
| U13 | B | merah: 404 | lulus — "Semua PT" 400 (pesan spesifikasi) di tabel & ekspor; periode salah jenis 400; rentang 370 hari 400; rentang 1–31 Okt 200 (target = bulan penuh) |
| U14 | B | merah: 404 | lulus — lembar "Definisi", "Capaian", "Dokumen"; sel omzet Andi 1000000000; Definisi memuat "terkirim" dan nomor versi; Dokumen memuat SJ & nota kredit; nama berkas `capaian-<kode>-2026-10.xlsx`; ekspor dengan cari "budi" hanya baris Budi |
| U15 | B | merah: 404 | lulus — akun berperan kustom beracuan `sales` dengan satu pesanan terkirim muncul (omzet 5.000.000); akun kedua tanpa angka tetap terdaftar |
| pelengkap | B | merah | lulus — kelompok pelanggan (tanpa target/piutang/pelanggan baru), sumber harga ("Harga PT" 1.505.000.000; uang masuk kosong + catatan), saringan `sales_id[]`; pemilik pelanggan (OB0 pindah ke Andi); izin bawaan & katalog |
| U16 | jest | merah (komponen belum ada) | lulus — bilah "2 baris dipilih · Omzet bersih: jumlah Rp 1.500.000.000 · rata-rata Rp 750.000.000 · Uang masuk: jumlah Rp 1.220.000.000 · rata-rata Rp 610.000.000", jumlah panggilan jaringan tetap |
| U17 | uji jalan | — | **belum dijalankan** (integrator, peramban 1280/1024/390). Pengganti di jest: klik uang masuk Budi → panel dua kwitansi "Jumlah Rp 520.000.000 dari 2 dokumen"; klik RB0 → `openDocument` kwitansi |

### Contoh angka F2 — dokumen → fakta → angka layar (hitung tangan; dibuktikan U1–U10)

| Dokumen | Fakta (KM-T1) | Capaian |
|---|---|---|
| OA0 Andi 52.000 yd × 50.000, list 56.800, SJ 14 Agu | `kirim` 2.600.000.000; `list_value` 2.600 jt × 56.800/50.000 = 2.953.600.000; `cost` 52.000 × 35.000 = 1.820.000.000 | Q3: omzet 2.600 jt ÷ target 2.400 jt = 108,3 %; realisasi 2.600 ÷ 2.953,6 = 88,0 % |
| OA1 Andi 20.000 yd, list 58.000, dibuat 28 Sep, SJ 12 Okt | `kirim` 1.000.000.000; `list_value` 1.160.000.000; `cost` 700.000.000 | Okt: 1.000 ÷ 800 = 125,0 %; realisasi 1.000 ÷ 1.160 = 86,2 %; potongan 13,8 %; di bawah acuan 100 %; margin (1.000 − 700) ÷ 1.000 = 30,0 % |
| OB0 Budi 400 yd SJ 20 Sep · OB1 Budi 10.000 yd SJ 9 Okt | `kirim` 20.000.000 (Sep) · 500.000.000 (Okt), acuan = harga | Budi Okt 500 ÷ 500 = 100,0 %; realisasi 100 %, di bawah 0 %; pembanding Sep 20 jt |
| RA0 10 Sep 2.300 jt → OA0 · RA1 20 Okt 700 jt → OA1 · RB1 15 Okt 500 jt → OB1 · RB0 16 Okt 20 jt → OB0 | `kas` per kwitansi pada tanggal kwitansi | Andi Okt 700 ÷ 750 = 93,3 %; Q3 2.300 ÷ 2.250 = 102,2 %; Budi Okt 520 ÷ 450 = 115,6 % |
| CN retur 25 Okt Rp 50 jt atas OA1 (HPP 35 jt) | `retur` −50.000.000 | Andi Okt omzet bersih 950 jt ÷ 800 jt = 118,75 → 118,8 % |
| Piutang per 31 Okt (NET30, per surat jalan, PK-41) | — | Andi: OA0 2.600 − 2.300 = 300 jt jatuh tempo 13 Sep (lewat) + OA1 1.000 − 700 = 300 jt jatuh tempo 11 Nov → sisa 600 jt, lewat tempo 300 jt |
| Kumulatif Okt | Agu 2.600 jt + Okt 1.000 jt | 3.600 jt; target = Σ target bulanan Jan–Okt = 800 jt (Q3 bukan target bulanan) |

## Cek layar

Layar baru **SDM › Kinerja & Insentif › Capaian** (`CapaianView.jsx`) dan panel telusur (`CapaianSourcesPanel.jsx`).
Dari kode (integrator memotret 1280/1024/390 px). Kartu di 1024 px ≈ 750 px (sidebar 220 px).

| # | Butir | Capaian (tabel) | Panel telusur |
|---|---|---|---|
| 1 | Tabel lebih lebar dari kartu | 17 kolom angka tidak muat di 1024 px, jadi kolom dipilih per kelompok ("Kolom": **Ringkas** (bawaan: Omzet, % capaian, Omzet bersih, Uang masuk, % capaian, Realisasi harga ≈ 720 px) · Omzet (5 kolom ≈ 690 px) · Pencairan (5 ≈ 690 px) · Kualitas harga (3–4 ≈ 540 px) · Lain (3 ≈ 550 px) · Semua kolom). Angka uang tanpa "Rp" (keterangan "angka uang dalam rupiah" di atas tabel); `data-table head-wrap` (judul dua baris); tidak ada kolom aksi (telusur lewat angka). "Semua kolom" bergulir di wadahnya (`overflow-x-auto`) dengan kolom nama menempel di kiri + keterangan "geser tabel ke samping" | Pop-up `DetailModal` lebar `max-w-4xl`; 7 kolom (centang, Tanggal, Dokumen, Pelanggan, Pesanan, Jenis, Nilai) `head-wrap`, nama/pelanggan boleh turun baris; tanpa kolom aksi (nomor = tautan) |
| 2 | `section-card` tanpa bantalan | `section-head` + `section-body`; memuat/galat/kosong/"Semua PT" `section-pad` | Kartu `section-card` dengan `section-head`; isi `section-pad` |
| 3 | Kepala kartu dijejali | Kepala hanya ikon + "Capaian"; saringan, tombol, definisi, peringatan di badan kartu (bilah sendiri) | Kepala = judul "{kolom} — {sales} — {periode}" + tombol × |
| 4 | Tombol mati hanya tooltip | "Kumulatif tahun berjalan" mati → "Kumulatif hanya untuk periode Bulan." tertulis; "Ekspor Excel" mati → "Ekspor menunggu capaian termuat."; rentang belum lengkap → kalimat di badan | Tidak ada tombol mati (pager berlabel) |
| 5 | Status hanya warna+teks | Peringatan pencocokan `notice-bar warning` + ikon segitiga + teks; catatan data berikon di bawah nama | — |
| 6 | Daftar tanpa cari | Kotak "Cari nama…", sakelar "Hanya yang ada angkanya", hitungan "n dari m sales · k tanpa angka disembunyikan" | Berhalaman 50 (KNPager) + "Jumlah Rp … dari {n} dokumen" |
| 7 | Teks bertentangan dengan izin | Tidak ada "bukan wewenang"; tidak ada tombol tulis; kolom margin hanya tampil bila server mengirimnya (izin `incentive.view_margin`) | — |
| 8 | Kosong ganda / angka 0 / grafik | Satu kalimat kosong; baris tanpa angka disembunyikan bawaan; nol tampil redup, target 0 "—", persen kosong "—"; tanpa grafik | Satu kalimat "Tidak ada dokumen untuk angka ini." |

Tombol `btn-sm` + `whitespace-nowrap`; persen satu desimal berkoma ("86,2 %"); rupiah berpemisah ribuan; tanggal
`formatDate`; tanpa kode mentah (nama kelompok, jenis dokumen `source_label`, sumber harga berlabel dari server). Bilah
jumlah pilihan menempel di bawah (`sticky bottom-3`). Belum diuji jalan di peramban.

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`649b7dc`** — satu gate
untuk KM-T2 (`4b219c4`) dan PY-T3 ((a) `9794ec7` · (b) `649b7dc`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`38c715f`: 12 / 39) — tidak ada gate baru yang merah. Kuitansi: `bukti/KM-T2/gate_quick_receipt.md`,
`gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- Pelaksana menggabung ke `38c715f` (T); integrator meng-commit T apa adanya (`c6010a9`) lalu memetiknya ke cabang di atas
  penutupan gelombang 4 → **`4b219c4`** (pohon sama). `tests_mem` di T 2063/2/2 (pelaksana); rantai KM-T2 + PY-T3 (b)
  **2101/2/2** (integrator). Glosarium KN_32 §9.23.
- Uji jalan **U17** (integrator; data acuan sesudah `restore_demo`, peramban zona Asia/Jakarta): SDM › Kinerja & Insentif ›
  **Capaian** (tab pertama dari enam) — saringan Periode/Bulan/Bandingkan/Kelompokkan/Kolom (bawaan Ringkas), cari nama,
  "Kumulatif tahun berjalan", "Hanya yang ada angkanya", Simpan tampilan, Ekspor Excel; tabel bertingkat (Omzet ·
  Pencairan · Kualitas harga) = **lebar kartu** di 1280 (1018 px) dan 1024 (762 px), `overflowX` 0; baris Total; data acuan
  November berangka 0 (belum ada pengiriman bulan ini) — angka contoh spesifikasi dibuktikan di uji B U1–U15
  (`bukti/KM-T2/cek_capaian_*.png`). Tidak ada cacat.
- Gate: lihat bagian Gate (gate `649b7dc` bersama PY-T3).

Pelaksana (catatan asli):

Belum dijalankan (lingkungan A = integrator; `scripts/gate.sh` dan uji jalan tidak dijalankan pelaksana). Lingkungan B:

| Rangkaian | Basis B (`5f193df`) | W (B + unit) | T (HEAD `38c715f` + unit) |
|---|---|---|---|
| `tests_mem` | **1924 lulus / 2 dilewati / 2 xfail** (`bukti/KM-T2/tests_mem_B.txt`) | **1942 / 2 / 2** (+18 = `test_KMT2_capaian.py`; PR-T9 & MN-T1 tetap hijau) | **2063 / 2 / 2** (= HEAD 2045 + 18) |
| jest | 154 suite · **957 lulus** (35 suite gagal dimuat: `cmdk`/`@radix-ui`) | 155 suite · **967 lulus** (+10 `kmt2Capaian`; 35 suite sama) | 161 suite · **1005 lulus** (= HEAD 995 (957 + 8 PY-T2 + 7 TX-T2 + 11 AG-T5 + 5 CR-T2 + 7 PM-T4) + 10; 35 suite sama) |
| `hitung_penjaga.sh` | auth 27 · ui_standard 13 · i18n 103 · create_modal 6 · page_tabs 1 · to_list 5 · entity_label 2, lainnya PASS/0 | **identik** (`penjaga_W.txt`) | **identik dengan HEAD `38c715f`** (diukur di salinan arsip HEAD; auth 26 — turun dari 27 oleh AG-T5, lainnya = B) (`penjaga_T.txt`) |

Penjaga lain di T (`bukti/KM-T2/penjaga_audit_T.txt`): `verify_role_gate_ui` 31/0 · `verify_payment_vocab` 1830/0 ·
`verify_access_catalog_nav` 0 · `verify_atomic_claim` 161/0 (+`--self-test` 64 kasus hijau; endpoint baru hanya GET) ·
`verify_permission_checked` 615/0 (`incentive.view_margin` diperiksa `has_permission`) · `verify_detail_modal` 30/0 ·
`verify_custom_modals` 97/0 · `verify_posting_coverage` 138/0 · `verify_cash_single_door` 737/0 · `verify_codebase_map` 0 ·
`verify_config_fallback` 159/0 (`--entity` 159/0) · `verify_config_text` 3332/0 · `audit_config_wiring --strict` hijau dan
`check_nav_map` PASS (keduanya lewat salinan berjalur T) · `verify_contract --all` OK · `tests/test_fe03_access_catalog.py`
6/6. Di tengah kerja dua penjaga sempat merah dan diperbaiki: `verify_custom_modals` (panel samping buatan sendiri →
`DetailModal`, penyimpangan 1) dan `audit_i18n_id` (`Rp {x:,}` di ekspor → `core_utils.rupiah`).

## Penggabungan

- HEAD tujuan: **`38c715f`**. HEAD bergerak lima kali selama penggabungan: `5f193df` → `5edef21` (PY-T2) → `82ef1bb` (PY-T2
  lencana) → `15d3258` (TX-T2) → `7747302` (AG-T5) → `38c715f` (CR-T2 a/b, PM-T4); tiap kali T dipindah (gabung tiga arah
  dari keadaan T sebelumnya: kepala baru × kepala lama × T) dan diuji ulang. Worktree tujuan `wt26`, belum di-commit.
- Berkas (`bukti/KM-T2/gabung*.log`): 24 berkas unit (di luar laporan/bukti dan `backend/.env`); 5 berkas baru disalin.
  Digabung tiga arah, **kedua perilaku dipertahankan**:
  - tanpa bentrok: `backend/access_modules.py` (label AG-T5 `ai_finance.*` + nav/label/kelompok peka KM-T2),
    `frontend/src/AppViewRouter.jsx`, `appViewImports.js`, `config/hubTabs.js`, `config/navMeta.js`,
    `docs/KN_13_NAVIGATION_MAP.md`, `memory/PRD.md`, `view_main_permission.json`;
  - bentrok diselesaikan tangan: `backend/permissions_config.py` dan `tests_mem/test_PRT9_izin_bawaan.py` (blok PM-T4
    `PMT4_DEFAULT_PAIRS` lalu blok KM-T2 `KMT2_DEFAULT_PAIRS`; AG-T5 tetap di tempatnya), `config/__tests__/roleReach.test.js`
    (`…KMT1_TARGET_ATURAN, …KMT2_CAPAIAN, …PYT1_KOMPONEN, …PMT4_TITIPAN` untuk admin/manajer, Finance `…KMT2_CAPAIAN,
    …PMT4_TITIPAN`), `config/__tests__/mnt1MenuKeuangan.test.js` (`cash-bank` 5 dari PM-T4 + `hr-kpi-hub` 6 dari KM-T2),
    `ENTITY_REGISTRY.md` (baris bersebelahan: baris Meja Insentif milik unit + baris AG-T5/PM-T4 dari HEAD),
    `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (semua bagian baru dipertahankan: §9.18 PY-T2, §9.19 TX-T2, §9.20 AG-T5,
    §9.21 CR-T2, §9.22 PM-T4, bagian KM-T2 menjadi **§9.23**; di W tetap §9.18);
  - dibangkitkan ulang: `CODEBASE_MAP.md`, `configKeyIndex.json` (sama dengan HEAD — unit ini tanpa kunci baru),
    `access_builtin_fixture.json` / `access_nav_fixture.json` (`tests/fe03_access_fixture.py`, katalog gabungan;
    `test_fe03_access_catalog.py` 6/6).
- `aging_report` diubah CR-T2 (pembaca piutang beralih ke jadwal tagihan & saldo tersimpan): Capaian memanggilnya apa adanya;
  U1 (sisa piutang 600 jt / lewat tempo 300 jt per 31 Okt) tetap hijau di T.
- Hitungan uji lama: PR-T9 `KMT2_DEFAULT_PAIRS`; unit ini tidak menambah kunci pengaturan atau indeks wajib (KF-T1
  `*_KUNCI` dan PK-14 milik unit lain dibiarkan apa adanya).
- Seed data uji (`seed_realistic.py` akar repo dan `backend/seed_realistic.py`): unit ini tidak mengubah syarat pembuatan
  dokumen yang di-seed dan tidak menghapus/mengganti nama fungsi — keduanya tidak diubah.

## Menyimpang dari blueprint

1. **Panel telusur = pop-up rincian baku `DetailModal`**, bukan panel samping: penjaga INV-UI-11
   (`verify_custom_modals.py`) menolak berkas baru yang merakit lapisan sendiri (`fixed inset-0`); versi panel samping
   pertama merah di penjaga itu. Isi, judul, centang, dan jumlah sesuai spesifikasi.
2. **Pilihan "Kolom"** (Ringkas · Omzet · Pencairan · Kualitas harga · Lain · Semua kolom; bawaan Ringkas, ikut tampilan
   tersimpan) dan **angka uang tanpa "Rp" di sel**: 17 kolom angka tidak muat di kartu 1024 px (aturan cek layar #1).
   Judul kelompok dan kolom tetap persis spesifikasi. Sakelar tambahan **"Hanya yang ada angkanya"** (bawaan hidup) supaya
   baris nol tidak mendominasi.
3. **Kelompok selain sales**: selain target, piutang, dan pelanggan baru, `pct_omzet`/`pct_pencairan` juga tidak dikirim
   (turunan target). **Uang masuk** (dan piutang) bernilai kosong + catatan untuk kelompok kategori/sumber harga dan saat
   saringan kategori/lini/sumber harga aktif — pencairan dialokasikan per pesanan, bukan per baris barang.
4. **Target rentang tanggal** = Σ target bulanan untuk bulan yang seluruhnya di dalam rentang (spesifikasi hanya
   mengatur kumulatif). Dua pesan 400 tambahan: "Kumulatif tahun berjalan hanya untuk jenis periode Bulan." dan "Rentang
   tanggal tidak sah. Isi tanggal awal dan akhir, …".
5. **Telusur** juga menerima `group_by` + `key` (baris pelanggan/kategori/sumber harga bisa ditelusuri); butir membawa
   `link` (`doc_refs_service.link_of`) dan `source_label`; `amount` dalam sen, `sum` = angka sel dalam rupiah.
6. **Ekspor** juga menerima `q` (cari nama) dan `only_numbers`, supaya isi berkas = daftar yang sedang dilihat (KN_37 §6);
   lembar Definisi juga menulis pengelompokan, cari, dan catatan; keterangan tiap definisi (mis. "Nilai barang terkirim
   (surat jalan) dalam periode, tanpa PPN.") — itulah yang memuat kata "terkirim" (U14; label pilihannya "Saat barang
   dikirim").
7. **Margin** atas baris `kirim`, `pesanan_lama`, dan `retur` yang biayanya tercatat (margin bersih retur); hitungan
   "baris tanpa biaya" hanya baris omzet.
8. **Pencocokan** periode lebih dari sebulan = tiap bulan yang tersentuh (cocok bila semua cocok; selisih = Σ).
9. **Sisa piutang** per `min(akhir periode, hari ini)`; pemegang piutang/target/pelanggan baru di luar `sales_roster`
   tetap menjadi baris supaya total = Σ baris.
10. `incentive.view_margin` dimasukkan ke kelompok peka "melihat HPP dan margin" (peringatan editor peran), setara
    `ai.view_margin`.
11. `KN_13`: baris Target & Aturan (`incentive-setup`) dan Komisi Otomatis yang belum dicatat KM-T1 ikut dibetulkan.

## Asumsi

- `ASUMSI:` (spesifikasi) % capaian omzet memakai omzet bersih; sisa piutang memakai pemilik pelanggan saat ini; tampilan
  tersimpan di peramban; ekspor memakai `incentive.view`.
- `ASUMSI:` dasar omzet **`lunas`**: pesanan dihitung sekali pada tanggal baris `settles_order` TERAKHIRNYA (pelunasan
  ulang sesudah pembatalan memindahkan pesanan ke periode pelunasan terakhir).
- `ASUMSI:` dasar **`pesanan`/`lunas`** memakai atribusi `fact_sales_lines` (bawaan `ai.sales_attribution` = `team_split` =
  potret K-21 yang sama); `fact_sales_lines` tidak menyimpan sumber harga → kelompok "Sumber harga tidak tercatat".
- `ASUMSI:` pemilik pelanggan berlaku juga untuk uang masuk (dikelompokkan menurut pemegang pelanggan saat ini).

## Hambatan lingkungan

- Uji jalan peramban (U17) dan gate `scripts/gate.sh` tidak dijalankan pelaksana (lingkungan A = integrator).
- Jest: 35 suite gagal dimuat (`cmdk`/`@radix-ui`), sama dengan basis.
- `hitung_penjaga.sh` sekali dijalankan baca-saja terhadap salinan utama sebagai pembanding hitungan HEAD; penjaga statik itu
  meninggalkan cache bytecode `.pyc` (diabaikan git) di sana — tidak ada berkas terlacak yang berubah.

## Yang perlu direview

- Uji jalan U17 (login manager, Capaian › klik uang masuk Budi › klik RB0) dan potret 1280/1024/390 px — terutama lebar
  pilihan kolom "Ringkas"/"Omzet"/"Pencairan" di 1024 px dengan angka miliaran.
- Kinerja periode panjang di data acuan: tiap permintaan memanggil `aging_report` sekali dan pencocokan per bulan
  (tahun = 12 bulan). Bila lambat, pencocokan bisa dipindah ke permintaan terpisah.
- Pembanding H5 (`05` §9) dilakukan pemilik sesudah unit ini; tidak ada yang dinyalakan.

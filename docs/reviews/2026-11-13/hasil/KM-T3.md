# KM-T3 — Bangun Lembar Insentif: dokumen keputusan dengan nominal diketik dan angka dasar dipotret

- Commit awal: `f64c9d3` (worktree kerja, basis B)        - Commit akhir: `5410979`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: KM-05 (spesifikasi `docs/blueprint/unit/KM-T3.md`; keputusan K-25, K-19 … K-24 lewat versi definisi yang dipotret)
- Risiko sedang → satu serah-terima. Unit ini tidak menjurnal dan tidak menyentuh gaji (KM-T4).

## Cek ulang "Keadaan sekarang" (spesifikasi `3132cc4`, diperiksa di `f64c9d3`)

| Butir | Hasil di basis B |
|---|---|
| Insentif = satu angka mesin, dihitung ulang tiap diminta `crm.py:294` (`get_commission`) → `sales_force_service.py:189` | Berlaku, bergeser — `crm.py:365` (`get_commission`) → `sales_force_service.py:192` (`compute_commission`). Tidak ada tempat mengetik nominal / alasan / mengesahkan |
| Akrual dihitung saat tombol ditekan `gl_service.py:2913`, dipicu `crm.py:321` (`post_incentive_gl`) | Berlaku, bergeser — `gl_service.py:3494` (`post_incentive_accrual`, memanggil `sf.compute_commission` di `:3520`), dipicu `crm.py:392`. Tidak disentuh (KM-T4) |
| Skema lama `status: "draft"` tidak pernah berpindah `crm.py:444` | Berlaku, bergeser — `crm.py:518` (`sales_incentives`) |
| Angka sumber berubah mundur: batal kwitansi menulis ulang riwayat bayar `ar_receipt_service.py:739` | **Sebagian tidak berlaku** — PK-19: batal = baris pembalik bertanggal batal (`paid_total` kini `:372`). Retur dan serah-terima pelanggan tetap mengubah hasil hitung periode lalu → alasan potret tetap ada (U4, U5) |
| Antrean Pusat Persetujuan = baris `approval_backlog_service.py:159` (`hr_payroll`); dibaca `so_approvals.py:442` | Berlaku, bergeser — `:168`; `so_approvals.py:461` (`approvals_backlog`). Menambah antrean kini juga menuntut jenis `approval_kinds.py` (INV-APPR-01 G, KP-T4), pintu di `verify_approval_queues.DOOR_QUEUE`, pasangan `verify_home_kpi.EXPECT` |
| Nomor per PT `hr_payroll_service.py:378` (`next_doc_number`); wajib-unik `indexes.py:366` | **Bergeser** — pembuat nomor kini `core_utils.py:22` (`next_doc_number`, KP-T5: jenis wajib terdaftar di `doc_number_kinds.py`); `UNIQUE_DOC_NUMBER_FIELDS` `indexes.py:460`. **Temuan:** awalan `INS-` sudah dipakai Inspeksi mutu (`doc_number_kinds` `ins`) dan deret per PT berkunci awalan → lihat "Menyimpang" |
| `IDEMPOTENT_PREFIXES` `idempotency.py:21` | Berlaku, bergeser `:25` |
| Dipakai dari unit lain: `incentive_achievement` (KM-T2), `incentive_components`, `current_definition`, rekonsiliasi (KM-T1), `butuh_orang_kedua` / `tolak_bila_pelaku_sama` (KF-T6) | Ada semua. Pengumpul KM-T2 dipakai lewat satu fungsi publik baru `incentive_achievement.angka_sales` (memanggil `_kumpulkan` + `achievement` yang sama dengan tabel Capaian); rekonsiliasi = `reconciliation` jawaban Capaian; `services/dual_control.py` |
| (tambahan) Hub `hr-kpi-hub` | **Sudah enam tab** sejak KM-T2 (Capaian, Kinerja Sales, Target & Aturan, Komisi Otomatis, Skema (Arsip), KPI Karyawan) — tab ke-7 melanggar `02_STANDAR.md` L3 dan penjaga INV-UI-13 → lihat "Menyimpang" |

## KM-05 — Keputusan insentif tanpa dokumen

- Berlaku di HEAD: ya (fitur baru; endpoint `/api/incentive/sheets*` 404 di B — `bukti/KM-T3/merah_kode_lama_varian_404.txt`).
- Akar masalah: insentif hanya angka mesin yang dihitung ulang tiap diminta; tidak ada nominal yang diketik orang, tidak ada
  pengesahan, dan angka dasarnya ikut berubah bila data sumber berubah (retur, serah-terima).
- Perubahan perilaku (sebelum → sesudah):
  - **Koleksi `incentive_sheets`** (SCOPED; `ENTITY_REGISTRY.md` §KM-T3; `verify_contract.py`): satu lembar per PT per periode
    bayar, nomor `{KODE PT}/LIN-00001` (jenis `lin` di `doc_number_kinds.py`), `lines[]` per sales × komponen × periode
    dasar, `active_keys[]`, `totals` (Σ nominal rupiah bulat), pelaku, `history[]` hanya-tambah, `rev`.
  - **Potret**: tiap baris memotret angka dasar dari pengumpul Capaian (`angka_sales`) + versi definisi PT
    (`current_definition`): target, omzet, retur, omzet bersih, % capaian, target cair, uang masuk, % pencairan, realisasi
    harga, porsi di bawah acuan, margin (dikirim hanya ke pemegang `incentive.view_margin`), catatan data, sidik SHA-256
    `doc_id:amount` dokumen omzet/retur/uang masuk, banyak dokumen. Disalin apa adanya, tidak dihitung ulang sesudah disahkan
    (D3). Server tidak pernah mengisi `amount`; tidak ada rumus.
  - **`drift`** pada `GET …/sheets/{id}`: `omzet_bersih`, `uang_masuk`, `realisasi_harga_pct` yang kini berbeda dari potret,
    dihitung dengan **definisi yang dipotret baris itu** (yang tampil = perubahan data, bukan perubahan definisi).
  - **Transisi** draf → diajukan → disahkan; diajukan → draf (kembalikan, alasan ≥ 5 huruf); draf → dibatalkan (alasan,
    `active_keys` dikosongkan). Semua tulisan lewat `_simpan` = `find_one_and_update` bersyarat status lama + `rev`
    (dua pengesahan bersamaan → satu 200, satu 409). `paid` ditulis KM-T4.
  - **Keunikan**: satu (sales, komponen, periode dasar) di lembar yang masih berlaku — dicek di layanan (409 pesan
    spesifikasi) dan dijaga indeks unik wajib `uq_isheet_active_key` (`entity_id`, `active_keys`, parsial teks terisi; D7).
    Koreksi sesudah disahkan = **baris penyesuaian** (boleh negatif, wajib catatan, rujukan `{sheet_id, sheet_number,
    line_id}` ke baris bukan penyesuaian lembar `approved`/`paid` PT sama untuk sales sama).
  - **Sahkan** (`approve_sheet`): koreksi nominal pemutus wajib catatan (`amount_prepared`, `approver_note`); kontrol dua orang
    `dual_control.tolak_bila_pelaku_sama("lembar_insentif", …, pengaju=[submitted_by.id])` atas nominal **terbesar** antara
    sebelum dan sesudah koreksi; lalu `approval_policy_service.guard_door("incentive_sheet", …)` (Aturan Persetujuan KP-T4,
    bawaan semua pemegang `incentive.approve` — tidak mengubah keputusan sampai Admin membatasi).
  - **Endpoint** di `routers/incentive.py` (pernyataan pertama tiap handler = `require_permission`/`require_any_permission`,
    pesan Z6 modul "Kinerja & Insentif"); awalan `/api/incentive/` di `IDEMPOTENT_PREFIXES` (N4); PT lembar = PT dokumen
    (`guard_doc`), tulis menolak "Semua PT" (`assert_write_entity`). Tambahan di luar tabel spesifikasi: `GET
    …/sheets/options` (sales `sales_roster` + komponen aktif untuk pop-up baris; penyiap tanpa `incentive.view` tidak bisa
    membaca `GET /api/incentive/targets`) dan `q` (cari nomor/judul) pada daftar.
  - **Antrean** `("incentive_sheet", "Lembar insentif menunggu pengesahan", "incentive-sheets", "incentive_sheets",
    {"status": "submitted"})` + `AGING_META` + `QUEUE_PRESETS` (`{status: "submitted"}`) + jenis `approval_kinds.incentive_sheet`
    + `DOOR_QUEUE` pintu approve + `verify_home_kpi.EXPECT`.
  - **Pengaturan**: aksi `lembar_insentif` di `KONTROL_AKSI` ("Pengesahan lembar insentif", bernominal, bawaan "1", bagian SDM)
    → `kontrol.lembar_insentif.min_orang` (bawaan "1", K-25) dan `.batas_nominal` (bawaan 0); `consumers`
    `services/incentive_sheet_service.py:approve_sheet`. Layar = tab Kontrol dua orang yang sudah ada.
  - **Izin** `incentive.prepare` ("Siapkan lembar insentif": admin, manager, sales_admin, finance) dan `incentive.approve`
    ("Sahkan lembar insentif": admin, manager) — `permissions_config.KMT3_DEFAULT_PAIRS`; modul akses `incentive` nav +
    `incentive-sheets`.
  - **Layar** SDM › Kinerja & Insentif › **Lembar Insentif** (tab ke-2; `IncentiveSheetsView`, rincian pop-up
    `IncentiveSheetDetail`) dan tombol "Buat lembar insentif dari tampilan ini" di Capaian (lihat "Cek layar").
- Fixture disiapkan langsung vs proses bisnis dijalankan: F3 = fixture F2 KM-T2 (pesanan, surat jalan, retur & nota kredit
  disisipkan; jurnal lewat `post_order_revenue_and_cogs` / `post_sales_return` asli; kwitansi lewat `create_receipt` asli;
  target `save_target`; komponen `create_component`; fakta `incentive_facts.rebuild`). Semua aksi lembar lewat API.
- Dampak pada modul terkait: tab "Skema (Arsip)" tidak lagi tampil di bilah tab hub Kinerja & Insentif (layarnya tetap; lihat
  "Menyimpang"); Pusat Persetujuan/KPI beranda mendapat satu antrean; tab Kontrol dua orang mendapat satu aksi.
- Status: implemented_pending_review

## Berkas

| Berkas | Isi |
|---|---|
| `backend/services/incentive_sheet_service.py` (baru) | Lembar: siapkan & potret baris, simpan bersyarat, transisi, `drift`, rujukan penyesuaian, ekspor `.xlsx` |
| `backend/services/incentive_achievement.py` | + `angka_sales` (pengumpul Capaian untuk potret; satu rumus) |
| `backend/routers/incentive.py`, `backend/schemas_incentive.py` | 13 endpoint `/api/incentive/sheets*`; tujuh skema permintaan (batas nominal ±1 T) |
| `backend/permissions_config.py`, `backend/access_modules.py` | `KMT3_DEFAULT_PAIRS`; nav `incentive-sheets`; label aksi |
| `backend/config_catalog_kontrol.py` | aksi `lembar_insentif` (+ titik pasang, nama pendek) |
| `backend/services/approval_backlog_service.py`, `backend/approval_kinds.py` | antrean, umur tunggu, preset; jenis `incentive_sheet` |
| `backend/indexes.py`, `backend/entity_scope.py`, `backend/idempotency.py`, `backend/doc_number_kinds.py` | indeks (unik `number`, wajib `uq_isheet_active_key`, dua indeks kerja); SCOPED; awalan idempoten; jenis nomor `lin` |
| `scripts/verify_contract.py`, `scripts/guardrails/verify_approval_queues.py`, `scripts/guardrails/verify_home_kpi.py` | koleksi kanonik; pintu approve → antrean; pasangan opini kedua |
| `frontend/src/features/incentive/IncentiveSheetsView.jsx`, `IncentiveSheetDetail.jsx` (baru) | Daftar & rincian |
| `frontend/src/features/incentive/CapaianView.jsx` | Tombol + pop-up "Buat lembar insentif dari tampilan ini" (terlokalisasi) |
| `frontend/src/AppViewRouter.jsx`, `appViewImports.js`, `config/hubTabs.js`, `config/navMeta.js` | Tab & rute; "Skema (Arsip)" `hidden` (`aliasOf` Lembar Insentif) |
| Dibangkitkan | `CODEBASE_MAP.md`, `frontend/src/features/settings/config/configKeyIndex.json`, `config/__tests__/fixtures/access_nav_fixture.json`, `access_builtin_fixture.json`; tabel bantu `view_main_permission.json` (+ baris `incentive-sheets`) |
| Uji baru | `backend/tests_mem/test_KMT3_lembar_insentif.py` (18), `backend/tests/test_bp_KMT3_lembar_bersamaan_mongo.py` (lapis A U16, ditulis), `frontend/src/features/__tests__/kmt3LembarInsentif.test.js` (7) |
| Dokumen | `ENTITY_REGISTRY.md` (baris ringkas + §KM-T3), `memory/PRD.md`, `docs/KN_13_NAVIGATION_MAP.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.25 |

## Uji penerimaan

"Merah lama" = berkas uji dijalankan di salinan dengan semua berkas backend yang diubah unit dikembalikan ke `f64c9d3` dan
layanan baru disingkirkan (`bukti/KM-T3/merah_kode_lama.txt`: fixture gagal — `Aksi ['prepare'] tidak berlaku untuk
“Kinerja & Insentif”`, izin belum ada; varian fixture tanpa izin baru `bukti/KM-T3/merah_kode_lama_varian_404.txt`: 18/18
gagal `{"detail":"Not Found"}`). Jest: `bukti/KM-T3/jest_merah_kode_lama.txt` (`Cannot find module '../incentive/IncentiveSheetsView'`).

| ID | Lapis | Kode lama | Kode baru |
|---|---|---|---|
| U1 | B | merah (404 / izin tidak ada) | lulus — `draft`, nomor `KANDA/LIN-…`, `amount` awal `[None, None, None]`, `totals` 0 → sesudah diketik 2 + 3 + 3,5 jt = **8.500.000**; potret Andi BLN `omzet` 1.000.000.000, `target_sales` 800.000.000, `uang_masuk` 700.000.000, `realisasi_harga_pct` 86,2 (+ omzet bersih, % 125,0 / 93,3, versi definisi, sidik 64 huruf, 1 dokumen omzet & 1 uang masuk); Andi TW 2.400/2.600/2.250/2.300 jt, 88,0; Budi BLN 500/500/450/520 jt, 100,0; label "Okt 2026" / "Triwulan III 2026"; margin tidak dikirim ke penyiap |
| U1 (galat) | B | merah | lulus — komponen nonaktif 400 pesan spesifikasi; periode dasar ≠ komponen 400; periode bayar salah 400; "Semua PT" ditolak; sales di luar PT 400 |
| U2 | B | merah | lulus — `submitted`; `PATCH` 409 "Lembar KANDA/LIN-00001 berstatus Diajukan, jadi tidak bisa diubah."; tambah baris 409 |
| U3 | B | merah | lulus — `mgr` 200 `approved`, `totals.amount` 8.500.000, `journal_entries` tetap; riwayat draf → diajukan → disahkan; margin 30,0 terlihat pemegang `view_margin`; `PATCH` sesudahnya 409 "… berstatus Disahkan …" |
| U4 | B | merah | lulus — retur 50 jt atas OA1 25 Okt + bangun fakta: potret tetap `omzet_bersih` 1.000.000.000; `drift` hanya baris Andi BLN: `current` 950.000.000, `diff` −50.000.000 |
| U5 | B | merah | lulus — lembar draf Andi BLN 2026-09; segarkan sebelum retur → `changed` []; retur 30 jt atas OA0 20 Sep → `changed` = [baris itu], potret `retur` 30.000.000, `omzet_bersih` −30.000.000, sidik berubah; lembar disahkan → segarkan 409 |
| U6 | B | merah | lulus — `kontrol.lembar_insentif.min_orang` = "2" untuk `ent_kanda`, lembar diajukan `mgr`: `mgr` sahkan 403 pesan `dual_control.pesan_tolak("lembar_insentif")`; `adm` sahkan 200; bawaan satu orang |
| U7 | B | merah | lulus — koreksi Budi 3.000.000 tanpa catatan 400 "Beri catatan untuk setiap nominal yang dikoreksi."; dengan catatan 200: `amount` 3.000.000, `amount_prepared` 3.500.000, `totals.amount` 8.000.000 |
| U8 | B | merah | lulus — 409 "Andi · Insentif Bulanan · Okt 2026 sudah ada di lembar KANDA/LIN-00001."; kembar di lembar yang sama juga 409 |
| U9 | B | merah | lulus — penyesuaian −500.000 merujuk baris U1 (catatan) 200, `active_keys` [], total −500.000; tanpa `adjusts` 400 pesan spesifikasi; tanpa catatan 400; rujuk lembar draf 400; baris biasa −1 → 400 "Nominal negatif hanya untuk baris penyesuaian." |
| U10 | B | merah | lulus — kembalikan "cek Budi" → `draft`, `history` +1 (`return`, alasan, `submitted` → `draft`, pelaku `mgr`); ajukan ulang, kembalikan "x" → 400 "Tulis alasan minimal 5 huruf.", status tetap `submitted` |
| U11 | B | merah | lulus — `insentif.dasar_omzet` `ent_kanda` = `pesanan` (versi definisi PT +1): potret semua baris tetap versi lama dan `dasar_omzet` `terkirim` |
| U12 | B | merah | lulus — Tanpa Acuan ber-`incentive.prepare` saja: buat lembar 200; sahkan 403 (Z6 "… mengesahkan lembar insentif … 'Kinerja & Insentif'"); Manajer Kosong & Sopir: daftar, rincian, buat → 403 bentuk Z6 |
| U13 | B | merah | lulus — lembar `ent_ksc`; `mgr` (hanya `ent_kanda`): rincian, ajukan, ekspor 403/404; status tetap `draft`; daftar Kanda tidak memuatnya |
| U14 | B | merah | lulus — `GET /api/approvals/backlog`: antrean `incentive_sheet` berjumlah 1, label & view spesifikasi |
| U15 | B | merah | lulus — `.xlsx` lembar "Lembar" & "Potret"; tiga baris nominal 2/3/3,5 jt, total 8.500.000; "Potret" memuat 1000000000 dan kolom Margin (pemegang `view_margin`); tanpa `view_margin` kolom Margin tidak ada |
| (tambahan) | B | merah | lulus — ajukan dengan nominal kosong 400 pesan spesifikasi; batal butuh alasan; lembar dibatalkan melepas `active_keys` (baris yang sama bisa dibuat lagi); daftar bersaring status, tanpa potret, berhalaman; katalog izin bawaan, aksi kontrol, kunci & `consumers`, jenis nomor, indeks, jenis persetujuan |
| U16 | A | — | **ditulis, belum teruji** — `backend/tests/test_bp_KMT3_lembar_bersamaan_mongo.py` (indeks terpasang; dua sahkan bersamaan → [200, 409] ×3; dua buat lembar → dua nomor; dua lembar dengan baris sama → [200, 409] ×3) |
| U17 | layar | merah (komponen belum ada) | jest pengganti `kmt3LembarInsentif` 7/7: konfirmasi "2 baris · total Rp 5.500.000 · CV Kanda Suka", lencana "Disahkan", isian nominal/koreksi hilang sesudah disahkan, kunci idempotensi terkirim, tombol Capaian aktif sesudah Andi & Budi dicentang. **Belum diuji jalan** di peramban (integrator, 1280/1024/390) |

### Contoh angka (hitung tangan; dibuktikan U1, U3, U4, U7)

| Langkah | Angka |
|---|---|
| Potret Andi BLN Okt 2026 | omzet bersih OA1 1.000.000.000 ÷ target 800.000.000 = 125,0 %; uang masuk RA1 700.000.000 ÷ 750.000.000 = 93,3 %; realisasi 1.000 jt ÷ 1.160 jt (list 58.000) = 86,2 % |
| Nominal diketik | Andi BLN 2.000.000 + Andi TW 3.000.000 + Budi BLN 3.500.000 = **8.500.000** (`totals.amount`) — tidak ada nominal dari sistem |
| Sahkan (U3) | 8.500.000; jurnal 0 (KM-T4) |
| Retur 25 Okt Rp 50 jt (U4) | potret tetap 1.000.000.000; `drift` 950.000.000 − 1.000.000.000 = −50.000.000 → bahan baris penyesuaian (U9: −500.000 dengan catatan) |
| Koreksi pemutus (U7) | Budi 3.500.000 → 3.000.000: total 2 + 3 + 3 = **8.000.000**, `amount_prepared` 3.500.000; kontrol dua orang dinilai atas max(8.500.000; 8.000.000) |

Log: `bukti/KM-T3/tests_mem_KMT3_hijau.txt`, `jest_KMT3_hijau.txt`, `merah_kode_lama*.txt`, `jest_merah_kode_lama.txt`,
`penjaga_sebelum_sesudah.txt`.

## Uji lama yang disesuaikan (angka/contoh, bukan harapan dilonggarkan)

| Berkas | Perubahan | Alasan |
|---|---|---|
| `tests_mem/test_KFT1_izin_pengaturan.py` | `KMT3_KUNCI_KONTROL = 2` (U02 & U04) | dua kunci `kontrol.lembar_insentif.*` berizin `settings.manage` |
| `tests_mem/test_KFT6_kontrol.py` | `N_AKSI` 40 → 41, `N_KUNCI` 66 → 68, `BERNOMINAL` + `lembar_insentif` | aksi kontrol dua orang baru (spesifikasi) |
| `tests_mem/test_PRT9_izin_bawaan.py` | `TAMBAHAN_SESUDAH` + `KMT3_DEFAULT_PAIRS` | izin bawaan baru |
| `tests_mem/test_PK14_indeks_wajib.py`, `tests/test_bp_PK14_indeks_wajib.py` (lapis A, ditulis) | `KMT3_INDEKS = 1`; 36 → 37 | indeks wajib `uq_isheet_active_key` |
| `tests_mem/test_KPT4a_setara.py::test_KPT4_U1` | antrean 40 → 41 | baris antrean `incentive_sheet` (spesifikasi); jenisnya tercakup baris bawaan (mekanisme G) |
| `tests_mem/test_KPT5a_setara.py` | `AWALAN_SESUDAH_KPT5` + `LIN-` | deret nomor baru per PT |
| `tests_mem/test_KPT5b_pengaturan.py` (U14, daftar lengkap) | jenis nomor `66 + 1 + 1 + 2` → `+ 1` | jenis `lin` tampil di tabel Penomoran Dokumen |
| `config/__tests__/mnt1MenuKeuangan.test.js` | label hub Kinerja & Insentif + menu manajer | tab Lembar Insentif; Skema (Arsip) tersembunyi (jumlah tetap 6) |
| `config/__tests__/roleReach.test.js` | `KMT3_LEMBAR` untuk admin, manajer, Finance, Admin Sales | layar baru (tercatat) |
| `features/__tests__/prt7TombolIzin.test.js` (U7/U8) | cek Skema dari `hubTabsForRole(...).some` → `!!hubForView("incentive-schemes", role)` | tab kini tersembunyi; yang diuji tetap gerbang izinnya (manajer bawaan ya, peran tanpa `sales_force` tidak) |

## Cek layar

Dari kode (integrator memotret 1280/1024/390 px; kartu di 1024 px ≈ 750 px, pop-up `xl` ≈ 990 px).

| # | Butir | Lembar Insentif (daftar) | Rincian lembar (pop-up) | Capaian (tombol + pop-up) |
|---|---|---|---|---|
| 1 | Tabel lebih lebar dari kartu | 7 kolom (Nomor 128 · Periode bayar · Status · Baris · Total tanpa "Rp" · Penyiap 96 · Pemutus 96 ≈ 650 px isi + bantalan ≈ 720 px) — muat 750; `data-table head-wrap`; **tanpa kolom aksi** (nomor = tautan); `overflow-x-auto` di HP | 8 kolom (Sales 120 + tombol buka-tutup di sel · Komponen 100 · Periode dasar · Omzet / target dan Cair / target dua baris tanpa "Rp" · Realisasi · Nominal 128 · Catatan 128 ≈ 955 px) dalam pop-up `xl` (≈ 990 px di 1024, 1120 px di 1280); tanpa kolom aksi (hapus baris di rincian baris); di HP pop-up layar penuh, tabel bergulir di wadahnya | Tidak ada tabel baru; pop-up `FormModal` 3 isian |
| 2 | `section-card` tanpa bantalan | `section-head` + `section-body`; memuat/galat/kosong `section-pad` | sama | bilah di `section-body` yang ada |
| 3 | Kepala kartu dijejali | Kepala = ikon + "Lembar Insentif"; tombol & alasan di bilah sendiri | Kepala = judul + ×; status/PT/periode di bilah info, tombol di bilah aksi (flex-wrap) | Tombol di bilah sendiri di bawah toolbar |
| 4 | Tombol mati hanya tooltip | "Pilih satu PT dulu." / "Membuat lembar butuh akses Siapkan lembar insentif …" tertulis | Alasan tertulis: "Pilih satu PT dulu.", "Mengubah lembar butuh akses …", "Menunggu pengesahan oleh pemegang akses …", "Lembar sudah disahkan — koreksi dibuat sebagai baris penyesuaian …", Ajukan: "Simpan nominal dulu." / "Isi nominal semua baris …" / "Tambahkan minimal satu baris …" | "Centang sales yang akan dibuatkan lembar." / "Kelompokkan menurut Sales …" / "Membuat lembar butuh akses …" |
| 5 | Status hanya warna+teks | `status-pill` + ikon + teks: Draf `status-draft` (FilePen) · Diajukan `status-pending` (Clock) · Disahkan `status-done` (CheckCircle2) · Dibayarkan `status-shipped` (Wallet) · Dibatalkan `status-cancelled` (XCircle) — kelas yang ada di `styles/components.css` | sama; "Berubah sejak dipotret" ikon segitiga + teks jingga; `notice-bar warning` di rincian baris | — |
| 6 | Daftar tanpa cari | Saringan Periode bayar, cari "Nomor atau judul", chip status, `KNPager` + "n dari m lembar" | Kotak "Cari sales atau komponen" + "n dari m baris" | — |
| 7 | Teks bertentangan dengan izin | Tidak ada "bukan wewenang"; teks menyebut akses "Siapkan/Sahkan lembar insentif" modul Kinerja & Insentif | sama | sama |
| 8 | Kosong ganda / angka 0 / grafik | Satu kalimat "Belum ada lembar insentif untuk saringan ini." | Satu kalimat "Belum ada baris. …"; nominal kosong "—", target 0 "—"; tanpa grafik | — |

Tombol `btn-sm` + `whitespace-nowrap`; satu tombol utama per keadaan (Ajukan / Sahkan / Buat lembar); Batalkan & Hapus
baris `danger-button` + konfirmasi/alasan. Rupiah berpemisah ribuan (isian juga, negatif hanya baris penyesuaian), tanggal
`formatDateTime` WIB, label status `docStatusLabel` (peta lokal), riwayat dengan kalimat aksi, tanpa kode mentah (periode
dasar dan komponen berlabel; definisi di ekspor memakai label Pusat Pengaturan). Tanpa `type="date"` peramban (pilihan
periode = `KNSelect`). Kirim lewat `moneyRequest` + `useIntentKey`. Belum diuji jalan di peramban.

## Menyimpang dari blueprint

1. **Titik pasang kontrol dua orang ditulis dengan literal** `tolak_bila_pelaku_sama("lembar_insentif", …)` (bukan
   konstanta): uji KF-T6 U15 dan `config_health` mengenali titik pasang dari literal nama aksi.
2. **Awalan nomor `LIN-`, bukan `INS-`.** `INS-` sudah dipakai Inspeksi mutu (`doc_number_kinds` `ins`, `inspections`), dan
   deret per PT berkunci awalan (`number_sequences` `{entity_id, doc_type: "INS"}`) → kedua dokumen akan berbagi deret dan
   mencetak nomor yang sama bentuknya (`KANDA/INS-00001` bisa lembar atau inspeksi). Uji penerimaan tidak menyebut awalan.
   Usulan koreksi blueprint (teks pengganti di tabel Data): "`id`, `number`, `entity_id` | teks | ya | `isheet_…`; nomor
   `LIN-` per PT (`INS-` sudah dipakai Inspeksi mutu); PT dari konteks pengguna (N1)".
3. **Tab ke-7 → "Skema (Arsip)" disembunyikan.** Hub sudah enam tab sejak KM-T2; tab baru akan melanggar L3 dan menaikkan
   INV-UI-13 (penjaga tidak boleh dilonggarkan, `00` §7.1). Dipilih yang paling mudah dibalik: tab arsip skema lama
   (pendahulu lembar sebagai dokumen keputusan; KM-T5 juga mencabut tempat lamanya) diberi `hidden: true, aliasOf:
   "incentive-sheets"` — layar, izin, dan perannya tetap; dibuka lewat tautan "Skema insentif lama (arsip)" di Lembar
   Insentif atau tautan langsung. Membalik = hapus `hidden` saat KM-T5 membebaskan satu tab. Uji PR-T7 U7/U8 disesuaikan
   (lihat tabel).
4. **Membaca lembar juga untuk penyiap & pemutus.** Spesifikasi menulis `incentive.view` untuk `GET` daftar/rincian/ekspor,
   tetapi penyiap bawaan Admin Sales hanya diberi `incentive.prepare` → ia tidak bisa membuka lembar yang ia siapkan. Ketiga
   `GET` memakai `require_any_permission(view | prepare | approve)`; U12 (Manajer Kosong 403) tetap.
5. **Tambahan kecil:** `GET /api/incentive/sheets/options` (sales + komponen aktif untuk pop-up baris, karena penyiap tanpa
   `incentive.view` tidak bisa membaca daftar sales Target & Aturan) dan `q` di daftar (KN_37 §6 cari). Ekspor per lembar
   (spesifikasi); daftar lembar tidak memakai "Unduh ▾" Pusat Export (tidak memakai `PaginationBar`; penjaga INV-UI-07 tetap 0).
6. **Aturan Persetujuan**: pintu Sahkan juga memanggil `guard_door("incentive_sheet", …)` (KP-T4 sudah ada; tanpa itu jenis
   persetujuan baru tampil di Aturan Persetujuan tanpa efek — L5). Bawaan = semua pemegang izin, keputusan tidak berubah.

## Asumsi

- `ASUMSI:` (spesifikasi) lembar draf boleh dibatalkan dengan alasan; baris tanpa karyawan tertaut boleh disahkan; satu
  (sales, komponen, periode dasar) diputus sekali — tambahan lewat penyesuaian.
- `ASUMSI:` kontrol dua orang dinilai atas nominal terbesar antara sebelum dan sesudah koreksi pemutus (koreksi tidak bisa
  dipakai menurunkan lembar di bawah `batas_nominal`). Bawaan aksi satu orang (`00` §4.1 butir 3, K-25).
- `ASUMSI:` `drift` dihitung dengan definisi yang dipotret baris (perubahan definisi tidak tampil sebagai "berubah").
- `ASUMSI:` jenis periode baris = periode dasar komponen; komponen `free` boleh bulan/triwulan/tahun.
- `ASUMSI:` baris penyesuaian mengambil sales/komponen/periode dasar dari baris yang dirujuk (isian lain yang berbeda → 400) dan
  boleh berulang untuk baris yang sama; komponen yang sudah nonaktif tidak bisa disesuaikan (pesan komponen nonaktif).
- `ASUMSI:` "Segarkan angka dasar" memotret ulang dengan versi definisi yang berlaku sekarang (lembar draf).

## Titik henti

- H4: tidak ada tarif/persen insentif, rumus, atau akun jurnal — nominal diketik orang, unit tidak menjurnal.
- H5: tidak ada sakelar PT yang dinyalakan; komisi otomatis lama tidak disentuh (KM-T4).
- H3: tidak ada skrip data; uji hanya di database tiruan.

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di **`5410979`**:

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` | 12 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama) | 3 (`config_wiring` + uji-diri, `guard:atomic_claim`) |
| `--ci` | 39 FAIL | 43 | 1 (ganti nama) | 3 (sama) |

Sama dengan gate sebelumnya (`1315ce6`: 12 / 39); `guard:page_tabs` tetap 1 pelanggaran (tab Skema (Arsip) disembunyikan sehingga
hub Kinerja & Insentif tetap 6 tab). Kuitansi: `bukti/KM-T3/gate_quick_receipt.md`, `gate_ci_receipt.md`.

### Integrator: penggabungan, lingkungan A, layar

- HEAD cabang tetap `d2684ea` sejak pelaksana menggabung; T disalin apa adanya → **`5410979`** (46 berkas). `tests_mem` di T
  2265/2/2 dan jest 1071 (pelaksana, pohon sama — tidak diulang integrator).
- Lingkungan A (data acuan sesudah `restore_demo`, kode `5410979`; `bukti/KM-T3/integrator_lapis_A.txt`): lapis A **U16 2
  lulus** (dua pengesahan/pembuatan bersamaan → satu lembar aktif); PK-14 lapis A 9 lulus; `check_required_indexes` **37/37**
  (`uq_isheet_active_key` terpasang, 0 kembar).
- Uji jalan **U17** (integrator; satu lembar dibuat lewat API di database uji — data acuan belum punya komponen insentif, jadi
  baris tidak bisa ditambah): SDM › Kinerja & Insentif › **Lembar Insentif** (tab kedua sesudah Capaian; Skema (Arsip)
  tersembunyi, tautan "Skema insentif lama (arsip)" di kaki kartu) — saringan periode bayar, cari, chip status, tabel 7 kolom =
  **762 px = kartu** di 1024 px, status `Draf` ikon+teks; pop-up rincian: kepala (status, PT, periode bayar, judul, penyiap),
  bilah tombol (Tambah baris, Tambah penyesuaian, Segarkan angka dasar mati, Ajukan mati dengan alasan "Tambahkan minimal satu
  baris sebelum mengajukan.", Batalkan, Ekspor Excel), keadaan kosong satu kalimat, Riwayat (`bukti/KM-T3/cek_*.png`). Tidak
  ada cacat. Tabel rincian berbaris (8 kolom ±955 px di pop-up `xl`) tidak terpotret karena data acuan tanpa komponen.

Pelaksana (catatan asli):

Belum dijalankan (lingkungan A dipakai integrator). Lapis A U16 dan `tests/test_bp_PK14_indeks_wajib.py` (37) ditulis, belum
teruji. Uji jalan U17 belum.

## Penjaga & angka uji (worktree kerja W, basis `f64c9d3`)

| | Sebelum (B) | Sesudah (W) |
|---|---|---|
| `tests_mem` | 2101 lulus / 2 dilewati / 2 xfail | **2121** lulus / 2 / 2 (+18 KM-T3, +2 kasus setara KP-T5 untuk titik panggil `LIN-`) |
| jest penuh | 1018 lulus (35 suite gagal dimuat — `cmdk`/`@radix-ui`) | **1025** lulus (+7 `kmt3LembarInsentif`; 35 suite yang sama) |
| `hitung_penjaga.sh` | auth 26 · ui_standard 13 · i18n 103 · create_modal 6 · page_tabs 1 (INV-UI-13 0) · to_list 5 · entity_label 2 · lainnya 0 | **identik** |
| `verify_posting_coverage` · `verify_atomic_claim` (+ uji-diri) · `verify_role_gate_ui` | 138/0 · 161/0 (64 kasus hijau) · 31/0 | 138/0 · 161/0 (64 kasus hijau) · 31/0 |
| `verify_detail_modal` · `verify_cash_single_door` · `verify_config_text` | 30/0 · 740/0 · 3402/0 | 31/0 · 741/0 · 3416/0 |
| `verify_approval_queues` (statik, MongoDB tidak dihubungi) | 9 pelanggaran lama / 328 cek | 9 yang sama / 334 cek |
| `audit_config_wiring --strict` · `check_nav_map` · `verify_config_fallback` (+`--entity`) · `verify_payment_vocab` | hijau | hijau (160/0, 160/0, 1839/0) |

Bukti: `bukti/KM-T3/tests_mem_ringkas.txt`, `jest_ringkas.txt`, `penjaga_sebelum_sesudah.txt`.

## Penggabungan (pelaksana, ke HEAD `d2684ea` — sesudah MN-T2, CR-T4, CR-T3, PY-T5, PY-T4, CR-T5)

Gabung pertama ke `fc95d36` dibatalkan sebelum uji penuh selesai karena HEAD bergeser ke `945da6e` (CR-T3 menyentuh banyak
berkas bersama); digabung ulang ke `945da6e`, lalu dimajukan ke `eaba57f` (hanya `CreditOverridesPanel.jsx`, tidak disentuh
unit ini) , ke `b014a38` (PY-T5; tiga arah dengan basis `eaba57f` untuk `test_KFT1`, `KN_32`, `PRD.md`), ke `61cf7a1` (PY-T4; tiga
arah dengan basis `b014a38` untuk 13 berkas bersama), , ke `efc1cc6` (PY-T4 cek layar; tiga berkas penggajian/cuti, tidak
disentuh unit ini), ke `d08d664` (CR-T5; tiga arah dengan basis `efc1cc6` untuk 14 berkas bersama — satu bentrok
glosarium), lalu ke `d2684ea` (cek layar CR-T5 `creditDeskParts.jsx` + STATUS/TRACKER; tidak bersinggungan). Angka
`tests_mem`/jest di bawah dijalankan di `d08d664` (backend dan berkas uji `d2684ea` sama); `hitung_penjaga.sh` diulang di
`d2684ea` (HEAD = T) dan jest suite terdampak (`kmt3`, `crt5`, menu, jangkauan peran) 95/95. Per berkas: sama dengan B → disalin dari W; beda → `git merge-file -p <HEAD> <B> <W>`; baru → disalin
(`bukti/KM-T3/gabung_daftar_berkas.txt`).

| Berkas | Keadaan | Keputusan |
|---|---|---|
| `backend/idempotency.py` | bentrok di ujung `IDEMPOTENT_PREFIXES` (CR-T3 `"/api/credit-overrides"`) | keduanya: `"/api/credit-overrides",` lalu `"/api/incentive/"` |
| `backend/permissions_config.py` | bentrok blok sesudah KM-T2 (CR-T3 `CRT3_DEFAULT_PAIRS`, lalu PY-T4 `PYT4_DEFAULT_PAIRS`) | semuanya: blok CR-T3, PY-T4 utuh lalu blok KM-T3 |
| `tests_mem/test_KFT1_izin_pengaturan.py` | bentrok konstanta & jumlah U04 (CR-T3 `CRT3_KUNCI = 9`, PY-T5 `PYT5_KUNCI = 1`) | semuanya: `… + CRT3_KUNCI + PYT5_KUNCI + KMT3_KUNCI_KONTROL` (U02 hanya `+ KMT3_KUNCI_KONTROL`: kunci CR-T3/PY-T5 tidak berizin `settings.manage`) |
| `tests_mem/test_PRT9_izin_bawaan.py` | bentrok blok tambahan izin (CR-T3, PY-T4) | semuanya, CR-T3, PY-T4 lalu KM-T3 |
| `config/__tests__/roleReach.test.js` | bentrok baris tambahan Finance (PY-T4 `PYT4_SETORAN_FINANCE`) | keduanya: `…, ...PYT4_SETORAN_FINANCE, ...KMT3_LEMBAR]` |
| `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` | HEAD menambah §9.25 (MN-T2), §9.26 (CR-T4), §9.27 (CR-T3), §9.28 (PY-T5), §9.29 (PY-T4), §9.30 (CR-T5) | bagian KM-T3 menjadi **§9.31** (di W tetap §9.25) |
| `ENTITY_REGISTRY.md`, `access_modules.py`, `config_catalog_kontrol.py`, `entity_scope.py`, `indexes.py`, `approval_backlog_service.py`, `scripts/verify_contract.py`, `KN_13`, `PRD.md`, `AppViewRouter.jsx`, `appViewImports.js`, `navMeta.js`, `hubTabs.js`, `mnt1MenuKeuangan.test.js`, `prt7TombolIzin.test.js`, `view_main_permission.json` | tergabung otomatis | diperiksa: tidak ada baris HEAD yang hilang (selain baris `QUEUE_PRESETS` yang diperluas) |
| `CODEBASE_MAP.md`, `configKeyIndex.json`, `access_nav_fixture.json`, `access_builtin_fixture.json` | turunan | dibangkitkan ulang di T (`test_fe03_access_catalog --noconftest` 6/6) |

Hitungan uji lama di HEAD (KF-T1, PRT9, indeks wajib PK-14 = 36 + 1, antrean KP-T4 = 40 + 1, jenis nomor KP-T5) tidak diubah
unit lain sesudah B selain yang tercatat di atas → angka KM-T3 ditambahkan apa adanya.

| | HEAD `d08d664`/`d2684ea` (murni) | T (HEAD + KM-T3) |
|---|---|---|
| `tests_mem` | 2245 lulus / 2 dilewati / 2 xfail | **2265** lulus / 2 / 2 (+20, sama dengan di W) |
| jest penuh | 1064 lulus (35 suite gagal dimuat — `cmdk`/`@radix-ui`) | **1071** lulus (+7; 35 suite yang sama) |
| `hitung_penjaga.sh` | auth 26 · ui_standard 11 · i18n 102 · create_modal 5 · page_tabs 1 (INV-UI-13 0) · to_list 5 · entity_label 2 · lainnya 0 | **identik** |
| `verify_posting_coverage` · `verify_atomic_claim` (+ uji-diri 64) · `verify_role_gate_ui` | 137/0 · 161/0 · 31/0 | 137/0 · 161/0 · 31/0 |
| `verify_detail_modal` · `verify_cash_single_door` · `verify_config_text` | 30/0 · 748/0 · 3472/0 | 31/0 · 749/0 · 3486/0 |
| `verify_config_fallback` (+`--entity`) · `verify_payment_vocab` | 161/0 (161/0) · 1855/0 | 162/0 (162/0) · 1858/0 |
| `verify_approval_queues` (statik) · `audit_config_wiring --strict` · `check_nav_map` | 9 lama / 328 · hijau · PASS | 9 yang sama / 334 · hijau · PASS |

## Hambatan lingkungan

- Suite jest yang memuat `cmdk`/`@radix-ui` gagal dimuat di lingkungan lokal (kendala lama); uji KM-T3 meniru `KNSelect`.
- `verify_approval_queues` bagian data dilewati (MongoDB tidak dihubungi); bagian statik: 9 pelanggaran lama yang sama
  dengan basis (pintu tanpa antrean di `hr_compensation.py`, `hr_payroll.py`, `initial_registration.py`, …), tidak bertambah.

## Yang perlu direview

- Keputusan "Skema (Arsip)" disembunyikan vs. tab ke-7 (Menyimpang 3) dan awalan `LIN-` (Menyimpang 2).
- `GET` lembar terbuka untuk pemegang `prepare`/`approve` (Menyimpang 4).
- Uji jalan U17 dan lapis A U16 (keunikan & bersamaan hanya teruji di MongoDB asli).

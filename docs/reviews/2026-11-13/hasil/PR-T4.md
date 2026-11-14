# PR-T4 — Cakupan data, halaman awal, kategori kerja, dan alamat notifikasi sebagai sifat peran

- Commit awal: `4844181` (dikerjakan) · digabung di atas `8b5fdea` (sesudah KF-T6, KP-T3, PR-T3 dan dua perbaikan susulan)        - Serah-terima (a): `6d7dacf`        - Serah-terima (b): `39cdd4b`        - Perbaikan sesudah gate: `db7e563`
- Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PR-06 (beserta butir layar PR-UX-03, PR-UX-04, PR-UX-19, PR-UX-22) — K-47

## Cek ulang "Keadaan sekarang" (di `4844181`)

| # | Hasil |
|---|---|
| 1 | Berlaku. `services/sales_ownership.py:47` `is_owner_locked` (`OWNER_LOCKED_ROLES = ("sales",)`); `role_registry.py:334` `role_in` |
| 2 | Berlaku. `services/customer_service.py:397` `scope_query`, `:407` `can_access_customer` (admin/manajer lolos di `:412` sebelum cek PT) |
| 3 | Berlaku, baris bergeser: `routers/crm.py:256` (`_kpi_scope`, dulu 240); `routers/design_requests.py:46`; `services/location_scope.py:72`. Semua jangkar tabel 1 ditemukan (sales_orders `:423`/`:699`, export_engine `:61`/`:222`/`:228`/`:232`, warehouses `:186`, stock_figures `:223`, analytics_engine `:71`, hr_payroll `:271`, logistics_service `:152`) |
| 4 | Berlaku, bergeser: `routers/crm.py:31`; `services/gl_service.py:3012` (dulu 2909); `services/logistics_service.py:714`; `services/design_request_service.py:148` |
| 5 | Berlaku. `role_registry.py:247`; `frontend/src/config/roles.js:431` |
| 6 | Berlaku, bergeser: `config_catalog_core.py:933` (dulu 921). Kuncinya terhitung "bisa diubah" di Pusat Pengaturan (U02 KF-T1) |
| 7 | Berlaku. `routers/work_desks.py:255`, `services/role_desk_service.py:232`; 404 mencetak id peran (`Peran 'cr_…' memakai meja khususnya sendiri.` — terbukti uji U11 merah) |
| 8 | Berlaku. `services/notification_scope.py:18` |
| 9 | Berlaku. `services/turn_notification_service.py:66` (terbukti U10 merah: peran kustom berdasar Manajer termasuk) |
| 10 | Berlaku. `services/location_scope.py:31` |
| 11 | Berlaku (tidak diubah). `services/inspection_service.py:693` |
| 12 | Berlaku. `services/custom_role_service.py:28`; `role_registry.py:292` |

Catatan tambahan: frontend `navMeta.js` menulis halaman awal Desainer `navId: "designer-hub"`, registry server
`home_nav_id: "design-requests"` (bercabang sebelum unit ini; dipertahankan, lihat Menyimpang 9).

## Pembagian serah-terima

### (a) — sifat dan pembantu ada, pemakai lama belum disentuh (perilaku aplikasi tidak berubah)

Salinan utuh keadaan (a): folder kerja `prt4_a_state/` (di luar repo). Berkas:

| Berkas | Isi |
|---|---|
| `backend/role_registry.py` | Blok `PR-T4`: `TRAIT_KEYS`, `DATA_SCOPES`, `WORK_CATEGORIES` (+ label), `PRT4_BUILTIN_TRAITS`, `BUILTIN_HOME`, `HOME_CHOICES` (14 pilihan, syarat izin), `apply_traits(overrides, matrix)`, `trait_defaults`, `traits_of`, `data_scope_of`, `category_of`, `roles_in_category`, `notify_addresses`, `home_allowed`, `home_choices_for`; `public_list()` + `data_scope`/`kategori_kerja`/`notify_like`; self-test +2 cek |
| `backend/services/data_scope.py` (baru) | `own_scoped`, `owner_ids` (None/milik sendiri/tim), `owns`, versi sinkron `owner_ids_now`/`owns_now` (tembolok tim per permintaan, `prime`), `team_member_ids` (`hr_org_units.head_employee_id` → unit + unit anaknya → `hr_employees.department_id/position_id` → `user_id`), `in_clause`, `assert_may_grant_scope` (403 E3) |
| `backend/services/custom_role_service.py` | `sync_registry` → `apply_traits` sesudah `apply_cross_entity`; jawaban peran + `traits`, `traits_default`, `traits_overridden`, `home_view_fallback`, `home_choices`; `_version` memuat sifat; `clean_traits` (400 berkalimat spesifikasi), `projected_scope`, `_save_traits`; `create_custom`/`update_role` menerima `traits`; `reset_builtin`/`delete_custom` menghapus `role_traits.<rid>`; `_modified_parts` + `"sifat"`; `migrate_role_traits` (`prt4:sifat-peran`) |
| `backend/routers/access_roles.py` | `RoleCreate`/`RolePatch.traits`; penjaga cakupan data (bukan Admin, melebihi cakupan sendiri → 403) |
| `backend/bootstrap.py` | Satu panggilan `migrate_role_traits` sesudah `migrate_role_gates_to_permissions` |
| `frontend/src/features/settings/entities/RoleTraitsPanel.jsx` (baru) | Bagian **Sifat peran**: Data yang terlihat · Halaman awal (pilihan tanpa izin mati + petunjuk) · Kategori kerja (+ kalimat akibat) · Ikut menerima notifikasi untuk; "Mengikuti …" untuk nilai turunan; pembantu `shownTraits`/`traitPayload`/`traitChangeLines` |
| `frontend/src/features/settings/entities/RoleEditorDrawer.jsx` | Panel di kolom kanan di bawah "Akses semua badan usaha"; `traits` di PATCH/POST (hanya kunci yang berubah); baris dialog "{Label}: {lama} → {baru}"; hanya-baca bila peran terkunci |
| `frontend/src/config/roles.js`, `navMeta.js`, `hooks/useSessionSync.js` | Halaman awal SEMUA peran dari `home_view`/`home_nav_id` `GET /api/roles` (nilai tertulis = cadangan; id menu tertulis dipertahankan bila view sama); `homeChangedByServer` mengarahkan peran bawaan yang halaman awalnya diatur Admin |
| Uji | `tests_mem/test_PRT4_sifat_peran.py` (uji (b) bertanda `xfail(strict)` "PR-06 — …" di keadaan (a)), `test_PRT4_sapuan.py` + `data/isi_sebelum_PRT4.json` (dibuat dari kode `4844181`), `test_PRT9_izin_bawaan.py` (`JUMLAH_MIGRASI` 17); jest `features/__tests__/prt4SifatPeran.test.js`, `config/__tests__/prt4HalamanAwal.test.js` |
| Dokumen | `ENTITY_REGISTRY.md` (`permission_settings.role_traits`), `CODEBASE_MAP.md` (generator), `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.2 |

Keadaan (a): `tests_mem` **357 lulus / 2 dilewati / 14 diharapkan gagal** (3 lama + 11 uji (b)); penjaga statik sama
dengan sebelum (lihat Gate); jest 8/8 uji baru.

### (b) — pengalihan pemakai dan pematian daftar nama

| Berkas | Isi |
|---|---|
| `services/sales_ownership.py` | `is_owner_locked` = `own_scoped`; `owner_clause`/`owns` memakai `owner_ids` (cakupan "tim" = + anggota tim); `OWNER_LOCKED_ROLES` dihapus; 403 "Peran Anda hanya membuka…" |
| `services/customer_service.py` | `scope_query`, bagian sales `can_access_customer`, `can_collect_customer`, `collection_worklist` → `own_scoped` + `owner_ids` (`admin`/`manager` di `:415`/`:450` tetap — PR-T6) |
| `routers/crm.py` | Permohonan kredit (daftar/detail), target & insentif (bagian cakupan), `_kpi_scope` (`own_scoped` → dirinya/timnya; selain itu `order.view_sales_kpi`), 4 kueri `users.role` → `roles_in_category("sales")` |
| `routers/crm_omnichannel.py`, `routers/price_approvals.py`, `routers/sample_orders.py` | `own_scoped` + `owner_ids` |
| `routers/customers.py`, `routers/admin.py`, `routers/sales_orders.py`, `services/analytics_facts.py`, `services/hr_payroll_service.py`, `services/product_exclusivity.py`, `dependencies.py` | `category_of(peran) == "sales"` (+ kueri `users.role` → `roles_in_category("sales")`); `current_user` menyiapkan tembolok tim (`data_scope.prime`) |
| `routers/design_requests.py`, `services/export_engine.py` | `_own_only` = `own_scoped`, penerima tugas = `owner_ids`; `FULL_VIEW_ROLES`, `DESIGN_FULL_VIEW` dihapus; daftar putih dataset gudang = kategori `gudang` |
| `routers/logistics.py`, `services/logistics_service.py` | Pagar tulis sopir: `own_scoped` dan pengemudi di luar `owner_ids` → 403 (teks tetap); pengemudi sah = kategori `sopir`; `list_drivers` → `roles_in_category("sopir")` |
| `routers/warehouses.py`, `services/location_scope.py` | `scope=all` = kategori `gudang`/`pengawas` (`MASTER_SCOPE_ROLES` → `MASTER_SCOPE_CATEGORIES`); pagar lokasi = kategori `gudang` (`SCOPED_ROLES` dihapus) |
| `services/stock_figures.py` | Lokasi jualan bawaan = pemegang `order.create` yang bukan `pengawas` (`SALES_ROLES` dihapus) |
| `services/analytics_engine.py` | `sales_only` bila `own_scoped` (lihat Menyimpang 4) |
| `routers/products.py`, `services/sales_force_service.py`, `services/gl_service.py`, `services/design_request_service.py` | Kueri `users.role` → `roles_in_category(...)` (tabel 2) |
| `permissions_config.py`, `access_modules.py` | `order.view_sales_kpi` "Lihat KPI & komisi sales lain" (bawaan Admin, Manajer, Admin Sales, Finance; blok `PR-T4`) |
| `services/custom_role_service.py`, `bootstrap.py` | `migrate_kpi_permission` (`prt4:izin-kpi-sales`, sebelum `sync_permission_modules`): keempat peran + peran kustom berdasar keempatnya, hanya bila memegang `order.view`; `defaults_applied` dicatat |
| `routers/work_desks.py`, `services/role_desk_service.py` | Meja dari kategori kerja (`DESK_BY_CATEGORY`, Admin = meja Admin); `QUEUE_PERMISSIONS` per antrean (antrean tanpa izin dilewati); tanpa kategori → 404 "Peran Anda belum punya meja kerja. Buka menu yang tersedia di samping." |
| `services/notification_scope.py`, `services/turn_notification_service.py`, `services/escalation_service.py` | `audience_roles` = `[peran, "all", *notify_addresses]`; `turn_roles` membuang pemegang berkategori `pengawas` kecuali rule menyebut id-nya atau alamat notifikasinya; eskalasi memakai `notify_addresses(peran)[0]` (`base_or_self` tidak dipakai lagi di sini) |
| `services/design_studio_service.py`, `services/design_gallery_service.py` | Titik tambahan (tidak tercantum): sisi "desainer" pada umpan balik/arahan = kategori `desainer` (4 baris) |
| `config_catalog_core.py` | `role_home.admin/manager/sales/warehouse` → `not_used` "Diatur per peran di Peran & Hak Akses › Halaman awal" |
| Frontend | `config/roles.js` `categoryOf` (kategori dari `GET /api/roles`); `WarehouseMasterView` (`scope=all` = kategori, mencegah 403 baru), `CustomerFormModal`, `LogisticsView`, `AccountLocationScope` memakai `categoryOf`; `SalesForceDashboard` pemilih sales = `can(perms, "order", "view_sales_kpi")`; fixture akses dibangkitkan ulang |
| Uji | `test_PRT4_sifat_peran.py` tanda `xfail` dicabut; `test_PRT9_izin_bawaan.py` (`JUMLAH_MIGRASI` 18, `TAMBAHAN_SESUDAH` `order.view_sales_kpi`); `test_KFT1_izin_pengaturan.py` (`PRT4_TIDAK_DIPAKAI = 4`, U02 −4 dengan alasan); lapis A `tests/test_bp_PRT4_sifat_peran.py` (lulus di MongoDB asli) |
| Dokumen | `memory/PRD.md`, `ENTITY_REGISTRY.md` (dua id migrasi), glosarium (+ "KPI & komisi sales lain"), `CODEBASE_MAP.md` |

Daftar lengkap berkas (b): `prt4_b_files.txt` di folder kerja (di luar repo).

## Uji penerimaan

Merah di kode lama: berkas uji akhir dijalankan pada salinan backend dengan semua berkas non-uji versi `4844181`
(`bukti/PR-T4/merah_kode_lama.log`) → 16 gagal, U13 lulus (memang harus). Merah di keadaan (a)
(`bukti/PR-T4/merah_keadaan_a.log`) → U1, U8, U8b, U14, U15 lulus; 11 uji (b) gagal karena pemakai lama.

| ID | Lapis | Merah di lama | Hasil |
|---|---|---|---|
| U1 | B | ya (`traits` tidak ada) | Lulus — 13 peran bawaan = kolom "Nilai bila tidak disimpan"; `traits_overridden` `[]`; `GET /api/roles` memuat sifat efektif |
| U2 | B | ya (2 → 2) | Lulus — 2 → 0 pelanggan (PT uji tanpa pelanggan seed, lihat Menyimpang 2) |
| U3 | B | ya (`sS` tidak ada di daftar) | Lulus — daftar memuat `sS`; pindah pelanggan 200 |
| U4 | B | ya (3 ≠ 4) | Lulus — baris = akun aktif berkategori sales (seed `sales@` + sA + sB + sS = 4) |
| U5 | B | ya (`kr` tidak ada) | Lulus — `kr` di daftar sopir; tulis posisi pengiriman akun lain → 403 "Pengiriman ini bukan tugas Anda…" |
| U6 | B | ya | Lulus — `sA` 2 pelanggan sesudah nyala ulang; `traits_overridden` ∋ `data_scope`; dikembalikan (null) → 1 |
| U7 | B | ya | Lulus — `sA` 2, `sB` 1 (+ pesanan `sA` 2) |
| U8 | B | ya (200) | Lulus — 400 "Halaman awal “Meja Finance” butuh akses yang belum dimiliki peran ini."; `hr-my-profile` 200; + 400 isian tak dikenal (3 kalimat), halaman awal tersimpan yang izinnya dicabut → Profil Saya + `home_view_fallback` |
| U8b | B | ya | Lulus — Admin terkunci (403); `version` berubah saat sifat berubah |
| U9 | B | ya | Lulus — tidak tampil → tampil |
| U10 | B | ya (termasuk) | Lulus — tidak termasuk; rule yang menyebut Manajer tetap sampai (lihat Menyimpang 3) |
| U11 | B | ya (`cr_` di pesan) | Lulus — 404 kalimat manusia; `gudang` + `wms.view` → "Meja Operator Gudang" |
| U12 | B | ya (izin tidak dikenal) | Lulus — 200 KPI `sA` · 403 · 403; tanpa izin → KPI dirinya |
| U13 | B | tidak (memang sama) | Lulus — kode + jumlah baris 13 peran bawaan (+ akun `sA`) × 9 rute sama dengan `isi_sebelum_PRT4.json`, termasuk Manajer |
| U14 | B | ya (200) | Lulus — 403 "Anda tidak bisa memberi cakupan data lebih luas…"; `milik_sendiri` 200; membuat peran tanpa peran dasar (bawaan "semua") 403, dengan cakupan sendiri 200 |
| U15 | B | ya | Lulus — `milik_sendiri` tersimpan; peran yang juga memegang `order.view` tidak disentuh |
| U16 | B | ya | Lulus — tidak ada `role_in(` di fungsi jangkar tabel 1 (kecuali bagian admin/manajer `can_access_customer` = PR-T6), tidak ada `"role": "sales"/"driver"/"designer"` di jangkar tabel 2, enam konstanta tidak terdefinisi |
| U17 | layar | — | Uji komponen `prt4SifatPeran.test.js` (5) + `prt4HalamanAwal.test.js` (4): baris dialog "Data yang terlihat: Milik sendiri → Milik sendiri dan timnya", isi simpan `traits: {data_scope: "tim"}`. **Uji jalan peramban belum dilakukan** (backend/peramban tidak dijalankan di lingkungan ini) |
| §3.2-4 | B | — | `order.view_sales_kpi`: Tanpa Acuan berizin 200; Manajer Kosong 403 (U12) |
| Lapis A | A | — | `backend/tests/test_bp_PRT4_sifat_peran.py` (migrasi sekali, sifat bawaan lewat API, cakupan tim dengan `$in` pada `sales_team` di MongoDB asli, Meja Saya 404): **lulus** di lingkungan A (MongoDB 7 asli, backend `39cdd4b`, data acuan), bersama lapis A PR-T3 dan KF-T6 (9 lulus) |

`backend/tests_mem`: sebelum **351 lulus / 2 dilewati / 3 xfail** → (a) **357 / 2 / 14 xfail** → (a)+(b) **368 / 2 / 3
xfail** (juga `-n 0`: 368 / 2 / 3). `tests/test_fe03_access_catalog.py --noconftest`: 6 lulus.

Sesudah digabung di atas KF-T6 + KP-T3 + PR-T3: HEAD **379 lulus / 2 / 3** → (a) `6d7dacf` **385 / 2 / 14 xfail** →
(b) `39cdd4b` **396 / 2 / 3**. Jest (`src/config/__tests__` + `src/features/__tests__`) sesudah (b): 400/400 uji lulus;
33 suite gagal dimuat karena `@radix-ui/primitive/is-development` tidak terpasang (kendala lingkungan, sama di HEAD).
Penjaga statik berhitung (`verify_auth_coverage` 28, `verify_ui_standard` 23, `verify_approval_queues` 4,
`audit_i18n_id` 113, `audit_create_modal` 6, `verify_page_tabs` 1, `verify_to_list_bound` 6, `verify_entity_label` 2,
lainnya 0/PASS): HEAD = (a) = (b), baris identik.

## Penggabungan dengan PR-T3

Unit dikerjakan di atas `4844181`; PR-T3 (`36b056e`) masuk lebih dulu dan menyentuh `backend/routers/crm.py` di titik
yang sama. Konflik (tiga arah; basis keadaan (a)):

| Titik | PR-T3 | PR-T4 | Penyelesaian |
|---|---|---|---|
| KPI/komisi (`_kpi_scope`) | `_sees_other_sales` (daftar nama peran pengawas, ditandai "diganti PR-T4") | cakupan data + izin `order.view_sales_kpi` | Bentuk PR-T4 |
| Daftar target & skema insentif | gerbang `order.view` + saringan `_target_sales_filter` (`sales_force.view` atau pengawas → semua; selain itu miliknya) | saringan cakupan data saja | Satu pembantu `_target_sales_query`: `sales_force.view` → semua/yang dipilih; cakupan bukan "semua" → dirinya/timnya; `order.view_sales_kpi` → semua/yang dipilih; selain itu miliknya. `_sees_other_sales` (nama peran) dihapus. Gerbang PR-T3 tetap |

Hasilnya: uji PR-T3 (U2, sapuan U14) dan uji PR-T4 (U2–U7, sapuan U13) hijau bersama. Berkas lain yang juga diubah
sejak `4844181` (`config_catalog_core.py`, `ENTITY_REGISTRY.md`, `memory/PRD.md`) tergabung otomatis; fixture akses
frontend dan `CODEBASE_MAP.md` dibangkitkan ulang.

Di salinan kerja — jest seluruhnya: `4844181` 62 suite lulus / 35 gagal dimuat (`@radix-ui/...`, kendala lingkungan) / 435 uji → sesudah
64 / 35 (suite yang sama) / 444 uji, semua lulus.
Sapuan arsip `docs/audit/konfigurasi-peran-2026-11-13/bukti/t2_roles.py` (17 peran — 13 bawaan + 4 peran kustom uji
arsip, termasuk "Uji Sales Plus" berdasar Sales — × rute GET, seed awal), kode `4844181` vs (a)+(b): 13.464 pasangan
(peran, rute), **0 kode jawaban berbeda, 0 jawaban 500** (`bukti/PR-T4/sapuan_arsip_t2_lama_vs_baru.log`).

## Akun yang mulai ikut daftar pilih dan hitungan

Database yang dijangkau sesi ini (`MONGO_URL` di `backend/.env`, 17 akun) tidak memuat peran kustom sama sekali →
tidak ada akun yang berubah di sana. Untuk data acuan/nyata (H3 — dijalankan pemilik, hanya baca):

```js
ids = db.custom_roles.find({base_role: {$in: ["sales", "driver", "designer"]}}).map(c => c.id)
db.users.find({role: {$in: ids}}, {_id: 0, name: 1, email: 1, role: 1, status: 1})
```

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli), sesudah `restore_demo` (data acuan; tiga skrip seed yang sama seperti
garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`).

| Jalan | Gate | Hasil | Garis dasar | Lebih merah |
|---|---|---|---|---|
| 1 (`39cdd4b`) | `--quick` | 16 FAIL | 16 | 0 |
| 1 (`39cdd4b`) | `--ci` | 45 FAIL | 43 | **2** |
| 2 (`db7e563`) | `--quick` | 16 FAIL | 16 | 0 |
| 2 (`db7e563`) | `--ci` | 43 FAIL | 43 | 0 |

Dua yang lebih merah di jalan 1 dan perbaikannya:
- **POC FASE E-8 G1** — memeriksa himpunan izin pesanan Finance persis; unit ini menambah izin lihat
  `order.view_sales_kpi` (dulu daftar nama peran pengawas yang memuat Finance). Harapan POC ditambah izin itu dengan
  alasan tertulis; yang dijaga E8.2 (Finance tidak membuat/mengubah/mengonfirmasi pesanan) tetap. `db7e563`, POC 65/65.
- **guard:home_kpi** — bukan dari unit ini: perbaikan susulan KF-T6 `8b5fdea` (antrean `journal_proposal`) belum
  punya pasangan hitung-ulang di `verify_home_kpi.EXPECT`. Diperbaiki `241a805` (dicatat di laporan KF-T6).

Penjaga statik di salinan kerja, sebelum → (a) →
(a)+(b) (`bukti/PR-T4/penjaga_*.txt`): `verify_auth_coverage` 28 → 28 → 28 (daftar identik); `verify_ui_standard` 23 →
23 → 23 (daftar identik; berkas baru `RoleTraitsPanel.jsx` tanpa pelanggaran); `audit_i18n_id` 113 → 113 → 113;
`audit_config_wiring` 9 bermasalah + 2 editor ganda → sama (empat `role_home.*` pindah OK → NOT_USED);
`verify_access_catalog_nav`, `verify_money_idempotency`, `verify_custom_modals`, `verify_scope_guard`,
`verify_codebase_map`, `verify_role_label`, `verify_notification_audience`, `verify_escape_layers`, `verify_view_aliases`,
`verify_desk_targets`, `verify_cross_entity` hijau; `role_registry --self-test` hijau (13 peran).

## Menyimpang dari blueprint

1. **Dua id migrasi**: `prt4:sifat-peran` (a) dan `prt4:izin-kpi-sales` (b), supaya instalasi yang menjalankan (a) tetap
   menerima izin KPI saat (b) dipasang. `JUMLAH_MIGRASI` PR-T9 16 → 18.
2. **U2** memakai PT uji `ent_uji_prt4` tanpa pelanggan seed (di `ent_ksc` ada 3 pelanggan seed sehingga "2" tidak
   mungkin); harapan 2 → 0 tidak diubah.
3. **U10**: TURN_MAP tidak memuat aturan berizin `order.deliver`; uji memakai aturan berbentuk sama. "Rule menyebut
   peran" diperluas ke alamat notifikasi peran itu (`notify_addresses`), supaya peran kustom berdasar Manajer tetap
   menerima giliran yang memang ditujukan ke Manajer (persetujuan) — perilaku lama untuk aturan itu.
4. **Asisten** (`analytics_engine`): `sales_only` tetap satu id (dipakai ±15 kueri di `ai_tools`/`ai_actions`); cakupan
   "tim" di asisten = milik sendiri (lebih sempit, tidak pernah lebih luas).
5. **Target & insentif** (`list_targets`/`list_incentives`): hanya bagian cakupan yang diganti (`own_scoped` +
   `owner_ids`); gerbang dan aturan "lihat sales lain" ditetapkan PR-T3 (S3) yang dikerjakan paralel.
6. **Meja Admin** dikenali dari peran terkunci `admin` (`role_desk_service.desk_of`) — tata letak "Admin tetap ditambah
   antrean gudang", bukan keputusan boleh/tidak; antrean tetap disaring izin.
7. Nilai sifat yang dikirim eksplisit disimpan apa adanya walau sama dengan turunan (dipatok; U8 `hr-my-profile`);
   `null` = kembali ke turunan. Editor hanya mengirim kunci yang berubah.
8. `home_choices` memuat juga `requires`/`needs_category` supaya editor menghitung ulang selagi izin diubah.
9. Layar: bila halaman awal dari server sama dengan nilai tertulis, id menu tertulis dipertahankan (Desainer
   `designer-hub`), sehingga sorotan sidebar tidak bergeser.
10. Tambahan di luar tabel: `categoryOf` di layar dan empat layar cermin pagar server (di atas); pemilih sales di dasbor
    Tim Sales memakai `can(order.view_sales_kpi)` — **Admin Sales dan Finance kini melihat pemilih itu** (server sudah
    mengizinkan mereka sejak sebelum unit ini); `_modified_parts` + `"sifat"` (tombol "Kembalikan ke bawaan" ikut
    menghapus sifat tersimpan); pesan 403 pesanan tanpa kata "sales" (Z6); sisi desainer di studio/galeri desain.

## Asumsi

- "Tim" = unit yang dikepalai karyawan pelaku ditambah unit anak langsungnya (jabatan di bawah departemen); anggota =
  karyawan ber-`department_id`/`position_id` di unit itu yang punya `user_id` (semua status).
- Halaman awal turunan tidak pernah jatuh ke Profil Saya (hanya nilai yang DISIMPAN Admin yang diperiksa syaratnya) —
  sama dengan hari ini.
- Data scope tunggal per peran (ASUMSI spesifikasi). Akibat yang perlu diketahui, hanya untuk peran KUSTOM (peran bawaan
  tidak berubah — U13): peran kustom tanpa peran dasar yang memegang `design_request.view` bersama `order.view` atau
  `customer.view`, dan peran kustom berdasar Finance/Gudang/Admin Gudang/Admin Sample/MD Quality/QC yang diberi
  `design_request.view`, kini melihat semua permintaan desain di PT (dulu hanya tugasnya); peran kustom tanpa peran
  dasar ber-`order.create` kini memakai lokasi jualan bawaan; peran kustom berdasar Sales/Sopir/Desainer mulai ikut daftar
  pilih, papan peringkat, komisi, akrual insentif (angka akrual periode berjalan bisa bertambah).
- Peran kustom berdasar Manajer tidak lagi menerima giliran pelaksana (U10, tujuan unit).

## Hambatan lingkungan

- Peramban tidak dijalankan → uji jalan U17 belum (lapis A dan gate dijalankan saat penggabungan).
- Jest: 35 suite gagal dimuat karena `@radix-ui/...` tidak termuat lokal (sama di `4844181`); suite yang memuat
  `CustomerFormModal`/`LogisticsView`/`WarehouseMasterView` termasuk di antaranya → perubahan satu baris di layar itu
  hanya diperiksa lewat uji `categoryOf` dan penjaga statik.

## Yang perlu direview

- Migrasi berjalan otomatis saat server mulai (preseden PR-T9/PR-T2); memasangnya di data nyata = H3.
- Sifat peran disimpan per proses (`TRAIT_OVERRIDES`, pola `CROSS_ENTITY_ROLES`); pada banyak worker, worker lain ikut
  saat `sync_registry` berikutnya (mis. `GET /api/roles` tiap 60 detik). Cakupan data ikut pola ini.
- Titik milik unit lain yang ditemukan dan tidak diubah: `ai_insights.list_for` (alamat `audience_roles` persis peran +
  `!= "admin"`), `logistics_service.PICKUP_CODE_HIDDEN_ROLES`, `location_scope.SUPERVISOR_ROLES` (PR-T7),
  `customer_service` admin/manajer (PR-T6), `ai_tools:365` dan `routers/marketing.py:87` (daftar `users.role` untuk
  asisten/penanda tangan), `roleIs(...)` lain di layar (PR-T7), pengirim `recipient_role` (±96, di luar lingkup).
- Gate penuh, `verify_role_label`/`verify_notification_audience` di gate, dan uji jalan U17 menunggu lingkungan A.

Status: implemented_pending_review.

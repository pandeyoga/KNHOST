# PR-T4 — Jadikan cakupan data, halaman awal, kategori kerja, dan alamat notifikasi sifat peran yang bisa diatur

| | |
|---|---|
| Gelombang | Jalur peran (sejajar dengan gelombang 3–7) |
| Jenis | fitur |
| Risiko | tinggi (dua serah-terima) |
| Prasyarat | PR-T2 |
| Menutup temuan | PR-06 (beserta butir layar PR-UX-03, PR-UX-04, PR-UX-19, PR-UX-22) |
| Keputusan | K-47 |
| Standar | §3.1 (Z2, Z5), §3.2, §3.3 (E3), §6 |
| Lingkungan uji | B |

## Tujuan

Empat hal yang hari ini melekat pada nama peran dasar menjadi isian per peran di layar peran: data siapa yang terlihat,
halaman awal, kategori kerja (siapa yang muncul di daftar pilih sales, sopir, desainer dan ikut hitungan komisi), dan
notifikasi peran mana yang ikut diterima. Peran baru yang dibuat dari nol bisa menjadi "sales yang hanya melihat
pelanggannya"; peran berdasar Sales bisa diperluas melihat timnya. Nilai awal tiap peran sama dengan perilaku hari ini.

## Keadaan sekarang

| # | Fakta | Jangkar | Bukti |
|---|---|---|---|
| 1 | "Hanya miliknya" untuk pesanan ditentukan satu daftar nama peran (`sales`), dicocokkan lewat peran dasar | `backend/services/sales_ownership.py:47` (`is_owner_locked`); `backend/role_registry.py:334` (`role_in`) | [dibaca] |
| 2 | Pelanggan, penagihan, dan status kredit memakai pola yang sama; `admin`/`manager` lolos sebelum cek PT | `backend/services/customer_service.py:397` (`scope_query`); `backend/services/customer_service.py:407` (`can_access_customer`) | [dibaca] |
| 3 | Total 35 pemakaian `role_in` bermakna cakupan data (daftar di "Server" tabel 1) | `backend/routers/crm.py:240` (`_kpi_scope`); `backend/routers/design_requests.py:46` (`_own_only`); `backend/services/location_scope.py:72` (`warehouse_ids_for`) | [dibaca] lampiran B C.1 |
| 4 | Daftar pilih dan hitungan mencari `users.role` persis `"sales"`, `"driver"`, `"designer"`; akun berperan kustom tidak pernah ikut, termasuk akrual insentif ke buku besar | `backend/routers/crm.py:31` (`list_sales_users`); `backend/services/gl_service.py:2909` (`sales_users`); `backend/services/logistics_service.py:714` (`list_drivers`); `backend/services/design_request_service.py:148` (`designer`) | [dibaca] |
| 5 | Halaman awal peran kustom = halaman awal peran dasarnya; tanpa peran dasar = Profil Saya. Tidak bisa diubah | `backend/role_registry.py:247` (`register_custom_roles`); `frontend/src/config/roles.js:431` (`ROLE_HOME_REGISTRY`) | [dibaca] |
| 6 | Empat pengaturan "Halaman awal peran …" terdaftar tetapi tidak dibaca layar | `backend/config_catalog_core.py:921` (`role_home`) | [dibaca] |
| 7 | Meja Saya memakai meja peran dasar tanpa memeriksa izin; peran tanpa meja mendapat 404 yang mencetak id peran | `backend/routers/work_desks.py:255` (`my_desk`); `backend/services/role_desk_service.py:232` (`role_desk`) | [dibaca] |
| 8 | Notifikasi beralamat nama peran; pembaca menerima alamat perannya, `all`, dan peran dasarnya | `backend/services/notification_scope.py:18` (`audience_roles`) | [dibaca] |
| 9 | Pengecualian "pengawas bukan pelaksana giliran" memakai nama persis `admin`/`manager`; peran kustom berdasar Manajer menerima semua giliran pelaksana | `backend/services/turn_notification_service.py:66` (`turn_roles`) | [dibaca] |
| 10 | Peran yang dibatasi lokasi kerja ditulis sebagai daftar nama (`warehouse`) | `backend/services/location_scope.py:31` (`SCOPED_ROLES`) | [dibaca] |
| 11 | Pemilih petugas inspeksi sudah diturunkan dari izin, bukan nama peran (lampiran B PR-UX-04 mencantumkannya; tidak perlu diubah) | `backend/services/inspection_service.py:694` (`dedicated_officer_roles`) | [dibaca] |
| 12 | Pengaturan per peran yang sudah ada (lintas PT, menu tersembunyi) disimpan di `permission_settings` berkunci id peran dan diterapkan ke registry di memori | `backend/services/custom_role_service.py:28` (`sync_registry`); `backend/role_registry.py:292` (`apply_cross_entity`) | [dibaca] |

Tidak ada butir yang dibuktikan uji jalan; PR-06 bertanda [dibaca] di laporan audit.

## Perubahan

### Data

Tempat simpan: `permission_settings` (dokumen `id: "default"`), field baru `role_traits`, berkunci id peran — pola yang
sama dengan `cross_entity` dan `hidden_views` (butir 12), berlaku untuk peran bawaan maupun kustom. `custom_roles`
tidak berubah.

| Field di `role_traits.<id peran>` | Tipe | Arti | Nilai bila tidak disimpan |
|---|---|---|---|
| `data_scope` | `"milik_sendiri"` · `"tim"` · `"semua"` | Dokumen ber-pemilik siapa yang terlihat dan bisa diubah (di dalam PT yang boleh dibuka) | Peran bawaan: `sales`, `driver`, `designer` = `milik_sendiri`; lainnya `semua`. Peran kustom: nilai efektif peran dasarnya; tanpa peran dasar `semua` |
| `home_view` | id layar dari daftar pilihan (lihat "Server" 4) | Halaman awal setelah masuk | Peran bawaan: `home_view` di registry. Peran kustom: milik peran dasar; tanpa peran dasar `hr-my-profile` |
| `kategori_kerja` | `""` · `"sales"` · `"sopir"` · `"desainer"` · `"gudang"` · `"pengawas"` | Jenis pekerjaan pemegang peran (tabel di bawah) | `sales` → `sales`; `driver` → `sopir`; `designer` → `desainer`; `warehouse` → `gudang`; `admin`, `manager` → `pengawas`; peran bawaan lain `""`. Peran kustom: milik peran dasar; tanpa peran dasar `""` |
| `notify_like` | daftar id peran bawaan | Ikut menerima notifikasi yang dialamatkan ke peran-peran ini | Peran bawaan `[]`. Peran kustom `[peran dasar]`; tanpa peran dasar `[]` |

Akibat tiap `kategori_kerja`:

| Nilai | Akibat |
|---|---|
| `sales` | Akun muncul di daftar pilih sales dan boleh menjadi penanggung jawab pelanggan; pesanan buatannya memakai dirinya sebagai `sales_id`; ikut papan peringkat, komisi, dan akrual insentif; dibatasi produk eksklusif dan tahap tersembunyi; Meja Sales |
| `sopir` | Akun bisa ditugaskan sebagai pengemudi; Meja Pengemudi |
| `desainer` | Akun bisa ditugaskan permintaan desain; Meja Desainer |
| `gudang` | Dibatasi lokasi kerja akun bila pengaturan lokasi kerja aktif; boleh meminta daftar seluruh gudang; dataset ekspor gudang; Meja Operator Gudang |
| `pengawas` | Tidak menerima notifikasi giliran pelaksana; boleh meminta daftar seluruh gudang; Meja Manajer |

"Tim" = milik sendiri ditambah milik akun yang karyawannya berada di unit organisasi yang dikepalai karyawan pelaku
(`hr_org_units.head_employee_id`, tautan akun–karyawan `hr_employees.user_id`). Tidak ada peran yang bernilai awal `tim`.

Migrasi sekali (id `"prt4:sifat-peran"` di `permission_settings.migrations_applied`): hanya untuk peran kustom **tanpa
peran dasar** yang memegang `design_request.view` tetapi tidak memegang `order.view` maupun `customer.view` → simpan
`data_scope: "milik_sendiri"` (hari ini peran itu hanya melihat tugas desainnya). Selain itu tidak ada tulisan: semua
nilai awal diturunkan. Laporan unit memuat daftar akun berperan kustom yang berdasar `sales`, `driver`, `designer`
(akun-akun ini mulai ikut daftar pilih dan hitungan).

### Server

**1. Pembantu** — `backend/role_registry.py`: `apply_traits(overrides: Dict[str, Dict]) -> None` (dipanggil
`custom_role_service.sync_registry` setelah `apply_cross_entity`; mengisi `ROLES[rid]` dengan `data_scope`,
`kategori_kerja`, `notify_like`, `home_view`, `home_nav_id` efektif), `data_scope_of(role) -> str`,
`category_of(role) -> str`, `roles_in_category(kategori) -> List[str]`, `notify_addresses(role) -> List[str]`.
`public_list()` menambah keempat sifat. Berkas baru `backend/services/data_scope.py`:

| Fungsi | Perilaku |
|---|---|
| `def own_scoped(actor) -> bool` | Benar bila `data_scope` peran pelaku bukan `semua` |
| `async def owner_ids(actor) -> Optional[List[str]]` | `None` = semua; `[id pelaku]` = milik sendiri; `[id pelaku, id anggota tim…]` = tim |
| `async def owns(actor, owner_id) -> bool` | `owner_ids` kosong (`None`) atau memuat `owner_id` |

**2. Tabel 1 — pengganti 35 `role_in` cakupan data.** Semua klausa `== id pelaku` menjadi `$in: owner_ids(pelaku)`.

| Jangkar | Arti sekarang | Pengganti |
|---|---|---|
| `backend/services/sales_ownership.py:47` (`is_owner_locked`) | pesanan milik sendiri bagi `sales` | `own_scoped(actor)`; `owner_clause` memakai `owner_ids` |
| `backend/services/customer_service.py:400` (`scope_query`), `backend/services/customer_service.py:419` (`can_access_customer`), `backend/services/customer_service.py:438` (`can_collect_customer`), `backend/services/customer_service.py:455` (`collection_worklist`) | pelanggan dan tagihan milik sendiri | `own_scoped` + `owner_ids` |
| `backend/routers/crm.py:126` (`list_credit_overrides`), `backend/routers/crm.py:135` (`get_credit_override`) | permohonan kredit milik sendiri | `own_scoped` + `owner_ids` |
| `backend/routers/crm.py:254` (`_kpi_scope`) | `sales` selalu dirinya; yang boleh melihat sales lain = admin, manager, sales_admin, finance | `own_scoped` → dirinya atau timnya; melihat sales lain butuh izin baru `order.view_sales_kpi` |
| `backend/routers/crm.py:358` (`list_targets`), `backend/routers/crm.py:413` (`list_incentives`) | target dan skema milik sendiri | Lewat `_kpi_scope` (bentuk akhir putusan S3 di PR-T3) |
| `backend/routers/crm_omnichannel.py:76` (`role_in`), `backend/routers/crm_omnichannel.py:132` (`role_in`), `backend/routers/crm_omnichannel.py:202` (`role_in`) | prospek dan interaksi milik sendiri | `own_scoped` + `owner_ids` |
| `backend/routers/customers.py:102` (`assigned_id`) | sales pembuat = penanggung jawab | `category_of(peran) == "sales"` |
| `backend/routers/admin.py:269` (`role_in`) | impor pelanggan: sales pengimpor = pemilik | `category_of(peran) == "sales"` |
| `backend/routers/price_approvals.py:179` (`requested_by`), `backend/routers/price_approvals.py:215` (`role_in`) | pengajuan harga milik sendiri | `own_scoped` + `owner_ids` |
| `backend/routers/sample_orders.py:247` (`assert_may_open`) | batal pesanan sample milik sendiri | `own_scoped` |
| `backend/routers/sales_orders.py:671` (`sales_id`) | `sales_id` = pembuat bila ia sales | `category_of(peran) == "sales"` |
| `backend/routers/sales_orders.py:396` (`roll_pick_sales`) | kebijakan pilih roll untuk sales | `category_of(peran) == "sales"` |
| `backend/routers/design_requests.py:46` (`_own_only`), `backend/services/export_engine.py:232` (`DESIGN_FULL_VIEW`) | selain admin, manager, sales_admin, md hanya tugasnya | `own_scoped(actor)` |
| `backend/routers/logistics.py:34` (`_guard_driver_write`) | sopir hanya menulis pengiriman tugasnya | `own_scoped` dan `driver_user_id` di luar `owner_ids` → 403 (teks tetap) |
| `backend/routers/warehouses.py:187` (`MASTER_SCOPE_ROLES`) | daftar seluruh gudang untuk admin, manager, warehouse | `category_of(peran)` ∈ `gudang`, `pengawas` |
| `backend/services/location_scope.py:72` (`warehouse_ids_for`) | `warehouse` dibatasi lokasi kerja | `category_of(peran) == "gudang"` |
| `backend/services/export_engine.py:61` (`WAREHOUSE_ROLE_DATASETS`) | daftar putih dataset untuk `warehouse` | `category_of(peran) == "gudang"` |
| `backend/services/export_engine.py:222` (`_owner_clause`), `backend/services/export_engine.py:228` (`customer_scope`) | ekspor milik sendiri | `own_scoped` + `owner_ids` |
| `backend/services/analytics_engine.py:62` (`build_scope`) | asisten: hanya pelanggan sendiri | `sales_only` diganti daftar `owner_ids` |
| `backend/services/analytics_facts.py:58` (`creator`), `backend/services/hr_payroll_service.py:245` (`_commission_for`) | kredit penjualan dan komisi hanya untuk akun sales | `category_of(peran akun) == "sales"` |
| `backend/services/logistics_service.py:152` (`driver_user_id`) | pengemudi harus berperan Sopir | `category_of(peran akun) == "sopir"` |
| `backend/services/product_exclusivity.py:58` (`is_restricted_role`), `backend/dependencies.py:68` (`refresh_hidden_stages`) | batas produk untuk sales | `category_of(peran) == "sales"` |
| `backend/services/stock_figures.py:223` (`SALES_ROLES`) | lokasi jualan bawaan untuk sales dan sales_admin | memegang `order.create` dan `category_of(peran) != "pengawas"` |
| `backend/routers/ai_analytics.py:424` (`usage_daily`) | — | Sudah di PR-T2 (`ai.manage`) |

**3. Tabel 2 — kueri `users.role` persis** → `{"role": {"$in": roles_in_category(<kategori>)}}`.

| Jangkar | Kategori |
|---|---|
| `backend/routers/crm.py:31` (`list_sales_users`), `backend/routers/crm.py:71` (`reassign_customer`), `backend/routers/crm.py:369` (`create_target`), `backend/routers/crm.py:424` (`create_incentive`), `backend/routers/customers.py:109` (`assigned_name`), `backend/routers/products.py:240` (`role`), `backend/routers/admin.py:225` (`sales_users`), `backend/routers/admin.py:429` (`users`), `backend/services/sales_force_service.py:454` (`leaderboard`), `backend/services/gl_service.py:2909` (`sales_users`), `backend/services/product_exclusivity.py:138` (`valid_ids`) | `sales` |
| `backend/services/logistics_service.py:714` (`list_drivers`) | `sopir` |
| `backend/services/design_request_service.py:148` (`designer`) | `desainer` |

**4. Halaman awal.** Daftar pilihan (konstanta `HOME_CHOICES` di `role_registry.py`): tiap pilihan `view`, `nav_id`,
`label`, dan syarat.

| `view` | `nav_id` | Label | Syarat pada peran |
|---|---|---|---|
| `hr-my-profile` | `hr-my-profile` | Profil Saya | — |
| `my-desk` | `my-desk` | Meja Saya | `kategori_kerja` tidak kosong |
| `sales-home` | `home` | Performa Saya | `order.view` |
| `manager-home` | `home` | Beranda Manajer | `manager_home.view` |
| `admin-home` | `home` | Beranda Admin | `manager_home.view` |
| `sales-admin-desk` | `sales-admin-desk` | Meja Admin Sales | `order.confirm` |
| `finance-desk` | `finance-desk` | Meja Finance | `payment_variance.decide` |
| `md-desk` | `md-desk` | Meja MD | `design_request.view` |
| `warehouse-admin-desk` | `warehouse-admin-desk` | Meja Admin Gudang | `wms.view` |
| `sample-admin-desk` | `sample-admin-desk` | Meja Admin Sample | `sample_order.view` |
| `operations` | `wms-operations` | Operasi Gudang | `wms.view` |
| `design-requests` | `design-requests` | Permintaan Desain | `design_request.view` |
| `logistics` | `logistics` | Pengiriman | `logistics.view` |
| `inspections` | `quality-hub` | SPK Inspeksi | `inspection.view` |

Bila syarat halaman awal yang tersimpan tidak lagi terpenuhi (izin dicabut), nilai efektifnya `hr-my-profile` dan
jawaban peran memuat `home_view_fallback: true`.

**5. Meja Saya** — `GET /api/desks/me`: jenis meja dari `category_of(peran)` (`pengawas` → antrean manajer; Admin
tetap ditambah antrean gudang). Tiap antrean di `role_desk_service` diberi pasangan izin lihat dokumen yang
ditampilkannya; antrean yang izinnya tidak dipegang dilewati. Kategori kosong → 404 "Peran Anda belum punya meja
kerja. Buka menu yang tersedia di samping."

**6. Notifikasi** — `audience_roles` mengembalikan `[peran, "all", *notify_addresses(peran)]`; `turn_roles` membuang
pemegang izin yang `category_of`-nya `pengawas` (bukan nama persis); rantai eskalasi
(`backend/services/escalation_service.py:36`, `ESCALATION_CHAIN`) memakai `notify_addresses(peran)[0]` sebagai ganti
peran dasar.

**7. Endpoint**

| Metode + path | Izin | Isi permintaan | Jawaban | Galat |
|---|---|---|---|---|
| `PATCH /api/access/roles/{rid}` (sudah ada) | `permission.update` + penjaga PR-T1 | field baru `traits: {data_scope?, home_view?, kategori_kerja?, notify_like?}`; nilai `null` pada sebuah kunci = kembali ke nilai turunan | bentuk peran + `traits` (efektif), `traits_default`, `traits_overridden` (daftar kunci), `home_choices` (`view`, `label`, `allowed`) | 400 "Cakupan data “{nilai}” tidak dikenal." · 400 "Halaman awal “{label}” butuh akses yang belum dimiliki peran ini." · 400 "Kategori kerja “{nilai}” tidak dikenal." · 400 "Alamat notifikasi hanya boleh peran bawaan." · 403 "Anda tidak bisa memberi cakupan data lebih luas dari cakupan peran Anda sendiri." (pelaku bukan Admin dan urutan `milik_sendiri` < `tim` < `semua` dilampaui) |
| `POST /api/access/roles` (sudah ada) | sama | field `traits` yang sama | sama | sama |
| `POST /api/access/roles/{rid}/reset` (sudah ada) | sama | — | `role_traits.<rid>` ikut dihapus | — |
| `GET /api/roles` (sudah ada) | login | — | tiap peran menambah `data_scope`, `kategori_kerja`, `home_view`, `home_nav_id` efektif | — |

Peran Admin terkunci: sifatnya tidak bisa diubah. `_version` peran ikut memuat `traits`.

### Pengaturan

Empat kunci `role_home.admin`, `role_home.manager`, `role_home.sales`, `role_home.warehouse` diberi status tidak
dipakai dengan alasan "Diatur per peran di Peran & Hak Akses › Halaman awal".

### Izin dan peran

| Pasangan | Label aksi | Modul | Penerima bawaan | Dipakai |
|---|---|---|---|---|
| `order.view_sales_kpi` | Lihat KPI & komisi sales lain | `penjualan` | admin, manager, sales_admin, finance; saat migrasi juga peran kustom yang berdasar keempatnya dan memegang `order.view` | `_kpi_scope` |

### Layar

Pengaturan › Perusahaan & Akun › Badan Usaha & Akses › tab Peran & Hak Akses › editor peran
(`frontend/src/features/settings/entities/RoleEditorDrawer.jsx`), bagian baru **Sifat peran** di kolom kanan, di bawah
"Akses semua badan usaha":

| Isian | Label | Pilihan | Keterangan di bawah isian |
|---|---|---|---|
| `data_scope` | **Data yang terlihat** | "Milik sendiri" · "Milik sendiri dan timnya" · "Semua di PT yang boleh dibuka" | "Berlaku untuk pelanggan, pesanan, pengajuan harga, prospek, pengiriman, dan permintaan desain." |
| `home_view` | **Halaman awal** | label dari `home_choices`; pilihan yang `allowed` salah tampil mati dengan petunjuk "Butuh akses yang belum dimiliki peran ini" | "Layar pertama setelah masuk." |
| `kategori_kerja` | **Kategori kerja** | "Tidak ada" · "Sales" · "Sopir" · "Desainer" · "Petugas gudang" · "Pengawas" | kalimat akibat dari tabel "Akibat tiap kategori" untuk pilihan yang aktif |
| `notify_like` | **Ikut menerima notifikasi untuk** | centang banyak, daftar peran bawaan | "Notifikasi giliran tetap mengikuti izin." |

Tiap isian yang nilainya turunan menampilkan "Mengikuti {peran dasar atau bawaan}". Dialog "Periksa sebelum
menyimpan" menambah baris per sifat yang berubah: "{Label}: {lama} → {baru}". Hanya-baca bagi peran terkunci.

`frontend/src/config/roles.js` (`registerDynamicRoles`) dan `frontend/src/config/navMeta.js` (`ROLE_HOME_REGISTRY`):
halaman awal semua peran (bawaan dan kustom) diisi dari `home_view`/`home_nav_id` jawaban `GET /api/roles`; nilai
tertulis menjadi cadangan sebelum jawaban datang.

## Uji penerimaan

Persiapan bersama: peran uji baku `02` §6; `sA`, `sB` = dua akun sales seed/fixture dengan masing-masing satu
pelanggan dan satu pesanan; berkas `backend/tests_mem/data/isi_sebelum_PRT4.json` dibuat pada langkah kerja 1 sebelum
kode diubah (kode jawaban dan jumlah baris 13 peran bawaan untuk rute di U13).

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | basis data baru | `GET /api/access/roles` | `traits` 13 peran bawaan sama dengan kolom "Nilai bila tidak disimpan"; `traits_overridden` = `[]` |
| U2 | B | "Tanpa Acuan" + `customer.view` | `GET /api/customers` sebelum dan sesudah `PATCH` `traits.data_scope = "milik_sendiri"` | 2 pelanggan → 0 pelanggan |
| U3 | B | peran kustom "Sales Senior" (`base_role: "sales"`), akun `sS` | `GET /api/sales-users`; `POST /api/customers/{pelanggan sA}/reassign` ke `sS` oleh admin | daftar memuat `sS`; 200 (sebelum unit: 400 "Salesperson tujuan tidak valid") |
| U4 | B | seperti U3 | `GET /api/sales/leaderboard` oleh admin | jumlah baris = jumlah akun aktif berkategori `sales` (termasuk `sS`) |
| U5 | B | peran kustom "Kurir" tanpa peran dasar: `logistics.view`, `logistics.update`, `traits.kategori_kerja = "sopir"`, `data_scope = "milik_sendiri"`; akun `kr` | `GET /api/logistics/drivers` oleh admin; `kr` menulis ke pengiriman yang ditugaskan ke akun lain | daftar memuat `kr`; 403 "Pengiriman ini bukan tugas Anda…" |
| U6 | B | — | admin: `PATCH /api/access/roles/sales` `{"traits": {"data_scope": "semua"}}` → nyalakan ulang → `GET /api/customers` oleh `sA` | 2 pelanggan; `traits_overridden` memuat `data_scope` |
| U7 | B | unit organisasi berkepala karyawan `sA`, beranggota karyawan `sB`; peran Sales diberi `data_scope = "tim"` | `GET /api/customers` oleh `sA` dan oleh `sB` | `sA`: 2 pelanggan; `sB`: 1 pelanggan |
| U8 | B | "Tanpa Acuan" tanpa `payment_variance.decide` | `PATCH` `traits.home_view = "finance-desk"`; lalu `"hr-my-profile"` | 400 "Halaman awal “Meja Finance” butuh akses…"; 200 dan `GET /api/roles` memuat `home_view: "hr-my-profile"` |
| U9 | B | notifikasi tanpa tautan beralamat `recipient_role: "warehouse"` (fixture) | `GET /api/notifications` oleh akun "Tanpa Acuan" sebelum dan sesudah `traits.notify_like = ["warehouse"]` | tidak tampil → tampil |
| U10 | B | peran kustom berdasar Manajer yang memegang `order.deliver` | Hitung `turn_roles` untuk aturan giliran berizin `order.deliver` | peran itu tidak termasuk (sebelum unit: termasuk) |
| U11 | B | "Tanpa Acuan" kategori kosong; lalu kategori `gudang` + `wms.view` | `GET /api/desks/me` | 404 tanpa teks `cr_`; 200 berjudul "Meja Operator Gudang" |
| U12 | B | "Tanpa Acuan" + `order.view` + `order.view_sales_kpi` | `GET /api/sales/kpi?sales_id={sA}` oleh Tanpa Acuan, Manajer Kosong, Sopir | 200 berisi KPI `sA` · 403 · 403 |
| U13 | B | berkas "sebelum" | 13 peran bawaan: `GET /api/customers`, `/api/sales-orders`, `/api/price-approvals`, `/api/credit-overrides`, `/api/design-requests`, `/api/sales/kpi`, `/api/warehouses?scope=all`, `/api/desks/me`, `/api/notifications` | Kode jawaban dan jumlah baris tiap (peran, rute) sama dengan berkas — termasuk Manajer |
| U14 | B | "Tanpa Acuan" + `permission.update`, `data_scope` perannya `milik_sendiri`, diberi wewenang PR-T1 atas peran X | `PATCH /api/access/roles/{X}` `{"traits": {"data_scope": "semua"}}` | 403 "Anda tidak bisa memberi cakupan data lebih luas…" |
| U15 | B | fixture sisip: peran kustom tanpa peran dasar dengan `design_request.view` saja; hapus id migrasi; nyalakan ulang | `GET /api/access/roles/{peran}` | `traits.data_scope` = `milik_sendiri`, tersimpan |
| U16 | B | — | Cari `role_in(` pada jangkar tabel 1 dan `"role": "sales"`/`"driver"`/`"designer"` pada jangkar tabel 2 | tidak ada |
| U17 | layar (uji jalan) | Login Admin | Buka editor Sales → ubah "Data yang terlihat" ke "Milik sendiri dan timnya" → simpan | Dialog memuat "Data yang terlihat: Milik sendiri → Milik sendiri dan timnya"; setelah simpan isian menampilkan nilai baru |

## Langkah kerja

**Serah-terima (a) — sifat dan pembantu ada, pemakai lama belum disentuh**

1. Berkas "sebelum"; `backend/tests_mem/test_PRT4_sifat_peran.py` (U1–U16). Merah: semua kecuali U13.
2. `apply_traits`, pembantu registry, `services/data_scope.py`, `HOME_CHOICES`; `traits` di `PATCH`/`POST`/`reset`
   dan `GET /api/roles`; migrasi. Hijau: U1, U8, U14, U15.
3. Bagian "Sifat peran" di editor; halaman awal dari server. U17.

**Serah-terima (b) — pengalihan pemakai dan pematian daftar nama**

4. Tabel 1 per berkas (mulai `sales_ownership.py` dan `customer_service.py`); jalankan U13 setelah tiap berkas.
5. Tabel 2; `order.view_sales_kpi` (empat tempat `02` §3.2). Hijau: U2–U7, U12.
6. Meja Saya dan notifikasi. Hijau: U9–U11.
7. Hapus konstanta daftar peran yang tidak lagi dibaca (`OWNER_LOCKED_ROLES`, `FULL_VIEW_ROLES`, `DESIGN_FULL_VIEW`,
   `MASTER_SCOPE_ROLES`, `SCOPED_ROLES`, `SALES_ROLES`); empat kunci `role_home.*`. Hijau: U16.
8. Gate penuh, `role_registry --self-test`, `verify_role_label.py`, `verify_notification_audience.py`; laporan dengan
   SHA (a) dan (b).

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`permission_settings.role_traits`); `CODEBASE_MAP.md` (`services/data_scope.py`);
`memory/PRD.md`; `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("cakupan data", "kategori kerja", "halaman awal").

## Di luar lingkup

- Batas nominal dan jenjang persetujuan per peran → KP-T4. Tampilannya di ringkasan peran → PR-T6.
- Panel "Ringkasan peran" dan pemisahan "Peran dasar" dari "Salin hak akses" → PR-T6.
- Mengalamatkan ulang pengirim notifikasi yang memakai `recipient_role` (±96 titik) ke izin: tidak dikerjakan;
  `notify_like` membuat alamat lama bisa diterima peran mana pun.
- Rekening tingkat grup dan pelanggan lintas PT bagi `admin`/`manager` (`backend/services/customer_service.py:412`) →
  PR-T6 (PR-UX-21).
- Tata letak aplikasi HP dan tur panduan per peran (PR-UX-42) → PR-T7.

## Asumsi dan risiko

- `ASUMSI:` "tim" diartikan lewat kepala unit organisasi SDM karena itu satu-satunya struktur atasan–bawahan di kode;
  tidak ada peran yang memakainya sampai Admin memilihnya.
- `ASUMSI:` satu nilai `data_scope` per peran cukup untuk semua jenis dokumen ber-pemilik; tidak ada keputusan yang
  meminta cakupan berbeda per jenis dokumen.
- `ASUMSI:` peran kustom berdasar `sales`, `driver`, `designer` yang sudah ada mengikuti kategori peran dasarnya, sehingga
  akunnya mulai ikut daftar pilih, papan peringkat, komisi, dan akrual insentif — itulah perbaikan yang diminta
  PR-UX-04. Angka akrual periode berjalan bisa bertambah; daftar akunnya ada di laporan unit.
- `ASUMSI:` syarat izin tiap halaman awal diambil dari gerbang endpoint data layarnya; Meja Admin Sample memakai
  `sample_order.view`.
- `RISIKO:` cakupan melebar karena satu titik terlewat. Penangkal: U13 membandingkan jumlah baris untuk 13 peran.
  Membatalkan (b): kembalikan commit per berkas; `role_traits` yang tersimpan tidak dibaca kode lama.

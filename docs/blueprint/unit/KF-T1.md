# KF-T1 — Izin kelola dan lihat pengaturan benar-benar berfungsi

| | |
|---|---|
| Gelombang | 2 (tinggi yang murah) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | PK-02 |
| Menutup temuan | KF-01, KF-02, KF-03 |
| Keputusan | K-47, K-48, K-49 |
| Standar | §2.1 (`permission`), §3.1 (Z1, Z2, Z3, Z6), §3.2, §6 |
| Lingkungan uji | B |

## Tujuan

Peran yang diberi izin "kelola pengaturan" bisa mengubah pengaturan; wewenang mengubah 48 pengaturan tidak lagi datang
dari nama peran "Manajer" melainkan dari izin yang terlihat dan bisa dicabut di layar peran; dan peran yang tidak
berkepentingan (mis. Sopir) tidak lagi bisa membaca ambang persetujuan, aturan komisi, dan aturan bank.

## Keadaan sekarang

`[dijalankan]` lewat `docs/audit/konfigurasi-peran-2026-11-13/bukti/t3_escalation.py` baris (a), (b), (c), (f1):

| Fakta | Hasil sekarang | Jangkar |
|---|---|---|
| Pemegang `settings.manage` (peran kustom tanpa acuan) menyimpan pengaturan di lapisan grup maupun PT | 403 "… tidak bisa Anda ubah (butuh izin settings.manage)"; `can_edit` salah untuk 232 dari 232 kunci | `backend/routers/config.py:45` (`_may_edit`) — cabang `backend/routers/config.py:66` (`owner_role`) menolak semua selain Admin karena 310 kunci ber-`owner_role` "admin" (`backend/config_registry.py:163` (`owner_role`)) |
| Peran kustom beracuan Manajer dengan semua modul "Tidak ada" menyimpan kunci ber-`roles=("manager",)` | 200 | `backend/routers/config.py:59` (`role_in`); 48 kunci memakai `roles=` (`backend/config_catalog_ops.py:34` (`_MANAGER_TOO`); `backend/config_catalog_rnd.py:15` (`_MANAGER_TOO`); `backend/config_catalog_approval_matrix.py:14` (`_MANAGER_TOO`)) |
| Sopir memanggil `GET /api/config/effective` | 200, 310 kunci | `backend/routers/config.py:184` (`read_effective`), `backend/routers/config.py:160` (`read_registry`), `backend/routers/config.py:204` (`explain`), `backend/routers/config.py:351` (`read_history`), `backend/routers/config.py:402` (`list_simulators`) hanya memanggil `current_user`; satu-satunya batas baca = `backend/routers/config.py:93` (`READ_LIMITS`) untuk peran `md`, dikenali lewat nama peran |

`[dibaca]`:

- Pesan galat menampilkan `x.y`: `backend/routers/config.py:71` (`_perm_error`).
- `GET /api/settings` (`backend/routers/settings.py:26` (`read_settings`)) dan `GET /api/settings/effective`
  (`backend/routers/settings.py:32` (`read_effective_settings`)) hanya butuh login dan mengembalikan **seluruh** isi
  dokumen pengaturan grup, termasuk bagian `commission`, `approval`, `ar`, dan setiap bagian yang pernah ditulis Pusat
  Pengaturan (`bank`, `case`, `payment`, …) karena penulisan diproyeksikan ke dokumen itu
  (`backend/services/config_resolver.py:379` (`_project`)).
- `GET /api/settings/effective` dipanggil semua pengguna saat aplikasi dibuka:
  `frontend/src/hooks/useAppActions.js:190` (`loadAll`). `GET /api/settings` tidak punya pemanggil di `frontend/src`.
- Matriks bawaan: hanya `admin` memegang `settings.manage` (`backend/permissions_config.py:48` (`settings`)); `manager`
  memegang `settings.view` (`backend/permissions_config.py:194` (`settings`)). `GET /api/config/health` sudah dijaga
  `settings.view` (`backend/routers/config.py:367` (`read_health`)).
- Aksi izin baru pada peran bawaan disalin sekali ke matriks tersimpan oleh
  `backend/bootstrap.py:361` (`sync_permission_modules`) dan tidak dihidupkan lagi setelah dicabut Admin
  (`defaults_applied`).
- Menu: tab `settings-cfg-*` tertulis untuk `admin` dan `manager` di
  `frontend/src/config/hubTabs.js:253` (`settings-cfg-sales`), tetapi **peran kustom** mendapatkannya dari modul domain:
  `backend/access_modules.py:23` (`settings-cfg-sales`). Jadi pembaca sah Pusat Pengaturan tidak hanya Admin dan
  Manajer; rancangan di bawah memperhitungkannya.

Pemeriksaan pemakaian `GET /api/settings/effective` oleh layar (seluruh `frontend/src`, 7 titik panggil):

| Titik panggil | Dibuka oleh | Yang dibaca |
|---|---|---|
| `frontend/src/hooks/useAppActions.js:190` (`loadAll`) → `frontend/src/App.js:219` (`showComingSoon`) | semua peran | `ui.show_coming_soon`, `ui.coming_soon_collapsed` |
| → `frontend/src/components/CartPanel.jsx:47` (`defaultTerm`), `frontend/src/features/pos/CheckoutDrawer.jsx:65` (`defaultTerm`), `frontend/src/utils/pricing.js:15` (`computeOrderPreview`) | Sales, Admin Sales | `finance.default_payment_term_code`, `inventory.min_cut_qty`, `sales.allow_item_discount`, `sales.allow_order_discount`, `tax.ppn_rate`, `tax.ppn_mode`, `tax.dpp_nilai_lain`, `tax.is_pkp` (hasil hitung) |
| → `frontend/src/features/sales/SalesPortal.jsx:319` (`allowRollPick`), `frontend/src/features/mobile/MobileAppSwitch.jsx:63` (`allowRollPick`) | Sales | `allocation.roll_pick_sales` |
| `frontend/src/features/admin/po/POCreateForm.jsx:62` (`setTaxCfg`), `frontend/src/features/admin/po/POAmendModal.jsx:74` (`setEffCfg`) | pembuat PO | empat nilai `tax.*` di atas, `purchasing.allow_item_discount`, `purchasing.allow_order_discount` |
| `frontend/src/features/purchasing/VendorBillCreateModal.jsx:56` (`setPriceTol`) | Finance | `purchasing.bill_price_tolerance_percent`, `purchasing.bill_qty_tolerance_percent` |
| `frontend/src/features/sales/ReturnPoliciesView.jsx:75` (`loadMeta`), `frontend/src/features/sales/ReturnAssumptionsPanel.jsx:29` (`customer_window_days`) | pemegang `sales_return.view` | bagian `returns` (5 isian asumsi retur; belum ada di registry) |
| `frontend/src/features/finance/interco/IntercoPaymentSchedule.jsx:25` (`interco_payment`) | pemegang `entity.update` | bagian `interco_payment` (belum ada di registry) |

Tidak ada layar di luar `frontend/src/features/settings/config/` yang memanggil `/api/config/registry|effective|
explain|history|simulators` (pencarian `configApi.` dan `/config/`); pemakai luar hanya menyematkan komponen dari
folder itu (`frontend/src/features/crm/IncentiveRatesEditor.jsx:51` (`useSettingsBrowser`)).

## Perubahan

### Data

`config_registry.E(...)`:

| Perubahan | Rincian |
|---|---|
| Hapus parameter `roles` dan `owner_role` | Field `roles` dan `owner_role` hilang dari entri; `"owner_role"` dicabut dari daftar field di `config_resolver.resolve_group`. Memanggil `E(..., roles=…)` menjadi galat saat impor |
| Tambah `sensitif_baca: Optional[bool] = None` | Nilai entri = nilai eksplisit, bila `None` mengikuti `GROUPS[i]["sensitif_baca"]`, bila tidak ada → `True` |
| `GROUPS` | Tambah `"sensitif_baca": False` pada kelompok `tampilan`; kelompok lain tidak diberi (= sensitif) |

Kunci ber-`sensitif_baca=False` secara eksplisit (14, sesuai tabel pemeriksaan di atas): `finance.default_payment_term_code`,
`inventory.min_cut_qty`, `sales.allow_item_discount`, `sales.allow_order_discount`, `tax.ppn_rate`, `tax.ppn_mode`,
`tax.dpp_nilai_lain`, `allocation.roll_pick_sales`, `purchasing.allow_item_discount`, `purchasing.allow_order_discount`,
`purchasing.bill_price_tolerance_percent`, `purchasing.bill_qty_tolerance_percent`, serta dua `ui.*` lewat kelompoknya.

Penggantian `roles=` pada 48 kunci (daftar = `LAMPIRAN_DAFTAR.md` §G):

| Kunci | `permission` sekarang | `permission` sesudah |
|---|---|---|
| `lot.enforcement_mode`, `lot.require_supplier_lot`, `lot.require_dye_lot`, `lot.alias_mode`, `lot.alias_unique_scope`, `lot.auto_create_on_receiving`, `lot.status_on_receipt`, `lot.number_format` (8) | `settings.manage` | `("inventory", "configure")` — baru |
| `receiving.supplier_dn_mode` (1) | `settings.manage` | `("goods_receipt", "configure")` — baru |
| `makloon.variance_tolerance_pct`, `makloon.auto_claim`, `makloon.claim_approval_roles`, `makloon.contract_mode`, `makloon.default_shrinkage_pct`, `makloon.require_output_product`, `makloon.require_yield_reason` (7) | `settings.manage` | `("makloon", "configure")` — baru |
| 27 kunci `rnd.*`: `lifecycle_enforcement`, `new_product_default_lifecycle`, `variant_axes_default`, `variant_axes_optional`, `spec_approval_roles`, `sample_decision_roles`, `max_rounds`, `round_sla_days`, `require_attachment_on_round`, `require_design_for_proofing`, `require_stage_chain`, `labdip_max_colors`, `design_code_pattern`, `design_code_seq_digits`, `design_prefix_motif`, `design_prefix_pattern`, `design_prefix_artwork`, `design_acc_min_score`, `sla_escalate_admin_days`, `kpi_weight_on_time`, `kpi_weight_score`, `kpi_weight_acc`, `kpi_weight_design`, `kpi_penalty_rework`, `kpi_penalty_overdue`, `auto_contract_on_decide`, `sample_material_from_stock` | `rnd.manage` | tetap `("rnd", "manage")` — cukup cabut `roles=` |
| `approval.matrix_enforcement`, `approval.matrix_scope`, `approval.matrix_effective_from`, `approval.matrix_sod`, `approval.po_custom_direksi_min` (5) | `rnd.manage` | tetap `("rnd", "manage")` — cukup cabut `roles=` |

Migrasi matriks, sekali jalan, di `backend/bootstrap.py` sesudah `sync_permission_modules`, ditandai
`system_settings{scope: "__migrations__"}.kft1_izin_pengaturan` (pola `_migrate_as01_value_approval`):

1. Untuk tiap dokumen `custom_roles` ber-`base_role == "manager"`: pada `permission_settings.matrix[<id peran>]`
   tambahkan aksi `rnd.manage`, `inventory.configure`, `goods_receipt.configure`, `makloon.configure` bila belum ada
   (hanya aksi itu; `view` tidak ditambahkan).
2. Tulis penanda. Jalan kedua tidak mengubah apa pun, juga bila Admin sudah mencabut izinnya.

Peran bawaan `manager` dan `admin` memperoleh tiga aksi baru lewat `DEFAULT_PERMISSIONS` (lihat "Izin dan peran");
`manager` dan `md` sudah memegang `rnd.manage`. Hasilnya perilaku hari ini tidak berubah bagi peran yang ada (K-47).

### Server

`backend/routers/config.py`:

| Fungsi | Aturan baru |
|---|---|
| `_may_edit(entry, user, perms)` | `True` bila `user.role == "admin"`; selain itu `True` bila dan hanya bila `_may(perms, *entry["permission"])`. Tidak ada cabang `roles` maupun `owner_role` |
| `_may_read(entry, user, perms)` — baru | `True` bila Admin, atau `_may(perms, "settings", "view")`, atau `_may_edit(entry, user, perms)` — yang boleh mengubah sebuah kunci boleh membacanya |
| `READ_LIMITS`, `_read_limit`, `_visible` | Dihapus; diganti `_may_read`. Hasil untuk peran `md` sama persis dengan hari ini: 32 kunci berizin `rnd.manage` (keputusan pemilik 26 Okt tentang batas baca MD tetap berlaku) |
| `_perm_error(entry)` | Teks Z6 (di bawah); nama modul dari `access_modules.MODULE_CATALOG` pemilik `entry["permission"][0]` |

| Endpoint | Izin | Perilaku |
|---|---|---|
| `GET /api/config/registry`, `GET /api/config/effective` | login + ada minimal satu entri yang lolos `_may_read` | Hanya entri yang lolos `_may_read`; `groups` dihitung dari entri itu. Tidak ada satu pun → 403 (pesan B1). Dengan `group=` yang tak punya entri terbaca → 403 (B2) |
| `GET /api/config/explain?key=`, `GET /api/config/history?key=` | `_may_read` untuk kunci itu | 403 (B2) bila tidak |
| `GET /api/config/history` tanpa `key` | seperti `registry` | Baris disaring `_may_read` |
| `GET /api/config/simulators` | seperti `registry` | Hanya simulator yang semua `needs`-nya terbaca |
| `POST /api/config/simulate` | semua `needs` lolos `_may_read` | 403 (B2) bila tidak |
| `PUT /api/config/values`, `POST …/values/reset`, `POST …/values/clear` | `_may_edit` | 403 (pesan U) bila tidak; pemeriksaan lapisan `_assert_scope_write` tetap |
| `GET /api/settings` | `require_permission(request, "settings", "view")` | 403 (B1) |
| `GET /api/settings/effective` | login | Pemegang `settings.view`: utuh seperti sekarang. Selain itu: disaring `config_service.saring_bagi_pembaca(doc)` |

`caps` pada jawaban `registry` menjadi: `settings_manage`, `settings_view` (baru), `impact_apply`, `editable_count`,
`global_write`, `read_scope` (= label kelompok yang terbaca dipisah ", " bila pelaku tidak memegang `settings.view`;
"" bila memegang).

`saring_bagi_pembaca(doc: dict) -> dict` (baru, `backend/services/config_service.py`): telusuri tiap daun; pertahankan
daun bila `config_registry.covers(path)` mengembalikan entri ber-`sensitif_baca == False`, atau bila jalurnya termasuk
`BUKA_SEMENTARA = ("scope", "tax.is_pkp", "returns", "interco_payment")`; buang selebihnya dan buang wadah yang
menjadi kosong. `BUKA_SEMENTARA` untuk `returns` dan `interco_payment` dicabut unit KF-T2 saat kunci itu masuk registry.

Teks galat (403):

| Kode | Keadaan | Pesan |
|---|---|---|
| U | Tidak berwenang mengubah | "Anda belum punya akses untuk mengubah pengaturan “{label}”. Minta Admin menambahkan akses '{nama modul}'." |
| B1 | Tidak boleh membaca Pusat Pengaturan | "Anda belum punya akses untuk melihat pengaturan. Minta Admin menambahkan akses 'Pengaturan, Pengguna & Hak Akses'." |
| B2 | Kunci/kelompok di luar yang terbaca | "Anda belum punya akses untuk melihat pengaturan “{label kunci atau kelompok}”. Minta Admin menambahkan akses '{nama modul}'." |

### Pengaturan

Tidak ada kunci baru.

### Izin dan peran

| Pasangan baru | Peran bawaan | Modul akses (sudah memuat sumber dayanya) | Diperiksa oleh |
|---|---|---|---|
| `inventory.configure` | `admin`, `manager` | Stok & Persediaan (`inventory`) | `_may_edit` untuk 8 kunci `lot.*` |
| `goods_receipt.configure` | `admin`, `manager` | Operasi Gudang (`warehouse_ops`) | `_may_edit` untuk `receiving.supplier_dn_mode` |
| `makloon.configure` | `admin`, `manager` | Pemasok & Makloon (`supplier`) | `_may_edit` untuk 7 kunci `makloon.*` |

`settings.view` dan `settings.manage` tidak berubah pemegangnya (K-48: bawaan hanya Admin yang mengelola).

`access_modules.VIEW_RESOURCE_OVERRIDES` bertambah supaya tab pengaturan tidak tampil bagi peran yang pasti tidak bisa
membaca isinya (saringan menu hanya mengenal "memegang aksi apa pun"; peran yang lolos saringan tetapi tidak boleh
membaca mendapat keadaan kosong berpesan B1): `settings-config`, `settings-cfg-finance`, `settings-cfg-documents`, `settings-cfg-notify`,
`settings-cfg-system` → `["settings"]`; `settings-cfg-approval`, `settings-cfg-rnd` → `["settings", "rnd"]`;
`settings-cfg-sales` → `["settings", "sales_return"]`; `settings-cfg-hr` → `["settings", "hr"]`;
`settings-cfg-purchasing` → `["settings", "makloon"]`; `settings-cfg-warehouse` → `["settings", "uom", "inventory",
"goods_receipt"]`. Satu tes membandingkan daftar ini dengan himpunan `permission[0]` kunci tiap kelompok menurut
`frontend/src/features/settings/config/configGroupViews.js`.

### Layar

- `frontend/src/features/settings/config/SettingsHub.jsx` (`useSettingsBrowser`): bila `registry` atau `effective`
  dijawab 403, tampilkan keadaan kosong (bukan galat merah) berisi pesan dari server dan tanpa tombol "Coba lagi".
- `frontend/src/features/settings/config/SettingsScopeBar.jsx`: pemberitahuan untuk pembaca terbatas menjadi
  "Anda hanya melihat pengaturan **{caps.read_scope}** — yaitu aturan yang termasuk wewenang peran Anda. Yang bisa Anda
  ubah di daftar ini: {n} dari {m} pengaturan." Kalimat lama "Anda dapat melihat semua aturan…" hanya untuk pemegang
  `settings.view` tanpa `settings.manage`.
- Tidak ada perubahan di layar POS, PO, tagihan pemasok, kebijakan retur, dan jadwal bayar antar-PT: semua nilai yang
  mereka baca tetap dikirim (tabel pemeriksaan).

## Uji penerimaan

Fixture: peran **Tanpa Acuan**, **Manajer Kosong**, **Sopir** (`02` §6), dibuat sesudah proses awal; akun `mgr`
(manager seed), `adm` (admin seed), `md` dan `sls` (akun berperan `md` dan `sales` hasil salin akun seed). PT `ent_ksc`.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | Tanpa Acuan = `{"settings": ["view", "manage"]}`, PT asal `ent_ksc` | `PUT /api/config/values` `sales.allow_partial_shipment=false`, `scope_type: "entity"`, `scope_id: "ent_ksc"` | 200; `value_of(key, {"entity_id": "ent_ksc"})` = `False` |
| U2 | B | seperti U1 | `GET /api/config/effective` | `can_edit == true` pada 232 kunci (kunci aktif berizin `settings.manage` sesudah 16 kunci dipindah: 251 − 16 − 3 tidak dipakai) |
| U3 | B | seperti U1 | `PUT` kunci yang sama dengan `scope_type: "global"` | 403 berisi "hanya dapat diubah peran lintas badan usaha" (aturan lapisan tetap) |
| U4 | B | Tanpa Acuan = `{"settings": ["view"]}` | `PUT` seperti U1; `GET /api/config/registry` | `PUT` 403 pesan U menyebut 'Pengaturan, Pengguna & Hak Akses' dan tidak memuat "settings.manage"; `GET` 200 dengan `total == 310` |
| U5 | B | Manajer Kosong | `PUT /api/config/values` `lot.require_dye_lot=false` lapisan PT; `GET /api/config/registry` | Keduanya 403; nilai kunci tidak berubah |
| U6 | B | — | `mgr`: `PUT` `lot.require_dye_lot=false` dan `rnd.max_rounds` (nilai + 1), `scope_type: "global"` | Keduanya 200 (Manajer bawaan tidak kehilangan wewenang) |
| U7 | B | Tanpa Acuan = `{"inventory": ["view", "configure"]}` | `PUT` `lot.require_dye_lot` lapisan PT; `PUT` `makloon.auto_claim` lapisan PT; `GET /api/config/registry`; `GET /api/config/effective?group=pajak` | 200; 403; 200 dengan `total == 8` dan semua kunci berawalan `lot.`; 403 pesan B2 |
| U8 | B | Sisipkan langsung satu `custom_roles` ber-`base_role: "manager"` + baris matriks kosong, hapus penanda migrasi | Jalankan fungsi migrasi dua kali; lalu Admin mencabut `inventory.configure` peran itu; jalankan lagi | Sesudah jalan pertama matriks peran memuat 4 aksi baru; jalan kedua tidak mengubah dokumen; sesudah dicabut tidak kembali |
| U9 | B | Sopir | `GET` `/api/config/registry`, `/effective`, `/explain?key=tax.ppn_rate`, `/history`, `/simulators`, `/health` | Enam-enamnya 403; lima pertama berpesan B1/B2 |
| U10 | B | `md` | `GET /api/config/registry`; `PUT` `rnd.max_rounds` lapisan PT; `GET /api/config/explain?key=bank.auto_match_min_score` | 200 dengan `total == 32`; 200; 403 |
| U11 | B | `adm`: `PUT` `bank.auto_match_min_score=85` global | Sopir dan `adm`: `GET /api/settings/effective` | Sopir: ada `ui.show_coming_soon`, `tax.ppn_rate`, `tax.is_pkp`, `finance.default_payment_term_code`; tidak ada kunci tingkat atas `bank`, `commission`, `approval`, `ar`, `role_home`. `adm`: `bank.auto_match_min_score == 85` dan `commission` ada |
| U12 | B | — | Sopir dan `mgr`: `GET /api/settings` | 403 pesan B1; 200 |
| U13 | B | — | Impor registry; periksa tiap entri | Tidak ada entri memuat `roles` atau `owner_role`; 14 kunci di daftar ber-`sensitif_baca == False`; `E("x.y", …, roles=("manager",))` melempar `TypeError` |
| U14 | B | — | Bandingkan `VIEW_RESOURCE_OVERRIDES` dengan himpunan hitung | Sama untuk 11 id layar |
| U15 | layar (uji jalan) | Login `sls` | Buka POS, isi keranjang, buka checkout | Ringkasan PPN, pilihan termin bawaan, dan batas potong minimum tampil seperti sebelum unit ini |
| U16 | layar (uji jalan) | Login akun berperan U7 | Pengaturan › Gudang & Mutu › Aturan Gudang & Mutu | Hanya 8 kartu lot, bisa disimpan; pemberitahuan menyebut "Lot & Ketertelusuran"; tab "Semua pengaturan" tidak tampil |

Sesudah unit selesai `t3_escalation.py` harus mencetak: (a) lapisan PT 200 dan `can_edit=true … 232 dari 232`; (c) 403;
(f1) 403. `t1_config.py` tetap 287/287 dan 242/242.

## Langkah kerja

1. `backend/tests_mem/test_KFT1_izin_pengaturan.py`: U1–U14; merah kecuali U3, U6.
2. Registry: hapus `roles`/`owner_role`, tambah `sensitif_baca`, ubah `permission` 16 kunci; tiga aksi baru di
   `permissions_config.py`; migrasi matriks.
3. `_may_edit`, `_may_read`, pesan galat, penjagaan endpoint baca di `routers/config.py`.
4. `saring_bagi_pembaca` dan dua endpoint `routers/settings.py`.
5. `VIEW_RESOURCE_OVERRIDES`; layar; uji jalan U15–U16.
6. Gate; laporan.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (penanda migrasi `kft1_izin_pengaturan`); `memory/PRD.md` (aturan baca dan ubah pengaturan);
komentar kepala `backend/config_registry.py` dan `backend/routers/config.py`.

## Di luar lingkup

- Memecah modul "Pengaturan, Pengguna & Hak Akses" → PR-T5. Pesan 403 umum `Permission ditolak: x.y` → PR-T6.
- Jalur tulis lama `PUT /api/settings` dan dua layar yang memakainya → KF-T2.
- Mengganti `role_in`/`require_role` di luar Pusat Pengaturan → PR-T2.
- Layar lapisan pelanggan/barang → KF-T5. Bahasa kartu → KF-T4.

## Asumsi dan risiko

- `ASUMSI:` tanpa `settings.view`, seseorang hanya membaca kunci yang boleh ia ubah. Ini bentuk umum dari batas baca
  MD yang sudah berlaku (`READ_LIMITS`): MD tetap membaca tepat 32 kunci R&D. Pemegang "Lihat saja" sebuah modul domain
  tidak membaca pengaturan modul itu; Admin memberinya `settings.view` bila perlu.
- `ASUMSI:` peran kustom beracuan Manajer yang sudah ada diberi empat aksi tanpa `view`; menu R&D tidak ikut terbuka.
- `ASUMSI:` peran kustom yang hari ini membaca tab pengaturan domain dalam keadaan terkunci (mis. hanya `order.view`)
  kini melihat pesan B1 di tab itu, sesuai K-49. Laporan unit memuat daftar peran kustom di data acuan yang terkena.
- `RISIKO:` layar yang membaca bagian pengaturan di luar tabel pemeriksaan menerima `undefined`. Penangkal: U11
  menegaskan isi minimum; pencarian `settings/effective` diulang di langkah 2 `00` §2. Membatalkan: kembalikan
  `saring_bagi_pembaca` menjadi fungsi identitas.

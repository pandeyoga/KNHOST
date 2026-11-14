# PR-T5 — Rapikan katalog izin dan pecah modul "Pengaturan, Pengguna & Hak Akses"

| | |
|---|---|
| Gelombang | Jalur peran (sejajar dengan gelombang 3–7) |
| Jenis | perbaikan |
| Risiko | sedang |
| Prasyarat | PR-T2 |
| Menutup temuan | PR-07, PR-08 (beserta butir layar PR-UX-12 … PR-UX-16, PR-UX-18, PR-UX-28, PR-UX-30) |
| Keputusan | K-47, K-50 |
| Standar | §3.2, §4 (L1, L2, L5), §6 |
| Lingkungan uji | B |

## Tujuan

Setiap tombol izin di layar peran berakibat nyata di server; yang tidak, hilang. "Kelola akun" bisa diberikan tanpa
ikut memberi "ubah peran", "kelola PT", "ubah pengaturan", dan "penjadwal". Tingkat akses tampil sebagaimana adanya
("Sebagian (7 dari 13 aksi)"), tombol tingkat yang tidak berlaku tidak ditawarkan, dan nama halaman serta aksi sama di
editor, pesan penolakan, dan jejak audit.

## Keadaan sekarang

| # | Fakta | Jangkar | Bukti |
|---|---|---|---|
| 1 | Matriks bawaan memuat 381 pasangan izin pada 79 sumber daya. Pencarian pemeriksa literal di `backend/` tidak menemukan 42 pasangan; 20 di antaranya diperiksa lewat nama aksi yang dirakit atau dikirim sebagai variabel, 22 tidak diperiksa sama sekali (laporan audit menyebut 41; lampiran B Lampiran D ±22) | `backend/permissions_config.py:1` (`DEFAULT_PERMISSIONS`); `backend/routers/goods_receipts.py:24` (`_act`); `backend/routers/rnd.py:115` (`_require_typed`) | [statik] hitungan ulang saat menyusun unit ini; dasar: `docs/audit/konfigurasi-peran-2026-11-13/bukti/inv_endpoints.py` |
| 2 | Tombol "Tambah Stok" tampil menurut `inventory.create`, sedangkan endpoint-nya memeriksa `product.create` | `frontend/src/features/wms/InventoryStockView.jsx:374` (`can`); `backend/routers/inventory.py:633` (`add_initial_stock`) | [dibaca] |
| 3 | Endpoint laporan memeriksa `order.view`, `product.view`, `warehouse.view`; `reports.view` tidak diperiksa di mana pun | `backend/routers/reporting.py:286` (`require_permission`) | [dibaca] |
| 4 | Satu modul menyatukan akun, peran, pengaturan, PT, dan penjadwal dalam satu tombol tingkat | `backend/access_modules.py:200` (`admin`) | [dibaca] |
| 5 | Modul "Profil POV Sales Komersial" tidak dibaca kode mana pun; pembaca visibilitas sengaja mengabaikannya | `backend/access_modules.py:196` (`sales_profile`); `backend/services/field_visibility.py:45` (`hidden_for`); `backend/permissions_config.py:683` (`EXTRA_ACTIONS`) | [dibaca] |
| 6 | Tingkat "Lihat saja" membuang sumber daya yang tidak punya aksi lihat; modul yang semua sumber dayanya demikian tidak berubah apa pun pada "Lihat saja" | `backend/access_modules.py:239` (`apply_levels`); `backend/access_modules.py:192` (`field_visibility`) | [dibaca] |
| 7 | Apa pun selain "hanya lihat" dibaca "Kelola penuh" dengan tanda `partial`; kartu peran menghitung yang sebagian sebagai "kelola" | `backend/access_modules.py:221` (`level_of`); `frontend/src/features/settings/entities/RoleModuleRow.jsx:52` (`partial`); `frontend/src/features/settings/entities/RoleAccessPanel.jsx:41` (`kelola`) | [dibaca] |
| 8 | Dua kamus label: editor memakai kamus server, pesan penolakan dan jejak audit memakai kamus layar; keduanya berbeda untuk 47 halaman dan 46 aksi | `backend/access_modules.py:275` (`RESOURCE_LABEL`); `backend/access_modules.py:305` (`ACTION_LABEL`); `frontend/src/config/auditLabels.js:4` (`MODULE_LABEL`) | [dibaca] lampiran B Lampiran E |
| 9 | Hanya satu modul bertanda sensitif; tanda itu per modul, bukan per aksi | `backend/access_modules.py:210` (`sensitive`); `frontend/src/features/settings/entities/RoleModuleRow.jsx:21` (`sensitive`) | [dibaca] |
| 10 | Sepuluh menu dan delapan tab tidak dimiliki modul mana pun, sehingga hanya ikut peran dasar | `frontend/src/config/hubTabs.js:36` (`customers-master`); `frontend/src/config/hubTabs.js:261` (`settings-receiving-ocr`); `backend/access_modules.py:389` (`all_nav_ids`) | [dibaca] lampiran B C.2 |
| 11 | Penyaring menu hanya menguji "ada aksi apa pun pada sumber daya", belum per aksi | `backend/access_modules.py:368` (`VIEW_RESOURCE_OVERRIDES`); `frontend/src/config/roles.js:362` (`accessBlocks`) | [dibaca] |

## Perubahan

### Data

Migrasi sekali (id `"prt5:katalog"` di `permission_settings.migrations_applied`), pada `matrix` semua peran (bawaan
dan kustom) dan pada `defaults_applied`: hapus pasangan berputusan "Hapus" di tabel 1 dan seluruh sumber daya
`sales_pov`. `custom_roles.levels` dihitung ulang dengan id modul baru. Tidak ada izin yang ditambahkan.

### Server

**Tabel 1 — pasangan yang tidak punya pemeriksa literal (42).**

| Pasangan | Layar memakainya? | Putusan |
|---|---|---|
| `esign.manage` | tidak | Hapus |
| `finance_case.admin` | tidak | Hapus |
| `interco.update` | tidak | Hapus (ubah transaksi dijaga `interco.create`) |
| `inventory.create` | ya, tombol "Tambah Stok" | Hapus; tombol memakai `product.create`, izin yang memang diperiksa endpoint-nya |
| `order.print`, `tax_invoice.print`, `template.print` | tidak | Hapus (cetak dijaga `document.print`) |
| `template.import`, `template.export`, `uom.import`, `uom.export` | tidak | Hapus |
| `transfer.complete` | tidak | Hapus |
| `reports.export` | tidak | Hapus (unduhan dijaga `data_export.export`) |
| `sales_pov.commercial` | tidak | Hapus beserta sumber daya dan modulnya |
| `reports.view` | ya, menu Analitik › Ringkasan | Sambungkan: `GET /api/reports/summary`, `/api/reports/warehouse-utilization`, `/api/reports/stock-aging`, `/api/reports/top-customers` memeriksa `reports.view` sebagai pernyataan pertama (pemanggilnya hanya layar Ringkasan). `/api/reports/reservation-funnel` dan `/api/reports/order-velocity` tetap `order.view` (dipakai layar Pesanan) |
| `md_quality.view` | ya, menu Kualitas | Sambungkan: empat endpoint baca inspeksi (`backend/routers/inspections.py:57`, `backend/routers/inspections.py:124`, `backend/routers/inspections.py:155`, `backend/routers/inspections.py:204`) memakai `require_any_permission` atas `inspection.view`, `md_quality.view`, `qc.view` |
| `marketing.approve` | tidak | Disambungkan PR-T2 |
| `purchase_order.approve`, `purchase_order.reject`, `vendor_bill.reject`, `landed_cost.approve`, `landed_cost.reject` | sebagian (`ApprovalDecisionModal.jsx`) | Disambungkan KP-T4 |
| `field_visibility.grade`, `.lot`, `.origin` | — | Tetap — diperiksa `backend/services/field_visibility.py:45` (`hidden_for`) |
| `goods_receipt.create`, `.count`, `.close` | — | Tetap — diperiksa lewat `backend/routers/goods_receipts.py:24` (`_act`) |
| `od_fulfillment.view`, `.choose_route`, `.override_default`, `.cancel` | — | Tetap — diperiksa `backend/services/special_order_fulfillment.py:213` (`has_permission`) |
| `rnd.assess_labdip`, `.assess_handfeel`, `.assess_proofing`, `.decide_labdip`, `.decide_handfeel`, `.decide_proofing` | — | Tetap — diperiksa `backend/routers/rnd.py:115` (`_require_typed`) |
| `sales_return.split_cutloss` | — | Tetap — diperiksa `backend/routers/sales_return_exceptions.py:232` (`split_cutloss`) |
| `finance_amendment.approve`, `order.approve_price_edit` | — | Tetap — diperiksa lewat `approval_permission` amandemen (`backend/services/amendment_service.py:729`) |
| `period.backdate` | — | Tetap — diperiksa `backend/routers/gl.py:155` (`can_backdate`) |

Jumlah: hapus 14 · sambung di unit ini 2 · disambung unit lain 6 · tetap 20.

**Tabel 2 — modul "Pengaturan, Pengguna & Hak Akses" (`admin`) dipecah menjadi lima.**

| id | Label | Sumber daya | Menu (`nav`) | Sensitif |
|---|---|---|---|---|
| `accounts` | Akun Pengguna | `user` | `settings-hub`, `settings-company`, `entities-access` | ya |
| `roles` | Peran & Hak Akses | `permission` | `settings-hub`, `settings-company`, `entities-access` | ya |
| `entities` | Badan Usaha (PT) | `entity` | `settings-hub`, `settings-company`, `entities-access`, `settings-masters`, `entity-masters` | ya |
| `settings` | Pusat Pengaturan | `settings` | `settings-hub`, `settings-system`, `settings-config`, `settings-cfg-system`, `admin`, `settings-approval`, `approval-rules`, `settings-cfg-approval`, `settings-masters`, `domain-registry`, `settings-cfg-documents`, `settings-documents` (koreksi PR-T5: induk tab dokumen), `settings-notify`, `settings-cfg-notify` | ya |
| `scheduler` | Penjadwal & Notifikasi Otomatis | `scheduler` | `settings-hub`, `settings-notify`, `scheduler` | tidak |

- `pdf-templates` dan `settings-documents` pindah ke `nav` modul `documents` (pemilik sumber daya `pdf_template`).
  `settings-devices` tetap di modul `warehouse_ops`, `hr`, dan `devices` (PR-T2).
- `apply_levels` menerima id lama `admin` sebagai alias kelima modul baru (konstanta `MODULE_ALIASES`), supaya
  permintaan dan uji yang masih mengirim `{"admin": …}` tetap bekerja; jawaban selalu memakai id baru.
- Deskripsi modul `accounts`: "Membuat, mengubah, menonaktifkan akun dan mereset sandi." Modul `roles`: "Mengatur hak
  akses peran. Hati-hati: bisa mengubah hak akses orang lain."

**Modul tanpa efek dan tombol tingkat yang tidak berlaku**

- Modul `sales_profile` dan sumber daya `sales_pov` dihapus (`MODULE_CATALOG`, `EXTRA_ACTIONS`, `RESOURCE_LABEL`,
  `ACTION_LABEL["commercial"]`).
- Modul `field_visibility` pindah ke grup "Gudang", label "Melihat grade, nomor lot & asal barang".
- `public_catalog()` menambah per modul `levels_available`: `["none", "manage"]` bila tidak ada sumber daya ber-aksi
  `view` (modul sakelar: `field_visibility`); `["none", "view"]` bila satu-satunya aksi semua sumber dayanya `view`
  (`approval`, `manager_home`, `costing`); selain itu ketiganya. `apply_levels` menolak tingkat di luar daftar itu
  dengan 400 "Tingkat “{label}” tidak berlaku untuk modul “{label modul}”."
- `public_catalog()` menambah per modul `view_excludes`: label sumber daya yang dibuang pada "Lihat saja" karena tidak
  punya aksi lihat (hari ini: Harga Pesanan Khusus, Periode & Tutup Buku, Amandemen Keuangan).
- `level_of` menambah `held` dan `total` (jumlah aksi dipegang dan jumlah aksi penuh modul). Nilai `level` tetap
  `none`/`view`/`manage`. `LEVEL_LABEL["manage"]` menjadi "Semua aksi".

**Aksi berisiko per aksi.** Konstanta baru `SENSITIVE_ACTIONS: Dict[Tuple[str, str], str]` di
`backend/access_modules.py`; nilai = kalimat akibat. `public_catalog()` menambah per modul
`sensitive_actions: {<sumber daya>: {<aksi>: <kalimat>}}`. Isi awal:

| Kalimat ("Peran ini bisa …") | Pasangan |
|---|---|
| membuka periode yang sudah ditutup dan mencatat bertanggal mundur | `period.unlock`, `period.backdate`, `accounting.reopen` |
| membatalkan jurnal dan menutup buku | `accounting.void`, `accounting.manage` |
| membayar pemasok dan mencairkan dana | `vendor_bill.pay`, `contra_bon.pay`, `landed_cost.pay`, `cash_advance.disburse` |
| membebaskan atau mengubah denda | `penalty.waive`, `penalty.adjust` |
| membatalkan kwitansi, faktur pajak, atau rencana bayar | `ar_receipt.void`, `tax_invoice.cancel`, `payment_plan.void` |
| mengirim barang sebelum lunas dan mengubah pesanan terkunci | `order.release_unpaid`, `order.override`, `order.approve_price_edit` |
| mengelola gaji dan melihat data pribadi karyawan | `hr.manage_payroll`, `hr.view_pii` |
| menghapus data induk | `product.delete`, `product.retire`, `customer.delete`, `supplier.delete`, `warehouse.delete`, `uom.delete`, `entity.delete` |
| mengelola akun dan hak akses orang lain | `user.create`, `user.update`, `user.delete`, `permission.update` |
| mengubah pengaturan perusahaan | `settings.manage` |
| melihat HPP dan margin | `costing.view`, `ai.view_margin`, `od_pricing.view_cost` |
| menyetujui nilai persediaan, melepas aset, dan mencatat akrual insentif | `inventory.approve_value`, `fixed_asset.dispose`, `sales_force.post` |
| mengatur perangkat dan alat sistem | `rfid_device.configure`, `system_tools.configure` |

**Menu di luar katalog (lampiran B C.2).**

| Menu atau tab | Putusan |
|---|---|
| `home`, `my-desk` | Tidak masuk modul; tampil menurut sifat peran (PR-T4): `home` bila `home_nav_id` peran = `home`, `my-desk` bila `kategori_kerja` tidak kosong. Bila PR-T4 belum selesai: tetap mengikuti peran dasar |
| `tanya-kn`, `incentive-rates` | Sudah masuk modul di PR-T2 (`assistant`, `sales_force`) |
| `sales-admin-desk`, `finance-desk`, `md-desk`, `warehouse-admin-desk`, `sample-admin-desk`, grup `meja-peran` | Masuk `nav` modul `penjualan`, `ar`, `design`, `warehouse_ops`, `sample_order` (grup ke kelimanya) dengan syarat aksi di bawah |
| `customers-master` | `nav` modul `customer` |
| `internal-prices` | `nav` modul `interco` |
| `reimburse-payables` | `nav` modul `petty_cash` |
| `amendment-reasons` | `nav` modul `finance_ops` |
| `settings-receiving-ocr` | `nav` modul `warehouse_ops` |
| `bank-recon-rules` | `nav` modul `finance_ops` |
| `permission-matrix` (alias), `cs-bom` (segera hadir), `hr-my-profile` | Tidak berubah |

Syarat per aksi: konstanta baru `VIEW_ACTION_REQUIREMENTS: Dict[str, List[Tuple[str, str]]]` — `sales-admin-desk` →
`order.confirm`; `finance-desk` → `payment_variance.decide`; `md-desk` → `design_request.view`;
`warehouse-admin-desk` → `wms.view`; `sample-admin-desk` → `sample_order.view`. Dikirim bersama `view_resources` pada
`GET /api/auth/me` sebagai `view_actions`; `accessBlocks` di `frontend/src/config/roles.js` menyembunyikan menu bila
tidak ada pasangan yang dipegang.

**Satu kamus label.**

| Metode + path | Izin | Jawaban | Galat |
|---|---|---|---|
| `GET /api/access/labels` (baru) | login (data rujukan; ditambahkan ke `LOGIN_ONLY` PR-T3) | `{"resources": {<sumber daya>: label}, "actions": {<aksi>: label}, "modules": {<sumber daya>: label modul pemiliknya}}` dari `RESOURCE_LABEL`, `ACTION_LABEL`, `MODULE_CATALOG` | — |

`frontend/src/config/auditLabels.js`: `moduleLabel` dan `actionLabel` membaca kamus server (diisi saat sesi dimuat);
`MODULE_LABEL` dan `ACTION_LABEL` setempat hanya untuk kunci yang bukan sumber daya izin (mis. jenis dokumen audit).
Teks tiap label yang berbeda diselaraskan ke kamus server; perbaikan kata per label ada di PR-T6.

**Penjaga.** Skrip baru `scripts/guardrails/verify_permission_checked.py` (INV-PERM-01), dipasang di
`scripts/gate.sh` bersama `--self-test`: tiap pasangan di `DEFAULT_PERMISSIONS` harus punya pemeriksa literal di
`backend/`, atau tercantum di daftar "diperiksa dinamis" di dalam skrip (20 pasangan "Tetap" tabel 1, masing-masing
dengan berkas pemeriksanya), atau di daftar "menunggu KP-T4" (5 pasangan) yang harus kosong setelah KP-T4. Tiap
sumber daya harus masuk tepat satu modul dan punya label; tiap aksi punya label.

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada pasangan baru. Empat belas pasangan dihapus (tabel 1). Lima modul baru menggantikan `admin` (tabel 2); satu
modul dihapus (`sales_profile`).

### Layar

Editor peran (`RoleEditorDrawer.jsx`, `RoleModuleRow.jsx`, `roleAccessUtil.js`, `RoleAccessPanel.jsx`):

- Tombol tingkat: **Tidak ada** · **Lihat saja** · **Semua aksi**. Hanya tingkat di `levels_available` yang tampil;
  modul sakelar menampilkan **Mati** · **Nyala**.
- Bila `partial`: tidak ada tombol yang menyala; di kanan nama modul tampil lencana "Sebagian ({held} dari {total}
  aksi)". Teks lama "Kelola penuh · sebagian" dihapus.
- Di bawah deskripsi modul, bila "Lihat saja" dipilih dan `view_excludes` tidak kosong: "Tidak termasuk pada Lihat
  saja: {daftar label}."
- Dialog "Periksa sebelum menyimpan": tiap modul yang berubah menampilkan aksi yang ditambah dan dicabut per halaman,
  "{label halaman}: +{aksi}, +{aksi} · −{aksi}". Bila ada aksi di `sensitive_actions` yang ditambah: "Perhatian —
  peran ini akan bisa: {kalimat}; {kalimat}." menggantikan kalimat modul sensitif yang lama.
- "Atur rinci": aksi berisiko diberi ikon peringatan dengan petunjuk berisi kalimatnya.
- Kartu peran: "{n} semua aksi · {n} sebagian · {n} lihat · {n} tidak ada".
- `frontend/src/features/wms/InventoryStockView.jsx`: tombol "Tambah Stok" memakai `can(…, "product", "create")`.

## Uji penerimaan

Persiapan bersama: peran uji baku `02` §6; `adm` = admin seed. Berkas `backend/tests_mem/data/kode_sebelum_PRT5.json`
dibuat pada langkah kerja 1 sebelum kode diubah (kode jawaban 13 peran bawaan untuk `/api/reports/*`, empat endpoint
baca inspeksi, `/api/users`, `/api/access/roles`, `/api/entities/x`, `/api/scheduler/settings`,
`/api/config/registry`).

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | — | `GET /api/access/modules` | Tidak ada modul `admin` dan `sales_profile`; ada `accounts`, `roles`, `entities`, `settings`, `scheduler`; tiap sumber daya muncul di tepat satu modul |
| U2 | B | "Tanpa Acuan" dengan `levels: {"accounts": "manage"}` | `GET /api/users`; `GET /api/access/roles`; `GET /api/scheduler/settings` | 200 · 403 · 403 (kelola akun tidak lagi membawa peran dan penjadwal) |
| U3 | B | — | `adm`: `POST /api/access/roles` `{"label": "Lama", "levels": {"admin": "manage"}}` | 200; izin memuat `user`, `permission`, `settings`, `entity`, `scheduler`; `levels` jawaban memakai lima id baru |
| U4 | B | fixture sisip: peran kustom yang matriksnya memuat `order.print`, `reports.export`, `sales_pov.commercial`; hapus id migrasi; nyalakan ulang | `GET /api/access/roles/{peran}` | Ketiga pasangan tidak ada; izin lain utuh |
| U5 | B | — | `adm`: `PATCH` peran kustom dengan `permissions` memuat `order: ["view", "print"]` | 400 "Aksi ['print'] tidak berlaku untuk “Pesanan Penjualan (SO)”." |
| U6 | B | "Tanpa Acuan" + `reports.view` | `GET /api/reports/summary` oleh Tanpa Acuan, Manajer Kosong, Sopir | 200 · 403 · 403 |
| U7 | B | "Tanpa Acuan" + `order.view` (tanpa `reports.view`) | `GET /api/reports/summary`; `GET /api/reports/order-velocity` | 403 · 200 |
| U8 | B | "Tanpa Acuan" + `md_quality.view` | `GET /api/inspections` | 200 (sebelum unit: 403) |
| U9 | B | — | `adm`: `PATCH` peran kustom `{"levels": {"field_visibility": "view"}}`; lalu `{"levels": {"approval": "manage"}}` | 400 "Tingkat “Lihat saja” tidak berlaku…" · 400 "Tingkat “Semua aksi” tidak berlaku…" |
| U10 | B | peran Sales bawaan | `GET /api/access/roles/sales` | Untuk modul `penjualan`: `level` = `manage`, `partial` = benar, `held` < `total`, keduanya bilangan bulat |
| U11 | B | — | `GET /api/access/labels` oleh Sopir | 200; `resources.permission` = "Peran & Hak Akses"; tiap sumber daya dan aksi di `DEFAULT_PERMISSIONS` punya label |
| U12 | B | — | `python scripts/guardrails/verify_permission_checked.py` dan `--self-test` | Keluar 0; self-test memerah saat satu pasangan tanpa pemeriksa ditambahkan |
| U13 | B | "Tanpa Acuan" dengan `levels: {"penjualan": "view"}` | `GET /api/auth/me` | `view_actions["sales-admin-desk"]` = `[["order", "confirm"]]`; menu itu tidak termasuk yang boleh dibuka |
| U14 | B | berkas "sebelum" | Sapu ulang oleh 13 peran bawaan | Admin dan Manajer: kode sama di semua rute. Selisih yang diizinkan hanya pada empat endpoint `/api/reports/*` tabel 1: 200 → 403 bagi peran tanpa `reports.view` (Sales, Gudang, MD, Admin Gudang, Admin Sample, dan lainnya), dan 403 → 200 bagi peran yang memegang `reports.view` tetapi tidak memegang izin lama endpoint itu (Finance pada `/api/reports/warehouse-utilization`) — koreksi PR-T5 |
| U15 | layar (uji jalan) | Login Admin | Buka editor Sales | Modul "Pesanan Penjualan" berlencana "Sebagian (n dari m aksi)" tanpa tombol menyala; modul "Melihat grade, nomor lot & asal barang" hanya punya Mati/Nyala; memilih "Semua aksi" lalu simpan menampilkan daftar "+aksi" dan kalimat "Perhatian — peran ini akan bisa: …" |

## Langkah kerja

1. Berkas "sebelum"; `backend/tests_mem/test_PRT5_katalog.py` (U1–U14). Merah: U1–U13.
2. Tabel 1: hapus 14 pasangan + migrasi; sambungkan `reports.view` dan `md_quality.view`; tombol "Tambah Stok".
   Hijau: U4–U8, U14.
3. Tabel 2 + `MODULE_ALIASES`; hapus `sales_profile`. Hijau: U1–U3.
4. `levels_available`, `view_excludes`, `held`/`total`, `SENSITIVE_ACTIONS`. Hijau: U9, U10.
5. Menu di luar katalog + `VIEW_ACTION_REQUIREMENTS`; `GET /api/access/labels` + kamus layar. Hijau: U11, U13.
6. Penjaga INV-PERM-01. Hijau: U12.
7. Editor; U15. Gate penuh, `verify_access_catalog_nav.py`, `verify_role_label.py`; laporan.

## Dokumen ikut berubah

`CODEBASE_MAP.md` (penjaga baru); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (nama lima modul, "Semua aksi",
"Sebagian"); `docs/KN_13_NAVIGATION_MAP.md` (pemilik menu dan tab yang dipindah); `memory/PRD.md`.

## Di luar lingkup

- Teks label per halaman dan per aksi (jargon, label mentah) → PR-T6.
- Menyambungkan izin setujui dan tolak PO, tagihan pemasok, dan voucher biaya masuk → KP-T4.
- Susunan hub dan tab Pengaturan → KP-T9; menu keuangan dan SDM → MN-T1.
- Mengganti gerbang `roles:` tertulis pada menu peran bawaan dengan izin → PR-T6 (pratinjau dan menu peran bawaan).
- Naiknya endpoint tulis dari izin lihat ke izin tulis → PR-T3.

## Asumsi dan risiko

- `ASUMSI:` laporan audit menyebut 41 pasangan mati; hitungan pada HEAD memberi 42 tanpa pemeriksa literal, 20 di
  antaranya diperiksa dinamis. Tabel 1 mengikuti hitungan HEAD.
- `ASUMSI:` empat endpoint `/api/reports/*` yang diberi `reports.view` hanya dipanggil layar Ringkasan
  (`frontend/src/features/manager/ManagerDashboard.jsx`); `/api/reports/top-customers` tidak punya pemanggil di layar.
- `ASUMSI:` daftar aksi berisiko adalah penggolongan perancang (lampiran B menyebut ±39 tanpa merinci); ia hanya
  memunculkan peringatan, tidak mengubah izin.
- `ASUMSI:` pemilik tab di luar katalog ditentukan dari izin endpoint datanya; `reimburse-payables` dianggap milik
  Kas Kecil.
- `RISIKO:` peran kustom kehilangan menu setelah modul dipecah. Penangkal: `custom_roles.levels` dihitung ulang dari
  izin, bukan dari id modul lama; U3 dan U4. Membatalkan: kembalikan `MODULE_CATALOG`; izin yang dihapus tidak pernah
  diperiksa server sehingga tidak ada akses yang berubah, kecuali dua yang disambungkan (kembalikan gerbangnya).

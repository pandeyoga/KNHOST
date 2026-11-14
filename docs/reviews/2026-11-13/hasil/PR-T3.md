# PR-T3 — Endpoint yang hanya butuh login: dipilah dan dijaga

- Commit awal: `783e67e` (dikerjakan) · digabung di atas `494a249` (sesudah KF-T6, KP-T3)        - Commit akhir: `36b056e` (koreksi blueprint `4d4da5c`)        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PR-04 (+ butir layar PR-UX-43) — K-47; merujuk K-18 (PK-17) dan K-49 (KF-T1)

## Cek ulang "Keadaan sekarang"

| # | Hasil di `783e67e` |
|---|---|
| 1 | Bergeser. Inventaris statik (`bukti/inv_endpoints.py`, dijalankan ulang, tidak diubah) kini mencatat **79** endpoint hanya login (51 baca, 28 tulis), bukan 107: asisten (PR-T2), `/home/finance` (PK-17) dll. sudah berizin |
| 2 | Berlaku; baris: `period_unlocks.py:43` (`list_unlocks`), `ai_analytics.py:46` (`post_query`, sudah `_ai_user` dari PR-T2), `config.py:285` (`write_values`, bergeser dari 262; KF-T1) |
| 3 | Sebagian. Sopir 200 + isi lengkap di `/sales-targets`, `/sales-users`, `/entities` (berkas "sebelum", baris `driver`). `/home/finance` dan `/config/effective` **sudah 403** (PK-17, KF-T1). Jangkar: `crm.py:31` (`list_sales_users`), `crm.py:360` (`list_targets`, bergeser dari 351), `entities.py:58` (`list_entities`, bergeser dari 35) |
| 4 | Berlaku. `dashboard.py:42` |
| 5 | Berlaku. `entities.py:103` (`get_entity`, bergeser dari 99); `entityApi.js:40` (`getEntity`) |
| 6 | Berlaku. `special_orders.py:750`; izin diperiksa di `special_order_fulfillment.py:212–214` (`_can` → `has_permission`) sesudah `_od_or_404` |
| 7 | Berlaku. `period_unlocks.py:43` |
| 8 | Berlaku. `lots.py:192` (`lot_label`, bergeser dari 185), `rfid.py:225` |

Bukti merah (`bukti/PR-T3/tests_mem_PRT3_merah_kode_lama.log`; enam router diganti versi `git show HEAD:…`,
`login_only_endpoints.py` disingkirkan, lalu dikembalikan): **12 gagal** — U1–U9, U13, U14 dan PK-47 U05 (harapan
baru); lulus di kode lama: U10 (putusan "tetap", lihat Menyimpang), U11, U12 (penjaga), U15 (harus sama).
Berkas `tests_mem/data/kode_sebelum_PRT3.json` dibuat dari kode lama sebelum perubahan apa pun, lalu dibangkitkan
ulang pada kode lama saat bukti merah: identik.

## Perubahan

| Berkas | Isi |
|---|---|
| `backend/routers/crm.py` | S4 `list_sales_users`: `require_any_permission` (`customer`/`order`/`sales_force` `.view`), pesan Z6. S3 `list_targets`, `list_incentives`: `require_permission("order","view")` + `_target_sales_filter` — pemegang `sales_force.view` atau peran pengawas melihat semua/sales pilihan, selain itu miliknya. Aturan pengawas `_kpi_scope` dipindah ke `_sees_other_sales` (satu tempat; `_kpi_scope` setara logis, pemanggilan `role_in` di jalur ini turun 4 → 2) |
| `backend/routers/entities.py` | S2 `list_entities`: tanpa `entity.view` hanya `REFERENCE_FIELDS` (14 kunci), tanpa `user_count`/`readiness`, `with_readiness` diabaikan. S5 `count_entities`, `get_entity`, `get_readiness`: `require_permission("entity","view")`, pesan Z6 |
| `backend/routers/dashboard.py` | S1: `may` per bagian (`order`, `customer`, `product`, `warehouse`, `inventory` `.view`); bagian tanpa izin `[]`/0/`{}`, kunci tetap; kueri bagian itu tidak dijalankan (segmen stok hanya untuk `inventory.view` atau stok PT produk mode gabungan) |
| `backend/routers/period_unlocks.py` | S6 `list_unlocks`: `require_any_permission` (`period.unlock`, `accounting.view`); `/active` tetap |
| `backend/routers/purchase_orders.py` | S7 `resolve_po_sourcing`: `require_any_permission` (`purchase_order.create`/`.update`) |
| `backend/routers/special_orders.py` | S8 `fulfillment_set_route` / `fulfillment_realize`: `require_permission("od_fulfillment","choose_route"/"realize")` sebagai pernyataan pertama; pemeriksaan di layanan tetap |
| `backend/login_only_endpoints.py` (baru) | `LOGIN_ONLY` — 53 baris "Tetap" tabel A: 31 `milik_sendiri`, 19 `rujukan`, 3 `sesi` |
| `backend/tests_mem/test_PRT3_login_saja.py`, `test_PRT3_sapuan.py`, `data/kode_sebelum_PRT3.json` (baru) | U1–U13; U14–U15 (modul sendiri; berkas "sebelum" ditulis dengan `KN_PRT3_TULIS_SEBELUM=1`) |
| `backend/tests_mem/test_PK47_cacat_kecil.py` | U05 "Sopir 200 (cukup login)" → 403 (`test_U05_hitung_dijaga_izin_sejak_PRT3`): digantikan putusan S5 |
| `backend/tests/test_bp_PRT3_login_saja.py` (baru) | Lapis A (lulus di MongoDB asli, lihat Uji) |
| `scripts/gen_codebase_map.py`, `CODEBASE_MAP.md` | `login_only_endpoints.py` masuk daftar berkas inti generator; peta dihasilkan ulang |
| `docs/blueprint/unit/PR-T3.md` | Koreksi blueprint (lihat bawah) — commit terpisah `4d4da5c` |

Tidak berubah: `permissions_config.py`, `access_modules.py`, `bootstrap.py` (tidak ada izin baru), layar, `middleware/`,
`rfid*`/`handheld`.

## Pemeriksaan layar (langkah kerja 5)

- **`/api/entities`** dipakai lewat daftar `entities` seluruh aplikasi (`hooks/useAppActions.js:192`, menimpa
  `entity_context.entities`) dan 13 pemanggil langsung. Field di luar 11 kunci S2 yang dibaca layar non-Admin:
  `is_group` (pemilih PT `ClosingView`, `PeriodUnlockView`, `SuspensePanel`, `EliminationModal`), `write_locked` dan
  `city` (`components/EntitySwitcher.jsx:44`, `:72` — saringan dan pencarian pemilih badan usaha). Ketiganya ditambahkan
  ke S2 (14 kunci). Pemanggil langsung lain hanya memakai `id`, `short_name`, `legal_name`, `name`, `code`.
  `user_count`/`readiness`/`with_readiness` hanya dipakai `features/settings/entities` (Badan Usaha & Akses).
- **S5** `/entities/{id}`, `/readiness`, `/count`: hanya `entityApi.js` (layar Badan Usaha & Akses).
- **S3/S4/S6/S7/S8**: pemanggil berada di layar yang menuntut izin sejenis (CRM/POS/HP sales, Skema Insentif, Buka
  Periode, form PO, panel pemenuhan OD dengan tombol dari `can` server).
- **Label lot**: asumsi spesifikasi gugur — lihat Menyimpang 1.

## Uji penerimaan

| ID | Lapis | Merah di lama | Hasil |
|---|---|---|---|
| U1 | B | ya (200·200·200) | Lulus — 200·403·403; `order.view` saja / `sales_force.view` saja → 200; pesan Z6 |
| U2 | B | ya (Sopir 200) | Lulus — target **dan** insentif: Sopir 403; `sls` 1 baris (miliknya, juga bila `sales_id` orang lain); TA+`order.view` 0; TA+`order.view`+`sales_force.view` 2; `adm` 2 dan saringan `sales_id` berlaku |
| U3 | B | ya (kunci lengkap) | Lulus — jumlah baris sama; baris Sopir = 14 kunci S2 (juga dengan `with_readiness=true`); baris `adm` ber-`user_count` |
| U4 | B | ya | Lulus — 200,200 · 403,403 · 403,403; `/count` 200·403·403 |
| U5 | B | ya (`orders` berisi) | Lulus — 200; empat bagian `[]`; `active_orders`, `customers`, `products`, `warehouses` = 0; angka stok 0/`{}`/`[]`; `stock_scope` = `{}` |
| U6 | B | ya | Lulus — `orders` = [`so_uji_prt3`], `active_orders` 1; `customers`/`products`/`warehouses` `[]`. Tambahan: TA master (pelanggan/produk/gudang) tanpa pesanan & stok; TA `inventory.view` dengan stok tanpa produk |
| U7 | B | ya | Lulus — 200·403·403; `accounting.view` saja 200; `/active` Sopir 200 |
| U8 | B | ya (Sopir 200) | Lulus — `create`/`update` bukan 403; Sopir 403; `purchase_order.view` saja 403 |
| U9 | B | ya (404) | Lulus — Sopir 403 (route & realize); TA `choose_route` → route 404, realize 403; TA `realize` → 404 |
| U10 | B | tidak (putusan "tetap") | Lulus — TA `inventory.view`+`field_visibility.lot`: 404 sebelum dan sesudah `label.generate` ditambah (PATCH peran); tanpa `inventory.view` 403 |
| U11 | B | tidak (penjaga) | Lulus — 23 rute pratinjau/simulasi ada; jumlah dokumen semua koleksi sama (selain `audit_logs`, `sessions`); 19 rute menjawab 200 dengan isi sah (`bukti/PR-T3/U11_kode_pratinjau.txt`) |
| U12 | B | tidak (penjaga) | Lulus — tidak ada 403 |
| U13 | B | ya (modul tidak ada) | Lulus — 53 entri, nilai sah, tiap entri = rute + metode di `server.app.routes`; rute unit ini tidak tercatat |
| U14 | B | ya (Desainer 200) | Lulus — Admin dan Manajer sama di semua rute; selisih lain hanya ke 403 bagi peran bawaan yang tidak memegang izin gerbangnya (tabel `bukti/PR-T3/sapuan_U14_sebelum_sesudah.txt`; S8 404→403, lihat Koreksi) |
| U15 | B | tidak (harus sama) | Lulus — dasbor Manajer: 1 pesanan, 4 pelanggan, 5 produk, 3 gudang, angka stok sama dengan sebelum unit |
| Lapis A | A | — | `backend/tests/test_bp_PRT3_login_saja.py` (Sopir ditolak/tersaring, Manajer tetap berisi, Sales hanya target miliknya) — **lulus** 3/3 di lingkungan A (MongoDB 7 asli, backend `36b056e`, data acuan) |

Padanan `t3_escalation.py` baris (f): skrip arsip berhenti di baris 50 (`IndexError`, perilaku sejak KF-T1) sebelum baris
(f); baris (f1)–(f5),(g) disalin apa adanya ke skrip sementara di luar repo (`bukti/PR-T3/t3_baris_f_kode_baru.log`):
(f3) 403, (f4) 403, (f5) 200 — sesuai spesifikasi; (f1)/(f2) 403 (KF-T1/PK-17).

`backend/tests_mem` seluruhnya: **315 lulus / 2 dilewati / 3 diharapkan gagal → 330 / 2 / 3** (15 uji baru; dua pekerja
dan `-n 0` sama) di salinan kerja. Sesudah digabung di atas KF-T6 + KP-T3: **364 → 379 lulus** / 2 / 3; berkas "sebelum"
U14 (dibuat di `783e67e`) tetap cocok — rute yang disapu tidak diubah KF-T6/KP-T3.

Penggabungan: `crm.py` dan `purchase_orders.py` juga diubah KF-T6 di cabang; keduanya tergabung otomatis (tiga arah,
basis `783e67e`). `CODEBASE_MAP.md` dibangkitkan ulang.

Inventaris statik (`bukti/PR-T3/inventaris_login_saja.txt`): LOGIN 79 → 68; 11 rute unit ini keluar; 49 rute LOGIN
sisanya tercatat di `LOGIN_ONLY`; 19 sisanya milik KF-T1 (10), KP-T4 (6), PK-17 (2), PR-T4 (1).

## Penjaga statik

| Penjaga | Sebelum | Sesudah |
|---|---|---|
| `verify_auth_coverage` | 28 | 28 — daftar identik: `ai_analytics` 2, `ai_assist` 3 (gerbang `_ai_user` PR-T2 tidak dikenali penjaga), `design_gallery` 3 (`_do_transition`), `handheld` 20 (sesi perangkat; H7). Tak satu pun rute tabel A unit ini |
| `verify_access_catalog_nav` | 0 | 0 |
| `verify_money_idempotency`, `verify_custom_modals`, `verify_scope_guard`, `verify_codebase_map` | hijau | hijau |
| Semua `scripts/guardrails/verify_*.py` lain | — | keluaran sama dengan salinan HEAD, urutan baris bisa beda (yang merah sudah merah karena lingkungan: `motor`/MongoDB tidak ada) |

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli + backend `36b056e`), sesudah `restore_demo` (data acuan; tiga skrip seed
yang sama seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `gate.sh --quick` | 16 FAIL | 16 | 0 | 0 |
| `gate.sh --ci` | 43 FAIL | 43 | 0 | 0 |

## Menyimpang dari blueprint

1. **Label lot (tabel B baris 1) → "tetap"**, sesuai aturan cadangan spesifikasi sendiri ("bila ternyata ada [layar],
   putusan baris itu menjadi tetap"): Admin Sales memegang `inventory.view` + `field_visibility.lot` tanpa
   `label.generate`, melihat tab Lot & Silsilah lewat menu warisan Sales (`hubTabs.js:157` `roles` memuat `sales`,
   `ROLE_NAV.sales_admin.inherit = "sales"`), dan tombol "Label / QR" (`LotDetailPanel.jsx:152`, tanpa `canEdit`) memanggil
   `POST /lots/{id}/label`. Endpoint hanya membangkitkan perintah cetak (tidak menulis selain jejak audit). Akibatnya U10
   dan sapuan U14 untuk baris itu dijaga "tidak berubah".
2. **S2 = 14 kunci** (+`is_group`, `write_locked`, `city`) — hasil langkah kerja 5, seperti diatur spesifikasi.
3. **S3 tidak memanggil `_kpi_scope` langsung**: fungsi itu memaksa id pelaku bila `sales_id` kosong dan menyelesaikan PT
   sendiri, sehingga pengawas (Admin/Manajer/Admin Sales/Finance) hanya akan melihat targetnya sendiri. Aturan
   pengawasnya dipindah ke `_sees_other_sales` dan dipakai keduanya (perilaku `_kpi_scope` setara).
4. **Pesan 403** diberi kalimat Z6 lewat `detail=` (pola PK-17), bukan pesan teknis bawaan.
5. **PK-47 U5** (`/entities/count` Sopir 200 "cukup login") diganti 403 — keputusan S5 unit ini menggantikannya.
6. **`CODEBASE_MAP.md`**: generator hanya mendaftar berkas inti dari daftar tetap; `login_only_endpoints.py` ditambahkan ke
   daftar itu (`scripts/gen_codebase_map.py`) supaya peta menyebutnya.
7. Uji U14/U15 di berkas sendiri `test_PRT3_sapuan.py` (pola PR-T2: basis data bersih untuk sapuan), bukan di
   `test_PRT3_login_saja.py`.

### Koreksi blueprint (commit terpisah `4d4da5c`)

`docs/blueprint/unit/PR-T3.md`: S2 (+3 kunci); tabel B baris 1 → "Tetap"; U3 (14 kunci); U10 (bukan 403 · bukan 403);
U14 — selisih S8 dari **404** ke 403 (id tidak ada) bagi peran tanpa `od_fulfillment.choose_route`/`.realize` (semua
selain Admin, Manajer, MD) tidak tercantum di harapan lama, dan baris label lot kini tidak berubah; langkah kerja 1
(merah U1–U9, U13, U14); catatan PK-47 U5; asumsi label lot "gugur untuk Admin Sales".

## Asumsi / keraguan

- `ASUMSI` (spesifikasi): peran selain pengawas tidak perlu target/skema insentif orang lain. Akibat: Gudang, Admin
  Gudang, MD, Admin Sample (memegang `order.view`) kini melihat daftar kosong (dulu semua). Kode jawaban tidak berubah.
- S1 sesuai spesifikasi: Finance (tanpa `inventory.view`, `warehouse.view`) dan peran lain kehilangan angka stok dan daftar
  gudang di dasbor (kartu "Jml Tersedia"/"Gudang" menjadi 0). Produk yang dikirim ke pemegang `product.view` tanpa
  `inventory.view` tetap membawa angka stok per produk (`apply_global`) — di luar daftar kunci S1; tidak diubah.
- Peran dengan `permission.view` tanpa `entity.view` yang membuka layar Badan Usaha & Akses: tab Badan Usaha tampil
  dengan baris S2 (tanpa jumlah akun/kesiapan) dan rincian 403 — kasus konfigurasi per-aksi, tidak ada pada peran bawaan.
- `GET /api/documents/resolve` dan `/finance/period-unlocks/active` dicatat `rujukan` (tiga nilai yang diizinkan tidak
  punya kategori "isi disaring di handler"/"pemberitahuan").
- `fulfillment_cancel` (`special_orders.py`, `current_user` + `_can` sesudah dokumen dimuat) berpola sama dengan S8 tetapi
  tidak ada di tabel A (inventaris menggolongkannya IZIN_CABANG); tidak diubah.

## Hambatan lingkungan

Gate dan uji lapis A dijalankan saat penggabungan (lingkungan A). Tanpa uji jalan peramban (tidak ada layar diubah). Uji jest tidak dijalankan karena tidak ada berkas `frontend/` yang berubah.

## Yang perlu direview

- Putusan label lot "tetap" (Menyimpang 1) dan tambahan tiga kunci S2.
- Penjaga matriks PR-T8 nanti membaca `LOGIN_ONLY`: 19 rute login-saja milik KF-T1/KP-T4/PK-17/PR-T4 belum tercatat dan
  akan merah sampai unit itu memutuskannya.
- Titik henti H7: tidak ada butir `rfid`/`handheld`/`middleware` yang disentuh; 20 pelanggaran `handheld` di
  `verify_auth_coverage` tetap.

Status: implemented_pending_review.

# FIX-1 — Cakupan lokasi kerja, PT & keamanan akses (WMS-RFID)

- **Tanggal:** 9 Nov 2026 (WIB) · **Pelaksana:** Claude Code (implementer paket FIX-1) · **Branch:** worktree
  `worktree-agent-a23362b99f3bdce6e` (dasar `integrasi-prep3`, lalu `git merge main` untuk B1b/B2b).
- **Keluhan pemilik yang dituju:** "tugas barang keluar/masuk tercampur, semua entitas semua gudang, tanpa filter atau
  aware dengan user — masa user Soreang melihat Rancamalang" + kebocoran akses yang ditemukan audit B1/B1b/B2a/B2b/B3a/B3b.
- **Status:** `implemented_pending_review` (implementer tidak menetapkan `verified`). Bagian uji yang belum selesai
  karena Docker Desktop macet ditulis apa adanya di §5.

---

## 1. Model cakupan yang diterapkan (keputusan koordinator 1–3)

Dua lapis yang sengaja dipisah (`backend/services/location_scope.py`):

| Lapis | Siapa | Dipakai di | Bisa dilepas? |
|---|---|---|---|
| **Pagar keras** `warehouse_ids_for` (tetap: peran `warehouse` + setelan `wms.location_scope_enforced`) | petugas gudang | SEMUA pemeriksa akses — daftar, detail, **aksi tulis** (`assert_entity_access`/`doc_in_scope`, `assert_warehouse`, `assert_doc_side`) | tidak (pilihan di luar pagar diabaikan, minta gudang di luar lokasi → 403) |
| **Saringan tampilan** `resolve_view`/`view_for` (BARU) | **semua akun** ber-lokasi kerja (`users.location_site_ids`/`location_warehouse_ids`) | daftar tugas & tampilan stok/roll WMS-RFID | ya, lewat bilah cakupan (header `X-Location-Scope`: `""` lokasi kerja · `all` · `site:<id>` · `wh:<id>`) |

- Mode tampilan: `home` (lokasi kerja) · `picked` (pilihan eksplisit) · `all` · `restricted` (petugas berpagar) ·
  **`unset`** (akun tanpa lokasi kerja → semua lokasi **dengan label & anjuran** "lokasi kerja belum diatur — minta admin
  mengisinya di Pengguna"; tidak diam-diam).
- **Pekerjaan fisik per gedung lintas PT** (`entity_scope.resolve_work_scope`): lokasi = cakupan tampilan; PT = SEMUA PT
  yang ditugaskan ke akun (penugasan `allowed_entity_ids` tetap pagarnya), `entity_id` = saringan PT eksplisit. Tiap
  baris membawa `work_entity_id/work_entity_name` (PT pemilik) dan `task_kind/task_kind_label` (jenis tugas,
  `services/work_labels.py`).
- **Aksi pada baris PT lain**: detail & aksi dokumen tetap dijaga ketat per PT dokumen di server (tidak dilonggarkan).
  Layar mendaftarkan PT baris (`frontend/src/services/docEntityRegistry.js`) dan interseptor `apiClient` mengirim
  permintaan ke `/…/{id}/…` atas nama **PT dokumen** (`X-Entity-Id`), hanya bila PT itu ada di penugasan akun.
- Gedung bertanda data uji (`is_test`) dibuang dari tampilan "semua lokasi" & pemilih bawaan.

---

## 2. Temuan yang ditutup (ID → perubahan → uji)

Uji backend baru: `backend/tests/test_fix1_cakupan.py` (30 uji, HTTP ke server hidup; sandi demo dibaca dari
`KN_DEMO_PW`, tidak ditulis di berkas). Uji klien baru:
`frontend/src/features/__tests__/fix1Cakupan.test.js` (9 uji). Guardrail baru: `scripts/guardrails/verify_scope_guard.py`.

### 2.1 Kebocoran akses (P0/P1)

| ID | Perubahan | Uji |
|---|---|---|
| **B3a SCP-1** (P0) | 5 endpoint roll RFID (`/rfid/lookup`, `/rfid/rolls/{id}/print-history`, `POST …/label-prints`, `POST /rfid/roll-scans`, `GET /rfid/roll-scans/{id}`) memakai **dokumen roll asli** di `assert_entity_access` (dulu dict `{"entity_id": …}` → cek PT & lokasi lolos). Respons roll lewat `strip_cost_fields` (HPP tidak bocor). Pola yang sama di `rfid_printers._roll` (tag-history, ganti tag, cetak ulang). Pindai dengan `warehouse_id` → pagar lokasi. | `TestScp1RfidRoll` (3), sapuan G-SCOPE-01 |
| **B3b FRM-23** (P0) | `GET /inbound/qc/tasks/{id}/rolls` lewat `_qc_task` (penjaga yang sama dengan `/plan`) + HPP diredaksi. | `test_frm23_qc_task_rolls_guarded` |
| **B3b FRM-01** (P0) | `PATCH /warehouses/{id}`: cakupan lokasi petugas berpagar; gudang **khusus** hanya oleh akun yang ditugaskan ke salah satu PT-nya; kunci struktur/profil (`zones, sharing_mode, entity_ids, site_id, roles, storage_rules, gate_config, stock_mode, storage_form, active, loading_check_policy`) hanya **admin & Admin Gudang**; `zones` dialihkan ke `save_warehouse_structure` (bin berisi roll/tugas → 409 `LOCATION_IN_USE`, kode bin unik, alasan migrasi); `name`/`code` tidak boleh kosong; `lat` ∈ [-90, 90], `lng` ∈ [-180, 180], NaN/teks ditolak. `DELETE` (nonaktifkan) memakai pagar yang sama. `GET …/occupancy` berpagar lokasi. | `TestFrm01WarehousePatch` (9) |
| **B2a STM-IN-02** (P0) | Cakupan lokasi di **setiap aksi tulis**: PA (`dispatch/publish/cancel-draft/PATCH draft` = gudang asal; `arrival-trips/close/confirm-arrival/resolve-exception` = gudang tujuan; `suggest` berpagar); transfer (`_guard_transfer`: sisi asal untuk setujui/tolak/kirim/batal/status, sisi tujuan untuk terima/pengecualian, baca = salah satu sisi; `POST /transfers` = gudang asal); opname & pendaftaran awal (`cycle_count_sessions` masuk `WAREHOUSE_FIELDS` → semua aksi lewat `guard_doc`; pembuatan sesi berpagar); terima hasil potong (gedung tugas & tujuan); RFID (encode/auto-encode/cabut tag, job cetak & sesi verifikasi, opname RFID, rute roll, alarm & insiden). | `TestStmIn02WriteActions` (3) |
| **G-SCOPE-01** (usulan B3b §8) | Sapuan runtime OpenAPI `GET …/{id}` WMS-RFID dengan id milik PT **dan** lokasi lain → harus 403/404; menemukan & menutup 3 bocor baru: `GET /rfid/rolls/{id}/tag-history`, `GET /inventory/rolls/{id}/repairs`, `GET /warehouses/{id}/occupancy`. Guardrail statik AST menemukan & menutup: `POST /wms/tasks/outbound-from-order/{order_id}` (SO PT lain), `GET /inbound/po/{po_id}/receiving-goods-document` (PO PT lain), `PUT /suppliers/{id}/label-pattern` (supplier PT lain), `GET /outbound/so/{order_id}/loading-check` (SO PT lain), `DELETE /warehouses/{id}`. | `test_g_scope_01_sweep_get_by_id` (≥ 10 endpoint), `verify_scope_guard.py` (+ `--self-test`) |
| **B1b UI-44** (P1) | **Satu aturan token**: header Bearer diutamakan, cookie HttpOnly cadangan (dulu cookie sesi lama mengalahkan Bearer akun baru). `POST /auth/login` mencabut sesi cookie lama di peramban itu; `POST /auth/logout` mencabut sesi Bearer **dan** cookie lalu menghapus cookie; tombol **Keluar** kini memanggil `/auth/logout`. | `TestUi44Session` (3), jest logout |
| **B1 UI-39** (P1) | Logout menghapus `kn_token, kn_user, kn_entity, kn_entity_ctx, kn_loc_scope, kn_my_bin, kn_pos_ctx, kn_reg_bin_*, kn.lineFilter.*`, header `X-Entity-Id`/`X-Location-Scope`, registri PT dokumen; login selalu mulai dari **PT bawaan akun** (tidak lagi `kn_entity` sisa pengguna sebelumnya) & lokasi kerja. Antrean offline tidak dihapus tetapi tiap butir terikat pengguna perekamnya (tidak dikirim dengan token pengguna lain). | jest (3) |
| **B3a SCP-2** (P1) | Lokasi kerja kini menyaring: `/transfers`, `/cycle-count/sessions`, `/registration/sessions`, `/rfid/summary|tags|untagged-rolls|locations|print-jobs|cycle-counts|passages|incidents|devices|printer-status`, `/rfid/printers/queue|follow-up`, `/logistics/deliveries` (via gudang surat jalan), `/inspections` (+ unduhan, via gudang tugas penerimaan), `/putaway-orders` (di dalam kueri, bukan sesudah `limit`), `/goods-receipts`. `/inventory/status-board`: rincian per gudang di luar lokasi petugas berpagar dipangkas (`location_trimmed`; total PT tidak dihitung ulang). Koleksi baru di `WAREHOUSE_FIELDS`: `cycle_count_sessions, rfid_tags, rfid_print_jobs, rfid_verify_sessions, makloon_orders, purchase_returns`. | `TestWorkLocationLists` |
| **B3a SCP-4** (P2) | `/products/{id}/stock-breakdown`: roll PT di luar penugasan hanya angka + identitas (nomor, lot, grade, gudang, panjang, status, PT) — tanpa supplier/PO/faktur/rujukan pesanan PT lain (rekomendasi keputusan #7). | — (kode) |
| **B3a SCP-5** (P3) | `/pos/site-stock?entity_id=` divalidasi penugasan (403); `/dashboard` memakai pagar eksklusivitas + lini yang sama dengan `/products`; gudang data uji tidak ikut. | — (kode) |
| **B3b INP-18** (P3) | Sopir pengiriman wajib akun ber-peran Sopir, aktif, dan ditugaskan di PT pengiriman (buat & ubah). | regresi logistik |
| **B3b matriks daftar** | Selisih supplier (`supplier_variance`) berpagar lokasi petugas. | — |
| **B1b UI-56** (P2) | `/desks/so-tracker` hanya pemegang `order.view` (sopir dulu melihat 89 SO + nilai Rupiah); antrean "Kiriman hari ini" sopir = SJ di pengiriman yang ditugaskan kepadanya (dulu SJ tanpa sopir ikut semua sopir). Kartu pelacak SO disembunyikan di meja tanpa izin pesanan. | `test_ui56_driver_cannot_read_so_tracker` |
| **B2b RFID-7** (P3) | `POST /handheld/session/start` ditolak bila akun tidak berizin satu pun jenis tugas handheld (sopir). | regresi handheld |

### 2.2 Lokasi kerja & PT lintas gedung (keputusan 1–2)

| ID | Perubahan |
|---|---|
| **B1 UI-01/UI-02, K-B1-01** | Bilah cakupan **"Lokasi: … ▾"** (`frontend/src/components/LocationScopeBar.jsx`) di app bar desktop (sebelah pengalih PT, untuk akun ber-izin wms/produk/logistik) & di atas daftar HP gudang. Pilihan: lokasi kerja saya · Semua lokasi (bila tak berpagar) · per site · per gedung (tanpa data uji). Ganti cakupan → layar dimuat ulang. Endpoint baru `GET /api/location-scope` (semua akun login). `LocationScopeBadge` memakai cakupan yang sama. |
| **B1 UI-03, K-B1-02, B2a FLW-IN-07/D1, B3a SCP-3/kep. 6** | Daftar per gedung lokasi kerja **lintas PT yang ditugaskan**: `/wms/tasks` (HP Masuk/Keluar/Sample), `/outbound/tasks` (Barang Keluar), `/inbound/tasks`, `/cutting/desk`, `/putaway-orders`, `/transfers`, `/cycle-count/sessions`, `/registration/sessions`, `/goods-receipts`, `/logistics/deliveries`. Antrean QC kedatangan ikut lokasi (PT tetap PT aktif). Label PT pemilik (`EntityBadge`) + jenis tugas di kartu HP, Barang Keluar, PA, Transfer, Opname, GRN; chip saring PT di HP bila > 1 PT. Terbukti: petugas Rancamalang kini melihat 6 tugas terbuka gedungnya (CST + KSC), dulu 2. |
| **B1 UI-04** | Papan antrean ACC Operasi Gudang (`/home/warehouse` → `approval_backlog_service`, parameter opsional `location_ids`) ikut cakupan lokasi yang sama; catatan "semua gudang" diganti. |
| **B1 UI-38** | Kartu Kedatangan (GRN) menyebut gudang tujuan & PT. |
| **B1 UI-42** | Lokasi Rak: gudang bawaan = gudang di cakupan lokasi aktif (bukan gudang pertama daftar). |
| **B1b UI-55** | Pemilih gate/perangkat, status & antrean printer, riwayat lintasan, insiden RFID ikut lokasi kerja (petugas Soreang tidak lagi melihat gate Jakarta/uji). |
| **B1 K-B1-10, UI-05** | Penanda `is_test` (bisa dibalik) disembunyikan dari `/warehouses` (kecuali `scope=all`/`include_test`), `/warehouse-sites`, `/entities` (pengalih PT), penugasan dinamis admin/manajer (`all_active_entity_ids`), dasbor, tampilan "semua lokasi". Skrip penanda (dry-run bawaan). Uji otomatis yang membuat gudang uji baru tidak terpengaruh (penanda hanya dari skrip). |
| **Skrip K-GDG-07** | `scripts/fix_data_2026_11_09_gedung_bersama.py` (dry-run bawaan, `--apply`, `--undo`): gedung aktif `dedicated` non-uji → `shared` (data acuan: SRG-01, WH-JKT), jejak `migrations` + audit. |

### 2.3 Menu ↔ izin server & aplikasi HP

| ID | Perubahan |
|---|---|
| **B1 UI-23, K-B1-08** | Aplikasi HP sopir = **`MobileDriverApp`**: satu tab Pengiriman (tugas hari ini + buka pengiriman untuk foto muat/posisi/POD, komponen sama dengan desktop). Tidak ada lagi tab ber-`wms.view` → tanpa "Permission ditolak". |
| **B1b UI-47** | Menu Pengiriman mengikuti izin `logistics` (`VIEW_RESOURCE_OVERRIDES["logistics"] = ["logistics"]`); manajer tanpa izin itu tidak lagi mendarat di galat mentah. |
| **B1b UI-48** | "Meja Saya" disembunyikan untuk Admin Gudang & Admin Sales (server menolak; meja mereka = Meja Gudang / Meja Admin Sales). |
| **K-B1-07 (diputuskan), B1 UI-20/UI-21, B1b UI-57** | Tab baru **"Operasional Gate"** di RFID › Monitor Gerbang (panel U300: kesehatan, kunci/buka kunci, sesi dokumen, riwayat lintasan) untuk Admin Gudang & manajer; menu RFID diberikan ke manajer (baca; aksi dijaga izin server, simulator/konfigurasi tetap admin). |

---

## 3. Perubahan perilaku untuk pengguna

1. Daftar tugas fisik (HP & desktop) kini **per gedung lokasi kerja, semua PT yang ditugaskan**, berlabel PT & jenis tugas
   — tidak lagi berubah saat ganti PT aktif. Saring PT lewat chip (HP) / `entity_id`.
2. Akun ber-lokasi kerja (semua peran) melihat **lokasinya** secara bawaan; "Semua lokasi" harus dipilih di bilah cakupan.
   Akun tanpa lokasi kerja melihat semua lokasi dengan label peringatan. Data acuan: hanya 3 akun `warehouse` ber-lokasi →
   peran lain tetap melihat semua (dengan label "belum diatur") sampai admin mengisi lokasinya.
3. Opname, PA, transfer, RFID: petugas berpagar mendapat 403 berpesan saat beraksi di gudang luar lokasinya.
4. Login selalu di **PT bawaan** (admin/manajer dulu "Semua Entitas" bila belum pernah memilih).
5. Keluar mengakhiri sesi server; peramban bersama tidak bisa lagi memakai sesi pengguna sebelumnya.
6. Struktur/profil gudang lewat PATCH hanya admin & Admin Gudang (manajer & operator ditolak; manajer tetap bisa lewat
   layar Struktur `PUT /structure` — perilaku lama, tidak diubah).
7. Sopir di HP hanya melihat Pengiriman; pelacak SO hilang dari meja sopir & desainer.
8. Manajer melihat menu RFID; Admin Gudang & manajer bisa membuka operasional gate dari Monitor Gerbang. Metode
   "Sapu RFID" di Stock Opname tetap tertutup untuk manajer (D-15). Admin Gudang & Admin Sales tidak lagi melihat "Meja
   Saya" (meja khususnya tetap), dan menu Pengiriman hanya tampil bila izin `logistics` ada.
9. Gudang/site/PT bertanda uji tidak muncul di pemilih bawaan (setelah skrip penanda dijalankan).

## 4. Keputusan implementer (di luar keputusan koordinator) + alasan

- **K-I1 — Penugasan PT tetap pagar** untuk daftar lintas PT (bukan "semua PT di gedung"). Alasan: isolasi entitas
  KN_14 §10; petugas Soreang (hanya Kanda) melihat tugas PT lain di Soreang setelah admin menugaskan PT itu ke akunnya.
  Data acuan: `warehouse.soreang` tetap 1 PT (dicatat sebagai sisa data, bukan diubah skrip).
- **K-I2 — Detail/aksi tetap ketat per PT dokumen**, klien mengirim PT dokumen (registri + interseptor). Alasan: tidak
  melonggarkan pagar server yang sudah diuji (E-02/T3); uji isolasi lama tetap berlaku.
- **K-I3 — Saringan tampilan stok bersifat opt-in** (`location_view=1`) untuk `/inventory/rolls|balances` (dipakai layar
  Operasi Gudang › Stok); rekonsiliasi Finance/R&D/produksi tidak berubah. Pemilih gudang eksplisit menang atas tampilan.
  `/inventory/status-board` hanya dipangkas pagar keras (angka "dua angka" = paket FIX-2).
- **K-I4 — Akun tanpa lokasi kerja = "semua lokasi + label & anjuran"**, bukan daftar kosong. Alasan: tidak mematikan
  admin/manajer/uji lama; "tidak diam-diam" dipenuhi oleh label yang selalu tampil.
- **K-I5 — Bearer diutamakan atas cookie** (UI-44). Alasan: Bearer = akun yang sedang tampil di layar; tidak melebarkan
  apa pun (keduanya sudah sah), menghilangkan "akun lama menang" tanpa risiko loop 401; login & logout mencabut sesi lama.
- **K-I6 — Penanda data uji mengecualikan PT uji dari penugasan dinamis admin/manajer** (bukan hanya pemilih) agar "Semua
  Entitas" tidak menjumlah PT uji; dibalik dengan `--undo`.
- **K-I7 — `makloon_orders` & `purchase_returns` ikut pagar lokasi petugas berpagar** (UI-02 menyebutnya tanpa lokasi).
- **K-I8 — PATCH struktur hanya admin & Admin Gudang** sesuai brief; `PUT /structure` (supervisor termasuk manajer) tidak
  diubah — dicatat agar reviewer memutuskan penyeragaman.

## 5. Hasil uji & perbandingan regresi

**Lingkungan:** stack sementara `kn-tmp-fix1-mongo` + `kn-tmp-fix1-be` (salinan `kn_test_trial_2026-11-08` →
`test_database`), node `kn-tmp-fix1-fe` (volume `kn-dev_fe_node_modules`). Stack bersama `kn-uji-*` tidak disentuh.

| Putaran | Hasil |
|---|---|
| Dasar `integrasi-prep3`, 128 berkas uji relevan (cakupan/lokasi/RFID/gudang/GRN/opname/logistik/isolasi) | **1.016 lulus · 357 gagal · 174 error · 62 lewat** (532 node gagal/error — utang lama data/lingkungan) |
| FIX-1 (sebelum penyesuaian 3 uji lama), berkas & DB pulihan yang sama | **1.010 lulus · 363 gagal · 174 error · 62 lewat** — 8 node gagal HANYA di FIX-1 (rincian di bawah), 3 node sembuh |
| 3 berkas uji lama yang disesuaikan (+ uji FIX-1), DB pulihan | **104 lulus · 12 gagal** — ke-12 node gagal SAMA dengan dasar (f0cdef 9, iter293 3); `test_iter293` 05–09 & 13 kini LULUS (id sopir nyata) |
| `tests/test_fix1_cakupan.py` — kode **dasar** (`main`) | **30/30 GAGAL** (bukti merah: setiap uji menangkap kebocoran/perilaku lama) |
| `tests/test_fix1_cakupan.py` — kode **FIX-1** | **30/30 lulus** |
| `fix1Cakupan.test.js` (jest) | **9/9 lulus** |
| Jest PENUH FIX-1 (`--runInBand`) | **78/79 suite · 564/565 uji lulus**; satu-satunya gagal `phase4R3` (aturan grid HP) gagal SAMA di dasar |
| Jest terarah (22 suite yang menyentuh berkas FIX-1) | FIX-1 22/22 suite · 221/221 uji; dasar 21/21 · 212/212 |
| ESLint berkas FE yang diubah | **0 error** (peringatan "unused eslint-disable" yang sudah ada) |

**8 node yang hanya gagal di FIX-1 (putaran 128 berkas) — semuanya akibat keputusan baru, uji lama disesuaikan:**
- `test_f0cdef_multientity::test_header_ent_kanda[/wms/tasks]` — uji lama mengharuskan `/wms/tasks` dipagari header PT
  aktif; keputusan K-B1-02 = daftar pekerjaan fisik lintas PT, saringan PT lewat `entity_id`. Uji kini memakai
  `?entity_id=` untuk daftar kerja (`WORK_LISTS`).
- `test_iter293_audit_backlog::test_02/03/04/11` — uji membuat pengiriman dengan sopir `user_driver_01` yang TIDAK ADA di
  data acuan; validasi sopir INP-18 menolaknya (memang temuannya). Uji kini memakai id akun sopir demo dari DB → test_02–09
  & 13 lulus (dulu 05–09, 13 gagal di dasar).
- `test_prep_b_initial_registration` (3) — gedung uji tanpa site; pendaftaran awal kini berpagar lokasi petugas
  (STM-IN-02). Gedung uji diletakkan di site lokasi kerja petugas `warehouse@`.
- 3 node sembuh di FIX-1: `test_l07_trip_regression::test_single_order_delivery_and_transition`,
  `test_m3_coa_per_pt_and_ic_transfer` (2) — tidak disengaja (urutan/data), dicatat apa adanya.

**Catatan lingkungan:** Docker Desktop macet ±09.10–11.40 WIB (semua panggilan HTTP 500; tidak di-restart oleh FIX-1
karena stack bersama). Putaran yang terganggu dibuang dan diulang dari DB pulihan bersih; jest penuh pertama (paralel,
beban tinggi) habis waktu di dasar maupun FIX-1 dan diganti putaran `--runInBand`.

## 6. Guardrail (dasar `main` vs FIX-1, host Windows, `PYTHONUTF8=1`)

| Guardrail | Dasar | FIX-1 |
|---|---|---|
| `verify_scope_guard` (BARU, G-SCOPE-01) | — | **HIJAU** (7 pengecualian beralasan; `--self-test` OK) |
| role_label, access_catalog_nav, view_aliases, page_tabs, knselect_contract, error_notice, custom_modals, modal_dismiss, picker_portal, uom_vocab, blocking_dialogs, escape_layers, desk_targets, detail_modal, list_export | hijau | hijau (tidak berubah) |
| `verify_line_scope` | MERAH 1 (`sales_order_helpers.py`) | MERAH 1 (sama) |
| `verify_auth_coverage` | MERAH 28/1.717 | MERAH 28/1.718 (endpoint baru `/location-scope` lolos) |
| `verify_entity_label`, `verify_numeric_bounds`, `verify_atomic_claim` | MERAH | MERAH (tidak naik) |
| `verify_no_secrets` | — | 8 temuan di `test_reports/pytest/*.xml` (berkas lama, bukan perubahan FIX-1; dasar pembanding tanpa folder itu) |
| `verify_cross_entity` (runtime, DB pulihan) | LEAK 0 · SKIP 0 | LEAK 0 · SKIP 0 |

## 7. Berkas berisiko bentrok

- **FIX-2 (rumus stok):** `routers/inventory.py` (status-board dipangkas sesudah hitung, `location_view` opt-in),
  `routers/products.py` (stock-breakdown redaksi), `routers/dashboard.py` (pagar produk), `services/fulfillment_service.py`
  TIDAK disentuh.
- **FIX-3 (alur):** `routers/putaway_orders.py`, `transfers.py`, `cycle_count.py`, `initial_registration.py`,
  `outbound_picking.py`, `inbound_receiving*.py`, `cutting.py`, `services/putaway_order_service.py` (`list_orders(extra=)`),
  `services/logistics_service.py` (validasi sopir), `services/role_desk_service.py` — hanya baris pemeriksa cakupan.
- **PREP-F/G/H:** `routers/rfid_printers.py` (`_roll`, antrean/follow-up), `routers/rfid.py`, `routers/handheld.py`
  (`session/start`). `rfid_v2_*`, `gate_*`, `gate_txn_service.py` **tidak** disentuh.
- **Bersama:** `backend/dependencies.py` (`extract_token`), `routers/auth.py`, `entity_scope.py`, `access_modules.py`,
  `services/approval_backlog_service.py`/`home_service.py` (parameter opsional), `frontend/src/App.js` (498 baris),
  `config/roles.js`, `config/navStructure.js`, `config/hubTabs.js`, `hooks/useAppActions.js`, `services/apiClient.js`.

## 8. Sisa (belum dikerjakan / di luar batas)

1. **Data**: jalankan (setelah ditinjau) `fix_data_2026_11_09_gedung_bersama.py` & `fix_data_2026_11_09_tandai_data_uji.py`
   di DB uji dengan `--apply`. Diuji di SALINAN (`test_database` stack sementara): dry-run → apply → dry-run 0 → undo →
   dry-run kembali; gedung bersama = **2** (WH-JKT, SRG-01), data uji = **12** (6 gudang `TEST_WH`, 3 `TEST_SITE`,
   3 "PT Uji Provisioning"); DB lain ditolak. DB bersama `kn_test_trial` TIDAK disentuh. Penugasan **lokasi kerja** untuk
   Admin Gudang, sales, Admin Sales, QC, MD dan penugasan PT petugas Soreang (K-GDG-07) = tindakan admin di Pengguna.
2. **Izin peran tersimpan ≠ katalog** (B1b UI-47 akar): manajer di DB uji tanpa `logistics` padahal katalog memberinya —
   perlu migrasi izin (bukan cakupan).
3. **B1b UI-49** (403 tampil sebagai data kosong: skor mitra makloon, pemilih grade) — di luar batas berkas.
4. **B2b RFID-8** (ringkasan antrean periksa & notifikasi gate tanpa pagar) — `rfid_v2_*` (paket PREP-H).
5. Nama gate manusiawi (kode perangkat sebagai nama, UI-55) & istilah Inggris RFID — label, di luar cakupan.
6. Bilah cakupan belum dipasang di aplikasi HP non-gudang (sales/MD/QC); stok HP sales ("dua angka") = FIX-2.
7. Label PT belum di kartu Cutting desk & daftar Barang Masuk lama (registri PT sudah).
8. `/wms/health-dashboard`, `/inventory/rolls/{id}/journey-timeline`, `/registration/freeze` belum memakai lokasi.
9. Penyeragaman izin struktur `PUT /structure` (manajer) vs PATCH (admin/Admin Gudang) — keputusan reviewer.

## 9. Ringkasan untuk koordinator

- **Ditutup:** B3a SCP-1 (+ pola sama di `rfid_printers`), SCP-2, SCP-3, SCP-4, SCP-5 · B3b FRM-01, FRM-23, INP-18,
  G-SCOPE-01 (uji sapuan + guardrail statik; 8 bocor tambahan ditemukan & ditutup) · B2a STM-IN-02, FLW-IN-07 (D1) ·
  B1 UI-01, UI-02, UI-03, UI-04, UI-05/K-B1-10, UI-23/K-B1-08, UI-38, UI-39, UI-42, K-B1-01, K-B1-02 · B1b UI-44, UI-47,
  UI-48, UI-55, UI-56, UI-57/K-B1-07 · B2b RFID-7. Skrip data K-GDG-07 & penanda uji (dry-run bawaan, bisa dibalik).
- **Perilaku baru:** daftar kerja fisik per gedung lokasi kerja lintas PT berlabel PT & jenis tugas; bilah cakupan
  "Lokasi: … ▾" di desktop & HP; pagar lokasi di setiap aksi tulis; Bearer > cookie + Keluar mengakhiri sesi server; login
  di PT bawaan; HP sopir = Pengiriman; menu ikut izin server; operasional gate di RFID › Monitor Gerbang.
- **Uji:** 30 uji backend baru (30/30 merah di dasar, hijau di FIX-1) + 9 jest; regresi 128 berkas tanpa node gagal
  khusus FIX-1 sesudah 3 uji lama disesuaikan dengan keputusan baru (alasan per uji di §5); jest penuh 78/79 (sama dengan
  dasar); guardrail tidak ada angka merah yang naik; `verify_scope_guard` baru hijau.
- **Risiko bentrok:** FIX-2 (`inventory.py`, `products.py`, `dashboard.py` — hanya pagar/redaksi), FIX-3 (router alur —
  hanya baris pemeriksa cakupan), PREP-F/G (`rfid_printers.py`, `handheld.py`), berkas bersama (`dependencies.py`,
  `auth.py`, `App.js`, `roles.js`, `apiClient.js`).
- **Sisa:** jalankan 2 skrip data; isi lokasi kerja akun non-gudang; migrasi izin peran tersimpan (UI-47 akar); UI-49;
  B2b RFID-8 (`rfid_v2_*`); nama gate; bilah cakupan di HP non-gudang; penyeragaman izin `PUT /structure`.

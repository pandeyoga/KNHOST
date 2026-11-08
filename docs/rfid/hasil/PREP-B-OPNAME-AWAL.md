# PREP-B — Opname awal: pendaftaran ulang stok dari fisik per gedung

Tanggal: 8–9 Nov 2026 · Pelaksana: Claude Code (implementer) · Dasar: `docs/rfid/KEPUTUSAN_GATE_RFID.md` §8
(K-OPN-01..06, mengikat). Status: **implemented_pending_review** (belum diuji dengan perangkat RFID nyata).

## 1. Ringkasan
Mode **"pendaftaran awal gedung"** dibangun DI ATAS mesin opname yang ada: sesi tetap dokumen `cycle_count_sessions`
(`mode: "registration"`) sehingga klaim saga, catatan operasi bertahap per roll (`roll_count.ops`, AUD-WMS-01),
`write_off_missing`, `surplus_unit_cost` dan jurnal `cycle_count_variance` dipakai ulang — bukan mesin kedua.

- **Sesi** per gedung dengan cakupan zona/rak (node lokasi; kosong = seluruh gedung), status
  `draft → running → pending_approval → approved | approved_with_exceptions | rejected`, progres per rak (roll terdaftar,
  rak ditandai selesai, baris belum dikenali, panjang belum terverifikasi, tag belum ditulis).
- **Pembekuan (K-OPN-03)** dipilih di sesi: `warehouse` (beku penuh, gedung kecil) atau `zone` (hanya bin cakupan,
  gedung besar). Aktif sejak sesi **dimulai** sampai disetujui tuntas/ditolak. Gerakan roll dari/ke area beku → **409
  `REGISTRATION_FREEZE`** dengan pesan Indonesia yang menyebut sesi & area. Cakupan dua sesi yang beririsan ditolak.
- **Baris lapangan** (HP/handheld; koleksi baru `initial_registration_lines`): EPC kanonik & unik (tag hidup + baris
  hidup sesi mana pun, dijaga indeks unik parsial), dua mode EPC per sesi (K-OPN-05 terbuka): `read` (EPC bawaan tag
  dibaca) / `system` (EPC dibuat server, tag `pending_write` → saat disetujui tag lahir `pending_print`, aktif setelah
  "Tag sudah ditulis"). Produk aktif, tergantikan (`superseded_by`, dibaca defensif) **diarahkan ke penggantinya**,
  tanpa satuan dasar ditolak (penjaga P18 `makloon_receipt_qc.require_unit`). "Produk belum dikenali" boleh disimpan
  dengan keterangan + foto (mekanisme `storage_service` yang sama dengan lampiran retur) — tidak bisa disetujui sebelum
  dipetakan. Panjang + satuan dikonversi ke satuan dasar (`conv_qty`), `length_verified` = dari label (K-OPN-04), selain
  itu "panjang belum terverifikasi" dan ikut ke roll. Lot/dye lot, grade (enum resmi), PT pemilik (dalam akses), bin
  (wajib di cakupan), nomor roll lama opsional. Label supplier dipindai lewat parser penerimaan yang ada
  (`label_decoder_service` + `supplier_item_service.lookup`) → saran produk, panjang terverifikasi, lot, nomor roll.
- **Rekonsiliasi per produk×PT** (`initial_registration_plan.build_plan`, satu fungsi untuk layar & persetujuan): data
  lama (roll fisik di cakupan, lahir sebelum sesi mulai) vs hasil pendaftaran → roll lama dicocokkan (EPC tag lamanya
  terbaca / nomor roll lama terbaca, produk & PT sama) dipakai ulang, baris lain = roll baru (temuan), roll lama tanpa
  pasangan = hilang, selisih qty, nilai dengan **biaya rata-rata** (K-OPN-02, dibekukan saat sesi diajukan).
- **Persetujuan massal** (per kelompok produk×PT atau seluruh sesi) oleh `inventory.approve_count`: roll baru
  `create_inbound_roll(acquired_via="initial_registration")` ber-id deterministik + tag ditautkan
  `rfid_service.encode_tag(..., epc=...)`; roll lama yang cocok dipakai ulang (CAS + catatan operasi bertahap, mutasi
  relokasi/penyesuaian, tag ditautkan); roll lama tak terdaftar dihapus (`write_off_missing(post_journal=False)`, tag
  lamanya dicabut); **satu jurnal selisih per kelompok** (`gl.post_cycle_count_variance`, idempoten per
  `sesi:reg:kelompok`). Tuntas → area ditandai **terverifikasi pendaftaran** (`registration_area_status`, tanggal)
  dan pembekuan dilepas.
- **UI**: desktop Operasi Gudang › Stock Opname › metode **"Pendaftaran awal gedung (RFID)"** (daftar sesi + buat sesi
  pop-up + rincian berdampingan: progres per rak, rekonsiliasi, pemetaan produk belum dikenali, setujui per produk /
  seluruh / terima pengecualian, kembalikan, tolak). HP: Pindai › **Daftar Awal** (EPC → produk/label → panjang →
  Simpan & lanjut; bin aktif diingat; produk & bin tetap untuk roll berikutnya; antrean EPC dari tempel banyak kode).

## 2. Berkas
Baru:
| Berkas | Isi |
|---|---|
| `backend/services/registration_freeze.py` | Pembekuan: `assert_movable`, `assert_rolls_movable`, `assert_order_movable`, `assert_task_movable`, `assert_transfer_movable`, `area_verification` |
| `backend/services/initial_registration_service.py` | Siklus sesi: buat, mulai (cek irisan), progres per rak, tandai rak, ajukan (biaya dibekukan), kembalikan, tolak; indeks unik parsial |
| `backend/services/initial_registration_lines.py` | Baris lapangan: cek EPC (banyak kode), EPC sistem, produk aktif/tergantikan/satuan, label supplier, tambah/ubah/batal, tag sudah ditulis |
| `backend/services/initial_registration_plan.py` | Cakupan, roll lama di cakupan, rencana & rekonsiliasi per produk×PT, biaya rata-rata beku |
| `backend/services/initial_registration_approve.py` | Persetujuan massal (saga + langkah idempoten), tautan tag, tandai area terverifikasi |
| `backend/routers/initial_registration.py` | API `/api/registration/...` (disertakan lewat `routers/cycle_count.py`, `server.py` tidak diubah) |
| `backend/tests/test_prep_b_initial_registration.py` | Uji HTTP + layanan (3 uji besar) |
| `frontend/src/features/inventory/registration/{registrationApi.js, InitialRegistration.jsx, RegistrationDetail.jsx}` | Layar desktop |
| `frontend/src/features/mobile/MobileRegistration.jsx` | Layar HP |
| `frontend/src/features/__tests__/prepBInitialRegistration.test.js` | Jest |

Diubah (milik B): `backend/services/stock_count_roll_service.py` (`write_off_missing(..., post_journal=False, label=...)`
+ pintu publik `resume_roll_op`/`start_roll_op`), `backend/routers/cycle_count.py` (daftar opname biasa menyaring
`mode != registration`; `include_router` pendaftaran), `frontend/src/features/wms/StockOpnameTab.jsx` (metode ketiga),
`frontend/src/features/mobile/MobileWarehouseApp.jsx` (sub-tab "Daftar Awal" di tab Pindai — bilah bawah tetap ≤5),
`scripts/guardrails/verify_atomic_claim.py` (2 entri REVIEWED untuk endpoint baru; jumlah "BELUM DITINJAU" tetap 77).

## 3. Kait di layanan lain (masing-masing 1 panggilan + impor lokal di baris sebelumnya)
| Berkas · fungsi | Aksi yang dibekukan |
|---|---|
| `services/location_service.py` · `place_roll` (jalur tunggal tulis bin: `/inventory/putaway`, putaway roll scan label/GRN, penempatan terima transfer, `fix_orphan`) | penempatan/pindah bin — asal & tujuan |
| `services/putaway_order_service.py` · `create_order` | membuat perintah putaway (roll asal + gudang tujuan) |
| `services/putaway_order_service.py` · `dispatch` | mengirim perintah putaway |
| `services/putaway_order_service.py` · `confirm_arrival` | konfirmasi tiba perintah putaway |
| `routers/outbound_picking.py` · `scan_pick_item` | pengambilan (picking) outbound (roll/bin yang dipindai, atau roll pesanan) |
| `services/shipment_service.py` · `dispatch_task` (juga dipakai kirim batch) | pengiriman outbound |
| `routers/transfers.py` · `update_transfer_status` | transfer gudang: siapkan/kirim (asal) · selesai (tujuan) |
| `services/transfer_receipt_service.py` · `receive` | penerimaan transfer gudang (gudang/bin tujuan) |
| `services/roll_service.py` · `confirm_cut` (hanya jalur baru, bukan lanjutan potong yang terputus) | pemotongan roll |
| `services/sample_sale_service.py` · `cut_sample_task` | potong sample |

Semua kait dipasang **sebelum** klaim saga/efek dan menolak dengan 409 (bukan 4xx validasi) — penjaga
`validation_after_claim` tidak terpengaruh. Logika `putaway_order_service` (paket C) tidak disentuh selain 3 kait.

## 4. Perubahan perilaku
- Selama sesi pendaftaran berjalan/menunggu persetujuan, gerakan di atas pada area beku → 409 `REGISTRATION_FREEZE`.
  Contoh pesan: *"Penempatan/pindah bin ditolak: tujuan bin … berada di zona Zona A di gudang … yang sedang dibekukan
  untuk pendaftaran awal stok (sesi …). Tunggu sesi itu disetujui/ditolak, atau pakai roll/bin di luar area beku."*
- **Barang masuk baru (GRN)**: penerimaan tetap diizinkan; roll lahir tanpa bin dan lahir SESUDAH sesi mulai → tidak
  ikut rekonsiliasi. Penempatannya ke bin beku ditolak (kait `place_roll`) → taruh di area penerimaan/zona lain,
  dipindah sesudah sesi tuntas. Di gedung beku penuh, roll GRN baru menunggu tanpa bin sampai pembekuan dilepas.
  Tim lapangan **tidak** mendaftarkan barang GRN baru (pisahkan fisik).
- Daftar opname biasa (`GET /cycle-count/sessions`) tidak lagi memuat sesi pendaftaran (punya daftar sendiri).
- Roll hasil pendaftaran membawa `registration{session_id, line_id, at, by, old_roll_no, lot, length_source}`,
  `length_verified`, `rfid_epc`; tag lama roll yang dihapus / diganti dicabut (`retire_reason` tercatat).

## 5. Keputusan desain
1. **Satu mesin**: sesi = `cycle_count_sessions` (mode `registration`); write-off & pemakaian ulang memakai catatan
   operasi bertahap `stock_count_roll_service` (lease + token, aman dilanjutkan). Baris di koleksi terpisah karena
   satu gedung bisa ribuan roll (batas 16 MB dokumen sesi) dan keunikan EPC antar sesi dijaga indeks unik parsial
   (`uq_reg_live_epc` pada baris `live`, `uq_reg_match` satu roll lama ↔ satu baris). Indeks dibuat malas oleh layanan
   (`indexes.py` tidak diubah).
2. **Roll & tag dibuat saat disetujui**, bukan saat baris disimpan (spesifikasi butir 5; menghindari stok ganda selama
   data lama masih ada). Baris = roll + tag yang akan lahir.
3. **Pencocokan roll lama** hanya bila produk & PT sama; bila beda → baris jadi roll baru, roll lama dianggap hilang
   (dicatat di catatan kelompok) — tidak memindah produk/PT roll lama (akuntansi tetap bersih). EPC yang sudah menjadi
   tag hidup roll lama di cakupan = roll lama itu; EPC tag hidup di luar cakupan → ditolak (indikasi EPC tidak unik).
4. **Biaya rata-rata dibekukan saat diajukan** (K-OPN-02) supaya penghapusan roll lama pada persetujuan bertahap tidak
   menggeser rata-rata kelompok berikutnya; kelompok baru (mis. hasil pemetaan) dihitung saat persetujuan pertama.
5. **Jurnal per kelompok hanya saat kelompok tuntas** (atau pengecualian diterima penyetuju) — jumlahnya dihitung dari
   hasil langkah tercatat, sehingga pengulangan sesudah pengecualian tetap satu jurnal benar (idempoten per source_id).
6. **Pengecualian** (mis. roll lama tak terdaftar masih dialokasikan pesanan, roll lama berubah) → sesi tetap
   menunggu persetujuan; penyetuju membereskan lalu menyetujui ulang, atau "Terima pengecualian & tuntaskan"
   (`approved_with_exceptions`).
7. **Gangguan di tengah persetujuan**: kunci saga **dilepas** (bukan `mark_failed`) karena semua langkah idempoten →
   pengulangan langsung melanjutkan. Proses mati tanpa exception meninggalkan kunci → terlihat di Kunci Saga (admin
   melepas) lalu diulang.
8. Penolakan bersifat final (baris batal, EPC bebas lagi); "Kembalikan" = kembali ke lapangan (pembekuan tetap). Keduanya
   ditolak bila sebagian kelompok sudah disetujui. Pemetaan "produk belum dikenali" saat menunggu persetujuan hanya oleh
   penyetuju; memetakan ke kelompok yang sudah disetujui ditolak.
9. Area terverifikasi disimpan di koleksi kecil `registration_area_status` (bukan di dokumen gudang milik paket C);
   dibaca lewat `registration_freeze.area_verification()` / `GET /api/registration/freeze`.

## 6. API (`/api/registration/sessions`, izin `inventory.cycle_count` kecuali disebut)
`POST /` buat · `GET /` daftar · `GET /{sid}` rincian+progres · `POST /{sid}/start` · `GET /{sid}/bins` ·
`POST /{sid}/racks/{rack_id}` · `GET /{sid}/lines` · `POST /{sid}/epc-check` · `POST /{sid}/label-decode` ·
`POST /{sid}/lines` · `PATCH|DELETE /{sid}/lines/{lid}` (saat menunggu persetujuan: `approve_count`) ·
`POST|GET /{sid}/lines/{lid}/photo` · `POST /{sid}/lines/mark-written` · `POST /{sid}/submit` · `GET /{sid}/reconcile` ·
`POST /{sid}/return|reject|approve` (`approve_count`) · `GET /api/registration/freeze?warehouse_id=` (`inventory.view`).

## 7. Bukti uji (apa adanya)
**Pytest baru** `tests/test_prep_b_initial_registration.py` — **3 passed** (lari akhir bersama `test_l10_ln101_roll_count`
+ `test_aud_wms_01`: 20 passed). Gudang & produk uji dibuat sendiri, dibersihkan. Isi:
alur zona lengkap (validasi buat, mulai, irisan sesi 409, putaway ke/dari zona beku 409 & zona lain 200, PA/potong/
transfer/picking 409, EPC tidak kanonik/kembar/tag di luar cakupan, bin di luar cakupan, produk tanpa satuan, produk
tergantikan → pengganti, konversi meter→yard, nomor lama tak ditemukan, produk belum dikenali, cek banyak EPC, label
supplier, progres rak, rekonsiliasi & biaya rata-rata/standar, 403 non-penyetuju, 400 belum dipetakan, pemetaan oleh
penyetuju, setujui per produk, pengecualian roll teralokasi, terima pengecualian, jurnal per produk, area terverifikasi,
beku dilepas, idempoten); beku penuh + seluruh gedung (roll tanpa bin ikut, GRN baru tidak) + EPC sistem
(`pending_print` → aktif) + **gangguan jurnal disuntik → kunci dilepas → ulang tanpa roll/jurnal ganda**; tolak &
kembalikan (EPC bebas lagi, daftar opname biasa tidak tercampur).

**Uji lama relevan** (16 berkas; dijalankan pada kode DASAR `0ed4ea8` di kontainer terpisah dan pada kode SESUDAH,
DB sama) — **hasil identik, tidak ada regresi**:
| Berkas | Dasar | Sesudah |
|---|---|---|
| test_l10_ln101_roll_count | 4 passed | 4 passed |
| test_l10_ops01_t1 | 8 passed | 8 passed |
| test_l10_t1_review | 2 failed, 10 passed | 2 failed, 10 passed |
| test_aud_wms_01 | 13 passed | 13 passed |
| test_iter118_p10 | 8 passed | 8 passed |
| test_iter266_r6_cc_r7 | 24 failed, 7 passed | 24 failed, 7 passed |
| test_p02_wms_putaway | 1 failed, 13 passed | 1 failed, 13 passed |
| test_iter264_putaway_fixes | 4 passed, 2 skipped | 4 passed, 2 skipped |
| test_iter263_wms_rfid_r0r1r2 | 30 passed | 30 passed |
| test_p03_transfer_receipt | 3 passed, 11 errors | 3 passed, 11 errors |
| test_transfer_status_guard | 3 failed, 1 passed | 3 failed, 1 passed |
| test_f10_cbd_dp_dispatch_gate | 5 failed | 5 failed |
| test_iter265_r3r4r5 | 6 failed, 27 passed, 1 skipped | 6 failed, 27 passed, 1 skipped |
| test_f05_cut_child_allocation | 2 failed, 1 passed | 2 failed, 1 passed |
| test_l06_samples_cutting | 8 passed | 8 passed |
| test_g3_phase01 | 1 skipped | 1 skipped |
Merah yang sudah ada di dasar bersumber dari data acuan (contoh terbaca: "Gudang Bandung Kopo sudah NONAKTIF",
`CREDIT_BLOCKED` tunggakan pelanggan), bukan dari PREP-B.

**Jest** `prepBInitialRegistration` + `phase3P5` (D-15 tab opname) + `mobileShell` — **32 passed**.
**ESLint** berkas baru/diubah — **0 error**, 7 warning "Unused eslint-disable directive" (pola sama dengan berkas lama
`MobileWarehouseApp.jsx`; konfigurasi CLI tanpa plugin react-hooks).

### 7a. Guardrail (dijalankan di kontainer uji, sebelum perubahan vs sesudah)
| Guardrail | Dasar | Sesudah |
|---|---|---|
| custom_modals | PASS 98 cek | PASS 98 cek |
| error_notice | PASS 265 | PASS 268 |
| escape_layers | PASS 1148 | PASS 1153 |
| uom_vocab | PASS 1149 | PASS 1156 |
| knselect_contract | 0 temuan | 0 temuan |
| picker_portal | PASS 305 | PASS 307 |
| detail_modal | PASS 25 (berdampingan 2) | PASS 26 (berdampingan 3 — rincian sesi pendaftaran) |
| modal_dismiss | PASS 10 | PASS 10 |
| page_tabs | PASS 12 | PASS 12 |
| role_label | PASS 1141 berkas | PASS 1146 berkas |
| auth_coverage | 8 (1614 cek) | 8 (1635 cek — endpoint baru semua ber-`require_permission`) |
| atomic_claim | 6 (110 cek, BELUM DITINJAU 77) | 6 (112 cek, BELUM DITINJAU 77; +2 entri REVIEWED lolos) |
| to_list_bound | 6 | 6 |
| numeric_bounds | 3 | 3 |
| qty_dual | 5 | 5 |
| ref_unlink | 3 | 3 |

## 8. Sisa / butuh perangkat / butuh keputusan
- **Butuh perangkat**: uji handheld nyata (keyboard-wedge EPC, kecepatan pindai, tempel banyak kode), printer/encoder
  untuk mode EPC sistem (saat ini "Tag sudah ditulis" dikonfirmasi manual per baris; integrasi job cetak `rfid_print_service`
  belum), uji coba satu rak untuk mengukur lama pembekuan (K-OPN-03).
- **Butuh keputusan**: K-OPN-05 (EPC unik?) menentukan mode EPC bawaan; apakah roll lama teralokasi pesanan yang tidak
  ditemukan boleh dilepas otomatis (kini pengecualian manual); apakah approval wajib Finance terpisah dari ACC gudang
  (kini satu izin `inventory.approve_count`, sama dengan opname).
- **Belum dikait** (di luar "titik gerak utama"): serah hasil potong antar lokasi `cutting_service.receive`, potong MD
  Quality `mdq_cut_service.cut` (jalur inspeksi penerimaan), jalur lama yang menulis `bin_id` langsung tanpa
  `place_roll` (tidak ditemukan di layanan utama). Gate/ingest RFID (D1) belum membaca `area_verification`.
- Paket A (`superseded_by`) belum tergabung di base ini — dibaca defensif (id/SKU/objek); perlu cek ulang bentuk field
  setelah A digabung. Satuan pemilih HP memakai katalog master (`useUomConversions`).
- Batas: sesi sampai ±20.000 roll lama/baris per cakupan (`to_list(20000)`); gedung lebih besar → pecah per zona.

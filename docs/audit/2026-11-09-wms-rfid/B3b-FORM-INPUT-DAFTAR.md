# B3b — Audit Form, Input/Output Pengguna, Pemilih Data vs Isian Bebas, dan Fitur Daftar (WMS-RFID)

**Tanggal:** 9 Nov 2026 (WIB) · **HEAD audit:** `5f1e36e` (cabang worktree di-*merge* dari `main` atas arahan koordinator;
mencakup gelombang 2 / D2 — antrean periksa gate) · **Jenis:** AUDIT (tidak ada kode aplikasi yang diubah).
**Lampiran:** [`B3b-MATRIKS-FORM.md`](B3b-MATRIKS-FORM.md) (122 form + paritas HP) ·
[`B3b-MATRIKS-DAFTAR.md`](B3b-MATRIKS-DAFTAR.md) (±55 layar daftar + 197 endpoint GET).
**Skrip analisis (baca-saja, ikut di-commit):** `scripts/audit/b3b_fe_census.js` (sensus Babel FE),
`scripts/audit/b3b_crossref.py` (FE ↔ OpenAPI ↔ router), `scripts/audit/b3b_form_census.py` (sensus elemen form),
`scripts/audit/b3b_collections.py` (koleksi vs ENTITY_REGISTRY), `scripts/audit/b3b_api_probe.py` (uji masukan buruk
— HANYA untuk stack sementara).

Permintaan pemilik yang diuji: *"input apakah sudah benar / lengkap sesuai schema; form yang seharusnya ambil data bukan
custom input; tidak membuat tabel/schema baru; standarisasi form, ukuran tombol, cari, saring, harus ada ekspor Excel;
jangan asal asumsi"*. Keputusan pemilik yang dipakai sebagai aturan: form HP = form desktop (tata letak boleh beda),
istilah tidak diubah (K-13), alasan minimal 5 huruf (K-14), ekspor Excel (XLSX) di daftar.

---

## 0. Ringkasan

| Ukuran | Nilai |
|---|---|
| Layar akar diaudit | 38 (Barang Masuk/GRN, Operasi Gudang, Barang Keluar, Cutting, Perbaikan, Antrean QC, SPK Inspeksi, Lokasi Rak, Data Gudang, Pengiriman, 4 layar RFID + antrean periksa D2, Perangkat, Penerimaan & OCR, Master Grade, Retur ×3, Order Makloon, PO, Lot, Pendaftaran Awal, Opname, Eskalasi, Meja Cutting/Sample, aplikasi HP gudang & ops) |
| Berkas FE terjangkau / dalam cakupan | 478 / 180 berkas berisi kontrol |
| **Form dipetakan** (isian → payload → skema → koleksi) | **122** (lampiran A) |
| Kontrol isian disensus | 658 (239 pemilih terikat id, 364 teks/angka) |
| **Layar daftar** | **±55** (lampiran B) |
| **Endpoint** | 259 panggilan tulis FE → **291 endpoint tulis** + **197 endpoint GET daftar** di 39 router; 11 body `dict`, 13 body diparse manual (V2), ±9 tulis via query string |
| Uji masukan buruk lewat API | **59 uji** dalam 3 putaran di stack sementara `kn-tmp-b3b` (kode `5f1e36e`): **29 masukan buruk DITERIMA**, 4 galat server (500), 14 ditolak benar, 8 info, 2 dilewati, 2 putus koneksi (artefak keep-alive sesudah 500 — diulang di putaran 2) (§2) |
| **Temuan** | **56** — **P0: 3 · P1: 13 · P2: 26 · P3: 14** (FRM 24 · INP 18 · LST 9 · EXP 5) · **20 temuan terverifikasi API** (FRM-09 & INP-09 sebagian), sisanya terverifikasi kode / kandidat |

Lima hal terpenting:
1. **Isian bebas mengisi alamat stok.** "Bin ID (opsional)" di opname (INP-02, **P0**) dan "Bin Location *" di Scan Terima
   (INP-01) adalah `<input>` teks; server tidak memakai `resolve_bin` yang sudah ada. **Terbukti API:** produk & bin yang sama —
   diketik sebagai kode rak `W01-L2-03` → *expected* **0**, sebagai id `bin_sim_rcm_woven_w01_l2_03` → *expected* **240**;
   saat disetujui, selisih "surplus" menjadi **roll baru + jurnal** di alamat yang tidak ada.
2. **Tembus PT.** Operator gudang PT Sukacita berhasil `PATCH` gudang **khusus PT Cipta Sandang** (200, kota berubah) dan
   mengosongkan struktur bin gudang berisi 18.471 roll (FRM-01, **P0**); `GET /api/inbound/qc/tasks/{id}/rolls` menjawab 200 untuk
   tugas PT lain sementara endpoint saudaranya `/plan` menjawab 404 (FRM-23, **P0**).
3. **Form HP jauh lebih sedikit dari desktop** (melanggar keputusan pemilik): Terima/Selesai di HP tidak punya satuan
   dokumen, rincian roll, no. SJ, lot, grade, bin; Ambil di HP tidak memindai roll dan server menerimanya (FRM-02/03/04).
4. **K-14 (alasan ≥ 5 huruf) baru di layar, belum di server** — 25 jalur menerima alasan kosong/1 huruf/teks tetap (FRM-09).
5. **Tidak satu pun daftar WMS-RFID bisa diunduh XLSX**, ±45 daftar tidak bisa diunduh sama sekali, ±46 daftar tanpa
   halaman server (batas keras 100–5000 yang memotong diam-diam). Padahal **mesin XLSX & 20+ dataset gudang sudah ada di
   Pusat Export** — belum disambungkan ke tombol daftar, dan peran `warehouse` tidak punya menu itu (EXP-01).

---

## 1. Metode & batas bukti

1. **Sensus statik otomatis** — `b3b_fe_census.js` mem-parse JSX (Babel) dari 38 layar akar, menelusuri impor, dan
   mencatat setiap `axios.<metode>(url, payload)` (URL konstanta & pembungkus `grnApi.post(id, path, body)` ikut
   diselesaikan), setiap elemen isian + atributnya, setiap tombol + kelasnya, dan pembungkus form.
2. **Silang skema** — `b3b_crossref.py` mencocokkan URL FE ke OpenAPI backend yang berjalan (field, `required`,
   `minimum/maximum/maxLength/pattern/enum`) dan AST router (berkas:baris) → kunci yang dibuang, field wajib yang
   tidak dikirim, endpoint tanpa body/body bebas, endpoint GET tanpa halaman.
3. **Telaah manual per area** (empat penelaah paralel + verifikasi ulang oleh penulis untuk semua butir P0/P1 —
   kutipan berkas:baris di bawah sudah dicek ulang di HEAD `5f1e36e`).
4. **Bukti data & uji API** di stack sementara `kn-tmp-b3b-*` (restore snapshot `kn_test_trial_2026-11-08` ke
   `kn_test_trial` dan `test_database`; backend memakai `test_database`). Docker Desktop engine sempat macet (memori) ±05.00–06.16 WIB
   dan memulai ulang dirinya; stack dijalankan ulang dengan kode **`5f1e36e`**, lalu uji API dijalankan (§2). **Kueri data**
   (baca-saja) dijalankan ke salinan `kn_test_trial` di kontainer sementara — isinya identik dengan snapshot stack bersama dan
   tidak disentuh uji; stack bersama `kn-dev-*`/`kn-uji-*` tidak dijalankan/diubah. Sensus FE otomatis memakai kode `70eb9fd`;
   berkas yang berubah ke `5f1e36e` (`GateReviewQueue/Detail.jsx`, `rfid_v2_review.py`, `LoadingCheckPanel.jsx`, hook gate di
   putaway/transfer/perbaikan/logistik) **dibaca manual**.
5. Tidak memakai alat peramban (dipakai paket B1). Hal yang butuh konfirmasi visual ditandai **→ B1**; tumpang tindih
   dengan SSOT/skema penuh ditandai **→ B3a**.

**Skala keparahan yang dipakai** (tafsir rubrik pemilik): **P0** = stok/jurnal/kepemilikan salah atau hilang lewat jalur
UI wajar, atau tembus PT · **P1** = data operasional salah / kontrol terlewati / form utama buntu · **P2** = validasi,
kelengkapan, konsistensi yang berdampak nyata · **P3** = kosmetik/kinerja ringan.

## 2. Hasil uji masukan buruk lewat API (butir 3)

`scripts/audit/b3b_api_probe.py` (3 putaran, 59 uji) — akun peran `warehouse` (operator, PT aktif Sukacita `ent_ksc`),
`warehouse_admin`, `manager`, `admin`; penilaian otomatis `DITERIMA_SEHARUSNYA_DITOLAK / DITOLAK_BENAR / GALAT_SERVER`,
hasil tersimpan dicek ulang langsung di DB sementara. Stack: `kn-tmp-b3b-be` (kode `5f1e36e`) + `kn-tmp-b3b-mongo`, 9 Nov
±06.20–06.30 WIB. Menjalankan ulang (stack sementara saja):
`docker exec -e KN_PROBE_PW=… -e MONGO_URL=mongodb://localhost:27017 -e DB_NAME=test_database kn-tmp-b3b-be python /app/scripts/audit/b3b_api_probe.py --round 1|2|3`.

**Masukan buruk yang DITERIMA server (seharusnya ditolak):**

| # | Peran | Permintaan | Hasil | Temuan |
|---|---|---|---|---|
| 1 | warehouse (PT Sukacita) | `PATCH /warehouses/wh_2328786267dd` (gudang **khusus PT Cipta Sandang**) `{"data":{"city":"Uji B3b"}}` | **200**, `city` tersimpan | FRM-01 (tembus PT) |
| 2 | warehouse | `PATCH /warehouses/wh_jakarta {"data":{"zones":[]}}` (18.471 roll ber-bin) | **200**, `zones: []` | FRM-01 |
| 3 | warehouse | `PATCH /warehouses/wh_jakarta {"data":{"name":""}}` lalu `{"lat":999,"lng":-999}` | **200**, nama kosong, lat 999 | FRM-01 |
| 4 | warehouse (PT Sukacita) | `GET /inbound/qc/tasks/wms_bef96c0e9725/rolls` (tugas PT Cipta Sandang) | **200** `[]` — pembanding `/plan` tugas yang sama **404** "Data di luar lokasi tugas Anda" | FRM-23 |
| 5 | admin | `POST /cycle-count/sessions/{sid}/items {"bin_id":"W01-L2-03",…}` (kode rak) | **200**, `expected_qty` **0** — dengan id `bin_sim_rcm_woven_w01_l2_03`: **240** | INP-02 |
| 6 | admin | `POST /inbound/tasks/wms_b7020f220cf0/scan-receive {"actual_qty":1,"bin_id":"BIN-FIKTIF-B3B","roll_id":"ROLL-FIKTIF-B3B"}` | **200**, keduanya tersimpan di tugas | INP-01 |
| 7 | admin | `POST /inventory/initial-stock {"unit":"hasta","grade":"ZZ","bin_id":"bin_tidak_ada","quantity":1,…}` | **200**, roll `available` ber-unit `hasta`, grade `ZZ`, bin `bin_tidak_ada` | INP-05 |
| 8 | admin | `POST /inbound/tasks/{id}/resolve-escalation?adjusted_qty=-10` | **200**, `expected_qty: -10` → penerimaan berikutnya ditolak "melebihi toleransi +2% dari PO (-10, maks -10.2)" (tugas macet) | INP-09 |
| 9 | admin | `POST /master/grades {"code":"Z9","rank":98,"max_points":-5}` | **200**, `max_points: -5` | INP-09 |
| 10 | warehouse | `POST /outbound/tasks/wms_4610c188a0d4/scan-pick?actual_qty=0.5` tanpa roll | **200**, `picked_qty: 0.5` | FRM-03 |
| 11 | warehouse_admin | `POST /inspections/random-check {"assigned_to":"user_03f0d6ed87f7"}` | 200, tersimpan `assigned_to: user_whadmin_01` (= pembuat) | FRM-05 |
| 12 | admin | `POST /transfers {… "requested_by":"Direktur Utama","kunci_asing":"…"}` | **200**, `requested_by: "Direktur Utama"`; `kunci_asing` dibuang diam | FRM-08, INP-13 |
| 13 | admin / warehouse | `escalate?reason=x` (inbound & outbound) | **200** | FRM-09 |
| 14 | manager | `grade-override {"grade":"B","reason":"x"}` | **200**, grade berubah | FRM-09 |
| 15 | manager | `transfers/{id}/reject {"reason":"","rejected_by":"Orang Lain"}` | **200** | FRM-09, FRM-08 |
| 16 | manager | `makloon-orders/{id}/cancel {"reason":"a"}` | **200** | FRM-09 |
| 17 | manager | `purchase-returns/{id}/reject {"notes":""}` | **200** | FRM-09 |
| 18 | admin | `purchase-orders/{id}/close {"reason":""}` | **200** | FRM-09 |
| 19 | warehouse_admin | `lots/{id}/status {"status":"hold_shade","reason":""}` | **200** | FRM-09 |
| 20 | warehouse_admin | `goods-receipts/{id}/reject {"reason":"     "}` (5 spasi) | **200**, status `rejected` | FRM-09 |
| 21 | admin | `PUT /config/values` `receiving.mode` alasan `"x"` (risiko *high*) | **200** | FRM-09 |
| 22 | warehouse_admin | `PATCH /goods-receipts/{id}/dn {"number":"N"×5000,"date":"bukan-tanggal"}` | **200**, tersimpan | INP-11 |
| 23 | admin | `POST /rfid/devices {"type":"gate","direction":"samping","status":"rusak","location":"Zona Fiktif"}` | **200**, tersimpan + `last_heartbeat` = saat dibuat | INP-07, FRM-12 |
| 24 | admin | `PATCH /rfid/devices/{id} {"status":"online"}` | 200, `last_heartbeat` diperbarui ke saat itu | FRM-12 |
| 25 | warehouse_admin | `POST /rfid/print-jobs {"kind":"qr"}` | **200**, dibuat job `kind: rfid_tag` + EPC baru | INP-14 |
| 26 | admin | `PUT /config/values receiving.client_po_patterns = ["(?P<core>\\d{3"]` | **200** (regex tak valid tersimpan) | FRM-19 |
| 27 | admin | `PUT /config/values receiving.ocr_price_table = "{rusak"` | **200** → `GET /goods-receipts/usage` **500** | FRM-19 |
| 28 | admin | `PUT /config/values receiving.ocr_max_pages = -1` | **200** | FRM-20 |
| 29 | admin | `PUT /settings {"scope":"global","inventory":{"min_cut_qty":-5}}` | **200** — seksi `inventory` global **kehilangan 5 kunci** (`default_uom`, `stock_analytics`, `reorder`, `intercompany_transfer_required`; tinggal `min_cut_qty:-5`) | FRM-20 |
| – | warehouse_admin | `GET /goods-receipts?limit=100000` | 200 (tanpa batas atas) | LST-03 |

**Galat server (500):** `GET /goods-receipts?limit=-1` (`ValueError: length must be non-negative`, LST-03);
`POST /warehouse-sites {"name":"Gudang (Baru"}` (`OperationFailure: Regular expression is invalid`, INP-12);
`GET /repair-orders?q=(` (INP-12); `GET /goods-receipts/usage` sesudah setelan JSON rusak (FRM-19).

**Ditolak dengan benar (pembanding positif):** `scan-receive doc_qty:-5` (422 `ge=0`); `pengiriman shipping_cost:-100000` (422);
`initial-stock quantity:0` ("quantity harus > 0"); `lots status:"hold"` (daftar status sah disebutkan); `grade-override` oleh
`warehouse_admin` (403 D-23); `milestone` retur oleh peran `warehouse` (403 — tetapi tombolnya tampil, FRM-22); `scan-receive` &
`escalate` oleh operator di luar lokasi tugas (404 pagar lokasi P9.5 ✓); `transfers` gudang asal = tujuan (400);
`qc-decision` saat SPK aktif (409, keputusan lewat SPK); `dispatch?ship_qty=nan` tertahan lebih dulu oleh syarat tag RFID (400) —
**NaN belum terbukti** (INP-09 tetap kandidat untuk butir itu). Tidak teruji (tanpa data prasyarat): tindakan antrean periksa D2
(tidak ada kasus terbuka di snapshot), selesaikan insiden RFID, retur jual tolak.

---

## 3. Temuan — FORM (FRM)

### FRM-01 · `PATCH /warehouses/{id}` menerima `zones` dan tidak memeriksa PT — pagar struktur bin & isolasi entitas terlewati
- **Area/form/endpoint:** Data Gudang (profil/mode/cek muat memakai PATCH) · `PATCH /api/warehouses/{id}` (`GenericPatch {data: dict}`)
- **Klasifikasi:** bug (otorisasi + integritas data, tembus PT) · **Keparahan:** **P0**
- **Bukti:** whitelist `allowed = ["code","name","city",*LOCATION_KEYS,"zones","active","lat","lng",…]`
  (backend/routers/warehouses.py:243-248); untuk `zones` hanya `whp.validate_zone_forms(...)` (:265-266). Jalur resmi
  `PUT /warehouses/{id}/structure` (:143-156) memanggil `assert_supervisor`, `location_scope.assert_warehouse`,
  `whscope.assert_usable`, cek `LOCATION_IN_USE`, kode bin unik & wajib, alasan migrasi (`save_warehouse_structure`).
  PATCH juga tidak memvalidasi `name`/`code` kosong (cek duplikat hanya `if data.get("code")`, :267), `lat/lng` tanpa
  rentang, dan tidak memanggil `assert_usable` (gudang khusus PT lain bisa diubah).
- **Aturan dilanggar:** satu pintu tulis per invarian (struktur lokasi hanya lewat `/structure`); P9.5 pagar lokasi.
- **Dampak:** pemegang `warehouse.update` (peran operator `warehouse`, bukan supervisor) dapat menghapus bin berisi stok
  → roll menjadi "alamat yatim"; kode bin ganda; nama gudang kosong; **dan mengubah gudang khusus PT lain**.
- **Rekomendasi:** keluarkan `zones` dari whitelist PATCH; ganti `GenericPatch` dengan model PATCH bertipe
  (`WarehousePatchIn`, `extra="forbid"`); panggil `assert_usable` + `location_scope`.
- **Status:** **terverifikasi API** (§2 #1–3): operator `warehouse` PT Sukacita → `PATCH` gudang `GU-CST` khusus PT Cipta Sandang
  **200**; `{"zones":[]}` pada `wh_jakarta` (18.471 roll ber-bin) **200**; `name:""` dan `lat:999` **200**.

### FRM-02 · HP "Terima" & "Selesai terima" jauh lebih sedikit isiannya dari desktop
- **Area:** aplikasi HP gudang (alur penerimaan lama `receiving.mode=legacy`) · `POST /inbound/tasks/{id}/scan-receive`, `/complete`
- **Klasifikasi:** fitur belum ada + bug data · **Keparahan:** P1
- **Bukti:** HP mengirim `{ product_id, actual_qty }` (frontend/src/features/mobile/MobileTaskActions.jsx:38) dan
  `{ supplier_lot, dye_lot }` (:46). Desktop `InboundScanInterface.jsx:149-255` mengirim `doc_uom/doc_qty`, batch, lot,
  dye_lot, grade, roll_id, bin_id, alasan override toleransi, dan `rolls[]` (panjang/berat/dye/grade per roll) + `supplier_dn`.
  Tanpa `rolls`, server membuat satu roll bawaan grade A tanpa berat (inbound_complete_service.py:35); mode SJ `block`
  menolak tanpa isian no. SJ (inbound_complete_service.py:60-66) — HP buntu; "Selesai" tampil untuk status `receiving`
  (penerimaan sebagian, MobileTaskActions.jsx:67) padahal desktop memblokir (InboundScanInterface.jsx:188-194).
- **Aturan dilanggar:** keputusan pemilik "form HP = form desktop"; INV-RCV-01/02 (jejak satuan penerimaan).
- **Dampak:** jumlah/berat/grade roll salah; penerimaan kurang ditutup tanpa eskalasi; HP tidak bisa menyelesaikan di gudang ber-SJ wajib.
- **Rekomendasi:** HP memakai komponen isian yang sama (ReceiveUomPanel, GRCatchWeightModal) dalam tata letak HP; server
  menolak `complete` tanpa `rolls[]` bila produk ber-roll dan menolak `complete` saat diterima < pesanan tanpa eskalasi.
- **Status:** terverifikasi kode · uji API kandidat: `scan-receive {"product_id":P,"actual_qty":5}` pada tugas berharapan 100
  → `complete {"supplier_lot":"X"}` (harap ditolak; dugaan: 200 + 1 roll 5 unit).

### FRM-03 · "Ambil" tanpa pindai roll diterima server (jalur HP), padahal desktop mewajibkan roll
- **Area:** HP Barang Keluar · `POST /outbound/tasks/{id}/scan-pick` (query)
- **Klasifikasi:** inkonsistensi + butuh keputusan · **Keparahan:** P1
- **Bukti:** HP: `params: { actual_qty: parseFloat(qty) || 0 }` (MobileTaskActions.jsx:86). Desktop: "Scan roll terlebih
  dahulu… tidak diketik manual" (OutboundScanInterface.jsx:128-131). Server: komentar "Tanpa scan roll (alur cepat
  HP/legacy) tetap diizinkan… Mewajibkan scan per roll = keputusan kebijakan gudang (belum ada)" (outbound_picking.py:119-123).
- **Aturan dilanggar:** WM-06 (verifikasi roll: produk, gudang, PT, alokasi, bin, panjang); form HP = desktop.
- **Dampak:** roll yang keluar dipilih sistem saat dispatch, bukan roll fisik yang diambil; qty diketik bebas.
- **Rekomendasi:** HP memindai roll (kamera/handheld) seperti desktop; setelah pemilik memutuskan, setelan
  `wms.require_roll_scan_on_pick` (bawaan *wajib*) dan server menolak pick tanpa `roll_id`.
- **Status:** **terverifikasi API** (§2 #10): `scan-pick?actual_qty=0.5` tanpa `roll_id` → 200, `picked_qty: 0.5`.

### FRM-04 · Paritas HP–desktop: ≥ 12 tindakan desktop tidak ada di HP, dan sebaliknya pendaftaran awal hanya lengkap di HP
- **Area:** aplikasi HP gudang (`features/mobile/*`) vs layar desktop · **Klasifikasi:** fitur belum ada · **Keparahan:** P2
- **Bukti:** tab HP hanya Pindai / Belum Tag / Daftar Awal + kartu tugas (MobileWarehouseApp.jsx:267). Tidak ada di HP:
  QC kedatangan, SPK, perintah putaway (verifikasi/tiba per trip/tutup), terima transfer, opname rutin & RFID, cek muat
  (gudang `required` → "Berangkatkan" HP ditolak, loading_check_service.py:297-305), encode/print job/verifikasi/pensiun tag,
  monitor & antrean periksa gate, eskalasi, rilis tugas terjadwal, scan label supplier/ukur/simpan ke bin.
  "Berangkatkan" HP tanpa konfirmasi, kirim parsial, gabung SJ (MobileTaskActions.jsx:87 vs OutboundScanInterface.jsx:146-238).
  Kartu baris SJ HP (GrnLineCard.jsx) tanpa katalog supplier, ringkasan packing list, peran, hasil konversi (GrnLineRow.jsx:162-199).
  Kebalikannya: desktop `RegistrationDetail.jsx` tidak bisa menambah/mengubah/membatalkan baris pendaftaran (hanya memetakan produk).
  Cetak ulang label HP lewat popup peramban tanpa mencatat `label-prints` (utils/rollLabels.js; MobileWarehouseApp.jsx:83,138) →
  `prints_count`/`label_outdated` salah. Matriks lengkap: lampiran A.7.
- **Aturan dilanggar:** keputusan pemilik "form input di HP lengkap sama dengan desktop".
- **Dampak:** pekerjaan gudang harian (terima transfer, putaway tiba, cek muat) terpaksa ke desktop atau buntu.
- **Rekomendasi:** satu komponen form per tindakan dipakai di dua kulit (desktop/HP), bukan form HP terpisah; daftar
  tindakan HP diturunkan dari daftar izin peran yang sama. Konfirmasi tampilan → B1.
- **Status:** terverifikasi kode.

### FRM-05 · Random check: "Petugas QC" yang dipilih dibuang skema
- **Area:** SPK Inspeksi → Random check · `POST /api/inspections/random-check` → `RandomCheckCreate`
- **Klasifikasi:** bug (data hilang) · **Keparahan:** P2
- **Bukti:** pemilih petugas (RandomCheckModal.jsx:64-67) → payload `assigned_to` (:29); `RandomCheckCreate` tidak punya
  field itu (backend/schemas_inspection.py:78-84) → dibuang (`extra="ignore"`); service `payload.get("assigned_to") or actor.get("id")`
  (inspection_service.py:1495) selalu jatuh ke pembuat. Terdeteksi otomatis oleh `b3b_crossref.py` (satu-satunya DROP nyata).
- **Aturan dilanggar:** isian layar harus tersimpan atau tidak ditampilkan.
- **Dampak:** SPK acak selalu ditugaskan ke pembuat; petugas yang dimaksud tidak menerima tugas.
- **Rekomendasi:** tambahkan `assigned_to: str = ""` ke model + validasi user aktif ber-izin QC; penjaga umum `extra="forbid"` (INP-13).
- **Status:** **terverifikasi API** (§2 #11): diminta `assigned_to: user_03f0d6ed87f7` (petugas QC), tersimpan `user_whadmin_01` (pembuat).

### FRM-06 · Field skema yang tidak punya isian di layar (dan satu yang dibuang)
- **Area:** beberapa form · **Klasifikasi:** fitur belum ada / bug · **Keparahan:** P2
- **Bukti:**
  - Terima hasil makloon: `supplier_dn` (no. SJ mitra) dan `weight_kg` per roll ada di `MakloonReceiveIn` (schemas_makloon.py:164,177)
    tetapi tidak di body (MkoStepModals.jsx:145-151); LOT diisi otomatis `${output_sku}-${mkoNumber}-1` (:127) padahal skema
    menulis "LOT WAJIB manual (nomor lot dari makloon)" (schemas_makloon.py:159); grade bawaan "A".
  - Retur beli "Kirim ke supplier": `lifecycleAct(r, "ship", {})` (PurchaseReturns.jsx:572) — `SupplierShipInput.carrier/tracking_no/notes`
    (schemas_purchasing.py:465-468) tak pernah terisi, padahal linimasa membacanya (ReturnDetailPanel.jsx:64); tanpa konfirmasi.
  - Lokasi (site) baru: FE mengirim `country/country_code` lewat `pickLoc` (WarehouseMasterView.jsx:199) → `SitePayload` tak
    punya field itu (warehouse_sites.py:15-23) → **dibuang**; `normalize_location` jatuh ke bawaan ID (wilayah_service.py:134-138).
  - Daftar awal HP: `label_raw` ada di `RegLineIn` (initial_registration.py:47) tetapi tidak dikirim (MobileRegistration.jsx:113-116).
  - Karantina retur: `notes` selalu `""` (ReturnQuarantinePanel.jsx:111-121); baris SJ GRN: bruto/netto tidak bisa diubah
    setelah dibuat (GrnLineRow.jsx:101); master grade: `description` tidak ada isiannya; lot: `shade_ref` di state tanpa isian
    (LotActionModals.jsx:296); potong SO: `note` tak di layar; transfer terima/exception: `evidence`, `code` tak di layar.
- **Aturan dilanggar:** "input lengkap sesuai schema".
- **Dampak:** no. SJ mitra & berat hilang dari jejak makloon; RMA tanpa resi; negara lokasi salah; lot makloon bukan nomor mitra.
- **Rekomendasi:** per field: tampilkan isian (bila memang data operasional) atau hapus dari skema; penjaga otomatis
  "field skema tanpa isian & tanpa penurun server" (§7, G-FORM-02).
- **Status:** terverifikasi kode.

### FRM-07 · "Kapasitas bin pertama (roll)" di form Gudang baru tidak berlaku
- **Area:** Data Gudang → Gudang baru · `POST /api/warehouses` → `WarehousePayload`
- **Klasifikasi:** bug · **Keparahan:** P2
- **Bukti:** disimpan `{"code": payload.bin_code, "capacity": payload.bin_capacity}` (warehouses.py:227); pagar kapasitas membaca
  `capacity_rolls` (placement_rules.py:102; location_service.py:71-87). Bawaan blueprint juga `"capacity": 5000.0`
  (warehouse_profile_service.py:350). Label & bawaan 1000 di WarehouseCreateModal.jsx:46-49 / WarehouseMasterView.jsx:51.
- **Aturan dilanggar:** isian layar harus berefek; satu nama field per konsep.
- **Dampak:** bin pertama tercatat "tanpa batas kapasitas"; pengguna mengira sudah dibatasi.
- **Bukti data (`kn_test_trial`):** **914 bin hanya punya `capacity`**, 10 bin ber-`capacity_rolls` → pagar kapasitas roll tidak
  berlaku untuk hampir semua bin. (`capacity` lama bermakna panjang, mis. 100000; `capacity_rolls` = jumlah roll — dua konsep satu nama.)
- **Rekomendasi:** simpan ke `capacity_rolls`; putuskan arti `capacity` lama (panjang) vs `capacity_rolls` (roll) → B3a (SSOT field kapasitas).
- **Status:** terverifikasi kode + data.

### FRM-08 · Nama pelaku transfer diambil dari klien
- **Area:** Transfer · `POST /api/transfers`, `/approve`, `/reject` · **Klasifikasi:** bug (integritas jejak) · **Keparahan:** P2
- **Bukti:** `"requested_by": payload.requested_by` (transfers.py:292), `approved_by: payload.approved_by` (:596,612),
  `rejected_by` (:652); FE mengirim `user?.name || "Manager"` (TransferManagement.jsx:142,182,210,222); bawaan skema
  "Warehouse User"/"Manager" (schemas.py:644,679,684,690); ditampilkan di TransferList.jsx:71-77.
- **Aturan dilanggar:** pelaku = sesi server (`actor["name"]`), bukan isian.
- **Dampak:** riwayat persetujuan bisa dipalsukan lewat API; nilai "Manager" generik tersimpan.
- **Rekomendasi:** isi dari `actor`; hapus field dari skema (atau abaikan).
- **Status:** **terverifikasi API** (§2 #12, #15): `requested_by:"Direktur Utama"` tersimpan apa adanya. **Data:**
  `warehouse_transfers.requested_by` ∈ {"Budi Santoso", **"Warehouse User"**}, `approved_by` ∈ {null, **"Manager"**} — nilai bawaan skema sudah tersimpan di data.

### FRM-09 · K-14 "alasan minimal 5 huruf" belum ditegakkan server di 25 jalur
- **Area:** lintas form · **Klasifikasi:** bug aturan / inkonsistensi · **Keparahan:** P2
- **Bukti (server menerima kosong / 1 huruf / spasi / teks tetap):**

  | # | Jalur | Server | Layar |
  |---|---|---|---|
  | 1 | Eskalasi inbound / outbound (query) | `reason: str = "Qty tidak sesuai…"` tanpa min (inbound_receiving.py:166; outbound_picking.py:262) | tidak kosong |
  | 2 | Catatan selesaikan eskalasi | tanpa min (inbound_receiving.py:231; outbound_picking.py:318) | FE saja |
  | 3 | QC kedatangan — tolak barang | `reason: str = ""` (schemas_purchasing.py:583) | opsional (QCInspection.jsx:348-351) |
  | 4 | Override grade roll | tidak kosong saja (grade_service.py:83) | `!reason.trim()` (RollGradePanel.jsx:198) |
  | 5 | Tutup PO kurang terima | `POCloseRequest.reason = ""` (schemas_purchasing.py:243) | ConfirmModal min 0 |
  | 6 | Rencana QC "Tidak wajib" | tanpa alasan (qc_service.py:247-263) | – |
  | 7 | Alasan override toleransi terima | tidak kosong saja (receiving_uom_service.py:486-487) | askReason |
  | 8 | Tolak / selisih GRN | `min_length=5` tanpa strip → 5 spasi lolos (schemas_goods_receipt.py:22,126) | askReason |
  | 9 | Tolak / batal transfer | `reason: str = ""`; batal opsional (schemas.py:683-685; transfers.py:748) | askReason(5) |
  | 10 | Tolak / setujui opname | tanpa panjang; alasan bawaan "Disetujui sesuai hasil cycle count" (cycle_count.py:49-54) | tidak kosong |
  | 11 | Setujui pendaftaran awal | alasan bawaan lolos (initial_registration.py:73) | – |
  | 12 | Lot split/merge/rework/status | `reason: str = ""` (schemas_lots.py:41-65; lot_service.py:415,446,485,526) | tidak wajib |
  | 13 | PA terima exception (`accept`) | alasan diisi otomatis (putaway_order_service.py:555) | tidak dikirim (PutawayOrdersPanel.jsx:130) |
  | 14 | Tolak / pembalikan retur jual | tanpa min (sales_returns.py:1058-1065) | FE min 5 |
  | 15 | Batalkan write-off retur | `reason` Optional (sales_returns.py:889-892) | tidak kosong |
  | 16 | Tolak retur beli / tolak oleh supplier | tanpa min (purchase_return_service.py:690) | min 0 / "opsional" |
  | 17 | Batalkan order makloon | tanpa min (makloon_order_service.py:1509) | ConfirmModal min 1 |
  | 18 | Batalkan pesanan sample | teks tetap "Dibatalkan dari daftar pesanan sample" (SampleOrdersView.jsx:233) | – |
  | 19 | Potong roll di luar saran | tidak kosong saja (sample_sale_service.py:422-426) | – |
  | 20 | Catatan status kendaraan | tanpa min (fleet_service.py:76) | FE min 5 |
  | 21 | Akui / selesaikan insiden RFID | `note: str = ""` (rfid.py:624-625; rfid_incident_service.py:124) | opsional |
  | 22 | Tutup sesi dokumen gate (V2) | teks tetap "Ditutup dari panel gate" (U300DocSession.jsx:84) | – |
  | 23 | Alasan ubah setelan berisiko | `not (reason or "").strip()` → 1 huruf lolos (config_resolver.py:333); reset & cabut lapisan tanpa alasan (routers/config.py:313,340) | – |
  | 24 | Pensiun tag, routing cross-dock, hapus perangkat | tanpa alasan | askConfirm |
  | 25 | Tutup kasus/terima/tolak antrean periksa (D2), cek muat override, ambil alih | **≥ 5 karakter** (`len(t) < 5`, gate_review_actions.py:31-35) — "....." lolos | "Minimal 5 huruf" |

  Sudah benar (pembanding): penutupan PA (≥10), override penempatan (≥5), terima transfer (≥5), gagal/bongkar logistik,
  keputusan roll retur, disposisi, susut/retur bahan MKO, retur antar-PT, buka kunci gate V2 `_note` (≥5, ≤1000),
  tolak/buka ulang SPK (≥15).
- **Aturan dilanggar:** K-14.
- **Dampak:** keputusan yang menghapus/menolak barang (QC tolak, write-off, tutup PO, batal MKO) tanpa jejak alasan.
- **Rekomendasi:** satu validator server `reason_field(min_letters=5)` (menghitung **huruf**, bukan karakter; strip),
  dipakai semua model ber-alasan; bawaan alasan teks tetap dihapus. Penjaga G-FORM-04 (§7). **Butuh keputusan:**
  apakah K-14 dihitung huruf (`[A-Za-z]`) atau karakter non-spasi.
- **Status:** terverifikasi kode; **terverifikasi API untuk 10 jalur** (§2 #13–21: eskalasi inbound & outbound `"x"`, override grade `"x"`,
  tolak transfer `""`, batal MKO `"a"`, tolak retur beli `""`, tutup PO `""`, status lot `""`, tolak GRN 5 spasi, setelan berisiko `"x"`);
  jalur lain kandidat (tanpa data prasyarat di snapshot).

### FRM-10 · Tombol "Simulasi Scan Semua" pada perintah putaway melewati syarat konfirmasi manual
- **Area:** Lokasi Rak → Perintah Simpan ke Rak · `POST /putaway-orders/{id}/confirm-arrival`
- **Klasifikasi:** bug (kontrol) · **Keparahan:** P1
- **Bukti:** `onClick={() => confirm(o, (o.items || []).map((i) => i.epc).filter(Boolean))}` (PutawayOrdersPanel.jsx:253-257)
  mengirim seluruh EPC sebagai hasil scan; server mencatatnya sebagai "gate-in scan" (putaway_order_service.py:521-523).
  Jalur manual yang setara butuh `wms.approve` + alasan ≥10 (putaway_orders.py:105; service :503-506). Tombol tanpa
  pagar mode simulasi.
- **Aturan dilanggar:** K-RFID (bukti tiba = bacaan nyata); pemisahan izin scan vs approve.
- **Dampak:** pemegang `wms.update` menyatakan semua roll tiba tanpa memindai; jejak tercatat sebagai hasil scan.
- **Rekomendasi:** tampilkan hanya bila `wms.rfid_simulation` aktif dan tandai `source:"simulated"`, atau hapus.
- **Status:** terverifikasi kode.

### FRM-11 · Cek muat: EPC yang diharapkan bisa ditempel manual, asal scan ditentukan klien
- **Area:** Barang Keluar → Pemeriksaan Muat Akhir · `POST /outbound/loading-check/{sid}/scan` (body `dict`)
- **Klasifikasi:** butuh keputusan (integritas) · **Keparahan:** P1
- **Bukti:** sesi mengembalikan daftar `expected` berikut EPC (loading_check_service.py:77,86); FE "Tempel EPC hasil sweep
  handheld…" (LoadingCheckPanel.jsx:157-161); router `str(payload.get("source") or "manual")` (outbound_picking.py:558-559);
  `SCAN_SOURCES = {"manual","device","simulated"}` (rfid_print_service.py:277), hanya `simulated` yang ditolak sebagai bukti
  (:320-324). D2 (`5f1e36e`) menjadikan cek muat **cadangan** bila gedung bergate OUT (loading_check_service.py:298-305), tetapi
  hasil handheld tetap mengikat bila dijalankan.
- **Aturan dilanggar:** RF-07 / gerbang dispatch R4; docs/rfid/KEPUTUSAN_GATE_RFID.md (bukti keluar = bacaan perangkat).
- **Dampak:** dispatch terbuka tanpa sweep fisik; siapa pun dapat mengaku `source:"device"`.
- **Rekomendasi (keputusan pemilik):** `manual` bukan bukti sah (atau izin khusus + alasan); `device` hanya dari kanal
  perangkat ber-kunci; jangan kirim EPC expected ke klien (cukup jumlah/no. roll). Rujuk audit middleware (AUD-MW-xx) — tidak diulang.
- **Status:** terverifikasi kode · uji API kandidat: start sesi → `scan {"epcs":[<expected[].epc>],"source":"device"}` → complete (dugaan `clean`).

### FRM-12 · "Nyalakan" perangkat dan perangkat baru memalsukan detak (heartbeat)
- **Area:** RFID → Perangkat · `PATCH /api/rfid/devices/{id}`, `POST /api/rfid/devices`
- **Klasifikasi:** bug · **Keparahan:** P1
- **Bukti:** `elif allowed.get("status") == "online": … allowed["last_heartbeat"] = now_iso()` (backend/services/rfid_service.py:245-248);
  pembuatan: `"status": … or "online"`, `"last_heartbeat": now_iso()` (:224-225). Data snapshot: satu-satunya perangkat
  `DEV-84134` berstatus `online`.
- **Aturan dilanggar:** status kesehatan = bukti dari perangkat, bukan isian manusia (RF-13).
- **Dampak:** kios menampilkan "Menunggu barang lewat" alih-alih "GATE OFFLINE — TAHAN" selama 120 detik (GateLiveVerdict.jsx:41);
  status printer dianggap online → alarm "label tertahan" tertutup.
- **Rekomendasi:** `last_heartbeat` hanya ditulis kanal perangkat; perangkat baru `status:"belum_terhubung"`; tombol "Nyalakan" hanya `enabled`.
- **Status:** **terverifikasi API** (§2 #23–24): perangkat baru ber-`status:"rusak"` langsung mendapat `last_heartbeat` = saat dibuat;
  `PATCH {"status":"online"}` memperbarui `last_heartbeat` ke saat itu tanpa sinyal dari perangkat.

### FRM-13 · "Simulasi Pindai Area" menulis bacaan & lokasi terakhir nyata
- **Area:** RFID → Lokasi RFID · `POST /api/rfid/reader/scan` · **Klasifikasi:** bug · **Keparahan:** P1
- **Bukti:** `reader_scan` mengambil ≤60 tag dari DB gudang lalu `_record_read` men-set `last_seen_*` tanpa penanda simulasi
  (rfid_service.py:350-369, :312-316); tidak dipagari `wms.rfid_simulation`.
- **Aturan dilanggar:** data simulasi wajib bertanda & terpisah (pola `simulated` di cek muat & V2).
- **Dampak:** tag "Terlacak" tanpa barang fisik; `rfid_reads` tercemar → opname RFID & lokasi tag menyesatkan.
- **Rekomendasi:** tandai `simulated:true`, jangan ubah `last_seen`, pagari dengan setelan simulasi.
- **Status:** terverifikasi kode.

### FRM-14 · Aksi destruktif / posting tanpa konfirmasi
- **Area:** lintas layar · **Klasifikasi:** hambatan UX / risiko · **Keparahan:** P2
- **Bukti:** "Tutup Penerimaan" GRN yang memposting stok & jurnal (GrnReconPanel.jsx:129); hapus baris SJ (GrnLineRow.jsx:204;
  GrnLineCard.jsx:51); batalkan roll hitung (GrnCountPanel.jsx:88); batalkan scan (ScannedRollRow.jsx:154); "Lupakan semua
  koreksi" profil SJ (GrnProfilesPanel.jsx:22,74); karantina Release/Scrap = write-off GL (ReturnQuarantinePanel.jsx:111-121,364);
  "Buang BS" (ReturnDispositionPanel.jsx:56,92); kirim RMA (PurchaseReturns.jsx:239); "Validasi & tutup (BTG)" dengan kotak
  kosong → semua roll exception (PutawayOrdersPanel.jsx:248-249, :92); hapus lokasi permanen (WarehouseMasterView.jsx:205-208,
  `delete_one` :288); hapus node struktur; toggle kemampuan lokasi cutting; setuju/teruskan/batal sample; "Buka Kembali" eskalasi
  (EscalationManagement.jsx:238-246); "Ulangi transaksi" antrean periksa (GateReviewDetail.jsx:183).
- **Aturan dilanggar:** KN_08 "Error Prevention > Error Handling"; pola `askConfirm` yang sudah ada.
- **Dampak:** salah ketuk memposting jurnal / menghapus data tanpa jalan balik.
- **Rekomendasi:** penjaga statik: setiap panggilan ke endpoint ber-efek GL/stok/hapus wajib melewati `askConfirm`/`askReason` (G-FORM-05).
- **Status:** terverifikasi kode (konfirmasi visual → B1).

### FRM-15 · Wizard Kedatangan membuat draf GRN ganda bila unggah foto gagal
- **Area:** Barang Masuk → Kedatangan baru · `POST /goods-receipts` lalu `/files`
- **Klasifikasi:** bug (duplikasi) · **Keparahan:** P2
- **Bukti:** `create` lalu `upload` (GrnCreateWizard.jsx:71-73); kegagalan unggah ditangkap sebagai "Gagal membuat kedatangan."
  (:82), wizard tetap terbuka; menekan ulang memanggil `create` lagi.
- **Dampak:** draf GRN yatim berulang di daftar Kedatangan. **Rekomendasi:** simpan `grn.id` setelah create; ulangi hanya unggah; atau Idempotency-Key.
- **Status:** terverifikasi kode (uji UI → B1).

### FRM-16 · Galat validasi 422 tertelan menjadi pesan umum, atau dirender sebagai objek sehingga layar rusak
- **Area:** GRN (±9 panel), QC kedatangan, label printer · **Klasifikasi:** bug · **Keparahan:** P2
- **Bukti:** `errText` GRN: `if (d && typeof d === "object") return d.message || (d.errors||[]).join(" ") || fallback;` — array 422
  juga "object", cabang `Array.isArray` tak tercapai (frontend/src/features/wms/grn/grnApi.js:39-41) → "Aksi gagal."
  QCInspection.jsx:139 `setFormErr(e.response?.data?.detail …)` → FormModal merender `{error}` dalam `<p>` (FormModal.jsx:149-152)
  → objek sebagai anak React; LabelPrinterModal.jsx:36,43,169 (`parseInt("")` → `NaN` → 422 array → `<p>{error}</p>`).
- **Aturan dilanggar:** INV-UI-03 (galat backend tidak senyap & terbaca); KN_08 Error states.
- **Dampak:** pengguna tidak tahu isian mana yang salah (mis. qty −5 pada baris SJ); layar produk dapat rusak.
- **Rekomendasi:** semua layar memakai `utils/apiError.apiErrorText` (sudah menangani array); penjaga statik: `setError(e.response?.data?.detail)` mentah dilarang (G-FORM-06).
- **Status:** terverifikasi kode (crash = kandidat uji UI → B1).

### FRM-17 · Elemen form tidak seragam (sensus) — → B1
- **Area:** 180 berkas cakupan · **Klasifikasi:** inkonsistensi · **Keparahan:** P3
- **Bukti (`b3b_form_census.py`):** 668 tombol: `secondary-button` 171, **Tailwind `bg-[#hex]` buatan sendiri 162**,
  `primary-button` 148, `btn-*` 29, kelas lain 124; isian: `.field` 191, Tailwind mentah 55, `.form-input` 31, `.input` 7,
  tanpa kelas 57; pembungkus: FormModal 43, DetailModal 10, ConfirmModal 7, sisanya inline/drawer buatan sendiri
  (WarehouseProfileDrawer memakai "Tutup" bukan "Batal"; LabelPrinterModal overlay sendiri); **atribut `required` 1**,
  **`maxLength` 3**, **`FormSection` 0** di cakupan; 284 label untuk 658 kontrol — ±35 isian hanya ber-placeholder (CycleCount.jsx:438-447,
  InitialRegistration.jsx:110-134, GrnLineRow LineEditForm, LoadingCheckPanel, MobileTaskActions); tanda wajib tiga gaya
  (`*` di label, `*` di placeholder "Nama penerima *", tanpa tanda — MkoStepModals, wizard GRN, grade inspeksi); urutan kaki
  modal dua gaya ([Selesaikan][Batal] GRCatchWeightModal.jsx:99-103 vs [Batal][Simpan] QCInspection.jsx:265-270); target sentuh
  HP 34–36 px (`.m-act` mobile.css:29-31; `py-2`) < 44 px KN_08:404; `grid-cols-2` tanpa breakpoint HP (TransferCreateForm.jsx:20).
- **Aturan dilanggar:** KN_08 (komponen baku, Quality Checklist), FormModal/FormSection sebagai standar.
- **Rekomendasi:** §7 G-FORM-07/08 (tombol hanya kelas baku; isian wajib berlabel; wajib = `required` + `*` dari satu komponen `Field`).
- **Status:** terverifikasi kode (ukuran piksel nyata → B1).

### FRM-18 · Pemilih grade bergantung izin `grade_master.view` — petugas gudang mendapat daftar kosong; tiga sumber grade
- **Area:** Inspeksi 4-point, isi hasil SPK, lembar inspect, ukur roll · **Klasifikasi:** bug / hambatan · **Keparahan:** P1
- **Bukti:** `GET /api/master/grades … .catch(() => setGrades([]))` (RollInspectionModal.jsx:61; InspectLineModal.jsx:50;
  InspectSheetGrid.jsx:60); izin lihat master grade hanya manager, md, sales_admin, warehouse_admin, md_quality, qc
  (permissions_config.py:608-609), sedangkan peran `warehouse` punya `qc: ["view","inspect"]` (:583); `qc.grade_from_points`
  bawaan False (config_catalog_core.py:780) → simpan ditolak "Pilih grade roll …". Sumber lain: `useDomainEnums().options("grade")`
  (7 layar, hanya grade aktif) dan `.items()` tanpa saring (ScannedRollRow.jsx:138, grade nonaktif tampil lalu ditolak server);
  stok awal grade A/B/C/Reject di-hard-code (InitialStockForm.jsx:64-68); HP pendaftaran grade teks (MobileRegistration.jsx:187).
- **Aturan dilanggar:** "form yang seharusnya ambil data bukan custom input"; satu sumber pilihan per master.
- **Dampak:** inspeksi 4-point oleh petugas gudang terblokir; grade tak seragam antar layar.
- **Rekomendasi:** semua pemilih grade lewat `useDomainEnums().options("grade")` (sudah disinkron dari `md_grades`); larang daftar grade di kode (perluas `verify_uom_vocab` aturan D ke grade).
- **Status:** terverifikasi kode · uji UI dengan akun `warehouse` → B1.

### FRM-19 · Pengaturan gudang/penerimaan: daftar regex dipecah di koma; JSON harga OCR di isian teks — server tidak memvalidasi isi
- **Area:** Pengaturan › Gudang & Mutu / Penerimaan & OCR · `PUT /api/config/values`
- **Klasifikasi:** bug · **Keparahan:** P1
- **Bukti:** editor daftar: `.split(",")…map(x => Number.isNaN(Number(x)) ? x : Number(x))` (frontend/src/features/settings/config/SettingEditor.jsx:44-53);
  nilai bawaan `receiving.client_po_patterns` memuat koma di kuantor: `(?P<core>\d{3,5})/(CST|SCB)/\d{4}` (backend/config_catalog_ops.py:249-250;
  services/dn_rules.py:122) → sekali disunting, terbelah menjadi `(?P<core>\d{3` dan `5})/…`; server `if typ == "list": … return value`
  tanpa cek (config_registry.py:345); dipakai `re.finditer(p, …)` tanpa `try` (dn_rules.py:131). `receiving.ocr_price_table` bertipe
  `text` (config_catalog_ops.py:303) berisi JSON, diurai `json.loads(pt)` tanpa `try` (goods_receipt_ocr_service.py:37).
  Editor juga membuang koma di akhir saat mengetik → butir baru sulit ditambah.
- **Aturan dilanggar:** INV-CFG (nilai setelan divalidasi registri); pemilih/isian sesuai tipe.
- **Dampak:** OCR kedatangan barang galat 500 untuk semua GRN setelah satu suntingan wajar.
- **Rekomendasi:** editor baris-per-butir untuk tipe `list`; tipe `regex_list` & `json_map` di registri dengan validasi `re.compile`/skema JSON di `coerce`.
- **Status:** **terverifikasi API** (§2 #26–27): regex tak valid diterima 200 (dipakai `re.finditer` tanpa `try` saat OCR/sampel OCR);
  `ocr_price_table = "{rusak"` diterima 200 lalu `GET /goods-receipts/usage` → **500** (`json.loads`).

### FRM-20 · Pengaturan: angka tanpa batas, jalur lama `PUT /settings` dict bebas, setelan "tombol palsu"
- **Area:** Pusat Pengaturan (gudang/mutu/penerimaan) · **Klasifikasi:** bug / duplikasi · **Keparahan:** P2
- **Bukti:** `int`/`decimal` tanpa min/max: config_catalog_ops.py:246,285,288,291,297 (`_bounded` hanya bila min/max ada,
  config_registry.py:362-368) → `receiving.ocr_max_pages=-1` diterima; `PUT /settings` menerima `inventory`/`allocation`
  `Optional[Dict[str, Any]]` (schemas.py:731-732) lalu `$set` seluruh seksi (routers/settings.py:71-81) — melewati registri,
  riwayat append-only, alasan wajib, dan menghapus kunci lain di seksi; `lot.number_format` aktif & bisa diubah tetapi
  `lot_service.py:133-136` memakai `f"LOT-{ym}-"` keras (INV-CFG-01 "tombol palsu"); ambang grade `float(th.get("a_max", 20.0) or 20.0)`
  → nilai 0 diganti 20 (qc_inspection_service.py:33), `max_points` master grade menimpa setelan (:113-115) — dua sumber;
  `inventory.default_uom` bertipe `text` (config_catalog_core.py:522) → `products.base_unit` tanpa cek master satuan;
  pesan validasi menyebut kunci teknis (`'{key}' harus angka bulat`) dan angka bulat dibulatkan diam-diam.
- **Aturan dilanggar:** INV-NUM-01 (diperluas ke registri), INV-CFG-01, INV-UOM-02.
- **Rekomendasi:** batas wajib untuk setiap setelan angka (penjaga G-CFG-01); tutup/arahkan `PUT /settings` ke registri; status `not_used` untuk setelan tanpa konsumen; satu sumber ambang grade; pemilih satuan dari master.
- **Status:** **terverifikasi API** (§2 #28–29): `ocr_max_pages=-1` → 200; `PUT /settings {"scope":"global","inventory":{"min_cut_qty":-5}}`
  → 200 dan seksi `inventory` global **kehilangan 5 kunci** (sebelum: `default_uom`, `min_cut_qty:0.5`, `stock_analytics`, `reorder`,
  `intercompany_transfer_required`; sesudah: hanya `min_cut_qty:-5`). Jalur lama ini masih dipakai FE untuk seksi lain
  (IntercoPaymentSchedule.jsx:36, ReturnAssumptionsPanel.jsx:36).

### FRM-21 · Antrean periksa gate (D2): form tindakan baku, sisa celah kecil
- **Area:** RFID › Monitor Gerbang › Antrean periksa (baru di `5f1e36e`) · `/api/rfid/v2/ops/reviews/*`
- **Klasifikasi:** inkonsistensi / fitur belum ada · **Keparahan:** P3
- **Bukti (positif dulu):** satu `FormModal` baku untuk 6 tindakan, izin `wms.approve` terpisah dari `wms.scan`, audit per
  tindakan, saringan divalidasi server (rfid_v2_review.py:59-73), CAS per kasus (gate_review_actions.py:42-58), ≤500 roll per
  tindakan (:61-63). Celah: (a) alasan dihitung **karakter** (`len(t) < 5`, :31-35; FE `text.trim().length < 5`,
  GateReviewDetail.jsx:176) padahal label "Minimal 5 huruf" — "....." lolos; (b) `textarea` tanpa `maxLength`, server memotong
  500 diam-diam (`t[:500]`); (c) tidak ada "pilih semua roll" (kasus `rolls_missing` bisa ratusan roll); (d) "Ulangi transaksi"
  tanpa konfirmasi; (e) koreksi klaim crossing (`/crossings/release|move`, alasan ≥10) **belum punya layar**.
- **Rekomendasi:** validator K-14 bersama (FRM-09); `maxLength={500}` + penghitung; kotak "pilih semua yang perlu tindakan"; askConfirm pada ulangi; layar koreksi klaim (atau catat sebagai sengaja API-saja).
- **Status:** terverifikasi kode.

### FRM-22 · Tombol tampil tetapi server menolak / fitur tak terjangkau / modal tanpa status sibuk
- **Area:** retur jual, eskalasi, tugas WMS · **Klasifikasi:** bug izin / kode mati · **Keparahan:** P2
- **Bukti:** "Tandai barang sampai" tampil bagi pemegang `wms.scan` (`canScan`, ReturnDetail.jsx:78,278; ReturnShipmentPanel.jsx:157-160)
  tetapi `/milestone` mewajibkan `sales_return.update` (sales_returns.py:511), yang tidak dimiliki `warehouse`/`warehouse_admin`
  (permissions_config.py:408,516); "Ambil alih tugas" (`TaskTakeoverButton`) hanya dipakai `ScannerTaskPanel.jsx`, yang **tidak diimpor
  di mana pun** dan berisi data contoh `prod_batik_mega`/`wh_jakarta` (ScannerTaskPanel.jsx:18); FormModal "Selesaikan eskalasi"
  tanpa `busy` (EscalationManagement.jsx:267-269) → klik ganda berakhir 409.
- **Rekomendasi:** turunkan visibilitas tombol dari izin endpoint yang sama; putuskan pemasangan ambil-alih atau hapus berkas mati; `busy` wajib di FormModal ber-`onSubmit`.
- **Status:** **terverifikasi API**: akun `warehouse` → `POST /sales-returns/{id}/milestone` → 403 "Permission ditolak: sales_return.update"
  (sementara tombolnya ditampilkan untuk pemegang `wms.scan`).

### FRM-23 · `GET /api/inbound/qc/tasks/{task_id}/rolls` tanpa cek badan usaha (baca lintas PT)
- **Area:** Antrean QC kedatangan → Inspeksi 4-point · **Klasifikasi:** bug (tembus PT) · **Keparahan:** **P0**
- **Bukti:** endpoint hanya `find_one({"id": task_id})` lalu `rolls_for_task(task_id)` (backend/routers/qc_inspection.py:31-38);
  endpoint saudara `/plan` memakai `_qc_task()` yang memanggil `assert_entity_access(task, "wms_tasks", …)` (:41-54);
  `rolls_for_task` hanya menyaring `qc_task_id` (qc_inspection_service.py:356-359).
- **Aturan dilanggar:** isolasi entitas (`entity_scope`, AUDIT_ISOLASI_ENTITAS).
- **Dampak:** pengguna PT A membaca roll_no, lot, dye lot, grade, status tahanan roll PT B bila mengetahui id tugas.
- **Rekomendasi:** ganti `find_one` dengan `_qc_task(task_id, request)`; tambahkan uji isolasi untuk semua endpoint `/{id}/…` di router cakupan (G-SCOPE-01, §7).
- **Status:** **terverifikasi API** (§2 #4): operator PT Sukacita → `GET …/tasks/wms_bef96c0e9725/rolls` (tugas PT Cipta Sandang) **200**,
  sedangkan `/plan` tugas yang sama **404**. Di snapshot tugas itu kebetulan belum punya roll ber-`qc_task_id` (respons `[]`), jadi
  belum ada isi yang bocor — tetapi gerbangnya terbukti terbuka.

### FRM-24 · Koleksi/skema baru tidak terdaftar & konsep yang tergandakan — → B3a
- **Area:** backend WMS-RFID · **Klasifikasi:** duplikasi / butuh keputusan · **Keparahan:** P3
- **Bukti (`b3b_collections.py`):** 53 koleksi bertema gudang/RFID dipakai kode; **29 tidak terdaftar** di ENTITY_REGISTRY.md:
  `putaway_orders`, `warehouse_sites`, `fleet_vehicles`, `logistics_deliveries`, `repair_orders`, `registration_area_status`,
  `location_corrections`, `location_migrations`, `bin_locks`, `roll_scans`, `roll_label_prints`, `supplier_roll_claims`,
  `return_create_locks`, `sample_price_master`, `fact_stock_daily`, `rfid_print_jobs`, `rfid_verify_sessions`, `rfid_incidents`,
  `rfid_cycle_counts`, `rfid_observations`, `rfid_passages`, dan 8 koleksi `rfid_v2_*` (`bindings, configs, crossings,
  doc_sessions, event_ids, health, overflow, passages`) — ditambah `rfid_v2_reviews`, `rfid_v2_claim_corrections`,
  `rfid_v2_summaries`, `rfid_v2_events` (D2). Kandidat duplikasi konsep: dua master kendaraan `vehicles` (terdaftar, vehicle_logs.py:21)
  vs `fleet_vehicles` (fleet_service.py:12); `putaway_orders` vs `warehouse_transfers` (dua dokumen pindah roll antar gudang dengan
  siklus kirim→tiba→exception); alamat di `warehouse_sites` dan di `warehouses`; jalur RFID v1 (`rfid_passages`, `rfid_verify_sessions`)
  berjalan sejajar v2 (`rfid_v2_passages`, `rfid_v2_doc_sessions`); entri registry `warehouse_locations`/`rfid_events` (ENTITY_REGISTRY.md:2727-2730)
  tidak punya kode (struktur nyata di `warehouses.zones`). Positif: pendaftaran awal memakai ulang `cycle_count_sessions` (`mode=registration`).
- **Aturan dilanggar:** pemilik "tidak membuat tabel/schema baru"; ENTITY_REGISTRY sebagai SSOT.
- **Rekomendasi:** daftarkan semua koleksi hidup; putuskan penyatuan master kendaraan dan v1↔v2 → **B3a** (SSOT & skema penuh).
- **Status:** terverifikasi kode.

---

## 4. Temuan — INPUT/OUTPUT (INP)

### INP-01 · Scan Terima (mode lama): "Bin Location *", "Roll ID", "Lot" adalah teks bebas yang mengisi field rujukan stok
- **Area:** Barang Masuk (tugas inbound) · `POST /inbound/tasks/{id}/scan-receive` → `/complete`
- **Klasifikasi:** bug (isian bebas untuk rujukan) · **Keparahan:** P1
- **Bukti:** `<input type="text" value={scanData.bin_id} … placeholder="A1-01" />` (frontend/src/features/wms/InboundScanForm.jsx:63-67);
  router `"roll_id": payload.roll_id or …`, `"bin_id": payload.bin_id or …` tanpa validasi (backend/routers/inbound_receiving.py:121-122);
  roll lahir dengan `bin_id` dari tugas (inbound_complete_service.py:364) dan `rfid_tag_id = task.roll_id` (:408). Bin di master
  ber-id `bin_…` dengan kode `A1-01` (warehouse_profile_service.py:350); resolver `placement_rules.resolve_bin(id|kode)` sudah ada
  (placement_rules.py:80-89) dan dipakai putaway scan-label (inbound_scan_label.py:248-252) — tidak di sini. Label "*" tetapi tidak wajib di layar maupun skema.
- **Aturan dilanggar:** "form yang seharusnya ambil data bukan custom input".
- **Dampak:** roll dengan `bin_id` kode/fiktif → okupansi (dicocokkan per id, location_service.py:137) salah, roll tidak masuk antrean
  "belum ditempatkan" (:233); "Roll ID" diketik dianggap tag RFID → opname RFID menganggap roll bertag padahal tag tidak ada.
- **Rekomendasi:** pemilih bin dari struktur gudang tugas + `resolve_bin` di server (tolak bila tak ditemukan); hapus pemetaan roll_id→rfid_tag_id (tag lewat `/inbound/rolls/{id}/tag`); "Lot" dari pemilih lot/penurun server.
- **Status:** **terverifikasi API** (§2 #6): `scan-receive {"actual_qty":1,"bin_id":"BIN-FIKTIF-B3B","roll_id":"ROLL-FIKTIF-B3B"}` → 200,
  keduanya tersimpan di tugas (dipakai saat `complete`). **Data:** di snapshot hanya 2 dari 607 `bin_id` roll yang tak cocok struktur
  (`bin_sim_hilang_*`, simulasi) — risiko belum terwujud di data uji, celahnya terbuka.

### INP-02 · Opname: "Bin ID (opsional)" teks bebas → *expected* 0 → roll surplus + jurnal di alamat yang tidak ada
- **Area:** Stok, Transfer & Opname → Sesi opname → Tambah item · `POST /cycle-count/sessions/{sid}/items`
- **Klasifikasi:** bug (isian bebas untuk rujukan) · **Keparahan:** **P0**
- **Bukti:** `<input placeholder="Bin ID (opsional)" value={addItem.bin_id} …>` (frontend/src/features/inventory/CycleCount.jsx:283);
  server hanya `.strip()` (backend/routers/cycle_count.py:119) lalu `expected = scope_qty(…, bin_id)` menyaring
  `inventory_rolls.bin_id == bin_id` (stock_count_service.py:29-40; cycle_count.py:130); saat disetujui, selisih positif membuat
  roll `create_inbound_roll(…, bin_id=item.get("bin_id"))` + nilai + jurnal (stock_count_service.py:110-118). Bin ber-id `bin_…`,
  yang tercetak di rak adalah kode (`A1-01`). Panel opname per roll memakai pemilih bin dari `/warehouses/{id}/locations`
  (RollCountPanel.jsx:45,87) — dua cara dalam satu menu. Bin mentah juga ditampilkan (CycleCount.jsx:313).
- **Aturan dilanggar:** "form yang seharusnya ambil data bukan custom input"; SSOT roll (stok = roll fisik di alamat sah).
- **Dampak:** operator yang mengetik kode bin yang benar (bukan id internal) mendapat *expected* 0 untuk stok yang ada;
  menghitung fisiknya → surplus → **stok ganda + jurnal persediaan** di alamat fiktif; salah ketik apa pun berakibat sama.
- **Rekomendasi:** ganti dengan pemilih bin (sama dengan RollCountPanel); server `resolve_bin` → simpan id, tolak bila tak dikenal.
- **Status:** **terverifikasi API** (§2 #5): gudang RCM-WOVEN, produk `prod_0b9b511406f0`, bin yang sama — `bin_id:"W01-L2-03"` (kode rak)
  → `expected_qty` **0,0**; `bin_id:"bin_sim_rcm_woven_w01_l2_03"` (id) → **240,0**. Tahap persetujuan (roll surplus + jurnal) dibuktikan dari kode
  (stock_count_service.py:110-118), tidak dijalankan agar jurnal uji tidak bertambah.

### INP-03 · HP "Bin / lokasi saya" teks bebas mengisi `bin_id`
- **Area:** HP → Pindai · `POST /api/rfid/roll-scans` · **Klasifikasi:** inkonsistensi · **Keparahan:** P2
- **Bukti:** MobileWarehouseApp.jsx:112,122,171; `(bin_id or "").strip() or None` → `roll_scans.bin_id` dan `inventory_rolls.last_scan.bin_id`
  tanpa cek struktur (rfid.py:140,211).
- **Rekomendasi:** pindai/pilih bin dari struktur; simpan id + kode. **Status:** terverifikasi kode; `roll_scans.bin_id` di snapshot masih kosong.

### INP-04 · Satuan baris SJ & packing list GRN teks bebas; `goods_receipts` di luar penjaga satuan
- **Area:** Barang Masuk → Tinjau SJ · `POST/PATCH /goods-receipts/{id}/lines` · **Klasifikasi:** inkonsistensi · **Keparahan:** P2
- **Bukti:** `placeholder="yd / m / kg"` (GrnReviewPanel.jsx:80; GrnLineRow.jsx:110,118); editor sampel OCR untuk konsep yang
  sama memakai master satuan (GrnOcrSampleEditor.jsx:28,50). Start-count memblokir baris PO yang satuannya tak terkonversi
  (goods_receipt_service.py:615-617), tetapi baris barang sisa makloon memakai teks apa adanya (:382-384 →
  goods_receipt_close_service.py:573); `goods_receipts` tidak ada di `UNIT_DOC_FIELDS` (uom_service.py:137-154) sehingga INV-UOM-02 tak memeriksanya.
- **Aturan dilanggar:** INV-UOM-02 aturan D (pemilih satuan dari master).
- **Rekomendasi:** `KNSelect` satuan dari `useUomConversions()`; tambahkan `goods_receipts.lines[].declared.unit` & `packing_list.unit` ke `UNIT_DOC_FIELDS`.
- **Status:** terverifikasi kode; data snapshot: satuan baris SJ hanya `meter` (cocok master) — celah belum terwujud.

### INP-05 · Stok awal: satuan, grade, dan bin tidak divalidasi; pilihan grade di layar memuat nilai di luar master
- **Area:** Stok → Stok awal · `POST /api/inventory/initial-stock` → `RollPayload` · **Klasifikasi:** isian bebas / bug data · **Keparahan:** P1
- **Bukti:** `"unit": payload.unit, "grade": payload.grade`, `"bin_id": payload.bin_id or None` (inventory.py:474-479); `unit: str = "meter"`,
  `grade: str = "A"` (schemas.py:713-714). Pilihan grade di layar diketik keras `A / B / C / Reject` (InitialStockForm.jsx:64-68) —
  master grade di data: `A, A1, B, B1, BS, C` → **"Reject" bukan grade sah** dan A1/B1/BS tidak bisa dipilih; jalur UI biasa pun
  menghasilkan grade di luar master. (`quantity` 0 ditolak service "quantity harus > 0" — baik.)
- **Rekomendasi:** validasi satuan (master UOM), grade (`domain_registry.require_grade`), `resolve_bin`; pemilih grade dari `useDomainEnums`.
- **Status:** **terverifikasi API** (§2 #7): `{"unit":"hasta","grade":"ZZ","bin_id":"bin_tidak_ada","quantity":1}` → 200, roll
  `roll_025bfc18050f` `available` dengan unit `hasta`, grade `ZZ`, bin `bin_tidak_ada` tersimpan.

### INP-06 · Kurir, sopir, kendaraan diketik bebas; plat manual melewati master armada; dua master kendaraan
- **Area:** Pengiriman, retur (pengembalian barang, perjalanan) · **Klasifikasi:** inkonsistensi / butuh keputusan · **Keparahan:** P2
- **Bukti:** plat manual tetap ada meski kendaraan master ada (DeliveryCreateModal.jsx:147), kendaraan non-available hanya
  dinonaktifkan di pemilih (:79); `assert_assignable` hanya bila `vehicle_id` terisi (logistics_service.py:191-195, :553-555);
  ubah plat/sopir di rincian tidak mengosongkan `vehicle_id`/`driver_user_id` (DeliveryDetailModal.jsx:198-207;
  logistics_service.py:433-449); retur: `courier`, `driver`, `vehicle` teks (ReturnShipmentPanel.jsx:99-114), dipotong diam
  120/60/40 huruf (return_service.py:703-714); `carrier` (ReturnTimelinePanel.jsx:74-75); `courier_name`, `service_level`
  (DeliveryCreateModal.jsx:136,140). Tidak ada master ekspedisi; master kendaraan ganda `vehicles` vs `fleet_vehicles` (FRM-24).
- **Dampak:** kendaraan berstatus perawatan dipakai dengan mengetik platnya; armada X "di jalan" padahal plat yang tampil Y;
  tugas tetap muncul di "milik saya" sopir lama; rekap per ekspedisi mustahil.
- **Rekomendasi:** pemilih armada & sopir (akun ber-peran sopir) untuk armada sendiri; plat manual hanya untuk kendaraan luar
  dan ditolak bila plat ada di master; **keputusan pemilik:** master ekspedisi & penyatuan master kendaraan (→ B3a).
- **Status:** terverifikasi kode. **Data:** `courier_name` ∈ {"JNE","LALAMOVE"}, retur `courier` = "J&T Express", `vehicle_plate`/`driver_name`
  kosong, `fleet_vehicles` & `vehicles` kosong di snapshot — belum ada variasi ejaan karena data logistik uji masih tipis.

### INP-07 · Perangkat RFID: lokasi berupa teks, arah/status tanpa enum, tidak ada form Ubah, hapus tanpa cek rujukan
- **Area:** RFID / Pengaturan › Perangkat · `POST/PATCH/DELETE /api/rfid/devices` · **Klasifikasi:** inkonsistensi + bug · **Keparahan:** P2
- **Bukti:** `DOCKS = ["Dock Terima","Dock Kirim","Gate Utama"]`, `value: z.name || z.id` (RfidDevicesView.jsx:48,51) → `location` teks;
  seed memakai "Dock Masuk"/"Zone A" (rfid_service.py:267-269) di luar daftar; `location: Optional[str]` (rfid.py:39); `direction =
  payload.get("direction") or (…)` tanpa cek in/out (rfid_service.py:217,236) — label `d.direction === "in" ? "MASUK" : "KELUAR"`
  (RfidGateMonitorView.jsx:119) menampilkan arah ngawur sebagai KELUAR; `status` bebas; `DevicePatch` mendukung name/location/direction
  tetapi UI tanpa form Ubah (koreksi = hapus + buat ulang → kunci API & riwayat hilang); `delete_one` tanpa cek `gate_config.pairs`,
  `rfid_v2_bindings`, lease print job (rfid_service.py:253-257). Data: `DEV-84134` `location: ""`.
- **Rekomendasi:** enum `in|out` (gate) / `n/a`; status hanya dari perangkat (FRM-12); simpan `location_node_id` + label; form Ubah; tolak hapus bila dirujuk (nonaktifkan saja).
- **Status:** **terverifikasi API** (§2 #23): `{"type":"gate","direction":"samping","status":"rusak","location":"Zona Fiktif"}` → 200, tersimpan apa adanya.

### INP-08 · Teks bebas lain yang mengisi rujukan master
- **Area:** lintas form · **Klasifikasi:** isian bebas · **Keparahan:** P2
- **Bukti:** kategori aturan zona/rak/bin `split(",")` (NodeRulesEditor.jsx:38-39) padahal profil gedung memakai centang dari
  `/product-categories` (WarehouseProfileDrawer.jsx:136-147), server tidak mencocokkan master (warehouse_profile_service.py:58;
  placement_rules.py:38); warna tujuan celup ulang `<input placeholder="mis. Navy 19-4052">` → `target.color_name`
  (RepairCreateModal.jsx:74-75; repair_order_service.py:122) padahal `color_library` + `PantoneFinder` ada; SKU tujuan
  perbaikan = pencarian ketik + chip buatan sendiri, bukan `ProductSelect` (:78-83); profil cacat QC kedatangan dipisah koma
  (QCInspection.jsx:325) padahal SPK punya kamus `meta.defect_codes`; "Bagian" SPK teks (InspectionDetailPanel.jsx:337);
  "Tempel ke lot yang ada" teks — resolver sengaja tidak memakai ulang lot penerimaan lain (KLX-01) dan teksnya masuk
  `legacy_lot_codes` (GRCatchWeightModal.jsx:171-178; lot_service.py:251-275) → isian menyesatkan; grade HP teks (FRM-18).
- **Rekomendasi:** pemilih dari master yang sudah ada (kategori, warna, produk, kode cacat); hapus "Tempel ke lot" atau ganti pemilih lot.
- **Status:** terverifikasi kode.

### INP-09 · Angka tanpa batas / NaN / negatif lolos
- **Area:** kirim, eskalasi, potong, master grade, inspeksi, gudang · **Klasifikasi:** bug · **Keparahan:** P1
- **Bukti:** kirim `qty = max_ship if (ship_qty is None or float(ship_qty) <= 0) else round(...)` lalu `if qty > max_ship + EPS` —
  ≤0 berarti kirim semua, `nan` lolos semua perbandingan (shipment_service.py:63-64); selesaikan eskalasi inbound
  `update_data["expected_qty"] = adjusted_qty` tanpa validasi (inbound_receiving.py:271-273), outbound NaN lolos (outbound_picking.py:369-381),
  FE `type=number` tanpa min (EscalationManagement.jsx:323-330); susut potong `waste: float = 0.0` hanya dicek `< 0`
  (routers/inventory.py:549-552; roll_service.py:621-628) → mutasi `cut_waste` sampai sisa roll habis; panjang potong sample
  `gt=0` tanpa batas terhadap permintaan dan harga pesanan dihitung ulang (sample_sales.py:27; sample_sale_service.py:412-459);
  `GradeIn.max_points` tanpa batas (grade_master.py:17,25); `InspectionLineInspect` gsm/width/delta_e/inspect_length_yard/yard_split
  tanpa batas (schemas_inspection.py:45-62); lat/lng gudang tanpa rentang; 50 dari 87 `<input type="number">` tanpa `min`.
  INV-NUM-01 hanya memindai `schemas*.py` (verify_numeric_bounds.py:137) → model di router (CutConfirmPayload, OrderCutIn,
  StepToleranceIn, MdqCutIn, GRNPartialIn, GradeIn …) dan parameter query tidak terjaga.
- **Aturan dilanggar:** INV-NUM-01.
- **Dampak:** SJ dengan qty NaN; kiriman penuh padahal diminta sebagian; stok dihapus sebagai susut; expected qty negatif.
- **Rekomendasi:** `Field(gt=0, allow_inf_nan=False)` untuk semua qty/panjang (termasuk query: `Query(..., gt=0)`); susut ≤ persen setelan + alasan; perluas INV-NUM-01 ke router & query (G-NUM-02).
- **Status:** **terverifikasi API** untuk `resolve-escalation?adjusted_qty=-10` (§2 #8: tersimpan `expected_qty:-10`, lalu tugas tak bisa
  menerima barang — "melebihi toleransi +2% dari PO (-10, maks -10.2)") dan `max_points:-5` (§2 #9). `ship_qty=nan` **belum terbukti**
  (tertahan syarat tag RFID lebih dulu) — kandidat dari kode (shipment_service.py:63-64).

### INP-10 · Desimal koma Indonesia hilang diam-diam (`parseFloat`/`Number` pada isian teks)
- **Area:** makloon kirim/terima, lembar inspect, packing list GRN · **Klasifikasi:** bug data · **Keparahan:** P1
- **Bukti:** qty dokumen mitra `<input … value={docQty}>` + `parseFloat(docQty)` (MkoStepModals.jsx:106-107,138,150,199-200;
  MakloonOrderDetailPanel.jsx:85) → "12,5" = 12, "1.250,5" = 1,25; lembar inspect `Number("120,5")` = NaN → 0 tersimpan
  (InspectSheetGrid.jsx:76-79; inspection_service.py:1051); packing list "1.234,5" → NaN → roll dibuang diam (GrnLineRow.jsx:18-20).
  Pembanding benar: `DecimalInput`/`parseDecimal` (PendingCutsPanel, RollInspectionModal) — hanya 7 `DecimalInput` di cakupan.
- **Aturan dilanggar:** PS-15/R5 (desimal koma didukung); INV-QTY-01.
- **Rekomendasi:** semua isian qty/panjang memakai `DecimalInput`; penjaga statik: `parseFloat(`/`Number(` atas nilai isian dilarang di form (G-NUM-03).
- **Status:** terverifikasi kode (logika FE).

### INP-11 · Teks tanpa batas panjang; tanggal tanpa format
- **Area:** GRN, PO terima, banyak model · **Klasifikasi:** inkonsistensi · **Keparahan:** P3
- **Bukti:** `GRNDnPatch` (schemas_goods_receipt.py:26-35), `GRNLineIn` (:60-62), `POReceiveItem` (schemas_purchasing.py:521-527),
  `GRCompletePayload` (:569-575), `PAVerifyLabelsPayload.codes` tanpa batas jumlah, akui passage lama tanpa batas (rfid.py:420);
  FE hanya **3** `maxLength`. `date` SJ berupa string bebas.
- **Rekomendasi:** `constr(max_length=…)`/`Field(max_length)` baku per jenis (nomor dok 60, nama 120, catatan 1000); `date` bertipe tanggal.
- **Status:** **terverifikasi API** (§2 #22): `PATCH /dn {"number":"N"×5000,"date":"bukan-tanggal"}` → 200, tersimpan.

### INP-12 · Regex dari isian tanpa escape → galat server
- **Area:** Perbaikan (cari), Lokasi (nama site) · **Klasifikasi:** bug · **Keparahan:** P2
- **Bukti:** `{"$regex": f"^{name}$"}` (warehouse_profile_service.py:262); `q` mentah (repair_order_service.py:44,336; repair_orders.py:99).
- **Rekomendasi:** `re.escape`. **Status:** **terverifikasi API**: `POST /warehouse-sites {"name":"Gudang (Baru"}` → **500**
  (`OperationFailure: Regular expression is invalid: missing closing parenthesis`); `GET /repair-orders?q=(` → **500**.

### INP-13 · Body tanpa skema & kunci asing dibuang diam-diam (sistemik)
- **Area:** semua router cakupan · **Klasifikasi:** inkonsistensi (kontrak input) · **Keparahan:** P2
- **Bukti:** Pydantic 2.13 tanpa satu pun `extra="forbid"` (grep `ConfigDict(`/`extra=` kosong di backend) → kunci salah eja
  dibuang tanpa galat (contoh nyata FRM-05, FRM-06 `country`); **11 endpoint body `dict`** (mis. loading-check scan/override/
  scan-label/simulate-tags, QC plan, hold/release roll, PO variance decide, takeover, akui passage lama); **13 endpoint V2**
  `await _payload(request)` + validasi manual (umumnya baik: sumber manifest, `_note`, saringan antrean); **±9 endpoint tulis via query**
  (`scan-pick`, `dispatch`, `dispatch-batch`, `escalate`, `resolve-escalation`, `loading-check/start`, DELETE transfer `reason`) —
  alasan ikut tercatat di log akses/URL; `int(body.get('roll_limit') or 200)` → 500 bila bukan angka (rfid_v2_ops.py:143).
- **Aturan dilanggar:** kontrak input bertipe; privasi (alasan/data di URL).
- **Rekomendasi:** model baku `KNIn(BaseModel, extra="forbid")` untuk semua body tulis; body untuk data tulis (bukan query);
  daftar pengecualian `dict` beralasan (G-API-01/02).
- **Status:** **terverifikasi API** (§2 #12): `POST /transfers {… "kunci_asing":"harus-ditolak"}` → 200, kunci dibuang tanpa galat.

### INP-14 · `PrintJobPayload.kind` tidak divalidasi — nilai salah menjadi encode tag RFID
- **Area:** RFID → cetak · `POST /api/rfid/print-jobs` · **Klasifikasi:** bug · **Keparahan:** P2
- **Bukti:** `if payload.kind == "qr_label": … else: create_print_job` (rfid.py:477-480).
- **Rekomendasi:** `kind: Literal["rfid_tag","qr_label"]`. **Status:** **terverifikasi API** (§2 #25): `{"kind":"qr"}` → 200, dibuat job
  `PJ00015` ber-`kind:"rfid_tag"` dengan EPC baru untuk roll itu.

### INP-15 · Keluaran tanggal tanpa zona WIB
- **Area:** RFID (14 pemakaian `fmtTime`), opname, pendaftaran, transfer exception, eskalasi, retur, makloon · **Klasifikasi:** inkonsistensi · **Keparahan:** P3
- **Bukti:** `toLocaleString("id-ID", {…})` tanpa `timeZone` dan tanpa tahun (rfidShared.jsx:13) — dipakai juga di antrean periksa D2
  (GateReviewQueue.jsx:80; GateReviewDetail.jsx:51); `.slice()` atas ISO UTC (CycleCount.jsx:227,242; InitialRegistration.jsx:92;
  RegistrationDetail.jsx:90,92; ReceiptExceptions.jsx:166); LoadingCheckPanel.jsx:199; EscalationManagement.jsx:205,232,312;
  ReturnTimelinePanel.jsx:31; MakloonPartialReceipts.jsx:7; RollGradePanel.jsx:128,162; `localTs` zona perangkat (InspectionDetailParts.jsx:10-15);
  nama sesi opname bawaan `Count %Y%m%d-%H%M` UTC (cycle_count.py:69). Formatter baku `formatDateTime` (utils/formatters.js:17-30) tidak dipakai.
- **Rekomendasi:** semua waktu lewat `formatDateTime`/`shortWib`; penjaga statik G-OUT-01.
- **Status:** terverifikasi kode.

### INP-16 · Keluaran: id / kode mentah tampil di layar & CSV (guardrail INV-UI-02 MERAH di HEAD)
- **Area:** pendaftaran, lokasi, opname, RFID, logistik, retur · **Klasifikasi:** inkonsistensi · **Keparahan:** P2
- **Bukti:** `g.owner_entity_id` (RegistrationDetail.jsx:146) — `verify_entity_label.py` **merah**; fallback `e.short_name || e.name || e.id`
  (LocationPutawayView.jsx:39; RollCountPanel.jsx:42; useRuleRefs.js:17; WarehouseProfileDrawer.jsx:193) **tidak ditangkap** guardrail;
  `bin_id` mentah (OrphanPanel.jsx:141; CycleCount.jsx:313; OutboundScanInterface.jsx:462 — PickListPanel memakai `bin_code`);
  `{r.read_type}` "gate_in" & `[{lastResult.code}]` (RfidGateMonitorView.jsx:213,234); `device_name || device_id`
  (GatePassageHistory.jsx:36); `roll_no || roll_id` (U300DocSession.jsx:42); `d.direction` "n/a" (RfidDevicesView.jsx:232); hasil verifikasi
  cetak = EPC mentah tanpa no. roll (RfidPrintVerifyPanel.jsx:308-309); riwayat pengiriman memuat nama field
  "courier_name, shipping_cost" & `t.action` (logistics_service.py:453; DeliveryDetailModal.jsx:212); status roll mentah
  (ReturnDispositionPanel.jsx:30); "Gagal ship/goods_back" (PurchaseReturns.jsx:272,307); pesan server "(current: qc_pending)",
  "Product ID tidak sesuai…" (inbound_receiving_extra.py:146-148; inbound_receiving.py:72). Istilah campur (Override, Loading Check)
  **tidak** diusulkan diubah (K-13).
- **Rekomendasi:** perbaiki baris merah guardrail; perluas INV-UI-02 ke pola `|| x.id`/`|| x_id`; label status lewat kamus; pesan server tanpa kode mentah.
- **Status:** terverifikasi kode (guardrail dijalankan).

### INP-17 · Keluaran: satuan ditulis keras / dijumlah lintas satuan
- **Area:** karantina retur, opname, perbaikan, selisih supplier · **Klasifikasi:** inkonsistensi (INV-QTY-01) · **Keparahan:** P3
- **Bukti:** `{r.unit || "m"}` & "(… m) akan" (ReturnQuarantinePanel.jsx:266, ±446); "Selisih … unit", Expected/Actual tanpa satuan
  (CycleCount.jsx:317,333,348); panjang lintas satuan dijumlah tanpa satuan (RepairCreateModal.jsx:44,88); "total kurang" per
  mitra lintas produk/satuan tanpa satuan (goods_receipt_service.py:957-958; SupplierVariancePanel.jsx:47); angka tanpa `formatQty`
  (GrnReconPanel.jsx:81-84; GrnLineRow.jsx:159-162; POVarianceTasksPanel.jsx:35; InspectionDetailPanel.jsx:412,423).
- **Rekomendasi:** `QtyDual` / `formatQty(qty, unit)`; jumlah per satuan. **Status:** terverifikasi kode.

### INP-18 · Sopir pengiriman tidak divalidasi sebagai akun ber-peran sopir / satu PT
- **Area:** Pengiriman · **Klasifikasi:** kandidat bug · **Keparahan:** P3
- **Bukti:** hanya `_assert_driver_free` (logistics_service.py:196-197). **Rekomendasi:** cek peran `driver` & cakupan PT.
- **Status:** kandidat · uji API: create/patch dengan `driver_user_id` milik pengguna non-sopir.

---

## 5. Temuan — DAFTAR (LST)

### LST-01 · Mayoritas daftar WMS-RFID tanpa halaman server — batas keras memotong diam-diam
- **Area:** ±46 dari ±55 layar daftar · **Klasifikasi:** fitur belum ada / hambatan · **Keparahan:** P2
- **Bukti:** inventaris otomatis 197 GET daftar: **178 tanpa parameter halaman**; contoh batas: Kedatangan `limit=100` tanpa paging,
  angka chip = baris termuat (GoodsReceiptsView.jsx:40,96-97; goods_receipts.py:48-65); tugas barang keluar & cutting `to_list(200)`
  termasuk yang sudah terkirim (outbound_picking.py:40-46; CuttingOpsView.jsx:50-52); transfer `to_list(200)` (transfers.py:126);
  PA `limit=100` termasuk draf/selesai (putaway_order_service.py:336; PutawayOrdersPanel.jsx:67); antrean rak 500 tanpa penanda
  (location_service.py:227,241); tag RFID 1000 (label tab "(1000)", rfid_service.py:66); pengiriman 1000, riwayat 3000 dipotong di
  memori (logistics_service.py:297,384); HP tugas `to_list(2000)`+200 dokumen penuh termasuk `scan_log` (wms.py:38-41), dirender semua.
  Hanya 9 daftar memakai halaman server (`pagination.py` atau kursor).
- **Aturan dilanggar:** INV-UI-07 (daftar berhalaman + unduh); KN_08 data-dense tables.
- **Dampak:** dokumen aktif yang lebih tua tak terlihat tanpa tanda; HP lambat.
- **Rekomendasi:** semua daftar dokumen memakai `pagination.py` (`page/page_size/q/sort`) + `PaginationBar`; bawaan menyaring status terbuka; kursor untuk log RFID.
- **Status:** terverifikasi kode.

### LST-02 · Meja Cutting kehilangan tugas terbaru setelah 500 tugas sample
- **Area:** Cutting → Meja Cutting · `GET /api/cutting/desk` · **Klasifikasi:** bug · **Keparahan:** P1
- **Bukti:** `db.wms_tasks.find({**scope, "task_subtype": "sample_cut"}).sort("created_at", 1).to_list(500)` — tanpa filter status,
  urut **naik** (backend/services/cutting_service.py:76-77).
- **Dampak:** begitu total tugas sample (termasuk yang sudah selesai) > 500, tugas baru tidak pernah tampil di "menunggu diterima".
- **Rekomendasi:** saring status terbuka, urut turun, halaman. **Status:** terverifikasi kode. **Data:** 20 tugas `sample_cut` di snapshot
  (ambang 500 belum tercapai di data uji; di produksi akan tercapai seiring waktu karena tugas selesai tidak pernah disaring).

### LST-03 · Parameter `limit` tanpa batas atas (17 endpoint) / negatif
- **Klasifikasi:** bug kecil · **Keparahan:** P3
- **Bukti:** daftar di lampiran B.5 (mis. `/goods-receipts`, `/putaway-orders`, `/inventory/rolls` bawaan 5000, `/rfid/incidents`, `/lots`);
  `GET /goods-receipts?limit=-1` → `to_list(-1)` (goods_receipts.py:65).
- **Rekomendasi:** `Query(…, ge=1, le=500)` baku. **Status:** **terverifikasi API**: `GET /goods-receipts?limit=-1` → **500**
  (`ValueError: length must be non-negative`); `limit=100000` → 200 (tanpa batas atas).

### LST-04 · Saringan tidak lengkap / hilang
- **Klasifikasi:** hambatan UX · **Keparahan:** P3
- **Bukti:** transfer tanpa status "Diterima Sebagian"/"Dibatalkan" (transferConstants.jsx:19-21); saringan gudang print job hilang
  setelah membuka job (`params: {}`, RfidPrintVerifyPanel.jsx:69) dan API `status` tidak dipakai; HP tugas tanpa saring gudang/status;
  daftar sesi pendaftaran tanpa saring padahal API mendukung status/gudang; shrinkage mengabaikan gudang (RfidSecurityPanel.jsx:118-160);
  roll siap cetak tanpa cari; antrean periksa D2 tanpa cari roll/no. dokumen; urut yang bisa dipilih hanya di 1 daftar (DeliveryTable).
- **Rekomendasi:** pola baku `ListToolbar` = `SearchBox` (server) + `OptionTabs` status lengkap + `KNSelect` gudang/PT + urut kolom. **Status:** terverifikasi kode.

### LST-05 · Tab Mutasi memotong 60 baris walau pager menawarkan 100
- **Area:** Stok → Mutasi · **Klasifikasi:** bug · **Keparahan:** P2
- **Bukti:** `movements.slice(0, 60)` (LedgerTable.jsx:28) vs `PaginationBar` 20/50/100.
- **Dampak:** pada 100/halaman, baris 61–100 tidak terlihat sementara pager menyebut "1–100". **Status:** terverifikasi kode.

### LST-06 · Keadaan kosong palsu saat memuat / galat senyap
- **Klasifikasi:** inkonsistensi (INV-UI-03) · **Keparahan:** P3
- **Bukti:** state awal `[]` → "Belum ada…" saat memuat (SupplierVariancePanel.jsx:13; GrnOcrSamplesPanel; GatePassageHistory);
  `.catch(() => {})` (rfidShared.jsx:22; CycleCountPanel.jsx:23); "Belum ada reader gate" tampil saat galat (WarehouseProfileDrawer.jsx:48);
  `String(err)` → "[object Object]" (PrinterStatusWidget); polling aktivitas gate menelan galat.
- **Rekomendasi:** hook daftar baku `{rows, loading, error}` + `EmptyState`/`ErrorNotice` (KN_08). **Status:** terverifikasi kode (→ B1 visual).

### LST-07 · Daftar tanpa proyeksi / kueri N+1
- **Klasifikasi:** kinerja · **Keparahan:** P3
- **Bukti:** sesi opname `to_list(100)` tanpa proyeksi (items + scans penuh); master gudang memanggil occupancy N kali
  (WarehouseMasterView.jsx:102-105); antrean QC 2 kueri per tugas (inbound_receiving_extra.py:93-131); selisih supplier `to_list(5000)`
  tanpa proyeksi; master grade mengagregasi seluruh `inventory_rolls` tiap muat; tag RFID tanpa proyeksi. **Status:** terverifikasi kode.

### LST-08 · Cari klien-saja dan tanpa debounce; urutan tetap
- **Klasifikasi:** hambatan UX · **Keparahan:** P3
- **Bukti:** cari klien atas 200–1000 baris yang sudah terpotong (Transfer, Master gudang, QC, Tag RFID, Lokasi tag, Order makloon,
  Armada) — hasil "tidak ditemukan" padahal datanya di luar batas; Kedatangan memanggil API tiap ketukan (ListControls.jsx:18-30 tanpa debounce);
  SPK memakai input mentah, bukan `SearchBox`.
- **Rekomendasi:** cari server + debounce 300 ms di `SearchBox`. **Status:** terverifikasi kode.

### LST-09 · Antrean periksa gate (D2): kursor dari server tidak dipakai — baris ke-101 tak terjangkau
- **Area:** RFID › Monitor Gerbang › Antrean periksa · `GET /api/rfid/v2/ops/reviews` · **Klasifikasi:** fitur belum ada · **Keparahan:** P2
- **Bukti:** layar meminta `{ status, limit: 100 }` (GateReviewQueue.jsx:33) dan tidak membaca `next_before` yang dikembalikan
  server (rfid_v2_review.py:70-71) → tanpa "muat lagi"/halaman dan tanpa penanda terpotong; tanpa cari; tanpa ekspor
  (dataset `rfid_v2_reviews` tidak ada di Pusat Export). Positif: server berbatas `le=100` + kursor + proyeksi `actions:0`.
- **Dampak:** pada lonjakan kuning (mis. reader bermasalah sehari, volume 6.000 roll/hari menurut KEPUTUSAN_GATE_RFID §10),
  kasus lama tidak bisa ditindak dari layar.
- **Rekomendasi:** "Muat lagi" dengan `before=next_before` atau `PaginationBar` kursor; cari no. roll/dokumen; ekspor XLSX (EXP-01).
- **Status:** terverifikasi kode.

---

## 6. Temuan — EKSPOR (EXP)

### EXP-01 · Tidak ada ekspor XLSX di satu pun daftar WMS-RFID — padahal mesin XLSX & dataset gudang sudah ada di Pusat Export
- **Area:** semua daftar cakupan · **Klasifikasi:** fitur belum ada · **Keparahan:** P2
- **Bukti:** `PaginationBar` hanya membangun CSV (`buildCsv`, PaginationBar.jsx:47); 6 daftar ber-CSV standar, 0 XLSX.
  Pusat Export (`features/export/ExportCenterView.jsx`, "Unduh XLSX" :200-201; backend `export_center.py` `format: xlsx|csv`,
  openpyxl) sudah punya dataset `goods_receipts`, `wms_tasks`, `inventory_rolls`, `inventory_movements`, `inventory_balances`,
  `inventory_lots`, `warehouse_transfers`, `warehouses`, `warehouse_sites`, `cycle_count_sessions`, `inspections`, `rfid_tags`,
  `rfid_reads`, `shipments`, `logistics_deliveries`, `makloon_orders`, `purchase_returns`, `sales_returns`, `mdq_cuts`
  (services/export_registry.py:93-232; export_registry_more.py) — tetapi tidak satu daftar pun menautkannya dengan saringan aktif,
  dan menu Pusat Export **tidak diberikan ke peran `warehouse`** (navStructure.js:376-381).
- **Aturan dilanggar:** permintaan pemilik "harus ada ekspor Excel"; INV-UI-07.
- **Rekomendasi (tanpa skema baru):** tombol baku "Unduh Excel" di `ListToolbar`/`PaginationBar` yang memanggil
  `/api/export-center/…` dengan `dataset` + saringan/cakupan pengguna aktif (format xlsx, kolom berformat & berlabel); CSV tetap sebagai pilihan.
  Izin isi tetap dari modul sumber (sudah dijaga mesin export). **Butuh keputusan:** apakah peran `warehouse` boleh mengunduh.
- **Status:** terverifikasi kode.

### EXP-02 · ±45 daftar tanpa ekspor sama sekali; penjaga INV-UI-07 hanya melihat `<PaginationBar>`
- **Klasifikasi:** fitur belum ada / celah guardrail · **Keparahan:** P2
- **Bukti:** lampiran B (penerimaan 8/9, putaway-lokasi 9/13, keluar-kirim 11/17, RFID 15/16 daftar tanpa ekspor); daftar yang memakai
  `useListSearch → usePagedRows → KNPager` (hooks/usePagedRows.js:11), `PagedRows`, atau tanpa pager lolos dari
  `verify_list_export.py` aturan A.
- **Rekomendasi:** perluas aturan A ke semua komponen/hook halaman (`KNPager`, `PagedRows`, `usePagedRows`) dan ke tabel dokumen ≥ 20 baris (G-LIST-01).
- **Status:** terverifikasi kode.

### EXP-03 · CSV Logistik tidak standar (pemisah koma, tanpa BOM, hanya baris tampil)
- **Area:** Pengiriman (daftar & riwayat) · **Klasifikasi:** inkonsistensi (INV-UI-07 B) · **Keparahan:** P2
- **Bukti:** LogisticsView.jsx:34-41 dan HistoryPanel.jsx:43-46 membangun CSV sendiri (`,`, tanpa BOM, tanpa `utils/csvExport.js`); riwayat hanya halaman berjalan.
- **Dampak:** di Excel ID semua kolom menumpuk di kolom A; data tak lengkap. **Rekomendasi:** `csvExport.js` + `fetchAll` (atau EXP-01). **Status:** terverifikasi kode.

### EXP-04 · Isi CSV memuat id/kode mentah
- **Klasifikasi:** inkonsistensi · **Keparahan:** P3
- **Bukti:** CSV Mutasi: SKU/Gudang jatuh ke id (InventoryStockView.jsx:144-148); CSV Roll: status kode mentah (:57); tabel Roll tanpa kolom bin/lokasi (RollsTable.jsx:19-30).
- **Rekomendasi:** kolom ekspor memakai label yang sama dengan layar. **Status:** terverifikasi kode.

### EXP-05 · Dataset ekspor belum mencakup dokumen WMS-RFID baru; endpoint ekspor ganda
- **Klasifikasi:** fitur belum ada / duplikasi · **Keparahan:** P3
- **Bukti:** tidak ada dataset `putaway_orders`, `repair_orders`, `rfid_devices`, `rfid_print_jobs`, `rfid_incidents`, `rfid_v2_reviews`,
  `rfid_v2_passages`, sesi pendaftaran (cycle_count_sessions `mode=registration` ikut dataset opname tanpa pembeda); `/api/inspections/export`
  (CSV backend) tidak dipakai FE, sementara layar SPK membangun CSV sendiri.
- **Rekomendasi:** tambah dataset ke `export_registry_more.py` (bukan koleksi baru); pensiunkan endpoint ekspor ganda. **Status:** terverifikasi kode.

---

## 7. Pola kesalahan (dengan jumlah)

| # | Pola | Jumlah | Contoh |
|---|---|---|---|
| 1 | Alasan K-14 hanya di layar / tidak sama sekali (server menerima kosong/1 huruf/spasi/teks tetap) | **25 jalur** | FRM-09 |
| 2 | Daftar tanpa halaman server (batas keras diam) | **±46 layar · 178 GET** | LST-01, LST-02 |
| 3 | Daftar tanpa ekspor / tanpa XLSX | **±45 / 55 (XLSX 0)** | EXP-01/02 |
| 4 | Teks bebas mengisi field rujukan master/dokumen | **±24 isian** (bin ×4, roll/lot ×3, satuan ×3, grade ×2, kurir/sopir/kendaraan/carrier ×8, lokasi perangkat, kategori, warna, kode cacat, bagian) | INP-01..08 |
| 5 | Angka tanpa batas / NaN / ≤0 lolos; `type=number` tanpa `min` | **±20 field server · 50/87 isian FE** | INP-09 |
| 6 | Form HP kurang isian/tindakan dibanding desktop | **4 aksi kurang + ≥12 tindakan tak ada** | FRM-02/03/04 |
| 7 | Tanggal tanpa WIB | **≥30 titik** di ≥14 berkas | INP-15 |
| 8 | Id/kode mentah di layar & CSV (1 guardrail merah) | **±20 titik** | INP-16, EXP-04 |
| 9 | Body tanpa skema / kunci asing dibuang / data tulis di query | **11 dict + 13 manual + ±9 query; 0 model `forbid`** | INP-13, FRM-05 |
| 10 | Elemen form buatan sendiri (tombol hex, isian Tailwind mentah, tanpa label, tanpa `required`) | **162 tombol · 55 isian · ±35 tanpa label · 1 `required` · 3 `maxLength`** | FRM-17 |
| 11 | Aksi destruktif/posting tanpa konfirmasi | **±14** | FRM-14 |
| 12 | Galat 422 tertelan / detail mentah dirender | **±11 tempat** | FRM-16 |
| 13 | Desimal koma hilang (`parseFloat`/`Number` atas isian) | **≥4 isian** | INP-10 |
| 14 | Pelaku/sumber bukti dari klien (`requested_by`, `source:"device"`, heartbeat) | **6** | FRM-08, FRM-11, FRM-12 |
| 15 | Koleksi tidak terdaftar di ENTITY_REGISTRY | **29 (+4 D2)** | FRM-24 |

## 8. Usulan aturan baku form & daftar (bisa dijadikan guardrail otomatis)

| Kode | Aturan | Cara cek otomatis (statik kecuali disebut) |
|---|---|---|
| **G-FORM-01** | Isian yang mengisi field `*_id`, `bin*`, `unit/uom`, `grade`, `warehouse*`, `supplier*`, `partner*`, `driver*`, `vehicle*`, `courier*`, `color*`, `category*` **wajib** pemilih terikat id (`KNSelect`/`ProductSelect`/`LocationFields`/pemilih bin/…), bukan `<input>`/`<textarea>` | Babel: `value={x.<field>}` pada `input/textarea` dengan nama field cocok pola → merah, kecuali `DIBOLEHKAN` beralasan (mis. plat kendaraan luar) |
| **G-FORM-02** | Setiap field model body (tulis) ada isiannya, atau diturunkan server (daftar diturunkan) | silang `b3b_crossref.py`: field skema ∉ kunci payload FE ∧ ∉ daftar `SERVER_DERIVED` |
| **G-FORM-03** | Kunci payload FE ⊆ field model | `b3b_crossref.py` → DROP = merah (sekarang 1 nyata: random-check) |
| **G-FORM-04** | Alasan: satu validator server `ReasonStr` (strip, ≥5 **huruf**) di semua model berfield `reason/notes/note` keputusan; tanpa alasan bawaan teks tetap | AST `schemas*.py` + model router: field bernama alasan tanpa `ReasonStr` → merah; uji runtime `"....."` & `"a"` → 400 |
| **G-FORM-05** | Panggilan FE ke endpoint ber-efek stok/GL/hapus wajib lewat `askConfirm`/`askReason` | daftar endpoint berefek (anotasi di router) × sensus FE |
| **G-FORM-06** | Galat API selalu lewat `apiErrorText`; `setError(e.response?.data?.detail)` mentah dilarang | grep/AST |
| **G-FORM-07** | Tombol hanya kelas baku (`primary/secondary/danger-button`, `<Button size>`); `bg-[#…]` pada `<button>` dilarang di form | sensus `b3b_form_census.py` (sekarang 162) — mulai sebagai *ratchet* (tidak boleh bertambah) |
| **G-FORM-08** | Isian wajib berlabel (`<label>`/`aria-label`); wajib = `required` + `*` dari satu komponen `Field`; `maxLength` sesuai skema | sensus: kontrol tanpa label, `*` di placeholder → merah |
| **G-FORM-09** | Paritas HP: setiap aksi tulis di `features/mobile/*` mengirim kunci payload ⊇ padanan desktop untuk endpoint yang sama | `b3b_crossref.py`: kelompokkan per endpoint, bandingkan himpunan kunci HP vs desktop |
| **G-NUM-02** | INV-NUM-01 diperluas ke model di router & `Query()` tulis; qty/panjang `gt=0, allow_inf_nan=False` | AST semua `routers/*.py` |
| **G-NUM-03** | Isian qty/panjang memakai `DecimalInput`; `parseFloat(`/`Number(` atas state form dilarang | grep/AST |
| **G-API-01** | Semua body tulis turunan `KNIn(extra="forbid")`; `dict`/`_payload` hanya di daftar pengecualian beralasan | AST |
| **G-API-02** | Endpoint tulis tidak menerima data bisnis/alasan via query string | OpenAPI: POST/PUT/PATCH dengan parameter `in: query` selain penanda teknis → merah |
| **G-SCOPE-01** | Endpoint `/{id}/…` di router cakupan memanggil `assert_entity_access` (langsung atau lewat helper) | AST + uji runtime id PT lain → 403/404 |
| **G-LIST-01** | Setiap daftar dokumen: halaman server (`pagination.py`) + `PaginationBar` + ekspor **XLSX** (Pusat Export, ikut saringan) + CSV; berlaku juga untuk `KNPager/PagedRows/usePagedRows` | perluas `verify_list_export.py` aturan A |
| **G-LIST-02** | GET daftar: `limit` ber-`le`, tanpa `to_list(n)` keras di service daftar | OpenAPI (`maximum`) + AST service |
| **G-OUT-01** | Waktu tampil lewat `formatDateTime`/`shortWib` (WIB); `toLocaleString` tanpa `timeZone` & `.slice(0,10)` atas ISO dilarang | grep/AST |
| **G-OUT-02** | INV-UI-02 diperluas: fallback `|| x.id` / `|| x_id` pada label dilarang | perluas `verify_entity_label.py` |
| **G-CFG-01** | Setiap setelan `int/decimal` punya `min/max`; `list` berpola regex divalidasi `re.compile`; JSON bertipe `json_map` | uji registri `config_catalog_*.py` |

## 9. Butir keputusan pemilik + rekomendasi

| # | Butir | Rekomendasi |
|---|---|---|
| K-B3b-01 | **Pick tanpa pindai roll** (alur cepat HP) — tetap boleh? (FRM-03) | **Wajib pindai roll** di HP dan desktop; pengecualian hanya produk non-roll |
| K-B3b-02 | **Bukti cek muat manual** (tempel EPC) sah? (FRM-11) | `manual` bukan bukti; sah hanya `device` dari kanal perangkat; manual = override berizin + alasan |
| K-B3b-03 | K-14 dihitung **huruf** atau karakter non-spasi? (FRM-09, FRM-21) | Huruf (`[A-Za-z]` ≥ 5) — sesuai teks keputusan, menolak "....." |
| K-B3b-04 | **Ekspor Excel** — lewat Pusat Export (dataset yang ada) dari tombol tiap daftar? Peran `warehouse` boleh mengunduh? (EXP-01) | Ya, satu tombol "Unduh Excel" baku → Pusat Export dengan saringan aktif; `warehouse` boleh untuk dataset gudang yang izin lihatnya ia punya |
| K-B3b-05 | **Master ekspedisi** & **satu master kendaraan** (`vehicles` vs `fleet_vehicles`) (INP-06) | Satukan ke satu master kendaraan; ekspedisi sebagai jenis mitra di master yang ada (bukan koleksi baru) → B3a |
| K-B3b-06 | Daftar awal HP di gedung bersama: PT pemilik roll dipilih per baris atau ikut PT sesi? (FRM-06/MobileRegistration) | Pilih per baris (bawaan PT sesi) agar roll PT lain tidak terdaftar atas nama PT sesi |
| K-B3b-07 | Batas **susut saat potong** & selisih panjang potong sample (INP-09) | Batas % (setelan, mis. 3%) + alasan ≥5 di atas batas; selisih sample > toleransi butuh konfirmasi |
| K-B3b-08 | Fitur **ambil alih tugas** dipasang di Barang Masuk/Keluar atau dihapus? (FRM-22) | Pasang di daftar tugas (izin approve) — atau hapus berkas mati `ScannerTaskPanel` |
| K-B3b-09 | Tombol **simulasi** (PA "Simulasi Scan Semua", pindai area) di produksi? (FRM-10, FRM-13) | Hanya saat `wms.rfid_simulation` aktif, data bertanda `simulated` |
| K-B3b-10 | Koreksi klaim crossing gate (D2) perlu layar? (FRM-21) | Ya, di rincian antrean periksa (admin gudang), alasan ≥10 |

## 10. Bukti data (`kn_test_trial`, baca-saja: find/distinct/aggregate/count)

Dijalankan ke salinan snapshot `kn_test_trial_2026-11-08` di kontainer sementara (identik dengan data acuan; tidak disentuh uji).

| Kueri | Hasil | Temuan |
|---|---|---|
| `inventory_rolls.bin_id` yang tidak cocok id bin struktur `warehouses.zones` | 2 dari 607 nilai (`bin_sim_hilang_01/02`, simulasi); 0 yang berupa **kode** bin | INP-01/02 — risiko belum terwujud di data uji |
| bin yang hanya punya `capacity` vs `capacity_rolls` | **914 vs 10** | FRM-07 |
| `warehouse_transfers.requested_by` / `approved_by` | {"Budi Santoso", **"Warehouse User"**} / {null, **"Manager"**} | FRM-08 |
| `rfid_devices` | 1: `DEV-84134` gate `out`, `location: ""`, `status: "online"` | FRM-12, INP-07 |
| `inventory_rolls.unit` / `grade` | {kg, meter, yard} / {A, A1, B, B1, BS, C} — **"Reject" (opsi layar stok awal) tidak ada di master** | INP-05 |
| `goods_receipts.lines.declared.unit` | {meter} (semua cocok master) | INP-04 — belum terwujud |
| `logistics_deliveries.courier_name` / `vehicle_plate` / `driver_name`; retur `courier` | {JNE, LALAMOVE} / {""} / {""}; {"J&T Express"} | INP-06 — data uji tipis |
| `fleet_vehicles.plate` / `vehicles.no_polisi` | [] / [] (dua master, keduanya kosong) | INP-06, FRM-24 |
| `wms_tasks` sample_cut / outbound / inbound | 20 / 123 / 129 | LST-01/02 |
| `cycle_count_sessions.items.bin_id`, `roll_scans.bin_id` | [] / [] | INP-02/03 — belum ada data |
| `warehouse_sites.country_code` | {ID} | FRM-06 |
| `config_values` `receiving.mode` | riwayat berganti `grn` ↔ `legacy` (global & `ent_ksc`) | FRM-02 — jalur lama masih hidup |

## 11. Koordinasi

- **→ B1 (peramban):** FRM-04 (paritas tampilan HP), FRM-14 (konfirmasi), FRM-15/16 (crash/duplikasi), FRM-17 (ukuran piksel tombol &
  isian, target sentuh HP), FRM-18 (pemilih grade kosong akun gudang), LST-06 (keadaan kosong/memuat).
- **→ B3a (SSOT & skema penuh):** FRM-07 (`capacity` vs `capacity_rolls`), FRM-24 (koleksi tak terdaftar, v1↔v2, `putaway_orders` vs
  `warehouse_transfers`, `warehouse_sites` vs alamat gudang), INP-06 (master kendaraan ganda).
- **→ audit middleware RFID:** FRM-11 dan antrean periksa D2 hanya dinilai dari sisi form/daftar; logika gate tidak diulang (AUD-MW-10/15/16/17).
- Tracker review (`docs/reviews/TRACKER.md`) **tidak diubah** (sesuai instruksi).

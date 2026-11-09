# B2b · Analisis statik A — Alur BARANG KELUAR penjualan (SO → alokasi → ambil → cek muat → kirim → logistik → POD)

> **Lampiran paket audit B2b** (SO → alokasi → ambil → cek muat → SJ → logistik → POD) — tabel transisi status dari KODE (`berkas:baris`, CAS, efek, pembalikan,
> idempotensi, pagar) + kandidat anomali statik + resep uji. Disusun dengan pembacaan kode di HEAD `35506d7`
> (`integrasi-prep3`). **Hasil uji runtime** (yang terbukti / dibantah / belum dijalankan) ada di laporan utama
> [`B2b-ALUR-KELUAR-POTONG-RFID.md`](B2b-ALUR-KELUAR-POTONG-RFID.md) §3 & §8 — ID kandidat di sini (ANOM-, POT-, SMP-, TRF-,
> MKO-, REP-, PRT-, T-, G-, L-, P-, H-) dipetakan ke ID temuan resmi (FLW-OUT-, STM-OUT-, CUT-, RFID-) di sana.
> Sandi akun demo sengaja tidak ditulis (lihat `AGENTS.md`). Catatan "belum dijalankan" di bagian resep = status saat
> lampiran disusun, sebelum uji runtime B2b.

* **Jenis:** audit BACA-SAJA dari kode (tanpa menjalankan aplikasi / DB). Worktree HEAD `35506d7`.
* **Akar:** `backend/` (semua `berkas:baris` relatif ke `backend/` kecuali disebut lain).
* **Alat bantu:** `scripts/audit/b3a_db_writers.py --json` (14.767 panggilan Mongo; disaring per koleksi) + grep + baca kode.
* **Acuan maksud:** `docs/KN_16_END_TO_END_PROCESS_FLOWS.md` §2/§4/§7/§8B.7, `docs/KN_15_INVENTORY_OWNERSHIP_LOT.md` §3.4.1/§6,
  `docs/rfid/KEPUTUSAN_GATE_RFID.md` §7 (K-GDG-02/09) & §9.
* **Tidak diulang (rujuk saja):** B3a SSOT-1 (63 penulis status roll, `allocated` bocor ke status roll), SSOT-3, SSOT-8
  (reservasi tertinggal / SO hantu), SCH-6 (mutasi bukan buku besar), STK-11 (GET menulis — `expire_old_reservations`),
  STK-13, SCP-2/SCP-3 (cakupan lokasi WMS); B3b FRM-03 (scan-pick tanpa roll), FRM-11 (EPC cek muat ditempel manual);
  B1 UI-08/09/11/41.
* **Legenda kolom:** CAS = filter `update` memuat status asal (atau klaim saga berprasyarat). "Klaim" = `atomic_claim.claim()`
  (`services/atomic_claim.py:24-45`) — hanya menolak pemanggil lain yang JUGA mengklaim; penulis tanpa klaim tidak terhalang.

Ringkasan angka: **71 baris transisi** (SO header 15 · sub-dokumen SO 8 · roll 12 · tugas WMS 12 · cek muat 7 · SJ 3 ·
logistik 9 · finansial 5) dan **30 kandidat anomali**: 27 **[K]** pasti dari kode (12 di antaranya punya probe runtime
deterministik di §c-3 untuk bukti/keparahan: ANOM-01..06, 08, 10..12, 15, 16) dan 3 **[R]** yang hanya bisa dipastikan
lewat runtime (ANOM-07, 13, 17); balapan tanpa CAS (ANOM-14, 18, 19, 25, 26) pasti dari kode tetapi dampaknya butuh uji
bersamaan (C-P11).

---

## (a) Tabel transisi per dokumen

### A1. `sales_orders.status` (header)

Penulis `status` (scan `--coll sales_orders`): `routers/sales_orders.py:682` (insert), `services/sales_order_helpers.py:243`
(`so_transition`, CAS), `services/fulfillment_status.py:73` (`recompute_so_status`, **tanpa CAS**),
`services/inventory_service.py:49` (kedaluwarsa, **tanpa CAS/klaim**), `services/backorder_service.py:106`,
`routers/sales_orders_extra.py:695` & `:835`, `services/so_override_service.py:317`, `services/special_order_phase2.py:779`
(**tanpa CAS**), `routers/sample_orders.py:216/232/251` (via `so_transition`).
`so_transition` (`sales_order_helpers.py:199-256`): baca → 409 pemandu bila status ∉ asal → `find_one_and_update`
`{id, status ∈ expected_from}` + `$unset saga_lock` + stempel `approved_*/confirmed_*/delivered_*` (`:194-196`) + `stage_fields`
+ `dead_order_patch` (tutup approval menunggu, `has_backorder=False`) + `audit()`.

| # | dari → ke | pemicu (endpoint → fungsi, berkas:baris) | penjaga / CAS | efek | dibalik saat batal? | idempoten bila diulang? | pagar PT / lokasi / lini |
|---|---|---|---|---|---|---|---|
| SO-01 | ∅ → `reserved` \| `waiting_stock` \| `draft` (regular); `approved` \| `waiting_approval` (sample) | `POST /api/sales-orders` → `create_order` `routers/sales_orders.py:96-722`; status awal `:549-561`; insert `:682` | insert (tanpa CAS perlu). **Reservasi roll terjadi SEBELUM SO ada** (`:440-543`); rollback hanya bila error di loop (`:532-543`) — `insert_one` `:682` di luar `try` | roll `reserved`/`length_reservations` (A2 R-01/R-02), mutasi `reservation`, `rebuild_balance`; `items[].reserved_qty/backorder_qty`; `backorders[]`=`waiting_stock`; `pending_approvals` (nilai/makloon/bayar sampel); notifikasi QC `:690-695`; `doc_refs` SO↔OD `:697-701`; `audit order_created` `:713` | ya: batal/kedaluwarsa/lepas reservasi melepas roll (A2 R-07) | **tidak** — tanpa kunci idempoten; klik ganda = 2 SO | izin `order.create`/`sample_order.create`; `pexcl.assert_can_order`, `line_scope.assert_can_order` `:213,220`; **PT dari `payload.entity_id` → `customer.entity_id` → PT aktif tanpa `resolve_requested_entity`** `:197-198` (lih. ANOM-17); tanpa pagar lokasi |
| SO-02 | `reserved` \| `waiting_stock` → `waiting_approval` | `POST /sales-orders/{id}/submit-for-approval` `sales_orders_extra.py:401-430` → `submit_core` `so_lifecycle_service.py:21-53` | CAS `so_transition`; `pending_approvals` ditulis dulu **tanpa CAS** `:43-48` | entri `nilai` (validasi admin) ditambah; `audit order_submitted` | — | 2× → 409 `ALREADY_WAITING_APPROVAL` `:407-430` | `order.update` + `assert_entity_access` `:406` |
| SO-03 | `reserved` → `approved` (auto) | `submit_core` bila tak perlu ACC `so_lifecycle_service.py:55-58` | CAS | roll → `committed` (`set_order_rolls_status`, tanpa CAS) | — | 409 | idem SO-02 |
| SO-04 | `reserved` \| `waiting_approval` \| `waiting_stock` → `approved` | `POST /sales-orders/{id}/approve` `sales_orders_extra.py:446-512` (`advance_so_if_all_approved` `:433-443`, cadangan `:498-500`); `POST /sales-orders/{id}/approvals/{aid}/decide` `routers/so_approvals.py:270-373` (`:357-361`); `POST .../continue-normal-price` `so_release_service.py:122-145` | CAS; pra-cek SO mati `:458-462`, `role_satisfies` `:463-466`, blokir pending kredit/harga/makloon `:468-476`, `has_rejected` `:480-485`; `decide` klaim saga per entri `so_approvals.py:308-316` | roll → `committed` (+`length_reservations.status`), stempel `approved_at/by`; WA `dispatch_event`; `auto_release` → SO-05 bila `release.requested` | — | `approve` ulang → 200 bila sudah `approved` (T-11) `:494-497` | `order.approve` + entitas |
| SO-05 | `approved` \| `waiting_approval` \| `reserved` → `confirmed` | `POST /sales-orders/{id}/confirm` `:515-524` → `confirm_core` `so_lifecycle_service.py:62-100`; `POST /sales-orders/{id}/review-release` & `/release` `routers/so_release.py:29-49` → `try_release` `so_release_service.py:57-75`; `auto_release` sesudah ACC/stok | verifikasi admin `:71-72`, gerbang ACC `:76-83`, CAS `:84`. **Tidak memeriksa stok/backorder** (lih. ANOM-10) | `create_outbound_tasks_for_order` `:87` (A3 T-01); `recompute_so_status` `:91`; WA. Roll **tidak** di-commit bila dari `reserved` (lih. ANOM-21) | — | 2× → 409 (CAS) | `order.confirm` + entitas (hanya bila SO ditemukan `:519-520`) |
| SO-06 | `confirmed` ⇄ `partially_picked` ⇄ `picked` | `recompute_so_status` `fulfillment_status.py:30-74` dipanggil scan-pick `outbound_picking.py:253`, confirm, potong sampel, backorder, OD, `wms outbound-from-order` | **TANPA CAS** — baca status lalu `update_one({id})` `:73`; bisa mundur (backorder bertambah) | `fulfillment{}` (total/picked/shipped/backorder), `stage/sub_status` | n/a | ya (turunan) | internal |
| SO-07 | `confirmed`/`*picked` → `partially_shipped` → `shipped` | `recompute_so_status` sesudah `dispatch_task` `shipment_service.py:137` | idem — tanpa CAS | idem; `shipped` hanya bila `shipped ≥ Σtask + backorder terbuka` `:47-57` | n/a | ya | internal |
| SO-08 | `shipped` → `done` | manual `POST /sales-orders/{id}/mark-delivered` `sales_orders_extra.py:527-555`; otomatis POD `so_delivery_service.complete_if_all_pod` `:31-56` (dari logistik `delivered/completed` & serah-terima ambil) | CAS `["shipped"]`; **`deliver_order_rolls` dijalankan SEBELUM CAS** (`:546-548`; `so_delivery_service.py:42-46`) | semua roll `in_transit_sales` SO → `delivered` (A2 R-06), stempel `delivered_*`, `audit order_delivered`, hook OD | — | manual 2× → 409; otomatis → `None` | manual `order.deliver` + entitas; otomatis: aktor logistik |
| SO-09 | non-terminal kecuali `partially_shipped/shipped` → `cancelled` | `POST /sales-orders/{id}/cancel` (body `SoCancelIn.reason` ≥5) `sales_orders_extra.py:844-909` | tolak `done/cancelled/expired/partially_shipped/shipped` `:855-856`; tolak Faktur aktif (`status≠batal`) `:859-867`; klaim saga prasyarat status `:869-870`; CAS `:874` | `release_order_rolls` **hanya bila status ∈ {reserved, waiting_approval, approved, confirmed, waiting_stock, partially_picked, picked}** `:871-873` (`draft` tidak!); tugas outbound non-dispatched → `cancelled` `:885-888` (sub-dok `escalation` dibiarkan); jurnal balik best-effort `:894-903`; notifikasi sales `:881-883`; approval menunggu ditutup | — (terminal) | 2× → 409 | `order.cancel` + entitas + `sales_ownership.assert_may_open` `:851` |
| SO-10 | `reserved`/`waiting_approval`/`approved`/`waiting_stock` → `draft` | `POST /sales-orders/{id}/release-reservation` `:809-841` | klaim saga prasyarat status `:821-822`; tulisan akhir `finish_set` | `release_order_rolls`; `allocations=[]`, `backorders=[]`, `has_backorder=False` (`items[].reserved_qty` **tidak** di-nolkan) | — | 2× → 409 | `order.update` + entitas |
| SO-11 | `reserved`/`waiting_approval`/`approved`/`waiting_stock` → `expired` | `expire_old_reservations` `inventory_service.py:26-68`, dipicu **GET** `/sales-orders`, `/sales-orders/stats/summary`, `/dashboard`, `/products` (STK-11) | **tanpa CAS & tanpa klaim** (`update_one({id})` `:49-52`) | `release_order_rolls`; alokasi/backorder dikosongkan; approval ditutup; jurnal balik; `audit reservation_expired` | — | ya | sistem |
| SO-12 | `waiting_stock` → `reserved` (backorder terisi) | `backorder_service._fill_order_locked` `:48-137` via `auto_fulfill_backorders` (GRN/QC/interco/makloon/OD) & `fulfill_from_stock` (`POST /sales-admin/orders/{id}/fulfillment-plan` `routers/work_desks.py:179-193`) | klaim saga prasyarat `status ∈ ACTIVE` `:38-39` (**ACTIVE tanpa `partially_picked/picked/partially_shipped`** `:26`); tulisan akhir `update_one({id})` `:106-108` | alokasi baru di-`$push`; roll `reserved` atau langsung `committed` bila SO `approved/confirmed` `:114-116`; tugas ambil **hanya bila SO sudah punya tugas** `:119-123`; `auto_release`; notifikasi backorder `:130-135` | n/a | ya (sisa nol → no-op) | route `order.confirm`; otomatis tanpa aktor |
| SO-13 | `reserved` ⇄ `waiting_stock` | Ganti Roll `sales_orders_extra.py:692-693`; override baris `so_override_service.py:259-261` | klaim saga prasyarat status; final `finish_set` | lih. A2 R-09, ANOM-03 | — | — | `inventory.pegging` / `order.override` + entitas |
| SO-14 | sampel: `waiting_approval` → `approved` → `confirmed`; → `cancelled` | `routers/sample_orders.py:216,232,251` | CAS `so_transition` | tugas `sample_cut` (A3) | — | 409 | `sample_order.*` |
| SO-15 | OD: `*` → `confirmed` | `special_order_phase2.py:779` | **tanpa CAS**, tanpa gerbang verifikasi/ACC | stempel `confirmed_by: Sistem (OD)`, timeline | — | ya | sistem (catat; alur OD agen lain) |

Status SO **dibaca tetapi tidak pernah ditulis**: `delivered` (`so_status.py:79`, `amendment_service.py:283`,
`config_impact_service.py:27`), `dispatched` (`so_status.py:81-84`, warisan), `packed/packing/ready`
(`so_tracker_service.py:12-25`, `sales_order_dashboard.py:13`), `completed/closed` (`amendment_service.py:283`),
`rejected/void` (`dispatch_payment_gate.py:23`). Status usulan KN_16 §2 yang tidak ada: `quotation`, `waiting_procurement`,
`waiting_intercompany`, `waiting_allocation_approval` (§8B.1), `invoiced/paid/returned`.

### A1b. Sub-dokumen SO

| # | field | transisi | pemicu (berkas:baris) | catatan |
|---|---|---|---|---|
| SUB-1 | `items[].reserved_qty/backorder_qty` | dihitung ulang | create `sales_orders.py:463-475,509-510`; Ganti Roll `sales_orders_extra.py:652-657`; lepas sebagian `:756-760`; override `so_override_service.py:157-167`; backorder `backorder_service.py:86-89`; eskalasi `outbound_picking.py:414-416` | `release-reservation` tidak menolkan (basi) |
| SUB-2 | `backorders[].status` | `waiting_stock` → `fulfilled` | `backorder_service.py:80-82` | diganti utuh oleh Ganti Roll/lepas sebagian/override; dikosongkan oleh lepas reservasi/kedaluwarsa; batal: `has_backorder=False`, daftar tetap |
| SUB-3 | `allocations[].status` | selalu `allocated` | `roll_service.py:1271`, `:2404`; `sales_order_helpers.py:182` | **ditulis, tak pernah berubah & tak pernah dibaca** (grep 0 pembaca). `allocations.$.quantity` diubah eskalasi `outbound_picking.py:399-401` tanpa memperbarui `rolls[]`; relink potong `roll_service.py:704-729`; pindah transfer `transfer_receipt_service.py:153` |
| SUB-4 | `pending_approvals[].status` | `pending` → `approved`/`rejected` · `pending` → `cancelled` · `rejected` → `cancelled` · `pending` → `superseded` | `so_approvals.py:296,322`; `services/so_approvals.py:174-178`; `so_release_service.py:133`; `routers/so_approvals.py:216` | `approve` menulis entri `nilai` tanpa CAS `sales_orders_extra.py:489` |
| SUB-5 | `dispatch_payment_release` | null → {…} → null (+history) | `dispatch_payment_gate.py:132-136` (CAS absen), `:151-154` (CAS `at`) | izin `order.release_unpaid` |
| SUB-6 | `loading_check` / `loading_checks.{wh}` | ∅ → {result clean\|with_issues\|simulated\|override} | `loading_check_service.py:123-127`, `:178-181` (`_save_result` `:38-42`, tanpa CAS) | lih. A4 |
| SUB-7 | `release{requested,hold,released_at}`, `verification.status` | — → requested/hold → released | `so_release_service.py:73-74,92-95,113`; `so_verify_service` | `release_hold` tanpa CAS |
| SUB-8 | `qc_request.status` | `required` → lulus/gagal (inspeksi) ; guard dispatch menulis ulang `required` | `inspection_service.py:1426`; `loading_check_service.py:276` | guard menulis di jalur cek (juga dari `trip_check`) |

### A2. `inventory_rolls` pada jalur SO (status, panjang, reservasi)

Konstanta: `ORDER_HELD_STATUSES = [reserved, committed, picked, packed, in_transit_sales]` `roll_service.py:232`;
`SHIPPABLE_STATUSES = [committed, packed, picked, reserved]` `:1438`; `EXPECTED_STATUSES` cek muat `loading_check_service.py:17`.
Penulis konstanta status roll di jalur ini (scan): hanya `in_transit_sales` (`:1482`) dan `delivered` (`:1529`) — sisanya
`<expr>`/`available`/`reserved`.

| # | dari → ke | pemicu | penjaga / CAS | efek | dibalik saat batal? | idempoten | pagar |
|---|---|---|---|---|---|---|---|
| R-01 | `available` → `reserved` (roll utuh) | `allocate_and_reserve_rolls` `roll_service.py:1155-1278` → `_reserve_single_roll` `:841-847`; `reserve_specific_rolls` `:2268-2345` (`:2309-2318`) | **CAS** `{status:available, length_reserved∉>0, active_movement:None}` | `reserved_ref={sales_order,id}`, `earmarked_for=None`; mutasi `reservation` per gudang (id roll digabung koma, SCH-6) `:1255-1262` / `record_reservation_movements` `:2409-2425`; `rebuild_balance` | ya (R-07) — tetapi `earmarked_for` tidak dipulihkan (ANOM-28) | CAS gagal → roll dilewati/409 | owner = PT penjual (`_available_rolls_for_order` `:898-926`); tanpa pagar lokasi (urutan gudang via `_site_id`) |
| R-02 | `available` (induk) → `available` + `length_reservations[{qty,status:reserved,ref}]` | `_reserve_length` `:580-598` (dari `:1222`, `:2301`) | **CAS** panjang bebas `$expr` + `status:available` + `active_movement:None` | `length_reserved` naik; saldo memecah bucket (`rebuild_balance` `:291-299`) | ya (R-07 menarik reservasi) | CAS | idem |
| R-03 | `reserved` (+`length_reservations.$[].status`) → `committed` | `set_order_rolls_status` `:1412-1435`; dipanggil approve `sales_orders_extra.py:442,500`, `so_approvals.py:361`, `so_lifecycle_service.py:58`, `so_release_service.py:139`, backorder `backorder_service.py:116` | **tanpa CAS** (`update_one({id})` `:1419-1421`); mengubah SEMUA status `ORDER_HELD` termasuk `in_transit_sales` ke `committed` | `rebuild_balance` | tidak ada transisi balik eksplisit (lepas → `available`) | ya | — |
| R-04 | reservasi panjang → roll anak (`status = rsv.status`) | `confirm_cut` `:604-650` / `_finish_cut` `:652-686` (`POST /api/inventory/rolls/{roll_id}/reservations/{rsv}/cut`) | CAS reservasi ada + panjang cukup | anak tanpa tag, `cut.identity_verified=False`; mutasi `roll_cut`/`cut_waste`; relink alokasi | — | idempoten via `pending_cut_ops` | (agen potong) |
| R-05 | `reserved`/`committed` (`picked/packed` tak pernah ada) → `in_transit_sales` | `ship_order_rolls` `:1441-1516` dari `dispatch_task` | klaim saga **tugas**; update roll **tanpa CAS** `:1480-1482`, `:1486-1490`; `assert_cut_identity_ready` `:1453`; `roll_ids` hasil pick `:1459-1466` | parsial → **roll dipecah**: induk dikurangi, anak `in_transit_sales` **tanpa tag** `:1484-1498`; `shipped_at`; mutasi `outbound_ship` (−) `:1504-1511`; biaya dibekukan ke `shipments.rolls[]`; `rebuild_balance` | **tidak** (tak ada void SJ; hanya retur) | 2× dispatch → 400 (tidak ada qty siap) | — |
| R-06 | `in_transit_sales` → `delivered` | `deliver_order_rolls` `:1519-1534` dari SO-08 | **tanpa CAS**; **per SO utuh** (bukan per SJ) | `delivered_at`; `rebuild_balance` (keluar `owned_qty`); **tanpa mutasi** | — | ya | — |
| R-07 | `reserved/committed/picked/packed/in_transit_sales` → `available` (semua milik SO) + tarik `length_reservations` | `release_order_rolls` `:1281-1326` — batal `sales_orders_extra.py:873`, lepas reservasi `:824`, kedaluwarsa `inventory_service.py:41`, rollback create `sales_orders.py:533,539`, alokasi gagal `:1238` | **tanpa CAS** (`update_one({id})` `:1310-1313`); **ikut `in_transit_sales`** | `reserved_ref=None`; mutasi `release_reservation` (dua jenis) `:1302-1307,1317-1322`; `rebuild_balance` | — | ya | — |
| R-08 | sebagian → `available` (per produk×gudang, qty) | `release_order_rolls_partial` `:1329-1409` — resolve eskalasi `outbound_picking.py:396-397`, override `so_override_service.py:123` | **tanpa CAS**; held = `ORDER_HELD_STATUSES` **termasuk `in_transit_sales`** `:1339-1342`, urut panjang naik | lepas utuh `:1373-1377` atau pecah → fragmen `available` `:1380-1392`; mutasi `release_reservation` | — | tidak (qty) | — |
| R-09 | `reserved` → `available` (per roll, rute khusus) | Ganti Roll `sales_orders_extra.py:627-629` (**tanpa mutasi**); lepas sebagian `:741-751`; batal baris `so_line_cancel_service.py:70-82` | **CAS** `{status:reserved, reserved_ref.id}` — `committed` **tidak** terlihat (ANOM-03/09) | Ganti Roll juga menarik reservasi potong yang dibuang `:633-643`; batal baris **tidak** (ANOM-09) | — | — | `inventory.pegging` |
| R-10 | `ORDER_HELD` → `available` (rollback) | `_release_rolls_by_ref_id` `:2348-2372` | tanpa CAS | **tanpa mutasi** (asimetris dg `reservation`, SCH-6) | — | ya | — |
| R-11 | `picked`, `packed` | — | — | **dibaca, tak pernah ditulis**: SHIPPABLE `:1438`, ORDER_HELD `:232`, EXPECTED `loading_check_service.py:17`, bucket `:207-208`; scan-pick tidak menyentuh roll | — | — | KN_15 §3.4.1 menghendaki `committed→picked→packed` |
| R-12 | (sampel) `available` → anak `reserved` | `sample_sale_service.py:440-447` | klaim tugas | `is_sample_cut` | — | — | (agen potong) |

`active_movement`: tidak ditulis jalur SO; reservasi mensyaratkan `None`. `reserved_ref`/`earmarked_for` lihat R-01/R-07.
`_split_roll` `:850-882` = kode mati (0 pemanggil).

### A3. `wms_tasks` `flow_type=outbound` (sumber SO)

Tahap tersimpan `stages=["created","picking","packing","staging","dispatched"]` (`fulfillment_status.py:92`; `wms.py:15-20`).
`NON_DISPATCHABLE={dispatched,cancelled,escalated}` (`shipment_service.py:24`).

| # | dari → ke | pemicu | penjaga / CAS | efek | dibalik saat batal SO? | idempoten | pagar |
|---|---|---|---|---|---|---|---|
| T-01 | ∅ → `created` \| `scheduled` (ambil, tgl > hari ini WIB) | `create_outbound_tasks_for_order` `fulfillment_status.py:77-144` — dari confirm `so_lifecycle_service.py:87`, `POST /api/wms/tasks/outbound-from-order/{id}` `wms.py:135-156`, backorder `backorder_service.py:121`, override `_regen_tasks` `so_override_service.py:199-206`, OD `special_order_phase2.py:770-777`, sampel `sample_orders.py:234`; salin transfer `transfer_receipt_service.py:169-173` | idempoten via `count_documents` (termasuk tugas `cancelled`) `:87-89` — tanpa indeks unik; iterasi **semua** `allocations` tanpa filter status | 1 tugas / alokasi (produk×gudang), `entity_id`=PT SO (tanpa `owner_entity_id`), `hold_until`; `doc_refs` picking_task↔SO `:135-137`; tugas `sample_cut` untuk baris sampel `:140-143`; **tanpa notifikasi** | ya → `cancelled` (T-10) | ya (cek jumlah) | `outbound-from-order`: `wms.create` + klaim saga **tanpa `assert_entity_access`** (ANOM-16) |
| T-02 | ∅ → `created` (tugas outbound bebas) | `POST /api/wms/tasks` `wms.py:65-132` | — | tanpa `order_id` (dispatch → KeyError) | — | — | `whscope.assert_usable`, `location_scope.assert_warehouse` `:73-77` (satu-satunya jalur outbound berpagar lokasi) |
| T-03 | `scheduled` → `created` | GET `/api/outbound/tasks` → `_auto_release_due_scheduled` `outbound_picking.py:15-23` (CAS status); `POST /api/outbound/tasks/{id}/release` `:96-113` | otomatis CAS; manual pra-cek lalu **update tanpa CAS** `:106-110` | `released_by/at` | — | manual 2× → 400 | `wms.update` + entitas |
| T-04 | `created` → `picking`; `created/picking/escalated/packing` → `packing` | `POST /api/outbound/tasks/{id}/scan-pick?actual_qty&roll_id&bin_id&lot&batch` `:150-255` | pra-cek `scheduled`/`dispatched`/`cancelled` `:175-178`; **CAS** `status ∉ {scheduled,dispatched,cancelled,completed}` + `picked_qty` tak berubah `:231-240` → **`escalated` lolos** | `picked_qty`, `scan_log` (roll di-resolve server atau `""`, FRM-03), `roll_id/bin/lot`; `audit`; `recompute_so_status` `:253`; **status roll tidak berubah** | — (tugas dibatalkan; tak ada "kembalikan ke rak") | berurutan = **aditif** (tanpa kunci idempoten); bersamaan → 409 | `wms.update` + entitas; `registration_freeze` `:184-185`; **tanpa `location_scope`** (SCP-2) |
| T-05 | `created/picking/packing/staging/scheduled/partially_shipped` → `escalated` | `POST /api/outbound/tasks/{id}/escalate?reason=` `:258-310` | **CAS** `status ∉ {dispatched,cancelled,completed,escalated}` `:288-289` | `escalation{status:pending_review}`; `audit`; **tanpa notifikasi manajer** | batal SO → tugas `cancelled` tetapi `escalation.status` tetap `pending_review` | 2× → 409 | `wms.update` + entitas |
| T-06 | `escalated` → `packing` (± qty) | `POST /api/outbound/tasks/{id}/resolve-escalation?adjusted_qty&resolution_notes` `:313-464` | pra-cek ada `escalation` & bukan resolved/resolving `:332-337`; klaim `{status:escalated, escalation.status∉…}` **hanya bila `adjusted_qty` & delta>0,01 & ada SO** `:339-352,393`; tulisan akhir filter **hanya** `escalation.status≠resolved` `:448-450` | dengan qty: `release_order_rolls_partial` (R-08), `allocations.$.quantity`, item+harga SO dihitung ulang, timeline `:395-446`; **tanpa `recompute_so_status`**; status → `packing` walau belum/terkirim penuh | — | 2× → 409 | `wms.approve` + entitas |
| T-07 | `escalation.resolving` → `pending_review` (status tugas tetap `escalated`) | `POST .../reopen-escalation` `:467-486` | **CAS** `escalation.status=resolving` | `reopened_by/at` | — | 2× → 409 | `wms.approve` + entitas |
| T-08 | `created→picking→packing→staging` | `POST /api/wms/tasks/{id}/advance?expected_status=` `wms.py:223-276` | **CAS** status `:268-271`; status di luar `stages` ditolak `:249-252` | **tanpa syarat pick** (ANOM-23); `staging→dispatched` = T-09 dengan `dispatch_guard` `:260-266` | — | 409 | `wms.update` + entitas |
| T-09 | `created/picking/packing/staging/partially_shipped` → `partially_shipped` \| `dispatched` | `POST /api/outbound/tasks/{id}/dispatch?ship_qty` `outbound_picking.py:490-516`; `POST /api/outbound/so/{id}/dispatch-batch?warehouse_id` `:519-534` → `dispatch_order_batch` `shipment_service.py:163-182`; advance | route: `dispatch_guard` (bayar, QC, serah potong sampel, cek muat, tag) `loading_check_service.py:281-333`; service: pra-cek `NON_DISPATCHABLE` `:49-50`, **klaim saga tugas** prasyarat status `:73-74`, baca ulang progres `:76-82`, `finish_set` `:118-127`; **status SO tidak dicek** | roll → `in_transit_sales` (R-05); `shipments` insert (A5); `scan_log` `dispatch`; `doc_refs` SJ↔SO, SJ↔tugas `:132-136`; `recompute_so_status` `:137`; hook OD; **GL pendapatan+HPP per SJ** `:147-159` | **tidak** | 2× → 400 | `wms.update` + entitas tugas / entitas SO (batch) |
| T-10 | non-`dispatched/completed/cancelled` → `cancelled` | batal SO `sales_orders_extra.py:885-888`; batal baris `so_line_cancel_service.py:85-88`; transfer rehome `transfer_receipt_service.py:160-162` | `update_many` dengan filter status | `cancel_reason/cancelled_by`; `escalation` dibiarkan | — | ya | — |
| T-11 | `*` → dihapus | override SO `confirmed` `_regen_tasks` `so_override_service.py:199-206` | `lock_reason` (belum dipick) `:32-47` | `delete_many` + buat ulang (termasuk `sample_cut`) | — | — | `order.override` |
| T-12 | (penugasan) `assigned_to` | `POST /api/wms/tasks/{id}/takeover` `wms.py:167-190` | tolak terminal; update tanpa CAS | `takeover_log`, audit+alasan | — | — | supervisor (`location_scope.is_supervisor`) |

Status tugas outbound **dibaca, tak pernah ditulis**: `completed` (filter `outbound_picking.py:232,289`; `wms.py:24`),
`picked` (`order_journey_service.py:153`), `done`. `staging` hanya lewat `advance`.
**Beda `sample_cut`** (catat, dibahas agen potong): `task_subtype=sample_cut`, `allocation_id=None` saat lahir
(`sample_sale_service.py:268-283`); aksi potong menulis `status=packing, picked_qty=quantity=take` + `scan_log.scan_type="cut"`
dengan `roll_id` = roll **induk** (`:470-479`); `picked_roll_ids` hanya membaca `scan_type=="pick"` (`shipment_service.py:31-39`)
→ dispatch tugas potong memilih roll FIFO; scan-pick/eskalasi/advance tidak membedakan subtipe.

### A4. Cek muat `loading_check` (`rfid_verify_sessions.kind="loading_check"` + `sales_orders.loading_check(s)`)

| # | dari → ke | pemicu | penjaga / CAS | efek | idempoten | pagar |
|---|---|---|---|---|---|---|
| L-01 | ∅ → `open` | `POST /api/outbound/so/{id}/loading-check/start?warehouse_id` `outbound_picking.py:543-551` → `start` `loading_check_service.py:55-99` | kembalikan sesi terbuka bila ada `:63-65`; `assert_cut_identity_ready` `:68`; ≥1 roll `EXPECTED_STATUSES` `:69-72` | `expected` = **semua** roll SO di gudang itu (bukan per tugas/pengiriman) `:45-52`; `untagged[]`; `not_committed_count` (komentar keliru, ANOM-21) | ya | `wms.update`; entitas SO ∈ scope `:61-62`; tanpa lokasi |
| L-02 | `open` (+`scanned_epcs`) | `POST /api/outbound/loading-check/{sid}/scan` body `{epcs[], source}` `:554-559` → `scan_session` `rfid_print_service.py:583-612` | CAS `status=open & saga_lock absen` `:607-610`; `source ∈ {manual,device,simulated}` `:580` | `$addToSet` | ya | scope entitas sesi; FRM-11 |
| L-03 | `open` (+`untagged_resolved`) | `POST .../{sid}/scan-label` body `{code, reason}` `:562-576` → `scan_label` `:134-158` | izin `wms.untagged_override`; alasan ≥5; CAS `open & !saga_lock` `:151-157` | `untagged_exceptions[]`; `audit` | `$addToSet` | idem |
| L-04 | `open` → `completed` (`result` = `clean` \| `with_issues` \| `simulated`) | `POST .../{sid}/complete` `:611-619` → `complete` `:102-131` | klaim saga prasyarat `open` `:114-115`; `finish_set` `:128-130` | `sales_orders.loading_check(s).{wh}` (`_save_result` tanpa CAS `:38-42`) + `manifest` (roll+panjang) | 2× → 400 | scope entitas |
| L-05 | SO: ∅/apa pun → `override` | `POST /api/outbound/so/{id}/loading-check/override` body `{reason, warehouse_id}` `:579-591` → `override` `:171-182` | `wms.approve`; alasan ≥5; tolak bila ada sesi `open` | `manifest` snapshot; `audit` | menimpa | entitas SO |
| L-06 | (tag simulasi) | `POST /api/outbound/so/{id}/loading-check/simulate-tags` body `{warehouse_id}` `:594-608` → `simulate_tags` `:195-220` | hanya bila `wms.rfid_simulation` hidup | tag `simulated=True` | ya | entitas SO |
| L-07 | efek ke dispatch | `dispatch_guard` `:281-333` | urut: gerbang bayar CBD/DP `:287-288` → QC pesanan `:289` → serah potong sampel `:290-295` → sesi `open` = blok `:296-297` → **tanpa hasil**: kebijakan gudang `required` & bukan gedung gate-OUT = blok `:304-308`; ada roll tanpa tag aktif = blok `:310-314`; **dengan hasil**: `simulated` hanya lolos bila lengkap & mode simulasi hidup `:316-320`; selain `clean/override/simulated` = blok `:321-325`; roll siap kirim harus ⊆ manifest (roll & panjang sama) `:327-333` | — | gedung gate-OUT tertaut (`gate_txn_service.gate_validates` `:75-81`): cek muat handheld **opsional**; validasi gate per trip **sesudah** SJ terbit — sesi gate SJ ditutup saat `in_transit/delivered/completed/pickup` (`logistics_service.py:590-593,640,653-658`) = sesuai K-GDG-02/§9 (tidak memblokir keberangkatan) | `GET /outbound/so/{id}/loading-check` **tanpa pagar entitas** `:622-625` |

Tidak ada endpoint batal/abaikan sesi `open`; batal SO meninggalkan sesi `open`.

### A5. `shipments` (Surat Jalan)

| # | dari → ke | pemicu | penjaga | efek | dibalik? | idempoten |
|---|---|---|---|---|---|---|
| S-01 | ∅ → `dispatched` | `dispatch_task` `shipment_service.py:97-117` (penulis lain: retur `return_cutloss_split_service.py:244`, `return_roll_settlement_service.py:527`) | klaim tugas; SJ ditulis sebelum tugas dinyatakan terkirim (AX-02) | `shipment_no` (bersama per batch), `rolls[]` + biaya, `is_partial`, `gl_status`; `doc_refs` | **tidak ada jalur void/batal** — `cancelled/void/voided` dibaca (`so_delivery_service.py:19`, `gl_service.py:908`) tak pernah ditulis | — |
| S-02 | `logistics_status`: None → `prepared` → … (cermin A6) | `logistics_service.py:234-246` (klaim atomik `logistics_id` kosong), `:590-591`, `:639` | `update_many` | dipakai `pod_progress` `so_delivery_service.py:22-28` | rollback create `:238-246` | — |
| S-03 | `gl_status`: → `posted` \| `failed` | `shipment_service.py:150-158`; ulang `routers/posting_failures.py:80` | — | — | — | backfill idempoten |

Dokumen SJ lama per SO `GET /api/outbound/so/{id}/surat-jalan` mencetak `task.quantity` (rencana), bukan qty terkirim
(`outbound_picking_extra.py:144-153`).

### A6. `logistics_deliveries` (Logistik / trip)

`TRANSITIONS` `logistics_service.py:31-38`; ambil sendiri `PICKUP_TRANSITIONS` `:39`.

| # | dari → ke | pemicu (`routers/logistics.py` → service) | penjaga / CAS | efek | idempoten | pagar |
|---|---|---|---|---|---|---|
| D-01 | ∅ → `prepared` | `POST /api/logistics/deliveries` `:205-215` → `create_delivery` `:145-247` | SJ ada, PT sama, belum diangkut, `status=dispatched`; ambil ≠ digabung; moda ↔ metode SO; sopir bebas; **klaim SJ atomik** `:234-237` + rollback | nomor `LG-`, kode pickup, `orders[]`; tanpa `doc_refs` | ulang → 400 "sudah diangkut" | `logistics.manage`; PT = PT aktif |
| D-02 | `prepared` → `loaded` | `POST /deliveries/{id}/transition {to:"loaded"}` `:323-337` → `transition` `:532-612` | wajib foto `load` `:544-547`; **update tanpa CAS** `:588-589` | `loaded_at`; `shipments.logistics_status` | ulang → 400 | `logistics.update`; entitas; sopir hanya miliknya `:32-36` |
| D-03 | `loaded` → `in_transit` | idem | resi (ekspedisi) / plat+sopir (armada), sopir bebas `:548-556` | `departed_at`, `fleet.mark_on_trip`, tutup sesi gate (`shipment_departed`) | 400 | idem |
| D-04 | `loaded` → `prepared` (bongkar) | idem | `logistics.manage` `:329-330`; alasan ≥5 | `loaded_at=None` | — | idem |
| D-05 | `loaded`/`in_transit` → `failed` | idem | alasan ≥5 | notifikasi sales; armada dilepas; **roll/SO/GL tidak disentuh** | — | idem |
| D-06 | `failed` → `prepared` | idem | — | jadwal ulang | — | idem |
| D-07 | `in_transit` → `delivered` | idem `{to:"delivered", receiver_name, received_at, note}` | wajib foto `pod` + nama penerima `:562-570` | `pod{}`, `delivered_at`; tutup sesi gate; notifikasi; `so_delivery.on_pod` → SO-08 bila SEMUA SJ aktif SO ber-POD **dan** SO `shipped`; hook OD | ulang → 400 | idem |
| D-08 | `delivered` → `completed` | idem | — | `completed_at`; `on_pod` lagi (idempoten) | — | idem |
| D-09 | `prepared` → `delivered` (ambil sendiri) | `POST /deliveries/{id}/pickup-handover` `{pickup_code, picker_name, picker_id_no, note}` `:225-239` → `pickup_handover` `:615-650` | kode harus cocok (salah → `pickup_attempts+1`) `:626-633`; **update tanpa CAS** `:634-637` | `pod.verified_by_code`; SJ `delivered`; tutup sesi gate; `on_pod` | ulang → 400 | `logistics.update`; entitas |
| — | posisi / foto | `POST /deliveries/{id}/positions` `{location, lat, lng, note}` (hanya `loaded/in_transit`) `:500-516`; `POST .../photos` multipart `kind=load\|pod\|other` `:457-477`; hapus | — | `positions[]`, `photos[]`, timeline | — | sopir miliknya |

### A7. Sentuhan finansial (hanya apakah dipicu otomatis)

| # | peristiwa | otomatis? | berkas:baris |
|---|---|---|---|
| F-1 | Pendapatan + HPP | **ya, per SJ saat dispatch** (best-effort, `gl_status`) | `shipment_service.py:147-159` → `gl_service.post_order_revenue_and_cogs` `:873-895` |
| F-2 | Jurnal balik | ya, saat batal / kedaluwarsa (best-effort) | `sales_orders_extra.py:897-903`; `inventory_service.py:61-66` |
| F-3 | Invoice | **tidak** — `POST /sales-orders/{id}/simulate-payment` manual membuat `invoices` berstatus `paid` | `routers/invoices.py:37-125` |
| F-4 | Faktur Pajak | **tidak** — terbit manual (≥ `confirmed`) | `tax_invoice_service.issue_tax_invoice` `:136-163` |
| F-5 | Gerbang bayar CBD/DP | ya, di `dispatch_guard` | `dispatch_payment_gate.guard` `:92-106` |

---

## (b) Kandidat anomali (urut dampak)

Klasifikasi: **[K]** = pasti dari kode (jalur deterministik terbaca) · **[R]** = perlu dibuktikan runtime (balapan,
ketergantungan data/konfigurasi, atau perilaku yang mungkin ditutup lapisan lain).

**ANOM-01 [K] — Resolve eskalasi dengan `adjusted_qty` pada tugas `partially_shipped` melepas roll yang SUDAH DIKIRIM ke `available`**
* Berkas: `routers/outbound_picking.py:288-289` (eskalasi membolehkan `partially_shipped`), `:393-397`;
  `services/roll_service.py:1339-1342` (held = `ORDER_HELD_STATUSES` termasuk `in_transit_sales`), `:1366-1377` (urut panjang
  naik, lepas utuh), `:1380-1392` (pecah jadi fragmen `available`).
* Penalaran: SO 100 = roll A 20 + roll B 80. Pick A 20 → dispatch 20 → A `in_transit_sales`, tugas `partially_shipped`
  (shipped 20, picked 20). Eskalasi → resolve `adjusted_qty=20` (≥ picked, lolos `:378-381`) → delta 80 →
  `release_order_rolls_partial`: A (20, in_transit) dilepas utuh → `available`; B dipecah: B 20 tetap `committed`,
  fragmen 60 `available`. Tugas → `packing` padahal `shipped=quantity` → tak bisa dispatch lagi (max_ship 0).
* Dampak: roll di jalan/di pelanggan tampil tersedia & bisa dijual lagi; sisa 20 B terkunci ke SO; tugas macet `packing`;
  `allocations[].rolls` basi; SO tidak di-recompute.
* Runtime: perlu — mudah dan deterministik (resep C-P1). Ini bukti paling kuat.

**ANOM-02 [K] — Resolve eskalasi TANPA `adjusted_qty` tidak mensyaratkan status `escalated` → tugas `cancelled`/`dispatched` hidup lagi jadi `packing`; scan-pick boleh pada tugas `escalated`**
* Berkas: `outbound_picking.py:332-337` (pra-cek hanya sub-dok), `:393` (klaim hanya di cabang qty), `:448-450` (filter final
  hanya `escalation.status≠resolved`); `:231-233` (scan-pick CAS tidak menolak `escalated`); batal SO meninggalkan
  `escalation.status=pending_review` `sales_orders_extra.py:885-888`.
* Penalaran: (a) eskalasi → batal SO (tugas `cancelled`) → resolve → tugas `packing` (komentar KN-C02 `:286-287` menyatakan
  justru ini yang dicegah). (b) eskalasi → scan-pick penuh → `packing` → dispatch (packing bukan NON_DISPATCHABLE) →
  `dispatched` → resolve → kembali `packing`.
* Dampak: eskalasi bisa dilompati; tugas hantu di antrean Barang Keluar untuk SO batal/terkirim; status SO tak sinkron.
* Runtime: perlu (deterministik, resep C-P2).

**ANOM-03 [K] — Override SO & Ganti Roll pada SO `approved/confirmed` tidak melihat roll `committed` → reservasi ganda, roll yatim, backorder palsu**
* Berkas: `so_override_service.py:20` (EDITABLE memuat `approved`,`confirmed`), `:101-108` (`_held` hanya `status:"reserved"`),
  `:115-123`, `:216-228`, `:157-167`, `:237-239`; `sales_orders_extra.py:570` (Ganti Roll boleh `approved`), `:579-581`
  (`current` hanya `reserved`), `:664-670`.
* Penalaran: sesudah approve, roll `committed` (R-03). Override qty naik 100→120: held=0 → `_reserve(120)` (bukan 20) →
  alokasi dibangun ulang dari roll `reserved` saja; roll `committed` 100 tetap `reserved_ref=SO` tetapi hilang dari
  `allocations`. Qty turun: `_release` tak menemukan apa pun → `backorder_qty = qty penuh` → backorder palsu + diisi otomatis lagi.
  Hapus baris: roll `committed` produk itu tidak pernah dilepas (bahkan sesudah SO `done`). Roll baru berstatus `reserved`
  di SO yang sudah approved.
* Dampak: stok terkunci ganda/selamanya, tugas ambil (regen) hanya untuk alokasi baru, dispatch bisa mengirim roll yatim
  (SHIPPABLE mencakup `committed`).
* Runtime: perlu (deterministik, resep C-P3).

**ANOM-04 [K] — Backorder tidak pernah terisi lagi sesudah gudang mulai mengambil/mengirim → SO macet `partially_shipped`, tak pernah `done`**
* Berkas: `backorder_service.py:26` (`ACTIVE` tanpa `partially_picked/picked/partially_shipped`), `:38-41` (klaim gagal →
  `busy`), `:143`; `fulfillment_status.py:47-57` (backorder terbuka menahan `shipped`); `so_delivery_service.py:33-35`
  (POD hanya menutup `shipped`); `fulfill_from_stock` → 409 "sedang diproses pemenuhan lain" `:216-219` (pesan menyesatkan).
* Penalaran: KN_16 §2 "Partial shipment: boleh kirim sebagian → sisa jadi backorder". Begitu satu SJ terbit, SO keluar dari
  `ACTIVE`; GRN/QC/interco tidak mengisinya, rencana pemenuhan Admin Sales ditolak.
* Dampak: SO tidak pernah selesai; roll SJ yang sudah ber-POD tetap `in_transit_sales` (ANOM-05); antrean backorder palsu.
* Runtime: perlu (resep C-P4) — satu-satunya jalan keluar yang terlihat: amandemen qty (`amendment_service` `_sync_backorders`).

**ANOM-05 [K] — POD per Surat Jalan tidak memindah roll; `in_transit_sales → delivered` hanya saat SO utuh `done`**
* Berkas: `so_delivery_service.py:31-46`; `roll_service.py:1519-1534`; `logistics_service.py:603-605`.
* Penalaran: KN_15 §3.4.1 & KN_16 §7: `in_transit_sales → sold` saat POD diterima. Kode: roll baru `delivered` bila SO `shipped`
  **dan** semua SJ aktif ber-POD. SO kirim bertahap / ber-backorder → roll SJ yang sudah diterima tetap "di jalan".
  Status tujuan juga `delivered` (bukan `sold`); tanpa mutasi.
* Dampak: `in_transit_sales_qty`/`owned_qty` membengkak; laporan barang di jalan salah.
* Runtime: tidak wajib (logika lurus); cukup dikonfirmasi pada resep C-P4.

**ANOM-06 [K] — Kedaluwarsa reservasi 3 hari berlaku untuk backorder murni (`waiting_stock`) dan SO `approved` (komit keras); tak pernah diperpanjang; tanpa CAS**
* Berkas: `routers/sales_orders.py:544,651` (sekali di create); `inventory_service.py:29-35,41-52`; bertentangan dengan
  `so_status.py:187` ("otomatis lanjut saat barang masuk") dan KN_15 §3.4.1 (`committed` = hard commit). Pemicu GET = STK-11.
* Dampak: pesanan menunggu PO > 3 hari dibatalkan diam-diam saat seseorang membuka daftar SO/dasbor; SO yang sudah disetujui
  manajer tetapi ditahan Admin Sales (`release.hold`) ikut gugur; balapan dengan confirm (tanpa CAS) dapat menghasilkan SO
  `expired` dengan tugas ambil hidup.
* Runtime: logika [K]; balapan [R]. Pembuktian data: hitung SO `expired` yang punya `backorders[]` (tanpa menulis).

**ANOM-07 [R] — Batal SO melepas roll `in_transit_sales` (status dibaca dari SO, bukan dari roll/tugas); dispatch tidak menghormati klaim SO**
* Berkas: `roll_service.py:232,1284-1286,1310-1313`; `sales_orders_extra.py:869-874`; `shipment_service.py:73-74` (klaim tugas,
  bukan SO), `:137`; `fulfillment_status.py:73` (recompute tanpa CAS).
* Penalaran: (1) balapan batal ↔ dispatch: batal membaca SO `picked`, klaim; dispatch memindah roll ke `in_transit_sales` &
  recompute → `shipped`; batal `release_order_rolls` mengembalikan roll terkirim ke `available`, lalu CAS gagal 409 → SO tetap
  terkunci `saga_lock`. (2) Tanpa balapan: bila recompute gagal sesudah roll dipindah (AX-02 menandai saga gagal), SO masih
  `picked` → batal diizinkan → roll terkirim kembali `available`.
* Dampak: stok fantom + SJ/GL berjalan + SO terkunci.
* Runtime: perlu (balapan / injeksi kegagalan) — sulit tanpa alat konkurensi; uji minimal = dua permintaan bersamaan.

**ANOM-08 [K] — SO `draft` bisa memegang roll (Ganti Roll), tak pernah kedaluwarsa, dan batal TIDAK melepasnya**
* Berkas: `sales_orders_extra.py:570` (Ganti Roll boleh `draft`), `:692-693` (status hanya diubah dari `reserved/waiting_stock`),
  `:871-873` (daftar lepas tanpa `draft`); `inventory_service.py:31` (kedaluwarsa tanpa `draft`); `so_lifecycle_service.py:51`
  (submit tak menerima `draft`).
* Jalur: create → `release-reservation` (→`draft`) → `items/{pid}/reallocate` (roll `reserved`, SO tetap `draft`) → `cancel` →
  roll tetap `reserved_ref` ke SO `cancelled` (varian SSOT-8 lewat jalur batal).
* Runtime: perlu (deterministik, resep C-P5).

**ANOM-09 [K] — Batal baris SO (`so_line_cancel_service`) tidak menarik reservasi potong, menolak roll `committed` dengan pesan salah, dan tidak me-recompute status SO**
* Berkas: `so_line_cancel_service.py:44-48` (`committed` dihitung "sudah dipick/dikemas/dikirim"), `:67-73` (hanya `reserved`),
  tidak ada penarikan `length_reservations` (bandingkan `sales_orders_extra.py:633-643`), `:85-88,115` (tanpa
  `recompute_so_status`).
* Dampak: panjang roll induk tetap dipesan SO untuk baris yang sudah dihapus (SSOT-8, jalur baru); baris SO approved tak bisa
  dibatalkan; SO bisa tertahan `partially_shipped` walau sisa baris terkirim semua.
* Runtime: perlu (jalur OD: batal item Pesanan Khusus `routers/special_orders.py:891-932`).

**ANOM-10 [K] — Konfirmasi tidak menunggu stok; SO backorder murni bisa `confirmed` tanpa tugas, dan pengisian backorder kemudian tidak melahirkan tugas ambil**
* Berkas: `so_lifecycle_service.py:62-91` (tanpa cek backorder); `so_status.py:9-10` (klaim "naik ke Confirmed hanya saat stok
  benar-benar siap"); `backorder_service.py:114-123` (tugas hanya bila SO **sudah** punya tugas).
* Dampak: SO `confirmed` + roll `committed` tanpa tugas di gudang (jalan keluar manual: `POST /wms/tasks/outbound-from-order`).
* Runtime: perlu (resep C-P6).

**ANOM-11 [K] — Tidak ada batal-pick; roll yang sama boleh dipindai berulang**
* Berkas: `outbound_picking.py:116-147` (tanpa cek `scan_log`), `:190-199` (hanya batas total), pesan `:182` merujuk "pembatalan
  pick" yang tidak ada (grep 0 endpoint); `shipment_service.py:31-39` (dedup) + `roll_service.py:1459-1466` → 409 permanen.
* Dampak: salah pick = tugas macet (hanya eskalasi qty ≥ picked); terkait FRM-03.
* Runtime: perlu (deterministik).

**ANOM-12 [K] — Kirim sebagian roll memecah roll diam-diam saat dispatch; anak tanpa tag lolos gerbang identitas WM-02**
* Berkas: `roll_service.py:1452-1453` (komentar "Tidak ada lagi potong otomatis saat dispatch"), `:1484-1498` (pecah),
  `:742-756` (gerbang hanya `cut.identity_verified=False`); `insert_child_roll` `:122-124` (anak tanpa tag).
* Pemicu: `ship_qty` < panjang roll atau `actual_qty` pick < panjang roll (`_resolve_pick_roll` membolehkan) → anak
  `in_transit_sales` tanpa tag/label; induk sisa tetap `committed` ke SO (bisa yatim bila tugas ditutup lewat eskalasi).
* Runtime: perlu (deterministik).

**ANOM-13 [R] — Cek muat per SO×gudang mengharapkan SEMUA roll SO (termasuk tugas yang belum dipick) → kirim sebagian wajib override**
* Berkas: `loading_check_service.py:45-52,69,119`.
* Dampak: di gudang `loading_check_policy=required` setiap pengiriman parsial = "with_issues"/override berizin.
* Runtime: perlu (konfigurasi gudang & data).

**ANOM-14 [K] — Transisi logistik & serah-terima ambil tanpa CAS; gagal kirim tidak punya jalur balik stok/SO/GL; SJ tak bisa di-void**
* Berkas: `logistics_service.py:532-538` (baca) vs `:588-589` (tulis `{id}`); `:615-637`; `failed` hanya notifikasi
  (`:571-575,600-601`); SJ status tetap `dispatched` (A5 S-01).
* Dampak: dua petugas bersamaan (`delivered` & `failed`) sama-sama menulis + efek samping ganda; barang kembali ke gudang
  setelah gagal tetap `in_transit_sales` & berpendapatan.
* Runtime: CAS [R] (balapan); celah jalur balik [K].

**ANOM-15 [K] — `is_issued` mencari Faktur `status≠"cancelled"`, padahal Faktur batal = `"batal"` → SO terkunci override/batal-baris selamanya sesudah Faktur dibatalkan**
* Berkas: `amendment_service.py:277-278` vs `tax_invoice_service.py:143,242`; dipakai `so_override_service.py:44`,
  `so_line_cancel_service.py:62`. (Batal SO memakai `"batal"` dengan benar `sales_orders_extra.py:859`.)
* Runtime: tidak wajib; konfirmasi dengan 1 Faktur batal.

**ANOM-16 [K] — `POST /wms/tasks/outbound-from-order/{id}` tanpa `assert_entity_access`; `GET /outbound/so/{id}/loading-check` tanpa pagar entitas**
* Berkas: `wms.py:135-156`; `outbound_picking.py:622-625`.
* Dampak: pengguna PT lain (izin `wms.create`) dapat melahirkan tugas untuk SO PT lain yang belum bertugas (mis. ANOM-10) dan
  membaca status cek muat + daftar roll belum bertag.
* Runtime: perlu (dua akun PT berbeda).

**ANOM-17 [R] — Create SO memakai `payload.entity_id` / `customer.entity_id` tanpa `resolve_requested_entity`**
* Berkas: `routers/sales_orders.py:197-198` (bandingkan pratinjau `sales_orders_extra.py` → `resolve_requested_entity`,
  `entity_scope.py:590-614`); pelanggan dicari tanpa pagar PT `:103`.
* Dampak: sales PT A dapat memesan & mereservasi stok PT B (atau SO mendarat di PT pelanggan, bukan PT aktif).
* Runtime: perlu (akun sales satu PT; mungkin ada pagar lain di lapisan dependensi).

**ANOM-18 [K] — `recompute_so_status` menulis status tanpa CAS; bisa menimpa `cancelled`/`expired`/`done` hasil proses paralel**
* Berkas: `fulfillment_status.py:32-37` (baca) vs `:73` (tulis `{id}`), mengabaikan `saga_lock`.
* Runtime: perlu (balapan scan-pick ↔ batal).

**ANOM-19 [K] — `mark-delivered`/POD memindah roll ke `delivered` SEBELUM CAS SO**
* Berkas: `sales_orders_extra.py:546-548`; `so_delivery_service.py:42-48` (409 ditelan → roll sudah `delivered`, SO tidak).
* Runtime: perlu (balapan manual vs POD).

**ANOM-20 [K] — Batal SO sesudah pick: roll langsung `available` di bin padahal fisik di area staging; tak ada tugas kembalikan**
* Berkas: `sales_orders_extra.py:871-873,885-888`; tidak ada pembuat tugas put-back.
* Runtime: tidak wajib (celah rancangan).

**ANOM-21 [K] — Status roll saat kirim tergantung jalur: konfirmasi langsung dari `reserved` tidak meng-commit roll; `picked/packed` tidak pernah ditulis; komentar cek muat keliru**
* Berkas: `so_lifecycle_service.py:84` (asal `reserved`, tanpa `set_order_rolls_status`); `roll_service.py:1438`
  (SHIPPABLE memuat `reserved`); `loading_check_service.py:91-94` ("ship_order_rolls hanya kirim roll committed" — salah);
  KN_15 §3.4.1.
* Dampak: bucket `reserved_qty` vs `committed_qty` tidak mencerminkan tahap; papan stok/pegging salah baca.

**ANOM-22 [K] — Gerbang bayar membaca `order.is_sample` yang tidak ada di dokumen SO → sampel berbayar ikut dinilai termin**
* Berkas: `dispatch_payment_gate.py:24-26,66`; SO menyimpan `order_type`/`has_sample` (`sales_orders.py:665-670`).
* Runtime: perlu (sampel berbayar dengan termin ber-DP).

**ANOM-23 [K] — `advance` outbound memajukan `created→picking→packing→staging` tanpa pick sama sekali**
* Berkas: `wms.py:241-271` (tak ada syarat `picked_qty`); dispatch baru menolak di `shipment_service.py:58-61`.
* Dampak: papan gudang menampilkan "Siap muat" untuk tugas kosong.

**ANOM-24 [K] — Resolve eskalasi tidak memanggil `recompute_so_status`, tidak memperbarui `allocations[].rolls`, dan memaksa `packing` walau qty belum terpick**
* Berkas: `outbound_picking.py:360-364,399-401,448-464`.

**ANOM-25 [K] — `decide_approval` melepas `saga_lock` tanpa token sesudah `so_transition` mencabutnya → bisa membuang kunci saga lain**
* Berkas: `routers/so_approvals.py:313-316`; `sales_order_helpers.py:245`; `atomic_claim.py:53-56`.
* Runtime: perlu (balapan; dampak rendah).

**ANOM-26 [K] — Rilis manual tugas terjadwal tanpa CAS (bisa menghidupkan tugas `cancelled`)**
* Berkas: `outbound_picking.py:104-110`. Runtime: balapan (rendah).

**ANOM-27 [K] — Eskalasi gudang tanpa notifikasi ke manajer** — `outbound_picking.py:304-308` hanya `audit()`;
`services/escalation_service.py` adalah eskalasi NOTIFIKASI, tidak memindai `wms_tasks.escalation`.

**ANOM-28 [K] — Pegging (`earmarked_for`) hilang permanen sesudah reservasi dilepas** — reservasi menolkan
`earmarked_for` (`roll_service.py:845`, `:2312`), pelepasan tidak memulihkannya (`:1310-1313`).

**ANOM-29 [K] — `allocations[].status` = `allocated` selamanya** (SUB-3) — field mati; status alokasi yang diminta
(picked/shipped) tidak ada; progres hanya di `wms_tasks`.

**ANOM-30 [K] — OD mengonfirmasi SO tanpa CAS & tanpa gerbang verifikasi/ACC** — `special_order_phase2.py:779`
(catat untuk agen OD).

Catatan kecil (tidak dinomori): SJ lama per SO mencetak qty rencana (`outbound_picking_extra.py:144-153`); `_split_roll` kode
mati (`roll_service.py:850`); rollback `reserve_specific_rolls` tanpa mutasi pelepasan (`:2348-2372`, SCH-6); `create_delivery`
gagal palsu bila `shipment_ids` berisi duplikat (`logistics_service.py:150-152` vs `:237`); `release-reservation` tidak
menolkan `items[].reserved_qty`; batal SO membiarkan sesi cek muat `open`.

---

## (c) Resep uji runtime

**Prasyarat & keselamatan.** Jalankan HANYA di DB dev hasil `bash scripts/dev_restore_demo.sh` (bukan DB reviewer), satu skenario
sekali jalan (AGENTS.md: jangan dua POC bersamaan). Peringatan STK-11: `GET /api/sales-orders`, `/sales-orders/stats/summary`,
`/dashboard`, `/products` MENJALANKAN `expire_old_reservations` → baca SO lewat `GET /api/sales-orders/{id}` saja.
Login: `POST /api/auth/login` body `{"email":"admin@kainnusantara.id","password":"<sandi demo — AGENTS.md>"}` (`schemas.py:161-163`) → ambil
`token` (`routers/auth.py:139`), kirim `Authorization: Bearer <token>` + `X-Entity-Id: <id PT>` (wajib satu PT untuk tulis).
Admin memegang semua izin; kolom "izin" menyebut izin minimum (peran bawaan `permissions_config.py`).

**Data awal (GET saja):** pelanggan PT itu (`GET /api/customers/{id}` → `id`, `addresses[].id`); produk ber-stok;
`GET /api/inventory/rolls/available?product_id={PID}&entity_id={E}&limit=50` (roll + `length_remaining`);
`POST /api/sales-orders/preview-allocation` body `AllocationPreviewIn` `{"items":[{"product_id":PID,"quantity":Q,"unit":"meter"}],
"entity_id":E,"customer_id":C}` (`schemas.py:554-564`, baca-saja). Bukti sesudah tiap langkah:
`GET /api/sales-orders/{SO}`, `GET /api/inventory/rolls?product_id={PID}&status=<s>`, `GET /api/inventory/movements?product_id={PID}`,
`GET /api/inventory/balances?product_id={PID}`, `GET /api/outbound/tasks?status=<s>`, `GET /api/shipments?order_id={SO}`.

### C-1. Alur penuh (bahagia)

| # | langkah | method & path | body / query (field persis — model:baris) | izin | yang diperiksa |
|---|---|---|---|---|---|
| 1a | buat SO qty penuh | `POST /api/sales-orders` | `SalesOrderCreate` (`schemas.py:525-548`): `{"customer_id":C,"shipping_address_id":A,"entity_id":E,"items":[{"product_id":PID,"quantity":Q,"unit":"meter"}],"allow_backorder":false,"confirm_mixed_lot":true,"payment_term_code":"NET30","fulfillment_method":"kirim","qc_request":"none"}`; item = `SalesOrderItemIn` `:483-517` | `order.create` | `status=reserved`; roll `reserved`, `reserved_ref.id=SO`; mutasi `reservation`; `allocations[].status=allocated` |
| 1b | varian potong dari roll | idem | item `{"product_id":PID,"quantity":X,"unit":"meter","purchase_mode":"roll","roll_lines":[{"roll_id":R,"take_qty":X}],"target_quantity":X,"rounding_choice":"exact_cut"}` (`RollLineIn` `:416-420`; X < panjang R) | `order.create` + `order.exact_cut` | roll R tetap `available`, `length_reservations[{qty:X,status:reserved}]`, `length_reserved=X` |
| 1c | varian backorder | idem | `quantity` > tersedia, `"allow_backorder":true` | `order.create` | `reserved` + `backorders[waiting_stock]` (atau `waiting_stock` bila 0 tersedia) |
| 2 | verifikasi admin | `POST /api/sales-orders/{SO}/verify` | `VerifyIn {"note":""}` (`routers/work_desks.py:27-28`) | `order.verify` | `verification.status=verified` |
| 3 | ajukan | `POST /api/sales-orders/{SO}/submit-for-approval` | — | `order.update` | `waiting_approval`, entri `nilai` pending |
| 4 | setujui | `POST /api/sales-orders/{SO}/approve` (atau `POST /api/sales-orders/{SO}/approvals/{AID}/decide` `SoApprovalDecision {"decision":"approve","notes":""}` `schemas.py:802-805`) | — | `order.approve` | `approved`; roll → `committed`; `length_reservations.status=committed` |
| 4' | satu tombol (alternatif 2–5) | `POST /api/sales-orders/{SO}/review-release` | `ReviewReleaseIn {"note":"","hold":false}` (`routers/so_release.py:16-18`) | `order.confirm` | langsung `confirmed` bila tak ada ACC |
| 5 | konfirmasi | `POST /api/sales-orders/{SO}/confirm` | — | `order.confirm` | `confirmed`; tugas `created` per alokasi (`GET /api/outbound/tasks?status=created`) |
| 5b | (1b) potong fisik | `POST /api/inventory/rolls/{R}/reservations/{RSV}/cut` lalu `POST /api/inventory/rolls/{CHILD}/verify-identity` | `CutConfirmPayload {"actual_length":X,"waste":0,"note":""}` (`routers/inventory.py:549-552`); `LabelVerifyPayload {"scanned_code":"<roll_no anak>"}` | `wms.update` | anak `reserved/committed`, `cut.identity_verified=true` |
| 6 | daftar ambil | `GET /api/outbound/tasks/{T}/pick-list` | — | `wms.view` | roll & reservasi potong |
| 7 | scan-pick dengan roll | `POST /api/outbound/tasks/{T}/scan-pick?actual_qty={len}&roll_id={roll_no\|id\|EPC}&bin_id=` | **query string** (bukan body) `:150-159` | `wms.update` | `picked_qty`, status `picking/packing`; status roll **tidak** berubah (R-11) |
| 8 | eskalasi | `POST /api/outbound/tasks/{T}/escalate?reason=Stok%20fisik%20kurang` | query | `wms.update` | `escalated`, `escalation.status=pending_review` |
| 9 | selesaikan | `POST /api/outbound/tasks/{T}/resolve-escalation?resolution_notes=ok` (± `&adjusted_qty={q}`) | query | `wms.approve` | `packing`; dengan qty: roll dilepas sebagian, harga SO dihitung ulang |
| 10 | buka ulang | `POST /api/outbound/tasks/{T}/reopen-escalation` | — | `wms.approve` | 409 kecuali `escalation.status=resolving` (keadaan proses mati — tak bisa dibuat lewat API normal) |
| 11 | gerbang bayar | `GET /api/sales-orders/{SO}/dispatch-payment-gate`; bila diblok `POST .../dispatch-payment-release` | `_GateReason {"reason":"uji audit B2b"}` (`sales_orders_extra.py:908-909`) | `order.view`/`wms.view`; `order.release_unpaid` | `blocked` |
| 12 | cek muat | `POST /api/outbound/so/{SO}/loading-check/start?warehouse_id={WH}` → (bila simulasi hidup) `POST /api/outbound/so/{SO}/loading-check/simulate-tags {"warehouse_id":WH}` → `POST /api/outbound/loading-check/{S}/scan {"epcs":[...],"source":"device"}` → (roll tanpa tag) `POST .../{S}/scan-label {"code":"RL-…","reason":"label tanpa tag"}` → `POST .../{S}/complete`; atau `POST /api/outbound/so/{SO}/loading-check/override {"reason":"uji audit B2b","warehouse_id":WH}` | body dict bebas (bukan Pydantic) `outbound_picking.py:554-591` | `wms.update`; `wms.untagged_override`; `wms.approve` | `GET /api/outbound/so/{SO}/loading-check?warehouse_id=WH` → `last_result.result` |
| 13 | kirim | `POST /api/outbound/tasks/{T}/dispatch?ship_qty={q}` atau `POST /api/outbound/so/{SO}/dispatch-batch?warehouse_id={WH}` | query | `wms.update` | tugas `dispatched/partially_shipped`; roll `in_transit_sales`; SJ `SJ-…` `status=dispatched`, `gl_status`; SO `shipped/partially_shipped` |
| 14 | buat pengiriman | `POST /api/logistics/deliveries` | `DeliveryCreateIn` (`schemas_logistics.py:7-21`): `{"shipment_ids":[SHP],"mode":"expedition","courier_name":"JNE","tracking_no":"RESI-B2B-1","shipping_cost":0}` | `logistics.manage` | `prepared`; SJ `logistics_status=prepared` |
| 15 | foto muat + muat | `POST /api/logistics/deliveries/{L}/photos` (multipart `kind=load`, `file=<jpg>`) → `POST /api/logistics/deliveries/{L}/transition` `TransitionIn {"to":"loaded"}` (`schemas_logistics.py:47-52`) | — | `logistics.update` | `loaded` |
| 16 | berangkat | `POST .../{L}/transition {"to":"in_transit"}` | — | `logistics.update` | `in_transit`; sesi gate SJ ditutup (gedung bergate) |
| 17 | GPS | `POST /api/logistics/deliveries/{L}/positions` | `PositionIn {"location":"Tol Cipularang KM 90","lat":-6.6,"lng":107.4,"note":""}` (`:40-44`) | `logistics.update` | `positions[]` |
| 18 | POD | `POST .../{L}/photos` (`kind=pod`) → `POST .../{L}/transition {"to":"delivered","receiver_name":"Budi","note":""}` | — | `logistics.update` | `delivered`; bila SO `shipped` & semua SJ ber-POD → SO `done`, roll `delivered` (`GET /api/sales-orders/{SO}/pod-progress`) |
| 19 | selesai | `POST .../{L}/transition {"to":"completed"}` | — | `logistics.update` | `completed` |
| 19' | ambil sendiri | SO `"fulfillment_method":"ambil","pickup_date":"<hari ini WIB>"`; delivery `"mode":"self_pickup"`; `POST /api/logistics/deliveries/{L}/pickup-handover` `PickupHandoverIn {"pickup_code":"<dari GET sbg admin>","picker_name":"Andi","picker_id_no":"","note":""}` (`:60-65`) | — | `logistics.update` | `delivered` + SO `done` |
| 19'' | manual tanpa logistik | `POST /api/sales-orders/{SO}/mark-delivered` | — | `order.deliver` | `done` |

### C-2. Cabang batal & ubah

| # | skenario | urutan | yang diperiksa (maksud) |
|---|---|---|---|
| B-1 | batal sesudah alokasi (1a/1b) | 1 → `POST /api/sales-orders/{SO}/cancel` `SoCancelIn {"reason":"uji batal B2b"}` (`schemas.py:457-458`) | roll `available`, `reserved_ref=null`, `length_reservations` bersih, mutasi `release_reservation`; `earmarked_for` (ANOM-28) |
| B-2 | batal sesudah approve | 1–4 → cancel | roll `committed` → `available` |
| B-3 | batal sesudah ambil | 1–7 (pick sebagian) → cancel | tugas `cancelled`; roll `available` (ANOM-20: tak ada tugas kembalikan) |
| B-4 | batal sesudah kirim | 1–13 → cancel | harus 409 (`partially_shipped/shipped`) |
| B-5 | lepas reservasi | 1 → `POST /api/sales-orders/{SO}/release-reservation` | `draft`; `items[].reserved_qty` basi |
| B-6 | Ganti Roll | `POST /api/sales-orders/{SO}/items/{PID}/reallocate` `SoReallocateIn {"roll_lines":[{"roll_id":R2,"take_qty":0}]}` (`schemas.py:423-426`) | izin `inventory.pegging`; roll lama `available` **tanpa mutasi** |
| B-7 | lepas sebagian roll | `POST /api/sales-orders/{SO}/items/{PID}/release-rolls` `SoReleaseRollsIn {"roll_ids":[R],"reason":"uji lepas B2b"}` (`:429-433`) | backorder bertambah; `reservation_releases[]` |
| B-8 | override SO | `GET /api/sales-orders/{SO}/override-context` → `POST /api/sales-orders/{SO}/override` `SoOverrideIn {"header":{"notes":"uji"},"lines":[{"product_id":PID,"quantity":Q2}],"add_items":[],"note":"uji override B2b"}` (`schemas.py:436-454`) | izin `order.override`; amandemen `auto_applied` |
| B-9 | rencana pemenuhan dari stok | `POST /api/sales-admin/orders/{SO}/fulfillment-plan` `FulfillmentPlanIn {"lines":[{"product_id":PID,"stock_qty":Q,"stock_roll_ids":[],"interco":[],"reorder_qty":0,"wait_qty":0}],"note":"uji"}` (`routers/work_desks.py:38-55`) | izin `order.confirm`; backorder `fulfilled` |

### C-3. Probe anomali (urutan konkret, hasil yang dibuktikan)

| probe | anomali | urutan | bukti "anomali terbukti" |
|---|---|---|---|
| C-P1 | ANOM-01 | SO roll-mode 2 roll (A pendek, B panjang; `purchase_mode:"roll"`, `roll_lines` A&B utuh) → 2–5 → scan-pick A penuh → dispatch → tugas `partially_shipped` → escalate → `resolve-escalation?adjusted_qty={panjang A}` | `GET /api/inventory/rolls?product_id=…` : A berstatus `available` padahal ada di `shipments.rolls[]`; fragmen baru `available`; tugas `packing` dengan `shipped_qty=quantity` |
| C-P2 | ANOM-02 | (a) 1–5 → escalate → cancel SO → `resolve-escalation` (tanpa qty); (b) 1–5 → escalate → scan-pick penuh → dispatch → `resolve-escalation` | (a) tugas SO batal jadi `packing` (200, bukan 409); (b) dispatch lolos saat `escalation.status=pending_review`, lalu `dispatched → packing` |
| C-P3 | ANOM-03 | 1a (Q=100) → 2–4 (roll `committed`) → override `lines:[{product_id,quantity:120}]`; ulangi dengan `quantity:60` dan `remove:true` | 100 `committed` + ≥120 `reserved` ke SO; `allocations` hanya roll `reserved`; varian 60 → `backorders` penuh; `remove` → roll `committed` tertinggal |
| C-P4 | ANOM-04/05 | 1c (stok 60 dari 100, `allow_backorder`) → 2–5 → pick 60 → dispatch → logistik → POD → B-9 (stok 40 tersedia dari SO lain yang dibatalkan) | B-9 409 "sedang diproses"; SO tetap `partially_shipped`; roll SJ ber-POD tetap `in_transit_sales`; `pod-progress.complete=true` tetapi SO tidak `done` |
| C-P5 | ANOM-08 | 1a → B-5 (`draft`) → B-6 (roll R) → B-1 | R tetap `reserved_ref.id=SO` dengan SO `cancelled` |
| C-P6 | ANOM-10/16 | SO X memborong stok PID → SO Y `allow_backorder` (status `waiting_stock`) → 2–5 untuk Y (`confirmed`, 0 tugas) → batal X → B-9 untuk Y | Y punya alokasi + roll `committed`, `wms_tasks` untuk Y = 0; lalu dengan akun PT lain `POST /api/wms/tasks/outbound-from-order/{Y}` → 200 (ANOM-16) |
| C-P7 | ANOM-11/12 | 1a satu roll 50 → 5 → scan-pick roll sama `actual_qty=25` dua kali → dispatch | dispatch 409 permanen; tak ada endpoint koreksi. Varian: pick 30 → `dispatch?ship_qty=30` → roll anak `in_transit_sales` `rfid_tag_id=null` tanpa `cut` |
| C-P8 | ANOM-13 | SO 2 produk di 1 gudang `loading_check_policy=required` → pick produk 1 saja → loading-check start/scan semua EPC produk 1/complete → dispatch | `result=with_issues` (missing roll produk 2) → dispatch 400 |
| C-P9 | ANOM-15 | SO ber-PPN `confirmed` → terbitkan Faktur → batalkan Faktur (status `batal`) → `GET /api/sales-orders/{SO}/override-context` | `locked_reason` = "Dokumen sudah terbit (sudah terbit Faktur Pajak …)" |
| C-P10 | ANOM-17 | akun sales PT A → `POST /api/sales-orders` dengan `"entity_id":"<PT B>"` (dan varian pelanggan milik PT B tanpa `entity_id`) | SO lahir di PT B + roll PT B `reserved` (bukan 403) |
| C-P11 | ANOM-14/18/19/07 | dua permintaan **bersamaan**: (i) `transition {to:"delivered"}` & `{to:"failed"}`; (ii) `scan-pick` & `cancel`; (iii) `mark-delivered` & POD; (iv) `cancel` & `dispatch` | (i) dua entri timeline status; (ii) SO `cancelled` lalu tertimpa status turunan; (iii)/(iv) roll `delivered`/`available` dengan SO tidak sinkron + `saga_lock` tertinggal |
| C-P12 | ANOM-06 | (baca-saja) hitung SO `expired` yang punya `backorders[]` atau pernah `approved` (`audit_logs` `reservation_expired` + `order_approved`) | jumlah > 0 = pesanan backorder/approved gugur otomatis |

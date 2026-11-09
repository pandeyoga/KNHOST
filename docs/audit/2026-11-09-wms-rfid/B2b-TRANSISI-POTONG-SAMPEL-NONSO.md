# B2b — Statik B: POTONG · SAMPEL · KELUAR NON-SO (transfer, makloon, perbaikan, retur supplier)

> **Lampiran paket audit B2b** (potong, sampel, transfer, makloon, perbaikan, retur supplier) — tabel transisi status dari KODE (`berkas:baris`, CAS, efek, pembalikan,
> idempotensi, pagar) + kandidat anomali statik + resep uji. Disusun dengan pembacaan kode di HEAD `35506d7`
> (`integrasi-prep3`). **Hasil uji runtime** (yang terbukti / dibantah / belum dijalankan) ada di laporan utama
> [`B2b-ALUR-KELUAR-POTONG-RFID.md`](B2b-ALUR-KELUAR-POTONG-RFID.md) §3 & §8 — ID kandidat di sini (ANOM-, POT-, SMP-, TRF-,
> MKO-, REP-, PRT-, T-, G-, L-, P-, H-) dipetakan ke ID temuan resmi (FLW-OUT-, STM-OUT-, CUT-, RFID-) di sana.
> Sandi akun demo sengaja tidak ditulis (lihat `AGENTS.md`). Catatan "belum dijalankan" di bagian resep = status saat
> lampiran disusun, sebelum uji runtime B2b.

* **Jenis:** audit LOGIKA ALUR, BACA-SAJA dari kode. Worktree `agent-a300a69678b4a7b03`, HEAD `35506d7`, 2026-11-09.
  Tidak ada berkas repo diubah, tidak ada docker/uvicorn/skrip penulis DB dijalankan, tidak ada commit. Semua
  `berkas:baris` relatif ke `backend/` kecuali disebut lain. Belum ada hasil runtime — semua butir "perlu runtime"
  masih hipotesis sampai resep §C dijalankan.
* **Susunan berkas:** Bagian 1–3 (POTONG, SAMPEL, TRANSFER) disusun langsung. Bagian 4 (MAKLOON) dan Bagian 5–6
  (PERBAIKAN, RETUR SUPPLIER) disusun subagen dengan brief yang sama lalu disalin utuh di belakang (Lampiran 4 & 5-6);
  dua klaim teratasnya saya cek ulang di kode (MKO-03: `stock_bucket_service.py:115-127` memang tanpa filter status;
  PRT-02: `purchase_return_service.py:997-999` memang mencari `type:"return_out"`).
* **Indeks:** (a) tabel transisi → §1 POTONG, §2 SAMPEL, §3 TRANSFER, Lampiran 4 §(a), Lampiran 5-6 §(a1)/(a2).
  (b) kandidat anomali → §B (POT-, SMP-, TRF-), Lampiran 4 §(b) (MKO-), Lampiran 5-6 §(b) (REP-, PRT-).
  (c) resep uji → §C (R-POT, R-SMP, R-SORD, R-TRF), Lampiran 4 §(c) (MKO), Lampiran 5-6 §(c) (C1–C6).
* **Rujuk saja (paket lain, tidak diulang):** B3a SSOT-4, **SSOT-8** (reservasi potong tertinggal di roll yang di-hold /
  menunjuk SO terhapus), SCP-2 (`/transfers` & daftar WMS tanpa saring lokasi), DUP-4 ("panjang bebas" diulang), DUP-6;
  B3b LST-02 (Meja Cutting >500 tugas), INP-09 (waste tanpa batas atas), FRM-08 (nama pelaku transfer dari klien);
  B1 UI-10 (potong desktop per paket vs HP per baris).
* **Kolom:** *CAS* = filter tulisan memuat status/nilai asal (atau klaim `saga_lock` berprasyarat). "filter `{id}`" = tanpa
  CAS. *Batal?* = dibalik saat dokumen dibatalkan. *Idem?* = aman bila diulang. *Pagar* = PT (`entity_id`/
  `owner_entity_id`) dan lokasi (`location_scope.assert_warehouse` / gudang).

Jumlah transisi yang dipetakan: **POTONG 16 · SAMPEL 22 · TRANSFER 31 · MAKLOON 37 · PERBAIKAN 9 (5 dokumen + 4 roll) ·
RETUR SUPPLIER 19 (+`gl_status` 4 nilai, 5 jalur `saga_lock`) = 134.**

---

## 1. POTONG untuk SO (reservasi panjang → potong fisik → roll anak → verifikasi)

Model data: reservasi potong = elemen `inventory_rolls.length_reservations[]` di **roll induk** (`{id, ref:{type,id},
qty, status}`), dijumlah ke `length_reserved` (`roll_service.py:580-601`). Induk tetap `available`; panjang yang
dipesan masuk bucket status reservasinya (`rebuild_balance` `roll_service.py:297-304`, hanya bila induk `available` —
lihat SSOT-8). Roll anak baru lahir saat potong dikonfirmasi.

### Tabel P-A — reservasi potong & roll SO

| # | dari → ke | pemicu (endpoint + fungsi, berkas:baris) | penjaga / CAS | efek | Batal? | Idem? | Pagar |
|---|---|---|---|---|---|---|---|
| P1 | — → `length_reservations[].status=reserved` (induk tetap `available`, `length_reserved` naik) | `POST /api/sales-orders` → `allocate_and_reserve_rolls` `roll_service.py:1155-1278` (cabang potong `:1219-1230`) → `_reserve_length` `:580-597`; juga `reserve_specific_rolls` `:2292-2305` (beli per roll, Ganti Roll `routers/sales_orders_extra.py:621`, isi backorder `services/backorder_service.py:199`) | CAS: `id`+`status:available`+`active_movement:None`+`$expr` panjang bebas ≥ take (`:587-590`) | alokasi SO `rolls[]` ber-`pending_cut:true, reservation_id` (`:1225-1229`); movement `reservation` per gudang (`:1265-1271`; jalur roll pilihan: `record_reservation_movements` `:2409`); `rebuild_balance` (`:1272`) | ya — `release_order_rolls` `:1287-1305` | tidak (tiap panggilan = reservasi baru; Ganti Roll dilindungi saga SO `sales_orders_extra.py:615-616`) | PT: hanya roll `owner_entity_id` = PT penjual (`:903-906`); lokasi: hanya urutan prioritas site (`:937-949`), tanpa `location_scope` |
| P2 | `reserved` → `committed` (status elemen reservasi) | SO disetujui → `set_order_rolls_status(order,"committed")` `roll_service.py:1412-1438` (pemanggil `so_lifecycle_service.py:58`, `sales_orders_extra.py:442,500`, `so_release_service.py:139`, `backorder_service.py:116`) | **tanpa CAS** (filter `{id}` + `array_filters r.ref.id`, `:1426-1428`) | bucket `committed_qty`; rebuild | tidak ada balik `committed→reserved` kecuali lepas | ya ($set) | — |
| P3 | reservasi → `pending_cut_ops[]` (induk: `length_remaining −(aktual+waste)`, `length_initial −aktual`) | `POST /api/inventory/rolls/{roll_id}/reservations/{reservation_id}/cut` (`routers/inventory.py:563-586`, izin `wms.update`) → `confirm_cut` `roll_service.py:604-649` | CAS: `id`+`length_reservations.id`+`length_remaining ≥ used` (`:637-639`) — **tidak memuat status induk / `active_movement`**; `actual ≤ rsv.qty` (`:624-626`); `waste ≥ 0` tanpa batas atas (INP-09); `registration_freeze.assert_movable` (`:617-618`) | operasi durable `pending_cut_ops` (`:643`); reservasi ditarik + `length_reserved` dihitung ulang dalam SATU tulisan | — (release tidak membaca `pending_cut_ops`) | ya: ulang dgn reservation_id sama → lanjut dari `pending_cut_ops` (`:610-614`) | PT: router cek `owner_entity_id ∈ scope` (`inventory.py:568-570`); **lokasi tidak** (bandingkan `_roll_wh_guard` `inventory.py:99-109`) |
| P4 | `pending_cut_ops` → roll anak lahir (`status = rsv.status` → reserved/committed, `reserved_ref` = SO, `rfid_tag_id:None`, `cut.identity_verified:false`, `journey.stage:cut_pending_tag`) | `_finish_cut` `roll_service.py:652-686` → `insert_child_roll` `:105-148` (nomor `RL-xxxxx-n` `:74-102`, berat proporsional `:151-189`) | id anak deterministik `roll_cut_{rsv}` (`:654-655`); movement upsert id deterministik (`:672-679`) | movement `roll_cut` qty 0 + `cut_waste` **−waste tanpa jurnal GL** (`:672-677`); `relink_cut_allocation` (`:680-681` → `:704-729`, CAS per entri alokasi); `$pull pending_cut_ops` (`:682`); `rebuild_balance` (`:684`); audit `roll_cut_confirmed` (router `:574-575`) | anak → `available` saat SO batal (`:1306-1310`), tidak digabung ke induk; susut tidak dibalik | ya | sama P3 |
| P5 | anak `cut.identity_verified false → true` (RFID) | sesi verifikasi tag cetak `rfid_print_service.py:722` → `mark_cut_identity_verified` `roll_service.py:759-767` | CAS `identity_verified:false` + `rfid_tag_id` terisi | penanda verifikasi | — | ya (0 diubah) | via sesi |
| P6 | anak `false → true` (label, gudang tanpa RFID) | `POST /api/inventory/rolls/{roll_id}/verify-identity` (`inventory.py:597-607`, `wms.update`) → `verify_cut_identity_by_label` `:770-789` | CAS `identity_verified:false`; kode = `roll_no` (`:778-781`) | `journey.stage:label_verified`; audit `roll_identity_verified` | — | ulang → 409 | PT router; lokasi tidak |
| P7 | gerbang muat: anak belum terverifikasi / reservasi belum dipotong → **409** | `assert_cut_identity_ready` `roll_service.py:742-756` dari `loading_check_service.start` `:66-68` dan `ship_order_rolls` `:1453` | — | blokir muat & dispatch | — | — | per gudang muat |
| P8 | reservasi dilepas (SO batal/kedaluwarsa/turun qty/rollback) | `release_order_rolls` `:1281-1326`; `release_order_rolls_partial` `:1329-1409`; `_release_rolls_by_ref_id` `:2348-2372` | `release_order_rolls`: **tanpa CAS** (`{id}` `:1290-1295`, `:1306-1309`); partial: CAS per `length_reservations.id` (`:1361`), roll utuh/pecah tanpa CAS (`:1373-1384`) | movement `release_reservation` (release & partial); `_release_rolls_by_ref_id` **tanpa movement & tanpa ubah `allocations` SO**; rebuild | — | ya | — |
| P9 | anak `reserved/committed` → `available` | sama P8 (SO batal) | tanpa CAS | anak tetap ber-`cut`, tanpa tag → tetap di daftar "belum terverifikasi" (`:803-812`) | — | ya | — |
| P10 | induk habis: `available` (panjang 0) → **tetap `available`** | P3/P4 bila `aktual+waste = sisa` | — | tidak ada status habis, tidak `is_remnant`, tidak grade BS; tag RFID induk tetap aktif | — | — | — |

Jalur lanjut anak (`picked → packed → in_transit_sales → delivered`) = jalur SO umum (`ship_order_rolls` `:1441`,
`deliver_order_rolls` `:1519`), tidak diulang di sini.

### Tabel P-B — jalur potong lain yang menyentuh panjang roll

| # | dari → ke | pemicu | penjaga / CAS | efek | Batal? | Idem? | Pagar |
|---|---|---|---|---|---|---|---|
| P11 | roll (`available/quarantine/qc_hold/inspection`) `length_remaining −qty`; `mdq_cuts` — → `pending` → `posted` | potong uji MD Quality, `routers/inspections.py:512-522` → `mdq_cut_service.cut` `:28-107` | inspeksi `po_receipt/makloon_output` terbuka (`:37-39`); kunci `_id = inspeksi:baris` (`:43-51`, `:79-82`); CAS roll `id`+panjang+status (`:83-87`) — tanpa `length_reserved` | movement `mdq_cut` −qty; rebuild; **GL write-off Dr 5-9500/Cr 1-1300** (`:98-101`); `inspections.lines.$.mdq_cut` | tidak | ya (`posted` → replay `:45-46`) | via inspeksi |
| P12 | `mdq_cuts pending` → (dihapus) | gagal CAS / proses lama mati (`:47-51`, `:88-90`) | `{_id, status:pending}` | — | — | ya | — |
| P13 | roll cutloss `delivered` → `hold` (masuk gudang hasil scan) | `return_cutloss_split_service._intake` `:85-113` | CAS `status:delivered` (`:97-99`) | movement intake | — | ya | — |
| P14 | induk cutloss → potongan: baik `hold`, BS `available`, dibuang `hold→damaged (0)` | `execute` `:140-195` | klaim `cutloss_split_lock` + `length_remaining` (`:150-152`); potongan pertama ditulis di induk **tanpa CAS status** dan kunci dicabut di tulisan itu (`:160-163`) | anak `insert_child_roll`; GL buang (`:169-171`) & reklas BS (`:184-188`), source_id memuat id roll anak baru | tidak | **tidak** bila mati di tengah: penanda `split.status:done` baru ditulis di akhir (`:193-194`) | `assert_can_choose` peran |
| P15 | potongan baik `hold` → `delivered` + SJ `kind:cutloss_return` langsung `dispatched` | `create_return_sj` `:205-248` | CAS `status:hold` (`:222-223`) | movement `cutloss_return_customer`; GL HPP (`:236-238`); **tanpa cek muat/gate/logistik** | tidak | `shipment_no` sudah ada → 400 | — |
| P16 | (kode mati) potong langsung tanpa reservasi panjang | `_split_roll` `roll_service.py:850-895`; cabang non-SO `reserve_specific_rolls` `:2325-2339` | — | — | — | — | semua pemanggil `reserve_specific_rolls` ber-ref SO (`backorder_service.py:199`, `sales_order_helpers.py:181`, `sales_orders_extra.py:621`); `_split_roll` hanya dipanggil test |

Potong sampel (sample_cut) dan pengambilan bahan R&D ada di §2.

---

## 2. SAMPEL

Tiga alur berbeda: **(a)** baris sampel di Pesanan Sample (SOS-) dipenuhi tugas `wms_tasks` ber-`task_subtype:"sample_cut"`;
**(b)** dokumen Pesanan Sample itu sendiri = `sales_orders` ber-`order_type:"sample"` (bukan koleksi terpisah,
`routers/sample_orders.py:1-8`); **(c)** sample R&D (`md_samples`) mengambil bahan dari roll (konsumsi internal).
Baris sampel **tidak boleh** dicampur di SO biasa (`routers/sales_orders.py:190-193`, `SAMPLE_MIXED`).

### Tabel S-A — tugas `sample_cut` (`wms_tasks`) + baris SO + roll

| # | dari → ke | pemicu | penjaga / CAS | efek | Batal? | Idem? | Pagar |
|---|---|---|---|---|---|---|---|
| S1 | — → tugas `created` (atau `scheduled` bila ambil terjadwal) | `POST /api/sample-orders/{id}/confirm` (`sample_orders.py:222-240`) → `create_outbound_tasks_for_order` `fulfillment_status.py:75-145` → `create_sample_cut_tasks` `sample_sale_service.py:247-288` | hanya "skip bila order sudah punya tugas outbound" (`fulfillment_status.py:87-88`) | tugas tanpa roll/alokasi, qty satuan dasar, `suggested_roll_id`; gudang = `suggested_warehouse_id` atau `_fallback_warehouse` (`:238-245`: gudang roll available PT, kalau tidak ada **gudang pertama di DB**); doc_refs `picking_task→sales_order` (`:285-287`) | SO batal → `cancelled` (S6) | lihat SMP-05 | PT = `entity_id` SO |
| S2 | `scheduled` → `created` | `outbound_picking.py:20` (rilis otomatis jatuh tempo), `:106` (rilis manual) | filter status | — | — | ya | — |
| S3 | `created/picking` → `packing` (+`roll_id` anak, `picked_qty`, `allocation_id`, `child_roll_no`) | `POST /api/outbound/tasks/{task_id}/cut-sample` (`sample_sales.py:75-88`, izin `wms.scan`); `POST /api/outbound/so/{order_id}/cut-samples` (`:91-102` → `cut_order_samples` `sample_sale_service.py:489-529`); handheld `handheld_sync.cut` `:401-418` → `cut_sample_task` `sample_sale_service.py:399-486` | precheck status + `picked_qty==0` (`:406-409`); klaim saga `wms_tasks` berprasyarat status (`:428`); tulisan akhir `finish_set` filter `{id}` (`:470-479`) | roll induk & anak (S9/S10); movement `sample_cut` qty 0 (`:448-452`); rebuild (`:453`); harga baris dihitung ulang bila panjang ≠ diminta (`:455-458` → `:319-338`) + `payment_after_reprice` (`:459` → `:341-396`); `allocations` `$push` ber-`roll_ids` (`:460-463`); baris `sample_cut_status:cut` (`:464-469`); `recompute_so_status` (`:480-481`); audit `sample_cut` | tidak (lihat S6) | ulang → 409 "sudah dipotong"; handheld `once(client_request_id)` | PT: `assert_entity_access` tugas (`sample_sales.py:83`), roll milik PT SO (`_resolve_roll` `:312-313`); **gudang roll tidak harus = gudang tugas** (tugas dipindah ke gudang roll `:471`); kemampuan lokasi tidak dicek ulang; desktop tanpa `location_scope` (handheld: `ctx.assert_warehouse` `handheld_tasks.py:376`) |
| S4 | `packing` + `cutting_handoff.received_at` (antrean "ready") | `POST /api/cutting/tasks/{task_id}/receive` (`cutting.py:44-50`, izin `sample_order.cutting_receive`); `POST /api/cutting/orders/{order_id}/receive` (`:53-60` → `receive_order` `cutting_service.py:205-223`) → `receive` `:109-163` | CAS `cutting_handoff.received_at` belum ada (`:134-139`); **tidak cek `task.status`** (tunggal) / status roll | beda lokasi: roll `warehouse_id=dst, bin_id:""` **filter `{id}`** (`:143-144`); movement `cutting_handoff_out/in` (`:149-153`); rebuild 2 gudang; `allocations.$.warehouse_id` (`:156-157`); timeline SO | tidak | ya (`:114-115`, `:140-141`) | `task.entity_id ∈ scope` (dilewati bila scope kosong `:112`); tujuan harus usable untuk pemilik (`:127-130`); tanpa `location_scope`, tanpa `registration_freeze` |
| S5 | `packing → staging → dispatched` | jalur outbound umum (`routers/wms.py:268`, `shipment_service.dispatch_task` `:114-118`) | `dispatch_guard` `loading_check_service.py:280-299`: gerbang bayar (tahan bila `reapproval_required`, `dispatch_payment_gate.py:99`), `pending_handoffs` (`cutting_service.py:166-170`), loading check / roll tanpa tag (`:304-315`) | SJ, `in_transit_sales` | — | — | — |
| S6 | `* (≠dispatched/completed/cancelled)` → `cancelled` | `POST /api/sales-orders/{id}/cancel` (`sales_orders_extra.py:844-905`): `update_many` tugas (`:885-889`) | filter status; **tidak memeriksa `saga_lock` tugas** | `release_order_rolls` (`:872-873`) → anak sampel `available`; induk tidak dipulihkan; harga tidak dibalik | — | ya | PT SO |
| S7 | baris — → `sample_cut_status: requested` / `awaiting_internal` | `POST /api/sales-orders` → `annotate_sample_line` `sample_sale_service.py:185-209` (+ `request_internal_supply` `:213-235`, dipanggil `sales_orders.py:683-685`) | — | tanpa reservasi (`reserved_qty:0`), saran roll FIFO (tanpa memperhitungkan `length_reserved`, `:167-175`) | — | — | lokasi sesuai kemampuan jenis sampel (`:189-191`) |
| S8 | baris `requested/awaiting_internal` → `cut` | S3 (`:464-469`) | `$elemMatch product_id+is_sample` | `reserved_qty=take`, roll induk & anak dicatat | — | — | — |
| S9 | roll induk `available` → `available` (panjang −take; `is_remnant` bila 0<sisa<2) | S3: `find_one_and_update` (`:429-433`) lalu `update_one {id}` (`:438-440`) | CAS `id`+`available`+`active_movement:None`+`length_remaining ≥ take` — **tanpa `length_reserved`**; tulisan kedua **tanpa CAS** menimpa `length_remaining` | `is_remnant`; freeze `assert_movable` (`:420-421`) | tidak | — | sama S3 |
| S10 | — → anak `reserved` (ref SO, `is_sample_cut:true`, tanpa tag, **tanpa field `cut`**) | S3 `insert_child_roll` (`:442-447`) | — | tidak ikut `assert_cut_identity_ready`; dijaga `untagged_rolls`/loading check | SO batal → `available` | — | — |

### Tabel S-B — Pesanan Sample (SORD/SOS-, `sales_orders.order_type="sample"`)

| # | dari → ke | pemicu | penjaga / CAS | efek | Batal? | Idem? | Pagar |
|---|---|---|---|---|---|---|---|
| S11 | — → `waiting_approval` (berbayar) / `approved` (gratis); `sample_payment_status: awaiting_approval / not_required` | `POST /api/sales-orders` dengan `order_type:"sample"` (`sales_orders.py:181-193`, `:305`, `:559-571`, `:669-670`) | `sample_billing` wajib (`:186-188`) | `pending_approvals` `pembayaran_sampel` (`:566-571`); nomor `SOS-` | — | tidak | PT payload/pelanggan/aktif (`:196-197`) |
| S12 | `waiting_approval` → `approved` (+`sample_payment_status:approved`) | `POST /api/sample-orders/{id}/approve-payment` (`sample_orders.py:178-219`; izin `sample_order.approve_payment` + peran `SAMPLE_PAYMENT_APPROVERS` `:181`) | tulisan pembayaran **filter `{id}`** (`:210-215`) lalu `so_transition` CAS status (`:216-217`; `sales_order_helpers.py:242-246`) | `sample_payment_approved_amount`; audit | — | `approved` → kembalikan apa adanya (`:201-202`) | `assert_active_entity_access` (`:45`) |
| S13 | `sample_payment_status: approved` → `reapproval_required` (status SO tetap) | potong S3 → `payment_after_reprice` `sample_sale_service.py:341-396` | **tanpa CAS** (`:379-384`); ≤ toleransi → hanya `sample_payment_approved_amount` disesuaikan (`:366-373`) | `pending_approvals` +1, notifikasi finance & sample_admin (`:385-394`); kiriman ditahan (S5) | — | tidak | — |
| S14 | `reapproval_required` → `approved` | approve-payment cabang ulang (`sample_orders.py:186-200`) | CAS `sample_payment_status` (`:193`); `pending_approvals` ditulis ulang utuh dari snapshot | — | — | ya | sama S12 |
| S15 | `approved` → `confirmed` (+ tugas S1) | `POST /api/sample-orders/{id}/confirm` (`:222-240`; `sample_order.confirm`) | berbayar wajib `sample_payment_status:approved` (`:229-231`); `so_transition` CAS (`:232-233`); **tugas dibuat SESUDAH transisi** (`:234`) | `create_outbound_tasks_for_order`, `recompute_so_status` (`:235`), audit | — | `confirmed` → return tanpa membuat tugas (`:227-228`) | sama |
| S16 | `confirmed` → `partially_picked` / `picked` → (`partially_shipped/shipped/delivered/done`) | `recompute_so_status` (`fulfillment_status.py:~40-73`) sesudah S3; selanjutnya mesin SO umum | `update_one {id}` | `fulfillment` | — | ya | — |
| S17 | `waiting_approval/approved` → `cancelled` | `POST /api/sample-orders/{id}/cancel` (`sample_orders.py:243-254`; `sample_order.cancel`; sales hanya miliknya `:247-248`) | `so_transition` CAS (`:251-252`) | tidak ada roll yang perlu dilepas (benar: sampel tanpa reservasi); `dead_order_patch` | — | — | sama |
| S18 | `confirmed/partially_picked/picked` → `cancelled` | `POST /api/sales-orders/{id}/cancel` (`sales_orders_extra.py:844-905`; `order.cancel`; alasan ≥5) | klaim saga `sales_orders` (`:869-870`) — **tidak saling-kunci dengan klaim `wms_tasks` potong sampel** | release roll, tugas `cancelled`, jurnal balik best-effort | — | — | `assert_entity_access` |
| S19 | `waiting_approval/approved` → `expired` | job `expire_old_reservations` `inventory_service.py:26-56` | filter status saat baca; **tulisan `{id}` tanpa CAS** (`:49-52`) | `allocations:[]`, audit `reservation_expired` | — | — | — |

### Tabel S-C — sample R&D (`md_samples`) mengambil bahan dari gudang

| # | dari → ke | pemicu | penjaga / CAS | efek | Batal? | Idem? | Pagar |
|---|---|---|---|---|---|---|---|
| S20 | roll `available` → `available` (panjang −qty) / `consumed` (sisa ≤ EPS) | `POST /api/rnd/samples/{id}/issue-material` (`routers/rnd.py:801-814`, izin `rnd.submit`, `_sample_guard`) → `issue_material` `rnd_sample_service.py:1430-1547` | sample `status ∈ OPEN_STATUSES` (`:1440`, dibaca); CAS roll `status`+`length_remaining` persis (`:1469-1475`) — **tanpa `length_reserved` / `active_movement` / registration_freeze** | movement `sample_issue` −qty (`:1477-1487`); rebuild; **GL Dr 6-7000 / Cr 1-1300** (`:1493-1503`); `material_issues` + timeline (`:1531-1537`) | **tidak** | tidak (tiap panggilan mengambil lagi) | PT roll = PT sample (`:1453-1454`); tanpa `location_scope`; tidak lewat SJ/gate |
| S21 | (kompensasi) `consumed` → status asal, panjang +qty | jurnal gagal (`:1504-1519`) | `$cond` status consumed; `$add` panjang; idempoten per movement (delete `:1508`) | movement dihapus | — | ya | — |
| S22 | `md_samples.*` → `cancelled` | `cancel_sample` `rnd_sample_service.py:759-771` | **filter `{id}`** (`:766`), tolak `decided`/`pending_pic` | bahan & jurnal S20 **tidak dikembalikan** | — | ya | — |

### Perbandingan SO vs Sampel (tugas gudang)

| Aspek | Potong untuk SO | Potong sampel |
|---|---|---|
| Koleksi tugas | `wms_tasks` (`flow_type:outbound`, tanpa subtipe) per alokasi | `wms_tasks` sama, dibedakan `task_subtype:"sample_cut"` (+ `order_type`, `sample_billing` di tugas, `sample_sale_service.py:270-271`) |
| Kapan potong | reservasi panjang saat SO dibuat; potong fisik dikonfirmasi terpisah (`/inventory/.../cut`) | tanpa reservasi; roll dipilih & dipotong saat tugas dikerjakan |
| Yang melihat | Antrean Potong `GET /api/inventory/pending-cuts` (`wms.view`); tugas di Meja Gudang (`role_desk_service.py:120-124`) | Meja Cutting `GET /api/cutting/desk` (`sample_order.view`, `cutting.py:36-41`); handheld menu potong & "Keluar · Sampel" (`handheld_tasks.py:116-117,170-178`); dikecualikan dari antrean `tugas_wms` (`role_desk_service.py:124`) |
| Susut | `waste` (movement `cut_waste`, tanpa GL) | tidak ada input susut |
| Sisa induk | tidak ditandai | `is_remnant` bila < 2 (`:440`) |
| Panjang bebas | dihormati (`$expr` `:587-590`) | **diabaikan** (`:429-433`) |
| Identitas anak | `cut.identity_verified` wajib (tag + sesi / label) | tidak ada `cut`; hanya syarat tag/loading check umum |
| Serah-terima | tidak ada | wajib "diterima Admin Cutting" sebelum kirim (`loading_check_service.py:290-295`) |
| Muat/SJ/gate | loading check + SJ + gate OUT (shipment) | sama (SJ, loading check `outbound_sample`, gerbang bayar) + gerbang handoff |
| Harga | harga baris tetap | dihitung ulang dari panjang aktual + toleransi bayar |

---

## 3. TRANSFER keluar antar gedung/site & antar-PT (`warehouse_transfers`)

### Tabel T-A — header transfer INTRA-PT (`transfer_kind:"intra_entity"`)

| # | dari → ke | pemicu | penjaga / CAS | efek | Batal? | Idem? | Pagar |
|---|---|---|---|---|---|---|---|
| T1 | — → `waiting_approval` | `POST /api/transfers` (`routers/transfers.py:151-275`, `transfer.create`) | validasi gudang & placement rules tujuan per roll (`:236-240`) | reservasi roll (T12–T15); insert (`:265`); SO `linked_transfer_ids` (`:266-267`); audit | kompensasi `release_wh_transfer_rolls` bila gagal (`:268-270`) | tidak | PT: kedua gudang `whscope.assert_usable` (`:182-191`), owner item `resolve_stock_owner(allowed)` (`:224-226`); lokasi: tidak (SCP-2); `requested_by` dari klien (FRM-08) |
| T2 | `waiting_approval` → `approved` | `POST /api/transfers/{id}/approve` (`:515-622`, `transfer.approve`, sisi asal) | klaim saga berprasyarat (`:545-546`) + `finish_set` (`:608-617`) | tidak ada efek roll | — | 400 bila status lain | sisi asal |
| T3 | `waiting_approval` → `rejected` | `POST /api/transfers/{id}/reject` (`:625-663`) | klaim (`:638-639`) | `release_wh_transfer_rolls` (`:646`) | — | 400 | sisi asal |
| T4 | `approved` → `picking` | `POST /api/transfers/{id}/status {status:"picking"}` (`:666-743`) | `STATUS_TRANSITIONS` (`:26-31`); klaim berprasyarat status (`:714-715`) | label saja (tanpa tugas gudang) | — | 400 | sisi asal |
| T5 | `picking` → `staging` | sama | sama | label | — | — | — |
| T6 | `staging` → `dispatched` | sama → `dispatch_wh_transfer_rolls` (`:720-722` → `roll_service.py:1973-1999`) | klaim; `registration_freeze.assert_transfer_movable(out)` (`:711`) | roll T16; movement `transfer_out`; **tanpa SJ / loading check**; gate OUT memvalidasi sesudahnya (`gate_evaluator.py:150-166`, dokumen aktif = `dispatched/partially_received`) | T11 | — | sisi asal |
| T7 | `dispatched` → `partially_received` | `POST /api/transfers/{id}/receive` (`:458-467`, `transfer.update`, sisi tujuan) atau gate IN (`gate_txn_service._transfer_in` `:239-256`, aktor gate) → `transfer_receipt_service.receive` `:256-336` → `_refresh_status` `:237-253` | status dibaca sekali (`:259-260`); **tidak memeriksa `saga_lock`**; per roll CAS (T17–T19); `_refresh_status` CAS status (`:246`) | `receipt_events` (`:331-333`) | — | ya ("already") | sisi tujuan; freeze `in` (`:265-266`) |
| T8 | `dispatched/partially_received` → `completed` (`completion_basis:actual_receipt`) | `_refresh_status` bila **tidak ada roll `in_transit_transfer` tersisa** (`:243-249`) — dari receive atau resolve | CAS status | `safe_close("wh_transfer", out+in)` (`:250-252`) | — | ya | — |
| T9 | `dispatched` → `completed` (jalur `/status`) | `POST /status {status:"completed"}` (`:703-709`) hanya bila 0 roll di jalan | klaim | **tanpa `safe_close` gate** | — | — | sisi tujuan |
| T10 | `dispatched/partially_received` → `completed` lewat pengembalian | `POST /api/transfers/{id}/exceptions/{exc_id}/resolve {action:"return_to_source"}` (`:480-488` → `trs.resolve` `:365-398`) → `_refresh_status` | supervisor (`:366`) | roll T21; bila semua dikembalikan → **`completed`** walau 0 diterima | — | — | `_guard_transfer` sisi "any" (`:484`) |
| T11 | `waiting_approval/approved/picking/staging/dispatched` → `cancelled` | `DELETE /api/transfers/{id}?reason=` (`:746-797`, `transfer.cancel`, sisi asal) | precheck `partially_received` → 400 (`:766-769`); klaim berprasyarat `$nin [completed,rejected,cancelled]` (`:773-774`, **tidak mengecualikan `partially_received`**) | `release_wh_transfer_rolls` (`:780` → `roll_service.py:2043-2076`): roll di jalan **langsung `available` di gudang asal** + movement `transfer_cancelled`; **tanpa `safe_close` gate**; `linked_transfer_ids` SO tidak dicabut | — | 400 bila terminal | sisi asal |

### Tabel T-B — roll pada transfer intra

| # | dari → ke | pemicu | penjaga / CAS | efek | Batal? | Idem? | Pagar |
|---|---|---|---|---|---|---|---|
| T12 | `available` → `reserved` (`reserved_ref:{type:wh_transfer}`), roll pilihan | `reserve_rolls_for_wh_transfer` cabang `roll_ids` `roll_service.py:1865-1889` | CAS lengkap: status, `length_reserved`, `active_movement`, owner, gudang (`:1879-1881`); gagal → lepas hanya milik operasi ini (`:1883-1887`) | rebuild | T22 | — | owner = PT transfer |
| T13 | `available` → `reserved`, FEFO roll utuh | cabang FEFO `:1890-1915` | CAS (`:1912-1915`) | — | T22 | — | — |
| T14 | FEFO pecah: induk `available` panjang −sisa; anak `reserved` | `:1916-1925` + `_split_roll_for_ref` `:1538-1552` | **induk `update_one {id}` + `$set` dari snapshot — tanpa CAS** (`:1923-1925`) | anak `insert_child_roll` | anak → `available` (tidak digabung) | — | — |
| T15 | roll SO `reserved/committed` → + `transfer_ref:{type:wh_transfer,id,so_id}` (komitmen tetap) | `attach_committed_rolls` `transfer_receipt_service.py:96-128` | SO ∈ `SO_TRANSFERABLE` (`:100-103`); CAS `held_cas`+`transfer_ref`+`active_movement` (`:118-120`) | — | `release_wh_transfer_rolls` hanya `reserved/in_transit` (`roll_service.py:1825`) → roll `committed` **tetap ber-`transfer_ref`** | — | owner = PT SO (`validate_so_link` `:82-93`) |
| T16 | `reserved/committed` → `in_transit_transfer` (+`transfer_prior_status`) | T6 `dispatch_wh_transfer_rolls` `roll_service.py:1973-1999` | `held_cas` (`:1981-1983`) | movement `transfer_out` −qty; rebuild (bucket `in_transit_transfer_qty` di gudang ASAL) | T20 | ya (CAS) | — |
| T17 | `in_transit_transfer` → `available` @tujuan | T7 `_land` `transfer_receipt_service.py:204-234` | `held_cas` (`:213`) | `warehouse_id`, `bin_id:None`, `last_transfer`; tag RFID pindah gudang (`:222-223`); movement `transfer_in`; rebuild asal+tujuan; placement bin opsional | — | ya | — |
| T18 | `in_transit_transfer` → `transfer_prior_status` (`reserved/committed`) @tujuan, `reserved_ref` SO tetap | `_land` bila SO masih "terbuka" (`so_still_open`, `roll_service.py:1944,1968-1970`) | sama | `_rehome_allocation` (`:232-233` → `:131-174`): `allocations` ditulis ulang utuh **tanpa CAS** (`:153-154`); tugas outbound `created` dipindah/dikurangi (`:157-174`) | — | ya | — |
| T19 | `in_transit_transfer` → `damaged` (alasan wajib) / `hold` (pelanggaran aturan + pengecualian supervisor) | `_land` status_kind (`:207-209`) | sama | exception `damaged`/`rule_violation` (`:298-321`); `reserved_ref` SO **dipertahankan** pada `damaged` tanpa rehome | — | ya | supervisor untuk pengecualian (`:269-271`) |
| T20 | `in_transit_transfer` → `available` / `reserved` @asal | T11 `release_wh_transfer_rolls` `roll_service.py:2043-2076` | `held_cas` (`:2054-2058`) | movement `transfer_cancelled` +qty (`:2062-2070`); `reserved` walau prior `committed`; `transfer_prior_status` **tidak dihapus** | — | ya | — |
| T21 | `in_transit_transfer` → `reserved` / `available` @asal | T10 `trs.resolve` `:370-389` | `held_cas` (`:377`) | `returned_from_transfer`; movement `transfer_cancelled`; sama seperti T20 (prior & field tidak dipulihkan) | — | ya | supervisor |
| T22 | `reserved` (ref wh_transfer) → `available` | T3/T11 | `held_cas` | rebuild | — | ya | — |

`receive_wh_transfer_rolls` `roll_service.py:2002-2040` (terima tanpa CAS, tanpa `last_transfer.code`) = **kode mati**
(tidak ada pemanggil).

### Tabel T-C — exception transfer

| # | dari → ke | pemicu | penjaga | efek |
|---|---|---|---|---|
| T23 | — → `open` | `POST /api/transfers/{id}/exceptions` (`missing/wrong_roll/other`, `:470-477` → `trs.report` `:347-362`); otomatis dari receive (`wrong_roll` `:281-286`, `rule_violation` `:300-304`, `damaged` `:309-312`) | transfer `dispatched/partially_received` (`:350-351`); `missing` hanya roll masih di jalan (`:354-358`) | `$push exceptions` (`:182`) |
| T24 | `open` → `resolved` (`return_to_source` / `close_note` / `received_hold`) | resolve (`:365-398`); otomatis saat terima dengan pengecualian (`:315-321`) | supervisor; **`close_note` ditolak untuk `missing`/`rule_violation`** (`:391-396`) | positional `exceptions.$` (`:339-344`) |

### Tabel T-D — transfer ANTAR-PT (`transfer_kind:"inter_entity"`, ganti pemilik di tempat)

| # | dari → ke | pemicu | penjaga / CAS | efek | Batal? | Idem? | Pagar |
|---|---|---|---|---|---|---|---|
| T25 | — → `waiting_approval` | `POST /api/transfers/inter-company` (`:303-429`, izin `order.create`) | pemohon cukup berwenang atas **salah satu** sisi (`:316-320`) | `reserve_rolls_for_transfer` (`:344-346` → `roll_service.py:1555-1662`) roll `available→reserved` (`ref type:transfer`) FEFO lintas gudang PT sumber; `source_warehouse_id = dest_warehouse_id` = gudang roll pertama (`:364`, `:401-402`); insert (`:419`) | kompensasi (`:421`) | tidak | PT sumber dipakai; tanpa kedaluwarsa reservasi |
| T26 | — → `waiting_approval` (tugas gudang dari transaksi antar-PT / retur antar-PT) | `interco_service.py:1732`, `interco_return_service.py:651` | — | sama T25 (`interco_service.py:1676`, `interco_return_service.py:599`) | — | — | — |
| T27 | `waiting_approval` → `completed` | approve (`:545-606`) → `execute_ownership_transfer` `roll_service.py:1665-1762` lalu jurnal (jembatan interco `:559,578` atau `post_intercompany_transfer` `:591-593`) lalu `finish_set` (`:594-601`) | klaim saga; roll `update_one {id}` **tanpa CAS** (`:1733`) | roll T30; lot dipindah rumah (`:1765-1798`); movement `ownership_transfer_out/in`; rebuild 2 segmen; jurnal at-cost / dilewati bila interco | tidak (balik lewat retur antar-PT) | — | sisi asal; interco_violations (`:528-544`) |
| T28 | `waiting_approval` → `rejected` / `cancelled` | reject (`:642-643`) / DELETE (`:777-778`) | klaim | `release_transfer_rolls` `roll_service.py:1801-1819` (**tanpa CAS** `:1810`) | — | — | sisi asal |
| T29 | `waiting_approval` → `cancelled` (transaksi antar-PT batal) | `interco_service.py:592-595` | filter `pair_id+status:waiting_approval` | release roll | — | — | — |
| T30 | roll `reserved` (ref transfer) → `available` milik PT tujuan | T27 | — | `acquired`, `acquired_history`, tag RFID ganti owner | — | — | — |
| T31 | — → `executing` → `completed` / `cancelled` (pindah kepemilikan roll retur) | `return_service.transfer_return_roll_ownership` `:1442-1472` | — | ownership + jurnal | rollback bila gagal sebelum pindah (`:1446-1453`) | lanjut (`:1458-1460`) | — |

### K-GDG-09 ("stok transit boleh dialokasikan/dijual seperti sekarang") terhadap transfer

* Alokator SO hanya mengambil roll `status:"available"` (`_available_rolls_for_order` `roll_service.py:903-906`);
  roll pilihan juga wajib `available` (`reserve_specific_rolls` `:2288-2289`). Roll `in_transit_transfer` milik transfer
  biasa **tidak bisa dialokasikan**. Daftar kandidat "Ganti Roll" menampilkan roll transit (`sales_p04_service.py:289`)
  tetapi reservasinya akan 409.
* ATP tujuan tidak menghitung transit transfer (`rebuild_balance` `:309-316`: `incoming = on_order + in_transit_inbound`);
  selama di jalan roll tetap tercatat di segmen gudang ASAL (`warehouse_id` baru diganti saat `_land`).
* Implementasi K-GDG-09 yang ada hanya untuk **draf putaway** (`putaway_draft_service.py:8`: draf tidak mengklaim roll).
* Satu-satunya "roll transit yang teralokasi" = roll yang **sudah** berkomitmen SO sebelum dikirim (T15). Saat tiba:
  `_land` memulihkan status prior (`:210-211`), mempertahankan `reserved_ref`, memindah alokasi & tugas outbound
  `created` ke gudang tujuan (`_rehome_allocation`). Celah: tugas yang bukan `created` (mis. `scheduled`) tidak pindah
  (TRF-06); SO yang `expired` dianggap masih terbuka (TRF-01).

---

## B. KANDIDAT ANOMALI (POTONG · SAMPEL · TRANSFER)

Label: **[pasti]** = terbukti dari kode; **[runtime]** = mekanisme terlihat di kode, kemunculan/dampak perlu dibuktikan;
**[keputusan]** = butuh konfirmasi pemilik (gate RFID = STOP & ASK per AGENTS.md).

### POT-01 — Potong sampel, potong MDQ, dan bahan R&D mengabaikan panjang yang sudah dipesan SO [pasti]
* **Bukti:** CAS potong sampel `sample_sale_service.py:429-433` (tanpa `length_reserved`); saran roll `suggest_roll`
  `:167-175`, `_resolve_roll` `:310-315`, alternatif paket `cut_order_samples` `:508-514`, kandidat handheld
  `handheld_tasks.py:383-386`; bahan R&D `rnd_sample_service.py:1459-1475`; MDQ `mdq_cut_service.py:83-84`. Bandingkan
  semua jalur reservasi yang memakai panjang bebas (`roll_service.py:587-590`, `:1576`, `:1869`, `:2328`).
* **Penalaran:** induk 10 yd dengan reservasi potong SO 8 yd tetap `available`; potong sampel 5 yd lolos CAS → sisa fisik
  5 < 8 yang dijanjikan. R&D bisa menghabiskan roll → `consumed` sementara `length_reservations` masih menempel.
* **Dampak:** `confirm_cut` SO 409 permanen (`roll_service.py:637-647`), SO tak bisa dimuat (`assert_cut_identity_ready`
  `:747-751`); `rebuild_balance` mengurangkan qty reservasi dari panjang yang tersisa (`:297-304`) → `available_qty`
  bisa negatif. Berbeda dari DUP-4 (jalur baca) — ini jalur TULIS. Varian SSOT-8 (reservasi tertinggal) lewat jalur baru.

### POT-02 — Potong sampel menulis ulang `length_remaining` tanpa CAS (regresi pola WM-01) [pasti; balapan = runtime]
* **Bukti:** `sample_sale_service.py:429-433` (`$inc`) lalu `:438-440` `update_one {id}` `$set length_remaining: rem`
  (nilai dari hasil tulisan pertama). Komentar WM-01 di `roll_service.py:854-856` menyebut pola ini pernah memakan
  potongan konkuren.
* **Dampak:** potong lain (SO `confirm_cut`, sampel lain, R&D, MDQ) yang jatuh di antara dua tulisan dibatalkan diam-diam
  → panjang induk kembali naik → stok fiktif (dan anak potong lain tetap ada).

### POT-03 — Pecah roll untuk transfer (intra & antar-PT) mengurangi induk tanpa CAS [pasti; balapan = runtime]
* **Bukti:** `reserve_rolls_for_wh_transfer` `roll_service.py:1923-1925` dan `reserve_rolls_for_transfer` `:1643-1649`:
  `update_one {id}` + `$set length_remaining = snapshot − take`, tanpa filter status/panjang/`length_reserved`/
  `active_movement`; anak tetap dibuat (`:1926`, `:1650`).
* **Dampak:** bila di antara baca (`:1894-1898`) dan tulis induk direservasi SO / dipotong / diklaim PA, tulisan ini
  menimpa → panjang hilang/bertambah, anak transfer lahir dari roll yang sudah dimiliki dokumen lain.

### POT-04 — Susut potong (`cut_waste`) tanpa jurnal GL [pasti]
* **Bukti:** `_finish_cut` `roll_service.py:675-677` menulis movement `cut_waste` −waste; tidak ada konsumen di
  `gl_service`/mana pun (grep `cut_waste` hanya baris ini). Bandingkan potong MDQ yang memposting write-off
  `mdq_cut_service.py:98-101` dan cutloss dibuang `return_cutloss_split_service.py:169-171`.
* **Dampak:** nilai persediaan subledger turun sebesar susut × HPP, GL 1-1300 tetap → drift INV-GL; susut juga tidak
  berbatas (INP-09).

### POT-05 — Rollback `reserve_specific_rolls` melepas SEMUA reservasi SO, bukan hanya yang baru [pasti; dampak = runtime]
* **Bukti:** `roll_service.py:2340-2342` → `_release_rolls_by_ref_id(ref.id)` `:2348-2372` melepas setiap
  `length_reservations.ref.id == SO` dan setiap roll `reserved_ref.id == SO` (`ORDER_HELD_STATUSES`). Pemanggil: Ganti
  Roll `sales_orders_extra.py:621` (komentar `:617-618`: "gagal di tengah tidak meninggalkan baris tanpa reservasi"),
  isi backorder `backorder_service.py:199` (take dihitung dari `length_remaining`, bukan panjang bebas `:194` → mudah
  400 "melebihi panjang bebas"), checkout `sales_order_helpers.py:181`.
* **Dampak:** satu roll yang "keburu diambil" saat Ganti Roll baris B → seluruh roll baris A, reservasi potong, bahkan roll
  anak hasil potong kembali `available`; `allocations` SO tidak diubah, tidak ada movement `release_reservation`; SO tetap
  status `confirmed` tanpa stok ter-reservasi.

### POT-06 — Potong yang mati di tengah (`pending_cut_ops`) tidak terlihat & tanpa penyapu [pasti; dampak = runtime]
* **Bukti:** `pending_cut_ops` hanya dibaca jalur lanjut `confirm_cut` `:610-614` (grep: tidak ada pembaca lain).
  Antrean potong `pending_cuts` `:814-839` membaca `length_reservations` — yang sudah ditarik pada tulisan `:637-647`.
* **Dampak:** induk sudah berkurang, anak belum lahir, reservasi hilang dari antrean → operator tidak bisa menemukan
  `reservation_id` untuk mengulang; `assert_cut_identity_ready` tidak melihatnya → loading check jalan dengan roll kurang.

### POT-07 — `confirm_cut` tidak memeriksa status induk / `active_movement` [pasti; jalur pemicu = runtime]
* **Bukti:** filter `roll_service.py:637-639`. Induk yang di-hold/karantina (SSOT-8: `hold_roll` tidak menolak roll
  ber-reservasi potong) atau diklaim perpindahan tetap bisa dipotong; anak lahir `reserved` dari roll terblokir.

### POT-08 — Pagar lokasi tidak ada di semua aksi potong & serah-terima [pasti]
* **Bukti:** `POST /inventory/rolls/{id}/reservations/{rid}/cut` (`inventory.py:563-570`), `cut-sample`
  (`sample_sales.py:75-84`), `cut-samples` (`:91-98`), Admin Cutting `receive` (`cutting_service.py:109-130`) — tidak
  memanggil `location_scope.assert_warehouse`; bandingkan putaway `_roll_wh_guard` `inventory.py:99-109` dan handheld
  `ctx.assert_warehouse` `handheld_tasks.py:376`.
* **Dampak:** petugas lokasi A memotong/memindah roll lokasi B lewat desktop/API (pelengkap SCP-2 di jalur tulis).

### POT-09 — Sisa potong tidak menjadi remnant/BS seperti KN_16; perlakuan SO ≠ sampel [pasti; maksud = keputusan]
* **Bukti:** KN_16 `docs/KN_16_END_TO_END_PROCESS_FLOWS.md:90` ("remnant (BS)") & `:146` ("Cut/Potong remnant→BS");
  `_finish_cut` tidak menyentuh `is_remnant`/grade (`roll_service.py:652-686`); potong sampel menandai `is_remnant`
  < 2 tanpa grade (`sample_sale_service.py:438-440`); induk habis tetap `available` 0 dengan tag aktif (P10).

### POT-10 — SO dibatalkan saat potong berjalan → roll anak ter-reservasi untuk SO mati [runtime]
* **Bukti:** `release_order_rolls` (`:1281-1326`) membaca `reserved_ref`/`length_reservations` sekali; `confirm_cut` yang
  sudah memindah reservasi ke `pending_cut_ops` (`:643`) melahirkan anak `reserved` sesudahnya (`:660-667`). Potong
  sampel: klaim di `wms_tasks` (`sample_sale_service.py:428`), batal SO klaim `sales_orders`
  (`sales_orders_extra.py:869-870`) → tidak saling mengunci; `finish_set` tugas filter `{id}` (`:470-479`) menimpa
  `cancelled` → `packing`; `update_many` batal tugas tidak memeriksa `saga_lock` (`sales_orders_extra.py:885-889`).
* **Dampak:** roll anak `reserved` ber-ref SO `cancelled` selamanya (tidak ada pelepas), tugas yang batal hidup lagi.

### SMP-01 — Serah-terima Admin Cutting menerima tugas batal & memindah roll tanpa CAS [pasti]
* **Bukti:** `cutting_service.receive` `:109-144` tidak memeriksa `task.status` (hanya `receive_order` memfilter
  `cancelled` `:210`), tidak memeriksa status/`reserved_ref`/`active_movement` roll, tulisan roll `{id}` (`:143-144`),
  tanpa `registration_freeze`.
* **Dampak:** SO sampel batal → roll anak sudah `available` → tetap bisa "diterima" & dipindah gudang dengan movement
  ber-ref SO batal; menimpa `warehouse_id` roll yang sedang di-PA/transfer.

### SMP-02 — Serah-terima lintas gedung = pindah roll tanpa dokumen gate [keputusan — STOP & ASK]
* **Bukti:** `cutting_service.py:142-157` memindah `warehouse_id` langsung; jenis dokumen gate hanya
  `shipment/wh_transfer/putaway/makloon_order/repair_order` (`rfid_v2_sources.py:16`). Roll `reserved` SO tanpa SJ aktif
  di gate OUT → merah (`gate_evaluator.py:86-97`, `:150-163`); di gate IN tujuan `NO_DOCUMENT`/`LOCAL_ROLL` (`:136-140`).
* **Pertanyaan pemilik:** apakah hasil potong boleh pindah gedung lewat Admin Cutting tanpa transfer? K-GDG-02 hanya
  menyebut SJ/transfer/makloon/perbaikan.

### SMP-03 — Potong sampel tidak terikat gudang tugas & kemampuan lokasi [pasti]
* **Bukti:** `_resolve_roll` `sample_sale_service.py:291-317` tidak membandingkan `roll.warehouse_id` dengan
  `task.warehouse_id`; tugas ditimpa ke gudang roll (`:471`); `assert_location_kind` hanya saat SO dibuat (`:189-191`).
* **Dampak:** sampel "catalogue/hanger" bisa dipotong di lokasi yang tidak berkemampuan; antrean lokasi tidak akurat.

### SMP-04 — Persetujuan bayar sampel menulis sebelum CAS; daftar persetujuan ditulis ulang utuh [pasti; balapan = runtime]
* **Bukti:** `sample_orders.py:210-215` (`{id}`) lalu `so_transition` (`:216`); cabang ulang `:188-197` menimpa
  `pending_approvals` dari snapshot; `payment_after_reprice` mendorong entri baru tanpa CAS
  (`sample_sale_service.py:379-384`).
* **Dampak:** approve × cancel/expire → SO `cancelled/expired` ber-`sample_payment_status:approved`; approve-ulang ×
  potong baris lain → entri `pembayaran_sampel` baru hilang (kiriman tak tertahan padahal tagihan berubah).

### SMP-05 — Konfirmasi sampel: transisi dulu, tugas belakangan; ulang tidak memperbaiki [runtime]
* **Bukti:** `sample_orders.py:232-235`; ulang `confirm` saat `confirmed` langsung return (`:227-228`);
  `create_outbound_tasks_for_order` skip bila ada tugas (`fulfillment_status.py:87-88`).
* **Dampak:** kegagalan antara `:232` dan `:234` → SO `confirmed` tanpa tugas `sample_cut`, tidak muncul di Meja Cutting.

### SMP-06 — `sample_cut_status:"awaiting_internal"` tidak pernah keluar kecuali ke `cut` [pasti]
* **Bukti:** penulis hanya `annotate_sample_line` `:203-209` dan potong `:466`; `request_internal_supply` menelan error
  (`:231-232`). Meja Cutting memakai field ini untuk antrean (`cutting_service.py:46`).
* **Dampak:** sesudah pembelian internal selesai (stok sudah milik PT) baris tetap di antrean "Menunggu pembelian
  internal"; bila pembelian internal gagal/batal tidak ada jalur kembali ke `requested`.

### SMP-07 — Gudang cadangan tugas sampel = gudang pertama di DB [pasti]
* **Bukti:** `_fallback_warehouse` `sample_sale_service.py:238-245` (`warehouses.find_one({})` tanpa filter PT/kemampuan).
* **Dampak:** tugas potong lahir di gudang yang tidak terkait PT/lokasi; antrean & handheld lokasi lain.

### SMP-08 — Bahan R&D keluar gudang tanpa pembalik, tanpa freeze, tanpa dokumen gate [pasti; gate = keputusan]
* **Bukti:** `cancel_sample` `rnd_sample_service.py:759-771` (`{id}`, tanpa mengembalikan `material_issues`); issue tanpa
  `registration_freeze` (grep 0 di berkas); tidak ada jenis dokumen gate untuk R&D (`rfid_v2_sources.py:16`) → bahan yang
  dibawa keluar gedung merah di gate (`gate_evaluator.py:145-153`).

### SMP-09 — Identitas roll anak sampel tidak dijaga seperti anak SO [perbedaan; pasti]
* **Bukti:** anak sampel tanpa `cut` (`sample_sale_service.py:442-447`) → tidak di "Roll anak belum terverifikasi"
  (`roll_service.py:803-812`) dan dilewati `assert_cut_identity_ready`; hanya `untagged_rolls`/loading check
  (`loading_check_service.py:223-233`, `:304-315`).

### TRF-01 — SO `expired` (dan `done`) dianggap masih terbuka → roll transit kembali ter-reservasi untuk SO mati [pasti]
* **Bukti:** `SO_CLOSED_STATUSES` `roll_service.py:1944` tanpa `expired`/`done` (bandingkan `SO_DEAD_STATUSES`
  `approval_backlog_service.py:38`); job kedaluwarsa memproses status yang juga `SO_TRANSFERABLE`
  (`inventory_service.py:29-31` vs `transfer_receipt_service.py:30`); `release_order_rolls` tidak menyentuh
  `in_transit_transfer` (`ORDER_HELD_STATUSES` `roll_service.py:232`); `_land` `keep=True` (`:207-214`) +
  `_rehome_allocation` menulis alokasi ke SO kedaluwarsa (`:153-154`). Sama untuk batal transfer (`:2051-2058`) dan
  `return_to_source` (`:374-380`).
* **Dampak:** roll terkunci `reserved` untuk SO mati tanpa pelepas otomatis (varian SSOT-8).

### TRF-02 — Transfer `completed` walau tidak ada roll yang diterima [pasti]
* **Bukti:** `_refresh_status` `transfer_receipt_service.py:243-249` → `completed` cukup bila 0 roll di jalan;
  `return_to_source` semua roll → `completed`, `completion_basis:"actual_receipt"`, `safe_close` gate (`:250-252`).
* **Dampak:** laporan transfer "Selesai" padahal semua barang kembali; sesi gate dinilai sebagai transfer selesai.

### TRF-03 — Roll hilang hanya bisa "dikembalikan ke asal" → stok hantu di gudang asal [pasti; keputusan DEC-13]
* **Bukti:** `close_note` ditolak untuk `missing` (`:391-396`); satu-satunya jalan selesai = `return_to_source`
  (`:370-389`) yang menjadikan roll `available/reserved` di asal; batal diblok saat `partially_received`
  (`transfers.py:766-769`).
* **Dampak:** pilihan operator = transfer menggantung `partially_received` selamanya, atau stok fiktif di asal.

### TRF-04 — Batal saat `dispatched`: roll di jalan langsung tersedia di asal; balapan dengan terima; gate tidak ditutup [pasti; balapan = runtime]
* **Bukti:** `transfers.py:762-790` mengizinkan `dispatched`; `release_wh_transfer_rolls` `roll_service.py:2043-2076`;
  `trs.receive` tidak mengklaim/memeriksa `saga_lock` (`:256-336`); klaim batal `$nin` terminal tidak mengecualikan
  `partially_received` (`transfers.py:774`); `safe_close` hanya di `_refresh_status` (`:250-252`).
* **Dampak:** stok tampil `available` di gudang asal saat fisiknya di truk; batal × terima → transfer `cancelled` dengan
  sebagian roll sudah mendarat di tujuan; sesi gate OUT/IN dokumen batal tetap terbuka.

### TRF-05 — Status SO `committed` tidak dipulihkan saat batal/kembali; penanda basi [pasti]
* **Bukti:** `release_wh_transfer_rolls` `:2054-2058` & `return_to_source` `:377-380` menulis `reserved` dan tidak
  menghapus `transfer_prior_status` (bandingkan `_land` `:210-215`); `INTRA_TRANSFER_HELD` `:1825` tanpa `committed` →
  batal sebelum kirim tidak mencabut `transfer_ref` roll `committed` (T15).
* **Dampak:** bucket `committed`→`reserved` pada SO yang sudah disetujui; field `transfer_prior_status`/`transfer_ref`
  basi memengaruhi `owned_by_transfer`/gate (`gate_evaluator.py:70-83`).

### TRF-06 — Pindah alokasi saat tiba hanya untuk tugas `created`; alokasi ditulis ulang tanpa CAS [pasti]
* **Bukti:** `_rehome_allocation` `transfer_receipt_service.py:157-159` (`status:"created"`); tanpa tugas sumber →
  tidak ada tugas tujuan; `allocations` `$set` utuh dari snapshot (`:153-154`).
* **Dampak:** Order Pengambilan terjadwal (`scheduled`, `fulfillment_status.py:93-104`) → alokasi pindah ke tujuan tanpa
  tugas, tugas asal menunggu roll yang sudah pergi; tulisan alokasi konkuren (relink potong `roll_service.py:704-729`,
  Ganti Roll) bisa hilang.

### TRF-07 — Roll SO tiba `damaged` mempertahankan `reserved_ref` tanpa pelepas [pasti]
* **Bukti:** `_land` `:209-214` (damaged + `reserved_ref` tetap); rehome hanya `SO_HELD` (`:232`); `release_order_rolls`
  hanya `ORDER_HELD_STATUSES` (`roll_service.py:232,1284-1286`).
* **Dampak:** roll rusak ber-ref SO selamanya; alokasi SO tetap menunjuk gudang asal.

### TRF-08 — SO batal sebelum transfer dikirim meninggalkan `transfer_ref` di roll `available` [pasti]
* **Bukti:** `release_order_rolls` `roll_service.py:1306-1310` tidak mencabut `transfer_ref`; dispatch melewati roll itu
  diam-diam (`owned_by_transfer` `:1947-1952`); item transfer tetap mencantumkannya (ringkasan "released").

### TRF-09 — K-GDG-09 tidak berlaku untuk stok transit transfer [keputusan]
* **Bukti:** lihat analisis §3 (allocator `available` saja `roll_service.py:903-906`; ATP tujuan tanpa transit `:309-316`;
  K-GDG-09 hanya di draf putaway `putaway_draft_service.py:8`).
* **Pertanyaan:** apakah "boleh dialokasikan/dijual" juga dimaksudkan untuk roll yang sedang di jalan antar gedung?

### TRF-10 — Antar-PT: jurnal sesudah kepemilikan pindah tanpa kompensasi [runtime]
* **Bukti:** `transfers.py:550` (roll & movement sudah pindah, `roll_service.py:1733` tanpa CAS) lalu jembatan/jurnal
  (`:559`, `:578`, `:591-593`) lalu `finish_set` (`:594-601`).
* **Dampak:** exception jurnal → `saga_lock` tertinggal, status `waiting_approval`, roll sudah milik PT tujuan; approve/
  cancel ulang 409 `SAGA_IN_PROGRESS` sampai admin melepas kunci.

### TRF-11 — Dokumen antar-PT menyebut satu gudang padahal roll lintas gudang; pemohon PT tujuan mengunci stok PT sumber [pasti; minor]
* **Bukti:** `transfers.py:364`, `:401-402` (`primary_wh`), FEFO lintas gudang (`roll_service.py:1574-1588`), pemohon cukup salah
  satu sisi (`transfers.py:316-320`), tanpa kedaluwarsa reservasi transfer.

### TRF-12 — Kode mati & status yatim [pasti; minor]
* `receive_wh_transfer_rolls` `roll_service.py:2002-2040` tanpa pemanggil (dan tanpa CAS); status roll
  `in_transit_intercompany` punya bucket (`:225`) tetapi tidak pernah ditulis (KN_16 §7 `:190`); `_split_roll` (P16).

---

## C. RESEP UJI RUNTIME (POTONG · SAMPEL · SORD · TRANSFER)

**R0 — persiapan.** Base `http://localhost:8001/api`. Login `POST /api/auth/login` body
`{"email":"admin@kainnusantara.id","password":"<sandi demo — AGENTS.md>"}` (`schemas.py:161-163`) → cookie `session_token` atau header
`Authorization: Bearer <token>` (`dependencies.py:27-32`) + `X-Entity-Id: <ENT>` (satu PT). Data acuan: `bash
scripts/dev_restore_demo.sh` (dari host, sebelum & sesudah uji). Cek DB baca-saja dengan `mongosh` ke DB `DB_NAME`
(dok: `test_database`; skrip B3a memakai `kn_test_trial` — `scripts/audit/b3a_mongo_ro.sh`). Peran: admin memegang semua
izin di bawah; peran gudang untuk uji pagar lokasi (akun seed sandi `<sandi demo — AGENTS.md>`). Satu skenario per waktu (AGENTS.md).

### R-POT — potong roll untuk SO (sisa, susut, POT-01/02/04/05/06/08)
1. Pilih produk **P** (base `yard`) dan satu roll **R** `available`, panjang ≥ 20, `length_reserved` 0, milik ENT di
   gudang **W**: `GET /api/inventory/rolls?product_id=P&status=available`.
2. Buat SO yang memicu reservasi panjang: `POST /api/sales-orders` (model `SalesOrderCreate` `schemas.py:525-551`,
   baris `SalesOrderItemIn` `:483-517`):
   `{"customer_id":"<C>","shipping_address_id":"<A>","entity_id":"<ENT>","items":[{"product_id":"P","quantity":7,
   "unit":"yard","purchase_mode":"roll","roll_lines":[{"roll_id":"R","take_qty":7}]}]}` (`RollLineIn` `:416-420`).
   Cek: `inventory_rolls R.length_reservations[0] {qty:7,status:"reserved",ref.id:SO}`, `length_reserved:7`;
   `sales_orders.allocations[].rolls[] {pending_cut:true,reservation_id}`; `inventory_balances` (P,W,ENT)
   `reserved_qty` +7.
3. Antrean: `GET /api/inventory/pending-cuts?order_id=<SO>` (`wms.view`) → `reservation_id`.
4. **POT-01:** sebelum memotong SO, buat Pesanan Sample (R-SMP langkah 1–3) untuk produk P dengan potong 5 yd dari roll R
   (`roll_id:"R"` di cut-sample). Harapan kode: lolos. Cek `R.length_remaining` (20−5=15 ≥ 7 masih aman); ulangi dengan
   roll 10 yd + reservasi 8 yd → sisa 5 < 8, lalu langkah 5 → 409 "panjang fisik tidak cukup"; `inventory_balances`
   `available_qty` < 0. Varian R&D: `POST /api/rnd/samples/{id}/issue-material` `{"roll_id":"R","qty":<sisa>,"note":"uji"}`
   (`schemas_rnd.py:229-232`) → `R.status:"consumed"` dengan `length_reservations` masih ada.
5. Potong: `POST /api/inventory/rolls/R/reservations/<rsv>/cut` body `CutConfirmPayload` (`inventory.py:549-552`)
   `{"actual_length":6.9,"waste":0.3,"note":"uji B2b"}` (`wms.update`). Cek: anak `id:"roll_cut_<rsv>"`,
   `status:"reserved"`, `rfid_tag_id:null`, `cut.identity_verified:false`, `roll_no:"<R.roll_no>-1"`; induk
   `length_remaining` −7,2, `length_initial` −6,9, `pending_cut_ops:[]`; movement `mov_cut_<rsv>` (qty 0) &
   `mov_cutw_<rsv>` (−0,3); **POT-04:** `journal_entries` dengan `source_id` memuat `<rsv>`/`cut_waste` = **tidak ada**;
   alokasi SO menunjuk anak (`cut_from_roll_id:R`). Ulang langkah 5 → 404 (idempoten).
6. Muat sebelum verifikasi: `POST /api/outbound/so/{order_id}/loading-check/start` (`routers/outbound_picking.py:543`) → 409
   "belum ber-tag/terverifikasi". Verifikasi label:
   `POST /api/inventory/rolls/<anak>/verify-identity` `{"scanned_code":"<anak.roll_no>"}` → `cut.identity_verified:true`.
7. **Sisa habis (P10/POT-09):** SO kedua dengan `take_qty` = sisa bebas R → potong `actual_length` = sisa → induk
   `length_remaining:0`, `status:"available"`, `is_remnant` tidak ada, `rfid_tag_id` tetap.
8. **POT-05:** SO dua baris (P1: roll X dipotong & sudah punya anak; P2: roll Y utuh). Ganti Roll baris P2:
   `POST /api/sales-orders/{order_id}/items/{P2}/reallocate` (`sales_orders_extra.py:558`, izin `inventory.pegging`) body
   `SoReallocateIn` (`schemas.py:423-426`) `{"roll_lines":[{"roll_id":"<Z1>","take_qty":0},{"roll_id":"<Z2>","take_qty":0}]}`
   dengan Z2 sudah direservasi SO lain di antara pemilihan & kirim (atau `take_qty` > panjang bebas Z2 → 400). Harapan kode: 409, lalu cek **semua** roll SO
   (termasuk anak X & reservasi panjang P1) `status:"available"`/`length_reservations` hilang; `allocations` SO tetap;
   tidak ada movement `release_reservation`.
9. **POT-06 (injeksi, hanya di lingkungan uji):** hentikan backend tepat sesudah tulisan `:637-647` (mis. breakpoint) →
   `GET pending-cuts` tidak menampilkan reservasi; `inventory_rolls R.pending_cut_ops[0]` ada; ulang langkah 5 dengan
   `reservation_id` yang dicatat → anak lahir.
10. **POT-08:** login peran gudang yang lokasinya hanya W2; ulang langkah 5 pada roll di W → harapan kode: 200 (seharusnya
    403 seperti `POST /api/inventory/putaway`).

### R-SMP — potong sampel: tugas `sample_cut` & paket per SO (SMP-01/03/06/07, POT-02, POT-10)
1. `POST /api/sales-orders` `{"customer_id":"<C>","shipping_address_id":"<A>","entity_id":"<ENT>","order_type":"sample",
   "sample_billing":"free","items":[{"product_id":"P","quantity":2,"unit":"yard","is_sample":true,
   "sample_kind":"standard","cut_warehouse_id":""}]}` → `status:"approved"`, `items[0].sample_cut_status:"requested"`,
   `suggested_roll_id`.
2. `POST /api/sample-orders/{id}/confirm` (izin `sample_order.confirm`) → `status:"confirmed"`, `tasks_created:1`;
   `wms_tasks {task_subtype:"sample_cut",status:"created",roll_id:""}`. Ulang → return tanpa tugas baru.
3. Potong per tugas: `POST /api/outbound/tasks/<task>/cut-sample` body `SampleCutIn` (`sample_sales.py:25-29`)
   `{"roll_id":"<R2>","epc":"","actual_length":2.2,"reason":"uji B2b roll bukan saran"}` (`wms.scan`). Cek: tugas
   `status:"packing"`, `picked_qty:2.2`, `saga_lock` tidak ada; induk −2,2 (+`is_remnant` bila sisa < 2); anak
   `reserved`, `is_sample_cut:true`, tanpa `cut`; `sales_orders.allocations[-1].roll_ids:[anak]`, baris
   `sample_cut_status:"cut"`, `quantity:2.2`, `grand_total` dihitung ulang (gratis = 0); movement `sample_cut`.
   **SMP-03:** pakai `roll_id` di gudang lain dari `task.warehouse_id` → harapan kode 200 dan `wms_tasks.warehouse_id`
   ikut berubah.
4. Paket per SO: SO sampel catalogue/multi-baris → `POST /api/outbound/so/{order_id}/cut-samples` body `OrderCutIn`
   (`:32-35`) `{"warehouse_id":"<W>","lines":[]}` → `{cut:[…],failed:[…]}`.
5. Serah-terima: `POST /api/cutting/tasks/<task>/receive` `{"to_warehouse_id":"<W3>"}` (izin
   `sample_order.cutting_receive`) → `cutting_handoff.transferred:true`; roll anak `warehouse_id:W3`, `bin_id:""`;
   movement `mov_cho_<task>`/`mov_chi_<task>`. Ulang → dokumen sama (idempoten).
6. **SMP-01:** SO sampel lain dipotong (langkah 3) lalu `POST /api/sales-orders/{id}/cancel` `{"reason":"uji B2b batal"}`
   (`SoCancelIn` `schemas.py:457-458`) → tugas `cancelled`, anak `available`; lalu `POST /api/cutting/tasks/<task>/receive`
   `{"to_warehouse_id":"<W3>"}` → harapan kode: 200, roll `available` pindah gudang + movement ber-ref SO batal.
7. **POT-02 / POT-10 (balapan):** kirim bersamaan (mis. `asyncio.gather`/2 terminal) `cut-sample` pada roll R dan
   `confirm_cut` reservasi SO di roll R; bandingkan `R.length_remaining` akhir dengan panjang awal − (potong sampel +
   aktual SO + waste). Varian: `cut-sample` × `POST /api/sales-orders/{id}/cancel` → cek tugas akhir (`packing` vs
   `cancelled`) dan anak `reserved_ref` SO batal.
8. **SMP-06/07:** buat SO sampel untuk produk yang hanya ada di PT lain → baris `awaiting_internal`, `internal_supply[]`;
   selesaikan pembelian internal → `GET /api/cutting/desk` masih di antrean `awaiting_internal`. Produk tanpa roll
   `available` sama sekali → `wms_tasks.warehouse_id` = gudang pertama koleksi `warehouses`.

### R-SORD — Pesanan Sample berbayar: approve-payment → confirm → cancel (SMP-04/05)
1. Buat SO sampel `"sample_billing":"paid"` (R-SMP-1) → `status:"waiting_approval"`, `sample_payment_status:
   "awaiting_approval"`, `pending_approvals[{type:"pembayaran_sampel",status:"pending"}]`.
2. `POST /api/sample-orders/{id}/confirm` → 409 `SAMPLE_PAYMENT_PENDING` (penjaga `sample_orders.py:229-231`; benar).
3. `POST /api/sample-orders/{id}/approve-payment` `{"note":"uji B2b bayar"}` dengan peran finance/sample_admin
   (izin `sample_order.approve_payment`; peran sales → 403 `:181-182`) → `status:"approved"`,
   `sample_payment_approved_amount = grand_total`. Ulang → dokumen sama.
4. `POST /api/sample-orders/{id}/cancel` `{"note":"uji B2b batal sebelum gudang"}` → `cancelled` (izin
   `sample_order.cancel`). Untuk SO kedua: confirm → `confirmed` → `cancel` sampel → 409 (harus lewat
   `POST /api/sales-orders/{id}/cancel`).
5. **Reapproval:** SO berbayar dikonfirmasi, potong dengan `actual_length` jauh dari diminta (selisih > toleransi
   `sales.sample_payment_tolerance_pct` bawaan 5 %) → `sample_payment_status:"reapproval_required"`, notifikasi
   `sample_payment_reapproval`; dispatch ditahan (`dispatch_payment_gate`); approve-payment ulang → `approved`.
6. **SMP-04 (balapan):** kirim bersamaan `approve-payment` dan `POST /api/sample-orders/{id}/cancel` pada SO
   `waiting_approval` → bila cancel menang: cek `status:"cancelled"` tetapi `sample_payment_status:"approved"` dan
   `pending_approvals[].status:"approved"`.
7. **SMP-05 (injeksi):** buat `create_outbound_tasks_for_order` gagal (hanya lingkungan uji, mis. hentikan backend sesudah
   `so_transition`) → `status:"confirmed"`, 0 tugas; ulang confirm → tetap 0 tugas.

### R-TRF-1 — transfer buat → kirim → terima sebagian → terima sisa → selesai (TRF-02/05/06/07)
1. Pilih 3 roll `available` (R1..R3) produk P di gudang **WA** (lokasi A) milik ENT, gudang tujuan **WB** usable untuk ENT.
   `POST /api/transfers` body `TransferCreate` (`schemas.py:639-646`, item `TransferItem` `:624-636`):
   `{"source_warehouse_id":"WA","dest_warehouse_id":"WB","owner_entity_id":"ENT","notes":"AUDIT-B2B-TRF",
   "items":[{"product_id":"P","qty":0,"roll_ids":["R1","R2","R3"]}]}` (izin `transfer.create`) → `waiting_approval`;
   roll `reserved`, `reserved_ref:{type:"wh_transfer",id}`.
2. `POST /api/transfers/{id}/approve` `{"approved_by":"uji"}` (`TransferApprove` `:678-680`; `transfer.approve`).
3. `POST /api/transfers/{id}/status` `{"status":"picking"}`, lalu `"staging"`, lalu `"dispatched"` (`TransferStatusUpdate`
   `:688-690`) → roll `in_transit_transfer`, `transfer_prior_status:"reserved"`, `warehouse_id` masih WA; movement
   `transfer_out` ×3; `inventory_balances` WA `in_transit_transfer_qty` naik; WB tidak berubah (TRF-09).
4. Terima sebagian (sisi tujuan): `POST /api/transfers/{id}/receive` body `TransferReceiveIn` (`:657-662`, baris
   `TransferReceiveLine` `:649-654`) `{"lines":[{"roll_id":"R1","outcome":"received"},{"roll_id":"R2",
   "outcome":"damaged","note":"sobek uji B2b"}],"note":"uji"}` → `transfer_status:"partially_received"`; R1 `available`@WB,
   R2 `damaged`@WB, exception `damaged`; movement `transfer_in` ×2. Ulang baris R1 → `result:"already"`.
5. Terima sisa: `{"lines":[{"code":"<R3.roll_no>","outcome":"received"}]}` → `completed`, `completion_basis:
   "actual_receipt"`; `rfid_gate_sessions`/sesi dokumen gate `wh_transfer` ditutup (safe_close).
6. **Varian SO (TRF-06/07, T15/T18):** SO pengambilan terjadwal (`"fulfillment_method":"ambil","pickup_date":"<besok>"`)
   dengan roll di WA, disetujui (`committed`); `POST /api/transfers` dengan `"sales_order_id":"<SO>"` dan `roll_ids` roll
   SO → kirim → terima di WB → cek `sales_orders.allocations` pindah ke WB, `wms_tasks` asal masih `scheduled` qty penuh
   di WA dan tidak ada tugas di WB. Satu roll SO diterima `damaged` → `reserved_ref` SO tetap, alokasi tetap di WA.
7. **TRF-02:** transfer baru 2 roll → kirim → `POST /api/transfers/{id}/exceptions` `{"kind":"other","roll_id":"R4",
   "reason":"uji B2b kembali"}` (`TransferExceptionIn` `:665-670`) untuk kedua roll → resolve masing-masing
   `POST .../exceptions/<exc>/resolve` `{"action":"return_to_source","reason":"uji B2b kembali"}` (`:673-675`, peran
   supervisor) → harapan kode: transfer `completed` dengan 0 roll diterima.

### R-TRF-2 — batal di tengah (TRF-01/03/04/05)
1. Buat & kirim transfer 2 roll (R-TRF-1 langkah 1–3). `DELETE /api/transfers/{id}?reason=uji%20B2b%20batal`
   (izin `transfer.cancel`) saat `dispatched` → `cancelled`; roll `available`@WA, `transfer_prior_status` masih ada
   (TRF-05), movement `transfer_cancelled` ×2; sesi gate dokumen tetap terbuka (TRF-04).
2. Ulang dengan terima 1 roll dulu → `DELETE` → 400 (benar). Laporkan roll lain `missing` → resolve `close_note` → 400;
   satu-satunya jalan `return_to_source` (TRF-03).
3. **TRF-04 balapan:** transfer `dispatched` 2 roll; kirim bersamaan `DELETE` dan `POST /receive` roll pertama → cek status
   akhir `cancelled` dengan satu roll `available`@WB (`last_transfer.ref_id` = transfer).
4. **TRF-05:** transfer roll SO `committed` (T15) → batal sebelum kirim → roll tetap `committed` dengan `transfer_ref`;
   batal sesudah kirim → roll `reserved` (bukan `committed`).
5. **TRF-01:** SO `reserved` dengan roll dikirim lewat transfer; set `reservation_expires_at` lewat (uji) dan jalankan job
   kedaluwarsa (lewat jalur scheduler yang sudah ada, bukan skrip tulis manual) → SO `expired`; terima roll di WB →
   roll `status:"reserved"`, `reserved_ref.id` = SO expired, `sales_orders.allocations` berisi alokasi baru.
6. **Antar-PT (T25–T30, TRF-10/11):** `POST /api/transfers/inter-company` body `InterCompanyTransferCreate`
   (`schemas.py:578-593`) `{"source_entity_id":"B","dest_entity_id":"E","items":[{"product_id":"P","quantity":15,
   "unit":"yard"}],"notes":"AUDIT-B2B"}` (izin `order.create`, user PT E saja) → roll PT B `reserved`
   (`ref type:"transfer"`); `source_warehouse_id` = gudang roll pertama walau roll dari >1 gudang. Approve sebagai PT B →
   `completed`, roll `owner_entity_id:E`, `acquired.via:"transfer"`, movement `ownership_transfer_out/in`, `je_intercompany`.

---

# LAMPIRAN 4 — MAKLOON kirim bahan (disusun subagen; disalin utuh dari part_mko.md)

## B2b — bagian MKO: kirim bahan (issue per roll, P18), terima hasil, batal

* **Jenis:** audit BACA-SAJA dari kode (tanpa runtime). Worktree HEAD `35506d7`. Tanggal 2026-11-09.
* **Berkas utama:** `backend/services/makloon_order_service.py` (1856 baris), `backend/services/makloon_issue_rolls.py`,
  `backend/services/stock_bucket_service.py`, `backend/services/material_reservation_service.py`,
  `backend/routers/makloon_orders.py`, `backend/schemas_makloon.py`, `backend/services/makloon_receipt_qc.py`,
  `backend/services/makloon_loss_service.py`, `backend/services/makloon_claim_service.py`,
  `backend/services/goods_receipt_close_service.py`, gate: `gate_doc_movements.py`, `rfid_v2_sources.py`,
  `gate_txn_service.py`, `routers/rfid_v2_ops.py`.
* **Catatan nomor baris:** nomor baris di brief (issue_step ~741, receive_step ~1309, dst.) adalah baris *tulisan* DB,
  bukan awal fungsi. Awal fungsi sebenarnya: `create_makloon_order` 224, `issue_step` 645, `record_service_step` 807,
  `receive_step` 946 (`_save_prog` 1042), `cancel_partial_receipt` 1354, `_release_leftover_reservation` 1406,
  `cancel_order` 1509, `set_step_tolerance` 1555, `_return_material_locked` 1602. Di
  `material_reservation_service.py`: `reserve_for_pr` 54, `reserve_for_mko` 112, `transfer_to_mko` 150,
  `consume_for_issue` 158, `release` 174.
* **Dok acuan:** `docs/KN_16_END_TO_END_PROCESS_FLOWS.md` **tidak punya bagian makloon** (grep "maklo/subkon/subcon" = 0;
  peta transisi §7 baris 177-194 tidak memuat `subcon`/`consumed`). Maksud yang dipakai sebagai acuan: DEC-13
  (`docs/development/gelombang-lanjutan-pasca-p05-2026-10-16/sources/P05_REPORT_SNAPSHOT.md:21` — batal sesudah issue:
  bahan tetap `subcon`, WIP tetap, retur dicatat manual), K-GDG-02 / K-RFID-09 / K-RFID-10
  (`docs/rfid/KEPUTUSAN_GATE_RFID.md:125-126, :141`), K-GDG-11 (:150).
* **Sudah dicatat paket lain (dirujuk, bukan temuan baru):** B3a SSOT-4 (cadangan makloon di `material_reservations`,
  bukan di roll), SSOT-8, DUP-4 ("panjang bebas" berulang), DUP-6, SCH-2/SCP-2 (`location_scope` melewatkan
  `makloon_orders`), status roll di luar enum registry (`consumed`/`subcon`, B3a baris 111-112).

Singkatan kolom: **CAS** = filter update memuat status asal / `saga_lock`; "replace_one {id}" = tulis dokumen penuh
dari snapshot tanpa prasyarat = **tanpa CAS** (lost update). "Batal?" = apakah dibalik saat `cancel_order`.

---

## (a) Tabel transisi status

### A. Header MKO — `makloon_orders.status` (draft · in_process · partially_received · completed · cancelled)

| # | dari → ke | pemicu | penjaga / CAS | efek | dibalik saat batal? | idempoten bila diulang? | pagar PT / lokasi |
|---|---|---|---|---|---|---|---|
| H1 | ∅ → `draft` | `POST /api/makloon-orders` (izin `makloon_order.create`, `routers/makloon_orders.py:76-96`, body `MakloonOrderCreate` `schemas_makloon.py:126-143`) → `create_makloon_order` `makloon_order_service.py:224`; `insert_one` :565 | n/a (insert); id `new_id("mko")` :243, tanpa kunci idempoten klien | `steps[]` `pending` (:481), `issue_ref = "<mko>:<seq>"` (:476); doc_refs kontrak/PO (:567-576); `reserve_for_mko` (:578-580) → `material_reservations` `active`; `buy_process` → PO bahan best-effort (`_spawn_material_po` :584-606); timeline `created` (:557); audit `makloon_order_created` (+`makloon_yield_override`) router :88-95. Tanpa movement/GL. | cadangan: ya (dilepas :1530). PO bahan `buy_process`: **tidak** (cancel_order tak menyentuh `po_id`) | **tidak** — klik ganda = 2 MKO + 2 cadangan (+2 PO) | `entity_id = payload.entity_id or ctx.active_entity_id` router :81 **tanpa** `resolve_requested_entity`/`assert_write_entity` (bisa PT tak ditugaskan / `"all"`); `from/target_warehouse_id` tak divalidasi |
| H2 | `draft` → `in_process` | `POST /api/makloon-orders/{id}/issue` (izin `makloon_order.issue`, router :151-169, body `MakloonIssueIn` `schemas_makloon.py:146-155`) → `issue_step` :645; set :739; tulis `replace_one({"id"})` :741 | **tanpa CAS**: cek `status!=cancelled` :652 & `step.status=="pending"` :655 dibaca dari snapshot :651; tidak ada `atomic_claim`, tidak cek `saga_lock` | lihat S1 + R1/R2 + M4 | tidak (DEC-13) | serial: ulang → 409 (:655). Paralel: **tidak** (MKO-01/02) | gudang dicek router :156-160 **hanya bila** `from_warehouse_id` diisi, terhadap `ctx.active_entity_id` (bukan `order.entity_id`); roll dicek `owner_entity_id == order.entity_id` (`makloon_issue_rolls.py:57`) |
| H3 | `partially_received` → `in_process` | `issue_step` langkah N+1 — :739 menyetel `IN_PROCESS` tanpa `_recompute_status_and_costing` | sama dengan H2 (tanpa CAS) | header "in_process" padahal ada langkah `received` (aturan `_recompute` :1441-1442 = `partially_received`); `completion_hold` lama tetap | tidak | sama H2 | sama H2 |
| H4 | `in_process` → `partially_received` / `completed` | `POST /api/makloon-orders/{id}/receive` (izin `receive`, router :185-203, body `MakloonReceiveIn` :167-183) atau tutup GRN (`goods_receipt_close_service._post_mko` :360-370) → `receive_step` :946; status oleh `_recompute_status_and_costing` :1297 (:1420-1444); tulis `update_one({"id", "saga_lock.token"})` + `$unset saga_lock` :1308-1312 | **CAS ya**: `_saga.claim(... precondition steps.$elemMatch{seq, status:"issued"})` :1033-1034; token; progres durable `receive_progress` (`_save_prog` :1042-1045) | lihat S2 + R4/R8 + M5 (bila `completed` :1314) | n/a — batal ditolak bila ada langkah `received` (:1513-1515) | ya: retry melanjutkan progres (lot deterministik :1169, bill via `receive_op_id` :1096-1099); sesudah sukses → 409 | `whscope.assert_usable(gudang hasil & gudang kiriman sebagian, order.entity_id)` :1019-1021; `guard_makloon_receive` (mode GRN → 409) router :190-191 |
| H5 | `partially_received` → `completed` | `POST /claim/approve` atau `/claim/reject` (izin `claim_approve`, router :261-292) → `makloon_claim_service._save` :252-263 | **tanpa CAS** (`replace_one({"id"})` :263) | `_recompute` → `completed`, timeline `completed`; **tidak** memanggil `_release_leftover_reservation` maupun `_flush_unabsorbed_service` | n/a | approve/reject kedua → ClaimError (bukan `pending_approval`) | `_assert_access` (penugasan) |
| H6 | `draft`/`in_process` → `cancelled` | `POST /api/makloon-orders/{id}/cancel` (izin `cancel`, router :295-303, body `MakloonOrderCancel{reason:""}` `schemas_makloon.py:250-251`) → `cancel_order` :1509; `replace_one({"id"})` :1528 | **tanpa CAS**; penjaga dari snapshot: bukan completed/cancelled :1511, tak ada langkah received :1513; **tidak** cek `saga_lock`, `receive_progress`, `partial_receipts` belum terposting, PO bahan | langkah `issued` → `awaiting_return=True` :1518-1520; `material_at_partner` :1522; `cancel_reason/cancelled_by/at` :1524; timeline :1525; `material_reservations` aktif → `released` :1530; audit `makloon_order_cancelled` router :301. Roll tetap `subcon`, WIP tetap, tanpa movement/GL (sesuai DEC-13). Tidak ada notifikasi, doc_refs, penutupan sesi gate | — | serial: 409 (:1511). Paralel: dua-duanya lolos (timeline ganda; `release` kedua 0) | `_assert_access` = `assert_entity_access` (penugasan, bukan PT aktif) router :408-412 |
| H7 | `cancelled` → `cancelled` (terminal) | retur / susut (S4/S5) hanya mengubah `material_at_partner` (:1675; `makloon_loss_service.py:141`) | klaim `precondition {"status":"cancelled"}` (:1592; loss `makloon_loss_service.py:43`) | — | — | — | — |
| H8 | `draft`/`in_process`/`partially_received` → (`_recompute`) | FASE T `POST /record-service` (izin `receive`, router :223-240, body `MakloonServiceIn` :186-201) → `record_service_step` :807; `replace_one({"id"})` :938 | klaim `makloon_record_service` **tanpa precondition** :882; `order` yang ditulis = snapshot **pra-klaim** :820 | tagihan jasa + GL + doc_refs (:884-905); langkah `received` | tidak (batal ditolak bila ada received) | serial 409 (:831); paralel: klaim 409 | `_assert_access` |

### B. Langkah — `steps[].status` (pending · issued · received · returned) + sub-status

| # | dari → ke | pemicu | penjaga / CAS | efek | dibalik saat batal? | idempoten? | pagar PT / lokasi |
|---|---|---|---|---|---|---|---|
| S1 | `pending` → `issued` | `issue_step` :727-731 (lihat H2). Penjaga lain: bukan langkah jasa murni :660-666, langkah sebelumnya `received` :668-671, stok gudang `_assert_source_stock` :704 (`inventory_balances.available_qty`), cadangan pihak lain :707-714 | **tanpa CAS** (H2) | roll R1 (per roll, `mir.pick_rolls` :678) atau R2 (FEFO) :719-722; `inventory_movements` `subcon_issue` per roll (`stock_bucket_service.py:270-275` / :91-98); `rebuild_balance` → `subcon_qty` (:276-277 / :100); GL `post_subcon_issue` Dr 1-1350 / Cr 1-1300, idempoten per `(mko,seq)` (`gl_service.py:1582-1596`); field `material_value`, `from_warehouse_id`, `issue_mode`, `issued_roll_ids` (**ditulis, tak pernah dibaca**), `issue_deviation`; skala estimasi hasil `apply_issue_qty` (`makloon_issue_rolls.py:142-158`); timeline `issued`/`issue_deviation` :732-738; `consume_for_issue` **hanya `seq==1`**, SESUDAH tulis :742-743; audit router :166-168. Roll tidak diberi `active_movement` (gate memakai `bucket_ref`) | tidak (DEC-13, sengaja) — dibalik oleh retur S4 | serial 409; paralel tidak (MKO-01/02) | lihat H2 |
| S2 | `issued` → `received` | `receive_step` :1246-1268 | CAS klaim + token (H4) | R4 (konsumsi input :1050), R8 (output :1177-1196, sisa :1206-1218); `vendor_bills` `makloon_service` :1100-1115 + GL `post_subcon_service` :1116-1119 + doc_refs `vendor_bill→makloon_order settles` :1121-1123; QC langkah terakhir: `wms_tasks` `qc_pending` + doc_refs `grn→makloon_order` (`makloon_receipt_qc.py:98-144`) bila `purchasing.qc_on_receipt` (K-GDG-11, :69-77); GL `post_subcon_receipt` Dr 1-1300 / Cr 1-1350 :1226-1227 (`gl_service.py:1631-1648`); kiriman sebagian → `posted` :1229-1245 + doc_refs :1313/:1340-1351; selisih + klaim otomatis :1279-1286, notifikasi klaim :1317-1318; `_reestimate_next` :1295; cadangan sisa dilepas bila `completed` :1314; `after_receipt` SPK inspeksi + tag RFID (`makloon_receipt_qc.py:147-176`, `update_one` tanpa CAS :174); pesanan khusus :1320-1327; backorder :1331-1336; audit `makloon_order_received` router :201 | n/a | ya (progres) | H4 |
| S3 | `issued` → `issued` + `awaiting_return=True` | `cancel_order` :1518-1520 | tanpa CAS (H6) | roll tetap `subcon`; gate OUT → `DOC_CANCELLED` merah, gate IN → hijau "bahan kembali" (`gate_doc_movements.py:37-45`, `:73-86`) | — | — | — |
| S4 | `issued`+`awaiting_return` → `returned` (atau tetap `issued` bila sebagian) | `POST /api/makloon-orders/{id}/steps/{seq}/return-material` (izin `makloon_order.cancel`, router :393-405, body `MaterialReturnIn{reason, roll_ids?, partial?[{roll_id, qty}]}` router :306-314) → `return_cancelled_material` :1579 → `_return_material_locked` :1602; `returned` bila sisa 0 :1672-1674; `replace_one({"id"})` :1680 | klaim `return_material` precondition `status=cancelled` :1592 (kunci di-`pop` dari snapshot sehingga `replace_one` mencabutnya; filter tulis tanpa token) | R5/R6; GL `reverse_subcon_issue` Dr 1-1300 / Cr 1-1350, idempoten per `(mko,seq[,part])` :1663-1664 (`gl_service.py:1794-1808`); `material_returns[]`, `material_value_open`, `returned_qty` :1665-1671; `material_at_partner` :1675; timeline; audit `makloon_material_returned` router :403 | — | ulang → 409 "sudah dicatat kembali" (:1655-1656 / :1642-1643) | `_assert_access`; roll kembali ke `warehouse_id` asal (tak bisa memilih gudang) |
| S5 | `issued`+`awaiting_return` → `returned` (susut/hilang) | `POST /steps/{seq}/material-loss` (izin `record_loss`, router :357-368, body `MaterialLossIn` :317-320) & `/material-loss/{loss_id}/decide` (izin `approve_loss`, `LossDecisionIn` :323-327) → `makloon_loss_service._execute` :103-145 (`returned` :139); `replace_one({"id"})` :222/:256 | klaim `material_loss` precondition `status=cancelled` (`makloon_loss_service.py:42-50`) | R4 dengan `movement_type="subcon_loss"` :112; GL `post_makloon_material_loss`; potong bon opsional | — | ulang → 409 (roll tak lagi di mitra) | penyetuju ≠ pencatat (`makloon_loss_service.py:242-243`) |
| S6 | `pending` → (tetap `pending`) saat MKO batal | `cancel_order` tidak menyentuh langkah pending | — | **tidak ada status akhir**; detail tetap `next_action="issue"` (:1719-1720); issue ditolak 409 (:652) | — | — | — |
| S7 | `pending` → `received` (jasa murni) | `record_service_step` :911-923 | lihat H8 | `service_absorption_pending` += jasa :924 | — | serial 409 | — |
| S8 | `partial_receipts[]` ∅ → `{posted:false}` (terima SEBAGIAN) | tutup GRN `mko_partial=true` (`POST /api/goods-receipts/{grn}/mko-partial {expected_version, partial}` `routers/goods_receipts.py:275-283`, lalu `/close`) → `goods_receipt_close_service._post_mko` :335-357 | CAS `saga_lock` absen + `steps.$elemMatch{seq, status:"issued", grn_id ≠}` :348-350; **tidak** memeriksa `order.status != cancelled`; `_close_preflight` hanya cek langkah `issued` (:474-479) | entri ditahan, timeline `partial_received`; tanpa stok/GL/tagihan | **tidak** — `cancel_order` tidak menolak/membatalkan kiriman ditahan (MKO-06) | ya (cek `grn_id` sudah ada :353-356) | gudang GRN dicatat `warehouse_id` (W2-003) |
| S9 | `{posted:false}` → `{posted:true}` | `receive_step` (kiriman akhir) :1232-1235 | CAS klaim + jumlah pending sama :1037-1039 | digabung ke penerimaan akhir | — | ya | H4 |
| S10 | `{posted:false}` → `cancelled_partials[]` | `POST /steps/{seq}/partial-receipts/{grn_id}/cancel` (izin `receive`, body `PartialCancelIn{reason}` router :206-220) → `cancel_partial_receipt` :1354-1391 | **CAS ya** :1377-1382 (`saga_lock` absen, langkah `issued`, entri `posted:false`) | `$pull`/`$push` + GRN `closed → cancelled` (CAS status) :1385-1390 | — | ulang → 404/409 | `_assert_access` |
| S11 | `claim.status` none/open → pending_approval → approved/rejected | `POST /claim`, `/claim/approve`, `/claim/reject` (router :243-292) → `makloon_claim_service` → `_save` :252-263 | **tanpa CAS** (`replace_one`) | lihat H5 | — | ClaimError bila status salah | — |

### C. Roll — `inventory_rolls.status` (available → subcon → consumed / available)

| # | dari → ke | pemicu | penjaga / CAS | efek | dibalik saat batal? | idempoten? | pagar PT / lokasi |
|---|---|---|---|---|---|---|---|
| R1 | `available` → `subcon` (PER ROLL, P18) | S1 dengan `roll_ids`/`roll_codes` → `mir.pick_rolls` (`makloon_issue_rolls.py:105-139`) → `sb.issue_rolls_to_subcon` (`stock_bucket_service.py:281-285`) → `move_specific_rolls` :240-278 | validasi baca `block_reason` (`makloon_issue_rolls.py:47-81`: produk, pemilik, gudang, panjang>0, `available`, tahanan inspeksi/`qc_hold_pending`, `reserved_ref/earmarked_for/committed_to`, `length_reserved`, `active_movement`, `repair_open`). **CAS per roll** :249-251 = `{id, status:available, length_remaining, reserved_ref∈{None,""}, length_reserved≯0, active_movement:None, repair_open∈{None,""}}` (tanpa `committed_to/earmarked_for/inspection.hold/qc_hold_pending`) | `bucket_ref={type:"subcon", id:issue_ref, mko_id, step, makloon...}` (`makloon_order_service.py:716-718`); semua-atau-tidak: kalah balapan → yang sudah pindah dikembalikan :255-261; movement `subcon_issue` per roll SESUDAH semua pindah :270-275; `rebuild_balance` :276-277; nilai WAC `_value_of_moved` :214-225 | tidak (DEC-13) | roll yang sama dua kali → CAS kalah → 409 | `owner_entity_id == order.entity_id`, `warehouse_id == gudang sumber` (`makloon_issue_rolls.py:57-60`) |
| R2 | `available` → `subcon` (JUMLAH/FEFO, jalur lama) | S1 tanpa roll → `sb.issue_to_subcon` :228-237 → `move_rolls_by_qty` :39-108 | query :47-49 & CAS :65 hanya `{id, status, length_remaining}` — **tanpa** pegangan roll (MKO-09) | roll utuh pindah, atau induk dipendekkan + anak `subcon` (`insert_child_roll`) :74-88; movement per roll :91-98; kompensasi `_rollback` bila konflik :101-107 | tidak | serial dijaga S1 | pemilik & gudang = filter query |
| R3 | `subcon` → `available` (kompensasi) | `move_specific_rolls` rollback :255-258; `move_rolls_by_qty` → `move_rolls_by_ref(..., from_status)` :103-104 | rollback per roll berprasyarat `bucket_ref.id` + `status` | tanpa movement (per roll) / movement `_rollback` (qty) | — | — | — |
| R4 | `subcon` → `consumed` | `consume_subcon_by_ref` :288-327 — dari terima S2 (:1050) dan susut S5 (`makloon_loss_service.py:112`) | **CAS** `{id, status:"subcon", bucket_ref.id}` :302-305 | `length_remaining=0`, `consumed_ref`; **`bucket_ref` TIDAK dicabut**; movement `subcon_consume`/`subcon_loss` :314-321; `rebuild_balance` :322-323 | — | ya (ulang → 0 terkonsumsi → 409 di terima :1051-1055) | — |
| R5 | `subcon` → `available` (retur MKO batal) | S4 → `sb.move_rolls_by_ref(issue_ref, "available", roll_ids=whole|None)` :1640-1641 → `stock_bucket_service.py:111-143` | filter `{bucket_ref.id[, id∈roll_ids]}` **TANPA status** :115-117, :125-127 | `bucket_ref=None`; movement `subcon_return_cancel`; rebuild. **Juga** menyentuh roll R4 hasil susut (masih ber-`bucket_ref`) → `consumed → available` panjang 0 (MKO-03) | — | ulang → 404→409 (bucket_ref sudah None) | roll kembali ke gudang asal |
| R6 | `subcon` (induk) → induk `subcon` dipendekkan + anak `available` | retur sebagian `partial[]` → `split_off_from_ref` :146-176 | CAS `length_remaining > take` (`find_one_and_update` :155-160) | anak `split_from_roll_id`, movement `subcon_return_cancel` :170-174 | — | gagal guard → `failed_partial_roll_ids` | — |
| R7 | `subcon` → anak `subcon` (susut sebagian) | `makloon_loss_service._split_partial_losses` → `split_off_from_ref(..., keep_in_bucket=True)` | sama R6 | anak ikut di bucket lalu dikonsumsi R4 | — | — | — |
| R8 | ∅ → `available` / `quarantine` (hasil + sisa) | S2 → `create_inbound_roll` (`makloon_order_service.py:1177-1185`, sisa :1208-1215) | id deterministik `roll_mko_{mko}_{seq}_{i}` / `_by` (:1169, :1205) | status dari `receipt_policy` (`makloon_receipt_qc.py:69-77`: langkah kain terakhir + `qc_on_receipt` → `quarantine`); movement `subcon_receipt`/`subcon_receipt_byproduct` (`roll_service.py:2161`); journey + `qc_task_id` (`makloon_receipt_qc.py:85-95`) | — | ya (retry melewati roll yang sudah ada :1170) | gudang hasil divalidasi :1019-1021 |
| R9 | `quarantine` → `available` | rilis QC (`qc_service`, di luar cakupan) lewat `wms_tasks` `qc_pending` | — | backorder/pesanan khusus saat lulus (:1324, :1331) | — | — | — |

### D. `material_reservations.status` (active · consumed · released)

| # | dari → ke | pemicu | penjaga / CAS | efek | dibalik saat batal? | idempoten? | pagar PT |
|---|---|---|---|---|---|---|---|
| M1 | ∅ → `active` (PR) | PR makloon disetujui → `reserve_for_pr` `material_reservation_service.py:54-109` | kunci serial `material_reservation_locks` `_id="{produk}:{PT}"` :84-93; id deterministik `mres_{pr}_{line}` :81 | `qty=min(need, free)`, `shortage_qty` :96-105 | PR batal/tolak → `release(pr_id)` (`purchase_requisition_service.py:367,387`) | ya (:65-67, :82-83) | `owner_entity_id = pr.entity_id` |
| M2 | `active`(ref PR) → `active`(ref MKO) | realisasi PR→MKO `pr_sourcing_service.py:994` → `transfer_to_mko` :150-155 | filter `{pr_id, pr_line_no, status:active}` | `ref_type/ref_id/mko_id` dipindah, history `moved_to_mko` | — | ya | — |
| M3 | ∅ → `active` (MKO langsung) | H1 :578-580 (jalur non-PR) / `pr_sourcing_service.py:995` → `reserve_for_mko` :112-147 | kunci serial sama :125-134; idempoten per MKO :118-120; id `mres_{mko}` | hanya `process_only` (:116) | dilepas :1530 | ya | `owner_entity_id = mko.entity_id` |
| M4 | `active` → `active` (qty berkurang) / `consumed` | S1 → `consume_for_issue` :158-171, **hanya bila `seq == 1`** (`makloon_order_service.py:742-743`), SESUDAH `replace_one` | filter `{id, status:active}` — tanpa CAS atas `qty` (baca-ubah-tulis) | `consumed_qty`, `qty=rest` / `status=consumed` | sisa aktif dilepas :1530 | **tidak** (dipanggil per issue; balapan = konsumsi ganda) | — |
| M5 | `active` → `released` | `release(ref_id)` :174-179 — dari `cancel_order` :1530, `_release_leftover_reservation` :1406-1417 (**hanya bila `completed` saat terima/catat jasa** :1314, :940), PR replan/tolak/batal | filter `{ref_id, status:active}` | `release_reason`, history; timeline `reservation_released` (:1414-1417) | — | ya (`modified_count` 0) | — |
| M6 | `consumed` / `released` → (terminal) | — | — | tidak ada penulis lain (pindaian `calls.json`: 5 penulis app, semuanya di atas) | — | — | — |

### E. Gate RFID untuk MKO (P18 · K-GDG-02 · K-RFID-10)

| # | dari → ke | pemicu | penjaga | efek | dibalik saat batal? | idempoten? | pagar |
|---|---|---|---|---|---|---|---|
| G1 | roll `subcon` + langkah `issued` + MKO tak batal → movement gate OUT **aktif** | `gate_evaluator.resolve_movement` → `gate_doc_movements.doc_movement` (`gate_doc_movements.py:64-70`, `_makloon` :25-45); manifest `rfid_v2_sources._makloon` :32-42 (roll `{bucket_ref.id: issue_ref, status: subcon}`) | arah `out`, gudang = `step.from_warehouse_id` | bukti trip `$push gate_exits` ke `makloon_orders` (`gate_txn_service.py:185-208`, `_apply` :272-273), buku `rfid_v2_gate_txn` per (lintasan, dokumen) | MKO batal → `DOC_CANCELLED` merah (K-RFID-09) | ya per lintasan (:197-199) | `source_document` → `assert_entity_access` (`rfid_v2_ops.py:29-38`) |
| G2 | MKO batal + `awaiting_return` → gate IN "kembali" | `gate_doc_movements.evaluate_in` :73-86 | gudang = gudang asal | hijau + bukti `gate_arrivals` saja; status roll baru berubah lewat S4 manual | — | ya | — |
| G3 | sesi dokumen gate OUT MKO `open` → `closed` | **hanya manual** `POST /api/rfid/v2/ops/doc-sessions/makloon_order/{issue_ref}/close` (izin `wms.scan`, `rfid_v2_ops.py:74-89`) → `close_document_session` (`gate_txn_service.py:406-430`) | `_doc_context` → `None` untuk MKO (:377) → roll dari rekaman sesi; `_completed` `{}` | REVIEW `ROLLS_MISSING` bila ada roll belum lewat | **tidak ada kait siklus hidup** MKO (pemanggil `safe_close`: `logistics_service.py:658`, `putaway_arrival_service.py:243`, `repair_order_service.py:330`, `transfer_receipt_service.py:252` — tanpa MKO) | ya (`closed_now`) | `_warehouse_of` MKO = gudang langkah PERTAMA (`rfid_v2_ops.py:50-51`), bukan langkah `issue_ref` |

**Jumlah transisi dipetakan: 37 baris** (header 8 · langkah 11 — termasuk sub-status `awaiting_return`, `partial_receipts`, `claim` · roll 9 · cadangan 6 · gate 3).

---

## (b) Kandidat anomali

Urut dampak. Label: **[pasti]** = terbukti dari kode; **[runtime]** = mekanisme dari kode, dampak/kemunculan perlu
dibuktikan runtime.

### MKO-01 — `issue_step` tanpa CAS/klaim → balapan dengan `cancel_order` menelantarkan bahan & WIP atau menghidupkan MKO batal
* **Berkas:** `makloon_order_service.py:651-655` (cek dari snapshot), `:741` (`replace_one({"id"})`), `:1510-1515` + `:1528` (cancel juga `replace_one({"id"})`, tanpa cek `saga_lock`).
* **Penalaran:** kedua aksi membaca dokumen, lalu menulis ulang dokumen penuh tanpa prasyarat. `issue_step` punya jendela
  panjang (validasi roll, CAS per roll, movement, `rebuild_balance`, jurnal) sebelum :741.
  (i) cancel menulis TERAKHIR → header `cancelled`, langkah tetap **`pending`** (snapshot cancel), `awaiting_return` tidak
  terpasang, padahal roll sudah `subcon` + jurnal `subcon_issue` sudah terposting; retur ditolak 409 (`:1607`) dan susut
  ditolak (`makloon_loss_service.py:182-183`) → roll & WIP 1-1350 terdampar tanpa jalan keluar di aplikasi.
  (ii) issue menulis TERAKHIR → pembatalan hilang (status `in_process`, `cancel_reason` hilang) padahal cadangan sudah
  `released` dan audit `makloon_order_cancelled` tercatat.
* **Dampak:** stok "di mitra" & WIP tanpa dokumen hidup; atau MKO batal hidup lagi tanpa cadangan. Tinggi.
* **Label:** [pasti] tanpa CAS · [runtime] kemunculan balapan.

### MKO-02 — Issue per roll ganda paralel (set roll berbeda) → dua set roll `subcon` di `issue_ref` sama, jurnal hanya satu
* **Berkas:** `makloon_order_service.py:655`, `:720`, `:725-726`, `:727-731`, `:741-743`; `gl_service.py:1586-1588`
  (idempoten per `(mko,seq)`); `stock_bucket_service.py:249-251` (CAS hanya per roll).
* **Penalaran:** CAS per roll mencegah roll yang SAMA dikirim dua kali, tetapi tidak ada CAS langkah. Dua permintaan
  dengan roll berbeda sama-sama lolos `pending`; keduanya memindah rollnya ke `bucket_ref.id = "<mko>:1"`. Jurnal kedua
  dilewati (`_already_posted`), `material_value`/`issued_roll_ids` = penulis terakhir, `consume_for_issue` dipanggil 2x.
  Saat terima, `consume_subcon_by_ref` mengonsumsi SEMUA roll (nilai A+B) → `post_subcon_receipt` meng-kredit WIP A+B
  padahal debit WIP hanya A → saldo 1-1350 MKO negatif / Persediaan lebih saji.
* **Dampak:** GL tak rekonsiliasi; cadangan terkonsumsi ganda. Tinggi.
* **Label:** [pasti] tanpa CAS · [runtime] kemunculan.

### MKO-03 — Retur "semua" (atau `roll_ids` eksplisit) menghidupkan roll yang sudah dicatat susut: `consumed → available` panjang 0
* **Berkas:** `stock_bucket_service.py:115-117, :125-127` (`move_rolls_by_ref` tanpa filter status),
  `:302-305` (`consume_subcon_by_ref` tidak mencabut `bucket_ref`), `makloon_order_service.py:1616, :1638-1641`
  (`whole` dari `roll_ids` tidak divalidasi status), `makloon_loss_service.py:112`.
* **Penalaran:** susut roll R4 → `status=consumed, length 0`, `bucket_ref.id` tetap `issue_ref`. Retur tanpa `roll_ids`
  memanggil `move_rolls_by_ref(issue_ref, "available", roll_ids=None)` → query `{bucket_ref.id}` ikut memuat R4 → disetel
  `available`, `bucket_ref=None`, movement `subcon_return_cancel` qty 0, `moved.rolls` ikut menghitungnya.
* **Dampak:** roll "Tersedia" panjang 0 (zombie) — saldo tidak berubah (`rebuild_balance` tak menghitung panjang 0,
  `roll_service.py:305-308`) tetapi status, jejak `consumed`, daftar roll & audit rusak; jumlah roll di catatan retur salah.
  Sedang.
* **Label:** [pasti] · konfirmasi runtime (resep A).

### MKO-04 — MKO selesai lewat keputusan klaim tidak pernah melepas sisa cadangan bahan
* **Berkas:** `makloon_claim_service.py:252-263` (`_save` → `completed`, tanpa `_release_leftover_reservation`);
  `makloon_order_service.py:1314`, `:940` (satu-satunya pemanggil), `:1408` (hanya bila `completed` saat itu),
  `:1426-1430` (klaim terbuka → `partially_received`).
* **Penalaran:** terima hasil kurang dari estimasi → klaim `open` → header `partially_received` → release dilewati.
  Approve/reject klaim → `completed` lewat `_save` → tidak ada release. `material_reservations` sisa tetap `active`
  selamanya (tak ada penulis lain, M6). Sejenis: `_flush_unabsorbed_service` juga tidak dipanggil di jalur ini → WIP jasa
  murni bisa tertinggal di 1-1350.
* **Dampak:** cadangan yatim mengurangi `free_for_commitment` (memblok issue MKO lain `:708-714`, cadangan PR baru) dan
  `available_qty` katalog (`apply_to_products`). Sedang–tinggi. (Bentuk cadangan di luar roll = B3a SSOT-4; temuan ini
  soal siklus hidupnya.)
* **Label:** [pasti].

### MKO-05 — `consume_for_issue` hanya untuk `seq == 1`: SPK yang bahannya masuk di langkah 2 (langkah 1 jasa murni) tidak pernah mengonsumsi cadangan
* **Berkas:** `makloon_order_service.py:742-743`; kontras komentar FASE T `:1445-1449` (bahan pokok tidak selalu masuk di
  langkah pertama) dan `record_service_step` yang tidak mengonsumsi apa pun.
* **Penalaran:** SPK printing `[screen (service_only), printing]` → bahan dikirim pada `seq=2` → cadangan `active` penuh
  sementara rollnya sudah `subcon` → stok yang sama dihitung dua kali sebagai "terikat" sampai MKO `completed` (dan bila
  selesai lewat klaim → tak pernah dilepas, MKO-04).
* **Dampak:** ketersediaan bahan lebih kecil dari seharusnya; issue/PR lain ditolak "sudah dicadangkan". Sedang.
* **Label:** [pasti].

### MKO-06 — Batal MKO dengan kiriman SEBAGIAN yang masih ditahan: hasil fisik sudah datang (GRN `closed`) tetapi tak pernah jadi stok
* **Berkas:** `makloon_order_service.py:1513-1515` (hanya cek `received`), `:949-950` (terima pada MKO batal → 409);
  `goods_receipt_close_service.py:348-350` (penahanan kiriman sebagian tidak cek `order.status`), `:474-479`
  (`_close_preflight` hanya cek langkah `issued`).
* **Penalaran:** langkah `issued` + `partial_receipts[posted:false]` → cancel lolos → langkah tetap `issued` +
  `awaiting_return`; kiriman ditahan tidak dibatalkan/ditolak; GRN-nya `closed`. Bahkan sesudah batal, GRN sebagian BARU
  masih bisa ditahan pada MKO batal. Jalur keluar hanya `cancel_partial_receipt` manual (S10) — barang hasil fisik di
  gudang tetap tanpa roll; sementara retur bahan mengharapkan bahan INPUT kembali.
* **Dampak:** barang fisik tanpa stok sistem; gate IN hasil bisa merah. Sedang.
* **Label:** [pasti].

### MKO-07 — `cancel_order` tidak memeriksa `saga_lock`/`receive_progress`: batal di tengah/sesudah saga terima gagal
* **Berkas:** `makloon_order_service.py:1509-1528`; `:1043-1045` (`_save_prog` tidak memeriksa `matched_count`);
  `:1309-1312` (409 SESUDAH semua efek); `:1609-1611, :1659` (retur menghitung nilai dari `material_value` penuh).
* **Penalaran:** (a) cancel membaca dokumen SEBELUM klaim terima lalu `replace_one` → `saga_lock` terhapus → semua
  `_save_prog` terima menjadi no-op diam-diam, tulisan akhir 409 padahal roll sudah `consumed`, roll hasil lahir, tagihan
  & jurnal terposting. (b) saga terima gagal (kunci tertinggal) → cancel tetap lolos (langkah masih `issued`) → status
  `cancelled` + `awaiting_return` padahal bahan sudah jadi hasil; setelah admin melepas kunci, retur memindah roll
  `consumed` (mekanisme MKO-03) dan membalik WIP **penuh** → Persediaan dobel (roll hasil + bahan "kembali").
* **Dampak:** tinggi bila terjadi. **Label:** [pasti] tak ada pemeriksaan · [runtime] butuh balapan/kegagalan saga.

### MKO-08 — Penulis `replace_one` dokumen penuh menghapus bukti gate (`gate_exits`/`gate_arrivals`) & `receipt_qc`
* **Berkas:** penulis bukti `gate_txn_service.py:206-207` (`$push` ke `makloon_orders`), `makloon_receipt_qc.py:174`;
  penimpa: `makloon_order_service.py:741, :938, :1528, :1680`, `makloon_claim_service.py:263`,
  `makloon_loss_service.py:222, :256`.
* **Penalaran:** lintasan gate OUT/IN yang tercatat di antara baca & `replace_one` hilang; buku `rfid_v2_gate_txn` sudah
  `done` sehingga tidak ditulis ulang. Kunci `saga_lock` (retur/susut) tidak dihormati penulis bukti gate.
* **Dampak:** jejak trip gate MKO hilang permanen (bukti K-GDG-02). Sedang. **Label:** [pasti] mekanisme · [runtime].

### MKO-09 — Jalur issue JUMLAH (FEFO) melewati pegangan roll yang dijaga jalur per roll
* **Berkas:** `stock_bucket_service.py:47-49` (query), `:65` (CAS hanya status+panjang), dipanggil
  `makloon_order_service.py:722`; kontras `makloon_issue_rolls.py:10-12` ("SATU aturan kelayakan ... dua permukaan") dan
  `:70-80`.
* **Penalaran:** roll `available` yang `length_reserved>0` (potong SO), `active_movement` (PA), `repair_open`, atau
  `inspection.hold`/`qc_hold_pending` ikut dipilih FEFO dan pindah UTUH ke `subcon` (bila `rlen <= remaining`). Cek stok
  `_assert_source_stock` memakai saldo (sudah dikurangi pegangan) tetapi pemilihan roll tidak.
* **Dampak:** reservasi potong SO pindah ke mitra; roll PA/QC keluar. Sedang–tinggi. (Kerabat B3a DUP-4, tidak termasuk
  tiga "lupa" yang disebut di sana.) **Label:** [pasti] pemilihan · [runtime] butuh data roll berpegangan.

### MKO-10 — Sesi gate OUT MKO tidak pernah ditutup oleh siklus hidup dokumen (K-RFID-10)
* **Berkas:** tak ada `safe_close("makloon_order", …)` (bandingkan `repair_order_service.py:330`); `gate_txn_service.py:377`
  (`_doc_context` → None), `:380-404` (`_completed` tanpa cabang MKO); `rfid_v2_ops.py:50-51` (`_warehouse_of` MKO =
  gudang langkah pertama).
* **Penalaran:** K-RFID-10 ("roll yang belum lewat dinilai saat dokumen ditutup/dikirim"): untuk MKO "dikirim" = issue
  yang mendahului gate, dan terima/batal/retur tidak menutup sesi → roll yang tidak lewat gate tak pernah dinilai
  `ROLLS_MISSING` kecuali ditutup manual; pelengkap handheld tidak dikenali. Langkah ≥2 dengan gudang sumber berbeda
  memakai gudang salah pada status/penutupan manual tanpa rekaman sesi.
* **Dampak:** bahan keluar tanpa lewat gate tidak terdeteksi. Sedang. **Label:** [pasti] · ketidakcocokan dok.

### MKO-11 — Pagar PT saat buat MKO & gudang sumber issue
* **Berkas:** `routers/makloon_orders.py:81` (entitas dari payload mentah); `:156-160` (gudang hanya dicek bila diisi,
  terhadap `ctx.active_entity_id`); `makloon_order_service.py:244-245` (gudang tak divalidasi saat buat).
* **Penalaran:** pengguna satu PT bisa membuat MKO atas PT lain via `entity_id` (bandingkan `resolve_requested_entity`
  `entity_scope.py:590-617`); mode "Semua Entitas" → `entity_id="all"` (MKO tak bisa di-issue karena tak ada roll milik
  "all"). Issue tanpa `from_warehouse_id` memakai gudang order yang tak pernah divalidasi.
* **Dampak:** sedang (data lintas PT / MKO macet). **Label:** [pasti]. (Cakupan lokasi `makloon_orders` = B3a SCH-2/SCP-2.)

### MKO-12 — Batal MKO `buy_process` tidak menyentuh PO bahan tertaut
* **Berkas:** `makloon_order_service.py:1509-1531` (tak ada `po_id`); PO dibuat `:512-514`, ditaut `:600-601`.
* **Dampak:** PO bahan tetap terbuka (stok masuk tanpa SPK). Rendah–sedang. **Label:** [pasti] · maksud perlu pemilik.

### MKO-13 — Dua aturan status header: `issue_step` menimpa `in_process` tanpa `_recompute`
* **Berkas:** `makloon_order_service.py:739` vs `:1441-1444`.
* **Dampak:** MKO dengan langkah sudah diterima tampil "Dalam proses" (filter `status=partially_received` luput).
  Rendah. **Label:** [pasti].

### MKO-14 — Field/status yatim
* `issued_roll_ids` ditulis `:730`, tak pernah dibaca (grep backend+frontend) — retur/terima/gate memakai
  `bucket_ref.id`, sehingga `roll_ids` retur tidak dibatasi ke roll yang benar-benar dikirim.
* Header `"done"`/`"received"` dibaca `:1320` tetapi tak pernah ditulis untuk `makloon_orders`.
* Langkah `pending` pada MKO batal tak punya status akhir; detail tetap `next_action="issue"` (`:1719-1720`).
* `issue_mode`, `issue_deviation` hanya ditulis (backend). **Label:** [pasti]; rendah.

### MKO-15 — `resolve_codes` mencocokkan EPC tanpa status tag & `roll_no` tanpa pemilik
* **Berkas:** `makloon_issue_rolls.py:93` (tanpa `status`), `:96` (`find_one` roll_no lintas PT); EPC hanya unik untuk tag
  HIDUP (`rfid_service.py:471`, indeks parsial); bandingkan `routers/rfid.py:197` (`status:"active"`).
* **Dampak:** tag mati lama / roll PT lain "menang" → roll salah dipilih atau penolakan 400 menyesatkan. Rendah–sedang.
  **Label:** [runtime] (butuh EPC daur ulang / roll_no kembar).

### MKO-16 — CAS `move_specific_rolls` lebih longgar dari `block_reason` (TOCTOU)
* **Berkas:** `stock_bucket_service.py:249-251` vs `makloon_issue_rolls.py:70-75` (`committed_to`, `earmarked_for`,
  `inspection.hold`, `qc_hold_pending` tidak di CAS). Pegangan yang muncul di antara baca `:123` dan CAS lolos.
  **Label:** [runtime]; rendah.

### MKO-17 — `record_service_step` menulis snapshot PRA-klaim
* **Berkas:** `makloon_order_service.py:820` (baca), `:882` (klaim tanpa precondition), `:938` (`replace_one`).
  Tulisan lain di antara keduanya (kiriman sebagian, toleransi, bukti gate) hilang. **Label:** [pasti] · [runtime]; rendah.

### MKO-18 — Buat MKO tanpa kunci idempoten
* **Berkas:** `makloon_order_service.py:243, :565`; router `:76-96`. Klik ganda → 2 MKO, 2 cadangan (berebut stok bebas
  yang sama → cadangan kedua `shortage`), 2 PO `buy_process`. **Label:** [pasti]; rendah–sedang.

### MKO-19 — Ketidakcocokan dokumen acuan
* `KN_16` tidak memuat alur makloon; §7 (`KN_16...:177-194`) tidak punya `subcon`/`consumed`. Kode SESUAI DEC-13 untuk
  "roll tetap `subcon` + WIP tetap saat batal; retur manual + 1 jurnal balik" (bukan anomali). Alasan batal opsional
  (`schemas_makloon.py:250-251`) sementara retur/susut/batal kiriman sebagian wajib ≥ 5 karakter. **Label:** [pasti]; rendah.

---

## (c) Resep uji runtime

### R0 — Persiapan (baca-saja kecuali langkah uji itu sendiri)
* Base URL `http://localhost:8001/api`. Login: `POST /api/auth/login` body `{"email":"admin@kainnusantara.id","password":"<sandi demo — AGENTS.md>"}`
  (`schemas.py:161-163`) → pakai `token` sebagai `Authorization: Bearer <token>` (`dependencies.py:27-32`) dan header
  `X-Entity-Id: <ENT>` (satu PT, bukan `all`; lihat `entity_context` di respons login).
* Izin (`permissions_config.py`): admin & manager punya `makloon_order.{view,create,issue,receive,cancel,claim,claim_approve}`
  (+admin `record_loss`,`approve_loss` :602); warehouse/warehouse_admin: `view,issue,receive,claim` (:421, :523). Toleransi
  langkah butuh `supplier_contract.update` (router :338). Tutup sesi gate: `wms.scan`; lihat sesi: `wms.view`. Jurnal:
  `accounting.view`; cadangan: `purchase_requisition.view`; roll: `product.view`.
* Cek mode terima: `GET /api/goods-receipts/mode` — bila PT bermode `grn`, `POST /receive` → 409 `GRN_MODE`
  (`receiving_mode_service.py:24-30`): pakai PT lain atau jalur GRN.
* Data: pilih bahan **P** dengan ≥ 6 roll `available` bebas di gudang **W** milik **ENT**
  (`GET /api/inventory/rolls?product_id=P&warehouse_id=W&owner_entity_id=ENT&status=available`, ambil yang
  `length_reserved` 0, tanpa `reserved_ref`/`active_movement`), produk hasil **Q** (≠P, `base_unit` terisi), mitra **M**
  (`GET /api/makloons`), tahap `celup` (material_flow `moves`) & `screen` (`either`, bawaan `service_only`)
  (`GET /api/process-stages`; seed `domain_registry.py:462, :469, :479`).
* Pembacaan DB (read-only) untuk cek: `docker compose -f docker-compose.dev.yml exec mongo mongosh test_database --quiet --eval '<query>'`.
* Body buat MKO dasar (field persis `MakloonOrderCreate`/`MakloonStepInput`, `schemas_makloon.py:80-143`):

```json
{"mode":"process_only","material_product_id":"P","material_qty":<Σ panjang roll uji>,
 "from_warehouse_id":"W","target_warehouse_id":"W",
 "manual_material_reason":"uji audit B2b tanpa resep","route_reason":"uji audit B2b","notes":"AUDIT-B2B-<skenario>",
 "steps":[{"stage_code":"celup","process_type":"celup","makloon_id":"M","input_product_id":"P",
           "output_product_id":"Q","input_qty":<Σ>,"roll_count":4,"tariff_basis":"lumpsum","tariff_rate":100000}]}
```
  Sesudah buat, cek: `makloon_orders {id, status:"draft", steps.0.status:"pending", steps.0.issue_ref:"<id>:1"}`;
  `material_reservations {id:"mres_<id>", status:"active", qty, shortage_qty, owner_entity_id:ENT}`;
  `audit_logs {action:"makloon_order_created", entity_id:<id>}`.

### Skenario A — issue per roll → ulang → batal → susut 1 roll → retur semua (DEC-13, MKO-03, MKO-10, MKO-14)
1. Buat MKO (R0) dengan `material_qty` = Σ 4 roll → `<A>`.
2. `GET /api/makloon-orders/<A>/steps/1/issue-rolls?warehouse_id=W` → pilih `rolls[].id` R1..R4 (blok `blocked[]` beralasan).
3. `POST /api/makloon-orders/<A>/issue` body `{"step_seq":1,"from_warehouse_id":"W","roll_ids":["R1","R2","R3","R4"]}`
   (`MakloonIssueIn` `schemas_makloon.py:146-155`). Cek:
   * `inventory_rolls` R1..R4: `status:"subcon"`, `bucket_ref.type:"subcon"`, `bucket_ref.id:"<A>:1"`, `bucket_ref.mko_id:"<A>"`.
   * `inventory_movements {source_document:"<A>:1", movement_type:"subcon_issue"}` = 4 baris.
   * `inventory_balances {product_id:P, warehouse_id:W, owner_entity_id:ENT}`: `subcon_qty` naik Σ, `available_qty` turun Σ.
   * `journal_entries {source_type:"subcon_issue", source_id:"<A>:1"}` = 1 (Dr 1-1350 / Cr 1-1300 = `steps.0.material_value`).
   * `makloon_orders`: `status:"in_process"`, `steps.0.status:"issued"`, `issue_mode:"rolls"`, `issued_roll_ids` = R1..R4.
   * `material_reservations mres_<A>`: `consumed_qty` = Σ, `status:"consumed"` (atau `active` dengan `qty` sisa).
4. Ulang langkah 3 persis → harus **409** "sudah di-issue" (idempoten serial OK).
5. `POST /api/makloon-orders/<A>/cancel` body `{"reason":"uji audit B2b batal sesudah issue"}`. Cek (DEC-13 = benar bila):
   `status:"cancelled"`, `material_at_partner:true`, `steps.0.status:"issued"`, `steps.0.awaiting_return:true`;
   R1..R4 tetap `subcon`; TIDAK ada `journal_entries source_type:"subcon_issue_reversal"`; `mres_<A>` aktif → `released`.
   **MKO-10:** `GET /api/rfid/v2/ops/doc-sessions/makloon_order/<A>:1?direction=out` → sesi tidak ditutup oleh batal.
   **MKO-14:** `GET /api/makloon-orders/<A>` → langkah pending lain (bila ada) masih `next_action:"issue"`.
6. `POST /api/makloon-orders/<A>/steps/1/tolerance` body `{"tolerance_pct":100,"reason":"uji audit toleransi B2b"}`
   (`StepToleranceIn` router :330-332) — supaya susut otomatis (dalam toleransi).
7. `POST /api/makloon-orders/<A>/steps/1/material-loss` body `{"reason":"uji susut audit B2b","roll_ids":["R4"]}`
   (`MaterialLossIn` router :317-320). Cek: R4 `status:"consumed"`, `length_remaining:0`, **`bucket_ref.id` masih `"<A>:1"`**;
   `steps.0.material_losses[0].status:"posted"`; movement `subcon_loss` R4.
8. `POST /api/makloon-orders/<A>/steps/1/return-material` body `{"reason":"uji retur semua audit B2b"}` (tanpa `roll_ids`;
   `MaterialReturnIn` router :311-314). Cek:
   * R1..R3 `available`, `bucket_ref:null`; `steps.0.status:"returned"`; `journal_entries {source_type:"subcon_issue_reversal", source_id:/^<A>:1/}` = 1,
     nilai = `material_value` − nilai susut.
   * **MKO-03 terbukti bila:** R4 `status:"available"` dengan `length_remaining:0`, `bucket_ref:null`, ada
     `inventory_movements {roll_id:"R4", movement_type:"subcon_return_cancel", quantity:0}`, dan
     `steps.0.material_returns[-1].rolls` = 4 (bukan 3). Benar = R4 tetap `consumed`.
   * Varian: ulangi skenario dengan langkah 8 memakai `{"reason":"…","roll_ids":["R1","R2","R3","R4"]}`.
9. Ulang langkah 8 → harus 409 (idempoten).

### Skenario B — balapan issue × batal (MKO-01, MKO-08)
1. Buat MKO `<B>` (R0) dengan ≥ 10 roll (jendela issue lebih panjang).
2. Kirim **bersamaan** (mis. bash: `curl … /issue & curl … /cancel & wait`):
   `POST /api/makloon-orders/<B>/issue` `{"step_seq":1,"from_warehouse_id":"W","roll_ids":[…10 roll…]}` dan
   `POST /api/makloon-orders/<B>/cancel` `{"reason":"uji balapan audit B2b"}`. Ulangi dengan MKO baru 5–10 kali.
3. Bukti bila keduanya 200:
   * (i) `makloon_orders.status:"cancelled"` DAN `steps.0.status:"pending"` (tanpa `awaiting_return`) SEMENTARA ada
     `inventory_rolls {bucket_ref.id:"<B>:1", status:"subcon"}` dan `journal_entries {source_type:"subcon_issue", source_id:"<B>:1"}`;
     lalu `POST …/steps/1/return-material {"reason":"uji retur balapan"}` → 409 (terdampar).
   * (ii) atau `status:"in_process"`, `cancel_reason` hilang, padahal `audit_logs {action:"makloon_order_cancelled", entity_id:"<B>"}`
     ada dan `material_reservations mres_<B>` `released`.
4. MKO-08 (opsional, butuh simulator gate V2 aktif): picu lintasan gate OUT `source_id "<B>:1"` lalu segera `/cancel`;
   cek `makloon_orders.gate_exits` vs `rfid_v2_gate_txn` (state `done` tetapi entri `gate_exits` hilang).

### Skenario C — issue ganda paralel set roll berbeda (MKO-02)
1. Buat MKO `<C>` dengan `material_qty` = Σ R1..R4.
2. Bersamaan: `POST …/<C>/issue {"step_seq":1,"from_warehouse_id":"W","roll_ids":["R1","R2"]}` dan
   `{"step_seq":1,"from_warehouse_id":"W","roll_ids":["R3","R4"]}`.
3. Bukti bila keduanya 200: R1..R4 semua `subcon` ber-`bucket_ref.id:"<C>:1"`; `journal_entries {source_type:"subcon_issue", source_id:"<C>:1"}` = 1
   dengan nilai hanya satu pasang; `steps.0.material_value` & `issued_roll_ids` = satu pasang;
   `material_reservations.history` berisi 2 event `consumed`.
4. Lanjut terima: `POST /api/makloon-orders/<C>/receive` body (`MakloonReceiveIn` :167-183, `MakloonReceiveRoll` :158-164)
   `{"step_seq":1,"actual_output_qty":<X>,"tariff":100000,"output_warehouse_id":"W","rolls":[{"lot":"AUD-B2B-C1","length":<X>,"grade":"A"}]}`.
   Cek: `journal_entries {source_type:"subcon_receipt", source_id:"<C>:1"}` nilai = nilai 4 roll + jasa > debit WIP
   (Σ `subcon_issue` + `subcon_service`) → saldo 1-1350 untuk `<C>` negatif.

### Skenario D — terima kurang dari estimasi → klaim → selesai → cadangan yatim (MKO-04, MKO-13)
1. Buat MKO `<D>` dengan `material_qty` = Σ 4 roll **+ 50** (stok bebas cukup agar `mres_<D>.qty` > Σ 4 roll).
2. Issue 4 roll (seperti A3). Cek `mres_<D>` `status:"active"`, `qty` = sisa (> 0).
3. Terima dengan hasil ≈ 50 % estimasi (`steps.0.expected_output_qty` sesudah skala):
   `POST …/<D>/receive {"step_seq":1,"actual_output_qty":<E/2>,"tariff":100000,"output_warehouse_id":"W","rolls":[{"lot":"AUD-B2B-D1","length":<E/2>,"grade":"A"}]}`.
   Cek: `status:"partially_received"`, `completion_hold.reason:"claim_unsettled"`, `steps.0.claim.status:"open"`, `mres_<D>` masih `active`.
4. `POST …/<D>/claim {"step_seq":1,"action":"terima_catatan","amount":0,"reason":"uji audit B2b"}` (`MakloonClaimIn` :204-209), lalu
   `POST …/<D>/claim/approve {"step_seq":1,"note":"uji"}` (`MakloonClaimDecisionIn` :212-215).
5. **Bukti MKO-04:** `makloon_orders.status:"completed"` tetapi `material_reservations {id:"mres_<D>"}` tetap `status:"active"`
   (qty sisa), tidak ada timeline `reservation_released`; `GET /api/material-reservations?ref_id=<D>` menampilkannya aktif.
6. **MKO-13** (MKO 2 langkah): sesudah terima langkah 1 (`partially_received`), issue langkah 2 → header `in_process`.

### Skenario E — kiriman sebagian ditahan lalu batal (MKO-06)
1. MKO `<E>` di-issue (A3). Buat GRN hasil makloon dengan baris target `mko_step` (alur `routers/goods_receipts.py:32-268`; body
   GRN tidak diverifikasi di audit ini), tandai `POST /api/goods-receipts/<grn>/mko-partial {"expected_version":<v>,"partial":true}`
   (`GRNPartialIn` :275-277), tutup `POST /api/goods-receipts/<grn>/close {"expected_version":<v>}` (`GRNVersionIn`).
   Cek `steps.0.partial_receipts[0].posted:false`, GRN `status:"closed"`.
2. `POST …/<E>/cancel {"reason":"uji batal dengan kiriman sebagian"}` → **bukti MKO-06** bila 200: `status:"cancelled"`,
   `partial_receipts[0].posted:false` tetap, tak ada roll hasil `{acquired_via:"subcon_receipt", ref_id:"<E>"}`;
   `POST …/<E>/receive` → 409. GRN sebagian kedua pada MKO batal masih diterima `_post_mko`.

### Skenario F — langkah 1 jasa murni, bahan dikirim di langkah 2 (MKO-05)
1. Buat MKO `<F>` dengan `steps`:
   `[{"stage_code":"screen","material_flow":"service_only","makloon_id":"M","input_product_id":"P","tariff_basis":"lumpsum","tariff_rate":150000},
     {"stage_code":"printing","process_type":"printing","makloon_id":"M","output_product_id":"Q","tariff_basis":"lumpsum","tariff_rate":100000}]`.
2. `POST …/<F>/record-service {"step_seq":1,"tariff":150000}` (`MakloonServiceIn` :186-201).
3. Issue langkah 2 per roll: `{"step_seq":2,"from_warehouse_id":"W","roll_ids":[…]}`.
4. **Bukti:** roll `subcon` (`bucket_ref.id:"<F>:2"`) TETAPI `mres_<F>` tetap `active` dengan `qty` & `consumed_qty` tak berubah;
   `GET /api/products` → `makloon_reserved_qty` P masih memuat cadangan itu.

### Skenario G — pagar PT buat MKO (MKO-11)
1. Login akun yang `entity_context.allowed_entity_ids` = [A] saja (akun peran demo, sandi `<sandi demo — AGENTS.md>`).
2. `POST /api/makloon-orders` header `X-Entity-Id: A`, body R0 + `"entity_id":"B"` (PT tak ditugaskan) → benar = 403;
   **bukti** bila 200 dan `makloon_orders.entity_id:"B"`.
3. Admin dengan `X-Entity-Id: all`, body tanpa `entity_id` → **bukti** bila 200 dan `entity_id:"all"`, `mres_<id>.owner_entity_id:"all"`, `qty:0`.

### Pembersihan
Semua MKO uji memakai `notes` berawalan `AUDIT-B2B-`; pulihkan data acuan dengan `bash scripts/dev_restore_demo.sh`
(AGENTS.md) setelah selesai — jangan menghapus manual.


---

# LAMPIRAN 5-6 — PERBAIKAN & RETUR KE SUPPLIER (disusun subagen; disalin utuh dari part_repair_preturn.md)

## B2b — Bagian Perbaikan (Repair Order) & Retur ke Supplier (Purchase Return)

Audit **baca-saja** atas worktree `agent-a300a69678b4a7b03` (HEAD `35506d7`). Tidak ada berkas repo diubah, tidak ada
docker/uvicorn/skrip dijalankan. Semua bukti `berkas:baris` relatif ke `backend/` kecuali disebut lain.
Rujukan silang (RUJUK SAJA, tidak diulang): B3a **SSOT-1** (tak ada tabel transisi roll), **SSOT-2** (grade diubah di
luar `grade_service`: `purchase_return_service.py:600-606`, `repair_order_service.py:305`), **SSOT-8** (reservasi potong
yatim), **SCH-4** (pembuat roll mentah, termasuk `repair_order_service.py:296`), **SCH-6** (mutasi bukan buku besar),
**STK-6/7** (`wip` tak dihitung di beberapa layar), **DUP-4** (panjang bebas diulang), **DUP-6**.

Ringkas angka: **Perbaikan 5 transisi dokumen** (+4 transisi status roll); **Retur Beli 19 transisi** (12 header
`status`, 7 `supplier_status`) + `gl_status` 4 nilai + 5 jalur `saga_lock`; kandidat anomali **REP-01..REP-13**,
**PRT-01..PRT-18**.

---

## (a1) PERBAIKAN — `repair_orders.status`

Mesin status: `STATUS_LABEL` `repair_order_service.py:23` = `draft | sent | done | cancelled`. Semua transisi keluar
memakai `_push()` `repair_order_service.py:169-177` yang ber-CAS `{"id", "status": expect}` (`:171-172`) dan menulis
`timeline` (`$push`, `:174`) — **tetapi CAS itu dijalankan di AKHIR fungsi, sesudah semua efek roll/mutasi/jurnal**.
Izin: `permissions_config.py:627-633` (admin/manager/warehouse_admin/md: view,create,send,receive,cancel; warehouse:
view,send,receive). Router: `routers/repair_orders.py`.

| # | dari → ke | pemicu | penjaga / CAS | efek | dibalik saat batal? | idempoten bila diulang? | pagar PT / lokasi |
|---|---|---|---|---|---|---|---|
| R1 | (baru) → `draft` | `POST /api/repair-orders` `routers/repair_orders.py:104-113` (izin `repair_order.create`) → `svc.create` `repair_order_service.py:106-159` (insert `:153`) | validasi baca: `_rolls_for_lines` `:58-79` (milik PT `:69`, status ∈ `ELIGIBLE_STATUSES` `:24`=available/quarantine/damaged/blocked/hold `:71`, tanpa `reserved_ref`/`length_reserved` `:74`, tanpa `repair_open` `:76`). **Roll TIDAK dikunci** (`repair_open` baru diisi saat kirim) | dokumen + `lines[]` (snapshot `prev_status`, `qty_sent`=`length_remaining`, grade/lot/unit_cost sebelum `:133-137`), `cost_estimate`, `timeline[0]` `:151-152`; `doc_refs.safe_link` ke sumber bila `source_type/source_id` (`:154-157`); `audit("repair_order_created")` router `:111-112`. Roll/saldo/mutasi/GL: tidak ada | n/a | Tidak: POST ganda = 2 draf dengan roll sama (keduanya lolos `:76`) | `entity_id` = PT aktif, wajib bukan "Semua" (`routers/repair_orders.py:30-34`); owner roll dicek `:69`; **gudang roll tidak dicek** terhadap cakupan gudang pengguna |
| R2 | `draft` → `sent` | `POST /api/repair-orders/{id}/send` `routers/repair_orders.py:122-131` (izin `send`; `_load` `:21-27` assert entitas) → `svc.send` `repair_order_service.py:188-216` | cek baca `status=="draft"` `:192`; CAS per roll `:197-199` = `{id, status: prev_status, reserved_ref kosong, repair_open kosong}` — **tanpa `length_reserved`, `active_movement`, `owner_entity_id`, `length_remaining`** (bandingkan CAS lengkap `stock_bucket_service.py:249-251`); gagal satu → semua roll dikembalikan `:201-207`; CAS dokumen `_push(...,"draft")` `:215-216` | roll → `status: wip` (`REPAIR_STATUS` `:25`), `bucket_ref {type:repair,id,number,partner}`, `repair_open = ro.id` `:200`; mutasi `repair_send` qty=`qty_sent` (snapshot saat buat) `:211` via `_movement` `:180-185` (tanpa `direction`/tanda); `rebuild_balance` per segmen `:213-214` → masuk `wip_qty` (bucket FISIK `roll_service.py:210`); `sent_at/by`, timeline; `audit("repair_order_sent")` router `:130`. **Tanpa jurnal** (docstring `:189`). Gate: tidak membuka sesi; gate OUT memvalidasi sesudahnya lewat sumber `repair_order` (`rfid_v2_sources.py:45-56` butuh `status=="sent"`; `gate_doc_movements.py:46-60`) | Ya, oleh R5 (batal) | Ya untuk ulang berurutan (`:192`); bersamaan: CAS roll menyerialkan, pemenang tunggal | owner roll **tidak** dicek ulang di CAS; tak ada pagar gudang |
| R3 | `sent` → `done` | `POST /api/repair-orders/{id}/receive` `routers/repair_orders.py:134-144` (izin `receive`; body `RepairReceive` `:65-68`) → `svc.receive` `repair_order_service.py:241-331` | cek baca `status=="sent"` `:246`; semua roll wajib diisi `:248-250`; roll dicari `{id, repair_open: ro.id}` `:268` (tanpa CAS status `wip`); **CAS dokumen `_push(...,"sent")` baru di `:324-328`, SESUDAH semua tulisan roll + mutasi + jurnal**; **tanpa `preflight_posting`** | per roll: susut → mutasi `repair_loss` `:280-281`; qty_out=0 → roll `consumed`, `length_remaining 0`, `consumed_ref` `:282-286`; celup ulang ke SKU lain → roll ANAK `insert_one({**roll,...})` `:288-296` (status `available`, SKU tujuan, `unit_cost` baru) + induk `consumed`, `child_roll_ids` `:297-300` + mutasi `repair_receive` di anak `:301`; selain itu roll `available`, `length_remaining=qty_out`, `grade=grade_after`, `lot=lot_after`, `unit_cost`/`base_unit_cost` baru (kapitalisasi) `:305-309` + mutasi `repair_receive` `:310`; `repair_history` `$push`; `rebuild_balance` `:312-313`; **JE** bila biaya>0: Dr 1-1300 Persediaan / Cr 2-1100 Hutang (makloon) atau Cr Overhead diserap (internal) `:315-322` lewat `gl._insert_entry` langsung (**tanpa `_already_posted`**); RO `lines`=hasil, `actual_cost`, `journal_id` `:326-328`; `gate_txn_service.safe_close("repair_order", …, ("out","in"))` `:329-330`; `audit("repair_order_received")` router `:142-143` | **Tidak ada** reversal/koreksi untuk `done` (cancel menolak `done` `:222`) | Ulang berurutan → 400 (`:246`). **Bersamaan: tidak** (lihat REP-01) | JE `entity_id=ro.entity_id` `:322`; roll anak mewarisi owner/gudang induk |
| R4 | `draft` → `cancelled` | `POST /api/repair-orders/{id}/cancel` `routers/repair_orders.py:147-157` (izin `cancel`; `ReasonIn` min 5 `:71-72`) → `svc.cancel` `repair_order_service.py:219-238` | cek baca `status ∈ {draft,sent}` `:222`; CAS `_push(..., ro["status"])` `:238` | `cancel_reason`, timeline; `audit("repair_order_cancelled", reason)` router `:155-156`. Roll tak berubah (tak pernah dikunci) | n/a | Ya (CAS) | — |
| R5 | `sent` → `cancelled` | idem | idem; roll dikembalikan dengan filter `{id, repair_open: ro.id}` `:229-231` (tanpa status) | roll → `prev_status`, `bucket_ref None`, `repair_open ""` `:231`; mutasi `repair_cancel` `:234`; `rebuild_balance` `:236-237`. **Tidak** memanggil `gate_txn_service.safe_close` (bandingkan R3 `:329-330`); **tidak** mensyaratkan bukti barang kembali (gate IN/handheld) | n/a (ini pembalik R2) | Ya (CAS akhir) | — |

**Status roll selama perbaikan** (tidak ada `repair`/`in_repair`/`subcon` — yang dipakai `wip`):
`available|quarantine|damaged|blocked|hold` → (R2) `wip` + `repair_open` + `bucket_ref.type=repair` → (R3) `available`
(panjang = qty_out, grade & lot baru, unit_cost naik) | `consumed` (qty_out=0, atau induk celup-ulang) + roll anak
`available` | (R5) `prev_status`. Panjang & grade **berubah** di R3 (`:306-307`). Biaya perbaikan **dikapitalisasi**
ke `unit_cost` roll hasil (`:271-274`) dan dijurnal (`:315-322`). `wip` = bucket FISIK di gudang (`roll_service.py:210`),
bukan OFFSITE seperti `subcon` (`roll_service.py:218-220`).

**Lewat logistik / gate?** Tidak ada surat jalan atau dokumen logistik; R2 langsung mengubah status roll. Gate RFID OUT/IN
**mendukung** sumber `repair_order` (sesuai K-GDG-02 `docs/rfid/KEPUTUSAN_GATE_RFID.md:141`), tetapi hanya sebagai
validasi pasca-status (sesi K-RFID-10 dinilai saat R3 `:329-330`); R3 tidak mensyaratkan lintasan gate IN, dan R5 tidak
menutup sesi.

---

## (a2) RETUR KE SUPPLIER — `purchase_returns`

Field status: **`status`** (header; mesin TIDAK ada di `purchase_return_state.py` — hanya docstring `purchase_return_service.py:10`
"draft → pending_approval → approved | rejected"), **`supplier_status`** (mesin `purchase_return_state.py:44-50`),
**`gl_status`**, `stock_adjusted`, `ap_adjusted`, `saga_lock` (`services/atomic_claim.py:24-56`). Router
`routers/purchase_returns.py`; semua aksi dokumen dijaga `_guard` `:18-22` (`guard_doc` strict = PT AKTIF,
`entity_scope.py:473-487`). Izin `permissions_config.py:83,225` (admin, manager: view,create,update,approve,reject) +
`decide_rolls` `:672-675`; warehouse/warehouse_admin hanya view,create (`:436,536`). Catatan: hapus & ajukan memakai
izin `update`; kirim/terima/tolak-supplier/barang-kembali/reverse memakai `approve`.

### Tabel B1 — header `status`

| # | dari → ke | pemicu | penjaga / CAS | efek | dibalik? | idempoten? | pagar PT / lokasi |
|---|---|---|---|---|---|---|---|
| P1 | (baru) → `draft` / `pending_approval` (`submit_now`) | `POST /api/purchase-returns` `routers/purchase_returns.py:71-85` (izin `create`) → `create_purchase_return` `purchase_return_service.py:48-210` (insert `:200`; status `:181`) | validasi baca: supplier/PO ada, gudang wajib, kebijakan impor `:82-87`, qty ≤ sisa roll `:117-120`. **Pilihan `roll_ids` tidak disaring owner/status** `:112-113`; roll tidak dikunci | dokumen (items, total, PPN tarif PO `:164,176-177`, `supplier_flow`, `supplier_status`=`requested_supplier` bila RMA `:185`, `stock_adjusted False`); `doc_refs` `reverses` PO `:202-204`; tautan rantai retur antar-PT `:209`, `:213-261` (update id-saja `:250-254`); `audit("purchase_return_created")` router `:83-84`. Roll/saldo/GL: tidak ada | n/a | Tidak (POST ganda = 2 dokumen) | `entity_id` = body (dicek penugasan hanya **bila diisi**, router `:74-76`) **atau PT PO** `:70-71` **atau** PT aktif `:62`; gudang **tidak** divalidasi (tak ada `whscope`) |
| P2 | (baru) → `pending_approval` + `stock_adjusted:True` (retur QC) | `POST /api/inbound/tasks/{task_id}/qc-decision` disposisi `return` (`routers/inbound_receiving_extra.py:134`) → `qc_service.process_qc_decision` `:432-442` → `_create_qc_return` `qc_service.py:144-205` (insert `:200`) | tidak ada; dokumen dibuat **sebelum** roll dipindah (`:433` lalu `:434`) | dokumen `source: qc_reject`, `status pending_approval`, **`stock_adjusted True`** `:193-194`, baris **tanpa `roll_ids`** `:181-188`, **tanpa `supplier_flow`/`supplier_status`**; roll karantina → `returned_supplier` + `returned_ref` lewat `_consume_quarantine` `qc_service.py:47-110` dengan mutasi `movement_type: qc_reject_return` **tanpa field `type`** `:91-107`; `doc_refs` PO `:202-204` | **Tidak** (lihat PRT-01/02) | n/a | `entity_id` = PT PO atau **`DEFAULT_ENTITY_ID`** `:180` (pemilik roll = `task.owner_entity_id` `:286`) |
| P3 | `draft` → `pending_approval` | `POST /{id}/submit` router `:115-124` (izin **`update`**) → `submit_purchase_return` `:264-273` | cek baca `status=="draft"` `:268`; **update filter id-saja `:270` (tanpa CAS, tanpa cek `saga_lock`)** | `submitted_at/by`; `audit("purchase_return_submitted")` | n/a | Ulang berurutan → 400; bersamaan dengan reject/approve: menimpa (PRT-05) | `_guard` |
| P4 | `draft`/`pending_approval` → `approved` (RMA) | `POST /{id}/approve` router `:127-138` (izin `approve`, body `PurchaseReturnDecision`) → `approve_and_adjust_stock` `:276-307`, cabang RMA `:296-303` | cek baca `:292-293`; **update id-saja `:298`** | `approved_by/at`, `decision_notes`, `supplier_status` tetap `requested_supplier` `:301`. Roll/DN/GL: belum | **Tidak ada jalan batal** dari sini (PRT-11a) | Ulang → 400 (`:292`) | `_guard` |
| P5 | `draft`/`pending_approval` → `approved` (DIRECT) | idem → `_finalize_supplier_return_financials` `:310-408` (dipanggil `:306-307`) | `preflight_posting` `:319`; **klaim saga** `precondition stock_adjusted≠True` `:324-325` (satu pemenang, lainnya 409); CAS roll per potongan `:868-873` (utuh) / `:878-882` (sebagian, `$expr` panjang bebas); gagal → `_undo_return_effects` + `release` `:332-335`; **tulisan akhir id-saja `:342`** (sekalian `$unset saga_lock`) | roll utuh → `returned_supplier` + `returned_ref` + `returned_from_status` `:872`; sebagian → induk dikurangi + roll anak `returned_supplier` via `insert_child_roll` `:885-888`; mutasi `return_out` qty negatif `direction:out` `:891-900`; `rebuild_balance` `:338-339`; DN `debit_note_number` (nomor atomik `:42-45`) `:341`; header `approved`, `stock_adjusted`, `supplier_status accepted_supplier`, `supplier_outcome`, `gl_status pending` `:342-350`; AP: `ap_adjusted` lalu PO `returned_amount += grand_total` + `recompute_po_payment_status` `:357-367` (**di luar try**); GL `post_purchase_return` `:372-379` (Dr GRIR/Hutang atau Kas / Cr 1-1300 net + Cr PPN Masukan, `gl_service.py:2441-2476`, idempoten `_already_posted` `:2451`); gagal → `gl_status failed` + 400 `:380-383`; `gl_status posted|not_required` `:386-388`; refund → `cash_ledger.record_return_cash` `:390-406` (galat ditelan `:403-406`); `audit("purchase_return_approved")` router `:136-137` | Ya, oleh P12 (reverse) | Stok: ya (klaim + `stock_adjusted`); AP: ya (`ap_adjusted`); GL: ya (`_already_posted`) | roll wajib milik PT retur & produk baris `:845-850`; FIFO tanpa `roll_ids` dibatasi gudang retur `:855` |
| P6 | `approved`+`gl_status failed` → `approved`+`posted` | `POST /{id}/approve` lagi → cabang ulang `:288-291` | cek baca; tanpa klaim (stok dilewati karena `stock_adjusted`) | ulang hanya DN/AP/GL; **akun refund jatuh ke `1-1100`** (`:374`; akun pilihan baru disimpan `:400-402`) | — | GL idempoten; bersamaan: cek-lalu-sisip `_already_posted` tidak atomik | `_guard` |
| P7 | `draft`/`pending_approval` → `rejected` | `POST /{id}/reject` router `:141-151` (izin `reject`) → `reject_purchase_return` `:690-701` | cek baca `:694`; **update id-saja `:697`** | `rejected_by/at`, `reject_reason`; `audit`. **Tidak** menyentuh roll (retur QC tetap `returned_supplier`), `supplier_status`, tautan retur jual, `doc_refs` | — | Ulang → 400 | `_guard` |
| P8 | `draft`/`pending_approval` → `rejected` (semua roll ditolak) | `POST /{id}/roll-decisions` router `:190-202` (izin `decide_rolls`, body `ReturnRollDecisionsIn`) → `decide_rolls` `:508-529` | cek baca `:515`; **CAS `{id, status: ret.status}` `:526`** | baris dihitung ulang `_retotal` `:496-505`, roll ditolak keluar dari `roll_ids` (`return_rolls_service.py:205-225`), `roll_decision_log`; semua 0 → `rejected` `:523-525`; `audit` | — | Ya (CAS) | `_guard` |
| P9 | `draft`/`pending_approval` → sama (sebagian roll ditolak) | idem | idem | idem tanpa ganti status | — | Ya | `_guard` |
| P10 | `draft` → (dihapus) | `DELETE /api/purchase-returns/{id}` router `:312-323` (izin **`update`**) → `delete_purchase_return` `:675-687` | cek baca `status=="draft"` `:680`; **`delete_one({"id"})` `:686` tanpa CAS & tanpa cek `saga_lock`** | `doc_refs.safe_unlink_all` `:685`; hapus dokumen; `audit("purchase_return_deleted")` | — | Ulang → 400 "tidak ditemukan" | `_guard` |
| P11 | (retur jual) → `pending_approval` + RMA (1..n dokumen) | `POST /api/sales-returns/{id}/create-purchase-return` (`routers/sales_returns.py:1017-1050`, izin `purchase_return.create`) atau disposisi per roll `return_disposition_service.py:349` → `create_from_sales_return` `:706-810` | cek baca tautan `:718-720`; **klaim saga pada `sales_returns`** `:779-780` | per supplier/PO asal: `create_purchase_return(submit_now=True, supplier_flow=True)` `:769-775`; `origin_sales_return_number` `:789-791`; `sales_returns.linked_purchase_return_id/_number/linked_purchase_returns` `:800-803` | tautan **tidak pernah dilepas** (P7/P12) | Ya (klaim; ulang → 400 `:718`) | PT = pemilik roll (LN-093) `:731-733`, bisa berbeda dari PT pembuat |
| P12 | `approved` (+`stock_adjusted`, `accepted_supplier`) → `cancelled` | `POST /{id}/reverse` router `:292-309` (izin `approve`) → `reverse_settlement` `:965-1098` | idempoten bila `reversed`/`cancelled` `:984-985`; guard `stock_adjusted` & `supplier_status==accepted_supplier` `:986-990`; roll sumber harus ada `:1010-1016`; **klaim saga** `:1022-1024`; tulisan akhir `finish_set` `:1089-1092` | JE dibalik `gl_service.reverse_document` `:1026-1028`; roll dari mutasi **`type: return_out`** `:997-999`: `returned_supplier` → **`available`** `:1039-1043` (bukan `returned_from_status`), selain itu `$inc length` `:1044-1048`; mutasi `return_out_reversal` `:1049-1060`; `rebuild_balance` `:1064-1065`; PO `returned_amount −= grand_total` `:1068-1079`; refund → `cash_transactions` void `:1082-1086`; header `cancelled`, `reversed`, `debit_note_voided`, `stock_adjusted False` (`supplier_status` **tetap** `accepted_supplier`); `audit("purchase_return_reversed")` | — | Ya | `_guard` |

### Tabel B2 — `supplier_status` (mesin `purchase_return_state.py:44-50`)

| # | dari → ke | pemicu | penjaga / CAS | efek | dibalik? | idempoten? | pagar PT / lokasi |
|---|---|---|---|---|---|---|---|
| S1 | `""` → `accepted_supplier` (DIRECT) | P5 `:347` | **melompati** `assert_transition` (SUP_NONE tak punya kunci di `TRANSITIONS`) | lihat P5 | P12 | ya | — |
| S2 | `requested_supplier` → `shipped_supplier` | `POST /{id}/ship-to-supplier` router `:156-169` (izin `approve`, body `SupplierShipInput`) → `ship_to_supplier` `:428-470` | `supplier_flow` `:436`, `status=="approved"` `:438`, `assert_transition(… or REQUESTED, SHIPPED)` `:440`; **klaim saga** `precondition supplier_status≠SHIPPED` `:443-444`; CAS roll `{status:available, length_reserved≯0, active_movement None}` `:454-456` | roll `available` → **`quarantine`** + `supplier_return_ref` `:457-459` (roll lain **dilewati diam-diam**: beda PT `:451-452`, dipesan/diklaim `:455-456`, status bukan available `:453`); `rebuild_balance` `:462-464`; `claim_window_check` `:466`; header `shipped_at/by`, `carrier`, `tracking_no` `finish_set` `:467-469`; **tanpa mutasi stok, tanpa surat jalan**; `audit` router `:167-168` | **tidak** ada pembalik langsung; lewat S5+S6 | ya (klaim + `assert_transition`) | owner dicek per roll `:451` |
| S3 | `shipped_supplier` → `accepted_supplier` | `POST /{id}/supplier-accept` router `:172-187` (izin `approve`, body `SupplierAcceptInput`) → `supplier_accept` `:473-493` → P5 finalisasi | `assert_transition` baca `:488`; klaim saga di finalisasi (`stock_adjusted≠True`) | lihat P5 (konsumsi roll `quarantine`/`available` `RETURNABLE_STATUSES` `:829`) | P12 | ya | idem P5 |
| S4 | `shipped_supplier` → `accepted_supplier` sebagian | idem dengan `rejected_rolls` → `_apply_supplier_rejections` `:532-557` lalu P5 | CAS `{id, supplier_status: SHIPPED}` `:554` (ditulis **sebelum** finalisasi) | roll ditolak keluar dari baris, `supplier_rejected_rolls[]` (goods_back_at "") `:547-550`, `supplier_partial`; lalu P5 untuk sisanya | — | sebagian (lihat PRT-17) | — |
| S5 | `shipped_supplier` → `rejected_supplier` | `POST /{id}/supplier-reject` router `:255-266` (izin `approve`, body `SupplierRejectInput`) → `supplier_reject` `:626-638` | `assert_transition` baca `:633`; **update id-saja `:635`, tanpa cek `saga_lock`/`stock_adjusted`** | `supplier_rejected_at/by/reason`; roll tetap `quarantine`; `audit` | — | ulang berurutan → 400; bersamaan dengan S3: menimpa (PRT-05a) | `_guard` |
| S6 | `rejected_supplier` → `goods_back` | `POST /{id}/goods-back` router `:269-287` (izin `approve`, body `GoodsBackInput`; gudang dicek `whscope.assert_usable` `:275-279`) → `goods_back` `:641-672` | `assert_transition` `:650`; **klaim saga** `supplier_status≠GOODS_BACK` `:654-655` | **semua** `items[].roll_ids` → `_roll_back_to_stock` `:593-623`: `status available`, `warehouse_id`, `supplier_return_ref None`, regrade (`grade`, `regraded_from`) **update id-saja tanpa cek status `:606`**; mutasi `goods_back direction:in` `:607-617`; rebuild asal & tujuan `:618-622`; header `goods_back_at/by`, `goods_back_regraded` `:669-671`. Tanpa jurnal. **Header `status` tetap `approved`** | — | ya (klaim) | gudang tujuan dicek di router; owner roll tidak |
| S7 | `supplier_rejected_rolls[].goods_back_at` `""` → waktu | `POST /{id}/supplier-rejected-goods-back` router `:205-223` (izin `approve`) → `supplier_rejected_goods_back` `:560-590` | **tanpa cek `supplier_status`/`status`**; klaim saga `$elemMatch goods_back_at ""` `:571-572` | `_roll_back_to_stock` per roll tertunda `:577-579` (sama: tanpa cek status); `finish_set` `:586-589` | — | ya (klaim) | idem S6 |

`gl_status`: (tidak ada) → `pending` `:349` → `failed` `:381` | `posted`/`not_required` `:386-388`; `failed` → P6.
Pembaca: hanya `:288` dan `routers/posting_failures.py:20` (keduanya hanya `failed`). **`pending` tak punya pembaca/jalan keluar.**

`saga_lock`: P5 `:324` (lepas `:334` atau `$unset` `:342`), S2 `:443`/`:467`, S7 `:571`/`:586`, S6 `:654`/`:669`,
P12 `:1022`/`:1089`, P11 (di `sales_returns`) `:779`/`:794`/`:800`. **P3, P4, P7, P10, S5, P6 tidak memeriksa `saga_lock`.**

**Status roll retur supplier:** `available|quarantine` → `returned_supplier` (terminal, di luar semua bucket —
`purchase_return_service.py:26`, `roll_service.py:203-230`) [P5/S3]; `available` → `quarantine`+`supplier_return_ref`
[S2]; apa pun → `available` (+regrade, +pindah gudang) [S6/S7]; `returned_supplier` → `available` [P12]; QC:
`quarantine` → `returned_supplier` [P2]. Debit note **bukan koleksi terpisah** — hanya `debit_note_number` +
`debit_note_voided` di dokumen. Tidak ada `status_history`/`timeline` di retur beli (hanya `roll_decision_log`), tidak ada
notifikasi; `audit()` tiap endpoint sesudah service sukses.

**Bandingkan `purchase_return_state.py`:** `SUPPLIER_TERMINAL`, `is_terminal`, `can_transition` (`:28,53-55,65-66`)
**tidak dipakai di luar modul** (grep); `SUP_NONE` tidak punya kunci di `TRANSITIONS` sehingga `assert_transition('', …)`
selalu gagal — `ship_to_supplier` menambalnya dengan `or REQUESTED` (`:440`) dan DIRECT menulis `ACCEPTED` langsung
(`:347`). Header `status` sama sekali tak punya mesin/CAS terpusat.

**Lewat logistik / gate?** Tidak. DIRECT: roll menjadi `returned_supplier` **saat persetujuan** (barang fisik masih di
gudang). RMA: roll menjadi `quarantine` saat "dikirim" (barang fisik di supplier tapi tetap `on_hand`). Tak ada surat
jalan (hanya `carrier`/`tracking_no` di S2). Gate OUT tidak mengenal sumber `purchase_return`
(`rfid_v2_sources.py:16`), sehingga roll RMA → MERAH `QUARANTINE` (`gate_evaluator.py:144`) dan roll DIRECT/QC → MERAH
`NO_DOCUMENT` (`gate_evaluator.py:153`). K-GDG-02 (`docs/rfid/KEPUTUSAN_GATE_RFID.md:141`) menyebut gate OUT memvalidasi
"SJ, transfer, makloon, perbaikan" — retur supplier tidak disebut → **butir terbuka (STOP & ASK pemilik)**.
KN_16 §3 (`docs/KN_16_END_TO_END_PROCESS_FLOWS.md:130`) hanya "kebalikan GRN (kurangi roll, debit note)" (blindspot G12
`:302`); §7 (`:177-193`) tak memuat `wip`/`returned_supplier`/`consumed`.

---

## (b) KANDIDAT ANOMALI

### Perbaikan

**REP-01 — Terima hasil ganda bersamaan: jurnal & roll anak dobel** · `repair_order_service.py:246, 268, 296, 319-322, 324-328` · **perlu runtime** · tinggi
Penalaran: cek status hanya baca (`:246`); roll dicari dengan `repair_open` (`:268`) yang baru dikosongkan saat update
roll; CAS dokumen di AKHIR (`:324-328`); `_insert_entry` dipanggil tanpa `_already_posted`. Dua POST `/receive` yang
bertumpuk bisa sama-sama melewati `:268` → dua roll anak (celup ulang), mutasi `repair_loss/receive` ganda, dua JE
kapitalisasi; yang kalah CAS mendapat 400 **sesudah** jurnalnya terposting.
Dampak: GL Persediaan & Hutang mitra lebih besar dari nyata; stok roll anak ganda.

**REP-02 — Kegagalan sesudah roll ditulis meninggalkan dokumen setengah jadi tanpa jalan ulang** · `repair_order_service.py:241-322` (tanpa `preflight_posting`), `gl_service.py:629-630` (cek periode di dalam `_insert_entry`), `:268-270`, `:229-231` · **pasti dari kode (urutan), konfirmasi runtime** · tinggi
Penalaran: semua roll sudah `available`/`consumed`, panjang/grade/unit_cost diganti, mutasi ditulis, lalu JE ditolak
(periode tertutup `ClosedPeriodError`, validasi akun `_validate_entry_lines`, atau `DuplicateKeyError` roll_no anak
`-C` — `inventory_rolls.roll_no` unik `indexes.py:372`). RO tetap `sent`; terima ulang gagal karena `repair_open` sudah
kosong (`:268-270` "tidak lagi tercatat"); batal (`:229-231`) tak menyentuh roll yang sudah diterima → RO `cancelled`
padahal roll membawa hasil perbaikan & biaya kapitalisasi tanpa jurnal. Bandingkan retur beli yang memanggil
`preflight_posting` sebelum efek (`purchase_return_service.py:319`).
Dampak: subledger (unit_cost naik) ≠ GL; dokumen macet.

**REP-03 — Perbaikan di mitra makloon tetap dihitung stok fisik gudang** · `repair_order_service.py:4-5, 25, 200`; `roll_service.py:210, 218-220` · **pasti dari kode** · sedang
Penalaran: docstring "fisik dicatat di mitra bila eksternal", tetapi status `wip` dipakai untuk internal **dan**
makloon; `wip` = bucket FISIK (`on_hand`), sedangkan barang di vendor makloon memakai `subcon` (OFFSITE). Rujuk STK-6/7.
Dampak: `on_hand` gudang memuat barang yang ada di mitra; opname selisih; gate IN "LOCAL_ROLL".

**REP-04 — CAS kirim tidak menolak reservasi potong / klaim putaway yang muncul sesudah draf** · `repair_order_service.py:74, 197-199`; `roll_service.py:587-594` (`_reserve_length` tak mengisi `reserved_ref`); pembanding `stock_bucket_service.py:249-251` · **pasti dari kode (filter), dampak perlu runtime** · sedang
Penalaran: `length_reserved` hanya dicek saat buat (`:74`); draf tidak mengunci roll. Reservasi potong SO atau klaim
`active_movement` PA pada roll di antara buat→kirim lolos CAS kirim → roll `wip` membawa `length_reservations`; celup
ulang menutup induk (`consumed`) yang masih memegang reservasi → reservasi yatim (= pola SSOT-8, DUP-4).
Dampak: SO menunggu potongan dari roll di perbaikan/yang sudah habis; PA mengklaim roll yang pergi ke mitra.

**REP-05 — Perbaikan menjadi jalan pintas lepas karantina/tahanan** · `repair_order_service.py:24, 40, 71, 305-309`; `services/roll_hold_service.py:3-6, 33-37, 48-58` · **pasti dari kode** · tinggi
Penalaran: roll `quarantine` (QC belum diputus, `qc_task_id`), `blocked` (tahanan, `hold.held=True`) boleh dikirim;
terima hasil selalu menulis `status: available` tanpa menyentuh `hold`, `inspection.hold`, `qc_task_id`. Pelepasan
tahanan seharusnya hanya oleh pemegang izin inspeksi (keputusan pemilik #5, `permissions_config.py:218-219`). Roll
karantina RMA (S2, fisik di supplier) juga lolos (lihat PRT-04).
Dampak: barang tahanan/karantina tersedia dijual tanpa keputusan QC; `hold.held` tetap True pada roll `available`.

**REP-06 — Batal dari `sent` tidak menutup sesi gate & langsung memulihkan stok tanpa bukti barang kembali** · `repair_order_service.py:219-238` vs `:329-330` · **pasti dari kode** · sedang
Penalaran: R5 mengembalikan roll ke `prev_status` (mis. `available`) seketika; tidak memanggil
`gate_txn_service.safe_close`. Bila roll sudah lewat gate OUT ke mitra, sistem menampilkan stok tersedia padahal fisik
di luar; sesi `rfid_v2_doc_sessions` OUT dokumen itu tak pernah dinilai.
Dampak: ATP semu; sesi gate menggantung.

**REP-07 — Nilai persediaan hilang/bertambah tanpa jurnal** · `repair_order_service.py:271-274, 282-286, 315-322` · **pasti dari kode** · sedang
Penalaran: qty_out=0 → roll `consumed` (nilai `length×unit_cost` keluar subledger) tanpa jurnal rugi; bila semua qty_out=0
dan biaya>0 → `alloc=0` (`:272`) tetapi JE Dr Persediaan tetap diposting (`:315-322`) tanpa roll penampung.
Dampak: GL Persediaan ≠ subledger roll.

**REP-08 — Roll anak celup ulang dibuat mentah: mewarisi tag RFID & atribut induk** · `repair_order_service.py:288-296`; pembanding `roll_service.py:105-145` (`insert_child_roll`: `rfid_tag_id=None` `:122-124`, buang reservasi/klaim `:117-118`, `root_roll_id` `:130-131`, nomor via `child_roll_no` + ulang DuplicateKey `:133-145`) · **pasti dari kode; efek tag ganda perlu runtime** · sedang
Penalaran: `{**roll}` menyalin `rfid_tag_id`, `weight_kg` penuh, `earmarked_for`, `active_movement`, `inspection`,
`hold`; `roll_no` tetap `X-C` tanpa ulang. Dua roll (induk `consumed`, anak `available`) ber-tag sama
(`rfid_tag_id` tidak unik, `indexes.py:37`). Rujuk SCH-4.
Dampak: gate/handheld bisa membaca tag → roll induk `consumed` → MERAH `ALREADY_OUT` (`gate_evaluator.py:146`).

**REP-09 — Status `done` tanpa koreksi/reversal** · `repair_order_service.py:23, 222` · **pasti dari kode** · rendah
Salah isi qty hasil/grade/biaya tidak bisa dibalik (tak ada endpoint), berbeda dengan retur beli (P12).

**REP-10 — Pagar PT/gudang** · `routers/repair_orders.py:160-164`, `repair_order_service.py:344-347`; `:58-79`, `:197-199` · **pasti dari kode** · rendah
`GET /api/inventory/rolls/{roll_id}/repairs` hanya izin `product.view`, tanpa cek entitas → nomor RPR, mitra, label
lintas PT terbaca. Buat/kirim tidak memeriksa gudang roll terhadap cakupan gudang pengguna (tak ada
`whscope`/`location_scope`); CAS kirim tidak memuat `owner_entity_id`.

**REP-11 — Draf tidak mengunci roll; `qty_sent` basi** · `repair_order_service.py:42, 76, 134, 211, 255` · **pasti dari kode** · rendah
Dua draf bisa memuat roll yang sama (hanya satu bisa dikirim). `qty_sent` = panjang saat buat; bila panjang berubah
sebelum kirim (opname/penyesuaian), mutasi `repair_send` dan batas qty_out memakai angka basi sedangkan `old_val`
memakai panjang terkini (`:271`).

**REP-12 — Mutasi perbaikan tanpa arah & bernomor teknis** · `repair_order_service.py:180-185`; `services/movement_label_service.py` `_PREFIX_MAP` (tak ada `rpr_`) · **pasti dari kode** · rendah
Semua qty positif tanpa `direction` (kirim/terima/susut/batal); `source_document` = id `rpr_…` tak diterjemahkan →
Kartu stok tak dapat membedakan keluar/masuk. Rujuk SCH-6.

**REP-13 — Hutang mitra dicatat di jurnal perbaikan DAN (direncanakan) lewat Vendor Bill** · `repair_order_service.py:9-11, 318` · **perlu runtime** · sedang
Receive memposting Cr 2-1100 langsung tanpa dokumen hutang; docstring menyebut tagihan mitra "memakai Vendor Bill yang
ada". Bila Vendor Bill mitra diposting juga ke 2-1100, hutang ganda; tak ada tautan `journal_id` ↔ tagihan. Cek alur
posting Vendor Bill makloon.

### Retur ke supplier

**PRT-01 — Retur QC yang ditolak: roll tetap `returned_supplier`, stok tak kembali** · `qc_service.py:193-194, 432-442`; `purchase_return_service.py:690-701` · **pasti dari kode** · tinggi
Penalaran: retur QC lahir `pending_approval` + `stock_adjusted True` dengan roll SUDAH `returned_supplier`. `reject`
hanya menulis status; tak ada pemulihan roll/mutasi; `reverse` menolak (butuh `accepted_supplier`, `:986`).
Dampak: barang keluar subledger permanen tanpa DN/AP/GL → GL Persediaan > subledger; tidak ada jalur UI untuk
memulihkannya.

**PRT-02 — Reverse retur QC tidak memulihkan roll tetapi membalik jurnal & AP** · `purchase_return_service.py:997-999, 1031-1065`; `qc_service.py:91-107` · **pasti dari kode** · tinggi
Penalaran: reverse mencari mutasi `type: "return_out"`; mutasi QC hanya punya `movement_type: "qc_reject_return"`
(tanpa `type`) → `restored=0`, guard roll lolos kosong; JE dibalik (Dr Persediaan kembali), PO `returned_amount`
dipulihkan, header `cancelled`, `stock_adjusted False`.
Dampak: GL Persediaan naik tanpa roll; roll tetap `returned_supplier`.

**PRT-03 — "Barang kembali" menghidupkan roll apa pun tanpa cek status** · `purchase_return_service.py:593-606, 662-664, 577-579`; `:451-459` · **pasti dari kode (filter), dampak runtime** · tinggi
Penalaran: `_roll_back_to_stock` menulis `status: available` dengan filter `{"id"}` saja; S6 memproses SEMUA `roll_ids`
baris, termasuk roll yang tidak dikarantina saat kirim (dilewati diam-diam: dipesan, beda PT, `blocked`/`damaged`) dan
roll yang sesudahnya terjual (`in_transit_sales`/`delivered`), dikonsumsi retur beli lain (`returned_supplier`),
dikirim ke perbaikan (`wip`), atau ditahan. Semua menjadi `available` (+ mutasi `goods_back` masuk).
Dampak: stok hantu; pelepasan tahanan; konflik dengan RO/SO yang masih memegang roll.

**PRT-04 — Penanda RMA `supplier_return_ref` tulis-saja; roll di supplier tetap terbuka untuk alur lain** · `purchase_return_service.py:458, 600` (satu-satunya penulis/pembaca, grep); `repair_order_service.py:24`; `:829`; `:722-724` · **pasti dari kode** · sedang
Roll RMA `quarantine` bisa dipilih Perbaikan, retur beli lain (`RETURNABLE_STATUSES`), retur dari retur jual, atau
dilepas karantina/ditahan, karena tak ada modul yang membaca penanda. Kombinasi dengan PRT-03/REP-05 menghasilkan
status saling timpa. Selain itu roll asal `quarantine` (mis. dari retur jual) **tidak** diberi penanda sama sekali
(`:453` hanya `available`).

**PRT-05 — Transisi header/supplier tanpa CAS & tanpa cek `saga_lock`** · `purchase_return_service.py:270, 298, 342, 635, 686, 697`; `:292` (approve DIRECT boleh dari `draft`) · **perlu runtime** · tinggi
(a) `supplier-accept` ∥ `supplier-reject` pada `shipped_supplier`: S5 menimpa `ACCEPTED` → dokumen `rejected_supplier`
padahal `stock_adjusted`, DN, JE sudah ada → S6 menghidupkan roll `returned_supplier` (PRT-03) dan P12 menolak (`:986`).
(b) `approve` (DIRECT dari draf, banyak roll) ∥ `DELETE`: hapus tidak melihat `saga_lock` → dokumen hilang, roll
`returned_supplier` + mutasi `return_out` yatim, PO `returned_amount` sudah naik (`:359-365`, filter PO id), `fresh=None`
→ GL gagal. (c) `submit` ∥ `reject`/`approve`: status "hidup lagi" (`rejected`→`pending_approval`, atau `approved`
+`stock_adjusted`→`pending_approval` lalu bisa `reject`).
Dampak: jurnal/AP/stok tak konsisten dengan header.

**PRT-06 — `gl_status: pending` yatim** · `purchase_return_service.py:349, 357-367, 288, 292-293`; `routers/posting_failures.py:20` · **pasti dari kode (struktur), pemicu runtime** · sedang
`recompute_po_payment_status` (`:366-367`) dan update AP di luar `try`; galat atau proses mati di sana meninggalkan
`approved`+`stock_adjusted`+`gl_status pending` tanpa JE. Jalur ulang (`:288`) & daftar kegagalan posting hanya untuk
`failed`; approve ulang ditolak "sudah approved".
Dampak: DN & AP berjalan, GL tidak pernah diposting, tak terlihat di layar kegagalan posting.

**PRT-07 — Refund: akun pilihan hilang saat ulang; kegagalan buku kas ditelan** · `purchase_return_service.py:374, 400-402, 403-406, 288-291` · **pasti dari kode** · sedang
`refund_account_code` baru disimpan sesudah GL & kas sukses; ulang lewat approve memakai `1-1100`. Galat
`record_return_cash` hanya di-log → JE Dr Kas tanpa transaksi kas.

**PRT-08 — Reverse memulihkan roll ke `available`, bukan status asal** · `purchase_return_service.py:872, 1039-1043` · **pasti dari kode** · sedang
`returned_from_status` disimpan tetapi tidak dipakai; roll cacat dari `quarantine` menjadi siap jual; `supplier_return_ref`
tak dibersihkan.

**PRT-09 — Tolak/reverse tidak melepas tautan retur jual; disposisi bertahap terblokir** · `purchase_return_service.py:718-720, 800-803, 690-701, 965-1098`; `services/return_disposition_service.py:349` · **pasti dari kode (cek), alur UI perlu runtime** · sedang
`linked_purchase_return_id` tak pernah dikosongkan → retur jual tak bisa diteruskan ulang sesudah retur beli
ditolak/dibatalkan; disposisi `supplier_return` per roll batch ke-2 dari retur jual yang sama ditolak `:718`.
`doc_refs` juga tidak dilepas (hanya `delete` `:685`).

**PRT-10 — Pagar PT di pembuatan retur** · `purchase_return_service.py:62-71, 112-113, 131-134`; `routers/purchase_returns.py:74-76`; `qc_service.py:180` vs `:286` · **pasti dari kode** · sedang
Tanpa `entity_id` di body, `po_id` PT lain menjadikan retur milik PT itu tanpa cek penugasan; `roll_ids` tak disaring
owner/status → meta roll PT lain (nomor, lot, invoice supplier, PO) ikut di respons; gudang tak divalidasi. Retur QC
tanpa PO jatuh ke `ent_ksc` walau pemilik roll PT lain. (Tindakan lanjut terhadang `_guard` strict.)

**PRT-11 — Status yatim / tak konsisten terhadap `purchase_return_state.py`** · `purchase_return_service.py:296-303, 680, 694, 986, 669-671, 697-700, 347, 1089-1092`; `purchase_return_state.py:44-50`; `services/supplier_service.py:30, 238-243` · **pasti dari kode** · sedang
(a) RMA `approved`+`requested_supplier` tak bisa dibatalkan sebelum dikirim (reject/delete/reverse menolak).
(b) `goods_back` terminal tetapi header tetap `approved` selamanya → scorecard supplier menghitung qty-nya sebagai
"reject nyata" (`COUNTED_RETURN_STATUS_EXCLUDE` hanya cancelled/rejected/draft) padahal supplier menolak klaim; juga
`pending_approval` ikut terhitung. (c) Header `rejected` dengan `supplier_status requested_supplier`. (d) DIRECT
melompati mesin (`''→accepted`). (e) `is_terminal/can_transition/SUPPLIER_TERMINAL` tak dipakai; `SUP_NONE` tanpa
kunci. (f) Sesudah reverse: `cancelled` + `accepted_supplier`.

**PRT-12 — Retur supplier tidak lewat logistik/gate; kartu stok timpang** · `purchase_return_service.py:342-350, 448-464, 607-617`; `rfid_v2_sources.py:16`; `gate_evaluator.py:144, 153`; `docs/rfid/KEPUTUSAN_GATE_RFID.md:141` · **pasti dari kode; keputusan pemilik terbuka** · sedang
DIRECT: stok hilang saat persetujuan (fisik masih di gudang). RMA: `on_hand` memuat barang di supplier; kirim tanpa
mutasi keluar tetapi barang-kembali menulis mutasi masuk → kartu stok +qty tanpa −qty. Gate OUT selalu MERAH untuk
barang retur supplier. Perlu keputusan: retur supplier sebagai sumber gate OUT / surat jalan retur.

**PRT-13 — Kirim ke supplier melewati roll diam-diam** · `purchase_return_service.py:449-461` · **pasti dari kode** · sedang
Roll beda PT, dipesan, diklaim PA, atau bukan `available` tidak dikarantina dan tak ada galat/ringkasan; RMA tanpa
`roll_ids` tak mengunci apa pun. Dokumen "Dikirim" sementara roll tetap dapat dijual; finalisasi kemudian gagal "Stok tak
cukup" (`:907-910`) dan satu-satunya jalan keluar S5→S6 (PRT-03).

**PRT-14 — Cr Persediaan = harga dokumen, bukan nilai roll yang keluar** · `purchase_return_service.py:107, 122, 136-137`; `gl_service.py:2455, 2468` · **pasti dari kode; besaran runtime** · sedang
Harga dari klien diterima; harga roll berbobot hanya bila `price<=0`. Roll ber-`unit_cost` hasil kapitalisasi
perbaikan (REP) atau landed cost diretur pada harga PO → selisih tertinggal di 1-1300.

**PRT-15 — Reverse tidak memeriksa Nota Debit yang sudah dipakai kontrabon** · `purchase_return_service.py:965-1092`; `services/contra_bon_service.py:389-401`; `services/contra_bon_scan.py:170-190` · **perlu runtime** · sedang
DN `cancelled` sementara potongan di kontrabon tetap; scan kontrabon tidak menandai sumber `cancelled`. Catatan: plafon
potongan kontrabon = `total_amount` (net) sedangkan AP dikurangi `grand_total` (gross, `:354-355,364`).

**PRT-16 — Draf/pending tidak mengunci roll; approve dari `draft` lewat API** · `purchase_return_service.py:110-134, 292`; `frontend/src/features/purchasing/PurchaseReturns.jsx:518-530` · **pasti dari kode** · rendah
Roll di retur menunggu tetap dijual/dipakai; approve gagal belakangan. API mengizinkan approve langsung dari draf
(melompati `pending_approval`) sedangkan UI hanya menampilkan Setujui untuk `pending_approval`. Tak ada pemisahan pembuat
≠ penyetuju.

**PRT-17 — Terima sebagian ditulis sebelum finalisasi** · `purchase_return_service.py:490-493, 554, 560-572`; `services/return_rolls_service.py:176-179` · **perlu runtime** · rendah
Bila finalisasi gagal, baris sudah dikurangi & `supplier_rejected_rolls` tercatat sementara `shipped_supplier`; ulang
dengan `rejected_rolls` sama → 400 "sudah ditolak". S7 tak memeriksa `supplier_status` → roll tolakan bisa
"kembali" saat retur masih `shipped_supplier`.

**PRT-18 — Retur QC: dokumen dulu, roll kemudian; qty dokumen = qty diminta** · `qc_service.py:163-165, 184, 433-442, 110` · **perlu runtime** · rendah
Bila `_consume_quarantine` gagal/kurang, dokumen `stock_adjusted True` tetap ada (DN/AP/GL atas qty yang tidak keluar).

---

## (c) RESEP UJI RUNTIME

Prasyarat (jalankan oleh penguji, bukan audit ini): data acuan `bash scripts/dev_restore_demo.sh`; stack dev hidup.
Base `http://localhost:8001/api`. Login `POST /auth/login` body `{"email":"admin@kainnusantara.id","password":"<sandi demo — AGENTS.md>"}`
(model `LoginRequest` `schemas.py:161-163`) → ambil `token`; semua panggilan berikut memakai header
`Authorization: Bearer <token>` dan `X-Entity-Id: ent_ksc` (`entity_scope.py:377`). Admin memegang semua izin di atas.
Pemeriksaan DB = baca-saja (mongosh / `docker compose -f docker-compose.dev.yml exec mongo mongosh`), koleksi:
`repair_orders`, `purchase_returns`, `inventory_rolls`, `inventory_movements`, `inventory_balances`, `journal_entries`,
`purchase_orders`, `cash_transactions`, `sales_returns`, `rfid_v2_doc_sessions`, `audit_logs`, `doc_refs`.

### C1 — Perbaikan kirim → terima (alur dasar)
1. `GET /repair-orders/candidate-rolls?q=` → pilih 2 roll `available` (catat `id`, `length_remaining`, `grade`, `unit_cost`).
2. `POST /repair-orders` (model `RepairCreate` `routers/repair_orders.py:44-55`, `CostIn` `:37-41`):
   `{"kind":"perbaikan","partner_type":"internal","partner_id":"","roll_ids":["<R1>","<R2>"],"cost":{"basis":"lumpsum","rate":100000,"other_costs":[],"contract_id":""},"target_product_id":"","target_color":"","target_dye_lot":"","notes":"uji B2b","source_type":"","source_id":""}`
   → cek `repair_orders.status=draft`, `lines[].prev_status`; roll **tanpa** `repair_open` (REP-11).
3. `POST /repair-orders/{ro}/send` (tanpa body) → cek `inventory_rolls`: `status=wip`, `repair_open=<ro>`,
   `bucket_ref.type=repair`; `inventory_movements{source_document:<ro>, movement_type:"repair_send"}` 2 baris tanpa
   `direction` (REP-12); `inventory_balances.wip_qty` naik & masuk on_hand (REP-03 bila ulangi dengan `partner_type:"makloon"`,
   `partner_id` dari `GET /makloons`); `audit_logs{action:"repair_order_sent"}`.
4. `POST /repair-orders/{ro}/receive` (model `RepairReceive` `:65-68`, `ReceiveLine` `:58-62`):
   `{"lines":[{"roll_id":"<R1>","qty_out":<len1-0.5>,"grade":"B","dye_lot":""},{"roll_id":"<R2>","qty_out":0,"grade":"","dye_lot":""}],"actual_cost":100000}`
   → cek R1 `available`, panjang & grade baru, `unit_cost` naik; R2 `consumed`; mutasi `repair_loss` 2 + `repair_receive` 1;
   `journal_entries{source_type:"repair_order",source_id:<ro>}` = 1 (Dr 1-1300 100000); **REP-07**: bandingkan
   Σ nilai roll sebelum (len×unit_cost R1+R2) + 100000 dengan nilai R1 sesudah — selisih = nilai R2 yang hilang tanpa JE.
5. Batal: buat RO ke-2, kirim, lalu `POST /repair-orders/{ro2}/cancel` `{"reason":"uji batal B2b"}` (`ReasonIn` `:71-72`)
   → roll kembali `prev_status`, mutasi `repair_cancel`; **REP-06**: bila RO ke-2 sempat lewat gate OUT (atau ada dokumen
   `rfid_v2_doc_sessions` untuk `repair_order`/<ro2>), sesi tetap tanpa `close`.

### C2 — Kandidat perbaikan khusus
* **REP-01:** RO 1 roll, kirim, lalu kirim DUA `POST /receive` identik bersamaan (mis. dua `curl … &` lalu `wait`, atau
  `asyncio.gather` httpx). Bukti anomali: `journal_entries{source_type:"repair_order",source_id:<ro>}` > 1, atau
  `inventory_movements{source_document:<ro>,movement_type:"repair_receive"}` > jumlah roll; untuk `kind:"celup_ulang"` +
  `target_product_id` (dari `GET /repair-orders/target-products?q=..`) cek `inventory_rolls{parent_roll_id:<R>}` > 1.
* **REP-02 (berat):** kirim RO ber-biaya, tutup periode bulan berjalan `POST /finance/closing/close`
  `{"period_type":"month","period_key":"2026-11","entity_id":"ent_ksc","note":"uji REP-02"}` (`routers/closing.py:73`), lalu
  `POST /receive` → harapkan galat; cek roll sudah `available`/panjang baru, RO masih `sent`, tidak ada JE; ulang receive
  → 400 "tidak lagi tercatat". Buka lagi periode `POST /finance/closing/{id}/reopen` (`routers/closing.py:104`).
* **REP-04:** buat draf RO atas roll X; sebelum kirim, beri X reservasi potong lewat alokasi SO sebagian roll, atau klaim
  PA `POST /putaway-orders` `{"from_warehouse_id":..,"to_warehouse_id":..,"roll_ids":["X"]}` (`PACreatePayload`
  `routers/putaway_orders.py:21-24`; syarat `journey.stage` di `putaway_order_service.py:243-246`); lalu `POST /send`.
  Bukti anomali: 200 dan X `status=wip` dengan `length_reserved>0` atau `active_movement` terisi.
* **REP-05:** `POST /inventory/rolls/{X}/hold` `{"reason":"uji tahan REP-05"}` (`routers/qc_inspection.py:121`) → X `blocked`;
  buat RO atas X, kirim, terima dengan `qty_out` = panjang penuh. Bukti: X `status=available` dengan `hold.held=true`.
* **REP-08:** C1 dengan `kind:"celup_ulang"` + `target_product_id` pada roll ber-`rfid_tag_id`; bukti: dua roll
  (`id=X` consumed & `parent_roll_id=X`) dengan `rfid_tag_id` sama.
* **REP-10:** login akun yang hanya punya PT `ent_kanda`, `GET /inventory/rolls/<roll ent_ksc>/repairs` → bila 200 berisi RPR.

### C3 — Retur supplier DIRECT: buat → ajukan → setujui → reverse
1. Data: `GET /suppliers`, `GET /purchase-orders` (PO `ent_ksc` berstatus diterima), `GET /purchase-returns/source-rolls?product_id=<P>&po_id=<PO>&warehouse_id=<W>` → roll `available` R.
2. `POST /purchase-returns` (model `PurchaseReturnCreate` `schemas_purchasing.py:443-457`, item `PurchaseReturnItem` `:426-440`):
   `{"supplier_id":"<S>","po_id":"<PO>","warehouse_id":"<W>","entity_id":"","items":[{"product_id":"<P>","quantity":0,"unit":"","price":0,"reason":"cacat","condition":"damaged","roll_ids":["<R>"],"roll_details":{}}],"reason":"uji B2b","notes":"","submit_now":false,"supplier_flow":false,"origin_sales_return_id":"","bypass_import_policy":false}`
   → `status=draft`, roll R tetap `available` (PRT-16).
3. `POST /purchase-returns/{id}/submit` → `pending_approval`.
4. `POST /purchase-returns/{id}/approve` `{"notes":""}` (`PurchaseReturnDecision` `:460-461`) → cek R `returned_supplier`,
   `returned_ref.id`, `returned_from_status`; `inventory_movements{ref_id:<id>,type:"return_out"}`; `purchase_returns`:
   `stock_adjusted`, `debit_note_number`, `supplier_status=accepted_supplier`, `gl_status=posted`, `journal_entry_id`, tanpa
   `saga_lock`; `purchase_orders.returned_amount` naik `grand_total`; **PRT-14**: kredit 1-1300 di JE vs `length×unit_cost` R.
5. `POST /purchase-returns/{id}/reverse` `{"notes":"uji reverse B2b"}` → R `available` (bukan `returned_from_status`, PRT-08),
   mutasi `return_out_reversal`, JE `source_type:"purchase_return_reversal"`, PO `returned_amount` kembali, header
   `cancelled` + `supplier_status` masih `accepted_supplier` (PRT-11f); `doc_refs` masih ada.

### C4 — Retur supplier RMA: buat → setujui → kirim → terima / tolak → barang kembali
1. `POST /purchase-returns` seperti C3 tetapi `"supplier_flow":true,"submit_now":true` dengan 2–3 roll (R1,R2,R3)
   → `pending_approval`, `supplier_status=requested_supplier`.
2. Sebelum kirim: tahan R3 `POST /inventory/rolls/{R3}/hold` `{"reason":"uji PRT-03"}`.
3. `POST /{id}/approve` `{"notes":""}` → `approved`, roll tak berubah. **PRT-11a:** `POST /{id}/reject` dan `DELETE /{id}`
   dan `POST /{id}/reverse` → semuanya 400.
4. `POST /{id}/ship-to-supplier` (`SupplierShipInput` `:465-468`) `{"notes":"","carrier":"JNE","tracking_no":"UJI-1"}` →
   R1,R2 `quarantine` + `supplier_return_ref`; **R3 tetap `blocked` tanpa galat (PRT-13)**; tidak ada mutasi baru
   (PRT-12); `inventory_balances.quarantine_qty` naik (on_hand tetap).
5. **PRT-04 + PRT-03:** buat RO atas R1 (`POST /repair-orders`, roll `quarantine` lolos) dan kirim → R1 `wip`.
6a. Cabang tolak: `POST /{id}/supplier-reject` (`SupplierRejectInput` `:480-481`) `{"reason":"supplier menolak"}` →
   `rejected_supplier`; lalu `POST /{id}/goods-back` (`GoodsBackInput` `:489-492`, `GoodsBackRegradeLine` `:484-486`)
   `{"regrade":[{"roll_id":"<R2>","grade":"B"}],"warehouse_id":"","notes":"uji"}` → bukti anomali: **R1 `available` padahal
   RO masih `sent` & `repair_open` terisi; R3 `available` dengan `hold.held=true`** (PRT-03); mutasi `goods_back` untuk
   ketiganya; header `status` tetap `approved` (PRT-11b) dan `GET /suppliers/{S}/scorecard` (`routers/suppliers.py:354`; juga `/suppliers/{S}/360` `:367`) menghitung
   qty retur ini sebagai reject.
6b. Cabang terima (dokumen baru): `POST /{id}/supplier-accept` (`SupplierAcceptInput` `:471-477`, `SupplierRollRejectIn`
   `schemas_return_rolls.py:31-34`) `{"outcome":"ap_credit","notes":"","refund_account_code":"","rejected_rolls":[{"roll_id":"<R2>","reason":"supplier tolak roll ini"}]}`
   → R1 `returned_supplier`, R2 tetap `quarantine`, `supplier_rejected_rolls[R2].goods_back_at=""`; lalu
   `POST /{id}/supplier-rejected-goods-back` `{"regrade":[],"warehouse_id":"","notes":""}` → R2 `available`.
   Varian refund: `"outcome":"refund","refund_account_code":"1-1200"` → cek JE akun debit & `cash_transactions{ref_id:<id>}`.
7. Keputusan per roll sebelum approve: `POST /{id}/roll-decisions` (`ReturnRollDecisionsIn` `schemas_return_rolls.py:27-28`,
   `ReturnRollDecisionIn` `:21-24`) `{"decisions":[{"roll_id":"<R>","decision":"reject","reason":"roll sudah dipotong"}]}`
   → semua ditolak ⇒ `rejected`.

### C5 — Retur QC (PRT-01, PRT-02, PRT-18)
1. Cari `wms_tasks{status:"qc_pending"}` milik `ent_ksc` (tanpa SPK inspeksi terbuka, lihat F-14 di
   `routers/inbound_receiving_extra.py:149-150`). `POST /inbound/tasks/{task}/qc-decision` (`QCDecision`
   `schemas_purchasing.py:577-584`) `{"accept_qty":0,"reject_qty":<sebagian>,"reject_disposition":"return","accept_grade":"A","defects":[],"reason":"uji PRT-01"}`.
2. Ambil `purchase_returns{source:"qc_reject"}` terbaru → `status=pending_approval`, `stock_adjusted=true`, tanpa
   `roll_ids`; roll `returned_ref.id=<pret>` `returned_supplier`; mutasi `movement_type:"qc_reject_return"` tanpa `type`.
3. **PRT-01:** `POST /purchase-returns/{pret}/reject` `{"notes":"uji"}` → bukti: roll tetap `returned_supplier`, tidak ada JE
   `purchase_return` & `purchase_orders.returned_amount` tak berubah.
4. **PRT-02:** ulangi 1–2 untuk retur QC baru → `POST /approve` lalu `POST /reverse` `{"notes":"uji PRT-02"}` → bukti:
   `_reversal_summary.rolls_restored == 0`, JE reversal ada, roll tetap `returned_supplier`, header `cancelled`.

### C6 — Balapan & yatim (PRT-05, PRT-06, PRT-09, PRT-10)
* **PRT-05a:** retur RMA `shipped_supplier`; kirim bersamaan `POST /supplier-accept` dan `POST /supplier-reject`. Bukti:
  `supplier_status=rejected_supplier` dengan `stock_adjusted=true` & JE ada → `POST /goods-back` sukses dan roll
  `returned_supplier` menjadi `available`; `POST /reverse` 400.
* **PRT-05b:** retur DIRECT `draft` dengan banyak roll (memperlebar jendela); bersamaan `POST /approve` dan `DELETE`.
  Bukti: `purchase_returns` hilang tetapi `inventory_rolls{"returned_ref.id":<id>}` / `inventory_movements{ref_id:<id>}` ada
  dan `purchase_orders.returned_amount` naik.
* **PRT-05c:** bersamaan `POST /submit` dan `POST /reject` pada draf → status akhir `pending_approval` dengan `rejected_at` terisi.
* **PRT-06 (data saja):** `db.purchase_returns.find({gl_status:"pending", updated_at:{$lt:<5 menit lalu>}})` → harus 0.
* **PRT-09:** retur jual ber-roll karantina → `POST /sales-returns/{sr}/create-purchase-return` (`SalesToPurchaseReturnInput`
  `schemas_purchasing.py:495-…`: `roll_ids, supplier_id, warehouse_id, reason, notes, bypass_import_policy`) → retur beli
  `pending_approval`; `POST /purchase-returns/{pr}/reject`; ulangi `create-purchase-return` → bukti: 400 "sudah tertaut"
  dan `sales_returns.linked_purchase_return_id` masih menunjuk retur yang ditolak.
* **PRT-10:** dengan `X-Entity-Id: ent_ksc`, `POST /purchase-returns` memakai `po_id` milik `ent_kanda` dan `entity_id:""`
  → bukti: dokumen `entity_id:"ent_kanda"`; ulangi dengan `roll_ids` roll `ent_kanda` tanpa `po_id` → respons memuat
  `items[].rolls[]` (roll_no/lot) PT lain.

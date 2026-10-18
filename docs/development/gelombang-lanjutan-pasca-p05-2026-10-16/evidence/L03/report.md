# L03 — Evidence report

## Sesi 2026-10-18 — LN-030 (implemented_pending_validation)

Navigasi aktual: Penjualan → Pesanan Khusus → "Buat" (form `special-order-form`, langkah 2 "Item & sumber desain") / Detail (`special-order-items-panel`); Produk & Desain → Design Studio (filter `rnd-filter-origin`, detail `design-detail-origin`).

- Sebelum: satu Pesanan Khusus = satu `custom_item`; tipe permintaan di tingkat dokumen; tidak ada sumber desain per item; lepas HOLD memakai izin yang sama dengan HOLD (`rnd.hold`); perubahan motif tidak punya jalur sendiri.
- Sesudah:
  - `items[]` (sumber `parent_product` / `approved_artwork` / `customer_reference`, jenis uji per item, qty/harga per item). Total = Σ item. Payload lama (`custom_item`) tetap berlaku.
  - Artwork ACC dipakai tanpa membuat produk; artwork HOLD/belum ACC/beda entitas → 400.
  - Routing saat disetujui per item; setiap dokumen turunan membawa `special_order_item_id` (permintaan desain, sample labdip/handfeel, proofing). Proofing otomatis setelah desain ACC memakai spec item-nya sendiri.
  - Lepas HOLD: izin baru `design_request.release_hold` (admin, manager, md). Desainer/sales 403.
  - `POST /api/special-orders/{id}/redesign` → OD baru `origin=redesign` + `redesign_of`; asal mencatat `redesigns[]`; proofing OD lama tidak diubah. `source_type=redesign` dari klien ditolak.
  - Label/filter asal: `GET /api/special-orders?origin=`, `GET /api/design-gallery?origin=internal|special_order|redesign`; desain dari permintaan Special Order membawa `special_order_number`, `parent_design_id/code`.
- Schema/migrasi: field baru opsional (`items`, `origin`, `redesign_of`, `redesigns`); dokumen lama tanpa `origin` dianggap Special Order/desain internal. Tidak ada migrasi data.
- Uji: iteration_218 (24/25, 2 bug: bypass HOLD lewat `source_type=redesign`, spec proofing salah item) → diperbaiki → iteration_219: 31/31 backend + UI 100%. File: `backend/tests/test_l03_ln030_special_order_items.py`, `backend/tests/test_l03_ln030_fixes_iter219.py`.
- Terbuka: redesign masih diizinkan saat OD asal draf/menunggu persetujuan (perlu keputusan owner).
- **Keputusan owner 2026-10-18**: redesign tetap diizinkan seperti sekarang (lihat `owner_decisions_2026-10-18.md`). Tidak ada perubahan kode. Fixture tes LN-030 dibuat dinamis (tidak lagi bergantung ID desain/template preview lama); 25/25 + 6/6 lulus ulang di HEAD baru.

## Sesi 2026-10-18 — LN-031 (implemented_pending_validation, commit 8013b92)

Navigasi aktual: Desainer → Desain & Pattern → buka desain → tab Ringkasan (checklist `design-round-paper-<v>` per ronde), tab Riwayat (filter "Print paper"); Penjualan → Pesanan Khusus → Detail → panel `od-customer-approval`.

- Sebelum: tidak ada checklist print paper; ACC desain tidak atomik (dua PIC serentak bisa sama-sama lolos); keputusan pelanggan bertajuk "ACC sample" tanpa objek; OD printing bisa dicatat ACC pelanggan dari ACC desain PIC padahal proofing kain masih berjalan.
- Sesudah:
  - `POST /api/design-gallery/{id}/rounds/{version}/paper {checked, note}` — izin baru `design_request.paper_check` (admin, manager, designer; designer hanya desain miliknya). Disimpan di `round_papers.<v>` + `round_paper_history.<v>` + timeline `paper_check|paper_uncheck`. Tidak mengubah status/ACC; klik ganda/serentak tercatat sekali.
  - Transisi lifecycle desain memakai update bersyarat (status+versi). Pemenang tunggal; lainnya 409 "sudah diproses pengguna lain". Proofing otomatis lahir tepat sekali.
  - Keputusan pelanggan menyimpan `object`/`object_label` (Proofing kain (printing) / Sample labdip/handfeel / Desain (ACC PIC)); `chain.review` membawa objek + pengingat di UI; riwayat status memakai label objek.
  - `review_ready`: selama sample proofing OD belum diputus → `ready=false`, `waiting_for=[nomor]`; keputusan pelanggan 400. Setelah proofing diputus → objek proofing.
- Schema/migrasi: field opsional baru (`round_papers`, `round_paper_history`, `customer_decisions[].object`). Data lama tanpa field tetap terbaca. Tidak ada migrasi.
- Uji: iteration_220 (backend 41/41, UI 100%; 3 temuan minor + 1 logika proofing) → semua diperbaiki. File: `backend/tests/test_l03_ln031_paper_and_acc.py` (4/4), `backend/tests/test_l03_ln031_extra_iter220.py` (6/6, disesuaikan perilaku baru).
- Belum: review terpisah + persetujuan owner. LN-032 (reproofing artwork sama per round) belum dikerjakan.

## Sesi 2026-10-18 — LN-032 (implemented_pending_validation, commit 8013b92)

Navigasi: Penjualan → Pesanan Khusus → Detail → panel `od-customer-approval` (chip `od-proofing-round-<n>`), Rantai Dokumen "Sample R&D" (label "ditolak pelanggan (revisi)"); Desain & Pattern → kartu (`design-paper-count-<id>` "Print paper X/Y ronde").

- T01: desain ACC pada OD printing → proofing ronde 1; `chain.review.ready=false` sampai proofing diputus R&D; keputusan pelanggan 400.
- T02: revisi pelanggan → reproofing ronde berikut dengan `design_id`+`design_version` sama dan `sample_types=['proofing']`; nomor ronde per item/artwork. Printing tanpa riwayat ronde → proofing (tidak jatuh ke labdip). ACC hanya sekali (ACC kedua 400); keputusan serentak dikunci per OD (`decision_lock`, kedaluwarsa 60 dtk) → 409.
- T03: revalidation SKU existing serentak → tepat satu (indeks unik P05 yang sudah ada, dipakai ulang); proofing pada revalidation 400.
- T04: OD polos revisi → jenis uji tetap labdip/handfeel, tanpa artwork/ronde proofing; sample/proofing yang masih terbuka menahan keputusan pelanggan.
- Kartu desain: progres print paper (`rounds_total`, `paper_rounds_done` dari `enrich`).
- Uji: iteration_221 backend 51/51, UI 100%; temuan minor (nomor ronde lintas item, label rantai) diperbaiki. File: `backend/tests/test_l03_ln032_reproofing.py` (4/4), `backend/tests/test_l03_ln032_extra_iter221.py` (6/6).
- Terbuka (butuh keputusan owner): OD printing+labdip — revisi hanya mengulang jenis uji sample terakhir (biasanya proofing), labdip tidak diulang. Label status OD "Terkonfirmasi" selama sampling (perilaku lama).

## Sesi 2026-10-18 (lanjutan) — LN-033 (in_progress: implementasi selesai, menunggu SHA + reviewer; validasi penuh menunggu fondasi L04)

Navigasi aktual: Penjualan → Pesanan Khusus → Detail → panel **Pemenuhan produksi per item** (`od-fulfillment`, kartu `od-ful-item-<key>`); chip PO/MKO di panel harga (`od-po-chip`, `od-mko-chip`); panel pengiriman (`od-shipping`) kini juga tampil untuk hasil MKO.

### Tabel route/API aktual

| Method · path | Izin | Request → response | Error |
|---|---|---|---|
| GET `/api/special-orders/{id}/fulfillment` | `order.view` | → `items[]` per item: `default_route`, `source_mode`, `route`, `status` (ready/blocked/realized/waiting_material/needs_data/error), `blockers`, `warnings`, `pr`, `docs[]` (PO/MKO + qty rencana/diterima/bahan), `history_docs`, `route_history`; `can{choose_route,override_default,realize,cancel}` | 404 OD |
| POST `/api/special-orders/{id}/fulfillment/{key}/route` | `od_fulfillment.choose_route` (+`override_default` bila menyimpang) | `{route: purchase\|makloon, reason}` → `state` (versi, histori) | 400 jalur/alasan, 403, 409 dokumen aktif / ubah serentak |
| POST `/api/special-orders/{id}/fulfillment/{key}/realize` | `od_fulfillment.realize` | `{warehouse_id?}` → `doc` (PO/MKO) atau `status=needs_data` atau `skipped` | 400 blocker/rilis/UOM, 403, 409 sedang diproses |
| POST `/api/special-orders/{id}/procure` | `purchase_requisition.create` + `od_fulfillment.realize` | retry semua item lewat layanan yang sama | 400 |
| POST `/api/special-orders/{id}/lock-price` (auto) | existing | auto-procure → `realize_all` (izin harga tetap terpisah) | error per item disimpan |
| POST `/api/special-orders/{id}/create-pr` | `purchase_requisition.create` | PR per item via `ensure_pr` (mode sesuai jalur; gudang default bila kosong) | 400 jalur belum dipilih |

Schema (opsional, tanpa migrasi wajib): `special_orders.fulfillment.<item_id|main>` {route, default_route, source_mode, reason, deviation, version, decided_by/at, status, error, pr_id, docs[], history[], history_docs[]}, `fulfillment_locks.<key>` (kunci 120 dtk), `linked_mko_id/number`; PR `source_item_key`, `special_order_item_id`; PO/MKO `special_order_id`, `special_order_item_key`, `special_order_item_id`; koleksi `special_order_reconciliation` (SKU ambigu / migrasi ambigu).

### Sebelum → sesudah
- `auto_procure` (special_order_phase2): PR tanpa `fulfillment_mode` → PO ke supplier pemenang + **fallback update lifecycle langsung** bila `release_product` gagal. Sekarang: delegasi ke `services/special_order_fulfillment.py::realize_all`; rilis memakai `rnd_spec_service.release_product` apa adanya — gagal = error terbuka, lifecycle tidak disentuh (T01).
- create-pr manual: PR tanpa jalur. Sekarang memakai `ensure_pr` yang sama; item ber-SKU wajib punya jalur.
- Default jalur = `product_templates.restock_source.mode` (supplier→purchase, makloon→makloon; both/unmapped → wajib dipilih, tidak diam-diam purchase). Menyimpang dari default butuh izin `override_default` + alasan; histori versi tersimpan (T03).
- Supplier: PR `purchase` → `convert_to_po` → harga PO = kontrak terkunci (T04). Makloon: PR `makloon` → `pr_sourcing_service.realize_to_makloon` (reservasi bahan via `material_reservation_service`, tanpa PO barang jadi) (T05). Tanpa resep → `needs_data`, PR dipakai ulang saat retry.
- Bahan kurang: reservasi existing mencatat `shortage_qty`; status item `waiting_material`; tidak ada stok negatif (T06). Forecast MKO < kebutuhan → peringatan sisa kebutuhan (tanpa toleransi baru).
- Idempoten: kunci per item + pencarian ulang PR (`source_item_key`) / PO (`special_order_item_key`) / MKO (realisasi PR) → klik ulang/serentak/retry = satu dokumen (T07).
- Ganti jalur saat PO/MKO aktif → 409 (pesan retur bahan bila sudah issue). Setelah dibatalkan lewat modul asal: dokumen lama diarsip di `history_docs`, PR lama `#retired` + dibatalkan bila belum terminal (T08).
- Izin baru `od_fulfillment.{view,choose_route,override_default,realize,cancel}` (admin/manager penuh; md tanpa cancel; sales/sales_admin/finance lihat), terdaftar di katalog modul Penjualan (T09).
- QC → OD: korelasi lewat `po.special_order_id`; SKU saja hanya bila kandidat tunggal, selain itu antrean `special_order_reconciliation`. Penerimaan hasil MKO OD memicu `on_goods_received` lewat `special_order_id`.
- Migrasi T10: `scripts/migrate_l03_ln033_fulfillment.py` (dry-run default, `--apply`, `--rollback`). Dry-run data demo: matched 0 / ambiguous 0 / unresolved 0 (belum ada OD lama ber-`linked_po_id`).

### Uji
- `backend/tests/test_l03_ln033_fulfillment.py` 8/8, `backend/tests/test_l03_ln033_fulfillment_edges.py` 11/11 (iteration_222: backend 19/19, UI semua alur jalan; temuan minor — error item lain menghentikan auto-procure, create-pr tanpa gudang, chip MKO pada OD campuran, peringatan forecast — sudah diperbaiki).
- Regresi lulus: LN-030/031/032 (+extra), `test_p05_restock_material_revalidation`, `test_p05_acceptance_acc31_33_34`, `test_l01_custom_role`.

### Belum / terbuka
- T02 (printing/polos + pemilihan rute tidak melewati persetujuan) bergantung guard existing (kunci harga butuh ACC pelanggan); diverifikasi ulang di L14.
- Konversi satuan bahan pada prefill makloon (resep output kg, bahan yard) mengikuti logika existing — perlu keputusan DES-01 (kg↔yard).
- Pembatalan PO/MKO tetap di modul asal; endpoint pembatalan khusus OD tidak dibuat (aksi `cancel` disiapkan di izin).
- Status `implemented_pending_validation` menunggu SHA dari "Save to GitHub" dan validasi fondasi L04.



## Sesi 2026-10-18 (lanjutan 2) — LN-034 (in_progress: implementasi + UI selesai, menunggu SHA + reviewer; T08 E2E penuh di L14)

Navigasi aktual: Riset & Sampel → Permintaan Sample (`?view=rnd-samples&entity=ent_ksc`) → panel **Menunggu keputusan PIC** (`pic-queue-panel`); "Buat Permintaan" → "Uji tambahan SKU existing" (`existing-sku-select`, `existing-sku-supplier`, `existing-sku-reason`, panel `supplier-eligibility-panel`); rincian sample uji ulang → `reval-box`, tombol "Catat hasil uji ulang" (`reval-decide-modal`), "Putuskan tindak lanjut" (`pic-decision-modal`).

### Tabel route/API aktual

| Method · path | Izin | Request → response | Error |
|---|---|---|---|
| POST `/api/rnd/samples` (dengan `product_id`) | `rnd.create` | `{product_id, sample_types, revalidation_supplier_id, revalidation_reason}` → sample `purpose=revalidation`, `revalidation{supplier_id, supplier_name, partner_kind, cycle_no, reference, reason}` | 400 supplier/alasan kosong, siklus sejenis terbuka/menunggu PIC, proofing tanpa artwork ACC |
| GET `/api/rnd/revalidation/partners?q=` | `rnd.create` | supplier luar (tanpa `group_entity_id`) + mitra makloon → `items[{id,name,code,partner_kind}]` | — |
| POST `/api/rnd/samples/{id}/decide` (uji ulang) | `rnd.decide` (tanpa matriks `sample_acc`, keputusan owner 2026-10-18) | `{result: pass\|fail, note, contract_id?}` → pass = `decided`; fail = `pending_pic`; `price=0`, `contract_created=false` | 400 lulus tanpa round ACC, gagal tanpa temuan ≥5, kontrak beda supplier/produk/entitas/jenis |
| GET `/api/rnd/samples/{id}/contract-options` | `rnd.decide` | kontrak aktif supplier siklus ini (produk sama/umum, entitas sama/all, jenis purchase/makloon) → `items[]` | 403 sales |
| POST `/api/rnd/samples/{id}/pic-decision` | `rnd.pic_decide` (+`rnd.override_fail` untuk override) | `{action: retest\|operational_note\|override, reason ≥5, scope{documents[], note}}` → `{sample, retest}`; hasil tetap `fail` | 400 bukan pending_pic/alasan, 403, 400 diputus pengguna lain |
| GET `/api/rnd/revalidation/pic-queue` | `rnd.assess` | antrean `pending_pic` per entitas aktif | — |
| GET `/api/rnd/products/{pid}/supplier-eligibility` | `rnd.assess` | per supplier: `latest`, `previous[]`, `open[]`, `eligible` | 403 sales |
| POST `/api/rnd/samples/{id}/cancel` | existing | sample `pending_pic` → 400 (hasil gagal tidak boleh hilang) | 400 |

### Sebelum → sesudah
- Sebelum: satu uji ulang per SKU×jenis tanpa supplier; proofing SKU existing ditolak; keputusan memakai alur "pemenang + harga + kontrak".
- Sesudah: siklus per SKU×supplier×jenis (`open_reval_keys` memuat supplier, indeks unik existing dipakai ulang) (T02); siklus baru mereferensi siklus terakhir supplier yang sama, histori utuh (T03); proofing memakai artwork existing ACC dan tidak membuat desain/SKU (T01); hasil teknis tanpa harga/kontrak, referensi kontrak existing divalidasi (T04/T05); gagal → `pending_pic`, produk/stok/kontrak tidak disentuh, notifikasi md/manager (T06); keputusan PIC tercatat dengan cakupan, override eksplisit & berizin, hasil tetap GAGAL, kelayakan tidak lulus (T07). Pemenuhan LN-033 menyimpan `revalidation_ref` (hasil terbaru produk×supplier) pada dokumen pengadaan (dasar T08).
- UI: pilihan supplier + alasan di form; panel kelayakan per supplier (form & rincian); modal lulus/gagal; antrean PIC; modal keputusan PIC; label status "Lulus uji ulang" / "Gagal — diputus PIC" / "Gagal — override PIC"; panel master data & stepper "Pemenang" disembunyikan untuk uji ulang; KPI "Pemenang dipilih" tidak menghitung hasil uji ulang (`stats.revalidation_decided`).
- Schema: field opsional `revalidation`, `decision.result/override/pic_action`, `pic_decision`, status `pending_pic`. Tidak ada migrasi; sample uji ulang lama tanpa supplier tetap terbaca (kunci lama `pid:type`).

### Uji
- `backend/tests/test_l03_ln034_revalidation.py` 4/4, `backend/tests/test_l03_ln034_revalidation_edges.py` 4/4 (iteration_223: backend 8/8, UI semua alur jalan; temuan label/status sudah diperbaiki).
- 6 tes lama disesuaikan (supplier wajib + fixture dinamis, tidak bergantung ID preview lama): `test_l03_ln032_reproofing` 4/4, `test_p05_restock_material_revalidation` 12/12, `test_p05_acceptance_acc31_33_34` 17/17, `test_l00_edge_cases` 5/5, `test_l00_p05_open_issues` 5/5. LN-033 `test_l03_ln033_fulfillment` 8/8 + `_edges` 11/11 (fixture dibuat dinamis).

### Belum / terbuka
- **Keputusan owner 2026-10-18 (lanjutan):** mencatat hasil teknis uji ulang cukup izin `rnd.decide` (md boleh); ACC Sample biasa (pemenang + kontrak) tetap lewat matriks `sample_acc`. Diterapkan di router `decide_sample` + service (cabang uji ulang sebelum `_assert_role`). Audit `rnd_revalidation_decided`.
- Pemilih kontrak existing di modal hasil (`reval-contract-select`) memakai `contract-options`; referensi tampil di `reval-box-contract`; isi kontrak tidak diubah. Panel spesifikasi disembunyikan untuk uji ulang. Tes: `test_l03_ln034_revalidation_edges.py` 5/5 (md mencatat gagal; opsi kontrak menyaring produk lain; kontrak utuh).
- Pemilih kontrak existing (referensi opsional) belum ada di layar; tersedia lewat API `contract_id`. → SELESAI (lihat butir di atas).
- T08 E2E penuh (revalidasi → PIC → pengadaan LN-033) divalidasi di L14.
- Status menunggu SHA dari "Save to GitHub" + reviewer.

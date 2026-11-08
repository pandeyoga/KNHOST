# B3a — Lampiran: Inventaris angka stok (endpoint × layar × rumus) + uji silang

Baseline kode `5f1e36e`. Semua `berkas:baris` relatif ke `backend/` (BE) atau `frontend/src/` (FE).

## A. Endpoint backend yang mengeluarkan kuantitas stok & rumusnya

| Endpoint | Router | Penghitung | Sumber | Gudang terdaftar? | Makloon dikurangi? | Potong sebagian? | PA/inspeksi | Cakupan PT · lokasi |
|---|---|---|---|---|---|---|---|---|
| GET `/inventory/balances` | `routers/inventory.py:194` | router langsung | saldo | tidak | tidak | ya (saldo) | PA ya · inspeksi tidak | `resolve_list_scope` (PT + lokasi) |
| GET `/inventory/low-stock-summary` | `inventory.py:183` | `stock_availability.low_stock_summary` (`:94`) | saldo (K-04) | **ya** | ya (per PT) | ya | PA ya · tidak | `resolve_scope_ids` (PT) |
| GET `/inventory/status-board` | `inventory.py:157` | `fulfillment_service.status_board` (`:275`) → `build_supply_index(registered_only=True)` | saldo + PO | ya | ya (per PT) | ya | PA ya · tidak | PT (non-lintas: rincian PT sendiri + `global_total`) |
| GET `/inventory/rolls` | `inventory.py:230` | router langsung | roll | — | — | `length_reserved` ditampilkan | — | PT + lokasi + lini |
| GET `/inventory/rolls/available` | `inventory.py:321` | `roll_service.list_available_rolls` (`:2210`) | roll `available`, `active_movement=None`, tanpa earmark | tidak | tidak | ya (`free_length`) | PA ya · inspeksi **tidak** | param PT / `all_entities` |
| GET `/inventory/stock-analytics` | `inventory.py:143` | `stock_analytics_service.compute_stock_analytics` | saldo + roll | tidak | tidak | — | — | PT |
| GET `/stock/buckets` | `routers/stock_buckets.py:18` | `stock_bucket_service.bucket_board` (`:347`) | saldo (`to_list(5000)`) | tidak | tidak | ya | PA ya | PT + lokasi |
| GET `/stock/atp` | `stock_buckets.py:52` | `stock_bucket_service.atp_detail` (`:583`) | saldo + PO penuh + antar-PT | tidak | tidak | ya | PA ya | **available = semua saldo dalam cakupan; incoming/pending = satu owner** |
| GET `/stock/holds`, `/stock/wip` | `stock_buckets.py:27,35` | `list_rolls_in_bucket` (`:399`) | roll | — | — | — | — | PT + lokasi |
| GET `/stock/pending-so` | `stock_buckets.py:43` | `pending_so_board` (`:628`) | SO + `_incoming_supply` (PO penuh) | — | — | — | — | PT (SO) |
| GET `/products` | `routers/products.py:21` | `sales_stock_service.apply_global` (`:23`) | saldo global + PO + antar-PT | tidak | ya (GLOBAL per produk) | ya | PA ya | angka GLOBAL + `entity_available_qty` (PT aktif, makloon **tidak**) |
| GET `/dashboard` | `routers/dashboard.py:41` | router (KPI) + `material_reservation_service.apply_to_products` + `apply_global` | saldo | tidak | KPI: PT AKTIF saja · produk: GLOBAL | ya | PA ya | KPI: `resolve_list_scope` (PT + lokasi) |
| GET `/products/{id}/stock-breakdown` | `products.py:264` | router: saldo `to_list(100)` + roll `to_list(5000)` + matriks | saldo + roll | tidak | tidak | **tidak** | **tidak** | **tanpa cakupan PT** (hanya lini) |
| GET `/product-templates/{id}/summary` | `routers/product_templates.py:32` | `product_variant_service.family_summary` (`:226`) | saldo field **`available`/`reserved` (tidak ada)** + count roll segala status | — | — | — | — | PT + lokasi |
| GET `/pos/site-stock` | `routers/pos.py:19` | `site_stock_service.site_stock` (`:22`) | roll `available` | gudang **aktif** di site | tidak | **tidak** | **tidak** | param `entity_id` tidak divalidasi |
| GET `/pos/best-sellers|featured|recommendations|frequently-bought-together|substitutes` | `pos.py:47,64,74,110,124` | `pos_recommendation_service._available_many` (`:57`) | saldo global | tidak | ya (global) | ya | PA ya | global |
| GET `/sales/stock-summary` | `routers/sales_p04.py:68` | `sales_p04_service.sales_stock_summary` (`:342`) | roll + `_incoming_supply` | tidak | tidak | ya (`$min`) | tidak | PT param |
| POST `/sales-orders/preview-allocation` | `sales_orders_extra.py:50` | `fulfillment_service.classify_lines` → `build_supply_index(registered_only=False)` | saldo + PO | **tidak** | ya | ya | PA ya | PT |
| GET `/sales-admin/orders/{id}/fulfillment-plan` | `routers/work_desks.py:167` | `fulfillment_plan_service` + `internal_request_service.availability` + `fulfillment_decision_service._usable_stock_by_entity` (`:54`) | saldo + roll | gudang boleh-pakai | tidak | tidak (roll) | tidak | PT |
| GET `/sales-orders/{id}/verification` | `work_desks.py:104` | `so_verify_service` (`:175-185`) | saldo PT SO | tidak | tidak | ya | PA ya | PT SO |
| GET `/internal-requests-availability/{pid}` | `routers/internal_requests.py:206` | `internal_request_service.availability` | saldo | tidak | tidak | ya | PA ya | semua PT |
| GET `/sales-orders/{id}/restock-state` | `sales_orders_extra.py:360` | `restock_service` → `alert_ops_service._available_qty` (`:120`) | saldo `to_list(200)` | tidak | tidak | ya | PA ya | PT |
| GET `/home/admin` | `routers/home.py:56` | `home_service.admin_home` → `low_stock_summary` + `reorder_suggestions` | K-04 | ya | ya | ya | PA ya | PT |
| GET `/reports/summary` | `routers/reporting.py:286` | `low_stock_summary` | K-04 | ya | ya | ya | PA ya | PT |
| GET `/reports/warehouse-utilization` | `reporting.py:217` | router Σ `on_hand_qty` | saldo | tidak | — | — | — | PT |
| GET `/reports/stock-aging` | `reporting.py:27` | router | saldo | tidak | — | — | — | PT |
| GET `/purchase-requisitions/reorder-suggestions` | `routers/purchase_requisitions.py:58` | `reorder_suggestions` (`:412`) | K-04 + PO (qty dokumen) | ya | ya | ya | PA ya | PT |
| GET `/warehouses/{id}/stock-tree` | `routers/warehouses.py:62` | `location_stock_tree.warehouse_tree` (`:57`) | roll | satu gudang | tidak | ya | **ya keduanya** | lokasi (`assert_warehouse`) + owner picker |
| GET `/warehouses/{id}/locations` | `warehouses.py:44` | `location_service` | roll | — | — | — | — | lokasi |
| GET `/lots`, `/lots/{id}` | `routers/lots.py:54,140` | `lot_service` (proyeksi `recompute`) | roll → lot | — | — | — | — | PT |
| POST `/cycle-count/sessions/{id}/items` | `routers/cycle_count.py:105` | `stock_count_service.scope_qty` (`:37`) — Σ `length_remaining` | roll | — | — | — | — | PT |
| GET `/rfid/lookup` | `routers/rfid.py:105` | router | roll utuh | — | — | — | — | **pagar tidak berfungsi (SCP-1)**; **menulis** `last_scan` |

## B. Tampilan FE yang menampilkan kuantitas (dan aritmetika di FE)

| Area | Komponen (berkas:baris) | Label | Endpoint · field | Aritmetika FE |
|---|---|---|---|---|
| Gudang › Stok | `features/wms/inventory/InventorySummaryCards.jsx:24-27` | Total Stok Fisik · Tersedia · Dipesan · Stok Rendah | `/inventory/balances` · `on_hand_qty/available_qty/reserved_qty`; `/inventory/low-stock-summary` · `count` | `sumByUnit` atas baris tersaring (`wms/InventoryStockView.jsx:262-269`); tooltip "Tersedia" = teks K-04 (`:296`) padahal angka D2 |
| | `wms/inventory/BalancesTable.jsx:80-101` | Stok Fisik · Dipesan · Tersedia · Lainnya | saldo | "Lainnya" = `max(0, on_hand − reserved − available)` (`:15,99-101`); lencana Habis/Rendah `< 100` per baris (`inventoryConstants.jsx:119-123`) |
| | `wms/inventory/RollsTable.jsx:99,108-125` | Panjang · Berat | `/inventory/rolls` | berat = `secondary_measures.kg ?? weight_kg` |
| Stok & ATP | `features/inventory/InventoryStatusBoard.jsx:246-264,284,354-358` | Stok Fisik · tertahan · Tersedia · Dipesan · Barang Masuk · ATP · antar-PT | `/inventory/status-board` | `pv()` (`:26-27`) — peran non-lintas melihat `global_total` sebagai angka utama; total per satuan dijumlah FE (`:85-97`) |
| | `features/inventory/StockBucketsView.jsx:30-41,198-223` | bucket & ATP | `/stock/buckets` | saat difilter gudang/PT, total dijumlah ulang dari baris (`sumSeg`, `:85-89`) termasuk ATP (server menghitung ATP per PT) |
| | `features/inventory/AtpDetailPanel.jsx:56-59` | Tersedia · Incoming (horizon) · Permintaan · ATP | `/stock/atp` | — (warisi STK-4) |
| Lokasi/Rak | `features/wms/location/StockTreePanel.jsx:11,39,79-83` | Tersedia · Dipesan · QC/ditahan · Proses · Perjalanan | `/warehouses/{id}/stock-tree` | — |
| Pemilih roll | `components/RollPicker.jsx:61,149` | sisa | `/inventory/rolls/available` | total = Σ `length_remaining` |
| POS / Kasir | `features/sales/SalesPortal.jsx:79-85` | filter "di lokasi", "tersedia", "stok rendah" | `/dashboard` products | stok rendah `0 < available ≤ 40` (`:81`) |
| | `features/pos/FacetRail.jsx:25` | "Tersedia (ATP > 0)" | `available_qty` global | label salah (bukan ATP) |
| | `features/pos/PosProductCard.jsx:19-24,101-130` | Habis/Stok rendah/Tersedia · "Di {site}: X" · PT · Grup · Datang · Makloon | `/dashboard` + `/pos/site-stock` | `≤ 40` rendah (`:23`); jumlah varian FE (`utils/variants.js:24-64`) |
| | `components/ProductQuickView.jsx:68-76,119-135` | Tersedia grup · Dipesan · Stok {PT} | `/products`/`/dashboard` | `≤ 40` (`:74`) |
| | `components/SalesStockSummary.jsx:21-29` | Fisik · Dikunci · Bebas · Datang · ATP · + grup | `/sales/stock-summary` | — (warisi STK-4/STK-6) |
| | `hooks/useAppActions.js:260-267,315` | "Qty melebihi stok tersedia" | `available_qty` | `free = max(0, available − inCart)` |
| | `features/pos/CheckoutItemCard.jsx:28-31,78` | "Stok {PT}: … kurang X" | `preview-allocation` | `short = max(0, requested − own_available)` |
| Admin Sales | `features/sales_admin/FulfillmentLineCard.jsx:81-118` | Ambil dari stok sendiri · PT lain | `fulfillment-plan` | Σ `length_remaining` roll terpilih |
| | `features/sales_admin/OrderPreviewCard.jsx:106-107` | cukup / sisa | `/verification` | — |
| | `features/orders/RestockPanel.jsx:177,191-193` | Stok gudang | `/restock-state` | `siap = available>0 && backorder>0` |
| Master produk | `features/catalog/CatalogWorkspace.jsx:90`, `VariantCard.jsx:29`, `FamilyHero.jsx:18-25` | tersedia · dipesan · roll | `/product-templates/{id}/summary` | Σ varian di FE; **selalu 0** (STK-1) |
| HP MD | `features/sales/mobile/MobileMdProducts.jsx:29,52,67,80` | tersedia · Stok per gudang | `/products` (global) · `/products/{id}/stock-breakdown` (`balances[].available_qty` semua PT) | — |
| HP Stok & ATP | `features/sales/mobile/MobileStockAtp.jsx:10,96-124` | siap janji · Tersedia · Dipesan · Akan datang · PT saya | `/inventory/status-board` | `pv()` |
| HP gudang | `features/mobile/MobileWarehouseApp.jsx:122-126,211-231` | sisa | `/rfid/lookup`, `/rfid/untagged-rolls` | — |
| Dasbor | `App.js:342-343` | Jml Tersedia · Jml Dipesan | `/dashboard.metrics.available_by_unit/reserved_by_unit` | — (STK-8) |
| | `features/mobile/MobileOpsApp.jsx:113-122` | Stok tersedia/dipesan/roll | `/dashboard` | — |
| | `features/home/AdminHome.jsx:119-125,169-171` | Stok Rendah · "Stok fisik {…}" | `/home/admin` | field salah → 0 (STK-2) |
| | `features/manager/ManagerDashboard.jsx:107-174,223` | Stok rendah · Utilisasi · Umur stok | `/reports/*` | — |
| Pembelian | `features/purchasing/ReorderSuggestions.jsx:220,247-251` | available · on_order · projected | `/reorder-suggestions` | flag `projected < ROP` |
| Produksi | `features/production/ProductionWO.jsx:101-112` | Tersedia · Cukup? | `/inventory/balances` | Σ `available_qty` produk×gudang SEMUA PT (D2) |
| Opname | `features/inventory/CycleCount.jsx:317-373` | Expected · Actual · Selisih | `/cycle-count/sessions` | selisih dihitung FE + server |
| Lot | `features/inventory/lots/LotParts.jsx:17-21,165-167`, `LotDetailPanel.jsx:117-118,193-195` | Sisa dalam lot · Roll aktif | `/lots` | fallback total satuan campur |
| Kode mati (tak diimpor) | `components/ProductCard.jsx`, `components/ProductDetail.jsx`, `features/pos/mobile/MobilePOS.jsx`, `MobileStock` di `sales/mobile/MobileFieldViews.jsx:90-110` | — | — | ambang `≤ 40`, label Inggris |

*(Inventaris FE disusun dengan bantuan pencarian kode terpisah lalu diperiksa ulang secara acak; 8 baris kunci dicek
langsung: `InventoryStockView.jsx:296`, `ProductionWO.jsx:101-104`, `StockBucketsView.jsx:85-89`, `RollsTable.jsx:108-112`,
`SalesPortal.jsx:81`, `ProductQuickView.jsx:74`, `variants.js:24-31`, `AdminHome.jsx:123`.)*

## C. Uji silang data

### C.1 `inventory_balances` vs hitung ulang dari `inventory_rolls` — **SELESAI (seluruh data)**
Skrip: `scripts/audit/b3a_balance_vs_rolls.js` (meniru `roll_service.rebuild_balance`: status→ember, klaim PA→hold,
`length_reservations` per status). Hasil 9 Nov 2026 ±05:05 WIB:

```
roll unit≠base_unit produk: 0
status tanpa bucket: {"consumed":44,"returned_supplier":7,"delivered":13}
{"segmen_roll":380,"saldo":393,"segmen_selisih":0,"segmen_roll_tanpa_saldo":0,"saldo_tanpa_roll":13,
 "saldo_duplikat":0,"net_selisih_per_bucket":{}}
{"k":"prod_TEST_F2_ee52f0|wh_TEST_F2_ee52f0_transit|ent_ksc","kind":"saldo_tanpa_roll","bal":"hold_qty=50"}
```
Kesimpulan: proyeksi saldo **benar**; tiap selisih antar-layar berasal dari rumus pembaca (STK-5).

### C.2 Distribusi status × gudang (roll) — **SELESAI**
| Gudang | Kode | Site | Sharing | Roll | Saldo |
|---|---|---|---|---:|---:|
| `wh_jakarta` | WH-JKT | Jakarta | dedicated KSC | 23.314 | 122 |
| `wh_fe25df27918e` | RCM-KNITTING | Rancamalang | shared | 10.405 | 99 |
| `wh_adc8726d019e` | RCM-WOVEN | Rancamalang | shared | 9.951 | 107 |
| `wh_40e831c5bb53` | SRG-01 | Soreang | dedicated Kanda | 2.902 | 44 |
| `wh_6cccc13554f8` | RCM-RETUR | Rancamalang | shared | 70 | 14 |
| `wh_09155c408ab2` | RCM-PRINTING | Rancamalang | shared | 58 | 3 |
| `wh_5ae35dcd8837` | RCM-TRANSIT | Rancamalang | shared | 0 | 2 |
| 5 gudang non-aktif + 6 `TEST_WH` | — | — | — | 0 | 0 |

PT pemilik roll: KSC 23.371 · Cipta Sandang 20.407 · Kanda 2.922. Status: available 46.436 · in_transit_sales 81 ·
consumed 44 · subcon 32 · quarantine 29 · reserved 20 · delivered 13 · committed 12 · in_transit_transfer 10 ·
blocked 8 · damaged 8 · returned_supplier 7.

### C.3 Endpoint × sampel — **SELESAI** (9 Nov 2026 06:25–06:40 WIB, sesudah Docker pulih)
**Sampel:** 31 produk (24 berskor keragaman tertinggi + 7 kasus khusus: PO terbuka `KANDA/PO-00001`, transit transfer
`KANDA/TRF-00001`, antar-PT `KANDA/IC-00035`, karantina, potong besar) — 3 satuan (kg/yard/meter), 3 PT, 7 gudang,
termasuk 2 produk bercadangan makloon aktif; **49 roll** (≤ 3 per status ×12 status + 5 potong sebagian + 3 anak
potongan + 3 ber-tag + 2 bin simulasi hilang). Prasyarat baca-saja dicek dulu: 0 SO memenuhi syarat
`expire_old_reservations` (STK-11), jadi GET `/products` & `/dashboard` tidak menulis saat uji.
**Alat:** `b3a_stock_truth.js` → `truth.json`; `b3a_api_fetch.py` (523 GET berhasil, 7 akun);
`b3a_compare_numbers.py` (acuan = K-04 dihitung langsung dari roll).

**Hasil:** **895 perbandingan, 48 berselisih**. Semua selisih dijelaskan rumus pembaca (tidak ada yang berasal dari
saldo rusak):

| endpoint | dibandingkan | berselisih | sebab (temuan) |
|---|---:|---:|---|
| `/inventory/status-board` total & per PT | 95 | 0 | = K-04 |
| `/products` `available_qty` (global) | 93 | 0 | = K-04 di sampel (cadangan ≤ tersedia PT) |
| `/dashboard` `entity_available_qty` | 63 | 0 | = K-04 (makloon PT aktif dikurangi) |
| `/inventory/low-stock-summary` | 3 | 0 | = K-04 |
| `/products` `entity_available_qty` | 63 | 2 | makloon tidak dikurangi (SSOT-4, STK-8) |
| `/stock/atp` `available` (per PT & owner=all) | 94 | 4 | makloon (SSOT-4) |
| `/stock/buckets` totals | 31 | 2 | makloon (SSOT-4) |
| `/products/{id}/stock-breakdown` saldo | 31 | 2 | makloon (SSOT-4) |
| `/products/{id}/stock-breakdown` matriks | 31 | 6 | makloon + panjang dipesan potong (STK-7, STK-13) |
| `/inventory/rolls/available` (pemilih roll) | 31 | 2 | makloon — roll cadangan makloon bisa dipilih (SSOT-4) |
| `/internal-requests-availability` | 31 | 2 | makloon (SSOT-4) |
| `/sales/stock-summary` `free` | 63 | 2 | makloon (SSOT-4) |
| `/sales/stock-summary` `physical` | 63 | 5 | `committed` tidak dihitung fisik (STK-6) |
| `/pos/site-stock` `own_qty` | 186 | 4 | panjang dipesan potong ikut "tersedia" (STK-13) |
| `/product-templates/{id}/summary` | 17 | **17** | field salah → selalu 0 (STK-1) |

Rincian semua baris berselisih:

| SKU | satuan | PT | endpoint | angka endpoint | acuan K-04/fisik | selisih |
|---|---|---|---|---:|---:|---:|
| KNKNT0021-L-BEIX-XA-XX-XB | kg | semua | `/stock/buckets`, stock-breakdown (saldo & matriks), `/inventory/rolls/available`, `/internal-requests-availability`, `/stock/atp?owner=all` | 5.684,33 | 5.609,33 | **+75,00** (cadangan `KSC/MKO-00082`) |
| KNKNT0021-L-BEIX-XA-XX-XB | kg | KSC | `/products` entity_available, `/stock/atp`, `/sales/stock-summary` free | 2.440,75 | 2.365,75 | **+75,00** |
| KNKNT0021-L-BEIX-XA-XX-XB | kg | KSC | `/sales/stock-summary` physical | 2.517,03 | 2.541,61 | **−24,58** (committed) |
| DMO-GRY-KNT-001 | kg | semua | 6 endpoint sama seperti di atas | 2.997,62 | 2.697,62 | **+300,00** (cadangan `MKO-00005`, Kanda) |
| DMO-GRY-KNT-001 | kg | Kanda | `/products` entity_available (477,63) vs `/dashboard` entity_available (177,63) untuk PT & produk yang SAMA | 477,63 | 177,63 | **+300,00** |
| BTK-MEGA-001 | yard | KSC | `/sales/stock-summary` physical | 162,00 | 662,00 | **−500,00** (committed 500) |
| BTK-MEGA-001 | yard | KSC | `/pos/site-stock` Jakarta, stock-breakdown matriks | 12,00 | 10,00 | **+2,00** (reservasi potong — milik SO yang sudah tidak ada, SSOT-8) |
| TNI-GRGD-001 | yard | KSC | `/sales/stock-summary` physical | 120,00 | 270,00 | **−150,00** (committed) |
| KNWVN0015-L-TAUX-XA-XX-XX | yard | KSC | `/pos/site-stock` Jakarta, matriks | 78.854,83 | 78.844,83 | **+10,00** (potong dipesan) |
| KNWVN0015-L-TAUX-XA-XX-XX | yard | KSC | `/sales/stock-summary` physical | 78.857,83 | 78.979,22 | **−121,39** |
| KNWVN0012-L-4XXX-XA-XX-XX | yard | KSC | `/pos/site-stock` Jakarta, matriks | 24.118,03 | 24.098,03 | **+20,00** |
| KNWVN0012-L-4XXX-XA-XX-XX | yard | KSC | `/sales/stock-summary` physical | 24.244,61 | 24.257,11 | **−12,50** |
| KNWVN0005-L-FOGX-XA-XX-XX | yard | KSC | `/pos/site-stock` Jakarta, matriks | 8.549,79 | 8.524,79 | **+25,00** |
| 17 varian (mis. KNKNT0021-L-KHKX-XA-XX-XB, KNKNT0021-L-HTMX-XA-XX-XA, KNKNT0054-L-CUBX-XA-XX-XX, KNKNT0054-L-CKLX-XA-XX-XX, KNKNT0054-L-DBXX-XA-XX-XX) | kg | semua | `/product-templates/{id}/summary` | **0,00** | 5.048,95 · 4.567,43 · 4.551,15 · 4.381,26 · 4.076,35 … | **−100 %** |

**KPI dasbor (`/dashboard` metrics.available_by_unit) vs K-04:**

| Cakupan (admin) | Dasbor | K-04 dari saldo | Selisih |
|---|---|---|---|
| KSC | kg 60.996,16 · yard 1.314.153,95 · meter 108 | sama | 0 |
| Kanda | kg 70.455,60 · yard 3.537,54 | sama | 0 |
| Cipta Sandang | kg 253.035,84 · yard 1.144.492,83 | sama | 0 |
| **Semua PT** (`?entity_id=all`, PT aktif KSC) | kg **384.787,60** | kg 384.487,60 | **+300 kg** — cadangan makloon Kanda tidak dikurangi karena hanya PT AKTIF (STK-8) |
`metrics.available_qty` masih dikirim sebagai **satu angka campur satuan** (2.847.079,92 = yard + kg + meter).

**Barang datang (produk `prod_e867010c6127`, KNKNT0052-L-NVYX, kg, Kanda @SRG-01):** PO `KANDA/PO-00001` 1.500 kg
(belum diterima) + 10 roll 250,65 kg `in_transit_transfer` (`KANDA/TRF-00001`, dispatched). Semua endpoint sepakat
incoming = 1.500 (PO); **transit transfer 250,65 kg tidak dihitung "datang" di mana pun** (hanya ditampilkan terpisah
sebagai "in_transit" di `/sales/stock-summary`). Produk `prod_tenun_ikat` (antar-PT `KANDA/IC-00035` status **draft**
5 yard dari KSC): `/stock/atp` & `/sales/stock-summary` Kanda = incoming 5; `/inventory/status-board` = **0** (rumus
papan tidak membaca antar-PT); `/products` & `/dashboard` (angka GRUP) = `incoming_restock_qty` 5 untuk SEMUA PT
aktif — padahal di tingkat grup barang itu sudah terhitung di stok KSC (**hitung ganda**) dan dokumennya masih draft.

**Pohon stok lokasi (`/warehouses/{id}/stock-tree`) vs saldo** — 6 gudang × 3 satuan: tersedia, dipesan(+dialokasikan),
QC/ditahan, perjalanan **identik** dengan saldo (D6 ≡ D2 selama 0 roll klaim PA / tahan inspeksi).

### C.4 Cakupan per akun (GET, 7 akun) — **SELESAI**
Setelan `wms.location_scope_enforced` = **true** (global, 22 Okt). Akun: admin/manager (lintas PT), wh.admin
(`warehouse_admin`, KSC+Kanda, supervisor lokasi), warehouse.rancamalang (`warehouse`, home Cipta Sandang, boleh 3 PT,
site Rancamalang), warehouse.soreang (`warehouse`, Kanda, site Soreang), sales (KSC), sales.kanda (Kanda). Sel =
jumlah baris; gudang & PT yang muncul di hasil (kode pendek). `403` = tidak berizin.

| endpoint | admin | manager | wh.admin | warehouse.rancamalang | warehouse.soreang | sales | sales.kanda |
|---|---|---|---|---|---|---|---|
| `wmstasks` | 243; gudang 80f859/JKT/RCM-PRT/RCM-TRN/RCM-WOV/b98b13; PT KSC | 243; gudang 80f859/JKT/RCM-PRT/RCM-TRN/RCM-WOV/b98b13; PT KSC | 243; gudang 80f859/JKT/RCM-PRT/RCM-TRN/RCM-WOV/b98b13; PT KSC | 5; gudang RCM-KNT/RCM-TRN/RCM-WOV; PT CST | 4; gudang SRG-01; PT KANDA | 403 | 403 |
| `balances` | 142; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV/ransit; PT KSC | 142; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV/ransit; PT KSC | 142; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV/ransit; PT KSC | 202; gudang RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV; PT CST | 44; gudang SRG-01; PT KANDA | 142; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV/ransit; PT KSC | 48; gudang RCM-RET/SRG-01; PT KANDA |
| `rolls` | 5000; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-WOV; PT KSC | 5000; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-WOV; PT KSC | 5000; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-WOV; PT KSC | 5000; gudang RCM-KNT/RCM-PRT/RCM-RET/RCM-WOV; PT CST | 2902; gudang SRG-01; PT KANDA | 5000; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-WOV; PT KSC | 2922; gudang RCM-RET/SRG-01; PT KANDA |
| `transfers` | 15; gudang JKT/RCM-WOV; PT CST/KANDA/KSC | 15; gudang JKT/RCM-WOV; PT CST/KANDA/KSC | 15; gudang JKT/RCM-WOV; PT CST/KANDA/KSC | 2; gudang RCM-TRN/RCM-WOV; PT CST/KSC | 15; gudang JKT/SRG-01/e7a951; PT KANDA/KSC | 403 | 403 |
| `putaway` | 2; gudang JKT/RCM-WOV; PT KSC | 2; gudang JKT/RCM-WOV; PT KSC | 2; gudang JKT/RCM-WOV; PT KSC | 0; gudang -; PT - | 0; gudang -; PT - | 403 | 403 |
| `grn` | 15; gudang JKT; PT - | 15; gudang JKT; PT - | 15; gudang JKT; PT - | 0; gudang -; PT - | 0; gudang -; PT - | 403 | 403 |
| `cyclecount` | 0; gudang -; PT - | 0; gudang -; PT - | 0; gudang -; PT - | 0; gudang -; PT - | 0; gudang -; PT - | 403 | 403 |
| `rfidtags` | 41; gudang JKT/RCM-PRT/RCM-WOV; PT KSC | 41; gudang JKT/RCM-PRT/RCM-WOV; PT KSC | 41; gudang JKT/RCM-PRT/RCM-WOV; PT KSC | 0; gudang -; PT - | 0; gudang -; PT - | 403 | 403 |
| `printjobs` | 8; gudang JKT/RCM-TRN; PT KSC | 8; gudang JKT/RCM-TRN; PT KSC | 8; gudang JKT/RCM-TRN; PT KSC | 0; gudang -; PT - | 0; gudang -; PT - | 403 | 403 |
| `deliveries` | 6; gudang -; PT KSC | 403 | 6; gudang -; PT KSC | 0; gudang -; PT - | 0; gudang -; PT - | 6; gudang -; PT KSC | 0; gudang -; PT - |
| `statusboard` | 411; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV/SRG-01; PT CST/KANDA/KSC | 411; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV/SRG-01; PT CST/KANDA/KSC | 411; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV; PT KSC | 411; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV; PT CST | 411; gudang RCM-RET/SRG-01; PT KANDA | 411; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV; PT KSC | 411; gudang RCM-RET/SRG-01; PT KANDA |
| `buckets` | 128; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV/ransit; PT KSC | 128; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV/ransit; PT KSC | 128; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV/ransit; PT KSC | 197; gudang RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV; PT CST | 44; gudang SRG-01; PT KANDA | 128; gudang JKT/RCM-KNT/RCM-PRT/RCM-RET/RCM-TRN/RCM-WOV/ransit; PT KSC | 44; gudang RCM-RET/SRG-01; PT KANDA |
| `rfidsummary` | {"tags_total": 41, "tags_active": 35, "untagged_rolls": 5000 | {"tags_total": 41, "tags_active": 35, "untagged_rolls": 5000 | {"tags_total": 41, "tags_active": 35, "untagged_rolls": 5000 | {"tags_total": 0, "tags_active": 0, "untagged_rolls": 5000} | {"tags_total": 0, "tags_active": 0, "untagged_rolls": 2920} | 403 | 403 |
| `myloc` | restricted=False whs=- | restricted=False whs=- | restricted=False whs=- | restricted=True whs=RCM-TRANSIT,RCM-WOVEN,RCM-KNITTING,RCM-PRINTING,RCM-RETUR | restricted=True whs=SRG-01 | 403 | 403 |

Bacaan:
* **Lokasi kerja bekerja** di `/wms/tasks`, `/inventory/balances`, `/inventory/rolls`, `/stock/buckets`,
  `/putaway-orders`, `/goods-receipts` (warehouse.soreang hanya SRG-01).
* **Lokasi kerja TIDAK bekerja** di `/transfers` (warehouse.soreang melihat **15** transfer termasuk Jakarta & gudang
  lama `GU-KANDA`), `/inventory/status-board` (warehouse.soreang melihat rincian gudang **RCM-RETUR** milik Kanda —
  sementara `/inventory/balances` akun yang sama menyembunyikannya), `/rfid/lookup` (SCP-1).
* **PT aktif mengunci daftar tugas**: warehouse.rancamalang (boleh 3 PT, gudang Rancamalang dipakai bersama) hanya
  melihat **5** tugas PT rumah (Cipta Sandang) dan **0** PA/GRN/tag/print job — padahal PA00001/2 KSC tiba di RCM-WOVEN
  (SCP-3).
* Admin/manager/wh.admin (PT aktif KSC) melihat **67 tugas di 6 gudang `TEST_WH`** (54 `waiting_goods`) bercampur
  tugas nyata (§8).
* `/rfid/summary` `untagged_rolls` = **5000** untuk KSC/admin (nyata ≈ 23.300 roll KSC tanpa tag) — batas daftar
  dipakai sebagai angka (STK-14).

### C.5 Uji pagar `/rfid/lookup` (`record=false`, tidak menulis) — SCP-1 **terverifikasi-data**
| Akun (PT boleh · lokasi) | RL-00014 (KSC @JKT) | RL-00016 (Cipta Sandang @RCM-KNITTING) | RL-09051 (Kanda @SRG-01) | Pembanding `/inventory/rolls?q=RL-00014` |
|---|---|---|---|---|
| warehouse.soreang (Kanda · Soreang) | **200**, dokumen roll utuh, `unit_cost` ada | **200**, `unit_cost`=31.680, `base_unit_cost`=31.680 | 200 | **0 baris** (pagar bekerja di sana) |
| warehouse.rancamalang (3 PT · Rancamalang) | **200** (Jakarta, di luar lokasi) | 200 | **200** (Soreang, di luar lokasi) | 0 baris |
| wh.admin (KSC+Kanda) | 200 | **200** (PT Cipta Sandang tidak diizinkan), HPP terbuka | 200 | 1 baris, **HPP disembunyikan** |
| sales / sales.kanda | 403 (`wms.view`) | 403 | 403 | — |

### C.6 Anomali roll & dokumen (seluruh data) — **SELESAI**
`b3a_roll_anomalies.js` (46.700 roll) dan `b3a_doc_checks.js`. Nol = pemeriksaan dijalankan dan bersih.

| Pemeriksaan | Jumlah | Contoh |
|---|---:|---|
| `roll_no` kembar · EPC kembar · `id` kembar (roll/saldo/lot/mutasi/tugas/tag) | **0 · 0 · 0** | guardrail `roll_identity` & `rfid_tag_unique` bekerja |
| sisa > panjang awal · sisa negatif · `length_reserved` ≠ Σ reservasi · `unit` ≠ satuan dasar | 0 · 0 · 0 · 0 | — |
| status ditahan tanpa `reserved_ref` · `available` masih ber-`reserved_ref` · roll PT lain di gudang dedicated · roll di gudang non-aktif | 0 · 0 · 0 · 0 | — |
| `inspection.hold.held=true` (status apa pun) · `active_movement` aktif | 0 · 0 | (laten: SSOT-3) |
| `grade` ≠ `qc_grade` / `inspection.grade` · `lot_id` yatim · `lot` ≠ `lot_number` | 0 · 0 · 0 | — |
| status tidak terdaftar di registry (`consumed`, `delivered`, `subcon`, `returned_supplier`) | **96 roll** | SSOT-1 |
| roll fisik di gudang **tanpa bin** | **9.394** (available 9.350, quarantine 29, reserved 7, blocked 4, committed 4) | `roll_bbdcd23fbe1b` |
| `location_type=warehouse_bin` padahal `in_transit_*` | **91** | `roll_08a02ac91ac8` (in_transit_sales) |
| `journey.stage` (sumbu status kedua, 136 roll) tidak mengikuti status sesudah alur masuk | 20 kombinasi | `label_verified` + `in_transit_sales` ×32 · `received_transit` + `quarantine` ×19 · `stored` + `available` ×23 · `stored` + `quarantine` ×10 · `received_transit` + `available` ×13 · `tag_verified` + `consumed` ×3 · `label_verified` + `delivered` ×5 |
| `dye_lot` ≠ `lot` | **100** | `roll_74d7283673bd` lot `KSC/LOT-2610-0124`, dye_lot `CST/LOT-2610-0123` (via inbound 64, transfer 9, subcon 19, …) |
| pemilik lot ≠ pemilik roll | **3** | `roll_8fc6567625bc` KSC vs lot Cipta Sandang |
| `rfid_tag_id` berisi label, bukan id tag | **3** | RL-46505 `DM-9A129A-020`, RL-46560 `F14-303FF0-00`, RL-46542 `F14-48C98C-00` (tracking `barcode`) |
| tag menunjuk roll yang sudah tidak ada | **6** (semua `retired`, "roll_dibatalkan") | `rtag_3bd08b08a9e2` → `roll_9e74d7987365` |
| bin tidak ada di master gudang | 2 | `bin_sim_hilang_01/02` (data simulasi) |
| roll `blocked` yang masih membawa reservasi potong | **1** | RL-00005 (50 yd): 1 yd → SO tak ada, 5 yd **committed** → `KSC/SO-00159` (confirmed) |
| reservasi potong ke SO yang tidak ada | **3** | RL-00005 1 yd; RL-46582 1 yd ×2 (`so_97da5e9786df`, `so_3a9b62992124`) |
| grade ≠ A tanpa `grade_history` | 1.785 (1.784 data impor/seed; **1** di luar impor: roll retur `roll_2ac2772f7df1`) | SSOT-2 |
| `wms_tasks.roll_id` berisi label | **26** | `wms_bef96c0e9725` → `DM-9A129A-020` |
| `wms_tasks.owner_entity_id` ≠ `entity_id` · `entity_id` tugas ≠ PO | 0 · 0 | (field owner hanya di 2 tugas) |
| `inventory_lots.entity_id` ≠ `owner_entity_id` | 0 | duplikasi field, nilai masih sama |
| mutasi dengan `roll_id` yatim | **71 nilai / 243 mutasi** — termasuk **203 mutasi `reservation` dengan `roll_id` berisi daftar id dipisah koma**, `ROLL-005`, `roll_TEST_*` | SCH-6 |
| mutasi ber-`type`+`direction` (skema kedua) | 16 | `return_quarantine_in` 12, `return_out` 3, `goods_back` 1 |
| tanda qty mutasi | `putaway` (+) 37.149, `reservation` (+) 524, `release_reservation` (+) 700, `subcon_consume`/`subcon_loss`/`qc_reject_damaged` **(+)**, `outbound_ship`/`transfer_out` (−) | Σ mutasi tidak bisa membangun saldo (KSC Σmutasi 1.453.827 vs Σroll 1.381.918, campur satuan) |
| alokasi SO ≠ roll tertahan | 1 | `KANDA/SO-00003` 250,65 kg — roll sedang `in_transit_transfer` (`transfer_ref.so_id`), jalur sah |
| roll `reserved` untuk transfer `waiting_approval` | 11 | `KSC/TRF-00001/2/5/9` — stok dikunci sebelum disetujui |
| PO item: field | `quantity_base` 40/41, **tidak ada** `base_quantity` | SCH-3 |

# B3b — Lampiran B: Matriks Fitur Daftar WMS-RFID (desktop & HP)

Paket **B3b** · 9 Nov 2026 · HEAD audit `5f1e36e`. Laporan utama: [`B3b-FORM-INPUT-DAFTAR.md`](B3b-FORM-INPUT-DAFTAR.md).

Kolom: **Cari** (server/klien/–) · **Saring** (jenis) · **Urut** · **Halaman** (server = parameter halaman ke API;
klien = memotong array yang sudah dimuat; – = semua baris dirender) · **Ekspor** · **Massal** = pilih banyak baris ·
**K/M/G** = keadaan kosong / memuat / galat (✓ ada, ✗ tidak, "palsu" = pesan kosong tampil saat masih memuat,
"senyap" = galat ditelan) · **GET** = endpoint daftar + batas/proyeksi (berkas:baris).
Tidak ada satu pun daftar di cakupan yang punya ekspor **XLSX** (lihat EXP-01).

## B.1 Penerimaan & QC

| Layar | Berkas | Cari | Saring | Urut | Halaman | Ekspor | Massal | K/M/G | GET (batas / proyeksi) |
|---|---|---|---|---|---|---|---|---|---|
| Kedatangan (GRN) | wms/grn/GoodsReceiptsView.jsx | server `q`, tanpa debounce | chip status | – | **– (dipotong 100 diam)**; angka chip = baris termuat | ✗ | ✗ | ✓/✓/✓ | /goods-receipts `limit=100` tanpa maks (`limit=-1` → `to_list(-1)`), dokumen penuh (goods_receipts.py:47-72) |
| Selisih supplier | grn/SupplierVariancePanel.jsx | – | chip rentang | server | – | ✗ | ✗ | palsu/✗/✓ | goods_receipt_service.py:937-973 `to_list(5000)` tanpa proyeksi, tanpa `location_scope`; "total kurang" dijumlah lintas satuan |
| Tugas barang masuk (mode lama) | wms/InboundScanInterface.jsx | – | chip status buatan sendiri | – | – | ✗ | ✗ | ✓/✓/✓ | inbound_receiving.py:18-39 `to_list(200)`; PO `to_list(100)` |
| Antrean QC kedatangan | wms/QCInspection.jsx | klien | – | – | klien 25 | ✗ | ✗ | ✓/✓/✓ | inbound_receiving_extra.py:93-131 `to_list(200)`, 2 kueri per tugas (N+1) |
| SPK inspeksi | inspections/InspectionsView.jsx | server (input mentah, bukan `SearchBox`) | chip jenis/status/ditahan + `LineFilter` | – | **server** `PaginationBar` 25 + pilih ukuran | **CSV** (fetchAll, ikut saringan) | ✗ | ✓/✓/✓ | /inspections berhalaman (le=500) — satu-satunya daftar penerimaan yang lengkap; `/inspections/export` (CSV backend) tak dipakai FE |
| Profil SJ | grn/GrnProfilesPanel.jsx | – | – | updated_at | – | ✗ | ✗ | ✓/✗/✓ | `to_list(500)` |
| Sampel OCR | grn/GrnOcrSamplesPanel.jsx | – | – | created_at | – | ✗ | centang → "Uji" | palsu/✗/✓ | `to_list(500)` |
| Master grade | settings/masters/GradeMasterView.jsx | – | – | rank | – | ✗ | ✗ | ✗/✓/✓ | `to_list(200)` + agregat seluruh `inventory_rolls` tiap muat |
| Roll per tugas QC | wms/RollInspectionModal.jsx | – | – | roll_no | – | – | – | ✓/✓/✓ | qc_inspection.py:31-38 `to_list(500)`, **tanpa cek PT** (FRM-23) |

## B.2 Putaway · lokasi · gudang · transfer · opname · pendaftaran · stok · perbaikan · lot

| Layar | Berkas | Cari | Saring | Urut | Halaman | Ekspor | Massal | K/M/G | GET (batas / proyeksi) |
|---|---|---|---|---|---|---|---|---|---|
| Antrean penempatan rak | wms/LocationPutawayView.jsx:150-156 | ✗ | gudang | ✗ | ✗ | ✗ | ✗ | ✓/✓/✓ | /inventory/putaway/queue cap 500 tanpa penanda (location_service.py:227,241) |
| Perintah simpan ke rak (PA) | wms/PutawayOrdersPanel.jsx:205-309 | ✗ | ✗ (aktif disaring klien :67) | created_at | ✗ | ✗ | ✗ | ✓/✗/✓ | /putaway-orders `limit=100` tanpa maks; 100 terbaru termasuk draf/selesai → PA aktif lama hilang |
| Draf PA | wms/PutawayDraftsPanel.jsx:86-151 | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓/✓/✓ | idem |
| Stok per alamat / okupansi / alamat yatim | location/StockTreePanel · BinOccupancyGrid · OrphanPanel | ✗ | PT | ✗ | ✗ | ✗ | ✗ | ✓/✓/✓ | orphans `to_list(1000)` (location_service.py:338) |
| Master gudang | wms/warehouses/WarehouseMasterView.jsx:260-440 | klien | chip "Boleh dipakai/Semua" | ✗ | ✗ | ✗ | ✗ | ✓/✓/✓ | /warehouses `to_list(500)` + **N× GET occupancy** (:102-105) |
| Transfer | TransferManagement.jsx:280-343 · transfer/TransferList.jsx | klien | jenis, status (**tanpa "Diterima Sebagian"/"Dibatalkan"**), lini | ✗ | ✗ | ✗ | ✗ | ✓/✓/✓ | /transfers `to_list(200)` tanpa proyeksi (transfers.py:124-131) |
| Sesi opname | inventory/CycleCount.jsx:205-230 | ✗ | ✗ | server desc | ✗ | ✗ (PDF per sesi) | ✗ | ✓/sebagian/✓ | `to_list(100)` **tanpa proyeksi** (items + scans penuh) |
| Sesi pendaftaran | registration/InitialRegistration.jsx:80-96 | ✗ | ✗ (API sudah dukung status/gudang) | ✗ | ✗ | ✗ | ✗ | ✓/–/✓ | `to_list(200)` berproyeksi ✓ |
| Stok: saldo | wms/inventory/BalancesTable.jsx | ✓ | gudang | ✗ | ✗ (cap 2000) | ✗ | ✗ | ✓/✓/✓ | inventory.py:202-204 |
| Stok: roll | RollsTable · InventoryStockView.jsx:483-498 | server | gudang, lini, cek, pegging | ✗ | **server** `PaginationBar` (100) | CSV (ikut saringan) | ✗ | ✓/✓/✓ | /inventory/rolls berhalaman (`limit` bawaan 5000 tanpa maks bila tak berhalaman) |
| Stok: mutasi | LedgerTable · InventoryStockView.jsx:506-519 | ✓ | jenis, gudang | ✗ | server — **tabel memotong 60 baris** walau pager 100 (LST-05) | CSV | ✗ | ✓/✓/✓ | berhalaman |
| Perbaikan | wms/repair/RepairOrdersView.jsx:60-70 | ✓ (regex tanpa escape) | tab status | ✗ | ✗ | ✗ | ✗ | ✓/✓/✓ | limit 200 (repair_order_service.py:331-338) |
| Lot | inventory/lots/LotsView.jsx:296-306 | ✓ | LotFilters | ✗ | server | CSV | lampirkan roll | ✓/✓/✓ | lots.py:55-58 |

## B.3 Barang keluar · potong · pengiriman · retur · makloon · eskalasi

| Layar | Berkas | Cari | Saring | Urut | Halaman | Ekspor | Massal | K/M/G | GET (batas / proyeksi) |
|---|---|---|---|---|---|---|---|---|---|
| Tugas barang keluar | wms/OutboundScanInterface.jsx:281-362 | klien | chip status (server) + jenis + gudang (klien) | – | – (gulir 520 px) | ✗ | ✗ | ✓/✓/✓ | /outbound/tasks `to_list(200)` desc termasuk dispatched/cancelled (outbound_picking.py:36-46) |
| Roll harus diambil | wms/PickListPanel.jsx | – | – | roll_no | – | cetak SPB | – | ✓/null/✓ | /pick-list `to_list(500)` |
| Paket potong | wms/CuttingOpsView.jsx | klien | tahap + gudang | – | – | ✗ | potong semua per paket | ✓/✗/✓ | memakai 200 tugas yang sama, disaring klien (:50-52) |
| Antrean potong + roll anak | wms/PendingCutsPanel.jsx | – | gudang (klien) | – | – | ✗ | cetak semua label | ✓/✗/pesan | /inventory/pending-cuts tanpa limit/filter server |
| Meja cutting | samples/CuttingDesk.jsx | – | 3 antrean | waktu tunggu | – | ✗ | terima semua per pesanan | ✓/✗/✓ | /cutting/desk **`sort(created_at, 1).to_list(500)` tanpa filter status** (cutting_service.py:76-77) → LST-02 |
| Pesanan sample | samples/SampleOrdersView.jsx | klien | `StatusTabs` (server) | – | klien 20 | ✗ | – | ✓/✓/✓ | /sample-orders `to_list(300)` |
| Daftar pengiriman | logistics/LogisticsView.jsx + DeliveryTable.jsx | server `q` | kartu status (server) + tanggal (klien) | kolom ✓ | `PagedRows` klien | **CSV buatan sendiri** (`,`, tanpa BOM, baris tampil saja) :34-41 | – | ✓/✓/✓ | /logistics/deliveries `to_list(1000)` (logistics_service.py:297) |
| Riwayat pengiriman | logistics/HistoryPanel.jsx | server | tanggal/moda/status (server) | – | server 25 tetap | **CSV halaman ini saja**, `,` :43-46 | – | ✓/✓/✓ | /logistics/history: `to_list(3000)` lalu dipotong di memori (:384) |
| Armada | logistics/FleetPanel.jsx | klien | – | plat | klien 20 | ✗ | – | ✓/✓/✓ | kendaraan `to_list(500)` |
| Trip / kandidat | logistics/TripPlannerPanel.jsx | – | – | – | – | cetak | centang | ✓/–/✓ | /trip/candidates |
| Retur & barang sisa | sales/SalesReturns.jsx | server | status, tipe, lini | belum dipastikan | **server** `PaginationBar` 20 | CSV standar (exportConfig + fetchAll) | – | ✓ | /sales-returns berhalaman |
| Retur beli | purchasing/PurchaseReturns.jsx:546-554 | server | tab | – | server | CSV standar | – | ✓ | /purchase-returns berhalaman |
| Retur antar-PT | finance/interco/IntercoReturnsPanel.jsx | ✗ | ✗ | – | ✗ | ✗ | – | belum dipastikan | /interco/returns `limit=200` tanpa maks |
| Inbox retur internal | finance/interco/IntercoReturnInbox.jsx | ✗ | ✗ | – | ✗ | ✗ | pilih roll | ✓/✓/? | /return-dispositions/inbox |
| Order makloon | purchasing/MakloonOrdersView.jsx | klien | status + lini (klien) | – | `PagedRows` klien | ✗ | – | ✓/✓/? | /makloon-orders `to_list(500)` (makloon_order_service.py:1687) |
| Eskalasi gudang | manager/EscalationManagement.jsx | ✗ | chip jenis (klien) | – | ✗ | ✗ | – | ✓/✓/✓ | inbound `to_list(200)` (+PO `to_list(100)`), outbound `to_list(200)` |
| Scanner WMS | wms/ScannerTaskPanel.jsx | — | — | — | — | — | — | — | **tidak diimpor di mana pun** (kode mati, data contoh `wh_jakarta`) |

## B.4 RFID · antrean periksa gate (D2) · pengaturan · aplikasi HP

| Layar | Berkas | Cari | Saring | Urut | Halaman | Ekspor | Massal | K/M/G | GET (batas / proyeksi) |
|---|---|---|---|---|---|---|---|---|---|
| Tag aktif | rfid/RfidTagsView.jsx:120-148 | ✓ | gudang | ✗ | klien 25 | ✗ | ✗ | ✓/✓/✓ | /rfid/tags `to_list(1000)` tanpa proyeksi (rfid_service.py:66); label tab "(1000)" terpotong diam |
| Belum ber-tag | RfidTagsView.jsx:151-180 | ✓ | gudang | ✗ | klien | ✗ | encode otomatis ≤200 (bukan pilihan pengguna) | ✓/✓/✓ | /rfid/untagged-rolls 500, berproyeksi |
| Roll siap cetak | rfid/RfidPrintVerifyPanel.jsx:157-182 | **✗** | gudang | ✗ | ✗ (gulir) | ✗ | pilih semua | ✓/✗/✓ | idem 500 |
| Print job | RfidPrintVerifyPanel.jsx:185-211 | ✗ | gudang (**hilang setelah buka job**, :69) | ✗ | ✗ | ✗ | – | ✓/✗/✓ | /rfid/print-jobs 100; API punya `status`, UI tak memakai |
| Aktivitas gate | rfid/RfidGateMonitorView.jsx:224-241 | ✓ (25 baris) | gudang / gate | ✗ | klien; `next_before` tak dipakai | ✗ | – | ✓/✓/senyap saat polling | /rfid/reads limit 25 (maks 300) |
| Riwayat lintasan | rfid/GatePassageHistory.jsx | ✗ | gate/gudang | ✗ | kursor 15 | ✗ | – | kosong = juga saat memuat | /rfid/passages ≤100; reads `to_list(3000)` |
| **D2 Antrean periksa gate** | rfid/GateReviewQueue.jsx:19-104 | **✗** (tidak bisa cari roll/no. dokumen) | 4 `KNSelect`: status, hasil, jenis, gate | waktu desc (server) | **✗** — minta `limit: 100`, `next_before` dari server **tidak dipakai** → baris ke-101 dst. tak terjangkau tanpa penanda | ✗ (pusat ekspor juga tak punya dataset `rfid_v2_reviews`) | (di rincian: centang per roll, tanpa "pilih semua") | ✓/✓/✓ (ErrorNotice + coba lagi) | /rfid/v2/ops/reviews `limit` le=100 + kursor `before` ✓, proyeksi `actions:0` ✓ (gate_review_service.py:297); ringkasan agregat ✓ |
| Insiden | rfid/RfidSecurityPanel.jsx:61-116 | ✗ | status | ✗ | ✗ (100 terpotong) | ✗ | – | ✓/✗/✓ | /rfid/incidents `limit` tanpa maks (rfid.py:630) |
| Shrinkage / kesehatan | RfidSecurityPanel.jsx:118-160 | ✗ | **mengabaikan gudang** | ✗ | ✗ | ✗ | – | ✓ | device-health `to_list(200)` |
| Lokasi tag | rfid/RfidLocationsView.jsx:114-140 | ✓ | gudang (status tak bisa disaring) | ✗ | klien 25 | ✗ | – | ✓/✓/✓ | /rfid/locations 1000 |
| Daftar perangkat | rfid/RfidDevicesView.jsx:217-284 | ✗ | gudang | kode | ✗ | ✗ | buat bawaan | ✓/✓/✓ | /rfid/devices 500 |
| Riwayat opname RFID | rfid/CycleCountPanel.jsx:107-121 | ✗ | gudang | ✗ | ✗ (30) | ✗ | – | galat **ditelan** (:23) | /rfid/cycle-counts 30; detail tak bisa dibuka |
| Lintasan U300 | rfid/U300PassageList.jsx | ✗ | ✗ | ✗ | kursor 50 | per baris JSON bukti | – | ✓ | v2 overview le=100 + kursor (baik) |
| Dokumen U300 | rfid/U300DocSession.jsx:105-114 | ✗ | jenis | ✗ | ✗ | – | ≤20 | ✓ | sources 200 |
| Kartu setelan | settings/cfg/SettingsGroupView · SettingsHub | ✓ | chip kelompok | – | ✗ | – | – | ✓ | /config/effective |
| **HP** tugas (masuk/keluar/sample) | mobile/MobileWarehouseApp.jsx:39-104 | ✓ bila >5 | **✗** (gudang/status) | terbaru | **✗** (semua dirender) | ✗ | – | ✓/✓/✓ | /wms/tasks `to_list(2000)` + 200 dokumen penuh termasuk `scan_log` (wms.py:38-41) |
| **HP** belum tag | MobileWarehouseApp.jsx:204-242 | ✓ | ✗ | ✗ | "+30 lagi" | ✗ | – | ✓ | 500 |

## B.5 Inventaris endpoint GET daftar (otomatis)

`scripts/audit/b3b_crossref.py` → 197 endpoint GET tanpa `{id}` di ujung pada 39 router cakupan:
**178 tanpa parameter halaman sama sekali** (batas keras di service: 100/200/300/500/1000/2000/3000/5000),
**17 punya `limit` tanpa `maximum`** (klien bisa meminta `limit=100000` atau `limit=-1`):
`/api/goods-receipts`, `/api/putaway-orders`, `/api/inventory/rolls` (bawaan 5000), `/api/inventory/rolls/available`,
`/api/inventory/rolls-without-cost`, `/api/inventory/putaway/suggest`, `/api/inventory/low-stock-summary`,
`/api/lots`, `/api/lots/unassigned-rolls`, `/api/makloon-orders/claims`, `/api/rfid/reads`, `/api/rfid/passages`,
`/api/rfid/incidents`, `/api/interco/transactions|settlements|returns`, `/api/config/history`.
Yang memakai halaman server baku (`pagination.py`, `?page=&page_size=`): hanya `inspections`, `inventory`
(roll/mutasi), `lots`, `purchase_orders`, `purchase_returns`, `sales_returns` — plus kursor `before` di
`rfid/reads`, `rfid/passages`, `rfid/v2/ops/reviews`, `rfid/v2` overview dan `page` sendiri di `logistics/history`.

## B.6 Rekap pola daftar (cakupan WMS-RFID, ±55 layar daftar)

| Fitur | Ada | Tidak / tidak lengkap |
|---|---|---|
| Halaman dari server | 9 | ±46 (klien memotong, atau semua dirender, atau batas keras diam) |
| Kotak cari | ±30 (banyak klien-saja) | ±25 |
| Urut yang bisa dipilih pengguna | 1 (`DeliveryTable`) | semua lainnya urutan tetap |
| Ekspor CSV standar (`utils/csvExport.js`) | 6 (SPK, roll, mutasi, lot, retur jual, retur beli) | – |
| Ekspor CSV non-standar | 2 (logistik: `,` tanpa BOM, baris tampil) | – |
| Ekspor XLSX | **0** | semua |
| Pilih massal | ±8 | – |
| Keadaan kosong palsu / galat senyap | – | ±10 |

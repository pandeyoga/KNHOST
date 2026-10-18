# Laporan Fase P00 — Baseline, keputusan bisnis, dan kontrak antarmodul

## Identitas

- Branch dan commit baseline: `main` @ `96f73fa` (actual HEAD saat P00). Rujukan paket `f59b8a60d7b7e078888c537ca93c046afae460a9` **ada di riwayat repo**; jarak `f59b8a6..96f73fa` = 4 commit (perubahan Pelacak SO/desk & lockfile, tidak menyentuh fungsi WMS yang di-probe).
- Commit implementasi: tidak ada perubahan kode aplikasi pada P00 (diagnosis saja).
- Commit yang diuji: `96f73fa` (probe) dan `f59b8a6` (probe pembanding, via git worktree sementara).
- Pelaksana: agent developer. Reviewer/validator: belum ditetapkan.
- Tanggal dan lingkungan uji: 2026-10-11, container preview; probe = eksekusi fungsi asli terisolasi dengan DB in-memory (tanpa app live/DB nyata).
- IMP serta DEV-F/DEV-G yang dicakup: lintas IMP (baseline); DEV-F01–F05, DEV-G01–G06.
- Status: **in_progress** (baseline, reproduksi DEV-F/G, inventaris sumber kebenaran, matriks consumer awal, kamus metrik draf, data acuan dan simulasi bin + dry-run selesai; contoh data UAT lintas entitas/lokasi belum).

## Data acuan development (keputusan pemilik 2026-10-11)

- Data VPS = data seed repo. Data acuan **semua fase** = urutan skrip resmi `deploy/setup_demo_lengkap.sh`: `import_master_produk_kn.py` → `import_stok_awal_kn.py` → `seed_demo_lengkap_kn.py` → `seed_demo_transaksi_kn.py` → `seed_demo_harga_internal_kn.py` → `seed_simulasi_bin_kn.py`.
- Konsekuensi: dry-run/diagnosis data dijalankan pada DB preview dan dianggap mewakili VPS; dump VPS **tidak diperlukan**.
- Bin nyata di lapangan belum ada → **disimulasikan (MOCK)** oleh `backend/scripts/seed_simulasi_bin_kn.py`: WH-JKT, RCM-WOVEN, RCM-KNITTING format baru (zona → rak → level → bin), gudang lain format lama (rak → bin); zona per satuan (W = yard kapasitas 6.000, K = kg kapasitas 1.500, isi maks 90%); ±80% roll fisik ditempatkan (deterministik per id roll) dengan mutasi `putaway` bertanda `sim_batch`, ±20% belum ditempatkan. Bin id deterministik per kode gudang (`bin_sim_<gudang>_<kode>`) sehingga preview dan VPS sama.
- Sampel bermasalah untuk uji P02 (WH-JKT, field `sim_anomaly`): 3 roll bin tidak ada di master, 2 roll kg di bin yard (satuan campur), 3 roll `in_transit_sales` ber-bin, 1 bin `W-OVER-01` berisi 4 roll melebihi kapasitas. Hapus: `--hapus-anomali`; batalkan seluruh simulasi: `--hapus-semua`.
- Fase berikutnya yang butuh data tambahan wajib menambah skrip seed idempoten ke `setup_demo_lengkap.sh` (bukan mengubah data manual), agar preview dan VPS tetap sinkron.

## Runtime & kemampuan platform

| Item | Nilai |
|---|---|
| Backend | FastAPI (Python 3.11), Motor; `backend/pytest.ini` dengan xdist |
| Frontend | React (CRA), Yarn 1.22.22; lock `frontend/yarn.lock` = `deploy/frontend-yarnlock.txt` |
| Database | MongoDB **7.0.43 standalone** (`rs.status` → NoReplicationEnabled) → **tidak ada transaksi multi-dokumen**; idempotensi memakai marker/CAS/id deterministik (pola Gelombang 3) |
| Deployment UAT | VPS `kainnusantara.cloud` via `deploy/update.sh` (Docker compose) — tidak disentuh agent |

## Hasil reproduksi DEV-F / DEV-G pada `96f73fa`

Probe paket (`sources/wms-developer-2026-10-08/wms-focused-probes.py`) dijalankan tanpa perubahan logika pada kedua commit. Hasil identik: 8 isu tereproduksi (5 defect, 3 capability/business gap), 1 kontrol existing tetap berfungsi. Bukti: [`wms-probes-head-96f73fa.json`](wms-probes-head-96f73fa.json), [`wms-probes-baseline-f59b8a6.json`](wms-probes-baseline-f59b8a6.json). Catatan: field `source_commit` di JSON head tertulis hardcode f59b8a6 oleh skrip; eksekusi head memakai `WMS_AUDIT_REPO=/app` dengan assert commit dilepas.

| ID | Probe | Status di 96f73fa | Pengamatan | Fase |
|---|---|---|---|---|
| DEV-F01 | P01-scan-modern-bin | **masih berlaku** | scan bin `BIN-01` pada `rack.levels[].bins` → 400 "tidak ada di master" | P02 |
| DEV-F02 | P02-delete-occupied-bin | **masih berlaku** | hapus bin berisi 100 → okupansi 0, unassigned 0, qty roll tetap 100 (stok "hilang" dari dashboard) | P02 |
| DEV-F03 | P03-mixed-uom-occupancy | **masih berlaku** | 100 m + 100 kg dilaporkan 200, utilisasi 400%, label "m" | P02/P08 |
| DEV-F04 | P05-putaway-transit-roll | **masih berlaku** | roll `in_transit_transfer` diterima ke bin | P02/P03 |
| DEV-F05 | P06-pa-dedicated-destination | **masih berlaku** | PA owner ent-a ke gudang dedicated ent-b → `open` | P02 |
| DEV-G01 | P04-putaway-over-capacity | **masih berlaku** (gap) | roll 100 ke bin kapasitas 50 diterima; kebijakan kapasitas = DEC-10 | P02 |
| DEV-G02 | P07-rules-category-plus-grade | **masih berlaku** (gap) | rules Woven + grade A menerima BS | P02 |
| DEV-G03 | P08-so-reservation-to-transfer | **masih berlaku** (gap) | roll reserved SO → transfer 409; jalur transfer-terkait-SO belum ada (DEC-11) | P03 |
| DEV-G04 | telaah kode | **masih berlaku** | `routers/transfers.py::create_transfer` & `roll_service.receive_wh_transfer_rolls` tidak memanggil evaluator storage rules (hanya `putaway_order_service`, `warehouse_profile_service`, `routers/warehouses.py`) | P02/P03 |
| DEV-G05 | telaah kode | **masih berlaku** | `schemas.TransferStatusUpdate` hanya `status`, `updated_by`; `completed` menerima seluruh roll in-transit tanpa receipt per roll | P03 |
| DEV-G06 | telaah kode | **masih berlaku** | `location_service.warehouse_locations` tanpa ringkasan semua node/daftar orphan | P02/P08 |
| C01 | inspection hold | kontrol existing **tetap** | putaway roll hold inspeksi → 400 | dipertahankan |

## Inventaris sumber kebenaran (awal)

| Domain | Sumber otoritatif | Jumlah modul pembaca/penulis (services+routers) |
|---|---|---|
| Roll fisik (qty, status, owner, gudang, bin, reservasi) | `inventory_rolls` (+ `inventory_movements` event) | 60 file; 30 file melakukan update langsung |
| Saldo/proyeksi | `inventory_balances`, `fulfillment_service.status_board` (ATP) | 22 |
| Lokasi | `warehouses` (struktur zone/rack/level/bin) via `location_service` | 51 |
| Transfer | `warehouse_transfers` | 29 |
| Demand/SO | `sales_orders` (`allocations`, `backorders`, `items`) | 77 |
| Tugas gudang | `wms_tasks` | 44 |
| Pengiriman | `shipments` | 16 |
| Master barang | `products` (+ alias/spec) | 99 |
| Absensi | `hr_attendance` (agregat), `hr_employees`, `hr_payroll_runs` | 20 / 41 / 26 |

Risiko kontrak: 30 file menulis langsung ke `inventory_rolls` → perubahan status/qty pada P02–P04 wajib melalui layanan bersama.

## Kontrak & kamus metrik (draf — usulan, bukan keputusan)

| Metrik | Formula saat ini (kode) | Status keputusan |
|---|---|---|
| ATP | tersedia + incoming(horizon 14 hari) − permintaan tertunda (`atp_policy.compute_atp`) | dikonfirmasi pemilik 2026-10-06 (G3 D4-TEST-01) |
| Keep | belum ada definisi tunggal | **DEC-01 open** |
| Pending | backorder aktif (`ACTIVE_BACKORDER_STATUSES`) | **DEC-01 open** |
| Qty SO | ordered / allocated / shipped terpisah per baris; physically received belum ada untuk transfer | kontrak usulan P03/P04 |

## Keputusan bisnis

Sesuai pilihan pemilik: keputusan ditanyakan **per fase**. Tidak ada DEC yang ditandai confirmed oleh P00. DEC-14: unit fingerprint **belum tersedia** → P09 memakai simulator, item perangkat nyata `waiting_hardware`.

## Migrasi dan rekonsiliasi

P00 tidak mengubah stok, HPP, atau jurnal. Satu-satunya perubahan data: simulasi bin (hanya `inventory_rolls.bin_id`, struktur `warehouses.zones`, mutasi `putaway` qty 0) — tidak memengaruhi saldo per produk×gudang×owner. Dapat dibatalkan penuh dengan `seed_simulasi_bin_kn.py --hapus-semua`.

## Hasil pengujian

| ACC/test | Perintah/langkah dan lingkungan | Input/fixture | Expected vs actual | Hasil | Evidence |
|---|---|---|---|---|---|
| ACC-00 (sebagian) | git rev-parse, rs.status, probe paket pada 96f73fa & f59b8a6 | fixture in-memory probe | baseline tercatat; 8/8 isu tereproduksi identik di kedua commit | pass (baseline) | JSON di folder ini |

## Matriks layar/consumer per IMP (awal — folder `frontend/src/features/*`, rute backend terkait)

| IMP | Fase | Layar/consumer utama yang terdampak |
|---|---|---|
| IMP-01 | P08 | `desks/RoleDesk`, `sales_admin/SalesAdminDesk`, `finance/FinanceDesk`, `samples/SampleAdminDesk`, `sales_admin/DeskQueueCard` + `services/work_desk_service`, `role_desk_service` |
| IMP-02, 03 | P04 | `sales`, `sales_admin` (Pending SO), `orders` + `fulfillment_service`, `atp_policy` |
| IMP-04, 05, 06 | P04 | `orders`, `sales`, `sales_admin/FulfillmentDecisionDialog`, `pdf` (dokumen SO/SJ/invoice) + `roll_service`, `sales_orders*` |
| IMP-07, 08 | P06 | `orders` (Special Order/OD), `design`, `designer`, `rnd` + `po_*`, `rnd_*` |
| IMP-09, 10 | P07 | `samples`, `sales`, `production` (cutting) |
| IMP-11 | P04 | `pricing`, `sales`, `catalog` + `pricing_service` |
| IMP-12–15 | P01 | `catalog`, `settings`, `purchasing` (supplier/alias), `admin` (master) |
| IMP-16, 17 | P05 | `inspections`, `rnd`, `catalog` |
| IMP-18 | P05 | `production` (makloon), `inventory` + `makloon_*` |
| IMP-19 | P05 | `purchasing`, `sales_admin` (backorder) |
| IMP-20 | P01 | `wms`, `rfid`, `mobile`, `admin` (role/user) + `warehouse_scope_service` |
| IMP-21 | P03 | `wms` (inbound/OCR), `documents` |
| IMP-22–25 | P02 | `wms` (putaway, struktur gudang), `rfid`, `mobile` + `location_service`, `putaway_order_service`, `warehouse_profile_service` |
| IMP-26, 27 | P03 | `transfers`, `wms`, `logistics` + `routers/transfers.py`, `roll_service.receive_wh_transfer_rolls` |
| IMP-28, 29 | P08 | `inventory` (opname, stok berjenjang), `rfid` (cycle count), `wms` (health) |
| IMP-30–35 | P09 | `hr` (absensi/monitoring) + `hr_attendance`, receiver baru; perangkat nyata = waiting_hardware |

Matriks ini adalah inventaris awal tingkat modul; daftar file/consumer final per IMP disusun di awal tiap fase sebelum perubahan.

## Dry-run diagnosis data (read-only, DB preview)

| Cek | Hasil |
|---|---|
| Sebelum simulasi | 46.487 roll (12 gudang), roll ber-bin **0** |
| Sesudah simulasi — bin | 934 bin (3 gudang format baru+lama, 9 gudang format lama) |
| Roll fisik / ber-bin / belum ditempatkan | 46.428 / 37.105 (79,9%) / 9.323 |
| Roll orphan bin | 3 (WH-JKT, sampel) |
| Bin satuan campur | 1 (WH-JKT, sampel) |
| Roll in-transit ber-bin | 3 (WH-JKT, sampel) |
| Bin melebihi kapasitas | 1 (WH-JKT `W-OVER-01`, sampel) |

Perintah: `python scripts/seed_simulasi_bin_kn.py --cek --json <file>` (read-only). Bukti: [`dry-run-bin-simulasi.json`](dry-run-bin-simulasi.json). Kesimpulan: data acuan kini representatif untuk P02; diagnosis hanya menemukan sampel bertanda (tidak ada anomali di luar sampel). Endpoint `GET /api/warehouses/wh_jakarta/locations` mengembalikan 283 bin, unassigned 4.650 roll. Catatan: scan bin di gudang format baru masih ditolak (DEV-F01) sampai diperbaiki di P02.

## Risiko dan issue terbuka

1. Contoh data UAT lintas entitas/lokasi belum disiapkan (sisa P00).
2. ~~Dry-run pada salinan data VPS~~ — ditutup: data VPS = data acuan repo; dry-run dijalankan di preview dengan simulasi bin.
3. Tanpa transaksi Mongo: perubahan P02–P04 wajib idempoten + rekonsiliasi.

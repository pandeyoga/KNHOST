# Cek ulang temuan di HEAD — paket 2026-10-20

- Dikerjakan: 2026-10-20 oleh Claude Code (implementer)
- Commit yang dicek: `f4e8f0b` (kode aplikasi; commit `4b2d046` sesudahnya hanya setup dev & dokumen)
- Baseline paket: FE `8dab383` (17 commit di belakang) · AUD `63c38bd` (42 commit di belakang)

## Metode dan batasnya

1. `git diff --numstat <baseline> f4e8f0b` untuk setiap berkas yang disebut laporan.
2. Berkas yang berubah: diff dibaca untuk memastikan apakah menyentuh jalur temuan.
3. Pola kode penyebab dicari ulang di HEAD dan dicatat nomor barisnya.

**Ini cek tingkat kode, bukan reproduksi runtime.** Lingkungan Docker lokal masih dibangun
saat cek ini dibuat. Reproduksi HTTP/browser per temuan dilakukan saat fase perbaikannya
dikerjakan, dan hasilnya dicatat di laporan fase (`hasil/<FASE>.md`).

## Ringkasan

| Kelompok | Masih berlaku (kode) | Sudah diperbaiki | Tidak dapat dicek |
|---|---|---|---|
| FE-01..FE-13 | 13 | 0 | 0 |
| AUD-* (12, termasuk AUD-RND-03 observasi) | 12 | 0 | 0 |

Tidak ada temuan yang ikut terselesaikan oleh 17/42 commit sesudah baseline.

## Frontend (baseline `8dab383`)

| ID | Berkas penyebab: perubahan sejak baseline | Bukti di HEAD `f4e8f0b` |
|---|---|---|
| FE-01 | `special_order_phase2.py` tidak berubah; `special_orders.py` +53 (endpoint baru batal pengadaan per item, bukan konversi); `SpecialOrderPricingPanel.jsx` +2/−1 (pilih PO aktif) | `special_order_phase2.py:283` qty dari `custom_item.quantity`; `special_orders.py:1087-1094` `SalesOrderCreate` dengan **satu** `SalesOrderItemIn` dari `custom_item` |
| FE-02 | `KNSelect.jsx` & ketiga berkas Interco tidak berubah | `KNSelect.jsx:151` menerima `onValueChange`; pemanggil memakai `onChange` di `IntercoCreateModal.jsx:109,112,115,118`, `IntercoPanels.jsx:32`, `IntercoSettlementModal.jsx:107,111,115`, dan pilihan produk `IntercoCreateModal.jsx:137-139` — sembilan lokasi |
| FE-03 | `access_modules.py` +5/−4 (hanya menambah `gl_mapping` ke modul akuntansi); `navStructure.js`, `navigationConfig.js` tidak berubah | Modul `interco` (`access_modules.py:56-59`) & `warehouse_ops` (`:74-79`) identik dengan baseline |
| FE-04 | Semua berkas contoh tidak berubah kecuali `InspectionDetailPanel.jsx` +2/−1 (label grade) | `SpecialOrders.jsx:118`, `InspectionsView.jsx:73`, `GoodsReceiptsView.jsx:14`, `TransferDetailModal.jsx:219`, `PaymentVarianceQueue.jsx:53` masih memakai daftar nama role literal |
| FE-05 | `warehouses.py`, `warehouseApi.js`, `WarehouseMasterView.jsx` tidak berubah | `warehouses.py:36` `MASTER_SCOPE_ROLES = {"admin","manager","warehouse"}`, `:165` menolak role lain; `warehouseApi.js:12` meminta `scope: "all"` |
| FE-06 | `workDeskApi.js` +4 (target tugas terima gudang), `role_desk_service.py` +11/−4 (qty tugas gudang), `AppViewRouter.jsx` +2 (view pemetaan akun) — tidak menyentuh harga khusus | `workDeskApi.js:217` `price_approval → view "approvals"`; renderer hanya `price-approvals` (`AppViewRouter.jsx:347`) |
| FE-07 | `SalesReturns.jsx` +2/−2 & `ReturnSettleModal.jsx` +13/−1 (opsi payout KLR-10) — pola error tetap | `SalesReturns.jsx` `handleSettle` menangkap error tanpa melempar ulang; `ReturnSettleModal.jsx:64-67` `await onSettle(...)` lalu `onClose()`; detail di-render lewat `if (selected)` (`SalesReturns.jsx:218`) |
| FE-08 | `CreateReturnForm.jsx` tidak berubah | `handleOrderChange` memasang respons tanpa memeriksa SO yang masih aktif |
| FE-09 | `SalesReturns.jsx` +2/−2 (bukan pemilih); `sales_orders_extra.py` +3 (hook batal pengganti retur) | `SalesReturns.jsx:110` `GET /sales-orders` tanpa paging; `sales_orders_extra.py:183` `.to_list(200)` |
| FE-10 | `QCInspection.jsx`, `inbound_receiving_extra.py`, `qc_service.py` tidak berubah | `QCInspection.jsx:76` total dijumlah tanpa unit; label `m` di `:142,193,219` |
| FE-11 | `TransferReceiptPanel.jsx` tidak berubah | `:55` `if (!data) return …Memuat…` sebelum `ErrorNotice` di `:101` |
| FE-12 | `FinancialStatementsParts.jsx`, `FinancialStatementsView.jsx` tidak berubah | `FinancialStatementsParts.jsx:113` `const ok = balanced !== false` |
| FE-13 | `CashFlowForecastView.jsx` tidak berubah | `:70` `formatter={(v, n) => [formatCurrency(Math.abs(v)), n]}` untuk semua seri |

## Backend (baseline `63c38bd`)

| ID | Berkas penyebab: perubahan sejak baseline | Bukti di HEAD `f4e8f0b` |
|---|---|---|
| AUD-RND-01 | `rnd_revalidation_service.py` tidak berubah | `decide` di `:112` |
| AUD-RND-02 | idem | `existing_artwork` di `:43` |
| AUD-RND-03 | idem | `_validate_contract_ref` di `:83` — tetap `pending_decision` (aturan bisnis kontrak terminated) |
| AUD-EXP-01 | `export_engine.py`, `routers/export_center.py` tidak berubah | `download_job` `export_center.py:199`, penolakan 403 `:218` |
| AUD-EXP-02 | `export_engine.py` tidak berubah | `fetch` `:332`, `write_file` `:395` |
| AUD-SO-01 | `special_order_fulfillment.py` tidak berubah | `_claim` `:279`, `_release` `:289` |
| AUD-WMS-01 | `stock_count_roll_service.py` +1/−1 (docstring OPS-01 saja) | `apply_scan` `:167` tidak berubah |
| AUD-MKL-01 | `supplier_contracts.py`, `makloon_recap_service.py` tidak berubah | `makloon_claim_recap_xlsx` `supplier_contracts.py:218` |
| AUD-MKL-02 | `makloon_recap_service.py` tidak berubah | `:97` `"rows": rows[:1000]` |
| AUD-MIG-01 | `scripts/migrate_l03_ln033_fulfillment.py` tidak berubah | cabang apply di `main` |
| AUD-MIG-02 | idem | cabang rollback `:50` |
| AUD-RET-01 | `return_disposition_service.py` +4/−1 di fungsi `view` (tanggal klaim KLR-09) — bukan jalur buang | `_stage` `:41`, `_dispose` `:213`, `decide_supplier` `:238` tidak berubah |

## Catatan untuk reviewer

- Nomor baris laporan FE sebagian bergeser beberapa baris; isi kode penyebabnya sama.
- Status tracker tidak diubah oleh cek ini (`open` tetap `open`); kolom "Berlaku di HEAD"
  diisi `ya (kode)`. Statusnya berubah menjadi `in_progress` saat fasenya mulai dikerjakan.

# Bukti cakupan runtime dan endpoint

Snapshot `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. Trace mencatat baris yang dijalankan, bukan seluruh cabang. Status endpoint berasal dari aplikasi ASGI asli dengan payload sintetis. Mode tanpa permission memakai user audit_no_permissions dengan matriks kosong dan akses entitas A. Logout dilewati dalam mode tersebut. Tidak semua respons 200 adalah celah; respons 403 juga belum membuktikan seluruh pembatasan objek benar.

## Setiap endpoint

| Method | Template | Tanpa login | User tanpa permission |
|---|---|---|---|
| POST | `/api/auth/login` | 401 | 401 |
| GET | `/api/roles` | 401 | 200 |
| GET | `/api/auth/me` | 401 | 200 |
| GET | `/api/auth/context` | 401 | 200 |
| POST | `/api/auth/logout` | 200 | SKIP |
| GET | `/api/users` | 401 | 403 |
| GET | `/api/users/count` | 401 | 403 |
| GET | `/api/hr-employees-available` | 401 | 403 |
| GET | `/api/users/{user_id}` | 401 | 403 |
| POST | `/api/users` | 401 | 403 |
| PATCH | `/api/users/{user_id}` | 401 | 403 |
| DELETE | `/api/users/{user_id}` | 401 | 403 |
| POST | `/api/users/{user_id}/reactivate` | 401 | 403 |
| POST | `/api/users/{user_id}/reset-password` | 401 | 403 |
| POST | `/api/users/{user_id}/revoke-sessions` | 401 | 403 |
| GET | `/api/dashboard` | 401 | 200 |
| GET | `/api/products` | 401 | 403 |
| POST | `/api/products` | 401 | 403 |
| PATCH | `/api/products/{product_id}` | 401 | 403 |
| GET | `/api/products/sales-owners` | 401 | 403 |
| DELETE | `/api/products/{product_id}` | 401 | 403 |
| GET | `/api/products/{product_id}/stock-breakdown` | 401 | 403 |
| GET | `/api/customers` | 401 | 403 |
| POST | `/api/customers` | 401 | 403 |
| PATCH | `/api/customers/{customer_id}` | 401 | 403 |
| POST | `/api/customers/{customer_id}/addresses` | 401 | 403 |
| GET | `/api/warehouses/{warehouse_id}/locations` | 401 | 403 |
| GET | `/api/warehouses/{warehouse_id}/occupancy` | 401 | 403 |
| PUT | `/api/warehouses/{warehouse_id}/structure` | 401 | 403 |
| GET | `/api/warehouses` | 401 | 403 |
| POST | `/api/warehouses` | 401 | 403 |
| PATCH | `/api/warehouses/{warehouse_id}` | 401 | 403 |
| DELETE | `/api/warehouses/{warehouse_id}` | 401 | 403 |
| GET | `/api/uoms` | 401 | 403 |
| GET | `/api/uoms/vocab` | 401 | 403 |
| POST | `/api/uoms` | 401 | 403 |
| PATCH | `/api/uoms/{uom_id}` | 401 | 403 |
| DELETE | `/api/uoms/{uom_id}` | 401 | 403 |
| GET | `/api/inventory/rolls/{roll_id}/journey-timeline` | 401 | 403 |
| GET | `/api/inventory/rolls/{roll_id}/cost-history` | 401 | 403 |
| GET | `/api/inventory/putaway/queue` | 401 | 403 |
| POST | `/api/inventory/putaway` | 401 | 403 |
| GET | `/api/inventory/stock-analytics` | 401 | 403 |
| GET | `/api/inventory/status-board` | 401 | 403 |
| GET | `/api/inventory/balances` | 401 | 403 |
| GET | `/api/inventory/rolls` | 401 | 403 |
| GET | `/api/inventory/rolls/available` | 401 | 403 |
| GET | `/api/inventory/movements` | 401 | 403 |
| GET | `/api/inventory/rolls-without-cost` | 401 | 403 |
| PATCH | `/api/inventory/rolls/{roll_id}/opening-cost` | 401 | 403 |
| POST | `/api/inventory/initial-stock` | 401 | 403 |
| GET | `/api/history/{product_id}` | 401 | 403 |
| POST | `/api/sales-orders/preview-allocation` | 401 | 403 |
| POST | `/api/sales-orders/preview-lots` | 401 | 403 |
| GET | `/api/sales-orders` | 401 | 403 |
| GET | `/api/sales-orders/stats/summary` | 401 | 403 |
| GET | `/api/sales-orders/frequent-products` | 401 | 403 |
| GET | `/api/sales-orders/{order_id}/journey` | 401 | 403 |
| POST | `/api/sales-orders/preview-roll-reconcile` | 401 | 403 |
| GET | `/api/sales-orders/{order_id}/restock-state` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/repeat-restock` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/submit-for-approval` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/approve` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/confirm` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/mark-delivered` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/items/{product_id}/reallocate` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/items/{product_id}/release-rolls` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/release-reservation` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/cancel` | 401 | 403 |
| POST | `/api/sales-orders` | 401 | 403 |
| GET | `/api/sales-orders/{order_id}` | 401 | 403 |
| PATCH | `/api/sales-orders/{order_id}` | 401 | 403 |
| GET | `/api/invoices` | 401 | 403 |
| GET | `/api/sales-orders/{order_id}/invoices` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/simulate-payment` | 401 | 403 |
| GET | `/api/wms/tasks` | 401 | 403 |
| POST | `/api/wms/tasks` | 401 | 403 |
| POST | `/api/wms/tasks/outbound-from-order/{order_id}` | 401 | 403 |
| POST | `/api/wms/tasks/{task_id}/scan` | 401 | 403 |
| POST | `/api/wms/tasks/{task_id}/advance` | 401 | 403 |
| GET | `/api/documents/trace/{doc_type}/{doc_id}` | 401 | 403 |
| GET | `/api/documents/trace/{doc_type}/{doc_id}/print` | 401 | 403 |
| GET | `/api/documents/refs/{doc_type}/{doc_id}` | 401 | 403 |
| GET | `/api/documents/trace-search` | 401 | 403 |
| GET | `/api/documents/ref-types` | 401 | 403 |
| POST | `/api/documents/refs/backfill` | 401 | 403 |
| GET | `/api/documents/relations/{doc_type}/{doc_id}` | 401 | 403 |
| GET | `/api/document-templates` | 401 | 403 |
| POST | `/api/document-templates` | 401 | 403 |
| PATCH | `/api/document-templates/{template_id}` | 401 | 403 |
| DELETE | `/api/document-templates/{template_id}` | 401 | 403 |
| POST | `/api/documents/generate` | 401 | 403 |
| GET | `/api/documents/{doc_id}/print` | 401 | 403 |
| GET | `/api/documents/preview/{order_id}` | 401 | 403 |
| POST | `/api/documents/barcode` | 401 | 403 |
| GET | `/api/documents/resolve` | 401 | 404 |
| POST | `/api/master-data/import-products` | 401 | 403 |
| POST | `/api/master-data/import-customers` | 401 | 403 |
| POST | `/api/master-data/import-warehouses` | 401 | 403 |
| GET | `/api/master-data/export-products` | 401 | 403 |
| GET | `/api/master-data/export-yarn` | 401 | 403 |
| GET | `/api/master-data/export-customers` | 401 | 403 |
| GET | `/api/master-data/export-warehouses` | 401 | 403 |
| GET | `/api/permissions` | 401 | 403 |
| PUT | `/api/permissions` | 401 | 403 |
| POST | `/api/admin/seed-demo` | 401 | 403 |
| GET | `/api/reports/stock-aging` | 401 | 403 |
| GET | `/api/reports/reservation-funnel` | 401 | 403 |
| GET | `/api/reports/order-velocity` | 401 | 403 |
| GET | `/api/reports/top-customers` | 401 | 403 |
| GET | `/api/reports/warehouse-utilization` | 401 | 403 |
| GET | `/api/reports/summary` | 401 | 403 |
| GET | `/api/audit-logs` | 401 | 403 |
| POST | `/api/cycle-count/sessions` | 401 | 403 |
| GET | `/api/cycle-count/sessions` | 401 | 403 |
| GET | `/api/cycle-count/sessions/{session_id}` | 401 | 403 |
| POST | `/api/cycle-count/sessions/{session_id}/items` | 401 | 403 |
| PATCH | `/api/cycle-count/sessions/{session_id}/items/{item_id}` | 401 | 403 |
| POST | `/api/cycle-count/sessions/{session_id}/submit` | 401 | 403 |
| POST | `/api/cycle-count/sessions/{session_id}/approve` | 401 | 403 |
| POST | `/api/cycle-count/sessions/{session_id}/reject` | 401 | 403 |
| GET | `/api/onboarding` | 401 | 200 |
| POST | `/api/onboarding/{task_id}/complete` | 401 | 404 |
| POST | `/api/onboarding/reset` | 401 | 200 |
| POST | `/api/labels/generate` | 401 | 403 |
| POST | `/api/labels/preview` | 401 | 403 |
| GET | `/api/transfers` | 401 | 403 |
| POST | `/api/transfers` | 401 | 403 |
| POST | `/api/transfers/inter-company` | 401 | 403 |
| GET | `/api/transfers/{transfer_id}` | 401 | 403 |
| POST | `/api/transfers/{transfer_id}/approve` | 401 | 403 |
| POST | `/api/transfers/{transfer_id}/reject` | 401 | 403 |
| POST | `/api/transfers/{transfer_id}/status` | 401 | 403 |
| DELETE | `/api/transfers/{transfer_id}` | 401 | 403 |
| GET | `/api/purchase-orders/board` | 401 | 403 |
| PATCH | `/api/purchase-orders/{po_id}/stage` | 401 | 403 |
| POST | `/api/purchase-orders/blanket` | 401 | 403 |
| GET | `/api/purchase-orders/blanket` | 401 | 403 |
| POST | `/api/purchase-orders/{blanket_id}/call-off` | 401 | 403 |
| POST | `/api/purchase-orders/{blanket_id}/close-contract` | 401 | 403 |
| POST | `/api/purchase-orders/{po_id}/pay` | 401 | 403 |
| POST | `/api/purchase-orders/{po_id}/close` | 401 | 403 |
| GET | `/api/purchase-orders/payables/summary` | 401 | 403 |
| POST | `/api/purchase-orders/{po_id}/cancel` | 401 | 403 |
| GET | `/api/purchase-orders` | 401 | 403 |
| POST | `/api/purchase-orders` | 401 | 403 |
| GET | `/api/purchase-orders/resolve-sourcing` | 401 | 400 |
| POST | `/api/purchase-orders/{po_id}/amend` | 401 | 403 |
| POST | `/api/purchase-orders/{po_id}/approve` | 401 | 404 |
| POST | `/api/purchase-orders/{po_id}/reject` | 401 | 404 |
| GET | `/api/purchase-orders/{po_id}` | 401 | 403 |
| GET | `/api/inbound/tasks/{task_id}/uom-options` | 401 | 403 |
| POST | `/api/inbound/tasks/{task_id}/preview-uom` | 401 | 403 |
| GET | `/api/receiving/uom-settings` | 401 | 403 |
| PUT | `/api/receiving/uom-settings` | 401 | 403 |
| GET | `/api/inbound/qc/queue` | 401 | 403 |
| POST | `/api/inbound/tasks/{task_id}/qc-decision` | 401 | 403 |
| GET | `/api/inbound/po/{po_id}/receiving-goods-document` | 401 | 403 |
| GET | `/api/inbound/tasks` | 401 | 403 |
| POST | `/api/inbound/tasks/{task_id}/scan-receive` | 401 | 403 |
| POST | `/api/inbound/tasks/{task_id}/escalate` | 401 | 403 |
| POST | `/api/inbound/tasks/{task_id}/resolve-escalation` | 401 | 403 |
| POST | `/api/inbound/tasks/{task_id}/complete` | 401 | 403 |
| GET | `/api/suppliers/{supplier_id}/label-pattern` | 401 | 403 |
| PUT | `/api/suppliers/{supplier_id}/label-pattern` | 401 | 403 |
| POST | `/api/suppliers/label-pattern/test` | 401 | 403 |
| GET | `/api/inbound/tasks/{task_id}/scanned-rolls` | 401 | 403 |
| POST | `/api/inbound/tasks/{task_id}/scan-label` | 401 | 403 |
| POST | `/api/inbound/rolls/{roll_id}/confirm-measure` | 401 | 403 |
| POST | `/api/inbound/rolls/{roll_id}/putaway` | 401 | 403 |
| POST | `/api/inbound/rolls/{roll_id}/tag` | 401 | 403 |
| DELETE | `/api/inbound/rolls/{roll_id}/scan` | 401 | 403 |
| GET | `/api/inbound/scan-label/stats` | 401 | 403 |
| POST | `/api/goods-receipts` | 401 | 403 |
| GET | `/api/goods-receipts` | 401 | 403 |
| GET | `/api/goods-receipts/partners` | 401 | 403 |
| GET | `/api/goods-receipts/supplier-variance` | 401 | 403 |
| GET | `/api/goods-receipts/usage` | 401 | 403 |
| GET | `/api/goods-receipts/mode` | 401 | 403 |
| PUT | `/api/goods-receipts/mode` | 401 | 403 |
| GET | `/api/goods-receipts/doc-variance` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/lines/{line_no}/save-catalog` | 401 | 403 |
| GET | `/api/goods-receipts/dn-profiles` | 401 | 403 |
| GET | `/api/goods-receipts/dn-profiles/{partner_id}` | 401 | 403 |
| PATCH | `/api/goods-receipts/dn-profiles/{partner_id}` | 401 | 403 |
| GET | `/api/goods-receipts/{grn_id}/rolls` | 401 | 403 |
| GET | `/api/goods-receipts/{grn_id}` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/read` | 401 | 403 |
| GET | `/api/goods-receipts/{grn_id}/targets` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/files` | 401 | 403 |
| DELETE | `/api/goods-receipts/{grn_id}/files/{page}` | 401 | 403 |
| GET | `/api/goods-receipts/{grn_id}/files/{page}` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/manual-entry` | 401 | 403 |
| PATCH | `/api/goods-receipts/{grn_id}/dn` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/lines` | 401 | 403 |
| PATCH | `/api/goods-receipts/{grn_id}/lines/{line_no}` | 401 | 403 |
| DELETE | `/api/goods-receipts/{grn_id}/lines/{line_no}` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/start-count` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/lines/{line_no}/scan-label` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/lines/{line_no}/rolls` | 401 | 403 |
| DELETE | `/api/goods-receipts/{grn_id}/rolls/{roll_id}` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/finish-count` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/reopen-count` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/discrepancies/{key}/resolve` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/close` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/mko-partial` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/return-to-reconcile` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/reject` | 401 | 403 |
| POST | `/api/goods-receipts/{grn_id}/cancel` | 401 | 403 |
| GET | `/api/shipments` | 401 | 403 |
| GET | `/api/shipments/{shipment_id}/surat-jalan` | 401 | 403 |
| GET | `/api/outbound/so/{order_id}/surat-jalan` | 401 | 403 |
| GET | `/api/outbound/tasks` | 401 | 403 |
| POST | `/api/outbound/tasks/{task_id}/release` | 401 | 403 |
| POST | `/api/outbound/tasks/{task_id}/scan-pick` | 401 | 403 |
| POST | `/api/outbound/tasks/{task_id}/escalate` | 401 | 403 |
| POST | `/api/outbound/tasks/{task_id}/resolve-escalation` | 401 | 403 |
| POST | `/api/outbound/tasks/{task_id}/reopen-escalation` | 401 | 403 |
| POST | `/api/outbound/tasks/{task_id}/dispatch` | 401 | 403 |
| POST | `/api/outbound/so/{order_id}/loading-check/start` | 401 | 403 |
| POST | `/api/outbound/loading-check/{session_id}/scan` | 401 | 403 |
| POST | `/api/outbound/loading-check/{session_id}/complete` | 401 | 403 |
| GET | `/api/outbound/so/{order_id}/loading-check` | 401 | 403 |
| GET | `/api/entities` | 401 | 200 |
| GET | `/api/entities/count` | 401 | 200 |
| GET | `/api/entities/{entity_id}` | 401 | 200 |
| GET | `/api/entities/{entity_id}/readiness` | 401 | 200 |
| GET | `/api/entities/{entity_id}/deactivation-impact` | 401 | 403 |
| GET | `/api/entities/{entity_id}/audit` | 401 | 403 |
| POST | `/api/entities` | 401 | 403 |
| PATCH | `/api/entities/{entity_id}` | 401 | 403 |
| DELETE | `/api/entities/{entity_id}` | 401 | 403 |
| POST | `/api/entities/{entity_id}/archive` | 401 | 403 |
| POST | `/api/entities/{entity_id}/reactivate` | 401 | 403 |
| GET | `/api/notifications` | 401 | 200 |
| GET | `/api/notifications/unread-count` | 401 | 200 |
| POST | `/api/notifications/read-all` | 401 | 200 |
| POST | `/api/notifications/{notification_id}/read` | 401 | 404 |
| POST | `/api/notifications/generate` | 401 | 403 |
| GET | `/api/settings` | 401 | 200 |
| GET | `/api/settings/effective` | 401 | 200 |
| PUT | `/api/settings` | 401 | 403 |
| GET | `/api/settings/compute-tax` | 401 | 200 |
| GET | `/api/settings/evaluate-approval` | 401 | 200 |
| GET | `/api/payment-terms` | 401 | 200 |
| POST | `/api/payment-terms` | 401 | 403 |
| PATCH | `/api/payment-terms/{term_id}` | 401 | 403 |
| POST | `/api/payment-terms/{term_id}/override` | 401 | 403 |
| DELETE | `/api/payment-terms/{term_id}` | 401 | 403 |
| GET | `/api/price-approvals/hint` | 401 | 403 |
| GET | `/api/price-approvals` | 401 | 403 |
| GET | `/api/price-approvals/effective` | 401 | 403 |
| GET | `/api/price-approvals/stats/summary` | 401 | 403 |
| POST | `/api/price-approvals` | 401 | 403 |
| GET | `/api/price-approvals/{approval_id}` | 401 | 403 |
| PATCH | `/api/price-approvals/{approval_id}` | 401 | 403 |
| DELETE | `/api/price-approvals/{approval_id}` | 401 | 403 |
| POST | `/api/price-approvals/{approval_id}/submit` | 401 | 403 |
| POST | `/api/price-approvals/{approval_id}/approve` | 401 | 403 |
| POST | `/api/price-approvals/{approval_id}/reject` | 401 | 403 |
| POST | `/api/price-approvals/{approval_id}/revoke` | 401 | 403 |
| POST | `/api/price-approvals/{approval_id}/attachments` | 401 | 403 |
| GET | `/api/price-approvals/{approval_id}/attachments/{att_id}/download` | 401 | 403 |
| DELETE | `/api/price-approvals/{approval_id}/attachments/{att_id}` | 401 | 403 |
| GET | `/api/pegging/rolls` | 401 | 403 |
| POST | `/api/inventory/rolls/{roll_id}/earmark` | 401 | 403 |
| DELETE | `/api/inventory/rolls/{roll_id}/earmark` | 401 | 403 |
| GET | `/api/tax-invoices` | 401 | 403 |
| GET | `/api/tax-invoices/{fkt_id}` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/tax-invoice` | 401 | 403 |
| PATCH | `/api/tax-invoices/{fkt_id}/nsfp` | 401 | 403 |
| POST | `/api/tax-invoices/{fkt_id}/replace` | 401 | 403 |
| POST | `/api/tax-invoices/{fkt_id}/cancel` | 401 | 403 |
| GET | `/api/tax-invoices/{fkt_id}/document` | 401 | 403 |
| GET | `/api/sales-returns` | 401 | 403 |
| GET | `/api/sales-returns/status-counts` | 401 | 403 |
| GET | `/api/credit-notes` | 401 | 403 |
| GET | `/api/credit-notes/{cn_id}` | 401 | 403 |
| POST | `/api/sales-returns` | 401 | 403 |
| GET | `/api/sales-returns/{return_id}` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/submit` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/approve` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/inspect/start` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/inspect/complete` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/milestone` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/complaint` | 401 | 403 |
| GET | `/api/sales-returns/meta/complaint-reasons` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/settle` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/reverse` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/reverse-writeoff` | 401 | 403 |
| GET | `/api/sales-returns/{return_id}/quarantine` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/quarantine/release` | 401 | 403 |
| GET | `/api/returns/chain/{doc_id}` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/rolls/{roll_id}/transfer-ownership` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/create-purchase-return` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/reject` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/attachments` | 401 | 403 |
| GET | `/api/sales-returns/{return_id}/attachments/{att_id}/download` | 401 | 403 |
| DELETE | `/api/sales-returns/{return_id}/attachments/{att_id}` | 401 | 403 |
| POST | `/api/sales-returns/{return_id}/relocate` | 401 | 403 |
| GET | `/api/special-orders` | 401 | 403 |
| POST | `/api/special-orders` | 401 | 403 |
| GET | `/api/special-orders/{order_id}` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/references` | 401 | 403 |
| GET | `/api/special-orders/{order_id}/references/{file_id}` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/route` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/submit` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/customer-decision` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/customer-decision/evidence` | 401 | 403 |
| GET | `/api/special-orders/{order_id}/customer-decision/evidence/{file_id}` | 401 | 403 |
| GET | `/api/special-orders/{order_id}/pricing` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/lock-price` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/procure` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/prepare-shipment` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/unlock-price` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/approve` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/reject` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/status` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/create-pr` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/create-sku` | 401 | 403 |
| POST | `/api/special-orders/{order_id}/convert-to-so` | 401 | 403 |
| PATCH | `/api/special-orders/{order_id}` | 401 | 403 |
| DELETE | `/api/special-orders/{order_id}` | 401 | 403 |
| GET | `/api/approval-rules` | 401 | 403 |
| POST | `/api/approval-rules` | 401 | 403 |
| GET | `/api/approval-rules/{rule_id}` | 401 | 403 |
| PATCH | `/api/approval-rules/{rule_id}` | 401 | 403 |
| DELETE | `/api/approval-rules/{rule_id}` | 401 | 403 |
| GET | `/api/suppliers` | 401 | 403 |
| POST | `/api/suppliers` | 401 | 403 |
| GET | `/api/suppliers/{supplier_id}` | 401 | 403 |
| PATCH | `/api/suppliers/{supplier_id}` | 401 | 403 |
| DELETE | `/api/suppliers/{supplier_id}` | 401 | 403 |
| GET | `/api/suppliers/{supplier_id}/price-list` | 401 | 403 |
| POST | `/api/suppliers/{supplier_id}/price-list` | 401 | 403 |
| PATCH | `/api/supplier-price-list/{entry_id}` | 401 | 403 |
| DELETE | `/api/supplier-price-list/{entry_id}` | 401 | 403 |
| GET | `/api/supplier-price-list/resolve` | 401 | 403 |
| GET | `/api/suppliers/{supplier_id}/scorecard` | 401 | 403 |
| GET | `/api/suppliers/{supplier_id}/360` | 401 | 403 |
| GET | `/api/suppliers/{supplier_id}/return-policy` | 401 | 403 |
| GET | `/api/cash-transactions` | 401 | 403 |
| GET | `/api/cash-transactions/summary` | 401 | 403 |
| POST | `/api/cash-transactions` | 401 | 403 |
| POST | `/api/cash-transactions/{txn_id}/void` | 401 | 403 |
| GET | `/api/purchase-returns` | 401 | 403 |
| GET | `/api/purchase-returns/status-counts` | 401 | 403 |
| POST | `/api/purchase-returns` | 401 | 403 |
| GET | `/api/purchase-returns/source-rolls` | 401 | 403 |
| GET | `/api/purchase-returns/{return_id}` | 401 | 403 |
| POST | `/api/purchase-returns/{return_id}/submit` | 401 | 403 |
| POST | `/api/purchase-returns/{return_id}/approve` | 401 | 403 |
| POST | `/api/purchase-returns/{return_id}/reject` | 401 | 403 |
| POST | `/api/purchase-returns/{return_id}/ship-to-supplier` | 401 | 403 |
| POST | `/api/purchase-returns/{return_id}/supplier-accept` | 401 | 403 |
| POST | `/api/purchase-returns/{return_id}/supplier-reject` | 401 | 403 |
| POST | `/api/purchase-returns/{return_id}/goods-back` | 401 | 403 |
| POST | `/api/purchase-returns/{return_id}/reverse` | 401 | 403 |
| DELETE | `/api/purchase-returns/{return_id}` | 401 | 403 |
| GET | `/api/purchase-requisitions` | 401 | 403 |
| GET | `/api/purchase-requisitions/reorder-suggestions` | 401 | 403 |
| POST | `/api/purchase-requisitions` | 401 | 403 |
| GET | `/api/purchase-requisitions/{pr_id}` | 401 | 403 |
| PATCH | `/api/purchase-requisitions/{pr_id}/lines/{line_no}` | 401 | 403 |
| POST | `/api/purchase-requisitions/{pr_id}/submit` | 401 | 403 |
| POST | `/api/purchase-requisitions/{pr_id}/approve` | 401 | 403 |
| POST | `/api/purchase-requisitions/{pr_id}/reject` | 401 | 403 |
| POST | `/api/purchase-requisitions/{pr_id}/cancel` | 401 | 403 |
| POST | `/api/purchase-requisitions/{pr_id}/convert-to-po` | 401 | 403 |
| GET | `/api/purchase-requisitions/{pr_id}/sourcing` | 401 | 403 |
| POST | `/api/purchase-requisitions/{pr_id}/realize-po` | 401 | 403 |
| GET | `/api/purchase-requisitions/{pr_id}/makloon-prefill` | 401 | 403 |
| POST | `/api/purchase-requisitions/{pr_id}/realize-makloon` | 401 | 403 |
| GET | `/api/purchase-orders/{po_id}/billing-context` | 401 | 403 |
| GET | `/api/vendor-bills/payables/summary` | 401 | 403 |
| GET | `/api/vendor-bills/status-counts` | 401 | 403 |
| GET | `/api/vendor-bills` | 401 | 403 |
| GET | `/api/vendor-bills/{bill_id}` | 401 | 403 |
| POST | `/api/vendor-bills` | 401 | 403 |
| POST | `/api/vendor-bills/{bill_id}/submit` | 401 | 403 |
| POST | `/api/vendor-bills/{bill_id}/approve` | 401 | 404 |
| POST | `/api/vendor-bills/{bill_id}/reject` | 401 | 404 |
| POST | `/api/vendor-bills/{bill_id}/pay` | 401 | 403 |
| POST | `/api/vendor-bills/{bill_id}/cancel` | 401 | 403 |
| GET | `/api/purchase-orders/{po_id}/landed-cost-context` | 401 | 403 |
| GET | `/api/landed-costs/payables/summary` | 401 | 403 |
| GET | `/api/landed-costs` | 401 | 403 |
| GET | `/api/landed-costs/{voucher_id}` | 401 | 403 |
| POST | `/api/landed-costs` | 401 | 403 |
| POST | `/api/landed-costs/{voucher_id}/submit` | 401 | 403 |
| POST | `/api/landed-costs/{voucher_id}/approve` | 401 | 404 |
| POST | `/api/landed-costs/{voucher_id}/reject` | 401 | 404 |
| POST | `/api/landed-costs/{voucher_id}/pay` | 401 | 403 |
| POST | `/api/landed-costs/{voucher_id}/cancel` | 401 | 403 |
| GET | `/api/input-tax-invoices/eligible-bills` | 401 | 403 |
| GET | `/api/tax/vat-summary` | 401 | 403 |
| GET | `/api/input-tax-invoices` | 401 | 403 |
| GET | `/api/input-tax-invoices/{fpm_id}` | 401 | 403 |
| POST | `/api/input-tax-invoices` | 401 | 403 |
| POST | `/api/input-tax-invoices/{fpm_id}/cancel` | 401 | 403 |
| GET | `/api/rfqs` | 401 | 403 |
| GET | `/api/rfqs/{rfq_id}` | 401 | 403 |
| GET | `/api/rfqs/{rfq_id}/compare` | 401 | 403 |
| POST | `/api/rfqs` | 401 | 403 |
| POST | `/api/rfqs/{rfq_id}/send` | 401 | 403 |
| POST | `/api/rfqs/{rfq_id}/quote` | 401 | 403 |
| POST | `/api/rfqs/{rfq_id}/award` | 401 | 403 |
| POST | `/api/rfqs/{rfq_id}/cancel` | 401 | 403 |
| GET | `/api/qc/grade-thresholds` | 401 | 403 |
| GET | `/api/inbound/qc/tasks/{task_id}/rolls` | 401 | 403 |
| POST | `/api/inbound/rolls/{roll_id}/inspect` | 401 | 403 |
| GET | `/api/inventory/rolls/{roll_id}/grade-history` | 401 | 403 |
| POST | `/api/inventory/rolls/{roll_id}/grade-override` | 401 | 403 |
| GET | `/api/sales-users` | 401 | 200 |
| GET | `/api/customers/{customer_id}/360` | 401 | 403 |
| POST | `/api/customers/{customer_id}/reassign` | 401 | 403 |
| POST | `/api/customers/{customer_id}/credit-override` | 401 | 403 |
| GET | `/api/credit-overrides` | 401 | 403 |
| POST | `/api/credit-overrides/{override_id}/decision` | 401 | 403 |
| GET | `/api/collection-worklist` | 401 | 403 |
| GET | `/api/customers/{customer_id}/credit-status` | 401 | 403 |
| GET | `/api/collection-reminders` | 401 | 403 |
| POST | `/api/collection-reminders/mark` | 401 | 403 |
| POST | `/api/customers/{customer_id}/followups` | 401 | 403 |
| GET | `/api/sales/kpi` | 401 | 403 |
| GET | `/api/sales/leaderboard` | 401 | 403 |
| GET | `/api/sales/commission` | 401 | 403 |
| GET | `/api/sales/commission-history` | 401 | 403 |
| GET | `/api/sales/incentive/gl-status` | 401 | 403 |
| POST | `/api/sales/incentive/post-gl` | 401 | 403 |
| GET | `/api/sales-targets` | 401 | 200 |
| POST | `/api/sales-targets` | 401 | 403 |
| GET | `/api/sales-incentives` | 401 | 200 |
| POST | `/api/sales-incentives` | 401 | 403 |
| GET | `/api/home/sales` | 401 | 200 |
| GET | `/api/home/admin` | 401 | 403 |
| GET | `/api/home/manager` | 401 | 403 |
| GET | `/api/home/warehouse` | 401 | 200 |
| GET | `/api/home/finance` | 401 | 200 |
| GET | `/api/product-categories` | 401 | 403 |
| GET | `/api/product-motifs` | 401 | 403 |
| POST | `/api/product-categories` | 401 | 403 |
| DELETE | `/api/product-categories/{category_id}` | 401 | 403 |
| PATCH | `/api/product-categories/{category_id}` | 401 | 403 |
| GET | `/api/costing/wac` | 401 | 403 |
| GET | `/api/costing/wac/{product_id}` | 401 | 403 |
| GET | `/api/ar-receipts/open-orders` | 401 | 403 |
| GET | `/api/ar-receipts/deposit` | 401 | 403 |
| GET | `/api/ar-receipts` | 401 | 403 |
| POST | `/api/ar-receipts` | 401 | 403 |
| POST | `/api/ar-receipts/{receipt_id}/void` | 401 | 403 |
| GET | `/api/ar-receipts/{receipt_id}` | 401 | 403 |
| GET | `/api/incentive-rates` | 401 | 403 |
| POST | `/api/incentive-rates` | 401 | 403 |
| PATCH | `/api/incentive-rates/{rate_id}` | 401 | 403 |
| DELETE | `/api/incentive-rates/{rate_id}` | 401 | 403 |
| GET | `/api/ar/aging` | 401 | 403 |
| POST | `/api/ar/aging/{customer_id}/accrue-penalties` | 401 | 403 |
| GET | `/api/ar/aging/{customer_id}` | 401 | 403 |
| GET | `/api/ar/advance-report` | 401 | 403 |
| GET | `/api/bank-accounts` | 401 | 403 |
| POST | `/api/bank-accounts` | 401 | 403 |
| PATCH | `/api/bank-accounts/{account_id}` | 401 | 403 |
| GET | `/api/bank-accounts/{account_id}/ledger` | 401 | 403 |
| POST | `/api/cash-transactions/{txn_id}/reconcile` | 401 | 403 |
| GET | `/api/gl/accounts` | 401 | 403 |
| GET | `/api/gl/cash-accounts` | 401 | 403 |
| POST | `/api/gl/accounts` | 401 | 403 |
| PATCH | `/api/gl/accounts/{code}` | 401 | 403 |
| DELETE | `/api/gl/accounts/{code}` | 401 | 403 |
| GET | `/api/gl/accounts/{code}/ledger` | 401 | 403 |
| GET | `/api/gl/journal` | 401 | 403 |
| POST | `/api/gl/journal` | 401 | 403 |
| GET | `/api/gl/journal/{entry_id}` | 401 | 403 |
| POST | `/api/gl/journal/{entry_id}/void` | 401 | 403 |
| POST | `/api/gl/sync` | 401 | 403 |
| GET | `/api/gl/trial-balance` | 401 | 403 |
| GET | `/api/gl/summary` | 401 | 403 |
| GET | `/api/gl/consolidation` | 401 | 403 |
| GET | `/api/gl/inventory-reconciliation` | 401 | 403 |
| GET | `/api/gl/inventory-drift-explain` | 401 | 403 |
| POST | `/api/gl/inventory-opening-balance` | 401 | 403 |
| GET | `/api/gl/suspense` | 401 | 403 |
| POST | `/api/gl/suspense/reclass` | 401 | 403 |
| GET | `/api/pricelist` | 401 | 403 |
| GET | `/api/pricelist/records` | 401 | 403 |
| GET | `/api/pricelist/export` | 401 | 403 |
| POST | `/api/pricelist/import` | 401 | 403 |
| DELETE | `/api/pricelist/override/{product_id}` | 401 | 403 |
| POST | `/api/pricelist` | 401 | 403 |
| PATCH | `/api/pricelist/{price_id}` | 401 | 403 |
| DELETE | `/api/pricelist/{price_id}` | 401 | 403 |
| GET | `/api/product-templates` | 401 | 403 |
| GET | `/api/product-templates/{template_id}/summary` | 401 | 403 |
| POST | `/api/product-templates/resolve-orphans` | 401 | 403 |
| GET | `/api/product-templates/{template_id}` | 401 | 403 |
| POST | `/api/product-templates` | 401 | 403 |
| PATCH | `/api/product-templates/{template_id}` | 401 | 403 |
| DELETE | `/api/product-templates/{template_id}` | 401 | 403 |
| POST | `/api/product-templates/{template_id}/generate-variants` | 401 | 403 |
| POST | `/api/product-templates/{template_id}/assign` | 401 | 403 |
| POST | `/api/product-templates/detach` | 401 | 403 |
| GET | `/api/stock/buckets` | 401 | 403 |
| GET | `/api/stock/holds` | 401 | 403 |
| GET | `/api/stock/wip` | 401 | 403 |
| GET | `/api/stock/pending-so` | 401 | 403 |
| GET | `/api/stock/atp` | 401 | 403 |
| POST | `/api/stock/hold` | 401 | 403 |
| POST | `/api/stock/hold/{hold_id}/release` | 401 | 403 |
| POST | `/api/stock/wip/start` | 401 | 403 |
| POST | `/api/stock/wip/{wip_id}/complete` | 401 | 403 |
| GET | `/api/pos/best-sellers` | 401 | 403 |
| GET | `/api/pos/frequently-bought-together` | 401 | 403 |
| GET | `/api/pos/substitutes` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/request-special-price` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/request-credit-approval` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/approvals/{approval_id}/decide` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/approvals/{approval_id}/evidence` | 401 | 403 |
| GET | `/api/sales-orders/{order_id}/approvals/{approval_id}/evidence/{att_id}/download` | 401 | 403 |
| GET | `/api/approvals/backlog` | 401 | 403 |
| GET | `/api/approvals/queue-board/{key}` | 401 | 403 |
| GET | `/api/approvals/queue` | 401 | 403 |
| GET | `/api/hr/org-units` | 401 | 403 |
| GET | `/api/hr/org-units/tree` | 401 | 403 |
| POST | `/api/hr/org-units` | 401 | 403 |
| PATCH | `/api/hr/org-units/{unit_id}` | 401 | 403 |
| DELETE | `/api/hr/org-units/{unit_id}` | 401 | 403 |
| GET | `/api/hr/employees` | 401 | 403 |
| GET | `/api/hr/summary` | 401 | 403 |
| GET | `/api/hr/employees/me` | 401 | 404 |
| POST | `/api/hr/employees` | 401 | 403 |
| GET | `/api/hr/employees/{employee_id}` | 401 | 403 |
| GET | `/api/hr/employees/{employee_id}/360` | 401 | 403 |
| PATCH | `/api/hr/employees/{employee_id}` | 401 | 403 |
| DELETE | `/api/hr/employees/{employee_id}` | 401 | 403 |
| GET | `/api/hr/settings` | 401 | 403 |
| PUT | `/api/hr/settings` | 401 | 403 |
| GET | `/api/hr/shifts` | 401 | 403 |
| POST | `/api/hr/shifts` | 401 | 403 |
| PATCH | `/api/hr/shifts/{shift_id}` | 401 | 403 |
| DELETE | `/api/hr/shifts/{shift_id}` | 401 | 403 |
| GET | `/api/hr/geofences` | 401 | 403 |
| POST | `/api/hr/geofences` | 401 | 403 |
| PATCH | `/api/hr/geofences/{geo_id}` | 401 | 403 |
| DELETE | `/api/hr/geofences/{geo_id}` | 401 | 403 |
| GET | `/api/hr/devices` | 401 | 403 |
| POST | `/api/hr/devices` | 401 | 403 |
| PATCH | `/api/hr/devices/{dev_id}` | 401 | 403 |
| DELETE | `/api/hr/devices/{dev_id}` | 401 | 403 |
| GET | `/api/hr/attendance` | 401 | 403 |
| GET | `/api/hr/attendance/recap` | 401 | 403 |
| GET | `/api/hr/attendance/me` | 401 | 404 |
| POST | `/api/hr/attendance/clock-in` | 401 | 404 |
| POST | `/api/hr/attendance/clock-out` | 401 | 404 |
| POST | `/api/hr/attendance/manual` | 401 | 403 |
| PATCH | `/api/hr/attendance/{att_id}` | 401 | 403 |
| POST | `/api/hr/attendance/import` | 401 | 403 |
| POST | `/api/hr/attendance/ingest` | 401 | 401 |
| GET | `/api/hr/field-tracks/latest` | 401 | 403 |
| GET | `/api/hr/field-tracks` | 401 | 403 |
| POST | `/api/hr/field-tracks` | 401 | 404 |
| GET | `/api/hr/visits` | 401 | 403 |
| GET | `/api/hr/visits/summary` | 401 | 403 |
| GET | `/api/hr/visits/me` | 401 | 404 |
| GET | `/api/hr/visits/mine` | 401 | 404 |
| POST | `/api/hr/visits/check-in` | 401 | 404 |
| POST | `/api/hr/visits/{visit_id}/check-out` | 401 | 404 |
| GET | `/api/hr/payroll/settings` | 401 | 403 |
| PUT | `/api/hr/payroll/settings` | 401 | 403 |
| GET | `/api/hr/payroll/runs` | 401 | 403 |
| POST | `/api/hr/payroll/runs/preview` | 401 | 403 |
| POST | `/api/hr/payroll/runs` | 401 | 403 |
| GET | `/api/hr/payroll/runs/{run_id}` | 401 | 403 |
| POST | `/api/hr/payroll/runs/{run_id}/submit` | 401 | 403 |
| POST | `/api/hr/payroll/runs/{run_id}/reject` | 401 | 403 |
| POST | `/api/hr/payroll/runs/{run_id}/approve` | 401 | 403 |
| POST | `/api/hr/payroll/runs/{run_id}/post-gl` | 401 | 403 |
| POST | `/api/hr/payroll/runs/{run_id}/pay` | 401 | 403 |
| GET | `/api/hr/payslips` | 401 | 403 |
| GET | `/api/hr/payslips/me` | 401 | 200 |
| GET | `/api/hr/payslips/{slip_id}` | 401 | 404 |
| GET | `/api/hr/payslips/{slip_id}/pdf` | 401 | 404 |
| GET | `/api/hr/leave-requests/me` | 401 | 404 |
| POST | `/api/hr/leave-requests/me` | 401 | 404 |
| GET | `/api/hr/leave-balance/me` | 401 | 404 |
| GET | `/api/hr/leave-requests` | 401 | 403 |
| POST | `/api/hr/leave-requests` | 401 | 403 |
| GET | `/api/hr/leave-balances` | 401 | 403 |
| POST | `/api/hr/leave-balances/set` | 401 | 403 |
| GET | `/api/hr/leave-calendar` | 401 | 403 |
| POST | `/api/hr/leave-requests/{leave_id}/approve` | 401 | 403 |
| POST | `/api/hr/leave-requests/{leave_id}/reject` | 401 | 403 |
| POST | `/api/hr/leave-requests/{leave_id}/cancel` | 401 | 404 |
| GET | `/api/hr/overtime/me` | 401 | 404 |
| POST | `/api/hr/overtime/me` | 401 | 404 |
| GET | `/api/hr/overtime` | 401 | 403 |
| POST | `/api/hr/overtime` | 401 | 403 |
| POST | `/api/hr/overtime/{ot_id}/approve` | 401 | 403 |
| POST | `/api/hr/overtime/{ot_id}/reject` | 401 | 403 |
| GET | `/api/hr/kpi/me` | 401 | 404 |
| GET | `/api/hr/kpi` | 401 | 403 |
| POST | `/api/hr/kpi` | 401 | 403 |
| PUT | `/api/hr/kpi/{kpi_id}` | 401 | 403 |
| DELETE | `/api/hr/kpi/{kpi_id}` | 401 | 403 |
| GET | `/api/design-gallery` | 401 | 403 |
| POST | `/api/design-gallery` | 401 | 403 |
| GET | `/api/design-gallery/{gallery_id}` | 401 | 403 |
| PUT | `/api/design-gallery/{gallery_id}` | 401 | 403 |
| DELETE | `/api/design-gallery/{gallery_id}` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/files` | 401 | 403 |
| GET | `/api/design-gallery/{gallery_id}/files/{file_id}` | 401 | 403 |
| DELETE | `/api/design-gallery/{gallery_id}/files/{file_id}` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/autotag` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/ai-illustrate` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/files/{file_id}/comments` | 401 | 403 |
| DELETE | `/api/design-gallery/{gallery_id}/files/{file_id}/comments/{comment_id}` | 401 | 403 |
| GET | `/api/design-gallery-ai/status` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/version` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/submit` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/reject` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/approve` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/rating` | 401 | 403 |
| DELETE | `/api/design-gallery/{gallery_id}/rating` | 401 | 403 |
| GET | `/api/admin/integrations` | 401 | 403 |
| PUT | `/api/admin/integrations` | 401 | 403 |
| POST | `/api/admin/integrations/gemini/test` | 401 | 403 |
| POST | `/api/admin/integrations/openai/test` | 401 | 403 |
| GET | `/api/hr/analytics/summary` | 401 | 403 |
| GET | `/api/tax/summary` | 401 | 403 |
| GET | `/api/tax/pph-records` | 401 | 403 |
| POST | `/api/tax/pph-records` | 401 | 403 |
| DELETE | `/api/tax/pph-records/{record_id}` | 401 | 403 |
| GET | `/api/finance/income-statement` | 401 | 403 |
| GET | `/api/finance/balance-sheet` | 401 | 403 |
| GET | `/api/finance/cash-flow` | 401 | 403 |
| GET | `/api/finance/equity-changes` | 401 | 403 |
| GET | `/api/finance/income-statement/export.csv` | 401 | 403 |
| GET | `/api/finance/balance-sheet/export.csv` | 401 | 403 |
| GET | `/api/finance/cash-flow/export.csv` | 401 | 403 |
| GET | `/api/finance/equity-changes/export.csv` | 401 | 403 |
| GET | `/api/finance/closing` | 401 | 403 |
| GET | `/api/finance/closing/preview` | 401 | 403 |
| GET | `/api/finance/closing/status` | 401 | 403 |
| POST | `/api/finance/closing/close` | 401 | 403 |
| POST | `/api/finance/closing/{closing_id}/reopen` | 401 | 403 |
| POST | `/api/finance/closing/{closing_id}/reclose` | 401 | 403 |
| GET | `/api/finance/bi` | 401 | 403 |
| GET | `/api/crm/leads` | 401 | 403 |
| GET | `/api/crm/leads/board` | 401 | 403 |
| GET | `/api/crm/pipeline-stats` | 401 | 403 |
| POST | `/api/crm/leads` | 401 | 403 |
| PATCH | `/api/crm/leads/{lead_id}` | 401 | 403 |
| POST | `/api/crm/leads/{lead_id}/convert` | 401 | 403 |
| DELETE | `/api/crm/leads/{lead_id}` | 401 | 403 |
| GET | `/api/crm/interactions` | 401 | 403 |
| POST | `/api/crm/interactions` | 401 | 403 |
| DELETE | `/api/crm/interactions/{intx_id}` | 401 | 403 |
| GET | `/api/finance/consolidation/summary` | 401 | 403 |
| GET | `/api/finance/consolidation/eliminations` | 401 | 403 |
| POST | `/api/finance/consolidation/eliminations` | 401 | 403 |
| DELETE | `/api/finance/consolidation/eliminations/{elim_id}` | 401 | 403 |
| GET | `/api/finance/consolidation/ic-candidates` | 401 | 403 |
| POST | `/api/finance/consolidation/eliminations/sync-from-pairs` | 401 | 403 |
| POST | `/api/consolidation/sync-g6` | 401 | 403 |
| GET | `/api/rfid/summary` | 401 | 403 |
| GET | `/api/rfid/tags` | 401 | 403 |
| GET | `/api/rfid/lookup` | 401 | 403 |
| POST | `/api/rfid/roll-scans` | 401 | 403 |
| GET | `/api/rfid/roll-scans/{roll_id}` | 401 | 403 |
| GET | `/api/rfid/printer-status` | 401 | 403 |
| GET | `/api/rfid/labels` | 401 | 403 |
| GET | `/api/rfid/untagged-rolls` | 401 | 403 |
| POST | `/api/rfid/tags/encode` | 401 | 403 |
| POST | `/api/rfid/tags/auto-encode` | 401 | 403 |
| DELETE | `/api/rfid/tags/{tag_id}` | 401 | 403 |
| GET | `/api/rfid/devices` | 401 | 403 |
| POST | `/api/rfid/devices` | 401 | 403 |
| PATCH | `/api/rfid/devices/{device_id}` | 401 | 403 |
| DELETE | `/api/rfid/devices/{device_id}` | 401 | 403 |
| POST | `/api/rfid/devices/seed-defaults` | 401 | 403 |
| GET | `/api/rfid/reads` | 401 | 403 |
| POST | `/api/rfid/gate/simulate` | 401 | 403 |
| POST | `/api/rfid/reader/scan` | 401 | 403 |
| GET | `/api/rfid/locations` | 401 | 403 |
| GET | `/api/rfid/print-jobs` | 401 | 403 |
| POST | `/api/rfid/print-jobs` | 401 | 403 |
| GET | `/api/rfid/print-jobs/{job_id}` | 401 | 403 |
| GET | `/api/rfid/print-jobs/{job_id}/zpl` | 401 | 403 |
| POST | `/api/rfid/print-jobs/{job_id}/mark-printed` | 401 | 403 |
| POST | `/api/rfid/print-jobs/{job_id}/verify/start` | 401 | 403 |
| POST | `/api/rfid/verify-sessions/{session_id}/scan` | 401 | 403 |
| POST | `/api/rfid/verify-sessions/{session_id}/complete` | 401 | 403 |
| POST | `/api/rfid/rolls/set-routing` | 401 | 403 |
| POST | `/api/rfid/devices/{device_id}/api-key` | 401 | 403 |
| POST | `/api/rfid/ingest` | 401 | 401 |
| POST | `/api/rfid/heartbeat` | 401 | 401 |
| GET | `/api/rfid/device-jobs/pending` | 401 | 401 |
| POST | `/api/rfid/device-jobs/{job_id}/ack` | 401 | 401 |
| GET | `/api/rfid/incidents` | 401 | 403 |
| POST | `/api/rfid/incidents/{incident_id}/acknowledge` | 401 | 403 |
| POST | `/api/rfid/incidents/{incident_id}/resolve` | 401 | 403 |
| GET | `/api/rfid/shrinkage-report` | 401 | 403 |
| GET | `/api/rfid/device-health` | 401 | 403 |
| POST | `/api/rfid/cycle-count/start` | 401 | 403 |
| POST | `/api/rfid/cycle-count/{session_id}/complete` | 401 | 403 |
| GET | `/api/rfid/cycle-counts` | 401 | 403 |
| GET | `/api/rfid/cycle-counts/{cc_id}` | 401 | 403 |
| GET | `/api/warehouse-sites` | 401 | 403 |
| POST | `/api/warehouse-sites` | 401 | 403 |
| PATCH | `/api/warehouse-sites/{site_id}` | 401 | 403 |
| DELETE | `/api/warehouse-sites/{site_id}` | 401 | 403 |
| POST | `/api/warehouse-sites/seed-blueprint` | 401 | 403 |
| GET | `/api/putaway-orders/suggest` | 401 | 403 |
| GET | `/api/putaway-orders` | 401 | 403 |
| POST | `/api/putaway-orders` | 401 | 403 |
| POST | `/api/putaway-orders/{order_id}/dispatch` | 401 | 403 |
| POST | `/api/putaway-orders/{order_id}/confirm-arrival` | 401 | 403 |
| POST | `/api/putaway-orders/{order_id}/resolve-exception` | 401 | 403 |
| GET | `/api/wms/health-dashboard` | 401 | 403 |
| GET | `/api/fulfillment/wizard/{so_id}` | 401 | 403 |
| POST | `/api/fulfillment/wizard/{so_id}/create-interco` | 401 | 403 |
| POST | `/api/fulfillment/wizard/{so_id}/create-pr` | 401 | 403 |
| GET | `/api/finance/profitability` | 401 | 403 |
| GET | `/api/finance/cashflow-forecast` | 401 | 403 |
| GET | `/api/finance/tower` | 401 | 403 |
| GET | `/api/finance/budgets` | 401 | 403 |
| POST | `/api/finance/budgets` | 401 | 403 |
| PATCH | `/api/finance/budgets/{budget_id}` | 401 | 403 |
| DELETE | `/api/finance/budgets/{budget_id}` | 401 | 403 |
| GET | `/api/finance/budget-vs-actual` | 401 | 403 |
| GET | `/api/finance/budget-keys` | 401 | 403 |
| GET | `/api/finance/budget-rules` | 401 | 403 |
| PUT | `/api/finance/budget-rules` | 401 | 403 |
| POST | `/api/finance/budget-check` | 401 | 403 |
| GET | `/api/enums` | 401 | 200 |
| GET | `/api/enums/stage-transitions` | 401 | 200 |
| POST | `/api/enums/stage-transitions/validate` | 401 | 400 |
| POST | `/api/enums/products/validate` | 401 | 200 |
| GET | `/api/enums/{name}` | 401 | 404 |
| GET | `/api/marketing/meta` | 401 | 403 |
| GET | `/api/marketing/campaigns` | 401 | 403 |
| POST | `/api/marketing/campaigns` | 401 | 403 |
| PATCH | `/api/marketing/campaigns/{cid}` | 401 | 403 |
| GET | `/api/marketing/posts` | 401 | 403 |
| GET | `/api/marketing/accounts` | 401 | 403 |
| POST | `/api/marketing/accounts` | 401 | 403 |
| PATCH | `/api/marketing/accounts/{aid}` | 401 | 403 |
| GET | `/api/marketing/templates` | 401 | 403 |
| POST | `/api/marketing/templates` | 401 | 403 |
| POST | `/api/marketing/templates/{tid}/use` | 401 | 403 |
| DELETE | `/api/marketing/templates/{tid}` | 401 | 403 |
| GET | `/api/marketing/dashboard` | 401 | 403 |
| GET | `/api/marketing/calendar.pdf` | 401 | 403 |
| GET | `/api/marketing/posts/{pid}` | 401 | 403 |
| POST | `/api/marketing/posts` | 401 | 403 |
| PATCH | `/api/marketing/posts/{pid}` | 401 | 403 |
| POST | `/api/marketing/posts/{pid}/reschedule` | 401 | 403 |
| POST | `/api/marketing/posts/{pid}/duplicate` | 401 | 403 |
| POST | `/api/marketing/posts/{pid}/transition` | 401 | 403 |
| POST | `/api/marketing/posts/{pid}/metrics` | 401 | 403 |
| DELETE | `/api/marketing/posts/{pid}` | 401 | 403 |
| POST | `/api/marketing/posts/{pid}/attachments` | 401 | 403 |
| GET | `/api/marketing/posts/{pid}/attachments/{fid}` | 401 | 403 |
| DELETE | `/api/marketing/posts/{pid}/attachments/{fid}` | 401 | 403 |
| GET | `/api/marketing/assets` | 401 | 403 |
| GET | `/api/marketing/analytics` | 401 | 403 |
| GET | `/api/uom-conversions/catalog` | 401 | 403 |
| GET | `/api/uom-conversions/rules` | 401 | 403 |
| POST | `/api/uom-conversions/rules` | 401 | 403 |
| PATCH | `/api/uom-conversions/rules/{rule_id}` | 401 | 403 |
| POST | `/api/uom-conversions/rules/{rule_id}/status` | 401 | 403 |
| GET | `/api/uom-conversions/settings` | 401 | 403 |
| PUT | `/api/uom-conversions/settings` | 401 | 403 |
| POST | `/api/uom-conversions/convert` | 401 | 403 |
| POST | `/api/uom-conversions/check-variance` | 401 | 403 |
| GET | `/api/uom-conversions/usage` | 401 | 403 |
| GET | `/api/color-library` | 401 | 403 |
| GET | `/api/color-library/customer-colors` | 401 | 403 |
| GET | `/api/color-library/customer-colors/{customer_id}/card` | 401 | 403 |
| GET | `/api/color-library/use-requests` | 401 | 403 |
| POST | `/api/color-library/{color_id}/use-requests` | 401 | 403 |
| POST | `/api/color-library/use-requests/{req_id}/approve` | 401 | 403 |
| POST | `/api/color-library/use-requests/{req_id}/reject` | 401 | 403 |
| POST | `/api/color-library/use-requests/{req_id}/revoke` | 401 | 403 |
| GET | `/api/color-library/nearest` | 401 | 403 |
| GET | `/api/color-library/supplier-variants` | 401 | 403 |
| GET | `/api/color-library/{color_id}/links` | 401 | 403 |
| POST | `/api/color-library` | 401 | 403 |
| PATCH | `/api/color-library/{color_id}` | 401 | 403 |
| DELETE | `/api/color-library/{color_id}` | 401 | 403 |
| POST | `/api/access/roles/preview` | 401 | 403 |
| POST | `/api/access/roles/{rid}/move-users` | 401 | 403 |
| GET | `/api/access/modules` | 401 | 403 |
| GET | `/api/access/roles` | 401 | 403 |
| GET | `/api/access/roles/{rid}` | 401 | 403 |
| POST | `/api/access/roles` | 401 | 403 |
| PATCH | `/api/access/roles/{rid}` | 401 | 403 |
| POST | `/api/access/roles/{rid}/reset` | 401 | 403 |
| DELETE | `/api/access/roles/{rid}` | 401 | 403 |
| GET | `/api/product-catalog/meta` | 401 | 403 |
| GET | `/api/products/{product_id}/media` | 401 | 403 |
| POST | `/api/products/{product_id}/media` | 401 | 403 |
| GET | `/api/products/{product_id}/media/{media_id}/content` | 401 | 403 |
| PATCH | `/api/products/{product_id}/media/{media_id}` | 401 | 403 |
| GET | `/api/products/{product_id}/catalog-relations` | 401 | 403 |
| DELETE | `/api/products/{product_id}/media/{media_id}` | 401 | 403 |
| POST | `/api/products/{product_id}/media/from-design` | 401 | 403 |
| POST | `/api/products/{product_id}/media/generate-mockup` | 401 | 403 |
| GET | `/api/customer-feedback/meta` | 401 | 403 |
| GET | `/api/customer-feedback/summary` | 401 | 403 |
| GET | `/api/customer-feedback` | 401 | 403 |
| POST | `/api/customer-feedback` | 401 | 403 |
| PATCH | `/api/customer-feedback/{fb_id}` | 401 | 403 |
| GET | `/api/push/public-key` | 401 | 200 |
| POST | `/api/push/subscribe` | 401 | 503 |
| POST | `/api/push/unsubscribe` | 401 | 200 |
| GET | `/api/push/status` | 401 | 200 |
| POST | `/api/push/test` | 401 | 404 |
| GET | `/api/saga-locks` | 401 | 403 |
| POST | `/api/saga-locks/{collection}/{doc_id}/release` | 401 | 403 |
| GET | `/api/wilayah/countries` | 401 | 200 |
| GET | `/api/wilayah/provinces` | 401 | 200 |
| GET | `/api/wilayah/regencies` | 401 | 200 |
| GET | `/api/wilayah/districts` | 401 | 200 |
| GET | `/api/wilayah/villages` | 401 | 200 |
| GET | `/api/wilayah/postal-code/{code}` | 401 | 200 |
| GET | `/api/wilayah/search` | 401 | 200 |
| POST | `/api/wilayah/validate` | 401 | 400 |
| GET | `/api/ai/catalog` | 401 | 403 |
| POST | `/api/ai/query` | 401 | 403 |
| POST | `/api/ai/analyze-change` | 401 | 403 |
| GET | `/api/ai/results/{result_id}` | 401 | 403 |
| GET | `/api/ai/facts/status` | 401 | 403 |
| POST | `/api/ai/facts/rebuild` | 401 | 403 |
| GET | `/api/ai/status` | 401 | 403 |
| GET | `/api/ai/templates` | 401 | 403 |
| POST | `/api/ai/templates/{template_id}/run` | 401 | 403 |
| POST | `/api/ai/tools/{tool}` | 401 | 403 |
| POST | `/api/ai/chat` | 401 | 403 |
| GET | `/api/ai/sessions` | 401 | 403 |
| DELETE | `/api/ai/sessions/{session_id}` | 401 | 403 |
| GET | `/api/ai/sessions/{session_id}` | 401 | 403 |
| POST | `/api/ai/feedback` | 401 | 403 |
| GET | `/api/ai/results/{result_id}/export.xlsx` | 401 | 403 |
| GET | `/api/ai/export.xlsx` | 401 | 403 |
| POST | `/api/ai/narrative` | 401 | 403 |
| GET | `/api/ai/my-templates` | 401 | 403 |
| POST | `/api/ai/my-templates` | 401 | 403 |
| DELETE | `/api/ai/my-templates/{template_id}` | 401 | 403 |
| GET | `/api/ai/schedules` | 401 | 403 |
| POST | `/api/ai/schedules` | 401 | 403 |
| PATCH | `/api/ai/schedules/{schedule_id}` | 401 | 403 |
| DELETE | `/api/ai/schedules/{schedule_id}` | 401 | 403 |
| POST | `/api/ai/schedules/{schedule_id}/run` | 401 | 403 |
| GET | `/api/ai/schedule-runs` | 401 | 403 |
| GET | `/api/ai/schedule-runs/{run_id}` | 401 | 403 |
| GET | `/api/ai/snapshots/status` | 401 | 403 |
| POST | `/api/ai/snapshots/run` | 401 | 403 |
| GET | `/api/ai/usage` | 401 | 403 |
| GET | `/api/ai/usage/daily` | 401 | 403 |
| GET | `/api/data-hygiene/summary` | 401 | 403 |
| GET | `/api/data-hygiene/log` | 401 | 403 |
| GET | `/api/data-hygiene/preview` | 401 | 403 |
| POST | `/api/data-hygiene/run` | 401 | 403 |
| POST | `/api/data-hygiene/log/{log_id}/revert` | 401 | 403 |
| POST | `/api/data-hygiene/{collection}/{doc_id}/unlock` | 401 | 403 |
| GET | `/api/turn-notifications/map` | 401 | 403 |
| GET | `/api/data-hygiene/unverified-locations` | 401 | 403 |
| POST | `/api/data-hygiene/location/{collection}/{doc_id}` | 401 | 403 |
| GET | `/api/sample-prices` | 401 | 403 |
| PUT | `/api/sample-prices/{template_id}` | 401 | 403 |
| GET | `/api/sample-quote` | 401 | 403 |
| POST | `/api/outbound/tasks/{task_id}/cut-sample` | 401 | 403 |
| GET | `/api/sample-orders/limits` | 401 | 403 |
| GET | `/api/sample-orders` | 401 | 403 |
| GET | `/api/sample-orders/stats/summary` | 401 | 403 |
| GET | `/api/sample-orders/desk` | 401 | 403 |
| POST | `/api/sample-orders/{order_id}/approve-payment` | 401 | 403 |
| POST | `/api/sample-orders/{order_id}/confirm` | 401 | 403 |
| POST | `/api/sample-orders/{order_id}/cancel` | 401 | 403 |
| GET | `/api/makloons` | 401 | 403 |
| POST | `/api/makloons` | 401 | 403 |
| GET | `/api/makloons/{makloon_id}` | 401 | 403 |
| PATCH | `/api/makloons/{makloon_id}` | 401 | 403 |
| DELETE | `/api/makloons/{makloon_id}` | 401 | 403 |
| GET | `/api/makloons/{makloon_id}/scorecard` | 401 | 403 |
| GET | `/api/process-recipes` | 401 | 403 |
| POST | `/api/process-recipes` | 401 | 403 |
| PATCH | `/api/process-recipes/{recipe_id}` | 401 | 403 |
| DELETE | `/api/process-recipes/{recipe_id}` | 401 | 403 |
| POST | `/api/process-recipes/forecast` | 401 | 403 |
| GET | `/api/process-stages` | 401 | 403 |
| GET | `/api/process-stages/for-line/{line_code}` | 401 | 403 |
| GET | `/api/makloon-orders` | 401 | 403 |
| POST | `/api/makloon-orders` | 401 | 403 |
| POST | `/api/makloon-orders/estimate` | 401 | 403 |
| GET | `/api/makloon-orders/claims` | 401 | 403 |
| GET | `/api/makloon-orders/claims/stats` | 401 | 403 |
| GET | `/api/makloon-orders/{mko_id}` | 401 | 403 |
| POST | `/api/makloon-orders/{mko_id}/issue` | 401 | 403 |
| POST | `/api/makloon-orders/{mko_id}/receive` | 401 | 403 |
| POST | `/api/makloon-orders/{mko_id}/steps/{seq}/partial-receipts/{grn_id}/cancel` | 401 | 403 |
| POST | `/api/makloon-orders/{mko_id}/record-service` | 401 | 403 |
| POST | `/api/makloon-orders/{mko_id}/claim` | 401 | 403 |
| POST | `/api/makloon-orders/{mko_id}/claim/approve` | 401 | 403 |
| POST | `/api/makloon-orders/{mko_id}/claim/reject` | 401 | 403 |
| POST | `/api/makloon-orders/{mko_id}/cancel` | 401 | 403 |
| GET | `/api/expense-categories` | 401 | 403 |
| PATCH | `/api/expense-categories/{code}` | 401 | 403 |
| GET | `/api/cash-advances` | 401 | 403 |
| POST | `/api/cash-advances` | 401 | 403 |
| GET | `/api/cash-advances/{ca_id}` | 401 | 403 |
| PATCH | `/api/cash-advances/{ca_id}` | 401 | 403 |
| POST | `/api/cash-advances/{ca_id}/submit` | 401 | 403 |
| POST | `/api/cash-advances/{ca_id}/approve` | 401 | 403 |
| POST | `/api/cash-advances/{ca_id}/reject` | 401 | 403 |
| POST | `/api/cash-advances/{ca_id}/disburse` | 401 | 403 |
| GET | `/api/cash-advance-settlements` | 401 | 403 |
| POST | `/api/cash-advance-settlements` | 401 | 403 |
| GET | `/api/cash-advance-settlements/{stl_id}` | 401 | 403 |
| PATCH | `/api/cash-advance-settlements/{stl_id}` | 401 | 403 |
| POST | `/api/cash-advance-settlements/{stl_id}/submit` | 401 | 403 |
| POST | `/api/cash-advance-settlements/{stl_id}/approve` | 401 | 403 |
| POST | `/api/cash-advance-settlements/{stl_id}/reject` | 401 | 403 |
| GET | `/api/vehicles` | 401 | 403 |
| POST | `/api/vehicles` | 401 | 403 |
| PATCH | `/api/vehicles/{veh_id}` | 401 | 403 |
| DELETE | `/api/vehicles/{veh_id}` | 401 | 403 |
| GET | `/api/vehicle-usage-logs` | 401 | 403 |
| GET | `/api/vehicle-usage-logs/summary` | 401 | 403 |
| POST | `/api/vehicle-usage-logs` | 401 | 403 |
| PATCH | `/api/vehicle-usage-logs/{log_id}` | 401 | 403 |
| DELETE | `/api/vehicle-usage-logs/{log_id}` | 401 | 403 |
| GET | `/api/pdf/doc-types` | 401 | 403 |
| GET | `/api/pdf/render/{doc_type}/{source_id}` | 401 | 403 |
| GET | `/api/pdf/sample/{doc_type}` | 401 | 403 |
| GET | `/api/pdf/documents/{doc_type}` | 401 | 403 |
| GET | `/api/pdf/templates` | 401 | 403 |
| GET | `/api/pdf/templates/{doc_type}` | 401 | 403 |
| PUT | `/api/pdf/templates/{doc_type}` | 401 | 403 |
| DELETE | `/api/pdf/templates/{doc_type}` | 401 | 403 |
| POST | `/api/pdf/templates/validate-script` | 401 | 403 |
| GET | `/api/pdf/branding/{entity_id}` | 401 | 403 |
| PUT | `/api/pdf/branding/{entity_id}` | 401 | 403 |
| POST | `/api/pdf/preview` | 401 | 403 |
| POST | `/api/esign/request` | 401 | 403 |
| POST | `/api/esign/verify` | 401 | 403 |
| GET | `/api/esign/signatures/{doc_type}/{source_id}` | 401 | 403 |
| GET | `/api/esign/verify/{code}` | 200 | 200 |
| POST | `/api/deliveries/whatsapp/send` | 401 | 403 |
| GET | `/api/deliveries/whatsapp/settings` | 401 | 403 |
| PUT | `/api/deliveries/whatsapp/settings` | 401 | 403 |
| GET | `/api/deliveries/whatsapp/recipient/{doc_type}/{source_id}` | 401 | 403 |
| GET | `/api/deliveries/whatsapp/rules` | 401 | 403 |
| POST | `/api/deliveries/whatsapp/rules` | 401 | 403 |
| PUT | `/api/deliveries/whatsapp/rules/{rule_id}` | 401 | 403 |
| DELETE | `/api/deliveries/whatsapp/rules/{rule_id}` | 401 | 403 |
| GET | `/api/deliveries/{doc_type}/{source_id}` | 401 | 403 |
| GET | `/api/products/{product_id}/purchase-history` | 401 | 403 |
| GET | `/api/sales-return-policies` | 401 | 403 |
| GET | `/api/sales-return-policies/eligibility` | 401 | 403 |
| POST | `/api/sales-return-policies` | 401 | 403 |
| GET | `/api/sales-return-policies/{policy_id}` | 401 | 403 |
| PATCH | `/api/sales-return-policies/{policy_id}` | 401 | 403 |
| DELETE | `/api/sales-return-policies/{policy_id}` | 401 | 403 |
| GET | `/api/entity-masters` | 401 | 403 |
| GET | `/api/entity-masters/{kind}` | 401 | 403 |
| GET | `/api/entity-masters/{kind}/effective` | 401 | 403 |
| POST | `/api/entity-masters/{kind}` | 401 | 403 |
| PATCH | `/api/entity-masters/{kind}/{row_id}` | 401 | 403 |
| POST | `/api/entity-masters/{kind}/{row_id}/override` | 401 | 403 |
| DELETE | `/api/entity-masters/{kind}/{row_id}` | 401 | 403 |
| GET | `/api/store-credit` | 401 | 403 |
| GET | `/api/store-credit/balance` | 401 | 403 |
| GET | `/api/store-credit/ledger` | 401 | 403 |
| GET | `/api/store-credit/open-orders` | 401 | 403 |
| POST | `/api/store-credit/redeem` | 401 | 403 |
| POST | `/api/store-credit/adjust` | 401 | 403 |
| POST | `/api/store-credit/entries/{entry_id}/reverse` | 401 | 403 |
| GET | `/api/bank-reconciliation/formats` | 401 | 403 |
| POST | `/api/bank-reconciliation/formats` | 401 | 403 |
| DELETE | `/api/bank-reconciliation/formats/{format_id}` | 401 | 403 |
| POST | `/api/bank-reconciliation/preview` | 401 | 403 |
| POST | `/api/bank-reconciliation/import` | 401 | 403 |
| POST | `/api/bank-reconciliation/import-file` | 401 | 403 |
| POST | `/api/bank-reconciliation/auto-match` | 401 | 403 |
| GET | `/api/bank-reconciliation/lines` | 401 | 403 |
| GET | `/api/bank-reconciliation/lines/{line_id}/candidates` | 401 | 403 |
| GET | `/api/bank-reconciliation/summary` | 401 | 403 |
| POST | `/api/bank-reconciliation/lines/{line_id}/match` | 401 | 403 |
| POST | `/api/bank-reconciliation/lines/{line_id}/match-split` | 401 | 403 |
| POST | `/api/bank-reconciliation/match-group` | 401 | 403 |
| POST | `/api/bank-reconciliation/lines/{line_id}/unmatch` | 401 | 403 |
| POST | `/api/bank-reconciliation/lines/{line_id}/ignore` | 401 | 403 |
| POST | `/api/bank-reconciliation/lines/{line_id}/unignore` | 401 | 403 |
| POST | `/api/bank-reconciliation/lines/{line_id}/book-charge` | 401 | 403 |
| GET | `/api/bank-reconciliation/rules` | 401 | 403 |
| POST | `/api/bank-reconciliation/rules/{rule_id}/decide` | 401 | 403 |
| GET | `/api/bank-reconciliation/holding` | 401 | 403 |
| POST | `/api/bank-reconciliation/lines/{line_id}/holding` | 401 | 403 |
| POST | `/api/bank-reconciliation/lines/{line_id}/holding/allocate` | 401 | 403 |
| POST | `/api/bank-reconciliation/lines/{line_id}/holding/cancel` | 401 | 403 |
| GET | `/api/finance-cases/playbooks` | 401 | 403 |
| GET | `/api/finance-cases/reasons` | 401 | 403 |
| GET | `/api/finance-cases/policy` | 401 | 403 |
| GET | `/api/finance-cases/stats` | 401 | 403 |
| GET | `/api/finance-cases` | 401 | 403 |
| GET | `/api/finance-cases/{case_id}` | 401 | 403 |
| POST | `/api/finance-cases` | 401 | 403 |
| POST | `/api/finance-cases/{case_id}/assign` | 401 | 403 |
| POST | `/api/finance-cases/{case_id}/note` | 401 | 403 |
| POST | `/api/finance-cases/{case_id}/resolve` | 401 | 403 |
| POST | `/api/finance-cases/{case_id}/reject` | 401 | 403 |
| POST | `/api/finance-cases/{case_id}/reopen` | 401 | 403 |
| POST | `/api/finance-cases/scan` | 401 | 403 |
| GET | `/api/contra-bons/meta` | 401 | 403 |
| GET | `/api/contra-bons/summary` | 401 | 403 |
| GET | `/api/contra-bons/status-counts` | 401 | 403 |
| GET | `/api/contra-bons/prepare` | 401 | 403 |
| GET | `/api/contra-bons/unbilled-receipts` | 401 | 403 |
| GET | `/api/contra-bons/exchange-schedules` | 401 | 403 |
| PUT | `/api/suppliers/{supplier_id}/invoice-exchange` | 401 | 403 |
| GET | `/api/contra-bons/bank-line-candidates/{line_id}` | 401 | 403 |
| POST | `/api/contra-bons/run-reminder` | 401 | 403 |
| GET | `/api/contra-bons` | 401 | 403 |
| GET | `/api/contra-bons/{cb_id}` | 401 | 403 |
| GET | `/api/contra-bons/{cb_id}/receipt` | 401 | 403 |
| POST | `/api/contra-bons` | 401 | 403 |
| POST | `/api/contra-bons/{cb_id}/deductions` | 401 | 403 |
| DELETE | `/api/contra-bons/{cb_id}/deductions/{ded_id}` | 401 | 403 |
| POST | `/api/contra-bons/{cb_id}/decide` | 401 | 403 |
| POST | `/api/contra-bons/{cb_id}/submit` | 401 | 403 |
| POST | `/api/contra-bons/{cb_id}/verify` | 401 | 403 |
| POST | `/api/contra-bons/{cb_id}/approve` | 401 | 403 |
| POST | `/api/contra-bons/{cb_id}/schedule` | 401 | 403 |
| POST | `/api/contra-bons/{cb_id}/pay` | 401 | 403 |
| POST | `/api/contra-bons/{cb_id}/pay-from-bank-line/{line_id}` | 401 | 403 |
| POST | `/api/contra-bons/{cb_id}/dispute` | 401 | 403 |
| POST | `/api/contra-bons/{cb_id}/cancel` | 401 | 403 |
| GET | `/api/interco/meta` | 401 | 403 |
| GET | `/api/interco/summary` | 401 | 403 |
| GET | `/api/interco/transactions` | 401 | 403 |
| POST | `/api/interco/transactions` | 401 | 403 |
| GET | `/api/interco/transactions/{interco_id}` | 401 | 403 |
| POST | `/api/interco/transactions/{interco_id}/confirm` | 401 | 403 |
| POST | `/api/interco/transactions/{interco_id}/ship` | 401 | 403 |
| POST | `/api/interco/transactions/{interco_id}/receive` | 401 | 403 |
| POST | `/api/interco/transactions/{interco_id}/invoice` | 401 | 403 |
| POST | `/api/interco/transactions/{interco_id}/cancel` | 401 | 403 |
| GET | `/api/interco/transactions/{interco_id}/journal` | 401 | 403 |
| POST | `/api/interco/transactions/{interco_id}/warehouse-task` | 401 | 403 |
| GET | `/api/interco/accounts` | 401 | 403 |
| GET | `/api/interco/accounts/{from_entity_id}/{to_entity_id}` | 401 | 403 |
| GET | `/api/interco/settlements` | 401 | 403 |
| POST | `/api/interco/settlements` | 401 | 403 |
| GET | `/api/interco/settlements/{sid}` | 401 | 403 |
| GET | `/api/interco/contracts` | 401 | 403 |
| GET | `/api/interco/transactions/{interco_id}/tax-invoice` | 401 | 403 |
| POST | `/api/interco/transactions/{interco_id}/tax-invoice` | 401 | 403 |
| POST | `/api/interco/transactions/{interco_id}/tax-invoice/replace` | 401 | 403 |
| POST | `/api/interco/transactions/{interco_id}/tax-invoice/cancel` | 401 | 403 |
| GET | `/api/interco/returns/meta` | 401 | 403 |
| GET | `/api/interco/returns` | 401 | 403 |
| GET | `/api/interco/transactions/{interco_id}/returnable` | 401 | 403 |
| POST | `/api/interco/returns` | 401 | 403 |
| GET | `/api/interco/returns/{ret_id}` | 401 | 403 |
| POST | `/api/interco/returns/{ret_id}/approve` | 401 | 403 |
| POST | `/api/interco/returns/{ret_id}/warehouse-task` | 401 | 403 |
| POST | `/api/interco/returns/{ret_id}/cancel` | 401 | 403 |
| GET | `/api/interco/reminders` | 401 | 403 |
| POST | `/api/interco/accounts/{payer_entity_id}/{payee_entity_id}/remind` | 401 | 403 |
| GET | `/api/interco/margin-report` | 401 | 403 |
| GET | `/api/interco/margin-by-product` | 401 | 403 |
| GET | `/api/interco/loans/meta` | 401 | 403 |
| GET | `/api/interco/loans` | 401 | 403 |
| POST | `/api/interco/loans` | 401 | 403 |
| GET | `/api/interco/loans/{loan_id}` | 401 | 403 |
| POST | `/api/interco/loans/{loan_id}/disburse` | 401 | 403 |
| POST | `/api/interco/loans/{loan_id}/repay` | 401 | 403 |
| POST | `/api/interco/loans/{loan_id}/cancel` | 401 | 403 |
| GET | `/api/interco/non-trade/{from_entity_id}/{to_entity_id}` | 401 | 403 |
| GET | `/api/internal-requests/meta` | 401 | 403 |
| GET | `/api/internal-requests` | 401 | 403 |
| POST | `/api/internal-requests` | 401 | 403 |
| GET | `/api/internal-requests/{req_id}` | 401 | 403 |
| GET | `/api/internal-requests/{req_id}/sources` | 401 | 403 |
| POST | `/api/internal-requests/{req_id}/cancel` | 401 | 403 |
| POST | `/api/internal-requests/{req_id}/reject` | 401 | 403 |
| POST | `/api/internal-requests/{req_id}/convert` | 401 | 403 |
| GET | `/api/internal-requests-availability/{product_id}` | 401 | 403 |
| GET | `/api/design-requests/meta` | 401 | 403 |
| GET | `/api/design-requests` | 401 | 403 |
| POST | `/api/design-requests` | 401 | 403 |
| GET | `/api/design-requests/{req_id}` | 401 | 403 |
| POST | `/api/design-requests/{req_id}/create-design` | 401 | 403 |
| POST | `/api/design-requests/{req_id}/references` | 401 | 403 |
| GET | `/api/design-requests/{req_id}/references/{file_id}` | 401 | 403 |
| DELETE | `/api/design-requests/{req_id}/references/{file_id}` | 401 | 403 |
| POST | `/api/design-requests/{req_id}/link-design` | 401 | 403 |
| PATCH | `/api/design-requests/{req_id}` | 401 | 403 |
| POST | `/api/design-requests/{req_id}/submit` | 401 | 403 |
| POST | `/api/design-requests/{req_id}/assign` | 401 | 403 |
| POST | `/api/design-requests/{req_id}/start` | 401 | 403 |
| POST | `/api/design-requests/{req_id}/deliver` | 401 | 403 |
| POST | `/api/design-requests/{req_id}/approve` | 401 | 403 |
| POST | `/api/design-requests/{req_id}/reject` | 401 | 403 |
| POST | `/api/design-requests/{req_id}/cancel` | 401 | 403 |
| GET | `/api/design/reports/by-designer` | 401 | 403 |
| GET | `/api/design/reports/mine` | 401 | 403 |
| GET | `/api/design-requests-for-so/{so_id}` | 401 | 403 |
| GET | `/api/design-studio/meta` | 401 | 403 |
| GET | `/api/design-studio/next-code` | 401 | 403 |
| GET | `/api/design-studio/tags` | 401 | 403 |
| GET | `/api/design-studio/categories` | 401 | 403 |
| POST | `/api/design-studio/categories` | 401 | 403 |
| PATCH | `/api/design-studio/categories/{cat_id}` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/lifecycle/submit` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/lifecycle/start-review` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/lifecycle/request-revision` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/lifecycle/approve` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/lifecycle/activate` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/lifecycle/submit-final` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/lifecycle/return-final` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/lifecycle/archive` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/lifecycle/reopen` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/new-version` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/lifecycle/hold` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/lifecycle/release-hold` | 401 | 403 |
| GET | `/api/design-gallery/{gallery_id}/history` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/feedback` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/colorways` | 401 | 403 |
| PUT | `/api/design-gallery/{gallery_id}/colorways/{cw_id}` | 401 | 403 |
| DELETE | `/api/design-gallery/{gallery_id}/colorways/{cw_id}` | 401 | 403 |
| POST | `/api/design-gallery/{gallery_id}/files-kind/{kind}` | 401 | 403 |
| GET | `/api/logistics/meta` | 401 | 403 |
| GET | `/api/logistics/summary` | 401 | 403 |
| GET | `/api/logistics/dashboard` | 401 | 403 |
| GET | `/api/logistics/history` | 401 | 403 |
| GET | `/api/logistics/fleet/availability` | 401 | 403 |
| GET | `/api/logistics/fleet/vehicles` | 401 | 403 |
| POST | `/api/logistics/fleet/vehicles` | 401 | 403 |
| PATCH | `/api/logistics/fleet/vehicles/{vehicle_id}` | 401 | 403 |
| POST | `/api/logistics/fleet/vehicles/{vehicle_id}/status` | 401 | 403 |
| GET | `/api/logistics/shipments/unassigned` | 401 | 403 |
| GET | `/api/logistics/drivers` | 401 | 403 |
| POST | `/api/logistics/my-route` | 401 | 403 |
| GET | `/api/logistics/deliveries` | 401 | 403 |
| POST | `/api/logistics/deliveries` | 401 | 403 |
| GET | `/api/logistics/deliveries/{delivery_id}` | 401 | 403 |
| POST | `/api/logistics/deliveries/{delivery_id}/pickup-handover` | 401 | 403 |
| PATCH | `/api/logistics/deliveries/{delivery_id}` | 401 | 403 |
| POST | `/api/logistics/deliveries/{delivery_id}/photos` | 401 | 403 |
| GET | `/api/logistics/deliveries/{delivery_id}/photos/{photo_id}` | 401 | 403 |
| DELETE | `/api/logistics/deliveries/{delivery_id}/photos/{photo_id}` | 401 | 403 |
| POST | `/api/logistics/deliveries/{delivery_id}/positions` | 401 | 403 |
| DELETE | `/api/logistics/deliveries/{delivery_id}/positions/{pos_id}` | 401 | 403 |
| POST | `/api/logistics/deliveries/{delivery_id}/transition` | 401 | 403 |
| GET | `/api/inspections/meta` | 401 | 403 |
| GET | `/api/inspections` | 401 | 403 |
| GET | `/api/inspections/export` | 401 | 403 |
| GET | `/api/inspections/{ins_id}` | 401 | 403 |
| POST | `/api/inspections` | 401 | 403 |
| POST | `/api/inspections/{ins_id}/assign` | 401 | 403 |
| POST | `/api/inspections/{ins_id}/start` | 401 | 403 |
| POST | `/api/inspections/{ins_id}/lines/{line_id}/inspect` | 401 | 403 |
| POST | `/api/inspections/{ins_id}/lines/{line_id}/release-hold` | 401 | 403 |
| POST | `/api/inspections/{ins_id}/finish` | 401 | 403 |
| POST | `/api/inspections/{ins_id}/reopen` | 401 | 403 |
| GET | `/api/inspections/meta/ref-docs` | 401 | 403 |
| GET | `/api/inspections/{ins_id}/pdf` | 401 | 403 |
| GET | `/api/inspections/queue/qc-tasks` | 401 | 403 |
| GET | `/api/finance/period-unlocks` | 401 | 200 |
| GET | `/api/finance/period-unlocks/active` | 401 | 200 |
| POST | `/api/finance/period-unlocks` | 401 | 403 |
| POST | `/api/finance/period-unlocks/{plu_id}/approve` | 401 | 403 |
| POST | `/api/finance/period-unlocks/{plu_id}/reject` | 401 | 403 |
| POST | `/api/finance/period-unlocks/reclose-expired` | 401 | 403 |
| GET | `/api/fixed-assets` | 401 | 403 |
| GET | `/api/fixed-assets/meta` | 401 | 403 |
| GET | `/api/fixed-assets/summary` | 401 | 403 |
| POST | `/api/fixed-assets` | 401 | 403 |
| POST | `/api/fixed-assets/run-depreciation` | 401 | 403 |
| GET | `/api/fixed-assets/{asset_id}` | 401 | 403 |
| PATCH | `/api/fixed-assets/{asset_id}` | 401 | 403 |
| POST | `/api/fixed-assets/{asset_id}/dispose` | 401 | 403 |
| POST | `/api/fixed-assets/{asset_id}/transfer` | 401 | 403 |
| POST | `/api/fixed-assets/{asset_id}/transfer/settle` | 401 | 403 |
| GET | `/api/production/boms` | 401 | 403 |
| POST | `/api/production/boms` | 401 | 403 |
| GET | `/api/production/boms/{bom_id}` | 401 | 403 |
| PATCH | `/api/production/boms/{bom_id}` | 401 | 403 |
| DELETE | `/api/production/boms/{bom_id}` | 401 | 403 |
| GET | `/api/production/work-orders` | 401 | 403 |
| POST | `/api/production/work-orders` | 401 | 403 |
| GET | `/api/production/work-orders/{wo_id}` | 401 | 403 |
| POST | `/api/production/work-orders/{wo_id}/release` | 401 | 403 |
| POST | `/api/production/work-orders/{wo_id}/complete` | 401 | 403 |
| POST | `/api/production/work-orders/{wo_id}/cancel` | 401 | 403 |
| GET | `/api/production/summary` | 401 | 403 |
| GET | `/api/scheduler/jobs` | 401 | 403 |
| GET | `/api/scheduler/summary` | 401 | 403 |
| POST | `/api/scheduler/jobs/{job_id}/run` | 401 | 403 |
| GET | `/api/scheduler/runs` | 401 | 403 |
| GET | `/api/scheduler/settings` | 401 | 403 |
| GET | `/api/scheduler/digest-preview` | 401 | 403 |
| PUT | `/api/scheduler/settings` | 401 | 403 |
| GET | `/api/scheduler/wa-outbox` | 401 | 403 |
| POST | `/api/scheduler/wa-outbox/{outbox_id}/retry` | 401 | 403 |
| POST | `/api/scheduler/wa-test` | 401 | 403 |
| GET | `/api/lots` | 401 | 403 |
| GET | `/api/lots/stats` | 401 | 403 |
| GET | `/api/lots/settings` | 401 | 403 |
| PUT | `/api/lots/settings` | 401 | 403 |
| GET | `/api/lots/unassigned-rolls` | 401 | 403 |
| GET | `/api/lots/{lot_id}` | 401 | 403 |
| GET | `/api/lots/{lot_id}/genealogy` | 401 | 403 |
| GET | `/api/lots/{lot_id}/recall` | 401 | 403 |
| POST | `/api/lots/{lot_id}/label` | 401 | 403 |
| POST | `/api/lots` | 401 | 403 |
| PATCH | `/api/lots/{lot_id}` | 401 | 403 |
| POST | `/api/lots/{lot_id}/status` | 401 | 403 |
| POST | `/api/lots/{lot_id}/rolls` | 401 | 403 |
| POST | `/api/lots/{lot_id}/split` | 401 | 403 |
| POST | `/api/lots/merge` | 401 | 403 |
| POST | `/api/lots/{lot_id}/rework` | 401 | 403 |
| GET | `/api/rolls/{roll_id}/lot` | 401 | 403 |
| GET | `/api/supplier-contracts` | 401 | 403 |
| GET | `/api/supplier-contracts/stats` | 401 | 403 |
| GET | `/api/supplier-contracts/policy` | 401 | 403 |
| PUT | `/api/supplier-contracts/policy` | 401 | 403 |
| POST | `/api/supplier-contracts/resolve` | 401 | 403 |
| POST | `/api/supplier-contracts/tariff-preview` | 401 | 403 |
| GET | `/api/supplier-contracts/{contract_id}` | 401 | 403 |
| POST | `/api/supplier-contracts` | 401 | 403 |
| PATCH | `/api/supplier-contracts/{contract_id}` | 401 | 403 |
| POST | `/api/supplier-contracts/{contract_id}/status` | 401 | 403 |
| DELETE | `/api/supplier-contracts/{contract_id}` | 401 | 403 |
| GET | `/api/makloon-partners/scorecard` | 401 | 403 |
| GET | `/api/supplier-items` | 401 | 403 |
| GET | `/api/supplier-items/stats` | 401 | 403 |
| GET | `/api/supplier-items/lookup` | 401 | 403 |
| GET | `/api/supplier-items/import-template` | 401 | 403 |
| POST | `/api/supplier-items/import` | 401 | 403 |
| POST | `/api/supplier-items/import-file` | 401 | 403 |
| GET | `/api/supplier-items/{sid}` | 401 | 403 |
| POST | `/api/supplier-items` | 401 | 403 |
| PATCH | `/api/supplier-items/{sid}` | 401 | 403 |
| DELETE | `/api/supplier-items/{sid}` | 401 | 403 |
| GET | `/api/config/registry` | 401 | 200 |
| GET | `/api/config/effective` | 401 | 200 |
| GET | `/api/config/explain` | 401 | 404 |
| POST | `/api/config/simulate` | 401 | 404 |
| PUT | `/api/config/values` | 401 | 400 |
| POST | `/api/config/values/reset` | 401 | 404 |
| POST | `/api/config/values/clear` | 401 | 404 |
| GET | `/api/config/history` | 401 | 200 |
| GET | `/api/config/health` | 401 | 403 |
| POST | `/api/config/impact-preview` | 401 | 403 |
| POST | `/api/config/impact-apply` | 401 | 403 |
| GET | `/api/config/simulators` | 401 | 200 |
| GET | `/api/amendment-reasons` | 401 | 403 |
| PUT | `/api/amendment-reasons` | 401 | 403 |
| POST | `/api/amendments/preview` | 401 | 403 |
| POST | `/api/amendments` | 401 | 403 |
| GET | `/api/amendments` | 401 | 403 |
| GET | `/api/amendments/stats/summary` | 401 | 403 |
| GET | `/api/amendments/doc/{doc_type}/{doc_id}` | 401 | 403 |
| GET | `/api/amendments/{amd_id}` | 401 | 403 |
| POST | `/api/amendments/{amd_id}/decision` | 401 | 403 |
| GET | `/api/payment-plans/meta` | 401 | 403 |
| POST | `/api/payment-plans/preview` | 401 | 403 |
| GET | `/api/payment-plans` | 401 | 403 |
| GET | `/api/payment-plans/by-doc/{doc_type}/{doc_id}` | 401 | 403 |
| POST | `/api/payment-plans` | 401 | 403 |
| PATCH | `/api/payment-plans/{plan_id}` | 401 | 403 |
| POST | `/api/payment-plans/{plan_id}/void` | 401 | 403 |
| POST | `/api/payment-plans/{plan_id}/accrue` | 401 | 403 |
| GET | `/api/penalties` | 401 | 403 |
| GET | `/api/penalties/{penalty_id}` | 401 | 403 |
| POST | `/api/penalties/{penalty_id}/issue` | 401 | 403 |
| POST | `/api/penalties/{penalty_id}/waive` | 401 | 403 |
| POST | `/api/penalties/{penalty_id}/adjust` | 401 | 403 |
| POST | `/api/penalties/{penalty_id}/pay` | 401 | 403 |
| GET | `/api/payment-variances/meta` | 401 | 403 |
| POST | `/api/payment-variances/assess` | 401 | 403 |
| GET | `/api/payment-variances` | 401 | 403 |
| GET | `/api/payment-variances/pending` | 401 | 403 |
| GET | `/api/payment-variances/receipt/{receipt_id}` | 401 | 403 |
| POST | `/api/payment-variances/receipt/{receipt_id}/decide` | 401 | 403 |
| GET | `/api/payment-variances/{decision_id}` | 401 | 403 |
| POST | `/api/payment-variances/{decision_id}/reverse` | 401 | 403 |
| GET | `/api/rnd/meta` | 401 | 403 |
| GET | `/api/rnd/sample-types` | 401 | 403 |
| GET | `/api/rnd/specs` | 401 | 403 |
| POST | `/api/rnd/specs` | 401 | 403 |
| GET | `/api/rnd/specs/{spec_id}` | 401 | 403 |
| PATCH | `/api/rnd/specs/{spec_id}` | 401 | 403 |
| POST | `/api/rnd/specs/{spec_id}/submit` | 401 | 403 |
| POST | `/api/rnd/specs/{spec_id}/approve` | 401 | 403 |
| POST | `/api/rnd/specs/{spec_id}/reject` | 401 | 403 |
| POST | `/api/rnd/specs/{spec_id}/release-product` | 401 | 403 |
| GET | `/api/rnd/samples` | 401 | 403 |
| POST | `/api/rnd/samples/{sample_id}/spec` | 401 | 403 |
| GET | `/api/rnd/labdip-history` | 401 | 403 |
| POST | `/api/rnd/samples` | 401 | 403 |
| GET | `/api/rnd/samples/{sample_id}` | 401 | 403 |
| PATCH | `/api/rnd/samples/{sample_id}` | 401 | 403 |
| POST | `/api/rnd/samples/{sample_id}/send` | 401 | 403 |
| POST | `/api/rnd/samples/{sample_id}/rounds` | 401 | 403 |
| POST | `/api/rnd/samples/{sample_id}/rounds/{round_id}/attachments` | 401 | 403 |
| GET | `/api/rnd/samples/{sample_id}/rounds/{round_id}/attachments/{file_id}` | 401 | 403 |
| POST | `/api/rnd/samples/{sample_id}/rounds/{round_id}/submit` | 401 | 403 |
| POST | `/api/rnd/samples/{sample_id}/rounds/{round_id}/assess` | 401 | 403 |
| POST | `/api/rnd/samples/{sample_id}/decide` | 401 | 403 |
| POST | `/api/rnd/samples/{sample_id}/issue-material` | 401 | 403 |
| POST | `/api/rnd/samples/{sample_id}/cancel` | 401 | 403 |
| POST | `/api/rnd/samples/{sample_id}/finish` | 401 | 403 |
| POST | `/api/rnd/samples/{sample_id}/deliver` | 401 | 403 |
| GET | `/api/rnd/reports/performer` | 401 | 403 |
| GET | `/api/rnd/reports/designer-kpi` | 401 | 403 |
| GET | `/api/rnd/reports/my-kpi` | 401 | 200 |
| GET | `/api/rnd/reports/designer-kpi/trend` | 401 | 403 |
| GET | `/api/rnd/reports/designer-kpi/export` | 401 | 403 |
| GET | `/api/rnd/reports/designer-kpi/report` | 401 | 403 |
| GET | `/api/rnd/sla/board` | 401 | 403 |
| POST | `/api/rnd/sla/escalate` | 401 | 403 |
| GET | `/api/rnd/lifecycle-board` | 401 | 403 |
| GET | `/api/rnd/divisions` | 401 | 403 |
| GET | `/api/rnd/divisions/members` | 401 | 403 |
| PUT | `/api/rnd/divisions/members` | 401 | 403 |
| GET | `/api/approvals/matrix` | 401 | 403 |
| GET | `/api/approvals/my-queue` | 401 | 403 |
| GET | `/api/approvals/matrix-log` | 401 | 403 |
| GET | `/api/customer-prices` | 401 | 403 |
| GET | `/api/customer-prices/records` | 401 | 403 |
| GET | `/api/customer-prices/quote` | 401 | 403 |
| GET | `/api/customer-prices/floor` | 401 | 403 |
| GET | `/api/customer-prices/export` | 401 | 403 |
| POST | `/api/customer-prices` | 401 | 403 |
| POST | `/api/customer-prices/import` | 401 | 403 |
| PATCH | `/api/customer-prices/{price_id}` | 401 | 403 |
| DELETE | `/api/customer-prices/{price_id}` | 401 | 403 |
| GET | `/api/sales-admin/desk` | 401 | 403 |
| GET | `/api/sales-orders/{order_id}/verification` | 401 | 403 |
| POST | `/api/sales-orders/{order_id}/verify` | 401 | 403 |
| GET | `/api/sales-admin/orders/{order_id}/fulfillment` | 401 | 403 |
| POST | `/api/sales-admin/orders/{order_id}/fulfillment-decision` | 401 | 403 |
| GET | `/api/md/desk` | 401 | 403 |
| GET | `/api/warehouse-admin/desk` | 401 | 403 |
| GET | `/api/finance/desk` | 401 | 403 |
| GET | `/api/desks/me` | 401 | 404 |
| GET | `/api/access/role-reality` | 401 | 403 |
| POST | `/api/access/role-reality/{user_id}/apply` | 401 | 403 |

## Fungsi dengan setidaknya satu baris dieksekusi

Kolom jumlah baris menyatakan baris yang teramati dijalankan. Angka itu bukan ukuran fungsi atau bukti semua cabang telah diuji. Persentase cakupan baris dan fungsi menyeluruh belum dihitung.

| Fungsi | Baris berbeda teramati |
|---|---|
| [backend/access_modules.py:148 level_of](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/access_modules.py#L148) | 6 |
| [backend/access_modules.py:270 nav_allowed_for_perms](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/access_modules.py#L270) | 4 |
| [backend/config_registry.py:249 all_entries](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/config_registry.py#L249) | 1 |
| [backend/config_registry.py:253 get](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/config_registry.py#L253) | 1 |
| [backend/config_registry.py:257 require](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/config_registry.py#L257) | 3 |
| [backend/config_registry.py:268 groups](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/config_registry.py#L268) | 6 |
| [backend/core_utils.py:14 now_iso](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/core_utils.py#L14) | 1 |
| [backend/core_utils.py:18 next_doc_number](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/core_utils.py#L18) | 18 |
| [backend/core_utils.py:83 entity_code](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/core_utils.py#L83) | 8 |
| [backend/core_utils.py:111 _max_existing_number](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/core_utils.py#L111) | 6 |
| [backend/core_utils.py:127 new_id](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/core_utils.py#L127) | 1 |
| [backend/core_utils.py:141 parse_decimal](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/core_utils.py#L141) | 4 |
| [backend/core_utils.py:178 _qty_validator](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/core_utils.py#L178) | 2 |
| [backend/core_utils.py:185 _money_validator](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/core_utils.py#L185) | 2 |
| [backend/core_utils.py:308 _coerce](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/core_utils.py#L308) | 9 |
| [backend/core_utils.py:329 safe_doc](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/core_utils.py#L329) | 3 |
| [backend/core_utils.py:370 strip_cost_fields](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/core_utils.py#L370) | 4 |
| [backend/dependencies.py:15 session_expiry](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L15) | 1 |
| [backend/dependencies.py:19 _as_utc](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L19) | 2 |
| [backend/dependencies.py:25 extract_token](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L25) | 6 |
| [backend/dependencies.py:35 current_user](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L35) | 26 |
| [backend/dependencies.py:81 require_role](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L81) | 4 |
| [backend/dependencies.py:89 permission_matrix](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L89) | 2 |
| [backend/dependencies.py:94 has_permission](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L94) | 2 |
| [backend/dependencies.py:100 require_permission](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L100) | 4 |
| [backend/dependencies.py:107 require_any_permission](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L107) | 9 |
| [backend/dependencies.py:130 audit](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/dependencies.py#L130) | 26 |
| [backend/domain_registry.py:26 __init__](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L26) | 3 |
| [backend/domain_registry.py:776 enum_names](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L776) | 1 |
| [backend/domain_registry.py:780 enum_meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L780) | 6 |
| [backend/domain_registry.py:789 enum_items](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L789) | 1 |
| [backend/domain_registry.py:793 values_of](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L793) | 1 |
| [backend/domain_registry.py:802 label_of](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L802) | 3 |
| [backend/domain_registry.py:846 normalize_grade](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L846) | 3 |
| [backend/domain_registry.py:872 normalize_stage](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L872) | 5 |
| [backend/domain_registry.py:880 normalize_fabric_type](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L880) | 5 |
| [backend/domain_registry.py:892 transitions](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L892) | 4 |
| [backend/domain_registry.py:902 transition_matrix](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L902) | 13 |
| [backend/domain_registry.py:920 resolve_transition](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L920) | 4 |
| [backend/domain_registry.py:1010 field_rules](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L1010) | 8 |
| [backend/domain_registry.py:1025 _has_value](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L1025) | 5 |
| [backend/domain_registry.py:1035 validate_product](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L1035) | 34 |
| [backend/domain_registry.py:1278 registry_snapshot](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/domain_registry.py#L1278) | 19 |
| [backend/entity_scope.py:292 field_for](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/entity_scope.py#L292) | 3 |
| [backend/entity_scope.py:335 entity_ctx](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/entity_scope.py#L335) | 21 |
| [backend/entity_scope.py:447 guard_doc](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/entity_scope.py#L447) | 2 |
| [backend/entity_scope.py:464 resolve_list_scope](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/entity_scope.py#L464) | 8 |
| [backend/entity_scope.py:493 resolve_scope_ids](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/entity_scope.py#L493) | 4 |
| [backend/entity_write_guard.py:189 dispatch](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/entity_write_guard.py#L189) | 3 |
| [backend/idempotency.py:27 dispatch](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/idempotency.py#L27) | 3 |
| [backend/pagination.py:23 is_paged](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/pagination.py#L23) | 2 |
| [backend/request_context.py:21 set_active_entity](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/request_context.py#L21) | 2 |
| [backend/request_context.py:26 get_active_entity](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/request_context.py#L26) | 1 |
| [backend/request_context.py:30 set_actor](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/request_context.py#L30) | 2 |
| [backend/request_context.py:35 get_actor](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/request_context.py#L35) | 1 |
| [backend/request_context.py:45 resolve_from_user](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/request_context.py#L45) | 5 |
| [backend/role_registry.py:217 register_custom_roles](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/role_registry.py#L217) | 4 |
| [backend/role_registry.py:257 role_ids](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/role_registry.py#L257) | 1 |
| [backend/role_registry.py:266 role_in](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/role_registry.py#L266) | 4 |
| [backend/role_registry.py:275 role_label](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/role_registry.py#L275) | 3 |
| [backend/role_registry.py:312 public_list](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/role_registry.py#L312) | 16 |
| [backend/routers/access_review.py:34 role_reality](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/access_review.py#L34) | 1 |
| [backend/routers/access_review.py:42 apply_reclassification](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/access_review.py#L42) | 1 |
| [backend/routers/access_roles.py:42 preview_role](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/access_roles.py#L42) | 1 |
| [backend/routers/access_roles.py:48 move_role_users](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/access_roles.py#L48) | 1 |
| [backend/routers/access_roles.py:56 list_modules](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/access_roles.py#L56) | 1 |
| [backend/routers/access_roles.py:63 list_roles](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/access_roles.py#L63) | 1 |
| [backend/routers/access_roles.py:69 get_role](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/access_roles.py#L69) | 1 |
| [backend/routers/access_roles.py:75 create_role](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/access_roles.py#L75) | 1 |
| [backend/routers/access_roles.py:84 patch_role](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/access_roles.py#L84) | 1 |
| [backend/routers/access_roles.py:93 reset_role](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/access_roles.py#L93) | 1 |
| [backend/routers/access_roles.py:101 delete_role](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/access_roles.py#L101) | 1 |
| [backend/routers/admin.py:144 import_products](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/admin.py#L144) | 1 |
| [backend/routers/admin.py:203 import_customers](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/admin.py#L203) | 1 |
| [backend/routers/admin.py:327 import_warehouses](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/admin.py#L327) | 1 |
| [backend/routers/admin.py:376 export_products](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/admin.py#L376) | 1 |
| [backend/routers/admin.py:391 export_yarn](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/admin.py#L391) | 1 |
| [backend/routers/admin.py:414 export_customers](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/admin.py#L414) | 1 |
| [backend/routers/admin.py:435 export_warehouses](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/admin.py#L435) | 1 |
| [backend/routers/admin.py:448 get_permissions](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/admin.py#L448) | 1 |
| [backend/routers/admin.py:455 update_permissions](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/admin.py#L455) | 1 |
| [backend/routers/admin.py:480 seed_demo](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/admin.py#L480) | 1 |
| [backend/routers/ai_analytics.py:18 _ai_user](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L18) | 5 |
| [backend/routers/ai_analytics.py:27 _run](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L27) | 1 |
| [backend/routers/ai_analytics.py:36 get_catalog](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L36) | 1 |
| [backend/routers/ai_analytics.py:45 post_query](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L45) | 1 |
| [backend/routers/ai_analytics.py:50 post_analyze_change](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L50) | 1 |
| [backend/routers/ai_analytics.py:55 get_result](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L55) | 1 |
| [backend/routers/ai_analytics.py:64 facts_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L64) | 1 |
| [backend/routers/ai_analytics.py:71 facts_rebuild](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L71) | 1 |
| [backend/routers/ai_analytics.py:80 get_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L80) | 2 |
| [backend/routers/ai_analytics.py:86 list_templates](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L86) | 2 |
| [backend/routers/ai_analytics.py:94 run_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L94) | 2 |
| [backend/routers/ai_analytics.py:104 run_tool](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L104) | 2 |
| [backend/routers/ai_analytics.py:114 post_chat](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L114) | 4 |
| [backend/routers/ai_analytics.py:135 list_sessions](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L135) | 2 |
| [backend/routers/ai_analytics.py:149 delete_session](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L149) | 1 |
| [backend/routers/ai_analytics.py:158 get_session](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L158) | 1 |
| [backend/routers/ai_analytics.py:168 post_feedback](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L168) | 2 |
| [backend/routers/ai_analytics.py:222 export_result](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L222) | 2 |
| [backend/routers/ai_analytics.py:232 export_answer](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L232) | 9 |
| [backend/routers/ai_analytics.py:260 post_narrative](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L260) | 3 |
| [backend/routers/ai_analytics.py:277 list_my_templates](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L277) | 1 |
| [backend/routers/ai_analytics.py:283 create_my_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L283) | 2 |
| [backend/routers/ai_analytics.py:298 delete_my_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L298) | 1 |
| [backend/routers/ai_analytics.py:314 list_schedules](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L314) | 1 |
| [backend/routers/ai_analytics.py:320 create_schedule](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L320) | 3 |
| [backend/routers/ai_analytics.py:338 update_schedule](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L338) | 2 |
| [backend/routers/ai_analytics.py:353 delete_schedule](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L353) | 1 |
| [backend/routers/ai_analytics.py:361 run_schedule_now](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L361) | 2 |
| [backend/routers/ai_analytics.py:368 list_schedule_runs](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L368) | 1 |
| [backend/routers/ai_analytics.py:376 get_schedule_run](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L376) | 1 |
| [backend/routers/ai_analytics.py:388 snapshots_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L388) | 2 |
| [backend/routers/ai_analytics.py:395 snapshots_run](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L395) | 2 |
| [backend/routers/ai_analytics.py:404 usage_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L404) | 3 |
| [backend/routers/ai_analytics.py:422 usage_daily](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ai_analytics.py#L422) | 2 |
| [backend/routers/amendments.py:44 list_reasons](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/amendments.py#L44) | 1 |
| [backend/routers/amendments.py:51 upsert_reason](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/amendments.py#L51) | 1 |
| [backend/routers/amendments.py:77 preview](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/amendments.py#L77) | 1 |
| [backend/routers/amendments.py:91 propose](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/amendments.py#L91) | 1 |
| [backend/routers/amendments.py:111 list_amendments](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/amendments.py#L111) | 1 |
| [backend/routers/amendments.py:125 summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/amendments.py#L125) | 1 |
| [backend/routers/amendments.py:132 by_document](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/amendments.py#L132) | 1 |
| [backend/routers/amendments.py:141 detail](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/amendments.py#L141) | 1 |
| [backend/routers/amendments.py:152 decide](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/amendments.py#L152) | 1 |
| [backend/routers/approval_rules.py:55 list_approval_rules](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/approval_rules.py#L55) | 1 |
| [backend/routers/approval_rules.py:77 create_approval_rule](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/approval_rules.py#L77) | 1 |
| [backend/routers/approval_rules.py:97 get_approval_rule](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/approval_rules.py#L97) | 1 |
| [backend/routers/approval_rules.py:108 update_approval_rule](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/approval_rules.py#L108) | 1 |
| [backend/routers/approval_rules.py:132 delete_approval_rule](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/approval_rules.py#L132) | 1 |
| [backend/routers/approvals_matrix.py:49 get_matrix](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/approvals_matrix.py#L49) | 1 |
| [backend/routers/approvals_matrix.py:57 get_my_queue](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/approvals_matrix.py#L57) | 1 |
| [backend/routers/approvals_matrix.py:68 get_matrix_log](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/approvals_matrix.py#L68) | 1 |
| [backend/routers/ar_aging.py:44 ar_aging](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ar_aging.py#L44) | 1 |
| [backend/routers/ar_aging.py:58 ar_aging_accrue](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ar_aging.py#L58) | 1 |
| [backend/routers/ar_aging.py:83 ar_aging_detail](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ar_aging.py#L83) | 1 |
| [backend/routers/ar_aging.py:96 ar_advance_report](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ar_aging.py#L96) | 1 |
| [backend/routers/ar_receipts.py:45 open_orders](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ar_receipts.py#L45) | 1 |
| [backend/routers/ar_receipts.py:52 deposit_balance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ar_receipts.py#L52) | 1 |
| [backend/routers/ar_receipts.py:60 list_receipts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ar_receipts.py#L60) | 1 |
| [backend/routers/ar_receipts.py:68 _perm_ar_receipt_create](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ar_receipts.py#L68) | 1 |
| [backend/routers/ar_receipts.py:97 void_receipt](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ar_receipts.py#L97) | 1 |
| [backend/routers/ar_receipts.py:121 get_receipt](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/ar_receipts.py#L121) | 1 |
| [backend/routers/audit.py:25 list_audit_logs](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/audit.py#L25) | 1 |
| [backend/routers/auth.py:32 _my_permissions](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/auth.py#L32) | 7 |
| [backend/routers/auth.py:53 _client_ip](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/auth.py#L53) | 3 |
| [backend/routers/auth.py:60 _check_lockout](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/auth.py#L60) | 3 |
| [backend/routers/auth.py:74 _register_failure](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/auth.py#L74) | 5 |
| [backend/routers/auth.py:87 login](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/auth.py#L87) | 7 |
| [backend/routers/auth.py:137 list_roles](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/auth.py#L137) | 5 |
| [backend/routers/auth.py:151 me](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/auth.py#L151) | 7 |
| [backend/routers/auth.py:163 auth_context](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/auth.py#L163) | 3 |
| [backend/routers/auth.py:171 logout](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/auth.py#L171) | 4 |
| [backend/routers/bank.py:18 list_bank_accounts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank.py#L18) | 1 |
| [backend/routers/bank.py:37 create_bank_account](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank.py#L37) | 1 |
| [backend/routers/bank.py:56 patch_bank_account](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank.py#L56) | 1 |
| [backend/routers/bank.py:79 bank_account_ledger](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank.py#L79) | 1 |
| [backend/routers/bank.py:89 reconcile_cash_transaction](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank.py#L89) | 1 |
| [backend/routers/bank_reconciliation.py:142 list_formats](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L142) | 1 |
| [backend/routers/bank_reconciliation.py:149 upsert_format](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L149) | 1 |
| [backend/routers/bank_reconciliation.py:163 delete_format](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L163) | 1 |
| [backend/routers/bank_reconciliation.py:175 preview_statement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L175) | 1 |
| [backend/routers/bank_reconciliation.py:187 import_statement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L187) | 1 |
| [backend/routers/bank_reconciliation.py:202 import_file](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L202) | 1 |
| [backend/routers/bank_reconciliation.py:221 auto_match](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L221) | 1 |
| [backend/routers/bank_reconciliation.py:235 list_lines](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L235) | 1 |
| [backend/routers/bank_reconciliation.py:247 line_candidates](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L247) | 1 |
| [backend/routers/bank_reconciliation.py:258 recon_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L258) | 1 |
| [backend/routers/bank_reconciliation.py:269 match_line](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L269) | 1 |
| [backend/routers/bank_reconciliation.py:282 match_split](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L282) | 1 |
| [backend/routers/bank_reconciliation.py:295 match_group](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L295) | 1 |
| [backend/routers/bank_reconciliation.py:308 unmatch_line](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L308) | 1 |
| [backend/routers/bank_reconciliation.py:320 ignore_line](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L320) | 1 |
| [backend/routers/bank_reconciliation.py:333 unignore_line](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L333) | 1 |
| [backend/routers/bank_reconciliation.py:346 book_charge](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L346) | 1 |
| [backend/routers/bank_reconciliation.py:364 list_rules](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L364) | 1 |
| [backend/routers/bank_reconciliation.py:372 decide_rule](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L372) | 1 |
| [backend/routers/bank_reconciliation.py:386 holding_queue](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L386) | 1 |
| [backend/routers/bank_reconciliation.py:394 to_holding](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L394) | 1 |
| [backend/routers/bank_reconciliation.py:408 allocate_holding](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L408) | 1 |
| [backend/routers/bank_reconciliation.py:423 cancel_holding](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/bank_reconciliation.py#L423) | 1 |
| [backend/routers/budgets.py:65 list_budgets](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/budgets.py#L65) | 1 |
| [backend/routers/budgets.py:77 create_budget](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/budgets.py#L77) | 1 |
| [backend/routers/budgets.py:90 update_budget](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/budgets.py#L90) | 1 |
| [backend/routers/budgets.py:104 delete_budget](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/budgets.py#L104) | 1 |
| [backend/routers/budgets.py:115 budget_vs_actual](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/budgets.py#L115) | 1 |
| [backend/routers/budgets.py:129 budget_keys](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/budgets.py#L129) | 1 |
| [backend/routers/budgets.py:146 get_budget_rules](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/budgets.py#L146) | 1 |
| [backend/routers/budgets.py:153 set_budget_rules](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/budgets.py#L153) | 1 |
| [backend/routers/budgets.py:166 check_budget](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/budgets.py#L166) | 1 |
| [backend/routers/cash.py:33 list_cash_transactions](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash.py#L33) | 1 |
| [backend/routers/cash.py:59 cash_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash.py#L59) | 1 |
| [backend/routers/cash.py:108 create_cash_transaction](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash.py#L108) | 1 |
| [backend/routers/cash.py:156 void_cash_transaction](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash.py#L156) | 1 |
| [backend/routers/cash_advances.py:23 list_expense_categories](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L23) | 1 |
| [backend/routers/cash_advances.py:32 update_expense_category](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L32) | 1 |
| [backend/routers/cash_advances.py:39 list_cash_advances](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L39) | 1 |
| [backend/routers/cash_advances.py:47 create_cash_advance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L47) | 1 |
| [backend/routers/cash_advances.py:54 get_cash_advance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L54) | 1 |
| [backend/routers/cash_advances.py:61 update_cash_advance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L61) | 1 |
| [backend/routers/cash_advances.py:68 submit_cash_advance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L68) | 1 |
| [backend/routers/cash_advances.py:75 approve_cash_advance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L75) | 1 |
| [backend/routers/cash_advances.py:82 reject_cash_advance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L82) | 1 |
| [backend/routers/cash_advances.py:89 disburse_cash_advance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L89) | 1 |
| [backend/routers/cash_advances.py:97 list_settlements](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L97) | 1 |
| [backend/routers/cash_advances.py:107 create_settlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L107) | 1 |
| [backend/routers/cash_advances.py:114 get_settlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L114) | 1 |
| [backend/routers/cash_advances.py:121 update_settlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L121) | 1 |
| [backend/routers/cash_advances.py:128 submit_settlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L128) | 1 |
| [backend/routers/cash_advances.py:135 approve_settlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L135) | 1 |
| [backend/routers/cash_advances.py:142 reject_settlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cash_advances.py#L142) | 1 |
| [backend/routers/categories.py:56 list_categories](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/categories.py#L56) | 1 |
| [backend/routers/categories.py:64 list_motifs](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/categories.py#L64) | 1 |
| [backend/routers/categories.py:86 create_category](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/categories.py#L86) | 1 |
| [backend/routers/categories.py:112 delete_category](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/categories.py#L112) | 1 |
| [backend/routers/categories.py:133 update_category](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/categories.py#L133) | 1 |
| [backend/routers/closing.py:38 list_closings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/closing.py#L38) | 1 |
| [backend/routers/closing.py:46 preview_closing](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/closing.py#L46) | 1 |
| [backend/routers/closing.py:59 closing_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/closing.py#L59) | 1 |
| [backend/routers/closing.py:71 close_period](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/closing.py#L71) | 1 |
| [backend/routers/closing.py:85 reopen_period](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/closing.py#L85) | 1 |
| [backend/routers/closing.py:102 reclose_period](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/closing.py#L102) | 1 |
| [backend/routers/color_library.py:25 list_color_library](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L25) | 1 |
| [backend/routers/color_library.py:38 list_customer_colors](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L38) | 1 |
| [backend/routers/color_library.py:51 customer_color_card](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L51) | 1 |
| [backend/routers/color_library.py:74 list_use_requests](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L74) | 1 |
| [backend/routers/color_library.py:81 create_use_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L81) | 1 |
| [backend/routers/color_library.py:95 _decide](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L95) | 1 |
| [backend/routers/color_library.py:110 approve_use_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L110) | 1 |
| [backend/routers/color_library.py:115 reject_use_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L115) | 1 |
| [backend/routers/color_library.py:120 revoke_use_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L120) | 1 |
| [backend/routers/color_library.py:125 nearest_color](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L125) | 1 |
| [backend/routers/color_library.py:134 list_supplier_color_variants](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L134) | 1 |
| [backend/routers/color_library.py:141 color_links](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L141) | 1 |
| [backend/routers/color_library.py:151 create_color](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L151) | 1 |
| [backend/routers/color_library.py:163 patch_color](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L163) | 1 |
| [backend/routers/color_library.py:184 delete_color](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/color_library.py#L184) | 1 |
| [backend/routers/config.py:33 _allowed](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L33) | 2 |
| [backend/routers/config.py:39 _may](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L39) | 2 |
| [backend/routers/config.py:44 _may_edit](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L44) | 6 |
| [backend/routers/config.py:75 _can_edit](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L75) | 3 |
| [backend/routers/config.py:88 read_registry](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L88) | 11 |
| [backend/routers/config.py:107 read_effective](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L107) | 9 |
| [backend/routers/config.py:123 explain](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L123) | 4 |
| [backend/routers/config.py:140 simulate](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L140) | 6 |
| [backend/routers/config.py:175 write_values](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L175) | 4 |
| [backend/routers/config.py:208 reset_value](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L208) | 5 |
| [backend/routers/config.py:230 clear_value_layer](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L230) | 5 |
| [backend/routers/config.py:258 read_history](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L258) | 3 |
| [backend/routers/config.py:267 read_health](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L267) | 1 |
| [backend/routers/config.py:276 impact_preview](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L276) | 1 |
| [backend/routers/config.py:288 impact_apply](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L288) | 1 |
| [backend/routers/config.py:302 list_simulators](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/config.py#L302) | 2 |
| [backend/routers/consolidation.py:42 consolidation_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/consolidation.py#L42) | 1 |
| [backend/routers/consolidation.py:56 list_eliminations](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/consolidation.py#L56) | 1 |
| [backend/routers/consolidation.py:62 create_elimination](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/consolidation.py#L62) | 1 |
| [backend/routers/consolidation.py:74 delete_elimination](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/consolidation.py#L74) | 1 |
| [backend/routers/consolidation.py:89 ic_candidates](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/consolidation.py#L89) | 1 |
| [backend/routers/consolidation.py:98 sync_ic_eliminations_from_pairs](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/consolidation.py#L98) | 1 |
| [backend/routers/consolidation.py:117 sync_g6_ic_eliminations](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/consolidation.py#L117) | 1 |
| [backend/routers/contra_bons.py:38 contra_bon_meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L38) | 1 |
| [backend/routers/contra_bons.py:53 contra_bon_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L53) | 1 |
| [backend/routers/contra_bons.py:59 contra_bon_status_counts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L59) | 1 |
| [backend/routers/contra_bons.py:65 contra_bon_prepare](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L65) | 1 |
| [backend/routers/contra_bons.py:78 contra_bon_unbilled](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L78) | 1 |
| [backend/routers/contra_bons.py:87 contra_bon_schedules](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L87) | 1 |
| [backend/routers/contra_bons.py:94 set_invoice_exchange](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L94) | 1 |
| [backend/routers/contra_bons.py:108 contra_bon_bank_candidates](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L108) | 1 |
| [backend/routers/contra_bons.py:119 contra_bon_run_reminder](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L119) | 1 |
| [backend/routers/contra_bons.py:130 list_contra_bons](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L130) | 1 |
| [backend/routers/contra_bons.py:138 get_contra_bon](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L138) | 1 |
| [backend/routers/contra_bons.py:148 contra_bon_receipt](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L148) | 1 |
| [backend/routers/contra_bons.py:172 create_contra_bon](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L172) | 1 |
| [backend/routers/contra_bons.py:186 add_deduction](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L186) | 1 |
| [backend/routers/contra_bons.py:199 remove_deduction](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L199) | 1 |
| [backend/routers/contra_bons.py:211 decide_exception](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L211) | 1 |
| [backend/routers/contra_bons.py:226 submit_contra_bon](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L226) | 1 |
| [backend/routers/contra_bons.py:238 verify_contra_bon](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L238) | 1 |
| [backend/routers/contra_bons.py:250 approve_contra_bon](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L250) | 1 |
| [backend/routers/contra_bons.py:263 schedule_contra_bon](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L263) | 1 |
| [backend/routers/contra_bons.py:276 pay_contra_bon](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L276) | 1 |
| [backend/routers/contra_bons.py:290 pay_from_bank_line](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L290) | 1 |
| [backend/routers/contra_bons.py:307 dispute_contra_bon](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L307) | 1 |
| [backend/routers/contra_bons.py:320 cancel_contra_bon](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/contra_bons.py#L320) | 1 |
| [backend/routers/costing.py:17 list_wac](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/costing.py#L17) | 1 |
| [backend/routers/costing.py:24 get_wac](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/costing.py#L24) | 1 |
| [backend/routers/crm.py:30 list_sales_users](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L30) | 15 |
| [backend/routers/crm.py:58 get_customer_360](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L58) | 1 |
| [backend/routers/crm.py:70 reassign_customer](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L70) | 1 |
| [backend/routers/crm.py:91 request_credit_override](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L91) | 1 |
| [backend/routers/crm.py:120 list_credit_overrides](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L120) | 1 |
| [backend/routers/crm.py:131 decide_credit_override](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L131) | 1 |
| [backend/routers/crm.py:151 get_collection_worklist](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L151) | 1 |
| [backend/routers/crm.py:157 get_credit_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L157) | 1 |
| [backend/routers/crm.py:177 get_collection_reminders](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L177) | 1 |
| [backend/routers/crm.py:183 mark_reminder](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L183) | 1 |
| [backend/routers/crm.py:204 add_followup](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L204) | 1 |
| [backend/routers/crm.py:230 _kpi_scope](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L230) | 1 |
| [backend/routers/crm.py:251 get_sales_kpi](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L251) | 1 |
| [backend/routers/crm.py:257 get_leaderboard](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L257) | 1 |
| [backend/routers/crm.py:263 get_commission](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L263) | 1 |
| [backend/routers/crm.py:269 get_commission_history](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L269) | 1 |
| [backend/routers/crm.py:278 get_incentive_gl_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L278) | 1 |
| [backend/routers/crm.py:290 post_incentive_gl](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L290) | 1 |
| [backend/routers/crm.py:319 list_targets](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L319) | 8 |
| [backend/routers/crm.py:337 create_target](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L337) | 1 |
| [backend/routers/crm.py:375 list_incentives](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L375) | 8 |
| [backend/routers/crm.py:392 create_incentive](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm.py#L392) | 1 |
| [backend/routers/crm_omnichannel.py:93 list_leads](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm_omnichannel.py#L93) | 1 |
| [backend/routers/crm_omnichannel.py:102 leads_board](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm_omnichannel.py#L102) | 1 |
| [backend/routers/crm_omnichannel.py:109 pipeline_stats](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm_omnichannel.py#L109) | 1 |
| [backend/routers/crm_omnichannel.py:116 create_lead](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm_omnichannel.py#L116) | 1 |
| [backend/routers/crm_omnichannel.py:136 update_lead](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm_omnichannel.py#L136) | 1 |
| [backend/routers/crm_omnichannel.py:150 convert_lead](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm_omnichannel.py#L150) | 1 |
| [backend/routers/crm_omnichannel.py:161 delete_lead](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm_omnichannel.py#L161) | 1 |
| [backend/routers/crm_omnichannel.py:174 list_interactions](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm_omnichannel.py#L174) | 1 |
| [backend/routers/crm_omnichannel.py:183 create_interaction](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm_omnichannel.py#L183) | 1 |
| [backend/routers/crm_omnichannel.py:195 delete_interaction](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/crm_omnichannel.py#L195) | 1 |
| [backend/routers/customer_feedback.py:37 feedback_meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customer_feedback.py#L37) | 1 |
| [backend/routers/customer_feedback.py:47 feedback_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customer_feedback.py#L47) | 1 |
| [backend/routers/customer_feedback.py:54 list_feedback](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customer_feedback.py#L54) | 1 |
| [backend/routers/customer_feedback.py:66 create_feedback](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customer_feedback.py#L66) | 1 |
| [backend/routers/customer_feedback.py:82 update_feedback](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customer_feedback.py#L82) | 1 |
| [backend/routers/customer_prices.py:45 customer_price_grid](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customer_prices.py#L45) | 1 |
| [backend/routers/customer_prices.py:59 customer_price_records](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customer_prices.py#L59) | 1 |
| [backend/routers/customer_prices.py:71 customer_price_quote](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customer_prices.py#L71) | 1 |
| [backend/routers/customer_prices.py:102 customer_price_floor](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customer_prices.py#L102) | 1 |
| [backend/routers/customer_prices.py:124 customer_price_export](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customer_prices.py#L124) | 1 |
| [backend/routers/customer_prices.py:139 create_customer_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customer_prices.py#L139) | 1 |
| [backend/routers/customer_prices.py:159 import_customer_prices](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customer_prices.py#L159) | 1 |
| [backend/routers/customer_prices.py:186 patch_customer_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customer_prices.py#L186) | 1 |
| [backend/routers/customer_prices.py:204 delete_customer_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customer_prices.py#L204) | 1 |
| [backend/routers/customers.py:23 list_customers](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customers.py#L23) | 1 |
| [backend/routers/customers.py:70 create_customer](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customers.py#L70) | 1 |
| [backend/routers/customers.py:160 update_customer](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customers.py#L160) | 1 |
| [backend/routers/customers.py:221 add_customer_address](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/customers.py#L221) | 1 |
| [backend/routers/cycle_count.py:49 create_session](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L49) | 1 |
| [backend/routers/cycle_count.py:76 list_sessions](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L76) | 1 |
| [backend/routers/cycle_count.py:86 get_session](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L86) | 1 |
| [backend/routers/cycle_count.py:96 add_item](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L96) | 1 |
| [backend/routers/cycle_count.py:133 update_item](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L133) | 1 |
| [backend/routers/cycle_count.py:156 submit_session](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L156) | 1 |
| [backend/routers/cycle_count.py:197 approve_session](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L197) | 1 |
| [backend/routers/cycle_count.py:253 reject_session](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/cycle_count.py#L253) | 1 |
| [backend/routers/dashboard.py:15 dashboard](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/dashboard.py#L15) | 49 |
| [backend/routers/data_hygiene.py:14 hygiene_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/data_hygiene.py#L14) | 1 |
| [backend/routers/data_hygiene.py:20 hygiene_log](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/data_hygiene.py#L20) | 1 |
| [backend/routers/data_hygiene.py:39 hygiene_preview](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/data_hygiene.py#L39) | 1 |
| [backend/routers/data_hygiene.py:45 hygiene_run](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/data_hygiene.py#L45) | 1 |
| [backend/routers/data_hygiene.py:53 hygiene_revert](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/data_hygiene.py#L53) | 1 |
| [backend/routers/data_hygiene.py:61 hygiene_unlock](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/data_hygiene.py#L61) | 1 |
| [backend/routers/data_hygiene.py:69 turn_map](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/data_hygiene.py#L69) | 1 |
| [backend/routers/data_hygiene.py:75 unverified_locations](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/data_hygiene.py#L75) | 1 |
| [backend/routers/data_hygiene.py:81 fix_location](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/data_hygiene.py#L81) | 1 |
| [backend/routers/deliveries.py:44 send_whatsapp](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/deliveries.py#L44) | 1 |
| [backend/routers/deliveries.py:59 get_wa_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/deliveries.py#L59) | 1 |
| [backend/routers/deliveries.py:65 put_wa_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/deliveries.py#L65) | 1 |
| [backend/routers/deliveries.py:72 wa_recipient](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/deliveries.py#L72) | 1 |
| [backend/routers/deliveries.py:80 list_wa_rules](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/deliveries.py#L80) | 1 |
| [backend/routers/deliveries.py:86 create_wa_rule](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/deliveries.py#L86) | 1 |
| [backend/routers/deliveries.py:96 update_wa_rule](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/deliveries.py#L96) | 1 |
| [backend/routers/deliveries.py:108 delete_wa_rule](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/deliveries.py#L108) | 1 |
| [backend/routers/deliveries.py:117 list_deliveries](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/deliveries.py#L117) | 1 |
| [backend/routers/design_gallery.py:26 _perm_view](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L26) | 4 |
| [backend/routers/design_gallery.py:39 _perm_manage](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L39) | 8 |
| [backend/routers/design_gallery.py:68 list_gallery](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L68) | 1 |
| [backend/routers/design_gallery.py:90 create_gallery](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L90) | 1 |
| [backend/routers/design_gallery.py:104 get_gallery](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L104) | 1 |
| [backend/routers/design_gallery.py:112 update_gallery](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L112) | 1 |
| [backend/routers/design_gallery.py:126 delete_gallery](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L126) | 1 |
| [backend/routers/design_gallery.py:140 upload_gallery_file](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L140) | 1 |
| [backend/routers/design_gallery.py:157 get_gallery_file](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L157) | 1 |
| [backend/routers/design_gallery.py:175 delete_gallery_file](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L175) | 1 |
| [backend/routers/design_gallery.py:190 autotag_gallery](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L190) | 1 |
| [backend/routers/design_gallery.py:206 ai_illustrate_gallery](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L206) | 1 |
| [backend/routers/design_gallery.py:224 comment_illustration](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L224) | 1 |
| [backend/routers/design_gallery.py:240 delete_illustration_comment](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L240) | 1 |
| [backend/routers/design_gallery.py:256 ai_illustrate_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L256) | 1 |
| [backend/routers/design_gallery.py:268 bump_design_version](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L268) | 1 |
| [backend/routers/design_gallery.py:285 submit_design](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L285) | 1 |
| [backend/routers/design_gallery.py:300 reject_design](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L300) | 1 |
| [backend/routers/design_gallery.py:316 approve_design](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L316) | 1 |
| [backend/routers/design_gallery.py:334 rate_design](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L334) | 1 |
| [backend/routers/design_gallery.py:352 unrate_design](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_gallery.py#L352) | 1 |
| [backend/routers/design_requests.py:67 meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L67) | 1 |
| [backend/routers/design_requests.py:90 list_requests](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L90) | 1 |
| [backend/routers/design_requests.py:127 create_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L127) | 1 |
| [backend/routers/design_requests.py:141 get_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L141) | 1 |
| [backend/routers/design_requests.py:148 create_design_from_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L148) | 1 |
| [backend/routers/design_requests.py:169 upload_reference](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L169) | 1 |
| [backend/routers/design_requests.py:186 get_reference](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L186) | 1 |
| [backend/routers/design_requests.py:199 delete_reference](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L199) | 1 |
| [backend/routers/design_requests.py:212 link_design_to_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L212) | 1 |
| [backend/routers/design_requests.py:226 update_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L226) | 1 |
| [backend/routers/design_requests.py:240 submit_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L240) | 1 |
| [backend/routers/design_requests.py:253 assign_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L253) | 1 |
| [backend/routers/design_requests.py:268 start_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L268) | 1 |
| [backend/routers/design_requests.py:282 deliver_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L282) | 1 |
| [backend/routers/design_requests.py:296 approve_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L296) | 1 |
| [backend/routers/design_requests.py:311 reject_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L311) | 1 |
| [backend/routers/design_requests.py:327 cancel_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L327) | 1 |
| [backend/routers/design_requests.py:342 report_by_designer](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L342) | 1 |
| [backend/routers/design_requests.py:359 report_mine](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L359) | 1 |
| [backend/routers/design_requests.py:390 requests_for_so](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_requests.py#L390) | 1 |
| [backend/routers/design_studio.py:28 _perm_assess](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L28) | 1 |
| [backend/routers/design_studio.py:32 _perm_view](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L32) | 1 |
| [backend/routers/design_studio.py:48 studio_meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L48) | 1 |
| [backend/routers/design_studio.py:66 studio_next_code](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L66) | 1 |
| [backend/routers/design_studio.py:76 studio_tags](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L76) | 1 |
| [backend/routers/design_studio.py:82 list_categories](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L82) | 1 |
| [backend/routers/design_studio.py:89 create_category](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L89) | 1 |
| [backend/routers/design_studio.py:100 patch_category](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L100) | 1 |
| [backend/routers/design_studio.py:112 _do_transition](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L112) | 1 |
| [backend/routers/design_studio.py:131 lc_submit](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L131) | 1 |
| [backend/routers/design_studio.py:136 lc_start_review](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L136) | 1 |
| [backend/routers/design_studio.py:141 lc_request_revision](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L141) | 1 |
| [backend/routers/design_studio.py:146 lc_approve](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L146) | 1 |
| [backend/routers/design_studio.py:151 lc_activate](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L151) | 1 |
| [backend/routers/design_studio.py:156 lc_submit_final](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L156) | 1 |
| [backend/routers/design_studio.py:162 lc_return_final](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L162) | 1 |
| [backend/routers/design_studio.py:168 lc_archive](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L168) | 1 |
| [backend/routers/design_studio.py:173 lc_reopen](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L173) | 1 |
| [backend/routers/design_studio.py:178 new_version](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L178) | 1 |
| [backend/routers/design_studio.py:193 lc_hold](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L193) | 1 |
| [backend/routers/design_studio.py:208 lc_release_hold](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L208) | 1 |
| [backend/routers/design_studio.py:222 design_history](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L222) | 1 |
| [backend/routers/design_studio.py:234 add_feedback](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L234) | 1 |
| [backend/routers/design_studio.py:249 add_colorway](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L249) | 1 |
| [backend/routers/design_studio.py:263 update_colorway](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L263) | 1 |
| [backend/routers/design_studio.py:276 delete_colorway](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L276) | 1 |
| [backend/routers/design_studio.py:290 upload_kind_file](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/design_studio.py#L290) | 1 |
| [backend/routers/documents.py:89 document_trace](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L89) | 1 |
| [backend/routers/documents.py:106 document_trace_print](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L106) | 3 |
| [backend/routers/documents.py:127 document_refs](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L127) | 1 |
| [backend/routers/documents.py:138 document_trace_search](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L138) | 1 |
| [backend/routers/documents.py:153 document_ref_types](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L153) | 1 |
| [backend/routers/documents.py:163 document_refs_backfill](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L163) | 1 |
| [backend/routers/documents.py:177 document_relations](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L177) | 2 |
| [backend/routers/documents.py:195 list_templates](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L195) | 1 |
| [backend/routers/documents.py:212 create_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L212) | 1 |
| [backend/routers/documents.py:222 update_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L222) | 1 |
| [backend/routers/documents.py:240 delete_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L240) | 1 |
| [backend/routers/documents.py:254 generate_document](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L254) | 1 |
| [backend/routers/documents.py:273 print_generated_document](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L273) | 1 |
| [backend/routers/documents.py:284 preview_document](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L284) | 1 |
| [backend/routers/documents.py:293 generate_barcode](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L293) | 1 |
| [backend/routers/documents.py:350 resolve_document_number](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L350) | 25 |
| [backend/routers/documents.py:366 _may_view](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/documents.py#L366) | 5 |
| [backend/routers/entities.py:35 list_entities](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entities.py#L35) | 17 |
| [backend/routers/entities.py:79 count_entities](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entities.py#L79) | 6 |
| [backend/routers/entities.py:90 get_entity](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entities.py#L90) | 7 |
| [backend/routers/entities.py:101 get_readiness](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entities.py#L101) | 3 |
| [backend/routers/entities.py:109 get_deactivation_impact](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entities.py#L109) | 1 |
| [backend/routers/entities.py:116 get_entity_audit](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entities.py#L116) | 1 |
| [backend/routers/entities.py:140 create_entity](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entities.py#L140) | 1 |
| [backend/routers/entities.py:154 update_entity](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entities.py#L154) | 1 |
| [backend/routers/entities.py:188 archive_entity](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entities.py#L188) | 1 |
| [backend/routers/entities.py:210 archive_entity_post](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entities.py#L210) | 1 |
| [backend/routers/entities.py:226 reactivate_entity](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entities.py#L226) | 1 |
| [backend/routers/entity_masters.py:25 list_master_groups](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entity_masters.py#L25) | 1 |
| [backend/routers/entity_masters.py:33 list_master_rows](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entity_masters.py#L33) | 1 |
| [backend/routers/entity_masters.py:43 list_master_effective](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entity_masters.py#L43) | 1 |
| [backend/routers/entity_masters.py:53 create_master_row](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entity_masters.py#L53) | 1 |
| [backend/routers/entity_masters.py:67 update_master_row](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entity_masters.py#L67) | 1 |
| [backend/routers/entity_masters.py:79 override_master_row](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entity_masters.py#L79) | 1 |
| [backend/routers/entity_masters.py:91 revert_master_row](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/entity_masters.py#L91) | 1 |
| [backend/routers/enums.py:25 _overlay_live_masters](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/enums.py#L25) | 10 |
| [backend/routers/enums.py:73 list_enums](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/enums.py#L73) | 5 |
| [backend/routers/enums.py:83 stage_transitions](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/enums.py#L83) | 6 |
| [backend/routers/enums.py:94 validate_stage_transition](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/enums.py#L94) | 6 |
| [backend/routers/enums.py:105 validate_product_domain](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/enums.py#L105) | 2 |
| [backend/routers/enums.py:112 get_enum](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/enums.py#L112) | 5 |
| [backend/routers/esign.py:32 request_otp](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/esign.py#L32) | 1 |
| [backend/routers/esign.py:46 verify](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/esign.py#L46) | 1 |
| [backend/routers/esign.py:61 signatures](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/esign.py#L61) | 2 |
| [backend/routers/esign.py:67 public_verify](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/esign.py#L67) | 1 |
| [backend/routers/finance_analytics.py:31 get_profitability](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_analytics.py#L31) | 1 |
| [backend/routers/finance_analytics.py:47 get_cashflow_forecast](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_analytics.py#L47) | 1 |
| [backend/routers/finance_analytics.py:59 get_finance_tower](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_analytics.py#L59) | 1 |
| [backend/routers/finance_bi.py:19 finance_bi_dashboard](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_bi.py#L19) | 1 |
| [backend/routers/finance_cases.py:44 list_playbooks](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_cases.py#L44) | 1 |
| [backend/routers/finance_cases.py:51 list_reasons](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_cases.py#L51) | 1 |
| [backend/routers/finance_cases.py:57 get_policy](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_cases.py#L57) | 1 |
| [backend/routers/finance_cases.py:65 get_stats](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_cases.py#L65) | 1 |
| [backend/routers/finance_cases.py:73 list_cases](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_cases.py#L73) | 1 |
| [backend/routers/finance_cases.py:87 get_case](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_cases.py#L87) | 1 |
| [backend/routers/finance_cases.py:97 create_case](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_cases.py#L97) | 1 |
| [backend/routers/finance_cases.py:113 assign_case](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_cases.py#L113) | 1 |
| [backend/routers/finance_cases.py:126 add_note](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_cases.py#L126) | 1 |
| [backend/routers/finance_cases.py:139 resolve_case](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_cases.py#L139) | 1 |
| [backend/routers/finance_cases.py:157 reject_case](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_cases.py#L157) | 1 |
| [backend/routers/finance_cases.py:170 reopen_case](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_cases.py#L170) | 1 |
| [backend/routers/finance_cases.py:183 run_scan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/finance_cases.py#L183) | 1 |
| [backend/routers/financial_statements.py:39 get_income_statement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/financial_statements.py#L39) | 1 |
| [backend/routers/financial_statements.py:52 get_balance_sheet](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/financial_statements.py#L52) | 1 |
| [backend/routers/financial_statements.py:68 get_cash_flow](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/financial_statements.py#L68) | 1 |
| [backend/routers/financial_statements.py:81 get_equity_changes](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/financial_statements.py#L81) | 1 |
| [backend/routers/financial_statements.py:109 export_income_statement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/financial_statements.py#L109) | 1 |
| [backend/routers/financial_statements.py:138 export_balance_sheet](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/financial_statements.py#L138) | 1 |
| [backend/routers/financial_statements.py:207 export_cash_flow](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/financial_statements.py#L207) | 1 |
| [backend/routers/financial_statements.py:243 export_equity_changes](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/financial_statements.py#L243) | 1 |
| [backend/routers/fixed_assets.py:62 list_fixed_assets](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/fixed_assets.py#L62) | 1 |
| [backend/routers/fixed_assets.py:69 fixed_asset_meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/fixed_assets.py#L69) | 1 |
| [backend/routers/fixed_assets.py:88 fixed_asset_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/fixed_assets.py#L88) | 1 |
| [backend/routers/fixed_assets.py:95 create_fixed_asset](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/fixed_assets.py#L95) | 1 |
| [backend/routers/fixed_assets.py:107 run_depreciation](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/fixed_assets.py#L107) | 1 |
| [backend/routers/fixed_assets.py:123 get_fixed_asset](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/fixed_assets.py#L123) | 1 |
| [backend/routers/fixed_assets.py:131 patch_fixed_asset](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/fixed_assets.py#L131) | 1 |
| [backend/routers/fixed_assets.py:145 dispose_fixed_asset](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/fixed_assets.py#L145) | 1 |
| [backend/routers/fixed_assets.py:160 transfer_fixed_asset](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/fixed_assets.py#L160) | 1 |
| [backend/routers/fixed_assets.py:189 settle_fixed_asset_transfer](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/fixed_assets.py#L189) | 1 |
| [backend/routers/fulfillment.py:28 get_wizard](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/fulfillment.py#L28) | 1 |
| [backend/routers/fulfillment.py:34 post_wizard_interco](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/fulfillment.py#L34) | 1 |
| [backend/routers/fulfillment.py:44 post_wizard_pr](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/fulfillment.py#L44) | 1 |
| [backend/routers/gl.py:31 list_gl_accounts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L31) | 1 |
| [backend/routers/gl.py:44 list_cash_accounts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L44) | 1 |
| [backend/routers/gl.py:59 create_gl_account](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L59) | 1 |
| [backend/routers/gl.py:74 update_gl_account](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L74) | 1 |
| [backend/routers/gl.py:88 delete_gl_account](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L88) | 1 |
| [backend/routers/gl.py:103 gl_account_ledger](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L103) | 1 |
| [backend/routers/gl.py:117 list_journal](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L117) | 1 |
| [backend/routers/gl.py:143 create_journal](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L143) | 1 |
| [backend/routers/gl.py:163 get_journal](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L163) | 1 |
| [backend/routers/gl.py:175 void_journal](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L175) | 1 |
| [backend/routers/gl.py:194 sync_journals](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L194) | 1 |
| [backend/routers/gl.py:203 trial_balance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L203) | 1 |
| [backend/routers/gl.py:212 gl_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L212) | 1 |
| [backend/routers/gl.py:220 gl_consolidation](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L220) | 1 |
| [backend/routers/gl.py:231 gl_inventory_reconciliation](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L231) | 1 |
| [backend/routers/gl.py:238 gl_inventory_drift_explain](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L238) | 1 |
| [backend/routers/gl.py:251 gl_inventory_opening_balance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L251) | 1 |
| [backend/routers/gl.py:276 gl_suspense](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L276) | 1 |
| [backend/routers/gl.py:284 gl_suspense_reclass](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/gl.py#L284) | 1 |
| [backend/routers/goods_receipts.py:23 _act](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L23) | 1 |
| [backend/routers/goods_receipts.py:32 create_grn](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L32) | 1 |
| [backend/routers/goods_receipts.py:38 list_grn](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L38) | 1 |
| [backend/routers/goods_receipts.py:63 grn_partners](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L63) | 1 |
| [backend/routers/goods_receipts.py:69 grn_supplier_variance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L69) | 1 |
| [backend/routers/goods_receipts.py:75 grn_ocr_usage](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L75) | 1 |
| [backend/routers/goods_receipts.py:81 grn_mode_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L81) | 1 |
| [backend/routers/goods_receipts.py:88 grn_mode_switch](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L88) | 1 |
| [backend/routers/goods_receipts.py:96 grn_doc_variance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L96) | 1 |
| [backend/routers/goods_receipts.py:104 grn_save_catalog](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L104) | 1 |
| [backend/routers/goods_receipts.py:110 grn_dn_profiles](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L110) | 1 |
| [backend/routers/goods_receipts.py:116 grn_dn_profile](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L116) | 1 |
| [backend/routers/goods_receipts.py:122 grn_dn_profile_patch](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L122) | 1 |
| [backend/routers/goods_receipts.py:131 grn_rolls](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L131) | 1 |
| [backend/routers/goods_receipts.py:137 get_grn](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L137) | 1 |
| [backend/routers/goods_receipts.py:143 read_grn](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L143) | 1 |
| [backend/routers/goods_receipts.py:149 grn_targets](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L149) | 1 |
| [backend/routers/goods_receipts.py:155 add_file](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L155) | 1 |
| [backend/routers/goods_receipts.py:165 delete_file](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L165) | 1 |
| [backend/routers/goods_receipts.py:171 get_file](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L171) | 1 |
| [backend/routers/goods_receipts.py:179 manual_entry](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L179) | 1 |
| [backend/routers/goods_receipts.py:185 patch_dn](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L185) | 1 |
| [backend/routers/goods_receipts.py:191 add_line](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L191) | 1 |
| [backend/routers/goods_receipts.py:197 patch_line](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L197) | 1 |
| [backend/routers/goods_receipts.py:203 delete_line](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L203) | 1 |
| [backend/routers/goods_receipts.py:209 start_count](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L209) | 1 |
| [backend/routers/goods_receipts.py:215 scan_label](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L215) | 1 |
| [backend/routers/goods_receipts.py:222 add_roll](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L222) | 1 |
| [backend/routers/goods_receipts.py:229 delete_roll](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L229) | 1 |
| [backend/routers/goods_receipts.py:235 finish_count](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L235) | 1 |
| [backend/routers/goods_receipts.py:241 reopen_count](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L241) | 1 |
| [backend/routers/goods_receipts.py:247 resolve](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L247) | 1 |
| [backend/routers/goods_receipts.py:253 close](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L253) | 1 |
| [backend/routers/goods_receipts.py:265 set_mko_partial](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L265) | 1 |
| [backend/routers/goods_receipts.py:271 return_to_reconcile](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L271) | 1 |
| [backend/routers/goods_receipts.py:277 reject](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L277) | 1 |
| [backend/routers/goods_receipts.py:283 cancel](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/goods_receipts.py#L283) | 1 |
| [backend/routers/home.py:13 _allowed](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/home.py#L13) | 3 |
| [backend/routers/home.py:23 _own_entity](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/home.py#L23) | 5 |
| [backend/routers/home.py:47 home_sales](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/home.py#L47) | 4 |
| [backend/routers/home.py:57 home_admin](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/home.py#L57) | 1 |
| [backend/routers/home.py:65 home_manager](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/home.py#L65) | 1 |
| [backend/routers/home.py:73 home_warehouse](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/home.py#L73) | 3 |
| [backend/routers/home.py:88 home_finance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/home.py#L88) | 3 |
| [backend/routers/hr.py:56 list_org_units](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L56) | 1 |
| [backend/routers/hr.py:77 org_units_tree](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L77) | 1 |
| [backend/routers/hr.py:97 create_org_unit](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L97) | 1 |
| [backend/routers/hr.py:129 update_org_unit](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L129) | 1 |
| [backend/routers/hr.py:149 deactivate_org_unit](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L149) | 1 |
| [backend/routers/hr.py:175 list_employees](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L175) | 1 |
| [backend/routers/hr.py:205 hr_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L205) | 1 |
| [backend/routers/hr.py:235 my_employee](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L235) | 4 |
| [backend/routers/hr.py:247 create_employee](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L247) | 1 |
| [backend/routers/hr.py:312 get_employee](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L312) | 1 |
| [backend/routers/hr.py:329 get_employee_360](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L329) | 1 |
| [backend/routers/hr.py:397 update_employee](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L397) | 1 |
| [backend/routers/hr.py:430 deactivate_employee](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L430) | 1 |
| [backend/routers/hr.py:448 read_hr_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L448) | 1 |
| [backend/routers/hr.py:461 update_hr_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr.py#L461) | 1 |
| [backend/routers/hr_analytics.py:16 hr_analytics_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_analytics.py#L16) | 1 |
| [backend/routers/hr_attendance.py:38 _emp_for_user](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L38) | 4 |
| [backend/routers/hr_attendance.py:62 list_shifts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L62) | 1 |
| [backend/routers/hr_attendance.py:70 create_shift](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L70) | 1 |
| [backend/routers/hr_attendance.py:90 update_shift](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L90) | 1 |
| [backend/routers/hr_attendance.py:108 deactivate_shift](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L108) | 1 |
| [backend/routers/hr_attendance.py:124 list_geofences](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L124) | 1 |
| [backend/routers/hr_attendance.py:132 create_geofence](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L132) | 1 |
| [backend/routers/hr_attendance.py:150 update_geofence](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L150) | 1 |
| [backend/routers/hr_attendance.py:173 deactivate_geofence](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L173) | 1 |
| [backend/routers/hr_attendance.py:189 list_devices](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L189) | 1 |
| [backend/routers/hr_attendance.py:198 create_device](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L198) | 1 |
| [backend/routers/hr_attendance.py:216 update_device](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L216) | 1 |
| [backend/routers/hr_attendance.py:234 deactivate_device](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L234) | 1 |
| [backend/routers/hr_attendance.py:250 list_attendance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L250) | 1 |
| [backend/routers/hr_attendance.py:281 attendance_recap](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L281) | 1 |
| [backend/routers/hr_attendance.py:311 my_attendance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L311) | 1 |
| [backend/routers/hr_attendance.py:329 clock_in](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L329) | 1 |
| [backend/routers/hr_attendance.py:371 clock_out](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L371) | 1 |
| [backend/routers/hr_attendance.py:411 manual_attendance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L411) | 1 |
| [backend/routers/hr_attendance.py:431 patch_attendance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L431) | 1 |
| [backend/routers/hr_attendance.py:485 import_attendance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L485) | 1 |
| [backend/routers/hr_attendance.py:504 ingest_attendance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_attendance.py#L504) | 5 |
| [backend/routers/hr_kpi.py:21 _emp_for_user](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_kpi.py#L21) | 4 |
| [backend/routers/hr_kpi.py:46 _my_kpi](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_kpi.py#L46) | 1 |
| [backend/routers/hr_kpi.py:52 my_kpi_endpoint](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_kpi.py#L52) | 1 |
| [backend/routers/hr_kpi.py:58 list_kpi](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_kpi.py#L58) | 1 |
| [backend/routers/hr_kpi.py:68 create_kpi](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_kpi.py#L68) | 1 |
| [backend/routers/hr_kpi.py:84 update_kpi](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_kpi.py#L84) | 1 |
| [backend/routers/hr_kpi.py:98 delete_kpi](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_kpi.py#L98) | 1 |
| [backend/routers/hr_leave.py:26 _emp_for_user](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L26) | 4 |
| [backend/routers/hr_leave.py:44 my_leave_requests](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L44) | 1 |
| [backend/routers/hr_leave.py:50 submit_my_leave](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L50) | 1 |
| [backend/routers/hr_leave.py:62 my_leave_balance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L62) | 1 |
| [backend/routers/hr_leave.py:69 list_leave_requests](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L69) | 1 |
| [backend/routers/hr_leave.py:80 create_leave_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L80) | 1 |
| [backend/routers/hr_leave.py:96 list_leave_balances](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L96) | 1 |
| [backend/routers/hr_leave.py:105 set_leave_entitlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L105) | 1 |
| [backend/routers/hr_leave.py:117 leave_calendar](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L117) | 1 |
| [backend/routers/hr_leave.py:127 _get_leave_guard](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L127) | 3 |
| [backend/routers/hr_leave.py:136 approve_leave_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L136) | 1 |
| [backend/routers/hr_leave.py:149 reject_leave_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L149) | 1 |
| [backend/routers/hr_leave.py:162 cancel_leave_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L162) | 3 |
| [backend/routers/hr_leave.py:181 my_overtime_requests](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L181) | 1 |
| [backend/routers/hr_leave.py:187 submit_my_overtime](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L187) | 1 |
| [backend/routers/hr_leave.py:200 list_overtime_requests](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L200) | 1 |
| [backend/routers/hr_leave.py:211 create_overtime](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L211) | 1 |
| [backend/routers/hr_leave.py:235 approve_overtime_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L235) | 1 |
| [backend/routers/hr_leave.py:248 reject_overtime_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_leave.py#L248) | 1 |
| [backend/routers/hr_payroll.py:31 get_payroll_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L31) | 1 |
| [backend/routers/hr_payroll.py:40 update_payroll_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L40) | 14 |
| [backend/routers/hr_payroll.py:64 list_payroll_runs](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L64) | 1 |
| [backend/routers/hr_payroll.py:73 preview_payroll_run](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L73) | 1 |
| [backend/routers/hr_payroll.py:82 create_payroll_run](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L82) | 1 |
| [backend/routers/hr_payroll.py:96 get_payroll_run](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L96) | 1 |
| [backend/routers/hr_payroll.py:107 submit_payroll_run](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L107) | 1 |
| [backend/routers/hr_payroll.py:122 reject_payroll_run](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L122) | 1 |
| [backend/routers/hr_payroll.py:137 approve_payroll_run](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L137) | 1 |
| [backend/routers/hr_payroll.py:150 post_payroll_run_gl](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L150) | 1 |
| [backend/routers/hr_payroll.py:164 pay_payroll_run](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L164) | 1 |
| [backend/routers/hr_payroll.py:179 list_payslips](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L179) | 1 |
| [backend/routers/hr_payroll.py:189 my_payslips](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L189) | 2 |
| [backend/routers/hr_payroll.py:195 get_payslip](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L195) | 4 |
| [backend/routers/hr_payroll.py:206 payslip_pdf](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_payroll.py#L206) | 4 |
| [backend/routers/hr_tracking.py:32 _emp_for_user](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_tracking.py#L32) | 4 |
| [backend/routers/hr_tracking.py:58 latest_tracks](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_tracking.py#L58) | 1 |
| [backend/routers/hr_tracking.py:67 track_history](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_tracking.py#L67) | 1 |
| [backend/routers/hr_tracking.py:85 push_track](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_tracking.py#L85) | 1 |
| [backend/routers/hr_tracking.py:95 list_visits](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_tracking.py#L95) | 1 |
| [backend/routers/hr_tracking.py:125 visits_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_tracking.py#L125) | 1 |
| [backend/routers/hr_tracking.py:150 my_visits](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_tracking.py#L150) | 1 |
| [backend/routers/hr_tracking.py:163 my_visits_history](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_tracking.py#L163) | 1 |
| [backend/routers/hr_tracking.py:197 visit_check_in](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_tracking.py#L197) | 1 |
| [backend/routers/hr_tracking.py:226 visit_check_out](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/hr_tracking.py#L226) | 1 |
| [backend/routers/inbound_receiving.py:19 list_inbound_tasks](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_receiving.py#L19) | 1 |
| [backend/routers/inbound_receiving.py:44 scan_receive_item](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_receiving.py#L44) | 1 |
| [backend/routers/inbound_receiving.py:165 escalate_inbound_task](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_receiving.py#L165) | 1 |
| [backend/routers/inbound_receiving.py:227 resolve_escalation](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_receiving.py#L227) | 1 |
| [backend/routers/inbound_receiving.py:299 complete_inbound_receiving](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_receiving.py#L299) | 1 |
| [backend/routers/inbound_receiving_extra.py:20 _load_task_for_uom](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_receiving_extra.py#L20) | 1 |
| [backend/routers/inbound_receiving_extra.py:40 inbound_uom_options](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_receiving_extra.py#L40) | 2 |
| [backend/routers/inbound_receiving_extra.py:54 inbound_preview_uom](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_receiving_extra.py#L54) | 2 |
| [backend/routers/inbound_receiving_extra.py:67 get_receiving_uom_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_receiving_extra.py#L67) | 2 |
| [backend/routers/inbound_receiving_extra.py:76 update_receiving_uom_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_receiving_extra.py#L76) | 2 |
| [backend/routers/inbound_receiving_extra.py:90 qc_inspection_queue](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_receiving_extra.py#L90) | 1 |
| [backend/routers/inbound_receiving_extra.py:121 qc_decision](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_receiving_extra.py#L121) | 1 |
| [backend/routers/inbound_receiving_extra.py:149 generate_receiving_goods_document](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_receiving_extra.py#L149) | 2 |
| [backend/routers/inbound_scan_label.py:30 _load_task](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_scan_label.py#L30) | 1 |
| [backend/routers/inbound_scan_label.py:62 get_label_pattern](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_scan_label.py#L62) | 1 |
| [backend/routers/inbound_scan_label.py:74 put_label_pattern](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_scan_label.py#L74) | 1 |
| [backend/routers/inbound_scan_label.py:86 test_label_pattern](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_scan_label.py#L86) | 1 |
| [backend/routers/inbound_scan_label.py:100 list_scanned_rolls](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_scan_label.py#L100) | 1 |
| [backend/routers/inbound_scan_label.py:133 scan_label](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_scan_label.py#L133) | 1 |
| [backend/routers/inbound_scan_label.py:151 confirm_measure](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_scan_label.py#L151) | 1 |
| [backend/routers/inbound_scan_label.py:233 putaway_scanned_roll](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_scan_label.py#L233) | 1 |
| [backend/routers/inbound_scan_label.py:268 tag_scanned_roll](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_scan_label.py#L268) | 1 |
| [backend/routers/inbound_scan_label.py:285 undo_scan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_scan_label.py#L285) | 1 |
| [backend/routers/inbound_scan_label.py:302 scan_label_stats](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inbound_scan_label.py#L302) | 1 |
| [backend/routers/incentive_rates.py:44 list_rates](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/incentive_rates.py#L44) | 1 |
| [backend/routers/incentive_rates.py:56 create_rate](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/incentive_rates.py#L56) | 1 |
| [backend/routers/incentive_rates.py:78 update_rate](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/incentive_rates.py#L78) | 1 |
| [backend/routers/incentive_rates.py:93 delete_rate](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/incentive_rates.py#L93) | 1 |
| [backend/routers/input_tax.py:33 list_eligible_bills](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/input_tax.py#L33) | 1 |
| [backend/routers/input_tax.py:42 get_vat_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/input_tax.py#L42) | 1 |
| [backend/routers/input_tax.py:53 list_input_tax](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/input_tax.py#L53) | 1 |
| [backend/routers/input_tax.py:73 get_input_tax](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/input_tax.py#L73) | 1 |
| [backend/routers/input_tax.py:87 create_input_tax](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/input_tax.py#L87) | 1 |
| [backend/routers/input_tax.py:165 cancel_input_tax](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/input_tax.py#L165) | 1 |
| [backend/routers/inspections.py:52 meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inspections.py#L52) | 1 |
| [backend/routers/inspections.py:69 list_inspections](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inspections.py#L69) | 1 |
| [backend/routers/inspections.py:97 export_inspections](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inspections.py#L97) | 1 |
| [backend/routers/inspections.py:145 get_inspection](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inspections.py#L145) | 1 |
| [backend/routers/inspections.py:151 create_inspection](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inspections.py#L151) | 1 |
| [backend/routers/inspections.py:165 assign_inspection](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inspections.py#L165) | 1 |
| [backend/routers/inspections.py:179 start_inspection](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inspections.py#L179) | 1 |
| [backend/routers/inspections.py:189 inspect_line](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inspections.py#L189) | 1 |
| [backend/routers/inspections.py:207 release_hold](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inspections.py#L207) | 1 |
| [backend/routers/inspections.py:224 finish_inspection](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inspections.py#L224) | 1 |
| [backend/routers/inspections.py:240 reopen_inspection](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inspections.py#L240) | 1 |
| [backend/routers/inspections.py:254 ref_doc_options](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inspections.py#L254) | 1 |
| [backend/routers/inspections.py:347 inspection_pdf](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inspections.py#L347) | 1 |
| [backend/routers/inspections.py:374 qc_tasks_without_doc](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inspections.py#L374) | 1 |
| [backend/routers/integrations.py:18 get_integrations](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/integrations.py#L18) | 1 |
| [backend/routers/integrations.py:25 update_integrations](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/integrations.py#L25) | 1 |
| [backend/routers/integrations.py:43 test_gemini](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/integrations.py#L43) | 1 |
| [backend/routers/integrations.py:66 test_openai](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/integrations.py#L66) | 1 |
| [backend/routers/interco.py:55 interco_meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L55) | 1 |
| [backend/routers/interco.py:61 interco_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L61) | 1 |
| [backend/routers/interco.py:69 list_ict](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L69) | 1 |
| [backend/routers/interco.py:78 create_ict](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L78) | 1 |
| [backend/routers/interco.py:96 get_ict](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L96) | 1 |
| [backend/routers/interco.py:102 confirm_ict](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L102) | 1 |
| [backend/routers/interco.py:116 ship_ict](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L116) | 1 |
| [backend/routers/interco.py:130 receive_ict](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L130) | 1 |
| [backend/routers/interco.py:144 invoice_ict](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L144) | 1 |
| [backend/routers/interco.py:158 cancel_ict](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L158) | 1 |
| [backend/routers/interco.py:173 journal_ict](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L173) | 1 |
| [backend/routers/interco.py:187 warehouse_task_ict](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L187) | 1 |
| [backend/routers/interco.py:210 list_ica](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L210) | 1 |
| [backend/routers/interco.py:217 get_ica](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L217) | 1 |
| [backend/routers/interco.py:231 list_ics](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L231) | 1 |
| [backend/routers/interco.py:239 create_ics](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L239) | 1 |
| [backend/routers/interco.py:258 get_ics](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L258) | 1 |
| [backend/routers/interco.py:268 list_internal_contracts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L268) | 1 |
| [backend/routers/interco.py:286 get_interco_tax](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L286) | 1 |
| [backend/routers/interco.py:296 issue_interco_tax](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L296) | 1 |
| [backend/routers/interco.py:320 replace_interco_tax](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L320) | 1 |
| [backend/routers/interco.py:339 cancel_interco_tax](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L339) | 1 |
| [backend/routers/interco.py:360 interco_return_meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L360) | 1 |
| [backend/routers/interco.py:366 list_interco_returns](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L366) | 1 |
| [backend/routers/interco.py:376 returnable_lines](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L376) | 1 |
| [backend/routers/interco.py:386 create_interco_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L386) | 1 |
| [backend/routers/interco.py:401 get_interco_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L401) | 1 |
| [backend/routers/interco.py:410 approve_interco_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L410) | 1 |
| [backend/routers/interco.py:426 return_warehouse_task](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L426) | 1 |
| [backend/routers/interco.py:442 cancel_interco_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L442) | 1 |
| [backend/routers/interco.py:459 interco_reminders](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L459) | 1 |
| [backend/routers/interco.py:467 remind_settlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L467) | 1 |
| [backend/routers/interco.py:487 margin_report](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L487) | 1 |
| [backend/routers/interco.py:496 margin_by_product](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco.py#L496) | 1 |
| [backend/routers/interco_loans.py:30 loans_meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco_loans.py#L30) | 1 |
| [backend/routers/interco_loans.py:37 list_loans](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco_loans.py#L37) | 1 |
| [backend/routers/interco_loans.py:50 create_loan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco_loans.py#L50) | 1 |
| [backend/routers/interco_loans.py:71 get_loan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco_loans.py#L71) | 1 |
| [backend/routers/interco_loans.py:84 disburse_loan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco_loans.py#L84) | 1 |
| [backend/routers/interco_loans.py:96 repay_loan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco_loans.py#L96) | 1 |
| [backend/routers/interco_loans.py:109 cancel_loan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco_loans.py#L109) | 1 |
| [backend/routers/interco_loans.py:122 non_trade_balance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/interco_loans.py#L122) | 1 |
| [backend/routers/internal_requests.py:52 meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/internal_requests.py#L52) | 1 |
| [backend/routers/internal_requests.py:63 list_requests](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/internal_requests.py#L63) | 1 |
| [backend/routers/internal_requests.py:82 create_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/internal_requests.py#L82) | 1 |
| [backend/routers/internal_requests.py:98 get_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/internal_requests.py#L98) | 1 |
| [backend/routers/internal_requests.py:112 request_sources](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/internal_requests.py#L112) | 1 |
| [backend/routers/internal_requests.py:136 cancel_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/internal_requests.py#L136) | 1 |
| [backend/routers/internal_requests.py:158 reject_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/internal_requests.py#L158) | 1 |
| [backend/routers/internal_requests.py:177 convert_request](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/internal_requests.py#L177) | 1 |
| [backend/routers/internal_requests.py:207 product_availability](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/internal_requests.py#L207) | 1 |
| [backend/routers/inventory.py:30 roll_journey_timeline](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inventory.py#L30) | 1 |
| [backend/routers/inventory.py:39 roll_cost_history_endpoint](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inventory.py#L39) | 1 |
| [backend/routers/inventory.py:71 get_putaway_queue](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inventory.py#L71) | 1 |
| [backend/routers/inventory.py:80 do_putaway](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inventory.py#L80) | 1 |
| [backend/routers/inventory.py:91 stock_analytics](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inventory.py#L91) | 1 |
| [backend/routers/inventory.py:105 inventory_status_board](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inventory.py#L105) | 1 |
| [backend/routers/inventory.py:130 list_balances](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inventory.py#L130) | 1 |
| [backend/routers/inventory.py:166 list_rolls](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inventory.py#L166) | 1 |
| [backend/routers/inventory.py:236 list_rolls_available](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inventory.py#L236) | 1 |
| [backend/routers/inventory.py:264 list_movements](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inventory.py#L264) | 1 |
| [backend/routers/inventory.py:312 rolls_without_cost](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inventory.py#L312) | 1 |
| [backend/routers/inventory.py:333 set_opening_cost](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inventory.py#L333) | 1 |
| [backend/routers/inventory.py:355 add_initial_stock](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inventory.py#L355) | 1 |
| [backend/routers/inventory.py:433 product_history](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/inventory.py#L433) | 1 |
| [backend/routers/invoices.py:19 list_invoices](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/invoices.py#L19) | 1 |
| [backend/routers/invoices.py:27 order_invoices](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/invoices.py#L27) | 1 |
| [backend/routers/invoices.py:38 simulate_payment](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/invoices.py#L38) | 1 |
| [backend/routers/label_printer.py:22 generate_product_label](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/label_printer.py#L22) | 1 |
| [backend/routers/label_printer.py:83 preview_label](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/label_printer.py#L83) | 1 |
| [backend/routers/landed_cost.py:34 po_landed_cost_context](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/landed_cost.py#L34) | 1 |
| [backend/routers/landed_cost.py:46 landed_cost_payables](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/landed_cost.py#L46) | 1 |
| [backend/routers/landed_cost.py:87 list_landed_costs](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/landed_cost.py#L87) | 1 |
| [backend/routers/landed_cost.py:105 get_landed_cost](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/landed_cost.py#L105) | 1 |
| [backend/routers/landed_cost.py:119 create_landed_cost](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/landed_cost.py#L119) | 1 |
| [backend/routers/landed_cost.py:228 submit_landed_cost](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/landed_cost.py#L228) | 1 |
| [backend/routers/landed_cost.py:237 approve_landed_cost](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/landed_cost.py#L237) | 3 |
| [backend/routers/landed_cost.py:288 reject_landed_cost](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/landed_cost.py#L288) | 3 |
| [backend/routers/landed_cost.py:313 pay_landed_cost](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/landed_cost.py#L313) | 1 |
| [backend/routers/landed_cost.py:373 cancel_landed_cost](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/landed_cost.py#L373) | 1 |
| [backend/routers/logistics.py:37 logistics_meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L37) | 1 |
| [backend/routers/logistics.py:43 logistics_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L43) | 1 |
| [backend/routers/logistics.py:50 logistics_dashboard](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L50) | 1 |
| [backend/routers/logistics.py:62 logistics_history](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L62) | 1 |
| [backend/routers/logistics.py:73 fleet_availability](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L73) | 1 |
| [backend/routers/logistics.py:80 list_vehicles](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L80) | 1 |
| [backend/routers/logistics.py:87 create_vehicle](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L87) | 1 |
| [backend/routers/logistics.py:99 update_vehicle](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L99) | 1 |
| [backend/routers/logistics.py:115 set_vehicle_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L115) | 1 |
| [backend/routers/logistics.py:131 unassigned_shipments](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L131) | 1 |
| [backend/routers/logistics.py:138 list_drivers](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L138) | 1 |
| [backend/routers/logistics.py:146 set_my_route](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L146) | 1 |
| [backend/routers/logistics.py:157 list_deliveries](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L157) | 1 |
| [backend/routers/logistics.py:171 create_delivery](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L171) | 1 |
| [backend/routers/logistics.py:184 get_delivery](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L184) | 1 |
| [backend/routers/logistics.py:191 pickup_handover](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L191) | 1 |
| [backend/routers/logistics.py:208 update_delivery](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L208) | 1 |
| [backend/routers/logistics.py:221 upload_photo](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L221) | 1 |
| [backend/routers/logistics.py:237 get_photo](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L237) | 1 |
| [backend/routers/logistics.py:249 delete_photo](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L249) | 1 |
| [backend/routers/logistics.py:262 add_position](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L262) | 1 |
| [backend/routers/logistics.py:275 delete_position](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L275) | 1 |
| [backend/routers/logistics.py:289 transition](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/logistics.py#L289) | 1 |
| [backend/routers/lots.py:55 list_lots](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L55) | 1 |
| [backend/routers/lots.py:81 lot_stats](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L81) | 1 |
| [backend/routers/lots.py:89 lot_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L89) | 1 |
| [backend/routers/lots.py:97 update_lot_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L97) | 1 |
| [backend/routers/lots.py:110 unassigned_rolls](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L110) | 1 |
| [backend/routers/lots.py:130 get_lot](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L130) | 1 |
| [backend/routers/lots.py:152 lot_genealogy](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L152) | 1 |
| [backend/routers/lots.py:162 lot_recall](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L162) | 1 |
| [backend/routers/lots.py:173 lot_label](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L173) | 1 |
| [backend/routers/lots.py:189 create_lot](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L189) | 1 |
| [backend/routers/lots.py:223 patch_lot](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L223) | 1 |
| [backend/routers/lots.py:239 set_lot_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L239) | 1 |
| [backend/routers/lots.py:254 attach_rolls](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L254) | 1 |
| [backend/routers/lots.py:272 split_lot](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L272) | 1 |
| [backend/routers/lots.py:292 merge_lots](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L292) | 1 |
| [backend/routers/lots.py:314 rework_lot](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L314) | 1 |
| [backend/routers/lots.py:334 roll_lot](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/lots.py#L334) | 1 |
| [backend/routers/makloon_orders.py:36 list_process_stages](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L36) | 1 |
| [backend/routers/makloon_orders.py:50 process_stages_for_line](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L50) | 1 |
| [backend/routers/makloon_orders.py:61 list_orders](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L61) | 1 |
| [backend/routers/makloon_orders.py:77 create_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L77) | 1 |
| [backend/routers/makloon_orders.py:100 estimate_step](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L100) | 1 |
| [backend/routers/makloon_orders.py:111 list_claims](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L111) | 1 |
| [backend/routers/makloon_orders.py:120 claim_stats](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L120) | 1 |
| [backend/routers/makloon_orders.py:128 get_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L128) | 1 |
| [backend/routers/makloon_orders.py:139 issue_order_step](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L139) | 1 |
| [backend/routers/makloon_orders.py:159 receive_order_step](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L159) | 1 |
| [backend/routers/makloon_orders.py:184 cancel_partial](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L184) | 1 |
| [backend/routers/makloon_orders.py:197 record_order_service](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L197) | 1 |
| [backend/routers/makloon_orders.py:217 propose_claim](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L217) | 1 |
| [backend/routers/makloon_orders.py:235 approve_claim](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L235) | 1 |
| [backend/routers/makloon_orders.py:251 reject_claim](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L251) | 1 |
| [backend/routers/makloon_orders.py:269 cancel_order_ep](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloon_orders.py#L269) | 1 |
| [backend/routers/makloons.py:34 list_makloons](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloons.py#L34) | 1 |
| [backend/routers/makloons.py:45 create_makloon](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloons.py#L45) | 1 |
| [backend/routers/makloons.py:84 get_makloon](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloons.py#L84) | 1 |
| [backend/routers/makloons.py:96 update_makloon](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloons.py#L96) | 1 |
| [backend/routers/makloons.py:124 deactivate_makloon](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloons.py#L124) | 1 |
| [backend/routers/makloons.py:137 get_makloon_scorecard](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/makloons.py#L137) | 1 |
| [backend/routers/marketing.py:84 marketing_meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L84) | 1 |
| [backend/routers/marketing.py:96 list_campaigns](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L96) | 1 |
| [backend/routers/marketing.py:103 create_campaign](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L103) | 1 |
| [backend/routers/marketing.py:115 update_campaign](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L115) | 1 |
| [backend/routers/marketing.py:130 list_posts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L130) | 1 |
| [backend/routers/marketing.py:174 list_accounts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L174) | 1 |
| [backend/routers/marketing.py:181 create_account](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L181) | 1 |
| [backend/routers/marketing.py:191 update_account](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L191) | 1 |
| [backend/routers/marketing.py:225 list_templates](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L225) | 1 |
| [backend/routers/marketing.py:232 create_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L232) | 1 |
| [backend/routers/marketing.py:244 use_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L244) | 1 |
| [backend/routers/marketing.py:256 delete_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L256) | 1 |
| [backend/routers/marketing.py:271 marketing_dashboard](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L271) | 1 |
| [backend/routers/marketing.py:279 calendar_pdf](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L279) | 1 |
| [backend/routers/marketing.py:299 get_post](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L299) | 1 |
| [backend/routers/marketing.py:305 create_post](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L305) | 1 |
| [backend/routers/marketing.py:317 update_post](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L317) | 1 |
| [backend/routers/marketing.py:327 reschedule_post](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L327) | 2 |
| [backend/routers/marketing.py:350 duplicate_post](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L350) | 1 |
| [backend/routers/marketing.py:365 transition_post](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L365) | 1 |
| [backend/routers/marketing.py:377 post_metrics](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L377) | 1 |
| [backend/routers/marketing.py:387 delete_post](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L387) | 1 |
| [backend/routers/marketing.py:398 upload_attachment](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L398) | 1 |
| [backend/routers/marketing.py:410 attachment_file](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L410) | 1 |
| [backend/routers/marketing.py:421 delete_attachment](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L421) | 1 |
| [backend/routers/marketing.py:429 assets](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L429) | 1 |
| [backend/routers/marketing.py:436 marketing_analytics](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/marketing.py#L436) | 1 |
| [backend/routers/notifications.py:20 _scope_query](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/notifications.py#L20) | 11 |
| [backend/routers/notifications.py:59 list_notifications](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/notifications.py#L59) | 4 |
| [backend/routers/notifications.py:82 unread_count](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/notifications.py#L82) | 2 |
| [backend/routers/notifications.py:88 mark_all_read](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/notifications.py#L88) | 3 |
| [backend/routers/notifications.py:95 mark_read](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/notifications.py#L95) | 7 |
| [backend/routers/notifications.py:110 generate](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/notifications.py#L110) | 1 |
| [backend/routers/onboarding.py:44 get_onboarding](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/onboarding.py#L44) | 14 |
| [backend/routers/onboarding.py:66 complete_task](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/onboarding.py#L66) | 4 |
| [backend/routers/onboarding.py:81 reset_onboarding](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/onboarding.py#L81) | 3 |
| [backend/routers/outbound_picking.py:27 list_outbound_tasks](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L27) | 1 |
| [backend/routers/outbound_picking.py:62 release_scheduled_task](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L62) | 1 |
| [backend/routers/outbound_picking.py:82 scan_pick_item](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L82) | 1 |
| [backend/routers/outbound_picking.py:181 escalate_outbound_task](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L181) | 1 |
| [backend/routers/outbound_picking.py:236 resolve_outbound_escalation](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L236) | 1 |
| [backend/routers/outbound_picking.py:390 reopen_outbound_escalation](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L390) | 1 |
| [backend/routers/outbound_picking.py:413 dispatch_outbound](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L413) | 1 |
| [backend/routers/outbound_picking.py:448 start_loading_check](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L448) | 1 |
| [backend/routers/outbound_picking.py:458 scan_loading_check](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L458) | 1 |
| [backend/routers/outbound_picking.py:466 complete_loading_check](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L466) | 1 |
| [backend/routers/outbound_picking.py:477 get_loading_check](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking.py#L477) | 1 |
| [backend/routers/outbound_picking_extra.py:17 list_shipments](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking_extra.py#L17) | 1 |
| [backend/routers/outbound_picking_extra.py:30 shipment_surat_jalan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking_extra.py#L30) | 3 |
| [backend/routers/outbound_picking_extra.py:92 generate_surat_jalan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/outbound_picking_extra.py#L92) | 2 |
| [backend/routers/payment_plans.py:70 plan_meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_plans.py#L70) | 1 |
| [backend/routers/payment_plans.py:99 plan_preview](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_plans.py#L99) | 1 |
| [backend/routers/payment_plans.py:109 list_plans](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_plans.py#L109) | 1 |
| [backend/routers/payment_plans.py:121 plan_by_doc](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_plans.py#L121) | 1 |
| [backend/routers/payment_plans.py:137 create_plan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_plans.py#L137) | 1 |
| [backend/routers/payment_plans.py:150 update_plan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_plans.py#L150) | 1 |
| [backend/routers/payment_plans.py:162 void_plan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_plans.py#L162) | 1 |
| [backend/routers/payment_plans.py:174 accrue_now](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_plans.py#L174) | 1 |
| [backend/routers/payment_plans.py:189 list_penalties](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_plans.py#L189) | 1 |
| [backend/routers/payment_plans.py:203 get_penalty](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_plans.py#L203) | 1 |
| [backend/routers/payment_plans.py:214 issue_penalty](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_plans.py#L214) | 1 |
| [backend/routers/payment_plans.py:226 waive_penalty](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_plans.py#L226) | 1 |
| [backend/routers/payment_plans.py:239 adjust_penalty](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_plans.py#L239) | 1 |
| [backend/routers/payment_plans.py:253 pay_penalty](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_plans.py#L253) | 1 |
| [backend/routers/payment_variance.py:51 variance_meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_variance.py#L51) | 1 |
| [backend/routers/payment_variance.py:65 assess](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_variance.py#L65) | 1 |
| [backend/routers/payment_variance.py:84 list_decisions](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_variance.py#L84) | 1 |
| [backend/routers/payment_variance.py:100 list_pending](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_variance.py#L100) | 1 |
| [backend/routers/payment_variance.py:109 by_receipt](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_variance.py#L109) | 1 |
| [backend/routers/payment_variance.py:142 decide](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_variance.py#L142) | 1 |
| [backend/routers/payment_variance.py:158 get_decision](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_variance.py#L158) | 1 |
| [backend/routers/payment_variance.py:168 reverse](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/payment_variance.py#L168) | 1 |
| [backend/routers/pdf.py:72 list_doc_types](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pdf.py#L72) | 1 |
| [backend/routers/pdf.py:79 render_document](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pdf.py#L79) | 1 |
| [backend/routers/pdf.py:106 get_sample](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pdf.py#L106) | 1 |
| [backend/routers/pdf.py:125 list_documents](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pdf.py#L125) | 1 |
| [backend/routers/pdf.py:184 list_templates](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pdf.py#L184) | 1 |
| [backend/routers/pdf.py:192 get_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pdf.py#L192) | 1 |
| [backend/routers/pdf.py:202 put_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pdf.py#L202) | 1 |
| [backend/routers/pdf.py:216 reset_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pdf.py#L216) | 1 |
| [backend/routers/pdf.py:226 validate_script](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pdf.py#L226) | 1 |
| [backend/routers/pdf.py:234 get_branding](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pdf.py#L234) | 1 |
| [backend/routers/pdf.py:240 put_branding](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pdf.py#L240) | 1 |
| [backend/routers/pdf.py:246 preview](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pdf.py#L246) | 1 |
| [backend/routers/pegging.py:56 list_earmarked](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pegging.py#L56) | 1 |
| [backend/routers/pegging.py:71 earmark_roll](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pegging.py#L71) | 1 |
| [backend/routers/pegging.py:110 unearmark_roll](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pegging.py#L110) | 1 |
| [backend/routers/period_unlocks.py:42 list_unlocks](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/period_unlocks.py#L42) | 2 |
| [backend/routers/period_unlocks.py:50 active_unlocks](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/period_unlocks.py#L50) | 2 |
| [backend/routers/period_unlocks.py:58 create_unlock](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/period_unlocks.py#L58) | 1 |
| [backend/routers/period_unlocks.py:75 approve_unlock](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/period_unlocks.py#L75) | 1 |
| [backend/routers/period_unlocks.py:88 reject_unlock](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/period_unlocks.py#L88) | 1 |
| [backend/routers/period_unlocks.py:101 reclose_expired](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/period_unlocks.py#L101) | 1 |
| [backend/routers/po_board.py:36 po_board](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/po_board.py#L36) | 1 |
| [backend/routers/po_board.py:54 patch_po_stage](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/po_board.py#L54) | 1 |
| [backend/routers/pos.py:13 get_best_sellers](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pos.py#L13) | 1 |
| [backend/routers/pos.py:24 get_frequently_bought_together](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pos.py#L24) | 1 |
| [backend/routers/pos.py:36 get_substitutes](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pos.py#L36) | 1 |
| [backend/routers/price_approvals.py:37 price_hint](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L37) | 1 |
| [backend/routers/price_approvals.py:131 list_price_approvals](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L131) | 1 |
| [backend/routers/price_approvals.py:153 effective_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L153) | 1 |
| [backend/routers/price_approvals.py:178 price_approval_stats](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L178) | 1 |
| [backend/routers/price_approvals.py:197 create_price_approval](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L197) | 1 |
| [backend/routers/price_approvals.py:249 get_price_approval](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L249) | 1 |
| [backend/routers/price_approvals.py:259 patch_price_approval](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L259) | 1 |
| [backend/routers/price_approvals.py:293 delete_price_approval](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L293) | 1 |
| [backend/routers/price_approvals.py:307 submit_price_approval](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L307) | 1 |
| [backend/routers/price_approvals.py:327 approve_price_approval](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L327) | 1 |
| [backend/routers/price_approvals.py:420 reject_price_approval](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L420) | 1 |
| [backend/routers/price_approvals.py:452 revoke_price_approval](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L452) | 1 |
| [backend/routers/price_approvals.py:512 upload_attachment](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L512) | 1 |
| [backend/routers/price_approvals.py:545 download_attachment](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L545) | 2 |
| [backend/routers/price_approvals.py:572 delete_attachment](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/price_approvals.py#L572) | 1 |
| [backend/routers/pricelist.py:29 pricelist_grid](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pricelist.py#L29) | 1 |
| [backend/routers/pricelist.py:42 pricelist_records](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pricelist.py#L42) | 1 |
| [backend/routers/pricelist.py:52 pricelist_export](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pricelist.py#L52) | 1 |
| [backend/routers/pricelist.py:65 pricelist_import](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pricelist.py#L65) | 1 |
| [backend/routers/pricelist.py:94 revert_to_global](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pricelist.py#L94) | 1 |
| [backend/routers/pricelist.py:116 create_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pricelist.py#L116) | 1 |
| [backend/routers/pricelist.py:133 patch_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pricelist.py#L133) | 1 |
| [backend/routers/pricelist.py:150 delete_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/pricelist.py#L150) | 1 |
| [backend/routers/process_recipes.py:54 list_recipes](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/process_recipes.py#L54) | 1 |
| [backend/routers/process_recipes.py:69 create_recipe](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/process_recipes.py#L69) | 1 |
| [backend/routers/process_recipes.py:104 update_recipe](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/process_recipes.py#L104) | 1 |
| [backend/routers/process_recipes.py:127 deactivate_recipe](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/process_recipes.py#L127) | 1 |
| [backend/routers/process_recipes.py:140 preview_forecast](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/process_recipes.py#L140) | 1 |
| [backend/routers/product_media.py:42 meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_media.py#L42) | 1 |
| [backend/routers/product_media.py:56 list_media](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_media.py#L56) | 1 |
| [backend/routers/product_media.py:64 upload](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_media.py#L64) | 1 |
| [backend/routers/product_media.py:74 content](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_media.py#L74) | 1 |
| [backend/routers/product_media.py:89 update](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_media.py#L89) | 1 |
| [backend/routers/product_media.py:104 relations](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_media.py#L104) | 1 |
| [backend/routers/product_media.py:118 remove](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_media.py#L118) | 1 |
| [backend/routers/product_media.py:127 from_design](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_media.py#L127) | 1 |
| [backend/routers/product_media.py:155 generate_mockup](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_media.py#L155) | 1 |
| [backend/routers/product_templates.py:21 list_templates](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_templates.py#L21) | 1 |
| [backend/routers/product_templates.py:29 template_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_templates.py#L29) | 1 |
| [backend/routers/product_templates.py:42 resolve_orphans](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_templates.py#L42) | 1 |
| [backend/routers/product_templates.py:52 get_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_templates.py#L52) | 1 |
| [backend/routers/product_templates.py:65 create_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_templates.py#L65) | 1 |
| [backend/routers/product_templates.py:82 patch_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_templates.py#L82) | 1 |
| [backend/routers/product_templates.py:99 delete_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_templates.py#L99) | 1 |
| [backend/routers/product_templates.py:111 generate_variants](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_templates.py#L111) | 1 |
| [backend/routers/product_templates.py:123 assign_products](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_templates.py#L123) | 1 |
| [backend/routers/product_templates.py:134 detach_products](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_templates.py#L134) | 1 |
| [backend/routers/product_traceability.py:69 product_purchase_history](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/product_traceability.py#L69) | 1 |
| [backend/routers/production.py:84 list_boms](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/production.py#L84) | 1 |
| [backend/routers/production.py:94 create_bom](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/production.py#L94) | 1 |
| [backend/routers/production.py:109 get_bom](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/production.py#L109) | 1 |
| [backend/routers/production.py:119 update_bom](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/production.py#L119) | 1 |
| [backend/routers/production.py:136 delete_bom](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/production.py#L136) | 1 |
| [backend/routers/production.py:156 list_work_orders](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/production.py#L156) | 1 |
| [backend/routers/production.py:165 create_work_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/production.py#L165) | 1 |
| [backend/routers/production.py:178 get_work_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/production.py#L178) | 1 |
| [backend/routers/production.py:188 release_work_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/production.py#L188) | 1 |
| [backend/routers/production.py:200 complete_work_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/production.py#L200) | 1 |
| [backend/routers/production.py:213 cancel_work_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/production.py#L213) | 1 |
| [backend/routers/production.py:225 production_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/production.py#L225) | 1 |
| [backend/routers/products.py:22 list_products](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/products.py#L22) | 1 |
| [backend/routers/products.py:93 create_product](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/products.py#L93) | 1 |
| [backend/routers/products.py:138 update_product](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/products.py#L138) | 1 |
| [backend/routers/products.py:216 list_sales_owners](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/products.py#L216) | 1 |
| [backend/routers/products.py:231 delete_product](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/products.py#L231) | 1 |
| [backend/routers/products.py:249 stock_breakdown](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/products.py#L249) | 1 |
| [backend/routers/purchase_orders.py:217 list_purchase_orders](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders.py#L217) | 1 |
| [backend/routers/purchase_orders.py:247 create_purchase_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders.py#L247) | 1 |
| [backend/routers/purchase_orders.py:255 resolve_po_sourcing](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders.py#L255) | 3 |
| [backend/routers/purchase_orders.py:687 amend_purchase_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders.py#L687) | 1 |
| [backend/routers/purchase_orders.py:713 approve_purchase_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders.py#L713) | 4 |
| [backend/routers/purchase_orders.py:825 reject_purchase_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders.py#L825) | 4 |
| [backend/routers/purchase_orders.py:864 get_purchase_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders.py#L864) | 1 |
| [backend/routers/purchase_orders_extra.py:23 create_blanket_po](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders_extra.py#L23) | 1 |
| [backend/routers/purchase_orders_extra.py:34 list_blanket_pos](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders_extra.py#L34) | 1 |
| [backend/routers/purchase_orders_extra.py:43 create_call_off](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders_extra.py#L43) | 1 |
| [backend/routers/purchase_orders_extra.py:69 close_blanket_contract](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders_extra.py#L69) | 1 |
| [backend/routers/purchase_orders_extra.py:79 pay_purchase_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders_extra.py#L79) | 1 |
| [backend/routers/purchase_orders_extra.py:95 close_purchase_order_short](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders_extra.py#L95) | 1 |
| [backend/routers/purchase_orders_extra.py:132 payables_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders_extra.py#L132) | 1 |
| [backend/routers/purchase_orders_extra.py:187 cancel_purchase_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_orders_extra.py#L187) | 1 |
| [backend/routers/purchase_requisitions.py:25 list_requisitions](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_requisitions.py#L25) | 1 |
| [backend/routers/purchase_requisitions.py:50 reorder_suggestions](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_requisitions.py#L50) | 1 |
| [backend/routers/purchase_requisitions.py:58 create_requisition](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_requisitions.py#L58) | 1 |
| [backend/routers/purchase_requisitions.py:73 get_requisition](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_requisitions.py#L73) | 1 |
| [backend/routers/purchase_requisitions.py:84 update_line_qty](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_requisitions.py#L84) | 1 |
| [backend/routers/purchase_requisitions.py:103 submit_requisition](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_requisitions.py#L103) | 1 |
| [backend/routers/purchase_requisitions.py:114 approve_requisition](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_requisitions.py#L114) | 1 |
| [backend/routers/purchase_requisitions.py:137 reject_requisition](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_requisitions.py#L137) | 1 |
| [backend/routers/purchase_requisitions.py:159 cancel_requisition](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_requisitions.py#L159) | 1 |
| [backend/routers/purchase_requisitions.py:170 convert_to_po](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_requisitions.py#L170) | 1 |
| [backend/routers/purchase_requisitions.py:195 pr_sourcing](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_requisitions.py#L195) | 1 |
| [backend/routers/purchase_requisitions.py:210 realize_po](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_requisitions.py#L210) | 1 |
| [backend/routers/purchase_requisitions.py:234 makloon_prefill](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_requisitions.py#L234) | 1 |
| [backend/routers/purchase_requisitions.py:244 realize_makloon](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_requisitions.py#L244) | 1 |
| [backend/routers/purchase_returns.py:25 list_purchase_returns](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_returns.py#L25) | 1 |
| [backend/routers/purchase_returns.py:52 purchase_return_status_counts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_returns.py#L52) | 1 |
| [backend/routers/purchase_returns.py:71 create_purchase_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_returns.py#L71) | 1 |
| [backend/routers/purchase_returns.py:88 purchase_return_source_rolls](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_returns.py#L88) | 1 |
| [backend/routers/purchase_returns.py:109 get_purchase_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_returns.py#L109) | 1 |
| [backend/routers/purchase_returns.py:115 submit_purchase_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_returns.py#L115) | 1 |
| [backend/routers/purchase_returns.py:127 approve_purchase_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_returns.py#L127) | 1 |
| [backend/routers/purchase_returns.py:141 reject_purchase_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_returns.py#L141) | 1 |
| [backend/routers/purchase_returns.py:156 ship_purchase_return_to_supplier](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_returns.py#L156) | 1 |
| [backend/routers/purchase_returns.py:172 supplier_accept_purchase_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_returns.py#L172) | 1 |
| [backend/routers/purchase_returns.py:188 supplier_reject_purchase_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_returns.py#L188) | 1 |
| [backend/routers/purchase_returns.py:202 goods_back_purchase_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_returns.py#L202) | 1 |
| [backend/routers/purchase_returns.py:225 reverse_purchase_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_returns.py#L225) | 1 |
| [backend/routers/purchase_returns.py:245 delete_purchase_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/purchase_returns.py#L245) | 1 |
| [backend/routers/push.py:38 public_key](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/push.py#L38) | 3 |
| [backend/routers/push.py:45 subscribe](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/push.py#L45) | 3 |
| [backend/routers/push.py:62 unsubscribe](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/push.py#L62) | 3 |
| [backend/routers/push.py:69 status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/push.py#L69) | 3 |
| [backend/routers/push.py:76 test_push](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/push.py#L76) | 4 |
| [backend/routers/putaway_orders.py:36 get_suggest](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/putaway_orders.py#L36) | 1 |
| [backend/routers/putaway_orders.py:42 get_orders](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/putaway_orders.py#L42) | 1 |
| [backend/routers/putaway_orders.py:49 post_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/putaway_orders.py#L49) | 1 |
| [backend/routers/putaway_orders.py:63 post_dispatch](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/putaway_orders.py#L63) | 1 |
| [backend/routers/putaway_orders.py:71 post_confirm](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/putaway_orders.py#L71) | 1 |
| [backend/routers/putaway_orders.py:81 post_resolve](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/putaway_orders.py#L81) | 1 |
| [backend/routers/putaway_orders.py:91 get_wms_health](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/putaway_orders.py#L91) | 1 |
| [backend/routers/qc_inspection.py:24 get_grade_thresholds](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/qc_inspection.py#L24) | 1 |
| [backend/routers/qc_inspection.py:31 list_task_rolls](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/qc_inspection.py#L31) | 1 |
| [backend/routers/qc_inspection.py:41 inspect](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/qc_inspection.py#L41) | 1 |
| [backend/routers/qc_inspection.py:84 roll_grade_history](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/qc_inspection.py#L84) | 1 |
| [backend/routers/qc_inspection.py:98 roll_grade_override](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/qc_inspection.py#L98) | 1 |
| [backend/routers/reporting.py:27 stock_aging](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/reporting.py#L27) | 1 |
| [backend/routers/reporting.py:79 reservation_funnel](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/reporting.py#L79) | 1 |
| [backend/routers/reporting.py:119 order_velocity](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/reporting.py#L119) | 1 |
| [backend/routers/reporting.py:152 top_customers](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/reporting.py#L152) | 1 |
| [backend/routers/reporting.py:192 warehouse_utilization](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/reporting.py#L192) | 1 |
| [backend/routers/reporting.py:259 dashboard_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/reporting.py#L259) | 1 |
| [backend/routers/return_policies.py:36 list_sales_return_policies](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/return_policies.py#L36) | 2 |
| [backend/routers/return_policies.py:71 sales_return_eligibility](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/return_policies.py#L71) | 1 |
| [backend/routers/return_policies.py:92 create_sales_return_policy](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/return_policies.py#L92) | 1 |
| [backend/routers/return_policies.py:143 get_sales_return_policy](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/return_policies.py#L143) | 2 |
| [backend/routers/return_policies.py:156 update_sales_return_policy](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/return_policies.py#L156) | 1 |
| [backend/routers/return_policies.py:210 deactivate_sales_return_policy](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/return_policies.py#L210) | 1 |
| [backend/routers/rfid.py:84 get_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L84) | 1 |
| [backend/routers/rfid.py:94 get_tags](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L94) | 1 |
| [backend/routers/rfid.py:104 lookup_code](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L104) | 1 |
| [backend/routers/rfid.py:147 post_roll_scan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L147) | 1 |
| [backend/routers/rfid.py:178 get_roll_scans](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L178) | 1 |
| [backend/routers/rfid.py:190 printer_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L190) | 1 |
| [backend/routers/rfid.py:234 labels_for_document](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L234) | 1 |
| [backend/routers/rfid.py:262 get_untagged](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L262) | 1 |
| [backend/routers/rfid.py:272 post_encode](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L272) | 1 |
| [backend/routers/rfid.py:283 post_auto_encode](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L283) | 1 |
| [backend/routers/rfid.py:293 delete_tag](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L293) | 1 |
| [backend/routers/rfid.py:304 get_devices](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L304) | 1 |
| [backend/routers/rfid.py:311 post_device](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L311) | 1 |
| [backend/routers/rfid.py:319 patch_device](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L319) | 1 |
| [backend/routers/rfid.py:327 del_device](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L327) | 1 |
| [backend/routers/rfid.py:335 post_seed_devices](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L335) | 1 |
| [backend/routers/rfid.py:344 get_reads](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L344) | 1 |
| [backend/routers/rfid.py:353 post_gate_simulate](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L353) | 1 |
| [backend/routers/rfid.py:365 post_reader_scan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L365) | 1 |
| [backend/routers/rfid.py:374 get_locations](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L374) | 1 |
| [backend/routers/rfid.py:385 get_print_jobs](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L385) | 1 |
| [backend/routers/rfid.py:395 post_print_job](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L395) | 1 |
| [backend/routers/rfid.py:409 get_print_job](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L409) | 1 |
| [backend/routers/rfid.py:417 get_print_job_zpl](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L417) | 1 |
| [backend/routers/rfid.py:428 post_mark_printed](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L428) | 1 |
| [backend/routers/rfid.py:438 post_verify_start](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L438) | 1 |
| [backend/routers/rfid.py:446 post_verify_scan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L446) | 1 |
| [backend/routers/rfid.py:454 post_verify_complete](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L454) | 1 |
| [backend/routers/rfid.py:466 post_set_routing](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L466) | 1 |
| [backend/routers/rfid.py:483 post_device_api_key](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L483) | 1 |
| [backend/routers/rfid.py:494 post_ingest](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L494) | 2 |
| [backend/routers/rfid.py:502 post_heartbeat](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L502) | 2 |
| [backend/routers/rfid.py:509 get_device_jobs](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L509) | 2 |
| [backend/routers/rfid.py:517 post_device_job_ack](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L517) | 2 |
| [backend/routers/rfid.py:529 get_incidents](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L529) | 1 |
| [backend/routers/rfid.py:538 post_incident_ack](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L538) | 1 |
| [backend/routers/rfid.py:548 post_incident_resolve](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L548) | 1 |
| [backend/routers/rfid.py:558 get_shrinkage](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L558) | 1 |
| [backend/routers/rfid.py:565 get_device_health](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L565) | 1 |
| [backend/routers/rfid.py:577 post_cc_start](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L577) | 1 |
| [backend/routers/rfid.py:589 post_cc_complete](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L589) | 1 |
| [backend/routers/rfid.py:599 get_cc_list](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L599) | 1 |
| [backend/routers/rfid.py:607 get_cc_detail](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfid.py#L607) | 1 |
| [backend/routers/rfq.py:33 list_rfqs](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfq.py#L33) | 1 |
| [backend/routers/rfq.py:45 get_rfq](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfq.py#L45) | 1 |
| [backend/routers/rfq.py:54 compare_rfq](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfq.py#L54) | 1 |
| [backend/routers/rfq.py:60 create_rfq](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfq.py#L60) | 1 |
| [backend/routers/rfq.py:135 send_rfq](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfq.py#L135) | 1 |
| [backend/routers/rfq.py:149 submit_quote](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfq.py#L149) | 1 |
| [backend/routers/rfq.py:184 award](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfq.py#L184) | 1 |
| [backend/routers/rfq.py:205 cancel_rfq](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rfq.py#L205) | 1 |
| [backend/routers/rnd.py:108 rnd_meta](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L108) | 1 |
| [backend/routers/rnd.py:138 list_sample_types](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L138) | 1 |
| [backend/routers/rnd.py:154 list_specs](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L154) | 1 |
| [backend/routers/rnd.py:171 create_spec](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L171) | 1 |
| [backend/routers/rnd.py:187 get_spec](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L187) | 1 |
| [backend/routers/rnd.py:199 patch_spec](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L199) | 1 |
| [backend/routers/rnd.py:216 submit_spec](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L216) | 1 |
| [backend/routers/rnd.py:233 approve_spec](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L233) | 1 |
| [backend/routers/rnd.py:257 reject_spec](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L257) | 1 |
| [backend/routers/rnd.py:276 release_product](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L276) | 1 |
| [backend/routers/rnd.py:294 list_samples](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L294) | 1 |
| [backend/routers/rnd.py:314 attach_sample_spec](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L314) | 1 |
| [backend/routers/rnd.py:332 labdip_history](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L332) | 1 |
| [backend/routers/rnd.py:347 create_sample](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L347) | 1 |
| [backend/routers/rnd.py:372 get_sample](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L372) | 1 |
| [backend/routers/rnd.py:383 patch_sample](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L383) | 1 |
| [backend/routers/rnd.py:398 send_sample](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L398) | 1 |
| [backend/routers/rnd.py:417 open_round](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L417) | 1 |
| [backend/routers/rnd.py:436 upload_round_file](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L436) | 1 |
| [backend/routers/rnd.py:453 download_round_file](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L453) | 1 |
| [backend/routers/rnd.py:468 submit_round](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L468) | 1 |
| [backend/routers/rnd.py:485 assess_round](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L485) | 1 |
| [backend/routers/rnd.py:501 decide_sample](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L501) | 1 |
| [backend/routers/rnd.py:526 issue_material](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L526) | 1 |
| [backend/routers/rnd.py:542 cancel_sample](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L542) | 1 |
| [backend/routers/rnd.py:566 finish_sample](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L566) | 1 |
| [backend/routers/rnd.py:584 deliver_sample](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L584) | 1 |
| [backend/routers/rnd.py:605 performer_report](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L605) | 1 |
| [backend/routers/rnd.py:616 designer_kpi_report](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L616) | 1 |
| [backend/routers/rnd.py:637 my_designer_kpi](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L637) | 6 |
| [backend/routers/rnd.py:657 designer_kpi_trend_report](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L657) | 1 |
| [backend/routers/rnd.py:677 export_designer_kpi](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L677) | 1 |
| [backend/routers/rnd.py:706 designer_kpi_report_pdf](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L706) | 1 |
| [backend/routers/rnd.py:741 sla_board](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L741) | 1 |
| [backend/routers/rnd.py:753 run_sla_escalation](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L753) | 1 |
| [backend/routers/rnd.py:769 lifecycle_board](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd.py#L769) | 1 |
| [backend/routers/rnd_org.py:38 list_divisions](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd_org.py#L38) | 1 |
| [backend/routers/rnd_org.py:48 list_members](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd_org.py#L48) | 1 |
| [backend/routers/rnd_org.py:59 set_member_division](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/rnd_org.py#L59) | 1 |
| [backend/routers/saga_locks.py:19 list_saga_locks](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/saga_locks.py#L19) | 1 |
| [backend/routers/saga_locks.py:29 release_saga_lock](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/saga_locks.py#L29) | 1 |
| [backend/routers/sales_orders.py:87 create_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders.py#L87) | 1 |
| [backend/routers/sales_orders.py:619 get_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders.py#L619) | 1 |
| [backend/routers/sales_orders.py:646 update_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders.py#L646) | 1 |
| [backend/routers/sales_orders_extra.py:52 preview_allocation](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L52) | 1 |
| [backend/routers/sales_orders_extra.py:93 preview_lots](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L93) | 1 |
| [backend/routers/sales_orders_extra.py:142 list_orders](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L142) | 1 |
| [backend/routers/sales_orders_extra.py:189 get_orders_stats](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L189) | 1 |
| [backend/routers/sales_orders_extra.py:271 frequent_products](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L271) | 1 |
| [backend/routers/sales_orders_extra.py:278 order_journey](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L278) | 1 |
| [backend/routers/sales_orders_extra.py:301 preview_roll_reconcile](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L301) | 1 |
| [backend/routers/sales_orders_extra.py:322 restock_state](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L322) | 1 |
| [backend/routers/sales_orders_extra.py:336 repeat_restock](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L336) | 1 |
| [backend/routers/sales_orders_extra.py:363 submit_for_approval](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L363) | 1 |
| [backend/routers/sales_orders_extra.py:421 approve_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L421) | 1 |
| [backend/routers/sales_orders_extra.py:478 confirm_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L478) | 1 |
| [backend/routers/sales_orders_extra.py:521 mark_delivered](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L521) | 1 |
| [backend/routers/sales_orders_extra.py:552 reallocate_line_rolls](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L552) | 1 |
| [backend/routers/sales_orders_extra.py:666 release_line_rolls](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L666) | 1 |
| [backend/routers/sales_orders_extra.py:771 release_reservation](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L771) | 1 |
| [backend/routers/sales_orders_extra.py:806 cancel_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_orders_extra.py#L806) | 1 |
| [backend/routers/sales_returns.py:33 list_returns](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L33) | 1 |
| [backend/routers/sales_returns.py:69 sales_return_status_counts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L69) | 1 |
| [backend/routers/sales_returns.py:90 list_credit_notes](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L90) | 1 |
| [backend/routers/sales_returns.py:110 get_credit_note](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L110) | 1 |
| [backend/routers/sales_returns.py:124 create_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L124) | 1 |
| [backend/routers/sales_returns.py:168 get_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L168) | 1 |
| [backend/routers/sales_returns.py:207 submit_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L207) | 1 |
| [backend/routers/sales_returns.py:233 approve_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L233) | 1 |
| [backend/routers/sales_returns.py:261 start_inspection](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L261) | 1 |
| [backend/routers/sales_returns.py:278 complete_inspection](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L278) | 1 |
| [backend/routers/sales_returns.py:302 mark_return_milestone](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L302) | 1 |
| [backend/routers/sales_returns.py:329 set_return_complaint](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L329) | 1 |
| [backend/routers/sales_returns.py:358 return_complaint_reasons](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L358) | 1 |
| [backend/routers/sales_returns.py:375 settle_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L375) | 1 |
| [backend/routers/sales_returns.py:410 reverse_return_settlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L410) | 1 |
| [backend/routers/sales_returns.py:443 reverse_return_writeoff](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L443) | 1 |
| [backend/routers/sales_returns.py:473 list_quarantine_rolls](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L473) | 1 |
| [backend/routers/sales_returns.py:485 release_quarantine](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L485) | 1 |
| [backend/routers/sales_returns.py:509 return_chain](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L509) | 1 |
| [backend/routers/sales_returns.py:536 transfer_roll_ownership](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L536) | 1 |
| [backend/routers/sales_returns.py:566 create_purchase_return_from_sales_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L566) | 1 |
| [backend/routers/sales_returns.py:602 reject_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L602) | 1 |
| [backend/routers/sales_returns.py:627 upload_attachment](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L627) | 1 |
| [backend/routers/sales_returns.py:665 download_attachment](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L665) | 1 |
| [backend/routers/sales_returns.py:683 delete_attachment](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L683) | 1 |
| [backend/routers/sales_returns.py:711 relocate_return](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sales_returns.py#L711) | 1 |
| [backend/routers/sample_orders.py:49 sample_limits](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sample_orders.py#L49) | 1 |
| [backend/routers/sample_orders.py:55 list_sample_orders](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sample_orders.py#L55) | 1 |
| [backend/routers/sample_orders.py:70 sample_stats](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sample_orders.py#L70) | 1 |
| [backend/routers/sample_orders.py:98 sample_desk](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sample_orders.py#L98) | 1 |
| [backend/routers/sample_orders.py:133 approve_payment](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sample_orders.py#L133) | 1 |
| [backend/routers/sample_orders.py:160 confirm_sample](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sample_orders.py#L160) | 1 |
| [backend/routers/sample_orders.py:181 cancel_sample](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sample_orders.py#L181) | 1 |
| [backend/routers/sample_sales.py:33 list_sample_prices](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sample_sales.py#L33) | 1 |
| [backend/routers/sample_sales.py:44 put_sample_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sample_sales.py#L44) | 1 |
| [backend/routers/sample_sales.py:56 sample_quote](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sample_sales.py#L56) | 1 |
| [backend/routers/sample_sales.py:70 cut_sample](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/sample_sales.py#L70) | 1 |
| [backend/routers/scheduler.py:31 list_jobs](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/scheduler.py#L31) | 1 |
| [backend/routers/scheduler.py:37 scheduler_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/scheduler.py#L37) | 1 |
| [backend/routers/scheduler.py:43 run_job_now](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/scheduler.py#L43) | 1 |
| [backend/routers/scheduler.py:61 list_runs](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/scheduler.py#L61) | 1 |
| [backend/routers/scheduler.py:69 get_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/scheduler.py#L69) | 1 |
| [backend/routers/scheduler.py:80 digest_preview](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/scheduler.py#L80) | 1 |
| [backend/routers/scheduler.py:89 update_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/scheduler.py#L89) | 1 |
| [backend/routers/scheduler.py:188 wa_outbox](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/scheduler.py#L188) | 1 |
| [backend/routers/scheduler.py:196 wa_retry](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/scheduler.py#L196) | 1 |
| [backend/routers/scheduler.py:207 wa_test](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/scheduler.py#L207) | 1 |
| [backend/routers/settings.py:25 read_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/settings.py#L25) | 2 |
| [backend/routers/settings.py:31 read_effective_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/settings.py#L31) | 4 |
| [backend/routers/settings.py:45 update_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/settings.py#L45) | 1 |
| [backend/routers/settings.py:75 compute_tax_endpoint](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/settings.py#L75) | 3 |
| [backend/routers/settings.py:82 evaluate_approval_endpoint](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/settings.py#L82) | 3 |
| [backend/routers/settings.py:92 list_payment_terms](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/settings.py#L92) | 5 |
| [backend/routers/settings.py:110 create_payment_term](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/settings.py#L110) | 1 |
| [backend/routers/settings.py:122 update_payment_term](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/settings.py#L122) | 1 |
| [backend/routers/settings.py:135 override_payment_term](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/settings.py#L135) | 1 |
| [backend/routers/settings.py:147 delete_payment_term](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/settings.py#L147) | 1 |
| [backend/routers/so_approvals.py:90 request_special_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/so_approvals.py#L90) | 1 |
| [backend/routers/so_approvals.py:138 request_credit_approval](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/so_approvals.py#L138) | 1 |
| [backend/routers/so_approvals.py:175 decide_approval](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/so_approvals.py#L175) | 1 |
| [backend/routers/so_approvals.py:245 upload_evidence](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/so_approvals.py#L245) | 1 |
| [backend/routers/so_approvals.py:285 download_evidence](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/so_approvals.py#L285) | 2 |
| [backend/routers/so_approvals.py:316 approvals_backlog](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/so_approvals.py#L316) | 1 |
| [backend/routers/so_approvals.py:350 approvals_queue_board](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/so_approvals.py#L350) | 2 |
| [backend/routers/so_approvals.py:379 approvals_queue](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/so_approvals.py#L379) | 1 |
| [backend/routers/special_orders.py:101 list_special_orders](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L101) | 1 |
| [backend/routers/special_orders.py:156 create_special_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L156) | 1 |
| [backend/routers/special_orders.py:321 get_special_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L321) | 1 |
| [backend/routers/special_orders.py:335 upload_od_reference](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L335) | 1 |
| [backend/routers/special_orders.py:350 get_od_reference](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L350) | 1 |
| [backend/routers/special_orders.py:363 route_od_now](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L363) | 1 |
| [backend/routers/special_orders.py:411 submit_special_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L411) | 1 |
| [backend/routers/special_orders.py:435 customer_decision](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L435) | 1 |
| [backend/routers/special_orders.py:449 customer_decision_evidence](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L449) | 1 |
| [backend/routers/special_orders.py:462 customer_decision_evidence_file](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L462) | 1 |
| [backend/routers/special_orders.py:473 pricing_preview](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L473) | 1 |
| [backend/routers/special_orders.py:480 lock_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L480) | 1 |
| [backend/routers/special_orders.py:502 procure_now](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L502) | 1 |
| [backend/routers/special_orders.py:517 prepare_shipment](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L517) | 1 |
| [backend/routers/special_orders.py:530 unlock_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L530) | 1 |
| [backend/routers/special_orders.py:544 approve_special_order_endpoint](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L544) | 1 |
| [backend/routers/special_orders.py:636 reject_special_order_endpoint](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L636) | 1 |
| [backend/routers/special_orders.py:679 update_special_order_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L679) | 1 |
| [backend/routers/special_orders.py:707 create_pr_from_special_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L707) | 1 |
| [backend/routers/special_orders.py:789 create_sku_endpoint](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L789) | 1 |
| [backend/routers/special_orders.py:817 convert_special_order_to_so](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L817) | 1 |
| [backend/routers/special_orders.py:908 patch_special_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L908) | 1 |
| [backend/routers/special_orders.py:953 delete_special_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/special_orders.py#L953) | 1 |
| [backend/routers/stock_buckets.py:19 stock_buckets](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/stock_buckets.py#L19) | 1 |
| [backend/routers/stock_buckets.py:28 list_holds](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/stock_buckets.py#L28) | 1 |
| [backend/routers/stock_buckets.py:36 list_wip](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/stock_buckets.py#L36) | 1 |
| [backend/routers/stock_buckets.py:44 pending_so](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/stock_buckets.py#L44) | 1 |
| [backend/routers/stock_buckets.py:53 stock_atp](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/stock_buckets.py#L53) | 1 |
| [backend/routers/stock_buckets.py:70 create_hold](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/stock_buckets.py#L70) | 1 |
| [backend/routers/stock_buckets.py:82 release_hold](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/stock_buckets.py#L82) | 1 |
| [backend/routers/stock_buckets.py:90 start_wip](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/stock_buckets.py#L90) | 1 |
| [backend/routers/stock_buckets.py:101 complete_wip](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/stock_buckets.py#L101) | 1 |
| [backend/routers/store_credit.py:72 list_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/store_credit.py#L72) | 1 |
| [backend/routers/store_credit.py:79 get_balance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/store_credit.py#L79) | 1 |
| [backend/routers/store_credit.py:90 get_ledger](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/store_credit.py#L90) | 1 |
| [backend/routers/store_credit.py:98 open_orders](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/store_credit.py#L98) | 1 |
| [backend/routers/store_credit.py:105 redeem](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/store_credit.py#L105) | 1 |
| [backend/routers/store_credit.py:116 adjust](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/store_credit.py#L116) | 1 |
| [backend/routers/store_credit.py:126 reverse_entry](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/store_credit.py#L126) | 1 |
| [backend/routers/supplier_contracts.py:35 list_contracts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_contracts.py#L35) | 1 |
| [backend/routers/supplier_contracts.py:58 contract_stats](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_contracts.py#L58) | 1 |
| [backend/routers/supplier_contracts.py:69 get_policy](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_contracts.py#L69) | 1 |
| [backend/routers/supplier_contracts.py:77 update_policy](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_contracts.py#L77) | 1 |
| [backend/routers/supplier_contracts.py:90 resolve_contract](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_contracts.py#L90) | 1 |
| [backend/routers/supplier_contracts.py:104 tariff_preview](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_contracts.py#L104) | 1 |
| [backend/routers/supplier_contracts.py:114 get_contract](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_contracts.py#L114) | 1 |
| [backend/routers/supplier_contracts.py:123 create_contract](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_contracts.py#L123) | 1 |
| [backend/routers/supplier_contracts.py:140 patch_contract](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_contracts.py#L140) | 1 |
| [backend/routers/supplier_contracts.py:154 set_contract_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_contracts.py#L154) | 1 |
| [backend/routers/supplier_contracts.py:168 delete_contract](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_contracts.py#L168) | 1 |
| [backend/routers/supplier_contracts.py:196 partner_scorecard](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_contracts.py#L196) | 1 |
| [backend/routers/supplier_items.py:43 list_supplier_items](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_items.py#L43) | 1 |
| [backend/routers/supplier_items.py:64 supplier_item_stats](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_items.py#L64) | 1 |
| [backend/routers/supplier_items.py:75 lookup_supplier_item](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_items.py#L75) | 1 |
| [backend/routers/supplier_items.py:96 import_template](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_items.py#L96) | 1 |
| [backend/routers/supplier_items.py:104 import_supplier_items](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_items.py#L104) | 1 |
| [backend/routers/supplier_items.py:126 import_supplier_items_file](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_items.py#L126) | 1 |
| [backend/routers/supplier_items.py:151 get_supplier_item](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_items.py#L151) | 1 |
| [backend/routers/supplier_items.py:160 create_supplier_item](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_items.py#L160) | 1 |
| [backend/routers/supplier_items.py:175 patch_supplier_item](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_items.py#L175) | 1 |
| [backend/routers/supplier_items.py:188 delete_supplier_item](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/supplier_items.py#L188) | 1 |
| [backend/routers/suppliers.py:33 list_suppliers](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/suppliers.py#L33) | 1 |
| [backend/routers/suppliers.py:66 create_supplier](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/suppliers.py#L66) | 1 |
| [backend/routers/suppliers.py:122 get_supplier](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/suppliers.py#L122) | 1 |
| [backend/routers/suppliers.py:140 update_supplier](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/suppliers.py#L140) | 1 |
| [backend/routers/suppliers.py:209 deactivate_supplier](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/suppliers.py#L209) | 1 |
| [backend/routers/suppliers.py:239 list_supplier_price_list](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/suppliers.py#L239) | 1 |
| [backend/routers/suppliers.py:253 create_supplier_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/suppliers.py#L253) | 1 |
| [backend/routers/suppliers.py:295 update_supplier_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/suppliers.py#L295) | 1 |
| [backend/routers/suppliers.py:326 deactivate_supplier_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/suppliers.py#L326) | 1 |
| [backend/routers/suppliers.py:341 resolve_supplier_price](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/suppliers.py#L341) | 1 |
| [backend/routers/suppliers.py:351 get_supplier_scorecard](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/suppliers.py#L351) | 1 |
| [backend/routers/suppliers.py:361 get_supplier_360](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/suppliers.py#L361) | 1 |
| [backend/routers/suppliers.py:373 get_supplier_return_policy](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/suppliers.py#L373) | 1 |
| [backend/routers/tax_center.py:37 get_tax_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/tax_center.py#L37) | 1 |
| [backend/routers/tax_center.py:49 list_pph_records](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/tax_center.py#L49) | 1 |
| [backend/routers/tax_center.py:60 create_pph_record](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/tax_center.py#L60) | 1 |
| [backend/routers/tax_center.py:77 delete_pph_record](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/tax_center.py#L77) | 1 |
| [backend/routers/tax_invoices.py:25 list_tax_invoices](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/tax_invoices.py#L25) | 1 |
| [backend/routers/tax_invoices.py:40 get_tax_invoice](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/tax_invoices.py#L40) | 1 |
| [backend/routers/tax_invoices.py:51 issue_for_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/tax_invoices.py#L51) | 1 |
| [backend/routers/tax_invoices.py:62 update_nsfp](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/tax_invoices.py#L62) | 1 |
| [backend/routers/tax_invoices.py:72 replace_faktur](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/tax_invoices.py#L72) | 1 |
| [backend/routers/tax_invoices.py:83 cancel_faktur](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/tax_invoices.py#L83) | 1 |
| [backend/routers/tax_invoices.py:93 faktur_document](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/tax_invoices.py#L93) | 1 |
| [backend/routers/transfers.py:93 list_transfers](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/transfers.py#L93) | 1 |
| [backend/routers/transfers.py:146 create_transfer](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/transfers.py#L146) | 1 |
| [backend/routers/transfers.py:265 create_inter_company_transfer](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/transfers.py#L265) | 1 |
| [backend/routers/transfers.py:390 get_transfer_detail](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/transfers.py#L390) | 1 |
| [backend/routers/transfers.py:412 approve_transfer](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/transfers.py#L412) | 1 |
| [backend/routers/transfers.py:506 reject_transfer](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/transfers.py#L506) | 1 |
| [backend/routers/transfers.py:547 update_transfer_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/transfers.py#L547) | 1 |
| [backend/routers/transfers.py:617 cancel_transfer](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/transfers.py#L617) | 1 |
| [backend/routers/uom_conversions.py:29 get_catalog](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uom_conversions.py#L29) | 1 |
| [backend/routers/uom_conversions.py:74 list_rules](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uom_conversions.py#L74) | 1 |
| [backend/routers/uom_conversions.py:83 create_rule](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uom_conversions.py#L83) | 1 |
| [backend/routers/uom_conversions.py:96 update_rule](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uom_conversions.py#L96) | 1 |
| [backend/routers/uom_conversions.py:110 toggle_rule](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uom_conversions.py#L110) | 1 |
| [backend/routers/uom_conversions.py:122 get_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uom_conversions.py#L122) | 1 |
| [backend/routers/uom_conversions.py:130 update_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uom_conversions.py#L130) | 1 |
| [backend/routers/uom_conversions.py:145 convert_preview](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uom_conversions.py#L145) | 1 |
| [backend/routers/uom_conversions.py:177 check_variance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uom_conversions.py#L177) | 1 |
| [backend/routers/uom_conversions.py:184 conversion_usage](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uom_conversions.py#L184) | 1 |
| [backend/routers/uoms.py:61 list_uoms](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uoms.py#L61) | 1 |
| [backend/routers/uoms.py:68 uom_vocab](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uoms.py#L68) | 1 |
| [backend/routers/uoms.py:85 create_uom](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uoms.py#L85) | 1 |
| [backend/routers/uoms.py:100 update_uom](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uoms.py#L100) | 1 |
| [backend/routers/uoms.py:137 delete_uom](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/uoms.py#L137) | 1 |
| [backend/routers/users.py:34 list_users](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/users.py#L34) | 1 |
| [backend/routers/users.py:68 count_users](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/users.py#L68) | 1 |
| [backend/routers/users.py:80 available_employees](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/users.py#L80) | 1 |
| [backend/routers/users.py:114 get_user](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/users.py#L114) | 1 |
| [backend/routers/users.py:122 create_user](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/users.py#L122) | 1 |
| [backend/routers/users.py:135 update_user](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/users.py#L135) | 1 |
| [backend/routers/users.py:161 deactivate_user](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/users.py#L161) | 1 |
| [backend/routers/users.py:175 reactivate_user](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/users.py#L175) | 1 |
| [backend/routers/users.py:184 reset_password](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/users.py#L184) | 1 |
| [backend/routers/users.py:197 revoke_sessions](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/users.py#L197) | 1 |
| [backend/routers/vehicle_logs.py:31 list_vehicles](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vehicle_logs.py#L31) | 1 |
| [backend/routers/vehicle_logs.py:39 create_vehicle](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vehicle_logs.py#L39) | 1 |
| [backend/routers/vehicle_logs.py:61 update_vehicle](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vehicle_logs.py#L61) | 1 |
| [backend/routers/vehicle_logs.py:85 delete_vehicle](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vehicle_logs.py#L85) | 1 |
| [backend/routers/vehicle_logs.py:125 list_vehicle_logs](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vehicle_logs.py#L125) | 1 |
| [backend/routers/vehicle_logs.py:136 vehicle_logs_summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vehicle_logs.py#L136) | 1 |
| [backend/routers/vehicle_logs.py:154 create_vehicle_log](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vehicle_logs.py#L154) | 1 |
| [backend/routers/vehicle_logs.py:177 update_vehicle_log](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vehicle_logs.py#L177) | 1 |
| [backend/routers/vehicle_logs.py:205 delete_vehicle_log](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vehicle_logs.py#L205) | 1 |
| [backend/routers/vendor_bills.py:43 po_billing_context](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vendor_bills.py#L43) | 1 |
| [backend/routers/vendor_bills.py:55 vendor_bill_payables](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vendor_bills.py#L55) | 1 |
| [backend/routers/vendor_bills.py:113 vendor_bill_status_counts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vendor_bills.py#L113) | 1 |
| [backend/routers/vendor_bills.py:126 list_vendor_bills](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vendor_bills.py#L126) | 1 |
| [backend/routers/vendor_bills.py:149 get_vendor_bill](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vendor_bills.py#L149) | 1 |
| [backend/routers/vendor_bills.py:163 create_vendor_bill](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vendor_bills.py#L163) | 1 |
| [backend/routers/vendor_bills.py:395 submit_vendor_bill](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vendor_bills.py#L395) | 1 |
| [backend/routers/vendor_bills.py:404 approve_vendor_bill](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vendor_bills.py#L404) | 3 |
| [backend/routers/vendor_bills.py:426 reject_vendor_bill](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vendor_bills.py#L426) | 3 |
| [backend/routers/vendor_bills.py:452 pay_vendor_bill](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vendor_bills.py#L452) | 1 |
| [backend/routers/vendor_bills.py:581 cancel_vendor_bill](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/vendor_bills.py#L581) | 1 |
| [backend/routers/warehouse_sites.py:38 get_sites](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/warehouse_sites.py#L38) | 1 |
| [backend/routers/warehouse_sites.py:44 post_site](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/warehouse_sites.py#L44) | 1 |
| [backend/routers/warehouse_sites.py:53 patch_site](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/warehouse_sites.py#L53) | 1 |
| [backend/routers/warehouse_sites.py:65 del_site](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/warehouse_sites.py#L65) | 1 |
| [backend/routers/warehouse_sites.py:73 post_seed_blueprint](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/warehouse_sites.py#L73) | 1 |
| [backend/routers/warehouses.py:44 get_warehouse_locations](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/warehouses.py#L44) | 1 |
| [backend/routers/warehouses.py:52 get_warehouse_occupancy](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/warehouses.py#L52) | 1 |
| [backend/routers/warehouses.py:70 put_warehouse_structure](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/warehouses.py#L70) | 1 |
| [backend/routers/warehouses.py:84 list_warehouses](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/warehouses.py#L84) | 1 |
| [backend/routers/warehouses.py:104 create_warehouse](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/warehouses.py#L104) | 1 |
| [backend/routers/warehouses.py:152 update_warehouse](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/warehouses.py#L152) | 1 |
| [backend/routers/warehouses.py:213 delete_warehouse](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/warehouses.py#L213) | 1 |
| [backend/routers/wilayah.py:11 countries](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/wilayah.py#L11) | 2 |
| [backend/routers/wilayah.py:17 provinces](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/wilayah.py#L17) | 2 |
| [backend/routers/wilayah.py:23 regencies](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/wilayah.py#L23) | 2 |
| [backend/routers/wilayah.py:29 districts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/wilayah.py#L29) | 2 |
| [backend/routers/wilayah.py:35 villages](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/wilayah.py#L35) | 2 |
| [backend/routers/wilayah.py:41 postal_code](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/wilayah.py#L41) | 2 |
| [backend/routers/wilayah.py:47 search](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/wilayah.py#L47) | 2 |
| [backend/routers/wilayah.py:53 validate](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/wilayah.py#L53) | 2 |
| [backend/routers/wms.py:28 list_tasks](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/wms.py#L28) | 1 |
| [backend/routers/wms.py:66 create_task](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/wms.py#L66) | 1 |
| [backend/routers/wms.py:134 create_outbound_from_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/wms.py#L134) | 1 |
| [backend/routers/wms.py:158 scan_task](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/wms.py#L158) | 1 |
| [backend/routers/wms.py:188 advance_task](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/wms.py#L188) | 1 |
| [backend/routers/work_desks.py:77 sales_admin_desk](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/work_desks.py#L77) | 1 |
| [backend/routers/work_desks.py:85 verification_preview](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/work_desks.py#L85) | 1 |
| [backend/routers/work_desks.py:93 verify_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/work_desks.py#L93) | 1 |
| [backend/routers/work_desks.py:109 fulfillment_options](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/work_desks.py#L109) | 1 |
| [backend/routers/work_desks.py:121 fulfillment_decision](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/work_desks.py#L121) | 1 |
| [backend/routers/work_desks.py:149 md_desk](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/work_desks.py#L149) | 1 |
| [backend/routers/work_desks.py:157 warehouse_admin_desk](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/work_desks.py#L157) | 1 |
| [backend/routers/work_desks.py:168 finance_desk](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/work_desks.py#L168) | 1 |
| [backend/routers/work_desks.py:190 my_desk](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/routers/work_desks.py#L190) | 6 |
| [backend/services/ai_usage_report.py:19 _tokens](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ai_usage_report.py#L19) | 1 |
| [backend/services/ai_usage_report.py:24 _when](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ai_usage_report.py#L24) | 1 |
| [backend/services/ai_usage_report.py:32 _user_key](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ai_usage_report.py#L32) | 1 |
| [backend/services/ai_usage_report.py:36 _summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ai_usage_report.py#L36) | 1 |
| [backend/services/ai_usage_report.py:51 _daily](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ai_usage_report.py#L51) | 1 |
| [backend/services/ai_usage_report.py:61 _names](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ai_usage_report.py#L61) | 1 |
| [backend/services/ai_usage_report.py:68 daily_report](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ai_usage_report.py#L68) | 1 |
| [backend/services/approval_backlog_service.py:176 _scope](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/approval_backlog_service.py#L176) | 2 |
| [backend/services/approval_backlog_service.py:596 queue_detail](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/approval_backlog_service.py#L596) | 18 |
| [backend/services/approval_backlog_service.py:658 boards](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/approval_backlog_service.py#L658) | 5 |
| [backend/services/ar_receipt_service.py:47 _payment_status](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ar_receipt_service.py#L47) | 3 |
| [backend/services/ar_receipt_service.py:273 _validate_allocation_target](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ar_receipt_service.py#L273) | 8 |
| [backend/services/ar_receipt_service.py:317 _apply_to_order](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/ar_receipt_service.py#L317) | 30 |
| [backend/services/atomic_claim.py:24 claim](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/atomic_claim.py#L24) | 6 |
| [backend/services/atomic_claim.py:48 finish_set](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/atomic_claim.py#L48) | 1 |
| [backend/services/atomic_claim.py:53 release](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/atomic_claim.py#L53) | 1 |
| [backend/services/bank_recon_service.py:108 _norm_dir](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_recon_service.py#L108) | 3 |
| [backend/services/bank_recon_service.py:115 _round](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_recon_service.py#L115) | 1 |
| [backend/services/bank_recon_service.py:140 _line](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_recon_service.py#L140) | 6 |
| [backend/services/bank_recon_service.py:575 _link](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_recon_service.py#L575) | 19 |
| [backend/services/bank_recon_service.py:691 manual_match](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_recon_service.py#L691) | 16 |
| [backend/services/bank_recon_service.py:724 match_split](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_recon_service.py#L724) | 24 |
| [backend/services/bank_recon_service.py:955 learn_from_manual](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_recon_service.py#L955) | 3 |
| [backend/services/bank_statement_parser.py:236 desc_key](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/bank_statement_parser.py#L236) | 5 |
| [backend/services/closing_service.py:404 status_for_date](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/closing_service.py#L404) | 6 |
| [backend/services/config_resolver.py:70 _dig](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_resolver.py#L70) | 6 |
| [backend/services/config_resolver.py:102 _legacy_doc](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_resolver.py#L102) | 1 |
| [backend/services/config_resolver.py:106 _stored_rows](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_resolver.py#L106) | 10 |
| [backend/services/config_resolver.py:123 _pick_effective](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_resolver.py#L123) | 4 |
| [backend/services/config_resolver.py:141 build_layers](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_resolver.py#L141) | 68 |
| [backend/services/config_resolver.py:182 _cfgv_layer](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_resolver.py#L182) | 19 |
| [backend/services/config_resolver.py:233 _decide](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_resolver.py#L233) | 8 |
| [backend/services/config_resolver.py:245 resolve](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_resolver.py#L245) | 13 |
| [backend/services/config_resolver.py:276 value_of](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_resolver.py#L276) | 1 |
| [backend/services/config_resolver.py:281 resolve_group](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_resolver.py#L281) | 20 |
| [backend/services/config_resolver.py:495 entity_overlay](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_resolver.py#L495) | 16 |
| [backend/services/config_resolver.py:530 apply_due_values](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_resolver.py#L530) | 7 |
| [backend/services/config_resolver.py:552 history](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_resolver.py#L552) | 7 |
| [backend/services/config_service.py:167 seed_config_defaults](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_service.py#L167) | 19 |
| [backend/services/config_service.py:205 _deep_merge](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_service.py#L205) | 6 |
| [backend/services/config_service.py:215 get_global_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_service.py#L215) | 5 |
| [backend/services/config_service.py:223 get_effective_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_service.py#L223) | 17 |
| [backend/services/config_service.py:255 compute_tax](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_service.py#L255) | 12 |
| [backend/services/config_service.py:304 evaluate_approval](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_service.py#L304) | 14 |
| [backend/services/config_simulator.py:596 catalog](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/config_simulator.py#L596) | 2 |
| [backend/services/custom_role_service.py:22 list_custom](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/custom_role_service.py#L22) | 1 |
| [backend/services/custom_role_service.py:26 sync_registry](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/custom_role_service.py#L26) | 1 |
| [backend/services/customer_service.py:122 _order_grand_total](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/customer_service.py#L122) | 1 |
| [backend/services/customer_service.py:126 _order_paid](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/customer_service.py#L126) | 1 |
| [backend/services/customer_service.py:130 order_payment_method](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/customer_service.py#L130) | 1 |
| [backend/services/entity_context_service.py:39 is_pkp](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_context_service.py#L39) | 1 |
| [backend/services/entity_context_service.py:44 all_active_entity_ids](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_context_service.py#L44) | 3 |
| [backend/services/entity_context_service.py:50 active_entity_ids_for](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_context_service.py#L50) | 5 |
| [backend/services/entity_context_service.py:73 entity_summaries](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_context_service.py#L73) | 7 |
| [backend/services/entity_context_service.py:92 build_entity_context](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_context_service.py#L92) | 14 |
| [backend/services/entity_lifecycle_service.py:78 get_entity_or_404](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_lifecycle_service.py#L78) | 3 |
| [backend/services/entity_lifecycle_service.py:85 is_write_locked](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_lifecycle_service.py#L85) | 1 |
| [backend/services/entity_lifecycle_service.py:90 uniform_entity](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_lifecycle_service.py#L90) | 32 |
| [backend/services/entity_lifecycle_service.py:134 first_issued_document](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_lifecycle_service.py#L134) | 13 |
| [backend/services/entity_lifecycle_service.py:166 prefix_lock_info](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_lifecycle_service.py#L166) | 5 |
| [backend/services/entity_lifecycle_service.py:399 entity_status_map](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_lifecycle_service.py#L399) | 12 |
| [backend/services/entity_lifecycle_service.py:421 assert_entity_writable_cached](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_lifecycle_service.py#L421) | 3 |
| [backend/services/entity_lifecycle_service.py:455 _collect_body_entities](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_lifecycle_service.py#L455) | 12 |
| [backend/services/entity_lifecycle_service.py:472 writable_entity_ids](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_lifecycle_service.py#L472) | 8 |
| [backend/services/entity_lifecycle_service.py:485 assert_body_entity_allowed](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_lifecycle_service.py#L485) | 20 |
| [backend/services/entity_lifecycle_service.py:517 readable_entity_ids](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_lifecycle_service.py#L517) | 9 |
| [backend/services/entity_lifecycle_service.py:552 assert_requested_entity_allowed](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_lifecycle_service.py#L552) | 4 |
| [backend/services/entity_master_service.py:218 spec](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_master_service.py#L218) | 3 |
| [backend/services/entity_master_service.py:235 _is_active](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_master_service.py#L235) | 2 |
| [backend/services/entity_master_service.py:314 effective_rows](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_master_service.py#L314) | 19 |
| [backend/services/entity_readiness_service.py:19 _usable_warehouses](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_readiness_service.py#L19) | 6 |
| [backend/services/entity_readiness_service.py:35 readiness](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/entity_readiness_service.py#L35) | 76 |
| [backend/services/esign_service.py:162 list_signatures](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/esign_service.py#L162) | 4 |
| [backend/services/esign_service.py:169 public_verify](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/esign_service.py#L169) | 5 |
| [backend/services/gl_service.py:429 _norm_lines](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L429) | 15 |
| [backend/services/gl_service.py:450 _account_names](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L450) | 4 |
| [backend/services/gl_service.py:463 enforce_closed_period_guard](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L463) | 7 |
| [backend/services/gl_service.py:499 _insert_entry](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L499) | 31 |
| [backend/services/gl_service.py:544 _mark_stale_closings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L544) | 8 |
| [backend/services/gl_service.py:695 _already_posted](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L695) | 3 |
| [backend/services/gl_service.py:2252 post_store_credit_redemption](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/gl_service.py#L2252) | 12 |
| [backend/services/home_service.py:20 _current_month](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/home_service.py#L20) | 1 |
| [backend/services/home_service.py:28 _month_progress](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/home_service.py#L28) | 2 |
| [backend/services/home_service.py:33 sales_home](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/home_service.py#L33) | 45 |
| [backend/services/home_service.py:230 _waiting_boards](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/home_service.py#L230) | 3 |
| [backend/services/home_service.py:251 warehouse_home](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/home_service.py#L251) | 3 |
| [backend/services/home_service.py:260 finance_home](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/home_service.py#L260) | 3 |
| [backend/services/hr_attendance_service.py:68 _hhmm](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_attendance_service.py#L68) | 3 |
| [backend/services/hr_attendance_service.py:76 compute_metrics](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_attendance_service.py#L76) | 20 |
| [backend/services/hr_attendance_service.py:113 default_shift](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_attendance_service.py#L113) | 4 |
| [backend/services/hr_attendance_service.py:120 resolve_shift](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_attendance_service.py#L120) | 3 |
| [backend/services/hr_attendance_service.py:193 upsert_attendance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_attendance_service.py#L193) | 23 |
| [backend/services/hr_leave_service.py:46 _parse_date](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L46) | 2 |
| [backend/services/hr_leave_service.py:53 working_days](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L53) | 12 |
| [backend/services/hr_leave_service.py:76 _annual_entitlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L76) | 4 |
| [backend/services/hr_leave_service.py:86 recompute_balance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L86) | 28 |
| [backend/services/hr_leave_service.py:120 get_balance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L120) | 5 |
| [backend/services/hr_leave_service.py:128 set_entitlement](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L128) | 6 |
| [backend/services/hr_leave_service.py:146 submit_leave](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L146) | 25 |
| [backend/services/hr_leave_service.py:180 _mark_attendance_for_leave](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L180) | 9 |
| [backend/services/hr_leave_service.py:193 _clear_attendance_for_leave](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L193) | 4 |
| [backend/services/hr_leave_service.py:202 approve_leave](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L202) | 10 |
| [backend/services/hr_leave_service.py:231 cancel_leave](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_leave_service.py#L231) | 11 |
| [backend/services/hr_payroll_service.py:74 _pct](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L74) | 1 |
| [backend/services/hr_payroll_service.py:79 _sum_allowances](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L79) | 4 |
| [backend/services/hr_payroll_service.py:92 bpjs_breakdown](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L92) | 25 |
| [backend/services/hr_payroll_service.py:127 _period_overtime_min](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L127) | 5 |
| [backend/services/hr_payroll_service.py:135 _period_filed_overtime_min](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L135) | 5 |
| [backend/services/hr_payroll_service.py:149 _overtime_amount](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L149) | 6 |
| [backend/services/hr_payroll_service.py:159 _commission_for](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L159) | 3 |
| [backend/services/hr_payroll_service.py:174 compute_payslip](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L174) | 29 |
| [backend/services/hr_payroll_service.py:445 get_payslip](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L445) | 1 |
| [backend/services/hr_payroll_service.py:449 my_payslips](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_payroll_service.py#L449) | 3 |
| [backend/services/hr_service.py:76 deep_merge](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_service.py#L76) | 6 |
| [backend/services/hr_service.py:92 get_hr_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/hr_service.py#L92) | 11 |
| [backend/services/inventory_service.py:26 expire_old_reservations](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/inventory_service.py#L26) | 12 |
| [backend/services/loading_check_service.py:17 _expected_rolls](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L17) | 5 |
| [backend/services/loading_check_service.py:25 start](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L25) | 31 |
| [backend/services/loading_check_service.py:68 complete](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L68) | 18 |
| [backend/services/loading_check_service.py:93 dispatch_guard](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/loading_check_service.py#L93) | 7 |
| [backend/services/master_registry.py:60 _seed_rows](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/master_registry.py#L60) | 3 |
| [backend/services/master_registry.py:79 rows](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/master_registry.py#L79) | 15 |
| [backend/services/master_registry.py:133 live_enum_values](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/master_registry.py#L133) | 6 |
| [backend/services/master_registry.py:168 stages](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/master_registry.py#L168) | 1 |
| [backend/services/master_registry.py:173 active_stages](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/master_registry.py#L173) | 5 |
| [backend/services/master_registry.py:249 process_types](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/master_registry.py#L249) | 8 |
| [backend/services/notification_scope.py:18 audience_roles](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/notification_scope.py#L18) | 7 |
| [backend/services/notification_scope.py:29 allowed_links](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/notification_scope.py#L29) | 7 |
| [backend/services/notification_scope.py:39 relevance_filter](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/notification_scope.py#L39) | 13 |
| [backend/services/period_unlock_service.py:50 _now](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/period_unlock_service.py#L50) | 1 |
| [backend/services/period_unlock_service.py:62 list_requests](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/period_unlock_service.py#L62) | 7 |
| [backend/services/period_unlock_service.py:79 active_unlocks](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/period_unlock_service.py#L79) | 6 |
| [backend/services/receiving_uom_service.py:63 get_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L63) | 1 |
| [backend/services/receiving_uom_service.py:87 update_settings](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L87) | 1 |
| [backend/services/receiving_uom_service.py:109 ensure_defaults](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L109) | 1 |
| [backend/services/receiving_uom_service.py:123 _n](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L123) | 1 |
| [backend/services/receiving_uom_service.py:127 _unit_label](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L127) | 1 |
| [backend/services/receiving_uom_service.py:132 _id_num](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L132) | 1 |
| [backend/services/receiving_uom_service.py:141 task_context](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L141) | 1 |
| [backend/services/receiving_uom_service.py:169 remaining_qty](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L169) | 1 |
| [backend/services/receiving_uom_service.py:178 _to_task_unit](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L178) | 3 |
| [backend/services/receiving_uom_service.py:196 convert_doc_qty](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L196) | 3 |
| [backend/services/receiving_uom_service.py:292 to_doc_uom](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L292) | 2 |
| [backend/services/receiving_uom_service.py:313 _value_of](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L313) | 1 |
| [backend/services/receiving_uom_service.py:318 uom_options](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L318) | 1 |
| [backend/services/receiving_uom_service.py:399 preview](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L399) | 2 |
| [backend/services/receiving_uom_service.py:420 dual_unit_message](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L420) | 2 |
| [backend/services/receiving_uom_service.py:437 prepare_scan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L437) | 1 |
| [backend/services/receiving_uom_service.py:459 over_limit_message](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L459) | 2 |
| [backend/services/receiving_uom_service.py:468 receive_tolerance_pct](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L468) | 1 |
| [backend/services/receiving_uom_service.py:476 preflight_scan](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/receiving_uom_service.py#L476) | 1 |
| [backend/services/rfid_incident_service.py:23 create_from_read](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_incident_service.py#L23) | 1 |
| [backend/services/rfid_incident_service.py:66 list_incidents](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_incident_service.py#L66) | 2 |
| [backend/services/rfid_incident_service.py:77 _transition](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_incident_service.py#L77) | 1 |
| [backend/services/rfid_incident_service.py:97 acknowledge](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_incident_service.py#L97) | 1 |
| [backend/services/rfid_incident_service.py:101 resolve](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_incident_service.py#L101) | 1 |
| [backend/services/rfid_incident_service.py:105 shrinkage_report](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_incident_service.py#L105) | 1 |
| [backend/services/rfid_incident_service.py:154 device_health](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_incident_service.py#L154) | 1 |
| [backend/services/rfid_ingest_service.py:20 ensure_api_key](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L20) | 1 |
| [backend/services/rfid_ingest_service.py:32 authenticate](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L32) | 6 |
| [backend/services/rfid_ingest_service.py:41 heartbeat](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L41) | 4 |
| [backend/services/rfid_ingest_service.py:47 _doc_gate_decision](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L47) | 12 |
| [backend/services/rfid_ingest_service.py:88 ingest](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L88) | 47 |
| [backend/services/rfid_ingest_service.py:144 pending_jobs_for_device](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L144) | 1 |
| [backend/services/rfid_ingest_service.py:153 ack_job_printed](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_ingest_service.py#L153) | 1 |
| [backend/services/rfid_print_service.py:41 generate_rfid_zpl](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L41) | 15 |
| [backend/services/rfid_print_service.py:210 scan_verify](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L210) | 9 |
| [backend/services/rfid_print_service.py:225 _verify_progress](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_print_service.py#L225) | 8 |
| [backend/services/rfid_service.py:39 generate_epc](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L39) | 3 |
| [backend/services/rfid_service.py:122 encode_tag](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rfid_service.py#L122) | 23 |
| [backend/services/rnd_gate.py:56 policy](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_gate.py#L56) | 5 |
| [backend/services/rnd_kpi_service.py:67 _division_map](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_kpi_service.py#L67) | 6 |
| [backend/services/rnd_kpi_service.py:106 period_options](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_kpi_service.py#L106) | 1 |
| [backend/services/rnd_kpi_service.py:110 normalize_period](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_kpi_service.py#L110) | 2 |
| [backend/services/rnd_kpi_service.py:115 period_start](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_kpi_service.py#L115) | 5 |
| [backend/services/rnd_kpi_service.py:171 _pct](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_kpi_service.py#L171) | 1 |
| [backend/services/rnd_kpi_service.py:193 weights](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_kpi_service.py#L193) | 10 |
| [backend/services/rnd_kpi_service.py:245 design_studio_stats](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_kpi_service.py#L245) | 10 |
| [backend/services/rnd_kpi_service.py:253 in_period](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_kpi_service.py#L253) | 1 |
| [backend/services/rnd_kpi_service.py:284 designer_kpi](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_kpi_service.py#L284) | 34 |
| [backend/services/rnd_kpi_service.py:408 _summary](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_kpi_service.py#L408) | 29 |
| [backend/services/rnd_kpi_service.py:453 _norm](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_kpi_service.py#L453) | 1 |
| [backend/services/rnd_kpi_service.py:457 my_rounds](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_kpi_service.py#L457) | 12 |
| [backend/services/rnd_kpi_service.py:504 my_kpi](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/rnd_kpi_service.py#L504) | 20 |
| [backend/services/role_desk_service.py:17 _scope_q](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/role_desk_service.py#L17) | 1 |
| [backend/services/role_desk_service.py:22 _turn_queue](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/role_desk_service.py#L22) | 1 |
| [backend/services/role_desk_service.py:38 _so_rows](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/role_desk_service.py#L38) | 1 |
| [backend/services/role_desk_service.py:45 _find](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/role_desk_service.py#L45) | 1 |
| [backend/services/role_desk_service.py:49 manager_queues](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/role_desk_service.py#L49) | 1 |
| [backend/services/role_desk_service.py:75 sales_queues](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/role_desk_service.py#L75) | 1 |
| [backend/services/role_desk_service.py:91 warehouse_queues](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/role_desk_service.py#L91) | 1 |
| [backend/services/role_desk_service.py:117 designer_queues](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/role_desk_service.py#L117) | 1 |
| [backend/services/role_desk_service.py:131 driver_queues](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/role_desk_service.py#L131) | 1 |
| [backend/services/role_desk_service.py:147 _days_ago](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/role_desk_service.py#L147) | 1 |
| [backend/services/role_desk_service.py:152 role_desk](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/role_desk_service.py#L152) | 1 |
| [backend/services/roll_service.py:73 child_roll_no](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L73) | 8 |
| [backend/services/roll_service.py:93 insert_child_roll](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L93) | 9 |
| [backend/services/roll_service.py:490 _split_roll](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/roll_service.py#L490) | 24 |
| [backend/services/sales_force_service.py:52 _expand_periods](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/sales_force_service.py#L52) | 9 |
| [backend/services/sales_force_service.py:89 sales_kpi](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/sales_force_service.py#L89) | 33 |
| [backend/services/sales_force_service.py:144 _target_collection_for](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/sales_force_service.py#L144) | 4 |
| [backend/services/sales_force_service.py:163 compute_commission](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/sales_force_service.py#L163) | 4 |
| [backend/services/sales_force_service.py:206 _load_incentive_rates](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/sales_force_service.py#L206) | 6 |
| [backend/services/sales_force_service.py:246 _compute_commission_per_sku](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/sales_force_service.py#L246) | 41 |
| [backend/services/sales_force_service.py:263 _live_wac](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/sales_force_service.py#L263) | 1 |
| [backend/services/sales_force_service.py:269 _hpp](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/sales_force_service.py#L269) | 1 |
| [backend/services/sales_force_service.py:274 cost_for_line](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/sales_force_service.py#L274) | 1 |
| [backend/services/sales_force_service.py:399 commission_history](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/sales_force_service.py#L399) | 14 |
| [backend/services/sales_ownership.py:46 is_owner_locked](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/sales_ownership.py#L46) | 1 |
| [backend/services/sales_ownership.py:83 apply_scope](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/sales_ownership.py#L83) | 2 |
| [backend/services/store_credit_service.py:34 _scope_clause](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/store_credit_service.py#L34) | 3 |
| [backend/services/store_credit_service.py:52 balance](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/store_credit_service.py#L52) | 6 |
| [backend/services/store_credit_service.py:113 _append](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/store_credit_service.py#L113) | 21 |
| [backend/services/store_credit_service.py:161 redeem](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/store_credit_service.py#L161) | 15 |
| [backend/services/store_credit_service.py:190 _redeem_locked](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/store_credit_service.py#L190) | 46 |
| [backend/services/supplier_item_service.py:67 attach_supplier_codes](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/supplier_item_service.py#L67) | 3 |
| [backend/services/text_normalize.py:64 phone_id](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/text_normalize.py#L64) | 8 |
| [backend/services/text_normalize.py:81 _phone_validator](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/text_normalize.py#L81) | 2 |
| [backend/services/trace_print_service.py:11 _col](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/trace_print_service.py#L11) | 1 |
| [backend/services/trace_print_service.py:15 build_trace_doc](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/trace_print_service.py#L15) | 1 |
| [backend/services/trace_print_service.py:55 render_trace](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/trace_print_service.py#L55) | 1 |
| [backend/services/turn_notification_service.py:158 after_audit](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/turn_notification_service.py#L158) | 3 |
| [backend/services/warehouse_scope_service.py:78 usable_query](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/warehouse_scope_service.py#L78) | 3 |
| [backend/services/warehouse_scope_service.py:91 entity_name_map](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/warehouse_scope_service.py#L91) | 3 |
| [backend/services/web_push_service.py:24 vapid_public_key](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/web_push_service.py#L24) | 1 |
| [backend/services/wilayah_service.py:40 _key](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/wilayah_service.py#L40) | 2 |
| [backend/services/wilayah_service.py:46 _db](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/wilayah_service.py#L46) | 21 |
| [backend/services/wilayah_service.py:71 provinces](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/wilayah_service.py#L71) | 1 |
| [backend/services/wilayah_service.py:75 regencies](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/wilayah_service.py#L75) | 1 |
| [backend/services/wilayah_service.py:79 districts](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/wilayah_service.py#L79) | 1 |
| [backend/services/wilayah_service.py:83 villages](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/wilayah_service.py#L83) | 1 |
| [backend/services/wilayah_service.py:87 by_postal_code](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/wilayah_service.py#L87) | 4 |
| [backend/services/wilayah_service.py:102 search](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/wilayah_service.py#L102) | 3 |
| [backend/services/wilayah_service.py:126 _bad](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/wilayah_service.py#L126) | 1 |
| [backend/services/wilayah_service.py:130 normalize_location](https://github.com/pandeyoga/KNHOST/blob/d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467/backend/services/wilayah_service.py#L130) | 25 |

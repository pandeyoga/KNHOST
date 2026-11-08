# B3a — Lampiran: SEMUA penulis per fakta (kode app, HEAD 5f1e36e)

Sumber: `python scripts/audit/b3a_db_writers.py --json calls.json` (AST, bukan grep) lalu diringkas per field.
Format baris: `berkas: baris(nilai status konstan)`. `<expr>` = nilai status dihitung saat jalan (variabel).
Keterbatasan: dokumen yang dirakit lintas fungsi/parameter tercatat sebagai 'insert dgn field tak terbaca' — penulis sebenarnya bisa LEBIH banyak dari daftar ini, tidak lebih sedikit.


### inventory_rolls.status: 63 panggilan tulis di 18 berkas (app)

- `backend/routers/inventory.py`: 495(available)
- `backend/routers/sales_orders_extra.py`: 628(available), 742(available)
- `backend/services/inbound_complete_service.py`: 426(<expr>)
- `backend/services/production_service.py`: 366(<expr>), 415(<expr>), 419(<expr>)
- `backend/services/purchase_return_service.py`: 606(available), 925(<expr>), 1041(available), 454(quarantine), 869(<expr>)
- `backend/services/putaway_order_service.py`: 408(<expr>), 475(<expr>), 366(in_transit_transfer), 373(<expr>)
- `backend/services/qc_service.py`: 67(<expr>)
- `backend/services/receiving_roll_service.py`: 99(receiving)
- `backend/services/repair_order_service.py`: 197(<expr>), 229(<expr>), 283(consumed), 296(available), 297(consumed), 305(available), 203(<expr>)
- `backend/services/return_cutloss_split_service.py`: 97(hold), 222(delivered), 160(<expr>), 174(damaged)
- `backend/services/return_disposition_service.py`: 255(damaged)
- `backend/services/return_service.py`: 1417(reserved), 1905(<expr>), 1132(quarantine), 1449(available)
- `backend/services/rnd_sample_service.py`: 1469(<expr>), 1513(<expr>)
- `backend/services/roll_hold_service.py`: 34(<expr>), 58(<expr>)
- `backend/services/roll_service.py`: 842(reserved), 2158(<expr>), 1310(available), 1419(<expr>), 1527(delivered), 1810(available), 1981(in_transit_transfer), 2014(available), 2054(<expr>), 2364(available), 1375(available), 1480(in_transit_sales), 1630(reserved), 1879(reserved), 1912(reserved), 2316(reserved), 1886(available)
- `backend/services/so_line_cancel_service.py`: 71(available)
- `backend/services/stock_bucket_service.py`: 125(<expr>), 252(<expr>), 302(consumed), 67(<expr>), 256(<expr>)
- `backend/services/transfer_receipt_service.py`: 213(<expr>), 377(<expr>)
- _(+ insert dgn field tak terbaca: backend/services/return_identity_service.py:[77, 71], backend/services/roll_service.py:[146, 557, 138])_

### inventory_rolls.warehouse_id: 12 panggilan tulis di 11 berkas (app)

- `backend/routers/inventory.py`: 495
- `backend/services/cutting_service.py`: 143
- `backend/services/inbound_complete_service.py`: 426
- `backend/services/purchase_return_service.py`: 606
- `backend/services/putaway_order_service.py`: 408
- `backend/services/receiving_roll_service.py`: 99
- `backend/services/return_cutloss_split_service.py`: 97
- `backend/services/return_identity_service.py`: 124
- `backend/services/return_service.py`: 1132
- `backend/services/roll_service.py`: 2158, 2014
- `backend/services/transfer_receipt_service.py`: 213
- _(+ insert dgn field tak terbaca: backend/services/repair_order_service.py:[296], backend/services/return_identity_service.py:[77, 71], backend/services/roll_service.py:[146, 557, 138])_

### inventory_rolls.bin_id: 10 panggilan tulis di 8 berkas (app)

- `backend/routers/inventory.py`: 495
- `backend/services/cutting_service.py`: 143
- `backend/services/inbound_complete_service.py`: 426
- `backend/services/location_service.py`: 295, 351
- `backend/services/putaway_order_service.py`: 408
- `backend/services/receiving_roll_service.py`: 99
- `backend/services/roll_service.py`: 2158, 2014
- `backend/services/transfer_receipt_service.py`: 213
- _(+ insert dgn field tak terbaca: backend/services/repair_order_service.py:[296], backend/services/return_identity_service.py:[77, 71], backend/services/return_service.py:[1132], backend/services/roll_service.py:[146, 557, 138])_

### inventory_rolls.owner_entity_id: 5 panggilan tulis di 5 berkas (app)

- `backend/routers/inventory.py`: 495
- `backend/services/inbound_complete_service.py`: 426
- `backend/services/receiving_roll_service.py`: 99
- `backend/services/return_service.py`: 1132
- `backend/services/roll_service.py`: 2158
- _(+ insert dgn field tak terbaca: backend/services/repair_order_service.py:[296], backend/services/return_identity_service.py:[77, 71], backend/services/roll_service.py:[146, 557, 138])_

### inventory_rolls.length_remaining: 35 panggilan tulis di 17 berkas (app)

- `backend/routers/inbound_scan_label.py`: 204
- `backend/routers/inventory.py`: 495
- `backend/services/inbound_complete_service.py`: 426
- `backend/services/mdq_cut_service.py`: 83
- `backend/services/production_service.py`: 415, 419
- `backend/services/purchase_return_service.py`: 1046, 878, 921
- `backend/services/qc_service.py`: 72
- `backend/services/receiving_roll_service.py`: 99
- `backend/services/repair_order_service.py`: 283, 296, 297, 305
- `backend/services/return_cutloss_split_service.py`: 160, 174
- `backend/services/return_disposition_service.py`: 255
- `backend/services/return_identity_service.py`: 124
- `backend/services/return_service.py`: 1132
- `backend/services/rnd_sample_service.py`: 1469, 1513
- `backend/services/roll_service.py`: 637, 859, 2158, 1382, 1486, 1643, 1923, 2327
- `backend/services/sample_sale_service.py`: 429, 438
- `backend/services/stock_bucket_service.py`: 155, 302, 74
- _(+ insert dgn field tak terbaca: backend/services/return_identity_service.py:[77, 71], backend/services/roll_service.py:[146, 557, 138])_

### inventory_rolls.length_reserved: 2 panggilan tulis di 2 berkas (app)

- `backend/services/repair_order_service.py`: 296
- `backend/services/roll_service.py`: 587
- _(+ insert dgn field tak terbaca: backend/routers/inventory.py:[495], backend/services/inbound_complete_service.py:[426], backend/services/receiving_roll_service.py:[99], backend/services/return_identity_service.py:[77, 71], backend/services/return_service.py:[1132], backend/services/roll_service.py:[146, 2158, 557, 138])_

### inventory_rolls.grade: 14 panggilan tulis di 13 berkas (app)

- `backend/bootstrap.py`: 596
- `backend/routers/inbound_scan_label.py`: 204
- `backend/routers/inventory.py`: 495
- `backend/services/grade_service.py`: 93
- `backend/services/inbound_complete_service.py`: 426
- `backend/services/purchase_return_service.py`: 606
- `backend/services/qc_service.py`: 409
- `backend/services/receiving_roll_service.py`: 99
- `backend/services/repair_order_service.py`: 296, 305
- `backend/services/return_cutloss_split_service.py`: 160
- `backend/services/return_identity_service.py`: 124
- `backend/services/return_service.py`: 1132
- `backend/services/roll_service.py`: 2158
- _(+ insert dgn field tak terbaca: backend/services/return_identity_service.py:[77, 71], backend/services/roll_service.py:[146, 557, 138])_

### inventory_rolls.rfid_tag_id: 11 panggilan tulis di 8 berkas (app)

- `backend/routers/inventory.py`: 495
- `backend/services/inbound_complete_service.py`: 426
- `backend/services/initial_registration_approve.py`: 47
- `backend/services/loading_check_service.py`: 215
- `backend/services/receiving_roll_service.py`: 99
- `backend/services/rfid_print_service.py`: 129
- `backend/services/rfid_service.py`: 129, 174
- `backend/services/roll_service.py`: 146, 2158, 138
- _(+ insert dgn field tak terbaca: backend/services/repair_order_service.py:[296], backend/services/return_identity_service.py:[77, 71], backend/services/return_service.py:[1132], backend/services/roll_service.py:[557])_

### inventory_rolls.journey: 11 panggilan tulis di 8 berkas (app)

- `backend/services/backorder_service.py`: 170
- `backend/services/inbound_complete_service.py`: 423, 426
- `backend/services/putaway_order_service.py`: 588
- `backend/services/receiving_roll_service.py`: 99
- `backend/services/return_service.py`: 1132
- `backend/services/rfid_print_service.py`: 45, 432, 401
- `backend/services/rfid_service.py`: 174
- `backend/services/roll_service.py`: 782
- _(+ insert dgn field tak terbaca: backend/routers/inventory.py:[495], backend/services/repair_order_service.py:[296], backend/services/return_identity_service.py:[77, 71], backend/services/roll_service.py:[146, 2158, 557, 138])_

### inventory_rolls.lot_id: 7 panggilan tulis di 6 berkas (app)

- `backend/routers/inventory.py`: 495
- `backend/services/inbound_complete_service.py`: 426
- `backend/services/receiving_roll_service.py`: 99
- `backend/services/repair_order_service.py`: 296
- `backend/services/return_service.py`: 1132
- `backend/services/roll_service.py`: 2158, 1733
- _(+ insert dgn field tak terbaca: backend/services/return_identity_service.py:[77, 71], backend/services/roll_service.py:[146, 557, 138])_

### inventory_rolls.reserved_ref: 26 panggilan tulis di 10 berkas (app)

- `backend/routers/inventory.py`: 495
- `backend/routers/sales_orders_extra.py`: 628, 742
- `backend/services/inbound_complete_service.py`: 426
- `backend/services/receiving_roll_service.py`: 99
- `backend/services/repair_order_service.py`: 296
- `backend/services/return_identity_service.py`: 124
- `backend/services/return_service.py`: 1417, 1132, 1449
- `backend/services/roll_service.py`: 842, 2158, 1310, 1810, 2014, 2054, 2364, 1375, 1630, 1879, 1912, 2316, 1886
- `backend/services/so_line_cancel_service.py`: 71
- `backend/services/transfer_receipt_service.py`: 213, 377
- _(+ insert dgn field tak terbaca: backend/services/return_identity_service.py:[77, 71], backend/services/roll_service.py:[146, 557, 138])_

### inventory_rolls.active_movement: 4 panggilan tulis di 1 berkas (app)

- `backend/services/putaway_order_service.py`: 176, 242, 408, 475
- _(+ insert dgn field tak terbaca: backend/routers/inventory.py:[495], backend/services/inbound_complete_service.py:[426], backend/services/receiving_roll_service.py:[99], backend/services/repair_order_service.py:[296], backend/services/return_identity_service.py:[77, 71], backend/services/return_service.py:[1132], backend/services/roll_service.py:[146, 2158, 557, 138])_

### inventory_rolls.hold: 2 panggilan tulis di 1 berkas (app)

- `backend/services/roll_hold_service.py`: 34, 58
- _(+ insert dgn field tak terbaca: backend/routers/inventory.py:[495], backend/services/inbound_complete_service.py:[426], backend/services/receiving_roll_service.py:[99], backend/services/repair_order_service.py:[296], backend/services/return_identity_service.py:[77, 71], backend/services/return_service.py:[1132], backend/services/roll_service.py:[146, 2158, 557, 138])_

### inventory_rolls.inspection: 7 panggilan tulis di 5 berkas (app)

- `backend/services/inspection_service.py`: 1663, 1699
- `backend/services/qc_inspection_service.py`: 175
- `backend/services/return_identity_service.py`: 124
- `backend/services/return_service.py`: 1132
- `backend/services/roll_hold_service.py`: 58, 64
- _(+ insert dgn field tak terbaca: backend/routers/inventory.py:[495], backend/services/inbound_complete_service.py:[426], backend/services/receiving_roll_service.py:[99], backend/services/repair_order_service.py:[296], backend/services/return_identity_service.py:[77, 71], backend/services/roll_service.py:[146, 2158, 557, 138])_

### inventory_rolls.earmarked_for: 13 panggilan tulis di 8 berkas (app)

- `backend/routers/inventory.py`: 495
- `backend/routers/pegging.py`: 102, 116
- `backend/services/customer_merge_service.py`: 83
- `backend/services/inbound_complete_service.py`: 426
- `backend/services/receiving_roll_service.py`: 99
- `backend/services/return_identity_service.py`: 124
- `backend/services/return_service.py`: 1132
- `backend/services/roll_service.py`: 146, 842, 2158, 138, 2316
- _(+ insert dgn field tak terbaca: backend/services/repair_order_service.py:[296], backend/services/return_identity_service.py:[77, 71], backend/services/roll_service.py:[557])_

### inventory_rolls.bucket_ref: 11 panggilan tulis di 2 berkas (app)

- `backend/services/repair_order_service.py`: 197, 229, 283, 296, 297, 305, 203
- `backend/services/stock_bucket_service.py`: 125, 252, 67, 256
- _(+ insert dgn field tak terbaca: backend/routers/inventory.py:[495], backend/services/inbound_complete_service.py:[426], backend/services/receiving_roll_service.py:[99], backend/services/return_identity_service.py:[77, 71], backend/services/return_service.py:[1132], backend/services/roll_service.py:[146, 2158, 557, 138])_

### inventory_rolls.transfer_ref: 5 panggilan tulis di 2 berkas (app)

- `backend/services/roll_service.py`: 2054
- `backend/services/transfer_receipt_service.py`: 213, 377, 118, 125
- _(+ insert dgn field tak terbaca: backend/routers/inventory.py:[495], backend/services/inbound_complete_service.py:[426], backend/services/receiving_roll_service.py:[99], backend/services/repair_order_service.py:[296], backend/services/return_identity_service.py:[77, 71], backend/services/return_service.py:[1132], backend/services/roll_service.py:[146, 2158, 557, 138])_

### inventory_rolls.last_scan: 2 panggilan tulis di 1 berkas (app)

- `backend/routers/rfid.py`: 216, 144
- _(+ insert dgn field tak terbaca: backend/routers/inventory.py:[495], backend/services/inbound_complete_service.py:[426], backend/services/receiving_roll_service.py:[99], backend/services/repair_order_service.py:[296], backend/services/return_identity_service.py:[77, 71], backend/services/return_service.py:[1132], backend/services/roll_service.py:[146, 2158, 557, 138])_

### inventory_rolls.gate_exit: 1 panggilan tulis di 1 berkas (app)

- `backend/services/gate_evaluator.py`: 173
- _(+ insert dgn field tak terbaca: backend/routers/inventory.py:[495], backend/services/inbound_complete_service.py:[426], backend/services/receiving_roll_service.py:[99], backend/services/repair_order_service.py:[296], backend/services/return_identity_service.py:[77, 71], backend/services/return_service.py:[1132], backend/services/roll_service.py:[146, 2158, 557, 138])_

### inventory_balances.available_qty: 1 panggilan tulis di 1 berkas (app)

- `backend/bootstrap.py`: 142

### inventory_balances.on_hand_qty: 2 panggilan tulis di 2 berkas (app)

- `backend/bootstrap.py`: 142
- `backend/services/roll_service.py`: 343

### inventory_balances.id: 2 panggilan tulis di 2 berkas (app)

- `backend/bootstrap.py`: 142
- `backend/services/roll_service.py`: 266

### inventory_lots.qty_remaining: 1 panggilan tulis di 1 berkas (app)

- `backend/services/lot_service.py`: 316
- _(+ insert dgn field tak terbaca: backend/services/lot_service.py:[224])_

### inventory_lots.roll_count: 1 panggilan tulis di 1 berkas (app)

- `backend/services/lot_service.py`: 316
- _(+ insert dgn field tak terbaca: backend/services/lot_service.py:[224])_

### inventory_lots.lot_status: 1 panggilan tulis di 1 berkas (app)

- `backend/services/lot_service.py`: 535
- _(+ insert dgn field tak terbaca: backend/services/lot_service.py:[224])_

### inventory_lots.owner_entity_id: 0 panggilan tulis di 0 berkas (app)

- _(+ insert dgn field tak terbaca: backend/services/lot_service.py:[224])_

### rfid_tags.status: 7 panggilan tulis di 5 berkas (app)

- `backend/services/initial_registration_approve.py`: 46(retired)
- `backend/services/initial_registration_lines.py`: 314(active)
- `backend/services/receiving_roll_service.py`: 396(retired)
- `backend/services/rfid_print_service.py`: 253(active)
- `backend/services/rfid_service.py`: 167(retired), 125(<expr>), 484(retired)

### rfid_tags.roll_id: 1 panggilan tulis di 1 berkas (app)

- `backend/services/rfid_service.py`: 125

### rfid_tags.epc: 2 panggilan tulis di 1 berkas (app)

- `backend/services/rfid_service.py`: 125, 455

### rfid_tags.last_seen_warehouse_id: 3 panggilan tulis di 2 berkas (app)

- `backend/services/rfid_ingest_service.py`: 215
- `backend/services/rfid_service.py`: 314, 125

### rfid_tags.owner_entity_id: 2 panggilan tulis di 2 berkas (app)

- `backend/services/rfid_service.py`: 125
- `backend/services/roll_service.py`: 1735

### wms_tasks.status: 23 panggilan tulis di 13 berkas (app)

- `backend/routers/inbound_receiving.py`: 142(qc_check), 200(escalated), 277(waiting_goods)
- `backend/routers/outbound_picking.py`: 20(created), 106(created), 231(packing), 288(escalated), 448(packing)
- `backend/routers/purchase_orders.py`: 167(<expr>)
- `backend/routers/purchase_orders_extra.py`: 127(cancelled), 268(cancelled)
- `backend/routers/sales_orders_extra.py`: 885(cancelled)
- `backend/routers/wms.py`: 110(<expr>), 268(<expr>)
- `backend/services/fulfillment_status.py`: 132(<expr>)
- `backend/services/inbound_complete_service.py`: 545(<expr>)
- `backend/services/makloon_receipt_qc.py`: 124(qc_pending)
- `backend/services/receiving_roll_service.py`: 137(qc_check), 418(waiting_goods)
- `backend/services/sample_sale_service.py`: 284(<expr>)
- `backend/services/so_line_cancel_service.py`: 85(cancelled)
- `backend/services/transfer_receipt_service.py`: 160(cancelled), 169(created)

### warehouse_transfers.status: 8 panggilan tulis di 5 berkas (app)

- `backend/routers/transfers.py`: 419(waiting_approval)
- `backend/services/interco_return_service.py`: 651(waiting_approval)
- `backend/services/interco_service.py`: 1732(waiting_approval), 595(cancelled)
- `backend/services/return_service.py`: 1442(executing), 1472(completed), 1452(cancelled)
- `backend/services/transfer_receipt_service.py`: 246(<expr>)
- _(+ insert dgn field tak terbaca: backend/routers/transfers.py:[265])_

### putaway_orders.status: 3 panggilan tulis di 2 berkas (app)

- `backend/services/putaway_draft_service.py`: 376(cancelled), 141(draft)
- `backend/services/putaway_order_service.py`: 321(open)

### shipments.status: 3 panggilan tulis di 3 berkas (app)

- `backend/services/return_cutloss_split_service.py`: 244(dispatched)
- `backend/services/return_roll_settlement_service.py`: 527(dispatched)
- `backend/services/shipment_service.py`: 117(dispatched)

### goods_receipts.status: 4 panggilan tulis di 3 berkas (app)

- `backend/services/goods_receipt_ocr_service.py`: 507(review)
- `backend/services/goods_receipt_service.py`: 205(draft), 671(review)
- `backend/services/makloon_order_service.py`: 1385(cancelled)

### cycle_count_sessions.status: 10 panggilan tulis di 2 berkas (app)

- `backend/routers/cycle_count.py`: 80(open), 203(submitted), 240(open), 326(rejected)
- `backend/services/initial_registration_service.py`: 86(draft), 110(running), 180(pending_approval), 193(running), 207(rejected), 121(draft)

### material_reservations.status: 3 panggilan tulis di 1 berkas (app)

- `backend/services/material_reservation_service.py`: 175(released), 144(<expr>), 105(<expr>)

### material_reservations.qty: 2 panggilan tulis di 1 berkas (app)

- `backend/services/material_reservation_service.py`: 144, 105
